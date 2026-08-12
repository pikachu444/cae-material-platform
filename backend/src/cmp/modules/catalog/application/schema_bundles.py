"""Plan, atomically apply, and export Catalog Schema Definition Bundles."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from cmp.modules.artifacts.domain.content import ArtifactRecord
from cmp.modules.catalog.domain.schema_bundles import (
    BUNDLE_CONTRACT_ID,
    CatalogSnapshot,
    PlanDisposition,
    SchemaBundlePlan,
    SourceArtifactIdentity,
    build_schema_bundle_plan,
    media_type_supported,
)
from cmp.modules.identity_access.domain.authorization import AuthorizationDecision, Permission
from cmp.modules.identity_access.domain.security import SecurityContext

MAX_SCHEMA_DEFINITION_BUNDLE_BYTES = 64 * 1024 * 1024
APPLICATION_CONTRACT_ID = (
    "https://cmp.example/contracts/catalog/schema-definition-bundle-application.schema.json"
)
APPLICATION_CONTRACT_VERSION = "1.0.0"
APPLIED_EVENT_TYPE = "io.cmp.catalog.schema-definition-bundle.applied.v1"
APPLIED_EVENT_SCHEMA = (
    "https://cmp.example/contracts/events/catalog-schema-definition-bundle-applied.v1.schema.json"
)


class SchemaBundlePlannerError(RuntimeError):
    """Base error for source and planner boundary failures."""


class SchemaBundleSourceConflict(SchemaBundlePlannerError):
    """The requested Artifact identity or media evidence is not eligible for planning."""


class SchemaBundleStalePlan(SchemaBundlePlannerError):
    """The approved plan fingerprint no longer matches the locked Catalog snapshot."""


class SchemaBundleIdempotencyConflict(SchemaBundlePlannerError):
    """An idempotency key was reused for a different apply request."""


class SchemaBundleVersionConflict(SchemaBundlePlannerError):
    """A bundle semantic version was reused for different canonical content."""


class SchemaBundleMigrationRequired(SchemaBundlePlannerError):
    """Current Catalog Records prevent a schema revision without explicit migration."""


class SchemaBundleApplicationNotFound(SchemaBundlePlannerError):
    """No tenant-visible bundle application matched the requested identity."""


class SchemaBundleExportConflict(SchemaBundlePlannerError):
    """Current Catalog state no longer matches the exact applied bundle bindings."""


@dataclass(frozen=True, slots=True)
class PlanSchemaDefinitionBundle:
    artifact_id: UUID
    expected_sha256: str

    def __post_init__(self) -> None:
        if self.artifact_id.int == 0:
            raise ValueError("artifact_id must be non-zero")
        if re.fullmatch(r"[0-9a-f]{64}", self.expected_sha256) is None:
            raise ValueError("expected_sha256 must be a lowercase SHA-256 digest")


@dataclass(frozen=True, slots=True)
class ApplySchemaDefinitionBundle:
    artifact_id: UUID
    expected_sha256: str
    plan_fingerprint: str
    idempotency_key: str
    delete_missing: bool = False

    def __post_init__(self) -> None:
        if self.artifact_id.int == 0:
            raise ValueError("artifact_id must be non-zero")
        for name, value in (
            ("expected_sha256", self.expected_sha256),
            ("plan_fingerprint", self.plan_fingerprint),
        ):
            if re.fullmatch(r"[0-9a-f]{64}", value) is None:
                raise ValueError(f"{name} must be a lowercase SHA-256 digest")
        if not 1 <= len(self.idempotency_key) <= 255 or any(
            ord(character) < 0x21 or ord(character) > 0x7E for character in self.idempotency_key
        ):
            raise ValueError("idempotency_key must contain 1..255 visible ASCII characters")
        if self.delete_missing:
            raise ValueError("Schema Definition Bundle v1 requires delete_missing=false")


@dataclass(frozen=True, slots=True)
class AppliedSchemaObject:
    sequence: int
    disposition: PlanDisposition
    target_type: str
    external_key: str
    parent_external_key: str | None
    aggregate_id: UUID | None
    revision_id: UUID | None
    content_hash: str
    published: bool
    source_schema_id: str
    source_schema_version: str
    source_pointer: str

    def canonical(self) -> dict[str, object]:
        return {
            "sequence": self.sequence,
            "disposition": self.disposition.value,
            "target_type": self.target_type,
            "external_key": self.external_key,
            "parent_external_key": self.parent_external_key,
            "aggregate_id": str(self.aggregate_id) if self.aggregate_id is not None else None,
            "revision_id": str(self.revision_id) if self.revision_id is not None else None,
            "content_hash": self.content_hash,
            "published": self.published,
            "source_schema_id": self.source_schema_id,
            "source_schema_version": self.source_schema_version,
            "source_pointer": self.source_pointer,
        }


@dataclass(frozen=True, slots=True)
class SchemaBundleApplication:
    application_id: UUID
    bundle_id: UUID
    bundle_key: str
    bundle_version: str
    classification: str
    source_artifact: SourceArtifactIdentity
    plan_fingerprint: str
    before_snapshot_fingerprint: str
    after_snapshot_fingerprint: str
    results: tuple[AppliedSchemaObject, ...]
    mutations_applied: bool
    applied_at: datetime
    applied_by: UUID
    idempotency_key: str
    replayed: bool = False

    def canonical(self) -> dict[str, object]:
        return {
            "$schema": APPLICATION_CONTRACT_ID,
            "contract_version": APPLICATION_CONTRACT_VERSION,
            "application_id": str(self.application_id),
            "bundle_id": str(self.bundle_id),
            "bundle_key": self.bundle_key,
            "bundle_version": self.bundle_version,
            "classification": self.classification,
            "source_artifact": self.source_artifact.canonical(),
            "plan_fingerprint": self.plan_fingerprint,
            "before_snapshot_fingerprint": self.before_snapshot_fingerprint,
            "after_snapshot_fingerprint": self.after_snapshot_fingerprint,
            "results": [result.canonical() for result in self.results],
            "mutations_applied": self.mutations_applied,
            "delete_missing": False,
            "applied_at": self.applied_at.isoformat().replace("+00:00", "Z"),
            "applied_by": str(self.applied_by),
            "idempotency_key": self.idempotency_key,
        }


@dataclass(frozen=True, slots=True)
class SchemaBundleExportDescriptor:
    application: SchemaBundleApplication
    canonical_bundle_sha256: str


@dataclass(frozen=True, slots=True)
class ExportedSchemaDefinitionBundle:
    value: bytes
    sha256: str
    application_id: UUID
    bundle_key: str
    bundle_version: str
    source_artifact_id: UUID
    source_artifact_sha256: str


class VerifiedArtifactReader(Protocol):
    async def read_verified_bytes(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        artifact_id: UUID,
        *,
        maximum_bytes: int,
    ) -> tuple[ArtifactRecord, bytes]: ...


class SchemaBundleSnapshotRepository(Protocol):
    def read_snapshot(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
    ) -> CatalogSnapshot: ...


class SchemaBundleApplicationRepository(Protocol):
    def apply(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: ApplySchemaDefinitionBundle,
        source: SourceArtifactIdentity,
        raw_bytes: bytes,
    ) -> SchemaBundleApplication: ...

    def get_application(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        application_id: UUID,
    ) -> SchemaBundleApplication: ...

    def resolve_export(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        bundle_key: str,
    ) -> SchemaBundleExportDescriptor: ...


def _require(
    context: SecurityContext,
    decision: AuthorizationDecision,
    permission: Permission,
) -> None:
    if (
        decision.permission is not permission
        or decision.principal_id != context.principal.id
        or decision.organization_id != context.organization_id
        or decision.project_id != context.project_id
        or decision.request_id != context.request_id
        or decision.trace_id != context.trace_id
    ):
        raise SchemaBundleSourceConflict(
            "authorization decision does not match the Schema Definition Bundle request"
        )


class SchemaBundlePlannerService:
    """Plan, apply, read back, and export one exact immutable bundle Artifact."""

    def __init__(
        self,
        *,
        artifacts: VerifiedArtifactReader,
        snapshots: SchemaBundleSnapshotRepository,
        applications: SchemaBundleApplicationRepository | None = None,
    ) -> None:
        self._artifacts = artifacts
        self._snapshots = snapshots
        self._applications = applications

    async def _source(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        artifact_id: UUID,
        expected_sha256: str,
    ) -> tuple[SourceArtifactIdentity, bytes]:
        record, raw_bytes = await self._artifacts.read_verified_bytes(
            context,
            decision,
            artifact_id,
            maximum_bytes=MAX_SCHEMA_DEFINITION_BUNDLE_BYTES,
        )
        artifact = record.artifact
        if artifact.id != artifact_id or artifact.sha256 != expected_sha256:
            raise SchemaBundleSourceConflict(
                "Artifact identity or digest differs from the exact request"
            )
        if (
            artifact.organization_id != context.organization_id
            or artifact.project_id != context.project_id
        ):
            raise SchemaBundleSourceConflict("Artifact tenant scope differs from the request")
        if len(raw_bytes) != artifact.size_bytes:
            raise SchemaBundleSourceConflict(
                "Artifact byte count differs from its immutable manifest"
            )
        if not media_type_supported(artifact.media_type):
            raise SchemaBundleSourceConflict(
                "Artifact media type is not a supported JSON Schema Definition Bundle type"
            )
        return (
            SourceArtifactIdentity(
                artifact.id,
                artifact.organization_id,
                artifact.project_id,
                artifact.classification,
                artifact.media_type,
                artifact.size_bytes,
                artifact.sha256,
            ),
            raw_bytes,
        )

    async def plan(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: PlanSchemaDefinitionBundle,
    ) -> SchemaBundlePlan:
        _require(context, decision, Permission.CATALOG_WRITE)
        source, raw_bytes = await self._source(
            context, decision, command.artifact_id, command.expected_sha256
        )
        snapshot = self._snapshots.read_snapshot(context=context, decision=decision)
        if (
            snapshot.organization_id != context.organization_id
            or snapshot.project_id != context.project_id
        ):
            raise SchemaBundleSourceConflict("Catalog snapshot tenant scope is inconsistent")
        return build_schema_bundle_plan(
            source=source,
            raw_bytes=raw_bytes,
            snapshot=snapshot,
            organization_id=context.organization_id,
            project_id=context.project_id,
            classification_allowed=lambda classification: decision.allows(
                context.organization_id,
                context.project_id,
                classification,
            ),
        )

    def _required_applications(self) -> SchemaBundleApplicationRepository:
        if self._applications is None:
            raise SchemaBundlePlannerError("Schema Definition Bundle apply/export is unavailable")
        return self._applications

    async def apply(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: ApplySchemaDefinitionBundle,
    ) -> SchemaBundleApplication:
        _require(context, decision, Permission.CATALOG_SCHEMA_APPLY)
        source, raw_bytes = await self._source(
            context, decision, command.artifact_id, command.expected_sha256
        )
        return self._required_applications().apply(
            context=context,
            decision=decision,
            command=command,
            source=source,
            raw_bytes=raw_bytes,
        )

    def get_application(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        application_id: UUID,
    ) -> SchemaBundleApplication:
        _require(context, decision, Permission.CATALOG_SCHEMA_APPLY)
        return self._required_applications().get_application(
            context=context,
            decision=decision,
            application_id=application_id,
        )

    async def export(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        bundle_key: str,
    ) -> ExportedSchemaDefinitionBundle:
        _require(context, decision, Permission.CATALOG_SCHEMA_APPLY)
        descriptor = self._required_applications().resolve_export(
            context=context,
            decision=decision,
            bundle_key=bundle_key,
        )
        source = descriptor.application.source_artifact
        verified, raw_bytes = await self._source(
            context, decision, source.artifact_id, source.sha256
        )
        try:
            document = json.loads(raw_bytes)
        except (UnicodeError, json.JSONDecodeError) as error:  # pragma: no cover - verified apply
            raise SchemaBundleExportConflict("Stored source bundle is no longer JSON") from error
        from cmp.shared.domain.revisions import canonical_json_bytes, content_sha256

        value = canonical_json_bytes(document)
        digest = content_sha256(document)
        if digest != descriptor.canonical_bundle_sha256:
            raise SchemaBundleExportConflict(
                "Stored source bundle differs from the applied canonical version"
            )
        if not isinstance(document, dict) or document.get("$schema") != BUNDLE_CONTRACT_ID:
            raise SchemaBundleExportConflict("Stored source is not a Bundle v1 document")
        return ExportedSchemaDefinitionBundle(
            value=value,
            sha256=digest,
            application_id=descriptor.application.application_id,
            bundle_key=descriptor.application.bundle_key,
            bundle_version=descriptor.application.bundle_version,
            source_artifact_id=verified.artifact_id,
            source_artifact_sha256=verified.sha256,
        )

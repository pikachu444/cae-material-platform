"""No-write application service for Catalog Schema Definition Bundle planning."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from cmp.modules.artifacts.domain.content import ArtifactRecord
from cmp.modules.catalog.domain.schema_bundles import (
    CatalogSnapshot,
    SchemaBundlePlan,
    SourceArtifactIdentity,
    build_schema_bundle_plan,
    media_type_supported,
)
from cmp.modules.identity_access.domain.authorization import AuthorizationDecision, Permission
from cmp.modules.identity_access.domain.security import SecurityContext

MAX_SCHEMA_DEFINITION_BUNDLE_BYTES = 64 * 1024 * 1024


class SchemaBundlePlannerError(RuntimeError):
    """Base error for source and planner boundary failures."""


class SchemaBundleSourceConflict(SchemaBundlePlannerError):
    """The requested Artifact identity or media evidence is not eligible for planning."""


@dataclass(frozen=True, slots=True)
class PlanSchemaDefinitionBundle:
    artifact_id: UUID
    expected_sha256: str

    def __post_init__(self) -> None:
        if self.artifact_id.int == 0:
            raise ValueError("artifact_id must be non-zero")
        if re.fullmatch(r"[0-9a-f]{64}", self.expected_sha256) is None:
            raise ValueError("expected_sha256 must be a lowercase SHA-256 digest")


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


def _require(context: SecurityContext, decision: AuthorizationDecision) -> None:
    if (
        decision.permission is not Permission.CATALOG_WRITE
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
    """Validate one exact immutable Artifact against one coherent read-only Catalog snapshot."""

    def __init__(
        self,
        *,
        artifacts: VerifiedArtifactReader,
        snapshots: SchemaBundleSnapshotRepository,
    ) -> None:
        self._artifacts = artifacts
        self._snapshots = snapshots

    async def plan(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: PlanSchemaDefinitionBundle,
    ) -> SchemaBundlePlan:
        _require(context, decision)
        record, raw_bytes = await self._artifacts.read_verified_bytes(
            context,
            decision,
            command.artifact_id,
            maximum_bytes=MAX_SCHEMA_DEFINITION_BUNDLE_BYTES,
        )
        artifact = record.artifact
        if artifact.id != command.artifact_id or artifact.sha256 != command.expected_sha256:
            raise SchemaBundleSourceConflict(
                "Artifact identity or digest differs from the exact planning request"
            )
        if (
            artifact.organization_id != context.organization_id
            or artifact.project_id != context.project_id
        ):
            raise SchemaBundleSourceConflict(
                "Artifact tenant scope differs from the request context"
            )
        if len(raw_bytes) != artifact.size_bytes:
            raise SchemaBundleSourceConflict(
                "Artifact byte count differs from its immutable manifest"
            )
        if not media_type_supported(artifact.media_type):
            raise SchemaBundleSourceConflict(
                "Artifact media type is not a supported JSON Schema Definition Bundle type"
            )
        snapshot = self._snapshots.read_snapshot(context=context, decision=decision)
        if (
            snapshot.organization_id != context.organization_id
            or snapshot.project_id != context.project_id
        ):
            raise SchemaBundleSourceConflict("Catalog snapshot tenant scope is inconsistent")
        return build_schema_bundle_plan(
            source=SourceArtifactIdentity(
                artifact.id,
                artifact.organization_id,
                artifact.project_id,
                artifact.classification,
                artifact.media_type,
                artifact.size_bytes,
                artifact.sha256,
            ),
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

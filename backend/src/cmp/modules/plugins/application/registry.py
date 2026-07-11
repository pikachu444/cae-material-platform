"""T-17 immutable plugin registry use cases and persistence port."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID, uuid4

from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
    Permission,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.plugins.domain.registry import (
    ArtifactReference,
    ImmutablePluginManifest,
    InvalidManifest,
    PackageAccessDenied,
    PackageRecord,
    PackageState,
    SchemaDocument,
    SchemaRole,
)
from cmp.shared.domain.revisions import content_sha256

_IDEMPOTENCY_KEY = re.compile(r"^[\x21-\x7e]{1,255}$")


class PluginContractValidator(Protocol):
    def validate_manifest(self, document: object) -> None: ...

    def validate_schema(self, document: object) -> None: ...


@dataclass(frozen=True, slots=True)
class RegisterSchema:
    schema_id: str
    extension_ordinal: int
    role: SchemaRole
    document: object
    sha256: str


@dataclass(frozen=True, slots=True)
class RegisterPackage:
    classification: DataClassification
    manifest: object
    package_artifact: ArtifactReference
    signature_artifact: ArtifactReference
    sbom_artifact: ArtifactReference
    schemas: tuple[RegisterSchema, ...]
    idempotency_key: str


@dataclass(frozen=True, slots=True)
class PackageRegistrationResult:
    package: PackageRecord
    replayed: bool


@dataclass(frozen=True, slots=True)
class ControlPackage:
    package_id: UUID
    reason: str


@dataclass(frozen=True, slots=True)
class ActivatePackage:
    package_id: UUID
    reason: str


class PluginRegistryRepository(Protocol):
    def register(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: RegisterPackage,
        definition_id: UUID,
        package_id: UUID,
        event_id: UUID,
        schema_ids: tuple[UUID, ...],
        manifest: ImmutablePluginManifest,
        schemas: tuple[SchemaDocument, ...],
        submission_digest: str,
        now: datetime,
    ) -> PackageRegistrationResult: ...

    def get(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        package_id: UUID,
    ) -> PackageRecord: ...

    def transition(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        package_id: UUID,
        target: PackageState,
        event_id: UUID,
        reason: str,
        now: datetime,
    ) -> PackageRecord: ...

    def activate(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: ActivatePackage,
        activation_id: UUID,
        now: datetime,
    ) -> PackageRecord: ...


def _require_decision(
    context: SecurityContext,
    decision: AuthorizationDecision,
    permission: Permission,
) -> None:
    if (
        decision.principal_id != context.principal.id
        or decision.organization_id != context.organization_id
        or decision.project_id != context.project_id
        or decision.request_id != context.request_id
        or decision.trace_id != context.trace_id
        or decision.permission is not permission
    ):
        raise ValueError("authorization decision does not match plugin command context")


def _nonzero(name: str, value: UUID) -> None:
    if value.int == 0:
        raise ValueError(f"{name} must be non-zero")


def _reason(value: str) -> None:
    if not value or value != value.strip() or len(value) > 2000 or "\x00" in value:
        raise ValueError("reason must be trimmed and contain 1..2000 characters")


class PluginRegistryService:
    def __init__(
        self,
        *,
        repository: PluginRegistryRepository,
        validator: PluginContractValidator,
        id_factory: Callable[[], UUID] = uuid4,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._validator = validator
        self._id_factory = id_factory
        self._clock = clock or (lambda: datetime.now(UTC))

    def _new_ids(self, count: int) -> tuple[UUID, ...]:
        values = tuple(self._id_factory() for _ in range(count))
        if any(value.int == 0 for value in values) or len(set(values)) != len(values):
            raise RuntimeError("plugin registry id_factory returned invalid identifiers")
        return values

    def register(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: RegisterPackage,
    ) -> PackageRegistrationResult:
        _require_decision(context, decision, Permission.PLUGIN_SUBMIT)
        if not decision.allows(
            context.organization_id,
            context.project_id,
            command.classification,
        ):
            raise PackageAccessDenied(
                "plugin package classification exceeds the authorized clearance"
            )
        if _IDEMPOTENCY_KEY.fullmatch(command.idempotency_key) is None:
            raise ValueError("idempotency_key must contain 1..255 visible ASCII characters")
        self._validator.validate_manifest(command.manifest)
        manifest = ImmutablePluginManifest.from_validated_document(command.manifest)
        if command.package_artifact.sha256 != manifest.package_digest:
            raise InvalidManifest(
                "package artifact digest must equal manifest package_digest"
            )
        if any(
            artifact.size_bytes <= 0
            for artifact in (
                command.package_artifact,
                command.signature_artifact,
                command.sbom_artifact,
            )
        ):
            raise InvalidManifest(
                "package, signature, and SBOM artifacts must be non-empty"
            )
        artifact_ids = {
            command.package_artifact.artifact_id,
            command.signature_artifact.artifact_id,
            command.sbom_artifact.artifact_id,
        }
        if len(artifact_ids) != 3:
            raise InvalidManifest("package, signature, and SBOM artifacts must be distinct")
        if not command.schemas:
            raise InvalidManifest("package registration requires extension schemas")
        schemas: list[SchemaDocument] = []
        for registered in command.schemas:
            self._validator.validate_schema(registered.document)
            schemas.append(
                SchemaDocument.from_validated_document(
                    schema_id=registered.schema_id,
                    extension_ordinal=registered.extension_ordinal,
                    role=registered.role,
                    document=registered.document,
                    expected_sha256=registered.sha256,
                )
            )
        schema_values = tuple(
            sorted(schemas, key=lambda item: (item.extension_ordinal, item.schema_id))
        )
        if len({item.schema_id for item in schema_values}) != len(schema_values):
            raise InvalidManifest("registered schema IDs must be unique per package")
        expected_ordinals = {item.ordinal for item in manifest.extensions}
        actual_ordinals = {item.extension_ordinal for item in schema_values}
        if actual_ordinals != expected_ordinals:
            raise InvalidManifest("every extension requires at least one registered schema")
        submission_digest = content_sha256(
            {
                "classification": command.classification.value,
                "manifest_digest": manifest.manifest_digest,
                "package_artifact": {
                    "id": str(command.package_artifact.artifact_id),
                    "sha256": command.package_artifact.sha256,
                    "size_bytes": command.package_artifact.size_bytes,
                    "media_type": command.package_artifact.media_type,
                },
                "signature_artifact": {
                    "id": str(command.signature_artifact.artifact_id),
                    "sha256": command.signature_artifact.sha256,
                    "size_bytes": command.signature_artifact.size_bytes,
                    "media_type": command.signature_artifact.media_type,
                },
                "sbom_artifact": {
                    "id": str(command.sbom_artifact.artifact_id),
                    "sha256": command.sbom_artifact.sha256,
                    "size_bytes": command.sbom_artifact.size_bytes,
                    "media_type": command.sbom_artifact.media_type,
                },
                "schemas": [
                    {
                        "schema_id": item.schema_id,
                        "extension_ordinal": item.extension_ordinal,
                        "role": item.role.value,
                        "sha256": item.sha256,
                    }
                    for item in schema_values
                ],
            }
        )
        generated_ids = self._new_ids(3 + len(schema_values))
        definition_id, package_id, event_id = generated_ids[:3]
        return self._repository.register(
            context=context,
            decision=decision,
            command=command,
            definition_id=definition_id,
            package_id=package_id,
            event_id=event_id,
            schema_ids=generated_ids[3:],
            manifest=manifest,
            schemas=schema_values,
            submission_digest=submission_digest,
            now=self._clock(),
        )

    def get(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        package_id: UUID,
    ) -> PackageRecord:
        _require_decision(context, decision, Permission.PLUGIN_READ)
        _nonzero("package_id", package_id)
        return self._repository.get(
            context=context, decision=decision, package_id=package_id
        )

    def verify(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: ControlPackage,
    ) -> PackageRecord:
        return self._transition(
            context, decision, command, PackageState.ELIGIBLE
        )

    def revoke(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: ControlPackage,
    ) -> PackageRecord:
        return self._transition(context, decision, command, PackageState.REVOKED)

    def _transition(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: ControlPackage,
        target: PackageState,
    ) -> PackageRecord:
        _require_decision(context, decision, Permission.PLUGIN_ACTIVATE)
        _nonzero("package_id", command.package_id)
        _reason(command.reason)
        return self._repository.transition(
            context=context,
            decision=decision,
            package_id=command.package_id,
            target=target,
            event_id=self._new_ids(1)[0],
            reason=command.reason,
            now=self._clock(),
        )

    def activate(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: ActivatePackage,
    ) -> PackageRecord:
        _require_decision(context, decision, Permission.PLUGIN_ACTIVATE)
        _nonzero("package_id", command.package_id)
        _reason(command.reason)
        return self._repository.activate(
            context=context,
            decision=decision,
            command=command,
            activation_id=self._new_ids(1)[0],
            now=self._clock(),
        )

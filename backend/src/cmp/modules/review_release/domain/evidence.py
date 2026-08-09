"""Closed, typed evidence contract for Issue #160 review subjects.

The resolver registry is intentionally small and adapter-extensible.  Resolvers own tenant,
current-head, schema and digest checks; clients submit only a registered subject identity and
change reason.  The resulting snapshot is immutable review evidence, not a generic EAV payload.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol, cast
from uuid import UUID

from cmp.modules.identity_access.domain.authorization import DataClassification

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
REGISTERED_REVIEW_SUBJECT_TYPES = (
    "catalog.material",
    "catalog.configurable_record",
    "datasets.test_data_document",
    "modeling.material_model",
    "exporting.solver_card",
    "exporting.neutral_solver_card",
)
# ``validation.result`` predates the closed Issue #160 subject registry.  It is
# retained as an explicit legacy resolver target so existing review requests can
# still be read and decided while new requests use the typed evidence snapshot.
LEGACY_REVIEW_SUBJECT_TYPES = ("validation.result",)
REGISTERED_REVIEW_RESOLVER_TYPES = REGISTERED_REVIEW_SUBJECT_TYPES + LEGACY_REVIEW_SUBJECT_TYPES


class EvidenceValidationStatus(StrEnum):
    VALID = "valid"
    WARNING = "warning"
    BLOCKED = "blocked"


class SourceArtifactState(StrEnum):
    ATTACHED = "attached"
    UNATTACHED = "unattached"


class ReviewEvidenceError(Exception):
    """Subject cannot be resolved as authoritative immutable review evidence."""


@dataclass(frozen=True, slots=True)
class ReviewSubjectEvidence:
    subject_type: str
    subject_id: UUID
    subject_revision_id: UUID
    label: str
    classification: DataClassification
    schema_ref: str
    schema_version: str
    server_manifest_sha256: str
    source_artifact_state: SourceArtifactState
    source_artifact_id: UUID | None
    source_artifact_sha256: str | None
    validation_status: EvidenceValidationStatus
    validation_summary: str
    created_by: UUID
    created_at: datetime
    change_reason: str
    exact_input_use: tuple[str, ...]
    affected_record_id: UUID | None
    affected_record_revision_id: UUID | None
    affected_path: str | None = None
    affected_table_id: UUID | None = None
    affected_table_revision_id: UUID | None = None
    output_artifact_sha256: str | None = None
    neutral_material_id: UUID | None = None
    neutral_material_revision_id: UUID | None = None
    neutral_artifact_sha256: str | None = None

    def __post_init__(self) -> None:
        if self.subject_type not in REGISTERED_REVIEW_SUBJECT_TYPES:
            raise ReviewEvidenceError("subject_type is not registered for review")
        for name, value in (
            ("subject_id", self.subject_id),
            ("subject_revision_id", self.subject_revision_id),
            ("created_by", self.created_by),
            ("neutral_material_id", self.neutral_material_id),
            ("neutral_material_revision_id", self.neutral_material_revision_id),
            ("affected_table_id", self.affected_table_id),
            ("affected_table_revision_id", self.affected_table_revision_id),
        ):
            if value is not None and value.int == 0:
                raise ReviewEvidenceError(f"{name} must be a non-zero UUID")
        if not self.label or self.label != self.label.strip() or len(self.label) > 255:
            raise ReviewEvidenceError("label must be trimmed and contain 1..255 characters")
        if not self.schema_ref or not self.schema_version or not self.validation_summary:
            raise ReviewEvidenceError("schema and validation evidence are required")
        if not _SHA256.fullmatch(self.server_manifest_sha256):
            raise ReviewEvidenceError("server_manifest_sha256 must be lowercase SHA-256")
        if self.source_artifact_state is SourceArtifactState.ATTACHED:
            if self.source_artifact_id is None or self.source_artifact_sha256 is None:
                raise ReviewEvidenceError(
                    "attached source artifacts require exact identity and digest"
                )
        elif self.source_artifact_id is not None or self.source_artifact_sha256 is not None:
            raise ReviewEvidenceError("unattached source artifacts must be explicitly null")
        if self.source_artifact_sha256 is not None and not _SHA256.fullmatch(
            self.source_artifact_sha256
        ):
            raise ReviewEvidenceError("source_artifact_sha256 must be lowercase SHA-256")
        if self.neutral_artifact_sha256 is not None and not _SHA256.fullmatch(
            self.neutral_artifact_sha256
        ):
            raise ReviewEvidenceError("neutral_artifact_sha256 must be lowercase SHA-256")
        if self.output_artifact_sha256 is not None and not _SHA256.fullmatch(
            self.output_artifact_sha256
        ):
            raise ReviewEvidenceError("output_artifact_sha256 must be lowercase SHA-256")
        neutral_parts = (
            self.neutral_material_id,
            self.neutral_material_revision_id,
            self.neutral_artifact_sha256,
        )
        if any(part is not None for part in neutral_parts) and not all(
            part is not None for part in neutral_parts
        ):
            raise ReviewEvidenceError(
                "Neutral identity, revision, and artifact digest must be provided together"
            )
        if self.created_at.tzinfo is None or self.created_at.utcoffset() is None:
            raise ReviewEvidenceError("created_at must be timezone-aware")
        if (
            not self.change_reason
            or self.change_reason != self.change_reason.strip()
            or len(self.change_reason) > 2000
        ):
            raise ReviewEvidenceError(
                "change_reason must be trimmed and contain 1..2000 characters"
            )
        if not self.exact_input_use or any(
            not item or item != item.strip() for item in self.exact_input_use
        ):
            raise ReviewEvidenceError("exact_input_use must contain at least one trimmed path")
        if (self.affected_record_id is None) != (self.affected_record_revision_id is None):
            raise ReviewEvidenceError("affected Record identity and revision must be paired")
        if (self.affected_table_id is None) != (self.affected_table_revision_id is None):
            raise ReviewEvidenceError("affected Record table identity and revision must be paired")
        if self.affected_record_id is not None and self.affected_table_id is None:
            raise ReviewEvidenceError("affected Record identity requires exact table pins")

    def to_document(self) -> dict[str, object]:
        return {
            "subject_type": self.subject_type,
            "subject_id": str(self.subject_id),
            "subject_revision_id": str(self.subject_revision_id),
            "label": self.label,
            "classification": self.classification.value,
            "schema": {"ref": self.schema_ref, "version": self.schema_version},
            "server_manifest": {"sha256": self.server_manifest_sha256},
            "source_artifact": {
                "state": self.source_artifact_state.value,
                "id": str(self.source_artifact_id) if self.source_artifact_id else None,
                "sha256": self.source_artifact_sha256,
            },
            "validation": {
                "status": self.validation_status.value,
                "summary": self.validation_summary,
            },
            "created": {"by": str(self.created_by), "at": self.created_at.isoformat()},
            "change_reason": self.change_reason,
            "exact_input_use": list(self.exact_input_use),
            "affected_materials": {
                "record_id": str(self.affected_record_id) if self.affected_record_id else None,
                "record_revision_id": str(self.affected_record_revision_id)
                if self.affected_record_revision_id
                else None,
                "path": self.affected_path,
            },
            "affected_table_id": str(self.affected_table_id) if self.affected_table_id else None,
            "affected_table_revision_id": (
                str(self.affected_table_revision_id) if self.affected_table_revision_id else None
            ),
            "output_artifact_sha256": self.output_artifact_sha256,
            "neutral": {
                "material_id": str(self.neutral_material_id) if self.neutral_material_id else None,
                "material_revision_id": str(self.neutral_material_revision_id)
                if self.neutral_material_revision_id
                else None,
                "artifact_sha256": self.neutral_artifact_sha256,
            },
        }

    @classmethod
    def from_document(cls, value: object) -> ReviewSubjectEvidence:
        if not isinstance(value, dict):
            raise ReviewEvidenceError("subject evidence snapshot must be an object")
        snapshot = cast(dict[str, object], value)

        def _mapping(raw: object) -> dict[str, object]:
            if not isinstance(raw, dict):
                raise ReviewEvidenceError("subject evidence snapshot is incomplete")
            return cast(dict[str, object], raw)

        source = _mapping(snapshot.get("source_artifact"))
        validation = _mapping(snapshot.get("validation"))
        created = _mapping(snapshot.get("created"))
        affected = _mapping(snapshot.get("affected_materials"))
        neutral = _mapping(snapshot.get("neutral"))
        schema = _mapping(snapshot.get("schema"))
        raw_input_use = snapshot.get("exact_input_use", ())
        if not isinstance(raw_input_use, (list, tuple)):
            raise ReviewEvidenceError("subject evidence exact_input_use is invalid")

        def _uuid_or_none(raw: object) -> UUID | None:
            if raw is None:
                return None
            try:
                return UUID(str(raw))
            except ValueError as error:
                raise ReviewEvidenceError("subject evidence contains an invalid UUID") from error

        return cls(
            subject_type=str(snapshot.get("subject_type", "")),
            subject_id=UUID(str(snapshot["subject_id"])),
            subject_revision_id=UUID(str(snapshot["subject_revision_id"])),
            label=str(snapshot.get("label", "")),
            classification=DataClassification(str(snapshot.get("classification", ""))),
            schema_ref=str(schema.get("ref", "")),
            schema_version=str(schema.get("version", "")),
            server_manifest_sha256=str(
                _mapping(snapshot.get("server_manifest", {})).get("sha256", "")
            ),
            source_artifact_state=SourceArtifactState(str(source.get("state", ""))),
            source_artifact_id=_uuid_or_none(source.get("id")),
            source_artifact_sha256=(
                str(source["sha256"]) if source.get("sha256") is not None else None
            ),
            validation_status=EvidenceValidationStatus(str(validation.get("status", ""))),
            validation_summary=str(validation.get("summary", "")),
            created_by=UUID(str(created["by"])),
            created_at=datetime.fromisoformat(str(created["at"])),
            change_reason=str(snapshot.get("change_reason", "")),
            exact_input_use=tuple(str(item) for item in raw_input_use),
            affected_record_id=_uuid_or_none(affected.get("record_id")),
            affected_record_revision_id=_uuid_or_none(affected.get("record_revision_id")),
            affected_path=(str(affected["path"]) if affected.get("path") is not None else None),
            affected_table_id=_uuid_or_none(snapshot.get("affected_table_id")),
            affected_table_revision_id=_uuid_or_none(snapshot.get("affected_table_revision_id")),
            output_artifact_sha256=(
                str(snapshot["output_artifact_sha256"])
                if snapshot.get("output_artifact_sha256") is not None
                else None
            ),
            neutral_material_id=_uuid_or_none(neutral.get("material_id")),
            neutral_material_revision_id=_uuid_or_none(neutral.get("material_revision_id")),
            neutral_artifact_sha256=(
                str(neutral["artifact_sha256"])
                if neutral.get("artifact_sha256") is not None
                else None
            ),
        )


class ReviewSubjectEvidenceResolver(Protocol):
    subject_type: str


class LegacyReviewSubjectResolver:
    """Compatibility resolver for review targets with client-supplied legacy hints.

    Legacy validation results do not have the Issue #160 closed evidence shape.  They
    therefore remain nullable evidence records, but still require the old explicit
    classification and manifest hints instead of silently fabricating a snapshot.
    """

    subject_type = "validation.result"

    def resolve(
        self,
        *,
        organization_id: UUID,
        project_id: UUID,
        subject_id: UUID,
        subject_revision_id: UUID,
        expected_manifest_sha256: str | None,
        expected_classification: DataClassification | None,
        requested_by: UUID,
        reason: str,
        occurred_at: datetime,
    ) -> None:
        del organization_id, project_id, subject_id, subject_revision_id
        del requested_by, reason, occurred_at
        if expected_manifest_sha256 is None or expected_classification is None:
            raise ReviewEvidenceError(
                "legacy validation.result requests require classification and manifest hints"
            )
        if not _SHA256.fullmatch(expected_manifest_sha256):
            raise ReviewEvidenceError("legacy validation.result manifest is not a SHA-256 digest")
        return None


class ReviewSubjectEvidenceRegistry:
    def __init__(self, resolvers: tuple[ReviewSubjectEvidenceResolver, ...] = ()) -> None:
        self._resolvers = {resolver.subject_type: resolver for resolver in resolvers}

    def register(self, resolver: ReviewSubjectEvidenceResolver) -> None:
        if resolver.subject_type not in REGISTERED_REVIEW_RESOLVER_TYPES:
            raise ReviewEvidenceError("resolver subject_type is not registered")
        self._resolvers[resolver.subject_type] = resolver

    def resolve(self, **kwargs: object) -> ReviewSubjectEvidence | None:
        subject_type = kwargs.pop("subject_type", None)
        if not isinstance(subject_type, str):
            raise ReviewEvidenceError("review subject_type is required")
        resolver = self._resolvers.get(subject_type)
        if resolver is None:
            raise ReviewEvidenceError("no resolver is registered for the review subject")
        context = kwargs.pop("_context", None)
        authorization_decision = kwargs.pop("_authorization_decision", None)
        scoped_resolve = getattr(resolver, "resolve_scoped", None)
        if callable(scoped_resolve):
            return cast(
                ReviewSubjectEvidence | None,
                scoped_resolve(
                context=context,
                authorization_decision=authorization_decision,
                **kwargs,
                ),
            )
        legacy_resolve = getattr(resolver, "resolve", None)
        if not callable(legacy_resolve):
            raise ReviewEvidenceError("registered resolver cannot resolve this review subject")
        return cast(ReviewSubjectEvidence | None, legacy_resolve(**kwargs))

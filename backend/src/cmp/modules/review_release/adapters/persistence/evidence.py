"""RLS-bound current-revision resolvers for the Issue #160 evidence registry."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.review_release.domain.evidence import (
    EvidenceValidationStatus,
    ReviewEvidenceError,
    ReviewSubjectEvidence,
    SourceArtifactState,
)


class RlsContext(Protocol):
    """Structural protocol kept local to avoid importing an adapter implementation."""

    def bind_authorization(
        self,
        session: Session,
        context: SecurityContext,
        decision: AuthorizationDecision,
    ) -> None: ...


_metadata = sa.MetaData()
def _base_revision_columns() -> tuple[sa.Column[Any], ...]:
    return (
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("aggregate_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("classification", sa.String(64), nullable=False),
        sa.Column("revision_no", sa.BigInteger(), nullable=False),
        sa.Column("schema_id", sa.String(255), nullable=False),
        sa.Column("schema_version", sa.String(64), nullable=False),
        sa.Column("content_hash", sa.CHAR(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("change_reason", sa.Text(), nullable=False),
    )


def _identity(schema: str, name: str) -> sa.Table:
    return sa.Table(
        name,
        _metadata,
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("classification", sa.String(64), nullable=False),
        sa.Column("current_revision_id", sa.Uuid(), nullable=False),
        schema=schema,
    )


def _revision(schema: str, name: str, *extra: sa.Column[Any]) -> sa.Table:
    return sa.Table(name, _metadata, *_base_revision_columns(), *extra, schema=schema)


_SUBJECTS: dict[str, tuple[sa.Table, sa.Table, tuple[str, ...]]] = {
    "catalog.material": (
        _identity("catalog", "material"),
        _revision(
            "catalog",
            "material_revision",
            sa.Column("name", sa.String(200)),
            sa.Column("material_code", sa.String(100)),
        ),
        ("name", "material_code"),
    ),
    "catalog.configurable_record": (
        _identity("catalog", "catalog_record"),
        _revision(
            "catalog",
            "catalog_record_revision",
            sa.Column("table_id", sa.Uuid()),
            sa.Column("table_revision_id", sa.Uuid()),
            sa.Column("name", sa.String(200)),
            sa.Column("external_key", sa.String(255)),
        ),
        ("name", "external_key"),
    ),
    "datasets.test_data_document": (
        _identity("datasets", "test_data_document"),
        _revision(
            "datasets",
            "test_data_document_revision",
            sa.Column("document_key", sa.String(200)),
            sa.Column("source_file_name", sa.String(255)),
            sa.Column("canonical_artifact_id", sa.Uuid()),
            sa.Column("canonical_sha256", sa.CHAR(64)),
        ),
        ("document_key", "source_file_name"),
    ),
    "modeling.material_model": (
        _identity("modeling", "material_model"),
        _revision(
            "modeling",
            "material_model_revision",
            sa.Column("model_family_id", sa.String(255)),
            sa.Column("material_id", sa.Uuid()),
            sa.Column("material_revision_id", sa.Uuid()),
            sa.Column("processing_output_id", sa.Uuid()),
            sa.Column("processing_output_revision_id", sa.Uuid()),
        ),
        ("model_family_id",),
    ),
    "exporting.solver_card": (
        _identity("exporting", "solver_card"),
        _revision(
            "exporting",
            "solver_card_revision",
            sa.Column("card_title", sa.String(100)),
            sa.Column("card_sha256", sa.CHAR(64)),
            sa.Column("material_model_id", sa.Uuid()),
            sa.Column("material_model_revision_id", sa.Uuid()),
        ),
        ("card_title",),
    ),
    "exporting.neutral_solver_card": (
        _identity("exporting", "neutral_solver_card"),
        _revision(
            "exporting",
            "neutral_solver_card_revision",
            sa.Column("material_name", sa.String(80)),
            sa.Column("card_sha256", sa.CHAR(64)),
            sa.Column("neutral_material_id", sa.Uuid()),
            sa.Column("neutral_material_revision_id", sa.Uuid()),
        ),
        ("material_name",),
    ),
}

_binding = sa.Table(
    "domain_record_binding",
    _metadata,
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("record_id", sa.Uuid(), nullable=False),
    sa.Column("record_revision_id", sa.Uuid(), nullable=False),
    sa.Column("domain_kind", sa.String(64), nullable=False),
    sa.Column("domain_object_id", sa.Uuid(), nullable=False),
    sa.Column("domain_revision_id", sa.Uuid(), nullable=False),
    schema="catalog",
)

_record = _SUBJECTS["catalog.configurable_record"][0]
_record_revision = _SUBJECTS["catalog.configurable_record"][1]

_neutral_identity = _identity("modeling", "neutral_material")
_neutral_revision = _revision(
    "modeling",
    "neutral_material_revision",
    sa.Column("validation_status", sa.String(160)),
    sa.Column("document_artifact_id", sa.Uuid()),
    sa.Column("document_artifact_sha256", sa.CHAR(64)),
    sa.Column("processing_output_id", sa.Uuid()),
    sa.Column("processing_output_revision_id", sa.Uuid()),
    sa.Column("prony_overlay_model_id", sa.Uuid()),
    sa.Column("prony_overlay_model_revision_id", sa.Uuid()),
)


def _label(row: Any, columns: tuple[str, ...], subject_id: UUID) -> str:
    for column in columns:
        value = row.get(column)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return f"{subject_id} exact revision"


class SqlAlchemyReviewSubjectResolver:
    """Resolve one registered subject from its immutable current revision."""

    def __init__(
        self,
        *,
        subject_type: str,
        session_factory: sessionmaker[Session],
        rls_context: RlsContext,
    ) -> None:
        if subject_type not in _SUBJECTS:
            raise ValueError("subject_type is not a current Issue #160 subject")
        self.subject_type = subject_type
        self._sessions = session_factory
        self._rls = rls_context

    def resolve_scoped(
        self,
        *,
        context: SecurityContext | None,
        authorization_decision: AuthorizationDecision | None,
        organization_id: UUID,
        project_id: UUID,
        subject_id: UUID,
        subject_revision_id: UUID,
        expected_manifest_sha256: str | None,
        expected_classification: DataClassification | None,
        requested_by: UUID,
        reason: str,
        occurred_at: datetime,
    ) -> ReviewSubjectEvidence:
        if context is None or authorization_decision is None:
            raise ReviewEvidenceError("review evidence resolution requires authorization scope")
        if context.organization_id != organization_id or context.project_id != project_id:
            raise ReviewEvidenceError("review evidence scope does not match the request tenant")
        identity, revision, label_columns = _SUBJECTS[self.subject_type]
        with self._sessions() as session, session.begin():
            self._rls.bind_authorization(session, context, authorization_decision)
            identity_row = session.execute(
                sa.select(identity).where(
                    identity.c.organization_id == organization_id,
                    identity.c.project_id == project_id,
                    identity.c.id == subject_id,
                )
            ).mappings().one_or_none()
            if identity_row is None:
                raise ReviewEvidenceError("review subject is not visible in this tenant")
            if identity_row["current_revision_id"] != subject_revision_id:
                raise ReviewEvidenceError("review subject revision is not current")
            row = session.execute(
                sa.select(revision).where(
                    revision.c.organization_id == organization_id,
                    revision.c.project_id == project_id,
                    revision.c.aggregate_id == subject_id,
                    revision.c.id == subject_revision_id,
                )
            ).mappings().one_or_none()
            if row is None:
                raise ReviewEvidenceError("review subject revision is not visible")
            classification = DataClassification(str(row["classification"]))
            if (
                expected_classification is not None
                and expected_classification is not classification
            ):
                raise ReviewEvidenceError("review classification hint does not match the subject")
            manifest = str(row["content_hash"])
            if expected_manifest_sha256 is not None and expected_manifest_sha256 != manifest:
                raise ReviewEvidenceError("review manifest hint does not match the subject")

            source_id = row.get("canonical_artifact_id") or None
            source_sha = row.get("canonical_sha256") or None
            card_sha = row.get("card_sha256") or None
            if source_id is None and card_sha is not None:
                source_sha = card_sha
            source_state = (
                SourceArtifactState.ATTACHED
                if source_id is not None and source_sha is not None
                else SourceArtifactState.UNATTACHED
            )
            if source_state is SourceArtifactState.UNATTACHED:
                source_id = None
                source_sha = None

            neutral_material_id: UUID | None = None
            neutral_material_revision_id: UUID | None = None
            neutral_artifact_sha256: str | None = None
            if self.subject_type == "modeling.material_model":
                processing_id = row.get("processing_output_id")
                processing_revision_id = row.get("processing_output_revision_id")
                neutral_matches: list[sa.ColumnElement[bool]] = [
                    sa.and_(
                        _neutral_revision.c.prony_overlay_model_id == subject_id,
                        _neutral_revision.c.prony_overlay_model_revision_id
                        == subject_revision_id,
                    )
                ]
                if processing_id is not None and processing_revision_id is not None:
                    neutral_matches.append(
                        sa.and_(
                            _neutral_revision.c.processing_output_id == processing_id,
                            _neutral_revision.c.processing_output_revision_id
                            == processing_revision_id,
                        )
                    )
                neutral_row = session.execute(
                    sa.select(_neutral_revision)
                    .join(
                        _neutral_identity,
                        sa.and_(
                            _neutral_identity.c.organization_id
                            == _neutral_revision.c.organization_id,
                            _neutral_identity.c.project_id == _neutral_revision.c.project_id,
                            _neutral_identity.c.id == _neutral_revision.c.aggregate_id,
                            _neutral_identity.c.current_revision_id == _neutral_revision.c.id,
                        ),
                    )
                    .where(
                        _neutral_revision.c.organization_id == organization_id,
                        _neutral_revision.c.project_id == project_id,
                        _neutral_revision.c.classification == classification.value,
                        sa.or_(*neutral_matches),
                    )
                ).mappings().first()
                if neutral_row is None:
                    raise ReviewEvidenceError(
                        "material model review requires an exact current Neutral revision pin"
                    )
                neutral_material_id = neutral_row["aggregate_id"]
                neutral_material_revision_id = neutral_row["id"]
                neutral_artifact_sha256 = str(neutral_row["document_artifact_sha256"])
            elif self.subject_type == "exporting.neutral_solver_card":
                neutral_material_id = row.get("neutral_material_id")
                neutral_material_revision_id = row.get("neutral_material_revision_id")
                if neutral_material_id is None or neutral_material_revision_id is None:
                    raise ReviewEvidenceError(
                        "Neutral Solver Card review requires an exact Neutral revision pin"
                    )
                neutral_row = session.execute(
                    sa.select(
                        _neutral_revision.c.id,
                        _neutral_revision.c.aggregate_id,
                        _neutral_revision.c.document_artifact_sha256,
                    )
                    .join(
                        _neutral_identity,
                        sa.and_(
                            _neutral_identity.c.organization_id
                            == _neutral_revision.c.organization_id,
                            _neutral_identity.c.project_id == _neutral_revision.c.project_id,
                            _neutral_identity.c.id == _neutral_revision.c.aggregate_id,
                            _neutral_identity.c.current_revision_id == _neutral_revision.c.id,
                        ),
                    )
                    .where(
                        _neutral_revision.c.organization_id == organization_id,
                        _neutral_revision.c.project_id == project_id,
                        _neutral_revision.c.aggregate_id == neutral_material_id,
                        _neutral_revision.c.id == neutral_material_revision_id,
                    )
                ).mappings().first()
                if neutral_row is None:
                    raise ReviewEvidenceError(
                        "Neutral Solver Card review requires a current exact Neutral revision"
                    )
                neutral_artifact_sha256 = str(neutral_row["document_artifact_sha256"])

            affected_record_id: UUID | None = None
            affected_record_revision_id: UUID | None = None
            if self.subject_type == "catalog.configurable_record":
                affected_record_id = subject_id
                affected_record_revision_id = subject_revision_id
            else:
                domain_kind = self.subject_type.rsplit(".", 1)[-1]
                domain_kind = {
                    "test_data_document": "test_data",
                    "material_model": "material_model",
                    "solver_card": "solver_card",
                    "neutral_solver_card": "neutral_solver_card",
                }.get(domain_kind, domain_kind)
                binding_row = session.execute(
                    sa.select(_binding.c.record_id, _binding.c.record_revision_id).where(
                        _binding.c.organization_id == organization_id,
                        _binding.c.project_id == project_id,
                        _binding.c.classification == classification.value,
                        _binding.c.domain_kind == domain_kind,
                        _binding.c.domain_object_id == subject_id,
                        _binding.c.domain_revision_id == subject_revision_id,
                    )
                ).mappings().first()
                if binding_row is not None:
                    record_row = session.execute(
                        sa.select(_record.c.current_revision_id).where(
                            _record.c.organization_id == organization_id,
                            _record.c.project_id == project_id,
                            _record.c.id == binding_row["record_id"],
                        )
                    ).first()
                    if (
                        record_row is not None
                        and record_row[0] == binding_row["record_revision_id"]
                    ):
                        affected_record_id = binding_row["record_id"]
                        affected_record_revision_id = binding_row["record_revision_id"]
                if affected_record_id is None or affected_record_revision_id is None:
                    raise ReviewEvidenceError(
                        "review subject must have a current exact Materials Record binding"
                    )

            affected_table_id: UUID | None = None
            affected_table_revision_id: UUID | None = None
            if affected_record_id is not None and affected_record_revision_id is not None:
                record_revision_row = session.execute(
                    sa.select(
                        _record_revision.c.table_id,
                        _record_revision.c.table_revision_id,
                    ).where(
                        _record_revision.c.organization_id == organization_id,
                        _record_revision.c.project_id == project_id,
                        _record_revision.c.aggregate_id == affected_record_id,
                        _record_revision.c.id == affected_record_revision_id,
                    )
                ).mappings().one_or_none()
                if record_revision_row is None:
                    raise ReviewEvidenceError(
                        "review subject must have an exact Materials Record table pin"
                    )
                affected_table_id = record_revision_row["table_id"]
                affected_table_revision_id = record_revision_row["table_revision_id"]

            affected_material_id: UUID | None = None
            affected_material_revision_id: UUID | None = None
            if affected_record_id is not None and affected_record_revision_id is not None:
                material_binding = session.execute(
                    sa.select(_binding.c.domain_object_id, _binding.c.domain_revision_id).where(
                        _binding.c.organization_id == organization_id,
                        _binding.c.project_id == project_id,
                        _binding.c.classification == classification.value,
                        _binding.c.record_id == affected_record_id,
                        _binding.c.record_revision_id == affected_record_revision_id,
                        _binding.c.domain_kind == "material",
                    )
                ).mappings().first()
                if material_binding is not None:
                    affected_material_id = material_binding["domain_object_id"]
                    affected_material_revision_id = material_binding["domain_revision_id"]

        raw_validation_status = row.get("validation_status")
        validation_status = {
            "valid": EvidenceValidationStatus.VALID,
            "passed": EvidenceValidationStatus.VALID,
            "approved": EvidenceValidationStatus.VALID,
            "blocked": EvidenceValidationStatus.BLOCKED,
            "failed": EvidenceValidationStatus.BLOCKED,
        }.get(str(raw_validation_status).lower(), EvidenceValidationStatus.WARNING)
        validation_summary = (
            f"Server validation status: {raw_validation_status}. Current revision identity, "
            "schema and digest were verified."
            if raw_validation_status
            else "Current revision identity, schema and digest were verified; "
            "subject validation evidence is not exposed by this adapter."
        )
        return ReviewSubjectEvidence(
            subject_type=self.subject_type,
            subject_id=subject_id,
            subject_revision_id=subject_revision_id,
            label=_label(row, label_columns, subject_id),
            classification=classification,
            schema_ref=str(row["schema_id"]),
            schema_version=str(row["schema_version"]),
            server_manifest_sha256=manifest,
            source_artifact_state=source_state,
            source_artifact_id=source_id,
            source_artifact_sha256=source_sha,
            validation_status=validation_status,
            validation_summary=validation_summary,
            created_by=UUID(str(row["created_by"])),
            created_at=row["created_at"],
            change_reason=str(row["change_reason"]),
            exact_input_use=tuple(
                [f"{self.subject_type}:{subject_id}:{subject_revision_id}"]
                + ([f"artifact:{source_id}:{source_sha}"] if source_id and source_sha else [])
                + (
                    [f"output-artifact:{self.subject_type}:{subject_id}:{subject_revision_id}:{card_sha}"]
                    if card_sha
                    else []
                )
                + (
                    [
                        f"neutral:{neutral_material_id}:{neutral_material_revision_id}:{neutral_artifact_sha256}"
                    ]
                    if (
                        neutral_material_id
                        and neutral_material_revision_id
                        and neutral_artifact_sha256
                    )
                    else []
                )
            ),
            affected_record_id=affected_record_id,
            affected_record_revision_id=affected_record_revision_id,
            affected_path=(
                f"/materials/{affected_material_id}?record_id={affected_record_id}"
                f"&record_revision_id={affected_record_revision_id}"
                f"&material_revision_id={affected_material_revision_id}"
                if (
                    affected_record_id is not None
                    and affected_record_revision_id is not None
                    and affected_material_id is not None
                    and affected_material_revision_id is not None
                )
                else None
            ),
            affected_table_id=affected_table_id,
            affected_table_revision_id=affected_table_revision_id,
            output_artifact_sha256=(
                str(card_sha) if card_sha is not None else None
            ),
            neutral_material_id=neutral_material_id,
            neutral_material_revision_id=neutral_material_revision_id,
            neutral_artifact_sha256=neutral_artifact_sha256,
        )

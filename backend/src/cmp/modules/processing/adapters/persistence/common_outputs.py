"""PostgreSQL adapter for immutable common Processing Output evidence (T-53)."""

from __future__ import annotations

from collections.abc import Sequence
from contextlib import contextmanager
from typing import Any, Protocol, cast
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from cmp.modules.identity_access.domain.authorization import AuthorizationDecision
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.processing.application.common_outputs import (
    PROCESSING_OUTPUT_AGGREGATE_TYPE,
    ExactRevisionPin,
    ProcessingOutputContent,
    ProcessingOutputNotFound,
    ProcessingOutputRepository,
    ProcessingOutputSnapshot,
    processing_output_content_canonical,
)
from cmp.modules.processing.domain.common_pipeline import ProcessingStep
from cmp.shared.adapters.persistence.revisions import (
    SqlAlchemyRevisionStore,
    SqlRevisionHook,
    TypedRevisionTables,
)
from cmp.shared.application.revisions import RevisionStore
from cmp.shared.domain.revisions import RevisionDraft, RevisionRecord, TenantScope, content_sha256


class RlsContext(Protocol):
    def bind_authorization(
        self, session: Session, context: SecurityContext, decision: AuthorizationDecision
    ) -> None: ...


metadata = sa.MetaData()
output_table = sa.Table(
    "common_processing_output",
    metadata,
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("label", sa.String(200), nullable=False),
    sa.Column("current_revision_id", sa.Uuid(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("created_by", sa.Uuid(), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    schema="processing",
)
revision_table = sa.Table(
    "common_processing_output_revision",
    metadata,
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("aggregate_id", sa.Uuid(), nullable=False),
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("revision_no", sa.BigInteger(), nullable=False),
    sa.Column("based_on_revision_id", sa.Uuid(), nullable=True),
    sa.Column("schema_id", sa.String(255), nullable=False),
    sa.Column("schema_version", sa.String(64), nullable=False),
    sa.Column("content_hash", sa.CHAR(64), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("created_by", sa.Uuid(), nullable=False),
    sa.Column("change_reason", sa.Text(), nullable=False),
    sa.Column("request_id", sa.Uuid(), nullable=False),
    sa.Column("trace_id", sa.String(255), nullable=False),
    sa.Column("label", sa.String(200), nullable=False),
    sa.Column("source_document_id", sa.Uuid(), nullable=False),
    sa.Column("source_document_revision_id", sa.Uuid(), nullable=False),
    sa.Column("source_document_sha256", sa.CHAR(64), nullable=False),
    sa.Column("source_canonical_artifact_sha256", sa.CHAR(64), nullable=False),
    sa.Column("mapping_profile_id", sa.Uuid(), nullable=False),
    sa.Column("mapping_profile_revision_id", sa.Uuid(), nullable=False),
    sa.Column("mapping_profile_sha256", sa.CHAR(64), nullable=False),
    sa.Column("independent_quantity", sa.String(160), nullable=False),
    sa.Column("step_count", sa.Integer(), nullable=False),
    sa.Column("stage_count", sa.Integer(), nullable=False),
    sa.Column("final_point_count", sa.Integer(), nullable=False),
    sa.Column("output_artifact_id", sa.Uuid(), nullable=False),
    sa.Column("output_sha256", sa.CHAR(64), nullable=False),
    schema="processing",
)
step_table = sa.Table(
    "common_processing_output_step",
    metadata,
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("output_id", sa.Uuid(), nullable=False),
    sa.Column("output_revision_id", sa.Uuid(), nullable=False),
    sa.Column("ordinal", sa.Integer(), nullable=False),
    sa.Column("method_id", sa.String(160), nullable=False),
    sa.Column("method_version", sa.String(64), nullable=False),
    sa.Column("options_sha256", sa.CHAR(64), nullable=False),
    sa.Column("options", sa.JSON(), nullable=False),
    schema="processing",
)


def _values(value: ProcessingOutputContent) -> dict[str, object]:
    return {
        "label": value.label,
        "source_document_id": value.source_document.aggregate_id,
        "source_document_revision_id": value.source_document.revision_id,
        "source_document_sha256": value.source_document_sha256,
        "source_canonical_artifact_sha256": value.source_canonical_artifact_sha256,
        "mapping_profile_id": value.mapping_profile.aggregate_id,
        "mapping_profile_revision_id": value.mapping_profile.revision_id,
        "mapping_profile_sha256": value.mapping_profile_sha256,
        "independent_quantity": value.independent_quantity,
        "step_count": len(value.steps),
        "stage_count": value.stage_count,
        "final_point_count": value.final_point_count,
        "output_artifact_id": value.output_artifact_id,
        "output_sha256": value.output_sha256,
    }


def _write_steps(session: Session, draft: RevisionDraft[ProcessingOutputContent]) -> None:
    session.execute(
        sa.insert(step_table),
        [
            {
                "organization_id": draft.scope.organization_id,
                "project_id": draft.scope.project_id,
                "classification": draft.scope.classification,
                "output_id": draft.aggregate_id,
                "output_revision_id": draft.revision_id,
                "ordinal": ordinal,
                "method_id": step.method_id,
                "method_version": step.method_version,
                "options_sha256": content_sha256(step.options),
                "options": step.options,
            }
            for ordinal, step in enumerate(draft.content.steps)
        ],
    )


_TABLES = TypedRevisionTables(
    aggregate_type=PROCESSING_OUTPUT_AGGREGATE_TYPE,
    identity_table=output_table,
    revision_table=revision_table,
    canonical_content=processing_output_content_canonical,
    content_values=_values,
    identity_values=lambda value: {"label": value.label},
    revision_content_writer=_write_steps,
)


def _record(row: Any) -> RevisionRecord:
    return RevisionRecord(
        revision_id=cast(UUID, row["id"]),
        aggregate_type=PROCESSING_OUTPUT_AGGREGATE_TYPE,
        aggregate_id=cast(UUID, row["aggregate_id"]),
        scope=TenantScope(
            cast(UUID, row["organization_id"]),
            cast(UUID, row["project_id"]),
            str(row["classification"]),
        ),
        revision_no=int(row["revision_no"]),
        based_on_revision_id=cast(UUID | None, row["based_on_revision_id"]),
        schema_id=str(row["schema_id"]),
        schema_version=str(row["schema_version"]),
        content_hash=str(row["content_hash"]),
        created_at=row["created_at"],
        created_by=cast(UUID, row["created_by"]),
        change_reason=str(row["change_reason"]),
        request_id=cast(UUID, row["request_id"]),
        trace_id=str(row["trace_id"]),
    )


def _content(row: Any, steps: Sequence[Any]) -> ProcessingOutputContent:
    return ProcessingOutputContent(
        label=str(row["label"]),
        source_document=ExactRevisionPin(
            cast(UUID, row["source_document_id"]),
            cast(UUID, row["source_document_revision_id"]),
        ),
        source_document_sha256=str(row["source_document_sha256"]),
        source_canonical_artifact_sha256=str(row["source_canonical_artifact_sha256"]),
        mapping_profile=ExactRevisionPin(
            cast(UUID, row["mapping_profile_id"]),
            cast(UUID, row["mapping_profile_revision_id"]),
        ),
        mapping_profile_sha256=str(row["mapping_profile_sha256"]),
        steps=tuple(
            ProcessingStep(
                method_id=str(step["method_id"]),
                method_version=str(step["method_version"]),
                options=dict(step["options"]),
            )
            for step in steps
        ),
        independent_quantity=str(row["independent_quantity"]),
        stage_count=int(row["stage_count"]),
        final_point_count=int(row["final_point_count"]),
        output_artifact_id=cast(UUID, row["output_artifact_id"]),
        output_sha256=str(row["output_sha256"]),
    )


class SqlAlchemyCommonProcessingOutputRepository(ProcessingOutputRepository):
    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session],
        rls_context: RlsContext,
        revision_hooks: Sequence[SqlRevisionHook] = (),
    ) -> None:
        self._sessions = session_factory
        self._rls = rls_context
        self._hooks = tuple(revision_hooks)

    def _bind(
        self, session: Session, context: SecurityContext, decision: AuthorizationDecision
    ) -> None:
        self._rls.bind_authorization(session, context, decision)

    @contextmanager
    def _session(self, context: SecurityContext, decision: AuthorizationDecision) -> Any:
        with self._sessions() as session, session.begin():
            self._bind(session, context, decision)
            yield session

    def output_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[ProcessingOutputContent]:
        return SqlAlchemyRevisionStore(
            session_factory=self._sessions,
            tables=_TABLES,
            hooks=self._hooks,
            session_binder=lambda session: self._bind(session, context, decision),
        )

    @staticmethod
    def _snapshot(session: Session, row: Any) -> ProcessingOutputSnapshot:
        steps = (
            session.execute(
                sa.select(step_table)
                .where(step_table.c.output_revision_id == row["id"])
                .order_by(step_table.c.ordinal)
            )
            .mappings()
            .all()
        )
        record = _record(row)
        return ProcessingOutputSnapshot(record.aggregate_id, record, _content(row, steps))

    def get_output(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        output_id: UUID,
    ) -> ProcessingOutputSnapshot:
        with self._session(context, decision) as session:
            row = (
                session.execute(
                    sa.select(revision_table)
                    .join(
                        output_table,
                        sa.and_(
                            output_table.c.organization_id == revision_table.c.organization_id,
                            output_table.c.project_id == revision_table.c.project_id,
                            output_table.c.id == revision_table.c.aggregate_id,
                            output_table.c.current_revision_id == revision_table.c.id,
                        ),
                    )
                    .where(output_table.c.id == output_id)
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise ProcessingOutputNotFound("Processing Output is not visible")
            return self._snapshot(session, row)

    def list_outputs(
        self, *, context: SecurityContext, decision: AuthorizationDecision
    ) -> tuple[ProcessingOutputSnapshot, ...]:
        with self._session(context, decision) as session:
            rows = (
                session.execute(
                    sa.select(revision_table)
                    .join(
                        output_table,
                        sa.and_(
                            output_table.c.organization_id == revision_table.c.organization_id,
                            output_table.c.project_id == revision_table.c.project_id,
                            output_table.c.id == revision_table.c.aggregate_id,
                            output_table.c.current_revision_id == revision_table.c.id,
                        ),
                    )
                    .order_by(output_table.c.updated_at.desc(), output_table.c.id)
                )
                .mappings()
                .all()
            )
            return tuple(self._snapshot(session, row) for row in rows)

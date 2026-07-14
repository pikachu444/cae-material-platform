"""RLS-bound persistence for immutable human Calibration Candidate Selections."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Protocol, cast
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session, sessionmaker

from cmp.modules.identity_access.domain.authorization import AuthorizationDecision
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.modeling.application.candidate_selection import (
    CALIBRATION_CANDIDATE_SELECTION_AGGREGATE_TYPE,
    CalibrationCandidateSelectionSnapshot,
    CandidateSelectionRepository,
)
from cmp.modules.modeling.application.service import RevisionSnapshot
from cmp.modules.modeling.domain.reference_calibration_candidate_selection import (
    CandidateSelectionNotFound,
    ReferenceCalibrationCandidateSelectionContent,
    reference_calibration_candidate_selection_canonical,
)
from cmp.shared.adapters.persistence.revisions import (
    SqlAlchemyRevisionStore,
    SqlRevisionHook,
    TypedRevisionTables,
)
from cmp.shared.application.revisions import RevisionStore
from cmp.shared.domain.revisions import RevisionRecord, TenantScope


class RlsContext(Protocol):
    def bind_authorization(
        self,
        session: Session,
        context: SecurityContext,
        decision: AuthorizationDecision,
    ) -> None: ...


metadata = sa.MetaData()

candidate_selection_table = sa.Table(
    "calibration_candidate_selection",
    metadata,
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("current_revision_id", sa.Uuid(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("created_by", sa.Uuid(), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("selection_label", sa.String(160), nullable=False),
    sa.Column("calibration_run_id", sa.Uuid(), nullable=False),
    schema="modeling",
)
candidate_selection_revision_table = sa.Table(
    "calibration_candidate_selection_revision",
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
    sa.Column("calibration_run_id", sa.Uuid(), nullable=False),
    sa.Column("calibration_candidate_id", sa.Uuid(), nullable=False),
    sa.Column("candidate_sha256", sa.CHAR(64), nullable=False),
    sa.Column("selection_reason", sa.Text(), nullable=False),
    sa.Column("selection_decision", sa.String(100), nullable=False),
    sa.Column("non_production", sa.Boolean(), nullable=False),
    schema="modeling",
)


def _record(row: Any) -> RevisionRecord:
    return RevisionRecord(
        revision_id=cast(UUID, row["id"]),
        aggregate_type=CALIBRATION_CANDIDATE_SELECTION_AGGREGATE_TYPE,
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
        created_at=cast(datetime, row["created_at"]),
        created_by=cast(UUID, row["created_by"]),
        change_reason=str(row["change_reason"]),
        request_id=cast(UUID, row["request_id"]),
        trace_id=str(row["trace_id"]),
    )


def _content(row: Any) -> ReferenceCalibrationCandidateSelectionContent:
    return ReferenceCalibrationCandidateSelectionContent(
        selection_label=str(row["selection_label"]),
        calibration_run_id=cast(UUID, row["calibration_run_id"]),
        calibration_candidate_id=cast(UUID, row["calibration_candidate_id"]),
        candidate_sha256=str(row["candidate_sha256"]),
        selection_reason=str(row["selection_reason"]),
        selection_decision=str(row["selection_decision"]),
        non_production=bool(row["non_production"]),
    )


def _content_values(value: ReferenceCalibrationCandidateSelectionContent) -> dict[str, object]:
    return {
        "calibration_run_id": value.calibration_run_id,
        "calibration_candidate_id": value.calibration_candidate_id,
        "candidate_sha256": value.candidate_sha256,
        "selection_reason": value.selection_reason,
        "selection_decision": value.selection_decision,
        "non_production": value.non_production,
    }


_TABLES: TypedRevisionTables[ReferenceCalibrationCandidateSelectionContent] = TypedRevisionTables(
    aggregate_type=CALIBRATION_CANDIDATE_SELECTION_AGGREGATE_TYPE,
    identity_table=candidate_selection_table,
    revision_table=candidate_selection_revision_table,
    canonical_content=reference_calibration_candidate_selection_canonical,
    content_values=_content_values,
    identity_values=lambda value: {
        "selection_label": value.selection_label,
        "calibration_run_id": value.calibration_run_id,
    },
)


def _revision_columns(table: sa.Table) -> tuple[Any, ...]:
    return (
        table.c.id.label("id"),
        table.c.aggregate_id.label("aggregate_id"),
        table.c.organization_id.label("organization_id"),
        table.c.project_id.label("project_id"),
        table.c.classification.label("classification"),
        table.c.revision_no.label("revision_no"),
        table.c.based_on_revision_id.label("based_on_revision_id"),
        table.c.schema_id.label("schema_id"),
        table.c.schema_version.label("schema_version"),
        table.c.content_hash.label("content_hash"),
        table.c.created_at.label("created_at"),
        table.c.created_by.label("created_by"),
        table.c.change_reason.label("change_reason"),
        table.c.request_id.label("request_id"),
        table.c.trace_id.label("trace_id"),
    )


def _content_columns(table: sa.Table) -> tuple[Any, ...]:
    return (
        table.c.calibration_run_id.label("calibration_run_id"),
        table.c.calibration_candidate_id.label("calibration_candidate_id"),
        table.c.candidate_sha256.label("candidate_sha256"),
        table.c.selection_reason.label("selection_reason"),
        table.c.selection_decision.label("selection_decision"),
        table.c.non_production.label("non_production"),
    )


class SqlAlchemyCandidateSelectionRepository(CandidateSelectionRepository):
    """Store typed Selection identities/revisions under the request's RLS context."""

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

    def selection_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[ReferenceCalibrationCandidateSelectionContent]:
        return SqlAlchemyRevisionStore(
            session_factory=self._sessions,
            tables=_TABLES,
            hooks=self._hooks,
            session_binder=lambda session: self._bind(session, context, decision),
        )

    @contextmanager
    def _session(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> Iterator[Session]:
        with self._sessions() as session:
            with session.begin():
                self._bind(session, context, decision)
                yield session

    @staticmethod
    def _snapshot(row: Any) -> CalibrationCandidateSelectionSnapshot:
        return CalibrationCandidateSelectionSnapshot(
            id=cast(UUID, row["selection_id"]),
            current=RevisionSnapshot(_record(row), _content(row)),
        )

    def _current_statement(self) -> sa.Select[Any]:
        identity = candidate_selection_table
        revision = candidate_selection_revision_table
        return sa.select(
            identity.c.id.label("selection_id"),
            identity.c.selection_label.label("selection_label"),
            *_revision_columns(revision),
            *_content_columns(revision),
        ).select_from(
            identity.join(
                revision,
                sa.and_(
                    revision.c.id == identity.c.current_revision_id,
                    revision.c.aggregate_id == identity.c.id,
                    revision.c.organization_id == identity.c.organization_id,
                    revision.c.project_id == identity.c.project_id,
                ),
            )
        )

    def get_selection(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        selection_id: UUID,
    ) -> CalibrationCandidateSelectionSnapshot:
        identity = candidate_selection_table
        statement = self._current_statement().where(
            identity.c.id == selection_id,
            identity.c.organization_id == context.organization_id,
            identity.c.project_id == context.project_id,
        )
        with self._session(context, decision) as session:
            try:
                row = session.execute(statement).mappings().one_or_none()
            except DBAPIError as error:
                raise CandidateSelectionNotFound("Candidate Selection is not available") from error
        if row is None:
            raise CandidateSelectionNotFound(
                "Candidate Selection is not visible in the selected tenant"
            )
        return self._snapshot(row)

    def get_selection_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        selection_id: UUID,
        selection_revision_id: UUID,
    ) -> RevisionSnapshot[ReferenceCalibrationCandidateSelectionContent]:
        identity = candidate_selection_table
        revision = candidate_selection_revision_table
        statement = (
            sa.select(
                identity.c.selection_label.label("selection_label"),
                *_revision_columns(revision),
                *_content_columns(revision),
            )
            .select_from(
                identity.join(
                    revision,
                    sa.and_(
                        revision.c.aggregate_id == identity.c.id,
                        revision.c.organization_id == identity.c.organization_id,
                        revision.c.project_id == identity.c.project_id,
                    ),
                )
            )
            .where(
                identity.c.id == selection_id,
                revision.c.id == selection_revision_id,
                identity.c.organization_id == context.organization_id,
                identity.c.project_id == context.project_id,
            )
        )
        with self._session(context, decision) as session:
            try:
                row = session.execute(statement).mappings().one_or_none()
            except DBAPIError as error:
                raise CandidateSelectionNotFound(
                    "Candidate Selection revision is not available"
                ) from error
        if row is None:
            raise CandidateSelectionNotFound(
                "Candidate Selection revision is not visible in the selected tenant"
            )
        return RevisionSnapshot(_record(row), _content(row))

    def list_selections(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        limit: int,
    ) -> tuple[CalibrationCandidateSelectionSnapshot, ...]:
        identity = candidate_selection_table
        revision = candidate_selection_revision_table
        statement = (
            self._current_statement()
            .where(
                identity.c.organization_id == context.organization_id,
                identity.c.project_id == context.project_id,
            )
            .order_by(revision.c.created_at.desc(), identity.c.id.asc())
            .limit(limit)
        )
        with self._session(context, decision) as session:
            try:
                rows = session.execute(statement).mappings().all()
            except DBAPIError as error:
                raise CandidateSelectionNotFound(
                    "Candidate Selections are not available"
                ) from error
        return tuple(self._snapshot(row) for row in rows)

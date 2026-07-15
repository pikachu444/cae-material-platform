"""PostgreSQL persistence for immutable human Prony Candidate Selections."""

from __future__ import annotations

from collections.abc import Sequence
from contextlib import contextmanager
from typing import Any, Protocol, cast
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session, sessionmaker

from cmp.modules.identity_access.domain.authorization import AuthorizationDecision
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.modeling.application.prony_candidate_promotion import (
    PRONY_CANDIDATE_SELECTION_AGGREGATE_TYPE,
    PronyCandidateSelectionRepository,
    PronyCandidateSelectionSnapshot,
)
from cmp.modules.modeling.application.service import RevisionSnapshot
from cmp.modules.modeling.domain.reference_prony_candidate_selection import (
    PronyCandidateSelectionNotFound,
    ReferencePronyCandidateSelectionContent,
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
        self, session: Session, context: SecurityContext, decision: AuthorizationDecision
    ) -> None: ...


metadata = sa.MetaData()
selection_table = sa.Table(
    "prony_candidate_selection",
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
    sa.Column("prony_calibration_run_id", sa.Uuid(), nullable=False),
    schema="modeling",
)
selection_revision_table = sa.Table(
    "prony_candidate_selection_revision",
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
    sa.Column("prony_calibration_run_id", sa.Uuid(), nullable=False),
    sa.Column("prony_calibration_candidate_id", sa.Uuid(), nullable=False),
    sa.Column("candidate_sha256", sa.CHAR(64), nullable=False),
    sa.Column("baseline_model_id", sa.Uuid(), nullable=False),
    sa.Column("baseline_model_revision_id", sa.Uuid(), nullable=False),
    sa.Column("selection_reason", sa.Text(), nullable=False),
    sa.Column("selection_decision", sa.String(100), nullable=False),
    sa.Column("non_production", sa.Boolean(), nullable=False),
    schema="modeling",
)


def _record(row: Any) -> RevisionRecord:
    return RevisionRecord(
        revision_id=cast(UUID, row["id"]),
        aggregate_type=PRONY_CANDIDATE_SELECTION_AGGREGATE_TYPE,
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


def _content(row: Any) -> ReferencePronyCandidateSelectionContent:
    return ReferencePronyCandidateSelectionContent(
        selection_label=str(row["selection_label"]),
        prony_calibration_run_id=cast(UUID, row["prony_calibration_run_id"]),
        prony_calibration_candidate_id=cast(UUID, row["prony_calibration_candidate_id"]),
        candidate_sha256=str(row["candidate_sha256"]),
        baseline_model_id=cast(UUID, row["baseline_model_id"]),
        baseline_model_revision_id=cast(UUID, row["baseline_model_revision_id"]),
        selection_reason=str(row["selection_reason"]),
        selection_decision=str(row["selection_decision"]),
        non_production=bool(row["non_production"]),
    )


def _values(value: ReferencePronyCandidateSelectionContent) -> dict[str, object]:
    return {
        "prony_calibration_run_id": value.prony_calibration_run_id,
        "prony_calibration_candidate_id": value.prony_calibration_candidate_id,
        "candidate_sha256": value.candidate_sha256,
        "baseline_model_id": value.baseline_model_id,
        "baseline_model_revision_id": value.baseline_model_revision_id,
        "selection_reason": value.selection_reason,
        "selection_decision": value.selection_decision,
        "non_production": value.non_production,
    }


_TABLES = TypedRevisionTables(
    aggregate_type=PRONY_CANDIDATE_SELECTION_AGGREGATE_TYPE,
    identity_table=selection_table,
    revision_table=selection_revision_table,
    canonical_content=lambda value: value.canonical(),
    content_values=_values,
    identity_values=lambda value: {
        "selection_label": value.selection_label,
        "prony_calibration_run_id": value.prony_calibration_run_id,
    },
)


class SqlAlchemyPronyCandidateSelectionRepository(PronyCandidateSelectionRepository):
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
    def _session(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> Any:
        with self._sessions() as session, session.begin():
            self._bind(session, context, decision)
            yield session

    def selection_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[ReferencePronyCandidateSelectionContent]:
        return SqlAlchemyRevisionStore(
            session_factory=self._sessions,
            tables=_TABLES,
            hooks=self._hooks,
            session_binder=lambda session: self._bind(session, context, decision),
        )

    @staticmethod
    def _statement() -> sa.Select[Any]:
        return sa.select(
            *selection_revision_table.c, selection_table.c.selection_label
        ).select_from(
            selection_table.join(
                selection_revision_table,
                sa.and_(
                    selection_revision_table.c.aggregate_id == selection_table.c.id,
                    selection_revision_table.c.organization_id
                    == selection_table.c.organization_id,
                    selection_revision_table.c.project_id == selection_table.c.project_id,
                ),
            )
        )

    @staticmethod
    def _snapshot(row: Any) -> PronyCandidateSelectionSnapshot:
        return PronyCandidateSelectionSnapshot(
            cast(UUID, row["aggregate_id"]), RevisionSnapshot(_record(row), _content(row))
        )

    def get_selection(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        selection_id: UUID,
    ) -> PronyCandidateSelectionSnapshot:
        statement = self._statement().where(
            selection_table.c.id == selection_id,
            selection_revision_table.c.id == selection_table.c.current_revision_id,
            selection_table.c.organization_id == context.organization_id,
            selection_table.c.project_id == context.project_id,
        )
        with self._session(context, decision) as session:
            try:
                row = session.execute(statement).mappings().one_or_none()
            except DBAPIError as error:
                raise PronyCandidateSelectionNotFound(
                    "Prony Selection is unavailable"
                ) from error
        if row is None:
            raise PronyCandidateSelectionNotFound("Prony Selection is not visible")
        return self._snapshot(row)

    def get_selection_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        selection_id: UUID,
        selection_revision_id: UUID,
    ) -> RevisionSnapshot[ReferencePronyCandidateSelectionContent]:
        statement = self._statement().where(
            selection_table.c.id == selection_id,
            selection_revision_table.c.id == selection_revision_id,
            selection_table.c.organization_id == context.organization_id,
            selection_table.c.project_id == context.project_id,
        )
        with self._session(context, decision) as session:
            try:
                row = session.execute(statement).mappings().one_or_none()
            except DBAPIError as error:
                raise PronyCandidateSelectionNotFound(
                    "Prony Selection revision is unavailable"
                ) from error
        if row is None:
            raise PronyCandidateSelectionNotFound(
                "Prony Selection revision is not visible"
            )
        return RevisionSnapshot(_record(row), _content(row))

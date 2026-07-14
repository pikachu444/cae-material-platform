"""RLS-bound PostgreSQL persistence for immutable review requests and decisions."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Protocol, cast
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.review_release.application.service import ReviewRepository
from cmp.modules.review_release.domain.lifecycle import (
    REQUIRED_REVIEW_ROLE,
    DecideReviewRequest,
    LifecycleState,
    ReviewConflict,
    ReviewDecisionKind,
    ReviewDecisionRecord,
    ReviewNotFound,
    ReviewRequestRecord,
    SubmitReviewRequest,
)


class RlsContext(Protocol):
    def bind_authorization(
        self,
        session: Session,
        context: SecurityContext,
        decision: AuthorizationDecision,
    ) -> None: ...


metadata = sa.MetaData()

lifecycle_event_table = sa.Table(
    "lifecycle_event",
    metadata,
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("aggregate_type", sa.String(100), nullable=False),
    sa.Column("aggregate_id", sa.Uuid(), nullable=False),
    sa.Column("revision_id", sa.Uuid(), nullable=False),
    sa.Column("sequence_no", sa.BigInteger(), nullable=False),
    sa.Column("from_state", sa.String(64), nullable=True),
    sa.Column("to_state", sa.String(64), nullable=False),
    sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("actor_id", sa.Uuid(), nullable=False),
    sa.Column("reason", sa.Text(), nullable=False),
    sa.Column("request_id", sa.Uuid(), nullable=False),
    sa.Column("trace_id", sa.String(255), nullable=False),
    schema="governance",
)

lifecycle_projection_table = sa.Table(
    "lifecycle_projection",
    metadata,
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("aggregate_type", sa.String(100), nullable=False),
    sa.Column("aggregate_id", sa.Uuid(), nullable=False),
    sa.Column("revision_id", sa.Uuid(), nullable=False),
    sa.Column("lifecycle_state", sa.String(64), nullable=False),
    sa.Column("sequence_no", sa.BigInteger(), nullable=False),
    sa.Column("last_event_id", sa.Uuid(), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    schema="governance",
)

review_request_table = sa.Table(
    "review_request",
    metadata,
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("aggregate_type", sa.String(100), nullable=False),
    sa.Column("aggregate_id", sa.Uuid(), nullable=False),
    sa.Column("revision_id", sa.Uuid(), nullable=False),
    sa.Column("manifest_sha256", sa.CHAR(64), nullable=False),
    sa.Column("required_role", sa.String(100), nullable=False),
    sa.Column("requested_by", sa.Uuid(), nullable=False),
    sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("reason", sa.Text(), nullable=False),
    sa.Column("request_id", sa.Uuid(), nullable=False),
    sa.Column("trace_id", sa.String(255), nullable=False),
    schema="governance",
)

review_decision_table = sa.Table(
    "review_decision",
    metadata,
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("review_request_id", sa.Uuid(), nullable=False),
    sa.Column("aggregate_type", sa.String(100), nullable=False),
    sa.Column("aggregate_id", sa.Uuid(), nullable=False),
    sa.Column("revision_id", sa.Uuid(), nullable=False),
    sa.Column("manifest_sha256", sa.CHAR(64), nullable=False),
    sa.Column("decision", sa.String(64), nullable=False),
    sa.Column("decided_by", sa.Uuid(), nullable=False),
    sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("reason", sa.Text(), nullable=False),
    sa.Column("request_id", sa.Uuid(), nullable=False),
    sa.Column("trace_id", sa.String(255), nullable=False),
    schema="governance",
)


def _scope_clause(table: sa.Table, context: SecurityContext) -> sa.ColumnElement[bool]:
    return sa.and_(
        table.c.organization_id == context.organization_id,
        table.c.project_id == context.project_id,
    )


def _request_record(row: Any, decision_row: Any | None = None) -> ReviewRequestRecord:
    decision = None
    if decision_row is not None:
        decision = ReviewDecisionRecord(
            id=cast(UUID, decision_row["id"]),
            review_request_id=cast(UUID, decision_row["review_request_id"]),
            organization_id=cast(UUID, decision_row["organization_id"]),
            project_id=cast(UUID, decision_row["project_id"]),
            classification=DataClassification(str(decision_row["classification"])),
            aggregate_type=str(decision_row["aggregate_type"]),
            aggregate_id=cast(UUID, decision_row["aggregate_id"]),
            revision_id=cast(UUID, decision_row["revision_id"]),
            manifest_sha256=str(decision_row["manifest_sha256"]),
            decision=ReviewDecisionKind(str(decision_row["decision"])),
            decided_by=cast(UUID, decision_row["decided_by"]),
            decided_at=cast(datetime, decision_row["decided_at"]),
            reason=str(decision_row["reason"]),
        )
    return ReviewRequestRecord(
        id=cast(UUID, row["id"]),
        organization_id=cast(UUID, row["organization_id"]),
        project_id=cast(UUID, row["project_id"]),
        classification=DataClassification(str(row["classification"])),
        aggregate_type=str(row["aggregate_type"]),
        aggregate_id=cast(UUID, row["aggregate_id"]),
        revision_id=cast(UUID, row["revision_id"]),
        manifest_sha256=str(row["manifest_sha256"]),
        required_role=str(row["required_role"]),
        requested_by=cast(UUID, row["requested_by"]),
        requested_at=cast(datetime, row["requested_at"]),
        reason=str(row["reason"]),
        lifecycle_state=LifecycleState(str(row["lifecycle_state"])),
        decision=decision,
    )


class SqlAlchemyReviewRepository(ReviewRepository):
    """Persist review facts and lifecycle transitions in one tenant-bound transaction."""

    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session],
        rls_context: RlsContext,
        id_factory: Callable[[], UUID] = uuid4,
    ) -> None:
        self._sessions = session_factory
        self._rls = rls_context
        self._id_factory = id_factory

    @contextmanager
    def _session(self, context: SecurityContext, decision: AuthorizationDecision) -> Any:
        with self._sessions() as session, session.begin():
            self._rls.bind_authorization(session, context, decision)
            yield session

    @staticmethod
    def _projection(
        session: Session,
        *,
        context: SecurityContext,
        aggregate_type: str,
        aggregate_id: UUID,
        revision_id: UUID,
        for_update: bool = False,
    ) -> Any | None:
        statement = sa.select(lifecycle_projection_table).where(
            _scope_clause(lifecycle_projection_table, context),
            lifecycle_projection_table.c.aggregate_type == aggregate_type,
            lifecycle_projection_table.c.aggregate_id == aggregate_id,
            lifecycle_projection_table.c.revision_id == revision_id,
        )
        if for_update:
            statement = statement.with_for_update()
        return session.execute(statement).mappings().one_or_none()

    @staticmethod
    def _decision_row(
        session: Session,
        *,
        context: SecurityContext,
        review_request_id: UUID,
        for_update: bool = False,
    ) -> Any | None:
        statement = sa.select(review_decision_table).where(
            _scope_clause(review_decision_table, context),
            review_decision_table.c.review_request_id == review_request_id,
        )
        if for_update:
            statement = statement.with_for_update()
        return session.execute(statement).mappings().one_or_none()

    def _request_row(
        self,
        session: Session,
        *,
        context: SecurityContext,
        review_request_id: UUID,
        for_update: bool = False,
    ) -> Any | None:
        statement = sa.select(
            review_request_table,
            lifecycle_projection_table.c.lifecycle_state,
        ).select_from(
            review_request_table.join(
                lifecycle_projection_table,
                sa.and_(
                    lifecycle_projection_table.c.organization_id
                    == review_request_table.c.organization_id,
                    lifecycle_projection_table.c.project_id == review_request_table.c.project_id,
                    lifecycle_projection_table.c.aggregate_type
                    == review_request_table.c.aggregate_type,
                    lifecycle_projection_table.c.aggregate_id
                    == review_request_table.c.aggregate_id,
                    lifecycle_projection_table.c.revision_id
                    == review_request_table.c.revision_id,
                ),
            )
        ).where(
            _scope_clause(review_request_table, context),
            review_request_table.c.id == review_request_id,
        )
        if for_update:
            statement = statement.with_for_update()
        return session.execute(statement).mappings().one_or_none()

    def _append_transition(
        self,
        session: Session,
        *,
        context: SecurityContext,
        projection: Any,
        to_state: LifecycleState,
        actor_id: UUID,
        reason: str,
        occurred_at: datetime,
    ) -> None:
        event_id = self._id_factory()
        if event_id.int == 0:
            raise ReviewConflict("lifecycle event id_factory returned a zero UUID")
        session.execute(
            sa.insert(lifecycle_event_table).values(
                id=event_id,
                organization_id=context.organization_id,
                project_id=context.project_id,
                classification=projection["classification"],
                aggregate_type=projection["aggregate_type"],
                aggregate_id=projection["aggregate_id"],
                revision_id=projection["revision_id"],
                sequence_no=int(projection["sequence_no"]) + 1,
                from_state=projection["lifecycle_state"],
                to_state=to_state.value,
                occurred_at=occurred_at,
                actor_id=actor_id,
                reason=reason,
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        result = session.execute(
            sa.update(lifecycle_projection_table)
            .where(
                _scope_clause(lifecycle_projection_table, context),
                lifecycle_projection_table.c.aggregate_type == projection["aggregate_type"],
                lifecycle_projection_table.c.aggregate_id == projection["aggregate_id"],
                lifecycle_projection_table.c.revision_id == projection["revision_id"],
                lifecycle_projection_table.c.sequence_no == projection["sequence_no"],
            )
            .values(
                lifecycle_state=to_state.value,
                sequence_no=int(projection["sequence_no"]) + 1,
                last_event_id=event_id,
                updated_at=occurred_at,
            )
        )
        if getattr(result, "rowcount", None) != 1:
            raise ReviewConflict("lifecycle projection changed while applying review transition")

    def create_request(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        review_request_id: UUID,
        command: SubmitReviewRequest,
        actor_id: UUID,
        occurred_at: datetime,
    ) -> ReviewRequestRecord:
        with self._session(context, decision) as session:
            projection = self._projection(
                session,
                context=context,
                aggregate_type=command.aggregate_type,
                aggregate_id=command.aggregate_id,
                revision_id=command.revision_id,
                for_update=True,
            )
            if projection is None:
                raise ReviewNotFound("immutable lifecycle target is not visible")
            if projection["classification"] != command.classification.value:
                raise ReviewConflict("review classification does not match the immutable target")
            if projection["lifecycle_state"] != LifecycleState.DRAFT.value:
                raise ReviewConflict(
                    "review requests require a draft revision; changes_requested requires a "
                    "new revision"
                )
            existing = session.execute(
                sa.select(review_request_table.c.id).where(
                    _scope_clause(review_request_table, context),
                    review_request_table.c.aggregate_type == command.aggregate_type,
                    review_request_table.c.aggregate_id == command.aggregate_id,
                    review_request_table.c.revision_id == command.revision_id,
                )
            ).scalar_one_or_none()
            if existing is not None:
                raise ReviewConflict("one review request is allowed per immutable revision")
            session.execute(
                sa.insert(review_request_table).values(
                    id=review_request_id,
                    organization_id=context.organization_id,
                    project_id=context.project_id,
                    classification=command.classification.value,
                    aggregate_type=command.aggregate_type,
                    aggregate_id=command.aggregate_id,
                    revision_id=command.revision_id,
                    manifest_sha256=command.manifest_sha256,
                    required_role=REQUIRED_REVIEW_ROLE,
                    requested_by=actor_id,
                    requested_at=occurred_at,
                    reason=command.reason,
                    request_id=context.request_id,
                    trace_id=context.trace_id,
                )
            )
            self._append_transition(
                session,
                context=context,
                projection=projection,
                to_state=LifecycleState.REVIEW,
                actor_id=actor_id,
                reason=command.reason,
                occurred_at=occurred_at,
            )
            row = self._request_row(
                session,
                context=context,
                review_request_id=review_request_id,
            )
            if row is None:
                raise ReviewConflict("created review request could not be reloaded")
            return _request_record(row)

    def get_request(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        review_request_id: UUID,
    ) -> ReviewRequestRecord:
        with self._session(context, decision) as session:
            row = self._request_row(
                session,
                context=context,
                review_request_id=review_request_id,
            )
            if row is None:
                raise ReviewNotFound("review request is not visible")
            return _request_record(
                row,
                self._decision_row(
                    session,
                    context=context,
                    review_request_id=review_request_id,
                ),
            )

    def list_requests(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        limit: int,
        aggregate_type: str | None = None,
        aggregate_id: UUID | None = None,
        revision_id: UUID | None = None,
    ) -> tuple[ReviewRequestRecord, ...]:
        with self._session(context, decision) as session:
            statement = (
                sa.select(review_request_table.c.id)
                .where(_scope_clause(review_request_table, context))
                .order_by(review_request_table.c.requested_at.desc())
                .limit(limit)
            )
            if aggregate_type is not None:
                statement = statement.where(review_request_table.c.aggregate_type == aggregate_type)
            if aggregate_id is not None:
                statement = statement.where(review_request_table.c.aggregate_id == aggregate_id)
            if revision_id is not None:
                statement = statement.where(review_request_table.c.revision_id == revision_id)
            ids = tuple(session.execute(statement).scalars())
            values: list[ReviewRequestRecord] = []
            for review_request_id in ids:
                row = self._request_row(
                    session,
                    context=context,
                    review_request_id=review_request_id,
                )
                if row is None:
                    continue
                values.append(
                    _request_record(
                        row,
                        self._decision_row(
                            session,
                            context=context,
                            review_request_id=review_request_id,
                        ),
                    )
                )
            return tuple(values)

    def decide(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        decision_id: UUID,
        review_request_id: UUID,
        command: DecideReviewRequest,
        actor_id: UUID,
        occurred_at: datetime,
    ) -> ReviewRequestRecord:
        with self._session(context, decision) as session:
            row = self._request_row(
                session,
                context=context,
                review_request_id=review_request_id,
                for_update=True,
            )
            if row is None:
                raise ReviewNotFound("review request is not visible")
            if row["lifecycle_state"] != LifecycleState.REVIEW.value:
                raise ReviewConflict("review request is not waiting for a decision")
            if row["manifest_sha256"] != command.expected_manifest_sha256:
                raise ReviewConflict(
                    "review manifest digest is stale or does not match the request"
                )
            if row["requested_by"] == actor_id:
                raise ReviewConflict("separation of duties forbids the author from deciding")
            if self._decision_row(
                session,
                context=context,
                review_request_id=review_request_id,
                for_update=True,
            ) is not None:
                raise ReviewConflict(
                    "review decisions are append-only and this request is already decided"
                )
            stale_revision = session.execute(
                sa.select(lifecycle_event_table.c.id)
                .where(
                    _scope_clause(lifecycle_event_table, context),
                    lifecycle_event_table.c.aggregate_type == row["aggregate_type"],
                    lifecycle_event_table.c.aggregate_id == row["aggregate_id"],
                    lifecycle_event_table.c.revision_id != row["revision_id"],
                    lifecycle_event_table.c.to_state == LifecycleState.DRAFT.value,
                    lifecycle_event_table.c.occurred_at > row["requested_at"],
                )
                .limit(1)
            ).scalar_one_or_none()
            if stale_revision is not None:
                raise ReviewConflict(
                    "a newer immutable revision exists; the review candidate is stale"
                )
            session.execute(
                sa.insert(review_decision_table).values(
                    id=decision_id,
                    organization_id=context.organization_id,
                    project_id=context.project_id,
                    classification=row["classification"],
                    review_request_id=review_request_id,
                    aggregate_type=row["aggregate_type"],
                    aggregate_id=row["aggregate_id"],
                    revision_id=row["revision_id"],
                    manifest_sha256=row["manifest_sha256"],
                    decision=command.decision.value,
                    decided_by=actor_id,
                    decided_at=occurred_at,
                    reason=command.reason,
                    request_id=context.request_id,
                    trace_id=context.trace_id,
                )
            )
            projection = self._projection(
                session,
                context=context,
                aggregate_type=row["aggregate_type"],
                aggregate_id=row["aggregate_id"],
                revision_id=row["revision_id"],
                for_update=True,
            )
            if projection is None:
                raise ReviewNotFound("review lifecycle projection is not visible")
            self._append_transition(
                session,
                context=context,
                projection=projection,
                to_state=(
                    LifecycleState.APPROVED
                    if command.decision is ReviewDecisionKind.APPROVED
                    else LifecycleState.CHANGES_REQUESTED
                ),
                actor_id=actor_id,
                reason=command.reason,
                occurred_at=occurred_at,
            )
            updated = self._request_row(
                session,
                context=context,
                review_request_id=review_request_id,
            )
            if updated is None:
                raise ReviewConflict("decided review request could not be reloaded")
            return _request_record(
                updated,
                self._decision_row(
                    session,
                    context=context,
                    review_request_id=review_request_id,
                ),
            )

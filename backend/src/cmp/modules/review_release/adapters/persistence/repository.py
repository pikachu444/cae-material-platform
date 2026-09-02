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
    Role,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.review_release.adapters.persistence.publication import (
    ReviewApprovalProjector,
)
from cmp.modules.review_release.application.service import ReviewRepository
from cmp.modules.review_release.domain.evidence import (
    REGISTERED_REVIEW_SUBJECT_TYPES,
    ReviewSubjectEvidence,
)
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
    sa.Column("requested_by_display_name", sa.String(255), nullable=False),
    sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("reason", sa.Text(), nullable=False),
    sa.Column("subject_evidence", sa.JSON(), nullable=True),
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

_subject_identity_tables = {
    "catalog.material": sa.Table(
        "material",
        metadata,
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("current_revision_id", sa.Uuid(), nullable=False),
        schema="catalog",
    ),
    "catalog.configurable_record": sa.Table(
        "catalog_record",
        metadata,
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("current_revision_id", sa.Uuid(), nullable=False),
        schema="catalog",
    ),
    "datasets.test_data_document": sa.Table(
        "test_data_document",
        metadata,
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("current_revision_id", sa.Uuid(), nullable=False),
        schema="datasets",
    ),
    "modeling.material_model": sa.Table(
        "material_model",
        metadata,
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("current_revision_id", sa.Uuid(), nullable=False),
        schema="modeling",
    ),
    "modeling.linear_viscoelastic_calibration_plan": sa.Table(
        "linear_viscoelastic_calibration_plan",
        metadata,
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("classification", sa.String(64), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("current_revision_id", sa.Uuid(), nullable=False),
        schema="modeling",
    ),
    "exporting.solver_card": sa.Table(
        "solver_card",
        metadata,
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("current_revision_id", sa.Uuid(), nullable=False),
        schema="exporting",
    ),
    "exporting.neutral_solver_card": sa.Table(
        "neutral_solver_card",
        metadata,
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("current_revision_id", sa.Uuid(), nullable=False),
        schema="exporting",
    ),
}


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
        requested_by_display_name=(
            str(row.get("requested_by_display_name"))
            if row.get("requested_by_display_name")
            else None
        ),
        requested_at=cast(datetime, row["requested_at"]),
        reason=str(row["reason"]),
        lifecycle_state=LifecycleState(str(row["lifecycle_state"])),
        decision=decision,
        evidence=(
            ReviewSubjectEvidence.from_document(row["subject_evidence"])
            if row.get("subject_evidence") is not None
            else None
        ),
    )


class SqlAlchemyReviewRepository(ReviewRepository):
    """Persist review facts and lifecycle transitions in one tenant-bound transaction."""

    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session],
        rls_context: RlsContext,
        id_factory: Callable[[], UUID] = uuid4,
        approval_projector: ReviewApprovalProjector | None = None,
    ) -> None:
        self._sessions = session_factory
        self._rls = rls_context
        self._id_factory = id_factory
        self._approval_projector = approval_projector

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
            # ``review_request`` is immutable and intentionally has no UPDATE policy.  Lock
            # the mutable lifecycle projection instead; PostgreSQL otherwise hides the joined
            # request row under SELECT ... FOR UPDATE when no UPDATE policy exists.
            statement = statement.with_for_update(of=lifecycle_projection_table)
        return session.execute(statement).mappings().one_or_none()

    @staticmethod
    def _assert_current_subject(
        session: Session,
        *,
        context: SecurityContext,
        aggregate_type: str,
        aggregate_id: UUID,
        revision_id: UUID,
    ) -> None:
        identity = _subject_identity_tables.get(aggregate_type)
        if identity is None:
            return
        current_revision_id = session.execute(
            sa.select(identity.c.current_revision_id)
            .where(
                identity.c.organization_id == context.organization_id,
                identity.c.project_id == context.project_id,
                identity.c.id == aggregate_id,
            )
        ).scalar_one_or_none()
        if current_revision_id is None:
            raise ReviewNotFound("review subject identity is not visible")
        if current_revision_id != revision_id:
            raise ReviewConflict("review subject revision changed while submitting")

    @staticmethod
    def _insert_request_if_current(
        session: Session,
        *,
        context: SecurityContext,
        aggregate_type: str,
        aggregate_id: UUID,
        revision_id: UUID,
        values: dict[str, Any],
    ) -> None:
        """Insert a request only when its subject head matches this statement snapshot.

        Subject identity rows are readable by ordinary review requesters but not writable,
        so row-locking them would apply PostgreSQL UPDATE RLS and hide valid candidates.  An
        INSERT ... SELECT guard instead makes the final current-head check atomic with the
        request fact: a concurrent head update committed before this statement yields zero
        inserted rows and a stale-review conflict, while a commit after this statement is
        ordered after the request was accepted.
        """
        identity = _subject_identity_tables.get(aggregate_type)
        if identity is None:
            session.execute(sa.insert(review_request_table).values(**values))
            return
        column_names = tuple(values)
        target_columns = tuple(review_request_table.c[name] for name in column_names)
        bind_values = tuple(
            sa.bindparam(
                f"review_request_{name}",
                value=values[name],
                type_=review_request_table.c[name].type,
            )
            for name in column_names
        )
        guarded_values = sa.select(*bind_values).select_from(identity).where(
            identity.c.organization_id == context.organization_id,
            identity.c.project_id == context.project_id,
            identity.c.id == aggregate_id,
            identity.c.current_revision_id == revision_id,
        )
        inserted_id = session.execute(
            sa.insert(review_request_table)
            .from_select(target_columns, guarded_values)
            .returning(review_request_table.c.id)
        ).scalar_one_or_none()
        if inserted_id != values["id"]:
            raise ReviewConflict("review subject revision changed while submitting")

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
        # ``review_decision`` is an immutable fact and intentionally has no UPDATE policy.
        # Do not issue SELECT ... FOR UPDATE here: PostgreSQL would apply UPDATE-policy
        # visibility and hide an existing decision.  The caller locks the mutable lifecycle
        # projection before checking/inserting this unique fact.
        return session.execute(statement).mappings().one_or_none()

    def _request_row(
        self,
        session: Session,
        *,
        context: SecurityContext,
        review_request_id: UUID,
        reviewer: bool = False,
        for_update: bool = False,
    ) -> Any | None:
        statement = (
            sa.select(
                review_request_table,
                lifecycle_projection_table.c.lifecycle_state,
            )
            .select_from(
                review_request_table.join(
                    lifecycle_projection_table,
                    sa.and_(
                        lifecycle_projection_table.c.organization_id
                        == review_request_table.c.organization_id,
                        lifecycle_projection_table.c.project_id
                        == review_request_table.c.project_id,
                        lifecycle_projection_table.c.aggregate_type
                        == review_request_table.c.aggregate_type,
                        lifecycle_projection_table.c.aggregate_id
                        == review_request_table.c.aggregate_id,
                        lifecycle_projection_table.c.revision_id
                        == review_request_table.c.revision_id,
                    ),
                )
            )
            .where(
                _scope_clause(review_request_table, context),
                review_request_table.c.id == review_request_id,
                sa.or_(
                    review_request_table.c.requested_by == context.principal.id,
                    sa.true() if reviewer else sa.false(),
                ),
            )
        )
        if for_update:
            # Lock only the mutable projection.  Locking the immutable review request would
            # require an UPDATE policy and PostgreSQL would hide the otherwise visible row.
            statement = statement.with_for_update(of=lifecycle_projection_table)
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
            # Serialize against a concurrent immutable revision append and re-check the
            # current head after evidence resolution.  The resolver runs in its own
            # transaction, so this lock closes the stale-submit race before the request fact
            # is inserted.
            self._assert_current_subject(
                session,
                context=context,
                aggregate_type=command.aggregate_type,
                aggregate_id=command.aggregate_id,
                revision_id=command.revision_id,
            )
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
            classification = command.classification
            if classification is None or command.manifest_sha256 is None:
                raise ReviewConflict("review subject evidence must be resolved server-side")
            if projection["classification"] != classification.value:
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
            self._insert_request_if_current(
                session,
                context=context,
                aggregate_type=command.aggregate_type,
                aggregate_id=command.aggregate_id,
                revision_id=command.revision_id,
                values={
                    "id": review_request_id,
                    "organization_id": context.organization_id,
                    "project_id": context.project_id,
                    "classification": classification.value,
                    "aggregate_type": command.aggregate_type,
                    "aggregate_id": command.aggregate_id,
                    "revision_id": command.revision_id,
                    "manifest_sha256": command.manifest_sha256,
                    "required_role": REQUIRED_REVIEW_ROLE,
                    "requested_by": actor_id,
                    "requested_by_display_name": context.principal.display_name,
                    "requested_at": occurred_at,
                    "reason": command.reason,
                    "subject_evidence": (
                        command.evidence.to_document() if command.evidence else None
                    ),
                    "request_id": context.request_id,
                    "trace_id": context.trace_id,
                },
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
                reviewer=Role.DOMAIN_REVIEWER in decision.roles,
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
                reviewer=Role.DOMAIN_REVIEWER in decision.roles,
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
            if Role.DOMAIN_REVIEWER in decision.roles:
                # Reviewers are intentionally tenant-scoped rather than assignment-scoped:
                # without an assignment model they must be able to read pending work and the
                # append-only outcomes they just recorded after the lifecycle leaves ``review``.
                statement = sa.select(review_request_table.c.id).select_from(
                    review_request_table.join(
                        lifecycle_projection_table,
                        sa.and_(
                            lifecycle_projection_table.c.organization_id
                            == review_request_table.c.organization_id,
                            lifecycle_projection_table.c.project_id
                            == review_request_table.c.project_id,
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
                )
            else:
                statement = sa.select(review_request_table.c.id).where(
                    _scope_clause(review_request_table, context),
                    review_request_table.c.requested_by == context.principal.id,
                )
            if aggregate_type is not None:
                statement = statement.where(review_request_table.c.aggregate_type == aggregate_type)
            if aggregate_id is not None:
                statement = statement.where(review_request_table.c.aggregate_id == aggregate_id)
            if revision_id is not None:
                statement = statement.where(review_request_table.c.revision_id == revision_id)
            statement = statement.order_by(review_request_table.c.requested_at.desc()).limit(limit)
            ids = tuple(session.execute(statement).scalars())
            values: list[ReviewRequestRecord] = []
            for review_request_id in ids:
                row = self._request_row(
                    session,
                    context=context,
                    review_request_id=review_request_id,
                    reviewer=Role.DOMAIN_REVIEWER in decision.roles,
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
                reviewer=Role.DOMAIN_REVIEWER in decision.roles,
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
            if (
                self._decision_row(
                    session,
                    context=context,
                    review_request_id=review_request_id,
                    for_update=True,
                )
                is not None
            ):
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
            if command.decision is ReviewDecisionKind.APPROVED:
                evidence = _request_record(
                    row,
                    self._decision_row(
                        session,
                        context=context,
                        review_request_id=review_request_id,
                    ),
                ).evidence
                # Issue #160 subjects are projected from their immutable typed evidence
                # snapshot.  ``validation.result`` predates that closed registry and has
                # intentionally null evidence; preserve its existing decision lifecycle
                # while keeping the new subject set fail-closed.
                if (
                    self._approval_projector is not None
                    and row["aggregate_type"] in REGISTERED_REVIEW_SUBJECT_TYPES
                ):
                    if evidence is None:
                        raise ReviewConflict(
                            "approved review request has no immutable subject evidence"
                        )
                    self._approval_projector.project(
                        session=session,
                        context=context,
                        review_request_id=review_request_id,
                        review_decision_id=decision_id,
                        evidence=evidence,
                        published_by=actor_id,
                        occurred_at=occurred_at,
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
                reviewer=Role.DOMAIN_REVIEWER in decision.roles,
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

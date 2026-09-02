"""SQLAlchemy adapter for T-05 append, query, export, integrity, and sealing."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any, Protocol
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.orm import Session

from cmp.modules.audit.application.service import AuditEventPage, AuditEventQuery
from cmp.modules.audit.domain.model import (
    GENESIS_HASH,
    AuditActorType,
    AuditConflict,
    AuditEvent,
    AuditEventDraft,
    AuditOutcome,
    AuditScope,
    AuditSegmentRoot,
    event_sha256,
    redact_ip_or_client,
    segment_root_sha256,
)
from cmp.modules.identity_access.domain.authorization import AuthorizationDecision
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.shared.domain.revisions import RevisionCreated

metadata = sa.MetaData()


class RlsContext(Protocol):
    def bind_authorization(
        self,
        session: Session,
        context: SecurityContext,
        decision: AuthorizationDecision,
    ) -> None: ...


event_table = sa.Table(
    "event",
    metadata,
    sa.Column("id", sa.Uuid(), primary_key=True),
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("sequence_no", sa.BigInteger(), nullable=False),
    sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("actor_type", sa.String(16), nullable=False),
    sa.Column("actor_id", sa.Uuid(), nullable=False),
    sa.Column("action", sa.String(150), nullable=False),
    sa.Column("target_type", sa.String(150), nullable=False),
    sa.Column("target_id", sa.Uuid(), nullable=True),
    sa.Column("outcome", sa.String(16), nullable=False),
    sa.Column("request_id", sa.Uuid(), nullable=False),
    sa.Column("trace_id", sa.String(255), nullable=False),
    sa.Column("ip_or_client", sa.String(32), nullable=False),
    sa.Column("reason", sa.Text(), nullable=False),
    sa.Column("previous_hash", sa.CHAR(64), nullable=False),
    sa.Column("event_hash", sa.CHAR(64), nullable=False),
    schema="audit",
)

segment_root_table = sa.Table(
    "segment_root",
    metadata,
    sa.Column("id", sa.Uuid(), primary_key=True),
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("segment_no", sa.BigInteger(), nullable=False),
    sa.Column("first_sequence_no", sa.BigInteger(), nullable=False),
    sa.Column("last_sequence_no", sa.BigInteger(), nullable=False),
    sa.Column("event_count", sa.Integer(), nullable=False),
    sa.Column("first_event_hash", sa.CHAR(64), nullable=False),
    sa.Column("last_event_hash", sa.CHAR(64), nullable=False),
    sa.Column("previous_root_hash", sa.CHAR(64), nullable=False),
    sa.Column("root_hash", sa.CHAR(64), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("created_by", sa.Uuid(), nullable=False),
    sa.Column("request_id", sa.Uuid(), nullable=False),
    sa.Column("trace_id", sa.String(255), nullable=False),
    schema="audit",
)


def _event(row: Any) -> AuditEvent:
    return AuditEvent(
        id=row.id,
        scope=AuditScope(row.organization_id, row.project_id),
        sequence_no=row.sequence_no,
        occurred_at=row.occurred_at,
        recorded_at=row.recorded_at,
        actor_type=AuditActorType(row.actor_type),
        actor_id=row.actor_id,
        action=row.action,
        target_type=row.target_type,
        target_id=row.target_id,
        outcome=AuditOutcome(row.outcome),
        request_id=row.request_id,
        trace_id=row.trace_id,
        ip_or_client=row.ip_or_client,
        reason=row.reason,
        previous_hash=row.previous_hash,
        event_hash=row.event_hash,
    )


def _root(row: Any) -> AuditSegmentRoot:
    return AuditSegmentRoot(
        id=row.id,
        scope=AuditScope(row.organization_id, row.project_id),
        segment_no=row.segment_no,
        first_sequence_no=row.first_sequence_no,
        last_sequence_no=row.last_sequence_no,
        event_count=row.event_count,
        first_event_hash=row.first_event_hash,
        last_event_hash=row.last_event_hash,
        previous_root_hash=row.previous_root_hash,
        root_hash=row.root_hash,
        created_at=row.created_at,
        created_by=row.created_by,
        request_id=row.request_id,
        trace_id=row.trace_id,
    )


class SqlAlchemyAuditWriter:
    """Append one event inside the owning command's existing transaction."""

    def append(self, session: Session, draft: AuditEventDraft) -> AuditEvent:
        row = session.execute(
            sa.insert(event_table)
            .values(
                id=draft.id,
                organization_id=draft.scope.organization_id,
                project_id=draft.scope.project_id,
                occurred_at=draft.occurred_at,
                actor_type=draft.actor_type.value,
                actor_id=draft.actor_id,
                action=draft.action,
                target_type=draft.target_type,
                target_id=draft.target_id,
                outcome=draft.outcome.value,
                request_id=draft.request_id,
                trace_id=draft.trace_id,
                ip_or_client=draft.ip_or_client,
                reason=draft.reason,
            )
            .returning(*event_table.c)
        ).one()
        event = _event(row)
        if event.event_hash != event_sha256(event):
            raise AuditConflict("PostgreSQL and application audit hashes differ")
        return event


class SqlAlchemyRevisionAuditHook:
    """Translate a T-06 immutable revision fact into the same transaction's audit chain."""

    # A DMA output specializes the ordinary revision Activity before its audit event is
    # appended.  The common output adapter uses this marker only when a transaction-local
    # specialization callback is present; ordinary revision writes keep their existing order.
    after_output_specializer = True

    def __init__(
        self,
        *,
        writer: SqlAlchemyAuditWriter | None = None,
        id_factory: Callable[[], UUID] = uuid4,
    ) -> None:
        self._writer = writer or SqlAlchemyAuditWriter()
        self._id_factory = id_factory

    def __call__(self, session: Session, event: RevisionCreated) -> None:
        record = event.revision
        principal_type = session.scalar(
            sa.text("SELECT current_setting('cmp.principal_type', true)")
        )
        actor_type = AuditActorType(principal_type)
        operation = "create" if record.revision_no == 1 else "revise"
        self._writer.append(
            session,
            AuditEventDraft(
                id=self._id_factory(),
                scope=AuditScope(
                    record.scope.organization_id,
                    record.scope.project_id,
                ),
                occurred_at=record.created_at,
                actor_type=actor_type,
                actor_id=record.created_by,
                action=f"{record.aggregate_type}.revision.{operation}",
                target_type=f"{record.aggregate_type}.revision",
                target_id=record.revision_id,
                outcome=AuditOutcome.SUCCESS,
                request_id=record.request_id,
                trace_id=record.trace_id,
                ip_or_client=redact_ip_or_client(None),
                reason=record.change_reason,
            ),
        )


class SqlAlchemyAuditRepository:
    def __init__(
        self,
        *,
        session_factory: Callable[[], Session],
        rls_context: RlsContext,
        id_factory: Callable[[], UUID] = uuid4,
    ) -> None:
        self._session_factory = session_factory
        self._rls = rls_context
        self._id_factory = id_factory

    @contextmanager
    def _transaction(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
    ) -> Iterator[Session]:
        with self._session_factory() as session, session.begin():
            self._rls.bind_authorization(session, context, decision)
            yield session

    def query_events(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        query: AuditEventQuery,
    ) -> AuditEventPage:
        statement = sa.select(event_table).where(event_table.c.sequence_no > query.after_sequence)
        if query.action is not None:
            statement = statement.where(event_table.c.action == query.action)
        if query.actor_id is not None:
            statement = statement.where(event_table.c.actor_id == query.actor_id)
        if query.target_type is not None:
            statement = statement.where(event_table.c.target_type == query.target_type)
        if query.target_id is not None:
            statement = statement.where(event_table.c.target_id == query.target_id)
        if query.outcome is not None:
            statement = statement.where(event_table.c.outcome == query.outcome.value)
        if query.occurred_from is not None:
            statement = statement.where(event_table.c.occurred_at >= query.occurred_from)
        if query.occurred_to is not None:
            statement = statement.where(event_table.c.occurred_at <= query.occurred_to)
        statement = statement.order_by(event_table.c.sequence_no).limit(query.limit + 1)
        with self._transaction(context, decision) as session:
            rows = session.execute(statement).all()
        values = tuple(_event(row) for row in rows[: query.limit])
        next_after = values[-1].sequence_no if len(rows) > query.limit else None
        return AuditEventPage(values, next_after)

    def load_chain(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
    ) -> tuple[tuple[AuditEvent, ...], tuple[AuditSegmentRoot, ...]]:
        with self._transaction(context, decision) as session:
            events = tuple(
                _event(row)
                for row in session.execute(
                    sa.select(event_table).order_by(event_table.c.sequence_no)
                ).all()
            )
            roots = tuple(
                _root(row)
                for row in session.execute(
                    sa.select(segment_root_table).order_by(segment_root_table.c.segment_no)
                ).all()
            )
        return events, roots

    def export_range(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        from_sequence: int,
        to_sequence: int,
    ) -> tuple[str, tuple[AuditEvent, ...], tuple[AuditSegmentRoot, ...]]:
        with self._transaction(context, decision) as session:
            anchor = session.scalar(
                sa.select(event_table.c.event_hash).where(
                    event_table.c.sequence_no == from_sequence - 1
                )
            )
            events = tuple(
                _event(row)
                for row in session.execute(
                    sa.select(event_table)
                    .where(event_table.c.sequence_no.between(from_sequence, to_sequence))
                    .order_by(event_table.c.sequence_no)
                ).all()
            )
            roots = tuple(
                _root(row)
                for row in session.execute(
                    sa.select(segment_root_table)
                    .where(
                        segment_root_table.c.last_sequence_no >= from_sequence,
                        segment_root_table.c.first_sequence_no <= to_sequence,
                    )
                    .order_by(segment_root_table.c.segment_no)
                ).all()
            )
        return str(anchor or GENESIS_HASH), events, roots

    def seal_next(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        maximum_events: int,
    ) -> AuditSegmentRoot | None:
        with self._transaction(context, decision) as session:
            prior_last = session.scalar(
                sa.select(sa.func.max(segment_root_table.c.last_sequence_no))
            )
            first = int(prior_last or 0) + 1
            rows = session.execute(
                sa.select(event_table.c.sequence_no)
                .where(event_table.c.sequence_no >= first)
                .order_by(event_table.c.sequence_no)
                .limit(maximum_events)
            ).all()
            if not rows:
                return None
            last = int(rows[-1].sequence_no)
            row = session.execute(
                sa.insert(segment_root_table)
                .values(
                    id=self._id_factory(),
                    organization_id=context.organization_id,
                    project_id=context.project_id,
                    first_sequence_no=first,
                    last_sequence_no=last,
                    created_by=context.principal.id,
                    request_id=context.request_id,
                    trace_id=context.trace_id,
                )
                .returning(*segment_root_table.c)
            ).one()
            root = _root(row)
            if root.root_hash != segment_root_sha256(root):
                raise AuditConflict("PostgreSQL and application segment root hashes differ")
            return root

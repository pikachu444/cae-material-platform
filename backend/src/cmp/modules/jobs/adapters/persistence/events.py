"""RLS-bound PostgreSQL transactional outbox, delivery lease, and inbox dedup."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol, cast
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine import RowMapping
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.jobs.domain.events import (
    ClaimedCloudEvent,
    CloudEventDraft,
    CloudEventRecord,
    DeliveryState,
    EventConflict,
    EventLeaseLost,
    InboxReceipt,
)

metadata = sa.MetaData()
uuid_type = postgresql.UUID(as_uuid=True)

outbox_event_table = sa.Table(
    "outbox_event",
    metadata,
    sa.Column("organization_id", uuid_type),
    sa.Column("project_id", uuid_type),
    sa.Column("classification", sa.String()),
    sa.Column("id", uuid_type),
    sa.Column("aggregate_type", sa.String()),
    sa.Column("aggregate_id", uuid_type),
    sa.Column("sequence_no", sa.BigInteger()),
    sa.Column("event_type", sa.String()),
    sa.Column("source", sa.String()),
    sa.Column("subject", sa.String()),
    sa.Column("data_schema", sa.String()),
    sa.Column("data", postgresql.JSONB()),
    sa.Column("data_sha256", sa.String()),
    sa.Column("occurred_at", sa.DateTime(timezone=True)),
    sa.Column("recorded_at", sa.DateTime(timezone=True)),
    sa.Column("recorded_by", uuid_type),
    sa.Column("request_id", uuid_type),
    sa.Column("trace_id", sa.String()),
    sa.Column("deduplication_key", sa.String()),
    schema="events",
)

outbox_delivery_table = sa.Table(
    "outbox_delivery",
    metadata,
    sa.Column("organization_id", uuid_type),
    sa.Column("project_id", uuid_type),
    sa.Column("classification", sa.String()),
    sa.Column("event_id", uuid_type),
    sa.Column("state", sa.String()),
    sa.Column("attempt_count", sa.Integer()),
    sa.Column("available_at", sa.DateTime(timezone=True)),
    sa.Column("lease_token", uuid_type),
    sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
    sa.Column("published_at", sa.DateTime(timezone=True)),
    sa.Column("last_failure_code", sa.String()),
    sa.Column("updated_at", sa.DateTime(timezone=True)),
    schema="events",
)

consumer_inbox_table = sa.Table(
    "consumer_inbox",
    metadata,
    sa.Column("organization_id", uuid_type),
    sa.Column("project_id", uuid_type),
    sa.Column("classification", sa.String()),
    sa.Column("consumer_name", sa.String()),
    sa.Column("event_id", uuid_type),
    sa.Column("event_type", sa.String()),
    sa.Column("data_sha256", sa.String()),
    sa.Column("outcome", sa.String()),
    sa.Column("side_effect_key", sa.String()),
    sa.Column("received_at", sa.DateTime(timezone=True)),
    sa.Column("processed_at", sa.DateTime(timezone=True)),
    sa.Column("processed_by", uuid_type),
    sa.Column("trace_id", sa.String()),
    schema="events",
)


class RlsContext(Protocol):
    def bind_authorization(
        self,
        session: Session,
        context: SecurityContext,
        decision: AuthorizationDecision,
    ) -> None: ...


def _draft(row: RowMapping) -> CloudEventDraft:
    return CloudEventDraft(
        organization_id=cast(UUID, row["organization_id"]),
        project_id=cast(UUID, row["project_id"]),
        classification=DataClassification(str(row["classification"])),
        aggregate_type=str(row["aggregate_type"]),
        aggregate_id=cast(UUID, row["aggregate_id"]),
        event_type=str(row["event_type"]),
        source=str(row["source"]),
        subject=str(row["subject"]),
        data_schema=str(row["data_schema"]),
        data=cast(object, row["data"]),
        occurred_at=row["occurred_at"],
        recorded_by=cast(UUID, row["recorded_by"]),
        request_id=cast(UUID, row["request_id"]),
        trace_id=str(row["trace_id"]),
        deduplication_key=str(row["deduplication_key"]),
    )


def _event(row: RowMapping) -> CloudEventRecord:
    draft = _draft(row)
    return CloudEventRecord(
        id=cast(UUID, row["id"]),
        sequence_no=int(row["sequence_no"]),
        draft=draft,
        recorded_at=row["recorded_at"],
    )


@dataclass(frozen=True, slots=True)
class AppendEventResult:
    event: CloudEventRecord
    replayed: bool


class SqlAlchemyOutboxWriter:
    """Append from an existing domain transaction or from an RLS-bound service call."""

    def __init__(self, *, id_factory: Callable[[], UUID] = uuid4) -> None:
        self._id_factory = id_factory

    @staticmethod
    def _same(existing: CloudEventRecord, draft: CloudEventDraft) -> bool:
        left = existing.draft
        return (
            left.organization_id == draft.organization_id
            and left.project_id == draft.project_id
            and left.classification is draft.classification
            and left.aggregate_type == draft.aggregate_type
            and left.aggregate_id == draft.aggregate_id
            and left.event_type == draft.event_type
            and left.source == draft.source
            and left.subject == draft.subject
            and left.data_schema == draft.data_schema
            and left.data_sha256 == draft.data_sha256
            and left.occurred_at == draft.occurred_at
            and left.recorded_by == draft.recorded_by
            and left.request_id == draft.request_id
            and left.trace_id == draft.trace_id
        )

    def append(
        self,
        session: Session,
        draft: CloudEventDraft,
        *,
        recorded_at: datetime,
    ) -> AppendEventResult:
        existing_row = (
            session.execute(
                sa.select(outbox_event_table).where(
                    outbox_event_table.c.organization_id == draft.organization_id,
                    outbox_event_table.c.project_id == draft.project_id,
                    outbox_event_table.c.deduplication_key == draft.deduplication_key,
                )
            )
            .mappings()
            .one_or_none()
        )
        if existing_row is not None:
            existing = _event(existing_row)
            if not self._same(existing, draft):
                raise EventConflict("outbox deduplication key was reused with different content")
            return AppendEventResult(existing, True)
        lock_key = (
            f"{draft.organization_id}:{draft.project_id}:"
            f"{draft.aggregate_type}:{draft.aggregate_id}"
        )
        session.execute(
            sa.text("SELECT pg_advisory_xact_lock(hashtextextended(:lock_key, 0))"),
            {"lock_key": lock_key},
        )
        existing_row = (
            session.execute(
                sa.select(outbox_event_table).where(
                    outbox_event_table.c.organization_id == draft.organization_id,
                    outbox_event_table.c.project_id == draft.project_id,
                    outbox_event_table.c.deduplication_key == draft.deduplication_key,
                )
            )
            .mappings()
            .one_or_none()
        )
        if existing_row is not None:
            existing = _event(existing_row)
            if not self._same(existing, draft):
                raise EventConflict("outbox deduplication key was reused with different content")
            return AppendEventResult(existing, True)
        sequence_no = (
            int(
                session.scalar(
                    sa.select(
                        sa.func.coalesce(sa.func.max(outbox_event_table.c.sequence_no), 0)
                    ).where(
                        outbox_event_table.c.organization_id == draft.organization_id,
                        outbox_event_table.c.project_id == draft.project_id,
                        outbox_event_table.c.aggregate_type == draft.aggregate_type,
                        outbox_event_table.c.aggregate_id == draft.aggregate_id,
                    )
                )
                or 0
            )
            + 1
        )
        event_id = self._id_factory()
        values = {
            "organization_id": draft.organization_id,
            "project_id": draft.project_id,
            "classification": draft.classification.value,
            "id": event_id,
            "aggregate_type": draft.aggregate_type,
            "aggregate_id": draft.aggregate_id,
            "sequence_no": sequence_no,
            "event_type": draft.event_type,
            "source": draft.source,
            "subject": draft.subject,
            "data_schema": draft.data_schema,
            "data": draft.data,
            "data_sha256": draft.data_sha256,
            "occurred_at": draft.occurred_at,
            "recorded_at": recorded_at,
            "recorded_by": draft.recorded_by,
            "request_id": draft.request_id,
            "trace_id": draft.trace_id,
            "deduplication_key": draft.deduplication_key,
        }
        try:
            row = (
                session.execute(
                    sa.insert(outbox_event_table).values(**values).returning(outbox_event_table)
                )
                .mappings()
                .one()
            )
            session.execute(
                sa.insert(outbox_delivery_table).values(
                    organization_id=draft.organization_id,
                    project_id=draft.project_id,
                    classification=draft.classification.value,
                    event_id=event_id,
                    state=DeliveryState.PENDING.value,
                    attempt_count=0,
                    available_at=recorded_at,
                    lease_token=None,
                    lease_expires_at=None,
                    published_at=None,
                    last_failure_code=None,
                    updated_at=recorded_at,
                )
            )
        except IntegrityError as error:
            raise EventConflict("database rejected immutable outbox event") from error
        return AppendEventResult(_event(row), False)


class SqlAlchemyOutboxRepository:
    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session],
        rls_context: RlsContext,
        token_factory: Callable[[], UUID] = uuid4,
    ) -> None:
        self._sessions = session_factory
        self._rls = rls_context
        self._token_factory = token_factory

    def _bind(
        self,
        session: Session,
        context: SecurityContext,
        decision: AuthorizationDecision,
    ) -> None:
        self._rls.bind_authorization(session, context, decision)

    def claim(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        limit: int,
        lease_duration: timedelta,
        now: datetime,
    ) -> tuple[ClaimedCloudEvent, ...]:
        query = sa.text(
            """
            SELECT event.*, delivery.attempt_count
            FROM events.outbox_delivery AS delivery
            JOIN events.outbox_event AS event
              ON event.organization_id = delivery.organization_id
             AND event.project_id = delivery.project_id
             AND event.classification = delivery.classification
             AND event.id = delivery.event_id
            WHERE delivery.organization_id = :organization_id
              AND delivery.project_id = :project_id
              AND (
                (delivery.state = 'pending' AND delivery.available_at <= :now)
                OR (delivery.state = 'claimed' AND delivery.lease_expires_at <= :now)
              )
              AND NOT EXISTS (
                SELECT 1
                FROM events.outbox_event AS prior_event
                JOIN events.outbox_delivery AS prior_delivery
                  ON prior_delivery.organization_id = prior_event.organization_id
                 AND prior_delivery.project_id = prior_event.project_id
                 AND prior_delivery.classification = prior_event.classification
                 AND prior_delivery.event_id = prior_event.id
                WHERE prior_event.organization_id = event.organization_id
                  AND prior_event.project_id = event.project_id
                  AND prior_event.aggregate_type = event.aggregate_type
                  AND prior_event.aggregate_id = event.aggregate_id
                  AND prior_event.sequence_no < event.sequence_no
                  AND prior_delivery.state <> 'published'
              )
            ORDER BY event.occurred_at, event.id
            FOR UPDATE OF delivery SKIP LOCKED
            LIMIT :limit
            """
        )
        with self._sessions() as session, session.begin():
            self._bind(session, context, decision)
            rows = (
                session.execute(
                    query,
                    {
                        "organization_id": context.organization_id,
                        "project_id": context.project_id,
                        "now": now,
                        "limit": limit,
                    },
                )
                .mappings()
                .all()
            )
            claimed: list[ClaimedCloudEvent] = []
            for row in rows:
                token = self._token_factory()
                expires_at = now + lease_duration
                attempt_count = int(row["attempt_count"]) + 1
                updated = session.execute(
                    sa.update(outbox_delivery_table)
                    .where(
                        outbox_delivery_table.c.organization_id == context.organization_id,
                        outbox_delivery_table.c.project_id == context.project_id,
                        outbox_delivery_table.c.event_id == row["id"],
                    )
                    .values(
                        state=DeliveryState.CLAIMED.value,
                        attempt_count=attempt_count,
                        lease_token=token,
                        lease_expires_at=expires_at,
                        published_at=None,
                        updated_at=now,
                    )
                )
                if getattr(updated, "rowcount", None) != 1:
                    raise EventLeaseLost("claimed outbox row disappeared")
                claimed.append(ClaimedCloudEvent(_event(row), token, expires_at, attempt_count))
            return tuple(claimed)

    def published(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        event_id: UUID,
        lease_token: UUID,
        published_at: datetime,
    ) -> None:
        with self._sessions() as session, session.begin():
            self._bind(session, context, decision)
            updated = session.execute(
                sa.update(outbox_delivery_table)
                .where(
                    outbox_delivery_table.c.organization_id == context.organization_id,
                    outbox_delivery_table.c.project_id == context.project_id,
                    outbox_delivery_table.c.event_id == event_id,
                    outbox_delivery_table.c.state == DeliveryState.CLAIMED.value,
                    outbox_delivery_table.c.lease_token == lease_token,
                    outbox_delivery_table.c.lease_expires_at >= published_at,
                )
                .values(
                    state=DeliveryState.PUBLISHED.value,
                    lease_token=None,
                    lease_expires_at=None,
                    published_at=published_at,
                    last_failure_code=None,
                    updated_at=published_at,
                )
            )
            if getattr(updated, "rowcount", None) != 1:
                raise EventLeaseLost("outbox publish fencing token is stale")

    def failed(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        event_id: UUID,
        lease_token: UUID,
        failure_code: str,
        retry_at: datetime,
        failed_at: datetime,
        maximum_attempts: int,
    ) -> bool:
        with self._sessions() as session, session.begin():
            self._bind(session, context, decision)
            row = (
                session.execute(
                    sa.select(outbox_delivery_table)
                    .where(
                        outbox_delivery_table.c.organization_id == context.organization_id,
                        outbox_delivery_table.c.project_id == context.project_id,
                        outbox_delivery_table.c.event_id == event_id,
                        outbox_delivery_table.c.state == DeliveryState.CLAIMED.value,
                        outbox_delivery_table.c.lease_token == lease_token,
                        outbox_delivery_table.c.lease_expires_at >= failed_at,
                    )
                    .with_for_update()
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise EventLeaseLost("outbox failure fencing token is stale")
            poison = int(row["attempt_count"]) >= maximum_attempts
            session.execute(
                sa.update(outbox_delivery_table)
                .where(
                    outbox_delivery_table.c.organization_id == context.organization_id,
                    outbox_delivery_table.c.project_id == context.project_id,
                    outbox_delivery_table.c.event_id == event_id,
                    outbox_delivery_table.c.lease_token == lease_token,
                )
                .values(
                    state=(DeliveryState.POISON if poison else DeliveryState.PENDING).value,
                    available_at=(failed_at if poison else retry_at),
                    lease_token=None,
                    lease_expires_at=None,
                    published_at=None,
                    last_failure_code=failure_code,
                    updated_at=failed_at,
                )
            )
            return poison


class SqlAlchemyInboxDeduplicator:
    """Insert a receipt inside the consumer's own side-effect transaction."""

    @staticmethod
    def record(
        session: Session,
        *,
        context: SecurityContext,
        classification: str,
        receipt: InboxReceipt,
    ) -> bool:
        inserted = session.execute(
            postgresql.insert(consumer_inbox_table)
            .values(
                organization_id=context.organization_id,
                project_id=context.project_id,
                classification=classification,
                consumer_name=receipt.consumer_name,
                event_id=receipt.event_id,
                event_type=receipt.event_type,
                data_sha256=receipt.data_sha256,
                outcome=receipt.outcome.value,
                side_effect_key=receipt.side_effect_key,
                received_at=receipt.received_at,
                processed_at=receipt.processed_at,
                processed_by=context.principal.id,
                trace_id=context.trace_id,
            )
            .on_conflict_do_nothing()
            .returning(consumer_inbox_table.c.event_id)
        ).scalar_one_or_none()
        return inserted is not None


__all__ = [
    "AppendEventResult",
    "SqlAlchemyInboxDeduplicator",
    "SqlAlchemyOutboxRepository",
    "SqlAlchemyOutboxWriter",
    "consumer_inbox_table",
    "outbox_delivery_table",
    "outbox_event_table",
]

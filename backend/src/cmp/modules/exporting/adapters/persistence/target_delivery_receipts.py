"""Atomic UXC-06C2 receipt/outbox hook for immutable native cards."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any, Protocol, cast
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from cmp.modules.exporting.application.target_delivery import (
    DeliveryReceipt,
    DeliveryReceiptRecorder,
    TargetDeliveryDuplicate,
)
from cmp.modules.exporting.application.target_preview import TargetPreview
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.jobs.adapters.persistence.events import SqlAlchemyOutboxWriter, outbox_event_table
from cmp.modules.jobs.domain.events import CloudEventDraft, EventConflict
from cmp.shared.domain.revisions import RevisionCreated

metadata = sa.MetaData()
delivery_receipt_table = sa.Table(
    "solver_card_delivery_receipt",
    metadata,
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("receipt_id", sa.Uuid(), nullable=False),
    sa.Column("delivery_identity", sa.CHAR(64), nullable=False),
    sa.Column("solver_card_id", sa.Uuid(), nullable=False),
    sa.Column("solver_card_revision_id", sa.Uuid(), nullable=False),
    sa.Column("filename", sa.String(255), nullable=False),
    sa.Column("native_sha256", sa.CHAR(64), nullable=False),
    sa.Column("mapping_report_sha256", sa.CHAR(64), nullable=False),
    sa.Column("mapping_statuses", postgresql.JSONB(), nullable=False),
    sa.Column("source", postgresql.JSONB(), nullable=False),
    sa.Column("target", postgresql.JSONB(), nullable=False),
    sa.Column("outbox_event_id", sa.Uuid(), nullable=False),
    sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("recorded_by", sa.Uuid(), nullable=False),
    schema="exporting",
)


class RlsContext(Protocol):
    def bind_authorization(
        self,
        session: Session,
        context: SecurityContext,
        decision: AuthorizationDecision,
    ) -> None: ...


def _receipt(row: Any) -> DeliveryReceipt:
    return DeliveryReceipt(
        receipt_id=cast(UUID, row["receipt_id"]),
        delivery_identity=str(row["delivery_identity"]),
        solver_card_id=cast(UUID, row["solver_card_id"]),
        solver_card_revision_id=cast(UUID, row["solver_card_revision_id"]),
        filename=str(row["filename"]),
        native_sha256=str(row["native_sha256"]),
        mapping_report_sha256=str(row["mapping_report_sha256"]),
        mapping_statuses=tuple(str(value) for value in row["mapping_statuses"]),
        source={str(key): str(value) for key, value in row["source"].items()},
        target={str(key): str(value) for key, value in row["target"].items()},
        occurred_at=row["occurred_at"].isoformat(),
        recorded_by=cast(UUID, row["recorded_by"]),
    )


def _is_expected_delivery_duplicate(error: IntegrityError) -> bool:
    diagnostic = getattr(error.orig, "diag", None)
    constraint = str(getattr(diagnostic, "constraint_name", ""))
    if getattr(error.orig, "sqlstate", None) != "23505":
        return False
    table = getattr(diagnostic, "table_name", None)
    return (
        table == delivery_receipt_table.name and "delivery_identity" in constraint
    ) or (
        table == outbox_event_table.name and constraint == "uq_events_outbox_deduplication"
    )


class SqlTargetDeliveryReceiptRecorder(DeliveryReceiptRecorder):
    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session],
        rls_context: RlsContext,
        writer: SqlAlchemyOutboxWriter | None = None,
    ) -> None:
        self._sessions = session_factory
        self._rls = rls_context
        self._writer = writer or SqlAlchemyOutboxWriter()

    @contextmanager
    def _session(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
    ) -> Iterator[Session]:
        with self._sessions() as session, session.begin():
            self._rls.bind_authorization(session, context, decision)
            yield session

    def find_by_delivery_identity(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        delivery_identity: str,
    ) -> DeliveryReceipt | None:
        with self._session(context, decision) as session:
            row = (
                session.execute(
                    sa.select(delivery_receipt_table).where(
                        delivery_receipt_table.c.organization_id == context.organization_id,
                        delivery_receipt_table.c.project_id == context.project_id,
                        delivery_receipt_table.c.delivery_identity == delivery_identity,
                    )
                )
                .mappings()
                .one_or_none()
            )
        return None if row is None else _receipt(row)

    def get(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        receipt_id: UUID,
    ) -> DeliveryReceipt | None:
        with self._session(context, decision) as session:
            row = (
                session.execute(
                    sa.select(delivery_receipt_table).where(
                        delivery_receipt_table.c.organization_id == context.organization_id,
                        delivery_receipt_table.c.project_id == context.project_id,
                        delivery_receipt_table.c.receipt_id == receipt_id,
                    )
                )
                .mappings()
                .one_or_none()
            )
        return None if row is None else _receipt(row)

    def hook_for(
        self, *, context: SecurityContext, preview: TargetPreview, receipt_id: UUID
    ) -> Callable[[object, RevisionCreated], None]:
        def record(session: object, created: RevisionCreated) -> None:
            if not isinstance(session, Session):
                raise RuntimeError("target delivery receipt requires a SQL transaction")
            revision = created.revision
            data = {
                "receipt_id": str(receipt_id),
                "delivery_identity": preview.preview_identity,
                "filename": preview.filename,
                "native_sha256": preview.native_sha256,
                "mapping_report_sha256": preview.mapping_report_sha256,
                "mapping_statuses": [
                    item["status"]
                    for item in cast(list[dict[str, object]], preview.mapping["items"])
                ],
                "source": preview.source,
                "target": preview.target,
                "solver_card_id": str(revision.aggregate_id),
                "solver_card_revision_id": str(revision.revision_id),
                "actor_id": str(context.principal.id),
                "occurred_at": revision.created_at.isoformat(),
            }
            try:
                event = self._writer.append(
                    session,
                    CloudEventDraft(
                        organization_id=context.organization_id,
                        project_id=context.project_id,
                        classification=DataClassification(revision.scope.classification),
                        aggregate_type="exporting.solver_card_delivery",
                        aggregate_id=receipt_id,
                        event_type="io.cmp.exporting.solver-card-delivered.v1",
                        source="urn:cmp:module:exporting",
                        subject=f"solver-card-deliveries/{receipt_id}",
                        data_schema="urn:cmp:schema:event:solver-card-delivered:1.0.0",
                        data=data,
                        occurred_at=revision.created_at,
                        recorded_by=context.principal.id,
                        request_id=context.request_id,
                        trace_id=context.trace_id,
                        deduplication_key=f"solver-card-delivery:{preview.preview_identity}",
                    ),
                    recorded_at=revision.created_at,
                ).event
                session.execute(
                    sa.insert(delivery_receipt_table).values(
                        organization_id=context.organization_id,
                        project_id=context.project_id,
                        classification=revision.scope.classification,
                        receipt_id=receipt_id,
                        delivery_identity=preview.preview_identity,
                        solver_card_id=revision.aggregate_id,
                        solver_card_revision_id=revision.revision_id,
                        filename=preview.filename,
                        native_sha256=preview.native_sha256,
                        mapping_report_sha256=preview.mapping_report_sha256,
                        mapping_statuses=data["mapping_statuses"],
                        source=preview.source,
                        target=preview.target,
                        outbox_event_id=event.id,
                        occurred_at=revision.created_at,
                        recorded_by=context.principal.id,
                    )
                )
            except IntegrityError as error:
                if _is_expected_delivery_duplicate(error):
                    raise TargetDeliveryDuplicate(
                        "another transaction already recorded this delivery identity"
                    ) from error
                raise
            except EventConflict as error:
                cause = error.__cause__
                if isinstance(cause, IntegrityError) and _is_expected_delivery_duplicate(cause):
                    raise TargetDeliveryDuplicate(
                        "another transaction already recorded this delivery identity"
                    ) from error
                raise

        return record

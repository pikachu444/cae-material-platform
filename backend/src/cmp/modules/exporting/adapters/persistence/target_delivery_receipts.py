"""Atomic UXC-06C2 receipt/outbox hook for immutable native cards."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Protocol, cast
from uuid import NAMESPACE_URL, UUID, uuid5

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from cmp.modules.exporting.application.target_delivery import (
    DeliveryReceipt,
    DeliveryReceiptRecorder,
    TargetDeliveryConflict,
    TargetDeliveryDuplicate,
)
from cmp.modules.exporting.application.target_preview import TargetPreview
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
)
from cmp.modules.identity_access.domain.security import SecurityContext
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
domain_record_identity_binding_table = sa.Table(
    "domain_record_identity_binding",
    metadata,
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("domain_kind", sa.String(32), nullable=False),
    sa.Column("domain_object_id", sa.Uuid(), nullable=False),
    sa.Column("domain_revision_id", sa.Uuid(), nullable=False),
    sa.Column("record_id", sa.Uuid(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("created_by", sa.Uuid(), nullable=False),
    sa.Column("request_id", sa.Uuid(), nullable=False),
    sa.Column("trace_id", sa.String(255), nullable=False),
    schema="catalog",
)
catalog_record_table = sa.Table(
    "catalog_record",
    metadata,
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("current_revision_id", sa.Uuid(), nullable=False),
    schema="catalog",
)
domain_record_binding_table = sa.Table(
    "domain_record_binding",
    metadata,
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("record_id", sa.Uuid(), nullable=False),
    sa.Column("record_revision_id", sa.Uuid(), nullable=False),
    sa.Column("domain_kind", sa.String(32), nullable=False),
    sa.Column("domain_object_id", sa.Uuid(), nullable=False),
    sa.Column("domain_revision_id", sa.Uuid(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("created_by", sa.Uuid(), nullable=False),
    sa.Column("request_id", sa.Uuid(), nullable=False),
    sa.Column("trace_id", sa.String(255), nullable=False),
    schema="catalog",
)
neutral_solver_card_revision_table = sa.Table(
    "neutral_solver_card_revision",
    metadata,
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("aggregate_id", sa.Uuid(), nullable=False),
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("neutral_material_id", sa.Uuid(), nullable=False),
    sa.Column("neutral_material_revision_id", sa.Uuid(), nullable=False),
    schema="exporting",
)


class RlsContext(Protocol):
    def bind_authorization(
        self,
        session: Session,
        context: SecurityContext,
        decision: AuthorizationDecision,
    ) -> None: ...


class OutboxWriter(Protocol):
    """Composition-bound outbox port; exporting owns no Job adapter imports."""

    def append(
        self,
        session: Session,
        draft: CloudEventDraft,
        *,
        recorded_at: datetime,
    ) -> Any: ...


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
        table == "outbox_event" and constraint == "uq_events_outbox_deduplication"
    )


class SqlTargetDeliveryReceiptRecorder(DeliveryReceiptRecorder):
    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session],
        rls_context: RlsContext,
        writer: OutboxWriter,
    ) -> None:
        self._sessions = session_factory
        self._rls = rls_context
        self._writer = writer

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
            if getattr(revision, "aggregate_type", None) == "exporting.neutral_solver_card":
                try:
                    neutral_id = UUID(preview.source["neutral_material_id"])
                    neutral_revision_id = UUID(preview.source["neutral_material_revision_id"])
                except (KeyError, TypeError, ValueError) as error:
                    raise TargetDeliveryConflict(
                        "target delivery source is missing an exact Neutral Material revision"
                    ) from error
                card_source = session.execute(
                    sa.select(
                        neutral_solver_card_revision_table.c.neutral_material_id,
                        neutral_solver_card_revision_table.c.neutral_material_revision_id,
                    ).where(
                        neutral_solver_card_revision_table.c.organization_id
                        == context.organization_id,
                        neutral_solver_card_revision_table.c.project_id == context.project_id,
                        neutral_solver_card_revision_table.c.classification
                        == revision.scope.classification,
                        neutral_solver_card_revision_table.c.aggregate_id
                        == revision.aggregate_id,
                        neutral_solver_card_revision_table.c.id == revision.revision_id,
                    )
                ).mappings().one_or_none()
                if (
                    card_source is None
                    or card_source["neutral_material_id"] != neutral_id
                    or card_source["neutral_material_revision_id"] != neutral_revision_id
                ):
                    raise TargetDeliveryConflict(
                        "target delivery Solver Card source does not match its exact "
                        "Neutral revision"
                    )
                record_row = session.execute(
                    sa.select(
                        domain_record_binding_table.c.record_id,
                        domain_record_binding_table.c.record_revision_id,
                    )
                    .join(
                        catalog_record_table,
                        sa.and_(
                            catalog_record_table.c.organization_id
                            == domain_record_binding_table.c.organization_id,
                            catalog_record_table.c.project_id
                            == domain_record_binding_table.c.project_id,
                            catalog_record_table.c.classification
                            == domain_record_binding_table.c.classification,
                            catalog_record_table.c.id == domain_record_binding_table.c.record_id,
                            catalog_record_table.c.current_revision_id
                            == domain_record_binding_table.c.record_revision_id,
                        ),
                    )
                    .where(
                        domain_record_binding_table.c.organization_id == context.organization_id,
                        domain_record_binding_table.c.project_id == context.project_id,
                        domain_record_binding_table.c.classification
                        == revision.scope.classification,
                        domain_record_binding_table.c.domain_kind == "neutral_material",
                        domain_record_binding_table.c.domain_object_id == neutral_id,
                        domain_record_binding_table.c.domain_revision_id == neutral_revision_id,
                    )
                ).mappings().one_or_none()
                if record_row is None:
                    raise TargetDeliveryConflict(
                        "target delivery Neutral Material has no Materials Record binding"
                    )
                record_id = cast(UUID, record_row["record_id"])
                record_revision_id = cast(UUID, record_row["record_revision_id"])
                binding_key = (
                    f"{context.organization_id}:{context.project_id}:"
                    f"{revision.scope.classification}:neutral_solver_card:"
                    f"{revision.aggregate_id}:{revision.revision_id}"
                )
                binding_id = uuid5(NAMESPACE_URL, f"urn:cmp:{binding_key}")
                identity_values = {
                    "organization_id": context.organization_id,
                    "project_id": context.project_id,
                    "classification": revision.scope.classification,
                    "domain_kind": "neutral_solver_card",
                    "domain_object_id": revision.aggregate_id,
                    "domain_revision_id": revision.revision_id,
                    "record_id": record_id,
                    "created_at": revision.created_at,
                    "created_by": context.principal.id,
                    "request_id": context.request_id,
                    "trace_id": context.trace_id,
                }
                session.execute(
                    postgresql.insert(domain_record_identity_binding_table)
                    .values(**identity_values)
                    .on_conflict_do_nothing()
                )
                session.execute(
                    postgresql.insert(domain_record_binding_table)
                    .values(
                        id=binding_id,
                        record_revision_id=record_revision_id,
                        **identity_values,
                    )
                    .on_conflict_do_nothing()
                )
                persisted = session.execute(
                    sa.select(
                        domain_record_binding_table.c.record_id,
                        domain_record_binding_table.c.record_revision_id,
                        domain_record_binding_table.c.domain_kind,
                        domain_record_binding_table.c.domain_object_id,
                        domain_record_binding_table.c.domain_revision_id,
                    ).where(
                        domain_record_binding_table.c.id == binding_id,
                        domain_record_binding_table.c.organization_id == context.organization_id,
                        domain_record_binding_table.c.project_id == context.project_id,
                    )
                ).mappings().one_or_none()
                if (
                    persisted is None
                    or persisted["record_id"] != record_id
                    or persisted["record_revision_id"] != record_revision_id
                    or persisted["domain_kind"] != "neutral_solver_card"
                    or persisted["domain_object_id"] != revision.aggregate_id
                    or persisted["domain_revision_id"] != revision.revision_id
                ):
                    raise TargetDeliveryConflict(
                        "target delivery Solver Card binding does not match its Neutral Record"
                    )
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

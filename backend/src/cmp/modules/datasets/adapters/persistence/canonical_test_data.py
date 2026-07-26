"""PostgreSQL adapter for immutable canonical Test Data documents (T-52)."""

from __future__ import annotations

from collections.abc import Sequence
from contextlib import contextmanager
from datetime import date
from decimal import Decimal
from typing import Any, Protocol, cast
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from cmp.modules.datasets.application.canonical_test_data import (
    TEST_DATA_DOCUMENT_AGGREGATE_TYPE,
    CanonicalTestDataRepository,
    ExactRevisionRef,
    GovernedTestDataSource,
    TestDataChannelSummary,
    TestDataDocumentContent,
    TestDataDocumentSnapshot,
    test_data_content_canonical,
)
from cmp.modules.datasets.domain.canonical_test_data import (
    TestCondition,
    TestDataSource,
    TestExecutionMetadata,
    TestMaterialMetadata,
    TestSpecimenMetadata,
)
from cmp.modules.datasets.domain.governed_tabular import GovernedImportNotFound
from cmp.modules.identity_access.domain.authorization import AuthorizationDecision
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.shared.adapters.persistence.revisions import (
    SqlAlchemyRevisionStore,
    SqlRevisionHook,
    TypedRevisionTables,
)
from cmp.shared.application.revisions import RevisionStore
from cmp.shared.domain.revisions import RevisionDraft, RevisionRecord, TenantScope


class RlsContext(Protocol):
    def bind_authorization(
        self,
        session: Session,
        context: SecurityContext,
        decision: AuthorizationDecision,
    ) -> None: ...


metadata = sa.MetaData()
document_table = sa.Table(
    "test_data_document",
    metadata,
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("document_key", sa.String(200), nullable=False),
    sa.Column("current_revision_id", sa.Uuid(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("created_by", sa.Uuid(), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    schema="datasets",
)
document_revision_table = sa.Table(
    "test_data_document_revision",
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
    sa.Column("document_key", sa.String(200), nullable=False),
    sa.Column("maker", sa.String(200), nullable=False),
    sa.Column("grade", sa.String(200), nullable=False),
    sa.Column("lot_batch", sa.String(200), nullable=True),
    sa.Column("test_date", sa.Date(), nullable=False),
    sa.Column("operator_name", sa.String(200), nullable=False),
    sa.Column("laboratory", sa.String(200), nullable=False),
    sa.Column("test_method", sa.String(300), nullable=False),
    sa.Column("equipment_maker", sa.String(200), nullable=True),
    sa.Column("equipment_model", sa.String(200), nullable=True),
    sa.Column("specimen_key", sa.String(200), nullable=False),
    sa.Column("specimen_description", sa.Text(), nullable=True),
    sa.Column("source_file_name", sa.String(255), nullable=False),
    sa.Column("source_media_type", sa.String(255), nullable=False),
    sa.Column("source_sha256", sa.CHAR(64), nullable=False),
    sa.Column("canonical_artifact_id", sa.Uuid(), nullable=False),
    sa.Column("canonical_sha256", sa.CHAR(64), nullable=False),
    sa.Column("normalized_artifact_id", sa.Uuid(), nullable=False),
    sa.Column("normalized_sha256", sa.CHAR(64), nullable=False),
    sa.Column("point_count", sa.Integer(), nullable=False),
    # PostgreSQL's nullable JSONB check accepts SQL NULL or an object, never JSON null.
    # Keep absent governed proof as SQL NULL rather than serializing Python None to JSON null.
    sa.Column("governed_source", sa.JSON(none_as_null=True), nullable=True),
    schema="datasets",
)
condition_table = sa.Table(
    "test_data_condition",
    metadata,
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("document_id", sa.Uuid(), nullable=False),
    sa.Column("document_revision_id", sa.Uuid(), nullable=False),
    sa.Column("ordinal", sa.Integer(), nullable=False),
    sa.Column("condition_key", sa.String(128), nullable=False),
    sa.Column("quantity_semantics", sa.String(160), nullable=False),
    sa.Column("original_value", sa.Numeric(), nullable=False),
    sa.Column("original_unit_string", sa.String(64), nullable=False),
    sa.Column("normalized_value", sa.Numeric(), nullable=False),
    sa.Column("normalized_unit", sa.String(64), nullable=False),
    schema="datasets",
)
channel_table = sa.Table(
    "test_data_channel",
    metadata,
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("document_id", sa.Uuid(), nullable=False),
    sa.Column("document_revision_id", sa.Uuid(), nullable=False),
    sa.Column("ordinal", sa.Integer(), nullable=False),
    sa.Column("channel_key", sa.String(128), nullable=False),
    sa.Column("channel_name", sa.String(200), nullable=False),
    sa.Column("quantity_semantics", sa.String(160), nullable=False),
    sa.Column("axis_role", sa.String(32), nullable=False),
    sa.Column("original_unit_string", sa.String(64), nullable=False),
    sa.Column("normalized_unit", sa.String(64), nullable=False),
    sa.Column("normalization_scale", sa.Numeric(), nullable=False),
    sa.Column("normalization_offset", sa.Numeric(), nullable=False),
    sa.Column("point_count", sa.Integer(), nullable=False),
    sa.Column("missing_count", sa.Integer(), nullable=False),
    schema="datasets",
)


def _content_values(value: TestDataDocumentContent) -> dict[str, object]:
    return {
        "document_key": value.document_key,
        "maker": value.material.maker,
        "grade": value.material.grade,
        "lot_batch": value.material.lot_batch,
        "test_date": value.test.test_date,
        "operator_name": value.test.operator,
        "laboratory": value.test.laboratory,
        "test_method": value.test.method,
        "equipment_maker": value.test.equipment_maker,
        "equipment_model": value.test.equipment_model,
        "specimen_key": value.specimen.specimen_id,
        "specimen_description": value.specimen.description,
        "source_file_name": value.source.file_name,
        "source_media_type": value.source.media_type,
        "source_sha256": value.source.sha256,
        "canonical_artifact_id": value.canonical_artifact_id,
        "canonical_sha256": value.canonical_sha256,
        "normalized_artifact_id": value.normalized_artifact_id,
        "normalized_sha256": value.normalized_sha256,
        "point_count": value.point_count,
        "governed_source": (
            None
            if value.governed_source is None
            else {
                "material": {
                    "aggregate_id": str(value.governed_source.material.aggregate_id),
                    "revision_id": str(value.governed_source.material.revision_id),
                },
                "material_state": {
                    "aggregate_id": str(value.governed_source.material_state.aggregate_id),
                    "revision_id": str(value.governed_source.material_state.revision_id),
                },
                "test_run": {
                    "aggregate_id": str(value.governed_source.test_run.aggregate_id),
                    "revision_id": str(value.governed_source.test_run.revision_id),
                },
            }
        ),
    }


def _write_children(session: Session, draft: RevisionDraft[TestDataDocumentContent]) -> None:
    common = {
        "organization_id": draft.scope.organization_id,
        "project_id": draft.scope.project_id,
        "classification": draft.scope.classification,
        "document_id": draft.aggregate_id,
        "document_revision_id": draft.revision_id,
    }
    if draft.content.conditions:
        session.execute(
            sa.insert(condition_table),
            [
                {
                    **common,
                    "ordinal": ordinal,
                    "condition_key": item.key,
                    "quantity_semantics": item.quantity_semantics,
                    "original_value": item.original_value,
                    "original_unit_string": item.original_unit_string,
                    "normalized_value": item.normalized_value,
                    "normalized_unit": item.normalized_unit,
                }
                for ordinal, item in enumerate(draft.content.conditions)
            ],
        )
    session.execute(
        sa.insert(channel_table),
        [
            {
                **common,
                "ordinal": ordinal,
                "channel_key": item.key,
                "channel_name": item.name,
                "quantity_semantics": item.quantity_semantics,
                "axis_role": item.axis_role,
                "original_unit_string": item.original_unit_string,
                "normalized_unit": item.normalized_unit,
                "normalization_scale": Decimal(item.normalization_scale),
                "normalization_offset": Decimal(item.normalization_offset),
                "point_count": item.point_count,
                "missing_count": item.missing_count,
            }
            for ordinal, item in enumerate(draft.content.channels)
        ],
    )


_TABLES = TypedRevisionTables(
    aggregate_type=TEST_DATA_DOCUMENT_AGGREGATE_TYPE,
    identity_table=document_table,
    revision_table=document_revision_table,
    canonical_content=test_data_content_canonical,
    content_values=_content_values,
    identity_values=lambda value: {"document_key": value.document_key},
    revision_content_writer=_write_children,
)


def _record(row: Any) -> RevisionRecord:
    return RevisionRecord(
        revision_id=cast(UUID, row["id"]),
        aggregate_type=TEST_DATA_DOCUMENT_AGGREGATE_TYPE,
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


def _content(
    row: Any,
    conditions: Sequence[Any],
    channels: Sequence[Any],
) -> TestDataDocumentContent:
    governed = row["governed_source"]
    return TestDataDocumentContent(
        document_key=str(row["document_key"]),
        material=TestMaterialMetadata(
            str(row["maker"]), str(row["grade"]), cast(str | None, row["lot_batch"])
        ),
        test=TestExecutionMetadata(
            cast(date, row["test_date"]),
            str(row["operator_name"]),
            str(row["laboratory"]),
            str(row["test_method"]),
            cast(str | None, row["equipment_maker"]),
            cast(str | None, row["equipment_model"]),
        ),
        specimen=TestSpecimenMetadata(
            str(row["specimen_key"]), cast(str | None, row["specimen_description"])
        ),
        conditions=tuple(
            TestCondition(
                key=str(item["condition_key"]),
                quantity_semantics=str(item["quantity_semantics"]),
                original_value=cast(Decimal, item["original_value"]),
                original_unit_string=str(item["original_unit_string"]),
                normalized_value=cast(Decimal, item["normalized_value"]),
                normalized_unit=str(item["normalized_unit"]),
            )
            for item in conditions
        ),
        channels=tuple(
            TestDataChannelSummary(
                key=str(item["channel_key"]),
                name=str(item["channel_name"]),
                quantity_semantics=str(item["quantity_semantics"]),
                axis_role=str(item["axis_role"]),
                original_unit_string=str(item["original_unit_string"]),
                normalized_unit=str(item["normalized_unit"]),
                normalization_scale=str(item["normalization_scale"]),
                normalization_offset=str(item["normalization_offset"]),
                point_count=int(item["point_count"]),
                missing_count=int(item["missing_count"]),
            )
            for item in channels
        ),
        source=TestDataSource(
            str(row["source_file_name"]),
            str(row["source_media_type"]),
            str(row["source_sha256"]),
        ),
        canonical_artifact_id=cast(UUID, row["canonical_artifact_id"]),
        canonical_sha256=str(row["canonical_sha256"]),
        normalized_artifact_id=cast(UUID, row["normalized_artifact_id"]),
        normalized_sha256=str(row["normalized_sha256"]),
        point_count=int(row["point_count"]),
        governed_source=(
            None
            if governed is None
            else GovernedTestDataSource(
                material=ExactRevisionRef(
                    UUID(str(governed["material"]["aggregate_id"])),
                    UUID(str(governed["material"]["revision_id"])),
                ),
                material_state=ExactRevisionRef(
                    UUID(str(governed["material_state"]["aggregate_id"])),
                    UUID(str(governed["material_state"]["revision_id"])),
                ),
                test_run=ExactRevisionRef(
                    UUID(str(governed["test_run"]["aggregate_id"])),
                    UUID(str(governed["test_run"]["revision_id"])),
                ),
            )
        ),
    )


class SqlAlchemyCanonicalTestDataRepository(CanonicalTestDataRepository):
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

    def document_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[TestDataDocumentContent]:
        return SqlAlchemyRevisionStore(
            session_factory=self._sessions,
            tables=_TABLES,
            hooks=self._hooks,
            session_binder=lambda session: self._bind(session, context, decision),
        )

    @staticmethod
    def _snapshot(session: Session, row: Any) -> TestDataDocumentSnapshot:
        revision_id = cast(UUID, row["id"])
        conditions = (
            session.execute(
                sa.select(condition_table)
                .where(condition_table.c.document_revision_id == revision_id)
                .order_by(condition_table.c.ordinal)
            )
            .mappings()
            .all()
        )
        channels = (
            session.execute(
                sa.select(channel_table)
                .where(channel_table.c.document_revision_id == revision_id)
                .order_by(channel_table.c.ordinal)
            )
            .mappings()
            .all()
        )
        record = _record(row)
        return TestDataDocumentSnapshot(
            record.aggregate_id,
            record,
            _content(row, conditions, channels),
        )

    def get_document(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        document_id: UUID,
    ) -> TestDataDocumentSnapshot:
        with self._session(context, decision) as session:
            row = (
                session.execute(
                    sa.select(document_revision_table)
                    .join(
                        document_table,
                        sa.and_(
                            document_table.c.organization_id
                            == document_revision_table.c.organization_id,
                            document_table.c.project_id == document_revision_table.c.project_id,
                            document_table.c.id == document_revision_table.c.aggregate_id,
                            document_table.c.current_revision_id == document_revision_table.c.id,
                        ),
                    )
                    .where(document_table.c.id == document_id)
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise GovernedImportNotFound("Test Data document is not visible")
            return self._snapshot(session, row)

    def get_document_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        document_id: UUID,
        revision_id: UUID,
    ) -> TestDataDocumentSnapshot:
        with self._session(context, decision) as session:
            row = (
                session.execute(
                    sa.select(document_revision_table).where(
                        document_revision_table.c.aggregate_id == document_id,
                        document_revision_table.c.id == revision_id,
                    )
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise GovernedImportNotFound("Test Data document revision is not visible")
            return self._snapshot(session, row)

    def list_documents(
        self, *, context: SecurityContext, decision: AuthorizationDecision
    ) -> tuple[TestDataDocumentSnapshot, ...]:
        with self._session(context, decision) as session:
            rows = (
                session.execute(
                    sa.select(document_revision_table)
                    .join(
                        document_table,
                        sa.and_(
                            document_table.c.organization_id
                            == document_revision_table.c.organization_id,
                            document_table.c.project_id == document_revision_table.c.project_id,
                            document_table.c.id == document_revision_table.c.aggregate_id,
                            document_table.c.current_revision_id == document_revision_table.c.id,
                        ),
                    )
                    .order_by(document_table.c.updated_at.desc(), document_table.c.id)
                )
                .mappings()
                .all()
            )
            return tuple(self._snapshot(session, row) for row in rows)

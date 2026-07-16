"""PostgreSQL adapter for T-42 viscoelastic Selections and derived Datasets."""

from __future__ import annotations

from collections.abc import Sequence
from contextlib import contextmanager
from typing import Any, Protocol, cast
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from cmp.modules.datasets.application.viscoelastic_master import (
    VISCOELASTIC_DERIVED_DATASET_AGGREGATE_TYPE,
    VISCOELASTIC_SELECTION_AGGREGATE_TYPE,
    RevisionSnapshot,
    ViscoelasticDatasetNotFound,
    ViscoelasticDatasetRepository,
    ViscoelasticDerivedDatasetSnapshot,
    ViscoelasticSelectionSnapshot,
)
from cmp.modules.datasets.domain.viscoelastic_master import (
    ViscoelasticDerivedDatasetContent,
    ViscoelasticDerivedRepresentation,
    ViscoelasticSelectionContent,
    ViscoelasticSelectionMember,
)
from cmp.modules.identity_access.domain.authorization import AuthorizationDecision
from cmp.modules.identity_access.domain.security import SecurityContext
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


def _identity(name: str, *columns: sa.Column[Any]) -> sa.Table:
    return sa.Table(
        name,
        metadata,
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("classification", sa.String(64), nullable=False),
        *columns,
        sa.Column("current_revision_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        schema="datasets",
    )


def _revision(name: str, *columns: sa.Column[Any]) -> sa.Table:
    return sa.Table(
        name,
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
        *columns,
        schema="datasets",
    )


selection_table = _identity(
    "viscoelastic_selection",
    sa.Column("selection_label", sa.String(160), nullable=False),
    sa.Column("material_state_id", sa.Uuid(), nullable=False),
)
selection_revision_table = _revision(
    "viscoelastic_selection_revision",
    sa.Column("selection_label", sa.String(160), nullable=False),
    sa.Column("material_state_id", sa.Uuid(), nullable=False),
    sa.Column("material_state_revision_id", sa.Uuid(), nullable=False),
    sa.Column("member_count", sa.SmallInteger(), nullable=False),
    sa.Column("temperature_count", sa.SmallInteger(), nullable=False),
)
selection_member_table = sa.Table(
    "viscoelastic_selection_member",
    metadata,
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("selection_id", sa.Uuid(), nullable=False),
    sa.Column("selection_revision_id", sa.Uuid(), nullable=False),
    sa.Column("ordinal", sa.SmallInteger(), nullable=False),
    sa.Column("dataset_id", sa.Uuid(), nullable=False),
    sa.Column("dataset_revision_id", sa.Uuid(), nullable=False),
    sa.Column("test_run_id", sa.Uuid(), nullable=False),
    sa.Column("test_run_revision_id", sa.Uuid(), nullable=False),
    sa.Column("temperature_k", sa.Double(), nullable=False),
    sa.Column("outlier_status", sa.String(32), nullable=False),
    schema="datasets",
)

derived_dataset_table = _identity(
    "viscoelastic_derived_dataset",
    sa.Column("material_state_id", sa.Uuid(), nullable=False),
    sa.Column("processing_run_id", sa.Uuid(), nullable=False),
    sa.Column("representation", sa.String(32), nullable=False),
)
derived_dataset_revision_table = _revision(
    "viscoelastic_derived_dataset_revision",
    sa.Column("material_state_id", sa.Uuid(), nullable=False),
    sa.Column("material_state_revision_id", sa.Uuid(), nullable=False),
    sa.Column("selection_id", sa.Uuid(), nullable=False),
    sa.Column("selection_revision_id", sa.Uuid(), nullable=False),
    sa.Column("processing_plan_id", sa.Uuid(), nullable=False),
    sa.Column("processing_plan_revision_id", sa.Uuid(), nullable=False),
    sa.Column("processing_run_id", sa.Uuid(), nullable=False),
    sa.Column("representation", sa.String(32), nullable=False),
    sa.Column("data_artifact_id", sa.Uuid(), nullable=False),
    sa.Column("data_sha256", sa.CHAR(64), nullable=False),
    sa.Column("row_count", sa.BigInteger(), nullable=False),
    sa.Column("source_curve_count", sa.SmallInteger(), nullable=False),
    sa.Column("reference_temperature_k", sa.Double(), nullable=False),
    sa.Column("schema_ref", sa.String(500), nullable=False),
)


def _record(row: Any, aggregate_type: str) -> RevisionRecord:
    return RevisionRecord(
        revision_id=cast(UUID, row["id"]),
        aggregate_type=aggregate_type,
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


def _write_members(session: Session, draft: Any) -> None:
    value = cast(ViscoelasticSelectionContent, draft.content)
    session.execute(
        sa.insert(selection_member_table),
        [
            {
                "organization_id": draft.scope.organization_id,
                "project_id": draft.scope.project_id,
                "classification": draft.scope.classification,
                "selection_id": draft.aggregate_id,
                "selection_revision_id": draft.revision_id,
                "ordinal": item.ordinal,
                "dataset_id": item.dataset_id,
                "dataset_revision_id": item.dataset_revision_id,
                "test_run_id": item.test_run_id,
                "test_run_revision_id": item.test_run_revision_id,
                "temperature_k": item.temperature_k,
                "outlier_status": item.outlier_status,
            }
            for item in value.members
        ],
    )


_SELECTION_TABLES = TypedRevisionTables[ViscoelasticSelectionContent](
    aggregate_type=VISCOELASTIC_SELECTION_AGGREGATE_TYPE,
    identity_table=selection_table,
    revision_table=selection_revision_table,
    canonical_content=lambda value: value.canonical(),
    content_values=lambda value: {
        "selection_label": value.selection_label,
        "material_state_id": value.material_state_id,
        "material_state_revision_id": value.material_state_revision_id,
        "member_count": len(value.members),
        "temperature_count": len({item.temperature_k for item in value.members}),
    },
    identity_values=lambda value: {
        "selection_label": value.selection_label,
        "material_state_id": value.material_state_id,
    },
    revision_content_writer=_write_members,
)


def _derived_values(value: ViscoelasticDerivedDatasetContent) -> dict[str, object]:
    return {
        "material_state_id": value.material_state_id,
        "material_state_revision_id": value.material_state_revision_id,
        "selection_id": value.selection_id,
        "selection_revision_id": value.selection_revision_id,
        "processing_plan_id": value.processing_plan_id,
        "processing_plan_revision_id": value.processing_plan_revision_id,
        "processing_run_id": value.processing_run_id,
        "representation": value.representation.value,
        "data_artifact_id": value.data_artifact_id,
        "data_sha256": value.data_sha256,
        "row_count": value.row_count,
        "source_curve_count": value.source_curve_count,
        "reference_temperature_k": value.reference_temperature_k,
        "schema_ref": value.schema_ref,
    }


_DERIVED_TABLES = TypedRevisionTables[ViscoelasticDerivedDatasetContent](
    aggregate_type=VISCOELASTIC_DERIVED_DATASET_AGGREGATE_TYPE,
    identity_table=derived_dataset_table,
    revision_table=derived_dataset_revision_table,
    canonical_content=lambda value: value.canonical(),
    content_values=_derived_values,
    identity_values=lambda value: {
        "material_state_id": value.material_state_id,
        "processing_run_id": value.processing_run_id,
        "representation": value.representation.value,
    },
)


def _members(session: Session, revision_id: UUID) -> tuple[ViscoelasticSelectionMember, ...]:
    rows = (
        session.execute(
            sa.select(selection_member_table)
            .where(selection_member_table.c.selection_revision_id == revision_id)
            .order_by(selection_member_table.c.ordinal)
        )
        .mappings()
        .all()
    )
    return tuple(
        ViscoelasticSelectionMember(
            ordinal=int(row["ordinal"]),
            dataset_id=cast(UUID, row["dataset_id"]),
            dataset_revision_id=cast(UUID, row["dataset_revision_id"]),
            test_run_id=cast(UUID, row["test_run_id"]),
            test_run_revision_id=cast(UUID, row["test_run_revision_id"]),
            temperature_k=float(row["temperature_k"]),
            outlier_status=str(row["outlier_status"]),
        )
        for row in rows
    )


def _selection_content(session: Session, row: Any) -> ViscoelasticSelectionContent:
    content = ViscoelasticSelectionContent(
        selection_label=str(row["selection_label"]),
        material_state_id=cast(UUID, row["material_state_id"]),
        material_state_revision_id=cast(UUID, row["material_state_revision_id"]),
        members=_members(session, cast(UUID, row["id"])),
    )
    if (
        len(content.members) != int(row["member_count"])
        or len({item.temperature_k for item in content.members})
        != int(row["temperature_count"])
    ):
        raise ViscoelasticDatasetNotFound("Selection membership is incomplete")
    return content


def _derived_content(row: Any) -> ViscoelasticDerivedDatasetContent:
    return ViscoelasticDerivedDatasetContent(
        material_state_id=cast(UUID, row["material_state_id"]),
        material_state_revision_id=cast(UUID, row["material_state_revision_id"]),
        selection_id=cast(UUID, row["selection_id"]),
        selection_revision_id=cast(UUID, row["selection_revision_id"]),
        processing_plan_id=cast(UUID, row["processing_plan_id"]),
        processing_plan_revision_id=cast(UUID, row["processing_plan_revision_id"]),
        processing_run_id=cast(UUID, row["processing_run_id"]),
        representation=ViscoelasticDerivedRepresentation(str(row["representation"])),
        data_artifact_id=cast(UUID, row["data_artifact_id"]),
        data_sha256=str(row["data_sha256"]),
        row_count=int(row["row_count"]),
        source_curve_count=int(row["source_curve_count"]),
        reference_temperature_k=float(row["reference_temperature_k"]),
        schema_ref=str(row["schema_ref"]),
    )


class SqlAlchemyViscoelasticDatasetRepository(ViscoelasticDatasetRepository):
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
        self,
        session: Session,
        context: SecurityContext,
        decision: AuthorizationDecision,
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
    ) -> RevisionStore[ViscoelasticSelectionContent]:
        return SqlAlchemyRevisionStore(
            session_factory=self._sessions,
            tables=_SELECTION_TABLES,
            hooks=self._hooks,
            session_binder=lambda session: self._bind(session, context, decision),
        )

    def derived_dataset_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[ViscoelasticDerivedDatasetContent]:
        return SqlAlchemyRevisionStore(
            session_factory=self._sessions,
            tables=_DERIVED_TABLES,
            hooks=self._hooks,
            session_binder=lambda session: self._bind(session, context, decision),
        )

    def _selection_snapshot(self, session: Session, row: Any) -> ViscoelasticSelectionSnapshot:
        record = _record(row, VISCOELASTIC_SELECTION_AGGREGATE_TYPE)
        return ViscoelasticSelectionSnapshot(
            record.aggregate_id,
            RevisionSnapshot(record, _selection_content(session, row)),
        )

    def get_selection(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        selection_id: UUID,
    ) -> ViscoelasticSelectionSnapshot:
        with self._session(context, decision) as session:
            row = (
                session.execute(
                    sa.select(selection_revision_table)
                    .join(
                        selection_table,
                        selection_table.c.current_revision_id == selection_revision_table.c.id,
                    )
                    .where(selection_table.c.id == selection_id)
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise ViscoelasticDatasetNotFound("Selection is not visible")
            return self._selection_snapshot(session, row)

    def get_selection_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        selection_id: UUID,
        selection_revision_id: UUID,
    ) -> RevisionSnapshot[ViscoelasticSelectionContent]:
        with self._session(context, decision) as session:
            row = (
                session.execute(
                    sa.select(selection_revision_table).where(
                        selection_revision_table.c.aggregate_id == selection_id,
                        selection_revision_table.c.id == selection_revision_id,
                    )
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise ViscoelasticDatasetNotFound("Selection revision is not visible")
            return RevisionSnapshot(
                _record(row, VISCOELASTIC_SELECTION_AGGREGATE_TYPE),
                _selection_content(session, row),
            )
    def list_selections(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_state_id: UUID,
    ) -> tuple[ViscoelasticSelectionSnapshot, ...]:
        with self._session(context, decision) as session:
            rows = (
                session.execute(
                    sa.select(selection_revision_table)
                    .join(
                        selection_table,
                        selection_table.c.current_revision_id == selection_revision_table.c.id,
                    )
                    .where(selection_table.c.material_state_id == material_state_id)
                    .order_by(selection_table.c.updated_at.desc(), selection_table.c.id)
                )
                .mappings()
                .all()
            )
            return tuple(self._selection_snapshot(session, row) for row in rows)

    def get_derived_dataset(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        dataset_id: UUID,
    ) -> ViscoelasticDerivedDatasetSnapshot:
        with self._session(context, decision) as session:
            row = (
                session.execute(
                    sa.select(derived_dataset_revision_table)
                    .join(
                        derived_dataset_table,
                        derived_dataset_table.c.current_revision_id
                        == derived_dataset_revision_table.c.id,
                    )
                    .where(derived_dataset_table.c.id == dataset_id)
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise ViscoelasticDatasetNotFound("derived Dataset is not visible")
            record = _record(row, VISCOELASTIC_DERIVED_DATASET_AGGREGATE_TYPE)
            return ViscoelasticDerivedDatasetSnapshot(
                record.aggregate_id,
                RevisionSnapshot(record, _derived_content(row)),
            )

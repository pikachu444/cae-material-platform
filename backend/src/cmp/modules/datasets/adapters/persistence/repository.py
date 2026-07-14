"""PostgreSQL persistence for raw/normalized reference tensile Dataset revisions."""

from __future__ import annotations

from collections.abc import Sequence
from contextlib import contextmanager
from typing import Any, Protocol, cast
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session, sessionmaker

from cmp.modules.datasets.application.service import (
    DATASET_AGGREGATE_TYPE,
    DATASET_SELECTION_AGGREGATE_TYPE,
    CalibrationDatasetSource,
    DatasetRepository,
    DatasetRevisionSnapshot,
    DatasetSelectionRevisionSnapshot,
    DatasetSelectionSnapshot,
    DatasetSnapshot,
    ReferenceTestRunSource,
    RevisionSnapshot,
    TensileReplicateSelectionRevisionSnapshot,
    TensileReplicateSelectionSnapshot,
)
from cmp.modules.datasets.domain.reference_tensile import (
    DatasetContent,
    DatasetNotFound,
    DatasetRepresentation,
    ReferenceTensileMapping,
    dataset_canonical,
)
from cmp.modules.datasets.domain.selection import (
    REFERENCE_TENSILE_REPLICATE_SELECTION_KIND,
    ReferenceDatasetSelectionContent,
    ReferenceTensileReplicateSelectionContent,
    ReferenceTensileReplicateSelectionMember,
    reference_dataset_selection_canonical,
    reference_tensile_replicate_selection_canonical,
)
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.testing.domain.reference_tensile import REFERENCE_TENSILE_METHOD_CODE
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
dataset_table = sa.Table(
    "dataset",
    metadata,
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("test_run_id", sa.Uuid(), nullable=False),
    sa.Column("raw_asset_id", sa.Uuid(), nullable=False),
    sa.Column("raw_artifact_id", sa.Uuid(), nullable=False),
    sa.Column("mapping_sha256", sa.CHAR(64), nullable=False),
    sa.Column("processing_run_id", sa.Uuid(), nullable=True),
    sa.Column("current_revision_id", sa.Uuid(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("created_by", sa.Uuid(), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    schema="datasets",
)
dataset_revision_table = sa.Table(
    "dataset_revision",
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
    sa.Column("test_run_id", sa.Uuid(), nullable=False),
    sa.Column("test_run_revision_id", sa.Uuid(), nullable=False),
    sa.Column("raw_asset_id", sa.Uuid(), nullable=False),
    sa.Column("raw_artifact_id", sa.Uuid(), nullable=False),
    sa.Column("data_artifact_id", sa.Uuid(), nullable=False),
    sa.Column("data_sha256", sa.CHAR(64), nullable=False),
    sa.Column("representation", sa.String(16), nullable=False),
    sa.Column("source_dataset_revision_id", sa.Uuid(), nullable=True),
    sa.Column("processing_run_id", sa.Uuid(), nullable=True),
    sa.Column("point_count", sa.BigInteger(), nullable=False),
    sa.Column("strain_column", sa.String(255), nullable=False),
    sa.Column("stress_column", sa.String(255), nullable=False),
    sa.Column("strain_original_unit", sa.String(16), nullable=False),
    sa.Column("stress_original_unit", sa.String(16), nullable=False),
    sa.Column("mapping_sha256", sa.CHAR(64), nullable=False),
    sa.Column("importer_id", sa.String(255), nullable=False),
    sa.Column("importer_version", sa.String(64), nullable=False),
    schema="datasets",
)
dataset_selection_table = sa.Table(
    "dataset_selection",
    metadata,
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("selection_kind", sa.String(64), nullable=False),
    sa.Column("selection_label", sa.String(160), nullable=False),
    sa.Column("current_revision_id", sa.Uuid(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("created_by", sa.Uuid(), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    schema="datasets",
)
dataset_selection_revision_table = sa.Table(
    "dataset_selection_revision",
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
    sa.Column("selection_kind", sa.String(64), nullable=False),
    sa.Column("dataset_id", sa.Uuid(), nullable=True),
    sa.Column("dataset_revision_id", sa.Uuid(), nullable=True),
    sa.Column("member_count", sa.SmallInteger(), nullable=False),
    schema="datasets",
)
dataset_selection_member_table = sa.Table(
    "dataset_selection_member",
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
    schema="datasets",
)
test_run_revision_table = sa.Table(
    "test_run_revision",
    metadata,
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("aggregate_id", sa.Uuid(), nullable=False),
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("test_method_id", sa.Uuid(), nullable=False),
    sa.Column("test_method_revision_id", sa.Uuid(), nullable=False),
    sa.Column("reference_only", sa.Boolean(), nullable=False),
    schema="testing",
)
test_run_table = sa.Table(
    "test_run",
    metadata,
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("specimen_id", sa.Uuid(), nullable=False),
    schema="testing",
)
test_method_revision_table = sa.Table(
    "test_method_revision",
    metadata,
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("aggregate_id", sa.Uuid(), nullable=False),
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("method_code", sa.String(100), nullable=False),
    sa.Column("reference_only", sa.Boolean(), nullable=False),
    schema="testing",
)
specimen_table = sa.Table(
    "specimen",
    metadata,
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("material_state_id", sa.Uuid(), nullable=False),
    schema="testing",
)
def _record(row: Any) -> RevisionRecord:
    return RevisionRecord(
        revision_id=cast(UUID, row["id"]),
        aggregate_type=DATASET_AGGREGATE_TYPE,
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


def _content(row: Any) -> DatasetContent:
    return DatasetContent(
        test_run_id=cast(UUID, row["test_run_id"]),
        test_run_revision_id=cast(UUID, row["test_run_revision_id"]),
        raw_asset_id=cast(UUID, row["raw_asset_id"]),
        raw_artifact_id=cast(UUID, row["raw_artifact_id"]),
        data_artifact_id=cast(UUID, row["data_artifact_id"]),
        data_sha256=str(row["data_sha256"]),
        representation=DatasetRepresentation(str(row["representation"])),
        source_dataset_revision_id=cast(UUID | None, row["source_dataset_revision_id"]),
        point_count=int(row["point_count"]),
        mapping=ReferenceTensileMapping(
            strain_column=str(row["strain_column"]),
            stress_column=str(row["stress_column"]),
            strain_unit=str(row["strain_original_unit"]),
            stress_unit=str(row["stress_original_unit"]),
        ),
        importer_id=str(row["importer_id"]),
        importer_version=str(row["importer_version"]),
        processing_run_id=cast(UUID | None, row["processing_run_id"]),
    )


def _values(value: DatasetContent) -> dict[str, object]:
    return {
        "test_run_id": value.test_run_id,
        "test_run_revision_id": value.test_run_revision_id,
        "raw_asset_id": value.raw_asset_id,
        "raw_artifact_id": value.raw_artifact_id,
        "data_artifact_id": value.data_artifact_id,
        "data_sha256": value.data_sha256,
        "representation": value.representation.value,
        "source_dataset_revision_id": value.source_dataset_revision_id,
        "processing_run_id": value.processing_run_id,
        "point_count": value.point_count,
        "strain_column": value.mapping.strain_column,
        "stress_column": value.mapping.stress_column,
        "strain_original_unit": value.mapping.strain_unit,
        "stress_original_unit": value.mapping.stress_unit,
        "mapping_sha256": value.mapping_sha256,
        "importer_id": value.importer_id,
        "importer_version": value.importer_version,
    }


_TABLES: TypedRevisionTables[DatasetContent] = TypedRevisionTables(
    aggregate_type=DATASET_AGGREGATE_TYPE,
    identity_table=dataset_table,
    revision_table=dataset_revision_table,
    canonical_content=dataset_canonical,
    content_values=_values,
    identity_values=lambda value: {
        "test_run_id": value.test_run_id,
        "raw_asset_id": value.raw_asset_id,
        "raw_artifact_id": value.raw_artifact_id,
        "mapping_sha256": value.mapping_sha256,
        "processing_run_id": value.processing_run_id,
    },
)


def _selection_record(row: Any) -> RevisionRecord:
    return RevisionRecord(
        revision_id=cast(UUID, row["id"]),
        aggregate_type=DATASET_SELECTION_AGGREGATE_TYPE,
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


def _selection_content(row: Any) -> ReferenceDatasetSelectionContent:
    if int(row["member_count"]) != 1:
        raise DatasetNotFound("reference Dataset Selection membership is invalid")
    return ReferenceDatasetSelectionContent(
        selection_label=str(row["selection_label"]),
        dataset_id=cast(UUID, row["dataset_id"]),
        dataset_revision_id=cast(UUID, row["dataset_revision_id"]),
    )


_SELECTION_TABLES: TypedRevisionTables[ReferenceDatasetSelectionContent] = TypedRevisionTables(
    aggregate_type=DATASET_SELECTION_AGGREGATE_TYPE,
    identity_table=dataset_selection_table,
    revision_table=dataset_selection_revision_table,
    canonical_content=reference_dataset_selection_canonical,
    content_values=lambda value: {
        "selection_kind": "reference_curve_dataset_revision",
        "dataset_id": value.dataset_id,
        "dataset_revision_id": value.dataset_revision_id,
        "member_count": 1,
    },
    identity_values=lambda value: {
        "selection_kind": "reference_curve_dataset_revision",
        "selection_label": value.selection_label,
    },
)


def _replicate_member_values(
    value: ReferenceTensileReplicateSelectionContent,
) -> dict[str, object]:
    return {
        "selection_kind": REFERENCE_TENSILE_REPLICATE_SELECTION_KIND,
        "dataset_id": None,
        "dataset_revision_id": None,
        "member_count": len(value.members),
    }


def _write_replicate_members(session: Session, draft: Any) -> None:
    value = cast(ReferenceTensileReplicateSelectionContent, draft.content)
    session.execute(
        dataset_selection_member_table.insert(),
        [
            {
                "organization_id": draft.scope.organization_id,
                "project_id": draft.scope.project_id,
                "classification": draft.scope.classification,
                "selection_id": draft.aggregate_id,
                "selection_revision_id": draft.revision_id,
                "ordinal": member.ordinal,
                "dataset_id": member.dataset_id,
                "dataset_revision_id": member.dataset_revision_id,
                "test_run_id": member.test_run_id,
                "test_run_revision_id": member.test_run_revision_id,
            }
            for member in value.members
        ],
    )


_REPLICATE_SELECTION_TABLES: TypedRevisionTables[
    ReferenceTensileReplicateSelectionContent
] = TypedRevisionTables(
    aggregate_type=DATASET_SELECTION_AGGREGATE_TYPE,
    identity_table=dataset_selection_table,
    revision_table=dataset_selection_revision_table,
    canonical_content=reference_tensile_replicate_selection_canonical,
    content_values=_replicate_member_values,
    identity_values=lambda value: {
        "selection_kind": REFERENCE_TENSILE_REPLICATE_SELECTION_KIND,
        "selection_label": value.selection_label,
    },
    revision_content_writer=_write_replicate_members,
)


def _revision_columns(table: sa.Table) -> tuple[Any, ...]:
    return tuple(
        table.c[name].label(name)
        for name in (
            "id",
            "aggregate_id",
            "organization_id",
            "project_id",
            "classification",
            "revision_no",
            "based_on_revision_id",
            "schema_id",
            "schema_version",
            "content_hash",
            "created_at",
            "created_by",
            "change_reason",
            "request_id",
            "trace_id",
        )
    )


class SqlAlchemyDatasetRepository(DatasetRepository):
    """RLS-bound explicit Dataset tables; data points remain in immutable Artifacts."""

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

    def dataset_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[DatasetContent]:
        return SqlAlchemyRevisionStore(
            session_factory=self._sessions,
            tables=_TABLES,
            hooks=self._hooks,
            session_binder=lambda session: self._bind(session, context, decision),
        )

    def selection_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[ReferenceDatasetSelectionContent]:
        return SqlAlchemyRevisionStore(
            session_factory=self._sessions,
            tables=_SELECTION_TABLES,
            hooks=self._hooks,
            session_binder=lambda session: self._bind(session, context, decision),
        )

    def replicate_selection_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[ReferenceTensileReplicateSelectionContent]:
        return SqlAlchemyRevisionStore(
            session_factory=self._sessions,
            tables=_REPLICATE_SELECTION_TABLES,
            hooks=self._hooks,
            session_binder=lambda session: self._bind(session, context, decision),
        )

    def load_reference_test_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        test_run_id: UUID,
        test_run_revision_id: UUID,
    ) -> ReferenceTestRunSource:
        run = test_run_revision_table
        method = test_method_revision_table
        statement = sa.select(
            run.c.classification,
            method.c.method_code,
            run.c.reference_only.label("run_reference_only"),
            method.c.reference_only.label("method_reference_only"),
        ).select_from(
            run.join(
                method,
                sa.and_(
                    method.c.id == run.c.test_method_revision_id,
                    method.c.aggregate_id == run.c.test_method_id,
                    method.c.organization_id == run.c.organization_id,
                    method.c.project_id == run.c.project_id,
                ),
            )
        ).where(
            run.c.organization_id == context.organization_id,
            run.c.project_id == context.project_id,
            run.c.aggregate_id == test_run_id,
            run.c.id == test_run_revision_id,
        )
        with self._session(context, decision) as session:
            try:
                row = session.execute(statement).mappings().one_or_none()
            except DBAPIError as error:
                raise DatasetNotFound("Test Run revision is not available") from error
        if (
            row is None
            or str(row["method_code"]) != REFERENCE_TENSILE_METHOD_CODE
            or not bool(row["run_reference_only"])
            or not bool(row["method_reference_only"])
        ):
            raise DatasetNotFound(
                "reference tensile Test Run is not visible in the selected tenant"
            )
        return ReferenceTestRunSource(
            classification=DataClassification(str(row["classification"])),
            test_method_code=str(row["method_code"]),
        )

    @staticmethod
    def _snapshot(row: Any) -> DatasetSnapshot:
        return DatasetSnapshot(
            id=cast(UUID, row["identity_id"]),
            test_run_id=cast(UUID, row["identity_test_run_id"]),
            current=RevisionSnapshot(_record(row), _content(row)),
        )

    @staticmethod
    def _current_statement() -> sa.Select[Any]:
        identity = dataset_table
        revision_row = dataset_revision_table
        return sa.select(
            identity.c.id.label("identity_id"),
            identity.c.test_run_id.label("identity_test_run_id"),
            *_revision_columns(revision_row),
            revision_row.c.test_run_id,
            revision_row.c.test_run_revision_id,
            revision_row.c.raw_asset_id,
            revision_row.c.raw_artifact_id,
            revision_row.c.data_artifact_id,
            revision_row.c.data_sha256,
            revision_row.c.representation,
            revision_row.c.source_dataset_revision_id,
            revision_row.c.processing_run_id,
            revision_row.c.point_count,
            revision_row.c.strain_column,
            revision_row.c.stress_column,
            revision_row.c.strain_original_unit,
            revision_row.c.stress_original_unit,
            revision_row.c.importer_id,
            revision_row.c.importer_version,
        ).select_from(
            identity.join(
                revision_row,
                sa.and_(
                    revision_row.c.id == identity.c.current_revision_id,
                    revision_row.c.aggregate_id == identity.c.id,
                    revision_row.c.organization_id == identity.c.organization_id,
                    revision_row.c.project_id == identity.c.project_id,
                ),
            )
        )

    def get_dataset(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        dataset_id: UUID,
    ) -> DatasetSnapshot:
        statement = self._current_statement().where(
            dataset_table.c.organization_id == context.organization_id,
            dataset_table.c.project_id == context.project_id,
            dataset_table.c.id == dataset_id,
        )
        with self._session(context, decision) as session:
            row = session.execute(statement).mappings().one_or_none()
        if row is None:
            raise DatasetNotFound("Dataset is not visible in the selected tenant")
        return self._snapshot(row)

    def get_dataset_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        dataset_revision_id: UUID,
    ) -> DatasetRevisionSnapshot:
        row_table = dataset_revision_table
        statement = sa.select(
            *_revision_columns(row_table),
            row_table.c.test_run_id,
            row_table.c.test_run_revision_id,
            row_table.c.raw_asset_id,
            row_table.c.raw_artifact_id,
            row_table.c.data_artifact_id,
            row_table.c.data_sha256,
            row_table.c.representation,
            row_table.c.source_dataset_revision_id,
            row_table.c.processing_run_id,
            row_table.c.point_count,
            row_table.c.strain_column,
            row_table.c.stress_column,
            row_table.c.strain_original_unit,
            row_table.c.stress_original_unit,
            row_table.c.importer_id,
            row_table.c.importer_version,
        ).where(
            row_table.c.organization_id == context.organization_id,
            row_table.c.project_id == context.project_id,
            row_table.c.id == dataset_revision_id,
        )
        with self._session(context, decision) as session:
            row = session.execute(statement).mappings().one_or_none()
        if row is None:
            raise DatasetNotFound("Dataset revision is not visible in the selected tenant")
        return DatasetRevisionSnapshot(
            dataset_id=cast(UUID, row["aggregate_id"]),
            revision=RevisionSnapshot(_record(row), _content(row)),
        )

    def get_calibration_dataset_source(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        dataset_revision_id: UUID,
    ) -> CalibrationDatasetSource:
        """Resolve the concrete specimen Material State for a pinned Dataset revision.

        Modeling receives this through the Dataset public application port, rather than joining
        Testing persistence tables directly.  The join follows the immutable Dataset Test Run
        identity and remains tenant/RLS-bound for the caller's expanded calibration capability.
        """

        dataset = self.get_dataset_revision(
            context=context,
            decision=decision,
            dataset_revision_id=dataset_revision_id,
        )
        statement = (
            sa.select(specimen_table.c.material_state_id)
            .select_from(
                dataset_revision_table.join(
                    test_run_table,
                    sa.and_(
                        test_run_table.c.id == dataset_revision_table.c.test_run_id,
                        test_run_table.c.organization_id
                        == dataset_revision_table.c.organization_id,
                        test_run_table.c.project_id == dataset_revision_table.c.project_id,
                        test_run_table.c.classification == dataset_revision_table.c.classification,
                    ),
                ).join(
                    specimen_table,
                    sa.and_(
                        specimen_table.c.id == test_run_table.c.specimen_id,
                        specimen_table.c.organization_id == test_run_table.c.organization_id,
                        specimen_table.c.project_id == test_run_table.c.project_id,
                        specimen_table.c.classification == test_run_table.c.classification,
                    ),
                )
            )
            .where(
                dataset_revision_table.c.organization_id == context.organization_id,
                dataset_revision_table.c.project_id == context.project_id,
                dataset_revision_table.c.id == dataset_revision_id,
            )
        )
        with self._session(context, decision) as session:
            row = session.execute(statement).mappings().one_or_none()
        if row is None:
            raise DatasetNotFound(
                "Dataset revision specimen lineage is not visible in the selected tenant"
            )
        return CalibrationDatasetSource(
            dataset=dataset,
            material_state_id=cast(UUID, row["material_state_id"]),
        )

    def list_dataset_revisions(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        dataset_id: UUID,
    ) -> tuple[RevisionSnapshot[DatasetContent], ...]:
        row_table = dataset_revision_table
        statement = sa.select(
            *_revision_columns(row_table),
            row_table.c.test_run_id,
            row_table.c.test_run_revision_id,
            row_table.c.raw_asset_id,
            row_table.c.raw_artifact_id,
            row_table.c.data_artifact_id,
            row_table.c.data_sha256,
            row_table.c.representation,
            row_table.c.source_dataset_revision_id,
            row_table.c.processing_run_id,
            row_table.c.point_count,
            row_table.c.strain_column,
            row_table.c.stress_column,
            row_table.c.strain_original_unit,
            row_table.c.stress_original_unit,
            row_table.c.importer_id,
            row_table.c.importer_version,
        ).where(
            row_table.c.organization_id == context.organization_id,
            row_table.c.project_id == context.project_id,
            row_table.c.aggregate_id == dataset_id,
        ).order_by(row_table.c.revision_no.asc())
        with self._session(context, decision) as session:
            rows = session.execute(statement).mappings().all()
        if not rows:
            raise DatasetNotFound("Dataset is not visible in the selected tenant")
        return tuple(RevisionSnapshot(_record(row), _content(row)) for row in rows)

    def list_datasets_for_material_state(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_state_id: UUID,
    ) -> tuple[DatasetSnapshot, ...]:
        statement = self._current_statement().join(
            test_run_table,
            sa.and_(
                test_run_table.c.id == dataset_table.c.test_run_id,
                test_run_table.c.organization_id == dataset_table.c.organization_id,
                test_run_table.c.project_id == dataset_table.c.project_id,
            ),
        ).join(
            specimen_table,
            sa.and_(
                specimen_table.c.id == test_run_table.c.specimen_id,
                specimen_table.c.organization_id == test_run_table.c.organization_id,
                specimen_table.c.project_id == test_run_table.c.project_id,
            ),
        ).where(
            dataset_table.c.organization_id == context.organization_id,
            dataset_table.c.project_id == context.project_id,
            specimen_table.c.material_state_id == material_state_id,
        ).order_by(dataset_table.c.created_at.asc())
        with self._session(context, decision) as session:
            rows = session.execute(statement).mappings().all()
        return tuple(self._snapshot(row) for row in rows)

    @staticmethod
    def _selection_snapshot(row: Any) -> DatasetSelectionSnapshot:
        return DatasetSelectionSnapshot(
            id=cast(UUID, row["identity_id"]),
            selection_label=str(row["identity_selection_label"]),
            current=RevisionSnapshot(_selection_record(row), _selection_content(row)),
        )

    @staticmethod
    def _selection_current_statement() -> sa.Select[Any]:
        identity = dataset_selection_table
        revision = dataset_selection_revision_table
        return sa.select(
            identity.c.id.label("identity_id"),
            identity.c.selection_label.label("identity_selection_label"),
            *_revision_columns(revision),
            revision.c.dataset_id,
            revision.c.dataset_revision_id,
            revision.c.member_count,
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
        ).where(identity.c.selection_kind == "reference_curve_dataset_revision")

    def get_dataset_selection(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        selection_id: UUID,
    ) -> DatasetSelectionSnapshot:
        statement = self._selection_current_statement().where(
            dataset_selection_table.c.organization_id == context.organization_id,
            dataset_selection_table.c.project_id == context.project_id,
            dataset_selection_table.c.id == selection_id,
        )
        with self._session(context, decision) as session:
            row = session.execute(statement).mappings().one_or_none()
        if row is None:
            raise DatasetNotFound("Dataset Selection is not visible in the selected tenant")
        return self._selection_snapshot(row)

    def get_dataset_selection_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        selection_id: UUID,
        selection_revision_id: UUID,
    ) -> DatasetSelectionRevisionSnapshot:
        identity = dataset_selection_table
        revision = dataset_selection_revision_table
        statement = sa.select(
            identity.c.id.label("identity_id"),
            identity.c.selection_label.label("identity_selection_label"),
            *_revision_columns(revision),
            revision.c.dataset_id,
            revision.c.dataset_revision_id,
            revision.c.member_count,
        ).select_from(
            identity.join(
                revision,
                sa.and_(
                    revision.c.aggregate_id == identity.c.id,
                    revision.c.organization_id == identity.c.organization_id,
                    revision.c.project_id == identity.c.project_id,
                ),
            )
        ).where(
            identity.c.organization_id == context.organization_id,
            identity.c.project_id == context.project_id,
            identity.c.id == selection_id,
            revision.c.id == selection_revision_id,
            identity.c.selection_kind == "reference_curve_dataset_revision",
        )
        with self._session(context, decision) as session:
            row = session.execute(statement).mappings().one_or_none()
        if row is None:
            raise DatasetNotFound(
                "Dataset Selection revision is not visible in the selected tenant"
            )
        return DatasetSelectionRevisionSnapshot(
            selection_id=cast(UUID, row["identity_id"]),
            selection_label=str(row["identity_selection_label"]),
            revision=RevisionSnapshot(_selection_record(row), _selection_content(row)),
        )

    def list_dataset_selections_for_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        dataset_revision_id: UUID,
    ) -> tuple[DatasetSelectionSnapshot, ...]:
        statement = self._selection_current_statement().where(
            dataset_selection_table.c.organization_id == context.organization_id,
            dataset_selection_table.c.project_id == context.project_id,
            dataset_selection_revision_table.c.dataset_revision_id == dataset_revision_id,
        ).order_by(dataset_selection_table.c.created_at.asc())
        with self._session(context, decision) as session:
            rows = session.execute(statement).mappings().all()
        return tuple(self._selection_snapshot(row) for row in rows)

    @staticmethod
    def _replicate_content(
        row: Any, members: Sequence[Any]
    ) -> ReferenceTensileReplicateSelectionContent:
        if len(members) != int(row["member_count"]):
            raise DatasetNotFound("replicate Selection membership is incomplete")
        return ReferenceTensileReplicateSelectionContent(
            selection_label=str(row["identity_selection_label"]),
            members=tuple(
                ReferenceTensileReplicateSelectionMember(
                    ordinal=int(member["ordinal"]),
                    dataset_id=cast(UUID, member["dataset_id"]),
                    dataset_revision_id=cast(UUID, member["dataset_revision_id"]),
                    test_run_id=cast(UUID, member["test_run_id"]),
                    test_run_revision_id=cast(UUID, member["test_run_revision_id"]),
                )
                for member in members
            ),
        )

    @staticmethod
    def _replicate_statement(*, current: bool) -> sa.Select[Any]:
        identity = dataset_selection_table
        revision = dataset_selection_revision_table
        join_condition = sa.and_(
            revision.c.aggregate_id == identity.c.id,
            revision.c.organization_id == identity.c.organization_id,
            revision.c.project_id == identity.c.project_id,
        )
        if current:
            join_condition = sa.and_(
                join_condition, revision.c.id == identity.c.current_revision_id
            )
        return sa.select(
            identity.c.id.label("identity_id"),
            identity.c.selection_label.label("identity_selection_label"),
            *_revision_columns(revision),
            revision.c.member_count,
        ).select_from(identity.join(revision, join_condition)).where(
            identity.c.selection_kind == REFERENCE_TENSILE_REPLICATE_SELECTION_KIND
        )

    @staticmethod
    def _load_replicate_members(session: Session, revision_id: UUID) -> Sequence[Any]:
        return session.execute(
            sa.select(
                dataset_selection_member_table.c.ordinal,
                dataset_selection_member_table.c.dataset_id,
                dataset_selection_member_table.c.dataset_revision_id,
                dataset_selection_member_table.c.test_run_id,
                dataset_selection_member_table.c.test_run_revision_id,
            ).where(
                dataset_selection_member_table.c.selection_revision_id == revision_id
            ).order_by(dataset_selection_member_table.c.ordinal.asc())
        ).mappings().all()

    def get_tensile_replicate_selection(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        selection_id: UUID,
    ) -> TensileReplicateSelectionSnapshot:
        statement = self._replicate_statement(current=True).where(
            dataset_selection_table.c.organization_id == context.organization_id,
            dataset_selection_table.c.project_id == context.project_id,
            dataset_selection_table.c.id == selection_id,
        )
        with self._session(context, decision) as session:
            row = session.execute(statement).mappings().one_or_none()
            if row is None:
                raise DatasetNotFound("replicate Selection is not visible in the selected tenant")
            members = self._load_replicate_members(session, cast(UUID, row["id"]))
        return TensileReplicateSelectionSnapshot(
            id=cast(UUID, row["identity_id"]),
            selection_label=str(row["identity_selection_label"]),
            current=RevisionSnapshot(
                _selection_record(row), self._replicate_content(row, members)
            ),
        )

    def get_tensile_replicate_selection_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        selection_id: UUID,
        selection_revision_id: UUID,
    ) -> TensileReplicateSelectionRevisionSnapshot:
        statement = self._replicate_statement(current=False).where(
            dataset_selection_table.c.organization_id == context.organization_id,
            dataset_selection_table.c.project_id == context.project_id,
            dataset_selection_table.c.id == selection_id,
            dataset_selection_revision_table.c.id == selection_revision_id,
        )
        with self._session(context, decision) as session:
            row = session.execute(statement).mappings().one_or_none()
            if row is None:
                raise DatasetNotFound(
                    "replicate Selection revision is not visible in the selected tenant"
                )
            members = self._load_replicate_members(session, selection_revision_id)
        return TensileReplicateSelectionRevisionSnapshot(
            selection_id=selection_id,
            selection_label=str(row["identity_selection_label"]),
            revision=RevisionSnapshot(
                _selection_record(row), self._replicate_content(row, members)
            ),
        )

    def list_tensile_replicate_selections_for_material_state(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_state_id: UUID,
    ) -> tuple[TensileReplicateSelectionSnapshot, ...]:
        identity = dataset_selection_table
        revision = dataset_selection_revision_table
        member = dataset_selection_member_table
        statement = self._replicate_statement(current=True).join(
            member,
            sa.and_(
                member.c.selection_revision_id == revision.c.id,
                member.c.ordinal == 0,
            ),
        ).join(
            test_run_table,
            sa.and_(
                test_run_table.c.id == member.c.test_run_id,
                test_run_table.c.organization_id == member.c.organization_id,
                test_run_table.c.project_id == member.c.project_id,
            ),
        ).join(
            specimen_table,
            sa.and_(
                specimen_table.c.id == test_run_table.c.specimen_id,
                specimen_table.c.organization_id == test_run_table.c.organization_id,
                specimen_table.c.project_id == test_run_table.c.project_id,
            ),
        ).where(
            identity.c.organization_id == context.organization_id,
            identity.c.project_id == context.project_id,
            specimen_table.c.material_state_id == material_state_id,
        ).order_by(identity.c.created_at.asc())
        results: list[TensileReplicateSelectionSnapshot] = []
        with self._session(context, decision) as session:
            rows = session.execute(statement).mappings().all()
            for row in rows:
                members = self._load_replicate_members(session, cast(UUID, row["id"]))
                results.append(
                    TensileReplicateSelectionSnapshot(
                        id=cast(UUID, row["identity_id"]),
                        selection_label=str(row["identity_selection_label"]),
                        current=RevisionSnapshot(
                            _selection_record(row), self._replicate_content(row, members)
                        ),
                    )
                )
        return tuple(results)

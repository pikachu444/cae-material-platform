"""PostgreSQL adapter for T-41 Import Profiles, Runs, and governed Datasets."""

from __future__ import annotations

from collections.abc import Sequence
from contextlib import contextmanager
from dataclasses import replace
from typing import Any, Protocol, cast
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.orm import Session, sessionmaker

from cmp.modules.datasets.application.governed_import import (
    GOVERNED_DATASET_AGGREGATE_TYPE,
    IMPORT_PROFILE_AGGREGATE_TYPE,
    SCHEMA_VERSION,
    CommitGovernedImportSuccess,
    GovernedDatasetSnapshot,
    GovernedImportRepository,
    ImportProfileRevisionSnapshot,
    ImportProfileSnapshot,
    ImportRun,
    RevisionSnapshot,
)
from cmp.modules.datasets.domain.governed_tabular import (
    GOVERNED_DATASET_SCHEMA_ID,
    GOVERNED_IMPORTER_ID,
    GOVERNED_IMPORTER_VERSION,
    AxisRole,
    GovernedChannelMapping,
    GovernedDatasetContent,
    GovernedDatasetRepresentation,
    GovernedImportConflict,
    GovernedImportNotFound,
    GovernedImportProfileContent,
    ImportDiagnostic,
    ImportRunStatus,
    QuantityKind,
    TabularDataSchema,
    TabularFileFormat,
    TabularPreview,
    governed_dataset_canonical,
    import_profile_canonical,
)
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.shared.adapters.persistence.revisions import (
    SqlAlchemyRevisionStore,
    SqlRevisionHook,
    TypedRevisionTables,
)
from cmp.shared.application.revisions import (
    CreateRevisionedAggregate,
    RevisionService,
    RevisionStore,
)
from cmp.shared.domain.revisions import RevisionDraft, RevisionRecord, TenantScope


class RlsContext(Protocol):
    def bind_authorization(
        self,
        session: Session,
        context: SecurityContext,
        decision: AuthorizationDecision,
    ) -> None: ...


metadata = sa.MetaData()


def _identity_table(name: str, *columns: sa.Column[Any]) -> sa.Table:
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


def _revision_table(name: str, *columns: sa.Column[Any]) -> sa.Table:
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


import_profile_table = _identity_table(
    "import_profile", sa.Column("profile_label", sa.String(160), nullable=False)
)
import_profile_revision_table = _revision_table(
    "import_profile_revision",
    sa.Column("profile_label", sa.String(160), nullable=False),
    sa.Column("data_schema", sa.String(64), nullable=False),
    sa.Column("file_format", sa.String(16), nullable=False),
    sa.Column("sheet_name", sa.String(255), nullable=True),
    sa.Column("header_row", sa.Integer(), nullable=False),
    sa.Column("encoding", sa.String(32), nullable=False),
    sa.Column("delimiter", sa.String(1), nullable=True),
    sa.Column("decimal_separator", sa.String(1), nullable=False),
    sa.Column("initial_gauge_length_m", sa.Float(), nullable=True),
    sa.Column("initial_cross_section_area_m2", sa.Float(), nullable=True),
    sa.Column("approval_kind", sa.String(32), nullable=False),
    # Nullable by design: migration 104 does not backfill historical profile revisions.
    sa.Column("deformation_mode", sa.String(32), nullable=True),
)
import_profile_channel_table = sa.Table(
    "import_profile_channel",
    metadata,
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("import_profile_id", sa.Uuid(), nullable=False),
    sa.Column("import_profile_revision_id", sa.Uuid(), nullable=False),
    sa.Column("ordinal", sa.Integer(), nullable=False),
    sa.Column("source_column", sa.String(255), nullable=False),
    sa.Column("source_quantity", sa.String(64), nullable=False),
    sa.Column("original_unit", sa.String(32), nullable=False),
    sa.Column("normalized_quantity", sa.String(64), nullable=False),
    sa.Column("normalized_unit", sa.String(32), nullable=False),
    sa.Column("axis_role", sa.String(32), nullable=False),
    schema="datasets",
)

governed_dataset_table = _identity_table(
    "governed_dataset", sa.Column("test_run_id", sa.Uuid(), nullable=False)
)
governed_dataset_revision_table = _revision_table(
    "governed_dataset_revision",
    sa.Column("test_run_id", sa.Uuid(), nullable=False),
    sa.Column("test_run_revision_id", sa.Uuid(), nullable=False),
    sa.Column("raw_asset_id", sa.Uuid(), nullable=False),
    sa.Column("raw_artifact_id", sa.Uuid(), nullable=False),
    sa.Column("import_profile_id", sa.Uuid(), nullable=False),
    sa.Column("import_profile_revision_id", sa.Uuid(), nullable=False),
    sa.Column("representation", sa.String(32), nullable=False),
    sa.Column("data_schema", sa.String(64), nullable=False),
    sa.Column("data_artifact_id", sa.Uuid(), nullable=False),
    sa.Column("data_sha256", sa.CHAR(64), nullable=False),
    sa.Column("source_dataset_revision_id", sa.Uuid(), nullable=True),
    sa.Column("row_count", sa.Integer(), nullable=False),
)
governed_dataset_channel_table = sa.Table(
    "governed_dataset_channel",
    metadata,
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("dataset_id", sa.Uuid(), nullable=False),
    sa.Column("dataset_revision_id", sa.Uuid(), nullable=False),
    sa.Column("ordinal", sa.Integer(), nullable=False),
    sa.Column("source_column", sa.String(255), nullable=False),
    sa.Column("source_quantity", sa.String(64), nullable=False),
    sa.Column("original_unit", sa.String(32), nullable=False),
    sa.Column("normalized_quantity", sa.String(64), nullable=False),
    sa.Column("normalized_unit", sa.String(32), nullable=False),
    sa.Column("axis_role", sa.String(32), nullable=False),
    schema="datasets",
)

preview_table = sa.Table(
    "tabular_preview_report",
    metadata,
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("raw_asset_id", sa.Uuid(), nullable=False),
    sa.Column("raw_artifact_id", sa.Uuid(), nullable=False),
    sa.Column("raw_sha256", sa.CHAR(64), nullable=False),
    sa.Column("file_format", sa.String(16), nullable=False),
    sa.Column("selected_sheet_name", sa.String(255), nullable=True),
    sa.Column("header_row", sa.Integer(), nullable=False),
    sa.Column("encoding", sa.String(32), nullable=False),
    sa.Column("delimiter", sa.String(1), nullable=True),
    sa.Column("decimal_separator", sa.String(1), nullable=False),
    sa.Column("status", sa.String(32), nullable=False),
    sa.Column("report_sha256", sa.CHAR(64), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("created_by", sa.Uuid(), nullable=False),
    sa.Column("request_id", sa.Uuid(), nullable=False),
    sa.Column("trace_id", sa.String(255), nullable=False),
    schema="datasets",
)
preview_column_table = sa.Table(
    "tabular_preview_column",
    metadata,
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("preview_report_id", sa.Uuid(), nullable=False),
    sa.Column("ordinal", sa.Integer(), nullable=False),
    sa.Column("column_name", sa.String(255), nullable=False),
    schema="datasets",
)

import_run_table = sa.Table(
    "tabular_import_run",
    metadata,
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("test_run_id", sa.Uuid(), nullable=False),
    sa.Column("test_run_revision_id", sa.Uuid(), nullable=False),
    sa.Column("raw_asset_id", sa.Uuid(), nullable=False),
    sa.Column("raw_artifact_id", sa.Uuid(), nullable=False),
    sa.Column("import_profile_id", sa.Uuid(), nullable=False),
    sa.Column("import_profile_revision_id", sa.Uuid(), nullable=False),
    sa.Column("profile_sha256", sa.CHAR(64), nullable=False),
    sa.Column("idempotency_key", sa.String(255), nullable=False),
    sa.Column("request_sha256", sa.CHAR(64), nullable=False),
    sa.Column("importer_id", sa.String(255), nullable=False),
    sa.Column("importer_version", sa.String(64), nullable=False),
    sa.Column("status", sa.String(32), nullable=False),
    sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("started_by", sa.Uuid(), nullable=False),
    sa.Column("request_id", sa.Uuid(), nullable=False),
    sa.Column("trace_id", sa.String(255), nullable=False),
    sa.Column("raw_dataset_id", sa.Uuid(), nullable=True),
    sa.Column("raw_dataset_revision_id", sa.Uuid(), nullable=True),
    sa.Column("normalized_dataset_id", sa.Uuid(), nullable=True),
    sa.Column("normalized_dataset_revision_id", sa.Uuid(), nullable=True),
    sa.Column("row_count", sa.Integer(), nullable=True),
    sa.Column("failure_code", sa.String(100), nullable=True),
    sa.Column("failure_detail", sa.Text(), nullable=True),
    schema="datasets",
)
import_row_error_table = sa.Table(
    "tabular_import_row_error",
    metadata,
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("import_run_id", sa.Uuid(), nullable=False),
    sa.Column("ordinal", sa.Integer(), nullable=False),
    sa.Column("row_number", sa.Integer(), nullable=True),
    sa.Column("column_name", sa.String(255), nullable=True),
    sa.Column("channel_key", sa.String(64), nullable=True),
    sa.Column("error_code", sa.String(100), nullable=False),
    sa.Column("error_detail", sa.Text(), nullable=False),
    sa.Column("recovery_hint", sa.String(500), nullable=False),
    schema="datasets",
)


def _profile_values(value: GovernedImportProfileContent) -> dict[str, object]:
    return {
        "profile_label": value.profile_label,
        "data_schema": value.data_schema.value,
        "file_format": value.file_format.value,
        "sheet_name": value.sheet_name,
        "header_row": value.header_row,
        "encoding": value.encoding,
        "delimiter": value.delimiter,
        "decimal_separator": value.decimal_separator,
        "initial_gauge_length_m": value.initial_gauge_length_m,
        "initial_cross_section_area_m2": value.initial_cross_section_area_m2,
        "approval_kind": value.approval_kind,
        "deformation_mode": value.deformation_mode,
    }


def _dataset_values(value: GovernedDatasetContent) -> dict[str, object]:
    return {
        "test_run_id": value.test_run_id,
        "test_run_revision_id": value.test_run_revision_id,
        "raw_asset_id": value.raw_asset_id,
        "raw_artifact_id": value.raw_artifact_id,
        "import_profile_id": value.import_profile_id,
        "import_profile_revision_id": value.import_profile_revision_id,
        "representation": value.representation.value,
        "data_schema": value.data_schema.value,
        "data_artifact_id": value.data_artifact_id,
        "data_sha256": value.data_sha256,
        "source_dataset_revision_id": value.source_dataset_revision_id,
        "row_count": value.row_count,
    }


def _channel_values(channel: GovernedChannelMapping) -> dict[str, object]:
    return {
        "ordinal": channel.ordinal,
        "source_column": channel.source_column,
        "source_quantity": channel.source_quantity.value,
        "original_unit": channel.original_unit,
        "normalized_quantity": channel.normalized_quantity.value,
        "normalized_unit": channel.normalized_unit,
        "axis_role": channel.axis_role.value,
    }


def _write_profile_channels(
    session: Session, draft: RevisionDraft[GovernedImportProfileContent]
) -> None:
    session.execute(
        sa.insert(import_profile_channel_table),
        [
            {
                "organization_id": draft.scope.organization_id,
                "project_id": draft.scope.project_id,
                "classification": draft.scope.classification,
                "import_profile_id": draft.aggregate_id,
                "import_profile_revision_id": draft.revision_id,
                **_channel_values(channel),
            }
            for channel in draft.content.channels
        ],
    )


def _write_dataset_channels(session: Session, draft: RevisionDraft[GovernedDatasetContent]) -> None:
    session.execute(
        sa.insert(governed_dataset_channel_table),
        [
            {
                "organization_id": draft.scope.organization_id,
                "project_id": draft.scope.project_id,
                "classification": draft.scope.classification,
                "dataset_id": draft.aggregate_id,
                "dataset_revision_id": draft.revision_id,
                **_channel_values(channel),
            }
            for channel in draft.content.channels
        ],
    )


_PROFILE_TABLES = TypedRevisionTables(
    aggregate_type=IMPORT_PROFILE_AGGREGATE_TYPE,
    identity_table=import_profile_table,
    revision_table=import_profile_revision_table,
    canonical_content=import_profile_canonical,
    content_values=_profile_values,
    identity_values=lambda value: {"profile_label": value.profile_label},
    revision_content_writer=_write_profile_channels,
)
_DATASET_TABLES = TypedRevisionTables(
    aggregate_type=GOVERNED_DATASET_AGGREGATE_TYPE,
    identity_table=governed_dataset_table,
    revision_table=governed_dataset_revision_table,
    canonical_content=governed_dataset_canonical,
    content_values=_dataset_values,
    identity_values=lambda value: {"test_run_id": value.test_run_id},
    revision_content_writer=_write_dataset_channels,
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


def _channels(rows: Sequence[Any]) -> tuple[GovernedChannelMapping, ...]:
    return tuple(
        GovernedChannelMapping(
            ordinal=int(row["ordinal"]),
            source_column=str(row["source_column"]),
            source_quantity=QuantityKind(str(row["source_quantity"])),
            original_unit=str(row["original_unit"]),
            axis_role=AxisRole(str(row["axis_role"])),
        )
        for row in rows
    )


def _profile(
    row: Any, channels: tuple[GovernedChannelMapping, ...]
) -> GovernedImportProfileContent:
    return GovernedImportProfileContent(
        profile_label=str(row["profile_label"]),
        data_schema=TabularDataSchema(str(row["data_schema"])),
        file_format=TabularFileFormat(str(row["file_format"])),
        sheet_name=cast(str | None, row["sheet_name"]),
        header_row=int(row["header_row"]),
        encoding=str(row["encoding"]),
        delimiter=cast(str | None, row["delimiter"]),
        decimal_separator=str(row["decimal_separator"]),
        channels=channels,
        initial_gauge_length_m=cast(float | None, row["initial_gauge_length_m"]),
        initial_cross_section_area_m2=cast(float | None, row["initial_cross_section_area_m2"]),
        approval_kind=str(row["approval_kind"]),
        schema_version=str(row["schema_version"]),
        deformation_mode=cast(str | None, row.get("deformation_mode")),
    )


def _dataset(row: Any, channels: tuple[GovernedChannelMapping, ...]) -> GovernedDatasetContent:
    return GovernedDatasetContent(
        test_run_id=cast(UUID, row["test_run_id"]),
        test_run_revision_id=cast(UUID, row["test_run_revision_id"]),
        raw_asset_id=cast(UUID, row["raw_asset_id"]),
        raw_artifact_id=cast(UUID, row["raw_artifact_id"]),
        import_profile_id=cast(UUID, row["import_profile_id"]),
        import_profile_revision_id=cast(UUID, row["import_profile_revision_id"]),
        representation=GovernedDatasetRepresentation(str(row["representation"])),
        data_schema=TabularDataSchema(str(row["data_schema"])),
        data_artifact_id=cast(UUID, row["data_artifact_id"]),
        data_sha256=str(row["data_sha256"]),
        source_dataset_revision_id=cast(UUID | None, row["source_dataset_revision_id"]),
        row_count=int(row["row_count"]),
        channels=channels,
    )


def _run(row: Any, diagnostics: tuple[ImportDiagnostic, ...] = ()) -> ImportRun:
    return ImportRun(
        id=cast(UUID, row["id"]),
        scope=TenantScope(
            cast(UUID, row["organization_id"]),
            cast(UUID, row["project_id"]),
            str(row["classification"]),
        ),
        test_run_id=cast(UUID, row["test_run_id"]),
        test_run_revision_id=cast(UUID, row["test_run_revision_id"]),
        raw_asset_id=cast(UUID, row["raw_asset_id"]),
        raw_artifact_id=cast(UUID, row["raw_artifact_id"]),
        import_profile_id=cast(UUID, row["import_profile_id"]),
        import_profile_revision_id=cast(UUID, row["import_profile_revision_id"]),
        profile_sha256=str(row["profile_sha256"]),
        idempotency_key=str(row["idempotency_key"]),
        request_sha256=str(row["request_sha256"]),
        status=ImportRunStatus(str(row["status"])),
        started_at=row["started_at"],
        finished_at=row["finished_at"],
        started_by=cast(UUID, row["started_by"]),
        request_id=cast(UUID, row["request_id"]),
        trace_id=str(row["trace_id"]),
        raw_dataset_id=cast(UUID | None, row["raw_dataset_id"]),
        raw_dataset_revision_id=cast(UUID | None, row["raw_dataset_revision_id"]),
        normalized_dataset_id=cast(UUID | None, row["normalized_dataset_id"]),
        normalized_dataset_revision_id=cast(UUID | None, row["normalized_dataset_revision_id"]),
        row_count=cast(int | None, row["row_count"]),
        failure_code=cast(str | None, row["failure_code"]),
        failure_detail=cast(str | None, row["failure_detail"]),
        diagnostics=diagnostics,
    )


def _diagnostics(rows: Sequence[Any]) -> tuple[ImportDiagnostic, ...]:
    return tuple(
        ImportDiagnostic(
            ordinal=int(row["ordinal"]),
            row_number=cast(int | None, row["row_number"]),
            column_name=cast(str | None, row["column_name"]),
            channel_key=cast(str | None, row["channel_key"]),
            error_code=str(row["error_code"]),
            error_detail=str(row["error_detail"]),
            recovery_hint=str(row["recovery_hint"]),
        )
        for row in rows
    )


class SqlAlchemyGovernedImportRepository(GovernedImportRepository):
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

    def profile_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[GovernedImportProfileContent]:
        return SqlAlchemyRevisionStore(
            session_factory=self._sessions,
            tables=_PROFILE_TABLES,
            hooks=self._hooks,
            session_binder=lambda session: self._bind(session, context, decision),
        )

    def dataset_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[GovernedDatasetContent]:
        return SqlAlchemyRevisionStore(
            session_factory=self._sessions,
            tables=_DATASET_TABLES,
            hooks=self._hooks,
            session_binder=lambda session: self._bind(session, context, decision),
        )

    @staticmethod
    def _load_channels(
        session: Session, table: sa.Table, field: str, revision_id: UUID
    ) -> tuple[GovernedChannelMapping, ...]:
        rows = (
            session.execute(
                sa.select(table).where(table.c[field] == revision_id).order_by(table.c.ordinal)
            )
            .mappings()
            .all()
        )
        return _channels(rows)

    def _profile_snapshot(self, session: Session, row: Any) -> ImportProfileSnapshot:
        channels = self._load_channels(
            session,
            import_profile_channel_table,
            "import_profile_revision_id",
            cast(UUID, row["id"]),
        )
        record = _record(row, IMPORT_PROFILE_AGGREGATE_TYPE)
        return ImportProfileSnapshot(
            record.aggregate_id, RevisionSnapshot(record, _profile(row, channels))
        )

    def get_profile(
        self, *, context: SecurityContext, decision: AuthorizationDecision, profile_id: UUID
    ) -> ImportProfileSnapshot:
        with self._session(context, decision) as session:
            row = (
                session.execute(
                    sa.select(import_profile_revision_table)
                    .join(
                        import_profile_table,
                        import_profile_table.c.current_revision_id
                        == import_profile_revision_table.c.id,
                    )
                    .where(import_profile_table.c.id == profile_id)
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise GovernedImportNotFound("Import Profile is not visible")
            return self._profile_snapshot(session, row)

    def get_profile_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        profile_id: UUID,
        revision_id: UUID,
    ) -> ImportProfileRevisionSnapshot:
        with self._session(context, decision) as session:
            row = (
                session.execute(
                    sa.select(import_profile_revision_table).where(
                        import_profile_revision_table.c.aggregate_id == profile_id,
                        import_profile_revision_table.c.id == revision_id,
                    )
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise GovernedImportNotFound("Import Profile revision is not visible")
            channels = self._load_channels(
                session, import_profile_channel_table, "import_profile_revision_id", revision_id
            )
            record = _record(row, IMPORT_PROFILE_AGGREGATE_TYPE)
            return ImportProfileRevisionSnapshot(
                profile_id, RevisionSnapshot(record, _profile(row, channels))
            )

    def list_profiles(
        self, *, context: SecurityContext, decision: AuthorizationDecision
    ) -> tuple[ImportProfileSnapshot, ...]:
        with self._session(context, decision) as session:
            rows = (
                session.execute(
                    sa.select(import_profile_revision_table)
                    .join(
                        import_profile_table,
                        import_profile_table.c.current_revision_id
                        == import_profile_revision_table.c.id,
                    )
                    .order_by(import_profile_table.c.updated_at.desc(), import_profile_table.c.id)
                )
                .mappings()
                .all()
            )
            return tuple(self._profile_snapshot(session, row) for row in rows)

    def save_preview(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        preview_id: UUID,
        classification: DataClassification,
        preview: TabularPreview,
        created_at: Any,
    ) -> None:
        values = {
            "id": preview_id,
            "organization_id": context.organization_id,
            "project_id": context.project_id,
            "classification": classification.value,
            "raw_asset_id": preview.raw_asset_id,
            "raw_artifact_id": preview.raw_artifact_id,
            "raw_sha256": preview.raw_sha256,
            "file_format": preview.file_format.value,
            "selected_sheet_name": preview.selected_sheet_name,
            "header_row": preview.header_row,
            "encoding": preview.encoding,
            "delimiter": preview.delimiter,
            "decimal_separator": preview.decimal_separator,
            "status": preview.status,
            "report_sha256": preview.digest,
            "created_at": created_at,
            "created_by": context.principal.id,
            "request_id": context.request_id,
            "trace_id": context.trace_id,
        }
        with self._session(context, decision) as session:
            session.execute(sa.insert(preview_table).values(**values))
            if preview.header_columns:
                session.execute(
                    sa.insert(preview_column_table),
                    [
                        {
                            "organization_id": context.organization_id,
                            "project_id": context.project_id,
                            "classification": classification.value,
                            "preview_report_id": preview_id,
                            "ordinal": ordinal,
                            "column_name": column,
                        }
                        for ordinal, column in enumerate(preview.header_columns)
                    ],
                )

    def create_run(
        self, *, context: SecurityContext, decision: AuthorizationDecision, run: ImportRun
    ) -> ImportRun:
        with self._session(context, decision) as session:
            row = (
                session.execute(
                    postgresql_insert(import_run_table)
                    .values(
                        id=run.id,
                        organization_id=run.scope.organization_id,
                        project_id=run.scope.project_id,
                        classification=run.scope.classification,
                        test_run_id=run.test_run_id,
                        test_run_revision_id=run.test_run_revision_id,
                        raw_asset_id=run.raw_asset_id,
                        raw_artifact_id=run.raw_artifact_id,
                        import_profile_id=run.import_profile_id,
                        import_profile_revision_id=run.import_profile_revision_id,
                        profile_sha256=run.profile_sha256,
                        idempotency_key=run.idempotency_key,
                        request_sha256=run.request_sha256,
                        importer_id=GOVERNED_IMPORTER_ID,
                        importer_version=GOVERNED_IMPORTER_VERSION,
                        status=run.status.value,
                        started_at=run.started_at,
                        finished_at=None,
                        started_by=run.started_by,
                        request_id=run.request_id,
                        trace_id=run.trace_id,
                    )
                    .on_conflict_do_nothing()
                    .returning(import_run_table)
                )
                .mappings()
                .one_or_none()
            )
            if row is not None:
                return _run(row)
            existing = (
                session.execute(
                    sa.select(import_run_table).where(
                        import_run_table.c.organization_id == context.organization_id,
                        import_run_table.c.project_id == context.project_id,
                        import_run_table.c.idempotency_key == run.idempotency_key,
                    )
                )
                .mappings()
                .one_or_none()
            )
            if existing is None:
                raise GovernedImportConflict("Import Run identity is already in use")
            if str(existing["request_sha256"]) != run.request_sha256:
                raise GovernedImportConflict(
                    "Import Run idempotency key was reused with different immutable inputs"
                )
            diagnostics = (
                session.execute(
                    sa.select(import_row_error_table)
                    .where(import_row_error_table.c.import_run_id == existing["id"])
                    .order_by(import_row_error_table.c.ordinal)
                )
                .mappings()
                .all()
            )
            return _run(existing, _diagnostics(diagnostics))

    def commit_success(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CommitGovernedImportSuccess,
    ) -> ImportRun:
        normalized_content: GovernedDatasetContent
        with self._session(context, decision) as session:
            run_row = (
                session.execute(
                    sa.select(import_run_table)
                    .where(
                        import_run_table.c.id == command.run_id,
                        import_run_table.c.status == ImportRunStatus.EXECUTING.value,
                    )
                    .with_for_update()
                )
                .mappings()
                .one_or_none()
            )
            if run_row is None:
                raise GovernedImportNotFound("executing Import Run is not visible")
            executing_run = _run(run_row)
            if executing_run.scope != command.scope or (
                command.raw_content.test_run_id,
                command.raw_content.test_run_revision_id,
                command.raw_content.raw_asset_id,
                command.raw_content.raw_artifact_id,
                command.raw_content.import_profile_id,
                command.raw_content.import_profile_revision_id,
            ) != (
                executing_run.test_run_id,
                executing_run.test_run_revision_id,
                executing_run.raw_asset_id,
                executing_run.raw_artifact_id,
                executing_run.import_profile_id,
                executing_run.import_profile_revision_id,
            ):
                raise GovernedImportConflict(
                    "governed Dataset commit does not match the executing Import Run"
                )
            store = SqlAlchemyRevisionStore(
                session_factory=self._sessions,
                tables=_DATASET_TABLES,
                hooks=self._hooks,
            )
            revision_service = RevisionService(
                aggregate_type=GOVERNED_DATASET_AGGREGATE_TYPE,
                store=store,
            )
            transaction = store.transaction_in(session)
            raw_record = revision_service.create_in(
                transaction,
                CreateRevisionedAggregate(
                    aggregate_id=command.raw_dataset_id,
                    scope=command.scope,
                    schema_id=GOVERNED_DATASET_SCHEMA_ID,
                    schema_version=SCHEMA_VERSION,
                    content=command.raw_content,
                    created_by=context.principal.id,
                    change_reason=command.raw_change_reason,
                    request_id=context.request_id,
                    trace_id=context.trace_id,
                ),
            )
            normalized_content = replace(
                command.raw_content,
                representation=GovernedDatasetRepresentation.NORMALIZED,
                data_artifact_id=command.normalized_artifact_id,
                data_sha256=command.normalized_artifact_sha256,
                source_dataset_revision_id=raw_record.revision_id,
            )
            normalized_record = revision_service.create_in(
                transaction,
                CreateRevisionedAggregate(
                    aggregate_id=command.normalized_dataset_id,
                    scope=command.scope,
                    schema_id=GOVERNED_DATASET_SCHEMA_ID,
                    schema_version=SCHEMA_VERSION,
                    content=normalized_content,
                    created_by=context.principal.id,
                    change_reason=command.normalized_change_reason,
                    request_id=context.request_id,
                    trace_id=context.trace_id,
                ),
            )
            result = (
                session.execute(
                    sa.update(import_run_table)
                    .where(
                        import_run_table.c.id == command.run_id,
                        import_run_table.c.status == ImportRunStatus.EXECUTING.value,
                    )
                    .values(
                        status=ImportRunStatus.SUCCEEDED.value,
                        finished_at=command.finished_at,
                        raw_dataset_id=command.raw_dataset_id,
                        raw_dataset_revision_id=raw_record.revision_id,
                        normalized_dataset_id=command.normalized_dataset_id,
                        normalized_dataset_revision_id=normalized_record.revision_id,
                        row_count=command.raw_content.row_count,
                    )
                    .returning(import_run_table)
                )
                .mappings()
                .one_or_none()
            )
            if result is None:
                raise GovernedImportNotFound("executing Import Run is not visible")
            return _run(result)

    def fail_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
        finished_at: Any,
        failure_code: str,
        failure_detail: str,
        diagnostics: tuple[ImportDiagnostic, ...],
    ) -> ImportRun:
        with self._session(context, decision) as session:
            row = (
                session.execute(
                    sa.update(import_run_table)
                    .where(
                        import_run_table.c.id == run_id,
                        import_run_table.c.status == ImportRunStatus.EXECUTING.value,
                    )
                    .values(
                        status=ImportRunStatus.FAILED.value,
                        finished_at=finished_at,
                        failure_code=failure_code,
                        failure_detail=failure_detail,
                    )
                    .returning(import_run_table)
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise GovernedImportNotFound("executing Import Run is not visible")
            result = _run(row)
            session.execute(
                sa.insert(import_row_error_table),
                [
                    {
                        "organization_id": result.scope.organization_id,
                        "project_id": result.scope.project_id,
                        "classification": result.scope.classification,
                        "import_run_id": result.id,
                        "ordinal": diagnostic.ordinal,
                        "row_number": diagnostic.row_number,
                        "column_name": diagnostic.column_name,
                        "channel_key": diagnostic.channel_key,
                        "error_code": diagnostic.error_code,
                        "error_detail": diagnostic.error_detail,
                        "recovery_hint": diagnostic.recovery_hint,
                    }
                    for diagnostic in diagnostics
                ],
            )
        return replace(result, diagnostics=diagnostics)

    def get_run(
        self, *, context: SecurityContext, decision: AuthorizationDecision, run_id: UUID
    ) -> ImportRun:
        with self._session(context, decision) as session:
            row = (
                session.execute(sa.select(import_run_table).where(import_run_table.c.id == run_id))
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise GovernedImportNotFound("Import Run is not visible")
            diagnostic_rows = (
                session.execute(
                    sa.select(import_row_error_table)
                    .where(import_row_error_table.c.import_run_id == run_id)
                    .order_by(import_row_error_table.c.ordinal)
                )
                .mappings()
                .all()
            )
            return _run(row, _diagnostics(diagnostic_rows))

    def get_dataset(
        self, *, context: SecurityContext, decision: AuthorizationDecision, dataset_id: UUID
    ) -> GovernedDatasetSnapshot:
        with self._session(context, decision) as session:
            row = (
                session.execute(
                    sa.select(governed_dataset_revision_table)
                    .join(
                        governed_dataset_table,
                        governed_dataset_table.c.current_revision_id
                        == governed_dataset_revision_table.c.id,
                    )
                    .where(governed_dataset_table.c.id == dataset_id)
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise GovernedImportNotFound("governed Dataset is not visible")
            revision_id = cast(UUID, row["id"])
            channels = self._load_channels(
                session, governed_dataset_channel_table, "dataset_revision_id", revision_id
            )
            record = _record(row, GOVERNED_DATASET_AGGREGATE_TYPE)
            return GovernedDatasetSnapshot(
                dataset_id, RevisionSnapshot(record, _dataset(row, channels))
            )

    def get_dataset_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        dataset_id: UUID,
        dataset_revision_id: UUID,
    ) -> RevisionSnapshot[GovernedDatasetContent]:
        with self._session(context, decision) as session:
            row = (
                session.execute(
                    sa.select(governed_dataset_revision_table).where(
                        governed_dataset_revision_table.c.aggregate_id == dataset_id,
                        governed_dataset_revision_table.c.id == dataset_revision_id,
                    )
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise GovernedImportNotFound("governed Dataset revision is not visible")
            channels = self._load_channels(
                session,
                governed_dataset_channel_table,
                "dataset_revision_id",
                dataset_revision_id,
            )
            return RevisionSnapshot(
                _record(row, GOVERNED_DATASET_AGGREGATE_TYPE),
                _dataset(row, channels),
            )

    def list_datasets_for_test_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        test_run_id: UUID,
    ) -> tuple[GovernedDatasetSnapshot, ...]:
        with self._session(context, decision) as session:
            rows = (
                session.execute(
                    sa.select(governed_dataset_revision_table)
                    .join(
                        governed_dataset_table,
                        governed_dataset_table.c.current_revision_id
                        == governed_dataset_revision_table.c.id,
                    )
                    .where(governed_dataset_revision_table.c.test_run_id == test_run_id)
                    .order_by(
                        governed_dataset_revision_table.c.representation.desc(),
                        governed_dataset_revision_table.c.created_at.desc(),
                    )
                )
                .mappings()
                .all()
            )
            result: list[GovernedDatasetSnapshot] = []
            for row in rows:
                revision_id = cast(UUID, row["id"])
                channels = self._load_channels(
                    session,
                    governed_dataset_channel_table,
                    "dataset_revision_id",
                    revision_id,
                )
                record = _record(row, GOVERNED_DATASET_AGGREGATE_TYPE)
                result.append(
                    GovernedDatasetSnapshot(
                        record.aggregate_id,
                        RevisionSnapshot(record, _dataset(row, channels)),
                    )
                )
            return tuple(result)

"""PostgreSQL persistence for explicit Specimen, Test Method, and Test Run revisions."""

from __future__ import annotations

from collections.abc import Sequence
from contextlib import contextmanager
from typing import Any, Protocol, cast
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session, sessionmaker

from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.testing.application.service import (
    IMPORT_MAPPING_AGGREGATE_TYPE,
    SPECIMEN_AGGREGATE_TYPE,
    TEST_METHOD_AGGREGATE_TYPE,
    TEST_RUN_AGGREGATE_TYPE,
    ImportDetectionReportSnapshot,
    ImportMappingRevisionSnapshot,
    ImportMappingSnapshot,
    MaterialStateSource,
    RevisionSnapshot,
    SpecimenSnapshot,
    TestingRepository,
    TestMethodSnapshot,
    TestRunSnapshot,
)
from cmp.modules.testing.domain.import_mapping import (
    ImportDetectionStatus,
    MappingSuggestionConfidence,
    ReferenceImportMappingContent,
    SyntheticCsvDetectionReport,
    reference_import_mapping_canonical,
)
from cmp.modules.testing.domain.reference_tensile import (
    SpecimenContent,
    TestingNotFound,
    TestMethodContent,
    TestRunContent,
    specimen_canonical,
    test_method_canonical,
    test_run_canonical,
)
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

specimen_table = sa.Table(
    "specimen",
    metadata,
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("material_state_id", sa.Uuid(), nullable=False),
    sa.Column("specimen_code", sa.String(100), nullable=False),
    sa.Column("current_revision_id", sa.Uuid(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("created_by", sa.Uuid(), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    schema="testing",
)
specimen_revision_table = sa.Table(
    "specimen_revision",
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
    sa.Column("material_id", sa.Uuid(), nullable=False),
    sa.Column("material_revision_id", sa.Uuid(), nullable=False),
    sa.Column("material_state_id", sa.Uuid(), nullable=False),
    sa.Column("material_state_revision_id", sa.Uuid(), nullable=False),
    sa.Column("specimen_code", sa.String(100), nullable=False),
    sa.Column("orientation", sa.String(100), nullable=True),
    sa.Column("preparation_note", sa.Text(), nullable=True),
    schema="testing",
)
test_method_table = sa.Table(
    "test_method",
    metadata,
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("method_code", sa.String(100), nullable=False),
    sa.Column("current_revision_id", sa.Uuid(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("created_by", sa.Uuid(), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
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
    sa.Column("method_code", sa.String(100), nullable=False),
    sa.Column("display_name", sa.String(160), nullable=False),
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
    sa.Column("test_method_id", sa.Uuid(), nullable=False),
    sa.Column("run_label", sa.String(160), nullable=False),
    sa.Column("current_revision_id", sa.Uuid(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("created_by", sa.Uuid(), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    schema="testing",
)
test_run_revision_table = sa.Table(
    "test_run_revision",
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
    sa.Column("specimen_id", sa.Uuid(), nullable=False),
    sa.Column("specimen_revision_id", sa.Uuid(), nullable=False),
    sa.Column("test_method_id", sa.Uuid(), nullable=False),
    sa.Column("test_method_revision_id", sa.Uuid(), nullable=False),
    sa.Column("run_label", sa.String(160), nullable=False),
    sa.Column("performed_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("test_temperature_k", sa.Double(), nullable=True),
    sa.Column("crosshead_speed_mm_per_min", sa.Double(), nullable=True),
    sa.Column("reference_only", sa.Boolean(), nullable=False),
    schema="testing",
)
import_detection_report_table = sa.Table(
    "import_detection_report",
    metadata,
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("raw_asset_id", sa.Uuid(), nullable=False),
    sa.Column("raw_artifact_id", sa.Uuid(), nullable=False),
    sa.Column("raw_sha256", sa.CHAR(64), nullable=False),
    sa.Column("importer_id", sa.String(255), nullable=False),
    sa.Column("importer_version", sa.String(64), nullable=False),
    sa.Column("status", sa.String(32), nullable=False),
    sa.Column("header_columns", sa.ARRAY(sa.String(255)), nullable=False),
    sa.Column("suggested_strain_column", sa.String(255), nullable=True),
    sa.Column("suggested_strain_unit", sa.String(16), nullable=True),
    sa.Column("strain_confidence", sa.String(16), nullable=False),
    sa.Column("suggested_stress_column", sa.String(255), nullable=True),
    sa.Column("suggested_stress_unit", sa.String(16), nullable=True),
    sa.Column("stress_confidence", sa.String(16), nullable=False),
    sa.Column("report_sha256", sa.CHAR(64), nullable=False),
    sa.Column("reference_only", sa.Boolean(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("created_by", sa.Uuid(), nullable=False),
    sa.Column("request_id", sa.Uuid(), nullable=False),
    sa.Column("trace_id", sa.String(255), nullable=False),
    schema="testing",
)
import_mapping_table = sa.Table(
    "import_mapping",
    metadata,
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("mapping_label", sa.String(160), nullable=False),
    sa.Column("raw_asset_id", sa.Uuid(), nullable=False),
    sa.Column("raw_artifact_id", sa.Uuid(), nullable=False),
    sa.Column("importer_id", sa.String(255), nullable=False),
    sa.Column("importer_version", sa.String(64), nullable=False),
    sa.Column("current_revision_id", sa.Uuid(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("created_by", sa.Uuid(), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    schema="testing",
)
import_mapping_revision_table = sa.Table(
    "import_mapping_revision",
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
    sa.Column("detection_report_id", sa.Uuid(), nullable=False),
    sa.Column("raw_asset_id", sa.Uuid(), nullable=False),
    sa.Column("raw_artifact_id", sa.Uuid(), nullable=False),
    sa.Column("strain_column", sa.String(255), nullable=False),
    sa.Column("stress_column", sa.String(255), nullable=False),
    sa.Column("strain_original_unit", sa.String(16), nullable=False),
    sa.Column("stress_original_unit", sa.String(16), nullable=False),
    sa.Column("dataset_mapping_sha256", sa.CHAR(64), nullable=False),
    sa.Column("importer_id", sa.String(255), nullable=False),
    sa.Column("importer_version", sa.String(64), nullable=False),
    sa.Column("approval_kind", sa.String(32), nullable=False),
    sa.Column("reference_only", sa.Boolean(), nullable=False),
    schema="testing",
)
catalog_material_state_revision_table = sa.Table(
    "material_state_revision",
    metadata,
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("aggregate_id", sa.Uuid(), nullable=False),
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("material_id", sa.Uuid(), nullable=False),
    sa.Column("material_revision_id", sa.Uuid(), nullable=False),
    schema="catalog",
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


def _specimen_content(row: Any) -> SpecimenContent:
    return SpecimenContent(
        material_id=cast(UUID, row["material_id"]),
        material_revision_id=cast(UUID, row["material_revision_id"]),
        material_state_id=cast(UUID, row["material_state_id"]),
        material_state_revision_id=cast(UUID, row["material_state_revision_id"]),
        specimen_code=str(row["specimen_code"]),
        orientation=str(row["orientation"]) if row["orientation"] is not None else None,
        preparation_note=(
            str(row["preparation_note"]) if row["preparation_note"] is not None else None
        ),
    )


def _method_content(row: Any) -> TestMethodContent:
    return TestMethodContent(
        method_code=str(row["method_code"]),
        display_name=str(row["display_name"]),
        reference_only=bool(row["reference_only"]),
    )


def _run_content(row: Any) -> TestRunContent:
    return TestRunContent(
        specimen_id=cast(UUID, row["specimen_id"]),
        specimen_revision_id=cast(UUID, row["specimen_revision_id"]),
        test_method_id=cast(UUID, row["test_method_id"]),
        test_method_revision_id=cast(UUID, row["test_method_revision_id"]),
        run_label=str(row["run_label"]),
        performed_at=row["performed_at"],
        test_temperature_k=(
            float(row["test_temperature_k"])
            if row["test_temperature_k"] is not None
            else None
        ),
        crosshead_speed_mm_per_min=(
            float(row["crosshead_speed_mm_per_min"])
            if row["crosshead_speed_mm_per_min"] is not None
            else None
        ),
        reference_only=bool(row["reference_only"]),
    )


def _detection_snapshot(row: Any) -> ImportDetectionReportSnapshot:
    report = SyntheticCsvDetectionReport(
        raw_asset_id=cast(UUID, row["raw_asset_id"]),
        raw_artifact_id=cast(UUID, row["raw_artifact_id"]),
        raw_sha256=str(row["raw_sha256"]),
        header_columns=tuple(cast(list[str], row["header_columns"])),
        status=ImportDetectionStatus(str(row["status"])),
        suggested_strain_column=(
            str(row["suggested_strain_column"])
            if row["suggested_strain_column"] is not None
            else None
        ),
        suggested_strain_unit=(
            str(row["suggested_strain_unit"])
            if row["suggested_strain_unit"] is not None
            else None
        ),
        strain_confidence=MappingSuggestionConfidence(str(row["strain_confidence"])),
        suggested_stress_column=(
            str(row["suggested_stress_column"])
            if row["suggested_stress_column"] is not None
            else None
        ),
        suggested_stress_unit=(
            str(row["suggested_stress_unit"])
            if row["suggested_stress_unit"] is not None
            else None
        ),
        stress_confidence=MappingSuggestionConfidence(str(row["stress_confidence"])),
        importer_id=str(row["importer_id"]),
        importer_version=str(row["importer_version"]),
        reference_only=bool(row["reference_only"]),
    )
    if report.digest != str(row["report_sha256"]):
        raise TestingNotFound("Import Detection Report digest is inconsistent")
    return ImportDetectionReportSnapshot(
        id=cast(UUID, row["id"]),
        classification=DataClassification(str(row["classification"])),
        report=report,
        created_at=row["created_at"],
        created_by=cast(UUID, row["created_by"]),
        request_id=cast(UUID, row["request_id"]),
        trace_id=str(row["trace_id"]),
    )


def _mapping_content(row: Any) -> ReferenceImportMappingContent:
    content = ReferenceImportMappingContent(
        mapping_label=str(row["mapping_label"]),
        detection_report_id=cast(UUID, row["detection_report_id"]),
        raw_asset_id=cast(UUID, row["raw_asset_id"]),
        raw_artifact_id=cast(UUID, row["raw_artifact_id"]),
        strain_column=str(row["strain_column"]),
        stress_column=str(row["stress_column"]),
        strain_unit=str(row["strain_original_unit"]),
        stress_unit=str(row["stress_original_unit"]),
        importer_id=str(row["importer_id"]),
        importer_version=str(row["importer_version"]),
        approval_kind=str(row["approval_kind"]),
        reference_only=bool(row["reference_only"]),
    )
    if content.dataset_mapping_digest != str(row["dataset_mapping_sha256"]):
        raise TestingNotFound("Import Mapping revision digest is inconsistent")
    return content


def _specimen_values(value: SpecimenContent) -> dict[str, object]:
    return {
        "material_id": value.material_id,
        "material_revision_id": value.material_revision_id,
        "material_state_id": value.material_state_id,
        "material_state_revision_id": value.material_state_revision_id,
        "specimen_code": value.specimen_code,
        "orientation": value.orientation,
        "preparation_note": value.preparation_note,
    }


def _method_values(value: TestMethodContent) -> dict[str, object]:
    return {
        "method_code": value.method_code,
        "display_name": value.display_name,
        "reference_only": value.reference_only,
    }


def _run_values(value: TestRunContent) -> dict[str, object]:
    return {
        "specimen_id": value.specimen_id,
        "specimen_revision_id": value.specimen_revision_id,
        "test_method_id": value.test_method_id,
        "test_method_revision_id": value.test_method_revision_id,
        "run_label": value.run_label,
        "performed_at": value.performed_at,
        "test_temperature_k": value.test_temperature_k,
        "crosshead_speed_mm_per_min": value.crosshead_speed_mm_per_min,
        "reference_only": value.reference_only,
    }


def _mapping_values(value: ReferenceImportMappingContent) -> dict[str, object]:
    return {
        "detection_report_id": value.detection_report_id,
        "raw_asset_id": value.raw_asset_id,
        "raw_artifact_id": value.raw_artifact_id,
        "strain_column": value.strain_column,
        "stress_column": value.stress_column,
        "strain_original_unit": value.strain_unit,
        "stress_original_unit": value.stress_unit,
        "dataset_mapping_sha256": value.dataset_mapping_digest,
        "importer_id": value.importer_id,
        "importer_version": value.importer_version,
        "approval_kind": value.approval_kind,
        "reference_only": value.reference_only,
    }


_SPECIMEN_TABLES: TypedRevisionTables[SpecimenContent] = TypedRevisionTables(
    aggregate_type=SPECIMEN_AGGREGATE_TYPE,
    identity_table=specimen_table,
    revision_table=specimen_revision_table,
    canonical_content=specimen_canonical,
    content_values=_specimen_values,
    identity_values=lambda value: {
        "material_state_id": value.material_state_id,
        "specimen_code": value.specimen_code,
    },
)
_METHOD_TABLES: TypedRevisionTables[TestMethodContent] = TypedRevisionTables(
    aggregate_type=TEST_METHOD_AGGREGATE_TYPE,
    identity_table=test_method_table,
    revision_table=test_method_revision_table,
    canonical_content=test_method_canonical,
    content_values=_method_values,
    identity_values=lambda value: {"method_code": value.method_code},
)
_RUN_TABLES: TypedRevisionTables[TestRunContent] = TypedRevisionTables(
    aggregate_type=TEST_RUN_AGGREGATE_TYPE,
    identity_table=test_run_table,
    revision_table=test_run_revision_table,
    canonical_content=test_run_canonical,
    content_values=_run_values,
    identity_values=lambda value: {
        "specimen_id": value.specimen_id,
        "test_method_id": value.test_method_id,
        "run_label": value.run_label,
    },
)
_IMPORT_MAPPING_TABLES: TypedRevisionTables[ReferenceImportMappingContent] = TypedRevisionTables(
    aggregate_type=IMPORT_MAPPING_AGGREGATE_TYPE,
    identity_table=import_mapping_table,
    revision_table=import_mapping_revision_table,
    canonical_content=reference_import_mapping_canonical,
    content_values=_mapping_values,
    identity_values=lambda value: {
        "mapping_label": value.mapping_label,
        "raw_asset_id": value.raw_asset_id,
        "raw_artifact_id": value.raw_artifact_id,
        "importer_id": value.importer_id,
        "importer_version": value.importer_version,
    },
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


class SqlAlchemyTestingRepository(TestingRepository):
    """Use one RLS-bound transaction per typed testing aggregate command."""

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

    def _store[ContentT](
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        tables: TypedRevisionTables[ContentT],
    ) -> RevisionStore[ContentT]:
        return SqlAlchemyRevisionStore(
            session_factory=self._sessions,
            tables=tables,
            hooks=self._hooks,
            session_binder=lambda session: self._bind(session, context, decision),
        )

    def specimen_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[SpecimenContent]:
        return self._store(context, decision, _SPECIMEN_TABLES)

    def test_method_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[TestMethodContent]:
        return self._store(context, decision, _METHOD_TABLES)

    def test_run_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[TestRunContent]:
        return self._store(context, decision, _RUN_TABLES)

    def import_mapping_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[ReferenceImportMappingContent]:
        return self._store(context, decision, _IMPORT_MAPPING_TABLES)

    def create_import_detection_report(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        report: ImportDetectionReportSnapshot,
    ) -> ImportDetectionReportSnapshot:
        values = {
            "id": report.id,
            "organization_id": context.organization_id,
            "project_id": context.project_id,
            "classification": report.classification.value,
            "raw_asset_id": report.report.raw_asset_id,
            "raw_artifact_id": report.report.raw_artifact_id,
            "raw_sha256": report.report.raw_sha256,
            "importer_id": report.report.importer_id,
            "importer_version": report.report.importer_version,
            "status": report.report.status.value,
            "header_columns": list(report.report.header_columns),
            "suggested_strain_column": report.report.suggested_strain_column,
            "suggested_strain_unit": report.report.suggested_strain_unit,
            "strain_confidence": report.report.strain_confidence.value,
            "suggested_stress_column": report.report.suggested_stress_column,
            "suggested_stress_unit": report.report.suggested_stress_unit,
            "stress_confidence": report.report.stress_confidence.value,
            "report_sha256": report.report.digest,
            "reference_only": report.report.reference_only,
            "created_at": report.created_at,
            "created_by": report.created_by,
            "request_id": report.request_id,
            "trace_id": report.trace_id,
        }
        with self._session(context, decision) as session:
            session.execute(sa.insert(import_detection_report_table).values(**values))
        return report

    def get_import_detection_report(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        detection_report_id: UUID,
    ) -> ImportDetectionReportSnapshot:
        statement = sa.select(import_detection_report_table).where(
            import_detection_report_table.c.organization_id == context.organization_id,
            import_detection_report_table.c.project_id == context.project_id,
            import_detection_report_table.c.id == detection_report_id,
        )
        with self._session(context, decision) as session:
            row = session.execute(statement).mappings().one_or_none()
        if row is None:
            raise TestingNotFound("Import Detection Report is not visible in the selected tenant")
        return _detection_snapshot(row)

    def load_material_state_source(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_state_id: UUID,
        material_state_revision_id: UUID,
        specimen_code: str,
        orientation: str | None,
        preparation_note: str | None,
    ) -> MaterialStateSource:
        state = catalog_material_state_revision_table
        statement = sa.select(
            state.c.classification,
            state.c.material_id,
            state.c.material_revision_id,
            state.c.aggregate_id.label("material_state_id"),
            state.c.id.label("material_state_revision_id"),
        ).where(
            state.c.organization_id == context.organization_id,
            state.c.project_id == context.project_id,
            state.c.aggregate_id == material_state_id,
            state.c.id == material_state_revision_id,
        )
        with self._session(context, decision) as session:
            try:
                row = session.execute(statement).mappings().one_or_none()
            except DBAPIError as error:
                raise TestingNotFound("Material State revision is not available") from error
        if row is None:
            raise TestingNotFound("Material State revision is not visible in the selected tenant")
        content = SpecimenContent(
            material_id=cast(UUID, row["material_id"]),
            material_revision_id=cast(UUID, row["material_revision_id"]),
            material_state_id=cast(UUID, row["material_state_id"]),
            material_state_revision_id=cast(UUID, row["material_state_revision_id"]),
            specimen_code=specimen_code,
            orientation=orientation,
            preparation_note=preparation_note,
        )
        return MaterialStateSource(DataClassification(str(row["classification"])), content)

    def load_specimen_source(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        specimen_id: UUID,
        specimen_revision_id: UUID,
    ) -> tuple[DataClassification, SpecimenContent]:
        revision = specimen_revision_table
        statement = sa.select(*_revision_columns(revision), *(
            revision.c[name].label(name)
            for name in (
                "material_id",
                "material_revision_id",
                "material_state_id",
                "material_state_revision_id",
                "specimen_code",
                "orientation",
                "preparation_note",
            )
        )).where(
            revision.c.organization_id == context.organization_id,
            revision.c.project_id == context.project_id,
            revision.c.aggregate_id == specimen_id,
            revision.c.id == specimen_revision_id,
        )
        with self._session(context, decision) as session:
            row = session.execute(statement).mappings().one_or_none()
        if row is None:
            raise TestingNotFound("Specimen revision is not visible in the selected tenant")
        return DataClassification(str(row["classification"])), _specimen_content(row)

    def load_test_method_source(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        test_method_id: UUID,
        test_method_revision_id: UUID,
    ) -> tuple[DataClassification, TestMethodContent]:
        revision = test_method_revision_table
        statement = sa.select(
            *_revision_columns(revision),
            revision.c.method_code,
            revision.c.display_name,
            revision.c.reference_only,
        ).where(
            revision.c.organization_id == context.organization_id,
            revision.c.project_id == context.project_id,
            revision.c.aggregate_id == test_method_id,
            revision.c.id == test_method_revision_id,
        )
        with self._session(context, decision) as session:
            row = session.execute(statement).mappings().one_or_none()
        if row is None:
            raise TestingNotFound("Test Method revision is not visible in the selected tenant")
        return DataClassification(str(row["classification"])), _method_content(row)

    @staticmethod
    def _specimen_snapshot(row: Any) -> SpecimenSnapshot:
        return SpecimenSnapshot(
            id=cast(UUID, row["identity_id"]),
            material_state_id=cast(UUID, row["identity_material_state_id"]),
            current=RevisionSnapshot(
                _record(row, SPECIMEN_AGGREGATE_TYPE), _specimen_content(row)
            ),
        )

    @staticmethod
    def _method_snapshot(row: Any) -> TestMethodSnapshot:
        return TestMethodSnapshot(
            id=cast(UUID, row["identity_id"]),
            current=RevisionSnapshot(
                _record(row, TEST_METHOD_AGGREGATE_TYPE), _method_content(row)
            ),
        )

    @staticmethod
    def _run_snapshot(row: Any) -> TestRunSnapshot:
        return TestRunSnapshot(
            id=cast(UUID, row["identity_id"]),
            specimen_id=cast(UUID, row["identity_specimen_id"]),
            test_method_id=cast(UUID, row["identity_test_method_id"]),
            current=RevisionSnapshot(_record(row, TEST_RUN_AGGREGATE_TYPE), _run_content(row)),
        )

    @staticmethod
    def _mapping_snapshot(row: Any) -> ImportMappingSnapshot:
        return ImportMappingSnapshot(
            id=cast(UUID, row["identity_id"]),
            current=RevisionSnapshot(
                _record(row, IMPORT_MAPPING_AGGREGATE_TYPE), _mapping_content(row)
            ),
        )

    @staticmethod
    def _current_specimen_statement() -> sa.Select[Any]:
        identity = specimen_table
        revision = specimen_revision_table
        return sa.select(
            identity.c.id.label("identity_id"),
            identity.c.material_state_id.label("identity_material_state_id"),
            *_revision_columns(revision),
            revision.c.material_id,
            revision.c.material_revision_id,
            revision.c.material_state_id,
            revision.c.material_state_revision_id,
            revision.c.specimen_code,
            revision.c.orientation,
            revision.c.preparation_note,
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
        )

    @staticmethod
    def _current_method_statement() -> sa.Select[Any]:
        identity = test_method_table
        revision = test_method_revision_table
        return sa.select(
            identity.c.id.label("identity_id"),
            *_revision_columns(revision),
            revision.c.method_code,
            revision.c.display_name,
            revision.c.reference_only,
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
        )

    @staticmethod
    def _current_run_statement() -> sa.Select[Any]:
        identity = test_run_table
        revision = test_run_revision_table
        return sa.select(
            identity.c.id.label("identity_id"),
            identity.c.specimen_id.label("identity_specimen_id"),
            identity.c.test_method_id.label("identity_test_method_id"),
            *_revision_columns(revision),
            revision.c.specimen_id,
            revision.c.specimen_revision_id,
            revision.c.test_method_id,
            revision.c.test_method_revision_id,
            revision.c.run_label,
            revision.c.performed_at,
            revision.c.test_temperature_k,
            revision.c.crosshead_speed_mm_per_min,
            revision.c.reference_only,
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
        )

    @staticmethod
    def _current_mapping_statement() -> sa.Select[Any]:
        identity = import_mapping_table
        revision = import_mapping_revision_table
        return sa.select(
            identity.c.id.label("identity_id"),
            identity.c.mapping_label,
            *_revision_columns(revision),
            revision.c.detection_report_id,
            revision.c.raw_asset_id,
            revision.c.raw_artifact_id,
            revision.c.strain_column,
            revision.c.stress_column,
            revision.c.strain_original_unit,
            revision.c.stress_original_unit,
            revision.c.dataset_mapping_sha256,
            revision.c.importer_id,
            revision.c.importer_version,
            revision.c.approval_kind,
            revision.c.reference_only,
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
        )

    @staticmethod
    def _mapping_revision_statement() -> sa.Select[Any]:
        identity = import_mapping_table
        revision = import_mapping_revision_table
        return sa.select(
            identity.c.id.label("identity_id"),
            identity.c.mapping_label,
            *_revision_columns(revision),
            revision.c.detection_report_id,
            revision.c.raw_asset_id,
            revision.c.raw_artifact_id,
            revision.c.strain_column,
            revision.c.stress_column,
            revision.c.strain_original_unit,
            revision.c.stress_original_unit,
            revision.c.dataset_mapping_sha256,
            revision.c.importer_id,
            revision.c.importer_version,
            revision.c.approval_kind,
            revision.c.reference_only,
        ).select_from(
            identity.join(
                revision,
                sa.and_(
                    revision.c.aggregate_id == identity.c.id,
                    revision.c.organization_id == identity.c.organization_id,
                    revision.c.project_id == identity.c.project_id,
                ),
            )
        )

    def get_import_mapping(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        mapping_id: UUID,
    ) -> ImportMappingSnapshot:
        statement = self._current_mapping_statement().where(
            import_mapping_table.c.organization_id == context.organization_id,
            import_mapping_table.c.project_id == context.project_id,
            import_mapping_table.c.id == mapping_id,
        )
        with self._session(context, decision) as session:
            row = session.execute(statement).mappings().one_or_none()
        if row is None:
            raise TestingNotFound("Import Mapping is not visible in the selected tenant")
        return self._mapping_snapshot(row)

    def get_import_mapping_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        mapping_id: UUID,
        mapping_revision_id: UUID,
    ) -> ImportMappingRevisionSnapshot:
        statement = self._mapping_revision_statement().where(
            import_mapping_table.c.organization_id == context.organization_id,
            import_mapping_table.c.project_id == context.project_id,
            import_mapping_table.c.id == mapping_id,
            import_mapping_revision_table.c.id == mapping_revision_id,
        )
        with self._session(context, decision) as session:
            row = session.execute(statement).mappings().one_or_none()
        if row is None:
            raise TestingNotFound(
                "Import Mapping revision is not visible in the selected tenant"
            )
        return ImportMappingRevisionSnapshot(
            mapping_id=cast(UUID, row["identity_id"]),
            revision=RevisionSnapshot(
                _record(row, IMPORT_MAPPING_AGGREGATE_TYPE), _mapping_content(row)
            ),
        )

    def get_test_run_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        test_run_id: UUID,
        test_run_revision_id: UUID,
    ) -> RevisionSnapshot[TestRunContent]:
        revision = test_run_revision_table
        statement = sa.select(
            *_revision_columns(revision),
            revision.c.specimen_id,
            revision.c.specimen_revision_id,
            revision.c.test_method_id,
            revision.c.test_method_revision_id,
            revision.c.run_label,
            revision.c.performed_at,
            revision.c.test_temperature_k,
            revision.c.crosshead_speed_mm_per_min,
            revision.c.reference_only,
        ).where(
            revision.c.organization_id == context.organization_id,
            revision.c.project_id == context.project_id,
            revision.c.aggregate_id == test_run_id,
            revision.c.id == test_run_revision_id,
        )
        with self._session(context, decision) as session:
            row = session.execute(statement).mappings().one_or_none()
        if row is None:
            raise TestingNotFound("Test Run revision is not visible in the selected tenant")
        return RevisionSnapshot(
            _record(row, TEST_RUN_AGGREGATE_TYPE), _run_content(row)
        )

    def get_specimen(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        specimen_id: UUID,
    ) -> SpecimenSnapshot:
        statement = self._current_specimen_statement().where(
            specimen_table.c.id == specimen_id,
            specimen_table.c.organization_id == context.organization_id,
            specimen_table.c.project_id == context.project_id,
        )
        with self._session(context, decision) as session:
            row = session.execute(statement).mappings().one_or_none()
        if row is None:
            raise TestingNotFound("Specimen is not visible in the selected tenant")
        return self._specimen_snapshot(row)

    def list_specimens_for_material_state(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_state_id: UUID,
    ) -> tuple[SpecimenSnapshot, ...]:
        statement = self._current_specimen_statement().where(
            specimen_table.c.organization_id == context.organization_id,
            specimen_table.c.project_id == context.project_id,
            specimen_table.c.material_state_id == material_state_id,
        ).order_by(specimen_table.c.created_at.asc())
        with self._session(context, decision) as session:
            rows = session.execute(statement).mappings().all()
        return tuple(self._specimen_snapshot(row) for row in rows)

    def get_test_method(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        test_method_id: UUID,
    ) -> TestMethodSnapshot:
        statement = self._current_method_statement().where(
            test_method_table.c.id == test_method_id,
            test_method_table.c.organization_id == context.organization_id,
            test_method_table.c.project_id == context.project_id,
        )
        with self._session(context, decision) as session:
            row = session.execute(statement).mappings().one_or_none()
        if row is None:
            raise TestingNotFound("Test Method is not visible in the selected tenant")
        return self._method_snapshot(row)

    def list_test_methods(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
    ) -> tuple[TestMethodSnapshot, ...]:
        statement = self._current_method_statement().where(
            test_method_table.c.organization_id == context.organization_id,
            test_method_table.c.project_id == context.project_id,
        ).order_by(test_method_table.c.created_at.asc())
        with self._session(context, decision) as session:
            rows = session.execute(statement).mappings().all()
        return tuple(self._method_snapshot(row) for row in rows)

    def get_test_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        test_run_id: UUID,
    ) -> TestRunSnapshot:
        statement = self._current_run_statement().where(
            test_run_table.c.id == test_run_id,
            test_run_table.c.organization_id == context.organization_id,
            test_run_table.c.project_id == context.project_id,
        )
        with self._session(context, decision) as session:
            row = session.execute(statement).mappings().one_or_none()
        if row is None:
            raise TestingNotFound("Test Run is not visible in the selected tenant")
        return self._run_snapshot(row)

    def list_test_runs_for_material_state(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_state_id: UUID,
    ) -> tuple[TestRunSnapshot, ...]:
        statement = self._current_run_statement().select_from(
            test_run_table.join(
                test_run_revision_table,
                sa.and_(
                    test_run_revision_table.c.id == test_run_table.c.current_revision_id,
                    test_run_revision_table.c.aggregate_id == test_run_table.c.id,
                    test_run_revision_table.c.organization_id == test_run_table.c.organization_id,
                    test_run_revision_table.c.project_id == test_run_table.c.project_id,
                ),
            ).join(
                specimen_table,
                sa.and_(
                    specimen_table.c.id == test_run_table.c.specimen_id,
                    specimen_table.c.organization_id == test_run_table.c.organization_id,
                    specimen_table.c.project_id == test_run_table.c.project_id,
                ),
            )
        ).where(
            test_run_table.c.organization_id == context.organization_id,
            test_run_table.c.project_id == context.project_id,
            specimen_table.c.material_state_id == material_state_id,
        ).order_by(test_run_table.c.created_at.asc())
        with self._session(context, decision) as session:
            rows = session.execute(statement).mappings().all()
        return tuple(self._run_snapshot(row) for row in rows)

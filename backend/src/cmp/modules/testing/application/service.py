"""Create immutable Specimen, Test Method, and Test Run records for the reference CSV slice."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID, uuid4

from cmp.modules.artifacts.application.content import ArtifactService
from cmp.modules.artifacts.domain.content import ArtifactKind, IntegrityStatus
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
    Permission,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.testing.domain.import_mapping import (
    REFERENCE_IMPORT_MAPPING_SCHEMA_ID,
    REFERENCE_IMPORT_MAPPING_SCHEMA_VERSION,
    ReferenceImportMappingContent,
    SyntheticCsvDetectionReport,
    detect_synthetic_csv_header,
)
from cmp.modules.testing.domain.reference_tensile import (
    REFERENCE_SHEAR_RELAXATION_METHOD_CODE,
    REFERENCE_SHEAR_RELAXATION_METHOD_DISPLAY_NAME,
    REFERENCE_TENSILE_METHOD_CODE,
    REFERENCE_TENSILE_METHOD_DISPLAY_NAME,
    REFERENCE_TENSILE_SCHEMA_VERSION,
    SpecimenContent,
    TestingConflict,
    TestMethodContent,
    TestRunContent,
)
from cmp.shared.application.revisions import (
    CreateRevisionedAggregate,
    ReviseAggregate,
    RevisionService,
    RevisionStore,
)
from cmp.shared.domain.revisions import RevisionRecord, TenantScope

SPECIMEN_AGGREGATE_TYPE = "testing.specimen"
TEST_METHOD_AGGREGATE_TYPE = "testing.test_method"
TEST_RUN_AGGREGATE_TYPE = "testing.test_run"
IMPORT_MAPPING_AGGREGATE_TYPE = "testing.import_mapping"
SPECIMEN_SCHEMA_ID = "urn:cmp:testing:reference-specimen:1.0.0"
TEST_METHOD_SCHEMA_ID = "urn:cmp:testing:reference-uniaxial-tensile-method:1.0.0"
TEST_RUN_SCHEMA_ID = "urn:cmp:testing:reference-uniaxial-tensile-run:1.0.0"
SHEAR_RELAXATION_METHOD_SCHEMA_ID = "urn:cmp:testing:reference-shear-relaxation-method:1.0.0"
SHEAR_RELAXATION_RUN_SCHEMA_ID = "urn:cmp:testing:reference-shear-relaxation-run:1.0.0"


@dataclass(frozen=True, slots=True)
class RevisionSnapshot[ContentT]:
    record: RevisionRecord
    content: ContentT


@dataclass(frozen=True, slots=True)
class SpecimenSnapshot:
    id: UUID
    material_state_id: UUID
    current: RevisionSnapshot[SpecimenContent]


@dataclass(frozen=True, slots=True)
class TestMethodSnapshot:
    id: UUID
    current: RevisionSnapshot[TestMethodContent]


@dataclass(frozen=True, slots=True)
class TestRunSnapshot:
    id: UUID
    specimen_id: UUID
    test_method_id: UUID
    current: RevisionSnapshot[TestRunContent]


@dataclass(frozen=True, slots=True)
class ImportDetectionReportSnapshot:
    id: UUID
    classification: DataClassification
    report: SyntheticCsvDetectionReport
    created_at: datetime
    created_by: UUID
    request_id: UUID
    trace_id: str


@dataclass(frozen=True, slots=True)
class ImportMappingSnapshot:
    id: UUID
    current: RevisionSnapshot[ReferenceImportMappingContent]


@dataclass(frozen=True, slots=True)
class ImportMappingRevisionSnapshot:
    mapping_id: UUID
    revision: RevisionSnapshot[ReferenceImportMappingContent]


@dataclass(frozen=True, slots=True)
class MaterialStateSource:
    classification: DataClassification
    content: SpecimenContent


@dataclass(frozen=True, slots=True)
class CreateSpecimen:
    material_state_id: UUID
    material_state_revision_id: UUID
    specimen_code: str
    orientation: str | None
    preparation_note: str | None
    change_reason: str


@dataclass(frozen=True, slots=True)
class CreateReferenceTensileMethod:
    classification: DataClassification
    change_reason: str


@dataclass(frozen=True, slots=True)
class CreateReferenceShearRelaxationMethod:
    classification: DataClassification
    change_reason: str


@dataclass(frozen=True, slots=True)
class CreateReferenceTensileRun:
    specimen_id: UUID
    specimen_revision_id: UUID
    test_method_id: UUID
    test_method_revision_id: UUID
    run_label: str
    performed_at: datetime
    test_temperature_k: float | None
    crosshead_speed_mm_per_min: float | None
    change_reason: str


@dataclass(frozen=True, slots=True)
class CreateReferenceShearRelaxationRun:
    specimen_id: UUID
    specimen_revision_id: UUID
    test_method_id: UUID
    test_method_revision_id: UUID
    run_label: str
    performed_at: datetime
    test_temperature_k: float | None
    change_reason: str


@dataclass(frozen=True, slots=True)
class DetectSyntheticCsvImport:
    raw_asset_id: UUID
    raw_artifact_id: UUID


@dataclass(frozen=True, slots=True)
class CreateReferenceImportMapping:
    detection_report_id: UUID
    mapping_label: str
    strain_column: str
    stress_column: str
    strain_unit: str
    stress_unit: str
    change_reason: str


@dataclass(frozen=True, slots=True)
class ReviseReferenceImportMapping:
    expected_current_revision_id: UUID
    detection_report_id: UUID
    strain_column: str
    stress_column: str
    strain_unit: str
    stress_unit: str
    change_reason: str


class TestingRepository(Protocol):
    def specimen_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[SpecimenContent]: ...

    def test_method_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[TestMethodContent]: ...

    def test_run_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[TestRunContent]: ...

    def import_mapping_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[ReferenceImportMappingContent]: ...

    def create_import_detection_report(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        report: ImportDetectionReportSnapshot,
    ) -> ImportDetectionReportSnapshot: ...

    def get_import_detection_report(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        detection_report_id: UUID,
    ) -> ImportDetectionReportSnapshot: ...

    def get_import_mapping(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        mapping_id: UUID,
    ) -> ImportMappingSnapshot: ...

    def get_import_mapping_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        mapping_id: UUID,
        mapping_revision_id: UUID,
    ) -> ImportMappingRevisionSnapshot: ...

    def get_test_run_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        test_run_id: UUID,
        test_run_revision_id: UUID,
    ) -> RevisionSnapshot[TestRunContent]: ...

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
    ) -> MaterialStateSource: ...

    def load_specimen_source(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        specimen_id: UUID,
        specimen_revision_id: UUID,
    ) -> tuple[DataClassification, SpecimenContent]: ...

    def load_test_method_source(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        test_method_id: UUID,
        test_method_revision_id: UUID,
    ) -> tuple[DataClassification, TestMethodContent]: ...

    def get_specimen(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        specimen_id: UUID,
    ) -> SpecimenSnapshot: ...

    def list_specimens_for_material_state(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_state_id: UUID,
    ) -> tuple[SpecimenSnapshot, ...]: ...

    def get_test_method(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        test_method_id: UUID,
    ) -> TestMethodSnapshot: ...

    def list_test_methods(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
    ) -> tuple[TestMethodSnapshot, ...]: ...

    def get_test_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        test_run_id: UUID,
    ) -> TestRunSnapshot: ...

    def list_test_runs_for_material_state(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_state_id: UUID,
    ) -> tuple[TestRunSnapshot, ...]: ...


def _require(
    context: SecurityContext,
    decision: AuthorizationDecision,
    permission: Permission,
) -> None:
    if (
        decision.permission is not permission
        or decision.principal_id != context.principal.id
        or decision.organization_id != context.organization_id
        or decision.project_id != context.project_id
        or decision.request_id != context.request_id
        or decision.trace_id != context.trace_id
    ):
        raise TestingConflict("authorization decision does not match testing request")


def _require_capability(
    context: SecurityContext,
    decision: AuthorizationDecision,
    permission: Permission,
) -> None:
    if (
        decision.principal_id != context.principal.id
        or decision.organization_id != context.organization_id
        or decision.project_id != context.project_id
        or decision.request_id != context.request_id
        or decision.trace_id != context.trace_id
        or permission.value not in decision.database_permissions
    ):
        raise TestingConflict("authorization decision lacks the required testing capability")


class TestingService:
    """Use T-06 revisions for the three explicit records required before CSV import."""

    def __init__(
        self,
        *,
        repository: TestingRepository,
        artifacts: ArtifactService | None = None,
        id_factory: Callable[[], UUID] = uuid4,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._artifacts = artifacts
        self._id_factory = id_factory
        self._clock = clock or (lambda: datetime.now(UTC))

    def _id(self) -> UUID:
        value = self._id_factory()
        if value.int == 0:
            raise RuntimeError("testing id_factory returned a zero UUID")
        return value

    def create_specimen(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CreateSpecimen,
    ) -> SpecimenSnapshot:
        _require(context, decision, Permission.TESTING_WRITE)
        source = self._repository.load_material_state_source(
            context=context,
            decision=decision,
            material_state_id=command.material_state_id,
            material_state_revision_id=command.material_state_revision_id,
            specimen_code=command.specimen_code,
            orientation=command.orientation,
            preparation_note=command.preparation_note,
        )
        specimen_id = self._id()
        scope = TenantScope(
            context.organization_id, context.project_id, source.classification.value
        )
        record = RevisionService(
            aggregate_type=SPECIMEN_AGGREGATE_TYPE,
            store=self._repository.specimen_store(context, decision),
        ).create(
            CreateRevisionedAggregate(
                aggregate_id=specimen_id,
                scope=scope,
                schema_id=SPECIMEN_SCHEMA_ID,
                schema_version=REFERENCE_TENSILE_SCHEMA_VERSION,
                content=source.content,
                created_by=context.principal.id,
                change_reason=command.change_reason,
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        return SpecimenSnapshot(
            specimen_id,
            source.content.material_state_id,
            RevisionSnapshot(record, source.content),
        )

    def create_reference_tensile_method(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CreateReferenceTensileMethod,
    ) -> TestMethodSnapshot:
        _require(context, decision, Permission.TESTING_WRITE)
        content = TestMethodContent(
            REFERENCE_TENSILE_METHOD_CODE,
            REFERENCE_TENSILE_METHOD_DISPLAY_NAME,
        )
        method_id = self._id()
        scope = TenantScope(
            context.organization_id, context.project_id, command.classification.value
        )
        record = RevisionService(
            aggregate_type=TEST_METHOD_AGGREGATE_TYPE,
            store=self._repository.test_method_store(context, decision),
        ).create(
            CreateRevisionedAggregate(
                aggregate_id=method_id,
                scope=scope,
                schema_id=TEST_METHOD_SCHEMA_ID,
                schema_version=REFERENCE_TENSILE_SCHEMA_VERSION,
                content=content,
                created_by=context.principal.id,
                change_reason=command.change_reason,
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        return TestMethodSnapshot(method_id, RevisionSnapshot(record, content))

    def create_reference_shear_relaxation_method(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CreateReferenceShearRelaxationMethod,
    ) -> TestMethodSnapshot:
        """Create the explicit reference method used by the viscoelastic data slice."""

        _require(context, decision, Permission.TESTING_WRITE)
        content = TestMethodContent(
            REFERENCE_SHEAR_RELAXATION_METHOD_CODE,
            REFERENCE_SHEAR_RELAXATION_METHOD_DISPLAY_NAME,
        )
        method_id = self._id()
        scope = TenantScope(
            context.organization_id, context.project_id, command.classification.value
        )
        record = RevisionService(
            aggregate_type=TEST_METHOD_AGGREGATE_TYPE,
            store=self._repository.test_method_store(context, decision),
        ).create(
            CreateRevisionedAggregate(
                aggregate_id=method_id,
                scope=scope,
                schema_id=SHEAR_RELAXATION_METHOD_SCHEMA_ID,
                schema_version=REFERENCE_TENSILE_SCHEMA_VERSION,
                content=content,
                created_by=context.principal.id,
                change_reason=command.change_reason,
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        return TestMethodSnapshot(method_id, RevisionSnapshot(record, content))

    def create_reference_tensile_run(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CreateReferenceTensileRun,
    ) -> TestRunSnapshot:
        _require(context, decision, Permission.TESTING_WRITE)
        specimen_classification, _specimen = self._repository.load_specimen_source(
            context=context,
            decision=decision,
            specimen_id=command.specimen_id,
            specimen_revision_id=command.specimen_revision_id,
        )
        method_classification, method = self._repository.load_test_method_source(
            context=context,
            decision=decision,
            test_method_id=command.test_method_id,
            test_method_revision_id=command.test_method_revision_id,
        )
        if specimen_classification is not method_classification:
            raise TestingConflict("Specimen and Test Method classifications must match")
        if method.method_code != REFERENCE_TENSILE_METHOD_CODE:
            raise TestingConflict("Test Run requires the reference tensile method")
        content = TestRunContent(
            specimen_id=command.specimen_id,
            specimen_revision_id=command.specimen_revision_id,
            test_method_id=command.test_method_id,
            test_method_revision_id=command.test_method_revision_id,
            run_label=command.run_label,
            performed_at=command.performed_at,
            test_temperature_k=command.test_temperature_k,
            crosshead_speed_mm_per_min=command.crosshead_speed_mm_per_min,
        )
        run_id = self._id()
        scope = TenantScope(
            context.organization_id, context.project_id, specimen_classification.value
        )
        record = RevisionService(
            aggregate_type=TEST_RUN_AGGREGATE_TYPE,
            store=self._repository.test_run_store(context, decision),
        ).create(
            CreateRevisionedAggregate(
                aggregate_id=run_id,
                scope=scope,
                schema_id=TEST_RUN_SCHEMA_ID,
                schema_version=REFERENCE_TENSILE_SCHEMA_VERSION,
                content=content,
                created_by=context.principal.id,
                change_reason=command.change_reason,
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        return TestRunSnapshot(
            run_id,
            content.specimen_id,
            content.test_method_id,
            RevisionSnapshot(record, content),
        )

    def create_reference_shear_relaxation_run(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CreateReferenceShearRelaxationRun,
    ) -> TestRunSnapshot:
        """Pin a shear-relaxation run to exact Specimen and Test Method revisions."""

        _require(context, decision, Permission.TESTING_WRITE)
        specimen_classification, _specimen = self._repository.load_specimen_source(
            context=context,
            decision=decision,
            specimen_id=command.specimen_id,
            specimen_revision_id=command.specimen_revision_id,
        )
        method_classification, method = self._repository.load_test_method_source(
            context=context,
            decision=decision,
            test_method_id=command.test_method_id,
            test_method_revision_id=command.test_method_revision_id,
        )
        if specimen_classification is not method_classification:
            raise TestingConflict("Specimen and Test Method classifications must match")
        if method.method_code != REFERENCE_SHEAR_RELAXATION_METHOD_CODE:
            raise TestingConflict("Test Run requires the reference shear-relaxation method")
        content = TestRunContent(
            specimen_id=command.specimen_id,
            specimen_revision_id=command.specimen_revision_id,
            test_method_id=command.test_method_id,
            test_method_revision_id=command.test_method_revision_id,
            run_label=command.run_label,
            performed_at=command.performed_at,
            test_temperature_k=command.test_temperature_k,
            crosshead_speed_mm_per_min=None,
        )
        run_id = self._id()
        scope = TenantScope(
            context.organization_id, context.project_id, specimen_classification.value
        )
        record = RevisionService(
            aggregate_type=TEST_RUN_AGGREGATE_TYPE,
            store=self._repository.test_run_store(context, decision),
        ).create(
            CreateRevisionedAggregate(
                aggregate_id=run_id,
                scope=scope,
                schema_id=SHEAR_RELAXATION_RUN_SCHEMA_ID,
                schema_version=REFERENCE_TENSILE_SCHEMA_VERSION,
                content=content,
                created_by=context.principal.id,
                change_reason=command.change_reason,
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        return TestRunSnapshot(
            run_id,
            content.specimen_id,
            content.test_method_id,
            RevisionSnapshot(record, content),
        )

    async def detect_synthetic_csv_import(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: DetectSyntheticCsvImport,
    ) -> ImportDetectionReportSnapshot:
        """Persist header evidence while deliberately requiring mapping input afterwards."""

        _require(context, decision, Permission.TESTING_WRITE)
        if self._artifacts is None:
            raise TestingConflict("immutable Artifact content is required for import detection")
        artifact_record, raw_bytes = await self._artifacts.read_verified_bytes(
            context,
            decision,
            command.raw_artifact_id,
            # Detection is header-only, but verified artifact reads deliberately use the same
            # bounded reference CSV envelope as the subsequent Dataset import.  A valid 16 MiB
            # source must not fail at the earlier detection step merely because it is larger than
            # one MiB.
            maximum_bytes=16 * 1024 * 1024,
        )
        artifact = artifact_record.artifact
        if (
            artifact_record.integrity_status is not IntegrityStatus.VERIFIED
            or artifact.artifact_kind is not ArtifactKind.RAW
            or artifact.source_raw_asset_id != command.raw_asset_id
            or artifact.media_type != "text/csv"
            or artifact.organization_id != context.organization_id
            or artifact.project_id != context.project_id
        ):
            raise TestingConflict(
                "synthetic import detection requires the named verified text/csv Raw Artifact"
            )
        report = detect_synthetic_csv_header(
            raw_bytes,
            raw_asset_id=command.raw_asset_id,
            raw_artifact_id=command.raw_artifact_id,
            raw_sha256=artifact.sha256,
        )
        snapshot = ImportDetectionReportSnapshot(
            id=self._id(),
            classification=artifact.classification,
            report=report,
            created_at=self._clock(),
            created_by=context.principal.id,
            request_id=context.request_id,
            trace_id=context.trace_id,
        )
        return self._repository.create_import_detection_report(
            context=context, decision=decision, report=snapshot
        )

    def _mapping_content(
        self,
        *,
        detection: ImportDetectionReportSnapshot,
        mapping_label: str,
        strain_column: str,
        stress_column: str,
        strain_unit: str,
        stress_unit: str,
    ) -> ReferenceImportMappingContent:
        report = detection.report
        if strain_column not in report.header_columns or stress_column not in report.header_columns:
            raise TestingConflict(
                "approved mapping columns must exist in the frozen Detection Report"
            )
        return ReferenceImportMappingContent(
            mapping_label=mapping_label,
            detection_report_id=detection.id,
            raw_asset_id=report.raw_asset_id,
            raw_artifact_id=report.raw_artifact_id,
            strain_column=strain_column,
            stress_column=stress_column,
            strain_unit=strain_unit,
            stress_unit=stress_unit,
        )

    def create_reference_import_mapping(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CreateReferenceImportMapping,
    ) -> ImportMappingSnapshot:
        _require(context, decision, Permission.TESTING_WRITE)
        detection = self._repository.get_import_detection_report(
            context=context,
            decision=decision,
            detection_report_id=command.detection_report_id,
        )
        content = self._mapping_content(
            detection=detection,
            mapping_label=command.mapping_label,
            strain_column=command.strain_column,
            stress_column=command.stress_column,
            strain_unit=command.strain_unit,
            stress_unit=command.stress_unit,
        )
        mapping_id = self._id()
        record = RevisionService(
            aggregate_type=IMPORT_MAPPING_AGGREGATE_TYPE,
            store=self._repository.import_mapping_store(context, decision),
        ).create(
            CreateRevisionedAggregate(
                aggregate_id=mapping_id,
                scope=TenantScope(
                    context.organization_id,
                    context.project_id,
                    detection.classification.value,
                ),
                schema_id=REFERENCE_IMPORT_MAPPING_SCHEMA_ID,
                schema_version=REFERENCE_IMPORT_MAPPING_SCHEMA_VERSION,
                content=content,
                created_by=context.principal.id,
                change_reason=command.change_reason,
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        return ImportMappingSnapshot(mapping_id, RevisionSnapshot(record, content))

    def get_import_detection_report(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        detection_report_id: UUID,
    ) -> ImportDetectionReportSnapshot:
        _require(context, decision, Permission.TESTING_READ)
        return self._repository.get_import_detection_report(
            context=context,
            decision=decision,
            detection_report_id=detection_report_id,
        )

    def revise_reference_import_mapping(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        mapping_id: UUID,
        command: ReviseReferenceImportMapping,
    ) -> ImportMappingSnapshot:
        _require(context, decision, Permission.TESTING_WRITE)
        existing = self._repository.get_import_mapping(
            context=context, decision=decision, mapping_id=mapping_id
        )
        detection = self._repository.get_import_detection_report(
            context=context,
            decision=decision,
            detection_report_id=command.detection_report_id,
        )
        content = self._mapping_content(
            detection=detection,
            mapping_label=existing.current.content.mapping_label,
            strain_column=command.strain_column,
            stress_column=command.stress_column,
            strain_unit=command.strain_unit,
            stress_unit=command.stress_unit,
        )
        if (
            content.raw_asset_id != existing.current.content.raw_asset_id
            or content.raw_artifact_id != existing.current.content.raw_artifact_id
            or content.importer_id != existing.current.content.importer_id
            or content.importer_version != existing.current.content.importer_version
        ):
            raise TestingConflict(
                "Import Mapping stable identity cannot move to another source Artifact or profile"
            )
        record = RevisionService(
            aggregate_type=IMPORT_MAPPING_AGGREGATE_TYPE,
            store=self._repository.import_mapping_store(context, decision),
        ).revise(
            ReviseAggregate(
                aggregate_id=mapping_id,
                scope=existing.current.record.scope,
                expected_current_revision_id=command.expected_current_revision_id,
                based_on_revision_id=command.expected_current_revision_id,
                schema_id=REFERENCE_IMPORT_MAPPING_SCHEMA_ID,
                schema_version=REFERENCE_IMPORT_MAPPING_SCHEMA_VERSION,
                content=content,
                created_by=context.principal.id,
                change_reason=command.change_reason,
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        return ImportMappingSnapshot(mapping_id, RevisionSnapshot(record, content))

    def get_import_mapping(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        mapping_id: UUID,
    ) -> ImportMappingSnapshot:
        _require(context, decision, Permission.TESTING_READ)
        return self._repository.get_import_mapping(
            context=context, decision=decision, mapping_id=mapping_id
        )

    def get_import_mapping_revision_for_processing(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        mapping_id: UUID,
        mapping_revision_id: UUID,
    ) -> ImportMappingRevisionSnapshot:
        _require_capability(context, decision, Permission.TESTING_READ)
        return self._repository.get_import_mapping_revision(
            context=context,
            decision=decision,
            mapping_id=mapping_id,
            mapping_revision_id=mapping_revision_id,
        )

    def get_test_run_revision_for_processing(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        test_run_id: UUID,
        test_run_revision_id: UUID,
    ) -> RevisionSnapshot[TestRunContent]:
        """Resolve the concrete Test Run input for an authorized Import Run."""

        _require_capability(context, decision, Permission.TESTING_READ)
        return self._repository.get_test_run_revision(
            context=context,
            decision=decision,
            test_run_id=test_run_id,
            test_run_revision_id=test_run_revision_id,
        )

    def get_specimen(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        specimen_id: UUID,
    ) -> SpecimenSnapshot:
        _require(context, decision, Permission.TESTING_READ)
        return self._repository.get_specimen(
            context=context, decision=decision, specimen_id=specimen_id
        )

    def list_specimens_for_material_state(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_state_id: UUID,
    ) -> tuple[SpecimenSnapshot, ...]:
        _require(context, decision, Permission.TESTING_READ)
        return self._repository.list_specimens_for_material_state(
            context=context, decision=decision, material_state_id=material_state_id
        )

    def get_test_method(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        test_method_id: UUID,
    ) -> TestMethodSnapshot:
        _require(context, decision, Permission.TESTING_READ)
        return self._repository.get_test_method(
            context=context, decision=decision, test_method_id=test_method_id
        )

    def list_test_methods(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
    ) -> tuple[TestMethodSnapshot, ...]:
        _require(context, decision, Permission.TESTING_READ)
        return self._repository.list_test_methods(context=context, decision=decision)

    def get_test_run(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        test_run_id: UUID,
    ) -> TestRunSnapshot:
        _require(context, decision, Permission.TESTING_READ)
        return self._repository.get_test_run(
            context=context, decision=decision, test_run_id=test_run_id
        )

    def list_test_runs_for_material_state(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_state_id: UUID,
    ) -> tuple[TestRunSnapshot, ...]:
        _require(context, decision, Permission.TESTING_READ)
        return self._repository.list_test_runs_for_material_state(
            context=context, decision=decision, material_state_id=material_state_id
        )

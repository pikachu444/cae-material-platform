from __future__ import annotations

import asyncio
import hashlib
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID, uuid4

from cmp.modules.artifacts.application.content import ArtifactService
from cmp.modules.artifacts.domain.content import (
    Artifact,
    ArtifactKind,
    ArtifactRecord,
    IntegrityStatus,
    content_object_key,
)
from cmp.modules.datasets.application.service import (
    DATASET_AGGREGATE_TYPE,
    DATASET_SELECTION_AGGREGATE_TYPE,
    DatasetRevisionSnapshot,
    DatasetSelectionRevisionSnapshot,
    DatasetService,
)
from cmp.modules.datasets.application.service import RevisionSnapshot as DatasetRevisionValue
from cmp.modules.datasets.domain.reference_tensile import (
    CurvePoint,
    DatasetContent,
    DatasetRepresentation,
    ReferenceTensileMapping,
    normalized_parquet_bytes,
)
from cmp.modules.datasets.domain.selection import ReferenceDatasetSelectionContent
from cmp.modules.identity_access.application.authorization import database_permissions_for
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
    Permission,
    Role,
)
from cmp.modules.identity_access.domain.security import (
    Principal,
    PrincipalType,
    SecurityContext,
)
from cmp.modules.modeling.application.service import (
    MATERIAL_MODEL_AGGREGATE_TYPE,
    MaterialModelService,
)
from cmp.modules.modeling.application.service import (
    RevisionSnapshot as ModelRevisionValue,
)
from cmp.modules.modeling.domain.reference_linear_elasticity import (
    ReferenceCalibrationEvidence,
    ReferenceLinearElasticContent,
)
from cmp.modules.validation.application.service import (
    VALIDATION_TEMPLATE_AGGREGATE_TYPE,
    EvaluateReferenceValidationRun,
    NumericalHealthReport,
    ReferenceValidationResult,
    ReferenceValidationService,
    RevisionSnapshot,
    ValidationRepository,
    ValidationResponseExtraction,
    ValidationRun,
    ValidationRunDetail,
    ValidationRunResultManifest,
)
from cmp.modules.validation.domain.reference_result_interpretation import (
    ValidationVerdict,
)
from cmp.modules.validation.domain.reference_virtual_specimen import (
    REFERENCE_NATIVE_RESULT_SCHEMA_ID,
    ReferenceVirtualSpecimenTemplateContent,
    SolverTerminationStatus,
    ValidationArtifactReference,
    ValidationExecutionMode,
    ValidationRunResultManifestContent,
    ValidationRunStatus,
    reference_mock_native_result_bytes,
)
from cmp.shared.domain.revisions import RevisionRecord, TenantScope

NOW = datetime(2026, 7, 22, 9, 0, tzinfo=UTC)
ORG = UUID("28000000-0000-4000-8000-000000000101")
PROJECT = UUID("28000000-0000-4000-8000-000000000102")
ACTOR = UUID("28000000-0000-4000-8000-000000000103")
RUN = UUID("28000000-0000-4000-8000-000000000104")
TEMPLATE = UUID("28000000-0000-4000-8000-000000000105")
TEMPLATE_REVISION = UUID("28000000-0000-4000-8000-000000000106")
PLAN = UUID("28000000-0000-4000-8000-000000000107")
PLAN_REVISION = UUID("28000000-0000-4000-8000-000000000108")
MODEL = UUID("28000000-0000-4000-8000-000000000109")
MODEL_REVISION = UUID("28000000-0000-4000-8000-00000000010a")
STATE = UUID("28000000-0000-4000-8000-00000000010b")
MATERIAL = UUID("28000000-0000-4000-8000-00000000010c")
DATASET = UUID("28000000-0000-4000-8000-00000000010d")
DATASET_REVISION = UUID("28000000-0000-4000-8000-00000000010e")
SELECTION = UUID("28000000-0000-4000-8000-00000000010f")
SELECTION_REVISION = UUID("28000000-0000-4000-8000-000000000110")
DECK = UUID("28000000-0000-4000-8000-000000000111")
STDOUT = UUID("28000000-0000-4000-8000-000000000112")
STDERR = UUID("28000000-0000-4000-8000-000000000113")
NATIVE = UUID("28000000-0000-4000-8000-000000000114")
MANIFEST = UUID("28000000-0000-4000-8000-000000000115")
MANIFEST_ARTIFACT = UUID("28000000-0000-4000-8000-000000000116")
OBSERVED_ARTIFACT = UUID("28000000-0000-4000-8000-000000000117")
EXTRACTION = UUID("28000000-0000-4000-8000-000000000118")
HEALTH = UUID("28000000-0000-4000-8000-000000000119")
RESULT = UUID("28000000-0000-4000-8000-00000000011a")
TRACE = "00-00000000000000000000000000000280-0000000000000280-01"
POINTS = (
    CurvePoint(0.0, 0.0),
    CurvePoint(0.01, 2_100_000_000.0),
    CurvePoint(0.02, 4_200_000_000.0),
)


def _context() -> SecurityContext:
    return SecurityContext(
        principal=Principal(ACTOR, PrincipalType.USER, "CAE analyst", True),
        organization_id=ORG,
        project_id=PROJECT,
        issuer="https://test-idp.invalid",
        subject=str(ACTOR),
        token_id=str(uuid4()),
        groups=(),
        scopes=("openid",),
        request_id=uuid4(),
        trace_id=TRACE,
        authenticated_at=NOW,
    )


CONTEXT = _context()
EXECUTE = AuthorizationDecision(
    principal_id=ACTOR,
    organization_id=ORG,
    project_id=PROJECT,
    permission=Permission.VALIDATION_EXECUTE,
    roles=(Role.CAE_ANALYST,),
    database_permissions=database_permissions_for(Permission.VALIDATION_EXECUTE),
    max_classification=DataClassification.INTERNAL,
    allow_export_controlled=False,
    request_id=CONTEXT.request_id,
    trace_id=TRACE,
    decided_at=NOW,
)
READ = AuthorizationDecision(
    principal_id=ACTOR,
    organization_id=ORG,
    project_id=PROJECT,
    permission=Permission.VALIDATION_READ,
    roles=(Role.CAE_ANALYST,),
    database_permissions=database_permissions_for(Permission.VALIDATION_READ),
    max_classification=DataClassification.INTERNAL,
    allow_export_controlled=False,
    request_id=CONTEXT.request_id,
    trace_id=TRACE,
    decided_at=NOW,
)


def _record(revision_id: UUID, aggregate_id: UUID, aggregate_type: str) -> RevisionRecord:
    return RevisionRecord(
        revision_id=revision_id,
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        scope=TenantScope(ORG, PROJECT, DataClassification.INTERNAL.value),
        revision_no=1,
        based_on_revision_id=None,
        schema_id="urn:cmp:test:validation:1.0.0",
        schema_version="1.0.0",
        content_hash="a" * 64,
        created_at=NOW,
        created_by=ACTOR,
        change_reason="reference validation result service test",
        request_id=CONTEXT.request_id,
        trace_id=TRACE,
    )


def _artifact(
    artifact_id: UUID,
    payload: bytes,
    *,
    role: str,
    schema_ref: str,
) -> ArtifactRecord:
    digest = hashlib.sha256(payload).hexdigest()
    return ArtifactRecord(
        artifact=Artifact(
            id=artifact_id,
            organization_id=ORG,
            project_id=PROJECT,
            classification=DataClassification.INTERNAL,
            artifact_kind=ArtifactKind.DERIVED,
            artifact_role=role,
            schema_ref=schema_ref,
            media_type="application/json",
            size_bytes=len(payload),
            sha256=digest,
            storage_key=content_object_key(ORG, PROJECT, DataClassification.INTERNAL, digest),
            encryption_profile="test",
            source_raw_asset_id=None,
            source_pending_id=uuid4(),
            created_at=NOW,
            created_by=ACTOR,
        ),
        integrity_status=IntegrityStatus.VERIFIED,
        last_checked_at=NOW,
        last_observation_id=uuid4(),
    )


def _reference(record: ArtifactRecord) -> ValidationArtifactReference:
    return ValidationArtifactReference(record.artifact.id, record.artifact.sha256)


def _template() -> ReferenceVirtualSpecimenTemplateContent:
    return ReferenceVirtualSpecimenTemplateContent(
        template_label="Reference virtual specimen",
        gauge_length_m=0.05,
        cross_section_area_m2=1.0e-5,
        axial_element_count=10,
        axial_displacement_end_m=0.001,
        output_sample_count=3,
    )


class _Datasets:
    def __init__(self) -> None:
        payload = normalized_parquet_bytes(POINTS)
        artifact = _artifact(
            OBSERVED_ARTIFACT,
            payload,
            role="dataset.normalized_curve",
            schema_ref="urn:cmp:datasets:reference-tensile-normalized-parquet:1.0.0",
        )
        content = DatasetContent(
            test_run_id=uuid4(),
            test_run_revision_id=uuid4(),
            raw_asset_id=uuid4(),
            raw_artifact_id=uuid4(),
            data_artifact_id=artifact.artifact.id,
            data_sha256=artifact.artifact.sha256,
            representation=DatasetRepresentation.NORMALIZED,
            source_dataset_revision_id=uuid4(),
            point_count=len(POINTS),
            mapping=ReferenceTensileMapping("strain", "stress", "1", "Pa"),
        )
        self.artifact = artifact
        self.dataset = DatasetRevisionSnapshot(
            DATASET,
            DatasetRevisionValue(
                _record(DATASET_REVISION, DATASET, DATASET_AGGREGATE_TYPE), content
            ),
        )
        selection = ReferenceDatasetSelectionContent(
            selection_label="Validation experiment",
            dataset_id=DATASET,
            dataset_revision_id=DATASET_REVISION,
        )
        self.selection = DatasetSelectionRevisionSnapshot(
            SELECTION,
            selection.selection_label,
            DatasetRevisionValue(
                _record(SELECTION_REVISION, SELECTION, DATASET_SELECTION_AGGREGATE_TYPE),
                selection,
            ),
        )

    def get_reference_dataset_selection_revision_for_validation(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        selection_id: UUID,
        selection_revision_id: UUID,
    ) -> DatasetSelectionRevisionSnapshot:
        assert context is CONTEXT and decision is EXECUTE
        assert (selection_id, selection_revision_id) == (SELECTION, SELECTION_REVISION)
        return self.selection

    def get_dataset_revision_for_validation(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        dataset_revision_id: UUID,
    ) -> DatasetRevisionSnapshot:
        assert context is CONTEXT and decision is EXECUTE
        assert dataset_revision_id == DATASET_REVISION
        return self.dataset


class _Models:
    def __init__(self, *, overlap: bool) -> None:
        evidence = (
            ReferenceCalibrationEvidence(
                calibration_selection_id=SELECTION,
                calibration_selection_revision_id=SELECTION_REVISION,
                calibration_run_id=uuid4(),
                calibration_candidate_id=uuid4(),
                calibration_candidate_sha256="b" * 64,
                diagnostics_artifact_id=uuid4(),
                diagnostics_sha256="c" * 64,
            )
            if overlap
            else None
        )
        self.revision = ModelRevisionValue(
            _record(MODEL_REVISION, MODEL, MATERIAL_MODEL_AGGREGATE_TYPE),
            ReferenceLinearElasticContent(
                material_id=MATERIAL,
                material_revision_id=uuid4(),
                material_state_id=STATE,
                material_state_revision_id=uuid4(),
                property_set_id=uuid4(),
                property_set_revision_id=uuid4(),
                density_kg_per_m3=7850.0,
                youngs_modulus_pa=210_000_000_000.0,
                poisson_ratio=0.3,
                calibration_evidence=evidence,
            ),
        )

    def get_material_model_revision_for_validation(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_model_id: UUID,
        material_model_revision_id: UUID,
    ) -> ModelRevisionValue[ReferenceLinearElasticContent]:
        assert context is CONTEXT and decision is EXECUTE
        assert (material_model_id, material_model_revision_id) == (MODEL, MODEL_REVISION)
        return self.revision


class _Artifacts:
    def __init__(self, datasets: _Datasets, *, abnormal: bool) -> None:
        template = _template()
        native_bytes = reference_mock_native_result_bytes(
            template=template,
            youngs_modulus_pa=210_000_000_000.0,
        )
        self.native = _artifact(
            NATIVE,
            native_bytes,
            role="validation.native_solver_result",
            schema_ref=REFERENCE_NATIVE_RESULT_SCHEMA_ID,
        )
        self.observed = datasets.artifact
        self.records: dict[UUID, tuple[ArtifactRecord, bytes]] = {
            self.observed.artifact.id: (self.observed, normalized_parquet_bytes(POINTS)),
        }
        if not abnormal:
            self.records[self.native.artifact.id] = (self.native, native_bytes)
        self.created: list[ArtifactRecord] = []

    async def read_verified_bytes(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        artifact_id: UUID,
        *,
        maximum_bytes: int,
    ) -> tuple[ArtifactRecord, bytes]:
        assert context is CONTEXT
        assert decision in {EXECUTE, READ}
        record, value = self.records[artifact_id]
        assert len(value) <= maximum_bytes
        return record, value

    async def finalize_derived_bytes(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        *,
        classification: DataClassification,
        artifact_role: str,
        schema_ref: str,
        media_type: str,
        value: bytes,
        idempotency_key: str,
    ) -> ArtifactRecord:
        assert context is CONTEXT and decision is EXECUTE
        assert classification is DataClassification.INTERNAL
        assert media_type == "application/json"
        record = _artifact(uuid4(), value, role=artifact_role, schema_ref=schema_ref)
        self.records[record.artifact.id] = (record, value)
        self.created.append(record)
        return record


class _Repository:
    def __init__(self, artifacts: _Artifacts, *, abnormal: bool) -> None:
        self.template = RevisionSnapshot(
            _record(TEMPLATE_REVISION, TEMPLATE, VALIDATION_TEMPLATE_AGGREGATE_TYPE), _template()
        )
        native = None if abnormal else _reference(artifacts.native)
        termination = (
            SolverTerminationStatus.ABNORMAL if abnormal else SolverTerminationStatus.NORMAL
        )
        content = ValidationRunResultManifestContent(
            validation_run_id=RUN,
            execution_mode=ValidationExecutionMode.REFERENCE_INLINE_MOCK,
            solver_termination=termination,
            external_job_reference=None,
            deck=ValidationArtifactReference(DECK, "d" * 64),
            stdout=ValidationArtifactReference(STDOUT, "e" * 64),
            stderr=ValidationArtifactReference(STDERR, "f" * 64),
            native_result=native,
            native_result_state="not_available" if abnormal else "available",
        )
        self.manifest = ValidationRunResultManifest(
            id=MANIFEST,
            content=content,
            manifest_artifact=ValidationArtifactReference(MANIFEST_ARTIFACT, "a" * 64),
            manifest_sha256="a" * 64,
            created_at=NOW,
            created_by=ACTOR,
        )
        self.run = ValidationRun(
            id=RUN,
            classification=DataClassification.INTERNAL,
            plan_id=PLAN,
            plan_revision_id=PLAN_REVISION,
            template_id=TEMPLATE,
            template_revision_id=TEMPLATE_REVISION,
            material_model_id=MODEL,
            material_model_revision_id=MODEL_REVISION,
            solver_card_id=uuid4(),
            solver_card_revision_id=uuid4(),
            experimental_selection_id=SELECTION,
            experimental_selection_revision_id=SELECTION_REVISION,
            execution_mode=ValidationExecutionMode.REFERENCE_INLINE_MOCK,
            runner_id="cmp.reference.inline-mock-runner",
            runner_version="1.0.0",
            runner_digest="b" * 64,
            status=ValidationRunStatus.FAILED if abnormal else ValidationRunStatus.SUCCEEDED,
            deck=content.deck,
            external_job_reference=None,
            failure_code="solver_failed" if abnormal else None,
            submitted_at=NOW,
            started_at=NOW,
            ended_at=NOW,
            created_by=ACTOR,
            request_id=CONTEXT.request_id,
            trace_id=TRACE,
            change_reason="Collect reference validation evidence",
        )
        self.result: ReferenceValidationResult | None = None

    def get_run_detail(
        self, *, context: SecurityContext, decision: AuthorizationDecision, run_id: UUID
    ) -> ValidationRunDetail:
        assert context is CONTEXT and decision is EXECUTE and run_id == RUN
        return ValidationRunDetail(self.run, self.manifest, self.result)

    def get_template_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        template_id: UUID,
        template_revision_id: UUID,
    ) -> RevisionSnapshot[ReferenceVirtualSpecimenTemplateContent]:
        assert context is CONTEXT and decision is EXECUTE
        assert (template_id, template_revision_id) == (TEMPLATE, TEMPLATE_REVISION)
        return self.template

    def record_result_evaluation(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
        response_extraction: ValidationResponseExtraction,
        numerical_health_report: NumericalHealthReport,
        validation_result: ReferenceValidationResult,
        change_reason: str,
    ) -> ValidationRunDetail:
        assert context is CONTEXT and decision is EXECUTE and run_id == RUN
        assert change_reason
        self.result = validation_result
        return ValidationRunDetail(self.run, self.manifest, validation_result)

    def get_validation_result(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        validation_result_id: UUID,
    ) -> ReferenceValidationResult:
        assert context is CONTEXT and decision is READ and self.result is not None
        assert validation_result_id == self.result.id
        return self.result


def _service(*, abnormal: bool = False, overlap: bool = False) -> ReferenceValidationService:
    datasets = _Datasets()
    artifacts = _Artifacts(datasets, abnormal=abnormal)
    repository = _Repository(artifacts, abnormal=abnormal)
    ids = iter((EXTRACTION, HEALTH, RESULT))
    return ReferenceValidationService(
        repository=cast(ValidationRepository, repository),
        datasets=cast(DatasetService, datasets),
        material_models=cast(MaterialModelService, _Models(overlap=overlap)),
        solver_cards=cast(Any, object()),
        artifacts=cast(ArtifactService, artifacts),
        id_factory=lambda: next(ids),
        clock=lambda: NOW,
    )


def test_reference_result_service_extracts_compares_and_previews_real_artifacts() -> None:
    service = _service()

    detail = asyncio.run(
        service.evaluate_reference_run(
            CONTEXT,
            EXECUTE,
            RUN,
            EvaluateReferenceValidationRun("Extract and compare terminal reference response"),
        )
    )

    assert detail.validation_result is not None
    assert detail.validation_result.content.verdict is ValidationVerdict.PASSED
    assert (
        detail.validation_result.numerical_health_report.content.assessment.status.value
        == "healthy"
    )
    preview = asyncio.run(
        service.preview_validation_result_curve(
            CONTEXT,
            READ,
            detail.validation_result.id,
        )
    )
    assert preview.response_point_count == 3
    assert preview.comparison_point_count == 3
    assert preview.comparison_points[1].residual_engineering_stress_pa == 0.0


def test_reference_result_service_records_abnormal_run_as_not_evaluated() -> None:
    detail = asyncio.run(
        _service(abnormal=True).evaluate_reference_run(
            CONTEXT,
            EXECUTE,
            RUN,
            EvaluateReferenceValidationRun("Record abnormal terminal solver state"),
        )
    )

    assert detail.validation_result is not None
    assert detail.validation_result.content.verdict is ValidationVerdict.NOT_EVALUATED
    assert detail.validation_result.content.reason_code == "solver_termination_abnormal"


def test_reference_result_service_blocks_fit_holdout_overlap_from_a_verdict() -> None:
    detail = asyncio.run(
        _service(overlap=True).evaluate_reference_run(
            CONTEXT,
            EXECUTE,
            RUN,
            EvaluateReferenceValidationRun("Reject fitted input as independent holdout evidence"),
        )
    )

    assert detail.validation_result is not None
    assert detail.validation_result.content.verdict is ValidationVerdict.NOT_EVALUATED
    assert detail.validation_result.content.reason_code == "fit_holdout_overlap"

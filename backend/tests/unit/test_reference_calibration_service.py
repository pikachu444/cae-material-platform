from __future__ import annotations

import asyncio
import hashlib
from dataclasses import replace
from datetime import UTC, datetime
from typing import cast
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
    CalibrationDatasetSource,
    DatasetRevisionSnapshot,
    DatasetSelectionRevisionSnapshot,
    DatasetService,
)
from cmp.modules.datasets.application.service import (
    RevisionSnapshot as DatasetRevisionSnapshotValue,
)
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
from cmp.modules.modeling.application.calibration import (
    CALIBRATION_PLAN_AGGREGATE_TYPE,
    CalibrationAttempt,
    CalibrationAttemptStatus,
    CalibrationCandidate,
    CalibrationRepository,
    CalibrationRun,
    CalibrationRunStatus,
    ExecuteReferenceLinearElasticCalibration,
    ReferenceCalibrationService,
)
from cmp.modules.modeling.application.service import (
    MATERIAL_MODEL_AGGREGATE_TYPE,
    MaterialModelService,
    RevisionSnapshot,
)
from cmp.modules.modeling.domain.reference_linear_elastic_calibration import (
    ReferenceLinearElasticCalibrationPlanContent,
)
from cmp.modules.modeling.domain.reference_linear_elasticity import ReferenceLinearElasticContent
from cmp.shared.domain.revisions import RevisionRecord, TenantScope

NOW = datetime(2026, 7, 19, 12, 0, tzinfo=UTC)
ORG = UUID("fa000000-0000-4000-8000-000000000001")
PROJECT = UUID("fa000000-0000-4000-8000-000000000002")
ACTOR = UUID("fa000000-0000-4000-8000-000000000003")
STATE = UUID("fa000000-0000-4000-8000-000000000004")
MATERIAL = UUID("fa000000-0000-4000-8000-000000000005")
MATERIAL_REVISION = UUID("fa000000-0000-4000-8000-000000000006")
STATE_REVISION = UUID("fa000000-0000-4000-8000-000000000007")
PROPERTY_SET = UUID("fa000000-0000-4000-8000-000000000008")
PROPERTY_SET_REVISION = UUID("fa000000-0000-4000-8000-000000000009")
MODEL = UUID("fa000000-0000-4000-8000-00000000000a")
MODEL_REVISION = UUID("fa000000-0000-4000-8000-00000000000b")
DATASET = UUID("fa000000-0000-4000-8000-00000000000c")
DATASET_REVISION = UUID("fa000000-0000-4000-8000-00000000000d")
SELECTION = UUID("fa000000-0000-4000-8000-00000000000e")
SELECTION_REVISION = UUID("fa000000-0000-4000-8000-00000000000f")
PLAN = UUID("fa000000-0000-4000-8000-000000000010")
PLAN_REVISION = UUID("fa000000-0000-4000-8000-000000000011")
INPUT_ARTIFACT = UUID("fa000000-0000-4000-8000-000000000012")
RUN = UUID("fa000000-0000-4000-8000-000000000013")
ATTEMPT_ONE = UUID("fa000000-0000-4000-8000-000000000014")
CANDIDATE_ONE = UUID("fa000000-0000-4000-8000-000000000015")
ATTEMPT_TWO = UUID("fa000000-0000-4000-8000-000000000016")
CANDIDATE_TWO = UUID("fa000000-0000-4000-8000-000000000017")
DIAGNOSTIC_ONE = UUID("fa000000-0000-4000-8000-000000000018")
DIAGNOSTIC_TWO = UUID("fa000000-0000-4000-8000-000000000019")
TRACE = "00-000000000000000000000000000000fa-00000000000000fa-01"
MAPPING = ReferenceTensileMapping("strain", "stress", "1", "Pa")


def _context() -> SecurityContext:
    return SecurityContext(
        principal=Principal(ACTOR, PrincipalType.USER, "Material Modeler", True),
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
    permission=Permission.CALIBRATION_EXECUTE,
    roles=(Role.MATERIAL_MODELER,),
    database_permissions=database_permissions_for(Permission.CALIBRATION_EXECUTE),
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
        schema_id=f"urn:cmp:test:{aggregate_type}:1.0.0",
        schema_version="1.0.0",
        content_hash="a" * 64,
        created_at=NOW,
        created_by=ACTOR,
        change_reason="reference calibration service test",
        request_id=CONTEXT.request_id,
        trace_id=TRACE,
    )


POINTS = (
    CurvePoint(0.0, 0.0),
    CurvePoint(0.01, 2_000_000_000.0),
    CurvePoint(0.02, 4_000_000_000.0),
)


def _artifact(artifact_id: UUID, payload: bytes, role: str, schema_ref: str) -> ArtifactRecord:
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
            media_type="application/vnd.apache.parquet",
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


def _plan() -> RevisionSnapshot[ReferenceLinearElasticCalibrationPlanContent]:
    return RevisionSnapshot(
        _record(PLAN_REVISION, PLAN, CALIBRATION_PLAN_AGGREGATE_TYPE),
        ReferenceLinearElasticCalibrationPlanContent(
            plan_label="Reference elastic calibration",
            selection_id=SELECTION,
            selection_revision_id=SELECTION_REVISION,
            material_model_id=MODEL,
            material_model_revision_id=MODEL_REVISION,
            youngs_modulus_lower_bound_pa=100_000_000_000.0,
            youngs_modulus_initial_value_pa=190_000_000_000.0,
            youngs_modulus_upper_bound_pa=300_000_000_000.0,
            normalization_stress_scale_pa=1_000_000.0,
            multistart_count=2,
            random_seed=42,
        ),
    )


class _Datasets:
    def __init__(self) -> None:
        payload = normalized_parquet_bytes(POINTS)
        content = DatasetContent(
            test_run_id=uuid4(),
            test_run_revision_id=uuid4(),
            raw_asset_id=uuid4(),
            raw_artifact_id=uuid4(),
            data_artifact_id=INPUT_ARTIFACT,
            data_sha256=hashlib.sha256(payload).hexdigest(),
            representation=DatasetRepresentation.NORMALIZED,
            source_dataset_revision_id=uuid4(),
            point_count=len(POINTS),
            mapping=MAPPING,
        )
        dataset = DatasetRevisionSnapshot(
            DATASET,
            DatasetRevisionSnapshotValue(
                _record(DATASET_REVISION, DATASET, DATASET_AGGREGATE_TYPE), content
            ),
        )
        selection_content = ReferenceDatasetSelectionContent(
            selection_label="Calibration input",
            dataset_id=DATASET,
            dataset_revision_id=DATASET_REVISION,
        )
        self.selection = DatasetSelectionRevisionSnapshot(
            SELECTION,
            selection_content.selection_label,
            DatasetRevisionSnapshotValue(
                _record(SELECTION_REVISION, SELECTION, DATASET_SELECTION_AGGREGATE_TYPE),
                selection_content,
            ),
        )
        self.source = CalibrationDatasetSource(dataset=dataset, material_state_id=STATE)

    def get_reference_dataset_selection_revision_for_calibration(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        selection_id: UUID,
        selection_revision_id: UUID,
    ) -> DatasetSelectionRevisionSnapshot:
        assert context is CONTEXT
        assert decision is EXECUTE
        assert (selection_id, selection_revision_id) == (SELECTION, SELECTION_REVISION)
        return self.selection

    def get_calibration_dataset_source(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        dataset_revision_id: UUID,
    ) -> CalibrationDatasetSource:
        assert context is CONTEXT
        assert decision is EXECUTE
        assert dataset_revision_id == DATASET_REVISION
        return self.source


class _Models:
    def __init__(self) -> None:
        self.revision = RevisionSnapshot(
            _record(MODEL_REVISION, MODEL, MATERIAL_MODEL_AGGREGATE_TYPE),
            ReferenceLinearElasticContent(
                material_id=MATERIAL,
                material_revision_id=MATERIAL_REVISION,
                material_state_id=STATE,
                material_state_revision_id=STATE_REVISION,
                property_set_id=PROPERTY_SET,
                property_set_revision_id=PROPERTY_SET_REVISION,
                density_kg_per_m3=7850.0,
                youngs_modulus_pa=210_000_000_000.0,
                poisson_ratio=0.3,
            ),
        )

    def get_material_model_revision_for_calibration(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_model_id: UUID,
        material_model_revision_id: UUID,
    ) -> RevisionSnapshot[ReferenceLinearElasticContent]:
        assert context is CONTEXT
        assert decision is EXECUTE
        assert (material_model_id, material_model_revision_id) == (MODEL, MODEL_REVISION)
        return self.revision


class _Artifacts:
    def __init__(self, *, fail_input: bool = False) -> None:
        self.input_bytes = normalized_parquet_bytes(POINTS)
        self.input = _artifact(
            INPUT_ARTIFACT,
            self.input_bytes,
            "dataset.normalized_curve",
            "urn:cmp:datasets:reference-tensile-normalized-parquet:1.0.0",
        )
        self.fail_input = fail_input
        self.diagnostics: list[bytes] = []

    async def read_verified_bytes(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        artifact_id: UUID,
        *,
        maximum_bytes: int,
    ) -> tuple[ArtifactRecord, bytes]:
        assert context is CONTEXT
        assert decision is EXECUTE
        assert artifact_id == INPUT_ARTIFACT
        assert maximum_bytes >= len(self.input_bytes)
        if self.fail_input:
            raise RuntimeError("object storage unavailable")
        return self.input, self.input_bytes

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
        assert context is CONTEXT
        assert decision is EXECUTE
        assert classification is DataClassification.INTERNAL
        assert artifact_role == "modeling.reference_linear_elastic_calibration_diagnostics"
        assert media_type == "application/vnd.apache.parquet"
        assert idempotency_key.endswith(":1") or idempotency_key.endswith(":2")
        self.diagnostics.append(value)
        artifact_id = DIAGNOSTIC_ONE if len(self.diagnostics) == 1 else DIAGNOSTIC_TWO
        return _artifact(artifact_id, value, artifact_role, schema_ref)


class _Repository:
    def __init__(self) -> None:
        self.plan = _plan()
        self.run: CalibrationRun | None = None
        self.attempts: list[CalibrationAttempt] = []
        self.candidates: list[CalibrationCandidate] = []

    def get_plan_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        plan_id: UUID,
        plan_revision_id: UUID,
    ) -> RevisionSnapshot[ReferenceLinearElasticCalibrationPlanContent]:
        assert context is CONTEXT
        assert decision is EXECUTE
        assert (plan_id, plan_revision_id) == (PLAN, PLAN_REVISION)
        return self.plan

    def create_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run: CalibrationRun,
    ) -> CalibrationRun:
        assert context is CONTEXT
        assert decision is EXECUTE
        self.run = run
        return run

    def create_attempt(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        attempt: CalibrationAttempt,
    ) -> CalibrationAttempt:
        assert context is CONTEXT
        assert decision is EXECUTE
        self.attempts.append(attempt)
        return attempt

    def succeed_attempt(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        attempt_id: UUID,
        candidate_id: UUID,
    ) -> CalibrationAttempt:
        assert context is CONTEXT
        assert decision is EXECUTE
        index = next(index for index, item in enumerate(self.attempts) if item.id == attempt_id)
        value = replace(
            self.attempts[index],
            status=CalibrationAttemptStatus.SUCCEEDED,
            candidate_id=candidate_id,
            ended_at=NOW,
        )
        self.attempts[index] = value
        return value

    def fail_attempt(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        attempt_id: UUID,
        failure_code: str,
    ) -> CalibrationAttempt:
        index = next(index for index, item in enumerate(self.attempts) if item.id == attempt_id)
        value = replace(
            self.attempts[index],
            status=CalibrationAttemptStatus.FAILED,
            failure_code=failure_code,
            ended_at=NOW,
        )
        self.attempts[index] = value
        return value

    def create_candidate(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        candidate: CalibrationCandidate,
    ) -> CalibrationCandidate:
        assert context is CONTEXT
        assert decision is EXECUTE
        self.candidates.append(candidate)
        return candidate

    def succeed_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
        candidate_count: int,
    ) -> CalibrationRun:
        assert self.run is not None and run_id == self.run.id
        self.run = replace(
            self.run,
            status=CalibrationRunStatus.SUCCEEDED,
            candidate_count=candidate_count,
            ended_at=NOW,
        )
        return self.run

    def fail_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
        failure_code: str,
    ) -> CalibrationRun:
        assert self.run is not None and run_id == self.run.id
        self.run = replace(
            self.run,
            status=CalibrationRunStatus.FAILED,
            candidate_count=len(self.candidates),
            failure_code=failure_code,
            ended_at=NOW,
        )
        return self.run

    def list_attempts(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
    ) -> tuple[CalibrationAttempt, ...]:
        assert self.run is not None and run_id == self.run.id
        return tuple(self.attempts)

    def list_candidates(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
    ) -> tuple[CalibrationCandidate, ...]:
        assert self.run is not None and run_id == self.run.id
        return tuple(self.candidates)


def _service(repository: _Repository, artifacts: _Artifacts) -> ReferenceCalibrationService:
    ids = iter((RUN, ATTEMPT_ONE, CANDIDATE_ONE, ATTEMPT_TWO, CANDIDATE_TWO))
    return ReferenceCalibrationService(
        repository=cast(CalibrationRepository, repository),
        datasets=cast(DatasetService, _Datasets()),
        material_models=cast(MaterialModelService, _Models()),
        artifacts=cast(ArtifactService, artifacts),
        id_factory=lambda: next(ids),
    )


def test_reference_calibration_run_pins_inputs_and_retains_every_multistart_candidate() -> None:
    repository = _Repository()
    artifacts = _Artifacts()

    result = asyncio.run(
        _service(repository, artifacts).execute(
            CONTEXT,
            EXECUTE,
            ExecuteReferenceLinearElasticCalibration(
                plan_id=PLAN,
                plan_revision_id=PLAN_REVISION,
                change_reason="Fit reference elastic slope against pinned normalized Dataset",
            ),
        )
    )

    assert result.run.status is CalibrationRunStatus.SUCCEEDED
    assert result.run.candidate_count == 2
    assert result.run.dataset_revision_id == DATASET_REVISION
    assert result.run.material_model_revision_id == MODEL_REVISION
    assert len(result.attempts) == 2
    assert all(item.status is CalibrationAttemptStatus.SUCCEEDED for item in result.attempts)
    assert len(result.candidates) == 2
    assert {item.youngs_modulus_pa for item in result.candidates} == {200_000_000_000.0}
    assert all(item.objective_total == 0.0 for item in result.candidates)
    assert len(artifacts.diagnostics) == 2


def test_reference_calibration_preserves_failed_run_for_unreadable_pinned_input_artifact() -> None:
    repository = _Repository()
    artifacts = _Artifacts(fail_input=True)

    result = asyncio.run(
        _service(repository, artifacts).execute(
            CONTEXT,
            EXECUTE,
            ExecuteReferenceLinearElasticCalibration(
                plan_id=PLAN,
                plan_revision_id=PLAN_REVISION,
                change_reason="Record failed reference calibration input read",
            ),
        )
    )

    assert result.run.status is CalibrationRunStatus.FAILED
    assert result.run.failure_code == "input_artifact_unreadable"
    assert result.attempts == ()
    assert result.candidates == ()

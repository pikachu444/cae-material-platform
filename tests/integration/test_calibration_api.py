from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import cast
from uuid import UUID, uuid4

import httpx
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
from cmp.modules.modeling.adapters.api.calibration import install_calibration_api
from cmp.modules.modeling.application.calibration import (
    CALIBRATION_PLAN_AGGREGATE_TYPE,
    CalibrationAttempt,
    CalibrationCandidate,
    CalibrationDiagnosticPreview,
    CalibrationPlanSnapshot,
    CalibrationRun,
    CalibrationRunDetail,
    CreateReferenceLinearElasticCalibrationPlan,
    ExecuteReferenceLinearElasticCalibration,
    ReferenceCalibrationService,
    ReviseReferenceLinearElasticCalibrationPlan,
)
from cmp.modules.modeling.application.service import RevisionSnapshot
from cmp.modules.modeling.domain.reference_linear_elastic_calibration import (
    CalibrationAttemptStatus,
    CalibrationCandidateStatus,
    CalibrationCurvePoint,
    CalibrationRunStatus,
    ReferenceLinearElasticCalibrationPlanContent,
)
from cmp.shared.domain.revisions import RevisionRecord, TenantScope
from fastapi import FastAPI, Request

NOW = datetime(2026, 7, 19, 9, 0, tzinfo=UTC)
ORG = UUID("d3000000-0000-4000-8000-000000000001")
PROJECT = UUID("d3000000-0000-4000-8000-000000000002")
ACTOR = UUID("d3000000-0000-4000-8000-000000000003")
PLAN = UUID("d3000000-0000-4000-8000-000000000004")
PLAN_REVISION = UUID("d3000000-0000-4000-8000-000000000005")
SELECTION = UUID("d3000000-0000-4000-8000-000000000006")
SELECTION_REVISION = UUID("d3000000-0000-4000-8000-000000000007")
MODEL = UUID("d3000000-0000-4000-8000-000000000008")
MODEL_REVISION = UUID("d3000000-0000-4000-8000-000000000009")
DATASET = UUID("d3000000-0000-4000-8000-00000000000a")
DATASET_REVISION = UUID("d3000000-0000-4000-8000-00000000000b")
RUN = UUID("d3000000-0000-4000-8000-00000000000c")
ATTEMPT = UUID("d3000000-0000-4000-8000-00000000000d")
CANDIDATE = UUID("d3000000-0000-4000-8000-00000000000e")
DIAGNOSTICS = UUID("d3000000-0000-4000-8000-00000000000f")
TRACE = "00-000000000000000000000000000000d3-00000000000000d3-01"


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


def _decision(permission: Permission) -> AuthorizationDecision:
    return AuthorizationDecision(
        principal_id=ACTOR,
        organization_id=ORG,
        project_id=PROJECT,
        permission=permission,
        roles=(Role.MATERIAL_MODELER,),
        database_permissions=database_permissions_for(permission),
        max_classification=DataClassification.INTERNAL,
        allow_export_controlled=False,
        request_id=CONTEXT.request_id,
        trace_id=TRACE,
        decided_at=NOW,
    )


READ = _decision(Permission.MODELING_READ)
EXECUTE = _decision(Permission.CALIBRATION_EXECUTE)


def _content() -> ReferenceLinearElasticCalibrationPlanContent:
    return ReferenceLinearElasticCalibrationPlanContent(
        plan_label="Reference calibration",
        selection_id=SELECTION,
        selection_revision_id=SELECTION_REVISION,
        material_model_id=MODEL,
        material_model_revision_id=MODEL_REVISION,
        youngs_modulus_lower_bound_pa=100_000_000_000.0,
        youngs_modulus_initial_value_pa=190_000_000_000.0,
        youngs_modulus_upper_bound_pa=300_000_000_000.0,
        normalization_stress_scale_pa=1_000_000.0,
        multistart_count=1,
        random_seed=0,
    )


def _record() -> RevisionRecord:
    return RevisionRecord(
        revision_id=PLAN_REVISION,
        aggregate_type=CALIBRATION_PLAN_AGGREGATE_TYPE,
        aggregate_id=PLAN,
        scope=TenantScope(ORG, PROJECT, DataClassification.INTERNAL.value),
        revision_no=1,
        based_on_revision_id=None,
        schema_id="urn:cmp:modeling:reference-uniaxial-linear-elastic-calibration:1.0.0",
        schema_version="1.0.0",
        content_hash="d" * 64,
        created_at=NOW,
        created_by=ACTOR,
        change_reason="create reference calibration plan",
        request_id=CONTEXT.request_id,
        trace_id=TRACE,
    )


class _CalibrationService:
    def __init__(self) -> None:
        self.plan = CalibrationPlanSnapshot(PLAN, RevisionSnapshot(_record(), _content()))
        self.run = CalibrationRun(
            id=RUN,
            classification=DataClassification.INTERNAL,
            plan_id=PLAN,
            plan_revision_id=PLAN_REVISION,
            selection_id=SELECTION,
            selection_revision_id=SELECTION_REVISION,
            dataset_id=DATASET,
            dataset_revision_id=DATASET_REVISION,
            material_model_id=MODEL,
            material_model_revision_id=MODEL_REVISION,
            execution_mode="reference_inline",
            reproducibility_level="R3",
            environment_digest="e" * 64,
            status=CalibrationRunStatus.SUCCEEDED,
            attempt_count=1,
            candidate_count=1,
            failure_code=None,
            change_reason="execute reference calibration",
            started_at=NOW,
            ended_at=NOW,
            created_by=ACTOR,
            request_id=CONTEXT.request_id,
            trace_id=TRACE,
        )
        self.attempt = CalibrationAttempt(
            id=ATTEMPT,
            calibration_run_id=RUN,
            attempt_ordinal=1,
            initial_youngs_modulus_pa=190_000_000_000.0,
            random_seed=0,
            status=CalibrationAttemptStatus.SUCCEEDED,
            candidate_id=CANDIDATE,
            failure_code=None,
            started_at=NOW,
            ended_at=NOW,
        )
        self.candidate = CalibrationCandidate(
            id=CANDIDATE,
            calibration_run_id=RUN,
            calibration_attempt_id=ATTEMPT,
            attempt_ordinal=1,
            status=CalibrationCandidateStatus.CONVERGED,
            candidate_sha256="c" * 64,
            youngs_modulus_pa=200_000_000_000.0,
            objective_total=0.0,
            residual_root_mean_square_pa=0.0,
            residual_mean_pa=0.0,
            bound_sticking=False,
            convergence_reason="analytic_bounded_weighted_least_squares",
            identifiability_status="not_assessed_reference_one_parameter",
            uncertainty_status="not_estimated_reference",
            diagnostics_artifact_id=DIAGNOSTICS,
            diagnostics_sha256="b" * 64,
            diagnostics_point_count=3,
            created_at=NOW,
            created_by=ACTOR,
        )

    def create_plan(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CreateReferenceLinearElasticCalibrationPlan,
    ) -> CalibrationPlanSnapshot:
        assert context is CONTEXT and decision is EXECUTE
        assert command.classification is DataClassification.INTERNAL
        assert command.content.plan_label == "Reference calibration"
        return self.plan

    def revise_plan(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        plan_id: UUID,
        command: ReviseReferenceLinearElasticCalibrationPlan,
    ) -> CalibrationPlanSnapshot:
        assert context is CONTEXT and decision is EXECUTE and plan_id == PLAN
        assert command.expected_current_revision_id == PLAN_REVISION
        return self.plan

    def list_plans(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        *,
        limit: int,
    ) -> tuple[CalibrationPlanSnapshot, ...]:
        assert context is CONTEXT and decision is READ and limit == 100
        return (self.plan,)

    def get_plan(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        plan_id: UUID,
    ) -> CalibrationPlanSnapshot:
        assert context is CONTEXT and decision is READ and plan_id == PLAN
        return self.plan

    async def execute(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: ExecuteReferenceLinearElasticCalibration,
    ) -> CalibrationRunDetail:
        assert context is CONTEXT and decision is EXECUTE
        assert (command.plan_id, command.plan_revision_id) == (PLAN, PLAN_REVISION)
        return CalibrationRunDetail(self.run, (self.attempt,), (self.candidate,))

    def get_run(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
    ) -> CalibrationRunDetail:
        assert context is CONTEXT and decision is READ and run_id == RUN
        return CalibrationRunDetail(self.run, (self.attempt,), (self.candidate,))

    async def preview_candidate_diagnostics(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        candidate_id: UUID,
        *,
        maximum_points: int,
    ) -> CalibrationDiagnosticPreview:
        assert context is CONTEXT and decision is READ and candidate_id == CANDIDATE
        assert maximum_points == 500
        return CalibrationDiagnosticPreview(
            calibration_candidate_id=CANDIDATE,
            point_count=3,
            returned_point_count=3,
            sampled=False,
            points=(
                CalibrationCurvePoint(0.0, 0.0, 0.0, 0.0, 0.0),
                CalibrationCurvePoint(0.01, 2_000_000_000.0, 2_000_000_000.0, 0.0, 0.0),
                CalibrationCurvePoint(0.02, 4_000_000_000.0, 4_000_000_000.0, 0.0, 0.0),
            ),
        )


def _application() -> FastAPI:
    application = FastAPI()
    service = _CalibrationService()

    def security(request: Request) -> None:
        request.state.security_context = CONTEXT

    def read(request: Request) -> None:
        request.state.authorization_decision = READ

    def execute(request: Request) -> None:
        request.state.authorization_decision = EXECUTE

    install_calibration_api(
        application,
        service=cast(ReferenceCalibrationService, service),
        security_dependency=security,
        read_dependency=read,
        execute_dependency=execute,
    )
    return application


def _request(
    application: FastAPI,
    method: str,
    path: str,
    *,
    json: dict[str, object] | None = None,
) -> httpx.Response:
    async def send() -> httpx.Response:
        transport = httpx.ASGITransport(app=application)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.request(method, path, json=json)

    return asyncio.run(send())


def test_calibration_api_exposes_immutable_plan_run_candidate_and_diagnostics_workflow() -> None:
    application = _application()
    created = _request(
        application,
        "POST",
        "/api/v1/calibration-plans",
        json={
            "classification": "internal",
            "plan_label": "Reference calibration",
            "selection_id": str(SELECTION),
            "selection_revision_id": str(SELECTION_REVISION),
            "material_model_id": str(MODEL),
            "material_model_revision_id": str(MODEL_REVISION),
            "youngs_modulus_lower_bound_pa": 100_000_000_000.0,
            "youngs_modulus_initial_value_pa": 190_000_000_000.0,
            "youngs_modulus_upper_bound_pa": 300_000_000_000.0,
            "normalization_stress_scale_pa": 1_000_000.0,
            "multistart_count": 1,
            "random_seed": 0,
            "change_reason": "Create reference calibration plan",
        },
    )

    assert created.status_code == 201
    assert created.headers["ETag"] == '"revision:1:sha256:' + "d" * 64 + '"'
    assert created.json()["current_revision"]["content"]["non_production"] is True
    assert created.json()["current_revision"]["content"]["evaluation_mode"] == "closed_form_curve"

    run = _request(
        application,
        "POST",
        "/api/v1/calibration-runs",
        json={
            "plan_id": str(PLAN),
            "plan_revision_id": str(PLAN_REVISION),
            "change_reason": "Execute reference calibration",
        },
    )
    assert run.status_code == 201
    assert run.json()["status"] == "succeeded"
    assert run.json()["candidates"][0]["youngs_modulus_pa"] == 200_000_000_000.0
    assert run.json()["candidates"][0]["candidate_sha256"] == "sha256:" + "c" * 64

    diagnostics = _request(
        application,
        "GET",
        f"/api/v1/calibration-candidates/{CANDIDATE}/diagnostics-preview",
    )
    assert diagnostics.status_code == 200
    assert diagnostics.json()["points"][1]["predicted_engineering_stress_pa"] == 2_000_000_000.0

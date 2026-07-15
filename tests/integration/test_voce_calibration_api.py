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
from cmp.modules.identity_access.domain.security import Principal, PrincipalType, SecurityContext
from cmp.modules.modeling.adapters.api.voce_calibration import install_voce_calibration_api
from cmp.modules.modeling.application.service import RevisionSnapshot
from cmp.modules.modeling.application.voce_calibration import (
    VOCE_CALIBRATION_PLAN_AGGREGATE_TYPE,
    CreateReferenceVoceCalibrationPlan,
    ExecuteReferenceVoceCalibration,
    ReferenceVoceCalibrationService,
    VoceCalibrationAttempt,
    VoceCalibrationCandidate,
    VoceCalibrationDiagnosticPreview,
    VoceCalibrationPlanSnapshot,
    VoceCalibrationRun,
    VoceCalibrationRunDetail,
)
from cmp.modules.modeling.domain.reference_linear_elastic_calibration import (
    CalibrationAttemptStatus,
    CalibrationCandidateStatus,
    CalibrationRunStatus,
)
from cmp.modules.modeling.domain.reference_voce_calibration import (
    ReferenceVoceCalibrationPlanContent,
    VoceDiagnosticPoint,
    VoceObjectiveTerm,
    VoceParameterPlan,
)
from cmp.shared.domain.revisions import RevisionRecord, TenantScope
from fastapi import FastAPI, Request

NOW = datetime(2026, 7, 15, tzinfo=UTC)
IDS = tuple(UUID(int=index) for index in range(1, 20))
ORG, PROJECT, ACTOR, PLAN, PLAN_REVISION, SCOPE, SCOPE_REVISION = IDS[:7]
STATE, STATE_REVISION, PROPERTIES, PROPERTIES_REVISION = IDS[7:11]
RUN, ATTEMPT, CANDIDATE, DATASET, DATASET_REVISION, ARTIFACT = IDS[11:17]
TRACE = "00-000000000000000000000000000000a1-00000000000000a1-01"

CONTEXT = SecurityContext(
    principal=Principal(ACTOR, PrincipalType.USER, "Modeler", True),
    organization_id=ORG,
    project_id=PROJECT,
    issuer="https://idp.invalid",
    subject=str(ACTOR),
    token_id=str(uuid4()),
    groups=(),
    scopes=("openid",),
    request_id=uuid4(),
    trace_id=TRACE,
    authenticated_at=NOW,
)


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


def _content() -> ReferenceVoceCalibrationPlanContent:
    return ReferenceVoceCalibrationPlanContent(
        plan_label="Reviewed Voce",
        calibration_input_scope_id=SCOPE,
        calibration_input_scope_revision_id=SCOPE_REVISION,
        material_state_id=STATE,
        material_state_revision_id=STATE_REVISION,
        property_set_id=PROPERTIES,
        property_set_revision_id=PROPERTIES_REVISION,
        youngs_modulus_pa=210e9,
        sigma_0=VoceParameterPlan("sigma_0_pa", "Pa", 200e6, 300e6, 400e6, 300e6),
        q=VoceParameterPlan("q_pa", "Pa", 20e6, 150e6, 600e6, 150e6),
        b=VoceParameterPlan("b", "1", 0.5, 10.0, 100.0, 10.0),
        normalization_stress_scale_pa=100e6,
        multistart_count=1,
        random_seed=20260715,
    )


def _record() -> RevisionRecord:
    return RevisionRecord(
        revision_id=PLAN_REVISION,
        aggregate_type=VOCE_CALIBRATION_PLAN_AGGREGATE_TYPE,
        aggregate_id=PLAN,
        scope=TenantScope(ORG, PROJECT, "internal"),
        revision_no=1,
        based_on_revision_id=None,
        schema_id="urn:cmp:modeling:reference-voce-calibration-plan:1.0.0",
        schema_version="1.0.0",
        content_hash="a" * 64,
        created_at=NOW,
        created_by=ACTOR,
        change_reason="create",
        request_id=CONTEXT.request_id,
        trace_id=TRACE,
    )


class _Service:
    def __init__(self) -> None:
        self.plan = VoceCalibrationPlanSnapshot(PLAN, RevisionSnapshot(_record(), _content()))
        self.run = VoceCalibrationRun(
            id=RUN,
            classification=DataClassification.INTERNAL,
            plan_id=PLAN,
            plan_revision_id=PLAN_REVISION,
            calibration_input_scope_id=SCOPE,
            calibration_input_scope_revision_id=SCOPE_REVISION,
            property_set_id=PROPERTIES,
            property_set_revision_id=PROPERTIES_REVISION,
            source_curve_count=3,
            execution_mode="reference_inline_scipy",
            reproducibility_level="R3",
            environment_digest="e" * 64,
            status=CalibrationRunStatus.SUCCEEDED,
            attempt_count=1,
            candidate_count=1,
            failure_code=None,
            change_reason="execute",
            started_at=NOW,
            ended_at=NOW,
            created_by=ACTOR,
            request_id=CONTEXT.request_id,
            trace_id=TRACE,
        )
        self.attempt = VoceCalibrationAttempt(
            ATTEMPT,
            RUN,
            1,
            300e6,
            150e6,
            10.0,
            20260715,
            CalibrationAttemptStatus.SUCCEEDED,
            CANDIDATE,
            None,
            NOW,
            NOW,
        )
        self.candidate = VoceCalibrationCandidate(
            id=CANDIDATE,
            calibration_run_id=RUN,
            calibration_attempt_id=ATTEMPT,
            attempt_ordinal=1,
            status=CalibrationCandidateStatus.CONVERGED,
            candidate_sha256="c" * 64,
            sigma_0_pa=301e6,
            q_pa=159e6,
            b=12.1,
            objective_total=0.0002,
            residual_root_mean_square_pa=1.2e6,
            residual_mean_pa=0,
            sigma_0_at_bound=False,
            q_at_bound=False,
            b_at_bound=False,
            convergence_status_code=1,
            convergence_reason="gtol satisfied",
            function_evaluations=18,
            jacobian_evaluations=16,
            optimality=1e-9,
            warning_at_bound=False,
            warning_nonconvergence=False,
            identifiability_status="not_assessed_reference",
            uncertainty_status="not_provided_reference",
            diagnostics_artifact_id=ARTIFACT,
            diagnostics_sha256="d" * 64,
            diagnostics_point_count=15,
            objective_terms=(VoceObjectiveTerm(0, DATASET, DATASET_REVISION, 5, 0.0002),),
            created_at=NOW,
            created_by=ACTOR,
        )

    def create_plan(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CreateReferenceVoceCalibrationPlan,
    ) -> VoceCalibrationPlanSnapshot:
        assert context is CONTEXT and decision is EXECUTE
        assert command.content.calibration_input_scope_revision_id == SCOPE_REVISION
        return self.plan

    async def execute(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: ExecuteReferenceVoceCalibration,
    ) -> VoceCalibrationRunDetail:
        assert context is CONTEXT and decision is EXECUTE
        assert command.plan_revision_id == PLAN_REVISION
        return VoceCalibrationRunDetail(self.run, (self.attempt,), (self.candidate,))

    async def preview_candidate_diagnostics(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        candidate_id: UUID,
        *,
        maximum_points: int,
    ) -> VoceCalibrationDiagnosticPreview:
        assert context is CONTEXT and decision is READ and candidate_id == CANDIDATE
        points = tuple(
            VoceDiagnosticPoint(
                member_ordinal=index // 3,
                dataset_revision_id=DATASET_REVISION,
                point_ordinal=index % 3,
                true_plastic_strain=0.01 * (index % 3 + 1),
                observed_true_yield_stress_pa=320e6 + index * 10e6,
                predicted_true_yield_stress_pa=321e6 + index * 10e6,
                residual_true_yield_stress_pa=1e6,
                normalized_residual=0.01,
                effective_weight=1 / 6,
            )
            for index in range(6)
        )
        return VoceCalibrationDiagnosticPreview(CANDIDATE, 6, 6, False, points)


def _app() -> FastAPI:
    app = FastAPI()

    def security(request: Request) -> None:
        request.state.security_context = CONTEXT

    def read(request: Request) -> None:
        request.state.authorization_decision = READ

    def execute(request: Request) -> None:
        request.state.authorization_decision = EXECUTE

    install_voce_calibration_api(
        app,
        service=cast(ReferenceVoceCalibrationService, _Service()),
        security_dependency=security,
        read_dependency=read,
        execute_dependency=execute,
    )
    return app


def _request(
    app: FastAPI, method: str, path: str, body: dict[str, object] | None = None
) -> httpx.Response:
    async def send() -> httpx.Response:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            return await client.request(method, path, json=body)

    return asyncio.run(send())


def test_voce_api_pins_reviewed_scope_and_returns_explicit_candidate_diagnostics() -> None:
    fields: dict[str, object] = {
        "classification": "internal",
        "plan_label": "Reviewed Voce",
        "calibration_input_scope_id": str(SCOPE),
        "calibration_input_scope_revision_id": str(SCOPE_REVISION),
        "material_state_id": str(STATE),
        "material_state_revision_id": str(STATE_REVISION),
        "property_set_id": str(PROPERTIES),
        "property_set_revision_id": str(PROPERTIES_REVISION),
        "youngs_modulus_pa": 210e9,
        "sigma_0_pa": {"lower": 200e6, "initial": 300e6, "upper": 400e6, "scale": 300e6},
        "q_pa": {"lower": 20e6, "initial": 150e6, "upper": 600e6, "scale": 150e6},
        "b": {"lower": 0.5, "initial": 10.0, "upper": 100.0, "scale": 10.0},
        "normalization_stress_scale_pa": 100e6,
        "multistart_count": 1,
        "random_seed": 20260715,
        "maximum_function_evaluations": 2000,
        "ftol": 1e-10,
        "xtol": 1e-10,
        "gtol": 1e-10,
        "change_reason": "pin reviewed scope",
    }
    created = _request(_app(), "POST", "/api/v1/voce-calibration-plans", fields)
    assert created.status_code == 201
    assert created.headers["etag"] == '"revision:1:sha256:' + "a" * 64 + '"'
    assert created.json()["current_revision"]["content"]["optimizer_method"] == "trf"

    run = _request(
        _app(),
        "POST",
        f"/api/v1/voce-calibration-plans/{PLAN}/runs",
        {"plan_revision_id": str(PLAN_REVISION), "change_reason": "execute"},
    )
    assert run.status_code == 201
    candidate = run.json()["candidates"][0]
    assert candidate["sigma_0_pa"] == 301e6
    assert candidate["objective_terms"][0]["dataset_revision_id"] == str(DATASET_REVISION)
    assert candidate["identifiability_status"] == "not_assessed_reference"

    preview = _request(
        _app(),
        "GET",
        f"/api/v1/voce-calibration-candidates/{CANDIDATE}/diagnostics-preview",
    )
    assert preview.status_code == 200
    assert preview.json()["points"][0]["residual_true_yield_stress_pa"] == 1e6

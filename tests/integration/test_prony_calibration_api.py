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
from cmp.modules.modeling.adapters.api.prony_calibration import install_prony_calibration_api
from cmp.modules.modeling.application.prony_calibration import (
    PRONY_CALIBRATION_PLAN_AGGREGATE_TYPE,
    CreateReferencePronyCalibrationPlan,
    ExecuteReferencePronyCalibration,
    PersistedPronyCandidate,
    PronyCalibrationPlanSnapshot,
    PronyCalibrationRun,
    ReferencePronyCalibrationService,
)
from cmp.modules.modeling.application.service import RevisionSnapshot
from cmp.modules.modeling.domain.reference_prony_calibration import (
    PronyCalibrationCandidate,
    PronyParameterPlan,
    ReferencePronyCalibrationPlanContent,
)
from cmp.modules.processing.domain.reference_tensile_crop import ProcessingRunStatus
from cmp.shared.domain.revisions import RevisionRecord, TenantScope
from fastapi import FastAPI, Request

NOW = datetime(2026, 7, 16, tzinfo=UTC)
IDS = tuple(UUID(int=index) for index in range(1, 20))
ORG, PROJECT, ACTOR, PLAN, PLAN_REVISION, DATASET, DATASET_REVISION = IDS[:7]
MODEL, MODEL_REVISION, RUN, ATTEMPT, CANDIDATE, ARTIFACT = IDS[7:13]
TRACE = "00-000000000000000000000000000000b1-00000000000000b1-01"
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


def _content() -> ReferencePronyCalibrationPlanContent:
    return ReferencePronyCalibrationPlanContent(
        plan_label="Reference Prony",
        input_dataset_id=DATASET,
        input_dataset_revision_id=DATASET_REVISION,
        baseline_model_id=MODEL,
        baseline_model_revision_id=MODEL_REVISION,
        total_g_ratio=PronyParameterPlan("total_g_ratio", "1", 0.1, 0.4, 0.9, "none"),
        fast_term_fraction=PronyParameterPlan(
            "fast_term_fraction", "1", 0.1, 0.5, 0.9, "none"
        ),
        fast_relaxation_time_s=PronyParameterPlan(
            "fast_relaxation_time_s", "s", 0.01, 0.1, 1.0, "log"
        ),
        slow_relaxation_time_s=PronyParameterPlan(
            "slow_relaxation_time_s", "s", 2.0, 10.0, 100.0, "log"
        ),
        normalization_modulus_pa=1e9,
        multistart_count=1,
        random_seed=7,
    )


def _record() -> RevisionRecord:
    return RevisionRecord(
        revision_id=PLAN_REVISION,
        aggregate_type=PRONY_CALIBRATION_PLAN_AGGREGATE_TYPE,
        aggregate_id=PLAN,
        scope=TenantScope(ORG, PROJECT, "internal"),
        revision_no=1,
        based_on_revision_id=None,
        schema_id="urn:cmp:modeling:reference-prony-calibration-plan:1.0.0",
        schema_version="1.0.0",
        content_hash="a" * 64,
        created_at=NOW,
        created_by=ACTOR,
        change_reason="create",
        request_id=CONTEXT.request_id,
        trace_id=TRACE,
    )


def _candidate() -> PersistedPronyCandidate:
    value = PronyCalibrationCandidate(
        attempt_ordinal=1,
        initial_values=(0.4, 0.5, 0.1, 10.0),
        total_g_ratio=0.5,
        fast_term_fraction=0.4,
        fast_g_ratio=0.2,
        slow_g_ratio=0.3,
        fast_relaxation_time_s=0.12,
        slow_relaxation_time_s=12.0,
        objective_total=0.001,
        residual_root_mean_square_pa=1e6,
        residual_mean_pa=0.0,
        status="converged",
        convergence_status_code=1,
        convergence_reason="gtol satisfied",
        function_evaluations=12,
        jacobian_evaluations=10,
        optimality=1e-10,
        parameter_at_bound=False,
        identifiability_status="full_rank",
        uncertainty_status="not_assessed_reference",
        predicted_modulus_pa=(),
        residual_pa=(),
        candidate_sha256="c" * 64,
    )
    return PersistedPronyCandidate(
        CANDIDATE, ATTEMPT, RUN, value, ARTIFACT, "d" * 64, 5, NOW, ACTOR
    )


class _Service:
    def __init__(self) -> None:
        self.plan = PronyCalibrationPlanSnapshot(
            PLAN, RevisionSnapshot(_record(), _content())
        )
        self.run = PronyCalibrationRun(
            RUN,
            DataClassification.INTERNAL,
            PLAN,
            PLAN_REVISION,
            DATASET,
            DATASET_REVISION,
            MODEL,
            MODEL_REVISION,
            ProcessingRunStatus.SUCCEEDED,
            "e" * 64,
            1,
            1,
            None,
            "execute",
            NOW,
            NOW,
            ACTOR,
            CONTEXT.request_id,
            TRACE,
            (_candidate(),),
        )

    def create_plan(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CreateReferencePronyCalibrationPlan,
    ) -> PronyCalibrationPlanSnapshot:
        assert context is CONTEXT and decision is EXECUTE
        assert command.content.input_dataset_revision_id == DATASET_REVISION
        return self.plan

    async def execute(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: ExecuteReferencePronyCalibration,
    ) -> PronyCalibrationRun:
        assert context is CONTEXT and decision is EXECUTE
        assert command.plan_revision_id == PLAN_REVISION
        return self.run

    def get_run(
        self, context: SecurityContext, decision: AuthorizationDecision, run_id: UUID
    ) -> PronyCalibrationRun:
        assert context is CONTEXT and decision is READ and run_id == RUN
        return self.run

    async def candidate_diagnostics(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        candidate_id: UUID,
    ) -> tuple[dict[str, float | int], ...]:
        assert context is CONTEXT and decision is READ and candidate_id == CANDIDATE
        return (
            {
                "point_ordinal": 0,
                "time_s": 0.1,
                "observed_shear_modulus_pa": 8e8,
                "predicted_shear_modulus_pa": 8.01e8,
                "residual_pa": 1e6,
            },
        )


def _app() -> FastAPI:
    app = FastAPI()
    service = cast(ReferencePronyCalibrationService, _Service())

    async def security(request: Request) -> None:
        request.state.security_context = CONTEXT

    async def read(request: Request) -> None:
        request.state.authorization_decision = READ

    async def execute(request: Request) -> None:
        request.state.authorization_decision = EXECUTE

    install_prony_calibration_api(
        app,
        service=service,
        security_dependency=security,
        read_dependency=read,
        execute_dependency=execute,
    )
    return app


async def _request() -> None:
    transport = httpx.ASGITransport(app=_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        content = _content()
        created = await client.post(
            "/api/v1/prony-calibration-plans",
            json={
                "classification": "internal",
                "plan_label": content.plan_label,
                "input_dataset_id": str(DATASET),
                "input_dataset_revision_id": str(DATASET_REVISION),
                "baseline_model_id": str(MODEL),
                "baseline_model_revision_id": str(MODEL_REVISION),
                "total_g_ratio": {"lower": 0.1, "initial": 0.4, "upper": 0.9},
                "fast_term_fraction": {"lower": 0.1, "initial": 0.5, "upper": 0.9},
                "fast_relaxation_time_s": {"lower": 0.01, "initial": 0.1, "upper": 1},
                "slow_relaxation_time_s": {"lower": 2, "initial": 10, "upper": 100},
                "normalization_modulus_pa": 1e9,
                "multistart_count": 1,
                "random_seed": 7,
                "change_reason": "create",
            },
        )
        assert created.status_code == 201
        assert created.json()["current_revision"]["content"]["non_production"] is True
        executed = await client.post(
            f"/api/v1/prony-calibration-plans/{PLAN}/runs",
            json={"plan_revision_id": str(PLAN_REVISION), "change_reason": "execute"},
        )
        assert executed.status_code == 201
        assert executed.json()["candidates"][0]["fast_g_ratio"] == 0.2
        diagnostics = await client.get(
            f"/api/v1/prony-calibration-candidates/{CANDIDATE}/diagnostics"
        )
        assert diagnostics.status_code == 200
        assert diagnostics.json()["points"][0]["residual_pa"] == 1e6


def test_prony_calibration_api_contract() -> None:
    asyncio.run(_request())

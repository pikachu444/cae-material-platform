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
from cmp.modules.modeling.application.service import RevisionSnapshot
from cmp.modules.validation.adapters.api.voce_holdout import install_voce_holdout_api
from cmp.modules.validation.application.voce_holdout import (
    VOCE_HOLDOUT_PLAN_AGGREGATE_TYPE,
    CreateReferenceVoceHoldoutPlan,
    ExecuteReferenceVoceHoldout,
    ReferenceVoceHoldoutService,
    VoceHoldoutPlanSnapshot,
)
from cmp.modules.validation.domain.reference_voce_holdout import (
    REFERENCE_VOCE_HOLDOUT_PLAN_SCHEMA_ID,
    ReferenceVoceHoldoutComparisonPoint,
    ReferenceVoceHoldoutMetrics,
    ReferenceVoceHoldoutPlanContent,
    ReferenceVoceHoldoutResult,
    VoceHoldoutVerdict,
)
from cmp.shared.domain.revisions import RevisionRecord, TenantScope
from fastapi import FastAPI, Request

NOW = datetime(2026, 7, 15, tzinfo=UTC)
IDS = tuple(UUID(int=index) for index in range(1, 30))
ORG, PROJECT, ACTOR, PLAN, PLAN_REVISION, MODEL, MODEL_REVISION = IDS[:7]
DATASET, DATASET_REVISION, TEST_RUN, TEST_RUN_REVISION, RUN, RESULT = IDS[7:13]
TRACE = "00-000000000000000000000000000000c1-00000000000000c1-01"
CONTEXT = SecurityContext(
    principal=Principal(ACTOR, PrincipalType.USER, "Validator", True),
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
        roles=(Role.CAE_ANALYST,),
        database_permissions=database_permissions_for(permission),
        max_classification=DataClassification.INTERNAL,
        allow_export_controlled=False,
        request_id=CONTEXT.request_id,
        trace_id=TRACE,
        decided_at=NOW,
    )


READ = _decision(Permission.VALIDATION_READ)
EXECUTE = _decision(Permission.VALIDATION_EXECUTE)


def _content() -> ReferenceVoceHoldoutPlanContent:
    return ReferenceVoceHoldoutPlanContent(
        plan_label="Independent DP780 holdout",
        material_model_id=MODEL,
        material_model_revision_id=MODEL_REVISION,
        holdout_dataset_id=DATASET,
        holdout_dataset_revision_id=DATASET_REVISION,
    )


def _plan() -> VoceHoldoutPlanSnapshot:
    record = RevisionRecord(
        revision_id=PLAN_REVISION,
        aggregate_type=VOCE_HOLDOUT_PLAN_AGGREGATE_TYPE,
        aggregate_id=PLAN,
        scope=TenantScope(ORG, PROJECT, "internal"),
        revision_no=1,
        based_on_revision_id=None,
        schema_id=REFERENCE_VOCE_HOLDOUT_PLAN_SCHEMA_ID,
        schema_version="1.0.0",
        content_hash="a" * 64,
        created_at=NOW,
        created_by=ACTOR,
        change_reason="pin independent holdout",
        request_id=CONTEXT.request_id,
        trace_id=TRACE,
    )
    return VoceHoldoutPlanSnapshot(PLAN, RevisionSnapshot(record, _content()))


def _result() -> ReferenceVoceHoldoutResult:
    points = tuple(
        ReferenceVoceHoldoutComparisonPoint(
            source_point_ordinal=index,
            true_plastic_strain=0.01 * (index + 1),
            observed_true_yield_stress_pa=400e6 + index * 10e6,
            predicted_true_yield_stress_pa=401e6 + index * 10e6,
            residual_true_yield_stress_pa=1e6,
        )
        for index in range(3)
    )
    return ReferenceVoceHoldoutResult(
        id=RESULT,
        run_id=RUN,
        plan_id=PLAN,
        plan_revision_id=PLAN_REVISION,
        material_model_id=MODEL,
        material_model_revision_id=MODEL_REVISION,
        calibration_input_scope_id=IDS[13],
        calibration_input_scope_revision_id=IDS[14],
        voce_calibration_run_id=IDS[15],
        voce_calibration_candidate_id=IDS[16],
        voce_candidate_selection_id=IDS[17],
        voce_candidate_selection_revision_id=IDS[18],
        holdout_dataset_id=DATASET,
        holdout_dataset_revision_id=DATASET_REVISION,
        holdout_test_run_id=TEST_RUN,
        holdout_test_run_revision_id=TEST_RUN_REVISION,
        source_data_artifact_id=IDS[19],
        source_data_sha256="b" * 64,
        comparison_artifact_id=IDS[20],
        comparison_sha256="c" * 64,
        metrics=ReferenceVoceHoldoutMetrics(
            points=points,
            root_mean_squared_error_pa=1e6,
            relative_root_mean_squared_error=0.0024,
            normalization_stress_scale_pa=420e6,
            characterized_max_true_plastic_strain=0.03,
            verdict=VoceHoldoutVerdict.PASSED,
        ),
        created_at=NOW,
        created_by=ACTOR,
    )


class _Service:
    def create_plan(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CreateReferenceVoceHoldoutPlan,
    ) -> VoceHoldoutPlanSnapshot:
        assert context is CONTEXT and decision is EXECUTE
        assert command.content.holdout_dataset_revision_id == DATASET_REVISION
        return _plan()

    def list_plans(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        *,
        limit: int = 100,
    ) -> tuple[VoceHoldoutPlanSnapshot, ...]:
        assert context is CONTEXT and decision is READ and limit == 100
        return (_plan(),)

    async def execute(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: ExecuteReferenceVoceHoldout,
    ) -> ReferenceVoceHoldoutResult:
        assert context is CONTEXT and decision is EXECUTE
        assert command.plan_id == PLAN and command.plan_revision_id == PLAN_REVISION
        return _result()

    def get_result(
        self, context: SecurityContext, decision: AuthorizationDecision, result_id: UUID
    ) -> ReferenceVoceHoldoutResult:
        assert context is CONTEXT and decision is READ and result_id == RESULT
        return _result()

    def list_results_for_model(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_model_id: UUID,
        *,
        limit: int = 100,
    ) -> tuple[ReferenceVoceHoldoutResult, ...]:
        assert context is CONTEXT and decision is READ
        assert material_model_id == MODEL and limit == 100
        return (_result(),)


def _app() -> FastAPI:
    app = FastAPI()

    def security(request: Request) -> None:
        request.state.security_context = CONTEXT

    def read(request: Request) -> None:
        request.state.authorization_decision = READ

    def execute(request: Request) -> None:
        request.state.authorization_decision = EXECUTE

    install_voce_holdout_api(
        app,
        service=cast(ReferenceVoceHoldoutService, _Service()),
        security_dependency=security,
        read_dependency=read,
        execute_dependency=execute,
    )
    return app


def _request(method: str, path: str, body: dict[str, object] | None = None) -> httpx.Response:
    async def send() -> httpx.Response:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=_app()), base_url="http://test"
        ) as client:
            return await client.request(method, path, json=body)

    return asyncio.run(send())


def test_voce_holdout_api_exposes_solver_independent_result() -> None:
    created = _request(
        "POST",
        "/api/v1/voce-holdout-validation-plans",
        {
            "classification": "internal",
            "content": {
                "plan_label": "Independent DP780 holdout",
                "material_model_id": str(MODEL),
                "material_model_revision_id": str(MODEL_REVISION),
                "holdout_dataset_id": str(DATASET),
                "holdout_dataset_revision_id": str(DATASET_REVISION),
            },
            "change_reason": "pin independent holdout",
        },
    )
    assert created.status_code == 201
    assert created.headers["etag"]
    assert created.json()["current_revision"]["content"]["solver_execution"] == "not_used"

    executed = _request(
        "POST",
        f"/api/v1/voce-holdout-validation-plans/{PLAN}/runs",
        {
            "plan_revision_id": str(PLAN_REVISION),
            "change_reason": "evaluate without solver",
        },
    )
    assert executed.status_code == 201
    body = executed.json()
    assert body["holdout_independence"] == "disjoint_dataset_and_test_run"
    assert body["evaluation_mode"] == "closed_form_curve"
    assert body["solver_execution"] == "not_used"
    assert body["verdict"] == "passed"
    assert len(body["points"]) == 3

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
from cmp.modules.modeling.adapters.api.ogden_calibration import install_ogden_calibration_api
from cmp.modules.modeling.application.ogden_calibration import (
    OGDEN_CALIBRATION_PLAN_AGGREGATE_TYPE,
    CreateReferenceOgdenCalibrationPlan,
    ExecuteReferenceOgdenCalibration,
    OgdenCalibrationPlanSnapshot,
    OgdenCalibrationRun,
    PersistedHyperelasticFamilyCandidate,
    PersistedOgdenCandidate,
    ReferenceOgdenCalibrationService,
)
from cmp.modules.modeling.application.service import RevisionSnapshot
from cmp.modules.modeling.domain.hyperelastic_families import (
    HyperelasticDiagnosticPoint,
    HyperelasticFamily,
    fit_hyperelastic_families,
)
from cmp.modules.modeling.domain.reference_ogden_calibration import (
    REFERENCE_OGDEN_CALIBRATION_PLAN_SCHEMA_ID,
    OgdenCalibrationCurve,
    OgdenCalibrationMember,
    OgdenCalibrationRole,
    OgdenDiagnosticPoint,
    OgdenTestMode,
    ReferenceOgdenCalibrationPlanContent,
    calibrate_reference_ogden,
)
from cmp.modules.modeling.domain.scientific_profile import OgdenScientificParameters
from cmp.modules.processing.domain.reference_tensile_crop import ProcessingRunStatus
from cmp.shared.domain.revisions import AggregateAlreadyExists, RevisionRecord, TenantScope
from fastapi import FastAPI, Request

NOW = datetime(2026, 7, 16, tzinfo=UTC)
IDS = tuple(UUID(int=index) for index in range(1, 24))
(
    ORG,
    PROJECT,
    ACTOR,
    PLAN,
    PLAN_REVISION,
    PROFILE,
    PROFILE_REVISION,
    STATE,
    STATE_REVISION,
    MODEL,
    MODEL_REVISION,
    DATASET,
    DATASET_REVISION,
    RUN,
    ATTEMPT,
    CANDIDATE,
    ARTIFACT,
) = IDS[:17]
TRACE = "00-000000000000000000000000000000c1-00000000000000c1-01"
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
MEMBER = OgdenCalibrationMember(
    0,
    OgdenCalibrationRole.CALIBRATION,
    OgdenTestMode.UNIAXIAL_TENSION,
    DATASET,
    DATASET_REVISION,
)
CONTENT = ReferenceOgdenCalibrationPlanContent(
    "Multi-test reference",
    PROFILE,
    PROFILE_REVISION,
    STATE,
    STATE_REVISION,
    MODEL,
    MODEL_REVISION,
    (MEMBER,),
)


def _record() -> RevisionRecord:
    return RevisionRecord(
        PLAN_REVISION,
        OGDEN_CALIBRATION_PLAN_AGGREGATE_TYPE,
        PLAN,
        TenantScope(ORG, PROJECT, "internal"),
        1,
        None,
        REFERENCE_OGDEN_CALIBRATION_PLAN_SCHEMA_ID,
        "1.0.0",
        "a" * 64,
        NOW,
        ACTOR,
        "create",
        CONTEXT.request_id,
        TRACE,
    )


def _candidate() -> PersistedOgdenCandidate:
    parameters = OgdenScientificParameters(
        2.0e6,
        1.0e5,
        1.0e7,
        1.0e6,
        2.0,
        0.5,
        8.0,
        1.0,
    )
    strain = (0.0, 0.05, 0.1, 0.2, 0.3)
    stress = tuple(2.0e6 * ((1 + item) - (1 + item) ** -2) for item in strain)
    value = calibrate_reference_ogden(
        parameters=parameters,
        multistart_count=1,
        seed=7,
        maximum_function_evaluations=5000,
        curves=(OgdenCalibrationCurve(MEMBER, strain, stress),),
    )[0]
    return PersistedOgdenCandidate(
        CANDIDATE,
        ATTEMPT,
        RUN,
        value,
        ARTIFACT,
        "d" * 64,
        len(value.diagnostics),
        NOW,
        ACTOR,
    )


def _family_candidate() -> PersistedHyperelasticFamilyCandidate:
    strain = (0.0, 0.05, 0.1, 0.2, 0.3)
    stress = tuple(2.0e6 * ((1 + item) - (1 + item) ** -2) for item in strain)
    value = fit_hyperelastic_families(
        (OgdenCalibrationCurve(MEMBER, strain, stress),),
        (HyperelasticFamily.NEO_HOOKEAN,),
        multistart_count=1,
        random_seed=7,
    )[0]
    return PersistedHyperelasticFamilyCandidate(IDS[17], RUN, value, NOW, ACTOR)


class _Service:
    def __init__(self) -> None:
        self.plan = OgdenCalibrationPlanSnapshot(
            PLAN, RevisionSnapshot(_record(), CONTENT)
        )
        self.run = OgdenCalibrationRun(
            RUN,
            DataClassification.INTERNAL,
            PLAN,
            PLAN_REVISION,
            PROFILE,
            PROFILE_REVISION,
            STATE,
            STATE_REVISION,
            MODEL,
            MODEL_REVISION,
            ProcessingRunStatus.SUCCEEDED,
            "sha256:" + "e" * 64,
            1,
            0,
            1,
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
            (_family_candidate(),),
        )

    def create_plan(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CreateReferenceOgdenCalibrationPlan,
    ) -> OgdenCalibrationPlanSnapshot:
        assert context is CONTEXT and decision is EXECUTE
        assert command.content.members[0].test_mode is OgdenTestMode.UNIAXIAL_TENSION
        return self.plan

    async def execute(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: ExecuteReferenceOgdenCalibration,
    ) -> OgdenCalibrationRun:
        assert context is CONTEXT and decision is EXECUTE
        assert command.plan_revision_id == PLAN_REVISION
        return self.run

    def get_run(
        self, context: SecurityContext, decision: AuthorizationDecision, run_id: UUID
    ) -> OgdenCalibrationRun:
        assert context is CONTEXT and decision is READ and run_id == RUN
        return self.run

    async def candidate_diagnostics(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        candidate_id: UUID,
    ) -> tuple[OgdenDiagnosticPoint, ...]:
        assert context is CONTEXT and decision is READ and candidate_id == CANDIDATE
        return self.run.candidates[0].value.diagnostics

    async def family_candidate_diagnostics(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        candidate_id: UUID,
    ) -> tuple[HyperelasticDiagnosticPoint, ...]:
        assert context is CONTEXT and decision is READ and candidate_id == IDS[17]
        return self.run.family_candidates[0].value.diagnostics


class _ConflictingService(_Service):
    def create_plan(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CreateReferenceOgdenCalibrationPlan,
    ) -> OgdenCalibrationPlanSnapshot:
        raise AggregateAlreadyExists(str(PLAN))


def _app(service_value: object | None = None) -> FastAPI:
    app = FastAPI()
    service = cast(ReferenceOgdenCalibrationService, service_value or _Service())

    async def security(request: Request) -> None:
        request.state.security_context = CONTEXT

    async def read(request: Request) -> None:
        request.state.authorization_decision = READ

    async def execute(request: Request) -> None:
        request.state.authorization_decision = EXECUTE

    install_ogden_calibration_api(
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
        created = await client.post(
            "/api/v1/ogden-calibration-plans",
            json={
                "classification": "internal",
                "plan_label": CONTENT.plan_label,
                "scientific_profile_id": str(PROFILE),
                "scientific_profile_revision_id": str(PROFILE_REVISION),
                "material_state_id": str(STATE),
                "material_state_revision_id": str(STATE_REVISION),
                "baseline_model_id": str(MODEL),
                "baseline_model_revision_id": str(MODEL_REVISION),
                "members": [
                    {
                        "role": "calibration",
                        "test_mode": "uniaxial_tension",
                        "dataset_id": str(DATASET),
                        "dataset_revision_id": str(DATASET_REVISION),
                    }
                ],
                "change_reason": "create exact multi-test Plan",
            },
        )
        assert created.status_code == 201
        assert created.json()["current_revision"]["content"]["non_production"] is True
        executed = await client.post(
            f"/api/v1/ogden-calibration-plans/{PLAN}/runs",
            json={"plan_revision_id": str(PLAN_REVISION), "change_reason": "execute"},
        )
        assert executed.status_code == 201
        candidate = executed.json()["candidates"][0]
        assert candidate["mu_pa"] == 2.0e6
        assert candidate["uncertainty_status"] == "estimated_jacobian_covariance"
        assert "no_holdout_data" in candidate["warnings"]
        assert executed.json()["family_candidate_count"] == 1
        family = executed.json()["family_candidates"][0]
        assert family["family"] == "neo_hookean"
        assert family["parameters"][0]["name"] == "c10_pa"
        family_diagnostics = await client.get(
            f"/api/v1/hyperelastic-family-candidates/{IDS[17]}/diagnostics"
        )
        assert family_diagnostics.status_code == 200
        assert family_diagnostics.json()["points"][1]["family"] == "neo_hookean"
        diagnostics = await client.get(
            f"/api/v1/ogden-calibration-candidates/{CANDIDATE}/diagnostics"
        )
        assert diagnostics.status_code == 200
        assert diagnostics.json()["points"][1]["test_mode"] == "uniaxial_tension"


def test_ogden_calibration_api_contract() -> None:
    asyncio.run(_request())


def test_duplicate_plan_label_is_an_actionable_conflict() -> None:
    async def request() -> None:
        transport = httpx.ASGITransport(app=_app(_ConflictingService()))
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/ogden-calibration-plans",
                json={
                    "classification": "internal",
                    "plan_label": CONTENT.plan_label,
                    "scientific_profile_id": str(PROFILE),
                    "scientific_profile_revision_id": str(PROFILE_REVISION),
                    "material_state_id": str(STATE),
                    "material_state_revision_id": str(STATE_REVISION),
                    "baseline_model_id": str(MODEL),
                    "baseline_model_revision_id": str(MODEL_REVISION),
                    "members": [
                        {
                            "role": "calibration",
                            "test_mode": "uniaxial_tension",
                            "dataset_id": str(DATASET),
                            "dataset_revision_id": str(DATASET_REVISION),
                        }
                    ],
                    "change_reason": "create exact multi-test Plan",
                },
            )
        assert response.status_code == 409
        assert "label already exists" in response.json()["detail"]

    asyncio.run(request())

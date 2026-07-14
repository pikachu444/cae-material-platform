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
from cmp.modules.statistics.adapters.api.replicate_statistics import (
    install_replicate_statistics_api,
)
from cmp.modules.statistics.application.replicate_service import (
    REPLICATE_STATISTICAL_PLAN_AGGREGATE_TYPE,
    REPLICATE_STATISTICAL_RESULT_AGGREGATE_TYPE,
    ReplicateRevisionSnapshot,
    ReplicateStatisticalPlanSnapshot,
    ReplicateStatisticalResultSnapshot,
    ReplicateStatisticalRun,
    ReplicateStatisticalRunMember,
    ReplicateStatisticsService,
)
from cmp.modules.statistics.domain.reference_tensile_pair import (
    QcObservation,
    QcOutcome,
    StatisticalRunStatus,
)
from cmp.modules.statistics.domain.reference_tensile_replicates import (
    ReferenceTensileReplicatePlanContent,
    ReferenceTensileReplicateResultContent,
    ReplicateCurvePoint,
    ReplicateScalarStatistics,
)
from cmp.shared.domain.revisions import RevisionRecord, TenantScope
from fastapi import FastAPI, Request

NOW = datetime(2026, 7, 30, 11, 0, tzinfo=UTC)
ORG = UUID(int=1)
PROJECT = UUID(int=2)
ACTOR = UUID(int=3)
PLAN = UUID(int=4)
PLAN_REVISION = UUID(int=5)
SELECTION = UUID(int=6)
SELECTION_REVISION = UUID(int=7)
RUN = UUID(int=8)
RESULT = UUID(int=9)
RESULT_REVISION = UUID(int=10)
CURVE_ARTIFACT = UUID(int=11)
TRACE = "00-00000000000000000000000000000034-0000000000000034-01"


def _context() -> SecurityContext:
    return SecurityContext(
        principal=Principal(ACTOR, PrincipalType.USER, "Statistical Analyst", True),
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
        roles=(Role.STATISTICAL_ANALYST,),
        database_permissions=database_permissions_for(permission),
        max_classification=DataClassification.INTERNAL,
        allow_export_controlled=False,
        request_id=CONTEXT.request_id,
        trace_id=TRACE,
        decided_at=NOW,
    )


READ = _decision(Permission.STATISTICS_READ)
EXECUTE = _decision(Permission.STATISTICS_EXECUTE)


def _record(revision_id: UUID, aggregate_id: UUID, aggregate_type: str) -> RevisionRecord:
    return RevisionRecord(
        revision_id=revision_id,
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        scope=TenantScope(ORG, PROJECT, "internal"),
        revision_no=1,
        based_on_revision_id=None,
        schema_id=f"urn:cmp:test:{aggregate_type}:1.0.0",
        schema_version="1.0.0",
        content_hash="b" * 64,
        created_at=NOW,
        created_by=ACTOR,
        change_reason="replicate Statistics API test",
        request_id=CONTEXT.request_id,
        trace_id=TRACE,
    )


PLAN_CONTENT = ReferenceTensileReplicatePlanContent(
    "DP780 replicate statistics", SELECTION, SELECTION_REVISION, 3
)
PLAN_SNAPSHOT = ReplicateStatisticalPlanSnapshot(
    PLAN,
    ReplicateRevisionSnapshot(
        _record(PLAN_REVISION, PLAN, REPLICATE_STATISTICAL_PLAN_AGGREGATE_TYPE),
        PLAN_CONTENT,
    ),
)
SCALAR = ReplicateScalarStatistics(
    sample_count=3,
    mean=520_000_000.0,
    sample_standard_deviation=20_000_000.0,
    median=520_000_000.0,
    median_absolute_deviation=20_000_000.0,
    interquartile_range=20_000_000.0,
    minimum=500_000_000.0,
    maximum=540_000_000.0,
    coefficient_of_variation=20_000_000.0 / 520_000_000.0,
    mean_confidence_interval_lower_95=470_316_674.0,
    mean_confidence_interval_upper_95=569_683_326.0,
)
RESULT_CONTENT = ReferenceTensileReplicateResultContent(
    RUN,
    PLAN,
    PLAN_REVISION,
    SELECTION,
    SELECTION_REVISION,
    CURVE_ARTIFACT,
    "c" * 64,
    31,
    SCALAR,
)
RESULT_SNAPSHOT = ReplicateStatisticalResultSnapshot(
    RESULT,
    ReplicateRevisionSnapshot(
        _record(RESULT_REVISION, RESULT, REPLICATE_STATISTICAL_RESULT_AGGREGATE_TYPE),
        RESULT_CONTENT,
    ),
)
MEMBERS = tuple(
    ReplicateStatisticalRunMember(
        ordinal=index,
        dataset_id=UUID(int=100 + index),
        dataset_revision_id=UUID(int=200 + index),
        test_run_id=UUID(int=300 + index),
        test_run_revision_id=UUID(int=400 + index),
    )
    for index in range(3)
)
RUN_VALUE = ReplicateStatisticalRun(
    id=RUN,
    classification=DataClassification.INTERNAL,
    plan_id=PLAN,
    plan_revision_id=PLAN_REVISION,
    selection_id=SELECTION,
    selection_revision_id=SELECTION_REVISION,
    status=StatisticalRunStatus.SUCCEEDED,
    sample_count=3,
    result_id=RESULT,
    result_revision_id=RESULT_REVISION,
    curve_artifact_id=CURVE_ARTIFACT,
    curve_sha256="c" * 64,
    curve_point_count=31,
    failure_code=None,
    change_reason="Calculate replicate statistics",
    started_at=NOW,
    ended_at=NOW,
    created_by=ACTOR,
    request_id=CONTEXT.request_id,
    trace_id=TRACE,
    members=MEMBERS,
    qc_observations=(
        QcObservation(
            "distinct_test_runs", QcOutcome.PASSED, "All Test Run revisions are distinct."
        ),
        QcObservation(
            "identical_observed_engineering_strain_grid",
            QcOutcome.PASSED,
            "All processed grids are exact.",
            31,
            31,
        ),
    ),
)


class _Service:
    def create_plan(self, context: object, decision: object, command: object) -> object:
        assert context is CONTEXT and decision is EXECUTE and command is not None
        return PLAN_SNAPSHOT

    def list_plans(
        self, context: object, decision: object, selection_revision_id: UUID, *, limit: int
    ) -> tuple[ReplicateStatisticalPlanSnapshot, ...]:
        assert context is CONTEXT and decision is READ
        assert selection_revision_id == SELECTION_REVISION and limit == 100
        return (PLAN_SNAPSHOT,)

    def get_plan(self, context: object, decision: object, plan_id: UUID) -> object:
        assert context is CONTEXT and decision is READ and plan_id == PLAN
        return PLAN_SNAPSHOT

    async def execute(self, context: object, decision: object, command: object) -> object:
        assert context is CONTEXT and decision is EXECUTE and command is not None
        return RUN_VALUE

    def get_run(self, context: object, decision: object, run_id: UUID) -> object:
        assert context is CONTEXT and decision is READ and run_id == RUN
        return RUN_VALUE

    def get_result(self, context: object, decision: object, result_id: UUID) -> object:
        assert context is CONTEXT and decision is READ and result_id == RESULT
        return RESULT_SNAPSHOT

    async def preview_result_curve(
        self,
        context: object,
        decision: object,
        result_id: UUID,
        *,
        maximum_points: int,
    ) -> tuple[ReplicateCurvePoint, ...]:
        assert context is CONTEXT and decision is READ and result_id == RESULT
        assert maximum_points == 1000
        return (
            ReplicateCurvePoint(0.0, SCALAR),
            ReplicateCurvePoint(0.03, SCALAR),
        )


def _application() -> FastAPI:
    application = FastAPI()

    def security(request: Request) -> None:
        request.state.security_context = CONTEXT

    def read(request: Request) -> None:
        request.state.authorization_decision = READ

    def execute(request: Request) -> None:
        request.state.authorization_decision = EXECUTE

    install_replicate_statistics_api(
        application,
        service=cast(ReplicateStatisticsService, _Service()),
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
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=application), base_url="http://test"
        ) as client:
            return await client.request(method, path, json=json)

    return asyncio.run(send())


def test_replicate_statistics_api_exposes_plan_run_result_and_pointwise_band() -> None:
    application = _application()
    created = _request(
        application,
        "POST",
        "/api/v1/replicate-statistical-plans",
        json={
            "classification": "internal",
            "plan_label": "DP780 replicate statistics",
            "selection_id": str(SELECTION),
            "selection_revision_id": str(SELECTION_REVISION),
            "sample_count": 3,
            "change_reason": "Pin aligned replicate Selection",
        },
    )
    assert created.status_code == 201
    assert created.json()["current_revision"]["content"]["sample_count"] == 3
    assert created.json()["current_revision"]["content"]["curve_grid_policy"] == (
        "exact_processed_grid_match_no_alignment"
    )

    run = _request(
        application,
        "POST",
        "/api/v1/replicate-statistical-runs",
        json={
            "plan_id": str(PLAN),
            "plan_revision_id": str(PLAN_REVISION),
            "change_reason": "Calculate replicate statistics",
        },
    )
    assert run.status_code == 201
    assert run.json()["status"] == "succeeded"
    assert len(run.json()["members"]) == 3
    assert run.json()["qc_observations"][1]["outcome"] == "passed"

    result = _request(application, "GET", f"/api/v1/replicate-statistical-results/{RESULT}")
    assert result.status_code == 200
    assert result.json()["peak_engineering_stress_pa"]["mean"] == 520_000_000.0
    assert result.json()["methods"]["confidence_interval"] == "student_t_95_two_sided"

    curve = _request(application, "GET", f"/api/v1/replicate-statistical-results/{RESULT}/curve")
    assert curve.status_code == 200
    assert curve.json()["points"][1]["statistics"]["sample_count"] == 3

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import cast
from uuid import UUID, uuid4

import httpx
from cmp.modules.datasets.domain.curve_metadata import (
    ArtifactPin,
    CurveMetadata,
    MetadataState,
    RevisionPin,
)
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
from cmp.modules.statistics.adapters.api.statistics import install_statistics_api
from cmp.modules.statistics.application.service import (
    STATISTICAL_PLAN_AGGREGATE_TYPE,
    STATISTICAL_RESULT_AGGREGATE_TYPE,
    CreateReferenceTensilePairPlan,
    ExecuteReferenceTensilePairStatistics,
    RevisionSnapshot,
    StatisticalCurvePreview,
    StatisticalPlanSnapshot,
    StatisticalResultSnapshot,
    StatisticalRun,
    StatisticsService,
)
from cmp.modules.statistics.domain.reference_tensile_pair import (
    REFERENCE_TENSILE_PAIR_CURVE_SCHEMA_V1,
    QcObservation,
    QcOutcome,
    ReferenceTensilePairCurvePoint,
    ReferenceTensilePairPlanContent,
    ReferenceTensilePairResultContent,
    ReferenceTensilePairScalarStatistics,
    StatisticalRunStatus,
    reference_tensile_pair_curve_series,
)
from cmp.shared.domain.revisions import RevisionRecord, TenantScope
from fastapi import FastAPI, Request

NOW = datetime(2026, 7, 16, 11, 0, tzinfo=UTC)
ORG = UUID("f7000000-0000-4000-8000-000000000001")
PROJECT = UUID("f7000000-0000-4000-8000-000000000002")
ACTOR = UUID("f7000000-0000-4000-8000-000000000003")
PLAN = UUID("f7000000-0000-4000-8000-000000000004")
PLAN_REVISION = UUID("f7000000-0000-4000-8000-000000000005")
FIRST_SELECTION = UUID("f7000000-0000-4000-8000-000000000006")
FIRST_SELECTION_REVISION = UUID("f7000000-0000-4000-8000-000000000007")
FIRST_DATASET = UUID("f7000000-0000-4000-8000-000000000008")
FIRST_DATASET_REVISION = UUID("f7000000-0000-4000-8000-000000000009")
SECOND_SELECTION = UUID("f7000000-0000-4000-8000-00000000000a")
SECOND_SELECTION_REVISION = UUID("f7000000-0000-4000-8000-00000000000b")
SECOND_DATASET = UUID("f7000000-0000-4000-8000-00000000000c")
SECOND_DATASET_REVISION = UUID("f7000000-0000-4000-8000-00000000000d")
RUN = UUID("f7000000-0000-4000-8000-00000000000e")
RESULT = UUID("f7000000-0000-4000-8000-00000000000f")
RESULT_REVISION = UUID("f7000000-0000-4000-8000-000000000010")
CURVE_ARTIFACT = UUID("f7000000-0000-4000-8000-000000000011")
TRACE = "00-000000000000000000000000000000f7-00000000000000f7-01"


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


def _record(*, revision_id: UUID, aggregate_id: UUID, aggregate_type: str) -> RevisionRecord:
    return RevisionRecord(
        revision_id=revision_id,
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        scope=TenantScope(ORG, PROJECT, DataClassification.INTERNAL.value),
        revision_no=1,
        based_on_revision_id=None,
        schema_id=f"urn:cmp:test:{aggregate_type}:1.0.0",
        schema_version="1.0.0",
        content_hash="f" * 64,
        created_at=NOW,
        created_by=ACTOR,
        change_reason="reference Statistics API test",
        request_id=CONTEXT.request_id,
        trace_id=TRACE,
    )


def _plan_content() -> ReferenceTensilePairPlanContent:
    return ReferenceTensilePairPlanContent(
        plan_label="Reference pair",
        first_selection_id=FIRST_SELECTION,
        first_selection_revision_id=FIRST_SELECTION_REVISION,
        second_selection_id=SECOND_SELECTION,
        second_selection_revision_id=SECOND_SELECTION_REVISION,
    )


def _plan() -> StatisticalPlanSnapshot:
    return StatisticalPlanSnapshot(
        id=PLAN,
        current=RevisionSnapshot(
            _record(
                revision_id=PLAN_REVISION,
                aggregate_id=PLAN,
                aggregate_type=STATISTICAL_PLAN_AGGREGATE_TYPE,
            ),
            _plan_content(),
        ),
    )


def _scalar() -> ReferenceTensilePairScalarStatistics:
    return ReferenceTensilePairScalarStatistics(
        first_peak_engineering_stress_pa=120_000_000.0,
        second_peak_engineering_stress_pa=140_000_000.0,
        mean_engineering_stress_pa=130_000_000.0,
        sample_standard_deviation_engineering_stress_pa=14_142_135.6237,
        median_engineering_stress_pa=130_000_000.0,
        median_absolute_deviation_engineering_stress_pa=10_000_000.0,
        interquartile_range_engineering_stress_pa=10_000_000.0,
        minimum_engineering_stress_pa=120_000_000.0,
        maximum_engineering_stress_pa=140_000_000.0,
        coefficient_of_variation=0.1087856586,
    )


def _result() -> StatisticalResultSnapshot:
    content = ReferenceTensilePairResultContent(
        statistical_run_id=RUN,
        plan_id=PLAN,
        plan_revision_id=PLAN_REVISION,
        first_selection_id=FIRST_SELECTION,
        first_selection_revision_id=FIRST_SELECTION_REVISION,
        first_dataset_id=FIRST_DATASET,
        first_dataset_revision_id=FIRST_DATASET_REVISION,
        second_selection_id=SECOND_SELECTION,
        second_selection_revision_id=SECOND_SELECTION_REVISION,
        second_dataset_id=SECOND_DATASET,
        second_dataset_revision_id=SECOND_DATASET_REVISION,
        curve_artifact_id=CURVE_ARTIFACT,
        curve_sha256="a" * 64,
        curve_point_count=3,
        scalar=_scalar(),
    )
    return StatisticalResultSnapshot(
        id=RESULT,
        current=RevisionSnapshot(
            _record(
                revision_id=RESULT_REVISION,
                aggregate_id=RESULT,
                aggregate_type=STATISTICAL_RESULT_AGGREGATE_TYPE,
            ),
            content,
        ),
    )


def _run() -> StatisticalRun:
    return StatisticalRun(
        id=RUN,
        classification=DataClassification.INTERNAL,
        plan_id=PLAN,
        plan_revision_id=PLAN_REVISION,
        first_selection_id=FIRST_SELECTION,
        first_selection_revision_id=FIRST_SELECTION_REVISION,
        first_dataset_id=FIRST_DATASET,
        first_dataset_revision_id=FIRST_DATASET_REVISION,
        second_selection_id=SECOND_SELECTION,
        second_selection_revision_id=SECOND_SELECTION_REVISION,
        second_dataset_id=SECOND_DATASET,
        second_dataset_revision_id=SECOND_DATASET_REVISION,
        status=StatisticalRunStatus.SUCCEEDED,
        sample_count=2,
        result_id=RESULT,
        result_revision_id=RESULT_REVISION,
        curve_artifact_id=CURVE_ARTIFACT,
        curve_sha256="a" * 64,
        curve_point_count=3,
        failure_code=None,
        change_reason="Commit reference pair statistics",
        started_at=NOW,
        ended_at=NOW,
        created_by=ACTOR,
        request_id=CONTEXT.request_id,
        trace_id=TRACE,
        qc_observations=(
            QcObservation(
                check_code="distinct_test_runs",
                outcome=QcOutcome.PASSED,
                detail="The two samples are backed by distinct Test Runs.",
            ),
            QcObservation(
                check_code="identical_observed_engineering_strain_grid",
                outcome=QcOutcome.PASSED,
                detail="Both normalized curves use the same observed engineering-strain grid.",
                expected_point_count=3,
                observed_point_count=3,
            ),
        ),
    )


class _StatisticsApiService:
    def create_reference_tensile_pair_plan(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CreateReferenceTensilePairPlan,
    ) -> StatisticalPlanSnapshot:
        assert context is CONTEXT
        assert decision is EXECUTE
        assert command.classification is DataClassification.INTERNAL
        assert command.content == _plan_content()
        return _plan()

    def list_plans(
        self, context: SecurityContext, decision: AuthorizationDecision, *, limit: int
    ) -> tuple[StatisticalPlanSnapshot, ...]:
        assert context is CONTEXT
        assert decision is READ
        assert limit == 100
        return (_plan(),)

    def get_plan(
        self, context: SecurityContext, decision: AuthorizationDecision, plan_id: UUID
    ) -> StatisticalPlanSnapshot:
        assert context is CONTEXT
        assert decision is READ
        assert plan_id == PLAN
        return _plan()

    async def execute_reference_tensile_pair_statistics(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: ExecuteReferenceTensilePairStatistics,
    ) -> StatisticalRun:
        assert context is CONTEXT
        assert decision is EXECUTE
        assert (command.plan_id, command.plan_revision_id) == (PLAN, PLAN_REVISION)
        return _run()

    def get_run(
        self, context: SecurityContext, decision: AuthorizationDecision, run_id: UUID
    ) -> StatisticalRun:
        assert context is CONTEXT
        assert decision is READ
        assert run_id == RUN
        return _run()

    def get_result(
        self, context: SecurityContext, decision: AuthorizationDecision, result_id: UUID
    ) -> StatisticalResultSnapshot:
        assert context is CONTEXT
        assert decision is READ
        assert result_id == RESULT
        return _result()

    async def preview_reference_tensile_pair_result_curve(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        result_id: UUID,
        *,
        maximum_points: int,
    ) -> StatisticalCurvePreview:
        assert context is CONTEXT
        assert decision is READ
        assert result_id == RESULT
        assert maximum_points == 1000
        points = (
            ReferenceTensilePairCurvePoint(0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
            ReferenceTensilePairCurvePoint(
                0.01, 105_000_000.0, 7_071_067.8119, 105_000_000.0, 100_000_000.0, 110_000_000.0
            ),
            ReferenceTensilePairCurvePoint(
                0.02, 130_000_000.0, 14_142_135.6237, 130_000_000.0, 120_000_000.0, 140_000_000.0
            ),
        )
        result = _result()
        series = reference_tensile_pair_curve_series(points)
        return StatisticalCurvePreview(
            result=result,
            points=points,
            metadata=CurveMetadata(
                state=MetadataState.LEGACY_COMPATIBLE,
                definition=series.definition,
                owning_revision=RevisionPin(
                    "statistical_result", RESULT, RESULT_REVISION
                ),
                artifact=ArtifactPin(
                    CURVE_ARTIFACT,
                    result.current.content.curve_sha256,
                    REFERENCE_TENSILE_PAIR_CURVE_SCHEMA_V1,
                    "application/vnd.apache.parquet",
                ),
            ),
            series=series.preview(maximum_points),
        )


def _application() -> FastAPI:
    application = FastAPI()

    def security(request: Request) -> None:
        request.state.security_context = CONTEXT

    def read(request: Request) -> None:
        request.state.authorization_decision = READ

    def execute(request: Request) -> None:
        request.state.authorization_decision = EXECUTE

    install_statistics_api(
        application,
        service=cast(StatisticsService, _StatisticsApiService()),
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


def test_reference_statistics_api_pins_inputs_reports_qc_and_exposes_typed_result_curve() -> None:
    application = _application()

    created = _request(
        application,
        "POST",
        "/api/v1/statistical-plans/reference-tensile-pair",
        json={
            "classification": "internal",
            "content": {
                "plan_label": "Reference pair",
                "first_selection_id": str(FIRST_SELECTION),
                "first_selection_revision_id": str(FIRST_SELECTION_REVISION),
                "second_selection_id": str(SECOND_SELECTION),
                "second_selection_revision_id": str(SECOND_SELECTION_REVISION),
            },
            "change_reason": "Pin two normalized curves",
        },
    )
    assert created.status_code == 201
    assert created.headers["Location"] == f"/api/v1/statistical-plans/{PLAN}"
    assert created.json()["current_revision"]["content"]["curve_grid_policy"] == (
        "exact_observed_grid_match_no_alignment"
    )
    assert created.json()["current_revision"]["content"]["confidence_interval_status"] == (
        "not_provided_reference_pair"
    )

    run = _request(
        application,
        "POST",
        "/api/v1/statistical-runs/reference-tensile-pair",
        json={
            "plan_id": str(PLAN),
            "plan_revision_id": str(PLAN_REVISION),
            "change_reason": "Commit reference pair statistics",
        },
    )
    assert run.status_code == 201
    assert run.json()["status"] == "succeeded"
    assert run.json()["sample_count"] == 2
    assert run.json()["qc_observations"][1]["outcome"] == "passed"
    assert run.json()["links"]["result"] == f"/api/v1/statistical-results/{RESULT}"

    result = _request(application, "GET", f"/api/v1/statistical-results/{RESULT}")
    assert result.status_code == 200
    assert (
        result.json()["current_revision"]["content"]["scalar"]["mean_engineering_stress_pa"]
        == 130_000_000.0
    )

    curve = _request(application, "GET", f"/api/v1/statistical-results/{RESULT}/curve")
    assert curve.status_code == 200
    assert curve.json()["points"][2]["maximum_engineering_stress_pa"] == 140_000_000.0

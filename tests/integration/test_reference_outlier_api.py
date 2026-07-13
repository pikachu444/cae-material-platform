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
from cmp.modules.statistics.adapters.api.statistics import install_statistics_api
from cmp.modules.statistics.application.service import (
    OUTLIER_ASSESSMENT_AGGREGATE_TYPE,
    OUTLIER_DETECTION_PLAN_AGGREGATE_TYPE,
    STATISTICAL_RESULT_AGGREGATE_TYPE,
    CreateReferenceTensilePairOutlierAssessment,
    CreateReferenceTensilePairOutlierDetectionPlan,
    ExecuteReferenceTensilePairOutlierDetection,
    OutlierAssessmentSnapshot,
    OutlierDetectionPlanSnapshot,
    OutlierDetectionRun,
    OutlierScopeComparison,
    OutlierScopeComparisonEntry,
    RevisionSnapshot,
    StatisticalResultSnapshot,
    StatisticsService,
)
from cmp.modules.statistics.domain.reference_tensile_outlier import (
    OutlierAssessmentDecision,
    OutlierCandidateStatus,
    OutlierDetectionRunStatus,
    ReferencePairPosition,
    ReferenceTensilePairOutlierAssessmentContent,
    ReferenceTensilePairOutlierCandidate,
    ReferenceTensilePairOutlierDetectionPlanContent,
)
from cmp.modules.statistics.domain.reference_tensile_pair import (
    ReferenceTensilePairResultContent,
    ReferenceTensilePairScalarStatistics,
)
from cmp.shared.domain.revisions import RevisionRecord, TenantScope
from fastapi import FastAPI, Request

NOW = datetime(2026, 7, 17, 10, 0, tzinfo=UTC)
ORG = UUID("fb000000-0000-4000-8000-000000000001")
PROJECT = UUID("fb000000-0000-4000-8000-000000000002")
ACTOR = UUID("fb000000-0000-4000-8000-000000000003")
RESULT = UUID("fb000000-0000-4000-8000-000000000004")
RESULT_REVISION = UUID("fb000000-0000-4000-8000-000000000005")
STATISTICAL_PLAN = UUID("fb000000-0000-4000-8000-000000000006")
STATISTICAL_PLAN_REVISION = UUID("fb000000-0000-4000-8000-000000000007")
DETECTION_PLAN = UUID("fb000000-0000-4000-8000-000000000008")
DETECTION_PLAN_REVISION = UUID("fb000000-0000-4000-8000-000000000009")
DETECTION_RUN = UUID("fb000000-0000-4000-8000-00000000000a")
FIRST_CANDIDATE = UUID("fb000000-0000-4000-8000-00000000000b")
SECOND_CANDIDATE = UUID("fb000000-0000-4000-8000-00000000000c")
ASSESSMENT = UUID("fb000000-0000-4000-8000-00000000000d")
ASSESSMENT_REVISION = UUID("fb000000-0000-4000-8000-00000000000e")
TRACE = "00-000000000000000000000000000000fb-00000000000000fb-01"


def _context() -> SecurityContext:
    return SecurityContext(
        principal=Principal(ACTOR, PrincipalType.USER, "Statistical analyst", True),
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
        content_hash="c" * 64,
        created_at=NOW,
        created_by=ACTOR,
        change_reason="reference outlier API test",
        request_id=CONTEXT.request_id,
        trace_id=TRACE,
    )


def _result() -> StatisticalResultSnapshot:
    return StatisticalResultSnapshot(
        id=RESULT,
        current=RevisionSnapshot(
            _record(
                revision_id=RESULT_REVISION,
                aggregate_id=RESULT,
                aggregate_type=STATISTICAL_RESULT_AGGREGATE_TYPE,
            ),
            ReferenceTensilePairResultContent(
                statistical_run_id=UUID("fb000000-0000-4000-8000-00000000000f"),
                plan_id=STATISTICAL_PLAN,
                plan_revision_id=STATISTICAL_PLAN_REVISION,
                first_selection_id=UUID("fb000000-0000-4000-8000-000000000010"),
                first_selection_revision_id=UUID("fb000000-0000-4000-8000-000000000011"),
                first_dataset_id=UUID("fb000000-0000-4000-8000-000000000012"),
                first_dataset_revision_id=UUID("fb000000-0000-4000-8000-000000000013"),
                second_selection_id=UUID("fb000000-0000-4000-8000-000000000014"),
                second_selection_revision_id=UUID("fb000000-0000-4000-8000-000000000015"),
                second_dataset_id=UUID("fb000000-0000-4000-8000-000000000016"),
                second_dataset_revision_id=UUID("fb000000-0000-4000-8000-000000000017"),
                curve_artifact_id=UUID("fb000000-0000-4000-8000-000000000018"),
                curve_sha256="a" * 64,
                curve_point_count=3,
                scalar=ReferenceTensilePairScalarStatistics(
                    first_peak_engineering_stress_pa=120_000_000.0,
                    second_peak_engineering_stress_pa=150_000_000.0,
                    mean_engineering_stress_pa=135_000_000.0,
                    sample_standard_deviation_engineering_stress_pa=1.0,
                    median_engineering_stress_pa=135_000_000.0,
                    median_absolute_deviation_engineering_stress_pa=1.0,
                    interquartile_range_engineering_stress_pa=1.0,
                    minimum_engineering_stress_pa=120_000_000.0,
                    maximum_engineering_stress_pa=150_000_000.0,
                    coefficient_of_variation=0.01,
                ),
            ),
        ),
    )


def _detection_plan() -> OutlierDetectionPlanSnapshot:
    return OutlierDetectionPlanSnapshot(
        id=DETECTION_PLAN,
        current=RevisionSnapshot(
            _record(
                revision_id=DETECTION_PLAN_REVISION,
                aggregate_id=DETECTION_PLAN,
                aggregate_type=OUTLIER_DETECTION_PLAN_AGGREGATE_TYPE,
            ),
            ReferenceTensilePairOutlierDetectionPlanContent(
                plan_label="Review reference pair difference",
                statistical_result_id=RESULT,
                statistical_result_revision_id=RESULT_REVISION,
                relative_peak_difference_threshold=0.2,
            ),
        ),
    )


def _candidate(
    candidate_id: UUID,
    position: ReferencePairPosition,
) -> ReferenceTensilePairOutlierCandidate:
    result = _result().current.content
    first = position is ReferencePairPosition.FIRST
    return ReferenceTensilePairOutlierCandidate(
        id=candidate_id,
        detection_run_id=DETECTION_RUN,
        detection_plan_id=DETECTION_PLAN,
        detection_plan_revision_id=DETECTION_PLAN_REVISION,
        statistical_result_id=RESULT,
        statistical_result_revision_id=RESULT_REVISION,
        statistical_plan_id=STATISTICAL_PLAN,
        statistical_plan_revision_id=STATISTICAL_PLAN_REVISION,
        selection_id=result.first_selection_id if first else result.second_selection_id,
        selection_revision_id=(
            result.first_selection_revision_id if first else result.second_selection_revision_id
        ),
        dataset_id=result.first_dataset_id if first else result.second_dataset_id,
        dataset_revision_id=(
            result.first_dataset_revision_id if first else result.second_dataset_revision_id
        ),
        pair_position=position,
        peak_engineering_stress_pa=(
            result.scalar.first_peak_engineering_stress_pa
            if first
            else result.scalar.second_peak_engineering_stress_pa
        ),
        peer_peak_engineering_stress_pa=(
            result.scalar.second_peak_engineering_stress_pa
            if first
            else result.scalar.first_peak_engineering_stress_pa
        ),
        relative_peak_difference=0.2,
        relative_peak_difference_threshold=0.2,
        status=OutlierCandidateStatus.REVIEW_REQUIRED,
    )


def _assessment() -> OutlierAssessmentSnapshot:
    return OutlierAssessmentSnapshot(
        id=ASSESSMENT,
        current=RevisionSnapshot(
            _record(
                revision_id=ASSESSMENT_REVISION,
                aggregate_id=ASSESSMENT,
                aggregate_type=OUTLIER_ASSESSMENT_AGGREGATE_TYPE,
            ),
            ReferenceTensilePairOutlierAssessmentContent(
                candidate_id=FIRST_CANDIDATE,
                statistical_plan_id=STATISTICAL_PLAN,
                statistical_plan_revision_id=STATISTICAL_PLAN_REVISION,
                decision=OutlierAssessmentDecision.RETAINED,
                assessment_reason="Human review retains this curve for the reference analysis.",
            ),
        ),
    )


class _OutlierApiService:
    def create_reference_tensile_pair_outlier_detection_plan(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CreateReferenceTensilePairOutlierDetectionPlan,
    ) -> OutlierDetectionPlanSnapshot:
        assert context is CONTEXT
        assert decision is EXECUTE
        assert command.content.statistical_result_revision_id == RESULT_REVISION
        return _detection_plan()

    def execute_reference_tensile_pair_outlier_detection(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: ExecuteReferenceTensilePairOutlierDetection,
    ) -> OutlierDetectionRun:
        assert context is CONTEXT
        assert decision is EXECUTE
        assert (command.detection_plan_id, command.detection_plan_revision_id) == (
            DETECTION_PLAN,
            DETECTION_PLAN_REVISION,
        )
        candidates = (
            _candidate(FIRST_CANDIDATE, ReferencePairPosition.FIRST),
            _candidate(SECOND_CANDIDATE, ReferencePairPosition.SECOND),
        )
        return OutlierDetectionRun(
            id=DETECTION_RUN,
            classification=DataClassification.INTERNAL,
            detection_plan_id=DETECTION_PLAN,
            detection_plan_revision_id=DETECTION_PLAN_REVISION,
            statistical_result_id=RESULT,
            statistical_result_revision_id=RESULT_REVISION,
            status=OutlierDetectionRunStatus.SUCCEEDED,
            candidate_count=2,
            failure_code=None,
            change_reason=command.change_reason,
            started_at=NOW,
            ended_at=NOW,
            created_by=ACTOR,
            request_id=CONTEXT.request_id,
            trace_id=TRACE,
            candidates=candidates,
        )

    def create_reference_tensile_pair_outlier_assessment(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CreateReferenceTensilePairOutlierAssessment,
    ) -> OutlierAssessmentSnapshot:
        assert context is CONTEXT
        assert decision is EXECUTE
        assert command.content.candidate_id == FIRST_CANDIDATE
        assert command.content.decision is OutlierAssessmentDecision.RETAINED
        return _assessment()

    def get_reference_tensile_pair_outlier_scope_comparison(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        *,
        detection_plan_id: UUID,
        detection_plan_revision_id: UUID,
    ) -> OutlierScopeComparison:
        assert context is CONTEXT
        assert decision is READ
        assert (detection_plan_id, detection_plan_revision_id) == (
            DETECTION_PLAN,
            DETECTION_PLAN_REVISION,
        )
        first = _candidate(FIRST_CANDIDATE, ReferencePairPosition.FIRST)
        second = _candidate(SECOND_CANDIDATE, ReferencePairPosition.SECOND)
        return OutlierScopeComparison(
            detection_plan=_detection_plan(),
            statistical_result=_result(),
            entries=(
                OutlierScopeComparisonEntry(first, (_assessment(),), _assessment()),
                OutlierScopeComparisonEntry(second, (), None),
            ),
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
        service=cast(StatisticsService, _OutlierApiService()),
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


def test_reference_outlier_api_keeps_candidates_and_human_scope_decisions_separate() -> None:
    application = _application()
    created = _request(
        application,
        "POST",
        "/api/v1/outlier-detection-plans/reference-tensile-pair",
        json={
            "classification": "internal",
            "content": {
                "plan_label": "Review reference pair difference",
                "statistical_result_id": str(RESULT),
                "statistical_result_revision_id": str(RESULT_REVISION),
                "relative_peak_difference_threshold": 0.2,
            },
            "change_reason": "Pin a declared review threshold",
        },
    )
    assert created.status_code == 201
    assert created.headers["Location"] == f"/api/v1/outlier-detection-plans/{DETECTION_PLAN}"
    assert created.json()["current_revision"]["content"]["automatic_exclusion"] is False

    run = _request(
        application,
        "POST",
        "/api/v1/outlier-detection-runs/reference-tensile-pair",
        json={
            "detection_plan_id": str(DETECTION_PLAN),
            "detection_plan_revision_id": str(DETECTION_PLAN_REVISION),
            "change_reason": "Generate review candidates",
        },
    )
    assert run.status_code == 201
    assert run.json()["candidate_count"] == 2
    assert {item["status"] for item in run.json()["candidates"]} == {"review_required"}

    assessment = _request(
        application,
        "POST",
        "/api/v1/outlier-assessments/reference-tensile-pair",
        json={
            "classification": "internal",
            "content": {
                "candidate_id": str(FIRST_CANDIDATE),
                "statistical_plan_id": str(STATISTICAL_PLAN),
                "statistical_plan_revision_id": str(STATISTICAL_PLAN_REVISION),
                "decision": "retained",
                "assessment_reason": "Human review retains this curve.",
            },
            "change_reason": "Record outlier review",
        },
    )
    assert assessment.status_code == 201
    assert assessment.json()["current_revision"]["content"]["scope_kind"] == (
        "reference_pair_analysis"
    )

    comparison = _request(
        application,
        "GET",
        "/api/v1/outlier-scope-comparisons/reference-tensile-pair"
        f"?detection_plan_id={DETECTION_PLAN}"
        f"&detection_plan_revision_id={DETECTION_PLAN_REVISION}",
    )
    assert comparison.status_code == 200
    assert comparison.json()["source_mutation"] is False
    assert comparison.json()["derived_selection_created"] is False
    assert comparison.json()["entries"][0]["assessment_history"][0]["current_revision"][
        "content"
    ]["decision"] == "retained"


def test_reference_outlier_api_rejects_an_automatic_or_zero_threshold() -> None:
    response = _request(
        _application(),
        "POST",
        "/api/v1/outlier-detection-plans/reference-tensile-pair",
        json={
            "classification": "internal",
            "content": {
                "plan_label": "Invalid threshold",
                "statistical_result_id": str(RESULT),
                "statistical_result_revision_id": str(RESULT_REVISION),
                "relative_peak_difference_threshold": 0.0,
            },
            "change_reason": "Attempt an invalid automatic threshold",
        },
    )

    assert response.status_code == 422

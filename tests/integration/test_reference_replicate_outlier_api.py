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
from cmp.modules.statistics.adapters.api.replicate_outliers import install_replicate_outlier_api
from cmp.modules.statistics.application.replicate_outlier_service import (
    CALIBRATION_INPUT_SCOPE_AGGREGATE_TYPE,
    OUTLIER_ASSESSMENT_AGGREGATE_TYPE,
    OUTLIER_PLAN_AGGREGATE_TYPE,
    CalibrationInputScopeSnapshot,
    ReplicateOutlierAssessmentSnapshot,
    ReplicateOutlierDetectionRun,
    ReplicateOutlierPlanSnapshot,
    ReplicateOutlierService,
)
from cmp.modules.statistics.application.replicate_service import ReplicateRevisionSnapshot
from cmp.modules.statistics.domain.reference_tensile_replicate_outlier import (
    CalibrationInputScopeMember,
    CalibrationScopeDisposition,
    ReferenceCalibrationInputScopeContent,
    ReferenceReplicateOutlierAssessmentContent,
    ReferenceReplicateOutlierCandidate,
    ReferenceReplicateOutlierPlanContent,
    ReplicateOutlierAssessmentDecision,
    ReplicateOutlierEvidenceCode,
    ReplicateOutlierMemberEvidence,
)
from cmp.shared.domain.revisions import RevisionRecord, TenantScope
from fastapi import FastAPI, Request

NOW = datetime(2026, 7, 31, 12, 0, tzinfo=UTC)
ORG, PROJECT, ACTOR = UUID(int=1), UUID(int=2), UUID(int=3)
PLAN, PLAN_REVISION, RUN = UUID(int=4), UUID(int=5), UUID(int=6)
RESULT, RESULT_REVISION = UUID(int=7), UUID(int=8)
CANDIDATE = UUID(int=9)
ASSESSMENT, ASSESSMENT_REVISION = UUID(int=10), UUID(int=11)
SCOPE, SCOPE_REVISION = UUID(int=12), UUID(int=13)
SELECTION, SELECTION_REVISION = UUID(int=14), UUID(int=15)
STAT_PLAN, STAT_PLAN_REVISION = UUID(int=16), UUID(int=17)
TRACE = "00-00000000000000000000000000000035-0000000000000035-01"


def _context() -> SecurityContext:
    return SecurityContext(
        Principal(ACTOR, PrincipalType.USER, "Statistical Analyst", True),
        ORG,
        PROJECT,
        "https://test.invalid",
        str(ACTOR),
        str(uuid4()),
        (),
        ("openid",),
        uuid4(),
        TRACE,
        NOW,
    )


CONTEXT = _context()


def _decision(permission: Permission) -> AuthorizationDecision:
    return AuthorizationDecision(
        ACTOR,
        ORG,
        PROJECT,
        permission,
        (Role.STATISTICAL_ANALYST,),
        database_permissions_for(permission),
        DataClassification.INTERNAL,
        False,
        CONTEXT.request_id,
        TRACE,
        NOW,
    )


READ = _decision(Permission.STATISTICS_READ)
EXECUTE = _decision(Permission.STATISTICS_EXECUTE)


def _record(revision_id: UUID, aggregate_id: UUID, aggregate_type: str) -> RevisionRecord:
    return RevisionRecord(
        revision_id,
        aggregate_type,
        aggregate_id,
        TenantScope(ORG, PROJECT, "internal"),
        1,
        None,
        f"urn:cmp:test:{aggregate_type}:1.0.0",
        "1.0.0",
        "a" * 64,
        NOW,
        ACTOR,
        "integration test",
        CONTEXT.request_id,
        TRACE,
    )


PLAN_CONTENT = ReferenceReplicateOutlierPlanContent(
    "Replicate peak review", RESULT, RESULT_REVISION, 3.5
)
PLAN_VALUE = ReplicateOutlierPlanSnapshot(
    PLAN,
    ReplicateRevisionSnapshot(
        _record(PLAN_REVISION, PLAN, OUTLIER_PLAN_AGGREGATE_TYPE), PLAN_CONTENT
    ),
)
MEMBERS = tuple(
    ReplicateOutlierMemberEvidence(
        index,
        UUID(int=100 + index),
        UUID(int=200 + index),
        UUID(int=300 + index),
        UUID(int=400 + index),
        (600_000_000.0, 610_000_000.0, 900_000_000.0)[index],
    )
    for index in range(3)
)
CANDIDATE_VALUE = ReferenceReplicateOutlierCandidate(
    CANDIDATE,
    RUN,
    PLAN,
    PLAN_REVISION,
    RESULT,
    RESULT_REVISION,
    STAT_PLAN,
    STAT_PLAN_REVISION,
    SELECTION,
    SELECTION_REVISION,
    MEMBERS[2],
    3,
    610_000_000.0,
    10_000_000.0,
    19.56020275568637,
    3.5,
    ReplicateOutlierEvidenceCode.MODIFIED_Z_THRESHOLD_EXCEEDED,
)
RUN_VALUE = ReplicateOutlierDetectionRun(
    RUN,
    DataClassification.INTERNAL,
    PLAN,
    PLAN_REVISION,
    RESULT,
    RESULT_REVISION,
    STAT_PLAN,
    STAT_PLAN_REVISION,
    SELECTION,
    SELECTION_REVISION,
    3,
    610_000_000.0,
    10_000_000.0,
    1,
    NOW,
    NOW,
    ACTOR,
    CONTEXT.request_id,
    TRACE,
    (CANDIDATE_VALUE,),
)
ASSESSMENT_CONTENT = ReferenceReplicateOutlierAssessmentContent(
    CANDIDATE,
    PLAN,
    PLAN_REVISION,
    ReplicateOutlierAssessmentDecision.EXCLUDED_FROM_CALIBRATION,
    "Confirmed specimen handling anomaly",
)
ASSESSMENT_VALUE = ReplicateOutlierAssessmentSnapshot(
    ASSESSMENT,
    ReplicateRevisionSnapshot(
        _record(ASSESSMENT_REVISION, ASSESSMENT, OUTLIER_ASSESSMENT_AGGREGATE_TYPE),
        ASSESSMENT_CONTENT,
    ),
)
SCOPE_CONTENT = ReferenceCalibrationInputScopeContent(
    "Reviewed calibration inputs",
    SELECTION,
    SELECTION_REVISION,
    RESULT,
    RESULT_REVISION,
    PLAN,
    PLAN_REVISION,
    tuple(
        CalibrationInputScopeMember(
            index,
            member.dataset_id,
            member.dataset_revision_id,
            member.test_run_id,
            member.test_run_revision_id,
            (
                CalibrationScopeDisposition.EXCLUDED
                if index == 2
                else CalibrationScopeDisposition.INCLUDED
            ),
            CANDIDATE if index == 2 else None,
            ASSESSMENT if index == 2 else None,
            ASSESSMENT_REVISION if index == 2 else None,
        )
        for index, member in enumerate(MEMBERS)
    ),
)
SCOPE_VALUE = CalibrationInputScopeSnapshot(
    SCOPE,
    ReplicateRevisionSnapshot(
        _record(SCOPE_REVISION, SCOPE, CALIBRATION_INPUT_SCOPE_AGGREGATE_TYPE),
        SCOPE_CONTENT,
    ),
)


class _Service:
    def create_plan(self, context: object, decision: object, command: object) -> object:
        assert context is CONTEXT and decision is EXECUTE and command is not None
        return PLAN_VALUE

    def list_plans(self, context: object, decision: object, result_revision: UUID) -> object:
        assert context is CONTEXT and decision is READ and result_revision == RESULT_REVISION
        return (PLAN_VALUE,)

    async def execute(self, context: object, decision: object, command: object) -> object:
        assert context is CONTEXT and decision is EXECUTE and command is not None
        return RUN_VALUE

    def get_detection_run(self, context: object, decision: object, run_id: UUID) -> object:
        assert context is CONTEXT and decision is READ and run_id == RUN
        return RUN_VALUE

    def create_assessment(self, context: object, decision: object, command: object) -> object:
        assert context is CONTEXT and decision is EXECUTE and command is not None
        return ASSESSMENT_VALUE

    def list_assessments(self, context: object, decision: object, candidate_id: UUID) -> object:
        assert context is CONTEXT and decision is READ and candidate_id == CANDIDATE
        return (ASSESSMENT_VALUE,)

    def create_scope(self, context: object, decision: object, command: object) -> object:
        assert context is CONTEXT and decision is EXECUTE and command is not None
        return SCOPE_VALUE

    def get_scope(self, context: object, decision: object, scope_id: UUID) -> object:
        assert context is CONTEXT and decision is READ and scope_id == SCOPE
        return SCOPE_VALUE

    def list_scopes(self, context: object, decision: object, result_revision: UUID) -> object:
        assert context is CONTEXT and decision is READ and result_revision == RESULT_REVISION
        return (SCOPE_VALUE,)


def _application() -> FastAPI:
    app = FastAPI()

    def security(request: Request) -> None:
        request.state.security_context = CONTEXT

    def read(request: Request) -> None:
        request.state.authorization_decision = READ

    def execute(request: Request) -> None:
        request.state.authorization_decision = EXECUTE

    install_replicate_outlier_api(
        app,
        service=cast(ReplicateOutlierService, _Service()),
        security_dependency=security,
        read_dependency=read,
        execute_dependency=execute,
    )
    return app


def _request(method: str, path: str, json: dict[str, object] | None = None) -> httpx.Response:
    async def send() -> httpx.Response:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=_application()), base_url="http://test"
        ) as client:
            return await client.request(method, path, json=json)

    return asyncio.run(send())


def test_review_evidence_assessment_and_scope_are_separate_http_resources() -> None:
    plan = _request(
        "POST",
        "/api/v1/replicate-outlier-detection-plans",
        {
            "classification": "internal",
            "plan_label": "Replicate peak review",
            "statistical_result_id": str(RESULT),
            "statistical_result_revision_id": str(RESULT_REVISION),
            "absolute_modified_z_threshold": 3.5,
            "change_reason": "Create evidence Plan",
        },
    )
    assert plan.status_code == 201
    assert plan.json()["content"]["automatic_exclusion"] is False

    run = _request(
        "POST",
        "/api/v1/replicate-outlier-detection-runs",
        {"detection_plan_id": str(PLAN), "detection_plan_revision_id": str(PLAN_REVISION)},
    )
    assert run.status_code == 201
    assert run.json()["candidates"][0]["review_status"] == "review_required"

    assessment = _request(
        "POST",
        "/api/v1/replicate-outlier-assessments",
        {
            "classification": "internal",
            "candidate_id": str(CANDIDATE),
            "detection_plan_id": str(PLAN),
            "detection_plan_revision_id": str(PLAN_REVISION),
            "decision": "excluded_from_calibration",
            "assessment_reason": "Confirmed specimen handling anomaly",
            "change_reason": "Record human decision",
        },
    )
    assert assessment.status_code == 201
    assert assessment.json()["automatic_exclusion"] is False

    scope = _request(
        "POST",
        "/api/v1/reference-calibration-input-scopes",
        {
            "classification": "internal",
            "scope_label": "Reviewed calibration inputs",
            "detection_run_id": str(RUN),
            "assessment_revision_ids": [str(ASSESSMENT_REVISION)],
            "change_reason": "Pin exact reviewed members",
        },
    )
    assert scope.status_code == 201
    assert scope.json()["included_member_count"] == 2
    assert scope.json()["excluded_member_count"] == 1
    assert scope.json()["members"][2]["assessment_revision_id"] == str(ASSESSMENT_REVISION)

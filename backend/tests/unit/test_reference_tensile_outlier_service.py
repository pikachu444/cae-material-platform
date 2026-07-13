from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import cast
from uuid import UUID, uuid4

import pytest
from cmp.modules.artifacts.application.content import ArtifactService
from cmp.modules.datasets.application.service import DatasetService
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
from cmp.modules.statistics.application.service import (
    STATISTICAL_PLAN_AGGREGATE_TYPE,
    STATISTICAL_RESULT_AGGREGATE_TYPE,
    CreateReferenceTensilePairOutlierAssessment,
    CreateReferenceTensilePairOutlierDetectionPlan,
    ExecuteReferenceTensilePairOutlierDetection,
    OutlierAssessmentSnapshot,
    OutlierDetectionPlanSnapshot,
    OutlierDetectionRun,
    RevisionSnapshot,
    StatisticalResultSnapshot,
    StatisticsRepository,
    StatisticsService,
)
from cmp.modules.statistics.domain.reference_tensile_outlier import (
    OutlierAssessmentDecision,
    OutlierDetectionRunStatus,
    ReferenceTensilePairOutlierAssessmentContent,
    ReferenceTensilePairOutlierCandidate,
    ReferenceTensilePairOutlierDetectionPlanContent,
)
from cmp.modules.statistics.domain.reference_tensile_pair import (
    ReferenceTensilePairPlanContent,
    ReferenceTensilePairResultContent,
    ReferenceTensilePairScalarStatistics,
    StatisticsConflict,
)
from cmp.shared.application.revisions import RevisionStore
from cmp.shared.domain.revisions import (
    AggregateAlreadyExists,
    AggregateNotFound,
    RevisionConflict,
    RevisionCreated,
    RevisionDraft,
    RevisionRecord,
    TenantScope,
)

NOW = datetime(2026, 7, 17, 9, 0, tzinfo=UTC)
ORG = UUID("fa000000-0000-4000-8000-000000000001")
PROJECT = UUID("fa000000-0000-4000-8000-000000000002")
ACTOR = UUID("fa000000-0000-4000-8000-000000000003")
STATISTICAL_PLAN = UUID("fa000000-0000-4000-8000-000000000004")
STATISTICAL_PLAN_REVISION = UUID("fa000000-0000-4000-8000-000000000005")
RESULT = UUID("fa000000-0000-4000-8000-000000000006")
RESULT_REVISION = UUID("fa000000-0000-4000-8000-000000000007")
FIRST_SELECTION = UUID("fa000000-0000-4000-8000-000000000008")
FIRST_SELECTION_REVISION = UUID("fa000000-0000-4000-8000-000000000009")
SECOND_SELECTION = UUID("fa000000-0000-4000-8000-00000000000a")
SECOND_SELECTION_REVISION = UUID("fa000000-0000-4000-8000-00000000000b")
FIRST_DATASET = UUID("fa000000-0000-4000-8000-00000000000c")
FIRST_DATASET_REVISION = UUID("fa000000-0000-4000-8000-00000000000d")
SECOND_DATASET = UUID("fa000000-0000-4000-8000-00000000000e")
SECOND_DATASET_REVISION = UUID("fa000000-0000-4000-8000-00000000000f")
DETECTION_PLAN = UUID("fa000000-0000-4000-8000-000000000010")
DETECTION_RUN = UUID("fa000000-0000-4000-8000-000000000011")
FIRST_CANDIDATE = UUID("fa000000-0000-4000-8000-000000000012")
SECOND_CANDIDATE = UUID("fa000000-0000-4000-8000-000000000013")
FIRST_ASSESSMENT = UUID("fa000000-0000-4000-8000-000000000014")
SECOND_ASSESSMENT = UUID("fa000000-0000-4000-8000-000000000015")
TRACE = "00-000000000000000000000000000000fa-00000000000000fa-01"


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


def _record(
    *, revision_id: UUID, aggregate_id: UUID, aggregate_type: str, revision_no: int = 1
) -> RevisionRecord:
    return RevisionRecord(
        revision_id=revision_id,
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        scope=TenantScope(ORG, PROJECT, DataClassification.INTERNAL.value),
        revision_no=revision_no,
        based_on_revision_id=None,
        schema_id=f"urn:cmp:test:{aggregate_type}:1.0.0",
        schema_version="1.0.0",
        content_hash="a" * 64,
        created_at=NOW,
        created_by=ACTOR,
        change_reason="reference outlier service test",
        request_id=CONTEXT.request_id,
        trace_id=TRACE,
    )


def _statistical_plan() -> RevisionSnapshot[ReferenceTensilePairPlanContent]:
    return RevisionSnapshot(
        _record(
            revision_id=STATISTICAL_PLAN_REVISION,
            aggregate_id=STATISTICAL_PLAN,
            aggregate_type=STATISTICAL_PLAN_AGGREGATE_TYPE,
        ),
        ReferenceTensilePairPlanContent(
            plan_label="Reference tensile pair",
            first_selection_id=FIRST_SELECTION,
            first_selection_revision_id=FIRST_SELECTION_REVISION,
            second_selection_id=SECOND_SELECTION,
            second_selection_revision_id=SECOND_SELECTION_REVISION,
        ),
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
                statistical_run_id=UUID("fa000000-0000-4000-8000-000000000016"),
                plan_id=STATISTICAL_PLAN,
                plan_revision_id=STATISTICAL_PLAN_REVISION,
                first_selection_id=FIRST_SELECTION,
                first_selection_revision_id=FIRST_SELECTION_REVISION,
                first_dataset_id=FIRST_DATASET,
                first_dataset_revision_id=FIRST_DATASET_REVISION,
                second_selection_id=SECOND_SELECTION,
                second_selection_revision_id=SECOND_SELECTION_REVISION,
                second_dataset_id=SECOND_DATASET,
                second_dataset_revision_id=SECOND_DATASET_REVISION,
                curve_artifact_id=UUID("fa000000-0000-4000-8000-000000000017"),
                curve_sha256="b" * 64,
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


@dataclass
class _StoreState:
    heads: dict[UUID, UUID]
    records: dict[UUID, RevisionRecord]
    contents: dict[UUID, object]


class _Transaction:
    def __init__(self, state: _StoreState) -> None:
        self._state = state

    @staticmethod
    def _record(
        draft: RevisionDraft[object], revision_no: int, based_on: UUID | None
    ) -> RevisionRecord:
        return RevisionRecord(
            revision_id=draft.revision_id,
            aggregate_type=draft.aggregate_type,
            aggregate_id=draft.aggregate_id,
            scope=draft.scope,
            revision_no=revision_no,
            based_on_revision_id=based_on,
            schema_id=draft.schema_id,
            schema_version=draft.schema_version,
            content_hash=draft.content_hash,
            created_at=draft.created_at,
            created_by=draft.created_by,
            change_reason=draft.change_reason,
            request_id=draft.request_id,
            trace_id=draft.trace_id,
        )

    def create(self, draft: RevisionDraft[object]) -> RevisionRecord:
        if draft.aggregate_id in self._state.heads:
            raise AggregateAlreadyExists(str(draft.aggregate_id))
        record = self._record(draft, 1, None)
        self._state.heads[draft.aggregate_id] = record.revision_id
        self._state.records[record.revision_id] = record
        self._state.contents[record.revision_id] = draft.content
        return record

    def revise(
        self, draft: RevisionDraft[object], expected_current_revision_id: UUID
    ) -> RevisionRecord:
        current_id = self._state.heads.get(draft.aggregate_id)
        if current_id is None:
            raise AggregateNotFound(str(draft.aggregate_id))
        if current_id != expected_current_revision_id:
            raise RevisionConflict(
                expected_current_revision_id,
                self._state.records[current_id].ref,
            )
        current = self._state.records[current_id]
        record = self._record(draft, current.revision_no + 1, current_id)
        self._state.heads[draft.aggregate_id] = record.revision_id
        self._state.records[record.revision_id] = record
        self._state.contents[record.revision_id] = draft.content
        return record

    def stage(self, event: RevisionCreated) -> None:
        del event


class _Store:
    def __init__(self) -> None:
        self.state = _StoreState({}, {}, {})

    def canonical_content(self, content: object) -> object:
        return {"typed_content": repr(content)}

    @contextmanager
    def transaction(self) -> Iterator[_Transaction]:
        yield _Transaction(self.state)


class _Repository:
    def __init__(self) -> None:
        self.plan = _statistical_plan()
        self.result = _result()
        self.detection_plans = _Store()
        self.assessments = _Store()
        self.runs: dict[UUID, OutlierDetectionRun] = {}
        self.candidates: dict[UUID, ReferenceTensilePairOutlierCandidate] = {}

    def _detection_snapshot(self, plan_id: UUID) -> OutlierDetectionPlanSnapshot:
        revision_id = self.detection_plans.state.heads.get(plan_id)
        if revision_id is None:
            raise StatisticsConflict("detection plan not found")
        return OutlierDetectionPlanSnapshot(
            plan_id,
            RevisionSnapshot(
                self.detection_plans.state.records[revision_id],
                cast(
                    ReferenceTensilePairOutlierDetectionPlanContent,
                    self.detection_plans.state.contents[revision_id],
                ),
            ),
        )

    def _assessment_snapshot(self, assessment_id: UUID) -> OutlierAssessmentSnapshot:
        revision_id = self.assessments.state.heads.get(assessment_id)
        if revision_id is None:
            raise StatisticsConflict("assessment not found")
        return OutlierAssessmentSnapshot(
            assessment_id,
            RevisionSnapshot(
                self.assessments.state.records[revision_id],
                cast(
                    ReferenceTensilePairOutlierAssessmentContent,
                    self.assessments.state.contents[revision_id],
                ),
            ),
        )

    def get_result(
        self, *, context: SecurityContext, decision: AuthorizationDecision, result_id: UUID
    ) -> StatisticalResultSnapshot:
        assert context is CONTEXT
        assert decision in (READ, EXECUTE)
        assert result_id == RESULT
        return self.result

    def outlier_detection_plan_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[ReferenceTensilePairOutlierDetectionPlanContent]:
        assert context is CONTEXT
        assert decision is EXECUTE
        return cast(
            RevisionStore[ReferenceTensilePairOutlierDetectionPlanContent],
            self.detection_plans,
        )

    def outlier_assessment_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[ReferenceTensilePairOutlierAssessmentContent]:
        assert context is CONTEXT
        assert decision is EXECUTE
        return cast(RevisionStore[ReferenceTensilePairOutlierAssessmentContent], self.assessments)

    def get_outlier_detection_plan(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        detection_plan_id: UUID,
    ) -> OutlierDetectionPlanSnapshot:
        assert context is CONTEXT
        assert decision in (READ, EXECUTE)
        return self._detection_snapshot(detection_plan_id)

    def get_outlier_detection_plan_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        detection_plan_id: UUID,
        detection_plan_revision_id: UUID,
    ) -> RevisionSnapshot[ReferenceTensilePairOutlierDetectionPlanContent]:
        assert context is CONTEXT
        assert decision in (READ, EXECUTE)
        record = self.detection_plans.state.records[detection_plan_revision_id]
        assert record.aggregate_id == detection_plan_id
        return RevisionSnapshot(
            record,
            cast(
                ReferenceTensilePairOutlierDetectionPlanContent,
                self.detection_plans.state.contents[detection_plan_revision_id],
            ),
        )

    def list_outlier_detection_plans(
        self, *, context: SecurityContext, decision: AuthorizationDecision, limit: int
    ) -> tuple[OutlierDetectionPlanSnapshot, ...]:
        assert context is CONTEXT
        assert decision is READ
        plan_ids = list(self.detection_plans.state.heads)[:limit]
        return tuple(self._detection_snapshot(plan_id) for plan_id in plan_ids)

    def create_outlier_detection_run(
        self, *, context: SecurityContext, decision: AuthorizationDecision, run: OutlierDetectionRun
    ) -> OutlierDetectionRun:
        assert context is CONTEXT
        assert decision is EXECUTE
        self.runs[run.id] = run
        return run

    def succeed_outlier_detection_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
        candidates: tuple[ReferenceTensilePairOutlierCandidate, ...],
    ) -> OutlierDetectionRun:
        assert context is CONTEXT
        assert decision is EXECUTE
        for candidate in candidates:
            self.candidates[candidate.id] = candidate
        terminal = replace(
            self.runs[run_id],
            status=OutlierDetectionRunStatus.SUCCEEDED,
            candidate_count=len(candidates),
            ended_at=NOW,
            candidates=candidates,
        )
        self.runs[run_id] = terminal
        return terminal

    def fail_outlier_detection_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
        failure_code: str,
    ) -> OutlierDetectionRun:
        assert context is CONTEXT
        assert decision is EXECUTE
        terminal = replace(
            self.runs[run_id],
            status=OutlierDetectionRunStatus.FAILED,
            failure_code=failure_code,
            ended_at=NOW,
        )
        self.runs[run_id] = terminal
        return terminal

    def get_outlier_detection_run(
        self, *, context: SecurityContext, decision: AuthorizationDecision, run_id: UUID
    ) -> OutlierDetectionRun:
        assert context is CONTEXT
        assert decision is READ
        return self.runs[run_id]

    def get_outlier_candidate(
        self, *, context: SecurityContext, decision: AuthorizationDecision, candidate_id: UUID
    ) -> ReferenceTensilePairOutlierCandidate:
        assert context is CONTEXT
        assert decision is EXECUTE
        return self.candidates[candidate_id]

    def list_outlier_candidates_for_detection_plan(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        detection_plan_id: UUID,
        detection_plan_revision_id: UUID,
    ) -> tuple[ReferenceTensilePairOutlierCandidate, ...]:
        assert context is CONTEXT
        assert decision is READ
        return tuple(
            candidate
            for candidate in self.candidates.values()
            if (
                candidate.detection_plan_id,
                candidate.detection_plan_revision_id,
            )
            == (detection_plan_id, detection_plan_revision_id)
        )

    def get_plan_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        plan_id: UUID,
        plan_revision_id: UUID,
    ) -> RevisionSnapshot[ReferenceTensilePairPlanContent]:
        assert context is CONTEXT
        assert decision is EXECUTE
        assert (plan_id, plan_revision_id) == (STATISTICAL_PLAN, STATISTICAL_PLAN_REVISION)
        return self.plan

    def get_outlier_assessment(
        self, *, context: SecurityContext, decision: AuthorizationDecision, assessment_id: UUID
    ) -> OutlierAssessmentSnapshot:
        assert context is CONTEXT
        assert decision is READ
        return self._assessment_snapshot(assessment_id)

    def list_outlier_assessments_for_candidate_scope(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        candidate_id: UUID,
        statistical_plan_id: UUID,
        statistical_plan_revision_id: UUID,
    ) -> tuple[OutlierAssessmentSnapshot, ...]:
        assert context is CONTEXT
        assert decision is READ
        values = (
            self._assessment_snapshot(assessment_id)
            for assessment_id in self.assessments.state.heads
        )
        return tuple(
            value
            for value in values
            if (
                value.current.content.candidate_id,
                value.current.content.statistical_plan_id,
                value.current.content.statistical_plan_revision_id,
            )
            == (candidate_id, statistical_plan_id, statistical_plan_revision_id)
        )


def _service() -> tuple[StatisticsService, _Repository]:
    values = iter(
        (
            DETECTION_PLAN,
            DETECTION_RUN,
            FIRST_CANDIDATE,
            SECOND_CANDIDATE,
            FIRST_ASSESSMENT,
            SECOND_ASSESSMENT,
        )
    )
    repository = _Repository()
    return (
        StatisticsService(
            repository=cast(StatisticsRepository, repository),
            datasets=cast(DatasetService, object()),
            artifacts=cast(ArtifactService, object()),
            id_factory=lambda: next(values),
        ),
        repository,
    )


def _detection_command() -> CreateReferenceTensilePairOutlierDetectionPlan:
    return CreateReferenceTensilePairOutlierDetectionPlan(
        classification=DataClassification.INTERNAL,
        content=ReferenceTensilePairOutlierDetectionPlanContent(
            plan_label="Review pair peak difference",
            statistical_result_id=RESULT,
            statistical_result_revision_id=RESULT_REVISION,
            relative_peak_difference_threshold=0.2,
        ),
        change_reason="Pin a declared review threshold to the immutable result",
    )


def test_outlier_detector_preserves_the_pinned_statistics_result_and_both_inputs() -> None:
    service, repository = _service()
    source_result = repository.result
    source_plan = repository.plan
    detection_plan = service.create_reference_tensile_pair_outlier_detection_plan(
        CONTEXT, EXECUTE, _detection_command()
    )

    run = service.execute_reference_tensile_pair_outlier_detection(
        CONTEXT,
        EXECUTE,
        ExecuteReferenceTensilePairOutlierDetection(
            detection_plan_id=detection_plan.id,
            detection_plan_revision_id=detection_plan.current.record.revision_id,
            change_reason="Generate review candidates without editing source evidence",
        ),
    )

    assert run.status is OutlierDetectionRunStatus.SUCCEEDED
    assert run.candidate_count == 2
    assert tuple(candidate.id for candidate in run.candidates) == (
        FIRST_CANDIDATE,
        SECOND_CANDIDATE,
    )
    assert repository.result == source_result
    assert repository.plan == source_plan
    assert run.candidates[0].selection_revision_id == FIRST_SELECTION_REVISION
    assert run.candidates[1].dataset_revision_id == SECOND_DATASET_REVISION


def test_outlier_assessments_are_append_only_and_cannot_escape_the_pinned_plan_scope() -> None:
    service, _ = _service()
    detection_plan = service.create_reference_tensile_pair_outlier_detection_plan(
        CONTEXT, EXECUTE, _detection_command()
    )
    run = service.execute_reference_tensile_pair_outlier_detection(
        CONTEXT,
        EXECUTE,
        ExecuteReferenceTensilePairOutlierDetection(
            detection_plan_id=detection_plan.id,
            detection_plan_revision_id=detection_plan.current.record.revision_id,
            change_reason="Generate review candidates without editing source evidence",
        ),
    )
    candidate = run.candidates[0]

    with pytest.raises(StatisticsConflict, match="scope must match"):
        service.create_reference_tensile_pair_outlier_assessment(
            CONTEXT,
            EXECUTE,
            CreateReferenceTensilePairOutlierAssessment(
                classification=DataClassification.INTERNAL,
                content=ReferenceTensilePairOutlierAssessmentContent(
                    candidate_id=candidate.id,
                    statistical_plan_id=STATISTICAL_PLAN,
                    statistical_plan_revision_id=UUID("fa000000-0000-4000-8000-000000000018"),
                    decision=OutlierAssessmentDecision.RETAINED,
                    assessment_reason="This must fail because the scope is stale.",
                ),
                change_reason="Attempt a stale assessment",
            ),
        )

    first = service.create_reference_tensile_pair_outlier_assessment(
        CONTEXT,
        EXECUTE,
        CreateReferenceTensilePairOutlierAssessment(
            classification=DataClassification.INTERNAL,
            content=ReferenceTensilePairOutlierAssessmentContent(
                candidate_id=candidate.id,
                statistical_plan_id=STATISTICAL_PLAN,
                statistical_plan_revision_id=STATISTICAL_PLAN_REVISION,
                decision=OutlierAssessmentDecision.RETAINED,
                assessment_reason="Review found no source-data issue.",
            ),
            change_reason="Record human review",
        ),
    )
    second = service.create_reference_tensile_pair_outlier_assessment(
        CONTEXT,
        EXECUTE,
        CreateReferenceTensilePairOutlierAssessment(
            classification=DataClassification.INTERNAL,
            content=ReferenceTensilePairOutlierAssessmentContent(
                candidate_id=candidate.id,
                statistical_plan_id=STATISTICAL_PLAN,
                statistical_plan_revision_id=STATISTICAL_PLAN_REVISION,
                decision=OutlierAssessmentDecision.EXCLUDED_FROM_REFERENCE_ANALYSIS,
                assessment_reason=(
                    "A later documented review excludes only this reference analysis."
                ),
            ),
            change_reason="Append a later review decision",
        ),
    )
    comparison = service.get_reference_tensile_pair_outlier_scope_comparison(
        CONTEXT,
        READ,
        detection_plan_id=detection_plan.id,
        detection_plan_revision_id=detection_plan.current.record.revision_id,
    )

    entry = next(item for item in comparison.entries if item.candidate.id == candidate.id)
    assert first.id != second.id
    assert len(entry.assessments) == 2
    assert {item.current.content.decision for item in entry.assessments} == {
        OutlierAssessmentDecision.RETAINED,
        OutlierAssessmentDecision.EXCLUDED_FROM_REFERENCE_ANALYSIS,
    }
    assert comparison.statistical_result.current.record.revision_id == RESULT_REVISION

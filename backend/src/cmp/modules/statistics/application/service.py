"""Committed reference Statistics/QC Runs over two immutable Dataset Selections."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from cmp.modules.artifacts.application.content import ArtifactService
from cmp.modules.artifacts.domain.content import ArtifactRecord
from cmp.modules.datasets.application.service import (
    DatasetRevisionSnapshot,
    DatasetSelectionRevisionSnapshot,
    DatasetService,
)
from cmp.modules.datasets.domain.reference_tensile import (
    DatasetRepresentation,
    normalized_points_from_parquet,
)
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
    Permission,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.statistics.domain.reference_tensile_outlier import (
    OutlierDetectionRunStatus,
    ReferenceTensilePairOutlierAssessmentContent,
    ReferenceTensilePairOutlierCandidate,
    ReferenceTensilePairOutlierDetectionPlanContent,
    reference_tensile_pair_review_candidates,
)
from cmp.modules.statistics.domain.reference_tensile_pair import (
    REFERENCE_TENSILE_PAIR_CURVE_SCHEMA,
    REFERENCE_TENSILE_PAIR_PLAN_SCHEMA,
    REFERENCE_TENSILE_PAIR_RESULT_SCHEMA,
    REFERENCE_TENSILE_PAIR_SCHEMA_VERSION,
    InvalidStatisticsRequest,
    QcObservation,
    QcOutcome,
    ReferenceTensilePairCurvePoint,
    ReferenceTensilePairPlanContent,
    ReferenceTensilePairResultContent,
    ReferenceTensilePairStatistics,
    StatisticalRunStatus,
    StatisticsConflict,
    calculate_reference_tensile_pair_statistics,
    observed_grid_qc,
    reference_tensile_pair_curve_from_parquet,
    reference_tensile_pair_curve_parquet_bytes,
)
from cmp.shared.application.revisions import (
    CreateRevisionedAggregate,
    ReviseAggregate,
    RevisionService,
    RevisionStore,
)
from cmp.shared.domain.revisions import AggregateAlreadyExists, RevisionRecord, TenantScope

STATISTICAL_PLAN_AGGREGATE_TYPE = "statistics.statistical_plan"
STATISTICAL_RESULT_AGGREGATE_TYPE = "statistics.statistical_result"
OUTLIER_DETECTION_PLAN_AGGREGATE_TYPE = "statistics.outlier_detection_plan"
OUTLIER_ASSESSMENT_AGGREGATE_TYPE = "statistics.outlier_assessment"


@dataclass(frozen=True, slots=True)
class RevisionSnapshot[ContentT]:
    record: RevisionRecord
    content: ContentT


@dataclass(frozen=True, slots=True)
class StatisticalPlanSnapshot:
    id: UUID
    current: RevisionSnapshot[ReferenceTensilePairPlanContent]


@dataclass(frozen=True, slots=True)
class StatisticalResultSnapshot:
    id: UUID
    current: RevisionSnapshot[ReferenceTensilePairResultContent]


@dataclass(frozen=True, slots=True)
class OutlierDetectionPlanSnapshot:
    id: UUID
    current: RevisionSnapshot[ReferenceTensilePairOutlierDetectionPlanContent]


@dataclass(frozen=True, slots=True)
class OutlierAssessmentSnapshot:
    id: UUID
    current: RevisionSnapshot[ReferenceTensilePairOutlierAssessmentContent]


@dataclass(frozen=True, slots=True)
class OutlierDetectionRun:
    id: UUID
    classification: DataClassification
    detection_plan_id: UUID
    detection_plan_revision_id: UUID
    statistical_result_id: UUID
    statistical_result_revision_id: UUID
    status: OutlierDetectionRunStatus
    candidate_count: int
    failure_code: str | None
    change_reason: str
    started_at: datetime
    ended_at: datetime | None
    created_by: UUID
    request_id: UUID
    trace_id: str
    candidates: tuple[ReferenceTensilePairOutlierCandidate, ...] = ()


@dataclass(frozen=True, slots=True)
class OutlierScopeComparisonEntry:
    candidate: ReferenceTensilePairOutlierCandidate
    assessments: tuple[OutlierAssessmentSnapshot, ...]
    latest_assessment: OutlierAssessmentSnapshot | None


@dataclass(frozen=True, slots=True)
class OutlierScopeComparison:
    detection_plan: OutlierDetectionPlanSnapshot
    statistical_result: StatisticalResultSnapshot
    entries: tuple[OutlierScopeComparisonEntry, ...]


@dataclass(frozen=True, slots=True)
class StatisticalRun:
    id: UUID
    classification: DataClassification
    plan_id: UUID
    plan_revision_id: UUID
    first_selection_id: UUID
    first_selection_revision_id: UUID
    first_dataset_id: UUID
    first_dataset_revision_id: UUID
    second_selection_id: UUID
    second_selection_revision_id: UUID
    second_dataset_id: UUID
    second_dataset_revision_id: UUID
    status: StatisticalRunStatus
    sample_count: int
    result_id: UUID | None
    result_revision_id: UUID | None
    curve_artifact_id: UUID | None
    curve_sha256: str | None
    curve_point_count: int | None
    failure_code: str | None
    change_reason: str
    started_at: datetime
    ended_at: datetime | None
    created_by: UUID
    request_id: UUID
    trace_id: str
    qc_observations: tuple[QcObservation, ...] = ()


@dataclass(frozen=True, slots=True)
class CreateReferenceTensilePairPlan:
    classification: DataClassification
    content: ReferenceTensilePairPlanContent
    change_reason: str


@dataclass(frozen=True, slots=True)
class ReviseReferenceTensilePairPlan:
    expected_current_revision_id: UUID
    content: ReferenceTensilePairPlanContent
    change_reason: str


@dataclass(frozen=True, slots=True)
class ExecuteReferenceTensilePairStatistics:
    plan_id: UUID
    plan_revision_id: UUID
    change_reason: str


@dataclass(frozen=True, slots=True)
class CreateReferenceTensilePairOutlierDetectionPlan:
    classification: DataClassification
    content: ReferenceTensilePairOutlierDetectionPlanContent
    change_reason: str


@dataclass(frozen=True, slots=True)
class ReviseReferenceTensilePairOutlierDetectionPlan:
    expected_current_revision_id: UUID
    content: ReferenceTensilePairOutlierDetectionPlanContent
    change_reason: str


@dataclass(frozen=True, slots=True)
class ExecuteReferenceTensilePairOutlierDetection:
    detection_plan_id: UUID
    detection_plan_revision_id: UUID
    change_reason: str


@dataclass(frozen=True, slots=True)
class CreateReferenceTensilePairOutlierAssessment:
    classification: DataClassification
    content: ReferenceTensilePairOutlierAssessmentContent
    change_reason: str


class StatisticsRepository(Protocol):
    def plan_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[ReferenceTensilePairPlanContent]: ...

    def result_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[ReferenceTensilePairResultContent]: ...

    def get_plan(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        plan_id: UUID,
    ) -> StatisticalPlanSnapshot: ...

    def get_plan_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        plan_id: UUID,
        plan_revision_id: UUID,
    ) -> RevisionSnapshot[ReferenceTensilePairPlanContent]: ...

    def list_plans(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        limit: int,
    ) -> tuple[StatisticalPlanSnapshot, ...]: ...

    def get_result(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        result_id: UUID,
    ) -> StatisticalResultSnapshot: ...

    def create_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run: StatisticalRun,
    ) -> StatisticalRun: ...

    def succeed_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
        result: StatisticalResultSnapshot,
        qc_observations: tuple[QcObservation, ...],
    ) -> StatisticalRun: ...

    def fail_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
        failure_code: str,
        qc_observations: tuple[QcObservation, ...],
    ) -> StatisticalRun: ...

    def get_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
    ) -> StatisticalRun: ...

    def outlier_detection_plan_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[ReferenceTensilePairOutlierDetectionPlanContent]: ...

    def outlier_assessment_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[ReferenceTensilePairOutlierAssessmentContent]: ...

    def get_outlier_detection_plan(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        detection_plan_id: UUID,
    ) -> OutlierDetectionPlanSnapshot: ...

    def get_outlier_detection_plan_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        detection_plan_id: UUID,
        detection_plan_revision_id: UUID,
    ) -> RevisionSnapshot[ReferenceTensilePairOutlierDetectionPlanContent]: ...

    def list_outlier_detection_plans(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        limit: int,
    ) -> tuple[OutlierDetectionPlanSnapshot, ...]: ...

    def create_outlier_detection_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run: OutlierDetectionRun,
    ) -> OutlierDetectionRun: ...

    def succeed_outlier_detection_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
        candidates: tuple[ReferenceTensilePairOutlierCandidate, ...],
    ) -> OutlierDetectionRun: ...

    def fail_outlier_detection_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
        failure_code: str,
    ) -> OutlierDetectionRun: ...

    def get_outlier_detection_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
    ) -> OutlierDetectionRun: ...

    def get_outlier_candidate(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        candidate_id: UUID,
    ) -> ReferenceTensilePairOutlierCandidate: ...

    def list_outlier_candidates_for_detection_plan(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        detection_plan_id: UUID,
        detection_plan_revision_id: UUID,
    ) -> tuple[ReferenceTensilePairOutlierCandidate, ...]: ...

    def get_outlier_assessment(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        assessment_id: UUID,
    ) -> OutlierAssessmentSnapshot: ...

    def list_outlier_assessments_for_candidate_scope(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        candidate_id: UUID,
        statistical_plan_id: UUID,
        statistical_plan_revision_id: UUID,
    ) -> tuple[OutlierAssessmentSnapshot, ...]: ...


def _reason(value: str) -> str:
    if not value or value != value.strip() or len(value) > 2000 or "\x00" in value:
        raise ValueError("change_reason must be trimmed and contain 1..2000 characters")
    return value


def _require(
    context: SecurityContext,
    decision: AuthorizationDecision,
    permission: Permission,
) -> None:
    if (
        decision.permission is not permission
        or decision.principal_id != context.principal.id
        or decision.organization_id != context.organization_id
        or decision.project_id != context.project_id
        or decision.request_id != context.request_id
        or decision.trace_id != context.trace_id
    ):
        raise StatisticsConflict("authorization decision does not match Statistics request")


class StatisticsService:
    """Own the T-20 plan/run/result workflow without mutating Dataset inputs."""

    def __init__(
        self,
        *,
        repository: StatisticsRepository,
        datasets: DatasetService,
        artifacts: ArtifactService,
        id_factory: Callable[[], UUID] = uuid4,
    ) -> None:
        self._repository = repository
        self._datasets = datasets
        self._artifacts = artifacts
        self._id_factory = id_factory

    def _id(self) -> UUID:
        value = self._id_factory()
        if value.int == 0:
            raise RuntimeError("statistics id_factory returned a zero UUID")
        return value

    @staticmethod
    def _result_id(context: SecurityContext, run_id: UUID) -> UUID:
        return uuid5(
            NAMESPACE_URL,
            "cmp:reference-tensile-pair-statistical-result:"
            f"{context.organization_id}:{context.project_id}:{run_id}",
        )

    def _plan_inputs(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        content: ReferenceTensilePairPlanContent,
    ) -> tuple[DatasetSelectionRevisionSnapshot, DatasetSelectionRevisionSnapshot]:
        first = self._datasets.get_reference_dataset_selection_revision_for_statistics(
            context,
            decision,
            content.first_selection_id,
            content.first_selection_revision_id,
        )
        second = self._datasets.get_reference_dataset_selection_revision_for_statistics(
            context,
            decision,
            content.second_selection_id,
            content.second_selection_revision_id,
        )
        if first.revision.record.scope != second.revision.record.scope:
            raise StatisticsConflict("both Selection revisions must share tenant scope")
        return first, second

    def create_reference_tensile_pair_plan(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CreateReferenceTensilePairPlan,
    ) -> StatisticalPlanSnapshot:
        _require(context, decision, Permission.STATISTICS_EXECUTE)
        reason = _reason(command.change_reason)
        first, second = self._plan_inputs(context, decision, command.content)
        scope = TenantScope(
            context.organization_id,
            context.project_id,
            command.classification.value,
        )
        if first.revision.record.scope != scope or second.revision.record.scope != scope:
            raise StatisticsConflict(
                "Plan classification must match both pinned Selection revisions"
            )
        plan_id = self._id()
        record = RevisionService(
            aggregate_type=STATISTICAL_PLAN_AGGREGATE_TYPE,
            store=self._repository.plan_store(context, decision),
        ).create(
            CreateRevisionedAggregate(
                aggregate_id=plan_id,
                scope=scope,
                schema_id=REFERENCE_TENSILE_PAIR_PLAN_SCHEMA,
                schema_version=REFERENCE_TENSILE_PAIR_SCHEMA_VERSION,
                content=command.content,
                created_by=context.principal.id,
                change_reason=reason,
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        return StatisticalPlanSnapshot(plan_id, RevisionSnapshot(record, command.content))

    def revise_reference_tensile_pair_plan(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        plan_id: UUID,
        command: ReviseReferenceTensilePairPlan,
    ) -> StatisticalPlanSnapshot:
        _require(context, decision, Permission.STATISTICS_EXECUTE)
        reason = _reason(command.change_reason)
        existing = self._repository.get_plan(context=context, decision=decision, plan_id=plan_id)
        if command.content.plan_label != existing.current.content.plan_label:
            raise StatisticsConflict(
                "Statistical Plan label is a stable identity and cannot change"
            )
        first, second = self._plan_inputs(context, decision, command.content)
        if (
            first.revision.record.scope != existing.current.record.scope
            or second.revision.record.scope != existing.current.record.scope
        ):
            raise StatisticsConflict("Plan Selection revisions are outside its tenant scope")
        record = RevisionService(
            aggregate_type=STATISTICAL_PLAN_AGGREGATE_TYPE,
            store=self._repository.plan_store(context, decision),
        ).revise(
            ReviseAggregate(
                aggregate_id=plan_id,
                scope=existing.current.record.scope,
                expected_current_revision_id=command.expected_current_revision_id,
                based_on_revision_id=command.expected_current_revision_id,
                schema_id=REFERENCE_TENSILE_PAIR_PLAN_SCHEMA,
                schema_version=REFERENCE_TENSILE_PAIR_SCHEMA_VERSION,
                content=command.content,
                created_by=context.principal.id,
                change_reason=reason,
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        return StatisticalPlanSnapshot(plan_id, RevisionSnapshot(record, command.content))

    def get_plan(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        plan_id: UUID,
    ) -> StatisticalPlanSnapshot:
        _require(context, decision, Permission.STATISTICS_READ)
        return self._repository.get_plan(context=context, decision=decision, plan_id=plan_id)

    def list_plans(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        *,
        limit: int = 100,
    ) -> tuple[StatisticalPlanSnapshot, ...]:
        _require(context, decision, Permission.STATISTICS_READ)
        if not 1 <= limit <= 200:
            raise ValueError("limit must be between 1 and 200")
        return self._repository.list_plans(context=context, decision=decision, limit=limit)

    @staticmethod
    def _dataset_input(
        selection: DatasetSelectionRevisionSnapshot,
        dataset: DatasetRevisionSnapshot,
        expected_scope: TenantScope,
    ) -> None:
        if dataset.dataset_id != selection.revision.content.dataset_id:
            raise StatisticsConflict(
                "Selection Dataset identity does not match its pinned revision"
            )
        if dataset.revision.record.scope != expected_scope:
            raise StatisticsConflict("Statistical input Dataset is outside the Plan tenant scope")
        if dataset.revision.content.representation is not DatasetRepresentation.NORMALIZED:
            raise StatisticsConflict(
                "reference Statistics accepts only normalized reference tensile Dataset revisions"
            )

    async def execute_reference_tensile_pair_statistics(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: ExecuteReferenceTensilePairStatistics,
    ) -> StatisticalRun:
        """Commit a durable run and immutable output only after fixed-shape QC has passed."""

        _require(context, decision, Permission.STATISTICS_EXECUTE)
        reason = _reason(command.change_reason)
        plan = self._repository.get_plan_revision(
            context=context,
            decision=decision,
            plan_id=command.plan_id,
            plan_revision_id=command.plan_revision_id,
        )
        first_selection, second_selection = self._plan_inputs(context, decision, plan.content)
        expected_scope = plan.record.scope
        if (
            first_selection.revision.record.scope != expected_scope
            or second_selection.revision.record.scope != expected_scope
        ):
            raise StatisticsConflict("Plan and Selection revisions must share tenant scope")
        first_dataset = self._datasets.get_dataset_revision_for_statistics(
            context,
            decision,
            first_selection.revision.content.dataset_revision_id,
        )
        second_dataset = self._datasets.get_dataset_revision_for_statistics(
            context,
            decision,
            second_selection.revision.content.dataset_revision_id,
        )
        self._dataset_input(first_selection, first_dataset, expected_scope)
        self._dataset_input(second_selection, second_dataset, expected_scope)
        run = StatisticalRun(
            id=self._id(),
            classification=DataClassification(expected_scope.classification),
            plan_id=command.plan_id,
            plan_revision_id=command.plan_revision_id,
            first_selection_id=first_selection.selection_id,
            first_selection_revision_id=first_selection.revision.record.revision_id,
            first_dataset_id=first_dataset.dataset_id,
            first_dataset_revision_id=first_dataset.revision.record.revision_id,
            second_selection_id=second_selection.selection_id,
            second_selection_revision_id=second_selection.revision.record.revision_id,
            second_dataset_id=second_dataset.dataset_id,
            second_dataset_revision_id=second_dataset.revision.record.revision_id,
            status=StatisticalRunStatus.EXECUTING,
            sample_count=2,
            result_id=None,
            result_revision_id=None,
            curve_artifact_id=None,
            curve_sha256=None,
            curve_point_count=None,
            failure_code=None,
            change_reason=reason,
            started_at=datetime.now(UTC),
            ended_at=None,
            created_by=context.principal.id,
            request_id=context.request_id,
            trace_id=context.trace_id,
        )
        created = self._repository.create_run(context=context, decision=decision, run=run)
        try:
            _, first_bytes = await self._artifacts.read_verified_bytes(
                context,
                decision,
                first_dataset.revision.content.data_artifact_id,
                maximum_bytes=16 * 1024 * 1024,
            )
            _, second_bytes = await self._artifacts.read_verified_bytes(
                context,
                decision,
                second_dataset.revision.content.data_artifact_id,
                maximum_bytes=16 * 1024 * 1024,
            )
            first_points = normalized_points_from_parquet(first_bytes)
            second_points = normalized_points_from_parquet(second_bytes)
        except Exception:
            return self._repository.fail_run(
                context=context,
                decision=decision,
                run_id=created.id,
                failure_code="input_artifact_unreadable",
                qc_observations=(
                    QcObservation(
                        check_code="input_artifact_readable",
                        outcome=QcOutcome.FAILED,
                        detail="One or more pinned normalized Dataset Artifacts could not be read.",
                    ),
                ),
            )
        if (
            len(first_points) != first_dataset.revision.content.point_count
            or len(second_points) != second_dataset.revision.content.point_count
        ):
            return self._repository.fail_run(
                context=context,
                decision=decision,
                run_id=created.id,
                failure_code="input_point_count_mismatch",
                qc_observations=(
                    QcObservation(
                        check_code="input_artifact_readable",
                        outcome=QcOutcome.FAILED,
                        detail=(
                            "A pinned Dataset Artifact point count differs from its "
                            "immutable revision."
                        ),
                    ),
                ),
            )
        distinct_runs = QcObservation(
            check_code="distinct_test_runs",
            outcome=(
                QcOutcome.PASSED
                if first_dataset.revision.content.test_run_id
                != second_dataset.revision.content.test_run_id
                else QcOutcome.FAILED
            ),
            detail=(
                "The two samples are backed by distinct Test Runs."
                if first_dataset.revision.content.test_run_id
                != second_dataset.revision.content.test_run_id
                else "Both selections resolve to the same Test Run and are not independent samples."
            ),
        )
        grid = observed_grid_qc(first_points, second_points)
        qc_observations = (distinct_runs, grid)
        if any(item.outcome is QcOutcome.FAILED for item in qc_observations):
            return self._repository.fail_run(
                context=context,
                decision=decision,
                run_id=created.id,
                failure_code="input_qc_failed",
                qc_observations=qc_observations,
            )
        statistics: ReferenceTensilePairStatistics = calculate_reference_tensile_pair_statistics(
            first_points, second_points
        )
        artifact: ArtifactRecord | None = None
        result_committed = False
        try:
            artifact = await self._artifacts.finalize_derived_bytes(
                context,
                decision,
                classification=created.classification,
                artifact_role="statistics.reference_tensile_pair_curve",
                schema_ref=REFERENCE_TENSILE_PAIR_CURVE_SCHEMA,
                media_type="application/vnd.apache.parquet",
                value=reference_tensile_pair_curve_parquet_bytes(statistics.curve),
                idempotency_key=f"statistics:{created.id}:reference-tensile-pair",
            )
            content = ReferenceTensilePairResultContent(
                statistical_run_id=created.id,
                plan_id=created.plan_id,
                plan_revision_id=created.plan_revision_id,
                first_selection_id=created.first_selection_id,
                first_selection_revision_id=created.first_selection_revision_id,
                first_dataset_id=created.first_dataset_id,
                first_dataset_revision_id=created.first_dataset_revision_id,
                second_selection_id=created.second_selection_id,
                second_selection_revision_id=created.second_selection_revision_id,
                second_dataset_id=created.second_dataset_id,
                second_dataset_revision_id=created.second_dataset_revision_id,
                curve_artifact_id=artifact.artifact.id,
                curve_sha256=artifact.artifact.sha256,
                curve_point_count=len(statistics.curve),
                scalar=statistics.scalar,
            )
            result = self._register_result(context, decision, content, reason)
            result_committed = True
            return self._repository.succeed_run(
                context=context,
                decision=decision,
                run_id=created.id,
                result=result,
                qc_observations=qc_observations,
            )
        except Exception as error:
            if result_committed:
                raise StatisticsConflict(
                    "Statistical Result output committed but Statistical Run terminal state "
                    "requires reconciliation"
                ) from error
            try:
                self._repository.fail_run(
                    context=context,
                    decision=decision,
                    run_id=created.id,
                    failure_code="statistics_command_failed",
                    qc_observations=qc_observations,
                )
            except Exception:
                pass
            raise

    def _register_result(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        content: ReferenceTensilePairResultContent,
        reason: str,
    ) -> StatisticalResultSnapshot:
        aggregate_id = self._result_id(context, content.statistical_run_id)
        service = RevisionService(
            aggregate_type=STATISTICAL_RESULT_AGGREGATE_TYPE,
            store=self._repository.result_store(context, decision),
        )
        try:
            record = service.create(
                CreateRevisionedAggregate(
                    aggregate_id=aggregate_id,
                    scope=TenantScope(
                        context.organization_id,
                        context.project_id,
                        # Result classification is pinned by the already-validated Plan/Run.
                        # The repository trigger cross-checks the supplied result against that Run.
                        self._repository.get_run(
                            context=context,
                            decision=decision,
                            run_id=content.statistical_run_id,
                        ).classification.value,
                    ),
                    schema_id=REFERENCE_TENSILE_PAIR_RESULT_SCHEMA,
                    schema_version=REFERENCE_TENSILE_PAIR_SCHEMA_VERSION,
                    content=content,
                    created_by=context.principal.id,
                    change_reason=reason,
                    request_id=context.request_id,
                    trace_id=context.trace_id,
                )
            )
        except AggregateAlreadyExists as error:
            existing = self._repository.get_result(
                context=context, decision=decision, result_id=aggregate_id
            )
            if existing.current.content != content:
                raise StatisticsConflict(
                    "Statistical Result identity is already bound to different immutable output"
                ) from error
            return existing
        return StatisticalResultSnapshot(aggregate_id, RevisionSnapshot(record, content))

    def get_run(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
    ) -> StatisticalRun:
        _require(context, decision, Permission.STATISTICS_READ)
        return self._repository.get_run(context=context, decision=decision, run_id=run_id)

    def get_result(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        result_id: UUID,
    ) -> StatisticalResultSnapshot:
        _require(context, decision, Permission.STATISTICS_READ)
        return self._repository.get_result(context=context, decision=decision, result_id=result_id)

    def _outlier_result_input(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        content: ReferenceTensilePairOutlierDetectionPlanContent,
    ) -> StatisticalResultSnapshot:
        result = self._repository.get_result(
            context=context,
            decision=decision,
            result_id=content.statistical_result_id,
        )
        if result.current.record.revision_id != content.statistical_result_revision_id:
            raise StatisticsConflict(
                "Outlier Detection Plan must pin the current immutable Statistical Result revision"
            )
        if result.current.record.scope.organization_id != context.organization_id or (
            result.current.record.scope.project_id != context.project_id
        ):
            raise StatisticsConflict("Statistical Result is outside the detector tenant scope")
        return result

    def create_reference_tensile_pair_outlier_detection_plan(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CreateReferenceTensilePairOutlierDetectionPlan,
    ) -> OutlierDetectionPlanSnapshot:
        _require(context, decision, Permission.STATISTICS_EXECUTE)
        reason = _reason(command.change_reason)
        result = self._outlier_result_input(context, decision, command.content)
        scope = TenantScope(
            context.organization_id,
            context.project_id,
            command.classification.value,
        )
        if result.current.record.scope != scope:
            raise StatisticsConflict(
                "Outlier Detection Plan classification must match its Statistical Result"
            )
        detection_plan_id = self._id()
        record = RevisionService(
            aggregate_type=OUTLIER_DETECTION_PLAN_AGGREGATE_TYPE,
            store=self._repository.outlier_detection_plan_store(context, decision),
        ).create(
            CreateRevisionedAggregate(
                aggregate_id=detection_plan_id,
                scope=scope,
                schema_id=(
                    "urn:cmp:statistics:reference-tensile-pair-outlier-detection-plan:1.0.0"
                ),
                schema_version="1.0.0",
                content=command.content,
                created_by=context.principal.id,
                change_reason=reason,
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        return OutlierDetectionPlanSnapshot(
            detection_plan_id,
            RevisionSnapshot(record, command.content),
        )

    def revise_reference_tensile_pair_outlier_detection_plan(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        detection_plan_id: UUID,
        command: ReviseReferenceTensilePairOutlierDetectionPlan,
    ) -> OutlierDetectionPlanSnapshot:
        _require(context, decision, Permission.STATISTICS_EXECUTE)
        reason = _reason(command.change_reason)
        existing = self._repository.get_outlier_detection_plan(
            context=context,
            decision=decision,
            detection_plan_id=detection_plan_id,
        )
        if command.content.plan_label != existing.current.content.plan_label:
            raise StatisticsConflict("Outlier Detection Plan label is a stable identity")
        result = self._outlier_result_input(context, decision, command.content)
        if result.current.record.scope != existing.current.record.scope:
            raise StatisticsConflict("Outlier Detection Plan Result is outside its tenant scope")
        record = RevisionService(
            aggregate_type=OUTLIER_DETECTION_PLAN_AGGREGATE_TYPE,
            store=self._repository.outlier_detection_plan_store(context, decision),
        ).revise(
            ReviseAggregate(
                aggregate_id=detection_plan_id,
                scope=existing.current.record.scope,
                expected_current_revision_id=command.expected_current_revision_id,
                based_on_revision_id=command.expected_current_revision_id,
                schema_id=(
                    "urn:cmp:statistics:reference-tensile-pair-outlier-detection-plan:1.0.0"
                ),
                schema_version="1.0.0",
                content=command.content,
                created_by=context.principal.id,
                change_reason=reason,
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        return OutlierDetectionPlanSnapshot(
            detection_plan_id,
            RevisionSnapshot(record, command.content),
        )

    def get_outlier_detection_plan(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        detection_plan_id: UUID,
    ) -> OutlierDetectionPlanSnapshot:
        _require(context, decision, Permission.STATISTICS_READ)
        return self._repository.get_outlier_detection_plan(
            context=context,
            decision=decision,
            detection_plan_id=detection_plan_id,
        )

    def list_outlier_detection_plans(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        *,
        limit: int = 100,
    ) -> tuple[OutlierDetectionPlanSnapshot, ...]:
        _require(context, decision, Permission.STATISTICS_READ)
        if not 1 <= limit <= 200:
            raise ValueError("limit must be between 1 and 200")
        return self._repository.list_outlier_detection_plans(
            context=context,
            decision=decision,
            limit=limit,
        )

    def execute_reference_tensile_pair_outlier_detection(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: ExecuteReferenceTensilePairOutlierDetection,
    ) -> OutlierDetectionRun:
        """Create review candidates from frozen pair evidence; never mutate the inputs."""

        _require(context, decision, Permission.STATISTICS_EXECUTE)
        reason = _reason(command.change_reason)
        plan = self._repository.get_outlier_detection_plan_revision(
            context=context,
            decision=decision,
            detection_plan_id=command.detection_plan_id,
            detection_plan_revision_id=command.detection_plan_revision_id,
        )
        result = self._outlier_result_input(context, decision, plan.content)
        if result.current.record.scope != plan.record.scope:
            raise StatisticsConflict("Outlier Detection Plan and Result must share tenant scope")
        run = OutlierDetectionRun(
            id=self._id(),
            classification=DataClassification(plan.record.scope.classification),
            detection_plan_id=command.detection_plan_id,
            detection_plan_revision_id=command.detection_plan_revision_id,
            statistical_result_id=plan.content.statistical_result_id,
            statistical_result_revision_id=plan.content.statistical_result_revision_id,
            status=OutlierDetectionRunStatus.EXECUTING,
            candidate_count=0,
            failure_code=None,
            change_reason=reason,
            started_at=datetime.now(UTC),
            ended_at=None,
            created_by=context.principal.id,
            request_id=context.request_id,
            trace_id=context.trace_id,
        )
        created = self._repository.create_outlier_detection_run(
            context=context,
            decision=decision,
            run=run,
        )
        try:
            candidates = reference_tensile_pair_review_candidates(
                candidate_ids=(self._id(), self._id()),
                detection_run_id=created.id,
                detection_plan_id=created.detection_plan_id,
                detection_plan_revision_id=created.detection_plan_revision_id,
                statistical_result_id=created.statistical_result_id,
                statistical_result_revision_id=created.statistical_result_revision_id,
                result=result.current.content,
                relative_peak_difference_threshold=(
                    plan.content.relative_peak_difference_threshold
                ),
            )
            return self._repository.succeed_outlier_detection_run(
                context=context,
                decision=decision,
                run_id=created.id,
                candidates=candidates,
            )
        except Exception:
            try:
                self._repository.fail_outlier_detection_run(
                    context=context,
                    decision=decision,
                    run_id=created.id,
                    failure_code="outlier_detection_command_failed",
                )
            except Exception:
                pass
            raise

    def get_outlier_detection_run(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
    ) -> OutlierDetectionRun:
        _require(context, decision, Permission.STATISTICS_READ)
        return self._repository.get_outlier_detection_run(
            context=context,
            decision=decision,
            run_id=run_id,
        )

    def create_reference_tensile_pair_outlier_assessment(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CreateReferenceTensilePairOutlierAssessment,
    ) -> OutlierAssessmentSnapshot:
        _require(context, decision, Permission.STATISTICS_EXECUTE)
        reason = _reason(command.change_reason)
        candidate = self._repository.get_outlier_candidate(
            context=context,
            decision=decision,
            candidate_id=command.content.candidate_id,
        )
        if (
            candidate.statistical_plan_id != command.content.statistical_plan_id
            or candidate.statistical_plan_revision_id
            != command.content.statistical_plan_revision_id
        ):
            raise StatisticsConflict(
                "Outlier Assessment scope must match the candidate's immutable Statistical Plan"
            )
        plan = self._repository.get_plan_revision(
            context=context,
            decision=decision,
            plan_id=command.content.statistical_plan_id,
            plan_revision_id=command.content.statistical_plan_revision_id,
        )
        scope = TenantScope(
            context.organization_id,
            context.project_id,
            command.classification.value,
        )
        if plan.record.scope != scope:
            raise StatisticsConflict("Outlier Assessment classification must match its scope Plan")
        assessment_id = self._id()
        record = RevisionService(
            aggregate_type=OUTLIER_ASSESSMENT_AGGREGATE_TYPE,
            store=self._repository.outlier_assessment_store(context, decision),
        ).create(
            CreateRevisionedAggregate(
                aggregate_id=assessment_id,
                scope=scope,
                schema_id="urn:cmp:statistics:reference-tensile-pair-outlier-assessment:1.0.0",
                schema_version="1.0.0",
                content=command.content,
                created_by=context.principal.id,
                change_reason=reason,
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        return OutlierAssessmentSnapshot(
            assessment_id,
            RevisionSnapshot(record, command.content),
        )

    def get_outlier_assessment(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        assessment_id: UUID,
    ) -> OutlierAssessmentSnapshot:
        _require(context, decision, Permission.STATISTICS_READ)
        return self._repository.get_outlier_assessment(
            context=context,
            decision=decision,
            assessment_id=assessment_id,
        )

    def get_reference_tensile_pair_outlier_scope_comparison(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        *,
        detection_plan_id: UUID,
        detection_plan_revision_id: UUID,
    ) -> OutlierScopeComparison:
        _require(context, decision, Permission.STATISTICS_READ)
        plan = self._repository.get_outlier_detection_plan_revision(
            context=context,
            decision=decision,
            detection_plan_id=detection_plan_id,
            detection_plan_revision_id=detection_plan_revision_id,
        )
        result = self._outlier_result_input(context, decision, plan.content)
        candidates = self._repository.list_outlier_candidates_for_detection_plan(
            context=context,
            decision=decision,
            detection_plan_id=detection_plan_id,
            detection_plan_revision_id=detection_plan_revision_id,
        )
        entries: list[OutlierScopeComparisonEntry] = []
        for candidate in candidates:
            assessments = self._repository.list_outlier_assessments_for_candidate_scope(
                context=context,
                decision=decision,
                candidate_id=candidate.id,
                statistical_plan_id=candidate.statistical_plan_id,
                statistical_plan_revision_id=candidate.statistical_plan_revision_id,
            )
            latest = max(
                assessments,
                key=lambda value: (
                    value.current.record.created_at,
                    str(value.current.record.revision_id),
                ),
                default=None,
            )
            entries.append(
                OutlierScopeComparisonEntry(
                    candidate=candidate,
                    assessments=assessments,
                    latest_assessment=latest,
                )
            )
        detection_plan = OutlierDetectionPlanSnapshot(detection_plan_id, plan)
        return OutlierScopeComparison(
            detection_plan=detection_plan,
            statistical_result=result,
            entries=tuple(entries),
        )

    async def preview_reference_tensile_pair_result_curve(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        result_id: UUID,
        *,
        maximum_points: int,
    ) -> tuple[ReferenceTensilePairCurvePoint, ...]:
        _require(context, decision, Permission.STATISTICS_READ)
        if not 2 <= maximum_points <= 10_000:
            raise InvalidStatisticsRequest("preview point limit must be between 2 and 10000")
        result = self._repository.get_result(
            context=context, decision=decision, result_id=result_id
        )
        _, data = await self._artifacts.read_verified_bytes(
            context,
            decision,
            result.current.content.curve_artifact_id,
            maximum_bytes=32 * 1024 * 1024,
        )
        curve = reference_tensile_pair_curve_from_parquet(data)
        if len(curve) != result.current.content.curve_point_count:
            raise StatisticsConflict(
                "result curve Artifact point count differs from immutable Result"
            )
        if len(curve) <= maximum_points:
            return curve
        last = len(curve) - 1
        indexes = tuple(
            round(index * last / (maximum_points - 1)) for index in range(maximum_points)
        )
        return tuple(curve[index] for index in indexes)

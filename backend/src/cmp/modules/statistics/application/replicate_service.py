"""Committed Statistics/QC over one immutable multi-replicate tensile Selection."""

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
    DatasetService,
    TensileReplicateSelectionRevisionSnapshot,
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
from cmp.modules.statistics.domain.reference_tensile_pair import (
    QcObservation,
    QcOutcome,
    StatisticalRunStatus,
    StatisticsConflict,
)
from cmp.modules.statistics.domain.reference_tensile_replicates import (
    REFERENCE_TENSILE_REPLICATE_CURVE_SCHEMA,
    REFERENCE_TENSILE_REPLICATE_PLAN_SCHEMA,
    REFERENCE_TENSILE_REPLICATE_RESULT_SCHEMA,
    REFERENCE_TENSILE_REPLICATE_SCHEMA_VERSION,
    ReferenceTensileReplicatePlanContent,
    ReferenceTensileReplicateResultContent,
    ReplicateCurvePoint,
    calculate_reference_tensile_replicate_statistics,
    exact_replicate_grid_qc,
    reference_tensile_replicate_curve_from_parquet,
    reference_tensile_replicate_curve_parquet_bytes,
)
from cmp.shared.application.revisions import (
    CreateRevisionedAggregate,
    ReviseAggregate,
    RevisionService,
    RevisionStore,
)
from cmp.shared.domain.revisions import AggregateAlreadyExists, RevisionRecord, TenantScope

REPLICATE_STATISTICAL_PLAN_AGGREGATE_TYPE = "statistics.replicate_statistical_plan"
REPLICATE_STATISTICAL_RESULT_AGGREGATE_TYPE = "statistics.replicate_statistical_result"


@dataclass(frozen=True, slots=True)
class ReplicateRevisionSnapshot[ContentT]:
    record: RevisionRecord
    content: ContentT


@dataclass(frozen=True, slots=True)
class ReplicateStatisticalPlanSnapshot:
    id: UUID
    current: ReplicateRevisionSnapshot[ReferenceTensileReplicatePlanContent]


@dataclass(frozen=True, slots=True)
class ReplicateStatisticalResultSnapshot:
    id: UUID
    current: ReplicateRevisionSnapshot[ReferenceTensileReplicateResultContent]


@dataclass(frozen=True, slots=True)
class ReplicateStatisticalRunMember:
    ordinal: int
    dataset_id: UUID
    dataset_revision_id: UUID
    test_run_id: UUID
    test_run_revision_id: UUID


@dataclass(frozen=True, slots=True)
class ReplicateStatisticalRun:
    id: UUID
    classification: DataClassification
    plan_id: UUID
    plan_revision_id: UUID
    selection_id: UUID
    selection_revision_id: UUID
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
    members: tuple[ReplicateStatisticalRunMember, ...]
    qc_observations: tuple[QcObservation, ...] = ()


@dataclass(frozen=True, slots=True)
class CreateReferenceTensileReplicateStatisticalPlan:
    classification: DataClassification
    content: ReferenceTensileReplicatePlanContent
    change_reason: str


@dataclass(frozen=True, slots=True)
class ReviseReferenceTensileReplicateStatisticalPlan:
    expected_current_revision_id: UUID
    content: ReferenceTensileReplicatePlanContent
    change_reason: str


@dataclass(frozen=True, slots=True)
class ExecuteReferenceTensileReplicateStatistics:
    plan_id: UUID
    plan_revision_id: UUID
    change_reason: str


class ReplicateStatisticsRepository(Protocol):
    def plan_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[ReferenceTensileReplicatePlanContent]: ...

    def result_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[ReferenceTensileReplicateResultContent]: ...

    def get_plan(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        plan_id: UUID,
    ) -> ReplicateStatisticalPlanSnapshot: ...

    def get_plan_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        plan_id: UUID,
        plan_revision_id: UUID,
    ) -> ReplicateRevisionSnapshot[ReferenceTensileReplicatePlanContent]: ...

    def list_plans(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        selection_revision_id: UUID,
        limit: int,
    ) -> tuple[ReplicateStatisticalPlanSnapshot, ...]: ...

    def get_result(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        result_id: UUID,
    ) -> ReplicateStatisticalResultSnapshot: ...

    def create_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run: ReplicateStatisticalRun,
    ) -> ReplicateStatisticalRun: ...

    def succeed_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
        result: ReplicateStatisticalResultSnapshot,
        qc_observations: tuple[QcObservation, ...],
    ) -> ReplicateStatisticalRun: ...

    def fail_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
        failure_code: str,
        qc_observations: tuple[QcObservation, ...],
    ) -> ReplicateStatisticalRun: ...

    def get_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
    ) -> ReplicateStatisticalRun: ...


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


class ReplicateStatisticsService:
    """Own the processed-replicate Plan/Run/Result workflow without modifying inputs."""

    def __init__(
        self,
        *,
        repository: ReplicateStatisticsRepository,
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
            "cmp:reference-tensile-replicate-statistical-result:"
            f"{context.organization_id}:{context.project_id}:{run_id}",
        )

    def _selection(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        content: ReferenceTensileReplicatePlanContent,
    ) -> TensileReplicateSelectionRevisionSnapshot:
        return self._datasets.get_reference_tensile_replicate_selection_revision_for_statistics(
            context,
            decision,
            content.selection_id,
            content.selection_revision_id,
        )

    def _processed_inputs(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        selection: TensileReplicateSelectionRevisionSnapshot,
        expected_scope: TenantScope,
    ) -> tuple[DatasetRevisionSnapshot, ...]:
        datasets = tuple(
            self._datasets.get_dataset_revision_for_statistics(
                context, decision, member.dataset_revision_id
            )
            for member in selection.revision.content.members
        )
        for member, dataset in zip(selection.revision.content.members, datasets, strict=True):
            if dataset.dataset_id != member.dataset_id:
                raise StatisticsConflict(
                    "replicate Selection Dataset identity does not match its pinned revision"
                )
            if dataset.revision.record.scope != expected_scope:
                raise StatisticsConflict("replicate Dataset is outside the Plan tenant scope")
            if dataset.revision.content.representation is not DatasetRepresentation.PROCESSED:
                raise StatisticsConflict(
                    "replicate Statistics accepts only explicitly aligned processed revisions"
                )
            if (
                dataset.revision.content.test_run_id != member.test_run_id
                or dataset.revision.content.test_run_revision_id != member.test_run_revision_id
            ):
                raise StatisticsConflict("replicate Selection Test Run binding has changed")
        return datasets

    def create_plan(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CreateReferenceTensileReplicateStatisticalPlan,
    ) -> ReplicateStatisticalPlanSnapshot:
        _require(context, decision, Permission.STATISTICS_EXECUTE)
        reason = _reason(command.change_reason)
        selection = self._selection(context, decision, command.content)
        scope = TenantScope(
            context.organization_id, context.project_id, command.classification.value
        )
        if selection.revision.record.scope != scope:
            raise StatisticsConflict("Plan classification must match its pinned Selection")
        if command.content.sample_count != len(selection.revision.content.members):
            raise StatisticsConflict("Plan sample_count must match its pinned Selection")
        self._processed_inputs(context, decision, selection, scope)
        plan_id = self._id()
        record = RevisionService(
            aggregate_type=REPLICATE_STATISTICAL_PLAN_AGGREGATE_TYPE,
            store=self._repository.plan_store(context, decision),
        ).create(
            CreateRevisionedAggregate(
                aggregate_id=plan_id,
                scope=scope,
                schema_id=REFERENCE_TENSILE_REPLICATE_PLAN_SCHEMA,
                schema_version=REFERENCE_TENSILE_REPLICATE_SCHEMA_VERSION,
                content=command.content,
                created_by=context.principal.id,
                change_reason=reason,
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        return ReplicateStatisticalPlanSnapshot(
            plan_id, ReplicateRevisionSnapshot(record, command.content)
        )

    def revise_plan(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        plan_id: UUID,
        command: ReviseReferenceTensileReplicateStatisticalPlan,
    ) -> ReplicateStatisticalPlanSnapshot:
        _require(context, decision, Permission.STATISTICS_EXECUTE)
        reason = _reason(command.change_reason)
        existing = self._repository.get_plan(context=context, decision=decision, plan_id=plan_id)
        if command.content.plan_label != existing.current.content.plan_label:
            raise StatisticsConflict("Statistical Plan label is a stable identity")
        selection = self._selection(context, decision, command.content)
        if selection.revision.record.scope != existing.current.record.scope:
            raise StatisticsConflict("Selection revision is outside the Plan tenant scope")
        if command.content.sample_count != len(selection.revision.content.members):
            raise StatisticsConflict("Plan sample_count must match its pinned Selection")
        self._processed_inputs(context, decision, selection, existing.current.record.scope)
        record = RevisionService(
            aggregate_type=REPLICATE_STATISTICAL_PLAN_AGGREGATE_TYPE,
            store=self._repository.plan_store(context, decision),
        ).revise(
            ReviseAggregate(
                aggregate_id=plan_id,
                scope=existing.current.record.scope,
                expected_current_revision_id=command.expected_current_revision_id,
                based_on_revision_id=command.expected_current_revision_id,
                schema_id=REFERENCE_TENSILE_REPLICATE_PLAN_SCHEMA,
                schema_version=REFERENCE_TENSILE_REPLICATE_SCHEMA_VERSION,
                content=command.content,
                created_by=context.principal.id,
                change_reason=reason,
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        return ReplicateStatisticalPlanSnapshot(
            plan_id, ReplicateRevisionSnapshot(record, command.content)
        )

    def get_plan(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        plan_id: UUID,
    ) -> ReplicateStatisticalPlanSnapshot:
        _require(context, decision, Permission.STATISTICS_READ)
        return self._repository.get_plan(context=context, decision=decision, plan_id=plan_id)

    def list_plans(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        selection_revision_id: UUID,
        *,
        limit: int = 100,
    ) -> tuple[ReplicateStatisticalPlanSnapshot, ...]:
        _require(context, decision, Permission.STATISTICS_READ)
        if not 1 <= limit <= 200:
            raise ValueError("limit must be between 1 and 200")
        return self._repository.list_plans(
            context=context,
            decision=decision,
            selection_revision_id=selection_revision_id,
            limit=limit,
        )

    async def execute(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: ExecuteReferenceTensileReplicateStatistics,
    ) -> ReplicateStatisticalRun:
        _require(context, decision, Permission.STATISTICS_EXECUTE)
        reason = _reason(command.change_reason)
        plan = self._repository.get_plan_revision(
            context=context,
            decision=decision,
            plan_id=command.plan_id,
            plan_revision_id=command.plan_revision_id,
        )
        selection = self._selection(context, decision, plan.content)
        if selection.revision.record.scope != plan.record.scope:
            raise StatisticsConflict("Plan and Selection revisions must share tenant scope")
        datasets = self._processed_inputs(context, decision, selection, plan.record.scope)
        members = tuple(
            ReplicateStatisticalRunMember(
                ordinal=member.ordinal,
                dataset_id=member.dataset_id,
                dataset_revision_id=member.dataset_revision_id,
                test_run_id=member.test_run_id,
                test_run_revision_id=member.test_run_revision_id,
            )
            for member in selection.revision.content.members
        )
        run = ReplicateStatisticalRun(
            id=self._id(),
            classification=DataClassification(plan.record.scope.classification),
            plan_id=command.plan_id,
            plan_revision_id=command.plan_revision_id,
            selection_id=selection.selection_id,
            selection_revision_id=selection.revision.record.revision_id,
            status=StatisticalRunStatus.EXECUTING,
            sample_count=len(members),
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
            members=members,
        )
        created = self._repository.create_run(context=context, decision=decision, run=run)
        curves = []
        try:
            for dataset in datasets:
                _, value = await self._artifacts.read_verified_bytes(
                    context,
                    decision,
                    dataset.revision.content.data_artifact_id,
                    maximum_bytes=16 * 1024 * 1024,
                )
                points = normalized_points_from_parquet(value)
                if len(points) != dataset.revision.content.point_count:
                    raise ValueError("Dataset Artifact point count mismatch")
                curves.append(points)
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
                        detail=(
                            "One or more pinned processed Dataset Artifacts could not be read."
                        ),
                    ),
                ),
            )
        distinct_runs = QcObservation(
            check_code="distinct_test_runs",
            outcome=(
                QcOutcome.PASSED
                if len({member.test_run_revision_id for member in members}) == len(members)
                else QcOutcome.FAILED
            ),
            detail=(
                "All replicate samples are backed by distinct Test Run revisions."
                if len({member.test_run_revision_id for member in members}) == len(members)
                else "Replicate members do not identify independent Test Run revisions."
            ),
        )
        grid = exact_replicate_grid_qc(tuple(curves))
        observations = (distinct_runs, grid)
        if any(item.outcome is QcOutcome.FAILED for item in observations):
            return self._repository.fail_run(
                context=context,
                decision=decision,
                run_id=created.id,
                failure_code="input_qc_failed",
                qc_observations=observations,
            )
        statistics = calculate_reference_tensile_replicate_statistics(tuple(curves))
        artifact: ArtifactRecord | None = None
        result_committed = False
        try:
            artifact = await self._artifacts.finalize_derived_bytes(
                context,
                decision,
                classification=created.classification,
                artifact_role="statistics.reference_tensile_replicate_curve",
                schema_ref=REFERENCE_TENSILE_REPLICATE_CURVE_SCHEMA,
                media_type="application/vnd.apache.parquet",
                value=reference_tensile_replicate_curve_parquet_bytes(statistics.curve),
                idempotency_key=f"statistics:{created.id}:reference-tensile-replicates",
            )
            content = ReferenceTensileReplicateResultContent(
                statistical_run_id=created.id,
                plan_id=created.plan_id,
                plan_revision_id=created.plan_revision_id,
                selection_id=created.selection_id,
                selection_revision_id=created.selection_revision_id,
                curve_artifact_id=artifact.artifact.id,
                curve_sha256=artifact.artifact.sha256,
                curve_point_count=len(statistics.curve),
                peak_engineering_stress_pa=statistics.peak_engineering_stress_pa,
            )
            result = self._register_result(context, decision, content, reason)
            result_committed = True
            return self._repository.succeed_run(
                context=context,
                decision=decision,
                run_id=created.id,
                result=result,
                qc_observations=observations,
            )
        except Exception as error:
            if result_committed:
                raise StatisticsConflict(
                    "Result committed but Run terminal state requires reconciliation"
                ) from error
            self._repository.fail_run(
                context=context,
                decision=decision,
                run_id=created.id,
                failure_code="statistics_command_failed",
                qc_observations=observations,
            )
            raise

    def get_run(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
    ) -> ReplicateStatisticalRun:
        _require(context, decision, Permission.STATISTICS_READ)
        return self._repository.get_run(context=context, decision=decision, run_id=run_id)

    def get_result(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        result_id: UUID,
    ) -> ReplicateStatisticalResultSnapshot:
        _require(context, decision, Permission.STATISTICS_READ)
        return self._repository.get_result(context=context, decision=decision, result_id=result_id)

    async def preview_result_curve(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        result_id: UUID,
        *,
        maximum_points: int,
    ) -> tuple[ReplicateCurvePoint, ...]:
        _require(context, decision, Permission.STATISTICS_READ)
        if not 2 <= maximum_points <= 10_000:
            raise ValueError("preview point limit must be between 2 and 10000")
        result = self._repository.get_result(
            context=context, decision=decision, result_id=result_id
        )
        _, data = await self._artifacts.read_verified_bytes(
            context,
            decision,
            result.current.content.curve_artifact_id,
            maximum_bytes=32 * 1024 * 1024,
        )
        curve = reference_tensile_replicate_curve_from_parquet(data)
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

    def _register_result(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        content: ReferenceTensileReplicateResultContent,
        reason: str,
    ) -> ReplicateStatisticalResultSnapshot:
        result_id = self._result_id(context, content.statistical_run_id)
        service = RevisionService(
            aggregate_type=REPLICATE_STATISTICAL_RESULT_AGGREGATE_TYPE,
            store=self._repository.result_store(context, decision),
        )
        scope = self._repository.get_run(
            context=context, decision=decision, run_id=content.statistical_run_id
        ).classification.value
        try:
            record = service.create(
                CreateRevisionedAggregate(
                    aggregate_id=result_id,
                    scope=TenantScope(context.organization_id, context.project_id, scope),
                    schema_id=REFERENCE_TENSILE_REPLICATE_RESULT_SCHEMA,
                    schema_version=REFERENCE_TENSILE_REPLICATE_SCHEMA_VERSION,
                    content=content,
                    created_by=context.principal.id,
                    change_reason=reason,
                    request_id=context.request_id,
                    trace_id=context.trace_id,
                )
            )
        except AggregateAlreadyExists as error:
            existing = self._repository.get_result(
                context=context, decision=decision, result_id=result_id
            )
            if existing.current.content != content:
                raise StatisticsConflict(
                    "Result identity already names different immutable output"
                ) from error
            return existing
        return ReplicateStatisticalResultSnapshot(
            result_id, ReplicateRevisionSnapshot(record, content)
        )

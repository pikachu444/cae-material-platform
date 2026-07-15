"""Persisted human-in-the-loop outlier review for one replicate Statistics result."""

from __future__ import annotations

import statistics as py_statistics
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from cmp.modules.artifacts.application.content import ArtifactService
from cmp.modules.datasets.application.service import DatasetService
from cmp.modules.datasets.domain.reference_tensile import normalized_points_from_parquet
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
    Permission,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.statistics.application.replicate_service import (
    ReplicateRevisionSnapshot,
    ReplicateStatisticsRepository,
)
from cmp.modules.statistics.domain.reference_tensile_pair import StatisticsConflict
from cmp.modules.statistics.domain.reference_tensile_replicate_outlier import (
    REFERENCE_CALIBRATION_INPUT_SCOPE_SCHEMA,
    REFERENCE_REPLICATE_OUTLIER_ASSESSMENT_SCHEMA,
    REFERENCE_REPLICATE_OUTLIER_PLAN_SCHEMA,
    REFERENCE_REPLICATE_OUTLIER_SCHEMA_VERSION,
    CalibrationInputScopeMember,
    CalibrationScopeDisposition,
    ReferenceCalibrationInputScopeContent,
    ReferenceReplicateOutlierAssessmentContent,
    ReferenceReplicateOutlierCandidate,
    ReferenceReplicateOutlierPlanContent,
    ReplicateOutlierAssessmentDecision,
    ReplicateOutlierMemberEvidence,
    reference_replicate_review_candidates,
)
from cmp.shared.application.revisions import (
    CreateRevisionedAggregate,
    RevisionService,
    RevisionStore,
)
from cmp.shared.domain.revisions import TenantScope

OUTLIER_PLAN_AGGREGATE_TYPE = "statistics.replicate_outlier_detection_plan"
OUTLIER_ASSESSMENT_AGGREGATE_TYPE = "statistics.replicate_outlier_assessment"
CALIBRATION_INPUT_SCOPE_AGGREGATE_TYPE = "statistics.calibration_input_scope"


@dataclass(frozen=True, slots=True)
class ReplicateOutlierPlanSnapshot:
    id: UUID
    current: ReplicateRevisionSnapshot[ReferenceReplicateOutlierPlanContent]


@dataclass(frozen=True, slots=True)
class ReplicateOutlierAssessmentSnapshot:
    id: UUID
    current: ReplicateRevisionSnapshot[ReferenceReplicateOutlierAssessmentContent]


@dataclass(frozen=True, slots=True)
class CalibrationInputScopeSnapshot:
    id: UUID
    current: ReplicateRevisionSnapshot[ReferenceCalibrationInputScopeContent]


@dataclass(frozen=True, slots=True)
class ReplicateOutlierDetectionRun:
    id: UUID
    classification: DataClassification
    detection_plan_id: UUID
    detection_plan_revision_id: UUID
    statistical_result_id: UUID
    statistical_result_revision_id: UUID
    statistical_plan_id: UUID
    statistical_plan_revision_id: UUID
    selection_id: UUID
    selection_revision_id: UUID
    sample_count: int
    sample_median_peak_stress_pa: float
    sample_mad_peak_stress_pa: float
    candidate_count: int
    started_at: datetime
    ended_at: datetime
    created_by: UUID
    request_id: UUID
    trace_id: str
    candidates: tuple[ReferenceReplicateOutlierCandidate, ...]


@dataclass(frozen=True, slots=True)
class CreateReplicateOutlierPlan:
    classification: DataClassification
    content: ReferenceReplicateOutlierPlanContent
    change_reason: str


@dataclass(frozen=True, slots=True)
class ExecuteReplicateOutlierDetection:
    detection_plan_id: UUID
    detection_plan_revision_id: UUID


@dataclass(frozen=True, slots=True)
class CreateReplicateOutlierAssessment:
    classification: DataClassification
    content: ReferenceReplicateOutlierAssessmentContent
    change_reason: str


@dataclass(frozen=True, slots=True)
class CreateCalibrationInputScope:
    classification: DataClassification
    scope_label: str
    detection_run_id: UUID
    assessment_revision_ids: tuple[UUID, ...]
    change_reason: str


class ReplicateOutlierRepository(Protocol):
    def plan_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[ReferenceReplicateOutlierPlanContent]: ...

    def assessment_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[ReferenceReplicateOutlierAssessmentContent]: ...

    def scope_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[ReferenceCalibrationInputScopeContent]: ...

    def get_plan_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        plan_id: UUID,
        plan_revision_id: UUID,
    ) -> ReplicateRevisionSnapshot[ReferenceReplicateOutlierPlanContent]: ...

    def list_plans(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        statistical_result_revision_id: UUID,
    ) -> tuple[ReplicateOutlierPlanSnapshot, ...]: ...

    def create_detection_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run: ReplicateOutlierDetectionRun,
    ) -> ReplicateOutlierDetectionRun: ...

    def get_detection_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
    ) -> ReplicateOutlierDetectionRun: ...

    def get_candidate(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        candidate_id: UUID,
    ) -> ReferenceReplicateOutlierCandidate: ...

    def get_assessment_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        assessment_revision_id: UUID,
    ) -> ReplicateOutlierAssessmentSnapshot: ...

    def list_assessments(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        candidate_id: UUID,
    ) -> tuple[ReplicateOutlierAssessmentSnapshot, ...]: ...

    def get_scope(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        scope_id: UUID,
    ) -> CalibrationInputScopeSnapshot: ...

    def get_scope_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        scope_id: UUID,
        scope_revision_id: UUID,
    ) -> CalibrationInputScopeSnapshot: ...

    def list_scopes(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        statistical_result_revision_id: UUID,
    ) -> tuple[CalibrationInputScopeSnapshot, ...]: ...


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
        raise StatisticsConflict("authorization decision does not match outlier request")


def _require_capability(
    context: SecurityContext,
    decision: AuthorizationDecision,
    permission: Permission,
) -> None:
    if (
        decision.principal_id != context.principal.id
        or decision.organization_id != context.organization_id
        or decision.project_id != context.project_id
        or decision.request_id != context.request_id
        or decision.trace_id != context.trace_id
        or permission.value not in decision.database_permissions
    ):
        raise StatisticsConflict("authorization decision lacks the required outlier capability")


class ReplicateOutlierService:
    """Create evidence, human decisions, and immutable calibration input scopes."""

    def __init__(
        self,
        *,
        repository: ReplicateOutlierRepository,
        statistics: ReplicateStatisticsRepository,
        datasets: DatasetService,
        artifacts: ArtifactService,
        id_factory: Callable[[], UUID] = uuid4,
    ) -> None:
        self._repository = repository
        self._statistics = statistics
        self._datasets = datasets
        self._artifacts = artifacts
        self._id_factory = id_factory

    def _id(self) -> UUID:
        value = self._id_factory()
        if value.int == 0:
            raise RuntimeError("outlier id_factory returned a zero UUID")
        return value

    @staticmethod
    def _scope(context: SecurityContext, classification: DataClassification) -> TenantScope:
        return TenantScope(
            context.organization_id, context.project_id, classification.value
        )

    def create_plan(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CreateReplicateOutlierPlan,
    ) -> ReplicateOutlierPlanSnapshot:
        _require(context, decision, Permission.STATISTICS_EXECUTE)
        reason = _reason(command.change_reason)
        result = self._statistics.get_result(
            context=context,
            decision=decision,
            result_id=command.content.statistical_result_id,
        )
        if result.current.record.revision_id != command.content.statistical_result_revision_id:
            raise StatisticsConflict("outlier Plan must pin the exact Statistics Result revision")
        scope = self._scope(context, command.classification)
        if result.current.record.scope != scope:
            raise StatisticsConflict("outlier Plan and Statistics Result must share tenant scope")
        if result.current.content.peak_engineering_stress_pa.sample_count < 3:
            raise StatisticsConflict("multi-replicate outlier review requires at least 3 members")
        plan_id = self._id()
        record = RevisionService(
            aggregate_type=OUTLIER_PLAN_AGGREGATE_TYPE,
            store=self._repository.plan_store(context, decision),
        ).create(
            CreateRevisionedAggregate(
                aggregate_id=plan_id,
                scope=scope,
                schema_id=REFERENCE_REPLICATE_OUTLIER_PLAN_SCHEMA,
                schema_version=REFERENCE_REPLICATE_OUTLIER_SCHEMA_VERSION,
                content=command.content,
                created_by=context.principal.id,
                change_reason=reason,
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        return ReplicateOutlierPlanSnapshot(
            plan_id, ReplicateRevisionSnapshot(record, command.content)
        )

    def list_plans(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        statistical_result_revision_id: UUID,
    ) -> tuple[ReplicateOutlierPlanSnapshot, ...]:
        _require(context, decision, Permission.STATISTICS_READ)
        return self._repository.list_plans(
            context=context,
            decision=decision,
            statistical_result_revision_id=statistical_result_revision_id,
        )

    async def execute(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: ExecuteReplicateOutlierDetection,
    ) -> ReplicateOutlierDetectionRun:
        _require(context, decision, Permission.STATISTICS_EXECUTE)
        plan = self._repository.get_plan_revision(
            context=context,
            decision=decision,
            plan_id=command.detection_plan_id,
            plan_revision_id=command.detection_plan_revision_id,
        )
        result = self._statistics.get_result(
            context=context,
            decision=decision,
            result_id=plan.content.statistical_result_id,
        )
        if result.current.record.revision_id != plan.content.statistical_result_revision_id:
            raise StatisticsConflict("outlier Plan pins a different Statistics Result revision")
        source_run = self._statistics.get_run(
            context=context,
            decision=decision,
            run_id=result.current.content.statistical_run_id,
        )
        if (
            source_run.result_id != result.id
            or source_run.result_revision_id != result.current.record.revision_id
            or source_run.sample_count < 3
        ):
            raise StatisticsConflict("Statistics Result is not a completed multi-replicate run")
        run_id = self._id()
        evidence: list[ReplicateOutlierMemberEvidence] = []
        for member in source_run.members:
            dataset = self._datasets.get_dataset_revision_for_statistics(
                context, decision, member.dataset_revision_id
            )
            if dataset.dataset_id != member.dataset_id:
                raise StatisticsConflict("outlier member does not match its Dataset revision")
            _, value = await self._artifacts.read_verified_bytes(
                context,
                decision,
                dataset.revision.content.data_artifact_id,
                maximum_bytes=16 * 1024 * 1024,
            )
            points = normalized_points_from_parquet(value)
            if len(points) != dataset.revision.content.point_count:
                raise StatisticsConflict("outlier input Artifact point count mismatch")
            evidence.append(
                ReplicateOutlierMemberEvidence(
                    ordinal=member.ordinal,
                    dataset_id=member.dataset_id,
                    dataset_revision_id=member.dataset_revision_id,
                    test_run_id=member.test_run_id,
                    test_run_revision_id=member.test_run_revision_id,
                    peak_engineering_stress_pa=max(
                        point.engineering_stress for point in points
                    ),
                )
            )
        candidates = reference_replicate_review_candidates(
            candidate_ids=tuple(
                uuid5(
                    NAMESPACE_URL,
                    f"cmp:replicate-outlier-candidate:{run_id}:{item.dataset_revision_id}",
                )
                for item in evidence
            ),
            detection_run_id=run_id,
            detection_plan_id=command.detection_plan_id,
            detection_plan_revision_id=command.detection_plan_revision_id,
            statistical_result_id=result.id,
            statistical_result_revision_id=result.current.record.revision_id,
            statistical_plan_id=result.current.content.plan_id,
            statistical_plan_revision_id=result.current.content.plan_revision_id,
            selection_id=result.current.content.selection_id,
            selection_revision_id=result.current.content.selection_revision_id,
            members=tuple(evidence),
            absolute_modified_z_threshold=plan.content.absolute_modified_z_threshold,
        )
        peaks = tuple(item.peak_engineering_stress_pa for item in evidence)
        started = datetime.now(UTC)
        median = py_statistics.median(peaks)
        run = ReplicateOutlierDetectionRun(
            id=run_id,
            classification=DataClassification(plan.record.scope.classification),
            detection_plan_id=command.detection_plan_id,
            detection_plan_revision_id=command.detection_plan_revision_id,
            statistical_result_id=result.id,
            statistical_result_revision_id=result.current.record.revision_id,
            statistical_plan_id=result.current.content.plan_id,
            statistical_plan_revision_id=result.current.content.plan_revision_id,
            selection_id=result.current.content.selection_id,
            selection_revision_id=result.current.content.selection_revision_id,
            sample_count=len(evidence),
            sample_median_peak_stress_pa=float(median),
            sample_mad_peak_stress_pa=float(
                py_statistics.median(tuple(abs(value - median) for value in peaks))
            ),
            candidate_count=len(candidates),
            started_at=started,
            ended_at=datetime.now(UTC),
            created_by=context.principal.id,
            request_id=context.request_id,
            trace_id=context.trace_id,
            candidates=candidates,
        )
        return self._repository.create_detection_run(
            context=context, decision=decision, run=run
        )

    def get_detection_run(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
    ) -> ReplicateOutlierDetectionRun:
        _require(context, decision, Permission.STATISTICS_READ)
        return self._repository.get_detection_run(
            context=context, decision=decision, run_id=run_id
        )

    def create_assessment(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CreateReplicateOutlierAssessment,
    ) -> ReplicateOutlierAssessmentSnapshot:
        _require(context, decision, Permission.STATISTICS_EXECUTE)
        reason = _reason(command.change_reason)
        candidate = self._repository.get_candidate(
            context=context, decision=decision, candidate_id=command.content.candidate_id
        )
        if (
            candidate.detection_plan_id != command.content.detection_plan_id
            or candidate.detection_plan_revision_id
            != command.content.detection_plan_revision_id
        ):
            raise StatisticsConflict("assessment does not pin the candidate detector revision")
        assessment_id = self._id()
        record = RevisionService(
            aggregate_type=OUTLIER_ASSESSMENT_AGGREGATE_TYPE,
            store=self._repository.assessment_store(context, decision),
        ).create(
            CreateRevisionedAggregate(
                aggregate_id=assessment_id,
                scope=self._scope(context, command.classification),
                schema_id=REFERENCE_REPLICATE_OUTLIER_ASSESSMENT_SCHEMA,
                schema_version=REFERENCE_REPLICATE_OUTLIER_SCHEMA_VERSION,
                content=command.content,
                created_by=context.principal.id,
                change_reason=reason,
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        return ReplicateOutlierAssessmentSnapshot(
            assessment_id, ReplicateRevisionSnapshot(record, command.content)
        )

    def list_assessments(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        candidate_id: UUID,
    ) -> tuple[ReplicateOutlierAssessmentSnapshot, ...]:
        _require(context, decision, Permission.STATISTICS_READ)
        return self._repository.list_assessments(
            context=context, decision=decision, candidate_id=candidate_id
        )

    def create_scope(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CreateCalibrationInputScope,
    ) -> CalibrationInputScopeSnapshot:
        _require(context, decision, Permission.STATISTICS_EXECUTE)
        reason = _reason(command.change_reason)
        run = self._repository.get_detection_run(
            context=context, decision=decision, run_id=command.detection_run_id
        )
        if len(set(command.assessment_revision_ids)) != len(command.assessment_revision_ids):
            raise StatisticsConflict("calibration scope assessment revisions must be unique")
        assessments = tuple(
            self._repository.get_assessment_revision(
                context=context, decision=decision, assessment_revision_id=revision_id
            )
            for revision_id in command.assessment_revision_ids
        )
        by_candidate = {item.current.content.candidate_id: item for item in assessments}
        if (
            len(assessments) != len(run.candidates)
            or len(by_candidate) != len(run.candidates)
            or set(by_candidate) != {item.id for item in run.candidates}
        ):
            raise StatisticsConflict("scope requires one explicit assessment per candidate")
        candidates = {item.member.dataset_revision_id: item for item in run.candidates}
        members: list[CalibrationInputScopeMember] = []
        source_run = self._statistics.get_run(
            context=context,
            decision=decision,
            run_id=self._statistics.get_result(
                context=context, decision=decision, result_id=run.statistical_result_id
            ).current.content.statistical_run_id,
        )
        for source in source_run.members:
            candidate = candidates.get(source.dataset_revision_id)
            if candidate is None:
                disposition = CalibrationScopeDisposition.INCLUDED
                assessment_id = assessment_revision_id = None
            else:
                assessment = by_candidate[candidate.id]
                if (
                    assessment.current.content.detection_plan_id != run.detection_plan_id
                    or assessment.current.content.detection_plan_revision_id
                    != run.detection_plan_revision_id
                ):
                    raise StatisticsConflict("scope assessment pins another detector revision")
                disposition = (
                    CalibrationScopeDisposition.EXCLUDED
                    if assessment.current.content.decision
                    is ReplicateOutlierAssessmentDecision.EXCLUDED_FROM_CALIBRATION
                    else CalibrationScopeDisposition.INCLUDED
                )
                assessment_id = assessment.id
                assessment_revision_id = assessment.current.record.revision_id
            members.append(
                CalibrationInputScopeMember(
                    ordinal=source.ordinal,
                    dataset_id=source.dataset_id,
                    dataset_revision_id=source.dataset_revision_id,
                    test_run_id=source.test_run_id,
                    test_run_revision_id=source.test_run_revision_id,
                    disposition=disposition,
                    candidate_id=candidate.id if candidate else None,
                    assessment_id=assessment_id,
                    assessment_revision_id=assessment_revision_id,
                )
            )
        content = ReferenceCalibrationInputScopeContent(
            scope_label=command.scope_label,
            source_selection_id=run.selection_id,
            source_selection_revision_id=run.selection_revision_id,
            statistical_result_id=run.statistical_result_id,
            statistical_result_revision_id=run.statistical_result_revision_id,
            detection_plan_id=run.detection_plan_id,
            detection_plan_revision_id=run.detection_plan_revision_id,
            members=tuple(members),
        )
        scope_id = self._id()
        record = RevisionService(
            aggregate_type=CALIBRATION_INPUT_SCOPE_AGGREGATE_TYPE,
            store=self._repository.scope_store(context, decision),
        ).create(
            CreateRevisionedAggregate(
                aggregate_id=scope_id,
                scope=self._scope(context, command.classification),
                schema_id=REFERENCE_CALIBRATION_INPUT_SCOPE_SCHEMA,
                schema_version=REFERENCE_REPLICATE_OUTLIER_SCHEMA_VERSION,
                content=content,
                created_by=context.principal.id,
                change_reason=reason,
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        return CalibrationInputScopeSnapshot(
            scope_id, ReplicateRevisionSnapshot(record, content)
        )

    def get_scope(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        scope_id: UUID,
    ) -> CalibrationInputScopeSnapshot:
        _require(context, decision, Permission.STATISTICS_READ)
        return self._repository.get_scope(
            context=context, decision=decision, scope_id=scope_id
        )

    def get_scope_revision_for_calibration(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        scope_id: UUID,
        scope_revision_id: UUID,
    ) -> CalibrationInputScopeSnapshot:
        """Resolve one exact reviewed Scope through the Statistics application boundary."""

        _require_capability(context, decision, Permission.STATISTICS_READ)
        return self._repository.get_scope_revision(
            context=context,
            decision=decision,
            scope_id=scope_id,
            scope_revision_id=scope_revision_id,
        )

    def list_scopes(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        statistical_result_revision_id: UUID,
    ) -> tuple[CalibrationInputScopeSnapshot, ...]:
        _require(context, decision, Permission.STATISTICS_READ)
        return self._repository.list_scopes(
            context=context,
            decision=decision,
            statistical_result_revision_id=statistical_result_revision_id,
        )

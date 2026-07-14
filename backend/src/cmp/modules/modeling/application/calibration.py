"""Reference Calibration Plan/Run/Attempt orchestration.

This module owns the T-23 execution records.  It obtains Dataset and Material Model inputs only
through their public application services, never through another bounded context's persistence
adapter.  The numerical evaluator is deliberately a narrow, deterministic reference capability;
it does not represent a production-approved constitutive model or optimizer choice.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID, uuid4

from cmp.modules.artifacts.application.content import ArtifactService
from cmp.modules.datasets.application.service import (
    CalibrationDatasetSource,
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
from cmp.modules.modeling.application.service import (
    MaterialModelService,
    RevisionSnapshot,
)
from cmp.modules.modeling.domain.reference_linear_elastic_calibration import (
    REFERENCE_CALIBRATION_ENVIRONMENT_DIGEST,
    REFERENCE_LINEAR_ELASTIC_CALIBRATION_SCHEMA_ID,
    REFERENCE_LINEAR_ELASTIC_CALIBRATION_SCHEMA_VERSION,
    REFERENCE_LINEAR_ELASTIC_DIAGNOSTICS_SCHEMA,
    CalibrationCandidateStatus,
    CalibrationConflict,
    CalibrationCurvePoint,
    CalibrationError,
    InvalidCalibrationPlan,
    ReferenceLinearElasticCalibrationPlanContent,
    calibrate_reference_linear_elastic_curve,
    calibration_candidate_content_hash,
    reference_calibration_diagnostics_from_parquet,
    reference_calibration_diagnostics_parquet_bytes,
)
from cmp.modules.modeling.domain.reference_linear_elastic_calibration import (
    CalibrationAttemptStatus as CalibrationAttemptStatus,
)
from cmp.modules.modeling.domain.reference_linear_elastic_calibration import (
    CalibrationRunStatus as CalibrationRunStatus,
)
from cmp.shared.application.revisions import (
    CreateRevisionedAggregate,
    ReviseAggregate,
    RevisionService,
    RevisionStore,
)
from cmp.shared.domain.revisions import TenantScope

CALIBRATION_PLAN_AGGREGATE_TYPE = "modeling.calibration_plan"
CALIBRATION_PLAN_SCHEMA_ID = REFERENCE_LINEAR_ELASTIC_CALIBRATION_SCHEMA_ID


@dataclass(frozen=True, slots=True)
class CalibrationPlanSnapshot:
    id: UUID
    current: RevisionSnapshot[ReferenceLinearElasticCalibrationPlanContent]


@dataclass(frozen=True, slots=True)
class CalibrationRun:
    id: UUID
    classification: DataClassification
    plan_id: UUID
    plan_revision_id: UUID
    selection_id: UUID
    selection_revision_id: UUID
    dataset_id: UUID
    dataset_revision_id: UUID
    material_model_id: UUID
    material_model_revision_id: UUID
    execution_mode: str
    reproducibility_level: str
    environment_digest: str
    status: CalibrationRunStatus
    attempt_count: int
    candidate_count: int
    failure_code: str | None
    change_reason: str
    started_at: datetime
    ended_at: datetime | None
    created_by: UUID
    request_id: UUID
    trace_id: str


@dataclass(frozen=True, slots=True)
class CalibrationAttempt:
    id: UUID
    calibration_run_id: UUID
    attempt_ordinal: int
    initial_youngs_modulus_pa: float
    random_seed: int
    status: CalibrationAttemptStatus
    candidate_id: UUID | None
    failure_code: str | None
    started_at: datetime
    ended_at: datetime | None


@dataclass(frozen=True, slots=True)
class CalibrationCandidate:
    id: UUID
    calibration_run_id: UUID
    calibration_attempt_id: UUID
    attempt_ordinal: int
    status: CalibrationCandidateStatus
    candidate_sha256: str
    youngs_modulus_pa: float
    objective_total: float
    residual_root_mean_square_pa: float
    residual_mean_pa: float
    bound_sticking: bool
    convergence_reason: str
    identifiability_status: str
    uncertainty_status: str
    diagnostics_artifact_id: UUID
    diagnostics_sha256: str
    diagnostics_point_count: int
    created_at: datetime
    created_by: UUID


@dataclass(frozen=True, slots=True)
class CalibrationRunDetail:
    run: CalibrationRun
    attempts: tuple[CalibrationAttempt, ...]
    candidates: tuple[CalibrationCandidate, ...]


@dataclass(frozen=True, slots=True)
class CalibrationDiagnosticPreview:
    calibration_candidate_id: UUID
    point_count: int
    returned_point_count: int
    sampled: bool
    points: tuple[CalibrationCurvePoint, ...]


@dataclass(frozen=True, slots=True)
class CreateReferenceLinearElasticCalibrationPlan:
    classification: DataClassification
    content: ReferenceLinearElasticCalibrationPlanContent
    change_reason: str


@dataclass(frozen=True, slots=True)
class ReviseReferenceLinearElasticCalibrationPlan:
    expected_current_revision_id: UUID
    content: ReferenceLinearElasticCalibrationPlanContent
    change_reason: str


@dataclass(frozen=True, slots=True)
class ExecuteReferenceLinearElasticCalibration:
    plan_id: UUID
    plan_revision_id: UUID
    change_reason: str


class CalibrationRepository(Protocol):
    def plan_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[ReferenceLinearElasticCalibrationPlanContent]: ...

    def get_plan(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        plan_id: UUID,
    ) -> CalibrationPlanSnapshot: ...

    def get_plan_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        plan_id: UUID,
        plan_revision_id: UUID,
    ) -> RevisionSnapshot[ReferenceLinearElasticCalibrationPlanContent]: ...

    def list_plans(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        limit: int,
    ) -> tuple[CalibrationPlanSnapshot, ...]: ...

    def create_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run: CalibrationRun,
    ) -> CalibrationRun: ...

    def create_attempt(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        attempt: CalibrationAttempt,
    ) -> CalibrationAttempt: ...

    def succeed_attempt(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        attempt_id: UUID,
        candidate_id: UUID,
    ) -> CalibrationAttempt: ...

    def fail_attempt(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        attempt_id: UUID,
        failure_code: str,
    ) -> CalibrationAttempt: ...

    def create_candidate(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        candidate: CalibrationCandidate,
    ) -> CalibrationCandidate: ...

    def succeed_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
        candidate_count: int,
    ) -> CalibrationRun: ...

    def fail_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
        failure_code: str,
    ) -> CalibrationRun: ...

    def get_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
    ) -> CalibrationRun: ...

    def list_attempts(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
    ) -> tuple[CalibrationAttempt, ...]: ...

    def list_candidates(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
    ) -> tuple[CalibrationCandidate, ...]: ...

    def get_candidate(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        candidate_id: UUID,
    ) -> CalibrationCandidate: ...


def _reason(value: str) -> str:
    if not value or value != value.strip() or len(value) > 2000 or "\x00" in value:
        raise InvalidCalibrationPlan("change_reason must be trimmed and contain 1..2000 characters")
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
        raise CalibrationConflict("authorization decision does not match Calibration request")


class ReferenceCalibrationService:
    """Execute explicit one-curve reference calibrations without mutable input aliases."""

    def __init__(
        self,
        *,
        repository: CalibrationRepository,
        datasets: DatasetService,
        material_models: MaterialModelService,
        artifacts: ArtifactService,
        id_factory: Callable[[], UUID] = uuid4,
    ) -> None:
        self._repository = repository
        self._datasets = datasets
        self._material_models = material_models
        self._artifacts = artifacts
        self._id_factory = id_factory

    def _id(self) -> UUID:
        value = self._id_factory()
        if value.int == 0:
            raise RuntimeError("calibration id_factory returned a zero UUID")
        return value

    def _inputs(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        content: ReferenceLinearElasticCalibrationPlanContent,
    ) -> tuple[DatasetSelectionRevisionSnapshot, CalibrationDatasetSource]:
        selection = self._datasets.get_reference_dataset_selection_revision_for_calibration(
            context,
            decision,
            content.selection_id,
            content.selection_revision_id,
        )
        dataset_source = self._datasets.get_calibration_dataset_source(
            context,
            decision,
            selection.revision.content.dataset_revision_id,
        )
        model = self._material_models.get_material_model_revision_for_calibration(
            context,
            decision,
            content.material_model_id,
            content.material_model_revision_id,
        )
        if selection.revision.content.dataset_id != dataset_source.dataset.dataset_id:
            raise CalibrationConflict(
                "Selection Dataset identity does not match its pinned revision"
            )
        if dataset_source.dataset.revision.record.scope != selection.revision.record.scope:
            raise CalibrationConflict("Selection and Dataset revisions must share tenant scope")
        if model.record.scope != selection.revision.record.scope:
            raise CalibrationConflict(
                "Material Model and Dataset Selection must share tenant scope"
            )
        if dataset_source.material_state_id != model.content.material_state_id:
            raise CalibrationConflict(
                "reference calibration Dataset specimen belongs to another Material State"
            )
        if dataset_source.dataset.revision.content.representation not in (
            DatasetRepresentation.NORMALIZED,
            DatasetRepresentation.PROCESSED,
        ):
            raise CalibrationConflict(
                "reference calibration accepts only normalized or processed tensile Dataset "
                "revisions"
            )
        return selection, dataset_source

    def create_plan(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CreateReferenceLinearElasticCalibrationPlan,
    ) -> CalibrationPlanSnapshot:
        _require(context, decision, Permission.CALIBRATION_EXECUTE)
        reason = _reason(command.change_reason)
        selection, _ = self._inputs(context, decision, command.content)
        scope = TenantScope(
            context.organization_id,
            context.project_id,
            command.classification.value,
        )
        if selection.revision.record.scope != scope:
            raise CalibrationConflict("Plan classification must match the pinned Dataset Selection")
        plan_id = self._id()
        record = RevisionService(
            aggregate_type=CALIBRATION_PLAN_AGGREGATE_TYPE,
            store=self._repository.plan_store(context, decision),
        ).create(
            CreateRevisionedAggregate(
                aggregate_id=plan_id,
                scope=scope,
                schema_id=CALIBRATION_PLAN_SCHEMA_ID,
                schema_version=REFERENCE_LINEAR_ELASTIC_CALIBRATION_SCHEMA_VERSION,
                content=command.content,
                created_by=context.principal.id,
                change_reason=reason,
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        return CalibrationPlanSnapshot(plan_id, RevisionSnapshot(record, command.content))

    def revise_plan(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        plan_id: UUID,
        command: ReviseReferenceLinearElasticCalibrationPlan,
    ) -> CalibrationPlanSnapshot:
        _require(context, decision, Permission.CALIBRATION_EXECUTE)
        reason = _reason(command.change_reason)
        existing = self._repository.get_plan(context=context, decision=decision, plan_id=plan_id)
        if command.content.plan_label != existing.current.content.plan_label:
            raise CalibrationConflict(
                "Calibration Plan label is a stable identity and cannot change"
            )
        selection, _ = self._inputs(context, decision, command.content)
        if selection.revision.record.scope != existing.current.record.scope:
            raise CalibrationConflict(
                "Plan Selection revision is outside the stable Plan tenant scope"
            )
        record = RevisionService(
            aggregate_type=CALIBRATION_PLAN_AGGREGATE_TYPE,
            store=self._repository.plan_store(context, decision),
        ).revise(
            ReviseAggregate(
                aggregate_id=plan_id,
                scope=existing.current.record.scope,
                expected_current_revision_id=command.expected_current_revision_id,
                based_on_revision_id=command.expected_current_revision_id,
                schema_id=CALIBRATION_PLAN_SCHEMA_ID,
                schema_version=REFERENCE_LINEAR_ELASTIC_CALIBRATION_SCHEMA_VERSION,
                content=command.content,
                created_by=context.principal.id,
                change_reason=reason,
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        return CalibrationPlanSnapshot(plan_id, RevisionSnapshot(record, command.content))

    def get_plan(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        plan_id: UUID,
    ) -> CalibrationPlanSnapshot:
        _require(context, decision, Permission.MODELING_READ)
        return self._repository.get_plan(context=context, decision=decision, plan_id=plan_id)

    def list_plans(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        *,
        limit: int = 100,
    ) -> tuple[CalibrationPlanSnapshot, ...]:
        _require(context, decision, Permission.MODELING_READ)
        if not 1 <= limit <= 200:
            raise InvalidCalibrationPlan("limit must be between 1 and 200")
        return self._repository.list_plans(context=context, decision=decision, limit=limit)

    async def execute(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: ExecuteReferenceLinearElasticCalibration,
    ) -> CalibrationRunDetail:
        """Persist the run before computation and retain every completed attempt/candidate."""

        _require(context, decision, Permission.CALIBRATION_EXECUTE)
        reason = _reason(command.change_reason)
        plan = self._repository.get_plan_revision(
            context=context,
            decision=decision,
            plan_id=command.plan_id,
            plan_revision_id=command.plan_revision_id,
        )
        selection, dataset_source = self._inputs(context, decision, plan.content)
        if selection.revision.record.scope != plan.record.scope:
            raise CalibrationConflict(
                "Calibration Plan and pinned Selection must share tenant scope"
            )
        dataset = dataset_source.dataset
        run = CalibrationRun(
            id=self._id(),
            classification=DataClassification(plan.record.scope.classification),
            plan_id=command.plan_id,
            plan_revision_id=command.plan_revision_id,
            selection_id=selection.selection_id,
            selection_revision_id=selection.revision.record.revision_id,
            dataset_id=dataset.dataset_id,
            dataset_revision_id=dataset.revision.record.revision_id,
            material_model_id=plan.content.material_model_id,
            material_model_revision_id=plan.content.material_model_revision_id,
            execution_mode="reference_inline",
            reproducibility_level="R3",
            environment_digest=REFERENCE_CALIBRATION_ENVIRONMENT_DIGEST,
            status=CalibrationRunStatus.EXECUTING,
            attempt_count=plan.content.multistart_count,
            candidate_count=0,
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
            _, input_bytes = await self._artifacts.read_verified_bytes(
                context,
                decision,
                dataset.revision.content.data_artifact_id,
                maximum_bytes=16 * 1024 * 1024,
            )
            input_points = normalized_points_from_parquet(input_bytes)
            if len(input_points) != dataset.revision.content.point_count:
                raise InvalidCalibrationPlan(
                    "input Dataset Artifact point count differs from its immutable revision"
                )
        except Exception:
            failed = self._repository.fail_run(
                context=context,
                decision=decision,
                run_id=created.id,
                failure_code="input_artifact_unreadable",
            )
            return CalibrationRunDetail(failed, (), ())

        candidate_count = 0
        try:
            for ordinal in range(1, plan.content.multistart_count + 1):
                outcome = calibrate_reference_linear_elastic_curve(
                    plan.content,
                    tuple(
                        (point.engineering_strain, point.engineering_stress)
                        for point in input_points
                    ),
                    attempt_ordinal=ordinal,
                )
                attempt = self._repository.create_attempt(
                    context=context,
                    decision=decision,
                    attempt=CalibrationAttempt(
                        id=self._id(),
                        calibration_run_id=created.id,
                        attempt_ordinal=ordinal,
                        initial_youngs_modulus_pa=outcome.initial_youngs_modulus_pa,
                        random_seed=plan.content.random_seed,
                        status=CalibrationAttemptStatus.EXECUTING,
                        candidate_id=None,
                        failure_code=None,
                        started_at=datetime.now(UTC),
                        ended_at=None,
                    ),
                )
                try:
                    diagnostics = await self._artifacts.finalize_derived_bytes(
                        context,
                        decision,
                        classification=created.classification,
                        artifact_role="modeling.reference_linear_elastic_calibration_diagnostics",
                        schema_ref=REFERENCE_LINEAR_ELASTIC_DIAGNOSTICS_SCHEMA,
                        media_type="application/vnd.apache.parquet",
                        value=reference_calibration_diagnostics_parquet_bytes(outcome.curve),
                        idempotency_key=(
                            f"calibration:{created.id}:reference-linear-elastic:{ordinal}"
                        ),
                    )
                    candidate = self._repository.create_candidate(
                        context=context,
                        decision=decision,
                        candidate=CalibrationCandidate(
                            id=self._id(),
                            calibration_run_id=created.id,
                            calibration_attempt_id=attempt.id,
                            attempt_ordinal=ordinal,
                            status=CalibrationCandidateStatus.CONVERGED,
                            candidate_sha256=calibration_candidate_content_hash(
                                calibration_run_id=created.id,
                                attempt_ordinal=ordinal,
                                calibrated_youngs_modulus_pa=outcome.calibrated_youngs_modulus_pa,
                                objective_total=outcome.objective_total,
                                diagnostics_sha256=diagnostics.artifact.sha256,
                            ),
                            youngs_modulus_pa=outcome.calibrated_youngs_modulus_pa,
                            objective_total=outcome.objective_total,
                            residual_root_mean_square_pa=outcome.residual_root_mean_square_pa,
                            residual_mean_pa=outcome.residual_mean_pa,
                            bound_sticking=outcome.bound_sticking,
                            convergence_reason=outcome.convergence_reason,
                            identifiability_status=outcome.identifiability_status,
                            uncertainty_status=outcome.uncertainty_status,
                            diagnostics_artifact_id=diagnostics.artifact.id,
                            diagnostics_sha256=diagnostics.artifact.sha256,
                            diagnostics_point_count=len(outcome.curve),
                            created_at=datetime.now(UTC),
                            created_by=context.principal.id,
                        ),
                    )
                    self._repository.succeed_attempt(
                        context=context,
                        decision=decision,
                        attempt_id=attempt.id,
                        candidate_id=candidate.id,
                    )
                    candidate_count += 1
                except Exception:
                    self._repository.fail_attempt(
                        context=context,
                        decision=decision,
                        attempt_id=attempt.id,
                        failure_code="candidate_persistence_failed",
                    )
                    raise
            succeeded = self._repository.succeed_run(
                context=context,
                decision=decision,
                run_id=created.id,
                candidate_count=candidate_count,
            )
            return CalibrationRunDetail(
                succeeded,
                self._repository.list_attempts(
                    context=context, decision=decision, run_id=created.id
                ),
                self._repository.list_candidates(
                    context=context, decision=decision, run_id=created.id
                ),
            )
        except Exception as error:
            try:
                failed = self._repository.fail_run(
                    context=context,
                    decision=decision,
                    run_id=created.id,
                    failure_code="reference_calibration_failed",
                )
            except Exception as terminal_error:
                raise CalibrationConflict(
                    "Calibration output exists but the durable Run terminal state requires "
                    "reconciliation"
                ) from terminal_error
            if isinstance(error, CalibrationError):
                return CalibrationRunDetail(
                    failed,
                    self._repository.list_attempts(
                        context=context, decision=decision, run_id=created.id
                    ),
                    self._repository.list_candidates(
                        context=context, decision=decision, run_id=created.id
                    ),
                )
            raise

    def get_run(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
    ) -> CalibrationRunDetail:
        _require(context, decision, Permission.MODELING_READ)
        return CalibrationRunDetail(
            self._repository.get_run(context=context, decision=decision, run_id=run_id),
            self._repository.list_attempts(context=context, decision=decision, run_id=run_id),
            self._repository.list_candidates(context=context, decision=decision, run_id=run_id),
        )

    async def preview_candidate_diagnostics(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        candidate_id: UUID,
        *,
        maximum_points: int,
    ) -> CalibrationDiagnosticPreview:
        _require(context, decision, Permission.MODELING_READ)
        if not 2 <= maximum_points <= 10_000:
            raise InvalidCalibrationPlan("maximum_points must be between 2 and 10000")
        candidate = self._repository.get_candidate(
            context=context, decision=decision, candidate_id=candidate_id
        )
        artifact, value = await self._artifacts.read_verified_bytes(
            context,
            decision,
            candidate.diagnostics_artifact_id,
            maximum_bytes=16 * 1024 * 1024,
        )
        if artifact.artifact.sha256 != candidate.diagnostics_sha256:
            raise CalibrationConflict(
                "Candidate diagnostics Artifact digest differs from immutable Candidate"
            )
        points = reference_calibration_diagnostics_from_parquet(value)
        if len(points) != candidate.diagnostics_point_count:
            raise CalibrationConflict(
                "Candidate diagnostics Artifact point count differs from immutable Candidate"
            )
        if len(points) <= maximum_points:
            preview = points
        else:
            indexes = {
                round(index * (len(points) - 1) / (maximum_points - 1))
                for index in range(maximum_points)
            }
            preview = tuple(points[index] for index in sorted(indexes))
        return CalibrationDiagnosticPreview(
            calibration_candidate_id=candidate.id,
            point_count=len(points),
            returned_point_count=len(preview),
            sampled=len(preview) != len(points),
            points=preview,
        )

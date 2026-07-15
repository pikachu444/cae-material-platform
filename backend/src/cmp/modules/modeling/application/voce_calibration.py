"""Durable orchestration for the bounded multi-curve reference Voce capability."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID, uuid4

from cmp.modules.artifacts.application.content import ArtifactService
from cmp.modules.catalog.application.service import CatalogService
from cmp.modules.datasets.application.service import CalibrationDatasetSource, DatasetService
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
from cmp.modules.modeling.application.service import RevisionSnapshot
from cmp.modules.modeling.domain.reference_linear_elastic_calibration import (
    CalibrationAttemptStatus,
    CalibrationCandidateStatus,
    CalibrationRunStatus,
)
from cmp.modules.modeling.domain.reference_voce_calibration import (
    REFERENCE_VOCE_DIAGNOSTICS_SCHEMA,
    REFERENCE_VOCE_ENVIRONMENT_DIGEST,
    REFERENCE_VOCE_PLAN_SCHEMA_ID,
    REFERENCE_VOCE_PLAN_SCHEMA_VERSION,
    InvalidVoceCalibration,
    ReferenceVoceCalibrationPlanContent,
    VoceDiagnosticPoint,
    VoceEngineeringCurveInput,
    VoceObjectiveTerm,
    calibrate_reference_voce_curves,
    reference_voce_candidate_content_hash,
    reference_voce_diagnostics_from_parquet,
    reference_voce_diagnostics_parquet_bytes,
    reference_voce_multistart_parameters,
)
from cmp.modules.statistics.application.replicate_outlier_service import (
    CalibrationInputScopeSnapshot,
    ReplicateOutlierService,
)
from cmp.modules.statistics.domain.reference_tensile_replicate_outlier import (
    CalibrationScopeDisposition,
)
from cmp.shared.application.revisions import (
    CreateRevisionedAggregate,
    ReviseAggregate,
    RevisionService,
    RevisionStore,
)
from cmp.shared.domain.revisions import TenantScope

VOCE_CALIBRATION_PLAN_AGGREGATE_TYPE = "modeling.voce_calibration_plan"


class VoceCalibrationConflict(Exception):
    """A scope, revision, tenant, or append-only execution invariant conflicted."""


class VoceCalibrationNotFound(Exception):
    """A persisted Voce calibration resource is not visible in the active tenant."""


@dataclass(frozen=True, slots=True)
class VoceCalibrationPlanSnapshot:
    id: UUID
    current: RevisionSnapshot[ReferenceVoceCalibrationPlanContent]


@dataclass(frozen=True, slots=True)
class VoceCalibrationRun:
    id: UUID
    classification: DataClassification
    plan_id: UUID
    plan_revision_id: UUID
    calibration_input_scope_id: UUID
    calibration_input_scope_revision_id: UUID
    property_set_id: UUID
    property_set_revision_id: UUID
    source_curve_count: int
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
class VoceCalibrationAttempt:
    id: UUID
    calibration_run_id: UUID
    attempt_ordinal: int
    initial_sigma_0_pa: float
    initial_q_pa: float
    initial_b: float
    random_seed: int
    status: CalibrationAttemptStatus
    candidate_id: UUID | None
    failure_code: str | None
    started_at: datetime
    ended_at: datetime | None


@dataclass(frozen=True, slots=True)
class VoceCalibrationCandidate:
    id: UUID
    calibration_run_id: UUID
    calibration_attempt_id: UUID
    attempt_ordinal: int
    status: CalibrationCandidateStatus
    candidate_sha256: str
    sigma_0_pa: float
    q_pa: float
    b: float
    objective_total: float
    residual_root_mean_square_pa: float
    residual_mean_pa: float
    sigma_0_at_bound: bool
    q_at_bound: bool
    b_at_bound: bool
    convergence_status_code: int
    convergence_reason: str
    function_evaluations: int
    jacobian_evaluations: int | None
    optimality: float
    warning_at_bound: bool
    warning_nonconvergence: bool
    identifiability_status: str
    uncertainty_status: str
    diagnostics_artifact_id: UUID
    diagnostics_sha256: str
    diagnostics_point_count: int
    objective_terms: tuple[VoceObjectiveTerm, ...]
    created_at: datetime
    created_by: UUID


@dataclass(frozen=True, slots=True)
class VoceCalibrationRunDetail:
    run: VoceCalibrationRun
    attempts: tuple[VoceCalibrationAttempt, ...]
    candidates: tuple[VoceCalibrationCandidate, ...]


@dataclass(frozen=True, slots=True)
class VoceCalibrationDiagnosticPreview:
    calibration_candidate_id: UUID
    point_count: int
    returned_point_count: int
    sampled: bool
    points: tuple[VoceDiagnosticPoint, ...]


@dataclass(frozen=True, slots=True)
class CreateReferenceVoceCalibrationPlan:
    classification: DataClassification
    content: ReferenceVoceCalibrationPlanContent
    change_reason: str


@dataclass(frozen=True, slots=True)
class ReviseReferenceVoceCalibrationPlan:
    expected_current_revision_id: UUID
    content: ReferenceVoceCalibrationPlanContent
    change_reason: str


@dataclass(frozen=True, slots=True)
class ExecuteReferenceVoceCalibration:
    plan_id: UUID
    plan_revision_id: UUID
    change_reason: str


class VoceCalibrationRepository(Protocol):
    def plan_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[ReferenceVoceCalibrationPlanContent]: ...

    def get_plan(
        self, *, context: SecurityContext, decision: AuthorizationDecision, plan_id: UUID
    ) -> VoceCalibrationPlanSnapshot: ...

    def get_plan_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        plan_id: UUID,
        plan_revision_id: UUID,
    ) -> RevisionSnapshot[ReferenceVoceCalibrationPlanContent]: ...

    def list_plans(
        self, *, context: SecurityContext, decision: AuthorizationDecision, limit: int
    ) -> tuple[VoceCalibrationPlanSnapshot, ...]: ...

    def create_run(
        self, *, context: SecurityContext, decision: AuthorizationDecision, run: VoceCalibrationRun
    ) -> VoceCalibrationRun: ...

    def create_attempt(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        attempt: VoceCalibrationAttempt,
    ) -> VoceCalibrationAttempt: ...

    def succeed_attempt(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        attempt_id: UUID,
        candidate_id: UUID,
    ) -> VoceCalibrationAttempt: ...

    def fail_attempt(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        attempt_id: UUID,
        failure_code: str,
    ) -> VoceCalibrationAttempt: ...

    def create_candidate(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        candidate: VoceCalibrationCandidate,
    ) -> VoceCalibrationCandidate: ...

    def succeed_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
        candidate_count: int,
    ) -> VoceCalibrationRun: ...

    def fail_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
        failure_code: str,
    ) -> VoceCalibrationRun: ...

    def get_run(
        self, *, context: SecurityContext, decision: AuthorizationDecision, run_id: UUID
    ) -> VoceCalibrationRun: ...

    def list_attempts(
        self, *, context: SecurityContext, decision: AuthorizationDecision, run_id: UUID
    ) -> tuple[VoceCalibrationAttempt, ...]: ...

    def list_candidates(
        self, *, context: SecurityContext, decision: AuthorizationDecision, run_id: UUID
    ) -> tuple[VoceCalibrationCandidate, ...]: ...

    def get_candidate(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        candidate_id: UUID,
    ) -> VoceCalibrationCandidate: ...


def _reason(value: str) -> str:
    if not value or value != value.strip() or len(value) > 2000 or "\x00" in value:
        raise InvalidVoceCalibration("change_reason must be trimmed and contain 1..2000 characters")
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
        raise VoceCalibrationConflict("authorization decision does not match Voce request")


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
        raise VoceCalibrationConflict("authorization decision lacks Voce read capability")


class ReferenceVoceCalibrationService:
    def __init__(
        self,
        *,
        repository: VoceCalibrationRepository,
        statistics: ReplicateOutlierService,
        datasets: DatasetService,
        catalog: CatalogService,
        artifacts: ArtifactService,
        id_factory: Callable[[], UUID] = uuid4,
    ) -> None:
        self._repository = repository
        self._statistics = statistics
        self._datasets = datasets
        self._catalog = catalog
        self._artifacts = artifacts
        self._id_factory = id_factory

    def _id(self) -> UUID:
        value = self._id_factory()
        if value.int == 0:
            raise RuntimeError("Voce calibration id_factory returned a zero UUID")
        return value

    def _inputs(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        content: ReferenceVoceCalibrationPlanContent,
    ) -> tuple[CalibrationInputScopeSnapshot, tuple[CalibrationDatasetSource, ...]]:
        scope = self._statistics.get_scope_revision_for_calibration(
            context,
            decision,
            content.calibration_input_scope_id,
            content.calibration_input_scope_revision_id,
        )
        properties = self._catalog.get_property_set_revision_for_calibration(
            context,
            decision,
            content.property_set_id,
            content.property_set_revision_id,
        )
        if properties.record.scope != scope.current.record.scope:
            raise VoceCalibrationConflict("Scope and Property Set revision must share tenant scope")
        if (
            properties.content.material_state_id != content.material_state_id
            or properties.content.material_state_revision_id != content.material_state_revision_id
        ):
            raise VoceCalibrationConflict("Plan Material State does not match its Property Set")
        if properties.content.youngs_modulus_pa != content.youngs_modulus_pa:
            raise VoceCalibrationConflict("Plan Young's modulus must equal the pinned Property Set")
        sources: list[CalibrationDatasetSource] = []
        for member in scope.current.content.members:
            if member.disposition is CalibrationScopeDisposition.EXCLUDED:
                continue
            source = self._datasets.get_calibration_dataset_source(
                context, decision, member.dataset_revision_id
            )
            revision = source.dataset.revision
            if (
                source.dataset.dataset_id != member.dataset_id
                or revision.record.revision_id != member.dataset_revision_id
                or revision.content.test_run_id != member.test_run_id
                or revision.content.test_run_revision_id != member.test_run_revision_id
            ):
                raise VoceCalibrationConflict("Scope member does not match Dataset lineage")
            if revision.record.scope != scope.current.record.scope:
                raise VoceCalibrationConflict("Scope member Dataset crosses tenant scope")
            if source.material_state_id != content.material_state_id:
                raise VoceCalibrationConflict("Scope member belongs to another Material State")
            if revision.content.representation not in (
                DatasetRepresentation.NORMALIZED,
                DatasetRepresentation.PROCESSED,
            ):
                raise VoceCalibrationConflict("Voce input must be normalized or processed")
            sources.append(source)
        if len(sources) < 2:
            raise VoceCalibrationConflict("Voce calibration requires at least two included curves")
        return scope, tuple(sources)

    def create_plan(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CreateReferenceVoceCalibrationPlan,
    ) -> VoceCalibrationPlanSnapshot:
        _require(context, decision, Permission.CALIBRATION_EXECUTE)
        scope, _ = self._inputs(context, decision, command.content)
        tenant_scope = TenantScope(
            context.organization_id, context.project_id, command.classification.value
        )
        if scope.current.record.scope != tenant_scope:
            raise VoceCalibrationConflict("Plan classification must match reviewed input Scope")
        plan_id = self._id()
        record = RevisionService(
            aggregate_type=VOCE_CALIBRATION_PLAN_AGGREGATE_TYPE,
            store=self._repository.plan_store(context, decision),
        ).create(
            CreateRevisionedAggregate(
                aggregate_id=plan_id,
                scope=tenant_scope,
                schema_id=REFERENCE_VOCE_PLAN_SCHEMA_ID,
                schema_version=REFERENCE_VOCE_PLAN_SCHEMA_VERSION,
                content=command.content,
                created_by=context.principal.id,
                change_reason=_reason(command.change_reason),
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        return VoceCalibrationPlanSnapshot(plan_id, RevisionSnapshot(record, command.content))

    def revise_plan(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        plan_id: UUID,
        command: ReviseReferenceVoceCalibrationPlan,
    ) -> VoceCalibrationPlanSnapshot:
        _require(context, decision, Permission.CALIBRATION_EXECUTE)
        existing = self._repository.get_plan(context=context, decision=decision, plan_id=plan_id)
        if command.content.plan_label != existing.current.content.plan_label:
            raise VoceCalibrationConflict("Plan label is a stable identity and cannot change")
        scope, _ = self._inputs(context, decision, command.content)
        if scope.current.record.scope != existing.current.record.scope:
            raise VoceCalibrationConflict("revised Plan input crosses the stable tenant scope")
        record = RevisionService(
            aggregate_type=VOCE_CALIBRATION_PLAN_AGGREGATE_TYPE,
            store=self._repository.plan_store(context, decision),
        ).revise(
            ReviseAggregate(
                aggregate_id=plan_id,
                scope=existing.current.record.scope,
                expected_current_revision_id=command.expected_current_revision_id,
                based_on_revision_id=command.expected_current_revision_id,
                schema_id=REFERENCE_VOCE_PLAN_SCHEMA_ID,
                schema_version=REFERENCE_VOCE_PLAN_SCHEMA_VERSION,
                content=command.content,
                created_by=context.principal.id,
                change_reason=_reason(command.change_reason),
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        return VoceCalibrationPlanSnapshot(plan_id, RevisionSnapshot(record, command.content))

    def get_plan(
        self, context: SecurityContext, decision: AuthorizationDecision, plan_id: UUID
    ) -> VoceCalibrationPlanSnapshot:
        _require(context, decision, Permission.MODELING_READ)
        return self._repository.get_plan(context=context, decision=decision, plan_id=plan_id)

    def list_plans(
        self, context: SecurityContext, decision: AuthorizationDecision, *, limit: int = 100
    ) -> tuple[VoceCalibrationPlanSnapshot, ...]:
        _require(context, decision, Permission.MODELING_READ)
        if not 1 <= limit <= 200:
            raise InvalidVoceCalibration("limit must be between 1 and 200")
        return self._repository.list_plans(context=context, decision=decision, limit=limit)

    async def execute(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: ExecuteReferenceVoceCalibration,
    ) -> VoceCalibrationRunDetail:
        _require(context, decision, Permission.CALIBRATION_EXECUTE)
        plan = self._repository.get_plan_revision(
            context=context,
            decision=decision,
            plan_id=command.plan_id,
            plan_revision_id=command.plan_revision_id,
        )
        scope, sources = self._inputs(context, decision, plan.content)
        run = self._repository.create_run(
            context=context,
            decision=decision,
            run=VoceCalibrationRun(
                id=self._id(),
                classification=DataClassification(plan.record.scope.classification),
                plan_id=command.plan_id,
                plan_revision_id=command.plan_revision_id,
                calibration_input_scope_id=scope.id,
                calibration_input_scope_revision_id=scope.current.record.revision_id,
                property_set_id=plan.content.property_set_id,
                property_set_revision_id=plan.content.property_set_revision_id,
                source_curve_count=len(sources),
                execution_mode="reference_inline_scipy",
                reproducibility_level="R3",
                environment_digest=REFERENCE_VOCE_ENVIRONMENT_DIGEST,
                status=CalibrationRunStatus.EXECUTING,
                attempt_count=plan.content.multistart_count,
                candidate_count=0,
                failure_code=None,
                change_reason=_reason(command.change_reason),
                started_at=datetime.now(UTC),
                ended_at=None,
                created_by=context.principal.id,
                request_id=context.request_id,
                trace_id=context.trace_id,
            ),
        )
        attempts = tuple(
            self._repository.create_attempt(
                context=context,
                decision=decision,
                attempt=VoceCalibrationAttempt(
                    id=self._id(),
                    calibration_run_id=run.id,
                    attempt_ordinal=ordinal,
                    initial_sigma_0_pa=values[0],
                    initial_q_pa=values[1],
                    initial_b=values[2],
                    random_seed=plan.content.random_seed,
                    status=CalibrationAttemptStatus.EXECUTING,
                    candidate_id=None,
                    failure_code=None,
                    started_at=datetime.now(UTC),
                    ended_at=None,
                ),
            )
            for ordinal, values in enumerate(
                reference_voce_multistart_parameters(plan.content), start=1
            )
        )
        try:
            inputs: list[VoceEngineeringCurveInput] = []
            source_by_revision = {
                source.dataset.revision.record.revision_id: source for source in sources
            }
            included_members = tuple(
                member
                for member in scope.current.content.members
                if member.disposition is CalibrationScopeDisposition.INCLUDED
            )
            for member_ordinal, member in enumerate(included_members):
                source = source_by_revision[member.dataset_revision_id]
                _, value = await self._artifacts.read_verified_bytes(
                    context,
                    decision,
                    source.dataset.revision.content.data_artifact_id,
                    maximum_bytes=16 * 1024 * 1024,
                )
                points = normalized_points_from_parquet(value)
                if len(points) != source.dataset.revision.content.point_count:
                    raise InvalidVoceCalibration(
                        "input Artifact point count differs from the pinned Dataset revision"
                    )
                inputs.append(
                    VoceEngineeringCurveInput(
                        member_ordinal=member_ordinal,
                        dataset_id=member.dataset_id,
                        dataset_revision_id=member.dataset_revision_id,
                        test_run_id=member.test_run_id,
                        test_run_revision_id=member.test_run_revision_id,
                        points=points,
                    )
                )
            outcomes = calibrate_reference_voce_curves(plan.content, tuple(inputs))
            for attempt, outcome in zip(attempts, outcomes, strict=True):
                diagnostics = await self._artifacts.finalize_derived_bytes(
                    context,
                    decision,
                    classification=run.classification,
                    artifact_role="modeling.reference_voce_calibration_diagnostics",
                    schema_ref=REFERENCE_VOCE_DIAGNOSTICS_SCHEMA,
                    media_type="application/vnd.apache.parquet",
                    value=reference_voce_diagnostics_parquet_bytes(outcome.diagnostics),
                    idempotency_key=f"voce-calibration:{run.id}:attempt:{outcome.attempt_ordinal}",
                )
                bound = set(outcome.bound_sticking_parameters)
                candidate = self._repository.create_candidate(
                    context=context,
                    decision=decision,
                    candidate=VoceCalibrationCandidate(
                        id=self._id(),
                        calibration_run_id=run.id,
                        calibration_attempt_id=attempt.id,
                        attempt_ordinal=outcome.attempt_ordinal,
                        status=(
                            CalibrationCandidateStatus.CONVERGED
                            if outcome.converged
                            else CalibrationCandidateStatus.NONCONVERGED
                        ),
                        candidate_sha256=reference_voce_candidate_content_hash(
                            run_id=run.id,
                            candidate=outcome,
                            diagnostics_sha256=diagnostics.artifact.sha256,
                        ),
                        sigma_0_pa=outcome.calibrated_parameters[0],
                        q_pa=outcome.calibrated_parameters[1],
                        b=outcome.calibrated_parameters[2],
                        objective_total=outcome.objective_total,
                        residual_root_mean_square_pa=outcome.residual_root_mean_square_pa,
                        residual_mean_pa=outcome.residual_mean_pa,
                        sigma_0_at_bound="sigma_0_pa" in bound,
                        q_at_bound="q_pa" in bound,
                        b_at_bound="b" in bound,
                        convergence_status_code=outcome.status_code,
                        convergence_reason=outcome.convergence_reason,
                        function_evaluations=outcome.function_evaluations,
                        jacobian_evaluations=outcome.jacobian_evaluations,
                        optimality=outcome.optimality,
                        warning_at_bound="one_or_more_parameters_at_bound" in outcome.warnings,
                        warning_nonconvergence="optimizer_did_not_converge" in outcome.warnings,
                        identifiability_status=outcome.identifiability_status,
                        uncertainty_status=outcome.uncertainty_status,
                        diagnostics_artifact_id=diagnostics.artifact.id,
                        diagnostics_sha256=diagnostics.artifact.sha256,
                        diagnostics_point_count=len(outcome.diagnostics),
                        objective_terms=outcome.objective_terms,
                        created_at=datetime.now(UTC),
                        created_by=context.principal.id,
                    ),
                )
                if outcome.converged:
                    self._repository.succeed_attempt(
                        context=context,
                        decision=decision,
                        attempt_id=attempt.id,
                        candidate_id=candidate.id,
                    )
                else:
                    self._repository.fail_attempt(
                        context=context,
                        decision=decision,
                        attempt_id=attempt.id,
                        failure_code="optimizer_nonconvergence",
                    )
            candidates = self._repository.list_candidates(
                context=context, decision=decision, run_id=run.id
            )
            succeeded = self._repository.succeed_run(
                context=context,
                decision=decision,
                run_id=run.id,
                candidate_count=len(candidates),
            )
            return VoceCalibrationRunDetail(
                succeeded,
                self._repository.list_attempts(context=context, decision=decision, run_id=run.id),
                candidates,
            )
        except Exception:
            for attempt in attempts:
                if attempt.status is CalibrationAttemptStatus.EXECUTING:
                    try:
                        self._repository.fail_attempt(
                            context=context,
                            decision=decision,
                            attempt_id=attempt.id,
                            failure_code="reference_voce_calibration_failed",
                        )
                    except Exception:
                        pass
            failed = self._repository.fail_run(
                context=context,
                decision=decision,
                run_id=run.id,
                failure_code="reference_voce_calibration_failed",
            )
            return VoceCalibrationRunDetail(
                failed,
                self._repository.list_attempts(context=context, decision=decision, run_id=run.id),
                self._repository.list_candidates(context=context, decision=decision, run_id=run.id),
            )

    def get_run(
        self, context: SecurityContext, decision: AuthorizationDecision, run_id: UUID
    ) -> VoceCalibrationRunDetail:
        _require(context, decision, Permission.MODELING_READ)
        return VoceCalibrationRunDetail(
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
        maximum_points: int = 1_000,
    ) -> VoceCalibrationDiagnosticPreview:
        _require(context, decision, Permission.MODELING_READ)
        if not 6 <= maximum_points <= 10_000:
            raise InvalidVoceCalibration("maximum_points must be between 6 and 10000")
        candidate = self._repository.get_candidate(
            context=context, decision=decision, candidate_id=candidate_id
        )
        artifact, value = await self._artifacts.read_verified_bytes(
            context,
            decision,
            candidate.diagnostics_artifact_id,
            maximum_bytes=32 * 1024 * 1024,
        )
        if artifact.artifact.sha256 != candidate.diagnostics_sha256:
            raise VoceCalibrationConflict("Candidate diagnostic digest does not match Artifact")
        points = reference_voce_diagnostics_from_parquet(value)
        if len(points) != candidate.diagnostics_point_count:
            raise VoceCalibrationConflict(
                "Candidate diagnostic point count does not match Artifact"
            )
        if len(points) <= maximum_points:
            returned = points
        else:
            indices = tuple(
                round(index * (len(points) - 1) / (maximum_points - 1))
                for index in range(maximum_points)
            )
            returned = tuple(points[index] for index in indices)
        return VoceCalibrationDiagnosticPreview(
            calibration_candidate_id=candidate.id,
            point_count=len(points),
            returned_point_count=len(returned),
            sampled=len(returned) != len(points),
            points=returned,
        )

    def get_candidate_for_projection(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        candidate_id: UUID,
    ) -> VoceCalibrationCandidate:
        _require_capability(context, decision, Permission.MODELING_READ)
        return self._repository.get_candidate(
            context=context, decision=decision, candidate_id=candidate_id
        )

    def get_run_for_projection(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
    ) -> VoceCalibrationRun:
        _require_capability(context, decision, Permission.MODELING_READ)
        return self._repository.get_run(context=context, decision=decision, run_id=run_id)

    def get_plan_revision_for_projection(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        plan_id: UUID,
        plan_revision_id: UUID,
    ) -> RevisionSnapshot[ReferenceVoceCalibrationPlanContent]:
        _require_capability(context, decision, Permission.MODELING_READ)
        return self._repository.get_plan_revision(
            context=context,
            decision=decision,
            plan_id=plan_id,
            plan_revision_id=plan_revision_id,
        )

    async def read_candidate_diagnostics_for_projection(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        candidate_id: UUID,
    ) -> tuple[VoceDiagnosticPoint, ...]:
        _require_capability(context, decision, Permission.MODELING_READ)
        candidate = self._repository.get_candidate(
            context=context, decision=decision, candidate_id=candidate_id
        )
        artifact, value = await self._artifacts.read_verified_bytes(
            context,
            decision,
            candidate.diagnostics_artifact_id,
            maximum_bytes=32 * 1024 * 1024,
        )
        if artifact.artifact.sha256 != candidate.diagnostics_sha256:
            raise VoceCalibrationConflict("Candidate diagnostic digest does not match Artifact")
        points = reference_voce_diagnostics_from_parquet(value)
        if len(points) != candidate.diagnostics_point_count:
            raise VoceCalibrationConflict(
                "Candidate diagnostic point count does not match Artifact"
            )
        return points

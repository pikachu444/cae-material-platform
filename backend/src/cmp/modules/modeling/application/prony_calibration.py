"""Application orchestration for bounded reference Prony calibration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID, uuid4

from cmp.modules.artifacts.application.content import ArtifactService
from cmp.modules.datasets.application.shear_relaxation import ShearRelaxationDatasetService
from cmp.modules.datasets.domain.reference_shear_relaxation import (
    shear_relaxation_points_from_parquet,
)
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
    Permission,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.modeling.application.linear_viscoelasticity import (
    LinearViscoelasticModelService,
)
from cmp.modules.modeling.application.service import RevisionSnapshot
from cmp.modules.modeling.domain.reference_linear_viscoelasticity import BulkRelaxationStatus
from cmp.modules.modeling.domain.reference_prony_calibration import (
    REFERENCE_PRONY_DIAGNOSTICS_SCHEMA,
    REFERENCE_PRONY_ENVIRONMENT_DIGEST,
    REFERENCE_PRONY_PLAN_SCHEMA_ID,
    REFERENCE_PRONY_PLAN_SCHEMA_VERSION,
    InvalidPronyCalibration,
    PronyCalibrationCandidate,
    ReferencePronyCalibrationPlanContent,
    calibrate_reference_prony,
    prony_diagnostics_from_parquet,
    prony_diagnostics_parquet_bytes,
)
from cmp.modules.processing.domain.reference_tensile_crop import ProcessingRunStatus
from cmp.shared.application.revisions import (
    CreateRevisionedAggregate,
    RevisionService,
    RevisionStore,
)
from cmp.shared.domain.revisions import TenantScope

PRONY_CALIBRATION_PLAN_AGGREGATE_TYPE = "modeling.prony_calibration_plan"


class PronyCalibrationConflict(Exception):
    """Pinned input, baseline, or persisted calibration evidence conflicts."""


class PronyCalibrationNotFound(Exception):
    """Requested Plan, Run, or Candidate is not visible."""


@dataclass(frozen=True, slots=True)
class PronyCalibrationPlanSnapshot:
    id: UUID
    current: RevisionSnapshot[ReferencePronyCalibrationPlanContent]


@dataclass(frozen=True, slots=True)
class PersistedPronyCandidate:
    id: UUID
    attempt_id: UUID
    calibration_run_id: UUID
    value: PronyCalibrationCandidate
    diagnostics_artifact_id: UUID
    diagnostics_sha256: str
    diagnostics_point_count: int
    created_at: datetime
    created_by: UUID


@dataclass(frozen=True, slots=True)
class PronyCalibrationRun:
    id: UUID
    classification: DataClassification
    plan_id: UUID
    plan_revision_id: UUID
    input_dataset_id: UUID
    input_dataset_revision_id: UUID
    baseline_model_id: UUID
    baseline_model_revision_id: UUID
    status: ProcessingRunStatus
    environment_digest: str
    attempt_count: int
    candidate_count: int
    failure_code: str | None
    change_reason: str
    started_at: datetime
    ended_at: datetime
    created_by: UUID
    request_id: UUID
    trace_id: str
    candidates: tuple[PersistedPronyCandidate, ...]


@dataclass(frozen=True, slots=True)
class CreateReferencePronyCalibrationPlan:
    classification: DataClassification
    content: ReferencePronyCalibrationPlanContent
    change_reason: str


@dataclass(frozen=True, slots=True)
class ExecuteReferencePronyCalibration:
    plan_id: UUID
    plan_revision_id: UUID
    change_reason: str


class PronyCalibrationRepository(Protocol):
    def plan_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[ReferencePronyCalibrationPlanContent]: ...

    def get_plan_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        plan_id: UUID,
        plan_revision_id: UUID,
    ) -> RevisionSnapshot[ReferencePronyCalibrationPlanContent]: ...

    def save_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run: PronyCalibrationRun,
    ) -> PronyCalibrationRun: ...

    def get_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
    ) -> PronyCalibrationRun: ...

    def get_candidate(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        candidate_id: UUID,
    ) -> PersistedPronyCandidate: ...


def _require(
    context: SecurityContext, decision: AuthorizationDecision, permission: Permission
) -> None:
    if (
        decision.permission is not permission
        or decision.principal_id != context.principal.id
        or decision.organization_id != context.organization_id
        or decision.project_id != context.project_id
        or decision.request_id != context.request_id
        or decision.trace_id != context.trace_id
    ):
        raise PronyCalibrationConflict(
            "authorization decision does not match Prony calibration request"
        )


def _reason(value: str) -> str:
    if not value or value != value.strip() or len(value) > 2000 or "\x00" in value:
        raise ValueError("change_reason must be trimmed and contain 1..2000 characters")
    return value


class ReferencePronyCalibrationService:
    def __init__(
        self,
        *,
        repository: PronyCalibrationRepository,
        datasets: ShearRelaxationDatasetService,
        models: LinearViscoelasticModelService,
        artifacts: ArtifactService,
        id_factory: Callable[[], UUID] = uuid4,
    ) -> None:
        self._repository = repository
        self._datasets = datasets
        self._models = models
        self._artifacts = artifacts
        self._id_factory = id_factory

    def create_plan(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CreateReferencePronyCalibrationPlan,
    ) -> PronyCalibrationPlanSnapshot:
        _require(context, decision, Permission.CALIBRATION_EXECUTE)
        plan_id = self._id_factory()
        record = RevisionService(
            aggregate_type=PRONY_CALIBRATION_PLAN_AGGREGATE_TYPE,
            store=self._repository.plan_store(context, decision),
        ).create(
            CreateRevisionedAggregate(
                aggregate_id=plan_id,
                scope=TenantScope(
                    context.organization_id,
                    context.project_id,
                    command.classification.value,
                ),
                schema_id=REFERENCE_PRONY_PLAN_SCHEMA_ID,
                schema_version=REFERENCE_PRONY_PLAN_SCHEMA_VERSION,
                content=command.content,
                created_by=context.principal.id,
                change_reason=_reason(command.change_reason),
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        return PronyCalibrationPlanSnapshot(plan_id, RevisionSnapshot(record, command.content))

    async def execute(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: ExecuteReferencePronyCalibration,
    ) -> PronyCalibrationRun:
        _require(context, decision, Permission.CALIBRATION_EXECUTE)
        reason = _reason(command.change_reason)
        plan = self._repository.get_plan_revision(
            context=context,
            decision=decision,
            plan_id=command.plan_id,
            plan_revision_id=command.plan_revision_id,
        )
        content = plan.content
        dataset = self._datasets.get_revision_for_calibration(
            context,
            decision,
            content.input_dataset_id,
            content.input_dataset_revision_id,
        )
        if dataset.content.representation != "processed":
            raise PronyCalibrationConflict(
                "Prony calibration requires an explicit processed Dataset revision"
            )
        baseline = self._models.get_model_revision_for_calibration(
            context,
            decision,
            content.baseline_model_id,
            content.baseline_model_revision_id,
        )
        if (
            plan.record.scope != dataset.record.scope
            or plan.record.scope != baseline.record.scope
            or dataset.content.material_state_id != baseline.content.material_state_id
            or dataset.content.material_state_revision_id
            != baseline.content.material_state_revision_id
        ):
            raise PronyCalibrationConflict(
                "Plan, processed Dataset, and baseline IR must share exact tenant "
                "and State revision"
            )
        if baseline.content.bulk_relaxation_status is not BulkRelaxationStatus.NOT_CHARACTERIZED:
            raise PronyCalibrationConflict(
                "reference shear-only calibration requires bulk relaxation not_characterized"
            )
        _, value = await self._artifacts.read_verified_bytes(
            context,
            decision,
            dataset.content.data_artifact_id,
            maximum_bytes=16 * 1024 * 1024,
        )
        points = shear_relaxation_points_from_parquet(value)
        if len(points) != dataset.content.point_count:
            raise PronyCalibrationConflict(
                "processed Dataset point count differs from its immutable Artifact"
            )
        candidates = calibrate_reference_prony(
            plan=content,
            points=points,
            instantaneous_shear_modulus_pa=(
                baseline.content.instantaneous_shear_modulus_pa
            ),
        )
        run_id = self._id_factory()
        started_at = datetime.now(UTC)
        persisted: list[PersistedPronyCandidate] = []
        for candidate in candidates:
            attempt_id = self._id_factory()
            candidate_id = self._id_factory()
            artifact = await self._artifacts.finalize_derived_bytes(
                context,
                decision,
                classification=DataClassification(plan.record.scope.classification),
                artifact_role="modeling.reference_prony_candidate_diagnostics",
                schema_ref=REFERENCE_PRONY_DIAGNOSTICS_SCHEMA,
                media_type="application/vnd.apache.parquet",
                value=prony_diagnostics_parquet_bytes(points=points, candidate=candidate),
                idempotency_key=(
                    f"prony-calibration:{run_id}:attempt:{candidate.attempt_ordinal}"
                ),
            )
            persisted.append(
                PersistedPronyCandidate(
                    id=candidate_id,
                    attempt_id=attempt_id,
                    calibration_run_id=run_id,
                    value=candidate,
                    diagnostics_artifact_id=artifact.artifact.id,
                    diagnostics_sha256=artifact.artifact.sha256,
                    diagnostics_point_count=len(points),
                    created_at=datetime.now(UTC),
                    created_by=context.principal.id,
                )
            )
        run = PronyCalibrationRun(
            id=run_id,
            classification=DataClassification(plan.record.scope.classification),
            plan_id=command.plan_id,
            plan_revision_id=command.plan_revision_id,
            input_dataset_id=content.input_dataset_id,
            input_dataset_revision_id=content.input_dataset_revision_id,
            baseline_model_id=content.baseline_model_id,
            baseline_model_revision_id=content.baseline_model_revision_id,
            status=ProcessingRunStatus.SUCCEEDED,
            environment_digest=REFERENCE_PRONY_ENVIRONMENT_DIGEST,
            attempt_count=len(candidates),
            candidate_count=len(candidates),
            failure_code=None,
            change_reason=reason,
            started_at=started_at,
            ended_at=datetime.now(UTC),
            created_by=context.principal.id,
            request_id=context.request_id,
            trace_id=context.trace_id,
            candidates=tuple(persisted),
        )
        return self._repository.save_run(context=context, decision=decision, run=run)

    def get_run(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
    ) -> PronyCalibrationRun:
        _require(context, decision, Permission.MODELING_READ)
        return self._repository.get_run(context=context, decision=decision, run_id=run_id)

    async def candidate_diagnostics(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        candidate_id: UUID,
    ) -> tuple[dict[str, float | int], ...]:
        _require(context, decision, Permission.MODELING_READ)
        candidate = self._repository.get_candidate(
            context=context, decision=decision, candidate_id=candidate_id
        )
        _, value = await self._artifacts.read_verified_bytes(
            context,
            decision,
            candidate.diagnostics_artifact_id,
            maximum_bytes=16 * 1024 * 1024,
        )
        rows = prony_diagnostics_from_parquet(value)
        if len(rows) != candidate.diagnostics_point_count:
            raise InvalidPronyCalibration(
                "diagnostics Artifact point count differs from Candidate"
            )
        return rows

"""Application workflow for solver-independent reference Voce holdout validation."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol, cast
from uuid import UUID, uuid4

from cmp.modules.artifacts.application.content import ArtifactService
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
from cmp.modules.modeling.application.tabulated_plasticity import (
    TabulatedPlasticityModelService,
)
from cmp.modules.modeling.domain.reference_voce_calibration import VoceEngineeringCurveInput
from cmp.modules.modeling.domain.reference_voce_tabulated_plasticity import (
    ReferenceVoceTabulatedPlasticityContent,
)
from cmp.modules.statistics.application.replicate_outlier_service import (
    CalibrationInputScopeSnapshot,
    ReplicateOutlierService,
)
from cmp.modules.validation.domain.reference_voce_holdout import (
    REFERENCE_VOCE_HOLDOUT_COMPARISON_SCHEMA_ID,
    REFERENCE_VOCE_HOLDOUT_PLAN_SCHEMA_ID,
    REFERENCE_VOCE_HOLDOUT_PLAN_SCHEMA_VERSION,
    ReferenceVoceHoldoutPlanContent,
    ReferenceVoceHoldoutResult,
    VoceHoldoutConflict,
    evaluate_reference_voce_holdout,
    reference_voce_holdout_comparison_bytes,
)
from cmp.shared.application.revisions import (
    CreateRevisionedAggregate,
    RevisionService,
    RevisionStore,
)
from cmp.shared.domain.revisions import TenantScope

VOCE_HOLDOUT_PLAN_AGGREGATE_TYPE = "validation.voce_holdout_plan"


@dataclass(frozen=True, slots=True)
class VoceHoldoutPlanSnapshot:
    id: UUID
    current: RevisionSnapshot[ReferenceVoceHoldoutPlanContent]


@dataclass(frozen=True, slots=True)
class CreateReferenceVoceHoldoutPlan:
    classification: DataClassification
    content: ReferenceVoceHoldoutPlanContent
    change_reason: str


@dataclass(frozen=True, slots=True)
class ExecuteReferenceVoceHoldout:
    plan_id: UUID
    plan_revision_id: UUID
    change_reason: str


class VoceHoldoutRepository(Protocol):
    def plan_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[ReferenceVoceHoldoutPlanContent]: ...

    def get_plan(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        plan_id: UUID,
    ) -> VoceHoldoutPlanSnapshot: ...

    def get_plan_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        plan_id: UUID,
        plan_revision_id: UUID,
    ) -> RevisionSnapshot[ReferenceVoceHoldoutPlanContent]: ...

    def list_plans(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        limit: int,
    ) -> tuple[VoceHoldoutPlanSnapshot, ...]: ...

    def create_succeeded_result(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        classification: DataClassification,
        result: ReferenceVoceHoldoutResult,
        change_reason: str,
    ) -> ReferenceVoceHoldoutResult: ...

    def get_result(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        result_id: UUID,
    ) -> ReferenceVoceHoldoutResult: ...

    def list_results_for_model(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_model_id: UUID,
        limit: int,
    ) -> tuple[ReferenceVoceHoldoutResult, ...]: ...


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
        raise VoceHoldoutConflict("authorization decision does not match holdout request")


def _reason(value: str) -> str:
    if not value or value != value.strip() or len(value) > 2_000 or "\x00" in value:
        raise ValueError("change reason must be trimmed and contain 1..2000 characters")
    return value


class ReferenceVoceHoldoutService:
    def __init__(
        self,
        *,
        repository: VoceHoldoutRepository,
        models: TabulatedPlasticityModelService,
        statistics: ReplicateOutlierService,
        datasets: DatasetService,
        artifacts: ArtifactService,
        id_factory: Callable[[], UUID] = uuid4,
    ) -> None:
        self._repository = repository
        self._models = models
        self._statistics = statistics
        self._datasets = datasets
        self._artifacts = artifacts
        self._id_factory = id_factory

    def _id(self) -> UUID:
        value = self._id_factory()
        if value.int == 0:
            raise RuntimeError("holdout id_factory returned a zero UUID")
        return value

    def _inputs(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        content: ReferenceVoceHoldoutPlanContent,
    ) -> tuple[
        RevisionSnapshot[ReferenceVoceTabulatedPlasticityContent],
        CalibrationInputScopeSnapshot,
        CalibrationDatasetSource,
    ]:
        model = self._models.get_model_revision_for_export(
            context,
            decision,
            content.material_model_id,
            content.material_model_revision_id,
        )
        if not isinstance(model.content, ReferenceVoceTabulatedPlasticityContent):
            raise VoceHoldoutConflict("holdout requires a calibrated reference Voce IR revision")
        scope = self._statistics.get_scope_revision_for_calibration(
            context,
            decision,
            model.content.calibration_input_scope_id,
            model.content.calibration_input_scope_revision_id,
        )
        holdout = self._datasets.get_dataset_source_for_validation(
            context, decision, content.holdout_dataset_revision_id
        )
        revision = holdout.dataset.revision
        if (
            holdout.dataset.dataset_id != content.holdout_dataset_id
            or revision.record.revision_id != content.holdout_dataset_revision_id
        ):
            raise VoceHoldoutConflict("holdout Dataset identity and revision do not match")
        if (
            model.record.scope != scope.current.record.scope
            or revision.record.scope != model.record.scope
        ):
            raise VoceHoldoutConflict("holdout inputs cross tenant or classification scope")
        if holdout.material_state_id != model.content.material_state_id:
            raise VoceHoldoutConflict("holdout Dataset belongs to another Material State")
        if revision.content.representation not in {
            DatasetRepresentation.NORMALIZED,
            DatasetRepresentation.PROCESSED,
        }:
            raise VoceHoldoutConflict("holdout Dataset must be normalized or processed")
        if any(
            member.dataset_revision_id == revision.record.revision_id
            or member.test_run_revision_id == revision.content.test_run_revision_id
            for member in scope.current.content.members
        ):
            raise VoceHoldoutConflict(
                "holdout Dataset or Test Run overlaps the complete calibration review scope"
            )
        return (
            cast(RevisionSnapshot[ReferenceVoceTabulatedPlasticityContent], model),
            scope,
            holdout,
        )

    def create_plan(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CreateReferenceVoceHoldoutPlan,
    ) -> VoceHoldoutPlanSnapshot:
        _require(context, decision, Permission.VALIDATION_EXECUTE)
        model, _, _ = self._inputs(context, decision, command.content)
        tenant_scope = TenantScope(
            context.organization_id, context.project_id, command.classification.value
        )
        if model.record.scope != tenant_scope:
            raise VoceHoldoutConflict("Plan classification must match the pinned model")
        plan_id = self._id()
        record = RevisionService(
            aggregate_type=VOCE_HOLDOUT_PLAN_AGGREGATE_TYPE,
            store=self._repository.plan_store(context, decision),
        ).create(
            CreateRevisionedAggregate(
                aggregate_id=plan_id,
                scope=tenant_scope,
                schema_id=REFERENCE_VOCE_HOLDOUT_PLAN_SCHEMA_ID,
                schema_version=REFERENCE_VOCE_HOLDOUT_PLAN_SCHEMA_VERSION,
                content=command.content,
                created_by=context.principal.id,
                change_reason=_reason(command.change_reason),
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        return VoceHoldoutPlanSnapshot(
            plan_id, RevisionSnapshot(record=record, content=command.content)
        )

    def get_plan(
        self, context: SecurityContext, decision: AuthorizationDecision, plan_id: UUID
    ) -> VoceHoldoutPlanSnapshot:
        _require(context, decision, Permission.VALIDATION_READ)
        return self._repository.get_plan(context=context, decision=decision, plan_id=plan_id)

    def list_plans(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        *,
        limit: int = 100,
    ) -> tuple[VoceHoldoutPlanSnapshot, ...]:
        _require(context, decision, Permission.VALIDATION_READ)
        if not 1 <= limit <= 200:
            raise ValueError("limit must be between 1 and 200")
        return self._repository.list_plans(context=context, decision=decision, limit=limit)

    async def execute(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: ExecuteReferenceVoceHoldout,
    ) -> ReferenceVoceHoldoutResult:
        _require(context, decision, Permission.VALIDATION_EXECUTE)
        plan = self._repository.get_plan_revision(
            context=context,
            decision=decision,
            plan_id=command.plan_id,
            plan_revision_id=command.plan_revision_id,
        )
        model, _, holdout = self._inputs(context, decision, plan.content)
        revision = holdout.dataset.revision
        artifact, value = await self._artifacts.read_verified_bytes(
            context,
            decision,
            revision.content.data_artifact_id,
            maximum_bytes=16 * 1024 * 1024,
        )
        if artifact.artifact.sha256 != revision.content.data_sha256:
            raise VoceHoldoutConflict("holdout Dataset Artifact digest is stale")
        points = normalized_points_from_parquet(value)
        if len(points) != revision.content.point_count:
            raise VoceHoldoutConflict("holdout Artifact point count differs from its revision")
        metrics = evaluate_reference_voce_holdout(
            VoceEngineeringCurveInput(
                member_ordinal=0,
                dataset_id=holdout.dataset.dataset_id,
                dataset_revision_id=revision.record.revision_id,
                test_run_id=revision.content.test_run_id,
                test_run_revision_id=revision.content.test_run_revision_id,
                points=points,
            ),
            youngs_modulus_pa=model.content.youngs_modulus_pa,
            sigma_0_pa=model.content.initial_yield_stress_pa,
            q_pa=model.content.q_pa,
            b=model.content.b,
        )
        run_id = self._id()
        comparison = await self._artifacts.finalize_derived_bytes(
            context,
            decision,
            classification=DataClassification(plan.record.scope.classification),
            artifact_role="validation.reference_voce_holdout_comparison",
            schema_ref=REFERENCE_VOCE_HOLDOUT_COMPARISON_SCHEMA_ID,
            media_type="application/json",
            value=reference_voce_holdout_comparison_bytes(metrics),
            idempotency_key=f"voce-holdout:{run_id}:comparison",
        )
        result = ReferenceVoceHoldoutResult(
            id=self._id(),
            run_id=run_id,
            plan_id=command.plan_id,
            plan_revision_id=command.plan_revision_id,
            material_model_id=plan.content.material_model_id,
            material_model_revision_id=plan.content.material_model_revision_id,
            calibration_input_scope_id=model.content.calibration_input_scope_id,
            calibration_input_scope_revision_id=(model.content.calibration_input_scope_revision_id),
            voce_calibration_run_id=model.content.voce_calibration_run_id,
            voce_calibration_candidate_id=model.content.voce_calibration_candidate_id,
            voce_candidate_selection_id=model.content.voce_candidate_selection_id,
            voce_candidate_selection_revision_id=(
                model.content.voce_candidate_selection_revision_id
            ),
            holdout_dataset_id=holdout.dataset.dataset_id,
            holdout_dataset_revision_id=revision.record.revision_id,
            holdout_test_run_id=revision.content.test_run_id,
            holdout_test_run_revision_id=revision.content.test_run_revision_id,
            source_data_artifact_id=artifact.artifact.id,
            source_data_sha256=artifact.artifact.sha256,
            comparison_artifact_id=comparison.artifact.id,
            comparison_sha256=comparison.artifact.sha256,
            metrics=metrics,
            created_at=datetime.now(UTC),
            created_by=context.principal.id,
        )
        return self._repository.create_succeeded_result(
            context=context,
            decision=decision,
            classification=DataClassification(plan.record.scope.classification),
            result=result,
            change_reason=_reason(command.change_reason),
        )

    def get_result(
        self, context: SecurityContext, decision: AuthorizationDecision, result_id: UUID
    ) -> ReferenceVoceHoldoutResult:
        _require(context, decision, Permission.VALIDATION_READ)
        return self._repository.get_result(context=context, decision=decision, result_id=result_id)

    def list_results_for_model(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_model_id: UUID,
        *,
        limit: int = 100,
    ) -> tuple[ReferenceVoceHoldoutResult, ...]:
        _require(context, decision, Permission.VALIDATION_READ)
        if not 1 <= limit <= 200:
            raise ValueError("limit must be between 1 and 200")
        return self._repository.list_results_for_model(
            context=context,
            decision=decision,
            material_model_id=material_model_id,
            limit=limit,
        )

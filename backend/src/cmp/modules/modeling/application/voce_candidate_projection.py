"""Human Voce Candidate Selection and deterministic solver-neutral IR projection."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID, uuid4

from cmp.modules.artifacts.application.content import ArtifactService
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
    Permission,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.modeling.application.service import (
    MATERIAL_MODEL_AGGREGATE_TYPE,
    MaterialModelService,
    RevisionSnapshot,
)
from cmp.modules.modeling.application.tabulated_plasticity import (
    TabulatedPlasticityModelSnapshot,
    TabulatedPlasticityRepository,
)
from cmp.modules.modeling.application.voce_calibration import ReferenceVoceCalibrationService
from cmp.modules.modeling.domain.reference_isotropic_tabulated_plasticity import (
    REFERENCE_HARDENING_CURVE_SCHEMA,
    hardening_curve_parquet_bytes,
)
from cmp.modules.modeling.domain.reference_linear_elastic_calibration import (
    CalibrationCandidateStatus,
    CalibrationRunStatus,
)
from cmp.modules.modeling.domain.reference_voce_candidate_selection import (
    REFERENCE_VOCE_SELECTION_SCHEMA_ID,
    REFERENCE_VOCE_SELECTION_SCHEMA_VERSION,
    ReferenceVoceCandidateSelectionContent,
    VoceCandidateSelectionConflict,
)
from cmp.modules.modeling.domain.reference_voce_tabulated_plasticity import (
    REFERENCE_VOCE_TABULATED_PLASTICITY_SCHEMA_ID,
    REFERENCE_VOCE_TABULATED_PLASTICITY_SCHEMA_VERSION,
    ReferenceVoceTabulatedPlasticityContent,
    voce_fixed_grid_hardening_curve,
)
from cmp.shared.application.revisions import (
    CreateRevisionedAggregate,
    RevisionService,
    RevisionStore,
)
from cmp.shared.domain.revisions import TenantScope

VOCE_CANDIDATE_SELECTION_AGGREGATE_TYPE = "modeling.voce_candidate_selection"


@dataclass(frozen=True, slots=True)
class VoceCandidateSelectionSnapshot:
    id: UUID
    current: RevisionSnapshot[ReferenceVoceCandidateSelectionContent]


@dataclass(frozen=True, slots=True)
class CreateVoceCandidateSelection:
    classification: DataClassification
    selection_label: str
    voce_calibration_run_id: UUID
    voce_calibration_candidate_id: UUID
    selection_reason: str


@dataclass(frozen=True, slots=True)
class ProjectSelectedVoceCandidate:
    selection_revision_id: UUID
    sampling_point_count: int
    extension_max_true_plastic_strain: float
    acknowledge_constant_extension: bool
    change_reason: str


class VoceCandidateSelectionRepository(Protocol):
    def selection_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[ReferenceVoceCandidateSelectionContent]: ...

    def get_selection(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        selection_id: UUID,
    ) -> VoceCandidateSelectionSnapshot: ...

    def get_selection_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        selection_id: UUID,
        selection_revision_id: UUID,
    ) -> RevisionSnapshot[ReferenceVoceCandidateSelectionContent]: ...


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
        raise VoceCandidateSelectionConflict(
            "authorization decision does not match Voce selection request"
        )


def _reason(value: str) -> str:
    if not value or value != value.strip() or len(value) > 2_000 or "\x00" in value:
        raise ValueError("reason must be trimmed and contain 1..2000 characters")
    return value


class VoceCandidateProjectionService:
    def __init__(
        self,
        *,
        selections: VoceCandidateSelectionRepository,
        material_model_repository: TabulatedPlasticityRepository,
        calibrations: ReferenceVoceCalibrationService,
        material_models: MaterialModelService,
        artifacts: ArtifactService,
        id_factory: Callable[[], UUID] = uuid4,
    ) -> None:
        self._selections = selections
        self._material_model_repository = material_model_repository
        self._calibrations = calibrations
        self._material_models = material_models
        self._artifacts = artifacts
        self._id_factory = id_factory

    def _id(self) -> UUID:
        value = self._id_factory()
        if value.int == 0:
            raise RuntimeError("Voce projection id_factory returned a zero UUID")
        return value

    def create_selection(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CreateVoceCandidateSelection,
    ) -> VoceCandidateSelectionSnapshot:
        _require(context, decision, Permission.MODELING_WRITE)
        candidate = self._calibrations.get_candidate_for_projection(
            context, decision, command.voce_calibration_candidate_id
        )
        run = self._calibrations.get_run_for_projection(
            context, decision, command.voce_calibration_run_id
        )
        if candidate.calibration_run_id != run.id:
            raise VoceCandidateSelectionConflict("Candidate does not belong to the selected Run")
        if candidate.status is not CalibrationCandidateStatus.CONVERGED:
            raise VoceCandidateSelectionConflict("only a converged Candidate can be selected")
        if run.status is not CalibrationRunStatus.SUCCEEDED:
            raise VoceCandidateSelectionConflict("Candidate Selection requires a succeeded Run")
        if run.classification is not command.classification:
            raise VoceCandidateSelectionConflict("Selection classification must equal Run scope")
        content = ReferenceVoceCandidateSelectionContent(
            selection_label=command.selection_label,
            voce_calibration_run_id=run.id,
            voce_calibration_candidate_id=candidate.id,
            candidate_sha256=candidate.candidate_sha256,
            selection_reason=_reason(command.selection_reason),
        )
        selection_id = self._id()
        record = RevisionService(
            aggregate_type=VOCE_CANDIDATE_SELECTION_AGGREGATE_TYPE,
            store=self._selections.selection_store(context, decision),
            id_factory=self._id_factory,
        ).create(
            CreateRevisionedAggregate(
                aggregate_id=selection_id,
                scope=TenantScope(
                    context.organization_id,
                    context.project_id,
                    command.classification.value,
                ),
                schema_id=REFERENCE_VOCE_SELECTION_SCHEMA_ID,
                schema_version=REFERENCE_VOCE_SELECTION_SCHEMA_VERSION,
                content=content,
                created_by=context.principal.id,
                change_reason=content.selection_reason,
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        return VoceCandidateSelectionSnapshot(
            selection_id, RevisionSnapshot(record=record, content=content)
        )

    def get_selection(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        selection_id: UUID,
    ) -> VoceCandidateSelectionSnapshot:
        _require(context, decision, Permission.MODELING_READ)
        return self._selections.get_selection(
            context=context, decision=decision, selection_id=selection_id
        )

    async def project(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        selection_id: UUID,
        command: ProjectSelectedVoceCandidate,
    ) -> TabulatedPlasticityModelSnapshot:
        _require(context, decision, Permission.MODELING_WRITE)
        selection = self._selections.get_selection_revision(
            context=context,
            decision=decision,
            selection_id=selection_id,
            selection_revision_id=command.selection_revision_id,
        )
        content = selection.content
        candidate = self._calibrations.get_candidate_for_projection(
            context, decision, content.voce_calibration_candidate_id
        )
        run = self._calibrations.get_run_for_projection(
            context, decision, content.voce_calibration_run_id
        )
        if (
            candidate.calibration_run_id != run.id
            or candidate.candidate_sha256 != content.candidate_sha256
            or candidate.status is not CalibrationCandidateStatus.CONVERGED
            or run.status is not CalibrationRunStatus.SUCCEEDED
        ):
            raise VoceCandidateSelectionConflict("Selection no longer resolves to exact lineage")
        plan = self._calibrations.get_plan_revision_for_projection(
            context, decision, run.plan_id, run.plan_revision_id
        )
        properties = self._material_models.get_reference_property_source_for_tabulated_plasticity(
            context,
            decision,
            material_state_id=plan.content.material_state_id,
            property_set_revision_id=run.property_set_revision_id,
        )
        if properties.material_class != "metal":
            raise VoceCandidateSelectionConflict(
                "Voce plasticity projection requires a Material revision classified as metal"
            )
        if selection.record.scope.classification != properties.classification.value:
            raise VoceCandidateSelectionConflict("Selection and Property Set scope differ")
        diagnostics = await self._calibrations.read_candidate_diagnostics_for_projection(
            context, decision, candidate.id
        )
        characterized_max = max(point.true_plastic_strain for point in diagnostics)
        points = voce_fixed_grid_hardening_curve(
            sigma_0_pa=candidate.sigma_0_pa,
            q_pa=candidate.q_pa,
            b=candidate.b,
            characterized_max_true_plastic_strain=characterized_max,
            extension_max_true_plastic_strain=command.extension_max_true_plastic_strain,
            sampling_point_count=command.sampling_point_count,
            acknowledge_constant_extension=command.acknowledge_constant_extension,
        )
        curve_bytes = hardening_curve_parquet_bytes(points)
        derivation_key = hashlib.sha256(
            (
                f"{selection.record.revision_id}:{candidate.candidate_sha256}:"
                f"{command.sampling_point_count}:{command.extension_max_true_plastic_strain:.17g}:"
                f"{hashlib.sha256(curve_bytes).hexdigest()}"
            ).encode("ascii")
        ).hexdigest()
        artifact = await self._artifacts.finalize_derived_bytes(
            context,
            decision,
            classification=properties.classification,
            artifact_role="modeling.hardening_curve",
            schema_ref=REFERENCE_HARDENING_CURVE_SCHEMA,
            media_type="application/vnd.apache.parquet",
            value=curve_bytes,
            idempotency_key=f"voce-tabulated-projection:{derivation_key}",
        )
        source = properties.content
        projected = ReferenceVoceTabulatedPlasticityContent(
            material_id=source.material_id,
            material_revision_id=source.material_revision_id,
            material_state_id=source.material_state_id,
            material_state_revision_id=source.material_state_revision_id,
            property_set_id=source.property_set_id,
            property_set_revision_id=source.property_set_revision_id,
            calibration_input_scope_id=run.calibration_input_scope_id,
            calibration_input_scope_revision_id=run.calibration_input_scope_revision_id,
            voce_calibration_plan_id=run.plan_id,
            voce_calibration_plan_revision_id=run.plan_revision_id,
            voce_calibration_run_id=run.id,
            voce_calibration_candidate_id=candidate.id,
            voce_calibration_candidate_sha256=candidate.candidate_sha256,
            voce_candidate_selection_id=selection_id,
            voce_candidate_selection_revision_id=selection.record.revision_id,
            hardening_curve_artifact_id=artifact.artifact.id,
            hardening_curve_sha256=artifact.artifact.sha256,
            hardening_curve_point_count=len(points),
            sampling_point_count=command.sampling_point_count,
            density_kg_per_m3=source.density_kg_per_m3,
            youngs_modulus_pa=source.youngs_modulus_pa,
            poisson_ratio=source.poisson_ratio,
            initial_yield_stress_pa=candidate.sigma_0_pa,
            q_pa=candidate.q_pa,
            b=candidate.b,
            characterized_max_true_plastic_strain=characterized_max,
            extension_max_true_plastic_strain=command.extension_max_true_plastic_strain,
            post_necking_approximation_acknowledged=command.acknowledge_constant_extension,
            applicable_temperature_min_k=source.applicable_temperature_min_k,
            applicable_temperature_max_k=source.applicable_temperature_max_k,
            applicable_strain_rate_min_per_s=source.applicable_strain_rate_min_per_s,
            applicable_strain_rate_max_per_s=source.applicable_strain_rate_max_per_s,
            applicability_note=source.applicability_note,
            reference_temperature_k=source.reference_temperature_k,
        )
        model_id = self._id()
        record = RevisionService(
            aggregate_type=MATERIAL_MODEL_AGGREGATE_TYPE,
            store=self._material_model_repository.material_model_store(context, decision),
            id_factory=self._id_factory,
        ).create(
            CreateRevisionedAggregate(
                aggregate_id=model_id,
                scope=selection.record.scope,
                schema_id=REFERENCE_VOCE_TABULATED_PLASTICITY_SCHEMA_ID,
                schema_version=REFERENCE_VOCE_TABULATED_PLASTICITY_SCHEMA_VERSION,
                content=projected,
                created_by=context.principal.id,
                change_reason=_reason(command.change_reason),
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        return TabulatedPlasticityModelSnapshot(
            id=model_id,
            material_state_id=projected.material_state_id,
            current=RevisionSnapshot(record=record, content=projected),
        )

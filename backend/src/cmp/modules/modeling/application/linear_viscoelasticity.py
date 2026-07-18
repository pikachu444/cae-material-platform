"""Create and read the manual reference linear-viscoelastic Material Model IR."""

from __future__ import annotations

import json
import math
from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Protocol
from uuid import UUID, uuid4

from cmp.modules.identity_access.domain.authorization import AuthorizationDecision, Permission
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.modeling.application.service import (
    MATERIAL_MODEL_AGGREGATE_TYPE,
    MaterialModelService,
    RevisionSnapshot,
)
from cmp.modules.modeling.domain.reference_linear_viscoelasticity import (
    REFERENCE_CALIBRATED_LINEAR_VISCOELASTIC_SCHEMA_ID,
    REFERENCE_CALIBRATED_LINEAR_VISCOELASTIC_SCHEMA_VERSION,
    REFERENCE_LINEAR_VISCOELASTIC_SCHEMA_ID,
    REFERENCE_LINEAR_VISCOELASTIC_SCHEMA_VERSION,
    REFERENCE_PROCESSING_LINEAR_VISCOELASTIC_SCHEMA_DIGEST,
    REFERENCE_PROCESSING_LINEAR_VISCOELASTIC_SCHEMA_ID,
    REFERENCE_PROCESSING_LINEAR_VISCOELASTIC_SCHEMA_VERSION,
    REFERENCE_RECIPE_PROCESSING_LINEAR_VISCOELASTIC_SCHEMA_DIGEST,
    REFERENCE_RECIPE_PROCESSING_LINEAR_VISCOELASTIC_SCHEMA_ID,
    REFERENCE_RECIPE_PROCESSING_LINEAR_VISCOELASTIC_SCHEMA_VERSION,
    BulkRelaxationStatus,
    LinearViscoelasticConflict,
    PronyTerm,
    ReferenceLinearViscoelasticContent,
    ReferencePronyProcessingEvidence,
    ReferencePronyPromotionEvidence,
    ReferenceRecipeBatchEvidence,
)
from cmp.modules.processing.application.common_batches import CommonBatchService
from cmp.modules.processing.application.common_outputs import CommonProcessingOutputService
from cmp.shared.application.revisions import (
    CreateRevisionedAggregate,
    ReviseAggregate,
    RevisionService,
    RevisionStore,
)
from cmp.shared.domain.revisions import TenantScope


@dataclass(frozen=True, slots=True)
class CreateReferenceLinearViscoelasticModel:
    material_state_id: UUID
    property_set_revision_id: UUID
    bulk_relaxation_status: BulkRelaxationStatus
    terms: tuple[PronyTerm, ...]
    change_reason: str


@dataclass(frozen=True, slots=True)
class PromoteReferencePronyCandidate:
    material_model_id: UUID
    baseline_model_revision_id: UUID
    terms: tuple[PronyTerm, PronyTerm]
    evidence: ReferencePronyPromotionEvidence
    change_reason: str


@dataclass(frozen=True, slots=True)
class PromotePronyProcessingOutput:
    material_state_id: UUID
    property_set_revision_id: UUID
    processing_output_id: UUID
    processing_output_revision_id: UUID
    acknowledged_maximum_relative_mismatch: float
    review_acknowledged: bool
    change_reason: str


@dataclass(frozen=True, slots=True)
class LinearViscoelasticModelSnapshot:
    id: UUID
    material_state_id: UUID
    current: RevisionSnapshot[ReferenceLinearViscoelasticContent]


class LinearViscoelasticRepository(Protocol):
    def material_model_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[ReferenceLinearViscoelasticContent]: ...

    def get_material_model(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_model_id: UUID,
    ) -> LinearViscoelasticModelSnapshot: ...

    def list_material_models_for_state(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_state_id: UUID,
    ) -> tuple[LinearViscoelasticModelSnapshot, ...]: ...

    def get_material_model_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_model_id: UUID,
        material_model_revision_id: UUID,
    ) -> RevisionSnapshot[ReferenceLinearViscoelasticContent]: ...


def _require_decision(
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
        raise LinearViscoelasticConflict(
            "authorization decision does not match linear-viscoelastic request"
        )


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
        raise LinearViscoelasticConflict(
            "authorization decision lacks the required Modeling capability"
        )


def _reason(value: str) -> str:
    if not value or value != value.strip() or len(value) > 2_000 or "\x00" in value:
        raise ValueError("change_reason must be trimmed and contain 1..2000 characters")
    return value


class LinearViscoelasticModelService:
    """Manual Prony IR creation with exact Catalog revision lineage."""

    def __init__(
        self,
        *,
        repository: LinearViscoelasticRepository,
        material_models: MaterialModelService,
        processing_outputs: CommonProcessingOutputService | None = None,
        processing_batches: CommonBatchService | None = None,
        id_factory: Callable[[], UUID] = uuid4,
    ) -> None:
        self._repository = repository
        self._material_models = material_models
        self._processing_outputs = processing_outputs
        self._processing_batches = processing_batches
        self._id_factory = id_factory

    def create_model(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CreateReferenceLinearViscoelasticModel,
    ) -> LinearViscoelasticModelSnapshot:
        _require_decision(context, decision, Permission.MODELING_WRITE)
        source = self._material_models.get_reference_property_source_for_linear_viscoelasticity(
            context,
            decision,
            material_state_id=command.material_state_id,
            property_set_revision_id=command.property_set_revision_id,
        )
        if source.material_class not in {"polymer", "elastomer"}:
            raise LinearViscoelasticConflict(
                "linear viscoelasticity requires a polymer- or elastomer-classified "
                "Material revision"
            )
        properties = source.content
        content = ReferenceLinearViscoelasticContent(
            material_id=properties.material_id,
            material_revision_id=properties.material_revision_id,
            material_state_id=properties.material_state_id,
            material_state_revision_id=properties.material_state_revision_id,
            property_set_id=properties.property_set_id,
            property_set_revision_id=properties.property_set_revision_id,
            density_kg_per_m3=properties.density_kg_per_m3,
            youngs_modulus_pa=properties.youngs_modulus_pa,
            poisson_ratio=properties.poisson_ratio,
            bulk_relaxation_status=command.bulk_relaxation_status,
            terms=command.terms,
            applicable_temperature_min_k=properties.applicable_temperature_min_k,
            applicable_temperature_max_k=properties.applicable_temperature_max_k,
            applicable_strain_rate_min_per_s=properties.applicable_strain_rate_min_per_s,
            applicable_strain_rate_max_per_s=properties.applicable_strain_rate_max_per_s,
            applicability_note=properties.applicability_note,
            reference_temperature_k=properties.reference_temperature_k,
        )
        aggregate_id = self._id_factory()
        if aggregate_id.int == 0:
            raise RuntimeError("linear-viscoelastic id_factory returned a zero UUID")
        record = RevisionService(
            aggregate_type=MATERIAL_MODEL_AGGREGATE_TYPE,
            store=self._repository.material_model_store(context, decision),
        ).create(
            CreateRevisionedAggregate(
                aggregate_id=aggregate_id,
                scope=TenantScope(
                    context.organization_id,
                    context.project_id,
                    source.classification.value,
                ),
                schema_id=REFERENCE_LINEAR_VISCOELASTIC_SCHEMA_ID,
                schema_version=REFERENCE_LINEAR_VISCOELASTIC_SCHEMA_VERSION,
                content=content,
                created_by=context.principal.id,
                change_reason=_reason(command.change_reason),
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        return LinearViscoelasticModelSnapshot(
            aggregate_id,
            command.material_state_id,
            RevisionSnapshot(record, content),
        )

    def get_model(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_model_id: UUID,
    ) -> LinearViscoelasticModelSnapshot:
        _require_decision(context, decision, Permission.MODELING_READ)
        return self._repository.get_material_model(
            context=context,
            decision=decision,
            material_model_id=material_model_id,
        )

    async def promote_processing_output(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: PromotePronyProcessingOutput,
    ) -> LinearViscoelasticModelSnapshot:
        """Create one typed IR from server-recomputed selected generalized-Maxwell evidence."""

        _require_decision(context, decision, Permission.MODELING_WRITE)
        if self._processing_outputs is None:
            raise LinearViscoelasticConflict("Processing Output promotion is unavailable")
        if not command.review_acknowledged:
            raise LinearViscoelasticConflict(
                "review of the selected Prony candidate and modulus consistency is required"
            )
        if (
            not math.isfinite(command.acknowledged_maximum_relative_mismatch)
            or not 0 <= command.acknowledged_maximum_relative_mismatch <= 1
        ):
            raise LinearViscoelasticConflict(
                "acknowledged maximum relative mismatch must be within [0,1]"
            )
        properties = self._material_models.get_reference_property_source_for_linear_viscoelasticity(
            context,
            decision,
            material_state_id=command.material_state_id,
            property_set_revision_id=command.property_set_revision_id,
        )
        if properties.material_class not in {"polymer", "elastomer"}:
            raise LinearViscoelasticConflict(
                "processed linear viscoelasticity requires a polymer or elastomer Material"
            )
        output, output_bytes = await self._processing_outputs.export_exact(
            context,
            decision,
            command.processing_output_id,
            command.processing_output_revision_id,
        )
        if output.current.scope.classification != properties.classification.value:
            raise LinearViscoelasticConflict("Processing Output and Property Set scopes differ")
        try:
            document = json.loads(output_bytes)
            stage = document["result"]["stages"][-1]
            step = output.content.steps[-1]
            if (
                stage["method_id"] != "polymer.prony_fit_compare"
                or step.method_id != stage["method_id"]
                or step.method_version != "1.0.0"
            ):
                raise KeyError("final method")
            series = {item["quantity"]: item for item in stage["series"]}
            selected_series = series["modulus.prony.selected"]
            time_series = series[output.content.independent_quantity]
            if selected_series["unit"] != "Pa" or time_series["unit"] != "s":
                raise KeyError("selected units")
            if len(selected_series["values"]) != output.content.final_point_count:
                raise KeyError("selected point count")
            scalars = {item["key"]: item for item in stage["scalar_results"]}
            selected_count_value = float(scalars["prony_selected_term_count"]["value"])
            selected_count = int(selected_count_value)
            if selected_count_value != selected_count or not 1 <= selected_count <= 10:
                raise ValueError("selected term count")
            terms = tuple(
                PronyTerm(
                    g_ratio=float(scalars[f"prony_g_ratio_{ordinal}"]["value"]),
                    k_ratio=0.0,
                    relaxation_time_s=float(scalars[f"prony_relaxation_time_{ordinal}"]["value"]),
                )
                for ordinal in range(1, selected_count + 1)
            )
            normalized_rmse = float(scalars[f"prony_{selected_count}_normalized_rmse"]["value"])
            bic = float(scalars[f"prony_{selected_count}_bic"]["value"])
            fitted_instantaneous = float(scalars["prony_instantaneous_modulus"]["value"])
            selection_mode = str(step.options["selection_mode"])
        except (KeyError, TypeError, ValueError, IndexError) as error:
            raise LinearViscoelasticConflict(
                "Processing Output does not retain the selected generalized-Maxwell contract"
            ) from error
        source = properties.content
        catalog_instantaneous = source.youngs_modulus_pa / (2 * (1 + source.poisson_ratio))
        relative_mismatch = abs(fitted_instantaneous - catalog_instantaneous) / (
            catalog_instantaneous
        )
        execution_origin = (
            self._processing_batches.find_execution_origin(
                context,
                decision,
                output.id,
                output.current.revision_id,
            )
            if self._processing_batches is not None
            else None
        )
        has_recipe_origin = execution_origin is not None
        evidence = ReferencePronyProcessingEvidence(
            processing_output_id=output.id,
            processing_output_revision_id=output.current.revision_id,
            processing_output_sha256=output.content.output_sha256,
            source_test_data_id=output.content.source_document.aggregate_id,
            source_test_data_revision_id=output.content.source_document.revision_id,
            mapping_profile_id=output.content.mapping_profile.aggregate_id,
            mapping_profile_revision_id=output.content.mapping_profile.revision_id,
            selection_mode=selection_mode,
            selected_term_count=selected_count,
            normalized_rmse=normalized_rmse,
            bic=bic,
            fitted_instantaneous_shear_modulus_pa=fitted_instantaneous,
            catalog_instantaneous_shear_modulus_pa=catalog_instantaneous,
            instantaneous_modulus_relative_mismatch=relative_mismatch,
            acknowledged_maximum_relative_mismatch=(command.acknowledged_maximum_relative_mismatch),
            recipe_batch=(
                ReferenceRecipeBatchEvidence(
                    recipe_id=execution_origin.recipe_id,
                    recipe_revision_id=execution_origin.recipe_revision_id,
                    recipe_sha256=execution_origin.recipe_sha256,
                    batch_id=execution_origin.batch_id,
                    batch_member_id=execution_origin.member_id,
                    batch_attempt_id=execution_origin.attempt_id,
                    batch_attempt_no=execution_origin.attempt_no,
                )
                if execution_origin is not None
                else None
            ),
        )
        content = ReferenceLinearViscoelasticContent(
            material_id=source.material_id,
            material_revision_id=source.material_revision_id,
            material_state_id=source.material_state_id,
            material_state_revision_id=source.material_state_revision_id,
            property_set_id=source.property_set_id,
            property_set_revision_id=source.property_set_revision_id,
            density_kg_per_m3=source.density_kg_per_m3,
            youngs_modulus_pa=source.youngs_modulus_pa,
            poisson_ratio=source.poisson_ratio,
            bulk_relaxation_status=BulkRelaxationStatus.NOT_CHARACTERIZED,
            terms=terms,
            applicable_temperature_min_k=source.applicable_temperature_min_k,
            applicable_temperature_max_k=source.applicable_temperature_max_k,
            applicable_strain_rate_min_per_s=source.applicable_strain_rate_min_per_s,
            applicable_strain_rate_max_per_s=source.applicable_strain_rate_max_per_s,
            applicability_note=source.applicability_note,
            reference_temperature_k=source.reference_temperature_k,
            processing_promotion_evidence=evidence,
            model_schema_digest=(
                REFERENCE_RECIPE_PROCESSING_LINEAR_VISCOELASTIC_SCHEMA_DIGEST
                if has_recipe_origin
                else REFERENCE_PROCESSING_LINEAR_VISCOELASTIC_SCHEMA_DIGEST
            ),
        )
        aggregate_id = self._id_factory()
        record = RevisionService(
            aggregate_type=MATERIAL_MODEL_AGGREGATE_TYPE,
            store=self._repository.material_model_store(context, decision),
        ).create(
            CreateRevisionedAggregate(
                aggregate_id=aggregate_id,
                scope=TenantScope(
                    context.organization_id,
                    context.project_id,
                    properties.classification.value,
                ),
                schema_id=(
                    REFERENCE_RECIPE_PROCESSING_LINEAR_VISCOELASTIC_SCHEMA_ID
                    if has_recipe_origin
                    else REFERENCE_PROCESSING_LINEAR_VISCOELASTIC_SCHEMA_ID
                ),
                schema_version=(
                    REFERENCE_RECIPE_PROCESSING_LINEAR_VISCOELASTIC_SCHEMA_VERSION
                    if has_recipe_origin
                    else REFERENCE_PROCESSING_LINEAR_VISCOELASTIC_SCHEMA_VERSION
                ),
                content=content,
                created_by=context.principal.id,
                change_reason=_reason(command.change_reason),
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        return LinearViscoelasticModelSnapshot(
            aggregate_id,
            command.material_state_id,
            RevisionSnapshot(record, content),
        )

    def promote_candidate(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: PromoteReferencePronyCandidate,
    ) -> LinearViscoelasticModelSnapshot:
        _require_decision(context, decision, Permission.MODELING_WRITE)
        baseline = self._repository.get_material_model(
            context=context,
            decision=decision,
            material_model_id=command.material_model_id,
        )
        if baseline.current.record.revision_id != command.baseline_model_revision_id:
            raise LinearViscoelasticConflict(
                "Candidate promotion requires the exact baseline revision to remain current"
            )
        if baseline.current.content.prony_promotion_evidence is not None:
            raise LinearViscoelasticConflict(
                "a promoted linear-Prony revision cannot silently replace its evidence"
            )
        content = replace(
            baseline.current.content,
            terms=command.terms,
            prony_promotion_evidence=command.evidence,
        )
        record = RevisionService(
            aggregate_type=MATERIAL_MODEL_AGGREGATE_TYPE,
            store=self._repository.material_model_store(context, decision),
        ).revise(
            ReviseAggregate(
                aggregate_id=command.material_model_id,
                scope=baseline.current.record.scope,
                expected_current_revision_id=command.baseline_model_revision_id,
                based_on_revision_id=command.baseline_model_revision_id,
                schema_id=REFERENCE_CALIBRATED_LINEAR_VISCOELASTIC_SCHEMA_ID,
                schema_version=REFERENCE_CALIBRATED_LINEAR_VISCOELASTIC_SCHEMA_VERSION,
                content=content,
                created_by=context.principal.id,
                change_reason=_reason(command.change_reason),
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        return LinearViscoelasticModelSnapshot(
            command.material_model_id,
            content.material_state_id,
            RevisionSnapshot(record, content),
        )

    def list_models_for_state(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_state_id: UUID,
    ) -> tuple[LinearViscoelasticModelSnapshot, ...]:
        _require_decision(context, decision, Permission.MODELING_READ)
        return self._repository.list_material_models_for_state(
            context=context,
            decision=decision,
            material_state_id=material_state_id,
        )

    def get_model_revision_for_export(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_model_id: UUID,
        material_model_revision_id: UUID,
    ) -> RevisionSnapshot[ReferenceLinearViscoelasticContent]:
        if decision.permission not in {Permission.EXPORT_READ, Permission.EXPORT_EXECUTE}:
            raise LinearViscoelasticConflict(
                "linear-viscoelastic export requires export.read or export.execute"
            )
        _require_decision(context, decision, decision.permission)
        snapshot = self._repository.get_material_model(
            context=context,
            decision=decision,
            material_model_id=material_model_id,
        )
        if snapshot.current.record.revision_id != material_model_revision_id:
            raise LinearViscoelasticConflict(
                "the exact requested immutable Material Model revision is not current"
            )
        return snapshot.current

    def get_model_revision_for_calibration(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_model_id: UUID,
        material_model_revision_id: UUID,
    ) -> RevisionSnapshot[ReferenceLinearViscoelasticContent]:
        _require_capability(context, decision, Permission.MODELING_READ)
        return self._repository.get_material_model_revision(
            context=context,
            decision=decision,
            material_model_id=material_model_id,
            material_model_revision_id=material_model_revision_id,
        )

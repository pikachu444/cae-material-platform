"""Read-only UXC-06C1 proof adapter; it never reads another module's tables."""

from __future__ import annotations

from uuid import UUID

from cmp.modules.artifacts.domain.content import ArtifactError
from cmp.modules.exporting.application.target_preview import (
    ExactPreviewSource,
    TargetPreviewConflict,
)
from cmp.modules.identity_access.domain.authorization import AuthorizationDecision
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.modeling.application.neutral_material import (
    NeutralMaterialConflict,
    NeutralMaterialNotFound,
    NeutralMaterialService,
)
from cmp.modules.modeling.application.tabulated_plasticity import (
    TabulatedPlasticityModelService,
)
from cmp.modules.modeling.domain.neutral_material import (
    NeutralProcessingSelection,
    NeutralPronyProcessingSelection,
)
from cmp.modules.modeling.domain.reference_isotropic_tabulated_plasticity import (
    TabulatedPlasticityError,
)
from cmp.modules.modeling.domain.reference_processed_tabulated_plasticity import (
    ReferenceProcessedTabulatedPlasticityContent,
)
from cmp.modules.processing.application.common_outputs import (
    CommonPipelineError,
    CommonProcessingOutputService,
    ProcessingOutputNotFound,
)


class TargetPreviewSourceAdapter:
    def __init__(
        self,
        *,
        outputs: CommonProcessingOutputService,
        neutral_materials: NeutralMaterialService,
        tabulated_models: TabulatedPlasticityModelService | None = None,
    ) -> None:
        self._outputs = outputs
        self._neutral_materials = neutral_materials
        self._tabulated_models = tabulated_models

    async def resolve_for_target_preview(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        processing_output_id: UUID,
        processing_output_revision_id: UUID,
        neutral_material_id: UUID,
        neutral_material_revision_id: UUID,
    ) -> ExactPreviewSource:
        try:
            output = self._outputs.get_output_revision_for_export(
                context, decision, processing_output_id, processing_output_revision_id
            )
            neutral = await self._neutral_materials.get_neutral_material_revision_for_export(
                context, decision, neutral_material_id, neutral_material_revision_id
            )
        except (
            ArtifactError,
            CommonPipelineError,
            ProcessingOutputNotFound,
            NeutralMaterialConflict,
            NeutralMaterialNotFound,
        ) as error:
            # The source services own tenant, classification, and not-found
            # distinctions.  Export C1 deliberately exposes none of them.
            raise TargetPreviewConflict("exact target-preview source is unavailable") from error
        proof = output.content.export_provenance
        selection = neutral.document.selection
        if proof is None or not isinstance(
            selection, (NeutralProcessingSelection, NeutralPronyProcessingSelection)
        ):
            raise TargetPreviewConflict("exact governed Processing Output relation is unavailable")
        if (
            selection.processing_output.object_id != output.id
            or selection.processing_output.revision_id != output.current.revision_id
            or selection.processing_output_sha256 != output.content.output_sha256
            or neutral.document.material_model_ir.model.object_id != neutral.id
            or neutral.document.material_model_ir.model.revision_id != neutral.current.revision_id
            or neutral.document.material.object_id != proof.material.aggregate_id
            or neutral.document.material.revision_id != proof.material.revision_id
            or neutral.document.material_state.object_id
            != proof.material_state.aggregate_id
            or neutral.document.material_state.revision_id
            != proof.material_state.revision_id
        ):
            raise TargetPreviewConflict(
                "Neutral/IR does not prove the requested exact Processing Output"
            )
        if isinstance(selection, NeutralProcessingSelection):
            if self._tabulated_models is None:
                raise TargetPreviewConflict("exact target-preview source is unavailable")
            try:
                resolved_model = self._tabulated_models.resolve_processing_output_for_export(
                    context,
                    decision,
                    selection.processing_output.object_id,
                    selection.processing_output.revision_id,
                )
            except TabulatedPlasticityError as error:
                # Export C1 deliberately exposes no missing, restricted, or
                # ambiguous model details from the source service.
                raise TargetPreviewConflict(
                    "exact target-preview source is unavailable"
                ) from error
            content = resolved_model.revision.content
            if not isinstance(content, ReferenceProcessedTabulatedPlasticityContent):
                raise TargetPreviewConflict(
                    "exact governed tabulated-plasticity relation is unavailable"
                )
            if (
                content.processing_output_id != output.id
                or content.processing_output_revision_id != output.current.revision_id
                or content.processing_output_sha256 != output.content.output_sha256
                or content.material_id != proof.material.aggregate_id
                or content.material_revision_id != proof.material.revision_id
                or content.material_state_id != proof.material_state.aggregate_id
                or content.material_state_revision_id != proof.material_state.revision_id
                or content.material_id != neutral.document.material.object_id
                or content.material_revision_id != neutral.document.material.revision_id
                or content.material_state_id != neutral.document.material_state.object_id
                or content.material_state_revision_id != neutral.document.material_state.revision_id
            ):
                raise TargetPreviewConflict(
                    "Neutral/IR does not prove the requested exact Processing Output"
                )
            material_model_ir_revision_id = resolved_model.revision.record.revision_id
        else:
            # Prony/linear-viscoelastic previews retain their existing
            # identity-for-identity behavior and do not consult the
            # tabulated-plasticity resolver.
            material_model_ir_revision_id = neutral.document.material_model_ir.model.revision_id
        return ExactPreviewSource(
            processing_output_id=output.id,
            processing_output_revision_id=output.current.revision_id,
            processing_output_sha256=output.content.output_sha256,
            material_id=proof.material.aggregate_id,
            material_revision_id=proof.material.revision_id,
            material_state_id=proof.material_state.aggregate_id,
            material_state_revision_id=proof.material_state.revision_id,
            material_model_ir_revision_id=material_model_ir_revision_id,
            neutral_material_id=neutral.id,
            neutral_material_revision_id=neutral.current.revision_id,
            neutral=neutral.document,
        )

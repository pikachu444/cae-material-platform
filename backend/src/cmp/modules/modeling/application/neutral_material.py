"""Promote a selected T-55E family Candidate to canonical Neutral Material JSON."""

from __future__ import annotations

import json
import math
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID, uuid4

from cmp.modules.artifacts.application.content import ArtifactService
from cmp.modules.datasets.application.canonical_test_data import CanonicalTestDataService
from cmp.modules.datasets.application.governed_import import GovernedImportService
from cmp.modules.datasets.application.shear_relaxation import ShearRelaxationDatasetService
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
    Permission,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.modeling.application.linear_viscoelasticity import LinearViscoelasticModelService
from cmp.modules.modeling.application.ogden_calibration import (
    ReferenceOgdenCalibrationService,
)
from cmp.modules.modeling.application.ogden_prony import OgdenPronyModelService
from cmp.modules.modeling.application.prony_calibration import ReferencePronyCalibrationService
from cmp.modules.modeling.application.tabulated_plasticity import TabulatedPlasticityModelService
from cmp.modules.modeling.domain.hyperelastic_families import (
    HyperelasticDiagnosticPoint,
    HyperelasticFamily,
    HyperelasticParameter,
)
from cmp.modules.modeling.domain.neutral_material import (
    HYPERELASTIC_CURVE_STAGES,
    NEUTRAL_HYPERELASTIC_IR_SCHEMA_DIGEST,
    NEUTRAL_HYPERELASTIC_IR_SCHEMA_ID,
    NEUTRAL_HYPERELASTIC_IR_SCHEMA_VERSION,
    NEUTRAL_MATERIAL_SCHEMA_REF,
    NEUTRAL_MATERIAL_SCHEMA_VERSION,
    CurveStage,
    EvidenceStatus,
    NeutralArtifactReference,
    NeutralCandidateSelection,
    NeutralCurve,
    NeutralDatasetKind,
    NeutralDatasetRole,
    NeutralDatasetSource,
    NeutralElastoplasticIR,
    NeutralHyperelasticIR,
    NeutralHyperelasticParameters,
    NeutralLinearViscoelasticIR,
    NeutralMaterialDocument,
    NeutralProcessingSelection,
    NeutralPronyOverlay,
    NeutralPronyProcessingSelection,
    NeutralPronyTerm,
    NeutralTestMode,
    OptionalRevisionEvidence,
    RevisionReference,
    neutral_material_from_json_bytes,
)
from cmp.modules.modeling.domain.reference_isotropic_tabulated_plasticity import (
    REFERENCE_HARDENING_CURVE_SCHEMA,
)
from cmp.modules.modeling.domain.reference_linear_viscoelasticity import (
    REFERENCE_CALIBRATED_LINEAR_VISCOELASTIC_SCHEMA_ID,
    REFERENCE_CALIBRATED_LINEAR_VISCOELASTIC_SCHEMA_VERSION,
    REFERENCE_PROCESSING_LINEAR_VISCOELASTIC_SCHEMA_ID,
    REFERENCE_PROCESSING_LINEAR_VISCOELASTIC_SCHEMA_VERSION,
)
from cmp.modules.modeling.domain.reference_ogden_calibration import OgdenCalibrationMember
from cmp.modules.modeling.domain.reference_processed_tabulated_plasticity import (
    REFERENCE_PROCESSED_EXTRAPOLATION_POLICY,
    ReferenceProcessedTabulatedPlasticityContent,
)
from cmp.modules.processing.application.common_outputs import CommonProcessingOutputService
from cmp.shared.application.revisions import (
    CreateRevisionedAggregate,
    RevisionService,
    RevisionStore,
)
from cmp.shared.domain.revisions import RevisionRecord, TenantScope

NEUTRAL_MATERIAL_AGGREGATE_TYPE = "modeling.neutral_material"


class NeutralMaterialConflict(Exception):
    pass


class NeutralMaterialNotFound(Exception):
    pass


@dataclass(frozen=True, slots=True)
class NeutralMaterialRevisionContent:
    document: NeutralMaterialDocument
    document_artifact_id: UUID
    document_artifact_sha256: str


@dataclass(frozen=True, slots=True)
class NeutralMaterialStoredRevision:
    neutral_material_id: UUID
    record: RevisionRecord
    document_artifact_id: UUID
    document_artifact_sha256: str


@dataclass(frozen=True, slots=True)
class NeutralMaterialSnapshot:
    id: UUID
    current: RevisionRecord
    document_artifact_id: UUID
    document_artifact_sha256: str
    document: NeutralMaterialDocument


@dataclass(frozen=True, slots=True)
class PromoteHyperelasticFamilyCandidate:
    candidate_id: UUID
    selection_reason: str
    change_reason: str


@dataclass(frozen=True, slots=True)
class PromoteMetalModelToNeutral:
    material_model_id: UUID
    material_model_revision_id: UUID
    selection_reason: str
    change_reason: str


@dataclass(frozen=True, slots=True)
class PromoteLinearViscoelasticModelToNeutral:
    material_model_id: UUID
    material_model_revision_id: UUID
    selection_reason: str
    change_reason: str


@dataclass(frozen=True, slots=True)
class ImportNeutralMaterial:
    value: bytes
    change_reason: str


class NeutralMaterialRepository(Protocol):
    def neutral_material_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[NeutralMaterialRevisionContent]: ...

    def get_current_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        neutral_material_id: UUID,
    ) -> NeutralMaterialStoredRevision: ...

    def get_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        neutral_material_id: UUID,
        neutral_material_revision_id: UUID,
    ) -> NeutralMaterialStoredRevision: ...

    def find_by_candidate(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        candidate_id: UUID,
    ) -> NeutralMaterialStoredRevision | None: ...


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
        raise NeutralMaterialConflict(
            "authorization decision does not match Neutral Material request"
        )


def _reason(name: str, value: str) -> str:
    if not value or value != value.strip() or len(value) > 2000 or "\x00" in value:
        raise ValueError(f"{name} must be trimmed and contain 1..2000 characters")
    return value


def _typed_parameters(
    family: HyperelasticFamily, parameters: tuple[HyperelasticParameter, ...]
) -> NeutralHyperelasticParameters:
    values = {item.name: item.value for item in parameters}
    expected = {
        HyperelasticFamily.NEO_HOOKEAN: {"c10_pa"},
        HyperelasticFamily.MOONEY_RIVLIN: {"c10_pa", "c01_pa"},
        HyperelasticFamily.YEOH: {"c10_pa", "c20_pa", "c30_pa"},
        HyperelasticFamily.OGDEN_1: {"mu_pa", "alpha"},
    }[family]
    if set(values) != expected:
        raise NeutralMaterialConflict("Candidate parameter contract does not match its family")
    return NeutralHyperelasticParameters(family=family, **values)


def _curve(
    *,
    stage: CurveStage,
    points: tuple[HyperelasticDiagnosticPoint, ...],
) -> NeutralCurve:
    first = points[0]
    y_quantity = {
        CurveStage.NORMALIZED: "stress.nominal.observed",
        CurveStage.FITTED: "stress.nominal.predicted",
        CurveStage.RESIDUAL: "stress.nominal.residual",
    }[stage]
    y = {
        CurveStage.NORMALIZED: tuple(item.observed_nominal_stress_pa for item in points),
        CurveStage.FITTED: tuple(item.predicted_nominal_stress_pa for item in points),
        CurveStage.RESIDUAL: tuple(item.residual_pa for item in points),
    }[stage]
    return NeutralCurve(
        stage=stage,
        dataset_revision_id=first.dataset_revision_id,
        test_mode=NeutralTestMode(first.test_mode.value),
        x_quantity="strain.engineering",
        x_unit="1",
        y_quantity=y_quantity,
        y_unit="Pa",
        x=tuple(item.engineering_strain for item in points),
        y=y,
    )


def _stage_series(
    stages: list[dict[str, object]], x_quantity: str, y_quantity: str, *, reverse: bool = False
) -> tuple[tuple[float, ...], tuple[float, ...]]:
    ordered = reversed(stages) if reverse else iter(stages)
    for stage in ordered:
        raw_series = stage.get("series")
        if not isinstance(raw_series, list):
            continue
        series = {
            str(item.get("quantity")): item.get("values")
            for item in raw_series
            if isinstance(item, dict)
        }
        x = series.get(x_quantity)
        y = series.get(y_quantity)
        if isinstance(x, list) and isinstance(y, list) and x and len(x) == len(y):
            return tuple(float(value) for value in x), tuple(float(value) for value in y)
    raise NeutralMaterialConflict(
        f"Processing Output omits required {x_quantity}/{y_quantity} series"
    )


def _metal_curves(
    value: bytes,
    *,
    dataset_revision_id: UUID,
    characterized_maximum: float,
) -> tuple[NeutralCurve, ...]:
    try:
        document = json.loads(value)
        stages = document["result"]["stages"]
    except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError) as error:
        raise NeutralMaterialConflict("Processing Output JSON structure is invalid") from error
    if not isinstance(stages, list) or not stages:
        raise NeutralMaterialConflict("Processing Output has no curve stages")
    engineering_x, engineering_y = _stage_series(
        stages, "strain.engineering", "stress.engineering"
    )
    plastic_x, plastic_y = _stage_series(
        stages, "strain.true_plastic", "stress.true", reverse=True
    )
    fitted_x, fitted_y = _stage_series(
        stages, "strain.true_plastic", "stress.hardening.selected", reverse=True
    )
    observed = tuple(
        (x, y) for x, y in zip(fitted_x, fitted_y, strict=True) if x <= characterized_maximum
    )
    extension = tuple(
        (x, y) for x, y in zip(fitted_x, fitted_y, strict=True) if x > characterized_maximum
    )
    if not observed or not extension:
        raise NeutralMaterialConflict(
            "selected hardening Output must retain observed and extrapolated domains"
        )

    def curve(
        stage: CurveStage,
        x: tuple[float, ...],
        y: tuple[float, ...],
        x_quantity: str,
        y_quantity: str,
    ) -> NeutralCurve:
        return NeutralCurve(
            stage=stage,
            dataset_revision_id=dataset_revision_id,
            test_mode=NeutralTestMode.UNIAXIAL_TENSION,
            x_quantity=x_quantity,
            x_unit="1",
            y_quantity=y_quantity,
            y_unit="Pa",
            x=x,
            y=y,
        )

    return (
        curve(
            CurveStage.NORMALIZED,
            engineering_x,
            engineering_y,
            "strain.engineering",
            "stress.engineering",
        ),
        curve(
            CurveStage.PROCESSED,
            plastic_x,
            plastic_y,
            "strain.true_plastic",
            "stress.true",
        ),
        curve(
            CurveStage.FITTED,
            tuple(item[0] for item in observed),
            tuple(item[1] for item in observed),
            "strain.true_plastic",
            "stress.hardening.selected",
        ),
        curve(
            CurveStage.EXTRAPOLATED,
            tuple(item[0] for item in extension),
            tuple(item[1] for item in extension),
            "strain.true_plastic",
            "stress.hardening.selected",
        ),
    )


class NeutralMaterialService:
    def __init__(
        self,
        *,
        repository: NeutralMaterialRepository,
        calibrations: ReferenceOgdenCalibrationService,
        datasets: GovernedImportService,
        models: OgdenPronyModelService,
        artifacts: ArtifactService,
        tabulated_models: TabulatedPlasticityModelService | None = None,
        linear_models: LinearViscoelasticModelService | None = None,
        processing_outputs: CommonProcessingOutputService | None = None,
        test_data: CanonicalTestDataService | None = None,
        prony_calibrations: ReferencePronyCalibrationService | None = None,
        shear_datasets: ShearRelaxationDatasetService | None = None,
        id_factory: Callable[[], UUID] = uuid4,
    ) -> None:
        self._repository = repository
        self._calibrations = calibrations
        self._datasets = datasets
        self._models = models
        self._artifacts = artifacts
        self._tabulated_models = tabulated_models
        self._linear_models = linear_models
        self._processing_outputs = processing_outputs
        self._test_data = test_data
        self._prony_calibrations = prony_calibrations
        self._shear_datasets = shear_datasets
        self._id_factory = id_factory

    def _id(self) -> UUID:
        value = self._id_factory()
        if value.int == 0:
            raise RuntimeError("neutral material id_factory returned zero")
        return value

    async def promote_family_candidate(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: PromoteHyperelasticFamilyCandidate,
    ) -> NeutralMaterialSnapshot:
        _require(context, decision, Permission.MODELING_WRITE)
        selection_reason = _reason("selection_reason", command.selection_reason)
        change_reason = _reason("change_reason", command.change_reason)
        if command.candidate_id.int == 0:
            raise ValueError("candidate_id must be non-zero")
        duplicate = self._repository.find_by_candidate(
            context=context,
            decision=decision,
            candidate_id=command.candidate_id,
        )
        if duplicate is not None:
            raise NeutralMaterialConflict(
                "a hyperelastic family Candidate can be promoted only once"
            )
        candidate = self._calibrations.get_family_candidate_for_promotion(
            context, decision, command.candidate_id
        )
        run = self._calibrations.get_run_for_promotion(
            context, decision, candidate.calibration_run_id
        )
        plan = self._calibrations.get_plan_revision_for_promotion(
            context,
            decision,
            run.plan_id,
            run.plan_revision_id,
        )
        baseline = self._models.get_model_revision_for_calibration(
            context,
            decision,
            run.baseline_model_id,
            run.baseline_model_revision_id,
        )
        if candidate.calibration_run_id != run.id:
            raise NeutralMaterialConflict("Candidate does not belong to the selected Run")
        if plan.current.record.revision_id != run.plan_revision_id:
            raise NeutralMaterialConflict("Run no longer resolves to its exact Plan revision")
        if baseline.record.revision_id != run.baseline_model_revision_id:
            raise NeutralMaterialConflict("Run baseline model revision could not be resolved")
        if candidate.diagnostics_artifact_id is None or candidate.diagnostics_sha256 is None:
            raise NeutralMaterialConflict("Candidate diagnostics Artifact is required")
        diagnostics = await self._calibrations.family_candidate_diagnostics_for_promotion(
            context, decision, command.candidate_id
        )
        grouped: list[tuple[OgdenCalibrationMember, tuple[HyperelasticDiagnosticPoint, ...]]] = []
        sources: list[NeutralDatasetSource] = []
        for member in plan.current.content.members:
            dataset = self._datasets.get_dataset_revision_for_calibration(
                context,
                decision,
                member.dataset_id,
                member.dataset_revision_id,
            )
            if dataset.record.revision_id != member.dataset_revision_id:
                raise NeutralMaterialConflict("Plan Dataset revision could not be resolved")
            points = tuple(
                item
                for item in diagnostics
                if item.dataset_revision_id == member.dataset_revision_id
            )
            if not points:
                raise NeutralMaterialConflict("Candidate diagnostics omit a Plan Dataset")
            grouped.append((member, points))
            sources.append(
                NeutralDatasetSource(
                    dataset=RevisionReference(member.dataset_id, member.dataset_revision_id),
                    role=NeutralDatasetRole(member.role.value),
                    test_mode=NeutralTestMode(member.test_mode.value),
                    normalized_artifact_id=dataset.content.data_artifact_id,
                    normalized_artifact_sha256=dataset.content.data_sha256,
                )
            )

        neutral_material_id = self._id()
        neutral_revision_id = self._id()
        curves = tuple(
            _curve(stage=stage, points=points)
            for _member, points in grouped
            for stage in HYPERELASTIC_CURVE_STAGES
        )
        content = baseline.content
        document = NeutralMaterialDocument(
            document_id=neutral_material_id,
            organization_id=context.organization_id,
            project_id=context.project_id,
            classification=run.classification.value,
            material=RevisionReference(content.material_id, content.material_revision_id),
            material_state=RevisionReference(
                content.material_state_id, content.material_state_revision_id
            ),
            property_set=RevisionReference(
                content.property_set_id, content.property_set_revision_id
            ),
            calibration_plan=RevisionReference(run.plan_id, run.plan_revision_id),
            scientific_profile=RevisionReference(
                run.scientific_profile_id, run.scientific_profile_revision_id
            ),
            mapping_profile=OptionalRevisionEvidence(
                EvidenceStatus.NOT_APPLICABLE,
                "T-55E consumed governed normalized Dataset revisions directly.",
            ),
            processing_recipe=OptionalRevisionEvidence(
                EvidenceStatus.NOT_APPLICABLE,
                "This exact reference run did not use a T-54 Processing Recipe.",
            ),
            source_datasets=tuple(sources),
            curves=curves,
            selection=NeutralCandidateSelection(
                calibration_run_id=run.id,
                candidate_id=candidate.id,
                candidate_sha256=candidate.value.candidate_sha256,
                diagnostics_artifact_id=candidate.diagnostics_artifact_id,
                diagnostics_sha256=candidate.diagnostics_sha256,
                reason=selection_reason,
                objective_total=candidate.value.objective_total,
                calibration_normalized_rmse=candidate.value.calibration_normalized_rmse,
                holdout_normalized_rmse=candidate.value.holdout_normalized_rmse,
                stability_status=candidate.value.stability_status,
                warnings=candidate.value.warnings,
            ),
            material_model_ir=NeutralHyperelasticIR(
                model=RevisionReference(neutral_material_id, neutral_revision_id),
                schema_id=NEUTRAL_HYPERELASTIC_IR_SCHEMA_ID,
                schema_version=NEUTRAL_HYPERELASTIC_IR_SCHEMA_VERSION,
                model_schema_digest=NEUTRAL_HYPERELASTIC_IR_SCHEMA_DIGEST,
                parameters=_typed_parameters(
                    candidate.value.family, tuple(candidate.value.parameters)
                ),
                density_kg_per_m3=content.density_kg_per_m3,
                volumetric_response="incompressible",
                prony_overlay=NeutralPronyOverlay(
                    EvidenceStatus.EXACT_REVISION,
                    "Preserved the exact shear-Prony overlay from the calibration baseline.",
                    terms=tuple(
                        NeutralPronyTerm(
                            ordinal=ordinal,
                            g_ratio=term.g_ratio,
                            k_ratio=0.0,
                            relaxation_time_s=term.relaxation_time_s,
                        )
                        for ordinal, term in enumerate(content.prony_terms, 1)
                    ),
                    source_model=RevisionReference(
                        run.baseline_model_id, run.baseline_model_revision_id
                    ),
                ),
            ),
            applicable_strain_min=min(item.engineering_strain for item in diagnostics),
            applicable_strain_max=max(item.engineering_strain for item in diagnostics),
            validation_status=(
                "reference_numerical_checks_passed"
                if candidate.value.stability_status == "monotonic_on_fitted_domain"
                else "reference_numerical_warning"
            ),
        )
        artifact = await self._artifacts.finalize_derived_bytes(
            context,
            decision,
            classification=DataClassification(run.classification.value),
            artifact_role="modeling.neutral_material_json",
            schema_ref=NEUTRAL_MATERIAL_SCHEMA_REF,
            media_type="application/json",
            value=document.to_json_bytes(),
            idempotency_key=f"neutral-material:{neutral_material_id}:revision:{neutral_revision_id}",
        )
        revision_content = NeutralMaterialRevisionContent(
            document=document,
            document_artifact_id=artifact.artifact.id,
            document_artifact_sha256=artifact.artifact.sha256,
        )
        record = RevisionService(
            aggregate_type=NEUTRAL_MATERIAL_AGGREGATE_TYPE,
            store=self._repository.neutral_material_store(context, decision),
            id_factory=lambda: neutral_revision_id,
        ).create(
            CreateRevisionedAggregate(
                aggregate_id=neutral_material_id,
                scope=TenantScope(
                    context.organization_id,
                    context.project_id,
                    run.classification.value,
                ),
                schema_id=NEUTRAL_HYPERELASTIC_IR_SCHEMA_ID,
                schema_version=NEUTRAL_MATERIAL_SCHEMA_VERSION,
                content=revision_content,
                created_by=context.principal.id,
                change_reason=change_reason,
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        return NeutralMaterialSnapshot(
            neutral_material_id,
            record,
            artifact.artifact.id,
            artifact.artifact.sha256,
            document,
        )

    async def _persist_new_document(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        *,
        document: NeutralMaterialDocument,
        neutral_revision_id: UUID,
        schema_id: str,
        classification: DataClassification,
        change_reason: str,
    ) -> NeutralMaterialSnapshot:
        artifact = await self._artifacts.finalize_derived_bytes(
            context,
            decision,
            classification=classification,
            artifact_role="modeling.neutral_material_json",
            schema_ref=NEUTRAL_MATERIAL_SCHEMA_REF,
            media_type="application/json",
            value=document.to_json_bytes(),
            idempotency_key=(
                f"neutral-material:{document.document_id}:revision:{neutral_revision_id}"
            ),
        )
        revision_content = NeutralMaterialRevisionContent(
            document=document,
            document_artifact_id=artifact.artifact.id,
            document_artifact_sha256=artifact.artifact.sha256,
        )
        record = RevisionService(
            aggregate_type=NEUTRAL_MATERIAL_AGGREGATE_TYPE,
            store=self._repository.neutral_material_store(context, decision),
            id_factory=lambda: neutral_revision_id,
        ).create(
            CreateRevisionedAggregate(
                aggregate_id=document.document_id,
                scope=TenantScope(
                    context.organization_id,
                    context.project_id,
                    classification.value,
                ),
                schema_id=schema_id,
                schema_version=NEUTRAL_MATERIAL_SCHEMA_VERSION,
                content=revision_content,
                created_by=context.principal.id,
                change_reason=change_reason,
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        return NeutralMaterialSnapshot(
            document.document_id,
            record,
            artifact.artifact.id,
            artifact.artifact.sha256,
            document,
        )

    async def promote_metal_model(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: PromoteMetalModelToNeutral,
    ) -> NeutralMaterialSnapshot:
        """Promote one selected T-55M Processing Output-backed metal IR."""

        _require(context, decision, Permission.MODELING_WRITE)
        if (
            self._tabulated_models is None
            or self._processing_outputs is None
            or self._test_data is None
        ):
            raise NeutralMaterialConflict("metal Neutral promotion service is unavailable")
        selection_reason = _reason("selection_reason", command.selection_reason)
        change_reason = _reason("change_reason", command.change_reason)
        model = self._tabulated_models.get_model_revision_for_export(
            context,
            decision,
            command.material_model_id,
            command.material_model_revision_id,
        )
        content = model.content
        if not isinstance(content, ReferenceProcessedTabulatedPlasticityContent):
            raise NeutralMaterialConflict(
                "metal Neutral promotion requires a selected Processing Output IR"
            )
        output, output_bytes = await self._processing_outputs.export_exact(
            context,
            decision,
            content.processing_output_id,
            content.processing_output_revision_id,
        )
        if (
            output.content.output_sha256 != content.processing_output_sha256
            or output.content.source_document.aggregate_id != content.source_test_data_id
            or output.content.source_document.revision_id != content.source_test_data_revision_id
            or output.content.mapping_profile.aggregate_id != content.mapping_profile_id
            or output.content.mapping_profile.revision_id != content.mapping_profile_revision_id
        ):
            raise NeutralMaterialConflict(
                "metal IR no longer resolves to its exact Processing/Profile/Test evidence"
            )
        source, _source_bytes = await self._test_data.export_document(
            context,
            decision,
            content.source_test_data_id,
            content.source_test_data_revision_id,
        )
        neutral_id = self._id()
        neutral_revision_id = self._id()
        classification = DataClassification(model.record.scope.classification)
        document = NeutralMaterialDocument(
            document_id=neutral_id,
            organization_id=context.organization_id,
            project_id=context.project_id,
            classification=classification.value,
            material=RevisionReference(content.material_id, content.material_revision_id),
            material_state=RevisionReference(
                content.material_state_id, content.material_state_revision_id
            ),
            property_set=RevisionReference(
                content.property_set_id, content.property_set_revision_id
            ),
            calibration_plan=OptionalRevisionEvidence(
                EvidenceStatus.NOT_APPLICABLE,
                "The selected metal IR was produced by a versioned Processing Output.",
            ),
            scientific_profile=OptionalRevisionEvidence(
                EvidenceStatus.NOT_APPLICABLE,
                "Metal hardening options are pinned by the Processing Output steps.",
            ),
            mapping_profile=OptionalRevisionEvidence(
                EvidenceStatus.EXACT_REVISION,
                "Exact Mapping Profile consumed by the selected Processing Output.",
                RevisionReference(content.mapping_profile_id, content.mapping_profile_revision_id),
            ),
            processing_recipe=OptionalRevisionEvidence(
                EvidenceStatus.NOT_APPLICABLE,
                "This selected Output was committed from explicit ordered steps, not a Recipe.",
            ),
            source_datasets=(
                NeutralDatasetSource(
                    dataset=RevisionReference(
                        content.source_test_data_id, content.source_test_data_revision_id
                    ),
                    role=NeutralDatasetRole.PROCESSING_INPUT,
                    test_mode=NeutralTestMode.UNIAXIAL_TENSION,
                    normalized_artifact_id=source.content.normalized_artifact_id,
                    normalized_artifact_sha256=source.content.normalized_sha256,
                    source_kind=NeutralDatasetKind.TEST_DATA_DOCUMENT,
                ),
            ),
            curves=_metal_curves(
                output_bytes,
                dataset_revision_id=content.source_test_data_revision_id,
                characterized_maximum=content.characterized_max_true_plastic_strain,
            ),
            selection=NeutralProcessingSelection(
                processing_output=RevisionReference(
                    content.processing_output_id, content.processing_output_revision_id
                ),
                processing_output_sha256=content.processing_output_sha256,
                reason=selection_reason,
                selected_series="stress.hardening.selected",
                candidate_families=content.candidate_families,
                primary_family=content.primary_family,
                secondary_family=content.secondary_family,
                primary_weight=content.primary_weight,
                warnings=("post-necking extension is an acknowledged approximation",),
            ),
            material_model_ir=NeutralElastoplasticIR(
                model=RevisionReference(neutral_id, neutral_revision_id),
                schema_id=model.record.schema_id,
                schema_version=model.record.schema_version,
                model_schema_digest=content.model_schema_digest,
                density_kg_per_m3=content.density_kg_per_m3,
                youngs_modulus_pa=content.youngs_modulus_pa,
                poisson_ratio=content.poisson_ratio,
                initial_yield_stress_pa=content.initial_yield_stress_pa,
                hardening_curve=NeutralArtifactReference(
                    content.hardening_curve_artifact_id,
                    content.hardening_curve_sha256,
                    REFERENCE_HARDENING_CURVE_SCHEMA,
                    content.hardening_curve_point_count,
                ),
                candidate_families=content.candidate_families,
                primary_family=content.primary_family,
                secondary_family=content.secondary_family,
                primary_weight=content.primary_weight,
                characterized_max_true_plastic_strain=(
                    content.characterized_max_true_plastic_strain
                ),
                extension_max_true_plastic_strain=(
                    content.extension_max_true_plastic_strain
                ),
                extrapolation_policy=REFERENCE_PROCESSED_EXTRAPOLATION_POLICY,
                approximation_acknowledged=(
                    content.post_necking_approximation_acknowledged
                ),
            ),
            applicable_strain_min=content.fit_minimum_true_plastic_strain,
            applicable_strain_max=content.extension_max_true_plastic_strain,
            validation_status="reference_processing_and_monotonicity_checks_passed",
        )
        return await self._persist_new_document(
            context,
            decision,
            document=document,
            neutral_revision_id=neutral_revision_id,
            schema_id=model.record.schema_id,
            classification=classification,
            change_reason=change_reason,
        )

    async def promote_linear_viscoelastic_model(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: PromoteLinearViscoelasticModelToNeutral,
    ) -> NeutralMaterialSnapshot:
        """Promote one reviewed generalized-Maxwell model and exact diagnostics."""

        _require(context, decision, Permission.MODELING_WRITE)
        if self._linear_models is None:
            raise NeutralMaterialConflict("linear-viscoelastic Neutral promotion is unavailable")
        selection_reason = _reason("selection_reason", command.selection_reason)
        change_reason = _reason("change_reason", command.change_reason)
        model = self._linear_models.get_model_revision_for_calibration(
            context,
            decision,
            command.material_model_id,
            command.material_model_revision_id,
        )
        content = model.content
        processing_evidence = content.processing_promotion_evidence
        if processing_evidence is not None:
            if self._processing_outputs is None or self._test_data is None:
                raise NeutralMaterialConflict(
                    "Processing Output Neutral promotion is unavailable"
                )
            output, output_bytes = await self._processing_outputs.export_exact(
                context,
                decision,
                processing_evidence.processing_output_id,
                processing_evidence.processing_output_revision_id,
            )
            source, _ = await self._test_data.export_document(
                context,
                decision,
                processing_evidence.source_test_data_id,
                processing_evidence.source_test_data_revision_id,
            )
            try:
                output_document = json.loads(output_bytes)
                stage = output_document["result"]["stages"][-1]
                series = {item["quantity"]: item for item in stage["series"]}
                scalars = {item["key"]: item for item in stage["scalar_results"]}
                independent = series[output.content.independent_quantity]
                observed = series["modulus.shear.relaxation"]
                fitted = series["modulus.prony.selected"]
                times = tuple(float(value) for value in independent["values"])
                observed_values = tuple(float(value) for value in observed["values"])
                fitted_values = tuple(float(value) for value in fitted["values"])
                selected_count = int(scalars["prony_selected_term_count"]["value"])
                terms = tuple(
                    (
                        float(scalars[f"prony_g_ratio_{ordinal}"]["value"]),
                        float(scalars[f"prony_relaxation_time_{ordinal}"]["value"]),
                    )
                    for ordinal in range(1, selected_count + 1)
                )
            except (KeyError, TypeError, ValueError, IndexError) as error:
                raise NeutralMaterialConflict(
                    "Processing Output does not reproduce the selected Prony evidence"
                ) from error
            if (
                output.id != processing_evidence.processing_output_id
                or output.current.revision_id
                != processing_evidence.processing_output_revision_id
                or output.content.output_sha256
                != processing_evidence.processing_output_sha256
                or output.content.source_document.aggregate_id
                != processing_evidence.source_test_data_id
                or output.content.source_document.revision_id
                != processing_evidence.source_test_data_revision_id
                or output.content.mapping_profile.aggregate_id
                != processing_evidence.mapping_profile_id
                or output.content.mapping_profile.revision_id
                != processing_evidence.mapping_profile_revision_id
                or stage["method_id"] != "polymer.prony_fit_compare"
                or independent["unit"] != "s"
                or observed["unit"] != "Pa"
                or fitted["unit"] != "Pa"
                or selected_count != processing_evidence.selected_term_count
                or len(times) != output.content.final_point_count
                or len(observed_values) != len(times)
                or len(fitted_values) != len(times)
                or terms
                != tuple((term.g_ratio, term.relaxation_time_s) for term in content.terms)
            ):
                raise NeutralMaterialConflict(
                    "selected generalized-Maxwell IR no longer resolves to exact "
                    "Processing evidence"
                )

            def processing_curve(
                stage_name: CurveStage, quantity: str, values: tuple[float, ...]
            ) -> NeutralCurve:
                return NeutralCurve(
                    stage=stage_name,
                    dataset_revision_id=source.current.revision_id,
                    test_mode=NeutralTestMode.STRESS_RELAXATION,
                    x_quantity=output.content.independent_quantity,
                    x_unit="s",
                    y_quantity=quantity,
                    y_unit="Pa",
                    x=times,
                    y=values,
                )

            neutral_id = self._id()
            neutral_revision_id = self._id()
            classification = DataClassification(model.record.scope.classification)
            mismatch_warning = (
                f"catalog/fitted instantaneous shear-modulus relative mismatch="
                f"{processing_evidence.instantaneous_modulus_relative_mismatch:.6g}"
            )
            document = NeutralMaterialDocument(
                document_id=neutral_id,
                organization_id=context.organization_id,
                project_id=context.project_id,
                classification=classification.value,
                material=RevisionReference(content.material_id, content.material_revision_id),
                material_state=RevisionReference(
                    content.material_state_id, content.material_state_revision_id
                ),
                property_set=RevisionReference(
                    content.property_set_id, content.property_set_revision_id
                ),
                calibration_plan=OptionalRevisionEvidence(
                    EvidenceStatus.NOT_APPLICABLE,
                    "The reviewed common Processing Output is not a Calibration Plan.",
                ),
                scientific_profile=OptionalRevisionEvidence(
                    EvidenceStatus.NOT_APPLICABLE,
                    "The versioned Processing steps retain their numerical options.",
                ),
                mapping_profile=OptionalRevisionEvidence(
                    EvidenceStatus.EXACT_REVISION,
                    "The Processing Output pins the exact Mapping Profile revision.",
                    RevisionReference(
                        processing_evidence.mapping_profile_id,
                        processing_evidence.mapping_profile_revision_id,
                    ),
                ),
                processing_recipe=(
                    OptionalRevisionEvidence(
                        EvidenceStatus.EXACT_REVISION,
                        "Exact published Recipe executed by the successful Batch attempt.",
                        RevisionReference(
                            processing_evidence.recipe_batch.recipe_id,
                            processing_evidence.recipe_batch.recipe_revision_id,
                        ),
                    )
                    if processing_evidence.recipe_batch is not None
                    else OptionalRevisionEvidence(
                        EvidenceStatus.NOT_APPLICABLE,
                        "This historical Output was committed without a Recipe/Batch pin.",
                    )
                ),
                source_datasets=(
                    NeutralDatasetSource(
                        dataset=RevisionReference(source.id, source.current.revision_id),
                        role=NeutralDatasetRole.PROCESSING_INPUT,
                        test_mode=NeutralTestMode.STRESS_RELAXATION,
                        normalized_artifact_id=source.content.normalized_artifact_id,
                        normalized_artifact_sha256=source.content.normalized_sha256,
                        source_kind=NeutralDatasetKind.TEST_DATA_DOCUMENT,
                    ),
                ),
                curves=(
                    processing_curve(
                        CurveStage.NORMALIZED,
                        "modulus.shear.relaxation",
                        observed_values,
                    ),
                    processing_curve(
                        CurveStage.FITTED, "modulus.prony.selected", fitted_values
                    ),
                    processing_curve(
                        CurveStage.RESIDUAL,
                        "modulus.shear.residual",
                        tuple(
                            fitted_value - observed_value
                            for fitted_value, observed_value in zip(
                                fitted_values, observed_values, strict=True
                            )
                        ),
                    ),
                ),
                selection=NeutralPronyProcessingSelection(
                    processing_output=RevisionReference(output.id, output.current.revision_id),
                    processing_output_sha256=output.content.output_sha256,
                    reason=selection_reason,
                    selected_series="modulus.prony.selected",
                    selection_mode=processing_evidence.selection_mode,
                    selected_term_count=processing_evidence.selected_term_count,
                    normalized_rmse=processing_evidence.normalized_rmse,
                    bic=processing_evidence.bic,
                    fitted_instantaneous_shear_modulus_pa=(
                        processing_evidence.fitted_instantaneous_shear_modulus_pa
                    ),
                    catalog_instantaneous_shear_modulus_pa=(
                        processing_evidence.catalog_instantaneous_shear_modulus_pa
                    ),
                    instantaneous_modulus_relative_mismatch=(
                        processing_evidence.instantaneous_modulus_relative_mismatch
                    ),
                    acknowledged_maximum_relative_mismatch=(
                        processing_evidence.acknowledged_maximum_relative_mismatch
                    ),
                    warnings=(mismatch_warning,),
                ),
                material_model_ir=NeutralLinearViscoelasticIR(
                    model=RevisionReference(neutral_id, neutral_revision_id),
                    schema_id=REFERENCE_PROCESSING_LINEAR_VISCOELASTIC_SCHEMA_ID,
                    schema_version=REFERENCE_PROCESSING_LINEAR_VISCOELASTIC_SCHEMA_VERSION,
                    model_schema_digest=content.model_schema_digest,
                    density_kg_per_m3=content.density_kg_per_m3,
                    youngs_modulus_pa=content.youngs_modulus_pa,
                    poisson_ratio=content.poisson_ratio,
                    bulk_relaxation_status=content.bulk_relaxation_status.value,
                    terms=tuple(
                        NeutralPronyTerm(
                            ordinal=ordinal,
                            g_ratio=term.g_ratio,
                            k_ratio=term.k_ratio,
                            relaxation_time_s=term.relaxation_time_s,
                        )
                        for ordinal, term in enumerate(content.terms, 1)
                    ),
                    reference_temperature_k=content.reference_temperature_k,
                ),
                applicable_strain_min=None,
                applicable_strain_max=None,
                applicable_time_min_s=min(times),
                applicable_time_max_s=max(times),
                validation_status="reviewed_processing_prony_fit_and_modulus_consistency",
            )
            return await self._persist_new_document(
                context,
                decision,
                document=document,
                neutral_revision_id=neutral_revision_id,
                schema_id=REFERENCE_PROCESSING_LINEAR_VISCOELASTIC_SCHEMA_ID,
                classification=classification,
                change_reason=change_reason,
            )

        if self._prony_calibrations is None or self._shear_datasets is None:
            raise NeutralMaterialConflict("calibrated Prony Neutral promotion is unavailable")
        evidence = content.prony_promotion_evidence
        if evidence is None:
            raise NeutralMaterialConflict(
                "linear-viscoelastic Neutral promotion requires a reviewed Prony Candidate"
            )
        run = self._prony_calibrations.get_run_for_promotion(
            context, decision, evidence.calibration_run_id
        )
        candidate = self._prony_calibrations.get_candidate_for_promotion(
            context, decision, evidence.calibration_candidate_id
        )
        plan = self._prony_calibrations.get_plan_revision_for_promotion(
            context, decision, run.plan_id, run.plan_revision_id
        )
        dataset = self._shear_datasets.get_revision_for_calibration(
            context, decision, run.input_dataset_id, run.input_dataset_revision_id
        )
        diagnostics = await self._prony_calibrations.candidate_diagnostics_for_promotion(
            context, decision, candidate.id
        )
        if (
            candidate.calibration_run_id != run.id
            or candidate.value.candidate_sha256 != evidence.candidate_sha256
            or candidate.diagnostics_artifact_id != evidence.diagnostics_artifact_id
            or candidate.diagnostics_sha256 != evidence.diagnostics_sha256
            or plan.record.revision_id != run.plan_revision_id
            or dataset.record.revision_id != run.input_dataset_revision_id
        ):
            raise NeutralMaterialConflict(
                "selected generalized-Maxwell IR no longer resolves to exact evidence"
            )
        times = tuple(float(item["time_s"]) for item in diagnostics)

        def diagnostic_curve(stage: CurveStage, key: str, quantity: str) -> NeutralCurve:
            return NeutralCurve(
                stage=stage,
                dataset_revision_id=run.input_dataset_revision_id,
                test_mode=NeutralTestMode.STRESS_RELAXATION,
                x_quantity="time",
                x_unit="s",
                y_quantity=quantity,
                y_unit="Pa",
                x=times,
                y=tuple(float(item[key]) for item in diagnostics),
            )

        neutral_id = self._id()
        neutral_revision_id = self._id()
        classification = DataClassification(model.record.scope.classification)
        value = candidate.value
        warnings = tuple(
            message
            for enabled, message in (
                (value.parameter_at_bound, "one or more fitted parameters are at a bound"),
                (
                    value.identifiability_status != "full_rank",
                    f"identifiability={value.identifiability_status}",
                ),
                (
                    value.uncertainty_status != "estimated",
                    f"uncertainty={value.uncertainty_status}",
                ),
            )
            if enabled
        )
        document = NeutralMaterialDocument(
            document_id=neutral_id,
            organization_id=context.organization_id,
            project_id=context.project_id,
            classification=classification.value,
            material=RevisionReference(content.material_id, content.material_revision_id),
            material_state=RevisionReference(
                content.material_state_id, content.material_state_revision_id
            ),
            property_set=RevisionReference(
                content.property_set_id, content.property_set_revision_id
            ),
            calibration_plan=RevisionReference(run.plan_id, run.plan_revision_id),
            scientific_profile=OptionalRevisionEvidence(
                EvidenceStatus.NOT_APPLICABLE,
                "The bounded Prony Plan pins its numerical options directly.",
            ),
            mapping_profile=OptionalRevisionEvidence(
                EvidenceStatus.NOT_APPLICABLE,
                "The governed relaxation Dataset already has typed time/modulus channels.",
            ),
            processing_recipe=OptionalRevisionEvidence(
                EvidenceStatus.NOT_APPLICABLE,
                "The exact processed relaxation Dataset predates the common Recipe path.",
            ),
            source_datasets=(
                NeutralDatasetSource(
                    dataset=RevisionReference(run.input_dataset_id, run.input_dataset_revision_id),
                    role=NeutralDatasetRole.CALIBRATION,
                    test_mode=NeutralTestMode.STRESS_RELAXATION,
                    normalized_artifact_id=dataset.content.data_artifact_id,
                    normalized_artifact_sha256=dataset.content.data_sha256,
                    source_kind=NeutralDatasetKind.SHEAR_RELAXATION_DATASET,
                ),
            ),
            curves=(
                diagnostic_curve(
                    CurveStage.NORMALIZED,
                    "observed_shear_modulus_pa",
                    "modulus.shear.observed",
                ),
                diagnostic_curve(
                    CurveStage.FITTED,
                    "predicted_shear_modulus_pa",
                    "modulus.shear.predicted",
                ),
                diagnostic_curve(CurveStage.RESIDUAL, "residual_pa", "modulus.shear.residual"),
            ),
            selection=NeutralCandidateSelection(
                calibration_run_id=run.id,
                candidate_id=candidate.id,
                candidate_sha256=value.candidate_sha256,
                diagnostics_artifact_id=candidate.diagnostics_artifact_id,
                diagnostics_sha256=candidate.diagnostics_sha256,
                reason=selection_reason,
                objective_total=value.objective_total,
                calibration_normalized_rmse=math.sqrt(max(value.objective_total, 0.0)),
                holdout_normalized_rmse=None,
                stability_status=value.status,
                warnings=warnings,
            ),
            material_model_ir=NeutralLinearViscoelasticIR(
                model=RevisionReference(neutral_id, neutral_revision_id),
                schema_id=REFERENCE_CALIBRATED_LINEAR_VISCOELASTIC_SCHEMA_ID,
                schema_version=REFERENCE_CALIBRATED_LINEAR_VISCOELASTIC_SCHEMA_VERSION,
                model_schema_digest=content.model_schema_digest,
                density_kg_per_m3=content.density_kg_per_m3,
                youngs_modulus_pa=content.youngs_modulus_pa,
                poisson_ratio=content.poisson_ratio,
                bulk_relaxation_status=content.bulk_relaxation_status.value,
                terms=tuple(
                    NeutralPronyTerm(
                        ordinal=ordinal,
                        g_ratio=term.g_ratio,
                        k_ratio=term.k_ratio,
                        relaxation_time_s=term.relaxation_time_s,
                    )
                    for ordinal, term in enumerate(content.terms, 1)
                ),
                reference_temperature_k=content.reference_temperature_k,
            ),
            applicable_strain_min=None,
            applicable_strain_max=None,
            applicable_time_min_s=min(times),
            applicable_time_max_s=max(times),
            validation_status="reference_prony_convergence_and_bounds_checked",
        )
        return await self._persist_new_document(
            context,
            decision,
            document=document,
            neutral_revision_id=neutral_revision_id,
            schema_id=REFERENCE_CALIBRATED_LINEAR_VISCOELASTIC_SCHEMA_ID,
            classification=classification,
            change_reason=change_reason,
        )

    async def get_neutral_material(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        neutral_material_id: UUID,
    ) -> NeutralMaterialSnapshot:
        _require(context, decision, Permission.MODELING_READ)
        stored = self._repository.get_current_revision(
            context=context,
            decision=decision,
            neutral_material_id=neutral_material_id,
        )
        return await self._snapshot_from_stored(context, decision, stored)

    async def get_neutral_material_revision_for_export(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        neutral_material_id: UUID,
        neutral_material_revision_id: UUID,
    ) -> NeutralMaterialSnapshot:
        """Expose one exact immutable Neutral revision through the Exporting boundary."""

        if decision.permission not in {Permission.EXPORT_READ, Permission.EXPORT_EXECUTE}:
            raise NeutralMaterialConflict("Neutral Material export permission is required")
        _require(context, decision, decision.permission)
        stored = self._repository.get_revision(
            context=context,
            decision=decision,
            neutral_material_id=neutral_material_id,
            neutral_material_revision_id=neutral_material_revision_id,
        )
        return await self._snapshot_from_stored(context, decision, stored)

    async def _snapshot_from_stored(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        stored: NeutralMaterialStoredRevision,
    ) -> NeutralMaterialSnapshot:
        artifact, value = await self._artifacts.read_verified_bytes(
            context,
            decision,
            stored.document_artifact_id,
            maximum_bytes=32 * 1024 * 1024,
        )
        if artifact.artifact.sha256 != stored.document_artifact_sha256:
            raise NeutralMaterialConflict("stored Neutral Material Artifact digest changed")
        document = neutral_material_from_json_bytes(value)
        if (
            document.document_id != stored.neutral_material_id
            or document.material_model_ir.model.revision_id != stored.record.revision_id
        ):
            raise NeutralMaterialConflict("Neutral Material JSON does not pin its stored revision")
        return NeutralMaterialSnapshot(
            stored.neutral_material_id,
            stored.record,
            stored.document_artifact_id,
            stored.document_artifact_sha256,
            document,
        )

    async def import_neutral_material(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: ImportNeutralMaterial,
    ) -> NeutralMaterialSnapshot:
        """Import exact canonical bytes, preserving their identity and IR revision IDs."""

        _require(context, decision, Permission.MODELING_WRITE)
        change_reason = _reason("change_reason", command.change_reason)
        if not command.value or len(command.value) > 25 * 1024 * 1024:
            raise ValueError("Neutral Material JSON must contain 1 byte..25 MiB")
        document = neutral_material_from_json_bytes(command.value)
        if (
            document.organization_id != context.organization_id
            or document.project_id != context.project_id
        ):
            raise NeutralMaterialConflict("Neutral Material JSON belongs to another tenant scope")
        if (
            document.material_model_ir.model.object_id != document.document_id
            or document.material_model_ir.model.revision_id.int == 0
        ):
            raise NeutralMaterialConflict(
                "imported Material Model IR must pin the document identity and exact revision"
            )
        selection = document.selection
        material_ir = document.material_model_ir
        calibration_plan = document.calibration_plan
        scientific_profile = document.scientific_profile
        try:
            existing = self._repository.get_current_revision(
                context=context,
                decision=decision,
                neutral_material_id=document.document_id,
            )
        except NeutralMaterialNotFound:
            existing = None
        if existing is not None:
            snapshot = await self._snapshot_from_stored(context, decision, existing)
            if snapshot.document.to_json_bytes() != document.to_json_bytes():
                raise NeutralMaterialConflict(
                    "Neutral Material identity already exists with different canonical content"
                )
            return snapshot

        if isinstance(material_ir, NeutralHyperelasticIR):
            if (
                not isinstance(selection, NeutralCandidateSelection)
                or not isinstance(calibration_plan, RevisionReference)
                or not isinstance(scientific_profile, RevisionReference)
            ):
                raise NeutralMaterialConflict("hyperelastic import evidence is incomplete")
            candidate = self._calibrations.get_family_candidate_for_promotion(
                context, decision, selection.candidate_id
            )
            run = self._calibrations.get_run_for_promotion(
                context, decision, selection.calibration_run_id
            )
            baseline = self._models.get_model_revision_for_calibration(
                context, decision, run.baseline_model_id, run.baseline_model_revision_id
            )
            if (
                candidate.calibration_run_id != run.id
                or candidate.value.candidate_sha256 != selection.candidate_sha256
                or candidate.value.family is not material_ir.parameters.family
                or candidate.diagnostics_artifact_id != selection.diagnostics_artifact_id
                or candidate.diagnostics_sha256 != selection.diagnostics_sha256
                or run.plan_id != calibration_plan.object_id
                or run.plan_revision_id != calibration_plan.revision_id
                or run.scientific_profile_id != scientific_profile.object_id
                or run.scientific_profile_revision_id != scientific_profile.revision_id
                or baseline.content.density_kg_per_m3 != material_ir.density_kg_per_m3
            ):
                raise NeutralMaterialConflict(
                    "imported hyperelastic Candidate, Plan, profile, or baseline differs"
                )
            if _typed_parameters(candidate.value.family, candidate.value.parameters) != (
                material_ir.parameters
            ):
                raise NeutralMaterialConflict(
                    "imported IR parameters differ from the exact Candidate"
                )
            for source in document.source_datasets:
                if source.source_kind is not NeutralDatasetKind.GOVERNED_DATASET:
                    raise NeutralMaterialConflict("hyperelastic import source kind is invalid")
                dataset = self._datasets.get_dataset_revision_for_calibration(
                    context, decision, source.dataset.object_id, source.dataset.revision_id
                )
                if (
                    dataset.content.data_artifact_id != source.normalized_artifact_id
                    or dataset.content.data_sha256 != source.normalized_artifact_sha256
                ):
                    raise NeutralMaterialConflict(
                        "imported Dataset revision does not reproduce its Artifact"
                    )
        elif isinstance(material_ir, NeutralElastoplasticIR):
            if (
                not isinstance(selection, NeutralProcessingSelection)
                or self._processing_outputs is None
                or self._test_data is None
                or len(document.source_datasets) != 1
            ):
                raise NeutralMaterialConflict("metal import evidence is incomplete")
            output, _ = await self._processing_outputs.export_exact(
                context,
                decision,
                selection.processing_output.object_id,
                selection.processing_output.revision_id,
            )
            source = document.source_datasets[0]
            source_snapshot, _ = await self._test_data.export_document(
                context, decision, source.dataset.object_id, source.dataset.revision_id
            )
            artifact, _ = await self._artifacts.read_verified_bytes(
                context,
                decision,
                material_ir.hardening_curve.artifact_id,
                maximum_bytes=64 * 1024 * 1024,
            )
            if (
                source.source_kind is not NeutralDatasetKind.TEST_DATA_DOCUMENT
                or output.content.output_sha256 != selection.processing_output_sha256
                or output.content.source_document.aggregate_id != source.dataset.object_id
                or output.content.source_document.revision_id != source.dataset.revision_id
                or source_snapshot.content.normalized_artifact_id
                != source.normalized_artifact_id
                or source_snapshot.content.normalized_sha256
                != source.normalized_artifact_sha256
                or artifact.artifact.sha256 != material_ir.hardening_curve.sha256
                or selection.candidate_families != material_ir.candidate_families
                or selection.primary_family != material_ir.primary_family
                or selection.secondary_family != material_ir.secondary_family
                or selection.primary_weight != material_ir.primary_weight
            ):
                raise NeutralMaterialConflict(
                    "imported metal Processing, source, curve, or selection evidence differs"
                )
        elif isinstance(material_ir, NeutralLinearViscoelasticIR):
            if len(document.source_datasets) != 1:
                raise NeutralMaterialConflict(
                    "linear-viscoelastic import requires exactly one source Dataset"
                )
            source = document.source_datasets[0]
            if isinstance(selection, NeutralPronyProcessingSelection):
                if (
                    self._processing_outputs is None
                    or self._test_data is None
                    or source.source_kind is not NeutralDatasetKind.TEST_DATA_DOCUMENT
                ):
                    raise NeutralMaterialConflict(
                        "processed linear-viscoelastic import evidence is incomplete"
                    )
                output, output_bytes = await self._processing_outputs.export_exact(
                    context,
                    decision,
                    selection.processing_output.object_id,
                    selection.processing_output.revision_id,
                )
                source_snapshot, _ = await self._test_data.export_document(
                    context, decision, source.dataset.object_id, source.dataset.revision_id
                )
                try:
                    output_document = json.loads(output_bytes)
                    stage = output_document["result"]["stages"][-1]
                    scalars = {item["key"]: item for item in stage["scalar_results"]}
                    selected_count = int(scalars["prony_selected_term_count"]["value"])
                    expected_terms = tuple(
                        (
                            float(scalars[f"prony_g_ratio_{ordinal}"]["value"]),
                            float(scalars[f"prony_relaxation_time_{ordinal}"]["value"]),
                        )
                        for ordinal in range(1, selected_count + 1)
                    )
                except (KeyError, TypeError, ValueError, IndexError) as error:
                    raise NeutralMaterialConflict(
                        "imported Processing Output does not reproduce Prony parameters"
                    ) from error
                if (
                    stage["method_id"] != "polymer.prony_fit_compare"
                    or output.content.output_sha256 != selection.processing_output_sha256
                    or output.content.source_document.aggregate_id != source.dataset.object_id
                    or output.content.source_document.revision_id != source.dataset.revision_id
                    or source_snapshot.content.normalized_artifact_id
                    != source.normalized_artifact_id
                    or source_snapshot.content.normalized_sha256
                    != source.normalized_artifact_sha256
                    or selection.selected_term_count != selected_count
                    or tuple(
                        (term.g_ratio, term.relaxation_time_s) for term in material_ir.terms
                    )
                    != expected_terms
                ):
                    raise NeutralMaterialConflict(
                        "imported generalized-Maxwell Processing, source, or parameters differ"
                    )
            else:
                if (
                    not isinstance(selection, NeutralCandidateSelection)
                    or not isinstance(calibration_plan, RevisionReference)
                    or self._prony_calibrations is None
                    or self._linear_models is None
                    or self._shear_datasets is None
                ):
                    raise NeutralMaterialConflict(
                        "linear-viscoelastic import evidence is incomplete"
                    )
                prony_run = self._prony_calibrations.get_run_for_promotion(
                    context, decision, selection.calibration_run_id
                )
                prony_candidate = self._prony_calibrations.get_candidate_for_promotion(
                    context, decision, selection.candidate_id
                )
                prony_baseline = self._linear_models.get_model_revision_for_calibration(
                    context,
                    decision,
                    prony_run.baseline_model_id,
                    prony_run.baseline_model_revision_id,
                )
                relaxation_dataset = self._shear_datasets.get_revision_for_calibration(
                    context, decision, source.dataset.object_id, source.dataset.revision_id
                )
                expected_terms = (
                    (
                        prony_candidate.value.fast_g_ratio,
                        prony_candidate.value.fast_relaxation_time_s,
                    ),
                    (
                        prony_candidate.value.slow_g_ratio,
                        prony_candidate.value.slow_relaxation_time_s,
                    ),
                )
                if (
                    prony_candidate.calibration_run_id != prony_run.id
                    or prony_candidate.value.candidate_sha256 != selection.candidate_sha256
                    or prony_candidate.diagnostics_artifact_id
                    != selection.diagnostics_artifact_id
                    or prony_candidate.diagnostics_sha256 != selection.diagnostics_sha256
                    or prony_run.plan_id != calibration_plan.object_id
                    or prony_run.plan_revision_id != calibration_plan.revision_id
                    or source.source_kind is not NeutralDatasetKind.SHEAR_RELAXATION_DATASET
                    or prony_run.input_dataset_id != source.dataset.object_id
                    or prony_run.input_dataset_revision_id != source.dataset.revision_id
                    or relaxation_dataset.content.data_artifact_id
                    != source.normalized_artifact_id
                    or relaxation_dataset.content.data_sha256
                    != source.normalized_artifact_sha256
                    or prony_baseline.content.density_kg_per_m3
                    != material_ir.density_kg_per_m3
                    or prony_baseline.content.youngs_modulus_pa
                    != material_ir.youngs_modulus_pa
                    or prony_baseline.content.poisson_ratio != material_ir.poisson_ratio
                    or tuple(
                        (term.g_ratio, term.relaxation_time_s) for term in material_ir.terms
                    )
                    != expected_terms
                ):
                    raise NeutralMaterialConflict(
                        "imported generalized-Maxwell Candidate, source, or parameters differ"
                    )
        else:  # pragma: no cover - closed domain union
            raise NeutralMaterialConflict("unsupported Neutral Material family")

        if isinstance(selection, NeutralCandidateSelection):
            duplicate = self._repository.find_by_candidate(
                context=context, decision=decision, candidate_id=selection.candidate_id
            )
            if duplicate is not None:
                raise NeutralMaterialConflict(
                    "the imported Candidate is already promoted by another Neutral Material"
                )
        classification = DataClassification(document.classification)
        artifact = await self._artifacts.finalize_derived_bytes(
            context,
            decision,
            classification=classification,
            artifact_role="modeling.neutral_material_json",
            schema_ref=NEUTRAL_MATERIAL_SCHEMA_REF,
            media_type="application/json",
            value=document.to_json_bytes(),
            idempotency_key=(
                f"neutral-material-import:{document.document_id}:"
                f"{document.material_model_ir.model.revision_id}"
            ),
        )
        revision_content = NeutralMaterialRevisionContent(
            document=document,
            document_artifact_id=artifact.artifact.id,
            document_artifact_sha256=artifact.artifact.sha256,
        )
        record = RevisionService(
            aggregate_type=NEUTRAL_MATERIAL_AGGREGATE_TYPE,
            store=self._repository.neutral_material_store(context, decision),
            id_factory=lambda: document.material_model_ir.model.revision_id,
        ).create(
            CreateRevisionedAggregate(
                aggregate_id=document.document_id,
                scope=TenantScope(
                    context.organization_id,
                    context.project_id,
                    document.classification,
                ),
                schema_id=material_ir.schema_id,
                schema_version=NEUTRAL_MATERIAL_SCHEMA_VERSION,
                content=revision_content,
                created_by=context.principal.id,
                change_reason=change_reason,
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        return NeutralMaterialSnapshot(
            document.document_id,
            record,
            artifact.artifact.id,
            artifact.artifact.sha256,
            document,
        )

    @staticmethod
    def validate_json(value: bytes) -> NeutralMaterialDocument:
        return neutral_material_from_json_bytes(value)

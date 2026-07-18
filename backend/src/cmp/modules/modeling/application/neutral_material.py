"""Promote a selected T-55E family Candidate to canonical Neutral Material JSON."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID, uuid4

from cmp.modules.artifacts.application.content import ArtifactService
from cmp.modules.datasets.application.governed_import import GovernedImportService
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
    Permission,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.modeling.application.ogden_calibration import (
    ReferenceOgdenCalibrationService,
)
from cmp.modules.modeling.application.ogden_prony import OgdenPronyModelService
from cmp.modules.modeling.domain.hyperelastic_families import (
    HyperelasticDiagnosticPoint,
    HyperelasticFamily,
    HyperelasticParameter,
)
from cmp.modules.modeling.domain.neutral_material import (
    NEUTRAL_HYPERELASTIC_IR_SCHEMA_DIGEST,
    NEUTRAL_HYPERELASTIC_IR_SCHEMA_ID,
    NEUTRAL_HYPERELASTIC_IR_SCHEMA_VERSION,
    NEUTRAL_MATERIAL_SCHEMA_REF,
    NEUTRAL_MATERIAL_SCHEMA_VERSION,
    CurveStage,
    EvidenceStatus,
    NeutralCandidateSelection,
    NeutralCurve,
    NeutralDatasetSource,
    NeutralHyperelasticIR,
    NeutralHyperelasticParameters,
    NeutralMaterialDocument,
    OptionalRevisionEvidence,
    RevisionReference,
    neutral_material_from_json_bytes,
)
from cmp.modules.modeling.domain.reference_ogden_calibration import OgdenCalibrationMember
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
        test_mode=first.test_mode,
        x_quantity="strain.engineering",
        x_unit="1",
        y_quantity=y_quantity,
        y_unit="Pa",
        x=tuple(item.engineering_strain for item in points),
        y=y,
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
        id_factory: Callable[[], UUID] = uuid4,
    ) -> None:
        self._repository = repository
        self._calibrations = calibrations
        self._datasets = datasets
        self._models = models
        self._artifacts = artifacts
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
                    role=member.role,
                    test_mode=member.test_mode,
                    normalized_artifact_id=dataset.content.data_artifact_id,
                    normalized_artifact_sha256=dataset.content.data_sha256,
                )
            )

        neutral_material_id = self._id()
        neutral_revision_id = self._id()
        curves = tuple(
            _curve(stage=stage, points=points)
            for _member, points in grouped
            for stage in CurveStage
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

        candidate = self._calibrations.get_family_candidate_for_promotion(
            context, decision, document.selection.candidate_id
        )
        run = self._calibrations.get_run_for_promotion(
            context, decision, document.selection.calibration_run_id
        )
        if (
            candidate.calibration_run_id != run.id
            or candidate.value.candidate_sha256 != document.selection.candidate_sha256
            or candidate.value.family is not document.material_model_ir.parameters.family
            or candidate.diagnostics_artifact_id != document.selection.diagnostics_artifact_id
            or candidate.diagnostics_sha256 != document.selection.diagnostics_sha256
            or run.plan_id != document.calibration_plan.object_id
            or run.plan_revision_id != document.calibration_plan.revision_id
            or run.scientific_profile_id != document.scientific_profile.object_id
            or run.scientific_profile_revision_id != document.scientific_profile.revision_id
        ):
            raise NeutralMaterialConflict(
                "imported selection, Candidate, Run, Plan, or profile evidence differs"
            )
        if _typed_parameters(candidate.value.family, candidate.value.parameters) != (
            document.material_model_ir.parameters
        ):
            raise NeutralMaterialConflict("imported IR parameters differ from the exact Candidate")
        for source in document.source_datasets:
            dataset = self._datasets.get_dataset_revision_for_calibration(
                context,
                decision,
                source.dataset.object_id,
                source.dataset.revision_id,
            )
            if (
                dataset.content.data_artifact_id != source.normalized_artifact_id
                or dataset.content.data_sha256 != source.normalized_artifact_sha256
            ):
                raise NeutralMaterialConflict(
                    "imported Dataset revision does not reproduce its normalized Artifact"
                )
        duplicate = self._repository.find_by_candidate(
            context=context,
            decision=decision,
            candidate_id=document.selection.candidate_id,
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
            document.document_id,
            record,
            artifact.artifact.id,
            artifact.artifact.sha256,
            document,
        )

    @staticmethod
    def validate_json(value: bytes) -> NeutralMaterialDocument:
        return neutral_material_from_json_bytes(value)

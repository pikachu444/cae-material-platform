"""HTTP registry and ephemeral preview for the configurable Processing Workbench (T-53)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Any, Literal
from uuid import UUID

import numpy as np
from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from sqlalchemy.exc import IntegrityError

from cmp.modules.datasets.domain.canonical_test_data import (
    CanonicalTestDataError,
    parse_canonical_test_data,
)
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.processing.application.common_outputs import (
    PROCESSING_OUTPUT_MEDIA_TYPE,
    CommitProcessingOutput,
    CommonProcessingOutputService,
    ExactRevisionPin,
    FitDecisionParameter,
    FitDecisionParameterSet,
    FitDecisionSnapshot,
    ProcessingOutputNotFound,
    ProcessingOutputSnapshot,
    ProcessingWorkupOverride,
)
from cmp.modules.processing.application.mapping_profiles import (
    CreateMappingProfile,
    MappingProfileNotFound,
    MappingProfileService,
    MappingProfileSnapshot,
    ReviseMappingProfile,
)
from cmp.modules.processing.application.metal_fit_runs import (
    ExecuteMetalFitRun,
    MetalFitRunDetail,
    MetalFitRunService,
)
from cmp.modules.processing.domain.common_ensemble import (
    ENSEMBLE_METHOD_REGISTRY,
    EnsembleAlignmentOptions,
    EnsemblePreview,
    preview_ensemble,
)
from cmp.modules.processing.domain.common_pipeline import (
    MAX_PIPELINE_STEPS,
    MAX_PREVIEW_POINTS,
    AttributeBinding,
    ChannelBinding,
    CommonPipelineError,
    MappingProfileContent,
    MethodDefinition,
    MissingDataPolicy,
    ProcessingPreview,
    ProcessingStep,
    preview_pipeline,
)
from cmp.modules.processing.domain.metal_hardening import HardeningCandidateEvidence
from cmp.shared.contracts.revisions import (
    InvalidRevisionETag,
    RevisionETag,
    RevisionMetadataResponse,
    RevisionPreconditionFailed,
    require_matching_if_match,
)
from cmp.shared.domain.revisions import (
    AggregateAlreadyExists,
    RevisionConflict,
    RevisionKernelError,
)

type Dependency = Callable[..., object]
type Text160 = Annotated[str, StringConstraints(min_length=1, max_length=160)]


class ChannelBindingInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    channel_key: Text160
    target_quantity: Text160
    accepted_normalized_units: Annotated[tuple[Text160, ...], Field(min_length=1, max_length=32)]
    required: bool = True
    scale: float = 1.0
    offset: float = 0.0

    def to_domain(self) -> ChannelBinding:
        return ChannelBinding(**self.model_dump())


class AttributeBindingInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    attribute_definition_id: UUID
    attribute_definition_revision_id: UUID
    target_quantity: Text160
    accepted_normalized_units: Annotated[tuple[Text160, ...], Field(min_length=1, max_length=32)]
    required: bool = True

    def to_domain(self) -> AttributeBinding:
        return AttributeBinding(**self.model_dump())


class MappingProfileInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    profile_key: Text160
    label: Annotated[str, StringConstraints(min_length=1, max_length=200)]
    independent_quantity: Text160
    missing_data_policy: MissingDataPolicy
    bindings: Annotated[tuple[ChannelBindingInput, ...], Field(min_length=2, max_length=128)]
    attribute_bindings: Annotated[tuple[AttributeBindingInput, ...], Field(max_length=128)] = ()

    def to_domain(self) -> MappingProfileContent:
        return MappingProfileContent(
            profile_key=self.profile_key,
            label=self.label,
            independent_quantity=self.independent_quantity,
            missing_data_policy=self.missing_data_policy,
            bindings=tuple(item.to_domain() for item in self.bindings),
            attribute_bindings=tuple(item.to_domain() for item in self.attribute_bindings),
        )


class ProcessingStepInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    method_id: Text160
    method_version: Text160
    options: dict[str, Any]

    def to_domain(self) -> ProcessingStep:
        return ProcessingStep(**self.model_dump())


class ProcessingPreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    document: dict[str, Any]
    mapping_profile: MappingProfileInput
    steps: Annotated[tuple[ProcessingStepInput, ...], Field(max_length=MAX_PIPELINE_STEPS)]


class CreateMappingProfileRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    classification: DataClassification
    content: MappingProfileInput
    change_reason: Annotated[str, StringConstraints(min_length=1, max_length=2000)]


class ReviseMappingProfileRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    content: MappingProfileInput
    change_reason: Annotated[str, StringConstraints(min_length=1, max_length=2000)]


class MappingProfileResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mapping_profile_id: UUID
    current_revision: RevisionMetadataResponse
    content: MappingProfileInput

    @classmethod
    def from_snapshot(cls, value: MappingProfileSnapshot) -> MappingProfileResponse:
        content = value.content
        return cls(
            mapping_profile_id=value.id,
            current_revision=RevisionMetadataResponse.from_record(value.current, "draft"),
            content=MappingProfileInput(
                profile_key=content.profile_key,
                label=content.label,
                independent_quantity=content.independent_quantity,
                missing_data_policy=content.missing_data_policy,
                bindings=tuple(
                    ChannelBindingInput(
                        channel_key=item.channel_key,
                        target_quantity=item.target_quantity,
                        accepted_normalized_units=item.accepted_normalized_units,
                        required=item.required,
                        scale=item.scale,
                        offset=item.offset,
                    )
                    for item in content.bindings
                ),
                attribute_bindings=tuple(
                    AttributeBindingInput(
                        attribute_definition_id=item.attribute_definition_id,
                        attribute_definition_revision_id=item.attribute_definition_revision_id,
                        target_quantity=item.target_quantity,
                        accepted_normalized_units=item.accepted_normalized_units,
                        required=item.required,
                    )
                    for item in content.attribute_bindings
                ),
            ),
        )


class MappingProfileListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: tuple[MappingProfileResponse, ...]


class MethodDefinitionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    method_id: str
    version: str
    label: str
    description: str
    option_schema: dict[str, Any]
    deterministic: bool
    allows_extrapolation: bool

    @classmethod
    def from_domain(cls, value: MethodDefinition) -> MethodDefinitionResponse:
        return cls(
            method_id=value.method_id,
            version=value.version,
            label=value.label,
            description=value.description,
            option_schema=value.option_schema,
            deterministic=value.deterministic,
            allows_extrapolation=value.allows_extrapolation,
        )


class MethodRegistryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: tuple[MethodDefinitionResponse, ...]


class QuantitySeriesResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    quantity: str
    unit: str
    values: tuple[float, ...]


class ScalarResultResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str
    quantity_semantics: str
    value: float
    unit: str


class HardeningCandidateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    family: str
    response: tuple[float, ...]
    residual: tuple[float, ...]
    tangent: tuple[float | None, ...]
    parameter_names: tuple[str, ...]
    parameter_units: tuple[str, ...]
    lower: tuple[float, ...]
    initial: tuple[float, ...]
    fitted: tuple[float, ...]
    upper: tuple[float, ...]
    rmse_pa: float
    relative_rmse: float
    objective: float
    scipy_cost: float
    convergence: bool
    nfev: int
    active_bound: tuple[str, ...]
    jacobian_rank: int
    jacobian_tolerance: float
    jacobian_condition: float | None
    identifiability: str
    uncertainty: str
    objective_history: tuple[float, ...]
    optimizer_status: int = 0
    optimizer_message: str = ""

    @classmethod
    def from_domain(cls, value: HardeningCandidateEvidence) -> HardeningCandidateResponse:
        return cls(
            family=value.family,
            response=tuple(float(item) for item in value.response),
            residual=tuple(float(item) for item in value.residual),
            tangent=tuple(
                None if not isinstance(item, (int, float)) or not np.isfinite(item) else float(item)
                for item in value.tangent
            ),
            parameter_names=value.parameter_names,
            parameter_units=value.parameter_units,
            lower=tuple(float(item) for item in value.lower),
            initial=tuple(float(item) for item in value.initial),
            fitted=tuple(float(item) for item in value.fitted),
            upper=tuple(float(item) for item in value.upper),
            rmse_pa=value.rmse_pa,
            relative_rmse=value.relative_rmse,
            objective=value.objective,
            scipy_cost=value.scipy_cost,
            convergence=value.convergence,
            nfev=value.nfev,
            active_bound=value.active_bound,
            jacobian_rank=value.jacobian_rank,
            jacobian_tolerance=value.jacobian_tolerance,
            jacobian_condition=value.jacobian_condition,
            identifiability=value.identifiability,
            uncertainty=value.uncertainty,
            objective_history=value.objective_history,
            optimizer_status=value.optimizer_status,
            optimizer_message=value.optimizer_message,
        )


class CurveStageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ordinal: int
    method_id: str
    method_version: str
    point_count: int
    series: tuple[QuantitySeriesResponse, ...]
    diagnostics: tuple[str, ...]
    scalar_results: tuple[ScalarResultResponse, ...]
    fit_candidates: tuple[HardeningCandidateResponse, ...] = ()


class ProcessingPreviewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    execution_mode: str
    promotable: bool
    source_document_sha256: str
    mapping_profile_sha256: str
    independent_quantity: str
    stages: tuple[CurveStageResponse, ...]

    @classmethod
    def from_domain(cls, value: ProcessingPreview) -> ProcessingPreviewResponse:
        return cls(
            execution_mode="preview",
            promotable=False,
            source_document_sha256=value.source_document_sha256,
            mapping_profile_sha256=value.mapping_profile_sha256,
            independent_quantity=value.independent_quantity,
            stages=tuple(
                CurveStageResponse(
                    ordinal=stage.ordinal,
                    method_id=stage.method_id,
                    method_version=stage.method_version,
                    point_count=stage.point_count,
                    series=tuple(
                        QuantitySeriesResponse(
                            quantity=series.quantity,
                            unit=series.unit,
                            values=series.values,
                        )
                        for series in stage.series
                    ),
                    diagnostics=stage.diagnostics,
                    scalar_results=tuple(
                        ScalarResultResponse(
                            key=item.key,
                            quantity_semantics=item.quantity_semantics,
                            value=item.value,
                            unit=item.unit,
                        )
                        for item in stage.scalar_results
                    ),
                    fit_candidates=tuple(
                        HardeningCandidateResponse.from_domain(item)
                        for item in stage.fit_candidates
                    ),
                )
                for stage in value.stages
            ),
        )


class ExactRevisionPinInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    aggregate_id: UUID
    revision_id: UUID

    def to_domain(self) -> ExactRevisionPin:
        return ExactRevisionPin(self.aggregate_id, self.revision_id)


class ExactProcessingFitPreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_processing_output: ExactRevisionPinInput
    fit_step: ProcessingStepInput


class ProcessingWorkupOverrideInput(BaseModel):
    """Structured manual decision evidence for one executed workup override."""

    model_config = ConfigDict(extra="forbid")
    kind: Literal["youngs_modulus", "necking_boundary"]
    original_value: float = Field(ge=0)
    original_unit: Text160
    canonical_value: float = Field(ge=0)
    canonical_unit: Text160
    reason: Annotated[str, StringConstraints(min_length=1, max_length=2000)]

    def to_domain(self) -> ProcessingWorkupOverride:
        return ProcessingWorkupOverride(**self.model_dump())


class FitDecisionParameterInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Text160
    value: float
    unit: Text160
    lower: float | None = None
    upper: float | None = None

    def to_domain(self) -> FitDecisionParameter:
        return FitDecisionParameter(**self.model_dump())


class FitDecisionParameterSetInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    law: Text160
    parameters: Annotated[tuple[FitDecisionParameterInput, ...], Field(min_length=1, max_length=32)]

    def to_domain(self) -> FitDecisionParameterSet:
        return FitDecisionParameterSet(
            self.law, tuple(parameter.to_domain() for parameter in self.parameters)
        )


class FitDecisionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    candidate_key: Text160
    mode: Literal["single", "blend"]
    primary_law: Text160
    secondary_law: Text160 | None = None
    primary_weight: float | None = None
    parameter_sets: Annotated[
        tuple[FitDecisionParameterSetInput, ...], Field(min_length=1, max_length=2)
    ]
    fit_minimum: float
    fit_maximum: float
    extrapolation_maximum: float | None = None
    extrapolation_policy: Text160
    metric_definition: Text160
    metric_value: float
    requested_term_policy: Text160 | None = None
    actual_term_count: int | None = Field(default=None, ge=1, le=10)
    selection_reason: Annotated[str, StringConstraints(min_length=1, max_length=2000)]
    warning_acknowledged: bool

    def to_domain(self) -> FitDecisionSnapshot:
        return FitDecisionSnapshot(
            candidate_key=self.candidate_key,
            mode=self.mode,
            primary_law=self.primary_law,
            secondary_law=self.secondary_law,
            primary_weight=self.primary_weight,
            parameter_sets=tuple(item.to_domain() for item in self.parameter_sets),
            fit_minimum=self.fit_minimum,
            fit_maximum=self.fit_maximum,
            extrapolation_maximum=self.extrapolation_maximum,
            extrapolation_policy=self.extrapolation_policy,
            metric_definition=self.metric_definition,
            metric_value=self.metric_value,
            requested_term_policy=self.requested_term_policy,
            actual_term_count=self.actual_term_count,
            selection_reason=self.selection_reason,
            warning_acknowledged=self.warning_acknowledged,
        )


class CommitProcessingOutputRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    classification: DataClassification
    label: Annotated[str, StringConstraints(min_length=1, max_length=200)]
    source_document: ExactRevisionPinInput
    mapping_profile: ExactRevisionPinInput
    steps: Annotated[
        tuple[ProcessingStepInput, ...], Field(min_length=1, max_length=MAX_PIPELINE_STEPS)
    ]
    change_reason: Annotated[str, StringConstraints(min_length=1, max_length=2000)]
    workup_overrides: Annotated[tuple[ProcessingWorkupOverrideInput, ...], Field(max_length=2)] = ()
    fit_decision: FitDecisionInput | None = None
    source_processing_output: ExactRevisionPinInput | None = None


class ExportProvenanceResponse(BaseModel):
    """Typed server proof copied from the exact Canonical Test Data revision."""

    model_config = ConfigDict(extra="forbid")
    material: ExactRevisionPinInput
    material_state: ExactRevisionPinInput
    test_run: ExactRevisionPinInput


class ProcessingOutputResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    processing_output_id: UUID
    current_revision: RevisionMetadataResponse
    label: str
    source_document: ExactRevisionPinInput
    source_document_sha256: str
    source_canonical_artifact_sha256: str
    mapping_profile: ExactRevisionPinInput
    mapping_profile_sha256: str
    steps: tuple[ProcessingStepInput, ...]
    independent_quantity: str
    stage_count: int
    final_point_count: int
    output_artifact_id: UUID
    output_sha256: str
    source_processing_output: ExactRevisionPinInput | None
    source_processing_output_sha256: str | None
    workup_overrides: tuple[ProcessingWorkupOverrideInput, ...]
    fit_decision: FitDecisionInput | None
    export_provenance: ExportProvenanceResponse | None

    @classmethod
    def from_snapshot(cls, value: ProcessingOutputSnapshot) -> ProcessingOutputResponse:
        content = value.content
        fit_decision = getattr(content, "fit_decision", None)
        source_processing_output = getattr(content, "source_processing_output", None)
        source_processing_output_sha256 = getattr(
            content, "source_processing_output_sha256", None
        )
        return cls(
            processing_output_id=value.id,
            current_revision=RevisionMetadataResponse.from_record(value.current, "published"),
            label=content.label,
            source_document=ExactRevisionPinInput(
                aggregate_id=content.source_document.aggregate_id,
                revision_id=content.source_document.revision_id,
            ),
            source_document_sha256=content.source_document_sha256,
            source_canonical_artifact_sha256=content.source_canonical_artifact_sha256,
            mapping_profile=ExactRevisionPinInput(
                aggregate_id=content.mapping_profile.aggregate_id,
                revision_id=content.mapping_profile.revision_id,
            ),
            mapping_profile_sha256=content.mapping_profile_sha256,
            steps=tuple(
                ProcessingStepInput(
                    method_id=step.method_id,
                    method_version=step.method_version,
                    options=step.options,
                )
                for step in content.steps
            ),
            independent_quantity=content.independent_quantity,
            stage_count=content.stage_count,
            final_point_count=content.final_point_count,
            output_artifact_id=content.output_artifact_id,
            output_sha256=content.output_sha256,
            source_processing_output=None
            if source_processing_output is None
            else ExactRevisionPinInput(
                aggregate_id=source_processing_output.aggregate_id,
                revision_id=source_processing_output.revision_id,
            ),
            source_processing_output_sha256=source_processing_output_sha256,
            workup_overrides=tuple(
                ProcessingWorkupOverrideInput(
                    kind=override.kind,
                    original_value=override.original_value,
                    original_unit=override.original_unit,
                    canonical_value=override.canonical_value,
                    canonical_unit=override.canonical_unit,
                    reason=override.reason,
                )
                for override in content.workup_overrides
            ),
            fit_decision=None
            if fit_decision is None
            else FitDecisionInput(
                candidate_key=fit_decision.candidate_key,
                mode=fit_decision.mode,
                primary_law=fit_decision.primary_law,
                secondary_law=fit_decision.secondary_law,
                primary_weight=fit_decision.primary_weight,
                parameter_sets=tuple(
                    FitDecisionParameterSetInput(
                        law=item.law,
                        parameters=tuple(
                            FitDecisionParameterInput(
                                name=parameter.name,
                                value=parameter.value,
                                unit=parameter.unit,
                                lower=parameter.lower,
                                upper=parameter.upper,
                            )
                            for parameter in item.parameters
                        ),
                    )
                    for item in fit_decision.parameter_sets
                ),
                fit_minimum=fit_decision.fit_minimum,
                fit_maximum=fit_decision.fit_maximum,
                extrapolation_maximum=fit_decision.extrapolation_maximum,
                extrapolation_policy=fit_decision.extrapolation_policy,
                metric_definition=fit_decision.metric_definition,
                metric_value=fit_decision.metric_value,
                requested_term_policy=fit_decision.requested_term_policy,
                actual_term_count=fit_decision.actual_term_count,
                selection_reason=fit_decision.selection_reason,
                warning_acknowledged=fit_decision.warning_acknowledged,
            ),
            export_provenance=None
            if content.export_provenance is None
            else ExportProvenanceResponse(
                material=ExactRevisionPinInput(
                    aggregate_id=content.export_provenance.material.aggregate_id,
                    revision_id=content.export_provenance.material.revision_id,
                ),
                material_state=ExactRevisionPinInput(
                    aggregate_id=content.export_provenance.material_state.aggregate_id,
                    revision_id=content.export_provenance.material_state.revision_id,
                ),
                test_run=ExactRevisionPinInput(
                    aggregate_id=content.export_provenance.test_run.aggregate_id,
                    revision_id=content.export_provenance.test_run.revision_id,
                ),
            ),
        )


class ProcessingOutputListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: tuple[ProcessingOutputResponse, ...]


class MetalFitRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    classification: DataClassification
    source_processing_output: ExactRevisionPinInput
    fit_step: ProcessingStepInput
    change_reason: Annotated[str, StringConstraints(min_length=1, max_length=2000)]


class MetalFitRunAttemptResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID
    run_id: UUID
    ordinal: int
    family: str
    status: str
    result: dict[str, Any] | None
    objective_history: tuple[float, ...]
    failure_code: str | None
    failure_reason: str | None


class MetalFitRunResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID
    classification: DataClassification
    source_processing_output: ExactRevisionPinInput
    source_processing_output_sha256: str
    source_document: ExactRevisionPinInput
    mapping_profile: ExactRevisionPinInput
    options: dict[str, Any]
    reproducibility_evidence: dict[str, Any]
    status: str
    failure_code: str | None
    failure_reason: str | None
    attempts: tuple[MetalFitRunAttemptResponse, ...]
    preview: ProcessingPreviewResponse | None = None
    created_by: UUID | None = None
    request_id: UUID | None = None
    trace_id: str | None = None
    started_at: str | None = None
    ended_at: str | None = None

    @classmethod
    def from_domain(cls, value: MetalFitRunDetail) -> MetalFitRunResponse:
        run = value.run
        return cls(
            id=run.id,
            classification=run.classification,
            source_processing_output=ExactRevisionPinInput(
                aggregate_id=run.source_processing_output.aggregate_id,
                revision_id=run.source_processing_output.revision_id,
            ),
            source_processing_output_sha256=run.source_processing_output_sha256,
            source_document=ExactRevisionPinInput(
                aggregate_id=run.source_document.aggregate_id,
                revision_id=run.source_document.revision_id,
            ),
            mapping_profile=ExactRevisionPinInput(
                aggregate_id=run.mapping_profile.aggregate_id,
                revision_id=run.mapping_profile.revision_id,
            ),
            options=run.options,
            reproducibility_evidence=run.reproducibility_evidence,
            status=run.status.value,
            failure_code=run.failure_code,
            failure_reason=run.failure_reason,
            attempts=tuple(
                MetalFitRunAttemptResponse(
                    id=item.id,
                    run_id=item.run_id,
                    ordinal=item.ordinal,
                    family=item.family,
                    status=item.status.value,
                    result=item.result,
                    objective_history=item.objective_history,
                    failure_code=item.failure_code,
                    failure_reason=item.failure_reason,
                )
                for item in value.attempts
            ),
            preview=(
                None
                if value.preview is None
                else ProcessingPreviewResponse.from_domain(value.preview)
            ),
            created_by=run.created_by,
            request_id=run.request_id,
            trace_id=run.trace_id,
            started_at=run.started_at.isoformat(),
            ended_at=None if run.ended_at is None else run.ended_at.isoformat(),
        )


class EnsembleAlignmentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    point_count: int = Field(ge=2, le=MAX_PREVIEW_POINTS)
    domain_policy: str = "intersection"
    extrapolation: str = "reject"

    def to_domain(self) -> EnsembleAlignmentOptions:
        return EnsembleAlignmentOptions(**self.model_dump())


class EnsemblePreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    documents: Annotated[tuple[dict[str, Any], ...], Field(min_length=2, max_length=100)]
    mapping_profile: MappingProfileInput
    preprocessing_steps: Annotated[
        tuple[ProcessingStepInput, ...], Field(max_length=MAX_PIPELINE_STEPS)
    ] = ()
    alignment: EnsembleAlignmentInput


class EnsembleMemberResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ordinal: int
    source_document_sha256: str
    stage: CurveStageResponse


class PointwiseStatisticsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    quantity: str
    unit: str
    mean: tuple[float, ...]
    median: tuple[float, ...]
    standard_deviation: tuple[float, ...]
    mad: tuple[float, ...]
    q1: tuple[float, ...]
    q3: tuple[float, ...]
    confidence_95_lower: tuple[float, ...]
    confidence_95_upper: tuple[float, ...]


class EnsemblePreviewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    execution_mode: str
    promotable: bool
    mapping_profile_sha256: str
    independent_quantity: str
    grid_unit: str
    grid: tuple[float, ...]
    members: tuple[EnsembleMemberResponse, ...]
    statistics: tuple[PointwiseStatisticsResponse, ...]
    diagnostics: tuple[str, ...]

    @classmethod
    def from_domain(cls, value: EnsemblePreview) -> EnsemblePreviewResponse:
        return cls(
            execution_mode="preview",
            promotable=False,
            mapping_profile_sha256=value.mapping_profile_sha256,
            independent_quantity=value.independent_quantity,
            grid_unit=value.grid_unit,
            grid=value.grid,
            members=tuple(
                EnsembleMemberResponse(
                    ordinal=member.ordinal,
                    source_document_sha256=member.source_document_sha256,
                    stage=CurveStageResponse(
                        ordinal=member.stage.ordinal,
                        method_id=member.stage.method_id,
                        method_version=member.stage.method_version,
                        point_count=member.stage.point_count,
                        series=tuple(
                            QuantitySeriesResponse(
                                quantity=series.quantity,
                                unit=series.unit,
                                values=series.values,
                            )
                            for series in member.stage.series
                        ),
                        diagnostics=member.stage.diagnostics,
                        scalar_results=tuple(
                            ScalarResultResponse(
                                key=item.key,
                                quantity_semantics=item.quantity_semantics,
                                value=item.value,
                                unit=item.unit,
                            )
                            for item in member.stage.scalar_results
                        ),
                    ),
                )
                for member in value.members
            ),
            statistics=tuple(
                PointwiseStatisticsResponse(
                    quantity=item.quantity,
                    unit=item.unit,
                    mean=item.mean,
                    median=item.median,
                    standard_deviation=item.standard_deviation,
                    mad=item.mad,
                    q1=item.q1,
                    q3=item.q3,
                    confidence_95_lower=item.confidence_95_lower,
                    confidence_95_upper=item.confidence_95_upper,
                )
                for item in value.statistics
            ),
            diagnostics=value.diagnostics,
        )


def install_common_processing_api(
    app: FastAPI,
    *,
    service: MappingProfileService | None = None,
    output_service: CommonProcessingOutputService | None = None,
    fit_run_service: MetalFitRunService | None = None,
    security_dependency: Dependency,
    read_dependency: Dependency,
    execute_dependency: Dependency,
) -> None:
    from cmp.modules.processing.domain.common_pipeline import METHOD_REGISTRY

    def scope(request: Request) -> tuple[SecurityContext, AuthorizationDecision]:
        context = getattr(request.state, "security_context", None)
        decision = getattr(request.state, "authorization_decision", None)
        if not isinstance(context, SecurityContext) or not isinstance(
            decision, AuthorizationDecision
        ):
            raise RuntimeError("Processing dependencies did not initialize request scope")
        return context, decision

    def etag(response: Response, snapshot: MappingProfileSnapshot) -> None:
        response.headers["ETag"] = str(RevisionETag.from_ref(snapshot.current.ref))
        response.headers["Cache-Control"] = "no-store"

    @app.post(
        "/api/v1/mapping-profiles",
        response_model=MappingProfileResponse,
        status_code=status.HTTP_201_CREATED,
        dependencies=[Depends(security_dependency), Depends(execute_dependency)],
        tags=["processing-workbench"],
    )
    def create_mapping_profile(
        body: CreateMappingProfileRequest, request: Request, response: Response
    ) -> MappingProfileResponse:
        context, decision = scope(request)
        if service is None:
            raise HTTPException(status_code=503, detail="Mapping Profile store unavailable")
        try:
            snapshot = service.create_profile(
                context,
                decision,
                CreateMappingProfile(
                    body.classification, body.content.to_domain(), body.change_reason
                ),
            )
        except (CommonPipelineError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        except (AggregateAlreadyExists, IntegrityError) as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        etag(response, snapshot)
        return MappingProfileResponse.from_snapshot(snapshot)

    @app.get(
        "/api/v1/mapping-profiles",
        response_model=MappingProfileListResponse,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["processing-workbench"],
    )
    def list_mapping_profiles(request: Request) -> MappingProfileListResponse:
        context, decision = scope(request)
        if service is None:
            raise HTTPException(status_code=503, detail="Mapping Profile store unavailable")
        return MappingProfileListResponse(
            items=tuple(
                MappingProfileResponse.from_snapshot(item)
                for item in service.list_profiles(context, decision)
            )
        )

    @app.get(
        "/api/v1/mapping-profiles/{profile_id}",
        response_model=MappingProfileResponse,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["processing-workbench"],
    )
    def get_mapping_profile(
        profile_id: UUID, request: Request, response: Response
    ) -> MappingProfileResponse:
        context, decision = scope(request)
        if service is None:
            raise HTTPException(status_code=503, detail="Mapping Profile store unavailable")
        try:
            snapshot = service.get_profile(context, decision, profile_id)
        except MappingProfileNotFound as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        etag(response, snapshot)
        return MappingProfileResponse.from_snapshot(snapshot)

    @app.post(
        "/api/v1/mapping-profiles/{profile_id}/revisions",
        response_model=MappingProfileResponse,
        status_code=status.HTTP_201_CREATED,
        dependencies=[Depends(security_dependency), Depends(execute_dependency)],
        tags=["processing-workbench"],
    )
    def revise_mapping_profile(
        profile_id: UUID,
        body: ReviseMappingProfileRequest,
        request: Request,
        response: Response,
        if_match: Annotated[str | None, Header(alias="If-Match")] = None,
    ) -> MappingProfileResponse:
        context, decision = scope(request)
        if service is None:
            raise HTTPException(status_code=503, detail="Mapping Profile store unavailable")
        try:
            current = service.get_profile(context, decision, profile_id, write=True)
            expected = require_matching_if_match(if_match, current.current.ref)
            snapshot = service.revise_profile(
                context,
                decision,
                profile_id,
                ReviseMappingProfile(expected, body.content.to_domain(), body.change_reason),
            )
        except InvalidRevisionETag as error:
            raise HTTPException(status_code=428, detail=str(error)) from error
        except RevisionPreconditionFailed as error:
            raise HTTPException(status_code=412, detail=str(error)) from error
        except MappingProfileNotFound as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except (RevisionConflict, RevisionKernelError, IntegrityError) as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        except (CommonPipelineError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        etag(response, snapshot)
        return MappingProfileResponse.from_snapshot(snapshot)

    @app.get(
        "/api/v1/processing-methods",
        response_model=MethodRegistryResponse,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["processing-workbench"],
    )
    def list_processing_methods() -> MethodRegistryResponse:
        return MethodRegistryResponse(
            items=tuple(MethodDefinitionResponse.from_domain(item) for item in METHOD_REGISTRY)
        )

    @app.get(
        "/api/v1/processing-ensemble-methods",
        response_model=MethodRegistryResponse,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["processing-workbench"],
    )
    def list_processing_ensemble_methods() -> MethodRegistryResponse:
        return MethodRegistryResponse(
            items=tuple(
                MethodDefinitionResponse.from_domain(item) for item in ENSEMBLE_METHOD_REGISTRY
            )
        )

    @app.post(
        "/api/v1/processing:preview",
        response_model=ProcessingPreviewResponse,
        status_code=status.HTTP_200_OK,
        dependencies=[Depends(security_dependency), Depends(execute_dependency)],
        tags=["processing-workbench"],
    )
    def preview_common_processing(body: ProcessingPreviewRequest) -> ProcessingPreviewResponse:
        try:
            result = preview_pipeline(
                parse_canonical_test_data(body.document),
                body.mapping_profile.to_domain(),
                tuple(item.to_domain() for item in body.steps),
            )
            return ProcessingPreviewResponse.from_domain(result)
        except (CanonicalTestDataError, CommonPipelineError, TypeError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @app.post(
        "/api/v1/processing:preview-from-output",
        response_model=ProcessingPreviewResponse,
        status_code=status.HTTP_200_OK,
        dependencies=[Depends(security_dependency), Depends(execute_dependency)],
        tags=["processing-workbench"],
    )
    async def preview_processing_fit_from_output(
        body: ExactProcessingFitPreviewRequest, request: Request
    ) -> ProcessingPreviewResponse:
        context, decision = scope(request)
        if output_service is None:
            raise HTTPException(status_code=503, detail="Processing Output store unavailable")
        try:
            result = await output_service.preview_from_exact_output(
                context,
                decision,
                body.source_processing_output.to_domain(),
                body.fit_step.to_domain(),
            )
            return ProcessingPreviewResponse.from_domain(result)
        except ProcessingOutputNotFound as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except (CommonPipelineError, ValueError, TypeError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @app.post(
        "/api/v1/processing:preview-ensemble",
        response_model=EnsemblePreviewResponse,
        status_code=status.HTTP_200_OK,
        dependencies=[Depends(security_dependency), Depends(execute_dependency)],
        tags=["processing-workbench"],
    )
    def preview_common_ensemble(body: EnsemblePreviewRequest) -> EnsemblePreviewResponse:
        try:
            result = preview_ensemble(
                tuple(parse_canonical_test_data(document) for document in body.documents),
                body.mapping_profile.to_domain(),
                tuple(item.to_domain() for item in body.preprocessing_steps),
                body.alignment.to_domain(),
            )
            return EnsemblePreviewResponse.from_domain(result)
        except (CanonicalTestDataError, CommonPipelineError, TypeError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @app.post(
        "/api/v1/processing-outputs",
        response_model=ProcessingOutputResponse,
        status_code=status.HTTP_201_CREATED,
        dependencies=[Depends(security_dependency), Depends(execute_dependency)],
        tags=["processing-workbench"],
    )
    async def commit_processing_output(
        body: CommitProcessingOutputRequest, request: Request
    ) -> ProcessingOutputResponse:
        context, decision = scope(request)
        if output_service is None:
            raise HTTPException(status_code=503, detail="Processing Output store unavailable")
        try:
            snapshot = await output_service.commit(
                context,
                decision,
                CommitProcessingOutput(
                    classification=body.classification,
                    label=body.label,
                    source_document=body.source_document.to_domain(),
                    mapping_profile=body.mapping_profile.to_domain(),
                    steps=tuple(step.to_domain() for step in body.steps),
                    change_reason=body.change_reason,
                    workup_overrides=tuple(
                        override.to_domain() for override in body.workup_overrides
                    ),
                    fit_decision=body.fit_decision.to_domain() if body.fit_decision else None,
                    source_processing_output=(
                        body.source_processing_output.to_domain()
                        if body.source_processing_output is not None
                        else None
                    ),
                ),
            )
            return ProcessingOutputResponse.from_snapshot(snapshot)
        except ProcessingOutputNotFound as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except (CommonPipelineError, CanonicalTestDataError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        except (AggregateAlreadyExists, IntegrityError, RevisionKernelError) as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.get(
        "/api/v1/processing-outputs",
        response_model=ProcessingOutputListResponse,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["processing-workbench"],
    )
    def list_processing_outputs(request: Request) -> ProcessingOutputListResponse:
        context, decision = scope(request)
        if output_service is None:
            raise HTTPException(status_code=503, detail="Processing Output store unavailable")
        return ProcessingOutputListResponse(
            items=tuple(
                ProcessingOutputResponse.from_snapshot(item)
                for item in output_service.list_outputs(context, decision)
            )
        )

    @app.get(
        "/api/v1/processing-outputs/{output_id}/content",
        response_class=Response,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["processing-workbench"],
    )
    async def download_processing_output(output_id: UUID, request: Request) -> Response:
        context, decision = scope(request)
        if output_service is None:
            raise HTTPException(status_code=503, detail="Processing Output store unavailable")
        try:
            snapshot, value = await output_service.export(context, decision, output_id)
        except ProcessingOutputNotFound as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return Response(
            content=value,
            media_type=PROCESSING_OUTPUT_MEDIA_TYPE,
            headers={
                "Content-Disposition": f'attachment; filename="processing-output-{output_id}.json"',
                "X-Content-SHA256": snapshot.content.output_sha256,
                "Cache-Control": "no-store",
            },
        )

    @app.post(
        "/api/v1/metal-fit-runs",
        response_model=MetalFitRunResponse,
        status_code=status.HTTP_201_CREATED,
        dependencies=[Depends(security_dependency), Depends(execute_dependency)],
        tags=["processing-workbench"],
    )
    async def execute_metal_fit_run(
        body: MetalFitRunRequest, request: Request
    ) -> MetalFitRunResponse:
        context, decision = scope(request)
        if fit_run_service is None:
            raise HTTPException(status_code=503, detail="metal Fit run store unavailable")
        try:
            value = await fit_run_service.execute(
                context,
                decision,
                ExecuteMetalFitRun(
                    classification=body.classification,
                    source_processing_output=body.source_processing_output.to_domain(),
                    fit_step=body.fit_step.to_domain(),
                    change_reason=body.change_reason,
                ),
            )
            return MetalFitRunResponse.from_domain(value)
        except ProcessingOutputNotFound as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except (CommonPipelineError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @app.get(
        "/api/v1/metal-fit-runs",
        response_model=tuple[MetalFitRunResponse, ...],
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["processing-workbench"],
    )
    def list_metal_fit_runs(request: Request) -> tuple[MetalFitRunResponse, ...]:
        context, decision = scope(request)
        if fit_run_service is None:
            raise HTTPException(status_code=503, detail="metal Fit run store unavailable")
        return tuple(
            MetalFitRunResponse.from_domain(fit_run_service.get(context, decision, item.id))
            for item in fit_run_service.list(context, decision)
        )

    @app.get(
        "/api/v1/metal-fit-runs/{run_id}",
        response_model=MetalFitRunResponse,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["processing-workbench"],
    )
    def get_metal_fit_run(run_id: UUID, request: Request) -> MetalFitRunResponse:
        context, decision = scope(request)
        if fit_run_service is None:
            raise HTTPException(status_code=503, detail="metal Fit run store unavailable")
        try:
            return MetalFitRunResponse.from_domain(fit_run_service.get(context, decision, run_id))
        except ProcessingOutputNotFound as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

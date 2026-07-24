"""HTTP registry and ephemeral preview for the configurable Processing Workbench (T-53)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Any, Literal
from uuid import UUID

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


class CurveStageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ordinal: int
    method_id: str
    method_version: str
    point_count: int
    series: tuple[QuantitySeriesResponse, ...]
    diagnostics: tuple[str, ...]
    scalar_results: tuple[ScalarResultResponse, ...]


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


class ProcessingWorkupOverrideInput(BaseModel):
    """Structured manual decision evidence for one executed workup override."""

    model_config = ConfigDict(extra="forbid")
    kind: Literal["youngs_modulus", "necking_boundary"]
    original_value: float = Field(gt=0)
    original_unit: Text160
    canonical_value: float = Field(gt=0)
    canonical_unit: Text160
    reason: Annotated[str, StringConstraints(min_length=1, max_length=2000)]

    def to_domain(self) -> ProcessingWorkupOverride:
        return ProcessingWorkupOverride(**self.model_dump())


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
    workup_overrides: tuple[ProcessingWorkupOverrideInput, ...]

    @classmethod
    def from_snapshot(cls, value: ProcessingOutputSnapshot) -> ProcessingOutputResponse:
        content = value.content
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
        )


class ProcessingOutputListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: tuple[ProcessingOutputResponse, ...]


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

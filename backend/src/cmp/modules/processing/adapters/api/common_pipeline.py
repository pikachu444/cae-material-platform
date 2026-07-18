"""HTTP registry and ephemeral preview for the configurable Processing Workbench (T-53)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from cmp.modules.datasets.domain.canonical_test_data import (
    CanonicalTestDataError,
    parse_canonical_test_data,
)
from cmp.modules.processing.domain.common_pipeline import (
    MAX_PIPELINE_STEPS,
    ChannelBinding,
    CommonPipelineError,
    MappingProfileContent,
    MethodDefinition,
    MissingDataPolicy,
    ProcessingPreview,
    ProcessingStep,
    preview_pipeline,
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


class MappingProfileInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    profile_key: Text160
    label: Annotated[str, StringConstraints(min_length=1, max_length=200)]
    independent_quantity: Text160
    missing_data_policy: MissingDataPolicy
    bindings: Annotated[tuple[ChannelBindingInput, ...], Field(min_length=2, max_length=128)]

    def to_domain(self) -> MappingProfileContent:
        return MappingProfileContent(
            profile_key=self.profile_key,
            label=self.label,
            independent_quantity=self.independent_quantity,
            missing_data_policy=self.missing_data_policy,
            bindings=tuple(item.to_domain() for item in self.bindings),
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


class CurveStageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ordinal: int
    method_id: str
    method_version: str
    point_count: int
    series: tuple[QuantitySeriesResponse, ...]
    diagnostics: tuple[str, ...]


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
                )
                for stage in value.stages
            ),
        )


def install_common_processing_api(
    app: FastAPI,
    *,
    security_dependency: Dependency,
    read_dependency: Dependency,
    execute_dependency: Dependency,
) -> None:
    from cmp.modules.processing.domain.common_pipeline import METHOD_REGISTRY

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

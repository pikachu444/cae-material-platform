"""Public curve metadata and bounded-series API models shared across product modules."""

from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from cmp.modules.datasets.domain.curve_metadata import (
    ArtifactPin,
    AxisRole,
    BoundDirection,
    Coverage,
    CurveChannel,
    CurveDefinition,
    CurveDeviation,
    CurveMetadata,
    CurveSeriesPreview,
    DeviationKind,
    DeviationScope,
    MetadataState,
    OriginalUnit,
    ProvenanceKind,
    ProvenancePointer,
    RevisionPin,
    SourcePin,
    UnitContract,
    ValueBasis,
)
from cmp.modules.units.domain.system import DimensionId

Sha256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
StableKey = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_.-]{0,127}$")]


class OriginalUnitResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    unit: str
    scale_to_normalized: str
    offset_to_normalized: str

    @classmethod
    def from_domain(cls, value: OriginalUnit) -> OriginalUnitResponse:
        return cls(
            unit=value.unit,
            scale_to_normalized=value.scale_to_normalized,
            offset_to_normalized=value.offset_to_normalized,
        )


class CurveChannelResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: StableKey
    label: str
    quantity_semantics: str
    axis_role: AxisRole
    unit_contract: UnitContract
    dimension: DimensionId | None
    original_units: tuple[OriginalUnitResponse, ...]
    normalized_unit: str
    display_unit: str
    display_scale: str
    display_offset: str
    value_basis: ValueBasis

    @classmethod
    def from_domain(cls, value: CurveChannel) -> CurveChannelResponse:
        return cls(
            key=value.key,
            label=value.label,
            quantity_semantics=value.quantity_semantics,
            axis_role=value.axis_role,
            unit_contract=value.unit_contract,
            dimension=value.dimension,
            original_units=tuple(
                OriginalUnitResponse.from_domain(item) for item in value.original_units
            ),
            normalized_unit=value.normalized_unit,
            display_unit=value.display_unit,
            display_scale=value.display_scale,
            display_offset=value.display_offset,
            value_basis=value.value_basis,
        )


class CurveDeviationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: StableKey
    target_channel_key: StableKey
    scope: DeviationScope
    kind: DeviationKind
    method_id: StableKey
    method_version: str
    unit: str
    bound_direction: BoundDirection
    band_group: StableKey | None
    scalar_value: str | None
    series_key: StableKey | None
    source_count: Annotated[int, Field(ge=1)] | None
    source_count_series_key: StableKey | None
    confidence_level: Annotated[float, Field(gt=0, lt=1)] | None
    coverage: Coverage | None
    ddof: Annotated[int, Field(ge=0)] | None
    quantile_probability: Annotated[float, Field(ge=0, le=1)] | None
    quantile_method: str | None

    @classmethod
    def from_domain(cls, value: CurveDeviation) -> CurveDeviationResponse:
        return cls(
            key=value.key,
            target_channel_key=value.target_channel_key,
            scope=value.scope,
            kind=value.kind,
            method_id=value.method_id,
            method_version=value.method_version,
            unit=value.unit,
            bound_direction=value.bound_direction,
            band_group=value.band_group,
            scalar_value=value.scalar_value,
            series_key=value.series_key,
            source_count=value.source_count,
            source_count_series_key=value.source_count_series_key,
            confidence_level=value.confidence_level,
            coverage=value.coverage,
            ddof=value.ddof,
            quantile_probability=value.quantile_probability,
            quantile_method=value.quantile_method,
        )


class CurveDefinitionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    definition_version: Literal["1.0.0"]
    channels: tuple[CurveChannelResponse, ...]
    deviations: tuple[CurveDeviationResponse, ...]

    @classmethod
    def from_domain(cls, value: CurveDefinition) -> CurveDefinitionResponse:
        return cls(
            definition_version="1.0.0",
            channels=tuple(CurveChannelResponse.from_domain(item) for item in value.channels),
            deviations=tuple(
                CurveDeviationResponse.from_domain(item) for item in value.deviations
            ),
        )


class RevisionPinResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entity_type: StableKey
    entity_id: UUID
    revision_id: UUID

    @classmethod
    def from_domain(cls, value: RevisionPin) -> RevisionPinResponse:
        return cls(
            entity_type=value.entity_type,
            entity_id=value.entity_id,
            revision_id=value.revision_id,
        )


class ArtifactPinResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact_id: UUID
    sha256: Sha256
    schema_ref: str | None
    media_type: str

    @classmethod
    def from_domain(cls, value: ArtifactPin) -> ArtifactPinResponse:
        return cls(
            artifact_id=value.artifact_id,
            sha256=value.sha256,
            schema_ref=value.schema_ref,
            media_type=value.media_type,
        )


class SourcePinResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entity_type: StableKey
    entity_id: UUID
    revision_id: UUID
    artifact_id: UUID | None
    artifact_sha256: Sha256 | None

    @classmethod
    def from_domain(cls, value: SourcePin) -> SourcePinResponse:
        return cls(
            entity_type=value.entity_type,
            entity_id=value.entity_id,
            revision_id=value.revision_id,
            artifact_id=value.artifact_id,
            artifact_sha256=value.artifact_sha256,
        )


class ProvenancePointerResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: ProvenanceKind
    entity_id: UUID
    revision_id: UUID | None

    @classmethod
    def from_domain(cls, value: ProvenancePointer) -> ProvenancePointerResponse:
        return cls(kind=value.kind, entity_id=value.entity_id, revision_id=value.revision_id)


class CurveMetadataResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_version: Literal["1.0.0"] = "1.0.0"
    metadata_state: MetadataState
    definition_sha256: Sha256 | None
    definition: CurveDefinitionResponse | None
    owning_revision: RevisionPinResponse
    artifact: ArtifactPinResponse
    sources: tuple[SourcePinResponse, ...]
    provenance: tuple[ProvenancePointerResponse, ...]

    @classmethod
    def from_domain(cls, value: CurveMetadata) -> CurveMetadataResponse:
        return cls(
            metadata_state=value.state,
            definition_sha256=value.definition_sha256,
            definition=(
                CurveDefinitionResponse.from_domain(value.definition)
                if value.definition is not None
                else None
            ),
            owning_revision=RevisionPinResponse.from_domain(value.owning_revision),
            artifact=ArtifactPinResponse.from_domain(value.artifact),
            sources=tuple(SourcePinResponse.from_domain(item) for item in value.sources),
            provenance=tuple(
                ProvenancePointerResponse.from_domain(item) for item in value.provenance
            ),
        )


class CurveFloatSeriesResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: StableKey
    values: tuple[float | None, ...]


class CurveCountSeriesResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: StableKey
    values: tuple[Annotated[int, Field(ge=1)], ...]


class CurveSeriesPreviewResponse(BaseModel):
    """All series use the same returned indices after full Artifact validation."""

    model_config = ConfigDict(extra="forbid")

    point_count: Annotated[int, Field(ge=2)]
    returned_point_count: Annotated[int, Field(ge=2)]
    sampled: bool
    indices: tuple[Annotated[int, Field(ge=0)], ...]
    channels: tuple[CurveFloatSeriesResponse, ...]
    deviations: tuple[CurveFloatSeriesResponse, ...]
    source_counts: tuple[CurveCountSeriesResponse, ...]

    @classmethod
    def from_domain(cls, value: CurveSeriesPreview) -> CurveSeriesPreviewResponse:
        return cls(
            point_count=value.point_count,
            returned_point_count=value.returned_point_count,
            sampled=value.sampled,
            indices=value.indices,
            channels=tuple(
                CurveFloatSeriesResponse(key=key, values=values)
                for key, values in value.channels.items()
            ),
            deviations=tuple(
                CurveFloatSeriesResponse(key=key, values=values)
                for key, values in value.deviations.items()
            ),
            source_counts=tuple(
                CurveCountSeriesResponse(key=key, values=values)
                for key, values in value.source_counts.items()
            ),
        )


__all__ = [
    "ArtifactPinResponse",
    "CurveChannelResponse",
    "CurveCountSeriesResponse",
    "CurveDefinitionResponse",
    "CurveDeviationResponse",
    "CurveFloatSeriesResponse",
    "CurveMetadataResponse",
    "CurveSeriesPreviewResponse",
    "OriginalUnitResponse",
    "ProvenancePointerResponse",
    "RevisionPinResponse",
    "SourcePinResponse",
]

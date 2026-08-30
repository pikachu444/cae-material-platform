"""HTTP contract for governed fixed-frequency DMA TTS processing."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import Depends, FastAPI, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.processing.application.dma_frequency_master_curve import (
    CreatedDmaFrequencyMasterCurve,
    CreateDmaFrequencyMasterCurve,
    DmaFrequencyMasterCurveService,
    DmaImportProfilePin,
    DmaTestDataPin,
    RecommendDmaFrequencyMasterCurve,
)
from cmp.modules.processing.domain.dma_frequency_master_curve import (
    ArrheniusShiftLaw,
    DmaPartition,
    DmaProcessingError,
    DmaRowDisposition,
    DmaShiftLaw,
    DmaWlfStartingSuggestion,
    TabulatedShiftLaw,
    WlfShiftLaw,
)

type Dependency = Callable[..., object]
type Reason = Annotated[str, StringConstraints(min_length=1, max_length=2000)]


class TestDataPinInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: UUID
    revision_id: UUID
    content_sha256: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]

    def to_domain(self) -> DmaTestDataPin:
        return DmaTestDataPin(**self.model_dump())


class ImportProfilePinInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile_id: UUID
    revision_id: UUID
    content_sha256: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]

    def to_domain(self) -> DmaImportProfilePin:
        return DmaImportProfilePin(**self.model_dump())


class DmaDispositionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_ordinal: Annotated[int, Field(ge=0)]
    partition: DmaPartition
    exclusion_reason: str | None = None

    def to_domain(self) -> DmaRowDisposition:
        return DmaRowDisposition(**self.model_dump())


class TabulatedFactorInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    temperature_k: Annotated[float, Field(gt=0)]
    log10_a_t: float


class DmaShiftLawInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["tabulated", "wlf", "arrhenius"]
    reference_temperature_k: float | None = None
    c1: float | None = None
    c2_k: float | None = None
    activation_energy_j_per_mol: float | None = None
    factors: tuple[TabulatedFactorInput, ...] = ()
    value_origin: Literal[
        "source_shift_factors",
        "generic_wlf_at_tg_starting_suggestion",
        "engineer_edited",
        "engineer_entered",
    ]

    @model_validator(mode="after")
    def validate_variant(self) -> DmaShiftLawInput:
        if self.kind == "tabulated":
            if (
                not self.factors
                or self.reference_temperature_k is None
                or self.c1 is not None
                or self.c2_k is not None
                or self.activation_energy_j_per_mol is not None
            ):
                raise ValueError("tabulated shift law requires only factors")
        elif self.kind == "wlf":
            if (
                self.reference_temperature_k is None
                or self.c1 is None
                or self.c2_k is None
                or self.activation_energy_j_per_mol is not None
                or self.factors
            ):
                raise ValueError("WLF shift law requires Tref, C1, and C2")
        elif (
            self.reference_temperature_k is None
            or self.activation_energy_j_per_mol is None
            or self.c1 is not None
            or self.c2_k is not None
            or self.factors
        ):
            raise ValueError("Arrhenius shift law requires Tref and activation energy")
        return self

    def to_domain(self) -> DmaShiftLaw:
        if self.kind == "tabulated":
            assert self.reference_temperature_k is not None
            return TabulatedShiftLaw(
                self.reference_temperature_k,
                tuple((item.temperature_k, item.log10_a_t) for item in self.factors),
            )
        if self.kind == "wlf":
            assert self.reference_temperature_k is not None
            assert self.c1 is not None
            assert self.c2_k is not None
            return WlfShiftLaw(self.reference_temperature_k, self.c1, self.c2_k)
        assert self.reference_temperature_k is not None
        assert self.activation_energy_j_per_mol is not None
        return ArrheniusShiftLaw(
            self.reference_temperature_k,
            self.activation_energy_j_per_mol,
        )


class DmaMasterCurveRecommendationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    test_data: TestDataPinInput
    import_profile: ImportProfilePinInput


class ConfirmationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confirmed: bool
    reason: Reason


class CreateDmaMasterCurveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    classification: DataClassification
    label: Annotated[str, StringConstraints(min_length=1, max_length=200)]
    test_data: TestDataPinInput
    import_profile: ImportProfilePinInput
    dispositions: Annotated[tuple[DmaDispositionInput, ...], Field(min_length=2)]
    shift_law: DmaShiftLawInput
    confirmation: ConfirmationInput
    recommendation_sha256: Annotated[str | None, StringConstraints(pattern=r"^[0-9a-f]{64}$")] = (
        None
    )
    change_reason: Reason


class DmaMasterCurveRecommendationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_evidence: dict[str, Any]
    reference_temperature_k: float
    source_ordinal: int
    c1: float
    c2_k: float
    value_origin: str
    material_specific: bool
    requires_confirmation: bool
    rule_id: str
    rule_version: str
    recommendation_sha256: str

    @classmethod
    def from_domain(cls, value: DmaWlfStartingSuggestion) -> DmaMasterCurveRecommendationResponse:
        return cls(
            source_evidence=dict(value.source_evidence),
            reference_temperature_k=value.reference_temperature_k,
            source_ordinal=value.source_ordinal,
            c1=value.c1,
            c2_k=value.c2_k,
            value_origin=value.value_origin,
            material_specific=value.material_specific,
            requires_confirmation=value.requires_confirmation,
            rule_id=value.rule_id,
            rule_version=value.rule_version,
            recommendation_sha256=value.recommendation_sha256,
        )


class ProcessingOutputPinResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    output_id: UUID
    revision_id: UUID
    content_sha256: str
    metadata_artifact_id: UUID
    metadata_sha256: str
    result_artifact_id: UUID
    result_sha256: str
    result_schema_ref: str
    result_media_type: str


class CreatedDmaMasterCurveResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    loss_modulus_output: ProcessingOutputPinResponse | None
    master_curve_output: ProcessingOutputPinResponse


def _output(value: Any) -> ProcessingOutputPinResponse:
    content = value.content
    assert content.result_artifact_id is not None
    assert content.result_sha256 is not None
    assert content.result_schema_ref is not None
    assert content.result_media_type is not None
    return ProcessingOutputPinResponse(
        output_id=value.id,
        revision_id=value.current.revision_id,
        content_sha256=value.current.content_hash,
        metadata_artifact_id=content.output_artifact_id,
        metadata_sha256=content.output_sha256,
        result_artifact_id=content.result_artifact_id,
        result_sha256=content.result_sha256,
        result_schema_ref=content.result_schema_ref,
        result_media_type=content.result_media_type,
    )


def _created(value: CreatedDmaFrequencyMasterCurve) -> CreatedDmaMasterCurveResponse:
    return CreatedDmaMasterCurveResponse(
        loss_modulus_output=(
            None if value.loss_modulus_output is None else _output(value.loss_modulus_output)
        ),
        master_curve_output=_output(value.master_curve_output),
    )


def _error(error: DmaProcessingError) -> JSONResponse:
    status_code = (
        status.HTTP_409_CONFLICT
        if error.code in {"CMP-PROCESSING-4309", "CMP-PROCESSING-4310"}
        else status.HTTP_422_UNPROCESSABLE_CONTENT
    )
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": error.code,
                "cause": error.cause,
                "recovery_hint": error.recovery,
            }
        },
    )


def install_dma_frequency_master_curve_api(
    application: FastAPI,
    *,
    service: DmaFrequencyMasterCurveService | None,
    security_dependency: Dependency,
    execute_dependency: Dependency,
) -> None:
    def scope(request: Request) -> tuple[SecurityContext, AuthorizationDecision]:
        context = getattr(request.state, "security_context", None)
        decision = getattr(request.state, "authorization_decision", None)
        if not isinstance(context, SecurityContext) or not isinstance(
            decision, AuthorizationDecision
        ):
            raise RuntimeError("Processing dependencies did not initialize request scope")
        return context, decision

    @application.post(
        "/api/v1/processing/dma-frequency-master-curves/recommendations",
        response_model=DmaMasterCurveRecommendationResponse,
        status_code=status.HTTP_200_OK,
        dependencies=[Depends(security_dependency), Depends(execute_dependency)],
    )
    async def recommend(
        body: DmaMasterCurveRecommendationRequest,
        request: Request,
    ) -> DmaMasterCurveRecommendationResponse | JSONResponse:
        context, decision = scope(request)
        if service is None:
            return JSONResponse(status_code=503, content={"detail": "DMA TTS is unavailable"})
        try:
            value = await service.recommend(
                context,
                decision,
                RecommendDmaFrequencyMasterCurve(
                    body.test_data.to_domain(), body.import_profile.to_domain()
                ),
            )
        except DmaProcessingError as error:
            return _error(error)
        return DmaMasterCurveRecommendationResponse.from_domain(value)

    @application.post(
        "/api/v1/processing/dma-frequency-master-curves",
        response_model=CreatedDmaMasterCurveResponse,
        status_code=status.HTTP_201_CREATED,
        dependencies=[Depends(security_dependency), Depends(execute_dependency)],
    )
    async def create(
        body: CreateDmaMasterCurveRequest,
        request: Request,
    ) -> CreatedDmaMasterCurveResponse | JSONResponse:
        context, decision = scope(request)
        if service is None:
            return JSONResponse(status_code=503, content={"detail": "DMA TTS is unavailable"})
        try:
            value = await service.create(
                context,
                decision,
                CreateDmaFrequencyMasterCurve(
                    classification=body.classification,
                    label=body.label,
                    test_data=body.test_data.to_domain(),
                    import_profile=body.import_profile.to_domain(),
                    dispositions=tuple(item.to_domain() for item in body.dispositions),
                    shift_law=body.shift_law.to_domain(),
                    confirmed=body.confirmation.confirmed,
                    confirmation_reason=body.confirmation.reason,
                    recommendation_sha256=body.recommendation_sha256,
                    change_reason=body.change_reason,
                ),
            )
        except DmaProcessingError as error:
            return _error(error)
        return _created(value)

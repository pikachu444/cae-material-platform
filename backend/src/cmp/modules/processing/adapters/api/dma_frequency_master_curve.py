"""HTTP contract for the current governed DMA frequency-master-curve method."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Any, Literal, cast
from uuid import UUID

from fastapi import Depends, FastAPI, Query, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from cmp.modules.datasets.domain.governed_tabular import GovernedImportNotFound
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.processing.application.common_outputs import ProcessingOutputNotFound
from cmp.modules.processing.application.dma_frequency_master_curve import (
    CreatedDmaFrequencyMasterCurve,
    CreateDmaFrequencyMasterCurve,
    DmaFrequencyMasterCurveService,
    DmaImportProfilePin,
    DmaTestDataPin,
    RecommendDmaFrequencyMasterCurve,
    RecommendMultiDmaFrequencyMasterCurve,
)
from cmp.modules.processing.domain.dma_frequency_master_curve import (
    ArrheniusShiftLaw,
    DmaFrequencyMasterCurveRow,
    DmaPartition,
    DmaProcessingError,
    DmaRowDisposition,
    DmaWlfStartingSuggestion,
    TabulatedShiftLaw,
    WlfShiftLaw,
)
from cmp.modules.processing.domain.dma_multi_frequency_tts import (
    DmaFrequencySweepDisposition,
    DmaMultiFrequencyStartingSuggestion,
    DmaShiftLawRequest,
    DmaTtsAdjacentOptimizerControls,
    DmaTtsLawOptimizerControls,
    DmaTtsScoringControls,
)

type Dependency = Callable[..., object]
type Reason = Annotated[str, StringConstraints(min_length=1, max_length=2000)]
type Sha256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]


class TestDataPinInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: UUID
    revision_id: UUID
    content_sha256: Sha256

    def to_domain(self) -> DmaTestDataPin:
        return DmaTestDataPin(**self.model_dump())


class ImportProfilePinInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile_id: UUID
    revision_id: UUID
    content_sha256: Sha256

    def to_domain(self) -> DmaImportProfilePin:
        return DmaImportProfilePin(**self.model_dump())


class ConfirmationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confirmed: bool
    reason: Reason


class FixedRowDispositionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_ordinal: Annotated[int, Field(ge=0)]
    partition: DmaPartition
    exclusion_reason: str | None = None

    def to_domain(self) -> DmaRowDisposition:
        return DmaRowDisposition(**self.model_dump())


class SweepDispositionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_sweep_ordinal: Annotated[int, Field(ge=1, le=9_223_372_036_854_775_807)]
    representative_temperature_k: Annotated[float, Field(gt=0)]
    partition: DmaPartition
    exclusion_reason: str | None = None

    def to_domain(self) -> DmaFrequencySweepDisposition:
        return DmaFrequencySweepDisposition(**self.model_dump())


class TabulatedFactorInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    temperature_k: Annotated[float, Field(gt=0)]
    log10_a_t: float


class FixedManualShiftLawInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["manual_tabulated"]
    reference_temperature_k: Annotated[float, Field(gt=0)]
    manual_table: Annotated[tuple[TabulatedFactorInput, ...], Field(min_length=1)]

    def to_domain(self) -> TabulatedShiftLaw:
        return TabulatedShiftLaw(
            self.reference_temperature_k,
            tuple((item.temperature_k, item.log10_a_t) for item in self.manual_table),
        )


class FixedWlfShiftLawInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["wlf"]
    reference_temperature_k: Annotated[float, Field(gt=0)]
    c1: Annotated[float, Field(gt=0)]
    c2_k: Annotated[float, Field(gt=0)]

    def to_domain(self) -> WlfShiftLaw:
        return WlfShiftLaw(self.reference_temperature_k, self.c1, self.c2_k)


class FixedArrheniusShiftLawInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["arrhenius"]
    reference_temperature_k: Annotated[float, Field(gt=0)]
    activation_energy_j_per_mol: Annotated[float, Field(gt=0)]

    def to_domain(self) -> ArrheniusShiftLaw:
        return ArrheniusShiftLaw(
            self.reference_temperature_k,
            self.activation_energy_j_per_mol,
        )


FixedShiftLawInput = Annotated[
    FixedManualShiftLawInput | FixedWlfShiftLawInput | FixedArrheniusShiftLawInput,
    Field(discriminator="kind"),
]


class MultiManualShiftLawInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["manual_tabulated"]
    reference_temperature_k: Annotated[float, Field(gt=0)]
    manual_table: Annotated[tuple[TabulatedFactorInput, ...], Field(min_length=1)]

    def to_domain(self) -> DmaShiftLawRequest:
        return DmaShiftLawRequest(
            kind=self.kind,
            reference_temperature_k=self.reference_temperature_k,
            manual_table=tuple((item.temperature_k, item.log10_a_t) for item in self.manual_table),
        )


class _MultiFittedShiftLawInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reference_temperature_k: Annotated[float, Field(gt=0)]
    initial_parameters: Annotated[tuple[float, ...], Field(min_length=1)]
    lower_bounds: Annotated[tuple[float, ...], Field(min_length=1)]
    upper_bounds: Annotated[tuple[float, ...], Field(min_length=1)]


class MultiWlfShiftLawInput(_MultiFittedShiftLawInput):
    kind: Literal["wlf_fit"]

    @model_validator(mode="after")
    def exact_parameter_count(self) -> MultiWlfShiftLawInput:
        if not (
            len(self.initial_parameters) == len(self.lower_bounds) == len(self.upper_bounds) == 2
        ):
            raise ValueError("WLF fitting requires two explicit parameters")
        return self

    def to_domain(self) -> DmaShiftLawRequest:
        return DmaShiftLawRequest(
            kind=self.kind,
            reference_temperature_k=self.reference_temperature_k,
            initial_parameters=self.initial_parameters,
            lower_bounds=self.lower_bounds,
            upper_bounds=self.upper_bounds,
        )


class MultiArrheniusShiftLawInput(_MultiFittedShiftLawInput):
    kind: Literal["arrhenius_fit"]

    @model_validator(mode="after")
    def exact_parameter_count(self) -> MultiArrheniusShiftLawInput:
        if not (
            len(self.initial_parameters) == len(self.lower_bounds) == len(self.upper_bounds) == 1
        ):
            raise ValueError("Arrhenius fitting requires one explicit parameter")
        return self

    def to_domain(self) -> DmaShiftLawRequest:
        return DmaShiftLawRequest(
            kind=self.kind,
            reference_temperature_k=self.reference_temperature_k,
            initial_parameters=self.initial_parameters,
            lower_bounds=self.lower_bounds,
            upper_bounds=self.upper_bounds,
        )


MultiShiftLawInput = Annotated[
    MultiManualShiftLawInput | MultiWlfShiftLawInput | MultiArrheniusShiftLawInput,
    Field(discriminator="kind"),
]


class ScoringInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    minimum_overlap_decades: Annotated[float, Field(gt=0)]
    scoring_point_count: Annotated[int, Field(ge=2, le=10_001)]
    storage_weight: Annotated[float, Field(ge=0)]
    loss_weight: Annotated[float, Field(ge=0)]

    def to_domain(self) -> DmaTtsScoringControls:
        return DmaTtsScoringControls(
            minimum_overlap_decades=self.minimum_overlap_decades,
            overlap_evaluation_point_count=self.scoring_point_count,
            storage_weight=self.storage_weight,
            loss_weight=self.loss_weight,
        )


class AdjacentOptimizerInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    relative_shift_lower_bound_log10: float
    relative_shift_upper_bound_log10: float
    xatol: float
    maxiter: int
    seed: None = None

    def to_domain(self) -> DmaTtsAdjacentOptimizerControls:
        return DmaTtsAdjacentOptimizerControls(
            self.relative_shift_lower_bound_log10,
            self.relative_shift_upper_bound_log10,
            self.xatol,
            self.maxiter,
        )


class LawOptimizerInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    initial_parameters: Annotated[tuple[float, ...], Field(min_length=1)]
    lower_bounds: Annotated[tuple[float, ...], Field(min_length=1)]
    upper_bounds: Annotated[tuple[float, ...], Field(min_length=1)]
    ftol: float
    xtol: float
    gtol: float
    max_nfev: int
    seed: None = None

    @model_validator(mode="after")
    def matching_vectors(self) -> LawOptimizerInput:
        if not (len(self.initial_parameters) == len(self.lower_bounds) == len(self.upper_bounds)):
            raise ValueError("law optimizer starts and bounds must have equal length")
        return self

    def to_domain(self) -> DmaTtsLawOptimizerControls:
        return DmaTtsLawOptimizerControls(
            self.initial_parameters,
            self.lower_bounds,
            self.upper_bounds,
            self.ftol,
            self.xtol,
            self.gtol,
            self.max_nfev,
        )


class _CreateCommon(BaseModel):
    model_config = ConfigDict(extra="forbid")

    classification: DataClassification
    label: Annotated[str, StringConstraints(min_length=1, max_length=200)]
    test_data: TestDataPinInput
    import_profile: ImportProfilePinInput
    confirmation: ConfirmationInput
    change_reason: Reason


class FixedDmaMasterCurveRequest(_CreateCommon):
    input_mode: Literal["fixed_frequency_temperature_sweep"]
    row_dispositions: Annotated[tuple[FixedRowDispositionInput, ...], Field(min_length=1)]
    shift_law: FixedShiftLawInput
    recommendation_sha256: Sha256 | None = None

    def to_domain(self) -> CreateDmaFrequencyMasterCurve:
        return CreateDmaFrequencyMasterCurve(
            input_mode=self.input_mode,
            classification=self.classification,
            label=self.label,
            test_data=self.test_data.to_domain(),
            import_profile=self.import_profile.to_domain(),
            dispositions=tuple(item.to_domain() for item in self.row_dispositions),
            shift_law=self.shift_law.to_domain(),
            confirmed=self.confirmation.confirmed,
            confirmation_reason=self.confirmation.reason,
            change_reason=self.change_reason,
            recommendation_sha256=self.recommendation_sha256,
        )


class MultiDmaMasterCurveRequest(_CreateCommon):
    input_mode: Literal["multi_frequency_isotherms"]
    sweep_dispositions: Annotated[tuple[SweepDispositionInput, ...], Field(min_length=1)]
    reference_sweep_ordinal: Annotated[int, Field(ge=1, le=9_223_372_036_854_775_807)]
    shift_law: MultiShiftLawInput
    scoring: ScoringInput
    adjacent_optimizer: AdjacentOptimizerInput
    law_optimizer: LawOptimizerInput | None = None
    recommendation_sha256: Sha256 | None = None

    @model_validator(mode="after")
    def require_law_optimizer_for_fits(self) -> MultiDmaMasterCurveRequest:
        fitted = self.shift_law.kind in {"wlf_fit", "arrhenius_fit"}
        if fitted != (self.law_optimizer is not None):
            raise ValueError(
                "WLF/Arrhenius multi-frequency laws require law_optimizer; manual tables forbid it"
            )
        return self

    def to_domain(self) -> CreateDmaFrequencyMasterCurve:
        return CreateDmaFrequencyMasterCurve(
            input_mode=self.input_mode,
            classification=self.classification,
            label=self.label,
            test_data=self.test_data.to_domain(),
            import_profile=self.import_profile.to_domain(),
            dispositions=tuple(item.to_domain() for item in self.sweep_dispositions),
            shift_law=self.shift_law.to_domain(),
            confirmed=self.confirmation.confirmed,
            confirmation_reason=self.confirmation.reason,
            change_reason=self.change_reason,
            reference_sweep_ordinal=self.reference_sweep_ordinal,
            scoring=self.scoring.to_domain(),
            adjacent_optimizer=self.adjacent_optimizer.to_domain(),
            law_optimizer=(None if self.law_optimizer is None else self.law_optimizer.to_domain()),
            recommendation_sha256=self.recommendation_sha256,
        )


CreateDmaMasterCurveRequest = Annotated[
    FixedDmaMasterCurveRequest | MultiDmaMasterCurveRequest,
    Field(discriminator="input_mode"),
]


class DmaMasterCurveRecommendationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    test_data: TestDataPinInput
    import_profile: ImportProfilePinInput


class DmaMultiFrequencyRecommendationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    test_data: TestDataPinInput
    import_profile: ImportProfilePinInput
    reference_sweep_ordinal: Annotated[
        int, Field(ge=1, le=9_223_372_036_854_775_807)
    ]


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
    recommendation_sha256: Sha256

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


class DmaMultiRecommendationEvidenceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    test_data_document_id: UUID
    test_data_revision_id: UUID
    test_data_content_sha256: Sha256
    import_profile_id: UUID
    import_profile_revision_id: UUID
    import_profile_content_sha256: Sha256
    source_normalized_artifact_id: UUID
    source_normalized_artifact_sha256: Sha256


class MultiSweepSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_sweep_ordinal: Annotated[int, Field(ge=1, le=9_223_372_036_854_775_807)]
    representative_temperature_k: float
    point_count: Annotated[int, Field(ge=2)]
    source_frequency_min_hz: float
    source_frequency_max_hz: float


class DmaMultiFrequencyRecommendationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input_mode: Literal["multi_frequency_isotherms"]
    source_evidence: DmaMultiRecommendationEvidenceResponse
    sweeps: tuple[MultiSweepSummaryResponse, ...]
    reference_sweep_ordinal: Annotated[int, Field(ge=1, le=9_223_372_036_854_775_807)]
    reference_temperature_k: float
    sweep_dispositions: tuple[SweepDispositionInput, ...]
    shift_law: MultiWlfShiftLawInput
    scoring: ScoringInput
    adjacent_optimizer: AdjacentOptimizerInput
    law_optimizer: LawOptimizerInput
    profile_id: Literal["cmp.dma_tts.multi_frequency_wlf_starting_profile"]
    profile_version: Literal["1.0.0"]
    material_specific: Literal[False]
    production_readiness: Literal["non_production"]
    requires_confirmation: Literal[True]
    recommendation_sha256: Sha256

    @classmethod
    def from_domain(
        cls, value: DmaMultiFrequencyStartingSuggestion
    ) -> DmaMultiFrequencyRecommendationResponse:
        return cls(
            input_mode=cast(Literal["multi_frequency_isotherms"], value.input_mode),
            source_evidence=DmaMultiRecommendationEvidenceResponse.model_validate(
                value.source_evidence
            ),
            sweeps=tuple(
                MultiSweepSummaryResponse.model_validate(item)
                for item in value.sweeps
            ),
            reference_sweep_ordinal=value.reference_sweep_ordinal,
            reference_temperature_k=value.reference_temperature_k,
            sweep_dispositions=tuple(
                SweepDispositionInput.model_validate(item)
                for item in value.sweep_dispositions
            ),
            shift_law=MultiWlfShiftLawInput.model_validate(value.shift_law),
            scoring=ScoringInput.model_validate(value.scoring),
            adjacent_optimizer=AdjacentOptimizerInput.model_validate(
                value.adjacent_optimizer
            ),
            law_optimizer=LawOptimizerInput.model_validate(value.law_optimizer),
            profile_id=cast(
                Literal["cmp.dma_tts.multi_frequency_wlf_starting_profile"], value.profile_id
            ),
            profile_version=cast(Literal["1.0.0"], value.profile_version),
            material_specific=cast(Literal[False], value.material_specific),
            production_readiness=cast(
                Literal["non_production"], value.production_readiness
            ),
            requires_confirmation=cast(Literal[True], value.requires_confirmation),
            recommendation_sha256=value.recommendation_sha256,
        )


class ProcessingOutputPinResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    output_id: UUID
    revision_id: UUID
    content_sha256: Sha256
    metadata_artifact_id: UUID
    metadata_sha256: Sha256
    result_artifact_id: UUID
    result_sha256: Sha256
    result_schema_ref: str
    result_media_type: Literal["application/vnd.apache.parquet"]


class CreatedDmaMasterCurveResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    master_curve_output: ProcessingOutputPinResponse


class ExactLineagePinResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: UUID
    revision_id: UUID
    content_sha256: Sha256


class DmaIsothermResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input_mode: str
    source_sweep_ordinal: int | None
    representative_temperature_k: float
    partition: DmaPartition
    is_reference: bool
    exclusion_reason: str | None
    holdout_evaluation_status: str | None
    source_ordinals: tuple[int, ...]
    measured_temperature_k: tuple[float, ...]
    source_frequency_hz: tuple[float, ...]
    angular_frequency_rad_per_s: tuple[float, ...]
    storage_modulus_pa: tuple[float, ...]
    loss_modulus_pa: tuple[float, ...]
    source_tan_delta: tuple[float | None, ...]
    loss_modulus_origin: tuple[str, ...]
    reduced_angular_frequency_rad_per_s: tuple[float, ...] | None
    raw_angular_frequency_min_rad_per_s: float
    raw_angular_frequency_max_rad_per_s: float
    shifted_angular_frequency_min_rad_per_s: float | None
    shifted_angular_frequency_max_rad_per_s: float | None
    comparison_sweep_ordinal: int | None
    observed_log10_a_t: float | None
    applied_log10_a_t: float | None
    shift_factor: float | None
    shift_residual_log10_a_t: float | None
    overlap_log10_reduced_angular_frequency_min: float | None
    overlap_log10_reduced_angular_frequency_max: float | None
    scoring_point_count: int | None
    storage_mse: float | None
    loss_mse: float | None
    storage_rmse: float | None
    loss_rmse: float | None
    weighted_mse: float | None
    adjacent_success: bool | None
    adjacent_status: int | None
    adjacent_iterations: int | None
    adjacent_evaluations: int | None
    adjacent_objective: float | None

    @classmethod
    def from_domain(cls, row: DmaFrequencyMasterCurveRow) -> DmaIsothermResponse:
        return cls(**{field: getattr(row, field) for field in row.__dataclass_fields__})


class ReadDmaMasterCurveResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    output: ProcessingOutputPinResponse
    input_mode: Literal["fixed_frequency_temperature_sweep", "multi_frequency_isotherms"]
    options: dict[str, Any]
    isotherms: tuple[DmaIsothermResponse, ...]
    test_data: ExactLineagePinResponse
    import_profile: ExactLineagePinResponse


def _output(value: Any) -> ProcessingOutputPinResponse:
    content = value.content
    assert content.output_artifact_id is not None
    assert content.output_sha256 is not None
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
        master_curve_output=_output(value.master_curve_output),
    )


def _read(value: Any) -> ReadDmaMasterCurveResponse:
    output = _output(value.output)
    source = value.output.content
    assert source.source_document is not None
    assert source.governed_import_profile is not None
    return ReadDmaMasterCurveResponse(
        output=output,
        input_mode=value.input_mode,
        options=dict(value.options),
        isotherms=tuple(DmaIsothermResponse.from_domain(row) for row in value.rows),
        test_data=ExactLineagePinResponse(
            document_id=source.source_document.aggregate_id,
            revision_id=source.source_document.revision_id,
            content_sha256=source.source_document_sha256,
        ),
        import_profile=ExactLineagePinResponse(
            document_id=source.governed_import_profile.aggregate_id,
            revision_id=source.governed_import_profile.revision_id,
            content_sha256=source.governed_import_profile_sha256,
        ),
    )


def _error(error: DmaProcessingError) -> JSONResponse:
    status_code = (
        status.HTTP_409_CONFLICT
        if error.code
        in {
            "CMP-PROCESSING-4309",
            "CMP-PROCESSING-4310",
            "CMP-PROCESSING-4317",
        }
        else (
            status.HTTP_403_FORBIDDEN
            if error.code == "CMP-PROCESSING-4030"
            else (
                status.HTTP_503_SERVICE_UNAVAILABLE
                if error.code == "CMP-PROCESSING-5030"
                else status.HTTP_422_UNPROCESSABLE_CONTENT
            )
        )
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


def _hidden_source_error() -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={
            "error": {
                "code": "CMP-PROCESSING-4040",
                "cause": "DMA source or Import Profile is not visible in this tenant",
                "recovery_hint": "Select visible exact Test Data and Import Profile revisions.",
            }
        },
    )


def install_dma_frequency_master_curve_api(
    application: FastAPI,
    *,
    service: DmaFrequencyMasterCurveService | None,
    security_dependency: Dependency,
    execute_dependency: Dependency,
    read_dependency: Dependency | None = None,
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
        except GovernedImportNotFound:
            return _hidden_source_error()
        except DmaProcessingError as error:
            return _error(error)
        return DmaMasterCurveRecommendationResponse.from_domain(value)

    @application.post(
        "/api/v1/processing/dma-frequency-master-curves/recommendations/multi-frequency",
        response_model=DmaMultiFrequencyRecommendationResponse,
        status_code=status.HTTP_200_OK,
        dependencies=[Depends(security_dependency), Depends(execute_dependency)],
    )
    async def recommend_multi(
        body: DmaMultiFrequencyRecommendationRequest,
        request: Request,
    ) -> DmaMultiFrequencyRecommendationResponse | JSONResponse:
        context, decision = scope(request)
        if service is None:
            return JSONResponse(status_code=503, content={"detail": "DMA TTS is unavailable"})
        try:
            value = await service.recommend_multi(
                context,
                decision,
                RecommendMultiDmaFrequencyMasterCurve(
                    body.test_data.to_domain(),
                    body.import_profile.to_domain(),
                    body.reference_sweep_ordinal,
                ),
            )
        except GovernedImportNotFound:
            return _hidden_source_error()
        except DmaProcessingError as error:
            return _error(error)
        return DmaMultiFrequencyRecommendationResponse.from_domain(value)

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
            value = await service.create(context, decision, body.to_domain())
        except GovernedImportNotFound:
            return _hidden_source_error()
        except DmaProcessingError as error:
            return _error(error)
        return _created(value)

    @application.get(
        "/api/v1/processing/dma-frequency-master-curves/{output_id}/revisions/{revision_id}",
        response_model=ReadDmaMasterCurveResponse,
        status_code=status.HTTP_200_OK,
        dependencies=[
            Depends(security_dependency),
            Depends(read_dependency or execute_dependency),
        ],
    )
    async def read(
        output_id: UUID,
        revision_id: UUID,
        request: Request,
        content_sha256: Annotated[str, Query(pattern=r"^[0-9a-f]{64}$")],
    ) -> ReadDmaMasterCurveResponse | JSONResponse:
        context, decision = scope(request)
        if service is None:
            return JSONResponse(status_code=503, content={"detail": "DMA TTS is unavailable"})
        try:
            value = await service.read(context, decision, output_id, revision_id, content_sha256)
        except ProcessingOutputNotFound:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={"detail": "Processing Output is not visible in this tenant"},
            )
        except DmaProcessingError as error:
            return _error(error)
        return _read(value)

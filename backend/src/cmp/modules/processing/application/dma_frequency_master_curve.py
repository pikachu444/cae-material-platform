"""Application boundary for the governed DMA master-curve output."""

from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import cast
from uuid import UUID, uuid4

from cmp.modules.artifacts.application.content import (
    ArtifactBatchCommitHook,
    ArtifactService,
    FinalizedArtifact,
    PrepareArtifact,
)
from cmp.modules.artifacts.domain.content import (
    ArtifactAccessDenied,
    ArtifactConflict,
    ArtifactIntegrityError,
    ArtifactKind,
    ArtifactNotFound,
    ArtifactRecord,
    ArtifactStateError,
)
from cmp.modules.artifacts.domain.uploads import ObjectStoreError
from cmp.modules.datasets.application.canonical_test_data import (
    CanonicalTestDataService,
    GovernedTestDataSource,
    TestDataDocumentSnapshot,
)
from cmp.modules.datasets.application.governed_import import (
    GovernedImportService,
    ImportProfileRevisionSnapshot,
)
from cmp.modules.datasets.domain.canonical_test_data import (
    CanonicalTestDataDocument,
    TestDataChannel,
    parse_canonical_test_data,
)
from cmp.modules.datasets.domain.governed_tabular import TabularDataSchema
from cmp.modules.identity_access.application.authorization import AuthorizationService
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
    Permission,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.processing.application.common_outputs import (
    PROCESSING_OUTPUT_MEDIA_TYPE,
    PROCESSING_OUTPUT_SCHEMA_ID_1_6,
    PROCESSING_OUTPUT_SCHEMA_VERSION_1_6,
    ExactRevisionPin,
    ProcessingOutputContent,
    ProcessingOutputNotFound,
    ProcessingOutputRepository,
    ProcessingOutputSnapshot,
)
from cmp.modules.processing.domain.common_pipeline import ProcessingStep
from cmp.modules.processing.domain.dma_frequency_master_curve import (
    DMA_FREQUENCY_MASTER_CURVE_METHOD_ID,
    DMA_FREQUENCY_MASTER_CURVE_METHOD_VERSION,
    DMA_FREQUENCY_MASTER_CURVE_PARQUET_SCHEMA_ID,
    DMA_TTS_WARNINGS,
    ArrheniusShiftLaw,
    DmaFrequencyMasterCurveRow,
    DmaInputMode,
    DmaProcessingError,
    DmaRowDisposition,
    DmaShiftLaw,
    DmaTemperatureSweepRow,
    DmaWlfStartingSuggestion,
    TabulatedShiftLaw,
    WlfShiftLaw,
    build_frequency_master_curve,
    frequency_master_curve_parquet_bytes,
    recommend_wlf_starting_values,
)
from cmp.modules.processing.domain.dma_frequency_master_curve_result import (
    from_parquet,
    validate_options_against_rows,
)
from cmp.modules.processing.domain.dma_multi_frequency_tts import (
    DmaFrequencySweep,
    DmaFrequencySweepDisposition,
    DmaFrequencySweepPoint,
    DmaMultiFrequencyStartingSuggestion,
    DmaShiftLawRequest,
    DmaTtsAdjacentOptimizerControls,
    DmaTtsLawOptimizerControls,
    DmaTtsScoringControls,
    build_multi_frequency_master_curve,
    representative_temperature_for_sweep,
)
from cmp.modules.provenance.domain.model import ProvenanceConflict
from cmp.shared.domain.revisions import canonical_json_bytes, content_sha256


@dataclass(frozen=True, slots=True)
class DmaTestDataPin:
    document_id: UUID
    revision_id: UUID
    content_sha256: str


@dataclass(frozen=True, slots=True)
class DmaImportProfilePin:
    profile_id: UUID
    revision_id: UUID
    content_sha256: str


@dataclass(frozen=True, slots=True)
class RecommendDmaFrequencyMasterCurve:
    test_data: DmaTestDataPin
    import_profile: DmaImportProfilePin


@dataclass(frozen=True, slots=True)
class RecommendMultiDmaFrequencyMasterCurve:
    test_data: DmaTestDataPin
    import_profile: DmaImportProfilePin
    reference_sweep_ordinal: int


@dataclass(frozen=True, slots=True)
class CreateDmaFrequencyMasterCurve:
    input_mode: str
    classification: DataClassification
    label: str
    test_data: DmaTestDataPin
    import_profile: DmaImportProfilePin
    dispositions: tuple[DmaRowDisposition | DmaFrequencySweepDisposition, ...]
    shift_law: DmaShiftLaw | DmaShiftLawRequest | None
    confirmed: bool
    confirmation_reason: str
    change_reason: str
    recommendation_sha256: str | None = None
    reference_sweep_ordinal: int | None = None
    scoring: DmaTtsScoringControls | None = None
    adjacent_optimizer: DmaTtsAdjacentOptimizerControls | None = None
    law_optimizer: DmaTtsLawOptimizerControls | None = None


@dataclass(frozen=True, slots=True)
class CreatedDmaFrequencyMasterCurve:
    master_curve_output: ProcessingOutputSnapshot


@dataclass(frozen=True, slots=True)
class ReadDmaFrequencyMasterCurve:
    output: ProcessingOutputSnapshot
    input_mode: str
    options: Mapping[str, object]
    rows: tuple[DmaFrequencyMasterCurveRow, ...]
    test_data: ExactRevisionPin
    import_profile: ExactRevisionPin


@dataclass(frozen=True, slots=True)
class _ResolvedInput:
    document: CanonicalTestDataDocument
    fixed_rows: tuple[DmaTemperatureSweepRow, ...]
    sweeps: tuple[DmaFrequencySweep, ...]
    test_data_snapshot: TestDataDocumentSnapshot
    import_profile_snapshot: ImportProfileRevisionSnapshot


def _channel(document: CanonicalTestDataDocument, semantics: str) -> TestDataChannel | None:
    matches = tuple(item for item in document.channels if item.quantity_semantics == semantics)
    if len(matches) > 1:
        raise DmaProcessingError(
            "CMP-PROCESSING-4318",
            f"Test Data repeats channel semantics {semantics}",
            "Create a new exact Test Data revision with one governed channel.",
        )
    return matches[0] if matches else None


def _required_channel(document: CanonicalTestDataDocument, semantics: str) -> TestDataChannel:
    channel = _channel(document, semantics)
    if channel is None:
        raise DmaProcessingError(
            "CMP-PROCESSING-4318",
            f"Test Data is missing channel semantics {semantics}",
            "Map the required DMA quantity and import a new exact Test Data revision.",
        )
    return channel


def _float_at(channel: TestDataChannel, ordinal: int) -> float:
    value = channel.normalized_values[ordinal]
    if value is None:
        raise DmaProcessingError(
            "CMP-PROCESSING-4312",
            f"channel {channel.key} has a missing value at source ordinal {ordinal}",
            "Correct the immutable source row and import a new Test Data revision.",
        )
    result = float(value)
    if not math.isfinite(result):
        raise DmaProcessingError(
            "CMP-PROCESSING-4312",
            f"channel {channel.key} has a non-finite value",
            "Correct the immutable source row and import a new Test Data revision.",
        )
    return result


def _frequency_hz(document: CanonicalTestDataDocument) -> float:
    matches = tuple(item for item in document.conditions if item.key == "frequency")
    if (
        len(matches) != 1
        or matches[0].quantity_semantics != "frequency.cyclic"
        or matches[0].normalized_unit != "Hz"
        or matches[0].normalized_value <= Decimal(0)
    ):
        raise DmaProcessingError(
            "CMP-PROCESSING-4318",
            "Test Data does not carry one positive fixed cyclic-frequency condition",
            "Record the fixed frequency as frequency.cyclic normalized to Hz.",
        )
    return float(matches[0].normalized_value)


def _fixed_rows(document: CanonicalTestDataDocument) -> tuple[DmaTemperatureSweepRow, ...]:
    temperature = _required_channel(document, "physics.temperature")
    storage = _required_channel(document, "mechanics.modulus.storage")
    loss = _channel(document, "mechanics.modulus.loss")
    tan_delta = _channel(document, "mechanics.loss_factor")
    if loss is None and tan_delta is None:
        raise DmaProcessingError(
            "CMP-PROCESSING-4318",
            "fixed DMA Test Data has neither loss modulus nor tan delta",
            "Map loss modulus, tan delta, or both.",
        )
    count = len(temperature.normalized_values)
    channels = tuple(item for item in (storage, loss, tan_delta) if item is not None)
    if any(len(item.normalized_values) != count for item in channels):
        raise DmaProcessingError(
            "CMP-PROCESSING-4318",
            "fixed DMA channels have different row counts",
            "Reload the exact canonical Test Data artifact.",
        )
    loss_values = tuple(
        None if loss is None else loss.normalized_values[index] for index in range(count)
    )
    tan_values = tuple(
        None if tan_delta is None else tan_delta.normalized_values[index] for index in range(count)
    )
    if (
        loss is not None
        and any(value is None for value in loss_values)
        and any(value is not None for value in loss_values)
    ):
        raise DmaProcessingError(
            "CMP-PROCESSING-4312",
            "fixed DMA loss modulus is mixed measured/missing",
            (
                "Provide measured loss modulus for every row or omit it for every "
                "row and supply tan_delta."
            ),
        )
    if (
        tan_delta is not None
        and any(value is None for value in tan_values)
        and any(value is not None for value in tan_values)
    ):
        raise DmaProcessingError(
            "CMP-PROCESSING-4312",
            "fixed DMA tan_delta is mixed measured/missing",
            "Provide tan_delta for every row or omit it for every row.",
        )
    if loss is not None and all(value is None for value in loss_values):
        loss = None
    if tan_delta is not None and all(value is None for value in tan_values):
        tan_delta = None
    if loss is None and tan_delta is None:
        raise DmaProcessingError(
            "CMP-PROCESSING-4312",
            "fixed DMA derived loss modulus lacks tan_delta",
            "Supply tan_delta for every row when measured loss modulus is absent.",
        )
    if loss is None and any(value is None for value in tan_values):
        raise DmaProcessingError(
            "CMP-PROCESSING-4312",
            "fixed DMA tan_delta is mixed measured/missing",
            "Provide tan_delta for every row when deriving loss modulus.",
        )
    frequency = _frequency_hz(document)
    rows = tuple(
        DmaTemperatureSweepRow(
            index,
            _float_at(temperature, index),
            frequency,
            _float_at(storage, index),
            None if loss is None else _float_at(loss, index),
            None if tan_delta is None else _float_at(tan_delta, index),
        )
        for index in range(count)
    )
    if (
        loss is not None
        and tan_delta is not None
        and any(
            row.loss_modulus_pa is None
            or row.tan_delta is None
            or not math.isclose(
                row.loss_modulus_pa,
                row.storage_modulus_pa * row.tan_delta,
                rel_tol=1e-12,
                abs_tol=1e-12,
            )
            for row in rows
        )
    ):
        raise DmaProcessingError(
            "CMP-PROCESSING-4312",
            "fixed measured loss modulus conflicts with tan delta",
            (
                "Correct the loss/tan-delta source channels or create a corrected "
                "immutable Test Data revision."
            ),
        )
    return rows


def _positive_source_sweep_ordinal(channel: TestDataChannel, index: int) -> int:
    value = channel.normalized_values[index]
    if value is None or value != value.to_integral_value():
        raise DmaProcessingError(
            "CMP-PROCESSING-4312",
            f"source sweep ordinal is not a direct integer at source row {index}",
            "Import the source identity as an integer token in the governed profile.",
        )
    ordinal = int(value)
    if not 1 <= ordinal <= 9_223_372_036_854_775_807:
        raise DmaProcessingError(
            "CMP-PROCESSING-4312",
            "source sweep ordinal is outside positive int64",
            "Use the exact positive source sweep identity from the source file.",
        )
    return ordinal


def _multi_sweeps(document: CanonicalTestDataDocument) -> tuple[DmaFrequencySweep, ...]:
    sweep_ordinal = _required_channel(document, "test.sweep.ordinal")
    temperature = _required_channel(document, "physics.temperature")
    frequency = _required_channel(document, "frequency.cyclic")
    storage = _required_channel(document, "mechanics.modulus.storage")
    loss = _required_channel(document, "mechanics.modulus.loss")
    count = len(sweep_ordinal.normalized_values)
    channels = (temperature, frequency, storage, loss)
    if any(len(item.normalized_values) != count for item in channels):
        raise DmaProcessingError(
            "CMP-PROCESSING-4318",
            "multi-frequency DMA channels have different row counts",
            "Reload the exact canonical Test Data artifact.",
        )
    grouped: dict[int, list[DmaFrequencySweepPoint]] = defaultdict(list)
    for index in range(count):
        ordinal = _positive_source_sweep_ordinal(sweep_ordinal, index)
        grouped[ordinal].append(
            DmaFrequencySweepPoint(
                index,
                _float_at(temperature, index),
                _float_at(frequency, index),
                _float_at(storage, index),
                _float_at(loss, index),
            )
        )
    return tuple(DmaFrequencySweep(key, tuple(value)) for key, value in sorted(grouped.items()))


def _fixed_law_options(law: DmaShiftLaw) -> dict[str, object]:
    if isinstance(law, WlfShiftLaw):
        return {
            "kind": "wlf",
            "reference_temperature_k": law.reference_temperature_k,
            "parameter_source": "supplied",
            "c1": law.c1,
            "c2_k": law.c2_k,
        }
    from cmp.modules.processing.domain.dma_frequency_master_curve import (
        ArrheniusShiftLaw,
        TabulatedShiftLaw,
    )

    if isinstance(law, TabulatedShiftLaw):
        return {
            "kind": "manual_tabulated",
            "reference_temperature_k": law.reference_temperature_k,
            "parameter_source": "supplied",
            "manual_table": [
                {"temperature_k": temperature, "log10_a_t": shift}
                for temperature, shift in law.log10_a_t_by_temperature_k
            ],
        }
    assert isinstance(law, ArrheniusShiftLaw)
    return {
        "kind": "arrhenius",
        "reference_temperature_k": law.reference_temperature_k,
        "parameter_source": "supplied",
        "activation_energy_j_per_mol": law.activation_energy_j_per_mol,
        "gas_constant_j_per_mol_k": law.gas_constant_j_per_mol_k,
    }


def _multi_shift_law_request_document(law: DmaShiftLawRequest) -> dict[str, object]:
    if law.kind == "manual_tabulated":
        return {
            "kind": law.kind,
            "reference_temperature_k": law.reference_temperature_k,
            "manual_table": [
                {"temperature_k": temperature, "log10_a_t": shift}
                for temperature, shift in law.manual_table
            ],
        }
    document: dict[str, object] = {
        "kind": law.kind,
        "reference_temperature_k": law.reference_temperature_k,
        "initial_parameters": list(law.initial_parameters),
        "lower_bounds": list(law.lower_bounds),
        "upper_bounds": list(law.upper_bounds),
    }
    if law.kind == "arrhenius_fit":
        document["gas_constant"] = law.gas_constant
    return document


def _multi_scoring_document(value: DmaTtsScoringControls) -> dict[str, object]:
    return {
        "minimum_overlap_decades": value.minimum_overlap_decades,
        "scoring_point_count": value.overlap_evaluation_point_count,
        "storage_weight": value.storage_weight,
        "loss_weight": value.loss_weight,
    }


def _multi_adjacent_document(value: DmaTtsAdjacentOptimizerControls) -> dict[str, object]:
    return {
        "relative_shift_lower_bound_log10": value.relative_shift_lower_bound_log10,
        "relative_shift_upper_bound_log10": value.relative_shift_upper_bound_log10,
        "xatol": value.xatol,
        "maxiter": value.maxiter,
        "seed": None,
    }


def _multi_law_optimizer_document(
    value: DmaTtsLawOptimizerControls | None,
) -> dict[str, object] | None:
    if value is None:
        return None
    return {
        "initial_parameters": list(value.initial_parameters),
        "lower_bounds": list(value.lower_bounds),
        "upper_bounds": list(value.upper_bounds),
        "ftol": value.ftol,
        "xtol": value.xtol,
        "gtol": value.gtol,
        "max_nfev": value.max_nfev,
        "seed": None,
    }


def _multi_disposition_document(
    value: DmaFrequencySweepDisposition,
) -> dict[str, object]:
    return {
        "source_sweep_ordinal": value.source_sweep_ordinal,
        "representative_temperature_k": value.representative_temperature_k,
        "partition": value.partition.value,
        "exclusion_reason": value.exclusion_reason,
    }


def _options(
    *,
    input_mode: str,
    source: TestDataDocumentSnapshot,
    rows: tuple[DmaFrequencyMasterCurveRow, ...],
    reference: dict[str, object],
    shift_law: dict[str, object],
    scoring: dict[str, object] | None,
    adjacent_optimizer: dict[str, object] | None,
    law_optimizer: dict[str, object] | None,
    residual_summary: dict[str, object] | None,
    application_range: dict[str, object] | None,
    recommendation: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "input_mode": input_mode,
        "source_normalized_artifact_id": str(source.content.normalized_artifact_id),
        "source_normalized_artifact_sha256": source.content.normalized_sha256,
        "result_row_count": len(rows),
        "frequency_conversion": "omega_rad_per_s=2*pi*frequency_hz",
        "shift_direction": "omega_reduced=omega*10**log10_a_t",
        "log_base": 10,
        "reference": reference,
        "shift_law": shift_law,
        "scoring": scoring,
        "adjacent_optimizer": adjacent_optimizer,
        "law_optimizer": law_optimizer,
        "residual_summary": residual_summary,
        "application_range": application_range,
        "recommendation": recommendation,
        "assessment": {
            "adequacy": "not_assessed",
            "uncertainty": "not_provided",
            "identifiability": "not_assessed",
            "production_readiness": "non_production",
        },
        "warnings": list(DMA_TTS_WARNINGS),
    }


class DmaFrequencyMasterCurveService:
    def __init__(
        self,
        *,
        test_data: CanonicalTestDataService,
        governed_imports: GovernedImportService,
        outputs: ProcessingOutputRepository,
        artifacts: ArtifactService,
        authorization: AuthorizationService,
        id_factory: Callable[[], UUID] = uuid4,
        dma_provenance_writer: Callable[..., None] | None = None,
    ) -> None:
        self._test_data = test_data
        self._governed_imports = governed_imports
        self._outputs = outputs
        self._artifacts = artifacts
        self._authorization = authorization
        self._id = id_factory
        self._dma_provenance_writer = dma_provenance_writer

    async def _resolve(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        test_data: DmaTestDataPin,
        import_profile: DmaImportProfilePin,
        input_mode: str,
    ) -> _ResolvedInput:
        if decision.permission is not Permission.PROCESSING_EXECUTE:
            raise DmaProcessingError(
                "CMP-PROCESSING-4030",
                "processing authorization is invalid",
                "Request Processing execute permission for this project.",
            )
        dataset_read = self._authorization.authorize(context, Permission.DATASET_READ)
        snapshot, canonical_bytes = await self._test_data.export_document(
            context, dataset_read, test_data.document_id, test_data.revision_id
        )
        if snapshot.current.content_hash != test_data.content_sha256:
            raise DmaProcessingError(
                "CMP-PROCESSING-4317",
                "Test Data content digest does not match the exact revision",
                "Reload the exact Test Data revision and retry with its digest.",
            )
        current = self._test_data.get_document(context, dataset_read, test_data.document_id)
        if current.current.revision_id != test_data.revision_id:
            raise DmaProcessingError(
                "CMP-PROCESSING-4309",
                "Test Data pin is no longer current",
                "Create a new DMA output from the current Test Data revision.",
            )
        source = snapshot.content.governed_source
        if source is None or source.tabular_import is None:
            raise DmaProcessingError(
                "CMP-PROCESSING-4318",
                "Test Data has no governed tabular lineage",
                "Import the DMA source through an approved governed Import Profile.",
            )
        lineage_profile = source.tabular_import.import_profile
        if (
            lineage_profile.aggregate_id != import_profile.profile_id
            or lineage_profile.revision_id != import_profile.revision_id
        ):
            raise DmaProcessingError(
                "CMP-PROCESSING-4317",
                "Import Profile pin does not match Test Data lineage",
                "Use the exact Import Profile revision recorded by Test Data.",
            )
        profile = self._governed_imports.get_profile_revision_for_calibration(
            context, dataset_read, import_profile.profile_id, import_profile.revision_id
        )
        if profile.revision.record.content_hash != import_profile.content_sha256:
            raise DmaProcessingError(
                "CMP-PROCESSING-4317",
                "Import Profile content digest does not match the exact revision",
                "Reload the exact Import Profile revision and retry with its digest.",
            )
        current_profile = self._governed_imports.get_profile(
            context=context, decision=dataset_read, profile_id=import_profile.profile_id
        )
        if current_profile.current.record.revision_id != import_profile.revision_id:
            raise DmaProcessingError(
                "CMP-PROCESSING-4309",
                "Import Profile pin is no longer current",
                "Create a new DMA output from the current Import Profile revision.",
            )
        expected_schema = (
            TabularDataSchema.DMA_TEMPERATURE_SWEEP
            if input_mode == DmaInputMode.FIXED_FREQUENCY_TEMPERATURE_SWEEP.value
            else TabularDataSchema.DMA_FREQUENCY_TEMPERATURE_SWEEP
        )
        if (
            profile.revision.content.data_schema is not expected_schema
            or profile.revision.content.schema_version != "1.3.0"
            or profile.revision.content.deformation_mode != "shear"
        ):
            raise DmaProcessingError(
                "CMP-PROCESSING-4318",
                "Import Profile does not match the selected current DMA input mode contract",
                (
                    "Use schema 1.3.0 with deformation_mode=shear and the exact "
                    "profile shape for the selected input_mode."
                ),
            )
        if snapshot.current.scope.classification != profile.revision.record.scope.classification:
            raise DmaProcessingError(
                "CMP-PROCESSING-4317",
                "Test Data and Import Profile classifications differ",
                "Create aligned governed revisions in the same classification.",
            )
        try:
            decoded = json.loads(canonical_bytes)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise DmaProcessingError(
                "CMP-PROCESSING-4317",
                "canonical Test Data artifact is not valid JSON",
                "Reload the immutable canonical Test Data artifact.",
            ) from error
        if not isinstance(decoded, Mapping):
            raise DmaProcessingError(
                "CMP-PROCESSING-4317",
                "canonical Test Data artifact is not an object",
                "Reload the immutable canonical Test Data artifact.",
            )
        document = parse_canonical_test_data(decoded)
        fixed_rows = (
            _fixed_rows(document)
            if input_mode == DmaInputMode.FIXED_FREQUENCY_TEMPERATURE_SWEEP.value
            else ()
        )
        sweeps = (
            _multi_sweeps(document)
            if input_mode == DmaInputMode.MULTI_FREQUENCY_ISOTHERMS.value
            else ()
        )
        return _ResolvedInput(document, fixed_rows, sweeps, snapshot, profile)

    async def recommend(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: RecommendDmaFrequencyMasterCurve,
    ) -> DmaWlfStartingSuggestion:
        resolved = await self._resolve(
            context,
            decision,
            command.test_data,
            command.import_profile,
            DmaInputMode.FIXED_FREQUENCY_TEMPERATURE_SWEEP.value,
        )
        return recommend_wlf_starting_values(
            resolved.fixed_rows,
            source_evidence={
                "test_data_id": str(command.test_data.document_id),
                "test_data_revision_id": str(command.test_data.revision_id),
                "test_data_sha256": command.test_data.content_sha256,
                "import_profile_id": str(command.import_profile.profile_id),
                "import_profile_revision_id": str(command.import_profile.revision_id),
                "import_profile_sha256": command.import_profile.content_sha256,
            },
        )

    async def recommend_multi(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: RecommendMultiDmaFrequencyMasterCurve,
    ) -> DmaMultiFrequencyStartingSuggestion:
        resolved = await self._resolve(
            context,
            decision,
            command.test_data,
            command.import_profile,
            DmaInputMode.MULTI_FREQUENCY_ISOTHERMS.value,
        )
        sweeps = resolved.sweeps
        if len(sweeps) < 3:
            raise DmaProcessingError(
                "CMP-PROCESSING-4316",
                "multi-frequency DMA recommendation requires at least three sweeps",
                "Provide at least three valid source frequency sweeps.",
            )
        if any(len(sweep.points) < 2 for sweep in sweeps):
            raise DmaProcessingError(
                "CMP-PROCESSING-4312",
                "a multi-frequency DMA sweep has fewer than two measured points",
                "Provide at least two finite positive points in every source sweep.",
            )
        by_ordinal = {sweep.source_sweep_ordinal: sweep for sweep in sweeps}
        if command.reference_sweep_ordinal not in by_ordinal:
            raise DmaProcessingError(
                "CMP-PROCESSING-4316",
                "the requested reference sweep is not present in the exact source",
                "Select one positive source_sweep_ordinal from the measured source sweeps.",
            )
        temperatures = {
            ordinal: float(representative_temperature_for_sweep(sweep))
            for ordinal, sweep in by_ordinal.items()
        }
        if len(set(temperatures.values())) != len(temperatures):
            raise DmaProcessingError(
                "CMP-PROCESSING-4316",
                "multi-frequency source sweeps have duplicate representative temperatures",
                "Provide one distinct representative temperature per source sweep.",
            )
        reference_temperature = temperatures[command.reference_sweep_ordinal]
        holdout_ordinal = min(
            (ordinal for ordinal in by_ordinal if ordinal != command.reference_sweep_ordinal),
            key=lambda ordinal: (-abs(temperatures[ordinal] - reference_temperature), ordinal),
        )
        sweeps_document = tuple(
            {
                "source_sweep_ordinal": ordinal,
                "representative_temperature_k": temperatures[ordinal],
                "point_count": len(by_ordinal[ordinal].points),
                "source_frequency_min_hz": min(
                    point.frequency_hz for point in by_ordinal[ordinal].points
                ),
                "source_frequency_max_hz": max(
                    point.frequency_hz for point in by_ordinal[ordinal].points
                ),
            }
            for ordinal in sorted(by_ordinal)
        )
        dispositions = tuple(
            {
                "source_sweep_ordinal": ordinal,
                "representative_temperature_k": temperatures[ordinal],
                "partition": "HOLDOUT" if ordinal == holdout_ordinal else "CALIBRATION",
                "exclusion_reason": None,
            }
            for ordinal in sorted(by_ordinal)
        )
        # The fitted law is also evaluated against HOLDOUT sweeps.  Its
        # governed bounds therefore have to stay WLF-safe for every included
        # sweep, not only the calibration partition.
        minimum_included_temperature = min(temperatures.values())
        lower_c2 = max(
            1e-3,
            reference_temperature - minimum_included_temperature + 1e-3,
        )
        initial_parameters = (17.44, max(51.6, lower_c2 + 1.0))
        shift_law = {
            "kind": "wlf_fit",
            "reference_temperature_k": reference_temperature,
            "initial_parameters": list(initial_parameters),
            "lower_bounds": [1e-8, lower_c2],
            "upper_bounds": [1000.0, 5000.0],
        }
        scoring = {
            "minimum_overlap_decades": 0.25,
            "scoring_point_count": 101,
            "storage_weight": 0.5,
            "loss_weight": 0.5,
        }
        adjacent_optimizer = {
            "relative_shift_lower_bound_log10": -12.0,
            "relative_shift_upper_bound_log10": 12.0,
            "xatol": 1e-10,
            "maxiter": 1000,
            "seed": None,
        }
        law_optimizer = {
            "initial_parameters": list(initial_parameters),
            "lower_bounds": [1e-8, lower_c2],
            "upper_bounds": [1000.0, 5000.0],
            "ftol": 1e-12,
            "xtol": 1e-12,
            "gtol": 1e-12,
            "max_nfev": 5000,
            "seed": None,
        }
        suggestion = DmaMultiFrequencyStartingSuggestion(
            input_mode=DmaInputMode.MULTI_FREQUENCY_ISOTHERMS.value,
            source_evidence={
                "test_data_document_id": str(command.test_data.document_id),
                "test_data_revision_id": str(command.test_data.revision_id),
                "test_data_content_sha256": command.test_data.content_sha256,
                "import_profile_id": str(command.import_profile.profile_id),
                "import_profile_revision_id": str(command.import_profile.revision_id),
                "import_profile_content_sha256": command.import_profile.content_sha256,
                "source_normalized_artifact_id": str(
                    resolved.test_data_snapshot.content.normalized_artifact_id
                ),
                "source_normalized_artifact_sha256": (
                    resolved.test_data_snapshot.content.normalized_sha256
                ),
            },
            sweeps=sweeps_document,
            reference_sweep_ordinal=command.reference_sweep_ordinal,
            reference_temperature_k=reference_temperature,
            sweep_dispositions=dispositions,
            shift_law=shift_law,
            scoring=scoring,
            adjacent_optimizer=adjacent_optimizer,
            law_optimizer=law_optimizer,
            profile_id="cmp.dma_tts.multi_frequency_wlf_starting_profile",
            profile_version="1.0.0",
            material_specific=False,
            production_readiness="non_production",
            requires_confirmation=True,
            recommendation_sha256="",
        )
        digest = content_sha256(suggestion.canonical_without_digest())
        return DmaMultiFrequencyStartingSuggestion(
            input_mode=suggestion.input_mode,
            source_evidence=suggestion.source_evidence,
            sweeps=suggestion.sweeps,
            reference_sweep_ordinal=suggestion.reference_sweep_ordinal,
            reference_temperature_k=suggestion.reference_temperature_k,
            sweep_dispositions=suggestion.sweep_dispositions,
            shift_law=suggestion.shift_law,
            scoring=suggestion.scoring,
            adjacent_optimizer=suggestion.adjacent_optimizer,
            law_optimizer=suggestion.law_optimizer,
            profile_id=suggestion.profile_id,
            profile_version=suggestion.profile_version,
            material_specific=suggestion.material_specific,
            production_readiness=suggestion.production_readiness,
            requires_confirmation=suggestion.requires_confirmation,
            recommendation_sha256=digest,
        )

    async def create(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CreateDmaFrequencyMasterCurve,
    ) -> CreatedDmaFrequencyMasterCurve:
        if command.input_mode not in {item.value for item in DmaInputMode}:
            raise DmaProcessingError(
                "CMP-PROCESSING-4318",
                "input_mode is unsupported",
                "Use one of the two current DMA input modes.",
            )
        resolved = await self._resolve(
            context, decision, command.test_data, command.import_profile, command.input_mode
        )
        snapshot = resolved.test_data_snapshot
        if snapshot.current.scope.classification != command.classification.value:
            raise DmaProcessingError(
                "CMP-PROCESSING-4317",
                "requested Processing Output classification differs from Test Data",
                "Use the exact upstream classification.",
            )
        if command.input_mode == DmaInputMode.FIXED_FREQUENCY_TEMPERATURE_SWEEP.value:
            if not isinstance(
                command.shift_law, (WlfShiftLaw, ArrheniusShiftLaw, TabulatedShiftLaw)
            ):
                raise DmaProcessingError(
                    "CMP-PROCESSING-4313",
                    "fixed input requires a supplied WLF, Arrhenius, or manual shift law",
                    "Supply one current fixed-frequency shift law.",
                )
            if (
                command.scoring is not None
                or command.adjacent_optimizer is not None
                or command.law_optimizer is not None
                or command.reference_sweep_ordinal is not None
            ):
                raise DmaProcessingError(
                    "CMP-PROCESSING-4313",
                    "multi-frequency controls are forbidden for fixed input",
                    "Remove sweep, overlap, weight, and optimizer controls from a fixed request.",
                )
            recommendation_metadata: dict[str, object] | None = None
            if command.recommendation_sha256 is not None:
                suggestion = await self.recommend(
                    context,
                    decision,
                    RecommendDmaFrequencyMasterCurve(command.test_data, command.import_profile),
                )
                law = command.shift_law
                if (
                    suggestion.recommendation_sha256 != command.recommendation_sha256
                    or not isinstance(law, WlfShiftLaw)
                    or law.reference_temperature_k != suggestion.reference_temperature_k
                    or law.c1 != suggestion.c1
                    or law.c2_k != suggestion.c2_k
                ):
                    raise DmaProcessingError(
                        "CMP-PROCESSING-4317",
                        "recommendation digest or WLF values do not match the exact fixed inputs",
                        "Reload the fixed recommendation or submit explicitly edited settings.",
                    )
                recommendation_metadata = {
                    "recommendation_sha256": suggestion.recommendation_sha256,
                    "rule_id": suggestion.rule_id,
                    "rule_version": suggestion.rule_version,
                }
            fixed_dispositions = tuple(
                item for item in command.dispositions if isinstance(item, DmaRowDisposition)
            )
            if len(fixed_dispositions) != len(command.dispositions):
                raise DmaProcessingError(
                    "CMP-PROCESSING-4311",
                    "fixed input carries non-row sweep dispositions",
                    "Provide one fixed-row disposition for every fixed DMA source row.",
                )
            fixed_rows = build_frequency_master_curve(
                resolved.fixed_rows,
                fixed_dispositions,
                command.shift_law,
                confirmed=command.confirmed,
                confirmation_reason=command.confirmation_reason,
            )
            reference_row = next(row for row in fixed_rows if row.is_reference)
            options = _options(
                input_mode=command.input_mode,
                source=snapshot,
                rows=fixed_rows,
                reference={
                    "source_sweep_ordinal": None,
                    "source_ordinal": reference_row.source_ordinals[0],
                    "representative_temperature_k": reference_row.representative_temperature_k,
                },
                shift_law=_fixed_law_options(command.shift_law),
                scoring=None,
                adjacent_optimizer=None,
                law_optimizer=None,
                residual_summary=None,
                application_range=None,
                recommendation=recommendation_metadata,
            )
            master = await self._commit_output(
                context=context,
                decision=decision,
                classification=command.classification,
                label=command.label,
                source_document=ExactRevisionPin(
                    command.test_data.document_id, command.test_data.revision_id
                ),
                source_document_sha256=command.test_data.content_sha256,
                source_canonical_artifact_sha256=snapshot.content.canonical_sha256,
                governed_import_profile=ExactRevisionPin(
                    command.import_profile.profile_id, command.import_profile.revision_id
                ),
                governed_import_profile_sha256=command.import_profile.content_sha256,
                step=ProcessingStep(
                    DMA_FREQUENCY_MASTER_CURVE_METHOD_ID,
                    DMA_FREQUENCY_MASTER_CURVE_METHOD_VERSION,
                    options,
                ),
                independent_quantity="frequency.angular.reduced",
                final_point_count=len(fixed_rows),
                result_schema_ref=DMA_FREQUENCY_MASTER_CURVE_PARQUET_SCHEMA_ID,
                result_bytes=frequency_master_curve_parquet_bytes(fixed_rows),
                source_processing_output=None,
                source_processing_output_sha256=None,
                export_provenance=snapshot.content.governed_source,
                change_reason=command.change_reason,
            )
            return CreatedDmaFrequencyMasterCurve(master)
        if (
            not command.dispositions
            or command.reference_sweep_ordinal is None
            or command.scoring is None
            or command.adjacent_optimizer is None
            or not isinstance(command.shift_law, DmaShiftLawRequest)
        ):
            raise DmaProcessingError(
                "CMP-PROCESSING-4313",
                (
                    "multi-frequency request carries forbidden fixed controls or "
                    "lacks required controls"
                ),
                (
                    "Use sweep dispositions, a manual/WLF-fit/Arrhenius-fit law, "
                    "explicit scoring, adjacent, and law controls."
                ),
            )
        if command.shift_law.kind == "manual_tabulated" and command.law_optimizer is not None:
            raise DmaProcessingError(
                "CMP-PROCESSING-4313",
                "manual multi-frequency law cannot carry a law optimizer",
                "Remove law optimizer controls for a supplied manual table.",
            )
        if command.shift_law.kind in {"wlf_fit", "arrhenius_fit"} and command.law_optimizer is None:
            raise DmaProcessingError(
                "CMP-PROCESSING-4313",
                "fitted multi-frequency law requires law optimizer controls",
                "Supply the exact positive fit starts, bounds, and governed optimizer settings.",
            )
        multi_dispositions = tuple(
            item for item in command.dispositions if isinstance(item, DmaFrequencySweepDisposition)
        )
        if len(multi_dispositions) != len(command.dispositions):
            raise DmaProcessingError(
                "CMP-PROCESSING-4311",
                "multi-frequency input carries fixed-row dispositions",
                "Provide one sweep disposition for every multi-frequency DMA source sweep.",
            )
        recommendation_metadata = None
        if command.recommendation_sha256 is not None:
            multi_suggestion = await self.recommend_multi(
                context,
                decision,
                RecommendMultiDmaFrequencyMasterCurve(
                    command.test_data,
                    command.import_profile,
                    command.reference_sweep_ordinal,
                ),
            )
            expected_law = _multi_shift_law_request_document(command.shift_law)
            expected_law_optimizer = _multi_law_optimizer_document(command.law_optimizer)
            if (
                multi_suggestion.recommendation_sha256 != command.recommendation_sha256
                or command.reference_sweep_ordinal != multi_suggestion.reference_sweep_ordinal
                or tuple(_multi_disposition_document(item) for item in multi_dispositions)
                != tuple(dict(item) for item in multi_suggestion.sweep_dispositions)
                or expected_law != dict(multi_suggestion.shift_law)
                or _multi_scoring_document(command.scoring) != dict(multi_suggestion.scoring)
                or _multi_adjacent_document(command.adjacent_optimizer)
                != dict(multi_suggestion.adjacent_optimizer)
                or expected_law_optimizer != dict(multi_suggestion.law_optimizer)
            ):
                raise DmaProcessingError(
                    "CMP-PROCESSING-4317",
                    (
                        "recommendation digest or multi-frequency controls do not match "
                        "the exact source"
                    ),
                    (
                        "Reload the exact recommendation or submit explicitly edited settings "
                        "with no digest."
                    ),
                )
            recommendation_metadata = {
                "recommendation_sha256": multi_suggestion.recommendation_sha256,
                "profile_id": multi_suggestion.profile_id,
                "profile_version": multi_suggestion.profile_version,
            }
        result = build_multi_frequency_master_curve(
            resolved.sweeps,
            multi_dispositions,
            reference_sweep_ordinal=command.reference_sweep_ordinal,
            shift_law=command.shift_law,
            scoring=command.scoring,
            adjacent_optimizer=command.adjacent_optimizer,
            law_optimizer=command.law_optimizer,
            confirmed=command.confirmed,
            confirmation_reason=command.confirmation_reason,
        )
        reference_row = next(row for row in result.rows if row.is_reference)
        options = _options(
            input_mode=command.input_mode,
            source=snapshot,
            rows=result.rows,
            reference={
                "source_sweep_ordinal": reference_row.source_sweep_ordinal,
                "source_ordinal": None,
                "representative_temperature_k": reference_row.representative_temperature_k,
            },
            shift_law=result.shift_law,
            scoring=result.scoring,
            adjacent_optimizer=result.adjacent_optimizer,
            law_optimizer=result.law_optimizer,
            residual_summary=result.residual_summary,
            application_range=result.application_range,
            recommendation=recommendation_metadata,
        )
        master = await self._commit_output(
            context=context,
            decision=decision,
            classification=command.classification,
            label=command.label,
            source_document=ExactRevisionPin(
                command.test_data.document_id, command.test_data.revision_id
            ),
            source_document_sha256=command.test_data.content_sha256,
            source_canonical_artifact_sha256=snapshot.content.canonical_sha256,
            governed_import_profile=ExactRevisionPin(
                command.import_profile.profile_id, command.import_profile.revision_id
            ),
            governed_import_profile_sha256=command.import_profile.content_sha256,
            step=ProcessingStep(
                DMA_FREQUENCY_MASTER_CURVE_METHOD_ID,
                DMA_FREQUENCY_MASTER_CURVE_METHOD_VERSION,
                options,
            ),
            independent_quantity="frequency.angular.reduced",
            final_point_count=len(result.rows),
            result_schema_ref=DMA_FREQUENCY_MASTER_CURVE_PARQUET_SCHEMA_ID,
            result_bytes=frequency_master_curve_parquet_bytes(result.rows),
            source_processing_output=None,
            source_processing_output_sha256=None,
            export_provenance=snapshot.content.governed_source,
            change_reason=command.change_reason,
        )
        return CreatedDmaFrequencyMasterCurve(master)

    async def read(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        output_id: UUID,
        revision_id: UUID,
        content_sha256: str,
    ) -> ReadDmaFrequencyMasterCurve:
        if decision.permission not in {Permission.PROCESSING_READ, Permission.PROCESSING_EXECUTE}:
            raise DmaProcessingError(
                "CMP-PROCESSING-4030",
                "processing read authorization is invalid",
                "Request Processing read permission for this project.",
            )
        try:
            output = self._outputs.get_output(
                context=context, decision=decision, output_id=output_id
            )
        except ProcessingOutputNotFound:
            raise
        if (
            output.current.revision_id != revision_id
            or output.current.content_hash != content_sha256
        ):
            raise DmaProcessingError(
                "CMP-PROCESSING-4317",
                "requested output revision or digest is not the exact current immutable revision",
                "Use the exact output revision and content_sha256 returned at creation.",
            )
        content = output.content
        if (
            len(content.steps) != 1
            or content.steps[0].method_id != DMA_FREQUENCY_MASTER_CURVE_METHOD_ID
            or content.steps[0].method_version != DMA_FREQUENCY_MASTER_CURVE_METHOD_VERSION
            or content.independent_quantity != "frequency.angular.reduced"
            or content.result_schema_ref != DMA_FREQUENCY_MASTER_CURVE_PARQUET_SCHEMA_ID
            or content.result_media_type != "application/vnd.apache.parquet"
            or content.source_profile_kind != "governed_import_profile"
            or content.governed_import_profile is None
            or content.governed_import_profile_sha256 is None
            or content.result_artifact_id is None
            or content.result_sha256 is None
        ):
            raise DmaProcessingError(
                "CMP-PROCESSING-4318",
                "Processing Output is not the current DMA master-curve contract",
                "Request the exact immutable DMA master-curve output revision.",
            )
        if content.output_artifact_id is None or content.output_sha256 is None:
            raise DmaProcessingError(
                "CMP-PROCESSING-4317",
                "Processing Output metadata Artifact pin is incomplete",
                "Reload the exact immutable Processing Output.",
            )
        try:
            metadata_artifact, metadata_bytes = await self._artifacts.read_verified_bytes(
                context, decision, content.output_artifact_id, maximum_bytes=8 * 1024 * 1024
            )
            result_artifact, result_bytes = await self._artifacts.read_verified_bytes(
                context, decision, content.result_artifact_id, maximum_bytes=64 * 1024 * 1024
            )
        except (ArtifactIntegrityError, ArtifactNotFound) as error:
            raise DmaProcessingError(
                "CMP-PROCESSING-4317",
                "DMA Processing Output artifacts are unavailable or corrupt",
                "Reload the exact immutable artifacts or recover their integrity state.",
            ) from error
        except ArtifactAccessDenied as error:
            raise DmaProcessingError(
                "CMP-PROCESSING-4030",
                "DMA Processing Output artifact access is unauthorized",
                "Request Artifact read permission for this project.",
            ) from error
        except ObjectStoreError as error:
            raise DmaProcessingError(
                "CMP-PROCESSING-5030",
                "DMA Processing Output artifacts are temporarily unavailable",
                "Retry after the exact immutable artifacts are available.",
            ) from error
        if (
            metadata_artifact.artifact.id != content.output_artifact_id
            or metadata_artifact.artifact.organization_id != output.current.scope.organization_id
            or metadata_artifact.artifact.project_id != output.current.scope.project_id
            or metadata_artifact.artifact.classification.value
            != output.current.scope.classification
            or metadata_artifact.artifact.artifact_kind.value != "derived"
            or metadata_artifact.artifact.artifact_role != "processing.common-output-json"
            or metadata_artifact.artifact.sha256 != content.output_sha256
            or metadata_artifact.artifact.media_type != PROCESSING_OUTPUT_MEDIA_TYPE
            or result_artifact.artifact.id != content.result_artifact_id
            or result_artifact.artifact.organization_id != output.current.scope.organization_id
            or result_artifact.artifact.project_id != output.current.scope.project_id
            or result_artifact.artifact.classification.value != output.current.scope.classification
            or result_artifact.artifact.artifact_kind.value != "derived"
            or result_artifact.artifact.artifact_role != "processing.dma-result-parquet"
            or result_artifact.artifact.sha256 != content.result_sha256
            or result_artifact.artifact.media_type != content.result_media_type
            or result_artifact.artifact.schema_ref != content.result_schema_ref
        ):
            raise DmaProcessingError(
                "CMP-PROCESSING-4317",
                "DMA Processing Output Artifact pins or digests are inconsistent",
                "Reload the exact immutable Processing Output revision.",
            )
        try:
            metadata = json.loads(metadata_bytes)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise DmaProcessingError(
                "CMP-PROCESSING-4317",
                "DMA Processing Output metadata is invalid",
                "Reload the exact immutable Processing Output revision.",
            ) from error
        result_pin = metadata.get("result_artifact") if isinstance(metadata, Mapping) else None
        if (
            not isinstance(metadata, Mapping)
            or metadata.get("output_id") != str(output.id)
            or result_pin
            != {
                "artifact_id": str(content.result_artifact_id),
                "sha256": content.result_sha256,
                "schema_ref": content.result_schema_ref,
                "media_type": content.result_media_type,
            }
            or not isinstance(result_pin, Mapping)
        ):
            raise DmaProcessingError(
                "CMP-PROCESSING-4317",
                "DMA Processing Output metadata does not pin its result",
                "Reload the exact immutable Processing Output revision.",
            )
        validator = getattr(self._dma_provenance_writer, "validate", None)
        if not callable(validator):
            raise DmaProcessingError(
                "CMP-PROCESSING-5030",
                "DMA provenance validation is not configured",
                "Retry after the current DMA persistence composition is available.",
            )
        try:
            validator(
                context=context,
                decision=decision,
                snapshot=output,
                metadata_artifact=metadata_artifact,
                result_artifact=result_artifact,
            )
        except ProvenanceConflict as error:
            raise DmaProcessingError(
                "CMP-PROCESSING-4317",
                "DMA provenance graph is inconsistent with the exact output pins",
                (
                    "Reload the immutable DMA Processing Output or recover its "
                    "complete provenance graph."
                ),
            ) from error
        except Exception as error:
            raise DmaProcessingError(
                "CMP-PROCESSING-5030",
                "DMA provenance graph is temporarily unavailable",
                "Retry after the provenance store is available.",
            ) from error
        try:
            rows = from_parquet(result_bytes)
            validate_options_against_rows(content.steps[0].options, rows)
        except DmaProcessingError:
            raise
        except Exception as error:
            raise DmaProcessingError(
                "CMP-PROCESSING-4317",
                "DMA result cannot be reloaded with its exact current schema",
                "Reload the exact immutable result Artifact.",
            ) from error
        if len(rows) != content.final_point_count:
            raise DmaProcessingError(
                "CMP-PROCESSING-4317",
                "DMA result row count differs from Common Output metadata",
                "Reload the exact immutable Processing Output revision.",
            )
        return ReadDmaFrequencyMasterCurve(
            output,
            rows[0].input_mode,
            content.steps[0].options,
            rows,
            content.source_document,
            content.governed_import_profile,
        )

    async def _commit_output(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        classification: DataClassification,
        label: str,
        source_document: ExactRevisionPin,
        source_document_sha256: str,
        source_canonical_artifact_sha256: str,
        governed_import_profile: ExactRevisionPin,
        governed_import_profile_sha256: str,
        step: ProcessingStep,
        independent_quantity: str,
        final_point_count: int,
        result_schema_ref: str,
        result_bytes: bytes,
        source_processing_output: ExactRevisionPin | None,
        source_processing_output_sha256: str | None,
        export_provenance: GovernedTestDataSource | None,
        change_reason: str,
    ) -> ProcessingOutputSnapshot:
        output_id = self._id()
        result_sha256 = hashlib.sha256(result_bytes).hexdigest()
        result_artifact_id = uuid4()
        metadata_artifact_id = uuid4()
        revision_id = self._id()
        if revision_id == output_id:
            revision_id = uuid4()

        def metadata_document(result_id: UUID, result_digest: str) -> dict[str, object]:
            return {
                "document_type": "cmp.processing-output",
                "document_version": PROCESSING_OUTPUT_SCHEMA_VERSION_1_6,
                "output_id": str(output_id),
                "source_document": {
                    "aggregate_id": str(source_document.aggregate_id),
                    "revision_id": str(source_document.revision_id),
                    "sha256": source_document_sha256,
                    "canonical_artifact_sha256": source_canonical_artifact_sha256,
                },
                "source_profile": {
                    "kind": "governed_import_profile",
                    "aggregate_id": str(governed_import_profile.aggregate_id),
                    "revision_id": str(governed_import_profile.revision_id),
                    "sha256": governed_import_profile_sha256,
                },
                "source_processing_output": (
                    None
                    if source_processing_output is None
                    else {
                        "aggregate_id": str(source_processing_output.aggregate_id),
                        "revision_id": str(source_processing_output.revision_id),
                        "sha256": source_processing_output_sha256,
                    }
                ),
                "step": {
                    "method_id": step.method_id,
                    "method_version": step.method_version,
                    "options": step.options,
                },
                "result_artifact": {
                    "artifact_id": str(result_id),
                    "sha256": result_digest,
                    "schema_ref": result_schema_ref,
                    "media_type": "application/vnd.apache.parquet",
                },
            }

        def content(
            metadata_artifact: ArtifactRecord,
            result_artifact: ArtifactRecord,
        ) -> ProcessingOutputContent:
            return ProcessingOutputContent(
                label=label,
                source_document=source_document,
                source_document_sha256=source_document_sha256,
                source_canonical_artifact_sha256=source_canonical_artifact_sha256,
                mapping_profile=None,
                mapping_profile_sha256=None,
                steps=(step,),
                independent_quantity=independent_quantity,
                stage_count=2,
                final_point_count=final_point_count,
                output_artifact_id=metadata_artifact.artifact.id,
                output_sha256=metadata_artifact.artifact.sha256,
                source_processing_output=source_processing_output,
                source_processing_output_sha256=source_processing_output_sha256,
                export_provenance=export_provenance,
                source_profile_kind="governed_import_profile",
                governed_import_profile=governed_import_profile,
                governed_import_profile_sha256=governed_import_profile_sha256,
                result_artifact_id=result_artifact.artifact.id,
                result_sha256=result_artifact.artifact.sha256,
                result_schema_ref=result_artifact.artifact.schema_ref,
                result_media_type=result_artifact.artifact.media_type,
            )

        dma_provenance_writer = self._dma_provenance_writer
        if dma_provenance_writer is None:
            raise DmaProcessingError(
                "CMP-PROCESSING-5030",
                "DMA provenance finalization is not configured",
                "Retry after the current DMA persistence composition is available.",
            )
        atomic_writer = self._outputs.commit_in_artifact_session
        committed: dict[str, ProcessingOutputSnapshot] = {}
        metadata_value = canonical_json_bytes(metadata_document(result_artifact_id, result_sha256))
        metadata_sha256 = hashlib.sha256(metadata_value).hexdigest()
        result_command = PrepareArtifact(
            classification=classification,
            artifact_kind=ArtifactKind.DERIVED,
            artifact_role="processing.dma-result-parquet",
            schema_ref=result_schema_ref,
            media_type="application/vnd.apache.parquet",
            expected_size_bytes=len(result_bytes),
            expected_sha256=result_sha256,
            staging_object_key=ArtifactService.derived_staging_key(
                context, classification, f"dma-processing-result:{output_id}"
            ),
            idempotency_key=f"dma-processing-result:{output_id}",
            reserved_artifact_id=result_artifact_id,
        )
        metadata_command = PrepareArtifact(
            classification=classification,
            artifact_kind=ArtifactKind.DERIVED,
            artifact_role="processing.common-output-json",
            schema_ref=PROCESSING_OUTPUT_SCHEMA_ID_1_6,
            media_type=PROCESSING_OUTPUT_MEDIA_TYPE,
            expected_size_bytes=len(metadata_value),
            expected_sha256=metadata_sha256,
            staging_object_key=ArtifactService.derived_staging_key(
                context, classification, f"common-processing-output:{output_id}"
            ),
            idempotency_key=f"common-processing-output:{output_id}",
            reserved_artifact_id=metadata_artifact_id,
        )

        def persist_batch(
            session: object,
            finalized: tuple[FinalizedArtifact, ...],
        ) -> None:
            by_role = {item.record.artifact.artifact_role: item.record for item in finalized}
            result_record = by_role["processing.dma-result-parquet"]
            metadata_record = by_role["processing.common-output-json"]
            output_content = content(metadata_record, result_record)

            def specialize(
                hook_session: object,
                snapshot: ProcessingOutputSnapshot,
            ) -> None:
                dma_provenance_writer(
                    session=hook_session,
                    context=context,
                    decision=decision,
                    snapshot=snapshot,
                    metadata_artifact=metadata_record,
                    result_artifact=result_record,
                )

            committed["snapshot"] = atomic_writer(
                session=session,
                context=context,
                decision=decision,
                output_id=output_id,
                classification=classification.value,
                content=output_content,
                change_reason=change_reason,
                artifact_created_at=metadata_record.artifact.created_at,
                revision_id=revision_id,
                post_commit_hook=specialize,
            )

        try:
            batch_result = await self._artifacts.finalize_derived_batch(
                context,
                decision,
                entries=((result_command, result_bytes), (metadata_command, metadata_value)),
                commit_hook=cast(ArtifactBatchCommitHook, persist_batch),
            )
        except ArtifactAccessDenied as error:
            raise DmaProcessingError(
                "CMP-PROCESSING-4030",
                "DMA output artifact authorization is invalid",
                "Request Artifact write permission for this project.",
            ) from error
        except (
            ArtifactConflict,
            ArtifactIntegrityError,
            ArtifactNotFound,
            ArtifactStateError,
        ) as error:
            raise DmaProcessingError(
                "CMP-PROCESSING-4317",
                "DMA output Artifact finalization conflicts with the exact immutable batch",
                "Retry with the exact current artifact transaction and recover any staged orphan.",
            ) from error
        except (ObjectStoreError, ProvenanceConflict) as error:
            raise DmaProcessingError(
                "CMP-PROCESSING-5030",
                "DMA output finalization is temporarily unavailable",
                "Retry after the object, provenance, or transaction store is available.",
            ) from error
        if "snapshot" in committed:
            return committed["snapshot"]
        if batch_result and all(item.replayed for item in batch_result):
            return self._outputs.get_output(
                context=context,
                decision=decision,
                output_id=output_id,
            )
        raise DmaProcessingError(
            "CMP-PROCESSING-5030",
            "DMA output batch completed without a Common Processing Output revision",
            "Retry after the transaction coordinator is available.",
        )

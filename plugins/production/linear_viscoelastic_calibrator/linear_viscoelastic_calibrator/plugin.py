"""Isolated generalized-Maxwell shear calibrator entrypoint.

The package deliberately talks to the platform only through ``cmp_plugin_sdk``.  It reads
the exact Plan/canonical/normalized bindings staged by T-18 and writes the three declared
result artifacts.  No network, ambient filesystem, or platform service import is used.
"""

from __future__ import annotations

import hashlib
import io
import json
import math
from decimal import Decimal, InvalidOperation
from itertools import pairwise
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
from cmp_plugin_sdk import (
    Diagnostic,
    DiagnosticSeverity,
    ExtensionDescriptor,
    ExtensionOutcome,
    ExtensionStatus,
    ExtensionType,
    RunContext,
    RunnerJobSpec,
    ValidationReport,
)
from scipy.optimize import least_squares

PLUGIN_ID = "cmp.linear_viscoelastic.calibrator"
PLUGIN_VERSION = "1.0.0"
RESULT_SCHEMA = "urn:cmp:modeling:linear-viscoelastic-calibration-result:1.0.0"
RESIDUAL_SCHEMA = "urn:cmp:modeling:linear-viscoelastic-calibration-response-residuals:1.0.0"
HISTORY_SCHEMA = "urn:cmp:modeling:linear-viscoelastic-calibration-objective-history:1.0.0"
CONFIG_SCHEMA = "urn:cmp:plugin:linear-viscoelastic-calibrator:config:1.0.0"
RECOMMENDATION_POLICY = "lowest_bic_then_term_count_then_attempt_ordinal@1.0.0"
DMA_MASTER_CURVE_SCHEMA = "urn:cmp:processing:dma-frequency-master-curve-parquet:1.0.0"
DMA_MASTER_CURVE_COLUMNS = (
    "input_mode",
    "source_sweep_ordinal",
    "representative_temperature_k",
    "partition",
    "is_reference",
    "exclusion_reason",
    "holdout_evaluation_status",
    "source_ordinals",
    "measured_temperature_k",
    "source_frequency_hz",
    "angular_frequency_rad_per_s",
    "storage_modulus_pa",
    "loss_modulus_pa",
    "source_tan_delta",
    "loss_modulus_origin",
    "reduced_angular_frequency_rad_per_s",
    "raw_angular_frequency_min_rad_per_s",
    "raw_angular_frequency_max_rad_per_s",
    "shifted_angular_frequency_min_rad_per_s",
    "shifted_angular_frequency_max_rad_per_s",
    "comparison_sweep_ordinal",
    "observed_log10_a_t",
    "applied_log10_a_t",
    "shift_factor",
    "shift_residual_log10_a_t",
    "overlap_log10_reduced_angular_frequency_min",
    "overlap_log10_reduced_angular_frequency_max",
    "scoring_point_count",
    "storage_mse",
    "loss_mse",
    "storage_rmse",
    "loss_rmse",
    "weighted_mse",
    "adjacent_success",
    "adjacent_status",
    "adjacent_iterations",
    "adjacent_evaluations",
    "adjacent_objective",
)


def _list_type(value_type: pa.DataType, *, nullable: bool = False) -> pa.DataType:
    return pa.list_(pa.field("item", value_type, nullable=nullable))


DMA_MASTER_CURVE_ARROW_SCHEMA = pa.schema(
    (
        pa.field("input_mode", pa.string(), nullable=False),
        pa.field("source_sweep_ordinal", pa.int64(), nullable=True),
        pa.field("representative_temperature_k", pa.float64(), nullable=False),
        pa.field("partition", pa.string(), nullable=False),
        pa.field("is_reference", pa.bool_(), nullable=False),
        pa.field("exclusion_reason", pa.string(), nullable=True),
        pa.field("holdout_evaluation_status", pa.string(), nullable=True),
        pa.field("source_ordinals", _list_type(pa.int64()), nullable=False),
        pa.field("measured_temperature_k", _list_type(pa.float64()), nullable=False),
        pa.field("source_frequency_hz", _list_type(pa.float64()), nullable=False),
        pa.field("angular_frequency_rad_per_s", _list_type(pa.float64()), nullable=False),
        pa.field("storage_modulus_pa", _list_type(pa.float64()), nullable=False),
        pa.field("loss_modulus_pa", _list_type(pa.float64()), nullable=False),
        pa.field(
            "source_tan_delta",
            _list_type(pa.float64(), nullable=True),
            nullable=False,
        ),
        pa.field("loss_modulus_origin", _list_type(pa.string()), nullable=False),
        pa.field("reduced_angular_frequency_rad_per_s", _list_type(pa.float64()), nullable=True),
        pa.field("raw_angular_frequency_min_rad_per_s", pa.float64(), nullable=False),
        pa.field("raw_angular_frequency_max_rad_per_s", pa.float64(), nullable=False),
        pa.field("shifted_angular_frequency_min_rad_per_s", pa.float64(), nullable=True),
        pa.field("shifted_angular_frequency_max_rad_per_s", pa.float64(), nullable=True),
        pa.field("comparison_sweep_ordinal", pa.int64(), nullable=True),
        pa.field("observed_log10_a_t", pa.float64(), nullable=True),
        pa.field("applied_log10_a_t", pa.float64(), nullable=True),
        pa.field("shift_factor", pa.float64(), nullable=True),
        pa.field("shift_residual_log10_a_t", pa.float64(), nullable=True),
        pa.field("overlap_log10_reduced_angular_frequency_min", pa.float64(), nullable=True),
        pa.field("overlap_log10_reduced_angular_frequency_max", pa.float64(), nullable=True),
        pa.field("scoring_point_count", pa.int32(), nullable=True),
        pa.field("storage_mse", pa.float64(), nullable=True),
        pa.field("loss_mse", pa.float64(), nullable=True),
        pa.field("storage_rmse", pa.float64(), nullable=True),
        pa.field("loss_rmse", pa.float64(), nullable=True),
        pa.field("weighted_mse", pa.float64(), nullable=True),
        pa.field("adjacent_success", pa.bool_(), nullable=True),
        pa.field("adjacent_status", pa.int32(), nullable=True),
        pa.field("adjacent_iterations", pa.int64(), nullable=True),
        pa.field("adjacent_evaluations", pa.int64(), nullable=True),
        pa.field("adjacent_objective", pa.float64(), nullable=True),
    )
)


def _error(code: str, message: str) -> Diagnostic:
    return Diagnostic(code, DiagnosticSeverity.ERROR, message)


def _recommendation_key(item: dict[str, Any], policy: object) -> tuple[float, int, int]:
    """Apply the one serialized recommendation policy supported by this package."""

    if policy != RECOMMENDATION_POLICY:
        raise ValueError("unsupported recommendation policy")
    return (float(item["bic"]), int(item["term_count"]), int(item["attempt_ordinal"]))


def _parameter_names(term_count: int) -> tuple[str, ...]:
    return (
        "G_inf_pa",
        *(f"G_{index}_pa" for index in range(1, term_count + 1)),
        *(f"tau_{index}_s" for index in range(1, term_count + 1)),
    )


def _evaluate(
    term_count: int, parameters: np.ndarray, domain: np.ndarray, mode: str
) -> tuple[np.ndarray, np.ndarray | None]:
    g_inf = parameters[0]
    gi = parameters[1 : term_count + 1]
    taus = parameters[term_count + 1 :]
    if mode == "relaxation":
        return g_inf + np.sum(gi[:, None] * np.exp(-domain[None, :] / taus[:, None]), axis=0), None
    x = (2.0 * math.pi * domain)[None, :] * taus[:, None]
    storage = g_inf + np.sum(gi[:, None] * (x * x) / (1.0 + x * x), axis=0)
    loss = np.sum(gi[:, None] * x / (1.0 + x * x), axis=0)
    return storage, loss


def _load_plan(context: RunContext) -> dict[str, Any]:
    payload = context.read_input("calibration.plan", maximum_bytes=32 * 1024 * 1024)
    value = json.loads(payload.decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError("calibration Plan input must be a JSON object")
    return value


def _parquet_bytes(columns: dict[str, list[Any]]) -> bytes:
    """Create deterministic compact Parquet evidence for the generic Result Manifest."""

    table = pa.table(columns)
    stream = io.BytesIO()
    pq.write_table(table, stream, compression=None, version="2.6", write_statistics=False)
    return stream.getvalue()


def _float64_column(table: pa.Table, names: tuple[str, ...]) -> list[float]:
    """Read one exact float64 normalized channel, accepting governed aliases only."""

    name = next((candidate for candidate in names if candidate in table.column_names), None)
    if name is None:
        raise ValueError(f"normalized Parquet is missing one of {names!r}")
    column = table.column(name)
    if not pa.types.is_float64(column.type):
        raise ValueError(f"normalized Parquet column {name!r} must be float64")
    values = [float(item) for item in column.to_pylist()]
    if any(not math.isfinite(item) for item in values):
        raise ValueError(f"normalized Parquet column {name!r} contains a non-finite value")
    return values


def _normalized_observations(
    normalized: bytes,
    canonical: dict[str, Any],
    plan: dict[str, Any],
) -> tuple[str, list[dict[str, Any]]]:
    """Decode and cross-check normalized float64 arrays before numerical evaluation.

    Canonical Test Data supplies immutable quantity/unit rows, while the Plan supplies the
    engineer's explicit calibration/holdout/excluded decision for every source ordinal.
    Numeric vectors used by the optimizer are always loaded from normalized Parquet and
    cross-checked against the canonical JSON arrays by the server-resolved channel keys.
    """

    try:
        table = pq.read_table(pa.BufferReader(normalized))
    except Exception as error:
        raise ValueError("test-data.normalized is not a valid Parquet Artifact") from error
    semantics = plan.get("input_semantics")
    if not isinstance(semantics, dict):
        raise ValueError("Plan is missing server-resolved input_semantics")
    mode = semantics.get("mode")
    if mode not in {"relaxation", "dma"} or semantics.get("deformation_mode") != "shear":
        raise ValueError("Plan input mode or deformation mode is unsupported")
    if mode == "relaxation" and "dma_domain_policy" in semantics:
        raise ValueError("relaxation Plan must omit dma_domain_policy")
    if mode == "dma" and semantics.get("dma_domain_policy") != "strict_unique":
        raise ValueError("direct DMA Plan requires the server-derived strict_unique policy")
    channel_contracts = semantics.get("channels")
    dispositions = semantics.get("point_dispositions")
    canonical_channels = canonical.get("channels")
    if (
        not isinstance(channel_contracts, list)
        or not isinstance(dispositions, list)
        or not isinstance(canonical_channels, list)
    ):
        raise ValueError("Plan or canonical Test Data channel arrays are missing")
    by_key: dict[str, dict[str, Any]] = {}
    for value in canonical_channels:
        if not isinstance(value, dict) or not isinstance(value.get("key"), str):
            raise ValueError("canonical Test Data channel entry is invalid")
        key = value["key"]
        if key in by_key:
            raise ValueError("canonical Test Data channel keys are duplicated")
        by_key[key] = value
    active: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for contract in channel_contracts:
        if not isinstance(contract, dict) or not isinstance(contract.get("key"), str):
            raise ValueError("Plan input channel contract is invalid")
        source = by_key.get(contract["key"])
        if source is None:
            raise ValueError("Plan input channel key is absent from canonical Test Data")
        normalization = source.get("normalization")
        if not isinstance(normalization, dict):
            raise ValueError("canonical Test Data channel normalization is invalid")
        actual = (
            source.get("quantity_semantics"),
            source.get("axis_role"),
            source.get("original_unit_string"),
            source.get("normalized_unit"),
        )
        expected = (
            contract.get("quantity_semantics"),
            contract.get("axis_role"),
            contract.get("original_unit_string"),
            contract.get("normalized_unit"),
        )
        if actual != expected:
            raise ValueError("Plan input channel semantics differ from canonical Test Data")
        values = source.get("normalized_values")
        if not isinstance(values, list) or any(item is None for item in values):
            raise ValueError("canonical active channel normalized values are incomplete")
        active.append((contract, source))
    if not active:
        raise ValueError("Plan does not declare active governed channels")
    row_count = len(active[0][1]["normalized_values"])
    if (
        table.num_rows != row_count
        or len(dispositions) != row_count
        or any(len(source["normalized_values"]) != row_count for _, source in active)
    ):
        raise ValueError("Plan, Parquet, and canonical Test Data row counts differ")
    expected_semantics = (
        (
            ("time.elapsed", "independent", "s"),
            ("mechanics.modulus.shear.relaxation", "dependent", "Pa"),
        )
        if mode == "relaxation"
        else (
            ("physics.temperature", "independent", "K"),
            ("frequency.cyclic", "independent", "Hz"),
            ("mechanics.modulus.storage", "dependent", "Pa"),
            ("mechanics.modulus.loss", "dependent", "Pa"),
        )
    )
    actual_semantics = tuple(
        (
            contract.get("quantity_semantics"),
            contract.get("axis_role"),
            contract.get("normalized_unit"),
        )
        for contract, _ in active
    )
    if actual_semantics != expected_semantics:
        raise ValueError("Plan active channel quantity, role, or normalized unit is unsupported")
    values_by_semantics: dict[str, list[float]] = {}
    for contract, source in active:
        key = str(contract["key"])
        values = _float64_column(table, (key,))
        canonical_values = source["normalized_values"]
        if any(float(value) != values[index] for index, value in enumerate(canonical_values)):
            raise ValueError("normalized Parquet value differs from canonical Test Data")
        values_by_semantics[str(contract["quantity_semantics"])] = values
    if mode == "relaxation":
        columns = {
            "time_s": values_by_semantics["time.elapsed"],
            "modulus_pa": values_by_semantics["mechanics.modulus.shear.relaxation"],
        }
    else:
        columns = {
            "temperature_k": values_by_semantics["physics.temperature"],
            "frequency_hz": values_by_semantics["frequency.cyclic"],
            "storage_modulus_pa": values_by_semantics["mechanics.modulus.storage"],
            "loss_modulus_pa": values_by_semantics["mechanics.modulus.loss"],
        }
    metadata = table.schema.metadata or {}
    metadata_keys = tuple(metadata)
    if any(b"quantity_semantics" in key for key in metadata_keys):
        semantic_values = tuple(
            metadata[key] for key in metadata_keys if key.endswith(b"quantity_semantics")
        )
        required_semantics = tuple(
            str(contract["quantity_semantics"]).encode() for contract, _ in active
        )
        if not all(expected in semantic_values for expected in required_semantics):
            raise ValueError("normalized Parquet channel semantics do not match governed mode")
    result: list[dict[str, Any]] = []
    for index, disposition in enumerate(dispositions):
        if (
            not isinstance(disposition, dict)
            or disposition.get("ordinal") != index
            or disposition.get("partition") not in {"CALIBRATION", "HOLDOUT", "EXCLUDED"}
        ):
            raise ValueError("Plan point dispositions must cover every ordinal exactly once")
        row = {
            "ordinal": index,
            "partition": disposition["partition"],
            "exclusion_reason": disposition.get("exclusion_reason"),
        }
        for name, values in columns.items():
            row[name] = values[index]
        result.append(row)
    if mode == "dma":
        selected = float(semantics.get("selected_temperature_k"))
        if not math.isfinite(selected) or selected <= 0:
            raise ValueError("Plan selected DMA temperature is invalid")
        if any(
            row["temperature_k"] != selected and row["partition"] != "EXCLUDED" for row in result
        ):
            raise ValueError("DMA rows outside the selected temperature were not excluded")
    return mode, result


_DMA_WARNINGS = [
    "DMA_TTS_LVR_EVIDENCE_MISSING",
    "DMA_TTS_TEMPERATURE_EQUILIBRIUM_EVIDENCE_MISSING",
    "DMA_TTS_PRECONDITIONING_EVIDENCE_MISSING",
]
_DMA_ASSESSMENT = {
    "adequacy": "not_assessed",
    "uncertainty": "not_provided",
    "identifiability": "not_assessed",
    "production_readiness": "non_production",
}
_DMA_EVIDENCE_FIELDS = (
    "comparison_sweep_ordinal",
    "observed_log10_a_t",
    "shift_residual_log10_a_t",
    "overlap_log10_reduced_angular_frequency_min",
    "overlap_log10_reduced_angular_frequency_max",
    "scoring_point_count",
    "storage_mse",
    "loss_mse",
    "storage_rmse",
    "loss_rmse",
    "weighted_mse",
    "adjacent_success",
    "adjacent_status",
    "adjacent_iterations",
    "adjacent_evaluations",
    "adjacent_objective",
)


def _dma_number(value: object, name: str, *, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"DMA {name} is not numeric")
    number = float(value)
    if not math.isfinite(number) or (positive and number <= 0):
        raise ValueError(f"DMA {name} is not finite and positive")
    return number


def _dma_integer(value: object, name: str, *, minimum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"DMA {name} is not an integer")
    if minimum is not None and value < minimum:
        raise ValueError(f"DMA {name} is below its governed minimum")
    return value


def _dma_list(source: dict[str, Any], name: str) -> list[Any]:
    value = source.get(name)
    if not isinstance(value, list) or not value:
        raise ValueError(f"DMA result {name} is not a nonempty list")
    return value


def _dma_exact_keys(value: object, keys: set[str], name: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        raise ValueError(f"DMA {name} does not have the exact current keys")
    return value


def _dma_uuid(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"DMA {name} is not a canonical UUID")
    try:
        parsed = UUID(value)
    except ValueError as error:
        raise ValueError(f"DMA {name} is not a canonical UUID") from error
    if str(parsed) != value:
        raise ValueError(f"DMA {name} is not a canonical UUID")
    return value


def _dma_decimal_temperature(value: object, name: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as error:
        raise ValueError(f"DMA {name} is not a normalized numeric temperature") from error
    if not result.is_finite() or result <= 0:
        raise ValueError(f"DMA {name} is not finite and positive")
    return result


def _dma_validate_temperature(measured: list[Any], representative: float, mode: str) -> None:
    if mode == "fixed_frequency_temperature_sweep":
        if representative != _dma_number(measured[0], "measured_temperature_k", positive=True):
            raise ValueError("fixed DMA representative temperature differs from its point")
        return
    values = [_dma_decimal_temperature(item, "measured_temperature_k") for item in measured]
    counts: dict[Decimal, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    maximum = max(counts.values())
    expected = min(value for value, count in counts.items() if count == maximum)
    requested = _dma_decimal_temperature(representative, "representative_temperature_k")
    if requested != expected:
        raise ValueError("DMA representative temperature is not the normalized modal value")
    if any(abs(value - expected) > Decimal("0.05") for value in values):
        raise ValueError("DMA measured temperature exceeds the inclusive 0.05 K tolerance")


def _dma_validate_loss_evidence(
    mode: str,
    storage: list[float],
    loss: list[float],
    tan_delta: list[Any],
    origins: list[Any],
) -> None:
    if len(tan_delta) != len(loss) or len(origins) != len(loss):
        raise ValueError("DMA loss evidence arrays have unequal lengths")
    for storage_value, loss_value, tan_value, origin in zip(
        storage, loss, tan_delta, origins, strict=True
    ):
        if origin not in {"measured", "derived_from_tan_delta"}:
            raise ValueError("DMA loss-modulus origin is unsupported")
        if origin == "measured":
            if tan_value is not None:
                raise ValueError("measured DMA loss rows must not persist tan delta")
        else:
            tan_number = _dma_number(tan_value, "source_tan_delta")
            if not math.isclose(
                loss_value,
                storage_value * tan_number,
                rel_tol=1e-12,
                abs_tol=1e-12,
            ):
                raise ValueError("derived DMA loss evidence does not match tan delta")
    if mode == "multi_frequency_isotherms" and any(
        origin != "measured" or tan_value is not None
        for origin, tan_value in zip(origins, tan_delta, strict=True)
    ):
        raise ValueError("multi-frequency DMA loss evidence is not measured-only")


def _dma_validate_row(
    source: object,
    mode: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if not isinstance(source, dict) or source.get("input_mode") != mode:
        raise ValueError("DMA result row input_mode differs from persisted options")
    partition = source.get("partition")
    if partition not in {"CALIBRATION", "HOLDOUT", "EXCLUDED"}:
        raise ValueError("DMA result row partition is invalid")
    representative = _dma_number(
        source.get("representative_temperature_k"),
        "representative_temperature_k",
        positive=True,
    )
    sweep_ordinal = source.get("source_sweep_ordinal")
    if mode == "multi_frequency_isotherms":
        _dma_integer(sweep_ordinal, "source_sweep_ordinal", minimum=1)
        if sweep_ordinal > 9_223_372_036_854_775_807:
            raise ValueError("DMA source_sweep_ordinal exceeds int64")
    elif sweep_ordinal is not None:
        raise ValueError("fixed DMA result carries a source sweep identity")
    source_ordinals = _dma_list(source, "source_ordinals")
    measured_temperature = _dma_list(source, "measured_temperature_k")
    source_frequency = _dma_list(source, "source_frequency_hz")
    angular_frequency = _dma_list(source, "angular_frequency_rad_per_s")
    storage_values = _dma_list(source, "storage_modulus_pa")
    loss_values = _dma_list(source, "loss_modulus_pa")
    tan_delta = _dma_list(source, "source_tan_delta")
    origins = _dma_list(source, "loss_modulus_origin")
    raw_lists = (
        source_ordinals,
        measured_temperature,
        source_frequency,
        angular_frequency,
        storage_values,
        loss_values,
        tan_delta,
        origins,
    )
    if len({len(value) for value in raw_lists}) != 1:
        raise ValueError("DMA result raw lists have unequal lengths")
    if mode == "fixed_frequency_temperature_sweep" and len(source_ordinals) != 1:
        raise ValueError("fixed DMA result rows must contain one raw point")
    ordinals = tuple(_dma_integer(value, "source_ordinal", minimum=0) for value in source_ordinals)
    if any(value > 9_223_372_036_854_775_807 for value in ordinals) or ordinals != tuple(
        sorted(ordinals)
    ):
        raise ValueError("DMA result source ordinals are not in source order")
    for value in measured_temperature:
        _dma_number(value, "measured_temperature_k", positive=True)
    frequencies = [
        _dma_number(value, "source_frequency_hz", positive=True) for value in source_frequency
    ]
    angular = [
        _dma_number(value, "angular_frequency_rad_per_s", positive=True)
        for value in angular_frequency
    ]
    storage = [_dma_number(value, "storage_modulus_pa", positive=True) for value in storage_values]
    loss = [_dma_number(value, "loss_modulus_pa") for value in loss_values]
    _dma_validate_temperature(measured_temperature, representative, mode)
    _dma_validate_loss_evidence(mode, storage, loss, tan_delta, origins)
    if mode == "multi_frequency_isotherms" and any(value <= 0 for value in loss):
        raise ValueError("multi-frequency DMA loss modulus must be positive")
    if any(
        not math.isclose(omega, 2.0 * math.pi * frequency, rel_tol=1e-12, abs_tol=1e-12)
        for omega, frequency in zip(angular, frequencies, strict=True)
    ):
        raise ValueError("DMA result angular frequency is not 2*pi times source frequency")
    if mode == "multi_frequency_isotherms" and any(
        right <= left for left, right in pairwise(frequencies)
    ):
        raise ValueError("multi-frequency source frequencies are not strictly increasing")
    raw_min = _dma_number(
        source.get("raw_angular_frequency_min_rad_per_s"),
        "raw_angular_frequency_min_rad_per_s",
        positive=True,
    )
    raw_max = _dma_number(
        source.get("raw_angular_frequency_max_rad_per_s"),
        "raw_angular_frequency_max_rad_per_s",
        positive=True,
    )
    if raw_min != min(angular) or raw_max != max(angular) or raw_max < raw_min:
        raise ValueError("DMA raw frequency bounds are inconsistent")
    is_reference = source.get("is_reference")
    if not isinstance(is_reference, bool):
        raise ValueError("DMA result reference flag is invalid")
    reduced = source.get("reduced_angular_frequency_rad_per_s")
    if partition == "EXCLUDED":
        if (
            is_reference
            or not isinstance(source.get("exclusion_reason"), str)
            or not source["exclusion_reason"].strip()
            or reduced is not None
            or source.get("holdout_evaluation_status") is not None
            or any(source.get(name) is not None for name in _DMA_EVIDENCE_FIELDS)
        ):
            raise ValueError("excluded DMA result row contains derived evidence")
        return source, []
    if source.get("exclusion_reason") is not None:
        raise ValueError("included DMA result row carries an exclusion reason")
    if not isinstance(reduced, list) or len(reduced) != len(ordinals):
        raise ValueError("included DMA result reduced-frequency list is invalid")
    reduced_values = [
        _dma_number(value, "reduced_angular_frequency_rad_per_s", positive=True)
        for value in reduced
    ]
    applied = _dma_number(source.get("applied_log10_a_t"), "applied_log10_a_t")
    factor = _dma_number(source.get("shift_factor"), "shift_factor", positive=True)
    if not math.isclose(factor, 10.0**applied, rel_tol=1e-12, abs_tol=1e-12) or any(
        not math.isclose(value, omega * factor, rel_tol=1e-12, abs_tol=1e-12)
        for value, omega in zip(reduced_values, angular, strict=True)
    ):
        raise ValueError("DMA result reduced frequencies do not match horizontal shifting")
    shifted_min = _dma_number(
        source.get("shifted_angular_frequency_min_rad_per_s"),
        "shifted_angular_frequency_min_rad_per_s",
        positive=True,
    )
    shifted_max = _dma_number(
        source.get("shifted_angular_frequency_max_rad_per_s"),
        "shifted_angular_frequency_max_rad_per_s",
        positive=True,
    )
    if shifted_min != min(reduced_values) or shifted_max != max(reduced_values):
        raise ValueError("DMA shifted-frequency bounds are inconsistent")
    if is_reference:
        if (
            partition != "CALIBRATION"
            or source.get("observed_log10_a_t") != 0.0
            or applied != 0.0
            or factor != 1.0
            or source.get("shift_residual_log10_a_t") != 0.0
            or source.get("holdout_evaluation_status") is not None
            or any(
                source.get(name) is not None
                for name in _DMA_EVIDENCE_FIELDS
                if name not in {"observed_log10_a_t", "shift_residual_log10_a_t"}
            )
        ):
            raise ValueError("DMA result reference row is inconsistent")
    elif mode == "fixed_frequency_temperature_sweep":
        expected_status = "not_applicable_no_curve_overlap" if partition == "HOLDOUT" else None
        if source.get("holdout_evaluation_status") != expected_status or any(
            source.get(name) is not None for name in _DMA_EVIDENCE_FIELDS
        ):
            raise ValueError("fixed DMA result contains multi-frequency evidence")
    elif partition == "CALIBRATION":
        if source.get("holdout_evaluation_status") is not None or any(
            source.get(name) is None for name in _DMA_EVIDENCE_FIELDS
        ):
            raise ValueError("multi-frequency calibration evidence is incomplete")
    elif partition == "HOLDOUT":
        holdout_required = (
            "holdout_evaluation_status",
            "comparison_sweep_ordinal",
            "overlap_log10_reduced_angular_frequency_min",
            "overlap_log10_reduced_angular_frequency_max",
            "scoring_point_count",
            "storage_mse",
            "loss_mse",
            "storage_rmse",
            "loss_rmse",
            "weighted_mse",
        )
        calibration_only = (
            "observed_log10_a_t",
            "shift_residual_log10_a_t",
            "adjacent_success",
            "adjacent_status",
            "adjacent_iterations",
            "adjacent_evaluations",
            "adjacent_objective",
        )
        if (
            source.get("holdout_evaluation_status") != "evaluated"
            or any(source.get(name) is None for name in holdout_required)
            or any(source.get(name) is not None for name in calibration_only)
        ):
            raise ValueError("multi-frequency holdout evidence is incomplete")
    else:
        raise ValueError("DMA result partition is invalid")
    for name in _DMA_EVIDENCE_FIELDS:
        value = source.get(name)
        if (
            name
            in {
                "comparison_sweep_ordinal",
                "scoring_point_count",
                "adjacent_status",
                "adjacent_iterations",
                "adjacent_evaluations",
            }
            and value is not None
        ):
            _dma_integer(value, name)
        elif value is not None and name != "adjacent_success":
            _dma_number(value, name)
    if source.get("adjacent_success") is not None and not isinstance(
        source.get("adjacent_success"), bool
    ):
        raise ValueError("DMA adjacent success evidence is not boolean")
    if (
        source.get("scoring_point_count") is not None
        and not 2 <= source["scoring_point_count"] <= 10_001
    ):
        raise ValueError("DMA scoring point count is outside the governed range")
    for mse_name, rmse_name in (
        ("storage_mse", "storage_rmse"),
        ("loss_mse", "loss_rmse"),
    ):
        mse = source.get(mse_name)
        rmse = source.get(rmse_name)
        if mse is not None and rmse is not None:
            if mse < 0 or not math.isclose(rmse, math.sqrt(mse), rel_tol=1e-12, abs_tol=1e-12):
                raise ValueError(f"DMA {rmse_name} does not match {mse_name}")
    overlap_min = source.get("overlap_log10_reduced_angular_frequency_min")
    overlap_max = source.get("overlap_log10_reduced_angular_frequency_max")
    if overlap_min is not None and overlap_max is not None and overlap_max <= overlap_min:
        raise ValueError("DMA scoring overlap is not a positive-width interval")
    observations = [
        {
            "ordinal": index,
            "partition": partition,
            "exclusion_reason": None,
            "frequency_hz": reduced_value / (2.0 * math.pi),
            "storage_modulus_pa": storage_value,
            "loss_modulus_pa": loss_value,
            "source_sweep_ordinal": sweep_ordinal,
            "source_ordinal": source_ordinal,
            "representative_temperature_k": representative,
        }
        for index, (source_ordinal, storage_value, loss_value, reduced_value) in enumerate(
            zip(ordinals, storage, loss, reduced_values, strict=True)
        )
    ]
    return source, observations


def _dma_validate_options(
    options: object,
    mode: str,
    rows: list[dict[str, Any]],
) -> None:
    required = {
        "input_mode",
        "source_normalized_artifact_id",
        "source_normalized_artifact_sha256",
        "result_row_count",
        "frequency_conversion",
        "shift_direction",
        "log_base",
        "reference",
        "shift_law",
        "scoring",
        "adjacent_optimizer",
        "law_optimizer",
        "residual_summary",
        "application_range",
        "recommendation",
        "assessment",
        "warnings",
    }
    if not isinstance(options, dict) or set(options) != required:
        raise ValueError("DMA Processing policy does not have the exact current keys")
    if options["input_mode"] != mode:
        raise ValueError("DMA Processing policy and result mode differ")
    _dma_uuid(options["source_normalized_artifact_id"], "source_normalized_artifact_id")
    source_digest = options["source_normalized_artifact_sha256"]
    if (
        not isinstance(source_digest, str)
        or len(source_digest) != 64
        or any(character not in "0123456789abcdef" for character in source_digest)
    ):
        raise ValueError("DMA source normalized Artifact digest is invalid")
    if _dma_integer(options["result_row_count"], "result_row_count", minimum=1) != len(rows):
        raise ValueError("DMA Processing policy row count differs from the result")
    if (
        options["frequency_conversion"] != "omega_rad_per_s=2*pi*frequency_hz"
        or options["shift_direction"] != "omega_reduced=omega*10**log10_a_t"
        or options["log_base"] != 10
        or options["assessment"] != _DMA_ASSESSMENT
        or options["warnings"] != _DMA_WARNINGS
    ):
        raise ValueError("DMA Processing policy convention or assessment is unsupported")
    recommendation = options["recommendation"]
    if recommendation is not None:
        recommendation_keys = (
            {"recommendation_sha256", "rule_id", "rule_version"}
            if mode == "fixed_frequency_temperature_sweep"
            else {"recommendation_sha256", "profile_id", "profile_version"}
        )
        recommendation = _dma_exact_keys(
            recommendation,
            recommendation_keys,
            "recommendation evidence",
        )
        digest = recommendation["recommendation_sha256"]
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
        ):
            raise ValueError("DMA recommendation digest is invalid")
        if any(
            not isinstance(recommendation[key], str) or not recommendation[key]
            for key in recommendation_keys - {"recommendation_sha256"}
        ):
            raise ValueError("DMA recommendation identity is invalid")
    reference = _dma_exact_keys(
        options["reference"],
        {"source_sweep_ordinal", "source_ordinal", "representative_temperature_k"},
        "reference evidence",
    )
    reference_temperature = _dma_number(
        reference["representative_temperature_k"],
        "reference temperature",
        positive=True,
    )
    if mode == "multi_frequency_isotherms":
        _dma_integer(reference["source_sweep_ordinal"], "reference sweep", minimum=1)
        if reference["source_ordinal"] is not None:
            raise ValueError("multi-frequency reference must omit source_ordinal")
    else:
        _dma_integer(reference["source_ordinal"], "reference source ordinal", minimum=0)
        if reference["source_sweep_ordinal"] is not None:
            raise ValueError("fixed reference must omit source_sweep_ordinal")
    reference_row = next(row for row in rows if row.get("is_reference") is True)
    if reference_row.get("representative_temperature_k") != reference_temperature:
        raise ValueError("DMA reference evidence differs from the reference result row")
    if mode == "multi_frequency_isotherms":
        if reference["source_sweep_ordinal"] != reference_row.get("source_sweep_ordinal"):
            raise ValueError("DMA reference sweep evidence differs from the result")
    elif reference["source_ordinal"] != reference_row["source_ordinals"][0]:
        raise ValueError("DMA reference source evidence differs from the result")
    if not isinstance(options["shift_law"], dict):
        raise ValueError("DMA shift-law evidence is not an object")
    shift_law = options["shift_law"]
    if shift_law.get("reference_temperature_k") != reference_temperature:
        raise ValueError("DMA shift-law reference differs from the result reference")
    if mode == "fixed_frequency_temperature_sweep":
        if any(
            options[name] is not None
            for name in (
                "scoring",
                "adjacent_optimizer",
                "law_optimizer",
                "residual_summary",
                "application_range",
            )
        ):
            raise ValueError("fixed DMA result contains multi-frequency policy evidence")
        if shift_law.get("parameter_source") != "supplied" or shift_law.get("kind") not in {
            "manual_tabulated",
            "wlf",
            "arrhenius",
        }:
            raise ValueError("fixed DMA shift law is not a supplied current-contract law")
        kind = shift_law["kind"]
        if kind == "manual_tabulated":
            _dma_exact_keys(
                shift_law,
                {"kind", "reference_temperature_k", "parameter_source", "manual_table"},
                "fixed manual shift law",
            )
            table = shift_law["manual_table"]
            if (
                not isinstance(table, list)
                or not table
                or any(
                    not isinstance(item, dict) or set(item) != {"temperature_k", "log10_a_t"}
                    for item in table
                )
            ):
                raise ValueError("fixed manual shift table is not exact")
            pairs = [
                (
                    _dma_number(item["temperature_k"], "manual temperature", positive=True),
                    _dma_number(item["log10_a_t"], "manual shift"),
                )
                for item in table
            ]
            included_temperatures = {
                row["representative_temperature_k"]
                for row in rows
                if row["partition"] != "EXCLUDED"
            }
            if (
                len({temperature for temperature, _ in pairs}) != len(pairs)
                or {temperature for temperature, _ in pairs} != included_temperatures
            ):
                raise ValueError("fixed manual shift table does not cover included rows")
            if dict(pairs).get(reference_temperature) != 0.0:
                raise ValueError("fixed manual reference shift is not exact zero")
        elif kind == "wlf":
            _dma_exact_keys(
                shift_law,
                {"kind", "reference_temperature_k", "parameter_source", "c1", "c2_k"},
                "fixed WLF shift law",
            )
            if (
                _dma_number(shift_law["c1"], "WLF c1", positive=True) <= 0
                or _dma_number(shift_law["c2_k"], "WLF c2_k", positive=True) <= 0
            ):
                raise ValueError("fixed WLF parameters are invalid")
        else:
            _dma_exact_keys(
                shift_law,
                {
                    "kind",
                    "reference_temperature_k",
                    "parameter_source",
                    "activation_energy_j_per_mol",
                    "gas_constant_j_per_mol_k",
                },
                "fixed Arrhenius shift law",
            )
            if (
                _dma_number(
                    shift_law["activation_energy_j_per_mol"],
                    "Arrhenius activation energy",
                    positive=True,
                )
                <= 0
                or _dma_number(shift_law["gas_constant_j_per_mol_k"], "Arrhenius gas constant")
                != 8.31446261815324
            ):
                raise ValueError("fixed Arrhenius parameters are not governed")
        return
    scoring = _dma_exact_keys(
        options["scoring"],
        {
            "scorer_id",
            "minimum_overlap_decades",
            "scoring_point_count",
            "storage_weight",
            "loss_weight",
            "grid_policy",
            "interpolation",
            "persisted_scoring_points",
        },
        "scoring evidence",
    )
    if (
        scoring["scorer_id"] != "cmp.dma_tts.common_log_frequency_grid_log_modulus_mse@1.0.0"
        or scoring["grid_policy"] != "equally_spaced_log10_frequency_inside_measured_overlap"
        or scoring["interpolation"] != "piecewise_linear_log10_modulus"
        or scoring["persisted_scoring_points"] is not False
        or _dma_number(scoring["minimum_overlap_decades"], "minimum overlap", positive=True) <= 0
        or not 2 <= _dma_integer(scoring["scoring_point_count"], "scoring point count") <= 10_001
        or _dma_number(scoring["storage_weight"], "storage weight") < 0
        or _dma_number(scoring["loss_weight"], "loss weight") < 0
        or _dma_number(scoring["storage_weight"], "storage weight")
        + _dma_number(scoring["loss_weight"], "loss weight")
        != 1.0
    ):
        raise ValueError("multi-frequency scorer evidence is not exact")
    adjacent = _dma_exact_keys(
        options["adjacent_optimizer"],
        {
            "optimizer_id",
            "scipy_version",
            "method",
            "method_variant",
            "singleton_policy",
            "relative_shift_lower_bound_log10",
            "relative_shift_upper_bound_log10",
            "xatol",
            "maxiter",
            "seed",
            "evidence",
        },
        "adjacent optimizer evidence",
    )
    if (
        adjacent["optimizer_id"] != "cmp.dma_tts.adjacent_overlap_log_mse.scipy_bounded@1.0.0"
        or adjacent["method"] != "minimize_scalar"
        or adjacent["method_variant"] != "bounded_or_direct_singleton"
        or adjacent["singleton_policy"] != "evaluate_once_without_optimizer"
        or adjacent["seed"] is not None
        or adjacent["xatol"] != 1e-10
        or adjacent["maxiter"] != 1000
        or _dma_number(adjacent["relative_shift_lower_bound_log10"], "adjacent lower bound")
        > _dma_number(adjacent["relative_shift_upper_bound_log10"], "adjacent upper bound")
    ):
        raise ValueError("multi-frequency adjacent optimizer evidence is not exact")
    comparison_rows = [
        row for row in rows if row["partition"] == "CALIBRATION" and not row["is_reference"]
    ]
    adjacent_evidence = adjacent["evidence"]
    if not isinstance(adjacent_evidence, list) or len(adjacent_evidence) != len(comparison_rows):
        raise ValueError("multi-frequency adjacent evidence is incomplete")
    kind = shift_law.get("kind")
    if kind not in {"manual_tabulated", "wlf_fit", "arrhenius_fit"}:
        raise ValueError("multi-frequency shift-law kind is invalid")
    if kind == "manual_tabulated":
        _dma_exact_keys(
            shift_law,
            {
                "kind",
                "reference_temperature_k",
                "parameter_source",
                "manual_table",
                "per_temperature",
                "adjacent_observed",
            },
            "manual multi-frequency shift law",
        )
        if shift_law["parameter_source"] != "supplied" or options["law_optimizer"] is not None:
            raise ValueError("manual multi-frequency shift law has invalid fit evidence")
        table = shift_law["manual_table"]
        if (
            not isinstance(table, list)
            or not table
            or any(
                not isinstance(item, dict) or set(item) != {"temperature_k", "log10_a_t"}
                for item in table
            )
        ):
            raise ValueError("manual multi-frequency shift table is incomplete")
        pairs = [
            (
                _dma_number(item["temperature_k"], "manual temperature", positive=True),
                _dma_number(item["log10_a_t"], "manual shift"),
            )
            for item in table
        ]
        included_temperatures = {
            row["representative_temperature_k"] for row in rows if row["partition"] != "EXCLUDED"
        }
        if (
            len({temperature for temperature, _ in pairs}) != len(pairs)
            or {temperature for temperature, _ in pairs} != included_temperatures
            or dict(pairs).get(reference_temperature) != 0.0
        ):
            raise ValueError("manual multi-frequency shift table coverage is invalid")
    else:
        fitted_key = "c1" if kind == "wlf_fit" else "activation_energy_j_per_mol"
        second_key = "c2_k" if kind == "wlf_fit" else "gas_constant_j_per_mol_k"
        _dma_exact_keys(
            shift_law,
            {
                "kind",
                "reference_temperature_k",
                "parameter_source",
                "fitted_parameters",
                "initial_parameters",
                "lower_bounds",
                "upper_bounds",
                fitted_key,
                second_key,
                "per_temperature",
                "adjacent_observed",
            },
            "fitted multi-frequency shift law",
        )
        if shift_law["parameter_source"] != "fitted":
            raise ValueError("fitted multi-frequency shift law is not marked fitted")
        vectors = []
        for name in ("fitted_parameters", "initial_parameters", "lower_bounds", "upper_bounds"):
            value = shift_law[name]
            if not isinstance(value, list) or not value:
                raise ValueError("fitted multi-frequency parameter vectors are invalid")
            vectors.append([_dma_number(item, name) for item in value])
        expected_count = 2 if kind == "wlf_fit" else 1
        if any(len(value) != expected_count for value in vectors) or any(
            lower >= initial or initial >= upper
            for initial, lower, upper in zip(vectors[1], vectors[2], vectors[3], strict=True)
        ):
            raise ValueError("fitted multi-frequency parameter vectors are invalid")
        fitted = vectors[0]
        if kind == "wlf_fit":
            if not math.isclose(
                _dma_number(shift_law["c1"], "WLF c1"), fitted[0], rel_tol=1e-12, abs_tol=1e-12
            ) or not math.isclose(
                _dma_number(shift_law["c2_k"], "WLF c2_k", positive=True),
                fitted[1],
                rel_tol=1e-12,
                abs_tol=1e-12,
            ):
                raise ValueError("fitted WLF parameters differ from the vector")
        elif (
            _dma_number(
                shift_law["activation_energy_j_per_mol"],
                "Arrhenius activation energy",
                positive=True,
            )
            <= 0
            or _dma_number(shift_law["gas_constant_j_per_mol_k"], "Arrhenius gas constant")
            != 8.31446261815324
            or not math.isclose(
                float(shift_law["activation_energy_j_per_mol"]),
                fitted[0],
                rel_tol=1e-12,
                abs_tol=1e-12,
            )
        ):
            raise ValueError("fitted Arrhenius parameters are not governed")
        law_optimizer = _dma_exact_keys(
            options["law_optimizer"],
            {
                "optimizer_id",
                "scipy_version",
                "method",
                "method_variant",
                "ftol",
                "xtol",
                "gtol",
                "max_nfev",
                "seed",
                "status",
                "success",
                "nfev",
                "cost",
                "optimality",
                "objective_mse",
                "initial_parameters",
                "lower_bounds",
                "upper_bounds",
            },
            "law optimizer evidence",
        )
        if (
            law_optimizer["optimizer_id"]
            != "cmp.dma_tts.shift_law_log10_least_squares.scipy_trf@1.0.0"
            or law_optimizer["method"] != "least_squares"
            or law_optimizer["method_variant"] != "trf"
            or law_optimizer["seed"] is not None
            or law_optimizer["ftol"] != 1e-12
            or law_optimizer["xtol"] != 1e-12
            or law_optimizer["gtol"] != 1e-12
            or law_optimizer["max_nfev"] != 5000
            or law_optimizer["initial_parameters"] != shift_law["initial_parameters"]
            or law_optimizer["lower_bounds"] != shift_law["lower_bounds"]
            or law_optimizer["upper_bounds"] != shift_law["upper_bounds"]
            or law_optimizer["success"] is not True
        ):
            raise ValueError("multi-frequency law optimizer evidence is not exact")
        for name in ("cost", "optimality", "objective_mse"):
            _dma_number(law_optimizer[name], f"law optimizer {name}")
    nonexcluded = [row for row in rows if row["partition"] != "EXCLUDED"]
    per_temperature = shift_law["per_temperature"]
    if not isinstance(per_temperature, list) or len(per_temperature) != len(nonexcluded):
        raise ValueError("multi-frequency per-temperature law evidence is incomplete")
    rows_by_sweep = {row["source_sweep_ordinal"]: row for row in nonexcluded}
    seen_sweeps: set[int] = set()
    for item in per_temperature:
        entry = _dma_exact_keys(
            item,
            {
                "source_sweep_ordinal",
                "representative_temperature_k",
                "observed_log10_a_t",
                "applied_log10_a_t",
                "shift_residual_log10_a_t",
            },
            "per-temperature law evidence",
        )
        sweep = _dma_integer(entry["source_sweep_ordinal"], "per-temperature sweep", minimum=1)
        if sweep in seen_sweeps or sweep not in rows_by_sweep:
            raise ValueError("per-temperature law evidence has an invalid sweep identity")
        seen_sweeps.add(sweep)
        row = rows_by_sweep[sweep]
        if entry["representative_temperature_k"] != row["representative_temperature_k"]:
            raise ValueError("per-temperature law evidence has an invalid temperature")
        for name in ("observed_log10_a_t", "applied_log10_a_t", "shift_residual_log10_a_t"):
            expected = row.get(name)
            actual = entry[name]
            if expected is None:
                if actual is not None:
                    raise ValueError("per-temperature law evidence has an invalid null pattern")
            elif not math.isclose(
                _dma_number(actual, name), expected, rel_tol=1e-12, abs_tol=1e-12
            ):
                raise ValueError("per-temperature law evidence differs from result rows")
    if seen_sweeps != set(rows_by_sweep):
        raise ValueError("per-temperature law evidence does not cover every nonexcluded sweep")
    expected_adjacent_rows = sorted(comparison_rows, key=lambda row: row["source_sweep_ordinal"])
    for item, row in zip(adjacent_evidence, expected_adjacent_rows, strict=True):
        entry = _dma_exact_keys(
            item,
            {
                "source_sweep_ordinal",
                "comparison_sweep_ordinal",
                "relative_observed_log10_shift",
                "score",
                "evidence",
            },
            "adjacent evidence",
        )
        anchor = next(
            (
                candidate
                for candidate in rows
                if candidate["source_sweep_ordinal"] == row["comparison_sweep_ordinal"]
            ),
            None,
        )
        if (
            anchor is None
            or entry["source_sweep_ordinal"] != row["source_sweep_ordinal"]
            or entry["comparison_sweep_ordinal"] != row["comparison_sweep_ordinal"]
            or not math.isclose(
                _dma_number(entry["relative_observed_log10_shift"], "relative shift"),
                row["observed_log10_a_t"] - anchor["observed_log10_a_t"],
                rel_tol=1e-12,
                abs_tol=1e-12,
            )
        ):
            raise ValueError("adjacent evidence identities or shift differ from result rows")
        score = _dma_exact_keys(
            entry["score"],
            {
                "overlap_min_log10_reduced_omega",
                "overlap_max_log10_reduced_omega",
                "storage_mse",
                "loss_mse",
                "weighted_mse",
            },
            "adjacent score",
        )
        for name, result_name in (
            ("overlap_min_log10_reduced_omega", "overlap_log10_reduced_angular_frequency_min"),
            ("overlap_max_log10_reduced_omega", "overlap_log10_reduced_angular_frequency_max"),
            ("storage_mse", "storage_mse"),
            ("loss_mse", "loss_mse"),
            ("weighted_mse", "weighted_mse"),
        ):
            if not math.isclose(
                _dma_number(score[name], name),
                row[result_name],
                rel_tol=1e-12,
                abs_tol=1e-12,
            ):
                raise ValueError("adjacent score differs from result rows")
        outcome = _dma_exact_keys(
            entry["evidence"],
            {"success", "status", "iterations", "evaluations", "objective"},
            "adjacent optimizer outcome",
        )
        if (
            outcome["success"] is not True
            or any(
                outcome[name] != row[f"adjacent_{name}"]
                for name in ("status", "iterations", "evaluations")
            )
            or not math.isclose(
                _dma_number(outcome["objective"], "adjacent objective"),
                row["adjacent_objective"],
                rel_tol=1e-12,
                abs_tol=1e-12,
            )
        ):
            raise ValueError("adjacent optimizer outcome differs from result rows")
    if shift_law["adjacent_observed"] != adjacent_evidence:
        raise ValueError("shift-law adjacent evidence differs from optimizer evidence")
    residual = _dma_exact_keys(
        options["residual_summary"],
        {
            "calibration_comparison_count",
            "units",
            "storage_mse",
            "loss_mse",
            "storage_rmse",
            "loss_rmse",
            "weighted_mse",
            "holdout_evaluation_separate",
        },
        "residual summary",
    )
    if (
        residual["calibration_comparison_count"] != len(comparison_rows)
        or residual["units"] != "log10(modulus) and log10(aT)"
        or residual["holdout_evaluation_separate"] is not True
    ):
        raise ValueError("multi-frequency residual summary is not exact")
    for name, expected in (
        (
            "storage_mse",
            sum(row["storage_mse"] for row in comparison_rows) / len(comparison_rows),
        ),
        (
            "loss_mse",
            sum(row["loss_mse"] for row in comparison_rows) / len(comparison_rows),
        ),
        (
            "weighted_mse",
            sum(row["weighted_mse"] for row in comparison_rows) / len(comparison_rows),
        ),
    ):
        if not math.isclose(
            _dma_number(residual[name], name), expected, rel_tol=1e-12, abs_tol=1e-12
        ):
            raise ValueError("multi-frequency residual summary differs from result rows")
    if not math.isclose(
        _dma_number(residual["storage_rmse"], "residual storage RMSE"),
        math.sqrt(float(residual["storage_mse"])),
        rel_tol=1e-12,
        abs_tol=1e-12,
    ) or not math.isclose(
        _dma_number(residual["loss_rmse"], "residual loss RMSE"),
        math.sqrt(float(residual["loss_mse"])),
        rel_tol=1e-12,
        abs_tol=1e-12,
    ):
        raise ValueError("multi-frequency residual summary RMSE is invalid")
    application_range = _dma_exact_keys(
        options["application_range"],
        {
            "basis",
            "holdout_included",
            "reduced_angular_frequency_intervals_rad_per_s",
            "calibration_temperature_interval_k",
        },
        "application range",
    )
    if (
        application_range["basis"] != "at_least_two_shifted_calibration_isotherms"
        or application_range["holdout_included"] is not False
    ):
        raise ValueError("multi-frequency application range basis is invalid")
    actual_intervals = application_range["reduced_angular_frequency_intervals_rad_per_s"]
    if not isinstance(actual_intervals, list) or not actual_intervals:
        raise ValueError("multi-frequency application range intervals are missing")
    actual_pairs: list[tuple[float, float]] = []
    previous = 0.0
    for item in actual_intervals:
        interval = _dma_exact_keys(item, {"minimum", "maximum"}, "application interval")
        minimum = _dma_number(interval["minimum"], "application minimum", positive=True)
        maximum = _dma_number(interval["maximum"], "application maximum", positive=True)
        if maximum <= minimum or minimum <= previous:
            raise ValueError("application intervals are not sorted and merged")
        actual_pairs.append((minimum, maximum))
        previous = maximum
    shifted_ranges = [
        (
            row["shifted_angular_frequency_min_rad_per_s"],
            row["shifted_angular_frequency_max_rad_per_s"],
        )
        for row in rows
        if row["partition"] == "CALIBRATION"
    ]
    endpoints = sorted({endpoint for pair in shifted_ranges for endpoint in pair})
    expected_pairs: list[tuple[float, float]] = []
    for left, right in pairwise(endpoints):
        if (
            right <= left
            or sum(start <= left and right <= finish for start, finish in shifted_ranges) < 2
        ):
            continue
        if expected_pairs and expected_pairs[-1][1] == left:
            expected_pairs[-1] = (expected_pairs[-1][0], right)
        else:
            expected_pairs.append((left, right))
    if len(actual_pairs) != len(expected_pairs) or any(
        not math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-12)
        for actual_pair, expected_pair in zip(actual_pairs, expected_pairs, strict=True)
        for actual, expected in zip(actual_pair, expected_pair, strict=True)
    ):
        raise ValueError("application intervals differ from shifted calibration ranges")
    temperature_interval = _dma_exact_keys(
        application_range["calibration_temperature_interval_k"],
        {"minimum", "maximum"},
        "calibration temperature interval",
    )
    calibration_temperatures = [
        row["representative_temperature_k"] for row in rows if row["partition"] == "CALIBRATION"
    ]
    if _dma_number(temperature_interval["minimum"], "calibration temperature minimum") != min(
        calibration_temperatures
    ) or _dma_number(temperature_interval["maximum"], "calibration temperature maximum") != max(
        calibration_temperatures
    ):
        raise ValueError("calibration temperature interval differs from result rows")


def _processed_dma_envelope(
    result_bytes: bytes,
    metadata_bytes: bytes,
    plan: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], pa.Table]:
    """Validate exact Processing Output pins and return its typed result table."""

    semantics = plan.get("input_semantics")
    output_pin = plan.get("processing_output")
    metadata_pin = plan.get("processing_metadata_artifact")
    result_pin = plan.get("processing_result_artifact")
    if not all(
        isinstance(value, dict) for value in (semantics, output_pin, metadata_pin, result_pin)
    ):
        raise ValueError("processed Plan is missing exact Processing Output evidence")
    assert isinstance(semantics, dict)
    assert isinstance(output_pin, dict)
    assert isinstance(metadata_pin, dict)
    assert isinstance(result_pin, dict)
    if (
        semantics.get("mode") != "dma_frequency_master_curve"
        or semantics.get("source_kind") != "processing_output"
        or semantics.get("processing_method") != "polymer.dma_frequency_master_curve@1.0.0"
        or semantics.get("frequency_kind") != "reduced_angular_rad_per_s"
        or semantics.get("dma_domain_policy") != "nondecreasing_observations"
        or semantics.get("angular_frequency_conversion")
        != (
            "omega_reduced_rad_per_s=omega_rad_per_s*shift_factor;"
            "frequency_reduced_hz=omega_reduced_rad_per_s/(2*pi)"
        )
    ):
        raise ValueError("processed Plan DMA master-curve semantics are unsupported")
    if hashlib.sha256(metadata_bytes).hexdigest() != metadata_pin.get("sha256"):
        raise ValueError("Processing Output metadata digest differs from the Plan pin")
    if hashlib.sha256(result_bytes).hexdigest() != result_pin.get("sha256"):
        raise ValueError("Processing Output result digest differs from the Plan pin")
    try:
        metadata = json.loads(metadata_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("Processing Output metadata is not valid JSON") from error
    if not isinstance(metadata, dict):
        raise ValueError("Processing Output metadata must be a JSON object")
    result_artifact = metadata.get("result_artifact")
    step = metadata.get("step")
    if (
        metadata.get("document_type") != "cmp.processing-output"
        or metadata.get("document_version") != "1.6.0"
        or metadata.get("output_id") != output_pin.get("id")
        or not isinstance(result_artifact, dict)
        or result_artifact.get("artifact_id") != result_pin.get("artifact_id")
        or result_artifact.get("sha256") != result_pin.get("sha256")
        or result_artifact.get("schema_ref") != DMA_MASTER_CURVE_SCHEMA
        or result_artifact.get("media_type") != "application/vnd.apache.parquet"
        or not isinstance(step, dict)
        or step.get("method_id") != "polymer.dma_frequency_master_curve"
        or step.get("method_version") != "1.0.0"
    ):
        raise ValueError("Processing Output metadata does not match the Plan or DMA schema")
    options = step.get("options")
    if not isinstance(options, dict):
        raise ValueError("DMA Processing Output options are not an object")
    mode = options.get("input_mode")
    if mode not in {"fixed_frequency_temperature_sweep", "multi_frequency_isotherms"}:
        raise ValueError("DMA Processing Output mode is unsupported")
    try:
        table = pq.read_table(pa.BufferReader(result_bytes))
    except Exception as error:
        raise ValueError("processing-output.result is not valid Parquet") from error
    if (
        tuple(table.column_names) != DMA_MASTER_CURVE_COLUMNS
        or table.schema != DMA_MASTER_CURVE_ARROW_SCHEMA
        or table.num_rows != options.get("result_row_count")
    ):
        raise ValueError("DMA master-curve Parquet fields are not the exact current shape")
    return semantics, options, table


def _processed_dma_observations(
    result_bytes: bytes,
    metadata_bytes: bytes,
    plan: dict[str, Any],
) -> tuple[str, list[dict[str, Any]]]:
    """Read exact ragged DMA evidence and expose only model-ready observations."""

    semantics, options, table = _processed_dma_envelope(result_bytes, metadata_bytes, plan)
    mode = str(options["input_mode"])
    decoded_rows: list[dict[str, Any]] = []
    observations: list[dict[str, Any]] = []
    source_sweeps: set[int] = set()
    source_ordinals: set[int] = set()
    calibration_observation_count = 0
    calibration_sweep_count = 0
    holdout_sweep_count = 0
    reference_count = 0
    for source in table.to_pylist():
        row, row_observations = _dma_validate_row(source, mode)
        decoded_rows.append(row)
        if mode == "multi_frequency_isotherms":
            sweep = int(row["source_sweep_ordinal"])
            if sweep in source_sweeps:
                raise ValueError("multi-frequency source sweep identities are duplicated")
            source_sweeps.add(sweep)
            row_source_ordinals = row["source_ordinals"]
            if any(ordinal in source_ordinals for ordinal in row_source_ordinals):
                raise ValueError("multi-frequency source row ordinals are duplicated")
            source_ordinals.update(row_source_ordinals)
        if row["is_reference"]:
            reference_count += 1
        if row["partition"] == "CALIBRATION":
            calibration_sweep_count += 1
            calibration_observation_count += len(row["source_ordinals"])
        elif row["partition"] == "HOLDOUT":
            holdout_sweep_count += 1
        observations.extend(row_observations)
    observations.sort(
        key=lambda item: (
            item["frequency_hz"],
            item["representative_temperature_k"],
            -1
            if item["source_sweep_ordinal"] is None
            else item["source_sweep_ordinal"],
            item["source_ordinal"],
        )
    )
    for ordinal, observation in enumerate(observations):
        observation["ordinal"] = ordinal
    if reference_count != 1:
        raise ValueError("DMA result must contain exactly one calibration reference row")
    if mode == "multi_frequency_isotherms" and (
        calibration_sweep_count < 2 or holdout_sweep_count != 1
    ):
        raise ValueError("multi-frequency result partitions are not exact")
    dispositions = semantics.get("point_dispositions")
    if (
        not isinstance(dispositions, list)
        or len(dispositions) != calibration_observation_count
        or any(
            not isinstance(item, dict)
            or item.get("ordinal") != index
            or item.get("partition") != "CALIBRATION"
            or item.get("exclusion_reason") is not None
            for index, item in enumerate(dispositions)
        )
    ):
        raise ValueError("processed Plan dispositions do not cover calibration observations")
    if (
        sum(
            len(row["source_ordinals"]) for row in decoded_rows if row["partition"] == "CALIBRATION"
        )
        < 3
    ):
        raise ValueError("processed DMA input requires at least three calibration observations")
    _dma_validate_options(options, mode, decoded_rows)
    return "dma", observations


def _rank_diagnostic(jacobian: np.ndarray, parameter_count: int) -> dict[str, Any]:
    """Record the prescribed terminal scaled-Jacobian SVD evidence."""

    matrix = np.asarray(jacobian, dtype=np.float64)
    m, _ = matrix.shape
    norms = np.linalg.norm(matrix, axis=0)
    scaled = matrix / np.where(norms > 0, norms, 1.0)
    singular = np.linalg.svd(scaled, compute_uv=False)
    sigma_max = float(singular[0]) if singular.size else 0.0
    threshold = float(max(m, parameter_count) * np.finfo(np.float64).eps * sigma_max)
    rank = int(np.count_nonzero(singular > threshold)) if sigma_max else 0
    status = "FULL_RANK" if rank >= parameter_count else "RANK_DEFICIENT"
    return {
        "singular_values": [float(item) for item in singular],
        "sigma_max": sigma_max,
        "threshold": threshold,
        "rank": rank,
        "status": status,
        "warning_code": "RANK_DEFICIENT" if status == "RANK_DEFICIENT" else None,
    }


class LinearViscoelasticCalibrator:
    def describe(self) -> ExtensionDescriptor:
        return ExtensionDescriptor(ExtensionType.CALIBRATOR, ("generalized-maxwell-shear",))

    def validate_job(self, job: RunnerJobSpec) -> ValidationReport:
        if job.operation != "execute_plan":
            return ValidationReport.reject(
                _error("CMP-LVE-0001", "linear-viscoelastic calibrator requires execute_plan")
            )
        if job.seed != 0:
            return ValidationReport.reject(
                _error("CMP-LVE-0002", "transport seed must be zero/not_applicable")
            )
        if job.config_schema_ref != CONFIG_SCHEMA:
            return ValidationReport.reject(
                _error("CMP-LVE-0003", "calibrator config schema is not the exact 1.0.0 schema")
            )
        config = job.config
        if (
            config.get("schema_version") != "1.0.0"
            or config.get("seed_status") != "not_applicable"
            or config.get("recommendation_policy") != RECOMMENDATION_POLICY
        ):
            return ValidationReport.reject(
                _error("CMP-LVE-0004", "calibrator config version or seed status is invalid")
            )
        required_roles = {
            "calibration.plan",
            "test-data.canonical",
            "test-data.normalized",
        }
        processed_roles = {
            *required_roles,
            "processing-output.metadata",
            "processing-output.result",
        }
        actual_roles = {item.role for item in job.inputs}
        if actual_roles not in (required_roles, processed_roles):
            return ValidationReport.reject(
                _error(
                    "CMP-LVE-0005",
                    "calibrator requires exact direct or processed scoped input roles",
                )
            )
        output_roles = {item.role for item in job.expected_outputs}
        if output_roles != {"calibration.run-result", "response-residuals", "objective-history"}:
            return ValidationReport.reject(
                _error("CMP-LVE-0006", "calibrator output roles are not the exact declared set")
            )
        return ValidationReport.ok()

    def run(self, context: RunContext, job: RunnerJobSpec) -> ExtensionOutcome:
        try:
            plan = _load_plan(context)
            if plan.get("recommendation_policy") != RECOMMENDATION_POLICY:
                raise ValueError("Plan recommendation policy is unsupported")
            if job.config.get("recommendation_policy") != plan["recommendation_policy"]:
                raise ValueError("Job and Plan recommendation policies differ")
            canonical = json.loads(
                context.read_input("test-data.canonical", maximum_bytes=32 * 1024 * 1024)
            )
            # Reading the normalized Arrow payload is mandatory even when the canonical JSON
            # carries the same rows: it proves the worker used the exact normalized Artifact.
            normalized = context.read_input("test-data.normalized", maximum_bytes=268_435_456)
            if not normalized:
                raise ValueError("normalized Artifact is empty")
            semantics = plan.get("input_semantics")
            if not isinstance(semantics, dict):
                raise ValueError("Plan input_semantics is missing")
            source_mode = semantics.get("mode")
            if source_mode in {"relaxation", "dma"} and plan.get("processing_output") is None:
                mode, observations = _normalized_observations(normalized, canonical, plan)
            elif (
                source_mode == "dma_frequency_master_curve"
                and plan.get("processing_output") is not None
            ):
                metadata = context.read_input(
                    "processing-output.metadata", maximum_bytes=64 * 1024 * 1024
                )
                processed = context.read_input(
                    "processing-output.result", maximum_bytes=268_435_456
                )
                mode, observations = _processed_dma_observations(processed, metadata, plan)
            else:
                raise ValueError("Plan source semantics and staged input roles are inconsistent")
            calibration = [item for item in observations if item.get("partition") == "CALIBRATION"]
            holdout = [item for item in observations if item.get("partition") == "HOLDOUT"]
            if len(calibration) < 3:
                raise ValueError("at least three calibration rows are required")
            term_counts = [int(item) for item in plan.get("term_counts", [])]
            bounds_document = plan.get("parameter_bounds", {})
            starts_document = plan.get("start_vectors", {})
            attempts: list[dict[str, Any]] = []
            candidates: list[dict[str, Any]] = []
            ordinal = 0
            for term_count in term_counts:
                bounds = bounds_document.get(str(term_count), bounds_document.get(term_count))
                starts = starts_document.get(str(term_count), starts_document.get(term_count))
                if not isinstance(bounds, list) or not isinstance(starts, list):
                    raise ValueError("Plan bounds/starts are missing for a declared term count")
                lower = np.log(
                    np.asarray([float(item["lower"]) for item in bounds], dtype=np.float64)
                )
                upper = np.log(
                    np.asarray([float(item["upper"]) for item in bounds], dtype=np.float64)
                )
                for start in starts:
                    ordinal += 1
                    start_physical = np.asarray([float(item) for item in start], dtype=np.float64)
                    history: list[dict[str, Any]] = []
                    if mode == "relaxation":
                        domain = np.asarray(
                            [float(item["time_s"]) for item in calibration], dtype=np.float64
                        )
                        observed = np.asarray(
                            [
                                float(item.get("modulus_pa", item.get("shear_modulus_pa")))
                                for item in calibration
                            ],
                            dtype=np.float64,
                        )
                        scale = float(plan["weights"]["relaxation_scale_pa"])

                        def residual(
                            transformed: np.ndarray,
                            _term_count: int = term_count,
                            _domain: np.ndarray = domain,
                            _observed: np.ndarray = observed,
                            _scale: float = scale,
                            _history: list[dict[str, Any]] = history,
                        ) -> np.ndarray:
                            physical = np.exp(transformed)
                            prediction, _ = _evaluate(_term_count, physical, _domain, mode)
                            result = (prediction - _observed) / _scale / math.sqrt(len(calibration))
                            _history.append(
                                {
                                    "ordinal": len(_history),
                                    "objective": float(np.dot(result, result)),
                                }
                            )
                            return result
                    else:
                        domain = np.asarray(
                            [float(item["frequency_hz"]) for item in calibration], dtype=np.float64
                        )
                        observed_storage = np.asarray(
                            [float(item["storage_modulus_pa"]) for item in calibration],
                            dtype=np.float64,
                        )
                        observed_loss = np.asarray(
                            [float(item["loss_modulus_pa"]) for item in calibration],
                            dtype=np.float64,
                        )
                        weights = plan["weights"]

                        def residual(
                            transformed: np.ndarray,
                            _term_count: int = term_count,
                            _domain: np.ndarray = domain,
                            _observed_storage: np.ndarray = observed_storage,
                            _observed_loss: np.ndarray = observed_loss,
                            _weights: dict[str, Any] = weights,
                            _history: list[dict[str, Any]] = history,
                        ) -> np.ndarray:
                            physical = np.exp(transformed)
                            prediction_storage, prediction_loss = _evaluate(
                                _term_count, physical, _domain, mode
                            )
                            result = np.concatenate(
                                (
                                    (prediction_storage - _observed_storage)
                                    / float(_weights["dma_storage_scale_pa"])
                                    * math.sqrt(
                                        float(_weights["dma_storage_weight"]) / len(calibration)
                                    ),
                                    (prediction_loss - _observed_loss)
                                    / float(_weights["dma_loss_scale_pa"])
                                    * math.sqrt(
                                        float(_weights["dma_loss_weight"]) / len(calibration)
                                    ),
                                )
                            )
                            _history.append(
                                {
                                    "ordinal": len(_history),
                                    "objective": float(np.dot(result, result)),
                                }
                            )
                            return result

                    try:
                        result = least_squares(
                            residual,
                            np.log(start_physical),
                            bounds=(lower, upper),
                            method="trf",
                            x_scale="jac",
                            ftol=float(plan["optimizer"]["ftol"]),
                            xtol=float(plan["optimizer"]["xtol"]),
                            gtol=float(plan["optimizer"]["gtol"]),
                            max_nfev=int(plan["optimizer"]["max_nfev"]),
                        )
                        physical = np.exp(result.x)
                        residuals = residual(result.x)
                        success = bool(result.success and np.all(np.isfinite(physical)))
                        rank = _rank_diagnostic(
                            np.asarray(result.jac, dtype=np.float64), physical.size
                        )
                        warnings = [rank["warning_code"]] if rank["warning_code"] else []
                        attempt = {
                            "ordinal": ordinal,
                            "term_count": term_count,
                            "start_vector": start_physical.tolist(),
                            "transformed_start_vector": np.log(start_physical).tolist(),
                            "status": int(result.status),
                            "message": str(result.message),
                            "nfev": int(result.nfev),
                            "cost": float(result.cost),
                            "optimality": float(result.optimality),
                            "active_mask": [int(item) for item in result.active_mask],
                            "physical_parameters": physical.tolist(),
                            "transformed_parameters": result.x.tolist(),
                            "residuals": residuals.tolist(),
                            "rss": float(np.dot(residuals, residuals)),
                            "rank": rank,
                            "warnings": warnings,
                            "objective_history": history,
                            "converged": success,
                            "physical": success,
                        }
                    except (ValueError, FloatingPointError) as error:
                        attempt = {
                            "ordinal": ordinal,
                            "term_count": term_count,
                            "start_vector": start_physical.tolist(),
                            "transformed_start_vector": np.log(start_physical).tolist(),
                            "status": 0,
                            "message": str(error),
                            "nfev": 0,
                            "cost": 0.0,
                            "optimality": 0.0,
                            "active_mask": [0] * len(start_physical),
                            "physical_parameters": start_physical.tolist(),
                            "transformed_parameters": np.log(start_physical).tolist(),
                            "residuals": [],
                            "rss": 0.0,
                            "rank": {
                                "singular_values": [],
                                "sigma_max": 0.0,
                                "threshold": 0.0,
                                "rank": 0,
                                "status": "RANK_DEFICIENT",
                                "warning_code": "RANK_DEFICIENT",
                            },
                            "warnings": ["EXECUTION_REQUEST_INVALID"],
                            "objective_history": history,
                            "converged": False,
                            "physical": False,
                        }
                    attempts.append(attempt)
                    if attempt["converged"] and attempt["physical"]:
                        holdout_residuals: list[float] = []
                        if holdout:
                            if mode == "relaxation":
                                holdout_domain = np.asarray(
                                    [float(item["time_s"]) for item in holdout], dtype=np.float64
                                )
                                holdout_observed = np.asarray(
                                    [float(item["modulus_pa"]) for item in holdout],
                                    dtype=np.float64,
                                )
                                holdout_residuals = (
                                    (
                                        _evaluate(term_count, physical, holdout_domain, mode)[0]
                                        - holdout_observed
                                    )
                                    / float(plan["weights"]["relaxation_scale_pa"])
                                ).tolist()
                            else:
                                holdout_domain = np.asarray(
                                    [float(item["frequency_hz"]) for item in holdout],
                                    dtype=np.float64,
                                )
                                holdout_storage = np.asarray(
                                    [float(item["storage_modulus_pa"]) for item in holdout],
                                    dtype=np.float64,
                                )
                                holdout_loss = np.asarray(
                                    [float(item["loss_modulus_pa"]) for item in holdout],
                                    dtype=np.float64,
                                )
                                holdout_prediction = _evaluate(
                                    term_count, physical, holdout_domain, mode
                                )
                                holdout_residuals = np.concatenate(
                                    (
                                        (holdout_prediction[0] - holdout_storage)
                                        / float(plan["weights"]["dma_storage_scale_pa"]),
                                        (holdout_prediction[1] - holdout_loss)
                                        / float(plan["weights"]["dma_loss_scale_pa"]),
                                    )
                                ).tolist()
                        candidate = {
                            "candidate_id": str(
                                uuid5(
                                    NAMESPACE_URL,
                                    f"{job.config.get('run_id', job.job_id)}:candidate:{ordinal}",
                                )
                            ),
                            "attempt_ordinal": ordinal,
                            "term_count": term_count,
                            "physical_parameters": attempt["physical_parameters"],
                            "transformed_parameters": attempt["transformed_parameters"],
                            "rss": attempt["rss"],
                            "bic": float(
                                len(attempt["residuals"])
                                * math.log(
                                    max(
                                        attempt["rss"] / len(attempt["residuals"]),
                                        np.finfo(np.float64).tiny,
                                    )
                                )
                                + (1 + 2 * term_count) * math.log(len(attempt["residuals"]))
                            ),
                            "calibration_residuals": attempt["residuals"],
                            "holdout_residuals": holdout_residuals,
                            "rank": attempt["rank"],
                            "warnings": attempt.get("warnings", []),
                            "uncertainty_status": "NOT_PROVIDED",
                        }
                        candidates.append(candidate)
            candidates.sort(
                key=lambda item: _recommendation_key(item, plan["recommendation_policy"])
            )
            status = "succeeded" if candidates else "failed"
            recommendation = None
            if candidates:
                winner = candidates[0]
                recommendation = {
                    "recommendation_id": str(
                        uuid5(
                            NAMESPACE_URL, f"{job.config.get('run_id', job.job_id)}:recommendation"
                        )
                    ),
                    "candidate_id": winner["candidate_id"],
                    "candidate_digest": hashlib.sha256(
                        json.dumps(
                            winner, allow_nan=False, separators=(",", ":"), sort_keys=True
                        ).encode("utf-8")
                    ).hexdigest(),
                    "rule_version": "linear_viscoelastic_bic@1.0.0",
                }
            result_document = {
                "schema_id": RESULT_SCHEMA,
                "schema_version": "1.0.0",
                "run_id": str(job.config.get("run_id", job.job_id)),
                "plan_revision_id": str(job.config.get("plan_revision_id")),
                "status": status,
                "attempts": attempts,
                "candidates": candidates,
                "recommendation": recommendation,
                "failure_code": None if candidates else "CALCULATION_FAILED",
                "failure_detail": None if candidates else "No candidate converged",
                "recovery_hint": None
                if candidates
                else "Create a new immutable Plan with reviewed bounds or starts.",
            }
            residual_columns: dict[str, list[Any]] = {
                "ordinal": [],
                "channel": [],
                "observed": [],
                "predicted": [],
                "residual": [],
                "partition": [],
            }
            winner_parameters = (
                np.asarray(candidates[0]["physical_parameters"], dtype=np.float64)
                if candidates
                else None
            )
            for point in observations:
                if mode == "relaxation":
                    prediction = 0.0
                    if winner_parameters is not None:
                        prediction = float(
                            _evaluate(
                                candidates[0]["term_count"],
                                winner_parameters,
                                np.asarray([float(point["time_s"])], dtype=np.float64),
                                mode,
                            )[0][0]
                        )
                    residual_columns["ordinal"].append(int(point["ordinal"]))
                    residual_columns["channel"].append("relaxation")
                    residual_columns["observed"].append(float(point["modulus_pa"]))
                    residual_columns["predicted"].append(prediction)
                    residual_columns["residual"].append(prediction - float(point["modulus_pa"]))
                    residual_columns["partition"].append(str(point.get("partition", "CALIBRATION")))
                else:
                    for channel, observed_key in (
                        ("dma_storage", "storage_modulus_pa"),
                        ("dma_loss", "loss_modulus_pa"),
                    ):
                        prediction = 0.0
                        if winner_parameters is not None:
                            values = _evaluate(
                                candidates[0]["term_count"],
                                winner_parameters,
                                np.asarray([float(point["frequency_hz"])], dtype=np.float64),
                                mode,
                            )
                            prediction = float(values[0 if channel == "dma_storage" else 1][0])
                        residual_columns["ordinal"].append(int(point["ordinal"]))
                        residual_columns["channel"].append(channel)
                        residual_columns["observed"].append(float(point[observed_key]))
                        residual_columns["predicted"].append(prediction)
                        residual_columns["residual"].append(prediction - float(point[observed_key]))
                        residual_columns["partition"].append(
                            str(point.get("partition", "CALIBRATION"))
                        )
            residual_payload = _parquet_bytes(residual_columns)
            evaluations = [
                item for attempt in attempts for item in attempt.get("objective_history", [])
            ]
            history_payload = _parquet_bytes(
                {
                    "ordinal": [int(item.get("ordinal", 0)) for item in evaluations],
                    "objective": [float(item.get("objective", 0.0)) for item in evaluations],
                }
            )
            context.write_output(
                role="calibration.run-result",
                media_type="application/json",
                schema_ref=RESULT_SCHEMA,
                data=json.dumps(
                    result_document, allow_nan=False, separators=(",", ":"), sort_keys=True
                ).encode("utf-8"),
            )
            context.write_output(
                role="response-residuals",
                media_type="application/vnd.apache.parquet",
                schema_ref=RESIDUAL_SCHEMA,
                data=residual_payload,
            )
            context.write_output(
                role="objective-history",
                media_type="application/vnd.apache.parquet",
                schema_ref=HISTORY_SCHEMA,
                data=history_payload,
            )
            return ExtensionOutcome(
                ExtensionStatus.SUCCEEDED if candidates else ExtensionStatus.FAILED
            )
        except Exception as error:
            return ExtensionOutcome(ExtensionStatus.FAILED, (_error("CMP-LVE-0007", str(error)),))

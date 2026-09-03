"""Canonical DMA result schema and strict Parquet serialization."""

from __future__ import annotations

import math
from collections.abc import Sequence
from decimal import Decimal, InvalidOperation
from itertools import pairwise
from typing import Any, cast
from uuid import UUID

import pyarrow as pa
import pyarrow.parquet as pq

from cmp.modules.processing.domain.dma_frequency_master_curve import (
    DMA_FREQUENCY_MASTER_CURVE_COLUMNS,
    DMA_SWEEP_TEMPERATURE_TOLERANCE_K,
    DmaFrequencyMasterCurveRow,
    DmaInputMode,
    DmaPartition,
    DmaProcessingError,
    _fail,
)
from cmp.modules.processing.domain.temperature_shift import (
    UNIVERSAL_GAS_CONSTANT_J_PER_MOL_K,
)

_write_parquet = cast(Any, pq.write_table)
_read_parquet = cast(Any, pq.read_table)


def _list_type(value_type: pa.DataType, *, nullable: bool = False) -> pa.DataType:
    return pa.list_(pa.field("item", value_type, nullable=nullable))


DMA_FREQUENCY_MASTER_CURVE_SCHEMA = pa.schema(
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
        pa.field("source_tan_delta", _list_type(pa.float64(), nullable=True), nullable=False),
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


def _read_failure(cause: str) -> DmaProcessingError:
    return _fail(4317, cause, "Reload the exact immutable current DMA result Artifact.")


def _decimal_temperature(value: object, name: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as error:
        raise _read_failure(f"result {name} is not a normalized numeric temperature") from error
    if not result.is_finite() or result <= 0:
        raise _read_failure(f"result {name} is not finite and positive")
    return result


def _validate_temperature_identity(row: DmaFrequencyMasterCurveRow) -> None:
    if row.input_mode != DmaInputMode.MULTI_FREQUENCY_ISOTHERMS.value:
        return
    counts: dict[Decimal, int] = {}
    measured_values = tuple(
        _decimal_temperature(value, "measured_temperature_k")
        for value in row.measured_temperature_k
    )
    for value in measured_values:
        counts[value] = counts.get(value, 0) + 1
    maximum = max(counts.values())
    expected = min(value for value, count in counts.items() if count == maximum)
    requested = _decimal_temperature(
        row.representative_temperature_k, "representative_temperature_k"
    )
    if requested != expected:
        raise _read_failure(
            "result representative temperature is not the normalized modal source temperature"
        )
    if any(
        abs(value - expected) > DMA_SWEEP_TEMPERATURE_TOLERANCE_K
        for value in measured_values
    ):
        raise _read_failure(
            "result measured temperature exceeds the inclusive "
            f"{DMA_SWEEP_TEMPERATURE_TOLERANCE_K} K sweep tolerance"
        )


def _canonical_key(row: DmaFrequencyMasterCurveRow) -> tuple[float, str, int]:
    return (
        row.representative_temperature_k,
        row.input_mode,
        -1 if row.source_sweep_ordinal is None else row.source_sweep_ordinal,
    )


def _validate_row_semantics(row: DmaFrequencyMasterCurveRow) -> None:
    _validate_temperature_identity(row)
    optional_float_fields = (
        ("shifted_angular_frequency_min_rad_per_s", row.shifted_angular_frequency_min_rad_per_s),
        ("shifted_angular_frequency_max_rad_per_s", row.shifted_angular_frequency_max_rad_per_s),
        ("observed_log10_a_t", row.observed_log10_a_t),
        ("applied_log10_a_t", row.applied_log10_a_t),
        ("shift_factor", row.shift_factor),
        ("shift_residual_log10_a_t", row.shift_residual_log10_a_t),
        (
            "overlap_log10_reduced_angular_frequency_min",
            row.overlap_log10_reduced_angular_frequency_min,
        ),
        (
            "overlap_log10_reduced_angular_frequency_max",
            row.overlap_log10_reduced_angular_frequency_max,
        ),
        ("storage_mse", row.storage_mse),
        ("loss_mse", row.loss_mse),
        ("storage_rmse", row.storage_rmse),
        ("loss_rmse", row.loss_rmse),
        ("weighted_mse", row.weighted_mse),
        ("adjacent_objective", row.adjacent_objective),
    )
    if any(
        value is not None
        and (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(float(value))
        )
        for _, value in optional_float_fields
    ):
        raise _read_failure("result contains a non-finite optional numeric value")
    for name, value in optional_float_fields:
        if name.endswith("_mse") and value is not None and value < 0:
            raise _read_failure(f"result {name} is negative")
    optional_integer_fields = (
        ("scoring_point_count", row.scoring_point_count),
        ("adjacent_status", row.adjacent_status),
        ("adjacent_iterations", row.adjacent_iterations),
        ("adjacent_evaluations", row.adjacent_evaluations),
        ("comparison_sweep_ordinal", row.comparison_sweep_ordinal),
    )
    if any(
        value is not None and (isinstance(value, bool) or not isinstance(value, int))
        for _, value in optional_integer_fields
    ):
        raise _read_failure("result contains an optional non-integer value")
    integer_bounds = (
        ("scoring_point_count", row.scoring_point_count, 2, 10_001),
        ("adjacent_iterations", row.adjacent_iterations, 0, None),
        ("adjacent_evaluations", row.adjacent_evaluations, 1, None),
    )
    if any(
        value is not None and (value < minimum or (maximum is not None and value > maximum))
        for _, value, minimum, maximum in integer_bounds
    ):
        raise _read_failure("result contains an optional integer outside its governed range")
    if row.input_mode == DmaInputMode.MULTI_FREQUENCY_ISOTHERMS.value and (
        row.comparison_sweep_ordinal is not None
        and not 1 <= row.comparison_sweep_ordinal <= 9_223_372_036_854_775_807
    ):
        raise _read_failure("multi-frequency comparison sweep identity is invalid")
    for frequency, omega in zip(
        row.source_frequency_hz, row.angular_frequency_rad_per_s, strict=True
    ):
        if not math.isclose(omega, 2.0 * math.pi * frequency, rel_tol=1e-12, abs_tol=1e-12):
            raise _read_failure("result angular frequency is not 2*pi times source frequency")
    if row.input_mode == DmaInputMode.MULTI_FREQUENCY_ISOTHERMS.value:
        if any(
            right <= left
            for left, right in pairwise(row.source_frequency_hz)
        ):
            raise _read_failure("multi-frequency source frequencies are not strictly increasing")
    if (
        row.storage_mse is not None
        and row.storage_rmse is not None
        and not math.isclose(
            row.storage_rmse, math.sqrt(max(0.0, row.storage_mse)), rel_tol=1e-12, abs_tol=1e-12
        )
    ):
        raise _read_failure("storage RMSE does not match storage MSE")
    if (
        row.loss_mse is not None
        and row.loss_rmse is not None
        and not math.isclose(
            row.loss_rmse, math.sqrt(max(0.0, row.loss_mse)), rel_tol=1e-12, abs_tol=1e-12
        )
    ):
        raise _read_failure("loss RMSE does not match loss MSE")
    if (
        row.overlap_log10_reduced_angular_frequency_min is not None
        and row.overlap_log10_reduced_angular_frequency_max is not None
        and row.overlap_log10_reduced_angular_frequency_max
        <= row.overlap_log10_reduced_angular_frequency_min
    ):
        raise _read_failure("result scoring overlap is not a positive-width interval")


def _validate_collection(
    rows: Sequence[DmaFrequencyMasterCurveRow],
) -> tuple[DmaFrequencyMasterCurveRow, ...]:
    frozen = tuple(rows)
    if not frozen:
        raise _read_failure("DMA result contains no rows")
    mode_set = {row.input_mode for row in frozen}
    if len(mode_set) != 1:
        raise _read_failure("DMA result mixes fixed and multi-frequency input modes")
    if tuple(_canonical_key(row) for row in frozen) != tuple(
        sorted(_canonical_key(row) for row in frozen)
    ):
        raise _read_failure("DMA result rows are not in canonical temperature and mode order")
    references = tuple(row for row in frozen if row.is_reference)
    if len(references) != 1 or references[0].partition is not DmaPartition.CALIBRATION:
        raise _read_failure("DMA result must contain exactly one calibration reference row")
    if mode_set == {DmaInputMode.FIXED_FREQUENCY_TEMPERATURE_SWEEP.value}:
        if any(row.source_sweep_ordinal is not None for row in frozen):
            raise _read_failure("fixed DMA result contains a source sweep identity")
        source_ordinals = tuple(row.source_ordinals[0] for row in frozen)
        if source_ordinals != tuple(sorted(source_ordinals)) or source_ordinals != tuple(
            range(len(frozen))
        ):
            raise _read_failure("fixed DMA result source ordinals are not canonical")
        if len({row.source_frequency_hz[0] for row in frozen}) != 1:
            raise _read_failure("fixed DMA result frequencies are not constant")
    else:
        sweep_ordinals = tuple(cast(int, row.source_sweep_ordinal) for row in frozen)
        if len(set(sweep_ordinals)) != len(sweep_ordinals) or any(
            value <= 0 for value in sweep_ordinals
        ):
            raise _read_failure(
                "multi-frequency source sweep identities are not unique positive int64 values"
            )
        source_ordinals = tuple(
            source_ordinal for row in frozen for source_ordinal in row.source_ordinals
        )
        if len(set(source_ordinals)) != len(source_ordinals):
            raise _read_failure("multi-frequency source row ordinals are not unique")
        calibration_count = sum(row.partition is DmaPartition.CALIBRATION for row in frozen)
        holdout_count = sum(row.partition is DmaPartition.HOLDOUT for row in frozen)
        if calibration_count < 2 or holdout_count != 1:
            raise _read_failure(
                "multi-frequency result partition does not contain at least two "
                "calibration and one holdout sweep"
            )
    for row in frozen:
        _validate_row_semantics(row)
    return frozen


def parquet_bytes(rows: Sequence[DmaFrequencyMasterCurveRow]) -> bytes:
    frozen = _validate_collection(rows)
    values: dict[str, list[object]] = {name: [] for name in DMA_FREQUENCY_MASTER_CURVE_COLUMNS}
    for row in frozen:
        values["input_mode"].append(row.input_mode)
        values["source_sweep_ordinal"].append(row.source_sweep_ordinal)
        values["representative_temperature_k"].append(row.representative_temperature_k)
        values["partition"].append(row.partition.value)
        values["is_reference"].append(row.is_reference)
        values["exclusion_reason"].append(row.exclusion_reason)
        values["holdout_evaluation_status"].append(row.holdout_evaluation_status)
        values["source_ordinals"].append(row.source_ordinals)
        values["measured_temperature_k"].append(row.measured_temperature_k)
        values["source_frequency_hz"].append(row.source_frequency_hz)
        values["angular_frequency_rad_per_s"].append(row.angular_frequency_rad_per_s)
        values["storage_modulus_pa"].append(row.storage_modulus_pa)
        values["loss_modulus_pa"].append(row.loss_modulus_pa)
        values["source_tan_delta"].append(row.source_tan_delta)
        values["loss_modulus_origin"].append(row.loss_modulus_origin)
        values["reduced_angular_frequency_rad_per_s"].append(
            row.reduced_angular_frequency_rad_per_s
        )
        values["raw_angular_frequency_min_rad_per_s"].append(
            row.raw_angular_frequency_min_rad_per_s
        )
        values["raw_angular_frequency_max_rad_per_s"].append(
            row.raw_angular_frequency_max_rad_per_s
        )
        values["shifted_angular_frequency_min_rad_per_s"].append(
            row.shifted_angular_frequency_min_rad_per_s
        )
        values["shifted_angular_frequency_max_rad_per_s"].append(
            row.shifted_angular_frequency_max_rad_per_s
        )
        values["comparison_sweep_ordinal"].append(row.comparison_sweep_ordinal)
        values["observed_log10_a_t"].append(row.observed_log10_a_t)
        values["applied_log10_a_t"].append(row.applied_log10_a_t)
        values["shift_factor"].append(row.shift_factor)
        values["shift_residual_log10_a_t"].append(row.shift_residual_log10_a_t)
        values["overlap_log10_reduced_angular_frequency_min"].append(
            row.overlap_log10_reduced_angular_frequency_min
        )
        values["overlap_log10_reduced_angular_frequency_max"].append(
            row.overlap_log10_reduced_angular_frequency_max
        )
        values["scoring_point_count"].append(row.scoring_point_count)
        values["storage_mse"].append(row.storage_mse)
        values["loss_mse"].append(row.loss_mse)
        values["storage_rmse"].append(row.storage_rmse)
        values["loss_rmse"].append(row.loss_rmse)
        values["weighted_mse"].append(row.weighted_mse)
        values["adjacent_success"].append(row.adjacent_success)
        values["adjacent_status"].append(row.adjacent_status)
        values["adjacent_iterations"].append(row.adjacent_iterations)
        values["adjacent_evaluations"].append(row.adjacent_evaluations)
        values["adjacent_objective"].append(row.adjacent_objective)
    type_by_name: dict[str, pa.DataType] = {
        "input_mode": pa.string(),
        "source_sweep_ordinal": pa.int64(),
        "representative_temperature_k": pa.float64(),
        "partition": pa.string(),
        "is_reference": pa.bool_(),
        "exclusion_reason": pa.string(),
        "holdout_evaluation_status": pa.string(),
        "source_ordinals": _list_type(pa.int64()),
        "measured_temperature_k": _list_type(pa.float64()),
        "source_frequency_hz": _list_type(pa.float64()),
        "angular_frequency_rad_per_s": _list_type(pa.float64()),
        "storage_modulus_pa": _list_type(pa.float64()),
        "loss_modulus_pa": _list_type(pa.float64()),
        "source_tan_delta": _list_type(pa.float64(), nullable=True),
        "loss_modulus_origin": _list_type(pa.string()),
        "reduced_angular_frequency_rad_per_s": _list_type(pa.float64()),
        "raw_angular_frequency_min_rad_per_s": pa.float64(),
        "raw_angular_frequency_max_rad_per_s": pa.float64(),
        "shifted_angular_frequency_min_rad_per_s": pa.float64(),
        "shifted_angular_frequency_max_rad_per_s": pa.float64(),
        "comparison_sweep_ordinal": pa.int64(),
        "observed_log10_a_t": pa.float64(),
        "applied_log10_a_t": pa.float64(),
        "shift_factor": pa.float64(),
        "shift_residual_log10_a_t": pa.float64(),
        "overlap_log10_reduced_angular_frequency_min": pa.float64(),
        "overlap_log10_reduced_angular_frequency_max": pa.float64(),
        "scoring_point_count": pa.int32(),
        "storage_mse": pa.float64(),
        "loss_mse": pa.float64(),
        "storage_rmse": pa.float64(),
        "loss_rmse": pa.float64(),
        "weighted_mse": pa.float64(),
        "adjacent_success": pa.bool_(),
        "adjacent_status": pa.int32(),
        "adjacent_iterations": pa.int64(),
        "adjacent_evaluations": pa.int64(),
        "adjacent_objective": pa.float64(),
    }
    table = pa.Table.from_arrays(
        [
            pa.array(values[name], type=type_by_name[name])
            for name in DMA_FREQUENCY_MASTER_CURVE_COLUMNS
        ],
        schema=DMA_FREQUENCY_MASTER_CURVE_SCHEMA,
    )
    if table.schema != DMA_FREQUENCY_MASTER_CURVE_SCHEMA:
        raise _read_failure("canonical DMA result schema could not be constructed")
    sink = pa.BufferOutputStream()
    _write_parquet(
        table,
        sink,
        compression="zstd",
        version="2.6",
        data_page_version="2.0",
        use_dictionary=False,
        write_statistics=True,
    )
    payload = sink.getvalue().to_pybytes()
    if not isinstance(payload, bytes):
        raise _read_failure("canonical DMA result bytes could not be materialized")
    return payload


def _tuple_int(values: object, name: str) -> tuple[int, ...]:
    if not isinstance(values, list):
        raise _read_failure(f"result {name} is not a list")
    if any(isinstance(item, bool) or not isinstance(item, int) for item in values):
        raise _read_failure(f"result {name} contains a non-integer")
    return tuple(values)


def _tuple_float(values: object, name: str) -> tuple[float, ...]:
    if not isinstance(values, list):
        raise _read_failure(f"result {name} is not a list")
    output = tuple(float(item) for item in values)
    if any(not math.isfinite(item) for item in output):
        raise _read_failure(f"result {name} contains a non-finite value")
    return output


def _tuple_optional_float(values: object, name: str) -> tuple[float | None, ...]:
    if not isinstance(values, list):
        raise _read_failure(f"result {name} is not a list")
    output: list[float | None] = []
    for item in values:
        if item is None:
            output.append(None)
            continue
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise _read_failure(f"result {name} contains a non-numeric value")
        number = float(item)
        if not math.isfinite(number):
            raise _read_failure(f"result {name} contains a non-finite value")
        output.append(number)
    return tuple(output)


def _tuple_string(values: object, name: str) -> tuple[str, ...]:
    if not isinstance(values, list) or any(not isinstance(item, str) for item in values):
        raise _read_failure(f"result {name} is not a string list")
    return tuple(values)


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise _read_failure("result optional value is not numeric")
    try:
        return float(value)
    except (TypeError, ValueError) as error:
        raise _read_failure("result optional value is not numeric") from error


def from_parquet(value: bytes) -> tuple[DmaFrequencyMasterCurveRow, ...]:
    try:
        table = _read_parquet(pa.BufferReader(value))
        if (
            tuple(table.column_names) != DMA_FREQUENCY_MASTER_CURVE_COLUMNS
            or table.schema != DMA_FREQUENCY_MASTER_CURVE_SCHEMA
        ):
            raise _read_failure(
                "result Arrow field order, types, or nullability are not the "
                "current canonical schema"
            )
        rows: list[DmaFrequencyMasterCurveRow] = []
        for raw in table.to_pylist():
            if not isinstance(raw, dict):
                raise _read_failure("result row is not an object")
            try:
                row = DmaFrequencyMasterCurveRow(
                    input_mode=str(raw["input_mode"]),
                    source_sweep_ordinal=None
                    if raw["source_sweep_ordinal"] is None
                    else int(raw["source_sweep_ordinal"]),
                    representative_temperature_k=float(raw["representative_temperature_k"]),
                    partition=DmaPartition(str(raw["partition"])),
                    is_reference=bool(raw["is_reference"]),
                    exclusion_reason=None
                    if raw["exclusion_reason"] is None
                    else str(raw["exclusion_reason"]),
                    holdout_evaluation_status=None
                    if raw["holdout_evaluation_status"] is None
                    else str(raw["holdout_evaluation_status"]),
                    source_ordinals=_tuple_int(raw["source_ordinals"], "source_ordinals"),
                    measured_temperature_k=_tuple_float(
                        raw["measured_temperature_k"], "measured_temperature_k"
                    ),
                    source_frequency_hz=_tuple_float(
                        raw["source_frequency_hz"], "source_frequency_hz"
                    ),
                    angular_frequency_rad_per_s=_tuple_float(
                        raw["angular_frequency_rad_per_s"], "angular_frequency_rad_per_s"
                    ),
                    storage_modulus_pa=_tuple_float(
                        raw["storage_modulus_pa"], "storage_modulus_pa"
                    ),
                    loss_modulus_pa=_tuple_float(raw["loss_modulus_pa"], "loss_modulus_pa"),
                    source_tan_delta=_tuple_optional_float(
                        raw["source_tan_delta"], "source_tan_delta"
                    ),
                    loss_modulus_origin=_tuple_string(
                        raw["loss_modulus_origin"], "loss_modulus_origin"
                    ),
                    reduced_angular_frequency_rad_per_s=None
                    if raw["reduced_angular_frequency_rad_per_s"] is None
                    else _tuple_float(
                        raw["reduced_angular_frequency_rad_per_s"],
                        "reduced_angular_frequency_rad_per_s",
                    ),
                    raw_angular_frequency_min_rad_per_s=float(
                        raw["raw_angular_frequency_min_rad_per_s"]
                    ),
                    raw_angular_frequency_max_rad_per_s=float(
                        raw["raw_angular_frequency_max_rad_per_s"]
                    ),
                    shifted_angular_frequency_min_rad_per_s=_optional_float(
                        raw["shifted_angular_frequency_min_rad_per_s"]
                    ),
                    shifted_angular_frequency_max_rad_per_s=_optional_float(
                        raw["shifted_angular_frequency_max_rad_per_s"]
                    ),
                    comparison_sweep_ordinal=None
                    if raw["comparison_sweep_ordinal"] is None
                    else int(raw["comparison_sweep_ordinal"]),
                    observed_log10_a_t=_optional_float(raw["observed_log10_a_t"]),
                    applied_log10_a_t=_optional_float(raw["applied_log10_a_t"]),
                    shift_factor=_optional_float(raw["shift_factor"]),
                    shift_residual_log10_a_t=_optional_float(raw["shift_residual_log10_a_t"]),
                    overlap_log10_reduced_angular_frequency_min=_optional_float(
                        raw["overlap_log10_reduced_angular_frequency_min"]
                    ),
                    overlap_log10_reduced_angular_frequency_max=_optional_float(
                        raw["overlap_log10_reduced_angular_frequency_max"]
                    ),
                    scoring_point_count=None
                    if raw["scoring_point_count"] is None
                    else int(raw["scoring_point_count"]),
                    storage_mse=_optional_float(raw["storage_mse"]),
                    loss_mse=_optional_float(raw["loss_mse"]),
                    storage_rmse=_optional_float(raw["storage_rmse"]),
                    loss_rmse=_optional_float(raw["loss_rmse"]),
                    weighted_mse=_optional_float(raw["weighted_mse"]),
                    adjacent_success=None
                    if raw["adjacent_success"] is None
                    else bool(raw["adjacent_success"]),
                    adjacent_status=None
                    if raw["adjacent_status"] is None
                    else int(raw["adjacent_status"]),
                    adjacent_iterations=None
                    if raw["adjacent_iterations"] is None
                    else int(raw["adjacent_iterations"]),
                    adjacent_evaluations=None
                    if raw["adjacent_evaluations"] is None
                    else int(raw["adjacent_evaluations"]),
                    adjacent_objective=_optional_float(raw["adjacent_objective"]),
                )
            except DmaProcessingError:
                raise
            except Exception as error:
                raise _read_failure(
                    "result row cannot be decoded with the current schema"
                ) from error
            _validate_row_semantics(row)
            rows.append(row)
        return _validate_collection(rows)
    except DmaProcessingError:
        raise
    except Exception as error:
        raise _read_failure(
            "result Parquet cannot be decoded with the exact current schema"
        ) from error


def validate_options_against_rows(
    options: object, rows: Sequence[DmaFrequencyMasterCurveRow]
) -> None:
    """Validate the immutable ProcessingStep evidence against decoded rows.

    This is intentionally narrow and deterministic; it does not recompute or mutate a
    result.  Application/reload code uses it before exposing the parsed output.
    """

    if not isinstance(options, dict):
        raise _read_failure("DMA ProcessingStep options are not an object")
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
        "assessment",
        "warnings",
    }
    if set(options) != required:
        raise _read_failure("DMA ProcessingStep options do not have the exact required keys")
    frozen = _validate_collection(rows)
    mode = frozen[0].input_mode
    if options["input_mode"] != mode or (
        isinstance(options["result_row_count"], bool)
        or not isinstance(options["result_row_count"], int)
        or options["result_row_count"] != len(frozen)
    ):
        raise _read_failure("DMA ProcessingStep options disagree with result rows")
    source_artifact_id = options["source_normalized_artifact_id"]
    try:
        parsed_source_artifact_id = UUID(source_artifact_id)
    except (ValueError, AttributeError, TypeError) as error:
        raise _read_failure("DMA source normalized Artifact identity is invalid") from error
    if (
        not isinstance(source_artifact_id, str)
        or str(parsed_source_artifact_id) != source_artifact_id
    ):
        raise _read_failure("DMA source normalized Artifact identity is not canonical")
    if parsed_source_artifact_id.int == 0:
        raise _read_failure("DMA source normalized Artifact identity is empty")
    source_digest = options["source_normalized_artifact_sha256"]
    if (
        not isinstance(source_digest, str)
        or len(source_digest) != 64
        or any(character not in "0123456789abcdef" for character in source_digest)
    ):
        raise _read_failure("DMA source normalized Artifact digest is invalid")
    if (
        options["frequency_conversion"] != "omega_rad_per_s=2*pi*frequency_hz"
        or options["shift_direction"] != "omega_reduced=omega*10**log10_a_t"
        or options["log_base"] != 10
    ):
        raise _read_failure("DMA ProcessingStep frequency or shift convention is invalid")
    if options["warnings"] != [
        "DMA_TTS_LVR_EVIDENCE_MISSING",
        "DMA_TTS_TEMPERATURE_EQUILIBRIUM_EVIDENCE_MISSING",
        "DMA_TTS_PRECONDITIONING_EVIDENCE_MISSING",
    ]:
        raise _read_failure("DMA ProcessingStep warnings are not in the governed order")
    assessment = options["assessment"]
    if assessment != {
        "adequacy": "not_assessed",
        "uncertainty": "not_provided",
        "identifiability": "not_assessed",
        "production_readiness": "non_production",
    }:
        raise _read_failure("DMA ProcessingStep assessment is invalid")
    reference = options["reference"]
    if not isinstance(reference, dict) or set(reference) != {
        "source_sweep_ordinal",
        "source_ordinal",
        "representative_temperature_k",
    }:
        raise _read_failure("DMA ProcessingStep reference object is not exact")
    reference_row = next(row for row in frozen if row.is_reference)
    expected_reference = {
        "source_sweep_ordinal": reference_row.source_sweep_ordinal,
        "source_ordinal": reference_row.source_ordinals[0]
        if reference_row.source_sweep_ordinal is None
        else None,
        "representative_temperature_k": reference_row.representative_temperature_k,
    }
    if reference != expected_reference:
        raise _read_failure("DMA ProcessingStep reference does not match the result")
    shift_law = options["shift_law"]
    if not isinstance(shift_law, dict):
        raise _read_failure("DMA shift-law evidence is not an object")
    if shift_law.get("reference_temperature_k") != reference_row.representative_temperature_k:
        raise _read_failure("DMA shift-law reference does not match the reference row")
    if shift_law.get("parameter_source") not in {"supplied", "fitted"}:
        raise _read_failure("DMA shift-law parameter source is invalid")

    def number(value: object, name: str) -> float:
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(float(value))
        ):
            raise _read_failure(f"DMA {name} is not finite")
        return float(value)

    def mapping(value: object, name: str) -> dict[str, object]:
        if not isinstance(value, dict):
            raise _read_failure(f"DMA {name} is not an object")
        return value

    def exact_keys(value: dict[str, object], keys: set[str], name: str) -> None:
        if set(value) != keys:
            raise _read_failure(f"DMA {name} does not have the exact current keys")

    def close(actual: object, expected: float, name: str) -> None:
        if not math.isclose(number(actual, name), expected, rel_tol=1e-12, abs_tol=1e-12):
            raise _read_failure(f"DMA {name} does not match result evidence")

    def finite_number_list(value: object, name: str) -> list[float]:
        if not isinstance(value, list) or not value:
            raise _read_failure(f"DMA {name} is not a nonempty numeric list")
        result = [number(item, name) for item in value]
        return result

    if mode == DmaInputMode.FIXED_FREQUENCY_TEMPERATURE_SWEEP.value:
        fixed_kind = shift_law.get("kind")
        if shift_law.get("parameter_source") != "supplied" or fixed_kind not in {
            "manual_tabulated",
            "wlf",
            "arrhenius",
        }:
            raise _read_failure(
                "fixed DMA shift-law evidence is not supplied current-contract data"
            )
        if (
            options["scoring"] is not None
            or options["adjacent_optimizer"] is not None
            or options["law_optimizer"] is not None
            or options["residual_summary"] is not None
            or options["application_range"] is not None
        ):
            raise _read_failure("fixed DMA result contains multi-frequency options")
        if fixed_kind == "manual_tabulated":
            exact_keys(
                shift_law,
                {
                    "kind",
                    "reference_temperature_k",
                    "parameter_source",
                    "manual_table",
                },
                "fixed manual shift law",
            )
            table = shift_law.get("manual_table")
            if not isinstance(table, list) or any(
                not isinstance(item, dict) or set(item) != {"temperature_k", "log10_a_t"}
                for item in table
            ):
                raise _read_failure("fixed manual shift table is not exact")
            table_values = [
                (
                    number(item["temperature_k"], "fixed manual temperature"),
                    number(item["log10_a_t"], "fixed manual shift"),
                )
                for item in table
            ]
            included_temperatures = tuple(
                row.representative_temperature_k
                for row in frozen
                if row.partition is not DmaPartition.EXCLUDED
            )
            if len({temperature for temperature, _ in table_values}) != len(table_values) or {
                temperature for temperature, _ in table_values
            } != set(included_temperatures):
                raise _read_failure("fixed manual shift table does not cover included rows exactly")
            reference_entry = next(
                (
                    shift
                    for temperature, shift in table_values
                    if temperature == reference_row.representative_temperature_k
                ),
                None,
            )
            if reference_entry != 0.0:
                raise _read_failure("fixed manual shift table reference value is not exact zero")
        elif fixed_kind == "wlf":
            exact_keys(
                shift_law,
                {
                    "kind",
                    "reference_temperature_k",
                    "parameter_source",
                    "c1",
                    "c2_k",
                },
                "fixed WLF shift law",
            )
            number(shift_law.get("c1"), "WLF c1")
            if number(shift_law.get("c2_k"), "WLF c2_k") <= 0:
                raise _read_failure("fixed WLF c2_k is not positive")
        else:
            exact_keys(
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
            number(shift_law.get("activation_energy_j_per_mol"), "Arrhenius activation energy")
            if (
                number(shift_law.get("activation_energy_j_per_mol"), "Arrhenius activation energy")
                <= 0
                or number(shift_law.get("gas_constant_j_per_mol_k"), "Arrhenius gas constant")
                != UNIVERSAL_GAS_CONSTANT_J_PER_MOL_K
            ):
                raise _read_failure("fixed Arrhenius law constants are not governed")
    else:
        scoring = mapping(options["scoring"], "scoring evidence")
        exact_keys(
            scoring,
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
        ):
            raise _read_failure("multi-frequency scorer evidence is not exact")
        minimum_overlap = number(scoring["minimum_overlap_decades"], "minimum overlap")
        scoring_count = scoring["scoring_point_count"]
        if (
            minimum_overlap <= 0
            or isinstance(scoring_count, bool)
            or not isinstance(scoring_count, int)
            or not 2 <= scoring_count <= 10_001
        ):
            raise _read_failure("multi-frequency scorer controls are invalid")
        storage_weight = number(scoring["storage_weight"], "storage weight")
        loss_weight = number(scoring["loss_weight"], "loss weight")
        if storage_weight < 0 or loss_weight < 0 or storage_weight + loss_weight != 1.0:
            raise _read_failure("multi-frequency scorer weights are invalid")
        adjacent = mapping(options["adjacent_optimizer"], "adjacent optimizer evidence")
        exact_keys(
            adjacent,
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
        ):
            raise _read_failure("multi-frequency adjacent optimizer evidence is not exact")
        lower = number(adjacent["relative_shift_lower_bound_log10"], "adjacent lower bound")
        upper = number(adjacent["relative_shift_upper_bound_log10"], "adjacent upper bound")
        if lower > upper or adjacent["xatol"] != 1e-10 or adjacent["maxiter"] != 1000:
            raise _read_failure("multi-frequency adjacent optimizer controls are invalid")
        evidence = adjacent["evidence"]
        if not isinstance(evidence, list) or len(evidence) != sum(
            row.partition is DmaPartition.CALIBRATION and not row.is_reference for row in frozen
        ):
            raise _read_failure("multi-frequency adjacent evidence is not a list")
        multi_kind = shift_law.get("kind")
        if multi_kind not in {"manual_tabulated", "wlf_fit", "arrhenius_fit"}:
            raise _read_failure("multi-frequency shift-law kind is invalid")
        if multi_kind == "manual_tabulated":
            exact_keys(
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
                raise _read_failure("manual multi-frequency shift law has invalid fit evidence")
            table = shift_law.get("manual_table")
            if (
                not isinstance(table, list)
                or not table
                or any(
                    not isinstance(item, dict) or set(item) != {"temperature_k", "log10_a_t"}
                    for item in table
                )
            ):
                raise _read_failure("manual multi-frequency shift table is missing")
            table_values = [
                (
                    number(item["temperature_k"], "manual shift temperature"),
                    number(item["log10_a_t"], "manual shift"),
                )
                for item in table
            ]
            nonexcluded_temperatures = tuple(
                row.representative_temperature_k
                for row in frozen
                if row.partition is not DmaPartition.EXCLUDED
            )
            if len({temperature for temperature, _ in table_values}) != len(table_values) or {
                temperature for temperature, _ in table_values
            } != set(nonexcluded_temperatures):
                raise _read_failure(
                    "manual multi-frequency shift table does not cover nonexcluded rows exactly"
                )
            if (
                next(
                    shift
                    for temperature, shift in table_values
                    if temperature == reference_row.representative_temperature_k
                )
                != 0.0
            ):
                raise _read_failure("manual multi-frequency reference shift is not exact zero")
        else:
            fitted_key = "c1" if multi_kind == "wlf_fit" else "activation_energy_j_per_mol"
            second_key = "c2_k" if multi_kind == "wlf_fit" else "gas_constant_j_per_mol_k"
            exact_keys(
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
                raise _read_failure("fitted multi-frequency shift law is not marked fitted")
            fitted = finite_number_list(shift_law.get("fitted_parameters"), "fitted parameters")
            starts = finite_number_list(shift_law.get("initial_parameters"), "initial parameters")
            lower_bounds = finite_number_list(shift_law.get("lower_bounds"), "lower bounds")
            upper_bounds = finite_number_list(shift_law.get("upper_bounds"), "upper bounds")
            expected_parameter_count = 2 if multi_kind == "wlf_fit" else 1
            if (
                not len(fitted)
                == len(starts)
                == len(lower_bounds)
                == len(upper_bounds)
                == expected_parameter_count
                or any(value <= 0 for value in (*fitted, *starts, *lower_bounds, *upper_bounds))
                or any(
                    lower_value >= initial or initial >= upper_value
                    for initial, lower_value, upper_value in zip(
                        starts, lower_bounds, upper_bounds, strict=True
                    )
                )
            ):
                raise _read_failure("fitted multi-frequency shift-law vectors are invalid")
            if multi_kind == "wlf_fit":
                close(shift_law["c1"], fitted[0], "WLF c1")
                if number(shift_law["c2_k"], "WLF c2_k") <= 0:
                    raise _read_failure("WLF c2_k is not positive")
                close(shift_law["c2_k"], fitted[1], "WLF c2_k")
            elif (
                number(shift_law["activation_energy_j_per_mol"], "Arrhenius activation energy") <= 0
            ):
                raise _read_failure("Arrhenius activation energy is not positive")
            else:
                if (
                    number(shift_law["gas_constant_j_per_mol_k"], "Arrhenius gas constant")
                    != UNIVERSAL_GAS_CONSTANT_J_PER_MOL_K
                ):
                    raise _read_failure("Arrhenius gas constant is not the governed fixed value")
                close(
                    shift_law["activation_energy_j_per_mol"],
                    fitted[0],
                    "Arrhenius activation energy",
                )
            if options["law_optimizer"] is None:
                raise _read_failure("fitted multi-frequency shift law has no optimizer evidence")
            law_optimizer = mapping(options["law_optimizer"], "law optimizer evidence")
            required_law_keys = {
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
            }
            if (
                set(law_optimizer) != required_law_keys
                or law_optimizer["optimizer_id"]
                != "cmp.dma_tts.shift_law_log10_least_squares.scipy_trf@1.0.0"
                or law_optimizer["method"] != "least_squares"
                or law_optimizer["method_variant"] != "trf"
                or law_optimizer["seed"] is not None
                or law_optimizer["ftol"] != 1e-12
                or law_optimizer["xtol"] != 1e-12
                or law_optimizer["gtol"] != 1e-12
                or law_optimizer["max_nfev"] != 5000
                or law_optimizer["initial_parameters"] != starts
                or law_optimizer["lower_bounds"] != lower_bounds
                or law_optimizer["upper_bounds"] != upper_bounds
            ):
                raise _read_failure("multi-frequency law optimizer evidence is not exact")
            if law_optimizer["success"] is not True or any(
                not isinstance(value, (int, float))
                or isinstance(value, bool)
                or not math.isfinite(float(value))
                for value in (
                    law_optimizer["cost"],
                    law_optimizer["optimality"],
                    law_optimizer["objective_mse"],
                )
            ):
                raise _read_failure("multi-frequency law optimizer outcome is invalid")
        per_temperature = shift_law.get("per_temperature")
        nonexcluded_rows = tuple(
            row for row in frozen if row.partition is not DmaPartition.EXCLUDED
        )
        if not isinstance(per_temperature, list) or len(per_temperature) != len(nonexcluded_rows):
            raise _read_failure("multi-frequency per-temperature law evidence is incomplete")
        seen_temperatures: set[int] = set()
        rows_by_sweep = {cast(int, row.source_sweep_ordinal): row for row in nonexcluded_rows}
        for item in per_temperature:
            item_map = mapping(item, "per-temperature law evidence")
            exact_keys(
                item_map,
                {
                    "source_sweep_ordinal",
                    "representative_temperature_k",
                    "observed_log10_a_t",
                    "applied_log10_a_t",
                    "shift_residual_log10_a_t",
                },
                "per-temperature law evidence",
            )
            source_sweep = item_map["source_sweep_ordinal"]
            if (
                isinstance(source_sweep, bool)
                or not isinstance(source_sweep, int)
                or source_sweep in seen_temperatures
                or source_sweep not in rows_by_sweep
            ):
                raise _read_failure(
                    "per-temperature law evidence has an invalid source sweep identity"
                )
            seen_temperatures.add(source_sweep)
            row = rows_by_sweep[source_sweep]
            if item_map["representative_temperature_k"] != row.representative_temperature_k:
                raise _read_failure(
                    "per-temperature law evidence has an invalid representative temperature"
                )
            for field_name in (
                "observed_log10_a_t",
                "applied_log10_a_t",
                "shift_residual_log10_a_t",
            ):
                actual = item_map[field_name]
                expected = getattr(row, field_name)
                if expected is None:
                    if actual is not None:
                        raise _read_failure(
                            "per-temperature law evidence has an invalid null pattern"
                        )
                elif not math.isclose(
                    number(actual, field_name), expected, rel_tol=1e-12, abs_tol=1e-12
                ):
                    raise _read_failure("per-temperature law evidence does not match result rows")
        if seen_temperatures != set(rows_by_sweep):
            raise _read_failure(
                "per-temperature law evidence does not cover every nonexcluded sweep"
            )

        def validate_adjacent_evidence(value: object, name: str) -> None:
            if not isinstance(value, list) or len(value) != len(evidence):
                raise _read_failure(f"{name} is incomplete")
            expected_rows = tuple(
                sorted(
                    (
                        row
                        for row in frozen
                        if row.partition is DmaPartition.CALIBRATION and not row.is_reference
                    ),
                    key=lambda row: cast(int, row.source_sweep_ordinal),
                )
            )
            seen: set[int] = set()
            for item, row in zip(value, expected_rows, strict=True):
                item_map = mapping(item, name)
                exact_keys(
                    item_map,
                    {
                        "source_sweep_ordinal",
                        "comparison_sweep_ordinal",
                        "relative_observed_log10_shift",
                        "score",
                        "evidence",
                    },
                    name,
                )
                source_sweep = item_map["source_sweep_ordinal"]
                comparison = item_map["comparison_sweep_ordinal"]
                if (
                    isinstance(source_sweep, bool)
                    or not isinstance(source_sweep, int)
                    or source_sweep in seen
                    or source_sweep != row.source_sweep_ordinal
                    or isinstance(comparison, bool)
                    or not isinstance(comparison, int)
                    or comparison != row.comparison_sweep_ordinal
                ):
                    raise _read_failure(f"{name} has an invalid adjacent identity")
                seen.add(source_sweep)
                anchor = next(
                    (
                        candidate
                        for candidate in frozen
                        if candidate.source_sweep_ordinal == comparison
                    ),
                    None,
                )
                if (
                    anchor is None
                    or anchor.observed_log10_a_t is None
                    or row.observed_log10_a_t is None
                ):
                    raise _read_failure(f"{name} is missing its resolved adjacent anchor")
                close(
                    item_map["relative_observed_log10_shift"],
                    row.observed_log10_a_t - anchor.observed_log10_a_t,
                    f"{name} relative shift",
                )
                score = mapping(item_map["score"], f"{name} score")
                exact_keys(
                    score,
                    {
                        "overlap_min_log10_reduced_omega",
                        "overlap_max_log10_reduced_omega",
                        "storage_mse",
                        "loss_mse",
                        "weighted_mse",
                    },
                    f"{name} score",
                )
                for field_name in (
                    "overlap_min_log10_reduced_omega",
                    "overlap_max_log10_reduced_omega",
                    "storage_mse",
                    "loss_mse",
                    "weighted_mse",
                ):
                    close(score[field_name], getattr(row, field_name), f"{name} {field_name}")
                outcome = mapping(item_map["evidence"], f"{name} optimizer outcome")
                exact_keys(
                    outcome,
                    {"success", "status", "iterations", "evaluations", "objective"},
                    f"{name} optimizer outcome",
                )
                if outcome["success"] is not True:
                    raise _read_failure(f"{name} optimizer outcome is unsuccessful")
                for field_name, expected in (
                    ("status", row.adjacent_status),
                    ("iterations", row.adjacent_iterations),
                    ("evaluations", row.adjacent_evaluations),
                ):
                    if outcome[field_name] != expected:
                        raise _read_failure(f"{name} optimizer outcome does not match result rows")
                if row.adjacent_objective is None:
                    raise _read_failure(f"{name} is missing its objective")
                close(outcome["objective"], row.adjacent_objective, f"{name} objective")
            if seen != {cast(int, row.source_sweep_ordinal) for row in expected_rows}:
                raise _read_failure(f"{name} does not cover every calibration comparison")

        validate_adjacent_evidence(evidence, "adjacent optimizer evidence")
        if shift_law["adjacent_observed"] != evidence:
            raise _read_failure("shift-law adjacent evidence does not match optimizer evidence")
        residual_summary = mapping(options["residual_summary"], "residual summary")
        calibration_rows = tuple(
            row
            for row in frozen
            if row.partition is DmaPartition.CALIBRATION and not row.is_reference
        )
        exact_keys(
            residual_summary,
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
            residual_summary["calibration_comparison_count"] != len(calibration_rows)
            or residual_summary["units"] != "log10(modulus) and log10(aT)"
            or residual_summary["holdout_evaluation_separate"] is not True
        ):
            raise _read_failure("multi-frequency residual summary is not exact")
        calibration_metrics: list[tuple[float, float, float]] = []
        for row in calibration_rows:
            if row.storage_mse is None or row.loss_mse is None or row.weighted_mse is None:
                raise _read_failure("calibration result rows are missing residual metrics")
            calibration_metrics.append((row.storage_mse, row.loss_mse, row.weighted_mse))
        expected_storage = sum(item[0] for item in calibration_metrics) / len(calibration_rows)
        expected_loss = sum(item[1] for item in calibration_metrics) / len(calibration_rows)
        expected_weighted = sum(item[2] for item in calibration_metrics) / len(calibration_rows)
        if residual_summary["calibration_comparison_count"] < 1:
            raise _read_failure("multi-frequency residual summary has no calibration comparisons")
        if (
            not math.isclose(
                number(residual_summary["storage_mse"], "residual storage MSE"),
                expected_storage,
                rel_tol=1e-12,
                abs_tol=1e-12,
            )
            or not math.isclose(
                number(residual_summary["loss_mse"], "residual loss MSE"),
                expected_loss,
                rel_tol=1e-12,
                abs_tol=1e-12,
            )
            or not math.isclose(
                number(residual_summary["storage_rmse"], "residual storage RMSE"),
                math.sqrt(expected_storage),
                rel_tol=1e-12,
                abs_tol=1e-12,
            )
            or not math.isclose(
                number(residual_summary["loss_rmse"], "residual loss RMSE"),
                math.sqrt(expected_loss),
                rel_tol=1e-12,
                abs_tol=1e-12,
            )
            or not math.isclose(
                number(residual_summary["weighted_mse"], "residual weighted MSE"),
                expected_weighted,
                rel_tol=1e-12,
                abs_tol=1e-12,
            )
        ):
            raise _read_failure("multi-frequency residual summary does not match result evidence")

    if mode == DmaInputMode.MULTI_FREQUENCY_ISOTHERMS.value:
        application_range = options["application_range"]
        if not isinstance(application_range, dict) or set(application_range) != {
            "basis",
            "holdout_included",
            "reduced_angular_frequency_intervals_rad_per_s",
            "calibration_temperature_interval_k",
        }:
            raise _read_failure("multi-frequency application range is not exact")
        if (
            application_range["basis"] != "at_least_two_shifted_calibration_isotherms"
            or application_range["holdout_included"] is not False
        ):
            raise _read_failure("multi-frequency application range basis is invalid")
        intervals = application_range["reduced_angular_frequency_intervals_rad_per_s"]
        if not isinstance(intervals, list) or not intervals:
            raise _read_failure("multi-frequency application range intervals are missing")
        actual_intervals: list[tuple[float, float]] = []
        previous_max = 0.0
        for item in intervals:
            item_map = mapping(item, "application interval")
            if set(item_map) != {"minimum", "maximum"}:
                raise _read_failure("application interval fields are not exact")
            minimum = number(item_map["minimum"], "application interval minimum")
            maximum = number(item_map["maximum"], "application interval maximum")
            if minimum <= 0 or maximum <= minimum or minimum <= previous_max:
                raise _read_failure("application intervals are not sorted, closed, and merged")
            actual_intervals.append((minimum, maximum))
            previous_max = maximum
        shifted_ranges = [
            (
                cast(float, row.shifted_angular_frequency_min_rad_per_s),
                cast(float, row.shifted_angular_frequency_max_rad_per_s),
            )
            for row in frozen
            if row.partition is DmaPartition.CALIBRATION
        ]
        endpoints = sorted(
            {endpoint for start, finish in shifted_ranges for endpoint in (start, finish)}
        )
        expected_intervals: list[tuple[float, float]] = []
        for left, right in pairwise(endpoints):
            if (
                right <= left
                or sum(start <= left and right <= finish for start, finish in shifted_ranges) < 2
            ):
                continue
            if expected_intervals and expected_intervals[-1][1] == left:
                expected_intervals[-1] = (expected_intervals[-1][0], right)
            else:
                expected_intervals.append((left, right))
        if len(actual_intervals) != len(expected_intervals) or any(
            not math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-12)
            for actual_pair, expected_pair in zip(actual_intervals, expected_intervals, strict=True)
            for actual, expected in zip(actual_pair, expected_pair, strict=True)
        ):
            raise _read_failure(
                "multi-frequency application intervals do not match shifted calibration ranges"
            )
        temperature_interval = mapping(
            application_range["calibration_temperature_interval_k"],
            "calibration temperature interval",
        )
        if set(temperature_interval) != {"minimum", "maximum"}:
            raise _read_failure("calibration temperature interval fields are not exact")
        calibration_temperatures = tuple(
            row.representative_temperature_k
            for row in frozen
            if row.partition is DmaPartition.CALIBRATION
        )
        minimum_temperature = number(
            temperature_interval["minimum"], "calibration temperature minimum"
        )
        maximum_temperature = number(
            temperature_interval["maximum"], "calibration temperature maximum"
        )
        if (
            minimum_temperature != min(calibration_temperatures)
            or maximum_temperature != max(calibration_temperatures)
            or maximum_temperature < minimum_temperature
        ):
            raise _read_failure("calibration temperature interval does not match result rows")
    elif options["application_range"] is not None:
        raise _read_failure("fixed DMA result contains an application range")

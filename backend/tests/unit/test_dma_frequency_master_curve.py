from __future__ import annotations

import importlib.util
import json
import math
from collections.abc import Callable
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from types import ModuleType
from typing import cast

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from cmp.modules.processing.domain.dma_frequency_master_curve import (
    DMA_FREQUENCY_MASTER_CURVE_COLUMNS,
    DMA_LOSS_MODULUS_COLUMNS,
    DMA_SWEEP_TEMPERATURE_TOLERANCE_K,
    ArrheniusShiftLaw,
    DmaFrequencyMasterCurveBuildResult,
    DmaPartition,
    DmaProcessingError,
    DmaRowDisposition,
    DmaTemperatureSweepRow,
    TabulatedShiftLaw,
    WlfShiftLaw,
    build_frequency_master_curve,
    derive_loss_modulus,
    frequency_master_curve_from_parquet,
    frequency_master_curve_parquet_bytes,
    loss_modulus_from_parquet,
    loss_modulus_parquet_bytes,
    recommend_wlf_starting_values,
)
from cmp.modules.processing.domain.dma_multi_frequency_tts import (
    DmaFrequencySweep,
    DmaFrequencySweepDisposition,
    DmaFrequencySweepPoint,
    DmaShiftLawRequest,
    DmaTtsAdjacentOptimizerControls,
    DmaTtsScoringControls,
    build_multi_frequency_master_curve,
    optimize_adjacent_shift,
    score_sweep_pair,
)

ROOT = Path(__file__).parents[3]
ORACLE_PATH = ROOT / "tests/fixtures/linear_viscoelastic/dma_temperature_shift_oracle.py"
_oracle_spec = importlib.util.spec_from_file_location(
    "dma_temperature_shift_decimal_oracle", ORACLE_PATH
)
assert _oracle_spec is not None and _oracle_spec.loader is not None
_oracle: ModuleType = importlib.util.module_from_spec(_oracle_spec)
_oracle_spec.loader.exec_module(_oracle)
angular_frequency = _oracle.angular_frequency
arrhenius_log10_shift = _oracle.arrhenius_log10_shift
loss_modulus = _oracle.loss_modulus
generalized_maxwell_loss = _oracle.generalized_maxwell_loss
generalized_maxwell_storage = _oracle.generalized_maxwell_storage
reduced_angular_frequency = _oracle.reduced_angular_frequency
wlf_log10_shift = _oracle.wlf_log10_shift

DMA_TTS_REFERENCE_PATH = (
    ROOT / "fixtures/synthetic/dma-temperature-sweep-linear-viscoelastic-v1.json"
)
DMA_TTS_WLF_UI_REFERENCE_PATH = ROOT / "fixtures/synthetic/dma-temperature-sweep-wlf-ui-v1.json"
_read_parquet = cast(Callable[..., pa.Table], pq.read_table)
_write_parquet = cast(Callable[..., None], pq.write_table)


def _rows() -> tuple[DmaTemperatureSweepRow, ...]:
    return (
        DmaTemperatureSweepRow(0, 293.15, 1.0, 1_200_000.0, tan_delta=0.10),
        DmaTemperatureSweepRow(1, 303.15, 1.0, 1_000_000.0, tan_delta=0.25),
        DmaTemperatureSweepRow(2, 313.15, 1.0, 800_000.0, tan_delta=0.50),
        DmaTemperatureSweepRow(3, 323.15, 1.0, 620_000.0, tan_delta=0.30),
        DmaTemperatureSweepRow(4, 333.15, 1.0, 500_000.0, tan_delta=-0.02),
    )


def _dispositions() -> tuple[DmaRowDisposition, ...]:
    return (
        DmaRowDisposition(0, DmaPartition.CALIBRATION),
        DmaRowDisposition(1, DmaPartition.CALIBRATION),
        DmaRowDisposition(2, DmaPartition.CALIBRATION),
        DmaRowDisposition(3, DmaPartition.HOLDOUT),
        DmaRowDisposition(4, DmaPartition.EXCLUDED, "nonpositive_derived_loss_modulus"),
    )


def test_fixture_backed_temperature_sweep_matches_independent_decimal_oracle() -> None:
    reference = json.loads(DMA_TTS_REFERENCE_PATH.read_bytes())
    source = reference["input"]
    rows = source["rows"]
    frequency_hz = source["frequency"]["value"]
    result = build_frequency_master_curve(
        tuple(
            DmaTemperatureSweepRow(
                int(row["source_ordinal"]),
                float(row["temperature_k"]),
                float(frequency_hz),
                float(row["storage_modulus_pa"]),
                loss_modulus_pa=float(row["loss_modulus_pa"]),
            )
            for row in rows
        ),
        tuple(
            DmaRowDisposition(int(row["source_ordinal"]), DmaPartition(row["partition"]))
            for row in rows
        ),
        TabulatedShiftLaw(
            float(source["shift_law"]["reference_temperature_k"]),
            tuple((float(row["temperature_k"]), float(row["log10_a_t"])) for row in rows),
        ),
        confirmed=True,
        confirmation_reason="Use the exact fixture-declared tabulated shifts",
    )
    truth = reference["closed_form_truth"]
    terms = tuple((item["g_i_pa"], item["tau_i_s"]) for item in truth["terms"])
    tolerance = float(reference["acceptance_tolerances"]["master_curve_relative"])

    for row, actual in zip(rows, result, strict=True):
        expected_omega = reduced_angular_frequency(frequency_hz, Decimal(row["log10_a_t"]))
        expected_storage = generalized_maxwell_storage(truth["g_inf_pa"], terms, expected_omega)
        expected_loss = generalized_maxwell_loss(terms, expected_omega)
        assert math.isclose(
            (actual.reduced_angular_frequency_rad_per_s or (0.0,))[0],
            float(expected_omega),
            rel_tol=tolerance,
        )
        assert math.isclose(
            actual.storage_modulus_pa[0], float(expected_storage), rel_tol=tolerance
        )
        assert math.isclose(actual.loss_modulus_pa[0], float(expected_loss), rel_tol=tolerance)


def test_ui_fixture_recommendation_creates_its_declared_wlf_master_curve() -> None:
    reference = json.loads(DMA_TTS_WLF_UI_REFERENCE_PATH.read_bytes())
    source = reference["input"]
    source_rows = source["rows"]
    frequency_hz = source["frequency"]["value"]
    rows = tuple(
        DmaTemperatureSweepRow(
            int(row["source_ordinal"]),
            float(row["temperature_k"]),
            float(frequency_hz),
            float(row["storage_modulus_pa"]),
            loss_modulus_pa=float(row["loss_modulus_pa"]),
        )
        for row in source_rows
    )
    recommendation = recommend_wlf_starting_values(rows, source_evidence={"fixture": "wlf-ui"})
    result = build_frequency_master_curve(
        rows,
        tuple(
            DmaRowDisposition(int(row["source_ordinal"]), DmaPartition(row["partition"]))
            for row in source_rows
        ),
        WlfShiftLaw(
            recommendation.reference_temperature_k,
            recommendation.c1,
            recommendation.c2_k,
        ),
        confirmed=True,
        confirmation_reason="Use the server recommendation for this synthetic UI reference.",
    )

    assert recommendation.reference_temperature_k == float(
        source["shift_law"]["reference_temperature_k"]
    )
    tolerance = float(reference["acceptance_tolerances"]["master_curve_relative"])
    for expected, actual in zip(source_rows, result, strict=True):
        assert actual.applied_log10_a_t is not None
        assert math.isclose(
            actual.applied_log10_a_t, float(expected["log10_a_t"]), rel_tol=tolerance
        )
        assert actual.reduced_angular_frequency_rad_per_s is not None
        assert math.isfinite(actual.reduced_angular_frequency_rad_per_s[0])


def test_loss_modulus_derivation_preserves_signed_tan_delta_and_source_order() -> None:
    result = derive_loss_modulus(_rows())

    assert [row.source_ordinal for row in result] == [0, 1, 2, 3, 4]
    assert result[2].loss_modulus_pa == 400_000.0
    assert result[4].tan_delta == -0.02
    assert result[4].loss_modulus_pa == -10_000.0
    expected = loss_modulus("800000", "0.50")
    assert Decimal(str(result[2].loss_modulus_pa)) == expected


def test_loss_modulus_parquet_round_trip_has_exact_columns_and_types() -> None:
    rows = derive_loss_modulus(_rows())
    value = loss_modulus_parquet_bytes(rows)
    table = _read_parquet(pa.BufferReader(value))

    assert tuple(table.column_names) == DMA_LOSS_MODULUS_COLUMNS
    assert table.schema.field("source_ordinal").type == pa.int64()
    assert all(
        table.schema.field(name).type == pa.float64() for name in DMA_LOSS_MODULUS_COLUMNS[1:]
    )
    assert loss_modulus_from_parquet(value) == rows


def test_wlf_recommendation_is_read_only_deterministic_and_not_material_specific() -> None:
    evidence = {
        "test_data_id": "test-data",
        "test_data_revision_id": "revision",
        "test_data_sha256": "a" * 64,
    }
    first = recommend_wlf_starting_values(_rows(), source_evidence=evidence)
    second = recommend_wlf_starting_values(_rows(), source_evidence=evidence)

    assert first == second
    assert first.reference_temperature_k == 313.15
    assert first.source_ordinal == 2
    assert first.c1 == 17.44
    assert first.c2_k == 51.6
    assert first.value_origin == "generic_wlf_at_tg_starting_suggestion"
    assert first.material_specific is False
    assert first.requires_confirmation is True
    assert len(first.recommendation_sha256) == 64


@pytest.mark.parametrize(
    ("rows", "code"),
    [
        (
            tuple(replace(row, tan_delta=-abs(row.loss_factor)) for row in _rows()),
            "CMP-PROCESSING-4301",
        ),
        (
            (
                DmaTemperatureSweepRow(0, 293.15, 1.0, 1.0, tan_delta=0.1),
                DmaTemperatureSweepRow(1, 303.15, 1.0, 1.0, tan_delta=0.5),
                DmaTemperatureSweepRow(2, 313.15, 1.0, 1.0, tan_delta=0.5),
                DmaTemperatureSweepRow(3, 323.15, 1.0, 1.0, tan_delta=0.2),
            ),
            "CMP-PROCESSING-4302",
        ),
        (
            (
                DmaTemperatureSweepRow(0, 293.15, 1.0, 1.0, tan_delta=0.5),
                DmaTemperatureSweepRow(1, 303.15, 1.0, 1.0, tan_delta=0.3),
                DmaTemperatureSweepRow(2, 313.15, 1.0, 1.0, tan_delta=0.1),
            ),
            "CMP-PROCESSING-4303",
        ),
    ],
)
def test_recommendation_rejects_missing_tied_and_endpoint_peaks(
    rows: tuple[DmaTemperatureSweepRow, ...], code: str
) -> None:
    with pytest.raises(DmaProcessingError) as captured:
        recommend_wlf_starting_values(rows, source_evidence={"sha256": "b" * 64})
    assert captured.value.code == code
    assert captured.value.recovery


def test_wlf_master_curve_matches_independent_decimal_reference() -> None:
    law = WlfShiftLaw(reference_temperature_k=313.15, c1=17.44, c2_k=51.6)
    result = build_frequency_master_curve(
        _rows(),
        _dispositions(),
        law,
        confirmed=True,
        confirmation_reason="Engineer accepted WLF starting values.",
    )

    assert [row.source_ordinals[0] for row in result] == [0, 1, 2, 3, 4]
    for row in result[:4]:
        expected_log = wlf_log10_shift(
            str(row.representative_temperature_k), "313.15", "17.44", "51.6"
        )
        expected_omega = angular_frequency("1.0")
        expected_reduced = reduced_angular_frequency("1.0", expected_log)
        assert math.isclose(
            row.angular_frequency_rad_per_s[0], float(expected_omega), rel_tol=1e-15
        )
        assert row.applied_log10_a_t is not None
        assert math.isclose(
            row.applied_log10_a_t, float(expected_log), rel_tol=1e-14, abs_tol=1e-14
        )
        assert row.reduced_angular_frequency_rad_per_s is not None
        assert math.isclose(
            row.reduced_angular_frequency_rad_per_s[0], float(expected_reduced), rel_tol=2e-14
        )
    assert result[2].applied_log10_a_t == 0.0
    assert result[2].shift_factor == 1.0
    assert result[4].partition is DmaPartition.EXCLUDED
    assert result[4].applied_log10_a_t is None
    assert result[4].loss_modulus_pa == (-10_000.0,)


def test_arrhenius_master_curve_matches_independent_decimal_reference() -> None:
    law = ArrheniusShiftLaw(313.15, 85_000.0)
    result = build_frequency_master_curve(
        _rows(),
        _dispositions(),
        law,
        confirmed=True,
        confirmation_reason="Engineer selected Arrhenius.",
    )
    for row in result[:4]:
        expected = arrhenius_log10_shift(str(row.representative_temperature_k), "313.15", "85000")
        assert row.applied_log10_a_t is not None
        assert math.isclose(row.applied_log10_a_t, float(expected), rel_tol=2e-14, abs_tol=1e-14)
    assert result[2].applied_log10_a_t == 0.0


def test_tabulated_factors_require_exact_included_temperature_coverage() -> None:
    factors = TabulatedShiftLaw(
        313.15,
        ((293.15, 2.0), (303.15, 1.0), (313.15, 0.0), (323.15, -1.0)),
    )
    result = build_frequency_master_curve(
        _rows(),
        _dispositions(),
        factors,
        confirmed=True,
        confirmation_reason="Published factors accepted.",
    )
    assert [row.applied_log10_a_t for row in result] == [2.0, 1.0, 0.0, -1.0, None]

    with pytest.raises(DmaProcessingError) as captured:
        build_frequency_master_curve(
            _rows(),
            _dispositions(),
            TabulatedShiftLaw(313.15, ((293.15, 2.0), (303.15, 1.0), (313.15, 0.0))),
            confirmed=True,
            confirmation_reason="incomplete",
        )
    assert captured.value.code == "CMP-PROCESSING-4305"


def test_wlf_domain_is_strict_and_confirmation_is_required() -> None:
    boundary_rows = (
        DmaTemperatureSweepRow(0, 302.0, 1.0, 1_000.0, tan_delta=0.2),
        DmaTemperatureSweepRow(1, 320.0, 1.0, 900.0, tan_delta=0.3),
    )
    dispositions = (
        DmaRowDisposition(0, DmaPartition.CALIBRATION),
        DmaRowDisposition(1, DmaPartition.CALIBRATION),
    )
    law = WlfShiftLaw(320.0, 10.0, 50.0)
    assert build_frequency_master_curve(
        boundary_rows, dispositions, law, confirmed=True, confirmation_reason="boundary check"
    )

    for temperature in (260.0, 259.999999):
        invalid = (replace(boundary_rows[0], temperature_k=temperature), boundary_rows[1])
        with pytest.raises(DmaProcessingError) as captured:
            build_frequency_master_curve(
                invalid, dispositions, law, confirmed=True, confirmation_reason="boundary check"
            )
        assert captured.value.code == "CMP-PROCESSING-4307"

    with pytest.raises(DmaProcessingError) as captured:
        build_frequency_master_curve(
            boundary_rows, dispositions, law, confirmed=False, confirmation_reason=""
        )
    assert captured.value.code == "CMP-PROCESSING-4306"


def test_included_negative_loss_requires_explicit_exclusion() -> None:
    dispositions = list(_dispositions())
    dispositions[-1] = DmaRowDisposition(4, DmaPartition.HOLDOUT)
    with pytest.raises(DmaProcessingError) as captured:
        build_frequency_master_curve(
            _rows(),
            dispositions,
            WlfShiftLaw(313.15, 17.44, 51.6),
            confirmed=True,
            confirmation_reason="check",
        )
    assert "negative usable loss modulus" in captured.value.cause


def test_frequency_master_curve_parquet_round_trip_preserves_excluded_nulls() -> None:
    rows = build_frequency_master_curve(
        _rows(),
        _dispositions(),
        WlfShiftLaw(313.15, 17.44, 51.6),
        confirmed=True,
        confirmation_reason="Engineer accepted WLF settings.",
    )
    value = frequency_master_curve_parquet_bytes(rows)
    table = _read_parquet(pa.BufferReader(value))

    assert tuple(table.column_names) == DMA_FREQUENCY_MASTER_CURVE_COLUMNS
    source_ordinals_field = table.schema.field("source_ordinals")
    assert source_ordinals_field.type.value_type == pa.int64()
    assert source_ordinals_field.type.value_field.nullable is False
    assert table.schema.field("partition").type == pa.string()
    assert table.column("applied_log10_a_t").null_count == 1
    assert frequency_master_curve_from_parquet(value) == rows


def test_nonconstant_frequency_is_rejected_with_recovery() -> None:
    rows = list(_rows())
    rows[2] = replace(rows[2], frequency_hz=2.0)
    with pytest.raises(DmaProcessingError) as captured:
        recommend_wlf_starting_values(rows, source_evidence={"sha256": "c" * 64})
    assert captured.value.code == "CMP-PROCESSING-4304"
    assert "Split" in captured.value.recovery


def _multi_synthetic_sweeps() -> tuple[DmaFrequencySweep, ...]:
    shifts = {11: 0.0, 27: 1.0, 42: 2.0, 99: 3.0}
    temperatures = {11: 300.0, 27: 310.0, 42: 320.0, 99: 330.0}
    frequencies = {
        11: (1.0, 10.0, 100.0),
        27: (1.0, 100.0),
        42: (1.0, 10.0, 100.0),
        99: (1.0, 10.0, 100.0),
    }
    result: list[DmaFrequencySweep] = []
    for sweep_ordinal in (11, 27, 42, 99):
        shift = shifts[sweep_ordinal]
        points = tuple(
            DmaFrequencySweepPoint(
                source_ordinal=(sweep_ordinal * 10) + index,
                measured_temperature_k=temperatures[sweep_ordinal] + (0.01 * index),
                frequency_hz=frequency,
                storage_modulus_pa=10.0 ** (5.0 + 0.2 * (math.log10(frequency) + shift)),
                loss_modulus_pa=10.0 ** (4.0 + 0.1 * (math.log10(frequency) + shift)),
            )
            for index, frequency in enumerate(frequencies[sweep_ordinal])
        )
        result.append(DmaFrequencySweep(sweep_ordinal, points))
    return tuple(result)


def _multi_synthetic_dispositions() -> tuple[DmaFrequencySweepDisposition, ...]:
    return (
        DmaFrequencySweepDisposition(11, 300.0, DmaPartition.CALIBRATION),
        DmaFrequencySweepDisposition(27, 310.0, DmaPartition.CALIBRATION),
        DmaFrequencySweepDisposition(42, 320.0, DmaPartition.CALIBRATION),
        DmaFrequencySweepDisposition(99, 330.0, DmaPartition.HOLDOUT),
    )


def _multi_scoring() -> DmaTtsScoringControls:
    return DmaTtsScoringControls(
        minimum_overlap_decades=0.5,
        overlap_evaluation_point_count=7,
        storage_weight=0.7,
        loss_weight=0.3,
    )


def test_multi_frequency_manual_ragged_result_preserves_identity_and_null_patterns() -> None:
    result = build_multi_frequency_master_curve(
        _multi_synthetic_sweeps(),
        _multi_synthetic_dispositions(),
        reference_sweep_ordinal=11,
        shift_law=DmaShiftLawRequest(
            "manual_tabulated",
            300.0,
            manual_table=((300.0, 0.0), (310.0, 1.0), (320.0, 2.0), (330.0, 3.0)),
        ),
        scoring=_multi_scoring(),
        adjacent_optimizer=DmaTtsAdjacentOptimizerControls(-3.0, 3.0),
        law_optimizer=None,
        confirmed=True,
        confirmation_reason="synthetic domain regression",
    )

    assert [row.source_sweep_ordinal for row in result.rows] == [11, 27, 42, 99]
    assert [len(row.source_frequency_hz) for row in result.rows] == [3, 2, 3, 3]
    assert result.rows[0].is_reference is True
    assert result.rows[0].observed_log10_a_t == 0.0
    assert result.rows[0].comparison_sweep_ordinal is None
    assert result.rows[1].observed_log10_a_t == pytest.approx(1.0)
    assert result.rows[2].observed_log10_a_t == pytest.approx(2.0)
    assert result.rows[3].partition is DmaPartition.HOLDOUT
    assert result.rows[3].holdout_evaluation_status == "evaluated"
    assert result.rows[3].observed_log10_a_t is None
    assert result.rows[3].shift_residual_log10_a_t is None
    assert result.rows[3].adjacent_success is None
    assert result.rows[3].scoring_point_count == 7
    assert result.application_intervals
    assert result.residual_summary is not None


def _multi_sweeps_with_reference_temperature_deviation(
    deviation_k: float,
) -> tuple[DmaFrequencySweep, ...]:
    sweeps = list(_multi_synthetic_sweeps())
    reference = sweeps[0]
    points = list(reference.points)
    points[1] = replace(
        points[1],
        measured_temperature_k=points[0].measured_temperature_k + deviation_k,
    )
    points[2] = replace(
        points[2],
        measured_temperature_k=points[0].measured_temperature_k,
    )
    sweeps[0] = replace(reference, points=tuple(points))
    return tuple(sweeps)


def _build_multi_temperature_boundary(
    sweeps: tuple[DmaFrequencySweep, ...],
) -> DmaFrequencyMasterCurveBuildResult:
    return build_multi_frequency_master_curve(
        sweeps,
        _multi_synthetic_dispositions(),
        reference_sweep_ordinal=11,
        shift_law=DmaShiftLawRequest(
            "manual_tabulated",
            300.0,
            manual_table=((300.0, 0.0), (310.0, 1.0), (320.0, 2.0), (330.0, 3.0)),
        ),
        scoring=_multi_scoring(),
        adjacent_optimizer=DmaTtsAdjacentOptimizerControls(-3.0, 3.0),
        law_optimizer=None,
        confirmed=True,
        confirmation_reason="temperature tolerance boundary regression",
    )


def test_multi_frequency_temperature_tolerance_accepts_inclusive_half_kelvin() -> None:
    assert DMA_SWEEP_TEMPERATURE_TOLERANCE_K == Decimal("0.5")
    result = _build_multi_temperature_boundary(
        _multi_sweeps_with_reference_temperature_deviation(0.5)
    )

    assert result.rows[0].representative_temperature_k == 300.0
    assert result.rows[0].measured_temperature_k == (300.0, 300.5, 300.0)
    assert frequency_master_curve_from_parquet(
        frequency_master_curve_parquet_bytes(result.rows)
    ) == result.rows


def test_multi_frequency_temperature_tolerance_rejects_above_half_kelvin() -> None:
    with pytest.raises(DmaProcessingError) as captured:
        _build_multi_temperature_boundary(
            _multi_sweeps_with_reference_temperature_deviation(0.5000000001)
        )

    assert captured.value.code == "CMP-PROCESSING-4316"
    assert "inclusive 0.5 K sweep tolerance" in captured.value.cause


def test_multi_frequency_result_readback_rejects_temperature_above_half_kelvin() -> None:
    result = _build_multi_temperature_boundary(
        _multi_sweeps_with_reference_temperature_deviation(0.5)
    )
    valid_payload = frequency_master_curve_parquet_bytes(result.rows)
    table = _read_parquet(pa.BufferReader(valid_payload))
    field_index = table.schema.get_field_index("measured_temperature_k")
    field = table.schema.field(field_index)
    tampered_temperatures: list[object] = list(
        table.column("measured_temperature_k").to_pylist()
    )
    tampered_temperatures[0] = [300.0, 300.5000000001, 300.0]
    tampered_table = table.set_column(
        field_index,
        field,
        pa.array(tampered_temperatures, type=field.type),
    )
    sink = pa.BufferOutputStream()
    _write_parquet(tampered_table, sink)
    tampered_payload = sink.getvalue().to_pybytes()
    assert isinstance(tampered_payload, bytes)

    with pytest.raises(DmaProcessingError) as captured:
        frequency_master_curve_from_parquet(tampered_payload)

    assert captured.value.code == "CMP-PROCESSING-4317"
    assert "inclusive 0.5 K sweep tolerance" in captured.value.cause


def test_multi_frequency_singleton_overlap_is_evaluated_without_optimizer() -> None:
    sweeps = (
        DmaFrequencySweep(
            1,
            (
                DmaFrequencySweepPoint(0, 300.0, 1.0, 100.0, 10.0),
                DmaFrequencySweepPoint(1, 300.0, 100.0, 10.0, 1.0),
            ),
        ),
        DmaFrequencySweep(
            2,
            (
                DmaFrequencySweepPoint(2, 310.0, 1.0, 100.0, 10.0),
                DmaFrequencySweepPoint(3, 310.0, 100.0, 10.0, 1.0),
            ),
        ),
    )
    shift, score, evidence = optimize_adjacent_shift(
        sweeps[1],
        sweeps[0],
        DmaTtsScoringControls(0.5, 3, 1.0, 0.0),
        DmaTtsAdjacentOptimizerControls(0.0, 0.0),
    )
    assert shift == 0.0
    assert score.scoring_point_count == 3
    assert evidence == type(evidence)(True, 0, 0, 1, score.weighted_mse)


def test_multi_frequency_empty_feasible_overlap_is_4314() -> None:
    current = DmaFrequencySweep(
        1,
        (
            DmaFrequencySweepPoint(0, 300.0, 1.0, 100.0, 10.0),
            DmaFrequencySweepPoint(1, 300.0, 10.0, 90.0, 9.0),
        ),
    )
    anchor = DmaFrequencySweep(
        2,
        (
            DmaFrequencySweepPoint(2, 310.0, 100.0, 100.0, 10.0),
            DmaFrequencySweepPoint(3, 310.0, 1000.0, 90.0, 9.0),
        ),
    )
    with pytest.raises(DmaProcessingError) as captured:
        score_sweep_pair(current, anchor, 0.0, DmaTtsScoringControls(0.5, 3, 1.0, 0.0))
    assert captured.value.code == "CMP-PROCESSING-4314"

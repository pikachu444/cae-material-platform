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
    ArrheniusShiftLaw,
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
_read_parquet = cast(Callable[..., pa.Table], pq.read_table)


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
            tuple(
                (float(row["temperature_k"]), float(row["log10_a_t"])) for row in rows
            ),
        ),
        confirmed=True,
        confirmation_reason="Use the exact fixture-declared tabulated shifts",
    )
    truth = reference["closed_form_truth"]
    terms = tuple((item["g_i_pa"], item["tau_i_s"]) for item in truth["terms"])
    tolerance = float(reference["acceptance_tolerances"]["master_curve_relative"])

    for row, actual in zip(rows, result, strict=True):
        expected_omega = reduced_angular_frequency(frequency_hz, Decimal(row["log10_a_t"]))
        expected_storage = generalized_maxwell_storage(
            truth["g_inf_pa"], terms, expected_omega
        )
        expected_loss = generalized_maxwell_loss(terms, expected_omega)
        assert math.isclose(
            actual.reduced_angular_frequency_rad_per_s or 0.0,
            float(expected_omega),
            rel_tol=tolerance,
        )
        assert math.isclose(actual.storage_modulus_pa, float(expected_storage), rel_tol=tolerance)
        assert math.isclose(actual.loss_modulus_pa, float(expected_loss), rel_tol=tolerance)


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

    assert [row.source_ordinal for row in result] == [0, 1, 2, 3, 4]
    for row in result[:4]:
        expected_log = wlf_log10_shift(str(row.temperature_k), "313.15", "17.44", "51.6")
        expected_omega = angular_frequency("1.0")
        expected_reduced = reduced_angular_frequency("1.0", expected_log)
        assert math.isclose(row.angular_frequency_rad_per_s, float(expected_omega), rel_tol=1e-15)
        assert row.log10_a_t is not None
        assert math.isclose(row.log10_a_t, float(expected_log), rel_tol=1e-14, abs_tol=1e-14)
        assert row.reduced_angular_frequency_rad_per_s is not None
        assert math.isclose(
            row.reduced_angular_frequency_rad_per_s, float(expected_reduced), rel_tol=2e-14
        )
    assert result[2].log10_a_t == 0.0
    assert result[2].shift_factor == 1.0
    assert result[4].partition is DmaPartition.EXCLUDED
    assert result[4].log10_a_t is None
    assert result[4].loss_modulus_pa == -10_000.0


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
        expected = arrhenius_log10_shift(str(row.temperature_k), "313.15", "85000")
        assert row.log10_a_t is not None
        assert math.isclose(row.log10_a_t, float(expected), rel_tol=2e-14, abs_tol=1e-14)
    assert result[2].log10_a_t == 0.0


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
    assert [row.log10_a_t for row in result] == [2.0, 1.0, 0.0, -1.0, None]

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
    law = WlfShiftLaw(350.0, 10.0, 50.0)
    assert build_frequency_master_curve(
        boundary_rows, dispositions, law, confirmed=True, confirmation_reason="boundary check"
    )

    for temperature in (300.0, 299.999999):
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
    assert table.schema.field("source_ordinal").type == pa.int64()
    assert table.schema.field("partition").type == pa.string()
    assert table.column("log10_a_t").null_count == 1
    assert frequency_master_curve_from_parquet(value) == rows


def test_nonconstant_frequency_is_rejected_with_recovery() -> None:
    rows = list(_rows())
    rows[2] = replace(rows[2], frequency_hz=2.0)
    with pytest.raises(DmaProcessingError) as captured:
        recommend_wlf_starting_values(rows, source_evidence={"sha256": "c" * 64})
    assert captured.value.code == "CMP-PROCESSING-4304"
    assert "Split" in captured.value.recovery

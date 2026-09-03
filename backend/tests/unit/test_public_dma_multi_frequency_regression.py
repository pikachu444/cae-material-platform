from __future__ import annotations

import csv
import hashlib
import math
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, localcontext
from pathlib import Path
from typing import cast

import pytest
import yaml
from cmp.modules.processing.domain.dma_frequency_master_curve import (
    DMA_SWEEP_TEMPERATURE_TOLERANCE_K,
    DmaFrequencyMasterCurveBuildResult,
    DmaPartition,
    frequency_master_curve_from_parquet,
    frequency_master_curve_parquet_bytes,
)
from cmp.modules.processing.domain.dma_multi_frequency_tts import (
    DmaFrequencySweep,
    DmaFrequencySweepDisposition,
    DmaFrequencySweepPoint,
    DmaShiftLawRequest,
    DmaTtsAdjacentOptimizerControls,
    DmaTtsScoringControls,
    build_multi_frequency_master_curve,
)
from cmp.modules.testing.domain.public_material_test_data import (
    PublicMaterialExperiment,
    PublicMaterialTestData,
    load_public_material_test_data_manifest,
)

ROOT = Path(__file__).parents[3]
DARUS_MANIFEST = ROOT / "fixtures/manifests/public-viscoelastic-darus-smp-v1.1.yaml"
NIST_MANIFEST = ROOT / "fixtures/manifests/nist-srm-2491-dma-table-9-v1.yaml"
_KELVIN_OFFSET = Decimal("273.15")
_DECIMAL_PI = Decimal("3.14159265358979323846264338327950288419716939937510582097494")


@dataclass(frozen=True, slots=True)
class _PublishedSweep:
    source_result_number: int
    source_rows: tuple[tuple[int, dict[str, str]], ...]
    representative_temperature_c: Decimal
    maximum_temperature_deviation_c: Decimal
    published_shift_factor: Decimal
    published_point_count: int


@dataclass(frozen=True, slots=True)
class _ConditionCase:
    condition: str
    frequency_rows: tuple[dict[str, str], ...]
    master_rows: tuple[dict[str, str], ...]
    published_sweeps: tuple[_PublishedSweep, ...]


@dataclass(frozen=True, slots=True)
class _NistTableRow:
    temperature_c: Decimal
    angular_frequency_rad_per_s: Decimal
    storage_modulus_pa: Decimal
    storage_standard_uncertainty_pa: Decimal
    storage_model_pa: Decimal
    loss_modulus_pa: Decimal
    loss_standard_uncertainty_pa: Decimal
    loss_model_pa: Decimal


def _experiment(
    dataset: PublicMaterialTestData,
    experiment_id: str,
) -> PublicMaterialExperiment:
    return next(item for item in dataset.experiments if item.id == experiment_id)


def _row_dicts(experiment: PublicMaterialExperiment) -> tuple[dict[str, str], ...]:
    return tuple(dict(zip(experiment.header, row, strict=True)) for row in experiment.rows)


def _load_condition_case(condition: str) -> _ConditionCase:
    dataset = load_public_material_test_data_manifest(DARUS_MANIFEST)
    frequency_rows = _row_dicts(
        _experiment(dataset, f"dmtha-{condition}-frequency-sweep-smp-{condition}")
    )
    master_rows = _row_dicts(
        _experiment(dataset, f"dmtha-{condition}-master-curve-smp-{condition}")
    )
    published_by_response: dict[tuple[str, str, str], set[tuple[str, str]]] = {}
    for row in master_rows:
        response = (row["Angular Frequency"], row["Storage Modulus"], row["Loss Modulus"])
        published_by_response.setdefault(response, set()).add(
            (row["Horizontal Shift Factor"], row["Reduced Angular Frequency"])
        )

    grouped: dict[int, list[tuple[int, dict[str, str]]]] = {}
    for source_ordinal, row in enumerate(frequency_rows):
        grouped.setdefault(int(row["Result No."]), []).append((source_ordinal, row))

    published_sweeps: list[_PublishedSweep] = []
    for source_result_number, source_rows_list in grouped.items():
        source_rows = tuple(source_rows_list)
        evidence = {
            item
            for _, row in source_rows
            for item in published_by_response.get(
                (row["Angular Frequency"], row["Storage Modulus"], row["Loss Modulus"]),
                set(),
            )
        }
        if not evidence:
            continue
        published_factors = {Decimal(factor) for factor, _ in evidence}
        assert len(published_factors) == 1
        temperature_counts = Counter(Decimal(row["Temperature"]) for _, row in source_rows)
        maximum_count = max(temperature_counts.values())
        representative_temperature_c = min(
            temperature
            for temperature, count in temperature_counts.items()
            if count == maximum_count
        )
        published_sweeps.append(
            _PublishedSweep(
                source_result_number=source_result_number,
                source_rows=source_rows,
                representative_temperature_c=representative_temperature_c,
                maximum_temperature_deviation_c=max(
                    abs(Decimal(row["Temperature"]) - representative_temperature_c)
                    for _, row in source_rows
                ),
                published_shift_factor=next(iter(published_factors)),
                published_point_count=sum(
                    (
                        row["Angular Frequency"],
                        row["Storage Modulus"],
                        row["Loss Modulus"],
                    )
                    in published_by_response
                    for _, row in source_rows
                ),
            )
        )
    return _ConditionCase(condition, frequency_rows, master_rows, tuple(published_sweeps))


def _temperature_k(temperature_c: Decimal) -> float:
    return float(temperature_c + _KELVIN_OFFSET)


def _object_mapping(value: object, name: str) -> Mapping[str, object]:
    assert isinstance(value, dict), f"{name} must be a mapping"
    return cast(Mapping[str, object], value)


def _load_nist_rows() -> tuple[_NistTableRow, ...]:
    manifest = _object_mapping(
        yaml.safe_load(NIST_MANIFEST.read_text(encoding="utf-8")), "manifest"
    )
    fixture = _object_mapping(manifest["fixture"], "fixture")
    fixture_path = ROOT / str(fixture["path"])
    digest = _object_mapping(fixture["digest"], "fixture.digest")
    assert hashlib.sha256(fixture_path.read_bytes()).hexdigest() == digest["value"]
    with fixture_path.open(encoding="utf-8", newline="") as source:
        reader = csv.DictReader(source)
        assert reader.fieldnames == [
            "temperature_c",
            "angular_frequency_rad_per_s",
            "storage_modulus_pa",
            "storage_standard_uncertainty_pa",
            "storage_model_pa",
            "loss_modulus_pa",
            "loss_standard_uncertainty_pa",
            "loss_model_pa",
        ]
        return tuple(
            _NistTableRow(
                temperature_c=Decimal(row["temperature_c"]),
                angular_frequency_rad_per_s=Decimal(row["angular_frequency_rad_per_s"]),
                storage_modulus_pa=Decimal(row["storage_modulus_pa"]),
                storage_standard_uncertainty_pa=Decimal(row["storage_standard_uncertainty_pa"]),
                storage_model_pa=Decimal(row["storage_model_pa"]),
                loss_modulus_pa=Decimal(row["loss_modulus_pa"]),
                loss_standard_uncertainty_pa=Decimal(row["loss_standard_uncertainty_pa"]),
                loss_model_pa=Decimal(row["loss_model_pa"]),
            )
            for row in reader
        )


def _nist_log10_shift_rebased(
    temperature_c: Decimal,
    reference_temperature_c: Decimal,
) -> Decimal:
    c1 = Decimal("6.64")
    c2 = Decimal("299.4")
    source_reference_c = Decimal("25")

    def natural_log_shift(value_c: Decimal) -> Decimal:
        delta = value_c - source_reference_c
        return -(c1 * delta) / (c2 + delta)

    return (
        natural_log_shift(temperature_c) - natural_log_shift(reference_temperature_c)
    ) / Decimal(10).ln()


def _build_condition(case: _ConditionCase) -> tuple[DmaFrequencyMasterCurveBuildResult, int]:
    usable = tuple(
        sweep
        for sweep in case.published_sweeps
        if sweep.maximum_temperature_deviation_c <= DMA_SWEEP_TEMPERATURE_TOLERANCE_K
    )
    holdout_ordinal = usable[-1].source_result_number
    sweeps = tuple(
        DmaFrequencySweep(
            source_sweep_ordinal=sweep.source_result_number,
            points=tuple(
                DmaFrequencySweepPoint(
                    source_ordinal=source_ordinal,
                    measured_temperature_k=_temperature_k(Decimal(row["Temperature"])),
                    frequency_hz=float(row["Frequency"]),
                    storage_modulus_pa=float(row["Storage Modulus"]) * 1_000_000.0,
                    loss_modulus_pa=float(row["Loss Modulus"]) * 1_000_000.0,
                )
                for source_ordinal, row in sweep.source_rows
            ),
        )
        for sweep in usable
    )
    dispositions = tuple(
        DmaFrequencySweepDisposition(
            source_sweep_ordinal=sweep.source_result_number,
            representative_temperature_k=_temperature_k(sweep.representative_temperature_c),
            partition=(
                DmaPartition.HOLDOUT
                if sweep.source_result_number == holdout_ordinal
                else DmaPartition.CALIBRATION
            ),
        )
        for sweep in usable
    )
    reference = next(sweep for sweep in usable if sweep.published_shift_factor == Decimal(1))
    result = build_multi_frequency_master_curve(
        sweeps,
        dispositions,
        reference_sweep_ordinal=reference.source_result_number,
        shift_law=DmaShiftLawRequest(
            kind="manual_tabulated",
            reference_temperature_k=_temperature_k(reference.representative_temperature_c),
            manual_table=tuple(
                (
                    _temperature_k(sweep.representative_temperature_c),
                    math.log10(float(sweep.published_shift_factor)),
                )
                for sweep in usable
            ),
        ),
        scoring=DmaTtsScoringControls(0.25, 101, 0.5, 0.5),
        adjacent_optimizer=DmaTtsAdjacentOptimizerControls(-12.0, 12.0),
        law_optimizer=None,
        confirmed=True,
        confirmation_reason=(
            f"Validate DaRUS {case.condition} multi-frequency DMA against published shifts"
        ),
    )
    return result, holdout_ordinal


@pytest.mark.parametrize(
    (
        "condition",
        "expected_raw_rows",
        "expected_master_rows",
        "expected_published_sweeps",
        "expected_published_source_points",
        "expected_published_memberships",
        "expected_maximum_deviation_c",
        "expected_rejected_ordinals",
    ),
    (
        ("50", 325, 283, 21, 273, 270, Decimal("0.21"), ()),
        ("70", 390, 216, 17, 221, 205, Decimal("0.34"), ()),
        ("dry", 351, 290, 21, 273, 264, Decimal("0.44"), ()),
        ("redry", 351, 279, 21, 273, 266, Decimal("0.52"), (2,)),
        ("wet", 325, 202, 15, 195, 189, Decimal("0.17"), ()),
    ),
)
def test_darus_environmental_conditions_preserve_raw_data_and_published_shifts(
    condition: str,
    expected_raw_rows: int,
    expected_master_rows: int,
    expected_published_sweeps: int,
    expected_published_source_points: int,
    expected_published_memberships: int,
    expected_maximum_deviation_c: Decimal,
    expected_rejected_ordinals: tuple[int, ...],
) -> None:
    case = _load_condition_case(condition)
    assert len(case.frequency_rows) == expected_raw_rows
    assert len(case.master_rows) == expected_master_rows
    assert len(case.published_sweeps) == expected_published_sweeps
    assert sum(len(sweep.source_rows) for sweep in case.published_sweeps) == (
        expected_published_source_points
    )
    assert sum(sweep.published_point_count for sweep in case.published_sweeps) == (
        expected_published_memberships
    )
    assert (
        max(sweep.maximum_temperature_deviation_c for sweep in case.published_sweeps)
        == expected_maximum_deviation_c
    )
    assert (
        tuple(
            sweep.source_result_number
            for sweep in case.published_sweeps
            if sweep.maximum_temperature_deviation_c > DMA_SWEEP_TEMPERATURE_TOLERANCE_K
        )
        == expected_rejected_ordinals
    )

    result, holdout_ordinal = _build_condition(case)
    usable = {
        sweep.source_result_number: sweep
        for sweep in case.published_sweeps
        if sweep.maximum_temperature_deviation_c <= DMA_SWEEP_TEMPERATURE_TOLERANCE_K
    }
    assert len(result.rows) == len(usable)
    assert next(
        row for row in result.rows if row.partition is DmaPartition.HOLDOUT
    ).source_sweep_ordinal == (holdout_ordinal)
    assert (
        frequency_master_curve_from_parquet(frequency_master_curve_parquet_bytes(result.rows))
        == result.rows
    )

    with localcontext() as decimal_context:
        decimal_context.prec = 70
        for row in result.rows:
            source_sweep_ordinal = row.source_sweep_ordinal
            assert source_sweep_ordinal is not None
            source_sweep = usable[source_sweep_ordinal]
            assert math.isclose(
                row.shift_factor or 0.0,
                float(source_sweep.published_shift_factor),
                rel_tol=1e-12,
            )
            reduced = row.reduced_angular_frequency_rad_per_s
            assert reduced is not None
            for index, (_, source) in enumerate(source_sweep.source_rows):
                expected_omega = Decimal(2) * _DECIMAL_PI * Decimal(source["Frequency"])
                expected_reduced = expected_omega * source_sweep.published_shift_factor
                assert row.measured_temperature_k[index] == _temperature_k(
                    Decimal(source["Temperature"])
                )
                assert row.storage_modulus_pa[index] == (
                    float(source["Storage Modulus"]) * 1_000_000.0
                )
                assert row.loss_modulus_pa[index] == (float(source["Loss Modulus"]) * 1_000_000.0)
                assert math.isclose(
                    row.angular_frequency_rad_per_s[index],
                    float(expected_omega),
                    rel_tol=1e-12,
                )
                assert math.isclose(reduced[index], float(expected_reduced), rel_tol=1e-12)


def test_nist_srm_2491_pdms_preserves_table_9_and_applies_published_wlf_direction() -> None:
    rows = _load_nist_rows()
    assert len(rows) == 96
    temperatures_c = tuple(sorted({row.temperature_c for row in rows}))
    assert temperatures_c == tuple(Decimal(value) for value in (0, 10, 20, 30, 40, 50))
    grouped = {
        temperature_c: tuple(row for row in rows if row.temperature_c == temperature_c)
        for temperature_c in temperatures_c
    }
    assert {len(group) for group in grouped.values()} == {16}
    assert all(
        tuple(row.angular_frequency_rad_per_s for row in group)
        == tuple(sorted(row.angular_frequency_rad_per_s for row in group))
        for group in grouped.values()
    )

    reference_temperature_c = Decimal(20)
    reference_sweep_ordinal = temperatures_c.index(reference_temperature_c) + 1
    sweeps = tuple(
        DmaFrequencySweep(
            source_sweep_ordinal=sweep_ordinal,
            points=tuple(
                DmaFrequencySweepPoint(
                    source_ordinal=source_ordinal,
                    measured_temperature_k=_temperature_k(source.temperature_c),
                    frequency_hz=float(source.angular_frequency_rad_per_s) / (2.0 * math.pi),
                    storage_modulus_pa=float(source.storage_modulus_pa),
                    loss_modulus_pa=float(source.loss_modulus_pa),
                )
                for source_ordinal, source in (
                    (rows.index(source), source) for source in grouped[temperature_c]
                )
            ),
        )
        for sweep_ordinal, temperature_c in enumerate(temperatures_c, start=1)
    )
    dispositions = tuple(
        DmaFrequencySweepDisposition(
            source_sweep_ordinal=sweep_ordinal,
            representative_temperature_k=_temperature_k(temperature_c),
            partition=(
                DmaPartition.HOLDOUT if temperature_c == Decimal(50) else DmaPartition.CALIBRATION
            ),
        )
        for sweep_ordinal, temperature_c in enumerate(temperatures_c, start=1)
    )
    result = build_multi_frequency_master_curve(
        sweeps,
        dispositions,
        reference_sweep_ordinal=reference_sweep_ordinal,
        shift_law=DmaShiftLawRequest(
            kind="manual_tabulated",
            reference_temperature_k=_temperature_k(reference_temperature_c),
            manual_table=tuple(
                (
                    _temperature_k(temperature_c),
                    float(
                        _nist_log10_shift_rebased(
                            temperature_c,
                            reference_temperature_c,
                        )
                    ),
                )
                for temperature_c in temperatures_c
            ),
        ),
        scoring=DmaTtsScoringControls(0.25, 101, 0.5, 0.5),
        adjacent_optimizer=DmaTtsAdjacentOptimizerControls(-2.0, 2.0),
        law_optimizer=None,
        confirmed=True,
        confirmation_reason=(
            "Validate NIST SRM 2491 Table 9 PDMS data against the published WLF equation"
        ),
    )

    assert len(result.rows) == 6
    assert sum(len(row.source_ordinals) for row in result.rows) == 96
    assert (
        frequency_master_curve_from_parquet(frequency_master_curve_parquet_bytes(result.rows))
        == result.rows
    )
    holdout = next(row for row in result.rows if row.partition is DmaPartition.HOLDOUT)
    assert holdout.representative_temperature_k == 323.15
    assert holdout.holdout_evaluation_status == "evaluated"

    source_by_ordinal = {source_ordinal: source for source_ordinal, source in enumerate(rows)}
    with localcontext() as decimal_context:
        decimal_context.prec = 70
        for actual, temperature_c in zip(result.rows, temperatures_c, strict=True):
            expected_log10_shift = _nist_log10_shift_rebased(
                temperature_c,
                reference_temperature_c,
            )
            expected_factor = Decimal(10) ** expected_log10_shift
            assert actual.applied_log10_a_t is not None
            assert math.isclose(
                actual.applied_log10_a_t,
                float(expected_log10_shift),
                rel_tol=1e-12,
                abs_tol=1e-12,
            )
            assert math.isclose(
                actual.shift_factor or 0.0,
                float(expected_factor),
                rel_tol=1e-12,
            )
            reduced = actual.reduced_angular_frequency_rad_per_s
            assert reduced is not None
            for index, source_ordinal in enumerate(actual.source_ordinals):
                source = source_by_ordinal[source_ordinal]
                assert actual.storage_modulus_pa[index] == float(source.storage_modulus_pa)
                assert actual.loss_modulus_pa[index] == float(source.loss_modulus_pa)
                assert math.isclose(
                    actual.angular_frequency_rad_per_s[index],
                    float(source.angular_frequency_rad_per_s),
                    rel_tol=1e-15,
                    abs_tol=1e-15,
                )
                assert math.isclose(
                    reduced[index],
                    float(source.angular_frequency_rad_per_s * expected_factor),
                    rel_tol=1e-12,
                )

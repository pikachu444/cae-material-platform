from __future__ import annotations

import hashlib
import math
import shutil
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal, localcontext
from pathlib import Path

import pytest
import yaml
from cmp.modules.processing.domain.dma_frequency_master_curve import (
    DMA_SWEEP_TEMPERATURE_TOLERANCE_K,
    DmaPartition,
    DmaRowDisposition,
    DmaTemperatureSweepRow,
    TabulatedShiftLaw,
    build_frequency_master_curve,
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
    PublicMaterialTestDataError,
    discover_public_material_test_data_manifests,
    load_public_material_test_data_manifest,
)

ROOT = Path(__file__).parents[3]
DARUS_MANIFEST = ROOT / "fixtures/manifests/public-viscoelastic-darus-smp-v1.1.yaml"
VITRIMER_MANIFEST = ROOT / "fixtures/manifests/public-viscoelastic-vitrimer-v1.0.yaml"


@dataclass(frozen=True, slots=True)
class _DarusPublishedShiftSweep:
    published_shift_factor: Decimal
    published_point_count: int
    source_result_number: int
    source_rows: tuple[tuple[int, dict[str, str]], ...]
    representative_temperature_c: float
    maximum_temperature_deviation_c: float


_DECIMAL_PI = Decimal("3.14159265358979323846264338327950288419716939937510582097494")


def test_darus_archive_preserves_every_member_and_only_exact_temperature_groups() -> None:
    dataset = load_public_material_test_data_manifest(DARUS_MANIFEST)

    assert dataset.source["doi"] == "10.18419/darus-2021"
    assert dataset.source["license"] == "CC BY 4.0"
    assert dataset.frequency_validation is not None
    assert dataset.frequency_validation.frequency_group_key == ("Result No.", "Temperature")
    assert dataset.frequency_validation.frequency_columns["frequency"] == "Frequency"
    assert len(dataset.experiments) == 18
    assert len(dataset.member_inventory) == 19
    assert {item.disposition for item in dataset.member_inventory} == {"validated", "ignored"}
    assert sum(item.disposition == "validated" for item in dataset.member_inventory) == 18
    assert dataset.member_inventory[-1].path == "MANIFEST.TXT"
    assert dataset.member_inventory[-1].role == "archive_manifest"
    assert Counter(experiment.kind for experiment in dataset.experiments) == {
        "shear_dma_frequency_sweep": 6,
        "time_temperature_shift": 6,
        "viscoelastic_master_curve": 6,
    }
    assert [
        (
            group.experiment_id,
            group.result_number,
            group.temperature_texts,
            group.row_count,
        )
        for group in dataset.eligible_frequency_groups
    ] == [
        ("dmtha-30-frequency-sweep-smp-30", "1", ("10",), 13),
        ("dmtha-70-frequency-sweep-smp-70", "1", ("10",), 13),
    ]
    assert all(
        experiment.conditions["humidity_state"] in {"30", "50", "70", "dry", "redry", "wet"}
        for experiment in dataset.experiments
    )
    assert all(not experiment.export_eligible for experiment in dataset.experiments)
    assert all(experiment.static_property_set == "absent" for experiment in dataset.experiments)


def test_darus_one_hertz_temperature_slice_matches_published_master_curve() -> None:
    dataset = load_public_material_test_data_manifest(DARUS_MANIFEST)
    frequency_sweep = next(
        item
        for item in dataset.experiments
        if item.kind == "shear_dma_frequency_sweep"
        and item.conditions.get("humidity_state") == "30"
    )
    published_master = next(
        item
        for item in dataset.experiments
        if item.kind == "viscoelastic_master_curve"
        and item.conditions.get("humidity_state") == "30"
    )

    frequency_rows = tuple(
        dict(zip(frequency_sweep.header, row, strict=True)) for row in frequency_sweep.rows
    )
    master_rows = tuple(
        dict(zip(published_master.header, row, strict=True)) for row in published_master.rows
    )
    published_by_response: dict[tuple[str, str, str], set[tuple[str, str]]] = {}
    for row in master_rows:
        key = (row["Angular Frequency"], row["Storage Modulus"], row["Loss Modulus"])
        published_by_response.setdefault(key, set()).add(
            (row["Horizontal Shift Factor"], row["Reduced Angular Frequency"])
        )

    selected: list[tuple[dict[str, str], str, str]] = []
    for row in frequency_rows:
        if row["Frequency"] != "1":
            continue
        key = (row["Angular Frequency"], row["Storage Modulus"], row["Loss Modulus"])
        evidence = published_by_response.get(key, set())
        if len(evidence) == 1:
            shift_factor, published_reduced_omega = next(iter(evidence))
            selected.append((row, shift_factor, published_reduced_omega))

    assert len(selected) == 25
    reference = next(item for item in selected if item[1] == "1")
    reference_temperature_k = float(reference[0]["Temperature"]) + 273.15
    result = build_frequency_master_curve(
        tuple(
            DmaTemperatureSweepRow(
                source_ordinal=ordinal,
                temperature_k=float(row["Temperature"]) + 273.15,
                frequency_hz=float(row["Frequency"]),
                storage_modulus_pa=float(row["Storage Modulus"]) * 1_000_000.0,
                loss_modulus_pa=float(row["Loss Modulus"]) * 1_000_000.0,
            )
            for ordinal, (row, _, _) in enumerate(selected)
        ),
        tuple(
            DmaRowDisposition(ordinal, DmaPartition.CALIBRATION) for ordinal in range(len(selected))
        ),
        TabulatedShiftLaw(
            reference_temperature_k,
            tuple(
                (
                    float(row["Temperature"]) + 273.15,
                    math.log10(float(shift_factor)),
                )
                for row, shift_factor, _ in selected
            ),
        ),
        confirmed=True,
        confirmation_reason="Use the exact published horizontal shift factors",
    )

    for actual, (source, shift_factor, published_reduced_omega) in zip(
        result, selected, strict=True
    ):
        assert actual.source_frequency_hz[0] == 1.0
        assert actual.storage_modulus_pa[0] == float(source["Storage Modulus"]) * 1_000_000.0
        assert actual.loss_modulus_pa[0] == float(source["Loss Modulus"]) * 1_000_000.0
        assert math.isclose(actual.shift_factor or 0.0, float(shift_factor), rel_tol=5e-14)
        # The publication rounds reduced angular frequency to about five significant digits.
        assert math.isclose(
            (actual.reduced_angular_frequency_rad_per_s or (0.0,))[0],
            float(published_reduced_omega),
            rel_tol=5e-5,
        )


def test_darus_multi_frequency_result_matches_published_shift_and_master_data() -> None:
    dataset = load_public_material_test_data_manifest(DARUS_MANIFEST)
    frequency_sweep = next(
        item for item in dataset.experiments if item.id == "dmtha-30-frequency-sweep-smp-30"
    )
    published_shift = next(item for item in dataset.experiments if item.id == "dmtha-30-alpha-t-30")
    published_master = next(
        item for item in dataset.experiments if item.id == "dmtha-30-master-curve-smp-30"
    )

    assert dataset.source["doi"] == "10.18419/darus-2021"
    assert dataset.source["license"] == "CC BY 4.0"
    assert dataset.source["landing_page"] == (
        "https://darus.uni-stuttgart.de/dataset.xhtml?persistentId=doi:10.18419/darus-2021"
    )
    assert dataset.archive_path.stat().st_size == 109_927
    assert dataset.archive_sha256 == (
        "26568b82a6031edbbeab933bce0273918d1f3dfebbc5202f91742becc51088cf"
    )
    assert frequency_sweep.sha256 == (
        "37f70abaae12791d0661ff78e778e2bbe765d46506b4ee9268ad50de4d2523e7"
    )
    assert published_shift.sha256 == (
        "dc2353cf6c68b2c777bc8bd745a88cdca7ead5247b616ef2ed0e336c8e6d020f"
    )
    assert published_master.sha256 == (
        "17f0fa62b50b5cdf33548769ad62c1a7216365889c54c8c11d28cf6b725036b2"
    )

    frequency_rows = tuple(
        dict(zip(frequency_sweep.header, row, strict=True)) for row in frequency_sweep.rows
    )
    master_rows = tuple(
        dict(zip(published_master.header, row, strict=True)) for row in published_master.rows
    )
    shift_rows = tuple(
        dict(zip(published_shift.header, row, strict=True)) for row in published_shift.rows
    )
    assert len(frequency_rows) == 429
    assert len(master_rows) == 323
    assert len(shift_rows) == 25

    grouped_rows: dict[int, list[tuple[int, dict[str, str]]]] = {}
    for source_ordinal, row in enumerate(frequency_rows):
        grouped_rows.setdefault(int(row["Result No."]), []).append((source_ordinal, row))

    raw_by_response: dict[tuple[str, str, str], int] = {}
    for row in frequency_rows:
        key = (row["Angular Frequency"], row["Storage Modulus"], row["Loss Modulus"])
        assert key not in raw_by_response
        raw_by_response[key] = int(row["Result No."])

    master_response_counts = Counter(
        (row["Angular Frequency"], row["Storage Modulus"], row["Loss Modulus"])
        for row in master_rows
    )
    assert set(master_response_counts) <= set(raw_by_response)
    assert sum(count - 1 for count in master_response_counts.values()) == 13
    duplicated_result_numbers = {
        raw_by_response[key] for key, count in master_response_counts.items() if count > 1
    }
    assert duplicated_result_numbers == {18}
    assert {count for count in master_response_counts.values() if count > 1} == {2}

    published_by_response: dict[tuple[str, str, str], set[tuple[str, str]]] = {}
    for row in master_rows:
        key = (row["Angular Frequency"], row["Storage Modulus"], row["Loss Modulus"])
        published_by_response.setdefault(key, set()).add(
            (row["Horizontal Shift Factor"], row["Reduced Angular Frequency"])
        )
    assert sum(key in published_by_response for key in raw_by_response) == 310
    assert sum(key not in published_by_response for key in raw_by_response) == 119

    matched_sweeps: list[_DarusPublishedShiftSweep] = []
    for result_number, rows in grouped_rows.items():
        source_rows = tuple(rows)
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

        temperature_counts = Counter(row["Temperature"] for _, row in source_rows)
        maximum_count = max(temperature_counts.values())
        representative_temperature_c = min(
            float(temperature)
            for temperature, count in temperature_counts.items()
            if count == maximum_count
        )
        maximum_temperature_deviation_c = max(
            abs(float(row["Temperature"]) - representative_temperature_c) for _, row in source_rows
        )
        matched_sweeps.append(
            _DarusPublishedShiftSweep(
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
                source_result_number=result_number,
                source_rows=source_rows,
                representative_temperature_c=representative_temperature_c,
                maximum_temperature_deviation_c=maximum_temperature_deviation_c,
            )
        )

    assert [item.source_result_number for item in matched_sweeps] == [
        *range(1, 21),
        23,
        25,
        27,
        32,
        33,
    ]
    assert sum(item.published_point_count for item in matched_sweeps) == 310
    assert sorted(set(grouped_rows) - {item.source_result_number for item in matched_sweeps}) == [
        21,
        22,
        24,
        26,
        28,
        29,
        30,
        31,
    ]

    # alpha_T_30.csv independently lists the same 25 shifted sweeps, but its headers are
    # reversed in practice and both values are less precise than the master-curve factors.
    for shift_row, item in zip(shift_rows, matched_sweeps, strict=True):
        mean_source_temperature_c = sum(
            Decimal(row["Temperature"]) for _, row in item.source_rows
        ) / Decimal(len(item.source_rows))
        assert abs(Decimal(shift_row["T"]) - mean_source_temperature_c) <= Decimal("0.003")
        assert math.isclose(
            float(shift_row["log alpha_T"]),
            float(item.published_shift_factor),
            rel_tol=0.003,
        )
        assert math.isclose(
            10.0 ** float(shift_row["alpha_T"]),
            float(item.published_shift_factor),
            rel_tol=0.003,
        )

    rejected = tuple(
        item
        for item in matched_sweeps
        if item.maximum_temperature_deviation_c
        > float(DMA_SWEEP_TEMPERATURE_TOLERANCE_K)
    )
    assert [
        (
            item.source_result_number,
            item.published_point_count,
            item.maximum_temperature_deviation_c,
        )
        for item in rejected
    ] == []
    usable = tuple(item for item in matched_sweeps if item not in rejected)
    assert len(usable) == 25
    assert sum(len(item.source_rows) for item in usable) == 325
    assert sum(item.published_point_count for item in usable) == 310

    sweeps = tuple(
        DmaFrequencySweep(
            source_sweep_ordinal=item.source_result_number,
            points=tuple(
                DmaFrequencySweepPoint(
                    source_ordinal=source_ordinal,
                    measured_temperature_k=float(row["Temperature"]) + 273.15,
                    frequency_hz=float(row["Frequency"]),
                    storage_modulus_pa=float(row["Storage Modulus"]) * 1_000_000.0,
                    loss_modulus_pa=float(row["Loss Modulus"]) * 1_000_000.0,
                )
                for source_ordinal, row in item.source_rows
            ),
        )
        for item in usable
    )
    dispositions = tuple(
        DmaFrequencySweepDisposition(
            source_sweep_ordinal=item.source_result_number,
            representative_temperature_k=item.representative_temperature_c + 273.15,
            # The highest published sweep is the independent holdout.
            partition=(
                DmaPartition.HOLDOUT
                if item.source_result_number == 33
                else DmaPartition.CALIBRATION
            ),
        )
        for item in usable
    )
    reference = next(item for item in usable if item.published_shift_factor == Decimal(1))
    result = build_multi_frequency_master_curve(
        sweeps,
        dispositions,
        reference_sweep_ordinal=reference.source_result_number,
        shift_law=DmaShiftLawRequest(
            kind="manual_tabulated",
            reference_temperature_k=reference.representative_temperature_c + 273.15,
            # The immutable raw sweep's exact modal temperature remains the contract key;
            # each factor is the authoritative value in the published master curve.
            manual_table=tuple(
                (
                    item.representative_temperature_c + 273.15,
                    math.log10(float(item.published_shift_factor)),
                )
                for item in usable
            ),
        ),
        scoring=DmaTtsScoringControls(
            minimum_overlap_decades=0.25,
            overlap_evaluation_point_count=101,
            storage_weight=0.5,
            loss_weight=0.5,
        ),
        adjacent_optimizer=DmaTtsAdjacentOptimizerControls(-3.0, 3.0),
        law_optimizer=None,
        confirmed=True,
        confirmation_reason=(
            "Validate the multi-frequency result against the CC BY 4.0 DaRUS raw data "
            "and published master-curve shift factors"
        ),
    )

    source_by_ordinal = {source_ordinal: row for source_ordinal, row in enumerate(frequency_rows)}
    shift_by_result_number = {
        item.source_result_number: item.published_shift_factor for item in usable
    }
    with localcontext() as decimal_context:
        decimal_context.prec = 70
        for actual in result.rows:
            source_sweep_ordinal = actual.source_sweep_ordinal
            assert source_sweep_ordinal is not None
            expected_factor = shift_by_result_number[source_sweep_ordinal]
            assert math.isclose(
                actual.shift_factor or 0.0,
                float(expected_factor),
                rel_tol=1e-12,
            )
            reduced = actual.reduced_angular_frequency_rad_per_s
            assert reduced is not None
            for index, source_ordinal in enumerate(actual.source_ordinals):
                source = source_by_ordinal[source_ordinal]
                source_frequency_hz = float(source["Frequency"])
                expected_omega = Decimal(2) * _DECIMAL_PI * Decimal(source["Frequency"])
                expected_reduced_omega = expected_omega * expected_factor
                assert actual.measured_temperature_k[index] == (
                    float(source["Temperature"]) + 273.15
                )
                assert actual.source_frequency_hz[index] == source_frequency_hz
                assert actual.storage_modulus_pa[index] == (
                    float(source["Storage Modulus"]) * 1_000_000.0
                )
                assert actual.loss_modulus_pa[index] == (
                    float(source["Loss Modulus"]) * 1_000_000.0
                )
                assert math.isclose(
                    actual.angular_frequency_rad_per_s[index],
                    float(expected_omega),
                    rel_tol=1e-12,
                )
                assert math.isclose(
                    reduced[index],
                    float(expected_reduced_omega),
                    rel_tol=1e-12,
                )

    published_comparison_count = 0
    unpublished_source_points: list[tuple[int, str]] = []
    maximum_published_rounding_relative_error = Decimal(0)
    with localcontext() as decimal_context:
        decimal_context.prec = 70
        for actual in result.rows:
            source_sweep_ordinal = actual.source_sweep_ordinal
            assert source_sweep_ordinal is not None
            expected_factor = shift_by_result_number[source_sweep_ordinal]
            reduced = actual.reduced_angular_frequency_rad_per_s
            assert reduced is not None
            for index, source_ordinal in enumerate(actual.source_ordinals):
                source = source_by_ordinal[source_ordinal]
                key = (
                    source["Angular Frequency"],
                    source["Storage Modulus"],
                    source["Loss Modulus"],
                )
                evidence = published_by_response.get(key, set())
                if not evidence:
                    unpublished_source_points.append((source_sweep_ordinal, source["Frequency"]))
                    continue
                assert len(evidence) == 1
                published_factor_text, published_reduced_omega_text = next(iter(evidence))
                assert Decimal(published_factor_text) == expected_factor
                expected_reduced_omega = (
                    Decimal(2) * _DECIMAL_PI * Decimal(source["Frequency"]) * expected_factor
                )
                published_reduced_omega = Decimal(published_reduced_omega_text)
                rounding_relative_error = abs(
                    expected_reduced_omega - published_reduced_omega
                ) / abs(expected_reduced_omega)
                maximum_published_rounding_relative_error = max(
                    maximum_published_rounding_relative_error,
                    rounding_relative_error,
                )
                assert rounding_relative_error <= Decimal("0.003")
                assert math.isclose(
                    reduced[index],
                    float(published_reduced_omega),
                    rel_tol=0.003,
                )
                published_comparison_count += 1

    assert published_comparison_count == 310
    assert math.isclose(
        float(maximum_published_rounding_relative_error),
        0.0010009653484362203,
        rel_tol=1e-15,
    )
    assert unpublished_source_points == [
        (23, "3.16"),
        (23, "5.62"),
        (23, "10"),
        (25, "3.16"),
        (25, "5.62"),
        (25, "10"),
        (27, "3.16"),
        (27, "5.62"),
        (27, "10"),
        (32, "10"),
        (33, "0.01"),
        (33, "1.78"),
        (33, "3.16"),
        (33, "5.62"),
        (33, "10"),
    ]
    holdout = next(row for row in result.rows if row.partition is DmaPartition.HOLDOUT)
    assert holdout.source_sweep_ordinal == 33
    assert holdout.holdout_evaluation_status == "evaluated"
    assert holdout.weighted_mse is not None and math.isfinite(holdout.weighted_mse)
    assert result.residual_summary is not None
    assert result.residual_summary["calibration_comparison_count"] == 23


def test_vitrimer_archive_preserves_all_relevant_experiments_without_promotion() -> None:
    dataset = load_public_material_test_data_manifest(VITRIMER_MANIFEST)

    assert dataset.source["doi"] == "10.5281/zenodo.21096098"
    assert dataset.source["license"] == "CC BY 4.0"
    assert len(dataset.experiments) == 30
    assert len(dataset.member_inventory) == 45
    assert sum(item.disposition == "ignored" for item in dataset.member_inventory) == 15
    assert Counter(experiment.kind for experiment in dataset.experiments) == {
        "shear_dma_temperature_ramp": 6,
        "shear_relaxation": 16,
        "arrhenius_summary": 4,
        "tensile": 4,
    }
    assert not dataset.eligible_frequency_groups
    assert all(not experiment.calibration_eligible for experiment in dataset.experiments)
    assert all(not experiment.export_eligible for experiment in dataset.experiments)

    dma = [
        experiment
        for experiment in dataset.experiments
        if experiment.kind == "shear_dma_temperature_ramp"
    ]
    assert all(experiment.conditions["frequency_hz"] == "1" for experiment in dma)
    assert all(
        experiment.units[0:2] == ("°C", "Pa") and experiment.units[-1] == "" for experiment in dma
    )
    assert sum(len(experiment.header) == 5 for experiment in dma) == 2
    assert all(
        experiment.ineligibility_reason
        == "fixed_1_hz_temperature_ramp_is_not_an_exact_temperature_frequency_sweep"
        for experiment in dma
    )

    relaxation = [
        experiment for experiment in dataset.experiments if experiment.kind == "shear_relaxation"
    ]
    assert all(experiment.units[1] == "" for experiment in relaxation)
    assert all(
        experiment.ineligibility_reason
        == "source_publishes_only_dimensionless_Gt_over_G0_without_absolute_relaxation_modulus"
        for experiment in relaxation
    )
    assert {
        experiment.id
        for experiment in relaxation
        if any(float(row[1]) <= 0 for row in experiment.rows if row[1])
    } == {
        "relaxation-test-raw-original-x1t-160-c",
        "relaxation-test-raw-original-x3t-140-c",
    }


def test_public_manifest_discovery_is_deterministic_and_not_dataset_named() -> None:
    assert discover_public_material_test_data_manifests(ROOT) == tuple(
        sorted((DARUS_MANIFEST, VITRIMER_MANIFEST))
    )


def test_member_inventory_digest_and_missing_member_are_fail_closed(tmp_path: Path) -> None:
    copied_manifest, _ = _copy_public_dataset(tmp_path, DARUS_MANIFEST)
    document = yaml.safe_load(copied_manifest.read_text(encoding="utf-8"))
    document["archive"]["member_inventory"][0]["sha256"] = "0" * 64
    copied_manifest.write_text(
        yaml.safe_dump(document, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
    with pytest.raises(PublicMaterialTestDataError, match="inventory digest changed"):
        load_public_material_test_data_manifest(copied_manifest)

    document["archive"]["member_inventory"].pop(0)
    copied_manifest.write_text(
        yaml.safe_dump(document, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
    with pytest.raises(PublicMaterialTestDataError, match="inventory does not match"):
        load_public_material_test_data_manifest(copied_manifest)


def test_semantic_column_mapping_is_required_for_each_parsed_member(tmp_path: Path) -> None:
    copied_manifest, _ = _copy_public_dataset(tmp_path, VITRIMER_MANIFEST)
    document = yaml.safe_load(copied_manifest.read_text(encoding="utf-8"))
    document["experiments"][0].pop("column_mapping")
    copied_manifest.write_text(
        yaml.safe_dump(document, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
    with pytest.raises(PublicMaterialTestDataError, match="column_mapping must be an object"):
        load_public_material_test_data_manifest(copied_manifest)


def test_manifest_cannot_reclassify_an_experiment_as_an_unsupported_kind(tmp_path: Path) -> None:
    copied_manifest, _ = _copy_public_dataset(tmp_path, VITRIMER_MANIFEST)
    document = yaml.safe_load(copied_manifest.read_text(encoding="utf-8"))
    document["experiments"][0]["kind"] = "compressive_hysteresis"
    copied_manifest.write_text(
        yaml.safe_dump(document, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
    with pytest.raises(PublicMaterialTestDataError, match="unsupported experiment kind"):
        load_public_material_test_data_manifest(copied_manifest)


def test_public_tensile_summaries_keep_published_values_but_create_no_property_set() -> None:
    dataset = load_public_material_test_data_manifest(VITRIMER_MANIFEST)
    tensile = [experiment for experiment in dataset.experiments if experiment.kind == "tensile"]

    assert len(tensile) == 4
    assert all(experiment.header[1] == "Youngov modul" for experiment in tensile)
    assert all(experiment.units[1] == "GPa" for experiment in tensile)
    assert tensile[1].rows[0][1] == "3250"
    assert all(experiment.static_property_set == "absent" for experiment in tensile)
    assert all(
        experiment.export_eligibility == "blocked_missing_static_property_set"
        for experiment in tensile
    )


def _copy_public_dataset(temporary_root: Path, source_manifest: Path) -> tuple[Path, Path]:
    manifest_document = yaml.safe_load(source_manifest.read_text(encoding="utf-8"))
    archive_relative = Path(manifest_document["archive"]["path"])
    copied_manifest = temporary_root / "fixtures/manifests" / source_manifest.name
    copied_archive = temporary_root / archive_relative
    copied_manifest.parent.mkdir(parents=True)
    copied_archive.parent.mkdir(parents=True)
    shutil.copyfile(ROOT / archive_relative, copied_archive)
    copied_manifest.write_text(
        yaml.safe_dump(manifest_document, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return copied_manifest, copied_archive


def test_public_archive_change_is_rejected_with_a_recoverable_cause(
    tmp_path: Path,
) -> None:
    copied_manifest, copied_archive = _copy_public_dataset(tmp_path, DARUS_MANIFEST)
    copied_archive.write_bytes(copied_archive.read_bytes() + b"changed")

    with pytest.raises(PublicMaterialTestDataError, match="archive SHA-256 changed"):
        load_public_material_test_data_manifest(copied_manifest)


def test_public_member_contract_change_is_rejected_without_hardcoded_fallback(
    tmp_path: Path,
) -> None:
    copied_manifest, copied_archive = _copy_public_dataset(tmp_path, VITRIMER_MANIFEST)
    document = yaml.safe_load(copied_manifest.read_text(encoding="utf-8"))
    document["experiments"][0]["expected_header"][0] = "Changed temperature"
    copied_manifest.write_text(
        yaml.safe_dump(document, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
    assert hashlib.sha256(copied_archive.read_bytes()).hexdigest() == document["archive"]["sha256"]

    with pytest.raises(PublicMaterialTestDataError, match="member header or units changed"):
        load_public_material_test_data_manifest(copied_manifest)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    (
        ("frequency_group_key", ["Unknown result", "Temperature"], "missing required column"),
        (
            "frequency_columns",
            {
                "frequency": "Angular Frequency",
                "storage_modulus": "Storage Modulus",
                "loss_modulus": "Loss Modulus",
            },
            "unit declaration",
        ),
        (
            "frequency_units",
            {
                "frequency": "rad/s",
                "storage_modulus": "MPa",
                "loss_modulus": "MPa",
                "temperature": "C",
            },
            "unit declaration",
        ),
        ("selection_rule", "a different selection rule", "selection_rule"),
        ("temperature_tolerance", "0.1 C", "temperature_tolerance"),
    ),
)
def test_darus_frequency_validation_declarations_are_required_and_source_bound(
    tmp_path: Path,
    field: str,
    value: object,
    message: str,
) -> None:
    copied_manifest, _ = _copy_public_dataset(tmp_path, DARUS_MANIFEST)
    document = yaml.safe_load(copied_manifest.read_text(encoding="utf-8"))
    document["validation"][field] = value
    copied_manifest.write_text(
        yaml.safe_dump(document, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )

    with pytest.raises(PublicMaterialTestDataError, match=message):
        load_public_material_test_data_manifest(copied_manifest)

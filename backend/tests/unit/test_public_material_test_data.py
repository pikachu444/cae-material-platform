from __future__ import annotations

import hashlib
import math
import shutil
from collections import Counter
from pathlib import Path

import pytest
import yaml
from cmp.modules.processing.domain.dma_frequency_master_curve import (
    DmaPartition,
    DmaRowDisposition,
    DmaTemperatureSweepRow,
    TabulatedShiftLaw,
    build_frequency_master_curve,
)
from cmp.modules.testing.domain.public_material_test_data import (
    PublicMaterialTestDataError,
    discover_public_material_test_data_manifests,
    load_public_material_test_data_manifest,
)

ROOT = Path(__file__).parents[3]
DARUS_MANIFEST = ROOT / "fixtures/manifests/public-viscoelastic-darus-smp-v1.1.yaml"
VITRIMER_MANIFEST = ROOT / "fixtures/manifests/public-viscoelastic-vitrimer-v1.0.yaml"


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

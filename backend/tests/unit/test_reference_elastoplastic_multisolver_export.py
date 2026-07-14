from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from uuid import UUID

import pytest
from cmp.modules.datasets.domain.reference_tensile import CurvePoint
from cmp.modules.exporting.domain.reference_isotropic_tabulated_plasticity import (
    ABAQUS_PLASTIC_EXPORTER_ID,
    OPENRADIOSS_LAW36_EXPORTER_ID,
    ElastoplasticExportTarget,
    ElastoplasticMappingReportMismatch,
    InvalidElastoplasticExport,
    UnsupportedElastoplasticTarget,
    build_reference_elastoplastic_solver_card,
    preflight_reference_elastoplastic_export,
    validate_reference_elastoplastic_card_with_curve,
)
from cmp.modules.modeling.domain.reference_isotropic_tabulated_plasticity import (
    HardeningCurvePoint,
    ReferenceIsotropicTabulatedPlasticityContent,
    derive_reference_isotropic_hardening_curve,
)


def _id(value: int) -> UUID:
    return UUID(int=value)


def _source() -> tuple[
    ReferenceIsotropicTabulatedPlasticityContent,
    tuple[HardeningCurvePoint, ...],
]:
    outcome = derive_reference_isotropic_hardening_curve(
        (
            CurvePoint(0.0, 0.0),
            CurvePoint(0.001, 200_000_000.0),
            CurvePoint(0.002, 300_000_000.0),
            CurvePoint(0.01, 400_000_000.0),
            CurvePoint(0.05, 500_000_000.0),
            CurvePoint(0.10, 480_000_000.0),
        ),
        youngs_modulus_pa=200_000_000_000.0,
        initial_yield_stress_pa=250_000_000.0,
        extension_max_true_plastic_strain=0.5,
        acknowledge_post_necking_approximation=True,
    )
    content = ReferenceIsotropicTabulatedPlasticityContent(
        material_id=_id(1),
        material_revision_id=_id(2),
        material_state_id=_id(3),
        material_state_revision_id=_id(4),
        property_set_id=_id(5),
        property_set_revision_id=_id(6),
        source_dataset_id=_id(7),
        source_dataset_revision_id=_id(8),
        hardening_curve_artifact_id=_id(9),
        hardening_curve_sha256="a" * 64,
        hardening_curve_point_count=len(outcome.points),
        source_point_count=outcome.input_point_count,
        pre_yield_excluded_point_count=outcome.pre_yield_excluded_count,
        post_necking_excluded_point_count=outcome.post_necking_excluded_count,
        necking_source_point_index=outcome.necking_source_index,
        density_kg_per_m3=7_850.0,
        youngs_modulus_pa=200_000_000_000.0,
        poisson_ratio=0.3,
        initial_yield_stress_pa=250_000_000.0,
        necking_engineering_strain=outcome.necking_engineering_strain,
        characterized_max_true_plastic_strain=(
            outcome.characterized_max_true_plastic_strain
        ),
        extension_max_true_plastic_strain=outcome.extension_max_true_plastic_strain,
        post_necking_approximation_acknowledged=True,
        applicable_temperature_min_k=288.15,
        applicable_temperature_max_k=308.15,
        applicable_strain_rate_min_per_s=0.0001,
        applicable_strain_rate_max_per_s=0.01,
        applicability_note="Ambient quasi-static reference range",
    )
    return content, outcome.points


@pytest.mark.parametrize(
    ("target", "expected_exporter"),
    [
        (ElastoplasticExportTarget("openradioss", "2025", "kg_m_s"), OPENRADIOSS_LAW36_EXPORTER_ID),
        (ElastoplasticExportTarget("abaqus", "2025", "kg_m_s"), ABAQUS_PLASTIC_EXPORTER_ID),
    ],
)
def test_preflight_declares_two_explicit_exportable_targets(
    target: ElastoplasticExportTarget,
    expected_exporter: str,
) -> None:
    source, _ = _source()

    report = preflight_reference_elastoplastic_export(
        material_model_id=_id(10),
        material_model_revision_id=_id(11),
        content=source,
        target=target,
    )

    assert report.exportable is True
    assert report.exporter_id == expected_exporter
    assert {item.status for item in report.items} <= {
        "exact",
        "transformed",
        "approximated",
        "not_applicable",
    }
    extension = next(item for item in report.items if item.name == "post_necking_extension")
    assert extension.status == "approximated"


def test_openradioss_law36_card_contains_material_and_hardening_function() -> None:
    source, points = _source()
    target = ElastoplasticExportTarget("openradioss", "2025", "kg_m_s")
    report = preflight_reference_elastoplastic_export(
        material_model_id=_id(10),
        material_model_revision_id=_id(11),
        content=source,
        target=target,
    )

    _, card = build_reference_elastoplastic_solver_card(
        material_model_id=_id(10),
        material_model_revision_id=_id(11),
        source=source,
        points=points,
        target=target,
        expected_mapping_report_sha256=report.digest,
        solver_material_id=42,
        material_name="DP600_REFERENCE",
    )

    assert "/MAT/LAW36/42/1" in card.card_text
    assert "/FUNCT/42" in card.card_text
    assert "5.000000000000E-01" in card.card_text
    fixture = (
        Path(__file__).parents[3]
        / "tests"
        / "fixtures"
        / "openradioss"
        / "reference-isotropic-tabulated-plasticity-kg-m-s.rad"
    )
    assert report.digest == "a32af1edd03fbba84bc5df37e38949a517184b8468c4e9f27069c6ce72c1ae79"
    assert card.card_text == fixture.read_text(encoding="utf-8")
    assert card.card_sha256 == "9bd80bbe677fea3dfd2734047ceebbd56118410809d1de35c9d4bc3ad63e6e3e"
    validate_reference_elastoplastic_card_with_curve(card, points)


def test_abaqus_card_contains_density_elastic_and_isotropic_plastic_keywords() -> None:
    source, points = _source()
    target = ElastoplasticExportTarget("abaqus", "2025", "kg_m_s")
    report = preflight_reference_elastoplastic_export(
        material_model_id=_id(10),
        material_model_revision_id=_id(11),
        content=source,
        target=target,
    )

    _, card = build_reference_elastoplastic_solver_card(
        material_model_id=_id(10),
        material_model_revision_id=_id(11),
        source=source,
        points=points,
        target=target,
        expected_mapping_report_sha256=report.digest,
        solver_material_id=42,
        material_name="DP600_REFERENCE",
    )

    assert "*MATERIAL, NAME=DP600_REFERENCE" in card.card_text
    assert "*DENSITY" in card.card_text
    assert "*ELASTIC, TYPE=ISOTROPIC" in card.card_text
    assert "*PLASTIC, HARDENING=ISOTROPIC, EXTRAPOLATION=CONSTANT" in card.card_text
    assert "2.500000000000E+08, 0.000000000000E+00" in card.card_text
    fixture = (
        Path(__file__).parents[3]
        / "tests"
        / "fixtures"
        / "abaqus"
        / "reference-isotropic-tabulated-plasticity-kg-m-s.inp"
    )
    assert report.digest == "bb075f51489b086cb99dd46616c2ac29965aa5eaaf7d9eb90d81b13d5ef4a1a6"
    assert card.card_text == fixture.read_text(encoding="utf-8")
    assert card.card_sha256 == "22f873566fe1c19d497a56b92772917c9b54ff66710d0c1baffb1c5f4b415b3c"
    assert card.applicable_temperature_min_k == 288.15
    assert card.applicable_temperature_max_k == 308.15
    assert card.applicable_strain_rate_min_per_s == 0.0001
    assert card.applicable_strain_rate_max_per_s == 0.01
    assert card.applicability_note == "Ambient quasi-static reference range"
    validate_reference_elastoplastic_card_with_curve(card, points)

    with pytest.raises(
        InvalidElastoplasticExport,
        match="stored mapping statuses differ from the target contract",
    ):
        replace(card, extension_mapping_status="exact")


def test_card_requires_current_mapping_report_acknowledgement() -> None:
    source, points = _source()

    with pytest.raises(ElastoplasticMappingReportMismatch):
        build_reference_elastoplastic_solver_card(
            material_model_id=_id(10),
            material_model_revision_id=_id(11),
            source=source,
            points=points,
            target=ElastoplasticExportTarget("abaqus", "2025", "kg_m_s"),
            expected_mapping_report_sha256="f" * 64,
            solver_material_id=42,
            material_name="DP600_REFERENCE",
        )


def test_undeclared_solver_target_is_not_exportable() -> None:
    source, points = _source()
    target = ElastoplasticExportTarget("ls_dyna", "R15", "kg_m_s")
    report = preflight_reference_elastoplastic_export(
        material_model_id=_id(10),
        material_model_revision_id=_id(11),
        content=source,
        target=target,
    )
    assert report.exportable is False
    assert report.items[0].status == "unsupported"

    with pytest.raises(UnsupportedElastoplasticTarget):
        build_reference_elastoplastic_solver_card(
            material_model_id=_id(10),
            material_model_revision_id=_id(11),
            source=source,
            points=points,
            target=target,
            expected_mapping_report_sha256=report.digest,
            solver_material_id=42,
            material_name="DP600_REFERENCE",
        )

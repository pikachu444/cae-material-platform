from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from uuid import UUID

import pytest
from cmp.modules.exporting.domain.reference_linear_viscoelasticity import (
    InvalidLinearViscoelasticExport,
    LinearViscoelasticExportTarget,
    LinearViscoelasticMappingReportMismatch,
    build_reference_linear_viscoelastic_solver_card,
    preflight_reference_linear_viscoelastic_export,
)
from cmp.modules.modeling.domain.reference_linear_viscoelasticity import (
    BulkRelaxationStatus,
    PronyTerm,
    ReferenceLinearViscoelasticContent,
)


def _id(value: int) -> UUID:
    return UUID(int=value)


def _source(
    *,
    status: BulkRelaxationStatus = BulkRelaxationStatus.NOT_CHARACTERIZED,
    terms: tuple[PronyTerm, ...] = (
        PronyTerm(0.2, 0.0, 0.1),
        PronyTerm(0.3, 0.0, 10.0),
    ),
) -> ReferenceLinearViscoelasticContent:
    return ReferenceLinearViscoelasticContent(
        material_id=_id(1),
        material_revision_id=_id(2),
        material_state_id=_id(3),
        material_state_revision_id=_id(4),
        property_set_id=_id(5),
        property_set_revision_id=_id(6),
        density_kg_per_m3=1_200.0,
        youngs_modulus_pa=3_000_000_000.0,
        poisson_ratio=0.35,
        bulk_relaxation_status=status,
        terms=terms,
    )


def _target() -> LinearViscoelasticExportTarget:
    return LinearViscoelasticExportTarget("abaqus", "2025", "kg_m_s")


def test_abaqus_preflight_is_explicit_and_deterministic() -> None:
    source = _source()
    first = preflight_reference_linear_viscoelastic_export(
        material_model_id=_id(10),
        material_model_revision_id=_id(11),
        source=source,
        target=_target(),
    )
    second = preflight_reference_linear_viscoelastic_export(
        material_model_id=_id(10),
        material_model_revision_id=_id(11),
        source=source,
        target=_target(),
    )

    assert first.exportable is True
    assert first.digest == second.digest
    statuses = {item.name: item.status for item in first.items}
    assert statuses == {
        "density": "exact",
        "instantaneous_isotropic_elasticity": "exact",
        "shear_prony_terms": "exact",
        "bulk_relaxation": "not_applicable",
        "temperature_dependence": "not_applicable",
        "unit_system": "transformed",
    }


def test_abaqus_card_matches_golden_fixture_and_byte_digest() -> None:
    source = _source()
    report = preflight_reference_linear_viscoelastic_export(
        material_model_id=_id(10),
        material_model_revision_id=_id(11),
        source=source,
        target=_target(),
    )
    _, card = build_reference_linear_viscoelastic_solver_card(
        material_model_id=_id(10),
        material_model_revision_id=_id(11),
        source=source,
        target=_target(),
        expected_mapping_report_sha256=report.digest,
        solver_material_id=42,
        material_name="POLYMER_REFERENCE",
    )

    fixture = (
        Path(__file__).parents[3]
        / "tests"
        / "fixtures"
        / "abaqus"
        / "reference-linear-viscoelastic-prony-kg-m-s.inp"
    )
    assert card.card_text == fixture.read_text(encoding="utf-8")
    assert card.card_sha256 == "42ec1d42d49d055def90121ea6c7728514869ca0e1f302ba878a05d9e0841b4b"
    assert "*VISCOELASTIC, TIME=PRONY, TYPE=ISOTROPIC" in card.card_text
    assert "2.000000000000e-01, 0.000000000000e+00, 1.000000000000e-01" in card.card_text

    with pytest.raises(InvalidLinearViscoelasticExport, match="mapping statuses"):
        replace(card, prony_terms_mapping_status="approximated")


def test_characterized_bulk_ratios_map_exactly() -> None:
    source = _source(
        status=BulkRelaxationStatus.CHARACTERIZED,
        terms=(PronyTerm(0.2, 0.1, 1.0),),
    )
    report = preflight_reference_linear_viscoelastic_export(
        material_model_id=_id(10),
        material_model_revision_id=_id(11),
        source=source,
        target=_target(),
    )
    assert next(item for item in report.items if item.name == "bulk_relaxation").status == "exact"


def test_card_requires_exact_preflight_acknowledgement() -> None:
    with pytest.raises(LinearViscoelasticMappingReportMismatch):
        build_reference_linear_viscoelastic_solver_card(
            material_model_id=_id(10),
            material_model_revision_id=_id(11),
            source=_source(),
            target=_target(),
            expected_mapping_report_sha256="f" * 64,
            solver_material_id=42,
            material_name="POLYMER_REFERENCE",
        )


def test_openradioss_law62_is_not_silently_used_for_linear_prony() -> None:
    target = LinearViscoelasticExportTarget("openradioss", "2025", "kg_m_s")
    report = preflight_reference_linear_viscoelastic_export(
        material_model_id=_id(10),
        material_model_revision_id=_id(11),
        source=_source(),
        target=target,
    )
    assert report.exportable is False
    assert report.items[0].status == "unsupported"
    assert "Ogden-Prony" in report.items[0].detail

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from uuid import UUID

import pytest
from cmp.modules.exporting.domain.openradioss_elast import (
    ExportTarget,
    InvalidExportRequest,
    MappingReportMismatch,
    UnsupportedExportTarget,
    build_reference_openradioss_card,
    mapping_report_from_card_content,
    preflight_reference_openradioss_elast,
)
from cmp.modules.modeling.domain.reference_linear_elasticity import (
    ReferenceLinearElasticContent,
)

MATERIAL = UUID("e1000000-0000-4000-8000-000000000001")
MATERIAL_REVISION = UUID("e1000000-0000-4000-8000-000000000002")
STATE = UUID("e1000000-0000-4000-8000-000000000003")
STATE_REVISION = UUID("e1000000-0000-4000-8000-000000000004")
PROPERTY_SET = UUID("e1000000-0000-4000-8000-000000000005")
PROPERTY_SET_REVISION = UUID("e1000000-0000-4000-8000-000000000006")
MODEL = UUID("e1000000-0000-4000-8000-000000000007")
MODEL_REVISION = UUID("e1000000-0000-4000-8000-000000000008")
TARGET = ExportTarget("openradioss", "2025", "kg_m_s")


def _source() -> ReferenceLinearElasticContent:
    return ReferenceLinearElasticContent(
        material_id=MATERIAL,
        material_revision_id=MATERIAL_REVISION,
        material_state_id=STATE,
        material_state_revision_id=STATE_REVISION,
        property_set_id=PROPERTY_SET,
        property_set_revision_id=PROPERTY_SET_REVISION,
        density_kg_per_m3=7850.0,
        youngs_modulus_pa=210_000_000_000.0,
        poisson_ratio=0.3,
        source_yield_stress_pa=355_000_000.0,
    )


def test_reference_openradioss_card_matches_golden_fixture_and_visible_mapping() -> None:
    report = preflight_reference_openradioss_elast(
        material_model_id=MODEL,
        material_model_revision_id=MODEL_REVISION,
        content=_source(),
        target=TARGET,
    )
    report_statuses = {item.name: item.status for item in report.items}

    assert report.exportable
    assert report.digest == "e7a0c3f86c58b1832ae129eafbb45e28d63c2c7bf160a5f84290276c38595abb"
    assert report_statuses == {
        "density": "exact",
        "youngs_modulus": "exact",
        "poisson_ratio": "exact",
        "source_yield_stress": "not_applicable",
        "temperature_applicability": "not_applicable",
        "strain_rate_applicability": "not_applicable",
        "unit_system": "exact",
    }

    _, card = build_reference_openradioss_card(
        material_model_id=MODEL,
        material_model_revision_id=MODEL_REVISION,
        source=_source(),
        target=TARGET,
        expected_mapping_report_sha256=report.digest,
        solver_material_id=17,
        card_title="Reference steel",
    )
    fixture = (
        Path(__file__).parents[3]
        / "tests"
        / "fixtures"
        / "openradioss"
        / "reference-linear-elasticity-kg-m-s.rad"
    )

    assert card.card_text == fixture.read_text(encoding="utf-8")
    assert card.card_sha256 == "0ccdb395ce67c73810cda0578510ace18307883e4278ce2de385300dd6799c83"
    assert mapping_report_from_card_content(card).digest == report.digest


def test_reference_openradioss_card_rejects_unacknowledged_or_tampered_output() -> None:
    report = preflight_reference_openradioss_elast(
        material_model_id=MODEL,
        material_model_revision_id=MODEL_REVISION,
        content=_source(),
        target=TARGET,
    )
    with pytest.raises(MappingReportMismatch, match="expected_mapping_report_sha256"):
        build_reference_openradioss_card(
            material_model_id=MODEL,
            material_model_revision_id=MODEL_REVISION,
            source=_source(),
            target=TARGET,
            expected_mapping_report_sha256="0" * 64,
            solver_material_id=17,
            card_title="Reference steel",
        )

    _, card = build_reference_openradioss_card(
        material_model_id=MODEL,
        material_model_revision_id=MODEL_REVISION,
        source=_source(),
        target=TARGET,
        expected_mapping_report_sha256=report.digest,
        solver_material_id=17,
        card_title="Reference steel",
    )
    with pytest.raises(InvalidExportRequest, match="card_text does not match"):
        replace(card, card_text=card.card_text.replace("Reference steel", "Altered steel"))


def test_reference_openradioss_card_does_not_silently_export_an_unsupported_target() -> None:
    target = ExportTarget("abaqus", "2025", "kg_m_s")
    report = preflight_reference_openradioss_elast(
        material_model_id=MODEL,
        material_model_revision_id=MODEL_REVISION,
        content=_source(),
        target=target,
    )

    assert not report.exportable
    assert report.items[0].status == "unsupported"
    with pytest.raises(UnsupportedExportTarget):
        build_reference_openradioss_card(
            material_model_id=MODEL,
            material_model_revision_id=MODEL_REVISION,
            source=_source(),
            target=target,
            expected_mapping_report_sha256=report.digest,
            solver_material_id=17,
            card_title="Reference steel",
        )

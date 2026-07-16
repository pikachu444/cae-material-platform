from dataclasses import replace
from pathlib import Path
from uuid import UUID

import pytest
from cmp.modules.exporting.domain.reference_ogden_prony import (
    InvalidOgdenPronyExport,
    OgdenPronyExportTarget,
    OgdenPronyMappingReportMismatch,
    build_reference_ogden_prony_solver_card,
    preflight_reference_ogden_prony_export,
)
from cmp.modules.modeling.domain.reference_ogden_prony import (
    ReferenceOgdenPromotionEvidence,
    ReferenceOgdenPronyContent,
    ReferenceOgdenTerm,
    ReferenceShearPronyTerm,
)


def _id(value: int) -> UUID:
    return UUID(int=value)


def _source() -> ReferenceOgdenPronyContent:
    return ReferenceOgdenPronyContent(
        material_id=_id(1),
        material_revision_id=_id(2),
        material_state_id=_id(3),
        material_state_revision_id=_id(4),
        property_set_id=_id(5),
        property_set_revision_id=_id(6),
        density_kg_per_m3=1_100.0,
        catalog_youngs_modulus_pa=3_000_000.0,
        catalog_poisson_ratio=0.49,
        ogden_term=ReferenceOgdenTerm(1_200_000.0, 2.4),
        prony_terms=(
            ReferenceShearPronyTerm(0.2, 0.1),
            ReferenceShearPronyTerm(0.3, 10.0),
        ),
    )


@pytest.mark.parametrize("solver", ["abaqus", "openradioss"])
def test_preflight_is_explicit_for_both_reference_targets(solver: str) -> None:
    report = preflight_reference_ogden_prony_export(
        material_model_id=_id(10),
        material_model_revision_id=_id(11),
        source=_source(),
        target=OgdenPronyExportTarget(solver, "2025", "kg_m_s"),
    )
    statuses = {item.name: item.status for item in report.items}
    assert report.exportable is True
    assert statuses["density"] == "exact"
    assert statuses["ogden_term"] == "exact"
    assert statuses["shear_prony_terms"] == "exact"
    assert statuses["volumetric_response"] == (
        "exact" if solver == "abaqus" else "approximated"
    )


@pytest.mark.parametrize(
    ("solver", "suffix", "keyword"),
    [("abaqus", ".inp", "*HYPERELASTIC"), ("openradioss", ".rad", "/MAT/LAW62/42/1")],
)
def test_cards_match_byte_golden_fixtures(solver: str, suffix: str, keyword: str) -> None:
    target = OgdenPronyExportTarget(solver, "2025", "kg_m_s")
    report = preflight_reference_ogden_prony_export(
        material_model_id=_id(10),
        material_model_revision_id=_id(11),
        source=_source(),
        target=target,
    )
    _, card = build_reference_ogden_prony_solver_card(
        material_model_id=_id(10),
        material_model_revision_id=_id(11),
        source=_source(),
        target=target,
        expected_mapping_report_sha256=report.digest,
        solver_material_id=42,
        material_name="ELASTOMER_REFERENCE",
    )
    fixture = (
        Path(__file__).parents[3]
        / "tests"
        / "fixtures"
        / solver
        / f"reference-ogden-prony-kg-m-s{suffix}"
    )
    assert keyword in card.card_text
    assert card.card_text == fixture.read_text(encoding="utf-8")
    assert len(card.card_sha256) == 64


def test_card_requires_current_preflight_and_declared_target() -> None:
    with pytest.raises(OgdenPronyMappingReportMismatch):
        build_reference_ogden_prony_solver_card(
            material_model_id=_id(10),
            material_model_revision_id=_id(11),
            source=_source(),
            target=OgdenPronyExportTarget("abaqus", "2025", "kg_m_s"),
            expected_mapping_report_sha256="f" * 64,
            solver_material_id=42,
            material_name="ELASTOMER_REFERENCE",
        )
    report = preflight_reference_ogden_prony_export(
        material_model_id=_id(10),
        material_model_revision_id=_id(11),
        source=_source(),
        target=OgdenPronyExportTarget("ls_dyna", "R15", "kg_m_s"),
    )
    assert report.exportable is False
    assert report.items[0].status == "unsupported"
    with pytest.raises(InvalidOgdenPronyExport, match="unsupported"):
        build_reference_ogden_prony_solver_card(
            material_model_id=_id(10),
            material_model_revision_id=_id(11),
            source=_source(),
            target=OgdenPronyExportTarget("ls_dyna", "R15", "kg_m_s"),
            expected_mapping_report_sha256=report.digest,
            solver_material_id=42,
            material_name="ELASTOMER_REFERENCE",
        )


def test_later_ir_promotion_cannot_change_a_prior_card_payload_or_digest() -> None:
    target = OgdenPronyExportTarget("abaqus", "2025", "kg_m_s")
    prior_source = _source()
    prior_report = preflight_reference_ogden_prony_export(
        material_model_id=_id(10),
        material_model_revision_id=_id(11),
        source=prior_source,
        target=target,
    )
    _, prior_card = build_reference_ogden_prony_solver_card(
        material_model_id=_id(10),
        material_model_revision_id=_id(11),
        source=prior_source,
        target=target,
        expected_mapping_report_sha256=prior_report.digest,
        solver_material_id=42,
        material_name="ELASTOMER_REFERENCE",
    )
    frozen_text = prior_card.card_text
    frozen_digest = prior_card.card_sha256

    promoted_source = replace(
        prior_source,
        ogden_term=ReferenceOgdenTerm(2_000_000.0, 2.0),
        promotion_evidence=ReferenceOgdenPromotionEvidence(
            _id(20),
            _id(21),
            _id(22),
            _id(23),
            "a" * 64,
            _id(24),
            "b" * 64,
            _id(11),
        ),
    )
    promoted_report = preflight_reference_ogden_prony_export(
        material_model_id=_id(10),
        material_model_revision_id=_id(12),
        source=promoted_source,
        target=target,
    )
    _, promoted_card = build_reference_ogden_prony_solver_card(
        material_model_id=_id(10),
        material_model_revision_id=_id(12),
        source=promoted_source,
        target=target,
        expected_mapping_report_sha256=promoted_report.digest,
        solver_material_id=42,
        material_name="ELASTOMER_REFERENCE",
    )

    assert prior_card.card_text == frozen_text
    assert prior_card.card_sha256 == frozen_digest
    assert promoted_card.card_sha256 != frozen_digest

from dataclasses import replace
from uuid import UUID

import pytest
from cmp.modules.modeling.domain.reference_ogden_prony import (
    InvalidReferenceOgdenProny,
    ReferenceOgdenPromotionEvidence,
    ReferenceOgdenPronyContent,
    ReferenceOgdenTerm,
    ReferenceShearPronyTerm,
    incompressible_uniaxial_nominal_stress_pa,
)


def _content() -> ReferenceOgdenPronyContent:
    return ReferenceOgdenPronyContent(
        material_id=UUID(int=1),
        material_revision_id=UUID(int=2),
        material_state_id=UUID(int=3),
        material_state_revision_id=UUID(int=4),
        property_set_id=UUID(int=5),
        property_set_revision_id=UUID(int=6),
        density_kg_per_m3=1100.0,
        catalog_youngs_modulus_pa=3_000_000.0,
        catalog_poisson_ratio=0.49,
        ogden_term=ReferenceOgdenTerm(mu_pa=1_200_000.0, alpha=2.4),
        prony_terms=(
            ReferenceShearPronyTerm(0.2, 0.1),
            ReferenceShearPronyTerm(0.3, 10.0),
        ),
    )


def test_canonical_model_pins_sources_and_instantaneous_convention() -> None:
    content = _content()
    canonical = content.canonical()
    assert canonical["material_revision_id"] == str(UUID(int=2))
    assert canonical["moduli_convention"] == "instantaneous"
    assert canonical["volumetric_response"] == "incompressible"
    assert content.instantaneous_shear_modulus_pa == 1_200_000.0
    assert content.long_term_shear_modulus_pa == pytest.approx(600_000.0)


def test_uniaxial_response_has_zero_reference_stress_and_positive_tension() -> None:
    content = _content()
    assert incompressible_uniaxial_nominal_stress_pa(content, 1.0) == pytest.approx(0.0)
    assert incompressible_uniaxial_nominal_stress_pa(content, 1.5) > 0


def test_each_promoted_revision_canonicalizes_its_own_exact_evidence() -> None:
    content = replace(
        _content(),
        promotion_evidence=ReferenceOgdenPromotionEvidence(
            selection_id=UUID(int=10),
            selection_revision_id=UUID(int=11),
            calibration_run_id=UUID(int=12),
            calibration_candidate_id=UUID(int=13),
            candidate_sha256="a" * 64,
            diagnostics_artifact_id=UUID(int=14),
            diagnostics_sha256="b" * 64,
            promoted_from_model_revision_id=UUID(int=15),
        ),
    )
    evidence = content.canonical()["promotion_evidence"]
    assert isinstance(evidence, dict)
    assert evidence["calibration_candidate_id"] == str(UUID(int=13))
    assert evidence["promoted_from_model_revision_id"] == str(UUID(int=15))


@pytest.mark.parametrize(
    "terms, message",
    [
        ((ReferenceShearPronyTerm(0.6, 0.1), ReferenceShearPronyTerm(0.4, 1.0)), "sum"),
        ((ReferenceShearPronyTerm(0.2, 1.0), ReferenceShearPronyTerm(0.3, 0.1)), "increasing"),
    ],
)
def test_prony_invariants(
    terms: tuple[ReferenceShearPronyTerm, ...], message: str
) -> None:
    with pytest.raises(InvalidReferenceOgdenProny, match=message):
        ReferenceOgdenPronyContent(
            material_id=UUID(int=1),
            material_revision_id=UUID(int=2),
            material_state_id=UUID(int=3),
            material_state_revision_id=UUID(int=4),
            property_set_id=UUID(int=5),
            property_set_revision_id=UUID(int=6),
            density_kg_per_m3=1100.0,
            catalog_youngs_modulus_pa=3_000_000.0,
            catalog_poisson_ratio=0.49,
            ogden_term=ReferenceOgdenTerm(1e6, 2.0),
            prony_terms=terms,
        )

from uuid import UUID

import pytest
from cmp.modules.modeling.domain.reference_linear_viscoelasticity import (
    BulkRelaxationStatus,
    InvalidLinearViscoelasticModel,
    PronyTerm,
    ReferenceLinearViscoelasticContent,
    evaluate_relaxation,
    reference_linear_viscoelastic_canonical,
)


def _id(value: int) -> UUID:
    return UUID(int=value)


def _content(
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


def test_relaxation_response_matches_instantaneous_and_long_time_limits() -> None:
    content = _content()
    points = evaluate_relaxation(content, (0.0, 0.1, 10.0, 1_000.0))
    assert points[0].relaxation_shear_modulus_pa == pytest.approx(
        content.instantaneous_shear_modulus_pa
    )
    assert points[0].relaxation_bulk_modulus_pa == pytest.approx(
        content.instantaneous_bulk_modulus_pa
    )
    assert points[-1].relaxation_shear_modulus_pa == pytest.approx(
        0.5 * content.instantaneous_shear_modulus_pa
    )
    assert points[-1].relaxation_bulk_modulus_pa == pytest.approx(
        content.instantaneous_bulk_modulus_pa
    )


def test_bulk_characterization_is_explicit_and_cannot_silently_default() -> None:
    with pytest.raises(InvalidLinearViscoelasticModel, match="explicit zero"):
        _content(terms=(PronyTerm(0.2, 0.1, 1.0),))
    with pytest.raises(InvalidLinearViscoelasticModel, match="positive k"):
        _content(
            status=BulkRelaxationStatus.CHARACTERIZED,
            terms=(PronyTerm(0.2, 0.0, 1.0),),
        )


@pytest.mark.parametrize(
    "terms, message",
    [
        ((PronyTerm(0.6, 0.0, 1.0), PronyTerm(0.4, 0.0, 2.0)), "sums"),
        ((PronyTerm(0.2, 0.0, 2.0), PronyTerm(0.3, 0.0, 1.0)), "increasing"),
    ],
)
def test_prony_term_invariants(terms: tuple[PronyTerm, ...], message: str) -> None:
    with pytest.raises(InvalidLinearViscoelasticModel, match=message):
        _content(terms=terms)


def test_canonical_ir_pins_every_catalog_revision_and_uses_si_time() -> None:
    canonical = reference_linear_viscoelastic_canonical(_content())
    assert canonical["material_revision_id"] == str(_id(2))
    assert canonical["material_state_revision_id"] == str(_id(4))
    assert canonical["property_set_revision_id"] == str(_id(6))
    assert canonical["elastic_moduli_convention"] == "instantaneous"
    terms = canonical["terms"]
    assert isinstance(terms, list)
    assert terms[0]["relaxation_time_s"] == 0.1
    assert canonical["non_production"] is True

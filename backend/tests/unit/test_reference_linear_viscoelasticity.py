from dataclasses import replace
from uuid import UUID

import pytest
from cmp.modules.modeling.domain.reference_linear_viscoelasticity import (
    REFERENCE_LINEAR_VISCOELASTIC_SCHEMA_DIGEST,
    REFERENCE_PROCESSING_LINEAR_VISCOELASTIC_SCHEMA_DIGEST,
    REFERENCE_RECIPE_PROCESSING_LINEAR_VISCOELASTIC_SCHEMA_DIGEST,
    BulkRelaxationStatus,
    InvalidLinearViscoelasticModel,
    PronyTerm,
    ReferenceLinearViscoelasticContent,
    ReferencePronyProcessingEvidence,
    ReferencePronyPromotionEvidence,
    ReferenceRecipeBatchEvidence,
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
    processing_evidence: ReferencePronyProcessingEvidence | None = None,
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
        processing_promotion_evidence=processing_evidence,
        model_schema_digest=(
            REFERENCE_RECIPE_PROCESSING_LINEAR_VISCOELASTIC_SCHEMA_DIGEST
            if processing_evidence is not None and processing_evidence.recipe_batch is not None
            else REFERENCE_PROCESSING_LINEAR_VISCOELASTIC_SCHEMA_DIGEST
            if processing_evidence is not None
            else REFERENCE_LINEAR_VISCOELASTIC_SCHEMA_DIGEST
        ),
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


def test_promoted_ir_pins_human_selection_candidate_and_diagnostics() -> None:
    evidence = ReferencePronyPromotionEvidence(
        selection_id=_id(7),
        selection_revision_id=_id(8),
        calibration_run_id=_id(9),
        calibration_candidate_id=_id(10),
        candidate_sha256="a" * 64,
        diagnostics_artifact_id=_id(11),
        diagnostics_sha256="b" * 64,
    )
    content = replace(_content(), prony_promotion_evidence=evidence)
    canonical = reference_linear_viscoelastic_canonical(content)
    promotion = canonical["prony_promotion_evidence"]
    assert isinstance(promotion, dict)
    assert promotion["selection_revision_id"] == str(_id(8))
    assert promotion["candidate_sha256"] == "a" * 64
    assert promotion["diagnostics_sha256"] == "b" * 64


def test_processing_promoted_ir_supports_ten_terms_and_pins_exact_evidence() -> None:
    terms = tuple(PronyTerm(0.05, 0.0, float(index)) for index in range(1, 11))
    evidence = ReferencePronyProcessingEvidence(
        processing_output_id=_id(20),
        processing_output_revision_id=_id(21),
        processing_output_sha256="c" * 64,
        source_test_data_id=_id(22),
        source_test_data_revision_id=_id(23),
        mapping_profile_id=_id(24),
        mapping_profile_revision_id=_id(25),
        selection_mode="automatic_bic",
        selected_term_count=10,
        normalized_rmse=0.012,
        bic=-41.5,
        fitted_instantaneous_shear_modulus_pa=1_100_000_000.0,
        catalog_instantaneous_shear_modulus_pa=1_111_111_111.0,
        instantaneous_modulus_relative_mismatch=0.01,
        acknowledged_maximum_relative_mismatch=0.05,
        recipe_batch=ReferenceRecipeBatchEvidence(
            recipe_id=_id(26),
            recipe_revision_id=_id(27),
            recipe_sha256="d" * 64,
            batch_id=_id(28),
            batch_member_id=_id(29),
            batch_attempt_id=_id(30),
            batch_attempt_no=1,
        ),
    )
    content = _content(terms=terms, processing_evidence=evidence)

    canonical = reference_linear_viscoelastic_canonical(content)

    canonical_terms = canonical["terms"]
    assert isinstance(canonical_terms, list)
    assert len(canonical_terms) == 10
    processing = canonical["processing_promotion_evidence"]
    assert isinstance(processing, dict)
    assert processing["processing_output"]["revision_id"] == str(_id(21))
    assert processing["selected_term_count"] == 10
    assert processing["bic"] == -41.5
    recipe_batch = processing["recipe_batch"]
    assert isinstance(recipe_batch, dict)
    assert recipe_batch["processing_recipe"]["revision_id"] == str(_id(27))
    assert recipe_batch["batch_attempt_no"] == 1


def test_recipe_batch_evidence_rejects_invalid_digest_and_attempt_number() -> None:
    with pytest.raises(InvalidLinearViscoelasticModel, match="recipe_sha256"):
        ReferenceRecipeBatchEvidence(_id(1), _id(2), "invalid", _id(3), _id(4), _id(5), 1)
    with pytest.raises(InvalidLinearViscoelasticModel, match="attempt_no"):
        ReferenceRecipeBatchEvidence(_id(1), _id(2), "a" * 64, _id(3), _id(4), _id(5), 0)


def test_manual_ir_cannot_claim_processing_term_limit_or_mixed_evidence() -> None:
    terms = tuple(PronyTerm(0.05, 0.0, float(index)) for index in range(1, 7))
    with pytest.raises(InvalidLinearViscoelasticModel, match="between 1 and 5"):
        _content(terms=terms)

    candidate = ReferencePronyPromotionEvidence(
        selection_id=_id(7),
        selection_revision_id=_id(8),
        calibration_run_id=_id(9),
        calibration_candidate_id=_id(10),
        candidate_sha256="a" * 64,
        diagnostics_artifact_id=_id(11),
        diagnostics_sha256="b" * 64,
    )
    processing = ReferencePronyProcessingEvidence(
        processing_output_id=_id(20),
        processing_output_revision_id=_id(21),
        processing_output_sha256="c" * 64,
        source_test_data_id=_id(22),
        source_test_data_revision_id=_id(23),
        mapping_profile_id=_id(24),
        mapping_profile_revision_id=_id(25),
        selection_mode="manual",
        selected_term_count=2,
        normalized_rmse=0.02,
        bic=1.0,
        fitted_instantaneous_shear_modulus_pa=1_100_000_000.0,
        catalog_instantaneous_shear_modulus_pa=1_111_111_111.0,
        instantaneous_modulus_relative_mismatch=0.01,
        acknowledged_maximum_relative_mismatch=0.05,
    )
    with pytest.raises(InvalidLinearViscoelasticModel, match="cannot mix"):
        replace(
            _content(),
            prony_promotion_evidence=candidate,
            processing_promotion_evidence=processing,
        )

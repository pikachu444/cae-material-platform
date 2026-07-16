from __future__ import annotations

import pytest
from cmp.modules.modeling.domain.scientific_profile import (
    InvalidScientificProfile,
    OgdenScientificParameters,
    PronyScientificParameters,
    ScientificApprovalStatus,
    ScientificProfileContent,
    ScientificProfileFamily,
    VoceScientificParameters,
)


def test_each_scientific_profile_has_an_explicit_family_parameter_block() -> None:
    voce = ScientificProfileContent(
        "Reference steel Voce",
        ScientificProfileFamily.STEEL_VOCE,
        ScientificApprovalStatus.REFERENCE_UNAPPROVED,
        5,
        17,
        voce=VoceScientificParameters(
            300e6, 100e6, 800e6, 300e6, 250e6, 1e6, 1e9, 250e6, 10, 0.1, 100, 10
        ),
    )
    prony = ScientificProfileContent(
        "Reference polymer Prony",
        ScientificProfileFamily.POLYMER_LINEAR_PRONY,
        ScientificApprovalStatus.REFERENCE_UNAPPROVED,
        5,
        18,
        prony=PronyScientificParameters(1, 10, 0.95, 1e-6, 1e6),
    )
    ogden = ScientificProfileContent(
        "Reference elastomer Ogden",
        ScientificProfileFamily.ELASTOMER_OGDEN_PRONY,
        ScientificApprovalStatus.REFERENCE_UNAPPROVED,
        8,
        19,
        ogden=OgdenScientificParameters(1e6, 1e3, 100e6, 1e6, 2.0, 0.1, 20, 2.0),
    )

    assert voce.parameter_block["sigma0_initial_pa"] == 300e6
    assert prony.parameter_block["term_count_max"] == 10
    assert ogden.parameter_block["alpha_upper"] == 20
    assert all(
        item.canonical()["approval_status"] == "reference_unapproved"
        for item in (voce, prony, ogden)
    )


def test_profile_rejects_generic_or_mismatched_parameter_payloads() -> None:
    with pytest.raises(InvalidScientificProfile, match="exactly its family-specific"):
        ScientificProfileContent(
            "Mismatched profile",
            ScientificProfileFamily.ELASTOMER_OGDEN_PRONY,
            ScientificApprovalStatus.REFERENCE_UNAPPROVED,
            4,
            1,
            prony=PronyScientificParameters(1, 2, 0.9, 1e-3, 1e3),
        )
    with pytest.raises(InvalidScientificProfile, match="lower < initial < upper"):
        OgdenScientificParameters(1e6, 2e6, 3e6, 1e6, 2.0, 0.1, 10.0, 2.0)

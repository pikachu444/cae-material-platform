from __future__ import annotations

import pytest
from cmp.modules.modeling.application.fit_decision_evidence import (
    selected_hardening_quantity,
)
from cmp.modules.modeling.domain.fit_decision_evidence import (
    FitDecisionEvidence,
    FitParameterEvidence,
    FitParameterSetEvidence,
    InvalidFitDecisionEvidence,
    fit_decision_evidence_from_canonical,
)
from cmp.modules.processing.application.common_outputs import (
    FitDecisionParameter,
    FitDecisionParameterSet,
    FitDecisionSnapshot,
)


def _parameter_set(law: str, value: float) -> FitParameterSetEvidence:
    return FitParameterSetEvidence(
        law,
        (
            FitParameterEvidence(
                name="strength",
                value=value,
                unit="Pa",
                lower=value * 0.5,
                upper=value * 1.5,
            ),
        ),
    )


def test_blend_fit_decision_round_trip_preserves_both_parameter_sets_and_digest() -> None:
    decision = FitDecisionEvidence(
        candidate_key="swift+voce",
        mode="blend",
        primary_law="swift",
        secondary_law="voce",
        primary_weight=0.65,
        parameter_sets=(
            _parameter_set("swift", 500e6),
            _parameter_set("voce", 450e6),
        ),
        fit_minimum=0.01,
        fit_maximum=0.12,
        extrapolation_maximum=0.2,
        extrapolation_policy="bounded",
        metric_definition="relative_rmse",
        metric_value=0.012,
        requested_term_policy=None,
        actual_term_count=None,
        selection_reason="The blend remains stable over the bounded extension.",
        warning_acknowledged=True,
    )

    restored = fit_decision_evidence_from_canonical(decision.canonical())

    assert restored == decision
    assert restored is not None
    assert restored.digest == decision.digest
    assert tuple(item.law for item in restored.parameter_sets) == ("swift", "voce")


def test_fit_decision_rejects_parameter_sets_that_do_not_match_selected_identity() -> None:
    with pytest.raises(InvalidFitDecisionEvidence, match="selected law identity"):
        FitDecisionEvidence(
            candidate_key="swift+voce",
            mode="blend",
            primary_law="swift",
            secondary_law="voce",
            primary_weight=0.65,
            parameter_sets=(
                _parameter_set("voce", 450e6),
                _parameter_set("swift", 500e6),
            ),
            fit_minimum=0.01,
            fit_maximum=0.12,
            extrapolation_maximum=0.2,
            extrapolation_policy="bounded",
            metric_definition="relative_rmse",
            metric_value=0.012,
            requested_term_policy=None,
            actual_term_count=None,
            selection_reason="This ordering is inconsistent.",
            warning_acknowledged=True,
        )


def test_selected_hardening_quantity_tracks_single_and_blend_identity() -> None:
    single = FitDecisionSnapshot(
        candidate_key="swift",
        mode="single",
        primary_law="swift",
        secondary_law=None,
        primary_weight=None,
        parameter_sets=(
            FitDecisionParameterSet(
                "swift",
                (FitDecisionParameter("K", 500e6, "Pa", 1.0, 1e9),),
            ),
        ),
        fit_minimum=0.01,
        fit_maximum=0.12,
        extrapolation_maximum=0.2,
        extrapolation_policy="bounded",
        metric_definition="relative_rmse",
        metric_value=0.01,
        requested_term_policy=None,
        actual_term_count=None,
        selection_reason="Select the single Swift curve.",
        warning_acknowledged=False,
    )
    blend = FitDecisionSnapshot(
        candidate_key="swift+voce",
        mode="blend",
        primary_law="swift",
        secondary_law="voce",
        primary_weight=0.6,
        parameter_sets=(
            single.parameter_sets[0],
            FitDecisionParameterSet(
                "voce",
                (FitDecisionParameter("sigma_sat", 700e6, "Pa", 1.0, 1e9),),
            ),
        ),
        fit_minimum=0.01,
        fit_maximum=0.12,
        extrapolation_maximum=0.2,
        extrapolation_policy="bounded",
        metric_definition="relative_rmse",
        metric_value=0.01,
        requested_term_policy=None,
        actual_term_count=None,
        selection_reason="Select the exact calculated blend.",
        warning_acknowledged=False,
    )

    assert selected_hardening_quantity(single) == "stress.hardening.swift"
    assert selected_hardening_quantity(blend) == "stress.hardening.selected"

"""Application adapter from a validated Processing decision to Modeling provenance."""

from cmp.modules.modeling.domain.fit_decision_evidence import (
    FitDecisionEvidence,
    FitParameterEvidence,
    FitParameterSetEvidence,
)
from cmp.modules.processing.application.common_outputs import FitDecisionSnapshot


def selected_hardening_quantity(value: FitDecisionSnapshot) -> str:
    """Resolve the curve series represented by the exact saved metal decision."""
    return (
        "stress.hardening.selected"
        if value.mode == "blend"
        else f"stress.hardening.{value.primary_law}"
    )


def modeling_fit_decision_evidence(value: FitDecisionSnapshot) -> FitDecisionEvidence:
    return FitDecisionEvidence(
        candidate_key=value.candidate_key,
        mode=value.mode,
        primary_law=value.primary_law,
        secondary_law=value.secondary_law,
        primary_weight=value.primary_weight,
        parameter_sets=tuple(
            FitParameterSetEvidence(
                law=parameter_set.law,
                parameters=tuple(
                    FitParameterEvidence(
                        name=parameter.name,
                        value=parameter.value,
                        unit=parameter.unit,
                        lower=parameter.lower,
                        upper=parameter.upper,
                    )
                    for parameter in parameter_set.parameters
                ),
            )
            for parameter_set in value.parameter_sets
        ),
        fit_minimum=value.fit_minimum,
        fit_maximum=value.fit_maximum,
        extrapolation_maximum=value.extrapolation_maximum,
        extrapolation_policy=value.extrapolation_policy,
        metric_definition=value.metric_definition,
        metric_value=value.metric_value,
        requested_term_policy=value.requested_term_policy,
        actual_term_count=value.actual_term_count,
        selection_reason=value.selection_reason,
        warning_acknowledged=value.warning_acknowledged,
    )

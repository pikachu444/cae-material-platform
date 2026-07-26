"""Typed provenance for one explicitly saved Fit decision.

This evidence is descriptive only.  It preserves the identity already validated
against an immutable Processing Output; it does not change constitutive math,
solver mapping, or numeric reference results.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from cmp.shared.domain.revisions import canonical_json_bytes


class InvalidFitDecisionEvidence(ValueError):
    pass


def _text(name: str, value: str, limit: int = 160) -> None:
    if not value or value != value.strip() or len(value) > limit or "\x00" in value:
        raise InvalidFitDecisionEvidence(
            f"{name} must be trimmed and contain 1..{limit} characters"
        )


@dataclass(frozen=True, slots=True)
class FitParameterEvidence:
    name: str
    value: float
    unit: str
    lower: float | None = None
    upper: float | None = None

    def __post_init__(self) -> None:
        _text("parameter name", self.name)
        _text("parameter unit", self.unit)
        if not math.isfinite(self.value):
            raise InvalidFitDecisionEvidence("parameter value must be finite")
        if self.lower is not None and (not math.isfinite(self.lower) or self.lower > self.value):
            raise InvalidFitDecisionEvidence("parameter lower bound is invalid")
        if self.upper is not None and (not math.isfinite(self.upper) or self.upper < self.value):
            raise InvalidFitDecisionEvidence("parameter upper bound is invalid")

    def canonical(self) -> dict[str, object]:
        return {
            "name": self.name,
            "value": self.value,
            "unit": self.unit,
            "lower": self.lower,
            "upper": self.upper,
        }


@dataclass(frozen=True, slots=True)
class FitParameterSetEvidence:
    law: str
    parameters: tuple[FitParameterEvidence, ...]

    def __post_init__(self) -> None:
        _text("parameter-set law", self.law)
        if not self.parameters or len(self.parameters) > 32:
            raise InvalidFitDecisionEvidence("parameter set must contain 1..32 parameters")
        if len({parameter.name for parameter in self.parameters}) != len(self.parameters):
            raise InvalidFitDecisionEvidence("parameter names must be unique within one law")

    def canonical(self) -> dict[str, object]:
        return {
            "law": self.law,
            "parameters": [parameter.canonical() for parameter in self.parameters],
        }


@dataclass(frozen=True, slots=True)
class FitDecisionEvidence:
    candidate_key: str
    mode: str
    primary_law: str
    secondary_law: str | None
    primary_weight: float | None
    parameter_sets: tuple[FitParameterSetEvidence, ...]
    fit_minimum: float
    fit_maximum: float
    extrapolation_maximum: float | None
    extrapolation_policy: str
    metric_definition: str
    metric_value: float
    requested_term_policy: str | None
    actual_term_count: int | None
    selection_reason: str
    warning_acknowledged: bool

    def __post_init__(self) -> None:
        for name, value, limit in (
            ("candidate key", self.candidate_key, 160),
            ("primary law", self.primary_law, 160),
            ("extrapolation policy", self.extrapolation_policy, 160),
            ("metric definition", self.metric_definition, 160),
            ("selection reason", self.selection_reason, 2000),
        ):
            _text(name, value, limit)
        if self.mode not in {"single", "blend"}:
            raise InvalidFitDecisionEvidence("fit decision mode must be single or blend")
        if not all(
            math.isfinite(value)
            for value in (self.fit_minimum, self.fit_maximum, self.metric_value)
        ) or self.fit_minimum >= self.fit_maximum:
            raise InvalidFitDecisionEvidence("fit decision range or metric is invalid")
        if self.extrapolation_maximum is not None and (
            not math.isfinite(self.extrapolation_maximum)
            or self.extrapolation_maximum < self.fit_maximum
        ):
            raise InvalidFitDecisionEvidence("extrapolation maximum is invalid")
        if self.requested_term_policy is not None:
            _text("requested term policy", self.requested_term_policy)
        if self.mode == "single":
            if (
                self.secondary_law is not None
                or self.primary_weight is not None
                or len(self.parameter_sets) != 1
            ):
                raise InvalidFitDecisionEvidence(
                    "single fit identity requires one parameter set and no blend fields"
                )
        else:
            if (
                self.secondary_law is None
                or self.secondary_law == self.primary_law
                or self.primary_weight is None
                or not 0 < self.primary_weight < 1
                or len(self.parameter_sets) != 2
            ):
                raise InvalidFitDecisionEvidence(
                    "blend fit identity requires distinct laws, ratio, and two parameter sets"
                )
        expected_laws = (
            (self.primary_law,)
            if self.mode == "single"
            else (self.primary_law, str(self.secondary_law))
        )
        if tuple(item.law for item in self.parameter_sets) != expected_laws:
            raise InvalidFitDecisionEvidence(
                "fit parameter sets must follow the selected law identity"
            )
        if self.actual_term_count is not None and (
            not 1 <= self.actual_term_count <= 10 or self.mode != "single"
        ):
            raise InvalidFitDecisionEvidence(
                "actual term count requires a single 1..10-term result"
            )

    def canonical(self) -> dict[str, object]:
        return {
            "candidate_key": self.candidate_key,
            "mode": self.mode,
            "primary_law": self.primary_law,
            "secondary_law": self.secondary_law,
            "primary_weight": self.primary_weight,
            "parameter_sets": [parameter_set.canonical() for parameter_set in self.parameter_sets],
            "fit_minimum": self.fit_minimum,
            "fit_maximum": self.fit_maximum,
            "extrapolation_maximum": self.extrapolation_maximum,
            "extrapolation_policy": self.extrapolation_policy,
            "metric_definition": self.metric_definition,
            "metric_value": self.metric_value,
            "requested_term_policy": self.requested_term_policy,
            "actual_term_count": self.actual_term_count,
            "selection_reason": self.selection_reason,
            "warning_acknowledged": self.warning_acknowledged,
        }

    @property
    def digest(self) -> str:
        import hashlib

        return hashlib.sha256(canonical_json_bytes(self.canonical())).hexdigest()

    @property
    def display_label(self) -> str:
        if self.actual_term_count is not None:
            return f"{self.actual_term_count}-term Generalized Maxwell"
        if self.mode == "blend":
            assert self.secondary_law is not None and self.primary_weight is not None
            primary_percent = round(self.primary_weight * 100)
            return (
                f"{self.primary_law} + {self.secondary_law} "
                f"{primary_percent}/{100 - primary_percent}"
            )
        return self.primary_law


def fit_decision_evidence_from_canonical(value: object) -> FitDecisionEvidence | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise InvalidFitDecisionEvidence("fit decision evidence must be an object")
    return FitDecisionEvidence(
        candidate_key=str(value["candidate_key"]),
        mode=str(value["mode"]),
        primary_law=str(value["primary_law"]),
        secondary_law=(
            None if value.get("secondary_law") is None else str(value["secondary_law"])
        ),
        primary_weight=(
            None if value.get("primary_weight") is None else float(value["primary_weight"])
        ),
        parameter_sets=tuple(
            FitParameterSetEvidence(
                law=str(parameter_set["law"]),
                parameters=tuple(
                    FitParameterEvidence(
                        name=str(parameter["name"]),
                        value=float(parameter["value"]),
                        unit=str(parameter["unit"]),
                        lower=(
                            None if parameter.get("lower") is None else float(parameter["lower"])
                        ),
                        upper=(
                            None if parameter.get("upper") is None else float(parameter["upper"])
                        ),
                    )
                    for parameter in parameter_set["parameters"]
                ),
            )
            for parameter_set in value["parameter_sets"]
        ),
        fit_minimum=float(value["fit_minimum"]),
        fit_maximum=float(value["fit_maximum"]),
        extrapolation_maximum=(
            None
            if value.get("extrapolation_maximum") is None
            else float(value["extrapolation_maximum"])
        ),
        extrapolation_policy=str(value["extrapolation_policy"]),
        metric_definition=str(value["metric_definition"]),
        metric_value=float(value["metric_value"]),
        requested_term_policy=(
            None
            if value.get("requested_term_policy") is None
            else str(value["requested_term_policy"])
        ),
        actual_term_count=(
            None if value.get("actual_term_count") is None else int(value["actual_term_count"])
        ),
        selection_reason=str(value["selection_reason"]),
        warning_acknowledged=bool(value["warning_acknowledged"]),
    )

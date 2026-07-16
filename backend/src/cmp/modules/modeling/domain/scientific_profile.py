"""Versioned, model-family-specific scientific calibration profiles."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

from cmp.modules.modeling.domain.reference_linear_viscoelasticity import (
    REFERENCE_LINEAR_VISCOELASTIC_FAMILY_ID,
)
from cmp.modules.modeling.domain.reference_ogden_prony import REFERENCE_OGDEN_PRONY_FAMILY_ID
from cmp.modules.modeling.domain.reference_voce_calibration import REFERENCE_VOCE_MODEL_FAMILY_ID

SCIENTIFIC_PROFILE_SCHEMA_ID = "urn:cmp:modeling:scientific-calibration-profile:1.0.0"
SCIENTIFIC_PROFILE_SCHEMA_VERSION = "1.0.0"


class InvalidScientificProfile(ValueError):
    pass


class ScientificProfileNotFound(Exception):
    pass


class ScientificProfileConflict(Exception):
    pass


class ScientificProfileFamily(StrEnum):
    STEEL_VOCE = "steel_voce"
    POLYMER_LINEAR_PRONY = "polymer_linear_prony"
    ELASTOMER_OGDEN_PRONY = "elastomer_ogden_prony"

    @property
    def model_family_id(self) -> str:
        return {
            self.STEEL_VOCE: REFERENCE_VOCE_MODEL_FAMILY_ID,
            self.POLYMER_LINEAR_PRONY: REFERENCE_LINEAR_VISCOELASTIC_FAMILY_ID,
            self.ELASTOMER_OGDEN_PRONY: REFERENCE_OGDEN_PRONY_FAMILY_ID,
        }[self]


class ScientificApprovalStatus(StrEnum):
    REFERENCE_UNAPPROVED = "reference_unapproved"
    DOMAIN_APPROVED = "domain_approved"


def _positive(name: str, value: float) -> None:
    if not math.isfinite(value) or value <= 0:
        raise InvalidScientificProfile(f"{name} must be finite and greater than zero")


def _bounds(name: str, initial: float, lower: float, upper: float, scale: float) -> None:
    for field, value in (
        (f"{name}_initial", initial),
        (f"{name}_lower", lower),
        (f"{name}_upper", upper),
        (f"{name}_scale", scale),
    ):
        _positive(field, value)
    if not lower < initial < upper:
        raise InvalidScientificProfile(f"{name} requires lower < initial < upper")


@dataclass(frozen=True, slots=True)
class VoceScientificParameters:
    sigma0_initial_pa: float
    sigma0_lower_pa: float
    sigma0_upper_pa: float
    sigma0_scale_pa: float
    q_initial_pa: float
    q_lower_pa: float
    q_upper_pa: float
    q_scale_pa: float
    b_initial: float
    b_lower: float
    b_upper: float
    b_scale: float

    def __post_init__(self) -> None:
        _bounds(
            "sigma0",
            self.sigma0_initial_pa,
            self.sigma0_lower_pa,
            self.sigma0_upper_pa,
            self.sigma0_scale_pa,
        )
        _bounds("q", self.q_initial_pa, self.q_lower_pa, self.q_upper_pa, self.q_scale_pa)
        _bounds("b", self.b_initial, self.b_lower, self.b_upper, self.b_scale)

    def canonical(self) -> dict[str, object]:
        return {
            "sigma0_initial_pa": self.sigma0_initial_pa,
            "sigma0_lower_pa": self.sigma0_lower_pa,
            "sigma0_upper_pa": self.sigma0_upper_pa,
            "sigma0_scale_pa": self.sigma0_scale_pa,
            "q_initial_pa": self.q_initial_pa,
            "q_lower_pa": self.q_lower_pa,
            "q_upper_pa": self.q_upper_pa,
            "q_scale_pa": self.q_scale_pa,
            "b_initial": self.b_initial,
            "b_lower": self.b_lower,
            "b_upper": self.b_upper,
            "b_scale": self.b_scale,
        }


@dataclass(frozen=True, slots=True)
class PronyScientificParameters:
    term_count_min: int
    term_count_max: int
    total_shear_ratio_upper: float
    relaxation_time_lower_s: float
    relaxation_time_upper_s: float

    def __post_init__(self) -> None:
        if not 1 <= self.term_count_min <= self.term_count_max <= 10:
            raise InvalidScientificProfile("Prony term count range must remain within 1..10")
        if (
            not math.isfinite(self.total_shear_ratio_upper)
            or not 0 < self.total_shear_ratio_upper < 1
        ):
            raise InvalidScientificProfile(
                "Prony total shear ratio upper bound must be within (0,1)"
            )
        _positive("relaxation_time_lower_s", self.relaxation_time_lower_s)
        _positive("relaxation_time_upper_s", self.relaxation_time_upper_s)
        if self.relaxation_time_lower_s >= self.relaxation_time_upper_s:
            raise InvalidScientificProfile("Prony relaxation time bounds must be ordered")

    def canonical(self) -> dict[str, object]:
        return {
            "term_count_min": self.term_count_min,
            "term_count_max": self.term_count_max,
            "total_shear_ratio_upper": self.total_shear_ratio_upper,
            "relaxation_time_lower_s": self.relaxation_time_lower_s,
            "relaxation_time_upper_s": self.relaxation_time_upper_s,
            "time_transform": "log",
        }


@dataclass(frozen=True, slots=True)
class OgdenScientificParameters:
    mu_initial_pa: float
    mu_lower_pa: float
    mu_upper_pa: float
    mu_scale_pa: float
    alpha_initial: float
    alpha_lower: float
    alpha_upper: float
    alpha_scale: float
    uniaxial_weight: float = 1.0
    planar_weight: float = 1.0
    biaxial_weight: float = 1.0

    def __post_init__(self) -> None:
        _bounds("mu", self.mu_initial_pa, self.mu_lower_pa, self.mu_upper_pa, self.mu_scale_pa)
        _bounds(
            "alpha",
            self.alpha_initial,
            self.alpha_lower,
            self.alpha_upper,
            self.alpha_scale,
        )
        for name, value in (
            ("uniaxial_weight", self.uniaxial_weight),
            ("planar_weight", self.planar_weight),
            ("biaxial_weight", self.biaxial_weight),
        ):
            _positive(name, value)

    def canonical(self) -> dict[str, object]:
        return {
            "mu_initial_pa": self.mu_initial_pa,
            "mu_lower_pa": self.mu_lower_pa,
            "mu_upper_pa": self.mu_upper_pa,
            "mu_scale_pa": self.mu_scale_pa,
            "alpha_initial": self.alpha_initial,
            "alpha_lower": self.alpha_lower,
            "alpha_upper": self.alpha_upper,
            "alpha_scale": self.alpha_scale,
            "uniaxial_weight": self.uniaxial_weight,
            "planar_weight": self.planar_weight,
            "biaxial_weight": self.biaxial_weight,
        }


@dataclass(frozen=True, slots=True)
class ScientificProfileContent:
    profile_label: str
    family: ScientificProfileFamily
    approval_status: ScientificApprovalStatus
    multistart_count: int
    seed: int
    voce: VoceScientificParameters | None = None
    prony: PronyScientificParameters | None = None
    ogden: OgdenScientificParameters | None = None
    optimizer: str = "scipy_least_squares_trf"
    residual_definition: str = "normalized_weighted_least_squares"
    aggregation_order: str = "point_then_curve_then_mode"
    missing_data_policy: str = "reject"
    holdout_policy: str = "explicit_disjoint"
    uncertainty_policy: str = "jacobian_covariance_or_not_estimable"
    status_note: str = "Reference profile; domain sign-off is not recorded."

    def __post_init__(self) -> None:
        if (
            not self.profile_label
            or self.profile_label != self.profile_label.strip()
            or len(self.profile_label) > 160
            or "\x00" in self.profile_label
        ):
            raise InvalidScientificProfile(
                "profile_label must be trimmed and contain 1..160 characters"
            )
        if not 1 <= self.multistart_count <= 32:
            raise InvalidScientificProfile("multistart_count must be within 1..32")
        if not 0 <= self.seed <= 2_147_483_647:
            raise InvalidScientificProfile("seed must be within signed 32-bit range")
        selected = (self.voce is not None, self.prony is not None, self.ogden is not None)
        expected = {
            ScientificProfileFamily.STEEL_VOCE: (True, False, False),
            ScientificProfileFamily.POLYMER_LINEAR_PRONY: (False, True, False),
            ScientificProfileFamily.ELASTOMER_OGDEN_PRONY: (False, False, True),
        }[self.family]
        if selected != expected:
            raise InvalidScientificProfile(
                "scientific profile must carry exactly its family-specific parameter block"
            )
        if (
            self.optimizer != "scipy_least_squares_trf"
            or self.residual_definition != "normalized_weighted_least_squares"
            or self.aggregation_order != "point_then_curve_then_mode"
            or self.missing_data_policy != "reject"
            or self.holdout_policy != "explicit_disjoint"
            or self.uncertainty_policy != "jacobian_covariance_or_not_estimable"
        ):
            raise InvalidScientificProfile("reference scientific policy is explicit and fixed")
        if (
            not self.status_note
            or self.status_note != self.status_note.strip()
            or len(self.status_note) > 500
        ):
            raise InvalidScientificProfile("status_note must contain 1..500 trimmed characters")

    @property
    def parameter_block(self) -> dict[str, object]:
        value = self.voce or self.prony or self.ogden
        if value is None:  # pragma: no cover - protected by construction
            raise InvalidScientificProfile("family parameter block is absent")
        return value.canonical()

    def canonical(self) -> dict[str, object]:
        return {
            "profile_label": self.profile_label,
            "family": self.family.value,
            "model_family_id": self.family.model_family_id,
            "approval_status": self.approval_status.value,
            "optimizer": self.optimizer,
            "residual_definition": self.residual_definition,
            "aggregation_order": self.aggregation_order,
            "missing_data_policy": self.missing_data_policy,
            "holdout_policy": self.holdout_policy,
            "uncertainty_policy": self.uncertainty_policy,
            "multistart_count": self.multistart_count,
            "seed": self.seed,
            "status_note": self.status_note,
            "parameters": self.parameter_block,
        }


def scientific_profile_canonical(value: ScientificProfileContent) -> dict[str, object]:
    return value.canonical()

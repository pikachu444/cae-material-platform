"""Solver-neutral reference linear viscoelasticity with explicit Prony terms."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from enum import StrEnum
from itertools import pairwise
from uuid import UUID

REFERENCE_LINEAR_VISCOELASTIC_FAMILY_ID = (
    "urn:cmp:reference:isotropic-linear-viscoelastic-prony:1.0.0"
)
REFERENCE_LINEAR_VISCOELASTIC_SCHEMA_ID = (
    "urn:cmp:modeling:reference-isotropic-linear-viscoelastic-prony:1.0.0"
)
REFERENCE_LINEAR_VISCOELASTIC_SCHEMA_VERSION = "1.0.0"

_SCHEMA_DOCUMENT = {
    "family": REFERENCE_LINEAR_VISCOELASTIC_FAMILY_ID,
    "version": REFERENCE_LINEAR_VISCOELASTIC_SCHEMA_VERSION,
    "elastic_moduli_convention": "instantaneous",
    "time_unit": "s",
    "terms": ["g_ratio", "k_ratio", "relaxation_time_s"],
    "bulk_status": ["characterized", "not_characterized"],
    "term_count": [1, 5],
}
REFERENCE_LINEAR_VISCOELASTIC_SCHEMA_DIGEST = hashlib.sha256(
    json.dumps(_SCHEMA_DOCUMENT, sort_keys=True, separators=(",", ":")).encode("utf-8")
).hexdigest()


class LinearViscoelasticError(Exception):
    """Base error for the bounded reference linear-viscoelastic family."""


class InvalidLinearViscoelasticModel(LinearViscoelasticError, ValueError):
    """The manual IR input violates physical or semantic invariants."""


class LinearViscoelasticConflict(LinearViscoelasticError):
    """Pinned sources or workflow compatibility conflict."""


class LinearViscoelasticNotFound(LinearViscoelasticError):
    """The requested visible reference IR does not exist."""


class BulkRelaxationStatus(StrEnum):
    CHARACTERIZED = "characterized"
    NOT_CHARACTERIZED = "not_characterized"


def _finite_positive(name: str, value: float) -> None:
    if not math.isfinite(value) or value <= 0:
        raise InvalidLinearViscoelasticModel(f"{name} must be finite and greater than zero")


def _nonzero(name: str, value: UUID) -> None:
    if value.int == 0:
        raise InvalidLinearViscoelasticModel(f"{name} must be non-zero")


@dataclass(frozen=True, slots=True)
class PronyTerm:
    g_ratio: float
    k_ratio: float
    relaxation_time_s: float

    def __post_init__(self) -> None:
        for name, value in (("g_ratio", self.g_ratio), ("k_ratio", self.k_ratio)):
            if not math.isfinite(value) or not 0 <= value < 1:
                raise InvalidLinearViscoelasticModel(f"{name} must be finite within [0, 1)")
        _finite_positive("relaxation_time_s", self.relaxation_time_s)


@dataclass(frozen=True, slots=True)
class ReferenceLinearViscoelasticContent:
    material_id: UUID
    material_revision_id: UUID
    material_state_id: UUID
    material_state_revision_id: UUID
    property_set_id: UUID
    property_set_revision_id: UUID
    density_kg_per_m3: float
    youngs_modulus_pa: float
    poisson_ratio: float
    bulk_relaxation_status: BulkRelaxationStatus
    terms: tuple[PronyTerm, ...]
    applicable_temperature_min_k: float | None = None
    applicable_temperature_max_k: float | None = None
    applicable_strain_rate_min_per_s: float | None = None
    applicable_strain_rate_max_per_s: float | None = None
    applicability_note: str | None = None
    reference_temperature_k: float = 293.15
    model_family_id: str = REFERENCE_LINEAR_VISCOELASTIC_FAMILY_ID
    model_schema_digest: str = REFERENCE_LINEAR_VISCOELASTIC_SCHEMA_DIGEST
    elastic_moduli_convention: str = "instantaneous"
    non_production: bool = True

    def __post_init__(self) -> None:
        for name in (
            "material_id",
            "material_revision_id",
            "material_state_id",
            "material_state_revision_id",
            "property_set_id",
            "property_set_revision_id",
        ):
            _nonzero(name, getattr(self, name))
        _finite_positive("density_kg_per_m3", self.density_kg_per_m3)
        _finite_positive("youngs_modulus_pa", self.youngs_modulus_pa)
        _finite_positive("reference_temperature_k", self.reference_temperature_k)
        if not math.isfinite(self.poisson_ratio) or not -1 < self.poisson_ratio < 0.5:
            raise InvalidLinearViscoelasticModel(
                "poisson_ratio must be within the stable isotropic interval (-1, 0.5)"
            )
        if not 1 <= len(self.terms) <= 5:
            raise InvalidLinearViscoelasticModel("Prony term count must be between 1 and 5")
        times = tuple(term.relaxation_time_s for term in self.terms)
        if any(right <= left for left, right in pairwise(times)):
            raise InvalidLinearViscoelasticModel(
                "Prony relaxation times must be strictly increasing"
            )
        shear_sum = sum(term.g_ratio for term in self.terms)
        bulk_sum = sum(term.k_ratio for term in self.terms)
        if shear_sum >= 1 or bulk_sum >= 1:
            raise InvalidLinearViscoelasticModel("Prony shear and bulk ratio sums must be below 1")
        if shear_sum == 0 and bulk_sum == 0:
            raise InvalidLinearViscoelasticModel(
                "at least one Prony ratio must be greater than zero"
            )
        if (
            self.bulk_relaxation_status is BulkRelaxationStatus.NOT_CHARACTERIZED
            and bulk_sum != 0
        ):
            raise InvalidLinearViscoelasticModel(
                "not_characterized bulk relaxation requires explicit zero k ratios"
            )
        if (
            self.bulk_relaxation_status is BulkRelaxationStatus.CHARACTERIZED
            and bulk_sum == 0
        ):
            raise InvalidLinearViscoelasticModel(
                "characterized bulk relaxation requires at least one positive k ratio"
            )
        if self.model_family_id != REFERENCE_LINEAR_VISCOELASTIC_FAMILY_ID:
            raise InvalidLinearViscoelasticModel("unexpected linear-viscoelastic model family")
        if self.model_schema_digest != REFERENCE_LINEAR_VISCOELASTIC_SCHEMA_DIGEST:
            raise InvalidLinearViscoelasticModel("unexpected linear-viscoelastic schema digest")
        if self.elastic_moduli_convention != "instantaneous":
            raise InvalidLinearViscoelasticModel("only instantaneous elastic moduli are supported")
        if self.non_production is not True:
            raise InvalidLinearViscoelasticModel("reference model must remain non-production")

    @property
    def instantaneous_shear_modulus_pa(self) -> float:
        return self.youngs_modulus_pa / (2 * (1 + self.poisson_ratio))

    @property
    def instantaneous_bulk_modulus_pa(self) -> float:
        return self.youngs_modulus_pa / (3 * (1 - 2 * self.poisson_ratio))


@dataclass(frozen=True, slots=True)
class LinearViscoelasticResponsePoint:
    time_s: float
    relaxation_shear_modulus_pa: float
    relaxation_bulk_modulus_pa: float


def evaluate_relaxation(
    content: ReferenceLinearViscoelasticContent, times_s: tuple[float, ...]
) -> tuple[LinearViscoelasticResponsePoint, ...]:
    if not times_s or len(times_s) > 200:
        raise InvalidLinearViscoelasticModel("response requires 1..200 time values")
    result: list[LinearViscoelasticResponsePoint] = []
    g0 = content.instantaneous_shear_modulus_pa
    k0 = content.instantaneous_bulk_modulus_pa
    shear_long = 1 - sum(term.g_ratio for term in content.terms)
    bulk_long = 1 - sum(term.k_ratio for term in content.terms)
    previous = -1.0
    for time_s in times_s:
        if not math.isfinite(time_s) or time_s < 0 or time_s <= previous:
            raise InvalidLinearViscoelasticModel(
                "response times must be finite, non-negative, and strictly increasing"
            )
        previous = time_s
        shear_factor = shear_long + sum(
            term.g_ratio * math.exp(-time_s / term.relaxation_time_s)
            for term in content.terms
        )
        bulk_factor = bulk_long + sum(
            term.k_ratio * math.exp(-time_s / term.relaxation_time_s)
            for term in content.terms
        )
        result.append(
            LinearViscoelasticResponsePoint(time_s, g0 * shear_factor, k0 * bulk_factor)
        )
    return tuple(result)


def reference_linear_viscoelastic_canonical(
    content: ReferenceLinearViscoelasticContent,
) -> dict[str, object]:
    return {
        "model_family_id": content.model_family_id,
        "model_schema_digest": content.model_schema_digest,
        "material_id": str(content.material_id),
        "material_revision_id": str(content.material_revision_id),
        "material_state_id": str(content.material_state_id),
        "material_state_revision_id": str(content.material_state_revision_id),
        "property_set_id": str(content.property_set_id),
        "property_set_revision_id": str(content.property_set_revision_id),
        "density_kg_per_m3": content.density_kg_per_m3,
        "youngs_modulus_pa": content.youngs_modulus_pa,
        "poisson_ratio": content.poisson_ratio,
        "elastic_moduli_convention": content.elastic_moduli_convention,
        "bulk_relaxation_status": content.bulk_relaxation_status.value,
        "terms": [
            {
                "ordinal": ordinal,
                "g_ratio": term.g_ratio,
                "k_ratio": term.k_ratio,
                "relaxation_time_s": term.relaxation_time_s,
            }
            for ordinal, term in enumerate(content.terms, 1)
        ],
        "applicability": {
            "temperature_min_k": content.applicable_temperature_min_k,
            "temperature_max_k": content.applicable_temperature_max_k,
            "strain_rate_min_per_s": content.applicable_strain_rate_min_per_s,
            "strain_rate_max_per_s": content.applicable_strain_rate_max_per_s,
            "note": content.applicability_note,
        },
        "reference_temperature_k": content.reference_temperature_k,
        "non_production": content.non_production,
    }

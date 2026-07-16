"""Bounded solver-neutral one-term Ogden plus shear-Prony reference model."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from itertools import pairwise
from uuid import UUID

REFERENCE_OGDEN_PRONY_FAMILY_ID = "urn:cmp:reference:ogden-prony-hyperviscoelastic:1.0.0"
REFERENCE_OGDEN_PRONY_SCHEMA_ID = (
    "urn:cmp:modeling:reference-ogden-prony-hyperviscoelastic:1.0.0"
)
REFERENCE_OGDEN_PRONY_SCHEMA_VERSION = "1.0.0"
REFERENCE_CALIBRATED_OGDEN_PRONY_SCHEMA_ID = (
    "urn:cmp:modeling:reference-ogden-prony-hyperviscoelastic:1.1.0"
)
REFERENCE_CALIBRATED_OGDEN_PRONY_SCHEMA_VERSION = "1.1.0"

_SCHEMA_DOCUMENT = {
    "family": REFERENCE_OGDEN_PRONY_FAMILY_ID,
    "version": REFERENCE_OGDEN_PRONY_SCHEMA_VERSION,
    "hyperelastic_potential": "abaqus_ogden_two_mu_over_alpha_squared",
    "ogden_term_count": 1,
    "moduli_convention": "instantaneous",
    "volumetric_response": "incompressible",
    "prony": {"kind": "normalized_shear", "term_count": [1, 5], "time_unit": "s"},
}
REFERENCE_OGDEN_PRONY_SCHEMA_DIGEST = hashlib.sha256(
    json.dumps(_SCHEMA_DOCUMENT, sort_keys=True, separators=(",", ":")).encode()
).hexdigest()


class InvalidReferenceOgdenProny(ValueError):
    pass


class ReferenceOgdenPronyNotFound(Exception):
    pass


class ReferenceOgdenPronyConflict(Exception):
    pass


def _positive(name: str, value: float) -> None:
    if not math.isfinite(value) or value <= 0:
        raise InvalidReferenceOgdenProny(f"{name} must be finite and greater than zero")


def _nonzero(name: str, value: UUID) -> None:
    if value.int == 0:
        raise InvalidReferenceOgdenProny(f"{name} must be a non-zero UUID")


@dataclass(frozen=True, slots=True)
class ReferenceOgdenTerm:
    mu_pa: float
    alpha: float

    def __post_init__(self) -> None:
        _positive("mu_pa", self.mu_pa)
        _positive("alpha", self.alpha)


@dataclass(frozen=True, slots=True)
class ReferenceShearPronyTerm:
    g_ratio: float
    relaxation_time_s: float

    def __post_init__(self) -> None:
        if not math.isfinite(self.g_ratio) or not 0 < self.g_ratio < 1:
            raise InvalidReferenceOgdenProny("g_ratio must be finite within (0, 1)")
        _positive("relaxation_time_s", self.relaxation_time_s)


@dataclass(frozen=True, slots=True)
class ReferenceOgdenPromotionEvidence:
    """Exact human decision and diagnostics owned by one promoted IR revision."""

    selection_id: UUID
    selection_revision_id: UUID
    calibration_run_id: UUID
    calibration_candidate_id: UUID
    candidate_sha256: str
    diagnostics_artifact_id: UUID
    diagnostics_sha256: str
    promoted_from_model_revision_id: UUID

    def __post_init__(self) -> None:
        for name in (
            "selection_id",
            "selection_revision_id",
            "calibration_run_id",
            "calibration_candidate_id",
            "diagnostics_artifact_id",
            "promoted_from_model_revision_id",
        ):
            _nonzero(name, getattr(self, name))
        for name in ("candidate_sha256", "diagnostics_sha256"):
            value = getattr(self, name)
            if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
                raise InvalidReferenceOgdenProny(f"{name} must be lowercase SHA-256")


@dataclass(frozen=True, slots=True)
class ReferenceOgdenPronyContent:
    material_id: UUID
    material_revision_id: UUID
    material_state_id: UUID
    material_state_revision_id: UUID
    property_set_id: UUID
    property_set_revision_id: UUID
    density_kg_per_m3: float
    catalog_youngs_modulus_pa: float
    catalog_poisson_ratio: float
    ogden_term: ReferenceOgdenTerm
    prony_terms: tuple[ReferenceShearPronyTerm, ...]
    reference_temperature_k: float = 293.15
    promotion_evidence: ReferenceOgdenPromotionEvidence | None = None
    law62_poisson_ratio: float = 0.495
    material_class: str = "elastomer"
    hyperelastic_potential: str = "abaqus_ogden_two_mu_over_alpha_squared"
    moduli_convention: str = "instantaneous"
    volumetric_response: str = "incompressible"
    model_family_id: str = REFERENCE_OGDEN_PRONY_FAMILY_ID
    model_schema_digest: str = REFERENCE_OGDEN_PRONY_SCHEMA_DIGEST
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
        _positive("density_kg_per_m3", self.density_kg_per_m3)
        _positive("catalog_youngs_modulus_pa", self.catalog_youngs_modulus_pa)
        if (
            not math.isfinite(self.catalog_poisson_ratio)
            or not -1 < self.catalog_poisson_ratio < 0.5
        ):
            raise InvalidReferenceOgdenProny(
                "catalog_poisson_ratio must be within the stable isotropic interval"
            )
        _positive("reference_temperature_k", self.reference_temperature_k)
        if not 1 <= len(self.prony_terms) <= 5:
            raise InvalidReferenceOgdenProny("Prony term count must be between 1 and 5")
        times = tuple(term.relaxation_time_s for term in self.prony_terms)
        if any(right <= left for left, right in pairwise(times)):
            raise InvalidReferenceOgdenProny("Prony relaxation times must be strictly increasing")
        if sum(term.g_ratio for term in self.prony_terms) >= 1:
            raise InvalidReferenceOgdenProny("Prony shear ratio sum must remain below one")
        if self.law62_poisson_ratio != 0.495:
            raise InvalidReferenceOgdenProny("reference LAW62 mapping fixes Poisson ratio to 0.495")
        if self.material_class != "elastomer":
            raise InvalidReferenceOgdenProny("reference Ogden-Prony requires elastomer class")
        if (
            self.hyperelastic_potential
            != "abaqus_ogden_two_mu_over_alpha_squared"
            or self.moduli_convention != "instantaneous"
            or self.volumetric_response != "incompressible"
            or self.model_family_id != REFERENCE_OGDEN_PRONY_FAMILY_ID
            or self.model_schema_digest != REFERENCE_OGDEN_PRONY_SCHEMA_DIGEST
            or not self.non_production
        ):
            raise InvalidReferenceOgdenProny("reference Ogden-Prony contract was changed")

    @property
    def instantaneous_shear_modulus_pa(self) -> float:
        return self.ogden_term.mu_pa

    @property
    def long_term_shear_modulus_pa(self) -> float:
        return self.ogden_term.mu_pa * (1 - sum(term.g_ratio for term in self.prony_terms))

    def canonical(self) -> dict[str, object]:
        result: dict[str, object] = {
            "model_family_id": self.model_family_id,
            "model_schema_digest": self.model_schema_digest,
            "material_class": self.material_class,
            "material_id": str(self.material_id),
            "material_revision_id": str(self.material_revision_id),
            "material_state_id": str(self.material_state_id),
            "material_state_revision_id": str(self.material_state_revision_id),
            "property_set_id": str(self.property_set_id),
            "property_set_revision_id": str(self.property_set_revision_id),
            "density_kg_per_m3": self.density_kg_per_m3,
            "catalog_source_properties": {
                "youngs_modulus_pa": self.catalog_youngs_modulus_pa,
                "poisson_ratio": self.catalog_poisson_ratio,
            },
            "hyperelastic_potential": self.hyperelastic_potential,
            "moduli_convention": self.moduli_convention,
            "volumetric_response": self.volumetric_response,
            "law62_poisson_ratio": self.law62_poisson_ratio,
            "ogden_terms": [
                {
                    "ordinal": 1,
                    "mu_pa": self.ogden_term.mu_pa,
                    "alpha": self.ogden_term.alpha,
                }
            ],
            "prony_terms": [
                {
                    "ordinal": ordinal,
                    "g_ratio": term.g_ratio,
                    "k_ratio": 0.0,
                    "relaxation_time_s": term.relaxation_time_s,
                }
                for ordinal, term in enumerate(self.prony_terms, 1)
            ],
            "reference_temperature_k": self.reference_temperature_k,
            "non_production": self.non_production,
        }
        if self.promotion_evidence is not None:
            evidence = self.promotion_evidence
            result["promotion_evidence"] = {
                "selection_id": str(evidence.selection_id),
                "selection_revision_id": str(evidence.selection_revision_id),
                "calibration_run_id": str(evidence.calibration_run_id),
                "calibration_candidate_id": str(evidence.calibration_candidate_id),
                "candidate_sha256": evidence.candidate_sha256,
                "diagnostics_artifact_id": str(evidence.diagnostics_artifact_id),
                "diagnostics_sha256": evidence.diagnostics_sha256,
                "promoted_from_model_revision_id": str(
                    evidence.promoted_from_model_revision_id
                ),
            }
        return result


def reference_ogden_prony_canonical(
    content: ReferenceOgdenPronyContent,
) -> dict[str, object]:
    return content.canonical()


def incompressible_uniaxial_nominal_stress_pa(
    content: ReferenceOgdenPronyContent, stretch: float
) -> float:
    """Evaluate the rate-independent N=1 Ogden nominal response."""

    if not math.isfinite(stretch) or stretch <= 0:
        raise InvalidReferenceOgdenProny("stretch must be finite and greater than zero")
    mu = content.ogden_term.mu_pa
    alpha = content.ogden_term.alpha
    return float(
        (2 * mu / alpha)
        * (stretch ** (alpha - 1) - stretch ** (-alpha / 2 - 1))
    )

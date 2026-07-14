"""Typed non-production reference IR for isotropic small-strain linear elasticity.

This module owns no solver keyword and has no fitting behavior.  It preserves concrete Catalog
revisions from which the three explicit SI properties were derived, so an IR remains reproducible
after a Material State or Property Set receives a later revision.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from uuid import UUID

from cmp.shared.domain.revisions import content_sha256

REFERENCE_MODEL_FAMILY_ID = "urn:cmp:reference:isotropic-linear-elasticity:1.0.0"
REFERENCE_MODEL_SCHEMA_VERSION = "1.0.0"
REFERENCE_MODEL_SCHEMA_DIGEST = content_sha256(
    {
        "family": REFERENCE_MODEL_FAMILY_ID,
        "schema_version": REFERENCE_MODEL_SCHEMA_VERSION,
        "parameters": {
            "density_kg_per_m3": "positive finite scalar",
            "youngs_modulus_pa": "positive finite scalar",
            "poisson_ratio": "-1 < value < 0.5",
        },
        "semantics": {
            "kinematics": "small_strain",
            "stress_measure": "cauchy",
            "strain_measure": "infinitesimal",
            "material_symmetry": "isotropic",
            "sign_convention": "tension_positive",
        },
        "non_production": True,
    }
)


class ModelingError(Exception):
    """Base error for model IR commands."""


class InvalidReferenceModel(ModelingError, ValueError):
    """The reference linear-elastic IR would be physically or semantically invalid."""


class ReferenceModelNotFound(ModelingError):
    """The requested model or concrete catalog input is absent or hidden."""


class ReferenceModelConflict(ModelingError):
    """A stable parent, scope, or immutable model invariant conflicts."""


@dataclass(frozen=True, slots=True)
class ReferenceCalibrationEvidence:
    """Typed evidence that a human-selected Candidate supplied this IR's Young's modulus."""

    calibration_selection_id: UUID
    calibration_selection_revision_id: UUID
    calibration_run_id: UUID
    calibration_candidate_id: UUID
    calibration_candidate_sha256: str
    diagnostics_artifact_id: UUID
    diagnostics_sha256: str

    def __post_init__(self) -> None:
        for name in (
            "calibration_selection_id",
            "calibration_selection_revision_id",
            "calibration_run_id",
            "calibration_candidate_id",
            "diagnostics_artifact_id",
        ):
            _nonzero(name, getattr(self, name))
        for name in ("calibration_candidate_sha256", "diagnostics_sha256"):
            value = getattr(self, name)
            if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
                raise InvalidReferenceModel(f"{name} must be a lowercase SHA-256 hex digest")


def _nonzero(name: str, value: UUID) -> None:
    if value.int == 0:
        raise InvalidReferenceModel(f"{name} must be non-zero")


def _finite_positive(name: str, value: float) -> None:
    if not math.isfinite(value) or value <= 0:
        raise InvalidReferenceModel(f"{name} must be finite and greater than zero")


def _optional_finite(name: str, value: float | None, *, minimum: float) -> None:
    if value is not None and (not math.isfinite(value) or value < minimum):
        raise InvalidReferenceModel(f"{name} must be finite and at least {minimum}")


@dataclass(frozen=True, slots=True)
class ReferenceLinearElasticContent:
    """A fully typed, SI-normalized snapshot of a Catalog Property Set revision."""

    material_id: UUID
    material_revision_id: UUID
    material_state_id: UUID
    material_state_revision_id: UUID
    property_set_id: UUID
    property_set_revision_id: UUID
    density_kg_per_m3: float
    youngs_modulus_pa: float
    poisson_ratio: float
    source_yield_stress_pa: float | None = None
    applicable_temperature_min_k: float | None = None
    applicable_temperature_max_k: float | None = None
    applicable_strain_rate_min_per_s: float | None = None
    applicable_strain_rate_max_per_s: float | None = None
    applicability_note: str | None = None
    reference_temperature_k: float = 293.15
    calibration_evidence: ReferenceCalibrationEvidence | None = None

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
        _optional_finite("source_yield_stress_pa", self.source_yield_stress_pa, minimum=0.0)
        if self.source_yield_stress_pa == 0:
            raise InvalidReferenceModel("source_yield_stress_pa must be greater than zero")
        if not math.isfinite(self.poisson_ratio) or not -1 < self.poisson_ratio < 0.5:
            raise InvalidReferenceModel(
                "poisson_ratio must be within the stable isotropic interval (-1, 0.5)"
            )
        _finite_positive("reference_temperature_k", self.reference_temperature_k)
        _optional_finite(
            "applicable_temperature_min_k", self.applicable_temperature_min_k, minimum=0.0
        )
        _optional_finite(
            "applicable_temperature_max_k", self.applicable_temperature_max_k, minimum=0.0
        )
        _optional_finite(
            "applicable_strain_rate_min_per_s",
            self.applicable_strain_rate_min_per_s,
            minimum=0.0,
        )
        _optional_finite(
            "applicable_strain_rate_max_per_s",
            self.applicable_strain_rate_max_per_s,
            minimum=0.0,
        )
        if (
            self.applicable_temperature_min_k is not None
            and self.applicable_temperature_max_k is not None
            and self.applicable_temperature_min_k > self.applicable_temperature_max_k
        ):
            raise InvalidReferenceModel("applicable temperature bounds are inverted")
        if (
            self.applicable_strain_rate_min_per_s is not None
            and self.applicable_strain_rate_max_per_s is not None
            and self.applicable_strain_rate_min_per_s
            > self.applicable_strain_rate_max_per_s
        ):
            raise InvalidReferenceModel("applicable strain-rate bounds are inverted")
        if self.applicability_note is not None and (
            not self.applicability_note.strip()
            or self.applicability_note != self.applicability_note.strip()
            or len(self.applicability_note) > 2000
            or "\x00" in self.applicability_note
        ):
            raise InvalidReferenceModel(
                "applicability_note must be a trimmed 1..2000 character text"
            )


def reference_linear_elastic_canonical(
    content: ReferenceLinearElasticContent,
) -> dict[str, object]:
    """Canonical typed content hashed by the shared immutable revision kernel."""

    return {
        "model_family_id": REFERENCE_MODEL_FAMILY_ID,
        "model_schema_version": REFERENCE_MODEL_SCHEMA_VERSION,
        "model_schema_digest": REFERENCE_MODEL_SCHEMA_DIGEST,
        "material_id": str(content.material_id),
        "material_revision_id": str(content.material_revision_id),
        "material_state_id": str(content.material_state_id),
        "material_state_revision_id": str(content.material_state_revision_id),
        "property_set_id": str(content.property_set_id),
        "property_set_revision_id": str(content.property_set_revision_id),
        "density_kg_per_m3": content.density_kg_per_m3,
        "youngs_modulus_pa": content.youngs_modulus_pa,
        "poisson_ratio": content.poisson_ratio,
        "source_yield_stress_pa": content.source_yield_stress_pa,
        "applicability": {
            "temperature_min_k": content.applicable_temperature_min_k,
            "temperature_max_k": content.applicable_temperature_max_k,
            "strain_rate_min_per_s": content.applicable_strain_rate_min_per_s,
            "strain_rate_max_per_s": content.applicable_strain_rate_max_per_s,
            "note": content.applicability_note,
        },
        "reference_temperature_k": content.reference_temperature_k,
        "calibration_evidence": (
            {
                "status": "reference_candidate_selected",
                "selection_id": str(content.calibration_evidence.calibration_selection_id),
                "selection_revision_id": str(
                    content.calibration_evidence.calibration_selection_revision_id
                ),
                "calibration_run_id": str(content.calibration_evidence.calibration_run_id),
                "calibration_candidate_id": str(
                    content.calibration_evidence.calibration_candidate_id
                ),
                "calibration_candidate_sha256": (
                    content.calibration_evidence.calibration_candidate_sha256
                ),
                "diagnostics_artifact_id": str(
                    content.calibration_evidence.diagnostics_artifact_id
                ),
                "diagnostics_sha256": content.calibration_evidence.diagnostics_sha256,
            }
            if content.calibration_evidence is not None
            else {"status": "not_calibrated_manual_property_projection"}
        ),
        "non_production": True,
    }


def reference_linear_elastic_ir(
    content: ReferenceLinearElasticContent,
    *,
    material_model_id: UUID,
    material_model_revision_id: UUID,
) -> dict[str, object]:
    """Render the fixed reference IR envelope without persisting a generic JSON payload."""

    _nonzero("material_model_id", material_model_id)
    _nonzero("material_model_revision_id", material_model_revision_id)
    return {
        "ir_version": "1.0.0",
        "ir_id": str(material_model_id),
        "ir_revision_id": str(material_model_revision_id),
        "material_ref": {
            "material_revision_id": str(content.material_revision_id),
            "material_state_revision_id": str(content.material_state_revision_id),
        },
        "model_family": {
            "id": REFERENCE_MODEL_FAMILY_ID,
            "schema_version": REFERENCE_MODEL_SCHEMA_VERSION,
            "schema_digest": f"sha256:{REFERENCE_MODEL_SCHEMA_DIGEST}",
            "provider_plugin": {
                "plugin_id": "cmp.reference.isotropic-linear-elasticity",
                "plugin_version": REFERENCE_MODEL_SCHEMA_VERSION,
                "package_digest": f"sha256:{REFERENCE_MODEL_SCHEMA_DIGEST}",
            },
        },
        "semantics": {
            "kinematics": "small_strain",
            "stress_measure": "cauchy",
            "strain_measure": "infinitesimal",
            "dimensionality": ["3d"],
            "material_symmetry": "isotropic",
            "material_frame": {"required": False, "definition": None},
            "sign_convention": "tension_positive",
            "temperature_scale": "K",
            "reference_temperature": {
                "value": content.reference_temperature_k,
                "unit": "K",
            },
            "density": {
                "value": content.density_kg_per_m3,
                "unit": "kg/m3",
                "required_for": ["explicit-dynamics"],
            },
        },
        "payload": {
            "model": "isotropic_linear_elasticity",
            "density": {"value": content.density_kg_per_m3, "unit": "kg/m3"},
            "youngs_modulus": {"value": content.youngs_modulus_pa, "unit": "Pa"},
            "poisson_ratio": {"value": content.poisson_ratio, "unit": "1"},
            "property_set_revision_id": str(content.property_set_revision_id),
            "source_property_disposition": {
                "yield_stress": (
                    {
                        "value": content.source_yield_stress_pa,
                        "unit": "Pa",
                        "status": "not_applicable_to_linear_elasticity",
                    }
                    if content.source_yield_stress_pa is not None
                    else {"status": "not_present"}
                )
            },
        },
        "applicability": {
            "analysis_domains": ["structural"],
            "loading_modes": ["small_deformation"],
            "element_formulations": ["continuum", "shell", "beam", "truss"],
            "time_dependence": "none",
            "temperature_dependence": "none",
            "required_state_variables": [],
            "required_initial_conditions": [],
        },
        "validity_domain": {
            "temperature": {
                "min": content.applicable_temperature_min_k,
                "max": content.applicable_temperature_max_k,
                "unit": "K",
                "status": "catalog_property_applicability",
            },
            "strain_rate": {
                "min": content.applicable_strain_rate_min_per_s,
                "max": content.applicable_strain_rate_max_per_s,
                "unit": "1/s",
                "status": "catalog_property_applicability",
            },
            "strain": {
                "min": None,
                "max": None,
                "unit": "1",
                "measure": "not_characterized",
            },
            "pressure_or_triaxiality": {"status": "not_characterized"},
            "loading_history": {"status": "not_characterized"},
            "extrapolation_policy": "disallowed_without_review",
        },
        "calibration_evidence": (
            {
                "status": "reference_candidate_selected",
                "selection_id": str(content.calibration_evidence.calibration_selection_id),
                "selection_revision_id": str(
                    content.calibration_evidence.calibration_selection_revision_id
                ),
                "calibration_run_id": str(content.calibration_evidence.calibration_run_id),
                "candidate_id": str(content.calibration_evidence.calibration_candidate_id),
                "candidate_sha256": (
                    f"sha256:{content.calibration_evidence.calibration_candidate_sha256}"
                ),
                "diagnostics_artifact_id": str(
                    content.calibration_evidence.diagnostics_artifact_id
                ),
                "diagnostics_sha256": (
                    f"sha256:{content.calibration_evidence.diagnostics_sha256}"
                ),
                "selection_decision": "accepted_for_reference_ir_promotion",
            }
            if content.calibration_evidence is not None
            else {"status": "not_calibrated_manual_property_projection"}
        ),
        "validation_evidence": [
            {
                "kind": "semantic",
                "status": "pass",
                "detail": "typed SI values and isotropic linear-elasticity invariants validated",
            }
        ],
        "provenance": {
            "source_property_set_revision_id": str(content.property_set_revision_id),
            "source_material_revision_id": str(content.material_revision_id),
            "source_material_state_revision_id": str(content.material_state_revision_id),
        },
        "extensions": {},
        "non_production": True,
    }

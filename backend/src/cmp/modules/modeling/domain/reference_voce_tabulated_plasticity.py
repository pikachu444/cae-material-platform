"""Typed solver-neutral projection of one accepted Voce Candidate.

The projection is deliberately separate from the tensile-reduction 1.0 family.  It samples the
public Voce saturation equation on an explicit fixed grid and retains the accepted Candidate,
Run, Plan, reviewed input Scope, and human Selection revisions as immutable provenance.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from uuid import UUID

from cmp.modules.modeling.domain.reference_isotropic_tabulated_plasticity import (
    REFERENCE_HARDENING_CURVE_SCHEMA,
    REFERENCE_POST_NECKING_EXTENSION_POLICY,
    HardeningCurvePoint,
    HardeningPointOrigin,
    validate_hardening_curve,
)
from cmp.shared.domain.revisions import content_sha256

REFERENCE_VOCE_TABULATED_PLASTICITY_FAMILY_ID = (
    "urn:cmp:reference:isotropic-tabulated-plasticity:1.1.0"
)
REFERENCE_VOCE_TABULATED_PLASTICITY_SCHEMA_ID = (
    "urn:cmp:modeling:reference-voce-tabulated-plasticity:1.1.0"
)
REFERENCE_VOCE_TABULATED_PLASTICITY_SCHEMA_VERSION = "1.1.0"
REFERENCE_VOCE_SAMPLING_PROFILE_ID = "urn:cmp:modeling:reference-voce-fixed-grid-projection:1.0.0"
REFERENCE_VOCE_SAMPLING_PROFILE_VERSION = "1.0.0"
REFERENCE_VOCE_SAMPLING_PROFILE_DIGEST = content_sha256(
    {
        "equation": "sigma_y=sigma_0+Q*(1-exp(-b*epsilon_p))",
        "grid": "linearly_spaced_true_plastic_strain_including_zero_and_characterized_max",
        "point_count_bounds": [21, 501],
        "extension": REFERENCE_POST_NECKING_EXTENSION_POLICY,
        "smoothing": "none",
        "parameter_refitting": "none",
        "non_production": True,
    }
)
REFERENCE_VOCE_TABULATED_PLASTICITY_SCHEMA_DIGEST = content_sha256(
    {
        "family": REFERENCE_VOCE_TABULATED_PLASTICITY_FAMILY_ID,
        "schema_version": REFERENCE_VOCE_TABULATED_PLASTICITY_SCHEMA_VERSION,
        "parameters": [
            "density_kg_per_m3",
            "youngs_modulus_pa",
            "poisson_ratio",
            "sigma_0_pa",
            "q_pa",
            "b",
        ],
        "hardening_curve_schema": REFERENCE_HARDENING_CURVE_SCHEMA,
        "source_revisions": [
            "material_revision_id",
            "material_state_revision_id",
            "property_set_revision_id",
            "calibration_input_scope_revision_id",
            "voce_calibration_plan_revision_id",
            "voce_calibration_run_id",
            "voce_calibration_candidate_id",
            "voce_candidate_selection_revision_id",
        ],
        "sampling_profile_digest": REFERENCE_VOCE_SAMPLING_PROFILE_DIGEST,
        "non_production": True,
    }
)


class InvalidVoceProjection(ValueError):
    """A selected Candidate cannot be represented by the fixed projection contract."""


def _uuid(name: str, value: UUID) -> None:
    if value.int == 0:
        raise InvalidVoceProjection(f"{name} must not be the zero UUID")


def _positive(name: str, value: float) -> None:
    if not math.isfinite(value) or value <= 0:
        raise InvalidVoceProjection(f"{name} must be finite and positive")


def voce_fixed_grid_hardening_curve(
    *,
    sigma_0_pa: float,
    q_pa: float,
    b: float,
    characterized_max_true_plastic_strain: float,
    extension_max_true_plastic_strain: float,
    sampling_point_count: int,
    acknowledge_constant_extension: bool,
) -> tuple[HardeningCurvePoint, ...]:
    """Sample Voce without refitting, repair, smoothing, or implicit extrapolation."""

    for name, value in (("sigma_0_pa", sigma_0_pa), ("q_pa", q_pa), ("b", b)):
        _positive(name, value)
    _positive(
        "characterized_max_true_plastic_strain",
        characterized_max_true_plastic_strain,
    )
    if (
        not math.isfinite(extension_max_true_plastic_strain)
        or extension_max_true_plastic_strain <= characterized_max_true_plastic_strain
    ):
        raise InvalidVoceProjection(
            "extension maximum must exceed the characterized true-plastic-strain maximum"
        )
    if not 21 <= sampling_point_count <= 501:
        raise InvalidVoceProjection("sampling_point_count must be between 21 and 501")
    if not acknowledge_constant_extension:
        raise InvalidVoceProjection("constant extension requires explicit acknowledgement")
    step = characterized_max_true_plastic_strain / (sampling_point_count - 1)
    points = tuple(
        HardeningCurvePoint(
            true_plastic_strain=index * step,
            true_yield_stress_pa=sigma_0_pa + q_pa * (1.0 - math.exp(-b * index * step)),
            origin=HardeningPointOrigin.CALIBRATED_VOCE_SAMPLE,
        )
        for index in range(sampling_point_count)
    )
    projected = (
        *points,
        HardeningCurvePoint(
            true_plastic_strain=extension_max_true_plastic_strain,
            true_yield_stress_pa=points[-1].true_yield_stress_pa,
            origin=HardeningPointOrigin.APPROVED_CONSTANT_EXTENSION,
        ),
    )
    validate_hardening_curve(projected)
    return projected


@dataclass(frozen=True, slots=True)
class ReferenceVoceTabulatedPlasticityContent:
    """One immutable 1.1 IR revision projected from one human-accepted Candidate."""

    material_id: UUID
    material_revision_id: UUID
    material_state_id: UUID
    material_state_revision_id: UUID
    property_set_id: UUID
    property_set_revision_id: UUID
    calibration_input_scope_id: UUID
    calibration_input_scope_revision_id: UUID
    voce_calibration_plan_id: UUID
    voce_calibration_plan_revision_id: UUID
    voce_calibration_run_id: UUID
    voce_calibration_candidate_id: UUID
    voce_calibration_candidate_sha256: str
    voce_candidate_selection_id: UUID
    voce_candidate_selection_revision_id: UUID
    hardening_curve_artifact_id: UUID
    hardening_curve_sha256: str
    hardening_curve_point_count: int
    sampling_point_count: int
    density_kg_per_m3: float
    youngs_modulus_pa: float
    poisson_ratio: float
    initial_yield_stress_pa: float
    q_pa: float
    b: float
    characterized_max_true_plastic_strain: float
    extension_max_true_plastic_strain: float
    post_necking_approximation_acknowledged: bool
    applicable_temperature_min_k: float | None = None
    applicable_temperature_max_k: float | None = None
    applicable_strain_rate_min_per_s: float | None = None
    applicable_strain_rate_max_per_s: float | None = None
    applicability_note: str | None = None
    reference_temperature_k: float = 293.15
    model_family_id: str = REFERENCE_VOCE_TABULATED_PLASTICITY_FAMILY_ID
    model_schema_version: str = REFERENCE_VOCE_TABULATED_PLASTICITY_SCHEMA_VERSION
    model_schema_digest: str = REFERENCE_VOCE_TABULATED_PLASTICITY_SCHEMA_DIGEST
    hardening_curve_schema_ref: str = REFERENCE_HARDENING_CURVE_SCHEMA
    transformation_profile_id: str = REFERENCE_VOCE_SAMPLING_PROFILE_ID
    transformation_profile_version: str = REFERENCE_VOCE_SAMPLING_PROFILE_VERSION
    transformation_profile_digest: str = REFERENCE_VOCE_SAMPLING_PROFILE_DIGEST
    post_necking_extension_policy: str = REFERENCE_POST_NECKING_EXTENSION_POLICY
    non_production: bool = True

    def __post_init__(self) -> None:
        for name in (
            "material_id",
            "material_revision_id",
            "material_state_id",
            "material_state_revision_id",
            "property_set_id",
            "property_set_revision_id",
            "calibration_input_scope_id",
            "calibration_input_scope_revision_id",
            "voce_calibration_plan_id",
            "voce_calibration_plan_revision_id",
            "voce_calibration_run_id",
            "voce_calibration_candidate_id",
            "voce_candidate_selection_id",
            "voce_candidate_selection_revision_id",
            "hardening_curve_artifact_id",
        ):
            _uuid(name, getattr(self, name))
        for name, value in (
            ("density_kg_per_m3", self.density_kg_per_m3),
            ("youngs_modulus_pa", self.youngs_modulus_pa),
            ("initial_yield_stress_pa", self.initial_yield_stress_pa),
            ("q_pa", self.q_pa),
            ("b", self.b),
            ("characterized_max_true_plastic_strain", self.characterized_max_true_plastic_strain),
            ("extension_max_true_plastic_strain", self.extension_max_true_plastic_strain),
        ):
            _positive(name, value)
        if not -1.0 < self.poisson_ratio < 0.5:
            raise InvalidVoceProjection("poisson_ratio must remain within (-1, 0.5)")
        if not 21 <= self.sampling_point_count <= 501:
            raise InvalidVoceProjection("sampling_point_count must be between 21 and 501")
        if self.hardening_curve_point_count != self.sampling_point_count + 1:
            raise InvalidVoceProjection("hardening point count must include one extension point")
        for name, digest in (
            ("candidate", self.voce_calibration_candidate_sha256),
            ("hardening curve", self.hardening_curve_sha256),
        ):
            if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
                raise InvalidVoceProjection(f"{name} SHA-256 is invalid")
        if self.extension_max_true_plastic_strain <= self.characterized_max_true_plastic_strain:
            raise InvalidVoceProjection("extension maximum must exceed characterized maximum")
        if not self.post_necking_approximation_acknowledged:
            raise InvalidVoceProjection("constant extension must be acknowledged")
        if (
            self.model_family_id != REFERENCE_VOCE_TABULATED_PLASTICITY_FAMILY_ID
            or self.model_schema_version != REFERENCE_VOCE_TABULATED_PLASTICITY_SCHEMA_VERSION
            or self.model_schema_digest != REFERENCE_VOCE_TABULATED_PLASTICITY_SCHEMA_DIGEST
            or self.transformation_profile_id != REFERENCE_VOCE_SAMPLING_PROFILE_ID
            or self.transformation_profile_version != REFERENCE_VOCE_SAMPLING_PROFILE_VERSION
            or self.transformation_profile_digest != REFERENCE_VOCE_SAMPLING_PROFILE_DIGEST
            or self.hardening_curve_schema_ref != REFERENCE_HARDENING_CURVE_SCHEMA
            or self.post_necking_extension_policy != REFERENCE_POST_NECKING_EXTENSION_POLICY
            or not self.non_production
        ):
            raise InvalidVoceProjection("Voce projected IR must retain its fixed typed contract")

    @property
    def source_dataset_id(self) -> None:
        return None

    @property
    def source_dataset_revision_id(self) -> None:
        return None

    @property
    def source_point_count(self) -> None:
        return None

    @property
    def pre_yield_excluded_point_count(self) -> None:
        return None

    @property
    def post_necking_excluded_point_count(self) -> None:
        return None

    @property
    def necking_source_point_index(self) -> None:
        return None

    @property
    def necking_engineering_strain(self) -> None:
        return None


def reference_voce_tabulated_plasticity_canonical(
    value: ReferenceVoceTabulatedPlasticityContent,
) -> dict[str, object]:
    return {
        "model_family_id": value.model_family_id,
        "model_schema_version": value.model_schema_version,
        "model_schema_digest": value.model_schema_digest,
        "material": {"id": str(value.material_id), "revision_id": str(value.material_revision_id)},
        "material_state": {
            "id": str(value.material_state_id),
            "revision_id": str(value.material_state_revision_id),
        },
        "property_set": {
            "id": str(value.property_set_id),
            "revision_id": str(value.property_set_revision_id),
        },
        "calibration": {
            "input_scope_id": str(value.calibration_input_scope_id),
            "input_scope_revision_id": str(value.calibration_input_scope_revision_id),
            "plan_id": str(value.voce_calibration_plan_id),
            "plan_revision_id": str(value.voce_calibration_plan_revision_id),
            "run_id": str(value.voce_calibration_run_id),
            "candidate_id": str(value.voce_calibration_candidate_id),
            "candidate_sha256": value.voce_calibration_candidate_sha256,
            "selection_id": str(value.voce_candidate_selection_id),
            "selection_revision_id": str(value.voce_candidate_selection_revision_id),
        },
        "parameters": {
            "density_kg_per_m3": value.density_kg_per_m3,
            "youngs_modulus_pa": value.youngs_modulus_pa,
            "poisson_ratio": value.poisson_ratio,
            "sigma_0_pa": value.initial_yield_stress_pa,
            "q_pa": value.q_pa,
            "b": value.b,
        },
        "hardening_curve": {
            "artifact_id": str(value.hardening_curve_artifact_id),
            "sha256": value.hardening_curve_sha256,
            "schema_ref": value.hardening_curve_schema_ref,
            "point_count": value.hardening_curve_point_count,
            "sampling_point_count": value.sampling_point_count,
            "characterized_max_true_plastic_strain": value.characterized_max_true_plastic_strain,
            "extension_max_true_plastic_strain": value.extension_max_true_plastic_strain,
            "extension_policy": value.post_necking_extension_policy,
            "constant_extension_acknowledged": value.post_necking_approximation_acknowledged,
        },
        "transformation": {
            "profile_id": value.transformation_profile_id,
            "profile_version": value.transformation_profile_version,
            "profile_digest": value.transformation_profile_digest,
        },
        "applicability": {
            "temperature_min_k": value.applicable_temperature_min_k,
            "temperature_max_k": value.applicable_temperature_max_k,
            "strain_rate_min_per_s": value.applicable_strain_rate_min_per_s,
            "strain_rate_max_per_s": value.applicable_strain_rate_max_per_s,
            "note": value.applicability_note,
            "reference_temperature_k": value.reference_temperature_k,
        },
        "non_production": value.non_production,
    }


def reference_voce_tabulated_plasticity_ir(
    *,
    material_model_id: UUID,
    material_model_revision_id: UUID,
    content: ReferenceVoceTabulatedPlasticityContent,
) -> dict[str, object]:
    """Expose the immutable calibrated IR without solver keyword concepts."""

    _uuid("material_model_id", material_model_id)
    _uuid("material_model_revision_id", material_model_revision_id)
    canonical = reference_voce_tabulated_plasticity_canonical(content)
    return {
        "schema": {
            "id": REFERENCE_VOCE_TABULATED_PLASTICITY_SCHEMA_ID,
            "version": content.model_schema_version,
            "digest": f"sha256:{content.model_schema_digest}",
        },
        "identity": {
            "material_model_id": str(material_model_id),
            "material_model_revision_id": str(material_model_revision_id),
        },
        "constitutive_model": {
            "family_id": content.model_family_id,
            "behavior": "rate_independent_isotropic_tabulated_plasticity",
            "parameters": canonical["parameters"],
            "hardening_curve": canonical["hardening_curve"],
        },
        "calibration_evidence": canonical["calibration"],
        "transformation_evidence": canonical["transformation"],
        "applicability": canonical["applicability"],
        "semantics": {
            "units": "SI",
            "stress_measure": "true_cauchy",
            "plastic_strain_measure": "logarithmic_true_plastic",
            "solver_neutral": True,
        },
        "non_production": True,
    }

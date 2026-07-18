"""Solver-neutral tabulated plasticity promoted from one exact Processing Output."""

from __future__ import annotations

import math
from dataclasses import dataclass
from uuid import UUID

from cmp.modules.modeling.domain.reference_isotropic_tabulated_plasticity import (
    REFERENCE_HARDENING_CURVE_SCHEMA,
)
from cmp.shared.domain.revisions import content_sha256

REFERENCE_PROCESSED_TABULATED_PLASTICITY_FAMILY_ID = (
    "urn:cmp:reference:isotropic-tabulated-plasticity:1.2.0"
)
REFERENCE_PROCESSED_TABULATED_PLASTICITY_SCHEMA_ID = (
    "urn:cmp:modeling:reference-processed-tabulated-plasticity:1.2.0"
)
REFERENCE_PROCESSED_TABULATED_PLASTICITY_SCHEMA_VERSION = "1.2.0"
REFERENCE_PROCESSED_SELECTION_PROFILE_ID = (
    "urn:cmp:modeling:processing-selected-hardening-projection:1.0.0"
)
REFERENCE_PROCESSED_SELECTION_PROFILE_VERSION = "1.0.0"
REFERENCE_PROCESSED_EXTRAPOLATION_POLICY = "selected_fitted_bounded_extrapolation"
SUPPORTED_HARDENING_FAMILIES = frozenset({"voce", "swift", "hockett_sherby", "ghosh"})

REFERENCE_PROCESSED_SELECTION_PROFILE_DIGEST = content_sha256(
    {
        "source": "exact_cmp_processing_output_revision",
        "required_final_method": "metal.hardening_fit_extrapolate@1.0.0",
        "selected_series": "stress.hardening.selected",
        "independent_series": "strain.true_plastic",
        "candidate_families": sorted(SUPPORTED_HARDENING_FAMILIES),
        "selection": "primary_weight*primary+(1-primary_weight)*secondary",
        "extrapolation": REFERENCE_PROCESSED_EXTRAPOLATION_POLICY,
        "parameter_refitting": "none",
        "non_production": True,
    }
)
REFERENCE_PROCESSED_TABULATED_PLASTICITY_SCHEMA_DIGEST = content_sha256(
    {
        "family": REFERENCE_PROCESSED_TABULATED_PLASTICITY_FAMILY_ID,
        "schema_version": REFERENCE_PROCESSED_TABULATED_PLASTICITY_SCHEMA_VERSION,
        "parameters": ["density_kg_per_m3", "youngs_modulus_pa", "poisson_ratio"],
        "hardening_curve_schema": REFERENCE_HARDENING_CURVE_SCHEMA,
        "source_revisions": [
            "material_revision_id",
            "material_state_revision_id",
            "property_set_revision_id",
            "processing_output_revision_id",
            "test_data_revision_id",
            "mapping_profile_revision_id",
        ],
        "selection": ["candidate_families", "primary_family", "secondary_family", "weight"],
        "domain": ["fit_minimum", "fit_maximum", "extrapolation_maximum"],
        "transformation_profile_digest": REFERENCE_PROCESSED_SELECTION_PROFILE_DIGEST,
        "non_production": True,
    }
)


class InvalidProcessedProjection(ValueError):
    """An exact Processing Output cannot be promoted without changing its declared meaning."""


def _uuid(name: str, value: UUID) -> None:
    if value.int == 0:
        raise InvalidProcessedProjection(f"{name} must be non-zero")


def _digest(name: str, value: str) -> None:
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise InvalidProcessedProjection(f"{name} must be a lowercase SHA-256 digest")


@dataclass(frozen=True, slots=True)
class ReferenceProcessedTabulatedPlasticityContent:
    material_id: UUID
    material_revision_id: UUID
    material_state_id: UUID
    material_state_revision_id: UUID
    property_set_id: UUID
    property_set_revision_id: UUID
    processing_output_id: UUID
    processing_output_revision_id: UUID
    processing_output_sha256: str
    source_test_data_id: UUID
    source_test_data_revision_id: UUID
    mapping_profile_id: UUID
    mapping_profile_revision_id: UUID
    candidate_families: tuple[str, ...]
    primary_family: str
    secondary_family: str
    primary_weight: float
    fit_minimum_true_plastic_strain: float
    characterized_max_true_plastic_strain: float
    extension_max_true_plastic_strain: float
    hardening_curve_artifact_id: UUID
    hardening_curve_sha256: str
    hardening_curve_point_count: int
    density_kg_per_m3: float
    youngs_modulus_pa: float
    poisson_ratio: float
    initial_yield_stress_pa: float
    post_necking_approximation_acknowledged: bool
    applicable_temperature_min_k: float | None = None
    applicable_temperature_max_k: float | None = None
    applicable_strain_rate_min_per_s: float | None = None
    applicable_strain_rate_max_per_s: float | None = None
    applicability_note: str | None = None
    reference_temperature_k: float = 293.15
    model_family_id: str = REFERENCE_PROCESSED_TABULATED_PLASTICITY_FAMILY_ID
    model_schema_version: str = REFERENCE_PROCESSED_TABULATED_PLASTICITY_SCHEMA_VERSION
    model_schema_digest: str = REFERENCE_PROCESSED_TABULATED_PLASTICITY_SCHEMA_DIGEST
    hardening_curve_schema_ref: str = REFERENCE_HARDENING_CURVE_SCHEMA
    transformation_profile_id: str = REFERENCE_PROCESSED_SELECTION_PROFILE_ID
    transformation_profile_version: str = REFERENCE_PROCESSED_SELECTION_PROFILE_VERSION
    transformation_profile_digest: str = REFERENCE_PROCESSED_SELECTION_PROFILE_DIGEST
    post_necking_extension_policy: str = REFERENCE_PROCESSED_EXTRAPOLATION_POLICY
    non_production: bool = True

    def __post_init__(self) -> None:
        for name in (
            "material_id",
            "material_revision_id",
            "material_state_id",
            "material_state_revision_id",
            "property_set_id",
            "property_set_revision_id",
            "processing_output_id",
            "processing_output_revision_id",
            "source_test_data_id",
            "source_test_data_revision_id",
            "mapping_profile_id",
            "mapping_profile_revision_id",
            "hardening_curve_artifact_id",
        ):
            _uuid(name, getattr(self, name))
        _digest("processing_output_sha256", self.processing_output_sha256)
        _digest("hardening_curve_sha256", self.hardening_curve_sha256)
        if not 2 <= len(self.candidate_families) <= 4 or (
            len(set(self.candidate_families)) != len(self.candidate_families)
            or not set(self.candidate_families) <= SUPPORTED_HARDENING_FAMILIES
        ):
            raise InvalidProcessedProjection("candidate_families must be 2..4 unique supported IDs")
        if (
            self.primary_family not in self.candidate_families
            or self.secondary_family not in self.candidate_families
        ):
            raise InvalidProcessedProjection("selected families must be declared candidates")
        if not math.isfinite(self.primary_weight) or not 0 <= self.primary_weight <= 1:
            raise InvalidProcessedProjection("primary_weight must be in [0,1]")
        if not (
            0
            <= self.fit_minimum_true_plastic_strain
            < self.characterized_max_true_plastic_strain
            < self.extension_max_true_plastic_strain
            <= 5
        ):
            raise InvalidProcessedProjection("fit and extrapolation domains are invalid")
        if not 21 <= self.hardening_curve_point_count <= 501:
            raise InvalidProcessedProjection("selected hardening curve must contain 21..501 points")
        for name, value in (
            ("density_kg_per_m3", self.density_kg_per_m3),
            ("youngs_modulus_pa", self.youngs_modulus_pa),
            ("initial_yield_stress_pa", self.initial_yield_stress_pa),
        ):
            if not math.isfinite(value) or value <= 0:
                raise InvalidProcessedProjection(f"{name} must be finite and positive")
        if not math.isfinite(self.poisson_ratio) or not -1 < self.poisson_ratio < 0.5:
            raise InvalidProcessedProjection("poisson_ratio must remain within (-1,0.5)")
        if not self.post_necking_approximation_acknowledged:
            raise InvalidProcessedProjection(
                "bounded fitted extrapolation requires acknowledgement"
            )
        if (
            self.model_family_id != REFERENCE_PROCESSED_TABULATED_PLASTICITY_FAMILY_ID
            or self.model_schema_version != REFERENCE_PROCESSED_TABULATED_PLASTICITY_SCHEMA_VERSION
            or self.model_schema_digest != REFERENCE_PROCESSED_TABULATED_PLASTICITY_SCHEMA_DIGEST
            or self.transformation_profile_id != REFERENCE_PROCESSED_SELECTION_PROFILE_ID
            or self.transformation_profile_digest != REFERENCE_PROCESSED_SELECTION_PROFILE_DIGEST
            or self.post_necking_extension_policy != REFERENCE_PROCESSED_EXTRAPOLATION_POLICY
            or not self.non_production
        ):
            raise InvalidProcessedProjection("processed projection must retain its typed contract")

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


def reference_processed_tabulated_plasticity_canonical(
    value: ReferenceProcessedTabulatedPlasticityContent,
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
        "processing_output": {
            "id": str(value.processing_output_id),
            "revision_id": str(value.processing_output_revision_id),
            "sha256": value.processing_output_sha256,
            "source_test_data_id": str(value.source_test_data_id),
            "source_test_data_revision_id": str(value.source_test_data_revision_id),
            "mapping_profile_id": str(value.mapping_profile_id),
            "mapping_profile_revision_id": str(value.mapping_profile_revision_id),
        },
        "selection": {
            "candidate_families": list(value.candidate_families),
            "primary_family": value.primary_family,
            "secondary_family": value.secondary_family,
            "primary_weight": value.primary_weight,
            "fit_minimum_true_plastic_strain": value.fit_minimum_true_plastic_strain,
            "fit_maximum_true_plastic_strain": value.characterized_max_true_plastic_strain,
            "extrapolation_maximum_true_plastic_strain": value.extension_max_true_plastic_strain,
        },
        "parameters": {
            "density_kg_per_m3": value.density_kg_per_m3,
            "youngs_modulus_pa": value.youngs_modulus_pa,
            "poisson_ratio": value.poisson_ratio,
            "initial_yield_stress_pa": value.initial_yield_stress_pa,
        },
        "hardening_curve": {
            "artifact_id": str(value.hardening_curve_artifact_id),
            "sha256": value.hardening_curve_sha256,
            "schema_ref": value.hardening_curve_schema_ref,
            "point_count": value.hardening_curve_point_count,
        },
        "transformation": {
            "profile_id": value.transformation_profile_id,
            "profile_version": value.transformation_profile_version,
            "profile_digest": value.transformation_profile_digest,
            "extrapolation_policy": value.post_necking_extension_policy,
            "acknowledged": value.post_necking_approximation_acknowledged,
        },
        "applicability": {
            "reference_temperature_k": value.reference_temperature_k,
            "temperature_min_k": value.applicable_temperature_min_k,
            "temperature_max_k": value.applicable_temperature_max_k,
            "strain_rate_min_per_s": value.applicable_strain_rate_min_per_s,
            "strain_rate_max_per_s": value.applicable_strain_rate_max_per_s,
            "note": value.applicability_note,
        },
        "non_production": True,
    }


def reference_processed_tabulated_plasticity_ir(
    *,
    material_model_id: UUID,
    material_model_revision_id: UUID,
    content: ReferenceProcessedTabulatedPlasticityContent,
) -> dict[str, object]:
    canonical = reference_processed_tabulated_plasticity_canonical(content)
    return {
        "schema": {
            "id": REFERENCE_PROCESSED_TABULATED_PLASTICITY_SCHEMA_ID,
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
        "source_revisions": canonical["processing_output"],
        "selection": canonical["selection"],
        "transformation_evidence": canonical["transformation"],
        "applicability": canonical["applicability"],
        "non_production": True,
    }

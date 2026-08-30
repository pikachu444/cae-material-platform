"""Solver-neutral reference linear viscoelasticity with explicit Prony terms."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from enum import StrEnum
from itertools import pairwise
from uuid import UUID

from cmp.modules.modeling.domain.fit_decision_evidence import FitDecisionEvidence

REFERENCE_LINEAR_VISCOELASTIC_FAMILY_ID = (
    "urn:cmp:reference:isotropic-linear-viscoelastic-prony:1.0.0"
)
REFERENCE_LINEAR_VISCOELASTIC_SCHEMA_ID = (
    "urn:cmp:modeling:reference-isotropic-linear-viscoelastic-prony:1.0.0"
)
REFERENCE_LINEAR_VISCOELASTIC_SCHEMA_VERSION = "1.0.0"
REFERENCE_CALIBRATED_LINEAR_VISCOELASTIC_SCHEMA_ID = (
    "urn:cmp:modeling:reference-isotropic-linear-viscoelastic-prony:1.1.0"
)
REFERENCE_CALIBRATED_LINEAR_VISCOELASTIC_SCHEMA_VERSION = "1.1.0"
REFERENCE_PROCESSING_LINEAR_VISCOELASTIC_SCHEMA_ID = (
    "urn:cmp:modeling:reference-isotropic-linear-viscoelastic-prony:1.2.0"
)
REFERENCE_PROCESSING_LINEAR_VISCOELASTIC_SCHEMA_VERSION = "1.2.0"
REFERENCE_RECIPE_PROCESSING_LINEAR_VISCOELASTIC_SCHEMA_ID = (
    "urn:cmp:modeling:reference-isotropic-linear-viscoelastic-prony:1.3.0"
)
REFERENCE_RECIPE_PROCESSING_LINEAR_VISCOELASTIC_SCHEMA_VERSION = "1.3.0"
REFERENCE_CALIBRATED_LINEAR_VISCOELASTIC_SCHEMA_ID_1_4 = (
    "urn:cmp:modeling:reference-isotropic-linear-viscoelastic-prony:1.4.0"
)
REFERENCE_CALIBRATED_LINEAR_VISCOELASTIC_SCHEMA_VERSION_1_4 = "1.4.0"

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
_PROCESSING_SCHEMA_DOCUMENT = {
    **_SCHEMA_DOCUMENT,
    "version": REFERENCE_PROCESSING_LINEAR_VISCOELASTIC_SCHEMA_VERSION,
    "term_count": [1, 10],
    "promotion_evidence": "exact_polymer_processing_output",
}
REFERENCE_PROCESSING_LINEAR_VISCOELASTIC_SCHEMA_DIGEST = hashlib.sha256(
    json.dumps(_PROCESSING_SCHEMA_DOCUMENT, sort_keys=True, separators=(",", ":")).encode("utf-8")
).hexdigest()
_RECIPE_PROCESSING_SCHEMA_DOCUMENT = {
    **_PROCESSING_SCHEMA_DOCUMENT,
    "version": REFERENCE_RECIPE_PROCESSING_LINEAR_VISCOELASTIC_SCHEMA_VERSION,
    "promotion_evidence": "exact_recipe_batch_processing_output",
}
REFERENCE_RECIPE_PROCESSING_LINEAR_VISCOELASTIC_SCHEMA_DIGEST = hashlib.sha256(
    json.dumps(_RECIPE_PROCESSING_SCHEMA_DOCUMENT, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
).hexdigest()
_CALIBRATION_SCHEMA_DOCUMENT = {
    **_PROCESSING_SCHEMA_DOCUMENT,
    "version": REFERENCE_CALIBRATED_LINEAR_VISCOELASTIC_SCHEMA_VERSION_1_4,
    "promotion_evidence": "linear_viscoelastic_calibration_plan_run_candidate_selection",
}
REFERENCE_CALIBRATED_LINEAR_VISCOELASTIC_SCHEMA_DIGEST_1_4 = hashlib.sha256(
    json.dumps(_CALIBRATION_SCHEMA_DOCUMENT, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
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


@dataclass(frozen=True, slots=True)
class ReferencePronyPromotionEvidence:
    selection_id: UUID
    selection_revision_id: UUID
    calibration_run_id: UUID
    calibration_candidate_id: UUID
    candidate_sha256: str
    diagnostics_artifact_id: UUID
    diagnostics_sha256: str

    def __post_init__(self) -> None:
        for name in (
            "selection_id",
            "selection_revision_id",
            "calibration_run_id",
            "calibration_candidate_id",
            "diagnostics_artifact_id",
        ):
            _nonzero(name, getattr(self, name))
        for name in ("candidate_sha256", "diagnostics_sha256"):
            value = getattr(self, name)
            if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
                raise InvalidLinearViscoelasticModel(f"{name} must be lowercase SHA-256")


@dataclass(frozen=True, slots=True)
class ReferenceLinearViscoelasticCalibrationEvidence:
    """Exact Plan/Run/Candidate/Selection evidence for IR schema 1.4."""

    plan_id: UUID
    plan_revision_id: UUID
    plan_sha256: str
    run_id: UUID
    run_sha256: str
    candidate_id: UUID
    candidate_sha256: str
    selection_id: UUID
    selection_revision_id: UUID
    selection_sha256: str
    recommendation_id: UUID
    recommendation_sha256: str
    canonical_test_data_id: UUID
    canonical_test_data_revision_id: UUID
    canonical_test_data_sha256: str
    canonical_artifact_id: UUID
    canonical_artifact_sha256: str
    normalized_artifact_id: UUID
    normalized_artifact_sha256: str
    import_profile_id: UUID
    import_profile_revision_id: UUID
    import_profile_sha256: str

    def __post_init__(self) -> None:
        for name in (
            "plan_id",
            "plan_revision_id",
            "run_id",
            "candidate_id",
            "selection_id",
            "selection_revision_id",
            "recommendation_id",
            "canonical_test_data_id",
            "canonical_test_data_revision_id",
            "canonical_artifact_id",
            "normalized_artifact_id",
            "import_profile_id",
            "import_profile_revision_id",
        ):
            _nonzero(name, getattr(self, name))
        for name in (
            "plan_sha256",
            "run_sha256",
            "candidate_sha256",
            "selection_sha256",
            "recommendation_sha256",
            "canonical_test_data_sha256",
            "canonical_artifact_sha256",
            "normalized_artifact_sha256",
            "import_profile_sha256",
        ):
            value = getattr(self, name)
            if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
                raise InvalidLinearViscoelasticModel(f"{name} must be lowercase SHA-256")


@dataclass(frozen=True, slots=True)
class ReferenceRecipeBatchEvidence:
    recipe_id: UUID
    recipe_revision_id: UUID
    recipe_sha256: str
    batch_id: UUID
    batch_member_id: UUID
    batch_attempt_id: UUID
    batch_attempt_no: int

    def __post_init__(self) -> None:
        for name in (
            "recipe_id",
            "recipe_revision_id",
            "batch_id",
            "batch_member_id",
            "batch_attempt_id",
        ):
            _nonzero(name, getattr(self, name))
        if len(self.recipe_sha256) != 64 or any(
            char not in "0123456789abcdef" for char in self.recipe_sha256
        ):
            raise InvalidLinearViscoelasticModel("recipe_sha256 must be lowercase SHA-256")
        if self.batch_attempt_no < 1:
            raise InvalidLinearViscoelasticModel("batch_attempt_no must be positive")


@dataclass(frozen=True, slots=True)
class ReferencePronyProcessingEvidence:
    processing_output_id: UUID
    processing_output_revision_id: UUID
    processing_output_sha256: str
    source_test_data_id: UUID
    source_test_data_revision_id: UUID
    mapping_profile_id: UUID
    mapping_profile_revision_id: UUID
    selection_mode: str
    selected_term_count: int
    normalized_rmse: float
    bic: float
    fitted_instantaneous_shear_modulus_pa: float
    catalog_instantaneous_shear_modulus_pa: float
    instantaneous_modulus_relative_mismatch: float
    acknowledged_maximum_relative_mismatch: float
    fit_decision: FitDecisionEvidence | None = None
    recipe_batch: ReferenceRecipeBatchEvidence | None = None

    def __post_init__(self) -> None:
        for name in (
            "processing_output_id",
            "processing_output_revision_id",
            "source_test_data_id",
            "source_test_data_revision_id",
            "mapping_profile_id",
            "mapping_profile_revision_id",
        ):
            _nonzero(name, getattr(self, name))
        value = self.processing_output_sha256
        if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
            raise InvalidLinearViscoelasticModel(
                "processing_output_sha256 must be lowercase SHA-256"
            )
        if self.selection_mode not in {"automatic_bic", "manual"}:
            raise InvalidLinearViscoelasticModel(
                "processing selection_mode must be automatic_bic or manual"
            )
        if not 1 <= self.selected_term_count <= 10:
            raise InvalidLinearViscoelasticModel(
                "processing selected_term_count must be within 1..10"
            )
        for name in (
            "normalized_rmse",
            "instantaneous_modulus_relative_mismatch",
            "acknowledged_maximum_relative_mismatch",
        ):
            current = getattr(self, name)
            if not math.isfinite(current) or current < 0:
                raise InvalidLinearViscoelasticModel(f"{name} must be finite and non-negative")
        if not math.isfinite(self.bic):
            raise InvalidLinearViscoelasticModel("bic must be finite")
        if self.fit_decision is not None and (
            self.fit_decision.mode != "single"
            or self.fit_decision.primary_law != "generalized_maxwell"
            or self.fit_decision.actual_term_count != self.selected_term_count
            or self.fit_decision.requested_term_policy != self.selection_mode
            or self.fit_decision.metric_definition != "normalized_rmse"
            or self.fit_decision.metric_value != self.normalized_rmse
            or self.fit_decision.extrapolation_policy != "observed_only"
        ):
            raise InvalidLinearViscoelasticModel(
                "processing fit evidence must match the selected generalized-Maxwell result"
            )
        _finite_positive(
            "fitted_instantaneous_shear_modulus_pa",
            self.fitted_instantaneous_shear_modulus_pa,
        )
        _finite_positive(
            "catalog_instantaneous_shear_modulus_pa",
            self.catalog_instantaneous_shear_modulus_pa,
        )
        if self.instantaneous_modulus_relative_mismatch > (
            self.acknowledged_maximum_relative_mismatch
        ):
            raise InvalidLinearViscoelasticModel(
                "instantaneous modulus mismatch exceeds the acknowledged maximum"
            )


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
    prony_promotion_evidence: ReferencePronyPromotionEvidence | None = None
    processing_promotion_evidence: ReferencePronyProcessingEvidence | None = None
    model_family_id: str = REFERENCE_LINEAR_VISCOELASTIC_FAMILY_ID
    model_schema_digest: str = REFERENCE_LINEAR_VISCOELASTIC_SCHEMA_DIGEST
    elastic_moduli_convention: str = "instantaneous"
    non_production: bool = True
    calibration_evidence: ReferenceLinearViscoelasticCalibrationEvidence | None = None

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
        if (
            self.prony_promotion_evidence is not None
            and self.processing_promotion_evidence is not None
        ):
            raise InvalidLinearViscoelasticModel("linear Prony revision cannot mix promotion kinds")
        if self.calibration_evidence is not None and (
            self.prony_promotion_evidence is not None
            or self.processing_promotion_evidence is not None
        ):
            raise InvalidLinearViscoelasticModel("linear Prony revision cannot mix promotion kinds")
        maximum_terms = (
            10
            if self.processing_promotion_evidence is not None
            or self.calibration_evidence is not None
            else 5
        )
        if not 1 <= len(self.terms) <= maximum_terms:
            raise InvalidLinearViscoelasticModel(
                f"Prony term count must be between 1 and {maximum_terms}"
            )
        if (
            self.processing_promotion_evidence is not None
            and self.processing_promotion_evidence.selected_term_count != len(self.terms)
        ):
            raise InvalidLinearViscoelasticModel(
                "Processing evidence selected term count differs from IR terms"
            )
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
        if self.bulk_relaxation_status is BulkRelaxationStatus.NOT_CHARACTERIZED and bulk_sum != 0:
            raise InvalidLinearViscoelasticModel(
                "not_characterized bulk relaxation requires explicit zero k ratios"
            )
        if self.bulk_relaxation_status is BulkRelaxationStatus.CHARACTERIZED and bulk_sum == 0:
            raise InvalidLinearViscoelasticModel(
                "characterized bulk relaxation requires at least one positive k ratio"
            )
        if self.model_family_id != REFERENCE_LINEAR_VISCOELASTIC_FAMILY_ID:
            raise InvalidLinearViscoelasticModel("unexpected linear-viscoelastic model family")
        expected_digest = REFERENCE_LINEAR_VISCOELASTIC_SCHEMA_DIGEST
        if self.calibration_evidence is not None:
            expected_digest = REFERENCE_CALIBRATED_LINEAR_VISCOELASTIC_SCHEMA_DIGEST_1_4
        if self.processing_promotion_evidence is not None:
            expected_digest = (
                REFERENCE_RECIPE_PROCESSING_LINEAR_VISCOELASTIC_SCHEMA_DIGEST
                if self.processing_promotion_evidence.recipe_batch is not None
                else REFERENCE_PROCESSING_LINEAR_VISCOELASTIC_SCHEMA_DIGEST
            )
        if self.model_schema_digest != expected_digest:
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
            term.g_ratio * math.exp(-time_s / term.relaxation_time_s) for term in content.terms
        )
        bulk_factor = bulk_long + sum(
            term.k_ratio * math.exp(-time_s / term.relaxation_time_s) for term in content.terms
        )
        result.append(LinearViscoelasticResponsePoint(time_s, g0 * shear_factor, k0 * bulk_factor))
    return tuple(result)


def reference_linear_viscoelastic_canonical(
    content: ReferenceLinearViscoelasticContent,
) -> dict[str, object]:
    result: dict[str, object] = {
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
    if content.prony_promotion_evidence is not None:
        evidence = content.prony_promotion_evidence
        result["prony_promotion_evidence"] = {
            "selection_id": str(evidence.selection_id),
            "selection_revision_id": str(evidence.selection_revision_id),
            "calibration_run_id": str(evidence.calibration_run_id),
            "calibration_candidate_id": str(evidence.calibration_candidate_id),
            "candidate_sha256": evidence.candidate_sha256,
            "diagnostics_artifact_id": str(evidence.diagnostics_artifact_id),
            "diagnostics_sha256": evidence.diagnostics_sha256,
        }
    if content.processing_promotion_evidence is not None:
        processing_evidence = content.processing_promotion_evidence
        processing_result: dict[str, object] = {
            "processing_output": {
                "id": str(processing_evidence.processing_output_id),
                "revision_id": str(processing_evidence.processing_output_revision_id),
                "sha256": processing_evidence.processing_output_sha256,
            },
            "source_test_data": {
                "id": str(processing_evidence.source_test_data_id),
                "revision_id": str(processing_evidence.source_test_data_revision_id),
            },
            "mapping_profile": {
                "id": str(processing_evidence.mapping_profile_id),
                "revision_id": str(processing_evidence.mapping_profile_revision_id),
            },
            "selection_mode": processing_evidence.selection_mode,
            "selected_term_count": processing_evidence.selected_term_count,
            "normalized_rmse": processing_evidence.normalized_rmse,
            "bic": processing_evidence.bic,
            "fitted_instantaneous_shear_modulus_pa": (
                processing_evidence.fitted_instantaneous_shear_modulus_pa
            ),
            "catalog_instantaneous_shear_modulus_pa": (
                processing_evidence.catalog_instantaneous_shear_modulus_pa
            ),
            "instantaneous_modulus_relative_mismatch": (
                processing_evidence.instantaneous_modulus_relative_mismatch
            ),
            "acknowledged_maximum_relative_mismatch": (
                processing_evidence.acknowledged_maximum_relative_mismatch
            ),
        }
        if processing_evidence.recipe_batch is not None:
            origin = processing_evidence.recipe_batch
            processing_result["recipe_batch"] = {
                "processing_recipe": {
                    "id": str(origin.recipe_id),
                    "revision_id": str(origin.recipe_revision_id),
                    "sha256": origin.recipe_sha256,
                },
                "processing_batch_id": str(origin.batch_id),
                "batch_member_id": str(origin.batch_member_id),
                "batch_attempt_id": str(origin.batch_attempt_id),
                "batch_attempt_no": origin.batch_attempt_no,
            }
        if processing_evidence.fit_decision is not None:
            processing_result["fit_decision"] = processing_evidence.fit_decision.canonical()
            processing_result["fit_decision_digest"] = processing_evidence.fit_decision.digest
        result["processing_promotion_evidence"] = processing_result
    if content.calibration_evidence is not None:
        calibration_evidence = content.calibration_evidence
        result["calibration_promotion_evidence"] = {
            "plan": {
                "id": str(calibration_evidence.plan_id),
                "revision_id": str(calibration_evidence.plan_revision_id),
                "sha256": calibration_evidence.plan_sha256,
            },
            "run": {
                "id": str(calibration_evidence.run_id),
                "sha256": calibration_evidence.run_sha256,
            },
            "candidate": {
                "id": str(calibration_evidence.candidate_id),
                "sha256": calibration_evidence.candidate_sha256,
            },
            "selection": {
                "id": str(calibration_evidence.selection_id),
                "revision_id": str(calibration_evidence.selection_revision_id),
                "sha256": calibration_evidence.selection_sha256,
            },
            "recommendation": {
                "id": str(calibration_evidence.recommendation_id),
                "sha256": calibration_evidence.recommendation_sha256,
            },
            "canonical_test_data": {
                "id": str(calibration_evidence.canonical_test_data_id),
                "revision_id": str(calibration_evidence.canonical_test_data_revision_id),
                "sha256": calibration_evidence.canonical_test_data_sha256,
            },
            "canonical_artifact": {
                "id": str(calibration_evidence.canonical_artifact_id),
                "sha256": calibration_evidence.canonical_artifact_sha256,
            },
            "normalized_artifact": {
                "id": str(calibration_evidence.normalized_artifact_id),
                "sha256": calibration_evidence.normalized_artifact_sha256,
            },
            "import_profile": {
                "id": str(calibration_evidence.import_profile_id),
                "revision_id": str(calibration_evidence.import_profile_revision_id),
                "sha256": calibration_evidence.import_profile_sha256,
            },
        }
    return result

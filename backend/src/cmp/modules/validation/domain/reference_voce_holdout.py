"""Solver-independent V3 holdout validation for the reference Voce model.

The profile evaluates the accepted public Voce equation directly at one independent tensile
Dataset's pre-necking true-plastic-strain observations.  It never invokes a solver, consumes a
solver card, or upgrades this reference metric into production material approval.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from cmp.modules.modeling.domain.reference_voce_calibration import (
    ReferenceVoceMaterialModelEvaluator,
    VoceEngineeringCurveInput,
    adapt_reference_voce_uniaxial_curve,
)
from cmp.shared.domain.revisions import canonical_json_bytes, content_sha256

REFERENCE_VOCE_HOLDOUT_PLAN_SCHEMA_ID = "urn:cmp:validation:reference-voce-holdout-plan:1.0.0"
REFERENCE_VOCE_HOLDOUT_PLAN_SCHEMA_VERSION = "1.0.0"
REFERENCE_VOCE_HOLDOUT_RESULT_SCHEMA_ID = "urn:cmp:validation:reference-voce-holdout-result:1.0.0"
REFERENCE_VOCE_HOLDOUT_COMPARISON_SCHEMA_ID = (
    "urn:cmp:validation:reference-voce-holdout-comparison:1.0.0"
)
REFERENCE_VOCE_HOLDOUT_METRIC_PROFILE_ID = (
    "urn:cmp:validation:reference-voce-true-stress-relative-rmse:1.0.0"
)
REFERENCE_VOCE_HOLDOUT_THRESHOLD_PROFILE_ID = (
    "urn:cmp:validation:reference-voce-relative-rmse-threshold:1.0.0"
)
REFERENCE_VOCE_HOLDOUT_THRESHOLD = 0.05


class VoceHoldoutError(Exception):
    pass


class InvalidVoceHoldout(VoceHoldoutError, ValueError):
    pass


class VoceHoldoutConflict(VoceHoldoutError):
    pass


class VoceHoldoutNotFound(VoceHoldoutError):
    pass


class VoceHoldoutVerdict(StrEnum):
    PASSED = "passed"
    FAILED = "failed"


def _uuid(name: str, value: UUID) -> None:
    if value.int == 0:
        raise InvalidVoceHoldout(f"{name} must not be the zero UUID")


def _text(name: str, value: str, maximum: int) -> None:
    if not value or value != value.strip() or len(value) > maximum or "\x00" in value:
        raise InvalidVoceHoldout(f"{name} must be trimmed and contain 1..{maximum} characters")


def _digest(name: str, value: str) -> None:
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise InvalidVoceHoldout(f"{name} must be a lowercase SHA-256 digest")


@dataclass(frozen=True, slots=True)
class ReferenceVoceHoldoutPlanContent:
    plan_label: str
    material_model_id: UUID
    material_model_revision_id: UUID
    holdout_dataset_id: UUID
    holdout_dataset_revision_id: UUID
    metric_profile_id: str = REFERENCE_VOCE_HOLDOUT_METRIC_PROFILE_ID
    threshold_profile_id: str = REFERENCE_VOCE_HOLDOUT_THRESHOLD_PROFILE_ID
    relative_rmse_threshold: float = REFERENCE_VOCE_HOLDOUT_THRESHOLD
    overlap_policy: str = "reject_any_calibration_scope_dataset_or_test_run_overlap"
    evaluation_mode: str = "closed_form_curve"
    non_production: bool = True

    def __post_init__(self) -> None:
        _text("plan_label", self.plan_label, 160)
        for name in (
            "material_model_id",
            "material_model_revision_id",
            "holdout_dataset_id",
            "holdout_dataset_revision_id",
        ):
            _uuid(name, getattr(self, name))
        if (
            self.metric_profile_id != REFERENCE_VOCE_HOLDOUT_METRIC_PROFILE_ID
            or self.threshold_profile_id != REFERENCE_VOCE_HOLDOUT_THRESHOLD_PROFILE_ID
            or not math.isclose(
                self.relative_rmse_threshold,
                REFERENCE_VOCE_HOLDOUT_THRESHOLD,
                rel_tol=0.0,
                abs_tol=1e-15,
            )
            or self.overlap_policy != "reject_any_calibration_scope_dataset_or_test_run_overlap"
            or self.evaluation_mode != "closed_form_curve"
            or not self.non_production
        ):
            raise InvalidVoceHoldout("reference holdout Plan must retain its fixed profile")


def reference_voce_holdout_plan_canonical(
    value: ReferenceVoceHoldoutPlanContent,
) -> dict[str, object]:
    return {
        "plan_label": value.plan_label,
        "material_model_id": str(value.material_model_id),
        "material_model_revision_id": str(value.material_model_revision_id),
        "holdout_dataset_id": str(value.holdout_dataset_id),
        "holdout_dataset_revision_id": str(value.holdout_dataset_revision_id),
        "metric_profile_id": value.metric_profile_id,
        "threshold_profile_id": value.threshold_profile_id,
        "relative_rmse_threshold": value.relative_rmse_threshold,
        "overlap_policy": value.overlap_policy,
        "evaluation_mode": value.evaluation_mode,
        "non_production": value.non_production,
    }


@dataclass(frozen=True, slots=True)
class ReferenceVoceHoldoutComparisonPoint:
    source_point_ordinal: int
    true_plastic_strain: float
    observed_true_yield_stress_pa: float
    predicted_true_yield_stress_pa: float
    residual_true_yield_stress_pa: float

    def __post_init__(self) -> None:
        if self.source_point_ordinal < 0:
            raise InvalidVoceHoldout("source point ordinal must be non-negative")
        for name in (
            "true_plastic_strain",
            "observed_true_yield_stress_pa",
            "predicted_true_yield_stress_pa",
            "residual_true_yield_stress_pa",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not math.isfinite(value):
                raise InvalidVoceHoldout(f"{name} must be finite")
        if self.true_plastic_strain <= 0.0:
            raise InvalidVoceHoldout("holdout true plastic strain must be positive")

    def canonical(self) -> dict[str, object]:
        return {
            "source_point_ordinal": self.source_point_ordinal,
            "true_plastic_strain": self.true_plastic_strain,
            "observed_true_yield_stress_pa": self.observed_true_yield_stress_pa,
            "predicted_true_yield_stress_pa": self.predicted_true_yield_stress_pa,
            "residual_true_yield_stress_pa": self.residual_true_yield_stress_pa,
        }


@dataclass(frozen=True, slots=True)
class ReferenceVoceHoldoutMetrics:
    points: tuple[ReferenceVoceHoldoutComparisonPoint, ...]
    root_mean_squared_error_pa: float
    relative_root_mean_squared_error: float
    normalization_stress_scale_pa: float
    characterized_max_true_plastic_strain: float
    verdict: VoceHoldoutVerdict

    def __post_init__(self) -> None:
        if len(self.points) < 3:
            raise InvalidVoceHoldout("holdout metric requires at least three observations")
        if tuple(point.source_point_ordinal for point in self.points) != tuple(
            sorted(point.source_point_ordinal for point in self.points)
        ):
            raise InvalidVoceHoldout("holdout source point ordinals must be ordered")
        for name in (
            "root_mean_squared_error_pa",
            "relative_root_mean_squared_error",
            "normalization_stress_scale_pa",
            "characterized_max_true_plastic_strain",
        ):
            value = getattr(self, name)
            if not math.isfinite(value) or value <= 0.0:
                raise InvalidVoceHoldout(f"{name} must be finite and positive")
        expected = (
            VoceHoldoutVerdict.PASSED
            if self.relative_root_mean_squared_error <= REFERENCE_VOCE_HOLDOUT_THRESHOLD
            else VoceHoldoutVerdict.FAILED
        )
        if self.verdict is not expected:
            raise InvalidVoceHoldout("holdout verdict does not match the fixed threshold")


def evaluate_reference_voce_holdout(
    curve: VoceEngineeringCurveInput,
    *,
    youngs_modulus_pa: float,
    sigma_0_pa: float,
    q_pa: float,
    b: float,
) -> ReferenceVoceHoldoutMetrics:
    """Evaluate one independent curve with no optimization, interpolation, or solver call."""

    import numpy as np

    adapted = adapt_reference_voce_uniaxial_curve(curve, youngs_modulus_pa=youngs_modulus_pa)
    strains = np.asarray(
        [point.true_plastic_strain for point in adapted.observations], dtype=np.float64
    )
    observed = np.asarray(
        [point.observed_true_yield_stress_pa for point in adapted.observations],
        dtype=np.float64,
    )
    predicted = ReferenceVoceMaterialModelEvaluator().evaluate(
        np.asarray([sigma_0_pa, q_pa, b], dtype=np.float64), strains
    )
    residual = predicted - observed
    rmse = float(np.sqrt(np.mean(np.square(residual))))
    scale = float(np.max(np.abs(observed)))
    relative = rmse / scale
    points = tuple(
        ReferenceVoceHoldoutComparisonPoint(
            source_point_ordinal=source.point_ordinal,
            true_plastic_strain=float(strain),
            observed_true_yield_stress_pa=float(observation),
            predicted_true_yield_stress_pa=float(prediction),
            residual_true_yield_stress_pa=float(error),
        )
        for source, strain, observation, prediction, error in zip(
            adapted.observations, strains, observed, predicted, residual, strict=True
        )
    )
    return ReferenceVoceHoldoutMetrics(
        points=points,
        root_mean_squared_error_pa=rmse,
        relative_root_mean_squared_error=relative,
        normalization_stress_scale_pa=scale,
        characterized_max_true_plastic_strain=points[-1].true_plastic_strain,
        verdict=(
            VoceHoldoutVerdict.PASSED
            if relative <= REFERENCE_VOCE_HOLDOUT_THRESHOLD
            else VoceHoldoutVerdict.FAILED
        ),
    )


@dataclass(frozen=True, slots=True)
class ReferenceVoceHoldoutResult:
    id: UUID
    run_id: UUID
    plan_id: UUID
    plan_revision_id: UUID
    material_model_id: UUID
    material_model_revision_id: UUID
    calibration_input_scope_id: UUID
    calibration_input_scope_revision_id: UUID
    voce_calibration_run_id: UUID
    voce_calibration_candidate_id: UUID
    voce_candidate_selection_id: UUID
    voce_candidate_selection_revision_id: UUID
    holdout_dataset_id: UUID
    holdout_dataset_revision_id: UUID
    holdout_test_run_id: UUID
    holdout_test_run_revision_id: UUID
    source_data_artifact_id: UUID
    source_data_sha256: str
    comparison_artifact_id: UUID
    comparison_sha256: str
    metrics: ReferenceVoceHoldoutMetrics
    created_at: datetime
    created_by: UUID

    def __post_init__(self) -> None:
        for name in (
            "id",
            "run_id",
            "plan_id",
            "plan_revision_id",
            "material_model_id",
            "material_model_revision_id",
            "calibration_input_scope_id",
            "calibration_input_scope_revision_id",
            "voce_calibration_run_id",
            "voce_calibration_candidate_id",
            "voce_candidate_selection_id",
            "voce_candidate_selection_revision_id",
            "holdout_dataset_id",
            "holdout_dataset_revision_id",
            "holdout_test_run_id",
            "holdout_test_run_revision_id",
            "source_data_artifact_id",
            "comparison_artifact_id",
            "created_by",
        ):
            _uuid(name, getattr(self, name))
        _digest("source_data_sha256", self.source_data_sha256)
        _digest("comparison_sha256", self.comparison_sha256)
        if self.created_at.tzinfo is None or self.created_at.utcoffset() is None:
            raise InvalidVoceHoldout("created_at must be timezone-aware")

    def canonical(self) -> dict[str, object]:
        return {
            "schema_id": REFERENCE_VOCE_HOLDOUT_RESULT_SCHEMA_ID,
            "schema_version": "1.0.0",
            "non_production": True,
            "solver_execution": "not_used",
            "run_id": str(self.run_id),
            "plan": {"id": str(self.plan_id), "revision_id": str(self.plan_revision_id)},
            "material_model": {
                "id": str(self.material_model_id),
                "revision_id": str(self.material_model_revision_id),
            },
            "calibration_input_scope": {
                "id": str(self.calibration_input_scope_id),
                "revision_id": str(self.calibration_input_scope_revision_id),
            },
            "candidate": {
                "calibration_run_id": str(self.voce_calibration_run_id),
                "candidate_id": str(self.voce_calibration_candidate_id),
                "selection_id": str(self.voce_candidate_selection_id),
                "selection_revision_id": str(self.voce_candidate_selection_revision_id),
            },
            "holdout": {
                "dataset_id": str(self.holdout_dataset_id),
                "dataset_revision_id": str(self.holdout_dataset_revision_id),
                "test_run_id": str(self.holdout_test_run_id),
                "test_run_revision_id": str(self.holdout_test_run_revision_id),
                "source_data_artifact_id": str(self.source_data_artifact_id),
                "source_data_sha256": self.source_data_sha256,
                "independence": "disjoint_dataset_and_test_run",
            },
            "comparison_artifact": {
                "id": str(self.comparison_artifact_id),
                "sha256": self.comparison_sha256,
                "schema_ref": REFERENCE_VOCE_HOLDOUT_COMPARISON_SCHEMA_ID,
            },
            "metric_profile_id": REFERENCE_VOCE_HOLDOUT_METRIC_PROFILE_ID,
            "threshold_profile_id": REFERENCE_VOCE_HOLDOUT_THRESHOLD_PROFILE_ID,
            "relative_rmse_threshold": REFERENCE_VOCE_HOLDOUT_THRESHOLD,
            "point_count": len(self.metrics.points),
            "root_mean_squared_error_pa": self.metrics.root_mean_squared_error_pa,
            "relative_root_mean_squared_error": (self.metrics.relative_root_mean_squared_error),
            "normalization_stress_scale_pa": (self.metrics.normalization_stress_scale_pa),
            "characterized_max_true_plastic_strain": (
                self.metrics.characterized_max_true_plastic_strain
            ),
            "verdict": self.metrics.verdict.value,
        }


def reference_voce_holdout_comparison_bytes(
    metrics: ReferenceVoceHoldoutMetrics,
) -> bytes:
    return canonical_json_bytes(
        {
            "schema_id": REFERENCE_VOCE_HOLDOUT_COMPARISON_SCHEMA_ID,
            "schema_version": "1.0.0",
            "non_production": True,
            "channels": {
                "true_plastic_strain": {"quantity": "true_plastic_strain", "unit": "1"},
                "observed_true_yield_stress_pa": {
                    "quantity": "true_yield_stress",
                    "unit": "Pa",
                },
                "predicted_true_yield_stress_pa": {
                    "quantity": "true_yield_stress",
                    "unit": "Pa",
                },
                "residual_true_yield_stress_pa": {
                    "quantity": "stress_residual",
                    "unit": "Pa",
                    "sign": "predicted_minus_observed",
                },
            },
            "points": [point.canonical() for point in metrics.points],
        }
    )


REFERENCE_VOCE_HOLDOUT_PLAN_SCHEMA_DIGEST = content_sha256(
    {
        "schema_id": REFERENCE_VOCE_HOLDOUT_PLAN_SCHEMA_ID,
        "schema_version": REFERENCE_VOCE_HOLDOUT_PLAN_SCHEMA_VERSION,
        "fields": [
            "plan_label",
            "material_model_id",
            "material_model_revision_id",
            "holdout_dataset_id",
            "holdout_dataset_revision_id",
            "metric_profile_id",
            "threshold_profile_id",
            "relative_rmse_threshold",
            "overlap_policy",
            "evaluation_mode",
            "non_production",
        ],
        "metric_profile_id": REFERENCE_VOCE_HOLDOUT_METRIC_PROFILE_ID,
        "threshold_profile_id": REFERENCE_VOCE_HOLDOUT_THRESHOLD_PROFILE_ID,
    }
)

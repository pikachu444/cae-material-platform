"""Deterministic scalar-distribution fitting for an existing replicate Statistics Run."""

from __future__ import annotations

import hashlib
import math
import platform
import sys
import warnings
from dataclasses import dataclass, replace
from enum import StrEnum
from pathlib import Path
from uuid import UUID

import numpy as np
import scipy  # type: ignore[import-untyped]
from scipy import optimize

from cmp.modules.statistics.domain.reference_tensile_pair import InvalidStatisticsRequest
from cmp.modules.units.domain.profiles import (
    UnitApplication,
    UnitProfilePin,
    unit_application_canonical,
    unit_profile_pin_canonical,
)
from cmp.shared.domain.revisions import canonical_json_bytes, content_sha256

SCALAR_DISTRIBUTION_PLAN_SCHEMA = "urn:cmp:statistics:scalar-distribution-plan:1.0.0"
SCALAR_DISTRIBUTION_RESULT_SCHEMA = "urn:cmp:statistics:scalar-distribution-result:1.0.0"
SCALAR_DISTRIBUTION_SELECTION_SCHEMA = "urn:cmp:statistics:scalar-distribution-selection:1.0.0"
SCALAR_DISTRIBUTION_ARTIFACT_MEDIA_TYPE = "application/vnd.cmp.scalar-distribution-result+json"
SCALAR_DISTRIBUTION_ALGORITHM_VERSION = "scalar_distribution_fitting_v1"
SCALAR_DISTRIBUTION_RECOMMENDATION_METHOD = "aicc_delta_le_2_at_least_two_successful_candidates_v1"
SCALAR_DISTRIBUTION_RNG = "numpy.random.PCG64"
SCALAR_DISTRIBUTION_BOOTSTRAP_SAMPLES = 999
SCALAR_DISTRIBUTION_MINIMUM_SAMPLE_COUNT = 8
SCALAR_DISTRIBUTION_SMALL_SAMPLE_WARNING_BELOW = 20
SCALAR_DISTRIBUTION_SCALAR_FEATURE = "peak_engineering_stress_pa"
SCALAR_DISTRIBUTION_FAMILY_ORDER: tuple[DistributionFamily, ...]


class DistributionFamily(StrEnum):
    NORMAL = "normal"
    LOGNORMAL = "lognormal"
    WEIBULL = "weibull"


SCALAR_DISTRIBUTION_FAMILY_ORDER = (
    DistributionFamily.NORMAL,
    DistributionFamily.LOGNORMAL,
    DistributionFamily.WEIBULL,
)


class DistributionCandidateStatus(StrEnum):
    SUCCEEDED = "succeeded"
    NOT_ELIGIBLE = "not_eligible"
    FAILED = "failed"


class ObservationQuality(StrEnum):
    OBSERVED = "observed"
    MISSING = "missing"
    NON_FINITE = "non_finite"
    CENSORED = "censored"


class OutlierAssessmentState(StrEnum):
    NOT_ASSESSED = "not_assessed"
    FLAGGED = "flagged"
    NOT_FLAGGED = "not_flagged"


_SUPPORT = {
    DistributionFamily.NORMAL: "real",
    DistributionFamily.LOGNORMAL: "positive",
    DistributionFamily.WEIBULL: "positive",
}
_ESTIMATOR = {
    DistributionFamily.NORMAL: "normal_two_parameter_mle_v1",
    DistributionFamily.LOGNORMAL: "lognormal_two_parameter_loc_zero_mle_v1",
    DistributionFamily.WEIBULL: "weibull_two_parameter_loc_zero_mle_v1",
}
_FAMILY_SEED = {
    DistributionFamily.NORMAL: 11,
    DistributionFamily.LOGNORMAL: 23,
    DistributionFamily.WEIBULL: 37,
}
_FLOAT64_LOG_MAX = math.log(np.finfo(np.float64).max)


def _uuid(name: str, value: UUID) -> None:
    if value.int == 0:
        raise InvalidStatisticsRequest(f"{name} must be non-zero")


def _sha256(name: str, value: str) -> None:
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise InvalidStatisticsRequest(f"{name} must be a lowercase SHA-256 digest")


def _finite_or_none(name: str, value: float | None, *, nonnegative: bool = False) -> None:
    if value is None:
        return
    if not math.isfinite(value) or (nonnegative and value < 0.0):
        raise InvalidStatisticsRequest(f"{name} must be finite")


@dataclass(frozen=True, slots=True)
class ScalarDistributionAnalysisOptions:
    seed: int
    bootstrap_samples: int = SCALAR_DISTRIBUTION_BOOTSTRAP_SAMPLES
    unit_profile: UnitProfilePin | None = None

    def __post_init__(self) -> None:
        if not 0 <= self.seed <= 0xFFFFFFFF:
            raise InvalidStatisticsRequest("distribution seed must be between 0 and 4294967295")
        if self.bootstrap_samples != SCALAR_DISTRIBUTION_BOOTSTRAP_SAMPLES:
            raise InvalidStatisticsRequest(
                "distribution fitting requires exactly 999 bootstrap samples"
            )


def scalar_distribution_options_canonical(
    value: ScalarDistributionAnalysisOptions,
) -> dict[str, object]:
    return {
        "schema_ref": SCALAR_DISTRIBUTION_PLAN_SCHEMA,
        "seed": value.seed,
        "bootstrap_samples": value.bootstrap_samples,
        "rng": SCALAR_DISTRIBUTION_RNG,
        "candidate_order": [item.value for item in SCALAR_DISTRIBUTION_FAMILY_ORDER],
        "estimators": {
            family.value: _ESTIMATOR[family] for family in SCALAR_DISTRIBUTION_FAMILY_ORDER
        },
        "goodness_of_fit": {
            "statistics": ["log_likelihood", "aicc", "bic", "anderson_darling"],
            "bootstrap_p_value": "estimator_aware_parametric_add_one_v1",
        },
        "recommendation": SCALAR_DISTRIBUTION_RECOMMENDATION_METHOD,
        "minimum_sample_count": SCALAR_DISTRIBUTION_MINIMUM_SAMPLE_COUNT,
        "small_sample_warning_below": SCALAR_DISTRIBUTION_SMALL_SAMPLE_WARNING_BELOW,
        "censoring": "unsupported",
        "missing_values": "not_complete_case",
        "unsupported_quality_value": "canonical_null_with_quality_v1",
        "extreme_range": "reject_unrepresentable_float64_magnitude_ratio_v1",
        "outliers": "retain_all_observations_and_report_assessment_state",
        "unit_profile": (
            unit_profile_pin_canonical(value.unit_profile)
            if value.unit_profile is not None
            else None
        ),
    }


@dataclass(frozen=True, slots=True)
class ScalarDistributionObservation:
    ordinal: int
    dataset_id: UUID
    dataset_revision_id: UUID
    test_run_id: UUID
    test_run_revision_id: UUID
    value_pa: float | None
    quality: ObservationQuality = ObservationQuality.OBSERVED
    outlier_assessment: OutlierAssessmentState = OutlierAssessmentState.NOT_ASSESSED

    def __post_init__(self) -> None:
        if not 0 <= self.ordinal < 50:
            raise InvalidStatisticsRequest("distribution observation ordinal must be 0..49")
        for name, value in (
            ("dataset_id", self.dataset_id),
            ("dataset_revision_id", self.dataset_revision_id),
            ("test_run_id", self.test_run_id),
            ("test_run_revision_id", self.test_run_revision_id),
        ):
            _uuid(name, value)
        if self.quality is ObservationQuality.OBSERVED:
            if self.value_pa is None or not math.isfinite(self.value_pa):
                raise InvalidStatisticsRequest("observed scalar values must be finite")
        elif self.value_pa is not None and math.isfinite(self.value_pa):
            raise InvalidStatisticsRequest("unsupported observation qualities cannot carry a value")


def scalar_distribution_observation_canonical(
    value: ScalarDistributionObservation,
) -> dict[str, object]:
    return {
        "ordinal": value.ordinal,
        "dataset_id": str(value.dataset_id),
        "dataset_revision_id": str(value.dataset_revision_id),
        "test_run_id": str(value.test_run_id),
        "test_run_revision_id": str(value.test_run_revision_id),
        # JSON cannot represent NaN or infinities. The quality field preserves
        # why the source value is unavailable; unsupported values are always
        # persisted as null without changing the source observation record.
        "value_pa": (
            value.value_pa if value.quality is ObservationQuality.OBSERVED else None
        ),
        "quality": value.quality.value,
        "outlier_assessment": value.outlier_assessment.value,
    }


@dataclass(frozen=True, slots=True)
class DistributionParameter:
    name: str
    value: float
    unit_id: str | None

    def __post_init__(self) -> None:
        if self.name not in {"location", "scale", "shape"}:
            raise InvalidStatisticsRequest("distribution parameter name is unsupported")
        if not math.isfinite(self.value):
            raise InvalidStatisticsRequest("distribution parameter must be finite")
        if self.unit_id is not None and self.unit_id not in {"Pa"}:
            raise InvalidStatisticsRequest("distribution parameter unit is unsupported")


@dataclass(frozen=True, slots=True)
class ScalarDistributionCandidate:
    family: DistributionFamily
    status: DistributionCandidateStatus
    support: str
    estimator: str
    parameters: tuple[DistributionParameter, ...]
    log_likelihood: float | None
    aicc: float | None
    bic: float | None
    anderson_darling: float | None
    bootstrap_p_value: float | None
    bootstrap_success_count: int
    bootstrap_failure_count: int
    delta_aicc: float | None
    recommended: bool
    reason_codes: tuple[str, ...]
    warnings: tuple[str, ...]
    candidate_sha256: str

    def __post_init__(self) -> None:
        if self.support != _SUPPORT[self.family] or self.estimator != _ESTIMATOR[self.family]:
            raise InvalidStatisticsRequest("distribution candidate method contract is inconsistent")
        if self.status is DistributionCandidateStatus.SUCCEEDED:
            if len(self.parameters) != 2 or any(
                value is None
                for value in (
                    self.log_likelihood,
                    self.aicc,
                    self.bic,
                    self.anderson_darling,
                    self.bootstrap_p_value,
                )
            ):
                raise InvalidStatisticsRequest(
                    "successful candidates require parameters and metrics"
                )
        elif self.parameters or any(
            value is not None
            for value in (
                self.log_likelihood,
                self.aicc,
                self.bic,
                self.anderson_darling,
                self.bootstrap_p_value,
                self.delta_aicc,
            )
        ):
            raise InvalidStatisticsRequest("unsuccessful candidates cannot carry fitted values")
        for name, value in (
            ("log_likelihood", self.log_likelihood),
            ("aicc", self.aicc),
            ("bic", self.bic),
            ("anderson_darling", self.anderson_darling),
            ("bootstrap_p_value", self.bootstrap_p_value),
            ("delta_aicc", self.delta_aicc),
        ):
            _finite_or_none(
                name,
                value,
                nonnegative=name in {"anderson_darling", "bootstrap_p_value", "delta_aicc"},
            )
        if self.bootstrap_p_value is not None and not 0.0 <= self.bootstrap_p_value <= 1.0:
            raise InvalidStatisticsRequest("bootstrap p-value must be within [0, 1]")
        if (
            not 0 <= self.bootstrap_success_count <= SCALAR_DISTRIBUTION_BOOTSTRAP_SAMPLES
            or not 0 <= self.bootstrap_failure_count <= SCALAR_DISTRIBUTION_BOOTSTRAP_SAMPLES
            or self.bootstrap_success_count + self.bootstrap_failure_count
            not in {0, SCALAR_DISTRIBUTION_BOOTSTRAP_SAMPLES}
        ):
            raise InvalidStatisticsRequest("bootstrap accounting is inconsistent")
        if not self.reason_codes:
            raise InvalidStatisticsRequest("candidate requires at least one explicit reason code")
        _sha256("candidate_sha256", self.candidate_sha256)


def _parameter_canonical(value: DistributionParameter) -> dict[str, object]:
    return {"name": value.name, "estimate": value.value, "unit_id": value.unit_id}


def scalar_distribution_candidate_canonical(
    value: ScalarDistributionCandidate, *, include_digest: bool = True
) -> dict[str, object]:
    result: dict[str, object] = {
        "family": value.family.value,
        "status": value.status.value,
        "support": value.support,
        "estimator": value.estimator,
        "parameter_count": 2,
        "parameters": [_parameter_canonical(item) for item in value.parameters],
        "log_likelihood": value.log_likelihood,
        "aicc": value.aicc,
        "bic": value.bic,
        "anderson_darling": value.anderson_darling,
        "bootstrap_p_value": value.bootstrap_p_value,
        "bootstrap_success_count": value.bootstrap_success_count,
        "bootstrap_failure_count": value.bootstrap_failure_count,
        "delta_aicc": value.delta_aicc,
        "recommended": value.recommended,
        "reason_codes": list(value.reason_codes),
        "warnings": list(value.warnings),
    }
    if include_digest:
        result["candidate_sha256"] = value.candidate_sha256
    return result


@dataclass(frozen=True, slots=True)
class ScalarDistributionRuntimeManifest:
    algorithm_version: str
    schema_ref: str
    python_version: str
    numpy_version: str
    scipy_version: str
    rng: str
    source_sha256: str
    lock_sha256: str
    environment_sha256: str

    def __post_init__(self) -> None:
        if (
            self.algorithm_version != SCALAR_DISTRIBUTION_ALGORITHM_VERSION
            or self.schema_ref != SCALAR_DISTRIBUTION_RESULT_SCHEMA
            or self.rng != SCALAR_DISTRIBUTION_RNG
        ):
            raise InvalidStatisticsRequest("distribution runtime method contract is unsupported")
        for name in ("source_sha256", "lock_sha256", "environment_sha256"):
            _sha256(name, getattr(self, name))


def scalar_distribution_runtime_manifest_canonical(
    value: ScalarDistributionRuntimeManifest,
) -> dict[str, str]:
    return {
        "algorithm_version": value.algorithm_version,
        "schema_ref": value.schema_ref,
        "python_version": value.python_version,
        "numpy_version": value.numpy_version,
        "scipy_version": value.scipy_version,
        "rng": value.rng,
        "source_sha256": value.source_sha256,
        "lock_sha256": value.lock_sha256,
        "environment_sha256": value.environment_sha256,
    }


def _file_sha256(path: Path | None, fallback: bytes) -> str:
    if path is not None and path.is_file():
        return hashlib.sha256(path.read_bytes()).hexdigest()
    return hashlib.sha256(fallback).hexdigest()


def runtime_manifest() -> ScalarDistributionRuntimeManifest:
    source_path = Path(__file__).resolve()
    lock_path = next(
        (parent / "uv.lock" for parent in source_path.parents if (parent / "uv.lock").is_file()),
        None,
    )
    environment = {
        "implementation": platform.python_implementation(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "numpy": np.__version__,
        "scipy": scipy.__version__,
    }
    return ScalarDistributionRuntimeManifest(
        algorithm_version=SCALAR_DISTRIBUTION_ALGORITHM_VERSION,
        schema_ref=SCALAR_DISTRIBUTION_RESULT_SCHEMA,
        python_version=sys.version.split()[0],
        numpy_version=np.__version__,
        scipy_version=scipy.__version__,
        rng=SCALAR_DISTRIBUTION_RNG,
        source_sha256=_file_sha256(source_path, b"scalar_distribution.py:unavailable"),
        lock_sha256=_file_sha256(
            lock_path,
            f"numpy={np.__version__};scipy={scipy.__version__}".encode(),
        ),
        environment_sha256=content_sha256(environment),
    )


@dataclass(frozen=True, slots=True)
class ScalarDistributionComputation:
    observations: tuple[ScalarDistributionObservation, ...]
    candidates: tuple[ScalarDistributionCandidate, ...]
    recommended_families: tuple[DistributionFamily, ...]
    manifest: ScalarDistributionRuntimeManifest


@dataclass(frozen=True, slots=True)
class ScalarDistributionResultContent:
    statistical_run_id: UUID
    statistical_result_id: UUID
    statistical_result_revision_id: UUID
    plan_id: UUID
    plan_revision_id: UUID
    selection_id: UUID
    selection_revision_id: UUID
    artifact_id: UUID
    artifact_sha256: str
    options: ScalarDistributionAnalysisOptions
    unit_applications: tuple[UnitApplication, ...]
    computation: ScalarDistributionComputation

    def __post_init__(self) -> None:
        for name in (
            "statistical_run_id",
            "statistical_result_id",
            "statistical_result_revision_id",
            "plan_id",
            "plan_revision_id",
            "selection_id",
            "selection_revision_id",
            "artifact_id",
        ):
            _uuid(name, getattr(self, name))
        _sha256("artifact_sha256", self.artifact_sha256)
        if self.options.unit_profile is None and self.unit_applications:
            raise InvalidStatisticsRequest("unit applications require an exact Unit Profile pin")
        if self.options.unit_profile is not None and len(self.unit_applications) != 1:
            raise InvalidStatisticsRequest("distribution display requires one unit application")


@dataclass(frozen=True, slots=True)
class ScalarDistributionSelectionContent:
    distribution_result_id: UUID
    distribution_result_revision_id: UUID
    selected_family: DistributionFamily
    candidate_sha256: str
    selection_reason: str

    def __post_init__(self) -> None:
        _uuid("distribution_result_id", self.distribution_result_id)
        _uuid("distribution_result_revision_id", self.distribution_result_revision_id)
        _sha256("candidate_sha256", self.candidate_sha256)
        if (
            not self.selection_reason
            or self.selection_reason != self.selection_reason.strip()
            or len(self.selection_reason) > 2000
            or "\x00" in self.selection_reason
        ):
            raise InvalidStatisticsRequest(
                "selection_reason must be trimmed and contain 1..2000 characters"
            )


def scalar_distribution_selection_canonical(
    value: ScalarDistributionSelectionContent,
) -> dict[str, object]:
    return {
        "schema_ref": SCALAR_DISTRIBUTION_SELECTION_SCHEMA,
        "distribution_result_id": str(value.distribution_result_id),
        "distribution_result_revision_id": str(value.distribution_result_revision_id),
        "selected_family": value.selected_family.value,
        "candidate_sha256": value.candidate_sha256,
        "selection_reason": value.selection_reason,
    }


@dataclass(frozen=True, slots=True)
class _Fit:
    parameters: tuple[DistributionParameter, DistributionParameter]
    log_likelihood: float
    cdf: np.ndarray
    sampler: tuple[float, float]


def _anderson_darling(cdf: np.ndarray) -> float:
    ordered = np.clip(np.sort(cdf.astype(float)), 1e-15, 1.0 - 1e-15)
    n = ordered.size
    index = np.arange(1, n + 1, dtype=float)
    value = -n - np.sum((2.0 * index - 1.0) * (np.log(ordered) + np.log1p(-ordered[::-1]))) / n
    return float(max(value, 0.0))


def _normal_fit(values: np.ndarray) -> _Fit:
    reference = float(np.max(np.abs(values)))
    if not math.isfinite(reference) or reference == 0.0:
        raise ValueError("constant_sample")
    scaled = values / reference
    mean_scaled = float(np.mean(scaled))
    sigma_scaled = float(np.sqrt(np.mean(np.square(scaled - mean_scaled))))
    if not math.isfinite(sigma_scaled) or sigma_scaled <= 0.0:
        raise ValueError("constant_sample")
    mean = mean_scaled * reference
    sigma = sigma_scaled * reference
    z = (values - mean) / sigma
    log_likelihood = float(
        -values.size * math.log(sigma)
        - values.size * 0.5 * math.log(2.0 * math.pi)
        - 0.5 * np.sum(np.square(z))
    )
    cdf = np.asarray(scipy.special.ndtr(z), dtype=float)
    return _Fit(
        parameters=(
            DistributionParameter("location", mean, "Pa"),
            DistributionParameter("scale", sigma, "Pa"),
        ),
        log_likelihood=log_likelihood,
        cdf=cdf,
        sampler=(mean, sigma),
    )


def _lognormal_fit(values: np.ndarray) -> _Fit:
    if np.any(values <= 0.0):
        raise ValueError("support_requires_positive")
    logs = np.log(values)
    mean_log = float(np.mean(logs))
    sigma_log = float(np.sqrt(np.mean(np.square(logs - mean_log))))
    if not math.isfinite(sigma_log) or sigma_log <= 0.0:
        raise ValueError("constant_sample")
    scale = math.exp(mean_log)
    standardized = (logs - mean_log) / sigma_log
    log_likelihood = float(
        -np.sum(logs)
        - values.size * math.log(sigma_log)
        - values.size * 0.5 * math.log(2.0 * math.pi)
        - 0.5 * np.sum(np.square(standardized))
    )
    return _Fit(
        parameters=(
            DistributionParameter("shape", sigma_log, None),
            DistributionParameter("scale", scale, "Pa"),
        ),
        log_likelihood=log_likelihood,
        cdf=np.asarray(scipy.special.ndtr(standardized), dtype=float),
        sampler=(mean_log, sigma_log),
    )


def _weibull_parameters(logs: np.ndarray) -> tuple[float, float]:
    mean_log = float(np.mean(logs))

    def score(shape: float) -> float:
        weighted = shape * logs
        pivot = float(np.max(weighted))
        weights = np.exp(weighted - pivot)
        weighted_mean = float(np.sum(weights * logs) / np.sum(weights))
        return 1.0 / shape + mean_log - weighted_mean

    lower = 1e-6
    upper = 1.0
    while score(upper) > 0.0 and upper < 1e6:
        upper *= 2.0
    if score(lower) * score(upper) >= 0.0:
        raise ValueError("numerical_fit_failure")
    shape = float(optimize.brentq(score, lower, upper, xtol=1e-12, rtol=1e-12))
    weighted = shape * logs
    pivot = float(np.max(weighted))
    log_scale = (pivot + math.log(float(np.mean(np.exp(weighted - pivot))))) / shape
    scale = math.exp(log_scale)
    if not math.isfinite(scale) or scale <= 0.0:
        raise ValueError("numerical_fit_failure")
    return shape, scale


def _weibull_fit(values: np.ndarray) -> _Fit:
    if np.any(values <= 0.0):
        raise ValueError("support_requires_positive")
    logs = np.log(values)
    shape, scale = _weibull_parameters(logs)
    log_scale = math.log(scale)
    exponent = shape * (logs - log_scale)
    powered = np.exp(np.clip(exponent, -745.0, 709.0))
    log_likelihood = float(
        values.size * math.log(shape)
        - values.size * shape * log_scale
        + (shape - 1.0) * np.sum(logs)
        - np.sum(powered)
    )
    cdf = -np.expm1(-powered)
    return _Fit(
        parameters=(
            DistributionParameter("shape", shape, None),
            DistributionParameter("scale", scale, "Pa"),
        ),
        log_likelihood=log_likelihood,
        cdf=np.asarray(cdf, dtype=float),
        sampler=(shape, scale),
    )


def _fit(family: DistributionFamily, values: np.ndarray) -> _Fit:
    if family is DistributionFamily.NORMAL:
        return _normal_fit(values)
    if family is DistributionFamily.LOGNORMAL:
        return _lognormal_fit(values)
    return _weibull_fit(values)


def _has_unrepresentable_float64_magnitude_ratio(values: np.ndarray) -> bool:
    """Reject a magnitude ratio that cannot itself be represented by float64."""

    magnitudes = np.abs(values[values != 0.0])
    if magnitudes.size < 2:
        return False
    log_span = math.log(float(np.max(magnitudes))) - math.log(
        float(np.min(magnitudes))
    )
    return log_span > _FLOAT64_LOG_MAX


def _sample(
    family: DistributionFamily,
    fitted: _Fit,
    rng: np.random.Generator,
    n: int,
) -> np.ndarray:
    first, second = fitted.sampler
    if family is DistributionFamily.NORMAL:
        return np.asarray(rng.normal(first, second, n), dtype=float)
    if family is DistributionFamily.LOGNORMAL:
        return np.asarray(rng.lognormal(first, second, n), dtype=float)
    return np.asarray(second * rng.weibull(first, n), dtype=float)


def _bootstrap(
    family: DistributionFamily,
    fitted: _Fit,
    observed_ad: float,
    *,
    n: int,
    options: ScalarDistributionAnalysisOptions,
) -> tuple[float | None, int, int]:
    rng = np.random.Generator(
        np.random.PCG64(np.random.SeedSequence([options.seed, _FAMILY_SEED[family]]))
    )
    exceedances = 0
    successes = 0
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        for _ in range(options.bootstrap_samples):
            try:
                generated = _sample(family, fitted, rng, n)
                if not np.all(np.isfinite(generated)):
                    raise ValueError("non_finite_bootstrap_sample")
                simulated = _fit(family, generated)
                simulated_ad = _anderson_darling(simulated.cdf)
            except (ArithmeticError, FloatingPointError, OverflowError, ValueError):
                continue
            successes += 1
            if simulated_ad >= observed_ad:
                exceedances += 1
    failures = options.bootstrap_samples - successes
    if successes == 0:
        return None, successes, failures
    return (exceedances + 1.0) / (successes + 1.0), successes, failures


def _unavailable_candidate(
    family: DistributionFamily,
    status: DistributionCandidateStatus,
    reason: str,
    warnings_: tuple[str, ...],
    *,
    digest_context: dict[str, object],
) -> ScalarDistributionCandidate:
    provisional = ScalarDistributionCandidate(
        family=family,
        status=status,
        support=_SUPPORT[family],
        estimator=_ESTIMATOR[family],
        parameters=(),
        log_likelihood=None,
        aicc=None,
        bic=None,
        anderson_darling=None,
        bootstrap_p_value=None,
        bootstrap_success_count=0,
        bootstrap_failure_count=0,
        delta_aicc=None,
        recommended=False,
        reason_codes=(reason,),
        warnings=warnings_,
        candidate_sha256="0" * 64,
    )
    digest = content_sha256(
        {
            **digest_context,
            "candidate": scalar_distribution_candidate_canonical(provisional, include_digest=False),
        }
    )
    return replace(provisional, candidate_sha256=digest)


def fit_scalar_distributions(
    observations: tuple[ScalarDistributionObservation, ...],
    options: ScalarDistributionAnalysisOptions,
    *,
    manifest: ScalarDistributionRuntimeManifest | None = None,
) -> ScalarDistributionComputation:
    """Fit all approved families while preserving candidate-specific outcomes."""

    if not 2 <= len(observations) <= 50:
        raise InvalidStatisticsRequest("distribution fitting requires 2..50 observations")
    if tuple(item.ordinal for item in observations) != tuple(range(len(observations))):
        raise InvalidStatisticsRequest("distribution observations require contiguous ordinals")
    identities = {(item.dataset_revision_id, item.test_run_revision_id) for item in observations}
    if len(identities) != len(observations):
        raise InvalidStatisticsRequest(
            "distribution observations must pin distinct sample identities"
        )
    active_manifest = manifest or runtime_manifest()
    normalized_observations = tuple(
        item
        if item.quality is ObservationQuality.OBSERVED or item.value_pa is None
        else replace(item, value_pa=None)
        for item in observations
    )
    observations_digest = content_sha256(
        [scalar_distribution_observation_canonical(item) for item in normalized_observations]
    )
    digest_context: dict[str, object] = {
        "schema_ref": SCALAR_DISTRIBUTION_RESULT_SCHEMA,
        "observations_sha256": observations_digest,
        "options": scalar_distribution_options_canonical(options),
        "runtime_manifest": scalar_distribution_runtime_manifest_canonical(active_manifest),
    }
    warnings_: list[str] = []
    if len(observations) < SCALAR_DISTRIBUTION_SMALL_SAMPLE_WARNING_BELOW:
        warnings_.append("small_sample_n_8_to_19_interpret_with_caution")
    if any(item.outlier_assessment is OutlierAssessmentState.FLAGGED for item in observations):
        warnings_.append("flagged_outlier_assessments_retained_no_automatic_exclusion")
    unsupported = next(
        (
            item.quality.value
            for item in normalized_observations
            if item.quality is not ObservationQuality.OBSERVED
        ),
        None,
    )
    values = np.asarray(
        [
            item.value_pa
            for item in normalized_observations
            if item.quality is ObservationQuality.OBSERVED and item.value_pa is not None
        ],
        dtype=float,
    )
    extreme_range = _has_unrepresentable_float64_magnitude_ratio(values)
    candidates: list[ScalarDistributionCandidate] = []
    for family in SCALAR_DISTRIBUTION_FAMILY_ORDER:
        if unsupported is not None:
            candidates.append(
                _unavailable_candidate(
                    family,
                    DistributionCandidateStatus.NOT_ELIGIBLE,
                    f"unsupported_observation_quality:{unsupported}",
                    tuple(warnings_),
                    digest_context=digest_context,
                )
            )
            continue
        if len(observations) < SCALAR_DISTRIBUTION_MINIMUM_SAMPLE_COUNT:
            candidates.append(
                _unavailable_candidate(
                    family,
                    DistributionCandidateStatus.NOT_ELIGIBLE,
                    "insufficient_sample_n_lt_8",
                    tuple(warnings_),
                    digest_context=digest_context,
                )
            )
            continue
        if np.all(values == values[0]):
            candidates.append(
                _unavailable_candidate(
                    family,
                    DistributionCandidateStatus.NOT_ELIGIBLE,
                    "constant_sample",
                    tuple(warnings_),
                    digest_context=digest_context,
                )
            )
            continue
        if family is not DistributionFamily.NORMAL and np.any(values <= 0.0):
            candidates.append(
                _unavailable_candidate(
                    family,
                    DistributionCandidateStatus.NOT_ELIGIBLE,
                    "support_requires_positive",
                    tuple(warnings_),
                    digest_context=digest_context,
                )
            )
            continue
        if extreme_range:
            candidates.append(
                _unavailable_candidate(
                    family,
                    DistributionCandidateStatus.NOT_ELIGIBLE,
                    "extreme_dynamic_range_exceeds_float64_ratio",
                    tuple(warnings_),
                    digest_context=digest_context,
                )
            )
            continue
        try:
            fitted = _fit(family, values)
            ad = _anderson_darling(fitted.cdf)
            bootstrap_p, bootstrap_success, bootstrap_failure = _bootstrap(
                family,
                fitted,
                ad,
                n=values.size,
                options=options,
            )
            if bootstrap_p is None:
                raise ValueError("bootstrap_refits_all_failed")
            parameter_count = 2
            aic = 2.0 * parameter_count - 2.0 * fitted.log_likelihood
            aicc = aic + (
                2.0
                * parameter_count
                * (parameter_count + 1.0)
                / (values.size - parameter_count - 1.0)
            )
            bic = parameter_count * math.log(values.size) - 2.0 * fitted.log_likelihood
            provisional = ScalarDistributionCandidate(
                family=family,
                status=DistributionCandidateStatus.SUCCEEDED,
                support=_SUPPORT[family],
                estimator=_ESTIMATOR[family],
                parameters=fitted.parameters,
                log_likelihood=fitted.log_likelihood,
                aicc=float(aicc),
                bic=float(bic),
                anderson_darling=ad,
                bootstrap_p_value=bootstrap_p,
                bootstrap_success_count=bootstrap_success,
                bootstrap_failure_count=bootstrap_failure,
                delta_aicc=None,
                recommended=False,
                reason_codes=("fit_succeeded",),
                warnings=tuple(warnings_),
                candidate_sha256="0" * 64,
            )
            digest = content_sha256(
                {
                    **digest_context,
                    "candidate": scalar_distribution_candidate_canonical(
                        provisional, include_digest=False
                    ),
                }
            )
            candidates.append(replace(provisional, candidate_sha256=digest))
        except (ArithmeticError, FloatingPointError, OverflowError, ValueError) as error:
            candidates.append(
                _unavailable_candidate(
                    family,
                    DistributionCandidateStatus.FAILED,
                    f"numerical_fit_failure:{str(error)[:64]}",
                    tuple(warnings_),
                    digest_context=digest_context,
                )
            )

    successful = [
        item
        for item in candidates
        if item.status is DistributionCandidateStatus.SUCCEEDED and item.aicc is not None
    ]
    recommended: tuple[DistributionFamily, ...] = ()
    if len(successful) >= 2:
        minimum_aicc = min(item.aicc for item in successful if item.aicc is not None)
        ranked: list[ScalarDistributionCandidate] = []
        for item in candidates:
            if item.aicc is None:
                ranked.append(item)
                continue
            delta = max(item.aicc - minimum_aicc, 0.0)
            selected = delta <= 2.0
            revised = replace(item, delta_aicc=delta, recommended=selected)
            digest = content_sha256(
                {
                    **digest_context,
                    "candidate": scalar_distribution_candidate_canonical(
                        revised, include_digest=False
                    ),
                }
            )
            ranked.append(replace(revised, candidate_sha256=digest))
        candidates = ranked
        recommended = tuple(item.family for item in candidates if item.recommended)
    return ScalarDistributionComputation(
        observations=normalized_observations,
        candidates=tuple(candidates),
        recommended_families=recommended,
        manifest=active_manifest,
    )


def scalar_distribution_artifact_canonical(
    *,
    statistical_run_id: UUID,
    statistical_result_id: UUID,
    statistical_result_revision_id: UUID,
    plan_id: UUID,
    plan_revision_id: UUID,
    selection_id: UUID,
    selection_revision_id: UUID,
    options: ScalarDistributionAnalysisOptions,
    unit_applications: tuple[UnitApplication, ...],
    computation: ScalarDistributionComputation,
) -> dict[str, object]:
    return {
        "schema_ref": SCALAR_DISTRIBUTION_RESULT_SCHEMA,
        "scalar_feature": SCALAR_DISTRIBUTION_SCALAR_FEATURE,
        "plan_id": str(plan_id),
        "plan_revision_id": str(plan_revision_id),
        "selection_id": str(selection_id),
        "selection_revision_id": str(selection_revision_id),
        "sample_count": len(computation.observations),
        "minimum_sample_count": SCALAR_DISTRIBUTION_MINIMUM_SAMPLE_COUNT,
        "small_sample_warning_below": SCALAR_DISTRIBUTION_SMALL_SAMPLE_WARNING_BELOW,
        "options": scalar_distribution_options_canonical(options),
        "observations": [
            scalar_distribution_observation_canonical(item) for item in computation.observations
        ],
        "candidates": [
            scalar_distribution_candidate_canonical(item) for item in computation.candidates
        ],
        "recommended_families": [item.value for item in computation.recommended_families],
        "recommendation_method": SCALAR_DISTRIBUTION_RECOMMENDATION_METHOD,
        "unit_applications": [unit_application_canonical(item) for item in unit_applications],
        "runtime_manifest": scalar_distribution_runtime_manifest_canonical(computation.manifest),
    }


def scalar_distribution_artifact_bytes(**kwargs: object) -> bytes:
    return canonical_json_bytes(scalar_distribution_artifact_canonical(**kwargs))  # type: ignore[arg-type]


def scalar_distribution_result_canonical(
    value: ScalarDistributionResultContent,
) -> dict[str, object]:
    return {
        **scalar_distribution_artifact_canonical(
            statistical_run_id=value.statistical_run_id,
            statistical_result_id=value.statistical_result_id,
            statistical_result_revision_id=value.statistical_result_revision_id,
            plan_id=value.plan_id,
            plan_revision_id=value.plan_revision_id,
            selection_id=value.selection_id,
            selection_revision_id=value.selection_revision_id,
            options=value.options,
            unit_applications=value.unit_applications,
            computation=value.computation,
        ),
        "statistical_run_id": str(value.statistical_run_id),
        "statistical_result_id": str(value.statistical_result_id),
        "statistical_result_revision_id": str(value.statistical_result_revision_id),
        "artifact_id": str(value.artifact_id),
        "artifact_sha256": value.artifact_sha256,
    }


__all__ = [
    "SCALAR_DISTRIBUTION_ALGORITHM_VERSION",
    "SCALAR_DISTRIBUTION_ARTIFACT_MEDIA_TYPE",
    "SCALAR_DISTRIBUTION_BOOTSTRAP_SAMPLES",
    "SCALAR_DISTRIBUTION_FAMILY_ORDER",
    "SCALAR_DISTRIBUTION_MINIMUM_SAMPLE_COUNT",
    "SCALAR_DISTRIBUTION_RECOMMENDATION_METHOD",
    "SCALAR_DISTRIBUTION_RESULT_SCHEMA",
    "SCALAR_DISTRIBUTION_SCALAR_FEATURE",
    "SCALAR_DISTRIBUTION_SMALL_SAMPLE_WARNING_BELOW",
    "DistributionCandidateStatus",
    "DistributionFamily",
    "DistributionParameter",
    "ObservationQuality",
    "OutlierAssessmentState",
    "ScalarDistributionAnalysisOptions",
    "ScalarDistributionCandidate",
    "ScalarDistributionComputation",
    "ScalarDistributionObservation",
    "ScalarDistributionResultContent",
    "ScalarDistributionRuntimeManifest",
    "ScalarDistributionSelectionContent",
    "fit_scalar_distributions",
    "runtime_manifest",
    "scalar_distribution_artifact_bytes",
    "scalar_distribution_artifact_canonical",
    "scalar_distribution_candidate_canonical",
    "scalar_distribution_observation_canonical",
    "scalar_distribution_options_canonical",
    "scalar_distribution_result_canonical",
    "scalar_distribution_runtime_manifest_canonical",
    "scalar_distribution_selection_canonical",
]

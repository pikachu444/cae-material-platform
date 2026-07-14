"""Typed T-28 result interpretation for the bounded reference virtual specimen.

The module deliberately keeps result extraction, numerical health, and experimental
comparison separate from T-27 execution evidence.  It supports one explicit,
non-production reference profile only: SI engineering stress--strain channels,
linear interpolation at the observed strain grid without extrapolation, and a
relative-RMSE threshold.  It is not a production solver-validation policy.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from cmp.modules.validation.domain.reference_virtual_specimen import (
    REFERENCE_NATIVE_RESULT_SCHEMA_ID,
    REFERENCE_SCHEMA_VERSION,
    ReferenceVirtualSpecimenTemplateContent,
    SolverTerminationStatus,
    ValidationArtifactReference,
    ValidationConflict,
    ValidationError,
)
from cmp.shared.domain.revisions import canonical_json_bytes, content_sha256

REFERENCE_NORMALIZED_RESPONSE_SCHEMA_ID = "urn:cmp:validation:reference-normalized-response:1.0.0"
REFERENCE_NUMERICAL_HEALTH_REPORT_SCHEMA_ID = (
    "urn:cmp:validation:reference-numerical-health-report:1.0.0"
)
REFERENCE_VALIDATION_RESULT_SCHEMA_ID = "urn:cmp:validation:reference-validation-result:1.0.0"
REFERENCE_ALIGNMENT_PROFILE_ID = (
    "urn:cmp:validation:reference-linear-interpolation-observed-grid:1.0.0"
)
REFERENCE_THRESHOLD_PROFILE_ID = "urn:cmp:validation:reference-relative-rmse-threshold:1.0.0"
REFERENCE_RELATIVE_RMSE_THRESHOLD = 0.05
REFERENCE_STRESS_NORMALIZATION_FLOOR_PA = 1.0
MAX_REFERENCE_RESPONSE_POINTS = 10_000


class ReferenceResultInterpretationError(ValidationError, ValueError):
    """A bounded reference result cannot be interpreted safely."""

    def __init__(self, message: str, *, reason_code: str) -> None:
        self.reason_code = reason_code
        super().__init__(message)


class CurveAlignmentError(ReferenceResultInterpretationError):
    """The observed and simulated curves have no declared comparable domain."""


class ResponseExtractionStatus(StrEnum):
    EXTRACTED = "extracted"
    NOT_EVALUATED = "not_evaluated"


class NumericalHealthStatus(StrEnum):
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    NOT_EVALUATED = "not_evaluated"


class ValidationVerdict(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    NOT_EVALUATED = "not_evaluated"


class HoldoutIndependenceStatus(StrEnum):
    NOT_APPLICABLE_MANUAL_IR = "not_applicable_manual_ir"
    INDEPENDENT_SELECTION = "independent_selection"
    OVERLAPS_CALIBRATION_SELECTION = "overlaps_calibration_selection"


@dataclass(frozen=True, slots=True)
class ReferenceResponsePoint:
    """One explicit SI engineering stress--strain point."""

    engineering_strain: float
    engineering_stress_pa: float

    def __post_init__(self) -> None:
        for name, value in (
            ("engineering_strain", self.engineering_strain),
            ("engineering_stress_pa", self.engineering_stress_pa),
        ):
            if isinstance(value, bool) or not math.isfinite(value) or value < 0.0:
                raise ReferenceResultInterpretationError(
                    f"{name} must be a finite non-negative SI value",
                    reason_code="native_result_invalid",
                )

    def canonical(self) -> dict[str, float]:
        return {
            "engineering_strain": self.engineering_strain,
            "engineering_stress_pa": self.engineering_stress_pa,
        }


@dataclass(frozen=True, slots=True)
class ReferenceNativeResponse:
    solver_termination: SolverTerminationStatus
    points: tuple[ReferenceResponsePoint, ...]

    def __post_init__(self) -> None:
        if not 2 <= len(self.points) <= MAX_REFERENCE_RESPONSE_POINTS:
            raise ReferenceResultInterpretationError(
                "native result must contain 2..10000 response points",
                reason_code="native_result_invalid",
            )


@dataclass(frozen=True, slots=True)
class NumericalHealthAssessment:
    status: NumericalHealthStatus
    expected_point_count: int
    observed_point_count: int | None
    output_complete: bool
    finite_values: bool
    strictly_increasing_strain: bool
    reason_code: str | None

    def __post_init__(self) -> None:
        if self.expected_point_count < 2:
            raise ValidationConflict("numerical health requires at least two expected points")
        if self.observed_point_count is not None and self.observed_point_count < 0:
            raise ValidationConflict("numerical health observed point count cannot be negative")
        if self.status is NumericalHealthStatus.HEALTHY:
            if (
                not self.output_complete
                or not self.finite_values
                or not self.strictly_increasing_strain
                or self.reason_code is not None
            ):
                raise ValidationConflict("healthy numerical report must have complete valid output")
        elif not self.reason_code:
            raise ValidationConflict("non-healthy numerical report requires a reason code")

    def canonical(self) -> dict[str, object]:
        return {
            "status": self.status.value,
            "expected_point_count": self.expected_point_count,
            "observed_point_count": self.observed_point_count,
            "output_complete": self.output_complete,
            "finite_values": self.finite_values,
            "strictly_increasing_strain": self.strictly_increasing_strain,
            "reason_code": self.reason_code,
        }


@dataclass(frozen=True, slots=True)
class ReferenceComparisonPoint:
    engineering_strain: float
    observed_engineering_stress_pa: float
    simulated_engineering_stress_pa: float
    residual_engineering_stress_pa: float

    def __post_init__(self) -> None:
        for name, value in (
            ("engineering_strain", self.engineering_strain),
            ("observed_engineering_stress_pa", self.observed_engineering_stress_pa),
            ("simulated_engineering_stress_pa", self.simulated_engineering_stress_pa),
            ("residual_engineering_stress_pa", self.residual_engineering_stress_pa),
        ):
            if isinstance(value, bool) or not math.isfinite(value):
                raise ValidationConflict(f"{name} must be finite")

    def canonical(self) -> dict[str, float]:
        return {
            "engineering_strain": self.engineering_strain,
            "observed_engineering_stress_pa": self.observed_engineering_stress_pa,
            "simulated_engineering_stress_pa": self.simulated_engineering_stress_pa,
            "residual_engineering_stress_pa": self.residual_engineering_stress_pa,
        }


@dataclass(frozen=True, slots=True)
class ReferenceMetricAssessment:
    root_mean_squared_error_pa: float
    relative_root_mean_squared_error: float
    normalization_stress_scale_pa: float
    comparison_points: tuple[ReferenceComparisonPoint, ...]

    def __post_init__(self) -> None:
        if not self.comparison_points:
            raise ValidationConflict("reference metrics require at least one aligned point")
        for name, value in (
            ("root_mean_squared_error_pa", self.root_mean_squared_error_pa),
            ("relative_root_mean_squared_error", self.relative_root_mean_squared_error),
            ("normalization_stress_scale_pa", self.normalization_stress_scale_pa),
        ):
            if not math.isfinite(value) or value < 0.0:
                raise ValidationConflict(f"{name} must be finite and non-negative")
        if self.normalization_stress_scale_pa <= 0.0:
            raise ValidationConflict("normalization_stress_scale_pa must be positive")


@dataclass(frozen=True, slots=True)
class ReferenceNormalizedResponseContent:
    validation_run_id: UUID
    validation_result_manifest_id: UUID
    response_extraction_id: UUID
    source_native_result: ValidationArtifactReference
    points: tuple[ReferenceResponsePoint, ...]

    def __post_init__(self) -> None:
        _nonzero("validation_run_id", self.validation_run_id)
        _nonzero("validation_result_manifest_id", self.validation_result_manifest_id)
        _nonzero("response_extraction_id", self.response_extraction_id)
        if not 2 <= len(self.points) <= MAX_REFERENCE_RESPONSE_POINTS:
            raise ValidationConflict("normalized response must contain 2..10000 points")

    def canonical(self) -> dict[str, object]:
        return {
            "schema_id": REFERENCE_NORMALIZED_RESPONSE_SCHEMA_ID,
            "schema_version": REFERENCE_SCHEMA_VERSION,
            "non_production": True,
            "validation_run_id": str(self.validation_run_id),
            "validation_result_manifest_id": str(self.validation_result_manifest_id),
            "response_extraction_id": str(self.response_extraction_id),
            "source_native_result": self.source_native_result.canonical(),
            "channels": {
                "engineering_strain": {"unit": "1", "quantity": "engineering_strain"},
                "engineering_stress_pa": {"unit": "Pa", "quantity": "engineering_stress"},
            },
            "points": [point.canonical() for point in self.points],
        }


@dataclass(frozen=True, slots=True)
class ReferenceNumericalHealthReportContent:
    validation_run_id: UUID
    validation_result_manifest_id: UUID
    response_extraction_id: UUID
    solver_termination: SolverTerminationStatus
    native_result_state: str
    assessment: NumericalHealthAssessment

    def __post_init__(self) -> None:
        _nonzero("validation_run_id", self.validation_run_id)
        _nonzero("validation_result_manifest_id", self.validation_result_manifest_id)
        _nonzero("response_extraction_id", self.response_extraction_id)
        if self.native_result_state not in {"available", "not_available"}:
            raise ValidationConflict("numerical health report native result state is invalid")

    def canonical(self) -> dict[str, object]:
        return {
            "schema_id": REFERENCE_NUMERICAL_HEALTH_REPORT_SCHEMA_ID,
            "schema_version": REFERENCE_SCHEMA_VERSION,
            "non_production": True,
            "validation_run_id": str(self.validation_run_id),
            "validation_result_manifest_id": str(self.validation_result_manifest_id),
            "response_extraction_id": str(self.response_extraction_id),
            "solver_termination": self.solver_termination.value,
            "native_result_state": self.native_result_state,
            "assessment": self.assessment.canonical(),
        }


@dataclass(frozen=True, slots=True)
class ReferenceValidationResultContent:
    validation_run_id: UUID
    validation_result_manifest_id: UUID
    response_extraction_id: UUID
    numerical_health_report_id: UUID
    experimental_selection_id: UUID
    experimental_selection_revision_id: UUID
    normalized_response: ValidationArtifactReference | None
    numerical_health_report: ValidationArtifactReference
    metric_profile_id: str
    threshold_profile_id: str
    alignment_profile_id: str
    relative_rmse_threshold: float
    experimental_point_count: int
    simulated_point_count: int | None
    metrics: ReferenceMetricAssessment | None
    holdout_independence: HoldoutIndependenceStatus
    verdict: ValidationVerdict
    reason_code: str | None

    def __post_init__(self) -> None:
        for name in (
            "validation_run_id",
            "validation_result_manifest_id",
            "response_extraction_id",
            "numerical_health_report_id",
            "experimental_selection_id",
            "experimental_selection_revision_id",
        ):
            _nonzero(name, getattr(self, name))
        if self.metric_profile_id != "urn:cmp:validation:reference-relative-rmse:1.0.0":
            raise ValidationConflict("unsupported reference metric profile")
        if self.threshold_profile_id != REFERENCE_THRESHOLD_PROFILE_ID:
            raise ValidationConflict("unsupported reference threshold profile")
        if self.alignment_profile_id != REFERENCE_ALIGNMENT_PROFILE_ID:
            raise ValidationConflict("unsupported reference alignment profile")
        if not math.isclose(
            self.relative_rmse_threshold,
            REFERENCE_RELATIVE_RMSE_THRESHOLD,
            rel_tol=0.0,
            abs_tol=1e-15,
        ):
            raise ValidationConflict("reference relative RMSE threshold is fixed")
        if self.experimental_point_count < 2:
            raise ValidationConflict("experimental response must contain at least two points")
        if self.simulated_point_count is not None and self.simulated_point_count < 2:
            raise ValidationConflict("simulated response must contain at least two points")
        if self.metrics is not None and self.simulated_point_count is None:
            raise ValidationConflict("metrics require a normalized simulated response")
        if self.verdict in {ValidationVerdict.PASSED, ValidationVerdict.FAILED}:
            if self.metrics is None or self.reason_code is not None:
                raise ValidationConflict("evaluated verdict requires metrics and no reason code")
            if (
                self.holdout_independence
                is HoldoutIndependenceStatus.OVERLAPS_CALIBRATION_SELECTION
            ):
                raise ValidationConflict(
                    "overlapping fit and holdout selections cannot receive a verdict"
                )
            expected = (
                ValidationVerdict.PASSED
                if self.metrics.relative_root_mean_squared_error <= self.relative_rmse_threshold
                else ValidationVerdict.FAILED
            )
            if self.verdict is not expected:
                raise ValidationConflict("reference verdict does not match the declared threshold")
        elif not self.reason_code:
            raise ValidationConflict("not_evaluated verdict requires an explicit reason code")

    def canonical(self) -> dict[str, object]:
        return {
            "schema_id": REFERENCE_VALIDATION_RESULT_SCHEMA_ID,
            "schema_version": REFERENCE_SCHEMA_VERSION,
            "non_production": True,
            "validation_run_id": str(self.validation_run_id),
            "validation_result_manifest_id": str(self.validation_result_manifest_id),
            "response_extraction_id": str(self.response_extraction_id),
            "numerical_health_report_id": str(self.numerical_health_report_id),
            "experimental_selection": {
                "id": str(self.experimental_selection_id),
                "revision_id": str(self.experimental_selection_revision_id),
            },
            "normalized_response": (
                self.normalized_response.canonical() if self.normalized_response else None
            ),
            "numerical_health_report": self.numerical_health_report.canonical(),
            "metric_profile_id": self.metric_profile_id,
            "threshold_profile_id": self.threshold_profile_id,
            "alignment_profile_id": self.alignment_profile_id,
            "relative_rmse_threshold": self.relative_rmse_threshold,
            "experimental_point_count": self.experimental_point_count,
            "simulated_point_count": self.simulated_point_count,
            "metrics": (
                {
                    "root_mean_squared_error_pa": self.metrics.root_mean_squared_error_pa,
                    "relative_root_mean_squared_error": (
                        self.metrics.relative_root_mean_squared_error
                    ),
                    "normalization_stress_scale_pa": self.metrics.normalization_stress_scale_pa,
                    "comparison_points": [
                        point.canonical() for point in self.metrics.comparison_points
                    ],
                }
                if self.metrics is not None
                else None
            ),
            "holdout_independence": self.holdout_independence.value,
            "verdict": self.verdict.value,
            "reason_code": self.reason_code,
        }


def normalized_response_bytes(value: ReferenceNormalizedResponseContent) -> bytes:
    return canonical_json_bytes(value.canonical())


def numerical_health_report_bytes(value: ReferenceNumericalHealthReportContent) -> bytes:
    return canonical_json_bytes(value.canonical())


def validation_result_bytes(value: ReferenceValidationResultContent) -> bytes:
    return canonical_json_bytes(value.canonical())


def validation_result_sha256(value: ReferenceValidationResultContent) -> str:
    return content_sha256(value.canonical())


def extract_reference_native_response(
    value: bytes,
    *,
    template: ReferenceVirtualSpecimenTemplateContent,
) -> ReferenceNativeResponse:
    """Parse the one declared native result envelope into typed SI response points.

    Channel names encode canonical units.  An optional unit declaration is accepted only when it
    explicitly confirms those units; a contradictory declaration is a non-evaluable unit mismatch.
    """

    if not 1 <= len(value) <= 1_000_000:
        raise ReferenceResultInterpretationError(
            "native result must contain between 1 and 1000000 bytes",
            reason_code="native_result_invalid",
        )
    try:
        document = json.loads(value)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ReferenceResultInterpretationError(
            "native result must be UTF-8 JSON",
            reason_code="native_result_invalid",
        ) from error
    if not isinstance(document, dict):
        raise ReferenceResultInterpretationError(
            "native result must be an object", reason_code="native_result_invalid"
        )
    if (
        document.get("schema_id") != REFERENCE_NATIVE_RESULT_SCHEMA_ID
        or document.get("schema_version") != REFERENCE_SCHEMA_VERSION
        or document.get("non_production") is not True
    ):
        raise ReferenceResultInterpretationError(
            "native result schema is not the supported reference contract",
            reason_code="native_result_invalid",
        )
    target = document.get("target")
    if not isinstance(target, dict) or (
        target.get("solver"),
        target.get("version"),
        target.get("unit_system"),
    ) != (template.target_solver, template.target_version, template.target_unit_system):
        raise ReferenceResultInterpretationError(
            "native result target does not match the pinned Template",
            reason_code="native_result_invalid",
        )
    units = document.get("channel_units")
    if units is not None:
        if not isinstance(units, dict) or units != {
            "engineering_strain": "1",
            "engineering_stress_pa": "Pa",
        }:
            raise ReferenceResultInterpretationError(
                "native result channel units do not match canonical SI semantics",
                reason_code="native_unit_mismatch",
            )
    raw_termination = document.get("solver_termination")
    try:
        termination = SolverTerminationStatus(str(raw_termination))
    except ValueError as error:
        raise ReferenceResultInterpretationError(
            "native result termination status is invalid",
            reason_code="native_result_invalid",
        ) from error
    if termination is SolverTerminationStatus.NOT_AVAILABLE:
        raise ReferenceResultInterpretationError(
            "supplied native result cannot use not_available termination",
            reason_code="native_result_invalid",
        )
    raw_points = document.get("points")
    if (
        not isinstance(raw_points, list)
        or not 2 <= len(raw_points) <= MAX_REFERENCE_RESPONSE_POINTS
    ):
        raise ReferenceResultInterpretationError(
            "native result points must contain between 2 and 10000 entries",
            reason_code="native_result_invalid",
        )
    points: list[ReferenceResponsePoint] = []
    for raw_point in raw_points:
        if not isinstance(raw_point, dict):
            raise ReferenceResultInterpretationError(
                "native result points must be objects", reason_code="native_result_invalid"
            )
        strain = raw_point.get("engineering_strain")
        stress = raw_point.get("engineering_stress_pa")
        if (
            isinstance(strain, bool)
            or isinstance(stress, bool)
            or not isinstance(strain, (int, float))
            or not isinstance(stress, (int, float))
        ):
            raise ReferenceResultInterpretationError(
                "native result points require engineering strain and stress in Pa",
                reason_code="native_result_invalid",
            )
        points.append(ReferenceResponsePoint(float(strain), float(stress)))
    return ReferenceNativeResponse(termination, tuple(points))


def assess_reference_numerical_health(
    *,
    template: ReferenceVirtualSpecimenTemplateContent,
    solver_termination: SolverTerminationStatus,
    native_result_state: str,
    response: ReferenceNativeResponse | None,
    extraction_reason_code: str | None,
) -> NumericalHealthAssessment:
    """Inspect termination and response completeness before any experimental metric is used."""

    expected = template.output_sample_count
    if solver_termination is not SolverTerminationStatus.NORMAL:
        return NumericalHealthAssessment(
            NumericalHealthStatus.NOT_EVALUATED,
            expected,
            None,
            False,
            False,
            False,
            f"solver_termination_{solver_termination.value}",
        )
    if native_result_state != "available" or response is None:
        return NumericalHealthAssessment(
            NumericalHealthStatus.UNHEALTHY,
            expected,
            None,
            False,
            False,
            False,
            extraction_reason_code or "native_result_missing",
        )
    points = response.points
    finite = all(
        math.isfinite(point.engineering_strain) and math.isfinite(point.engineering_stress_pa)
        for point in points
    )
    strictly_increasing = all(
        points[index].engineering_strain > points[index - 1].engineering_strain
        for index in range(1, len(points))
    )
    expected_endpoint = template.axial_displacement_end_m / template.gauge_length_m
    endpoint_tolerance = max(1e-12, abs(expected_endpoint) * 1e-9)
    starts_at_zero = math.isclose(points[0].engineering_strain, 0.0, abs_tol=endpoint_tolerance)
    ends_at_expected = math.isclose(
        points[-1].engineering_strain,
        expected_endpoint,
        rel_tol=0.0,
        abs_tol=endpoint_tolerance,
    )
    complete = len(points) == expected and starts_at_zero and ends_at_expected
    if finite and strictly_increasing and complete:
        return NumericalHealthAssessment(
            NumericalHealthStatus.HEALTHY,
            expected,
            len(points),
            True,
            True,
            True,
            None,
        )
    if not finite:
        reason = "non_finite_response"
    elif not strictly_increasing:
        reason = "non_monotonic_response"
    else:
        reason = "truncated_curve"
    return NumericalHealthAssessment(
        NumericalHealthStatus.UNHEALTHY,
        expected,
        len(points),
        complete,
        finite,
        strictly_increasing,
        reason,
    )


def compare_reference_responses(
    *,
    observed: tuple[ReferenceResponsePoint, ...],
    simulated: tuple[ReferenceResponsePoint, ...],
) -> ReferenceMetricAssessment:
    """Apply the declared observed-grid linear interpolation profile without extrapolation."""

    if len(observed) < 2 or len(simulated) < 2:
        raise CurveAlignmentError(
            "both reference curves require at least two points",
            reason_code="curve_alignment_invalid",
        )
    if any(
        observed[index].engineering_strain <= observed[index - 1].engineering_strain
        for index in range(1, len(observed))
    ):
        raise CurveAlignmentError(
            "experimental curve strain must be strictly increasing",
            reason_code="experimental_curve_invalid",
        )
    if any(
        simulated[index].engineering_strain <= simulated[index - 1].engineering_strain
        for index in range(1, len(simulated))
    ):
        raise CurveAlignmentError(
            "simulated curve strain must be strictly increasing",
            reason_code="simulated_curve_invalid",
        )
    low = simulated[0].engineering_strain
    high = simulated[-1].engineering_strain
    tolerance = max(1e-12, max(abs(low), abs(high)) * 1e-9)
    if any(
        point.engineering_strain < low - tolerance or point.engineering_strain > high + tolerance
        for point in observed
    ):
        raise CurveAlignmentError(
            "experimental curve extends outside the simulated domain; extrapolation is forbidden",
            reason_code="curve_domain_mismatch",
        )
    comparisons = tuple(
        _comparison_at_observed_strain(point, simulated, tolerance) for point in observed
    )
    rmse = math.sqrt(
        sum(point.residual_engineering_stress_pa**2 for point in comparisons) / len(comparisons)
    )
    scale = max(
        REFERENCE_STRESS_NORMALIZATION_FLOOR_PA,
        max(abs(point.observed_engineering_stress_pa) for point in comparisons),
    )
    return ReferenceMetricAssessment(rmse, rmse / scale, scale, comparisons)


def parse_reference_validation_result_bytes(value: bytes) -> dict[str, object]:
    """Read a final typed report for a bounded UI preview; never accept arbitrary JSON."""

    try:
        document = json.loads(value)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ReferenceResultInterpretationError(
            "validation result Artifact is not valid UTF-8 JSON",
            reason_code="validation_result_invalid",
        ) from error
    if not isinstance(document, dict) or (
        document.get("schema_id"),
        document.get("schema_version"),
        document.get("non_production"),
    ) != (REFERENCE_VALIDATION_RESULT_SCHEMA_ID, REFERENCE_SCHEMA_VERSION, True):
        raise ReferenceResultInterpretationError(
            "validation result Artifact is not the reference result schema",
            reason_code="validation_result_invalid",
        )
    return document


def parse_reference_normalized_response_bytes(value: bytes) -> tuple[ReferenceResponsePoint, ...]:
    """Read the immutable normalized response Artifact with fixed channel semantics."""

    try:
        document = json.loads(value)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ReferenceResultInterpretationError(
            "normalized response Artifact is not valid UTF-8 JSON",
            reason_code="normalized_response_invalid",
        ) from error
    if not isinstance(document, dict) or (
        document.get("schema_id"),
        document.get("schema_version"),
        document.get("non_production"),
    ) != (REFERENCE_NORMALIZED_RESPONSE_SCHEMA_ID, REFERENCE_SCHEMA_VERSION, True):
        raise ReferenceResultInterpretationError(
            "normalized response Artifact is not the reference response schema",
            reason_code="normalized_response_invalid",
        )
    channels = document.get("channels")
    if channels != {
        "engineering_strain": {"unit": "1", "quantity": "engineering_strain"},
        "engineering_stress_pa": {"unit": "Pa", "quantity": "engineering_stress"},
    }:
        raise ReferenceResultInterpretationError(
            "normalized response Artifact channel semantics are invalid",
            reason_code="normalized_response_invalid",
        )
    raw_points = document.get("points")
    if (
        not isinstance(raw_points, list)
        or not 2 <= len(raw_points) <= MAX_REFERENCE_RESPONSE_POINTS
    ):
        raise ReferenceResultInterpretationError(
            "normalized response Artifact point count is invalid",
            reason_code="normalized_response_invalid",
        )
    points: list[ReferenceResponsePoint] = []
    for raw_point in raw_points:
        if not isinstance(raw_point, dict):
            raise ReferenceResultInterpretationError(
                "normalized response Artifact points must be objects",
                reason_code="normalized_response_invalid",
            )
        strain = raw_point.get("engineering_strain")
        stress = raw_point.get("engineering_stress_pa")
        if (
            isinstance(strain, bool)
            or isinstance(stress, bool)
            or not isinstance(strain, (int, float))
            or not isinstance(stress, (int, float))
        ):
            raise ReferenceResultInterpretationError(
                "normalized response Artifact points are invalid",
                reason_code="normalized_response_invalid",
            )
        points.append(ReferenceResponsePoint(float(strain), float(stress)))
    return tuple(points)


def preview_reference_comparison_points(
    value: ReferenceValidationResultContent,
    maximum_points: int,
) -> tuple[ReferenceComparisonPoint, ...]:
    if not 2 <= maximum_points <= MAX_REFERENCE_RESPONSE_POINTS:
        raise ValidationConflict("validation curve preview limit must be between 2 and 10000")
    if value.metrics is None:
        return ()
    points = value.metrics.comparison_points
    if len(points) <= maximum_points:
        return points
    last = len(points) - 1
    indexes = tuple(round(index * last / (maximum_points - 1)) for index in range(maximum_points))
    return tuple(points[index] for index in indexes)


def preview_reference_response_points(
    points: tuple[ReferenceResponsePoint, ...], maximum_points: int
) -> tuple[ReferenceResponsePoint, ...]:
    if not 2 <= maximum_points <= MAX_REFERENCE_RESPONSE_POINTS:
        raise ValidationConflict("validation curve preview limit must be between 2 and 10000")
    if len(points) <= maximum_points:
        return points
    last = len(points) - 1
    indexes = tuple(round(index * last / (maximum_points - 1)) for index in range(maximum_points))
    return tuple(points[index] for index in indexes)


def _comparison_at_observed_strain(
    observed: ReferenceResponsePoint,
    simulated: tuple[ReferenceResponsePoint, ...],
    tolerance: float,
) -> ReferenceComparisonPoint:
    for point in simulated:
        if math.isclose(
            point.engineering_strain,
            observed.engineering_strain,
            rel_tol=0.0,
            abs_tol=tolerance,
        ):
            prediction = point.engineering_stress_pa
            return ReferenceComparisonPoint(
                observed.engineering_strain,
                observed.engineering_stress_pa,
                prediction,
                prediction - observed.engineering_stress_pa,
            )
    for index in range(1, len(simulated)):
        lower = simulated[index - 1]
        upper = simulated[index]
        if lower.engineering_strain < observed.engineering_strain < upper.engineering_strain:
            fraction = (observed.engineering_strain - lower.engineering_strain) / (
                upper.engineering_strain - lower.engineering_strain
            )
            prediction = lower.engineering_stress_pa + fraction * (
                upper.engineering_stress_pa - lower.engineering_stress_pa
            )
            return ReferenceComparisonPoint(
                observed.engineering_strain,
                observed.engineering_stress_pa,
                prediction,
                prediction - observed.engineering_stress_pa,
            )
    raise CurveAlignmentError(
        "experimental strain was not aligned within the simulated curve domain",
        reason_code="curve_domain_mismatch",
    )


def _nonzero(name: str, value: UUID) -> None:
    if value.int == 0:
        raise ValidationConflict(f"{name} must be non-zero")

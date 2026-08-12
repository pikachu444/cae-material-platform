from __future__ import annotations

from dataclasses import replace
from uuid import UUID

import numpy as np
import pytest
from cmp.modules.statistics.domain.scalar_distribution import (
    DistributionCandidateStatus,
    DistributionFamily,
    ObservationQuality,
    OutlierAssessmentState,
    ScalarDistributionAnalysisOptions,
    ScalarDistributionObservation,
    ScalarDistributionRuntimeManifest,
    fit_scalar_distributions,
    scalar_distribution_artifact_bytes,
)


def _id(value: int) -> UUID:
    return UUID(int=value)


def _observations(
    values: np.ndarray,
    *,
    outlier: int | None = None,
) -> tuple[ScalarDistributionObservation, ...]:
    return tuple(
        ScalarDistributionObservation(
            ordinal=index,
            dataset_id=_id(1000 + index),
            dataset_revision_id=_id(2000 + index),
            test_run_id=_id(3000 + index),
            test_run_revision_id=_id(4000 + index),
            value_pa=float(value),
            outlier_assessment=(
                OutlierAssessmentState.FLAGGED
                if outlier == index
                else OutlierAssessmentState.NOT_ASSESSED
            ),
        )
        for index, value in enumerate(values)
    )


def _manifest() -> ScalarDistributionRuntimeManifest:
    return ScalarDistributionRuntimeManifest(
        algorithm_version="scalar_distribution_fitting_v1",
        schema_ref="urn:cmp:statistics:scalar-distribution-result:1.0.0",
        python_version="3.12.test",
        numpy_version="2.test",
        scipy_version="1.test",
        rng="numpy.random.PCG64",
        source_sha256="1" * 64,
        lock_sha256="2" * 64,
        environment_sha256="3" * 64,
    )


@pytest.mark.parametrize(
    ("family", "values", "expected", "relative_tolerance"),
    (
        (
            DistributionFamily.NORMAL,
            np.random.Generator(np.random.PCG64(101)).normal(520e6, 35e6, 30),
            (520e6, 35e6),
            (0.03, 0.20),
        ),
        (
            DistributionFamily.LOGNORMAL,
            np.random.Generator(np.random.PCG64(202)).lognormal(np.log(480e6), 0.12, 30),
            (0.12, 480e6),
            (0.25, 0.05),
        ),
        (
            DistributionFamily.WEIBULL,
            560e6 * np.random.Generator(np.random.PCG64(303)).weibull(8.0, 30),
            (8.0, 560e6),
            (0.35, 0.08),
        ),
    ),
)
def test_known_synthetic_distribution_parameter_recovery(
    family: DistributionFamily,
    values: np.ndarray,
    expected: tuple[float, float],
    relative_tolerance: tuple[float, float],
) -> None:
    result = fit_scalar_distributions(
        _observations(values),
        ScalarDistributionAnalysisOptions(seed=451),
        manifest=_manifest(),
    )

    candidate = next(item for item in result.candidates if item.family is family)
    assert candidate.status is DistributionCandidateStatus.SUCCEEDED
    assert candidate.parameters[0].value == pytest.approx(expected[0], rel=relative_tolerance[0])
    assert candidate.parameters[1].value == pytest.approx(expected[1], rel=relative_tolerance[1])
    assert candidate.bootstrap_success_count + candidate.bootstrap_failure_count == 999
    assert candidate.bootstrap_p_value is not None


def test_candidate_eligibility_is_explicit_for_small_constant_support_and_missing() -> None:
    options = ScalarDistributionAnalysisOptions(seed=9)

    small = fit_scalar_distributions(
        _observations(np.asarray([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0])),
        options,
        manifest=_manifest(),
    )
    assert {item.status for item in small.candidates} == {DistributionCandidateStatus.NOT_ELIGIBLE}
    assert all(item.reason_codes == ("insufficient_sample_n_lt_8",) for item in small.candidates)

    constant = fit_scalar_distributions(
        _observations(np.full(8, 500e6)), options, manifest=_manifest()
    )
    assert all(item.reason_codes == ("constant_sample",) for item in constant.candidates)

    support = fit_scalar_distributions(
        _observations(np.asarray([-2.0, -1.0, 0.0, 1.0, 2.0, 3.0, 4.0, 5.0])),
        options,
        manifest=_manifest(),
    )
    assert support.candidates[0].status is DistributionCandidateStatus.SUCCEEDED
    assert all(
        item.reason_codes == ("support_requires_positive",) for item in support.candidates[1:]
    )

    missing_values = list(_observations(np.arange(1.0, 9.0)))
    original = missing_values[3]
    missing_values[3] = ScalarDistributionObservation(
        ordinal=original.ordinal,
        dataset_id=original.dataset_id,
        dataset_revision_id=original.dataset_revision_id,
        test_run_id=original.test_run_id,
        test_run_revision_id=original.test_run_revision_id,
        value_pa=None,
        quality=ObservationQuality.MISSING,
    )
    missing = fit_scalar_distributions(tuple(missing_values), options, manifest=_manifest())
    assert all(
        item.reason_codes == ("unsupported_observation_quality:missing",)
        for item in missing.candidates
    )


@pytest.mark.parametrize("non_finite", (float("nan"), float("inf"), float("-inf")))
def test_non_finite_observation_is_canonical_null_and_explicitly_not_eligible(
    non_finite: float,
) -> None:
    observations = list(_observations(np.arange(1.0, 9.0)))
    observations[3] = replace(
        observations[3],
        value_pa=non_finite,
        quality=ObservationQuality.NON_FINITE,
    )
    options = ScalarDistributionAnalysisOptions(seed=19)

    result = fit_scalar_distributions(
        tuple(observations),
        options,
        manifest=_manifest(),
    )

    assert result.observations[3].value_pa is None
    assert all(
        item.status is DistributionCandidateStatus.NOT_ELIGIBLE
        for item in result.candidates
    )
    assert all(
        item.reason_codes == ("unsupported_observation_quality:non_finite",)
        for item in result.candidates
    )
    artifact = scalar_distribution_artifact_bytes(
        statistical_run_id=_id(10),
        statistical_result_id=_id(11),
        statistical_result_revision_id=_id(12),
        plan_id=_id(13),
        plan_revision_id=_id(14),
        selection_id=_id(15),
        selection_revision_id=_id(16),
        options=options,
        unit_applications=(),
        computation=result,
    )
    assert b'"quality":"non_finite"' in artifact
    assert b'"value_pa":null' in artifact
    assert b'"unsupported_quality_value":"canonical_null_with_quality_v1"' in artifact
    assert b"NaN" not in artifact and b"Infinity" not in artifact


def test_extreme_values_and_outlier_assessment_never_silently_drop_a_candidate() -> None:
    values = np.geomspace(1e-240, 1e240, 20)
    result = fit_scalar_distributions(
        _observations(values, outlier=5),
        ScalarDistributionAnalysisOptions(seed=83),
        manifest=_manifest(),
    )

    assert tuple(item.family for item in result.candidates) == (
        DistributionFamily.NORMAL,
        DistributionFamily.LOGNORMAL,
        DistributionFamily.WEIBULL,
    )
    assert all(
        item.status is DistributionCandidateStatus.NOT_ELIGIBLE
        and item.reason_codes == ("extreme_dynamic_range_exceeds_float64_ratio",)
        for item in result.candidates
    )
    assert all(
        "flagged_outlier_assessments_retained_no_automatic_exclusion" in item.warnings
        for item in result.candidates
    )
    assert len(result.observations) == len(values)
    assert result.recommended_families == ()


def test_replay_preserves_candidate_values_digests_and_canonical_artifact_checksum() -> None:
    observations = _observations(np.random.Generator(np.random.PCG64(999)).normal(610e6, 28e6, 20))
    options = ScalarDistributionAnalysisOptions(seed=712)
    first = fit_scalar_distributions(observations, options, manifest=_manifest())
    second = fit_scalar_distributions(observations, options, manifest=_manifest())

    assert first == second
    common = {
        "plan_id": _id(10),
        "plan_revision_id": _id(11),
        "selection_id": _id(12),
        "selection_revision_id": _id(13),
        "options": options,
        "unit_applications": (),
        "computation": first,
    }
    first_bytes = scalar_distribution_artifact_bytes(
        statistical_run_id=_id(20),
        statistical_result_id=_id(21),
        statistical_result_revision_id=_id(22),
        **common,
    )
    replay_bytes = scalar_distribution_artifact_bytes(
        statistical_run_id=_id(30),
        statistical_result_id=_id(31),
        statistical_result_revision_id=_id(32),
        **common,
    )
    assert first_bytes == replay_bytes
    assert b'"numpy_version":"2.test"' in first_bytes
    assert b'"bootstrap_samples":999' in first_bytes

from __future__ import annotations

import json
from uuid import UUID

import pytest
from cmp.modules.validation.domain.reference_result_interpretation import (
    REFERENCE_ALIGNMENT_PROFILE_ID,
    REFERENCE_RELATIVE_RMSE_THRESHOLD,
    REFERENCE_THRESHOLD_PROFILE_ID,
    CurveAlignmentError,
    HoldoutIndependenceStatus,
    NumericalHealthStatus,
    ReferenceNormalizedResponseContent,
    ReferenceResponsePoint,
    ReferenceResultInterpretationError,
    ReferenceValidationResultContent,
    ValidationVerdict,
    assess_reference_numerical_health,
    compare_reference_responses,
    extract_reference_native_response,
    normalized_response_bytes,
    parse_reference_normalized_response_bytes,
    validation_result_bytes,
    validation_result_sha256,
)
from cmp.modules.validation.domain.reference_virtual_specimen import (
    REFERENCE_METRIC_PROFILE_ID,
    ReferenceVirtualSpecimenTemplateContent,
    SolverTerminationStatus,
    ValidationArtifactReference,
    ValidationConflict,
    reference_mock_native_result_bytes,
)

RUN = UUID("28000000-0000-4000-8000-000000000001")
MANIFEST = UUID("28000000-0000-4000-8000-000000000002")
EXTRACTION = UUID("28000000-0000-4000-8000-000000000003")
HEALTH = UUID("28000000-0000-4000-8000-000000000004")
SELECTION = UUID("28000000-0000-4000-8000-000000000005")
SELECTION_REVISION = UUID("28000000-0000-4000-8000-000000000006")
NATIVE = UUID("28000000-0000-4000-8000-000000000007")
RESPONSE = UUID("28000000-0000-4000-8000-000000000008")
HEALTH_REPORT = UUID("28000000-0000-4000-8000-000000000009")


def _template(*, samples: int = 3) -> ReferenceVirtualSpecimenTemplateContent:
    return ReferenceVirtualSpecimenTemplateContent(
        template_label="Reference result interpretation",
        gauge_length_m=0.05,
        cross_section_area_m2=1.0e-5,
        axial_element_count=10,
        axial_displacement_end_m=0.001,
        output_sample_count=samples,
    )


def _artifact(value: UUID, digest: str) -> ValidationArtifactReference:
    return ValidationArtifactReference(value, digest)


def test_reference_result_extracts_si_response_and_compares_on_explicit_observed_grid() -> None:
    template = _template()
    native = extract_reference_native_response(
        reference_mock_native_result_bytes(template=template, youngs_modulus_pa=210_000_000_000.0),
        template=template,
    )
    health = assess_reference_numerical_health(
        template=template,
        solver_termination=SolverTerminationStatus.NORMAL,
        native_result_state="available",
        response=native,
        extraction_reason_code=None,
    )
    observed = (
        ReferenceResponsePoint(0.0, 0.0),
        ReferenceResponsePoint(0.01, 2_100_000_000.0),
        ReferenceResponsePoint(0.02, 4_200_000_000.0),
    )
    metrics = compare_reference_responses(observed=observed, simulated=native.points)

    assert health.status is NumericalHealthStatus.HEALTHY
    assert metrics.root_mean_squared_error_pa == 0.0
    assert metrics.relative_root_mean_squared_error == 0.0
    assert metrics.comparison_points[1].simulated_engineering_stress_pa == 2_100_000_000.0

    response_content = ReferenceNormalizedResponseContent(
        validation_run_id=RUN,
        validation_result_manifest_id=MANIFEST,
        response_extraction_id=EXTRACTION,
        source_native_result=_artifact(NATIVE, "a" * 64),
        points=native.points,
    )
    assert (
        parse_reference_normalized_response_bytes(normalized_response_bytes(response_content))
        == native.points
    )
    result = ReferenceValidationResultContent(
        validation_run_id=RUN,
        validation_result_manifest_id=MANIFEST,
        response_extraction_id=EXTRACTION,
        numerical_health_report_id=HEALTH,
        experimental_selection_id=SELECTION,
        experimental_selection_revision_id=SELECTION_REVISION,
        normalized_response=_artifact(RESPONSE, "b" * 64),
        numerical_health_report=_artifact(HEALTH_REPORT, "c" * 64),
        metric_profile_id=REFERENCE_METRIC_PROFILE_ID,
        threshold_profile_id=REFERENCE_THRESHOLD_PROFILE_ID,
        alignment_profile_id=REFERENCE_ALIGNMENT_PROFILE_ID,
        relative_rmse_threshold=REFERENCE_RELATIVE_RMSE_THRESHOLD,
        experimental_point_count=len(observed),
        simulated_point_count=len(native.points),
        metrics=metrics,
        holdout_independence=HoldoutIndependenceStatus.INDEPENDENT_SELECTION,
        verdict=ValidationVerdict.PASSED,
        reason_code=None,
    )
    assert validation_result_sha256(result) == validation_result_sha256(result)
    assert validation_result_bytes(result) == validation_result_bytes(result)


def test_abnormal_termination_and_truncated_output_are_never_healthy() -> None:
    template = _template()
    abnormal = assess_reference_numerical_health(
        template=template,
        solver_termination=SolverTerminationStatus.ABNORMAL,
        native_result_state="not_available",
        response=None,
        extraction_reason_code=None,
    )
    truncated_document = json.loads(
        reference_mock_native_result_bytes(template=template, youngs_modulus_pa=210_000_000_000.0)
    )
    truncated_document["points"] = truncated_document["points"][:-1]
    truncated = extract_reference_native_response(
        json.dumps(truncated_document).encode("utf-8"), template=template
    )
    truncated_health = assess_reference_numerical_health(
        template=template,
        solver_termination=SolverTerminationStatus.NORMAL,
        native_result_state="available",
        response=truncated,
        extraction_reason_code=None,
    )

    assert abnormal.status is NumericalHealthStatus.NOT_EVALUATED
    assert abnormal.reason_code == "solver_termination_abnormal"
    assert truncated_health.status is NumericalHealthStatus.UNHEALTHY
    assert truncated_health.reason_code == "truncated_curve"


def test_unit_mismatch_and_alignment_domain_mismatch_are_explicitly_rejected() -> None:
    template = _template()
    document = json.loads(
        reference_mock_native_result_bytes(template=template, youngs_modulus_pa=210_000_000_000.0)
    )
    document["channel_units"]["engineering_stress_pa"] = "MPa"
    with pytest.raises(ReferenceResultInterpretationError, match="units") as mismatch:
        extract_reference_native_response(json.dumps(document).encode("utf-8"), template=template)
    assert mismatch.value.reason_code == "native_unit_mismatch"

    with pytest.raises(CurveAlignmentError, match="extrapolation") as alignment:
        compare_reference_responses(
            observed=(
                ReferenceResponsePoint(0.0, 0.0),
                ReferenceResponsePoint(0.03, 1.0),
            ),
            simulated=(
                ReferenceResponsePoint(0.0, 0.0),
                ReferenceResponsePoint(0.02, 1.0),
            ),
        )
    assert alignment.value.reason_code == "curve_domain_mismatch"


def test_fit_holdout_overlap_cannot_be_persisted_as_a_passing_reference_verdict() -> None:
    metrics = compare_reference_responses(
        observed=(ReferenceResponsePoint(0.0, 0.0), ReferenceResponsePoint(0.02, 1.0)),
        simulated=(ReferenceResponsePoint(0.0, 0.0), ReferenceResponsePoint(0.02, 1.0)),
    )

    with pytest.raises(ValidationConflict, match="overlapping fit and holdout"):
        ReferenceValidationResultContent(
            validation_run_id=RUN,
            validation_result_manifest_id=MANIFEST,
            response_extraction_id=EXTRACTION,
            numerical_health_report_id=HEALTH,
            experimental_selection_id=SELECTION,
            experimental_selection_revision_id=SELECTION_REVISION,
            normalized_response=_artifact(RESPONSE, "b" * 64),
            numerical_health_report=_artifact(HEALTH_REPORT, "c" * 64),
            metric_profile_id=REFERENCE_METRIC_PROFILE_ID,
            threshold_profile_id=REFERENCE_THRESHOLD_PROFILE_ID,
            alignment_profile_id=REFERENCE_ALIGNMENT_PROFILE_ID,
            relative_rmse_threshold=REFERENCE_RELATIVE_RMSE_THRESHOLD,
            experimental_point_count=2,
            simulated_point_count=2,
            metrics=metrics,
            holdout_independence=HoldoutIndependenceStatus.OVERLAPS_CALIBRATION_SELECTION,
            verdict=ValidationVerdict.PASSED,
            reason_code=None,
        )

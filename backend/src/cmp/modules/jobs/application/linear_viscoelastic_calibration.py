"""Generic Job bridge for the isolated linear-viscoelastic calibrator."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from cmp.modules.jobs.domain.jobs import ImmutableJobSpec, ResourcePolicy

LINEAR_VISCOELASTIC_CALIBRATION_JOB_TYPE = "modeling.linear_viscoelastic_calibration"
LINEAR_VISCOELASTIC_CALIBRATOR_ID = "cmp.linear_viscoelastic.calibrator"
LINEAR_VISCOELASTIC_CALIBRATOR_VERSION = "1.0.2"
LINEAR_VISCOELASTIC_CONFIG_SCHEMA = "urn:cmp:plugin:linear-viscoelastic-calibrator:config:1.0.0"
LINEAR_VISCOELASTIC_RESULT_SCHEMA = "urn:cmp:modeling:linear-viscoelastic-calibration-result:1.0.0"
LINEAR_VISCOELASTIC_RESIDUAL_SCHEMA = (
    "urn:cmp:modeling:linear-viscoelastic-calibration-response-residuals:1.0.0"
)
LINEAR_VISCOELASTIC_HISTORY_SCHEMA = (
    "urn:cmp:modeling:linear-viscoelastic-calibration-objective-history:1.0.0"
)
LINEAR_VISCOELASTIC_MAX_TOTAL_OUTPUT_BYTES = 436_207_616
LINEAR_VISCOELASTIC_OUTPUT_CAPS = {
    "calibration.run-result": 33_554_432,
    "response-residuals": 268_435_456,
    "objective-history": 134_217_728,
}


def linear_viscoelastic_resource_policy() -> ResourcePolicy:
    return ResourcePolicy(cpu_millis=2_000, memory_mb=4_096, gpu_count=0, max_attempts=3)


def build_linear_viscoelastic_job_spec(
    *,
    job_id: UUID,
    attempt_id: UUID,
    run_id: UUID,
    plan_revision_id: UUID,
    plan_sha256: str,
    plan_artifact_id: UUID,
    canonical_test_data_revision_id: UUID,
    canonical_test_data_artifact_id: UUID,
    canonical_test_data_sha256: str,
    normalized_test_data_revision_id: UUID,
    normalized_test_data_artifact_id: UUID,
    normalized_test_data_sha256: str,
    package_sha256: str,
    recommendation_policy: str,
    deadline: datetime,
    traceparent: str,
    processing_output_revision_id: UUID | None = None,
    processing_metadata_artifact_id: UUID | None = None,
    processing_metadata_sha256: str | None = None,
    processing_result_artifact_id: UUID | None = None,
    processing_result_sha256: str | None = None,
) -> tuple[ImmutableJobSpec, ResourcePolicy]:
    """Create the exact T-18 Job Spec; callers persist it before enqueueing."""

    if deadline.tzinfo is None or deadline.utcoffset() is None:
        raise ValueError("deadline must be timezone-aware")
    if deadline <= datetime.now(UTC):
        # A worker may receive a precomputed historical deadline in a replay test.  The
        # generic Job contract still stores it exactly; no local clock substitution occurs.
        pass
    processing_pins = (
        processing_output_revision_id,
        processing_metadata_artifact_id,
        processing_metadata_sha256,
        processing_result_artifact_id,
        processing_result_sha256,
    )
    if any(value is not None for value in processing_pins) != all(
        value is not None for value in processing_pins
    ):
        raise ValueError("processed calibration Job inputs must be provided together")
    inputs: list[dict[str, Any]] = [
        {
            "role": "calibration.plan",
            "entity_revision_id": str(plan_revision_id),
            "artifact_id": str(plan_artifact_id),
            "sha256": plan_sha256,
            "media_type": "application/json",
            "access": "read_exact_artifact",
        },
        {
            "role": "test-data.canonical",
            "entity_revision_id": str(canonical_test_data_revision_id),
            "artifact_id": str(canonical_test_data_artifact_id),
            "sha256": canonical_test_data_sha256,
            "media_type": "application/vnd.cmp.test-data+json",
            "access": "read_exact_artifact",
        },
        {
            "role": "test-data.normalized",
            "entity_revision_id": str(normalized_test_data_revision_id),
            "artifact_id": str(normalized_test_data_artifact_id),
            "sha256": normalized_test_data_sha256,
            "media_type": "application/vnd.apache.parquet",
            "access": "read_exact_artifact",
        },
    ]
    if processing_output_revision_id is not None:
        assert processing_metadata_artifact_id is not None
        assert processing_metadata_sha256 is not None
        assert processing_result_artifact_id is not None
        assert processing_result_sha256 is not None
        inputs.extend(
            (
                {
                    "role": "processing-output.metadata",
                    "entity_revision_id": str(processing_output_revision_id),
                    "artifact_id": str(processing_metadata_artifact_id),
                    "sha256": processing_metadata_sha256,
                    "media_type": "application/vnd.cmp.processing-output+json",
                    "access": "read_exact_artifact",
                },
                {
                    "role": "processing-output.result",
                    "entity_revision_id": str(processing_output_revision_id),
                    "artifact_id": str(processing_result_artifact_id),
                    "sha256": processing_result_sha256,
                    "media_type": "application/vnd.apache.parquet",
                    "access": "read_exact_artifact",
                },
            )
        )
    document: dict[str, Any] = {
        "job_spec_version": "1.0",
        "job_id": str(job_id),
        "attempt_id": str(attempt_id),
        "extension": {
            "type": "calibrator",
            "plugin_id": LINEAR_VISCOELASTIC_CALIBRATOR_ID,
            "plugin_version": LINEAR_VISCOELASTIC_CALIBRATOR_VERSION,
            "package_digest": f"sha256:{package_sha256}",
        },
        "operation": "execute_plan",
        "inputs": inputs,
        "config": {
            "schema_version": "1.0.0",
            "run_id": str(run_id),
            "plan_revision_id": str(plan_revision_id),
            "plan_sha256": plan_sha256,
            "recommendation_policy": recommendation_policy,
            "seed_status": "not_applicable",
        },
        "config_schema_ref": LINEAR_VISCOELASTIC_CONFIG_SCHEMA,
        "expected_outputs": [
            {"role": "calibration.run-result", "schema_ref": LINEAR_VISCOELASTIC_RESULT_SCHEMA},
            {"role": "response-residuals", "schema_ref": LINEAR_VISCOELASTIC_RESIDUAL_SCHEMA},
            {"role": "objective-history", "schema_ref": LINEAR_VISCOELASTIC_HISTORY_SCHEMA},
        ],
        "execution": {
            "seed": 0,
            "deadline": deadline.astimezone(UTC).isoformat().replace("+00:00", "Z"),
            "traceparent": traceparent,
            "locale": "C",
            "timezone": "UTC",
        },
    }
    return ImmutableJobSpec.from_validated_document(document), linear_viscoelastic_resource_policy()


def linear_viscoelastic_deadline(submitted_at: datetime) -> datetime:
    if submitted_at.tzinfo is None or submitted_at.utcoffset() is None:
        raise ValueError("submitted_at must be timezone-aware")
    return submitted_at + timedelta(seconds=3_600)


def map_worker_failure(*, outcome: str, diagnostic_code: str | None = None) -> str:
    """Map generic runner outcomes to stable calibration-specific failure codes."""

    if outcome == "cancelled":
        return "CALCULATION_CANCELLED"
    if outcome == "timed_out":
        return "CALCULATION_TIMED_OUT"
    if diagnostic_code in {"isolation_unavailable", "runner_unavailable"}:
        return "EXECUTION_ISOLATION_UNAVAILABLE"
    if diagnostic_code in {"package_integrity", "package_digest_mismatch"}:
        return "EXECUTION_PACKAGE_INTEGRITY_FAILED"
    if diagnostic_code in {"invalid_request", "request_invalid"}:
        return "EXECUTION_REQUEST_INVALID"
    if diagnostic_code in {"invalid_output", "result_invalid"}:
        return "EXECUTION_RESULT_INVALID"
    if outcome == "failed" and diagnostic_code in {"calculation_failed", "plugin_domain"}:
        return "CALCULATION_FAILED"
    return "EXECUTION_INTERNAL_ERROR"

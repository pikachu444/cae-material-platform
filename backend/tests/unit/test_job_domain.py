from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from cmp.modules.jobs.adapters.contracts.jsonschema import (
    JsonSchemaJobContractValidator,
)
from cmp.modules.jobs.domain.jobs import (
    FailureCategory,
    ImmutableJobSpec,
    InvalidJobSpec,
    InvalidJobTransition,
    JobState,
    ResourcePolicy,
    RetryDisposition,
    assert_job_transition,
    retry_disposition,
)

PROJECT_ROOT = Path(__file__).parents[3]


def _spec() -> dict[str, Any]:
    document = cast(
        dict[str, Any],
        json.loads(
        (PROJECT_ROOT / "contracts/examples/positive/job-spec.json").read_text(
            encoding="utf-8"
        )
        ),
    )
    document["job_id"] = str(uuid4())
    document["attempt_id"] = str(uuid4())
    document["execution"]["deadline"] = "2030-01-01T00:00:00Z"
    return document


def test_job_state_machine_has_only_explicit_retry_escape_from_terminal_failure() -> None:
    assert_job_transition(JobState.QUEUED, JobState.CLAIMED)
    assert_job_transition(JobState.RUNNING, JobState.SUCCEEDED)
    assert_job_transition(JobState.PLANNED, JobState.CANCELLED)
    assert_job_transition(JobState.NEEDS_INPUT, JobState.CANCELLED)
    assert_job_transition(JobState.FAILED, JobState.QUEUED)
    assert_job_transition(JobState.TIMED_OUT, JobState.QUEUED)

    with pytest.raises(InvalidJobTransition):
        assert_job_transition(JobState.SUCCEEDED, JobState.QUEUED)
    with pytest.raises(InvalidJobTransition):
        assert_job_transition(JobState.CANCELLED, JobState.RUNNING)
    with pytest.raises(InvalidJobTransition):
        assert_job_transition(JobState.QUEUED, JobState.SUCCEEDED)


def test_retry_taxonomy_is_conservative_for_immutable_invalid_input() -> None:
    automatic = {
        FailureCategory.TRANSIENT_INFRASTRUCTURE,
        FailureCategory.RESOURCE_EXHAUSTED,
        FailureCategory.EXTERNAL_UNAVAILABLE,
        FailureCategory.INTERNAL_ERROR,
    }
    assert all(
        retry_disposition(category) is RetryDisposition.AUTOMATIC
        for category in automatic
    )
    assert (
        retry_disposition(FailureCategory.DOMAIN_INVALID)
        is RetryDisposition.NEVER
    )
    assert (
        retry_disposition(FailureCategory.OUTPUT_INVALID)
        is RetryDisposition.MANUAL_ONLY
    )
    assert (
        retry_disposition(FailureCategory.DEADLINE_EXCEEDED)
        is RetryDisposition.MANUAL_ONLY
    )


def test_attempt_job_specs_are_distinct_immutable_canonical_documents() -> None:
    original_document = _spec()
    original = ImmutableJobSpec.from_validated_document(original_document)
    next_attempt_id = UUID("81000000-0000-4000-8000-000000000001")

    replacement = original.for_attempt(next_attempt_id)
    original_document["operation"] = "mutated-after-construction"

    assert original.document()["operation"] == "run"
    assert original.attempt_id != replacement.attempt_id == next_attempt_id
    assert original.job_id == replacement.job_id
    assert original.digest != replacement.digest
    assert original.document()["attempt_id"] != replacement.document()["attempt_id"]


def test_runtime_validator_uses_the_exact_versioned_job_spec_contract() -> None:
    validator = JsonSchemaJobContractValidator()
    document = _spec()
    validator.validate_job_spec(document)

    document["job_spec_version"] = "latest"
    with pytest.raises(InvalidJobSpec, match=r"1\.0"):
        validator.validate_job_spec(document)


@pytest.mark.parametrize(
    "values",
    [
        (0, 1024, 0, 1),
        (1000, 0, 0, 1),
        (1000, 1024, -1, 1),
        (1000, 1024, 0, 0),
    ],
)
def test_resource_policy_rejects_non_positive_or_negative_limits(
    values: tuple[int, int, int, int],
) -> None:
    with pytest.raises(ValueError):
        ResourcePolicy(*values)


def test_job_spec_rejects_moving_alias_zero_id_and_naive_deadline() -> None:
    moving = _spec()
    moving["attempt_id"] = "latest"
    with pytest.raises(InvalidJobSpec, match="UUID"):
        ImmutableJobSpec.from_validated_document(moving)

    zero = _spec()
    zero["job_id"] = str(UUID(int=0))
    with pytest.raises(InvalidJobSpec, match="non-zero"):
        ImmutableJobSpec.from_validated_document(zero)

    naive = _spec()
    naive["execution"]["deadline"] = datetime(2030, 1, 1).isoformat()
    with pytest.raises(InvalidJobSpec, match="timezone-aware"):
        ImmutableJobSpec.from_validated_document(naive)

    aware = _spec()
    aware["execution"]["deadline"] = datetime(2030, 1, 1, tzinfo=UTC).isoformat()
    assert ImmutableJobSpec.from_validated_document(aware).deadline.tzinfo is not None

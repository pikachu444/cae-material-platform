import asyncio
import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from cmp.apps.worker import (
    DurableJobWorker,
    EmptyWorker,
    HandlerResult,
    WorkerExecution,
)
from cmp.modules.identity_access.domain.authorization import DataClassification
from cmp.modules.jobs.application.jobs import (
    ClaimedAttempt,
    FinalizeAttempt,
    FinalizeResult,
    HeartbeatAttempt,
    HeartbeatResult,
)
from cmp.modules.jobs.domain.jobs import (
    AttemptRecord,
    AttemptState,
    ImmutableJobSpec,
    JobRecord,
    JobState,
    ResourcePolicy,
    RetryKind,
)
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider

PROJECT_ROOT = Path(__file__).parents[3]
NOW = datetime(2026, 7, 11, 8, 0, tzinfo=UTC)
ORG = UUID("82000000-0000-4000-8000-000000000001")
PROJECT = UUID("82000000-0000-4000-8000-000000000002")
ACTOR = UUID("82000000-0000-4000-8000-000000000003")
JOB = UUID("82000000-0000-4000-8000-000000000004")
ATTEMPT = UUID("82000000-0000-4000-8000-000000000005")
RUNNER = UUID("82000000-0000-4000-8000-000000000006")
LEASE = UUID("82000000-0000-4000-8000-000000000007")
MANIFEST = UUID("82000000-0000-4000-8000-000000000008")
DIGEST = "0" * 64


def _claimed() -> ClaimedAttempt:
    document = json.loads(
        (PROJECT_ROOT / "contracts/examples/positive/job-spec.json").read_text(
            encoding="utf-8"
        )
    )
    document["job_id"] = str(JOB)
    document["attempt_id"] = str(ATTEMPT)
    document["execution"]["deadline"] = "2030-01-01T00:00:00Z"
    spec = ImmutableJobSpec.from_validated_document(document)
    job = JobRecord(
        JOB,
        ORG,
        PROJECT,
        DataClassification.INTERNAL,
        "reference.operation",
        JobState.CLAIMED,
        0,
        NOW,
        ACTOR,
        uuid4(),
        f"00-{uuid4().hex}-{uuid4().hex[:16]}-01",
        spec.deadline,
        ResourcePolicy(1000, 1024, 0, 3),
        1,
        ATTEMPT,
        None,
        None,
        None,
        None,
        NOW,
    )
    attempt = AttemptRecord(
        ATTEMPT,
        JOB,
        1,
        AttemptState.CLAIMED,
        RetryKind.INITIAL,
        "initial submission",
        spec,
        RUNNER,
        LEASE,
        NOW + timedelta(seconds=30),
        NOW,
        NOW,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
    )
    return ClaimedAttempt(job, attempt)


class _Queue:
    def __init__(self, *, request_cancel: bool = False) -> None:
        self.claimed = _claimed()
        self.request_cancel = request_cancel
        self.accepted: tuple[str, ...] | None = None
        self.finalized: FinalizeAttempt | None = None
        self.heartbeats = 0

    async def claim(
        self, accepted_job_types: tuple[str, ...]
    ) -> ClaimedAttempt | None:
        self.accepted = accepted_job_types
        return self.claimed

    async def start(self, claimed: ClaimedAttempt) -> ClaimedAttempt:
        running = ClaimedAttempt(
            replace(claimed.job, state=JobState.RUNNING),
            replace(claimed.attempt, state=AttemptState.RUNNING, started_at=NOW),
        )
        self.claimed = running
        return running

    async def heartbeat(self, command: HeartbeatAttempt) -> HeartbeatResult:
        assert command.lease_token == LEASE
        self.heartbeats += 1
        return HeartbeatResult(
            self.claimed.job,
            self.claimed.attempt,
            self.request_cancel,
        )

    async def finalize(self, command: FinalizeAttempt) -> FinalizeResult:
        self.finalized = command
        terminal_job = replace(
            self.claimed.job,
            state=JobState(command.outcome.value),
            result_manifest_id=command.result_manifest_id,
            result_manifest_digest=command.result_manifest_digest,
            failure=command.failure,
        )
        terminal_attempt = replace(
            self.claimed.attempt,
            state=command.outcome,
            ended_at=NOW + timedelta(seconds=1),
            result_manifest_id=command.result_manifest_id,
            result_manifest_digest=command.result_manifest_digest,
            failure=command.failure,
        )
        return FinalizeResult(terminal_job, terminal_attempt, False, False)


def test_empty_worker_runs_one_idle_cycle() -> None:
    result = asyncio.run(EmptyWorker(poll_interval_seconds=0.01).run_once())

    assert result.status == "idle"
    assert result.handlers_registered == 0


def test_empty_worker_rejects_non_positive_interval() -> None:
    with pytest.raises(ValueError, match="must be positive"):
        EmptyWorker(poll_interval_seconds=0)


def test_durable_worker_claims_starts_and_finalizes_generic_handler() -> None:
    queue = _Queue()

    async def handler(_execution: WorkerExecution) -> HandlerResult:
        return HandlerResult(AttemptState.SUCCEEDED, MANIFEST, DIGEST)

    worker = DurableJobWorker(
        queue=queue,
        handlers={"reference.operation": handler},
        poll_interval_seconds=0.01,
    )
    result = asyncio.run(worker.run_once())

    assert result.status == "succeeded"
    assert result.handlers_registered == 1
    assert queue.accepted == ("reference.operation",)
    assert queue.finalized is not None
    assert queue.finalized.result_manifest_id == MANIFEST


def test_durable_worker_continues_the_submission_trace() -> None:
    queue = _Queue()
    observed_trace_ids: list[int] = []

    async def handler(_execution: WorkerExecution) -> HandlerResult:
        observed_trace_ids.append(trace.get_current_span().get_span_context().trace_id)
        return HandlerResult(AttemptState.SUCCEEDED, MANIFEST, DIGEST)

    provider = TracerProvider()
    worker = DurableJobWorker(
        queue=queue,
        handlers={"reference.operation": handler},
        tracer=provider.get_tracer("cmp-test"),
    )

    asyncio.run(worker.run_once())
    provider.shutdown()

    submitted_trace_id = int(queue.claimed.job.trace_id.split("-")[1], 16)
    assert observed_trace_ids == [submitted_trace_id]


def test_durable_worker_heartbeats_and_exposes_cooperative_cancel() -> None:
    queue = _Queue(request_cancel=True)

    async def handler(execution: WorkerExecution) -> HandlerResult:
        cancellation = execution.cancellation_requested
        await asyncio.wait_for(cancellation.wait(), timeout=0.5)
        return HandlerResult(AttemptState.CANCELLED)

    worker = DurableJobWorker(
        queue=queue,
        handlers={"reference.operation": handler},
        heartbeat_interval_seconds=0.01,
        lease_duration=timedelta(seconds=5),
    )
    result = asyncio.run(worker.run_once())

    assert result.status == "cancelled"
    assert queue.heartbeats >= 1
    assert queue.finalized is not None
    assert queue.finalized.outcome is AttemptState.CANCELLED


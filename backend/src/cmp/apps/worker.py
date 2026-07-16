"""Generic durable worker shell over the T-15 Job/Attempt/Lease application port."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from collections.abc import Awaitable, Callable, Mapping, Sequence
from contextlib import nullcontext
from dataclasses import asdict, dataclass
from datetime import timedelta
from typing import Protocol
from uuid import UUID

from opentelemetry.context import Context
from opentelemetry.trace import SpanKind, Tracer
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

from cmp import __version__
from cmp.bootstrap.settings import Settings
from cmp.modules.jobs.application.jobs import (
    ClaimedAttempt,
    FinalizeAttempt,
    FinalizeResult,
    HeartbeatAttempt,
    HeartbeatResult,
)
from cmp.modules.jobs.domain.jobs import AttemptState, Failure, FailureCategory
from cmp.modules.plugins.adapters.worker import PluginAttemptHandler
from cmp.shared.observability import build_telemetry_runtime, configure_structured_logging

LOGGER = logging.getLogger("cmp.worker")


@dataclass(frozen=True, slots=True)
class WorkerCycleResult:
    """Stable process-level result; execution details remain in the durable job resource."""

    status: str = "idle"
    service: str = "cmp-worker"
    version: str = __version__
    handlers_registered: int = 0


@dataclass(frozen=True, slots=True)
class HandlerResult:
    outcome: AttemptState
    result_manifest_id: UUID | None = None
    result_manifest_digest: str | None = None
    failure: Failure | None = None


@dataclass(frozen=True, slots=True)
class WorkerExecution:
    claimed: ClaimedAttempt
    cancellation_requested: asyncio.Event


type JobHandler = Callable[[WorkerExecution], Awaitable[HandlerResult]]


def isolated_plugin_job_handler(executor: PluginAttemptHandler) -> JobHandler:
    """Adapt the T-18 module handler without exposing worker internals to plugins."""

    async def handle(execution: WorkerExecution) -> HandlerResult:
        result = await executor.execute(
            execution.claimed,
            execution.cancellation_requested,
        )
        return HandlerResult(
            outcome=result.outcome,
            result_manifest_id=result.result_manifest_id,
            result_manifest_digest=result.result_manifest_digest,
            failure=result.failure,
        )

    return handle


class JobWorkerQueue(Protocol):
    """Authorized queue adapter; it owns the worker service-principal context."""

    async def claim(
        self, accepted_job_types: tuple[str, ...]
    ) -> ClaimedAttempt | None: ...

    async def start(self, claimed: ClaimedAttempt) -> ClaimedAttempt: ...

    async def heartbeat(self, command: HeartbeatAttempt) -> HeartbeatResult: ...

    async def finalize(self, command: FinalizeAttempt) -> FinalizeResult: ...


class DurableJobWorker:
    """Poll one generic job at a time and maintain its lease while a handler runs."""

    def __init__(
        self,
        *,
        queue: JobWorkerQueue | None = None,
        handlers: Mapping[str, JobHandler] | None = None,
        poll_interval_seconds: float = 1.0,
        heartbeat_interval_seconds: float = 10.0,
        lease_duration: timedelta = timedelta(seconds=30),
        tracer: Tracer | None = None,
    ) -> None:
        if poll_interval_seconds <= 0:
            raise ValueError("poll_interval_seconds must be positive")
        if heartbeat_interval_seconds <= 0:
            raise ValueError("heartbeat_interval_seconds must be positive")
        if lease_duration < timedelta(seconds=5):
            raise ValueError("lease_duration must be at least five seconds")
        if heartbeat_interval_seconds >= lease_duration.total_seconds():
            raise ValueError("heartbeat interval must be shorter than the lease")
        self._queue = queue
        self._handlers = dict(handlers or {})
        self._poll_interval_seconds = poll_interval_seconds
        self._heartbeat_interval_seconds = heartbeat_interval_seconds
        self._lease_duration = lease_duration
        self._tracer = tracer
        self._stop = asyncio.Event()

    async def _heartbeat(
        self,
        claimed: ClaimedAttempt,
        cancellation: asyncio.Event,
    ) -> None:
        if self._queue is None or claimed.attempt.lease_token is None:
            return
        while True:
            await asyncio.sleep(self._heartbeat_interval_seconds)
            result = await self._queue.heartbeat(
                HeartbeatAttempt(
                    attempt_id=claimed.attempt.id,
                    lease_token=claimed.attempt.lease_token,
                    lease_duration=self._lease_duration,
                )
            )
            if result.cancellation_requested:
                cancellation.set()

    async def run_once(self) -> WorkerCycleResult:
        """Claim, execute, heartbeat, and finalize at most one attempt."""

        if self._queue is None or not self._handlers:
            await asyncio.sleep(0)
            return WorkerCycleResult(handlers_registered=len(self._handlers))
        accepted = tuple(sorted(self._handlers))
        claimed = await self._queue.claim(accepted)
        if claimed is None:
            return WorkerCycleResult(handlers_registered=len(self._handlers))
        claimed = await self._queue.start(claimed)
        token = claimed.attempt.lease_token
        if token is None:
            raise RuntimeError("claimed attempt has no lease fencing token")
        cancellation = asyncio.Event()
        if claimed.job.state.value == "cancel_requested":
            cancellation.set()
        parent: Context = TraceContextTextMapPropagator().extract(
            {"traceparent": claimed.job.trace_id}
        )
        span = (
            self._tracer.start_as_current_span(
                "cmp.job.execute",
                context=parent,
                kind=SpanKind.CONSUMER,
                attributes={"job.type": claimed.job.job_type},
            )
            if self._tracer is not None
            else nullcontext()
        )
        with span:
            heartbeat = asyncio.create_task(self._heartbeat(claimed, cancellation))
            try:
                handler = self._handlers[claimed.job.job_type]
                result = await handler(WorkerExecution(claimed, cancellation))
            except Exception:
                LOGGER.exception(
                    "job_handler_failed",
                    extra={
                        "job_id": str(claimed.job.id),
                        "attempt_id": str(claimed.attempt.id),
                        "job_type": claimed.job.job_type,
                        "request_id": str(claimed.job.request_id),
                    },
                )
                result = HandlerResult(
                    AttemptState.FAILED,
                    failure=Failure(
                        FailureCategory.INTERNAL_ERROR,
                        "handler_exception",
                        "The generic worker handler raised an unhandled exception.",
                    ),
                )
            finally:
                heartbeat.cancel()
                try:
                    await heartbeat
                except asyncio.CancelledError:
                    pass
        finalized = await self._queue.finalize(
            FinalizeAttempt(
                attempt_id=claimed.attempt.id,
                lease_token=token,
                outcome=result.outcome,
                result_manifest_id=result.result_manifest_id,
                result_manifest_digest=result.result_manifest_digest,
                failure=result.failure,
            )
        )
        return WorkerCycleResult(
            status=finalized.attempt.state.value,
            handlers_registered=len(self._handlers),
        )

    async def serve(self) -> None:
        LOGGER.info("worker_started", extra={"version": __version__})
        try:
            while not self._stop.is_set():
                await self.run_once()
                try:
                    await asyncio.wait_for(
                        self._stop.wait(), timeout=self._poll_interval_seconds
                    )
                except TimeoutError:
                    continue
        finally:
            LOGGER.info("worker_stopped")

    def stop(self) -> None:
        self._stop.set()


class EmptyWorker(DurableJobWorker):
    """Backward-compatible unconfigured shell used by the deployment smoke test."""

    def __init__(self, poll_interval_seconds: float = 1.0) -> None:
        super().__init__(poll_interval_seconds=poll_interval_seconds)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the CMP durable worker shell.")
    parser.add_argument("--once", action="store_true", help="Run one cycle and exit.")
    parser.add_argument("--json", action="store_true", help="Print the cycle result as JSON.")
    parser.add_argument("--poll-interval", type=float, default=None)
    return parser


async def _run(args: argparse.Namespace) -> int:
    settings = Settings.from_environment()
    interval = args.poll_interval or settings.worker_poll_interval_seconds
    telemetry = build_telemetry_runtime(
        service_name="cmp-worker",
        environment=settings.environment,
        endpoint=settings.otel_exporter_otlp_endpoint,
        export_interval_ms=settings.otel_metric_export_interval_ms,
    )
    # Production composition requires a trusted service principal plus T-10 package/input
    # materializer and result committer. When they are absent, the deployable stays safely
    # idle instead of fabricating credentials or mutable artifact references.
    worker = DurableJobWorker(poll_interval_seconds=interval, tracer=telemetry.tracer)
    if args.once:
        try:
            result = await worker.run_once()
            if args.json:
                print(json.dumps(asdict(result), sort_keys=True))
            else:
                print(f"{result.service}: {result.status} ({result.handlers_registered} handlers)")
            return 0
        finally:
            telemetry.shutdown()

    try:
        await worker.serve()
    except asyncio.CancelledError:
        worker.stop()
        raise
    finally:
        telemetry.shutdown()
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point that is testable without starting a permanent process."""

    configure_structured_logging("cmp-worker")
    args = _parser().parse_args(argv)
    try:
        return asyncio.run(_run(args))
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())

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
from pathlib import Path
from typing import Protocol
from uuid import UUID, uuid4

from opentelemetry.context import Context
from opentelemetry.trace import SpanKind, Tracer
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from sqlalchemy.orm import Session, sessionmaker

from cmp import __version__
from cmp.bootstrap.artifacts import build_artifact_services, build_object_store
from cmp.bootstrap.demo_identity import DEMO_WORKER_RUNNER_ID, DemoIdentity
from cmp.bootstrap.exporting import build_bulk_export_service
from cmp.bootstrap.jobs import build_job_service
from cmp.bootstrap.modeling import build_linear_viscoelastic_calibration_service
from cmp.bootstrap.plugins import build_plugin_registry_service
from cmp.bootstrap.rotating_secret import RotatingTextFile
from cmp.bootstrap.security import (
    IdentityServices,
    build_demo_identity_services,
    build_identity_services,
)
from cmp.bootstrap.settings import Settings
from cmp.modules.exporting.application.bulk_export import BulkExportService
from cmp.modules.identity_access.application.authorization import AuthorizationService
from cmp.modules.identity_access.application.security import SecurityContextService
from cmp.modules.identity_access.domain.authorization import (
    Permission,
)
from cmp.modules.identity_access.domain.security import (
    AuthenticationRequest,
)
from cmp.modules.jobs.adapters.persistence.events import SqlAlchemyOutboxRepository
from cmp.modules.jobs.adapters.signed_connectors import (
    SignedEventEncoder,
    SignedHttpEventTransport,
    SignedObjectStorageEventTransport,
)
from cmp.modules.jobs.application.events import EventTransport, OutboxPublisher
from cmp.modules.jobs.application.jobs import (
    ClaimedAttempt,
    FinalizeAttempt,
    FinalizeResult,
    HeartbeatAttempt,
    HeartbeatResult,
)
from cmp.modules.jobs.domain.jobs import AttemptState, Failure, FailureCategory
from cmp.modules.modeling.adapters.worker.linear_viscoelastic_calibration_worker import (
    LinearViscoelasticCalibrationWorker,
    WorkerCompositionError,
)
from cmp.modules.plugins.adapters.worker import PluginAttemptHandler
from cmp.shared.observability import build_telemetry_runtime, configure_structured_logging
from cmp.tools.release_signing import ExternalCommandSigner

LOGGER = logging.getLogger("cmp.worker")


@dataclass(frozen=True, slots=True)
class WorkerCycleResult:
    """Stable process-level result; execution details remain in the durable job resource."""

    status: str = "idle"
    service: str = "cmp-worker"
    version: str = __version__
    handlers_registered: int = 0
    bulk_export_enabled: bool = False
    event_delivery_enabled: bool = False
    events_published: int = 0


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
type WorkerFinalizeHook = Callable[
    [ClaimedAttempt, HandlerResult, FinalizeResult], Awaitable[None]
]


class WorkerComponent(Protocol):
    """Small lifecycle contract used by the composite worker."""

    async def run_once(self) -> WorkerCycleResult: ...

    def stop(self) -> None: ...


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

    async def claim(self, accepted_job_types: tuple[str, ...]) -> ClaimedAttempt | None: ...

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
        finalize_hook: WorkerFinalizeHook | None = None,
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
        self._finalize_hook = finalize_hook
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
        if self._finalize_hook is not None:
            await self._finalize_hook(claimed, result, finalized)
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
                    await asyncio.wait_for(self._stop.wait(), timeout=self._poll_interval_seconds)
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


class BulkExportQueueWorker:
    """Out-of-process bounded Bundle assembler over the typed durable Export Job queue."""

    def __init__(
        self,
        *,
        service: BulkExportService,
        security: SecurityContextService,
        authorization: AuthorizationService,
        access_token: Callable[[], str],
    ) -> None:
        self._service = service
        self._security = security
        self._authorization = authorization
        self._access_token = access_token

    async def run_once(self) -> WorkerCycleResult:
        request_id = uuid4()
        context = self._security.authenticate(
            AuthenticationRequest(
                self._access_token(),
                request_id,
                f"00-{uuid4().hex}-{uuid4().hex[:16]}-01",
            )
        )
        decision = self._authorization.authorize(context, Permission.EXPORT_EXECUTE)
        result = await self._service.execute_next_external(context, decision)
        return WorkerCycleResult(
            status=result[0].state.value if result is not None else "idle",
            bulk_export_enabled=True,
        )


class OutboxQueueWorker:
    """Authenticate a fresh service token and dispatch one leased outbox batch."""

    def __init__(
        self,
        *,
        publisher: OutboxPublisher,
        security: SecurityContextService,
        authorization: AuthorizationService,
        access_token: Callable[[], str],
    ) -> None:
        self._publisher = publisher
        self._security = security
        self._authorization = authorization
        self._access_token = access_token

    async def run_once(self) -> WorkerCycleResult:
        context = self._security.authenticate(
            AuthenticationRequest(
                self._access_token(),
                uuid4(),
                f"00-{uuid4().hex}-{uuid4().hex[:16]}-01",
            )
        )
        decision = self._authorization.authorize(context, Permission.JOB_EXECUTE)
        result = await asyncio.to_thread(
            self._publisher.publish_batch,
            context,
            decision,
        )
        return WorkerCycleResult(
            status="published" if result.published else "idle",
            event_delivery_enabled=True,
            events_published=result.published,
        )


class CompositeWorker:
    """Poll generic leased handlers first, then the typed external Bundle queue."""

    def __init__(
        self,
        *,
        generic: WorkerComponent,
        bulk_exports: BulkExportQueueWorker | None,
        event_delivery: OutboxQueueWorker | None,
        poll_interval_seconds: float,
    ) -> None:
        self._generic = generic
        self._bulk_exports = bulk_exports
        self._event_delivery = event_delivery
        self._poll_interval_seconds = poll_interval_seconds
        self._stop = asyncio.Event()

    async def run_once(self) -> WorkerCycleResult:
        generic = await self._generic.run_once()
        if generic.status != "idle":
            return WorkerCycleResult(
                status=generic.status,
                handlers_registered=generic.handlers_registered,
                bulk_export_enabled=self._bulk_exports is not None,
                event_delivery_enabled=self._event_delivery is not None,
            )
        if self._bulk_exports is not None:
            bulk = await self._bulk_exports.run_once()
            if bulk.status != "idle":
                return WorkerCycleResult(
                    status=bulk.status,
                    bulk_export_enabled=True,
                    event_delivery_enabled=self._event_delivery is not None,
                )
        if self._event_delivery is not None:
            return await self._event_delivery.run_once()
        return WorkerCycleResult(
            handlers_registered=generic.handlers_registered,
            bulk_export_enabled=self._bulk_exports is not None,
            event_delivery_enabled=False,
        )

    async def serve(self) -> None:
        LOGGER.info("worker_started", extra={"version": __version__})
        try:
            while not self._stop.is_set():
                await self.run_once()
                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=self._poll_interval_seconds)
                except TimeoutError:
                    continue
        finally:
            LOGGER.info("worker_stopped")

    def stop(self) -> None:
        self._stop.set()


def _worker_token(
    settings: Settings,
    demo: DemoIdentity | None,
) -> Callable[[], str] | None:
    token: Callable[[], str] | None = (
        (lambda: demo.issue_worker_access_token()) if demo is not None else None
    )
    if token is None and settings.worker_access_token_file is not None:
        token = RotatingTextFile(Path(settings.worker_access_token_file))
    if token is None and settings.worker_access_token is not None:
        if settings.environment == "production":
            raise ValueError(
                "production workers must rotate identity through CMP_WORKER_ACCESS_TOKEN_FILE"
            )
        fixed = settings.worker_access_token

        def configured_token() -> str:
            return fixed

        token = configured_token
    return token


def _build_event_worker(
    settings: Settings,
    identity: IdentityServices,
    token: Callable[[], str] | None,
) -> OutboxQueueWorker | None:
    kind = settings.event_connector_kind.strip().lower()
    if kind == "none":
        return None
    if (
        token is None
        or identity.security is None
        or identity.authorization is None
        or identity.engine is None
        or identity.rls_context is None
    ):
        raise ValueError("event delivery requires worker identity and PostgreSQL composition")
    required = (
        settings.event_signer_command_json,
        settings.event_signer_trusted_public_key,
        settings.event_signer_expected_key_id,
    )
    if any(value is None for value in required):
        raise ValueError("event delivery requires an external signer command, trust key and key ID")
    try:
        command = json.loads(settings.event_signer_command_json or "")
    except json.JSONDecodeError as error:
        raise ValueError("event signer command must be a JSON string array") from error
    if (
        not isinstance(command, list)
        or not command
        or not all(isinstance(value, str) and value for value in command)
    ):
        raise ValueError("event signer command must be a non-empty JSON string array")
    signer = ExternalCommandSigner(
        tuple(command),
        trusted_public_key=Path(settings.event_signer_trusted_public_key or "").read_bytes(),
        expected_key_id=settings.event_signer_expected_key_id or "",
        timeout_seconds=settings.event_signer_timeout_seconds,
    )
    transport: EventTransport
    if kind in {"rest", "webhook"}:
        endpoint = settings.event_connector_endpoint
        if endpoint is None:
            raise ValueError("HTTP event connector requires CMP_EVENT_CONNECTOR_ENDPOINT")
        if settings.environment == "production" and settings.event_connector_allow_loopback_http:
            raise ValueError("production event connectors cannot enable loopback HTTP")
        bearer = (
            RotatingTextFile(Path(settings.event_connector_bearer_token_file))
            if settings.event_connector_bearer_token_file is not None
            else None
        )
        transport = SignedHttpEventTransport(
            endpoint,
            SignedEventEncoder(signer, kind=kind, audience=endpoint),
            bearer_token=bearer,
            timeout_seconds=settings.event_signer_timeout_seconds,
            allow_loopback_http=settings.event_connector_allow_loopback_http,
        )
    elif kind == "object_storage":
        store = build_object_store(settings)
        if store is None:
            raise ValueError("object-storage event connector requires an object store")
        transport = SignedObjectStorageEventTransport(
            store,
            SignedEventEncoder(
                signer,
                kind=kind,
                audience="urn:cmp:connector:object-storage",
            ),
        )
    else:
        raise ValueError("CMP_EVENT_CONNECTOR_KIND must be none, rest, webhook or object_storage")
    publisher = OutboxPublisher(
        repository=SqlAlchemyOutboxRepository(
            session_factory=sessionmaker(
                identity.engine,
                class_=Session,
                expire_on_commit=False,
            ),
            rls_context=identity.rls_context,
        ),
        transport=transport,
    )
    return OutboxQueueWorker(
        publisher=publisher,
        security=identity.security,
        authorization=identity.authorization,
        access_token=token,
    )


def _build_workers(
    settings: Settings,
    *,
    tracer: Tracer | None = None,
) -> tuple[
    BulkExportQueueWorker | None,
    OutboxQueueWorker | None,
    IdentityServices,
    WorkerComponent | None,
]:
    demo = DemoIdentity.from_settings(settings)
    identity = (
        build_demo_identity_services(settings, demo.idp)
        if demo is not None
        else build_identity_services(settings)
    )
    identity_values = (
        identity.security,
        identity.authorization,
        identity.engine,
        identity.rls_context,
    )
    if all(value is None for value in identity_values):
        return None, None, identity, None
    if any(value is None for value in identity_values):
        raise WorkerCompositionError(
            "worker identity composition is partial; security, authorization, database and RLS "
            "must be configured together"
        )
    assert (
        identity.security is not None
        and identity.authorization is not None
        and identity.engine is not None
        and identity.rls_context is not None
    )
    token = _worker_token(settings, demo)
    if token is None:
        raise WorkerCompositionError(
            "configured worker identity requires CMP_WORKER_ACCESS_TOKEN_FILE or an explicit "
            "non-production CMP_WORKER_ACCESS_TOKEN"
        )
    if settings.environment.strip().lower() == "production":
        raise WorkerCompositionError(
            "the calibration worker is non-production until an attested OCI runner is approved"
        )

    artifact_services = build_artifact_services(identity, settings)
    artifacts = artifact_services.content
    jobs = build_job_service(identity)
    plugins = build_plugin_registry_service(identity)
    calibration = build_linear_viscoelastic_calibration_service(
        identity,
        jobs=jobs,
        artifacts=artifacts,
        plugins=plugins,
    )
    if artifacts is None or jobs is None or plugins is None or calibration is None:
        raise WorkerCompositionError(
            "configured worker requires PostgreSQL Job, Plugin Registry, Artifact and "
            "linear-viscoelastic calibration services"
        )

    generic: WorkerComponent = LinearViscoelasticCalibrationWorker(
        jobs=jobs,
        artifacts=artifacts,
        plugins=plugins,
        calibration=calibration,
        security=identity.security,
        authorization=identity.authorization,
        access_token=token,
        runner_id=DEMO_WORKER_RUNNER_ID if demo is not None else None,
        tracer=tracer,
    )
    event_delivery = _build_event_worker(settings, identity, token)
    service = build_bulk_export_service(identity, artifacts, settings)
    if service is None:
        return None, event_delivery, identity, generic
    return (
        BulkExportQueueWorker(
            service=service,
            security=identity.security,
            authorization=identity.authorization,
            access_token=token,
        ),
        event_delivery,
        identity,
        generic,
    )


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
    # Calibration uses the explicitly non-production local subprocess sandbox until an
    # attested OCI runner is approved.  With no identity/database configuration the worker
    # remains the deployment smoke-test idle shell; partial composition fails closed.
    bulk_exports, event_delivery, identity, configured_generic = _build_workers(
        settings,
        tracer=telemetry.tracer,
    )
    generic = configured_generic or DurableJobWorker(
        poll_interval_seconds=interval,
        tracer=telemetry.tracer,
    )
    worker = CompositeWorker(
        generic=generic,
        bulk_exports=bulk_exports,
        event_delivery=event_delivery,
        poll_interval_seconds=interval,
    )
    if args.once:
        try:
            result = await worker.run_once()
            if args.json:
                print(json.dumps(asdict(result), sort_keys=True))
            else:
                print(f"{result.service}: {result.status} ({result.handlers_registered} handlers)")
            return 0
        finally:
            if identity.engine is not None:
                identity.engine.dispose()
            telemetry.shutdown()

    try:
        await worker.serve()
    except asyncio.CancelledError:
        worker.stop()
        raise
    finally:
        if identity.engine is not None:
            identity.engine.dispose()
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

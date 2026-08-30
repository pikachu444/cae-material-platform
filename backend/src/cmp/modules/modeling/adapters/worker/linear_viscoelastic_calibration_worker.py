"""Worker composition and reconciliation for the isolated linear-viscoelastic plugin."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping
from datetime import timedelta
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from opentelemetry.trace import Tracer

from cmp.bootstrap.demo_identity import DEMO_WORKER_RUNNER_ID
from cmp.modules.artifacts.application.content import ArtifactService
from cmp.modules.identity_access.application.authorization import AuthorizationService
from cmp.modules.identity_access.application.security import SecurityContextService
from cmp.modules.identity_access.domain.authorization import AuthorizationDecision, Permission
from cmp.modules.identity_access.domain.security import AuthenticationRequest, SecurityContext
from cmp.modules.jobs.application.jobs import ClaimedAttempt, FinalizeResult, JobService
from cmp.modules.jobs.application.linear_viscoelastic_calibration import (
    LINEAR_VISCOELASTIC_CALIBRATOR_ID,
)
from cmp.modules.jobs.application.worker import AuthorizedJobWorkerQueue
from cmp.modules.jobs.domain.jobs import AttemptState
from cmp.modules.modeling.adapters.worker.linear_viscoelastic_calibration_materializer import (
    LinearViscoelasticCalibrationMaterializer,
)
from cmp.modules.modeling.adapters.worker.linear_viscoelastic_calibration_results import (
    LinearViscoelasticCalibrationResultCommitter,
)
from cmp.modules.modeling.application.linear_viscoelastic_calibration import (
    LinearViscoelasticCalibrationService,
)
from cmp.modules.plugins.application.execution import PluginExecutionService
from cmp.modules.plugins.application.planning import RegistryPluginExecutionPlanner
from cmp.modules.plugins.application.registry import PluginRegistryService
from cmp.modules.plugins.application.worker import (
    PLUGIN_JOB_TYPE,
    JsonSchemaRunnerContractValidator,
    PluginAttemptHandler,
    SubprocessPluginRunner,
)
from cmp.modules.plugins.domain.execution import SandboxPolicy

if TYPE_CHECKING:
    from cmp.apps.worker import HandlerResult, WorkerCycleResult


class WorkerCompositionError(ValueError):
    """The configured worker cannot form its complete isolated execution boundary."""


def _calibration_failure_identity(
    claimed: ClaimedAttempt,
) -> tuple[UUID, str] | None:
    """Extract only immutable calibration identity from a claimed plugin Job."""

    if claimed.job.job_type != PLUGIN_JOB_TYPE:
        return None
    document = claimed.attempt.spec.document()
    if not isinstance(document, Mapping) or document.get("operation") != "execute_plan":
        return None
    extension = document.get("extension")
    config = document.get("config")
    if not isinstance(extension, Mapping) or not isinstance(config, Mapping):
        return None
    if extension.get("plugin_id") != LINEAR_VISCOELASTIC_CALIBRATOR_ID:
        return None
    package_ref = extension.get("package_digest")
    run_value = config.get("run_id")
    if not isinstance(package_ref, str) or not package_ref.startswith("sha256:"):
        return None
    package_sha256 = package_ref.removeprefix("sha256:")
    if len(package_sha256) != 64 or any(
        char not in "0123456789abcdef" for char in package_sha256
    ):
        return None
    try:
        run_id = UUID(str(run_value))
    except (TypeError, ValueError):
        return None
    if run_id.int == 0:
        return None
    return run_id, package_sha256


def _calibration_diagnostic_code(code: str | None) -> str | None:
    """Translate sanitized generic handler codes to calibration failure codes."""

    mapping: dict[str, str] = {
        "plugin_isolation_unavailable": "isolation_unavailable",
        "plugin_package_integrity_failed": "package_integrity",
        "plugin_execution_request_invalid": "invalid_request",
        "plugin_result_invalid": "invalid_output",
        "plugin_reported_failure": "plugin_domain",
    }
    return mapping.get(code) if code is not None else None


class LinearViscoelasticCalibrationWorker:
    """Refresh authentication and compose one isolated calibrator cycle at a time."""

    def __init__(
        self,
        *,
        jobs: JobService,
        artifacts: ArtifactService,
        plugins: PluginRegistryService,
        calibration: LinearViscoelasticCalibrationService,
        security: SecurityContextService,
        authorization: AuthorizationService,
        access_token: Callable[[], str],
        runner_id: UUID | None = None,
        heartbeat_interval_seconds: float = 10.0,
        lease_duration: timedelta = timedelta(seconds=30),
        tracer: Tracer | None = None,
    ) -> None:
        if runner_id is not None and runner_id.int == 0:
            raise ValueError("runner_id must be non-zero")
        self._jobs = jobs
        self._artifacts = artifacts
        self._plugins = plugins
        self._calibration = calibration
        self._security = security
        self._authorization = authorization
        self._access_token = access_token
        self._runner_id = runner_id or DEMO_WORKER_RUNNER_ID
        self._heartbeat_interval_seconds = heartbeat_interval_seconds
        self._lease_duration = lease_duration
        self._tracer = tracer
        self._bound_scope: tuple[UUID, UUID] | None = None
        self._stop = asyncio.Event()

    @staticmethod
    def _check_decision(
        context: SecurityContext,
        decision: AuthorizationDecision,
        permission: Permission,
    ) -> None:
        if (
            decision.permission is not permission
            or decision.principal_id != context.principal.id
            or decision.organization_id != context.organization_id
            or decision.project_id != context.project_id
            or decision.request_id != context.request_id
            or decision.trace_id != context.trace_id
        ):
            raise WorkerCompositionError(
                f"worker authorization decision does not match {permission.value} context"
            )

    def _authorize_cycle(
        self,
    ) -> tuple[
        SecurityContext,
        AuthorizationDecision,
        AuthorizationDecision,
        AuthorizationDecision,
        AuthorizationDecision,
    ]:
        request_id = uuid4()
        context = self._security.authenticate(
            AuthenticationRequest(
                self._access_token(),
                request_id,
                f"00-{uuid4().hex}-{uuid4().hex[:16]}-01",
            )
        )
        scope = (context.organization_id, context.project_id)
        if self._bound_scope is None:
            self._bound_scope = scope
        elif self._bound_scope != scope:
            raise WorkerCompositionError(
                "rotating worker credentials must remain bound to one organization/project"
            )

        job_decision = self._authorization.authorize(context, Permission.JOB_EXECUTE)
        plugin_decision = self._authorization.authorize(context, Permission.PLUGIN_READ)
        artifact_read_decision = self._authorization.authorize(context, Permission.ARTIFACT_READ)
        artifact_write_decision = self._authorization.authorize(
            context, Permission.ARTIFACT_WRITE
        )
        self._check_decision(context, job_decision, Permission.JOB_EXECUTE)
        self._check_decision(context, plugin_decision, Permission.PLUGIN_READ)
        self._check_decision(context, artifact_read_decision, Permission.ARTIFACT_READ)
        self._check_decision(context, artifact_write_decision, Permission.ARTIFACT_WRITE)
        required_dependencies = {
            Permission.ARTIFACT_READ.value,
            Permission.ARTIFACT_WRITE.value,
            Permission.CALIBRATION_EXECUTE.value,
        }
        if not required_dependencies.issubset(set(job_decision.database_permissions)):
            missing = ", ".join(
                sorted(required_dependencies - set(job_decision.database_permissions))
            )
            raise WorkerCompositionError(
                "JOB_EXECUTE decision is missing worker transaction dependencies: " + missing
            )
        return (
            context,
            job_decision,
            plugin_decision,
            artifact_read_decision,
            artifact_write_decision,
        )

    async def _reconcile_after_finalize(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        claimed: ClaimedAttempt,
        result: HandlerResult,
        finalized: FinalizeResult,
    ) -> None:
        if result.outcome is AttemptState.SUCCEEDED:
            return
        identity = _calibration_failure_identity(claimed)
        if identity is None:
            return
        run_id, package_sha256 = identity
        failure = result.failure
        await asyncio.to_thread(
            self._calibration.record_execution_failure,
            context,
            decision,
            run_id=run_id,
            job_id=claimed.job.id,
            attempt_id=claimed.attempt.id,
            job_attempt_no=claimed.attempt.attempt_no,
            outcome=result.outcome.value,
            diagnostic_code=(
                _calibration_diagnostic_code(failure.code if failure is not None else None)
            ),
            detail=failure.detail if failure is not None else None,
            package_sha256=package_sha256,
            submitted_at=claimed.job.submitted_at,
            deadline_at=claimed.job.deadline,
            retry_scheduled=finalized.retry_scheduled,
        )

    async def run_once(self) -> WorkerCycleResult:
        """Authenticate, compose, execute, finalize, and clean one attempt."""

        # Importing these generic lifecycle types lazily avoids coupling the app entry point
        # back into this model adapter during bootstrap.
        from cmp.apps.worker import (
            DurableJobWorker,
            WorkerCycleResult,
            isolated_plugin_job_handler,
        )

        if self._stop.is_set():
            return WorkerCycleResult(handlers_registered=1)
        (
            context,
            job_decision,
            plugin_decision,
            artifact_read_decision,
            _artifact_write_decision,
        ) = self._authorize_cycle()
        materializer = LinearViscoelasticCalibrationMaterializer(
            context=context,
            decision=artifact_read_decision,
            artifact_service=self._artifacts,
        )
        try:
            queue = AuthorizedJobWorkerQueue(
                service=self._jobs,
                context=context,
                decision=job_decision,
                runner_id=self._runner_id,
                lease_duration=self._lease_duration,
            )
            planner = RegistryPluginExecutionPlanner(
                registry=self._plugins,
                context=context,
                plugin_read_decision=plugin_decision,
                materializer=materializer,
                sandbox=SandboxPolicy.development_subprocess(),
                production=False,
            )
            execution = PluginExecutionService(
                runner=SubprocessPluginRunner(),
                validator=JsonSchemaRunnerContractValidator(),
            )
            committer = LinearViscoelasticCalibrationResultCommitter(
                context=context,
                decision=job_decision,
                artifact_service=self._artifacts,
                calibration_service=self._calibration,
            )
            executor = PluginAttemptHandler(
                planner=planner,
                execution=execution,
                committer=committer,
            )

            async def reconcile(
                claimed: ClaimedAttempt,
                result: HandlerResult,
                finalized: FinalizeResult,
            ) -> None:
                await self._reconcile_after_finalize(
                    context, job_decision, claimed, result, finalized
                )

            worker = DurableJobWorker(
                queue=queue,
                handlers={PLUGIN_JOB_TYPE: isolated_plugin_job_handler(executor)},
                heartbeat_interval_seconds=self._heartbeat_interval_seconds,
                lease_duration=self._lease_duration,
                tracer=self._tracer,
                finalize_hook=reconcile,
            )
            result = await worker.run_once()
            return WorkerCycleResult(
                status=result.status,
                handlers_registered=result.handlers_registered,
            )
        finally:
            materializer.cleanup_all()

    def stop(self) -> None:
        self._stop.set()

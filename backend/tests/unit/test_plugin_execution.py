from __future__ import annotations

import asyncio
import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from cmp.apps.worker import HandlerResult, WorkerExecution, isolated_plugin_job_handler
from cmp.modules.identity_access.application.authorization import database_permissions_for
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
    Permission,
    Role,
)
from cmp.modules.identity_access.domain.security import (
    Principal,
    PrincipalType,
    SecurityContext,
)
from cmp.modules.jobs.application.jobs import ClaimedAttempt
from cmp.modules.jobs.domain.jobs import (
    AttemptRecord,
    AttemptState,
    FailureCategory,
    ImmutableJobSpec,
    JobRecord,
    JobState,
    ResourcePolicy,
    RetryKind,
)
from cmp.modules.plugins.adapters.runner.oci import (
    OciExecutionPlan,
    OciPluginRunner,
    OciRuntimeCapabilities,
)
from cmp.modules.plugins.adapters.worker import (
    CommittedResultManifest,
    PluginAttemptHandler,
)
from cmp.modules.plugins.application.execution import (
    ExecutePlugin,
    PluginExecutionService,
)
from cmp.modules.plugins.application.planning import (
    ExecutionMaterialization,
    PluginExecutionMaterializer,
    PluginExecutionPlanner,
    RegistryPluginExecutionPlanner,
)
from cmp.modules.plugins.application.registry import PluginRegistryService
from cmp.modules.plugins.domain.execution import (
    AllowedOutput,
    IsolationUnavailable,
    PackageIntegrityError,
    ResultStatus,
    RunnerResponse,
    SandboxPolicy,
    ValidatedPluginResult,
)
from cmp.modules.plugins.domain.registry import (
    ActivationRecord,
    ArtifactReference,
    ImmutablePluginManifest,
    PackageRecord,
    PackageState,
    SchemaDocument,
    SchemaRole,
)
from cmp.shared.domain.revisions import content_sha256

PROJECT_ROOT = Path(__file__).parents[3]
NOW = datetime(2026, 7, 12, 8, 0, tzinfo=UTC)
ORG = UUID("86000000-0000-4000-8000-000000000001")
PROJECT = UUID("86000000-0000-4000-8000-000000000002")
ACTOR = UUID("86000000-0000-4000-8000-000000000003")
JOB = UUID("86000000-0000-4000-8000-000000000004")
ATTEMPT = UUID("86000000-0000-4000-8000-000000000005")
PACKAGE = UUID("86000000-0000-4000-8000-000000000006")
TRACE = "00-00000000000000000000000000000086-0000000000000086-01"


def _job_document() -> dict[str, Any]:
    value = json.loads(
        (PROJECT_ROOT / "contracts/examples/positive/job-spec.json").read_text(
            encoding="utf-8"
        )
    )
    assert isinstance(value, dict)
    value["job_id"] = str(JOB)
    value["attempt_id"] = str(ATTEMPT)
    value["execution"]["deadline"] = "2030-01-01T00:00:00Z"
    return cast(dict[str, Any], value)


def _claimed(*, project_id: UUID = PROJECT) -> ClaimedAttempt:
    spec = ImmutableJobSpec.from_validated_document(_job_document())
    job = JobRecord(
        id=JOB,
        organization_id=ORG,
        project_id=project_id,
        classification=DataClassification.INTERNAL,
        job_type="plugin.run",
        state=JobState.RUNNING,
        priority=0,
        submitted_at=NOW,
        submitted_by=ACTOR,
        deadline=spec.deadline,
        resource_policy=ResourcePolicy(1000, 256, 0, 1),
        attempt_count=1,
        current_attempt_id=ATTEMPT,
        result_manifest_id=None,
        result_manifest_digest=None,
        failure=None,
        cancel_requested_at=None,
        updated_at=NOW,
    )
    attempt = AttemptRecord(
        id=ATTEMPT,
        job_id=JOB,
        attempt_no=1,
        state=AttemptState.RUNNING,
        retry_kind=RetryKind.INITIAL,
        retry_reason="initial submission",
        spec=spec,
        runner_id=uuid4(),
        lease_token=uuid4(),
        lease_expires_at=NOW + timedelta(seconds=30),
        heartbeat_at=NOW,
        claimed_at=NOW,
        started_at=NOW,
        ended_at=None,
        progress_fraction=None,
        progress_phase=None,
        progress_updated_at=None,
        result_manifest_id=None,
        result_manifest_digest=None,
        failure=None,
    )
    return ClaimedAttempt(job, attempt)


def _package() -> PackageRecord:
    raw = json.loads(
        (PROJECT_ROOT / "contracts/examples/positive/plugin-manifest.json").read_text(
            encoding="utf-8"
        )
    )
    manifest = ImmutablePluginManifest.from_validated_document(raw)
    schema_document = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "urn:cmp:reference:processor-config:1.0.0",
        "type": "object",
    }
    schema = SchemaDocument.from_validated_document(
        schema_id=str(schema_document["$id"]),
        extension_ordinal=1,
        role=SchemaRole.CONFIG,
        document=schema_document,
        expected_sha256=content_sha256(schema_document),
    )
    return PackageRecord(
        id=PACKAGE,
        definition_id=uuid4(),
        organization_id=ORG,
        project_id=PROJECT,
        classification=DataClassification.INTERNAL,
        manifest=manifest,
        package_artifact=ArtifactReference(uuid4(), "0" * 64, 1, "application/zip"),
        signature_artifact=ArtifactReference(
            uuid4(), "1" * 64, 1, "application/vnd.dev.cosign.simplesigning.v1+json"
        ),
        sbom_artifact=ArtifactReference(uuid4(), "2" * 64, 1, "application/spdx+json"),
        schemas=(schema,),
        state=PackageState.ELIGIBLE,
        state_events=(),
        submitted_at=NOW,
        submitted_by=ACTOR,
        submission_request_id=uuid4(),
        submission_trace_id=TRACE,
        activation=ActivationRecord(
            uuid4(), PACKAGE, NOW, ACTOR, "approved", uuid4(), TRACE
        ),
    )


def _context() -> SecurityContext:
    return SecurityContext(
        principal=Principal(ACTOR, PrincipalType.SERVICE, "T-18 runner", True),
        organization_id=ORG,
        project_id=PROJECT,
        issuer="https://test-idp.invalid",
        subject="t18-runner",
        token_id=str(uuid4()),
        groups=(),
        scopes=(),
        request_id=uuid4(),
        trace_id=TRACE,
        authenticated_at=NOW,
    )


def _decision(context: SecurityContext) -> AuthorizationDecision:
    return AuthorizationDecision(
        principal_id=context.principal.id,
        organization_id=context.organization_id,
        project_id=context.project_id,
        permission=Permission.PLUGIN_READ,
        roles=(Role.JOB_RUNNER,),
        database_permissions=database_permissions_for(Permission.PLUGIN_READ),
        max_classification=DataClassification.RESTRICTED,
        allow_export_controlled=False,
        request_id=context.request_id,
        trace_id=context.trace_id,
        decided_at=NOW,
    )


class _Registry:
    def __init__(self, package: PackageRecord) -> None:
        self.package = package
        self.calls = 0

    def get_active(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        *,
        plugin_id: str,
        plugin_version: str,
        package_digest: str,
    ) -> PackageRecord:
        del context, decision
        self.calls += 1
        assert (plugin_id, plugin_version, package_digest) == (
            self.package.manifest.plugin_id,
            self.package.manifest.plugin_version,
            self.package.manifest.package_digest,
        )
        return self.package


class _Materializer:
    def __init__(self, tmp_path: Path) -> None:
        self.tmp_path = tmp_path

    async def materialize(
        self,
        *,
        claimed: ClaimedAttempt,
        package: PackageRecord,
        extension_ordinal: int,
        job_spec: dict[str, Any],
    ) -> ExecutionMaterialization:
        del claimed, package, job_spec
        assert extension_ordinal == 1
        return ExecutionMaterialization(
            archive_path=self.tmp_path / "approved.zip",
            dependency_lock_digest="3" * 64,
            staged_inputs=(),
            allowed_outputs=(
                AllowedOutput(
                    "processed-dataset",
                    "urn:cmp:schema:dataset:1.0.0",
                    ("application/vnd.apache.parquet",),
                    1024,
                ),
            ),
            output_staging_root=self.tmp_path / "output",
        )


def test_registry_planner_resolves_one_active_extension_without_importing_it(
    tmp_path: Path,
) -> None:
    registry = _Registry(_package())
    context = _context()
    planner = RegistryPluginExecutionPlanner(
        registry=cast(PluginRegistryService, registry),
        context=context,
        plugin_read_decision=_decision(context),
        materializer=cast(PluginExecutionMaterializer, _Materializer(tmp_path)),
        sandbox=SandboxPolicy.development_subprocess(),
    )

    command = asyncio.run(planner.prepare(_claimed()))

    assert registry.calls == 1
    assert command.package.entrypoint == "reference.processor:IdentityProcessor"
    assert command.package.config_schema is not None
    assert command.package.config_schema.schema_id == (
        "urn:cmp:reference:processor-config:1.0.0"
    )
    assert command.package.active


def test_registry_planner_rejects_cross_project_claim_before_lookup(
    tmp_path: Path,
) -> None:
    registry = _Registry(_package())
    context = _context()
    planner = RegistryPluginExecutionPlanner(
        registry=cast(PluginRegistryService, registry),
        context=context,
        plugin_read_decision=_decision(context),
        materializer=cast(PluginExecutionMaterializer, _Materializer(tmp_path)),
        sandbox=SandboxPolicy.development_subprocess(),
    )

    with pytest.raises(ValueError, match="tenant"):
        asyncio.run(planner.prepare(_claimed(project_id=uuid4())))
    assert registry.calls == 0


class _StaticPlanner:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error

    async def prepare(self, claimed: ClaimedAttempt) -> ExecutePlugin:
        del claimed
        if self.error is not None:
            raise self.error
        raise AssertionError("execution is stubbed for this test")


class _StaticExecution:
    def __init__(self, result: ValidatedPluginResult) -> None:
        self.result = result

    async def execute(
        self, command: ExecutePlugin, cancellation: asyncio.Event
    ) -> ValidatedPluginResult:
        del command, cancellation
        return self.result


class _PassPlanner:
    async def prepare(self, claimed: ClaimedAttempt) -> ExecutePlugin:
        del claimed
        return cast(ExecutePlugin, object())


class _Committer:
    async def commit(
        self,
        *,
        claimed: ClaimedAttempt,
        result: ValidatedPluginResult,
    ) -> CommittedResultManifest:
        del claimed
        return CommittedResultManifest(uuid4(), result.manifest_digest)


@pytest.mark.parametrize(
    ("status", "outcome", "failure_category"),
    (
        (ResultStatus.SUCCEEDED, AttemptState.SUCCEEDED, None),
        (ResultStatus.FAILED, AttemptState.FAILED, FailureCategory.DOMAIN_INVALID),
        (
            ResultStatus.TIMED_OUT,
            AttemptState.TIMED_OUT,
            FailureCategory.DEADLINE_EXCEEDED,
        ),
        (ResultStatus.CANCELLED, AttemptState.CANCELLED, None),
    ),
)
def test_worker_bridge_commits_valid_manifest_for_every_runner_terminal_status(
    status: ResultStatus,
    outcome: AttemptState,
    failure_category: FailureCategory | None,
) -> None:
    result = ValidatedPluginResult(status, {}, "4" * 64, ())
    executor = PluginAttemptHandler(
        planner=cast(PluginExecutionPlanner, _PassPlanner()),
        execution=cast(PluginExecutionService, _StaticExecution(result)),
        committer=_Committer(),
    )
    handler = isolated_plugin_job_handler(executor)

    async def invoke() -> HandlerResult:
        return await handler(WorkerExecution(_claimed(), asyncio.Event()))

    handled = asyncio.run(invoke())

    assert handled.outcome is outcome
    assert handled.result_manifest_id is not None
    assert handled.result_manifest_digest == "4" * 64
    assert (
        handled.failure.category if handled.failure is not None else None
    ) is failure_category


def test_worker_handler_sanitizes_package_integrity_failure() -> None:
    executor = PluginAttemptHandler(
        planner=cast(
            PluginExecutionPlanner,
            _StaticPlanner(PackageIntegrityError("sensitive filesystem detail")),
        ),
        execution=cast(
            PluginExecutionService,
            _StaticExecution(
                ValidatedPluginResult(ResultStatus.SUCCEEDED, {}, "5" * 64, ())
            ),
        ),
        committer=_Committer(),
    )

    handled = asyncio.run(executor.execute(_claimed(), asyncio.Event()))

    assert handled.outcome is AttemptState.FAILED
    assert handled.failure is not None
    assert handled.failure.code == "plugin_package_integrity_failed"
    assert "filesystem" not in handled.failure.detail


class _OciRuntime:
    def __init__(self, capabilities: OciRuntimeCapabilities) -> None:
        self.capabilities = capabilities
        self.plan: OciExecutionPlan | None = None

    async def execute(
        self,
        plan: OciExecutionPlan,
        cancellation: asyncio.Event,
    ) -> RunnerResponse:
        del cancellation
        self.plan = plan
        return RunnerResponse(
            {},
            (),
            SandboxPolicy.attested_oci(),
        )


def _oci_capabilities(**changes: bool) -> OciRuntimeCapabilities:
    values = {
        "digest_pinned_image": True,
        "non_root": True,
        "read_only_root": True,
        "read_only_inputs": True,
        "ephemeral_output": True,
        "network_none": True,
        "no_new_privileges": True,
        "no_host_sockets": True,
        "syscall_profile": True,
        "cpu_memory_pid_quota": True,
        **changes,
    }
    return OciRuntimeCapabilities(**values)


def _oci_command(tmp_path: Path) -> ExecutePlugin:
    context = _context()
    planner = RegistryPluginExecutionPlanner(
        registry=cast(PluginRegistryService, _Registry(_package())),
        context=context,
        plugin_read_decision=_decision(context),
        materializer=cast(PluginExecutionMaterializer, _Materializer(tmp_path)),
        sandbox=SandboxPolicy.development_subprocess(),
    )
    local = asyncio.run(planner.prepare(_claimed()))
    return replace(
        local,
        package=replace(local.package, non_production=False),
        sandbox=SandboxPolicy.attested_oci(),
        production=True,
    )


def test_oci_adapter_emits_runtime_neutral_plan_with_all_security_controls(
    tmp_path: Path,
) -> None:
    runtime = _OciRuntime(_oci_capabilities())

    asyncio.run(OciPluginRunner(runtime).execute(_oci_command(tmp_path), asyncio.Event()))

    assert runtime.plan is not None
    assert runtime.plan.image_digest == "sha256:" + "0" * 64
    assert runtime.plan.network == "none"
    assert runtime.plan.non_root
    assert runtime.plan.root_filesystem_read_only
    assert runtime.plan.no_new_privileges
    assert runtime.plan.no_host_sockets
    assert runtime.plan.syscall_profile


def test_oci_adapter_refuses_runtime_missing_any_required_control(tmp_path: Path) -> None:
    runtime = _OciRuntime(_oci_capabilities(network_none=False))

    with pytest.raises(IsolationUnavailable, match="every required"):
        asyncio.run(
            OciPluginRunner(runtime).execute(_oci_command(tmp_path), asyncio.Event())
        )
    assert runtime.plan is None

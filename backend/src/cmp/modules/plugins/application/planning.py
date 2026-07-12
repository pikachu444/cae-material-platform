"""Prepare one T-18 execution from immutable T-15 and T-17 records."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any, Protocol, cast

from cmp.modules.identity_access.domain.authorization import AuthorizationDecision
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.jobs.application.jobs import ClaimedAttempt
from cmp.modules.plugins.application.execution import ExecutePlugin
from cmp.modules.plugins.application.registry import PluginRegistryService
from cmp.modules.plugins.domain.execution import (
    AllowedOutput,
    ExecutablePluginPackage,
    ExecutionSchema,
    InvalidExecutionRequest,
    RunnerLimits,
    SandboxPolicy,
    StagedInput,
)
from cmp.modules.plugins.domain.registry import (
    ExtensionType,
    PackageRecord,
    SchemaRole,
)


@dataclass(frozen=True, slots=True)
class ExecutionMaterialization:
    """Attempt-scoped files and output policy supplied by the T-10 boundary."""

    archive_path: Path
    dependency_lock_digest: str
    staged_inputs: tuple[StagedInput, ...]
    allowed_outputs: tuple[AllowedOutput, ...]
    output_staging_root: Path


class PluginExecutionMaterializer(Protocol):
    """Materialize approved package/input bytes without exposing object-store credentials."""

    async def materialize(
        self,
        *,
        claimed: ClaimedAttempt,
        package: PackageRecord,
        extension_ordinal: int,
        job_spec: dict[str, Any],
    ) -> ExecutionMaterialization: ...


class PluginExecutionPlanner(Protocol):
    async def prepare(self, claimed: ClaimedAttempt) -> ExecutePlugin: ...


@dataclass(frozen=True, slots=True)
class RunnerLimitPolicy:
    """Platform bounds that are independent of any scientific extension type."""

    cancellation_grace: timedelta = timedelta(seconds=2)
    max_total_output_bytes: int = 512 * 1024 * 1024
    max_processes: int = 64
    max_package_bytes: int = 512 * 1024 * 1024
    max_package_entries: int = 10_000
    max_control_document_bytes: int = 4 * 1024 * 1024
    max_diagnostic_bytes: int = 1024 * 1024

    def for_attempt(
        self,
        claimed: ClaimedAttempt,
        package: PackageRecord,
    ) -> RunnerLimits:
        resource = claimed.job.resource_policy
        return RunnerLimits(
            cpu=resource.cpu_millis / 1000,
            memory_mb=resource.memory_mb,
            gpu=resource.gpu_count,
            timeout=timedelta(seconds=package.manifest.timeout_s),
            cancellation_grace=self.cancellation_grace,
            max_total_output_bytes=self.max_total_output_bytes,
            max_processes=self.max_processes,
            max_package_bytes=self.max_package_bytes,
            max_package_entries=self.max_package_entries,
            max_control_document_bytes=self.max_control_document_bytes,
            max_diagnostic_bytes=self.max_diagnostic_bytes,
        )


def _job_document(claimed: ClaimedAttempt) -> dict[str, Any]:
    value = claimed.attempt.spec.document()
    if not isinstance(value, dict):
        raise InvalidExecutionRequest("immutable Job Spec ceased to be an object")
    job = value
    if (
        str(job.get("job_id")) != str(claimed.job.id)
        or str(job.get("attempt_id")) != str(claimed.attempt.id)
    ):
        raise InvalidExecutionRequest("claimed Job/Attempt identity differs from its Job Spec")
    return job


def _extension_identity(job: dict[str, Any]) -> tuple[ExtensionType, str, str, str]:
    raw = job.get("extension")
    if not isinstance(raw, dict):
        raise InvalidExecutionRequest("Job Spec extension must be an object")
    extension = cast(dict[str, Any], raw)
    try:
        extension_type = ExtensionType(str(extension.get("type")))
    except ValueError as error:
        raise InvalidExecutionRequest("Job Spec extension type is invalid") from error
    digest_ref = str(extension.get("package_digest"))
    if not digest_ref.startswith("sha256:"):
        raise InvalidExecutionRequest("Job Spec package digest is invalid")
    return (
        extension_type,
        str(extension.get("plugin_id")),
        str(extension.get("plugin_version")),
        digest_ref.removeprefix("sha256:"),
    )


class RegistryPluginExecutionPlanner:
    """Resolve exactly one active extension, then request scoped byte materialization."""

    def __init__(
        self,
        *,
        registry: PluginRegistryService,
        context: SecurityContext,
        plugin_read_decision: AuthorizationDecision,
        materializer: PluginExecutionMaterializer,
        sandbox: SandboxPolicy,
        limit_policy: RunnerLimitPolicy | None = None,
        production: bool = False,
    ) -> None:
        self._registry = registry
        self._context = context
        self._decision = plugin_read_decision
        self._materializer = materializer
        self._sandbox = sandbox
        self._limit_policy = limit_policy or RunnerLimitPolicy()
        self._production = production

    async def prepare(self, claimed: ClaimedAttempt) -> ExecutePlugin:
        if (
            claimed.job.organization_id != self._context.organization_id
            or claimed.job.project_id != self._context.project_id
        ):
            raise InvalidExecutionRequest(
                "worker security context differs from the claimed Job tenant"
            )
        job = _job_document(claimed)
        extension_type, plugin_id, plugin_version, package_digest = _extension_identity(job)
        package = await asyncio.to_thread(
            self._registry.get_active,
            self._context,
            self._decision,
            plugin_id=plugin_id,
            plugin_version=plugin_version,
            package_digest=package_digest,
        )
        matching = tuple(
            item
            for item in package.manifest.extensions
            if item.extension_type is extension_type
        )
        if len(matching) != 1:
            raise InvalidExecutionRequest(
                "active package must declare exactly one matching extension type"
            )
        extension = matching[0]
        config_schemas = tuple(
            item
            for item in package.schemas
            if item.extension_ordinal == extension.ordinal
            and item.role is SchemaRole.CONFIG
        )
        if len(config_schemas) > 1:
            raise InvalidExecutionRequest(
                "active extension has more than one registered config schema"
            )
        config_schema = None
        if config_schemas:
            schema = config_schemas[0]
            config_schema = ExecutionSchema(
                schema_id=schema.schema_id,
                document=schema.document(),
                sha256=schema.sha256,
            )
        materialized = await self._materializer.materialize(
            claimed=claimed,
            package=package,
            extension_ordinal=extension.ordinal,
            job_spec=job,
        )
        try:
            executable = ExecutablePluginPackage(
                package_id=package.id,
                plugin_id=package.manifest.plugin_id,
                plugin_version=package.manifest.plugin_version,
                package_digest=package.manifest.package_digest,
                extension_type=extension.extension_type,
                entrypoint=extension.entrypoint,
                capabilities=extension.capabilities,
                artifact_read_roles=package.manifest.artifact_read_roles,
                artifact_write_roles=package.manifest.artifact_write_roles,
                requested_cpu=package.manifest.cpu,
                requested_memory_mb=package.manifest.memory_mb,
                requested_gpu=package.manifest.gpu,
                requested_timeout=timedelta(seconds=package.manifest.timeout_s),
                config_schema=config_schema,
                archive_path=materialized.archive_path,
                dependency_lock_digest=materialized.dependency_lock_digest,
                active=package.active,
                # T-17 currently admits reviewed non-production ZIP packages only. The OCI
                # adapter is production-ready, but a future registry policy must admit images.
                non_production=True,
            )
            limits = self._limit_policy.for_attempt(claimed, package)
        except ValueError as error:
            raise InvalidExecutionRequest(
                "registry or runner resource facts cannot form a valid execution plan"
            ) from error
        return ExecutePlugin(
            job_spec=job,
            package=executable,
            staged_inputs=materialized.staged_inputs,
            allowed_outputs=materialized.allowed_outputs,
            limits=limits,
            sandbox=self._sandbox,
            output_staging_root=materialized.output_staging_root,
            production=self._production,
        )

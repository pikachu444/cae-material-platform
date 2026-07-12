"""OCI-runtime-neutral production execution plan with fail-closed capability attestation."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from cmp.modules.plugins.application.execution import ExecutePlugin
from cmp.modules.plugins.domain.execution import (
    IsolationUnavailable,
    RunnerResponse,
    RuntimeKind,
)


@dataclass(frozen=True, slots=True)
class OciRuntimeCapabilities:
    digest_pinned_image: bool
    non_root: bool
    read_only_root: bool
    read_only_inputs: bool
    ephemeral_output: bool
    network_none: bool
    no_new_privileges: bool
    no_host_sockets: bool
    syscall_profile: bool
    cpu_memory_pid_quota: bool

    @property
    def production_ready(self) -> bool:
        return all(
            (
                self.digest_pinned_image,
                self.non_root,
                self.read_only_root,
                self.read_only_inputs,
                self.ephemeral_output,
                self.network_none,
                self.no_new_privileges,
                self.no_host_sockets,
                self.syscall_profile,
                self.cpu_memory_pid_quota,
            )
        )


@dataclass(frozen=True, slots=True)
class OciInputMount:
    artifact_id: str
    source: Path
    target: str
    read_only: bool = True


@dataclass(frozen=True, slots=True)
class OciOutputPolicy:
    role: str
    schema_ref: str
    media_types: tuple[str, ...]
    max_bytes: int
    retain_on_failure: bool


@dataclass(frozen=True, slots=True)
class OciExecutionPlan:
    image_digest: str
    dependency_lock_digest: str
    job_spec: object
    entrypoint: str
    inputs: tuple[OciInputMount, ...]
    outputs: tuple[OciOutputPolicy, ...]
    output_staging_root: Path
    network: str
    root_filesystem_read_only: bool
    non_root: bool
    no_new_privileges: bool
    no_host_sockets: bool
    syscall_profile: bool
    cpu: float
    memory_mb: int
    gpu: int
    timeout_seconds: float
    max_processes: int
    max_total_output_bytes: int


class OciRuntime(Protocol):
    @property
    def capabilities(self) -> OciRuntimeCapabilities: ...

    async def execute(
        self,
        plan: OciExecutionPlan,
        cancellation: asyncio.Event,
    ) -> RunnerResponse: ...


class OciPluginRunner:
    """Build a runtime-neutral plan; Docker/Kubernetes/vendor APIs stay behind the port."""

    def __init__(self, runtime: OciRuntime) -> None:
        self._runtime = runtime

    async def execute(
        self,
        command: ExecutePlugin,
        cancellation: asyncio.Event,
    ) -> RunnerResponse:
        if command.sandbox.runtime is not RuntimeKind.OCI:
            raise IsolationUnavailable("OCI adapter requires an OCI sandbox policy")
        command.sandbox.require_usable(production=True)
        if not self._runtime.capabilities.production_ready:
            raise IsolationUnavailable(
                "OCI runtime did not attest every required production sandbox control"
            )
        plan = OciExecutionPlan(
            image_digest=command.package.package_digest_ref,
            dependency_lock_digest=command.package.dependency_lock_digest_ref,
            job_spec=command.job_spec,
            entrypoint=command.package.entrypoint,
            inputs=tuple(
                OciInputMount(
                    artifact_id=str(item.artifact_id),
                    source=item.source_path,
                    target=f"/cmp/inputs/{item.artifact_id}",
                )
                for item in command.staged_inputs
            ),
            outputs=tuple(
                OciOutputPolicy(
                    item.role,
                    item.schema_ref,
                    item.media_types,
                    item.max_bytes,
                    item.retain_on_failure,
                )
                for item in command.allowed_outputs
            ),
            output_staging_root=command.output_staging_root,
            network="none",
            root_filesystem_read_only=True,
            non_root=True,
            no_new_privileges=True,
            no_host_sockets=True,
            syscall_profile=True,
            cpu=command.limits.cpu,
            memory_mb=command.limits.memory_mb,
            gpu=command.limits.gpu,
            timeout_seconds=command.limits.timeout.total_seconds(),
            max_processes=command.limits.max_processes,
            max_total_output_bytes=command.limits.max_total_output_bytes,
        )
        response = await self._runtime.execute(plan, cancellation)
        if not response.sandbox.production_ready:
            raise IsolationUnavailable("OCI runtime response lacks sandbox attestation")
        return response

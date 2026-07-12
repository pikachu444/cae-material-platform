"""Framework-free policy and result values for T-18 isolated plugin execution."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import timedelta
from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import UUID

from cmp.modules.plugins.domain.registry import ExtensionType
from cmp.shared.domain.revisions import content_sha256

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_PLUGIN_ID = re.compile(r"^[a-z0-9]+(?:[._-][a-z0-9]+)+$")
_SEMVER = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
_ENTRYPOINT = re.compile(
    r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*:"
    r"[A-Za-z_][A-Za-z0-9_]*$"
)
_ROLE = re.compile(r"^[a-z][a-z0-9_.-]{0,99}$")
_STAGED = re.compile(r"^runner-output:[1-9][0-9]*:sha256:[0-9a-f]{64}$")


class PluginExecutionError(Exception):
    """Base error for T-18 runner preparation or result validation."""


class InvalidExecutionRequest(PluginExecutionError, ValueError):
    """Immutable package, Job Spec, staging, or policy facts disagree."""


class PackageIntegrityError(PluginExecutionError):
    """Package bytes, archive entries, or dependency lock are invalid."""


class IsolationUnavailable(PluginExecutionError):
    """The selected runtime cannot attest the requested sandbox policy."""


class PluginExecutionTimedOut(PluginExecutionError):
    """The runner exceeded its immutable deadline or platform timeout."""


class PluginExecutionCancelled(PluginExecutionError):
    """The worker requested cancellation before a trusted result was committed."""


class InvalidResultManifest(PluginExecutionError):
    """Runner output violates the Result Manifest or output artifact contract."""


class RuntimeKind(StrEnum):
    LOCAL_SUBPROCESS = "local_subprocess"
    OCI = "oci"


class ResultStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


@dataclass(frozen=True, slots=True)
class SandboxPolicy:
    runtime: RuntimeKind
    network: str = "none"
    non_root: bool = True
    root_filesystem_read_only: bool = True
    inputs_read_only: bool = True
    output_ephemeral: bool = True
    no_new_privileges: bool = True
    no_host_sockets: bool = True
    syscall_profile: bool = True
    enforcement_attested: bool = True
    non_production: bool = False

    def __post_init__(self) -> None:
        if self.network != "none":
            raise ValueError("plugin runner network must be exactly 'none'")
        if self.runtime is RuntimeKind.LOCAL_SUBPROCESS and not self.non_production:
            raise ValueError("local subprocess runner is non-production only")

    @classmethod
    def development_subprocess(cls) -> SandboxPolicy:
        """Describe requested best-effort controls without claiming kernel attestation."""

        return cls(
            runtime=RuntimeKind.LOCAL_SUBPROCESS,
            network="none",
            non_root=False,
            root_filesystem_read_only=False,
            inputs_read_only=True,
            output_ephemeral=True,
            no_new_privileges=False,
            no_host_sockets=False,
            syscall_profile=False,
            enforcement_attested=False,
            non_production=True,
        )

    @classmethod
    def attested_oci(cls) -> SandboxPolicy:
        return cls(runtime=RuntimeKind.OCI)

    @property
    def production_ready(self) -> bool:
        return (
            self.runtime is RuntimeKind.OCI
            and self.network == "none"
            and self.non_root
            and self.root_filesystem_read_only
            and self.inputs_read_only
            and self.output_ephemeral
            and self.no_new_privileges
            and self.no_host_sockets
            and self.syscall_profile
            and self.enforcement_attested
            and not self.non_production
        )

    def require_usable(self, *, production: bool) -> None:
        if production and not self.production_ready:
            raise IsolationUnavailable(
                "production plugin execution requires an attested OCI sandbox"
            )
        if not production and self.runtime is RuntimeKind.LOCAL_SUBPROCESS:
            return
        if not production and (
            not self.enforcement_attested
            or not all(
                (
                    self.non_root,
                    self.root_filesystem_read_only,
                    self.inputs_read_only,
                    self.output_ephemeral,
                    self.no_new_privileges,
                    self.no_host_sockets,
                    self.syscall_profile,
                )
            )
        ):
            raise IsolationUnavailable("OCI sandbox controls were not attested")


@dataclass(frozen=True, slots=True)
class RunnerLimits:
    cpu: float
    memory_mb: int
    gpu: int
    timeout: timedelta
    cancellation_grace: timedelta
    max_total_output_bytes: int
    max_processes: int = 64
    max_package_bytes: int = 512 * 1024 * 1024
    max_package_entries: int = 10_000
    max_control_document_bytes: int = 4 * 1024 * 1024
    max_diagnostic_bytes: int = 1024 * 1024

    def __post_init__(self) -> None:
        if not 0 < self.cpu <= 9_999_999.999:
            raise ValueError("runner cpu limit is invalid")
        if not 64 <= self.memory_mb <= 2_147_483_647:
            raise ValueError("runner memory limit is invalid")
        if not 0 <= self.gpu <= 1024:
            raise ValueError("runner gpu limit is invalid")
        if not timedelta(seconds=1) <= self.timeout <= timedelta(hours=24):
            raise ValueError("runner timeout must be between one second and 24 hours")
        if not timedelta(0) <= self.cancellation_grace <= timedelta(seconds=30):
            raise ValueError("cancellation grace must be between zero and 30 seconds")
        for name, value in (
            ("max_total_output_bytes", self.max_total_output_bytes),
            ("max_package_bytes", self.max_package_bytes),
            ("max_control_document_bytes", self.max_control_document_bytes),
            ("max_diagnostic_bytes", self.max_diagnostic_bytes),
        ):
            if not 1 <= value <= 9_223_372_036_854_775_807:
                raise ValueError(f"{name} must be a positive bigint")
        if not 1 <= self.max_package_entries <= 100_000:
            raise ValueError("max_package_entries must be between one and 100000")
        if not 1 <= self.max_processes <= 65_535:
            raise ValueError("max_processes must be between one and 65535")


@dataclass(frozen=True, slots=True)
class ExecutionSchema:
    schema_id: str
    document: dict[str, Any]
    sha256: str

    def __post_init__(self) -> None:
        if not self.schema_id or len(self.schema_id) > 500:
            raise ValueError("execution schema_id is invalid")
        if _SHA256.fullmatch(self.sha256) is None:
            raise ValueError("execution schema digest is invalid")
        if self.document.get("$id") != self.schema_id:
            raise ValueError("execution schema $id differs from schema_id")
        if content_sha256(self.document) != self.sha256:
            raise ValueError("execution schema document digest mismatch")


@dataclass(frozen=True, slots=True)
class ExecutablePluginPackage:
    package_id: UUID
    plugin_id: str
    plugin_version: str
    package_digest: str
    extension_type: ExtensionType
    entrypoint: str
    capabilities: tuple[str, ...]
    artifact_read_roles: tuple[str, ...]
    artifact_write_roles: tuple[str, ...]
    requested_cpu: float
    requested_memory_mb: int
    requested_gpu: int
    requested_timeout: timedelta
    config_schema: ExecutionSchema | None
    archive_path: Path
    dependency_lock_digest: str
    active: bool
    non_production: bool

    def __post_init__(self) -> None:
        if self.package_id.int == 0:
            raise ValueError("package_id must be non-zero")
        if _PLUGIN_ID.fullmatch(self.plugin_id) is None or len(self.plugin_id) > 255:
            raise ValueError("plugin_id is invalid")
        if _SEMVER.fullmatch(self.plugin_version) is None or len(self.plugin_version) > 64:
            raise ValueError("plugin_version is invalid")
        if (
            _SHA256.fullmatch(self.package_digest) is None
            or _SHA256.fullmatch(self.dependency_lock_digest) is None
        ):
            raise ValueError("package and dependency-lock digests must be lowercase SHA-256")
        if _ENTRYPOINT.fullmatch(self.entrypoint) is None:
            raise ValueError("entrypoint must be a safe module:attribute reference")
        if not self.capabilities or tuple(sorted(set(self.capabilities))) != self.capabilities:
            raise ValueError("package capabilities must be sorted, unique, and non-empty")
        for name, roles in (
            ("artifact_read_roles", self.artifact_read_roles),
            ("artifact_write_roles", self.artifact_write_roles),
        ):
            if tuple(sorted(set(roles))) != roles or any(
                _ROLE.fullmatch(role) is None for role in roles
            ):
                raise ValueError(f"{name} must contain sorted unique roles")
        if not 0 < self.requested_cpu <= 9_999_999.999:
            raise ValueError("package requested_cpu is invalid")
        if not 64 <= self.requested_memory_mb <= 2_147_483_647:
            raise ValueError("package requested_memory_mb is invalid")
        if not 0 <= self.requested_gpu <= 1024:
            raise ValueError("package requested_gpu is invalid")
        if not timedelta(seconds=1) <= self.requested_timeout <= timedelta(hours=24):
            raise ValueError("package requested_timeout is invalid")

    @property
    def package_digest_ref(self) -> str:
        return f"sha256:{self.package_digest}"

    @property
    def dependency_lock_digest_ref(self) -> str:
        return f"sha256:{self.dependency_lock_digest}"


@dataclass(frozen=True, slots=True)
class StagedInput:
    role: str
    artifact_id: UUID
    sha256: str
    media_type: str
    source_path: Path
    size_bytes: int

    def __post_init__(self) -> None:
        if _ROLE.fullmatch(self.role) is None or self.artifact_id.int == 0:
            raise ValueError("staged input role or artifact identity is invalid")
        if _SHA256.fullmatch(self.sha256) is None:
            raise ValueError("staged input digest is invalid")
        if not self.media_type or len(self.media_type) > 255:
            raise ValueError("staged input media type is invalid")
        if not 0 <= self.size_bytes <= 9_223_372_036_854_775_807:
            raise ValueError("staged input size must fit a non-negative bigint")


@dataclass(frozen=True, slots=True)
class AllowedOutput:
    role: str
    schema_ref: str
    media_types: tuple[str, ...]
    max_bytes: int
    retain_on_failure: bool = False

    def __post_init__(self) -> None:
        if _ROLE.fullmatch(self.role) is None:
            raise ValueError("allowed output role is invalid")
        if not self.schema_ref or len(self.schema_ref) > 500:
            raise ValueError("allowed output schema_ref is invalid")
        if not self.media_types or tuple(sorted(set(self.media_types))) != self.media_types:
            raise ValueError("allowed output media types must be sorted and unique")
        if not 1 <= self.max_bytes <= 9_223_372_036_854_775_807:
            raise ValueError("allowed output size must be a positive bigint")


@dataclass(frozen=True, slots=True)
class RunnerOutput:
    role: str
    media_type: str
    schema_ref: str
    staged_artifact: str
    sha256: str
    size_bytes: int
    path: Path

    def __post_init__(self) -> None:
        if _ROLE.fullmatch(self.role) is None or _STAGED.fullmatch(
            self.staged_artifact
        ) is None:
            raise ValueError("runner output role or staged reference is invalid")
        if _SHA256.fullmatch(self.sha256) is None:
            raise ValueError("runner output digest is invalid")
        if not 0 <= self.size_bytes <= 9_223_372_036_854_775_807:
            raise ValueError("runner output size must fit a non-negative bigint")


@dataclass(frozen=True, slots=True)
class RunnerResponse:
    manifest: object
    outputs: tuple[RunnerOutput, ...]
    sandbox: SandboxPolicy


@dataclass(frozen=True, slots=True)
class ValidatedPluginResult:
    status: ResultStatus
    manifest: dict[str, object]
    manifest_digest: str
    outputs: tuple[RunnerOutput, ...]

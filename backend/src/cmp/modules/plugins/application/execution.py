"""T-18 isolated plugin execution use case and runner port."""

from __future__ import annotations

import asyncio
import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol, cast
from uuid import UUID

from cmp.modules.plugins.domain.execution import (
    AllowedOutput,
    ExecutablePluginPackage,
    InvalidExecutionRequest,
    InvalidResultManifest,
    PluginExecutionCancelled,
    ResultStatus,
    RunnerLimits,
    RunnerOutput,
    RunnerResponse,
    SandboxPolicy,
    StagedInput,
    ValidatedPluginResult,
)
from cmp.shared.domain.revisions import canonical_json_bytes, content_sha256


class RunnerContractValidator(Protocol):
    def validate_job_spec(self, document: object) -> None: ...

    def validate_result_manifest(self, document: object) -> None: ...

    def validate_instance(self, instance: object, schema: object) -> None: ...


@dataclass(frozen=True, slots=True)
class ExecutePlugin:
    job_spec: object
    package: ExecutablePluginPackage
    staged_inputs: tuple[StagedInput, ...]
    allowed_outputs: tuple[AllowedOutput, ...]
    limits: RunnerLimits
    sandbox: SandboxPolicy
    output_staging_root: Path
    production: bool = False


class PluginRunner(Protocol):
    async def execute(
        self,
        command: ExecutePlugin,
        cancellation: asyncio.Event,
    ) -> RunnerResponse: ...


def _object(value: object, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise InvalidExecutionRequest(f"{name} must be an object")
    return cast(dict[str, Any], value)


def _uuid(value: object, name: str) -> UUID:
    try:
        parsed = UUID(str(value))
    except ValueError as error:
        raise InvalidExecutionRequest(f"{name} must be a UUID") from error
    if parsed.int == 0:
        raise InvalidExecutionRequest(f"{name} must be non-zero")
    return parsed


def _time(value: object, name: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as error:
        raise InvalidResultManifest(f"{name} must be an RFC3339 timestamp") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise InvalidResultManifest(f"{name} must be timezone-aware")
    return parsed


def _verify_file(output: RunnerOutput, root: Path) -> None:
    if output.path.is_symlink():
        raise InvalidResultManifest("runner output cannot be a symlink")
    try:
        resolved_root = root.resolve(strict=True)
        path = output.path.resolve(strict=True)
        path.relative_to(resolved_root)
    except (OSError, ValueError) as error:
        raise InvalidResultManifest("runner output escapes the staging root") from error
    if not path.is_file() or path.stat().st_size != output.size_bytes:
        raise InvalidResultManifest("runner output size differs from the staged file")
    digest = hashlib.sha256()
    observed = 0
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            observed += len(chunk)
            if observed > output.size_bytes:
                raise InvalidResultManifest("runner output grew during verification")
            digest.update(chunk)
    if observed != output.size_bytes or digest.hexdigest() != output.sha256:
        raise InvalidResultManifest("runner output digest differs from the staged file")


class PluginExecutionService:
    def __init__(
        self,
        *,
        runner: PluginRunner,
        validator: RunnerContractValidator,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._runner = runner
        self._validator = validator
        self._clock = clock or (lambda: datetime.now(UTC))

    def _validate_command(self, command: ExecutePlugin) -> dict[str, Any]:
        self._validator.validate_job_spec(command.job_spec)
        job = _object(command.job_spec, "Job Spec")
        package = command.package
        if not package.active:
            raise InvalidExecutionRequest("plugin package is not active in this project")
        if command.production and package.non_production:
            raise InvalidExecutionRequest("non-production package cannot run in production")
        if not command.production and not package.non_production:
            raise InvalidExecutionRequest(
                "production package cannot use the local non-production execution path"
            )
        command.sandbox.require_usable(production=command.production)
        extension = _object(job.get("extension"), "Job Spec extension")
        expected_identity = (
            package.extension_type.value,
            package.plugin_id,
            package.plugin_version,
            package.package_digest_ref,
        )
        actual_identity = (
            extension.get("type"),
            extension.get("plugin_id"),
            extension.get("plugin_version"),
            extension.get("package_digest"),
        )
        if actual_identity != expected_identity:
            raise InvalidExecutionRequest(
                "Job Spec extension identity differs from the active package"
            )
        execution = _object(job.get("execution"), "Job Spec execution")
        try:
            deadline = _time(execution.get("deadline"), "execution.deadline")
        except InvalidResultManifest as error:
            raise InvalidExecutionRequest(str(error)) from error
        if deadline <= self._clock():
            raise InvalidExecutionRequest("Job Spec deadline has already elapsed")
        if not (
            command.limits.cpu <= package.requested_cpu
            and command.limits.memory_mb <= package.requested_memory_mb
            and command.limits.gpu <= package.requested_gpu
            and command.limits.timeout <= package.requested_timeout
        ):
            raise InvalidExecutionRequest(
                "runner limits cannot exceed immutable package resource requests"
            )

        raw_inputs = job.get("inputs")
        if not isinstance(raw_inputs, list):
            raise InvalidExecutionRequest("Job Spec inputs must be an array")
        staged_by_id = {item.artifact_id: item for item in command.staged_inputs}
        if len(staged_by_id) != len(command.staged_inputs):
            raise InvalidExecutionRequest("staged input artifact IDs must be unique")
        seen_inputs: set[UUID] = set()
        for raw in raw_inputs:
            item = _object(raw, "Job Spec input")
            artifact_id = _uuid(item.get("artifact_id"), "input.artifact_id")
            staged = staged_by_id.get(artifact_id)
            if staged is None or artifact_id in seen_inputs:
                raise InvalidExecutionRequest("Job Spec input staging is missing or duplicated")
            seen_inputs.add(artifact_id)
            if (
                staged.role != item.get("role")
                or staged.sha256 != item.get("sha256")
                or staged.media_type != item.get("media_type")
                or staged.role not in package.artifact_read_roles
            ):
                raise InvalidExecutionRequest(
                    "staged input differs from Job Spec or package read roles"
                )
        if seen_inputs != set(staged_by_id):
            raise InvalidExecutionRequest("unexpected staged inputs were supplied")

        raw_expected = job.get("expected_outputs")
        if not isinstance(raw_expected, list):
            raise InvalidExecutionRequest("Job Spec expected_outputs must be an array")
        expected: dict[str, str] = {}
        for raw in raw_expected:
            item = _object(raw, "Job Spec expected output")
            role = str(item.get("role"))
            if role in expected:
                raise InvalidExecutionRequest("expected output roles must be unique")
            expected[role] = str(item.get("schema_ref"))
        rules = {item.role: item for item in command.allowed_outputs}
        if len(rules) != len(command.allowed_outputs) or set(rules) != set(expected):
            raise InvalidExecutionRequest(
                "output policies must match Job Spec expected roles exactly"
            )
        for role, schema_ref in expected.items():
            if (
                rules[role].schema_ref != schema_ref
                or role not in package.artifact_write_roles
            ):
                raise InvalidExecutionRequest(
                    "output schema or package write role differs from the Job Spec"
                )
        config_ref = job.get("config_schema_ref")
        if package.config_schema is None:
            if config_ref is not None:
                raise InvalidExecutionRequest("Job Spec references an unregistered config schema")
        else:
            if config_ref != package.config_schema.schema_id:
                raise InvalidExecutionRequest(
                    "Job Spec config schema differs from the active package"
                )
            self._validator.validate_instance(
                job.get("config"), package.config_schema.document
            )
        return job

    def _validate_result(
        self,
        command: ExecutePlugin,
        job: dict[str, Any],
        response: RunnerResponse,
    ) -> ValidatedPluginResult:
        if response.sandbox != command.sandbox:
            raise InvalidResultManifest("runner sandbox attestation differs from the request")
        self._validator.validate_result_manifest(response.manifest)
        manifest = _object(response.manifest, "Result Manifest")
        try:
            identities_match = (
                _uuid(manifest.get("job_id"), "result.job_id")
                == _uuid(job.get("job_id"), "job_id")
                and _uuid(manifest.get("attempt_id"), "result.attempt_id")
                == _uuid(job.get("attempt_id"), "attempt_id")
            )
        except InvalidExecutionRequest as error:
            raise InvalidResultManifest(str(error)) from error
        if not identities_match:
            raise InvalidResultManifest("Result Manifest job/attempt identity mismatch")
        started = _time(manifest.get("started_at"), "result.started_at")
        ended = _time(manifest.get("ended_at"), "result.ended_at")
        if ended < started:
            raise InvalidResultManifest("Result Manifest ended_at precedes started_at")
        try:
            status = ResultStatus(str(manifest.get("status")))
        except ValueError as error:
            raise InvalidResultManifest("Result Manifest status is invalid") from error
        if manifest.get("non_production") is not (not command.production):
            raise InvalidResultManifest(
                "Result Manifest execution mode differs from the runner request"
            )
        execution = _object(job.get("execution"), "Job Spec execution")
        deadline = _time(execution.get("deadline"), "execution.deadline")
        if status is ResultStatus.SUCCEEDED and ended > deadline:
            raise InvalidResultManifest("successful Result Manifest exceeded the Job deadline")
        reproducibility = _object(
            manifest.get("reproducibility"), "Result Manifest reproducibility"
        )
        if (
            reproducibility.get("package_digest")
            != command.package.package_digest_ref
            or reproducibility.get("dependency_lock_digest")
            != command.package.dependency_lock_digest_ref
            or reproducibility.get("seed") != execution.get("seed")
        ):
            raise InvalidResultManifest("Result Manifest reproducibility identity mismatch")

        raw_outputs = manifest.get("outputs")
        if not isinstance(raw_outputs, list):
            raise InvalidResultManifest("Result Manifest outputs must be an array")
        staged = {item.staged_artifact: item for item in response.outputs}
        if len(staged) != len(response.outputs) or len(raw_outputs) != len(staged):
            raise InvalidResultManifest("Result Manifest staged outputs are duplicated or missing")
        rules = {item.role: item for item in command.allowed_outputs}
        observed_roles: set[str] = set()
        total = 0
        for raw in raw_outputs:
            item = _object(raw, "Result Manifest output")
            token = str(item.get("staged_artifact"))
            output = staged.get(token)
            if output is None or output.role in observed_roles:
                raise InvalidResultManifest("Result Manifest output is unknown or duplicated")
            observed_roles.add(output.role)
            rule = rules.get(output.role)
            if rule is None or (
                output.media_type not in rule.media_types
                or output.schema_ref != rule.schema_ref
                or output.size_bytes > rule.max_bytes
                or (
                    status is not ResultStatus.SUCCEEDED
                    and not rule.retain_on_failure
                )
                or item.get("role") != output.role
                or item.get("media_type") != output.media_type
                or item.get("schema_ref") != output.schema_ref
                or item.get("sha256") != output.sha256
                or item.get("size_bytes") != output.size_bytes
                or not token.endswith(output.sha256)
            ):
                raise InvalidResultManifest("Result Manifest output violates its allowlist")
            _verify_file(output, command.output_staging_root)
            total += output.size_bytes
            if total > command.limits.max_total_output_bytes:
                raise InvalidResultManifest("Result Manifest outputs exceed the total size limit")
        if status is ResultStatus.SUCCEEDED and observed_roles != set(rules):
            raise InvalidResultManifest(
                "successful Result Manifest must contain every expected output role"
            )
        canonical = canonical_json_bytes(manifest)
        canonical_value = json.loads(canonical)
        if not isinstance(canonical_value, dict):
            raise RuntimeError("canonical Result Manifest ceased to be an object")
        return ValidatedPluginResult(
            status=status,
            manifest=cast(dict[str, object], canonical_value),
            manifest_digest=content_sha256(canonical_value),
            outputs=response.outputs,
        )

    async def execute(
        self,
        command: ExecutePlugin,
        cancellation: asyncio.Event,
    ) -> ValidatedPluginResult:
        job = self._validate_command(command)
        if cancellation.is_set():
            raise PluginExecutionCancelled("execution was cancelled before runner launch")
        response = await self._runner.execute(command, cancellation)
        return self._validate_result(command, job, response)

"""Non-production subprocess runner with safe package staging and bounded file protocol."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import platform
import re
import shutil
import stat
import sys
import tempfile
import zipfile
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any, cast

from cmp.modules.plugins.application.execution import ExecutePlugin
from cmp.modules.plugins.domain.execution import (
    InvalidExecutionRequest,
    InvalidResultManifest,
    PackageIntegrityError,
    PluginExecutionCancelled,
    PluginExecutionTimedOut,
    RunnerOutput,
    RunnerResponse,
    RuntimeKind,
    SandboxPolicy,
)

_STAGED = re.compile(r"^runner-output:([1-9][0-9]*):sha256:([0-9a-f]{64})$")


def _hash_file(path: Path, *, maximum: int) -> tuple[str, int]:
    if path.is_symlink() or not path.is_file():
        raise PackageIntegrityError("staged artifact must be a regular file")
    digest = hashlib.sha256()
    observed = 0
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            observed += len(chunk)
            if observed > maximum:
                raise PackageIntegrityError("staged artifact exceeds its size limit")
            digest.update(chunk)
    return digest.hexdigest(), observed


def _archive_path(name: str) -> PurePosixPath:
    if "\\" in name or "\x00" in name or re.match(r"^[A-Za-z]:", name):
        raise PackageIntegrityError("package archive entry has an unsafe path")
    path = PurePosixPath(name)
    if path.is_absolute() or not path.parts or any(
        part in {"", ".", ".."} for part in path.parts
    ):
        raise PackageIntegrityError("package archive entry has an unsafe path")
    return path


def _is_zip_symlink(info: zipfile.ZipInfo) -> bool:
    mode = info.external_attr >> 16
    return stat.S_IFMT(mode) == stat.S_IFLNK


def _extract_package(command: ExecutePlugin, destination: Path) -> None:
    package = command.package
    digest, size = _hash_file(
        package.archive_path, maximum=command.limits.max_package_bytes
    )
    if digest != package.package_digest or size == 0:
        raise PackageIntegrityError("plugin package archive digest or size mismatch")
    seen: set[PurePosixPath] = set()
    unpacked = 0
    try:
        archive = zipfile.ZipFile(package.archive_path)
    except (OSError, zipfile.BadZipFile) as error:
        raise PackageIntegrityError("plugin package is not a valid ZIP archive") from error
    with archive:
        infos = archive.infolist()
        if not infos or len(infos) > command.limits.max_package_entries:
            raise PackageIntegrityError("plugin package entry count is invalid")
        for info in infos:
            path = _archive_path(info.filename.rstrip("/"))
            if path in seen or info.flag_bits & 0x1 or _is_zip_symlink(info):
                raise PackageIntegrityError(
                    "plugin package contains duplicate, encrypted, or linked entries"
                )
            seen.add(path)
            unpacked += info.file_size
            if unpacked > command.limits.max_package_bytes:
                raise PackageIntegrityError("plugin package expands beyond its size limit")
            target = destination.joinpath(*path.parts)
            resolved = target.resolve(strict=False)
            try:
                resolved.relative_to(destination.resolve(strict=True))
            except ValueError as error:
                raise PackageIntegrityError("plugin package extraction path escapes") from error
            if info.is_dir():
                resolved.mkdir(parents=True, exist_ok=True)
                continue
            resolved.parent.mkdir(parents=True, exist_ok=True)
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
            descriptor = os.open(resolved, flags, 0o600)
            try:
                with archive.open(info, "r") as source, os.fdopen(
                    descriptor, "wb", closefd=False
                ) as target_stream:
                    shutil.copyfileobj(source, target_stream, length=1024 * 1024)
            finally:
                os.close(descriptor)
            if resolved.stat().st_size != info.file_size:
                raise PackageIntegrityError("plugin package entry size changed while extracting")
    lock = destination / "dependency.lock"
    lock_digest, lock_size = _hash_file(lock, maximum=command.limits.max_control_document_bytes)
    if lock_size == 0 or lock_digest != package.dependency_lock_digest:
        raise PackageIntegrityError("plugin dependency lock digest mismatch")
    for extracted_path in sorted(destination.rglob("*"), reverse=True):
        if extracted_path.is_file():
            try:
                extracted_path.chmod(stat.S_IREAD)
            except OSError:
                pass


def _copy_inputs(command: ExecutePlugin, destination: Path) -> list[dict[str, object]]:
    values: list[dict[str, object]] = []
    for item in command.staged_inputs:
        digest, size = _hash_file(item.source_path, maximum=item.size_bytes)
        if digest != item.sha256 or size != item.size_bytes:
            raise InvalidExecutionRequest("staged input bytes differ from the Job Spec")
        file_name = f"{item.artifact_id}.input"
        target = destination / file_name
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(target, flags, 0o400)
        try:
            with item.source_path.open("rb") as source, os.fdopen(
                descriptor, "wb", closefd=False
            ) as target_stream:
                shutil.copyfileobj(source, target_stream, length=1024 * 1024)
        finally:
            os.close(descriptor)
        try:
            target.chmod(stat.S_IREAD)
        except OSError:
            pass
        values.append(
            {
                "role": item.role,
                "artifact_id": str(item.artifact_id),
                "sha256": item.sha256,
                "media_type": item.media_type,
                "size_bytes": item.size_bytes,
                "file_name": file_name,
            }
        )
    return values


def _environment() -> dict[str, str]:
    environment = {
        "PYTHONHASHSEED": "0",
        "PYTHONDONTWRITEBYTECODE": "1",
        "TZ": "UTC",
        "LC_ALL": "C",
        "LANG": "C",
    }
    for name in ("PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "PATHEXT"):
        value = os.environ.get(name)
        if value:
            environment[name] = value
    return environment


def _write_json(path: Path, value: object, maximum: int) -> None:
    payload = json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    if len(payload) > maximum:
        raise InvalidExecutionRequest("runner control document exceeds its size limit")
    path.write_bytes(payload)


def _policy(command: ExecutePlugin, inputs: list[dict[str, object]]) -> dict[str, object]:
    package = command.package
    return {
        "runner_protocol_version": "1.0",
        "network": "none",
        "non_production": True,
        "package": {
            "plugin_id": package.plugin_id,
            "plugin_version": package.plugin_version,
            "package_digest": package.package_digest_ref,
            "dependency_lock_digest": package.dependency_lock_digest_ref,
            "extension_type": package.extension_type.value,
            "entrypoint": package.entrypoint,
            "capabilities": list(package.capabilities),
        },
        "inputs": inputs,
        "outputs": [
            {
                "role": item.role,
                "schema_ref": item.schema_ref,
                "media_types": list(item.media_types),
                "max_bytes": item.max_bytes,
                "retain_on_failure": item.retain_on_failure,
            }
            for item in command.allowed_outputs
        ],
        "max_total_output_bytes": command.limits.max_total_output_bytes,
        "hardware_summary": platform.machine() or "unknown",
    }


async def _stop(process: asyncio.subprocess.Process) -> None:
    if process.returncode is not None:
        return
    process.kill()
    await process.wait()


async def _await_process(
    process: asyncio.subprocess.Process,
    *,
    cancellation: asyncio.Event,
    cancellation_marker: Path,
    timeout_seconds: float,
    grace_seconds: float,
) -> None:
    process_wait = asyncio.create_task(process.wait())
    cancellation_wait = asyncio.create_task(cancellation.wait())
    try:
        done, _ = await asyncio.wait(
            {process_wait, cancellation_wait},
            timeout=timeout_seconds,
            return_when=asyncio.FIRST_COMPLETED,
        )
        if process_wait in done:
            return
        if cancellation_wait in done and cancellation.is_set():
            cancellation_marker.touch(exist_ok=True)
            try:
                # Keep the transport wait alive so Windows cleanup cannot race a killed child.
                await asyncio.wait_for(asyncio.shield(process_wait), timeout=grace_seconds)
                return
            except TimeoutError as error:
                await _stop(process)
                raise PluginExecutionCancelled(
                    "plugin subprocess ignored cancellation"
                ) from error
        try:
            await asyncio.wait_for(asyncio.shield(process_wait), timeout=grace_seconds)
            return
        except TimeoutError as error:
            await _stop(process)
            raise PluginExecutionTimedOut(
                "plugin subprocess exceeded its timeout"
            ) from error
    except asyncio.CancelledError:
        await _stop(process)
        raise
    finally:
        if not process_wait.done():
            process_wait.cancel()
        if not cancellation_wait.done():
            cancellation_wait.cancel()


def _read_result(
    command: ExecutePlugin, result_path: Path
) -> tuple[object, tuple[RunnerOutput, ...]]:
    if result_path.is_symlink() or not result_path.is_file():
        raise InvalidResultManifest("plugin runner did not produce a Result Manifest")
    if result_path.stat().st_size > command.limits.max_control_document_bytes:
        raise InvalidResultManifest("Result Manifest exceeds its size limit")
    try:
        manifest = json.loads(result_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise InvalidResultManifest("plugin runner produced corrupt result JSON") from error
    if not isinstance(manifest, dict) or not isinstance(manifest.get("outputs"), list):
        raise InvalidResultManifest("plugin runner result is not a manifest object")
    outputs: list[RunnerOutput] = []
    for raw in cast(list[object], manifest["outputs"]):
        if not isinstance(raw, dict):
            raise InvalidResultManifest("Result Manifest output must be an object")
        item = cast(dict[str, Any], raw)
        staged = str(item.get("staged_artifact"))
        match = _STAGED.fullmatch(staged)
        if match is None:
            raise InvalidResultManifest("Result Manifest staged reference is invalid")
        ordinal = int(match.group(1))
        digest = match.group(2)
        candidates = tuple(
            command.output_staging_root.glob(f"{ordinal:04d}-*-{digest}.bin")
        )
        if len(candidates) != 1:
            raise InvalidResultManifest("staged output file is missing or ambiguous")
        path = candidates[0]
        try:
            expected_size = int(item.get("size_bytes", -1))
            observed_digest, size = _hash_file(path, maximum=expected_size)
        except (PackageIntegrityError, TypeError, ValueError) as error:
            raise InvalidResultManifest("staged output file is invalid") from error
        if observed_digest != digest or size != item.get("size_bytes"):
            raise InvalidResultManifest("staged output bytes differ from the manifest")
        outputs.append(
            RunnerOutput(
                role=str(item.get("role")),
                media_type=str(item.get("media_type")),
                schema_ref=str(item.get("schema_ref")),
                staged_artifact=staged,
                sha256=digest,
                size_bytes=size,
                path=path,
            )
        )
    return manifest, tuple(outputs)


class SubprocessPluginRunner:
    """Reviewed-package development adapter; not a production security boundary."""

    def __init__(self, *, temporary_root: Path | None = None) -> None:
        self._temporary_root = temporary_root

    async def execute(
        self,
        command: ExecutePlugin,
        cancellation: asyncio.Event,
    ) -> RunnerResponse:
        if command.production or command.sandbox.runtime is not RuntimeKind.LOCAL_SUBPROCESS:
            raise InvalidExecutionRequest(
                "subprocess adapter accepts non-production local policy only"
            )
        if command.sandbox != SandboxPolicy.development_subprocess():
            raise InvalidExecutionRequest(
                "subprocess sandbox policy must not claim unattested production controls"
            )
        if command.output_staging_root.exists() or any(
            parent.is_symlink() for parent in command.output_staging_root.parents
        ):
            raise InvalidExecutionRequest("output staging root must be newly allocated")
        command.output_staging_root.mkdir(parents=True, exist_ok=False)
        temporary_parent = str(self._temporary_root) if self._temporary_root else None
        with tempfile.TemporaryDirectory(
            prefix="cmp-plugin-", dir=temporary_parent
        ) as temporary:
            root = Path(temporary)
            package_root = root / "package"
            input_root = root / "inputs"
            workspace_root = root / "workspace"
            package_root.mkdir()
            input_root.mkdir()
            workspace_root.mkdir()
            _extract_package(command, package_root)
            input_values = _copy_inputs(command, input_root)
            job_path = root / "job-spec.json"
            policy_path = root / "runner-policy.json"
            result_path = command.output_staging_root / "result-manifest.json"
            cancellation_marker = workspace_root / "cancel.requested"
            stdout_path = root / "runner.stdout"
            stderr_path = root / "runner.stderr"
            _write_json(
                job_path,
                command.job_spec,
                command.limits.max_control_document_bytes,
            )
            _write_json(
                policy_path,
                _policy(command, input_values),
                command.limits.max_control_document_bytes,
            )
            deadline = datetime.fromisoformat(
                str(cast(dict[str, Any], command.job_spec)["execution"]["deadline"])
                .replace("Z", "+00:00")
            )
            remaining = max(0.0, (deadline - datetime.now(UTC)).total_seconds())
            timeout_seconds = min(command.limits.timeout.total_seconds(), remaining)
            if timeout_seconds <= 0:
                raise PluginExecutionTimedOut("Job Spec deadline elapsed before launch")
            with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
                process = await asyncio.create_subprocess_exec(
                    sys.executable,
                    "-I",
                    "-m",
                    "cmp_plugin_sdk.runner",
                    "--job-spec",
                    str(job_path),
                    "--policy",
                    str(policy_path),
                    "--package-root",
                    str(package_root),
                    "--input-root",
                    str(input_root),
                    "--output-root",
                    str(command.output_staging_root),
                    "--workspace-root",
                    str(workspace_root),
                    "--result",
                    str(result_path),
                    cwd=workspace_root,
                    env=_environment(),
                    stdin=asyncio.subprocess.DEVNULL,
                    stdout=stdout,
                    stderr=stderr,
                )
                await _await_process(
                    process,
                    cancellation=cancellation,
                    cancellation_marker=cancellation_marker,
                    timeout_seconds=timeout_seconds,
                    grace_seconds=command.limits.cancellation_grace.total_seconds(),
                )
            for diagnostic_path in (stdout_path, stderr_path):
                if diagnostic_path.stat().st_size > command.limits.max_diagnostic_bytes:
                    raise InvalidResultManifest("runner diagnostics exceeded their size limit")
            if process.returncode != 0:
                raise InvalidResultManifest("plugin runner bootstrap failed closed")
            manifest, outputs = _read_result(command, result_path)
            return RunnerResponse(manifest, outputs, command.sandbox)

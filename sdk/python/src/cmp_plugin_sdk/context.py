"""Capability-limited execution context supplied to one plugin extension."""

from __future__ import annotations

import hashlib
import os
import random
import re
import stat
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from uuid import UUID

from cmp_plugin_sdk.model import Diagnostic, RunnerJobSpec

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_ROLE = re.compile(r"^[a-z][a-z0-9_.-]{0,99}$")


class RunContextError(Exception):
    """Base error for capability-limited SDK operations."""


class CancellationRequested(RunContextError):
    """The parent runner requested cooperative cancellation."""


class DeadlineExceeded(RunContextError):
    """The immutable Job Spec deadline elapsed."""


class OutputPolicyError(RunContextError):
    """A plugin attempted an undeclared, unsafe, or oversized output."""


@dataclass(frozen=True, slots=True)
class InputBinding:
    role: str
    artifact_id: UUID
    sha256: str
    media_type: str
    path: Path
    size_bytes: int

    def __post_init__(self) -> None:
        if _ROLE.fullmatch(self.role) is None:
            raise ValueError("input role is invalid")
        if self.artifact_id.int == 0 or _SHA256.fullmatch(self.sha256) is None:
            raise ValueError("input artifact identity or digest is invalid")
        if not 0 <= self.size_bytes <= 9223372036854775807:
            raise ValueError("input size must fit a non-negative bigint")


@dataclass(frozen=True, slots=True)
class OutputRule:
    role: str
    schema_ref: str
    media_types: tuple[str, ...]
    max_bytes: int

    def __post_init__(self) -> None:
        if _ROLE.fullmatch(self.role) is None:
            raise ValueError("output role is invalid")
        if not self.schema_ref or self.schema_ref != self.schema_ref.strip():
            raise ValueError("output schema_ref must be non-blank and trimmed")
        if not self.media_types or tuple(sorted(set(self.media_types))) != self.media_types:
            raise ValueError("output media types must be sorted, unique, and non-empty")
        if any(not value or value != value.strip() for value in self.media_types):
            raise ValueError("output media type is invalid")
        if not 1 <= self.max_bytes <= 9223372036854775807:
            raise ValueError("output max_bytes must be a positive bigint")


@dataclass(frozen=True, slots=True)
class StagedOutput:
    role: str
    media_type: str
    schema_ref: str
    staged_artifact: str
    sha256: str
    size_bytes: int
    path: Path

    def manifest_entry(self) -> dict[str, object]:
        return {
            "role": self.role,
            "media_type": self.media_type,
            "schema_ref": self.schema_ref,
            "staged_artifact": self.staged_artifact,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
        }


def _within(root: Path, candidate: Path) -> Path:
    resolved_root = root.resolve(strict=True)
    resolved = candidate.resolve(strict=False)
    try:
        resolved.relative_to(resolved_root)
    except ValueError as error:
        raise OutputPolicyError("path escapes the ephemeral runner workspace") from error
    return resolved


def _safe_relative(value: str) -> PurePosixPath:
    if "\\" in value or "\x00" in value:
        raise OutputPolicyError("workspace path contains a forbidden separator")
    relative = PurePosixPath(value)
    if relative.is_absolute() or not relative.parts or any(
        part in {"", ".", ".."} for part in relative.parts
    ):
        raise OutputPolicyError("workspace path must be a safe relative path")
    return relative


class RunContext:
    """The only I/O, time, cancellation, and RNG surface given to plugin code."""

    def __init__(
        self,
        *,
        job: RunnerJobSpec,
        inputs: tuple[InputBinding, ...],
        output_rules: tuple[OutputRule, ...],
        output_root: Path,
        workspace_root: Path,
        cancellation_marker: Path,
        max_total_output_bytes: int,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if not 1 <= max_total_output_bytes <= 9223372036854775807:
            raise ValueError("max_total_output_bytes must be a positive bigint")
        if len({rule.role for rule in output_rules}) != len(output_rules):
            raise ValueError("output roles must be unique")
        self._job = job
        self._inputs = inputs
        self._rules = {rule.role: rule for rule in output_rules}
        self._output_root = output_root.resolve(strict=True)
        self._workspace_root = workspace_root.resolve(strict=True)
        self._cancellation_marker = cancellation_marker
        self._max_total = max_total_output_bytes
        self._clock = clock or (lambda: datetime.now(UTC))
        self._rng = random.Random(job.seed)
        self._outputs: list[StagedOutput] = []
        self._diagnostics: list[Diagnostic] = []
        self._total_output = 0

    @property
    def rng(self) -> random.Random:
        return self._rng

    @property
    def outputs(self) -> tuple[StagedOutput, ...]:
        return tuple(self._outputs)

    @property
    def diagnostics(self) -> tuple[Diagnostic, ...]:
        return tuple(self._diagnostics)

    @property
    def cancelled(self) -> bool:
        return self._cancellation_marker.exists()

    def raise_if_cancelled(self) -> None:
        if self.cancelled:
            raise CancellationRequested("plugin execution was cancelled")
        if self._clock() >= self._job.deadline:
            raise DeadlineExceeded("plugin execution deadline elapsed")

    def add_diagnostic(self, diagnostic: Diagnostic) -> None:
        self._diagnostics.append(diagnostic)

    def read_input(
        self,
        role: str,
        *,
        index: int = 0,
        maximum_bytes: int | None = None,
    ) -> bytes:
        self.raise_if_cancelled()
        matches = tuple(item for item in self._inputs if item.role == role)
        if index < 0 or index >= len(matches):
            raise RunContextError("requested input role/index is not staged")
        binding = matches[index]
        limit = binding.size_bytes if maximum_bytes is None else maximum_bytes
        if limit < 0 or binding.size_bytes > limit:
            raise RunContextError("input exceeds the requested read bound")
        if binding.path.is_symlink():
            raise RunContextError("input must be a regular read-only staged file")
        path = binding.path.resolve(strict=True)
        if not path.is_file():
            raise RunContextError("input must be a regular read-only staged file")
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(path, flags)
        try:
            details = os.fstat(descriptor)
            if not stat.S_ISREG(details.st_mode) or details.st_size != binding.size_bytes:
                raise RunContextError("staged input size changed")
            with os.fdopen(descriptor, "rb", closefd=False) as stream:
                payload = stream.read(limit + 1)
        finally:
            os.close(descriptor)
        if len(payload) != binding.size_bytes:
            raise RunContextError("staged input could not be read exactly")
        if hashlib.sha256(payload).hexdigest() != binding.sha256:
            raise RunContextError("staged input digest changed")
        return payload

    def temporary_path(self, relative_path: str) -> Path:
        self.raise_if_cancelled()
        relative = _safe_relative(relative_path)
        candidate = self._workspace_root.joinpath(*relative.parts)
        resolved = _within(self._workspace_root, candidate)
        resolved.parent.mkdir(parents=True, exist_ok=True)
        for parent in (resolved.parent, *resolved.parents):
            if parent == self._workspace_root:
                break
            if parent.is_symlink():
                raise OutputPolicyError("workspace path traverses a symlink")
        return resolved

    def write_output(
        self,
        *,
        role: str,
        media_type: str,
        schema_ref: str,
        data: bytes | bytearray | memoryview,
    ) -> StagedOutput:
        self.raise_if_cancelled()
        rule = self._rules.get(role)
        if rule is None:
            raise OutputPolicyError("output role was not declared by the Job Spec")
        if schema_ref != rule.schema_ref or media_type not in rule.media_types:
            raise OutputPolicyError("output media type or schema is not allowlisted")
        payload = bytes(data)
        if len(payload) > rule.max_bytes:
            raise OutputPolicyError("output exceeds its role size limit")
        if self._total_output + len(payload) > self._max_total:
            raise OutputPolicyError("outputs exceed the attempt total size limit")
        digest = hashlib.sha256(payload).hexdigest()
        ordinal = len(self._outputs) + 1
        safe_role = re.sub(r"[^a-zA-Z0-9_.-]", "_", role)
        path = self._output_root / f"{ordinal:04d}-{safe_role}-{digest}.bin"
        resolved = _within(self._output_root, path)
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(resolved, flags, 0o600)
        try:
            with os.fdopen(descriptor, "wb", closefd=False) as stream:
                stream.write(payload)
                stream.flush()
        finally:
            os.close(descriptor)
        staged = StagedOutput(
            role=role,
            media_type=media_type,
            schema_ref=schema_ref,
            staged_artifact=f"runner-output:{ordinal}:sha256:{digest}",
            sha256=digest,
            size_bytes=len(payload),
            path=resolved,
        )
        self._outputs.append(staged)
        self._total_output += len(payload)
        return staged

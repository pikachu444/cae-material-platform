from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest
from cmp_plugin_sdk import (
    CancellationRequested,
    DeadlineExceeded,
    ExtensionDescriptor,
    ExtensionType,
    OutputPolicyError,
    RunContext,
    RunnerJobSpec,
)
from cmp_plugin_sdk.context import InputBinding, OutputRule
from cmp_plugin_sdk.tck import ALL_EXTENSION_TYPES, check_extension_matrix

PROJECT_ROOT = Path(__file__).parents[3]
ARTIFACT_ID = UUID("84000000-0000-4000-8000-000000000001")


def _job() -> RunnerJobSpec:
    document = json.loads(
        (PROJECT_ROOT / "contracts/examples/positive/job-spec.json").read_text(
            encoding="utf-8"
        )
    )
    return RunnerJobSpec.from_validated_document(document)


def _context(
    tmp_path: Path,
    *,
    job: RunnerJobSpec | None = None,
    inputs: tuple[InputBinding, ...] = (),
    clock: Callable[[], datetime] | None = None,
) -> RunContext:
    output = tmp_path / "outputs"
    workspace = tmp_path / "workspace"
    output.mkdir(parents=True)
    workspace.mkdir(parents=True)
    return RunContext(
        job=job or _job(),
        inputs=inputs,
        output_rules=(
            OutputRule(
                "processed-dataset",
                "urn:cmp:schema:dataset:1.0.0",
                ("application/octet-stream",),
                16,
            ),
        ),
        output_root=output,
        workspace_root=workspace,
        cancellation_marker=workspace / "cancel.requested",
        max_total_output_bytes=16,
        clock=clock,
    )


def test_tck_requires_each_synthetic_extension_type_exactly_once() -> None:
    descriptors = tuple(
        ExtensionDescriptor(extension_type, ("contract_echo",))
        for extension_type in sorted(ALL_EXTENSION_TYPES, key=str)
    )

    assert check_extension_matrix(descriptors).passed
    assert set(ALL_EXTENSION_TYPES) == set(ExtensionType)
    assert not check_extension_matrix(descriptors[:-1]).passed


def test_run_context_rehashes_read_only_input_and_bounds_output(tmp_path: Path) -> None:
    payload = b"immutable-input"
    input_path = tmp_path / "input.bin"
    input_path.write_bytes(payload)
    binding = InputBinding(
        "dataset",
        ARTIFACT_ID,
        hashlib.sha256(payload).hexdigest(),
        "application/octet-stream",
        input_path,
        len(payload),
    )
    context = _context(tmp_path, inputs=(binding,))

    assert context.read_input("dataset") == payload
    staged = context.write_output(
        role="processed-dataset",
        media_type="application/octet-stream",
        schema_ref="urn:cmp:schema:dataset:1.0.0",
        data=b"bounded",
    )
    assert staged.path.read_bytes() == b"bounded"
    assert staged.staged_artifact.endswith(staged.sha256)

    input_path.write_bytes(b"mutable-input")
    with pytest.raises(Exception, match=r"size changed|digest changed"):
        context.read_input("dataset")
    with pytest.raises(OutputPolicyError, match="size limit"):
        context.write_output(
            role="processed-dataset",
            media_type="application/octet-stream",
            schema_ref="urn:cmp:schema:dataset:1.0.0",
            data=b"x" * 17,
        )


def test_run_context_rng_is_deterministic_and_paths_cannot_escape(tmp_path: Path) -> None:
    first = _context(tmp_path / "first")
    second = _context(tmp_path / "second")

    assert [first.rng.getrandbits(64) for _ in range(3)] == [
        second.rng.getrandbits(64) for _ in range(3)
    ]
    assert first.temporary_path("nested/work.bin").is_relative_to(
        tmp_path / "first" / "workspace"
    )
    with pytest.raises(OutputPolicyError, match="safe relative path"):
        first.temporary_path("../escape")


def test_run_context_exposes_cooperative_cancel_and_immutable_deadline(
    tmp_path: Path,
) -> None:
    cancelled = _context(tmp_path / "cancelled")
    (tmp_path / "cancelled" / "workspace" / "cancel.requested").touch()
    with pytest.raises(CancellationRequested):
        cancelled.raise_if_cancelled()

    job = _job()
    expired = _context(
        tmp_path / "expired",
        job=job,
        clock=lambda: datetime.fromtimestamp(job.deadline.timestamp(), UTC),
    )
    with pytest.raises(DeadlineExceeded):
        expired.raise_if_cancelled()

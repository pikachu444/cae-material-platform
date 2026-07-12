"""Standalone JSON/file protocol runner used only inside a subprocess or container."""

from __future__ import annotations

import argparse
import importlib
import inspect
import json
import platform
import re
import sys
import time
import tracemalloc
from collections.abc import Sequence
from datetime import UTC, datetime
from importlib.resources import files
from pathlib import Path
from typing import Any, cast
from uuid import UUID

from jsonschema import Draft202012Validator, FormatChecker

from cmp_plugin_sdk.context import (
    CancellationRequested,
    DeadlineExceeded,
    InputBinding,
    OutputPolicyError,
    OutputRule,
    RunContext,
    RunContextError,
)
from cmp_plugin_sdk.guards import DevelopmentSandboxViolation, install_development_guards
from cmp_plugin_sdk.model import (
    Diagnostic,
    DiagnosticSeverity,
    ExtensionOutcome,
    ExtensionStatus,
    ExtensionType,
    PluginExtension,
    RunnerJobSpec,
    ValidationReport,
)
from cmp_plugin_sdk.tck import check_declared_descriptor

_ENTRYPOINT = re.compile(
    r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*:"
    r"[A-Za-z_][A-Za-z0-9_]*$"
)
_SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")
_MAX_CONTROL_DOCUMENT = 4 * 1024 * 1024


def _json_object(path: Path, *, maximum_bytes: int = _MAX_CONTROL_DOCUMENT) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise ValueError("runner control document must be a regular file")
    if path.stat().st_size > maximum_bytes:
        raise ValueError("runner control document exceeds its size limit")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("runner control document must be a JSON object")
    return cast(dict[str, Any], value)


def _validator(name: str) -> Draft202012Validator:
    resource = files("cmp_plugin_sdk.contracts").joinpath(name)
    schema = json.loads(resource.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def _validate_job(document: object) -> None:
    errors = sorted(_validator("job-spec.schema.json").iter_errors(document), key=str)
    if errors:
        raise ValueError("Job Spec does not satisfy runner contract 1.0")


def _policy_values(policy: dict[str, Any]) -> tuple[dict[str, Any], list[Any], list[Any]]:
    if (
        policy.get("runner_protocol_version") != "1.0"
        or policy.get("network") != "none"
        or policy.get("non_production") is not True
    ):
        raise ValueError("runner policy version or network policy is invalid")
    package = policy.get("package")
    inputs = policy.get("inputs")
    outputs = policy.get("outputs")
    if not isinstance(package, dict) or not isinstance(inputs, list) or not isinstance(
        outputs, list
    ):
        raise ValueError("runner policy package/input/output sections are required")
    return cast(dict[str, Any], package), inputs, outputs


def _load_extension(entrypoint: str, package_root: Path) -> PluginExtension:
    if _ENTRYPOINT.fullmatch(entrypoint) is None:
        raise ValueError("plugin entrypoint is not a safe module:attribute reference")
    module_name, attribute = entrypoint.split(":", maxsplit=1)
    sys.path.insert(0, str(package_root))
    module = importlib.import_module(module_name)
    target = getattr(module, attribute)
    extension = target() if inspect.isclass(target) else target
    for method in ("describe", "validate_job", "run"):
        if not callable(getattr(extension, method, None)):
            raise ValueError("plugin entrypoint does not implement SDK API 1.0")
    return cast(PluginExtension, extension)


def _inputs(values: list[Any], input_root: Path) -> tuple[InputBinding, ...]:
    bindings: list[InputBinding] = []
    for raw in values:
        if not isinstance(raw, dict):
            raise ValueError("runner input binding must be an object")
        file_name = raw.get("file_name")
        if (
            not isinstance(file_name, str)
            or Path(file_name).name != file_name
            or file_name in {".", ".."}
        ):
            raise ValueError("runner input binding file name is invalid")
        bindings.append(
            InputBinding(
                role=str(raw["role"]),
                artifact_id=UUID(str(raw["artifact_id"])),
                sha256=str(raw["sha256"]),
                media_type=str(raw["media_type"]),
                path=input_root / file_name,
                size_bytes=int(raw["size_bytes"]),
            )
        )
    return tuple(bindings)


def _outputs(values: list[Any]) -> tuple[OutputRule, ...]:
    rules: list[OutputRule] = []
    for raw in values:
        if not isinstance(raw, dict) or not isinstance(raw.get("media_types"), list):
            raise ValueError("runner output policy must be an object")
        rules.append(
            OutputRule(
                role=str(raw["role"]),
                schema_ref=str(raw["schema_ref"]),
                media_types=tuple(str(item) for item in raw["media_types"]),
                max_bytes=int(raw["max_bytes"]),
            )
        )
    return tuple(rules)


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _diagnostic(code: str, message: str) -> Diagnostic:
    return Diagnostic(code, DiagnosticSeverity.ERROR, message)


def _execute(
    *,
    job_path: Path,
    policy_path: Path,
    package_root: Path,
    input_root: Path,
    output_root: Path,
    workspace_root: Path,
    result_path: Path,
) -> int:
    job_document = _json_object(job_path)
    policy = _json_object(policy_path)
    _validate_job(job_document)
    package, input_values, output_values = _policy_values(policy)
    job = RunnerJobSpec.from_validated_document(job_document)
    if (
        job.plugin_id != package.get("plugin_id")
        or job.plugin_version != package.get("plugin_version")
        or job.package_digest != package.get("package_digest")
        or job.extension_type.value != package.get("extension_type")
    ):
        raise ValueError("Job Spec extension identity differs from the execution package")
    entrypoint = str(package.get("entrypoint", ""))
    capabilities_value = package.get("capabilities")
    dependency_lock_digest = package.get("dependency_lock_digest")
    if (
        not isinstance(capabilities_value, list)
        or not isinstance(dependency_lock_digest, str)
        or _SHA256.fullmatch(dependency_lock_digest) is None
    ):
        raise ValueError("package capabilities or dependency lock digest is invalid")
    capabilities = tuple(str(item) for item in capabilities_value)
    bindings = _inputs(input_values, input_root)
    rules = _outputs(output_values)
    max_total = int(policy["max_total_output_bytes"])
    hardware_summary = str(policy.get("hardware_summary") or platform.machine() or "unknown")

    install_development_guards(
        package_root=package_root,
        input_root=input_root,
        output_root=output_root,
        workspace_root=workspace_root,
    )
    started = datetime.now(UTC)
    started_monotonic = time.perf_counter()
    tracemalloc.start()
    context = RunContext(
        job=job,
        inputs=bindings,
        output_rules=rules,
        output_root=output_root,
        workspace_root=workspace_root,
        cancellation_marker=workspace_root / "cancel.requested",
        max_total_output_bytes=max_total,
    )
    diagnostics: list[Diagnostic] = []
    status = ExtensionStatus.FAILED
    try:
        extension = _load_extension(entrypoint, package_root)
        descriptor = extension.describe()
        tck = check_declared_descriptor(
            descriptor,
            expected_type=ExtensionType(str(package["extension_type"])),
            declared_capabilities=capabilities,
        )
        if not tck.passed:
            diagnostics.append(
                _diagnostic(
                    "CMP-RUNNER-0002",
                    "Runtime descriptor differs from the immutable package manifest.",
                )
            )
        else:
            report = extension.validate_job(job)
            if not isinstance(report, ValidationReport):
                raise TypeError("validate_job must return ValidationReport")
            diagnostics.extend(report.diagnostics)
            if report.accepted:
                context.raise_if_cancelled()
                outcome = extension.run(context, job)
                if not isinstance(outcome, ExtensionOutcome):
                    raise TypeError("run must return ExtensionOutcome")
                context.raise_if_cancelled()
                status = outcome.status
                diagnostics.extend(outcome.diagnostics)
            else:
                status = ExtensionStatus.FAILED
    except CancellationRequested:
        status = ExtensionStatus.CANCELLED
        diagnostics.append(_diagnostic("CMP-RUNNER-0003", "Execution was cancelled."))
    except DeadlineExceeded:
        status = ExtensionStatus.TIMED_OUT
        diagnostics.append(_diagnostic("CMP-RUNNER-0004", "Execution deadline elapsed."))
    except (DevelopmentSandboxViolation, OutputPolicyError, RunContextError):
        status = ExtensionStatus.FAILED
        diagnostics.append(
            _diagnostic(
                "CMP-RUNNER-0005",
                "Plugin attempted an operation outside its execution policy.",
            )
        )
    except Exception:
        status = ExtensionStatus.FAILED
        diagnostics.append(
            _diagnostic(
                "CMP-RUNNER-0001",
                "Plugin raised an unhandled exception; details were suppressed.",
            )
        )
    diagnostics.extend(context.diagnostics)
    _, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    ended = datetime.now(UTC)
    wall_time = max(0.0, time.perf_counter() - started_monotonic)
    manifest: dict[str, Any] = {
        "result_manifest_version": "1.0",
        "job_id": str(job.job_id),
        "attempt_id": str(job.attempt_id),
        "status": status.value,
        "started_at": _iso(started),
        "ended_at": _iso(ended),
        "outputs": [item.manifest_entry() for item in context.outputs],
        "diagnostics": [item.document() for item in diagnostics],
        "metrics": {
            "wall_time_s": wall_time,
            "peak_memory_mb": peak_bytes / (1024 * 1024),
        },
        "reproducibility": {
            "package_digest": job.package_digest,
            "dependency_lock_digest": dependency_lock_digest,
            "seed": job.seed,
            "hardware_summary": hardware_summary,
        },
        "non_production": True,
    }
    result_validator = _validator("result-manifest.schema.json")
    if list(result_validator.iter_errors(manifest)):
        raise ValueError("runner generated an invalid Result Manifest")
    payload = json.dumps(
        manifest,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    if len(payload.encode("utf-8")) > _MAX_CONTROL_DOCUMENT:
        raise ValueError("Result Manifest exceeds its size limit")
    result_path.write_text(payload, encoding="utf-8")
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run one isolated CMP plugin attempt.")
    parser.add_argument("--job-spec", type=Path, required=True)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--package-root", type=Path, required=True)
    parser.add_argument("--input-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--workspace-root", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        return _execute(
            job_path=args.job_spec.resolve(strict=True),
            policy_path=args.policy.resolve(strict=True),
            package_root=args.package_root.resolve(strict=True),
            input_root=args.input_root.resolve(strict=True),
            output_root=args.output_root.resolve(strict=True),
            workspace_root=args.workspace_root.resolve(strict=True),
            result_path=args.result.resolve(strict=False),
        )
    except Exception:
        print("CMP-RUNNER-BOOTSTRAP-FAILED", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

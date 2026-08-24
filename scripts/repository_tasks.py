from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
CONTAINER_MARKER = "container_service"
POSTGRES_DSN_ENV = "CMP_TEST_POSTGRES_DSN"
_CANCEL_GRACE_SECONDS = 5.0


class TaskConfigurationError(ValueError):
    """Raised when the requested task scope cannot be executed safely."""


class TaskCancelled(Exception):
    """Raised after the active child process group has been stopped."""


@dataclass(frozen=True, slots=True)
class CommandResult:
    returncode: int
    stdout: str = ""
    stderr: str = ""


@dataclass(frozen=True, slots=True)
class TaskStep:
    step_id: str
    argv: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class TestScope:
    mode: str
    marker_expression: str | None


def _task_environment() -> dict[str, str]:
    environment = dict(os.environ)
    environment.setdefault("UV_LINK_MODE", "copy")
    return environment


def _resolved_root(value: Path) -> Path:
    root = value.resolve()
    missing = [name for name in ("pyproject.toml", "package.json") if not (root / name).is_file()]
    if missing:
        raise TaskConfigurationError(
            f"repository root {root} is missing required files: {', '.join(missing)}"
        )
    return root


def _test_scope(
    *, host_only: bool, require_container_tests: bool, environment: dict[str, str]
) -> TestScope:
    if host_only and require_container_tests:
        raise TaskConfigurationError(
            "--host-only and --require-container-tests cannot be used together"
        )
    if host_only:
        return TestScope("host-only", f"not {CONTAINER_MARKER}")
    if require_container_tests:
        if not environment.get(POSTGRES_DSN_ENV):
            raise TaskConfigurationError(
                f"--require-container-tests requires {POSTGRES_DSN_ENV}"
            )
        return TestScope("all", None)
    if environment.get(POSTGRES_DSN_ENV):
        return TestScope("all", None)
    return TestScope("host-only", f"not {CONTAINER_MARKER}")


def _ci_steps(scope: TestScope) -> tuple[TaskStep, ...]:
    uv = "uv"
    pytest_argv: tuple[str, ...] = (uv, "run", "pytest")
    if scope.marker_expression is not None:
        pytest_argv = (*pytest_argv, "-m", scope.marker_expression)
    return (
        TaskStep("python-sync", (uv, "sync", "--all-groups", "--locked")),
        TaskStep(
            "development-environment",
            (uv, "run", "python", "scripts/check_development_environment.py"),
        ),
        TaskStep("ruff", (uv, "run", "ruff", "check", ".")),
        TaskStep("mypy", (uv, "run", "mypy", "--no-incremental")),
        TaskStep(
            "architecture",
            (uv, "run", "cmp-check-architecture", "--root", "backend/src"),
        ),
        TaskStep(
            "contract-lint",
            (uv, "run", "cmp-check-contracts", "lint", "--root", "."),
        ),
        TaskStep(
            "contract-compat",
            (
                uv,
                "run",
                "cmp-check-contracts",
                "compat",
                "--baseline",
                "contracts/http/openapi.baseline.yaml",
                "--current",
                "contracts/http/openapi.yaml",
            ),
        ),
        TaskStep("user-guide", (uv, "run", "cmp-check-user-guide", "--root", ".")),
        TaskStep(
            "docs-impact",
            (uv, "run", "cmp-check-doc-impact", "--root", ".", "--mode", "range"),
        ),
        TaskStep("pytest", pytest_argv),
        TaskStep(
            "npm-install",
            ("npm", "ci", "--workspaces", "--include-workspace-root"),
        ),
        TaskStep("npm-check", ("npm", "run", "check")),
    )


def _popen(
    argv: Sequence[str],
    *,
    cwd: Path,
    environment: dict[str, str],
    capture: bool,
) -> subprocess.Popen[str]:
    creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    return subprocess.Popen(
        list(argv),
        cwd=str(cwd),
        env=environment,
        stdin=None,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
        text=True,
        shell=False,
        start_new_session=os.name != "nt",
        creationflags=creationflags,
    )


def _wait_after_signal(process: subprocess.Popen[str]) -> bool:
    try:
        process.wait(timeout=_CANCEL_GRACE_SECONDS)
    except subprocess.TimeoutExpired:
        return False
    return True


def _signal_posix_group(process: subprocess.Popen[str], value: int) -> None:
    killpg = vars(os)["killpg"]
    try:
        killpg(process.pid, value)
    except ProcessLookupError:
        pass


def _cancel_process_group(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        break_event = getattr(signal, "CTRL_BREAK_EVENT", signal.SIGTERM)
        try:
            process.send_signal(break_event)
        except OSError:
            process.terminate()
        if _wait_after_signal(process):
            return
        process.terminate()
        if _wait_after_signal(process):
            return
        process.kill()
        process.wait()
        return

    _signal_posix_group(process, signal.SIGINT)
    if _wait_after_signal(process):
        return
    _signal_posix_group(process, signal.SIGTERM)
    if _wait_after_signal(process):
        return
    _signal_posix_group(process, getattr(signal, "SIGKILL", 9))
    process.wait()


def _execute_command(
    argv: Sequence[str],
    *,
    cwd: Path,
    environment: dict[str, str],
    capture: bool = False,
) -> CommandResult:
    process = _popen(argv, cwd=cwd, environment=environment, capture=capture)
    try:
        if capture:
            stdout, stderr = process.communicate()
            return CommandResult(process.returncode, stdout, stderr)
        return CommandResult(process.wait())
    except KeyboardInterrupt as exc:
        _cancel_process_group(process)
        raise TaskCancelled from exc


def _node_ids(output: str) -> tuple[str, ...]:
    return tuple(
        line.strip()
        for line in output.splitlines()
        if "::" in line and not line.lstrip().startswith(("=", "<"))
    )


def _collect_marker_node_ids(
    expression: str,
    *,
    root: Path,
    environment: dict[str, str],
) -> tuple[str, ...]:
    argv = (
        "uv",
        "run",
        "pytest",
        "--collect-only",
        "-q",
        "-p",
        "no:cacheprovider",
        "-m",
        expression,
        "tests/integration",
    )
    result = _execute_command(argv, cwd=root, environment=environment, capture=True)
    if result.returncode not in {0, 5}:
        detail = (result.stderr or result.stdout).strip()
        raise TaskConfigurationError(
            f"pytest marker collection failed for {expression!r} "
            f"with exit {result.returncode}: {detail}"
        )
    return _node_ids(result.stdout)


def _marker_inventory(*, root: Path, environment: dict[str, str]) -> int:
    container_items = _collect_marker_node_ids(
        CONTAINER_MARKER, root=root, environment=environment
    )
    if not container_items:
        raise TaskConfigurationError(
            f"pytest marker {CONTAINER_MARKER!r} collected zero tests"
        )
    drift = _collect_marker_node_ids(
        f"postgresql and not {CONTAINER_MARKER}",
        root=root,
        environment=environment,
    )
    if drift:
        preview = ", ".join(drift[:3])
        raise TaskConfigurationError(
            f"pytest marker drift: {len(drift)} postgresql tests lack "
            f"{CONTAINER_MARKER}: {preview}"
        )
    return len(container_items)


def _exit_code(returncode: int) -> int:
    return returncode if returncode >= 0 else 128 + abs(returncode)


def run_ci(
    *,
    root: Path,
    host_only: bool,
    require_container_tests: bool,
) -> int:
    resolved_root = _resolved_root(root)
    environment = _task_environment()
    scope = _test_scope(
        host_only=host_only,
        require_container_tests=require_container_tests,
        environment=environment,
    )
    steps = _ci_steps(scope)
    for index, step in enumerate(steps, start=1):
        if step.step_id == "pytest":
            count = _marker_inventory(root=resolved_root, environment=environment)
            excluded = count if scope.mode == "host-only" else 0
            included = count if scope.mode == "all" else 0
            print(
                "[repository-tasks] TEST_SCOPE "
                f"mode={scope.mode} marker={CONTAINER_MARKER} "
                f"selected={count} included={included} excluded={excluded}",
                flush=True,
            )
        command = json.dumps(step.argv, ensure_ascii=False)
        print(
            f"[repository-tasks] START {index:02d}/{len(steps):02d} "
            f"step={step.step_id} argv={command}",
            flush=True,
        )
        started = time.monotonic()
        result = _execute_command(
            step.argv,
            cwd=resolved_root,
            environment=environment,
        )
        duration = time.monotonic() - started
        if result.returncode:
            code = _exit_code(result.returncode)
            print(
                f"[repository-tasks] FAIL step={step.step_id} "
                f"exit={code} duration_seconds={duration:.3f}",
                file=sys.stderr,
                flush=True,
            )
            return code
        print(
            f"[repository-tasks] PASS step={step.step_id} "
            f"duration_seconds={duration:.3f}",
            flush=True,
        )
    print("[repository-tasks] PASS task=ci", flush=True)
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run cross-platform repository tasks.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    ci = subparsers.add_parser("ci", help="Run the authoritative repository CI sequence.")
    ci.add_argument("--root", type=Path, default=REPOSITORY_ROOT)
    ci.add_argument("--host-only", action="store_true")
    ci.add_argument("--require-container-tests", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "ci":
            return run_ci(
                root=args.root,
                host_only=args.host_only,
                require_container_tests=args.require_container_tests,
            )
    except TaskCancelled:
        print("[repository-tasks] CANCELLED task=ci exit=130", file=sys.stderr, flush=True)
        return 130
    except FileNotFoundError as exc:
        executable = exc.filename or "<unknown>"
        print(
            f"[repository-tasks] ERROR missing executable={executable} exit=127",
            file=sys.stderr,
            flush=True,
        )
        return 127
    except OSError as exc:
        print(f"[repository-tasks] ERROR operating-system failure: {exc}", file=sys.stderr)
        return 126
    except TaskConfigurationError as exc:
        print(f"[repository-tasks] ERROR {exc}", file=sys.stderr, flush=True)
        return 2
    raise AssertionError(f"unsupported command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())

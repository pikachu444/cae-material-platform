from __future__ import annotations

import argparse
import json
import os
import re
import shutil
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
CI_MODES = ("full", "frontend", "docs")
CI_EVENTS = ("pull_request", "schedule", "workflow_dispatch")
_FULL_PATH_PREFIXES = (
    ".codex/hooks/",
    ".github/",
    ".githooks/",
    "backend/",
    "contracts/",
    "deploy/",
    "generated/",
    "plugins/",
    "sdk/",
    "tests/",
)
_FULL_ROOT_PATHS = frozenset(
    {
        ".dockerignore",
        ".env.example",
        ".gitattributes",
        ".gitignore",
        ".node-version",
        ".python-version",
        "Makefile",
        "alembic.ini",
        "pnpm-workspace.yaml",
        "pyproject.toml",
        "skills-lock.json",
        "uv.lock",
    }
)
_FRONTEND_ROOT_PATHS = frozenset({"package.json", "package-lock.json"})
_FRONTEND_SCRIPT_PATHS = frozenset(
    {
        "scripts/check_frontend_guard.mjs",
        "scripts/check_frontend_guard.test.mjs",
        "scripts/check_web_bundle.mjs",
        "scripts/check_web_bundle.test.mjs",
        "scripts/fixtures/modeling_route_fixture.mjs",
        "scripts/measure_modeling_route.mjs",
        "scripts/measure_modeling_route.test.mjs",
    }
)
_DOCS_ROOT_PATHS = frozenset(
    {"AGENTS.md", "DEVELOPMENT.md", "IMPLEMENTATION_STATUS.md", "README.md"}
)
_AGENT_DOCUMENT_SUFFIXES = frozenset({".md", ".txt", ".yaml", ".yml"})
_DOCS_CONTRACT_TESTS = (
    "tests/contracts/test_agent_guidance.py",
    "tests/contracts/test_documentation_impact.py",
    "tests/contracts/test_documentation_routing.py",
    "tests/contracts/test_pre_publish.py",
    "tests/contracts/test_user_guide.py",
)
_FRONTEND_CONTRACT_TESTS = (
    *_DOCS_CONTRACT_TESTS[:4],
    "tests/contracts/test_repository_tasks.py",
    _DOCS_CONTRACT_TESTS[4],
)
_SHA_PATTERN = re.compile(r"[0-9a-fA-F]{40}")


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


@dataclass(frozen=True, slots=True)
class ChangedPath:
    path: str
    mode: str
    reason: str


@dataclass(frozen=True, slots=True)
class ChangePlan:
    event_name: str
    mode: str
    base_sha: str
    head_sha: str
    changed_paths: tuple[ChangedPath, ...]
    reason: str


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


def _full_ci_steps(scope: TestScope) -> tuple[TaskStep, ...]:
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


def _frontend_ci_steps() -> tuple[TaskStep, ...]:
    uv = "uv"
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
        TaskStep("pytest", (uv, "run", "pytest", *_FRONTEND_CONTRACT_TESTS)),
        TaskStep(
            "npm-install",
            ("npm", "ci", "--workspaces", "--include-workspace-root"),
        ),
        TaskStep("npm-check", ("npm", "run", "check")),
        TaskStep(
            "npm-bundle-tests",
            ("npm", "run", "test:bundle-budget", "--workspace", "@cmp/web"),
        ),
    )


def _docs_ci_steps() -> tuple[TaskStep, ...]:
    uv = "uv"
    return (
        TaskStep("python-sync", (uv, "sync", "--all-groups", "--locked")),
        TaskStep(
            "development-environment",
            (uv, "run", "python", "scripts/check_development_environment.py"),
        ),
        TaskStep("user-guide", (uv, "run", "cmp-check-user-guide", "--root", ".")),
        TaskStep(
            "docs-impact",
            (uv, "run", "cmp-check-doc-impact", "--root", ".", "--mode", "range"),
        ),
        TaskStep("pytest", (uv, "run", "pytest", *_DOCS_CONTRACT_TESTS)),
    )


def _ci_steps(scope: TestScope, ci_mode: str = "full") -> tuple[TaskStep, ...]:
    if ci_mode == "full":
        return _full_ci_steps(scope)
    if ci_mode == "frontend":
        return _frontend_ci_steps()
    if ci_mode == "docs":
        return _docs_ci_steps()
    raise TaskConfigurationError(f"unsupported CI mode: {ci_mode}")


def _popen(
    argv: Sequence[str],
    *,
    cwd: Path,
    environment: dict[str, str],
    capture: bool,
) -> subprocess.Popen[str]:
    creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    resolved = list(argv)
    executable = shutil.which(resolved[0], path=environment.get("PATH"))
    if executable is not None:
        resolved[0] = executable
    return subprocess.Popen(
        resolved,
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


def _git_bytes(root: Path, arguments: Sequence[str]) -> bytes:
    try:
        result = subprocess.run(
            ["git", *arguments],
            cwd=root,
            check=False,
            capture_output=True,
        )
    except OSError as error:
        raise TaskConfigurationError(f"cannot run git: {error}") from error
    if result.returncode:
        detail = (result.stderr or result.stdout).decode("utf-8", errors="replace").strip()
        rendered = " ".join(arguments)
        raise TaskConfigurationError(
            f"git {rendered} failed with exit {result.returncode}: {detail}"
        )
    return result.stdout


def _resolve_commit(root: Path, value: str, label: str) -> str:
    if _SHA_PATTERN.fullmatch(value) is None:
        raise TaskConfigurationError(f"{label} must be an explicit full Git SHA")
    output = _git_bytes(root, ("rev-parse", "--verify", f"{value}^{{commit}}"))
    try:
        resolved = output.decode("ascii").strip().lower()
    except UnicodeDecodeError as error:
        raise TaskConfigurationError(f"cannot resolve {label} as a Git commit") from error
    if _SHA_PATTERN.fullmatch(resolved) is None:
        raise TaskConfigurationError(f"cannot resolve {label} as a full Git commit SHA")
    return resolved


def _parse_changed_paths(output: bytes) -> tuple[str, ...]:
    try:
        decoded = output.decode("utf-8")
    except UnicodeDecodeError as error:
        raise TaskConfigurationError("changed paths are not valid UTF-8") from error
    if not decoded:
        return ()
    fields = decoded.split("\0")
    if fields[-1] != "":
        raise TaskConfigurationError("git changed-path output is not NUL terminated")
    fields.pop()
    paths: set[str] = set()
    index = 0
    while index < len(fields):
        status = fields[index]
        index += 1
        if not status or status[0] not in "ACMRTD":
            raise TaskConfigurationError(f"unsupported git change status: {status!r}")
        path_count = 2 if status[0] in "CR" else 1
        if index + path_count > len(fields):
            raise TaskConfigurationError("git changed-path output is incomplete")
        paths.update(fields[index : index + path_count])
        index += path_count
    return tuple(sorted(paths))


def _changed_paths(root: Path, base_sha: str, head_sha: str) -> tuple[str, ...]:
    output = _git_bytes(
        root,
        (
            "diff",
            "--name-status",
            "-z",
            "--find-renames",
            f"{base_sha}...{head_sha}",
        ),
    )
    return _parse_changed_paths(output)


def _is_agent_document(path: str) -> bool:
    pure = Path(path)
    suffix = pure.suffix.lower()
    return (
        pure.name == "AGENTS.md"
        or (
            path.startswith((".agents/", ".codex/skills/"))
            and suffix in _AGENT_DOCUMENT_SUFFIXES
        )
    )


def _classify_path(path: str) -> ChangedPath:
    if (
        not path
        or path.startswith("/")
        or "\\" in path
        or ".." in path.split("/")
        or "" in path.split("/")
    ):
        return ChangedPath(path, "full", "invalid-path")
    if path in _DOCS_ROOT_PATHS:
        return ChangedPath(path, "docs", "repository-guide")
    if path.startswith(("docs/", "adr/")):
        return ChangedPath(path, "docs", "documentation")
    if _is_agent_document(path):
        return ChangedPath(path, "docs", "agent-guidance")
    if path in _FULL_ROOT_PATHS or path.startswith(_FULL_PATH_PREFIXES):
        return ChangedPath(path, "full", "runtime-or-policy")
    if path in {"scripts/ci.sh", "scripts/repository_tasks.py"}:
        return ChangedPath(path, "full", "ci-task-runner")
    if path in _FRONTEND_ROOT_PATHS:
        return ChangedPath(path, "frontend", "npm-workspace")
    if path.startswith("apps/web/"):
        return ChangedPath(path, "frontend", "frontend")
    if path in _FRONTEND_SCRIPT_PATHS:
        return ChangedPath(path, "frontend", "frontend-guard-or-measurement")
    return ChangedPath(path, "full", "unknown-path")


def classify_changed_paths(paths: Sequence[str]) -> tuple[str, tuple[ChangedPath, ...], str]:
    classified = tuple(_classify_path(path) for path in sorted(set(paths)))
    if not classified:
        return "full", (), "empty-change-set"
    if any(item.mode == "full" for item in classified):
        return "full", classified, "full-or-unknown-path"
    if any(item.mode == "frontend" for item in classified):
        return "frontend", classified, "frontend-with-optional-documentation"
    return "docs", classified, "documentation-only"


def create_change_plan(
    *,
    root: Path,
    event_name: str,
    base_sha: str,
    head_sha: str,
) -> ChangePlan:
    resolved_root = _resolved_root(root)
    if event_name not in CI_EVENTS:
        raise TaskConfigurationError(f"unsupported CI event: {event_name}")
    resolved_base = _resolve_commit(resolved_root, base_sha, "base SHA")
    resolved_head = _resolve_commit(resolved_root, head_sha, "head SHA")
    if event_name != "pull_request":
        return ChangePlan(
            event_name=event_name,
            mode="full",
            base_sha=resolved_base,
            head_sha=resolved_head,
            changed_paths=(),
            reason="scheduled-or-manual-full",
        )
    mode, changed, reason = classify_changed_paths(
        _changed_paths(resolved_root, resolved_base, resolved_head)
    )
    return ChangePlan(
        event_name=event_name,
        mode=mode,
        base_sha=resolved_base,
        head_sha=resolved_head,
        changed_paths=changed,
        reason=reason,
    )


def _emit_change_plan(plan: ChangePlan, github_output: Path | None) -> None:
    print(
        "[repository-tasks] CHANGE_PLAN "
        f"event={plan.event_name} mode={plan.mode} base={plan.base_sha} "
        f"head={plan.head_sha} changed={len(plan.changed_paths)} reason={plan.reason}",
        flush=True,
    )
    for item in plan.changed_paths:
        rendered = json.dumps(item.path, ensure_ascii=True)
        print(
            "[repository-tasks] CHANGED_PATH "
            f"mode={item.mode} reason={item.reason} path={rendered}",
            flush=True,
        )
    if github_output is not None:
        try:
            with github_output.open("a", encoding="utf-8", newline="\n") as stream:
                stream.write(f"mode={plan.mode}\n")
        except OSError as error:
            raise TaskConfigurationError(
                f"cannot write GitHub Actions output {github_output}: {error}"
            ) from error


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
    ci_mode: str = "full",
) -> int:
    resolved_root = _resolved_root(root)
    if ci_mode not in CI_MODES:
        raise TaskConfigurationError(f"unsupported CI mode: {ci_mode}")
    environment = _task_environment()
    scope = _test_scope(
        host_only=host_only,
        require_container_tests=require_container_tests,
        environment=environment,
    )
    steps = _ci_steps(scope, ci_mode)
    print(
        "[repository-tasks] CI_MODE "
        f"mode={ci_mode} platform_scope={scope.mode} steps={len(steps)}",
        flush=True,
    )
    for index, step in enumerate(steps, start=1):
        if step.step_id == "pytest":
            count = _marker_inventory(root=resolved_root, environment=environment)
            include_containers = ci_mode == "full" and scope.mode == "all"
            included = count if include_containers else 0
            excluded = count - included
            print(
                "[repository-tasks] TEST_SCOPE "
                f"ci_mode={ci_mode} platform_scope={scope.mode} marker={CONTAINER_MARKER} "
                f"selected={count} included={included} excluded={excluded}",
                flush=True,
            )
            if ci_mode == "full":
                python_included = [
                    "full repository pytest"
                    if scope.mode == "all"
                    else f"full repository pytest filtered by not {CONTAINER_MARKER}"
                ]
                python_excluded = (
                    [] if scope.mode == "all" else [f"{CONTAINER_MARKER}:{count}"]
                )
            else:
                python_included = list(step.argv[3:])
                python_excluded = [
                    "unrelated full backend/repository pytest",
                    f"{CONTAINER_MARKER}:{count}",
                ]
            print(
                "[repository-tasks] TEST_SELECTION "
                f"included={json.dumps(python_included)} "
                f"excluded={json.dumps(python_excluded)}",
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
    ci.add_argument("--mode", choices=CI_MODES, default="full")
    ci.add_argument("--host-only", action="store_true")
    ci.add_argument("--require-container-tests", action="store_true")
    classify = subparsers.add_parser(
        "classify", help="Select a fail-closed CI mode from explicit Git commits."
    )
    classify.add_argument("--root", type=Path, default=REPOSITORY_ROOT)
    classify.add_argument("--event-name", choices=CI_EVENTS, required=True)
    classify.add_argument("--base-sha", required=True)
    classify.add_argument("--head-sha", required=True)
    classify.add_argument("--github-output", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "ci":
            return run_ci(
                root=args.root,
                host_only=args.host_only,
                require_container_tests=args.require_container_tests,
                ci_mode=args.mode,
            )
        if args.command == "classify":
            plan = create_change_plan(
                root=args.root,
                event_name=args.event_name,
                base_sha=args.base_sha,
                head_sha=args.head_sha,
            )
            _emit_change_plan(plan, args.github_output)
            return 0
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

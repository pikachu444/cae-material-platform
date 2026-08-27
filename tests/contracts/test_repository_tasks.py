from __future__ import annotations

import hashlib
import json
import signal
import subprocess
import sys
from collections.abc import Sequence
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from typing import cast

import pytest
from cmp.shared.domain.revisions import canonical_json_bytes
from pytest import CaptureFixture, MonkeyPatch

ROOT = Path(__file__).parents[2]
SCRIPT = ROOT / "scripts" / "repository_tasks.py"

_SPEC = spec_from_file_location("repository_tasks", SCRIPT)
assert _SPEC and _SPEC.loader
tasks = module_from_spec(_SPEC)
sys.modules[_SPEC.name] = tasks
_SPEC.loader.exec_module(tasks)


@pytest.mark.parametrize(
    ("paths", "expected"),
    [
        (["docs/user-guide/index.md"], "docs"),
        (["adr/README.md", "AGENTS.md", "IMPLEMENTATION_STATUS.md"], "docs"),
        (["apps/web/AGENTS.md", ".agents/skills/webapp-testing/SKILL.md"], "docs"),
        (["apps/web/src/app.tsx"], "frontend"),
        (["package.json", "package-lock.json"], "frontend"),
        (
            [
                "scripts/check_frontend_guard.mjs",
                "scripts/check_web_bundle.test.mjs",
                "scripts/fixtures/modeling_route_fixture.mjs",
                "scripts/measure_modeling_route.mjs",
                "docs/README.md",
            ],
            "frontend",
        ),
        (["apps/web/src/app.tsx", "backend/src/cmp/apps/api.py"], "full"),
        (["docs/README.md", "contracts/http/openapi.yaml"], "full"),
        ([".github/workflows/ci.yml"], "full"),
        (["scripts/repository_tasks.py"], "full"),
        (["pyproject.toml", "uv.lock"], "full"),
        (["backend/migrations/versions/001.py"], "full"),
        (["sdk/python/src/cmp_plugin_sdk/runner.py"], "full"),
        (["tests/contracts/test_repository_tasks.py"], "full"),
        (["pnpm-workspace.yaml"], "full"),
        (["unknown-root-file.txt"], "full"),
        ([], "full"),
    ],
)
def test_changed_path_classifier_is_deterministic_and_fail_closed(
    paths: list[str], expected: str
) -> None:
    mode, classified, _reason = tasks.classify_changed_paths(paths)

    assert mode == expected
    assert [item.path for item in classified] == sorted(set(paths))


def test_changed_path_parser_keeps_both_rename_paths() -> None:
    assert tasks._parse_changed_paths(
        b"R100\0docs/old.md\0apps/web/new.ts\0M\0README.md\0"
    ) == ("README.md", "apps/web/new.ts", "docs/old.md")


@pytest.mark.parametrize("status", ("U", "X", "B"))
def test_changed_path_parser_rejects_unsupported_git_statuses(status: str) -> None:
    with pytest.raises(tasks.TaskConfigurationError, match="unsupported git change status"):
        tasks._parse_changed_paths(f"{status}\0docs/README.md\0".encode())


def test_changed_path_collection_does_not_filter_unknown_git_statuses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: tuple[str, ...] = ()

    def fake_git_bytes(_root: Path, arguments: tuple[str, ...]) -> bytes:
        nonlocal observed
        observed = arguments
        return b"U\0docs/README.md\0"

    monkeypatch.setattr(tasks, "_git_bytes", fake_git_bytes)

    with pytest.raises(tasks.TaskConfigurationError, match="unsupported git change status"):
        tasks._changed_paths(ROOT, "a" * 40, "b" * 40)

    assert not any(argument.startswith("--diff-filter") for argument in observed)


def test_all_explicit_frontend_scripts_remain_frontend_only() -> None:
    mode, classified, _reason = tasks.classify_changed_paths(
        list(tasks._FRONTEND_SCRIPT_PATHS)
    )

    assert mode == "frontend"
    assert {item.path for item in classified} == tasks._FRONTEND_SCRIPT_PATHS


def test_change_plan_requires_explicit_resolvable_base_sha() -> None:
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    with pytest.raises(tasks.TaskConfigurationError, match="explicit full Git SHA"):
        tasks.create_change_plan(
            root=ROOT,
            event_name="pull_request",
            base_sha="origin/main",
            head_sha=head,
        )
    with pytest.raises(tasks.TaskConfigurationError, match="git rev-parse"):
        tasks.create_change_plan(
            root=ROOT,
            event_name="pull_request",
            base_sha="f" * 40,
            head_sha=head,
        )


@pytest.mark.parametrize("event_name", ("schedule", "workflow_dispatch"))
def test_scheduled_and_manual_plans_are_always_full(event_name: str) -> None:
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    plan = tasks.create_change_plan(
        root=ROOT,
        event_name=event_name,
        base_sha=head,
        head_sha=head,
    )

    assert plan.mode == "full"
    assert plan.changed_paths == ()
    assert plan.reason == "scheduled-or-manual-full"


def test_change_plan_output_is_visible_and_exports_only_the_mode(
    tmp_path: Path, capsys: CaptureFixture[str]
) -> None:
    output = tmp_path / "github-output.txt"
    plan = tasks.ChangePlan(
        event_name="pull_request",
        mode="frontend",
        base_sha="a" * 40,
        head_sha="b" * 40,
        changed_paths=(
            tasks.ChangedPath("apps/web/src/app.tsx", "frontend", "frontend"),
        ),
        reason="frontend-with-optional-documentation",
    )

    tasks._emit_change_plan(plan, output)

    logs = capsys.readouterr().out
    assert "event=pull_request mode=frontend" in logs
    assert f"base={'a' * 40} head={'b' * 40}" in logs
    assert 'path="apps/web/src/app.tsx"' in logs
    assert output.read_text(encoding="utf-8") == "mode=frontend\n"


def test_ci_registry_keeps_the_linux_sequence_and_host_filter_exact() -> None:
    full = tasks._ci_steps(tasks.TestScope("all", None))
    host = tasks._ci_steps(
        tasks.TestScope("host-only", f"not {tasks.CONTAINER_MARKER}")
    )

    assert [step.step_id for step in full] == [
        "python-sync",
        "development-environment",
        "ruff",
        "mypy",
        "architecture",
        "contract-lint",
        "contract-compat",
        "user-guide",
        "docs-impact",
        "pytest",
        "npm-install",
        "npm-check",
    ]
    assert full[9].argv == ("uv", "run", "pytest")
    assert host[9].argv == (
        "uv",
        "run",
        "pytest",
        "-m",
        "not container_service",
    )
    assert full[:9] == host[:9]
    assert full[10:] == host[10:]


def test_frontend_and_docs_registries_have_exact_bounded_scopes() -> None:
    scope = tasks.TestScope("host-only", f"not {tasks.CONTAINER_MARKER}")
    frontend = tasks._ci_steps(scope, "frontend")
    docs = tasks._ci_steps(scope, "docs")

    assert [step.step_id for step in frontend] == [
        "python-sync",
        "development-environment",
        "ruff",
        "mypy",
        "architecture",
        "contract-lint",
        "contract-compat",
        "user-guide",
        "docs-impact",
        "pytest",
        "npm-install",
        "npm-check",
        "npm-bundle-tests",
    ]
    assert frontend[9].argv == ("uv", "run", "pytest", *tasks._FRONTEND_CONTRACT_TESTS)
    assert frontend[-1].argv == (
        "npm",
        "run",
        "test:bundle-budget",
        "--workspace",
        "@cmp/web",
    )
    assert [step.step_id for step in docs] == [
        "python-sync",
        "development-environment",
        "user-guide",
        "docs-impact",
        "pytest",
    ]
    assert docs[-1].argv == ("uv", "run", "pytest", *tasks._DOCS_CONTRACT_TESTS)
    assert not any(step.argv[0] == "npm" for step in docs)


def test_make_and_bash_are_thin_wrappers_for_the_same_cli() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    script = (ROOT / "scripts/ci.sh").read_text(encoding="utf-8")

    assert "$(UV) run python scripts/repository_tasks.py ci" in makefile
    assert "bash scripts/ci.sh" not in makefile
    assert "exec uv run python scripts/repository_tasks.py ci \"$@\"" in script
    for duplicated in ("ruff check", "mypy --no-incremental", "npm ci", "uv sync"):
        assert duplicated not in script
    assert "/tmp" not in makefile
    assert "/tmp" not in script


def test_command_runner_resolves_windows_command_shims_from_the_task_environment(
    monkeypatch: MonkeyPatch,
) -> None:
    observed: dict[str, object] = {}

    monkeypatch.setattr(
        tasks.shutil,
        "which",
        lambda command, *, path: "C:\\pinned-node\\npm.cmd"
        if command == "npm" and path == "C:\\pinned-node"
        else None,
    )

    class FakeProcess:
        pass

    def popen(argv: Sequence[str], **kwargs: object) -> FakeProcess:
        observed["argv"] = tuple(argv)
        observed["kwargs"] = kwargs
        return FakeProcess()

    monkeypatch.setattr(tasks.subprocess, "Popen", popen)

    tasks._popen(
        ("npm", "ci"),
        cwd=ROOT,
        environment={"PATH": "C:\\pinned-node"},
        capture=False,
    )

    assert observed["argv"] == ("C:\\pinned-node\\npm.cmd", "ci")
    assert cast(dict[str, object], observed["kwargs"])["shell"] is False


def test_linux_and_windows_workflows_bootstrap_exact_tools_and_share_the_cli() -> None:
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    windows = workflow.split("  windows-host-ci:", maxsplit=1)[1]

    assert workflow.count("uv run python scripts/repository_tasks.py ci") == 2
    assert workflow.count("scripts/repository_tasks.py classify") == 2
    assert workflow.count("github.event.pull_request.base.sha || github.sha") == 2
    assert workflow.count("github.event.pull_request.head.sha || github.sha") == 2
    assert workflow.count("name: Linux CI with container service") == 1
    assert workflow.count("name: Windows host-only CI") == 1
    assert "--require-container-tests" in workflow
    assert "--host-only" in windows
    assert "\n  push:" not in workflow
    assert 'cron: "0 18 * * *"' in workflow
    assert "  workflow_dispatch:" in workflow
    assert "cancel-in-progress: true" in workflow
    assert "if: steps.ci-mode.outputs.mode == 'full'" in workflow
    assert "if: always() && steps.ci-mode.outputs.mode == 'full'" in workflow
    linux = workflow.split("  linux-ci:", maxsplit=1)[1].split(
        "  windows-host-ci:", maxsplit=1
    )[0]
    assert "\n    if:" not in linux
    assert "\n    if:" not in windows
    assert "docker " not in windows
    for exact_version in ("3.12.14", "0.12.5", "24.19.0", "npm@11.17.0"):
        assert exact_version in workflow
    for action_pin in (
        "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1",
        "astral-sh/setup-uv@c771a70e6277c0a99b617c7a806ffedaca235ff9",
        "actions/setup-node@48b55a011bda9f5d6aeb4c2d9c7362e8dae4041e",
    ):
        assert workflow.count(action_pin) == 2


def test_ci_stops_on_the_first_failed_step_and_preserves_its_exit(
    monkeypatch: MonkeyPatch,
) -> None:
    calls: list[tuple[str, ...]] = []

    def execute(
        argv: Sequence[str],
        *,
        cwd: Path,
        environment: dict[str, str],
        capture: bool = False,
    ) -> object:
        del cwd, environment, capture
        value = tuple(argv)
        calls.append(value)
        return tasks.CommandResult(17 if value[2:4] == ("ruff", "check") else 0)

    monkeypatch.setattr(tasks, "_execute_command", execute)
    monkeypatch.setattr(tasks, "_marker_inventory", lambda **_: 98)

    result = tasks.run_ci(root=ROOT, host_only=True, require_container_tests=False)

    assert result == 17
    assert calls[-1] == ("uv", "run", "ruff", "check", ".")
    assert not any("mypy" in call for call in calls)


def test_missing_tool_and_cancellation_have_cross_platform_exit_codes(
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    def missing(*args: object, **kwargs: object) -> object:
        del args, kwargs
        raise FileNotFoundError(2, "not found", "uv")

    monkeypatch.setattr(tasks, "_execute_command", missing)
    assert tasks.main(["ci", "--root", str(ROOT), "--host-only"]) == 127
    assert "missing executable=uv" in capsys.readouterr().err

    def cancelled(*args: object, **kwargs: object) -> object:
        del args, kwargs
        raise tasks.TaskCancelled

    monkeypatch.setattr(tasks, "_execute_command", cancelled)
    assert tasks.main(["ci", "--root", str(ROOT), "--host-only"]) == 130
    assert "CANCELLED" in capsys.readouterr().err


def test_container_scope_requires_an_explicit_dsn_and_rejects_conflicting_modes(
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    with pytest.raises(tasks.TaskConfigurationError, match=tasks.POSTGRES_DSN_ENV):
        tasks._test_scope(
            host_only=False,
            require_container_tests=True,
            environment={},
        )
    with pytest.raises(tasks.TaskConfigurationError, match="cannot be used together"):
        tasks._test_scope(
            host_only=True,
            require_container_tests=True,
            environment={tasks.POSTGRES_DSN_ENV: "postgresql://isolated"},
        )
    assert tasks._test_scope(
        host_only=False,
        require_container_tests=False,
        environment={},
    ) == tasks.TestScope("host-only", "not container_service")
    assert tasks._test_scope(
        host_only=False,
        require_container_tests=False,
        environment={tasks.POSTGRES_DSN_ENV: "postgresql://isolated"},
    ) == tasks.TestScope("all", None)

    monkeypatch.setattr(tasks, "_task_environment", lambda: {})
    assert (
        tasks.main(["ci", "--root", str(ROOT), "--require-container-tests"])
        == 2
    )
    assert tasks.POSTGRES_DSN_ENV in capsys.readouterr().err


def test_root_with_spaces_is_passed_as_cwd_without_shell_interpolation(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    root = tmp_path / "repository task root with spaces"
    root.mkdir()
    for name in ("pyproject.toml", "package.json"):
        (root / name).write_bytes((ROOT / name).read_bytes())
    observed: list[Path] = []

    def execute(
        argv: Sequence[str],
        *,
        cwd: Path,
        environment: dict[str, str],
        capture: bool = False,
    ) -> object:
        del argv, environment, capture
        observed.append(cwd)
        return tasks.CommandResult(0)

    monkeypatch.setattr(tasks, "_execute_command", execute)
    monkeypatch.setattr(tasks, "_marker_inventory", lambda **_: 98)

    assert tasks.run_ci(root=root, host_only=True, require_container_tests=False) == 0
    assert observed == [root] * 12
    assert (
        "TEST_SCOPE ci_mode=full platform_scope=host-only marker=container_service "
        "selected=98 included=0 excluded=98"
    ) in capsys.readouterr().out


def test_marker_inventory_reports_exact_nodes_and_rejects_drift(
    monkeypatch: MonkeyPatch,
) -> None:
    def clean(
        argv: Sequence[str],
        *,
        cwd: Path,
        environment: dict[str, str],
        capture: bool = False,
    ) -> object:
        del cwd, environment
        assert capture
        value = tuple(argv)
        assert value[-1] == "tests/integration"
        expression = value[-2]
        if expression == tasks.CONTAINER_MARKER:
            return tasks.CommandResult(
                0,
                "tests/integration/test_one.py::test_a\n"
                "tests/integration/test_two.py::test_b[value]\n\n2 tests collected\n",
            )
        return tasks.CommandResult(5, "\nno tests collected\n")

    monkeypatch.setattr(tasks, "_execute_command", clean)
    assert tasks._marker_inventory(root=ROOT, environment={}) == 2

    def drift(
        argv: Sequence[str],
        *,
        cwd: Path,
        environment: dict[str, str],
        capture: bool = False,
    ) -> object:
        del cwd, environment, capture
        del argv
        node = "tests/integration/test_drift.py::test_missing_marker\n"
        return tasks.CommandResult(0, node)

    monkeypatch.setattr(tasks, "_execute_command", drift)
    with pytest.raises(tasks.TaskConfigurationError, match="marker drift"):
        tasks._marker_inventory(root=ROOT, environment={})


def test_every_postgresql_module_has_the_container_service_marker() -> None:
    modules = sorted((ROOT / "tests/integration").glob("*_postgresql.py"))

    assert len(modules) == 23
    for module in modules:
        source = module.read_text(encoding="utf-8")
        assert "pytest.mark.postgresql" in source, module
        assert "pytest.mark.container_service" in source, module


def test_repository_text_is_canonical_but_raw_bytes_remain_byte_exact() -> None:
    lf = b'{\n  "kind": "repository-text",\n  "value": 1\n}\n'
    crlf = lf.replace(b"\n", b"\r\n")

    assert hashlib.sha256(lf).hexdigest() != hashlib.sha256(crlf).hexdigest()
    assert canonical_json_bytes(json.loads(lf)) == canonical_json_bytes(json.loads(crlf))

    attributes = (ROOT / ".gitattributes").read_text(encoding="utf-8").splitlines()
    expected = {
        "plugins/reference/contract_echo/dependency.lock text eol=lf",
        "plugins/reference/contract_echo/contract_echo/__init__.py text eol=lf",
        "plugins/reference/contract_echo/contract_echo/plugin.py text eol=lf",
        "plugins/reference/contract_echo/schemas/config.schema.json text eol=lf",
    }
    assert expected.issubset(attributes)


class _FakeProcess:
    pid = 42

    def __init__(self) -> None:
        self.wait_calls = 0
        self.sent: list[object] = []

    def poll(self) -> None:
        return None

    def wait(self, timeout: float | None = None) -> int:
        self.wait_calls += 1
        if timeout is not None and self.wait_calls <= 2:
            raise subprocess.TimeoutExpired("fake", timeout)
        return 0

    def send_signal(self, value: object) -> None:
        self.sent.append(value)

    def terminate(self) -> None:
        self.sent.append("terminate")

    def kill(self) -> None:
        self.sent.append("kill")


def test_posix_cancellation_escalates_over_the_whole_process_group(
    monkeypatch: MonkeyPatch,
) -> None:
    process = _FakeProcess()
    sent: list[tuple[int, signal.Signals]] = []
    kill_signal = getattr(signal, "SIGKILL", signal.SIGABRT)
    monkeypatch.setattr(tasks.os, "name", "posix")
    monkeypatch.setattr(tasks.signal, "SIGKILL", kill_signal, raising=False)
    monkeypatch.setattr(
        tasks.os,
        "killpg",
        lambda pid, value: sent.append((pid, value)),
        raising=False,
    )

    tasks._cancel_process_group(cast(subprocess.Popen[str], process))

    assert sent == [
        (42, signal.SIGINT),
        (42, signal.SIGTERM),
        (42, kill_signal),
    ]


def test_windows_cancellation_uses_break_then_terminate_and_kill(
    monkeypatch: MonkeyPatch,
) -> None:
    process = _FakeProcess()
    monkeypatch.setattr(tasks.os, "name", "nt")

    tasks._cancel_process_group(cast(subprocess.Popen[str], process))

    assert process.sent == [
        getattr(signal, "CTRL_BREAK_EVENT", signal.SIGTERM),
        "terminate",
        "kill",
    ]

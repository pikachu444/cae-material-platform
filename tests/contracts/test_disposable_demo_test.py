from __future__ import annotations

import subprocess
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from typing import Any

import pytest
from pytest import MonkeyPatch

ROOT = Path(__file__).parents[2]

_SPEC = spec_from_file_location(
    "run_disposable_demo_test", ROOT / "scripts" / "run_disposable_demo_test.py"
)
assert _SPEC and _SPEC.loader
demo_test = module_from_spec(_SPEC)
sys.modules[_SPEC.name] = demo_test
_SPEC.loader.exec_module(demo_test)


def _isolated_config(project: str) -> dict[str, Any]:
    return {
        "name": project,
        "services": {
            "postgres": {},
            "api": {},
            "web": {
                "ports": [
                    {
                        "target": 5173,
                        "published": "0",
                        "host_ip": "127.0.0.1",
                    }
                ]
            },
        },
        "volumes": {key: {"name": f"{project}_{key}"} for key in demo_test.PROJECT_VOLUME_KEYS},
    }


def _make_target(source: str, target: str, next_target: str) -> str:
    return source.split(f"{target}:\n", 1)[1].split(f"\n{next_target}:\n", 1)[0]


def test_make_routes_automation_to_disposable_runner_and_preserves_demo_volumes() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")

    verify = _make_target(makefile, "demo-verify", "demo-e2e")
    e2e = _make_target(makefile, "demo-e2e", "demo-down")
    down = _make_target(makefile, "demo-down", "compose-preflight")

    assert "scripts/run_disposable_demo_test.py" in verify
    assert "npx --no-install playwright install chromium" in e2e
    assert "scripts/run_disposable_demo_test.py --e2e" in e2e
    assert "down" in down
    assert " -v" not in down
    assert "--volumes" not in down


def test_isolated_config_accepts_only_project_scoped_volumes_and_random_web_port() -> None:
    project = "cmp-demo-test-proof123"

    assert demo_test.validate_isolated_config(_isolated_config(project), project=project) == ()


def test_isolated_config_rejects_a_published_database_or_permanent_volume() -> None:
    project = "cmp-demo-test-proof123"
    config = _isolated_config(project)
    config["services"]["postgres"] = {"ports": [{"target": 5432, "published": "54329"}]}
    config["volumes"]["cmp_demo_postgres"] = {"name": "cmp-local-demo_cmp_demo_postgres"}

    errors = demo_test.validate_isolated_config(config, project=project)

    assert "service postgres must not publish host ports in disposable tests" in errors
    assert any("cmp-local-demo_cmp_demo_postgres" in error for error in errors)


@pytest.mark.parametrize(
    "project",
    ("cmp-local-demo", "cmp-demo-test", "cmp-demo-test_bad", "other-test-proof"),
)
def test_permanent_or_unbounded_project_names_are_rejected(project: str) -> None:
    with pytest.raises(demo_test.DisposableDemoError):
        demo_test.validate_project_name(project)


def test_failure_still_removes_only_the_disposable_project(monkeypatch: MonkeyPatch) -> None:
    project = "cmp-demo-test-proof123"
    snapshot = demo_test.PermanentDemoSnapshot(
        volumes=(("cmp-local-demo_cmp_demo_postgres", "created", "mount"),),
        counts=(("catalog.catalog_record", 15),),
    )
    cleanups: list[str] = []

    monkeypatch.setattr(demo_test, "_load_isolated_config", lambda *args: {})
    monkeypatch.setattr(demo_test, "_assert_project_absent", lambda *args, **kwargs: None)
    monkeypatch.setattr(demo_test, "permanent_demo_snapshot", lambda *args: snapshot)
    monkeypatch.setattr(
        demo_test,
        "_run_verification",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("verification failed")),
    )
    monkeypatch.setattr(
        demo_test,
        "_cleanup",
        lambda _root, selected_project: cleanups.append(selected_project),
    )

    with pytest.raises(RuntimeError, match="verification failed"):
        demo_test.run_disposable_demo_test(ROOT, project=project)

    assert cleanups == [project]


def test_verification_starts_worker_for_queued_jobs(monkeypatch: MonkeyPatch) -> None:
    project = "cmp-demo-test-proof123"
    commands: list[list[str]] = []

    def run_command(args: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        commands.append(list(args))
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(demo_test, "_run_command", run_command)
    monkeypatch.setattr(
        demo_test, "_run_seed_twice_and_assert_stable", lambda *args, **kwargs: None
    )

    demo_test._run_verification(ROOT, project, e2e=False)

    build = next(command for command in commands if "build" in command)
    up = next(command for command in commands if "up" in command)
    assert "worker" in build
    assert "worker" in up


def test_browser_verification_uses_disposable_web_url_without_full_api_verifier(
    monkeypatch: MonkeyPatch,
) -> None:
    project = "cmp-demo-test-proof123"
    commands: list[list[str]] = []

    def run_command(args: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        commands.append(list(args))
        output = "127.0.0.1:49152\n" if "port" in args else ""
        return subprocess.CompletedProcess(args, 0, output, "")

    monkeypatch.setattr(demo_test, "_run_command", run_command)
    monkeypatch.setattr(
        demo_test, "_run_seed_twice_and_assert_stable", lambda *args, **kwargs: None
    )
    monkeypatch.setattr(demo_test, "_wait_for_url", lambda *args, **kwargs: None)
    monkeypatch.setattr(demo_test, "_npm_executable", lambda: "npm")

    demo_test._run_verification(ROOT, project, e2e=True)

    npm = next(command for command in commands if command[0] == "npm")
    assert npm == ["npm", "run", "test:e2e", "--workspace", "@cmp/web"]
    assert not any("scripts/verify_full_demo.py" in command for command in commands)


def test_browser_verification_can_select_the_owned_specs_without_changing_the_default(
    monkeypatch: MonkeyPatch,
) -> None:
    project = "cmp-demo-test-proof123"
    commands: list[list[str]] = []

    def run_command(args: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        commands.append(list(args))
        output = "127.0.0.1:49152\n" if "port" in args else ""
        return subprocess.CompletedProcess(args, 0, output, "")

    monkeypatch.setattr(demo_test, "_run_command", run_command)
    monkeypatch.setattr(
        demo_test, "_run_seed_twice_and_assert_stable", lambda *args, **kwargs: None
    )
    monkeypatch.setattr(demo_test, "_wait_for_url", lambda *args, **kwargs: None)
    monkeypatch.setattr(demo_test, "_npm_executable", lambda: "npm")

    demo_test._run_verification(
        ROOT,
        project,
        e2e=True,
        e2e_specs=("e2e/guided-demo.spec.ts", "e2e/display-density.spec.ts"),
    )

    npm = next(command for command in commands if command[0] == "npm")
    assert npm == [
        "npm",
        "run",
        "test:e2e",
        "--workspace",
        "@cmp/web",
        "--",
        "e2e/guided-demo.spec.ts",
        "e2e/display-density.spec.ts",
    ]


def test_repeat_seed_runs_twice_and_requires_an_exact_protected_table_snapshot(
    monkeypatch: MonkeyPatch,
) -> None:
    project = "cmp-demo-test-proof123"
    commands: list[list[str]] = []
    snapshot = demo_test.RepeatSeedSnapshot(
        tables=(("catalog.catalog_record", 3, "a" * 32),)
    )

    def run_command(args: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        commands.append(list(args))
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(demo_test, "_run_command", run_command)
    monkeypatch.setattr(demo_test, "_repeat_seed_snapshot", lambda *args: snapshot)

    demo_test._run_seed_twice_and_assert_stable(ROOT, project)

    seed_commands = [command for command in commands if command[-1] == "seed"]
    assert len(seed_commands) == 2


def test_repeat_seed_table_discovery_covers_every_seeded_domain_table(
    monkeypatch: MonkeyPatch,
) -> None:
    discovered = (
        *demo_test.REPEAT_SEED_REQUIRED_TABLES,
        "access_control.seeded_state",
        "artifact.seeded_state",
        "audit.seeded_state",
        "events.seeded_state",
        "jobs.seeded_state",
        "plugin.seeded_state",
        "revisioning.seeded_state",
    )
    commands: list[tuple[str, ...]] = []

    def capture(args: tuple[str, ...], **kwargs: object) -> subprocess.CompletedProcess[str]:
        commands.append(args)
        return subprocess.CompletedProcess(args, 0, "\n".join(discovered), "")

    monkeypatch.setattr(
        demo_test,
        "_run_command",
        capture,
    )

    assert demo_test._repeat_seed_tables(ROOT, "postgres-1") == discovered
    query = commands[0][-1]
    assert "schemaname NOT IN ('information_schema', 'pg_catalog', 'public')" in query
    assert "schemaname !~ '^pg_(temp|toast)'" in query
    assert "schemaname IN" not in query


def test_repeat_seed_snapshot_ignores_only_operational_authentication_last_seen() -> None:
    assert demo_test.REPEAT_SEED_IGNORED_FIELDS == {
        "identity.external_identity": ("last_seen_at",)
    }
    assert demo_test._repeat_seed_row_json("identity.external_identity") == (
        "(to_jsonb(seed_row) - ARRAY['last_seen_at']::text[])"
    )
    assert demo_test._repeat_seed_row_json("catalog.material_state_revision") == (
        "to_jsonb(seed_row)"
    )


def test_repeat_seed_table_discovery_fails_when_state_neutral_or_review_is_uncovered(
    monkeypatch: MonkeyPatch,
) -> None:
    discovered = tuple(
        table
        for table in demo_test.REPEAT_SEED_REQUIRED_TABLES
        if table
        not in {
            "catalog.material_state_revision",
            "modeling.neutral_material_revision",
            "governance.review_request",
        }
    )
    monkeypatch.setattr(
        demo_test,
        "_run_command",
        lambda args, **kwargs: subprocess.CompletedProcess(
            args, 0, "\n".join(discovered), ""
        ),
    )

    with pytest.raises(
        demo_test.DisposableDemoError,
        match=r"material_state_revision.*review_request.*neutral_material_revision",
    ):
        demo_test._repeat_seed_tables(ROOT, "postgres-1")


def test_repeat_seed_reports_the_conflicting_stage_and_table_delta(
    monkeypatch: MonkeyPatch,
) -> None:
    project = "cmp-demo-test-proof123"
    snapshots = iter(
        (
            demo_test.RepeatSeedSnapshot(
                tables=(("catalog.domain_record_binding", 8, "a" * 32),)
            ),
            demo_test.RepeatSeedSnapshot(
                tables=(("catalog.domain_record_binding", 9, "b" * 32),)
            ),
        )
    )
    monkeypatch.setattr(
        demo_test,
        "_run_command",
        lambda args, **kwargs: subprocess.CompletedProcess(args, 0, "", ""),
    )
    monkeypatch.setattr(demo_test, "_repeat_seed_snapshot", lambda *args: next(snapshots))

    with pytest.raises(
        demo_test.DisposableDemoError,
        match=r"repeat demo seed comparison failed.*catalog.domain_record_binding",
    ):
        demo_test._run_seed_twice_and_assert_stable(ROOT, project)


def test_repeat_seed_409_is_labeled_as_the_repeat_seed_stage(
    monkeypatch: MonkeyPatch,
) -> None:
    project = "cmp-demo-test-proof123"
    snapshot = demo_test.RepeatSeedSnapshot(
        tables=(("catalog.catalog_record", 3, "a" * 32),)
    )
    seed_run = 0

    def run_command(args: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        nonlocal seed_run
        seed_run += 1
        if seed_run == 2:
            raise demo_test.DisposableDemoError("domain binding returned 409")
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(demo_test, "_run_command", run_command)
    monkeypatch.setattr(demo_test, "_repeat_seed_snapshot", lambda *args: snapshot)

    with pytest.raises(
        demo_test.DisposableDemoError,
        match=r"repeat demo seed failed.*domain binding returned 409",
    ):
        demo_test._run_seed_twice_and_assert_stable(ROOT, project)


def test_cleanup_removes_only_validated_project_resources_and_local_images(
    monkeypatch: MonkeyPatch,
) -> None:
    project = "cmp-demo-test-proof123"
    commands: list[list[str]] = []

    def run_command(args: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        commands.append(list(args))
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(demo_test, "_run_command", run_command)
    monkeypatch.setattr(demo_test, "_assert_project_absent", lambda *args, **kwargs: None)

    demo_test._cleanup(ROOT, project)

    command = commands[0]
    assert command[command.index("--project-name") + 1] == project
    assert "--volumes" in command
    assert command[command.index("--rmi") + 1] == "local"

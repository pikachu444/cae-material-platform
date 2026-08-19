from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen

PERMANENT_PROJECT = "cmp-local-demo"
DISPOSABLE_PROJECT_PREFIX = "cmp-demo-test-"
DISPOSABLE_PROJECT_PATTERN = re.compile(r"^cmp-demo-test-[a-z0-9][a-z0-9-]{0,31}$")
COMPOSE_FILES = (
    Path("deploy/compose/docker-compose.demo.yml"),
    Path("deploy/compose/docker-compose.demo-test.yml"),
)
PROJECT_VOLUME_KEYS = ("cmp_demo_objects", "cmp_demo_postgres")
PERMANENT_COUNT_TABLES = (
    "catalog.catalog_record",
    "catalog.catalog_record_revision",
    "catalog.domain_record_binding",
    "catalog.material",
    "catalog.material_revision",
    "datasets.test_data_document_revision",
    "modeling.material_model_revision",
    "exporting.solver_card_revision",
)


class DisposableDemoError(RuntimeError):
    """A disposable Compose boundary could not be proven or completed."""


@dataclass(frozen=True)
class PermanentDemoSnapshot:
    volumes: tuple[tuple[str, str, str], ...]
    counts: tuple[tuple[str, int], ...] | None


def new_project_name() -> str:
    return f"{DISPOSABLE_PROJECT_PREFIX}{uuid.uuid4().hex[:12]}"


def validate_project_name(value: str) -> str:
    project = value.strip().lower()
    if project == PERMANENT_PROJECT or not DISPOSABLE_PROJECT_PATTERN.fullmatch(project):
        raise DisposableDemoError(
            "disposable project name must match cmp-demo-test-<unique-token>; "
            f"refusing project={value!r}"
        )
    return project


def compose_command(root: Path, project: str, *args: str) -> list[str]:
    command = ["docker", "compose", "--project-name", project]
    for relative in COMPOSE_FILES:
        command.extend(("--file", str((root / relative).resolve())))
    command.extend(args)
    return command


def _run_command(
    args: Sequence[str],
    *,
    cwd: Path,
    capture_output: bool = False,
    env: Mapping[str, str] | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            list(args),
            cwd=str(cwd),
            check=check,
            capture_output=capture_output,
            text=True,
            env=dict(env) if env is not None else None,
        )
    except OSError as exc:
        raise DisposableDemoError(f"cannot run {args[0]}: {exc}") from exc


def _json_object(value: str, *, source: str) -> dict[str, Any]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise DisposableDemoError(f"{source} returned invalid JSON: {exc.msg}") from exc
    if not isinstance(parsed, dict):
        raise DisposableDemoError(f"{source} did not return a JSON object")
    return parsed


def validate_isolated_config(config: Mapping[str, Any], *, project: str) -> tuple[str, ...]:
    errors: list[str] = []
    if config.get("name") != project:
        errors.append(
            f"Compose resolved the wrong project (expected={project}, actual={config.get('name')})"
        )

    services = config.get("services")
    service_map = services if isinstance(services, Mapping) else {}
    for name, value in service_map.items():
        service = value if isinstance(value, Mapping) else {}
        ports = service.get("ports") or []
        if name != "web" and ports:
            errors.append(f"service {name} must not publish host ports in disposable tests")
    web = service_map.get("web")
    web_map = web if isinstance(web, Mapping) else {}
    web_ports = web_map.get("ports") or []
    if len(web_ports) != 1 or not isinstance(web_ports[0], Mapping):
        errors.append("service web must publish one random localhost test port")
    else:
        web_port = web_ports[0]
        if (
            str(web_port.get("target")) != "5173"
            or str(web_port.get("published")) != "0"
            or web_port.get("host_ip") != "127.0.0.1"
        ):
            errors.append("service web test port must be 127.0.0.1:<random>:5173")

    volumes = config.get("volumes")
    volume_map = volumes if isinstance(volumes, Mapping) else {}
    for key in PROJECT_VOLUME_KEYS:
        value = volume_map.get(key)
        volume = value if isinstance(value, Mapping) else {}
        expected_name = f"{project}_{key}"
        if volume.get("name") != expected_name or volume.get("external") is True:
            errors.append(
                f"volume {key} must be project-scoped (expected={expected_name}, "
                f"actual={volume.get('name')})"
            )
    return tuple(errors)


def _load_isolated_config(root: Path, project: str) -> dict[str, Any]:
    result = _run_command(
        compose_command(root, project, "config", "--format", "json"),
        cwd=root,
        capture_output=True,
    )
    config = _json_object(result.stdout, source="docker compose config")
    errors = validate_isolated_config(config, project=project)
    if errors:
        raise DisposableDemoError("; ".join(errors))
    return config


def _project_resource_names(root: Path, project: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    containers = _run_command(
        (
            "docker",
            "container",
            "ls",
            "--all",
            "--filter",
            f"label=com.docker.compose.project={project}",
            "--format",
            "{{.Names}}",
        ),
        cwd=root,
        capture_output=True,
    ).stdout.splitlines()
    volumes = _run_command(
        (
            "docker",
            "volume",
            "ls",
            "--filter",
            f"label=com.docker.compose.project={project}",
            "--format",
            "{{.Name}}",
        ),
        cwd=root,
        capture_output=True,
    ).stdout.splitlines()
    return tuple(sorted(filter(None, containers))), tuple(sorted(filter(None, volumes)))


def _assert_project_absent(root: Path, project: str, *, phase: str) -> None:
    containers, volumes = _project_resource_names(root, project)
    if containers or volumes:
        raise DisposableDemoError(
            f"disposable project is not empty {phase}: "
            f"containers={list(containers)}, volumes={list(volumes)}"
        )


def _permanent_volume_identity(root: Path) -> tuple[tuple[str, str, str], ...]:
    _, names = _project_resource_names(root, PERMANENT_PROJECT)
    if not names:
        return ()
    result = _run_command(
        ("docker", "volume", "inspect", *names),
        cwd=root,
        capture_output=True,
    )
    try:
        records = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise DisposableDemoError(
            f"docker volume inspect returned invalid JSON: {exc.msg}"
        ) from exc
    if not isinstance(records, list):
        raise DisposableDemoError("docker volume inspect did not return a JSON list")
    identity: list[tuple[str, str, str]] = []
    for record in records:
        if not isinstance(record, Mapping):
            raise DisposableDemoError("docker volume inspect returned an invalid record")
        identity.append(
            (
                str(record.get("Name", "")),
                str(record.get("CreatedAt", "")),
                str(record.get("Mountpoint", "")),
            )
        )
    return tuple(sorted(identity))


def _permanent_postgres_container(root: Path) -> str | None:
    result = _run_command(
        (
            "docker",
            "container",
            "ls",
            "--filter",
            f"label=com.docker.compose.project={PERMANENT_PROJECT}",
            "--filter",
            "label=com.docker.compose.service=postgres",
            "--format",
            "{{.ID}}",
        ),
        cwd=root,
        capture_output=True,
    )
    containers = tuple(filter(None, result.stdout.splitlines()))
    if len(containers) > 1:
        raise DisposableDemoError("multiple running cmp-local-demo postgres containers were found")
    return containers[0] if containers else None


def _permanent_counts(root: Path) -> tuple[tuple[str, int], ...] | None:
    container = _permanent_postgres_container(root)
    if container is None:
        return None
    query = (
        " UNION ALL ".join(
            f"SELECT '{table}', count(*)::bigint FROM {table}" for table in PERMANENT_COUNT_TABLES
        )
        + " ORDER BY 1"
    )
    result = _run_command(
        (
            "docker",
            "exec",
            container,
            "psql",
            "-U",
            "cmp_owner",
            "-d",
            "cmp",
            "--no-align",
            "--tuples-only",
            "--set=ON_ERROR_STOP=1",
            "--field-separator=|",
            "--command",
            query,
        ),
        cwd=root,
        capture_output=True,
    )
    counts: list[tuple[str, int]] = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        table, separator, count = line.partition("|")
        if not separator:
            raise DisposableDemoError(f"cannot parse permanent demo count: {line!r}")
        counts.append((table, int(count)))
    return tuple(counts)


def permanent_demo_snapshot(root: Path) -> PermanentDemoSnapshot:
    return PermanentDemoSnapshot(
        volumes=_permanent_volume_identity(root),
        counts=_permanent_counts(root),
    )


def _print_snapshot(label: str, snapshot: PermanentDemoSnapshot) -> None:
    volume_names = [item[0] for item in snapshot.volumes]
    count_values = dict(snapshot.counts) if snapshot.counts is not None else "not-running"
    print(
        f"Permanent demo {label}: project={PERMANENT_PROJECT}, "
        f"volumes={volume_names}, counts={count_values}"
    )


def _wait_for_url(url: str, *, timeout_seconds: float = 90.0) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error = "not attempted"
    while time.monotonic() < deadline:
        try:
            with urlopen(url, timeout=3) as response:
                if response.status == 200:
                    return
                last_error = f"HTTP {response.status}"
        except (OSError, URLError) as exc:
            last_error = str(exc)
        time.sleep(1)
    raise DisposableDemoError(f"web test endpoint did not become ready: {url} ({last_error})")


def _web_url(root: Path, project: str) -> str:
    result = _run_command(
        compose_command(root, project, "port", "web", "5173"),
        cwd=root,
        capture_output=True,
    )
    endpoint = result.stdout.strip()
    _, separator, port = endpoint.rpartition(":")
    if not separator or not port.isdigit():
        raise DisposableDemoError(f"cannot resolve disposable web port from {endpoint!r}")
    return f"http://127.0.0.1:{port}"


def _npm_executable() -> str:
    return shutil.which("npm") or "npm"


def _run_verification(root: Path, project: str, *, e2e: bool) -> None:
    build_services = ["migrate", "api", "worker", "reference-plugins", "seed"]
    if e2e:
        build_services.append("web")
    _run_command(compose_command(root, project, "build", *build_services), cwd=root)
    _run_command(
        compose_command(
            root,
            project,
            "up",
            "--detach",
            "api",
            "worker",
            "reference-plugins",
        ),
        cwd=root,
    )
    _run_command(compose_command(root, project, "run", "--rm", "--no-deps", "seed"), cwd=root)
    if not e2e:
        _run_command(
            compose_command(
                root,
                project,
                "run",
                "--rm",
                "--no-deps",
                "seed",
                "python",
                "scripts/verify_full_demo.py",
                "--api-base-url",
                "http://api:8000/api/v1",
            ),
            cwd=root,
        )
        return

    _run_command(compose_command(root, project, "up", "--detach", "web"), cwd=root)
    web_url = _web_url(root, project)
    _wait_for_url(web_url)
    environment = os.environ.copy()
    environment["CMP_DEMO_WEB_URL"] = web_url
    print(f"Disposable browser endpoint: {web_url}")
    _run_command(
        (_npm_executable(), "run", "test:e2e", "--workspace", "@cmp/web"),
        cwd=root,
        env=environment,
    )


def _cleanup(root: Path, project: str) -> None:
    result = _run_command(
        compose_command(
            root,
            project,
            "down",
            "--volumes",
            "--rmi",
            "local",
            "--remove-orphans",
            "--timeout",
            "30",
        ),
        cwd=root,
        check=False,
    )
    if result.returncode:
        raise DisposableDemoError(
            f"disposable Compose cleanup failed for project={project} (exit={result.returncode})"
        )
    _assert_project_absent(root, project, phase="after cleanup")


def run_disposable_demo_test(root: Path, *, project: str, e2e: bool = False) -> None:
    project = validate_project_name(project)
    root = root.resolve()
    _load_isolated_config(root, project)
    _assert_project_absent(root, project, phase="before creation")
    permanent_before = permanent_demo_snapshot(root)
    _print_snapshot("before", permanent_before)
    expected_volumes = [f"{project}_{key}" for key in PROJECT_VOLUME_KEYS]
    print(
        f"Disposable demo test: project={project}, volumes={expected_volumes}, "
        f"e2e={str(e2e).lower()}"
    )

    failure: BaseException | None = None
    try:
        _run_verification(root, project, e2e=e2e)
    except BaseException as exc:
        failure = exc
    try:
        _cleanup(root, project)
    except BaseException as cleanup_exc:
        if failure is not None:
            raise DisposableDemoError(
                f"verification failed ({failure}); cleanup also failed ({cleanup_exc})"
            ) from cleanup_exc
        raise

    permanent_after = permanent_demo_snapshot(root)
    _print_snapshot("after", permanent_after)
    if permanent_after != permanent_before:
        raise DisposableDemoError(
            "cmp-local-demo changed while the disposable verification ran: "
            f"before={permanent_before}, after={permanent_after}"
        )
    if failure is not None:
        raise failure
    print(f"Disposable demo test passed and removed project={project}")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run demo verification in a fresh project-scoped Compose environment."
    )
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--project-name", default=None)
    parser.add_argument("--e2e", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    project = args.project_name or new_project_name()
    try:
        run_disposable_demo_test(args.root, project=project, e2e=args.e2e)
    except (DisposableDemoError, subprocess.CalledProcessError, ValueError) as exc:
        print(f"Disposable demo test failed: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

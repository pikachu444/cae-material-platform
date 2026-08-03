"""Read-only validation of the canonical local Docker Compose environment."""

from __future__ import annotations

import argparse
import json
import os
import posixpath
import re
import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

EXPECTED_PROJECT = "cmp-local-demo"
DEFAULT_COMPOSE_FILE = Path("deploy/compose/docker-compose.demo.yml")
REQUIRED_SERVICES = ("postgres", "api", "web")
OPTIONAL_SERVICES = ("postgres-test",)
SERVICE_PORTS: dict[str, tuple[int, int]] = {
    "postgres": (54329, 5432),
    "api": (8000, 8000),
    "web": (5173, 5173),
    "postgres-test": (54330, 5432),
}


class ComposePreflightError(RuntimeError):
    """A Docker/Compose command did not produce trustworthy preflight input."""


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _labels(container: Mapping[str, Any]) -> dict[str, str]:
    labels = _mapping(_mapping(container.get("Config")).get("Labels"))
    return {str(key): str(value) for key, value in labels.items() if value is not None}


def _container_name(container: Mapping[str, Any]) -> str:
    return str(container.get("Name") or "<unknown-container>").lstrip("/")


def _state(container: Mapping[str, Any]) -> Mapping[str, Any]:
    return _mapping(container.get("State"))


def _state_status(container: Mapping[str, Any]) -> str:
    return str(_state(container).get("Status") or "unknown").strip().lower()


def _is_running(container: Mapping[str, Any]) -> bool:
    return _state(container).get("Running") is True


def _health_status(container: Mapping[str, Any]) -> str | None:
    state = _state(container)
    if "Health" not in state or state["Health"] is None:
        return None
    health = _mapping(state["Health"])
    return str(health.get("Status") or "missing").strip().lower()


def _port_number(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        port = int(str(value).strip())
    except (TypeError, ValueError):
        return None
    return port if 1 <= port <= 65535 else None


def _target_port(value: Any) -> tuple[int | None, str]:
    match = re.fullmatch(r"\s*(\d+)(?:/(tcp|udp|sctp))?\s*", str(value).lower())
    if not match:
        return None, "tcp"
    return _port_number(match.group(1)), match.group(2) or "tcp"


def _port_bindings(container: Mapping[str, Any]) -> tuple[tuple[int, int, str], ...]:
    """Read published ports from the standard inspect ``NetworkSettings.Ports`` field."""

    ports = _mapping(_mapping(container.get("NetworkSettings")).get("Ports"))
    bindings: list[tuple[int, int, str]] = []
    for target, entries in ports.items():
        target_port, protocol = _target_port(target)
        if target_port is None or not isinstance(entries, list):
            continue
        for entry in entries:
            item = _mapping(entry)
            host_port = _port_number(item.get("HostPort"))
            if host_port is None:
                continue
            binding = (host_port, target_port, str(item.get("Protocol") or protocol).lower())
            if binding not in bindings:
                bindings.append(binding)
    return tuple(bindings)


def _normalise_path(value: str | Path) -> str:
    raw = str(value).strip().replace("\\", "/")
    if raw.startswith("//?/"):
        raw = raw[4:]
    return os.path.normcase(posixpath.normpath(raw))


def _config_files(labels: Mapping[str, str]) -> tuple[str, ...]:
    raw = labels.get("com.docker.compose.project.config_files", "")
    return tuple(item.strip() for item in raw.split(",") if item.strip())


def _image_id(container: Mapping[str, Any]) -> str:
    return str(container.get("Image") or "").strip()


def _normalise_image_id(value: Any) -> str:
    return str(value or "").strip().lower()


def _port_conflict_evidence(
    containers: Sequence[Mapping[str, Any]],
    *,
    expected_project: str,
    selected_services: Sequence[str],
) -> list[str]:
    """Report required host-port owners, considering only running containers."""

    selected_ports = {SERVICE_PORTS[service][0]: service for service in selected_services}
    errors: list[str] = []
    for container in containers:
        if not _is_running(container):
            continue
        labels = _labels(container)
        project = labels.get("com.docker.compose.project", "<unlabelled>")
        service = labels.get("com.docker.compose.service", "<unlabelled>")
        name = _container_name(container)
        for host_port, _, _ in _port_bindings(container):
            selected_service = selected_ports.get(host_port)
            if selected_service is None:
                continue
            if project != expected_project or service != selected_service:
                errors.append(
                    f"port {host_port} required by {selected_service} is owned by "
                    f"container {name} (project={project}, service={service})"
                )
    return errors


def validate_compose_environment(
    containers: Sequence[Mapping[str, Any]],
    resolved_image_ids: Mapping[str, Any],
    *,
    expected_project: str = EXPECTED_PROJECT,
    expected_compose_file: str | Path = DEFAULT_COMPOSE_FILE,
    expected_workdir: str | Path | None = None,
    services: Sequence[str] = REQUIRED_SERVICES,
) -> tuple[str, ...]:
    """Return concise validation errors for standard Docker inspect records."""

    selected = tuple(dict.fromkeys(services))
    unknown = [service for service in selected if service not in SERVICE_PORTS]
    if unknown:
        return tuple(f"unknown selected service {service}" for service in unknown)
    if not selected:
        return ("no services selected",)

    compose_path = Path(expected_compose_file)
    expected_file = _normalise_path(compose_path)
    compose_parent = compose_path.parent
    expected_dir = _normalise_path(expected_workdir or compose_parent)
    errors = _port_conflict_evidence(
        containers, expected_project=expected_project, selected_services=selected
    )

    canonical: dict[str, list[Mapping[str, Any]]] = {service: [] for service in selected}
    for container in containers:
        labels = _labels(container)
        if labels.get("com.docker.compose.project") != expected_project:
            continue
        service = labels.get("com.docker.compose.service")
        if service in canonical:
            canonical[service].append(container)

    for service in selected:
        matches = canonical[service]
        if not matches:
            errors.append(
                f"required service {service} is missing for Compose project {expected_project}"
            )
            continue
        if len(matches) > 1:
            names = ", ".join(_container_name(item) for item in matches)
            errors.append(f"required service {service} is ambiguous ({names})")
            continue

        container = matches[0]
        labels = _labels(container)
        name = _container_name(container)
        config_files = tuple(_normalise_path(item) for item in _config_files(labels))
        if config_files != (expected_file,):
            actual = ", ".join(config_files) or "missing"
            errors.append(
                f"service {service} container {name} has wrong Compose config path "
                f"(expected={expected_file}, actual={actual})"
            )
        actual_dir = labels.get("com.docker.compose.project.working_dir")
        if actual_dir is None or _normalise_path(actual_dir) != expected_dir:
            observed_dir = _normalise_path(actual_dir) if actual_dir else "missing"
            errors.append(
                f"service {service} container {name} has wrong Compose working directory "
                f"(expected={expected_dir}, actual={observed_dir})"
            )

        if not _is_running(container):
            errors.append(
                f"required service {service} container {name} is not running "
                f"(state={_state_status(container)})"
            )
        else:
            health = _health_status(container)
            if health is not None and health != "healthy":
                errors.append(
                    f"required service {service} container {name} is not healthy (health={health})"
                )

        expected_host, expected_container = SERVICE_PORTS[service]
        matching_ports = {
            host for host, target, _ in _port_bindings(container) if target == expected_container
        }
        if expected_host not in matching_ports:
            observed = ", ".join(str(port) for port in sorted(matching_ports)) or "none"
            errors.append(
                f"service {service} container {name} does not publish expected host port "
                f"{expected_host} (observed={observed})"
            )

        expected_image = _normalise_image_id(resolved_image_ids.get(service))
        actual_image = _normalise_image_id(_image_id(container))
        if not expected_image:
            errors.append(f"canonical Compose image ID for service {service} is unresolved")
        elif not actual_image:
            errors.append(f"service {service} container {name} has no inspect image ID")
        elif actual_image != expected_image:
            errors.append(
                f"service {service} container {name} image mismatch "
                f"(expected={expected_image}, actual={actual_image})"
            )

    return tuple(dict.fromkeys(errors))


validate_environment = validate_compose_environment


def _parse_json_lines(payload: str, *, source: str) -> list[Any]:
    records: list[Any] = []
    for line_number, line in enumerate(payload.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ComposePreflightError(
                f"{source} returned invalid JSON at line {line_number}: {exc.msg}"
            ) from exc
    return records


def _parse_json_object(payload: str, *, source: str) -> Mapping[str, Any]:
    try:
        value = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise ComposePreflightError(f"{source} returned invalid JSON: {exc.msg}") from exc
    if not isinstance(value, Mapping):
        raise ComposePreflightError(f"{source} returned invalid JSON object")
    return value


def _run_command(args: Sequence[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(
            list(args), cwd=str(cwd), check=False, capture_output=True, text=True
        )
    except (FileNotFoundError, OSError) as exc:
        raise ComposePreflightError(f"Docker is unavailable: {exc}") from exc
    if result.returncode:
        detail = (result.stderr or result.stdout).strip().splitlines()
        suffix = f": {detail[-1]}" if detail else ""
        raise ComposePreflightError(
            f"command failed ({' '.join(args[:3])}… exit={result.returncode}){suffix}"
        )
    return result


def inspect_containers(*, docker_bin: str = "docker", cwd: Path) -> list[dict[str, Any]]:
    """List all containers, then inspect the standard Docker JSON records."""

    listed = _parse_json_lines(
        _run_command(
            [docker_bin, "container", "ls", "--all", "--no-trunc", "--format", "{{json .}}"],
            cwd=cwd,
        ).stdout,
        source="docker container ls",
    )
    ids: list[str] = []
    for index, item in enumerate(listed, start=1):
        if not isinstance(item, Mapping) or not item.get("ID"):
            raise ComposePreflightError(
                f"docker container ls returned invalid record at index {index}"
            )
        ids.append(str(item["ID"]))
    if not ids:
        return []

    inspected = _run_command([docker_bin, "container", "inspect", *ids], cwd=cwd).stdout
    try:
        value = json.loads(inspected)
    except json.JSONDecodeError as exc:
        raise ComposePreflightError(
            f"docker container inspect returned invalid JSON: {exc.msg}"
        ) from exc
    if not isinstance(value, list) or not all(isinstance(item, Mapping) for item in value):
        raise ComposePreflightError("docker container inspect returned invalid JSON records")
    return [dict(item) for item in value]


def _compose_service_image_references(
    config: Mapping[str, Any], *, services: Sequence[str], project: str
) -> dict[str, str]:
    service_config = _mapping(config.get("services"))
    references: dict[str, str] = {}
    for service in services:
        image = _mapping(service_config.get(service)).get("image")
        references[service] = str(image).strip() if image else f"{project}-{service}"
    return references


def resolve_compose_image_ids(
    *,
    compose_file: Path,
    project: str,
    services: Sequence[str],
    cwd: Path,
    docker_bin: str = "docker",
) -> dict[str, str]:
    """Resolve image IDs from the current canonical Compose config and image store."""

    compose_args = [
        docker_bin,
        "compose",
        "--project-name",
        project,
        "--file",
        str(compose_file),
    ]
    if "postgres-test" in services:
        compose_args.extend(("--profile", "test"))
    config = _parse_json_object(
        _run_command([*compose_args, "config", "--format", "json"], cwd=cwd).stdout,
        source="docker compose config",
    )
    references = _compose_service_image_references(config, services=services, project=project)
    image_ids: dict[str, str] = {}
    for service, reference in references.items():
        lines = (
            _run_command(
                [docker_bin, "image", "inspect", reference, "--format", "{{.Id}}"], cwd=cwd
            )
            .stdout.strip()
            .splitlines()
        )
        if not lines or not lines[0].strip():
            raise ComposePreflightError(
                f"canonical Compose image for service {service} ({reference}) has no image ID"
            )
        image_ids[service] = lines[0].strip()
    return image_ids


def selected_services(
    *, include_postgres_test: bool = False, value: str | None = None
) -> tuple[str, ...]:
    services = (
        list(REQUIRED_SERVICES)
        if value is None
        else [item.strip() for item in value.split(",") if item.strip()]
    )
    if include_postgres_test and "postgres-test" not in services:
        services.append("postgres-test")
    return tuple(dict.fromkeys(services))


def run_preflight(
    *,
    root: Path,
    compose_file: Path,
    workdir: Path | None = None,
    services: Sequence[str] = REQUIRED_SERVICES,
    expected_project: str = EXPECTED_PROJECT,
    docker_bin: str = "docker",
) -> tuple[str, ...]:
    compose_path = compose_file if compose_file.is_absolute() else root / compose_file
    compose_path = compose_path.resolve()
    working_dir = workdir if workdir is not None else compose_path.parent
    if not working_dir.is_absolute():
        working_dir = root / working_dir
    working_dir = working_dir.resolve()
    if not compose_path.is_file():
        return (f"canonical Compose config is missing: {compose_path}",)
    try:
        containers = inspect_containers(docker_bin=docker_bin, cwd=working_dir)
        port_errors = _port_conflict_evidence(
            containers, expected_project=expected_project, selected_services=services
        )
        if port_errors:
            return tuple(dict.fromkeys(port_errors))
        image_ids = resolve_compose_image_ids(
            compose_file=compose_path,
            project=expected_project,
            services=services,
            cwd=working_dir,
            docker_bin=docker_bin,
        )
    except ComposePreflightError as exc:
        return (str(exc),)
    return validate_compose_environment(
        containers,
        image_ids,
        expected_project=expected_project,
        expected_compose_file=compose_path,
        expected_workdir=working_dir,
        services=services,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Read-only validation of the current canonical Docker Compose environment."
    )
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--compose-file", type=Path, default=DEFAULT_COMPOSE_FILE)
    parser.add_argument("--workdir", type=Path, default=None)
    parser.add_argument("--services", default=None, help="comma-separated selected services")
    parser.add_argument("--include-postgres-test", action="store_true")
    parser.add_argument("--docker-bin", default="docker")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    root = args.root.resolve()
    compose_file = (
        args.compose_file if args.compose_file.is_absolute() else root / args.compose_file
    )
    compose_file = compose_file.resolve()
    workdir = args.workdir
    if workdir is None:
        workdir = compose_file.parent
    elif not workdir.is_absolute():
        workdir = root / workdir
    workdir = workdir.resolve()
    services = selected_services(
        include_postgres_test=args.include_postgres_test, value=args.services
    )
    unknown = [service for service in services if service not in SERVICE_PORTS]
    if unknown:
        print(
            f"Compose preflight failed: unknown selected service(s): {', '.join(unknown)}",
            file=sys.stderr,
        )
        return 2
    errors = run_preflight(
        root=root,
        compose_file=compose_file,
        workdir=workdir,
        services=services,
        docker_bin=args.docker_bin,
    )
    if errors:
        print("Compose preflight failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 2
    print(
        f"Compose preflight passed: project={EXPECTED_PROJECT}, "
        f"services={','.join(services)}, config={compose_file}"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised through the CLI gate
    raise SystemExit(main())

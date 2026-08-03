from __future__ import annotations

import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from typing import Any

ROOT = Path("/workspace")
COMPOSE = ROOT / "deploy" / "compose" / "docker-compose.demo.yml"

_REPOSITORY_ROOT = Path(__file__).parents[2]
_SPEC = spec_from_file_location(
    "check_compose_environment", _REPOSITORY_ROOT / "scripts" / "check_compose_environment.py"
)
assert _SPEC and _SPEC.loader
preflight = module_from_spec(_SPEC)
sys.modules[_SPEC.name] = preflight
_SPEC.loader.exec_module(preflight)

EXPECTED_PROJECT = preflight.EXPECTED_PROJECT
REQUIRED_SERVICES = preflight.REQUIRED_SERVICES
SERVICE_PORTS = preflight.SERVICE_PORTS
main = preflight.main
validate_compose_environment = preflight.validate_compose_environment


def _container(
    service: str,
    *,
    project: str = EXPECTED_PROJECT,
    state: str = "running",
    health: str | None = "healthy",
    image: str | None = None,
    compose_file: Path = COMPOSE,
    workdir: Path = ROOT,
    host_port: int | None = None,
) -> dict[str, Any]:
    expected_host, expected_container = SERVICE_PORTS[service]
    published = expected_host if host_port is None else host_port
    labels = {
        "com.docker.compose.project": project,
        "com.docker.compose.service": service,
        "com.docker.compose.project.config_files": str(compose_file),
        "com.docker.compose.project.working_dir": str(workdir),
    }
    state_record: dict[str, Any] = {"Status": state, "Running": state == "running"}
    if health is not None:
        state_record["Health"] = {"Status": health}
    return {
        "Name": f"/{project}-{service}-1",
        "Id": f"container-{service}",
        "Image": image or f"sha256:{service}-image",
        "Config": {"Labels": labels},
        "State": state_record,
        "NetworkSettings": {
            "Ports": {
                f"{expected_container}/tcp": [{"HostPort": str(published), "HostIp": "0.0.0.0"}]
            }
        },
        "HostConfig": {
            "PortBindings": {
                f"{expected_container}/tcp": [{"HostPort": str(published), "HostIp": "0.0.0.0"}]
            }
        },
    }


def _images() -> dict[str, str]:
    return {service: f"sha256:{service}-image" for service in REQUIRED_SERVICES}


def test_canonical_compose_environment_passes() -> None:
    records = [_container(service) for service in REQUIRED_SERVICES]

    assert (
        validate_compose_environment(
            records,
            _images(),
            expected_compose_file=COMPOSE,
            expected_workdir=ROOT,
        )
        == ()
    )


def test_foreign_compose_project_owning_54330_fails_with_evidence() -> None:
    records = [_container(service) for service in REQUIRED_SERVICES]
    records.append(
        _container(
            "postgres-test",
            project="cmp159-proof-20260802",
            host_port=54330,
        )
    )
    records.append(_container("postgres-test"))
    images = {**_images(), "postgres-test": "sha256:postgres-test-image"}

    errors = validate_compose_environment(
        records,
        images,
        expected_compose_file=COMPOSE,
        expected_workdir=ROOT,
        services=(*REQUIRED_SERVICES, "postgres-test"),
    )

    assert any(
        "port 54330 required by postgres-test" in error
        and "cmp159-proof-20260802" in error
        and "postgres-test" in error
        for error in errors
    )


def test_stopped_foreign_container_does_not_conflict() -> None:
    records = [_container(service) for service in REQUIRED_SERVICES]
    records.extend(
        (
            _container(
                "postgres-test",
                project="cmp159-proof-20260802",
                state="exited",
                host_port=54330,
            ),
            _container("postgres-test"),
        )
    )
    images = {**_images(), "postgres-test": "sha256:postgres-test-image"}

    errors = validate_compose_environment(
        records,
        images,
        expected_compose_file=COMPOSE,
        expected_workdir=ROOT,
        services=(*REQUIRED_SERVICES, "postgres-test"),
    )

    assert not any("port 54330 required by postgres-test" in error for error in errors)


def test_healthcheckless_running_web_passes() -> None:
    records = [_container(service) for service in REQUIRED_SERVICES]
    records[2] = _container("web", health=None)

    assert (
        validate_compose_environment(
            records,
            _images(),
            expected_compose_file=COMPOSE,
            expected_workdir=ROOT,
        )
        == ()
    )


def test_default_workdir_uses_compose_parent() -> None:
    records = [_container(service, workdir=COMPOSE.parent) for service in REQUIRED_SERVICES]

    assert validate_compose_environment(records, _images(), expected_compose_file=COMPOSE) == ()


def test_run_preflight_default_cwd_is_compose_parent(tmp_path, monkeypatch) -> None:
    compose_file = tmp_path / "deploy" / "compose" / "docker-compose.demo.yml"
    compose_file.parent.mkdir(parents=True)
    compose_file.write_text("name: cmp-local-demo\n", encoding="utf-8")
    inspect_cwds: list[Path] = []
    image_cwds: list[Path] = []
    records = [
        _container(service, compose_file=compose_file, workdir=compose_file.parent)
        for service in REQUIRED_SERVICES
    ]
    monkeypatch.setattr(
        preflight,
        "inspect_containers",
        lambda **kwargs: inspect_cwds.append(kwargs["cwd"]) or records,
    )
    monkeypatch.setattr(
        preflight,
        "resolve_compose_image_ids",
        lambda **kwargs: image_cwds.append(kwargs["cwd"]) or _images(),
    )

    assert (
        preflight.run_preflight(
            root=tmp_path,
            compose_file=compose_file,
            services=REQUIRED_SERVICES,
        )
        == ()
    )
    assert inspect_cwds == [compose_file.parent]
    assert image_cwds == [compose_file.parent]


def test_created_required_service_is_not_accepted() -> None:
    records = [_container(service) for service in REQUIRED_SERVICES]
    records[0] = _container("postgres", state="created", health="starting")

    errors = validate_compose_environment(
        records,
        _images(),
        expected_compose_file=COMPOSE,
        expected_workdir=ROOT,
    )

    assert any("postgres" in error and "not running (state=created)" in error for error in errors)


def test_wrong_compose_config_or_workdir_fails_closed() -> None:
    records = [_container(service) for service in REQUIRED_SERVICES]
    records[1] = _container(
        "api",
        compose_file=ROOT / "other-compose.yml",
        workdir=Path("/foreign/project"),
    )

    errors = validate_compose_environment(
        records,
        _images(),
        expected_compose_file=COMPOSE,
        expected_workdir=ROOT,
    )

    assert any("api" in error and "wrong Compose config path" in error for error in errors)
    assert any("api" in error and "wrong Compose working directory" in error for error in errors)


def test_image_id_mismatch_fails() -> None:
    records = [_container(service) for service in REQUIRED_SERVICES]
    records[2] = _container("web", image="sha256:stale-web-image")

    errors = validate_compose_environment(
        records,
        _images(),
        expected_compose_file=COMPOSE,
        expected_workdir=ROOT,
    )

    assert any("web" in error and "image mismatch" in error for error in errors)


def test_cli_reports_a_single_concise_failure_without_docker(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        preflight,
        "run_preflight",
        lambda **_: ("port 54330 required by postgres-test is owned by container proof-1",),
    )

    result = main(["--root", str(ROOT), "--include-postgres-test"])
    output = capsys.readouterr()

    assert result == 2
    assert output.out == ""
    assert output.err.count("Compose preflight failed") == 1
    assert "proof-1" in output.err

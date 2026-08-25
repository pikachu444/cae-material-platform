from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any, cast

import yaml

_ROOT = Path(__file__).parents[2]


def _load_renderer() -> ModuleType:
    path = _ROOT / "scripts/render_stack_topology.py"
    spec = importlib.util.spec_from_file_location("render_stack_topology", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _topology() -> dict[str, Any]:
    return cast(
        dict[str, Any],
        yaml.safe_load((_ROOT / "deploy/stack/topology.yaml").read_text(encoding="utf-8")),
    )


def test_compose_is_exactly_generated_from_the_versioned_topology() -> None:
    renderer = _load_renderer()
    topology_path = _ROOT / "deploy/stack/topology.yaml"
    expected = renderer.render_compose(renderer.load_topology(topology_path))

    assert (_ROOT / "deploy/compose/docker-compose.demo.yml").read_text(
        encoding="utf-8"
    ) == expected


def test_topology_preserves_order_names_volumes_and_port_numbers() -> None:
    topology = _topology()

    assert topology["name"] == "cmp-local-demo"
    assert topology["service_order"] == [
        "postgres",
        "migrate",
        "api",
        "worker",
        "reference-plugins",
        "seed",
        "web",
    ]
    assert topology["volumes"] == {
        "database": "cmp_demo_postgres",
        "objects": "cmp_demo_objects",
    }
    assert {name: value["host"] for name, value in topology["ports"].items()} == {
        "web": 5173,
        "api": 8000,
        "postgres": 54329,
        "otlp": 4318,
        "metrics": 8889,
    }


def test_host_registry_and_compose_share_commands_health_and_application_environment() -> None:
    topology = _topology()
    host = topology["host"]

    assert host["execution_order"] == topology["service_order"]
    assert host["processes"]["api"] == {
        "command": ["{python}", "-m", "cmp.apps.api"],
        "health_path": "/api/v1/health",
    }
    assert host["processes"]["worker"]["command"] == [
        "{python}",
        "-m",
        "cmp.apps.worker",
    ]
    assert host["processes"]["web"]["health_path"] == "/.cmp/health"
    assert host["external_services"] == {
        "otel-collector": {
            "mode": "external-opt-in",
            "endpoint_environment": "OTEL_EXPORTER_OTLP_ENDPOINT",
            "reason": "host runtime does not manage a collector process",
        }
    }

    renderer = _load_renderer()
    rendered = renderer.render_compose(topology)
    compose = yaml.safe_load(rendered)
    common = topology["application_environment"]
    for name, value in common.items():
        assert compose["services"]["api"]["environment"][name] == value
        assert compose["services"]["worker"]["environment"][name] == value
    assert "status" not in compose


def test_compose_status_registry_covers_the_default_profile_exactly() -> None:
    topology = _topology()
    status = topology["compose"]["status"]

    assert set(status["running_services"] + status["completed_services"]) == set(
        topology["compose"]["services"]
    ) - {"postgres-test", "restore-drill"}


def test_host_cli_does_not_duplicate_topology_ports_process_modules_or_common_settings() -> None:
    source = (_ROOT / "backend/src/cmp/tools/stack.py").read_text(encoding="utf-8")

    for duplicated_literal in (
        "54329",
        "8000",
        "5173",
        "cmp.apps.api",
        "cmp.apps.worker",
        "cmp.apps.web",
        "CMP_BULK_EXPORT_INLINE_MAXIMUM_BYTES",
    ):
        assert duplicated_literal not in source


def test_only_the_web_front_door_is_lan_exposed() -> None:
    topology = _topology()

    assert topology["ports"]["web"]["exposure"] == "private-lan-front-door"
    assert all(
        port["exposure"] == "loopback-only"
        for name, port in topology["ports"].items()
        if name != "web"
    )
    compose = topology["compose"]["services"]
    assert compose["postgres"]["ports"] == ["127.0.0.1:54329:5432"]
    assert compose["api"]["ports"] == ["127.0.0.1:8000:8000"]
    assert compose["web"]["ports"] == ["5173:5173"]


def test_server_profile_forbids_demo_identity_seed_and_unattested_plugins() -> None:
    server = _topology()["profiles"]["server"]

    assert server == {
        "environment": "production",
        "demo_identity": False,
        "seed": False,
        "requires_external_auth": True,
        "requires_external_secret_file": True,
        "allow_unattested_plugins": False,
    }


def test_web_image_uses_node_only_to_build_and_python_to_serve() -> None:
    dockerfile = (_ROOT / "deploy/compose/Dockerfile.web").read_text(encoding="utf-8")

    assert dockerfile.count("FROM ") == 2
    assert dockerfile.startswith("FROM node:24.19.0-")
    assert " AS build\n" in dockerfile
    assert "FROM python:3.12.14-" in dockerfile
    assert "COPY --from=build /app/apps/web/dist /app/web" in dockerfile
    assert 'CMD ["cmp-web"]' in dockerfile
    assert 'CMD ["npm"' not in dockerfile

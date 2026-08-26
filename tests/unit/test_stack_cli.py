from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from subprocess import CompletedProcess

import pytest
from cmp.tools import stack

_ROOT = Path(__file__).parents[2]


def _paths(tmp_path: Path) -> stack.StackPaths:
    state = tmp_path / "state with spaces"
    data = tmp_path / "data with spaces"
    web = tmp_path / "web build with spaces"
    web.mkdir()
    (web / "index.html").write_text("CMP", encoding="utf-8")
    return stack.StackPaths(
        root=_ROOT,
        state=state,
        data=data,
        logs=state / "logs",
        objects=data / "objects",
        postgres=data / "postgres-16",
        web_dist=web,
    )


def _options(
    tmp_path: Path,
    *,
    profile: stack.Profile = "demo",
    runtime: stack.Runtime = "host",
) -> stack.StackOptions:
    postgres_bin = tmp_path / "PostgreSQL 16" / "bin"
    postgres_bin.mkdir(parents=True)
    suffix = ".exe" if os.name == "nt" else ""
    for name in ("postgres", "initdb", "pg_ctl", "pg_isready", "psql", "createdb"):
        (postgres_bin / f"{name}{suffix}").write_text("", encoding="utf-8")
    return stack.StackOptions(
        profile=profile,
        runtime=runtime,
        paths=_paths(tmp_path),
        postgres_bin=postgres_bin,
        listen_address="127.0.0.1",
        auth_config=None,
        secret_file=None,
        json_output=False,
    )


def test_host_doctor_accepts_tool_and_data_paths_with_spaces(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    options = _options(tmp_path)
    monkeypatch.setattr(stack, "_available_port", lambda address, port: f"{address}:{port}")
    monkeypatch.setattr(stack, "_postgres_major_version", lambda _: "16.15")

    checks = stack._doctor(options)

    assert not [check for check in checks if check.status == "error"]
    assert any("PostgreSQL 16" in check.detail for check in checks if check.name == "postgres-bin")
    assert any(check.detail == "16.15" for check in checks if check.name == "postgres-version")


def test_host_doctor_rejects_a_non_16_postgres_runtime(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    options = _options(tmp_path)
    monkeypatch.setattr(stack, "_available_port", lambda address, port: f"{address}:{port}")
    monkeypatch.setattr(
        stack,
        "_postgres_major_version",
        lambda _: (_ for _ in ()).throw(
            stack.StackError("PostgreSQL 16.x is required, got: postgres (PostgreSQL) 17.6")
        ),
    )

    checks = stack._doctor(options)

    assert [check.name for check in checks if check.status == "error"] == ["postgres-version"]


def test_host_doctor_reports_an_incomplete_postgres_tool_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    options = _options(tmp_path)
    assert options.postgres_bin is not None
    missing = options.postgres_bin / ("psql.exe" if os.name == "nt" else "psql")
    missing.unlink()
    monkeypatch.setattr(stack, "_available_port", lambda address, port: f"{address}:{port}")
    monkeypatch.setattr(stack, "_postgres_major_version", lambda _: "16.15")

    checks = stack._doctor(options)

    failure = next(check for check in checks if check.name == "postgres-bin")
    assert failure.status == "error"
    assert str(missing) in failure.detail


def test_server_profile_fails_closed_without_external_auth_and_secrets(tmp_path: Path) -> None:
    options = _options(tmp_path, profile="server")

    with pytest.raises(stack.StackError, match="--auth-config and --secret-file"):
        stack._server_configuration(options)


@pytest.mark.parametrize(
    ("extra", "message"),
    [
        ({"CMP_DEMO_IDENTITY": "true"}, "forbids Demo identity and seed"),
        ({"CMP_DEMO_FIXTURE_STAMP": "server-must-not-seed"}, "forbids Demo identity and seed"),
        ({"CMP_PLUGIN_RUNTIME": "subprocess"}, "without an attested sandbox"),
    ],
)
def test_server_profile_rejects_demo_or_unattested_plugin_settings(
    tmp_path: Path, extra: dict[str, str], message: str
) -> None:
    options = _options(tmp_path, profile="server")
    token = tmp_path / "worker.token"
    token.write_text("token", encoding="utf-8")
    auth = {
        "CMP_OIDC_ISSUER": "https://identity.example.test",
        "CMP_OIDC_AUDIENCE": "cmp-server",
        "CMP_OIDC_JWKS_URL": "https://identity.example.test/jwks.json",
        "CMP_WORKER_ACCESS_TOKEN_FILE": str(token),
        "CMP_OBJECT_STORE_BACKEND": "s3",
        "CMP_S3_BUCKET": "cmp-server",
        "CMP_S3_KMS_KEY_ID": "test-key-id",
        **extra,
    }
    secret = {
        "database_owner_password": "owner-password",
        "database_application_password": "application-password",
        "upload_capability_secret": "upload-capability",
        "artifact_transfer_secret": "artifact-transfer",
    }
    auth_path = tmp_path / "auth.json"
    secret_path = tmp_path / "secret.json"
    auth_path.write_text(json.dumps(auth), encoding="utf-8")
    secret_path.write_text(json.dumps(secret), encoding="utf-8")
    auth_options = stack.StackOptions(
        profile=options.profile,
        runtime=options.runtime,
        paths=options.paths,
        postgres_bin=options.postgres_bin,
        listen_address=options.listen_address,
        auth_config=auth_path,
        secret_file=secret_path,
        json_output=options.json_output,
    )

    with pytest.raises(stack.StackError, match=message):
        stack._server_configuration(auth_options)


@pytest.mark.parametrize(
    ("name", "message"),
    [
        ("CMP_DEMO_IDENTITY", "inherited Demo settings"),
        ("CMP_PLUGIN_RUNTIME", "inherited plugin settings"),
    ],
)
def test_server_profile_rejects_inherited_demo_or_plugin_environment(
    monkeypatch: pytest.MonkeyPatch, name: str, message: str
) -> None:
    monkeypatch.setenv(name, "unexpected")

    with pytest.raises(stack.StackError, match=message):
        stack._server_environment_guard(os.environ)


@pytest.mark.parametrize(
    "address", ["0.0.0.0", "8.8.8.8", "169.254.1.1", "127.0.0.2", "::1"]
)
def test_listen_address_rejects_implicit_public_or_unsupported_bindings(address: str) -> None:
    with pytest.raises(stack.StackError):
        stack._validate_listen_address(address)


@pytest.mark.parametrize("runtime", ["host", "compose"])
def test_status_rejects_a_noncanonical_loopback_address(
    tmp_path: Path, runtime: stack.Runtime
) -> None:
    base_options = _options(tmp_path, runtime=runtime)
    options = stack.StackOptions(
        profile=base_options.profile,
        runtime=base_options.runtime,
        paths=base_options.paths,
        postgres_bin=base_options.postgres_bin,
        listen_address="127.0.0.2",
        auth_config=base_options.auth_config,
        secret_file=base_options.secret_file,
        json_output=base_options.json_output,
    )

    with pytest.raises(stack.StackError, match=r"supported loopback.*127\.0\.0\.1"):
        stack._access_status(options)


def test_host_state_contains_no_database_or_application_secret(tmp_path: Path) -> None:
    options = _options(tmp_path)
    state = stack.HostState(
        schema_version=1,
        profile="demo",
        runtime="host",
        listen_address="127.0.0.1",
        postgres_bin=str(options.postgres_bin),
        processes={"api": stack.ProcessState(123, "api.log", "windows-filetime:456")},
    )

    stack._write_state(options, state)

    content = stack._state_path(options).read_text(encoding="utf-8")
    assert "password" not in content.lower()
    assert "capability" not in content.lower()
    assert json.loads(content)["processes"]["api"]["pid"] == 123


def test_down_when_stopped_preserves_existing_database_and_objects(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    options = _options(tmp_path)
    sentinel = options.paths.data / "postgres-16" / "preserve.me"
    sentinel.parent.mkdir(parents=True)
    sentinel.write_text("immutable", encoding="utf-8")

    stack._host_down(options)

    assert sentinel.read_text(encoding="utf-8") == "immutable"
    assert "data was not changed" in capsys.readouterr().out


def test_failed_up_stops_started_processes_and_postgres_without_deleting_data(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    options = _options(tmp_path)
    stopped: list[tuple[int, str]] = []
    postgres_stops: list[Path | None] = []
    sentinel = options.paths.data / "preserve.me"
    sentinel.parent.mkdir(parents=True)
    sentinel.write_text("keep", encoding="utf-8")
    monkeypatch.setattr(stack, "_doctor", lambda _: [stack.DoctorCheck("all", "ok", "ok")])
    monkeypatch.setattr(stack, "_runtime_environment", lambda _: ({}, stack._demo_secrets()))
    monkeypatch.setattr(stack, "_initialize_postgres", lambda *args, **kwargs: None)
    monkeypatch.setattr(stack, "_migrate_and_bootstrap", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        stack,
        "_start_process",
        lambda *args, **kwargs: stack.ProcessState(101, "api.log", "windows-filetime:2026"),
    )
    monkeypatch.setattr(
        stack,
        "_wait_http",
        lambda *args, **kwargs: (_ for _ in ()).throw(stack.StackError("api unhealthy")),
    )
    monkeypatch.setattr(stack, "_stop_pid", lambda pid, token: stopped.append((pid, token)))
    monkeypatch.setattr(
        stack,
        "_stop_postgres",
        lambda _options, *, postgres_bin: postgres_stops.append(postgres_bin),
    )

    with pytest.raises(stack.StackError, match="api unhealthy"):
        stack._host_up(options, open_browser=False)

    assert stopped == [(101, "windows-filetime:2026")]
    assert postgres_stops == [options.postgres_bin]
    assert sentinel.read_text(encoding="utf-8") == "keep"
    assert not stack._state_path(options).exists()


def test_ctrl_c_returns_standard_cancellation_exit_code(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        stack,
        "_host_up",
        lambda *args, **kwargs: (_ for _ in ()).throw(KeyboardInterrupt()),
    )

    result = stack.main(
        [
            "--profile",
            "demo",
            "--runtime",
            "host",
            "--root",
            str(_ROOT),
            "--state-dir",
            str(tmp_path / "state"),
            "--data-dir",
            str(tmp_path / "data"),
            "up",
            "--no-browser",
        ]
    )

    assert result == 130


def test_status_reports_only_web_as_remote_front_door(tmp_path: Path) -> None:
    options = _options(tmp_path)
    stack._write_state(
        options,
        stack.HostState(
            schema_version=1,
            profile="demo",
            runtime="host",
            listen_address="192.168.10.12",
            postgres_bin=str(options.postgres_bin),
            processes={},
        ),
    )

    status = stack._host_status(options)

    assert status["local_url"] == "http://192.168.10.12:5173"
    assert status["lan_url"] == "http://192.168.10.12:5173"
    assert status["exposed_ports"] == {"web": 5173}
    assert status["loopback_ports"] == {"api": 8000, "postgres": 54329}
    assert status["identity"] == "synthetic-demo-only"
    assert status["observability"] == {
        "mode": "external-opt-in",
        "endpoint_environment": "OTEL_EXPORTER_OTLP_ENDPOINT",
        "reason": "host runtime does not manage a collector process",
        "configured_endpoint": None,
    }


def test_compose_status_reports_shared_urls_ports_and_managed_observability(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    base_options = _options(tmp_path, runtime="compose")
    options = stack.StackOptions(
        profile=base_options.profile,
        runtime=base_options.runtime,
        paths=base_options.paths,
        postgres_bin=base_options.postgres_bin,
        listen_address="192.168.10.12",
        auth_config=base_options.auth_config,
        secret_file=base_options.secret_file,
        json_output=base_options.json_output,
    )
    running = {"otel-collector", "postgres", "api", "worker", "web"}
    completed_services = {"migrate", "reference-plugins", "seed"}
    entries = [{"Service": name, "State": "running", "Health": "healthy"} for name in running] + [
        {"Service": name, "State": "exited", "ExitCode": 0} for name in completed_services
    ]
    environments: list[dict[str, str]] = []

    def completed_command(command: list[str], **kwargs: object) -> CompletedProcess[str]:
        environment = kwargs.get("environment")
        assert isinstance(environment, dict)
        environments.append(environment)
        return CompletedProcess(command, 0, json.dumps(entries), "")

    monkeypatch.setattr(stack, "_run", completed_command)

    status = stack._compose_status(options)

    assert status["state"] == "running"
    assert status["local_url"] == "http://192.168.10.12:5173"
    assert status["lan_url"] == "http://192.168.10.12:5173"
    assert status["remote_access"] == "requires Private/Domain LocalSubnet firewall rule"
    assert environments[0]["CMP_STACK_LISTEN_ADDRESS"] == "192.168.10.12"
    assert status["exposed_ports"] == {"web": 5173}
    assert status["loopback_ports"] == {
        "api": 8000,
        "postgres": 54329,
        "otlp": 4318,
        "metrics": 8889,
    }
    assert status["observability"]["mode"] == "managed"


def test_compose_status_is_degraded_when_a_topology_service_is_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    options = _options(tmp_path, runtime="compose")
    monkeypatch.setattr(
        stack,
        "_run",
        lambda *args, **kwargs: CompletedProcess(
            args[0],
            0,
            json.dumps([{"Service": "web", "State": "running", "Health": "healthy"}]),
            "",
        ),
    )

    assert stack._compose_status(options)["state"] == "degraded"


def test_pid_reuse_is_not_treated_as_the_owned_process(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(stack, "_process_token", lambda _: "windows-filetime:new")

    assert not stack._is_running(123, "windows-filetime:old")


def test_server_compose_refuses_to_start_before_owned_spa_auth_exists(tmp_path: Path) -> None:
    options = _options(tmp_path, profile="server", runtime="compose")

    with pytest.raises(stack.StackError, match="#215 SPA OIDC"):
        stack._compose_action(options, "up", lines=10)


def test_compose_doctor_runs_the_existing_environment_preflight(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    options = _options(tmp_path, runtime="compose")
    commands: list[list[str]] = []

    def completed(command: list[object], **_: object) -> object:
        rendered = [str(item) for item in command]
        commands.append(rendered)
        return CompletedProcess(rendered, 0, "ok\n", "")

    monkeypatch.setattr(stack, "_run", completed)
    monkeypatch.setattr(shutil, "which", lambda _: "docker")

    checks = stack._doctor(options)

    assert not [check for check in checks if check.status == "error"]
    assert any(check.name == "compose-preflight" for check in checks)
    assert any(Path(command[-1]).name == "check_compose_environment.py" for command in commands)

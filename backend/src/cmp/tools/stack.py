"""Run the canonical CMP stack through Compose or local host processes."""

from __future__ import annotations

import argparse
import ctypes
import ctypes.wintypes
import ipaddress
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
import webbrowser
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal, cast
from urllib.error import URLError
from urllib.parse import quote
from urllib.request import urlopen

import sqlalchemy as sa
import yaml

from cmp.bootstrap.database import ensure_application_role, grant_application_privileges

Profile = Literal["demo", "server"]
Runtime = Literal["compose", "host"]

_SERVER_AUTH_REQUIRED = (
    "CMP_OIDC_ISSUER",
    "CMP_OIDC_AUDIENCE",
    "CMP_OIDC_JWKS_URL",
    "CMP_WORKER_ACCESS_TOKEN_FILE",
    "CMP_OBJECT_STORE_BACKEND",
    "CMP_S3_BUCKET",
    "CMP_S3_KMS_KEY_ID",
)
_SECRET_REQUIRED = (
    "database_owner_password",
    "database_application_password",
    "upload_capability_secret",
    "artifact_transfer_secret",
)


class StackError(RuntimeError):
    """Expected operator-correctable stack failure."""


def _platform_attribute(module: object, name: str) -> Any:
    """Resolve an OS-specific stdlib attribute without cross-platform typing drift."""
    return getattr(module, name)


@dataclass(frozen=True, slots=True)
class StackPaths:
    root: Path
    state: Path
    data: Path
    logs: Path
    objects: Path
    postgres: Path
    web_dist: Path


@dataclass(frozen=True, slots=True)
class StackOptions:
    profile: Profile
    runtime: Runtime
    paths: StackPaths
    postgres_bin: Path | None
    listen_address: str
    auth_config: Path | None
    secret_file: Path | None
    json_output: bool


@dataclass(frozen=True, slots=True)
class ProcessState:
    pid: int
    log: str
    token: str


@dataclass(frozen=True, slots=True)
class HostState:
    schema_version: int
    profile: Profile
    runtime: Runtime
    listen_address: str
    postgres_bin: str
    processes: dict[str, ProcessState]


@dataclass(frozen=True, slots=True)
class DoctorCheck:
    name: str
    status: Literal["ok", "error"]
    detail: str


def _repository_root(start: Path) -> Path:
    current = start.resolve()
    for candidate in (current, *current.parents):
        if (candidate / "pyproject.toml").is_file() and (candidate / "deploy").is_dir():
            return candidate
    raise StackError(f"repository root not found from {start}")


def _platform_root(kind: Literal["state", "data"]) -> Path:
    if os.name == "nt":
        base = os.getenv("LOCALAPPDATA")
        if not base:
            raise StackError("LOCALAPPDATA is required to resolve Windows stack paths")
        return Path(base) / "CAE Material Platform" / kind
    variable = "XDG_STATE_HOME" if kind == "state" else "XDG_DATA_HOME"
    configured = os.getenv(variable)
    if configured:
        return Path(configured) / "cae-material-platform"
    suffix = ".local/state" if kind == "state" else ".local/share"
    return Path.home() / suffix / "cae-material-platform"


def resolve_paths(
    *,
    root: Path,
    state_dir: Path | None,
    data_dir: Path | None,
    web_dist: Path | None,
) -> StackPaths:
    repository = _repository_root(root)
    state = (state_dir or _platform_root("state")).resolve()
    data = (data_dir or _platform_root("data")).resolve()
    return StackPaths(
        root=repository,
        state=state,
        data=data,
        logs=state / "logs",
        objects=data / "objects",
        postgres=data / "postgres-16",
        web_dist=(web_dist or repository / "apps/web/dist").resolve(),
    )


def _load_topology(root: Path) -> dict[str, Any]:
    path = root / "deploy/stack/topology.yaml"
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict) or document.get("schema_version") != 1:
        raise StackError(f"invalid stack topology: {path}")
    return document


def _topology_port(options: StackOptions, name: str) -> int:
    try:
        value = _load_topology(options.paths.root)["ports"][name]["host"]
    except (KeyError, TypeError) as error:
        raise StackError(f"stack topology has no host port for {name}") from error
    if not isinstance(value, int) or not 1 <= value <= 65535:
        raise StackError(f"stack topology has an invalid host port for {name}: {value}")
    return value


def _host_command(
    options: StackOptions,
    key: str,
    *,
    process: str | None = None,
) -> list[str]:
    topology = _load_topology(options.paths.root)
    try:
        raw = topology["host"]["processes"][process][key] if process else topology["host"][key]
    except (KeyError, TypeError) as error:
        label = f"process {process} {key}" if process else key
        raise StackError(f"stack topology has no host {label}") from error
    if not isinstance(raw, list) or not raw or not all(isinstance(item, str) for item in raw):
        raise StackError(f"stack topology host command is invalid: {process or key}")
    values = {
        "python": sys.executable,
        "root": str(options.paths.root),
        "web_dist": str(options.paths.web_dist),
        "api_port": str(_topology_port(options, "api")),
        "web_port": str(_topology_port(options, "web")),
        "listen_address": options.listen_address,
    }
    try:
        return [item.format_map(values) for item in raw]
    except KeyError as error:
        raise StackError(f"unknown host command placeholder: {error.args[0]}") from error


def _host_seed_commands(options: StackOptions) -> list[list[str]]:
    topology = _load_topology(options.paths.root)
    raw = topology.get("host", {}).get("demo_seed_commands")
    if not isinstance(raw, list):
        raise StackError("stack topology host demo_seed_commands must be a list")
    values = {
        "python": sys.executable,
        "root": str(options.paths.root),
        "api_port": str(_topology_port(options, "api")),
    }
    commands: list[list[str]] = []
    for command in raw:
        if (
            not isinstance(command, list)
            or not command
            or not all(isinstance(item, str) for item in command)
        ):
            raise StackError("stack topology contains an invalid host Demo seed command")
        try:
            commands.append([item.format_map(values) for item in command])
        except KeyError as error:
            raise StackError(f"unknown Demo seed command placeholder: {error.args[0]}") from error
    return commands


def _host_execution_order(options: StackOptions) -> list[str]:
    raw = _load_topology(options.paths.root).get("host", {}).get("execution_order")
    if not isinstance(raw, list) or not raw or not all(isinstance(item, str) for item in raw):
        raise StackError("stack topology host execution_order must be a non-empty string list")
    return cast(list[str], raw)


def _host_process_order(options: StackOptions) -> list[str]:
    processes = _load_topology(options.paths.root).get("host", {}).get("processes")
    if not isinstance(processes, dict):
        raise StackError("stack topology host processes must be a mapping")
    return [name for name in _host_execution_order(options) if name in processes]


def _host_health_path(options: StackOptions, process: str) -> str | None:
    raw = (
        _load_topology(options.paths.root)
        .get("host", {})
        .get("processes", {})
        .get(process, {})
        .get("health_path")
    )
    if raw is None:
        return None
    if not isinstance(raw, str) or not raw.startswith("/"):
        raise StackError(f"stack topology has invalid health path for {process}")
    return raw


def _read_json_mapping(path: Path, *, label: str) -> dict[str, str]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise StackError(f"{label} is unreadable JSON: {path}: {error}") from error
    if not isinstance(raw, dict) or not all(
        isinstance(key, str) and isinstance(value, str) and value for key, value in raw.items()
    ):
        raise StackError(f"{label} must be a JSON object of non-empty string values: {path}")
    return cast(dict[str, str], raw)


def _server_configuration(options: StackOptions) -> tuple[dict[str, str], dict[str, str]]:
    if options.auth_config is None or options.secret_file is None:
        raise StackError("server profile requires --auth-config and --secret-file")
    auth = _read_json_mapping(options.auth_config, label="server auth config")
    secret = _read_json_mapping(options.secret_file, label="server secret file")
    missing_auth = [name for name in _SERVER_AUTH_REQUIRED if not auth.get(name)]
    missing_secret = [name for name in _SECRET_REQUIRED if not secret.get(name)]
    if missing_auth or missing_secret:
        raise StackError(
            "server profile configuration is incomplete: "
            f"auth={missing_auth or 'ok'} secret={missing_secret or 'ok'}"
        )
    if auth["CMP_OBJECT_STORE_BACKEND"].lower() != "s3":
        raise StackError("server profile requires CMP_OBJECT_STORE_BACKEND=s3")
    demo_keys = sorted(name for name in auth if name.startswith("CMP_DEMO_"))
    if demo_keys:
        raise StackError(f"server profile forbids Demo identity and seed settings: {demo_keys}")
    plugin_keys = sorted(name for name in auth if name.startswith("CMP_PLUGIN_"))
    if plugin_keys:
        raise StackError(
            f"server profile forbids plugin settings without an attested sandbox: {plugin_keys}"
        )
    worker_token = Path(auth["CMP_WORKER_ACCESS_TOKEN_FILE"])
    if not worker_token.is_file():
        raise StackError(f"server worker token file is missing: {worker_token}")
    return auth, secret


def _server_environment_guard(environment: Mapping[str, str]) -> str:
    demo_keys = sorted(name for name in environment if name.startswith("CMP_DEMO_"))
    if demo_keys:
        raise StackError(f"server profile forbids inherited Demo settings: {demo_keys}")
    plugin_keys = sorted(name for name in environment if name.startswith("CMP_PLUGIN_"))
    if plugin_keys:
        raise StackError(
            "server profile forbids inherited plugin settings without an attested sandbox: "
            f"{plugin_keys}"
        )
    return "no inherited Demo or unattested plugin settings"


def _validate_listen_address(value: str) -> ipaddress.IPv4Address:
    try:
        address = ipaddress.ip_address(value)
    except ValueError as error:
        raise StackError(f"listen address must be an explicit IPv4 address: {value}") from error
    if not isinstance(address, ipaddress.IPv4Address):
        raise StackError("only explicit IPv4 listen addresses are supported")
    private_networks = (
        ipaddress.ip_network("10.0.0.0/8"),
        ipaddress.ip_network("172.16.0.0/12"),
        ipaddress.ip_network("192.168.0.0/16"),
    )
    if address.is_loopback and address != ipaddress.ip_address("127.0.0.1"):
        raise StackError("the supported loopback listen address is 127.0.0.1")
    if not address.is_loopback and not any(address in network for network in private_networks):
        raise StackError("listen address must be loopback or a Private/Domain LAN address")
    return address


def _postgres_executable(bin_dir: Path, name: str) -> Path:
    suffix = ".exe" if os.name == "nt" else ""
    candidate = bin_dir / f"{name}{suffix}"
    if not candidate.is_file():
        raise StackError(f"PostgreSQL executable is missing: {candidate}")
    return candidate


def _postgres_major_version(bin_dir: Path) -> str:
    postgres = _postgres_executable(bin_dir, "postgres")
    result = _run([postgres, "--version"], cwd=bin_dir, capture=True)
    output = result.stdout.strip()
    fields = output.rsplit(" ", 1)
    if len(fields) != 2 or not fields[1].startswith("16."):
        raise StackError(f"PostgreSQL 16.x is required, got: {output or 'empty version output'}")
    return fields[1]


def _available_port(address: str, port: int) -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.bind((address, port))
    except OSError as error:
        raise StackError(f"port is unavailable: {address}:{port}: {error}") from error
    return f"{address}:{port} available"


def _run(
    command: Sequence[str | Path],
    *,
    cwd: Path,
    environment: Mapping[str, str] | None = None,
    capture: bool = False,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [str(item) for item in command],
        cwd=cwd,
        env=dict(environment) if environment is not None else None,
        text=True,
        capture_output=capture,
        check=False,
    )
    if check and result.returncode:
        detail = (result.stderr or result.stdout or "").strip()
        raise StackError(f"command failed ({result.returncode}): {command[0]}: {detail}")
    return result


def _doctor(options: StackOptions) -> list[DoctorCheck]:
    checks: list[DoctorCheck] = []

    def check(name: str, action: Any) -> None:
        try:
            detail = str(action())
        except (OSError, StackError, subprocess.SubprocessError, ValueError) as error:
            checks.append(DoctorCheck(name, "error", str(error)))
        else:
            checks.append(DoctorCheck(name, "ok", detail))

    topology = _load_topology(options.paths.root)
    check("topology", lambda: f"schema={topology['schema_version']}")
    check(
        "compose-drift",
        lambda: _run(
            [
                sys.executable,
                options.paths.root / "scripts/render_stack_topology.py",
                "--check",
            ],
            cwd=options.paths.root,
            capture=True,
        ).stdout.strip(),
    )
    check("listen", lambda: str(_validate_listen_address(options.listen_address)))
    if options.profile == "server":
        check("server-config", lambda: _server_configuration(options) and "fail-closed config ok")
        check("server-environment", lambda: _server_environment_guard(os.environ))
    if options.runtime == "compose":
        check(
            "docker",
            lambda: shutil.which("docker") or (_ for _ in ()).throw(StackError("docker not found")),
        )
        check(
            "compose-config",
            lambda: (
                _run(
                    [
                        "docker",
                        "compose",
                        "-f",
                        options.paths.root / "deploy/compose/docker-compose.demo.yml",
                        "config",
                        "--quiet",
                    ],
                    cwd=options.paths.root,
                    environment=_compose_environment(options),
                )
                and "valid"
            ),
        )
        check(
            "compose-preflight",
            lambda: _run(
                [
                    sys.executable,
                    options.paths.root / "scripts/check_compose_environment.py",
                ],
                cwd=options.paths.root,
                environment=_compose_environment(options),
                capture=True,
            ).stdout.strip(),
        )
        if options.profile == "server":
            checks.append(
                DoctorCheck(
                    "server-spa-auth",
                    "error",
                    "SPA OIDC Code+PKCE is owned by #215; server Compose cannot start yet",
                )
            )
    else:
        check(
            "postgres-port",
            lambda: _available_port("127.0.0.1", _topology_port(options, "postgres")),
        )
        check("api-port", lambda: _available_port("127.0.0.1", _topology_port(options, "api")))
        check(
            "web-port",
            lambda: _available_port(options.listen_address, _topology_port(options, "web")),
        )
        if options.postgres_bin is None:
            checks.append(DoctorCheck("postgres-bin", "error", "--postgres-bin is required"))
        else:
            names = cast(list[str], topology["host"]["postgres_executables"])
            check(
                "postgres-bin",
                lambda: ", ".join(
                    str(_postgres_executable(options.postgres_bin or Path(), name))
                    for name in names
                ),
            )
            check(
                "postgres-version",
                lambda: _postgres_major_version(options.postgres_bin or Path()),
            )
        check(
            "web-build",
            lambda: (
                options.paths.web_dist / "index.html"
                if (options.paths.web_dist / "index.html").is_file()
                else (_ for _ in ()).throw(
                    StackError(f"immutable Web build is missing: {options.paths.web_dist}")
                )
            ),
        )
        if options.profile == "server":
            checks.append(
                DoctorCheck(
                    "server-spa-auth",
                    "error",
                    "SPA OIDC Code+PKCE is owned by #215; server host cannot start yet",
                )
            )
    return checks


def _state_path(options: StackOptions) -> Path:
    return options.paths.state / f"{options.profile}-{options.runtime}.json"


def _write_state(options: StackOptions, state: HostState) -> None:
    options.paths.state.mkdir(parents=True, exist_ok=True)
    payload = asdict(state)
    _state_path(options).write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _read_state(options: StackOptions) -> HostState | None:
    path = _state_path(options)
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise StackError(f"stack state is unreadable JSON: {path}: {error}") from error
    if not isinstance(raw, dict):
        raise StackError(f"stack state must be a JSON object: {path}")
    if raw.get("schema_version") != 1 or raw.get("profile") != options.profile:
        raise StackError(f"invalid or foreign stack state: {path}")
    try:
        processes = {
            name: ProcessState(
                pid=int(value["pid"]),
                log=str(value["log"]),
                token=str(value["token"]),
            )
            for name, value in raw.get("processes", {}).items()
        }
    except (KeyError, TypeError, ValueError) as error:
        raise StackError(f"stack state has invalid process metadata: {path}") from error
    return HostState(
        schema_version=1,
        profile=cast(Profile, raw["profile"]),
        runtime=cast(Runtime, raw["runtime"]),
        listen_address=str(raw["listen_address"]),
        postgres_bin=str(raw["postgres_bin"]),
        processes=processes,
    )


def _process_token(pid: int) -> str:
    if os.name == "nt":
        win_dll = cast(Any, _platform_attribute(ctypes, "WinDLL"))
        get_last_error = cast(Any, _platform_attribute(ctypes, "get_last_error"))
        kernel32 = win_dll("kernel32", use_last_error=True)
        process = kernel32.OpenProcess(0x1000, False, pid)
        if not process:
            raise OSError(get_last_error(), f"cannot open process {pid}")
        try:
            creation = ctypes.wintypes.FILETIME()
            exit_time = ctypes.wintypes.FILETIME()
            kernel = ctypes.wintypes.FILETIME()
            user = ctypes.wintypes.FILETIME()
            if not kernel32.GetProcessTimes(
                process,
                ctypes.byref(creation),
                ctypes.byref(exit_time),
                ctypes.byref(kernel),
                ctypes.byref(user),
            ):
                raise OSError(get_last_error(), f"cannot inspect process {pid}")
            value = (creation.dwHighDateTime << 32) | creation.dwLowDateTime
            return f"windows-filetime:{value}"
        finally:
            kernel32.CloseHandle(process)
    stat_path = Path(f"/proc/{pid}/stat")
    try:
        stat = stat_path.read_text(encoding="ascii")
    except OSError as error:
        raise OSError(f"cannot inspect process {pid}: {error}") from error
    close = stat.rfind(")")
    fields = stat[close + 2 :].split()
    if close < 0 or len(fields) < 20:
        raise OSError(f"cannot parse process identity: {stat_path}")
    return f"linux-starttime:{fields[19]}"


def _is_running(pid: int, token: str) -> bool:
    try:
        return _process_token(pid) == token
    except OSError:
        return False


def _wait_http(url: str, *, timeout_seconds: float = 90.0) -> None:
    deadline = time.monotonic() + timeout_seconds
    last: Exception | None = None
    while time.monotonic() < deadline:
        try:
            with urlopen(url, timeout=2) as response:
                if response.status == 200:
                    return
        except (OSError, URLError) as error:
            last = error
        time.sleep(0.5)
    raise StackError(f"health check timed out: {url}: {last}")


def _database_url(*, user: str, password: str, port: int) -> str:
    return f"postgresql+psycopg://{quote(user)}:{quote(password)}@127.0.0.1:{port}/cmp"


def _demo_secrets() -> dict[str, str]:
    return {
        "database_owner_password": "cmp_owner_development_only",
        "database_application_password": "cmp_app_development_only",
        "upload_capability_secret": "demo-upload-capability-secret-not-for-production-2026",
        "artifact_transfer_secret": "demo-artifact-transfer-secret-not-for-production-2026",
    }


def _runtime_environment(options: StackOptions) -> tuple[dict[str, str], dict[str, str]]:
    base = os.environ.copy()
    common = _load_topology(options.paths.root).get("application_environment")
    if not isinstance(common, dict) or not all(
        isinstance(name, str) and isinstance(value, str) for name, value in common.items()
    ):
        raise StackError("stack topology application_environment must contain string values")
    base.update(cast(dict[str, str], common))
    if options.profile == "demo":
        auth: dict[str, str] = {}
        secret = _demo_secrets()
        base.update({"CMP_ENVIRONMENT": "demo", "CMP_DEMO_IDENTITY": "true"})
    else:
        auth, secret = _server_configuration(options)
        _server_environment_guard(base)
        for name in tuple(base):
            if name.startswith(("CMP_DEMO_", "CMP_PLUGIN_")):
                base.pop(name)
        base.update(auth)
        base.update({"CMP_ENVIRONMENT": "production", "CMP_DEMO_IDENTITY": "false"})
    base.update(
        {
            "CMP_API_HOST": "127.0.0.1",
            "CMP_API_PORT": str(_topology_port(options, "api")),
            "CMP_DATABASE_URL": _database_url(
                user="cmp_app",
                password=secret["database_application_password"],
                port=_topology_port(options, "postgres"),
            ),
            "CMP_UPLOAD_STORAGE_ROOT": str(options.paths.objects),
            "CMP_UPLOAD_CAPABILITY_SECRET": secret["upload_capability_secret"],
            "CMP_ARTIFACT_TRANSFER_SECRET": secret["artifact_transfer_secret"],
        }
    )
    return base, secret


def _initialize_postgres(
    options: StackOptions,
    *,
    environment: Mapping[str, str],
    owner_password: str,
) -> None:
    assert options.postgres_bin is not None
    postgres_port = _topology_port(options, "postgres")
    data = options.paths.postgres
    log = options.paths.logs / "postgres.log"
    options.paths.logs.mkdir(parents=True, exist_ok=True)
    data.parent.mkdir(parents=True, exist_ok=True)
    if not (data / "PG_VERSION").is_file():
        data.mkdir(parents=True, exist_ok=True)
        password_file = options.paths.state / "postgres-owner.pw"
        options.paths.state.mkdir(parents=True, exist_ok=True)
        password_file.write_text(owner_password, encoding="utf-8", newline="\n")
        try:
            _run(
                [
                    _postgres_executable(options.postgres_bin, "initdb"),
                    "-D",
                    data,
                    "-U",
                    "cmp_owner",
                    "--auth-host=scram-sha-256",
                    "--auth-local=scram-sha-256",
                    f"--pwfile={password_file}",
                    "--encoding=UTF8",
                ],
                cwd=options.paths.root,
                environment=environment,
            )
        finally:
            password_file.unlink(missing_ok=True)
    status = _run(
        [_postgres_executable(options.postgres_bin, "pg_ctl"), "status", "-D", data],
        cwd=options.paths.root,
        environment=environment,
        check=False,
    )
    if status.returncode:
        _run(
            [
                _postgres_executable(options.postgres_bin, "pg_ctl"),
                "start",
                "-D",
                data,
                "-l",
                log,
                "-o",
                f"-p {postgres_port} -h 127.0.0.1",
                "-w",
            ],
            cwd=options.paths.root,
            environment=environment,
        )
    postgres_env = dict(environment)
    postgres_env["PGPASSWORD"] = owner_password
    exists = _run(
        [
            _postgres_executable(options.postgres_bin, "psql"),
            "-h",
            "127.0.0.1",
            "-p",
            str(postgres_port),
            "-U",
            "cmp_owner",
            "-d",
            "postgres",
            "-tAc",
            "SELECT 1 FROM pg_database WHERE datname='cmp'",
        ],
        cwd=options.paths.root,
        environment=postgres_env,
        capture=True,
    )
    if exists.stdout.strip() != "1":
        _run(
            [
                _postgres_executable(options.postgres_bin, "createdb"),
                "-h",
                "127.0.0.1",
                "-p",
                str(postgres_port),
                "-U",
                "cmp_owner",
                "cmp",
            ],
            cwd=options.paths.root,
            environment=postgres_env,
        )


def _migrate_and_bootstrap(
    options: StackOptions,
    *,
    environment: Mapping[str, str],
    secret: Mapping[str, str],
) -> None:
    owner_environment = dict(environment)
    owner_environment["CMP_DATABASE_URL"] = _database_url(
        user="cmp_owner",
        password=secret["database_owner_password"],
        port=_topology_port(options, "postgres"),
    )
    _run(
        _host_command(options, "migration_command"),
        cwd=options.paths.root,
        environment=owner_environment,
    )
    if options.profile == "demo":
        owner_environment["CMP_DEMO_APP_DATABASE_PASSWORD"] = secret[
            "database_application_password"
        ]
        _run(
            _host_command(options, "demo_bootstrap_command"),
            cwd=options.paths.root,
            environment=owner_environment,
        )
        return
    engine = sa.create_engine(owner_environment["CMP_DATABASE_URL"], pool_pre_ping=True)
    try:
        with engine.begin() as connection:
            ensure_application_role(connection, secret["database_application_password"])
            grant_application_privileges(connection)
    finally:
        engine.dispose()


def _start_process(
    name: str,
    command: Sequence[str | Path],
    *,
    options: StackOptions,
    environment: Mapping[str, str],
) -> ProcessState:
    options.paths.logs.mkdir(parents=True, exist_ok=True)
    log_path = options.paths.logs / f"{name}.log"
    log_handle = log_path.open("a", encoding="utf-8", newline="\n")
    kwargs: dict[str, Any] = {
        "cwd": options.paths.root,
        "env": dict(environment),
        "stdin": subprocess.DEVNULL,
        "stdout": log_handle,
        "stderr": subprocess.STDOUT,
        "text": True,
    }
    if os.name == "nt":
        kwargs["creationflags"] = int(getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
    else:
        kwargs["start_new_session"] = True
    try:
        process = subprocess.Popen([str(item) for item in command], **kwargs)
    finally:
        log_handle.close()
    try:
        token = _process_token(process.pid)
    except OSError:
        process.terminate()
        process.wait(timeout=10)
        raise
    return ProcessState(process.pid, str(log_path), token)


def _stop_pid(pid: int, token: str) -> None:
    if not _is_running(pid, token):
        return
    os.kill(pid, signal.SIGTERM)
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if not _is_running(pid, token):
            return
        time.sleep(0.1)
    if os.name != "nt":
        os.kill(pid, getattr(signal, "SIGKILL", signal.SIGTERM))
        return
    raise StackError(f"process did not stop after SIGTERM: pid={pid}")


def _host_up(options: StackOptions, *, open_browser: bool) -> None:
    checks = _doctor(options)
    failures = [check for check in checks if check.status == "error"]
    if failures:
        raise StackError("doctor failed: " + "; ".join(f"{c.name}: {c.detail}" for c in failures))
    if _read_state(options) is not None:
        raise StackError("stack state already exists; run status or down before up")
    environment, secret = _runtime_environment(options)
    options.paths.objects.mkdir(parents=True, exist_ok=True)
    processes: dict[str, ProcessState] = {}
    try:
        for step in _host_execution_order(options):
            if step == "postgres":
                _initialize_postgres(
                    options,
                    environment=environment,
                    owner_password=secret["database_owner_password"],
                )
                continue
            if step == "migrate":
                _migrate_and_bootstrap(options, environment=environment, secret=secret)
                continue
            if step == "reference-plugins":
                if options.profile == "demo":
                    _run(
                        _host_command(options, "reference_plugin_check_command"),
                        cwd=options.paths.root,
                        environment=environment,
                    )
                continue
            if step == "seed":
                if options.profile == "demo":
                    api_port = _topology_port(options, "api")
                    seed_environment = dict(environment)
                    seed_environment["CMP_DEMO_API_BASE_URL"] = (
                        f"http://127.0.0.1:{api_port}/api/v1"
                    )
                    seed_environment["CMP_DEMO_FIXTURE_STAMP"] = "t60-reference"
                    for command in _host_seed_commands(options):
                        _run(command, cwd=options.paths.root, environment=seed_environment)
                continue
            if step not in _host_process_order(options):
                raise StackError(f"unsupported host topology step: {step}")
            processes[step] = _start_process(
                step,
                _host_command(options, "command", process=step),
                options=options,
                environment=environment,
            )
            health_path = _host_health_path(options, step)
            if health_path is not None:
                host = options.listen_address if step == "web" else "127.0.0.1"
                port = _topology_port(options, "web" if step == "web" else step)
                _wait_http(f"http://{host}:{port}{health_path}")
        assert options.postgres_bin is not None
        _write_state(
            options,
            HostState(
                schema_version=1,
                profile=options.profile,
                runtime="host",
                listen_address=options.listen_address,
                postgres_bin=str(options.postgres_bin.resolve()),
                processes=processes,
            ),
        )
    except BaseException:
        for process in reversed(tuple(processes.values())):
            try:
                _stop_pid(process.pid, process.token)
            except (OSError, StackError):
                pass
        _stop_postgres(options, postgres_bin=options.postgres_bin)
        raise
    web_port = _topology_port(options, "web")
    url = f"http://{options.listen_address}:{web_port}"
    identity = "synthetic-demo-only" if options.profile == "demo" else "external-oidc"
    print(
        f"CMP stack started: profile={options.profile} identity={identity} "
        f"local=http://127.0.0.1:{web_port} lan={url}"
    )
    if open_browser:
        webbrowser.open(url)


def _stop_postgres(options: StackOptions, *, postgres_bin: Path | None) -> None:
    if postgres_bin is None or not (options.paths.postgres / "PG_VERSION").is_file():
        return
    _run(
        [
            _postgres_executable(postgres_bin, "pg_ctl"),
            "stop",
            "-D",
            options.paths.postgres,
            "-m",
            "fast",
            "-w",
        ],
        cwd=options.paths.root,
        check=False,
    )


def _host_down(options: StackOptions) -> None:
    state = _read_state(options)
    if state is None:
        print("CMP stack is already stopped; persistent data was not changed")
        return
    errors: list[str] = []
    for name in reversed(_host_process_order(options)):
        process = state.processes.get(name)
        if process is None:
            continue
        try:
            _stop_pid(process.pid, process.token)
        except (OSError, StackError) as error:
            errors.append(f"{name}: {error}")
    _stop_postgres(options, postgres_bin=Path(state.postgres_bin))
    if errors:
        raise StackError("stack stop was incomplete: " + "; ".join(errors))
    _state_path(options).unlink(missing_ok=True)
    print(f"CMP stack stopped; data preserved at {options.paths.data}")


def _host_status(options: StackOptions) -> dict[str, Any]:
    state = _read_state(options)
    if state is None:
        return {
            "state": "stopped",
            "profile": options.profile,
            "runtime": "host",
            **_access_status(options),
            "processes": {},
        }
    processes = {
        name: {
            "pid": process.pid,
            "running": _is_running(process.pid, process.token),
            "log": process.log,
        }
        for name, process in state.processes.items()
    }
    expected = set(_host_process_order(options))
    running = set(processes) == expected and all(value["running"] for value in processes.values())
    return {
        "state": "running" if running else "degraded",
        "profile": state.profile,
        "runtime": state.runtime,
        **_access_status(
            StackOptions(
                profile=state.profile,
                runtime="host",
                paths=options.paths,
                postgres_bin=options.postgres_bin,
                listen_address=state.listen_address,
                auth_config=options.auth_config,
                secret_file=options.secret_file,
                json_output=options.json_output,
            )
        ),
        "processes": processes,
    }


def _host_logs(options: StackOptions, *, lines: int) -> None:
    state = _read_state(options)
    if state is None:
        raise StackError("stack has no state; run up first")
    for name in ("postgres", *_host_process_order(options)):
        path = options.paths.logs / f"{name}.log"
        print(f"== {name}: {path} ==")
        if not path.is_file():
            print("(no log)")
            continue
        content = path.read_text(encoding="utf-8", errors="replace").splitlines()
        print("\n".join(content[-lines:]))


def _access_status(options: StackOptions) -> dict[str, Any]:
    web_port = _topology_port(options, "web")
    listen_address = str(_validate_listen_address(options.listen_address))
    loopback_names = ["api", "postgres"]
    if options.runtime == "compose":
        loopback_names.extend(("otlp", "metrics"))
        observability: dict[str, Any] = {
            "mode": "managed",
            "service": "otel-collector",
            "otlp_endpoint": f"http://127.0.0.1:{_topology_port(options, 'otlp')}",
            "metrics_endpoint": f"http://127.0.0.1:{_topology_port(options, 'metrics')}",
        }
    else:
        raw = (
            _load_topology(options.paths.root)
            .get("host", {})
            .get("external_services", {})
            .get("otel-collector")
        )
        if not isinstance(raw, dict) or not all(
            isinstance(raw.get(name), str) for name in ("mode", "endpoint_environment", "reason")
        ):
            raise StackError("stack topology host otel-collector boundary is invalid")
        endpoint_environment = cast(str, raw["endpoint_environment"])
        observability = {
            **raw,
            "configured_endpoint": os.environ.get(endpoint_environment) or None,
        }
    return {
        "local_url": f"http://{listen_address}:{web_port}",
        "lan_url": f"http://{listen_address}:{web_port}",
        "listen_address": listen_address,
        "identity": "synthetic-demo-only" if options.profile == "demo" else "external-oidc",
        "remote_access": "local-only"
        if listen_address == "127.0.0.1"
        else "requires Private/Domain LocalSubnet firewall rule",
        "exposed_ports": {"web": web_port},
        "loopback_ports": {name: _topology_port(options, name) for name in loopback_names},
        "observability": observability,
    }


def _print_status(options: StackOptions, status: Mapping[str, Any]) -> None:
    print(
        json.dumps(status, indent=2, sort_keys=True)
        if options.json_output
        else " ".join(f"{key}={value}" for key, value in status.items())
    )


def _print_started(options: StackOptions, status: Mapping[str, Any]) -> None:
    print(
        "CMP stack started: "
        f"profile={options.profile} identity={status['identity']} "
        f"local={status['local_url']} lan={status['lan_url']} "
        f"remote_access={status['remote_access']} exposed_ports={status['exposed_ports']}"
    )


def _compose_command(options: StackOptions, *arguments: str) -> list[str | Path]:
    return [
        "docker",
        "compose",
        "-f",
        options.paths.root / "deploy/compose/docker-compose.demo.yml",
        *arguments,
    ]


def _compose_environment(options: StackOptions) -> dict[str, str]:
    """Bind Compose's published Web port to the same validated address shown in status."""
    return {
        **os.environ,
        "CMP_STACK_LISTEN_ADDRESS": str(_validate_listen_address(options.listen_address)),
    }


def _parse_compose_ps(output: str) -> list[dict[str, Any]]:
    stripped = output.strip()
    if not stripped:
        return []
    try:
        document = json.loads(stripped)
    except json.JSONDecodeError:
        try:
            document = [json.loads(line) for line in stripped.splitlines() if line.strip()]
        except json.JSONDecodeError as error:
            raise StackError(f"docker compose returned invalid status JSON: {error}") from error
    if isinstance(document, dict):
        document = [document]
    if not isinstance(document, list) or not all(isinstance(item, dict) for item in document):
        raise StackError("docker compose returned an invalid status document")
    return cast(list[dict[str, Any]], document)


def _compose_status(options: StackOptions) -> dict[str, Any]:
    result = _run(
        _compose_command(options, "ps", "--all", "--format", "json"),
        cwd=options.paths.root,
        environment=_compose_environment(options),
        capture=True,
    )
    entries = _parse_compose_ps(result.stdout)
    processes = {
        str(entry.get("Service")): {
            "state": str(entry.get("State", "unknown")).lower(),
            "health": str(entry.get("Health", "")) or None,
            "exit_code": entry.get("ExitCode"),
        }
        for entry in entries
        if entry.get("Service")
    }
    contract = _load_topology(options.paths.root).get("compose", {}).get("status")
    if not isinstance(contract, dict):
        raise StackError("stack topology compose status contract is missing")
    running_services = contract.get("running_services")
    completed_services = contract.get("completed_services")
    if not all(
        isinstance(value, list) and all(isinstance(name, str) for name in value)
        for value in (running_services, completed_services)
    ):
        raise StackError("stack topology compose status contract is invalid")
    if not processes:
        state = "stopped"
    else:
        steady_ok = all(
            processes.get(name, {}).get("state") == "running"
            and processes.get(name, {}).get("health") not in {"unhealthy", "starting"}
            for name in cast(list[str], running_services)
        )
        completed_ok = all(
            processes.get(name, {}).get("state") == "exited"
            and processes.get(name, {}).get("exit_code") in {0, "0"}
            for name in cast(list[str], completed_services)
        )
        state = "running" if steady_ok and completed_ok else "degraded"
    return {
        "state": state,
        "profile": options.profile,
        "runtime": "compose",
        **_access_status(options),
        "processes": processes,
    }


def _compose_action(
    options: StackOptions,
    command: str,
    *,
    lines: int,
    open_browser: bool = False,
) -> dict[str, Any] | None:
    if options.profile == "server":
        raise StackError(
            "server runtime cannot start until the #215 SPA OIDC contract is available"
        )
    if command == "up":
        failures = [check for check in _doctor(options) if check.status == "error"]
        if failures:
            raise StackError(
                "doctor failed: " + "; ".join(f"{c.name}: {c.detail}" for c in failures)
            )
        _run(
            _compose_command(options, "up", "--build", "-d"),
            cwd=options.paths.root,
            environment=_compose_environment(options),
        )
        status = _compose_status(options)
        if status["state"] != "running":
            raise StackError("Compose stack did not reach the topology status contract")
        _print_started(options, status)
        if open_browser:
            webbrowser.open(cast(str, status["lan_url"]))
    elif command == "down":
        _run(
            _compose_command(options, "down"),
            cwd=options.paths.root,
            environment=_compose_environment(options),
        )
    elif command == "status":
        return _compose_status(options)
    elif command == "logs":
        _run(
            _compose_command(options, "logs", "--no-color", "--tail", str(lines)),
            cwd=options.paths.root,
            environment=_compose_environment(options),
        )
    else:  # pragma: no cover - argparse constrains commands.
        raise StackError(f"unsupported Compose command: {command}")
    return None


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=("demo", "server"), required=True)
    parser.add_argument("--runtime", choices=("compose", "host"), required=True)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--state-dir", type=Path)
    parser.add_argument("--data-dir", type=Path)
    parser.add_argument("--web-dist", type=Path)
    parser.add_argument("--postgres-bin", type=Path)
    parser.add_argument("--listen-address", default="127.0.0.1")
    parser.add_argument("--auth-config", type=Path)
    parser.add_argument("--secret-file", type=Path)
    parser.add_argument("--json", action="store_true", dest="json_output")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("doctor")
    up = subparsers.add_parser("up")
    up.add_argument("--no-browser", action="store_true")
    subparsers.add_parser("down")
    subparsers.add_parser("status")
    logs = subparsers.add_parser("logs")
    logs.add_argument("--lines", type=int, default=200)
    return parser


def _options(args: argparse.Namespace) -> StackOptions:
    return StackOptions(
        profile=cast(Profile, args.profile),
        runtime=cast(Runtime, args.runtime),
        paths=resolve_paths(
            root=args.root,
            state_dir=args.state_dir,
            data_dir=args.data_dir,
            web_dist=args.web_dist,
        ),
        postgres_bin=args.postgres_bin.resolve() if args.postgres_bin else None,
        listen_address=args.listen_address,
        auth_config=args.auth_config.resolve() if args.auth_config else None,
        secret_file=args.secret_file.resolve() if args.secret_file else None,
        json_output=args.json_output,
    )


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    options = _options(args)
    try:
        if args.command == "doctor":
            checks = _doctor(options)
            if options.json_output:
                print(json.dumps([asdict(check) for check in checks], indent=2, sort_keys=True))
            else:
                for check in checks:
                    print(f"DOCTOR {check.status.upper()} {check.name}: {check.detail}")
            return 1 if any(check.status == "error" for check in checks) else 0
        if options.runtime == "compose":
            status = _compose_action(
                options,
                args.command,
                lines=getattr(args, "lines", 200),
                open_browser=not getattr(args, "no_browser", True),
            )
            if status is not None:
                _print_status(options, status)
                return 0 if status["state"] in {"running", "stopped"} else 1
            return 0
        if args.command == "up":
            _host_up(options, open_browser=not args.no_browser)
        elif args.command == "down":
            _host_down(options)
        elif args.command == "status":
            status = _host_status(options)
            _print_status(options, status)
            return 0 if status["state"] in {"running", "stopped"} else 1
        elif args.command == "logs":
            _host_logs(options, lines=args.lines)
        return 0
    except KeyboardInterrupt:
        print("CMP stack command cancelled", file=sys.stderr)
        return 130
    except StackError as error:
        print(f"CMP stack error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

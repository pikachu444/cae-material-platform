"""Install and control a verified CMP Windows 11 x64 offline bundle."""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import platform
import re
import secrets
import shutil
import subprocess
import sys
import webbrowser
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal, cast

from cmp.tools import stack

Scope = Literal["user", "machine"]
Profile = Literal["demo", "server"]

_FIREWALL_RULE = "CAE-Material-Platform-Web"
_FIREWALL_DISPLAY = "CAE Material Platform Web (installer-owned)"
_FIREWALL_GROUP = "CAE Material Platform Offline Installer"
_VERSION = re.compile(r"^[0-9]+(?:\.[0-9]+){2}$")


class InstallerError(RuntimeError):
    """Expected installation or recovery failure."""


def _platform_attribute(module: object, name: str) -> Any:
    return getattr(module, name)


@dataclass(frozen=True, slots=True)
class InstallPaths:
    program: Path
    control: Path
    state: Path
    data: Path
    log: Path


@dataclass(frozen=True, slots=True)
class InstallRecord:
    schema_version: int
    scope: Scope
    profile: Profile
    version: str
    bundle_manifest_sha256: str
    program: str
    control: str
    state: str
    data: str
    listen_address: str
    firewall_rule: str


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_json(path: Path, *, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise InstallerError(f"{label} is missing or invalid: {path}: {error}") from error
    if not isinstance(value, dict):
        raise InstallerError(f"{label} must be a JSON object: {path}")
    return cast(dict[str, Any], value)


def _canonical_json(value: Mapping[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _verify_windows_11_x64() -> str:
    if os.name != "nt":
        raise InstallerError("unsupported operating system: Windows 11 x64 is required")
    machine = platform.machine().lower()
    if machine not in {"amd64", "x86_64"}:
        raise InstallerError(f"unsupported architecture: {machine}; Windows 11 x64 is required")
    version = cast(Any, _platform_attribute(sys, "getwindowsversion"))()
    product_type = getattr(version, "product_type", None)
    if product_type != 1:
        raise InstallerError(
            f"unsupported Windows product type: {product_type}; Windows Server is not supported"
        )
    if version.major != 10 or version.build < 22000:
        raise InstallerError(
            f"unsupported Windows version: {version.major}.{version.minor}.{version.build}; "
            "Windows 11 x64 is required"
        )
    return f"Windows 11 x64 build {version.build}"


def _is_admin() -> bool:
    if os.name != "nt":
        return False
    try:
        windll = cast(Any, _platform_attribute(ctypes, "windll"))
        return bool(windll.shell32.IsUserAnAdmin())
    except (AttributeError, OSError):
        return False


def _scope_paths(scope: Scope, version: str, environment: Mapping[str, str]) -> InstallPaths:
    if not _VERSION.fullmatch(version):
        raise InstallerError(f"invalid product version in bundle: {version}")
    if scope == "machine":
        program_files = environment.get("ProgramFiles")
        program_data = environment.get("ProgramData")
        if not program_files or not program_data:
            raise InstallerError("ProgramFiles and ProgramData are required for machine scope")
        program = Path(program_files) / "CAE Material Platform" / "program" / version
        control = Path(program_data) / "CAE Material Platform"
    else:
        local_app_data = environment.get("LOCALAPPDATA")
        if not local_app_data:
            raise InstallerError("LOCALAPPDATA is required for user scope")
        control = Path(local_app_data) / "CAE Material Platform"
        program = control / "program" / version
    return InstallPaths(
        program=program,
        control=control,
        state=control / "state",
        data=control / "data",
        log=control / "state" / "logs" / "installer.log",
    )


def _log(paths: InstallPaths, message: str) -> None:
    paths.log.parent.mkdir(parents=True, exist_ok=True)
    with paths.log.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(message.rstrip() + "\n")
    print(message)


def _verified_bundle(bundle_root: Path, expected_sha256: str) -> dict[str, Any]:
    root = bundle_root.resolve()
    manifest_path = root / "bundle-manifest.json"
    actual_manifest = _sha256(manifest_path) if manifest_path.is_file() else "missing"
    if actual_manifest != expected_sha256.lower():
        raise InstallerError(
            "offline bundle manifest checksum mismatch: "
            f"expected={expected_sha256.lower()} actual={actual_manifest}"
        )
    manifest = _load_json(manifest_path, label="offline bundle manifest")
    if manifest.get("schema_version") != 1:
        raise InstallerError("offline bundle manifest schema_version must be 1")
    files = manifest.get("files")
    if not isinstance(files, dict) or not files:
        raise InstallerError("offline bundle manifest has no file inventory")
    for relative, expected in files.items():
        if not isinstance(relative, str) or not isinstance(expected, dict):
            raise InstallerError("offline bundle file inventory is invalid")
        candidate = (root / Path(relative)).resolve()
        try:
            candidate.relative_to(root)
        except ValueError as error:
            raise InstallerError(f"offline bundle path escapes its root: {relative}") from error
        if not candidate.is_file():
            raise InstallerError(f"offline bundle file is missing: {relative}")
        actual_size = candidate.stat().st_size
        actual_hash = _sha256(candidate)
        if actual_size != expected.get("size") or actual_hash != expected.get("sha256"):
            raise InstallerError(
                f"offline bundle file checksum mismatch: {relative} "
                f"expected={expected.get('sha256')} actual={actual_hash}"
            )
    return manifest


def _safe_remove_program(path: Path, *, control: Path) -> None:
    resolved = path.resolve()
    program_root = (control / "program").resolve()
    try:
        relative = resolved.relative_to(program_root)
    except ValueError as error:
        raise InstallerError(
            f"refusing to replace a path outside the program root: {resolved}"
        ) from error
    version_name = relative.name.removesuffix(".installing").removesuffix(".previous")
    if len(relative.parts) != 1 or not _VERSION.fullmatch(version_name):
        raise InstallerError(f"refusing to replace an invalid program directory: {resolved}")
    shutil.rmtree(resolved)


def _payload_matches(program: Path, files: Mapping[str, Any]) -> bool:
    for relative, expected in files.items():
        if not isinstance(relative, str) or not relative.startswith("payload/"):
            return False
        candidate = program / Path(relative).relative_to("payload")
        if (
            not candidate.is_file()
            or not isinstance(expected, dict)
            or candidate.stat().st_size != expected.get("size")
            or _sha256(candidate) != expected.get("sha256")
        ):
            return False
    return True


def _install_payload(
    bundle_root: Path,
    paths: InstallPaths,
    manifest_sha256: str,
    files: Mapping[str, Any],
) -> None:
    payload = bundle_root / "payload"
    if not payload.is_dir():
        raise InstallerError(f"offline bundle payload is missing: {payload}")
    marker = paths.program / ".bundle-manifest-sha256"
    if (
        marker.is_file()
        and marker.read_text(encoding="ascii").strip() == manifest_sha256
        and _payload_matches(paths.program, files)
    ):
        return
    staging = paths.program.with_name(paths.program.name + ".installing")
    previous = paths.program.with_name(paths.program.name + ".previous")
    if staging.exists():
        _safe_remove_program(staging, control=paths.control)
    if previous.exists():
        _safe_remove_program(previous, control=paths.control)
    staging.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.copytree(payload, staging)
        if not _payload_matches(staging, files):
            raise InstallerError("copied program payload failed its checksum inventory")
        (staging / ".bundle-manifest-sha256").write_text(
            manifest_sha256 + "\n", encoding="ascii", newline="\n"
        )
        if paths.program.exists():
            paths.program.replace(previous)
        try:
            staging.replace(paths.program)
        except OSError:
            if previous.exists() and not paths.program.exists():
                previous.replace(paths.program)
            raise
        if previous.exists():
            _safe_remove_program(previous, control=paths.control)
    except OSError as error:
        if staging.exists():
            _safe_remove_program(staging, control=paths.control)
        diagnosis = "execution policy or antivirus may have blocked the verified payload"
        raise InstallerError(f"program installation failed: {error}; {diagnosis}") from error


def _run(command: Sequence[str | Path], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [str(value) for value in command], text=True, capture_output=True, check=False
    )
    if check and result.returncode:
        detail = (result.stderr or result.stdout).strip()
        raise InstallerError(f"command failed ({result.returncode}): {command[0]}: {detail}")
    return result


def _start_failure_category(detail: str) -> str:
    lowered = detail.lower()
    if "port is unavailable" in lowered:
        return "port-conflict"
    if "#215 spa oidc" in lowered or "server profile" in lowered:
        return "server-authentication"
    if any(value in lowered for value in ("antivirus", "quarantine", "threat detected")):
        return "antivirus"
    if any(value in lowered for value in ("applocker", "execution policy", "system administrator")):
        return "execution-policy"
    if "access is denied" in lowered or "winerror 5" in lowered:
        return "execution-policy-or-antivirus"
    return "runtime-start"


def _restrict_secret_file(path: Path) -> None:
    path.chmod(0o600)
    if os.name != "nt":
        return
    username = os.environ.get("USERNAME")
    domain = os.environ.get("USERDOMAIN")
    principal = f"{domain}\\{username}" if domain and username else username
    if not principal:
        raise InstallerError("USERNAME is required to restrict a Server secret file")
    _run(["icacls", path, "/inheritance:r", "/grant:r", f"{principal}:(F)"])


def _prepare_server_configuration(paths: InstallPaths) -> tuple[Path, Path]:
    template = paths.program / "config" / "server-auth.json"
    auth = _load_json(template, label="Server auth configuration")
    forbidden = sorted(name for name in auth if name.startswith(("CMP_DEMO_", "CMP_PLUGIN_")))
    required = {
        "CMP_OIDC_ISSUER",
        "CMP_OIDC_AUDIENCE",
        "CMP_OIDC_JWKS_URL",
        "CMP_OBJECT_STORE_BACKEND",
        "CMP_S3_BUCKET",
        "CMP_S3_KMS_KEY_ID",
    }
    missing = sorted(
        name for name in required if not isinstance(auth.get(name), str) or not auth[name]
    )
    if forbidden or missing or str(auth.get("CMP_OBJECT_STORE_BACKEND", "")).lower() != "s3":
        raise InstallerError(
            f"Server auth configuration is invalid: missing={missing or 'none'} "
            f"forbidden={forbidden or 'none'} backend={auth.get('CMP_OBJECT_STORE_BACKEND')}"
        )
    secrets_dir = paths.state / "secrets"
    secrets_dir.mkdir(parents=True, exist_ok=True)
    worker_token = secrets_dir / "worker.token"
    secret_file = secrets_dir / "server.json"
    if not worker_token.is_file():
        worker_token.write_text(secrets.token_urlsafe(48) + "\n", encoding="utf-8", newline="\n")
        _restrict_secret_file(worker_token)
    if not secret_file.is_file():
        secret = {
            "database_owner_password": secrets.token_urlsafe(48),
            "database_application_password": secrets.token_urlsafe(48),
            "upload_capability_secret": secrets.token_urlsafe(48),
            "artifact_transfer_secret": secrets.token_urlsafe(48),
        }
        secret_file.write_text(_canonical_json(secret), encoding="utf-8", newline="\n")
        _restrict_secret_file(secret_file)
    config_dir = paths.state / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    auth_file = config_dir / "server-auth.json"
    if not auth_file.is_file():
        auth["CMP_WORKER_ACCESS_TOKEN_FILE"] = str(worker_token)
        auth_file.write_text(_canonical_json(auth), encoding="utf-8", newline="\n")
        _restrict_secret_file(auth_file)
    return auth_file, secret_file


def _firewall_program(paths: InstallPaths) -> Path:
    return paths.program / "python" / "python.exe"


def _firewall_add_command(paths: InstallPaths) -> str:
    return (
        f'netsh advfirewall firewall add rule name="{_FIREWALL_RULE}" '
        f'description="{_FIREWALL_DISPLAY}" group="{_FIREWALL_GROUP}" '
        "dir=in action=allow protocol=TCP localport=5173 profile=private,domain "
        f'remoteip=localsubnet program="{_firewall_program(paths)}"'
    )


def _powershell_literal(value: str | Path) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def _owned_firewall_command(paths: InstallPaths, *, remove: bool) -> list[str]:
    rule = _powershell_literal(_FIREWALL_RULE)
    display = _powershell_literal(_FIREWALL_DISPLAY)
    group = _powershell_literal(_FIREWALL_GROUP)
    program = _powershell_literal(_firewall_program(paths))
    script = f"""
$ErrorActionPreference = 'Stop'
$owned = @(
  Get-NetFirewallRule -DisplayName {rule} -ErrorAction SilentlyContinue |
    Where-Object {{
      $_.Group -eq {group} -and $_.Description -eq {display} -and
      $_.Direction -eq 'Inbound' -and
      $_.Action -eq 'Allow' -and ($_.Profile -band 1) -eq 1 -and
      ($_.Profile -band 2) -eq 2 -and ($_.Profile -band 4) -eq 0
    }} |
    Where-Object {{
      $application = @($_ | Get-NetFirewallApplicationFilter)
      $port = @($_ | Get-NetFirewallPortFilter)
      $address = @($_ | Get-NetFirewallAddressFilter)
      $matchingApplication = @($application | Where-Object {{ $_.Program -eq {program} }})
      $matchingPort = @($port | Where-Object {{
        "$($_.Protocol)" -in @('TCP', '6') -and "$($_.LocalPort)" -eq '5173'
      }})
      $matchingAddress = @($address | Where-Object {{
        @($_.RemoteAddress) -contains 'LocalSubnet'
      }})
      $matchingApplication.Count -gt 0 -and $matchingPort.Count -gt 0 -and
      $matchingAddress.Count -gt 0
    }}
)
""".strip()
    script += (
        "\n$owned | Remove-NetFirewallRule -Confirm:$false -ErrorAction Stop"
        if remove
        else "\nif ($owned.Count -gt 0) { 'true' } else { 'false' }"
    )
    return [
        "powershell.exe",
        "-NoLogo",
        "-NoProfile",
        "-NonInteractive",
        "-Command",
        script,
    ]


def _firewall_delete_command(paths: InstallPaths) -> str:
    return subprocess.list2cmdline(_owned_firewall_command(paths, remove=True))


def _firewall_exists(paths: InstallPaths) -> bool:
    result = _run(_owned_firewall_command(paths, remove=False), check=False)
    return result.returncode == 0 and result.stdout.strip().lower() == "true"


def _delete_owned_firewall_rule(paths: InstallPaths, *, check: bool) -> None:
    _run(_owned_firewall_command(paths, remove=True), check=check)


def _configure_firewall(paths: InstallPaths, *, admin: bool) -> bool:
    if not admin:
        _log(
            paths,
            "Firewall rule not changed (non-admin). Local use remains available. "
            f"Ask IT to run as administrator: {_firewall_add_command(paths)}",
        )
        return _firewall_exists(paths)
    _delete_owned_firewall_rule(paths, check=False)
    result = _run(
        [
            "netsh",
            "advfirewall",
            "firewall",
            "add",
            "rule",
            f"name={_FIREWALL_RULE}",
            f"description={_FIREWALL_DISPLAY}",
            f"group={_FIREWALL_GROUP}",
            "dir=in",
            "action=allow",
            "protocol=TCP",
            "localport=5173",
            "profile=private,domain",
            "remoteip=localsubnet",
            f"program={_firewall_program(paths)}",
        ],
        check=False,
    )
    if result.returncode:
        _log(
            paths,
            "Firewall rule could not be added; local installation is preserved. "
            f"Ask IT to run as administrator: {_firewall_add_command(paths)}; "
            f"detail={(result.stderr or result.stdout).strip()}",
        )
        return False
    return True


def _remove_firewall(paths: InstallPaths, *, admin: bool) -> None:
    if not _firewall_exists(paths):
        return
    if not admin:
        _log(
            paths,
            "Installer-owned firewall rule remains. Ask IT to run as administrator: "
            f"{_firewall_delete_command(paths)}",
        )
        return
    _delete_owned_firewall_rule(paths, check=True)


def _record_path(control: Path) -> Path:
    return control / "install.json"


def _write_record(paths: InstallPaths, record: InstallRecord) -> Path:
    path = _record_path(paths.control)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_canonical_json(asdict(record)), encoding="utf-8", newline="\n")
    return path


def _read_record(path: Path) -> InstallRecord:
    value = _load_json(path, label="installation record")
    try:
        record = InstallRecord(**value)
    except TypeError as error:
        raise InstallerError(f"installation record fields are invalid: {path}: {error}") from error
    if record.schema_version != 1:
        raise InstallerError(f"unsupported installation record schema: {record.schema_version}")
    return record


def _batch_quote(path: Path) -> str:
    value = str(path)
    if any(character in value for character in ('"', "\r", "\n")):
        raise InstallerError(f"Windows command path contains unsupported characters: {path}")
    return f'"{value}"'


def _entrypoint(command: str, *, record_path: Path, python: Path) -> str:
    return (
        "@echo off\r\n"
        "setlocal\r\n"
        f"{_batch_quote(python)} -m cmp.tools.windows_installer {command} "
        f"--record {_batch_quote(record_path)} %*\r\n"
        "exit /b %ERRORLEVEL%\r\n"
    )


def _uninstall_entrypoint(*, record_path: Path, python: Path, paths: InstallPaths) -> str:
    return (
        "@echo off\r\n"
        "setlocal\r\n"
        f"{_batch_quote(python)} -m cmp.tools.windows_installer uninstall "
        f"--record {_batch_quote(record_path)}\r\n"
        "if errorlevel 1 exit /b %ERRORLEVEL%\r\n"
        f"rmdir /s /q {_batch_quote(paths.program)}\r\n"
        f"if exist {_batch_quote(paths.program)} "
        "(echo Installer-owned program removal failed & exit /b 2)\r\n"
        f"del /q {_batch_quote(paths.control / 'Start.cmd')}\r\n"
        f"del /q {_batch_quote(paths.control / 'Stop.cmd')}\r\n"
        f"del /q {_batch_quote(paths.control / 'Status.cmd')}\r\n"
        f"del /q {_batch_quote(record_path)}\r\n"
        'start "" /b cmd.exe /d /c "ping 127.0.0.1 -n 2 >nul & del /q ^"%~f0^""\r\n'
        "exit /b 0\r\n"
    )


def _write_entrypoints(paths: InstallPaths, record_path: Path) -> None:
    python = paths.program / "python" / "python.exe"
    for filename, command in (
        ("Start.cmd", "start"),
        ("Stop.cmd", "stop"),
        ("Status.cmd", "status"),
    ):
        (paths.control / filename).write_text(
            _entrypoint(command, record_path=record_path, python=python),
            encoding="utf-8",
            newline="",
        )
    (paths.control / "Uninstall.cmd").write_text(
        _uninstall_entrypoint(record_path=record_path, python=python, paths=paths),
        encoding="utf-8",
        newline="",
    )


def _stack_arguments(record: InstallRecord, command: str) -> list[str]:
    program = Path(record.program)
    arguments = [
        "--profile",
        record.profile,
        "--runtime",
        "host",
        "--root",
        str(program / "runtime"),
        "--state-dir",
        record.state,
        "--data-dir",
        record.data,
        "--web-dist",
        str(program / "web"),
        "--postgres-bin",
        str(program / "postgresql" / "bin"),
        "--listen-address",
        record.listen_address,
    ]
    if record.profile == "server":
        arguments.extend(
            (
                "--auth-config",
                str(Path(record.state) / "config" / "server-auth.json"),
                "--secret-file",
                str(Path(record.state) / "secrets" / "server.json"),
            )
        )
    arguments.append(command)
    return arguments


def _installed_action(record_path: Path, command: str) -> int:
    record = _read_record(record_path.resolve())
    if command == "start":
        options = stack._options(stack._parser().parse_args(_stack_arguments(record, "status")))
        status = stack._host_status(options)
        if status["state"] == "running":
            print(f"CMP stack is already running: {status['lan_url']}")
            webbrowser.open(cast(str, status["lan_url"]))
            return 0
        if status["state"] == "degraded":
            raise InstallerError("installed stack is degraded; run Stop.cmd, then Start.cmd")
        return stack.main(_stack_arguments(record, "up"))
    if command == "status":
        result = stack.main(_stack_arguments(record, "status"))
        paths = InstallPaths(
            program=Path(record.program),
            control=Path(record.control),
            state=Path(record.state),
            data=Path(record.data),
            log=Path(record.state) / "logs" / "installer.log",
        )
        firewall = _firewall_exists(paths)
        remote_access = "Private/Domain LocalSubnet" if firewall else "local-only until IT rule"
        print(
            f"firewall_rule={record.firewall_rule} present={str(firewall).lower()} "
            f"remote_access={remote_access}"
        )
        return result
    stack_command = "down" if command == "stop" else command
    return stack.main(_stack_arguments(record, stack_command))


def install(
    *,
    bundle_root: Path,
    expected_manifest_sha256: str,
    listen_address: str | None,
    environment: Mapping[str, str],
    admin: bool,
    start: bool = True,
) -> Path:
    platform_detail = _verify_windows_11_x64()
    root = bundle_root.resolve()
    manifest = _verified_bundle(root, expected_manifest_sha256)
    profile = manifest.get("profile")
    version = manifest.get("product_version")
    if profile not in {"demo", "server"} or not isinstance(version, str):
        raise InstallerError("offline bundle profile or product version is invalid")
    scope: Scope = "machine" if admin else "user"
    paths = _scope_paths(scope, version, environment)
    existing_path = _record_path(paths.control)
    existing = _read_record(existing_path) if existing_path.is_file() else None
    if existing is not None and existing.profile != profile:
        raise InstallerError(
            "refusing to change an existing installation profile while preserving its data: "
            f"installed={existing.profile} requested={profile}; uninstall and move the preserved "
            "data directory before installing the other profile"
        )
    selected_address = listen_address or (existing.listen_address if existing else "127.0.0.1")
    stack._validate_listen_address(selected_address)
    _log(paths, f"Verified {platform_detail}; installing profile={profile} scope={scope}")
    files = manifest.get("files")
    if not isinstance(files, dict):
        raise InstallerError("offline bundle manifest file inventory is invalid")
    _install_payload(root, paths, expected_manifest_sha256.lower(), files)
    paths.state.mkdir(parents=True, exist_ok=True)
    paths.data.mkdir(parents=True, exist_ok=True)
    if profile == "server":
        _prepare_server_configuration(paths)
    record = InstallRecord(
        schema_version=1,
        scope=scope,
        profile=cast(Profile, profile),
        version=version,
        bundle_manifest_sha256=expected_manifest_sha256.lower(),
        program=str(paths.program),
        control=str(paths.control),
        state=str(paths.state),
        data=str(paths.data),
        listen_address=selected_address,
        firewall_rule=_FIREWALL_RULE,
    )
    record_path = _write_record(paths, record)
    _write_entrypoints(paths, record_path)
    firewall = _configure_firewall(paths, admin=admin)
    _log(
        paths,
        f"Installation ready: record={record_path} data_preserved={paths.data} "
        f"firewall={'ready' if firewall else 'local-only'}",
    )
    if start:
        target_python = paths.program / "python" / "python.exe"
        result = _run(
            [target_python, "-m", "cmp.tools.windows_installer", "start", "--record", record_path],
            check=False,
        )
        if result.stdout:
            print(result.stdout, end="")
        if result.returncode:
            detail = (result.stderr or result.stdout).strip()
            category = _start_failure_category(detail)
            _log(
                paths,
                f"Stack start failed after installation: category={category} "
                f"exit={result.returncode} detail={detail}",
            )
            raise InstallerError(
                f"installation succeeded but stack start failed category={category} "
                f"({result.returncode}): {detail}; "
                f"run {paths.control / 'Status.cmd'} for diagnosis"
            )
    return record_path


def uninstall(record_path: Path, *, admin: bool) -> int:
    record = _read_record(record_path.resolve())
    paths = InstallPaths(
        program=Path(record.program),
        control=Path(record.control),
        state=Path(record.state),
        data=Path(record.data),
        log=Path(record.state) / "logs" / "installer.log",
    )
    stopped = _installed_action(record_path, "stop")
    if stopped:
        return stopped
    _remove_firewall(paths, admin=admin)
    _log(
        paths,
        f"Uninstall cleanup authorized for installer-owned program={paths.program}; "
        f"database and user data are preserved at {paths.data}",
    )
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    install_parser = subparsers.add_parser("install")
    install_parser.add_argument("--bundle-root", type=Path, required=True)
    install_parser.add_argument("--expected-manifest-sha256", required=True)
    install_parser.add_argument("--listen-address")
    for command in ("start", "stop", "status", "uninstall"):
        action = subparsers.add_parser(command)
        action.add_argument("--record", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "install":
            install(
                bundle_root=args.bundle_root,
                expected_manifest_sha256=args.expected_manifest_sha256,
                listen_address=args.listen_address,
                environment=os.environ,
                admin=_is_admin(),
            )
            return 0
        if args.command == "uninstall":
            return uninstall(args.record, admin=_is_admin())
        return _installed_action(args.record, args.command)
    except KeyboardInterrupt:
        print("CMP installer command cancelled", file=sys.stderr)
        return 130
    except (InstallerError, stack.StackError, OSError) as error:
        print(f"CMP installer error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

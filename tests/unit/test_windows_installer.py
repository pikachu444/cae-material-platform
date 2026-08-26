from __future__ import annotations

import hashlib
import json
import os
import platform
from dataclasses import asdict
from pathlib import Path
from subprocess import CompletedProcess
from types import SimpleNamespace

import pytest
from cmp.tools import stack
from cmp.tools import windows_installer as installer


def _bundle(tmp_path: Path, *, profile: str = "demo") -> tuple[Path, str]:
    root = tmp_path / "bundle with spaces"
    payload = root / "payload"
    (payload / "python").mkdir(parents=True)
    (payload / "python/python.exe").write_bytes(b"verified-python")
    (payload / "postgresql/bin").mkdir(parents=True)
    (payload / "postgresql/bin/postgres.exe").write_bytes(b"verified-postgres")
    (payload / "runtime/deploy/stack").mkdir(parents=True)
    (payload / "runtime/pyproject.toml").write_text("[project]\n", encoding="utf-8")
    (payload / "web").mkdir()
    (payload / "web/index.html").write_text("CMP", encoding="utf-8")
    if profile == "server":
        (payload / "config").mkdir()
        (payload / "config/server-auth.json").write_text(
            json.dumps(
                {
                    "CMP_OIDC_ISSUER": "https://identity.example.test",
                    "CMP_OIDC_AUDIENCE": "cmp-server",
                    "CMP_OIDC_JWKS_URL": "https://identity.example.test/jwks.json",
                    "CMP_OBJECT_STORE_BACKEND": "s3",
                    "CMP_S3_BUCKET": "cmp-server",
                    "CMP_S3_KMS_KEY_ID": "key-id",
                }
            ),
            encoding="utf-8",
        )
    files = {}
    for path in sorted(candidate for candidate in payload.rglob("*") if candidate.is_file()):
        value = path.read_bytes()
        files[path.relative_to(root).as_posix()] = {
            "sha256": hashlib.sha256(value).hexdigest(),
            "size": len(value),
        }
    manifest = {
        "schema_version": 1,
        "profile": profile,
        "product_version": "0.38.0",
        "platform": "windows-x64",
        "files": files,
    }
    manifest_path = root / "bundle-manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return root, hashlib.sha256(manifest_path.read_bytes()).hexdigest()


def _environment(tmp_path: Path) -> dict[str, str]:
    return {
        "LOCALAPPDATA": str(tmp_path / "Local App Data"),
        "ProgramFiles": str(tmp_path / "Program Files"),
        "ProgramData": str(tmp_path / "Program Data"),
    }


def test_tampered_or_missing_bundle_file_is_rejected_before_install(tmp_path: Path) -> None:
    root, digest = _bundle(tmp_path)
    (root / "payload/web/index.html").write_text("tampered", encoding="utf-8")

    with pytest.raises(installer.InstallerError, match="checksum mismatch"):
        installer._verified_bundle(root, digest)


def test_manifest_checksum_is_anchored_by_install_cmd(tmp_path: Path) -> None:
    root, digest = _bundle(tmp_path)

    with pytest.raises(installer.InstallerError, match="manifest checksum mismatch"):
        installer._verified_bundle(root, "0" * 64)
    assert installer._verified_bundle(root, digest)["profile"] == "demo"


def test_user_install_and_reinstall_preserve_data_and_listen_address(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, digest = _bundle(tmp_path)
    monkeypatch.setattr(installer, "_verify_windows_11_x64", lambda: "Windows 11 x64 build 26100")
    monkeypatch.setattr(installer, "_configure_firewall", lambda *args, **kwargs: False)

    record_path = installer.install(
        bundle_root=root,
        expected_manifest_sha256=digest,
        listen_address="192.168.10.12",
        environment=_environment(tmp_path),
        admin=False,
        start=False,
    )
    record = installer._read_record(record_path)
    sentinel = Path(record.data) / "preserve.me"
    sentinel.write_text("immutable", encoding="utf-8")
    installed_python = Path(record.program, "python/python.exe")
    installed_python.write_bytes(b"tampered-installed-program")
    second = installer.install(
        bundle_root=root,
        expected_manifest_sha256=digest,
        listen_address=None,
        environment=_environment(tmp_path),
        admin=False,
        start=False,
    )

    assert second == record_path
    assert installer._read_record(second).listen_address == "192.168.10.12"
    assert sentinel.read_text(encoding="utf-8") == "immutable"
    assert installed_python.read_bytes() == b"verified-python"
    for name in ("Start.cmd", "Stop.cmd", "Status.cmd", "Uninstall.cmd"):
        assert (Path(record.control) / name).is_file()
    uninstall = (Path(record.control) / "Uninstall.cmd").read_text(encoding="utf-8")
    assert f'rmdir /s /q "{record.program}"' in uninstall
    assert f'rmdir /s /q "{record.data}"' not in uninstall
    assert 'start "" /b cmd.exe /d /c' in uninstall
    assert 'del /q ^"%~f0^"' in uninstall


def test_already_elevated_install_uses_machine_scope_without_requesting_uac(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, digest = _bundle(tmp_path)
    monkeypatch.setattr(installer, "_verify_windows_11_x64", lambda: "Windows 11 x64 build 26100")
    monkeypatch.setattr(installer, "_configure_firewall", lambda *args, **kwargs: True)

    record_path = installer.install(
        bundle_root=root,
        expected_manifest_sha256=digest,
        listen_address=None,
        environment=_environment(tmp_path),
        admin=True,
        start=False,
    )
    record = installer._read_record(record_path)

    assert record.scope == "machine"
    assert record.program.startswith(_environment(tmp_path)["ProgramFiles"])
    assert record.data.startswith(_environment(tmp_path)["ProgramData"])


def test_server_install_generates_and_preserves_restricted_secrets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, digest = _bundle(tmp_path, profile="server")
    restricted: list[Path] = []
    monkeypatch.setattr(installer, "_verify_windows_11_x64", lambda: "Windows 11 x64 build 26100")
    monkeypatch.setattr(installer, "_configure_firewall", lambda *args, **kwargs: False)
    monkeypatch.setattr(installer, "_restrict_secret_file", restricted.append)

    record_path = installer.install(
        bundle_root=root,
        expected_manifest_sha256=digest,
        listen_address=None,
        environment=_environment(tmp_path),
        admin=False,
        start=False,
    )
    record = installer._read_record(record_path)
    secret = Path(record.state) / "secrets/server.json"
    first = secret.read_bytes()
    installer.install(
        bundle_root=root,
        expected_manifest_sha256=digest,
        listen_address=None,
        environment=_environment(tmp_path),
        admin=False,
        start=False,
    )

    assert secret.read_bytes() == first
    assert secret in restricted
    auth = json.loads((Path(record.state) / "config/server-auth.json").read_text(encoding="utf-8"))
    assert auth["CMP_WORKER_ACCESS_TOKEN_FILE"].endswith("worker.token")
    assert not any(name.startswith("CMP_DEMO_") for name in auth)


def test_existing_profile_cannot_be_reused_with_preserved_other_profile_data(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    demo_root, demo_digest = _bundle(tmp_path / "demo", profile="demo")
    server_root, server_digest = _bundle(tmp_path / "server", profile="server")
    monkeypatch.setattr(installer, "_verify_windows_11_x64", lambda: "Windows 11 x64")
    monkeypatch.setattr(installer, "_configure_firewall", lambda *args, **kwargs: False)
    environment = _environment(tmp_path)
    record_path = installer.install(
        bundle_root=demo_root,
        expected_manifest_sha256=demo_digest,
        listen_address=None,
        environment=environment,
        admin=False,
        start=False,
    )
    sentinel = Path(installer._read_record(record_path).data) / "demo.seed"
    sentinel.write_text("preserve", encoding="utf-8")

    with pytest.raises(installer.InstallerError, match=r"refusing to change.*profile"):
        installer.install(
            bundle_root=server_root,
            expected_manifest_sha256=server_digest,
            listen_address=None,
            environment=environment,
            admin=False,
            start=False,
        )

    assert sentinel.read_text(encoding="utf-8") == "preserve"
    assert installer._read_record(record_path).profile == "demo"


def test_windows_server_product_type_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    version = SimpleNamespace(major=10, minor=0, build=26100, product_type=3)
    monkeypatch.setattr(os, "name", "nt")
    monkeypatch.setattr(platform, "machine", lambda: "AMD64")
    monkeypatch.setattr(installer, "_platform_attribute", lambda *args: lambda: version)

    with pytest.raises(installer.InstallerError, match="Windows Server is not supported"):
        installer._verify_windows_11_x64()


def test_non_admin_firewall_failure_prints_exact_bounded_it_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = installer._scope_paths("user", "0.38.0", _environment(tmp_path))
    monkeypatch.setattr(installer, "_firewall_exists", lambda paths: False)

    assert not installer._configure_firewall(paths, admin=False)
    output = capsys.readouterr().out

    assert 'name="CAE-Material-Platform-Web"' in output
    assert "localport=5173" in output
    assert "profile=private,domain" in output
    assert "remoteip=localsubnet" in output
    assert 'description="CAE Material Platform Web (installer-owned)"' in output
    assert 'group="CAE Material Platform Offline Installer"' in output
    assert 'program="' in output and "python.exe" in output
    assert "8000" not in output and "54329" not in output and "4318" not in output


def test_admin_firewall_update_is_idempotent_and_bounded_to_web(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = installer._scope_paths("machine", "0.38.0", _environment(tmp_path))
    commands: list[list[str]] = []

    def capture(command: list[object], *, check: bool = True) -> CompletedProcess[str]:
        rendered = [str(value) for value in command]
        commands.append(rendered)
        return CompletedProcess(rendered, 0, "Ok.", "")

    monkeypatch.setattr(installer, "_run", capture)

    assert installer._configure_firewall(paths, admin=True)
    rendered = [" ".join(command) for command in commands]

    assert "Remove-NetFirewallRule" in rendered[0]
    assert "CAE Material Platform Offline Installer" in rendered[0]
    assert "CAE Material Platform Web (installer-owned)" in rendered[0]
    assert "LocalSubnet" in rendered[0] and "python.exe" in rendered[0]
    assert "add rule" in rendered[1]
    assert "localport=5173" in rendered[1]
    assert "profile=private,domain" in rendered[1]
    assert "remoteip=localsubnet" in rendered[1]
    assert "group=CAE Material Platform Offline Installer" in rendered[1]
    assert "program=" in rendered[1] and "python.exe" in rendered[1]
    assert all(port not in rendered[1] for port in ("8000", "54329", "4318", "8889"))


def test_uninstall_deletes_only_the_owned_program_specific_firewall_rule(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = installer._scope_paths("machine", "0.38.0", _environment(tmp_path))
    commands: list[list[str]] = []

    def capture(command: list[object], *, check: bool = True) -> CompletedProcess[str]:
        rendered = [str(value) for value in command]
        commands.append(rendered)
        if "Remove-NetFirewallRule" not in rendered[-1]:
            return CompletedProcess(rendered, 0, "true\n", "")
        return CompletedProcess(rendered, 0, "Deleted 1 rule.", "")

    monkeypatch.setattr(installer, "_run", capture)

    installer._remove_firewall(paths, admin=True)

    deletion = commands[-1][-1]
    assert "Remove-NetFirewallRule" in deletion
    assert installer._FIREWALL_RULE in deletion
    assert installer._FIREWALL_DISPLAY in deletion
    assert installer._FIREWALL_GROUP in deletion
    assert str(installer._firewall_program(paths)) in deletion
    assert "LocalPort)\" -eq '5173'" in deletion
    assert "RemoteAddress) -contains 'LocalSubnet'" in deletion


def test_external_firewall_collision_is_not_selected_as_installer_owned(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = installer._scope_paths("machine", "0.38.0", _environment(tmp_path))
    commands: list[list[str]] = []

    def capture(command: list[object], *, check: bool = True) -> CompletedProcess[str]:
        rendered = [str(value) for value in command]
        commands.append(rendered)
        return CompletedProcess(rendered, 0, "false\n", "")

    monkeypatch.setattr(installer, "_run", capture)

    assert not installer._firewall_exists(paths)
    installer._delete_owned_firewall_rule(paths, check=False)

    query = commands[0][-1]
    deletion = commands[1][-1]
    for discriminator in (
        installer._FIREWALL_RULE,
        installer._FIREWALL_DISPLAY,
        installer._FIREWALL_GROUP,
        str(installer._firewall_program(paths)),
        "LocalSubnet",
        "5173",
    ):
        assert discriminator in query
        assert discriminator in deletion
    assert "Remove-NetFirewallRule" not in query
    assert "Remove-NetFirewallRule" in deletion


def test_stop_entrypoint_maps_to_the_stack_down_contract(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    record = installer.InstallRecord(
        schema_version=1,
        scope="user",
        profile="demo",
        version="0.38.0",
        bundle_manifest_sha256="a" * 64,
        program=str(tmp_path / "program"),
        control=str(tmp_path / "control"),
        state=str(tmp_path / "state"),
        data=str(tmp_path / "data"),
        listen_address="127.0.0.1",
        firewall_rule="CAE-Material-Platform-Web",
    )
    record_path = tmp_path / "install.json"
    record_path.write_text(installer._canonical_json(asdict(record)), encoding="utf-8")
    calls: list[list[str]] = []

    def capture(arguments: list[str]) -> int:
        calls.append(arguments)
        return 0

    monkeypatch.setattr(stack, "main", capture)

    assert installer._installed_action(record_path, "stop") == 0
    assert calls[0][-1] == "down"


@pytest.mark.parametrize(
    ("detail", "category"),
    [
        ("port is unavailable: 127.0.0.1:5173", "port-conflict"),
        ("server runtime cannot start until the #215 SPA OIDC contract", "server-authentication"),
        ("AppLocker blocked this program", "execution-policy"),
        ("antivirus quarantine: threat detected", "antivirus"),
        ("[WinError 5] Access is denied", "execution-policy-or-antivirus"),
        ("health check timed out", "runtime-start"),
    ],
)
def test_start_failure_diagnosis_is_specific(detail: str, category: str) -> None:
    assert installer._start_failure_category(detail) == category

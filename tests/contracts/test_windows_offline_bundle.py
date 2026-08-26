from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import zipfile
from pathlib import Path
from types import ModuleType

import pytest

_ROOT = Path(__file__).parents[2]


def _builder() -> ModuleType:
    path = _ROOT / "scripts/build_windows_offline_bundle.py"
    spec = importlib.util.spec_from_file_location("build_windows_offline_bundle", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_toolchain_manifest_matches_all_repository_version_authorities() -> None:
    builder = _builder()
    manifest = builder.load_toolchain_manifest()

    assert builder.validate_repository_versions(manifest) == "0.38.0"
    tools = manifest["tools"]
    assert {name: value["version"] for name, value in tools.items()} == {
        "node": "24.19.0",
        "npm": "11.17.0",
        "postgresql": "16.15",
        "python": "3.12.14",
        "uv": "0.12.5",
    }
    assert tools["node"]["runtime"] == "build-only"
    assert tools["npm"]["runtime"] == "build-only"
    assert tools["uv"]["runtime"] == "build-only"
    assert tools["python"]["runtime"] == "product"
    assert tools["postgresql"]["runtime"] == "product"


def test_version_drift_is_rejected(tmp_path: Path) -> None:
    builder = _builder()
    manifest = builder.load_toolchain_manifest()
    manifest["tools"]["python"]["version"] = "3.12.13"

    with pytest.raises(builder.BundleError, match="#282 toolchain version drift"):
        builder.validate_repository_versions(manifest)


def test_mismatched_cached_archive_is_preserved_for_diagnosis(tmp_path: Path) -> None:
    builder = _builder()
    cached = tmp_path / "tool.zip"
    cached.write_bytes(b"preserve-corrupt-input")
    record = {
        "archive": "tool.zip",
        "url": "https://example.test/tool.zip",
        "sha256": "0" * 64,
    }

    with pytest.raises(builder.BundleError, match="preserve it for diagnosis"):
        builder._download(record, tmp_path)

    assert cached.read_bytes() == b"preserve-corrupt-input"


def test_install_template_anchors_the_generated_manifest_before_python_runs() -> None:
    template = (_ROOT / "deploy/windows/Install.cmd").read_text(encoding="utf-8")

    assert template.count("__BUNDLE_MANIFEST_SHA256__") == 2
    assert template.count("__PAYLOAD_ARCHIVE_SHA256__") == 1
    assert '"%CMP_BOOTSTRAP%\\payload\\python\\python.exe"' in template
    assert '--bundle-root "%CMP_BOOTSTRAP%"' in template
    assert "--expected-manifest-sha256" in template
    assert "certutil -hashfile" in template
    archive_verification = 'call :verify "%~dp0payload.zip"'
    assert template.index(archive_verification) < template.index("tar.exe -xf")
    assert template.index("tar.exe -xf") < template.index(" -m cmp.tools.windows_installer")
    assert "powershell" not in template.lower()


def test_payload_archive_covers_python_loader_closure(tmp_path: Path) -> None:
    builder = _builder()
    payload = tmp_path / "payload"
    (payload / "python").mkdir(parents=True)
    (payload / "python/python.exe").write_bytes(b"python")
    (payload / "python/python312.dll").write_bytes(b"loader")
    archive = tmp_path / "payload.zip"

    builder._write_deterministic_zip(payload, archive, prefix=builder.PurePosixPath("payload"))

    with zipfile.ZipFile(archive) as payload_zip:
        assert set(payload_zip.namelist()) == {
            "payload/python/python.exe",
            "payload/python/python312.dll",
        }


@pytest.mark.skipif(os.name != "nt", reason="Install.cmd pre-execution check requires Windows")
def test_install_cmd_rejects_tampered_loader_dll_before_launch(tmp_path: Path) -> None:
    root = tmp_path / "bundle with spaces"
    root.mkdir(parents=True)
    payload_archive = root / "payload.zip"
    with zipfile.ZipFile(payload_archive, "w") as archive:
        archive.writestr("payload/python/python.exe", b"not-executed")
        archive.writestr("payload/python/python312.dll", b"verified-loader")
    manifest = root / "bundle-manifest.json"
    manifest.write_text("{}\n", encoding="utf-8", newline="\n")
    template = (_ROOT / "deploy/windows/Install.cmd").read_text(encoding="utf-8")
    script = template.replace(
        "__BUNDLE_MANIFEST_SHA256__", hashlib.sha256(manifest.read_bytes()).hexdigest()
    ).replace(
        "__PAYLOAD_ARCHIVE_SHA256__",
        hashlib.sha256(payload_archive.read_bytes()).hexdigest(),
    )
    install = root / "Install.cmd"
    install.write_text(script, encoding="utf-8", newline="")
    rewritten = root / "tampered-payload.zip"
    with zipfile.ZipFile(payload_archive) as original, zipfile.ZipFile(rewritten, "w") as tampered:
        for entry in original.infolist():
            content = original.read(entry)
            if entry.filename == "payload/python/python312.dll":
                content = b"tampered-python312.dll"
            tampered.writestr(entry, content)
    rewritten.replace(payload_archive)

    result = subprocess.run(
        ["cmd.exe", "/d", "/c", str(install)], text=True, capture_output=True, check=False
    )

    assert result.returncode == 2
    assert "pre-execution checksum mismatch" in result.stderr


def test_bundle_runtime_contains_the_topology_drift_inputs_used_by_host_doctor() -> None:
    source = (_ROOT / "scripts/build_windows_offline_bundle.py").read_text(encoding="utf-8")

    assert 'root / "deploy/stack"' in source
    assert 'root / "deploy/compose/docker-compose.demo.yml"' in source
    assert 'root / "scripts/render_stack_topology.py"' in source
    assert 'for directory in ("bin", "lib", "share")' in source
    assert 'postgres_payload / "bin/stackbuilder.exe"' in source
    assert '"pgAdmin 4"' not in source
    assert '"StackBuilder"' not in source


def test_server_bundle_configuration_rejects_demo_plugin_and_secret_values(
    tmp_path: Path,
) -> None:
    builder = _builder()
    baseline = {
        "CMP_OIDC_ISSUER": "https://identity.example.test",
        "CMP_OIDC_AUDIENCE": "cmp-server",
        "CMP_OIDC_JWKS_URL": "https://identity.example.test/jwks.json",
        "CMP_OBJECT_STORE_BACKEND": "s3",
        "CMP_S3_BUCKET": "cmp-server",
        "CMP_S3_KMS_KEY_ID": "key-id",
    }
    path = tmp_path / "auth.json"
    path.write_text(json.dumps({**baseline, "CMP_DEMO_IDENTITY": "true"}), encoding="utf-8")
    with pytest.raises(builder.BundleError, match="forbidden"):
        builder._server_auth_template(path)
    path.write_text(json.dumps({**baseline, "CMP_CLIENT_SECRET": "secret"}), encoding="utf-8")
    with pytest.raises(builder.BundleError, match="secret_fields"):
        builder._server_auth_template(path)
    path.write_text(
        json.dumps({**baseline, "CMP_OIDC_ISSUER": "http://identity.example.test"}),
        encoding="utf-8",
    )
    with pytest.raises(builder.BundleError, match="requires HTTPS"):
        builder._server_auth_template(path)


def test_documentation_routes_the_exact_windows_installer_commands() -> None:
    readme = (_ROOT / "README.md").read_text(encoding="utf-8")
    guide = (_ROOT / "docs/user-guide/19-windows-offline-installation.md").read_text(
        encoding="utf-8"
    )
    deploy = (_ROOT / "deploy/windows/README.md").read_text(encoding="utf-8")

    for command in ("Install.cmd", "Start.cmd", "Stop.cmd", "Status.cmd", "Uninstall.cmd"):
        assert command in guide
    assert "19-windows-offline-installation.md" in readme
    assert "build_windows_offline_bundle.py" in deploy

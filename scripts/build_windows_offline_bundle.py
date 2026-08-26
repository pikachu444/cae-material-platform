"""Build a checksum-verified Windows 11 x64 CMP offline installation bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import tomllib
import urllib.request
import zipfile
from collections.abc import Mapping, Sequence
from pathlib import Path, PurePosixPath
from typing import Any, Literal, cast

Profile = Literal["demo", "server"]

_ROOT = Path(__file__).parents[1]
_MANIFEST = _ROOT / "deploy/windows/toolchain-manifest.json"
_INSTALL_TEMPLATE = _ROOT / "deploy/windows/Install.cmd"


class BundleError(RuntimeError):
    """Expected bundle construction failure."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _canonical_json(value: Mapping[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def load_toolchain_manifest(path: Path = _MANIFEST) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise BundleError(f"toolchain manifest is invalid: {path}: {error}") from error
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        raise BundleError("toolchain manifest must be a schema_version 1 object")
    if value.get("platform") != "windows-x64":
        raise BundleError("toolchain manifest platform must be windows-x64")
    tools = value.get("tools")
    required = {"python", "uv", "node", "npm", "postgresql"}
    if not isinstance(tools, dict) or set(tools) != required:
        raise BundleError(f"toolchain manifest must contain exactly {sorted(required)}")
    for name, record in tools.items():
        if not isinstance(record, dict) or not all(
            isinstance(record.get(field), str) and record[field]
            for field in ("version", "url", "archive", "architecture", "runtime", "sha256")
        ):
            raise BundleError(f"toolchain manifest record is invalid: {name}")
        digest = cast(str, record["sha256"])
        if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
            raise BundleError(f"toolchain manifest SHA-256 is invalid: {name}")
        if not cast(str, record["url"]).startswith("https://"):
            raise BundleError(f"toolchain manifest URL must use HTTPS: {name}")
    expected_architectures = {
        "python": "x86_64",
        "uv": "x86_64",
        "node": "x86_64",
        "npm": "any",
        "postgresql": "x86_64",
    }
    actual_architectures = {
        name: cast(Mapping[str, str], record)["architecture"] for name, record in tools.items()
    }
    if actual_architectures != expected_architectures:
        raise BundleError(f"toolchain manifest architecture drift: {actual_architectures}")
    return cast(dict[str, Any], value)


def validate_repository_versions(manifest: Mapping[str, Any], root: Path = _ROOT) -> str:
    tools = cast(Mapping[str, Mapping[str, str]], manifest["tools"])
    python_version = (root / ".python-version").read_text(encoding="utf-8").strip()
    pyproject = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    uv_required = str(pyproject["tool"]["uv"]["required-version"])
    package = json.loads((root / "package.json").read_text(encoding="utf-8"))
    lock = json.loads((root / "package-lock.json").read_text(encoding="utf-8"))
    expected = {
        "python": python_version,
        "uv": uv_required.removeprefix("=="),
        "node": str(package["engines"]["node"]),
        "npm": str(package["engines"]["npm"]),
    }
    lock_root = lock["packages"][""]["engines"]
    if lock_root != package["engines"]:
        raise BundleError("package.json and package-lock.json Node/npm engines differ")
    mismatches = {
        name: {"repository": version, "manifest": tools[name]["version"]}
        for name, version in expected.items()
        if tools[name]["version"] != version
    }
    if mismatches:
        raise BundleError(f"#282 toolchain version drift: {mismatches}")
    project_version = str(pyproject["project"]["version"])
    if not project_version:
        raise BundleError("pyproject project.version is missing")
    return project_version


def _default_cache() -> Path:
    if os.name == "nt" and os.environ.get("LOCALAPPDATA"):
        return Path(os.environ["LOCALAPPDATA"]) / "CAE Material Platform" / "cache" / "downloads"
    configured = os.environ.get("XDG_CACHE_HOME")
    base = Path(configured) if configured else Path.home() / ".cache"
    return base / "cae-material-platform" / "downloads"


def _download(record: Mapping[str, str], cache: Path) -> Path:
    cache.mkdir(parents=True, exist_ok=True)
    destination = cache / record["archive"]
    if destination.exists():
        if destination.is_file() and _sha256(destination) == record["sha256"]:
            return destination
        raise BundleError(
            "cached download checksum mismatch; preserve it for diagnosis and use a clean cache: "
            f"{destination}"
        )
    partial = destination.with_suffix(destination.suffix + ".part")
    if partial.exists():
        partial.unlink()
    try:
        with urllib.request.urlopen(record["url"]) as response, partial.open("wb") as stream:
            shutil.copyfileobj(response, stream)
        actual = _sha256(partial)
        if actual != record["sha256"]:
            raise BundleError(
                f"download checksum mismatch: {record['archive']} "
                f"expected={record['sha256']} actual={actual}"
            )
        partial.replace(destination)
    except BaseException:
        partial.unlink(missing_ok=True)
        raise
    return destination


def _safe_member(name: str) -> PurePosixPath:
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts:
        raise BundleError(f"archive member escapes extraction root: {name}")
    return path


def _extract_zip(archive: Path, destination: Path) -> None:
    with zipfile.ZipFile(archive) as source:
        for member in source.infolist():
            _safe_member(member.filename)
        source.extractall(destination)


def _extract_tar(archive: Path, destination: Path) -> None:
    with tarfile.open(archive, "r:gz") as source:
        for member in source.getmembers():
            _safe_member(member.name)
            if member.issym() or member.islnk():
                raise BundleError(f"archive link is not allowed: {member.name}")
        source.extractall(destination, filter="data")


def _single_directory(root: Path, label: str) -> Path:
    children = list(root.iterdir())
    if len(children) != 1 or not children[0].is_dir():
        raise BundleError(f"{label} archive must contain one root directory")
    return children[0]


def _run(
    command: Sequence[str | Path],
    *,
    cwd: Path,
    environment: Mapping[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [str(value) for value in command],
        cwd=cwd,
        env=dict(environment) if environment is not None else None,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    if result.returncode:
        detail = (result.stderr or result.stdout).strip()
        raise BundleError(f"command failed ({result.returncode}): {command[0]}: {detail}")
    return result


def _copy_runtime(root: Path, payload: Path, web_dist: Path, profile: Profile) -> None:
    runtime = payload / "runtime"
    for source, relative in (
        (root / "pyproject.toml", Path("pyproject.toml")),
        (root / "alembic.ini", Path("alembic.ini")),
        (root / "backend/migrations", Path("backend/migrations")),
        (root / "deploy/stack", Path("deploy/stack")),
        (
            root / "deploy/windows/toolchain-manifest.json",
            Path("deploy/windows/toolchain-manifest.json"),
        ),
        (
            root / "deploy/compose/docker-compose.demo.yml",
            Path("deploy/compose/docker-compose.demo.yml"),
        ),
        (root / "plugins/reference", Path("plugins/reference")),
        (
            root / "scripts/render_stack_topology.py",
            Path("scripts/render_stack_topology.py"),
        ),
        (root / "scripts/seed_full_demo.py", Path("scripts/seed_full_demo.py")),
    ):
        target = runtime / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            shutil.copytree(source, target)
        else:
            shutil.copy2(source, target)
    shutil.copytree(web_dist, payload / "web")
    (runtime / "bundle-profile.json").write_text(
        _canonical_json({"profile": profile}), encoding="utf-8", newline="\n"
    )


def _server_auth_template(path: Path) -> dict[str, str]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise BundleError(f"Server auth configuration is invalid: {path}: {error}") from error
    if not isinstance(value, dict) or not all(
        isinstance(name, str) and isinstance(item, str) and item for name, item in value.items()
    ):
        raise BundleError("Server auth configuration must contain non-empty string values")
    auth = cast(dict[str, str], value)
    forbidden = sorted(name for name in auth if name.startswith(("CMP_DEMO_", "CMP_PLUGIN_")))
    secret_like = sorted(name for name in auth if "SECRET" in name or "PASSWORD" in name)
    required = {
        "CMP_OIDC_ISSUER",
        "CMP_OIDC_AUDIENCE",
        "CMP_OIDC_JWKS_URL",
        "CMP_OBJECT_STORE_BACKEND",
        "CMP_S3_BUCKET",
        "CMP_S3_KMS_KEY_ID",
    }
    missing = sorted(required - auth.keys())
    if (
        forbidden
        or secret_like
        or missing
        or auth.get("CMP_OBJECT_STORE_BACKEND", "").lower() != "s3"
    ):
        raise BundleError(
            f"Server auth configuration rejected: missing={missing or 'none'} "
            f"forbidden={forbidden or 'none'} secret_fields={secret_like or 'none'}"
        )
    for name in ("CMP_OIDC_ISSUER", "CMP_OIDC_JWKS_URL"):
        if not auth[name].startswith("https://"):
            raise BundleError(f"Server auth configuration requires HTTPS: {name}")
    auth.pop("CMP_WORKER_ACCESS_TOKEN_FILE", None)
    return auth


def _inventory(payload: Path) -> dict[str, dict[str, int | str]]:
    files: dict[str, dict[str, int | str]] = {}
    for path in sorted(candidate for candidate in payload.rglob("*") if candidate.is_file()):
        relative = path.relative_to(payload.parent).as_posix()
        files[relative] = {"sha256": _sha256(path), "size": path.stat().st_size}
    return files


def _write_deterministic_zip(
    source: Path, destination: Path, *, prefix: PurePosixPath | None = None
) -> None:
    with zipfile.ZipFile(
        destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6
    ) as archive:
        for path in sorted(candidate for candidate in source.rglob("*") if candidate.is_file()):
            relative = PurePosixPath(path.relative_to(source).as_posix())
            if prefix is not None:
                relative = prefix / relative
            info = zipfile.ZipInfo(relative.as_posix(), date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, path.read_bytes())


def build_bundle(
    *,
    profile: Profile,
    output_dir: Path,
    cache: Path,
    server_auth_config: Path | None,
    root: Path = _ROOT,
) -> Path:
    if os.name != "nt":
        raise BundleError("Windows bundle construction requires a connected Windows x64 build host")
    manifest = load_toolchain_manifest(root / "deploy/windows/toolchain-manifest.json")
    product_version = validate_repository_versions(manifest, root)
    tools = cast(dict[str, dict[str, str]], manifest["tools"])
    if profile == "server" and server_auth_config is None:
        raise BundleError("Server bundle requires --server-auth-config")
    if profile == "demo" and server_auth_config is not None:
        raise BundleError("Demo bundle must not include Server auth configuration")
    archives = {name: _download(record, cache) for name, record in tools.items()}
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="cmp-windows-bundle-") as temporary:
        work = Path(temporary)
        extracted = work / "extracted"
        extracted.mkdir()
        for name in ("python", "uv", "node", "npm", "postgresql"):
            target = extracted / name
            target.mkdir()
            if archives[name].suffix == ".zip":
                _extract_zip(archives[name], target)
            else:
                _extract_tar(archives[name], target)
        bundle = work / f"CAE-Material-Platform-{product_version}-{profile}-windows-x64"
        payload = bundle / "payload"
        payload.mkdir(parents=True)
        python_root = _single_directory(extracted / "python", "Python")
        shutil.copytree(python_root, payload / "python")
        postgres_root = _single_directory(extracted / "postgresql", "PostgreSQL")
        postgres_payload = payload / "postgresql"
        postgres_payload.mkdir()
        for directory in ("bin", "lib", "share"):
            shutil.copytree(postgres_root / directory, postgres_payload / directory)
        (postgres_payload / "bin/stackbuilder.exe").unlink(missing_ok=True)
        for filename in ("server_license.txt", "commandlinetools_3rd_party_licenses.txt"):
            shutil.copy2(postgres_root / filename, postgres_payload / filename)
        node_root = _single_directory(extracted / "node", "Node")
        npm_root = _single_directory(extracted / "npm", "npm")
        bundled_npm = node_root / "node_modules" / "npm"
        if bundled_npm.exists():
            shutil.rmtree(bundled_npm)
        shutil.copytree(npm_root, bundled_npm)
        uv_exe = extracted / "uv" / "uv.exe"
        if not uv_exe.is_file():
            raise BundleError("verified uv archive does not contain uv.exe")
        environment = os.environ.copy()
        environment["PATH"] = f"{node_root}{os.pathsep}{environment.get('PATH', '')}"
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        versions = {
            "python": _run([payload / "python/python.exe", "--version"], cwd=root).stdout.strip(),
            "uv": _run([uv_exe, "--version"], cwd=root).stdout.strip(),
            "node": _run([node_root / "node.exe", "--version"], cwd=root).stdout.strip(),
            "npm": _run(
                [node_root / "npm.cmd", "--version"], cwd=root, environment=environment
            ).stdout.strip(),
            "postgresql": _run(
                [payload / "postgresql/bin/postgres.exe", "--version"], cwd=root
            ).stdout.strip(),
        }
        expected_fragments = {
            "python": tools["python"]["version"],
            "uv": tools["uv"]["version"],
            "node": tools["node"]["version"],
            "npm": tools["npm"]["version"],
            "postgresql": tools["postgresql"]["version"],
        }
        mismatches = {
            name: output
            for name, output in versions.items()
            if expected_fragments[name] not in output
        }
        if mismatches:
            raise BundleError(f"verified tool version output mismatch: {mismatches}")
        web_source = work / "web-source"
        web_source.mkdir()
        shutil.copy2(root / "package.json", web_source / "package.json")
        shutil.copy2(root / "package-lock.json", web_source / "package-lock.json")
        (web_source / "scripts").mkdir()
        shutil.copy2(
            root / "scripts/check_web_bundle.mjs",
            web_source / "scripts/check_web_bundle.mjs",
        )
        shutil.copytree(
            root / "apps/web",
            web_source / "apps/web",
            ignore=shutil.ignore_patterns("node_modules", "dist"),
        )
        _run([node_root / "npm.cmd", "ci"], cwd=web_source, environment=environment)
        _run([node_root / "npm.cmd", "run", "build"], cwd=web_source, environment=environment)
        requirements = work / "requirements.txt"
        _run(
            [
                uv_exe,
                "export",
                "--frozen",
                "--no-dev",
                "--no-emit-project",
                "--no-header",
                "--output-file",
                requirements,
            ],
            cwd=root,
            environment=environment,
        )
        wheels = work / "wheels"
        wheels.mkdir()
        _run([uv_exe, "build", "--wheel", "--out-dir", wheels], cwd=root, environment=environment)
        _run(
            [
                uv_exe,
                "pip",
                "install",
                "--python",
                payload / "python/python.exe",
                "--require-hashes",
                "--requirements",
                requirements,
            ],
            cwd=root,
            environment=environment,
        )
        wheel = next(wheels.glob("cae_material_platform-*.whl"), None)
        if wheel is None:
            raise BundleError("application wheel was not produced")
        _run(
            [
                uv_exe,
                "pip",
                "install",
                "--python",
                payload / "python/python.exe",
                "--no-deps",
                wheel,
            ],
            cwd=root,
            environment=environment,
        )
        for bytecode in payload.rglob("__pycache__"):
            shutil.rmtree(bytecode)
        _copy_runtime(root, payload, web_source / "apps/web/dist", profile)
        if server_auth_config is not None:
            config = payload / "config"
            config.mkdir()
            (config / "server-auth.json").write_text(
                _canonical_json(_server_auth_template(server_auth_config)),
                encoding="utf-8",
                newline="\n",
            )
        files = _inventory(payload)
        descriptor = {
            "schema_version": 1,
            "profile": profile,
            "product_version": product_version,
            "platform": "windows-x64",
            "toolchain_manifest_sha256": _sha256(root / "deploy/windows/toolchain-manifest.json"),
            "files": files,
        }
        descriptor_path = bundle / "bundle-manifest.json"
        descriptor_path.write_text(_canonical_json(descriptor), encoding="utf-8", newline="\n")
        descriptor_sha = _sha256(descriptor_path)
        payload_archive = bundle / "payload.zip"
        _write_deterministic_zip(payload, payload_archive, prefix=PurePosixPath("payload"))
        payload_archive_sha = _sha256(payload_archive)
        shutil.rmtree(payload)
        install = (root / "deploy/windows/Install.cmd").read_text(encoding="utf-8")
        if install.count("__BUNDLE_MANIFEST_SHA256__") != 2:
            raise BundleError(
                "Install.cmd template must contain two manifest checksum placeholders"
            )
        if install.count("__PAYLOAD_ARCHIVE_SHA256__") != 1:
            raise BundleError(
                "Install.cmd template must contain one payload archive checksum placeholder"
            )
        (bundle / "Install.cmd").write_text(
            install.replace("__BUNDLE_MANIFEST_SHA256__", descriptor_sha).replace(
                "__PAYLOAD_ARCHIVE_SHA256__", payload_archive_sha
            ),
            encoding="utf-8",
            newline="",
        )
        destination = output_dir / f"{bundle.name}.zip"
        if destination.exists():
            raise BundleError(f"refusing to overwrite an existing offline bundle: {destination}")
        partial = destination.with_suffix(destination.suffix + ".part")
        partial.unlink(missing_ok=True)
        try:
            _write_deterministic_zip(bundle, partial)
            partial.replace(destination)
        except BaseException:
            partial.unlink(missing_ok=True)
            raise
    print(
        f"Windows offline bundle ready: {destination} sha256={_sha256(destination)} "
        f"profile={profile}"
    )
    return destination


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=("demo", "server"), required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--download-cache", type=Path, default=_default_cache())
    parser.add_argument("--server-auth-config", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        build_bundle(
            profile=cast(Profile, args.profile),
            output_dir=args.output_dir,
            cache=args.download_cache,
            server_auth_config=args.server_auth_config,
        )
        return 0
    except (BundleError, OSError, subprocess.SubprocessError) as error:
        print(f"Windows bundle error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

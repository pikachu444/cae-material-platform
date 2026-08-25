from __future__ import annotations

import argparse
import json
import platform
import re
import shutil
import subprocess
import sys
import tomllib
from collections.abc import Sequence
from pathlib import Path
from typing import Any

PYTHON_DOCKERFILE_PATTERN = re.compile(
    r"^FROM python:(?P<version>\d+\.\d+\.\d+)-slim-trixie@sha256:(?P<digest>[0-9a-f]{64})$",
    re.MULTILINE,
)
NODE_DOCKERFILE_PATTERN = re.compile(
    r"^FROM node:(?P<version>\d+\.\d+\.\d+)-alpine3\.24@sha256:"
    r"(?P<digest>[0-9a-f]{64})(?: AS [A-Za-z0-9_.-]+)?$",
    re.MULTILINE,
)
UV_INSTALL_PATTERN = re.compile(r"uv==(?P<version>\d+\.\d+\.\d+)")


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise ValueError(f"cannot read {path}: {exc}") from exc


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(_read_text(path))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in {path}: {exc.msg}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"expected a JSON object in {path}")
    return value


def _read_toml(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as handle:
            value = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ValueError(f"invalid TOML in {path}: {exc}") from exc
    return value


def expected_versions(root: Path) -> dict[str, str]:
    package = _read_json(root / "package.json")
    pyproject = _read_toml(root / "pyproject.toml")
    engines = package.get("engines")
    tool = pyproject.get("tool")
    uv = tool.get("uv") if isinstance(tool, dict) else None
    if not isinstance(engines, dict):
        raise ValueError("package.json is missing engines")
    if not isinstance(uv, dict) or not isinstance(uv.get("required-version"), str):
        raise ValueError("pyproject.toml is missing tool.uv.required-version")
    required_uv = uv["required-version"]
    if not required_uv.startswith("=="):
        raise ValueError("tool.uv.required-version must use an exact == version")
    return {
        "python": _read_text(root / ".python-version"),
        "uv": required_uv[2:],
        "node": _read_text(root / ".node-version"),
        "npm": str(engines.get("npm", "")),
    }


def _docker_version(
    path: Path, pattern: re.Pattern[str], *, runtime: str
) -> tuple[str, str] | None:
    match = pattern.search(_read_text(path))
    if match is None:
        return None
    return match.group("version"), match.group("digest")


def validate_repository(root: Path) -> tuple[str, ...]:
    try:
        versions = expected_versions(root)
        package = _read_json(root / "package.json")
        package_lock = _read_json(root / "package-lock.json")
    except ValueError as exc:
        return (str(exc),)

    errors: list[str] = []
    engines = package.get("engines", {})
    if engines.get("node") != versions["node"]:
        errors.append(
            "package.json engines.node mismatch "
            f"(expected={versions['node']}, actual={engines.get('node')})"
        )
    if package.get("packageManager") != f"npm@{versions['npm']}":
        errors.append(
            "package.json packageManager mismatch "
            f"(expected=npm@{versions['npm']}, actual={package.get('packageManager')})"
        )

    lock_root = package_lock.get("packages", {}).get("")
    lock_engines = lock_root.get("engines") if isinstance(lock_root, dict) else None
    if lock_engines != engines:
        errors.append("package-lock.json root engines do not match package.json")

    for relative in ("deploy/compose/Dockerfile.api", "deploy/compose/Dockerfile.restore"):
        path = root / relative
        docker_version = _docker_version(path, PYTHON_DOCKERFILE_PATTERN, runtime="Python")
        if docker_version is None:
            errors.append(f"{relative} must pin Python slim-trixie with a sha256 digest")
            continue
        version, _ = docker_version
        if version != versions["python"]:
            errors.append(
                f"{relative} Python mismatch (expected={versions['python']}, actual={version})"
            )
        uv_match = UV_INSTALL_PATTERN.search(_read_text(path))
        uv_version = uv_match.group("version") if uv_match else "missing"
        if uv_version != versions["uv"]:
            errors.append(
                f"{relative} uv mismatch (expected={versions['uv']}, actual={uv_version})"
            )

    web_path = root / "deploy/compose/Dockerfile.web"
    node_docker_version = _docker_version(web_path, NODE_DOCKERFILE_PATTERN, runtime="Node.js")
    if node_docker_version is None:
        errors.append("deploy/compose/Dockerfile.web must pin Node alpine3.24 with a sha256 digest")
    elif node_docker_version[0] != versions["node"]:
        errors.append(
            "deploy/compose/Dockerfile.web Node.js mismatch "
            f"(expected={versions['node']}, actual={node_docker_version[0]})"
        )

    return tuple(errors)


def _resolved_executable(value: str) -> str:
    path = Path(value)
    if path.parent != Path("."):
        return str(path)
    return shutil.which(value) or value


def _command_version(command: str, *, cwd: Path) -> tuple[str | None, str | None]:
    executable = _resolved_executable(command)
    try:
        result = subprocess.run(
            [executable, "--version"],
            cwd=str(cwd),
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        return None, str(exc)
    output = (result.stdout or result.stderr).strip()
    if result.returncode:
        return None, output or f"exit {result.returncode}"
    match = re.search(r"\d+\.\d+\.\d+", output)
    return (match.group(0), None) if match else (None, f"unrecognized output: {output}")


def validate_runtime(
    root: Path,
    *,
    uv_bin: str = "uv",
    node_bin: str = "node",
    npm_bin: str = "npm",
) -> tuple[str, ...]:
    try:
        versions = expected_versions(root)
    except ValueError as exc:
        return (str(exc),)

    errors: list[str] = []
    observed_python = platform.python_version()
    if observed_python != versions["python"]:
        errors.append(
            f"Python version mismatch (expected={versions['python']}, actual={observed_python})"
        )

    for name, command in (("uv", uv_bin), ("Node.js", node_bin), ("npm", npm_bin)):
        expected_key = "node" if name == "Node.js" else name.lower()
        observed, failure = _command_version(command, cwd=root)
        if failure:
            errors.append(f"{name} version check failed: {failure}")
        elif observed != versions[expected_key]:
            errors.append(
                f"{name} version mismatch (expected={versions[expected_key]}, actual={observed})"
            )
    return tuple(errors)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate repository and active development-tool version alignment."
    )
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--uv-bin", default="uv")
    parser.add_argument("--node-bin", default="node")
    parser.add_argument("--npm-bin", default="npm")
    parser.add_argument("--repository-only", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    root = args.root.resolve()
    errors = list(validate_repository(root))
    if not args.repository_only:
        errors.extend(
            validate_runtime(
                root,
                uv_bin=args.uv_bin,
                node_bin=args.node_bin,
                npm_bin=args.npm_bin,
            )
        )
    if errors:
        print("Development environment check failed:", file=sys.stderr)
        for error in dict.fromkeys(errors):
            print(f"- {error}", file=sys.stderr)
        return 2
    versions = expected_versions(root)
    print(
        "Development environment check passed: "
        + ", ".join(f"{name}={version}" for name, version in versions.items())
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

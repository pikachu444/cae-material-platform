from __future__ import annotations

import json
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

from pytest import CaptureFixture, MonkeyPatch

ROOT = Path(__file__).parents[2]

_SPEC = spec_from_file_location(
    "check_development_environment", ROOT / "scripts" / "check_development_environment.py"
)
assert _SPEC and _SPEC.loader
environment = module_from_spec(_SPEC)
sys.modules[_SPEC.name] = environment
_SPEC.loader.exec_module(environment)


def test_repository_declarations_are_aligned() -> None:
    assert environment.validate_repository(ROOT) == ()


def test_node_runtime_pin_accepts_a_named_multistage_builder() -> None:
    dockerfile = "FROM node:24.19.0-alpine3.24@sha256:" + "a" * 64 + " AS build\n"

    match = environment.NODE_DOCKERFILE_PATTERN.search(dockerfile)

    assert match is not None
    assert match.group("version") == "24.19.0"


def test_repository_check_reports_package_lock_drift(tmp_path: Path) -> None:
    for relative in (
        ".python-version",
        ".node-version",
        "pyproject.toml",
        "package.json",
        "package-lock.json",
        "deploy/compose/Dockerfile.api",
        "deploy/compose/Dockerfile.restore",
        "deploy/compose/Dockerfile.web",
    ):
        source = ROOT / relative
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())

    package_lock = json.loads((tmp_path / "package-lock.json").read_text(encoding="utf-8"))
    package_lock["packages"][""]["engines"]["node"] = "24.18.0"
    (tmp_path / "package-lock.json").write_text(json.dumps(package_lock), encoding="utf-8")

    errors = environment.validate_repository(tmp_path)

    assert "package-lock.json root engines do not match package.json" in errors


def test_runtime_check_reports_every_version_mismatch(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(environment.platform, "python_version", lambda: "3.12.13")
    observed = iter((("0.11.29", None), ("24.18.0", None), ("11.13.0", None)))
    monkeypatch.setattr(environment, "_command_version", lambda *args, **kwargs: next(observed))

    errors = environment.validate_runtime(ROOT)

    assert errors == (
        "Python version mismatch (expected=3.12.14, actual=3.12.13)",
        "uv version mismatch (expected=0.12.5, actual=0.11.29)",
        "Node.js version mismatch (expected=24.19.0, actual=24.18.0)",
        "npm version mismatch (expected=11.17.0, actual=11.13.0)",
    )


def test_cli_can_check_repository_without_active_runtime(
    capsys: CaptureFixture[str],
) -> None:
    result = environment.main(["--root", str(ROOT), "--repository-only"])
    output = capsys.readouterr()

    assert result == 0
    assert output.err == ""
    assert "Python=3.12.14" not in output.out
    assert "python=3.12.14" in output.out

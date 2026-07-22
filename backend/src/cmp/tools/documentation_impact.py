"""Reject user-visible changes that omit their current documentation evidence."""

from __future__ import annotations

import argparse
import subprocess
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Literal

ImpactMode = Literal["staged", "range", "worktree"]

_GUIDE_PREFIX = "docs/user-guide/"
_SCREENSHOT_MANIFEST = "docs/user-guide/screenshot-manifest.yaml"
_NAVIGATION_CONTRACT = "docs/user-guide/navigation-contract.yaml"
_CURRENT_IMAGE_PREFIX = "docs/user-guide/images/current/"
_OPENAPI_CONTRACTS = {
    "contracts/http/openapi.yaml",
    "contracts/http/openapi.baseline.yaml",
}


class DocumentationImpactError(RuntimeError):
    """Raised when changed files do not include required current documentation."""


@dataclass(frozen=True, slots=True)
class DocumentationImpactReport:
    changed_files: tuple[str, ...]
    visual_files: tuple[str, ...]
    requirements: tuple[str, ...]


def _normalize(paths: Iterable[str]) -> set[str]:
    return {path.strip().replace("\\", "/") for path in paths if path.strip()}


def _git_lines(project: Path, arguments: list[str], *, allow_failure: bool = False) -> set[str]:
    result = subprocess.run(
        ["git", *arguments],
        cwd=project,
        check=not allow_failure,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return set()
    return _normalize(result.stdout.splitlines())


def changed_files(project: Path, mode: ImpactMode) -> set[str]:
    if mode == "staged":
        return _git_lines(project, ["diff", "--cached", "--name-only", "--diff-filter=ACMR"])
    if mode == "range":
        return _git_lines(
            project,
            ["diff", "--name-only", "--diff-filter=ACMR", "origin/main...HEAD"],
            allow_failure=True,
        )
    changed = set()
    changed |= _git_lines(project, ["diff", "--name-only", "--diff-filter=ACMR"])
    changed |= _git_lines(project, ["diff", "--cached", "--name-only", "--diff-filter=ACMR"])
    changed |= _git_lines(project, ["ls-files", "--others", "--exclude-standard"])
    changed |= _git_lines(
        project,
        ["diff", "--name-only", "--diff-filter=ACMR", "origin/main...HEAD"],
        allow_failure=True,
    )
    return changed


def _is_test_path(path: str) -> bool:
    pure = PurePosixPath(path)
    name = pure.name.lower()
    return (
        "tests" in pure.parts
        or "__tests__" in pure.parts
        or ".test." in name
        or ".spec." in name
        or path.startswith("apps/web/e2e/")
    )


def _is_visual_source(path: str) -> bool:
    return (
        path.startswith("apps/web/")
        and PurePosixPath(path).suffix.lower() in {".tsx", ".css"}
        and not _is_test_path(path)
    )


def evaluate_documentation_impact(paths: Iterable[str]) -> DocumentationImpactReport:
    changed = _normalize(paths)
    visual = sorted(path for path in changed if _is_visual_source(path))
    guide_changed = any(
        path.startswith(_GUIDE_PREFIX) and path.endswith(".md") for path in changed
    )
    manifest_changed = _SCREENSHOT_MANIFEST in changed
    png_changed = any(
        path.startswith(_CURRENT_IMAGE_PREFIX) and path.lower().endswith(".png") for path in changed
    )
    requirements: list[str] = []

    if visual:
        if not guide_changed:
            requirements.append("update a current docs/user-guide/*.md workflow")
        if not manifest_changed:
            requirements.append("update docs/user-guide/screenshot-manifest.yaml")
        if not png_changed:
            requirements.append("add or update a current user-guide PNG")

    app_changed = "apps/web/src/app.tsx" in changed
    if app_changed and _NAVIGATION_CONTRACT not in changed:
        requirements.append("update docs/user-guide/navigation-contract.yaml for app.tsx")

    workflow_contract_changed = bool(changed & _OPENAPI_CONTRACTS)
    if workflow_contract_changed and not guide_changed:
        requirements.append("update a current user guide for the OpenAPI workflow change")

    if requirements:
        visual_note = f"; visual sources: {', '.join(visual)}" if visual else ""
        raise DocumentationImpactError("; ".join(requirements) + visual_note)

    return DocumentationImpactReport(
        changed_files=tuple(sorted(changed)),
        visual_files=tuple(visual),
        requirements=(),
    )


def verify_documentation_impact(root: Path, mode: ImpactMode) -> DocumentationImpactReport:
    project = root.resolve()
    return evaluate_documentation_impact(changed_files(project, mode))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--mode", choices=("staged", "range", "worktree"), default="staged")
    args = parser.parse_args()
    try:
        report = verify_documentation_impact(args.root, args.mode)
    except (OSError, subprocess.CalledProcessError, DocumentationImpactError) as error:
        parser.exit(1, f"documentation impact check failed: {error}\n")
    print(
        "documentation impact check passed: "
        f"{len(report.changed_files)} changed files, {len(report.visual_files)} visual sources"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

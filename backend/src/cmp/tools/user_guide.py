"""Verify current documentation, navigation contracts, and screenshot evidence."""

from __future__ import annotations

import argparse
import fnmatch
import re
import struct
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import yaml

_MARKDOWN_LINK = re.compile(r"!?\[[^\]]*\]\(([^)#]+)(?:#[^)]+)?\)")
_MARKDOWN_IMAGE = re.compile(r"!\[[^\]]*\]\(([^)#]+)(?:#[^)]+)?\)")
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_HISTORICAL_IMAGE = re.compile(r"docs/15-demo/images/(?:t\d|e2e-|governed-|process-|test-run-)")
_STALE_CURRENT_PATTERNS = {
    "retired global navigation": re.compile(
        r"(?:전역|global)\s+\*\*(?:Dashboard|Models|Exports|Governance)\*\*", re.IGNORECASE
    ),
    "manual connection panel": re.compile(r"Connection\s+panel", re.IGNORECASE),
    "retired T-46 screenshot": re.compile(r"t46-[^)\s]+\.png", re.IGNORECASE),
}
_README_HEADINGS = (
    "## 핵심 사용 흐름",
    "## 주요 기능",
    "## 5분 로컬 실행",
    "## 구조",
    "## 개발과 검증",
    "## 문서",
)


class UserGuideContractError(RuntimeError):
    """Raised when current documentation or screenshot evidence is incomplete."""


@dataclass(frozen=True, slots=True)
class UserGuideReport:
    document_count: int
    capture_count: int
    navigation_count: int
    classified_markdown_count: int
    current_document_count: int


def _mapping(value: object, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise UserGuideContractError(f"{name} must be a mapping")
    return cast(dict[str, Any], value)


def _sequence(value: object, name: str) -> list[Any]:
    if not isinstance(value, list):
        raise UserGuideContractError(f"{name} must be a list")
    return value


def _text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise UserGuideContractError(f"{name} must be non-blank text")
    return value.strip()


def _inside(path: Path, parent: Path, name: str) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(parent.resolve())
    except ValueError as error:
        raise UserGuideContractError(f"{name} escapes {parent}") from error
    return resolved


def _relative(path: Path, project: Path) -> str:
    return path.resolve().relative_to(project.resolve()).as_posix()


def _glob_matches(path: str, pattern: str) -> bool:
    candidate = pattern
    while True:
        if fnmatch.fnmatchcase(path, candidate):
            return True
        if "/**/" not in candidate:
            return False
        candidate = candidate.replace("/**/", "/", 1)


def _tracked_markdown(project: Path) -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "*.md"],
        cwd=project,
        check=True,
        capture_output=True,
        text=True,
    )
    return sorted(line.strip().replace("\\", "/") for line in result.stdout.splitlines() if line)


def _documentation_classes(project: Path) -> dict[str, str]:
    manifest_path = project / "docs" / "documentation-manifest.yaml"
    manifest = _mapping(
        yaml.safe_load(manifest_path.read_text(encoding="utf-8")),
        "documentation manifest",
    )
    rules = _sequence(manifest.get("rules"), "documentation manifest rules")
    classified: dict[str, str] = {}
    for path in _tracked_markdown(project):
        matches: list[str] = []
        for ordinal, raw_rule in enumerate(rules, start=1):
            rule = _mapping(raw_rule, f"documentation rule {ordinal}")
            status = _text(rule.get("status"), f"documentation rule {ordinal} status")
            if status not in {"current", "authoritative", "historical", "reference"}:
                raise UserGuideContractError(f"unsupported documentation status: {status}")
            patterns = _sequence(rule.get("include"), f"documentation rule {ordinal} include")
            if any(
                _glob_matches(path, _text(pattern, "documentation include"))
                for pattern in patterns
            ):
                matches.append(status)
        if len(matches) != 1:
            raise UserGuideContractError(
                f"tracked Markdown must match exactly one documentation rule: {path} ({matches})"
            )
        classified[path] = matches[0]
    return classified


def _image_dimensions(path: Path) -> tuple[int, int]:
    value = path.read_bytes()
    if len(value) >= 24 and value[:8] == _PNG_SIGNATURE and value[12:16] == b"IHDR":
        return cast(tuple[int, int], struct.unpack(">II", value[16:24]))
    raise UserGuideContractError(f"screenshot is not a PNG image: {path}")


def _verify_current_documents(project: Path, classes: dict[str, str]) -> set[str]:
    images: set[str] = set()
    for relative_document, status in classes.items():
        if status != "current":
            continue
        document = project / relative_document
        content = document.read_text(encoding="utf-8")
        for label, pattern in _STALE_CURRENT_PATTERNS.items():
            if pattern.search(content):
                raise UserGuideContractError(f"{relative_document} contains {label}")
        for match in _MARKDOWN_LINK.finditer(content):
            target = match.group(1).strip().strip("<>")
            if re.match(r"^(?:https?://|mailto:)", target):
                continue
            linked = _inside(document.parent / target, project, f"link in {relative_document}")
            if not linked.exists():
                raise UserGuideContractError(
                    f"missing link target in {relative_document}: {target}"
                )
        for match in _MARKDOWN_IMAGE.finditer(content):
            target = match.group(1).strip().strip("<>")
            linked = _inside(document.parent / target, project, f"image in {relative_document}")
            relative_image = _relative(linked, project)
            if _HISTORICAL_IMAGE.search(relative_image):
                raise UserGuideContractError(
                    "current document uses a historical screenshot: "
                    f"{relative_document} -> {relative_image}"
                )
            images.add(relative_image)
    return images


def _verify_readme(project: Path, registered_images: set[str]) -> None:
    readme = (project / "README.md").read_text(encoding="utf-8")
    if len(readme.splitlines()) > 200:
        raise UserGuideContractError("README.md must remain at or below 200 lines")
    for heading in _README_HEADINGS:
        if heading not in readme:
            raise UserGuideContractError(f"README.md is missing required section: {heading}")
    if "docker compose -f deploy/compose/docker-compose.demo.yml up --build -d" not in readme:
        raise UserGuideContractError("README.md is missing the runnable Compose quickstart")
    readme_images = {
        _relative(_inside(project / match.group(1), project, "README image"), project)
        for match in _MARKDOWN_IMAGE.finditer(readme)
    }
    if len(readme_images & registered_images) < 2:
        raise UserGuideContractError("README.md must show at least two current registered screens")


def verify_user_guide(root: Path) -> UserGuideReport:
    project = root.resolve()
    guide_root = project / "docs" / "user-guide"
    image_root = project / "docs" / "15-demo" / "images"
    documents = sorted(guide_root.glob("*.md"))
    if not documents:
        raise UserGuideContractError("no user-guide documents were found")

    classes = _documentation_classes(project)
    current_document_images = _verify_current_documents(project, classes)

    manifest = _mapping(
        yaml.safe_load((guide_root / "screenshot-manifest.yaml").read_text(encoding="utf-8")),
        "screenshot manifest",
    )
    captures = _sequence(manifest.get("captures"), "screenshot manifest captures")
    capture_ids: set[str] = set()
    registered_images: set[str] = set()
    for ordinal, raw_capture in enumerate(captures, start=1):
        capture = _mapping(raw_capture, f"capture {ordinal}")
        capture_id = _text(capture.get("id"), f"capture {ordinal} id")
        if capture_id in capture_ids:
            raise UserGuideContractError(f"duplicate screenshot id: {capture_id}")
        capture_ids.add(capture_id)
        route = _text(capture.get("route"), f"capture {capture_id} route")
        _text(capture.get("workflow"), f"capture {capture_id} workflow")
        _text(capture.get("fixture"), f"capture {capture_id} fixture")
        if not route.startswith("/"):
            raise UserGuideContractError(f"capture route must be absolute: {capture_id}")
        relative_image = _text(capture.get("image"), f"capture {capture_id} image")
        image = _inside(guide_root / relative_image, image_root, f"capture {capture_id} image")
        if not image.is_file() or image.suffix.lower() != ".png" or image.stat().st_size < 10_000:
            raise UserGuideContractError(f"capture is missing or implausibly small: {capture_id}")
        width, height = _image_dimensions(image)
        if width < 800 or height < 700:
            raise UserGuideContractError(
                f"capture is below the minimum evidence viewport: {capture_id}"
            )
        if capture.get("width") != width or capture.get("height") != height:
            raise UserGuideContractError(f"capture viewport drifted: {capture_id}")
        project_image = _relative(image, project)
        if project_image in registered_images:
            raise UserGuideContractError(
                f"screenshot image is registered more than once: {project_image}"
            )
        registered_images.add(project_image)

    missing_registration = current_document_images - registered_images
    unused_registration = registered_images - current_document_images
    if missing_registration:
        raise UserGuideContractError(
            f"current document images are absent from the manifest: {sorted(missing_registration)}"
        )
    if unused_registration:
        raise UserGuideContractError(
            "current manifest images are unused by current documents: "
            f"{sorted(unused_registration)}"
        )
    _verify_readme(project, registered_images)

    navigation = _mapping(
        yaml.safe_load((guide_root / "navigation-contract.yaml").read_text(encoding="utf-8")),
        "navigation contract",
    )
    items = _sequence(navigation.get("items"), "navigation contract items")
    navigation_sources = (
        project / "apps" / "web" / "src" / "app.tsx",
        project / "apps" / "web" / "src" / "design" / "application-shell.tsx",
    )
    app_source = "\n".join(
        source.read_text(encoding="utf-8") for source in navigation_sources if source.is_file()
    )
    index_source = (guide_root / "index.md").read_text(encoding="utf-8")
    labels: set[str] = set()
    routes: set[str] = set()
    for ordinal, raw_item in enumerate(items, start=1):
        item = _mapping(raw_item, f"navigation item {ordinal}")
        label = _text(item.get("label"), f"navigation item {ordinal} label")
        route = _text(item.get("route"), f"navigation item {ordinal} route")
        guide_name = _text(item.get("guide"), f"navigation item {ordinal} guide")
        if label in labels or route in routes:
            raise UserGuideContractError(f"duplicate navigation label or route: {label} {route}")
        labels.add(label)
        routes.add(route)
        if f'label: "{label}"' not in app_source or f'target: "{route}"' not in app_source:
            raise UserGuideContractError(f"navigation contract drifted from web navigation: {label}")
        guide = _inside(guide_root / guide_name, guide_root, f"navigation guide for {label}")
        if not guide.is_file() or f"({guide_name})" not in index_source:
            raise UserGuideContractError(f"navigation guide is missing from the index: {label}")

    return UserGuideReport(
        document_count=len(documents),
        capture_count=len(captures),
        navigation_count=len(items),
        classified_markdown_count=len(classes),
        current_document_count=sum(status == "current" for status in classes.values()),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    try:
        report = verify_user_guide(args.root)
    except (OSError, subprocess.CalledProcessError, UserGuideContractError) as error:
        parser.exit(1, f"user-guide check failed: {error}\n")
    print(
        "user-guide check passed: "
        f"{report.document_count} guide documents, {report.capture_count} current captures, "
        f"{report.navigation_count} navigation items, "
        f"{report.classified_markdown_count} classified Markdown files"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

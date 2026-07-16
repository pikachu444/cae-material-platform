"""Verify task-oriented guides, navigation contracts, and screenshot evidence."""

from __future__ import annotations

import argparse
import re
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import yaml

_MARKDOWN_LINK = re.compile(r"!?\[[^\]]*\]\(([^)#]+)(?:#[^)]+)?\)")
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


class UserGuideContractError(RuntimeError):
    """Raised when user-visible workflow evidence is stale or incomplete."""


@dataclass(frozen=True, slots=True)
class UserGuideReport:
    document_count: int
    capture_count: int
    navigation_count: int


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


def _image_dimensions(path: Path) -> tuple[int, int]:
    value = path.read_bytes()
    if len(value) >= 24 and value[:8] == _PNG_SIGNATURE and value[12:16] == b"IHDR":
        return cast(tuple[int, int], struct.unpack(">II", value[16:24]))
    if value[:2] == b"\xff\xd8":
        offset = 2
        start_of_frame = frozenset(range(0xC0, 0xC4)) | frozenset(range(0xC5, 0xC8)) | frozenset(
            range(0xC9, 0xCC)
        ) | frozenset(range(0xCD, 0xD0))
        while offset + 9 <= len(value):
            if value[offset] != 0xFF:
                offset += 1
                continue
            marker = value[offset + 1]
            offset += 2
            if marker in {0xD8, 0xD9}:
                continue
            if offset + 2 > len(value):
                break
            segment_length = int.from_bytes(value[offset : offset + 2], "big")
            if segment_length < 2 or offset + segment_length > len(value):
                break
            if marker in start_of_frame:
                height = int.from_bytes(value[offset + 3 : offset + 5], "big")
                width = int.from_bytes(value[offset + 5 : offset + 7], "big")
                return width, height
            offset += segment_length
    raise UserGuideContractError(f"screenshot is not a recognized PNG/JPEG image: {path}")


def verify_user_guide(root: Path) -> UserGuideReport:
    project = root.resolve()
    guide_root = project / "docs" / "user-guide"
    image_root = project / "docs" / "15-demo" / "images"
    documents = sorted(guide_root.glob("*.md"))
    if not documents:
        raise UserGuideContractError("no user-guide documents were found")

    for document in documents:
        content = document.read_text(encoding="utf-8")
        for match in _MARKDOWN_LINK.finditer(content):
            target = match.group(1).strip()
            if re.match(r"^(?:https?://|mailto:)", target):
                continue
            linked = _inside(document.parent / target, project, f"link in {document.name}")
            if not linked.exists():
                raise UserGuideContractError(f"missing link target in {document.name}: {target}")

    manifest = _mapping(
        yaml.safe_load((guide_root / "screenshot-manifest.yaml").read_text(encoding="utf-8")),
        "screenshot manifest",
    )
    captures = _sequence(manifest.get("captures"), "screenshot manifest captures")
    capture_ids: set[str] = set()
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
        declared_width = capture.get("width")
        declared_height = capture.get("height")
        if declared_width is not None and declared_width != width:
            raise UserGuideContractError(f"capture width drifted: {capture_id}")
        if declared_height is not None and declared_height != height:
            raise UserGuideContractError(f"capture height drifted: {capture_id}")

    navigation = _mapping(
        yaml.safe_load((guide_root / "navigation-contract.yaml").read_text(encoding="utf-8")),
        "navigation contract",
    )
    items = _sequence(navigation.get("items"), "navigation contract items")
    app_source = (project / "apps" / "web" / "src" / "app.tsx").read_text(encoding="utf-8")
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
            raise UserGuideContractError(f"navigation contract drifted from app.tsx: {label}")
        guide = _inside(guide_root / guide_name, guide_root, f"navigation guide for {label}")
        if not guide.is_file() or f"({guide_name})" not in index_source:
            raise UserGuideContractError(f"navigation guide is missing from the index: {label}")

    return UserGuideReport(len(documents), len(captures), len(items))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    try:
        report = verify_user_guide(args.root)
    except UserGuideContractError as error:
        parser.exit(1, f"user-guide check failed: {error}\n")
    print(
        "user-guide check passed: "
        f"{report.document_count} documents, {report.capture_count} captures, "
        f"{report.navigation_count} navigation items"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

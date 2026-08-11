"""Capture issue #184 wide-viewport direct 100%-pixel inspection crops."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

from PIL import Image
from playwright.sync_api import Browser, Locator, sync_playwright

SCRIPT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_ROOT))

import capture_current_product as current  # noqa: E402
import capture_high_dpi_decision as decision  # noqa: E402

VIEWPORTS = ((1920, 1080), (2560, 1440), (3840, 2160))
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _record(
    destination: Path,
    *,
    viewport: tuple[int, int],
    surface: str,
    source: str,
    interactions: list[str],
) -> dict[str, Any]:
    with Image.open(destination) as image:
        width, height = image.size
    return {
        "path": destination.as_posix(),
        "surface": surface,
        "source": source,
        "original_pixels": f"{width}x{height}",
        "source_viewport": f"{viewport[0]}x{viewport[1]}",
        "browser_zoom_percent": 100,
        "dpr": 1,
        "density": "standard",
        "sha256": _sha256(destination),
        "interactions": interactions,
    }


def _screenshot(
    locator: Locator,
    destination: Path,
    *,
    viewport: tuple[int, int],
    surface: str,
    source: str,
    interactions: list[str],
) -> dict[str, Any]:
    locator.wait_for(state="visible", timeout=30_000)
    locator.screenshot(path=str(destination), animations="disabled")
    if destination.read_bytes()[:8] != PNG_SIGNATURE:
        raise RuntimeError(f"direct crop is not a PNG: {destination}")
    return _record(
        destination,
        viewport=viewport,
        surface=surface,
        source=source,
        interactions=interactions,
    )


def _capture_materials_and_density(
    browser: Browser,
    base_url: str,
    output: Path,
    viewport: tuple[int, int],
) -> list[dict[str, Any]]:
    width, height = viewport
    page = current._new_page(browser, base_url, width, height)
    try:
        current._open_materials_search(page, base_url)
        current._wait_for_settled(page)
        directory = output / f"{width}x{height}"
        directory.mkdir(parents=True, exist_ok=True)
        records = [
            _screenshot(
                page.locator(".application-menu-bar"),
                directory / "header.png",
                viewport=viewport,
                surface="header",
                source=f"live:/materials@{width}x{height}",
                interactions=["primary navigation visible"],
            ),
            _screenshot(
                page.get_by_label("Materials navigator", exact=True),
                directory / "materials-navigator.png",
                viewport=viewport,
                surface="materials-navigator",
                source=f"live:/materials@{width}x{height}",
                interactions=["navigator expanded", "exact tree visible"],
            ),
            _screenshot(
                page.locator(".materials-result-table-wrap"),
                directory / "materials-table.png",
                viewport=viewport,
                surface="materials-table",
                source=f"live:/materials@{width}x{height}",
                interactions=["result table visible", "bounded identity columns"],
            ),
        ]
        menu = page.locator(".application-user-menu")
        summary = menu.locator("summary")
        summary.focus()
        summary.press("Enter")
        density = menu.get_by_role("group", name="Display density", exact=True)
        density.wait_for(state="visible", timeout=10_000)
        standard = density.get_by_role("radio", name="Standard", exact=True)
        if not standard.is_checked():
            raise RuntimeError("wide crop session did not start with Standard selected")
        records.append(
            _screenshot(
                menu.locator(".application-utility-menu"),
                directory / "density-control.png",
                viewport=viewport,
                surface="density-control",
                source=f"live:/materials@{width}x{height}",
                interactions=["keyboard opened", "Standard selected", "reset visible"],
            )
        )
        summary.press("Escape")
        if menu.get_attribute("open") is not None:
            raise RuntimeError("Escape did not close the display density utility menu")
        if not summary.evaluate("node => document.activeElement === node"):
            raise RuntimeError("display density utility menu did not return focus")
        return records
    finally:
        page.context.close()


def _capture_graph(
    browser: Browser,
    base_url: str,
    output: Path,
    viewport: tuple[int, int],
) -> dict[str, Any]:
    width, height = viewport
    page = current._new_page(browser, base_url, width, height)
    try:
        current._prepare_modeling(page, base_url, verify_reload=False)
        current._wait_for_data_plot(page)
        destination = output / f"{width}x{height}" / "modeling-data-graph.png"
        return _screenshot(
            page.locator(".persistent-modeling-plot"),
            destination,
            viewport=viewport,
            surface="modeling-data-graph",
            source=f"live:/modeling?stage=data@{width}x{height}",
            interactions=["SVG resized", "axis/legend/labels visible", "hit region retained"],
        )
    finally:
        page.context.close()


def _capture_administration_form(
    browser: Browser,
    base_url: str,
    output: Path,
    viewport: tuple[int, int],
) -> dict[str, Any]:
    width, height = viewport
    page = current._new_page(browser, base_url, width, height)
    try:
        decision._setup_administration_database(page, base_url)
        page.locator(".application-workspace").evaluate(
            "node => node.scrollTo({ top: 0, left: 0 })"
        )
        destination = output / f"{width}x{height}" / "administration-form.png"
        return _screenshot(
            page.locator(".schema-property-editor"),
            destination,
            viewport=viewport,
            surface="administration-form",
            source=f"live:/administration/database@{width}x{height}",
            interactions=["semantic third pane", "readable form bound", "actions visible"],
        )
    finally:
        page.context.close()


def _crop_native_preview(
    evidence_root: Path,
    output: Path,
    viewport: tuple[int, int],
) -> dict[str, Any]:
    width, height = viewport
    source = evidence_root / "after" / "standard" / f"modeling-export-{width}x{height}.png"
    destination = output / f"{width}x{height}" / "export-native-preview.png"
    destination.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as image:
        if image.size != viewport:
            raise RuntimeError(f"native preview source viewport drift: {source} {image.size}")
        box = (300, 134, width - 315, height - 52)
        image.crop(box).save(destination)
    return _record(
        destination,
        viewport=viewport,
        surface="export-native-preview",
        source=source.as_posix(),
        interactions=["1:1 pixel crop", "shared preview minimum", "native content visible"],
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:5173")
    parser.add_argument(
        "--evidence-root",
        type=Path,
        default=Path(
            "docs/17-evidence/images/issue-184-high-dpi-global-implementation"
        ),
    )
    args = parser.parse_args()
    current.CAPTURE_DISPLAY_DENSITY = "standard"
    target = (args.evidence_root / "crops").resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=".issue-184-crops-", dir=target.parent
    ) as temporary:
        staged = Path(temporary)
        records: list[dict[str, Any]] = []
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                for viewport in VIEWPORTS:
                    records.extend(
                        _capture_materials_and_density(
                            browser, args.base_url, staged, viewport
                        )
                    )
                    records.append(
                        _capture_graph(browser, args.base_url, staged, viewport)
                    )
                    records.append(
                        _capture_administration_form(
                            browser, args.base_url, staged, viewport
                        )
                    )
                    records.append(
                        _crop_native_preview(
                            args.evidence_root.resolve(), staged, viewport
                        )
                    )
            finally:
                browser.close()
        expected = len(VIEWPORTS) * 7
        if len(records) != expected:
            raise RuntimeError(f"direct crop count drift: {len(records)} != {expected}")
        for record in records:
            staged_path = Path(str(record["path"]))
            record["path"] = (target / staged_path.relative_to(staged)).as_posix()
        (staged / "manifest.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "capture": "issue-184-direct-100-percent-crops",
                    "resampling": "none",
                    "physical_4k_readability": "DEFERRED_TO_223",
                    "images": records,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        current._replace_capture_directory(staged, target)
    print(json.dumps({"output": target.as_posix(), "captures": expected}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

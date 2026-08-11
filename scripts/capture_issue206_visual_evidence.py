"""Capture the issue #206 curve-contract visual acceptance packet.

The five-viewport current-guide captures are first validated by
``capture_current_product.py``.  This issue-owned step preserves those originals,
extracts unscaled pixel crops, and exercises the statistical-band, keyboard
tooltip, Evidence, and metadata-absent states at 1440x900.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import capture_current_product as current
import yaml
from PIL import Image
from playwright.sync_api import Browser, Page, Route, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
CURRENT = ROOT / "docs/user-guide/images/current"
EVIDENCE = ROOT / "docs/17-evidence/images/issue-206-curve-channel-metadata-and-deviation"
BASE_SHA = "93ff2ba32a988a20cd910dbb3f2b29d728a20a40"
VIEWPORTS = ((1366, 768), (1440, 900), (1920, 1080), (2560, 1440), (3840, 2160))
WIDE_VIEWPORTS = ((1920, 1080), (2560, 1440), (3840, 2160))
ROUTES = ("material-curves", "modeling-data", "modeling-process", "modeling-fit")


def _project_ref(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _git(*args: str) -> str:
    return subprocess.run(
        ("git", *args), cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


def _copy_originals() -> None:
    target = EVIDENCE / "after/originals"
    target.mkdir(parents=True, exist_ok=True)
    for route in ROUTES:
        for width, height in VIEWPORTS:
            source = CURRENT / f"{route}-{width}x{height}.png"
            if not source.is_file():
                raise RuntimeError(f"validated current capture is missing: {source}")
            shutil.copyfile(source, target / source.name)


def _extract_before_originals() -> None:
    """Preserve the accepted origin/main visual baseline without a second checkout."""

    target = EVIDENCE / "before/originals"
    target.mkdir(parents=True, exist_ok=True)
    paths = [
        f"docs/user-guide/images/current/{route}-{width}x{height}.png"
        for route in ("modeling-data", "modeling-process", "modeling-fit")
        for width, height in WIDE_VIEWPORTS
    ]
    paths.extend(
        f"docs/user-guide/images/current/material-detail-{width}x{height}.png"
        for width, height in WIDE_VIEWPORTS
    )
    for relative in paths:
        destination = target / Path(relative).name
        with destination.open("wb") as stream:
            subprocess.run(
                ("git", "show", f"{BASE_SHA}:{relative}"),
                cwd=ROOT,
                check=True,
                stdout=stream,
            )


def _bounded_box(
    width: int, height: int, box: tuple[int, int, int, int]
) -> tuple[int, int, int, int]:
    left, top, right, bottom = box
    return (
        max(0, min(width - 1, left)),
        max(0, min(height - 1, top)),
        max(1, min(width, right)),
        max(1, min(height, bottom)),
    )


def _crop_originals() -> None:
    originals = EVIDENCE / "after/originals"
    crops = EVIDENCE / "after/crops"
    crops.mkdir(parents=True, exist_ok=True)
    for route in ROUTES:
        for width, height in WIDE_VIEWPORTS:
            source = originals / f"{route}-{width}x{height}.png"
            with Image.open(source) as image:
                if image.size != (width, height):
                    raise RuntimeError(f"original viewport drifted: {source} {image.size}")
                context_gutter = 300 if route == "material-curves" else 0
                top = 360 if route == "material-curves" else 340
                controls_bottom = 650 if route == "material-curves" else 420
                regions = {
                    "header": (0, 0, width, min(height, 180)),
                    "navigator": (0, 90, min(width, 320), height - 18),
                    "controls": (
                        300,
                        160,
                        width - context_gutter,
                        min(height, controls_bottom),
                    ),
                    "graph": (
                        300 if route != "material-curves" else 610,
                        top,
                        width - context_gutter,
                        height - 18,
                    ),
                }
                for region, box in regions.items():
                    image.crop(_bounded_box(width, height, box)).save(
                        crops / f"{route}-{width}x{height}-{region}.png"
                    )


def _console_guard(page: Page) -> list[str]:
    failures: list[str] = []
    page.on(
        "console",
        lambda message: (
            failures.append(f"console.{message.type}: {message.text}")
            if message.type == "error"
            else None
        ),
    )
    page.on("pageerror", lambda error: failures.append(f"pageerror: {error}"))
    return failures


def _open_statistics_curve(page: Page, base_url: str) -> None:
    current._open_material_detail(page, base_url)
    current._open_material_curves(page)
    page.locator(".material-curve-list button").filter(
        has_text="Replicate statistics curve"
    ).click()
    page.get_by_text("Statistical curve · View only", exact=True).first.wait_for(timeout=30_000)
    page.locator(".ensemble-confidence-band").wait_for(timeout=30_000)
    page.locator(".curve-band-meaning").get_by_text(
        re.compile(r"confidence interval", re.IGNORECASE)
    ).wait_for(timeout=30_000)
    current._wait_for_settled(page)
    page.locator(".contract-curve-frame").scroll_into_view_if_needed()


def _capture_special_states(browser: Browser, base_url: str) -> dict[str, Any]:
    states = EVIDENCE / "after/states"
    states.mkdir(parents=True, exist_ok=True)
    provenance: dict[str, Any] = {
        "browser": f"Chromium {browser.version}",
        "css_viewport": "1440x900",
        "device_pixel_ratio": None,
        "browser_zoom": "100%",
        "states": [],
    }

    page = current._new_page(browser, base_url, 1440, 900)
    console_failures = _console_guard(page)
    _open_statistics_curve(page, base_url)
    definition_text = page.locator(".contract-curve-heading p").inner_text()
    if "Declared curve contract" not in definition_text:
        raise RuntimeError(f"statistical curve definition is not declared: {definition_text}")
    band_toggle = page.locator(".curve-legend button").filter(
        has_text=re.compile(r"confidence interval", re.IGNORECASE)
    )
    band_toggle.click()
    if page.locator(".ensemble-confidence-band").count() != 0:
        raise RuntimeError("keyboard-reachable band toggle did not hide the band")
    band_toggle.click()
    page.locator(".ensemble-confidence-band").wait_for(timeout=10_000)
    chart = page.locator(".contract-curve-svg")
    chart.focus()
    chart.press("Home")
    tooltip = page.locator(".contract-curve-tooltip")
    tooltip.wait_for(timeout=10_000)
    tooltip_text = tooltip.inner_text()
    if "confidence interval" not in tooltip_text.lower() or "n=" not in tooltip_text:
        raise RuntimeError(f"band tooltip lost statistical meaning: {tooltip_text}")
    tooltip_file = states / "material-statistics-keyboard-tooltip-1440x900.png"
    page.screenshot(path=tooltip_file)
    with Image.open(tooltip_file) as image:
        image.crop((300, 330, 1435, 895)).save(
            states / "material-statistics-keyboard-tooltip-graph-crop.png"
        )
    page.keyboard.press("Escape")
    if tooltip.count() != 0:
        raise RuntimeError("Escape did not clear the curve tooltip")
    evidence = page.locator("details.curve-evidence")
    evidence.locator("summary").click()
    if evidence.get_attribute("open") is None:
        raise RuntimeError("Evidence disclosure did not open")
    evidence.scroll_into_view_if_needed()
    evidence_file = states / "material-statistics-evidence-1440x900.png"
    page.screenshot(path=evidence_file)
    evidence.screenshot(path=states / "material-statistics-evidence-crop.png")
    provenance["device_pixel_ratio"] = page.evaluate("window.devicePixelRatio")
    provenance["states"].extend(
        [
            {
                "file": _project_ref(tooltip_file),
                "route": page.url,
                "fixture": "live synthetic declared replicate Statistical Result",
                "interaction": "band toggle off/on; SVG focus; Home; Escape",
            },
            {
                "file": _project_ref(evidence_file),
                "route": page.url,
                "fixture": "live exact Artifact/revision/calculation provenance",
                "interaction": "Evidence summary click",
            },
        ]
    )
    if console_failures:
        raise RuntimeError(f"statistical state browser errors: {console_failures}")
    page.context.close()

    page = current._new_page(browser, base_url, 1440, 900)
    console_failures = _console_guard(page)

    def absent(route: Route) -> None:
        response = route.fetch()
        payload = response.json()
        payload["curve_metadata"]["metadata_state"] = "absent"
        payload["curve_metadata"]["definition_sha256"] = None
        payload["curve_metadata"]["definition"] = None
        payload["curve_series"] = None
        payload["modeling_use"] = "view_only"
        payload["modeling_source"] = None
        route.fulfill(response=response, json=payload)

    page.route(re.compile(r".*/curve-values/.*/preview(?:\?.*)?$"), absent)
    current._open_material_detail(page, base_url)
    page.get_by_role("tab", name="Curves", exact=True).click()
    page.get_by_text(
        "This revision has no recorded channel or deviation metadata.", exact=True
    ).wait_for(timeout=30_000)
    page.get_by_text(
        "The stored curve remains available, but axes, units, bands, and Fit "
        "eligibility are not inferred.",
        exact=True,
    ).wait_for(timeout=30_000)
    if page.locator(".contract-curve-svg, .ensemble-confidence-band").count() != 0:
        raise RuntimeError("metadata-absent state inferred a chart or band")
    absent_file = states / "material-legacy-metadata-absent-1440x900.png"
    page.screenshot(path=absent_file)
    page.locator("article.contract-curve.absent").screenshot(
        path=states / "material-legacy-metadata-absent-crop.png"
    )
    provenance["states"].append(
        {
            "file": _project_ref(absent_file),
            "route": page.url,
            "fixture": "synthetic frontend response adapter over a live exact curve preview",
            "interaction": "metadata_state=absent; definition/series removed",
            "note": (
                "Backend unknown-legacy behavior is separately verified against real "
                "Artifact bytes; this route adapter isolates the visible recovery state."
            ),
        }
    )
    if console_failures:
        raise RuntimeError(f"metadata-absent state browser errors: {console_failures}")
    page.context.close()
    return provenance


def _file_record(path: Path) -> dict[str, Any]:
    value = path.read_bytes()
    record: dict[str, Any] = {
        "path": _project_ref(path),
        "sha256": hashlib.sha256(value).hexdigest(),
        "bytes": len(value),
    }
    if path.suffix.lower() == ".png":
        with Image.open(path) as image:
            record["pixels"] = f"{image.width}x{image.height}"
    return record


def _duplicate_groups() -> list[dict[str, Any]]:
    inventory_roots = (
        ROOT / "docs/00-research",
        ROOT / "docs/17-evidence/images",
        ROOT / "docs/user-guide/images",
    )
    by_digest: dict[str, list[Path]] = {}
    for inventory_root in inventory_roots:
        for path in inventory_root.rglob("*"):
            if path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg"}:
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
                by_digest.setdefault(digest, []).append(path)
    return [
        {
            "rationale": (
                "Issue #206 preserves this byte-identical accepted source/current image as an "
                "explicit before or after original; the separate path records lifecycle and "
                "capture provenance without altering pixels."
            ),
            "images": sorted(_project_ref(path) for path in paths),
        }
        for paths in by_digest.values()
        if len(paths) > 1 and any(path.is_relative_to(EVIDENCE) for path in paths)
    ]


def _write_manifest(special: dict[str, Any]) -> None:
    files = sorted(
        path
        for path in EVIDENCE.rglob("*")
        if path.is_file() and path.name != "visual-evidence.yaml"
    )
    manifest = {
        "issue": 206,
        "captured_at": datetime.now(UTC).isoformat(),
        "source_commit": _git("rev-parse", "HEAD"),
        "base_commit": BASE_SHA,
        "branch": _git("branch", "--show-current"),
        "base_url": "http://127.0.0.1:5173",
        "synthetic_non_production_only": True,
        "current_capture_command": (
            "uv run --with playwright==1.62.0 python "
            "scripts/capture_current_product.py --only-materials; "
            "--only-modeling-data-session; --only-modeling-process-fit-viewports"
        ),
        "issue_capture_command": (
            "uv run --with playwright==1.62.0 --with pillow "
            "python scripts/capture_issue206_visual_evidence.py"
        ),
        "viewports": [f"{width}x{height}" for width, height in VIEWPORTS],
        "special_state_provenance": special,
        "before": {
            "source": "accepted current-guide PNG blobs from exact origin/main base",
            "materials_note": (
                "origin/main had no Materials curve-chart capture; its exact Material detail "
                "originals are retained as the visible baseline and no missing chart is fabricated"
            ),
        },
        "allowed_duplicate_groups": _duplicate_groups(),
        "files": [_file_record(path) for path in files],
    }
    (EVIDENCE / "visual-evidence.yaml").write_text(
        yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def main() -> int:
    _copy_originals()
    _extract_before_originals()
    _crop_originals()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            special = _capture_special_states(browser, "http://127.0.0.1:5173")
        finally:
            browser.close()
    _write_manifest(special)
    print(
        json.dumps(
            {
                "source_commit": _git("rev-parse", "HEAD"),
                "evidence": str(EVIDENCE.relative_to(ROOT)),
                "files": sum(1 for path in EVIDENCE.rglob("*") if path.is_file()),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Capture the issue #212 explicit toe-compensation visual evidence packet.

The script starts from a clean implementation commit, refreshes the ten current
Process/Fit guide captures through the canonical capture journey, preserves the
exact ``origin/main`` baseline, extracts unscaled pixel crops, and records the
warning-save gate plus exact Fit source evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import capture_current_product as current
import yaml
from PIL import Image
from playwright.sync_api import Browser, Page, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
CURRENT = ROOT / "docs/user-guide/images/current"
EVIDENCE = ROOT / "docs/17-evidence/images/issue-212-explicit-toe-compensation"
BASE_SHA = "c341679e0e17654c6e13f718cd37044b29423431"
VIEWPORTS = ((1366, 768), (1440, 900), (1920, 1080), (2560, 1440), (3840, 2160))
WIDE_VIEWPORTS = ((1920, 1080), (2560, 1440), (3840, 2160))
ROUTES = ("modeling-process", "modeling-fit")


def _project_ref(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _evidence_ref(path: Path, packet: Path) -> str:
    if path.is_relative_to(packet):
        path = EVIDENCE / path.relative_to(packet)
    return _project_ref(path)


def _git(*args: str) -> str:
    return subprocess.run(
        ("git", *args), cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


def _refresh_current(base_url: str) -> dict[str, Any]:
    result = subprocess.run(
        (
            sys.executable,
            str(ROOT / "scripts/capture_current_product.py"),
            "--base-url",
            base_url,
            "--output",
            str(CURRENT),
            "--density",
            "standard",
            "--only-modeling-process-fit-viewports",
        ),
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    if not lines:
        raise RuntimeError("current Process/Fit capture returned no report")
    report = json.loads(lines[-1])
    if report.get("captures") != 10 or len(report.get("measurements", [])) != 10:
        raise RuntimeError(f"current Process/Fit capture report drifted: {report!r}")
    return report


def _extract_base_originals(packet: Path) -> None:
    target = packet / "before/originals"
    target.mkdir(parents=True)
    for route in ROUTES:
        for width, height in VIEWPORTS:
            relative = f"docs/user-guide/images/current/{route}-{width}x{height}.png"
            destination = target / Path(relative).name
            with destination.open("wb") as stream:
                subprocess.run(
                    ("git", "show", f"{BASE_SHA}:{relative}"),
                    cwd=ROOT,
                    check=True,
                    stdout=stream,
                )


def _copy_after_originals(packet: Path) -> None:
    target = packet / "after/originals"
    target.mkdir(parents=True)
    for route in ROUTES:
        for width, height in VIEWPORTS:
            source = CURRENT / f"{route}-{width}x{height}.png"
            if not source.is_file():
                raise RuntimeError(f"validated current capture is missing: {source}")
            shutil.copyfile(source, target / source.name)


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


def _crop_originals(packet: Path, lifecycle: str) -> None:
    originals = packet / lifecycle / "originals"
    crops = packet / lifecycle / "crops"
    crops.mkdir(parents=True)
    for route in ROUTES:
        for width, height in WIDE_VIEWPORTS:
            source = originals / f"{route}-{width}x{height}.png"
            with Image.open(source) as image:
                if image.size != (width, height):
                    raise RuntimeError(f"original viewport drifted: {source} {image.size}")
                if route == "modeling-process":
                    controls = (302, 135, width, min(height, 425))
                    graph = (302, 425, width, height)
                else:
                    controls = (302, 160, width, min(height, 345))
                    graph = (302, 345, width, height)
                regions = {
                    "header": (0, 0, width, min(height, 180)),
                    "navigator": (0, 100, min(width, 302), height),
                    "controls": controls,
                    "graph": graph,
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


def _capture_states(browser: Browser, base_url: str, packet: Path) -> dict[str, Any]:
    states = packet / "after/states"
    states.mkdir(parents=True)
    warning_file = states / "modeling-process-toe-warning-1440x900.png"
    fit_file = states / "modeling-fit-toe-source-evidence-1440x900.png"
    fit_crop = states / "modeling-fit-toe-source-evidence-crop.png"

    page = current._new_page(browser, base_url, 1440, 900)
    failures = _console_guard(page)
    current._prepare_modeling_process(page, base_url, verify_data_reload=True)
    current._prepare_toe_compensation_preview(
        page,
        warning_capture_path=warning_file,
    )
    process_geometry = current._measure_process_fit(page, "process", 1440, 900)
    pointer = current._save_process_output_for_fit(
        page,
        label="Toe-corrected Process result visual evidence",
        reason="Bind reviewed toe compensation as the exact Fit source.",
        verify_default_preview=False,
    )
    current._open_modeling_stage(page, "fit")
    current._click_modeling_fit_preview_and_wait(page)
    _, body, _ = current._open_fit_evidence(page)
    source = body.locator(".fit-source-evidence")
    method_label = source.get_by_text(
        "OLS zero intercept · v1.0.0 · exact saved Process step", exact=True
    )
    method_label.wait_for(state="visible", timeout=30_000)
    fit_geometry = method_label.evaluate(
        """element => {
          const rect = element.getBoundingClientRect();
          return {
            box: {
              left: rect.left,
              right: rect.right,
              top: rect.top,
              bottom: rect.bottom,
              width: rect.width,
              height: rect.height,
            },
            scrollWidth: element.scrollWidth,
            clientWidth: element.clientWidth,
            scrollHeight: element.scrollHeight,
            clientHeight: element.clientHeight,
          };
        }"""
    )
    label_box = fit_geometry.get("box")
    if (
        not isinstance(label_box, dict)
        or float(label_box.get("left", -1)) < 0
        or float(label_box.get("right", 1441)) > 1440
        or float(label_box.get("top", -1)) < 0
        or float(label_box.get("bottom", 901)) > 900
        or float(fit_geometry.get("scrollWidth", 1))
        > float(fit_geometry.get("clientWidth", 0)) + 1
        or float(fit_geometry.get("scrollHeight", 1))
        > float(fit_geometry.get("clientHeight", 0)) + 1
    ):
        raise RuntimeError(
            f"Fit exact toe source evidence is clipped at 1440x900: {fit_geometry}"
        )
    page.screenshot(path=fit_file)
    source.screenshot(path=fit_crop)
    dpr = page.evaluate("window.devicePixelRatio")
    browser_version = browser.version
    if failures:
        raise RuntimeError(f"toe-compensation browser state errors: {failures}")
    page.context.close()

    return {
        "browser": f"Chromium {browser_version}",
        "css_viewport": "1440x900",
        "device_pixel_ratio": dpr,
        "browser_zoom": "100%",
        "density": "standard",
        "exact_processing_output": pointer,
        "process_geometry_after_warning_recovery": process_geometry,
        "fit_exact_source_evidence_geometry": fit_geometry,
        "states": [
            {
                "file": _evidence_ref(warning_file, packet),
                "route": f"{base_url}/modeling?stage=process&family=metal",
                "interaction": (
                    "explicit add; select 0.0005..0.003; preview; warning visible; "
                    "acknowledgement clear; save disabled"
                ),
            },
            {
                "file": _evidence_ref(fit_file, packet),
                "crop": _evidence_ref(fit_crop, packet),
                "route": f"{base_url}/modeling?stage=fit&family=metal",
                "interaction": (
                    "recover 0..0.002; preview; save immutable Process output; open Fit; "
                    "preview; open Candidate parameters source evidence"
                ),
            },
        ],
    }


def _file_record(path: Path, packet: Path) -> dict[str, Any]:
    value = path.read_bytes()
    record: dict[str, Any] = {
        "path": _evidence_ref(path, packet),
        "sha256": hashlib.sha256(value).hexdigest(),
        "bytes": len(value),
    }
    if path.suffix.lower() == ".png":
        with Image.open(path) as image:
            record["pixels"] = f"{image.width}x{image.height}"
    return record


def _duplicate_groups(packet: Path) -> list[dict[str, Any]]:
    inventory_roots = (
        ROOT / "docs/00-research",
        ROOT / "docs/17-evidence/images",
        ROOT / "docs/user-guide/images",
    )
    by_digest: dict[str, list[Path]] = {}
    for inventory_root in inventory_roots:
        for path in inventory_root.rglob("*"):
            if path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg"}:
                by_digest.setdefault(hashlib.sha256(path.read_bytes()).hexdigest(), []).append(path)
    return [
        {
            "rationale": (
                "Issue #212 preserves this byte-identical exact-main/current image under an "
                "issue-owned lifecycle path so visual provenance remains independently auditable."
            ),
            "images": sorted(_evidence_ref(path, packet) for path in paths),
        }
        for paths in by_digest.values()
        if len(paths) > 1 and any(path.is_relative_to(packet) for path in paths)
    ]


def _write_manifest(
    packet: Path,
    *,
    base_url: str,
    current_report: dict[str, Any],
    states: dict[str, Any],
) -> None:
    files = sorted(
        path for path in packet.rglob("*") if path.is_file() and path.name != "visual-evidence.yaml"
    )
    manifest = {
        "issue": 212,
        "captured_at": datetime.now(UTC).isoformat(),
        "source_commit": _git("rev-parse", "HEAD"),
        "base_commit": BASE_SHA,
        "branch": _git("branch", "--show-current"),
        "base_url": base_url,
        "synthetic_non_production_only": True,
        "current_capture_command": (
            "uv run --with playwright==1.62.0 --with pillow python "
            "scripts/capture_issue212_visual_evidence.py"
        ),
        "viewports": [f"{width}x{height}" for width, height in VIEWPORTS],
        "density": "standard",
        "browser_zoom": "100%",
        "device_pixel_ratio": 1,
        "available_windows_displays": [
            "2560x1440@59Hz, 96 DPI, 100% scale",
            "2560x1600@165Hz, 96 DPI, 100% scale",
        ],
        "physical_4k_readability": "deferred_to_issue_223",
        "before": {
            "source": "accepted current-guide PNG blobs from the exact origin/main base",
            "note": "No missing state or changed baseline pixel was fabricated.",
        },
        "current_capture_report": current_report,
        "special_state_provenance": states,
        "allowed_duplicate_groups": _duplicate_groups(packet),
        "files": [_file_record(path, packet) for path in files],
    }
    (packet / "visual-evidence.yaml").write_text(
        yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:5173")
    args = parser.parse_args()

    if EVIDENCE.exists():
        raise RuntimeError(f"refusing to replace existing issue evidence: {EVIDENCE}")
    if _git("status", "--porcelain"):
        raise RuntimeError("issue evidence must start from a clean implementation commit")

    current_report = _refresh_current(args.base_url)
    EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".issue-212-evidence-", dir=EVIDENCE.parent))
    try:
        _extract_base_originals(staging)
        _copy_after_originals(staging)
        _crop_originals(staging, "before")
        _crop_originals(staging, "after")
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                states = _capture_states(browser, args.base_url, staging)
            finally:
                browser.close()
        _write_manifest(
            staging,
            base_url=args.base_url,
            current_report=current_report,
            states=states,
        )
        os.replace(staging, EVIDENCE)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise

    print(
        json.dumps(
            {
                "source_commit": _git("rev-parse", "HEAD"),
                "evidence": _project_ref(EVIDENCE),
                "files": sum(1 for path in EVIDENCE.rglob("*") if path.is_file()),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

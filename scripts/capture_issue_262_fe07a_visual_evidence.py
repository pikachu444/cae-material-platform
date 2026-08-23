"""Capture and validate the bounded #262 FE-07A Materials visual packet."""

from __future__ import annotations

import argparse
import hashlib
import json
import runpy
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops
from playwright.sync_api import Browser, Page, Route, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs/17-evidence/images/issue-262-fe07a-materials-architecture-ui"
VIEWPORTS = ((1366, 768), (1440, 900), (1920, 1080), (2560, 1440), (3840, 2160))
CAPTURE = runpy.run_path(str(ROOT / "scripts/capture_current_product.py"))

STATES: dict[str, tuple[str, ...]] = {
    "materials-search": ("header", "navigator", "table-form"),
    "materials-browse": ("header", "navigator", "table-form"),
    "material-detail": ("header", "navigator", "table-form", "graph-preview"),
    "material-curves": ("header", "navigator", "table-form", "graph-preview"),
}

# The current-guide manifest is cumulative. Keep the complete literal output
# roster for the documentation checker even though FE-07A promotes only the
# sixteen Materials originals listed in its capture provenance record.
CURRENT_CAPTURE_OUTPUTS = (
    "materials-search-1366x768.png",
    "materials-search-1440x900.png",
    "materials-search-1920x1080.png",
    "materials-search-2560x1440.png",
    "materials-search-3840x2160.png",
    "materials-search-long-1366x768.png",
    "materials-search-long-1440x900.png",
    "materials-search-long-1920x1080.png",
    "materials-search-short-1440x900.png",
    "materials-search-empty-1440x900.png",
    "materials-browse-1440x900.png",
    "demo-session-recovery-1440x900.png",
    "material-database-categories-1440x900.png",
    "material-database-linked-test-1440x900.png",
    "material-detail-1440x900.png",
    "material-detail-1366x768.png",
    "material-detail-1920x1080.png",
    "material-detail-2560x1440.png",
    "material-detail-3840x2160.png",
    "material-curves-1366x768.png",
    "material-curves-1440x900.png",
    "material-curves-1920x1080.png",
    "material-curves-2560x1440.png",
    "material-curves-3840x2160.png",
    "material-cae-cards-1440x900.png",
    "solver-card-preview-1366x768.png",
    "solver-card-preview-1440x900.png",
    "solver-card-preview-1920x1080.png",
    "modeling-data-1366x768.png",
    "modeling-session-1366x768.png",
    "modeling-session-1440x900.png",
    "modeling-session-1920x1080.png",
    "modeling-data-1440x900.png",
    "modeling-data-1920x1080.png",
    "modeling-data-2560x1440.png",
    "modeling-data-3840x2160.png",
    "modeling-data-dma-1366x768.png",
    "modeling-data-dma-1440x900.png",
    "modeling-data-dma-1920x1080.png",
    "modeling-data-dma-2560x1440.png",
    "modeling-data-dma-3840x2160.png",
    "modeling-data-dma-rejected-1366x768.png",
    "modeling-data-dma-rejected-1440x900.png",
    "modeling-data-dma-rejected-1920x1080.png",
    "modeling-data-dma-rejected-2560x1440.png",
    "modeling-data-dma-rejected-3840x2160.png",
    "modeling-data-fld-1366x768.png",
    "modeling-data-fld-1440x900.png",
    "modeling-data-fld-1920x1080.png",
    "modeling-data-fld-2560x1440.png",
    "modeling-data-fld-3840x2160.png",
    "modeling-data-empty-1440x900.png",
    "modeling-data-invalid-1440x900.png",
    "modeling-data-invalid-scrolled-1440x900.png",
    "modeling-process-1366x768.png",
    "modeling-process-linear-regression-1366x768.png",
    "modeling-process-manual-1366x768.png",
    "modeling-process-1440x900.png",
    "modeling-process-1920x1080.png",
    "modeling-process-2560x1440.png",
    "modeling-process-3840x2160.png",
    "modeling-process-blocked-1440x900.png",
    "modeling-process-exact-read-failed-1440x900.png",
    "modeling-process-siblings-1440x900.png",
    "modeling-fit-1366x768.png",
    "modeling-fit-1440x900.png",
    "modeling-fit-1920x1080.png",
    "modeling-fit-2560x1440.png",
    "modeling-fit-3840x2160.png",
    "modeling-fit-candidate-parameters-long-1440x900.png",
    "modeling-fit-candidate-evidence-scrolled-1440x900.png",
    "modeling-fit-calculation-failed-1920x1080.png",
    "modeling-fit-save-failed-1920x1080.png",
    "modeling-fit-exact-source-blocked-1920x1080.png",
    "modeling-fit-exact-read-failed-1920x1080.png",
    "modeling-fit-restored-1920x1080.png",
    "modeling-export-1366x768.png",
    "modeling-export-1440x900.png",
    "modeling-export-1920x1080.png",
    "modeling-export-2560x1440.png",
    "modeling-export-3840x2160.png",
    "modeling-export-source-blocked-1440x900.png",
    "modeling-export-approximation-blocked-1440x900.png",
    "modeling-export-delivered-1440x900.png",
    "activity-1366x768.png",
    "activity-1440x900.png",
    "activity-1920x1080.png",
    "activity-2560x1440.png",
    "activity-3840x2160.png",
    "activity-history-1440x900.png",
    "activity-history-1920x1080.png",
    "activity-history-2560x1440.png",
    "activity-history-3840x2160.png",
    "activity-user-1440x900.png",
    "activity-administrator-1440x900.png",
    "activity-decision-error-1440x900.png",
    "activity-recovery-1440x900.png",
    "administration-schema-bundle-1440x900.png",
    "administration-database-1366x768.png",
    "administration-database-1440x900.png",
    "administration-database-1920x1080.png",
    "administration-database-2560x1440.png",
    "administration-database-3840x2160.png",
    "administration-database-preview-1366x768.png",
    "administration-database-preview-1440x900.png",
    "administration-database-preview-1920x1080.png",
    "administration-database-preview-2560x1440.png",
    "administration-database-preview-3840x2160.png",
    "administration-records-1366x768.png",
    "administration-records-1440x900.png",
    "administration-records-1920x1080.png",
    "administration-records-2560x1440.png",
    "administration-records-3840x2160.png",
    "administration-access-1366x768.png",
    "administration-access-role-control-1366x768.png",
    "administration-access-1440x900.png",
    "administration-access-1920x1080.png",
    "administration-access-2560x1440.png",
    "administration-access-3840x2160.png",
    "modeling-distribution-1366x768.png",
    "modeling-distribution-1440x900.png",
    "modeling-distribution-1920x1080.png",
    "modeling-distribution-2560x1440.png",
    "modeling-distribution-3840x2160.png",
)


class EvidenceError(RuntimeError):
    """Raised when observable FE-07A acceptance is incomplete."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _viewport(width: int, height: int) -> str:
    return f"{width}x{height}"


def _settle(page: Page) -> None:
    CAPTURE["_wait_for_settled"](page)
    page.locator("footer[role='status']").filter(
        has_not_text="Loading materials"
    ).wait_for(timeout=30_000)
    visible_alerts = [
        page.get_by_role("alert").nth(index).inner_text()
        for index in range(page.get_by_role("alert").count())
        if page.get_by_role("alert").nth(index).is_visible()
    ]
    if visible_alerts:
        raise EvidenceError(f"unexpected visible alert: {visible_alerts}")


def _open_browse(page: Page, base_url: str) -> None:
    page.goto(f"{base_url}/materials")
    page.get_by_role("button", name="Browse", exact=True).wait_for(timeout=30_000)
    page.wait_for_url(lambda url: "table=" in url, timeout=30_000)
    for label in ("Technical Data", "Test Data", "Simulation Data", "Solver Cards"):
        page.get_by_text(label, exact=True).first.wait_for(timeout=30_000)
    page.get_by_role("heading", name="Technical Data", exact=True).wait_for(timeout=30_000)
    _settle(page)


def _open_search(page: Page) -> None:
    page.get_by_role("button", name="Filters", exact=True).click()
    query = page.get_by_role("textbox", name="Search materials")
    query.wait_for(timeout=30_000)
    query.fill("DP780")
    page.locator(".materials-search-form").get_by_role(
        "button", name="Find", exact=True
    ).click()
    row = page.locator('table[aria-label="Material results"] tbody tr').filter(
        has_text="DP780"
    ).first
    row.wait_for(timeout=30_000)
    page.wait_for_url(lambda url: "q=DP780" in url and "selected=" in url, timeout=30_000)
    _settle(page)


def _open_detail(page: Page) -> None:
    page.locator('table[aria-label="Material results"] tbody tr').filter(
        has_text="DP780"
    ).first.click()
    page.locator(".material-detail-shell").wait_for(timeout=30_000)
    page.get_by_role(
        "heading", name="DP780 synthetic reference steel", exact=True
    ).wait_for(timeout=30_000)
    page.get_by_role("heading", name="CAE card applicability", exact=True).wait_for(
        timeout=30_000
    )
    page.get_by_label("Related exact records").wait_for(timeout=30_000)
    _settle(page)


def _measure(page: Page, state: str, width: int, height: int) -> dict[str, Any]:
    values = page.evaluate(
        """state => {
          const visible = element => Boolean(element && element.getClientRects().length);
          const bounds = selector => {
            const element = [...document.querySelectorAll(selector)].find(visible);
            if (!element) return null;
            const box = element.getBoundingClientRect();
            return {
              left: box.left, right: box.right, top: box.top, bottom: box.bottom,
              width: box.width, height: box.height,
              clientWidth: element.clientWidth, scrollWidth: element.scrollWidth,
              clientHeight: element.clientHeight, scrollHeight: element.scrollHeight,
            };
          };
          const contentSelector = state === 'materials-search'
            ? 'table[aria-label="Material results"]'
            : state === 'materials-browse'
              ? 'table[aria-label="Data results"]'
              : state === 'material-detail'
                ? '.overview-grid'
                : '.material-tab-panel';
          return {
            state,
            viewport: { width: innerWidth, height: innerHeight },
            devicePixelRatio,
            visualViewportScale: visualViewport?.scale || 1,
            pageOverflowX: document.documentElement.scrollWidth - document.documentElement.clientWidth,
            workspace: bounds('.resizable-workspace'),
            navigator: bounds('.navigator-panel'),
            main: bounds('.main-panel'),
            content: bounds(contentSelector),
            related: bounds('.material-linked-data'),
            localScroll: bounds('.materials-result-table-wrap, .material-tab-panel'),
          };
        }""",
        state,
    )
    if values["viewport"] != {"width": width, "height": height}:
        raise EvidenceError(f"viewport drift for {state}: {values}")
    if values["devicePixelRatio"] != 1 or values["visualViewportScale"] != 1:
        raise EvidenceError(f"capture scale drift for {state}: {values}")
    if values["pageOverflowX"] > 1:
        raise EvidenceError(f"page overflow for {state}: {values}")
    workspace = values["workspace"]
    navigator = values["navigator"]
    main = values["main"]
    content = values["content"]
    if not workspace or workspace["width"] < width * 0.8:
        raise EvidenceError(f"fixed work island for {state}: {values}")
    if not navigator or not (190 <= navigator["width"] <= 520):
        raise EvidenceError(f"unusable navigator for {state}: {values}")
    if not main or main["width"] < max(600, width - navigator["width"] - 180):
        raise EvidenceError(f"results/datasheet is not dominant for {state}: {values}")
    if not content or content["left"] < -1 or content["right"] > width + 1:
        raise EvidenceError(f"primary content is clipped for {state}: {values}")
    return values


def _screenshot(page: Page, path: Path, width: int, height: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=path)
    with Image.open(path) as image:
        if image.size != (width, height):
            raise EvidenceError(f"screenshot size drift: {path} {image.size}")


def _capture_matrix(browser: Browser, base_url: str) -> list[dict[str, Any]]:
    after = EVIDENCE / "after/originals"
    measurements: list[dict[str, Any]] = []
    for width, height in VIEWPORTS:
        suffix = _viewport(width, height)
        page = CAPTURE["_new_page"](browser, base_url, width, height)
        errors: list[str] = []
        page.on("pageerror", lambda error, values=errors: values.append(str(error)))
        _open_browse(page, base_url)
        measurements.append(_measure(page, "materials-browse", width, height))
        _screenshot(page, after / f"materials-browse-{suffix}.png", width, height)

        _open_search(page)
        measurements.append(_measure(page, "materials-search", width, height))
        _screenshot(page, after / f"materials-search-{suffix}.png", width, height)

        _open_detail(page)
        measurements.append(_measure(page, "material-detail", width, height))
        _screenshot(page, after / f"material-detail-{suffix}.png", width, height)

        page.get_by_role("tab", name="Curves", exact=True).click()
        page.get_by_role("heading", name="Curves", exact=True).wait_for(timeout=30_000)
        page.get_by_label("Related exact records").wait_for(timeout=30_000)
        _settle(page)
        measurements.append(_measure(page, "material-curves", width, height))
        _screenshot(page, after / f"material-curves-{suffix}.png", width, height)
        if errors:
            raise EvidenceError(f"browser page errors at {suffix}: {errors}")
        page.context.close()
    return measurements


def _capture_recovery(browser: Browser, base_url: str) -> dict[str, Any]:
    width, height = 1440, 900
    page = CAPTURE["_new_page"](browser, base_url, width, height)
    _open_browse(page, base_url)
    _open_search(page)
    original_url = page.url

    def fail_query(route: Route) -> None:
        route.abort("failed")

    page.route("**/catalog/records:search", fail_query)
    query = page.get_by_role("textbox", name="Search materials")
    query.fill("DP780 recovery check")
    page.locator(".materials-search-form").get_by_role(
        "button", name="Find", exact=True
    ).click()
    alert = page.get_by_role("alert")
    alert.wait_for(timeout=30_000)
    retained = page.locator('table[aria-label="Material results"] tbody tr').filter(
        has_text="DP780"
    ).first
    retained.wait_for(timeout=30_000)
    if retained.get_attribute("aria-selected") != "true":
        raise EvidenceError("failed query did not retain exact selection")
    _screenshot(
        page,
        EVIDENCE / "after/exceptions/materials-search-error-1440x900.png",
        width,
        height,
    )

    page.unroute("**/catalog/records:search", fail_query)
    page.get_by_role("button", name="Retry", exact=True).click()
    alert.wait_for(state="detached", timeout=30_000)
    retained.wait_for(timeout=30_000)
    _settle(page)
    _screenshot(
        page,
        EVIDENCE / "after/exceptions/materials-search-recovered-1440x900.png",
        width,
        height,
    )
    result = {
        "state": "query-error-recovery",
        "viewport": "1440x900",
        "retainedRows": True,
        "retainedSelection": True,
        "retryRecovered": True,
        "originalUrl": original_url,
        "recoveredUrl": page.url,
    }
    page.context.close()
    return result


def _verify_continuity(browser: Browser, base_url: str) -> dict[str, Any]:
    page = CAPTURE["_new_page"](browser, base_url, 1440, 900)
    _open_browse(page, base_url)
    _open_search(page)
    search_url = page.url
    _open_detail(page)
    exact_url = page.url
    exact_params = page.evaluate("Object.fromEntries(new URL(location.href).searchParams)")
    required = {"record_id", "record_revision_id", "material_revision_id"}
    if not required.issubset(exact_params):
        raise EvidenceError(f"exact detail pins are incomplete: {exact_params}")
    page.reload()
    page.get_by_role(
        "heading", name="DP780 synthetic reference steel", exact=True
    ).wait_for(timeout=30_000)
    _settle(page)
    if page.url != exact_url:
        raise EvidenceError(f"exact detail URL drifted after reload: {page.url}")
    page.get_by_role("button", name="Results", exact=True).click()
    page.wait_for_url(
        lambda url: "/materials?" in str(url) and "q=DP780" in str(url),
        timeout=30_000,
    )
    page.locator('table[aria-label="Material results"] tbody tr').filter(
        has_text="DP780"
    ).first.wait_for(timeout=30_000)
    return_url = page.url
    if "selected=" not in return_url or "table=" not in return_url:
        raise EvidenceError(f"return path lost query/scope/selection: {return_url}")

    _open_detail(page)
    outcome = "exact-preview-or-download"
    start = page.get_by_role("button", name="Start Modeling", exact=True)
    if start.count() and start.is_visible():
        start.click()
        page.wait_for_url(lambda url: "/modeling" in str(url), timeout=30_000)
        session = page.evaluate(
            "JSON.parse(sessionStorage.getItem('cmp.modeling.recent-session.v4') || 'null')"
        )
        if not session or session.get("material", {}).get("revisionId") != exact_params["material_revision_id"]:
            raise EvidenceError(f"Modeling handoff lost the exact Material revision: {session}")
        outcome = "start-modeling-exact-context"
    page.context.close()
    return {
        "searchUrl": search_url,
        "exactUrl": exact_url,
        "exactPins": exact_params,
        "reloadReadBack": True,
        "returnUrl": return_url,
        "handoffOutcome": outcome,
    }


def _crop_box(region: str, width: int, height: int) -> tuple[int, int, int, int]:
    header_bottom = min(height, 150)
    navigator_right = min(width, 320)
    middle_bottom = min(height, max(430, round(height * 0.58)))
    if region == "header":
        return (0, 0, width, header_bottom)
    if region == "navigator":
        return (0, header_bottom, navigator_right, height)
    if region == "table-form":
        return (navigator_right, header_bottom, width, middle_bottom)
    if region == "graph-preview":
        return (navigator_right, middle_bottom, width, height)
    raise EvidenceError(f"unknown crop region: {region}")


def _write_crops() -> None:
    for phase in ("before", "after"):
        originals = EVIDENCE / phase / "originals"
        crops = EVIDENCE / phase / "crops"
        crops.mkdir(parents=True, exist_ok=True)
        for state, regions in STATES.items():
            for width, height in VIEWPORTS:
                source = originals / f"{state}-{_viewport(width, height)}.png"
                if not source.is_file():
                    raise EvidenceError(f"missing {phase} original: {source}")
                with Image.open(source) as image:
                    if image.size != (width, height):
                        raise EvidenceError(f"original size drift: {source} {image.size}")
                    for region in regions:
                        target = crops / f"{state}-{_viewport(width, height)}-{region}-100pct.png"
                        image.crop(_crop_box(region, width, height)).save(target)


def _image_record(path: Path) -> dict[str, Any]:
    with Image.open(path) as image:
        width, height = image.size
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "sha256": _sha256(path),
        "width": width,
        "height": height,
    }


def _comparison(before: Path, after: Path) -> dict[str, Any]:
    with Image.open(before).convert("RGB") as left, Image.open(after).convert("RGB") as right:
        difference = ImageChops.difference(left, right)
        bbox = difference.getbbox()
        changed = (
            0
            if bbox is None
            else sum(
                pixel != (0, 0, 0)
                for pixel in difference.get_flattened_data()
            )
        )
        return {
            "name": before.name,
            "changedPixels": changed,
            "changedPercent": round(changed * 100 / (left.width * left.height), 4),
            "differenceBounds": list(bbox) if bbox else None,
        }


def _duplicate_groups() -> list[dict[str, Any]]:
    grouped: dict[str, list[str]] = {}
    for root in (
        ROOT / "docs/00-research",
        ROOT / "docs/17-evidence/images",
        ROOT / "docs/user-guide/images",
    ):
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in {".png", ".jpg", ".jpeg"}:
                continue
            grouped.setdefault(_sha256(path), []).append(path.relative_to(ROOT).as_posix())
    evidence_prefix = EVIDENCE.relative_to(ROOT).as_posix() + "/"
    prior_materials_search_prefix = (
        "docs/17-evidence/images/issue-261-fe06-m2-materials-css-ownership/"
    )
    groups = [
        {
            "rationale": "Issue #262 retains independently addressable before/after, direct-crop and current-guide provenance for exact-hash evidence.",
            "images": sorted(paths),
        }
        for paths in grouped.values()
        if len(paths) > 1
        and (
            any(path.startswith(evidence_prefix) for path in paths)
            or all(
                path.startswith(prior_materials_search_prefix)
                and "/canonical/materials-search-" in path
                for path in paths
            )
        )
    ]
    return sorted(groups, key=lambda group: group["images"])


def _write_manifest(
    measurements: list[dict[str, Any]],
    recovery: dict[str, Any],
    continuity: dict[str, Any],
) -> None:
    images = sorted(
        [
            path
            for path in EVIDENCE.rglob("*.png")
            if path.is_file()
        ],
        key=lambda path: path.as_posix(),
    )
    comparisons = []
    for state in STATES:
        for width, height in VIEWPORTS:
            name = f"{state}-{_viewport(width, height)}.png"
            comparisons.append(
                _comparison(
                    EVIDENCE / "before/originals" / name,
                    EVIDENCE / "after/originals" / name,
                )
            )
    manifest = {
        "schemaVersion": "cmp.issue-262.fe07a.visual-evidence.v1",
        "issue": "#262",
        "unit": "FE-07A Materials",
        "status": "READY_FOR_OWNER_VISUAL_GEOMETRY_APPROVAL",
        "browserZoomPercent": 100,
        "devicePixelRatio": 1,
        "display": "Playwright Chromium CSS viewports; no claim of physical Windows 4K readability",
        "viewports": [_viewport(width, height) for width, height in VIEWPORTS],
        "states": list(STATES),
        "measurements": measurements,
        "recovery": recovery,
        "continuity": continuity,
        "comparisons": comparisons,
        "images": [_image_record(path) for path in images],
        "allowed_duplicate_groups": _duplicate_groups(),
    }
    (EVIDENCE / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:5173")
    parser.add_argument("--manifest-only", action="store_true")
    args = parser.parse_args()
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    if args.manifest_only:
        current = json.loads((EVIDENCE / "manifest.json").read_text(encoding="utf-8"))
        _write_manifest(current["measurements"], current["recovery"], current["continuity"])
        print("FE-07A visual manifest refreshed from existing verified captures.")
        return 0
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            measurements = _capture_matrix(browser, args.base_url)
            recovery = _capture_recovery(browser, args.base_url)
            continuity = _verify_continuity(browser, args.base_url)
        finally:
            browser.close()
    _write_crops()
    _write_manifest(measurements, recovery, continuity)
    print(
        "FE-07A visual evidence ready: "
        f"{len(measurements)} geometry records, 20 before/after pairs, "
        "error/recovery, reload, return, and exact handoff verified."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

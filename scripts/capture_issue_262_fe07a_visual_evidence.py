"""Capture and validate the bounded #262 FE-07A Materials visual packet."""

from __future__ import annotations

import argparse
import hashlib
import json
import runpy
import shutil
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops
from playwright.sync_api import Browser, Page, Route, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs/17-evidence/images/issue-262-fe07a-materials-architecture-ui"
CORRECTION = EVIDENCE / "owner-correction"
CONSISTENCY = CORRECTION / "consistency-correction"
VIEWPORTS = ((1366, 768), (1440, 900), (1920, 1080), (2560, 1440), (3840, 2160))
CAPTURE = runpy.run_path(str(ROOT / "scripts/capture_current_product.py"))

STATES: dict[str, tuple[str, ...]] = {
    "materials-search": ("header", "navigator", "table-form"),
    "materials-browse": ("header", "navigator", "table-form"),
    "material-detail": ("header", "navigator", "table-form", "graph-preview"),
    "material-curves": ("header", "navigator", "table-form", "graph-preview"),
}

OWNER_REPORT_STATES = (
    ("Search", "materials-search-1920x1080.png"),
    ("Browse", "materials-browse-1920x1080.png"),
    ("Detail Overview", "material-detail-1920x1080.png"),
    ("Curves", "material-curves-1920x1080.png"),
    ("Source & history", "material-source-history-1920x1080.png"),
)

CONSISTENCY_STATES: dict[str, tuple[str, ...]] = {
    "material-curves": ("header", "navigator", "table-form", "graph-preview"),
    "material-source-history": ("header", "navigator", "table-form"),
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
    # React can schedule the exact-link explorer request immediately after the
    # first idle frame. Require a short stable idle window before measuring or
    # capturing so a transient pre-request frame cannot pass the evidence gate.
    for _ in range(2):
        CAPTURE["_wait_for_settled"](page)
        page.wait_for_timeout(250)
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
    page.get_by_role("heading", name="Available solver cards", exact=True).wait_for(
        timeout=30_000
    )
    page.get_by_label("Related data").wait_for(timeout=30_000)
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
            pageOverflowX:
              document.documentElement.scrollWidth -
              document.documentElement.clientWidth,
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
    after = CORRECTION / "after/originals"
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
        page.get_by_label("Related data").wait_for(timeout=30_000)
        _settle(page)
        measurements.append(_measure(page, "material-curves", width, height))
        _screenshot(page, after / f"material-curves-{suffix}.png", width, height)
        if errors:
            raise EvidenceError(f"browser page errors at {suffix}: {errors}")
        page.context.close()
    return measurements


def _capture_owner_report(browser: Browser, base_url: str) -> dict[str, Any]:
    width, height = 1920, 1080
    after = CORRECTION / "after/originals"
    page = CAPTURE["_new_page"](browser, base_url, width, height)
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))

    _open_browse(page, base_url)
    _screenshot(page, after / "materials-browse-1920x1080.png", width, height)

    _open_search(page)
    _screenshot(page, after / "materials-search-1920x1080.png", width, height)

    _open_detail(page)
    page.get_by_role("tab", name="Overview", exact=True).wait_for(timeout=30_000)
    _screenshot(page, after / "material-detail-1920x1080.png", width, height)

    page.get_by_role("tab", name="Curves", exact=True).click()
    page.get_by_role("heading", name="Curves", exact=True).wait_for(timeout=30_000)
    _settle(page)
    _screenshot(page, after / "material-curves-1920x1080.png", width, height)

    source_history = page.get_by_role("tab", name="Source & history", exact=True)
    source_history.click()
    page.wait_for_url(lambda url: "/evidence" in url, timeout=30_000)
    page.get_by_role(
        "heading", name="Related records and workflow", exact=True
    ).wait_for(timeout=30_000)
    _settle(page)
    if source_history.get_attribute("aria-selected") != "true":
        raise EvidenceError("Source & history is not the active tab")
    source_measurement = _measure(page, "material-source-history", width, height)
    _screenshot(
        page,
        after / "material-source-history-1920x1080.png",
        width,
        height,
    )
    if errors:
        raise EvidenceError(f"browser page errors in owner report: {errors}")
    result = {
        "viewport": "1920x1080",
        "browserZoomPercent": 100,
        "devicePixelRatio": 1,
        "sourceHistoryActive": True,
        "sourceHistoryInternalRouteKey": "evidence",
        "sourceHistoryUrl": page.url,
        "sourceHistoryMeasurement": source_measurement,
    }
    page.context.close()
    return result


def _capture_consistency_matrix(
    browser: Browser,
    base_url: str,
    phase: str,
) -> list[dict[str, Any]]:
    target = CONSISTENCY / phase / "originals"
    measurements: list[dict[str, Any]] = []
    expected_curve_summary = "Evidence" if phase == "before" else "Curve source"
    expected_source_heading = (
        "Lineage and evidence"
        if phase == "before"
        else "Related records and workflow"
    )
    helper = (
        "Follow related records and the exact material workflow; open technical "
        "identifiers only when needed."
    )
    for width, height in VIEWPORTS:
        suffix = _viewport(width, height)
        page = CAPTURE["_new_page"](browser, base_url, width, height)
        errors: list[str] = []
        page.on("pageerror", lambda error, values=errors: values.append(str(error)))
        _open_browse(page, base_url)
        _open_search(page)
        _open_detail(page)

        page.get_by_role("tab", name="Curves", exact=True).click()
        page.get_by_role("heading", name="Curves", exact=True).wait_for(timeout=30_000)
        _settle(page)
        summaries = page.locator("details.curve-evidence > summary")
        summaries.first.wait_for(timeout=30_000)
        summary_texts = [text.strip() for text in summaries.all_inner_texts()]
        if not summary_texts or set(summary_texts) != {expected_curve_summary}:
            raise EvidenceError(
                f"curve source summary drifted in {phase}: {summary_texts}"
            )
        measurements.append(_measure(page, "material-curves", width, height))
        _screenshot(page, target / f"material-curves-{suffix}.png", width, height)

        source_history = page.get_by_role("tab", name="Source & history", exact=True)
        source_history.click()
        page.wait_for_url(lambda url: "/evidence" in url, timeout=30_000)
        page.get_by_role(
            "heading", name=expected_source_heading, exact=True
        ).wait_for(timeout=30_000)
        _settle(page)
        if source_history.get_attribute("aria-selected") != "true":
            raise EvidenceError(f"Source & history is not active in {phase}")
        helper_count = page.get_by_text(helper, exact=True).count()
        if (phase == "before" and helper_count != 1) or (
            phase == "after" and helper_count != 0
        ):
            raise EvidenceError(
                f"Source & history helper-copy state drifted in {phase}: {helper_count}"
            )
        measurements.append(
            _measure(page, "material-source-history", width, height)
        )
        _screenshot(
            page,
            target / f"material-source-history-{suffix}.png",
            width,
            height,
        )
        if errors:
            raise EvidenceError(
                f"browser page errors in {phase} consistency capture at {suffix}: {errors}"
            )
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
        CORRECTION / "after/exceptions/materials-search-error-1440x900.png",
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
        CORRECTION / "after/exceptions/materials-search-recovered-1440x900.png",
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
    result_table = page.locator('table[aria-label="Material results"]')
    headers = [
        result_table.locator("thead th").nth(index).inner_text().strip()
        for index in range(result_table.locator("thead th").count())
    ]
    if headers[:5] != ["Compare", "Material", "Code", "Family", "Description"]:
        raise EvidenceError(f"search result semantics drifted: {headers}")
    code_header = result_table.locator("thead th").nth(2)
    if code_header.locator("button").count() or code_header.get_attribute("aria-sort"):
        raise EvidenceError("Code sorting was added without a server sort contract")
    row = result_table.locator("tbody tr").filter(has_text="DP780").first
    cells = [row.locator("td").nth(index).inner_text().strip() for index in range(5)]
    if cells[1] != "DP780 synthetic reference steel" or cells[2] != "CMP-DEMO-DP780":
        raise EvidenceError(f"Material and Code columns are not exact: {cells}")
    if "not validated for engineering use" in result_table.inner_text().lower():
        raise EvidenceError("demo provenance warning remains in normal Search results")

    query = page.get_by_role("textbox", name="Search materials")
    query.fill("CMP-DEMO-DP780")
    page.locator(".materials-search-form").get_by_role(
        "button", name="Find", exact=True
    ).click()
    row = result_table.locator("tbody tr").filter(has_text="CMP-DEMO-DP780").first
    row.wait_for(timeout=30_000)
    page.wait_for_url(lambda url: "q=CMP-DEMO-DP780" in str(url), timeout=30_000)
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
    if page.get_by_role("tab", name="Source & history", exact=True).count() != 1:
        raise EvidenceError("Source & history tab label is missing")
    if page.get_by_role("tab", name="Evidence", exact=True).count():
        raise EvidenceError("legacy Evidence tab label remains visible")
    if "not validated for engineering use" in page.locator(
        ".material-detail-header"
    ).inner_text().lower():
        raise EvidenceError("demo provenance warning remains in Material Detail header")
    property_text = page.locator(".overview-property-list").inner_text()
    condition_text = page.locator(".condition-summary").inner_text()
    for required_label in (
        "Density",
        "Young’s modulus",  # noqa: RUF001 - exact user-facing label
        "Yield strength",
        "Poisson ratio",
    ):
        if required_label not in property_text:
            raise EvidenceError(f"missing key property label {required_label!r}")
    for required_label in (
        "Temperature",
        "Strain rate",
        "State",
        "Manufacturing route",
    ):
        if required_label not in condition_text:
            raise EvidenceError(f"missing applicability label {required_label!r}")
    condition_width = page.locator(".condition-summary").evaluate(
        "element => element.getBoundingClientRect().width"
    )
    if condition_width > 560:
        raise EvidenceError(f"condition form exceeds readable bound: {condition_width}")

    material_related = page.get_by_label("Related data")
    material_groups = [
        material_related.locator(".related-record-group h3").nth(index).inner_text().strip()
        for index in range(material_related.locator(".related-record-group h3").count())
    ]
    if material_groups != ["Test Data 6"]:
        raise EvidenceError(f"unexpected direct Material links: {material_groups}")
    direct_test = material_related.locator(".related-record-list button").filter(
        has_text="23 °C · 0.0067"
    ).first
    direct_test.click()
    page.get_by_role(
        "heading",
        name="DP780 tensile · 23 °C · 0.0067 s⁻¹ · synthetic reference",
        exact=True,
    ).wait_for(timeout=30_000)
    _settle(page)
    test_url = page.url
    test_text = page.locator(".exact-record-datasheet").inner_text()
    for required_text in (
        "Type Test Data",
        "Data type",
        "Tensile",
        "Test conditions",
        "23 °C; 0.0067 s⁻¹",
        "Engineering strain: 0 to 0.14 1",
        "Engineering stress: 0 to 775000000 Pa",
    ):
        if required_text not in test_text:
            raise EvidenceError(f"exact Test Data is missing {required_text!r}")
    direct_test_modeling_available = bool(
        page.get_by_role("button", name="Open in Modeling", exact=True).count()
    )
    simulation = page.locator(".exact-record-datasheet .related-record-list button").filter(
        has_text="selected Voce"
    ).first
    if "Processing Output" not in simulation.inner_text():
        raise EvidenceError("Simulation Data does not show its Processing Output subtype")
    simulation.click()
    page.get_by_role(
        "heading",
        name="DP780 elastoplasticity · selected Voce result · synthetic reference",
        exact=True,
    ).wait_for(timeout=30_000)
    _settle(page)
    simulation_url = page.url
    simulation_text = page.locator(".exact-record-datasheet").inner_text()
    for required_text in (
        "Type Processing Output",
        "23 °C room-temperature tensile input",
        "CMP-246-TENSILE-ROOM",
    ):
        if required_text not in simulation_text:
            raise EvidenceError(f"Processing Output is missing {required_text!r}")
    page.go_back()
    page.get_by_role(
        "heading",
        name="DP780 tensile · 23 °C · 0.0067 s⁻¹ · synthetic reference",
        exact=True,
    ).wait_for(timeout=30_000)
    if page.url != test_url:
        raise EvidenceError("Back did not restore the exact Test Data revision")
    page.go_forward()
    page.get_by_role(
        "heading",
        name="DP780 elastoplasticity · selected Voce result · synthetic reference",
        exact=True,
    ).wait_for(timeout=30_000)
    if page.url != simulation_url:
        raise EvidenceError("Forward did not restore the exact Processing Output revision")
    page.reload()
    page.get_by_role(
        "heading",
        name="DP780 elastoplasticity · selected Voce result · synthetic reference",
        exact=True,
    ).wait_for(timeout=30_000)
    _settle(page)
    page.go_back()
    page.get_by_role(
        "heading",
        name="DP780 tensile · 23 °C · 0.0067 s⁻¹ · synthetic reference",
        exact=True,
    ).wait_for(timeout=30_000)
    page.go_back()
    page.get_by_role(
        "heading", name="DP780 synthetic reference steel", exact=True
    ).wait_for(timeout=30_000)
    _settle(page)
    if page.url != exact_url:
        raise EvidenceError(f"Material context drifted after exact direct hops: {page.url}")

    page.get_by_role("tab", name="Curves", exact=True).click()
    page.get_by_role("heading", name="Curves", exact=True).wait_for(timeout=30_000)
    _settle(page)
    curves_modeling_available = bool(
        page.get_by_role("button", name="Open in Modeling", exact=True).count()
    )
    if "View only" not in page.locator(".material-tab-panel").inner_text():
        raise EvidenceError("unqualified configured curves are not visibly view-only")

    start = page.get_by_role("button", name="Start Modeling", exact=True)
    start.click()
    page.wait_for_url(lambda url: "/modeling" in str(url), timeout=30_000)
    page.get_by_role("heading", name="Select Test Data", exact=True).wait_for(
        timeout=30_000
    )
    session = page.evaluate(
        "JSON.parse(sessionStorage.getItem('cmp.modeling.recent-session.v4') || 'null')"
    )
    modeling_params = page.evaluate(
        "Object.fromEntries(new URL(location.href).searchParams)"
    )
    if (
        not session
        or session.get("material", {}).get("revisionId")
        != exact_params["material_revision_id"]
        or not session.get("materialState", {}).get("revisionId")
        or session.get("contextSelectionRequired") is not False
    ):
        raise EvidenceError(f"Modeling handoff lost exact known context: {session}")
    expected_modeling_params = {
        "stage": "data",
        "family": "metal",
        "material_id": session["material"]["id"],
        "material_revision_id": session["material"]["revisionId"],
        "material_state_id": session["materialState"]["id"],
        "material_state_revision_id": session["materialState"]["revisionId"],
    }
    if modeling_params != expected_modeling_params:
        raise EvidenceError(
            "Modeling URL did not pin the exact known Material and State context: "
            f"{modeling_params}"
        )
    modeling_url = page.url
    page.reload()
    page.get_by_role("heading", name="Select Test Data", exact=True).wait_for(
        timeout=30_000
    )
    restored_session = page.evaluate(
        "JSON.parse(sessionStorage.getItem('cmp.modeling.recent-session.v4') || 'null')"
    )
    if (
        not restored_session
        or restored_session.get("material", {}).get("id")
        != session["material"]["id"]
        or restored_session.get("material", {}).get("revisionId")
        != session["material"]["revisionId"]
        or restored_session.get("materialState", {}).get("id")
        != session["materialState"]["id"]
        or restored_session.get("materialState", {}).get("revisionId")
        != session["materialState"]["revisionId"]
        or restored_session.get("contextSelectionRequired") is not False
        or page.url != modeling_url
    ):
        raise EvidenceError(
            "Modeling reload did not preserve exact Material and State context: "
            f"{restored_session}"
        )
    page.go_back()
    page.get_by_role("heading", name="Curves", exact=True).wait_for(timeout=30_000)
    page.get_by_role("tab", name="Overview", exact=True).click()
    page.get_by_role("heading", name="Available solver cards", exact=True).wait_for(
        timeout=30_000
    )
    _settle(page)

    page.get_by_role("treeitem", name="Solver Cards", exact=True).click()
    solver_record = page.get_by_role(
        "treeitem",
        name="DP780 Abaqus native material card · synthetic reference",
        exact=True,
    )
    solver_record.wait_for(timeout=30_000)
    solver_record.dblclick()
    page.get_by_role("heading", name="Solver card delivery", exact=True).wait_for(
        timeout=30_000
    )
    page.get_by_text("Abaqus 2025", exact=True).wait_for(timeout=30_000)
    _settle(page)
    solver_url = page.url
    solver_text = page.locator(".exact-solver-card-delivery").inner_text()
    for required_text in (
        "Native ASCII .inp",
        "kg · m · s",
        "Release state",
        "Review required",
        "Exact source evidence",
    ):
        if required_text not in solver_text:
            raise EvidenceError(f"Solver Card detail is missing {required_text!r}")
    download = page.get_by_role("button", name="Download .inp", exact=True)
    if not download.is_disabled():
        raise EvidenceError(
            "review-required Solver Card download is enabled before acknowledgement"
        )
    page.get_by_role("button", name="Preview .inp", exact=True).click()
    page.locator(".native-card-preview").wait_for(timeout=30_000)
    if "*MATERIAL" not in page.locator(".native-card-preview").inner_text():
        raise EvidenceError("exact Solver Card native preview did not load")
    acknowledgement = page.get_by_role("checkbox")
    acknowledgement.check()
    if download.is_disabled():
        raise EvidenceError("reviewed Solver Card download did not become available")
    page.reload()
    page.get_by_role("heading", name="Solver card delivery", exact=True).wait_for(
        timeout=30_000
    )
    page.get_by_text("Abaqus 2025", exact=True).wait_for(timeout=30_000)
    _settle(page)
    if page.url != solver_url:
        raise EvidenceError("Solver Card exact URL drifted after reload")
    page.go_back()
    page.get_by_role(
        "heading", name="DP780 synthetic reference steel", exact=True
    ).wait_for(timeout=30_000)
    page.go_forward()
    page.get_by_role("heading", name="Solver card delivery", exact=True).wait_for(
        timeout=30_000
    )

    page.get_by_role("button", name="Results", exact=True).click()
    page.wait_for_url(
        lambda url: "/materials?" in str(url) and "q=CMP-DEMO-DP780" in str(url),
        timeout=30_000,
    )
    result_table.locator("tbody tr").filter(has_text="CMP-DEMO-DP780").first.wait_for(
        timeout=30_000
    )
    return_url = page.url
    if "selected=" not in return_url or "table=" not in return_url:
        raise EvidenceError(f"return path lost query/scope/selection: {return_url}")

    page.context.close()
    return {
        "searchUrl": search_url,
        "exactUrl": exact_url,
        "exactPins": exact_params,
        "reloadReadBack": True,
        "returnUrl": return_url,
        "materialPropertiesAndConditions": True,
        "directTestDataUrl": test_url,
        "directTestDataTypeAndUnits": True,
        "directTestDataModelingAvailable": direct_test_modeling_available,
        "processingOutputUrl": simulation_url,
        "processingOutputSubtypeAndSource": True,
        "backForwardExactReadBack": True,
        "configuredCurvesModelingAvailable": curves_modeling_available,
        "startModelingUrl": modeling_url,
        "startModelingExactMaterialAndState": True,
        "solverCardUrl": solver_url,
        "solverCardTargetReleasePreviewAndDownloadState": True,
        "fixtureGaps": [
            (
                "Published direct Test Data records contain test kind, condition and "
                "curve coverage text but no stored curve value/modeling source, so "
                "their exact datasheets remain view-only."
            ),
            (
                "The published Material curve values are explicitly view-only; no "
                "provenance-qualified Materials Open in Modeling action exists in "
                "this fixture."
            ),
            (
                "No stored published direct link connects the Processing Output or "
                "selected Material Model to a Neutral Material or Solver Card; the "
                "exact Solver Card is verified independently through the Solver "
                "Cards peer root."
            ),
        ],
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
        originals = CORRECTION / phase / "originals"
        crops = CORRECTION / phase / "crops"
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


def _write_consistency_crops() -> None:
    for phase in ("before", "after"):
        originals = CONSISTENCY / phase / "originals"
        crops = CONSISTENCY / phase / "crops"
        crops.mkdir(parents=True, exist_ok=True)
        for state, regions in CONSISTENCY_STATES.items():
            for width, height in VIEWPORTS:
                source = originals / f"{state}-{_viewport(width, height)}.png"
                if not source.is_file():
                    raise EvidenceError(f"missing {phase} consistency original: {source}")
                with Image.open(source) as image:
                    if image.size != (width, height):
                        raise EvidenceError(
                            f"consistency original size drift: {source} {image.size}"
                        )
                    for region in regions:
                        target = (
                            crops
                            / f"{state}-{_viewport(width, height)}-{region}-100pct.png"
                        )
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
            "rationale": (
                "Issue #262 retains independently addressable before/after, "
                "direct-crop and current-guide provenance for exact-hash evidence."
            ),
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
    owner_report_verification: dict[str, Any] | None = None,
) -> None:
    images = sorted(
        [
            path
            for path in CORRECTION.rglob("*.png")
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
                    CORRECTION / "before/originals" / name,
                    CORRECTION / "after/originals" / name,
                )
            )
    manifest = {
        "schemaVersion": "cmp.issue-262.fe07a.owner-correction.visual-evidence.v1",
        "issue": "#262",
        "unit": "FE-07A Materials",
        "status": "OWNER_APPROVED_MINOR_CORRECTION_COMPLETE_UNMERGED",
        "browserZoomPercent": 100,
        "devicePixelRatio": 1,
        "display": "Playwright Chromium CSS viewports; no claim of physical Windows 4K readability",
        "viewports": [_viewport(width, height) for width, height in VIEWPORTS],
        "states": list(STATES),
        "measurements": measurements,
        "recovery": recovery,
        "continuity": continuity,
        "comparisons": comparisons,
        "ownerReport": [
            {
                "state": state,
                **_image_record(CORRECTION / "after/originals" / name),
            }
            for state, name in OWNER_REPORT_STATES
        ],
        "ownerReportVerification": owner_report_verification,
        "images": [_image_record(path) for path in images],
        "allowed_duplicate_groups": _duplicate_groups(),
    }
    (CORRECTION / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )


def _write_consistency_manifest(measurements: list[dict[str, Any]]) -> None:
    images = sorted(
        [path for path in CONSISTENCY.rglob("*.png") if path.is_file()],
        key=lambda path: path.as_posix(),
    )
    comparisons = []
    for state in CONSISTENCY_STATES:
        for width, height in VIEWPORTS:
            name = f"{state}-{_viewport(width, height)}.png"
            comparisons.append(
                _comparison(
                    CONSISTENCY / "before/originals" / name,
                    CONSISTENCY / "after/originals" / name,
                )
            )
    manifest = {
        "schemaVersion": "cmp.issue-262.fe07a.consistency-correction.v1",
        "issue": "#262",
        "unit": "FE-07A Materials",
        "status": "BOUNDED_CONSISTENCY_CORRECTION_COMPLETE_UNMERGED",
        "browserZoomPercent": 100,
        "devicePixelRatio": 1,
        "viewports": [_viewport(width, height) for width, height in VIEWPORTS],
        "states": list(CONSISTENCY_STATES),
        "afterMeasurements": measurements,
        "comparisons": comparisons,
        "images": [_image_record(path) for path in images],
    }
    (CONSISTENCY / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )


def _promote_consistency_curve_captures() -> None:
    current = ROOT / "docs/user-guide/images/current"
    originals = CONSISTENCY / "after/originals"
    for width, height in VIEWPORTS:
        name = f"material-curves-{_viewport(width, height)}.png"
        source = originals / name
        if not source.is_file():
            raise EvidenceError(f"missing corrected current-guide capture: {source}")
        shutil.copy2(source, current / name)


def _stage_correction_before() -> None:
    source = CORRECTION / "after/originals"
    if not source.is_dir():
        source = EVIDENCE / "after/originals"
    target = CORRECTION / "before/originals"
    target.mkdir(parents=True, exist_ok=True)
    for state in STATES:
        for width, height in VIEWPORTS:
            name = f"{state}-{_viewport(width, height)}.png"
            original = source / name
            if not original.is_file():
                raise EvidenceError(f"missing owner-correction baseline: {original}")
            shutil.copy2(original, target / name)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:5173")
    parser.add_argument("--manifest-only", action="store_true")
    parser.add_argument("--owner-report-only", action="store_true")
    parser.add_argument("--consistency-phase", choices=("before", "after"))
    args = parser.parse_args()
    CORRECTION.mkdir(parents=True, exist_ok=True)
    if args.manifest_only:
        if (CONSISTENCY / "after/originals").is_dir():
            _promote_consistency_curve_captures()
        current = json.loads((CORRECTION / "manifest.json").read_text(encoding="utf-8"))
        _write_manifest(
            current["measurements"],
            current["recovery"],
            current["continuity"],
            current.get("ownerReportVerification"),
        )
        print("FE-07A visual manifest refreshed from existing verified captures.")
        return 0
    if args.owner_report_only:
        current = json.loads((CORRECTION / "manifest.json").read_text(encoding="utf-8"))
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                owner_report_verification = _capture_owner_report(browser, args.base_url)
            finally:
                browser.close()
        _write_manifest(
            current["measurements"],
            current["recovery"],
            current["continuity"],
            owner_report_verification,
        )
        print("FE-07A owner report ready: five 1920x1080 originals verified.")
        return 0
    if args.consistency_phase:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                measurements = _capture_consistency_matrix(
                    browser, args.base_url, args.consistency_phase
                )
                if args.consistency_phase == "after":
                    owner_report_verification = _capture_owner_report(
                        browser, args.base_url
                    )
            finally:
                browser.close()
        if args.consistency_phase == "after":
            _write_consistency_crops()
            _write_consistency_manifest(measurements)
            _promote_consistency_curve_captures()
            current = json.loads(
                (CORRECTION / "manifest.json").read_text(encoding="utf-8")
            )
            _write_manifest(
                current["measurements"],
                current["recovery"],
                current["continuity"],
                owner_report_verification,
            )
        print(
            "FE-07A consistency evidence ready: "
            f"{args.consistency_phase}, {len(measurements)} geometry records."
        )
        return 0
    _stage_correction_before()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            measurements = _capture_matrix(browser, args.base_url)
            recovery = _capture_recovery(browser, args.base_url)
            continuity = _verify_continuity(browser, args.base_url)
            owner_report_verification = _capture_owner_report(browser, args.base_url)
        finally:
            browser.close()
    _write_crops()
    _write_manifest(measurements, recovery, continuity, owner_report_verification)
    print(
        "FE-07A visual evidence ready: "
        f"{len(measurements)} geometry records, 20 before/after pairs, "
        "error/recovery, reload, return, and exact handoff verified."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

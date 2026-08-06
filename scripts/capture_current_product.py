"""Capture the current product screens declared by the user-guide manifest.

Run against the deterministic Compose demo:

    uv run --with playwright==1.62.0 python scripts/capture_current_product.py
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import struct
import tempfile
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, cast
from urllib.parse import parse_qs, urlsplit

# Embedded Playwright snippets and exact UI labels intentionally exceed Ruff's
# line length and preserve typographic punctuation for source-contract checks.
# ruff: noqa: E501, RUF001

if TYPE_CHECKING:
    from playwright.sync_api import Browser, FloatRect, Locator, Page, Route

VIEWPORTS = ((1366, 768), (1440, 900), (1920, 1080))
WIDE_VIEWPORTS = ((2560, 1440), (3840, 2160))
REVISION_LABEL_PATTERN = re.compile(r"\br[1-9]\d*\b")
MODELING_EXPORT_OUTPUTS = tuple(
    f"modeling-export-{width}x{height}.png" for width, height in VIEWPORTS
)
MODELING_FIT_STATE_OUTPUTS = (
    "modeling-fit-candidate-parameters-long-1440x900.png",
    "modeling-fit-candidate-evidence-scrolled-1440x900.png",
    "modeling-fit-calculation-failed-1440x900.png",
    "modeling-fit-save-failed-1440x900.png",
    "modeling-fit-exact-source-blocked-1440x900.png",
    "modeling-fit-exact-read-failed-1440x900.png",
    "modeling-fit-restored-1440x900.png",
)
MODELING_PROCESS_FIT_OUTPUTS = (
    *(f"modeling-process-{width}x{height}.png" for width, height in (*VIEWPORTS, *WIDE_VIEWPORTS)),
    "modeling-fit-1366x768.png",
    "modeling-fit-1440x900.png",
    "modeling-fit-1920x1080.png",
    "modeling-fit-2560x1440.png",
    "modeling-fit-3840x2160.png",
    "modeling-fit-candidate-parameters-long-1440x900.png",
    "modeling-fit-candidate-evidence-scrolled-1440x900.png",
    "modeling-fit-calculation-failed-1440x900.png",
    "modeling-fit-save-failed-1440x900.png",
    "modeling-fit-exact-source-blocked-1440x900.png",
    "modeling-fit-exact-read-failed-1440x900.png",
    "modeling-fit-restored-1440x900.png",
)
MODELING_PROCESS_OUTPUTS = (
    *(f"modeling-process-{width}x{height}.png" for width, height in (*VIEWPORTS, *WIDE_VIEWPORTS)),
    "modeling-process-linear-regression-1366x768.png",
    "modeling-process-blocked-1440x900.png",
    "modeling-process-exact-read-failed-1440x900.png",
    "modeling-process-siblings-1440x900.png",
)
MODELING_CONSISTENCY_OUTPUTS = tuple(
    f"modeling-{stage}-{width}x{height}.png"
    for stage in ("data", "process", "fit", "export", "session")
    for width, height in VIEWPORTS
)
MODELING_DATA_SESSION_OUTPUTS = (
    *(f"modeling-data-{width}x{height}.png" for width, height in (*VIEWPORTS, *WIDE_VIEWPORTS)),
    *(f"modeling-session-{width}x{height}.png" for width, height in VIEWPORTS),
    "modeling-data-empty-1440x900.png",
    "modeling-data-invalid-1440x900.png",
)
PRODUCT_ACCESS_OUTPUTS = (
    "administration-access-1366x768.png",
    "administration-access-1440x900.png",
)
ADMINISTRATION_DATABASE_OUTPUTS = tuple(
    f"administration-database-{width}x{height}.png"
    for width, height in (*VIEWPORTS, *WIDE_VIEWPORTS)
)
ADMINISTRATION_RECORDS_OUTPUTS = tuple(
    f"administration-records-{width}x{height}.png"
    for width, height in (*VIEWPORTS, *WIDE_VIEWPORTS)
)
ACTIVITY_OUTPUTS = tuple(f"activity-{width}x{height}.png" for width, height in VIEWPORTS)
REVIEW_SUBMISSION_OUTPUTS = (
    *(
        f"{screen}-{width}x{height}.png"
        for screen in ("solver-card-preview", "activity")
        for width, height in VIEWPORTS
    ),
    "material-detail-1440x900.png",
)
CURRENT_CAPTURE_OUTPUTS = (
    "materials-search-1366x768.png",
    "materials-search-1440x900.png",
    "materials-search-1920x1080.png",
    "materials-search-long-1366x768.png",
    "materials-search-long-1440x900.png",
    "materials-search-long-1920x1080.png",
    "materials-search-short-1440x900.png",
    "materials-search-empty-1440x900.png",
    "materials-browse-1440x900.png",
    "material-detail-1366x768.png",
    "material-detail-1440x900.png",
    "material-detail-1920x1080.png",
    "material-cae-cards-1440x900.png",
    "materials-search-2560x1440.png",
    "materials-search-3840x2160.png",
    "material-detail-2560x1440.png",
    "material-detail-3840x2160.png",
    "solver-card-preview-1366x768.png",
    "solver-card-preview-1440x900.png",
    "solver-card-preview-1920x1080.png",
    "modeling-data-1366x768.png",
    "modeling-data-1440x900.png",
    "modeling-data-1920x1080.png",
    "modeling-data-2560x1440.png",
    "modeling-data-3840x2160.png",
    "modeling-session-1366x768.png",
    "modeling-session-1440x900.png",
    "modeling-session-1920x1080.png",
    "modeling-data-empty-1440x900.png",
    "modeling-data-invalid-1440x900.png",
    "modeling-process-1366x768.png",
    "modeling-process-linear-regression-1366x768.png",
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
    "modeling-fit-calculation-failed-1440x900.png",
    "modeling-fit-save-failed-1440x900.png",
    "modeling-fit-exact-source-blocked-1440x900.png",
    "modeling-fit-exact-read-failed-1440x900.png",
    "modeling-fit-restored-1440x900.png",
    "modeling-export-1366x768.png",
    "modeling-export-1440x900.png",
    "modeling-export-1920x1080.png",
    "activity-1366x768.png",
    "activity-1440x900.png",
    "activity-1920x1080.png",
    "administration-database-1366x768.png",
    "administration-database-1440x900.png",
    "administration-database-1920x1080.png",
    "administration-database-2560x1440.png",
    "administration-database-3840x2160.png",
    "administration-records-1366x768.png",
    "administration-records-1440x900.png",
    "administration-records-1920x1080.png",
    "administration-records-2560x1440.png",
    "administration-records-3840x2160.png",
    "administration-access-1366x768.png",
    "administration-access-1440x900.png",
)
STAGE_HEADINGS = {
    "data": "Select Test Data",
    "process": "Prepare observed curves",
    "fit": "Fit material response",
    "export": "Review & deliver solver card",
}
EXPECTED_EXACT_FIT_RESTORE_ERROR = "Saved Fit result unavailable · Retry exact saved result."
PROCESS_SOURCE_DOCUMENT_KEY = "CMP-DEMO-DP780-TEST-JSON"
PROCESS_SOURCE_TITLE = f"{PROCESS_SOURCE_DOCUMENT_KEY} · Specimen 01 · revision r1"
PROCESS_SOURCE_VISIBLE_IDENTITY = "Specimen 01 · r1"
PROCESS_NO_PREVIEW_SAVED_INSTRUCTION = (
    "No Process preview is active. Choose Use settings for a saved result, then select "
    "Preview changes to preview the draft."
)
NORMAL_COMPACT_DATA_RIBBON_HEIGHT = 178
UNFINISHED = re.compile(
    r"^(Checking|Loading|Calculating|Resolving|Updating|Preparing|Creating)\b.*(?:…|\.\.\.)$",
    re.IGNORECASE,
)
NORMAL_SURFACE_TECHNICAL_LABELS = re.compile(
    r"\b(?:draft|fixture|uuid|sha(?:256)?|hash|lifecycle[_\s-]?state)\b"
    r"|\bissue\s*#\s*\d+\b|\bimplementation state\b",
    re.IGNORECASE,
)
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _new_page(browser: Browser, base_url: str, width: int, height: int) -> Page:
    context = browser.new_context(viewport={"width": width, "height": height})
    token_response = context.request.get(f"{base_url}/api/v1/demo-identity/token")
    if not token_response.ok:
        raise RuntimeError("local demo identity is unavailable")
    access_token = token_response.json()["access_token"]
    page = context.new_page()
    page.goto(base_url)
    page.evaluate(
        """token => window.localStorage.setItem(
            "cmp.material-platform.api-config",
            JSON.stringify({baseUrl: "/api/v1", accessToken: token})
        )""",
        access_token,
    )
    return page


def _bounding_box_edges(box: FloatRect | None) -> dict[str, float] | None:
    """Add viewport edges to Playwright's x/y/width/height bounding box."""
    if box is None:
        return None
    return {
        "x": box["x"],
        "y": box["y"],
        "width": box["width"],
        "height": box["height"],
        "left": box["x"],
        "right": box["x"] + box["width"],
        "top": box["y"],
        "bottom": box["y"] + box["height"],
    }


def _wait_for_settled(page: Page) -> None:
    page.wait_for_load_state("networkidle")
    page.wait_for_function(
        """() => {
            const unfinished =
              /^(Checking|Loading|Calculating|Resolving|Updating|Preparing|Creating)\\b.*(?:…|\\.\\.\\.)$/i;
            const visible = element => element.getClientRects().length > 0;
            const textPending = document.body.innerText
              .split("\\n")
              .some((line) => unfinished.test(line.trim()));
            const activeStatus = [...document.querySelectorAll('[role="status"], .loading-state')]
              .some((element) => visible(element)
                && (element.textContent ?? "").split("\\n")
                  .some((line) => unfinished.test(line.trim())));
            const activeBusy = [...document.querySelectorAll('[aria-busy="true"]')]
              .some(visible);
            return !activeBusy && !textPending && !activeStatus;
        }""",
        timeout=30_000,
    )
    pending_lines = [
        line.strip()
        for line in page.locator("body").inner_text().splitlines()
        if UNFINISHED.match(line.strip())
    ]
    if pending_lines:
        raise RuntimeError(f"unfinished UI state remains: {pending_lines}")


def _capture(
    page: Page,
    path: Path,
    width: int,
    height: int,
    *,
    focus_selector: str | None = None,
    before_screenshot: Callable[[], object] | None = None,
) -> None:
    _wait_for_settled(page)
    overflow = page.evaluate(
        "document.documentElement.scrollWidth - document.documentElement.clientWidth"
    )
    if overflow != 0:
        raise RuntimeError(f"horizontal overflow is {overflow}px for {path.name}")
    page.evaluate(
        """() => {
            if (document.activeElement instanceof HTMLElement) {
              document.activeElement.blur();
            }
            window.scrollTo(0, 0);
            for (const selector of [
              ".application-workspace",
              ".modeling-task-ribbon",
              ".step-option-panel",
              ".native-card-preview",
              ".card-preview-actions",
            ]) {
              document.querySelectorAll(selector).forEach(element => {
                element.scrollTop = 0;
                element.scrollLeft = 0;
              });
            }
        }"""
    )
    if focus_selector is not None:
        page.locator(focus_selector).scroll_into_view_if_needed()
    if before_screenshot is not None:
        before_screenshot()
    page.evaluate(
        """async () => {
            if (document.activeElement instanceof HTMLElement) {
              document.activeElement.blur();
            }
            await new Promise(requestAnimationFrame);
            await new Promise(requestAnimationFrame);
        }"""
    )
    page.screenshot(path=str(path), full_page=False)
    viewport = page.viewport_size
    if viewport != {"width": width, "height": height}:
        raise RuntimeError(f"viewport drift for {path.name}: {viewport}")


def _open_materials_search(page: Page, base_url: str) -> None:
    page.goto(f"{base_url}/materials")
    search = page.get_by_role("textbox", name="Search materials")
    search.wait_for(timeout=30_000)
    search.fill("DP780")
    page.locator(".materials-search-form").get_by_role("button", name="Find", exact=True).click()
    rows = page.locator('table[aria-label="Material results"] tbody tr')
    rows.filter(has_text="DP780").first.wait_for(timeout=30_000)
    _wait_for_settled(page)
    if rows.count() < 1:
        raise RuntimeError("the deterministic DP780 Material result is missing")
    if page.get_by_text("Checking…", exact=True).count():
        raise RuntimeError("Material enrichment is incomplete")
    rows.filter(has_text="DP780").first.click()
    page.get_by_text("Selected material", exact=True).wait_for(timeout=30_000)
    page.locator(".application-status-bar").get_by_text(REVISION_LABEL_PATTERN).wait_for(
        timeout=30_000
    )
    if page.get_by_role("columnheader", name="Status", exact=True).count():
        raise RuntimeError("normal Materials results must not expose a Status column")
    for selector in (".materials-results", ".materials-selection", ".application-status-bar"):
        surface = page.locator(selector)
        surface.wait_for(timeout=30_000)
        surface_text = surface.inner_text()
        if NORMAL_SURFACE_TECHNICAL_LABELS.search(surface_text):
            raise RuntimeError(
                f"normal Materials surface exposes technical label in {selector}: {surface_text}"
            )


def _assert_material_pane_reset(page: Page, width: int) -> None:
    expected_navigator = 244 if width <= 1390 else 264 if width < 1600 else 280
    navigator = page.locator(".navigator-panel")
    navigator_separator = page.get_by_role("separator", name="Resize navigator")
    before = navigator.bounding_box()
    separator = navigator_separator.bounding_box()
    if before is None or separator is None:
        raise RuntimeError("Materials navigator divider is unavailable for reset verification")
    page.mouse.move(separator["x"] + 2, separator["y"] + 80)
    page.mouse.down()
    page.mouse.move(separator["x"] + 42, separator["y"] + 80)
    page.mouse.up()
    page.wait_for_timeout(100)
    dragged = navigator.bounding_box()
    if dragged is None or abs(dragged["width"] - before["width"]) < 10:
        raise RuntimeError("Materials navigator divider did not resize before reset verification")
    navigator_separator.dblclick()
    page.wait_for_timeout(100)
    reset = navigator.bounding_box()
    if reset is None or abs(reset["width"] - expected_navigator) > 4:
        raise RuntimeError(
            f"Materials navigator reset drift at {width}px: expected {expected_navigator}px, "
            f"got {reset and reset['width']}px"
        )

    if width <= 1390:
        return
    expected_context = 280 if width < 1600 else 300
    context = page.locator(".context-panel")
    context_separator = page.get_by_role("separator", name="Resize details")
    context_before = context.bounding_box()
    context_divider = context_separator.bounding_box()
    if context_before is None or context_divider is None:
        raise RuntimeError("Materials context divider is unavailable for reset verification")
    page.mouse.move(context_divider["x"] + 2, context_divider["y"] + 80)
    page.mouse.down()
    page.mouse.move(context_divider["x"] - 42, context_divider["y"] + 80)
    page.mouse.up()
    page.wait_for_timeout(100)
    context_dragged = context.bounding_box()
    if context_dragged is None or abs(context_dragged["width"] - context_before["width"]) < 10:
        raise RuntimeError("Materials context divider did not resize before reset verification")
    context_separator.dblclick()
    page.wait_for_timeout(100)
    context_reset = context.bounding_box()
    if context_reset is None or abs(context_reset["width"] - expected_context) > 4:
        raise RuntimeError(
            f"Materials context reset drift at {width}px: expected {expected_context}px, "
            f"got {context_reset and context_reset['width']}px"
        )


def _assert_wide_material_cluster(page: Page, width: int) -> None:
    geometry = page.locator(".materials-page").evaluate(
        "element => { const bounds = element.getBoundingClientRect(); "
        "return { left: bounds.left, width: bounds.width }; }"
    )
    if geometry["left"] > 8 or geometry["width"] > min(width, 1920) + 1:
        raise RuntimeError(
            f"Materials workspace escaped its bounded left cluster at {width}px: {geometry}"
        )
    if page.evaluate("document.documentElement.scrollWidth > window.innerWidth"):
        raise RuntimeError(f"Materials has page-level horizontal overflow at {width}px")


def _assert_response_points_table(page: Page, width: int) -> None:
    table = page.get_by_role("table", name="Representative response points")
    if width < 1800:
        if table.is_visible():
            raise RuntimeError(f"response points table leaked into compact {width}px layout")
        return
    region = page.get_by_role("region", name="Scrollable representative response points")
    region.wait_for(timeout=30_000)
    table.wait_for(timeout=30_000)
    geometry = region.evaluate(
        """region => {
          const shell = region.parentElement;
          const header = region.querySelector('thead th');
          const table = region.querySelector('table');
          const rail = shell?.querySelector('.materials-scroll-rail-y');
          const xRail = shell?.querySelector('.materials-scroll-rail-x');
          const rect = element => {
            if (!element) return null;
            const bounds = element.getBoundingClientRect();
            return {
              left: bounds.left,
              right: bounds.right,
              top: bounds.top,
              bottom: bounds.bottom,
            };
          };
          const style = header ? getComputedStyle(header) : null;
          return {
            region: rect(region),
            table: rect(table),
            rail: rect(rail),
            clientHeight: region.clientHeight,
            scrollHeight: region.scrollHeight,
            clientWidth: region.clientWidth,
            scrollWidth: region.scrollWidth,
            scrollTop: region.scrollTop,
            tabIndex: region.tabIndex,
            role: region.getAttribute('role'),
            headerPosition: style?.position ?? null,
            headerBackground: style?.backgroundColor ?? null,
            scrollY: shell?.getAttribute('data-scroll-y') ?? null,
            scrollX: shell?.getAttribute('data-scroll-x') ?? null,
            hasHorizontalRail: Boolean(xRail),
          };
        }"""
    )
    if geometry["role"] != "region" or geometry["tabIndex"] != 0:
        raise RuntimeError("response points region is not keyboard-focusable")
    if geometry["headerPosition"] != "sticky" or geometry["headerBackground"] in (
        None,
        "rgba(0, 0, 0, 0)",
    ):
        raise RuntimeError("response points header is not visibly sticky")
    if geometry["scrollY"] != "true" or geometry["scrollHeight"] <= geometry["clientHeight"]:
        raise RuntimeError("response points vertical overflow rail is missing")
    if (
        geometry["scrollX"] != "false"
        or geometry["hasHorizontalRail"]
        or geometry["scrollWidth"] > geometry["clientWidth"] + 1
    ):
        raise RuntimeError("response points exposes an unexpected horizontal rail")
    if (
        not geometry["rail"]
        or not geometry["table"]
        or geometry["table"]["right"] > geometry["region"]["right"] + 1
    ):
        raise RuntimeError("response points table and visible rail overlap or are unavailable")
    region.evaluate("element => { element.scrollTop = 0; element.scrollLeft = 0; }")
    if region.evaluate("element => element.scrollTop") != 0:
        raise RuntimeError("response points capture did not restore scroll position")


_SCROLL_TABLE_ID = "materials-reference-table"


def _scroll_metadata(entity_id: str, revision_no: int = 1) -> dict[str, object]:
    return {
        "id": f"{entity_id}-revision",
        "aggregate_id": entity_id,
        "revision_no": revision_no,
        "based_on_revision_id": None,
        "schema_id": "urn:cmp:materials-reference:1",
        "schema_version": "1.0.0",
        "content_hash": "a" * 64,
        "created_at": "2026-08-03T00:00:00Z",
        "created_by": "00000000-0000-0000-0000-000000000001",
        "change_reason": "materials reference archive",
        "organization_id": "00000000-0000-0000-0000-000000000002",
        "project_id": "00000000-0000-0000-0000-000000000003",
        "classification": "internal",
        "lifecycle_state": "published",
    }


def _scroll_table() -> dict[str, object]:
    return {
        "table_id": _SCROLL_TABLE_ID,
        "current_revision": {
            **_scroll_metadata(f"{_SCROLL_TABLE_ID}-current"),
            "content": {
                "key": "demo_material_records",
                "name": "Materials Reference Table",
                "description": "Materials reference table",
            },
        },
    }


def _scroll_folder(folder_id: str, name: str, parent_folder_id: str | None) -> dict[str, object]:
    return {
        "folder_id": folder_id,
        "table_id": _SCROLL_TABLE_ID,
        "current_revision": _scroll_metadata(folder_id),
        "content": {
            "table_revision_id": f"{_SCROLL_TABLE_ID}-current-revision",
            "name": name,
            "description": None,
            "parent_folder_id": parent_folder_id,
            "parent_folder_revision_id": (
                f"{parent_folder_id}-revision" if parent_folder_id else None
            ),
        },
    }


def _scroll_record(
    record_id: str,
    row: int,
    name: str | None = None,
) -> dict[str, object]:
    names = (
        "DP780 dual-phase steel",
        "DP600 dual-phase steel",
        "HSLA structural steel",
        "AISI 304 stainless steel",
        "PA66 glass-filled polymer",
    )
    material_name = name or f"{names[row % len(names)]} · reference {row:03}"
    material_class = "polymer" if "PA66" in material_name else "metal"
    return {
        "record_id": record_id,
        "table_id": _SCROLL_TABLE_ID,
        "domain_binding": {
            "binding_id": f"{record_id}-binding",
            "record_id": record_id,
            "record_revision_id": f"{record_id}-revision",
            "kind": "material",
            "object_id": f"{record_id}-material",
            "revision_id": f"{record_id}-material-revision",
            "workbench_path": f"/materials/{record_id}-material",
        },
        "current_revision": {
            **_scroll_metadata(f"{record_id}-revision"),
            "content": {
                "table_revision_id": f"{_SCROLL_TABLE_ID}-current-revision",
                "name": material_name,
                "external_key": f"MAT-{row + 1:03}",
                "description": "Materials reference record with governed response data",
                "folder_id": None,
                "folder_revision_id": None,
                "values": [
                    {
                        "data_type": "discrete",
                        "attribute_definition_id": "material-class",
                        "attribute_definition_revision_id": "material-class-r1",
                        "value": material_class,
                    },
                    {
                        "data_type": "text",
                        "attribute_definition_id": "provider",
                        "attribute_definition_revision_id": "provider-r1",
                        "value": "Northstar Materials",
                    },
                    {
                        "data_type": "text",
                        "attribute_definition_id": "evidence-source",
                        "attribute_definition_revision_id": "evidence-source-r1",
                        "value": "Governed reference",
                    },
                ],
            },
        },
    }


def _install_material_scroll_fixture(page: Page) -> None:
    folder_names = (
        "Cold-rolled steel reference archive for stamped body panels",
        "Automotive body sheet grades",
        "Structural plate and section data",
        "Heat-treated alloy specifications",
        "Stainless and corrosion-resistant grades",
        "Polymer compound reference data",
        "Supplier certificate imports",
        "Qualification and acceptance records",
        "Legacy design allowables",
        "Temperature-conditioned studies",
        "Welded joint material records",
        "Surface-treated coil references",
    )
    root_folders = [
        _scroll_folder(
            f"folder-{index}",
            f"{folder_names[index % len(folder_names)]} · {index + 1:03}",
            None,
        )
        for index in range(90)
    ]
    short_names = (
        "DP780 dual-phase steel",
        "DP600 dual-phase steel",
        "HSLA structural steel",
        "AISI 304 stainless steel",
        "IF mild steel",
        "TRIP advanced high-strength steel",
    )

    def fulfill(route: Route, value: object) -> None:
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(value),
        )

    def handle(route: Route) -> None:
        request = route.request
        parsed = urlsplit(request.url)
        request_path = parsed.path
        if request_path.endswith("/catalog/explorer/tables"):
            fulfill(route, {"items": [_scroll_table()]})
            return
        if request_path.endswith(f"/catalog/explorer/tables/{_SCROLL_TABLE_ID}/children"):
            parent = parse_qs(parsed.query).get("parent_folder_id", [None])[0]
            folders = [] if parent else root_folders
            fulfill(route, {"table": _scroll_table(), "folders": folders, "records": []})
            return
        if request_path.endswith(f"/catalog/tables/{_SCROLL_TABLE_ID}/subsets"):
            fulfill(route, {"items": []})
            return
        if request_path.endswith(f"/catalog/tables/{_SCROLL_TABLE_ID}/attributes"):
            fulfill(
                route,
                {
                    "items": [
                        {
                            "attribute_definition_id": "material-class",
                            "table_id": _SCROLL_TABLE_ID,
                            "current_revision": {"content": {"key": "material_class"}},
                        },
                        {
                            "attribute_definition_id": "provider",
                            "table_id": _SCROLL_TABLE_ID,
                            "current_revision": {"content": {"key": "provider"}},
                        },
                        {
                            "attribute_definition_id": "evidence-source",
                            "table_id": _SCROLL_TABLE_ID,
                            "current_revision": {"content": {"key": "evidence_source"}},
                        },
                    ]
                },
            )
            return
        if request_path.endswith("/catalog/records:search"):
            payload = request.post_data_json or {}
            text = payload.get("text") if isinstance(payload, dict) else None
            count = 0 if text == "magnesium" else 6 if text == "steel" else 50
            total_count = 0 if count == 0 else 6 if count == 6 else 120
            facets = (
                []
                if count == 0
                else [
                    {
                        "attribute_definition_id": attribute_id,
                        "value": value,
                        "count": total_count,
                    }
                    for attribute_id, value in (
                        ("material-class", "metal"),
                        ("provider", "Northstar Materials"),
                        ("evidence-source", "Governed reference"),
                    )
                ]
            )
            fulfill(
                route,
                {
                    "items": [
                        _scroll_record(
                            f"record-{index}",
                            index,
                            short_names[index] if text == "steel" else None,
                        )
                        for index in range(count)
                    ],
                    "total_count": total_count,
                    "offset": 0,
                    "limit": 50,
                    "facets": facets,
                },
            )
            return
        route.continue_()

    page.route("**/api/v1/**", handle)


def _open_material_scroll_state(page: Page, base_url: str, search_text: str) -> None:
    page.goto(f"{base_url}/materials")
    search = page.get_by_role("textbox", name="Search materials")
    search.wait_for(timeout=30_000)
    search.fill(search_text)
    page.locator(".materials-search-form").get_by_role("button", name="Find", exact=True).click()
    if search_text == "magnesium":
        page.get_by_text("No materials match this search.", exact=True).wait_for(timeout=30_000)
    else:
        page.locator('table[aria-label="Material results"] tbody tr').first.wait_for(timeout=30_000)
    _wait_for_settled(page)


def _capture_material_scroll_states(browser: Browser, base_url: str, output: Path) -> None:
    for width, height in VIEWPORTS:
        page = _new_page(browser, base_url, width, height)
        _install_material_scroll_fixture(page)
        _open_material_scroll_state(page, base_url, "reference")
        _capture(
            page,
            output / f"materials-search-long-{width}x{height}.png",
            width,
            height,
        )
        page.context.close()

    for search_text, output_name in (
        ("steel", "materials-search-short-1440x900.png"),
        ("magnesium", "materials-search-empty-1440x900.png"),
    ):
        page = _new_page(browser, base_url, 1440, 900)
        _install_material_scroll_fixture(page)
        _open_material_scroll_state(page, base_url, search_text)
        _capture(page, output / output_name, 1440, 900)
        page.context.close()


def _open_material_detail(page: Page, base_url: str) -> None:
    _open_materials_search(page, base_url)
    page.locator('table[aria-label="Material results"] tbody tr').filter(
        has_text="DP780"
    ).first.dblclick()
    page.wait_for_url(
        re.compile(
            r"/materials/[0-9a-f-]+\?record_id=[0-9a-f-]+"
            r"&record_revision_id=[0-9a-f-]+&material_revision_id=[0-9a-f-]+$"
        ),
        timeout=30_000,
    )
    page.get_by_role("heading", name="Key properties", exact=True).wait_for(timeout=30_000)
    for tab_name in ("Overview", "Properties", "Curves", "CAE Cards", "Evidence"):
        page.get_by_role("tab", name=tab_name, exact=True).wait_for(timeout=30_000)
    _wait_for_settled(page)
    page.get_by_text(
        re.compile(r"^(Request review|Waiting for review|Approved|Changes requested)$")
    ).first.wait_for(timeout=30_000)
    page.locator(".application-status-bar").get_by_text(REVISION_LABEL_PATTERN).wait_for(
        timeout=30_000
    )
    for selector in (
        ".material-detail-header",
        '[aria-label="Related exact records"]',
        ".application-status-bar",
    ):
        surface = page.locator(selector)
        surface.wait_for(timeout=30_000)
        surface_text = surface.inner_text()
        if NORMAL_SURFACE_TECHNICAL_LABELS.search(surface_text):
            raise RuntimeError(
                "normal Material detail surface exposes technical label in "
                f"{selector}: {surface_text}"
            )


def _capture_materials(browser: Browser, base_url: str, output: Path) -> None:
    for width, height in VIEWPORTS:
        page = _new_page(browser, base_url, width, height)
        _open_materials_search(page, base_url)
        _assert_material_pane_reset(page, width)
        _capture(page, output / f"materials-search-{width}x{height}.png", width, height)
        page.context.close()

    for width, height in WIDE_VIEWPORTS:
        page = _new_page(browser, base_url, width, height)
        _open_materials_search(page, base_url)
        _assert_wide_material_cluster(page, width)
        _capture(page, output / f"materials-search-{width}x{height}.png", width, height)
        page.context.close()

    _capture_material_scroll_states(browser, base_url, output)

    width, height = 1440, 900
    page = _new_page(browser, base_url, width, height)
    _open_materials_search(page, base_url)
    page.get_by_role("button", name="Browse", exact=True).click()
    page.get_by_role("complementary", name="Materials navigator").wait_for(timeout=30_000)
    tree_find = page.get_by_role("textbox", name="Find in tree")
    tree_find.wait_for(timeout=30_000)
    tree_find.fill("Material Library")
    page.get_by_test_id("navigator").get_by_role("button", name="Find", exact=True).click()
    page.get_by_text("Material Library", exact=True).wait_for(timeout=30_000)
    _capture(page, output / "materials-browse-1440x900.png", width, height)
    page.context.close()

    page = _new_page(browser, base_url, width, height)
    _open_material_detail(page, base_url)
    _assert_response_points_table(page, width)
    _capture(page, output / "material-detail-1440x900.png", width, height)
    page.get_by_role("tab", name="CAE Cards", exact=True).click()
    page.get_by_role("heading", name="CAE Cards", exact=True).wait_for(timeout=30_000)
    _wait_for_settled(page)
    primary_delivery_actions = page.locator(
        ".material-detail-header .card-action-row button.ux-button.primary"
    )
    if primary_delivery_actions.count() != 1 or not re.match(
        r"^(Download|Preview card|Create card|Start Modeling)",
        primary_delivery_actions.first.inner_text(),
    ):
        raise RuntimeError("CAE Cards must expose exactly one contextual filled delivery command")
    _capture(page, output / "material-cae-cards-1440x900.png", width, height)
    page.context.close()

    for width, height in ((1366, 768), (1920, 1080)):
        page = _new_page(browser, base_url, width, height)
        _open_material_detail(page, base_url)
        _assert_response_points_table(page, width)
        _capture(page, output / f"material-detail-{width}x{height}.png", width, height)
        page.context.close()

    for width, height in WIDE_VIEWPORTS:
        page = _new_page(browser, base_url, width, height)
        _open_material_detail(page, base_url)
        _assert_wide_material_cluster(page, width)
        _assert_response_points_table(page, width)
        _capture(page, output / f"material-detail-{width}x{height}.png", width, height)
        page.context.close()


def _assert_linked_response_labels_visible(page: Page) -> None:
    geometry = page.locator(".response-plot").evaluate(
        """svg => {
          const frame = svg.closest('.response-plot-frame')?.getBoundingClientRect();
          const status = document.querySelector('.application-status-bar')?.getBoundingClientRect();
          const rect = element => {
            if (!element) return null;
            const bounds = element.getBoundingClientRect();
            return {
              left: bounds.left,
              right: bounds.right,
              top: bounds.top,
              bottom: bounds.bottom,
            };
          };
          const xTickLabels = [...svg.querySelectorAll('.linked-response-tick-label')]
            .filter(label => {
              const tick = label.parentElement?.querySelector('.linked-response-tick');
              return tick?.getAttribute('y1') !== tick?.getAttribute('y2');
            });
          return {
            frame: frame
              ? { left: frame.left, right: frame.right, top: frame.top, bottom: frame.bottom }
              : null,
            statusTop: status?.top ?? null,
            xTicks: xTickLabels.map(rect),
            xTitle: rect(svg.querySelector('.linked-response-axis-title:not([transform])')),
          };
        }"""
    )
    if not geometry["frame"] or geometry["statusTop"] is None:
        raise RuntimeError("linked response plot frame or status bar is unavailable")
    if not geometry["xTicks"] or not geometry["xTitle"]:
        raise RuntimeError("linked response plot has no rendered x-axis ticks or title")
    frame = geometry["frame"]
    status_top = float(geometry["statusTop"])
    for label in [*geometry["xTicks"], geometry["xTitle"]]:
        if (
            label["left"] < frame["left"] - 1
            or label["right"] > frame["right"] + 1
            or label["top"] < frame["top"] - 1
            or label["bottom"] > frame["bottom"] + 1
            or label["bottom"] > status_top + 1
        ):
            raise RuntimeError(
                "linked response x-axis label is clipped: "
                f"label={label}, frame={frame}, status_top={status_top}"
            )


def _capture_solver_delivery(browser: Browser, base_url: str, output: Path) -> None:
    for width, height in VIEWPORTS:
        page = _new_page(browser, base_url, width, height)
        _open_materials_search(page, base_url)
        page.locator('table[aria-label="Material results"] tbody tr').filter(
            has_text="DP780"
        ).first.dblclick()
        page.wait_for_url(
            re.compile(
                r"/materials/[0-9a-f-]+\?record_id=[0-9a-f-]+"
                r"&record_revision_id=[0-9a-f-]+&material_revision_id=[0-9a-f-]+$"
            ),
            timeout=30_000,
        )
        if width == 1440:
            page.get_by_text(
                re.compile(r"^(Request review|Waiting for review|Approved|Changes requested)$")
            ).first.wait_for(timeout=30_000)
            _capture(
                page,
                output / "material-detail-1440x900.png",
                width,
                height,
            )
        page.get_by_role("tab", name="CAE Cards", exact=True).click()
        openradioss = page.locator(".cae-card-table tbody tr").filter(has_text="OpenRadioss").first
        openradioss.get_by_role("button", name=re.compile(r"^Preview(?: card)?$")).click()
        page.wait_for_url(
            re.compile(
                r"/materials/[0-9a-f-]+/cards/[0-9a-f-]+\?record_id=[0-9a-f-]+"
                r"&record_revision_id=[0-9a-f-]+&material_revision_id=[0-9a-f-]+$"
            ),
            timeout=30_000,
        )
        page.get_by_role("heading", name="Delivery check", exact=True).wait_for(timeout=30_000)
        download = page.get_by_role("button", name="Download .rad", exact=True)
        download.wait_for(timeout=30_000)
        native_preview = page.get_by_label("Native solver card preview")
        native_preview.wait_for(timeout=30_000)
        if native_preview.get_attribute("tabindex") != "0":
            raise RuntimeError("native solver card preview is not keyboard focusable")
        scroll_state = native_preview.evaluate(
            "element => ({"
            "clientHeight: element.clientHeight, "
            "scrollHeight: element.scrollHeight, "
            "scrollTop: element.scrollTop"
            "})"
        )
        if scroll_state["scrollHeight"] > scroll_state["clientHeight"] + 1:
            rail = page.locator(".preview-scroll-rail")
            if rail.get_attribute("data-scrollable") != "true":
                raise RuntimeError(
                    "long native solver card preview has no visible local scroll rail"
                )
            native_preview.focus()
            native_preview.press("End")
            page.wait_for_function(
                "element => element.scrollTop > 0",
                arg=native_preview.element_handle(),
            )
            native_preview.press("Home")
        linked_response = page.get_by_role(
            "img",
            name="Linked response chart showing true stress in MPa versus true plastic strain",
        )
        if width >= 1800:
            linked_response.wait_for(state="visible", timeout=30_000)
            if linked_response.get_attribute("data-x-label") != "True plastic strain [1]":
                raise RuntimeError("linked response graph has the wrong horizontal axis")
            y_domain = linked_response.get_attribute("data-y-domain") or ""
            try:
                y_bounds = [float(value) for value in y_domain.split(",")]
            except ValueError as cause:
                raise RuntimeError("linked response graph has an invalid stress range") from cause
            if len(y_bounds) != 2 or min(y_bounds) < 0 or max(y_bounds) >= 10_000:
                raise RuntimeError("linked response graph is not displayed in MPa")
            _assert_linked_response_labels_visible(page)
        elif linked_response.is_visible():
            raise RuntimeError("linked response graph must remain bounded to wide workspaces")
        if page.locator(".mapping-status.unsupported").count():
            raise RuntimeError("exact demo card unexpectedly exposes an unsupported mapping")
        approximation_count = page.locator(
            ".mapping-status.approximated, .mapping-status.ignored"
        ).count()
        acknowledgement = page.get_by_role("checkbox")
        if approximation_count:
            if acknowledgement.count() != 1 or download.is_enabled():
                raise RuntimeError(
                    "approximated solver-card delivery must require one adjacent acknowledgement"
                )
            acknowledgement.check()
            if not download.is_enabled():
                raise RuntimeError("reviewed approximation did not enable solver-card delivery")
        elif acknowledgement.count() or not download.is_enabled():
            raise RuntimeError("exact solver-card delivery has a redundant confirmation")
        review_reason = page.get_by_role("textbox", name="Review request reason", exact=True)
        if (
            not review_reason.count()
            and page.get_by_role("button", name="Request review", exact=True).count()
        ):
            page.get_by_role("button", name="Request review", exact=True).click()
        review_reason = page.get_by_role("textbox", name="Review request reason", exact=True)
        if review_reason.count():
            review_reason.fill("Review the synthetic native card mapping before use.")
            page.get_by_role("button", name="Send request", exact=True).click()
        page.get_by_role("status").filter(has_text="Waiting for review").wait_for(timeout=30_000)
        _capture(
            page,
            output / f"solver-card-preview-{width}x{height}.png",
            width,
            height,
        )
        _ensure_activity_review_fixture(page, base_url)
        page.goto(f"{base_url}/activity")
        _wait_for_activity_queue(page)
        solver_review = page.get_by_role("listitem").filter(has_text="Solver card review").first
        solver_review.wait_for(timeout=30_000)
        solver_review.get_by_role("button", name="Review", exact=True).wait_for(timeout=30_000)
        _capture(page, output / f"activity-{width}x{height}.png", width, height)
        page.context.close()


def _capture_activity(browser: Browser, base_url: str, output: Path) -> None:
    for width, height in VIEWPORTS:
        page = _new_page(browser, base_url, width, height)
        _ensure_activity_review_fixture(page, base_url)
        page.goto(f"{base_url}/activity")
        _wait_for_activity_queue(page)
        _capture(page, output / f"activity-{width}x{height}.png", width, height)
        page.context.close()


def _wait_for_activity_queue(page: Page) -> None:
    page.get_by_role("heading", name="Activity", exact=True).wait_for(timeout=30_000)
    page.get_by_role("heading", name="Needs attention", exact=True).wait_for(timeout=30_000)
    page.get_by_text(re.compile(r"^(Selected model review|Material data review)$")).first.wait_for(
        timeout=30_000
    )
    page.get_by_role("button", name="Review", exact=True).first.wait_for(timeout=30_000)


def _ensure_activity_review_fixture(page: Page, base_url: str) -> None:
    """Reuse the clean-demo selected-model review or create the no-review fallback."""
    outcome = page.evaluate(
        """async ({ baseUrl }) => {
          const config = JSON.parse(
            localStorage.getItem("cmp.material-platform.api-config") || "{}"
          );
          const headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": `Bearer ${config.accessToken}`,
          };
          const reviews = await fetch(`${baseUrl}/api/v1/review-requests?limit=50`, { headers });
          if (!reviews.ok) throw new Error(`cannot list review requests: ${reviews.status}`);
          if ((await reviews.json()).items.length) return "reused";
          const materials = await fetch(
            `${baseUrl}/api/v1/materials?limit=10&offset=0`, { headers }
          );
          if (!materials.ok) {
            throw new Error(`cannot list synthetic materials: ${materials.status}`);
          }
          const material = (await materials.json()).items.find(
            item => item.current_revision?.lifecycle_state === "draft"
          );
          if (!material) return "empty";
          const revision = material.current_revision;
          const created = await fetch(`${baseUrl}/api/v1/review-requests`, {
            method: "POST",
            headers,
            body: JSON.stringify({
              classification: revision.classification,
              aggregate_type: "catalog.material",
              aggregate_id: material.material_id,
              revision_id: revision.id,
              manifest_sha256: revision.content_hash,
              reason: "Review synthetic material data for the Activity queue",
            }),
          });
          if (!created.ok) {
            throw new Error(`cannot create Activity review fixture: ${created.status}`);
          }
          return "created";
        }""",
        {"baseUrl": base_url},
    )
    if outcome not in {"created", "reused"}:
        raise RuntimeError(f"unexpected Activity fixture result: {outcome}")


def _open_modeling_stage(page: Page, stage: str) -> None:
    stage_title = stage.title()
    stage_button = page.locator(".modeling-stage-shell button:visible").filter(
        has=page.locator("strong").filter(
            has_text=re.compile(rf"^{re.escape(stage_title)}$")
        )
    )
    stage_button.wait_for(state="visible", timeout=30_000)
    if stage_button.count() != 1:
        raise RuntimeError(
            f"Modeling stage {stage_title!r} did not resolve to exactly one visible stage button"
        )
    stage_button.click()


def _wait_for_modeling_data_surface(page: Page) -> None:
    """Wait for the visible Data workspace, not an off-screen heading."""
    page.locator(".data-source-tabs").wait_for(state="visible", timeout=30_000)
    page.locator(".modeling-workspace-rail").wait_for(state="visible", timeout=30_000)
    page.locator(".persistent-modeling-plot").wait_for(state="visible", timeout=30_000)


def _modeling_session(page: Page) -> dict[str, object]:
    raw = page.evaluate(
        "() => window.sessionStorage.getItem('cmp.modeling.recent-session.v4')"
    )
    if not raw:
        raise RuntimeError("Modeling Data session v4 is missing from sessionStorage")
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as cause:
        raise RuntimeError("Modeling Data session v4 is not valid JSON") from cause
    if not isinstance(parsed, dict):
        raise RuntimeError("Modeling Data session v4 has an unexpected shape")
    return parsed


def _data_session_snapshot(page: Page) -> dict[str, object]:
    session = _modeling_session(page)
    workspace = session.get("workspace")
    if not isinstance(workspace, dict):
        raise RuntimeError("Modeling Data session has no workspace state")
    refs = workspace.get("selectedTestDataRefs")
    included = workspace.get("selectedDocumentIds")
    visible = workspace.get("visibleTestDataKeys")
    if not isinstance(refs, list) or not isinstance(included, list) or not isinstance(visible, list):
        raise RuntimeError("Modeling Data session is missing exact selection arrays")
    return {
        "selectedTestDataRefs": refs,
        "selectedDocumentIds": included,
        "visibleTestDataKeys": visible,
    }


def _session_list(snapshot: dict[str, object], key: str) -> list[object]:
    value = snapshot.get(key)
    if not isinstance(value, list):
        raise RuntimeError(f"Modeling Data session field {key!r} is not a list")
    return value


def _wait_for_data_session_counts(page: Page, refs: int, included: int, visible: int) -> None:
    page.wait_for_function(
        """expected => {
          const raw = window.sessionStorage.getItem('cmp.modeling.recent-session.v4');
          if (!raw) return false;
          const workspace = JSON.parse(raw).workspace || {};
          return Array.isArray(workspace.selectedTestDataRefs)
            && workspace.selectedTestDataRefs.length === expected.refs
            && Array.isArray(workspace.selectedDocumentIds)
            && workspace.selectedDocumentIds.length === expected.included
            && Array.isArray(workspace.visibleTestDataKeys)
            && workspace.visibleTestDataKeys.length === expected.visible;
        }""",
        arg={"refs": refs, "included": included, "visible": visible},
        timeout=30_000,
    )


def _wait_for_exact_document_load_settled(page: Page) -> None:
    """Wait for the selected exact Test Data read to finish successfully."""
    page.wait_for_function(
        """() => {
          const selection = document.querySelector('select[aria-label="Test Data revision"]');
          const selected = selection?.selectedOptions?.[0];
          const load = [...document.querySelectorAll('.processing-input-card button')]
            .find(button => button.textContent?.trim() === 'Load exact JSON');
          return Boolean(
            selection
              && selection.value
              && selected
              && selected.value === selection.value
              && load
              && !load.disabled
              && !document.querySelector('.error-banner')
          );
        }""",
        timeout=30_000,
    )


def _wait_for_data_plot(page: Page, *, lines: int = 3, legends: int = 3) -> None:
    page.wait_for_function(
        """expected => document.querySelectorAll('.curve-line.data-observed').length === expected.lines
          && document.querySelectorAll('.persistent-modeling-plot .curve-legend.interactive button').length === expected.legends""",
        arg={"lines": lines, "legends": legends},
        timeout=30_000,
    )


def _wait_for_modeling_data_ribbon(page: Page) -> None:
    page.wait_for_function(
        """expected => {
          const panel = document.querySelector('.modeling-data-ribbon-panel');
          if (!panel) return false;
          return Math.abs(panel.getBoundingClientRect().height - expected) <= 1;
        }""",
        arg=NORMAL_COMPACT_DATA_RIBBON_HEIGHT,
        timeout=30_000,
    )


def _assert_modeling_data_surface(page: Page, width: int, height: int) -> None:
    """Assert the normal Data topology and readable identity at one viewport."""
    if page.evaluate(
        "document.documentElement.scrollWidth > document.documentElement.clientWidth"
    ):
        raise RuntimeError(f"Modeling Data has page horizontal overflow at {width}x{height}")
    rail = page.locator(".modeling-workspace-rail")
    curve_rows = rail.locator(".curve-row-label")
    if curve_rows.count() != 3:
        raise RuntimeError(f"expected three visible curve rows at {width}x{height}")
    identity_metrics = curve_rows.evaluate_all(
        """elements => elements.map(element => {
          const lineMetrics = node => {
            if (!node) return null;
            const box = node.getBoundingClientRect();
            return {
              text: node.textContent?.trim() ?? '',
              visible: node.getClientRects().length > 0,
              fits: node.scrollWidth <= node.clientWidth + 1,
              top: box.top,
              bottom: box.bottom,
            };
          };
          const rowBox = element.getBoundingClientRect();
          const primary = element.querySelector(':scope > span > strong');
          const secondary = element.querySelector(':scope > span > .curve-secondary-identity');
          const secondaryLines = secondary ? [...secondary.querySelectorAll(':scope > span')] : [];
          return {
            primary: lineMetrics(primary),
            secondary: secondaryLines.map(lineMetrics),
            row: { top: rowBox.top, bottom: rowBox.bottom },
          };
        })"""
    )
    if len(identity_metrics) != 3:
        raise RuntimeError(f"curve rail identity lines are missing at {width}x{height}: {identity_metrics}")
    for identity in identity_metrics:
        primary = identity["primary"]
        secondary = identity["secondary"]
        if primary is None or len(secondary) != 1 or not primary["visible"] or not primary["fits"] or not secondary[0]["visible"] or not secondary[0]["fits"]:
            raise RuntimeError(f"curve rail identity line is clipped at {width}x{height}: {identity}")
        if not primary["text"].lower().startswith(("specimen", "sample")):
            raise RuntimeError(f"curve rail specimen identity is not explicit: {identity}")
        if not re.fullmatch(r"(?:Session revision|Revision) r[1-9]\d*", secondary[0]["text"]):
            raise RuntimeError(f"curve rail exact revision identity drifted: {identity}")
        if primary["text"].casefold() == secondary[0]["text"].casefold():
            raise RuntimeError(f"curve rail identity lines duplicate at {width}x{height}: {identity}")
        if any(
            line["top"] < identity["row"]["top"] - 1 or line["bottom"] > identity["row"]["bottom"] + 1
            for line in (primary, secondary[0])
        ):
            raise RuntimeError(f"curve rail identity line escaped its row: {identity}")

    library = page.locator(".data-library-list")
    library_header = page.locator(".data-library-heading")
    if library_header.count() != 1 or "Saved Test Data" not in library_header.inner_text():
        raise RuntimeError("Modeling Data Library is missing its Saved Test Data header")
    if not re.fullmatch(r"3 exact revisions?", library_header.locator("span").inner_text().strip()):
        raise RuntimeError("Modeling Data Library count is not an exact-revision count")
    if page.get_by_text(re.compile(r"Test Data records available", re.IGNORECASE)).count():
        raise RuntimeError("retired Test Data records-available paragraph is still visible")
    library_box = _bounding_box_edges(library.bounding_box())
    if library_box is None or library.get_attribute("tabindex") != "0":
        raise RuntimeError("Modeling Data Library is not a local keyboard-focusable region")
    library_metrics = library.evaluate(
        "element => ({clientHeight: element.clientHeight, scrollHeight: element.scrollHeight})"
    )
    if library_metrics["scrollHeight"] > library_metrics["clientHeight"] + 1:
        raise RuntimeError(f"three-row Modeling Data Library must fit its local list: {library_metrics}")
    ribbon_box = _bounding_box_edges(page.locator(".modeling-data-ribbon-panel").bounding_box())
    divider_box = _bounding_box_edges(page.locator("#modeling-data-ribbon-plot-divider").bounding_box())
    if ribbon_box is None or divider_box is None:
        raise RuntimeError("Modeling Data ribbon/divider geometry is unavailable")
    if abs(ribbon_box["height"] - NORMAL_COMPACT_DATA_RIBBON_HEIGHT) > 1:
        raise RuntimeError(
            "normal compact Modeling Data ribbon height drifted from the "
            f"{NORMAL_COMPACT_DATA_RIBBON_HEIGHT}px contract at {width}x{height}: "
            f"{ribbon_box['height']}px"
        )
    for index in range(library.locator(".data-library-row").count()):
        row = library.locator(".data-library-row").nth(index)
        row_box = _bounding_box_edges(row.bounding_box())
        if row_box is None or row_box["top"] < library_box["top"] - 1 or row_box["bottom"] > library_box["bottom"] + 1 or row_box["top"] < ribbon_box["top"] - 1 or row_box["bottom"] > divider_box["top"] + 1:
            raise RuntimeError(f"Modeling Data Library row crosses its pane/divider at {width}x{height}: row={row_box}, list={library_box}, ribbon={ribbon_box}, divider={divider_box}")
    if library.evaluate("element => element.scrollWidth > element.clientWidth + 1"):
        raise RuntimeError("Modeling Data Library exposes page-horizontal overflow")

    axis_labels = [(text or "").strip() for text in page.locator(".persistent-modeling-plot .chart-axis-label").all_text_contents()]
    if not any(label.startswith("Engineering strain") for label in axis_labels):
        raise RuntimeError(f"engineering strain axis title is missing at {width}x{height}: {axis_labels}")
    if not any(label.startswith("Engineering stress") for label in axis_labels):
        raise RuntimeError(f"engineering stress axis title is missing at {width}x{height}: {axis_labels}")
    negative_ticks = [(text or "").strip() for text in page.locator(".persistent-modeling-plot .chart-tick").all_text_contents() if (text or "").strip().startswith("-")]
    if negative_ticks:
        raise RuntimeError(f"non-negative tensile Data plot exposed negative ticks at {width}x{height}: {negative_ticks}")

    workspace = page.locator(".modeling-data-workspace-bounded")
    workspace_box = _bounding_box_edges(workspace.bounding_box())
    plot_box = _bounding_box_edges(page.locator(".persistent-modeling-plot").bounding_box())
    if workspace_box is None or plot_box is None:
        raise RuntimeError("bounded Modeling Data workspace geometry is unavailable")
    if width >= 1920 and workspace_box["height"] > 879:
        raise RuntimeError(f"wide Modeling Data workspace height escaped its cap: {workspace_box}")
    if width >= 2560 and plot_box["height"] > 711:
        raise RuntimeError(f"wide Modeling Data graph remains too tall: {plot_box}")


def _assert_local_initial_controls(page: Page) -> None:
    controls = [
        page.locator('select[name="local-test-run"]'),
        page.locator('input[name="local-test-data-file"]'),
        page.get_by_role("button", name="Inspect source", exact=True),
    ]
    boxes = []
    for control in controls:
        control.wait_for(state="visible", timeout=30_000)
        box = _bounding_box_edges(control.bounding_box())
        if box is None:
            raise RuntimeError("Local file initial control has no measurable box")
        metrics = control.evaluate(
            """element => { const style = getComputedStyle(element); const box = element.getBoundingClientRect();
              return { height: box.height, fontSize: parseFloat(style.fontSize), boxSizing: style.boxSizing,
                top: box.top, bottom: box.bottom, cursor: style.cursor }; }"""
        )
        if abs(metrics["height"] - 28) > 1 or metrics["fontSize"] != 13 or metrics["boxSizing"] != "border-box":
            raise RuntimeError(f"Local initial control geometry drifted: {metrics}")
        boxes.append(box)
    if max(box["top"] for box in boxes) - min(box["top"] for box in boxes) > 1 or max(box["bottom"] for box in boxes) - min(box["bottom"] for box in boxes) > 1:
        raise RuntimeError(f"Local initial controls are not edge-aligned: {boxes}")
    file_button = controls[1].evaluate(
        """element => { const style = getComputedStyle(element, '::file-selector-button');
          return { height: parseFloat(style.height), marginTop: parseFloat(style.marginTop), marginBottom: parseFloat(style.marginBottom) }; }"""
    )
    if abs(file_button["height"] - 26) > 1 or file_button["marginTop"] != 0 or file_button["marginBottom"] != 0:
        raise RuntimeError(f"native file selector button is outside its 28px control: {file_button}")


def _prepare_modeling(page: Page, base_url: str) -> None:
    page.goto(f"{base_url}/modeling?stage=data&family=metal")
    _wait_for_modeling_data_surface(page)
    library_rows = page.locator(".data-library-list .data-library-row")
    library_rows.first.wait_for(timeout=30_000)
    if library_rows.count() != 3:
        raise RuntimeError(f"expected exactly 3 governed Test Data Library rows, got {library_rows.count()}")
    library_box = _bounding_box_edges(page.locator(".data-library-list").bounding_box())
    if library_box is None or page.locator(".data-library-list").get_attribute("tabindex") != "0":
        raise RuntimeError("Test Data Library must expose a keyboard-focusable local scroll region")
    for index in range(library_rows.count()):
        row = library_rows.nth(index)
        row_box = _bounding_box_edges(row.bounding_box())
        if row_box is None or row_box["top"] < library_box["top"] - 1 or row_box["bottom"] > library_box["bottom"] + 1:
            raise RuntimeError(
                f"Test Data Library row {index + 1} is clipped in the normal state: "
                f"row={row_box}, list={library_box}"
            )
    # Use the real Library rows so every selected curve has an exact server
    # revision, rather than manufacturing a capture-only document identity.
    for index in range(3):
        library_rows.nth(index).click()
        _wait_for_exact_document_load_settled(page)
        _wait_for_data_session_counts(page, refs=index + 1, included=index + 1, visible=index + 1)
    advanced_contract = page.locator("details.modeling-data-advanced")
    if not advanced_contract.get_attribute("open"):
        advanced_contract.locator(":scope > summary").click()
    profile = page.get_by_role("combobox", name="Saved Mapping Profile")
    profile.wait_for(timeout=30_000)
    page.wait_for_function(
        """() => (document.querySelector('select[aria-label=\"Saved Mapping Profile\"]')?.options.length ?? 0) >= 2""",
        timeout=30_000,
    )
    if profile.locator("option").count() < 2:
        raise RuntimeError("no saved Mapping Profile is available for Modeling Data capture")
    profile.select_option(index=1)
    page.wait_for_function(
        """() => Boolean(document.querySelector('select[aria-label="Saved Mapping Profile"]')?.value)""",
        timeout=30_000,
    )
    advanced_contract.locator(":scope > summary").click()
    rail = page.locator(".modeling-workspace-rail")
    checkboxes = rail.locator(".curve-include-toggle input")
    checkboxes.first.wait_for(timeout=30_000)
    if checkboxes.count() != 3:
        raise RuntimeError(f"expected exactly 3 Include controls, got {checkboxes.count()}")
    for index in range(3):
        checkbox = checkboxes.nth(index)
        if not checkbox.is_checked():
            checkbox.check()
    page.wait_for_function(
        "() => document.querySelectorAll('.modeling-workspace-rail .curve-include-toggle input:checked').length === 3",
        timeout=30_000,
    )
    checkboxes.nth(0).uncheck()
    page.wait_for_function(
        "() => document.querySelectorAll('.modeling-workspace-rail .curve-include-toggle input:checked').length === 2",
        timeout=30_000,
    )
    visibility = rail.locator(".curve-visibility-toggle")
    if visibility.count() != 3:
        raise RuntimeError(f"expected exactly 3 Show controls, got {visibility.count()}")
    for index in range(3):
        button = visibility.nth(index)
        if button.get_attribute("aria-pressed") != "true":
            button.click()
    page.wait_for_function(
        "() => [...document.querySelectorAll('.modeling-workspace-rail .curve-visibility-toggle')].every(button => button.getAttribute('aria-pressed') === 'true')",
        timeout=30_000,
    )
    _wait_for_data_plot(page)
    _wait_for_settled(page)

    _wait_for_modeling_data_ribbon(page)
    viewport_size = page.viewport_size
    if viewport_size is None:
        raise RuntimeError("Modeling Data capture lost its viewport size")
    _assert_modeling_data_surface(page, viewport_size["width"], viewport_size["height"])
    before_reload = _data_session_snapshot(page)
    if len(_session_list(before_reload, "selectedTestDataRefs")) != 3:
        raise RuntimeError(f"expected 3 selected exact refs before reload, got {before_reload}")
    if len(_session_list(before_reload, "selectedDocumentIds")) != 2:
        raise RuntimeError(f"expected exactly 2 included Test Data ids before reload, got {before_reload}")
    if len(_session_list(before_reload, "visibleTestDataKeys")) != 3:
        raise RuntimeError(f"expected 3 visible exact refs before reload, got {before_reload}")
    # Reload through the actual route and require the selected exact rows to
    # remain included. This catches the old id-only/current-head regression.
    page.reload()
    _wait_for_modeling_data_surface(page)
    page.locator(".data-library-list .data-library-row").first.wait_for(timeout=30_000)
    page.wait_for_function(
        "() => document.querySelectorAll('.modeling-workspace-rail .curve-include-toggle input:checked').length === 2",
        timeout=30_000,
    )
    page.wait_for_function(
        """() => document.querySelectorAll('.modeling-workspace-rail .curve-visibility-toggle[aria-pressed=\"true\"]').length === 3""",
        timeout=30_000,
    )
    _wait_for_data_plot(page)
    after_reload = _data_session_snapshot(page)
    if after_reload != before_reload:
        raise RuntimeError(f"exact Modeling Data selection changed across reload: before={before_reload}, after={after_reload}")
    if page.locator(".modeling-workspace-rail .curve-include-toggle input:checked").count() != 2:
        raise RuntimeError("reload did not preserve exactly 2 included Test Data records")
    if page.locator('.modeling-workspace-rail .curve-visibility-toggle[aria-pressed="true"]').count() != 3:
        raise RuntimeError("reload did not preserve all 3 visible Test Data records")
    _wait_for_settled(page)


def _prepare_modeling_process(page: Page, base_url: str) -> None:
    """Prepare Process on the exact Specimen 01 source and session pins."""
    _prepare_modeling(page, base_url)
    # _prepare_modeling intentionally leaves the page on the Data stage. Pick
    # the exact source there before navigating to Process; a Process-scoped
    # locator would not exist yet and could silently select an unrelated row.
    data_rail = page.locator(
        ".modeling-data-workspace-bounded .modeling-data-curve-tree"
    )
    data_rail.wait_for(state="visible", timeout=30_000)
    data_rows = data_rail.locator(".curve-row-label")
    exact_rows = (
        data_rows
        .filter(has=page.locator("strong").filter(has_text="Specimen 01"))
        .filter(
            has=page.locator(".curve-secondary-identity").filter(
                has_text="Session revision r1"
            )
        )
    )
    if exact_rows.count() != 1:
        raise RuntimeError(
            "Data capture must expose exactly one visible Specimen 01 / "
            f"Session revision r1 row, got {exact_rows.count()}"
        )
    exact_row = exact_rows.first
    exact_row.wait_for(state="visible", timeout=30_000)
    data_identity = exact_row.evaluate(
        """element => {
          const primary = element.querySelector(':scope > span > strong');
          const secondary = element.querySelector(
            ':scope > span > .curve-secondary-identity'
          );
          return {
            primary: primary?.textContent?.trim() ?? '',
            secondary: secondary?.textContent?.trim() ?? '',
            primaryVisible: Boolean(primary && primary.getClientRects().length),
            secondaryVisible: Boolean(secondary && secondary.getClientRects().length),
          };
        }"""
    )
    if (
        not isinstance(data_identity, dict)
        or data_identity.get("primary") != "Specimen 01"
        or data_identity.get("secondary") != "Session revision r1"
        or data_identity.get("primaryVisible") is not True
        or data_identity.get("secondaryVisible") is not True
    ):
        raise RuntimeError(
            "Data capture selected a row without the exact visible Specimen 01 / "
            f"Session revision r1 identity: {data_identity}"
        )
    exact_row.click()
    _wait_for_exact_document_load_settled(page)
    page.wait_for_function(
        """expected => {
          const raw = window.sessionStorage.getItem('cmp.modeling.recent-session.v4');
          if (!raw) return false;
          const session = JSON.parse(raw);
          const focused = session.testData || {};
          const workspace = session.workspace || {};
          return focused.label === expected.label
            && focused.revisionNo === 1
            && Array.isArray(workspace.selectedTestDataRefs)
            && workspace.selectedTestDataRefs.length === 3
            && Array.isArray(workspace.selectedDocumentIds)
            && workspace.selectedDocumentIds.length === 2
            && Array.isArray(workspace.visibleTestDataKeys)
            && workspace.visibleTestDataKeys.length === 3;
        }""",
        arg={"label": PROCESS_SOURCE_DOCUMENT_KEY},
        timeout=30_000,
    )
    session = _modeling_session(page)
    focused = session.get("testData")
    workspace = session.get("workspace")
    mapping = session.get("mappingProfile")
    if not isinstance(focused, dict) or focused.get("label") != PROCESS_SOURCE_DOCUMENT_KEY or focused.get("revisionNo") != 1:
        raise RuntimeError(f"Process capture did not focus exact Specimen 01 r1: {focused}")
    if not isinstance(workspace, dict):
        raise RuntimeError("Process capture session has no workspace state")
    refs = workspace.get("selectedTestDataRefs")
    if not isinstance(refs, list) or len(refs) != 3:
        raise RuntimeError(f"Process capture must retain three exact Test Data refs: {workspace}")
    focused_ref = next(
        (
            ref for ref in refs
            if isinstance(ref, dict)
            and ref.get("id") == focused.get("id")
            and ref.get("revisionId") == focused.get("revisionId")
            and ref.get("label") == PROCESS_SOURCE_DOCUMENT_KEY
            and ref.get("revisionNo") == 1
        ),
        None,
    )
    if focused_ref is None:
        raise RuntimeError(f"Process capture focused ref is not the exact Specimen 01 r1 pin: {refs}")
    if len(workspace.get("selectedDocumentIds", [])) != 2 or len(workspace.get("visibleTestDataKeys", [])) != 3:
        raise RuntimeError(f"Process capture must retain Include 2 and Show 3: {workspace}")
    if (
        not isinstance(mapping, dict)
        or mapping.get("label") != "CMP demo tensile JSON mapping"
        or not str(mapping.get("id") or "").strip()
        or not str(mapping.get("revisionId") or "").strip()
        or mapping.get("revisionNo") != 1
    ):
        raise RuntimeError(f"Process capture did not retain the exact Mapping Profile r1 session ref: {mapping}")
    _open_modeling_stage(page, "process")
    page.wait_for_url(re.compile(r"stage=process"), timeout=30_000)
    page.locator(".modeling-work-title strong").get_by_text(
        STAGE_HEADINGS["process"], exact=True
    ).wait_for(timeout=30_000)
    _wait_modeling_process_panel(page)
    source = page.locator(".process-band-source")
    source.wait_for(state="visible", timeout=30_000)
    if source.inner_text().strip() != PROCESS_SOURCE_VISIBLE_IDENTITY:
        raise RuntimeError(f"Process panel source drifted from exact Specimen 01 r1: {source.inner_text()!r}")
    preview = page.get_by_role("button", name="Preview changes", exact=True)
    preview.wait_for(state="visible", timeout=30_000)
    if preview.is_disabled():
        raise RuntimeError("Process capture settled with Preview changes disabled")


def _list_processing_outputs(page: Page, base_url: str) -> list[dict[str, object]]:
    """List immutable outputs through the capture page's authenticated session."""
    payload = page.evaluate(
        """async ({ baseUrl }) => {
          const config = JSON.parse(
            window.localStorage.getItem("cmp.material-platform.api-config") || "{}"
          );
          const response = await fetch(`${baseUrl}/api/v1/processing-outputs`, {
            headers: {
              "Accept": "application/json",
              "Authorization": `Bearer ${config.accessToken}`,
            },
          });
          if (!response.ok) throw new Error(`cannot list Processing Outputs: ${response.status}`);
          return await response.json();
        }""",
        {"baseUrl": base_url},
    )
    if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
        raise RuntimeError(f"Processing Output list has an unexpected shape: {payload!r}")
    items = payload["items"]
    if any(not isinstance(item, dict) for item in items):
        raise RuntimeError("Processing Output list contains a non-object item")
    return [item for item in items if isinstance(item, dict)]


def _has_processing_output_revision(
    item: dict[str, object], output_id: object, revision_id: object
) -> bool:
    if item.get("processing_output_id") != output_id:
        return False
    revision = item.get("current_revision")
    return isinstance(revision, dict) and revision.get("id") == revision_id


def _process_session_pins(page: Page) -> tuple[dict[str, object], dict[str, object]]:
    session = _modeling_session(page)
    source = session.get("testData")
    profile = session.get("mappingProfile")
    if not isinstance(source, dict) or not isinstance(profile, dict):
        raise RuntimeError(f"Process capture session is missing exact source/profile pins: {session!r}")
    for name, pin in (("source", source), ("profile", profile)):
        if not all(isinstance(pin.get(key), str) and pin.get(key) for key in ("id", "revisionId")):
            raise RuntimeError(f"Process capture {name} pin is not an exact id/revision pair: {pin!r}")
    return source, profile


def _is_fit_method_id(method_id: object) -> bool:
    value = str(method_id or "")
    return any(token in value for token in ("hardening_fit", "prony_fit", "fit_compare"))


def _is_non_fit_process_output(output: dict[str, object]) -> bool:
    if output.get("fit_decision") is not None:
        return False
    steps = output.get("steps")
    if not isinstance(steps, list):
        raise RuntimeError(f"Process output has no ordered steps: {output.get('processing_output_id')!r}")
    for step in steps:
        if not isinstance(step, dict):
            raise RuntimeError(f"Process output contains a malformed step: {output.get('processing_output_id')!r}")
        if _is_fit_method_id(step.get("method_id")):
            return False
    return True


def _matching_process_outputs(
    outputs: list[dict[str, object]],
    source: dict[str, object],
    profile: dict[str, object],
) -> list[dict[str, object]]:
    source_id = source["id"]
    source_revision = source["revisionId"]
    profile_id = profile["id"]
    profile_revision = profile["revisionId"]
    matching: list[dict[str, object]] = []
    for output in outputs:
        output_source = output.get("source_document")
        output_profile = output.get("mapping_profile")
        if not isinstance(output_source, dict) or not isinstance(output_profile, dict):
            continue
        if (
            output_source.get("aggregate_id") == source_id
            and output_source.get("revision_id") == source_revision
            and output_profile.get("aggregate_id") == profile_id
            and output_profile.get("revision_id") == profile_revision
            and _is_non_fit_process_output(output)
        ):
            matching.append(output)
    return matching


_PROCESS_CAPTURE_LABELS = frozenset(
    {
        "Robust elastic",
        "Chord elastic",
        "Elastic window 0.0005-0.0025",
    }
)


def _as_float(value: object, default: float = 0.0) -> float:
    """Read a browser-measured scalar without laundering arbitrary objects."""
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return default
    return default


def _matching_capture_process_outputs(
    outputs: list[dict[str, object]],
    source: dict[str, object],
    profile: dict[str, object],
) -> list[dict[str, object]]:
    """Keep only the exact Process siblings owned by this capture journey."""

    return [
        output
        for output in _matching_process_outputs(outputs, source, profile)
        if output.get("label") in _PROCESS_CAPTURE_LABELS
    ]


def _filter_capture_process_output_list(
    page: Page,
    source: dict[str, object],
    profile: dict[str, object],
) -> None:
    """Keep Fit-source outputs out of the Process sibling disclosure during capture."""

    expected_source = {
        "aggregate_id": source["id"],
        "revision_id": source["revisionId"],
    }
    expected_profile = {
        "aggregate_id": profile["id"],
        "revision_id": profile["revisionId"],
    }

    def route_outputs(route: Route) -> None:
        if route.request.method != "GET":
            route.continue_()
            return
        response = route.fetch()
        payload = response.json()
        if isinstance(payload, dict) and isinstance(payload.get("items"), list):
            payload["items"] = [
                item
                for item in payload["items"]
                if isinstance(item, dict)
                and item.get("label") in _PROCESS_CAPTURE_LABELS
                and item.get("source_document") == expected_source
                and item.get("mapping_profile") == expected_profile
            ]
        route.fulfill(response=response, json=payload)

    page.route("**/api/v1/processing-outputs", route_outputs)


def _assert_no_mis_pinned_capture_labels(
    outputs: list[dict[str, object]],
    source: dict[str, object],
    profile: dict[str, object],
) -> None:
    """Reject capture-named outputs that belong to another exact input/profile."""
    expected_pins = {
        "source_document": {
            "aggregate_id": source["id"],
            "revision_id": source["revisionId"],
        },
        "mapping_profile": {
            "aggregate_id": profile["id"],
            "revision_id": profile["revisionId"],
        },
    }
    for output in outputs:
        if output.get("label") not in {
            "Robust elastic",
            "Chord elastic",
            "Elastic window 0.0005-0.0025",
        }:
            continue
        if not _is_non_fit_process_output(output):
            raise RuntimeError(
                f"Capture-named Process output is Fit or malformed: {output.get('processing_output_id')!r}"
            )
        if (
            output.get("source_document") != expected_pins["source_document"]
            or output.get("mapping_profile") != expected_pins["mapping_profile"]
        ):
            raise RuntimeError(
                f"Capture-named Process output has wrong exact pins: {output.get('processing_output_id')!r}"
            )


def _assert_process_output_configuration(
    output: dict[str, object],
    source: dict[str, object],
    profile: dict[str, object],
    *,
    expected_label: str,
    expected_method: str,
    expected_minimum: float,
    expected_maximum: float,
) -> None:
    output_id = output.get("processing_output_id")
    revision = output.get("current_revision")
    output_source = output.get("source_document")
    output_profile = output.get("mapping_profile")
    if not isinstance(output_id, str) or not output_id:
        raise RuntimeError(f"Saved Process output has no stable identity: {output!r}")
    if (
        not isinstance(revision, dict)
        or revision.get("revision_no") != 1
        or not isinstance(revision.get("id"), str)
        or not revision.get("id")
    ):
        raise RuntimeError(f"Saved Process output is not exact immutable r1: {output_id!r} {revision!r}")
    if output.get("fit_decision") is not None or not _is_non_fit_process_output(output):
        raise RuntimeError(f"Saved Process sibling must be non-Fit: {output_id!r}")
    if output_source != {
        "aggregate_id": source["id"],
        "revision_id": source["revisionId"],
    } or output_profile != {
        "aggregate_id": profile["id"],
        "revision_id": profile["revisionId"],
    }:
        raise RuntimeError(f"Saved Process sibling has wrong exact pins: {output_id!r}")
    if output.get("label") != expected_label:
        raise RuntimeError(
            f"Saved Process sibling label drifted: expected {expected_label!r}, got {output.get('label')!r}"
        )
    steps = output.get("steps")
    if not isinstance(steps, list):
        raise RuntimeError(f"Saved Process sibling has no ordered steps: {output_id!r}")
    modulus_steps = [
        step for step in steps
        if isinstance(step, dict) and step.get("method_id") == "metal.elastic_modulus"
    ]
    if len(modulus_steps) != 1:
        raise RuntimeError(f"Saved Process sibling must have one elastic modulus step: {output_id!r}")
    modulus = modulus_steps[0]
    if modulus.get("method_version") != "1.0.0" or not isinstance(modulus.get("options"), dict):
        raise RuntimeError(f"Saved Process sibling elastic step identity drifted: {output_id!r}")
    options = modulus["options"]
    if options.get("method") != expected_method:
        raise RuntimeError(
            f"Saved Process sibling method drifted: expected {expected_method!r}, got {options.get('method')!r}"
        )
    if (
        isinstance(options.get("minimum_strain"), bool)
        or not isinstance(options.get("minimum_strain"), (int, float))
        or float(options["minimum_strain"]) != expected_minimum
        or isinstance(options.get("maximum_strain"), bool)
        or not isinstance(options.get("maximum_strain"), (int, float))
        or float(options["maximum_strain"]) != expected_maximum
    ):
        raise RuntimeError(f"Saved Process sibling range drifted: {output_id!r} {options!r}")


def _assert_resumable_modeling_process_outputs(
    outputs: list[dict[str, object]],
    source: dict[str, object],
    profile: dict[str, object],
) -> dict[str, dict[str, object]]:
    """Validate the one exact three-output state produced by the interrupted capture."""
    if len(outputs) != 3:
        raise RuntimeError(
            "Modeling Process resume requires exactly three matching outputs: "
            f"got {len(outputs)}"
        )
    labels = [output.get("label") for output in outputs]
    expected_labels = {
        "Robust elastic",
        "Chord elastic",
        "Elastic window 0.0005-0.0025",
    }
    if (
        any(not isinstance(label, str) for label in labels)
        or set(labels) != expected_labels
        or len(set(labels)) != 3
    ):
        raise RuntimeError(f"Interrupted Process outputs have wrong exact labels: {labels!r}")
    output_ids = [output.get("processing_output_id") for output in outputs]
    if (
        any(not isinstance(output_id, str) or not output_id for output_id in output_ids)
        or len({output_id for output_id in output_ids if isinstance(output_id, str)}) != 3
    ):
        raise RuntimeError(
            "Interrupted Process outputs have duplicate or missing identities: "
            f"{output_ids!r}"
        )
    revision_ids: list[object] = []
    for output in outputs:
        revision = output.get("current_revision")
        revision_ids.append(revision.get("id") if isinstance(revision, dict) else None)
    if (
        any(not isinstance(revision_id, str) or not revision_id for revision_id in revision_ids)
        or len({revision_id for revision_id in revision_ids if isinstance(revision_id, str)}) != 3
    ):
        raise RuntimeError(
            "Interrupted Process outputs have duplicate or missing revision identities: "
            f"{revision_ids!r}"
        )
    configurations: dict[str, dict[str, str | float]] = {
        "Robust elastic": {
            "expected_method": "robust_huber",
            "expected_minimum": 0.0002,
            "expected_maximum": 0.002,
        },
        "Chord elastic": {
            "expected_method": "chord",
            "expected_minimum": 0.001,
            "expected_maximum": 0.003,
        },
        "Elastic window 0.0005-0.0025": {
            "expected_method": "robust_huber",
            "expected_minimum": 0.0005,
            "expected_maximum": 0.0025,
        },
    }
    by_label: dict[str, dict[str, object]] = {}
    for output in outputs:
        label = output.get("label")
        if not isinstance(label, str):
            raise RuntimeError(f"Interrupted Process output label is not text: {output!r}")
        expected = configurations[label]
        _assert_process_output_configuration(
            output,
            source,
            profile,
            expected_label=label,
            expected_method=str(expected["expected_method"]),
            expected_minimum=float(expected["expected_minimum"]),
            expected_maximum=float(expected["expected_maximum"]),
        )
        by_label[label] = output
    return by_label


def _assert_modeling_process_saved_rows(
    page: Page,
    *,
    require_current_and_history: bool = False,
) -> list[str]:
    details = page.locator("details.process-saved-results")
    details.wait_for(state="visible", timeout=30_000)
    if details.get_attribute("open") is None:
        details.locator(":scope > summary").click()
    rows = details.locator(".process-comparison-row")
    rows.nth(1).wait_for(timeout=30_000)
    for scalar in ("210.0 GPa", "120.0 GPa"):
        rows.filter(has_text=scalar).first.wait_for(timeout=30_000)
    row_text = rows.all_inner_texts()
    if len(row_text) != 2:
        raise RuntimeError(f"Saved Process comparison must contain exactly two rows: {row_text}")
    for label, method, range_text, scalar in (
        ("Robust elastic", "Auto robust", "0.0002–0.002", "210.0 GPa"),
        ("Chord elastic", "Chord", "0.001–0.003", "120.0 GPa"),
    ):
        matching = [text for text in row_text if label in text]
        if (
            len(matching) != 1
            or method not in matching[0]
            or range_text not in matching[0]
            or scalar not in matching[0]
            or "r1" not in matching[0]
        ):
            raise RuntimeError(f"Saved Process row is missing exact {label} evidence: {row_text}")
    if require_current_and_history:
        robust = next(text for text in row_text if "Robust elastic" in text)
        chord = next(text for text in row_text if "Chord elastic" in text)
        if "history" not in robust or "current" not in chord:
            raise RuntimeError(f"Saved Process current/history pointers drifted: {row_text}")
    return row_text


def _is_modeling_process_saved_result_response(response: object) -> bool:
    """Identify one lazy saved-result content response from the Process disclosure."""
    request = getattr(response, "request", None)
    path = urlsplit(str(getattr(response, "url", ""))).path.rstrip("/")
    return (
        str(getattr(request, "method", "")).upper() == "GET"
        and re.fullmatch(r"/api/v1/processing-outputs/[^/]+/content", path) is not None
    )


def _wait_for_modeling_process_saved_rows_refresh(page: Page, summary: Locator) -> None:
    """Wait for the toggle-triggered content requests and their settled render."""
    content_responses: dict[str, object] = {}

    def record_response(response: object) -> None:
        if _is_modeling_process_saved_result_response(response):
            content_responses.setdefault(str(getattr(response, "url", "")), response)

    page.on("response", record_response)
    try:
        # The native disclosure toggle starts all three lazy content requests.
        # Require the first response before observing the settled DOM so a cached
        # ready render from before the toggle cannot satisfy the state check.
        with page.expect_response(
            _is_modeling_process_saved_result_response,
            timeout=30_000,
        ) as first_response_info:
            summary.click()
        first_response = first_response_info.value
        record_response(first_response)
        # The disclosure starts all three requests together.  Polling the real
        # disclosure DOM after the first response both proves that the render
        # consumed the responses and pumps Playwright's event loop so the
        # response listener observes every remaining callback.  A second
        # response wait would reintroduce the missed-event race.
        page.wait_for_function(
            """() => {
              const details = document.querySelector('details.process-saved-results');
              const rows = [...document.querySelectorAll(
                'details.process-saved-results .process-comparison-row'
              )];
              return details instanceof HTMLDetailsElement
                && details.open
                && rows.length === 3
                && rows.every(row => !(row.textContent ?? '').includes('Loading saved result…'));
            }""",
            timeout=30_000,
        )
        if len(content_responses) != 3:
            raise RuntimeError(
                "Saved Process content refresh expected exactly three unique content "
                f"responses, got {len(content_responses)}: {sorted(content_responses)!r}"
            )
        responses = list(content_responses.values())
        failed = []
        for response in responses:
            status = getattr(response, "status", None)
            if (
                not bool(getattr(response, "ok", False))
                or not isinstance(status, int)
                or not 200 <= status < 300
            ):
                failed.append(response)
        if failed:
            statuses = [getattr(response, "status", "unknown") for response in failed]
            raise RuntimeError(
                "Saved Process content refresh returned a non-2xx response: "
                f"{statuses!r}"
            )
        # Keep the two-frame render boundary after response validation and
        # before the scalar/current-history assertions in the caller.
        page.evaluate(
            """async () => {
              await new Promise(requestAnimationFrame);
              await new Promise(requestAnimationFrame);
            }"""
        )
    finally:
        page.remove_listener("response", record_response)


def _assert_modeling_process_saved_rows_three(
    page: Page,
    *,
    current_label: str,
) -> list[str]:
    """Verify the primary journey's current result plus two immutable siblings."""
    details = page.locator("details.process-saved-results")
    details.wait_for(state="visible", timeout=30_000)
    rows = details.locator(".process-comparison-row")
    disclosure_was_open = details.get_attribute("open") is not None
    if not disclosure_was_open:
        _wait_for_modeling_process_saved_rows_refresh(
            page,
            details.locator(":scope > summary"),
        )
    else:
        page.wait_for_function(
            """() => {
              const rows = [...document.querySelectorAll(
                'details.process-saved-results .process-comparison-row'
              )];
              return rows.length === 3
                && rows.every(row => !(row.textContent ?? '').includes('Loading saved result…'));
            }""",
            timeout=30_000,
        )
    row_text = rows.all_inner_texts()
    if len(row_text) != 3:
        raise RuntimeError(f"Saved Process comparison must contain exactly three rows: {row_text}")
    for label, scalar in (
        ("Robust elastic", "210.0 GPa"),
        ("Chord elastic", "120.0 GPa"),
        (current_label, "210.0 GPa"),
    ):
        matching = [text for text in row_text if label in text]
        if len(matching) != 1 or scalar not in matching[0] or "r1" not in matching[0]:
            raise RuntimeError(f"Saved Process row is missing exact {label} evidence: {row_text}")
    current_rows = [text for text in row_text if "current" in text]
    if len(current_rows) != 1 or current_label not in current_rows[0]:
        raise RuntimeError(f"Saved Process current pointer drifted: {row_text}")
    if sum("history" in text for text in row_text) != 2:
        raise RuntimeError(f"Saved Process history rows drifted: {row_text}")
    return row_text


def _assert_modeling_process_table_geometry(page: Page) -> None:
    """Verify semantic Saved-results columns and row actions stay reachable."""
    layout = page.evaluate(
        """() => {
          const table = document.querySelector('details.process-saved-results[open] .process-comparison-table');
          if (!table) return { present: false };
          const details = table.closest('details');
          const ribbon = document.querySelector('.modeling-task-ribbon');
          const plot = document.querySelector('.persistent-modeling-plot');
          const rect = node => node?.getBoundingClientRect() ?? null;
          const inside = (child, parent) => {
            const childBox = rect(child);
            const parentBox = rect(parent);
            return Boolean(childBox && parentBox
              && childBox.left >= parentBox.left - 1
              && childBox.right <= parentBox.right + 1
              && childBox.top >= parentBox.top - 1
              && childBox.bottom <= parentBox.bottom + 1);
          };
          const hitWithin = (owner, box) => {
            if (!box || box.width <= 0 || box.height <= 0) return false;
            const hit = document.elementFromPoint(box.left + box.width / 2, box.top + box.height / 2);
            return hit instanceof Element && (hit === owner || owner.contains(hit));
          };
          const rows = [...table.querySelectorAll('tbody tr')];
          const headers = [...table.querySelectorAll('thead th')].map(header => header.textContent?.trim() || '');
          const rowChecks = rows.map(row => {
            const cells = [...row.querySelectorAll(':scope > td')];
            const cellBoxes = cells.map(rect);
            const action = cells.at(-1)?.querySelector('button');
            const actionBox = rect(action);
            const horizontalOrder = cellBoxes.every((box, index) => !index || !box || !cellBoxes[index - 1] || box.left >= cellBoxes[index - 1].right - 1);
            return {
              cellCount: cells.length,
              rowContained: inside(row, table) && inside(row, details) && inside(row, ribbon),
              rowAbovePlot: Boolean(plot && rect(row)?.bottom <= rect(plot)?.top + 1),
              horizontalOrder,
              actionVisible: Boolean(actionBox && actionBox.width > 0 && actionBox.height > 0),
              actionTopmost: Boolean(action && hitWithin(action, actionBox)),
              actionLabel: action?.textContent?.trim() || '',
            };
          });
          return {
            present: true,
            tableContained: inside(table, details) && inside(table, ribbon),
            tableAbovePlot: Boolean(plot && rect(table)?.bottom <= rect(plot)?.top + 1),
            headers,
            rowChecks,
          };
        }"""
    )
    if not isinstance(layout, dict) or not layout.get("present"):
        return
    expected_headers = ["Label", "Method", "Range", "Result", "Revision", "State", "Action"]
    if (
        layout.get("headers") != expected_headers
        or not layout.get("tableContained")
        or not layout.get("tableAbovePlot")
        or not isinstance(layout.get("rowChecks"), list)
        or not layout["rowChecks"]
    ):
        raise RuntimeError(f"Saved Process semantic table is not contained/reachable: {layout!r}")
    for row in layout["rowChecks"]:
        if (
            not isinstance(row, dict)
            or row.get("cellCount") != 7
            or not row.get("rowContained")
            or not row.get("rowAbovePlot")
            or not row.get("horizontalOrder")
            or row.get("actionLabel") not in {"Retry", "Use settings"}
            or not row.get("actionVisible")
            or not row.get("actionTopmost")
        ):
            raise RuntimeError(f"Saved Process semantic row/action is not reachable: {layout!r}")


def _assert_modeling_process_saved_rows_reachable(page: Page) -> None:
    """Reject Process captures where the graph paints over saved-row actions."""
    _assert_modeling_process_table_geometry(page)
    checks = page.evaluate(
        """() => {
          const rows = [...document.querySelectorAll(
            'details.process-saved-results[open] .process-comparison-row'
          )];
          const details = document.querySelector('details.process-saved-results[open]');
          const region = details?.querySelector('.process-comparison-region');
          const ribbon = document.querySelector('.modeling-task-ribbon');
          const plot = document.querySelector('.persistent-modeling-plot');
          const heading = plot?.querySelector(':scope > .section-heading');
          const toolbar = plot?.querySelector(':scope > .modeling-plot-toolbar');
          const emptyPlot = plot?.querySelector(':scope > .modeling-plot-empty');
          const rect = node => node?.getBoundingClientRect() ?? null;
          const plotBox = rect(plot);
          const visible = node => {
            const box = rect(node);
            return Boolean(box && box.width > 0 && box.height > 0);
          };
          const inside = (child, parent) => {
            const childBox = rect(child);
            const parentBox = rect(parent);
            return Boolean(
              childBox && parentBox
                && childBox.left >= parentBox.left - 1
                && childBox.right <= parentBox.right + 1
                && childBox.top >= parentBox.top - 1
                && childBox.bottom <= parentBox.bottom + 1,
            );
          };
          const hitWithin = (owner, rect) => {
            if (!rect || rect.width <= 0 || rect.height <= 0) return false;
            const hit = document.elementFromPoint(
              rect.left + rect.width / 2,
              rect.top + rect.height / 2,
            );
            return hit instanceof Element && (hit === owner || owner.contains(hit));
          };
          return rows.map((row) => {
            const rowRect = row.getBoundingClientRect();
            const action = row.querySelector('button');
            const actionRect = action?.getBoundingClientRect() ?? null;
            return {
              label: row.textContent?.trim() || '',
              rowTopmost: hitWithin(row, rowRect),
              rowContained: inside(row, region) && inside(row, details) && inside(row, ribbon),
              rowAbovePlot: Boolean(plot && rowRect.bottom <= plot.getBoundingClientRect().top + 1),
              actionLabel: action?.textContent?.trim() || '',
              actionVisible: Boolean(actionRect && actionRect.width > 0 && actionRect.height > 0),
              actionEnabled: action instanceof HTMLButtonElement && !action.disabled,
              actionTopmost: Boolean(action && hitWithin(action, actionRect)),
            };
          }).concat([{
            layout: true,
            rowCount: rows.length,
            rowsWithoutScroll: Boolean(
              region
                && region.scrollHeight <= region.clientHeight + 1
                && region.clientWidth >= region.scrollWidth - 1,
            ),
            disclosureContained: inside(details, ribbon),
            disclosureAbovePlot: Boolean(
              details && plot
                && details.getBoundingClientRect().bottom <= plot.getBoundingClientRect().top + 1,
            ),
            plotUseful: Boolean(
              visible(plot)
                && plotBox
                && plotBox.width >= 320
                && plotBox.height >= 240,
            ),
            plotHeadingVisible: visible(heading),
            plotHeadingTopmost: Boolean(heading && hitWithin(heading, rect(heading))),
            plotToolbarExists: Boolean(toolbar),
            plotToolbarVisible: visible(toolbar),
            plotToolbarTopmost: Boolean(toolbar && hitWithin(toolbar, rect(toolbar))),
            plotToolbarButtons: [...(toolbar?.querySelectorAll('button') ?? [])]
              .filter(button => ['Reset view', 'Pan', 'Select range'].includes(button.textContent?.trim() || ''))
              .map(button => ({
                label: button.textContent?.trim() || '',
                visible: visible(button),
                enabled: button instanceof HTMLButtonElement && !button.disabled,
                topmost: hitWithin(button, rect(button)),
              })),
            plotEmptyVisible: visible(emptyPlot),
            plotEmptyTopmost: Boolean(emptyPlot && hitWithin(emptyPlot, rect(emptyPlot))),
            plotEmptyContained: inside(emptyPlot, plot),
            plotEmptyMessage: emptyPlot?.querySelector(':scope > strong')?.textContent?.trim() || '',
            plotEmptyInstruction: emptyPlot?.querySelector(':scope > p')?.textContent?.trim() || '',
          }]);
        }"""
    )
    if not isinstance(checks, list) or len(checks) != 4:
        raise RuntimeError(f"Saved Process reachability check found {checks!r}")
    rows = checks[:-1]
    layout = checks[-1]
    if (
        not isinstance(layout, dict)
        or layout.get("layout") is not True
        or layout.get("rowCount") != 3
        or not layout.get("rowsWithoutScroll")
        or not layout.get("disclosureContained")
        or not layout.get("disclosureAbovePlot")
        or not layout.get("plotUseful")
        or not layout.get("plotHeadingVisible")
        or not layout.get("plotHeadingTopmost")
    ):
        raise RuntimeError(f"Saved Process disclosure or persistent plot is not contained/reachable: {checks!r}")
    if layout.get("plotToolbarExists"):
        if not layout.get("plotToolbarVisible") or not layout.get("plotToolbarTopmost"):
            raise RuntimeError(f"Saved Process plot toolbar is not visible/reachable: {checks!r}")
        toolbar_buttons = layout.get("plotToolbarButtons")
        if (
            not isinstance(toolbar_buttons, list)
            or len(toolbar_buttons) != 3
            or any(
                not isinstance(button, dict)
                or not button.get("visible")
                or not button.get("enabled")
                or not button.get("topmost")
                for button in toolbar_buttons
            )
        ):
            raise RuntimeError(f"Saved Process plot toolbar controls are not reachable: {checks!r}")
    else:
        if (
            not layout.get("plotEmptyVisible")
            or not layout.get("plotEmptyTopmost")
            or not layout.get("plotEmptyContained")
            or layout.get("plotEmptyMessage")
            != "The graph stays here while you prepare the curves."
            or layout.get("plotEmptyInstruction")
            != PROCESS_NO_PREVIEW_SAVED_INSTRUCTION
        ):
            raise RuntimeError(f"Saved Process reload plot is missing its honest no-preview state: {checks!r}")
    for check in rows:
        if (
            not isinstance(check, dict)
            or not check.get("rowTopmost")
            or not check.get("rowContained")
            or not check.get("rowAbovePlot")
            or check.get("actionLabel") != "Use settings"
            or not check.get("actionVisible")
            or not check.get("actionEnabled")
            or not check.get("actionTopmost")
        ):
            raise RuntimeError(f"Saved Process row or Use settings is occluded: {checks!r}")


def _patch_capture_processing_output_pointer(
    page: Page, output: dict[str, object]
) -> None:
    revision = output.get("current_revision")
    output_id = output.get("processing_output_id")
    if not isinstance(revision, dict) or not isinstance(output_id, str):
        raise RuntimeError(f"Cannot patch capture pointer from malformed output: {output!r}")
    pointer = {
        "id": output_id,
        "revisionId": revision.get("id"),
        "label": output.get("label"),
        "revisionNo": revision.get("revision_no"),
    }
    if not isinstance(pointer["revisionId"], str) or pointer["revisionNo"] != 1:
        raise RuntimeError(f"Cannot patch capture pointer from non-r1 output: {output!r}")
    page.evaluate(
        """pointer => {
          const key = "cmp.modeling.recent-session.v4";
          const raw = window.sessionStorage.getItem(key);
          if (!raw) throw new Error("Modeling session v4 is missing before pointer patch");
          const session = JSON.parse(raw);
          session.processingOutput = pointer;
          window.sessionStorage.setItem(key, JSON.stringify(session));
        }""",
        pointer,
    )


def _assert_capture_processing_output_pointer(
    page: Page, output: dict[str, object]
) -> None:
    """Require session state to pin the exact immutable output after recovery."""
    revision = output.get("current_revision")
    output_id = output.get("processing_output_id")
    if not isinstance(revision, dict) or not isinstance(output_id, str):
        raise RuntimeError(f"Cannot verify capture pointer from malformed output: {output!r}")
    expected = {
        "id": output_id,
        "revisionId": revision.get("id"),
        "label": output.get("label"),
        "revisionNo": revision.get("revision_no"),
    }
    pointer = page.evaluate(
        """() => {
          const raw = window.sessionStorage.getItem("cmp.modeling.recent-session.v4");
          if (!raw) throw new Error("Modeling session v4 is missing after pointer restore");
          return JSON.parse(raw).processingOutput || null;
        }"""
    )
    if pointer != expected:
        raise RuntimeError(f"Capture pointer did not restore the exact current output: {pointer!r}")


def _save_exact_fit_selection(
    page: Page,
    *,
    allow_expected_exact_restore_failure: bool = False,
) -> None:
    """Save the selected Fit output and leave the workflow on the Fit stage."""
    _open_modeling_stage(page, "fit")
    page.wait_for_url(re.compile(r"stage=fit"), timeout=30_000)
    page.locator(".modeling-work-title strong").get_by_text(
        STAGE_HEADINGS["fit"], exact=True
    ).wait_for(timeout=30_000)
    if parse_qs(urlsplit(page.url).query).get("stage") != ["fit"]:
        raise RuntimeError(f"Fit selection started on an unexpected route: {page.url}")
    show_settings = page.get_by_role("button", name="Show current-stage settings", exact=True)
    if show_settings.count():
        show_settings.click()
    trigger, _body, candidate_table = _open_fit_evidence(page)
    _assert_fit_candidate_surface(page, candidate_table)
    _select_warned_fit_candidate(candidate_table)
    page.get_by_role("textbox", name="Candidate selection reason").fill(
        "Best agreement over the measured strain range."
    )
    warning_acknowledgement = page.get_by_role(
        "checkbox", name="Acknowledge selected candidate warning"
    )
    if warning_acknowledgement.count():
        warning_acknowledgement.check()
    else:
        raise RuntimeError("Selected warned Fit candidate is missing its acknowledgement")
    _assert_fit_selected_evidence(page)
    previous_pointer = _modeling_session(page).get("processingOutput")
    save_candidate = page.get_by_role("button", name="Save fit & continue", exact=True)
    page.wait_for_function(
        """() => [...document.querySelectorAll("button")].some(
            button => button.textContent?.trim() === "Save fit & continue"
              && !button.disabled
        )""",
        timeout=30_000,
    )
    _close_fit_evidence(page, trigger)
    save_candidate.click()
    page.get_by_text(
        "New immutable Fit Output saved and current",
        exact=False,
    ).wait_for(timeout=30_000)
    if parse_qs(urlsplit(page.url).query).get("stage") != ["fit"]:
        raise RuntimeError(f"Fit save unexpectedly navigated away from Fit: {page.url}")
    page.wait_for_function(
        """() => {
          const raw = window.sessionStorage.getItem('cmp.modeling.recent-session.v4');
          if (!raw) return false;
          const pointer = JSON.parse(raw).processingOutput;
          return Boolean(
            pointer
              && typeof pointer.id === 'string'
              && pointer.id
              && typeof pointer.revisionId === 'string'
              && pointer.revisionId
          );
        }""",
        timeout=30_000,
    )
    pointer = _modeling_session(page).get("processingOutput")
    if not isinstance(pointer, dict) or not all(
        isinstance(pointer.get(key), str) and pointer.get(key)
        for key in ("id", "revisionId")
    ):
        raise RuntimeError(f"Fit save did not pin an exact session output pointer: {pointer!r}")
    if isinstance(previous_pointer, dict) and all(
        isinstance(previous_pointer.get(key), str) and previous_pointer.get(key)
        for key in ("id", "revisionId")
    ) and all(pointer.get(key) == previous_pointer.get(key) for key in ("id", "revisionId")):
        raise RuntimeError(
            f"Fit save did not advance to a new immutable output pointer: {pointer!r}"
        )
    error_banner = page.locator(".error-banner")
    if error_banner.count() and error_banner.is_visible():
        error_text = error_banner.inner_text().strip()
        if not allow_expected_exact_restore_failure or not error_text.startswith(
            EXPECTED_EXACT_FIT_RESTORE_ERROR
        ):
            raise RuntimeError(f"Fit selected-output save failed: {error_text}")


def _prepare_exact_target_preview(page: Page) -> None:
    page.get_by_role("heading", name=STAGE_HEADINGS["export"], exact=True).wait_for(timeout=30_000)
    target_heading = page.get_by_role("heading", name="Choose delivery target", exact=True)
    if not target_heading.count():
        page.get_by_role("heading", name="Prepare exact metal source", exact=True).wait_for(
            timeout=30_000
        )
        page.get_by_role(
            "checkbox",
            name="I acknowledge the selected bounded extrapolation for this reference model.",
            exact=True,
        ).check()
        page.get_by_role("textbox", name="Metal promotion reason").fill(
            "Prepare the exact selected output for synthetic non-production target preview."
        )
        page.get_by_role("button", name="Prepare exact model and Neutral", exact=True).click()
        page.wait_for_function(
            """() => [...document.querySelectorAll("h1, h2, h3")].some(
                heading => heading.textContent?.trim() === "Choose delivery target"
            ) || document.querySelector('[role="alert"]')""",
            timeout=30_000,
        )
        recovery_error = page.get_by_role("alert")
        if recovery_error.count():
            raise RuntimeError(
                f"Exact model/Neutral recovery failed: {recovery_error.inner_text().strip()}"
            )
        target_heading.wait_for(timeout=30_000)

    page.get_by_role("combobox", name="Solver target").select_option("abaqus")
    page.get_by_role("textbox", name="Native material name").fill("DP780_C1_REFERENCE")
    page.get_by_role("button", name="Generate preview", exact=True).click()
    page.wait_for_function(
        """() => document.querySelector(
            '[aria-label="Target mapping preflight"]'
        ) || document.querySelector('[role="alert"]')""",
        timeout=30_000,
    )
    preview_error = page.get_by_role("alert")
    if preview_error.count():
        raise RuntimeError(f"Exact target preview failed: {preview_error.inner_text().strip()}")
    page.get_by_role("region", name="Target mapping preflight", exact=True).wait_for(timeout=30_000)
    page.get_by_role("region", name="Native preview", exact=True).locator("pre").wait_for(
        timeout=30_000
    )
    deliver = page.get_by_role("button", name="Deliver native card", exact=True)
    deliver.wait_for(timeout=30_000)
    acknowledgement = page.get_by_role(
        "checkbox", name="Acknowledge mapped approximations", exact=True
    )
    acknowledgement.wait_for(timeout=30_000)
    acknowledgement.check()
    page.wait_for_function(
        """() => ![...document.querySelectorAll("button")].some(
          button => button.textContent?.trim() === "Deliver native card" && button.disabled
        )""",
        timeout=30_000,
    )
    if deliver.is_disabled():
        raise RuntimeError("UXC-06C2 Deliver must be enabled after its exact acknowledgement")
    deliver.click()
    page.wait_for_function(
        """() => document.querySelector('[role="alert"]')
          || [...document.querySelectorAll('[role="status"]')].some(
            element => element.textContent?.includes("Solver card delivered")
          )""",
        timeout=30_000,
    )
    delivery_error = page.get_by_role("alert")
    if delivery_error.count():
        raise RuntimeError(f"UXC-06C2 delivery failed: {delivery_error.inner_text().strip()}")
    delivery_status = page.get_by_role("status").filter(has_text="Solver card delivered")
    delivery_status.wait_for(timeout=30_000)
    if delivery_status.get_by_role("link", name="Receipt").count() != 1:
        raise RuntimeError("delivered solver card must expose its immutable receipt link")
    if page.get_by_role("button", name=re.compile(r"^Deliver\b")).count():
        raise RuntimeError("completed C2 delivery must not retain an active Deliver action")
    if page.get_by_role("button", name="Change solver target", exact=True).count() != 1:
        raise RuntimeError("completed delivery must offer an explicit target-change action")
    if page.locator(".modeling-curve-tree, .neutral-solver-export").count():
        raise RuntimeError(
            "Export must not restore the curve rail or legacy Neutral export surface"
        )
    _wait_for_settled(page)


def _capture_modeling_export_only(browser: Browser, base_url: str, output: Path) -> None:
    for width, height in VIEWPORTS:
        page = _new_page(browser, base_url, width, height)
        _prepare_fit_from_saved_process(
            page,
            base_url,
            label=f"Fit source Process result {width}x{height}",
        )
        _save_exact_fit_selection(page)
        _open_modeling_stage(page, "export")
        page.wait_for_url(re.compile(r"stage=export"), timeout=30_000)
        _prepare_exact_target_preview(page)
        _capture(
            page,
            output / f"modeling-export-{width}x{height}.png",
            width,
            height,
            focus_selector=".modeling-target-preview .ux-notice.success",
        )
        page.context.close()


def _capture_modeling(
    browser: Browser,
    base_url: str,
    output: Path,
    *,
    include_process_normals: bool = True,
) -> None:
    for width, height in (*VIEWPORTS, *WIDE_VIEWPORTS):
        page = _new_page(browser, base_url, width, height)
        _prepare_modeling(page, base_url)
        plot = page.locator(".persistent-modeling-plot svg[role=img]")
        for stage, heading in STAGE_HEADINGS.items():
            if stage == "export" and (width, height) not in VIEWPORTS:
                continue
            _open_modeling_stage(page, stage)
            page.wait_for_url(re.compile(rf"stage={stage}"), timeout=30_000)
            page.locator(".modeling-work-title strong").get_by_text(heading, exact=True).wait_for(
                timeout=30_000
            )
            if stage == "process":
                _save_process_output_for_fit(
                    page,
                    label=f"Fit source Process result {width}x{height}",
                    reason="Bind one immutable Process result as the exact Fit source.",
                )
            if stage == "fit":
                _click_modeling_fit_preview_and_wait(page)
                show_settings = page.get_by_role(
                    "button", name="Show current-stage settings", exact=True
                )
                if show_settings.count():
                    show_settings.click()
                _wait_for_settled(page)
                trigger, _body, candidate_table = _open_fit_evidence(page)
                if candidate_table.locator("tbody tr").count() != 5:
                    raise RuntimeError(
                        "Fit must expose four calculated single-law candidates "
                        "and the exact calculated preview blend"
                    )
                _assert_fit_candidate_surface(page, candidate_table)
                page.get_by_text(re.compile(r"^Preview blend · .+ · fitted domain$")).wait_for(
                    timeout=30_000
                )
                save_candidate = page.get_by_role("button", name="Save fit & continue", exact=True)
                if save_candidate.count() != 1:
                    raise RuntimeError("Fit is missing its sole top-row save action")
                if not save_candidate.is_disabled():
                    raise RuntimeError(
                        "Fit save must remain disabled before an explicit row selection"
                    )
                _select_warned_fit_candidate(candidate_table)
                page.get_by_text(re.compile(r"^Selected · .+ · fitted domain$")).wait_for(
                    timeout=30_000
                )
                parameter_table = page.get_by_role(
                    "table", name="Selected candidate parameters and bounds"
                )
                parameter_table.wait_for(timeout=30_000)
                if parameter_table.locator("tbody tr").count() < 1:
                    raise RuntimeError(
                        "Selected Fit candidate must expose parameter and bound evidence"
                    )
                selection_reason = page.get_by_role("textbox", name="Candidate selection reason")
                selection_reason.fill("Best agreement over the measured strain range.")
                warning_acknowledgement = page.get_by_role(
                    "checkbox", name="Acknowledge selected candidate warning"
                )
                if warning_acknowledgement.count():
                    warning_acknowledgement.check()
                else:
                    raise RuntimeError("Selected warned Fit candidate is missing its acknowledgement")
                _assert_fit_selected_evidence(page)
                if save_candidate.is_disabled():
                    raise RuntimeError(
                        "Fit save did not become ready after selection evidence was completed"
                    )
                _close_fit_evidence(page, trigger)
            if stage == "export":
                _prepare_exact_target_preview(page)
            plot.wait_for(timeout=30_000)
            plot_geometry = plot.evaluate(
                """svg => {
                    const horizontalAxis = [...svg.querySelectorAll(".chart-axis")]
                      .find(line => line.getAttribute("x1") !== line.getAttribute("x2"));
                    if (!horizontalAxis) return { ratio: 0, reason: "horizontal axis missing" };
                    const axisBounds = horizontalAxis.getBoundingClientRect();
                    const drawableWidth = axisBounds.width;
                    const workspace = document.querySelector(".modeling-split-workspace");
                    const plotBounds = svg.getBoundingClientRect();
                    const workspaceWidth = workspace?.getBoundingClientRect().width ?? 0;
                    return {
                      ratio: workspaceWidth ? drawableWidth / workspaceWidth : 0,
                      drawableWidth,
                      plotWidth: plotBounds.width,
                      workspaceWidth,
                    };
                }"""
            )
            drawable_ratio = float(plot_geometry["ratio"])
            if drawable_ratio < 0.72:
                raise RuntimeError(
                    f"Modeling plot drawable is only {drawable_ratio:.1%} "
                    f"of workspace for {stage} at {width}x{height}: {plot_geometry}"
                )
            if stage != "process" or include_process_normals:
                _capture(
                    page,
                    output / f"modeling-{stage}-{width}x{height}.png",
                    width,
                    height,
                    focus_selector=None,
                )
            if stage == "fit":
                _save_exact_fit_selection(page)
        page.context.close()


def _measure_process_fit(
    page: Page,
    stage: str,
    width: int,
    height: int,
    *,
    minimum_svg_height: int | None = None,
) -> dict[str, float]:
    measurement = cast(dict[str, float], page.evaluate(
        """() => {
          const box = selector => document.querySelector(selector)?.getBoundingClientRect();
          const rect = node => {
            const value = node?.getBoundingClientRect?.();
            return value && node?.getClientRects?.().length
              ? { left: value.left, right: value.right, top: value.top, bottom: value.bottom, width: value.width, height: value.height }
              : null;
          };
          const overlaps = (first, second) => Boolean(
            first && second
              && first.left < Math.max(second.right, second.left + 1)
              && Math.max(first.right, first.left + 1) > second.left
              && first.top < Math.max(second.bottom, second.top + 1)
              && Math.max(first.bottom, first.top + 1) > second.top
          );
          const segmentIntersectsRect = (first, second, target) => {
            if (!first || !second || !target) return false;
            const dx = second.x - first.x;
            const dy = second.y - first.y;
            let enter = 0;
            let leave = 1;
            const clip = (p, q) => {
              if (Math.abs(p) < 1e-9) return q >= 0;
              const ratio = q / p;
              if (p < 0) {
                if (ratio > leave) return false;
                if (ratio > enter) enter = ratio;
              } else {
                if (ratio < enter) return false;
                if (ratio < leave) leave = ratio;
              }
              return true;
            };
            return clip(-dx, first.x - target.left)
              && clip(dx, target.right - first.x)
              && clip(-dy, first.y - target.top)
              && clip(dy, target.bottom - first.y)
              && enter <= leave;
          };
          const screenPoint = (element, x, y) => {
            const matrix = element?.getScreenCTM?.();
            if (!matrix || !Number.isFinite(x) || !Number.isFinite(y)) return null;
            const point = new DOMPoint(x, y).matrixTransform(matrix);
            return { x: point.x, y: point.y };
          };
          const svg = document.querySelector('.persistent-modeling-plot svg[role=img]');
          const axis = [...(svg?.querySelectorAll('.chart-axis') ?? [])]
            .find(
              line => line.getAttribute('x1') !== line.getAttribute('x2')
            )?.getBoundingClientRect();
          const workspace = box('.modeling-split-workspace');
          const processCluster = box('.modeling-process-workspace-bounded');
          const fitCluster = box('.modeling-fit-workspace-bounded');
          const rail = box('.modeling-workspace-rail');
          const ribbon = box('.modeling-task-ribbon');
          const plot = box('.persistent-modeling-plot');
          const legend = rect(document.querySelector('.modeling-process-workspace-bounded .persistent-modeling-plot > .curve-legend')
            ?? document.querySelector('.modeling-fit-workspace-bounded .persistent-modeling-plot > .curve-legend'));
          const svgBox = svg?.getBoundingClientRect();
          const ticks = [...(svg?.querySelectorAll('.chart-tick') ?? [])].map(rect).filter(Boolean);
          const axisLabels = [...(svg?.querySelectorAll('.chart-axis-label') ?? [])].map(rect).filter(Boolean);
          const axes = [...(svg?.querySelectorAll('.chart-axis') ?? [])].map(rect).filter(Boolean);
          const xAxisLabel = axisLabels.at(-2);
          const xTickLabels = [...(svg?.querySelectorAll('g') ?? [])]
            .filter(group => [...group.querySelectorAll('line.chart-grid')]
              .some(line => line.getAttribute('x1') === line.getAttribute('x2')))
            .map(group => group.querySelector('text.chart-tick'))
            .map(rect)
            .filter(Boolean);
          const lastXTick = xTickLabels.at(-1) ?? null;
          const xTicksWithinSvg = Boolean(svgBox) && xTickLabels.every(tick => (
            tick.left >= svgBox.left - 1
              && tick.right <= svgBox.right + 1
              && tick.top >= svgBox.top - 1
              && tick.bottom <= svgBox.bottom + 1
          ));
          const curveSegments = [...(svg?.querySelectorAll('polyline.curve-line') ?? [])]
            .filter(polyline => polyline.getClientRects().length)
            .flatMap(polyline => {
              const values = (polyline.getAttribute('points') ?? '')
                .trim()
                .split(/\\s+/)
                .map(pair => pair.split(',').map(Number))
                .filter(pair => pair.length === 2 && pair.every(Number.isFinite));
              const points = values.map(pair => screenPoint(polyline, pair[0], pair[1])).filter(Boolean);
              return points.slice(1).map((point, index) => ({ first: points[index], second: point }));
            });
          const extrapolationBoundary = rect(svg?.querySelector('.extrapolation-region line'));
          const extrapolationLabel = rect(svg?.querySelector('.extrapolation-region text'));
          const stateOverlays = [...(svg?.querySelectorAll(
            '.graph-range-selection, .graph-point-selection, .graph-point-marker, .engineering-result-marker, .chart-crosshair',
          ) ?? [])].map(rect).filter(Boolean);
          const processRows = [...document.querySelectorAll('.modeling-process-workspace-bounded .modeling-dataset-list .curve-row-label')].map(row => {
            const text = (row.textContent ?? '').replace(/\\s+/g, ' ').trim();
            const descendants = [row, ...row.querySelectorAll('strong, small')];
            const clipped = descendants.some(node => node.scrollWidth > node.clientWidth + 1 || node.scrollHeight > node.clientHeight + 1);
            return { text, clipped };
          });
          const processRoot = document.querySelector('.processing-workbench-page.stage-process');
          const processRibbon = rect(processRoot?.querySelector('.modeling-task-ribbon'));
          const processPanel = rect(processRoot?.querySelector('[data-modeling-process-panel="ready"]'));
          const saveBand = rect(processRoot?.querySelector('.process-band-save'));
          const controlNodes = [
            processRoot?.querySelector('.elastic-modulus-method select'),
            processRoot?.querySelector('[aria-label="Elastic range start"]'),
            processRoot?.querySelector('[aria-label="Elastic range end"]'),
            processRoot?.querySelector(`[aria-label="Manual Young's modulus"]`),
            processRoot?.querySelector(`[aria-label="Manual Young's modulus unit"]`),
            processRoot?.querySelector(`[aria-label="Manual Young's modulus reason"]`),
            processRoot?.querySelector('[aria-label="Processed curve label"]'),
            processRoot?.querySelector('[aria-label="Save reason"]'),
            processRoot?.querySelector('.process-band-save > .button'),
          ].filter(Boolean);
          const processControls = controlNodes.map(node => {
            const box = rect(node);
            const style = node ? getComputedStyle(node) : null;
            const text = node?.textContent?.trim() ?? '';
            return {
              label: node?.getAttribute('aria-label') ?? text,
              box,
              height: box?.height ?? 0,
              whiteSpace: style?.whiteSpace ?? '',
              scrollHeight: node?.scrollHeight ?? 0,
              clientHeight: node?.clientHeight ?? 0,
              scrollWidth: node?.scrollWidth ?? 0,
              clientWidth: node?.clientWidth ?? 0,
            };
          });
          const topActionNodes = [
            processRoot?.querySelector('.modeling-context-actions > .modeling-advanced-menu > summary'),
            processRoot?.querySelector('.modeling-context-actions > button.button.secondary'),
          ];
          const topActions = topActionNodes.map(node => {
            const box = rect(node);
            const style = node ? getComputedStyle(node) : null;
            return {
              label: node?.textContent?.trim() ?? '',
              box,
              height: box?.height ?? 0,
              whiteSpace: style?.whiteSpace ?? '',
              scrollHeight: node?.scrollHeight ?? 0,
              clientHeight: node?.clientHeight ?? 0,
              scrollWidth: node?.scrollWidth ?? 0,
              clientWidth: node?.clientWidth ?? 0,
            };
          });
          const method = rect(document.querySelector('.modeling-process-workspace-bounded .elastic-modulus-method select'));
          const range = rect(document.querySelector('.modeling-process-workspace-bounded .elastic-modulus-range'));
          return {
            svgHeight: svgBox?.height ?? 0,
            svgWidth: svgBox?.width ?? 0,
            svgBottom: svgBox?.bottom ?? 0,
            drawableRatio: workspace && axis ? axis.width / workspace.width : 0,
            processClusterWidth: processCluster?.width ?? 0,
            processClusterHeight: processCluster?.height ?? 0,
            processClusterLeft: processCluster?.left ?? 0,
            processClusterTop: processCluster?.top ?? 0,
            fitClusterWidth: fitCluster?.width ?? 0,
            fitClusterHeight: fitCluster?.height ?? 0,
            fitClusterLeft: fitCluster?.left ?? 0,
            fitClusterTop: fitCluster?.top ?? 0,
            workspaceLeft: workspace?.left ?? 0,
            workspaceTop: workspace?.top ?? 0,
            railWidth: rail?.width ?? 0, ribbonHeight: ribbon?.height ?? 0,
            plotBottom: plot?.bottom ?? 0, xAxisLabelBottom: xAxisLabel?.bottom ?? 0,
            legendBottom: legend?.bottom ?? 0,
            legendInPlot: Boolean(legend && plot
              && legend.left >= plot.left - 1
              && legend.right <= plot.right + 1
              && legend.top >= plot.top - 1
              && legend.bottom <= plot.bottom + 1),
            legendOutsideSvg: Boolean(legend && svgBox
              && (legend.left < svgBox.left - 1
                || legend.right > svgBox.right + 1
                || legend.top < svgBox.top - 1
                || legend.bottom > svgBox.bottom + 1)),
            legendTickOverlap: ticks.some(tick => overlaps(legend, tick)),
            legendAxisLabelOverlap: axisLabels.some(label => overlaps(legend, label)),
            legendAxisOverlap: axes.some(axisLine => overlaps(legend, axisLine)),
            legendCurveSegmentOverlap: curveSegments.some(segment => segmentIntersectsRect(segment.first, segment.second, legend)),
            legendExtrapolationBoundaryOverlap: overlaps(legend, extrapolationBoundary),
            legendExtrapolationLabelOverlap: overlaps(legend, extrapolationLabel),
            legendStateOverlayOverlap: stateOverlays.some(overlay => overlaps(legend, overlay)),
            lastXTickWithinSvg: Boolean(lastXTick && xTicksWithinSvg),
            xTicksWithinSvg,
            xTickCount: xTickLabels.length,
            processRows,
            processRowClipped: processRows.some(row => row.clipped),
            fitRows: [...document.querySelectorAll('.modeling-fit-workspace-bounded .modeling-dataset-list .curve-row-label')].map(row => {
              const rowBox = row.getBoundingClientRect();
              const descendants = [row, ...row.querySelectorAll('strong, small')];
              const clipped = descendants.some(node => node.scrollWidth > node.clientWidth + 1 || node.scrollHeight > node.clientHeight + 1);
              return { text: (row.textContent ?? '').replace(/\\s+/g, ' ').trim(), visible: row.getClientRects().length > 0, clipped, box: { top: rowBox.top, bottom: rowBox.bottom } };
            }),
            fitRowsIncluded: document.querySelector('.modeling-fit-workspace-bounded .modeling-dataset-list .rail-heading > span')?.textContent?.trim() ?? '',
            fitNoMatchingCurves: [...document.querySelectorAll('.modeling-fit-workspace-bounded .modeling-dataset-list .muted')]
              .some(node => node.getClientRects().length && (node.textContent ?? '').trim() === 'No matching curves.'),
            methodRangeGap: method && range ? range.left - method.right : null,
            processControls,
            topActions,
            processRibbon,
            processPanel,
            saveBand,
            viewportHeight: window.innerHeight
          };
        }"""
    ))
    if stage == "data":
        # Data keeps a slightly taller source-selection ribbon than Process/Fit.
        # Preserve a large graph without treating a single-digit pixel
        # difference at the 900px viewport as a structural failure.
        default_minimum = 300 if height == 768 else 420
    else:
        default_minimum = 330 if height == 768 else 430
    minimum = minimum_svg_height if minimum_svg_height is not None else default_minimum
    if measurement["svgHeight"] < minimum or measurement["drawableRatio"] < 0.72:
        raise RuntimeError(f"{stage} geometry gate failed at {width}x{height}: {measurement}")
    if width == 1440 and measurement["svgWidth"] < 1050:
        raise RuntimeError(f"{stage} 1440 graph-width gate failed: {measurement}")
    if stage == "process":
        rows = measurement.get("processRows")
        if not isinstance(rows, list) or not rows:
            raise RuntimeError(f"Process rail rows are missing at {width}x{height}: {measurement}")
        for row in rows:
            if not isinstance(row, dict) or not re.fullmatch(r"Specimen \d{2} · r[1-9]\d*", str(row.get("text", ""))):
                raise RuntimeError(f"Process rail identity drifted at {width}x{height}: {measurement}")
        if measurement.get("processRowClipped"):
            raise RuntimeError(f"Process rail identity is clipped at {width}x{height}: {measurement}")
        if measurement.get("legendTickOverlap") or measurement.get("legendAxisLabelOverlap") or measurement.get("legendAxisOverlap"):
            raise RuntimeError(f"Process legend overlaps chart ticks/labels/axis at {width}x{height}: {measurement}")
        method_range_gap = measurement.get("methodRangeGap")
        if not isinstance(method_range_gap, (int, float)) or method_range_gap < 0 or method_range_gap > 20:
            raise RuntimeError(f"Process elastic method/range gap is outside 0–20px at {width}x{height}: {measurement}")
        controls = measurement.get("processControls")
        if not isinstance(controls, list):
            raise RuntimeError(f"Process control geometry is missing at {width}x{height}: {measurement}")
        required_controls = {
            "Evaluation method",
            "Elastic range start",
            "Elastic range end",
            "Processed curve label",
            "Save reason",
            "Save processed curves",
        }
        visible_controls = {
            str(control.get("label"))
            for control in controls
            if isinstance(control, dict) and isinstance(control.get("box"), dict)
        }
        if not required_controls <= visible_controls:
            raise RuntimeError(
                f"Process normal controls are missing at {width}x{height}: {sorted(visible_controls)}"
            )
        ribbon_box = measurement.get("processRibbon")
        panel_box = measurement.get("processPanel")
        if not isinstance(ribbon_box, dict) or not isinstance(panel_box, dict):
            raise RuntimeError(f"Process control containment boxes are missing at {width}x{height}: {measurement}")
        def _inside(child: dict[str, object], parent: dict[str, object]) -> bool:
            return (
                _as_float(child.get("left")) >= _as_float(parent.get("left")) - 1
                and _as_float(child.get("right")) <= _as_float(parent.get("right")) + 1
                and _as_float(child.get("top")) >= _as_float(parent.get("top")) - 1
                and _as_float(child.get("bottom")) <= _as_float(parent.get("bottom")) + 1
            )
        visible_control_boxes = [
            control.get("box")
            for control in controls
            if isinstance(control, dict) and isinstance(control.get("box"), dict)
        ]
        if any(not _inside(box, panel_box) for box in visible_control_boxes if isinstance(box, dict)):
            raise RuntimeError(f"Process controls escaped their panel at {width}x{height}: {measurement}")
        normal_row = [
            control for control in controls
            if isinstance(control, dict) and control.get("label") in {"Evaluation method", "Elastic range start", "Elastic range end"}
        ]
        save_row = [
            control for control in controls
            if isinstance(control, dict) and control.get("label") in {"Processed curve label", "Save reason", "Save processed curves"}
        ]
        manual_row = [
            control for control in controls
            if isinstance(control, dict) and control.get("label") in {
                "Manual Young's modulus",
                "Manual Young's modulus unit",
                "Manual Young's modulus reason",
            }
        ]
        def _aligned(items: Sequence[object], tolerance: float = 2) -> bool:
            boxes = [item.get("box") for item in items if isinstance(item, dict) and isinstance(item.get("box"), dict)]
            if len(boxes) < 2:
                return False
            tops = [_as_float(box.get("top")) for box in boxes]
            bottoms = [_as_float(box.get("bottom")) for box in boxes]
            return max(tops) - min(tops) <= tolerance and max(bottoms) - min(bottoms) <= tolerance
        if not _aligned(normal_row) or not _aligned(save_row):
            raise RuntimeError(f"Process control baselines drifted at {width}x{height}: {measurement}")
        if manual_row and len(manual_row) == 3 and not _aligned(manual_row):
            raise RuntimeError(f"Process manual control baselines drifted at {width}x{height}: {measurement}")
        for control in controls:
            if not isinstance(control, dict) or not isinstance(control.get("box"), dict):
                continue
            height_px = float(control.get("height", 0))
            if abs(height_px - 28) > 1:
                raise RuntimeError(f"Process control height drifted at {width}x{height}: {control}")
            if str(control.get("label")) == "Save processed curves":
                if control.get("whiteSpace") != "nowrap" or float(control.get("scrollHeight", 0)) > float(control.get("clientHeight", 0)) + 1:
                    raise RuntimeError(f"Process Save button wraps at {width}x{height}: {control}")
            if str(control.get("label")) in {"Processed curve label", "Save reason"}:
                if control.get("whiteSpace") != "nowrap":
                    raise RuntimeError(f"Process save label wraps at {width}x{height}: {control}")
        top_actions = measurement.get("topActions")
        if not isinstance(top_actions, list) or len(top_actions) != 2:
            raise RuntimeError(f"Process top actions are missing at {width}x{height}: {measurement}")
        expected_top_action_labels = ["Advanced", "Preview changes"]
        actual_top_action_labels = [
            str(action.get("label", "")).strip()
            for action in top_actions
            if isinstance(action, dict)
        ]
        if actual_top_action_labels != expected_top_action_labels:
            raise RuntimeError(
                f"Process top action labels drifted at {width}x{height}: {measurement}"
            )
        if not _aligned(top_actions):
            raise RuntimeError(f"Process top action baselines drifted at {width}x{height}: {measurement}")
        for action in top_actions:
            box = action.get("box") if isinstance(action, dict) else None
            if (
                not isinstance(action, dict)
                or not isinstance(box, dict)
                or float(box.get("width", 0)) <= 0
                or float(box.get("height", 0)) <= 0
                or abs(float(action.get("height", 0)) - 28) > 1
            ):
                raise RuntimeError(f"Process top action height drifted at {width}x{height}: {action}")
    if stage == "process" and width >= 2560:
        if (
            measurement["processClusterWidth"] <= 0
            or measurement["processClusterHeight"] <= 0
            or measurement["processClusterWidth"] > 1920 + 1
            or measurement["processClusterHeight"] > 879
            or measurement["processClusterLeft"] > measurement["workspaceLeft"] + 1
            or measurement["processClusterTop"] > measurement["workspaceTop"] + 1
        ):
            raise RuntimeError(f"Process wide cluster bound/alignment failed at {width}x{height}: {measurement}")
    if stage == "fit":
        rows = measurement.get("fitRows")
        if not isinstance(rows, list) or len(rows) != 3:
            raise RuntimeError(f"Fit rail must expose exactly three exact rows at {width}x{height}: {measurement}")
        for row in rows:
            if (
                not isinstance(row, dict)
                or row.get("visible") is not True
                or row.get("clipped") is True
                or not re.fullmatch(r"Specimen \d{2} · r[1-9]\d*", str(row.get("text", "")))
            ):
                raise RuntimeError(f"Fit rail identity is missing or clipped at {width}x{height}: {measurement}")
        if measurement.get("fitRowsIncluded") != "2 included":
            raise RuntimeError(f"Fit rail selected included count drifted at {width}x{height}: {measurement}")
        if measurement.get("fitNoMatchingCurves"):
            raise RuntimeError(f"Fit rail exposed No matching curves at {width}x{height}: {measurement}")
        if measurement["fitClusterWidth"] <= 0 or measurement["fitClusterWidth"] > 1920 + 1:
            raise RuntimeError(f"Fit workspace width escaped its bounded cluster at {width}x{height}: {measurement}")
        if width >= 2560 and (
            measurement["fitClusterHeight"] <= 0
            or measurement["fitClusterHeight"] > 879
            or measurement["fitClusterLeft"] > measurement["workspaceLeft"] + 1
            or measurement["fitClusterTop"] > measurement["workspaceTop"] + 1
        ):
            raise RuntimeError(f"Fit wide cluster bound/alignment failed at {width}x{height}: {measurement}")
        if not 184 <= measurement["railWidth"] <= 210:
            raise RuntimeError(f"Fit compact curve rail width drifted at {width}x{height}: {measurement}")
        if abs(measurement["ribbonHeight"] - 104) > 1:
            raise RuntimeError(f"Fit ribbon must remain exactly 104px (31+72) at {width}x{height}: {measurement}")
        if (
            not measurement.get("legendInPlot")
            or measurement.get("legendOutsideSvg")
            or measurement.get("legendTickOverlap")
            or measurement.get("legendAxisLabelOverlap")
            or measurement.get("legendAxisOverlap")
            or measurement.get("legendCurveSegmentOverlap")
            or measurement.get("legendExtrapolationBoundaryOverlap")
            or measurement.get("legendExtrapolationLabelOverlap")
            or measurement.get("legendStateOverlayOverlap")
        ):
            raise RuntimeError(f"Fit legend collides with plot content at {width}x{height}: {measurement}")
        if not measurement.get("lastXTickWithinSvg") or not measurement.get("xTicksWithinSvg"):
            raise RuntimeError(f"Fit final x tick is clipped at {width}x{height}: {measurement}")
    if (
        measurement["svgBottom"] > measurement["plotBottom"] + 2.5
        or measurement["xAxisLabelBottom"] > measurement["plotBottom"] + 1
    ):
        raise RuntimeError(f"{stage} axis is clipped at {width}x{height}: {measurement}")
    if measurement["legendBottom"] > measurement["viewportHeight"]:
        raise RuntimeError(f"{stage} legend is clipped at {width}x{height}: {measurement}")
    return measurement


def _wait_modeling_process_panel(page: Page) -> None:
    page.locator('[data-modeling-process-panel="ready"]').wait_for(timeout=30_000)
    if page.get_by_role("status", name="Loading Process controls").count():
        raise RuntimeError("Process capture settled with the lazy loading fallback visible")


def _wait_for_modeling_process_destination_state(page: Page) -> None:
    """Wait for the Process destination to retain its deliberately blocked session."""
    page.wait_for_function(
        """() => {
          const raw = window.sessionStorage.getItem('cmp.modeling.recent-session.v4');
          if (!raw) return false;
          try {
            const session = JSON.parse(raw);
            const workspace = session.workspace;
            return session.testData === undefined
              && workspace !== null
              && typeof workspace === 'object'
              && Array.isArray(workspace.selectedTestDataRefs)
              && workspace.selectedTestDataRefs.length === 0
              && Array.isArray(workspace.selectedDocumentIds)
              && workspace.selectedDocumentIds.length === 0
              && Array.isArray(workspace.visibleTestDataKeys)
              && workspace.visibleTestDataKeys.length === 0;
          } catch {
            return false;
          }
        }""",
        timeout=30_000,
    )


def _wait_for_modeling_process_plot_size(page: Page) -> None:
    """Wait until the responsive Process SVG viewBox matches its rendered frame."""
    page.wait_for_function(
        """() => {
          const svg = document.querySelector('.persistent-modeling-plot svg[role="img"]');
          if (!svg || svg.getClientRects().length === 0) return false;
          const viewBox = svg.viewBox.baseVal;
          const rendered = svg.getBoundingClientRect();
          return viewBox.width > 0
            && viewBox.height > 0
            && rendered.width > 0
            && rendered.height > 0
            && Math.abs(viewBox.width - rendered.width) < 1
            && Math.abs(viewBox.height - rendered.height) < 1;
        }""",
        timeout=30_000,
    )


def _wait_for_process_plot_before_capture(page: Page) -> None:
    _wait_for_modeling_process_plot_size(page)


def _process_plot_capture_callback(page: Page) -> Callable[[], None]:
    def callback() -> None:
        _wait_for_process_plot_before_capture(page)

    return callback


def _click_modeling_process_preview_and_wait(page: Page) -> None:
    """Wait for the new Process preview POST, then require an idle action bar."""
    preview = page.get_by_role("button", name="Preview changes", exact=True)
    with page.expect_response(
        lambda response: response.request.method == "POST"
        and urlsplit(response.url).path.endswith("/processing:preview"),
        timeout=30_000,
    ) as response_info:
        preview.click()
    response = response_info.value
    if not response.ok:
        raise RuntimeError(f"Process preview request failed: {response.status}")
    page.get_by_role("button", name="Preview changes", exact=True).wait_for(
        state="visible", timeout=30_000
    )
    page.wait_for_function(
        """() => {
          const preview = [...document.querySelectorAll('button')]
            .find(button => button.textContent?.trim() === 'Preview changes');
          const updating = [...document.querySelectorAll('button')]
            .some(button => button.textContent?.trim() === 'Updating…');
          return Boolean(preview && !preview.disabled && !updating);
        }""",
        timeout=30_000,
    )
    page.get_by_text("Preview ready", exact=False).wait_for(timeout=30_000)


def _click_modeling_fit_preview_and_wait(page: Page) -> None:
    """Wait for the one persisted exact-source Fit run and its settled result."""
    preview = page.get_by_role("button", name="Preview changes", exact=True)
    with page.expect_response(
        lambda response: response.request.method == "POST"
        and urlsplit(response.url).path.endswith("/metal-fit-runs"),
        timeout=30_000,
    ) as response_info:
        preview.click()
    response = response_info.value
    if not response.ok:
        raise RuntimeError(f"Fit calculation request failed: {response.status}")
    page.wait_for_function(
        """() => {
          const preview = [...document.querySelectorAll('button')]
            .find(button => button.textContent?.trim() === 'Preview changes');
          const updating = [...document.querySelectorAll('button')]
            .some(button => button.textContent?.trim() === 'Updating…');
          return Boolean(preview && !preview.disabled && !updating);
        }""",
        timeout=30_000,
    )
    page.get_by_text("Preview ready", exact=False).wait_for(timeout=30_000)


def _save_process_output_for_fit(
    page: Page,
    *,
    label: str,
    reason: str,
) -> dict[str, object]:
    """Persist one Process-only result before any Fit preview is requested."""
    _assert_modeling_process_preview(page)
    panel = page.locator('[data-modeling-process-panel="ready"]')
    output_label = panel.get_by_role("textbox", name="Processed curve label", exact=True)
    output_reason = panel.get_by_role("textbox", name="Save reason", exact=True)
    save = panel.get_by_role("button", name="Save processed curves", exact=True)
    output_label.fill(label)
    output_reason.fill(reason)
    with page.expect_response(
        lambda response: response.request.method == "POST"
        and urlsplit(response.url).path.endswith("/processing-outputs"),
        timeout=30_000,
    ) as response_info:
        save.click()
    response = response_info.value
    if not response.ok:
        raise RuntimeError(f"Process source save failed before Fit: {response.status}")
    page.get_by_text("Processed result saved and current", exact=False).wait_for(timeout=30_000)
    session = _modeling_session(page)
    pointer = session.get("processingOutput")
    if not isinstance(pointer, dict):
        raise RuntimeError("Process save did not pin an exact Processing Output for Fit")
    if not all(
        isinstance(pointer.get(key), str) and pointer.get(key)
        for key in ("id", "revisionId", "label")
    ):
        raise RuntimeError(f"Process save pinned an incomplete output identity: {pointer!r}")
    if pointer.get("revisionNo") != 1:
        raise RuntimeError(f"Process save did not pin Processing Output revision r1: {pointer!r}")
    return pointer


def _prepare_fit_from_saved_process(
    page: Page,
    base_url: str,
    *,
    label: str = "Fit source Process result",
) -> dict[str, object]:
    """Prepare Fit from a real exact Process Output rather than a raw Test Data preview."""
    _prepare_modeling_process(page, base_url)
    pointer = _save_process_output_for_fit(
        page,
        label=label,
        reason="Bind one immutable Process result as the exact Fit source.",
    )
    _open_modeling_stage(page, "fit")
    page.wait_for_url(re.compile(r"stage=fit"), timeout=30_000)
    page.locator(".modeling-work-title strong").get_by_text(
        STAGE_HEADINGS["fit"], exact=True
    ).wait_for(timeout=30_000)
    page.get_by_text(re.compile(r"Exact Process source"), exact=False).wait_for(timeout=30_000)
    return pointer


def _open_fit_evidence(page: Page) -> tuple[Locator, Locator, Locator]:
    """Open the controlled Fit drawer and expose its single local body scrollport."""
    trigger = page.get_by_role("button", name="Candidate parameters", exact=True)
    trigger.wait_for(state="visible", timeout=30_000)
    if trigger.get_attribute("aria-expanded") != "true":
        trigger.click()
    if trigger.get_attribute("aria-expanded") != "true":
        raise RuntimeError("Fit evidence trigger did not expose aria-expanded=true")
    if trigger.get_attribute("aria-controls") != "fit-evidence-dock":
        raise RuntimeError("Fit evidence trigger lost its controlled dock identity")
    drawer = page.locator(".fit-evidence-drawer#fit-evidence-dock")
    drawer.wait_for(state="visible", timeout=30_000)
    if page.get_by_role("region", name="Candidate parameters", exact=True).count() != 1:
        raise RuntimeError("Fit evidence dock lost its Candidate parameters outer label")
    drawer.get_by_role("button", name="Close", exact=True).wait_for(state="visible", timeout=30_000)
    drawer.get_by_role("status").filter(has_text="Calculated evidence").wait_for(state="visible", timeout=30_000)
    body = drawer.locator(".fit-evidence-body")
    body.wait_for(state="visible", timeout=30_000)
    if body.get_attribute("tabindex") != "0":
        raise RuntimeError("Fit evidence body must be the focusable local scrollport")
    if drawer.locator(".fit-evidence-scroll-rail").count():
        raise RuntimeError("Fit evidence drawer contains a fake scrollbar rail")
    table = page.get_by_role("table", name="Hardening candidate comparison")
    table.wait_for(state="visible", timeout=30_000)
    return trigger, body, table


def _close_fit_evidence(page: Page, trigger: Locator) -> None:
    """Close through the explicit action and require React focus restoration."""
    drawer = page.locator(".fit-evidence-drawer#fit-evidence-dock")
    drawer.get_by_role("button", name="Close", exact=True).click()
    page.wait_for_function(
        """() => {
          const trigger = document.querySelector('button.fit-evidence-trigger');
          const drawer = document.querySelector('.fit-evidence-drawer#fit-evidence-dock');
          return Boolean(trigger && trigger.getAttribute('aria-expanded') === 'false' && !drawer);
        }""",
        timeout=30_000,
    )
    if page.evaluate("() => document.activeElement?.textContent?.trim()") != "Candidate parameters":
        raise RuntimeError("Fit evidence Close did not restore trigger focus")
    if trigger.get_attribute("aria-expanded") != "false":
        raise RuntimeError("Fit evidence trigger remained expanded after Close")


def _assert_fit_candidate_surface(page: Page, table: Locator) -> None:
    """Assert the numerical identity, decision, and recovery fields in Fit."""
    for column in (
        "Decision",
        "Model / law",
        "Recommendation",
        "Metric",
        "Fit / extrapolation range",
        "Stability",
        "Compatibility",
        "Warning",
    ):
        if table.get_by_role("columnheader", name=column, exact=True).count() != 1:
            raise RuntimeError(f"Fit candidate table is missing {column}")
    for text, message in (
        ("RMSE", "RMSE evidence"),
        ("Converged", "convergence evidence"),
        ("active bound", "active-bound evidence"),
        ("identifiability", "identifiability evidence"),
        ("Select candidate", "candidate selection action"),
    ):
        if table.get_by_text(re.compile(text, re.IGNORECASE)).count() == 0:
            raise RuntimeError(f"Fit candidate table is missing {message}")
    page.get_by_role("button", name="Close", exact=True).wait_for(state="visible", timeout=30_000)


def _assert_fit_display_scale(page: Page, context: str) -> None:
    """Keep Ghosh's epsilon_0 tail out of the normal graph scale only."""
    plot = page.locator(".persistent-modeling-plot")
    plot.wait_for(state="visible", timeout=30_000)
    axis_labels = [text.strip() for text in plot.locator(".chart-axis-label").all_text_contents()]
    if not any(label.startswith("Hardening stress") and "[MPa]" in label for label in axis_labels):
        raise RuntimeError(f"Fit {context} graph is not readable in MPa: {axis_labels!r}")
    plot_text = plot.inner_text()
    if re.search(r"1e\d+\s*GPa", plot_text, re.IGNORECASE):
        raise RuntimeError(f"Fit {context} graph exposed an epsilon_0-scale GPa label: {plot_text!r}")
    note = plot.locator(".ghosh-display-scale-note")
    note.wait_for(state="visible", timeout=30_000)
    note_metrics = note.evaluate(
        "element => ({ height: element.getBoundingClientRect().height, scrollHeight: element.scrollHeight, clientHeight: element.clientHeight, text: element.textContent?.trim() || '' })"
    )
    if note_metrics["scrollHeight"] > note_metrics["clientHeight"] + 1:
        raise RuntimeError(f"Fit {context} Ghosh display note is clipped: {note_metrics!r}")


def _select_warned_fit_candidate(table: Locator) -> None:
    """Select the first candidate whose Warning column contains a warning."""
    rows = table.locator("tbody tr")
    for index in range(rows.count()):
        row = rows.nth(index)
        warning = row.locator("td").last.inner_text().strip()
        if warning and warning.casefold() != "none":
            row.get_by_role(
                "button", name=re.compile(r"^Select .+ candidate$")
            ).click()
            return
    raise RuntimeError("Fit candidate table did not expose a warned candidate")


def _assert_fit_selected_evidence(page: Page) -> None:
    parameter_table = page.get_by_role(
        "table", name="Selected candidate parameters and bounds"
    )
    parameter_table.wait_for(state="visible", timeout=30_000)
    for column in ("Law", "Parameter", "Unit", "Lower", "Initial", "Fitted", "Upper", "Bound / condition"):
        if parameter_table.get_by_role("columnheader", name=column, exact=True).count() != 1:
            raise RuntimeError(f"Selected Fit parameter table is missing {column}")
    if parameter_table.locator("tbody tr").count() < 1:
        raise RuntimeError("Selected Fit candidate must expose parameter and bound evidence")
    page.get_by_role("textbox", name="Candidate selection reason", exact=True).wait_for(state="visible", timeout=30_000)
    page.get_by_role("button", name="Close", exact=True).wait_for(state="visible", timeout=30_000)


def _scroll_fit_evidence_locally(
    page: Page,
    body: Locator,
    *,
    close_escape: bool = True,
) -> None:
    """Exercise PageDown, wheel, native-thumb drag, and optionally Escape on one body."""
    body.evaluate(
        """el => {
          el.scrollTop = 0;
          el.scrollLeft = 0;
          el.focus({ preventScroll: true });
        }"""
    )
    before = page.evaluate("() => window.scrollY")
    metrics = body.evaluate(
        """el => ({
          scrollTop: el.scrollTop,
          scrollLeft: el.scrollLeft,
          scrollHeight: el.scrollHeight,
          scrollWidth: el.scrollWidth,
          clientHeight: el.clientHeight,
          clientWidth: el.clientWidth,
          offsetHeight: el.offsetHeight,
          offsetWidth: el.offsetWidth,
          rect: el.getBoundingClientRect().toJSON(),
        })"""
    )
    if metrics["scrollHeight"] <= metrics["clientHeight"]:
        raise RuntimeError(f"Fit evidence body is not vertically overflowing: {metrics!r}")
    gutter = metrics["offsetWidth"] - metrics["clientWidth"]
    if not 12 <= gutter <= 16:
        raise RuntimeError(
            "Fit evidence body must reserve a genuine native scrollbar gutter "
            f"of 12-16 px inclusive: {metrics!r}"
        )
    body.press("PageDown")
    page.wait_for_function(
        """() => {
          const body = document.querySelector('.fit-evidence-body');
          return Boolean(body && body.scrollTop > 0 && body.scrollTop < body.scrollHeight - body.clientHeight + 1);
        }""",
        timeout=30_000,
    )
    after_page_down = body.evaluate("el => el.scrollTop")
    page.mouse.move(metrics["rect"]["left"] + metrics["clientWidth"] / 2, metrics["rect"]["top"] + metrics["clientHeight"] / 2)
    page.mouse.wheel(0, 92)
    after_wheel = body.evaluate("el => el.scrollTop")
    if after_wheel <= after_page_down:
        raise RuntimeError("Fit evidence wheel did not move the local body")
    body.evaluate("el => { el.scrollTop = 0; el.scrollLeft = 0; }")
    refreshed = body.evaluate("el => ({ rect: el.getBoundingClientRect().toJSON(), clientHeight: el.clientHeight, scrollHeight: el.scrollHeight })")
    track_x = refreshed["rect"]["right"] - 6
    thumb_height = max(20, refreshed["clientHeight"] * refreshed["clientHeight"] / refreshed["scrollHeight"])
    thumb_start = refreshed["rect"]["top"] + thumb_height / 2
    page.mouse.move(track_x, thumb_start)
    page.mouse.down()
    page.mouse.move(track_x, thumb_start + 22, steps=4)
    page.mouse.up()
    after_drag = body.evaluate("el => el.scrollTop")
    if after_drag <= 0:
        raise RuntimeError("Fit evidence native scrollbar thumb drag did not move the local body")
    if page.evaluate("() => window.scrollY") != before:
        raise RuntimeError("Fit evidence local scrolling changed the page scroll position")
    if close_escape:
        page.keyboard.press("Escape")
        active_after_escape = page.evaluate(
            """() => ({
              tag: document.activeElement?.tagName || null,
              text: document.activeElement?.textContent?.trim() || null,
              triggerExpanded: document.querySelector('button.fit-evidence-trigger')?.getAttribute('aria-expanded') || null,
            })"""
        )
        if active_after_escape["text"] != "Candidate parameters" or active_after_escape["triggerExpanded"] != "false":
            raise RuntimeError(f"Fit evidence Escape recovery did not restore trigger focus: {active_after_escape!r}")


def _assert_modeling_process_preview(
    page: Page,
    expected_modulus: str = "210.0 GPa",
    method_label: str = "Auto robust",
) -> None:
    """Run the focused Process preview and assert its normal non-Fit surface."""
    _click_modeling_process_preview_and_wait(page)
    _wait_modeling_process_panel(page)
    _wait_for_modeling_process_plot_size(page)
    panel = page.locator('[data-modeling-process-panel="ready"]')
    if panel.count() != 1 or not panel.is_visible():
        raise RuntimeError("Process preview did not settle on its ready panel")
    source = panel.locator(".process-band-source")
    source.wait_for(state="visible", timeout=30_000)
    if source.inner_text().strip() != PROCESS_SOURCE_VISIBLE_IDENTITY:
        raise RuntimeError(f"Process preview source is not exact Specimen 01 r1: {source.inner_text()!r}")
    heading = page.locator(".persistent-modeling-plot > .section-heading")
    heading.get_by_text("Curve response", exact=True).wait_for(state="visible", timeout=30_000)
    toolbar = page.locator(".persistent-modeling-plot > .modeling-plot-toolbar")
    toolbar.wait_for(state="visible", timeout=30_000)
    for control in ("Reset view", "Pan", "Select range"):
        button = toolbar.get_by_role("button", name=control, exact=True)
        button.wait_for(state="visible", timeout=30_000)
        if button.is_disabled():
            raise RuntimeError(f"Process plot control is unexpectedly disabled: {control}")
    result = panel.locator(".process-band-result")
    result.get_by_text(expected_modulus, exact=True).wait_for(timeout=30_000)
    save = panel.get_by_role("button", name="Save processed curves", exact=True)
    save.wait_for(state="visible", timeout=30_000)
    controls = panel.locator(".process-band-controls")
    method = controls.get_by_role("combobox", name="Evaluation method", exact=True)
    method.wait_for(state="visible", timeout=30_000)
    expected_methods = [
        ("robust_huber", "Auto robust"),
        ("linear_regression", "Linear regression"),
        ("chord", "Chord"),
        ("secant", "Secant"),
        ("manual", "Manual slope"),
    ]
    if method.locator("option").all_inner_texts() != [label for _, label in expected_methods]:
        raise RuntimeError("Process Evaluation method options drifted")
    method_by_label = {label: value for value, label in expected_methods}
    for value, label in expected_methods:
        # select_option exercises the pointer path; Home/ArrowDown exercises
        # the native keyboard path without replacing the native select.
        method.select_option(value)
        if method.input_value() != value:
            raise RuntimeError(f"Process pointer method selection drifted: {label!r}")
        method.focus()
        method.press("Home")
        for _ in range(expected_methods.index((value, label))):
            method.press("ArrowDown")
        if method.input_value() != value:
            raise RuntimeError(f"Process keyboard method selection drifted: {label!r}")
    method.select_option(method_by_label[method_label])
    _wait_modeling_process_panel(page)
    _click_modeling_process_preview_and_wait(page)
    _wait_for_modeling_process_plot_size(page)
    if method.locator("option:checked").inner_text() != method_label:
        raise RuntimeError(f"Process preview method drifted: expected {method_label!r}")
    for label in ("Elastic range start", "Elastic range end"):
        controls.get_by_role("spinbutton", name=label, exact=True).wait_for(state="visible", timeout=30_000)
    if page.locator(".fit-evidence-drawer").count() or page.get_by_text("Candidate equations", exact=True).count() or page.get_by_text("Fit domain", exact=True).count() or page.get_by_text("Selected blend", exact=True).count():
        raise RuntimeError("Process preview exposed Fit candidate controls")
    _assert_modeling_process_geometry(page)


def _assert_modeling_process_manual_surface(page: Page) -> None:
    """Exercise the compact Process manual workup, then restore Auto robust."""
    panel = page.locator('[data-modeling-process-panel="ready"]')
    controls = panel.locator(".process-band-controls")
    manual = controls.get_by_role("combobox", name="Evaluation method", exact=True)
    # Locator.click is a real pointer click in the live capture (not a
    # synthetic React event), so the helper proves the normal interaction path.
    manual.select_option("manual")
    value = controls.get_by_role("spinbutton", name="Manual Young's modulus", exact=True)
    unit = controls.get_by_role("combobox", name="Manual Young's modulus unit", exact=True)
    reason = controls.get_by_role("textbox", name="Manual Young's modulus reason", exact=True)
    for control in (value, unit, reason):
        control.wait_for(state="visible", timeout=30_000)
    panel_box = _bounding_box_edges(panel.bounding_box())
    if panel_box is None:
        raise RuntimeError("Process manual controls have no current-step panel bounds")
    for name, control in (("value", value), ("unit", unit), ("reason", reason)):
        control_box = _bounding_box_edges(control.bounding_box())
        if control_box is None or control_box["left"] < panel_box["left"] or control_box["right"] > panel_box["right"] or control_box["top"] < panel_box["top"] or control_box["bottom"] > panel_box["bottom"]:
            raise RuntimeError(f"Process manual {name} control escaped the current-step band: panel={panel_box}, control={control_box}")
    hit_tests = page.evaluate(
        """() => [
          '[data-modeling-process-panel="ready"] [aria-label="Manual Young\\'s modulus"]',
          '[data-modeling-process-panel="ready"] [aria-label="Manual Young\\'s modulus unit"]',
          '[data-modeling-process-panel="ready"] [aria-label="Manual Young\\'s modulus reason"]',
        ].map(selector => {
          const node = document.querySelector(selector);
          const box = node?.getBoundingClientRect();
          const hit = box ? document.elementFromPoint(box.left + box.width / 2, box.top + box.height / 2) : null;
          return { selector, own: Boolean(node && hit && (hit === node || node.contains(hit))) };
        })"""
    )
    if not isinstance(hit_tests, list) or any(not isinstance(item, dict) or not item.get("own") for item in hit_tests):
        raise RuntimeError(f"Process manual controls failed center hit-testing: {hit_tests!r}")
    overflow = page.evaluate(
        """() => ({ scrollWidth: document.documentElement.scrollWidth, clientWidth: document.documentElement.clientWidth })"""
    )
    if not isinstance(overflow, dict) or float(overflow.get("scrollWidth", 0)) > float(overflow.get("clientWidth", 0)):
        raise RuntimeError(f"Process manual surface introduced page horizontal overflow: {overflow!r}")
    value.focus()
    page.keyboard.press("Tab")
    if page.evaluate("() => document.activeElement?.getAttribute('aria-label')") != "Manual Young's modulus unit":
        raise RuntimeError("Process manual value did not Tab to Unit")
    page.keyboard.press("Tab")
    if page.evaluate("() => document.activeElement?.getAttribute('aria-label')") != "Manual Young's modulus reason":
        raise RuntimeError("Process manual Unit did not Tab to reason")
    plot_box = page.locator(".persistent-modeling-plot").bounding_box()
    svg_box = page.locator(".persistent-modeling-plot svg[role=img]").bounding_box()
    if plot_box is None or plot_box["height"] < 280 or svg_box is None or svg_box["height"] < 230:
        raise RuntimeError(f"Process manual surface compressed the plot: plot={plot_box}, svg={svg_box}")
    viewport = page.evaluate("() => ({ width: window.innerWidth, height: window.innerHeight })")
    _measure_process_fit(
        page,
        "process",
        int(viewport["width"]),
        int(viewport["height"]),
        minimum_svg_height=230,
    )
    auto = controls.get_by_role("combobox", name="Evaluation method", exact=True)
    auto.select_option("robust_huber")
    page.wait_for_function(
        """() => document.querySelector('[data-modeling-process-panel="ready"] select[aria-label="Evaluation method"]')
          ?.value === 'robust_huber'""",
        timeout=30_000,
    )
    _click_modeling_process_preview_and_wait(page)
    _wait_modeling_process_panel(page)
    _wait_for_modeling_process_plot_size(page)
    controls = page.locator('[data-modeling-process-panel="ready"] .process-band-controls')
    if controls.get_by_role("combobox", name="Evaluation method", exact=True).input_value() != "robust_huber":
        raise RuntimeError("Process manual helper did not restore Auto robust")
    page.locator('[data-modeling-process-panel="ready"] .process-band-result').get_by_text("210.0 GPa", exact=True).wait_for(timeout=30_000)
    _assert_modeling_process_geometry(page)


def _assert_modeling_process_geometry(page: Page) -> None:
    ribbon = _bounding_box_edges(page.locator(".modeling-task-ribbon").bounding_box())
    panel = _bounding_box_edges(page.locator('[data-modeling-process-panel="ready"]').bounding_box())
    plot = _bounding_box_edges(page.locator(".persistent-modeling-plot").bounding_box())
    svg = _bounding_box_edges(page.locator(".persistent-modeling-plot svg[role='img']").bounding_box())
    save_band = _bounding_box_edges(page.locator(".process-band-save").bounding_box())
    save = page.get_by_role("button", name="Save processed curves", exact=True)
    save_box = _bounding_box_edges(save.bounding_box())
    if ribbon is None or panel is None or plot is None or svg is None or save_band is None or save_box is None:
        raise RuntimeError("Process preview geometry is unavailable")
    if plot["height"] < 280 or svg["height"] < 230:
        raise RuntimeError(f"Process plot geometry fell below the required minima: plot={plot}, svg={svg}")
    if panel["left"] < ribbon["left"] - 1 or panel["right"] > ribbon["right"] + 1 or panel["top"] < ribbon["top"] - 1 or panel["bottom"] > ribbon["bottom"] + 1:
        raise RuntimeError(f"Process panel escaped the task ribbon: panel={panel}, ribbon={ribbon}")
    if save_band["bottom"] > plot["top"] + 1 or save_box["bottom"] > plot["top"] + 1:
        raise RuntimeError(f"Process save band crosses the plot top: save_band={save_band}, save={save_box}, plot={plot}")
    hit = page.evaluate(
        """button => {
          const box = button.getBoundingClientRect();
          const element = document.elementFromPoint(box.left + box.width / 2, box.top + box.height / 2);
          return {
            insideSave: Boolean(element && button.contains(element)),
            tag: element?.tagName ?? null,
            graph: Boolean(element?.closest('.persistent-modeling-plot')),
            svg: Boolean(element?.closest('svg')),
          };
        }""",
        save.element_handle(),
    )
    if not hit["insideSave"] or hit["graph"] or hit["svg"]:
        raise RuntimeError(f"Process Save center is intercepted by graph/SVG: {hit}")
    _assert_modeling_process_table_geometry(page)


def _assert_modeling_process_draft_geometry(page: Page) -> None:
    """Exercise the action-needed draft height and restore a settled preview."""
    method = page.locator(
        '[data-modeling-process-panel="ready"] select[aria-label="Evaluation method"]'
    )
    method.wait_for(state="visible", timeout=30_000)
    current = method.input_value()
    draft = "chord" if current != "chord" else "linear_regression"
    method.select_option(draft)
    page.wait_for_function(
        """() => {
          const preview = [...document.querySelectorAll('button')]
            .find(button => button.textContent?.trim() === 'Preview changes');
          return Boolean(preview && !preview.disabled);
        }""",
        timeout=30_000,
    )
    _assert_modeling_process_geometry(page)
    method.select_option(current)
    _click_modeling_process_preview_and_wait(page)
    _wait_for_modeling_process_plot_size(page)


def _assert_modeling_process_stage_round_trip(
    page: Page,
    base_url: str,
    *,
    expected_current_output: dict[str, object],
    expected_current_label: str,
) -> None:
    """Keep one copied history draft and the saved current through Data→Fit→Export→Process."""
    panel = page.locator('[data-modeling-process-panel="ready"]')
    panel.wait_for(state="visible", timeout=30_000)
    source = panel.locator(".process-band-source")
    if source.inner_text().strip() != PROCESS_SOURCE_VISIBLE_IDENTITY:
        raise RuntimeError(f"Process round-trip source drifted: {source.inner_text()!r}")
    label = panel.get_by_role("textbox", name="Processed curve label", exact=True)
    reason = panel.get_by_role("textbox", name="Save reason", exact=True)
    draft_label = label.input_value()
    draft_reason = reason.input_value()
    method = panel.get_by_role("combobox", name="Evaluation method", exact=True)
    draft_method = method.input_value()
    draft_range_start = panel.get_by_role("spinbutton", name="Elastic range start", exact=True).input_value()
    draft_range_end = panel.get_by_role("spinbutton", name="Elastic range end", exact=True).input_value()
    if draft_method != "chord" or draft_range_start != "0.001" or draft_range_end != "0.003":
        raise RuntimeError(
            "Process round-trip did not start from the copied Chord draft settings: "
            f"method={draft_method!r}, range={draft_range_start!r}–{draft_range_end!r}"
        )
    panel.locator(".process-band-result").get_by_text("210.0 GPa", exact=True).wait_for(timeout=30_000)
    graph = page.locator(".persistent-modeling-plot svg[role='img']")
    graph.wait_for(state="visible", timeout=30_000)
    graph_label = graph.get_attribute("aria-label")
    graph_box = graph.bounding_box()
    if not graph_label or graph_box is None or graph_box["width"] <= 0 or graph_box["height"] <= 0:
        raise RuntimeError("Process round-trip graph is not a visible retained engineering graph")

    expected_current_output_id = expected_current_output.get("processing_output_id")
    if not isinstance(expected_current_output_id, str) or not expected_current_output_id:
        raise RuntimeError(
            "Process round-trip expected current output has no stable identity: "
            f"{expected_current_output!r}"
        )
    source_pin, profile_pin = _process_session_pins(page)
    before_outputs = _matching_process_outputs(
        _list_processing_outputs(page, base_url), source_pin, profile_pin
    )
    before_by_id = {
        str(item.get("processing_output_id")): item
        for item in before_outputs
        if item.get("processing_output_id")
    }
    before_rows = _assert_modeling_process_saved_rows_three(
        page,
        current_label=expected_current_label,
    )
    if not any(expected_current_label in row and "current" in row for row in before_rows):
        raise RuntimeError("Process round-trip did not expose the newly saved output as the sole current row")
    if expected_current_output_id not in before_by_id:
        raise RuntimeError("Process round-trip current output identity is missing before stage navigation")

    _assert_capture_processing_output_pointer(page, expected_current_output)

    mutation_requests: list[str] = []
    data_preview_requests: list[str] = []
    forbidden_preview_requests: list[str] = []
    mutation_tokens = ("processing-outputs", "selection", "export")
    preview_path = "/processing:preview"
    active_stage = "process"

    def record_mutation(request: object) -> None:
        method_name = str(getattr(request, "method", "")).upper()
        path = urlsplit(str(getattr(request, "url", ""))).path.lower()
        if method_name not in {"GET", "HEAD", "OPTIONS"} and any(
            token in path for token in mutation_tokens
        ):
            mutation_requests.append(f"{method_name} {path}")
        if path.endswith(preview_path):
            try:
                payload = getattr(request, "post_data_json", None)
            except Exception:
                payload = None
            steps = payload.get("steps") if isinstance(payload, dict) else None
            request_label = (
                f"{method_name} {path} stage={active_stage} steps={steps!r}"
            )
            if active_stage == "data" and steps == []:
                data_preview_requests.append(request_label)
            else:
                forbidden_preview_requests.append(request_label)

    page.on("request", record_mutation)
    # Close first so the row helper owns the new opening toggle and can gate its
    # refresh responses before any stage navigation begins.
    details = page.locator("details.process-saved-results")
    if details.get_attribute("open") is not None:
        details.locator(":scope > summary").click()
    rerender_rows = _assert_modeling_process_saved_rows_three(
        page,
        current_label=expected_current_label,
    )
    if rerender_rows != before_rows:
        raise RuntimeError("Process rerender changed saved row identities/settings or current pointer")
    for stage in ("data", "fit", "export", "process"):
        active_stage = stage
        _open_modeling_stage(page, stage)
        page.wait_for_url(re.compile(rf"stage={stage}"), timeout=30_000)
        page.locator(".modeling-work-title strong").get_by_text(
            STAGE_HEADINGS[stage], exact=True
        ).wait_for(timeout=30_000)
        _wait_for_settled(page)

    _wait_modeling_process_panel(page)
    returned_panel = page.locator('[data-modeling-process-panel="ready"]')
    returned_panel.locator(".process-band-source").get_by_text(
        PROCESS_SOURCE_VISIBLE_IDENTITY, exact=True
    ).wait_for(timeout=30_000)
    if returned_panel.get_by_role("textbox", name="Processed curve label", exact=True).input_value() != draft_label:
        raise RuntimeError("Process round-trip lost the draft output label")
    if returned_panel.get_by_role("textbox", name="Save reason", exact=True).input_value() != draft_reason:
        raise RuntimeError("Process round-trip lost the draft save reason")
    returned_method = returned_panel.get_by_role("combobox", name="Evaluation method", exact=True)
    if returned_method.input_value() != draft_method:
        raise RuntimeError("Process round-trip lost the copied Evaluation method")
    if returned_panel.get_by_role("spinbutton", name="Elastic range start", exact=True).input_value() != draft_range_start:
        raise RuntimeError("Process round-trip lost the copied elastic range start")
    if returned_panel.get_by_role("spinbutton", name="Elastic range end", exact=True).input_value() != draft_range_end:
        raise RuntimeError("Process round-trip lost the copied elastic range end")
    if not returned_panel.get_by_role("button", name="Save processed curves", exact=True).is_disabled():
        raise RuntimeError("Copied Process settings unexpectedly became saveable without a new preview")
    returned_panel.locator(".process-band-result").get_by_text("210.0 GPa", exact=True).wait_for(timeout=30_000)
    returned_graph = page.locator(".persistent-modeling-plot svg[role='img']")
    returned_graph.wait_for(state="visible", timeout=30_000)
    returned_graph_box = returned_graph.bounding_box()
    if returned_graph.get_attribute("aria-label") != graph_label or returned_graph_box is None or returned_graph_box["width"] <= 0 or returned_graph_box["height"] <= 0:
        raise RuntimeError("Process round-trip did not retain the same visible engineering graph")
    after_outputs = _matching_process_outputs(
        _list_processing_outputs(page, base_url), source_pin, profile_pin
    )
    after_by_id = {
        str(item.get("processing_output_id")): item
        for item in after_outputs
        if item.get("processing_output_id")
    }
    _assert_capture_processing_output_pointer(page, expected_current_output)
    if mutation_requests:
        raise RuntimeError(f"Data→Fit→Export→Process navigation sent a forbidden mutation request: {mutation_requests!r}")
    if forbidden_preview_requests:
        raise RuntimeError(
            "Data→Fit→Export→Process navigation sent a forbidden Process preview: "
            f"{forbidden_preview_requests!r}"
        )
    if set(after_by_id) != set(before_by_id) or any(after_by_id[key] != before_by_id[key] for key in before_by_id):
        raise RuntimeError("Data→Fit→Export→Process navigation changed saved output ids or settings")
    after_rows = _assert_modeling_process_saved_rows_three(
        page,
        current_label=expected_current_label,
    )
    if after_rows != before_rows:
        raise RuntimeError("Process stage round-trip changed saved row identities/settings or current pointer")
    if expected_current_output_id not in after_by_id:
        raise RuntimeError("Process round-trip current output identity is missing after stage navigation")


def _assert_modeling_process_blocked(page: Page) -> None:
    frame = page.locator(
        '.engineering-curve-plot-empty-frame[data-plot-state="blocked"]'
    )
    frame.wait_for(state="visible", timeout=30_000)
    if frame.locator("svg .chart-axis").count() < 2 or frame.locator("svg .chart-grid").count() < 2:
        raise RuntimeError("Process blocked capture lost the visible plot axes or grid")
    if not frame.get_by_text("Restore inputs.", exact=True).is_visible():
        raise RuntimeError("Process blocked capture is missing its Restore inputs reason")
    if not page.get_by_role("button", name="Back to Data", exact=True).is_visible():
        raise RuntimeError("Process blocked capture is missing the Back to Data recovery")
    _wait_modeling_process_panel(page)
    if page.get_by_role("status", name="Loading Process controls").count():
        raise RuntimeError("Process blocked capture retained the lazy loading fallback")
    preview = page.get_by_role("button", name="Preview changes", exact=True)
    save = page.get_by_role("button", name="Save processed curves", exact=True)
    if not preview.is_disabled() or not save.is_disabled():
        raise RuntimeError("Process blocked capture left Preview or Save enabled")
    method_buttons = page.locator(".method-library .method-pill")
    rail_buttons = page.locator(".configured-step-list button:visible")
    method_buttons.first.wait_for(state="attached", timeout=30_000)
    rail_buttons.first.wait_for(timeout=30_000)
    if method_buttons.count() == 0 or any(not button.is_disabled() for button in method_buttons.all()):
        raise RuntimeError("Process blocked capture left an Add operation registry method enabled")
    if rail_buttons.count() != 5 or any(not button.is_disabled() for button in rail_buttons.all()):
        raise RuntimeError("Process blocked capture left a configured Process rail button enabled")
    if page.locator('.method-library > summary[aria-disabled="true"]').count() != 1:
        raise RuntimeError("Process blocked capture is missing the disabled Add operation summary")
    process_inputs = page.locator(".process-band-controls input, .rail-statistics-action input")
    if any(not control.is_disabled() for control in process_inputs.all()):
        raise RuntimeError("Process blocked capture left a Process range or manual input enabled")


def _assert_modeling_process_exact_read_failed(page: Page, content_gets: int | None = None) -> None:
    """Assert the settled selected-ref exact-read failure without a fallback."""
    _wait_modeling_process_panel(page)
    page.locator(".error-banner").wait_for(state="visible", timeout=30_000)
    source = page.locator(".process-band-source")
    source.wait_for(state="visible", timeout=30_000)
    if not re.fullmatch(r"Exact source unavailable · r[1-9]\d*", source.inner_text().strip()):
        raise RuntimeError(f"Exact-read failure lost the selected revision identity: {source.inner_text()!r}")
    if page.get_by_role("button", name="Retry exact source", exact=True).count() != 1:
        raise RuntimeError("Exact-read failure is missing its explicit Retry exact source action")
    if not page.get_by_role("button", name="Back to Data", exact=True).is_visible():
        raise RuntimeError("Exact-read failure is missing the Back to Data recovery")
    preview = page.get_by_role("button", name="Preview changes", exact=True)
    save = page.get_by_role("button", name="Save processed curves", exact=True)
    if not preview.is_disabled() or not save.is_disabled():
        raise RuntimeError("Exact-read failure left Preview or Save enabled")
    if page.get_by_text(re.compile(r"\b(?:210\.0|120\.0) GPa\b"), exact=False).count():
        raise RuntimeError("Exact-read failure exposed a stale Process scalar")
    frame = page.locator('.engineering-curve-plot-empty-frame[data-plot-state="blocked"]')
    frame.wait_for(state="visible", timeout=30_000)
    if frame.locator("svg .chart-axis").count() < 2 or frame.locator("svg .chart-grid").count() < 2:
        raise RuntimeError("Exact-read failure lost the retained axes/grid recovery frame")
    if content_gets is not None and content_gets != 1:
        raise RuntimeError(f"Exact-read failure made {content_gets} content GETs instead of one settled attempt")


def _assert_modeling_process_capture_ready(page: Page) -> None:
    """Re-check blocked state and responsive plot geometry after capture settling."""
    _wait_for_modeling_process_destination_state(page)
    _wait_for_modeling_process_plot_size(page)
    _assert_modeling_process_blocked(page)


def _capture_modeling_fit_states(browser: Browser, base_url: str, output: Path) -> None:
    """Capture the Fit drawer, failure, exact-source, and restored states."""

    def prepared_fit(label: str) -> Page:
        page = _new_page(browser, base_url, 1440, 900)
        _prepare_fit_from_saved_process(page, base_url, label=label)
        _click_modeling_fit_preview_and_wait(page)
        return page

    long_drawer = prepared_fit("Fit candidate drawer source")
    _long_trigger, _long_body, table = _open_fit_evidence(long_drawer)
    _assert_fit_candidate_surface(long_drawer, table)
    _assert_fit_display_scale(long_drawer, "candidate-parameters-long")
    if table.locator("tbody tr").count() < 5:
        raise RuntimeError("Fit candidate parameters drawer did not expose calculated evidence")
    _capture(
        long_drawer,
        output / "modeling-fit-candidate-parameters-long-1440x900.png",
        1440,
        900,
        focus_selector=".fit-evidence-drawer",
    )
    long_drawer.context.close()

    scrolled = prepared_fit("Fit candidate evidence source")
    _scrolled_trigger, scrolled_body, scrolled_table = _open_fit_evidence(scrolled)
    _assert_fit_candidate_surface(scrolled, scrolled_table)
    _select_warned_fit_candidate(scrolled_table)
    scrolled.get_by_role("textbox", name="Candidate selection reason", exact=True).fill(
        "Capture the full numerical evidence before the explicit engineering decision."
    )
    acknowledgement = scrolled.get_by_role(
        "checkbox", name="Acknowledge selected candidate warning", exact=True
    )
    if acknowledgement.count():
        acknowledgement.check()
    else:
        raise RuntimeError("Selected warned Fit candidate is missing its acknowledgement")
    _assert_fit_selected_evidence(scrolled)
    _scroll_fit_evidence_locally(scrolled, scrolled_body)
    _scrolled_trigger, scrolled_body, _scrolled_table = _open_fit_evidence(scrolled)

    def prepare_scrolled_capture() -> None:
        _scroll_fit_evidence_locally(scrolled, scrolled_body, close_escape=False)
        # Clear browser text selection only after the real keyboard/wheel/native
        # scrollbar interactions have been proven, so the screenshot records
        # the collapsed text-selection state rather than a synthetic highlight.
        scrolled.evaluate("() => window.getSelection()?.removeAllRanges()")

    _capture(
        scrolled,
        output / "modeling-fit-candidate-evidence-scrolled-1440x900.png",
        1440,
        900,
        focus_selector=".fit-evidence-drawer",
        before_screenshot=prepare_scrolled_capture,
    )
    scrolled.context.close()

    calculation_failed = prepared_fit("Fit calculation failure source")
    calculation_failed.route(
        "**/api/v1/metal-fit-runs",
        lambda route: route.fulfill(
            status=503,
            content_type="application/json",
            body='{"detail":"deterministic Fit calculation failure"}',
        ),
    )
    calculation_failed.get_by_role("button", name="Preview changes", exact=True).click()
    calculation_failed.get_by_role("alert").wait_for(state="visible", timeout=30_000)
    calculation_failed.locator(".persistent-modeling-plot svg[role=img]").wait_for(
        state="visible", timeout=30_000
    )
    _assert_fit_display_scale(calculation_failed, "calculation-failed")
    if calculation_failed.get_by_role(
        "button", name=re.compile(r"Preview changes|Update candidates"), exact=False
    ).count() != 1:
        raise RuntimeError("Fit calculation failure lost its explicit retry/update action")
    _capture(
        calculation_failed,
        output / "modeling-fit-calculation-failed-1440x900.png",
        1440,
        900,
    )
    calculation_failed.context.close()

    save_failed = prepared_fit("Fit save failure source")
    save_trigger, _save_body, save_table = _open_fit_evidence(save_failed)
    _assert_fit_candidate_surface(save_failed, save_table)
    _select_warned_fit_candidate(save_table)
    save_failed.get_by_role("textbox", name="Candidate selection reason", exact=True).fill(
        "Persist the selected candidate only after reviewing numerical evidence."
    )
    save_acknowledgement = save_failed.get_by_role(
        "checkbox", name="Acknowledge selected candidate warning"
    )
    if save_acknowledgement.count():
        save_acknowledgement.check()
    else:
        raise RuntimeError("Selected warned Fit candidate is missing its acknowledgement")
    _assert_fit_selected_evidence(save_failed)
    _close_fit_evidence(save_failed, save_trigger)
    save_failed.route(
        "**/api/v1/processing-outputs",
        lambda route: route.fulfill(
            status=503,
            content_type="application/json",
            body='{"detail":"deterministic Fit save failure"}',
        ),
    )
    save_failed.get_by_role("button", name="Save fit & continue", exact=True).click()
    save_failed.get_by_role("alert").wait_for(state="visible", timeout=30_000)
    if (
        save_failed.get_by_role(
            "button", name=re.compile(r"Save fit & continue|Retry save"), exact=False
        ).count()
        < 1
    ):
        raise RuntimeError("Fit save failure lost its explicit retry action")
    save_failed.locator(".persistent-modeling-plot svg[role=img]").wait_for(
        state="visible", timeout=30_000
    )
    _capture(save_failed, output / "modeling-fit-save-failed-1440x900.png", 1440, 900)
    save_failed.context.close()

    fit_blocked = _new_page(browser, base_url, 1440, 900)
    _prepare_fit_from_saved_process(fit_blocked, base_url, label="Fit blocked source")
    fit_blocked.evaluate(
        """() => {
          const key = 'cmp.modeling.recent-session.v4';
          const session = JSON.parse(window.sessionStorage.getItem(key) || '{}');
          delete session.processingOutput;
          window.sessionStorage.setItem(key, JSON.stringify(session));
        }"""
    )
    fit_blocked.goto(f"{base_url}/modeling?stage=fit&family=metal")
    fit_blocker_message = "No saved Process Output is bound. Save Process before calculating Fit."
    fit_plot_overlay = fit_blocked.locator(
        "#modeling-fit .engineering-curve-plot-empty-overlay"
    )
    fit_plot_overlay.get_by_text(
        fit_blocker_message,
        exact=True,
    ).wait_for(state="visible", timeout=30_000)
    fit_source_binding = fit_blocked.locator(".fit-source-binding.missing")
    fit_source_binding.wait_for(state="visible", timeout=30_000)
    if fit_source_binding.inner_text().strip() != fit_blocker_message:
        raise RuntimeError("Fit exact-source blocker lost its settings binding status")
    fit_blocked.get_by_role("button", name="Back to Process", exact=True).wait_for(
        state="visible", timeout=30_000
    )
    process_stage = fit_blocked.get_by_role("button", name=re.compile(r"^Process\b"))
    if process_stage.count() != 1 or not process_stage.is_visible():
        raise RuntimeError("Fit exact-source blocker lost its visible return-to-Process recovery")
    blocked_session = _modeling_session(fit_blocked)
    blocked_workspace = blocked_session.get("workspace")
    if not isinstance(blocked_workspace, dict):
        raise RuntimeError("Fit blocked capture lost its workspace session state")
    blocked_history = {
        item.get("processing_output_id")
        for item in _list_processing_outputs(fit_blocked, base_url)
    }
    _capture(fit_blocked, output / "modeling-fit-exact-source-blocked-1440x900.png", 1440, 900)
    # Arm the recovery-only request assertion after the blocked screenshot has
    # settled.  The screenshot path may refresh read-only data while it settles;
    # only the explicit Back to Process action and its readback belong here.
    blocked_requests: list[str] = []

    def record_blocked_recovery_request(request: object) -> None:
        method = str(getattr(request, "method", "")).upper()
        url = str(getattr(request, "url", ""))
        blocked_requests.append(f"{method} {url}")

    fit_blocked.on("request", record_blocked_recovery_request)
    try:
        fit_blocked.get_by_role("button", name="Back to Process", exact=True).click()
        fit_blocked.wait_for_url(re.compile(r"stage=process"), timeout=30_000)
        recovered_session = _modeling_session(fit_blocked)
        recovered_workspace = recovered_session.get("workspace")
        if not isinstance(recovered_workspace, dict):
            raise RuntimeError("Fit blocked recovery lost its workspace session state")
        if recovered_workspace.get("selectedTestDataRefs") != blocked_workspace.get("selectedTestDataRefs"):
            raise RuntimeError("Fit blocked recovery changed the exact selected Test Data refs")
        if recovered_workspace.get("visibleTestDataKeys") != blocked_workspace.get("visibleTestDataKeys"):
            raise RuntimeError("Fit blocked recovery changed visible exact Test Data identities")
        if recovered_session.get("processingOutput") != blocked_session.get("processingOutput"):
            raise RuntimeError("Fit blocked recovery changed the saved-output pointer")
        recovered_history = {
            item.get("processing_output_id")
            for item in _list_processing_outputs(fit_blocked, base_url)
        }
        if recovered_history != blocked_history:
            raise RuntimeError("Fit blocked recovery changed Processing Output history")
        if any(not request.startswith("GET ") for request in blocked_requests):
            raise RuntimeError(f"Fit blocked recovery issued a mutation request: {blocked_requests!r}")
    finally:
        fit_blocked.remove_listener("request", record_blocked_recovery_request)
    fit_blocked.context.close()

    exact_read_failed = prepared_fit("Fit exact-read failure source")
    fit_saved = False
    exact_content_requests: list[str] = []
    request_methods: list[str] = []
    exact_read_failed.on(
        "request",
        lambda request: request_methods.append(request.method),
    )

    def arm_after_fit_save(route: Route) -> None:
        nonlocal fit_saved
        if route.request.method == "POST":
            fit_saved = True
        route.continue_()

    def fail_saved_fit_content(route: Route) -> None:
        if not fit_saved:
            route.continue_()
            return
        exact_content_requests.append(route.request.url)
        route.fulfill(
            status=503,
            content_type="application/json",
            body='{"detail":"deterministic saved Fit exact-read failure"}',
        )

    # The Fit save itself remains real.  Once its immutable pointer exists,
    # fail only the exact saved-output content GET; this keeps the previously
    # valid Fit graph/selection visible while exercising the restore retry.
    exact_read_failed.route("**/api/v1/processing-outputs", arm_after_fit_save)
    exact_read_failed.route(
        "**/api/v1/processing-outputs/*/content", fail_saved_fit_content
    )
    _save_exact_fit_selection(
        exact_read_failed,
        allow_expected_exact_restore_failure=True,
    )
    saved_fit_pointer = _modeling_session(exact_read_failed).get("processingOutput")
    if not isinstance(saved_fit_pointer, dict) or not isinstance(saved_fit_pointer.get("id"), str):
        raise RuntimeError("Fit exact-read failure setup did not produce an exact saved pointer")
    exact_read_failed.get_by_text(
        "Saved Fit result unavailable", exact=False
    ).wait_for(timeout=30_000)
    retry_saved_fit = exact_read_failed.get_by_role(
        "button", name="Retry exact saved Fit", exact=True
    )
    if retry_saved_fit.count() != 1:
        raise RuntimeError("Fit exact saved-output read failure lost its explicit retry action")
    if exact_read_failed.get_by_role(
        "img", name="Hardening candidate and selected extrapolation curves", exact=True
    ).count() != 1:
        raise RuntimeError("Fit exact-read failure replaced the last valid graph")
    failed_trigger, _failed_body, _failed_table = _open_fit_evidence(exact_read_failed)
    _assert_fit_selected_evidence(exact_read_failed)
    if exact_read_failed.get_by_role(
        "textbox", name="Candidate selection reason", exact=True
    ).input_value() != "Best agreement over the measured strain range.":
        raise RuntimeError("Fit exact-read failure lost the original selection reason")
    if exact_read_failed.get_by_role(
        "checkbox", name="Acknowledge selected candidate warning", exact=True
    ).is_checked() is not True:
        raise RuntimeError("Fit exact-read failure lost the warning acknowledgement")
    _close_fit_evidence(exact_read_failed, failed_trigger)
    if len(exact_content_requests) != 1:
        raise RuntimeError(
            f"Fit exact-read failure made {len(exact_content_requests)} exact content GETs before retry"
        )
    expected_content_url = (
        f"{base_url}/api/v1/processing-outputs/{saved_fit_pointer['id']}/content"
    )
    if exact_content_requests != [expected_content_url]:
        raise RuntimeError(
            f"Fit exact-read failure did not read the pinned saved Fit URL: {exact_content_requests!r}"
        )
    methods_before_retry = len(request_methods)
    pointer_before_retry = _modeling_session(exact_read_failed).get("processingOutput")
    retry_saved_fit.click()
    exact_read_failed.get_by_text(
        "Saved Fit result unavailable", exact=False
    ).wait_for(timeout=30_000)
    if len(exact_content_requests) != 2 or exact_content_requests[1] != expected_content_url:
        raise RuntimeError(
            f"Fit exact saved-output retry did not repeat the same exact URL: {exact_content_requests!r}"
        )
    if any(method != "GET" for method in request_methods[methods_before_retry:]):
        raise RuntimeError(
            f"Fit exact saved-output retry issued a non-GET mutation: {request_methods[methods_before_retry:]!r}"
        )
    if _modeling_session(exact_read_failed).get("processingOutput") != pointer_before_retry:
        raise RuntimeError("Fit exact saved-output retry mutated the current pointer")
    _capture(
        exact_read_failed,
        output / "modeling-fit-exact-read-failed-1440x900.png",
        1440,
        900,
    )
    exact_read_failed.context.close()

    restored = prepared_fit("Fit restored source")
    _save_exact_fit_selection(restored)
    restored_session = _modeling_session(restored)
    restored_pointer = restored_session.get("processingOutput")
    if not isinstance(restored_pointer, dict) or not all(
        isinstance(restored_pointer.get(key), str) and restored_pointer.get(key)
        for key in ("id", "revisionId", "label")
    ):
        raise RuntimeError("Fit save did not leave an exact session output pointer for restore")
    restore_requests: list[tuple[str, str]] = []
    restored.on(
        "request",
        lambda request: restore_requests.append((request.method, request.url)),
    )
    restored.goto(f"{base_url}/modeling?stage=fit&family=metal")
    restored.get_by_text(
        "Saved immutable Fit Output restored with its exact Process source and decision.",
        exact=False,
    ).wait_for(timeout=30_000)
    restored.get_by_role("img", name="Hardening candidate and selected extrapolation curves", exact=True).wait_for(
        state="visible", timeout=30_000
    )
    restored.get_by_role("button", name="Preview changes", exact=True).wait_for(timeout=30_000)
    persisted_outputs = _list_processing_outputs(restored, base_url)
    persisted = next(
        (
            item for item in persisted_outputs
            if _has_processing_output_revision(
                item, restored_pointer.get("id"), restored_pointer.get("revisionId")
            )
        ),
        None,
    )
    decision = persisted.get("fit_decision") if isinstance(persisted, dict) else None
    if (
        not isinstance(decision, dict)
        or not decision.get("candidate_key")
        or not decision.get("selection_reason")
    ):
        raise RuntimeError("Restored Fit output lost its selected candidate/reason evidence")
    if decision.get("warning_acknowledged") is not True:
        raise RuntimeError("Restored Fit output lost its warning acknowledgement")
    if not isinstance(persisted.get("steps") if isinstance(persisted, dict) else None, list):
        raise RuntimeError("Restored Fit output lost its ordered calculation steps")
    source_pin = persisted.get("source_processing_output") if isinstance(persisted, dict) else None
    source_output = next(
        (
            item for item in persisted_outputs
            if isinstance(source_pin, dict)
            and _has_processing_output_revision(
                item, source_pin.get("aggregate_id"), source_pin.get("revision_id")
            )
        ),
        None,
    )
    if not isinstance(source_output, dict) or not isinstance(source_output.get("current_revision"), dict):
        raise RuntimeError("Restored Fit output lost its exact Process source identity")
    source_binding_text = restored.locator(".fit-source-binding").inner_text()
    source_revision_record = source_output.get("current_revision")
    if not isinstance(source_revision_record, dict):
        raise RuntimeError("Restored Fit source revision record is unavailable")
    source_revision = source_revision_record.get("revision_no")
    source_digest = source_output.get("output_sha256")
    source_label = source_output.get("label")
    if (
        not isinstance(source_label, str)
        or source_label not in source_binding_text
        or f"r{source_revision}" not in source_binding_text
        or not isinstance(source_digest, str)
        or source_digest[:12] not in source_binding_text
    ):
        raise RuntimeError(f"Restored Fit source binding lost label/revision/digest: {source_binding_text!r}")
    saved_binding_text = restored.locator(".fit-source-binding").inner_text()
    saved_revision_record = persisted.get("current_revision") if isinstance(persisted, dict) else None
    if not isinstance(saved_revision_record, dict):
        raise RuntimeError("Restored Fit output revision identity is unavailable")
    saved_revision_no = saved_revision_record.get("revision_no")
    if (
        not isinstance(restored_pointer.get("label"), str)
        or restored_pointer["label"] not in saved_binding_text
        or f"r{saved_revision_no}" not in saved_binding_text
    ):
        raise RuntimeError("Restored Fit output lost its saved label/revision identity")
    restore_trigger, _restore_body, restore_table = _open_fit_evidence(restored)
    _assert_fit_selected_evidence(restored)
    selected_rows = restore_table.locator("tbody tr.selected")
    if selected_rows.count() != 1:
        raise RuntimeError("Restored Fit output lost the selected candidate row")
    if restored.get_by_role("textbox", name="Candidate selection reason", exact=True).input_value() != "Best agreement over the measured strain range.":
        raise RuntimeError("Restored Fit output lost the original selection reason")
    if restored.get_by_role("checkbox", name="Acknowledge selected candidate warning", exact=True).is_checked() is not True:
        raise RuntimeError("Restored Fit output lost the checked warning acknowledgement")
    _close_fit_evidence(restored, restore_trigger)
    content_urls = [url for method, url in restore_requests if method == "GET" and urlsplit(url).path.endswith("/content")]
    if len(content_urls) != 1:
        raise RuntimeError(f"Restored Fit reload made {len(content_urls)} exact content GETs: {restore_requests!r}")
    expected_restore_url = f"{base_url}/api/v1/processing-outputs/{restored_pointer['id']}/content"
    if content_urls != [expected_restore_url]:
        raise RuntimeError(f"Restored Fit reload used a non-exact content URL: {content_urls!r}")
    if any(method != "GET" for method, _url in restore_requests):
        raise RuntimeError(f"Restored Fit reload issued a non-GET request: {restore_requests!r}")
    _capture(restored, output / "modeling-fit-restored-1440x900.png", 1440, 900)
    restored.context.close()


def _capture_modeling_process_fit(
    browser: Browser, base_url: str, output: Path
) -> list[dict[str, object]]:
    measurements: list[dict[str, object]] = []
    for width, height in (*VIEWPORTS, *WIDE_VIEWPORTS):
        page = _new_page(browser, base_url, width, height)
        _prepare_modeling_process(page, base_url)
        if page.locator(".modeling-stage-number:visible").count():
            raise RuntimeError("Process/Fit capture received the retired numbered stage strip")
        if page.locator(".stage-process > .section-heading:visible").count():
            raise RuntimeError("Process capture received the retired duplicate workspace heading")
        page.locator(".modeling-workspace-rail .rail-heading").get_by_text(
            "Curves", exact=True
        ).wait_for(timeout=30_000)
        _save_process_output_for_fit(
            page,
            label=f"Fit source Process result {width}x{height}",
            reason="Bind one immutable Process result as the exact Fit source.",
        )
        _capture(
            page,
            output / f"modeling-process-{width}x{height}.png",
            width,
            height,
            before_screenshot=_process_plot_capture_callback(page),
        )
        measurements.append(
            {
                "stage": "process",
                "viewport": f"{width}x{height}",
                **_measure_process_fit(page, "process", width, height),
            }
        )

        _open_modeling_stage(page, "fit")
        page.locator(".modeling-work-title strong").get_by_text(
            STAGE_HEADINGS["fit"], exact=True
        ).wait_for(timeout=30_000)
        _click_modeling_fit_preview_and_wait(page)
        trigger, _body, table = _open_fit_evidence(page)
        _assert_fit_candidate_surface(page, table)
        if page.get_by_role("button", name="Save fit & continue", exact=True).count() != 1:
            raise RuntimeError("Fit must expose one top-row Save fit & continue action")
        _select_warned_fit_candidate(table)
        page.get_by_role("textbox", name="Candidate selection reason").fill(
            "Best agreement over the measured strain range."
        )
        acknowledgement = page.get_by_role(
            "checkbox", name="Acknowledge selected candidate warning"
        )
        if acknowledgement.count():
            acknowledgement.check()
        else:
            raise RuntimeError("Selected warned Fit candidate is missing its acknowledgement")
        _assert_fit_selected_evidence(page)
        if page.get_by_role("button", name="Save fit & continue", exact=True).is_disabled():
            raise RuntimeError("Fit selection did not enable the top-row save action")
        _close_fit_evidence(page, trigger)
        _assert_fit_display_scale(page, "normal")
        _capture(page, output / f"modeling-fit-{width}x{height}.png", width, height)
        measurements.append(
            {
                "stage": "fit",
                "viewport": f"{width}x{height}",
                **_measure_process_fit(page, "fit", width, height),
            }
        )
        page.context.close()

    _capture_modeling_fit_states(browser, base_url, output)
    return measurements


def _capture_modeling_process_only(
    browser: Browser,
    base_url: str,
    output: Path,
    *,
    resume_modeling_process: bool = False,
) -> list[dict[str, object]]:
    measurements: list[dict[str, object]] = []
    for width, height in (*VIEWPORTS, *WIDE_VIEWPORTS):
        page = _new_page(browser, base_url, width, height)
        _prepare_modeling_process(page, base_url)
        page.wait_for_url(re.compile(r"stage=process"), timeout=30_000)
        page.locator(".modeling-work-title strong").get_by_text(
            STAGE_HEADINGS["process"], exact=True
        ).wait_for(timeout=30_000)
        page.locator(".modeling-workspace-rail .rail-heading").get_by_text(
            "Curves", exact=True
        ).wait_for(timeout=30_000)
        _wait_modeling_process_panel(page)
        _assert_modeling_process_preview(page)
        _assert_modeling_process_draft_geometry(page)
        if width == 1366:
            linear_method = page.locator(
                '[data-modeling-process-panel="ready"] select[aria-label="Evaluation method"]'
            )
            linear_method.select_option("linear_regression")
            _click_modeling_process_preview_and_wait(page)
            _wait_for_modeling_process_plot_size(page)
            if linear_method.input_value() != "linear_regression":
                raise RuntimeError("Linear regression Process capture did not settle on its target method")
            _assert_modeling_process_geometry(page)
            _capture(
                page,
                output / "modeling-process-linear-regression-1366x768.png",
                width,
                height,
                before_screenshot=_process_plot_capture_callback(page),
            )
            _assert_modeling_process_manual_surface(page)
        _capture(
            page,
            output / f"modeling-process-{width}x{height}.png",
            width,
            height,
            before_screenshot=_process_plot_capture_callback(page),
        )
        measurements.append(
            {
                "stage": "process",
                "viewport": f"{width}x{height}",
                **_measure_process_fit(page, "process", width, height),
            }
        )
        page.context.close()

    blocked = _new_page(browser, base_url, 1440, 900)
    _prepare_modeling_process(blocked, base_url)
    blocked.add_init_script(
        """(() => {
          const key = 'cmp.modeling.recent-session.v4';
          const session = JSON.parse(window.sessionStorage.getItem(key) || '{}');
          delete session.testData;
          session.workspace = {
            ...(session.workspace || {}),
            selectedTestDataRefs: [], selectedDocumentIds: [], visibleTestDataKeys: []
          };
          window.sessionStorage.setItem(key, JSON.stringify(session));
        })();"""
    )
    blocked.goto(f"{base_url}/modeling?stage=process&family=metal")
    _wait_for_settled(blocked)
    _wait_for_modeling_process_destination_state(blocked)
    _wait_for_modeling_process_plot_size(blocked)
    _assert_modeling_process_blocked(blocked)
    _capture(
        blocked,
        output / "modeling-process-blocked-1440x900.png",
        1440,
        900,
        before_screenshot=lambda: _assert_modeling_process_capture_ready(blocked),
    )
    blocked.context.close()

    failed = _new_page(browser, base_url, 1440, 900)
    _prepare_modeling_process(failed, base_url)
    failed_content_gets = 0

    def fail_exact_source(route: Route) -> None:
        nonlocal failed_content_gets
        failed_content_gets += 1
        route.fulfill(
            status=503,
            content_type="application/json",
            body='{"detail":"deterministic exact source read failure"}',
        )

    failed.route("**/api/v1/test-data-documents/**/content", fail_exact_source)
    failed.reload()
    failed.wait_for_url(re.compile(r"stage=process"), timeout=30_000)
    failed.locator(".modeling-work-title strong").get_by_text(
        STAGE_HEADINGS["process"], exact=True
    ).wait_for(timeout=30_000)
    failed.get_by_role("button", name="Retry exact source", exact=True).wait_for(timeout=30_000)
    _assert_modeling_process_exact_read_failed(failed, failed_content_gets)
    _capture(
        failed,
        output / "modeling-process-exact-read-failed-1440x900.png",
        1440,
        900,
        before_screenshot=lambda: _assert_modeling_process_exact_read_failed(failed, failed_content_gets),
    )
    failed.context.close()

    siblings = _new_page(browser, base_url, 1440, 900)
    _prepare_modeling_process(siblings, base_url)
    source_pin, profile_pin = _process_session_pins(siblings)
    listed_outputs = _list_processing_outputs(siblings, base_url)
    _assert_no_mis_pinned_capture_labels(listed_outputs, source_pin, profile_pin)
    initial_outputs = _matching_capture_process_outputs(
        listed_outputs, source_pin, profile_pin
    )
    _filter_capture_process_output_list(siblings, source_pin, profile_pin)
    siblings.reload()
    siblings.wait_for_url(re.compile(r"stage=process"), timeout=30_000)
    siblings.locator(".modeling-work-title strong").get_by_text(
        STAGE_HEADINGS["process"], exact=True
    ).wait_for(timeout=30_000)
    _wait_modeling_process_panel(siblings)
    resumed_existing_primary = False
    resume_output_posts: list[str] = []
    if resume_modeling_process:
        if len(initial_outputs) != 3:
            raise RuntimeError(
                "Modeling Process resume requires exactly three matching saved outputs; "
                f"got {len(initial_outputs)}"
            )
        resumed_by_label = _assert_resumable_modeling_process_outputs(
            initial_outputs, source_pin, profile_pin
        )
        elastic_output = resumed_by_label["Elastic window 0.0005-0.0025"]
        def record_resume_output_post(request: object) -> None:
            if (
                getattr(request, "method", "") == "POST"
                and urlsplit(getattr(request, "url", "")).path.endswith("/processing-outputs")
            ):
                resume_output_posts.append(str(getattr(request, "url", "")))

        siblings.on("request", record_resume_output_post)
        _patch_capture_processing_output_pointer(siblings, elastic_output)
        _assert_capture_processing_output_pointer(siblings, elastic_output)
        siblings.reload()
        siblings.wait_for_url(re.compile(r"stage=process"), timeout=30_000)
        siblings.locator(".modeling-work-title strong").get_by_text(
            STAGE_HEADINGS["process"], exact=True
        ).wait_for(timeout=30_000)
        _wait_modeling_process_panel(siblings)
        _assert_capture_processing_output_pointer(siblings, elastic_output)
        _assert_modeling_process_saved_rows_three(
            siblings,
            current_label="Elastic window 0.0005-0.0025",
        )
        if resume_output_posts:
            raise RuntimeError(
                "Modeling Process resume unexpectedly posted a Processing Output: "
                f"{resume_output_posts!r}"
            )
        siblings.remove_listener("request", record_resume_output_post)
        resumed_existing_primary = True
        final_outputs = _matching_capture_process_outputs(
            _list_processing_outputs(siblings, base_url), source_pin, profile_pin
        )
        if {
            output.get("processing_output_id") for output in final_outputs
        } != {
            output.get("processing_output_id") for output in initial_outputs
        }:
            raise RuntimeError("Modeling Process resume changed the immutable output identities")
        final_output = final_outputs[
            next(
                index
                for index, output in enumerate(final_outputs)
                if output.get("processing_output_id") == elastic_output.get("processing_output_id")
            )
        ]
    elif len(initial_outputs) not in (0, 2):
        raise RuntimeError(
            "Process capture requires exactly zero or two matching saved outputs before the sibling flow; "
            f"got {len(initial_outputs)}"
        )
    elif len(initial_outputs) == 2:
        labels = [output.get("label") for output in initial_outputs]
        if set(labels) != {"Robust elastic", "Chord elastic"} or len(set(labels)) != 2:
            raise RuntimeError(f"Existing Process siblings have duplicate or missing labels: {labels!r}")
        output_ids = [output.get("processing_output_id") for output in initial_outputs]
        if any(not isinstance(output_id, str) or not output_id for output_id in output_ids) or len(set(output_ids)) != 2:
            raise RuntimeError(f"Existing Process siblings have duplicate or missing identities: {output_ids!r}")
        for saved_output in initial_outputs:
            label = saved_output.get("label")
            if label == "Robust elastic":
                _assert_process_output_configuration(
                    saved_output,
                    source_pin,
                    profile_pin,
                    expected_label="Robust elastic",
                    expected_method="robust_huber",
                    expected_minimum=0.0002,
                    expected_maximum=0.002,
                )
            elif label == "Chord elastic":
                _assert_process_output_configuration(
                    saved_output,
                    source_pin,
                    profile_pin,
                    expected_label="Chord elastic",
                    expected_method="chord",
                    expected_minimum=0.001,
                    expected_maximum=0.003,
                )
            else:
                raise RuntimeError(f"Unexpected Process sibling label: {label!r}")
        _assert_modeling_process_saved_rows(siblings)

        # Read the real persisted Chord identity again from the authenticated
        # browser session.  The pointer must never be manufactured from a
        # capture constant or inferred from row order.
        resumed_outputs = _matching_capture_process_outputs(
            _list_processing_outputs(siblings, base_url), source_pin, profile_pin
        )
        if len(resumed_outputs) != 2 or {
            output.get("processing_output_id") for output in resumed_outputs
        } != {
            output.get("processing_output_id") for output in initial_outputs
        }:
            raise RuntimeError("Process sibling list changed while resuming the existing outputs")
        for resumed_output in resumed_outputs:
            label = resumed_output.get("label")
            if label == "Robust elastic":
                _assert_process_output_configuration(
                    resumed_output,
                    source_pin,
                    profile_pin,
                    expected_label="Robust elastic",
                    expected_method="robust_huber",
                    expected_minimum=0.0002,
                    expected_maximum=0.002,
                )
            elif label == "Chord elastic":
                _assert_process_output_configuration(
                    resumed_output,
                    source_pin,
                    profile_pin,
                    expected_label="Chord elastic",
                    expected_method="chord",
                    expected_minimum=0.001,
                    expected_maximum=0.003,
                )
            else:
                raise RuntimeError(f"Unexpected resumed Process sibling label: {label!r}")
        chord_output = next(
            resumed_output
            for resumed_output in resumed_outputs
            if resumed_output.get("label") == "Chord elastic"
        )
        _patch_capture_processing_output_pointer(siblings, chord_output)
        siblings.reload()
        siblings.wait_for_url(re.compile(r"stage=process"), timeout=30_000)
        siblings.locator(".modeling-work-title strong").get_by_text(
            STAGE_HEADINGS["process"], exact=True
        ).wait_for(timeout=30_000)
        _wait_modeling_process_panel(siblings)
        _assert_modeling_process_saved_rows(siblings, require_current_and_history=True)
    else:
        _assert_modeling_process_preview(siblings)
        label = siblings.get_by_role("textbox", name="Processed curve label")
        reason = siblings.get_by_role("textbox", name="Save reason")
        save = siblings.get_by_role("button", name="Save processed curves", exact=True)
        label.fill("Robust elastic")
        reason.fill("Capture deterministic saved-result sibling one")
        save.click()
        siblings.get_by_text("Processed result saved and current", exact=False).wait_for(timeout=30_000)
        siblings.get_by_role("combobox", name="Evaluation method", exact=True).select_option("chord")
        siblings.get_by_role("spinbutton", name="Elastic range start", exact=True).fill("0.001")
        siblings.get_by_role("spinbutton", name="Elastic range end", exact=True).fill("0.003")
        _assert_modeling_process_preview(siblings, expected_modulus="120.0 GPa", method_label="Chord")
        label.fill("Chord elastic")
        reason.fill("Capture deterministic saved-result sibling two")
        save.click()
        siblings.get_by_text("Processed result saved and current", exact=False).wait_for(timeout=30_000)
        saved_outputs = _matching_capture_process_outputs(
            _list_processing_outputs(siblings, base_url), source_pin, profile_pin
        )
        if len(saved_outputs) != 2:
            raise RuntimeError(f"Process capture did not create exactly two matching outputs: {saved_outputs!r}")
        saved_ids = [output_item.get("processing_output_id") for output_item in saved_outputs]
        if any(not isinstance(output_id, str) or not output_id for output_id in saved_ids) or len(set(saved_ids)) != 2:
            raise RuntimeError(f"Newly saved Process siblings have duplicate or missing identities: {saved_ids!r}")
        for output_item in saved_outputs:
            label_value = output_item.get("label")
            if label_value == "Robust elastic":
                _assert_process_output_configuration(
                    output_item,
                    source_pin,
                    profile_pin,
                    expected_label="Robust elastic",
                    expected_method="robust_huber",
                    expected_minimum=0.0002,
                    expected_maximum=0.002,
                )
            elif label_value == "Chord elastic":
                _assert_process_output_configuration(
                    output_item,
                    source_pin,
                    profile_pin,
                    expected_label="Chord elastic",
                    expected_method="chord",
                    expected_minimum=0.001,
                    expected_maximum=0.003,
                )
            else:
                raise RuntimeError(f"Unexpected newly saved Process sibling label: {label_value!r}")
        _assert_modeling_process_saved_rows(siblings, require_current_and_history=True)
    if resumed_existing_primary:
        # Resume keeps the three exact immutable outputs.  Copy the current
        # Elastic window through the real row action so the saved current
        # pointer survives while the exact draft is restored.
        resume_preview_posts: list[str] = []

        def record_resume_action_request(request: object) -> None:
            if getattr(request, "method", "") != "POST":
                return
            path = urlsplit(getattr(request, "url", "")).path
            if path.endswith("/processing-outputs"):
                resume_output_posts.append(str(getattr(request, "url", "")))
            elif path.endswith("/processing:preview"):
                resume_preview_posts.append(str(getattr(request, "url", "")))

        siblings.on("request", record_resume_action_request)
        resume_details = siblings.locator("details.process-saved-results")
        resume_current_row = resume_details.locator(".process-comparison-row").filter(
            has_text="Elastic window 0.0005-0.0025"
        )
        if resume_current_row.count() != 1:
            raise RuntimeError(
                "Resumed Process could not resolve exactly one current Elastic window row"
            )
        resume_current_row.get_by_role("button", name="Use settings", exact=True).click()
        siblings.get_by_text(
            "Saved Process settings restored as a new draft", exact=False
        ).wait_for(timeout=30_000)
        siblings.wait_for_timeout(350)
        if resume_preview_posts:
            raise RuntimeError(
                "Current Elastic Use settings implicitly posted a Process preview: "
                f"{resume_preview_posts!r}"
            )
        if resume_output_posts:
            raise RuntimeError(
                "Current Elastic Use settings unexpectedly posted a Processing Output: "
                f"{resume_output_posts!r}"
            )
        _assert_capture_processing_output_pointer(siblings, elastic_output)
        resume_panel = siblings.locator('[data-modeling-process-panel="ready"]')
        resume_method = resume_panel.get_by_role(
            "combobox", name="Evaluation method", exact=True
        )
        resume_start = resume_panel.get_by_role(
            "spinbutton", name="Elastic range start", exact=True
        )
        resume_end = resume_panel.get_by_role(
            "spinbutton", name="Elastic range end", exact=True
        )
        if (
            resume_method.input_value() != "robust_huber"
            or resume_start.input_value() != "0.0005"
            or resume_end.input_value() != "0.0025"
        ):
            raise RuntimeError(
                "Current Elastic Use settings did not copy robust_huber 0.0005–0.0025"
            )
        if not resume_panel.get_by_role(
            "button", name="Save processed curves", exact=True
        ).is_disabled():
            raise RuntimeError(
                "Current Elastic Use settings enabled Save before a new preview"
            )
        resume_rows_after_use = _assert_modeling_process_saved_rows_three(
            siblings,
            current_label="Elastic window 0.0005-0.0025",
        )
        if not any(
            "Elastic window 0.0005-0.0025" in row and "current" in row
            for row in resume_rows_after_use
        ):
            raise RuntimeError("Current Elastic Use settings changed the current pointer")

        # Only the explicit Preview action may issue the Process preview; it
        # must keep the exact current output and produce no new saved output.
        preview_posts_before_explicit = len(resume_preview_posts)
        _click_modeling_process_preview_and_wait(siblings)
        resume_panel.locator(".process-band-result").get_by_text(
            "210.0 GPa", exact=True
        ).wait_for(timeout=30_000)
        if (
            len(resume_preview_posts) != preview_posts_before_explicit + 1
            or resume_output_posts
        ):
            raise RuntimeError(
                "Resumed Process explicit preview changed the forbidden request set: "
                f"previews={resume_preview_posts!r}, outputs={resume_output_posts!r}"
            )
        if (
            resume_method.input_value() != "robust_huber"
            or resume_start.input_value() != "0.0005"
            or resume_end.input_value() != "0.0025"
        ):
            raise RuntimeError(
                "Resumed Process explicit preview drifted from the saved Elastic window settings"
            )
        _assert_capture_processing_output_pointer(siblings, elastic_output)
        _wait_for_modeling_process_plot_size(siblings)
        siblings.locator('.persistent-modeling-plot svg[role="img"]').wait_for(
            state="visible", timeout=30_000
        )
        siblings.remove_listener("request", record_resume_action_request)
    if not resumed_existing_primary:
        # The primary journey adds one new immutable result after the deterministic
        # two-sibling setup. Preview and save exactly once with the approved Auto
        # robust elastic window before exercising historical Use settings.
        primary_panel = siblings.locator('[data-modeling-process-panel="ready"]')
        primary_method = primary_panel.get_by_role("combobox", name="Evaluation method", exact=True)
        primary_start = primary_panel.get_by_role("spinbutton", name="Elastic range start", exact=True)
        primary_end = primary_panel.get_by_role("spinbutton", name="Elastic range end", exact=True)
        primary_method.select_option("robust_huber")
        primary_start.fill("0.0005")
        primary_end.fill("0.0025")
        _click_modeling_process_preview_and_wait(siblings)
        _wait_for_modeling_process_plot_size(siblings)
        if primary_method.input_value() != "robust_huber":
            raise RuntimeError("Primary Process preview method drifted from Auto robust")
        if primary_start.input_value() != "0.0005" or primary_end.input_value() != "0.0025":
            raise RuntimeError("Primary Process preview elastic range drifted from 0.0005–0.0025")
        primary_panel.locator(".process-band-result").get_by_text("210.0 GPa", exact=True).wait_for(timeout=30_000)
        primary_label = siblings.get_by_role("textbox", name="Processed curve label", exact=True)
        primary_reason = siblings.get_by_role("textbox", name="Save reason", exact=True)
        primary_save = siblings.get_by_role("button", name="Save processed curves", exact=True)
        primary_label.fill("Elastic window 0.0005-0.0025")
        primary_reason.fill("Baseline elastic evaluation for DP780 review")
        primary_save.click()
        siblings.get_by_text("Processed result saved and current", exact=False).wait_for(timeout=30_000)
        final_outputs = _matching_capture_process_outputs(
            _list_processing_outputs(siblings, base_url), source_pin, profile_pin
        )
        if len(final_outputs) != 3:
            raise RuntimeError(f"Process primary journey did not reach exactly three outputs: {final_outputs!r}")
        try:
            final_output = next(
                item
                for item in final_outputs
                if item.get("label") == "Elastic window 0.0005-0.0025"
            )
        except StopIteration as cause:
            raise RuntimeError("Process primary journey lost the new Elastic window output") from cause
        _assert_process_output_configuration(
            final_output,
            source_pin,
            profile_pin,
            expected_label="Elastic window 0.0005-0.0025",
            expected_method="robust_huber",
            expected_minimum=0.0005,
            expected_maximum=0.0025,
        )
        _assert_modeling_process_saved_rows_three(siblings, current_label="Elastic window 0.0005-0.0025")

    # History settings are a local draft action.  It must not create another
    # persisted output or replace the newly saved output identity on the server.
    history_output_posts: list[str] = []
    history_preview_posts: list[str] = []

    def record_history_output_post(request: object) -> None:
        if getattr(request, "method", "") != "POST":
            return
        path = urlsplit(getattr(request, "url", "")).path
        if path.endswith("/processing-outputs"):
            history_output_posts.append(str(getattr(request, "url", "")))
        elif path.endswith("/processing:preview"):
            history_preview_posts.append(str(getattr(request, "url", "")))

    siblings.on("request", record_history_output_post)
    preview_posts_before_history = len(history_preview_posts)
    details = siblings.locator("details.process-saved-results")
    history_row = details.locator(".process-comparison-row").filter(has_text="Chord elastic")
    history_row.get_by_role("button", name="Use settings", exact=True).click()
    siblings.get_by_text("Saved Process settings restored as a new draft", exact=False).wait_for(timeout=30_000)
    siblings.wait_for_timeout(350)
    if len(history_preview_posts) != preview_posts_before_history:
        raise RuntimeError(
            "Use settings implicitly posted a Process preview: "
            f"{history_preview_posts[preview_posts_before_history:]!r}"
        )
    if history_output_posts:
        raise RuntimeError(f"Use settings unexpectedly posted a Processing Output: {history_output_posts!r}")
    after_history_outputs = _matching_capture_process_outputs(
        _list_processing_outputs(siblings, base_url), source_pin, profile_pin
    )
    if {item.get("processing_output_id") for item in after_history_outputs} != {
        item.get("processing_output_id") for item in final_outputs
    }:
        raise RuntimeError("Use settings changed the persisted Process output identities")
    if not any(item.get("processing_output_id") == final_output.get("processing_output_id") for item in after_history_outputs):
        raise RuntimeError("Use settings lost the newly saved current Process output identity")
    history_panel = siblings.locator('[data-modeling-process-panel="ready"]')
    if history_panel.get_by_role("combobox", name="Evaluation method", exact=True).input_value() != "chord":
        raise RuntimeError("Chord Use settings did not copy Evaluation method=chord")
    if (
        history_panel.get_by_role("spinbutton", name="Elastic range start", exact=True).input_value() != "0.001"
        or history_panel.get_by_role("spinbutton", name="Elastic range end", exact=True).input_value() != "0.003"
    ):
        raise RuntimeError("Chord Use settings did not copy the 0.001–0.003 elastic range")
    if not history_panel.get_by_role("button", name="Save processed curves", exact=True).is_disabled():
        raise RuntimeError("Chord Use settings enabled Save before a new preview")
    history_panel.locator(".process-band-result").get_by_text("210.0 GPa", exact=True).wait_for(timeout=30_000)
    history_rows = _assert_modeling_process_saved_rows_three(
        siblings,
        current_label="Elastic window 0.0005-0.0025",
    )
    if sum("current" in row for row in history_rows) != 1 or not any(
        "Elastic window 0.0005-0.0025" in row and "current" in row
        for row in history_rows
    ):
        raise RuntimeError("Chord Use settings changed the sole visible current Process row")
    if siblings.locator('[data-modeling-process-panel="ready"]').count() != 1:
        raise RuntimeError("Saved sibling capture lost the ready Process panel")
    _wait_modeling_process_panel(siblings)
    _assert_modeling_process_saved_rows_reachable(siblings)
    _assert_modeling_process_stage_round_trip(
        siblings,
        base_url,
        expected_current_output=final_output,
        expected_current_label="Elastic window 0.0005-0.0025",
    )
    _capture(
        siblings,
        output / "modeling-process-siblings-1440x900.png",
        1440,
        900,
        before_screenshot=lambda: _assert_modeling_process_saved_rows_three(
            siblings,
            current_label="Elastic window 0.0005-0.0025",
        ),
    )
    siblings.context.close()
    return measurements


def _assert_modeling_normal_shell(page: Page) -> None:
    shell = page.get_by_role("navigation", name="Modeling workflow stages")
    buttons = shell.get_by_role("button")
    if buttons.count() != 4 or buttons.all_inner_texts() != ["Data", "Process", "Fit", "Export"]:
        raise RuntimeError(
            "normal Modeling shell must visibly contain only Data, Process, Fit and Export"
        )
    if shell.get_by_text(re.compile(r"Validate|Review")).count():
        raise RuntimeError("Validate/Review must not appear in the normal Modeling stage strip")


def _capture_modeling_consistency(
    browser: Browser, base_url: str, output: Path
) -> list[dict[str, object]]:
    measurements: list[dict[str, object]] = []
    _capture_modeling_session_shell(browser, base_url, output)
    for width, height in VIEWPORTS:
        page = _new_page(browser, base_url, width, height)
        _prepare_modeling(page, base_url)
        _assert_modeling_normal_shell(page)
        rail = page.locator(".modeling-workspace-rail")
        rail.get_by_text("Curves", exact=True).wait_for(timeout=30_000)
        if (
            page.get_by_text("Hide", exact=True).count()
            or page.get_by_role("button", name="Mean & band", exact=True).count()
        ):
            raise RuntimeError(
                "Data must use icon-only visibility and omit Mean & band before an ensemble preview"
            )
        if (
            rail.get_by_role("checkbox").count() < 1
            or rail.locator(".curve-visibility-toggle").count() < 1
        ):
            raise RuntimeError("Data must retain compact curve inclusion and visibility controls")
        if (
            rail.locator(".curve-tree-group").count() < 1
            or rail.locator(".curve-group-row").count() < 1
        ):
            raise RuntimeError("Data must group specimen rows under a real test-method tree parent")
        rail_box = rail.bounding_box()
        if rail_box is None or not 180 <= rail_box["width"] <= 210:
            raise RuntimeError(f"Data compact curve rail width drifted: {rail_box}")
        _capture(page, output / f"modeling-data-{width}x{height}.png", width, height)
        measurements.append(
            {
                "stage": "data",
                "viewport": f"{width}x{height}",
                **_measure_process_fit(page, "data", width, height),
            }
        )
        for stage in ("process", "fit", "export"):
            _open_modeling_stage(page, stage)
            page.locator(".modeling-work-title strong").get_by_text(
                STAGE_HEADINGS[stage], exact=True
            ).wait_for(timeout=30_000)
            _assert_modeling_normal_shell(page)
            if stage in ("process", "fit"):
                stage_rail = page.locator(".modeling-workspace-rail")
                stage_rail_box = stage_rail.bounding_box()
                if stage_rail_box is None or not 180 <= stage_rail_box["width"] <= 210:
                    raise RuntimeError(
                        f"{stage} compact curve rail width drifted: {stage_rail_box}"
                    )
                if page.get_by_role("button", name="Mean & band", exact=True).count():
                    raise RuntimeError(
                        f"{stage} must omit Mean & band before a real ensemble preview"
                    )
            elif page.locator(".modeling-workspace-rail").count():
                raise RuntimeError("Export must remain graph-only without a curve rail")
            if stage == "fit":
                page.get_by_role("button", name="Preview changes", exact=True).click()
            if stage == "export":
                _save_exact_fit_selection(page)
                _open_modeling_stage(page, "export")
                page.wait_for_url(re.compile(r"stage=export"), timeout=30_000)
                _prepare_exact_target_preview(page)
            _capture(page, output / f"modeling-{stage}-{width}x{height}.png", width, height)
            measurements.append(
                {
                    "stage": stage,
                    "viewport": f"{width}x{height}",
                    **_measure_process_fit(page, stage, width, height),
                }
            )
        page.context.close()
    return measurements


def _capture_modeling_data_viewports(
    browser: Browser,
    base_url: str,
    output: Path,
    viewports: tuple[tuple[int, int], ...],
) -> list[dict[str, object]]:
    measurements: list[dict[str, object]] = []
    for width, height in viewports:
        page = _new_page(browser, base_url, width, height)
        _prepare_modeling(page, base_url)
        _assert_modeling_normal_shell(page)
        rail = page.locator(".modeling-workspace-rail")
        rail.get_by_text("Curves", exact=True).wait_for(timeout=30_000)
        rail_box = rail.bounding_box()
        if rail_box is None or not 180 <= rail_box["width"] <= 210:
            raise RuntimeError(f"Data compact curve rail width drifted: {rail_box}")
        if (
            page.get_by_text("Hide", exact=True).count()
            or page.get_by_role("button", name="Mean & band", exact=True).count()
        ):
            raise RuntimeError(
                "Data must use icon-only visibility and omit Mean & band before an ensemble preview"
            )
        if (
            rail.locator(".curve-tree-group").count() < 1
            or rail.locator(".curve-group-row").count() < 1
        ):
            raise RuntimeError("Data must group specimen rows under a real test-method tree parent")
        _capture(page, output / f"modeling-data-{width}x{height}.png", width, height)
        data_measurement = _measure_process_fit(page, "data", width, height)
        if width > 1920:
            workspace_box = page.locator(".modeling-data-workspace-bounded").bounding_box()
            plot_box = page.locator(".persistent-modeling-plot").bounding_box()
            if workspace_box is None or plot_box is None or workspace_box["width"] > 1920.5 or plot_box["width"] > 1920.5:
                raise RuntimeError(
                    f"wide Modeling Data workspace exceeded the bounded working width at {width}x{height}: "
                    f"workspace={workspace_box}, plot={plot_box}"
                )
            data_measurement.update({"boundedWorkspaceWidth": workspace_box["width"], "boundedPlotWidth": plot_box["width"]})
        measurements.append(
            {
                "stage": "data",
                "viewport": f"{width}x{height}",
                **data_measurement,
            }
        )
        page.context.close()
    return measurements


def _capture_modeling_data_session(
    browser: Browser, base_url: str, output: Path
) -> list[dict[str, object]]:
    """Capture exact Library selection, reload persistence, and Data exceptions."""
    _capture_modeling_session_shell(browser, base_url, output)
    measurements = _capture_modeling_data_viewports(
        browser, base_url, output, (*VIEWPORTS, *WIDE_VIEWPORTS)
    )
    _capture_modeling_data_exceptions(browser, base_url, output)
    return measurements


def _capture_modeling_session_shell(browser: Browser, base_url: str, output: Path) -> None:
    """Capture the pin-free Data-first state separately from the populated Data workflow."""
    for width, height in VIEWPORTS:
        page = _new_page(browser, base_url, width, height)
        try:
            page.goto(f"{base_url}/modeling?stage=data&family=metal")
            page.locator(".modeling-stage-shell button").filter(has_text="Data").wait_for(
                timeout=30_000
            )
            page.wait_for_function(
                """() => document.querySelector(
                  ".modeling-stage-shell button.active strong"
                )?.textContent?.trim() === "Data" """,
                timeout=30_000,
            )
            page.evaluate(
                """() => window.dispatchEvent(new CustomEvent(
                  "cmp:workspace-command", { detail: { command: "modeling:new" } }
                ))"""
            )
            page.wait_for_url(re.compile(r"stage=data"), timeout=30_000)
            page.wait_for_function(
                """() => {
                  const raw = sessionStorage.getItem("cmp.modeling.recent-session.v4");
                  if (!raw) return false;
                  const session = JSON.parse(raw);
                  return session.contextSelectionRequired === true
                    && !session.material
                    && !session.materialState;
                }""",
                timeout=30_000,
            )
            shell = page.get_by_role("navigation", name="Modeling workflow stages")
            shell.wait_for(timeout=30_000)
            shell_buttons = shell.get_by_role("button")
            shell_buttons.nth(3).wait_for(timeout=30_000)
            if shell_buttons.count() != 4 or shell_buttons.all_inner_texts() != [
                "Data",
                "Process",
                "Fit",
                "Export",
            ]:
                raise RuntimeError("new-session shell must visibly contain exactly four normal stages")
            retired_terms = page.get_by_text(re.compile(r"exact Test Data|Advanced data contract"))
            if any(retired_terms.nth(index).is_visible() for index in range(retired_terms.count())):
                raise RuntimeError("new-session shell exposed retired implementation terminology")

            collapse_control = page.get_by_role(
                "button", name="Collapse curve and process navigator", exact=True
            )
            if (
                collapse_control.count() != 1
                or not collapse_control.is_visible()
                or not collapse_control.is_enabled()
            ):
                raise RuntimeError(
                    "new-session shell must expose one visible, enabled navigator collapse control"
                )
            collapse_control.click()
            page.wait_for_function(
                """() => {
                  const control = document.querySelector(
                    'button[aria-label="Expand curve and process navigator"]'
                  );
                  return control?.getAttribute("aria-expanded") === "false";
                }""",
                timeout=30_000,
            )
            expand_control = page.get_by_role(
                "button", name="Expand curve and process navigator", exact=True
            )
            if (
                expand_control.count() != 1
                or not expand_control.is_visible()
                or not expand_control.is_enabled()
                or expand_control.get_attribute("aria-expanded") != "false"
            ):
                raise RuntimeError(
                    "collapsed navigator must expose one visible, enabled expand control"
                )
            page.wait_for_function(
                """() => {
                  const rail = document.querySelector(".modeling-workspace-rail");
                  if (!rail) return true;
                  const box = rail.getBoundingClientRect();
                  const style = window.getComputedStyle(rail);
                  return box.width <= 1
                    || style.display === "none"
                    || style.visibility === "hidden";
                }""",
                timeout=30_000,
            )
            navigator_rail = page.locator(".modeling-workspace-rail")
            if navigator_rail.count():
                rail_box = navigator_rail.bounding_box()
                if navigator_rail.is_visible() and (
                    rail_box is None or rail_box["width"] > 1
                ):
                    raise RuntimeError(
                        f"collapsed navigator rail did not reclaim its width: {rail_box}"
                    )
            empty_plot = page.locator(".engineering-curve-plot-empty-frame")
            empty_plot.wait_for(state="visible", timeout=30_000)
            empty_svg = empty_plot.locator(
                'svg[role="img"][aria-label="Empty engineering curve plot"]'
            )
            if empty_svg.count() != 1 or not empty_svg.is_visible():
                raise RuntimeError(
                    "collapsed new-session shell must retain one visible empty engineering plot"
                )
            _capture(page, output / f"modeling-session-{width}x{height}.png", width, height)
        finally:
            page.context.close()


def _capture_modeling_data_exceptions(browser: Browser, base_url: str, output: Path) -> None:
    """Capture an empty new session and an invalid runtime CSV mapping state."""
    page = _new_page(browser, base_url, 1440, 900)
    try:
        page.goto(f"{base_url}/modeling?stage=data&family=metal")
        _wait_for_modeling_data_surface(page)
        page.evaluate(
            """() => window.dispatchEvent(new CustomEvent(
              "cmp:workspace-command", { detail: { command: "modeling:new" } }
            ))"""
        )
        _wait_for_modeling_data_surface(page)
        page.wait_for_function(
            """() => {
              const raw = sessionStorage.getItem("cmp.modeling.recent-session.v4");
              if (!raw) return false;
              const session = JSON.parse(raw);
              const workspace = session.workspace || {};
              return session.contextSelectionRequired === true
                && !session.material
                && !session.materialState
                && !session.testData
                && !session.mappingProfile
                && Array.isArray(workspace.selectedTestDataRefs)
                && workspace.selectedTestDataRefs.length === 0
                && Array.isArray(workspace.selectedDocumentIds)
                && workspace.selectedDocumentIds.length === 0
                && Array.isArray(workspace.visibleTestDataKeys)
                && workspace.visibleTestDataKeys.length === 0;
            }""",
            timeout=30_000,
        )
        empty_session = _modeling_session(page)
        if empty_session.get("material") or empty_session.get("materialState") or empty_session.get("testData"):
            raise RuntimeError(f"new Modeling Data session retained a pin: {empty_session}")
        empty_plot = page.locator(".engineering-curve-plot-empty-frame")
        empty_plot.wait_for(state="visible", timeout=30_000)
        empty_svg = empty_plot.locator("svg[role=img]")
        if empty_svg.count() != 1 or empty_svg.get_attribute("aria-label") != "Empty engineering curve plot":
            raise RuntimeError("empty Modeling Data state must retain one real engineering plot SVG")
        if empty_svg.locator(".chart-grid").count() < 2 or empty_svg.locator(".chart-axis").count() != 2:
            raise RuntimeError("empty Modeling Data plot is missing visible axes/grid")
        if not empty_svg.get_by_text("Engineering strain [1]").count() or not empty_svg.get_by_text("Engineering stress [MPa]").count():
            raise RuntimeError("empty Modeling Data plot is missing engineering axis labels")
        local_action = empty_plot.get_by_role("button", name="Local file", exact=True)
        if local_action.count() != 1 or not local_action.is_visible() or not local_action.is_enabled():
            raise RuntimeError("empty Modeling Data state must expose an operable Local file action")
        _assert_local_initial_controls(page)
        _capture(page, output / "modeling-data-empty-1440x900.png", 1440, 900)
    finally:
        page.context.close()

    page = _new_page(browser, base_url, 1440, 900)
    temporary_directory: tempfile.TemporaryDirectory[str] | None = None
    try:
        # Start from the valid three-curve state so the blocked Local mapping
        # capture proves that the last usable graph remains on screen.
        _prepare_modeling(page, base_url)
        _wait_for_data_plot(page)
        page.get_by_role("tab", name="Local file", exact=True).click()
        test_run = page.get_by_role("combobox", name="Local file Test Run", exact=True)
        test_run.wait_for(timeout=30_000)
        if test_run.locator("option").count() <= 1:
            raise RuntimeError("no governed Test Run is available for invalid mapping capture")
        test_run.select_option(index=1)
        selected_run = test_run.input_value()
        if not selected_run:
            raise RuntimeError("invalid mapping capture did not select a Test Run")
        long_strain = "Engineering strain measurement channel from extensometer (longitudinal)"
        long_stress = "True stress observed channel [MPa]"
        specimen_column = "Specimen identifier"
        temporary_directory = tempfile.TemporaryDirectory(prefix="cmp-invalid-")
        temporary_csv = Path(temporary_directory.name) / "modeling-data-invalid.csv"
        temporary_csv.write_text(
            f"{long_strain},{long_stress},{specimen_column}\n"
            "0.0000,0.0,Specimen 03\n"
            "0.0100,410.0,Specimen 03\n"
            "0.0200,520.0,Specimen 03\n"
            "0.0300,610.0,Specimen 03\n",
            encoding="utf-8",
        )
        page.get_by_label("Local test data file", exact=True).set_input_files(str(temporary_csv))
        inspect = page.get_by_role("button", name="Inspect source", exact=True)
        inspect.wait_for(state="visible", timeout=30_000)
        if not inspect.is_enabled():
            raise RuntimeError("Inspect source is disabled after selecting a Test Run and CSV")
        inspect.click()
        page.locator(".data-raw-table").wait_for(state="visible", timeout=30_000)
        independent = page.get_by_role("combobox", name="Independent source column", exact=True)
        dependent = page.get_by_role("combobox", name="Dependent source column", exact=True)
        independent.wait_for(state="visible", timeout=30_000)
        dependent.wait_for(state="visible", timeout=30_000)
        independent.select_option(label=long_strain)
        dependent.select_option(label=long_strain)
        dependent_unit = page.get_by_role("combobox", name="Dependent original unit", exact=True)
        dependent_unit.select_option(label="%")
        reason = page.get_by_role("textbox", name="Mapping change reason", exact=True)
        reason.fill("Review the measured source columns before saving this Test Data mapping.")
        blockers = page.locator(".data-mapping-blockers[role=alert]")
        blockers.wait_for(state="visible", timeout=30_000)
        if not blockers.get_by_text("Fix the test data mapping.", exact=True).count():
            raise RuntimeError("invalid mapping capture did not expose the exact blocker heading")
        if not blockers.get_by_text(
            "Use different source columns for Independent and Dependent.", exact=True
        ).count():
            raise RuntimeError("invalid mapping capture did not expose duplicate-source blocker")
        if not blockers.get_by_text(
            "Engineering stress cannot use “%”. Choose Pa, kPa, MPa, or GPa.", exact=True
        ).count():
            raise RuntimeError("invalid mapping capture did not expose unsupported-unit blocker")
        divider = page.locator("#modeling-data-ribbon-plot-divider")
        if divider.count() != 1 or not divider.is_visible() or divider.get_attribute("role") != "separator":
            raise RuntimeError("invalid mapping must expose one visible Data ribbon/plot separator")
        if divider.get_attribute("aria-orientation") != "horizontal":
            raise RuntimeError("Data ribbon/plot separator must expose horizontal orientation")
        action_boxes: list[tuple[str, dict[str, float]]] = []
        for action in ("Update preview", "Save Test Data"):
            button = page.get_by_role("button", name=action, exact=True)
            visible_candidates = []
            for index in range(button.count()):
                candidate = button.nth(index)
                if not candidate.is_visible():
                    continue
                action_box = _bounding_box_edges(candidate.bounding_box())
                if action_box is None or action_box["right"] <= 0 or action_box["left"] >= 1440 or action_box["bottom"] <= 0 or action_box["top"] >= 900:
                    raise RuntimeError(f"invalid mapping {action} is outside the captured viewport: {action_box}")
                if not candidate.is_disabled():
                    raise RuntimeError(f"invalid mapping left {action} enabled")
                if action == "Save Test Data":
                    class_tokens = (candidate.get_attribute("class") or "").split()
                    if "is-prerequisite-blocked" not in class_tokens:
                        raise RuntimeError("invalid mapping Save Test Data is missing is-prerequisite-blocked")
                    if "primary" in class_tokens:
                        raise RuntimeError("invalid mapping Save Test Data must not carry primary while prerequisites are unresolved")
                    style = candidate.evaluate(
                        """element => {
                          const computed = getComputedStyle(element);
                          return {
                            cursor: computed.cursor,
                            opacity: computed.opacity,
                            boxShadow: computed.boxShadow,
                            borderRadius: computed.borderRadius,
                          };
                        }"""
                    )
                    if style["cursor"] != "not-allowed" or style["opacity"] != "1" or style["boxShadow"] != "none" or style["borderRadius"] != "0px":
                        raise RuntimeError(f"invalid mapping Save Test Data blocked styling drifted: {style}")
                if action_box is not None:
                    visible_candidates.append(action_box)
            if len(visible_candidates) != 1:
                raise RuntimeError(f"invalid mapping must expose one visible {action} action: {visible_candidates}")
            action_boxes.append((action, visible_candidates[0]))
        ribbon_box = _bounding_box_edges(page.locator(".modeling-task-ribbon").bounding_box())
        workspace_box = _bounding_box_edges(page.locator(".modeling-main-surface").bounding_box())
        mapping_grid_box = _bounding_box_edges(page.locator(".data-source-decision-grid").bounding_box())
        mapping_table_box = _bounding_box_edges(
            page.get_by_role("region", name="Axis and unit mapping decision table", exact=True).bounding_box()
        )
        blockers_box = _bounding_box_edges(blockers.bounding_box())
        recovery_detail_box = _bounding_box_edges(page.locator(".data-mapping-recovery-detail").bounding_box())
        reason_box = _bounding_box_edges(reason.bounding_box())
        advanced_source = page.locator("details.data-source-advanced")
        advanced_source_box = _bounding_box_edges(advanced_source.bounding_box())
        advanced_summary = advanced_source.locator(":scope > summary")
        advanced_summary_box = _bounding_box_edges(advanced_summary.bounding_box())
        divider_box = _bounding_box_edges(divider.bounding_box())
        if advanced_source.count() != 1 or advanced_source.get_attribute("open") is not None:
            raise RuntimeError("invalid mapping technical source evidence must remain collapsed under Advanced")
        if any(item is None for item in (ribbon_box, workspace_box, mapping_grid_box, mapping_table_box, blockers_box, recovery_detail_box, reason_box, advanced_source_box, advanced_summary_box, divider_box)):
            raise RuntimeError("invalid mapping recovery controls are not visible in the Data workspace")
        assert ribbon_box is not None and workspace_box is not None and mapping_grid_box is not None
        assert mapping_table_box is not None and blockers_box is not None and recovery_detail_box is not None
        assert reason_box is not None and advanced_source_box is not None and advanced_summary_box is not None and divider_box is not None
        if advanced_source_box["height"] > 22:
            raise RuntimeError(f"invalid mapping collapsed Advanced source evidence exceeds 22px: {advanced_source_box}")
        ribbon_locator = page.locator(".modeling-task-ribbon")
        intake_locator = ribbon_locator.locator(":scope > .modeling-data-intake")
        ribbon_metrics = ribbon_locator.evaluate(
            "element => ({clientHeight: element.clientHeight, scrollHeight: element.scrollHeight})"
        )
        if ribbon_metrics["scrollHeight"] > ribbon_metrics["clientHeight"] + 1:
            raise RuntimeError(f"invalid mapping Data ribbon content overflows its container: {ribbon_metrics}")
        intake_box = _bounding_box_edges(intake_locator.bounding_box())
        if intake_box is None:
            raise RuntimeError("invalid mapping Data intake is not a direct child with measurable bounds")
        if ribbon_box["bottom"] - intake_box["bottom"] < 8:
            raise RuntimeError(
                "invalid mapping Data ribbon lacks 8px visual headroom below intake: "
                f"ribbon={ribbon_box}, intake={intake_box}"
            )
        if (
            intake_box["left"] < ribbon_box["left"] - 1
            or intake_box["right"] > ribbon_box["right"] + 1
            or intake_box["top"] < ribbon_box["top"] - 1
            or intake_box["bottom"] > ribbon_box["bottom"] + 1
        ):
            raise RuntimeError(f"invalid mapping Data intake escaped the task ribbon: ribbon={ribbon_box}, intake={intake_box}")
        if divider_box["height"] < 8:
            raise RuntimeError(f"invalid mapping Data ribbon/plot separator is below 8px: {divider_box}")
        if before_plot := _bounding_box_edges(page.locator(".modeling-data-plot-panel").bounding_box()):
            if before_plot["height"] < 296:
                raise RuntimeError(f"invalid mapping default plot panel is below 296px: {before_plot}")
        if blockers_box["width"] < 480 or recovery_detail_box["width"] < 360 or blockers_box["height"] > 70:
            raise RuntimeError(
                "invalid mapping recovery row does not preserve the bounded blocker/detail grammar: "
                f"blockers={blockers_box}, detail={recovery_detail_box}"
            )
        q20_sizes = page.locator(
            ".data-mapping-table td, .data-mapping-table select, "
            ".data-mapping-recovery-detail input, .data-mapping-actions button, "
            ".data-mapping-blockers"
        ).evaluate_all(
            "elements => elements.filter(element => element.getClientRects().length > 0).map(element => ({"
            "selector: element.tagName.toLowerCase(), fontSize: parseFloat(getComputedStyle(element).fontSize)"
            "}))"
        )
        if any(item["fontSize"] < 13 for item in q20_sizes):
            raise RuntimeError(f"invalid mapping data/control typography is below 13px: {q20_sizes}")
        control_metrics = page.locator(
            ".data-mapping-table select, "
            "select[name='local-test-run'], select[name='local-data-schema'], "
            ".data-mapping-recovery-detail input, .data-mapping-actions button"
        ).evaluate_all(
            "elements => elements.filter(element => element.getClientRects().length > 0).map(element => {"
            "const style = getComputedStyle(element);"
            "const box = element.getBoundingClientRect();"
            "return {tag: element.tagName.toLowerCase(), name: element.getAttribute('name'), "
            "height: box.height, minHeight: parseFloat(style.minHeight), "
            "paddingBlockStart: parseFloat(style.paddingBlockStart), paddingBlockEnd: parseFloat(style.paddingBlockEnd), "
            "paddingInlineStart: parseFloat(style.paddingInlineStart), paddingInlineEnd: parseFloat(style.paddingInlineEnd), "
            "fontSize: parseFloat(style.fontSize), lineHeight: style.lineHeight, boxSizing: style.boxSizing, appearance: style.appearance};"
            "})"
        )
        mapping_select_names = {
            "independent-source-column", "dependent-source-column",
            "independent-original-unit", "dependent-original-unit",
        }
        for item in control_metrics:
            is_mapping_select = item["tag"] == "select" and item["name"] in mapping_select_names
            is_action_button = item["tag"] == "button" and item["name"] is None
            expected_height = 26 if is_mapping_select else 28
            expected_inline = 4 if is_mapping_select else 10 if is_action_button else 6
            if abs(item["height"] - expected_height) > 0.75 or item["minHeight"] < expected_height - 0.75:
                raise RuntimeError(f"invalid mapping control height drifted: {item}")
            if item["paddingBlockStart"] != 0 or item["paddingBlockEnd"] != 0:
                raise RuntimeError(f"invalid mapping control vertical padding drifted: {item}")
            if item["paddingInlineStart"] != expected_inline or item["paddingInlineEnd"] != expected_inline:
                raise RuntimeError(f"invalid mapping control horizontal padding drifted: {item}")
            if item["fontSize"] != 13 or item["lineHeight"] != "normal" or item["boxSizing"] != "border-box":
                raise RuntimeError(f"invalid mapping control typography/box sizing drifted: {item}")
            if is_mapping_select and item["appearance"] != "auto":
                raise RuntimeError(f"invalid mapping native select appearance drifted: {item}")
        blocker_lines = blockers.locator(":scope > span").evaluate_all(
            "elements => elements.map(element => {const style = getComputedStyle(element); return "
            "{height: element.getBoundingClientRect().height, lineHeight: parseFloat(style.lineHeight), whiteSpace: style.whiteSpace};})"
        )
        if any(line["whiteSpace"] == "nowrap" or line["height"] > line["lineHeight"] + 1 for line in blocker_lines):
            raise RuntimeError(f"invalid mapping blocker issue wrapped unexpectedly: {blocker_lines}")
        metadata_sizes = page.locator(
            ".data-source-evidence header, .data-source-evidence p, "
            ".data-mapping-heading span, .data-mapping-consequence, "
            ".data-source-advanced > summary"
        ).evaluate_all(
            "elements => elements.filter(element => element.getClientRects().length > 0).map(element => ({"
            "selector: element.tagName.toLowerCase(), fontSize: parseFloat(getComputedStyle(element).fontSize)"
            "}))"
        )
        if any(item["fontSize"] < 11.5 for item in metadata_sizes):
            raise RuntimeError(f"invalid mapping metadata typography is below 11.5px: {metadata_sizes}")
        before_keyboard_ribbon = _bounding_box_edges(page.locator(".modeling-data-ribbon-panel").bounding_box())
        before_keyboard_plot = _bounding_box_edges(page.locator(".modeling-data-plot-panel").bounding_box())
        if before_keyboard_ribbon is None or before_keyboard_plot is None:
            raise RuntimeError("invalid mapping Data split panels are not measurable")
        divider.focus()
        divider.press("ArrowDown")
        page.wait_for_timeout(80)
        after_keyboard_ribbon = _bounding_box_edges(page.locator(".modeling-data-ribbon-panel").bounding_box())
        after_keyboard_plot = _bounding_box_edges(page.locator(".modeling-data-plot-panel").bounding_box())
        if after_keyboard_ribbon is None or after_keyboard_plot is None:
            raise RuntimeError("invalid mapping Data split panels disappeared after keyboard resize")
        ribbon_delta = after_keyboard_ribbon["height"] - before_keyboard_ribbon["height"]
        plot_delta = after_keyboard_plot["height"] - before_keyboard_plot["height"]
        if ribbon_delta <= 0 or plot_delta >= 0 or after_keyboard_plot["height"] < 240:
            raise RuntimeError(
                "invalid mapping keyboard resize must grow the ribbon, shrink the plot, "
                f"and keep the plot container >=240px: before=({before_keyboard_ribbon}, {before_keyboard_plot}) "
                f"after=({after_keyboard_ribbon}, {after_keyboard_plot})"
            )
        divider.dblclick()
        page.wait_for_timeout(80)
        reset_plot_panel = _bounding_box_edges(page.locator(".modeling-data-plot-panel").bounding_box())
        if reset_plot_panel is None or reset_plot_panel["height"] < 296:
            raise RuntimeError(f"invalid mapping separator reset did not restore a >=296px plot container: {reset_plot_panel}")
        visible_left = max(ribbon_box["left"], workspace_box["left"], 0)
        visible_right = min(ribbon_box["right"], workspace_box["right"], 1440)
        visible_bottom = min(ribbon_box["bottom"], workspace_box["bottom"], 900)
        required_boxes = [
            ("mapping grid", mapping_grid_box),
            ("mapping table", mapping_table_box),
            ("mapping blockers", blockers_box),
            ("mapping reason", reason_box),
            ("Advanced source evidence summary", advanced_summary_box),
            *action_boxes,
        ]
        for name, box in required_boxes:
            if (
                box["left"] < visible_left - 1
                or box["right"] > visible_right + 1
                or box["top"] < ribbon_box["top"] - 1
                or box["bottom"] > visible_bottom + 1
            ):
                raise RuntimeError(f"invalid mapping {name} is clipped: box={box}, ribbon={ribbon_box}, workspace={workspace_box}")
        if page.locator(".data-intake-local").evaluate("element => ['auto', 'scroll'].includes(getComputedStyle(element).overflowY)"):
            raise RuntimeError("invalid mapping must not add a nested scroll container inside the Data ribbon")
        provenance = page.locator("[aria-label='Test identity and provenance']")
        if provenance.count() and re.search(r"\bSpecimen\b|\bRaw (?:asset|artifact)\b|SHA-?256", provenance.inner_text(), re.IGNORECASE):
            raise RuntimeError("invalid mapping normal provenance surface exposes a technical source identifier")
        _wait_for_data_plot(page)
        if page.locator(".curve-line.data-observed").count() != 3:
            raise RuntimeError("invalid mapping capture lost the last valid three-curve graph")
        plot_geometry = page.locator(".persistent-modeling-plot").evaluate(
            """plot => {
                const rect = element => {
                    if (!element) return null;
                    const box = element.getBoundingClientRect();
                    return {
                        left: box.left,
                        right: box.right,
                        top: box.top,
                        bottom: box.bottom,
                        width: box.width,
                        height: box.height,
                    };
                };
                const overlaps = (first, second, tolerance = 1) => Boolean(
                    first && second
                    && first.left < second.right - tolerance
                    && first.right > second.left + tolerance
                    && first.top < second.bottom - tolerance
                    && first.bottom > second.top + tolerance
                );
                const plotBox = rect(plot);
                const svg = plot.querySelector('svg[role="img"]');
                const svgBox = rect(svg);
                const toolbarBox = rect(plot.querySelector('.modeling-plot-toolbar'));
                const legendBox = rect(plot.querySelector('.curve-legend'));
                const axisLabels = [...(svg?.querySelectorAll('.chart-axis-label') ?? [])]
                    .map(rect)
                    .filter(Boolean);
                const axes = [...(svg?.querySelectorAll('.chart-axis') ?? [])]
                    .map(rect)
                    .filter(Boolean);
                const inside = (child, parent, tolerance = 1) => Boolean(
                    child && parent
                    && child.left >= parent.left - tolerance
                    && child.right <= parent.right + tolerance
                    && child.top >= parent.top - tolerance
                    && child.bottom <= parent.bottom + tolerance
                );
                const viewport = {
                    left: 0,
                    right: window.innerWidth,
                    top: 0,
                    bottom: window.innerHeight,
                };
                return {
                    plot: plotBox,
                    svg: svgBox,
                    toolbar: toolbarBox,
                    legend: legendBox,
                    svgHeight: svgBox?.height ?? 0,
                    plotHeight: plotBox?.height ?? 0,
                    svgInsidePlot: inside(svgBox, plotBox),
                    plotInsideViewport: inside(plotBox, viewport),
                    svgInsideViewport: inside(svgBox, viewport),
                    labelsInsideSvg: axisLabels.every(label => inside(label, svgBox, 2)),
                    toolbarLegendOverlap: overlaps(toolbarBox, legendBox),
                    toolbarAxisOverlap: axes.some(axis => overlaps(toolbarBox, axis)),
                    toolbarAxisLabelOverlap: axisLabels.some(label => overlaps(toolbarBox, label)),
                    legendAxisOverlap: axes.some(axis => overlaps(legendBox, axis)),
                    legendAxisLabelOverlap: axisLabels.some(label => overlaps(legendBox, label)),
                };
            }"""
        )
        if plot_geometry["svgHeight"] < 230 or plot_geometry["plotHeight"] < 280:
            raise RuntimeError(f"invalid mapping plot must retain a usable >=280px frame and >=230px SVG: {plot_geometry}")
        if (
            not plot_geometry["svgInsidePlot"]
            or not plot_geometry["plotInsideViewport"]
            or not plot_geometry["svgInsideViewport"]
            or not plot_geometry["labelsInsideSvg"]
        ):
            raise RuntimeError(f"invalid mapping plot SVG or axis labels escaped the plot frame: {plot_geometry}")
        if any(
            plot_geometry[key]
            for key in (
                "toolbarLegendOverlap",
                "toolbarAxisOverlap",
                "toolbarAxisLabelOverlap",
                "legendAxisOverlap",
                "legendAxisLabelOverlap",
            )
        ):
            raise RuntimeError(f"invalid mapping plot controls, legend, and axes overlap: {plot_geometry}")
        _capture(page, output / "modeling-data-invalid-1440x900.png", 1440, 900)
    finally:
        try:
            if temporary_directory is not None:
                temporary_directory.cleanup()
        finally:
            page.context.close()


def _capture_administration_database(browser: Browser, base_url: str, output: Path) -> None:
    for width, height in (*VIEWPORTS, *WIDE_VIEWPORTS):
        page = _new_page(browser, base_url, width, height)
        page.goto(f"{base_url}/administration/database")
        page.get_by_role("navigation", name="Administration areas").wait_for(timeout=30_000)
        page.get_by_role("heading", name="Database design", exact=True).wait_for(timeout=30_000)
        page.get_by_role("navigation", name="Database objects").wait_for(timeout=30_000)
        page.get_by_role("combobox", name="Current table", exact=True).wait_for(timeout=30_000)
        page.locator(".schema-property-editor .property-sheet").wait_for(timeout=30_000)
        if page.get_by_role("alert").count():
            raise RuntimeError(f"Administration shows an error at {width}x{height}")
        if page.evaluate(
            "document.documentElement.scrollWidth > document.documentElement.clientWidth"
        ):
            raise RuntimeError(f"Administration has horizontal overflow at {width}x{height}")
        _capture(page, output / f"administration-database-{width}x{height}.png", width, height)
        page.context.close()


def _capture_administration_records(browser: Browser, base_url: str, output: Path) -> None:
    for width, height in (*VIEWPORTS, *WIDE_VIEWPORTS):
        page = _new_page(browser, base_url, width, height)
        page.goto(f"{base_url}/administration/records")
        page.get_by_role("navigation", name="Administration areas").wait_for(timeout=30_000)
        page.get_by_role("heading", name="Single entry or multiple rows", exact=True).wait_for(
            timeout=30_000
        )
        page.get_by_role("heading", name="Create Record", exact=True).wait_for(timeout=30_000)
        multiple_rows = page.get_by_role("button", name="Multiple rows", exact=True)
        multiple_rows.wait_for(timeout=30_000)
        multiple_rows.click()
        page.get_by_label("Source file", exact=True).wait_for(timeout=30_000)
        page.get_by_role("button", name="Read columns", exact=True).wait_for(timeout=30_000)
        if page.get_by_role("alert").count():
            raise RuntimeError(f"Administration registration shows an error at {width}x{height}")
        if page.evaluate(
            "document.documentElement.scrollWidth > document.documentElement.clientWidth"
        ):
            raise RuntimeError(
                f"Administration registration has horizontal overflow at {width}x{height}"
            )
        _capture(page, output / f"administration-records-{width}x{height}.png", width, height)
        page.context.close()


def _capture_supporting_screens(browser: Browser, base_url: str, output: Path) -> None:
    _capture_administration_database(browser, base_url, output)
    _capture_administration_records(browser, base_url, output)
    for width, height in ((1366, 768), (1440, 900)):
        page = _new_page(browser, base_url, width, height)
        page.goto(f"{base_url}/administration/access")
        page.get_by_role("heading", name="Choose what each team can do", exact=True).wait_for(
            timeout=30_000
        )
        page.get_by_role("combobox", name="Role", exact=True).select_option("reviewer")
        included_tasks = page.get_by_text("Included tasks:", exact=False)
        included_tasks.wait_for(timeout=30_000)
        included_tasks.scroll_into_view_if_needed()
        if page.get_by_role("group", name="Feature grants").count():
            raise RuntimeError("product access must use task presets, not feature checkboxes")
        _capture(
            page,
            output / f"administration-access-{width}x{height}.png",
            width,
            height,
            focus_selector="#role-task-summary",
        )
        page.context.close()


def _validate_capture_outputs(output: Path) -> int:
    actual_outputs = {
        path.relative_to(output).as_posix() for path in output.rglob("*") if path.is_file()
    }
    expected_outputs = set(CURRENT_CAPTURE_OUTPUTS)
    if actual_outputs != expected_outputs:
        raise RuntimeError(
            "current capture output drift: "
            f"missing={sorted(expected_outputs - actual_outputs)}, "
            f"unexpected={sorted(actual_outputs - expected_outputs)}"
        )
    for name in CURRENT_CAPTURE_OUTPUTS:
        image = output / name
        value = image.read_bytes()
        if len(value) < 10_000 or value[:8] != PNG_SIGNATURE or value[12:16] != b"IHDR":
            raise RuntimeError(f"current capture is not a plausible PNG: {name}")
        width, height = struct.unpack(">II", value[16:24])
        expected = re.search(r"-(\d+)x(\d+)\.png$", name)
        if expected is None or (width, height) != (
            int(expected.group(1)),
            int(expected.group(2)),
        ):
            raise RuntimeError(f"current capture viewport drift for {name}: {width}x{height}")
    return len(actual_outputs)


def _replace_capture_directory(staged: Path, target: Path) -> None:
    backup: Path | None = None
    if target.exists():
        backup = Path(tempfile.mkdtemp(prefix=f".{target.name}-previous-", dir=target.parent))
        backup.rmdir()
        os.replace(target, backup)
    try:
        os.replace(staged, target)
    except OSError:
        if backup is not None and backup.exists() and not target.exists():
            os.replace(backup, target)
        raise
    if backup is not None:
        shutil.rmtree(backup)


def _capture_to_empty_directory(target: Path, producer: Callable[[Path], None]) -> int:
    target = target.resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=f".{target.name}-capture-", dir=target.parent
    ) as temporary:
        staged = Path(temporary)
        producer(staged)
        capture_count = _validate_capture_outputs(staged)
        _replace_capture_directory(staged, target)
    return capture_count


def main() -> int:
    from playwright.sync_api import sync_playwright

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:5173")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/user-guide/images/current"),
    )
    parser.add_argument(
        "--only-materials",
        action="store_true",
        help="Capture and replace only the seventeen Materials workspace captures.",
    )
    parser.add_argument(
        "--only-product-access",
        action="store_true",
        help="Capture and replace only the two Product Access role-preset viewports.",
    )
    parser.add_argument(
        "--only-administration-database",
        action="store_true",
        help="Capture and replace only the five Administration database-design viewports.",
    )
    parser.add_argument(
        "--only-administration-records",
        action="store_true",
        help="Capture and replace only the five Administration registration viewports.",
    )
    parser.add_argument(
        "--only-activity",
        action="store_true",
        help="Capture and replace only the three role-aware Activity queue viewports.",
    )
    parser.add_argument(
        "--only-review-submission",
        action="store_true",
        help="Capture Native Solver Card review submission and Activity status at all viewports.",
    )
    parser.add_argument(
        "--only-modeling-export",
        action="store_true",
        help="Capture and replace only the three Modeling Export viewports.",
    )
    parser.add_argument(
        "--only-modeling-process-fit",
        action="store_true",
        help=(
            "Capture and replace the five Process/Fit viewports plus candidate-evidence, "
            "calculation/save failure, exact-source/read failure, and restored Fit states."
        ),
    )
    parser.add_argument(
        "--only-modeling-process",
        action="store_true",
        help="Capture and replace only the nine Modeling Process viewports and settled states.",
    )
    parser.add_argument(
        "--resume-modeling-process",
        action="store_true",
        help=(
            "Resume only the interrupted three-output Modeling Process capture; "
            "requires --only-modeling-process."
        ),
    )
    parser.add_argument(
        "--only-modeling-consistency",
        action="store_true",
        help=(
            "Capture all 15 current Modeling Data/Process/Fit/Export/session screens "
            "with consistency gates."
        ),
    )
    parser.add_argument(
        "--only-modeling-data-session",
        action="store_true",
        help=(
            "Capture the ten current Modeling Data/session screens with the same consistency gates."
        ),
    )
    args = parser.parse_args()
    if args.resume_modeling_process and not args.only_modeling_process:
        parser.error("--resume-modeling-process requires --only-modeling-process")
    if args.resume_modeling_process and any(
        (
            args.only_materials,
            args.only_product_access,
            args.only_administration_database,
            args.only_administration_records,
            args.only_activity,
            args.only_review_submission,
            args.only_modeling_export,
            args.only_modeling_process_fit,
            args.only_modeling_consistency,
            args.only_modeling_data_session,
        )
    ):
        parser.error("--resume-modeling-process cannot be combined with another capture selector")

    def produce(output: Path) -> None:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                _capture_materials(browser, args.base_url, output)
                _capture_solver_delivery(browser, args.base_url, output)
                _capture_modeling_session_shell(browser, args.base_url, output)
                _capture_modeling(
                    browser,
                    args.base_url,
                    output,
                    include_process_normals=False,
                )
                _capture_modeling_process_only(browser, args.base_url, output)
                _capture_modeling_fit_states(browser, args.base_url, output)
                _capture_modeling_data_viewports(
                    browser, args.base_url, output, WIDE_VIEWPORTS
                )
                _capture_modeling_data_exceptions(browser, args.base_url, output)
                _capture_supporting_screens(browser, args.base_url, output)
            finally:
                browser.close()

    if (
        args.only_materials
        or args.only_modeling_export
        or args.only_modeling_process_fit
        or args.only_modeling_process
        or args.only_modeling_consistency
        or args.only_modeling_data_session
        or args.only_product_access
        or args.only_administration_database
        or args.only_administration_records
        or args.only_activity
        or args.only_review_submission
    ):
        names = (
            CURRENT_CAPTURE_OUTPUTS[:17]
            if args.only_materials
            else MODELING_EXPORT_OUTPUTS
            if args.only_modeling_export
            else MODELING_PROCESS_FIT_OUTPUTS
            if args.only_modeling_process_fit
            else MODELING_PROCESS_OUTPUTS
            if args.only_modeling_process
            else MODELING_CONSISTENCY_OUTPUTS
            if args.only_modeling_consistency
            else MODELING_DATA_SESSION_OUTPUTS
            if args.only_modeling_data_session
            else ACTIVITY_OUTPUTS
            if args.only_activity
            else REVIEW_SUBMISSION_OUTPUTS
            if args.only_review_submission
            else PRODUCT_ACCESS_OUTPUTS
            if args.only_product_access
            else ADMINISTRATION_RECORDS_OUTPUTS
            if args.only_administration_records
            else ADMINISTRATION_DATABASE_OUTPUTS
        )
        args.output.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(
            prefix=".modeling-stage-capture-", dir=args.output.parent
        ) as temporary:
            staged = Path(temporary)
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                try:
                    measurements: list[dict[str, object]] = []
                    if args.only_materials:
                        _capture_materials(browser, args.base_url, staged)
                    elif args.only_modeling_export:
                        _capture_modeling_export_only(browser, args.base_url, staged)
                    elif args.only_modeling_process_fit:
                        measurements = _capture_modeling_process_fit(
                            browser, args.base_url, staged
                        )
                    elif args.only_modeling_process:
                        measurements = _capture_modeling_process_only(
                            browser,
                            args.base_url,
                            staged,
                            resume_modeling_process=args.resume_modeling_process,
                        )
                    elif args.only_modeling_consistency:
                        measurements = _capture_modeling_consistency(
                            browser, args.base_url, staged
                        )
                    elif args.only_modeling_data_session:
                        measurements = _capture_modeling_data_session(
                            browser, args.base_url, staged
                        )
                    elif args.only_activity:
                        _capture_activity(browser, args.base_url, staged)
                    elif args.only_review_submission:
                        _capture_solver_delivery(browser, args.base_url, staged)
                    elif args.only_product_access:
                        _capture_supporting_screens(browser, args.base_url, staged)
                    elif args.only_administration_records:
                        _capture_administration_records(browser, args.base_url, staged)
                    else:
                        _capture_administration_database(browser, args.base_url, staged)
                finally:
                    browser.close()
            actual_outputs = {path.name for path in staged.iterdir() if path.is_file()}
            if args.only_product_access:
                actual_outputs = {name for name in actual_outputs if name in names}
            if actual_outputs != set(names):
                raise RuntimeError(
                    f"targeted capture output drift: actual={sorted(actual_outputs)}"
                )
            for name in names:
                image = staged / name
                value = image.read_bytes()
                if len(value) < 10_000 or value[:8] != PNG_SIGNATURE:
                    raise RuntimeError(f"targeted Modeling capture is not a plausible PNG: {name}")
            for name in names:
                os.replace(staged / name, args.output / name)
        capture_count = len(names)
    else:
        capture_count = _capture_to_empty_directory(args.output, produce)
    result = {
        "output": args.output.as_posix(),
        "captures": capture_count,
        "viewports": [
            f"{width}x{height}"
            for width, height in (
                (*VIEWPORTS, *WIDE_VIEWPORTS)
                if (
                    args.only_administration_database
                    or args.only_administration_records
                    or args.only_modeling_data_session
                    or args.only_modeling_process_fit
                )
                else VIEWPORTS
            )
        ],
    }
    if (
        args.only_modeling_process_fit
        or args.only_modeling_consistency
        or args.only_modeling_data_session
    ):
        result["measurements"] = measurements
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

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
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import parse_qs, urlsplit

if TYPE_CHECKING:
    from playwright.sync_api import Browser, Page, Route

VIEWPORTS = ((1366, 768), (1440, 900), (1920, 1080))
WIDE_VIEWPORTS = ((2560, 1440), (3840, 2160))
REVISION_LABEL_PATTERN = re.compile(r"\br[1-9]\d*\b")
MODELING_EXPORT_OUTPUTS = tuple(
    f"modeling-export-{width}x{height}.png" for width, height in VIEWPORTS
)
MODELING_PROCESS_FIT_OUTPUTS = tuple(
    f"modeling-{stage}-{width}x{height}.png"
    for stage in ("process", "fit")
    for width, height in VIEWPORTS
)
MODELING_CONSISTENCY_OUTPUTS = tuple(
    f"modeling-{stage}-{width}x{height}.png"
    for stage in ("data", "process", "fit", "export", "session")
    for width, height in VIEWPORTS
)
MODELING_DATA_SESSION_OUTPUTS = tuple(
    f"modeling-{stage}-{width}x{height}.png"
    for stage in ("data", "session")
    for width, height in VIEWPORTS
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
    "modeling-session-1366x768.png",
    "modeling-session-1440x900.png",
    "modeling-session-1920x1080.png",
    "modeling-process-1366x768.png",
    "modeling-process-1440x900.png",
    "modeling-process-1920x1080.png",
    "modeling-fit-1366x768.png",
    "modeling-fit-1440x900.png",
    "modeling-fit-1920x1080.png",
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
    "data": "Verify source & channel mapping",
    "process": "Prepare observed curves",
    "fit": "Fit material response",
    "export": "Review & deliver solver card",
}
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
    page.locator(".modeling-stage-shell").get_by_text(stage.title(), exact=True).click()


def _prepare_modeling(page: Page, base_url: str) -> None:
    page.goto(f"{base_url}/modeling?stage=data&family=metal")
    page.get_by_role("heading", name=STAGE_HEADINGS["data"], exact=True).wait_for(timeout=30_000)
    revision = page.get_by_role("combobox", name="Data-stage Test Data revision")
    revision.wait_for(timeout=30_000)
    if not revision.input_value():
        revision.select_option(index=1)
    page.get_by_text(re.compile(r"Loaded saved dataset revision")).wait_for(timeout=30_000)
    advanced_contract = page.locator("details.modeling-data-advanced")
    if not advanced_contract.get_attribute("open"):
        advanced_contract.locator(":scope > summary").click()
    profile = page.get_by_role("combobox", name="Saved Mapping Profile")
    profile.wait_for(timeout=30_000)
    if not profile.input_value():
        profile.select_option(index=1)
    advanced_contract.locator(":scope > summary").click()
    plot = page.locator(".persistent-modeling-plot svg[role=img]")
    # Data has no competing stage-header primary action. Compute the same exact source/mapping
    # preview through Process's secondary action, then return to Data for its evidence capture.
    _open_modeling_stage(page, "process")
    page.wait_for_url(re.compile(r"stage=process"), timeout=30_000)
    page.get_by_role("button", name="Preview changes", exact=True).click()
    plot.wait_for(timeout=30_000)
    _open_modeling_stage(page, "data")
    page.wait_for_url(re.compile(r"stage=data"), timeout=30_000)
    page.get_by_role("heading", name=STAGE_HEADINGS["data"], exact=True).wait_for(timeout=30_000)
    _wait_for_settled(page)


def _save_exact_fit_selection(page: Page) -> None:
    _open_modeling_stage(page, "fit")
    page.wait_for_url(re.compile(r"stage=fit"), timeout=30_000)
    page.locator(".modeling-work-title strong").get_by_text(
        STAGE_HEADINGS["fit"], exact=True
    ).wait_for(timeout=30_000)
    show_settings = page.get_by_role("button", name="Show current-stage settings", exact=True)
    if show_settings.count():
        show_settings.click()
    disclosure = page.locator("details.fit-evidence-disclosure")
    disclosure.locator(":scope > summary").click()
    candidate_table = page.get_by_role("table", name="Hardening candidate comparison")
    candidate_table.wait_for(timeout=30_000)
    candidate_table.get_by_role("button", name=re.compile(r"^Select .+ candidate$")).last.click()
    page.get_by_role("textbox", name="Candidate selection reason").fill(
        "Best agreement over the measured strain range."
    )
    warning_acknowledgement = page.get_by_role(
        "checkbox", name="Acknowledge selected candidate warning"
    )
    if warning_acknowledgement.count():
        warning_acknowledgement.check()
    save_candidate = page.get_by_role("button", name="Save fit & continue", exact=True)
    page.wait_for_function(
        """() => [...document.querySelectorAll("button")].some(
            button => button.textContent?.trim() === "Save fit & continue"
              && !button.disabled
        )""",
        timeout=30_000,
    )
    disclosure.locator(":scope > summary").click()
    save_candidate.click()
    page.wait_for_function(
        """() => [...document.querySelectorAll("h1, h2, h3")].some(
            heading => heading.textContent?.trim() ===
              "Review & deliver solver card"
        ) || document.querySelector(".error-banner")""",
        timeout=30_000,
    )
    error_banner = page.locator(".error-banner")
    if error_banner.count():
        raise RuntimeError(f"Fit selected-output save failed: {error_banner.inner_text().strip()}")


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
        _prepare_modeling(page, base_url)
        _save_exact_fit_selection(page)
        _prepare_exact_target_preview(page)
        _capture(
            page,
            output / f"modeling-export-{width}x{height}.png",
            width,
            height,
            focus_selector=".modeling-target-preview .ux-notice.success",
        )
        page.context.close()


def _capture_modeling(browser: Browser, base_url: str, output: Path) -> None:
    for width, height in VIEWPORTS:
        page = _new_page(browser, base_url, width, height)
        _prepare_modeling(page, base_url)
        plot = page.locator(".persistent-modeling-plot svg[role=img]")
        for stage, heading in STAGE_HEADINGS.items():
            _open_modeling_stage(page, stage)
            page.wait_for_url(re.compile(rf"stage={stage}"), timeout=30_000)
            page.locator(".modeling-work-title strong").get_by_text(heading, exact=True).wait_for(
                timeout=30_000
            )
            if stage == "fit":
                show_settings = page.get_by_role(
                    "button", name="Show current-stage settings", exact=True
                )
                if show_settings.count():
                    show_settings.click()
                _wait_for_settled(page)
                disclosure = page.locator("details.fit-evidence-disclosure")
                disclosure.locator(":scope > summary").click()
                candidate_table = page.get_by_role("table", name="Hardening candidate comparison")
                candidate_table.wait_for(timeout=30_000)
                if candidate_table.locator("tbody tr").count() != 5:
                    raise RuntimeError(
                        "Fit must expose four calculated single-law candidates "
                        "and the exact calculated preview blend"
                    )
                page.get_by_text(re.compile(r"^Preview blend · .+ · fitted domain$")).wait_for(
                    timeout=30_000
                )
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
                    if (
                        candidate_table.get_by_role("columnheader", name=column, exact=True).count()
                        != 1
                    ):
                        raise RuntimeError(f"Fit candidate table is missing {column}")
                save_candidate = page.get_by_role("button", name="Save fit & continue", exact=True)
                if save_candidate.count() != 1:
                    raise RuntimeError("Fit is missing its sole top-row save action")
                if not save_candidate.is_disabled():
                    raise RuntimeError(
                        "Fit save must remain disabled before an explicit row selection"
                    )
                select_candidate = candidate_table.get_by_role(
                    "button", name=re.compile(r"^Select .+ candidate$")
                ).first
                select_candidate.click()
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
                if save_candidate.is_disabled():
                    raise RuntimeError(
                        "Fit save did not become ready after selection evidence was completed"
                    )
                disclosure.locator(":scope > summary").click()
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
            _capture(
                page,
                output / f"modeling-{stage}-{width}x{height}.png",
                width,
                height,
                focus_selector=None,
            )
            if stage == "fit":
                page.get_by_role("button", name="Save fit & continue", exact=True).click()
                page.wait_for_url(re.compile(r"stage=export"), timeout=30_000)
        page.context.close()


def _measure_process_fit(page: Page, stage: str, width: int, height: int) -> dict[str, float]:
    measurement = page.evaluate(
        """() => {
          const box = selector => document.querySelector(selector)?.getBoundingClientRect();
          const svg = document.querySelector('.persistent-modeling-plot svg[role=img]');
          const axis = [...(svg?.querySelectorAll('.chart-axis') ?? [])]
            .find(
              line => line.getAttribute('x1') !== line.getAttribute('x2')
            )?.getBoundingClientRect();
          const workspace = box('.modeling-split-workspace');
          const rail = box('.modeling-workspace-rail');
          const ribbon = box('.modeling-task-ribbon');
          const plot = box('.persistent-modeling-plot');
          const legend = box('.curve-legend');
          const svgBox = svg?.getBoundingClientRect();
          const axisLabels = [...(svg?.querySelectorAll('.chart-axis-label') ?? [])];
          const xAxisLabel = axisLabels.at(-2)?.getBoundingClientRect();
          return {
            svgHeight: svgBox?.height ?? 0,
            svgWidth: svgBox?.width ?? 0,
            svgBottom: svgBox?.bottom ?? 0,
            drawableRatio: workspace && axis ? axis.width / workspace.width : 0,
            railWidth: rail?.width ?? 0, ribbonHeight: ribbon?.height ?? 0,
            plotBottom: plot?.bottom ?? 0, xAxisLabelBottom: xAxisLabel?.bottom ?? 0,
            legendBottom: legend?.bottom ?? 0,
            viewportHeight: window.innerHeight
          };
        }"""
    )
    if stage == "data":
        # Data keeps a slightly taller source-selection ribbon than Process/Fit.
        # Preserve a large graph without treating a single-digit pixel
        # difference at the 900px viewport as a structural failure.
        minimum = 300 if height == 768 else 420
    else:
        minimum = 330 if height == 768 else 430
    if measurement["svgHeight"] < minimum or measurement["drawableRatio"] < 0.72:
        raise RuntimeError(f"{stage} geometry gate failed at {width}x{height}: {measurement}")
    if width == 1440 and measurement["svgWidth"] < 1050:
        raise RuntimeError(f"{stage} 1440 graph-width gate failed: {measurement}")
    if (
        measurement["svgBottom"] > measurement["plotBottom"] + 2.5
        or measurement["xAxisLabelBottom"] > measurement["plotBottom"] + 1
    ):
        raise RuntimeError(f"{stage} axis is clipped at {width}x{height}: {measurement}")
    if measurement["legendBottom"] > measurement["viewportHeight"]:
        raise RuntimeError(f"{stage} legend is clipped at {width}x{height}: {measurement}")
    return measurement


def _capture_modeling_process_fit(
    browser: Browser, base_url: str, output: Path
) -> list[dict[str, float]]:
    measurements: list[dict[str, float]] = []
    for width, height in VIEWPORTS:
        page = _new_page(browser, base_url, width, height)
        _prepare_modeling(page, base_url)
        _open_modeling_stage(page, "process")
        page.locator(".modeling-work-title strong").get_by_text(
            STAGE_HEADINGS["process"], exact=True
        ).wait_for(timeout=30_000)
        if page.locator(".modeling-stage-number:visible").count():
            raise RuntimeError("Process/Fit capture received the retired numbered stage strip")
        if page.locator(".stage-process > .section-heading:visible").count():
            raise RuntimeError("Process capture received the retired duplicate workspace heading")
        page.locator(".modeling-workspace-rail .rail-heading").get_by_text(
            "Curves", exact=True
        ).wait_for(timeout=30_000)
        _capture(page, output / f"modeling-process-{width}x{height}.png", width, height)
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
        page.get_by_role("button", name="Preview changes", exact=True).click()
        disclosure = page.locator("details.fit-evidence-disclosure")
        disclosure.locator(":scope > summary").click()
        table = page.get_by_role("table", name="Hardening candidate comparison")
        table.wait_for(timeout=30_000)
        if page.get_by_role("button", name="Save fit & continue", exact=True).count() != 1:
            raise RuntimeError("Fit must expose one top-row Save fit & continue action")
        table.get_by_role("button", name=re.compile(r"^Select .+ candidate$")).last.click()
        page.get_by_role("textbox", name="Candidate selection reason").fill(
            "Best agreement over the measured strain range."
        )
        acknowledgement = page.get_by_role(
            "checkbox", name="Acknowledge selected candidate warning"
        )
        if acknowledgement.count():
            acknowledgement.check()
        if page.get_by_role("button", name="Save fit & continue", exact=True).is_disabled():
            raise RuntimeError("Fit selection did not enable the top-row save action")
        disclosure.locator(":scope > summary").click()
        _capture(page, output / f"modeling-fit-{width}x{height}.png", width, height)
        measurements.append(
            {
                "stage": "fit",
                "viewport": f"{width}x{height}",
                **_measure_process_fit(page, "fit", width, height),
            }
        )
        page.context.close()
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
) -> list[dict[str, float]]:
    measurements: list[dict[str, float]] = []
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


def _capture_modeling_data_session(
    browser: Browser, base_url: str, output: Path
) -> list[dict[str, float]]:
    """Refresh the Data and new-session evidence after user-facing copy changes."""
    measurements: list[dict[str, float]] = []
    _capture_modeling_session_shell(browser, base_url, output)
    for width, height in VIEWPORTS:
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
        measurements.append(
            {
                "stage": "data",
                "viewport": f"{width}x{height}",
                **_measure_process_fit(page, "data", width, height),
            }
        )
        page.context.close()
    return measurements


def _capture_modeling_session_shell(browser: Browser, base_url: str, output: Path) -> None:
    """Capture the pin-free Data-first state separately from the populated Data workflow."""
    for width, height in VIEWPORTS:
        page = _new_page(browser, base_url, width, height)
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
              const raw = sessionStorage.getItem("cmp.modeling.recent-session.v3");
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
        _capture(page, output / f"modeling-session-{width}x{height}.png", width, height)
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
        help="Capture and replace only the six Modeling Process/Fit viewports.",
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
            "Capture the six current Modeling Data/session screens with the same consistency gates."
        ),
    )
    args = parser.parse_args()

    def produce(output: Path) -> None:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                _capture_materials(browser, args.base_url, output)
                _capture_solver_delivery(browser, args.base_url, output)
                _capture_modeling_session_shell(browser, args.base_url, output)
                _capture_modeling(browser, args.base_url, output)
                _capture_supporting_screens(browser, args.base_url, output)
            finally:
                browser.close()

    if (
        args.only_materials
        or args.only_modeling_export
        or args.only_modeling_process_fit
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
                    measurements = (
                        _capture_materials(browser, args.base_url, staged)
                        if args.only_materials
                        else _capture_modeling_export_only(browser, args.base_url, staged)
                        if args.only_modeling_export
                        else _capture_modeling_process_fit(browser, args.base_url, staged)
                        if args.only_modeling_process_fit
                        else _capture_modeling_consistency(browser, args.base_url, staged)
                        if args.only_modeling_consistency
                        else _capture_modeling_data_session(browser, args.base_url, staged)
                        if args.only_modeling_data_session
                        else _capture_activity(browser, args.base_url, staged)
                        if args.only_activity
                        else _capture_solver_delivery(browser, args.base_url, staged)
                        if args.only_review_submission
                        else _capture_supporting_screens(browser, args.base_url, staged)
                        if args.only_product_access
                        else _capture_administration_records(browser, args.base_url, staged)
                        if args.only_administration_records
                        else _capture_administration_database(browser, args.base_url, staged)
                    )
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
                if args.only_administration_database or args.only_administration_records
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

# ruff: noqa: E501, B023
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from playwright.sync_api import Page, sync_playwright

TARGET_ID_1440 = "materials-search-normal-1440x900"
TARGET_ID_1366 = "materials-search-normal-1366x768"
TARGET_ID_1920 = "materials-search-normal-1920x1080"
ROOT = Path(__file__).resolve().parents[3]
RESULT_COUNT_TEXT = "1\u201350 of 10,000 matches"
RESULT_RANGE_TEXT = "Rows 1\u201350 of 10,000 matches"
RESULT_FIRST = ("DP780 synthetic demo steel", "DP780-REF")
RESULT_LAST = ("Synthetic steel demo record 50", "STEEL-DEMO-50")
WIDE_VIEWPORTS = (
    {"width": 2560, "height": 1440, "device_scale_factor": 1},
    {"width": 3840, "height": 2160, "device_scale_factor": 1},
)
TARGETS = {
    TARGET_ID_1440: {
        "html": ROOT / "docs/00-research/ux-service-reference/materials-search-normal.html",
        "image": ROOT
        / (
            "docs/17-evidence/images/issue-167-service-reference/"
            "materials-search-normal-1440x900.png"
        ),
        "measurements": ROOT
        / (
            "docs/17-evidence/images/issue-167-service-reference/"
            "materials-search-normal-1440x900.measurements.json"
        ),
        "viewport": {"width": 1440, "height": 900, "device_scale_factor": 1},
        "navigator_width": 264,
        "context_visible": True,
        "context_width": 280,
        "expected_divider_count": 2,
        "result_width": {"exact": 870},
        "splitter_expectations": {
            "default": {
                "widths": [264, 870, 280],
                "aria_now": [264, 280],
                "aria_maximum": [360, 480],
            },
            "navigator_arrow_right": {
                "widths": [272, 862, 280],
                "aria_now": [272, 280],
                "aria_maximum": [360, 480],
            },
            "navigator_home": {
                "widths": [200, 934, 280],
                "aria_now": [200, 280],
                "aria_maximum": [360, 480],
                "tree_horizontal_overflow": 41,
                "tree_horizontal_rail": True,
            },
            "navigator_end": {
                "widths": [360, 774, 280],
                "aria_now": [360, 280],
                "aria_maximum": [360, 480],
            },
        },
        "splitter_steps": [
            {"label": "navigator_arrow_right", "splitter": "navigator", "key": "ArrowRight"},
            {"label": "navigator_home", "splitter": "navigator", "key": "Home"},
            {"label": "navigator_end", "splitter": "navigator", "key": "End"},
        ],
    },
    TARGET_ID_1366: {
        "html": ROOT / "docs/00-research/ux-service-reference/materials-search-normal.html",
        "css_override": ROOT
        / "docs/00-research/ux-service-reference/materials-search-normal-1366x768.css",
        "javascript_override": ROOT
        / "docs/00-research/ux-service-reference/materials-search-normal-1366x768.js",
        "image": ROOT
        / (
            "docs/17-evidence/images/issue-167-service-reference/"
            "materials-search-normal-1366x768.png"
        ),
        "measurements": ROOT
        / (
            "docs/17-evidence/images/issue-167-service-reference/"
            "materials-search-normal-1366x768.measurements.json"
        ),
        "viewport": {"width": 1366, "height": 768, "device_scale_factor": 1},
        "navigator_width": 244,
        "context_visible": True,
        "context_width": 280,
        "expected_divider_count": 2,
        "result_width": {"exact": 816},
        "splitter_expectations": {
            "default": {
                "widths": [244, 816, 280],
                "aria_now": [244, 280],
                "aria_maximum": [340, 376],
            },
            "navigator_arrow_right": {
                "widths": [252, 808, 280],
                "aria_now": [252, 280],
                "aria_maximum": [340, 368],
            },
            "navigator_home": {
                "widths": [200, 860, 280],
                "aria_now": [200, 280],
                "aria_maximum": [340, 420],
                "tree_horizontal_overflow": 41,
                "tree_horizontal_rail": True,
            },
            "navigator_end": {
                "widths": [340, 720, 280],
                "aria_now": [340, 280],
                "aria_maximum": [340, 280],
            },
            "context_arrow_left": {
                "widths": [244, 808, 288],
                "aria_now": [244, 288],
                "aria_maximum": [332, 376],
            },
            "context_home": {
                "widths": [244, 836, 260],
                "aria_now": [244, 260],
                "aria_maximum": [360, 376],
            },
            "context_end": {
                "widths": [244, 720, 376],
                "aria_now": [244, 376],
                "aria_maximum": [244, 376],
            },
        },
        "splitter_steps": [
            {"label": "navigator_arrow_right", "splitter": "navigator", "key": "ArrowRight"},
            {"label": "navigator_home", "splitter": "navigator", "key": "Home"},
            {"label": "navigator_end", "splitter": "navigator", "key": "End"},
            {
                "label": "context_arrow_left",
                "splitter": "context",
                "key": "ArrowLeft",
                "reload": True,
            },
            {"label": "context_home", "splitter": "context", "key": "Home"},
            {"label": "context_end", "splitter": "context", "key": "End"},
        ],
    },
    TARGET_ID_1920: {
        "html": ROOT / "docs/00-research/ux-service-reference/materials-search-normal.html",
        "css_override": ROOT
        / "docs/00-research/ux-service-reference/materials-search-normal-1920x1080.css",
        "javascript_override": ROOT
        / "docs/00-research/ux-service-reference/materials-search-normal-1920x1080.js",
        "image": ROOT
        / (
            "docs/17-evidence/images/issue-167-service-reference/"
            "materials-search-normal-1920x1080.png"
        ),
        "measurements": ROOT
        / (
            "docs/17-evidence/images/issue-167-service-reference/"
            "materials-search-normal-1920x1080.measurements.json"
        ),
        "viewport": {"width": 1920, "height": 1080, "device_scale_factor": 1},
        "navigator_width": 280,
        "context_visible": True,
        "context_width": 300,
        "expected_divider_count": 2,
        "result_width": {"exact": 1314},
        "wide_evidence": WIDE_VIEWPORTS,
        "splitter_expectations": {
            "default": {
                "widths": [280, 1314, 300],
                "aria_now": [280, 300],
                "aria_maximum": [360, 480],
            },
            "navigator_arrow_right": {
                "widths": [288, 1306, 300],
                "aria_now": [288, 300],
                "aria_maximum": [360, 480],
            },
            "navigator_home": {
                "widths": [200, 1394, 300],
                "aria_now": [200, 300],
                "aria_maximum": [360, 480],
                "tree_horizontal_overflow": 41,
                "tree_horizontal_rail": True,
            },
            "navigator_end": {
                "widths": [360, 1234, 300],
                "aria_now": [360, 300],
                "aria_maximum": [360, 480],
            },
            "context_arrow_left": {
                "widths": [280, 1306, 308],
                "aria_now": [280, 308],
                "aria_maximum": [360, 480],
            },
            "context_home": {
                "widths": [280, 1354, 260],
                "aria_now": [280, 260],
                "aria_maximum": [360, 480],
            },
            "context_end": {
                "widths": [280, 1134, 480],
                "aria_now": [280, 480],
                "aria_maximum": [360, 480],
            },
        },
        "splitter_steps": [
            {"label": "navigator_arrow_right", "splitter": "navigator", "key": "ArrowRight"},
            {"label": "navigator_home", "splitter": "navigator", "key": "Home"},
            {"label": "navigator_end", "splitter": "navigator", "key": "End"},
            {
                "label": "context_arrow_left",
                "splitter": "context",
                "key": "ArrowLeft",
                "reload": True,
            },
            {"label": "context_home", "splitter": "context", "key": "Home"},
            {"label": "context_end", "splitter": "context", "key": "End"},
        ],
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Capture and measure a static CAE Material Platform service reference."
    )
    parser.add_argument("--target", choices=sorted(TARGETS), help="Registered reference target id.")
    parser.add_argument("--html", type=Path, help="Exact static HTML path.")
    parser.add_argument("--image", type=Path, help="Exact output PNG path.")
    parser.add_argument("--measurements", type=Path, help="Exact output measurement JSON path.")
    parser.add_argument(
        "--wide-evidence",
        action="store_true",
        help="Also capture 2560x1440 and 3840x2160 supporting evidence for the 1920 target.",
    )
    args = parser.parse_args()

    if args.target is None and (args.html is None or args.image is None):
        parser.error("provide --target or both --html and --image")
    if args.wide_evidence and args.target != TARGET_ID_1920:
        parser.error("--wide-evidence requires --target materials-search-normal-1920x1080")
    return args


def resolve_paths(args: argparse.Namespace) -> tuple[str, Path, Path, Path, dict[str, Any]]:
    registered = TARGETS.get(args.target, {}) if args.target else {}
    html_path = args.html or registered.get("html")
    image_path = args.image or registered.get("image")
    if html_path is None or image_path is None:
        raise SystemExit("target configuration is missing HTML or image path")
    html = html_path.resolve()
    image = image_path.resolve()
    measurements_arg = args.measurements or registered.get("measurements")
    measurements = (
        measurements_arg.resolve()
        if measurements_arg
        else image.with_suffix(".measurements.json")
    )
    target = args.target or image.stem
    config = TARGETS.get(target, TARGETS[TARGET_ID_1440])
    return target, html, image, measurements, config


def rounded_box(page: Page, selector: str) -> dict[str, float]:
    box = page.locator(selector).bounding_box()
    if box is None:
        raise AssertionError(f"{selector} is not visible")
    return {key: round(value, 2) for key, value in box.items()}


def assert_close(actual: float, expected: float, name: str, tolerance: float = 0.6) -> None:
    if abs(actual - expected) > tolerance:
        raise AssertionError(f"{name}: expected {expected}px, got {actual}px")


def assert_between(actual: float, minimum: float, maximum: float, name: str) -> None:
    if actual < minimum or actual > maximum:
        raise AssertionError(f"{name}: expected {minimum} to {maximum}px, got {actual}px")


def collect_measurements(
    page: Page,
    target: str,
    config: dict[str, Any],
    splitter_evidence: dict[str, Any] | None = None,
    navigator_fixture: dict[str, Any] | None = None,
    result_fixture: dict[str, Any] | None = None,
) -> dict[str, Any]:
    context_visible = page.locator("[data-region='selected-context']").is_visible()
    regions = {
        "application_bar": rounded_box(page, "[data-region='application-bar']"),
        "command_bar": rounded_box(page, "[data-region='command-bar']"),
        "search_band": rounded_box(page, "[data-region='search-band']"),
        "workspace": rounded_box(page, "[data-region='materials-workspace']"),
        "navigator": rounded_box(page, "[data-region='navigator']"),
        "navigator_divider": rounded_box(page, "[data-region='navigator-divider']"),
        "results": rounded_box(page, "[data-region='results']"),
        "context_divider": (
            rounded_box(page, "[data-region='context-divider']") if context_visible else None
        ),
        "selected_context": (
            rounded_box(page, "[data-region='selected-context']") if context_visible else None
        ),
        "status_bar": rounded_box(page, "[data-region='status-bar']"),
    }
    divider_visual_widths = page.locator(".splitter > span").evaluate_all(
        """(elements) => elements
          .filter((element) => {
            const parent = element.parentElement;
            const parentBox = parent?.getBoundingClientRect();
            const style = parent ? getComputedStyle(parent) : null;
            return style?.display !== "none" && parentBox?.width > 0 && parentBox?.height > 0;
          })
          .map((element) => element.getBoundingClientRect().width)"""
    )
    tree_row_heights = page.locator("[role='treeitem']").evaluate_all(
        "(elements) => elements.map((element) => element.getBoundingClientRect().height)"
    )
    result_row_heights = page.locator("[data-result-row]").evaluate_all(
        "(elements) => elements.map((element) => element.getBoundingClientRect().height)"
    )
    overflow = page.evaluate(
        """() => ({
          documentHorizontal:
            document.documentElement.scrollWidth - document.documentElement.clientWidth,
          documentVertical:
            document.documentElement.scrollHeight - document.documentElement.clientHeight,
          bodyHorizontal: document.body.scrollWidth - document.body.clientWidth,
          bodyVertical: document.body.scrollHeight - document.body.clientHeight
        })"""
    )
    table_headers = page.locator(".results-table th .column-label").all_text_contents()
    sticky_header = page.locator(".results-table th").first.evaluate(
        "(element) => getComputedStyle(element).position"
    )
    tree_scroller = page.locator(".tree-scroll").evaluate(
        """(element) => {
          const shell = element.closest('[data-scroll-shell]');
          const vertical = document.querySelector('#tree-scrollbar-y');
          const horizontal = document.querySelector('#tree-scrollbar-x');
          const rail = (candidate) => {
            const box = candidate?.getBoundingClientRect();
            const thumb = candidate?.querySelector('.app-scrollbar-thumb')?.getBoundingClientRect();
            return {
              visible: Boolean(candidate && !candidate.hidden && box && box.width > 0 && box.height > 0),
              orientation: candidate?.getAttribute('aria-orientation') || '',
              aria_min: Number(candidate?.getAttribute('aria-valuemin') || 0),
              aria_max: Number(candidate?.getAttribute('aria-valuemax') || 0),
              aria_now: Number(candidate?.getAttribute('aria-valuenow') || 0),
              track: box ? {left: box.left, top: box.top, right: box.right, bottom: box.bottom, width: box.width, height: box.height, background: getComputedStyle(candidate).backgroundColor} : null,
              thumb: thumb ? {left: thumb.left, top: thumb.top, right: thumb.right, bottom: thumb.bottom, width: thumb.width, height: thumb.height, background: getComputedStyle(candidate.querySelector('.app-scrollbar-thumb')).backgroundColor} : null,
            };
          };
          const contentRight = element.getBoundingClientRect().right;
          const kindRightEdges = [...element.querySelectorAll(".tree-kind")]
            .map((kind) => kind.getBoundingClientRect().right);
          const identities = [...element.querySelectorAll('[role="treeitem"]')].map((row) => {
            const label = row.querySelector('.tree-label');
            const kind = row.querySelector('.tree-kind');
            return {
              kind: row.dataset.kind,
              identity: label?.textContent || '',
              title: label?.title || '',
              accessible_name: row.getAttribute('aria-label') || '',
              glyph_title: kind?.title || '',
              glyph_kind: kind?.dataset.kind || '',
              glyph_font_size: getComputedStyle(kind).fontSize,
            };
          });
          return {
            horizontal_overflow: element.scrollWidth - element.clientWidth,
            vertical_overflow: element.scrollHeight - element.clientHeight,
            content_right: contentRight,
            scroll_width: element.scrollWidth,
            scroll_height: element.scrollHeight,
            client_width: element.clientWidth,
            client_height: element.clientHeight,
            shell_scroll_x: shell?.dataset.scrollX === 'true',
            shell_scroll_y: shell?.dataset.scrollY === 'true',
            rails: {vertical: rail(vertical), horizontal: rail(horizontal)},
            identities,
            tree_kind_right_edges: kindRightEdges,
            all_tree_kind_right_edges_within_content:
              kindRightEdges.every((right) => right <= contentRight + 0.01)
          };
        }"""
    )
    result_scroller = page.locator("#results-scroll").evaluate(
        """(element) => {
          const shell = element.closest('[data-scroll-shell]');
          const vertical = document.querySelector('#results-scrollbar-y');
          const horizontal = document.querySelector('#results-scrollbar-x');
          const rail = (candidate) => {
            const box = candidate?.getBoundingClientRect();
            const thumb = candidate?.querySelector('.app-scrollbar-thumb')?.getBoundingClientRect();
            return {
              visible: Boolean(candidate && !candidate.hidden && box && box.width > 0 && box.height > 0),
              orientation: candidate?.getAttribute('aria-orientation') || '',
              aria_min: Number(candidate?.getAttribute('aria-valuemin') || 0),
              aria_max: Number(candidate?.getAttribute('aria-valuemax') || 0),
              aria_now: Number(candidate?.getAttribute('aria-valuenow') || 0),
              track: box ? {left: box.left, top: box.top, right: box.right, bottom: box.bottom, width: box.width, height: box.height, background: getComputedStyle(candidate).backgroundColor} : null,
              thumb: thumb ? {left: thumb.left, top: thumb.top, right: thumb.right, bottom: thumb.bottom, width: thumb.width, height: thumb.height, background: getComputedStyle(candidate.querySelector('.app-scrollbar-thumb')).backgroundColor} : null,
            };
          };
          const viewport = element.getBoundingClientRect();
          const header = document.querySelector('.results-table th')?.getBoundingClientRect();
          const footer = document.querySelector('.results-pagination')?.getBoundingClientRect();
          const rows = [...document.querySelectorAll('[data-result-row]')];
          const first = rows[0];
          const last = rows.at(-1);
          const visibleRows = rows.filter((row) => {
            const box = row.getBoundingClientRect();
            return box.bottom > viewport.top && box.top < viewport.bottom;
          });
          const rowRecord = (row) => ({
            name: row?.dataset.name || '',
            grade: row?.dataset.grade || '',
            text: row?.querySelector('.material-identity strong')?.textContent || '',
            title: row?.querySelector('.material-identity')?.title || '',
          });
          return {
            client_width: element.clientWidth,
            client_height: element.clientHeight,
            scroll_width: element.scrollWidth,
            scroll_height: element.scrollHeight,
            horizontal_overflow: element.scrollWidth - element.clientWidth,
            vertical_overflow: element.scrollHeight - element.clientHeight,
            scroll_left: element.scrollLeft,
            scroll_top: element.scrollTop,
            shell_scroll_x: shell?.dataset.scrollX === 'true',
            shell_scroll_y: shell?.dataset.scrollY === 'true',
            viewport: {left: viewport.left, top: viewport.top, right: viewport.right, bottom: viewport.bottom, width: viewport.width, height: viewport.height},
            header: header ? {left: header.left, top: header.top, right: header.right, bottom: header.bottom, width: header.width, height: header.height} : null,
            footer: footer ? {left: footer.left, top: footer.top, right: footer.right, bottom: footer.bottom, width: footer.width, height: footer.height} : null,
            rails: {vertical: rail(vertical), horizontal: rail(horizontal)},
            rows: {count: rows.length, first: rowRecord(first), last: rowRecord(last)},
            visible_row_count: visibleRows.length,
            visible_rows_fully_contained: visibleRows.every((row) => {
              const box = row.getBoundingClientRect();
              return box.top >= viewport.top - 0.5 && box.bottom <= viewport.bottom + 0.5;
            }),
            selected_row_visible: Boolean(rows.find((row) => row.getAttribute('aria-selected') === 'true')?.getBoundingClientRect().top >= viewport.top && rows.find((row) => row.getAttribute('aria-selected') === 'true')?.getBoundingClientRect().bottom <= viewport.bottom),
            sticky_header_position: document.querySelector('.results-table th') ? getComputedStyle(document.querySelector('.results-table th')).position : '',
            footer_range: document.querySelector('#results-range')?.textContent || '',
            next_page_visible: Boolean(document.querySelector('#results-next-page')?.checkVisibility()),
          };
        }"""
    )
    context_content = {
        "selected_summary": page.locator(".selected-summary").is_visible(),
        "open_datasheet": page.locator("#open-datasheet").is_visible(),
    }

    return {
        "target": target,
        "capture_date": "2026-07-28",
        "viewport": config["viewport"],
        "regions": regions,
        "divider_visual_widths": divider_visual_widths,
        "visible_splitter_count": len(divider_visual_widths),
        "row_density": {
            "tree": {
                "count": len(tree_row_heights),
                "minimum": min(tree_row_heights),
                "maximum": max(tree_row_heights),
            },
            "results": {
                "count": len(result_row_heights),
                "minimum": min(result_row_heights),
                "maximum": max(result_row_heights),
            },
        },
        "table_headers": table_headers,
        "table_header_position": sticky_header,
        "tree_scroller": tree_scroller,
        "result_scroller": result_scroller,
        "result_count": page.locator(".result-count").text_content() or "",
        "result_range": page.locator("#results-range").text_content() or "",
        "context_content": context_content,
        "selected_result_rows": page.locator("[data-result-row][aria-selected='true']").count(),
        "selected_tree_rows": page.locator("[role='treeitem'][aria-selected='true']").count(),
        "visible_selected_context": context_visible,
        "context_state": "visible" if context_visible else "collapsed",
        "primary_command_count": page.locator(".primary-action").count(),
        "nested_persistent_card_count": page.locator(
            ".card, .content-card, .module-material-card"
        ).count(),
        "overflow": overflow,
        "interactions": {
            "search_shortcut": page.locator("body").get_attribute("data-query-applied") == "steel",
            "tree_keyboard": page.locator("body").get_attribute("data-selected-tree-id")
            == "tree-dp780",
            "tree_pointer_record_sync": page.locator("body").get_attribute(
                "data-tree-pointer-record-sync"
            )
            == "true",
            "tree_keyboard_record_sync": page.locator("body").get_attribute(
                "data-tree-keyboard-record-sync"
            )
            == "true",
            "tree_non_record_preserves_context": page.locator("body").get_attribute(
                "data-tree-non-record-preserves-context"
            )
            == "true",
            "result_enter": page.locator("body").get_attribute("data-datasheet-consequence")
            == "DP780-REF",
        },
        "splitter_evidence": splitter_evidence,
        "navigator_fixture": navigator_fixture,
        "result_fixture": result_fixture,
    }


def exercise_interactions(page: Page) -> None:
    page.keyboard.press("Control+K")
    active_id = page.evaluate("document.activeElement?.id")
    if active_id != "material-query":
        raise AssertionError(f"Control+K did not focus material-query: {active_id}")
    page.keyboard.press("Enter")
    if page.locator("body").get_attribute("data-query-applied") != "steel":
        raise AssertionError("search submit did not preserve and apply the steel query")

    dp780 = page.locator("#tree-dp780")
    dp780.focus()
    page.keyboard.press("Home")
    if page.evaluate("document.activeElement?.id") != "tree-database":
        raise AssertionError("tree Home did not focus the first row")
    page.keyboard.press("End")
    if page.evaluate("document.activeElement?.id") != "tree-dp600":
        raise AssertionError("tree End did not focus the last row")
    page.keyboard.press("ArrowUp")
    if page.evaluate("document.activeElement?.id") != "tree-dp780":
        raise AssertionError("tree ArrowUp did not move to the previous row")
    page.keyboard.press("ArrowDown")
    if page.evaluate("document.activeElement?.id") != "tree-dp600":
        raise AssertionError("tree ArrowDown did not move to the next row")

    dp600 = page.locator("#tree-dp600")
    dp600.click()
    if (
        dp600.get_attribute("aria-selected") != "true"
        or page.locator("[data-result-row][data-grade='DP600-REF']").get_attribute(
            "aria-selected"
        )
        != "true"
        or page.locator("#selected-grade").text_content() != "DP600-REF"
        or page.locator("body").get_attribute("data-selected-result") != "DP600-REF"
    ):
        raise AssertionError("tree pointer selection did not synchronize DP600 context")
    page.locator("body").evaluate(
        "(element) => { element.dataset.treePointerRecordSync = 'true'; }"
    )

    page.locator("#tree-metals").click()
    if (
        page.locator("#selected-grade").text_content() != "DP600-REF"
        or page.locator("body").get_attribute("data-selected-result") != "DP600-REF"
    ):
        raise AssertionError("non-Record tree selection fabricated a material context")
    page.locator("body").evaluate(
        "(element) => { element.dataset.treeNonRecordPreservesContext = 'true'; }"
    )

    dp780.focus()
    page.keyboard.press("Enter")
    if (
        dp780.get_attribute("aria-selected") != "true"
        or page.locator("[data-result-row][data-grade='DP780-REF']").get_attribute(
            "aria-selected"
        )
        != "true"
        or page.locator("#selected-grade").text_content() != "DP780-REF"
        or page.locator("body").get_attribute("data-selected-result") != "DP780-REF"
    ):
        raise AssertionError("tree Enter did not synchronize DP780 context")
    page.locator("body").evaluate(
        "(element) => { element.dataset.treeKeyboardRecordSync = 'true'; }"
    )

    selected_row = page.locator("[data-result-row]").first
    selected_row.focus()
    page.keyboard.press("Enter")
    if page.locator("body").get_attribute("data-datasheet-consequence") != "DP780-REF":
        raise AssertionError("result-row Enter did not expose the datasheet consequence")
    open_datasheet = page.locator("#open-datasheet")
    if open_datasheet.is_visible():
        open_datasheet.click()
        if page.locator("body").get_attribute("data-datasheet-consequence") != "DP780-REF":
            raise AssertionError(
                "Open datasheet did not preserve the selected datasheet consequence"
            )
    page.evaluate("document.activeElement?.blur()")


def navigator_fixture_snapshot(page: Page) -> dict[str, Any]:
    return page.locator(".tree-scroll").evaluate(
        """(element) => {
          const shell = element.closest('[data-scroll-shell]');
          const rail = (selector) => {
            const candidate = document.querySelector(selector);
            const box = candidate?.getBoundingClientRect();
            const thumb = candidate?.querySelector('.app-scrollbar-thumb')?.getBoundingClientRect();
          return {
            visible: Boolean(candidate && !candidate.hidden && box && box.width > 0 && box.height > 0),
            orientation: candidate?.getAttribute('aria-orientation') || '',
            aria_min: Number(candidate?.getAttribute('aria-valuemin') || 0),
              aria_max: Number(candidate?.getAttribute('aria-valuemax') || 0),
              aria_now: Number(candidate?.getAttribute('aria-valuenow') || 0),
              track: box ? {left: box.left, top: box.top, right: box.right, bottom: box.bottom, width: box.width, height: box.height, background: getComputedStyle(candidate).backgroundColor} : null,
              thumb: thumb ? {left: thumb.left, top: thumb.top, right: thumb.right, bottom: thumb.bottom, width: thumb.width, height: thumb.height, background: getComputedStyle(candidate.querySelector('.app-scrollbar-thumb')).backgroundColor} : null,
            };
          };
          return {
            client_width: element.clientWidth,
            client_height: element.clientHeight,
            scroll_width: element.scrollWidth,
            scroll_height: element.scrollHeight,
            scroll_left: element.scrollLeft,
            scroll_top: element.scrollTop,
            shell_scroll_x: shell?.dataset.scrollX === 'true',
            shell_scroll_y: shell?.dataset.scrollY === 'true',
            vertical: rail('#tree-scrollbar-y'),
            horizontal: rail('#tree-scrollbar-x'),
            identity: (() => {
              const row = element.querySelector('#tree-dp780');
              const label = row?.querySelector('.tree-label');
              const box = label?.getBoundingClientRect();
              return {text: label?.textContent || '', title: label?.title || '', right: box?.right || 0};
            })(),
          };
        }"""
    )


def exercise_navigator_fixture(page: Page) -> dict[str, Any]:
    page.evaluate(
        """() => {
          const tree = document.querySelector('#material-tree');
          const selected = document.querySelector('#tree-dp780');
          if (!tree || !selected) throw new Error('normal navigator fixture target is missing');
          const label = selected.querySelector('.tree-label');
          const longIdentity = 'DP780 synthetic demo steel — exact governed identity with an extended local qualification label for review';
          label.textContent = longIdentity;
          label.title = longIdentity;
          selected.setAttribute('aria-label', `Record: ${longIdentity}`);
          for (let index = 0; index < 42; index += 1) {
            const row = document.createElement('div');
            row.className = `tree-row depth-${index % 3}`;
            row.setAttribute('role', 'treeitem');
            row.setAttribute('aria-level', String((index % 3) + 1));
            row.setAttribute('aria-selected', 'false');
            row.tabIndex = -1;
            row.dataset.kind = 'Record';
            row.setAttribute('aria-label', `Record: Fixture record ${String(index + 1).padStart(2, '0')}`);
            row.innerHTML = `<span class="tree-disclosure" aria-hidden="true"></span><span class="tree-kind" data-kind="Record" title="Record" aria-hidden="true">Record</span><span class="tree-label" title="Fixture record ${index + 1}">Fixture record ${String(index + 1).padStart(2, '0')}</span>`;
            tree.append(row);
          }
          window.MaterialsNavigator?.syncAll();
        }"""
    )
    page.wait_for_timeout(80)
    initial = navigator_fixture_snapshot(page)
    if not initial["shell_scroll_x"] or not initial["shell_scroll_y"]:
        raise AssertionError(f"fixture did not expose both navigator rails: {initial}")
    if initial["scroll_width"] <= initial["client_width"] or initial["scroll_height"] <= initial["client_height"]:
        raise AssertionError(f"fixture did not overflow both axes: {initial}")
    rails = (initial["vertical"], initial["horizontal"])
    for rail in rails:
        if not rail["visible"] or not rail["track"] or not rail["thumb"]:
            raise AssertionError(f"fixture rail is not visible: {initial}")
        if rail["track"]["background"] == rail["thumb"]["background"]:
            raise AssertionError(f"fixture rail track/thumb are not distinct: {initial}")
        if rail["aria_max"] <= 0 or rail["aria_now"] != 0:
            raise AssertionError(f"fixture rail ARIA range is not synchronized at origin: {initial}")
    vertical_track = initial["vertical"]["track"]
    horizontal_track = initial["horizontal"]["track"]
    viewport_box = page.locator(".tree-scroll").bounding_box()
    if viewport_box is None or vertical_track["left"] < viewport_box["x"] + viewport_box["width"] - 0.5 or horizontal_track["top"] < viewport_box["y"] + viewport_box["height"] - 0.5:
        raise AssertionError(f"fixture rails do not reserve gutters outside row text: {initial}")
    page.locator(".tree-scroll").evaluate("(element) => { element.scrollTop = 0; element.scrollLeft = 0; }")
    before_wheel = navigator_fixture_snapshot(page)
    page.locator(".tree-scroll").hover()
    page.mouse.wheel(0, 360)
    page.wait_for_timeout(20)
    after_wheel = navigator_fixture_snapshot(page)
    page.locator(".tree-scroll").focus()
    before_page = navigator_fixture_snapshot(page)
    page.keyboard.press("PageDown")
    page.wait_for_timeout(20)
    after_page = navigator_fixture_snapshot(page)
    page.locator(".tree-scroll").evaluate("(element) => { element.scrollTop = 0; element.scrollLeft = 0; }")
    page.locator("#tree-scrollbar-y").focus()
    page.keyboard.press("End")
    page.wait_for_timeout(20)
    vertical_end = navigator_fixture_snapshot(page)
    page.keyboard.press("Home")
    page.keyboard.press("ArrowDown")
    page.wait_for_timeout(20)
    vertical_arrow = navigator_fixture_snapshot(page)
    page.locator("#tree-scrollbar-x").focus()
    page.keyboard.press("End")
    page.wait_for_timeout(20)
    horizontal_end = navigator_fixture_snapshot(page)
    identity_reachable = horizontal_end["scroll_left"] >= horizontal_end["scroll_width"] - horizontal_end["client_width"] - 1 and horizontal_end["identity"]["right"] <= page.locator(".tree-scroll").bounding_box()["x"] + page.locator(".tree-scroll").bounding_box()["width"] + 1
    page.keyboard.press("Home")
    page.keyboard.press("ArrowRight")
    page.wait_for_timeout(20)
    horizontal_arrow = navigator_fixture_snapshot(page)
    page.locator(".tree-scroll").evaluate("(element) => { element.scrollTop = 0; element.scrollLeft = 0; }")
    page.locator("#tree-scrollbar-y").focus()
    vertical_thumb = page.locator("#tree-scrollbar-y .app-scrollbar-thumb").bounding_box()
    if vertical_thumb is None:
        raise AssertionError("fixture vertical thumb is missing before pointer exercise")
    start_x = vertical_thumb["x"] + vertical_thumb["width"] / 2
    start_y = vertical_thumb["y"] + vertical_thumb["height"] / 2
    page.mouse.move(start_x, start_y)
    page.mouse.down()
    page.mouse.move(start_x, start_y + 36, steps=4)
    page.mouse.up()
    page.wait_for_timeout(20)
    vertical_pointer = navigator_fixture_snapshot(page)
    page.locator(".tree-scroll").evaluate("(element) => { element.scrollTop = 0; element.scrollLeft = 0; }")
    page.locator("#tree-scrollbar-x").focus()
    horizontal_thumb = page.locator("#tree-scrollbar-x .app-scrollbar-thumb").bounding_box()
    if horizontal_thumb is None:
        raise AssertionError("fixture horizontal thumb is missing before pointer exercise")
    start_x = horizontal_thumb["x"] + horizontal_thumb["width"] / 2
    start_y = horizontal_thumb["y"] + horizontal_thumb["height"] / 2
    page.mouse.move(start_x, start_y)
    page.mouse.down()
    page.mouse.move(start_x + 36, start_y, steps=4)
    page.mouse.up()
    page.wait_for_timeout(20)
    horizontal_pointer = navigator_fixture_snapshot(page)
    return {
        "initial": initial,
        "wheel_moved": after_wheel["scroll_top"] > before_wheel["scroll_top"],
        "page_down_moved": after_page["scroll_top"] > before_page["scroll_top"],
        "vertical_end_reached": vertical_end["scroll_top"] >= vertical_end["scroll_height"] - vertical_end["client_height"] - 1 and vertical_end["vertical"]["aria_now"] == vertical_end["scroll_height"] - vertical_end["client_height"],
        "vertical_arrow_moved": vertical_arrow["scroll_top"] > 0,
        "horizontal_end_reached": horizontal_end["scroll_left"] >= horizontal_end["scroll_width"] - horizontal_end["client_width"] - 1 and horizontal_end["horizontal"]["aria_now"] == horizontal_end["scroll_width"] - horizontal_end["client_width"],
        "horizontal_arrow_moved": horizontal_arrow["scroll_left"] > 0,
        "identity_reachable_at_horizontal_end": identity_reachable,
        "vertical_pointer_moved": vertical_pointer["scroll_top"] > 0 and vertical_pointer["vertical"]["aria_now"] == vertical_pointer["scroll_top"],
        "horizontal_pointer_moved": horizontal_pointer["scroll_left"] > 0 and horizontal_pointer["horizontal"]["aria_now"] == horizontal_pointer["scroll_left"],
        "rails_outside_text": True,
        "proportional_thumbs": initial["vertical"]["thumb"]["height"] < initial["vertical"]["track"]["height"] and initial["horizontal"]["thumb"]["width"] < initial["horizontal"]["track"]["width"],
    }


def result_fixture_snapshot(page: Page) -> dict[str, Any]:
    return page.locator("#results-scroll").evaluate(
        """(element) => {
          const rail = (selector) => {
            const candidate = document.querySelector(selector);
            const box = candidate?.getBoundingClientRect();
            const thumb = candidate?.querySelector('.app-scrollbar-thumb')?.getBoundingClientRect();
            return {
              visible: Boolean(candidate && !candidate.hidden && box && box.width > 0 && box.height > 0),
              aria_max: Number(candidate?.getAttribute('aria-valuemax') || 0),
              aria_now: Number(candidate?.getAttribute('aria-valuenow') || 0),
              track: box ? {left: box.left, top: box.top, right: box.right, bottom: box.bottom, width: box.width, height: box.height, background: getComputedStyle(candidate).backgroundColor} : null,
              thumb: thumb ? {left: thumb.left, top: thumb.top, right: thumb.right, bottom: thumb.bottom, width: thumb.width, height: thumb.height, background: getComputedStyle(candidate.querySelector('.app-scrollbar-thumb')).backgroundColor} : null,
            };
          };
          const viewport = element.getBoundingClientRect();
          const header = document.querySelector('.results-table th')?.getBoundingClientRect();
          const footer = document.querySelector('.results-pagination')?.getBoundingClientRect();
          const rows = [...document.querySelectorAll('[data-result-row]')];
          const selected = rows.find((row) => row.getAttribute('aria-selected') === 'true');
          const visibleRows = rows.filter((row) => {
            const box = row.getBoundingClientRect();
            return box.bottom > viewport.top && box.top < viewport.bottom;
          });
          const record = (row) => ({
            name: row?.dataset.name || '',
            grade: row?.dataset.grade || '',
            text: row?.querySelector('.material-identity strong')?.textContent || '',
          });
          return {
            client_width: element.clientWidth,
            client_height: element.clientHeight,
            scroll_width: element.scrollWidth,
            scroll_height: element.scrollHeight,
            horizontal_overflow: element.scrollWidth - element.clientWidth,
            vertical_overflow: element.scrollHeight - element.clientHeight,
            scroll_left: element.scrollLeft,
            scroll_top: element.scrollTop,
            viewport: {left: viewport.left, top: viewport.top, right: viewport.right, bottom: viewport.bottom},
            header: header ? {top: header.top, bottom: header.bottom} : null,
            footer: footer ? {top: footer.top, bottom: footer.bottom} : null,
            rows: {count: rows.length, first: record(rows[0]), last: record(rows.at(-1))},
            visible_row_count: visibleRows.length,
            visible_rows_fully_contained: visibleRows.every((row) => {
              const box = row.getBoundingClientRect();
              return box.top >= viewport.top - 0.5 && box.bottom <= viewport.bottom + 0.5;
            }),
            selected_row_visible: Boolean(selected && selected.getBoundingClientRect().top >= viewport.top && selected.getBoundingClientRect().bottom <= viewport.bottom),
            sticky_header_position: document.querySelector('.results-table th') ? getComputedStyle(document.querySelector('.results-table th')).position : '',
            vertical: rail('#results-scrollbar-y'),
            horizontal: rail('#results-scrollbar-x'),
            footer_range: document.querySelector('#results-range')?.textContent || '',
            next_page_visible: Boolean(document.querySelector('#results-next-page')?.checkVisibility()),
          };
        }"""
    )


def exercise_result_fixture(page: Page) -> dict[str, Any]:
    page.wait_for_timeout(80)
    initial = result_fixture_snapshot(page)
    if initial["rows"]["count"] != 50:
        raise AssertionError(f"normal result fixture must render 50 rows: {initial}")
    if (initial["rows"]["first"]["name"], initial["rows"]["first"]["grade"]) != RESULT_FIRST:
        raise AssertionError(f"normal result first row changed: {initial['rows']['first']}")
    if (initial["rows"]["last"]["name"], initial["rows"]["last"]["grade"]) != RESULT_LAST:
        raise AssertionError(f"normal result last row changed: {initial['rows']['last']}")
    if initial["horizontal_overflow"] > 0:
        raise AssertionError(f"normal result grid horizontally overflows: {initial}")
    if initial["sticky_header_position"] != "sticky":
        raise AssertionError("normal result header is not sticky")
    if initial["footer_range"] != RESULT_RANGE_TEXT or not initial["next_page_visible"]:
        raise AssertionError(f"normal result pagination is incomplete: {initial}")
    if not initial["visible_rows_fully_contained"]:
        raise AssertionError(f"normal result viewport cuts through a visible row: {initial}")
    if not initial["selected_row_visible"]:
        raise AssertionError("selected DP780 row is not visible at result origin")

    overflowing = initial["vertical_overflow"] > 0
    if not overflowing:
        if initial["vertical"]["visible"] or initial["horizontal"]["visible"]:
            raise AssertionError(f"normal result presents a fake rail without overflow: {initial}")
        return {
            "overflowing": False,
            "wheel_moved": False,
            "page_down_moved": False,
            "vertical_end_reached": True,
            "vertical_arrow_moved": False,
            "vertical_pointer_moved": False,
            "sticky_header_at_end": True,
            "footer_fixed_at_end": True,
            "rails_outside_text": True,
            "proportional_thumbs": False,
            "initial": initial,
            "at_end": initial,
        }

    vertical = initial["vertical"]
    if not vertical["visible"] or not vertical["track"] or not vertical["thumb"]:
        raise AssertionError(f"normal result overflow has no reserved vertical rail: {initial}")
    if vertical["aria_max"] <= 0 or vertical["aria_now"] != 0:
        raise AssertionError(f"normal result vertical rail ARIA range is not synchronized: {initial}")
    if vertical["track"]["background"] == vertical["thumb"]["background"]:
        raise AssertionError(f"normal result vertical rail lacks track/thumb contrast: {initial}")
    if vertical["track"]["left"] < initial["viewport"]["right"] - 0.5:
        raise AssertionError(f"normal result vertical rail covers cell text: {initial}")
    if vertical["thumb"]["height"] >= vertical["track"]["height"] or vertical["thumb"]["height"] < 36:
        raise AssertionError(f"normal result vertical thumb is not proportional: {initial}")

    page.locator("#results-scroll").evaluate("(element) => { element.scrollTop = 0; }")
    page.wait_for_timeout(20)
    before_wheel = result_fixture_snapshot(page)
    page.locator("#results-scroll").hover()
    page.mouse.wheel(0, 360)
    page.wait_for_timeout(30)
    after_wheel = result_fixture_snapshot(page)

    page.locator("#results-scroll").evaluate("(element) => { element.scrollTop = 0; }")
    page.wait_for_timeout(20)
    before_page = result_fixture_snapshot(page)
    page.locator("#results-scroll").focus()
    page.keyboard.press("PageDown")
    page.wait_for_timeout(30)
    after_page = result_fixture_snapshot(page)

    page.locator("#results-scrollbar-y").focus()
    page.keyboard.press("End")
    page.wait_for_timeout(30)
    at_end = result_fixture_snapshot(page)
    if at_end["vertical"]["aria_now"] != at_end["vertical_overflow"] or at_end["scroll_top"] < at_end["vertical_overflow"] - 1:
        raise AssertionError(f"normal result End did not reach the local scroll end: {at_end}")
    page.keyboard.press("Home")
    page.keyboard.press("ArrowDown")
    page.wait_for_timeout(30)
    after_arrow = result_fixture_snapshot(page)

    page.locator("#results-scroll").evaluate("(element) => { element.scrollTop = 0; }")
    page.wait_for_timeout(20)
    thumb_box = page.locator("#results-scrollbar-y .app-scrollbar-thumb").bounding_box()
    if thumb_box is None:
        raise AssertionError("normal result vertical thumb is missing before pointer exercise")
    start_x = thumb_box["x"] + thumb_box["width"] / 2
    start_y = thumb_box["y"] + thumb_box["height"] / 2
    page.mouse.move(start_x, start_y)
    page.mouse.down()
    page.mouse.move(start_x, start_y + 36, steps=4)
    page.mouse.up()
    page.wait_for_timeout(30)
    after_pointer = result_fixture_snapshot(page)

    footer_fixed = (
        at_end["footer"] is not None
        and initial["footer"] is not None
        and abs(at_end["footer"]["top"] - initial["footer"]["top"]) <= 0.6
    )
    sticky_at_end = (
        at_end["header"] is not None
        and at_end["header"]["bottom"] > at_end["viewport"]["top"]
        and at_end["header"]["top"] <= at_end["viewport"]["top"] + 1
    )
    page.locator("#results-scroll").evaluate("(element) => { element.scrollTop = 0; }")
    page.wait_for_timeout(30)
    restored = result_fixture_snapshot(page)
    if not restored["selected_row_visible"]:
        raise AssertionError("selected DP780 row is not visible after result scroll restoration")
    return {
        "overflowing": True,
        "wheel_moved": after_wheel["scroll_top"] > before_wheel["scroll_top"],
        "page_down_moved": after_page["scroll_top"] > before_page["scroll_top"],
        "vertical_end_reached": at_end["scroll_top"] >= at_end["vertical_overflow"] - 1 and at_end["vertical"]["aria_now"] == at_end["vertical_overflow"],
        "vertical_arrow_moved": after_arrow["scroll_top"] > 0,
        "vertical_pointer_moved": after_pointer["scroll_top"] > 0 and after_pointer["vertical"]["aria_now"] == after_pointer["scroll_top"],
        "sticky_header_at_end": sticky_at_end,
        "footer_fixed_at_end": footer_fixed,
        "rails_outside_text": True,
        "proportional_thumbs": True,
        "initial": initial,
        "at_end": at_end,
        "restored": restored,
    }


def splitter_snapshot(page: Page) -> dict[str, Any]:
    return page.evaluate(
        """() => {
          const region = (selector) => Math.round(
            document.querySelector(selector).getBoundingClientRect().width
          );
          const separator = (selector) => {
            const element = document.querySelector(selector);
            return {
              minimum: Number(element.getAttribute('aria-valuemin')),
              maximum: Number(element.getAttribute('aria-valuemax')),
              now: Number(element.getAttribute('aria-valuenow')),
            };
          };
          const treeScroller = document.querySelector('.tree-scroll');
          const treeContentRight = treeScroller.getBoundingClientRect().right;
          const treeKindRightEdges = [...treeScroller.querySelectorAll('.tree-kind')]
            .map((kind) => kind.getBoundingClientRect().right);
          return {
            widths: {
              navigator: region("[data-region='navigator']"),
              results: region("[data-region='results']"),
              context: region("[data-region='selected-context']"),
            },
            aria: {
              navigator: separator("[data-region='navigator-divider']"),
              context: separator("[data-region='context-divider']"),
            },
            selected_context_visible: document.querySelector(
              "[data-region='selected-context']"
            ).checkVisibility(),
            tree_scroller: {
              horizontal_overflow: treeScroller.scrollWidth - treeScroller.clientWidth,
              vertical_overflow: treeScroller.scrollHeight - treeScroller.clientHeight,
              content_right: treeContentRight,
              tree_kind_right_edges: treeKindRightEdges,
              all_tree_kind_right_edges_within_content:
                treeKindRightEdges.every((right) => right <= treeContentRight + 0.01),
              rails: {
                horizontal: !document.querySelector('#tree-scrollbar-x').hidden,
                vertical: !document.querySelector('#tree-scrollbar-y').hidden,
              },
            },
            overflow: {
              documentHorizontal:
                document.documentElement.scrollWidth - document.documentElement.clientWidth,
              documentVertical:
                document.documentElement.scrollHeight - document.documentElement.clientHeight,
              bodyHorizontal: document.body.scrollWidth - document.body.clientWidth,
              bodyVertical: document.body.scrollHeight - document.body.clientHeight,
            },
          };
        }"""
    )


def assert_splitter_snapshot(
    label: str,
    snapshot: dict[str, Any],
    expected: dict[str, list[int]],
) -> None:
    expected_widths = tuple(expected["widths"])
    expected_now = tuple(expected["aria_now"])
    expected_maximum = tuple(expected["aria_maximum"])
    widths = snapshot["widths"]
    actual_widths = (widths["navigator"], widths["results"], widths["context"])
    if actual_widths != expected_widths:
        raise AssertionError(f"{label} widths: expected {expected_widths}, got {actual_widths}")
    navigator_aria = snapshot["aria"]["navigator"]
    context_aria = snapshot["aria"]["context"]
    if (navigator_aria["now"], context_aria["now"]) != expected_now:
        raise AssertionError(
            f"{label} aria now: expected {expected_now}, got "
            f"{(navigator_aria['now'], context_aria['now'])}"
        )
    if (navigator_aria["maximum"], context_aria["maximum"]) != expected_maximum:
        raise AssertionError(
            f"{label} aria maximum: expected {expected_maximum}, got "
            f"{(navigator_aria['maximum'], context_aria['maximum'])}"
        )
    if (navigator_aria["minimum"], context_aria["minimum"]) != (200, 260):
        raise AssertionError(f"{label} aria minimum is not truthful")
    if navigator_aria["now"] != widths["navigator"] or context_aria["now"] != widths["context"]:
        raise AssertionError(f"{label} visible and ARIA pane widths are not synchronized")
    if widths["results"] < 720:
        raise AssertionError(f"{label} result region is below 720px")
    if not snapshot["selected_context_visible"]:
        raise AssertionError(f"{label} selected context is not visible")
    if any(value != 0 for value in snapshot["overflow"].values()):
        raise AssertionError(f"{label} has page overflow: {snapshot['overflow']}")
    tree_scroller = snapshot["tree_scroller"]
    expected_tree_overflow = expected.get("tree_horizontal_overflow", 0)
    if tree_scroller["horizontal_overflow"] != expected_tree_overflow:
        raise AssertionError(
            f"{label} tree scroller horizontal overflow: "
            f"expected {expected_tree_overflow}px, got {tree_scroller['horizontal_overflow']}px"
        )
    expected_tree_rail = expected.get("tree_horizontal_rail", expected_tree_overflow > 0)
    if tree_scroller["rails"]["horizontal"] != expected_tree_rail:
        raise AssertionError(f"{label} tree horizontal rail visibility is not truthful")
    if tree_scroller["rails"]["vertical"]:
        raise AssertionError(f"{label} tree vertical rail unexpectedly visible")
    if not tree_scroller["all_tree_kind_right_edges_within_content"]:
        raise AssertionError(f"{label} tree kind labels extend beyond the content edge")


def exercise_splitters(page: Page, config: dict[str, Any]) -> dict[str, Any]:
    navigator = page.locator("[data-region='navigator-divider']")
    context = page.locator("[data-region='context-divider']")
    evidence: dict[str, Any] = {}
    expectations = config["splitter_expectations"]

    evidence["default"] = splitter_snapshot(page)
    assert_splitter_snapshot("default", evidence["default"], expectations["default"])

    for step in config["splitter_steps"]:
        if step.get("reload"):
            page.reload(wait_until="load")
            page.evaluate("document.fonts.ready")
            inject_target_overrides(page, config)
        splitter = navigator if step["splitter"] == "navigator" else context
        splitter.focus()
        page.keyboard.press(step["key"])
        page.wait_for_timeout(60)
        label = step["label"]
        evidence[label] = splitter_snapshot(page)
        assert_splitter_snapshot(label, evidence[label], expectations[label])

    return evidence


def inject_target_overrides(page: Page, config: dict[str, Any]) -> None:
    if css_override := config.get("css_override"):
        page.add_style_tag(path=str(css_override))
    if javascript_override := config.get("javascript_override"):
        page.add_script_tag(path=str(javascript_override))


def capture_wide_evidence(browser: Any, config: dict[str, Any]) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    for viewport in config.get("wide_evidence", ()):
        context = browser.new_context(
            viewport={"width": viewport["width"], "height": viewport["height"]},
            device_scale_factor=viewport["device_scale_factor"],
        )
        page = context.new_page()
        console_errors: list[str] = []
        page_errors: list[str] = []
        page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
        page.on("pageerror", lambda error: page_errors.append(str(error)))
        page.goto(config["html"].as_uri(), wait_until="load")
        page.evaluate("document.fonts.ready")
        inject_target_overrides(page, config)
        page.wait_for_timeout(40)
        exercise_interactions(page)
        result_fixture = exercise_result_fixture(page)
        page.reload(wait_until="load")
        page.evaluate("document.fonts.ready")
        inject_target_overrides(page, config)
        page.wait_for_timeout(40)
        result_fixture = exercise_result_fixture(page)
        image = config["image"].with_name(f"{config['image'].stem}.wide-evidence-{viewport['width']}x{viewport['height']}.png")
        measurements_path = config["measurements"].with_name(
            f"{config['image'].stem}.wide-evidence-{viewport['width']}x{viewport['height']}.measurements.json"
        )
        page.screenshot(path=str(image), full_page=False)
        measurement = collect_measurements(page, config["target_id"], {**config, "viewport": viewport}, navigator_fixture=None, result_fixture=result_fixture)
        measurement["wide_evidence"] = True
        measurement["image"] = str(image.relative_to(ROOT)).replace("\\", "/")
        measurement["image_dimensions"] = {"width": viewport["width"], "height": viewport["height"]}
        measurement["image_sha256"] = hashlib.sha256(image.read_bytes()).hexdigest()
        measurement["console_errors"] = console_errors
        measurement["page_errors"] = page_errors
        measurements_path.write_text(json.dumps(measurement, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        if console_errors or page_errors:
            raise AssertionError(f"wide {viewport['width']} browser errors: console={console_errors}, page={page_errors}")
        evidence.append({"viewport": viewport, "image": str(image.relative_to(ROOT)).replace("\\", "/"), "measurements": str(measurements_path.relative_to(ROOT)).replace("\\", "/"), "image_sha256": measurement["image_sha256"]})
        context.close()
    return evidence


def validate_measurements(measurements: dict[str, Any], config: dict[str, Any]) -> None:
    regions = measurements["regions"]
    viewport = config["viewport"]
    assert_close(regions["application_bar"]["height"], 46, "application bar height")
    assert_close(regions["command_bar"]["height"], 38, "command bar height")
    assert_close(regions["search_band"]["height"], 40, "search band height")
    assert_close(regions["status_bar"]["height"], 24, "status bar height")
    assert_close(regions["workspace"]["x"], 8, "workspace left margin")
    assert_close(
        viewport["width"] - regions["workspace"]["x"] - regions["workspace"]["width"],
        8,
        "workspace right margin",
    )
    assert_close(regions["navigator"]["width"], config["navigator_width"], "navigator width")
    assert_close(regions["navigator_divider"]["width"], 5, "navigator divider hit width")
    if config["context_visible"]:
        if regions["selected_context"] is None or regions["context_divider"] is None:
            raise AssertionError("selected context is unexpectedly collapsed")
        assert_close(
            regions["selected_context"]["width"], config["context_width"], "selected context width"
        )
        assert_close(regions["context_divider"]["width"], 5, "context divider hit width")
    elif regions["selected_context"] is not None or regions["context_divider"] is not None:
        raise AssertionError("compact context must be represented as collapsed/null regions")
    if measurements["visible_splitter_count"] != config["expected_divider_count"]:
        raise AssertionError(
            "unexpected visible splitter count: "
            f"{measurements['visible_splitter_count']} (expected "
            f"{config['expected_divider_count']})"
        )
    for index, width in enumerate(measurements["divider_visual_widths"], start=1):
        assert_close(width, 1, f"divider {index} visual width")
    result_width = config["result_width"]
    if "exact" in result_width:
        assert_close(regions["results"]["width"], result_width["exact"], "result width")
    else:
        assert_between(
            regions["results"]["width"],
            result_width["minimum"],
            result_width["maximum"],
            "result width",
        )
    if regions["results"]["width"] < 720:
        raise AssertionError(f"result width below 720px: {regions['results']['width']}px")
    if (
        config["context_visible"]
        and regions["results"]["width"] <= regions["selected_context"]["width"]
    ):
        raise AssertionError("results are not wider than selected context")

    tree_density = measurements["row_density"]["tree"]
    result_density = measurements["row_density"]["results"]
    assert_between(tree_density["minimum"], 24, 26, "minimum tree row height")
    assert_between(tree_density["maximum"], 24, 26, "maximum tree row height")
    assert_between(result_density["minimum"], 32, 36, "minimum result row height")
    assert_between(result_density["maximum"], 32, 36, "maximum result row height")
    if result_density["count"] != 50:
        raise AssertionError(f"expected 50 result rows, got {result_density['count']}")
    if result_density["minimum"] != 36 or result_density["maximum"] != 36:
        raise AssertionError(f"normal result rows must remain fixed at 36px: {result_density}")
    if measurements.get("result_count") != RESULT_COUNT_TEXT:
        raise AssertionError(f"normal result count changed: {measurements.get('result_count')!r}")
    if measurements.get("result_range") != RESULT_RANGE_TEXT:
        raise AssertionError(f"normal result range footer changed: {measurements.get('result_range')!r}")
    result_scroller = measurements.get("result_scroller", {})
    result_rows = result_scroller.get("rows", {})
    if result_rows.get("count") != 50:
        raise AssertionError(f"normal result scroller row count changed: {result_rows}")
    if (result_rows.get("first", {}).get("name"), result_rows.get("first", {}).get("grade")) != RESULT_FIRST:
        raise AssertionError(f"normal first result identity changed: {result_rows.get('first')}")
    if (result_rows.get("last", {}).get("name"), result_rows.get("last", {}).get("grade")) != RESULT_LAST:
        raise AssertionError(f"normal last result identity changed: {result_rows.get('last')}")
    if result_scroller.get("horizontal_overflow", 0) != 0:
        raise AssertionError(f"normal result grid has horizontal overflow: {result_scroller}")
    if not result_scroller.get("visible_rows_fully_contained"):
        raise AssertionError("normal result viewport cuts through a visible row")
    result_fixture = measurements.get("result_fixture") or {}
    required_result_fixture = (
        "sticky_header_at_end",
        "footer_fixed_at_end",
        "rails_outside_text",
    )
    if result_fixture.get("overflowing") is None or not all(result_fixture.get(key) for key in required_result_fixture):
        raise AssertionError(f"normal result overflow fixture interaction evidence failed: {result_fixture}")
    if result_fixture.get("overflowing"):
        if not all(result_fixture.get(key) for key in ("wheel_moved", "page_down_moved", "vertical_end_reached", "vertical_arrow_moved", "vertical_pointer_moved")):
            raise AssertionError(f"normal result overflow interaction evidence failed: {result_fixture}")
        if not result_scroller.get("rails", {}).get("vertical", {}).get("visible"):
            raise AssertionError("normal result overflow is missing a visible vertical rail")
    elif result_scroller.get("rails", {}).get("vertical", {}).get("visible"):
        raise AssertionError("normal result without overflow presents a fake vertical rail")
    if measurements["table_headers"] != [
        "Compare",
        "Material / grade",
        "Family",
        "Description",
        "Status",
    ]:
        raise AssertionError(f"unexpected table headers: {measurements['table_headers']}")
    if measurements["table_header_position"] != "sticky":
        raise AssertionError("table headers are not sticky")
    if measurements["selected_result_rows"] != 1:
        raise AssertionError("normal state must have exactly one selected result row")
    if measurements["selected_tree_rows"] != 1:
        raise AssertionError("normal state must have exactly one selected tree row")
    if measurements["visible_selected_context"] != config["context_visible"]:
        raise AssertionError(
            "selected context visibility mismatch: "
            f"{measurements['visible_selected_context']} (expected "
            f"{config['context_visible']})"
        )
    expected_context_state = "visible" if config["context_visible"] else "collapsed"
    if measurements.get("context_state") != expected_context_state:
        raise AssertionError(
            f"selected context state must be {expected_context_state!r}, "
            f"got {measurements.get('context_state')!r}"
        )
    if measurements["primary_command_count"] != 1:
        raise AssertionError("normal task context must have one filled primary command")
    if measurements["nested_persistent_card_count"] != 0:
        raise AssertionError("nested persistent cards are present")
    tree_scroller = measurements["tree_scroller"]
    if tree_scroller["horizontal_overflow"] != 0 or tree_scroller.get("vertical_overflow", 0) != 0:
        raise AssertionError(
            "normal tree scroller unexpectedly overflows: "
            f"x={tree_scroller['horizontal_overflow']}px y={tree_scroller.get('vertical_overflow', 0)}px"
        )
    if not tree_scroller["all_tree_kind_right_edges_within_content"]:
        raise AssertionError("tree kind labels extend beyond the navigator content edge")
    if tree_scroller.get("rails", {}).get("vertical", {}).get("visible") or tree_scroller.get("rails", {}).get("horizontal", {}).get("visible"):
        raise AssertionError("normal short tree presents a fake application scrollbar")
    identities = tree_scroller.get("identities", [])
    if len(identities) != 7 or any(
        item.get("identity") != item.get("title")
        or item.get("glyph_kind") != item.get("kind")
        or item.get("glyph_title") != item.get("kind")
        or item.get("glyph_font_size") != "0px"
        or not item.get("accessible_name", "").startswith(f"{item.get('kind')}: ")
        for item in identities
    ):
        raise AssertionError(f"normal tree identity/glyph semantics changed: {identities}")
    fixture = measurements.get("navigator_fixture") or {}
    required_fixture = (
        "wheel_moved",
        "page_down_moved",
        "vertical_end_reached",
        "vertical_arrow_moved",
        "horizontal_end_reached",
        "horizontal_arrow_moved",
        "identity_reachable_at_horizontal_end",
        "vertical_pointer_moved",
        "horizontal_pointer_moved",
        "rails_outside_text",
        "proportional_thumbs",
    )
    if not all(fixture.get(key) for key in required_fixture):
        raise AssertionError(f"navigator overflow fixture interaction evidence failed: {fixture}")
    if config["context_visible"] and not all(measurements["context_content"].values()):
        raise AssertionError(
            "visible selected context is missing its summary or Open datasheet action"
        )
    if any(value != 0 for value in measurements["overflow"].values()):
        raise AssertionError(f"page-level overflow detected: {measurements['overflow']}")
    if not all(measurements["interactions"].values()):
        raise AssertionError(f"interaction exercise failed: {measurements['interactions']}")


def main() -> None:
    args = parse_args()
    target, html, image, measurements_path, config = resolve_paths(args)
    if not html.is_file():
        raise SystemExit(f"HTML does not exist: {html}")
    image.parent.mkdir(parents=True, exist_ok=True)
    measurements_path.parent.mkdir(parents=True, exist_ok=True)

    console_errors: list[str] = []
    page_errors: list[str] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        viewport = config["viewport"]
        context = browser.new_context(
            viewport={"width": viewport["width"], "height": viewport["height"]},
            device_scale_factor=viewport["device_scale_factor"],
        )
        page = context.new_page()
        page.on(
            "console",
            lambda message: console_errors.append(message.text)
            if message.type == "error"
            else None,
        )
        page.on("pageerror", lambda error: page_errors.append(str(error)))
        page.goto(html.as_uri(), wait_until="load")
        page.evaluate("document.fonts.ready")
        inject_target_overrides(page, config)
        splitter_evidence = None
        if config.get("splitter_steps"):
            splitter_evidence = exercise_splitters(page, config)
            page.reload(wait_until="load")
            page.evaluate("document.fonts.ready")
            inject_target_overrides(page, config)
        exercise_interactions(page)
        page.reload(wait_until="load")
        page.evaluate("document.fonts.ready")
        inject_target_overrides(page, config)
        page.wait_for_timeout(40)
        navigator_fixture = exercise_navigator_fixture(page)
        page.reload(wait_until="load")
        page.evaluate("document.fonts.ready")
        inject_target_overrides(page, config)
        page.wait_for_timeout(40)
        exercise_interactions(page)
        result_fixture = exercise_result_fixture(page)
        measurements = collect_measurements(page, target, config, splitter_evidence, navigator_fixture, result_fixture)
        validate_measurements(measurements, config)
        if console_errors:
            raise AssertionError(f"browser console errors: {console_errors}")
        if page_errors:
            raise AssertionError(f"uncaught page errors: {page_errors}")
        page.screenshot(path=str(image), full_page=False)
        wide_evidence = capture_wide_evidence(browser, {**config, "target_id": target}) if args.wide_evidence else []
        browser.close()

    measurements["image_sha256"] = hashlib.sha256(image.read_bytes()).hexdigest()
    measurements["console_errors"] = console_errors
    measurements["page_errors"] = page_errors
    measurements_path.write_text(
        json.dumps(measurements, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"PASS {target}")
    print(f"image: {image.relative_to(ROOT)}")
    print(f"measurements: {measurements_path.relative_to(ROOT)}")
    context_region = measurements["regions"]["selected_context"]
    context_width = context_region["width"] if context_region else "collapsed"
    print(
        "regions: "
        f"navigator={measurements['regions']['navigator']['width']}px "
        f"results={measurements['regions']['results']['width']}px "
        f"context={context_width}"
    )
    for entry in wide_evidence:
        print(f"wide {entry['viewport']['width']}x{entry['viewport']['height']}: {entry['image_sha256']}")


if __name__ == "__main__":
    main()

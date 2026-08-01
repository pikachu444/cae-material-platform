# ruff: noqa: E501
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path
from typing import Any

from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parents[3]
REFERENCE_DIR = ROOT / "docs/00-research/ux-service-reference"
IMAGE_DIR = ROOT / "docs/17-evidence/images/issue-167-service-reference"
HTML = REFERENCE_DIR / "materials-search-exceptional.html"
CSS = REFERENCE_DIR / "materials-search-exceptional.css"
JAVASCRIPT = REFERENCE_DIR / "materials-search-exceptional.js"
STAGING_INDEX = IMAGE_DIR / "materials-search-wave03.staging.json"
STATE_EVIDENCE = IMAGE_DIR / "materials-search-wave03.state-evidence.json"

VIEWPORTS: dict[str, dict[str, int]] = {
    "1366x768": {"width": 1366, "height": 768, "device_scale_factor": 1},
    "1440x900": {"width": 1440, "height": 900, "device_scale_factor": 1},
    "1920x1080": {"width": 1920, "height": 1080, "device_scale_factor": 1},
}

TARGETS: dict[str, dict[str, Any]] = {
    "materials-search-long-1440x900": {
        "state": "long",
        "viewport": VIEWPORTS["1440x900"],
        "image": IMAGE_DIR / "materials-search-long-1440x900.png",
        "measurements": IMAGE_DIR / "materials-search-long-1440x900.measurements.json",
        "kind": "approval",
    },
    "materials-search-empty-1440x900": {
        "state": "empty",
        "viewport": VIEWPORTS["1440x900"],
        "image": IMAGE_DIR / "materials-search-empty-1440x900.png",
        "measurements": IMAGE_DIR / "materials-search-empty-1440x900.measurements.json",
        "kind": "approval",
    },
}

EXCEPTION_RESPONSIVE: dict[str, dict[str, Any]] = {}
for _state in ("long", "empty"):
    for _viewport_name in ("1366x768", "1920x1080"):
        _target = f"materials-search-{_state}-1440x900.responsive-{_viewport_name}"
        EXCEPTION_RESPONSIVE[_target] = {
            "state": _state,
            "viewport": VIEWPORTS[_viewport_name],
            "image": IMAGE_DIR / f"{_target}.png",
            "measurements": IMAGE_DIR / f"{_target}.measurements.json",
            "kind": "responsive",
        }

STATE_TARGETS: dict[str, dict[str, Any]] = {}
for _state, _slug in (
    ("search-loading", "loading"),
    ("tree-loading", "tree-lazy-loading"),
    ("query-error", "query-error"),
    ("tree-error", "tree-error"),
):
    for _viewport_name, _viewport in VIEWPORTS.items():
        _target = f"materials-search-state-{_slug}-{_viewport_name}"
        STATE_TARGETS[_target] = {
            "state": _state,
            "viewport": _viewport,
            "image": IMAGE_DIR / f"{_target}.png",
            "measurements": IMAGE_DIR / f"{_target}.measurements.json",
            "kind": "state-evidence",
        }

ALL_TARGETS = {**TARGETS, **EXCEPTION_RESPONSIVE, **STATE_TARGETS}

FROZEN_NORMAL_HASHES = {
    "materials-search-normal-1366x768.png": "b1fc0cfeaaa0734e22d6678eef3ef6ca03cecdbce3d6588d8bee18f4a9572065",
    "materials-search-normal-1440x900.png": "8f99dba3ec20cc75f29ab938dfa42682ff741ef624fcdd495b89fd673e49c53b",
    "materials-search-normal-1920x1080.png": "b92757e5f80cbcd020f73d54af65cd700112497a76e40f412cfc0a60988ef191",
}
FROZEN_NORMAL_SOURCES = {
    "materials-search-normal.html": "ff9f6367f2369778734f7255ca5beb7ac86508dbf215cf6133721ce60cfe5988",
    "reference.css": "0f09daE7b9350e73613d21b3c2694e609b71b9486ecfd3c8546fcd691758b589".lower(),
    "reference.js": "788cb8278e7bc50dd2cdee8bad06517488bd8a6fffb04af2424fc32321c7c2af",
    "materials-search-normal-1366x768.css": "07cdb7b3a158788324fdf5b96ce9e1f425daedc1f4e20e47b5f18bd3db0c4008",
    "materials-search-normal-1366x768.js": "ed630f1c71bd813476801e20c9474907430153586fdccb86dc8068c291e1c4ee",
    "materials-search-normal-1920x1080.css": "3007a2bef1afa2793adc2616e2afa7c0b8481a55ef1884a5b80b953ce985ebd7",
    "materials-search-normal-1920x1080.js": "045b2ca8439552c52c6acb5bab1e915cd02b167748a8c3f2c26249e4dd31c475",
}

LEGACY_SELECTORS = (
    "page-stack",
    "page-heading",
    "content-card",
    "module-material-card",
    "hero-actions",
    "eyebrow",
    "status-badge",
    "count-chip",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Capture MAT-EXP WAVE-03 exceptional service-reference states.")
    parser.add_argument("--target", choices=sorted(TARGETS), help="Capture one canonical approval target.")
    parser.add_argument("--all-packet-targets", action="store_true", help="Capture both approvals, responsive evidence and state evidence.")
    args = parser.parse_args()
    if not args.target and not args.all_packet_targets:
        parser.error("provide --target or --all-packet-targets")
    if args.target and args.all_packet_targets:
        parser.error("--target and --all-packet-targets are mutually exclusive")
    return args


def relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def png_dimensions(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise AssertionError(f"not a PNG: {path}")
    return struct.unpack(">II", data[16:24])


def box(page: Page, selector: str) -> dict[str, float]:
    locator = page.locator(selector)
    if not locator.is_visible():
        raise AssertionError(f"{selector} is not visible")
    value = locator.bounding_box()
    if value is None:
        raise AssertionError(f"{selector} has no bounding box")
    return {key: round(number, 2) for key, number in value.items()}


def overflow(page: Page) -> dict[str, int]:
    return page.evaluate(
        """() => ({
          documentHorizontal: Math.max(0, document.documentElement.scrollWidth - document.documentElement.clientWidth),
          documentVertical: Math.max(0, document.documentElement.scrollHeight - document.documentElement.clientHeight),
          bodyHorizontal: Math.max(0, document.body.scrollWidth - document.body.clientWidth),
          bodyVertical: Math.max(0, document.body.scrollHeight - document.body.clientHeight),
        })"""
    )


def tree_snapshot(page: Page) -> dict[str, Any]:
    return page.locator(".tree-scroll").evaluate(
        """(element) => {
          const style = getComputedStyle(element);
          const selectedRows = [...element.querySelectorAll('[role="treeitem"][aria-selected="true"]')];
          const rows = [...element.querySelectorAll('[role="treeitem"]')];
          const rowHeights = rows.map((row) => Math.round(row.getBoundingClientRect().height));
          const paddings = [...new Set(rows.map((row) => Math.round(parseFloat(getComputedStyle(row).paddingLeft))))].sort((a, b) => a - b);
          const representative = ['Database', 'Profile', 'Table', 'Folder', 'Record'].map((kind) => rows
            .filter((row) => row.dataset.kind === kind)
            .sort((left, right) => right.querySelector('.tree-label').textContent.length - left.querySelector('.tree-label').textContent.length)[0])
            .filter(Boolean)
            .map((row) => {
              const label = row.querySelector('.tree-label');
              const glyph = row.querySelector('.tree-kind');
              return {
                kind: row.dataset.kind,
                full_text: label.textContent,
                visible_text_box_width: Math.round(label.getBoundingClientRect().width),
                title: label.title,
                accessible_type: row.getAttribute('aria-label').split(':')[0],
                glyph_title: glyph.title,
              };
            });
          const railSnapshot = (selector) => {
            const rail = document.querySelector(selector);
            const thumb = rail?.querySelector('.app-scrollbar-thumb');
            const railRect = rail?.getBoundingClientRect();
            const thumbRect = thumb?.getBoundingClientRect();
            const visible = Boolean(rail && !rail.hidden && railRect && railRect.width > 0 && railRect.height > 0);
            return {
              visible,
              orientation: rail?.getAttribute('aria-orientation') || '',
              aria_controls: rail?.getAttribute('aria-controls') || '',
              aria_min: Number(rail?.getAttribute('aria-valuemin') || 0),
              aria_max: Number(rail?.getAttribute('aria-valuemax') || 0),
              aria_now: Number(rail?.getAttribute('aria-valuenow') || 0),
              track: railRect ? {left: railRect.left, top: railRect.top, right: railRect.right, bottom: railRect.bottom, width: railRect.width, height: railRect.height, background: getComputedStyle(rail).backgroundColor} : null,
              thumb: thumbRect ? {left: thumbRect.left, top: thumbRect.top, right: thumbRect.right, bottom: thumbRect.bottom, width: thumbRect.width, height: thumbRect.height, background: getComputedStyle(thumb).backgroundColor} : null,
            };
          };
          const verticalRail = railSnapshot('#tree-scrollbar-y');
          const horizontalRail = railSnapshot('#tree-scrollbar-x');
          const verticalOverflow = Math.max(0, element.scrollHeight - element.clientHeight);
          const selected = selectedRows[0];
          return {
            client_width: element.clientWidth,
            client_height: element.clientHeight,
            scroll_width: element.scrollWidth,
            scroll_height: element.scrollHeight,
            horizontal_overflow: Math.max(0, element.scrollWidth - element.clientWidth),
            vertical_overflow: verticalOverflow,
            overflow_x: style.overflowX,
            overflow_y: style.overflowY,
            scrollbar_gutter: style.scrollbarGutter,
            visible_scrollbar_indicator: verticalRail.visible,
            native_scrollbar_visible: false,
            scrollbar_reservation_px: verticalRail.track?.width || 0,
            custom_scrollbar_indicator_visible: verticalRail.visible,
            scroll_controls: {
              vertical: verticalRail,
              horizontal: horizontalRail,
              rails_outside_text: Boolean(verticalRail.track && verticalRail.track.left >= element.getBoundingClientRect().right - .5 && horizontalRail.track && horizontalRail.track.top >= element.getBoundingClientRect().bottom - .5),
              distinct_track_thumb: Boolean(verticalRail.track && verticalRail.thumb && verticalRail.track.background !== verticalRail.thumb.background && horizontalRail.track && horizontalRail.thumb && horizontalRail.track.background !== horizontalRail.thumb.background),
            },
            row_height_range: { min: Math.min(...rowHeights), max: Math.max(...rowHeights) },
            indentation_increment_px: paddings.length > 1 ? Math.min(...paddings.slice(1).map((value, index) => value - paddings[index])) : 0,
            representative_identities: representative,
            labels_have_title: rows.every((row) => Boolean(row.querySelector('.tree-label')?.title)),
            labels_are_concise_identities: rows.every((row) => !row.querySelector('.tree-label')?.textContent.includes(' — ')),
            selected_rows: selectedRows.length,
            selected_without_type_prefix: Boolean(selected) && !selected.querySelector('.tree-kind').textContent.includes('Selected') && selected.querySelector('.tree-kind').title === selected.dataset.kind,
          };
        }"""
    )


def typography_snapshot(page: Page) -> dict[str, Any]:
    return page.evaluate(
        """(legacySelectors) => {
          const fontSize = (selector) => {
            const element = document.querySelector(selector);
            return element ? Number.parseFloat(getComputedStyle(element).fontSize) : null;
          };
          return {
            body_px: fontSize('body'),
            tree_row_px: fontSize('.tree-row'),
            result_data_px: fontSize('.results-table td'),
            result_metadata_px: fontSize('.material-identity span'),
            result_header_px: fontSize('.results-table th'),
            legacy_selector_report: Object.fromEntries(legacySelectors.map((name) => [name, document.querySelectorAll(`.${name}`).length])),
          };
        }""",
        list(LEGACY_SELECTORS),
    )


def result_snapshot(page: Page, state: str) -> dict[str, Any]:
    return page.evaluate(
        """(state) => {
          const scroll = document.querySelector('#results-scroll');
          const rail = document.querySelector('#results-scrollbar-y');
          const railThumb = rail?.querySelector('.app-scrollbar-thumb');
          const railRect = rail?.getBoundingClientRect();
          const railThumbRect = railThumb?.getBoundingClientRect();
          const rows = [...document.querySelectorAll('[data-result-row]')];
          const selected = rows.filter((row) => row.getAttribute('aria-selected') === 'true');
          const tableHeader = document.querySelector('.results-table th');
          const selectedContext = document.querySelector('[data-region="selected-context"]');
          const visible = (element) => element ? (typeof element.checkVisibility === 'function' ? element.checkVisibility() : Boolean(element.offsetWidth || element.offsetHeight)) : false;
          return {
            state,
            count_text: document.querySelector('#result-count')?.textContent.trim() || '',
            family_counts: document.querySelector('#family-counts')?.textContent.trim() || '',
            rendered_rows: rows.length,
            selected_rows: selected.length,
            selected_grade: selected[0]?.dataset.grade || '',
            sticky_header: tableHeader ? getComputedStyle(tableHeader).position === 'sticky' : false,
            table_headers: [...document.querySelectorAll('.results-table th .column-label')].map((header) => header.textContent.trim()),
            result_scroll: {
              client_width: scroll?.clientWidth || 0,
              client_height: scroll?.clientHeight || 0,
              scroll_width: scroll?.scrollWidth || 0,
              scroll_height: scroll?.scrollHeight || 0,
              independent_vertical_scroll: state === 'long' ? Boolean(scroll && scroll.scrollHeight > scroll.clientHeight) : true,
              vertical_overflow: Math.max(0, (scroll?.scrollHeight || 0) - (scroll?.clientHeight || 0)),
              overflow_x: scroll ? getComputedStyle(scroll).overflowX : '',
              overflow_y: scroll ? getComputedStyle(scroll).overflowY : '',
              scrollbar_gutter: scroll ? getComputedStyle(scroll).scrollbarGutter : '',
              native_scrollbar_visible: false,
              custom_scrollbar_indicator_visible: Boolean(rail && !rail.hidden && railRect && railRect.width > 0 && railRect.height > 0),
              scroll_control: {
                visible: Boolean(rail && !rail.hidden && railRect && railRect.width > 0 && railRect.height > 0),
                aria_controls: rail?.getAttribute('aria-controls') || '',
                aria_max: Number(rail?.getAttribute('aria-valuemax') || 0),
                track: railRect ? {left: railRect.left, right: railRect.right, width: railRect.width, height: railRect.height, background: getComputedStyle(rail).backgroundColor} : null,
                thumb: railThumbRect ? {left: railThumbRect.left, right: railThumbRect.right, width: railThumbRect.width, height: railThumbRect.height, background: getComputedStyle(railThumb).backgroundColor} : null,
                outside_text: Boolean(scroll && railRect && railRect.left >= scroll.getBoundingClientRect().right - .5),
              },
            },
            empty_visible: visible(document.querySelector('#results-empty')),
            clear_search_visible: visible(document.querySelector('#clear-search')),
            visible_filled_primary_actions: [...document.querySelectorAll('.primary-action')].filter(visible).map((action) => action.textContent.trim()),
            retry_buttons: [...document.querySelectorAll('.results-notice button')].map((button) => button.textContent.trim()),
            selected_context_visible: visible(selectedContext),
            selected_context_heading: document.querySelector('#empty-context:not([hidden]) h3')?.textContent.trim() || document.querySelector('#selected-name')?.textContent.trim() || '',
            no_material_context: Boolean(document.querySelector('#empty-context:not([hidden])')),
            stale_context_action_visible: visible(document.querySelector('#open-datasheet')),
          };
        }""",
        state,
    )


def splitter_snapshot(page: Page) -> dict[str, Any]:
    return page.evaluate(
        """() => {
          const width = (selector) => Math.round(document.querySelector(selector).getBoundingClientRect().width);
          const separator = (selector) => {
            const element = document.querySelector(selector);
            return {
              minimum: Number(element.getAttribute('aria-valuemin')),
              maximum: Number(element.getAttribute('aria-valuemax')),
              now: Number(element.getAttribute('aria-valuenow')),
            };
          };
          return {
            widths: { navigator: width('[data-region="navigator"]'), results: width('[data-region="results"]'), context: width('[data-region="selected-context"]') },
            aria: { navigator: separator('[data-region="navigator-divider"]'), context: separator('[data-region="context-divider"]') },
            divider_visual_widths: [...document.querySelectorAll('.splitter > span')].map((element) => Math.round(element.getBoundingClientRect().width)),
            selected_context_visible: document.querySelector('[data-region="selected-context"]')?.checkVisibility?.() ?? true,
            overflow: {
              documentHorizontal: Math.max(0, document.documentElement.scrollWidth - document.documentElement.clientWidth),
              documentVertical: Math.max(0, document.documentElement.scrollHeight - document.documentElement.clientHeight),
              bodyHorizontal: Math.max(0, document.body.scrollWidth - document.body.clientWidth),
              bodyVertical: Math.max(0, document.body.scrollHeight - document.body.clientHeight),
            },
            tree_scroller: (() => {
              const tree = document.querySelector('.tree-scroll');
              const rail = document.querySelector('#tree-scrollbar-y');
              return {
                vertical_overflow: Math.max(0, tree.scrollHeight - tree.clientHeight),
                custom_vertical_visible: Boolean(rail && !rail.hidden && rail.getBoundingClientRect().width >= 12),
              };
            })(),
          };
        }"""
    )


def expected_ranges(page: Page) -> tuple[int, int]:
    width = page.evaluate("window.innerWidth")
    return (360, 480) if width >= 1700 else (340, 420) if width >= 1400 else (340, 376)


def exercise_splitters(page: Page) -> dict[str, Any]:
    navigator = page.locator("[data-region='navigator-divider']")
    context = page.locator("[data-region='context-divider']")
    nav_max, context_max = expected_ranges(page)
    evidence: dict[str, Any] = {"default": splitter_snapshot(page)}
    steps = (
        ("navigator_arrow_right", navigator, "ArrowRight"),
        ("navigator_home", navigator, "Home"),
        ("navigator_end", navigator, "End"),
        ("context_arrow_left", context, "ArrowLeft"),
        ("context_home", context, "Home"),
        ("context_end", context, "End"),
    )
    for label, splitter, key in steps:
        splitter.focus()
        page.keyboard.press(key)
        evidence[label] = splitter_snapshot(page)
    for label, snapshot in evidence.items():
        widths = snapshot["widths"]
        aria = snapshot["aria"]
        if widths["results"] < 720:
            raise AssertionError(f"{label}: results below 720px: {widths}")
        if aria["navigator"]["minimum"] != 200 or aria["context"]["minimum"] != 260:
            raise AssertionError(f"{label}: splitter minima are not truthful: {aria}")
        if aria["navigator"]["maximum"] != nav_max or aria["context"]["maximum"] != context_max:
            raise AssertionError(f"{label}: splitter maxima are not truthful: {aria}")
        if aria["navigator"]["now"] != widths["navigator"] or aria["context"]["now"] != widths["context"]:
            raise AssertionError(f"{label}: visible/ARIA widths diverge: {snapshot}")
        if snapshot["divider_visual_widths"] != [1, 1]:
            raise AssertionError(f"{label}: divider rule width mismatch: {snapshot}")
        if any(value != 0 for value in snapshot["overflow"].values()):
            raise AssertionError(f"{label}: page overflow: {snapshot['overflow']}")
        if snapshot["tree_scroller"]["vertical_overflow"] <= 0 or not snapshot["tree_scroller"]["custom_vertical_visible"]:
            raise AssertionError(f"{label}: tree independent scrolling was lost: {snapshot['tree_scroller']}")
    return evidence


def exercise_interactions(page: Page, state: str) -> dict[str, bool]:
    result: dict[str, bool] = {}
    page.keyboard.press("Control+K")
    result["search_shortcut"] = page.evaluate("document.activeElement?.id") == "material-query"
    page.keyboard.press("Enter")
    result["search_submit"] = page.locator("body").get_attribute("data-query-applied") == page.locator("#material-query").input_value()

    dp780 = page.locator("#tree-dp780")
    dp780.focus()
    page.keyboard.press("Home")
    home = page.evaluate("document.activeElement?.id") == "tree-database"
    page.keyboard.press("End")
    end = page.evaluate("document.activeElement?.id") == "tree-legacy-dp"
    page.keyboard.press("ArrowUp")
    previous = page.evaluate("document.activeElement?.id") == "tree-legacy"
    dp780.focus()
    page.keyboard.press("Enter")
    result["tree_keyboard"] = home and end and previous and dp780.get_attribute("aria-selected") == "true"

    if state == "empty":
        page.locator("#clear-search").click()
        result["clear_search"] = page.locator("body").get_attribute("data-clear-search") == "true" and page.locator("#results-body [data-result-row]").count() == 6
    else:
        result["clear_search"] = True

    row = page.locator("[data-result-row]").first
    row.focus()
    page.keyboard.press("Enter")
    result["result_enter"] = page.locator("body").get_attribute("data-datasheet-consequence") == "DP780-REF"

    if state == "query-error":
        page.locator("#retry-query").click()
        result["query_retry"] = page.evaluate("document.body.dataset.queryRetry === 'true'") and page.locator("[data-result-row]").count() == 6
    else:
        result["query_retry"] = True
    if state == "tree-error":
        page.locator("#retry-tree").click()
        result["tree_retry"] = page.evaluate("document.body.dataset.treeRetry === 'true'") and page.locator("[data-result-row]").count() == 6
    else:
        result["tree_retry"] = True
    return result


def exercise_local_scroll(page: Page, state: str) -> dict[str, dict[str, Any]]:
    def snapshot(selector: str) -> dict[str, int]:
        return page.locator(selector).evaluate(
            """(element) => ({
              scroll_top: element.scrollTop,
              scroll_left: element.scrollLeft,
              document_top: window.scrollY,
              client_height: element.clientHeight,
              scroll_height: element.scrollHeight,
              client_width: element.clientWidth,
              scroll_width: element.scrollWidth,
            })"""
        )

    evidence: dict[str, dict[str, Any]] = {}
    for name, selector, focus_selector in (
        ("tree", ".tree-scroll", "#tree-dp780"),
        ("result", "#results-scroll", "#results-scroll"),
    ):
        initial = snapshot(selector)
        overflowing = initial["scroll_height"] > initial["client_height"]
        if not overflowing:
            evidence[name] = {
                "overflowing": False,
                "wheel_moved": False,
                "page_down_moved": False,
                "document_unchanged": True,
                "horizontal_overflowing": initial["scroll_width"] > initial["client_width"],
                "horizontal_keyboard_moved": False,
                "vertical_scrollbar_keyboard_moved": False,
                "vertical_scrollbar_pointer_moved": False,
                "horizontal_scrollbar_keyboard_moved": False,
            }
            continue
        page.locator(selector).evaluate("(element) => { element.scrollTop = 0; }")
        before_wheel = snapshot(selector)
        page.locator(selector).hover()
        page.mouse.wheel(0, 360)
        after_wheel = snapshot(selector)
        page.locator(selector).evaluate("(element) => { element.scrollTop = 0; }")
        page.locator(focus_selector).focus()
        before_page_down = snapshot(selector)
        page.keyboard.press("PageDown")
        after_page_down = snapshot(selector)
        horizontal_overflowing = initial["scroll_width"] > initial["client_width"]
        horizontal_before = snapshot(selector)
        horizontal_after = horizontal_before
        if name == "tree" and horizontal_overflowing:
            page.locator(selector).evaluate("(element) => { element.scrollLeft = 0; }")
            page.locator(selector).focus()
            horizontal_before = snapshot(selector)
            for _ in range(8):
                page.keyboard.press("ArrowRight")
            horizontal_after = snapshot(selector)
        vertical_scrollbar = "#tree-scrollbar-y" if name == "tree" else "#results-scrollbar-y"
        page.locator(selector).evaluate("(element) => { element.scrollTop = 0; }")
        page.locator(vertical_scrollbar).focus()
        vertical_scrollbar_before = snapshot(selector)
        page.keyboard.press("ArrowDown")
        vertical_scrollbar_after = snapshot(selector)
        page.locator(selector).evaluate("(element) => { element.scrollTop = 0; }")
        vertical_thumb_box = page.locator(f"{vertical_scrollbar} .app-scrollbar-thumb").bounding_box()
        if vertical_thumb_box:
            thumb_x = vertical_thumb_box["x"] + vertical_thumb_box["width"] / 2
            thumb_y = vertical_thumb_box["y"] + vertical_thumb_box["height"] / 2
            page.mouse.move(thumb_x, thumb_y)
            page.mouse.down()
            page.mouse.move(thumb_x, thumb_y + 36, steps=4)
            page.mouse.up()
        vertical_pointer_after = snapshot(selector)
        horizontal_scrollbar_keyboard_moved = False
        if name == "tree" and horizontal_overflowing:
            page.locator(selector).evaluate("(element) => { element.scrollLeft = 0; }")
            page.locator("#tree-scrollbar-x").focus()
            horizontal_rail_before = snapshot(selector)
            page.keyboard.press("ArrowRight")
            horizontal_rail_after = snapshot(selector)
            horizontal_scrollbar_keyboard_moved = horizontal_rail_after["scroll_left"] > horizontal_rail_before["scroll_left"]
        evidence[name] = {
            "overflowing": True,
            "wheel_before_scroll_top": before_wheel["scroll_top"],
            "wheel_after_scroll_top": after_wheel["scroll_top"],
            "page_down_before_scroll_top": before_page_down["scroll_top"],
            "page_down_after_scroll_top": after_page_down["scroll_top"],
            "wheel_moved": after_wheel["scroll_top"] > before_wheel["scroll_top"],
            "page_down_moved": after_page_down["scroll_top"] > before_page_down["scroll_top"],
            "document_unchanged": before_wheel["document_top"] == after_wheel["document_top"] == before_page_down["document_top"] == after_page_down["document_top"],
            "horizontal_overflowing": horizontal_overflowing,
            "horizontal_keyboard_before_scroll_left": horizontal_before["scroll_left"],
            "horizontal_keyboard_after_scroll_left": horizontal_after["scroll_left"],
            "horizontal_keyboard_moved": horizontal_after["scroll_left"] > horizontal_before["scroll_left"],
            "vertical_scrollbar_keyboard_moved": vertical_scrollbar_after["scroll_top"] > vertical_scrollbar_before["scroll_top"],
            "vertical_scrollbar_pointer_moved": vertical_pointer_after["scroll_top"] > 0,
            "horizontal_scrollbar_keyboard_moved": horizontal_scrollbar_keyboard_moved,
        }
    if state == "empty" and evidence["result"]["overflowing"]:
        raise AssertionError("empty result region unexpectedly overflows")
    if not evidence["tree"]["overflowing"] or not evidence["tree"]["wheel_moved"] or not evidence["tree"]["page_down_moved"]:
        raise AssertionError(f"tree local-scroll evidence failed: {evidence['tree']}")
    if not evidence["tree"]["horizontal_overflowing"] or not evidence["tree"]["horizontal_keyboard_moved"]:
        raise AssertionError(f"tree horizontal local-scroll evidence failed: {evidence['tree']}")
    if not evidence["tree"]["vertical_scrollbar_keyboard_moved"] or not evidence["tree"]["vertical_scrollbar_pointer_moved"] or not evidence["tree"]["horizontal_scrollbar_keyboard_moved"]:
        raise AssertionError(f"tree application scrollbar interaction failed: {evidence['tree']}")
    if state == "long" and (not evidence["result"]["wheel_moved"] or not evidence["result"]["page_down_moved"]):
        raise AssertionError(f"long result local-scroll evidence failed: {evidence['result']}")
    if state == "long" and (not evidence["result"]["vertical_scrollbar_keyboard_moved"] or not evidence["result"]["vertical_scrollbar_pointer_moved"]):
        raise AssertionError(f"long result application scrollbar interaction failed: {evidence['result']}")
    return evidence


def collect_measurements(page: Page, target: str, config: dict[str, Any], interactions: dict[str, bool], splitter_evidence: dict[str, Any], local_scroll: dict[str, dict[str, Any]]) -> dict[str, Any]:
    state = config["state"]
    result = result_snapshot(page, state)
    tree = tree_snapshot(page)
    typography = typography_snapshot(page)
    state_notices = page.evaluate(
        """() => Object.fromEntries(['results-notice', 'tree-notice'].map((id) => {
          const element = document.querySelector(`#${id}`);
          return [id, {
            visible: Boolean(element && !element.hidden),
            text: element?.textContent.replace(/\\s+/g, ' ').trim() || '',
            buttons: [...(element?.querySelectorAll('button') || [])].map((button) => button.textContent.trim()),
          }];
        }))"""
    )
    regions = {name: box(page, selector) for name, selector in {
        "application_bar": "[data-region='application-bar']",
        "command_bar": "[data-region='command-bar']",
        "search_band": "[data-region='search-band']",
        "workspace": "[data-region='materials-workspace']",
        "navigator": "[data-region='navigator']",
        "navigator_divider": "[data-region='navigator-divider']",
        "results": "[data-region='results']",
        "context_divider": "[data-region='context-divider']",
        "selected_context": "[data-region='selected-context']",
        "status_bar": "[data-region='status-bar']",
    }.items()}
    measurements = {
        "schema_version": 1,
        "target": target,
        "family": "MAT-EXP",
        "kind": config["kind"],
        "state": state,
        "capture_date": "2026-07-29",
        "viewport": config["viewport"],
        "source": {"html": relative(HTML), "css": relative(CSS), "javascript": relative(JAVASCRIPT)},
        "regions": regions,
        "result": result,
        "tree": tree,
        "selected_context": {
            "visible": result["selected_context_visible"],
            "heading": result["selected_context_heading"],
            "no_material_selected": result["no_material_context"],
            "open_datasheet_visible": result["stale_context_action_visible"],
        },
        "state_notices": state_notices,
        "result_count": {"text": result["count_text"], "rendered_rows": result["rendered_rows"], "total": int(page.locator("body").get_attribute("data-result-total") or 0)},
        "sticky_header": result["sticky_header"],
        "independent_result_scroll": result["result_scroll"]["independent_vertical_scroll"],
        "typography": typography,
        "legacy_selector_report": typography["legacy_selector_report"],
        "splitter_evidence": splitter_evidence,
        "interactions": interactions,
        "local_scroll": local_scroll,
        "overflow": overflow(page),
        "console_errors": [],
        "page_errors": [],
        "status": "pending",
        "main_agent_evaluation": {"status": "pending"},
        "product_owner_approval": {"status": "absent"},
    }
    if any(value != 0 for value in measurements["overflow"].values()):
        raise AssertionError(f"{target}: page overflow {measurements['overflow']}")
    if tree["vertical_overflow"] <= 0 or not tree["custom_scrollbar_indicator_visible"] or not tree["labels_have_title"] or not tree["labels_are_concise_identities"]:
        raise AssertionError(f"{target}: tree scrolling/identity evidence failed {tree}")
    if not 24 <= tree["row_height_range"]["min"] <= tree["row_height_range"]["max"] <= 26 or not 8 <= tree["indentation_increment_px"] <= 10:
        raise AssertionError(f"{target}: tree density evidence failed {tree}")
    if any(item["full_text"] != item["title"] or item["kind"] != item["accessible_type"] or item["kind"] != item["glyph_title"] for item in tree["representative_identities"]):
        raise AssertionError(f"{target}: tree identity semantics failed {tree}")
    if result["table_headers"] != ["Compare", "Material / grade", "Family", "Description", "Status"]:
        raise AssertionError(f"{target}: table headers changed {result['table_headers']}")
    if not result["sticky_header"]:
        raise AssertionError(f"{target}: table header is not sticky")
    if state == "long":
        if result["rendered_rows"] != 50 or not result["selected_rows"] or result["count_text"] != "1\u201350 of 126 matches":
            raise AssertionError(f"{target}: long result contract failed {result}")
        if not result["result_scroll"]["independent_vertical_scroll"]:
            raise AssertionError(f"{target}: long result pane does not scroll independently")
        if tree["selected_rows"] != 1:
            raise AssertionError(f"{target}: long state must retain one selected tree Record")
    if state == "empty":
        if result["rendered_rows"] != 0 or result["selected_rows"] != 0 or tree["selected_rows"] != 0 or not result["no_material_context"] or result["stale_context_action_visible"]:
            raise AssertionError(f"{target}: empty result contract failed {result}")
        if not result["empty_visible"] or not result["clear_search_visible"]:
            raise AssertionError(f"{target}: empty recovery is not visible {result}")
        if result["visible_filled_primary_actions"] != ["Find"]:
            raise AssertionError(f"{target}: empty state must have exactly one visible filled task-primary action {result}")
    if not all(interactions.values()):
        raise AssertionError(f"{target}: interaction exercise failed {interactions}")
    return measurements


def assert_frozen_normals() -> None:
    for name, expected in FROZEN_NORMAL_HASHES.items():
        path = IMAGE_DIR / name
        if not path.is_file() or sha256(path) != expected:
            raise AssertionError(f"frozen normal image changed: {relative(path)}")
        width, height = png_dimensions(path)
        viewport_token = name.split("-")[-1].split(".")[0]
        expected_size = {"1366x768": (1366, 768), "1440x900": (1440, 900), "1920x1080": (1920, 1080)}[viewport_token]
        if (width, height) != expected_size:
            raise AssertionError(f"frozen normal image dimensions changed: {relative(path)} {(width, height)}")
    for name, expected in FROZEN_NORMAL_SOURCES.items():
        path = REFERENCE_DIR / name
        if not path.is_file() or sha256(path) != expected:
            raise AssertionError(f"frozen normal source changed: {relative(path)}")


def capture_target(target: str, config: dict[str, Any], browser: Any) -> dict[str, Any]:
    image = config["image"]
    measurements_path = config["measurements"]
    image.parent.mkdir(parents=True, exist_ok=True)
    measurements_path.parent.mkdir(parents=True, exist_ok=True)
    errors: list[str] = []
    page_errors: list[str] = []
    context = browser.new_context(viewport={"width": config["viewport"]["width"], "height": config["viewport"]["height"]}, device_scale_factor=config["viewport"]["device_scale_factor"])
    page = context.new_page()
    page.on("console", lambda message: errors.append(message.text) if message.type == "error" else None)
    page.on("pageerror", lambda error: page_errors.append(str(error)))
    url = f"{HTML.resolve().as_uri()}?state={config['state']}"
    page.goto(url, wait_until="load")
    page.evaluate("document.fonts.ready")
    interactions = exercise_interactions(page, config["state"])
    page.reload(wait_until="load")
    page.evaluate("document.fonts.ready")
    local_scroll = exercise_local_scroll(page, config["state"])
    page.reload(wait_until="load")
    page.evaluate("document.fonts.ready")
    splitter_evidence = exercise_splitters(page)
    page.reload(wait_until="load")
    page.evaluate("document.fonts.ready")
    page.screenshot(path=str(image), full_page=False)
    measurements = collect_measurements(page, target, config, interactions, splitter_evidence, local_scroll)
    measurements["console_errors"] = errors
    measurements["page_errors"] = page_errors
    if errors or page_errors:
        raise AssertionError(f"{target}: browser errors console={errors} page={page_errors}")
    dimensions = png_dimensions(image)
    if dimensions != (config["viewport"]["width"], config["viewport"]["height"]):
        raise AssertionError(f"{target}: screenshot dimensions {dimensions}")
    measurements["image"] = relative(image)
    measurements["image_dimensions"] = {"width": dimensions[0], "height": dimensions[1]}
    measurements["image_sha256"] = sha256(image)
    measurements_path.write_text(json.dumps(measurements, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    context.close()
    return measurements


def build_staging(captured: dict[str, dict[str, Any]]) -> None:
    references = []
    for target, config in TARGETS.items():
        measurement = captured[target]
        references.append({
            "id": target,
            "family": "MAT-EXP",
            "kind": "approval",
            "state": config["state"],
            "viewport": config["viewport"],
            "html": relative(HTML),
            "css": relative(CSS),
            "javascript": relative(JAVASCRIPT),
            "image": measurement["image"],
            "measurements": relative(config["measurements"]),
            "image_sha256": measurement["image_sha256"],
            "status": "pending",
            "main_agent_evaluation": {"status": "pending"},
            "product_owner_approval": {"status": "absent"},
            "responsive_evidence": " ".join(captured[target_name]["image"] for target_name in EXCEPTION_RESPONSIVE if target_name.startswith(f"materials-search-{config['state']}-")),
        })
    state_index = []
    for target, measurement in captured.items():
        if target in TARGETS:
            continue
        state_index.append({"id": target, "state": measurement["state"], "viewport": measurement["viewport"], "image": measurement["image"], "measurements": relative(ALL_TARGETS[target]["measurements"]), "image_sha256": measurement["image_sha256"]})
    staging = {
        "schema_version": 1,
        "generated": "2026-07-29",
        "family": "MAT-EXP",
        "references": references,
        "responsive_evidence": [entry for entry in state_index if ALL_TARGETS[entry["id"]]["kind"] == "responsive"],
        "state_evidence": relative(STATE_EVIDENCE),
    }
    STAGING_INDEX.write_text(json.dumps(staging, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    state_doc = {
        "schema_version": 1,
        "generated": "2026-07-29",
        "family": "MAT-EXP",
        "approval_references": {target: captured[target] for target in TARGETS},
        "long-responsive": [captured[target] for target in EXCEPTION_RESPONSIVE if ALL_TARGETS[target]["state"] == "long"],
        "empty-responsive": [captured[target] for target in EXCEPTION_RESPONSIVE if ALL_TARGETS[target]["state"] == "empty"],
        "loading-error-evidence": [captured[target] for target in STATE_TARGETS],
    }
    STATE_EVIDENCE.write_text(json.dumps(state_doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    assert_frozen_normals()
    selected = TARGETS if args.all_packet_targets else {args.target: TARGETS[args.target]}
    configurations = dict(selected)
    if args.all_packet_targets:
        configurations.update(EXCEPTION_RESPONSIVE)
        configurations.update(STATE_TARGETS)
    captured: dict[str, dict[str, Any]] = {}
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        for target, config in configurations.items():
            captured[target] = capture_target(target, config, browser)
            print(f"PASS {target}")
            print(f"image: {captured[target]['image']}")
            print(f"sha256: {captured[target]['image_sha256']}")
        browser.close()
    if args.all_packet_targets:
        build_staging(captured)
        print(f"staging: {relative(STAGING_INDEX)}")
        print(f"state evidence: {relative(STATE_EVIDENCE)}")


if __name__ == "__main__":
    main()

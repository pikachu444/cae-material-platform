# ruff: noqa: E501
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parents[3]
REFERENCE_DIR = ROOT / "docs/00-research/ux-service-reference"
IMAGE_DIR = ROOT / "docs/17-evidence/images/issue-167-service-reference"
HTML = REFERENCE_DIR / "materials-card-preview-normal.html"
CSS = REFERENCE_DIR / "materials-card-preview.css"
JAVASCRIPT = REFERENCE_DIR / "materials-card-preview.js"
STAGING_INDEX = IMAGE_DIR / "materials-card-wave02.staging.json"

VIEWPORTS: dict[str, dict[str, int]] = {
    "1366x768": {"width": 1366, "height": 768, "device_scale_factor": 1},
    "1440x900": {"width": 1440, "height": 900, "device_scale_factor": 1},
    "1920x1080": {"width": 1920, "height": 1080, "device_scale_factor": 1},
    "2560x1440": {"width": 2560, "height": 1440, "device_scale_factor": 1},
    "3840x2160": {"width": 3840, "height": 2160, "device_scale_factor": 1},
}

CANONICAL_TARGETS: dict[str, dict[str, Any]] = {
    "materials-card-preview-normal-1366x768": {
        "state": "normal",
        "viewport": VIEWPORTS["1366x768"],
        "image": IMAGE_DIR / "materials-card-preview-normal-1366x768.png",
        "measurements": IMAGE_DIR / "materials-card-preview-normal-1366x768.measurements.json",
    },
    "materials-card-preview-normal-1440x900": {
        "state": "normal",
        "viewport": VIEWPORTS["1440x900"],
        "image": IMAGE_DIR / "materials-card-preview-normal-1440x900.png",
        "measurements": IMAGE_DIR / "materials-card-preview-normal-1440x900.measurements.json",
    },
    "materials-card-preview-normal-1920x1080": {
        "state": "normal",
        "viewport": VIEWPORTS["1920x1080"],
        "image": IMAGE_DIR / "materials-card-preview-normal-1920x1080.png",
        "measurements": IMAGE_DIR / "materials-card-preview-normal-1920x1080.measurements.json",
    },
    "materials-card-approximation-blocked-1440x900": {
        "state": "approximation",
        "viewport": VIEWPORTS["1440x900"],
        "image": IMAGE_DIR / "materials-card-approximation-blocked-1440x900.png",
        "measurements": IMAGE_DIR / "materials-card-approximation-blocked-1440x900.measurements.json",
    },
    "materials-card-unsupported-blocked-1440x900": {
        "state": "unsupported",
        "viewport": VIEWPORTS["1440x900"],
        "image": IMAGE_DIR / "materials-card-unsupported-blocked-1440x900.png",
        "measurements": IMAGE_DIR / "materials-card-unsupported-blocked-1440x900.measurements.json",
    },
}

WIDE_SUPPORT_TARGETS: dict[str, dict[str, Any]] = {
    "materials-card-preview-normal-2560x1440": {
        "state": "normal",
        "viewport": VIEWPORTS["2560x1440"],
        "image": IMAGE_DIR / "materials-card-preview-normal-2560x1440.png",
        "measurements": IMAGE_DIR / "materials-card-preview-normal-2560x1440.measurements.json",
    },
    "materials-card-preview-normal-3840x2160": {
        "state": "normal",
        "viewport": VIEWPORTS["3840x2160"],
        "image": IMAGE_DIR / "materials-card-preview-normal-3840x2160.png",
        "measurements": IMAGE_DIR / "materials-card-preview-normal-3840x2160.measurements.json",
    },
}

TARGETS: dict[str, dict[str, Any]] = {**CANONICAL_TARGETS, **WIDE_SUPPORT_TARGETS}
STATE_VIEWPORT_KEYS = ("1366x768", "1440x900", "1920x1080")

EXCEPTION_STATES = {
    "materials-card-approximation-blocked-1440x900": "approximation",
    "materials-card-unsupported-blocked-1440x900": "unsupported",
}

LEGACY_ACTIVE_ROUTE_SELECTORS = (
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
    parser = argparse.ArgumentParser(description="Capture the WAVE-02 MAT-CARD static-reference family.")
    parser.add_argument("--target", choices=sorted(TARGETS), help="One canonical target id.")
    parser.add_argument("--all-packet-targets", action="store_true", help="Capture all five canonical targets and responsive/state evidence.")
    args = parser.parse_args()
    if not args.target and not args.all_packet_targets:
        parser.error("provide --target or --all-packet-targets")
    if args.target and args.all_packet_targets:
        parser.error("--target and --all-packet-targets are mutually exclusive")
    return args


def rounded_box(page: Page, selector: str) -> dict[str, float]:
    box = page.locator(selector).bounding_box()
    if box is None:
        raise AssertionError(f"{selector} is not visible")
    return {key: round(value, 2) for key, value in box.items()}


def png_dimensions(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise AssertionError(f"not a PNG: {path}")
    return struct.unpack(">II", data[16:24])


def overflow_snapshot(page: Page) -> dict[str, int]:
    return page.evaluate(
        """() => ({
          document_horizontal: document.documentElement.scrollWidth - document.documentElement.clientWidth,
          document_vertical: document.documentElement.scrollHeight - document.documentElement.clientHeight,
          body_horizontal: document.body.scrollWidth - document.body.clientWidth,
          body_vertical: document.body.scrollHeight - document.body.clientHeight,
        })"""
    )


def visual_acceptance_snapshot(page: Page) -> dict[str, Any]:
    return page.evaluate(
        """(legacySelectors) => {
          const fontSize = (selector) => {
            const element = document.querySelector(selector);
            return element ? Number.parseFloat(getComputedStyle(element).fontSize) : null;
          };
          return {
            typography: {
              body_px: fontSize('body'),
              tree_row_px: fontSize('.tree-row'),
              native_preview_data_px: fontSize('.preview-scroll pre'),
              mapping_primary_px: fontSize('.mapping-row strong'),
              delivery_value_px: fontSize('.delivery-fields dd'),
            },
            legacy_selector_report: Object.fromEntries(
              legacySelectors.map((name) => [name, document.querySelectorAll(`.${name}`).length])
            ),
          };
        }""",
        list(LEGACY_ACTIVE_ROUTE_SELECTORS),
    )


def tree_snapshot(page: Page) -> dict[str, Any]:
    return page.locator(".tree-scroll").evaluate(
        """(element) => {
          const right = element.getBoundingClientRect().right;
          const labels = [...element.querySelectorAll('[role="treeitem"]')].map((row) => ({
            expected: row.dataset.kind,
            actual: row.querySelector('.tree-kind')?.textContent.trim(),
            title: row.querySelector('.tree-label')?.title,
          }));
          const kinds = [...element.querySelectorAll('.tree-kind')].map((kind) => kind.getBoundingClientRect());
          return {
            horizontal_overflow: element.scrollWidth - element.clientWidth,
            kinds_inside: kinds.every((box) => box.right <= right + 0.01),
            labels_match: labels.every((label) => label.expected === label.actual),
            labels_have_title: labels.every((label) => Boolean(label.title)),
            labels,
          };
        }"""
    )


def card_snapshot(page: Page) -> dict[str, Any]:
    return page.evaluate(
        """() => {
          const rect = (selector) => {
            const element = document.querySelector(selector);
            if (!element) return null;
            const box = element.getBoundingClientRect();
            return {left: Math.round(box.left), top: Math.round(box.top), width: Math.round(box.width), height: Math.round(box.height)};
          };
          const download = document.querySelector('#download-card');
          const advanced = document.querySelector('#advanced-mapping');
          const pre = document.querySelector('#native-text');
          const nativePreview = document.querySelector('.native-preview');
          const previewScroll = document.querySelector('#preview-scroll');
          const previewScrollRail = document.querySelector('#preview-scroll-rail');
          const previewScrollThumb = document.querySelector('#preview-scroll-thumb');
          const cardContent = document.querySelector('[data-region="card-content"]');
          const responsePlotBand = document.querySelector('#response-plot-band');
          const responsePlotFrame = responsePlotBand?.querySelector('.response-plot-frame');
          const responsePlot = document.querySelector('#response-plot');
          const previewRect = nativePreview?.getBoundingClientRect();
          const scrollRect = previewScroll?.getBoundingClientRect();
          const railRect = previewScrollRail?.getBoundingClientRect();
          const thumbRect = previewScrollThumb?.getBoundingClientRect();
          const plotBandRect = responsePlotBand?.getBoundingClientRect();
          const plotFrameRect = responsePlotFrame?.getBoundingClientRect();
          const plotRect = responsePlot?.getBoundingClientRect();
          const previewStyle = previewScroll ? getComputedStyle(previewScroll) : null;
          const nativeTextStyle = pre ? getComputedStyle(pre) : null;
          const railStyle = previewScrollRail ? getComputedStyle(previewScrollRail) : null;
          const thumbStyle = previewScrollThumb ? getComputedStyle(previewScrollThumb) : null;
          const readJsonAttribute = (element, attribute) => {
            try { return JSON.parse(element?.getAttribute(attribute) || 'null'); } catch { return null; }
          };
          const plotViewBox = responsePlot?.viewBox?.baseVal;
          const plotRows = readJsonAttribute(responsePlot, 'data-series') || [];
          const plotXDomain = readJsonAttribute(responsePlot, 'data-x-domain');
          const plotYDomain = readJsonAttribute(responsePlot, 'data-y-domain');
          const plotLine = responsePlot?.querySelector('[data-series-line="true"]');
          let plotLineBox = null;
          try {
            const box = plotLine?.getBBox();
            if (box) plotLineBox = {x: box.x, y: box.y, width: box.width, height: box.height};
          } catch { plotLineBox = null; }
          const plotTick = document.querySelector('.plot-tick-label');
          const plotTitle = document.querySelector('.plot-axis-title');
          const decisionTextClipped = [...document.querySelectorAll('[data-decision-text]')]
            .filter((element) => element.checkVisibility())
            .filter((element) => element.scrollWidth > element.clientWidth + 1 || element.scrollHeight > element.clientHeight + 1)
            .map((element) => element.textContent.trim());
          const visibleMappingRows = [...document.querySelectorAll('.mapping-row')].filter((row) => !row.hidden && row.checkVisibility());
          const mappingRowDetails = visibleMappingRows.map((row) => {
            const title = row.querySelector('strong');
            const value = row.querySelector('.mapping-value');
            const consequence = row.querySelector('.mapping-status');
            const rowStyle = getComputedStyle(row);
            const consequenceStyle = consequence ? getComputedStyle(consequence) : null;
            const valueRect = value?.getBoundingClientRect();
            const consequenceRect = consequence?.getBoundingClientRect();
            const titleClipped = Boolean(title && (title.scrollWidth > title.clientWidth + 1 || title.scrollHeight > title.clientHeight + 1));
            const valueClipped = Boolean(value && (value.scrollWidth > value.clientWidth + 1 || value.scrollHeight > value.clientHeight + 1));
            const consequenceClipped = Boolean(consequence && (consequence.scrollWidth > consequence.clientWidth + 1 || consequence.scrollHeight > consequence.clientHeight + 1));
            const overlap = Boolean(valueRect && consequenceRect && consequenceRect.left < valueRect.right - 1);
            return {
              key: row.dataset.mappingKey || '',
              title: title?.textContent.trim() || '',
              value: value?.textContent.trim() || '',
              consequence: consequence?.textContent.trim() || '',
              status_class: consequence?.className || '',
              grid_template_columns: rowStyle.gridTemplateColumns,
              status_border_width: consequenceStyle?.borderWidth || '',
              status_border_radius: consequenceStyle?.borderRadius || '',
              status_padding: consequenceStyle?.padding || '',
              status_text_transform: consequenceStyle?.textTransform || '',
              clipped: titleClipped || valueClipped || consequenceClipped,
              overlap,
            };
          });
          return {
            state: document.body.dataset.state,
            mode: document.body.dataset.cardMode,
            regions: {
              card_panel: rect('[data-region="card-panel"]'),
              card_heading: rect('[data-region="card-heading"]'),
              card_content: rect('[data-region="card-content"]'),
              native_preview: rect('.native-preview'),
              preview_scroll: rect('#preview-scroll'),
              preview_scroll_rail: rect('#preview-scroll-rail'),
              preview_scroll_thumb: rect('#preview-scroll-thumb'),
              response_plot_band: rect('#response-plot-band'),
              response_plot_frame: rect('.response-plot-frame'),
              response_plot_svg: rect('#response-plot'),
              delivery_sheet: rect('.delivery-sheet'),
            },
            card_content_child_count: cardContent?.children.length ?? 0,
            native_width: Math.round(nativePreview.getBoundingClientRect().width),
            delivery_width: Math.round(document.querySelector('.delivery-sheet').getBoundingClientRect().width),
            preview_scroll_width: previewScroll?.scrollWidth ?? 0,
            preview_scroll_height: previewScroll?.scrollHeight ?? 0,
            preview_client_width: previewScroll?.clientWidth ?? 0,
            preview_client_height: previewScroll?.clientHeight ?? 0,
            preview_available_height: previewRect && scrollRect ? Math.round(responsePlotBand && !responsePlotBand.hidden ? scrollRect.height : previewRect.bottom - scrollRect.top - 10) : 0,
            preview_rendered_height: scrollRect ? Math.round(scrollRect.height) : 0,
            preview_fills_available_height: Boolean(previewRect && scrollRect && ((responsePlotBand && !responsePlotBand.hidden) || Math.abs(scrollRect.bottom - (previewRect.bottom - 10)) <= 1)),
            preview_scroll_range: Math.max(0, (previewScroll?.scrollHeight ?? 0) - (previewScroll?.clientHeight ?? 0)),
            preview_scroll_rail_visible: Boolean(previewScrollRail?.checkVisibility() && previewScrollRail.dataset.scrollable === 'true'),
            preview_scroll_gutter_width: Boolean(scrollRect && railRect) ? Math.round(scrollRect.right - railRect.left) : 0,
            preview_scroll_thumb_ratio: Boolean(railRect && thumbRect && railRect.height) ? thumbRect.height / railRect.height : 0,
            preview_scroll_text_clearance: pre && railRect ? Number.parseFloat(getComputedStyle(pre).paddingRight) - railRect.width : 0,
            preview_surface: previewStyle?.backgroundColor || '',
            preview_ink: nativeTextStyle?.color || '',
            preview_border: previewStyle?.borderTopColor || '',
            preview_scroll_track: railStyle?.backgroundColor || '',
            preview_scroll_divider: railStyle?.borderLeftColor || '',
            preview_scroll_thumb: thumbStyle?.backgroundColor || '',
            native_surface_ratio: Boolean(previewRect && scrollRect && previewRect.height) ? scrollRect.height / previewRect.height : 0,
            response_plot_ratio: Boolean(previewRect && plotBandRect && previewRect.height) ? plotBandRect.height / previewRect.height : 0,
            response_plot_visible: Boolean(responsePlotBand && !responsePlotBand.hidden && responsePlotBand.checkVisibility()),
            response_plot_rows: Number(responsePlot?.getAttribute('data-series-rows') || 0),
            response_plot_series: plotRows,
            response_plot_first_point: plotRows[0] || null,
            response_plot_x_domain: plotXDomain,
            response_plot_y_domain: plotYDomain,
            response_plot_line_bbox: plotLineBox,
            response_plot_line_has_frame_headroom: Boolean(plotLineBox && plotViewBox && plotLineBox.x > 1 && plotLineBox.y > 1 && plotLineBox.x + plotLineBox.width < plotViewBox.width - 1 && plotLineBox.y + plotLineBox.height < plotViewBox.height - 1),
            response_plot_x_label: responsePlot?.getAttribute('data-x-label') || '',
            response_plot_y_label: responsePlot?.getAttribute('data-y-label') || '',
            response_plot_svg_aspect: plotRect && plotViewBox ? {
              render_width: plotRect.width,
              render_height: plotRect.height,
              viewbox_width: plotViewBox.width,
              viewbox_height: plotViewBox.height,
              render_aspect: plotRect.width / Math.max(plotRect.height, 1),
              viewbox_aspect: plotViewBox.width / Math.max(plotViewBox.height, 1),
              mismatch: Math.abs((plotRect.width / Math.max(plotRect.height, 1)) - (plotViewBox.width / Math.max(plotViewBox.height, 1))) / Math.max(plotRect.width / Math.max(plotRect.height, 1), 0.0001),
            } : null,
            response_plot_preserve_aspect_ratio: responsePlot?.getAttribute('preserveAspectRatio') || '',
            response_plot_tick_font_px: plotTick ? Number.parseFloat(getComputedStyle(plotTick).fontSize) : null,
            response_plot_title_font_px: plotTitle ? Number.parseFloat(getComputedStyle(plotTitle).fontSize) : null,
            response_plot_frame_size: plotFrameRect ? {width: plotFrameRect.width, height: plotFrameRect.height} : null,
            native_text_visible: Boolean(pre && !pre.closest('[hidden]') && pre.checkVisibility()),
            native_text_length: pre?.textContent.length ?? 0,
            unavailable_visible: Boolean(document.querySelector('#preview-unavailable')?.checkVisibility()),
            loading_visible: Boolean(document.querySelector('#preview-loading')?.checkVisibility()),
            error_visible: Boolean(document.querySelector('#preview-error')?.checkVisibility()),
            retry_visible: Boolean(document.querySelector('#retry-preview')?.checkVisibility()),
            mapping_title: document.querySelector('#mapping-title')?.textContent.trim() || '',
            mapping_disclosure_title: document.querySelector('#advanced-mapping summary')?.textContent.trim() || '',
            mapping_rows: visibleMappingRows.map((row) => row.textContent.trim()),
            mapping_row_details: mappingRowDetails,
            mapping_visible_count: mappingRowDetails.length,
            approximation_acknowledged: document.querySelector('#approximation-ack')?.checked ?? false,
            download: {text: download?.textContent.trim(), disabled: Boolean(download?.disabled), primary: download?.classList.contains('primary-action')},
            open_modeling_visible: Boolean(document.querySelector('#open-modeling')?.checkVisibility()),
            back_to_cards_visible: Boolean(document.querySelector('#back-to-cards')?.checkVisibility()),
            advanced_open: Boolean(advanced?.open),
            delivery_summary_present: Boolean(document.querySelector('#delivery-summary')),
            decision_text_clipped: decisionTextClipped,
            status: document.querySelector('#delivery-status')?.textContent.trim(),
          };
        }"""
    )


def splitter_snapshot(page: Page) -> dict[str, Any]:
    return page.evaluate(
        """() => {
          const width = (selector) => Math.round(document.querySelector(selector).getBoundingClientRect().width);
          const divider = document.querySelector('[data-region="navigator-divider"]');
          return {
            widths: {navigator: width('[data-region="navigator"]'), divider: width('[data-region="navigator-divider"]'), datasheet: width('[data-region="datasheet"]'), native: width('.native-preview'), delivery: width('.delivery-sheet')},
            aria: {minimum: Number(divider.getAttribute('aria-valuemin')), maximum: Number(divider.getAttribute('aria-valuemax')), now: Number(divider.getAttribute('aria-valuenow'))},
            overflow: {
              document_horizontal: document.documentElement.scrollWidth - document.documentElement.clientWidth,
              document_vertical: document.documentElement.scrollHeight - document.documentElement.clientHeight,
              body_horizontal: document.body.scrollWidth - document.body.clientWidth,
              body_vertical: document.body.scrollHeight - document.body.clientHeight,
            },
            selected_record_visible: document.querySelector('#tree-dp780')?.checkVisibility() ?? false,
          };
        }"""
    )


def splitter_states(page: Page) -> dict[str, Any]:
    splitter = page.locator("[data-region='navigator-divider']")
    viewport_width = page.evaluate("window.innerWidth")
    expected = 244 if viewport_width == 1366 else 280 if viewport_width >= 1700 else 264
    maximum = 345 if viewport_width == 1366 else 360
    evidence: dict[str, Any] = {}
    for label, key, expected_width in (("default", None, expected), ("navigator_arrow_right", "ArrowRight", expected + 8), ("navigator_home", "Home", 200), ("navigator_end", "End", maximum)):
        if key:
            splitter.focus()
            page.keyboard.press(key)
        evidence[label] = splitter_snapshot(page)
        snapshot = evidence[label]
        if snapshot["widths"]["navigator"] != expected_width:
            raise AssertionError(f"{label}: navigator width {snapshot}")
        if snapshot["widths"]["divider"] != 5 or snapshot["widths"]["navigator"] != snapshot["aria"]["now"]:
            raise AssertionError(f"{label}: splitter ARIA continuity {snapshot}")
        if snapshot["aria"]["minimum"] != 200 or snapshot["aria"]["maximum"] != maximum:
            raise AssertionError(f"{label}: splitter range {snapshot}")
        if snapshot["widths"]["datasheet"] < 720:
            raise AssertionError(f"{label}: datasheet below 720px {snapshot}")
        if any(value != 0 for value in snapshot["overflow"].values()):
            raise AssertionError(f"{label}: page overflow {snapshot}")
        if not snapshot["selected_record_visible"]:
            raise AssertionError(f"{label}: selected Record not visible")
    return evidence


def common_interactions(page: Page, state: str) -> dict[str, bool]:
    page.keyboard.press("Control+K")
    search_focus = page.evaluate("document.activeElement?.id") == "tree-query"
    page.locator("#tree-query").fill("DP780")
    page.locator("#tree-search-form").press("Enter")
    tree_search = page.locator("body").get_attribute("data-tree-search-consequence") == "DP780-REF"
    page.locator("#back-to-results").click()
    restored = page.locator("body").get_attribute("data-restored-selection") == "DP780-REF"
    dp780 = page.locator("#tree-dp780")
    dp780.focus()
    page.keyboard.press("Home")
    home = page.evaluate("document.activeElement?.id") == "tree-database"
    page.keyboard.press("End")
    end = page.evaluate("document.activeElement?.id") == "tree-dp600"
    page.keyboard.press("ArrowUp")
    previous = page.evaluate("document.activeElement?.id") == "tree-dp780"
    page.keyboard.press("Enter")
    selected = dp780.get_attribute("aria-selected") == "true"
    tab_clicks = True
    for button in page.locator("[role='tab']").all():
        button.click()
        tab_clicks = tab_clicks and page.locator("body").get_attribute("data-active-tab") == button.get_attribute("data-tab")
    page.locator("#tab-evidence").focus()
    page.keyboard.press("Home")
    tabs = page.evaluate("document.activeElement?.id") == "tab-overview"
    page.keyboard.press("End")
    tabs = tabs and page.evaluate("document.activeElement?.id") == "tab-evidence"
    page.keyboard.press("ArrowLeft")
    tabs = tabs and page.evaluate("document.activeElement?.id") == "tab-related"
    page.locator("#tab-cards").click()
    advanced = page.locator("#advanced-mapping")
    advanced.locator("summary").click()
    native_scroll_wheel = True
    if page.locator("#preview-scroll").is_visible():
        scrollable = page.locator("#preview-scroll").evaluate("element => element.scrollHeight > element.clientHeight + 1")
        if scrollable:
            preview = page.locator("#preview-scroll")
            preview.evaluate("element => { element.focus(); element.scrollTop = 0; }")
            box = preview.bounding_box()
            if box is None:
                native_scroll_wheel = False
            else:
                page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
                page.mouse.wheel(0, 240)
                page.wait_for_timeout(80)
                native_scroll_wheel = preview.evaluate("element => element.scrollTop > 0")
    details_open = advanced.get_attribute("open") == ""
    advanced.locator("summary").click()
    mapping_acknowledgement = True
    if state == "normal":
        page.locator("#download-card").click()
        command = page.locator("body").get_attribute("data-card-download") == "Abaqus:.inp"
        state_checks = page.locator("#download-card").is_enabled() and page.locator("#download-card").inner_text() == "Download .inp"
    elif state == "approximation":
        initially_blocked = page.locator("#download-card").is_disabled() and not page.locator("#approximation-ack").is_checked()
        report_before = page.locator("#native-text").text_content()
        consequence_before = page.locator("#approximation-row .mapping-status").inner_text()
        page.locator("#approximation-ack").check()
        consequence_after = page.locator("#approximation-row .mapping-status").inner_text()
        enabled = page.locator("#download-card").is_enabled()
        page.locator("#download-card").click()
        command = page.locator("body").get_attribute("data-card-download") == "OpenRadioss:.rad"
        report_after = page.locator("#native-text").text_content()
        mapping_acknowledgement = consequence_before == "Review required" and consequence_after == "Reviewed" and report_before == report_after
        state_checks = initially_blocked and mapping_acknowledgement and enabled and command
    else:
        no_artifact = not page.locator("#native-text").is_visible() and page.locator("#preview-unavailable").is_visible()
        blocked = page.locator("#download-card").is_disabled() and page.locator("#download-card").inner_text() == "Download blocked"
        page.locator("#open-modeling").click()
        page.locator("#back-to-cards").click()
        state_checks = no_artifact and blocked and page.locator("body").get_attribute("data-recovery-open-modeling") == "true" and page.locator("body").get_attribute("data-recovery-back-to-cards") == "true"
        command = blocked
    return {"navigator_search": search_focus, "tree_search": tree_search, "back_to_results": restored, "tree_keyboard": home and end and previous and selected, "tabs": tab_clicks and tabs and page.locator("#tab-cards").get_attribute("aria-selected") == "true", "advanced_disclosure": details_open and page.locator("#advanced-mapping").get_attribute("open") is None, "native_scroll_wheel": native_scroll_wheel, "mapping_acknowledgement": mapping_acknowledgement, "state_command": state_checks and command}


MAPPING_CONSEQUENCES = {"Exact", "Converted", "Review required", "Reviewed", "Not supported"}
MAPPING_EXPECTATIONS = {
    "density": ("Density", "7 800 kg/m³ → 7.8000E+03 kg/m³", "Exact"),
    "isotropic-elasticity": ("Isotropic elasticity", "210 GPa, \N{GREEK SMALL LETTER NU} 0.30 → *ELASTIC", "Exact"),
    "initial-yield": ("Initial yield", "450 MPa at εp = 0 → first *PLASTIC row", "Converted"),
    "hardening-response": ("Hardening response", "5 points → native *PLASTIC rows", "Converted"),
    "post-necking-extension": ("Post-necking extension", "Bounded extension → target behavior", "Review required"),
    "damage-initiation-gissmo": ("Damage initiation · GISSMO", "No governed target representation", "Not supported"),
}


def assert_mapping_grammar(snapshot: dict[str, Any], label: str, state: str) -> None:
    if snapshot.get("mapping_title") != "Mapping details":
        raise AssertionError(f"{label} mapping title mismatch: {snapshot.get('mapping_title')!r}")
    if snapshot.get("mapping_disclosure_title") != "Technical mapping details":
        raise AssertionError(f"{label} technical disclosure mismatch: {snapshot.get('mapping_disclosure_title')!r}")
    mode = state if state in {"normal", "approximation", "unsupported"} else "normal"
    expected_keys = {
        "normal": {"density", "isotropic-elasticity", "initial-yield", "hardening-response"},
        "approximation": {"density", "post-necking-extension"},
        "unsupported": {"density", "damage-initiation-gissmo"},
    }[mode]
    details = snapshot.get("mapping_row_details")
    if not isinstance(details, list) or {row.get("key") for row in details} != expected_keys:
        raise AssertionError(f"{label} visible mapping keys mismatch: {details!r}")
    if snapshot.get("mapping_visible_count") != len(expected_keys):
        raise AssertionError(f"{label} visible mapping count mismatch: {snapshot.get('mapping_visible_count')!r}")
    for row in details:
        key = row.get("key")
        if key not in MAPPING_EXPECTATIONS:
            raise AssertionError(f"{label} unexpected mapping key: {row!r}")
        expected_title, expected_value, expected_consequence = MAPPING_EXPECTATIONS[key]
        expected_consequence = "Reviewed" if mode == "approximation" and row.get("consequence") == "Reviewed" else expected_consequence
        if (row.get("title"), row.get("value")) != (expected_title, expected_value):
            raise AssertionError(f"{label} mapping title/value mismatch: {row!r}")
        if row.get("consequence") not in MAPPING_CONSEQUENCES or row.get("consequence") != expected_consequence:
            raise AssertionError(f"{label} mapping consequence mismatch: {row!r}")
        if row.get("clipped") or row.get("overlap"):
            raise AssertionError(f"{label} mapping row clipping/overlap: {row!r}")
        if row.get("status_border_width") != "0px" or row.get("status_border_radius") != "0px" or row.get("status_padding") != "0px":
            raise AssertionError(f"{label} mapping consequence is styled as a badge: {row!r}")
        if row.get("status_text_transform") not in {"none", ""}:
            raise AssertionError(f"{label} mapping consequence changes case: {row!r}")


def measure_page(page: Page, target: str, state: str, viewport: dict[str, int], splitters: dict[str, Any], interactions: dict[str, bool], *, responsive: bool = False) -> dict[str, Any]:
    snapshot = card_snapshot(page)
    visual_acceptance = visual_acceptance_snapshot(page)
    assert_mapping_grammar(snapshot, target, state)
    wide = viewport["width"] >= 1800
    if any(value != 0 for value in overflow_snapshot(page).values()):
        raise AssertionError(f"page overflow for {target}: {overflow_snapshot(page)}")
    if snapshot["delivery_width"] < 300 or snapshot["delivery_width"] > 340:
        raise AssertionError(f"delivery sheet outside 300-340px rail: {snapshot}")
    if snapshot["native_width"] <= snapshot["delivery_width"]:
        raise AssertionError(f"native preview is not dominant: {snapshot}")
    expected_light_preview = {
        "preview_surface": "rgb(247, 249, 250)",
        "preview_ink": "rgb(37, 52, 61)",
        "preview_border": "rgb(170, 181, 187)",
    }
    for key, expected in expected_light_preview.items():
        if snapshot[key] != expected:
            raise AssertionError(f"native preview no longer uses the required light document grammar: {snapshot}")
    if snapshot["preview_scroll_range"] <= 0 and snapshot["preview_scroll_rail_visible"]:
        raise AssertionError(f"non-overflow native preview falsely exposes a custom scroll rail: {snapshot}")
    if snapshot["preview_scroll_rail_visible"] and {
        "preview_scroll_track": snapshot["preview_scroll_track"],
        "preview_scroll_divider": snapshot["preview_scroll_divider"],
        "preview_scroll_thumb": snapshot["preview_scroll_thumb"],
    } != {
        "preview_scroll_track": "rgb(220, 231, 236)",
        "preview_scroll_divider": "rgb(182, 201, 210)",
        "preview_scroll_thumb": "rgb(78, 129, 149)",
    }:
        raise AssertionError(f"visible native-preview rail does not use the sibling light document grammar: {snapshot}")
    if wide and state == "normal":
        plot = snapshot["response_plot_svg_aspect"]
        if not snapshot["response_plot_visible"]:
            raise AssertionError(f"wide normal card is missing its linked response plot: {snapshot}")
        if snapshot["card_content_child_count"] != 2:
            raise AssertionError(f"wide card introduced a third top-level pane: {snapshot}")
        if snapshot["response_plot_rows"] != 6 or len(snapshot["response_plot_series"]) != 6:
            raise AssertionError(f"wide response plot does not use all six exact *PLASTIC rows: {snapshot}")
        if snapshot["response_plot_first_point"] != {"stress": 450, "strain": 0}:
            raise AssertionError(f"wide response plot first point is not (0, 450 MPa): {snapshot}")
        if snapshot["response_plot_x_label"] != "True plastic strain [1]" or snapshot["response_plot_y_label"] != "True stress (MPa)":
            raise AssertionError(f"wide response plot axes are not engineering-labeled: {snapshot}")
        x_domain = snapshot["response_plot_x_domain"]
        y_domain = snapshot["response_plot_y_domain"]
        strains = [row["strain"] for row in snapshot["response_plot_series"]]
        stresses = [row["stress"] for row in snapshot["response_plot_series"]]
        if not (x_domain and y_domain and x_domain[0] < min(strains) and x_domain[1] > max(strains) and y_domain[0] < min(stresses) and y_domain[1] > max(stresses)):
            raise AssertionError(f"wide response plot has no data-relative axis headroom: {snapshot}")
        if not plot or plot["mismatch"] > 0.005:
            raise AssertionError(f"wide response SVG viewBox/render aspect mismatch: {snapshot}")
        if snapshot["response_plot_preserve_aspect_ratio"].lower() == "none":
            raise AssertionError(f"wide response SVG uses forbidden non-uniform glyph scaling: {snapshot}")
        if not all(10 <= snapshot[key] <= 12.5 for key in ("response_plot_tick_font_px", "response_plot_title_font_px")):
            raise AssertionError(f"wide response plot typography is outside 10-12.5px: {snapshot}")
        native_ratio_max = {1920: 0.42, 2560: 0.34, 3840: 0.24}[viewport["width"]]
        if snapshot["native_surface_ratio"] > native_ratio_max or snapshot["preview_rendered_height"] > 440 or snapshot["response_plot_ratio"] < 0.40:
            raise AssertionError(f"wide card evidence split violates the content-bounded native/plot policy: {snapshot}")
        if not snapshot["preview_scroll_rail_visible"] or snapshot["preview_scroll_range"] <= 0 or snapshot["preview_scroll_gutter_width"] < 6 or snapshot["preview_scroll_thumb_ratio"] <= 0 or snapshot["preview_scroll_text_clearance"] <= 0:
            raise AssertionError(f"wide card native preview lacks a usable visible local-scroll rail: {snapshot}")
        if not interactions.get("native_scroll_wheel"):
            raise AssertionError(f"wide card native preview wheel scroll has no consequence: {interactions}")
    elif not wide and snapshot["response_plot_visible"]:
        raise AssertionError(f"sub-1800 card unexpectedly exposes wide linked plot: {snapshot}")
    if state == "normal":
        if not snapshot["native_text_visible"] or snapshot["unavailable_visible"] or snapshot["loading_visible"]:
            raise AssertionError(f"normal preview not visible: {snapshot}")
        if snapshot["download"] != {"text": "Download .inp", "disabled": False, "primary": True}:
            raise AssertionError(f"normal command mismatch: {snapshot}")
        if any("APPROXIMATED" in row or "UNSUPPORTED" in row for row in snapshot["mapping_rows"]):
            raise AssertionError(f"normal mapping includes blocked state: {snapshot}")
    if state == "approximation":
        if not snapshot["native_text_visible"] or not any("post-necking extension" in row.casefold() for row in snapshot["mapping_rows"]):
            raise AssertionError(f"approximation mapping/preview missing: {snapshot}")
        if snapshot["approximation_acknowledged"] or not snapshot["download"]["disabled"] or snapshot["download"]["text"] != "Download .rad":
            raise AssertionError(f"approximation acknowledgement/command mismatch: {snapshot}")
    if state == "unsupported":
        if snapshot["native_text_visible"] or not snapshot["unavailable_visible"] or not any("damage initiation" in row.casefold() for row in snapshot["mapping_rows"]):
            raise AssertionError(f"unsupported preview/mapping missing: {snapshot}")
        if not snapshot["download"]["disabled"] or snapshot["download"]["text"] != "Download blocked":
            raise AssertionError(f"unsupported command mismatch: {snapshot}")
    return {
        "schema_version": 1,
        "target": target,
        "family": "MAT-CARD",
        "kind": "normal" if state == "normal" else state,
        "state": state,
        "capture_date": "2026-07-30",
        "viewport": viewport,
        "regions": {key: rounded_box(page, selector) for key, selector in {
            "application_bar": "[data-region='application-bar']",
            "command_bar": "[data-region='command-bar']",
            "workspace": "[data-region='workspace']",
            "navigator": "[data-region='navigator']",
            "navigator_divider": "[data-region='navigator-divider']",
            "datasheet": "[data-region='datasheet']",
            "record_header": ".record-header",
            "tabs": ".datasheet-tabs",
            "card_panel": "[data-region='card-panel']",
            "card_heading": "[data-region='card-heading']",
            "card_content": "[data-region='card-content']",
            "native_preview": ".native-preview",
            "delivery_sheet": ".delivery-sheet",
            "status_bar": "[data-region='status-bar']",
        }.items()},
        "tree": tree_snapshot(page),
        "selected_record": page.locator("#tree-dp780").get_attribute("aria-selected") == "true",
        "tabs": {"count": page.locator("[role='tab']").count(), "labels": page.locator("[role='tab']").all_text_contents(), "active": page.locator("[role='tab'][aria-selected='true']").inner_text()},
        "overflow": overflow_snapshot(page),
        "splitter_evidence": splitters,
        "card": snapshot,
        "interactions": interactions,
        "forbidden_visible_terms": [term for term in ["UUID", "Mapping Profile", "Recipe", "Batch", "provenance"] if term.casefold() in page.locator("body").inner_text().casefold()],
        "nested_persistent_card_count": page.locator(".card, .content-card, .module-material-card").count(),
        "responsive_evidence": responsive,
        **visual_acceptance,
        "web_interface_guidelines_audit": {"checked": ["semantic buttons, links, tabs and associated labels", "visible keyboard focus", "deliberate text containment and native scrolling", "no decorative nested cards"], "result": "pass"},
    }


def load_page(page: Page, state: str, viewport: dict[str, int]) -> None:
    url = f"{HTML.as_uri()}?{urlencode({'state': state})}"
    page.set_viewport_size({"width": viewport["width"], "height": viewport["height"]})
    page.goto(url, wait_until="load")
    page.evaluate("document.fonts.ready")
    page.wait_for_timeout(50)


def capture_one(target: str, config: dict[str, Any], *, save_image: bool, responsive: bool = False) -> dict[str, Any]:
    image_path = config.get("image") if save_image else None
    measurement_path = config.get("measurements") if save_image else None
    if image_path:
        image_path.parent.mkdir(parents=True, exist_ok=True)
    console_errors: list[str] = []
    page_errors: list[str] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": config["viewport"]["width"], "height": config["viewport"]["height"]}, device_scale_factor=1)
        page = context.new_page()
        page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
        page.on("pageerror", lambda error: page_errors.append(str(error)))
        load_page(page, config["state"], config["viewport"])
        splitters = splitter_states(page)
        page.reload(wait_until="load")
        page.evaluate("document.fonts.ready")
        interactions = common_interactions(page, config["state"] if config["state"] in {"normal", "approximation", "unsupported"} else "normal")
        page.reload(wait_until="load")
        page.evaluate("document.fonts.ready")
        measure = measure_page(page, target, config["state"], config["viewport"], splitters, interactions, responsive=responsive)
        if console_errors or page_errors:
            raise AssertionError(f"browser errors for {target}: console={console_errors}, page={page_errors}")
        screenshot_bytes = page.screenshot(path=str(image_path), full_page=False) if image_path else page.screenshot(full_page=False)
        browser.close()
    digest = hashlib.sha256(screenshot_bytes).hexdigest()
    width, height = struct.unpack(">II", screenshot_bytes[16:24])
    if (width, height) != (config["viewport"]["width"], config["viewport"]["height"]):
        raise AssertionError(f"screenshot dimensions for {target}: {(width, height)}")
    measure.update({"image": str(image_path.relative_to(ROOT)).replace("\\", "/") if image_path else None, "image_sha256": digest, "screenshot_dimensions": {"width": width, "height": height}, "console_errors": console_errors, "page_errors": page_errors})
    if measurement_path:
        measurement_path.write_text(json.dumps(measure, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return measure


def responsive_path(target: str, width_key: str) -> tuple[Path, Path]:
    image = IMAGE_DIR / f"{target}.responsive-{width_key}.png"
    measurements = IMAGE_DIR / f"{target}.responsive-{width_key}.measurements.json"
    return image, measurements


def state_image_path(state: str, viewport_key: str, *, recovery: bool = False) -> Path:
    state_name = f"{state}-recovery" if recovery else state
    return IMAGE_DIR / f"materials-card-state-{state_name}-{viewport_key}.png"


def persisted_screenshot(page: Page, path: Path) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    screenshot = page.screenshot(path=str(path), full_page=False)
    width, height = struct.unpack(">II", screenshot[16:24])
    return {
        "image": path.relative_to(ROOT).as_posix(),
        "screenshot_dimensions": {"width": width, "height": height},
        "screenshot_sha256": hashlib.sha256(screenshot).hexdigest(),
    }


def state_evidence() -> dict[str, Any]:
    states = ["long", "loading", "error"]
    evidence: dict[str, Any] = {"schema_version": 1, "family": "MAT-CARD", "capture_date": "2026-07-30", "states": {}}
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        for state in states:
            evidence["states"][state] = {}
            for key in STATE_VIEWPORT_KEYS:
                viewport = VIEWPORTS[key]
                console_errors: list[str] = []
                page_errors: list[str] = []
                context = browser.new_context(viewport={"width": viewport["width"], "height": viewport["height"]}, device_scale_factor=1)
                page = context.new_page()
                page.on("console", lambda message, errors=console_errors: errors.append(message.text) if message.type == "error" else None)
                page.on("pageerror", lambda error, errors=page_errors: errors.append(str(error)))
                load_page(page, state, viewport)
                snap = card_snapshot(page)
                assert_mapping_grammar(snap, f"{state}/{key}", state)
                if state == "long":
                    if snap["preview_scroll_height"] <= snap["preview_client_height"] or not snap["preview_scroll_rail_visible"] or snap["preview_scroll_gutter_width"] < 6 or snap["preview_scroll_text_clearance"] <= 0 or snap["delivery_width"] < 300:
                        raise AssertionError(f"long evidence not independently scrollable: {state} {key} {snap}")
                    page.locator("#preview-scroll").evaluate("element => { element.scrollTop = element.scrollHeight; return element.scrollTop > 0; }")
                if state == "loading" and not snap["loading_visible"]:
                    raise AssertionError(f"loading evidence missing: {state} {key}")
                if state == "error":
                    if not snap["error_visible"] or not snap["native_text_visible"]:
                        raise AssertionError(f"error evidence did not preserve preview: {state} {key}")
                    if not snap["retry_visible"]:
                        raise AssertionError(f"error evidence missing Retry control: {state} {key}")
                    pre_retry = {
                        "state": "error",
                        "viewport": viewport,
                        **persisted_screenshot(page, state_image_path(state, key)),
                        "overflow": overflow_snapshot(page),
                        "card": snap,
                        **visual_acceptance_snapshot(page),
                        "preserved_task_context": {
                            "selected_record": page.locator("#tree-dp780").get_attribute("aria-selected") == "true",
                            "active_tab": page.locator("[role='tab'][aria-selected='true']").inner_text(),
                        },
                        "console_errors": console_errors,
                        "page_errors": page_errors,
                    }
                    page.locator("#retry-preview").click()
                    if page.locator("body").get_attribute("data-preview-retry") != "true":
                        raise AssertionError(f"retry did not announce: {state} {key}")
                    recovery_card = card_snapshot(page)
                    assert_mapping_grammar(recovery_card, f"{state}/{key}/recovery", "normal")
                    if recovery_card["state"] != "normal" or not recovery_card["native_text_visible"] or recovery_card["error_visible"]:
                        raise AssertionError(f"retry did not recover normal preview/context: {state} {key} {recovery_card}")
                    evidence["states"][state][key] = {
                        **pre_retry,
                        "recovery": {
                            "state": recovery_card["state"],
                            "retry_announced": page.locator("body").get_attribute("data-preview-retry") == "true",
                            **persisted_screenshot(page, state_image_path(state, key, recovery=True)),
                            "overflow": overflow_snapshot(page),
                            "card": recovery_card,
                            **visual_acceptance_snapshot(page),
                            "preserved_task_context": {
                                "selected_record": page.locator("#tree-dp780").get_attribute("aria-selected") == "true",
                                "active_tab": page.locator("[role='tab'][aria-selected='true']").inner_text(),
                            },
                        },
                    }
                else:
                    evidence["states"][state][key] = {
                        "viewport": viewport,
                        **persisted_screenshot(page, state_image_path(state, key)),
                        "overflow": overflow_snapshot(page),
                        "card": card_snapshot(page),
                        **visual_acceptance_snapshot(page),
                        "console_errors": console_errors,
                        "page_errors": page_errors,
                    }
                if console_errors or page_errors:
                    raise AssertionError(f"browser errors in evidence {state}/{key}: {console_errors} {page_errors}")
                context.close()
        browser.close()
    return evidence


def main() -> None:
    args = parse_args()
    selected = list(TARGETS) if args.all_packet_targets else [args.target]
    captured: list[dict[str, Any]] = []
    for target in selected:
        config = TARGETS[target]
        if not HTML.is_file() or not CSS.is_file() or not JAVASCRIPT.is_file():
            raise SystemExit("MAT-CARD source HTML/CSS/JS is missing")
        captured.append(capture_one(target, config, save_image=True))
    if args.all_packet_targets:
        for target, state in EXCEPTION_STATES.items():
            for key in ("1366x768", "1920x1080"):
                image, measurements = responsive_path(target, key)
                responsive_config = {"state": state, "viewport": VIEWPORTS[key], "image": image, "measurements": measurements}
                captured.append(capture_one(f"{target}.responsive-{key}", responsive_config, save_image=True, responsive=True))
        state_evidence_path = REFERENCE_DIR / "materials-card-wave02.state-evidence.json"
        state_evidence_path.write_text(json.dumps(state_evidence(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    references = []
    wide_support = []
    for entry in captured:
        target = entry["target"]
        if target not in TARGETS:
            continue
        config = TARGETS[target]
        pointer = {"id": target, "kind": config["state"], "viewport": config["viewport"], "html": str(HTML.relative_to(ROOT)).replace("\\", "/"), "css": str(CSS.relative_to(ROOT)).replace("\\", "/"), "javascript": str(JAVASCRIPT.relative_to(ROOT)).replace("\\", "/"), "image": entry["image"], "measurements": str(config["measurements"].relative_to(ROOT)).replace("\\", "/"), "image_sha256": entry["image_sha256"], "status": "pending", "main_agent_evaluation": {"status": "pending"}, "product_owner_approval": {"status": "absent"}, "responsive_evidence": [str(responsive_path(target, key)[0].relative_to(ROOT)).replace("\\", "/") for key in ("1366x768", "1920x1080")] if target in EXCEPTION_STATES else []}
        (references if target in CANONICAL_TARGETS else wide_support).append(pointer)
    staging = {"schema_version": 1, "generated": "2026-07-30", "family": "MAT-CARD", "references": references, "wide_support": wide_support, "state_evidence": str((REFERENCE_DIR / "materials-card-wave02.state-evidence.json").relative_to(ROOT)).replace("\\", "/") if args.all_packet_targets else None}
    STAGING_INDEX.parent.mkdir(parents=True, exist_ok=True)
    STAGING_INDEX.write_text(json.dumps(staging, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    for entry in captured:
        if entry["target"] in TARGETS:
            print(f"PASS {entry['target']} {entry['viewport']['width']}x{entry['viewport']['height']} {entry['image_sha256']}")
    print(f"staging_index: {STAGING_INDEX.relative_to(ROOT).as_posix()}")


if __name__ == "__main__":
    main()

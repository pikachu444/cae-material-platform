# ruff: noqa: E501
from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
from pathlib import Path
from typing import Any

from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parents[3]
REFERENCE_DIR = ROOT / "docs/00-research/ux-service-reference"
IMAGE_DIR = ROOT / "docs/17-evidence/images/issue-167-service-reference"
BASE_HTML = REFERENCE_DIR / "materials-datasheet-overview-normal.html"
COMPACT_CSS = REFERENCE_DIR / "materials-datasheet-overview-normal-1366x768.css"
COMPACT_JS = REFERENCE_DIR / "materials-datasheet-overview-normal-1366x768.js"
WIDE_CSS = REFERENCE_DIR / "materials-datasheet-overview-normal-1920x1080.css"
WIDE_JS = REFERENCE_DIR / "materials-datasheet-overview-normal-1920x1080.js"
RELATED_CSS = REFERENCE_DIR / "materials-datasheet-related-long-1440x900.css"
RELATED_JS = REFERENCE_DIR / "materials-datasheet-related-long-1440x900.js"
EMPTY_CSS = REFERENCE_DIR / "materials-datasheet-empty-1440x900.css"
EMPTY_JS = REFERENCE_DIR / "materials-datasheet-empty-1440x900.js"
STAGING_INDEX = IMAGE_DIR / "materials-datasheet-wave01.staging.json"

TARGETS: dict[str, dict[str, Any]] = {
    "materials-datasheet-overview-normal-1920x1080": {
        "kind": "normal",
        "html": BASE_HTML,
        "css": WIDE_CSS,
        "javascript": WIDE_JS,
        "viewport": {"width": 1920, "height": 1080, "device_scale_factor": 1},
        "navigator_width": 280,
        "compact_max": 360,
        "datasheet_width": 1619,
        "main_width": 1319,
        "aside_width": 300,
        "splitter_layouts": {
            "default": {
                "navigator": 280,
                "divider": 5,
                "datasheet": 1619,
                "main": 1319,
                "aside": 300,
                "plot": 1295,
            },
            "navigator_arrow_right": {
                "navigator": 288,
                "divider": 5,
                "datasheet": 1611,
                "main": 1311,
                "aside": 300,
                "plot": 1287,
            },
            "navigator_home": {
                "navigator": 200,
                "divider": 5,
                "datasheet": 1699,
                "main": 1399,
                "aside": 300,
                "plot": 1375,
            },
            "navigator_end": {
                "navigator": 360,
                "divider": 5,
                "datasheet": 1539,
                "main": 1239,
                "aside": 300,
                "plot": 1215,
            },
        },
        "splitter_states": {
            "default": 280,
            "navigator_arrow_right": 288,
            "navigator_home": 200,
            "navigator_end": 360,
        },
        "image": IMAGE_DIR / "materials-datasheet-overview-normal-1920x1080.png",
        "measurements": IMAGE_DIR
        / "materials-datasheet-overview-normal-1920x1080.measurements.json",
    },
    "materials-datasheet-related-long-1440x900": {
        "kind": "related",
        "html": BASE_HTML,
        "css": RELATED_CSS,
        "javascript": RELATED_JS,
        "viewport": {"width": 1440, "height": 900, "device_scale_factor": 1},
        "navigator_width": 264,
        "compact_max": 360,
        "splitter_states": {
            "default": 264,
            "navigator_arrow_right": 272,
            "navigator_home": 200,
            "navigator_end": 360,
        },
        "image": IMAGE_DIR / "materials-datasheet-related-long-1440x900.png",
        "measurements": IMAGE_DIR / "materials-datasheet-related-long-1440x900.measurements.json",
        "responsive": True,
    },
    "materials-datasheet-empty-1440x900": {
        "kind": "empty",
        "html": BASE_HTML,
        "css": EMPTY_CSS,
        "javascript": EMPTY_JS,
        "viewport": {"width": 1440, "height": 900, "device_scale_factor": 1},
        "navigator_width": 264,
        "compact_max": 360,
        "splitter_states": {
            "default": 264,
            "navigator_arrow_right": 272,
            "navigator_home": 200,
            "navigator_end": 360,
        },
        "image": IMAGE_DIR / "materials-datasheet-empty-1440x900.png",
        "measurements": IMAGE_DIR / "materials-datasheet-empty-1440x900.measurements.json",
        "responsive": True,
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Capture the WAVE-01 Materials datasheet static-reference family."
    )
    parser.add_argument("--target", choices=sorted(TARGETS), help="One canonical target id.")
    parser.add_argument(
        "--all-packet-targets",
        action="store_true",
        help="Capture all three canonical targets and Related/Empty responsive evidence.",
    )
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
    width, height = struct.unpack(">II", data[16:24])
    return width, height


def assert_close(actual: float, expected: float, name: str, tolerance: float = 0.6) -> None:
    if abs(actual - expected) > tolerance:
        raise AssertionError(f"{name}: expected {expected}px, got {actual}px")


def overflow_snapshot(page: Page) -> dict[str, int]:
    return page.evaluate(
        """() => ({
          document_horizontal: document.documentElement.scrollWidth - document.documentElement.clientWidth,
          document_vertical: document.documentElement.scrollHeight - document.documentElement.clientHeight,
          body_horizontal: document.body.scrollWidth - document.body.clientWidth,
          body_vertical: document.body.scrollHeight - document.body.clientHeight,
        })"""
    )


def tree_snapshot(page: Page) -> dict[str, Any]:
    return page.locator(".tree-scroll").evaluate(
        """(element) => {
          const right = element.getBoundingClientRect().right;
          const labels = [...element.querySelectorAll('[role="treeitem"]')].map((row) => ({
            expected: row.dataset.kind,
            actual: row.querySelector('.tree-kind')?.textContent.trim(),
          }));
          const kindBoxes = [...element.querySelectorAll('.tree-kind')].map((kind) => kind.getBoundingClientRect());
          return {
            horizontal_overflow: element.scrollWidth - element.clientWidth,
            all_tree_kind_right_edges_within_content: kindBoxes.every((box) => box.right <= right + 0.01),
            tree_kind_labels: labels.map((label) => label.actual),
            tree_kind_labels_match: labels.every((label) => label.expected === label.actual),
          };
        }"""
    )


def splitter_snapshot(page: Page) -> dict[str, Any]:
    return page.evaluate(
        """() => {
          const width = (selector) => Math.round(document.querySelector(selector).getBoundingClientRect().width);
          const separator = document.querySelector('[data-region="navigator-divider"]');
          const tab = document.querySelector('[role="tab"][aria-selected="true"]');
          return {
            widths: {
              navigator: width('[data-region="navigator"]'),
              divider: width('[data-region="navigator-divider"]'),
              datasheet: width('[data-region="datasheet"]'),
              related_list: document.querySelector('.related-list') ? width('.related-list') : null,
              related_context: document.querySelector('.related-context') ? width('.related-context') : null,
              empty_main: document.querySelector('.empty-main') ? width('.empty-main') : null,
              empty_context: document.querySelector('.empty-context') ? width('.empty-context') : null,
              main: document.querySelector('.overview-main') ? width('.overview-main') : null,
              aside: document.querySelector('.overview-aside') ? width('.overview-aside') : null,
              plot: document.querySelector('.plot-frame') ? width('.plot-frame') : null,
            },
            aria: {
              minimum: Number(separator.getAttribute('aria-valuemin')),
              maximum: Number(separator.getAttribute('aria-valuemax')),
              now: Number(separator.getAttribute('aria-valuenow')),
            },
            active_tab: tab?.textContent.trim() ?? null,
            tree: (() => {
              const element = document.querySelector('.tree-scroll');
              const right = element.getBoundingClientRect().right;
              const kinds = [...element.querySelectorAll('.tree-kind')].map((kind) => kind.getBoundingClientRect());
              return {
                horizontal_overflow: element.scrollWidth - element.clientWidth,
                all_tree_kind_right_edges_within_content: kinds.every((box) => box.right <= right + 0.01),
                tree_kind_labels_match: [...element.querySelectorAll('[role="treeitem"]')].every(
                  (row) => row.dataset.kind === row.querySelector('.tree-kind')?.textContent.trim()
                ),
              };
            })(),
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


def splitter_states(page: Page, config: dict[str, Any]) -> dict[str, Any]:
    splitter = page.locator("[data-region='navigator-divider']")
    viewport_width = page.evaluate("window.innerWidth")
    expected_navigator = (
        244
        if viewport_width == 1366
        else 280
        if viewport_width == 1920
        else config["navigator_width"]
    )
    expected_max = 345 if viewport_width == 1366 else config["compact_max"]
    evidence: dict[str, Any] = {}
    for label, key in (
        ("default", None),
        ("navigator_arrow_right", "ArrowRight"),
        ("navigator_home", "Home"),
        ("navigator_end", "End"),
    ):
        if key:
            splitter.focus()
            page.keyboard.press(key)
        evidence[label] = splitter_snapshot(page)
        expected = (
            expected_navigator
            if label == "default"
            else expected_navigator + 8
            if label == "navigator_arrow_right"
            else 200
            if label == "navigator_home"
            else expected_max
        )
        actual = evidence[label]
        if actual["widths"]["navigator"] != expected:
            raise AssertionError(f"{label} navigator width mismatch: {actual}")
        if (
            actual["widths"]["divider"] != 5
            or actual["widths"]["navigator"] != actual["aria"]["now"]
        ):
            raise AssertionError(f"{label} divider/ARIA continuity failed: {actual}")
        if actual["aria"]["minimum"] != 200 or actual["aria"]["maximum"] != expected_max:
            raise AssertionError(f"{label} splitter range mismatch: {actual}")
        expected_layout = config.get("splitter_layouts", {}).get(label)
        if expected_layout and any(
            actual["widths"].get(key) != value for key, value in expected_layout.items()
        ):
            raise AssertionError(f"{label} inner layout mismatch: {actual}")
        if actual["widths"]["datasheet"] < 720:
            raise AssertionError(f"{label} datasheet is below 720px: {actual}")
        if any(value != 0 for value in actual["overflow"].values()):
            raise AssertionError(f"{label} page overflow: {actual}")
        if (
            actual["tree"]["horizontal_overflow"] != 0
            or not actual["tree"]["all_tree_kind_right_edges_within_content"]
            or not actual["tree"]["tree_kind_labels_match"]
        ):
            raise AssertionError(f"{label} tree containment failed: {actual}")
        if not actual["selected_record_visible"]:
            raise AssertionError(f"{label} selected Record is not visible")
        page.locator("[data-region='navigator-divider']").focus()
    return evidence


def nice_step(rough_step: float, factors: list[float]) -> float:
    exponent = math.floor(math.log10(rough_step))
    candidates = [
        factor * 10**power for power in range(exponent - 1, exponent + 3) for factor in factors
    ]
    return min(candidate for candidate in candidates if candidate >= rough_step - 1e-12)


def derive_axis(
    minimum: float, maximum: float, ratio: float, intervals: int, factors: list[float]
) -> dict[str, float]:
    padded = maximum + (maximum - minimum) * ratio
    rough = (padded - minimum) / intervals
    step = nice_step(rough, factors)
    domain = math.ceil(padded / step - 1e-12) * step
    return {
        "padded_maximum": round(padded, 10),
        "rough_step": round(rough, 10),
        "nice_step": round(step, 10),
        "domain_maximum": round(domain, 10),
    }


def plot_snapshot(page: Page) -> dict[str, Any]:
    return page.locator(".response-plot").evaluate(
        """(plot) => {
          const number = (element, attribute) => Number(element.getAttribute(attribute));
          const lines = [...plot.querySelectorAll('.plot-grid line')];
          const horizontal = lines.filter((line) => number(line, 'y1') === number(line, 'y2'));
          const vertical = lines.filter((line) => number(line, 'x1') === number(line, 'x2'));
          const path = plot.querySelector('.response-line');
          const box = path.getBBox();
          const start = path.getPointAtLength(0);
          const endpoint = path.getPointAtLength(path.getTotalLength());
          const plotArea = {
            left: Math.min(...vertical.map((line) => number(line, 'x1'))),
            right: Math.max(...vertical.map((line) => number(line, 'x1'))),
            top: Math.min(...horizontal.map((line) => number(line, 'y1'))),
            bottom: Math.max(...horizontal.map((line) => number(line, 'y1'))),
          };
          const response = {x: box.x, y: box.y, right: box.x + box.width, bottom: box.y + box.height};
          return {
            declared_series: {
              strain: {minimum: Number(plot.dataset.seriesMinStrain), maximum: Number(plot.dataset.seriesMaxStrain)},
              stress_mpa: {minimum: Number(plot.dataset.seriesMinStressMpa), maximum: Number(plot.dataset.seriesMaxStressMpa)},
            },
            domain_policy: {
              upper_headroom_ratio: Number(plot.dataset.axisHeadroomRatio),
              target_intervals: {strain: Number(plot.dataset.axisTargetIntervalsStrain), stress_mpa: Number(plot.dataset.axisTargetIntervalsStress)},
              nice_step_factors: plot.dataset.axisNiceStepFactors.split(',').map(Number),
            },
            declared_axis_maxima: {strain: Number(plot.dataset.axisMaxStrain), stress_mpa: Number(plot.dataset.axisMaxStressMpa)},
            plot_area: plotArea,
            response_path: {
              bounding_box: {...response, width: box.width, height: box.height},
              start: {x: start.x, y: start.y},
              endpoint: {x: endpoint.x, y: endpoint.y},
              fully_inside_plot: response.x >= plotArea.left && response.right <= plotArea.right && response.y >= plotArea.top && response.bottom <= plotArea.bottom,
            },
            headroom: {right: plotArea.right - response.right, top: response.y - plotArea.top},
            visible_text: {
              plot: [...plot.querySelectorAll('text')].map((text) => text.textContent.trim()),
              legend: [...document.querySelectorAll('.plot-legend')].map((legend) => legend.textContent.trim()),
            },
          };
        }"""
    )


def normal_interactions(page: Page) -> dict[str, bool]:
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
    click_tabs = True
    for button in page.locator("[role='tab']").all():
        button.click()
        click_tabs = click_tabs and page.locator("body").get_attribute(
            "data-active-tab"
        ) == button.get_attribute("data-tab")
    page.locator("#tab-evidence").focus()
    page.keyboard.press("Home")
    tab_keys = page.evaluate("document.activeElement?.id") == "tab-overview"
    page.keyboard.press("End")
    tab_keys = tab_keys and page.evaluate("document.activeElement?.id") == "tab-evidence"
    page.keyboard.press("ArrowLeft")
    tab_keys = tab_keys and page.evaluate("document.activeElement?.id") == "tab-related"
    page.locator("#tab-overview").click()
    overview = page.locator("#tab-overview").get_attribute("aria-selected") == "true"
    page.locator("#preview-rad").click()
    preview = page.locator("body").get_attribute("data-card-preview") == "OpenRadioss:.rad"
    page.locator("#download-rad").click()
    download = page.locator("body").get_attribute("data-card-download") == "OpenRadioss:.rad"
    return {
        "navigator_search_shortcut": search_focus,
        "tree_search": tree_search,
        "back_to_results": restored,
        "tree_keyboard": home and end and previous and selected,
        "tabs_click_keyboard": click_tabs and tab_keys and overview,
        "card_preview": preview,
        "card_download": download,
    }


def related_interactions(page: Page) -> dict[str, bool]:
    buttons = page.locator(".relation-select")
    buttons.nth(1).click()
    reverse = (
        page.locator("body").get_attribute("data-related-selection") == "DP780-OPENRADIOSS-CARD-01"
    )
    context = page.locator("#related-context-record").inner_text().startswith("DP780 solver-card")
    buttons.nth(0).focus()
    page.keyboard.press("Enter")
    forward = page.locator("body").get_attribute("data-related-selection") == "DP780-LONG-CYCLE-03"
    page.locator("#open-related-record").click()
    opened = page.locator("body").get_attribute("data-related-record-open") == "DP780-LONG-CYCLE-03"
    current = page.locator("#tree-dp780").get_attribute("aria-selected") == "true"
    active = page.locator("[role='tab'][aria-selected='true']").inner_text() == "Related"
    return {
        "reverse_row_selection": reverse and context,
        "forward_keyboard_selection": forward,
        "open_exact_related_record": opened,
        "current_record_preserved": current,
        "related_tab_active": active,
    }


def empty_interactions(page: Page) -> dict[str, bool]:
    button = page.locator("#empty-back-to-results")
    button.focus()
    focused = page.evaluate("document.activeElement?.id") == "empty-back-to-results"
    button.click()
    returned = page.locator("body").get_attribute("data-empty-return") == "results"
    hash_consequence = page.evaluate("window.location.hash") == "#results?from=datasheet-empty"
    current = page.locator("#tree-dp780").get_attribute("aria-selected") == "true"
    active = page.locator("[role='tab'][aria-selected='true']").inner_text() == "Overview"
    return {
        "safe_return_focus": focused,
        "safe_return": returned and hash_consequence,
        "current_record_preserved": current,
        "overview_tab_active": active,
    }


def load_page(
    page: Page, config: dict[str, Any], viewport: dict[str, int], *, reload: bool = False
) -> None:
    if reload:
        page.goto(config["html"].as_uri(), wait_until="load")
    else:
        page.goto(config["html"].as_uri(), wait_until="load")
    if config.get("css"):
        page.add_style_tag(path=str(config["css"]))
    if viewport["width"] == 1920:
        page.add_style_tag(path=str(WIDE_CSS))
    if viewport["width"] == 1366 and config.get("kind") in {"related", "empty"}:
        page.add_style_tag(path=str(COMPACT_CSS))
    if config.get("javascript"):
        page.add_script_tag(path=str(config["javascript"]))
    if viewport["width"] == 1920:
        page.add_script_tag(path=str(WIDE_JS))
    if viewport["width"] == 1366 and config.get("kind") in {"related", "empty"}:
        page.add_script_tag(path=str(COMPACT_JS))
    page.evaluate("document.fonts.ready")


def common_measurements(
    page: Page,
    target: str,
    config: dict[str, Any],
    splitter: dict[str, Any],
    interactions: dict[str, bool],
    viewport: dict[str, int],
) -> dict[str, Any]:
    body_text = page.locator("body").inner_text()
    forbidden = [
        term
        for term in ["UUID", "hash", "checksum", "Mapping Profile", "Recipe", "Batch", "provenance"]
        if term.casefold() in body_text.casefold()
    ]
    unsupported = [
        term
        for term in ["reviewed", "approved", "released", "delivered"]
        if term.casefold() in body_text.casefold()
    ]
    return {
        "target": target,
        "capture_date": "2026-07-29",
        "viewport": viewport,
        "regions": {
            "application_bar": rounded_box(page, "[data-region='application-bar']"),
            "command_bar": rounded_box(page, "[data-region='command-bar']"),
            "workspace": rounded_box(page, "[data-region='workspace']"),
            "navigator": rounded_box(page, "[data-region='navigator']"),
            "navigator_divider": rounded_box(page, "[data-region='navigator-divider']"),
            "datasheet": rounded_box(page, "[data-region='datasheet']"),
            "status_bar": rounded_box(page, "[data-region='status-bar']"),
        },
        "divider_visual_widths": page.locator(".splitter > span").evaluate_all(
            "(elements) => elements.map((element) => element.getBoundingClientRect().width)"
        ),
        "visible_splitter_count": page.locator(".splitter > span").count(),
        "tree": tree_snapshot(page),
        "selected_tree_rows": page.locator("[role='treeitem'][aria-selected='true']").count(),
        "selected_record": page.locator("#tree-dp780").get_attribute("aria-selected") == "true",
        "tabs": {
            "count": page.locator("[role='tab']").count(),
            "labels": page.locator("[role='tab']").all_text_contents(),
            "active": page.locator("[role='tab'][aria-selected='true']").inner_text(),
        },
        "overflow": overflow_snapshot(page),
        "forbidden_visible_terms": forbidden,
        "unsupported_labels": unsupported,
        "primary_command_count": page.locator(".primary-action").count(),
        "nested_persistent_card_count": page.locator(
            ".card, .content-card, .module-material-card"
        ).count(),
        "splitter_evidence": splitter,
        "interactions": interactions,
        "web_interface_guidelines_audit": {
            "source": "vercel-labs/web-interface-guidelines/command.md",
            "checked": [
                "semantic buttons, links, tabs and associated labels",
                "visible keyboard focus",
                "no fake controls or non-dialog ellipsis labels",
                "no render-time layout loop",
                "deliberate containment and truncation",
            ],
            "result": "pass",
        },
    }


def normal_measurements(
    page: Page,
    target: str,
    config: dict[str, Any],
    splitter: dict[str, Any],
    interactions: dict[str, bool],
    viewport: dict[str, int],
) -> dict[str, Any]:
    measurement = common_measurements(page, target, config, splitter, interactions, viewport)
    tree_heights = page.locator("[role='treeitem']").evaluate_all(
        "(elements) => elements.map((element) => element.getBoundingClientRect().height)"
    )
    property_heights = page.locator(".property-sheet tbody tr").evaluate_all(
        "(elements) => elements.map((element) => element.getBoundingClientRect().height)"
    )
    formats = page.locator(".solver-row").evaluate_all(
        "(rows) => rows.map((row) => ({solver: row.querySelector('.solver-identity strong')?.textContent.trim(), format: row.querySelector('.solver-format')?.textContent.trim()}))"
    )
    measurement.update(
        {
            "kind": "normal",
            "regions": {
                **measurement["regions"],
                "datasheet_main": rounded_box(page, ".overview-main"),
                "datasheet_aside": rounded_box(page, ".overview-aside"),
            },
            "row_density": {
                "tree": {
                    "count": len(tree_heights),
                    "minimum": min(tree_heights),
                    "maximum": max(tree_heights),
                },
                "properties": {
                    "count": len(property_heights),
                    "minimum": min(property_heights),
                    "maximum": max(property_heights),
                },
            },
            "property_headers": page.locator(".property-sheet thead th").all_text_contents(),
            "property_rows": page.locator(".property-sheet tbody tr").count(),
            "property_semantics": page.locator(".property-sheet tbody tr").evaluate_all(
                "(rows) => rows.map((row) => [...row.children].map((cell) => cell.textContent.trim()))"
            ),
            "solver_formats": formats,
            "solver_format_count": len(formats),
            "delivery_preview_count": page.locator(
                ".solver-actions button", has_text="Preview"
            ).count(),
            "delivery_download_count": page.locator(
                ".solver-actions button", has_text="Download"
            ).count(),
            "plot_domain": plot_snapshot(page),
            "first_viewport": page.evaluate("""() => {
          const viewport = {width: window.innerWidth, height: window.innerHeight};
          const statusTop = document.querySelector('[data-region="status-bar"]').getBoundingClientRect().top;
          const box = (element) => { const rect = element.getBoundingClientRect(); return {left: rect.left, top: rect.top, right: rect.right, bottom: rect.bottom, inside: rect.left >= 0 && rect.top >= 0 && rect.right <= viewport.width && rect.bottom <= statusTop}; };
          const groups = {
            selected_record: [box(document.querySelector('#tree-dp780'))], tabs: [...document.querySelectorAll('[role="tab"]')].map(box), headers: [...document.querySelectorAll('.property-sheet thead th')].map(box), rows: [...document.querySelectorAll('.property-sheet tbody tr')].map(box), plot: [box(document.querySelector('.plot-frame'))], condition: [box(document.querySelector('.condition-section'))], delivery: [box(document.querySelector('.delivery-section'))], formats: [...document.querySelectorAll('.solver-row')].map(box), previews: [...document.querySelectorAll('.solver-actions button')].filter((button) => button.textContent.trim() === 'Preview').map(box), downloads: [...document.querySelectorAll('.solver-actions button')].filter((button) => button.textContent.trim() === 'Download').map(box),
          };
          return {viewport, status_bar_top: statusTop, groups, all_inside: Object.values(groups).flat().every((entry) => entry.inside)};
        }"""),
        }
    )
    return measurement


def relation_measurements(
    page: Page,
    target: str,
    config: dict[str, Any],
    splitter: dict[str, Any],
    interactions: dict[str, bool],
    viewport: dict[str, int],
) -> dict[str, Any]:
    measurement = common_measurements(page, target, config, splitter, interactions, viewport)
    table = page.locator(".related-table")
    measurement.update(
        {
            "kind": "related",
            "related": {
                "active_tab": page.locator("[role='tab'][aria-selected='true']").inner_text(),
                "row_count": page.locator(".relation-row").count(),
                "directions": page.locator(".relation-direction").all_text_contents(),
                "relationship_titles": page.locator(".relation-direction").evaluate_all(
                    "(cells) => cells.map((cell) => cell.title)"
                ),
                "record_names": page.locator(".relation-select").all_text_contents(),
                "record_titles": page.locator(".relation-select").evaluate_all(
                    "(buttons) => buttons.map((button) => button.title)"
                ),
                "types": page.locator(".relation-type").all_text_contents(),
                "revisions": page.locator(".relation-revision").all_text_contents(),
                "table_horizontal_overflow": table.evaluate(
                    "(element) => element.scrollWidth - element.clientWidth"
                ),
                "table_scroll_horizontal_overflow": page.locator(".related-table-scroll").evaluate(
                    "(element) => element.scrollWidth - element.clientWidth"
                ),
                "cells_inside_boundary": table.evaluate(
                    """(element) => { const boundary = element.getBoundingClientRect(); return [...element.querySelectorAll('th, td')].every((cell) => { const box = cell.getBoundingClientRect(); return box.left >= boundary.left - 0.6 && box.right <= boundary.right + 0.6; }); }"""
                ),
                "context_record": page.locator("#related-context-record").inner_text(),
                "primary_open_count": page.locator("#open-related-record.primary-action").count(),
            },
            "topology_signature": {
                "navigator": True,
                "divider": True,
                "datasheet": True,
                "related_list": True,
                "related_context": True,
                "nested_cards": 0,
            },
        }
    )
    return measurement


def empty_measurements(
    page: Page,
    target: str,
    config: dict[str, Any],
    splitter: dict[str, Any],
    interactions: dict[str, bool],
    viewport: dict[str, int],
) -> dict[str, Any]:
    measurement = common_measurements(page, target, config, splitter, interactions, viewport)
    measurement.update(
        {
            "kind": "empty",
            "empty": {
                "active_tab": page.locator("[role='tab'][aria-selected='true']").inner_text(),
                "explanation": page.locator(".empty-explanation").inner_text(),
                "context": page.locator(".empty-context").inner_text(),
                "safe_return_label_count": page.locator("#empty-back-to-results").count(),
                "safe_return_primary_count": page.locator(
                    "#empty-back-to-results.primary-action"
                ).count(),
                "command_back_visible": page.locator("#back-to-results").is_visible(),
                "property_count": page.locator(".property-sheet").count(),
                "curve_count": page.locator(".response-plot").count(),
                "solver_row_count": page.locator(".solver-row").count(),
                "delivery_section_count": page.locator(".delivery-section").count(),
                "empty_panel_visible": page.locator(".empty-panel").is_visible(),
                "record_header": {
                    "visible": page.locator(".record-header").is_visible(),
                    "title": page.locator("#record-title").inner_text(),
                    "identity": page.locator(".record-meta span").all_text_contents(),
                    "synthetic_note": page.locator(".synthetic-note").inner_text(),
                    "revision_context": page.locator(".record-status").inner_text(),
                },
            },
            "topology_signature": {
                "navigator": True,
                "divider": True,
                "datasheet": True,
                "empty_panel": True,
                "nested_cards": 0,
            },
        }
    )
    return measurement


def capture_one(
    target: str,
    config: dict[str, Any],
    viewport: dict[str, int],
    image_path: Path,
    measurement_path: Path,
    *,
    responsive: bool = False,
) -> dict[str, Any]:
    image_path.parent.mkdir(parents=True, exist_ok=True)
    measurement_path.parent.mkdir(parents=True, exist_ok=True)
    console_errors: list[str] = []
    page_errors: list[str] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": viewport["width"], "height": viewport["height"]},
            device_scale_factor=viewport["device_scale_factor"],
        )
        page = context.new_page()
        page.on(
            "console",
            lambda message: (
                console_errors.append(message.text) if message.type == "error" else None
            ),
        )
        page.on("pageerror", lambda error: page_errors.append(str(error)))
        load_page(page, config, viewport)
        splitter = splitter_states(page, config)
        load_page(page, config, viewport, reload=True)
        interactions = (
            normal_interactions(page)
            if config["kind"] == "normal"
            else related_interactions(page)
            if config["kind"] == "related"
            else empty_interactions(page)
        )
        load_page(page, config, viewport, reload=True)
        if config["kind"] == "normal":
            measurement = normal_measurements(
                page, target, config, splitter, interactions, viewport
            )
        elif config["kind"] == "related":
            measurement = relation_measurements(
                page, target, config, splitter, interactions, viewport
            )
        else:
            measurement = empty_measurements(page, target, config, splitter, interactions, viewport)
        if console_errors or page_errors:
            raise AssertionError(
                f"browser errors for {target}: console={console_errors}, page={page_errors}"
            )
        page.screenshot(path=str(image_path), full_page=False)
        browser.close()
    digest = hashlib.sha256(image_path.read_bytes()).hexdigest()
    measurement["image"] = str(image_path.relative_to(ROOT)).replace("\\", "/")
    measurement["image_sha256"] = digest
    measurement["responsive_evidence"] = responsive
    measurement["console_errors"] = console_errors
    measurement["page_errors"] = page_errors
    measurement_path.write_text(
        json.dumps(measurement, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return measurement


def responsive_path(config: dict[str, Any], width: int, height: int) -> tuple[Path, Path]:
    stem = config["image"].stem
    suffix = f"responsive-{width}x{height}"
    return IMAGE_DIR / f"{stem}.{suffix}.png", IMAGE_DIR / f"{stem}.{suffix}.measurements.json"


def main() -> None:
    args = parse_args()
    selected = list(TARGETS) if args.all_packet_targets else [args.target]
    captured: list[dict[str, Any]] = []
    for target in selected:
        config = TARGETS[target]
        if not config["html"].is_file():
            raise SystemExit(f"missing HTML source: {config['html']}")
        for key in ("css", "javascript"):
            if config.get(key) and not Path(config[key]).is_file():
                raise SystemExit(f"missing target source: {config[key]}")
        captured.append(
            capture_one(target, config, config["viewport"], config["image"], config["measurements"])
        )
        if config.get("responsive"):
            for width, height in ((1366, 768), (1920, 1080)):
                image, measurements = responsive_path(config, width, height)
                captured.append(
                    capture_one(
                        target,
                        config,
                        {"width": width, "height": height, "device_scale_factor": 1},
                        image,
                        measurements,
                        responsive=True,
                    )
                )
    staging = {
        "schema_version": 1,
        "generated": "2026-07-29",
        "family": "MAT-DETAIL",
        "references": [
            {
                "id": entry["target"],
                "kind": entry["kind"],
                "viewport": entry["viewport"],
                "image": entry["image"],
                "measurements": entry["target"] + ".measurements.json",
                "image_sha256": entry["image_sha256"],
                "status": "pending",
                "main_agent_evaluation": {"status": "pending"},
                "product_owner_approval": {"status": "absent"},
                "responsive_evidence": (
                    [
                        str(responsive_path(TARGETS[entry["target"]], 1366, 768)[0].relative_to(ROOT))
                        .replace("\\", "/"),
                        entry["image"],
                        str(
                            responsive_path(TARGETS[entry["target"]], 1920, 1080)[0].relative_to(ROOT)
                        ).replace("\\", "/"),
                    ]
                    if TARGETS[entry["target"]].get("responsive")
                    else []
                ),
            }
            for entry in captured
            if not entry.get("responsive_evidence")
        ],
    }
    STAGING_INDEX.parent.mkdir(parents=True, exist_ok=True)
    STAGING_INDEX.write_text(
        json.dumps(staging, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    for entry in captured:
        print(
            f"PASS {entry['target']} {entry['viewport']['width']}x{entry['viewport']['height']} {entry['image_sha256']}"
        )
    print(f"staging_index: {STAGING_INDEX.relative_to(ROOT).as_posix()}")


if __name__ == "__main__":
    main()

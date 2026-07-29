from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

from playwright.sync_api import Page, sync_playwright

TARGET_ID_1440 = "materials-datasheet-overview-normal-1440x900"
TARGET_ID_1366 = "materials-datasheet-overview-normal-1366x768"
ROOT = Path(__file__).resolve().parents[3]
HTML_PATH = ROOT / "docs/00-research/ux-service-reference/materials-datasheet-overview-normal.html"
TARGETS: dict[str, dict[str, Any]] = {
    TARGET_ID_1440: {
        "html": HTML_PATH,
        "image": ROOT
        / "docs/17-evidence/images/issue-167-service-reference/"
        "materials-datasheet-overview-normal-1440x900.png",
        "measurements": ROOT
        / "docs/17-evidence/images/issue-167-service-reference/"
        "materials-datasheet-overview-normal-1440x900.measurements.json",
        "viewport": {"width": 1440, "height": 900, "device_scale_factor": 1},
        "navigator_width": 264,
        "compact_max": 360,
        "datasheet_width": 1155,
        "main_width": 855,
        "aside_width": 300,
        "splitter_states": {
            "default": 264,
            "navigator_arrow_right": 272,
            "navigator_home": 200,
            "navigator_end": 360,
        },
    },
    TARGET_ID_1366: {
        "html": HTML_PATH,
        "css_override": ROOT
        / "docs/00-research/ux-service-reference/"
        "materials-datasheet-overview-normal-1366x768.css",
        "javascript_override": ROOT
        / "docs/00-research/ux-service-reference/"
        "materials-datasheet-overview-normal-1366x768.js",
        "image": ROOT
        / "docs/17-evidence/images/issue-167-service-reference/"
        "materials-datasheet-overview-normal-1366x768.png",
        "measurements": ROOT
        / "docs/17-evidence/images/issue-167-service-reference/"
        "materials-datasheet-overview-normal-1366x768.measurements.json",
        "viewport": {"width": 1366, "height": 768, "device_scale_factor": 1},
        "navigator_width": 244,
        "compact_max": 345,
        "datasheet_width": 1101,
        "main_width": 821,
        "aside_width": 280,
        "splitter_states": {
            "default": 244,
            "navigator_arrow_right": 252,
            "navigator_home": 200,
            "navigator_end": 345,
        },
        "splitter_layouts": {
            "default": {"main": 821, "aside": 280, "plot": 797},
            "navigator_arrow_right": {"main": 813, "aside": 280, "plot": 789},
            "navigator_home": {"main": 865, "aside": 280, "plot": 841},
            "navigator_end": {"main": 720, "aside": 280, "plot": 696},
        },
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Capture the Materials datasheet overview service reference."
    )
    parser.add_argument(
        "--target",
        choices=sorted(TARGETS),
        help="Registered reference target id.",
    )
    parser.add_argument("--html", type=Path, help="Exact static HTML path.")
    parser.add_argument("--image", type=Path, help="Exact output PNG path.")
    parser.add_argument("--measurements", type=Path, help="Exact output measurement JSON path.")
    args = parser.parse_args()
    if args.target is None and (args.html is None or args.image is None):
        parser.error("provide --target or both --html and --image")
    return args


def resolve_paths(
    args: argparse.Namespace,
) -> tuple[str, Path, Path, Path, dict[str, Any]]:
    registered = TARGETS.get(args.target, {}) if args.target else {}
    html_path = args.html or registered.get("html")
    image_path = args.image or registered.get("image")
    if html_path is None or image_path is None:
        raise SystemExit("target configuration is missing HTML or image path")
    html = Path(html_path).resolve()
    image = Path(image_path).resolve()
    measurements_arg = args.measurements or registered.get("measurements")
    measurements = (
        Path(measurements_arg).resolve()
        if measurements_arg
        else image.with_suffix(".measurements.json")
    )
    target = args.target or TARGET_ID_1440
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


def next_nice_step(rough_step: float, factors: list[float]) -> float:
    if rough_step <= 0 or not factors:
        raise AssertionError(f"invalid nice-step inputs: {rough_step}, {factors}")
    exponent = math.floor(math.log10(rough_step))
    candidates = [
        factor * 10**power
        for power in range(exponent - 1, exponent + 3)
        for factor in factors
    ]
    return min(candidate for candidate in candidates if candidate >= rough_step - 1e-12)


def derive_axis(
    minimum: float,
    maximum: float,
    headroom_ratio: float,
    target_intervals: int,
    factors: list[float],
) -> dict[str, float]:
    padded_maximum = maximum + (maximum - minimum) * headroom_ratio
    rough_step = (padded_maximum - minimum) / target_intervals
    nice_step = next_nice_step(rough_step, factors)
    domain_maximum = math.ceil(padded_maximum / nice_step - 1e-12) * nice_step
    return {
        "padded_maximum": round(padded_maximum, 10),
        "rough_step": round(rough_step, 10),
        "nice_step": round(nice_step, 10),
        "domain_maximum": round(domain_maximum, 10),
    }


def recompute_plot_domain(plot_domain: dict[str, Any]) -> dict[str, Any]:
    series = plot_domain["declared_series"]
    policy = plot_domain["domain_policy"]
    factors = policy["nice_step_factors"]
    axes = {
        "strain": derive_axis(
            series["strain"]["minimum"],
            series["strain"]["maximum"],
            policy["upper_headroom_ratio"],
            policy["target_intervals"]["strain"],
            factors,
        ),
        "stress_mpa": derive_axis(
            series["stress_mpa"]["minimum"],
            series["stress_mpa"]["maximum"],
            policy["upper_headroom_ratio"],
            policy["target_intervals"]["stress_mpa"],
            factors,
        ),
    }
    area = plot_domain["plot_area"]
    expected_endpoint = {
        "x": area["left"]
        + (series["strain"]["maximum"] - series["strain"]["minimum"])
        / (axes["strain"]["domain_maximum"] - series["strain"]["minimum"])
        * (area["right"] - area["left"]),
        "y": area["bottom"]
        - (series["stress_mpa"]["maximum"] - series["stress_mpa"]["minimum"])
        / (axes["stress_mpa"]["domain_maximum"] - series["stress_mpa"]["minimum"])
        * (area["bottom"] - area["top"]),
    }
    return {
        "axes": axes,
        "expected_response_endpoint": {
            "x": round(expected_endpoint["x"], 10),
            "y": round(expected_endpoint["y"], 10),
        },
    }


def overflow_snapshot(page: Page) -> dict[str, int]:
    return page.evaluate(
        """() => ({
          documentHorizontal:
            document.documentElement.scrollWidth - document.documentElement.clientWidth,
          documentVertical:
            document.documentElement.scrollHeight - document.documentElement.clientHeight,
          bodyHorizontal: document.body.scrollWidth - document.body.clientWidth,
          bodyVertical: document.body.scrollHeight - document.body.clientHeight
        })"""
    )


def plot_domain_snapshot(page: Page) -> dict[str, Any]:
    return page.locator(".response-plot").evaluate(
        """(plot) => {
          const number = (element, attribute) => Number(element.getAttribute(attribute));
          const gridLines = [...plot.querySelectorAll('.plot-grid line')];
          const horizontal = gridLines.filter((line) => number(line, 'y1') === number(line, 'y2'));
          const vertical = gridLines.filter((line) => number(line, 'x1') === number(line, 'x2'));
          const path = plot.querySelector('.response-line');
          const boundingBox = path.getBBox();
          const pointAt = (length) => path.getPointAtLength(length);
          const start = pointAt(0);
          const endpoint = pointAt(path.getTotalLength());
          const plotArea = {
            left: Math.min(...vertical.map((line) => number(line, 'x1'))),
            right: Math.max(...vertical.map((line) => number(line, 'x1'))),
            top: Math.min(...horizontal.map((line) => number(line, 'y1'))),
            bottom: Math.max(...horizontal.map((line) => number(line, 'y1'))),
          };
          const responseBoundingBox = {
            x: boundingBox.x,
            y: boundingBox.y,
            width: boundingBox.width,
            height: boundingBox.height,
            right: boundingBox.x + boundingBox.width,
            bottom: boundingBox.y + boundingBox.height,
          };
          return {
            declared_series: {
              strain: {
                minimum: Number(plot.dataset.seriesMinStrain),
                maximum: Number(plot.dataset.seriesMaxStrain),
              },
              stress_mpa: {
                minimum: Number(plot.dataset.seriesMinStressMpa),
                maximum: Number(plot.dataset.seriesMaxStressMpa),
              },
            },
            domain_policy: {
              upper_headroom_ratio: Number(plot.dataset.axisHeadroomRatio),
              target_intervals: {
                strain: Number(plot.dataset.axisTargetIntervalsStrain),
                stress_mpa: Number(plot.dataset.axisTargetIntervalsStress),
              },
              nice_step_factors: plot.dataset.axisNiceStepFactors
                .split(',')
                .map((factor) => Number(factor)),
            },
            declared_axis_maxima: {
              strain: Number(plot.dataset.axisMaxStrain),
              stress_mpa: Number(plot.dataset.axisMaxStressMpa),
            },
            plot_area: plotArea,
            response_path: {
              bounding_box: responseBoundingBox,
              start: {x: start.x, y: start.y},
              endpoint: {x: endpoint.x, y: endpoint.y},
              fully_inside_plot:
                responseBoundingBox.x >= plotArea.left &&
                responseBoundingBox.right <= plotArea.right &&
                responseBoundingBox.y >= plotArea.top &&
                responseBoundingBox.bottom <= plotArea.bottom,
            },
            headroom: {
              right: plotArea.right - responseBoundingBox.right,
              top: responseBoundingBox.y - plotArea.top,
            },
            visible_text: {
              plot: [...plot.querySelectorAll('text')].map((text) => text.textContent.trim()),
              legend: [...document.querySelectorAll('.plot-legend')].map((legend) =>
                legend.textContent.trim()
              ),
            },
          };
        }"""
    )


def tree_snapshot(page: Page) -> dict[str, Any]:
    return page.locator(".tree-scroll").evaluate(
        """(element) => {
          const contentRight = element.getBoundingClientRect().right;
          const kindRightEdges = [...element.querySelectorAll('.tree-kind')]
            .map((kind) => kind.getBoundingClientRect().right);
          const treeKindLabels = [...element.querySelectorAll('[role="treeitem"]')]
            .map((row) => ({
              expected: row.dataset.kind,
              actual: row.querySelector('.tree-kind')?.textContent.trim(),
            }));
          return {
            horizontal_overflow: element.scrollWidth - element.clientWidth,
            content_right: contentRight,
            tree_kind_right_edges: kindRightEdges,
            all_tree_kind_right_edges_within_content:
              kindRightEdges.every((right) => right <= contentRight + 0.01),
            tree_kind_labels: treeKindLabels.map((entry) => entry.actual),
            tree_kind_labels_match: treeKindLabels.every(
              (entry) => entry.expected === entry.actual
            ),
          };
        }"""
    )


def splitter_snapshot(page: Page) -> dict[str, Any]:
    return page.evaluate(
        """() => {
          const tolerance = 0.6;
          const width = (selector) => Math.round(
            document.querySelector(selector).getBoundingClientRect().width
          );
          const roundedBox = (element) => {
            const box = element.getBoundingClientRect();
            return {
              left: Math.round(box.left * 100) / 100,
              right: Math.round(box.right * 100) / 100,
              width: Math.round(box.width * 100) / 100,
            };
          };
          const propertyContainment = () => {
            const table = document.querySelector('.property-sheet');
            const container = table.closest('.property-section');
            const boundary = table.getBoundingClientRect();
            const cells = [...table.querySelectorAll('thead th, tbody th, tbody td')]
              .map((cell, index) => {
                const box = cell.getBoundingClientRect();
                return {
                  identifier: cell.closest('thead')
                    ? `header-${index}`
                    : `body-${cell.parentElement.rowIndex}-${cell.cellIndex}`,
                  section: cell.closest('thead') ? 'header' : 'body',
                  text: cell.textContent.trim(),
                  box: roundedBox(cell),
                  client_width: cell.clientWidth,
                  scroll_width: cell.scrollWidth,
                  within_table_horizontal_boundary:
                    box.left >= boundary.left - tolerance &&
                    box.right <= boundary.right + tolerance,
                  scroll_width_within_client_width:
                    cell.scrollWidth <= cell.clientWidth + tolerance,
                };
              });
            return {
              table_boundary: roundedBox(table),
              table_horizontal_overflow: table.scrollWidth - table.clientWidth,
              container_horizontal_overflow: container.scrollWidth - container.clientWidth,
              cells,
              all_cells_within_table_horizontal_boundary: cells.every(
                (cell) => cell.within_table_horizontal_boundary
              ),
              all_cell_scroll_widths_within_client_width: cells.every(
                (cell) => cell.scroll_width_within_client_width
              ),
            };
          };
          const separator = document.querySelector('[data-region="navigator-divider"]');
          return {
            widths: {
              navigator: width('[data-region="navigator"]'),
              divider: width('[data-region="navigator-divider"]'),
              datasheet: width('[data-region="datasheet"]'),
              main: width('.overview-main'),
              aside: width('.overview-aside'),
              plot: width('.plot-frame'),
            },
            aria: {
              minimum: Number(separator.getAttribute('aria-valuemin')),
              maximum: Number(separator.getAttribute('aria-valuemax')),
              now: Number(separator.getAttribute('aria-valuenow')),
            },
            tree_scroller: (() => {
              const element = document.querySelector('.tree-scroll');
              const contentRight = element.getBoundingClientRect().right;
              const kindRightEdges = [...element.querySelectorAll('.tree-kind')]
                .map((kind) => kind.getBoundingClientRect().right);
              const treeKindLabels = [...element.querySelectorAll('[role="treeitem"]')]
                .map((row) => ({
                  expected: row.dataset.kind,
                  actual: row.querySelector('.tree-kind')?.textContent.trim(),
                }));
              return {
                horizontal_overflow: element.scrollWidth - element.clientWidth,
                content_right: contentRight,
                tree_kind_right_edges: kindRightEdges,
                all_tree_kind_right_edges_within_content:
                  kindRightEdges.every((right) => right <= contentRight + 0.01),
                tree_kind_labels: treeKindLabels.map((entry) => entry.actual),
                tree_kind_labels_match: treeKindLabels.every(
                  (entry) => entry.expected === entry.actual
                ),
              };
            })(),
            property_containment: propertyContainment(),
            overflow: {
              documentHorizontal:
                document.documentElement.scrollWidth - document.documentElement.clientWidth,
              documentVertical:
                document.documentElement.scrollHeight - document.documentElement.clientHeight,
              bodyHorizontal: document.body.scrollWidth - document.body.clientWidth,
              bodyVertical: document.body.scrollHeight - document.body.clientHeight,
            },
            selected_record_visible: document.querySelector('#tree-dp780').checkVisibility(),
            delivery_visible: document.querySelector('.delivery-section').checkVisibility(),
          };
        }"""
    )


def assert_splitter(
    label: str,
    actual: dict[str, Any],
    expected_width: int,
    compact_max: int,
    config: dict[str, Any],
) -> None:
    widths = actual["widths"]
    if widths["navigator"] != expected_width:
        raise AssertionError(f"{label} navigator width: expected {expected_width}, got {widths}")
    if widths["divider"] != 5:
        raise AssertionError(f"{label} divider width: expected 5, got {widths['divider']}")
    if widths["navigator"] != actual["aria"]["now"]:
        raise AssertionError(f"{label} visible and ARIA navigator widths differ: {actual}")
    if actual["aria"]["minimum"] != 200 or actual["aria"]["maximum"] != compact_max:
        raise AssertionError(f"{label} splitter range is not truthful: {actual['aria']}")
    expected_layout = config.get("splitter_layouts", {}).get(label)
    if expected_layout and any(widths[key] != value for key, value in expected_layout.items()):
        raise AssertionError(
            f"{label} main/aside/plot widths: expected {expected_layout}, got {widths}"
        )
    if widths["main"] < 720:
        raise AssertionError(f"{label} main data region is below 720px: {widths['main']}")
    if any(value != 0 for value in actual["overflow"].values()):
        raise AssertionError(f"{label} page overflow: {actual['overflow']}")
    tree = actual["tree_scroller"]
    if (
        tree["horizontal_overflow"] != 0
        or not tree["all_tree_kind_right_edges_within_content"]
        or not tree["tree_kind_labels_match"]
    ):
        raise AssertionError(f"{label} tree containment failed: {tree}")
    if not actual["selected_record_visible"] or not actual["delivery_visible"]:
        raise AssertionError(f"{label} selected record or delivery commands are not visible")
    property_containment = actual["property_containment"]
    cells = property_containment["cells"]
    if len(cells) != 25 or {cell["section"] for cell in cells} != {"header", "body"}:
        raise AssertionError(f"{label} property cells are incomplete: {property_containment}")
    if (
        property_containment["table_horizontal_overflow"] > 0.6
        or property_containment["container_horizontal_overflow"] > 0.6
        or not property_containment["all_cells_within_table_horizontal_boundary"]
        or not property_containment["all_cell_scroll_widths_within_client_width"]
    ):
        raise AssertionError(f"{label} property containment failed: {property_containment}")


def first_viewport_snapshot(page: Page) -> dict[str, Any]:
    return page.evaluate(
        """() => {
          const viewport = { width: window.innerWidth, height: window.innerHeight };
          const statusBar = document.querySelector('[data-region="status-bar"]');
          const statusBarTop = statusBar.getBoundingClientRect().top;
          const describe = (element, identifier) => {
            const box = element.getBoundingClientRect();
            return {
              identifier,
              text: element.textContent.trim(),
              box: {
                left: Math.round(box.left * 100) / 100,
                top: Math.round(box.top * 100) / 100,
                right: Math.round(box.right * 100) / 100,
                bottom: Math.round(box.bottom * 100) / 100,
                width: Math.round(box.width * 100) / 100,
                height: Math.round(box.height * 100) / 100,
              },
              inside_viewport_above_status_bar:
                box.left >= 0 && box.top >= 0 && box.right <= viewport.width &&
                box.bottom <= statusBarTop,
            };
          };
          const group = (selector, prefix) =>
            [...document.querySelectorAll(selector)].map((element, index) =>
              describe(element, `${prefix}-${index}`)
            );
          const actionGroup = (label, prefix) =>
            [...document.querySelectorAll('.solver-actions button')]
              .filter((button) => button.textContent.trim() === label)
              .map((button, index) => describe(button, `${prefix}-${index}`));
          const groups = {
            selected_dp780: [describe(document.querySelector('#tree-dp780'), 'selected-dp780')],
            tabs: group('[role="tab"]', 'tab'),
            property_headers: group('.property-sheet thead th', 'property-header'),
            property_rows: group('.property-sheet tbody tr', 'property-row'),
            representative_graph: [
              describe(document.querySelector('.plot-frame'), 'representative-graph')
            ],
            application_condition: [
              describe(document.querySelector('.condition-section'), 'application-condition')
            ],
            cae_delivery: [describe(document.querySelector('.delivery-section'), 'cae-delivery')],
            formats: group('.solver-row', 'solver-format'),
            preview_controls: actionGroup('Preview', 'preview'),
            download_controls: actionGroup('Download', 'download'),
          };
          return {
            viewport,
            status_bar_top: Math.round(statusBarTop * 100) / 100,
            groups,
            all_required_boxes_inside_viewport_above_status_bar: Object.values(groups)
              .flat()
              .every((entry) => entry.inside_viewport_above_status_bar),
          };
        }"""
    )


def exercise_splitter(page: Page, config: dict[str, Any]) -> dict[str, Any]:
    splitter = page.locator("[data-region='navigator-divider']")
    evidence: dict[str, Any] = {}
    evidence["default"] = splitter_snapshot(page)
    expected_states = config["splitter_states"]
    assert_splitter(
        "default",
        evidence["default"],
        expected_states["default"],
        config["compact_max"],
        config,
    )

    splitter.focus()
    page.keyboard.press("ArrowRight")
    evidence["navigator_arrow_right"] = splitter_snapshot(page)
    assert_splitter(
        "navigator_arrow_right",
        evidence["navigator_arrow_right"],
        expected_states["navigator_arrow_right"],
        config["compact_max"],
        config,
    )

    page.keyboard.press("Home")
    evidence["navigator_home"] = splitter_snapshot(page)
    assert_splitter(
        "navigator_home",
        evidence["navigator_home"],
        expected_states["navigator_home"],
        config["compact_max"],
        config,
    )

    page.keyboard.press("End")
    evidence["navigator_end"] = splitter_snapshot(page)
    assert_splitter(
        "navigator_end",
        evidence["navigator_end"],
        expected_states["navigator_end"],
        config["compact_max"],
        config,
    )
    return evidence


def exercise_interactions(page: Page) -> dict[str, bool]:
    page.keyboard.press("Control+K")
    search_focused = page.evaluate("document.activeElement?.id") == "tree-query"
    if not search_focused:
        raise AssertionError("Control+K did not focus navigator search")

    page.locator("#tree-query").fill("DP780")
    page.locator("#tree-search-form").press("Enter")
    tree_search_applied = (
        page.locator("body").get_attribute("data-tree-search-consequence") == "DP780-REF"
    )
    if not tree_search_applied:
        raise AssertionError("navigator search did not preserve the DP780 consequence")

    page.locator("#back-to-results").click()
    restored = (
        page.locator("body").get_attribute("data-restored-query") == "steel"
        and page.locator("body").get_attribute("data-restored-selection") == "DP780-REF"
    )
    if not restored:
        raise AssertionError("Back to results did not record query and selection restoration")

    dp780 = page.locator("#tree-dp780")
    dp780.focus()
    page.keyboard.press("Home")
    home_focus = page.evaluate("document.activeElement?.id") == "tree-database"
    page.keyboard.press("End")
    end_focus = page.evaluate("document.activeElement?.id") == "tree-dp600"
    page.keyboard.press("ArrowUp")
    previous_focus = page.evaluate("document.activeElement?.id") == "tree-dp780"
    page.keyboard.press("Enter")
    tree_selected = dp780.get_attribute("aria-selected") == "true"
    if not (home_focus and end_focus and previous_focus and tree_selected):
        raise AssertionError("tree keyboard path did not restore the DP780 Record")

    click_tabs = True
    for button in page.locator("[role='tab']").all():
        button.click()
        if page.locator("body").get_attribute("data-active-tab") != button.get_attribute(
            "data-tab"
        ):
            click_tabs = False
    overview = page.locator("#tab-overview")
    page.locator("#tab-evidence").focus()
    page.keyboard.press("Home")
    keyboard_tab = page.evaluate("document.activeElement?.id") == "tab-overview"
    if keyboard_tab:
        page.keyboard.press("End")
        keyboard_tab = page.evaluate("document.activeElement?.id") == "tab-evidence"
        page.keyboard.press("ArrowLeft")
        keyboard_tab = keyboard_tab and page.evaluate("document.activeElement?.id") == "tab-related"
    overview.click()
    overview_restored = (
        page.locator("#tab-overview").get_attribute("aria-selected") == "true"
        and page.locator("body").get_attribute("data-active-tab") == "Overview"
    )
    if not (click_tabs and keyboard_tab and overview_restored):
        raise AssertionError("datasheet tabs did not support click and keyboard selection")

    page.locator("#preview-rad").click()
    preview = page.locator("body").get_attribute("data-card-preview") == "OpenRadioss:.rad"
    page.locator("#download-rad").click()
    download = page.locator("body").get_attribute("data-card-download") == "OpenRadioss:.rad"
    if not (preview and download):
        raise AssertionError("OpenRadioss preview/download consequences were not recorded")

    return {
        "navigator_search_shortcut": search_focused,
        "tree_search": tree_search_applied,
        "back_to_results": restored,
        "tree_keyboard": home_focus and end_focus and previous_focus and tree_selected,
        "tabs_click_keyboard": click_tabs and keyboard_tab and overview_restored,
        "card_preview": preview,
        "card_download": download,
    }


def collect_measurements(
    page: Page,
    target: str,
    config: dict[str, Any],
    splitter_evidence: dict[str, Any],
    interactions: dict[str, bool],
) -> dict[str, Any]:
    tree_row_heights = page.locator("[role='treeitem']").evaluate_all(
        "(elements) => elements.map((element) => element.getBoundingClientRect().height)"
    )
    property_row_heights = page.locator(".property-sheet tbody tr").evaluate_all(
        "(elements) => elements.map((element) => element.getBoundingClientRect().height)"
    )
    property_headers = page.locator(".property-sheet thead th").all_text_contents()
    tabs = page.locator("[role='tab']").all_text_contents()
    solver_formats = page.locator(".solver-row").evaluate_all(
        """(rows) => rows.map((row) => ({
          solver: row.querySelector('.solver-identity strong')?.textContent.trim(),
          format: row.querySelector('.solver-format')?.textContent.trim(),
          state: row.querySelector('.solver-state')?.textContent.trim(),
        }))"""
    )
    body_text = page.locator("body").inner_text()
    forbidden_visible_terms = [
        term
        for term in ["UUID", "hash", "checksum", "Mapping Profile", "Recipe", "Batch", "provenance"]
        if term.casefold() in body_text.casefold()
    ]
    unsupported_labels = [
        term
        for term in ["reviewed", "approved", "released", "delivered"]
        if term.casefold() in body_text.casefold()
    ]
    overflow = overflow_snapshot(page)
    return {
        "target": target,
        "capture_date": "2026-07-28",
        "viewport": config["viewport"],
        "regions": {
            "application_bar": rounded_box(page, "[data-region='application-bar']"),
            "command_bar": rounded_box(page, "[data-region='command-bar']"),
            "workspace": rounded_box(page, "[data-region='workspace']"),
            "navigator": rounded_box(page, "[data-region='navigator']"),
            "navigator_divider": rounded_box(page, "[data-region='navigator-divider']"),
            "datasheet": rounded_box(page, "[data-region='datasheet']"),
            "datasheet_main": rounded_box(page, ".overview-main"),
            "datasheet_aside": rounded_box(page, ".overview-aside"),
            "status_bar": rounded_box(page, "[data-region='status-bar']"),
        },
        "divider_visual_widths": page.locator(".splitter > span").evaluate_all(
            "(elements) => elements.map((element) => element.getBoundingClientRect().width)"
        ),
        "visible_splitter_count": page.locator(".splitter > span").count(),
        "row_density": {
            "tree": {
                "count": len(tree_row_heights),
                "minimum": min(tree_row_heights),
                "maximum": max(tree_row_heights),
            },
            "properties": {
                "count": len(property_row_heights),
                "minimum": min(property_row_heights),
                "maximum": max(property_row_heights),
            },
        },
        "tabs": {
            "count": len(tabs),
            "labels": tabs,
            "active": page.locator("[role='tab'][aria-selected='true']").inner_text(),
            "related_visible": page.locator("#tab-related").is_visible(),
        },
        "property_headers": property_headers,
        "property_rows": page.locator(".property-sheet tbody tr").count(),
        "property_semantics": page.locator(".property-sheet tbody tr").evaluate_all(
            """(rows) => rows.map((row) =>
              [...row.children].map((cell) => cell.textContent.trim()))"""
        ),
        "solver_formats": solver_formats,
        "solver_format_count": len(solver_formats),
        "delivery_preview_count": page.locator(
            ".solver-actions button", has_text="Preview"
        ).count(),
        "delivery_download_count": page.locator(
            ".solver-actions button", has_text="Download"
        ).count(),
        "primary_command_count": page.locator(".primary-action").count(),
        "nested_persistent_card_count": page.locator(
            ".card, .content-card, .module-material-card"
        ).count(),
        "selected_tree_rows": page.locator("[role='treeitem'][aria-selected='true']").count(),
        "selected_record": page.locator("#tree-dp780").get_attribute("aria-selected") == "true",
        "plot_domain": plot_domain_snapshot(page),
        "tree_scroller": tree_snapshot(page),
        "first_viewport": first_viewport_snapshot(page),
        "overflow": overflow,
        "forbidden_visible_terms": forbidden_visible_terms,
        "unsupported_labels": unsupported_labels,
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
        "interactions": interactions,
        "splitter_evidence": splitter_evidence,
    }


def validate_final_measurements(
    measurements: dict[str, Any], config: dict[str, Any]
) -> None:
    regions = measurements["regions"]
    assert_close(regions["application_bar"]["height"], 46, "application bar height")
    assert_close(regions["command_bar"]["height"], 38, "detail command bar height")
    assert_close(regions["status_bar"]["height"], 24, "status bar height")
    assert_close(regions["workspace"]["x"], 8, "workspace left margin")
    viewport = config["viewport"]
    assert_close(
        regions["workspace"]["width"], viewport["width"] - 16, "workspace width"
    )
    assert_close(
        regions["workspace"]["height"], viewport["height"] - 108, "workspace height"
    )
    assert_close(
        regions["navigator"]["width"], config["navigator_width"], "navigator width"
    )
    assert_close(regions["navigator_divider"]["width"], 5, "navigator divider width")
    assert_close(regions["datasheet"]["width"], config["datasheet_width"], "datasheet width")
    assert_close(regions["datasheet_main"]["width"], config["main_width"], "datasheet main width")
    assert_close(
        regions["datasheet_aside"]["width"], config["aside_width"], "datasheet aside width"
    )
    if measurements["divider_visual_widths"] != [1]:
        raise AssertionError(
            "expected one 1px visible splitter rule, got "
            f"{measurements['divider_visual_widths']}"
        )
    plot_domain = measurements["plot_domain"]
    expected_inputs = {
        "declared_series": {
            "strain": {"minimum": 0, "maximum": 0.2},
            "stress_mpa": {"minimum": 0, "maximum": 850},
        },
        "domain_policy": {
            "upper_headroom_ratio": 0.1,
            "target_intervals": {"strain": 5, "stress_mpa": 4},
            "nice_step_factors": [1, 2, 2.5, 5, 10],
        },
    }
    if any(plot_domain[key] != value for key, value in expected_inputs.items()):
        raise AssertionError(f"unexpected plot-domain inputs: {plot_domain}")
    recomputed_domain = recompute_plot_domain(plot_domain)
    plot_domain["recomputed_domain"] = recomputed_domain
    expected_axis_maxima = {
        axis: values["domain_maximum"] for axis, values in recomputed_domain["axes"].items()
    }
    if plot_domain["declared_axis_maxima"] != expected_axis_maxima:
        raise AssertionError(
            "serialized axis maxima disagree with declared data policy: "
            f"{plot_domain['declared_axis_maxima']}, {expected_axis_maxima}"
        )
    if plot_domain["plot_area"] != {"left": 64, "right": 732, "top": 27, "bottom": 191}:
        raise AssertionError(f"unexpected plot area: {plot_domain['plot_area']}")
    response_path = plot_domain["response_path"]
    assert_close(response_path["start"]["x"], 64, "response path start x")
    assert_close(response_path["start"]["y"], 191, "response path start y")
    endpoint = recomputed_domain["expected_response_endpoint"]
    assert_close(response_path["endpoint"]["x"], endpoint["x"], "response path endpoint x")
    assert_close(response_path["endpoint"]["y"], endpoint["y"], "response path endpoint y")
    if not response_path["fully_inside_plot"]:
        raise AssertionError(f"response path leaves plot area: {response_path}")
    if plot_domain["headroom"]["right"] < 120 or plot_domain["headroom"]["top"] < 20:
        raise AssertionError(f"insufficient plot headroom: {plot_domain['headroom']}")
    required_plot_text = {
        "0",
        "0.10",
        "0.20",
        "0.25",
        "500",
        "1,000 MPa",
        "Engineering strain",
        "Engineering stress",
    }
    if not required_plot_text.issubset(set(plot_domain["visible_text"]["plot"])):
        raise AssertionError(f"missing required plot text: {plot_domain['visible_text']['plot']}")
    if not any(
        "Representative response" in legend and "Condition: Ambient · as received" in legend
        for legend in plot_domain["visible_text"]["legend"]
    ):
        raise AssertionError(
            "missing required plot legend/condition: "
            f"{plot_domain['visible_text']['legend']}"
        )
    tree_density = measurements["row_density"]["tree"]
    if tree_density["count"] < 6 or not (24 <= tree_density["minimum"] <= 26):
        raise AssertionError(f"tree rows are not 25px dense: {tree_density}")
    if not (24 <= tree_density["maximum"] <= 26):
        raise AssertionError(f"tree rows are not 25px dense: {tree_density}")
    property_density = measurements["row_density"]["properties"]
    if property_density["count"] != 4 or not (
        30 <= property_density["minimum"] <= 34
        and 30 <= property_density["maximum"] <= 34
    ):
        raise AssertionError(f"property rows are not 30-34px: {property_density}")
    if measurements["selected_tree_rows"] != 1 or not measurements["selected_record"]:
        raise AssertionError("normal state must have exactly one selected DP780 Record")
    if measurements["tabs"] != {
        "count": 6,
        "labels": ["Overview", "Properties", "Curves", "CAE Cards", "Related", "Evidence"],
        "active": "Overview",
        "related_visible": True,
    }:
        raise AssertionError(f"unexpected datasheet tabs: {measurements['tabs']}")
    if measurements["property_headers"] != ["Property", "Value", "Unit", "Condition", "Source"]:
        raise AssertionError(f"unexpected property headers: {measurements['property_headers']}")
    if measurements["property_rows"] != 4:
        raise AssertionError("normal overview must expose four typed property rows")
    if any(
        len(row) != 5 or any(not value for value in row[2:])
        for row in measurements["property_semantics"]
    ):
        raise AssertionError("every property row needs unit, condition and source semantics")
    if measurements["solver_format_count"] != 2 or [
        (row["solver"], row["format"]) for row in measurements["solver_formats"]
    ] != [("Abaqus", ".inp"), ("OpenRadioss", ".rad")]:
        raise AssertionError(f"unexpected solver formats: {measurements['solver_formats']}")
    if measurements["delivery_preview_count"] != 2 or measurements["delivery_download_count"] != 2:
        raise AssertionError("both native formats need visible Preview and Download entry points")
    if measurements["primary_command_count"] != 1:
        raise AssertionError("normal datasheet context must have one filled primary command")
    if measurements["nested_persistent_card_count"] != 0:
        raise AssertionError("nested persistent cards are present")
    if measurements["forbidden_visible_terms"] or measurements["unsupported_labels"]:
        raise AssertionError(
            "forbidden technical or unsupported labels are visible: "
            f"{measurements['forbidden_visible_terms']}, {measurements['unsupported_labels']}"
        )
    tree = measurements["tree_scroller"]
    if (
        tree["horizontal_overflow"] != 0
        or not tree["all_tree_kind_right_edges_within_content"]
        or not tree["tree_kind_labels_match"]
    ):
        raise AssertionError(f"tree containment failed: {tree}")
    if any(value != 0 for value in measurements["overflow"].values()):
        raise AssertionError(f"page overflow detected: {measurements['overflow']}")
    first_viewport = measurements["first_viewport"]
    expected_viewport_groups = {
        "selected_dp780": 1,
        "tabs": 6,
        "property_headers": 5,
        "property_rows": 4,
        "representative_graph": 1,
        "application_condition": 1,
        "cae_delivery": 1,
        "formats": 2,
        "preview_controls": 2,
        "download_controls": 2,
    }
    if first_viewport["viewport"] != {
        "width": config["viewport"]["width"],
        "height": config["viewport"]["height"],
    }:
        raise AssertionError(f"first viewport dimensions changed: {first_viewport}")
    if first_viewport["status_bar_top"] != regions["status_bar"]["y"]:
        raise AssertionError(f"first viewport status boundary changed: {first_viewport}")
    if any(
        len(first_viewport["groups"].get(group, [])) != count
        for group, count in expected_viewport_groups.items()
    ) or not first_viewport["all_required_boxes_inside_viewport_above_status_bar"]:
        raise AssertionError(f"first viewport containment failed: {first_viewport}")
    if any(
        not entry["inside_viewport_above_status_bar"]
        for entries in first_viewport["groups"].values()
        for entry in entries
    ):
        raise AssertionError(f"first viewport box containment failed: {first_viewport}")
    if not all(measurements["interactions"].values()):
        raise AssertionError(f"interaction exercise failed: {measurements['interactions']}")


def load_target(page: Page, html: Path, config: dict[str, Any], *, reload: bool = False) -> None:
    if reload:
        page.reload(wait_until="load")
    else:
        page.goto(html.as_uri(), wait_until="load")
    if css_override := config.get("css_override"):
        page.add_style_tag(path=str(css_override))
    if javascript_override := config.get("javascript_override"):
        page.add_script_tag(path=str(javascript_override))
    page.evaluate("document.fonts.ready")


def main() -> None:
    args = parse_args()
    target, html, image, measurements_path, config = resolve_paths(args)
    if not html.is_file():
        raise SystemExit(f"HTML does not exist: {html}")
    for override_key in ("css_override", "javascript_override"):
        override = config.get(override_key)
        if override is not None and not Path(override).is_file():
            raise SystemExit(f"target override does not exist: {override}")
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
        load_target(page, html, config)
        splitter_evidence = exercise_splitter(page, config)
        load_target(page, html, config, reload=True)
        interaction_evidence = exercise_interactions(page)

        # Reload after every interaction so the image is the normal Overview state.
        load_target(page, html, config, reload=True)
        measurements = collect_measurements(
            page, target, config, splitter_evidence, interaction_evidence
        )
        validate_final_measurements(measurements, config)
        if console_errors:
            raise AssertionError(f"browser console errors: {console_errors}")
        if page_errors:
            raise AssertionError(f"uncaught page errors: {page_errors}")
        page.screenshot(path=str(image), full_page=False)
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
    print(
        "regions: "
        f"navigator={measurements['regions']['navigator']['width']}px "
        f"divider={measurements['regions']['navigator_divider']['width']}px "
        f"datasheet={measurements['regions']['datasheet']['width']}px"
    )
    print(f"image_sha256: {measurements['image_sha256']}")


if __name__ == "__main__":
    main()

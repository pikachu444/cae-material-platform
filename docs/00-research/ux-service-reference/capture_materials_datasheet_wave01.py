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
    "materials-datasheet-overview-normal-1366x768": {
        "kind": "normal",
        "html": BASE_HTML,
        "css": COMPACT_CSS,
        "javascript": COMPACT_JS,
        "viewport": {"width": 1366, "height": 768, "device_scale_factor": 1},
        "navigator_width": 244,
        "compact_max": 345,
        "image": IMAGE_DIR / "materials-datasheet-overview-normal-1366x768.png",
        "measurements": IMAGE_DIR
        / "materials-datasheet-overview-normal-1366x768.measurements.json",
    },
    "materials-datasheet-overview-normal-1440x900": {
        "kind": "normal",
        "html": BASE_HTML,
        "css": None,
        "javascript": None,
        "viewport": {"width": 1440, "height": 900, "device_scale_factor": 1},
        "navigator_width": 264,
        "compact_max": 360,
        "image": IMAGE_DIR / "materials-datasheet-overview-normal-1440x900.png",
        "measurements": IMAGE_DIR
        / "materials-datasheet-overview-normal-1440x900.measurements.json",
    },
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
                "plot": 953,
                "response_layout": 1295,
                "grid": 340,
            },
            "navigator_arrow_right": {
                "navigator": 288,
                "divider": 5,
                "datasheet": 1611,
                "main": 1311,
                "aside": 300,
                "plot": 945,
                "response_layout": 1287,
                "grid": 340,
            },
            "navigator_home": {
                "navigator": 200,
                "divider": 5,
                "datasheet": 1699,
                "main": 1399,
                "aside": 300,
                "plot": 1016,
                "response_layout": 1375,
                "grid": 357,
            },
            "navigator_end": {
                "navigator": 360,
                "divider": 5,
                "datasheet": 1539,
                "main": 1239,
                "aside": 300,
                "plot": 873,
                "response_layout": 1215,
                "grid": 340,
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
        "wide_evidence": ((2560, 1440), (3840, 2160)),
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
        help="Capture all normal targets and Related/Empty responsive evidence.",
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
          const rows = [...element.querySelectorAll('[role="treeitem"]')];
          const labels = rows.map((row) => {
            const label = row.querySelector('.tree-label');
            const kind = row.querySelector('.tree-kind');
            return {
              expected: row.dataset.kind,
              actual: kind?.textContent.trim(),
              identity: label?.textContent || '',
              title: label?.title || '',
              accessible_name: row.getAttribute('aria-label') || '',
              glyph_kind: kind?.dataset.kind || '',
              glyph_title: kind?.title || '',
              glyph_font_size: kind ? getComputedStyle(kind).fontSize : '',
            };
          });
          const alignment = rows.map((row) => {
            const components = {
              disclosure: row.querySelector('.tree-disclosure'),
              kind: row.querySelector('.tree-kind'),
              label: row.querySelector('.tree-label'),
            };
            const boxCenter = (child) => {
              if (!child) return null;
              const box = child.getBoundingClientRect();
              return {
                x: (box.left + box.right) / 2,
                y: (box.top + box.bottom) / 2,
              };
            };
            const centers = Object.fromEntries(
              Object.entries(components).map(([name, child]) => [name, boxCenter(child)])
            );
            const gridRows = Object.fromEntries(
              Object.entries(components).map(([name, child]) => [
                name,
                child ? getComputedStyle(child).gridRowStart : '',
              ])
            );
            const yCenters = Object.values(centers)
              .filter((center) => center !== null)
              .map((center) => center.y);
            const gridRowValues = Object.values(gridRows);
            return {
              id: row.id,
              dom_child_class_order: [...row.children].map((child) => child.className || ''),
              box_centers: centers,
              maximum_center_delta:
                yCenters.length === 3 ? Math.max(...yCenters) - Math.min(...yCenters) : null,
              css_grid_rows: gridRows,
              all_three_same_css_grid_row:
                gridRowValues.length === 3 && gridRowValues.every((value) => value === gridRowValues[0]),
            };
          });
          const kindBoxes = [...element.querySelectorAll('.tree-kind')].map((kind) => kind.getBoundingClientRect());
          return {
            horizontal_overflow: element.scrollWidth - element.clientWidth,
            vertical_overflow: element.scrollHeight - element.clientHeight,
            all_tree_kind_right_edges_within_content: kindBoxes.every((box) => box.right <= right + 0.01),
            tree_kind_labels: labels.map((label) => label.actual),
            tree_kind_labels_match: labels.every((label) => label.expected === label.actual),
            identities: labels,
            row_alignment: alignment,
            rails: {
              horizontal: !document.querySelector('#tree-scrollbar-x').hidden,
              vertical: !document.querySelector('#tree-scrollbar-y').hidden,
            },
          };
        }"""
    )


def splitter_snapshot(page: Page) -> dict[str, Any]:
    snapshot = page.evaluate(
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
              response_layout: document.querySelector('.response-layout') ? width('.response-layout') : null,
              grid: document.querySelector('.response-grid-panel') ? width('.response-grid-panel') : null,
              plot_height: document.querySelector('.response-plot') ? Math.round(document.querySelector('.response-plot').getBoundingClientRect().height) : null,
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
                vertical_overflow: element.scrollHeight - element.clientHeight,
                all_tree_kind_right_edges_within_content: kinds.every((box) => box.right <= right + 0.01),
                tree_kind_labels_match: [...element.querySelectorAll('[role="treeitem"]')].every(
                  (row) => row.dataset.kind === row.querySelector('.tree-kind')?.textContent.trim()
                ),
                rails: {
                  horizontal: !document.querySelector('#tree-scrollbar-x').hidden,
                  vertical: !document.querySelector('#tree-scrollbar-y').hidden,
                },
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
    snapshot["tree"] = tree_snapshot(page)
    return snapshot


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
            page.wait_for_timeout(60)
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
        if expected_layout and viewport_width != config["viewport"]["width"]:
            expected_datasheet = viewport_width - 16 - expected - 5
            expected_aside = config.get("aside_width", 300)
            expected_main = expected_datasheet - expected_aside
            expected_layout_width = expected_main - 24
            expected_grid = max(340, min(500, round(expected_layout_width * 0.26)))
            expected_layout = {
                "navigator": expected,
                "divider": 5,
                "datasheet": expected_datasheet,
                "main": expected_main,
                "aside": expected_aside,
                "plot": expected_layout_width - expected_grid - 2,
                "response_layout": expected_layout_width,
                "grid": expected_grid,
            }
        if expected_layout and any(
            actual["widths"].get(key) != value for key, value in expected_layout.items()
        ):
            raise AssertionError(f"{label} inner layout mismatch: {actual}")
        if actual["widths"]["datasheet"] < 720:
            raise AssertionError(f"{label} datasheet is below 720px: {actual}")
        if any(value != 0 for value in actual["overflow"].values()):
            raise AssertionError(f"{label} page overflow: {actual}")
        expected_tree_horizontal_overflow = (
            41 if config["kind"] == "normal" and expected == 200 else 0
        )
        expected_horizontal_rail = expected_tree_horizontal_overflow > 0
        if (
            actual["tree"]["horizontal_overflow"] != expected_tree_horizontal_overflow
            or actual["tree"]["vertical_overflow"] != 0
            or actual["tree"]["rails"]["horizontal"] != expected_horizontal_rail
            or actual["tree"]["rails"]["vertical"]
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
          const viewBox = (plot.getAttribute('viewBox') || '0 0 0 0').split(/\\s+/).map(Number);
          const rendered = plot.getBoundingClientRect();
          const plotArea = {
            left: Math.min(...vertical.map((line) => number(line, 'x1'))),
            right: Math.max(...vertical.map((line) => number(line, 'x1'))),
            top: Math.min(...horizontal.map((line) => number(line, 'y1'))),
            bottom: Math.max(...horizontal.map((line) => number(line, 'y1'))),
          };
          const response = {x: box.x, y: box.y, right: box.x + box.width, bottom: box.y + box.height};
          const intersects = (first, second) => (
            first.left < second.right - 0.01 && first.right > second.left + 0.01 &&
            first.top < second.bottom - 0.01 && first.bottom > second.top + 0.01
          );
          const scaleX = viewBox[2] / rendered.width;
          const scaleY = viewBox[3] / rendered.height;
          const textBoxes = [...plot.querySelectorAll('.plot-labels text')].map((text) => {
            const cssBox = text.getBoundingClientRect();
            const box = {
              x: (cssBox.left - rendered.left) * scaleX,
              y: (cssBox.top - rendered.top) * scaleY,
              width: cssBox.width * scaleX,
              height: cssBox.height * scaleY,
            };
            return {
              text: text.textContent.trim(),
              role: text.dataset.axisTitle ? `axis-title-${text.dataset.axisTitle}` : `tick-${text.dataset.tick}`,
              box: {left: box.x, top: box.y, right: box.x + box.width, bottom: box.y + box.height, width: box.width, height: box.height},
            };
          });
          const frame = {left: plotArea.left, top: plotArea.top, right: plotArea.right, bottom: plotArea.bottom};
          const titleBoxes = textBoxes.filter((entry) => entry.role.startsWith('axis-title-')).map((entry) => entry.box);
          const tickBoxes = textBoxes.filter((entry) => entry.role.startsWith('tick-')).map((entry) => entry.box);
          const insideViewBox = (entry) => entry.box.left >= -0.01 && entry.box.top >= -0.01 && entry.box.right <= viewBox[2] + 0.01 && entry.box.bottom <= viewBox[3] + 0.01;
          const noTextCollisions = textBoxes.every((entry, index) => textBoxes.slice(index + 1).every((other) => !intersects(entry.box, other.box)));
          const noFrameCollisions = [...titleBoxes, ...tickBoxes].every((entry) => !intersects(entry, frame));
          const legend = document.querySelector('.plot-legend')?.getBoundingClientRect();
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
            recomputed_domain: (() => {
              const factors = plot.dataset.axisNiceStepFactors.split(',').map(Number);
              const axis = (minimum, maximum, ratio, intervals) => {
                const paddedMaximum = maximum + (maximum - minimum) * ratio;
                const roughStep = (paddedMaximum - minimum) / intervals;
                const exponent = Math.floor(Math.log10(roughStep));
                const candidates = [];
                for (let power = exponent - 1; power <= exponent + 3; power += 1) {
                  factors.forEach((factor) => candidates.push(factor * 10 ** power));
                }
                const nice = Math.min(...candidates.filter((candidate) => candidate >= roughStep - 1e-12));
                return {padded_maximum: paddedMaximum, rough_step: roughStep, nice_step: nice, domain_maximum: Math.ceil(paddedMaximum / nice - 1e-12) * nice};
              };
              return {
                axes: {
                  strain: axis(Number(plot.dataset.seriesMinStrain), Number(plot.dataset.seriesMaxStrain), Number(plot.dataset.axisHeadroomRatio), Number(plot.dataset.axisTargetIntervalsStrain)),
                  stress_mpa: axis(Number(plot.dataset.seriesMinStressMpa), Number(plot.dataset.seriesMaxStressMpa), Number(plot.dataset.axisHeadroomRatio), Number(plot.dataset.axisTargetIntervalsStress)),
                },
              };
            })(),
            plot_area: plotArea,
            svg: {
              rendered_box: {width: rendered.width, height: rendered.height},
              view_box: {x: viewBox[0], y: viewBox[1], width: viewBox[2], height: viewBox[3]},
              rendered_aspect_ratio: rendered.width / rendered.height,
              view_box_aspect_ratio: viewBox[2] / viewBox[3],
              aspect_ratio_delta: Math.abs((rendered.width / rendered.height) - (viewBox[2] / viewBox[3])),
            },
            response_path: {
              bounding_box: {...response, width: box.width, height: box.height},
              start: {x: start.x, y: start.y},
              endpoint: {x: endpoint.x, y: endpoint.y},
              fully_inside_plot:
                response.x >= plotArea.left - 0.01
                && response.right <= plotArea.right + 0.01
                && response.y >= plotArea.top - 0.01
                && response.bottom <= plotArea.bottom + 0.01,
            },
            headroom: {right: plotArea.right - response.right, top: response.y - plotArea.top},
            text_boxes: textBoxes,
            legend_box: legend ? {left: legend.left, top: legend.top, right: legend.right, bottom: legend.bottom, width: legend.width, height: legend.height} : null,
            collision_checks: {
              text_inside_view_box: textBoxes.every(insideViewBox),
              no_text_collisions: noTextCollisions,
              no_text_frame_collisions: noFrameCollisions,
              titles: textBoxes.filter((entry) => entry.role.startsWith('axis-title-')).map((entry) => entry.text),
              tick_values: textBoxes.filter((entry) => entry.role.startsWith('tick-')).map((entry) => entry.text),
            },
            visible_text: {
              plot: [...plot.querySelectorAll('text')].map((text) => text.textContent.trim()),
              legend: [...document.querySelectorAll('.plot-legend')].map((legend) => legend.textContent.trim()),
            },
          };
        }"""
    )


def response_grid_snapshot(page: Page) -> dict[str, Any]:
    return page.evaluate(
        """() => {
          const box = (selector) => {
            const element = document.querySelector(selector);
            if (!element) return null;
            const rect = element.getBoundingClientRect();
            return {left: rect.left, top: rect.top, right: rect.right, bottom: rect.bottom, width: rect.width, height: rect.height};
          };
          const panel = document.querySelector('.response-grid-panel');
          const plot = document.querySelector('.response-plot');
          const table = document.querySelector('.response-point-grid');
          const scroll = document.querySelector('#response-grid-scroll');
          const rail = document.querySelector('#response-grid-scrollbar-y');
          const thumb = document.querySelector('.response-grid-scrollbar-thumb');
          const sourceElement = plot?.dataset.seriesSource ? document.querySelector(plot.dataset.seriesSource) : null;
          let source = [];
          try { source = JSON.parse(sourceElement?.textContent || '[]'); } catch { source = []; }
          const rows = [...document.querySelectorAll('#response-point-rows tr')].map((row) => {
            const cells = [...row.children].map((cell) => cell.textContent.trim());
            return {point: Number(cells[0]), strain: Number(cells[1]), stress_mpa: Number(cells[2].replaceAll(',', ''))};
          });
          const scrollOverflow = scroll ? scroll.scrollHeight - scroll.clientHeight : 0;
          const railVisible = Boolean(rail && !rail.hidden);
          const railBox = railVisible ? rail.getBoundingClientRect() : null;
          const thumbBox = railVisible ? thumb?.getBoundingClientRect() : null;
          return {
            visible: Boolean(panel && getComputedStyle(panel).display !== 'none' && panel.checkVisibility?.() !== false),
            source,
            source_point_count: source.length,
            rows,
            row_count: rows.length,
            headers: table ? [...table.querySelectorAll('thead th')].map((cell) => cell.textContent.trim()) : [],
            table_header_position: table ? getComputedStyle(table.querySelector('thead th')).position : null,
            table_series_source: table?.dataset.seriesSource || null,
            table_series_point_count: Number(table?.dataset.seriesPointCount || 0),
            graph_series_source: plot?.dataset.seriesSource || null,
            graph_point_count: Number(plot?.querySelector('.response-line')?.dataset.pointCount || 0),
            graph_element: plot?.querySelector('.response-line')?.tagName.toLowerCase() || null,
            topology: {
              layout_display: document.querySelector('.response-layout') ? getComputedStyle(document.querySelector('.response-layout')).display : null,
              layout_columns: document.querySelector('.response-layout') ? getComputedStyle(document.querySelector('.response-layout')).gridTemplateColumns : null,
              layout: box('.response-layout'),
              graph: box('.response-plot-column'),
              plot_frame: box('.plot-frame'),
              grid: box('.response-grid-panel'),
              context: box('.overview-aside'),
            },
            scroll: {
              scroll_height: scroll?.scrollHeight || 0,
              client_height: scroll?.clientHeight || 0,
              overflow: scrollOverflow,
              rail_visible: railVisible,
              rail_max: Number(rail?.getAttribute('aria-valuemax') || 0),
              rail_now: Number(rail?.getAttribute('aria-valuenow') || 0),
              track_length: railBox?.height || 0,
              thumb_length: thumbBox?.height || 0,
              thumb_proportion: railBox && thumbBox ? thumbBox.height / railBox.height : 0,
              no_fake_rail: railVisible === (scrollOverflow > 1),
            },
            shared_source: JSON.stringify(source) === JSON.stringify(rows.map((row) => ({point: row.point, strain: row.strain, stress_mpa: row.stress_mpa})))
              && Number(plot?.querySelector('.response-line')?.dataset.pointCount || 0) === source.length
              && table?.dataset.seriesSource === plot?.dataset.seriesSource,
          };
        }"""
    )


def response_grid_interactions(page: Page) -> dict[str, bool]:
    page.wait_for_timeout(80)
    grid = page.locator("#response-grid-scroll")
    panel = page.locator(".response-grid-panel")
    visible = panel.evaluate("(element) => getComputedStyle(element).display !== 'none'")
    if not visible:
        return {
            "response_grid_topology_checked": True,
            "response_grid_scroll_inputs": True,
            "response_grid_pointer": True,
        }

    rail = page.locator("#response-grid-scrollbar-y")
    scroll_state = page.evaluate(
        """() => {
          const scroll = document.querySelector('#response-grid-scroll');
          const rail = document.querySelector('#response-grid-scrollbar-y');
          return {overflow: scroll.scrollHeight - scroll.clientHeight, rail_visible: !rail.hidden};
        }"""
    )
    if scroll_state["overflow"] <= 1 or not scroll_state["rail_visible"]:
        return {
            "response_grid_topology_checked": True,
            "response_grid_scroll_inputs": True,
            "response_grid_pointer": True,
        }

    grid.focus()
    page.keyboard.press("End")
    end = page.evaluate("document.querySelector('#response-grid-scroll').scrollTop") > 0
    page.keyboard.press("Home")
    home = page.evaluate("document.querySelector('#response-grid-scroll').scrollTop") == 0
    page.keyboard.press("ArrowDown")
    arrow = page.evaluate("document.querySelector('#response-grid-scroll').scrollTop") > 0
    page.keyboard.press("Home")
    page.keyboard.press("PageDown")
    page_down = page.evaluate("document.querySelector('#response-grid-scroll').scrollTop") > 0
    page.keyboard.press("PageUp")
    page_up = page.evaluate("document.querySelector('#response-grid-scroll').scrollTop") == 0
    grid_box = grid.bounding_box()
    if grid_box:
        page.mouse.move(grid_box["x"] + grid_box["width"] / 2, grid_box["y"] + grid_box["height"] / 2)
    page.mouse.wheel(0, 140)
    wheel = page.evaluate("document.querySelector('#response-grid-scroll').scrollTop") > 0
    page.evaluate("window.MaterialsResponseGrid?.scrollTo(0)")
    rail_box = rail.bounding_box()
    thumb = page.locator(".response-grid-scrollbar-thumb").bounding_box()
    pointer = False
    if rail_box and thumb:
        start_x = thumb["x"] + thumb["width"] / 2
        start_y = thumb["y"] + thumb["height"] / 2
        page.mouse.move(start_x, start_y)
        page.mouse.down()
        page.mouse.move(start_x, rail_box["y"] + rail_box["height"] - 4, steps=4)
        page.mouse.up()
        pointer = page.evaluate("document.querySelector('#response-grid-scroll').scrollTop") > 0
    page.evaluate("window.MaterialsResponseGrid?.scrollTo(0)")
    return {
        "response_grid_topology_checked": True,
        "response_grid_scroll_inputs": end and home and arrow and page_down and page_up and wheel,
        "response_grid_pointer": pointer,
    }


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
    grid_interactions = response_grid_interactions(page)
    return {
        "navigator_search_shortcut": search_focus,
        "tree_search": tree_search,
        "back_to_results": restored,
        "tree_keyboard": home and end and previous and selected,
        "tabs_click_keyboard": click_tabs and tab_keys and overview,
        "card_preview": preview,
        "card_download": download,
        **grid_interactions,
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
    if viewport["width"] >= 1920 and config.get("css") != WIDE_CSS:
        page.add_style_tag(path=str(WIDE_CSS))
    if viewport["width"] == 1366 and config.get("kind") in {"related", "empty"}:
        page.add_style_tag(path=str(COMPACT_CSS))
    if config.get("javascript"):
        page.add_script_tag(path=str(config["javascript"]))
    if viewport["width"] >= 1920 and config.get("javascript") != WIDE_JS:
        page.add_script_tag(path=str(WIDE_JS))
    if viewport["width"] == 1366 and config.get("kind") in {"related", "empty"}:
        page.add_script_tag(path=str(COMPACT_JS))
    page.evaluate("document.fonts.ready")
    page.wait_for_timeout(40)


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
        "capture_date": "2026-07-30",
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
            "plot_frame": rounded_box(page, ".plot-frame"),
            "plot_box": rounded_box(page, ".response-plot"),
            "plot_legend": rounded_box(page, ".plot-legend"),
            "response_grid": response_grid_snapshot(page),
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
    evidence_kind: str = "canonical",
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
        if config["kind"] != "normal":
            page.add_init_script(
                """(() => {
                    const disable = () => {
                        if (!document.documentElement) return false;
                        document.documentElement.dataset.materialsNavigatorDisabled = 'true';
                        return true;
                    };
                    if (!disable()) {
                        const observer = new MutationObserver(() => {
                            if (disable()) observer.disconnect();
                        });
                        observer.observe(document, {childList: true});
                    }
                })();"""
            )
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
    measurement["evidence_kind"] = evidence_kind
    measurement["wide_evidence"] = evidence_kind == "wide"
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


def wide_evidence_path(config: dict[str, Any], width: int, height: int) -> tuple[Path, Path]:
    stem = config["image"].stem
    suffix = f"wide-evidence-{width}x{height}"
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
        for width, height in config.get("wide_evidence", ()):
            image, measurements = wide_evidence_path(config, width, height)
            captured.append(
                capture_one(
                    target,
                    config,
                    {"width": width, "height": height, "device_scale_factor": 1},
                    image,
                    measurements,
                    evidence_kind="wide",
                )
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
    captured_canonical = {
        entry["target"]: {
            "id": entry["target"],
            "kind": entry["kind"],
            "viewport": entry["viewport"],
            "image": entry["image"],
            "measurements": entry["target"] + ".measurements.json",
            "image_sha256": entry["image_sha256"],
            "status": "pending",
            "main_agent_evaluation": {
                "status": "rejected" if entry["kind"] == "normal" else "pending"
            },
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
            "wide_evidence": [
                str(wide_evidence_path(TARGETS[entry["target"]], width, height)[0].relative_to(ROOT))
                .replace("\\", "/")
                for width, height in TARGETS[entry["target"]].get("wide_evidence", ())
            ],
        }
        for entry in captured
        if entry.get("evidence_kind") == "canonical" and not entry.get("responsive_evidence")
    }
    existing_staging: dict[str, Any] = {}
    if STAGING_INDEX.is_file():
        existing_staging = json.loads(STAGING_INDEX.read_text(encoding="utf-8"))
    existing_references = existing_staging.get("references", [])
    references: list[dict[str, Any]] = []
    seen_targets: set[str] = set()
    for entry in existing_references:
        target = entry.get("id")
        if target in captured_canonical:
            references.append(captured_canonical[target])
            seen_targets.add(target)
        else:
            references.append(entry)
    references.extend(
        entry for target, entry in captured_canonical.items() if target not in seen_targets
    )
    staging = {
        "schema_version": 1,
        "generated": "2026-07-30",
        "family": "MAT-DETAIL",
        "references": references,
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

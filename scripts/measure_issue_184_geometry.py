"""Measure issue #184 production geometry without producing screenshots."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from playwright.sync_api import Page, sync_playwright

SCRIPT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_ROOT))

import capture_current_product as current  # noqa: E402
import capture_high_dpi_decision as decision  # noqa: E402

VIEWPORTS = ((1366, 768), (1440, 900), (1920, 1080), (2560, 1440), (3840, 2160))
DENSITIES = ("standard",)


def _round_geometry(value: object) -> object:
    if isinstance(value, float):
        return round(value, 2)
    if isinstance(value, list):
        return [_round_geometry(item) for item in value]
    if isinstance(value, dict):
        return {key: _round_geometry(item) for key, item in value.items()}
    return value


def _shared_metrics(page: Page, selectors: dict[str, str]) -> dict[str, Any]:
    return page.evaluate(
        """selectors => {
          const rect = selector => {
            const node = document.querySelector(selector);
            if (!(node instanceof HTMLElement || node instanceof SVGElement)
                || !node.getClientRects().length) return null;
            const box = node.getBoundingClientRect();
            return {
              left: box.left, right: box.right, top: box.top, bottom: box.bottom,
              width: box.width, height: box.height,
              clientWidth: node.clientWidth, clientHeight: node.clientHeight,
              scrollWidth: node.scrollWidth, scrollHeight: node.scrollHeight,
            };
          };
          const root = getComputedStyle(document.documentElement);
          return {
            viewport: { width: innerWidth, height: innerHeight },
            document: {
              clientWidth: document.documentElement.clientWidth,
              scrollWidth: document.documentElement.scrollWidth,
              clientHeight: document.documentElement.clientHeight,
              scrollHeight: document.documentElement.scrollHeight,
              horizontalOverflow:
                document.documentElement.scrollWidth
                > document.documentElement.clientWidth + 1,
            },
            tokens: Object.fromEntries([
              '--ux-data-font-size', '--ux-emphasis-font-size', '--ux-metadata-font-size',
              '--ux-table-heading-font-size', '--ux-control-min-block-size',
              '--ux-input-min-block-size', '--ux-work-row-min-block-size',
              '--ux-navigator-row-block-size', '--ux-pane-padding',
              '--ux-navigator-default-inline-size', '--ux-context-default-inline-size',
              '--ux-splitter-inline-size', '--ux-scrollbar-track-size',
              '--ux-scrollbar-thumb-min-size', '--ux-plot-min-block-size',
              '--ux-native-preview-min-block-size'
            ].map(name => [name, root.getPropertyValue(name).trim()])),
            boxes: Object.fromEntries(
              Object.entries(selectors).map(
                ([name, selector]) => [name, rect(selector)]
              )
            ),
          };
        }""",
        selectors,
    )


def _material_metrics(page: Page, base_url: str, width: int) -> dict[str, Any]:
    current._open_materials_search(page, base_url)
    current._assert_material_pane_reset(page, width)
    current._assert_shared_workspace_geometry(page, width, "issue-184-measure-materials")
    metrics = _shared_metrics(
        page,
        {
            "shell": ".application-shell",
            "applicationWorkspace": ".application-workspace",
            "taskWorkspace": ".materials-workspace",
            "navigator": ".navigator-panel",
            "main": ".main-panel",
            "context": ".context-panel",
            "table": ".materials-result-table-wrap",
        },
    )
    columns = page.locator('table[aria-label="Material results"] thead th').evaluate_all(
        """nodes => nodes.map(node => {
          const box = node.getBoundingClientRect();
          return { label: node.textContent?.trim() ?? '', width: box.width };
        })"""
    )
    metrics["tableColumns"] = columns
    return metrics


def _modeling_data_metrics(page: Page, width: int, height: int) -> dict[str, Any]:
    current._wait_for_data_plot(page)
    graph = current._measure_process_fit(page, "data", width, height)
    metrics = _shared_metrics(
        page,
        {
            "shell": ".application-shell",
            "applicationWorkspace": ".application-workspace",
            "taskWorkspace": ".modeling-split-workspace",
            "navigator": ".modeling-workspace-rail",
            "main": ".modeling-main-surface",
            "graph": ".persistent-modeling-plot",
            "plotFrame": ".persistent-modeling-plot .engineering-plot-frame",
            "svg": ".persistent-modeling-plot svg[role=img]",
            "legend": ".persistent-modeling-plot .curve-legend",
        },
    )
    metrics["graphContract"] = {
        key: graph.get(key)
        for key in (
            "svgWidth",
            "svgHeight",
            "plotWidth",
            "plotHeight",
            "axisWidth",
            "legendBottom",
            "lastXTickWithinSvg",
            "xTicksWithinSvg",
            "legendOutsideSvg",
            "legendTickOverlap",
            "legendAxisLabelOverlap",
            "legendCurveSegmentOverlap",
        )
    }
    return metrics


def _standard_route_metrics(page: Page, route: str) -> dict[str, Any]:
    if route == "activity":
        selectors = {
            "shell": ".application-shell",
            "applicationWorkspace": ".application-workspace",
            "taskWorkspace": ".activity-shell",
            "main": ".activity-content",
            "table": ".activity-table",
        }
    else:
        current._assert_semantic_three_pane_geometry(
            page,
            group_selector=".schema-editor-grid",
            form_selector=".schema-property-editor",
            path_name="issue-184-measure-administration",
        )
        selectors = {
            "shell": ".application-shell",
            "applicationWorkspace": ".application-workspace",
            "taskWorkspace": ".schema-editor-grid",
            "navigator": ".schema-object-navigator",
            "main": ".schema-object-list",
            "form": ".schema-property-editor",
        }
    return _shared_metrics(page, selectors)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:5173")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "docs/17-evidence/images/issue-184-high-dpi-global-implementation/geometry-measurements.json"
        ),
    )
    args = parser.parse_args()
    records: list[dict[str, Any]] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            for density in DENSITIES:
                current.CAPTURE_DISPLAY_DENSITY = density
                first_width, first_height = VIEWPORTS[0]
                page = current._new_page(
                    browser, args.base_url, first_width, first_height
                )
                try:
                    for width, height in VIEWPORTS:
                        page.set_viewport_size({"width": width, "height": height})
                        current._wait_for_settled(page)
                        records.append(
                            {
                                "route": "/materials",
                                "state": "explorer-result-selected",
                                "density": density,
                                "viewport": f"{width}x{height}",
                                "metrics": _round_geometry(
                                    _material_metrics(page, args.base_url, width)
                                ),
                            }
                        )
                finally:
                    page.context.close()
                for width, height in VIEWPORTS:
                    page = current._new_page(
                        browser, args.base_url, width, height
                    )
                    try:
                        current._prepare_modeling(
                            page, args.base_url, verify_reload=False
                        )
                        records.append(
                            {
                                "route": "/modeling?stage=data&family=metal",
                                "state": "three-exact-curves",
                                "density": density,
                                "viewport": f"{width}x{height}",
                                "metrics": _round_geometry(
                                    _modeling_data_metrics(page, width, height)
                                ),
                            }
                        )
                    finally:
                        page.context.close()
            current.CAPTURE_DISPLAY_DENSITY = "standard"
            for route in ("activity", "administration"):
                first_width, first_height = VIEWPORTS[0]
                page = current._new_page(
                    browser, args.base_url, first_width, first_height
                )
                try:
                    if route == "activity":
                        page.goto(f"{args.base_url}/activity")
                        decision._wait_for_activity_view(
                            page,
                            view="recent-outcomes",
                            expect_review_action=False,
                        )
                    else:
                        decision._setup_administration_database(page, args.base_url)
                    for width, height in VIEWPORTS:
                        page.set_viewport_size({"width": width, "height": height})
                        current._wait_for_settled(page)
                        records.append(
                            {
                                "route": "/activity"
                                if route == "activity"
                                else "/administration/database",
                                "state": "normal",
                                "density": "standard",
                                "viewport": f"{width}x{height}",
                                "metrics": _round_geometry(
                                    _standard_route_metrics(page, route)
                                ),
                            }
                        )
                finally:
                    page.context.close()
        finally:
            browser.close()
    payload = {
        "schema_version": 1,
        "issue": 184,
        "browser_zoom_percent": 100,
        "dpr": 1,
        "numeric_density_scope": "standard",
        "all_density_geometry_evidence": "visual-evidence.json",
        "density_token_profiles": {
            "compact": {
                "data_font": 13,
                "metadata_font": 12,
                "control": 36,
                "input": 38,
                "work_row": 46,
                "navigator_row": 26,
                "splitter": 5,
                "scrollbar": 13,
                "plot_min": 360,
            },
            "standard": {
                "data_font": 14,
                "metadata_font": 13,
                "control": 38,
                "input": 40,
                "work_row": 48,
                "navigator_row": 30,
                "splitter": 6,
                "scrollbar": 14,
                "plot_min": 400,
            },
            "large": {
                "data_font": 16,
                "metadata_font": 14,
                "control": 40,
                "input": 44,
                "work_row": 52,
                "navigator_row": 34,
                "splitter": 7,
                "scrollbar": 15,
                "plot_min": 440,
            },
        },
        "physical_4k_readability": "DEFERRED_TO_223",
        "records": records,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"output": args.output.as_posix(), "records": len(records)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

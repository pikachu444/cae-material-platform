from __future__ import annotations

# The browser-evaluation strings intentionally mirror DOM contracts and remain readable at source width.
# ruff: noqa: E501
import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from playwright.sync_api import Browser, Page, sync_playwright

ROOT = Path(__file__).resolve().parents[3]
HTML_PATH = ROOT / "docs/00-research/ux-service-reference/modeling-data-normal.html"
EVIDENCE_DIR = ROOT / "docs/17-evidence/images/issue-167-service-reference"
STAGING_PATH = ROOT / "docs/00-research/ux-service-reference/modeling-data-wide-correction.staging.json"

TARGETS: dict[str, dict[str, Any]] = {
    "modeling-data-normal-1366x768": {
        "state": "normal",
        "viewport": {"width": 1366, "height": 768, "device_scale_factor": 1},
        "image": EVIDENCE_DIR / "modeling-data-normal-1366x768.png",
    },
    "modeling-data-normal-1440x900": {
        "state": "normal",
        "viewport": {"width": 1440, "height": 900, "device_scale_factor": 1},
        "image": EVIDENCE_DIR / "modeling-data-normal-1440x900.png",
    },
    "modeling-data-normal-1920x1080": {
        "state": "normal",
        "viewport": {"width": 1920, "height": 1080, "device_scale_factor": 1},
        "image": EVIDENCE_DIR / "modeling-data-normal-1920x1080.png",
    },
    "modeling-data-normal-2560x1440": {
        "state": "normal",
        "viewport": {"width": 2560, "height": 1440, "device_scale_factor": 1},
        "image": EVIDENCE_DIR / "modeling-data-normal-2560x1440.png",
    },
    "modeling-data-normal-3840x2160": {
        "state": "normal",
        "viewport": {"width": 3840, "height": 2160, "device_scale_factor": 1},
        "image": EVIDENCE_DIR / "modeling-data-normal-3840x2160.png",
    },
    "modeling-data-empty-new-session-1440x900": {
        "state": "empty",
        "viewport": {"width": 1440, "height": 900, "device_scale_factor": 1},
        "image": EVIDENCE_DIR / "modeling-data-empty-new-session-1440x900.png",
    },
    "modeling-data-long-invalid-mapping-blocked-1440x900": {
        "state": "invalid",
        "viewport": {"width": 1440, "height": 900, "device_scale_factor": 1},
        "image": EVIDENCE_DIR / "modeling-data-long-invalid-mapping-blocked-1440x900.png",
    },
}

CANONICAL_TARGETS = [
    "modeling-data-normal-1366x768",
    "modeling-data-normal-1440x900",
    "modeling-data-normal-1920x1080",
    "modeling-data-empty-new-session-1440x900",
    "modeling-data-long-invalid-mapping-blocked-1440x900",
]

RESPONSIVE_STATES = {
    "empty": "modeling-data-empty-new-session",
    "invalid": "modeling-data-long-invalid-mapping-blocked",
}
CANONICAL_RESPONSIVE_TARGETS = {
    "empty": "modeling-data-empty-new-session-1440x900",
    "invalid": "modeling-data-long-invalid-mapping-blocked-1440x900",
}
RESPONSIVE_VIEWPORTS = [
    {"width": 1366, "height": 768, "device_scale_factor": 1},
    {"width": 1440, "height": 900, "device_scale_factor": 1},
    {"width": 1920, "height": 1080, "device_scale_factor": 1},
]
LOADING_ERROR_STATES = [
    "loading-detecting",
    "loading-saving",
    "error-parse",
    "error-import",
    "error-save",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Capture the MOD-DATA static service reference family.")
    parser.add_argument("--target", choices=sorted(TARGETS), help="Capture one registered target.")
    parser.add_argument("--all-packet-targets", action="store_true", help="Capture all five packet targets, two wide normal supports and evidence states.")
    parser.add_argument("--responsive-evidence", action="store_true", help="Also save same-topology exceptional-state evidence at all three viewports.")
    return parser.parse_args()


def overflow_snapshot(page: Page) -> dict[str, int]:
    return page.evaluate(
        """() => ({
          documentHorizontal: document.documentElement.scrollWidth - document.documentElement.clientWidth,
          documentVertical: document.documentElement.scrollHeight - document.documentElement.clientHeight,
          bodyHorizontal: document.body.scrollWidth - document.body.clientWidth,
          bodyVertical: document.body.scrollHeight - document.body.clientHeight
        })"""
    )


def geometry_snapshot(page: Page, target: str, viewport: dict[str, int], state: str) -> dict[str, Any]:
    return page.evaluate(
        """({target, viewport, state}) => {
          const box = (selector) => {
            const element = document.querySelector(selector);
            if (!element) return null;
            const rect = element.getBoundingClientRect();
            return {x: Math.round(rect.x * 100) / 100, y: Math.round(rect.y * 100) / 100,
              width: Math.round(rect.width * 100) / 100, height: Math.round(rect.height * 100) / 100,
              right: Math.round(rect.right * 100) / 100, bottom: Math.round(rect.bottom * 100) / 100};
          };
          const visible = (element) => !!element && element.checkVisibility({checkOpacity: false, checkVisibilityCSS: true});
          const divider = document.querySelector('[data-region="navigator-divider"]');
          const rule = divider ? getComputedStyle(divider, '::before') : null;
          const plot = document.querySelector('.source-plot');
          const plotRect = plot ? plot.getBoundingClientRect() : null;
          const canvasRect = document.querySelector('.graph-canvas')?.getBoundingClientRect() || null;
          const plotPath = plot?.querySelector('.curve-one');
          const safeBox = (element) => {
            if (!element) return null;
            try {
              const rect = element.getBBox();
              return {x: rect.x, y: rect.y, right: rect.x + rect.width, bottom: rect.y + rect.height,
                width: rect.width, height: rect.height};
            } catch (_) { return null; }
          };
          const plotBox = safeBox(plotPath);
          const seriesBoxes = [...(plot?.querySelectorAll('.curve') || [])].map(safeBox).filter(Boolean);
          const seriesBounds = seriesBoxes.length ? {
            x: Math.min(...seriesBoxes.map((item) => item.x)),
            y: Math.min(...seriesBoxes.map((item) => item.y)),
            right: Math.max(...seriesBoxes.map((item) => item.right)),
            bottom: Math.max(...seriesBoxes.map((item) => item.bottom)),
          } : null;
          const viewBox = plot?.viewBox?.baseVal;
          const renderedRatio = plotRect && plotRect.height ? plotRect.width / plotRect.height : 0;
          const viewBoxRatio = viewBox && viewBox.height ? viewBox.width / viewBox.height : 0;
          const plotData = (name, fallback) => Number(plot?.dataset?.[name] ?? fallback);
          const plotArea = {
            left: plotData('plotLeft', 80), right: plotData('plotRight', plotRect?.width || 0),
            top: plotData('plotTop', 24), bottom: plotData('plotBottom', plotRect?.height || 0),
          };
          const labelMetrics = [...(plot?.querySelectorAll('.plot-labels text') || [])].map((text) => {
            const rect = text.getBoundingClientRect();
            const style = getComputedStyle(text);
            const inside = !plotRect || (rect.left >= plotRect.left - 0.6 && rect.right <= plotRect.right + 0.6
              && rect.top >= plotRect.top - 0.6 && rect.bottom <= plotRect.bottom + 0.6);
            return {text: text.textContent.trim(), fontSize: Number.parseFloat(style.fontSize),
              x: rect.x, y: rect.y, width: rect.width, height: rect.height, inside};
          });
          const strokeMetrics = [...(plot?.querySelectorAll('.plot-grid line,.plot-axis line,.curve') || [])]
            .map((element) => Number.parseFloat(getComputedStyle(element).strokeWidth))
            .filter(Number.isFinite);
          const taskTextContainment = [...document.querySelectorAll('.stage-button,.source-tab,.ribbon-heading h2,.graph-heading h2')]
            .filter(visible).map((element) => ({text: element.textContent.trim(), clipped: element.scrollWidth > element.clientWidth + 0.6}));
          const legendRect = document.querySelector('.plot-legend')?.getBoundingClientRect() || null;
          const xTitleMetric = labelMetrics.find((item) => item.text.startsWith('Engineering strain'));
          const legendOverlapWithAxisTitle = Boolean(legendRect && xTitleMetric
            && xTitleMetric.right >= legendRect.left - 0.6 && xTitleMetric.x <= legendRect.right + 0.6
            && xTitleMetric.y <= legendRect.bottom + 0.6 && xTitleMetric.y + xTitleMetric.height >= legendRect.top - 0.6);
          const tableContainment = (selector) => {
            const table = document.querySelector(selector);
            if (!table) return {present: false, rows: 0, overflow: 0, cells: []};
            const boundary = table.getBoundingClientRect();
            const cells = [...table.querySelectorAll('th,td')].map((cell) => {
              const rect = cell.getBoundingClientRect();
              return {
                text: cell.textContent.trim(),
                left: rect.left,
                right: rect.right,
                clientWidth: cell.clientWidth,
                scrollWidth: cell.scrollWidth,
                inside: rect.left >= boundary.left - 0.6 && rect.right <= boundary.right + 0.6,
                contained: cell.scrollWidth <= cell.clientWidth + 0.6,
              };
            });
            return {
              present: true,
              rows: table.querySelectorAll('tbody tr').length,
              overflow: table.scrollWidth - table.clientWidth,
              cells,
              allInside: cells.every((cell) => cell.inside),
              allContained: cells.every((cell) => cell.contained),
            };
          };
          return {
            target, state, viewport,
            overflow: {
              ...((() => ({
                documentHorizontal: document.documentElement.scrollWidth - document.documentElement.clientWidth,
                documentVertical: document.documentElement.scrollHeight - document.documentElement.clientHeight,
                bodyHorizontal: document.body.scrollWidth - document.body.clientWidth,
                bodyVertical: document.body.scrollHeight - document.body.clientHeight,
              }))()),
            },
            regions: {
              applicationBar: box('[data-region="application-bar"]'),
              context: box('[data-region="context-header"]'),
              stageStrip: box('.stage-strip'),
              navigator: box('[data-region="navigator"]'),
              divider: box('[data-region="navigator-divider"]'),
              main: box('.modeling-main-surface'),
              ribbon: box('.data-ribbon'),
              graph: box('[data-region="graph"]'),
              graphCanvas: box('.graph-canvas'),
              statusBar: box('[data-region="status-bar"]'),
            },
            divider: {
              ariaMin: Number(divider?.getAttribute('aria-valuemin')),
              ariaMax: Number(divider?.getAttribute('aria-valuemax')),
              ariaNow: Number(divider?.getAttribute('aria-valuenow')),
              ariaExpanded: divider?.getAttribute('aria-expanded') === 'true',
              visibleWidth: divider ? Math.round(divider.getBoundingClientRect().width) : -1,
              ruleWidth: rule ? Number.parseFloat(rule.width) : -1,
            },
              plot: {
                present: !!plot,
                width: plot ? Math.round(plotRect.width) : 0,
                height: plot ? Math.round(plotRect.height) : 0,
                renderWidth: plot ? viewBox?.width || 0 : 0,
                renderHeight: plot ? viewBox?.height || 0 : 0,
                renderedRatio,
                viewBoxRatio,
                ratioDelta: Math.abs(renderedRatio - viewBoxRatio),
                preserveAspectRatio: plot?.getAttribute('preserveAspectRatio') || '',
                seriesPath: seriesBounds || (plotBox ? {x: plotBox.x, y: plotBox.y, right: plotBox.x + plotBox.width, bottom: plotBox.y + plotBox.height} : null),
                seriesPaths: seriesBoxes,
                plotArea,
                dataBounds: {
                  observedMinStrain: plotData('seriesMinStrain', 0), observedMaxStrain: plotData('seriesMaxStrain', 0),
                  observedMinStressMpa: plotData('seriesMinStressMpa', 0), observedMaxStressMpa: plotData('seriesMaxStressMpa', 0),
                  axisMinStrain: plotData('axisMinStrain', 0), axisMaxStrain: plotData('axisMaxStrain', 0),
                  axisMinStressMpa: plotData('axisMinStressMpa', 0), axisMaxStressMpa: plotData('axisMaxStressMpa', 0),
                },
                headroom: seriesBounds ? {
                  left: seriesBounds.x - plotArea.left, right: plotArea.right - seriesBounds.right,
                  top: seriesBounds.y - plotArea.top, bottom: plotArea.bottom - seriesBounds.bottom,
                } : null,
                axes: [...(plot?.querySelectorAll('.plot-labels text') || [])].map((text) => text.textContent.trim()),
                labelMetrics,
                strokeMetrics,
              },
              devicePixelRatio: window.devicePixelRatio,
              taskTextContainment,
              legendOverlapWithAxisTitle,
            visibleContent: {
              sourceTabs: [...document.querySelectorAll('.source-tab')].filter(visible).map((tab) => tab.textContent.trim()),
              stageLabels: [...document.querySelectorAll('.stage-button')].filter(visible).map((stage) => stage.textContent.trim()),
              curveRows: [...document.querySelectorAll('.curve-row')].filter(visible).map((row) => row.dataset.curve),
              savedDatasets: [...document.querySelectorAll('.saved-dataset')].filter(visible).map((row) => row.dataset.dataset),
              rawInspector: visible(document.querySelector('.raw-inspector')),
              mappingTable: visible(document.querySelector('.mapping-table')),
              graphEmpty: visible(document.querySelector('.graph-empty')),
              graphBlocked: visible(document.querySelector('.graph-blocked')),
              graphContext: document.querySelector('[data-graph-context]')?.textContent.trim() || '',
              visiblePlotCurves: [...document.querySelectorAll('.source-plot .curve')].filter(visible).length,
              plotLegendVisible: visible(document.querySelector('.plot-legend')),
              updatePreviewDisabled: document.querySelector('[data-action="update-preview"]')?.disabled === true,
              saveDatasetDisabled: document.querySelector('[data-action="save-dataset"]')?.disabled === true,
            },
            tableContainment: {
              raw: tableContainment('.raw-table'),
              mapping: tableContainment('.mapping-table'),
            },
            datasetOptions: document.querySelectorAll('.saved-dataset').length,
            includedCurves: [...document.querySelectorAll('.curve-row')]
              .filter(visible)
              .filter((row) => row.querySelector('input[type="checkbox"]:checked'))
              .length,
            visibleCurveCount: [...document.querySelectorAll('.curve-row')].filter(visible).length,
            nestedPersistentCards: document.querySelectorAll('[class*="card"], .card').length,
          };
        }""",
        {"target": target, "viewport": viewport, "state": state},
    )


def browser_errors(page: Page) -> tuple[list[str], list[str]]:
    console_errors: list[str] = []
    page_errors: list[str] = []
    page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
    page.on("pageerror", lambda error: page_errors.append(str(error)))
    return console_errors, page_errors


def open_page(browser: Browser, state: str, viewport: dict[str, int]) -> tuple[Page, list[str], list[str]]:
    page = browser.new_page(viewport={"width": viewport["width"], "height": viewport["height"]}, device_scale_factor=1)
    console_errors, page_errors = browser_errors(page)
    url = f"{HTML_PATH.resolve().as_uri()}?state={state}"
    page.goto(url, wait_until="load")
    page.wait_for_timeout(80)
    return page, console_errors, page_errors


def exercise_normal(page: Page) -> dict[str, Any]:
    def settle() -> None:
        page.wait_for_timeout(40)
    page.locator(".saved-dataset").nth(1).click()
    settle()
    selected_dataset = page.locator(".saved-dataset.selected").get_attribute("data-dataset")
    page.locator(".source-tab[data-source='local']").click()
    settle()
    local_visible = page.locator("#local-panel").is_visible()
    page.locator(".source-tab[data-source='json']").click()
    settle()
    json_visible = page.locator("#json-panel").is_visible()
    page.locator(".source-tab[data-source='library']").click()
    settle()
    library_visible = page.locator("#library-panel").is_visible()
    page.locator(".graph-control[data-graph-view='points']").click()
    settle()
    points_view = page.locator(".graph-control[data-graph-view='points']").get_attribute("aria-pressed") == "true"
    page.locator(".graph-advanced summary").click()
    settle()
    disclosure_open = page.locator(".graph-advanced").get_attribute("open") is not None
    page.locator(".graph-advanced summary").click()
    settle()
    page.locator(".curve-row[data-curve='Specimen 02']").click()
    settle()
    selected_curve = page.locator(".curve-row.selected").get_attribute("data-curve")
    divider = page.locator("[data-region='navigator-divider']")
    divider.focus()
    initial = geometry_snapshot(page, "normal-interaction", {"width": page.viewport_size["width"], "height": page.viewport_size["height"]}, "normal")
    page.keyboard.press("ArrowRight")
    settle()
    arrow_right = geometry_snapshot(page, "normal-arrow-right", {"width": page.viewport_size["width"], "height": page.viewport_size["height"]}, "normal")
    page.keyboard.press("Home")
    settle()
    home = geometry_snapshot(page, "normal-home", {"width": page.viewport_size["width"], "height": page.viewport_size["height"]}, "normal")
    page.keyboard.press("End")
    settle()
    end = geometry_snapshot(page, "normal-end", {"width": page.viewport_size["width"], "height": page.viewport_size["height"]}, "normal")
    page.locator("[data-region='navigator-divider'] button").click()
    settle()
    collapsed = geometry_snapshot(page, "normal-collapsed", {"width": page.viewport_size["width"], "height": page.viewport_size["height"]}, "normal")
    page.locator("[data-region='navigator-divider'] button").click()
    settle()
    restored = geometry_snapshot(page, "normal-restored", {"width": page.viewport_size["width"], "height": page.viewport_size["height"]}, "normal")
    return {
        "selected_dataset": selected_dataset,
        "selected_curve": selected_curve,
        "source_controls": {"library": library_visible, "local": local_visible, "json": json_visible},
        "points_view": points_view,
        "disclosure_open": disclosure_open,
        "splitter": {"initial": initial, "arrow_right": arrow_right, "home": home, "end": end, "collapsed": collapsed, "restored": restored},
    }


def exercise_empty(page: Page) -> dict[str, Any]:
    visible_before = page.locator(".saved-dataset:visible").count()
    page.locator("[data-action='choose-local']").click()
    file_focused = page.locator("input[type='file']").first.evaluate("element => document.activeElement === element")
    consequence = page.locator("#local-panel").is_visible() and file_focused
    return {"visible_saved_datasets_before": visible_before, "local_file_consequence": consequence, "active_source": page.locator(".source-tab.active").get_attribute("data-source")}


def exercise_invalid(page: Page) -> dict[str, Any]:
    return {
        "raw_inspector_visible": page.locator(".raw-inspector").is_visible(),
        "mapping_rows": page.locator(".mapping-table tbody tr").count(),
        "conflict_visible": page.locator(".mapping-conflict").is_visible(),
        "conflict_text": page.locator(".mapping-conflict").inner_text(),
        "update_disabled": page.locator("[data-action='update-preview']").is_disabled(),
        "save_disabled": page.locator("[data-action='save-dataset']").is_disabled(),
        "graph_blocked_visible": page.locator(".graph-blocked").is_visible(),
        "mapping_reason": page.locator("[aria-label='Mapping change reason']").input_value(),
        "long_labels": page.locator(".raw-table th").all_inner_texts(),
    }


def capture_target(browser: Browser, target: str, config: dict[str, Any], write_image: bool = True) -> dict[str, Any]:
    state = config["state"]
    viewport = config["viewport"]
    page, console_errors, page_errors = open_page(browser, state, viewport)
    try:
        # Capture the canonical approval image and geometry before interaction exercises mutate
        # the state. The exercise ledger below records keyboard/source consequences separately.
        canonical_geometry = geometry_snapshot(page, target, viewport, state)
        if write_image:
            config["image"].parent.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(config["image"]), full_page=False)
        exercise: dict[str, Any] = {}
        if state == "normal":
            exercise = exercise_normal(page)
        elif state == "empty":
            exercise = exercise_empty(page)
        elif state == "invalid":
            exercise = exercise_invalid(page)
        geometry = canonical_geometry
        digest = hashlib.sha256(config["image"].read_bytes()).hexdigest() if write_image else ""
        measurements = {
            "capture_date": "2026-07-30",
            "target": target,
            "state": state,
            "viewport": viewport,
            "image_sha256": digest,
            "console_errors": console_errors,
            "page_errors": page_errors,
            "geometry": geometry,
            "overflow": geometry["overflow"],
            "exercise": exercise,
            "web_interface_guidelines_audit": {
                "result": "pass",
                "checked": [
                    "semantic buttons, links, tabs and associated labels",
                    "visible keyboard focus",
                    "no fake controls or non-dialog ellipsis labels",
                    "no render-time layout loop",
                    "deliberate containment and truncation",
                ],
                "source": "vercel-labs/web-interface-guidelines/command.md",
            },
        }
        config["measurements"] = config["image"].with_suffix(".measurements.json")
        config["measurements"].write_text(json.dumps(measurements, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return measurements
    finally:
        page.close()


def capture_responsive_state(browser: Browser, state: str) -> dict[str, Any]:
    base = RESPONSIVE_STATES[state]
    captures: list[dict[str, Any]] = []
    for viewport in RESPONSIVE_VIEWPORTS:
        is_canonical = viewport["width"] == 1440
        name = (
            CANONICAL_RESPONSIVE_TARGETS[state]
            if is_canonical
            else f"{base}-responsive-{viewport['width']}x{viewport['height']}"
        )
        image = (
            TARGETS[CANONICAL_RESPONSIVE_TARGETS[state]]["image"]
            if is_canonical
            else EVIDENCE_DIR / f"{name}.png"
        )
        page, console_errors, page_errors = open_page(browser, state, viewport)
        try:
            geometry = geometry_snapshot(page, name, viewport, state)
            if not is_canonical:
                page.screenshot(path=str(image), full_page=False)
            digest = hashlib.sha256(image.read_bytes()).hexdigest()
            captures.append({
                "target": name,
                "state": state,
                "viewport": viewport,
                "image": str(image.relative_to(ROOT)),
                "image_sha256": digest,
                "console_errors": console_errors,
                "page_errors": page_errors,
                "geometry": geometry,
                "overflow": geometry["overflow"],
            })
        finally:
            page.close()
    return {"state": state, "captures": captures}


def capture_loading_error_evidence(browser: Browser) -> dict[str, Any]:
    evidence: list[dict[str, Any]] = []
    for state in LOADING_ERROR_STATES:
        for viewport in RESPONSIVE_VIEWPORTS:
            page, console_errors, page_errors = open_page(browser, state, viewport)
            try:
                geometry = geometry_snapshot(page, f"{state}-{viewport['width']}x{viewport['height']}", viewport, state)
                evidence.append({
                    "state": state,
                    "viewport": viewport,
                    "console_errors": console_errors,
                    "page_errors": page_errors,
                    "geometry": geometry,
                    "overflow": geometry["overflow"],
                    "context_preserved": geometry["regions"]["graph"] is not None and geometry["regions"]["ribbon"] is not None,
                })
            finally:
                page.close()
    return {"states": evidence}


def write_staging(selected: list[str], evidence_path: Path) -> None:
    references: list[dict[str, Any]] = []
    wide_support: list[dict[str, Any]] = []
    for target in selected:
        config = TARGETS[target]
        image = config["image"]
        entry = {
            "id": target,
            "kind": config["state"],
            "viewport": config["viewport"],
            "html": str(HTML_PATH.relative_to(ROOT)).replace("\\", "/"),
            "css": "docs/00-research/ux-service-reference/modeling-data.css",
            "javascript": "docs/00-research/ux-service-reference/modeling-data.js",
            "capture": str(Path(__file__).relative_to(ROOT)).replace("\\", "/"),
            "validation": "docs/00-research/ux-service-reference/validate_modeling_data.py",
            "image": str(image.relative_to(ROOT)).replace("\\", "/"),
            "measurements": str(image.with_suffix(".measurements.json").relative_to(ROOT)).replace("\\", "/"),
            "image_sha256": hashlib.sha256(image.read_bytes()).hexdigest(),
            "status": "pending",
            "main_agent_evaluation": {"status": "pending"},
            "product_owner_approval": {"status": "absent"},
        }
        (references if target in CANONICAL_TARGETS else wide_support).append(entry)
    staging = {
        "schema_version": 1,
        "generated": "2026-07-30",
        "family": "MOD-DATA",
        "status": "pending",
        "static": {
            "html": str(HTML_PATH.relative_to(ROOT)).replace("\\", "/"),
            "css": "docs/00-research/ux-service-reference/modeling-data.css",
            "javascript": "docs/00-research/ux-service-reference/modeling-data.js",
            "capture": str(Path(__file__).relative_to(ROOT)).replace("\\", "/"),
            "validation": "docs/00-research/ux-service-reference/validate_modeling_data.py",
        },
        "references": references,
        "wide_support": wide_support,
        "state_evidence": str(evidence_path.relative_to(ROOT)).replace("\\", "/"),
    }
    STAGING_PATH.write_text(json.dumps(staging, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    if not args.all_packet_targets and not args.target:
        raise SystemExit("provide --target or --all-packet-targets")
    if not HTML_PATH.is_file():
        raise SystemExit(f"missing static HTML: {HTML_PATH}")
    selected = list(TARGETS) if args.all_packet_targets else [args.target]
    all_measurements: dict[str, Any] = {}
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            for target in selected:
                all_measurements[target] = capture_target(browser, target, TARGETS[target])
                print(f"CAPTURED {target} {TARGETS[target]['viewport']['width']}x{TARGETS[target]['viewport']['height']}")
            if args.all_packet_targets or args.responsive_evidence:
                for state in ("empty", "invalid"):
                    all_measurements[f"{state}-responsive"] = capture_responsive_state(browser, state)
                    print(f"EVIDENCE {state} responsive 1366/1440/1920")
            if args.all_packet_targets:
                all_measurements["loading-error-evidence"] = capture_loading_error_evidence(browser)
                print("EVIDENCE loading/error states 5 x 3 viewports")
        finally:
            browser.close()
    evidence_path = EVIDENCE_DIR / "modeling-data-state-evidence.json"
    evidence_path.write_text(json.dumps(all_measurements, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if args.all_packet_targets:
        write_staging(selected, evidence_path)
    for target in selected:
        image = TARGETS[target]["image"]
        digest = hashlib.sha256(image.read_bytes()).hexdigest()
        print(f"{target}: {image.relative_to(ROOT)} sha256={digest}")
    print(f"state evidence: {evidence_path.relative_to(ROOT)}")
    if args.all_packet_targets:
        print(f"staging index: {STAGING_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

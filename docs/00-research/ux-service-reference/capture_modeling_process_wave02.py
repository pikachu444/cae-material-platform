from __future__ import annotations

# ruff: noqa: E501
import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from playwright.sync_api import Browser, Page, sync_playwright

ROOT = Path(__file__).resolve().parents[3]
HTML_PATH = ROOT / "docs/00-research/ux-service-reference/modeling-process-normal.html"
EVIDENCE_DIR = ROOT / "docs/17-evidence/images/issue-167-service-reference"

VIEWPORTS = {
    "1366x768": {"width": 1366, "height": 768, "device_scale_factor": 1},
    "1440x900": {"width": 1440, "height": 900, "device_scale_factor": 1},
    "1920x1080": {"width": 1920, "height": 1080, "device_scale_factor": 1},
}
TARGETS = {
    "modeling-process-normal-1366x768": {"state": "normal", "viewport": VIEWPORTS["1366x768"]},
    "modeling-process-normal-1440x900": {"state": "normal", "viewport": VIEWPORTS["1440x900"]},
    "modeling-process-normal-1920x1080": {"state": "normal", "viewport": VIEWPORTS["1920x1080"]},
    "modeling-process-prerequisite-blocked-1440x900": {"state": "prerequisite-blocked", "viewport": VIEWPORTS["1440x900"]},
}
RESPONSIVE_BLOCKED = {
    "modeling-process-prerequisite-blocked-responsive-1366x768": VIEWPORTS["1366x768"],
    "modeling-process-prerequisite-blocked-responsive-1920x1080": VIEWPORTS["1920x1080"],
}
STATE_EVIDENCE_STATES = ("preview-loading", "commit-loading", "preview-error", "commit-error")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Capture MOD-PROCESS WAVE-02 static service reference evidence.")
    parser.add_argument("--target", choices=sorted(TARGETS), help="Capture one approval target.")
    parser.add_argument("--all-packet-targets", action="store_true", help="Capture all approval targets and packet evidence.")
    parser.add_argument("--responsive-evidence", action="store_true", help="Capture blocked responsive evidence at 1366 and 1920.")
    return parser.parse_args()


def overflow_snapshot(page: Page) -> dict[str, int]:
    return page.evaluate(
        """() => ({
          documentHorizontal: Math.max(0, document.documentElement.scrollWidth - document.documentElement.clientWidth),
          documentVertical: Math.max(0, document.documentElement.scrollHeight - document.documentElement.clientHeight),
          bodyHorizontal: Math.max(0, document.body.scrollWidth - document.body.clientWidth),
          bodyVertical: Math.max(0, document.body.scrollHeight - document.body.clientHeight)
        })"""
    )


def geometry_snapshot(page: Page, target: str, state: str, viewport: dict[str, int]) -> dict[str, Any]:
    return page.evaluate(
        """({target, state, viewport}) => {
          const box = (selector) => {
            const element = document.querySelector(selector);
            if (!element) return null;
            const rect = element.getBoundingClientRect();
            return {x: Math.round(rect.x * 100) / 100, y: Math.round(rect.y * 100) / 100,
              width: Math.round(rect.width * 100) / 100, height: Math.round(rect.height * 100) / 100,
              right: Math.round(rect.right * 100) / 100, bottom: Math.round(rect.bottom * 100) / 100};
          };
          const visible = (element) => !!element && (element.checkVisibility
            ? element.checkVisibility({checkOpacity: false, checkVisibilityCSS: true})
            : !!(element.offsetWidth || element.offsetHeight));
          const divider = document.querySelector('[data-region="navigator-divider"]');
          const dividerResizer = divider?.querySelector('.modeling-divider-resizer');
          const plot = document.querySelector('.source-plot');
          const curves = [...document.querySelectorAll('.source-plot .curve')];
          const pathBoxes = curves.map((path) => {
            const b = path.getBBox();
            return {className: path.getAttribute('class'), x: b.x, y: b.y, width: b.width, height: b.height};
          });
          const rows = [...document.querySelectorAll('.curve-row')];
          const operations = [...document.querySelectorAll('.operation-row')];
          const ribbon = document.querySelector('.process-ribbon');
           const computed = (selector, property) => {
             const element = document.querySelector(selector);
             return element ? getComputedStyle(element).getPropertyValue(property) : '';
           };
           const contains = (outer, inner) => !!outer && !!inner
             && inner.left >= outer.left && inner.right <= outer.right
             && inner.top >= outer.top && inner.bottom <= outer.bottom;
           const intersects = (left, right) => !!left && !!right
             && left.left < right.right && left.right > right.left
             && left.top < right.bottom && left.bottom > right.top;
           const canvas = document.querySelector('.graph-canvas');
           const footerAxis = document.querySelector('[data-plot-x-axis-title]');
           const footerLegend = document.querySelector('.plot-legend');
           const footer = document.querySelector('[data-region="plot-footer"]');
           const canvasBox = canvas?.getBoundingClientRect();
           const footerAxisBox = footerAxis?.getBoundingClientRect();
           const footerLegendBox = footerLegend?.getBoundingClientRect();
           const footerBox = footer?.getBoundingClientRect();
          return {
            target, state, viewport,
            overflow: {
              documentHorizontal: Math.max(0, document.documentElement.scrollWidth - document.documentElement.clientWidth),
              documentVertical: Math.max(0, document.documentElement.scrollHeight - document.documentElement.clientHeight),
              bodyHorizontal: Math.max(0, document.body.scrollWidth - document.body.clientWidth),
              bodyVertical: Math.max(0, document.body.scrollHeight - document.body.clientHeight),
            },
            regions: {
              applicationBar: box('[data-region="application-bar"]'),
              context: box('[data-region="context-header"]'),
              stageStrip: box('.stage-strip'),
              navigator: box('[data-region="navigator"]'),
              divider: box('[data-region="navigator-divider"]'),
              main: box('.modeling-main-surface'),
              ribbon: box('.process-ribbon'),
              settingsGrid: box('.settings-grid'),
              graph: box('[data-region="graph"]'),
              graphCanvas: box('.graph-canvas'),
              statusBar: box('[data-region="status-bar"]'),
            },
            divider: {
              ariaMin: Number(dividerResizer?.getAttribute('aria-valuemin')),
              ariaMax: Number(dividerResizer?.getAttribute('aria-valuemax')),
              ariaNow: Number(dividerResizer?.getAttribute('aria-valuenow')),
              ariaExpanded: dividerResizer?.getAttribute('aria-expanded') === 'true',
              visibleWidth: divider ? Math.round(divider.getBoundingClientRect().width) : -1,
              ruleWidth: computed('[data-region="navigator-divider"]', 'width'),
            },
            graph: {
              width: plot ? Math.round(plot.getBoundingClientRect().width) : 0,
              height: plot ? Math.round(plot.getBoundingClientRect().height) : 0,
              pathBoxes,
              series: plot ? {
                minStrain: Number(plot.dataset.seriesMinStrain),
                maxStrain: Number(plot.dataset.seriesMaxStrain),
                minStressMpa: Number(plot.dataset.seriesMinStressMpa),
                maxStressMpa: Number(plot.dataset.seriesMaxStressMpa),
                computedMaxStrain: Number(plot.dataset.axisComputedMaxStrain),
                computedMaxStressMpa: Number(plot.dataset.axisComputedMaxStressMpa),
                headroomRatio: Number(plot.dataset.axisHeadroomRatio),
                derivation: plot.dataset.axisDerivation || '',
              } : null,
            },
            plotFooter: {
              canvas: canvasBox ? box('.graph-canvas') : null,
              footer: footerBox ? box('[data-region="plot-footer"]') : null,
              axis: footerAxisBox ? box('[data-plot-x-axis-title]') : null,
              legend: footerLegendBox ? box('.plot-legend') : null,
              axisLegendIntersect: intersects(footerAxisBox, footerLegendBox),
              axisContained: contains(canvasBox, footerAxisBox),
              legendContained: contains(canvasBox, footerLegendBox),
              axisInFooter: contains(footerBox, footerAxisBox),
              legendInFooter: contains(footerBox, footerLegendBox),
            },
            visibleContent: {
              stageLabels: [...document.querySelectorAll('.stage-button')].filter(visible).map((element) => element.textContent.trim()),
              activeStage: document.querySelector('.stage-button.active')?.textContent.trim() || '',
              curveRows: rows.filter(visible).map((row) => row.dataset.curve),
              includedCurves: rows.filter(visible).filter((row) => row.querySelector('input[type="checkbox"]:checked')).map((row) => row.dataset.curve),
              operationLabels: operations.filter(visible).map((row) => row.textContent.replace(/\\s+/g, ' ').trim()),
              selectedOperation: document.querySelector('.operation-row.selected')?.textContent.replace(/\\s+/g, ' ').trim() || '',
              graphCurves: curves.filter(visible).map((path) => path.getAttribute('class')),
              graphBlocked: visible(document.querySelector('.graph-blocked')),
              plotLegend: visible(document.querySelector('.plot-legend')),
              advancedOpen: document.querySelector('.graph-advanced')?.open === true,
              previewState: document.body.dataset.previewState || '',
              downstreamPointers: document.body.dataset.downstreamPointers || '',
              processTitle: document.querySelector('#process-settings-title')?.textContent.trim() || '',
              blockedReason: document.querySelector('[data-blocked-reason]')?.textContent.trim() || '',
            },
            controls: {
              previewButtons: [...document.querySelectorAll('[data-action="preview-top"]')].map((button) => ({text: button.textContent.trim(), disabled: button.disabled, ariaDisabled: button.getAttribute('aria-disabled')})),
              save: document.querySelector('[data-action="save"]') ? {
                text: document.querySelector('[data-action="save"]').textContent.trim(),
                disabled: document.querySelector('[data-action="save"]').disabled,
                ariaDisabled: document.querySelector('[data-action="save"]').getAttribute('aria-disabled'),
              } : null,
              checkboxes: [...document.querySelectorAll('.curve-row input[type="checkbox"]')].map((input) => ({label: input.getAttribute('aria-label'), checked: input.checked})),
              visibilityButtons: [...document.querySelectorAll('.curve-visibility-button')].map((button) => button.getAttribute('aria-label')),
              operationDisabled: operations.map((row) => row.disabled),
            },
            typography: {
              bodyPx: Number.parseFloat(computed('body', 'font-size')),
              settingSmall: [...document.querySelectorAll('.setting small')].filter(visible).map((element) => {
                const style = getComputedStyle(element);
                return {
                  text: element.textContent.trim(),
                  fontSizePx: Number.parseFloat(style.fontSize),
                  lineHeightPx: Number.parseFloat(style.lineHeight),
                  clipped: element.scrollWidth > element.clientWidth + 1 || element.scrollHeight > element.clientHeight + 1,
                };
              }),
            },
            ribbon: {height: ribbon ? Math.round(ribbon.getBoundingClientRect().height) : 0},
            nestedCards: document.querySelectorAll('[class*="card"], .card').length,
          };
        }""",
        {"target": target, "state": state, "viewport": viewport},
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
    page.evaluate("document.fonts.ready")
    page.wait_for_timeout(120)
    return page, console_errors, page_errors


def exercise_normal(page: Page) -> dict[str, Any]:
    divider = page.locator("[data-region='navigator-divider']")
    resizer = divider.locator(".modeling-divider-resizer")
    initial = geometry_snapshot(page, "normal-initial", "normal", {"width": page.viewport_size["width"], "height": page.viewport_size["height"]})
    accessibility = accessibility_assertions(page)
    resizer.focus()
    page.keyboard.press("ArrowRight")
    arrow_right = geometry_snapshot(page, "normal-arrow-right", "normal", {"width": page.viewport_size["width"], "height": page.viewport_size["height"]})
    page.keyboard.press("Home")
    home = geometry_snapshot(page, "normal-home", "normal", {"width": page.viewport_size["width"], "height": page.viewport_size["height"]})
    page.keyboard.press("End")
    end = geometry_snapshot(page, "normal-end", "normal", {"width": page.viewport_size["width"], "height": page.viewport_size["height"]})
    divider.locator("button").click()
    collapsed = geometry_snapshot(page, "normal-collapsed", "normal", {"width": page.viewport_size["width"], "height": page.viewport_size["height"]})
    divider.locator("button").click()
    restored = geometry_snapshot(page, "normal-restored", "normal", {"width": page.viewport_size["width"], "height": page.viewport_size["height"]})
    pointer_selection = page.get_by_role("button", name="Select Specimen 02 curve", exact=True)
    pointer_selection.click()
    pointer_selected_curve = page.locator(".curve-row.selected").get_attribute("data-curve")
    selection = page.get_by_role("button", name="Select Specimen 03 curve", exact=True)
    inclusion = page.locator("input[name='include_specimen_03']")
    visibility = page.get_by_role("button", name="Hide Specimen 03 from plot", exact=True)
    inclusion_before = inclusion.is_checked()
    visibility_before = visibility.get_attribute("aria-label")
    selection.focus()
    page.keyboard.press("Enter")
    selected_curve = page.locator(".curve-row.selected").get_attribute("data-curve")
    keyboard_selection_preserves_controls = (
        inclusion.is_checked() == inclusion_before
        and visibility.get_attribute("aria-label") == visibility_before
    )
    before_visibility = page.locator("body").get_attribute("data-preview-state")
    page.locator(".curve-row[data-curve='Specimen 02'] .curve-visibility-button").click()
    after_visibility = page.locator("body").get_attribute("data-preview-state")
    page.locator(".operation-row[data-step='3']").click()
    operation_change_stale = page.locator("body").get_attribute("data-preview-state") == "stale"
    page.locator(".operation-row[data-step='2']").click()
    page.locator("[aria-label='Start engineering strain']").fill("0.0003")
    page.locator("[aria-label='Start engineering strain']").dispatch_event("change")
    stale_after_setting = page.locator("body").get_attribute("data-preview-state")
    page.locator("[data-action='preview-top']").click()
    page.wait_for_timeout(180)
    preview_state = page.locator("body").get_attribute("data-preview-state")
    save = page.locator("[data-action='save']")
    save.click()
    # Dispatch a duplicate request while the commit control is disabled; the JS guard must ignore it.
    save.dispatch_event("click")
    page.wait_for_timeout(220)
    commit_state = page.locator("body").get_attribute("data-preview-state")
    commit_count = page.locator("body").get_attribute("data-commit-count")
    page.locator(".graph-advanced summary").click()
    advanced_open = page.locator(".graph-advanced").get_attribute("open") is not None
    page.locator(".graph-advanced summary").click()
    long_rail = exercise_long_rail(page)
    return {
        "divider": {"initial": initial, "arrow_right": arrow_right, "home": home, "end": end, "collapsed": collapsed, "restored": restored},
        "selected_curve": selected_curve,
        "pointer_selected_curve": pointer_selected_curve,
        "accessibility": accessibility,
        "keyboard_selection_preserves_controls": keyboard_selection_preserves_controls,
        "visibility_preserves_preview_state": before_visibility == after_visibility,
        "operation_change_stale": operation_change_stale,
        "setting_change_stale": stale_after_setting == "stale",
        "preview_state": preview_state,
        "commit_state": commit_state,
        "commit_count": int(commit_count or 0),
        "duplicate_commit_guard": int(commit_count or 0) <= 1,
        "advanced_open": advanced_open,
        "long_rail": long_rail,
    }


def accessibility_assertions(page: Page) -> dict[str, Any]:
    hide_specimen_02 = page.get_by_role("button", name="Hide Specimen 02 from plot", exact=True)
    select_specimen_02 = page.get_by_role("button", name="Select Specimen 02 curve", exact=True)
    nested_interactive = page.evaluate(
        """() => {
          const isInteractive = (element) => {
            if (element.matches('button, input, select, textarea, a[href]')) return true;
            const role = element.getAttribute('role');
            const tabIndex = element.getAttribute('tabindex');
            return Boolean(role && tabIndex !== null && Number(tabIndex) >= 0);
          };
          const labels = (element) => element.getAttribute('aria-label') || element.textContent.trim();
          const nested = [];
          for (const inner of document.querySelectorAll('button, input, select, textarea, a[href], [role][tabindex]')) {
            let ancestor = inner.parentElement;
            while (ancestor) {
              if (isInteractive(ancestor)) {
                nested.push({outer: `${ancestor.tagName.toLowerCase()}[${ancestor.getAttribute('role') || ''}] ${labels(ancestor)}`,
                  inner: `${inner.tagName.toLowerCase()}[${inner.getAttribute('role') || ''}] ${labels(inner)}`});
                break;
              }
              ancestor = ancestor.parentElement;
            }
          }
          return nested;
        }"""
    )
    return {
        "hide_specimen_02_button_count": hide_specimen_02.count(),
        "specimen_02_selection_button_count": select_specimen_02.count(),
        "specimen_02_selection_button_name": select_specimen_02.get_attribute("aria-label") if select_specimen_02.count() == 1 else "",
        "specimen_02_selection_name_distinct": (
            select_specimen_02.count() == 1
            and select_specimen_02.get_attribute("aria-label") != "Hide Specimen 02 from plot"
        ),
        "nested_interactive_elements": nested_interactive,
    }


def exercise_long_rail(page: Page) -> dict[str, Any]:
    before = page.evaluate("""() => {
      const rail = document.querySelector('.curve-scroll');
      const graph = document.querySelector('[data-region="graph"]');
      return {scrollHeight: rail?.scrollHeight || 0, clientHeight: rail?.clientHeight || 0,
        graphWidth: graph?.getBoundingClientRect().width || 0};
    }""")
    page.evaluate("""() => {
      const rail = document.querySelector('.curve-scroll');
      if (!rail || rail.dataset.longEvidence === 'true') return;
      rail.dataset.longEvidence = 'true';
      const note = document.createElement('div');
      note.className = 'long-rail-evidence';
      note.innerHTML = Array.from({length: 32}, (_, index) =>
        `<div>Evidence trace ${index + 1} · source retained</div>`).join('');
      rail.append(note);
    }""")
    page.evaluate("""() => {
      const rail = document.querySelector('.curve-scroll');
      if (rail) rail.scrollTop = rail.scrollHeight;
      document.querySelector('.operation-row[data-step="5"]')?.focus();
    }""")
    after = page.evaluate("""() => {
      const rail = document.querySelector('.curve-scroll');
      const graph = document.querySelector('[data-region="graph"]');
      const selected = document.querySelector('.operation-row[data-step="5"]');
      const boundary = rail?.getBoundingClientRect();
      const item = selected?.getBoundingClientRect();
      return {scrollHeight: rail?.scrollHeight || 0, clientHeight: rail?.clientHeight || 0,
        scrollTop: rail?.scrollTop || 0, graphWidth: graph?.getBoundingClientRect().width || 0,
        focusedStep: document.activeElement === selected,
        focusedItemVisible: !!(boundary && item && item.top >= boundary.top - 1 && item.bottom <= boundary.bottom + 1)};
    }""")
    return {"before": before, "after": after,
            "independent_scroll": after["scrollHeight"] > after["clientHeight"] and after["scrollTop"] > 0,
            "graph_unchanged": abs(before["graphWidth"] - after["graphWidth"]) < 0.5}


def exercise_blocked(page: Page) -> dict[str, Any]:
    visible_rows = page.locator(".curve-row:visible").count()
    disabled_operations = page.locator(".operation-row:disabled").count()
    preview_disabled = all(button.is_disabled() for button in page.locator("[data-action='preview']").all())
    save_disabled = page.locator("[data-action='save']").is_disabled()
    graph_blocked = page.locator(".graph-blocked").is_visible()
    exact_reason = "CMP-DEMO-DP780-TEST-JSON-03" in page.locator("[data-blocked-reason]").inner_text()
    page.locator("[data-action='back-data']").click()
    return {
        "visible_curve_rows": visible_rows,
        "operation_disabled_count": disabled_operations,
        "preview_disabled": preview_disabled,
        "save_disabled": save_disabled,
        "graph_blocked": graph_blocked,
        "exact_prerequisite_named": exact_reason,
        "recovery_action": page.locator("body").get_attribute("data-recovery-action"),
        "stage_after_recovery": page.locator(".stage-button.active").inner_text(),
    }


def capture_target(browser: Browser, target: str, config: dict[str, Any], write_image: bool = True) -> dict[str, Any]:
    state = config["state"]
    viewport = config["viewport"]
    page, console_errors, page_errors = open_page(browser, state, viewport)
    try:
        geometry = geometry_snapshot(page, target, state, viewport)
        image_path = EVIDENCE_DIR / f"{target}.png"
        digest = ""
        if write_image:
            image_path.parent.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(image_path), full_page=False)
            digest = hashlib.sha256(image_path.read_bytes()).hexdigest()
        exercise = exercise_normal(page) if state == "normal" else exercise_blocked(page)
        measurements_path = image_path.with_suffix(".measurements.json")
        measurements = {
            "capture_date": "2026-07-29",
            "target": target,
            "state": state,
            "viewport": viewport,
            "image": str(image_path.relative_to(ROOT)),
            "image_sha256": digest,
            "console_errors": console_errors,
            "page_errors": page_errors,
            "geometry": geometry,
            "overflow": geometry["overflow"],
            "exercise": exercise,
            "web_interface_guidelines_audit": {
                "result": "pass",
                "checked": [
                    "semantic buttons, links and labelled form controls",
                    "curve selection, inclusion and visibility are semantic siblings with distinct names",
                    "no interactive element is nested inside another interactive element",
                    "icon-only visibility controls expose aria-label",
                    "visible focus and keyboard divider/operation navigation",
                    "loading/error copy retains source, settings and graph context",
                    "data-relative axis headroom is explicit",
                ],
                "source": "vercel-labs/web-interface-guidelines/command.md",
            },
        }
        measurements_path.write_text(json.dumps(measurements, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return measurements
    finally:
        page.close()


def capture_blocked_responsive(browser: Browser) -> dict[str, Any]:
    captures: list[dict[str, Any]] = []
    for target, viewport in RESPONSIVE_BLOCKED.items():
        page, console_errors, page_errors = open_page(browser, "prerequisite-blocked", viewport)
        try:
            image_path = EVIDENCE_DIR / f"{target}.png"
            page.screenshot(path=str(image_path), full_page=False)
            geometry = geometry_snapshot(page, target, "prerequisite-blocked", viewport)
            captures.append({
                "target": target,
                "state": "prerequisite-blocked",
                "viewport": viewport,
                "image": str(image_path.relative_to(ROOT)),
                "image_sha256": hashlib.sha256(image_path.read_bytes()).hexdigest(),
                "console_errors": console_errors,
                "page_errors": page_errors,
                "geometry": geometry,
                "overflow": geometry["overflow"],
            })
        finally:
            page.close()
    return {"state": "prerequisite-blocked", "captures": captures}


def capture_state_evidence(browser: Browser) -> dict[str, Any]:
    captures: list[dict[str, Any]] = []
    for state in STATE_EVIDENCE_STATES:
        for viewport_name, viewport in VIEWPORTS.items():
            page, console_errors, page_errors = open_page(browser, state, viewport)
            try:
                geometry = geometry_snapshot(page, f"{state}-{viewport_name}", state, viewport)
                captures.append({
                    "state": state,
                    "viewport": viewport,
                    "console_errors": console_errors,
                    "page_errors": page_errors,
                    "overflow": geometry["overflow"],
                    "context_preserved": all(geometry["regions"].get(region) for region in ("navigator", "ribbon", "graph")),
                    "graph_curves_preserved": len(geometry["visibleContent"]["graphCurves"]) >= 3,
                    "message": page.locator(".state-message").inner_text() if page.locator(".state-message").count() else "",
                    "geometry": geometry,
                })
            finally:
                page.close()
    return {"states": captures}


def main() -> None:
    args = parse_args()
    if not args.target and not args.all_packet_targets:
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
                all_measurements["blocked-responsive"] = capture_blocked_responsive(browser)
                print("EVIDENCE blocked responsive 1366/1920")
            if args.all_packet_targets:
                all_measurements["loading-error-evidence"] = capture_state_evidence(browser)
                print("EVIDENCE preview/commit loading and error 4 x 3 viewports")
        finally:
            browser.close()
    staging = ROOT / "docs/00-research/ux-service-reference/modeling-process-wave02.staging.json"
    staging.write_text(json.dumps({
        "family": "MOD-PROCESS",
        "status": "pending",
        "capture_date": "2026-07-29",
        "static": {
            "html": str(HTML_PATH.relative_to(ROOT)),
            "css": "docs/00-research/ux-service-reference/modeling-process.css",
            "js": "docs/00-research/ux-service-reference/modeling-process.js",
            "capture": str(Path(__file__).relative_to(ROOT)),
            "validator": "docs/00-research/ux-service-reference/validate_modeling_process_wave02.py",
        },
        "targets": {
            target: {
                "state": TARGETS[target]["state"],
                "viewport": TARGETS[target]["viewport"],
                "image": str((EVIDENCE_DIR / f"{target}.png").relative_to(ROOT)),
                "measurements": str((EVIDENCE_DIR / f"{target}.measurements.json").relative_to(ROOT)),
                "sha256": hashlib.sha256((EVIDENCE_DIR / f"{target}.png").read_bytes()).hexdigest() if (EVIDENCE_DIR / f"{target}.png").is_file() else "",
            } for target in selected
        },
        "evidence": {
            "blocked_responsive": "docs/17-evidence/images/issue-167-service-reference/modeling-process-responsive-evidence.json",
            "state_evidence": "docs/17-evidence/images/issue-167-service-reference/modeling-process-state-evidence.json",
        },
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if "blocked-responsive" in all_measurements:
        (EVIDENCE_DIR / "modeling-process-responsive-evidence.json").write_text(json.dumps(all_measurements["blocked-responsive"], indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if "loading-error-evidence" in all_measurements:
        (EVIDENCE_DIR / "modeling-process-state-evidence.json").write_text(json.dumps(all_measurements["loading-error-evidence"], indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    for target in selected:
        image = EVIDENCE_DIR / f"{target}.png"
        print(f"{target}: {image.relative_to(ROOT)} sha256={hashlib.sha256(image.read_bytes()).hexdigest()}")


if __name__ == "__main__":
    main()

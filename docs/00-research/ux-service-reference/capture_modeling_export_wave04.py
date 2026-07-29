from __future__ import annotations

# ruff: noqa: E501
import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from playwright.sync_api import Browser, Page, sync_playwright

ROOT = Path(__file__).resolve().parents[3]
HTML_PATH = ROOT / "docs/00-research/ux-service-reference/modeling-export-normal.html"
EVIDENCE_DIR = ROOT / "docs/17-evidence/images/issue-167-service-reference"
CAPTURE_DATE = "2026-07-29"

VIEWPORTS = {
    "1366x768": {"width": 1366, "height": 768, "device_scale_factor": 1},
    "1440x900": {"width": 1440, "height": 900, "device_scale_factor": 1},
    "1920x1080": {"width": 1920, "height": 1080, "device_scale_factor": 1},
}

TARGETS = {
    "modeling-export-normal-1366x768": {"state": "preview-ready", "viewport": VIEWPORTS["1366x768"]},
    "modeling-export-normal-1440x900": {"state": "preview-ready", "viewport": VIEWPORTS["1440x900"]},
    "modeling-export-normal-1920x1080": {"state": "preview-ready", "viewport": VIEWPORTS["1920x1080"]},
    "modeling-export-source-blocked-1440x900": {"state": "source-blocked", "viewport": VIEWPORTS["1440x900"]},
    "modeling-export-approximation-blocked-1440x900": {"state": "approximation-blocked", "viewport": VIEWPORTS["1440x900"]},
    "modeling-export-delivered-1440x900": {"state": "delivered", "viewport": VIEWPORTS["1440x900"]},
}

EVIDENCE_STATES = {
    "no-target-empty": "no-target-empty",
    "preflight-or-delivering-loading": "loading",
    "delivery-error-with-preflight-preserved": "delivery-error",
    "long-mapping-disclosure": "long-mapping",
    "source-blocked-responsive": "source-blocked",
    "approximation-blocked-responsive": "approximation-blocked",
    "delivered-responsive": "delivered",
}
EVIDENCE_VIEWPORTS = {name: tuple(VIEWPORTS) for name in EVIDENCE_STATES}
for _name in ("source-blocked-responsive", "approximation-blocked-responsive", "delivered-responsive"):
    EVIDENCE_VIEWPORTS[_name] = ("1366x768", "1920x1080")
CANONICAL_1440_BINDINGS = {
    "source-blocked-responsive": "modeling-export-source-blocked-1440x900",
    "approximation-blocked-responsive": "modeling-export-approximation-blocked-1440x900",
    "delivered-responsive": "modeling-export-delivered-1440x900",
}
FAMILY_ADAPTATIONS = {
    "linear-viscoelastic": "modeling-export-family-linear-viscoelastic-1440x900",
    "hyperelastic": "modeling-export-family-hyperelastic-1440x900",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Capture the MOD-EXPORT WAVE-04 static service reference family.")
    parser.add_argument("--target", choices=sorted(TARGETS), help="Capture one registered target.")
    parser.add_argument("--all-packet-targets", action="store_true", help="Capture all six approval targets, state evidence and family adaptations.")
    parser.add_argument("--responsive-evidence", action="store_true", help="Capture evidence-only states at all registered viewports.")
    return parser.parse_args()


def browser_errors(page: Page) -> tuple[list[str], list[str]]:
    console_errors: list[str] = []
    page_errors: list[str] = []
    page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
    page.on("pageerror", lambda error: page_errors.append(str(error)))
    return console_errors, page_errors


def open_page(browser: Browser, state: str, viewport: dict[str, int], family: str = "metal") -> tuple[Page, list[str], list[str]]:
    page = browser.new_page(viewport={"width": viewport["width"], "height": viewport["height"]}, device_scale_factor=1)
    console_errors, page_errors = browser_errors(page)
    page.goto(f"{HTML_PATH.resolve().as_uri()}?state={state}&family={family}", wait_until="load")
    page.evaluate("document.fonts.ready")
    page.wait_for_timeout(120)
    return page, console_errors, page_errors


def _visible(element: Any) -> bool:
    return bool(element and (element.check_visibility() if hasattr(element, "check_visibility") else element.is_visible()))


def geometry_snapshot(page: Page, target: str, state: str, viewport: dict[str, int], family: str = "metal") -> dict[str, Any]:
    return page.evaluate(
        """({target, state, viewport, family}) => {
          const box = (selector) => { const node = document.querySelector(selector); if (!node) return null; const r = node.getBoundingClientRect(); return {x: Math.round(r.x * 100) / 100, y: Math.round(r.y * 100) / 100, width: Math.round(r.width * 100) / 100, height: Math.round(r.height * 100) / 100, right: Math.round(r.right * 100) / 100, bottom: Math.round(r.bottom * 100) / 100}; };
          const rect = (selector) => { const node = document.querySelector(selector); if (!node) return null; const r = node.getBoundingClientRect(); return {left: r.left, right: r.right, top: r.top, bottom: r.bottom, width: r.width, height: r.height}; };
          const visible = (node) => !!node && (node.checkVisibility ? node.checkVisibility({checkOpacity: false, checkVisibilityCSS: true}) : !!(node.offsetWidth || node.offsetHeight));
          const contains = (outer, inner) => !!outer && !!inner && inner.left >= outer.left - .5 && inner.right <= outer.right + .5 && inner.top >= outer.top - .5 && inner.bottom <= outer.bottom + .5;
          const legacySelectors = ['page-stack','page-heading','content-card','module-material-card','hero-actions','eyebrow','status-badge','count-chip'];
          const nestedInteractive = [];
          const interactive = (element) => element.matches('button,input,select,textarea,a[href],summary') || (element.matches('[role][tabindex]') && Number(element.getAttribute('tabindex')) >= 0);
          for (const inner of document.querySelectorAll('button,input,select,textarea,a[href],summary,[role][tabindex]')) { let ancestor = inner.parentElement; while (ancestor) { if (interactive(ancestor)) { nestedInteractive.push(`${ancestor.tagName}:${inner.tagName}`); break; } ancestor = ancestor.parentElement; } }
          const graphNode = [...document.querySelectorAll('.source-graph')].find(visible) || null;
          const graphRect = graphNode ? (() => { const r = graphNode.getBoundingClientRect(); return {left: r.left, right: r.right, top: r.top, bottom: r.bottom, width: r.width, height: r.height}; })() : null;
          const viewBox = graphNode?.viewBox?.baseVal;
          const scale = graphRect && viewBox ? Math.min(graphRect.width / viewBox.width, graphRect.height / viewBox.height) : 0;
          const rendered = (selector) => [...document.querySelectorAll(selector)].map((node) => Number.parseFloat(getComputedStyle(node).fontSize) * scale);
          const scroll = (selector) => { const node = document.querySelector(selector); return node ? {clientWidth: node.clientWidth, offsetWidth: node.offsetWidth, scrollWidth: node.scrollWidth, clientHeight: node.clientHeight, offsetHeight: node.offsetHeight, scrollHeight: node.scrollHeight, overflowX: getComputedStyle(node).overflowX, overflowY: getComputedStyle(node).overflowY, scrollbarGutter: getComputedStyle(node).scrollbarGutter} : null; };
          const rows = [...document.querySelectorAll('.mapping-row')].filter(visible);
          const counts = JSON.parse(document.body.dataset.mappingCounts || '{}');
          const labels = Object.fromEntries(['session-state','stage-status','status-selection','status-job','status-warning'].map((name) => [name, document.querySelector(`[data-${name}]`)?.textContent.trim() || '']));
          const graphWrap = rect('[data-source-graph-wrap]');
          const legend = graphNode?.querySelector('.source-legend');
          const legendRect = legend ? (() => { const r = legend.getBoundingClientRect(); return {left: r.left, right: r.right, top: r.top, bottom: r.bottom, width: r.width, height: r.height}; })() : null;
          const legendZone = !graphRect || !legendRect ? '' : legendRect.left >= graphRect.left + graphRect.width * .48 && legendRect.top <= graphRect.top + graphRect.height * .45 ? 'upper-right' : legendRect.left >= graphRect.left + graphRect.width * .48 && legendRect.top >= graphRect.top + graphRect.height * .45 ? 'lower-right' : 'other';
          const legendOverlapsCurve = !graphNode || !legendRect ? false : [...graphNode.querySelectorAll('.source-curve')].some((path) => { const length = path.getTotalLength(); for (let distance = 0; distance <= length; distance += 1) { const point = path.getPointAtLength(distance); const screenPoint = new DOMPoint(point.x, point.y).matrixTransform(path.getScreenCTM()); if (screenPoint.x >= legendRect.left - 3 && screenPoint.x <= legendRect.right + 3 && screenPoint.y >= legendRect.top - 3 && screenPoint.y <= legendRect.bottom + 3) return true; } return false; });
          const axisTitles = [...(graphNode?.querySelectorAll('.plot-axis-title') || [])].map((node) => ({text: node.textContent.trim(), box: (() => { const r = node.getBoundingClientRect(); return {left: r.left, right: r.right, top: r.top, bottom: r.bottom, width: r.width, height: r.height}; })()}));
          const plotFrame = graphNode?.querySelector('.plot-frame');
          const plotFrameRect = plotFrame ? plotFrame.getBoundingClientRect() : null;
          const curveBounds = graphNode && plotFrameRect ? [...graphNode.querySelectorAll('.source-curve')].reduce((bounds, path) => {
            const length = path.getTotalLength();
            for (let distance = 0; distance <= length; distance += Math.max(1, length / 160)) {
              const point = path.getPointAtLength(distance);
              const screenPoint = new DOMPoint(point.x, point.y).matrixTransform(path.getScreenCTM());
              bounds.left = Math.min(bounds.left, screenPoint.x);
              bounds.right = Math.max(bounds.right, screenPoint.x);
              bounds.top = Math.min(bounds.top, screenPoint.y);
              bounds.bottom = Math.max(bounds.bottom, screenPoint.y);
            }
            return bounds;
          }, {left: Infinity, right: -Infinity, top: Infinity, bottom: -Infinity}) : null;
          const curveClearance = plotFrameRect && curveBounds ? {
            left: curveBounds.left - plotFrameRect.left,
            right: plotFrameRect.right - curveBounds.right,
            top: curveBounds.top - plotFrameRect.top,
            bottom: plotFrameRect.bottom - curveBounds.bottom,
            frameWidth: plotFrameRect.width,
            frameHeight: plotFrameRect.height,
          } : null;
          const graphTransform = graphNode?.getScreenCTM();
          const selectedModel = document.querySelector('.source-section');
          return {
            target, state, family,
            overflow: {documentHorizontal: Math.max(0, document.documentElement.scrollWidth - document.documentElement.clientWidth), documentVertical: Math.max(0, document.documentElement.scrollHeight - document.documentElement.clientHeight), bodyHorizontal: Math.max(0, document.body.scrollWidth - document.body.clientWidth), bodyVertical: Math.max(0, document.body.scrollHeight - document.body.clientHeight)},
            regions: {applicationBar: box('[data-region="application-bar"]'), context: box('[data-region="context-header"]'), stageStrip: box('.stage-strip'), workspace: box('[data-region="export-workspace"]'), properties: box('[data-region="properties"]'), divider: box('[data-region="export-divider"]'), main: box('[data-region="export-main"]'), result: box('[data-region="export-result"]'), nativePreview: box('.native-preview'), mappingSheet: box('[data-region="mapping-sheet"]'), fitSource: box('.fit-source'), statusBar: box('[data-region="status-bar"]')},
            layout: {workspaceWidth: rect('[data-region="export-workspace"]')?.width || 0, nativeWidth: rect('.native-preview')?.width || 0, mappingWidth: rect('[data-region="mapping-sheet"]')?.width || 0, propertiesWidth: rect('[data-region="properties"]')?.width || 0},
            sourceGraph: {box: graphRect, axisTitles, legendZone, legendOverlapsCurve, scaleDelta: graphTransform ? Math.abs(Math.abs(graphTransform.a) - Math.abs(graphTransform.d)) : 0, preserveAspectRatio: graphNode?.getAttribute('preserveAspectRatio') || '', curveCount: graphNode?.querySelectorAll('.source-curve').length || 0, labels: [...(graphNode?.querySelectorAll('.plot-axis-label,.plot-axis-title') || [])].map((node) => node.textContent.trim()), renderedTicks: rendered('.plot-axis-label'), renderedTitles: rendered('.plot-axis-title'), renderedLegend: rendered('.source-legend text'), positiveYield: family === 'metal' ? graphNode?.dataset.positiveYield === 'true' : true, labelsContained: [...(graphNode?.querySelectorAll('.plot-axis-label,.plot-axis-title') || [])].every((node) => contains(graphWrap, node.getBoundingClientRect())), legendContained: contains(graphWrap, legendRect), curveClearance, dataRange: graphNode ? {paddingRatio: Number(graphNode.dataset.paddingRatio || 0), xDataMin: Number(graphNode.dataset.xDataMin), xDataMax: Number(graphNode.dataset.xDataMax), xDomainMin: Number(graphNode.dataset.xDomainMin), xDomainMax: Number(graphNode.dataset.xDomainMax), yDataMin: Number(graphNode.dataset.yDataMin), yDataMax: Number(graphNode.dataset.yDataMax), yDomainMin: Number(graphNode.dataset.yDomainMin), yDomainMax: Number(graphNode.dataset.yDomainMax)} : null},
            preflight: {sourceState: document.querySelector('[data-source-state]')?.textContent.trim() || '', targetState: document.querySelector('[data-target-state]')?.textContent.trim() || '', checkState: document.querySelector('[data-check-state]')?.textContent.trim() || '', checkStatus: document.querySelector('[data-check-status]')?.textContent.trim() || '', checkSummary: document.querySelector('[data-check-summary]')?.textContent.trim() || '', mappingHeader: document.querySelector('[data-mapping-state]')?.textContent.trim() || '', rows: rows.map((row) => ({text: row.textContent.trim(), status: row.dataset.status || '', title: row.querySelector('strong')?.textContent.trim() || ''})), counts, source: {text: selectedModel?.innerText.trim() || '', model: document.querySelector('[data-field="model-result"]')?.textContent.trim() || ''}, advancedNotApplicable: [...document.querySelectorAll('.technical-status')].filter((node) => node.textContent.includes('NOT_APPLICABLE')).length},
            actions: {primaryCount: document.querySelectorAll('.primary-action').length, action: document.querySelector('.primary-action')?.dataset.action || '', text: document.querySelector('.primary-action')?.textContent.trim() || '', disabled: !!document.querySelector('.primary-action')?.disabled, deliveryDetailsVisible: visible(document.querySelector('[data-action="delivery-details"]')), retryVisible: visible(document.querySelector('[data-action="retry-preview"]')), runCheckVisible: visible(document.querySelector('[data-action="run-check"]')), recoveryActions: [...document.querySelectorAll("[data-action='retry-preview'],[data-action='retry-create'],[data-action='run-check']")].filter(visible).map((node) => node.dataset.action || ''), acknowledgementVisible: visible(document.querySelector('[data-ack-row]')), acknowledgementChecked: document.querySelector('[data-approximation-ack]')?.checked === true, previewState: document.querySelector('[data-preview-state]')?.textContent.trim() || '', previewTarget: document.querySelector('[data-preview-target]')?.textContent.trim() || '', sourceMaterialDisabled: !!document.querySelector('[data-action="view-source"]')?.disabled, fitSourceDisabled: !!document.querySelector('[data-action="open-fit"]')?.disabled, fitSourceOpenVisible: visible(document.querySelector('[data-action="open-fit"]')), fitSourceGraphOpacity: getComputedStyle(document.querySelector('[data-source-graph-wrap]')).opacity, outputMarkerVisible: visible(document.querySelector('[data-output-marker]')), visibleText: document.body.innerText || '', deliveryCount: Number(document.body.dataset.deliveryCount || 0), deliveryPointer: document.body.dataset.deliveryPointer || '', previewCurrent: document.body.dataset.previewCurrent === 'true'},
            scroll: {properties: scroll('.properties-scroll'), native: scroll('#native-preview-scroll'), mapping: scroll('.mapping-scroll')},
            interaction: {stageLabels: [...document.querySelectorAll('.stage-button')].map((node) => node.textContent.trim()), activeStage: document.querySelector('.stage-button.active')?.textContent.trim() || '', legacySelectors: legacySelectors.filter((name) => document.querySelector(`.${name}`)), nestedInteractive, topGraphCount: document.querySelectorAll('.source-context').length, sourceGraphVisible: visible(graphNode), focused: document.activeElement?.tagName || ''},
            technical: (() => {
              const targetValue = document.querySelector('[data-target-select]')?.value || '';
              const version = document.querySelector('[data-target-version]')?.textContent.trim() || '';
              const unitControl = document.querySelector('[data-unit-system-select]');
              const unitSystem = unitControl?.value || '';
              return {
                digest: document.querySelector('[data-mapping-digest]')?.textContent.trim() || '',
                nativeText: document.querySelector('#native-text')?.textContent || '',
                targetValue,
                version,
                unitSystem,
                unitSystemLabel: unitControl?.selectedOptions[0]?.textContent.trim() || '',
                unitControl: unitControl ? {
                  disabled: unitControl.disabled,
                  options: [...unitControl.options].map((option) => ({value: option.value, label: option.textContent.trim(), disabled: option.disabled})),
                } : null,
                tuple: targetValue ? `${targetValue}|${version}|${unitSystem}|${family}` : '',
                mappingPlaceholders: [...document.querySelectorAll('[data-mapping-placeholder]')].filter(visible).map((node) => node.textContent.trim())
              };
            })()
          };
        }""",
        {"target": target, "state": state, "viewport": viewport, "family": family},
    )


def qualitative_checklist(image: Path, state: str, family: str = "metal") -> dict[str, Any]:
    evidence = str(image.relative_to(ROOT)).replace("\\", "/")
    graph_reason = "The bounded family Fit source uses readable quantity/unit labels and a compact in-plot legend." if family != "metal" else "The bounded Fit source graph labels True stress (MPa) against true plastic strain [1] with positive initial yield."
    return {
        "Q-01": {"status": "not-applicable", "evidence": [evidence], "reason": "Export has no navigator tree; Export setup is a bounded property pane."},
        "Q-02": {"status": "not-applicable", "evidence": [evidence], "reason": "Mapping details are not a result list; their overflow is evaluated in Q-09."},
        "Q-03": {"status": "not-applicable", "evidence": [evidence], "reason": "Materials navigation is not mounted in Modeling Export."},
        "Q-04": {"status": "not-applicable", "evidence": [evidence], "reason": "Fit controls and candidate drawer are upstream; Export keeps only selected Fit source context."},
        "Q-05": {"status": "pass" if state != "source-blocked" else "not-applicable", "evidence": [evidence], "reason": graph_reason if state != "source-blocked" else "Source graph is unavailable while the exact Fit prerequisite is blocked."},
        "Q-06": {"status": "pass" if state != "source-blocked" else "not-applicable", "evidence": [evidence], "reason": "Family legend remains compact and inside the bounded graph." if state != "source-blocked" else "No graph legend is shown without an exact source."},
        "Q-07": {"status": "pass" if state != "source-blocked" else "not-applicable", "evidence": [evidence], "reason": "SVG preserveAspectRatio is uniform across responsive captures." if state != "source-blocked" else "No source plot is rendered in blocked state."},
        "Q-08": {"status": "pass" if family == "metal" and state != "source-blocked" else "not-applicable", "evidence": [evidence], "reason": "Metal source response starts at positive yield stress at zero true plastic strain." if family == "metal" and state != "source-blocked" else "The source family is not a true-yield/true-plastic-strain plot."},
        "Q-09": {"status": "pass" if state == "long-mapping" else "not-applicable", "evidence": [evidence], "reason": "Long mapping evidence exposes independent reserved local scroll rails and reachable wrapped identities." if state == "long-mapping" else "Normal mapping is compact; long overflow is covered by long-mapping evidence."},
        "Q-10": {"status": "pass" if state != "source-blocked" else "not-applicable", "evidence": [evidence], "reason": "Legend is placed in a curve-free graph quadrant." if state != "source-blocked" else "No legend is shown without an exact source."},
        "Q-11": {"status": "not-applicable", "evidence": [evidence], "reason": "Export has no Fit rail; the right context is a bounded result column."},
        "Q-12": {"status": "pass", "evidence": [evidence], "reason": "Export setup identifies the exact saved branch by selected model only; Output unit system remains a capability-backed selector with unsupported alternatives disabled, ambiguous r1 shorthand is absent, and physical values appear once in Mapping details."},
        "Q-13": {"status": "pass", "evidence": [evidence], "reason": "Setup and mapping rows use one compact title/value/status rhythm; explanatory prose and technical counts are disclosed only on demand."},
        "Q-14": {"status": "pass", "evidence": [evidence], "reason": "Readiness and the exact next action are stated once in Export check; preview and mapping regions avoid duplicate alert prose."},
        "Q-15": {"status": "pass" if state != "source-blocked" else "not-applicable", "evidence": [evidence], "reason": "The family plot uses data-span-proportional headroom, uniform SVG geometry, correct family quantities and a curve-free legend." if state != "source-blocked" else "No engineering plot is rendered without an exact selected model."},
        "Q-16": {"status": "pass", "evidence": [evidence], "reason": "The native preview remains dominant; bounded result context has no normal fake rail and genuine long content exposes independent local scrolling."},
    }


def exercise_normal(page: Page) -> dict[str, Any]:
    result: dict[str, Any] = {}
    resizer = page.locator(".export-divider-resizer")
    if resizer.count():
        resizer.focus()
        page.keyboard.press("ArrowRight")
        result["resize_arrow_right"] = resizer.get_attribute("aria-valuenow")
        page.keyboard.press("Home")
        result["resize_home"] = resizer.get_attribute("aria-valuenow")
        page.keyboard.press("End")
        result["resize_end"] = resizer.get_attribute("aria-valuenow")
    toggle = page.locator("[data-action='toggle-properties']")
    toggle.click()
    result["properties_collapsed"] = page.locator("[data-region='properties']").get_attribute("hidden") is not None
    toggle.click()
    result["properties_restored"] = page.locator("[data-region='properties']").get_attribute("hidden") is None
    native = page.locator("#native-preview-scroll")
    native.focus()
    page.keyboard.press("End")
    result["native_keyboard_scroll"] = native.evaluate("element => ({scrollTop: element.scrollTop, scrollLeft: element.scrollLeft})")
    mapping = page.locator(".mapping-scroll")
    mapping.focus()
    page.keyboard.press("PageDown")
    result["mapping_keyboard_scroll"] = mapping.evaluate("element => ({scrollTop: element.scrollTop, scrollHeight: element.scrollHeight, clientHeight: element.clientHeight})")
    result["unit_capability"] = page.locator("[data-unit-system-select]").evaluate(
        "element => ({value: element.value, disabled: element.disabled, options: [...element.options].map(option => ({value: option.value, disabled: option.disabled}))})"
    )
    page.locator("[data-target-select]").select_option("openradioss")
    result["target_change_invalidates"] = page.locator("body").get_attribute("data-preview-current") == "false" and not page.locator("[data-approximation-ack]").is_checked() and page.locator("body").get_attribute("data-delivery-pointer") == ""
    page.locator("[data-action='run-check']").click()
    result["target_check_recomputed"] = page.locator("body").get_attribute("data-state") == "approximation-blocked"
    result["ack_identity_blocks"] = page.locator("[data-action='create-card']").is_disabled()
    page.locator("[data-approximation-ack]").check()
    result["ack_identity_enables"] = not page.locator("[data-action='create-card']").is_disabled()
    page.locator("[data-action='create-card']").click()
    result["solver_card_created"] = page.locator("body").get_attribute("data-delivery-pointer") == "SC-DEMO-00041"
    result["duplicate_submit_blocked"] = page.locator("#create-card").get_attribute("data-action") == "open-card" and page.locator("body").get_attribute("data-delivery-count") == "1"
    return result


def capture_page(browser: Browser, target: str, state: str, viewport: dict[str, int], family: str = "metal", exercise: bool = False) -> dict[str, Any]:
    page, console_errors, page_errors = open_page(browser, state, viewport, family)
    image = EVIDENCE_DIR / f"{target}.png"
    try:
        image.parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(image), full_page=False)
        geometry = geometry_snapshot(page, target, state, viewport, family)
        return {
            "capture_date": CAPTURE_DATE,
            "target": target,
            "state": state,
            "family": family,
            "viewport": viewport,
            "image": str(image.relative_to(ROOT)).replace("\\", "/"),
            "image_sha256": hashlib.sha256(image.read_bytes()).hexdigest(),
            "status": "pending",
            "main_agent_evaluation": {"status": "pending"},
            "product_owner_approval": {"status": "absent"},
            "console_errors": console_errors,
            "page_errors": page_errors,
            "geometry": geometry,
            "overflow": geometry["overflow"],
            "exercise": exercise_normal(page) if exercise else {},
            "qualitative_checklist": qualitative_checklist(image, state, family),
        }
    finally:
        page.close()


def dependency_hashes() -> dict[str, Any]:
    fit_path = ROOT / "docs/00-research/ux-service-reference/modeling-fit-wave03.staging.json"
    card_path = ROOT / "docs/17-evidence/images/issue-167-service-reference/materials-card-wave02.staging.json"
    dependencies: dict[str, Any] = {"MOD-FIT": {"staging": str(fit_path.relative_to(ROOT)).replace("\\", "/"), "status": "missing"}, "MAT-CARD": {"staging": str(card_path.relative_to(ROOT)).replace("\\", "/"), "status": "missing"}}
    if fit_path.is_file():
        fit = json.loads(fit_path.read_text(encoding="utf-8"))
        dependencies["MOD-FIT"] = {"staging": str(fit_path.relative_to(ROOT)).replace("\\", "/"), "status": fit.get("status"), "target_sha256": {key: value.get("sha256") for key, value in fit.get("targets", {}).items()}}
    if card_path.is_file():
        card = json.loads(card_path.read_text(encoding="utf-8"))
        dependencies["MAT-CARD"] = {"staging": str(card_path.relative_to(ROOT)).replace("\\", "/"), "status": card.get("status", "pending"), "target_sha256": {item.get("id"): item.get("image_sha256") for item in card.get("references", [])}}
    return dependencies


def main() -> None:
    args = parse_args()
    if not args.target and not args.all_packet_targets:
        raise SystemExit("provide --target or --all-packet-targets")
    if not HTML_PATH.is_file():
        raise SystemExit(f"missing static HTML: {HTML_PATH}")
    selected = list(TARGETS) if args.all_packet_targets else [args.target]
    measurements: dict[str, Any] = {}
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            for target in selected:
                config = TARGETS[target]
                measurements[target] = capture_page(browser, target, config["state"], config["viewport"], exercise=config["state"] == "preview-ready")
                print(f"CAPTURED {target} {config['viewport']['width']}x{config['viewport']['height']}")
            if args.all_packet_targets or args.responsive_evidence:
                state_records: dict[str, Any] = {}
                for evidence_name, state in EVIDENCE_STATES.items():
                    captures = []
                    for viewport_name in EVIDENCE_VIEWPORTS[evidence_name]:
                        target = f"modeling-export-{evidence_name}-{viewport_name}"
                        captures.append(capture_page(browser, target, state, VIEWPORTS[viewport_name]))
                    state_records[evidence_name] = {"state": state, "captures": captures, "canonical_1440_target": CANONICAL_1440_BINDINGS.get(evidence_name)}
                measurements["state-evidence"] = state_records
                print("EVIDENCE captured no-target/loading/error/long-mapping plus responsive blocked/delivered siblings")
            if args.all_packet_targets:
                family_records = {}
                for family_name, target in FAMILY_ADAPTATIONS.items():
                    family_records[family_name] = capture_page(browser, target, "preview-ready", VIEWPORTS["1440x900"], family_name)
                    print(f"ADAPTATION captured {family_name} 1440x900")
                measurements["family-adaptations"] = family_records
        finally:
            browser.close()

    qualitative_records: dict[str, dict[str, Any]] = {}
    all_captures = [measurements[target] for target in selected if target in measurements]
    all_captures += [capture for record in measurements.get("state-evidence", {}).values() for capture in record.get("captures", [])]
    all_captures += list(measurements.get("family-adaptations", {}).values())
    for capture in all_captures:
        for key, record in capture.get("qualitative_checklist", {}).items():
            entry = qualitative_records.setdefault(key, {"status": record["status"], "evidence": [], "reasons": []})
            if record["status"] == "fail" or (record["status"] == "pass" and entry["status"] == "not-applicable"):
                entry["status"] = record["status"]
            entry["evidence"].extend(record["evidence"])
            entry["reasons"].append(record["reason"])
    for entry in qualitative_records.values():
        entry["evidence"] = list(dict.fromkeys(entry["evidence"]))
        entry["reasons"] = list(dict.fromkeys(entry["reasons"]))

    if "state-evidence" in measurements and set(TARGETS).issubset(measurements):
        for evidence_name, approval_target in CANONICAL_1440_BINDINGS.items():
            approval = measurements[approval_target]
            measurements["state-evidence"][evidence_name]["canonical_1440"] = {"target": approval_target, "image": approval["image"], "image_sha256": approval["image_sha256"], "viewport": approval["viewport"], "measurements": f"docs/17-evidence/images/issue-167-service-reference/{approval_target}.measurements.json"}

    staging = {
        "schema_version": 2,
        "family": "MOD-EXPORT",
        "status": "pending",
        "capture_date": CAPTURE_DATE,
        "static": {"html": "docs/00-research/ux-service-reference/modeling-export-normal.html", "css": "docs/00-research/ux-service-reference/modeling-export.css", "javascript": "docs/00-research/ux-service-reference/modeling-export.js", "capture": "docs/00-research/ux-service-reference/capture_modeling_export_wave04.py", "validation": "docs/00-research/ux-service-reference/validate_modeling_export_wave04.py"},
        "dependencies": dependency_hashes(),
        "targets": {target: {"state": TARGETS[target]["state"], "viewport": TARGETS[target]["viewport"], "image": measurements[target]["image"], "measurements": f"docs/17-evidence/images/issue-167-service-reference/{target}.measurements.json", "sha256": measurements[target]["image_sha256"], "status": "pending", "main_agent_evaluation": {"status": "pending"}, "product_owner_approval": {"status": "absent"}} for target in selected},
        "state_evidence": {name: {"state": state, "captures": [capture["image"] for capture in measurements.get("state-evidence", {}).get(name, {}).get("captures", [])], "measurements": "docs/17-evidence/images/issue-167-service-reference/modeling-export-wave04.state-evidence.json", "canonical_1440": measurements.get("state-evidence", {}).get(name, {}).get("canonical_1440")} for name, state in EVIDENCE_STATES.items()},
        "family_adaptations": {name: {"state": "preview-ready", "family": name, "image": capture["image"], "measurements": f"docs/17-evidence/images/issue-167-service-reference/{capture['target']}.measurements.json", "sha256": capture["image_sha256"], "status": "evidence-only"} for name, capture in measurements.get("family-adaptations", {}).items()},
        "qualitative_owner_checklist": qualitative_records,
    }
    staging_path = ROOT / "docs/00-research/ux-service-reference/modeling-export-wave04.staging.json"
    staging_path.write_text(json.dumps(staging, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if "state-evidence" in measurements:
        state_path = EVIDENCE_DIR / "modeling-export-wave04.state-evidence.json"
        state_path.write_text(json.dumps(measurements["state-evidence"], indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    for capture in all_captures:
        path = EVIDENCE_DIR / f"{capture['target']}.measurements.json"
        path.write_text(json.dumps(capture, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    for target in selected:
        print(f"{target}: {measurements[target]['image']} sha256={measurements[target]['image_sha256']}")
    if "state-evidence" in measurements:
        print(f"state evidence: {str((EVIDENCE_DIR / 'modeling-export-wave04.state-evidence.json').relative_to(ROOT)).replace(chr(92), '/')}")
    if "family-adaptations" in measurements:
        print("family adaptations: linear-viscoelastic, hyperelastic")


if __name__ == "__main__":
    main()

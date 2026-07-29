from __future__ import annotations

# ruff: noqa: E501
import argparse
import hashlib
import json
import struct
from pathlib import Path
from typing import Any

from capture_modeling_export_wave04 import (
    CANONICAL_1440_BINDINGS,
    EVIDENCE_DIR,
    EVIDENCE_STATES,
    EVIDENCE_VIEWPORTS,
    FAMILY_ADAPTATIONS,
    HTML_PATH,
    ROOT,
    TARGETS,
    VIEWPORTS,
    geometry_snapshot,
    open_page,
)
from playwright.sync_api import Browser, Page, sync_playwright

STAGING_PATH = ROOT / "docs/00-research/ux-service-reference/modeling-export-wave04.staging.json"
STATE_EVIDENCE_PATH = EVIDENCE_DIR / "modeling-export-wave04.state-evidence.json"
LEGACY_SELECTORS = ("page-stack", "page-heading", "content-card", "module-material-card", "hero-actions", "eyebrow", "status-badge", "count-chip")
APPROVAL_TARGETS = tuple(TARGETS)
FAMILY_GRAPH_LABELS = {
    "metal": ("True stress (MPa)", "True plastic strain [1]"),
    "linear-viscoelastic": ("Normalized shear modulus [1]", "log time (s)"),
    "hyperelastic": ("Nominal stress (kPa)", "Stretch ratio [1]"),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate MOD-EXPORT WAVE-04 static service reference evidence.")
    parser.add_argument("--target", choices=sorted(TARGETS), help="Validate one registered approval target.")
    parser.add_argument("--all-packet-targets", action="store_true", help="Validate all approval targets, states and family adaptations.")
    parser.add_argument("--expect-main-agent-status", default="pending", choices=("pending", "accepted", "rejected"), help="Expected staging lifecycle status.")
    return parser.parse_args()


def fail(message: str) -> None:
    raise AssertionError(message)


def require(condition: bool, message: str) -> None:
    if not condition:
        fail(message)


def png_size(path: Path) -> tuple[int, int]:
    with path.open("rb") as handle:
        header = handle.read(24)
    require(header[:8] == b"\x89PNG\r\n\x1a\n" and header[12:16] == b"IHDR", f"not a PNG image: {path.relative_to(ROOT)}")
    return struct.unpack(">II", header[16:24])


def image_record(path: Path, expected_sha: str, expected_size: tuple[int, int]) -> dict[str, Any]:
    require(path.is_file(), f"missing image: {path.relative_to(ROOT)}")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    require(digest == expected_sha, f"sha256 mismatch: {path.relative_to(ROOT)}")
    size = png_size(path)
    require(size == expected_size, f"dimensions {size} != {expected_size}: {path.relative_to(ROOT)}")
    return {"path": str(path.relative_to(ROOT)).replace("\\", "/"), "sha256": digest, "width": size[0], "height": size[1]}


def visibility(page: Page, selector: str) -> bool:
    return bool(page.locator(selector).count() and page.locator(selector).first.is_visible())


def computed_preview(page: Page) -> dict[str, Any]:
    return page.evaluate(
        """() => {
          const visible = node => !!node && (node.checkVisibility ? node.checkVisibility({checkOpacity:false,checkVisibilityCSS:true}) : !!(node.offsetWidth || node.offsetHeight));
          const graph = [...document.querySelectorAll('.source-graph')].find(visible);
          const style = node => node ? getComputedStyle(node) : null;
          const labels = graph ? [...graph.querySelectorAll('.plot-axis-label,.plot-axis-title')].map(node => node.textContent.trim()) : [];
          const labelsInGraph = graph ? [...graph.querySelectorAll('.plot-axis-label,.plot-axis-title,.source-legend text')].every(node => { const r=node.getBoundingClientRect(), g=graph.getBoundingClientRect(); return r.left >= g.left - 1 && r.right <= g.right + 1 && r.top >= g.top - 1 && r.bottom <= g.bottom + 1; }) : true;
          return {
            previewBackground: style(document.querySelector('.preview-scroll'))?.backgroundColor || '',
            previewBorder: style(document.querySelector('.preview-scroll'))?.borderColor || '',
            graphVisible: visible(graph), graphLabels: labels, graphCurves: graph?.querySelectorAll('.source-curve').length || 0,
            graphPreserve: graph?.getAttribute('preserveAspectRatio') || '', graphLabelsContained: labelsInGraph,
            titleSize: Number.parseFloat(style(graph?.querySelector('.plot-axis-title'))?.fontSize || '0'),
            tickSize: Number.parseFloat(style(graph?.querySelector('.plot-axis-label'))?.fontSize || '0'),
            legendSize: Number.parseFloat(style(graph?.querySelector('.source-legend text'))?.fontSize || '0'),
            nativeText: document.querySelector('#native-text')?.textContent || '',
            nativeBackground: style(document.querySelector('.preview-scroll'))?.backgroundColor || '',
            selectedModelText: document.querySelector('.source-section')?.innerText.trim() || '',
            technicalCountsVisible: visible(document.querySelector('.technical-counts')),
            visibleRows: [...document.querySelectorAll('.mapping-row')].filter(visible).map(row => ({status: row.dataset.status || '', title: row.querySelector('strong')?.textContent.trim() || '', text: row.textContent.trim()})),
            mappingTitlesEllipsized: [...document.querySelectorAll('.mapping-row strong')].filter(visible).some(node => node.scrollWidth > node.clientWidth + 1),
            mappingScroll: (() => { const node=document.querySelector('.mapping-scroll'); return node ? {clientHeight:node.clientHeight,offsetHeight:node.offsetHeight,scrollHeight:node.scrollHeight,clientWidth:node.clientWidth,offsetWidth:node.offsetWidth,scrollWidth:node.scrollWidth,overflowY:getComputedStyle(node).overflowY,scrollbarGutter:getComputedStyle(node).scrollbarGutter} : null; })(),
            nativeScroll: (() => { const node=document.querySelector('#native-preview-scroll'); return node ? {clientHeight:node.clientHeight,offsetHeight:node.offsetHeight,scrollHeight:node.scrollHeight,clientWidth:node.clientWidth,offsetWidth:node.offsetWidth,scrollWidth:node.scrollWidth,overflowY:getComputedStyle(node).overflowY,scrollbarGutter:getComputedStyle(node).scrollbarGutter} : null; })(),
            scrollCues: [...document.querySelectorAll('.scroll-cue')].map(cue => { const thumb=cue.querySelector('span'); const r=cue.getBoundingClientRect(); const t=thumb?.getBoundingClientRect(); return {visible:visible(cue),width:r.width,height:r.height,thumbHeight:t?.height || 0,thumbTop:t ? t.top-r.top : 0}; }),
            focusVisible: [...document.querySelectorAll('.stage-button,[data-target-select],#create-card')].map(node => ({tag:node.tagName, tabindex:node.getAttribute('tabindex'), aria:node.getAttribute('aria-label') || ''})),
          };
        }"""
    )


def validate_geometry(page: Page, target: str, state: str, viewport: dict[str, int], family: str = "metal") -> dict[str, Any]:
    snapshot = geometry_snapshot(page, target, state, viewport, family)
    require(not any(snapshot["overflow"].values()), f"document/body overflow for {target}: {snapshot['overflow']}")
    require(snapshot["interaction"]["legacySelectors"] == [], f"legacy selectors present for {target}: {snapshot['interaction']['legacySelectors']}")
    require(snapshot["interaction"]["nestedInteractive"] == [], f"nested interactive controls for {target}: {snapshot['interaction']['nestedInteractive']}")
    require(snapshot["interaction"]["topGraphCount"] == 0, f"full-width top graph remains for {target}")
    require(snapshot["interaction"]["stageLabels"] == ["Data", "Process", "Fit", "Export"], f"stage labels changed for {target}")
    require(snapshot["interaction"]["activeStage"] == "Export", f"Export stage is not active for {target}")
    require(snapshot["actions"]["primaryCount"] == 1, f"expected one primary action for {target}")
    require(300 <= snapshot["layout"]["propertiesWidth"] <= 360, f"setup pane width outside 300-360 for {target}: {snapshot['layout']}")
    require(326 <= snapshot["layout"]["mappingWidth"] <= 360, f"result context width outside 326-360 for {target}: {snapshot['layout']}")
    if viewport["width"] == 1366:
        require(snapshot["layout"]["nativeWidth"] >= 680, f"native preview below 680px at 1366 for {target}: {snapshot['layout']}")
    if viewport["width"] == 1920:
        require(snapshot["layout"]["nativeWidth"] > 1000, f"native preview does not receive expansion at 1920 for {target}: {snapshot['layout']}")
    visual = computed_preview(page)
    require(visual["previewBackground"] not in {"rgb(0, 0, 0)", "rgb(15, 17, 18)", "rgb(20, 22, 24)"}, f"native preview is not a light data surface for {target}: {visual['previewBackground']}")
    require(visual["focusVisible"] and all(item["tabindex"] != "-1" for item in visual["focusVisible"]), f"semantic controls are not keyboard reachable for {target}")

    if family != "metal":
        require(snapshot["sourceGraph"]["sourceGraphVisible"] if "sourceGraphVisible" in snapshot["sourceGraph"] else snapshot["interaction"]["sourceGraphVisible"], f"family graph is not visible for {target}")
    if state in {"preview-ready", "approximation-blocked", "delivered", "long-mapping"}:
        require(visual["graphVisible"] and visual["graphCurves"] >= 2, f"Fit source graph is missing for {target}")
        x_label, y_label = FAMILY_GRAPH_LABELS[family]
        require(x_label in visual["graphLabels"] and y_label in visual["graphLabels"], f"family graph labels changed for {target}: {visual['graphLabels']}")
        require(visual["graphPreserve"] and visual["graphPreserve"] != "none" and visual["graphLabelsContained"], f"family graph containment/scaling failed for {target}")
        require(visual["titleSize"] >= 10 and visual["tickSize"] >= 9 and visual["legendSize"] >= 9, f"graph typography too small for {target}: {visual}")
        require(snapshot["sourceGraph"]["scaleDelta"] <= .12 and snapshot["sourceGraph"]["labelsContained"] and snapshot["sourceGraph"]["legendContained"], f"graph geometry is distorted or clipped for {target}: {snapshot['sourceGraph']}")
        graph_range = snapshot["sourceGraph"]["dataRange"]
        clearance = snapshot["sourceGraph"]["curveClearance"]
        require(graph_range and abs(graph_range["paddingRatio"] - .1) <= .001, f"graph must derive its offset from the 10% data-span ratio for {target}: {graph_range}")
        x_span = graph_range["xDataMax"] - graph_range["xDataMin"]
        y_span = graph_range["yDataMax"] - graph_range["yDataMin"]
        require(x_span > 0 and graph_range["xDomainMax"] - graph_range["xDataMax"] >= x_span * .095, f"graph x maximum lacks data-relative headroom for {target}: {graph_range}")
        require(y_span > 0 and graph_range["yDomainMax"] - graph_range["yDataMax"] >= y_span * .095 and graph_range["yDataMin"] - graph_range["yDomainMin"] >= y_span * .095, f"graph y range lacks data-relative headroom for {target}: {graph_range}")
        require(clearance and clearance["right"] >= clearance["frameWidth"] * .07 and clearance["top"] >= clearance["frameHeight"] * .07 and clearance["bottom"] >= clearance["frameHeight"] * .07, f"rendered curves remain too close to the plot frame for {target}: {clearance}")
        expected_legend_zone = "upper-right" if family == "linear-viscoelastic" else "lower-right"
        require(snapshot["sourceGraph"]["legendZone"] == expected_legend_zone and not snapshot["sourceGraph"]["legendOverlapsCurve"], f"{family} legend placement/curve clearance failed for {target}: {snapshot['sourceGraph']}")
        status_bar_top = snapshot["regions"]["statusBar"]["y"]
        graph_box = snapshot["sourceGraph"]["box"]
        axis_titles = snapshot["sourceGraph"]["axisTitles"]
        require(graph_box["bottom"] <= status_bar_top - 4, f"Fit source graph overlaps the status bar for {target}: graph={graph_box}, statusBar={snapshot['regions']['statusBar']}")
        require(axis_titles and all(title["box"]["bottom"] <= status_bar_top - 4 for title in axis_titles), f"Fit source axis title overlaps the status bar for {target}: titles={axis_titles}, statusBar={snapshot['regions']['statusBar']}")
        if family == "metal":
            require(snapshot["sourceGraph"]["positiveYield"], f"metal graph does not start at positive yield for {target}")

    require(not visual["technicalCountsVisible"], f"technical mapping counts leaked from Advanced for {target}")
    require(all(term not in visual["selectedModelText"] for term in ("Density", "Saved", "Pinned", "Fit result", "r1 ·")), f"Selected model exposes mapping or lifecycle detail for {target}: {visual['selectedModelText']}")
    require("Fit r1" not in snapshot["actions"]["visibleText"] and "r1 · Tensile" not in snapshot["actions"]["visibleText"], f"ambiguous Fit revision shorthand leaked into the normal Export surface for {target}")
    unit_control = snapshot["technical"]["unitControl"]
    require(unit_control is not None, f"Output unit system selector is missing for {target}")
    enabled_units = [option for option in unit_control["options"] if option["value"] and not option["disabled"]]
    unavailable_units = [option for option in unit_control["options"] if option["disabled"]]
    if state == "no-target-empty":
        require(unit_control["disabled"] and snapshot["technical"]["unitSystem"] == "", f"unit selector must be disabled without a destination for {target}: {unit_control}")
    else:
        require(not unit_control["disabled"] and snapshot["technical"]["unitSystem"] == "kg_m_s" and snapshot["technical"]["unitSystemLabel"] == "kg · m · s", f"selected exporter unit capability is inconsistent for {target}: {snapshot['technical']}")
    require(len(enabled_units) == 1 and enabled_units[0]["value"] == "kg_m_s", f"reference exporter must expose exactly one supported unit system for {target}: {unit_control}")
    require(any("unavailable" in option["label"].lower() for option in unavailable_units), f"unsupported unit capability is not discoverable without becoming selectable for {target}: {unit_control}")
    if state != "long-mapping":
        require(visual["mappingScroll"]["scrollHeight"] <= visual["mappingScroll"]["clientHeight"] + 1, f"normal mapping rows are clipped or unnecessarily scrollable for {target}: {visual['mappingScroll']}")
        require(not visual["mappingTitlesEllipsized"], f"normal mapping titles are clipped for {target}")
    return {"snapshot": snapshot, "visual": visual}


def validate_state_contract(page: Page, target: str, state: str, live: dict[str, Any], family: str = "metal") -> None:
    snap, visual = live["snapshot"], live["visual"]
    actions = snap["actions"]
    preflight = snap["preflight"]
    rows = preflight["rows"]
    statuses = [row["status"] for row in rows]
    texts = [row["text"] for row in rows]
    counts = preflight["counts"]
    require("Material State" not in " ".join(texts), f"Material State leaked into mapping rows for {target}")
    visible_text = actions["visibleText"].lower()
    forbidden_visible_terms = ("preflight", "mapping sheet", "next safe action", "receipt", "evidence")
    require(not any(term in visible_text for term in forbidden_visible_terms) and "SC-DEMO-00041" not in actions["visibleText"], f"undisclosed internal vocabulary leaked for {target}: {actions['visibleText']}")

    if state in {"preview-ready", "long-mapping", "delivered", "approximation-blocked"}:
        require(preflight["sourceState"] == "Available", f"selected model missing in {target}")
        require(preflight["source"]["model"], f"selected model identity is incomplete in {target}: {preflight['source']}")
        require(visibility(page, "[data-action='view-source']"), f"Open in Fit is missing in {target}")
        if family == "metal":
            require("7.80000000E+03" in visual["nativeText"] and "2.10000000E+11" in visual["nativeText"], f"metal native values missing in {target}")
        require("kg · m · s" in visual["nativeText"] and "stress in Pa" in visual["nativeText"], f"unit convention missing in native preview for {target}")
        expected_status = "Review required" if state == "approximation-blocked" else "Solver Card created" if state == "delivered" else "Ready to create"
        require(expected_status in preflight["checkStatus"], f"check status does not match state for {target}: {preflight['checkStatus']}")

    if family == "metal" and state in {"preview-ready", "long-mapping", "delivered"}:
        require(statuses.count("exact") == 2 and statuses.count("transformed") == 3 and statuses.count("approximated") == 1, f"metal visible mapping statuses disagree for {target}: {statuses}")
        require(counts.get("exact") == 2 and counts.get("transformed") == 3 and counts.get("approximated") == 1 and counts.get("not_applicable") == 2 and counts.get("unsupported", 0) == 0, f"technical mapping counts disagree for {target}: {counts}")
        require(preflight["advancedNotApplicable"] >= 2, f"Advanced not-applicable rows missing for {target}")
    if state == "long-mapping":
        require(len(rows) == 28, f"long mapping should expose 28 rows for {target}, got {len(rows)}")
        require(all("target field" in row["text"].lower() and "evidence" not in row["text"].lower() for row in rows), f"long Mapping details must use neutral target-field identifiers for {target}: {rows}")
        require(visual["mappingScroll"]["scrollHeight"] - visual["mappingScroll"]["clientHeight"] >= 10, f"long mapping rail is not discoverable for {target}")
        require(visual["nativeScroll"]["scrollHeight"] - visual["nativeScroll"]["clientHeight"] >= 10, f"long native preview rail is not discoverable for {target}")
        require(visual["mappingScroll"]["offsetWidth"] - visual["mappingScroll"]["clientWidth"] >= 10 and visual["mappingScroll"]["scrollbarGutter"] == "stable", f"long mapping must reserve a visible local rail for {target}")
        require(visual["nativeScroll"]["offsetWidth"] - visual["nativeScroll"]["clientWidth"] >= 10 and visual["nativeScroll"]["scrollbarGutter"] == "stable", f"long native preview must reserve a visible local rail for {target}")
        require(len(visual["scrollCues"]) == 2 and all(cue["visible"] and cue["width"] >= 8 and cue["height"] >= 80 and cue["thumbHeight"] >= 34 for cue in visual["scrollCues"]), f"long overflow must expose captured proportional scroll cues for {target}: {visual['scrollCues']}")
        require(not visual["mappingTitlesEllipsized"], f"long mapping titles are clipped for {target}")
    if state == "preview-ready":
        require(actions["action"] == "create-card" and not actions["disabled"] and not actions["acknowledgementVisible"], f"normal Create action contract failed for {target}: {actions}")
        require(actions["previewCurrent"] and "Current preview" in actions["previewState"], f"normal preview pointer failed for {target}")
    elif state == "source-blocked":
        require(preflight["sourceState"] == "Missing" and actions["action"] == "back-fit" and actions["text"] == "Back to Fit" and not actions["disabled"], f"source-blocked action contract failed for {target}: {actions}")
        require(not actions["previewCurrent"] and not visual["graphVisible"] and len(rows) == 1 and statuses == ["blocked"], f"source-blocked preview/mapping contract failed for {target}")
        require(counts.get("blockers") == 1 and all(counts.get(key, 0) == 0 for key in ("exact", "transformed", "approximated", "not_applicable")), f"source-blocked counts disagree for {target}: {counts}")
        require(actions["sourceMaterialDisabled"] and actions["fitSourceDisabled"], f"source links must be unavailable without an exact Fit source for {target}")
        require("No selected model" in actions["visibleText"] and "Swift / Voce blend (50/50)" not in actions["visibleText"], f"source-blocked Fit context leaks a stale source identity for {target}")
    elif state == "no-target-empty":
        technical = snap["technical"]
        require(preflight["targetState"] == "Choose destination", f"no-target Destination state is not empty for {target}: {preflight}")
        require(actions["action"] == "select-destination" and actions["text"] == "Select Destination" and not actions["disabled"], f"no-target primary action contract failed for {target}: {actions}")
        require(not actions["previewCurrent"] and actions["previewTarget"] == "No target selected", f"no-target preview pointer leaked for {target}: {actions}")
        require(preflight["mappingHeader"] == "" and rows == [] and technical["mappingPlaceholders"] == ["No mapping available"], f"no-target Mapping details must contain one neutral placeholder and zero mapping rows for {target}: {preflight}, {technical}")
        require(not technical["targetValue"] and not technical["version"] and not technical["unitSystem"] and not technical["tuple"] and not technical["digest"] and not technical["nativeText"], f"no-target target tuple/native values leaked for {target}: {technical}")
        require(all(value == 0 for value in counts.values()) and "blockers" not in counts, f"no-target must expose zero mapping counts for {target}: {preflight}")
        require(visual["graphVisible"] and preflight["sourceState"] == "Available" and actions["fitSourceOpenVisible"] and not actions["fitSourceDisabled"] and actions["fitSourceGraphOpacity"] == "1", f"no-target must preserve an active, undimmed upstream Fit source context for {target}: {visual}, {preflight}, {actions}")
    elif state == "approximation-blocked":
        require(actions["acknowledgementVisible"] and not actions["acknowledgementChecked"] and actions["action"] == "create-card" and actions["disabled"], f"approximation acknowledgement gate failed for {target}: {actions}")
        require("Review required" in preflight["checkStatus"] and "Confirm 1 approximation" in preflight["checkStatus"], f"approximation status copy failed for {target}")
        require(any(row["status"] == "approximated" and "Review" in row["text"] for row in rows), f"unchecked approximated row not visible for {target}")
        require(statuses.count("exact") == 3 and statuses.count("transformed") == 2 and statuses.count("approximated") == 1, f"OpenRadioss mapping rows disagree for {target}: {statuses}")
        require(counts.get("exact") == 3 and counts.get("transformed") == 2 and counts.get("approximated") == 1 and counts.get("not_applicable") == 2, f"OpenRadioss mapping counts disagree for {target}: {counts}")
        unit_row = next((row for row in rows if row["title"] == "Unit convention"), None)
        require(unit_row is not None and unit_row["status"] == "exact" and "Exact" in unit_row["text"], f"OpenRadioss unit convention must be exact for {target}")
    elif state == "delivery-error":
        require(actions["action"] == "retry-create" and actions["text"] == "Retry create" and not actions["disabled"], f"delivery-error primary recovery contract failed for {target}: {actions}")
        require(actions["recoveryActions"] == ["retry-create"] and not actions["retryVisible"] and not actions["runCheckVisible"], f"delivery-error must expose exactly one Retry create recovery for {target}: {actions}")
    elif state == "delivered":
        require(actions["action"] == "open-card" and actions["deliveryDetailsVisible"] and actions["previewCurrent"] and actions["deliveryCount"] == 1 and actions["deliveryPointer"] == "SC-DEMO-00041", f"delivered Solver Card/action contract failed for {target}: {actions}")
        require("Delivered" in actions["previewState"], f"delivered preview state missing for {target}")
        require("receipt" not in visible_text and "SC-DEMO-00041" not in actions["visibleText"], f"receipt vocabulary or identity leaked before Delivery details for {target}")


def validate_target(browser: Browser, target: str, expected: dict[str, Any], staging_target: dict[str, Any]) -> dict[str, Any]:
    state = expected["state"]
    viewport = expected["viewport"]
    image = ROOT / staging_target["image"]
    image_info = image_record(image, staging_target["sha256"], (viewport["width"], viewport["height"]))
    require(staging_target.get("status") == "pending" and staging_target.get("main_agent_evaluation", {}).get("status") == "pending" and staging_target.get("product_owner_approval", {}).get("status") == "absent", f"pending lifecycle missing for {target}")
    measurements = ROOT / staging_target["measurements"]
    require(measurements.is_file(), f"missing measurement file for {target}")
    measured = json.loads(measurements.read_text(encoding="utf-8"))
    require(measured.get("image_sha256") == image_info["sha256"] and measured.get("status") == "pending", f"measurement hash/lifecycle mismatch for {target}")
    require(measured.get("viewport", {}).get("width") == viewport["width"] and measured.get("viewport", {}).get("height") == viewport["height"], f"measurement viewport mismatch for {target}")
    page, console_errors, page_errors = open_page(browser, state, viewport)
    try:
        live = validate_geometry(page, target, state, viewport)
        validate_state_contract(page, target, state, live)
        require(console_errors == [] and page_errors == [], f"browser errors for {target}: {console_errors} / {page_errors}")
        require(measured.get("console_errors", []) == [] and measured.get("page_errors", []) == [], f"recorded browser errors for {target}")
        return {"target": target, "image": image_info, "live": live}
    finally:
        page.close()


def validate_interactions(browser: Browser) -> dict[str, Any]:
    page, console_errors, page_errors = open_page(browser, "preview-ready", VIEWPORTS["1440x900"])
    try:
        resizer = page.locator(".export-divider-resizer")
        initial = resizer.get_attribute("aria-valuenow")
        resizer.focus()
        page.keyboard.press("ArrowRight")
        arrow = resizer.get_attribute("aria-valuenow")
        page.keyboard.press("Home")
        home = resizer.get_attribute("aria-valuenow")
        page.keyboard.press("End")
        end = resizer.get_attribute("aria-valuenow")
        require(initial == "320" and arrow == "328" and home == "300" and end == "360", f"splitter keyboard path failed: {initial}/{arrow}/{home}/{end}")
        toggle = page.locator("[data-action='toggle-properties']")
        toggle.click()
        require(page.locator("[data-region='properties']").get_attribute("hidden") is not None, "setup collapse did not hide pane")
        toggle.click()
        require(page.locator("[data-region='properties']").get_attribute("hidden") is None, "setup restore did not show pane")
        unit_control = page.locator("[data-unit-system-select]")
        unit_options = unit_control.locator("option")
        require(not unit_control.is_disabled() and unit_control.input_value() == "kg_m_s", "supported Output unit system is not selected")
        require(unit_options.count() == 3 and unit_options.nth(2).get_attribute("disabled") is not None, "unavailable unit capability is not visible as a disabled option")
        page.locator("[data-target-select]").select_option("openradioss")
        require(page.locator("body").get_attribute("data-preview-current") == "false" and not page.locator("[data-approximation-ack]").is_checked() and page.locator("body").get_attribute("data-delivery-pointer") == "", "target change did not invalidate current preview")
        page.locator("[data-action='run-check']").click()
        require(page.locator("body").get_attribute("data-state") == "approximation-blocked" and page.locator("[data-action='create-card']").is_disabled(), "OpenRadioss check did not require acknowledgement")
        page.locator("[data-approximation-ack]").check()
        require(not page.locator("[data-action='create-card']").is_disabled(), "acknowledgement did not enable create")
        page.locator("[data-action='create-card']").click()
        require(page.locator("body").get_attribute("data-delivery-pointer") == "SC-DEMO-00041", "create did not create immutable Solver Card pointer")
        require(page.locator(".primary-action").get_attribute("data-action") == "open-card" and page.locator("body").get_attribute("data-delivery-count") == "1", "duplicate submit was not converted to open-card")
        require("receipt" not in page.locator("body").inner_text().lower(), "receipt leaked before Delivery details was opened")
        page.locator("[data-action='delivery-details']").click()
        require("receipt SC-DEMO-00041" in page.locator("#interaction-status").inner_text(), "Delivery details did not disclose the receipt identity")
        page.locator("[data-action='advanced']").click()
        require(page.locator("[data-advanced-disclosure]").get_attribute("open") is not None, "Advanced disclosure did not open")
        return {"resize": {"initial": initial, "arrow": arrow, "home": home, "end": end}, "collapse_restore": True, "unit_capability_discoverable": True, "target_invalidation": True, "acknowledgement_gate": True, "immutable_delivery": True, "receipt_disclosed_only_after_action": True, "console_errors": console_errors, "page_errors": page_errors}
    finally:
        page.close()


def validate_state_evidence(staging: dict[str, Any]) -> dict[str, int]:
    require(STATE_EVIDENCE_PATH.is_file(), f"missing state evidence: {STATE_EVIDENCE_PATH.relative_to(ROOT)}")
    state_evidence = json.loads(STATE_EVIDENCE_PATH.read_text(encoding="utf-8"))
    result: dict[str, int] = {}
    for name, state in EVIDENCE_STATES.items():
        expected_viewports = EVIDENCE_VIEWPORTS[name]
        record = staging.get("state_evidence", {}).get(name, {})
        require(record.get("state") == state, f"state evidence state mismatch: {name}")
        captures = state_evidence.get(name, {}).get("captures", [])
        require(len(captures) == len(expected_viewports), f"state {name} must have {len(expected_viewports)} viewport captures")
        by_viewport = {capture.get("viewport", {}).get("width"): capture for capture in captures}
        for viewport_name in expected_viewports:
            viewport = VIEWPORTS[viewport_name]
            capture = by_viewport.get(viewport["width"])
            require(capture is not None, f"missing {name}/{viewport_name} state capture")
            image = ROOT / capture["image"]
            info = image_record(image, capture["image_sha256"], (viewport["width"], viewport["height"]))
            require(capture.get("status") == "pending" and capture.get("main_agent_evaluation", {}).get("status") == "pending" and capture.get("product_owner_approval", {}).get("status") == "absent", f"state lifecycle incomplete for {name}/{viewport_name}")
            require(capture.get("console_errors", []) == [] and capture.get("page_errors", []) == [], f"browser errors recorded for {name}/{viewport_name}")
            require(all(value == 0 for value in capture.get("overflow", {}).values()), f"overflow recorded for {name}/{viewport_name}: {capture.get('overflow')}")
            measurement = ROOT / f"docs/17-evidence/images/issue-167-service-reference/{capture['target']}.measurements.json"
            require(measurement.is_file(), f"missing state measurement {capture['target']}")
            measured = json.loads(measurement.read_text(encoding="utf-8"))
            require(measured.get("image_sha256") == info["sha256"] and measured.get("status") == "pending", f"state measurement mismatch {capture['target']}")
        canonical = record.get("canonical_1440")
        if name in CANONICAL_1440_BINDINGS:
            require(canonical and canonical.get("target") == CANONICAL_1440_BINDINGS[name] and canonical.get("viewport", {}).get("width") == 1440 and canonical.get("viewport", {}).get("height") == 900, f"canonical 1440 binding missing for {name}")
        result[name] = len(captures)
    return result


def validate_family_adaptations(browser: Browser, staging: dict[str, Any]) -> dict[str, str]:
    results: dict[str, str] = {}
    for family, target in FAMILY_ADAPTATIONS.items():
        record = staging.get("family_adaptations", {}).get(family, {})
        require(record.get("family") == family and record.get("status") == "evidence-only", f"family adaptation record incomplete: {family}")
        image = ROOT / record["image"]
        image_info = image_record(image, record["sha256"], (1440, 900))
        measurement = ROOT / record["measurements"]
        require(measurement.is_file(), f"missing family adaptation measurement: {family}")
        measured = json.loads(measurement.read_text(encoding="utf-8"))
        require(measured.get("image_sha256") == image_info["sha256"] and measured.get("status") == "pending", f"family adaptation measurement mismatch: {family}")
        page, console_errors, page_errors = open_page(browser, "preview-ready", VIEWPORTS["1440x900"], family)
        try:
            live = validate_geometry(page, target, "preview-ready", VIEWPORTS["1440x900"], family)
            validate_state_contract(page, target, "preview-ready", live, family)
            require(console_errors == [] and page_errors == [], f"browser errors for family {family}")
            titles = {row["title"] for row in live["snapshot"]["preflight"]["rows"]}
            require(titles != {"Density", "Isotropic elasticity", "Initial yield", "Hardening response", "Unit convention", "Post-necking extension"}, f"family {family} reused metal mapping rows")
            rows = live["snapshot"]["preflight"]["rows"]
            statuses = [row["status"] for row in rows]
            counts = live["snapshot"]["preflight"]["counts"]
            require(statuses.count("approximated") == 0 and counts.get("approximated") == 0, f"family {family} incorrectly exposes an approximation for the Abaqus target")
            require("Ready to create" in live["snapshot"]["preflight"]["checkStatus"] and "No blockers" in live["snapshot"]["preflight"]["checkStatus"], f"family {family} readiness does not match its zero-blocker mapping set")
            require("acknowledg" not in live["snapshot"]["preflight"]["checkStatus"].lower() and "acknowledg" not in live["snapshot"]["preflight"]["checkSummary"].lower(), f"family {family} claims an acknowledgement with no approximation")
            require("Unit convention" in titles and "transformed" in statuses, f"family {family} must visibly retain its Unit convention consequence")
            if family == "linear-viscoelastic":
                require(len(rows) == 5 and statuses.count("exact") == 4 and statuses.count("transformed") == 1, f"linear-viscoelastic rows/counts are incomplete: {rows}")
            if family == "hyperelastic":
                require(len(rows) == 5 and statuses.count("exact") == 4 and statuses.count("transformed") == 1, f"hyperelastic rows/counts are incomplete: {rows}")
            results[family] = image_info["sha256"]
        finally:
            page.close()
    return results


def validate_dependencies(staging: dict[str, Any]) -> None:
    dependencies = staging.get("dependencies", {})
    fit_path = ROOT / "docs/00-research/ux-service-reference/modeling-fit-wave03.staging.json"
    card_path = ROOT / "docs/17-evidence/images/issue-167-service-reference/materials-card-wave02.staging.json"
    require(dependencies.get("MOD-FIT", {}).get("staging") == str(fit_path.relative_to(ROOT)).replace("\\", "/"), "MOD-FIT dependency path changed")
    require(dependencies.get("MAT-CARD", {}).get("staging") == str(card_path.relative_to(ROOT)).replace("\\", "/"), "MAT-CARD dependency path changed")
    if fit_path.is_file():
        fit = json.loads(fit_path.read_text(encoding="utf-8"))
        require(dependencies["MOD-FIT"].get("target_sha256") == {key: value.get("sha256") for key, value in fit.get("targets", {}).items()}, "MOD-FIT dependency hashes drifted")
    if card_path.is_file():
        card = json.loads(card_path.read_text(encoding="utf-8"))
        require(dependencies["MAT-CARD"].get("target_sha256") == {item.get("id"): item.get("image_sha256") for item in card.get("references", [])}, "MAT-CARD dependency hashes drifted")


def main() -> None:
    args = parse_args()
    require(args.target or args.all_packet_targets, "provide --target or --all-packet-targets")
    require(HTML_PATH.is_file(), f"missing static HTML: {HTML_PATH}")
    require(STAGING_PATH.is_file(), f"missing staging: {STAGING_PATH}")
    staging = json.loads(STAGING_PATH.read_text(encoding="utf-8"))
    require(staging.get("family") == "MOD-EXPORT", f"staging family must be MOD-EXPORT, got {staging.get('family')}")
    require(staging.get("status") == args.expect_main_agent_status, f"staging status {staging.get('status')} != {args.expect_main_agent_status}")
    selected = list(TARGETS) if args.all_packet_targets else [args.target]
    require(all(target in TARGETS for target in selected), "unknown target selection")
    staging_targets = staging.get("targets", {})
    if args.all_packet_targets:
        require(set(staging_targets) == set(TARGETS), f"staging target set mismatch: {set(staging_targets)}")
    results = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            for target in selected:
                results.append(validate_target(browser, target, TARGETS[target], staging_targets.get(target, {})))
            interactions = validate_interactions(browser) if args.all_packet_targets else {}
            family_results = validate_family_adaptations(browser, staging) if args.all_packet_targets else {}
        finally:
            browser.close()
    validate_dependencies(staging)
    state_results = validate_state_evidence(staging) if args.all_packet_targets else {}
    checklist = staging.get("qualitative_owner_checklist", {})
    for key in (f"Q-{index:02d}" for index in range(1, 17)):
        require(checklist.get(key, {}).get("status") in {"pass", "not-applicable"}, f"qualitative checklist {key} is missing/pass-fail: {checklist.get(key)}")
    print(f"VALIDATED {len(results)} MOD-EXPORT approval target(s)")
    target_summary = [{"target": result["target"], "viewport": f"{result['image']['width']}x{result['image']['height']}", "sha256": result["image"]["sha256"]} for result in results]
    print(f"TARGETS {json.dumps(target_summary, ensure_ascii=False)}")
    if args.all_packet_targets:
        print(f"STATE_EVIDENCE {json.dumps(state_results, ensure_ascii=False)}")
        print(f"FAMILY_ADAPTATIONS {json.dumps(family_results, ensure_ascii=False)}")
        print(f"INTERACTIONS {json.dumps(interactions, ensure_ascii=False)}")
    print("PASS zero overflow/errors, capability-backed unit selector, exact tuple/native units, mapping counts, responsive topology, family adaptation, state gates, local scroll rails, accessibility and pending lifecycle")


if __name__ == "__main__":
    main()

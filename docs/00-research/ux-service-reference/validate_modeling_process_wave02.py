from __future__ import annotations

# ruff: noqa: E501
import argparse
import hashlib
import json
import struct
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
EVIDENCE_DIR = ROOT / "docs/17-evidence/images/issue-167-service-reference"
HTML = ROOT / "docs/00-research/ux-service-reference/modeling-process-normal.html"
CSS = ROOT / "docs/00-research/ux-service-reference/modeling-process.css"
JAVASCRIPT = ROOT / "docs/00-research/ux-service-reference/modeling-process.js"
CAPTURE = ROOT / "docs/00-research/ux-service-reference/capture_modeling_process_wave02.py"
STAGING = ROOT / "docs/00-research/ux-service-reference/modeling-process-wave02.staging.json"

TARGETS = {
    "modeling-process-normal-1366x768": {"state": "normal", "viewport": {"width": 1366, "height": 768, "device_scale_factor": 1}, "navigator": 184},
    "modeling-process-normal-1440x900": {"state": "normal", "viewport": {"width": 1440, "height": 900, "device_scale_factor": 1}, "navigator": 192},
    "modeling-process-normal-1920x1080": {"state": "normal", "viewport": {"width": 1920, "height": 1080, "device_scale_factor": 1}, "navigator": 208},
    "modeling-process-prerequisite-blocked-1440x900": {"state": "prerequisite-blocked", "viewport": {"width": 1440, "height": 900, "device_scale_factor": 1}, "navigator": 192},
}
SUPPORT_TARGETS = {
    "modeling-process-normal-2560x1440": {"state": "normal", "viewport": {"width": 2560, "height": 1440, "device_scale_factor": 1}, "navigator": 208},
    "modeling-process-normal-3840x2160": {"state": "normal", "viewport": {"width": 3840, "height": 2160, "device_scale_factor": 1}, "navigator": 208},
}


def fail(message: str) -> None:
    raise AssertionError(message)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate MOD-PROCESS WAVE-02 static service reference evidence.")
    parser.add_argument("--target", choices=sorted(TARGETS), help="Validate one target.")
    parser.add_argument("--all-packet-targets", action="store_true", help="Validate all four targets and evidence.")
    parser.add_argument("--expect-main-agent-status", default=None, help="Expected writer staging lifecycle status.")
    return parser.parse_args()


def png_dimensions(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n" or len(data) < 24:
        fail(f"not a PNG: {path}")
    return struct.unpack(">II", data[16:24])


def read_measurement(target: str) -> dict[str, Any]:
    path = EVIDENCE_DIR / f"{target}.measurements.json"
    if not path.is_file():
        fail(f"missing measurements: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        fail(f"invalid measurements {path}: {error}")


def assert_sources() -> None:
    for path in (HTML, CSS, JAVASCRIPT, CAPTURE, STAGING):
        if not path.is_file():
            fail(f"missing packet-owned source: {path}")
    source = HTML.read_text(encoding="utf-8")
    for required in ("reference.css", "modeling-process.css", "modeling-process.js", "Save processed curves", "Preview changes", "Advanced / Evidence"):
        if required not in source:
            fail(f"HTML missing required contract text: {required}")
    if "hardening" in source.lower() or "metal.hardening_fit" in source.lower():
        fail("Process reference incorrectly includes Fit hardening step")
    if 'class="curve-row selected" role="button"' in source or 'class="curve-row" role="button"' in source:
        fail("curve rows must remain non-interactive wrappers")
    if "preserveAspectRatio=\"none\"" in source or "0 0 1000 500" in source or "0 0 1000 500" in JAVASCRIPT.read_text(encoding="utf-8"):
        fail("Process plot still uses the forbidden fixed 1000x500/non-uniform SVG contract")
    javascript = JAVASCRIPT.read_text(encoding="utf-8")
    for required in ("ResizeObserver", "renderModelingProcessPlot", "Engineering stress (MPa)", "Engineering strain [1]", "finite-plotted-span-plus-proportional-headroom", "data-relative"):
        if required not in javascript:
            fail(f"Process renderer missing required responsive graph contract: {required}")
    combined = source + CSS.read_text(encoding="utf-8") + javascript
    for forbidden in ("Processed response", "processed-response", "renderProcessedResponseGrid", "min-width: 3000px"):
        if forbidden in combined:
            fail(f"retired Process wide response-grid contract remains: {forbidden}")


def assert_common(target: str, config: dict[str, Any], measurements: dict[str, Any]) -> None:
    image = EVIDENCE_DIR / f"{target}.png"
    if not image.is_file():
        fail(f"missing target PNG: {image}")
    if png_dimensions(image) != (config["viewport"]["width"], config["viewport"]["height"]):
        fail(f"{target} PNG dimensions do not match target viewport: {png_dimensions(image)}")
    digest = hashlib.sha256(image.read_bytes()).hexdigest()
    if measurements.get("target") != target or measurements.get("state") != config["state"] or measurements.get("viewport") != config["viewport"]:
        fail(f"{target} measurement target/state/viewport mismatch")
    if measurements.get("image_sha256") != digest:
        fail(f"{target} image SHA-256 mismatch")
    if measurements.get("console_errors") or measurements.get("page_errors"):
        fail(f"{target} browser errors: console={measurements.get('console_errors')!r}, page={measurements.get('page_errors')!r}")
    overflow = measurements.get("overflow") or {}
    if any(value != 0 for value in overflow.values()):
        fail(f"{target} document/body overflow: {overflow}")
    geometry = measurements.get("geometry") or {}
    regions = geometry.get("regions") or {}
    for name in ("applicationBar", "context", "stageStrip", "navigator", "divider", "main", "ribbon", "graph", "statusBar"):
        if not regions.get(name):
            fail(f"{target} missing geometry region {name}")
    divider = geometry.get("divider") or {}
    if not (divider.get("ariaMin") == 180 and divider.get("ariaMax") == 240 and divider.get("ariaExpanded")):
        fail(f"{target} divider ARIA range/state is not truthful: {divider}")
    if divider.get("visibleWidth") != 5:
        fail(f"{target} divider hit width must be 5px: {divider}")
    visible = geometry.get("visibleContent") or {}
    language = geometry.get("productLanguage") or {}
    primary_text = language.get("primaryWorkspaceText") or ""
    forbidden_primary_terms = ("Mapping Profile", "CMP-", "robust_huber", "immutable output", "stale pointers", "Recipe details", "active job")
    if any(term.lower() in primary_text.lower() for term in forbidden_primary_terms):
        fail(f"{target} primary workspace exposes internal product language: {primary_text!r}")
    exact_contracts = language.get("exactContracts") or {}
    if config["state"] == "normal":
        if any(exact_contracts.get(key) != "CMP-DEMO-DP780-TEST-JSON-03" for key in ("sourceTestData", "graphTestData", "statusTestData")):
            fail(f"{target} no longer retains the exact Test Data contract in metadata: {exact_contracts}")
        for required in ("Saved Test Data", "calculated method", "preview not saved", "Fit and Export remain unchanged until the processing result is saved"):
            if required.lower() not in primary_text.lower():
                fail(f"{target} primary workspace is missing required task language {required!r}: {primary_text!r}")
        if visible.get("statusSelection") != "DP780 tensile · 293 K" or visible.get("statusRevision") != "Saved Test Data · Revision 1":
            fail(f"{target} normal status bar must separate curve-set identity from the saved Test Data revision: {visible}")
    else:
        if exact_contracts.get("blockedTestData") != "CMP-DEMO-DP780-TEST-JSON-03" or exact_contracts.get("blockedNoFallback") != "true":
            fail(f"{target} blocked state no longer retains exact prerequisite metadata: {exact_contracts}")
        if "return to data and choose compatible saved test data" not in primary_text.lower():
            fail(f"{target} blocked recovery does not use the required task language: {primary_text!r}")
    if visible.get("stageLabels") != ["Data", "Process", "Fit", "Export"] or visible.get("activeStage") != "Process":
        fail(f"{target} stage strip mismatch: {visible.get('stageLabels')!r}, active={visible.get('activeStage')!r}")
    if geometry.get("nestedCards", 0) != 0:
        fail(f"{target} nested-card hard gate failed")
    working_cluster_width = regions["graph"].get("width", 0)
    if config["viewport"]["width"] >= 2200:
        settings_width = (regions.get("settingsGrid") or {}).get("width", 0)
        if working_cluster_width < settings_width * .95 or regions["graph"].get("height", 0) < (regions.get("settingsGrid") or {}).get("height", 0) * 3:
            fail(f"{target} bounded graph is not dominant within the wide task cluster: graph={regions['graph']}, settings={regions.get('settingsGrid')}")
    elif working_cluster_width <= regions["ribbon"].get("width", 0) * .72:
        fail(f"{target} graph is not dominant: graph={regions['graph']}, ribbon={regions['ribbon']}")
    typography = geometry.get("typography") or {}
    if typography.get("bodyPx") != 13:
        fail(f"{target} body typography is not the 13px system: {typography}")
    setting_metadata = typography.get("settingSmall") or []
    if not setting_metadata:
        fail(f"{target} missing computed setting metadata typography: {typography}")
    if any(item.get("fontSizePx") != 12 or item.get("lineHeightPx", 0) < 14 for item in setting_metadata):
        fail(f"{target} setting metadata is below the readable 12px/14px minimum: {setting_metadata}")
    if any(item.get("clipped") for item in setting_metadata):
        fail(f"{target} readable setting metadata is clipped after typography restoration: {setting_metadata}")
    settings_grid = regions.get("settingsGrid") or {}
    if settings_grid.get("bottom", 0) > regions["ribbon"].get("bottom", 0):
        fail(f"{target} settings escape the shallow process ribbon: settings={settings_grid}, ribbon={regions['ribbon']}")
    if target in {"modeling-process-normal-2560x1440", "modeling-process-normal-3840x2160"}:
        cap_measurement = read_measurement("modeling-process-normal-1920x1080")
        cap_canvas = ((cap_measurement.get("geometry") or {}).get("regions") or {}).get("graphCanvas") or {}
        wide_canvas = regions.get("graphCanvas") or {}
        if wide_canvas.get("width", 0) > cap_canvas.get("width", 0) + 16 or wide_canvas.get("height", 0) > cap_canvas.get("height", 0) + 16:
            fail(f"{target} graph exceeds the 1920 useful-size cap: wide={wide_canvas}, cap={cap_canvas}")
        if target == "modeling-process-normal-2560x1440" and wide_canvas.get("x", 0) > regions["main"].get("x", 0) + 12:
            fail(f"{target} capped graph is not left-aligned below its toolbar: graph={wide_canvas}, main={regions['main']}")
    if target == "modeling-process-normal-3840x2160":
        if abs(settings_grid.get("width", 0) - 1707) > 1 or settings_grid.get("x") > regions["ribbon"].get("x", 0) + 12:
            fail(f"{target} wide settings ribbon does not preserve the 1920 width at its start: settings={settings_grid}, ribbon={regions['ribbon']}")
    if regions["ribbon"].get("bottom", 0) > regions["graph"].get("y", 0):
        fail(f"{target} process ribbon overlaps the persistent graph: ribbon={regions['ribbon']}, graph={regions['graph']}")
    plot = geometry.get("graph") or {}
    coordinate = plot.get("coordinateSystem") or {}
    graph_canvas = regions.get("graphCanvas") or {}
    if coordinate.get("viewBox", [])[:2] != [0, 0] or coordinate.get("widthDelta", 99) > 0.5 or coordinate.get("heightDelta", 99) > 0.5:
        fail(f"{target} SVG coordinate system does not match measured CSS-pixel graph canvas: {coordinate}")
    if abs(coordinate.get("width", 0) - graph_canvas.get("width", 0)) > 0.5 or abs(coordinate.get("height", 0) - graph_canvas.get("height", 0)) > 0.5:
        fail(f"{target} SVG dimensions do not match graph canvas: svg={coordinate}, canvas={graph_canvas}")
    series = plot.get("series") or {}
    if series.get("derivation") != "finite-plotted-span-plus-proportional-headroom":
        fail(f"{target} graph bounds are not data-relative: {series}")
    if not series.get("sourceStrain") or not series.get("observedSeries") or not series.get("processedSeries") or not series.get("elasticFit"):
        fail(f"{target} finite graph data arrays were not recorded: {series}")
    if series.get("computedMaxStrain", 0) <= series.get("maxStrain", 0) or series.get("computedMaxStressMpa", 0) <= series.get("maxStressMpa", 0):
        fail(f"{target} graph headroom does not clear finite extrema: {series}")
    if series.get("niceStepStrain", 0) <= 0 or series.get("niceStepStressMpa", 0) <= 0 or len(series.get("ticksStrain") or []) < 3 or len(series.get("ticksStressMpa") or []) < 3:
        fail(f"{target} readable nice tick intervals are missing: {series}")
    clearances = series.get("pointFrameClearances") or {}
    if min((clearances.get("right", 0), clearances.get("top", 0))) < 4:
        fail(f"{target} finite extrema are too close to the frame: {clearances}")
    graph_typography = plot.get("typography") or {}
    if graph_typography.get("tickFontSizes") != [11] or graph_typography.get("titleFontSizes") != [12]:
        fail(f"{target} graph tick/title typography is not stable 11/12px: {graph_typography}")
    if graph_typography.get("nonScalingStrokeCount", 0) < 7:
        fail(f"{target} graph strokes are not explicitly non-scaling: {graph_typography}")


def assert_normal(target: str, config: dict[str, Any], measurements: dict[str, Any]) -> None:
    assert_common(target, config, measurements)
    geometry = measurements["geometry"]
    regions = geometry["regions"]
    visible = geometry["visibleContent"]
    if regions["navigator"]["width"] != config["navigator"]:
        fail(f"{target} default navigator width is not {config['navigator']}: {regions['navigator']}")
    if visible.get("curveRows") != ["Specimen 01", "Specimen 02", "Specimen 03"]:
        fail(f"{target} curve rail identity mismatch: {visible.get('curveRows')!r}")
    if visible.get("includedCurves") != ["Specimen 01", "Specimen 02"]:
        fail(f"{target} inclusion membership mismatch: {visible.get('includedCurves')!r}")
    required_ops = ("Resolve duplicate x values", "Elastic modulus", "Offset proof stress", "Necking boundary", "Engineering → true / plastic")
    operation_labels = visible.get("operationLabels") or []
    if len(operation_labels) != 5 or not all(any(required in label for label in operation_labels) for required in required_ops):
        fail(f"{target} ordered Process operations mismatch: {operation_labels!r}")
    if "Elastic modulus" not in (visible.get("selectedOperation") or "") or visible.get("processTitle") != "Step 2 · Elastic modulus":
        fail(f"{target} Elastic modulus focus missing: {visible}")
    if len(visible.get("graphCurves") or []) != 5:
        fail(f"{target} graph must keep observed, processed and fit overlays distinguishable: {visible.get('graphCurves')!r}")
    if not visible.get("plotLegend"):
        fail(f"{target} graph legend is not visible")
    plot = geometry.get("graph") or {}
    series = plot.get("series") or {}
    if series.get("derivation") != "finite-plotted-span-plus-proportional-headroom" or series.get("computedMaxStrain", 0) <= series.get("maxStrain", 0) or series.get("computedMaxStressMpa", 0) <= series.get("maxStressMpa", 0):
        fail(f"{target} data-relative graph bounds/headroom missing: {series}")
    if plot.get("width", 0) < 700:
        fail(f"{target} plot width unexpectedly small: {plot}")
    response = geometry.get("processedResponse") or {}
    if response.get("visible") or response.get("rows") or (regions.get("processedResponse") or {}).get("width", 0):
        fail(f"{target} retired Processed response grid remains visible or mounted: {response}")
    viewport_width = config["viewport"]["width"]
    if viewport_width >= 2200:
        graph_region = regions["graph"]
        graph_canvas = regions["graphCanvas"]
        settings_grid = regions["settingsGrid"]
        save_button = regions.get("saveButton") or {}
        if abs(graph_region.get("width", 0) - 1707) > 1 or abs(graph_canvas.get("width", 0) - 1689) > 1 or abs(graph_canvas.get("height", 0) - 680) > 1:
            fail(f"{target} wide Process graph does not preserve the exact 1920 useful pixel size: graph={graph_region}, canvas={graph_canvas}")
        if abs(graph_region.get("right", 0) - settings_grid.get("right", 0)) > 1:
            fail(f"{target} wide Process graph does not align with the bounded settings band: graph={graph_region}, settings={settings_grid}")
        if not save_button or abs(graph_canvas.get("right", 0) - save_button.get("right", 0)) > 1:
            fail(f"{target} Process plot right edge does not align with Save processed curves: canvas={graph_canvas}, save={save_button}")
    elif viewport_width == 1920:
        graph_canvas = regions["graphCanvas"]
        save_button = regions.get("saveButton") or {}
        if not save_button or abs(graph_canvas.get("right", 0) - save_button.get("right", 0)) > 1:
            fail(f"{target} 1920 alignment reference changed: canvas={graph_canvas}, save={save_button}")
    controls = geometry.get("controls") or {}
    if len(controls.get("previewButtons") or []) != 1 or controls["previewButtons"][0].get("text") != "Preview changes":
        fail(f"{target} title-row Preview changes command missing or duplicated: {controls}")
    if not controls.get("save") or controls["save"].get("text") != "Save processed curves":
        fail(f"{target} sole Save processed curves command missing: {controls}")
    contract = geometry.get("plotContract") or {}
    if contract.get("footerPresent") or not contract.get("legendContained") or not contract.get("legendInPlot") or contract.get("legendCurveIntersect") or contract.get("legendAxisIntersect") or contract.get("legendTitleIntersect"):
        fail(f"{target} internal curve legend is not collision-free: {contract}")
    if set(visible.get("plotLegendLabels") or []) != {"Observed input", "Processed preview", "Calculated elastic fit"}:
        fail(f"{target} legend must identify only the three curve series: {visible.get('plotLegendLabels')!r}")
    if set(visible.get("axisTitles") or []) != {"Engineering stress (MPa)", "Engineering strain [1]"}:
        fail(f"{target} exact engineering axis titles are missing: {visible.get('axisTitles')!r}")
    tick_labels = visible.get("tickLabels") or []
    if not tick_labels or any(not label.replace(",", "").replace(".", "", 1).isdigit() for label in tick_labels):
        fail(f"{target} axis ticks must be numeric only: {tick_labels!r}")
    if any("show" not in label.lower() and "hide" not in label.lower() for label in controls.get("visibilityButtons") or []):
        fail(f"{target} icon-only visibility labels missing: {controls.get('visibilityButtons')!r}")
    exercise = measurements.get("exercise") or {}
    accessibility = exercise.get("accessibility") or {}
    if accessibility.get("hide_specimen_02_button_count") != 1:
        fail(f"{target} requires exactly one Hide Specimen 02 visibility button: {accessibility}")
    if (
        accessibility.get("specimen_02_selection_button_count") != 1
        or accessibility.get("specimen_02_selection_button_name") != "Select Specimen 02 curve"
        or not accessibility.get("specimen_02_selection_name_distinct")
    ):
        fail(f"{target} Specimen 02 curve selection button is missing a distinct accessible name: {accessibility}")
    if accessibility.get("nested_interactive_elements"):
        fail(f"{target} nested interactive elements found: {accessibility['nested_interactive_elements']}")
    if exercise.get("selected_curve") != "Specimen 03":
        fail(f"{target} keyboard/row selection consequence missing: {exercise}")
    if exercise.get("pointer_selected_curve") != "Specimen 02":
        fail(f"{target} pointer curve selection consequence missing: {exercise}")
    if not exercise.get("keyboard_selection_preserves_controls"):
        fail(f"{target} keyboard curve selection changed inclusion or visibility: {exercise}")
    if not exercise.get("visibility_preserves_preview_state"):
        fail(f"{target} plot visibility incorrectly invalidates processing state: {exercise}")
    if not exercise.get("operation_change_stale"):
        fail(f"{target} operation change did not stale the preview: {exercise}")
    if not exercise.get("setting_change_stale"):
        fail(f"{target} setting change did not stale preview: {exercise}")
    if exercise.get("preview_state") != "current" or exercise.get("commit_state") != "saved":
        fail(f"{target} preview/commit state sequence incomplete: {exercise}")
    if not exercise.get("duplicate_commit_guard") or exercise.get("commit_count") != 1:
        fail(f"{target} duplicate commit guard failed: {exercise}")
    if not exercise.get("advanced_open"):
        fail(f"{target} Advanced/Evidence disclosure interaction missing: {exercise}")
    long_rail = exercise.get("long_rail") or {}
    if not long_rail.get("independent_scroll") or not long_rail.get("graph_unchanged"):
        fail(f"{target} long rail did not scroll independently with graph topology preserved: {long_rail}")
    divider = exercise.get("divider") or {}
    if (divider.get("arrow_right", {}).get("divider", {}).get("ariaNow") or 0) <= (divider.get("initial", {}).get("divider", {}).get("ariaNow") or 0):
        fail(f"{target} divider ArrowRight did not increase aria value: {divider}")
    if divider.get("home", {}).get("divider", {}).get("ariaNow") != 180 or divider.get("end", {}).get("divider", {}).get("ariaNow") != 240:
        fail(f"{target} divider Home/End range failed: {divider}")
    if divider.get("collapsed", {}).get("divider", {}).get("ariaExpanded") or not divider.get("restored", {}).get("divider", {}).get("ariaExpanded"):
        fail(f"{target} divider collapse/restore failed: {divider}")


def assert_blocked(target: str, config: dict[str, Any], measurements: dict[str, Any]) -> None:
    assert_common(target, config, measurements)
    geometry = measurements["geometry"]
    visible = geometry["visibleContent"]
    regions = geometry["regions"]
    if regions["navigator"]["width"] != 192:
        fail(f"{target} blocked navigator width changed topology: {regions['navigator']}")
    if visible.get("curveRows"):
        fail(f"{target} blocked state shows fake compatible curves: {visible.get('curveRows')!r}")
    if not visible.get("graphBlocked") or visible.get("graphCurves"):
        fail(f"{target} blocked graph incorrectly shows a believable processed result: {visible}")
    if not visible.get("blockedReason") or "processing blocked. compatible saved test data is required." not in visible["blockedReason"].lower():
        fail(f"{target} blocked requirement wording is missing: {visible.get('blockedReason')!r}")
    if visible.get("sourceRevision") != "No compatible saved Test Data selected":
        fail(f"{target} blocked source field must identify the missing selected Test Data: {visible.get('sourceRevision')!r}")
    if visible.get("downstreamStatusVisible"):
        fail(f"{target} blocked workspace exposes a duplicate recovery layer: {visible.get('downstreamStatus')!r}")
    if visible.get("blockedGraphCopy") != "Return to Data and choose compatible saved Test Data before processing." or visible.get("blockedAction") != "Back to Data":
        fail(f"{target} centered panel must own the single recovery instruction/action: {visible}")
    controls = geometry.get("controls") or {}
    if not all(item.get("disabled") for item in controls.get("previewButtons") or []) or not controls.get("save", {}).get("disabled"):
        fail(f"{target} blocked commands are not disabled: {controls}")
    if sum(1 for disabled in controls.get("operationDisabled") or [] if disabled) != 5:
        fail(f"{target} blocked operation rows should be disabled: {controls}")
    exercise = measurements.get("exercise") or {}
    if not exercise.get("exact_prerequisite_named") or not exercise.get("graph_blocked") or exercise.get("stage_after_recovery") != "Data":
        fail(f"{target} blocked recovery consequence missing: {exercise}")


def assert_state_evidence() -> None:
    responsive = EVIDENCE_DIR / "modeling-process-responsive-evidence.json"
    state = EVIDENCE_DIR / "modeling-process-state-evidence.json"
    if not responsive.is_file() or not state.is_file():
        fail("missing responsive/state evidence JSON")
    responsive_data = json.loads(responsive.read_text(encoding="utf-8"))
    captures = responsive_data.get("captures") or []
    if {item.get("viewport", {}).get("width") for item in captures} != {1366, 1920}:
        fail(f"blocked responsive evidence must cover 1366/1920: {captures}")
    for item in captures:
        if item.get("console_errors") or item.get("page_errors") or any(value != 0 for value in (item.get("overflow") or {}).values()):
            fail(f"blocked responsive evidence has browser/overflow failure: {item}")
        geometry = item.get("geometry") or {}
        if geometry.get("visibleContent", {}).get("graphBlocked") is not True or geometry.get("regions", {}).get("navigator", {}).get("width") not in (184, 208):
            fail(f"blocked responsive topology changed: {item}")
    state_data = json.loads(state.read_text(encoding="utf-8"))
    state_captures = state_data.get("states") or []
    expected = {(state, width) for state in ("long-rail", "preview-loading", "commit-loading", "preview-error", "commit-error") for width in (1366, 1440, 1920)}
    actual = {(item.get("state"), item.get("viewport", {}).get("width")) for item in state_captures}
    if actual != expected:
        fail(f"loading/error state matrix incomplete: {actual}")
    for item in state_captures:
        target = item.get("target") or ""
        image = ROOT / str(item.get("image") or "")
        if not target.startswith("modeling-process-state-") or not image.is_file():
            fail(f"loading/error/long evidence image is missing: {item}")
        if png_dimensions(image) != (item["viewport"]["width"], item["viewport"]["height"]):
            fail(f"state evidence image dimensions do not match viewport: {item}")
        if item.get("image_sha256") != hashlib.sha256(image.read_bytes()).hexdigest():
            fail(f"state evidence image SHA-256 mismatch: {item}")
        if item.get("console_errors") or item.get("page_errors") or any(value != 0 for value in (item.get("overflow") or {}).values()):
            fail(f"loading/error evidence has browser/overflow failure: {item}")
        state_text = ((item.get("geometry") or {}).get("productLanguage") or {}).get("primaryWorkspaceText") or ""
        forbidden_state_language = ("evidence trace", "context preserved", "source retained", "graph retained", "preview retained", "job in progress")
        if any(term in state_text.lower() for term in forbidden_state_language):
            fail(f"state evidence exposes forbidden internal/redundant language: {state_text!r}")
        if item.get("state") in {"preview-loading", "commit-loading", "preview-error", "commit-error"}:
            if "error" in state_text.lower():
                fail(f"state evidence repeats a generic Error label instead of the named consequence: {state_text!r}")
        if not item.get("context_preserved") or not item.get("graph_curves_preserved") or not item.get("message"):
            if item.get("state") != "long-rail" or not item.get("context_preserved") or not item.get("graph_curves_preserved"):
                fail(f"loading/error evidence lost context or message: {item}")
        if item.get("state") == "long-rail":
            long_rail = item.get("long_rail") or {}
            if not long_rail.get("independent_scroll") or not long_rail.get("graph_unchanged") or not (item.get("geometry") or {}).get("visibleContent", {}).get("longRailTrack"):
                fail(f"long rail is not independently scrollable with graph context retained: {item}")
            visible = (item.get("geometry") or {}).get("visibleContent") or {}
            if len(visible.get("curveRows") or []) <= 3 or visible.get("includedCurves") != ["Specimen 01", "Specimen 02"]:
                fail(f"long rail does not truthfully show additional excluded stored curves while preserving the two included curves: {visible}")
        if item.get("state") in {"preview-loading", "commit-loading"}:
            controls = (item.get("geometry") or {}).get("controls") or {}
            previews = controls.get("previewButtons") or []
            if len(previews) != 1 or not previews[0].get("disabled") or not controls.get("save", {}).get("disabled"):
                fail(f"{target} loading commands are not visibly disabled: {controls}")


def assert_support_targets(staging: dict[str, Any]) -> None:
    support = staging.get("support_targets") or {}
    if set(support) != {"modeling-process-normal-2560x1440", "modeling-process-normal-3840x2160"}:
        fail(f"wide support targets missing from staging: {support}")
    for target in support:
        config = SUPPORT_TARGETS[target]
        measurement = read_measurement(target)
        assert_normal(target, config, measurement)
        image = EVIDENCE_DIR / f"{target}.png"
        if support[target].get("sha256") != hashlib.sha256(image.read_bytes()).hexdigest():
            fail(f"{target} staging SHA-256 mismatch")
        print(f"PASS {target}")
    if staging.get("lifecycle_candidates"):
        fail(f"3840 must remain support evidence because its topology now matches 1920: {staging['lifecycle_candidates']}")


def assert_plot_stability(targets: list[str]) -> None:
    signatures: dict[str, tuple[Any, ...]] = {}
    for target in targets:
        measurement = read_measurement(target)
        plot = (measurement.get("geometry") or {}).get("graph") or {}
        typography = plot.get("typography") or {}
        signatures[target] = tuple(round(float(value), 3) for value in typography.get("strokeWidths") or [])
    baseline = signatures[targets[0]]
    for target, signature in signatures.items():
        if signature != baseline:
            fail(f"{target} plot stroke widths changed across viewports: baseline={baseline}, current={signature}")


def main() -> None:
    args = parse_args()
    if not args.target and not args.all_packet_targets:
        raise SystemExit("provide --target or --all-packet-targets")
    assert_sources()
    staging = json.loads(STAGING.read_text(encoding="utf-8"))
    if args.expect_main_agent_status is not None and staging.get("status") != args.expect_main_agent_status:
        fail(f"staging status {staging.get('status')!r} != expected {args.expect_main_agent_status!r}")
    selected = list(TARGETS) if args.all_packet_targets else [args.target]
    for target in selected:
        measurements = read_measurement(target)
        if TARGETS[target]["state"] == "normal":
            assert_normal(target, TARGETS[target], measurements)
        else:
            assert_blocked(target, TARGETS[target], measurements)
        print(f"PASS {target}")
    if args.all_packet_targets:
        assert_support_targets(staging)
        assert_plot_stability([*TARGETS.keys(), *SUPPORT_TARGETS.keys()])
        assert_state_evidence()
        print("PASS responsive/state evidence")
    print("MOD-PROCESS WAVE-02 validation passed")


if __name__ == "__main__":
    main()

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
    if visible.get("stageLabels") != ["Data", "Process", "Fit", "Export"] or visible.get("activeStage") != "Process":
        fail(f"{target} stage strip mismatch: {visible.get('stageLabels')!r}, active={visible.get('activeStage')!r}")
    if geometry.get("nestedCards", 0) != 0:
        fail(f"{target} nested-card hard gate failed")
    if regions["graph"].get("width", 0) <= regions["ribbon"].get("width", 0) * .72:
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
    if regions["ribbon"].get("bottom", 0) > regions["graph"].get("y", 0):
        fail(f"{target} process ribbon overlaps the persistent graph: ribbon={regions['ribbon']}, graph={regions['graph']}")


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
    controls = geometry.get("controls") or {}
    if len(controls.get("previewButtons") or []) != 1 or controls["previewButtons"][0].get("text") != "Preview changes":
        fail(f"{target} title-row Preview changes command missing or duplicated: {controls}")
    if not controls.get("save") or controls["save"].get("text") != "Save processed curves":
        fail(f"{target} sole Save processed curves command missing: {controls}")
    footer = geometry.get("plotFooter") or {}
    if footer.get("axisLegendIntersect") or not all(footer.get(name) for name in ("axisContained", "legendContained", "axisInFooter", "legendInFooter")):
        fail(f"{target} graph footer lanes overlap or escape their containers: {footer}")
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
    if not visible.get("blockedReason") or "CMP-DEMO-DP780-TEST-JSON-03" not in visible["blockedReason"] or "Mapping Profile" not in visible["blockedReason"]:
        fail(f"{target} exact unmet prerequisite not named: {visible.get('blockedReason')!r}")
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
    expected = {(state, width) for state in ("preview-loading", "commit-loading", "preview-error", "commit-error") for width in (1366, 1440, 1920)}
    actual = {(item.get("state"), item.get("viewport", {}).get("width")) for item in state_captures}
    if actual != expected:
        fail(f"loading/error state matrix incomplete: {actual}")
    for item in state_captures:
        if item.get("console_errors") or item.get("page_errors") or any(value != 0 for value in (item.get("overflow") or {}).values()):
            fail(f"loading/error evidence has browser/overflow failure: {item}")
        if not item.get("context_preserved") or not item.get("graph_curves_preserved") or not item.get("message"):
            fail(f"loading/error evidence lost context or message: {item}")


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
        assert_state_evidence()
        print("PASS responsive/state evidence")
    print("MOD-PROCESS WAVE-02 validation passed")


if __name__ == "__main__":
    main()

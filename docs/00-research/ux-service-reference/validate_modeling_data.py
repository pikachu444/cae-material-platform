from __future__ import annotations

# ruff: noqa: E501
import argparse
import hashlib
import json
import struct
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover - the staging gate does not require the shared manifest
    yaml = None

ROOT = Path(__file__).resolve().parents[3]
EVIDENCE_DIR = ROOT / "docs/17-evidence/images/issue-167-service-reference"
CAPTURE = ROOT / "docs/00-research/ux-service-reference/capture_modeling_data.py"
HTML = ROOT / "docs/00-research/ux-service-reference/modeling-data-normal.html"
CSS = ROOT / "docs/00-research/ux-service-reference/modeling-data.css"
JAVASCRIPT = ROOT / "docs/00-research/ux-service-reference/modeling-data.js"
MANIFEST = ROOT / "docs/01-product/service-reference-manifest.yaml"
STAGING_PATH = ROOT / "docs/00-research/ux-service-reference/modeling-data-wide-correction.staging.json"

TARGETS = {
    "modeling-data-normal-1366x768": {"state": "normal", "viewport": {"width": 1366, "height": 768, "device_scale_factor": 1}, "navigator": 184},
    "modeling-data-normal-1440x900": {"state": "normal", "viewport": {"width": 1440, "height": 900, "device_scale_factor": 1}, "navigator": 192},
    "modeling-data-normal-1920x1080": {"state": "normal", "viewport": {"width": 1920, "height": 1080, "device_scale_factor": 1}, "navigator": 208},
    "modeling-data-normal-2560x1440": {"state": "normal", "viewport": {"width": 2560, "height": 1440, "device_scale_factor": 1}, "navigator": 208},
    "modeling-data-normal-3840x2160": {"state": "normal", "viewport": {"width": 3840, "height": 2160, "device_scale_factor": 1}, "navigator": 208},
    "modeling-data-empty-new-session-1440x900": {"state": "empty", "viewport": {"width": 1440, "height": 900, "device_scale_factor": 1}, "navigator": 192},
    "modeling-data-long-invalid-mapping-blocked-1440x900": {"state": "invalid", "viewport": {"width": 1440, "height": 900, "device_scale_factor": 1}, "navigator": 192},
}

CANONICAL_TARGETS = [
    "modeling-data-normal-1366x768",
    "modeling-data-normal-1440x900",
    "modeling-data-normal-1920x1080",
    "modeling-data-empty-new-session-1440x900",
    "modeling-data-long-invalid-mapping-blocked-1440x900",
]
NORMAL_TARGETS = [target for target, config in TARGETS.items() if config["state"] == "normal"]

INVALID_CANVAS_MINIMUMS = {
    (1366, 768): 210,
    (1440, 900): 265,
    (1920, 1080): 300,
}
INVALID_GRAPH_SHARE_MINIMUM = 0.42


def fail(message: str) -> None:
    raise AssertionError(message)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate the MOD-DATA static service reference family.")
    parser.add_argument("--target", choices=sorted(TARGETS), help="Validate one target.")
    parser.add_argument("--all-packet-targets", action="store_true", help="Validate all five packet targets, two wide normal supports and evidence states.")
    parser.add_argument("--expect-main-agent-status", default=None, help="Optional lifecycle status used after manifest integration.")
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
        fail(f"invalid measurement JSON {path}: {error}")


def assert_common(target: str, config: dict[str, Any], measurements: dict[str, Any]) -> None:
    image = EVIDENCE_DIR / f"{target}.png"
    if not image.is_file():
        fail(f"missing target PNG: {image}")
    if png_dimensions(image) != (config["viewport"]["width"], config["viewport"]["height"]):
        fail(f"{target} PNG dimensions do not match the named viewport: {png_dimensions(image)}")
    digest = hashlib.sha256(image.read_bytes()).hexdigest()
    if measurements.get("target") != target or measurements.get("viewport") != config["viewport"]:
        fail(f"{target} measurement target/viewport mismatch")
    if measurements.get("image_sha256") != digest:
        fail(f"{target} measurement image SHA-256 mismatch")
    if measurements.get("console_errors") or measurements.get("page_errors"):
        fail(f"{target} browser errors: console={measurements.get('console_errors')!r}, page={measurements.get('page_errors')!r}")
    overflow = measurements.get("overflow") or {}
    if any(value != 0 for value in overflow.values()):
        fail(f"{target} page overflow: {overflow}")
    geometry = measurements.get("geometry") or {}
    regions = geometry.get("regions") or {}
    for name in ("applicationBar", "context", "stageStrip", "navigator", "divider", "main", "ribbon", "graph", "statusBar"):
        if not regions.get(name):
            fail(f"{target} missing geometry region {name}")
    divider = geometry.get("divider") or {}
    if divider.get("visibleWidth") != 5 or divider.get("ruleWidth") != 1:
        fail(f"{target} divider geometry is not one 5px hit area with a 1px rule: {divider}")
    if regions.get("navigator", {}).get("width") != divider.get("ariaNow"):
        # The 5px hit area has its own width; aria-valuenow reports the adjacent navigator width.
        fail(f"{target} navigator/ARIA width mismatch: regions={regions.get('navigator')}, divider={divider}")
    if divider.get("ariaMin") != 180 or divider.get("ariaMax") != 240 or not divider.get("ariaExpanded"):
        fail(f"{target} divider ARIA range/state is not truthful: {divider}")
    visible = geometry.get("visibleContent") or {}
    if visible.get("stageLabels") != ["Data", "Process", "Fit", "Export"]:
        fail(f"{target} stage labels mismatch: {visible.get('stageLabels')!r}")
    if visible.get("sourceTabs") != ["Library", "Local file", "Test Data JSON"]:
        fail(f"{target} source tabs mismatch: {visible.get('sourceTabs')!r}")
    if geometry.get("nestedPersistentCards") != 0:
        fail(f"{target} nested persistent card hard-gate failed")


def assert_responsive_plot_geometry(target: str, measurements: dict[str, Any]) -> None:
    """Prove the static reference uses CSS-pixel geometry rather than SVG stretching."""
    geometry = measurements.get("geometry") or {}
    if geometry.get("devicePixelRatio") != 1:
        fail(f"{target} device scale factor is not 1: {geometry.get('devicePixelRatio')}")
    plot = geometry.get("plot") or {}
    if not plot.get("present"):
        fail(f"{target} source plot is missing")
    if str(plot.get("preserveAspectRatio", "")).strip().lower() == "none":
        fail(f"{target} preserveAspectRatio=none is forbidden")
    if plot.get("ratioDelta", 1) > 0.005:
        fail(f"{target} SVG/render ratio delta exceeds 0.005: {plot.get('ratioDelta')}")
    if abs(float(plot.get("renderWidth", 0)) - float(plot.get("width", 0))) > 1.0 or abs(float(plot.get("renderHeight", 0)) - float(plot.get("height", 0))) > 1.0:
        fail(f"{target} viewBox does not match the measured CSS render box: {plot}")
    area = plot.get("plotArea") or {}
    if not (area.get("right", 0) > area.get("left", 0) and area.get("bottom", 0) > area.get("top", 0)):
        fail(f"{target} plot area is invalid: {area}")
    bounds = plot.get("dataBounds") or {}
    if bounds.get("axisMaxStrain", 0) <= bounds.get("observedMaxStrain", 0) or bounds.get("axisMaxStressMpa", 0) <= bounds.get("observedMaxStressMpa", 0):
        fail(f"{target} axis bounds do not leave data-relative headroom: {bounds}")
    headroom = plot.get("headroom") or {}
    if min(float(headroom.get("top", 0)), float(headroom.get("right", 0))) <= 4:
        fail(f"{target} observed series is too close to the top/right frame: {headroom}")
    path = plot.get("seriesPath") or {}
    if path.get("x", 999) < area.get("left", 0) - 0.6 or path.get("right", -1) > area.get("right", 0) + 0.6 or path.get("y", 999) < area.get("top", 0) - 0.6 or path.get("bottom", -1) > area.get("bottom", 0) + 0.6:
        fail(f"{target} source curve leaves the dynamic plot area: {plot}")
    label_metrics = plot.get("labelMetrics") or []
    if not label_metrics or any(not item.get("inside") for item in label_metrics):
        fail(f"{target} axis labels/titles are outside the graph: {label_metrics}")
    if any(float(item.get("fontSize", 0)) < 10 or float(item.get("fontSize", 0)) > 12.5 for item in label_metrics):
        fail(f"{target} graph typography is outside the 10-12.5px range: {label_metrics}")
    strokes = [float(value) for value in plot.get("strokeMetrics", []) if isinstance(value, (float, int))]
    if not strokes or min(strokes) < 0.75 or max(strokes) > 3.5:
        fail(f"{target} grid/curve strokes are outside bounded CSS-pixel widths: {strokes}")
    if geometry.get("legendOverlapWithAxisTitle"):
        fail(f"{target} compact legend overlaps the x-axis title")
    if any(item.get("clipped") for item in geometry.get("taskTextContainment", [])):
        fail(f"{target} task text is clipped: {geometry.get('taskTextContainment')}")


def assert_normal(target: str, config: dict[str, Any], measurements: dict[str, Any]) -> None:
    assert_common(target, config, measurements)
    assert_responsive_plot_geometry(target, measurements)
    geometry = measurements["geometry"]
    visible = geometry["visibleContent"]
    if geometry["regions"]["navigator"]["width"] != config["navigator"]:
        fail(f"{target} default navigator width is not {config['navigator']}: {geometry['regions']['navigator']}")
    if visible.get("curveRows") != ["Specimen 01", "Specimen 02", "Specimen 03"]:
        fail(f"{target} normal curve rail mismatch: {visible.get('curveRows')!r}")
    if geometry.get("includedCurves") != 2 or geometry.get("visibleCurveCount") != 3:
        fail(f"{target} normal curve inclusion/visibility mismatch: {geometry.get('includedCurves')}, {geometry.get('visibleCurveCount')}")
    if visible.get("savedDatasets") != [
        "CMP-DEMO-DP780-TEST-JSON-03 · r1",
        "CMP-DEMO-DP780-TEST-JSON-02 · r1",
        "CMP-DEMO-DP780-TEST-JSON-01 · r2",
    ]:
        fail(f"{target} saved dataset list mismatch: {visible.get('savedDatasets')!r}")
    if geometry.get("datasetOptions") != 3:
        fail(f"{target} saved dataset option count is not three")
    plot = geometry.get("plot") or {}
    required_axes = {"0", "0.10", "0.20", "0.25", "500", "1,000", "Engineering strain [1]", "Engineering stress (MPa)"}
    if not required_axes.issubset(set(plot.get("axes") or [])):
        fail(f"{target} required engineering axes are missing: {plot.get('axes')!r}")
    exercise = measurements.get("exercise") or {}
    if exercise.get("selected_dataset") != "CMP-DEMO-DP780-TEST-JSON-02 · r1" or exercise.get("selected_curve") != "Specimen 02":
        fail(f"{target} selection consequence is missing: {exercise}")
    if exercise.get("source_controls") != {"library": True, "local": True, "json": True} or not exercise.get("points_view") or not exercise.get("disclosure_open"):
        fail(f"{target} source/graph/disclosure interactions are incomplete: {exercise}")
    splitter = exercise.get("splitter") or {}
    initial = splitter.get("initial") or {}
    arrow = splitter.get("arrow_right") or {}
    home = splitter.get("home") or {}
    end = splitter.get("end") or {}
    collapsed = splitter.get("collapsed") or {}
    restored = splitter.get("restored") or {}
    if initial.get("regions", {}).get("navigator", {}).get("width") != config["navigator"] or initial.get("divider", {}).get("ariaNow") != config["navigator"]:
        fail(f"{target} initial splitter state mismatch: {initial}")
    if arrow.get("divider", {}).get("ariaNow") != config["navigator"] + 8 or home.get("divider", {}).get("ariaNow") != 180 or end.get("divider", {}).get("ariaNow") != 240:
        fail(f"{target} keyboard splitter states mismatch: {splitter}")
    if collapsed.get("regions", {}).get("navigator", {}).get("width") != 0 or collapsed.get("divider", {}).get("ariaNow") != 0 or collapsed.get("divider", {}).get("ariaExpanded"):
        fail(f"{target} collapsed splitter state mismatch: {collapsed}")
    if restored.get("regions", {}).get("navigator", {}).get("width") != 240 or restored.get("divider", {}).get("ariaNow") != 240 or not restored.get("divider", {}).get("ariaExpanded"):
        fail(f"{target} restored splitter state mismatch: {restored}")


def assert_empty(target: str, config: dict[str, Any], measurements: dict[str, Any]) -> None:
    assert_common(target, config, measurements)
    geometry = measurements["geometry"]
    visible = geometry["visibleContent"]
    if geometry["regions"]["navigator"]["width"] != config["navigator"]:
        fail(f"{target} default navigator width is not {config['navigator']}")
    if visible.get("savedDatasets") or visible.get("curveRows") or geometry.get("datasetOptions") != 0 or geometry.get("includedCurves") != 0:
        fail(f"{target} empty state exposes saved data or curves: {visible}")
    if not visible.get("graphEmpty") or visible.get("graphBlocked"):
        fail(f"{target} graph empty state is not truthful: {visible}")
    if visible.get("visiblePlotCurves") != 0 or visible.get("plotLegendVisible") or "CMP-DEMO" in visible.get("graphContext", ""):
        fail(f"{target} empty graph still implies a saved preview: {visible}")
    exercise = measurements.get("exercise") or {}
    if exercise.get("visible_saved_datasets_before") != 0 or not exercise.get("local_file_consequence") or exercise.get("active_source") != "local":
        fail(f"{target} empty state does not have exactly one Local-file consequence: {exercise}")


def assert_invalid(target: str, config: dict[str, Any], measurements: dict[str, Any]) -> None:
    assert_common(target, config, measurements)
    assert_responsive_plot_geometry(target, measurements)
    geometry = measurements["geometry"]
    visible = geometry["visibleContent"]
    if geometry["regions"]["navigator"]["width"] != config["navigator"]:
        fail(f"{target} default navigator width is not {config['navigator']}")
    if not visible.get("rawInspector") or not visible.get("mappingTable") or not visible.get("graphBlocked"):
        fail(f"{target} invalid source evidence/graph context is incomplete: {visible}")
    if "stale" not in visible.get("graphContext", "").lower() or not visible.get("visiblePlotCurves"):
        fail(f"{target} invalid graph does not preserve a clearly stale last-valid preview: {visible}")
    if geometry.get("includedCurves") != 2 or geometry.get("visibleCurveCount") != 3:
        fail(f"{target} invalid state lost graph curve context")
    if not visible.get("updatePreviewDisabled") or not visible.get("saveDatasetDisabled"):
        fail(f"{target} invalid mapping actions are not blocked: {visible}")
    assert_invalid_graph_allocation(target, config["viewport"], geometry)
    exercise = measurements.get("exercise") or {}
    if not exercise.get("raw_inspector_visible") or exercise.get("mapping_rows") != 2 or not exercise.get("conflict_visible") or not exercise.get("update_disabled") or not exercise.get("save_disabled") or not exercise.get("mapping_reason"):
        fail(f"{target} invalid mapping decision evidence is incomplete: {exercise}")
    if not any("Engineering strain measurement long channel name" in label for label in exercise.get("long_labels", [])):
        fail(f"{target} long raw source label is missing")
    for name in ("raw", "mapping"):
        table = (geometry.get("tableContainment") or {}).get(name) or {}
        if table.get("present") and (table.get("overflow", 999) > 0.6 or not table.get("allInside") or not table.get("allContained")):
            fail(f"{target} {name} table text is not contained: {table}")


def assert_invalid_graph_allocation(target: str, viewport: dict[str, int], geometry: dict[str, Any]) -> None:
    """Keep the invalid decision visible without sacrificing the persistent graph."""
    key = (viewport["width"], viewport["height"])
    minimum_canvas = INVALID_CANVAS_MINIMUMS.get(key)
    if minimum_canvas is None:
        fail(f"{target} uses an unsupported invalid viewport: {viewport}")
    regions = geometry.get("regions") or {}
    main = regions.get("main") or {}
    graph = regions.get("graph") or {}
    canvas = regions.get("graphCanvas") or {}
    main_height = main.get("height", 0)
    graph_height = graph.get("height", 0)
    canvas_height = canvas.get("height", 0)
    graph_share = graph_height / main_height if main_height else 0
    if graph_share < INVALID_GRAPH_SHARE_MINIMUM:
        fail(f"{target} invalid graph share {graph_share:.3f} is below {INVALID_GRAPH_SHARE_MINIMUM:.2f}")
    if canvas_height < minimum_canvas:
        fail(f"{target} invalid graph canvas {canvas_height}px is below {minimum_canvas}px")


def assert_responsive_evidence() -> None:
    evidence_path = EVIDENCE_DIR / "modeling-data-state-evidence.json"
    if not evidence_path.is_file():
        fail(f"missing state evidence: {evidence_path}")
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    for state in ("empty", "invalid"):
        captures = (evidence.get(f"{state}-responsive") or {}).get("captures") or []
        if len(captures) != 3:
            fail(f"{state} responsive evidence must contain 1366/1440/1920 captures")
        for capture in captures:
            viewport = capture.get("viewport") or {}
            image_relative = capture.get("image")
            if not image_relative:
                fail(f"{state} responsive evidence is missing its image path")
            image_path = ROOT / Path(image_relative.replace("\\", "/"))
            if not image_path.is_file():
                fail(f"{state} responsive image is missing: {image_relative}")
            digest = hashlib.sha256(image_path.read_bytes()).hexdigest()
            if capture.get("image_sha256") != digest:
                fail(
                    f"{state} responsive image_sha256 mismatch for {image_relative}: "
                    f"{capture.get('image_sha256')} != {digest}"
                )
            if png_dimensions(image_path) != (viewport.get("width"), viewport.get("height")):
                fail(f"{state} responsive PNG dimensions do not match {viewport}: {image_relative}")
            if viewport.get("width") == 1440:
                canonical_target = (
                    "modeling-data-empty-new-session-1440x900"
                    if state == "empty"
                    else "modeling-data-long-invalid-mapping-blocked-1440x900"
                )
                canonical_image = (
                    f"docs\\17-evidence\\images\\issue-167-service-reference\\"
                    f"{canonical_target}.png"
                )
                if capture.get("target") != canonical_target or capture.get("image") != canonical_image:
                    fail(f"{state} 1440 responsive evidence must reuse its canonical image")
            if capture.get("console_errors") or capture.get("page_errors"):
                fail(f"{state} responsive browser errors: {capture}")
            if any(value != 0 for value in (capture.get("overflow") or {}).values()):
                fail(f"{state} responsive overflow: {capture}")
            geometry = capture.get("geometry") or {}
            if not geometry.get("regions", {}).get("ribbon") or not geometry.get("regions", {}).get("graph"):
                fail(f"{state} responsive topology changed: {capture}")
            if state == "invalid":
                assert_invalid_graph_allocation(capture.get("target", "invalid-responsive"), capture.get("viewport") or {}, geometry)
    loading = (evidence.get("loading-error-evidence") or {}).get("states") or []
    if len(loading) != 15:
        fail(f"loading/error evidence must contain 5 states at 3 viewports, found {len(loading)}")
    for capture in loading:
        if capture.get("console_errors") or capture.get("page_errors") or any(value != 0 for value in (capture.get("overflow") or {}).values()):
            fail(f"loading/error evidence has browser failure or overflow: {capture}")
        if not capture.get("context_preserved"):
            fail(f"loading/error evidence lost source/graph context: {capture}")


def assert_manifest_if_integrated(selected: list[str], expected_main_agent_status: str | None) -> None:
    """Validate integrated MOD-DATA rows when the main agent has added them.

    The writer gate intentionally runs before common-manifest integration, so an absent row is
    permitted here. Once rows exist, image/viewport/hash and lifecycle continuity become required.
    """
    if not MANIFEST.is_file() or yaml is None:
        return
    document = yaml.safe_load(MANIFEST.read_text(encoding="utf-8")) or {}
    entries = {entry.get("id"): entry for entry in document.get("references", [])}
    manifest_selected = [target for target in selected if target in CANONICAL_TARGETS]
    present = [target for target in manifest_selected if target in entries]
    if not present:
        return
    if len(present) != len(manifest_selected):
        fail(f"integrated MOD-DATA manifest is incomplete: present={present}, expected={manifest_selected}")
    if expected_main_agent_status == "pending" and not any(
        (entries[target].get("main_agent_evaluation") or {}).get("status") == "pending" for target in manifest_selected
    ):
        # The approved WAVE-01 rows are retained in the shared manifest until /root integrates this
        # bounded correction. Their old hashes must not block the writer-owned staging gate.
        return
    for target in manifest_selected:
        entry = entries[target]
        config = TARGETS[target]
        if entry.get("screen") not in ("modeling-data", "modeling-data-normal"):
            fail(f"{target} manifest screen is not Modeling Data: {entry.get('screen')!r}")
        if entry.get("viewport") != config["viewport"]:
            fail(f"{target} manifest viewport mismatch: {entry.get('viewport')!r}")
        expected_image = f"docs/17-evidence/images/issue-167-service-reference/{target}.png"
        expected_measurements = f"docs/17-evidence/images/issue-167-service-reference/{target}.measurements.json"
        if entry.get("image") != expected_image or entry.get("measurements") != expected_measurements:
            fail(f"{target} manifest image/measurements paths do not match staging evidence")
        digest = hashlib.sha256((EVIDENCE_DIR / f"{target}.png").read_bytes()).hexdigest()
        if entry.get("image_sha256") != digest:
            fail(f"{target} manifest image_sha256 mismatch")
        if expected_main_agent_status is not None and (entry.get("main_agent_evaluation") or {}).get("status") != expected_main_agent_status:
            fail(f"{target} manifest main-agent lifecycle mismatch")


def assert_wide_stroke_consistency(measurements_by_target: dict[str, dict[str, Any]]) -> None:
    normal_measurements = [measurements_by_target[target] for target in NORMAL_TARGETS if target in measurements_by_target]
    if len(normal_measurements) < 2:
        return
    baseline = [float(value) for value in ((normal_measurements[0].get("geometry") or {}).get("plot") or {}).get("strokeMetrics", [])]
    if not baseline:
        fail("normal wide-support stroke metrics are missing")
    for target, measurements in measurements_by_target.items():
        if target not in NORMAL_TARGETS:
            continue
        current = [float(value) for value in ((measurements.get("geometry") or {}).get("plot") or {}).get("strokeMetrics", [])]
        if len(current) != len(baseline) or any(abs(value - baseline[index]) > 0.15 for index, value in enumerate(current)):
            fail(f"{target} grid/curve strokes scale with viewport: baseline={baseline}, current={current}")


def assert_staging_index(selected: list[str], expected_main_agent_status: str | None) -> bool:
    if not STAGING_PATH.is_file():
        return False
    try:
        staging = json.loads(STAGING_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        fail(f"invalid MOD-DATA staging JSON: {error}")
    if staging.get("schema_version") != 1 or staging.get("family") != "MOD-DATA":
        fail(f"unexpected MOD-DATA staging family/schema: {staging.get('family')!r}/{staging.get('schema_version')!r}")
    if expected_main_agent_status is not None and staging.get("status") != expected_main_agent_status:
        fail(f"MOD-DATA staging status {staging.get('status')!r} != {expected_main_agent_status!r}")
    references = staging.get("references") or []
    wide_support = staging.get("wide_support") or []
    entries = {entry.get("id"): entry for entry in [*references, *wide_support]}
    expected_canonical = [target for target in CANONICAL_TARGETS if target in selected]
    expected_wide = [target for target in selected if target in NORMAL_TARGETS and target not in CANONICAL_TARGETS]
    if set(entry.get("id") for entry in references) != set(expected_canonical):
        fail(f"MOD-DATA staging canonical target set mismatch: {sorted(entries)}")
    if set(entry.get("id") for entry in wide_support) != set(expected_wide):
        fail(f"MOD-DATA staging wide-support target set mismatch: {sorted(entries)}")
    for target in selected:
        entry = entries.get(target)
        if not entry:
            fail(f"MOD-DATA staging index missing target: {target}")
        config = TARGETS[target]
        if entry.get("viewport") != config["viewport"] or entry.get("kind") != config["state"]:
            fail(f"{target} staging viewport/state mismatch: {entry}")
        image = ROOT / Path(str(entry.get("image", "")).replace("\\", "/"))
        measurements = ROOT / Path(str(entry.get("measurements", "")).replace("\\", "/"))
        if not image.is_file() or not measurements.is_file():
            fail(f"{target} staging image/measurement pointer is missing: {entry}")
        digest = hashlib.sha256(image.read_bytes()).hexdigest()
        if entry.get("image_sha256") != digest:
            fail(f"{target} staging image_sha256 mismatch: {entry.get('image_sha256')} != {digest}")
        if expected_main_agent_status is not None and (entry.get("main_agent_evaluation") or {}).get("status") != expected_main_agent_status:
            fail(f"{target} staging main-agent status mismatch")
    evidence = staging.get("state_evidence")
    if not evidence or not (ROOT / Path(str(evidence).replace("\\", "/"))).is_file():
        fail(f"MOD-DATA staging state-evidence pointer is missing: {evidence}")
    return True


def main() -> None:
    args = parse_args()
    if not args.all_packet_targets and not args.target:
        raise SystemExit("provide --target or --all-packet-targets")
    for path in (HTML, CSS, JAVASCRIPT, CAPTURE):
        if not path.is_file():
            fail(f"missing MOD-DATA source: {path}")
    selected = list(TARGETS) if args.all_packet_targets else [args.target]
    measurements_by_target: dict[str, dict[str, Any]] = {}
    for target in selected:
        config = TARGETS[target]
        measurements = read_measurement(target)
        measurements_by_target[target] = measurements
        if config["state"] == "normal":
            assert_normal(target, config, measurements)
        elif config["state"] == "empty":
            assert_empty(target, config, measurements)
        else:
            assert_invalid(target, config, measurements)
        digest = hashlib.sha256((EVIDENCE_DIR / f"{target}.png").read_bytes()).hexdigest()
        print(f"PASS {target} image_sha256={digest}")
    if args.all_packet_targets:
        assert_wide_stroke_consistency(measurements_by_target)
        assert_responsive_evidence()
        print("PASS MOD-DATA responsive exceptional/loading/error evidence")
    staging_active = args.all_packet_targets and assert_staging_index(selected, args.expect_main_agent_status)
    if staging_active:
        print(f"PASS MOD-DATA staging index {STAGING_PATH.relative_to(ROOT)}")
    else:
        assert_manifest_if_integrated(selected, args.expect_main_agent_status)
    print("PASS MOD-DATA family validator")


if __name__ == "__main__":
    main()

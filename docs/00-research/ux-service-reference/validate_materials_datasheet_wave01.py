# ruff: noqa: E501
from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover - common manifest is optional during staging
    yaml = None


ROOT = Path(__file__).resolve().parents[3]
IMAGE_DIR = ROOT / "docs/17-evidence/images/issue-167-service-reference"
CAPTURE = ROOT / "docs/00-research/ux-service-reference/capture_materials_datasheet_wave01.py"
STAGING_INDEX = IMAGE_DIR / "materials-datasheet-wave01.staging.json"
MANIFEST = ROOT / "docs/01-product/service-reference-manifest.yaml"

TARGETS: dict[str, dict[str, Any]] = {
    "materials-datasheet-overview-normal-1366x768": {
        "kind": "normal",
        "viewport": {"width": 1366, "height": 768, "device_scale_factor": 1},
        "navigator": 244,
        "compact_max": 345,
        "splitter": {
            "default": 244,
            "navigator_arrow_right": 252,
            "navigator_home": 200,
            "navigator_end": 345,
        },
        "image": IMAGE_DIR / "materials-datasheet-overview-normal-1366x768.png",
        "measurements": IMAGE_DIR
        / "materials-datasheet-overview-normal-1366x768.measurements.json",
    },
    "materials-datasheet-overview-normal-1440x900": {
        "kind": "normal",
        "viewport": {"width": 1440, "height": 900, "device_scale_factor": 1},
        "navigator": 264,
        "compact_max": 360,
        "splitter": {
            "default": 264,
            "navigator_arrow_right": 272,
            "navigator_home": 200,
            "navigator_end": 360,
        },
        "image": IMAGE_DIR / "materials-datasheet-overview-normal-1440x900.png",
        "measurements": IMAGE_DIR
        / "materials-datasheet-overview-normal-1440x900.measurements.json",
    },
    "materials-datasheet-overview-normal-1920x1080": {
        "kind": "normal",
        "viewport": {"width": 1920, "height": 1080, "device_scale_factor": 1},
        "navigator": 280,
        "compact_max": 360,
        "splitter": {
            "default": 280,
            "navigator_arrow_right": 288,
            "navigator_home": 200,
            "navigator_end": 360,
        },
        "layouts": {
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
    },
    "materials-datasheet-related-long-1440x900": {
        "kind": "related",
        "viewport": {"width": 1440, "height": 900, "device_scale_factor": 1},
        "navigator": 264,
        "compact_max": 360,
        "splitter": {
            "default": 264,
            "navigator_arrow_right": 272,
            "navigator_home": 200,
            "navigator_end": 360,
        },
    },
    "materials-datasheet-empty-1440x900": {
        "kind": "empty",
        "viewport": {"width": 1440, "height": 900, "device_scale_factor": 1},
        "navigator": 264,
        "compact_max": 360,
        "splitter": {
            "default": 264,
            "navigator_arrow_right": 272,
            "navigator_home": 200,
            "navigator_end": 360,
        },
    },
}

EXPECTED_TABS = ["Overview", "Properties", "Curves", "CAE Cards", "Related", "Evidence"]
EXPECTED_HEADERS = ["Property", "Value", "Unit", "Condition", "Source"]
EXPECTED_SERIES = {
    "strain": {"minimum": 0, "maximum": 0.2},
    "stress_mpa": {"minimum": 0, "maximum": 850},
}
EXPECTED_POLICY = {
    "upper_headroom_ratio": 0.1,
    "target_intervals": {"strain": 5, "stress_mpa": 4},
    "nice_step_factors": [1, 2, 2.5, 5, 10],
}
EXPECTED_RESPONSE_POINTS = [
    {"point": 1, "strain": 0.0, "stress_mpa": 0},
    {"point": 2, "strain": 0.001, "stress_mpa": 210},
    {"point": 3, "strain": 0.002, "stress_mpa": 420},
    {"point": 4, "strain": 0.003, "stress_mpa": 560},
    {"point": 5, "strain": 0.004, "stress_mpa": 578},
    {"point": 6, "strain": 0.006, "stress_mpa": 596},
    {"point": 7, "strain": 0.008, "stress_mpa": 608},
    {"point": 8, "strain": 0.01, "stress_mpa": 620},
    {"point": 9, "strain": 0.015, "stress_mpa": 638},
    {"point": 10, "strain": 0.02, "stress_mpa": 655},
    {"point": 11, "strain": 0.025, "stress_mpa": 668},
    {"point": 12, "strain": 0.03, "stress_mpa": 680},
    {"point": 13, "strain": 0.04, "stress_mpa": 700},
    {"point": 14, "strain": 0.05, "stress_mpa": 718},
    {"point": 15, "strain": 0.06, "stress_mpa": 735},
    {"point": 16, "strain": 0.07, "stress_mpa": 750},
    {"point": 17, "strain": 0.08, "stress_mpa": 765},
    {"point": 18, "strain": 0.09, "stress_mpa": 778},
    {"point": 19, "strain": 0.1, "stress_mpa": 790},
    {"point": 20, "strain": 0.11, "stress_mpa": 801},
    {"point": 21, "strain": 0.12, "stress_mpa": 810},
    {"point": 22, "strain": 0.13, "stress_mpa": 818},
    {"point": 23, "strain": 0.14, "stress_mpa": 826},
    {"point": 24, "strain": 0.15, "stress_mpa": 832},
    {"point": 25, "strain": 0.16, "stress_mpa": 838},
    {"point": 26, "strain": 0.17, "stress_mpa": 842},
    {"point": 27, "strain": 0.18, "stress_mpa": 846},
    {"point": 28, "strain": 0.19, "stress_mpa": 849},
    {"point": 29, "strain": 0.2, "stress_mpa": 850},
]
PRESERVED_MAT_DETAIL_EXCEPTIONAL_HASHES = {
    "materials-datasheet-related-long-1440x900.png": "810394678a9a77c1c35adc4a1848ca45eadd71a1a95a69ea94af7266405079b6",
    "materials-datasheet-related-long-1440x900.responsive-1366x768.png": "4963c0eb91ba711ffcaf370999fb07dbb53735ce6dce32fe5884e675170a583d",
    "materials-datasheet-related-long-1440x900.responsive-1920x1080.png": "bf98b166f6b89ffae6baddb24321296837b340704352d74769b5764334eb0fc2",
    "materials-datasheet-empty-1440x900.png": "8df98559459f03db925e02251e10a84265b9ff1e21cd8f4573dd9d2a090548e6",
    "materials-datasheet-empty-1440x900.responsive-1366x768.png": "9aa40656c8aa86fe858b438efd5f9447401af439b629df65e25b7e6537fb0d95",
    "materials-datasheet-empty-1440x900.responsive-1920x1080.png": "958b8b7f228d6df776885ddcb3760b33881625b9fd1086a94db38fdb3bffa1d5",
}
WIDE_VIEWPORTS = (
    {"width": 2560, "height": 1440, "device_scale_factor": 1},
    {"width": 3840, "height": 2160, "device_scale_factor": 1},
)


def fail(message: str) -> None:
    raise SystemExit(f"FAIL: {message}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate the WAVE-01 Materials datasheet family.")
    parser.add_argument("--target", choices=sorted(TARGETS), help="One canonical target id.")
    parser.add_argument(
        "--all-packet-targets",
        action="store_true",
        help="Validate all canonical and responsive evidence.",
    )
    parser.add_argument(
        "--expect-main-agent-status", default="accepted", choices=["pending", "accepted", "rejected"]
    )
    parser.add_argument(
        "--expect-owner-approval",
        default="absent",
        choices=["absent", "approved"],
        help="Expected product-owner lifecycle for the normal references.",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=MANIFEST,
        help="Optional common manifest after main-agent integration.",
    )
    parser.add_argument(
        "--wide-evidence",
        action="store_true",
        help="Validate the canonical normal target plus its 2560x1440/3840x2160 wide evidence.",
    )
    parser.add_argument(
        "--assert-preserved-hashes",
        action="store_true",
        help="Assert that frozen MAT-DETAIL related/empty images and responsive siblings are unchanged.",
    )
    args = parser.parse_args()
    if not args.target and not args.all_packet_targets:
        parser.error("provide --target or --all-packet-targets")
    if args.target and args.all_packet_targets:
        parser.error("--target and --all-packet-targets are mutually exclusive")
    if args.wide_evidence and args.all_packet_targets:
        parser.error("--wide-evidence is only valid for the normal target")
    return args


def png_dimensions(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        fail(f"not a PNG: {path}")
    return struct.unpack(">II", data[16:24])


def close(actual: float, expected: float, label: str, tolerance: float = 0.6) -> None:
    if abs(actual - expected) > tolerance:
        fail(f"{label}: expected {expected}, got {actual}")


def nice_step(rough: float, factors: list[float]) -> float:
    exponent = math.floor(math.log10(rough))
    candidates = [
        factor * 10**power for power in range(exponent - 1, exponent + 3) for factor in factors
    ]
    return min(candidate for candidate in candidates if candidate >= rough - 1e-12)


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


def expected_measurement_path(target: str) -> Path:
    return IMAGE_DIR / f"{target}.measurements.json"


def expected_image_path(target: str) -> Path:
    return IMAGE_DIR / f"{target}.png"


def assert_tree_row_alignment(tree: dict[str, Any], target: str, context: str) -> None:
    expected_child_order = ["tree-disclosure", "tree-label", "tree-kind"]
    expected_components = ("disclosure", "kind", "label")
    rows = tree.get("row_alignment") or []
    if len(rows) != 7:
        fail(f"{target} {context} must record alignment for 7 tree rows: {rows!r}")
    for row in rows:
        if row.get("dom_child_class_order") != expected_child_order:
            fail(f"{target} {context} HTML child order changed: {row!r}")
        centers = row.get("box_centers") or {}
        y_centers: list[float] = []
        for component in expected_components:
            center = centers.get(component) or {}
            y = center.get("y")
            if not isinstance(y, (int, float)):
                fail(f"{target} {context} missing {component} center: {row!r}")
            y_centers.append(y)
        maximum_delta = max(y_centers) - min(y_centers)
        if (
            row.get("maximum_center_delta") is None
            or abs(row["maximum_center_delta"] - maximum_delta) > 0.01
            or maximum_delta > 0.5
        ):
            fail(f"{target} {context} child centers are misaligned: {row!r}")
        if (
            row.get("css_grid_rows") != {component: "1" for component in expected_components}
            or row.get("all_three_same_css_grid_row") is not True
        ):
            fail(f"{target} {context} children do not resolve to CSS grid row 1: {row!r}")


def assert_common(
    measurement: dict[str, Any],
    target: str,
    config: dict[str, Any],
    image: Path,
    *,
    responsive: bool = False,
    wide: bool = False,
) -> None:
    viewport = measurement.get("viewport")
    allowed_viewports = (
        {"width": 1366, "height": 768, "device_scale_factor": 1},
        {"width": 1440, "height": 900, "device_scale_factor": 1},
        {"width": 1920, "height": 1080, "device_scale_factor": 1},
    )
    if wide:
        valid_viewport = viewport in WIDE_VIEWPORTS
    elif responsive:
        valid_viewport = viewport in allowed_viewports
    else:
        valid_viewport = viewport == config["viewport"]
    if not valid_viewport:
        fail(f"{target} viewport mismatch: {viewport!r}")
    if measurement.get("target") != target:
        fail(f"measurement target mismatch: {measurement.get('target')!r}")
    if measurement.get("responsive_evidence") is not responsive:
        fail(f"responsive flag mismatch for {target}")
    if wide and measurement.get("wide_evidence") is not True:
        fail(f"wide evidence flag mismatch for {target}")
    if measurement.get("console_errors") or measurement.get("page_errors"):
        fail(f"browser errors recorded for {target}")
    if not CAPTURE.is_file():
        fail(f"capture helper missing: {CAPTURE}")
    if not image.is_file():
        fail(f"missing image/measurement for {target}: {image}")
    digest = hashlib.sha256(image.read_bytes()).hexdigest()
    if measurement.get("image_sha256") != digest:
        fail(f"image SHA-256 mismatch in measurement for {target}")
    if png_dimensions(image) != (viewport["width"], viewport["height"]):
        fail(f"PNG dimensions mismatch for {target}: {png_dimensions(image)}")
    regions = measurement.get("regions") or {}
    close(regions.get("application_bar", {}).get("height", -1), 46, f"{target} application bar")
    close(regions.get("command_bar", {}).get("height", -1), 38, f"{target} command bar")
    close(regions.get("status_bar", {}).get("height", -1), 24, f"{target} status bar")
    close(regions.get("workspace", {}).get("x", -1), 8, f"{target} workspace x")
    close(
        regions.get("workspace", {}).get("width", -1),
        viewport["width"] - 16,
        f"{target} workspace width",
    )
    close(
        regions.get("workspace", {}).get("height", -1),
        viewport["height"] - 108,
        f"{target} workspace height",
    )
    expected_navigator = (
        244
        if viewport["width"] == 1366
        else 280
        if viewport["width"] == 1920
        else config["navigator"]
    )
    expected_max = 345 if viewport["width"] == 1366 else config["compact_max"]
    close(
        regions.get("navigator", {}).get("width", -1),
        expected_navigator,
        f"{target} navigator width",
    )
    close(regions.get("navigator_divider", {}).get("width", -1), 5, f"{target} divider width")
    close(
        regions.get("datasheet", {}).get("width", -1),
        viewport["width"] - 16 - expected_navigator - 5,
        f"{target} datasheet width",
    )
    if (
        measurement.get("divider_visual_widths") != [1]
        or measurement.get("visible_splitter_count") != 1
    ):
        fail(f"{target} must have one 5px splitter with one 1px rule")
    if measurement.get("selected_tree_rows") != 1 or not measurement.get("selected_record"):
        fail(f"{target} must preserve one selected DP780 Record")
    tree = measurement.get("tree") or {}
    expected_tree_overflow = 0
    expected_horizontal_rail = False
    if (
        tree.get("horizontal_overflow") != expected_tree_overflow
        or tree.get("vertical_overflow") != 0
        or tree.get("rails", {}).get("horizontal") != expected_horizontal_rail
        or tree.get("rails", {}).get("vertical")
        or not tree.get("all_tree_kind_right_edges_within_content")
        or not tree.get("tree_kind_labels_match")
    ):
        fail(f"{target} tree containment failed: {tree!r}")
    if config["kind"] == "normal":
        identities = tree.get("identities") or []
        if len(identities) != 7 or any(
            item.get("identity") != item.get("title")
            or item.get("glyph_kind") != item.get("expected")
            or item.get("glyph_title") != item.get("expected")
            or item.get("glyph_font_size") != "0px"
            or not item.get("accessible_name", "").startswith(f"{item.get('expected')}: ")
            for item in identities
        ):
            fail(f"{target} tree identity/glyph semantics failed: {identities!r}")
    if any(value != 0 for value in (measurement.get("overflow") or {}).values()):
        fail(f"{target} page overflow: {measurement.get('overflow')!r}")
    if measurement.get("nested_persistent_card_count") != 0:
        fail(f"{target} nested persistent card count is not zero")
    if measurement.get("forbidden_visible_terms") or measurement.get("unsupported_labels"):
        fail(
            f"{target} forbidden visible terms: {measurement.get('forbidden_visible_terms')!r}, {measurement.get('unsupported_labels')!r}"
        )
    expected_states = {
        "default": expected_navigator,
        "navigator_arrow_right": expected_navigator + 8,
        "navigator_home": 200,
        "navigator_end": expected_max,
    }
    for label, expected in expected_states.items():
        snapshot = (measurement.get("splitter_evidence") or {}).get(label)
        if not snapshot:
            fail(f"{target} missing splitter state {label}")
        widths = snapshot.get("widths") or {}
        aria = snapshot.get("aria") or {}
        if (
            widths.get("navigator") != expected
            or widths.get("divider") != 5
            or widths.get("navigator") != aria.get("now")
        ):
            fail(f"{target} {label} navigator/ARIA mismatch: {snapshot!r}")
        if aria.get("minimum") != 200 or aria.get("maximum") != expected_max:
            fail(f"{target} {label} ARIA range mismatch: {aria!r}")
        if widths.get("datasheet", 0) < 720:
            fail(f"{target} {label} datasheet below safety rail: {widths!r}")
        if any(value != 0 for value in (snapshot.get("overflow") or {}).values()):
            fail(f"{target} {label} page overflow: {snapshot.get('overflow')!r}")
        tree_state = snapshot.get("tree") or {}
        if config["kind"] == "normal":
            assert_tree_row_alignment(tree_state, target, f"{label} splitter state")
        expected_state_overflow = 41 if config["kind"] == "normal" and expected == 200 else 0
        if (
            tree_state.get("horizontal_overflow") != expected_state_overflow
            or tree_state.get("vertical_overflow") != 0
            or tree_state.get("rails", {}).get("horizontal") != (expected_state_overflow > 0)
            or tree_state.get("rails", {}).get("vertical")
            or not tree_state.get("all_tree_kind_right_edges_within_content")
            or not tree_state.get("tree_kind_labels_match")
        ):
            fail(f"{target} {label} tree containment failed")
        if not snapshot.get("selected_record_visible"):
            fail(f"{target} {label} selected Record is not visible")
    interactions = measurement.get("interactions") or {}
    if not interactions or not all(interactions.values()):
        fail(f"{target} interaction evidence incomplete: {interactions!r}")


def assert_normal(
    measurement: dict[str, Any], target: str, config: dict[str, Any], *, wide: bool = False
) -> None:
    assert_tree_row_alignment(measurement.get("tree") or {}, target, "normal navigator")
    if measurement.get("tabs") != {"count": 6, "labels": EXPECTED_TABS, "active": "Overview"}:
        fail(f"{target} tabs mismatch: {measurement.get('tabs')!r}")
    if (
        measurement.get("property_headers") != EXPECTED_HEADERS
        or measurement.get("property_rows") != 4
    ):
        fail(f"{target} property sheet mismatch")
    if any(
        len(row) != 5 or any(not value for value in row[2:])
        for row in measurement.get("property_semantics") or []
    ):
        fail(f"{target} property semantics missing unit/condition/source")
    formats = measurement.get("solver_formats") or []
    if [(entry.get("solver"), entry.get("format")) for entry in formats] != [
        ("Abaqus", ".inp"),
        ("OpenRadioss", ".rad"),
    ]:
        fail(f"{target} native formats mismatch: {formats!r}")
    if (
        measurement.get("solver_format_count") != 2
        or measurement.get("delivery_preview_count") != 2
        or measurement.get("delivery_download_count") != 2
    ):
        fail(f"{target} solver-card delivery entry points incomplete")
    if measurement.get("primary_command_count") != 1:
        fail(f"{target} normal overview must have one filled primary command")
    density = measurement.get("row_density") or {}
    if (
        density.get("tree", {}).get("count", 0) < 6
        or not (24 <= density.get("tree", {}).get("minimum", 0) <= 26)
        or not (24 <= density.get("tree", {}).get("maximum", 0) <= 26)
    ):
        fail(f"{target} tree row density mismatch")
    if (
        density.get("properties", {}).get("count") != 4
        or not (30 <= density.get("properties", {}).get("minimum", 0) <= 34)
        or not (30 <= density.get("properties", {}).get("maximum", 0) <= 34)
    ):
        fail(f"{target} property row density mismatch")
    grid = measurement.get("response_grid") or {}
    if (
        grid.get("source") != EXPECTED_RESPONSE_POINTS
        or grid.get("rows") != EXPECTED_RESPONSE_POINTS
        or grid.get("source_point_count") != len(EXPECTED_RESPONSE_POINTS)
        or grid.get("row_count") != len(EXPECTED_RESPONSE_POINTS)
        or grid.get("headers") != [
            "Point",
            "Engineering strain",
            "Engineering stress (MPa)",
        ]
        or grid.get("table_header_position") != "sticky"
        or grid.get("table_series_point_count") != len(EXPECTED_RESPONSE_POINTS)
        or grid.get("graph_point_count") != len(EXPECTED_RESPONSE_POINTS)
        or grid.get("graph_element") != "polyline"
        or not grid.get("shared_source")
    ):
        fail(f"{target} exact response series/grid sharing failed: {grid!r}")
    wide_grid = measurement.get("viewport", {}).get("width", 0) >= 1920
    scroll = grid.get("scroll") or {}
    topology = grid.get("topology") or {}
    if wide_grid:
        layout = topology.get("layout") or {}
        graph = topology.get("graph") or {}
        grid_box = topology.get("grid") or {}
        context = topology.get("context") or {}
        if (
            not grid.get("visible")
            or topology.get("layout_display") != "grid"
            or not layout.get("width")
            or graph.get("width", 0) <= grid_box.get("width", 0)
            or grid_box.get("width", 0) < 340
            or grid_box.get("width", 0) > 500
            or context.get("width") != 300
            or scroll.get("no_fake_rail") is not True
            or (
                scroll.get("overflow", 0) > 1
                and scroll.get("rail_max") != scroll.get("overflow")
            )
            or (scroll.get("overflow", 0) > 1 and not scroll.get("rail_visible"))
            or (scroll.get("overflow", 0) <= 1 and scroll.get("rail_visible"))
            or (
                scroll.get("overflow", 0) > 1
                and not 0 < scroll.get("thumb_proportion", 0) < 1
            )
            or (
                scroll.get("overflow", 0) > 1
                and abs(
                    scroll.get("thumb_length", 0)
                    - max(
                        36,
                        round(
                            (scroll.get("client_height", 0) / scroll.get("scroll_height", 1))
                            * max(0, scroll.get("track_length", 0) - 4)
                        ),
                    )
                )
                > 1
            )
        ):
            fail(f"{target} wide response graph/grid topology or scrollbar failed: {grid!r}")
    else:
        if grid.get("visible") or topology.get("layout_display") != "block" or scroll.get("rail_visible"):
            fail(f"{target} compact response grid must be hidden without a fake rail: {grid!r}")
    expected_layouts = config.get("layouts") or {}
    if not wide:
        for label, expected in expected_layouts.items():
            widths = (measurement.get("splitter_evidence") or {}).get(label, {}).get("widths") or {}
            if any(widths.get(key) != value for key, value in expected.items()):
                fail(f"{target} {label} layout mismatch: expected {expected!r}, got {widths!r}")
            if widths.get("main", 0) < 720:
                fail(f"{target} {label} main region below 720px")
    else:
        for label, snapshot in (measurement.get("splitter_evidence") or {}).items():
            widths = snapshot.get("widths") or {}
            if (
                widths.get("main", 0) < 720
                or widths.get("aside") != 300
                or widths.get("response_layout", 0) != widths.get("main", 0) - 24
                or widths.get("plot", 0) + widths.get("grid", 0) + 2 != widths.get("response_layout", 0)
                or not 340 <= widths.get("grid", 0) <= 500
                or widths.get("plot_height", 0) < 450
            ):
                fail(f"{target} {label} wide layout or plot height mismatch: {widths!r}")
    plot = measurement.get("plot_domain") or {}
    if (
        plot.get("declared_series") != EXPECTED_SERIES
        or plot.get("domain_policy") != EXPECTED_POLICY
        or plot.get("declared_axis_maxima") != {"strain": 0.25, "stress_mpa": 1000}
    ):
        fail(f"{target} plot policy mismatch")
    axes = {
        "strain": derive_axis(0, 0.2, 0.1, 5, [1, 2, 2.5, 5, 10]),
        "stress_mpa": derive_axis(0, 850, 0.1, 4, [1, 2, 2.5, 5, 10]),
    }
    recomputed = plot.get("recomputed_domain") or {}
    for axis_name, expected_axis in axes.items():
        actual_axis = (recomputed.get("axes") or {}).get(axis_name) or {}
        for key, expected_value in expected_axis.items():
            close(actual_axis.get(key, -1), expected_value, f"{target} {axis_name} {key}", 0.01)
    svg = plot.get("svg") or {}
    rendered = svg.get("rendered_box") or {}
    view_box = svg.get("view_box") or {}
    if (
        rendered.get("width", 0) <= 0
        or rendered.get("height", 0) <= 0
        or view_box.get("width", 0) <= 0
        or view_box.get("height", 0) <= 0
        or svg.get("aspect_ratio_delta", 1) > 0.01
    ):
        fail(f"{target} rendered SVG/viewBox aspect ratio mismatch: {svg!r}")
    minimum_rendered_height = (
        235
        if measurement.get("viewport", {}).get("width") == 1366
        else 320
        if measurement.get("viewport", {}).get("width") == 1440
        else 450
    )
    if rendered.get("height", 0) < minimum_rendered_height:
        fail(
            f"{target} engineering graph does not use the available vertical workspace: "
            f"{rendered!r}"
        )
    plot_area = plot.get("plot_area") or {}
    plot_width = plot_area.get("right", 0) - plot_area.get("left", 0)
    plot_height = plot_area.get("bottom", 0) - plot_area.get("top", 0)
    minimum_plot_height = (
        150
        if measurement.get("viewport", {}).get("width") == 1366
        else 220
    )
    if plot_width < 600 or plot_height < minimum_plot_height or not 1.9 <= plot_width / plot_height <= 4.8:
        fail(f"{target} engineering plot proportion is outside the bounded range: {plot_area!r}")
    if (
        plot_area.get("left", -1) < 60
        or plot_area.get("right", -1) > view_box.get("width", 0)
        or plot_area.get("top", -1) < 20
        or plot_area.get("bottom", -1) > view_box.get("height", 0) - 40
    ):
        fail(f"{target} plot frame is not contained by the SVG viewBox: {plot_area!r}, {view_box!r}")
    path = plot.get("response_path") or {}
    endpoint = path.get("endpoint") or {}
    expected_endpoint = {
        "x": plot_area.get("left", 0) + 0.8 * plot_width,
        "y": plot_area.get("bottom", 0) - 0.85 * plot_height,
    }
    if (
        abs((endpoint.get("x") or -1) - expected_endpoint["x"]) > 0.8
        or abs((endpoint.get("y") or -1) - expected_endpoint["y"]) > 0.8
        or not path.get("fully_inside_plot")
    ):
        fail(f"{target} plot response endpoint/headroom mismatch: {plot!r}")
    if (
        (plot.get("headroom") or {}).get("right", 0) < plot_width * 0.12
        or (plot.get("headroom") or {}).get("top", 0) < plot_height * 0.08
    ):
        fail(f"{target} plot headroom is insufficient")
    collisions = plot.get("collision_checks") or {}
    if (
        not collisions.get("text_inside_view_box")
        or not collisions.get("no_text_collisions")
        or not collisions.get("no_text_frame_collisions")
        or collisions.get("titles") != ["Engineering strain", "Engineering stress (MPa)"]
        or any("MPa" in value for value in collisions.get("tick_values") or [])
        or any(not value.replace(",", "").replace(".", "", 1).isdigit() for value in collisions.get("tick_values") or [])
    ):
        fail(f"{target} plot title/tick/frame collision or labeling failure: {collisions!r}")
    legend = measurement.get("plot_legend") or {}
    plot_box = measurement.get("plot_box") or {}
    if abs(legend.get("width", -1) - plot_box.get("width", -2)) > 1 or legend.get("top", 0) <= plot_box.get("bottom", 0) - 1:
        fail(f"{target} compact legend is not bounded below the plot: {legend!r}, {plot_box!r}")
    first = measurement.get("first_viewport") or {}
    expected_first_viewport = measurement.get("viewport") if wide else config["viewport"]
    expected_first_viewport = {
        "width": expected_first_viewport["width"],
        "height": expected_first_viewport["height"],
    }
    if first.get("viewport") != expected_first_viewport or not first.get("all_inside"):
        fail(f"{target} first viewport containment failed")


def assert_related_or_empty(
    measurement: dict[str, Any], target: str, config: dict[str, Any]
) -> None:
    kind = config["kind"]
    expected_tab = "Related" if kind == "related" else "Overview"
    if (
        measurement.get("tabs", {}).get("labels") != EXPECTED_TABS
        or measurement.get("tabs", {}).get("active") != expected_tab
    ):
        fail(f"{target} tab state mismatch: {measurement.get('tabs')!r}")
    if kind == "related":
        related = measurement.get("related") or {}
        if related.get("row_count") != 2:
            fail(f"{target} must show two relations")
        directions = " ".join(related.get("directions") or [])
        if "Forward" not in directions or "Reverse" not in directions:
            fail(f"{target} forward/reverse relation wording missing")
        relationship_titles = related.get("relationship_titles") or []
        relationship_labels = related.get("directions") or []
        if len(relationship_labels) != 2 or len(relationship_titles) != 2:
            fail(f"{target} must expose both full relationship labels")
        generic_relationships = {"forward · source record", "reverse · referenced by"}
        for label, title in zip(relationship_labels, relationship_titles, strict=True):
            normalized = label.casefold().strip()
            if (
                len(label.strip()) <= 45
                or normalized in generic_relationships
                or title != label
                or not any(term in normalized for term in ("derived", "prepared"))
                or "record" not in normalized
            ):
                fail(f"{target} relationship label is generic, short, or unavailable in full text: {label!r}")
        if any(len(title) < 45 for title in related.get("record_titles") or []):
            fail(f"{target} long record titles are not present")
        if any("exact" not in revision.casefold() for revision in related.get("revisions") or []):
            fail(f"{target} exact-revision labels missing")
        if (
            related.get("table_horizontal_overflow", 1) > 0.6
            or related.get("table_scroll_horizontal_overflow", 1) > 0.6
            or not related.get("cells_inside_boundary")
        ):
            fail(f"{target} relation table containment failed: {related!r}")
        if related.get("primary_open_count") != 1 or not related.get("context_record"):
            fail(f"{target} relation context/primary consequence missing")
        if (measurement.get("topology_signature") or {}).get("nested_cards") != 0:
            fail(f"{target} related nested card hard gate failed")
    else:
        empty = measurement.get("empty") or {}
        record_header = empty.get("record_header") or {}
        if (
            not record_header.get("visible")
            or record_header.get("title") != "DP780 synthetic demo steel"
            or record_header.get("identity") != ["DP780-REF", "Metal", "Draft"]
            or record_header.get("synthetic_note")
            != "Synthetic reference data · not validated engineering data"
            or record_header.get("revision_context") != "Current revision\nr1 · Draft"
        ):
            fail(f"{target} must preserve the visible selected Record header/status context: {record_header!r}")
        if (
            not empty.get("empty_panel_visible")
            or empty.get("safe_return_label_count") != 1
            or empty.get("safe_return_primary_count") != 1
        ):
            fail(f"{target} empty panel/safe return missing: {empty!r}")
        if (
            empty.get("command_back_visible")
            or empty.get("property_count")
            or empty.get("curve_count")
            or empty.get("solver_row_count")
            or empty.get("delivery_section_count")
        ):
            fail(
                f"{target} empty state contains fabricated data or duplicate return control: {empty!r}"
            )
        if (
            "no displayable" not in empty.get("explanation", "").casefold()
            or "unavailable" not in empty.get("context", "").casefold()
        ):
            fail(f"{target} truthful empty explanation/context missing")
        if (measurement.get("topology_signature") or {}).get("nested_cards") != 0:
            fail(f"{target} empty nested card hard gate failed")


def wide_evidence_path(target: str, width: int, height: int) -> tuple[Path, Path]:
    stem = target
    return (
        IMAGE_DIR / f"{stem}.wide-evidence-{width}x{height}.png",
        IMAGE_DIR / f"{stem}.wide-evidence-{width}x{height}.measurements.json",
    )


def assert_preserved_hashes() -> None:
    for filename, expected in PRESERVED_MAT_DETAIL_EXCEPTIONAL_HASHES.items():
        image = IMAGE_DIR / filename
        if not image.is_file():
            fail(f"missing frozen MAT-DETAIL image: {image}")
        actual = hashlib.sha256(image.read_bytes()).hexdigest()
        if actual != expected:
            fail(f"frozen MAT-DETAIL image changed: {filename}: {actual}")


def assert_wide_evidence(target: str, config: dict[str, Any]) -> None:
    heights: list[float] = []
    for viewport in WIDE_VIEWPORTS:
        image, measurement_path = wide_evidence_path(target, viewport["width"], viewport["height"])
        if not image.is_file() or not measurement_path.is_file():
            fail(f"missing wide evidence for {target}: {image}")
        measurement = json.loads(measurement_path.read_text(encoding="utf-8"))
        assert_common(measurement, target, config, image, wide=True)
        assert_normal(measurement, target, config, wide=True)
        height = (measurement.get("plot_box") or {}).get("height", 0)
        if not 450 <= height <= 1550 or height > viewport["height"] * 0.75:
            fail(f"{target} wide plot height outside professional bounds: {viewport!r}, {height}")
        heights.append(height)
    if not heights[0] < heights[1]:
        fail(f"{target} graph height did not increase with wide viewport: {heights!r}")


def manifest_entry(target: str, manifest_path: Path) -> dict[str, Any] | None:
    if not manifest_path.is_file() or yaml is None:
        return None
    data = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    entries = [entry for entry in data.get("references", []) if entry.get("id") == target]
    return entries[0] if len(entries) == 1 else None


def assert_lifecycle(
    target: str,
    measurement: dict[str, Any],
    expected_status: str,
    expected_owner_approval: str,
    manifest_path: Path,
) -> None:
    entry = manifest_entry(target, manifest_path)
    if entry is not None and entry.get("image_sha256") != measurement.get("image_sha256"):
        # A corrected reference remains a pending staging candidate until the
        # common manifest is serially integrated by the main agent.
        entry = None
    if entry is None:
        if not STAGING_INDEX.is_file():
            fail(f"{target} is not in common manifest and staging index is missing")
        staging = json.loads(STAGING_INDEX.read_text(encoding="utf-8"))
        matches = [item for item in staging.get("references", []) if item.get("id") == target]
        if len(matches) != 1:
            fail(f"{target} missing from staging index")
        entry = matches[0]
    expected_reference_status = (
        "approved"
        if TARGETS[target]["kind"] != "normal" or expected_owner_approval == "approved"
        else "pending"
    )
    if entry.get("status") != expected_reference_status:
        fail(
            f"{target} lifecycle status is not {expected_reference_status}: "
            f"{entry.get('status')!r}"
        )
    expected_evaluation_status = expected_status if TARGETS[target]["kind"] == "normal" else "accepted"
    if (entry.get("main_agent_evaluation") or {}).get("status") != expected_evaluation_status:
        fail(
            f"{target} main-agent status mismatch: {(entry.get('main_agent_evaluation') or {}).get('status')!r}"
        )
    approval = entry.get("product_owner_approval") or {}
    if expected_reference_status == "pending":
        if approval != {"status": "absent"}:
            fail(f"{target} pending lifecycle must use absent owner approval: {approval!r}")
    elif (
        approval.get("status") != "approved"
        or not approval.get("date")
        or not approval.get("evidence")
    ):
        fail(f"{target} approved lifecycle lacks owner evidence: {approval!r}")
    if entry.get("image_sha256") != measurement.get("image_sha256"):
        fail(f"{target} lifecycle SHA-256 mismatch")


def validate_target(target: str, args: argparse.Namespace) -> list[str]:
    config = TARGETS[target]
    image = expected_image_path(target)
    measurement_path = expected_measurement_path(target)
    if not image.is_file() or not measurement_path.is_file():
        fail(f"missing canonical evidence for {target}")
    measurement = json.loads(measurement_path.read_text(encoding="utf-8"))
    assert_common(measurement, target, config, image)
    if config["kind"] == "normal":
        assert_normal(measurement, target, config)
    else:
        assert_related_or_empty(measurement, target, config)
    assert_lifecycle(
        target,
        measurement,
        args.expect_main_agent_status,
        args.expect_owner_approval,
        args.manifest,
    )
    responsive_paths: list[str] = []
    if config["kind"] in {"related", "empty"}:
        for width, height in ((1366, 768), (1440, 900), (1920, 1080)):
            is_canonical = width == 1440
            responsive_image = (
                image
                if is_canonical
                else IMAGE_DIR / f"{target}.responsive-{width}x{height}.png"
            )
            responsive_measurement = (
                measurement_path if is_canonical else responsive_image.with_suffix(".measurements.json")
            )
            if not responsive_image.is_file() or not responsive_measurement.is_file():
                fail(f"missing responsive evidence for {target} at {width}x{height}")
            responsive = json.loads(responsive_measurement.read_text(encoding="utf-8"))
            assert_common(
                responsive,
                target,
                config,
                responsive_image,
                responsive=not is_canonical,
            )
            assert_related_or_empty(responsive, target, config)
            responsive_paths.append(str(responsive_image.relative_to(ROOT)).replace("\\", "/"))
    return responsive_paths


def main() -> None:
    args = parse_args()
    if args.assert_preserved_hashes:
        assert_preserved_hashes()
        print("PASS preserved MAT-DETAIL related/empty canonical+responsive SHA-256")
    if args.wide_evidence:
        target = "materials-datasheet-overview-normal-1920x1080"
        config = TARGETS[target]
        validate_target(target, args)
        assert_wide_evidence(target, config)
        print(f"PASS {target} wide evidence 2560x1440/3840x2160")
        for viewport in WIDE_VIEWPORTS:
            _, measurement_path = wide_evidence_path(target, viewport["width"], viewport["height"])
            measurement = json.loads(measurement_path.read_text(encoding="utf-8"))
            print(
                f"wide_image_sha256 {viewport['width']}x{viewport['height']}: {measurement['image_sha256']}"
            )
        return
    targets = list(TARGETS) if args.all_packet_targets else [args.target]
    for target in targets:
        responsive = validate_target(target, args)
        print(f"PASS {target}")
        if responsive:
            print("responsive_evidence:")
            for path in responsive:
                print(f"  {path}")
        measurement = json.loads(expected_measurement_path(target).read_text(encoding="utf-8"))
        print(f"image_sha256: {measurement['image_sha256']}")


if __name__ == "__main__":
    main()

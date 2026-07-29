from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
from pathlib import Path
from typing import Any

import yaml

TARGET_ID_1440 = "materials-datasheet-overview-normal-1440x900"
TARGET_ID_1366 = "materials-datasheet-overview-normal-1366x768"
ROOT = Path(__file__).resolve().parents[3]
MANIFEST_PATH = ROOT / "docs/01-product/service-reference-manifest.yaml"
HTML_PATH = ROOT / "docs/00-research/ux-service-reference/materials-datasheet-overview-normal.html"
CSS_PATH = ROOT / "docs/00-research/ux-service-reference/materials-datasheet.css"
FROZEN_CSS_PATH = ROOT / "docs/00-research/ux-service-reference/reference.css"
JAVASCRIPT_PATH = ROOT / "docs/00-research/ux-service-reference/materials-datasheet.js"
CAPTURE_PATH = ROOT / "docs/00-research/ux-service-reference/capture_materials_datasheet.py"
TARGETS: dict[str, dict[str, Any]] = {
    TARGET_ID_1440: {
        "viewport": {"width": 1440, "height": 900, "device_scale_factor": 1},
        "image": ROOT
        / "docs/17-evidence/images/issue-167-service-reference/"
        "materials-datasheet-overview-normal-1440x900.png",
        "measurements": ROOT
        / "docs/17-evidence/images/issue-167-service-reference/"
        "materials-datasheet-overview-normal-1440x900.measurements.json",
        "navigator_width": 264,
        "datasheet_width": 1155,
        "main_width": 855,
        "aside_width": 300,
        "compact_max": 360,
        "splitter_states": {
            "default": (264, 5, 1155, 264),
            "navigator_arrow_right": (272, 5, 1147, 272),
            "navigator_home": (200, 5, 1219, 200),
            "navigator_end": (360, 5, 1059, 360),
        },
        "status": "approved",
    },
    TARGET_ID_1366: {
        "viewport": {"width": 1366, "height": 768, "device_scale_factor": 1},
        "image": ROOT
        / "docs/17-evidence/images/issue-167-service-reference/"
        "materials-datasheet-overview-normal-1366x768.png",
        "measurements": ROOT
        / "docs/17-evidence/images/issue-167-service-reference/"
        "materials-datasheet-overview-normal-1366x768.measurements.json",
        "css_override": ROOT
        / "docs/00-research/ux-service-reference/"
        "materials-datasheet-overview-normal-1366x768.css",
        "javascript_override": ROOT
        / "docs/00-research/ux-service-reference/"
        "materials-datasheet-overview-normal-1366x768.js",
        "navigator_width": 244,
        "datasheet_width": 1101,
        "main_width": 821,
        "aside_width": 280,
        "compact_max": 345,
        "splitter_states": {
            "default": (244, 5, 1101, 244),
            "navigator_arrow_right": (252, 5, 1093, 252),
            "navigator_home": (200, 5, 1145, 200),
            "navigator_end": (345, 5, 1000, 345),
        },
        "splitter_layouts": {
            "default": {"main": 821, "aside": 280, "plot": 797},
            "navigator_arrow_right": {"main": 813, "aside": 280, "plot": 789},
            "navigator_home": {"main": 865, "aside": 280, "plot": 841},
            "navigator_end": {"main": 720, "aside": 280, "plot": 696},
        },
        "status": "approved",
    },
}
EXPECTED_HEADERS = ["Property", "Value", "Unit", "Condition", "Source"]
EXPECTED_TABS = ["Overview", "Properties", "Curves", "CAE Cards", "Related", "Evidence"]
EXPECTED_SPLITTERS = TARGETS[TARGET_ID_1440]["splitter_states"]
EXPECTED_PLOT_AREA = {"left": 64, "right": 732, "top": 27, "bottom": 191}
EXPECTED_SERIES = {
    "strain": {"minimum": 0, "maximum": 0.2},
    "stress_mpa": {"minimum": 0, "maximum": 850},
}
EXPECTED_DOMAIN_POLICY = {
    "upper_headroom_ratio": 0.1,
    "target_intervals": {"strain": 5, "stress_mpa": 4},
    "nice_step_factors": [1, 2, 2.5, 5, 10],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate the Materials datasheet overview service reference."
    )
    parser.add_argument("--target", choices=sorted(TARGETS), help="Registered reference target id.")
    parser.add_argument(
        "--expect-main-agent-status",
        choices=["pending", "accepted", "rejected"],
        default="pending",
        help="Expected lifecycle status in the reference manifest.",
    )
    args = parser.parse_args()
    if args.target is None:
        parser.error("--target is required")
    return args


def fail(message: str) -> None:
    raise AssertionError(message)


def png_dimensions(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        fail(f"not a PNG: {path}")
    width, height = struct.unpack(">II", data[16:24])
    return width, height


def next_nice_step(rough_step: float, factors: list[float]) -> float:
    if rough_step <= 0 or not factors:
        fail(f"invalid nice-step inputs: {rough_step}, {factors}")
    exponent = math.floor(math.log10(rough_step))
    candidates = [
        factor * 10**power
        for power in range(exponent - 1, exponent + 3)
        for factor in factors
    ]
    return min(candidate for candidate in candidates if candidate >= rough_step - 1e-12)


def derive_axis(
    minimum: float,
    maximum: float,
    headroom_ratio: float,
    target_intervals: int,
    factors: list[float],
) -> dict[str, float]:
    padded_maximum = maximum + (maximum - minimum) * headroom_ratio
    rough_step = (padded_maximum - minimum) / target_intervals
    nice_step = next_nice_step(rough_step, factors)
    domain_maximum = math.ceil(padded_maximum / nice_step - 1e-12) * nice_step
    return {
        "padded_maximum": round(padded_maximum, 10),
        "rough_step": round(rough_step, 10),
        "nice_step": round(nice_step, 10),
        "domain_maximum": round(domain_maximum, 10),
    }


def recompute_plot_domain(plot_domain: dict[str, Any]) -> dict[str, Any]:
    series = plot_domain["declared_series"]
    policy = plot_domain["domain_policy"]
    factors = policy["nice_step_factors"]
    axes = {
        "strain": derive_axis(
            series["strain"]["minimum"],
            series["strain"]["maximum"],
            policy["upper_headroom_ratio"],
            policy["target_intervals"]["strain"],
            factors,
        ),
        "stress_mpa": derive_axis(
            series["stress_mpa"]["minimum"],
            series["stress_mpa"]["maximum"],
            policy["upper_headroom_ratio"],
            policy["target_intervals"]["stress_mpa"],
            factors,
        ),
    }
    area = plot_domain["plot_area"]
    return {
        "axes": axes,
        "expected_response_endpoint": {
            "x": round(
                area["left"]
                + (series["strain"]["maximum"] - series["strain"]["minimum"])
                / (axes["strain"]["domain_maximum"] - series["strain"]["minimum"])
                * (area["right"] - area["left"]),
                10,
            ),
            "y": round(
                area["bottom"]
                - (series["stress_mpa"]["maximum"] - series["stress_mpa"]["minimum"])
                / (axes["stress_mpa"]["domain_maximum"] - series["stress_mpa"]["minimum"])
                * (area["bottom"] - area["top"]),
                10,
            ),
        },
    }


def assert_manifest_entry(
    entry: dict[str, Any], target: str, config: dict[str, Any], expected_main_agent_status: str
) -> None:
    if entry.get("id") != target:
        fail(f"manifest entry id mismatch: {entry.get('id')!r}")
    if entry.get("screen") != "materials-datasheet-overview" or entry.get("state") != "normal":
        fail("manifest screen/state is not the packet 04 normal overview")
    if entry.get("viewport") != config["viewport"]:
        fail(f"manifest viewport mismatch: {entry.get('viewport')!r}")
    sources = entry.get("sources") or {}
    expected_sources = {
        "html": "docs/00-research/ux-service-reference/materials-datasheet-overview-normal.html",
        "css": "docs/00-research/ux-service-reference/reference.css",
        "css_detail": "docs/00-research/ux-service-reference/materials-datasheet.css",
        "javascript": "docs/00-research/ux-service-reference/materials-datasheet.js",
        "capture": "docs/00-research/ux-service-reference/capture_materials_datasheet.py",
        "validation": "docs/00-research/ux-service-reference/validate_materials_datasheet.py",
    }
    if target == TARGET_ID_1366:
        expected_sources.update(
            {
                "css_override": "docs/00-research/ux-service-reference/"
                "materials-datasheet-overview-normal-1366x768.css",
                "javascript_override": "docs/00-research/ux-service-reference/"
                "materials-datasheet-overview-normal-1366x768.js",
            }
        )
    if any(sources.get(key) != value for key, value in expected_sources.items()):
        fail(f"manifest source paths mismatch: {sources!r}")
    expected_image = (
        "docs/17-evidence/images/issue-167-service-reference/"
        f"{target}.png"
    )
    if entry.get("image") != expected_image:
        fail("manifest image path mismatch")
    expected_measurements = (
        "docs/17-evidence/images/issue-167-service-reference/"
        f"{target}.measurements.json"
    )
    if entry.get("measurements") != expected_measurements:
        fail("manifest measurements path mismatch")
    if str(entry.get("date")) != "2026-07-28":
        fail(f"manifest date mismatch: {entry.get('date')!r}")
    if entry.get("status") != config["status"]:
        fail(f"reference status mismatch: {entry.get('status')!r}")
    if (entry.get("main_agent_evaluation") or {}).get("status") != expected_main_agent_status:
        fail(
            "main-agent lifecycle mismatch: "
            f"{(entry.get('main_agent_evaluation') or {}).get('status')!r}"
        )
    product_owner_approval = entry.get("product_owner_approval") or {}
    if config["status"] == "approved":
        if (
            product_owner_approval.get("status") != "approved"
            or str(product_owner_approval.get("date")) != "2026-07-28"
            or not product_owner_approval.get("evidence")
        ):
            fail(f"product-owner approval is incomplete: {product_owner_approval!r}")
    elif product_owner_approval.get("status") != "absent":
        fail(f"pending target must not claim product-owner approval: {product_owner_approval!r}")


def assert_measurements(
    measurements: dict[str, Any], image_digest: str, target: str, config: dict[str, Any]
) -> None:
    if measurements.get("target") != target:
        fail(f"measurement target mismatch: {measurements.get('target')!r}")
    if measurements.get("viewport") != config["viewport"]:
        fail(f"measurement viewport mismatch: {measurements.get('viewport')!r}")
    if measurements.get("image_sha256") != image_digest:
        fail("measurement image SHA-256 does not match the rendered PNG")
    if measurements.get("console_errors") or measurements.get("page_errors"):
        fail(
            "browser errors recorded: "
            f"console={measurements.get('console_errors')!r}, "
            f"page={measurements.get('page_errors')!r}"
        )
    if any(value != 0 for value in (measurements.get("overflow") or {}).values()):
        fail(f"final normal viewport has page overflow: {measurements.get('overflow')!r}")
    if measurements.get("divider_visual_widths") != [1] or measurements.get(
        "visible_splitter_count"
    ) != 1:
        fail("normal overview must have one 5px splitter with a 1px visible rule")

    plot_domain = measurements.get("plot_domain") or {}
    if plot_domain.get("declared_series") != EXPECTED_SERIES:
        fail(f"plot series extrema mismatch: {plot_domain.get('declared_series')!r}")
    if plot_domain.get("domain_policy") != EXPECTED_DOMAIN_POLICY:
        fail(f"plot domain policy mismatch: {plot_domain.get('domain_policy')!r}")
    if plot_domain.get("plot_area") != EXPECTED_PLOT_AREA:
        fail(f"plot area mismatch: {plot_domain.get('plot_area')!r}")
    recomputed_domain = recompute_plot_domain(plot_domain)
    if plot_domain.get("recomputed_domain") != recomputed_domain:
        fail(
            "serialized derivation evidence disagrees with independent recomputation: "
            f"{plot_domain.get('recomputed_domain')!r}, {recomputed_domain!r}"
        )
    expected_axis_maxima = {
        axis: values["domain_maximum"] for axis, values in recomputed_domain["axes"].items()
    }
    if plot_domain.get("declared_axis_maxima") != expected_axis_maxima:
        fail(
            "serialized axis maxima disagree with declared data policy: "
            f"{plot_domain.get('declared_axis_maxima')!r}, {expected_axis_maxima!r}"
        )
    response_path = plot_domain.get("response_path") or {}
    bounding_box = response_path.get("bounding_box") or {}
    start = response_path.get("start") or {}
    endpoint = response_path.get("endpoint") or {}
    if abs(start.get("x", -999) - 64) > 0.6 or abs(start.get("y", -999) - 191) > 0.6:
        fail(f"response path must start at the plot origin: {start!r}")
    expected_endpoint = recomputed_domain["expected_response_endpoint"]
    if (
        abs(endpoint.get("x", -999) - expected_endpoint["x"]) > 0.6
        or abs(endpoint.get("y", -999) - expected_endpoint["y"]) > 0.6
    ):
        fail(f"response path endpoint mismatch: {endpoint!r}, {expected_endpoint!r}")
    if not response_path.get("fully_inside_plot"):
        fail(f"response path leaves plot area: {response_path!r}")
    if (
        bounding_box.get("x", -999) < EXPECTED_PLOT_AREA["left"]
        or bounding_box.get("right", 999) > EXPECTED_PLOT_AREA["right"]
        or bounding_box.get("y", -999) < EXPECTED_PLOT_AREA["top"]
        or bounding_box.get("bottom", 999) > EXPECTED_PLOT_AREA["bottom"]
    ):
        fail(f"response path bounding box leaves plot area: {bounding_box!r}")
    headroom = plot_domain.get("headroom") or {}
    if headroom.get("right", -999) < 120 or headroom.get("top", -999) < 20:
        fail(f"plot headroom is insufficient: {headroom!r}")
    visible_text = plot_domain.get("visible_text") or {}
    required_plot_text = {
        "0",
        "0.10",
        "0.20",
        "0.25",
        "500",
        "1,000 MPa",
        "Engineering strain",
        "Engineering stress",
    }
    if not required_plot_text.issubset(set(visible_text.get("plot") or [])):
        fail(f"required plot tick/axis text is missing: {visible_text.get('plot')!r}")
    if not any(
        "Representative response" in legend and "Condition: Ambient · as received" in legend
        for legend in visible_text.get("legend") or []
    ):
        fail(f"required plot legend/condition text is missing: {visible_text.get('legend')!r}")

    regions = measurements.get("regions") or {}
    expected_regions = {
        "application_bar": {"height": 46},
        "command_bar": {"height": 38},
        "workspace": {
            "x": 8,
            "width": config["viewport"]["width"] - 16,
            "height": config["viewport"]["height"] - 108,
        },
        "navigator": {"width": config["navigator_width"]},
        "navigator_divider": {"width": 5},
        "datasheet": {"width": config["datasheet_width"]},
        "datasheet_main": {"width": config["main_width"]},
        "datasheet_aside": {"width": config["aside_width"]},
        "status_bar": {"height": 24},
    }
    for region, expected in expected_regions.items():
        actual = regions.get(region) or {}
        for key, value in expected.items():
            if abs(actual.get(key, -999) - value) > 0.6:
                fail(f"{region}.{key}: expected {value}, got {actual.get(key)!r}")

    splitter_evidence = measurements.get("splitter_evidence") or {}
    expected_splitters = config["splitter_states"]
    if set(splitter_evidence) != set(expected_splitters):
        fail(f"splitter evidence labels mismatch: {sorted(splitter_evidence)}")
    for label, expected in expected_splitters.items():
        snapshot = splitter_evidence[label]
        widths = snapshot.get("widths") or {}
        actual_widths = (widths.get("navigator"), widths.get("divider"), widths.get("datasheet"))
        if actual_widths != expected[:3]:
            fail(f"{label} widths: expected {expected[:3]}, got {actual_widths}")
        aria = snapshot.get("aria") or {}
        if (
            aria.get("now") != expected[3]
            or aria.get("minimum") != 200
            or aria.get("maximum") != config["compact_max"]
        ):
            fail(f"{label} ARIA range: got {aria!r}")
        if widths.get("navigator") != aria.get("now"):
            fail(f"{label} pane/ARIA continuity failed: widths={widths!r}, aria={aria!r}")
        if any(value != 0 for value in (snapshot.get("overflow") or {}).values()):
            fail(f"{label} page overflow: {snapshot.get('overflow')!r}")
        tree = snapshot.get("tree_scroller") or {}
        if (
            tree.get("horizontal_overflow") != 0
            or not tree.get("all_tree_kind_right_edges_within_content")
            or not tree.get("tree_kind_labels_match")
        ):
            fail(f"{label} tree containment failed: {tree!r}")
        if not snapshot.get("selected_record_visible") or not snapshot.get("delivery_visible"):
            fail(f"{label} selected Record or delivery action disappeared")
        expected_layout = (config.get("splitter_layouts") or {}).get(label)
        if expected_layout:
            actual_layout = {key: widths.get(key) for key in expected_layout}
            if actual_layout != expected_layout:
                fail(
                    f"{label} main/aside/plot widths: expected {expected_layout!r}, "
                    f"got {actual_layout!r}"
                )
            if widths.get("main", 0) < 720:
                fail(f"{label} main data region is below 720px: {widths!r}")
            property = snapshot.get("property_containment") or {}
            cells = property.get("cells") or []
            header_cells = [cell for cell in cells if cell.get("section") == "header"]
            body_cells = [cell for cell in cells if cell.get("section") == "body"]
            if len(cells) != 25 or len(header_cells) != 5 or len(body_cells) != 20:
                fail(f"{label} property cells are incomplete: {property!r}")
            if (
                property.get("table_horizontal_overflow", 999) > 0.6
                or property.get("container_horizontal_overflow", 999) > 0.6
                or not property.get("all_cells_within_table_horizontal_boundary")
                or not property.get("all_cell_scroll_widths_within_client_width")
                or any(
                    not cell.get("within_table_horizontal_boundary")
                    or not cell.get("scroll_width_within_client_width")
                    for cell in cells
                )
            ):
                fail(f"{label} property containment failed: {property!r}")

    density = measurements.get("row_density") or {}
    tree_density = density.get("tree") or {}
    if tree_density.get("count", 0) < 6 or not (
        24 <= tree_density.get("minimum", 0) <= 26
        and 24 <= tree_density.get("maximum", 0) <= 26
    ):
        fail(f"tree density is not 25px: {tree_density!r}")
    property_density = density.get("properties") or {}
    if property_density.get("count") != 4 or not (
        30 <= property_density.get("minimum", 0) <= 34
        and 30 <= property_density.get("maximum", 0) <= 34
    ):
        fail(f"property density is not 30-34px: {property_density!r}")
    final_tree = measurements.get("tree_scroller") or {}
    if (
        final_tree.get("horizontal_overflow") != 0
        or not final_tree.get("all_tree_kind_right_edges_within_content")
        or not final_tree.get("tree_kind_labels_match")
    ):
        fail(f"final tree containment failed: {final_tree!r}")

    if measurements.get("selected_tree_rows") != 1 or not measurements.get("selected_record"):
        fail("selected DP780 Record count is not exactly one")
    tabs = measurements.get("tabs") or {}
    if tabs.get("count") != 6 or tabs.get("labels") != EXPECTED_TABS:
        fail(f"datasheet tabs mismatch: {tabs!r}")
    if tabs.get("active") != "Overview" or not tabs.get("related_visible"):
        fail(f"Overview/Related tab state is not normal: {tabs!r}")
    if measurements.get("property_headers") != EXPECTED_HEADERS:
        fail(f"property headers mismatch: {measurements.get('property_headers')!r}")
    if measurements.get("property_rows") != 4:
        fail("property row count is not four")
    for row in measurements.get("property_semantics") or []:
        if len(row) != 5 or any(not str(value).strip() for value in row[2:]):
            fail(f"property row is missing unit/condition/source semantics: {row!r}")

    formats = measurements.get("solver_formats") or []
    if measurements.get("solver_format_count") != 2 or [
        (row.get("solver"), row.get("format")) for row in formats
    ] != [("Abaqus", ".inp"), ("OpenRadioss", ".rad")]:
        fail(f"solver format set mismatch: {formats!r}")
    if measurements.get("delivery_preview_count") != 2 or measurements.get(
        "delivery_download_count"
    ) != 2:
        fail("both Preview and Download entry points must be visible for both formats")
    if measurements.get("primary_command_count") != 1:
        fail("normal datasheet overview must have one filled primary command")
    if measurements.get("nested_persistent_card_count") != 0:
        fail("nested persistent cards are present")
    if measurements.get("forbidden_visible_terms") or measurements.get("unsupported_labels"):
        fail(
            "forbidden visible content: "
            f"technical={measurements.get('forbidden_visible_terms')!r}, "
            f"unsupported={measurements.get('unsupported_labels')!r}"
        )
    interactions = measurements.get("interactions") or {}
    if not interactions or not all(interactions.values()):
        fail(f"ordinary interaction consequences are incomplete: {interactions!r}")
    if target == TARGET_ID_1366:
        first_viewport = measurements.get("first_viewport") or {}
        expected_viewport_groups = {
            "selected_dp780": 1,
            "tabs": 6,
            "property_headers": 5,
            "property_rows": 4,
            "representative_graph": 1,
            "application_condition": 1,
            "cae_delivery": 1,
            "formats": 2,
            "preview_controls": 2,
            "download_controls": 2,
        }
        if first_viewport.get("viewport") != {
            "width": config["viewport"]["width"],
            "height": config["viewport"]["height"],
        }:
            fail(f"first viewport dimensions mismatch: {first_viewport!r}")
        if abs(first_viewport.get("status_bar_top", -999) - regions["status_bar"]["y"]) > 0.6:
            fail(f"first viewport status boundary mismatch: {first_viewport!r}")
        viewport_groups = first_viewport.get("groups") or {}
        if any(
            len(viewport_groups.get(group) or []) != count
            for group, count in expected_viewport_groups.items()
        ):
            fail(f"first viewport required boxes are incomplete: {first_viewport!r}")
        if not first_viewport.get("all_required_boxes_inside_viewport_above_status_bar"):
            fail(f"first viewport containment summary failed: {first_viewport!r}")
        if any(
            not entry.get("inside_viewport_above_status_bar")
            for entries in viewport_groups.values()
            for entry in entries
        ):
            fail(f"first viewport box containment failed: {first_viewport!r}")
        audit = measurements.get("web_interface_guidelines_audit") or {}
        required_audit_checks = {
            "semantic buttons, links, tabs and associated labels",
            "visible keyboard focus",
            "no fake controls or non-dialog ellipsis labels",
            "no render-time layout loop",
            "deliberate containment and truncation",
        }
        if audit.get("result") != "pass" or not required_audit_checks.issubset(
            set(audit.get("checked") or [])
        ):
            fail(f"Web Interface Guidelines audit is incomplete: {audit!r}")


def main() -> None:
    args = parse_args()
    target = args.target
    config = TARGETS[target]
    if not HTML_PATH.is_file() or not CSS_PATH.is_file() or not FROZEN_CSS_PATH.is_file():
        fail("registered HTML/CSS source is missing")
    if not JAVASCRIPT_PATH.is_file() or not CAPTURE_PATH.is_file():
        fail("registered JavaScript/capture source is missing")
    for override_key in ("css_override", "javascript_override"):
        override = config.get(override_key)
        if override is not None and not Path(override).is_file():
            fail(f"target override source is missing: {override}")
    image_path = Path(config["image"])
    measurements_path = Path(config["measurements"])
    if not image_path.is_file() or not measurements_path.is_file():
        fail("rendered image or measurements are missing")

    manifest = yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))
    entries = [entry for entry in manifest.get("references", []) if entry.get("id") == target]
    if len(entries) != 1:
        fail(f"expected one manifest entry for {target}, found {len(entries)}")
    assert_manifest_entry(entries[0], target, config, args.expect_main_agent_status)

    expected_dimensions = (config["viewport"]["width"], config["viewport"]["height"])
    if png_dimensions(image_path) != expected_dimensions:
        fail(f"image viewport mismatch: {png_dimensions(image_path)}")
    image_digest = hashlib.sha256(image_path.read_bytes()).hexdigest()
    measurements = json.loads(measurements_path.read_text(encoding="utf-8"))
    assert_measurements(measurements, image_digest, target, config)
    if entries[0].get("image_sha256") != image_digest:
        fail("manifest image_sha256 does not match the rendered PNG")

    print(f"PASS {target}")
    print(f"image_sha256: {image_digest}")
    print(
        "measurements: geometry, splitter extremes, density, tabs, "
        "properties, delivery, interactions"
    )


if __name__ == "__main__":
    main()

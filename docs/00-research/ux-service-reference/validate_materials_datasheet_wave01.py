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
                "plot": 1295,
            },
            "navigator_arrow_right": {
                "navigator": 288,
                "divider": 5,
                "datasheet": 1611,
                "main": 1311,
                "aside": 300,
                "plot": 1287,
            },
            "navigator_home": {
                "navigator": 200,
                "divider": 5,
                "datasheet": 1699,
                "main": 1399,
                "aside": 300,
                "plot": 1375,
            },
            "navigator_end": {
                "navigator": 360,
                "divider": 5,
                "datasheet": 1539,
                "main": 1239,
                "aside": 300,
                "plot": 1215,
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
EXPECTED_PLOT_AREA = {"left": 64, "right": 732, "top": 27, "bottom": 191}


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
        "--expect-main-agent-status", default="pending", choices=["pending", "accepted", "rejected"]
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=MANIFEST,
        help="Optional common manifest after main-agent integration.",
    )
    args = parser.parse_args()
    if not args.target and not args.all_packet_targets:
        parser.error("provide --target or --all-packet-targets")
    if args.target and args.all_packet_targets:
        parser.error("--target and --all-packet-targets are mutually exclusive")
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


def assert_common(
    measurement: dict[str, Any],
    target: str,
    config: dict[str, Any],
    image: Path,
    *,
    responsive: bool = False,
) -> None:
    viewport = measurement.get("viewport")
    allowed_viewports = (
        {"width": 1366, "height": 768, "device_scale_factor": 1},
        {"width": 1440, "height": 900, "device_scale_factor": 1},
        {"width": 1920, "height": 1080, "device_scale_factor": 1},
    )
    if (not responsive and viewport != config["viewport"]) or (
        responsive and viewport not in allowed_viewports
    ):
        fail(f"{target} viewport mismatch: {viewport!r}")
    if measurement.get("target") != target:
        fail(f"measurement target mismatch: {measurement.get('target')!r}")
    if measurement.get("responsive_evidence") is not responsive:
        fail(f"responsive flag mismatch for {target}")
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
    if (
        tree.get("horizontal_overflow") != 0
        or not tree.get("all_tree_kind_right_edges_within_content")
        or not tree.get("tree_kind_labels_match")
    ):
        fail(f"{target} tree containment failed: {tree!r}")
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
        if (
            tree_state.get("horizontal_overflow") != 0
            or not tree_state.get("all_tree_kind_right_edges_within_content")
            or not tree_state.get("tree_kind_labels_match")
        ):
            fail(f"{target} {label} tree containment failed")
        if not snapshot.get("selected_record_visible"):
            fail(f"{target} {label} selected Record is not visible")
    interactions = measurement.get("interactions") or {}
    if not interactions or not all(interactions.values()):
        fail(f"{target} interaction evidence incomplete: {interactions!r}")


def assert_normal(measurement: dict[str, Any], target: str, config: dict[str, Any]) -> None:
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
    expected_layouts = config.get("layouts") or {}
    for label, expected in expected_layouts.items():
        widths = (measurement.get("splitter_evidence") or {}).get(label, {}).get("widths") or {}
        if any(widths.get(key) != value for key, value in expected.items()):
            fail(f"{target} {label} layout mismatch: expected {expected!r}, got {widths!r}")
        if widths.get("main", 0) < 720:
            fail(f"{target} {label} main region below 720px")
    plot = measurement.get("plot_domain") or {}
    if (
        plot.get("declared_series") != EXPECTED_SERIES
        or plot.get("domain_policy") != EXPECTED_POLICY
        or plot.get("plot_area") != EXPECTED_PLOT_AREA
    ):
        fail(f"{target} plot policy mismatch")
    axes = {
        "strain": derive_axis(0, 0.2, 0.1, 5, [1, 2, 2.5, 5, 10]),
        "stress_mpa": derive_axis(0, 850, 0.1, 4, [1, 2, 2.5, 5, 10]),
    }
    expected_derivation = {"axes": axes, "expected_response_endpoint": {"x": 598.4, "y": 51.6}}
    if plot.get("recomputed_domain") not in (None, expected_derivation):
        fail(f"{target} plot derivation evidence unexpected")
    path = plot.get("response_path") or {}
    endpoint = path.get("endpoint") or {}
    if (
        abs((endpoint.get("x") or -1) - 598.4) > 0.6
        or abs((endpoint.get("y") or -1) - 51.6) > 0.6
        or not path.get("fully_inside_plot")
    ):
        fail(f"{target} plot response endpoint/headroom mismatch: {plot!r}")
    if (plot.get("headroom") or {}).get("right", 0) < 120 or (plot.get("headroom") or {}).get(
        "top", 0
    ) < 20:
        fail(f"{target} plot headroom is insufficient")
    first = measurement.get("first_viewport") or {}
    if first.get("viewport") != {
        "width": config["viewport"]["width"],
        "height": config["viewport"]["height"],
    } or not first.get("all_inside"):
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


def manifest_entry(target: str, manifest_path: Path) -> dict[str, Any] | None:
    if not manifest_path.is_file() or yaml is None:
        return None
    data = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    entries = [entry for entry in data.get("references", []) if entry.get("id") == target]
    return entries[0] if len(entries) == 1 else None


def assert_lifecycle(
    target: str, measurement: dict[str, Any], expected_status: str, manifest_path: Path
) -> None:
    entry = manifest_entry(target, manifest_path)
    if entry is None:
        if not STAGING_INDEX.is_file():
            fail(f"{target} is not in common manifest and staging index is missing")
        staging = json.loads(STAGING_INDEX.read_text(encoding="utf-8"))
        matches = [item for item in staging.get("references", []) if item.get("id") == target]
        if len(matches) != 1:
            fail(f"{target} missing from staging index")
        entry = matches[0]
    if entry.get("status") != "pending":
        fail(f"{target} lifecycle status is not pending: {entry.get('status')!r}")
    if (entry.get("main_agent_evaluation") or {}).get("status") != expected_status:
        fail(
            f"{target} main-agent status mismatch: {(entry.get('main_agent_evaluation') or {}).get('status')!r}"
        )
    if (entry.get("product_owner_approval") or {}).get("status") != "absent":
        fail(f"{target} must not claim product-owner approval")
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
    assert_lifecycle(target, measurement, args.expect_main_agent_status, args.manifest)
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

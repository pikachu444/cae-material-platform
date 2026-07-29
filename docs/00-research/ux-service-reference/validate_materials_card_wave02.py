# ruff: noqa: E501
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
REFERENCE_DIR = ROOT / "docs/00-research/ux-service-reference"
IMAGE_DIR = ROOT / "docs/17-evidence/images/issue-167-service-reference"
STAGING_INDEX = IMAGE_DIR / "materials-card-wave02.staging.json"
STATE_EVIDENCE = REFERENCE_DIR / "materials-card-wave02.state-evidence.json"

TARGETS = {
    "materials-card-preview-normal-1366x768": {"state": "normal", "width": 1366, "height": 768},
    "materials-card-preview-normal-1440x900": {"state": "normal", "width": 1440, "height": 900},
    "materials-card-preview-normal-1920x1080": {"state": "normal", "width": 1920, "height": 1080},
    "materials-card-approximation-blocked-1440x900": {"state": "approximation", "width": 1440, "height": 900},
    "materials-card-unsupported-blocked-1440x900": {"state": "unsupported", "width": 1440, "height": 900},
}

LEGACY_ACTIVE_ROUTE_SELECTORS = (
    "page-stack",
    "page-heading",
    "content-card",
    "module-material-card",
    "hero-actions",
    "eyebrow",
    "status-badge",
    "count-chip",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate the WAVE-02 MAT-CARD static-reference family.")
    parser.add_argument("--target", choices=sorted(TARGETS), help="Validate one canonical target.")
    parser.add_argument("--all-packet-targets", action="store_true", help="Validate all five targets plus responsive/state evidence.")
    parser.add_argument("--expect-main-agent-status", choices=["pending", "approved"], default=None)
    args = parser.parse_args()
    if not args.target and not args.all_packet_targets:
        parser.error("provide --target or --all-packet-targets")
    if args.target and args.all_packet_targets:
        parser.error("--target and --all-packet-targets are mutually exclusive")
    return args


def fail(message: str) -> None:
    raise AssertionError(message)


def read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        fail(f"missing JSON evidence: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"invalid JSON {path}: {exc}")
    if not isinstance(value, dict):
        fail(f"JSON root is not an object: {path}")
    return value


def dimensions(path: Path) -> tuple[int, int]:
    if not path.is_file():
        fail(f"missing image: {path}")
    data = path.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        fail(f"not a PNG: {path}")
    return struct.unpack(">II", data[16:24])


def expect_equal(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        fail(f"{label}: expected {expected!r}, got {actual!r}")


def validate_visual_acceptance_evidence(entry: dict[str, Any], label: str) -> None:
    expected_legacy_report = {selector: 0 for selector in LEGACY_ACTIVE_ROUTE_SELECTORS}
    expect_equal(entry.get("legacy_selector_report"), expected_legacy_report, f"{label} active-route legacy selectors")
    typography = entry.get("typography")
    if not isinstance(typography, dict):
        fail(f"{label} missing computed typography evidence")
    expect_equal(typography.get("body_px"), 13, f"{label} body typography")
    expected_data_keys = ("tree_row_px", "native_preview_data_px", "mapping_primary_px", "delivery_value_px")
    for key in expected_data_keys:
        value = typography.get(key)
        if not isinstance(value, (int, float)) or not 12 <= value <= 13:
            fail(f"{label} {key} is outside the readable 12-13px data/metadata system: {value!r}")


def validate_persisted_screenshot(entry: dict[str, Any], expected_path: Path, viewport: dict[str, int], label: str) -> None:
    expect_equal(entry.get("image"), expected_path.relative_to(ROOT).as_posix(), f"{label} image path")
    expect_equal(dimensions(expected_path), (viewport["width"], viewport["height"]), f"{label} persisted image dimensions")
    expect_equal(entry.get("screenshot_dimensions"), {"width": viewport["width"], "height": viewport["height"]}, f"{label} recorded image dimensions")
    expect_equal(hashlib.sha256(expected_path.read_bytes()).hexdigest(), entry.get("screenshot_sha256"), f"{label} persisted image SHA-256")


def validate_sources(staging: dict[str, Any]) -> None:
    expected_sources = {
        "html": "docs/00-research/ux-service-reference/materials-card-preview-normal.html",
        "css": "docs/00-research/ux-service-reference/materials-card-preview.css",
        "javascript": "docs/00-research/ux-service-reference/materials-card-preview.js",
    }
    for key, expected in expected_sources.items():
        paths = {entry.get(key) for entry in staging["references"]}
        expect_equal(paths, {expected}, f"source {key}")
    source_html = ROOT / "docs/00-research/ux-service-reference/materials-card-preview-normal.html"
    source_css = ROOT / "docs/00-research/ux-service-reference/materials-card-preview.css"
    source_js = ROOT / "docs/00-research/ux-service-reference/materials-card-preview.js"
    for path in (source_html, source_css, source_js):
        if not path.is_file() or not path.read_text(encoding="utf-8").strip():
            fail(f"empty MAT-CARD source: {path}")
    html = source_html.read_text(encoding="utf-8")
    for marker in ("data-region=\"navigator\"", "data-region=\"card-panel\"", "Native preview", "Delivery properties", "Advanced mapping evidence", "CAE Cards"):
        if marker not in html:
            fail(f"MAT-CARD HTML missing marker: {marker}")


def validate_common(entry: dict[str, Any], config: dict[str, Any], measurement: dict[str, Any]) -> None:
    target = entry["id"]
    viewport = config
    expect_equal(entry.get("status"), "pending", f"{target} status")
    expect_equal(entry.get("viewport"), {"width": viewport["width"], "height": viewport["height"], "device_scale_factor": 1}, f"{target} viewport")
    expect_equal(measurement.get("viewport"), entry["viewport"], f"{target} measurement viewport")
    image = ROOT / entry["image"]
    expect_equal(dimensions(image), (viewport["width"], viewport["height"]), f"{target} image dimensions")
    digest = hashlib.sha256(image.read_bytes()).hexdigest()
    expect_equal(digest, entry.get("image_sha256"), f"{target} staging SHA-256")
    expect_equal(digest, measurement.get("image_sha256"), f"{target} measurement SHA-256")
    if measurement.get("console_errors") or measurement.get("page_errors"):
        fail(f"{target} browser errors: {measurement.get('console_errors')} {measurement.get('page_errors')}")
    expect_equal(measurement.get("overflow"), {"document_horizontal": 0, "document_vertical": 0, "body_horizontal": 0, "body_vertical": 0}, f"{target} document/body overflow")
    expect_equal(measurement.get("selected_record"), True, f"{target} selected Record")
    expect_equal(measurement.get("tree", {}).get("horizontal_overflow"), 0, f"{target} navigator horizontal overflow")
    expect_equal(measurement.get("tree", {}).get("kinds_inside"), True, f"{target} navigator type containment")
    expect_equal(measurement.get("tree", {}).get("labels_match"), True, f"{target} navigator labels")
    expect_equal(measurement.get("tree", {}).get("labels_have_title"), True, f"{target} navigator title containment")
    expect_equal(measurement.get("tabs", {}).get("count"), 6, f"{target} tab count")
    expect_equal(measurement.get("tabs", {}).get("active"), "CAE Cards", f"{target} active tab")
    expect_equal(measurement.get("nested_persistent_card_count"), 0, f"{target} nested persistent cards")
    if measurement.get("forbidden_visible_terms"):
        fail(f"{target} forbidden primary-path terms: {measurement['forbidden_visible_terms']}")
    validate_visual_acceptance_evidence(measurement, target)
    card = measurement.get("card", {})
    regions = card.get("regions", {})
    delivery_width = card.get("delivery_width")
    native_width = card.get("native_width")
    if not isinstance(delivery_width, int) or not 300 <= delivery_width <= 320:
        fail(f"{target} delivery sheet width is not 300-320px: {delivery_width}")
    if not isinstance(native_width, int) or native_width <= delivery_width:
        fail(f"{target} native preview is not dominant: {native_width} / {delivery_width}")
    validate_preview_height_and_decision(card, target)
    expect_equal(measurement.get("interactions", {}).get("navigator_search"), True, f"{target} search shortcut")
    expect_equal(measurement.get("interactions", {}).get("tree_keyboard"), True, f"{target} tree keyboard")
    expect_equal(measurement.get("interactions", {}).get("tabs"), True, f"{target} tab keyboard/click")
    expect_equal(measurement.get("interactions", {}).get("advanced_disclosure"), True, f"{target} advanced disclosure")
    if not all(regions.get(key) for key in ("card_panel", "card_heading", "card_content", "native_preview", "delivery_sheet")):
        fail(f"{target} required card regions missing: {regions}")


def validate_preview_height_and_decision(card: dict[str, Any], target: str) -> None:
    if card.get("native_text_visible"):
        available_height = card.get("preview_available_height")
        rendered_height = card.get("preview_rendered_height")
        if not isinstance(available_height, int) or not isinstance(rendered_height, int) or rendered_height < available_height - 1:
            fail(f"{target} native preview does not use available pane height: {rendered_height} / {available_height}")
        expect_equal(card.get("preview_fills_available_height"), True, f"{target} native preview fills available height")
    expect_equal(card.get("delivery_summary_present"), False, f"{target} redundant delivery header status")
    expect_equal(card.get("decision_text_clipped"), [], f"{target} clipped decision text")


def validate_state(measurement: dict[str, Any], state: str, target: str) -> None:
    card = measurement.get("card", {})
    validate_preview_height_and_decision(card, target)
    if state == "normal":
        expect_equal(card.get("native_text_visible"), True, f"{target} native text visible")
        expect_equal(card.get("unavailable_visible"), False, f"{target} unavailable state")
        expect_equal(card.get("loading_visible"), False, f"{target} loading state")
        expect_equal(card.get("download"), {"text": "Download .inp", "disabled": False, "primary": True}, f"{target} exact command")
        expect_equal(card.get("approximation_acknowledged"), False, f"{target} unexpected acknowledgement")
        if any("APPROXIMATED" in row or "UNSUPPORTED" in row for row in card.get("mapping_rows", [])):
            fail(f"{target} normal mapping includes blocked state")
        expect_equal(measurement.get("interactions", {}).get("state_command"), True, f"{target} exact command interaction")
    elif state == "approximation":
        expect_equal(card.get("native_text_visible"), True, f"{target} approximation native text")
        expect_equal(card.get("approximation_acknowledged"), False, f"{target} canonical acknowledgement")
        if not any("post-necking extension" in row for row in card.get("mapping_rows", [])):
            fail(f"{target} named approximation missing")
        expect_equal(card.get("download", {}).get("text"), "Download .rad", f"{target} approximation command label")
        expect_equal(card.get("download", {}).get("disabled"), True, f"{target} approximation command blocked")
        expect_equal(card.get("download", {}).get("primary"), True, f"{target} approximation primary command treatment")
        expect_equal(measurement.get("interactions", {}).get("state_command"), True, f"{target} acknowledgement interaction")
    elif state == "unsupported":
        expect_equal(card.get("native_text_visible"), False, f"{target} unsupported fake preview")
        expect_equal(card.get("unavailable_visible"), True, f"{target} unavailable explanation")
        expect_equal(card.get("download"), {"text": "Download blocked", "disabled": True, "primary": False}, f"{target} unsupported command")
        expect_equal(card.get("open_modeling_visible"), True, f"{target} Open Modeling recovery")
        expect_equal(card.get("back_to_cards_visible"), True, f"{target} Back to CAE Cards recovery")
        if not any("damage initiation" in row for row in card.get("mapping_rows", [])):
            fail(f"{target} unsupported field missing")
        expect_equal(measurement.get("interactions", {}).get("state_command"), True, f"{target} unsupported recovery interaction")


def validate_responsive(target: str, state: str, canonical: dict[str, Any]) -> None:
    canonical_regions = canonical.get("card", {}).get("regions", {})
    canonical_topology = tuple(key for key in ("card_panel", "card_heading", "card_content", "native_preview", "delivery_sheet") if key in canonical_regions)
    for key in ("1366x768", "1920x1080"):
        image = IMAGE_DIR / f"{target}.responsive-{key}.png"
        measurement_path = IMAGE_DIR / f"{target}.responsive-{key}.measurements.json"
        measurement = read_json(measurement_path)
        width, height = map(int, key.split("x"))
        expect_equal(dimensions(image), (width, height), f"{target} responsive {key} image dimensions")
        expect_equal(hashlib.sha256(image.read_bytes()).hexdigest(), measurement.get("image_sha256"), f"{target} responsive {key} SHA-256")
        expect_equal(measurement.get("overflow"), {"document_horizontal": 0, "document_vertical": 0, "body_horizontal": 0, "body_vertical": 0}, f"{target} responsive {key} overflow")
        responsive_regions = measurement.get("card", {}).get("regions", {})
        expect_equal(set(responsive_regions).intersection(canonical_topology), set(canonical_topology), f"{target} responsive {key} topology")
        expect_equal(measurement.get("state"), state, f"{target} responsive {key} state")
        validate_state(measurement, state, f"{target}.responsive-{key}")


def validate_state_evidence() -> None:
    evidence = read_json(STATE_EVIDENCE)
    expect_equal(evidence.get("family"), "MAT-CARD", "state evidence family")
    for state in ("long", "loading", "error"):
        for key, viewport in (("1366x768", {"width": 1366, "height": 768, "device_scale_factor": 1}), ("1440x900", {"width": 1440, "height": 900, "device_scale_factor": 1}), ("1920x1080", {"width": 1920, "height": 1080, "device_scale_factor": 1})):
            entry = evidence.get("states", {}).get(state, {}).get(key)
            if not entry:
                fail(f"missing {state}/{key} evidence")
            expect_equal(entry.get("viewport"), viewport, f"{state}/{key} evidence viewport")
            expect_equal(entry.get("screenshot_dimensions"), {"width": viewport["width"], "height": viewport["height"]}, f"{state}/{key} evidence dimensions")
            expected_image = IMAGE_DIR / f"materials-card-state-{state}-{key}.png"
            validate_persisted_screenshot(entry, expected_image, viewport, f"{state}/{key}")
            expect_equal(entry.get("overflow"), {"document_horizontal": 0, "document_vertical": 0, "body_horizontal": 0, "body_vertical": 0}, f"{state}/{key} evidence overflow")
            if entry.get("console_errors") or entry.get("page_errors"):
                fail(f"browser errors in {state}/{key}: {entry.get('console_errors')} {entry.get('page_errors')}")
            validate_visual_acceptance_evidence(entry, f"{state}/{key}")
            validate_preview_height_and_decision(entry.get("card", {}), f"{state}/{key}")
    for key, entry in evidence["states"]["long"].items():
        if entry["card"]["preview_scroll_height"] <= entry["card"]["preview_client_height"]:
            fail(f"long evidence {key} is not independently scrollable")
    for key, entry in evidence["states"]["loading"].items():
        expect_equal(entry["card"]["loading_visible"], True, f"loading evidence {key}")
    for key, entry in evidence["states"]["error"].items():
        expect_equal(entry.get("state"), "error", f"error evidence {key} pre-retry state")
        expect_equal(entry["card"].get("error_visible"), True, f"error evidence {key} visible error")
        expect_equal(entry["card"].get("native_text_visible"), True, f"error evidence {key} retained preview")
        expect_equal(entry["card"].get("retry_visible"), True, f"error evidence {key} Retry recovery control")
        expect_equal(entry["card"].get("decision_text_clipped"), [], f"error evidence {key} clipped decision text")
        expect_equal(entry.get("preserved_task_context"), {"selected_record": True, "active_tab": "CAE Cards"}, f"error evidence {key} retained task context")
        recovery = entry.get("recovery")
        if not isinstance(recovery, dict):
            fail(f"error evidence {key} missing separate retry recovery record")
        expect_equal(recovery.get("state"), "normal", f"error evidence {key} recovery state")
        viewport = entry["viewport"]
        recovery_image = IMAGE_DIR / f"materials-card-state-error-recovery-{key}.png"
        validate_persisted_screenshot(recovery, recovery_image, viewport, f"error evidence {key} recovery")
        expect_equal(recovery.get("retry_announced"), True, f"error evidence {key} recovery announcement")
        expect_equal(recovery.get("card", {}).get("error_visible"), False, f"error evidence {key} recovery error visibility")
        expect_equal(recovery.get("card", {}).get("native_text_visible"), True, f"error evidence {key} recovery preview")
        expect_equal(recovery.get("overflow"), {"document_horizontal": 0, "document_vertical": 0, "body_horizontal": 0, "body_vertical": 0}, f"error evidence {key} recovery overflow")
        expect_equal(recovery.get("preserved_task_context"), {"selected_record": True, "active_tab": "CAE Cards"}, f"error evidence {key} recovery task context")
        validate_visual_acceptance_evidence(recovery, f"error evidence {key} recovery")


def main() -> None:
    args = parse_args()
    staging = read_json(STAGING_INDEX)
    if staging.get("schema_version") != 1 or staging.get("family") != "MAT-CARD":
        fail("unexpected MAT-CARD staging schema/family")
    entries = {entry.get("id"): entry for entry in staging.get("references", [])}
    selected = sorted(TARGETS) if args.all_packet_targets else [args.target]
    missing = sorted(set(selected) - set(entries))
    if missing:
        fail(f"staging index missing targets: {missing}")
    validate_sources(staging)
    measurements: dict[str, dict[str, Any]] = {}
    for target in selected:
        entry = entries[target]
        config = TARGETS[target]
        measurement_path = ROOT / entry["measurements"]
        measurement = read_json(measurement_path)
        measurements[target] = measurement
        validate_common(entry, config, measurement)
        validate_state(measurement, config["state"], target)
        if args.expect_main_agent_status:
            expect_equal(entry.get("main_agent_evaluation", {}).get("status"), args.expect_main_agent_status, f"{target} main-agent status")
    if args.all_packet_targets:
        validate_responsive("materials-card-approximation-blocked-1440x900", "approximation", measurements["materials-card-approximation-blocked-1440x900"])
        validate_responsive("materials-card-unsupported-blocked-1440x900", "unsupported", measurements["materials-card-unsupported-blocked-1440x900"])
        validate_state_evidence()
    print(f"PASS issue-167 MAT-CARD WAVE-02: {len(selected)} target(s) validated; responsive and state evidence={'yes' if args.all_packet_targets else 'not requested'}")


if __name__ == "__main__":
    main()

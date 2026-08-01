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

CANONICAL_TARGETS = {
    "materials-card-preview-normal-1366x768": {"state": "normal", "width": 1366, "height": 768},
    "materials-card-preview-normal-1440x900": {"state": "normal", "width": 1440, "height": 900},
    "materials-card-preview-normal-1920x1080": {"state": "normal", "width": 1920, "height": 1080},
    "materials-card-approximation-blocked-1440x900": {"state": "approximation", "width": 1440, "height": 900},
    "materials-card-unsupported-blocked-1440x900": {"state": "unsupported", "width": 1440, "height": 900},
}

WIDE_SUPPORT_TARGETS = {
    "materials-card-preview-normal-2560x1440": {"state": "normal", "width": 2560, "height": 1440},
    "materials-card-preview-normal-3840x2160": {"state": "normal", "width": 3840, "height": 2160},
}

TARGETS = {**CANONICAL_TARGETS, **WIDE_SUPPORT_TARGETS}

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

MAPPING_CONSEQUENCES = {"Exact", "Converted", "Review required", "Reviewed", "Not supported"}
MAPPING_EXPECTATIONS = {
    "density": ("Density", "7 800 kg/m³ → 7.8000E+03 kg/m³", "Exact"),
    "isotropic-elasticity": ("Isotropic elasticity", "210 GPa, \N{GREEK SMALL LETTER NU} 0.30 → *ELASTIC", "Exact"),
    "initial-yield": ("Initial yield", "450 MPa at εp = 0 → first *PLASTIC row", "Converted"),
    "hardening-response": ("Hardening response", "5 points → native *PLASTIC rows", "Converted"),
    "post-necking-extension": ("Post-necking extension", "Bounded extension → target behavior", "Review required"),
    "damage-initiation-gissmo": ("Damage initiation · GISSMO", "No governed target representation", "Not supported"),
}


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


def validate_light_native_preview(card: dict[str, Any], label: str) -> None:
    expected_surface = {
        "preview_surface": "rgb(247, 249, 250)",
        "preview_ink": "rgb(37, 52, 61)",
        "preview_border": "rgb(170, 181, 187)",
    }
    for key, expected in expected_surface.items():
        expect_equal(card.get(key), expected, f"{label} light native preview {key}")
    rail_visible = card.get("preview_scroll_rail_visible")
    scroll_range = card.get("preview_scroll_range", 0)
    if scroll_range <= 0 and rail_visible:
        fail(f"{label} non-overflow native preview exposes a false custom scroll rail")
    if rail_visible:
        expect_equal(card.get("preview_scroll_track"), "rgb(220, 231, 236)", f"{label} light native rail track")
        expect_equal(card.get("preview_scroll_divider"), "rgb(182, 201, 210)", f"{label} light native rail divider")
        expect_equal(card.get("preview_scroll_thumb"), "rgb(78, 129, 149)", f"{label} light native rail thumb")


def validate_sources(staging: dict[str, Any]) -> None:
    expected_sources = {
        "html": "docs/00-research/ux-service-reference/materials-card-preview-normal.html",
        "css": "docs/00-research/ux-service-reference/materials-card-preview.css",
        "javascript": "docs/00-research/ux-service-reference/materials-card-preview.js",
    }
    staged_entries = [*staging.get("references", []), *staging.get("wide_support", [])]
    for key, expected in expected_sources.items():
        paths = {entry.get(key) for entry in staged_entries}
        expect_equal(paths, {expected}, f"source {key}")
    source_html = ROOT / "docs/00-research/ux-service-reference/materials-card-preview-normal.html"
    source_css = ROOT / "docs/00-research/ux-service-reference/materials-card-preview.css"
    source_js = ROOT / "docs/00-research/ux-service-reference/materials-card-preview.js"
    for path in (source_html, source_css, source_js):
        if not path.is_file() or not path.read_text(encoding="utf-8").strip():
            fail(f"empty MAT-CARD source: {path}")
    html = source_html.read_text(encoding="utf-8")
    for marker in ("data-region=\"navigator\"", "data-region=\"card-panel\"", "Native preview", "Delivery properties", "Mapping details", "Technical mapping details", "CAE Cards"):
        if marker not in html:
            fail(f"MAT-CARD HTML missing marker: {marker}")
    if "Mapping summary" in html or "Advanced mapping evidence" in html:
        fail("MAT-CARD HTML retains the superseded mapping grammar label")
    css_text = source_css.read_text(encoding="utf-8")
    if "grid-template-columns: minmax(0, 1fr) auto" not in css_text:
        fail("MAT-CARD mapping rows do not use the shared minmax(0, 1fr) auto grammar")
    if "padding: 0; border: 0; border-radius: 0" not in css_text:
        fail("MAT-CARD mapping consequences retain badge silhouette styling")


def validate_mapping_grammar(card: dict[str, Any], label: str, state: str) -> None:
    expect_equal(card.get("mapping_title"), "Mapping details", f"{label} mapping title")
    expect_equal(card.get("mapping_disclosure_title"), "Technical mapping details", f"{label} technical mapping disclosure")
    mode = state if state in {"normal", "approximation", "unsupported"} else "normal"
    expected_keys = {
        "normal": {"density", "isotropic-elasticity", "initial-yield", "hardening-response"},
        "approximation": {"density", "post-necking-extension"},
        "unsupported": {"density", "damage-initiation-gissmo"},
    }[mode]
    details = card.get("mapping_row_details")
    if not isinstance(details, list):
        fail(f"{label} missing structured mapping row evidence")
    expect_equal({row.get("key") for row in details}, expected_keys, f"{label} visible mapping row keys")
    expect_equal(card.get("mapping_visible_count"), len(expected_keys), f"{label} visible mapping row count")
    for row in details:
        key = row.get("key")
        if key not in MAPPING_EXPECTATIONS:
            fail(f"{label} unexpected mapping row: {row!r}")
        expected_title, expected_value, expected_consequence = MAPPING_EXPECTATIONS[key]
        if (row.get("title"), row.get("value")) != (expected_title, expected_value):
            fail(f"{label} mapping title/value mismatch: {row!r}")
        if mode == "approximation" and row.get("key") == "post-necking-extension" and row.get("consequence") == "Reviewed":
            expected_consequence = "Reviewed"
        if row.get("consequence") not in MAPPING_CONSEQUENCES or row.get("consequence") != expected_consequence:
            fail(f"{label} mapping consequence mismatch: {row!r}")
        if row.get("clipped") or row.get("overlap"):
            fail(f"{label} mapping row clipping/overlap: {row!r}")
        expect_equal(row.get("status_border_width"), "0px", f"{label} {key} consequence border")
        expect_equal(row.get("status_border_radius"), "0px", f"{label} {key} consequence radius")
        expect_equal(row.get("status_padding"), "0px", f"{label} {key} consequence padding")
        if row.get("status_text_transform") not in {"none", ""}:
            fail(f"{label} {key} consequence is not sentence case: {row!r}")


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
    validate_light_native_preview(card, target)
    validate_mapping_grammar(card, target, config["state"])
    regions = card.get("regions", {})
    delivery_width = card.get("delivery_width")
    native_width = card.get("native_width")
    if not isinstance(delivery_width, int) or not 300 <= delivery_width <= 340:
        fail(f"{target} delivery sheet width is not 300-340px: {delivery_width}")
    if not isinstance(native_width, int) or native_width <= delivery_width:
        fail(f"{target} native preview is not dominant: {native_width} / {delivery_width}")
    wide = viewport["width"] >= 1800
    if wide and config["state"] == "normal":
        if card.get("card_content_child_count") != 2:
            fail(f"{target} wide card has a third top-level pane: {card.get('card_content_child_count')}")
        expect_equal(card.get("response_plot_visible"), True, f"{target} linked response plot visibility")
        expect_equal(card.get("response_plot_rows"), 6, f"{target} linked response row count")
        expect_equal(card.get("response_plot_first_point"), {"stress": 450, "strain": 0}, f"{target} linked response first point")
        expect_equal(card.get("response_plot_x_label"), "True plastic strain [1]", f"{target} linked response x-axis")
        expect_equal(card.get("response_plot_y_label"), "True stress (MPa)", f"{target} linked response y-axis")
        series = card.get("response_plot_series")
        if not isinstance(series, list) or len(series) != 6:
            fail(f"{target} linked response series is not six exact rows: {series!r}")
        x_domain = card.get("response_plot_x_domain")
        y_domain = card.get("response_plot_y_domain")
        strains = [row.get("strain") for row in series if isinstance(row, dict)]
        stresses = [row.get("stress") for row in series if isinstance(row, dict)]
        if not (isinstance(x_domain, list) and len(x_domain) == 2 and isinstance(y_domain, list) and len(y_domain) == 2):
            fail(f"{target} linked response domains are missing: {x_domain} / {y_domain}")
        if not (all(isinstance(value, (int, float)) for value in strains + stresses) and x_domain[0] < min(strains) and x_domain[1] > max(strains) and y_domain[0] < min(stresses) and y_domain[1] > max(stresses)):
            fail(f"{target} linked response domains lack data-relative headroom: {x_domain} / {y_domain}")
        aspect = card.get("response_plot_svg_aspect")
        if not isinstance(aspect, dict) or aspect.get("mismatch", 1) > 0.005:
            fail(f"{target} linked response SVG aspect mismatch: {aspect}")
        if card.get("response_plot_preserve_aspect_ratio", "").lower() == "none":
            fail(f"{target} linked response SVG uses preserveAspectRatio=none")
        for key in ("response_plot_tick_font_px", "response_plot_title_font_px"):
            value = card.get(key)
            if not isinstance(value, (int, float)) or not 10 <= value <= 12.5:
                fail(f"{target} linked response {key} outside 10-12.5px: {value!r}")
        expect_equal(card.get("response_plot_line_has_frame_headroom"), True, f"{target} linked response frame headroom")
        native_ratio_max = {1920: 0.42, 2560: 0.34, 3840: 0.24}[viewport["width"]]
        if card.get("native_surface_ratio", 1) > native_ratio_max:
            fail(f"{target} dark native surface exceeds {native_ratio_max:.0%} of evidence height: {card.get('native_surface_ratio')}")
        if card.get("preview_rendered_height", 441) > 440:
            fail(f"{target} dark native surface exceeds the 440px content cap: {card.get('preview_rendered_height')}")
        if card.get("response_plot_ratio", 0) < 0.40:
            fail(f"{target} linked response plot is below 40% of evidence height: {card.get('response_plot_ratio')}")
        if not card.get("preview_scroll_rail_visible") or card.get("preview_scroll_range", 0) <= 0 or card.get("preview_scroll_gutter_width", 0) < 6 or card.get("preview_scroll_thumb_ratio", 0) <= 0 or card.get("preview_scroll_text_clearance", 0) <= 0:
            fail(f"{target} native preview lacks a visible, reserved local-scroll rail")
        expect_equal(measurement.get("interactions", {}).get("native_scroll_wheel"), True, f"{target} native preview wheel scrolling")
    elif not wide:
        expect_equal(card.get("response_plot_visible"), False, f"{target} sub-2200 linked response visibility")
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
        bounded_expanded_preview = card.get("response_plot_visible") or ("approximation" in target and "1920x1080" in target)
        if not isinstance(available_height, int) or not isinstance(rendered_height, int):
            fail(f"{target} native preview is missing height evidence: {rendered_height} / {available_height}")
        if bounded_expanded_preview:
            if rendered_height > 440:
                fail(f"{target} expanded native preview exceeds the 440px content cap: {rendered_height}")
        else:
            if rendered_height < available_height - 1:
                fail(f"{target} native preview does not use available pane height: {rendered_height} / {available_height}")
            expect_equal(card.get("preview_fills_available_height"), True, f"{target} native preview fills available height")
    expect_equal(card.get("delivery_summary_present"), False, f"{target} redundant delivery header status")
    expect_equal(card.get("decision_text_clipped"), [], f"{target} clipped decision text")


def validate_state(measurement: dict[str, Any], state: str, target: str) -> None:
    card = measurement.get("card", {})
    validate_mapping_grammar(card, target, state)
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
        if not any("post-necking extension" in row.casefold() for row in card.get("mapping_rows", [])):
            fail(f"{target} named approximation missing")
        expect_equal(card.get("download", {}).get("text"), "Download .rad", f"{target} approximation command label")
        expect_equal(card.get("download", {}).get("disabled"), True, f"{target} approximation command blocked")
        expect_equal(card.get("download", {}).get("primary"), True, f"{target} approximation primary command treatment")
        expect_equal(measurement.get("interactions", {}).get("state_command"), True, f"{target} acknowledgement interaction")
        expect_equal(measurement.get("interactions", {}).get("mapping_acknowledgement"), True, f"{target} in-place acknowledgement consequence")
    elif state == "unsupported":
        expect_equal(card.get("native_text_visible"), False, f"{target} unsupported fake preview")
        expect_equal(card.get("unavailable_visible"), True, f"{target} unavailable explanation")
        expect_equal(card.get("download"), {"text": "Download blocked", "disabled": True, "primary": False}, f"{target} unsupported command")
        expect_equal(card.get("open_modeling_visible"), True, f"{target} Open Modeling recovery")
        expect_equal(card.get("back_to_cards_visible"), True, f"{target} Back to CAE Cards recovery")
        if not any("damage initiation" in row.casefold() for row in card.get("mapping_rows", [])):
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
            validate_light_native_preview(entry.get("card", {}), f"{state}/{key}")
            validate_preview_height_and_decision(entry.get("card", {}), f"{state}/{key}")
    for key, entry in evidence["states"]["long"].items():
        if entry["card"]["preview_scroll_height"] <= entry["card"]["preview_client_height"]:
            fail(f"long evidence {key} is not independently scrollable")
        if not entry["card"].get("preview_scroll_rail_visible") or entry["card"].get("preview_scroll_gutter_width", 0) < 6 or entry["card"].get("preview_scroll_text_clearance", 0) <= 0:
            fail(f"long evidence {key} lacks a visible reserved local-scroll rail")
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
        validate_light_native_preview(recovery.get("card", {}), f"error evidence {key} recovery")
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
    entries = {entry.get("id"): entry for entry in [*staging.get("references", []), *staging.get("wide_support", [])]}
    selected = sorted(TARGETS) if args.all_packet_targets else [args.target]
    if args.all_packet_targets:
        expect_equal({entry.get("id") for entry in staging.get("references", [])}, set(CANONICAL_TARGETS), "canonical MAT-CARD staging targets")
        expect_equal({entry.get("id") for entry in staging.get("wide_support", [])}, set(WIDE_SUPPORT_TARGETS), "wide MAT-CARD staging targets")
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

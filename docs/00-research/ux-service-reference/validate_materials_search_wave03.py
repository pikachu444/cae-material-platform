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
HTML = REFERENCE_DIR / "materials-search-exceptional.html"
CSS = REFERENCE_DIR / "materials-search-exceptional.css"
JAVASCRIPT = REFERENCE_DIR / "materials-search-exceptional.js"
STAGING_INDEX = IMAGE_DIR / "materials-search-wave03.staging.json"
STATE_EVIDENCE = IMAGE_DIR / "materials-search-wave03.state-evidence.json"

VIEWPORTS = {
    "1366x768": {"width": 1366, "height": 768, "device_scale_factor": 1},
    "1440x900": {"width": 1440, "height": 900, "device_scale_factor": 1},
    "1920x1080": {"width": 1920, "height": 1080, "device_scale_factor": 1},
}

CANONICAL = {
    "materials-search-long-1440x900": ("long", "materials-search-long-1440x900"),
    "materials-search-empty-1440x900": ("empty", "materials-search-empty-1440x900"),
}
RESPONSIVE = {
    f"materials-search-{state}-1440x900.responsive-{viewport}": (state, f"materials-search-{state}-1440x900.responsive-{viewport}")
    for state in ("long", "empty")
    for viewport in ("1366x768", "1920x1080")
}
STATE_TARGETS = {
    f"materials-search-state-{slug}-{viewport}": (state, f"materials-search-state-{slug}-{viewport}")
    for state, slug in (("search-loading", "loading"), ("tree-loading", "tree-lazy-loading"), ("query-error", "query-error"), ("tree-error", "tree-error"))
    for viewport in VIEWPORTS
}
ALL_TARGETS = {**CANONICAL, **RESPONSIVE, **STATE_TARGETS}

LEGACY_SELECTORS = (
    "page-stack",
    "page-heading",
    "content-card",
    "module-material-card",
    "hero-actions",
    "eyebrow",
    "status-badge",
    "count-chip",
)

FROZEN_APPROVED_EXCEPTIONAL_HASHES = {
    "materials-search-long-1440x900.png": "43f146e60baf2d933265d952e22fce5cd0c1e2ca0e9145eea0e72a9677da2484",
    "materials-search-long-1440x900.responsive-1366x768.png": "6e9b91ff80698c08d591b514bd491a682f618c4595ea7d9b11cb0f70bd66c504",
    "materials-search-long-1440x900.responsive-1920x1080.png": "a8b387bf1dbc6327da02d494699d19022f89ac6e10c57e0b9922cae6fee96bb4",
    "materials-search-empty-1440x900.png": "d9e4fed1d8c17ca86b7c14dfe57909591b44ff8ec300286bb49f3a940fb5e1b1",
    "materials-search-empty-1440x900.responsive-1366x768.png": "2bb1798ab9a4d7438b4e2e274393e49cfe61b1329c2bc6e9dbe9a49624049025",
    "materials-search-empty-1440x900.responsive-1920x1080.png": "9e1caed30c77fd8141fd64fe1a4b6dc3f2fa540841d791513a16c74753e71493",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate MAT-EXP WAVE-03 exceptional service-reference evidence.")
    parser.add_argument("--target", choices=sorted(CANONICAL), help="Validate one canonical approval target.")
    parser.add_argument("--all-packet-targets", action="store_true", help="Validate both approval targets, responsive evidence and state evidence.")
    parser.add_argument("--expect-main-agent-status", default="pending", choices=("pending", "evaluated"), help="Required lifecycle status in every measurement.")
    args = parser.parse_args()
    if not args.target and not args.all_packet_targets:
        parser.error("provide --target or --all-packet-targets")
    if args.target and args.all_packet_targets:
        parser.error("--target and --all-packet-targets are mutually exclusive")
    return args


def relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def png_dimensions(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise AssertionError(f"not a PNG: {path}")
    return struct.unpack(">II", data[16:24])


def load_measurement(target: str) -> dict[str, Any]:
    path = IMAGE_DIR / f"{target}.measurements.json"
    if not path.is_file():
        raise AssertionError(f"missing measurement: {relative(path)}")
    return json.loads(path.read_text(encoding="utf-8"))


def validate_frozen_approved_exceptional() -> None:
    expected_sizes = {"1366x768": (1366, 768), "1440x900": (1440, 900), "1920x1080": (1920, 1080)}
    for name, expected_hash in FROZEN_APPROVED_EXCEPTIONAL_HASHES.items():
        path = IMAGE_DIR / name
        if not path.is_file() or sha256(path) != expected_hash:
            raise AssertionError(f"frozen approved exceptional image changed: {relative(path)}")
        token = name.rsplit("-", 1)[-1].removesuffix(".png")
        if png_dimensions(path) != expected_sizes[token]:
            raise AssertionError(f"frozen approved exceptional dimensions changed: {relative(path)}")


def validate_source() -> None:
    for path in (HTML, CSS, JAVASCRIPT):
        if not path.is_file() or path.stat().st_size == 0:
            raise AssertionError(f"exceptional source missing or empty: {relative(path)}")
    html = HTML.read_text(encoding="utf-8")
    css = CSS.read_text(encoding="utf-8")
    javascript = JAVASCRIPT.read_text(encoding="utf-8")
    required_html = ("id=\"material-query\"", "id=\"material-tree\"", "id=\"results-body\"", "id=\"clear-search\"", "id=\"selected-context-title\"", "data-region=\"navigator-divider\"", "data-region=\"context-divider\"", "id=\"tree-scrollbar-y\"", "id=\"tree-scrollbar-x\"", "id=\"results-scrollbar-y\"", "role=\"scrollbar\"")
    for token in required_html:
        if token not in html:
            raise AssertionError(f"exceptional HTML missing required contract: {token}")
    if "@media (max-width: 1399px)" not in css or "--navigator-width: 244px" not in css or "--context-width: 280px" not in css:
        raise AssertionError("exceptional CSS does not preserve the 1366 selected-context topology")
    if ".app-scrollbar-thumb" not in css or ".tree-kind[data-kind=\"Record\"]" not in css or "padding-left: 15px" not in css:
        raise AssertionError("exceptional CSS is missing the compact tree and discoverable-scroll correction")
    if "bindScrollbar" not in javascript or "setPointerCapture" not in javascript or "ctrlKey" not in javascript or "ArrowDown" not in javascript or "retry-query" not in javascript or "clearSearch" not in javascript:
        raise AssertionError("exceptional JavaScript is missing required interaction contracts")


def validate_measurement(target: str, expected_state: str, measurement: dict[str, Any], expect_main_agent_status: str) -> None:
    if measurement.get("target") != target:
        raise AssertionError(f"{target}: measurement target mismatch")
    if measurement.get("family") != "MAT-EXP":
        raise AssertionError(f"{target}: family mismatch")
    if measurement.get("state") != expected_state:
        raise AssertionError(f"{target}: state mismatch")
    viewport = measurement.get("viewport")
    if viewport not in VIEWPORTS.values():
        raise AssertionError(f"{target}: invalid viewport {viewport}")
    image_path = ROOT / measurement.get("image", "")
    if not image_path.is_file():
        raise AssertionError(f"{target}: missing image {measurement.get('image')}")
    expected_dimensions = (viewport["width"], viewport["height"])
    if png_dimensions(image_path) != expected_dimensions or measurement.get("image_dimensions") != {"width": expected_dimensions[0], "height": expected_dimensions[1]}:
        raise AssertionError(f"{target}: image dimensions do not match viewport")
    if measurement.get("image_sha256") != sha256(image_path):
        raise AssertionError(f"{target}: image hash mismatch")
    for key in ("html", "css", "javascript"):
        if measurement.get("source", {}).get(key) != relative((HTML, CSS, JAVASCRIPT)[("html", "css", "javascript").index(key)]):
            raise AssertionError(f"{target}: source {key} is not the exceptional source")
    if measurement.get("status") != "pending":
        raise AssertionError(f"{target}: status must remain pending")
    if measurement.get("main_agent_evaluation", {}).get("status") != expect_main_agent_status:
        raise AssertionError(f"{target}: main-agent lifecycle status mismatch")
    if measurement.get("product_owner_approval", {}).get("status") != "absent":
        raise AssertionError(f"{target}: product-owner approval must remain absent")
    if any(value != 0 for value in measurement.get("overflow", {}).values()):
        raise AssertionError(f"{target}: page overflow {measurement.get('overflow')}")
    tree = measurement.get("tree", {})
    controls = tree.get("scroll_controls", {})
    vertical_control = controls.get("vertical", {})
    horizontal_control = controls.get("horizontal", {})
    if tree.get("vertical_overflow", 0) <= 0 or tree.get("overflow_y") not in ("auto", "scroll") or not tree.get("visible_scrollbar_indicator") or tree.get("native_scrollbar_visible") or tree.get("scrollbar_reservation_px", 0) < 12 or not tree.get("custom_scrollbar_indicator_visible") or not tree.get("labels_have_title") or not tree.get("labels_are_concise_identities"):
        raise AssertionError(f"{target}: tree scroll/identity contract failed")
    if not vertical_control.get("visible") or vertical_control.get("orientation") != "vertical" or vertical_control.get("aria_controls") != "tree-scroll" or vertical_control.get("aria_max", 0) <= 0 or vertical_control.get("thumb", {}).get("height", 0) < 36:
        raise AssertionError(f"{target}: visible vertical tree scrollbar evidence failed {vertical_control}")
    if tree.get("horizontal_overflow", 0) <= 0 or not horizontal_control.get("visible") or horizontal_control.get("orientation") != "horizontal" or horizontal_control.get("aria_controls") != "tree-scroll" or horizontal_control.get("aria_max", 0) <= 0 or horizontal_control.get("thumb", {}).get("width", 0) < 36:
        raise AssertionError(f"{target}: visible horizontal tree scrollbar evidence failed {horizontal_control}")
    if not controls.get("rails_outside_text") or not controls.get("distinct_track_thumb"):
        raise AssertionError(f"{target}: tree rails cover text or lack perceptual contrast {controls}")
    if not 24 <= tree.get("row_height_range", {}).get("min", 0) <= tree.get("row_height_range", {}).get("max", 0) <= 26 or not 8 <= tree.get("indentation_increment_px", 0) <= 10:
        raise AssertionError(f"{target}: tree density contract failed")
    identities = tree.get("representative_identities", [])
    if {identity.get("kind") for identity in identities} != {"Database", "Profile", "Table", "Folder", "Record"} or any(identity.get("full_text") != identity.get("title") or identity.get("accessible_type") != identity.get("kind") or identity.get("glyph_title") != identity.get("kind") or identity.get("visible_text_box_width", 0) <= 0 for identity in identities):
        raise AssertionError(f"{target}: tree compact identity semantics failed")
    if expected_state != "empty" and not tree.get("selected_without_type_prefix"):
        raise AssertionError(f"{target}: selected tree row has a visible type-prefix tax")
    if measurement.get("sticky_header") is not True:
        raise AssertionError(f"{target}: result table header is not sticky")
    if measurement.get("result", {}).get("table_headers") != ["Compare", "Material / grade", "Family", "Description", "Status"]:
        raise AssertionError(f"{target}: result table headers changed")
    if measurement.get("typography", {}).get("body_px") != 13 or not 12 <= measurement.get("typography", {}).get("tree_row_px", 0) <= 13:
        raise AssertionError(f"{target}: typography density outside contract")
    if any(measurement.get("legacy_selector_report", {}).get(selector) != 0 for selector in LEGACY_SELECTORS):
        raise AssertionError(f"{target}: legacy selector is present")
    if not all(measurement.get("interactions", {}).values()):
        raise AssertionError(f"{target}: interaction evidence failed {measurement.get('interactions')}")
    local_scroll = measurement.get("local_scroll", {})
    tree_scroll = local_scroll.get("tree", {})
    if not tree_scroll.get("overflowing") or not tree_scroll.get("wheel_moved") or not tree_scroll.get("page_down_moved") or not tree_scroll.get("document_unchanged") or not tree_scroll.get("horizontal_overflowing") or not tree_scroll.get("horizontal_keyboard_moved") or not tree_scroll.get("vertical_scrollbar_keyboard_moved") or not tree_scroll.get("vertical_scrollbar_pointer_moved") or not tree_scroll.get("horizontal_scrollbar_keyboard_moved"):
        raise AssertionError(f"{target}: tree wheel/PageDown local scroll evidence failed")
    regions = measurement.get("regions", {})
    for region in ("application_bar", "command_bar", "search_band", "workspace", "navigator", "navigator_divider", "results", "context_divider", "selected_context", "status_bar"):
        if not regions.get(region):
            raise AssertionError(f"{target}: missing region {region}")
    if regions["navigator_divider"]["width"] != 5 or regions["context_divider"]["width"] != 5:
        raise AssertionError(f"{target}: splitter hit widths changed")
    result = measurement.get("result", {})
    if expected_state == "long":
        if result.get("rendered_rows") != 50 or result.get("selected_rows") != 1 or result.get("count_text") != "1\u201350 of 126 matches" or not result.get("result_scroll", {}).get("independent_vertical_scroll"):
            raise AssertionError(f"{target}: long result contract failed")
        if not measurement.get("selected_context", {}).get("visible") or measurement.get("selected_context", {}).get("no_material_selected"):
            raise AssertionError(f"{target}: long selected context missing")
        result_scroll = result.get("result_scroll", {})
        result_control = result_scroll.get("scroll_control", {})
        if result_scroll.get("vertical_overflow", 0) <= 0 or result_scroll.get("overflow_y") not in ("auto", "scroll") or result_scroll.get("native_scrollbar_visible") or not result_scroll.get("custom_scrollbar_indicator_visible") or not result_control.get("visible") or result_control.get("aria_controls") != "results-scroll" or result_control.get("aria_max", 0) <= 0 or result_control.get("thumb", {}).get("height", 0) < 36 or not result_control.get("outside_text"):
            raise AssertionError(f"{target}: long result scrollbar contract failed")
        local_result = local_scroll.get("result", {})
        if not local_result.get("overflowing") or not local_result.get("wheel_moved") or not local_result.get("page_down_moved") or not local_result.get("document_unchanged") or not local_result.get("vertical_scrollbar_keyboard_moved") or not local_result.get("vertical_scrollbar_pointer_moved"):
            raise AssertionError(f"{target}: long result wheel/PageDown local scroll evidence failed")
    elif expected_state == "empty":
        if result.get("rendered_rows") != 0 or result.get("selected_rows") != 0 or measurement.get("tree", {}).get("selected_rows") != 0 or result.get("count_text") != "0 matches" or not result.get("empty_visible") or not result.get("clear_search_visible"):
            raise AssertionError(f"{target}: empty result contract failed")
        if not measurement.get("selected_context", {}).get("no_material_selected") or measurement.get("selected_context", {}).get("open_datasheet_visible"):
            raise AssertionError(f"{target}: empty context is stale")
        if result.get("visible_filled_primary_actions") != ["Find"]:
            raise AssertionError(f"{target}: empty state must expose exactly one filled task-primary action")
        if result.get("result_scroll", {}).get("vertical_overflow") != 0 or result.get("result_scroll", {}).get("native_scrollbar_visible") or result.get("result_scroll", {}).get("custom_scrollbar_indicator_visible") or result.get("result_scroll", {}).get("scroll_control", {}).get("visible") or local_scroll.get("result", {}).get("overflowing"):
            raise AssertionError(f"{target}: empty state presents a fake result scrollbar")
    else:
        if result.get("rendered_rows") != 6 or result.get("selected_rows") != 1 or measurement.get("tree", {}).get("selected_rows") != 1 or not measurement.get("selected_context", {}).get("visible"):
            raise AssertionError(f"{target}: retained-result state lost query selection")
        notices = measurement.get("state_notices", {})
        if expected_state == "search-loading" and (not notices.get("results-notice", {}).get("visible") or "retained" not in notices.get("results-notice", {}).get("text", "")):
            raise AssertionError(f"{target}: search refresh notice does not state retention")
        if expected_state == "tree-loading" and (not notices.get("tree-notice", {}).get("visible") or "retained" not in notices.get("tree-notice", {}).get("text", "")):
            raise AssertionError(f"{target}: tree lazy-loading notice does not state retention")
        if expected_state == "query-error" and (not notices.get("results-notice", {}).get("visible") or notices.get("results-notice", {}).get("buttons") != ["Retry"]):
            raise AssertionError(f"{target}: query error recovery is incomplete")
        if expected_state == "tree-error" and (not notices.get("tree-notice", {}).get("visible") or notices.get("tree-notice", {}).get("buttons") != ["Retry"]):
            raise AssertionError(f"{target}: tree error recovery is incomplete")


def validate_splitter_ranges(measurement: dict[str, Any]) -> None:
    width = measurement["viewport"]["width"]
    navigator_max = 360 if width >= 1700 else 340
    context_max = 480 if width >= 1700 else 420 if width >= 1400 else 376
    for label, snapshot in measurement.get("splitter_evidence", {}).items():
        widths = snapshot["widths"]
        aria = snapshot["aria"]
        if widths["results"] < 720 or aria["navigator"]["minimum"] != 200 or aria["context"]["minimum"] != 260 or aria["navigator"]["maximum"] != navigator_max or aria["context"]["maximum"] != context_max:
            raise AssertionError(f"{measurement['target']}:{label}: invalid splitter range")
        if aria["navigator"]["now"] != widths["navigator"] or aria["context"]["now"] != widths["context"] or snapshot["divider_visual_widths"] != [1, 1]:
            raise AssertionError(f"{measurement['target']}:{label}: splitter visible/ARIA mismatch")
        if any(value != 0 for value in snapshot["overflow"].values()):
            raise AssertionError(f"{measurement['target']}:{label}: overflow")
        if snapshot.get("tree_scroller", {}).get("vertical_overflow", 0) <= 0 or not snapshot.get("tree_scroller", {}).get("custom_vertical_visible"):
            raise AssertionError(f"{measurement['target']}:{label}: tree scroll contract changed")


def validate_all(expect_main_agent_status: str) -> None:
    if not STAGING_INDEX.is_file() or not STATE_EVIDENCE.is_file():
        raise AssertionError("WAVE-03 staging/state-evidence index is missing")
    staging = json.loads(STAGING_INDEX.read_text(encoding="utf-8"))
    if staging.get("family") != "MAT-EXP" or staging.get("state_evidence") != relative(STATE_EVIDENCE):
        raise AssertionError("staging index family/state-evidence pointer is invalid")
    for target, (state, _) in ALL_TARGETS.items():
        measurement = load_measurement(target)
        validate_measurement(target, state, measurement, expect_main_agent_status)
        validate_splitter_ranges(measurement)
    references = {entry.get("id") for entry in staging.get("references", [])}
    if references != set(CANONICAL):
        raise AssertionError(f"staging canonical references mismatch: {references}")
    state_doc = json.loads(STATE_EVIDENCE.read_text(encoding="utf-8"))
    if state_doc.get("family") != "MAT-EXP" or len(state_doc.get("loading-error-evidence", [])) != len(STATE_TARGETS):
        raise AssertionError("state evidence index is incomplete")


def main() -> None:
    args = parse_args()
    validate_frozen_approved_exceptional()
    validate_source()
    if args.all_packet_targets:
        validate_all(args.expect_main_agent_status)
    else:
        target = args.target
        state = CANONICAL[target][0]
        measurement = load_measurement(target)
        validate_measurement(target, state, measurement, args.expect_main_agent_status)
        validate_splitter_ranges(measurement)
    print("PASS MAT-EXP WAVE-03")
    if args.all_packet_targets:
        print(f"validated targets: {len(ALL_TARGETS)}")
    else:
        print(f"validated target: {args.target}")


if __name__ == "__main__":
    main()

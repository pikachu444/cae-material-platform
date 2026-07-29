from __future__ import annotations

# ruff: noqa: E501
import argparse
import hashlib
import json
import re
import struct
import sys
from pathlib import Path
from typing import Any

from playwright.sync_api import Browser, sync_playwright

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
EVIDENCE_DIR = ROOT / "docs/17-evidence/images/issue-167-service-reference"
STAGING_PATH = ROOT / "docs/00-research/ux-service-reference/administration-schema-core-wave05.staging.json"
sys.path.insert(0, str(HERE))
from capture_administration_schema_core_wave05 import (  # noqa: E402, I001
    STATE_EVIDENCE,
    TARGETS,
    VIEWPORTS,
    dom_snapshot,
    open_page,
)


ATTRIBUTE_STATE_CONTRACTS = {
    "attribute-draft": {
        "id": "density",
        "name": "Density",
        "value_type": "Number",
        "entry_guidance": "Enter the measured mass density at the selected test condition.",
        "conditional": {
            "hasQuantity": True,
            "hasStandardUnit": True,
            "hasMinMax": True,
            "hasAllowedChoices": False,
            "hasRelatedTable": False,
            "hasTextLimits": False,
        },
    },
    "attribute-discrete": {
        "id": "material-condition",
        "name": "Material condition",
        "value_type": "Discrete choice",
        "entry_guidance": "Choose the controlled material condition recorded for this material.",
        "conditional": {
            "hasQuantity": False,
            "hasStandardUnit": False,
            "hasMinMax": False,
            "hasAllowedChoices": True,
            "hasRelatedTable": False,
            "hasTextLimits": False,
        },
    },
    "attribute-reference": {
        "id": "source-reference",
        "name": "Source reference",
        "value_type": "Record reference",
        "entry_guidance": "Link the Source references Record that supports this entered value.",
        "conditional": {
            "hasQuantity": False,
            "hasStandardUnit": False,
            "hasMinMax": False,
            "hasAllowedChoices": False,
            "hasRelatedTable": True,
            "hasTextLimits": False,
        },
    },
    "attribute-text": {
        "id": "test-method",
        "name": "Test method",
        "value_type": "Text",
        "entry_guidance": "Enter the method identifier used by the test engineer.",
        "conditional": {
            "hasQuantity": False,
            "hasStandardUnit": False,
            "hasMinMax": False,
            "hasAllowedChoices": False,
            "hasRelatedTable": False,
            "hasTextLimits": True,
        },
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate the WAVE-05 ADM-SCHEMA-CORE static Administration service-reference bundle.")
    parser.add_argument("--target", choices=sorted(TARGETS), help="Validate one approval target.")
    parser.add_argument("--all-packet-targets", action="store_true", help="Validate all eleven approval targets and evidence-only states.")
    parser.add_argument("--expect-main-agent-status", choices=("pending", "accepted"), required=True, help="Expected lifecycle status in the writer staging file.")
    return parser.parse_args()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_attribute_state_semantics(snapshot: dict[str, Any], state: str, target: str) -> None:
    contract = ATTRIBUTE_STATE_CONTRACTS.get(state)
    if contract is None:
        return
    fields = {field["name"]: field["value"] for field in snapshot["fields"]}
    selected = snapshot["selectedRow"]
    require(selected and selected["id"] == contract["id"] and selected["name"] == contract["name"], f"selected Attribute drifted for {target}: {selected}")
    require(snapshot["editorTitle"] == f"Edit {contract['name']}", f"Attribute editor title drifted for {target}: {snapshot['editorTitle']}")
    require(fields.get("attributeName") == contract["name"], f"Attribute name drifted for {target}: {fields.get('attributeName')}")
    require(fields.get("attributeReference") == contract["name"], f"Attribute reference drifted for {target}: {fields.get('attributeReference')}")
    require(fields.get("attributeType") == contract["value_type"], f"Attribute value type drifted for {target}: {fields.get('attributeType')}")
    require(fields.get("entryGuidance") == contract["entry_guidance"], f"Attribute entry guidance drifted for {target}: {fields.get('entryGuidance')}")
    require(snapshot["conditional"] == contract["conditional"], f"Attribute conditional fields drifted for {target}: {snapshot['conditional']}")


def validate_long_attribute_row_containment(snapshot: dict[str, Any], target: str) -> None:
    if snapshot["state"] != "attribute-long-invalid":
        return
    selected = snapshot["selectedRow"]
    require(selected and selected["id"] == "material-condition", f"long Attribute selection drifted for {target}: {selected}")
    cells = selected["cells"]
    name = cells["name"]
    definition = cells["definition"]
    revision = cells["revision"]
    primary_name = cells["primaryName"]
    require(name["x"] + name["width"] <= definition["x"] + 0.5, f"long Attribute name overlaps Definition for {target}: {cells}")
    require(definition["x"] + definition["width"] <= revision["x"] + 0.5, f"long Attribute Definition overlaps Rev for {target}: {cells}")
    require(primary_name["scrollWidth"] > primary_name["clientWidth"], f"long Attribute name is not ellipsized for {target}: {primary_name}")
    require(primary_name["overflow"] == "hidden" and primary_name["textOverflow"] == "ellipsis" and primary_name["whiteSpace"] == "nowrap", f"long Attribute name ellipsis contract drifted for {target}: {primary_name}")


def png_dimensions(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    require(data[:8] == b"\x89PNG\r\n\x1a\n", f"invalid PNG signature: {path}")
    return struct.unpack(">II", data[16:24])


def viewport_contract(snapshot: dict[str, Any], viewport_name: str, target: str) -> None:
    viewport = VIEWPORTS[viewport_name]
    require(snapshot["viewport"]["width"] == viewport["width"] and snapshot["viewport"]["height"] == viewport["height"], f"viewport mismatch for {target}")
    require(snapshot["viewport"]["deviceScaleFactor"] == 1, f"device scale factor is not 1 for {target}")
    require(all(value == 0 for value in snapshot["overflow"].values()), f"page overflow for {target}: {snapshot['overflow']}")
    require(snapshot["nestedInteractive"] == [], f"nested interactive controls for {target}")
    require(all(control["name"] for control in snapshot["controls"]), f"unnamed visible control for {target}")
    require(snapshot["bodyCss"]["overflowX"] == "hidden" and snapshot["bodyCss"]["rootOverflowX"] in {"visible", "hidden"}, f"horizontal overflow CSS changed for {target}")
    require(snapshot["geometry"]["workspace"] and snapshot["geometry"]["navigator"] and snapshot["geometry"]["list"] and snapshot["geometry"]["editorPane"], f"three-pane geometry missing for {target}")
    workspace = snapshot["geometry"]["workspace"]
    navigator = snapshot["geometry"]["navigator"]
    listing = snapshot["geometry"]["list"]
    editor = snapshot["geometry"]["editorPane"]
    require(abs((navigator["width"] + listing["width"] + editor["width"] + 14) - workspace["width"]) <= 2, f"pane widths do not account for splitters for {target}")
    require(editor["width"] > listing["width"] and editor["width"] > navigator["width"], f"property editor is not dominant for {target}")
    if viewport_name == "1366x768":
        require(220 <= navigator["width"] <= 232, f"navigator width outside 1366 contract for {target}: {navigator['width']}")
        require(292 <= listing["width"] <= 320, f"list width outside 1366 contract for {target}: {listing['width']}")
    elif viewport_name == "1440x900":
        require(232 <= navigator["width"] <= 248, f"navigator width outside 1440 contract for {target}: {navigator['width']}")
        require(312 <= listing["width"] <= 344, f"list width outside 1440 contract for {target}: {listing['width']}")
    else:
        require(252 <= navigator["width"] <= 272, f"navigator width outside 1920 contract for {target}: {navigator['width']}")
        require(344 <= listing["width"] <= 384, f"list width outside 1920 contract for {target}: {listing['width']}")
    require(len(snapshot["splitters"]) == 2, f"two splitters required for {target}")
    for splitter in snapshot["splitters"]:
        require(splitter["min"] <= splitter["value"] <= splitter["max"], f"splitter value outside range for {target}: {splitter}")
        require(splitter["rect"] and 5 <= splitter["rect"]["width"] <= 9, f"splitter hit area missing for {target}")
    row_heights = [row["height"] for row in snapshot["rows"]]
    require(all(24 <= height <= 30 for height in row_heights), f"object row density outside 24-26px contract for {target}: {row_heights}")
    require(snapshot["localScroll"]["list"]["overflowY"] in {"auto", "scroll"} and "stable" in snapshot["localScroll"]["list"]["scrollbarGutter"], f"list local scroll rail not reserved for {target}")
    require(snapshot["localScroll"]["editor"]["overflowY"] in {"auto", "scroll"} and "stable" in snapshot["localScroll"]["editor"]["scrollbarGutter"], f"editor local scroll rail not reserved for {target}")
    css_text = (HERE / "administration-schema-core.css").read_text(encoding="utf-8")
    require(":focus-visible" in css_text and "transition: all" not in css_text and "outline: none" not in css_text, f"focus/interaction CSS contract failed for {target}")


def validate_target(browser: Browser, target: str, staged: dict[str, Any]) -> None:
    spec = TARGETS[target]
    image = ROOT / staged["image"]
    require(image.exists(), f"missing approval image: {image}")
    require(png_dimensions(image) == (VIEWPORTS[spec["viewport"]]["width"], VIEWPORTS[spec["viewport"]]["height"]), f"wrong dimensions for {target}")
    require(sha256(image) == staged["sha256"], f"staging hash mismatch for {target}")
    page, console_errors, page_errors = open_page(browser, spec["role"], spec["state"], spec["viewport"])
    try:
        require(not console_errors and not page_errors, f"browser errors for {target}: {console_errors + page_errors}")
        snapshot = dom_snapshot(page)
        require(snapshot["role"] == spec["role"] and snapshot["state"] == spec["state"], f"role/state mismatch for {target}")
        viewport_contract(snapshot, spec["viewport"], target)
        validate_attribute_state_semantics(snapshot, spec["state"], target)
        validate_long_attribute_row_containment(snapshot, target)
        if spec["state"] == "normal":
            require(snapshot["editorMode"] == "table-readonly", f"normal editor mode changed for {target}")
            require(any(button["name"] == "Edit Table" for button in snapshot["buttons"]), f"normal Table action missing for {target}")
            require(sum(button["name"] == "Add Table" and not button["disabled"] for button in snapshot["buttons"]) == 1, f"normal Add Table command missing/duplicated for {target}")
            require(sum(button["name"] == "Save new revision" and not button["disabled"] for button in snapshot["buttons"]) == 0, f"normal state exposes save command for {target}")
        elif spec["state"] == "table-draft":
            require(snapshot["editorMode"] == "table-draft", f"Table draft editor missing for {target}")
            require(any(field["name"] == "tableReason" for field in snapshot["fields"]), f"Table change reason missing for {target}")
            require(sum(button["name"] == "Save new revision" and not button["disabled"] for button in snapshot["buttons"]) == 1, f"Table draft primary missing for {target}")
            require(not any(button["name"] in {"Duplicate", "Delete"} for button in snapshot["buttons"]), f"legacy Table command visible for {target}")
        elif spec["state"] == "attribute-draft":
            require(snapshot["editorMode"] == "attribute-draft", f"Attribute draft editor missing for {target}")
            require(snapshot["conditional"]["hasQuantity"] and snapshot["conditional"]["hasStandardUnit"] and snapshot["conditional"]["hasMinMax"], f"number conditional fields missing for {target}")
            require(not snapshot["conditional"]["hasAllowedChoices"] and not snapshot["conditional"]["hasRelatedTable"], f"non-number fields leaked into number Attribute for {target}")
            require(sum(button["name"] == "Save new revision" and not button["disabled"] for button in snapshot["buttons"]) == 1, f"Attribute draft primary missing for {target}")
        elif spec["state"] == "stale-conflict":
            require(snapshot["announcements"]["alert"], f"stale conflict alert missing for {target}")
            require(snapshot["buttons"][-3:][0]["name"] == "Reload current" if len(snapshot["buttons"]) >= 3 else False, f"stale recovery commands missing for {target}")
            recovery = [button["name"] for button in snapshot["buttons"] if button["name"] in {"Reload current", "Keep local as new revision", "Cancel"}]
            require(recovery == ["Reload current", "Keep local as new revision", "Cancel"], f"stale recovery commands changed for {target}: {recovery}")
            require(not any(button["name"] == "Save new revision" for button in snapshot["buttons"]), f"stale conflict exposes competing save for {target}")
        elif spec["state"] == "attribute-long-invalid":
            require(snapshot["announcements"]["alert"], f"long invalid summary missing for {target}")
            require(snapshot["localScroll"]["editor"]["scrollHeight"] > snapshot["localScroll"]["editor"]["clientHeight"], f"long Attribute editor does not scroll for {target}")
            require(any(field["invalid"] for field in snapshot["fields"]), f"long Attribute fields have no inline invalid state for {target}")
            require(any(button["name"] == "Save new revision" and button["disabled"] for button in snapshot["buttons"]), f"long Attribute save is not disabled for {target}")
            require("Allowed choices" in snapshot["pageText"] and "Entry guidance" in snapshot["pageText"], f"long Attribute content missing for {target}")
        print(f"PASS target {target} {spec['viewport']} sha256={staged['sha256']}")
    finally:
        page.context.close()


def validate_state(browser: Browser, state_target: str, staged: dict[str, Any]) -> list[dict[str, Any]]:
    role = STATE_EVIDENCE[state_target][0]
    state = STATE_EVIDENCE[state_target][1]
    captures = staged.get("captures", [])
    require(len(captures) == 3, f"state evidence must have three viewports: {state_target}")
    snapshots: list[dict[str, Any]] = []
    for image_rel in captures:
        image = ROOT / image_rel
        require(image.exists(), f"missing state image: {image}")
        viewport_name = next((name for name in VIEWPORTS if image.stem.endswith(name)), "")
        require(viewport_name, f"state image has unknown viewport: {image}")
        require(png_dimensions(image) == (VIEWPORTS[viewport_name]["width"], VIEWPORTS[viewport_name]["height"]), f"wrong state dimensions: {image}")
        page, console_errors, page_errors = open_page(browser, role, state, viewport_name)
        try:
            require(not console_errors and not page_errors, f"browser errors for {state_target}: {console_errors + page_errors}")
            snapshot = dom_snapshot(page)
            require(snapshot["role"] == role and snapshot["state"] == state, f"state role/state mismatch for {state_target}")
            viewport_contract(snapshot, viewport_name, state_target)
            validate_attribute_state_semantics(snapshot, state, f"{state_target}-{viewport_name}")
            validate_long_attribute_row_containment(snapshot, f"{state_target}-{viewport_name}")
            if state == "empty":
                require(len(snapshot["rows"]) == 0 and any(button["name"] == "Add Table" for button in snapshot["buttons"]), f"empty state contract failed for {state_target}")
            elif state == "catalog-loading":
                require(len(snapshot["rows"]) == 5 and any(row["selected"] for row in snapshot["rows"]), f"loading state did not retain rows/selection for {state_target}")
                require(snapshot["localScroll"]["list"]["scrollHeight"] >= snapshot["localScroll"]["list"]["clientHeight"], f"loading list geometry missing for {state_target}")
            elif state == "catalog-error":
                require(len(snapshot["rows"]) == 5 and any(row["selected"] for row in snapshot["rows"]), f"catalog error discarded selection for {state_target}")
                require(any(button["name"] == "Retry" for button in snapshot["buttons"]), f"catalog Retry missing for {state_target}")
            elif state in {"table-saving", "attribute-saving"}:
                require(any(button["name"] == "Save new revision" and button["disabled"] for button in snapshot["buttons"]), f"saving state did not block duplicate submit for {state_target}")
                require(snapshot["announcements"]["status"], f"saving status announcement missing for {state_target}")
            elif state in {"table-save-error", "attribute-save-error"}:
                require(snapshot["announcements"]["alert"], f"save error alert missing for {state_target}")
                require(any(button["name"] == "Retry save" for button in snapshot["buttons"]), f"save retry missing for {state_target}")
                require(all(field["value"] for field in snapshot["fields"] if field["name"] in {"tableName", "tableDescription", "attributeName", "entryGuidance"}), f"save error discarded draft fields for {state_target}")
            elif state == "attribute-draft":
                require(snapshot["conditional"]["hasQuantity"] and snapshot["conditional"]["hasStandardUnit"] and snapshot["conditional"]["hasMinMax"], f"number conditional evidence missing for {state_target}")
            elif state == "attribute-discrete":
                require(snapshot["conditional"]["hasAllowedChoices"] and not snapshot["conditional"]["hasQuantity"] and not snapshot["conditional"]["hasStandardUnit"], f"discrete conditional evidence incorrect for {state_target}")
            elif state == "attribute-reference":
                require(snapshot["conditional"]["hasRelatedTable"] and not snapshot["conditional"]["hasQuantity"] and not snapshot["conditional"]["hasAllowedChoices"], f"record reference conditional evidence incorrect for {state_target}")
            elif state == "attribute-text":
                require(snapshot["conditional"]["hasTextLimits"] and not snapshot["conditional"]["hasQuantity"] and not snapshot["conditional"]["hasAllowedChoices"], f"text conditional evidence incorrect for {state_target}")
            elif state == "stale-conflict":
                require(len([button for button in snapshot["buttons"] if button["name"] in {"Reload current", "Keep local as new revision", "Cancel"}]) == 3, f"stale conflict recovery incomplete for {state_target}")
            elif state == "attribute-long-invalid":
                require(snapshot["localScroll"]["editor"]["scrollHeight"] > snapshot["localScroll"]["editor"]["clientHeight"], f"long editor does not scroll for {state_target}")
                require(any(field["invalid"] for field in snapshot["fields"]), f"long editor lacks invalid fields for {state_target}")
            snapshots.append(snapshot)
        finally:
            page.context.close()
    print(f"PASS state {state_target} (3 viewports)")
    return snapshots


def validate_interactions(staging: dict[str, Any]) -> None:
    interactions = staging.get("interaction_evidence", {})
    require(interactions.get("selection_continuity", {}).get("retained_after_refresh") is True, "selection continuity evidence failed")
    conditional = interactions.get("conditional_fields", {})
    require(conditional.get("number_has_quantity_unit_min_max") is True and conditional.get("number_has_no_choices") is True, "conditional number evidence failed")
    splitter = interactions.get("splitter_min_default_max", {})
    require(splitter.get("navigator_min") == 220 and splitter.get("navigator_max") == 272 and splitter.get("list_min") == 292 and splitter.get("list_max") == 384, f"splitter min/default/max evidence failed: {splitter}")
    require(splitter.get("navigator_after_arrow", 0) == 264 and splitter.get("list_after_arrow", 0) == 376, f"splitter Arrow behavior failed: {splitter}")
    local_scroll = interactions.get("local_scroll", {})
    require((local_scroll.get("list_scroll_moved") is True or local_scroll.get("list_scroll_not_needed") is True) and local_scroll.get("editor_scroll_moved") is True, "local scroll evidence failed")
    require(interactions.get("duplicate_submit_blocking", {}).get("blocked") is True, "duplicate submit evidence failed")
    stale = interactions.get("stale_conflict", {})
    require(stale.get("focus_region_present") is True and stale.get("local_draft_preserved") is True, "stale conflict preservation evidence failed")
    require(interactions.get("page_errors") == [], f"interaction browser errors: {interactions.get('page_errors')}")
    print("PASS deterministic keyboard, selection, conditional, scroll and recovery interaction evidence")


def main() -> None:
    args = parse_args()
    require(STAGING_PATH.exists(), f"missing staging file: {STAGING_PATH}")
    staging = json.loads(STAGING_PATH.read_text(encoding="utf-8"))
    require(staging.get("family") == "ADM-SCHEMA-CORE", f"wrong staging family: {staging.get('family')}")
    require(staging.get("wave") == "WAVE-05", f"wrong staging wave: {staging.get('wave')}")
    require(staging.get("status") == args.expect_main_agent_status, f"staging status {staging.get('status')} != expected {args.expect_main_agent_status}")
    static = staging.get("static", {})
    for key in ("html", "css", "js", "capture", "validator"):
        require((ROOT / static[key]).exists(), f"missing static source {key}: {static.get(key)}")
    require(set(staging.get("targets", {})) == set(TARGETS), "staging approval target set is not exactly the 11 packet targets")
    require(set(staging.get("evidence_only_states", {})) == set(STATE_EVIDENCE), "staging evidence-only state set is incomplete")
    selected = [args.target] if args.target else list(TARGETS)
    if not args.target and not args.all_packet_targets:
        raise SystemExit("choose --target or --all-packet-targets")
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        for target in selected:
            validate_target(browser, target, staging["targets"][target])
        if args.all_packet_targets:
            for state_target, staged in staging["evidence_only_states"].items():
                validate_state(browser, state_target, staged)
        browser.close()
    if args.all_packet_targets:
        validate_interactions(staging)
    static_text = "\n".join((ROOT / static[key]).read_text(encoding="utf-8") for key in ("html", "css", "js"))
    for forbidden in (r">\s*Duplicate\s*<", r">\s*Delete\s*<", r">\s*Publish\s*<", "workspace setup", "workspace-setup", "database revision", "fake Database"):
        require(not re.search(forbidden, static_text, flags=re.IGNORECASE), f"forbidden shortcut text present: {forbidden}")
    print("ADM-SCHEMA-CORE WAVE-05 validation complete")


if __name__ == "__main__":
    main()

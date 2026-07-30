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
    WIDE_EVIDENCE,
    WIDE_VIEWPORTS,
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

EXPECTED_PREVIEW_FIELDS = [
    "density", "youngs-modulus", "yield-strength", "poisson-ratio", "material-condition", "test-method",
    "measurement-date", "hardness", "test-temperature", "test-direction", "specimen-thickness",
    "representative-response",
]
EXPECTED_ATTRIBUTE_REVISIONS = {
    "density": "11111111-1111-4111-8111-111111111111",
    "youngs-modulus": "22222222-2222-4222-8222-222222222222",
    "yield-strength": "33333333-3333-4333-8333-333333333333",
    "poisson-ratio": "44444444-4444-4444-8444-444444444444",
    "material-condition": "55555555-5555-4555-8555-555555555555",
    "test-method": "66666666-6666-4666-8666-666666666666",
    "measurement-date": "77777777-7777-4777-8777-777777777777",
    "source-reference": "88888888-8888-4888-8888-888888888888",
    "test-temperature": "99999999-9999-4999-8999-999999999999",
    "test-direction": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    "specimen-thickness": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
    "hardness": "abababab-abab-4aba-8aba-abababababab",
    "representative-response": "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
}
EXPECTED_CURVE_ARTIFACT_ID = "dddddddd-dddd-4ddd-8ddd-dddddddddddd"
EXPECTED_CURVE_ARTIFACT_SHA256 = "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd"

PRESERVED_LOWER_HASHES = {
    "administration-database-normal-1366x768": "9995b53dae3a9907fe95f33ad9eed0b4a96a19fe1d7e7d19f61f89249f313724",
    "administration-database-normal-1440x900": "1b2491632ca17a96bbcd32efeac6d8d4cc5555b5ee43eaaa016085538828a2bf",
    "administration-table-edit-draft-1366x768": "9de662dd7dfa2453a66c0b0da830193b4061c25796406b3d88803f8ec5fc8c69",
    "administration-table-edit-draft-1440x900": "2390d47c2b9828f9aa4ae2a0d47d1829b2b4567c2584f13aac5863d0561cb284",
    "administration-attribute-edit-draft-1366x768": "e6682346823355eb99da5eb72eb5c795a31b4847a025d5f554a572e607d7dfd0",
    "administration-attribute-edit-draft-1440x900": "3db6cd5a26221bf62d13bcedd07c7d3a309df3984ef81914a5828da47f9a1a62",
    "administration-edit-stale-conflict-1440x900": "e64c034fb1ad3fd6428ca319d91bde6ec7c675b95b5332d7cb2db49a9552cd21",
    "administration-attribute-long-invalid-1440x900": "51157e7802a56e093d228a74770cd43b6ad85bc7cb4be2161eca1859087f3994",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate the WAVE-05 ADM-SCHEMA-CORE static Administration service-reference bundle.")
    parser.add_argument("--target", choices=sorted(TARGETS), help="Validate one approval target.")
    parser.add_argument("--all-packet-targets", action="store_true", help="Validate all eleven approval targets and evidence-only states.")
    parser.add_argument("--state-target", choices=sorted(STATE_EVIDENCE), help="Validate one evidence-only state at all three registered viewports.")
    parser.add_argument("--expect-main-agent-status", choices=("pending", "accepted"), required=True, help="Expected lifecycle status in the writer staging file.")
    args = parser.parse_args()
    if args.state_target and any((args.target, args.all_packet_targets)):
        parser.error("--state-target is a bounded standalone validation mode")
    return args


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
    editor_scroll = snapshot["localScroll"]["editor"]
    require(editor_scroll["scrollHeight"] > editor_scroll["clientHeight"], f"long Attribute editor does not have genuine overflow for {target}: {editor_scroll}")
    require(editor_scroll["overflowY"] == "scroll", f"long Attribute editor rail is not permanently reserved for {target}: {editor_scroll}")
    require(editor_scroll["reservedScrollbarWidth"] >= 12, f"long Attribute editor rail is not visibly reserved for {target}: {editor_scroll}")


def validate_editor_scroll_rail(snapshot: dict[str, Any], target: str) -> None:
    editor_scroll = snapshot["localScroll"]["editor"]
    rail = snapshot["localScroll"]["editorRail"]
    require(rail is not None, f"editor scroll control is missing for {target}")
    max_scroll = max(0, editor_scroll["scrollHeight"] - editor_scroll["clientHeight"])
    has_overflow = max_scroll > 1
    require(rail["hidden"] is not has_overflow, f"editor scroll control visibility does not match genuine overflow for {target}: {rail}")
    require(abs(rail["ariaMax"] - max_scroll) <= 1, f"editor scroll maximum is not synchronized for {target}: {rail}, max={max_scroll}")
    require(abs(rail["ariaNow"] - editor_scroll["scrollTop"]) <= 1, f"editor scroll position is not synchronized for {target}: {rail}, scrollTop={editor_scroll['scrollTop']}")
    if not has_overflow:
        return
    track = rail["rect"]
    thumb = rail["thumbRect"]
    require(track and thumb and 12 <= track["width"] <= 16, f"visible editor scroll track geometry is invalid for {target}: {rail}")
    require(48 <= thumb["height"] < track["height"], f"editor scroll thumb is not visibly proportional for {target}: {rail}")
    require(track["x"] <= thumb["x"] and thumb["x"] + thumb["width"] <= track["x"] + track["width"] + 0.5, f"editor scroll thumb escapes its track for {target}: {rail}")
    require(track["y"] <= thumb["y"] and thumb["y"] + thumb["height"] <= track["y"] + track["height"] + 0.5, f"editor scroll thumb escapes its vertical track for {target}: {rail}")


def validate_list_information_economy(snapshot: dict[str, Any], target: str) -> None:
    require(snapshot["objectNameSecondaryCount"] == 0, f"secondary prose leaked into Name for {target}")
    is_attribute_list = snapshot["state"].startswith("attribute")
    if is_attribute_list:
        require(snapshot["listColumns"] == ["Name", "Value type", "Rev"], f"Attribute columns drifted for {target}: {snapshot['listColumns']}")
        allowed_types = {"Number", "Discrete choice", "Record reference", "Text", "Date", "Curve / table artifact"}
        require(all(row["columnCount"] == 3 and row["metadata"] in allowed_types for row in snapshot["listRows"]), f"Attribute rows contain non-type prose for {target}: {snapshot['listRows']}")
    else:
        require(snapshot["listColumns"] == ["Name", "Rev"], f"Table columns drifted for {target}: {snapshot['listColumns']}")
        require(all(row["columnCount"] == 2 and row["metadata"] is None for row in snapshot["listRows"]), f"Table rows contain duplicated Definition prose for {target}: {snapshot['listRows']}")


def validate_preview_graph(snapshot: dict[str, Any], viewport_name: str, target: str) -> None:
    graph = snapshot["preview"]["graph"]
    require(graph["visible"] is True, f"saved curve graph is not visible for {target}: {graph}")
    require(graph["title"] == "DP780 representative engineering response", f"graph accessible name drifted for {target}: {graph}")
    require("Saved linked Artifact value" in graph["description"] and "Engineering stress" in graph["description"], f"graph accessible description drifted for {target}: {graph}")
    require(graph["axisTitles"] == ["Engineering strain", "Engineering stress (MPa)"], f"graph axis titles/units drifted for {target}: {graph['axisTitles']}")
    require(graph["path"]["d"].startswith("M ") and " C " in graph["path"]["d"], f"graph response path missing for {target}")
    view_box = graph["viewBox"]
    rendered = graph["rendered"]
    require(len(view_box) == 4 and view_box[0] == 0 and view_box[1] == 0 and view_box[2] > 1 and view_box[3] > 1, f"graph viewBox invalid for {target}: {view_box}")
    require(rendered["width"] > 1 and rendered["height"] > 1, f"graph rendered dimensions missing for {target}: {rendered}")
    require(abs(view_box[2] - rendered["width"]) <= 1 and abs(view_box[3] - rendered["height"]) <= 1, f"graph viewBox/rendered geometry is non-uniform for {target}: {view_box}, {rendered}")
    area = graph["plotArea"]
    require(0 < area["left"] < area["right"] < view_box[2] and 0 < area["top"] < area["bottom"] < view_box[3], f"graph plot frame escapes viewBox for {target}: {area}, {view_box}")
    path = graph["path"]
    require(area["left"] <= path["left"] <= path["right"] <= area["right"] and area["top"] <= path["top"] <= path["bottom"] <= area["bottom"], f"graph response path escapes plot frame for {target}: {path}, {area}")
    require(graph["series"] == {"minStrain": 0, "maxStrain": 0.2, "minStressMpa": 0, "maxStressMpa": 850}, f"graph synthetic series drifted for {target}: {graph['series']}")
    require(graph["axis"] == {"headroomRatio": 0.1, "maxStrain": 0.25, "maxStressMpa": 1000}, f"graph axis domain/headroom drifted for {target}: {graph['axis']}")
    require(path["right"] - area["left"] <= (area["right"] - area["left"]) * 0.9 and area["right"] - path["right"] >= (area["right"] - area["left"]) * 0.08, f"graph right headroom is insufficient for {target}: {path}, {area}")
    require(path["top"] - area["top"] >= (area["bottom"] - area["top"]) * 0.05, f"graph top headroom is insufficient for {target}: {path}, {area}")
    section = graph["section"]
    editor = snapshot["geometry"]["editorPane"]
    status_bar = snapshot["geometry"]["statusBar"]
    require(editor and status_bar and section["y"] >= editor["y"] and section["y"] + section["height"] >= editor["y"] + editor["height"] * 0.88 and section["y"] + section["height"] <= status_bar["y"], f"graph does not reach the useful lower editor region for {target}: {section}, {editor}, {status_bar}")
    minimum_height = {"1920x1080": 300, "2560x1440": 600, "3840x2160": 1000}[viewport_name]
    require(section["height"] >= minimum_height, f"graph result region is too short for {target}: {section}")
    require(graph["artifactId"] == EXPECTED_CURVE_ARTIFACT_ID and graph["artifactSha256"] == EXPECTED_CURVE_ARTIFACT_SHA256, f"curve Artifact identity drifted for {target}: {graph['artifactId']}, {graph['artifactSha256']}")


def validate_preview_contract(snapshot: dict[str, Any], viewport_name: str, target: str) -> None:
    preview = snapshot["preview"]
    expected_fields = EXPECTED_PREVIEW_FIELDS
    stale_projection = ("Materials master", "DP780 synthetic demo steel", "Material datasheet")
    if snapshot["state"] in {"empty", "table-add"}:
        require(preview["projectionState"] == "unavailable", f"unavailable Table state retained a preview projection for {target}: {preview}")
        require(not preview["record"] and not preview["table"], f"unavailable Table state names a stale Record or Table for {target}: {preview}")
        require(not preview["sections"] and not preview["valueRows"] and not preview["layoutRows"], f"unavailable Table state renders stale Layout rows for {target}: {preview}")
        require(all(value not in preview["text"] for value in stale_projection), f"unavailable Table state contains stale companion data for {target}: {preview['text']}")
        if snapshot["state"] == "table-add":
            require("no saved Record or Layout projection" in preview["note"], f"new Table truth boundary is not explained for {target}: {preview}")
    elif snapshot["state"] == "normal":
        require(preview["projectionState"] == "saved" and preview["title"] == "Material datasheet", f"normal preview identity drifted for {target}: {preview}")
        require([row["id"] for row in preview["valueRows"]] == expected_fields and [row["id"] for row in preview["layoutRows"]] == expected_fields, f"normal preview no longer exposes the twelve ordered Layout fields for {target}: {preview}")
        require([row["revisionId"] for row in preview["valueRows"]] == [EXPECTED_ATTRIBUTE_REVISIONS[field] for field in expected_fields], f"Record value Attribute revision pins drifted for {target}: {preview['valueRows']}")
        require([row["revisionId"] for row in preview["layoutRows"]] == [EXPECTED_ATTRIBUTE_REVISIONS[field] for field in expected_fields], f"Layout Attribute revision pins drifted for {target}: {preview['layoutRows']}")
        require(preview["layoutRevisionId"] == "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee" and preview["recordRevisionId"] == "ffffffff-ffff-4fff-8fff-ffffffffffff" and preview["recordTableRevisionId"] == "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee", f"Layout/Record exact revision links drifted for {target}: {preview}")
        curve_value = next((row for row in preview["valueRows"] if row["id"] == "representative-response"), None)
        curve_layout = next((row for row in preview["layoutRows"] if row["id"] == "representative-response"), None)
        require(curve_value and curve_layout and curve_value["artifactId"] == EXPECTED_CURVE_ARTIFACT_ID and curve_value["artifactSha256"] == EXPECTED_CURVE_ARTIFACT_SHA256 and curve_layout["artifactId"] == EXPECTED_CURVE_ARTIFACT_ID and curve_layout["artifactSha256"] == EXPECTED_CURVE_ARTIFACT_SHA256, f"curve value/layout Artifact pin drifted for {target}: {curve_value}, {curve_layout}")
    wide = viewport_name in WIDE_VIEWPORTS or viewport_name == "1920x1080"
    if not wide:
        hidden_geometry = snapshot["geometry"]["preview"]
        require(preview["visible"] is False and preview["commandLabel"] == "Preview datasheet" and (hidden_geometry is None or hidden_geometry["width"] == 0), f"preview leaked into lower canonical surface for {target}")
        return
    require(preview["visible"] is True and preview["open"] is True and preview["commandLabel"] == "Hide preview", f"wide Record preview is not visible/open for {target}")
    panel = snapshot["geometry"]["preview"]
    editor = snapshot["geometry"]["editorPane"]
    workspace = snapshot["geometry"]["workspace"]
    require(panel and panel["width"] >= 320 and panel["height"] > 0, f"wide preview region is too small for {target}: {panel}")
    require(editor and panel["x"] >= editor["x"] and panel["x"] + panel["width"] <= editor["x"] + editor["width"] + 1, f"preview escapes the editor pane for {target}: {panel}, {editor}")
    require(workspace and panel["x"] + panel["width"] <= workspace["x"] + workspace["width"] + 1, f"preview escapes workspace for {target}: {panel}, {workspace}")
    if snapshot["state"] in {"empty", "table-add"}:
        return
    require(preview["title"] == "Material datasheet", f"preview Layout title drifted for {target}: {preview}")
    if snapshot["state"].startswith("attribute"):
        require([section["heading"] for section in preview["sections"]] == ["Record values", "Layout fields"] and preview["graph"]["visible"] is False and "Return to the read-only Table view" in preview["note"], f"Attribute editor exposes an incomplete graph instead of the saved-response disclosure for {target}: {preview}")
        return
    if snapshot["state"] in {"table-saving", "table-save-error"}:
        require(
            [section["heading"] for section in preview["sections"]]
            == ["Record values", "Layout fields"]
            and preview["graph"]["visible"] is False,
            f"Table recovery state did not prioritize the complete draft over the response graph for {target}: {preview}",
        )
        table_scrolls = snapshot["localScroll"].get("previewTables", [])
        require(
            len(table_scrolls) == 2
            and all(item and item["overflowY"] == "auto" for item in table_scrolls),
            f"Table recovery companion preview lost local table scrolling for {target}: {table_scrolls}",
        )
        require(
            all(
                item["scrollHeight"] > item["clientHeight"]
                and item["partialRows"] == 0
                and item["rail"]
                and item["rail"]["hidden"] is False
                for item in table_scrolls
            ),
            f"Table recovery companion preview clips a row or lacks a truthful rail for {target}: {table_scrolls}",
        )
        return
    require([section["heading"] for section in preview["sections"]] == ["Record values", "Layout fields", "Representative response"], f"preview subsections drifted for {target}: {preview['sections']}")
    table_scrolls = snapshot["localScroll"].get("previewTables", [])
    require(len(table_scrolls) == 2 and all(item and item["overflowY"] == "auto" for item in table_scrolls), f"preview local table-scroll contract failed for {target}: {table_scrolls}")
    require(all(item["scrollHeight"] > item["clientHeight"] and item["partialRows"] == 0 and item["rail"] and item["rail"]["hidden"] is False and 12 <= item["rail"]["rect"]["width"] <= 16 and 0 < item["rail"]["thumbRect"]["height"] < item["rail"]["rect"]["height"] and item["rail"]["ariaMin"] == 0 and item["rail"]["ariaMax"] > 0 and item["rail"]["ariaNow"] == 0 for item in table_scrolls), f"preview table rail is not visible genuine overflow or clips a partial row for {target}: {table_scrolls}")
    first, second, graph_section = preview["sections"]
    if viewport_name in WIDE_VIEWPORTS:
        require(second["rect"]["x"] > first["rect"]["x"] + first["rect"]["width"] - 1 and abs(second["rect"]["y"] - first["rect"]["y"]) <= 2, f"wide preview projections are not side-by-side for {target}: {preview['sections']}")
    else:
        require(second["rect"]["y"] >= first["rect"]["y"] + first["rect"]["height"] - 1, f"1920 preview projections are not stacked for {target}: {preview['sections']}")
    require(graph_section["rect"]["y"] >= max(first["rect"]["y"] + first["rect"]["height"], second["rect"]["y"] + second["rect"]["height"]) - 1 and graph_section["rect"]["x"] <= first["rect"]["x"], f"graph is not a full editor-pane result beneath Layout/value evidence for {target}: {preview['sections']}")
    validate_preview_graph(snapshot, viewport_name, target)
    if snapshot["state"] in {"attribute-draft", "attribute-saving", "attribute-save-error", "attribute-discrete", "attribute-reference", "attribute-text", "attribute-long-invalid"}:
        selected_value_rows = [row["id"] for row in preview["valueRows"] if row["selected"]]
        selected_layout_rows = [row["id"] for row in preview["layoutRows"] if row["selected"]]
        if snapshot["state"] == "attribute-reference":
            require(not selected_value_rows and not selected_layout_rows, f"out-of-layout Attribute was highlighted in preview for {target}: {preview}")
        else:
            require(selected_value_rows and selected_value_rows == selected_layout_rows, f"selected Attribute is not synchronized into the preview for {target}: {preview}")


def png_dimensions(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    require(data[:8] == b"\x89PNG\r\n\x1a\n", f"invalid PNG signature: {path}")
    return struct.unpack(">II", data[16:24])


def viewport_contract(snapshot: dict[str, Any], viewport_name: str, target: str) -> None:
    viewport = (VIEWPORTS | WIDE_VIEWPORTS)[viewport_name]
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
    validate_editor_scroll_rail(snapshot, target)
    validate_preview_contract(snapshot, viewport_name, target)
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
        validate_list_information_economy(snapshot, target)
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


def validate_wide_evidence(browser: Browser, target: str, staged: dict[str, Any]) -> None:
    spec = WIDE_EVIDENCE[target]
    image = ROOT / staged["image"]
    require(image.exists(), f"missing wide evidence image: {image}")
    require(png_dimensions(image) == (WIDE_VIEWPORTS[spec["viewport"]]["width"], WIDE_VIEWPORTS[spec["viewport"]]["height"]), f"wrong wide evidence dimensions for {target}")
    require(sha256(image) == staged["sha256"], f"wide evidence staging hash mismatch for {target}")
    page, console_errors, page_errors = open_page(browser, spec["role"], spec["state"], spec["viewport"])
    try:
        require(not console_errors and not page_errors, f"browser errors for wide evidence {target}: {console_errors + page_errors}")
        snapshot = dom_snapshot(page)
        require(snapshot["role"] == spec["role"] and snapshot["state"] == spec["state"], f"wide evidence role/state mismatch for {target}")
        viewport_contract(snapshot, spec["viewport"], target)
        validate_list_information_economy(snapshot, target)
        preview = snapshot["preview"]
        graph = preview["graph"]
        frame = graph["frame"]
        plot_box = graph["plotBox"]
        status_bar = snapshot["geometry"].get("statusBar", {"y": snapshot["viewport"]["height"]})
        require(snapshot["editorMode"] == "table-readonly" and preview["visible"], f"wide normal preview contract failed for {target}")
        require(graph["visible"] and graph["axisTitles"] == ["Engineering strain", "Engineering stress (MPa)"], f"wide graph semantics missing for {target}: {graph}")
        require(frame["y"] >= snapshot["geometry"]["editorPane"]["y"] and frame["y"] + frame["height"] <= status_bar["y"], f"wide graph frame is not fully in the initial workspace for {target}: {frame}")
        require(plot_box["height"] >= 360 and plot_box["y"] >= frame["y"] and plot_box["y"] + plot_box["height"] <= frame["y"] + frame["height"], f"wide graph box is incomplete for {target}: {plot_box}")
        require(frame["width"] >= snapshot["geometry"]["editorPane"]["width"] * 0.9, f"wide graph is confined to a preview rail for {target}: {frame}")
        require(graph["plotArea"]["left"] <= graph["path"]["left"] <= graph["path"]["right"] <= graph["plotArea"]["right"] and graph["plotArea"]["top"] <= graph["path"]["top"] <= graph["path"]["bottom"] <= graph["plotArea"]["bottom"], f"wide graph path containment failed for {target}: {graph}")
        print(f"PASS wide evidence {target} {spec['viewport']} sha256={staged['sha256']}")
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
            validate_list_information_economy(snapshot, state_target)
            validate_attribute_state_semantics(snapshot, state, f"{state_target}-{viewport_name}")
            validate_long_attribute_row_containment(snapshot, f"{state_target}-{viewport_name}")
            if state == "empty":
                require(len(snapshot["rows"]) == 0 and any(button["name"] == "Add Table" for button in snapshot["buttons"]), f"empty state contract failed for {state_target}")
            elif state == "table-add":
                require(snapshot["editorMode"] == "table-add" and snapshot["editorTitle"] == "New Table", f"Add Table editor missing for {state_target}")
                field_names = {field["name"] for field in snapshot["fields"]}
                require({"newTableName", "newTableKey", "newTableDescription", "newTableReason"} <= field_names, f"Add Table fields incomplete for {state_target}: {field_names}")
                require(any(button["name"] == "Save new Table" and not button["disabled"] for button in snapshot["buttons"]), f"Add Table save missing for {state_target}")
            elif state == "attribute-add":
                require(snapshot["editorMode"] == "attribute-add" and snapshot["editorTitle"].startswith("New Attribute for "), f"Add Attribute editor missing for {state_target}")
                type_field = next((field for field in snapshot["fields"] if field["name"] == "newAttributeType"), None)
                require(type_field and not type_field["disabled"] and not type_field["readonly"], f"new Attribute value type is not editable for {state_target}")
                require(snapshot["conditional"]["hasAllowedChoices"] and not snapshot["conditional"]["hasQuantity"], f"new discrete Attribute fields are incorrect for {state_target}")
                require(any(button["name"] == "Save new Attribute" and not button["disabled"] for button in snapshot["buttons"]), f"Add Attribute save missing for {state_target}")
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
            if state in {"table-saving", "table-save-error"} and viewport_name == "1920x1080":
                editor_scroll = snapshot["localScroll"]["editor"]
                editor_box = snapshot["geometry"]["editorScroll"]
                action_names = {"Save new revision", "Discard draft"}
                action_buttons = [
                    button for button in snapshot["buttons"] if button["name"] in action_names
                ]
                require(
                    editor_scroll["scrollHeight"] <= editor_scroll["clientHeight"] + 1,
                    f"{state_target} still hides the Table action row below initial editor overflow: {editor_scroll}",
                )
                require(
                    snapshot["localScroll"]["editorRail"]["hidden"] is True,
                    f"{state_target} exposes a distant editor rail despite a complete first view",
                )
                require(
                    editor_box
                    and len(action_buttons) == 2
                    and all(
                        button["rect"]["y"] >= editor_box["y"] - 0.5
                        and button["rect"]["y"] + button["rect"]["height"]
                        <= editor_box["y"] + editor_box["height"] + 0.5
                        for button in action_buttons
                    ),
                    f"{state_target} Table actions are not completely visible in the initial editor: {action_buttons}, {editor_box}",
                )
                require(
                    snapshot["preview"]["graph"]["visible"] is False,
                    f"{state_target} retained a lower graph instead of prioritizing save/recovery",
                )
            snapshots.append(snapshot)
        finally:
            page.context.close()
    print(f"PASS state {state_target} (3 viewports)")
    return snapshots


def validate_interactions(staging: dict[str, Any]) -> None:
    interactions = staging.get("interaction_evidence", {})
    require(interactions.get("selection_continuity", {}).get("retained_after_refresh") is True, "selection continuity evidence failed")
    add_flows = interactions.get("add_flows", {})
    table_add = add_flows.get("table", {})
    require(table_add.get("editor_mode") == "table-add" and table_add.get("editor_title") == "New Table", f"Add Table interaction failed: {table_add}")
    require(table_add.get("list_columns") == ["Name", "Rev"] and table_add.get("selected_row") == "materials", f"Add Table did not retain list context: {table_add}")
    require({"newTableName", "newTableKey", "newTableDescription", "newTableReason"} <= set(table_add.get("field_names", [])), f"Add Table interaction fields incomplete: {table_add}")
    attribute_add = add_flows.get("attribute", {})
    require(attribute_add.get("editor_mode") == "attribute-add" and str(attribute_add.get("editor_title", "")).startswith("New Attribute for "), f"Add Attribute interaction failed: {attribute_add}")
    require(attribute_add.get("list_columns") == ["Name", "Value type", "Rev"] and attribute_add.get("selected_row") == "density" and attribute_add.get("value_type_editable") is True, f"Add Attribute did not retain list/type context: {attribute_add}")
    require(attribute_add.get("discrete_fields", {}).get("hasAllowedChoices") is True and attribute_add.get("reference_fields", {}).get("hasRelatedTable") is True, f"Add Attribute conditional interaction failed: {attribute_add}")
    conditional = interactions.get("conditional_fields", {})
    require(conditional.get("number_has_quantity_unit_min_max") is True and conditional.get("number_has_no_choices") is True, "conditional number evidence failed")
    splitter = interactions.get("splitter_min_default_max", {})
    require(splitter.get("navigator_min") == 220 and splitter.get("navigator_max") == 272 and splitter.get("list_min") == 292 and splitter.get("list_max") == 384, f"splitter min/default/max evidence failed: {splitter}")
    require(splitter.get("navigator_after_arrow", 0) == 264 and splitter.get("list_after_arrow", 0) == 376, f"splitter Arrow behavior failed: {splitter}")
    local_scroll = interactions.get("local_scroll", {})
    require((local_scroll.get("list_scroll_moved") is True or local_scroll.get("list_scroll_not_needed") is True) and local_scroll.get("editor_scroll_moved") is True, "local scroll evidence failed")
    initial_rail = local_scroll.get("editor_rail_initial", {})
    end_rail = local_scroll.get("editor_rail_end", {})
    arrow_down_rail = local_scroll.get("editor_rail_arrow_down", {})
    require(initial_rail.get("hidden") is False and initial_rail.get("ariaNow") == 0 and initial_rail.get("ariaMax", 0) > 0, f"initial editor scroll control evidence failed: {initial_rail}")
    require(end_rail.get("ariaNow") == end_rail.get("ariaMax") and end_rail.get("ariaMax", 0) > 0, f"End key did not synchronize editor scroll control: {end_rail}")
    require(local_scroll.get("editor_home_scroll_top") == 0 and local_scroll.get("editor_arrow_down_scroll_top", 0) > 0, f"Home/ArrowDown editor scroll behavior failed: {local_scroll}")
    require(0 < arrow_down_rail.get("ariaNow", 0) < arrow_down_rail.get("ariaMax", 0), f"ArrowDown did not synchronize editor scroll thumb: {arrow_down_rail}")
    require(interactions.get("duplicate_submit_blocking", {}).get("blocked") is True, "duplicate submit evidence failed")
    stale = interactions.get("stale_conflict", {})
    require(stale.get("focus_region_present") is True and stale.get("local_draft_preserved") is True, "stale conflict preservation evidence failed")
    wide_preview = interactions.get("wide_preview", {})
    require(wide_preview.get("initial_visible") is True and wide_preview.get("initial_sections") == ["Record values", "Layout fields", "Representative response"], f"wide preview initial evidence failed: {wide_preview}")
    require(wide_preview.get("hidden_after_toggle") is True and wide_preview.get("reopened_and_focused") is True, f"wide preview toggle/focus evidence failed: {wide_preview}")
    require(wide_preview.get("density_selected_rows") == ["density"] and wide_preview.get("yield_selected_rows") == ["yield-strength"], f"Attribute selection did not synchronize to preview rows: {wide_preview}")
    require(wide_preview.get("draft_label_updates_preview") is True and wide_preview.get("draft_saved_value_unchanged") is True, f"Attribute draft preview semantics failed: {wide_preview}")
    require(wide_preview.get("table_rails_visible") is True and wide_preview.get("value_table_keyboard_scroll") is True and wide_preview.get("layout_table_wheel_scroll") is True, f"preview table overflow does not retain visible rail, keyboard, and wheel consequences: {wide_preview}")
    require(wide_preview.get("new_table_has_no_projection") is True, f"new Table preview truth boundary failed: {wide_preview}")
    require(wide_preview.get("empty_has_no_projection") is True, f"empty Table preview truth boundary failed: {wide_preview}")
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
    require(set(staging.get("wide_evidence", {})) == set(WIDE_EVIDENCE), "staging wide evidence set is incomplete")
    require(staging.get("counts", {}).get("approval_targets") == len(TARGETS) and staging.get("counts", {}).get("state_targets") == len(STATE_EVIDENCE) and staging.get("counts", {}).get("state_captures") == len(STATE_EVIDENCE) * len(VIEWPORTS), "wide evidence changed the existing family matrix inventory")
    for target, expected_hash in PRESERVED_LOWER_HASHES.items():
        require(staging["targets"][target]["sha256"] == expected_hash, f"preserved lower canonical hash changed for {target}: {staging['targets'][target]['sha256']}")
    selected = [args.target] if args.target else list(TARGETS) if args.all_packet_targets else []
    if not args.target and not args.all_packet_targets and not args.state_target:
        raise SystemExit("choose --target, --state-target, or --all-packet-targets")
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        for target in selected:
            validate_target(browser, target, staging["targets"][target])
        if args.target or args.all_packet_targets:
            for target, staged in staging["wide_evidence"].items():
                validate_wide_evidence(browser, target, staged)
        if args.all_packet_targets:
            for state_target, staged in staging["evidence_only_states"].items():
                validate_state(browser, state_target, staged)
        elif args.state_target:
            validate_state(
                browser,
                args.state_target,
                staging["evidence_only_states"][args.state_target],
            )
        browser.close()
    if args.all_packet_targets:
        validate_interactions(staging)
    static_text = "\n".join((ROOT / static[key]).read_text(encoding="utf-8") for key in ("html", "css", "js"))
    for forbidden in (r">\s*Duplicate\s*<", r">\s*Delete\s*<", r">\s*Publish\s*<", "workspace setup", "workspace-setup", "database revision", "fake Database"):
        require(not re.search(forbidden, static_text, flags=re.IGNORECASE), f"forbidden shortcut text present: {forbidden}")
    print("ADM-SCHEMA-CORE WAVE-05 validation complete")


if __name__ == "__main__":
    main()

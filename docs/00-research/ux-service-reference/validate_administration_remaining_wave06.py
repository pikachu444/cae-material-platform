from __future__ import annotations

# ruff: noqa: E501
import argparse
import hashlib
import json
import struct
from collections.abc import Iterable
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
SOURCE_DIR = ROOT / "docs/00-research/ux-service-reference"
EVIDENCE_DIR = ROOT / "docs/17-evidence/images/issue-167-service-reference"
STAGING_PATH = SOURCE_DIR / "administration-remaining-wave06.staging.json"
SOURCE_PATHS = [
    SOURCE_DIR / "administration-remaining.html",
    SOURCE_DIR / "administration-remaining.css",
    SOURCE_DIR / "administration-remaining.js",
    SOURCE_DIR / "capture_administration_remaining_wave06.py",
    SOURCE_DIR / "finalize_administration_remaining_wave06.py",
    Path(__file__),
]

VIEWPORTS = {
    "1366x768": (1366, 768),
    "1440x900": (1440, 900),
    "1920x1080": (1920, 1080),
    "2560x1440": (2560, 1440),
    "3840x2160": (3840, 2160),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate WAVE-06 Administration relationship, access, and publish reference evidence.")
    parser.add_argument("--all-packet-targets", action="store_true", help="Validate all 17 approval targets, evidence-only states, and wide evidence.")
    parser.add_argument("--target", help="Validate one target ID present in the staging file.")
    parser.add_argument("--expect-main-agent-status", choices=["pending", "accepted"], default="pending", help="Expected lifecycle status used only for the compact report.")
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def png_dimensions(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"invalid PNG signature: {path}")
    return struct.unpack(">II", data[16:24])


def load_measurement(target: str) -> dict[str, Any]:
    path = EVIDENCE_DIR / f"{target}.measurements.json"
    if not path.exists():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def check(condition: bool, message: str, failures: list[str], passes: list[str]) -> None:
    if condition:
        passes.append(message)
    else:
        failures.append(message)


def all_target_ids(staging: dict[str, Any]) -> list[str]:
    values = list(staging["targets"])
    for state in staging["evidence_only_states"].values():
        values.extend(Path(path).stem for path in state["captures"])
    values.extend(staging["wide_evidence"])
    return values


def validate_common(target: str, measurement: dict[str, Any], failures: list[str], passes: list[str]) -> None:
    snap = measurement["snapshot"]
    viewport = measurement["viewport"]
    expected = VIEWPORTS[viewport]
    image_path = ROOT / measurement["image"]
    check(image_path.exists(), f"{target}: image exists", failures, passes)
    if image_path.exists():
        check(png_dimensions(image_path) == expected, f"{target}: exact viewport dimensions", failures, passes)
        check(sha256(image_path) == measurement["image_sha256"], f"{target}: image SHA-256 matches measurement", failures, passes)
    check(measurement["width"] == expected[0] and measurement["height"] == expected[1], f"{target}: recorded dimensions match viewport", failures, passes)
    check(not measurement["console_errors"] and not measurement["page_errors"], f"{target}: browser errors absent", failures, passes)
    check(snap["ready"] is True, f"{target}: reference reached ready state", failures, passes)
    check(snap["family"] == measurement["family"] and snap["state"] == measurement["state"], f"{target}: family/state identity matches", failures, passes)
    check(snap["documentOverflow"]["horizontal"] <= 0 and snap["documentOverflow"]["vertical"] <= 0, f"{target}: page overflow absent", failures, passes)
    check(not snap["nestedInteractive"], f"{target}: nested interactive controls absent", failures, passes)
    check(all(item["count"] == 0 for item in snap["legacySelectors"]), f"{target}: prohibited legacy selectors absent", failures, passes)
    check(len(snap["activePrimary"]) <= 1, f"{target}: at most one active filled primary command", failures, passes)
    check(snap["bodyFontPx"] <= 13.5 and snap["maximumDataFontPx"] <= 13.5, f"{target}: compact readable data typography", failures, passes)
    check(snap["selectedRowCount"] <= 1, f"{target}: selection is unambiguous", failures, passes)
    geometry = snap["geometry"]
    required_regions = ["application_bar", "command_bar", "workspace", "navigator", "object_list", "editor", "status_bar"]
    check(all(geometry[name] and geometry[name]["width"] > 0 and geometry[name]["height"] > 0 for name in required_regions), f"{target}: required Administration regions exist", failures, passes)
    if viewport in {"2560x1440", "3840x2160"} and geometry.get("editor_grid"):
        check(geometry["editor_grid"]["width"] <= 1281, f"{target}: wide editor cluster remains bounded", failures, passes)
        check(geometry["navigator"]["x"] <= 16 and geometry["object_list"]["x"] < 700, f"{target}: wide task cluster stays left aligned", failures, passes)
    check(measurement["interactions"].get("keyboard_splitter_delta") == 12, f"{target}: keyboard pane resize works", failures, passes)


def values_by_id(measurement: dict[str, Any]) -> dict[str, str]:
    return {item["id"]: item["value"] for item in measurement["snapshot"]["fieldValues"] if item["id"]}


def controls(measurement: dict[str, Any], action: str) -> list[dict[str, Any]]:
    return [item for item in measurement["snapshot"]["controls"] if item["action"] == action]


def validate_family(target: str, measurement: dict[str, Any], failures: list[str], passes: list[str]) -> None:
    family = measurement["family"]
    state = measurement["state"]
    snap = measurement["snapshot"]
    text = snap["documentText"]
    fields = values_by_id(measurement)

    if family == "layout":
        check(snap["pageTitle"] == "Database design", f"{target}: Layout remains in Database design", failures, passes)
        check(len(snap["orderedFields"]) == 9, f"{target}: nine ordered Layout fields are visible", failures, passes)
        check(snap["previewTables"] == (0 if state == "preview-loading" else 1), f"{target}: Layout preview state is truthful", failures, passes)
        check("Saved Record values in current Layout order" in text, f"{target}: preview is tied to saved Record values", failures, passes)
        if state == "missing-attribute-blocked":
            check("Missing Attribute revision" in text and "Deleted Attribute revision" in text, f"{target}: missing exact Attribute is identified", failures, passes)
            check(all(item["disabled"] for item in controls(measurement, "save-layout")), f"{target}: invalid Layout cannot be saved", failures, passes)
        if state == "preview-error":
            check("last valid saved Record remains visible".lower() in text.lower(), f"{target}: last valid Layout preview is preserved on error", failures, passes)
        if state == "draft":
            check("DP780-REF" in text and "Related solver cards" in text, f"{target}: real datasheet context is visible", failures, passes)
            check("Draft save requested" in measurement["interactions"].get("ctrl_s_status", ""), f"{target}: Ctrl+S invokes the enabled revision save", failures, passes)

    elif family == "subset":
        check(len(snap["filters"]) == 3, f"{target}: typed Subset filters are visible", failures, passes)
        check("Same server-scoped query supplies count and rows" in text, f"{target}: Subset count and rows share one server query", failures, passes)
        if state != "preview-loading":
            check("24 authorized matches" in text and "1" + chr(0x2013) + "8 of 24" in text, f"{target}: Subset total and page are consistent", failures, passes)
        if state == "invalid-filter-blocked":
            check("minimum exceeds maximum" in text and "Invalid numeric range" in text, f"{target}: invalid numeric filter is explicit", failures, passes)
            check(all(item["disabled"] for item in controls(measurement, "save-subset")), f"{target}: invalid Subset cannot be saved", failures, passes)
        if state == "preview-error":
            check("last valid result page remains visible".lower() in text.lower(), f"{target}: last valid Subset result is preserved on error", failures, passes)
        if state == "draft":
            check("Draft save requested" in measurement["interactions"].get("ctrl_s_status", ""), f"{target}: Ctrl+S invokes Subset revision save", failures, passes)

    elif family == "link":
        check(fields.get("source-table") == "Neutral materials" and fields.get("target-table") in {"Solver cards", "Neutral materials"}, f"{target}: source and target Tables are explicit", failures, passes)
        check(fields.get("source-cardinality") == "one" and fields.get("target-cardinality") == "many", f"{target}: independent one-to-many cardinalities are visible", failures, passes)
        check(fields.get("forward-label") == "Available solver cards" and fields.get("reverse-label") == "Generated from neutral model", f"{target}: both direction labels are preserved", failures, passes)
        check("each Record Link pins the source revision and target revision" in text, f"{target}: exact endpoint revisions are authoritative", failures, passes)
        check("no “latest” alias" in text, f"{target}: latest-alias prohibition is explicit", failures, passes)
        if state != "validation-loading":
            check(len(snap["related"]) == 5, f"{target}: branching Related test retains five exact links", failures, passes)
        if state == "link-invalid":
            check(fields.get("target-table") == "Neutral materials" and "Invalid endpoints" in text, f"{target}: invalid endpoint combination is shown", failures, passes)
            check(all(item["disabled"] for item in controls(measurement, "save-link")), f"{target}: invalid Link Type cannot be saved", failures, passes)
        if state == "validation-loading":
            check(all(item["disabled"] for item in controls(measurement, "save-link") + controls(measurement, "validate-link")), f"{target}: Link Type commands remain blocked during validation", failures, passes)
        if state == "related-error":
            check("last valid exact-revision branches remain visible".lower() in text.lower(), f"{target}: last valid branches remain on Related test error", failures, passes)
        if state == "draft":
            check("Draft save requested" in measurement["interactions"].get("ctrl_s_status", ""), f"{target}: Ctrl+S invokes Link Type revision save", failures, passes)

    elif family == "access":
        check(snap["pageTitle"] == "Users and access", f"{target}: access screen title is role-oriented", failures, passes)
        if state == "normal":
            check(len(snap["listRows"]) == 8, f"{target}: normal access list exposes eight truthful assignments", failures, passes)
            check(len(snap["tasks"]) == 5 and "Not granted" in text, f"{target}: Reviewer task preset is readable and bounded", failures, passes)
            check(measurement["interactions"].get("revoke_confirmation_visible") is True, f"{target}: revoke command opens a bounded confirmation", failures, passes)
            check(bool(measurement["interactions"].get("revoke_reason_preserved")), f"{target}: revoke reason is preserved", failures, passes)
        elif state == "denied":
            check("Administrator access required" in text and "cannot view or change product assignments" in text, f"{target}: access denial gives a safe return", failures, passes)
            leaked = any(name in text for name in ("material-reviewers", "materials-admins", "external-lab-readers"))
            check(not leaked and not snap["listRows"], f"{target}: denied state leaks no assignment identities", failures, passes)
        elif state == "revoke-confirm":
            check("material-reviewers" in text and "currentrolereviewer" in text.replace(" ", "").lower(), f"{target}: selected assignment context is preserved", failures, passes)
            check(fields.get("revoke-reason") or fields.get("revoke-reason-live"), f"{target}: revoke requires a reason", failures, passes)
            check(len(snap["activePrimary"]) == 1 and "Revoke access" in snap["activePrimary"][0], f"{target}: revoke is the sole destructive primary", failures, passes)
        elif state == "empty":
            check("No assignments exist" in text and fields.get("access-team") == "material-engineers", f"{target}: empty state provides one complete next assignment", failures, passes)
        elif state == "loading":
            check("Commands are disabled" in text and all(item["disabled"] for item in controls(measurement, "add-assignment")), f"{target}: access loading state blocks writes", failures, passes)
        elif state == "service-error":
            check("last valid assignments and selection remain visible".lower() in text.lower() and len(snap["listRows"]) == 8, f"{target}: access service error preserves current context", failures, passes)

    elif family == "publish":
        check(snap["pageTitle"] == "Catalog publish", f"{target}: publish boundary has a distinct task title", failures, passes)
        check("Not configured" in text and "no catalog publication transition" in text.lower(), f"{target}: unavailable publication capability is truthful", failures, passes)
        check(len(snap["publishButtons"]) >= 1 and all(item["disabled"] for item in snap["publishButtons"]), f"{target}: every Publish command is disabled", failures, passes)
        check("Not fabricated" in text and "Published state, publication date, release receipt or successful transition" in text, f"{target}: fabricated publication evidence is explicitly excluded", failures, passes)
        check(len(snap["listRows"]) == 5 and "Saved draft" in text, f"{target}: saved drafts remain visible and editable", failures, passes)
        forbidden_success = any(term in text.lower() for term in ("publication successful", "catalog published successfully", "publish complete"))
        check(not forbidden_success, f"{target}: no fabricated publish success copy", failures, passes)
        if state == "validation-blocked":
            check("Layout validation is blocked" in text and "missing Attribute revision" in text, f"{target}: publication validation blocker is actionable", failures, passes)
        elif state == "validation-loading":
            check("Validating saved draft revisions" in text, f"{target}: publication validation loading state is explicit", failures, passes)
        elif state == "publish-error":
            check("No publication request was sent" in text and "saved draft revisions remain unchanged" in text, f"{target}: publication error preserves drafts", failures, passes)


def iter_measurements(staging: dict[str, Any], selected_target: str | None) -> Iterable[tuple[str, dict[str, Any]]]:
    ids = all_target_ids(staging)
    if selected_target:
        if selected_target not in ids:
            raise KeyError(f"unknown target in staging: {selected_target}")
        ids = [selected_target]
    for target in ids:
        yield target, load_measurement(target)


def main() -> None:
    args = parse_args()
    if not (args.all_packet_targets or args.target):
        raise SystemExit("choose --all-packet-targets or --target")
    failures: list[str] = []
    passes: list[str] = []
    for path in SOURCE_PATHS:
        check(path.exists() and path.stat().st_size > 0, f"source exists: {path.relative_to(ROOT)}", failures, passes)
    check(STAGING_PATH.exists(), "WAVE-06 staging file exists", failures, passes)
    if not STAGING_PATH.exists():
        print("FAIL: staging file missing")
        raise SystemExit(1)
    staging = json.loads(STAGING_PATH.read_text(encoding="utf-8"))
    check(staging["status"] == "pending_product_owner_review", "lifecycle remains pending product-owner review", failures, passes)
    check(staging["counts"] == {"approval_targets": 17, "evidence_state_families": 15, "evidence_state_captures": 45, "wide_evidence": 10}, "finite WAVE-06 inventory is 17 + 45 + 10", failures, passes)
    check(len(staging["targets"]) == 17, "exactly 17 approval targets are registered", failures, passes)
    check(len(staging["evidence_only_states"]) == 15, "exactly 15 evidence-only state families are registered", failures, passes)
    check(len(staging["wide_evidence"]) == 10, "exactly 10 wide evidence images are registered", failures, passes)

    count = 0
    for target, measurement in iter_measurements(staging, args.target):
        count += 1
        validate_common(target, measurement, failures, passes)
        validate_family(target, measurement, failures, passes)

    if failures:
        print(f"FAIL: {len(failures)} of {len(passes) + len(failures)} checks failed across {count} captures")
        for failure in failures:
            print(f"  - {failure}")
        raise SystemExit(1)
    print(f"PASS: {len(passes)} checks across {count} captures; main-agent lifecycle expectation={args.expect_main_agent_status}")


if __name__ == "__main__":
    main()

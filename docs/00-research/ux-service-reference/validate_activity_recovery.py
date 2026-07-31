from __future__ import annotations

# ruff: noqa: E501
import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path
from typing import Any

from playwright.sync_api import Browser, sync_playwright

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
EVIDENCE_DIR = ROOT / "docs/17-evidence/images/issue-167-service-reference"
STAGING_PATH = HERE / "activity-recovery.staging.json"
sys.path.insert(0, str(HERE))
from capture_activity_recovery import (  # noqa: E402
    STATE_EVIDENCE,
    TARGETS,
    VIEWPORTS,
    WIDE_TARGETS,
    dom_snapshot,
    open_page,
)

ACT_QUEUE_SOURCE_HASHES = {
    "activity-queue-normal.html": "3c74d943e447eaa020109a1be527969224f273ac131a1a0625504f62d085034f",
    "activity-queue.css": "26bd2cd69708f712f2d2a78ab0f8ee476bafb9f34a93ee24b5a91940448a87ce",
    "activity-queue.js": "880b479eacab90de92200deee48810cb6614160ea221fb78db6a8d39aac050c5",
}

ALLOWED_SERVER_TASKS = {
    "Material review": "Confirm material details",
    "Test Data review": "Confirm the Test Data",
    "Selected model review": "Confirm the selected model",
    "Solver card review": "Confirm the solver card",
}
FORBIDDEN_PRODUCT_LANGUAGE = (
    "import provenance",
    "source provenance",
    "processing output",
    "curve selection",
    "fit result",
    "mapping",
    "evidence",
    "immutable revision",
    "immutable revisions",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate the ACT-RECOVERY static Activity service-reference bundle.")
    parser.add_argument("--target", choices=sorted(TARGETS), help="Validate one approval target.")
    parser.add_argument("--all-packet-targets", action="store_true", help="Validate all canonical/wide targets and state evidence.")
    parser.add_argument("--wide-support", action="store_true", help="Validate only the 2560x1440 and 3840x2160 support targets.")
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


def png_dimensions(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    require(data[:8] == b"\x89PNG\r\n\x1a\n", f"invalid PNG signature: {path}")
    return struct.unpack(">II", data[16:24])


def validate_activity_queue_authority() -> None:
    queue_dir = HERE
    for name, expected in ACT_QUEUE_SOURCE_HASHES.items():
        path = queue_dir / name
        require(path.exists(), f"approved ACT-QUEUE source is missing: {path}")
        require(sha256(path) == expected, f"approved ACT-QUEUE source hash changed: {path}")
    queue_staging = queue_dir / "activity-queue-wave04.staging.json"
    require(queue_staging.exists(), f"approved ACT-QUEUE staging is missing: {queue_staging}")
    queue_data = json.loads(queue_staging.read_text(encoding="utf-8"))
    for target, spec in queue_data.get("targets", {}).items():
        image = ROOT / spec["image"]
        require(image.exists(), f"approved ACT-QUEUE image is missing: {image}")
        require(sha256(image) == spec["sha256"], f"approved ACT-QUEUE image hash changed: {target}")
    print("PASS frozen ACT-QUEUE authority hashes")


def validate_snapshot(snapshot: dict[str, Any], target: str, role: str, state: str, viewport_name: str) -> None:
    require(snapshot["role"] == "user" and role == "user", f"role changed for {target}")
    require(snapshot["state"] == state, f"state mismatch for {target}: {snapshot['state']} != {state}")
    viewport = VIEWPORTS[viewport_name]
    require(snapshot["viewport"]["width"] == viewport["width"] and snapshot["viewport"]["height"] == viewport["height"], f"viewport mismatch for {target}")
    require(snapshot["viewport"]["deviceScaleFactor"] == 1, f"device scale factor is not 1 for {target}")
    require(all(value == 0 for value in snapshot["overflow"].values()), f"document/body overflow for {target}: {snapshot['overflow']}")
    require(snapshot["legacy"] == [], f"legacy selectors present for {target}: {snapshot['legacy']}")
    require(snapshot["nestedInteractive"] == [], f"nested interactive controls for {target}: {snapshot['nestedInteractive']}")
    require(snapshot["tabCount"] == 3, f"saved-view topology changed for {target}")
    require(snapshot["activeTab"] == "in-progress", f"In progress is not the active view for {target}")
    require(sum(1 for section in snapshot["sections"] if section["visible"]) == 1, f"inactive tabpanel is visible for {target}")
    require(snapshot["tableCount"] == 3, f"semantic queue tables missing for {target}")
    require(snapshot["tableHeaders"] == ["Task", "Request reason", "Status", "Updated", "Action"], f"queue headers changed for {target}: {snapshot['tableHeaders']}")
    require(snapshot["geometry"]["queue"] and snapshot["geometry"]["content"], f"queue/content geometry missing for {target}")
    require(snapshot["geometry"]["queue"]["width"] / max(snapshot["geometry"]["content"]["width"], 1) >= 0.82, f"queue width does not dominate for {target}")
    queue_scroll = snapshot["queueScroll"]
    require(queue_scroll and queue_scroll["overflowY"] in ("auto", "scroll"), f"queue scroll rail missing for {target}")
    require("stable" in queue_scroll["scrollbarGutter"], f"queue scroll rail does not reserve a track for {target}")
    require(all(row["reasonClipped"] is False for row in snapshot["rows"]), f"row reason clipped for {target}")
    require(all(control["name"] for control in snapshot["controls"]), f"unnamed visible control for {target}")
    require(snapshot["typography"]["body"] >= 13 and snapshot["typography"]["task"] >= 13 and snapshot["typography"]["metadata"] >= 12, f"compact typography below contract for {target}: {snapshot['typography']}")
    require(snapshot["boundary"] == {
        "title": "Failed calculations",
        "status": "Not available in Activity",
        "consequence": "Resume the saved Modeling session to inspect the current step.",
        "titleCount": 1,
        "statusCount": 1,
        "consequenceCount": 1,
    }, f"unavailable boundary changed or repeated for {target}: {snapshot['boundary']}")
    forbidden = ("projection", "job id", "attempt", "runner", "manifest", "failure code", "receipt", "outbox", "release", "uuid", "hash", "api", "retry")
    visible_text = snapshot["pageText"].lower()
    require(not any(term in visible_text for term in forbidden), f"forbidden internal vocabulary visible for {target}")
    queue_text = "\n".join(f"{row['task']} {row['reason']}" for row in snapshot["rows"]).lower()
    require(
        not any(term in queue_text for term in FORBIDDEN_PRODUCT_LANGUAGE),
        f"forbidden product-language vocabulary visible for {target}",
    )
    require(":focus-visible" in (HERE / "activity-recovery.css").read_text(encoding="utf-8"), f"focus-visible rule missing for {target}")
    if snapshot["rows"]:
        require(snapshot["rowHeightRange"]["min"] >= 42 and snapshot["rowHeightRange"]["max"] <= 52, f"row-height range outside compact contract for {target}: {snapshot['rowHeightRange']}")
    if queue_scroll["hasOverflow"]:
        require(snapshot["overflowRail"]["reserved"], f"overflow rail is not reserved for {target}")
        require(snapshot["overflowRail"]["trackHeight"] > snapshot["overflowRail"]["thumbHeight"] >= 42, f"overflow thumb is not proportional for {target}")


def validate_normal(snapshot: dict[str, Any], target: str, viewport_name: str) -> None:
    rows = snapshot["rows"]
    require(len(rows) == 41, f"normal surface must expose 41 rows for {target}, got {len(rows)}")
    require(rows[0]["id"] == "modeling-session-local" and rows[0]["source"] == "browser-local", f"saved Modeling row is not first for {target}")
    require(rows[0]["task"] == "Resume Modeling session", f"local task changed for {target}")
    require(
        rows[0]["reason"] == "DP780 Dual-Phase Steel · selected model needs review",
        f"saved Modeling context changed for {target}",
    )
    require(rows[0]["status"] == "Saved in this browser", f"local status changed for {target}")
    require(rows[0]["command"] == "resume" and rows[0]["commandPrimary"] and rows[0]["commandNames"] == ["Resume Modeling"], f"Resume Modeling is not the sole filled action for {target}")
    server_rows = rows[1:]
    require(len(server_rows) == 40 and all(row["source"] == "server" for row in server_rows), f"normal server request count changed for {target}")
    require(
        all(row["task"] in ALLOWED_SERVER_TASKS for row in server_rows),
        f"server task outside the bounded product-language set for {target}",
    )
    require(
        all(row["reason"].startswith(ALLOWED_SERVER_TASKS[row["task"]]) for row in server_rows),
        f"server request reason does not state its concrete product decision for {target}",
    )
    require(all(row["actionKind"] == "state" and row["passiveAction"] and row["actionText"] == "—" and not row["command"] for row in server_rows), f"normal server rows expose an unsupported action for {target}")
    require(all(row["status"] == "Needs a decision" for row in server_rows), f"normal server lifecycle changed for {target}")
    require(snapshot["contract"]["serverRequestCount"] == 40 and snapshot["contract"]["pendingCount"] == 40 and snapshot["contract"]["localHistoryCount"] == 1, f"normal contract counts changed for {target}: {snapshot['contract']}")
    require(not any(row["actionText"].lower() == "retry" for row in rows), f"normal surface exposes Retry for {target}")
    require(not any(control["name"].startswith(("Review", "Approve", "Request changes")) for control in snapshot["controls"]), f"user decision controls exposed for {target}")
    require(viewport_name != "3840x2160" or len(rows) == 41, f"wide normal row count changed for {target}")


def validate_state_snapshot(snapshot: dict[str, Any], state_target: str, state: str) -> None:
    rows = snapshot["rows"]
    server_rows = [row for row in rows if row["source"] == "server"]
    require(
        all(row["task"] in ALLOWED_SERVER_TASKS for row in server_rows),
        f"state task outside the bounded product-language set for {state_target}",
    )
    require(
        all(row["reason"].startswith(ALLOWED_SERVER_TASKS[row["task"]]) for row in server_rows),
        f"state reason does not state its concrete product decision for {state_target}",
    )
    if state == "recovery-empty":
        require(len(rows) == 40 and all(row["source"] == "server" for row in rows), f"empty recovery must retain available queue rows without the local session: {state_target}")
        open_buttons = [control for control in snapshot["controls"] if control["action"] == "open-modeling"]
        require(len(open_buttons) == 1 and open_buttons[0]["name"].startswith("Open Modeling") and not open_buttons[0]["primary"], f"empty recovery must expose one quiet Open Modeling action: {state_target}")
        require(not any(control["action"] == "resume" for control in snapshot["controls"]), f"empty recovery exposes Resume Modeling: {state_target}")
    elif state == "recovery-loading":
        require(len(rows) == 41 and rows[0]["id"] == "modeling-session-local", f"loading recovery lost the saved session or queue rows: {state_target}")
        require(snapshot["refresh"] == {"text": "Refreshing…", "disabled": True}, f"loading recovery refresh state changed: {snapshot['refresh']}")
        require("Available Activity work" in snapshot["announcement"] and "failed" not in snapshot["announcement"].lower(), f"loading announcement is not scoped to available Activity work: {state_target}")
    elif state == "recovery-action-error":
        require(len(rows) == 41 and rows[0]["id"] == "modeling-session-local", f"action-error recovery lost the saved session or queue rows: {state_target}")
        require(snapshot["feedbackCount"] == 1 and snapshot["feedback"][0]["tryAgain"] and rows[0]["selected"] and rows[0]["command"] == "resume", f"action-error state must retain the selected saved row and one Try again consequence: {state_target}")
        require(not any(control["name"].lower().startswith("retry") for control in snapshot["controls"]), f"action-error state exposes Retry: {state_target}")


def validate_target(browser: Browser, target: str, staging_target: dict[str, Any]) -> dict[str, Any]:
    spec = TARGETS[target]
    viewport_name = spec["viewport"]
    image = ROOT / staging_target["image"]
    require(image.exists(), f"missing approval image: {image}")
    require(png_dimensions(image) == (VIEWPORTS[viewport_name]["width"], VIEWPORTS[viewport_name]["height"]), f"wrong dimensions for {target}")
    require(sha256(image) == staging_target["sha256"], f"staging hash mismatch for {target}")
    page, console_errors, page_errors = open_page(browser, spec["role"], spec["state"], viewport_name)
    try:
        require(not console_errors and not page_errors, f"browser errors for {target}: {console_errors + page_errors}")
        snapshot = dom_snapshot(page)
        validate_snapshot(snapshot, target, spec["role"], spec["state"], viewport_name)
        validate_normal(snapshot, target, viewport_name)
        print(f"PASS target {target} {viewport_name} sha256={staging_target['sha256']}")
        return snapshot
    finally:
        page.context.close()


def validate_state(browser: Browser, state_target: str, state_spec: dict[str, Any]) -> None:
    role = state_spec["role"]
    state = state_spec["state"]
    captures = state_spec.get("captures", [])
    require(len(captures) == 3, f"state evidence must have three viewports: {state_target}")
    for image_rel in captures:
        image = ROOT / image_rel
        require(image.exists(), f"missing state image: {image}")
        if image.stem.endswith("1920x1080"):
            viewport_name = "1920x1080"
        elif image.stem.endswith("1440x900"):
            viewport_name = "1440x900"
        else:
            viewport_name = "1366x768"
        require(png_dimensions(image) == (VIEWPORTS[viewport_name]["width"], VIEWPORTS[viewport_name]["height"]), f"wrong state dimensions: {image}")
        page, console_errors, page_errors = open_page(browser, role, state, viewport_name)
        try:
            require(not console_errors and not page_errors, f"browser errors for {state_target}: {console_errors + page_errors}")
            snapshot = dom_snapshot(page)
            validate_snapshot(snapshot, state_target, role, state, viewport_name)
            validate_state_snapshot(snapshot, state_target, state)
        finally:
            page.context.close()
    print(f"PASS state {state_target} (3 viewports)")


def validate_interactions() -> None:
    evidence_path = EVIDENCE_DIR / "activity-recovery-state-evidence.json"
    require(evidence_path.exists(), f"missing interaction evidence: {evidence_path}")
    interactions = json.loads(evidence_path.read_text(encoding="utf-8")).get("interactions", {})
    tabs = interactions.get("saved_view_keyboard", {})
    require(tabs.get("end_active") is True and tabs.get("home_active") is True and tabs.get("arrow_active") is True, f"saved-view keyboard evidence failed: {tabs}")
    scroll = interactions.get("queue_pointer_keyboard_scroll", {})
    require(scroll.get("pointer_wheel_moved") is True and scroll.get("keyboard_page_down_moved") is True and scroll.get("end_reached") is True and scroll.get("selected_row_visible_after_resume") is True, f"queue scroll evidence failed: {scroll}")
    require(interactions.get("focus_visible") is True, "focus-visible interaction evidence missing")
    require(interactions.get("destination") == "modeling-session-local", "Resume Modeling did not change the simulated destination")
    loading = interactions.get("loading_refresh", {})
    require(loading.get("text") == "Refreshing…" and loading.get("disabled") is True and "Available Activity work" in loading.get("announcement", ""), f"loading refresh evidence failed: {loading}")
    empty = interactions.get("empty_open_modeling", {})
    require(empty.get("destination") == "modeling-new" and empty.get("resume_count") == 0 and empty.get("status") == "Modeling opened", f"empty action evidence failed: {empty}")
    action_error = interactions.get("action_error_recovery", {})
    require(action_error.get("error_visible") is True and action_error.get("selected_row") is True and action_error.get("scroll_preserved") is True and action_error.get("try_again_present") is True and action_error.get("error_cleared") is True and action_error.get("destination") == "modeling-session-local" and action_error.get("status") == "Modeling session opened", f"action-error recovery evidence failed: {action_error}")
    errors = [value for key, value in interactions.items() if key.endswith("console_errors") or key.endswith("page_errors")]
    require(all(not value for value in errors), f"interaction page errors present: {errors}")
    print("PASS deterministic pointer/keyboard/recovery interaction evidence")


def main() -> None:
    args = parse_args()
    require(not (args.wide_support and (args.target or args.all_packet_targets)), "--wide-support cannot be combined with another target selector")
    require(STAGING_PATH.exists(), f"missing staging file: {STAGING_PATH}")
    staging = json.loads(STAGING_PATH.read_text(encoding="utf-8"))
    require(staging.get("family") == "ACT-RECOVERY", f"wrong staging family: {staging.get('family')}")
    require(staging.get("status") == args.expect_main_agent_status, f"staging status {staging.get('status')} != expected {args.expect_main_agent_status}")
    static = staging.get("static", {})
    for key in ("html", "css", "js", "capture", "validator"):
        require((ROOT / static[key]).exists(), f"missing static source {key}: {static.get(key)}")
    validate_activity_queue_authority()
    if not args.target and not args.all_packet_targets and not args.wide_support:
        raise SystemExit("choose --target, --wide-support, or --all-packet-targets")
    targets = staging.get("targets", {})
    if args.all_packet_targets:
        require(set(targets) == set(TARGETS), f"staging targets are incomplete: {sorted(targets)}")
    elif args.wide_support:
        require(set(WIDE_TARGETS).issubset(targets), "wide-support targets are not staged")
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        selected = [args.target] if args.target else (list(TARGETS) if args.all_packet_targets else list(WIDE_TARGETS) if args.wide_support else [])
        for target in selected:
            require(target in targets, f"target not staged: {target}")
            validate_target(browser, target, targets[target])
        if args.all_packet_targets:
            evidence_states = staging.get("evidence_only_states", {})
            require(set(evidence_states) == set(STATE_EVIDENCE), "all ACT-RECOVERY evidence-only states must be staged")
            for state_target, state_spec in evidence_states.items():
                validate_state(browser, state_target, state_spec)
        browser.close()
    if args.all_packet_targets:
        validate_interactions()
    print("ACT-RECOVERY validation complete")


if __name__ == "__main__":
    main()

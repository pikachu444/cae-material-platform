from __future__ import annotations

# ruff: noqa: E501
import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path
from typing import Any

from playwright.sync_api import Browser, Page, sync_playwright

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
EVIDENCE_DIR = ROOT / "docs/17-evidence/images/issue-167-service-reference"
STAGING_PATH = HERE / "activity-queue-wave04.staging.json"
sys.path.insert(0, str(HERE))
from capture_activity_queue_wave04 import (  # noqa: E402
    STATE_EVIDENCE,
    TARGETS,
    VIEWPORTS,
    dom_snapshot,
    open_page,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate the WAVE-04 ACT-QUEUE static Activity service-reference bundle.")
    parser.add_argument("--target", choices=sorted(TARGETS), help="Validate one approval target.")
    parser.add_argument("--all-packet-targets", action="store_true", help="Validate all seven approval targets and evidence-only states.")
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


def open_target_page(browser: Browser, role: str, state: str, viewport_name: str) -> tuple[Page, list[str], list[str]]:
    return open_page(browser, role, state, viewport_name)


def validate_contract(snapshot: dict[str, Any], target: str, role: str, state: str, viewport_name: str) -> None:
    require(snapshot["role"] == role and snapshot["state"] == state, f"role/state mismatch for {target}: {snapshot['role']}/{snapshot['state']}")
    viewport = VIEWPORTS[viewport_name]
    require(snapshot["viewport"]["width"] == viewport["width"] and snapshot["viewport"]["height"] == viewport["height"], f"viewport mismatch for {target}")
    require(snapshot["viewport"]["deviceScaleFactor"] == 1, f"device scale factor is not 1 for {target}")
    require(all(value == 0 for value in snapshot["overflow"].values()), f"document/body overflow for {target}: {snapshot['overflow']}")
    require(snapshot["legacy"] == [], f"legacy selectors present for {target}: {snapshot['legacy']}")
    require(snapshot["nestedInteractive"] == [], f"nested interactive controls for {target}: {snapshot['nestedInteractive']}")
    require(snapshot["tabCount"] == 3, f"saved-view topology changed for {target}")
    require([item["id"] for item in snapshot["sections"]] == ["needs-attention", "in-progress", "recent-outcomes"], f"section order changed for {target}")
    require(snapshot["geometry"]["queue"] and snapshot["geometry"]["content"], f"queue/content geometry missing for {target}")
    queue_width = snapshot["geometry"]["queue"]["width"]
    content_width = snapshot["geometry"]["content"]["width"]
    require(queue_width / max(content_width, 1) >= 0.82, f"queue width does not dominate for {target}: {queue_width}/{content_width}")
    queue_scroll = snapshot["queueScroll"]
    require(queue_scroll and queue_scroll["overflowY"] in ("auto", "scroll"), f"queue scroll rail missing for {target}")
    require("stable" in queue_scroll["scrollbarGutter"], f"queue scroll rail does not reserve a track for {target}")
    require(all(row["reasonClipped"] is False for row in snapshot["rows"]), f"row reason clipped for {target}")
    require(all(control["name"] for control in snapshot["controls"]), f"unnamed visible control for {target}")
    require(snapshot["typography"]["body"] >= 13 and snapshot["typography"]["task"] >= 13 and snapshot["typography"]["metadata"] >= 12, f"compact typography below contract for {target}: {snapshot['typography']}")
    require(":focus-visible" in (HERE / "activity-queue.css").read_text(encoding="utf-8"), f"focus-visible rule missing for {target}")
    if state in {"queue-error", "decision-error", "stale-unauthorized", "long-decision-error"}:
        require(snapshot["announcements"]["alert"], f"local live alert missing for {target}")
    if state in {"decision-error", "stale-unauthorized", "long-decision-error"}:
        selected_choices = snapshot["decision"]["selectedChoice"]
        require(len(selected_choices) == 1 and selected_choices[0]["chosen"], f"selected decision choice is not perceptually clear for {target}: {selected_choices}")
    if state == "loading":
        require(snapshot["announcements"]["loading"], f"busy announcement missing for {target}")

    buttons = [control["name"] for control in snapshot["controls"] if control["tag"] == "button"]
    forbidden_user = [name for name in buttons if name.startswith("Review") or name in {"Approve", "Request changes", "Record decision"}]
    if role == "user":
        require(not forbidden_user, f"user role exposes decision controls for {target}: {forbidden_user}")
    if role == "reviewer" and state == "normal":
        require(sum(row["hasReview"] for row in snapshot["rows"]) >= 1, f"reviewer normal queue has no Review action for {target}")
        require(not snapshot["decision"]["visible"], f"review decision is permanently open for {target}")
    if state == "long-decision-error":
        require(role == "reviewer", "long decision error must be reviewer-only")
        require(queue_scroll["scrollHeight"] > queue_scroll["clientHeight"], f"long decision state does not require local vertical scrolling for {target}")
        require(snapshot["decision"]["visible"], f"selected decision surface missing for {target}")
        require(snapshot["decision"]["reason"].strip(), f"decision reason was not preserved for {target}")
        require(snapshot["decision"]["selected"], f"selected request was not preserved for {target}")
        require(snapshot["decision"]["help"] == "Reason retained; retry will resubmit this decision.", f"long decision error has incorrect retained-reason help for {target}")
        require("Reason is required" not in snapshot["decision"]["help"], f"long decision error contradicts preserved reason for {target}")
        require(snapshot["decision"]["recoveryCommands"] == [{"name": "Retry decision", "action": "retry-decision", "primary": True}], f"long decision error has competing recovery commands for {target}: {snapshot['decision']['recoveryCommands']}")
        require(snapshot["queueStatus"] == "Decision not recorded", f"long decision error has incorrect queue status for {target}: {snapshot['queueStatus']}")
        require("remain available" in snapshot["decision"]["error"], f"decision failure does not preserve context for {target}")


def validate_target(browser: Browser, target: str, staging_target: dict[str, Any]) -> None:
    spec = TARGETS[target]
    viewport_name = spec["viewport"]
    image = ROOT / staging_target["image"]
    require(image.exists(), f"missing approval image: {image}")
    require(png_dimensions(image) == (VIEWPORTS[viewport_name]["width"], VIEWPORTS[viewport_name]["height"]), f"wrong dimensions for {target}: {png_dimensions(image)}")
    require(sha256(image) == staging_target["sha256"], f"staging hash mismatch for {target}")
    page, console_errors, page_errors = open_target_page(browser, spec["role"], spec["state"], viewport_name)
    try:
        require(not console_errors and not page_errors, f"browser errors for {target}: {console_errors + page_errors}")
        snapshot = dom_snapshot(page)
        validate_contract(snapshot, target, spec["role"], spec["state"], viewport_name)
        print(f"PASS target {target} {viewport_name} sha256={staging_target['sha256']}")
    finally:
        page.context.close()


def validate_state(browser: Browser, state_target: str, state_spec: dict[str, Any]) -> list[dict[str, Any]]:
    role = state_spec["role"]
    state = state_spec["state"]
    captures = state_spec.get("captures", [])
    require(len(captures) == 3, f"state evidence must have three viewports: {state_target}")
    snapshots: list[dict[str, Any]] = []
    for image_rel in captures:
        image = ROOT / image_rel
        if image.stem.endswith("1920x1080"):
            viewport_name = "1920x1080"
        elif image.stem.endswith("1440x900"):
            viewport_name = "1440x900"
        else:
            viewport_name = "1366x768"
        require(image.exists(), f"missing state image: {image}")
        require(png_dimensions(image) == (VIEWPORTS[viewport_name]["width"], VIEWPORTS[viewport_name]["height"]), f"wrong state dimensions: {image}")
        page, console_errors, page_errors = open_target_page(browser, role, state, viewport_name)
        try:
            require(not console_errors and not page_errors, f"browser errors for {state_target}: {console_errors + page_errors}")
            snapshot = dom_snapshot(page)
            validate_contract(snapshot, state_target, role, state, viewport_name)
            if state == "empty":
                require(sum(section["rows"] for section in snapshot["sections"]) == 0, f"empty state retains queue rows: {state_target}")
                require(any(control["name"] == "Start Modeling" for control in snapshot["controls"]), f"empty state lacks one next command: {state_target}")
            elif state == "loading":
                require(snapshot["announcements"]["loading"], f"loading state lacks busy row: {state_target}")
                require(any(row["id"] == "modeling-session-local" for row in snapshot["rows"]), f"loading state lost local Modeling session: {state_target}")
                require(any(row["id"] == "solver-card-local" for row in snapshot["rows"]), f"loading state lost solver-card history: {state_target}")
            elif state == "long-row":
                require(any(len(row["reason"]) > 100 for row in snapshot["rows"]), f"long row evidence is not long: {state_target}")
                require(any(row["reasonClipped"] is False for row in snapshot["rows"]), f"long row was clipped: {state_target}")
            elif state == "queue-error":
                require(snapshot["announcements"]["alert"], f"queue error alert missing: {state_target}")
                require(any(control["name"] == "Retry activity queue" for control in snapshot["controls"]), f"queue error Retry missing: {state_target}")
                require(any(row["id"] == "modeling-session-local" for row in snapshot["rows"]), f"queue error lost local row: {state_target}")
            elif state == "decision-blocked":
                require(role == "user" and not snapshot["decision"]["visible"], f"user-role decision block topology wrong: {state_target}")
                require("Reviewer or Administrator" in snapshot.get("pageText", ""), f"decision block context missing: {state_target}")
            elif state == "decision-error":
                require(role == "reviewer" and snapshot["decision"]["visible"], f"decision failure surface missing: {state_target}")
                require(snapshot["decision"]["reason"].strip() and snapshot["decision"]["selected"], f"decision failure lost request/reason: {state_target}")
                require(snapshot["decision"]["help"] == "Reason retained; retry will resubmit this decision.", f"decision error has incorrect retained-reason help: {state_target}")
                require(snapshot["decision"]["recoveryCommands"] == [{"name": "Retry decision", "action": "retry-decision", "primary": True}], f"decision error has competing recovery commands: {state_target}")
                require(snapshot["queueStatus"] == "Decision not recorded", f"decision error has incorrect queue status: {state_target}")
            elif state == "stale-unauthorized":
                require(role == "reviewer" and snapshot["decision"]["visible"], f"access recovery surface missing: {state_target}")
                require(snapshot["decision"]["reason"].strip() and snapshot["decision"]["selected"], f"access recovery lost request/reason: {state_target}")
                require(snapshot["decision"]["help"] == "Reason retained; refresh access before a new decision.", f"stale access has incorrect retained-reason help: {state_target}")
                require(snapshot["decision"]["recoveryCommands"] == [{"name": "Refresh access", "action": "refresh-access", "primary": True}], f"stale access implies an unsafe retry: {state_target}")
                require(snapshot["queueStatus"] == "Review access needs refresh", f"stale access has incorrect queue status: {state_target}")
            snapshots.append(snapshot)
        finally:
            page.context.close()
    print(f"PASS state {state_target} (3 viewports)")
    return snapshots


def validate_interactions() -> None:
    evidence_path = EVIDENCE_DIR / "activity-queue-wave04-state-evidence.json"
    require(evidence_path.exists(), f"missing interaction evidence: {evidence_path}")
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    interactions = evidence.get("interactions", {})
    require(interactions.get("saved_view_switching", {}).get("in_progress_active") is True, "saved-view In progress did not become active")
    require(interactions.get("saved_view_switching", {}).get("needs_attention_active") is True, "saved-view Needs attention did not restore")
    require(interactions.get("queue_pointer_keyboard_scroll", {}).get("pointer_wheel_moved") is True, "pointer queue scroll did not move")
    require(interactions.get("queue_pointer_keyboard_scroll", {}).get("keyboard_page_down_moved") is True, "keyboard queue scroll did not move")
    require(interactions.get("focus_visible") is True, "focus-visible interaction evidence missing")
    require(interactions.get("review_open_close", {}).get("open") is True and interactions.get("review_open_close", {}).get("close_with_escape") is True, "Review open/close interaction failed")
    require(interactions.get("reason_validation", {}).get("blank_rejected") is True and interactions.get("reason_validation", {}).get("non_empty_accepted") is True, "reason validation interaction failed")
    require(interactions.get("decision_choice", {}).get("request_changes_selected") is True, "decision choice interaction failed")
    require(interactions.get("duplicate_submit_blocking", {}).get("blocked") is True, "duplicate submit was not blocked")
    retry = interactions.get("retry_and_selected_row_restoration", {})
    require(retry.get("reason_preserved") is True and retry.get("error_preserved") is True and retry.get("same_decision_retried") is True and retry.get("retry_status") == "Decision not recorded", "retry did not resubmit and preserve selected request/reason")
    access = interactions.get("access_recovery", {})
    require(access.get("status") == "Review access needs refresh" and access.get("decision_sent") is False, "stale access recovery implied a successful retry")
    require(not interactions.get("user_console_errors") and not interactions.get("user_page_errors") and not interactions.get("reviewer_console_errors") and not interactions.get("reviewer_page_errors") and not interactions.get("error_console_errors") and not interactions.get("error_page_errors") and not interactions.get("access_console_errors") and not interactions.get("access_page_errors"), "interaction page errors present")
    print("PASS deterministic pointer/keyboard/recovery interaction evidence")


def main() -> None:
    args = parse_args()
    require(STAGING_PATH.exists(), f"missing staging file: {STAGING_PATH}")
    staging = json.loads(STAGING_PATH.read_text(encoding="utf-8"))
    require(staging.get("family") == "ACT-QUEUE", f"wrong staging family: {staging.get('family')}")
    require(staging.get("status") == args.expect_main_agent_status, f"staging status {staging.get('status')} != expected {args.expect_main_agent_status}")
    static = staging.get("static", {})
    for key in ("html", "css", "js", "capture", "validator"):
        require((ROOT / static[key]).exists(), f"missing static source {key}: {static.get(key)}")
    selected = [args.target] if args.target else list(TARGETS)
    if not args.target and not args.all_packet_targets:
        raise SystemExit("choose --target or --all-packet-targets")
    targets = staging.get("targets", {})
    if args.all_packet_targets:
        require(set(targets) == set(TARGETS), f"staging targets are incomplete: {sorted(targets)}")
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        for target in selected:
            require(target in targets, f"target not staged: {target}")
            validate_target(browser, target, targets[target])
        if args.all_packet_targets:
            evidence_states = staging.get("evidence_only_states", {})
            require(set(evidence_states) == set(STATE_EVIDENCE), "all ACT-U/ACT-R evidence-only states must be staged")
            for state_target, state_spec in evidence_states.items():
                validate_state(browser, state_target, state_spec)
        browser.close()
    if args.all_packet_targets:
        validate_interactions()
    print("ACT-QUEUE WAVE-04 validation complete")


if __name__ == "__main__":
    main()

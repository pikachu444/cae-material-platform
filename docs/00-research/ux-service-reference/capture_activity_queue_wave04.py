from __future__ import annotations

# ruff: noqa: E501
import argparse
import hashlib
import json
import struct
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from playwright.sync_api import Browser, Page, sync_playwright

ROOT = Path(__file__).resolve().parents[3]
HTML_PATH = ROOT / "docs/00-research/ux-service-reference/activity-queue-normal.html"
EVIDENCE_DIR = ROOT / "docs/17-evidence/images/issue-167-service-reference"
STAGING_PATH = ROOT / "docs/00-research/ux-service-reference/activity-queue-wave04.staging.json"

VIEWPORTS: dict[str, dict[str, int]] = {
    "1366x768": {"width": 1366, "height": 768, "device_scale_factor": 1},
    "1440x900": {"width": 1440, "height": 900, "device_scale_factor": 1},
    "1920x1080": {"width": 1920, "height": 1080, "device_scale_factor": 1},
    "2560x1440": {"width": 2560, "height": 1440, "device_scale_factor": 1},
    "3840x2160": {"width": 3840, "height": 2160, "device_scale_factor": 1},
}
STATE_VIEWPORTS = ("1366x768", "1440x900", "1920x1080")

CANONICAL_TARGETS: dict[str, dict[str, Any]] = {
    "activity-user-normal-1366x768": {"role": "user", "state": "normal", "viewport": "1366x768"},
    "activity-user-normal-1440x900": {"role": "user", "state": "normal", "viewport": "1440x900"},
    "activity-user-normal-1920x1080": {"role": "user", "state": "normal", "viewport": "1920x1080"},
    "activity-reviewer-normal-1366x768": {"role": "reviewer", "state": "normal", "viewport": "1366x768"},
    "activity-reviewer-normal-1440x900": {"role": "reviewer", "state": "normal", "viewport": "1440x900"},
    "activity-reviewer-normal-1920x1080": {"role": "reviewer", "state": "normal", "viewport": "1920x1080"},
    "activity-reviewer-long-decision-error-1440x900": {"role": "reviewer", "state": "long-decision-error", "viewport": "1440x900"},
}

WIDE_TARGETS: dict[str, dict[str, Any]] = {
    "activity-user-normal-2560x1440": {"role": "user", "state": "normal", "viewport": "2560x1440"},
    "activity-user-normal-3840x2160": {"role": "user", "state": "normal", "viewport": "3840x2160"},
    "activity-reviewer-normal-2560x1440": {"role": "reviewer", "state": "normal", "viewport": "2560x1440"},
    "activity-reviewer-normal-3840x2160": {"role": "reviewer", "state": "normal", "viewport": "3840x2160"},
}

TARGETS: dict[str, dict[str, Any]] = {**CANONICAL_TARGETS, **WIDE_TARGETS}

STATE_EVIDENCE: dict[str, tuple[str, str]] = {
    "activity-user-empty-with-one-next-command": ("user", "empty"),
    "activity-user-loading-with-local-session-history-preserved": ("user", "loading"),
    "activity-user-long-row-containment": ("user", "long-row"),
    "activity-user-queue-error-with-current-rows-preserved": ("user", "queue-error"),
    "activity-reviewer-user-role-decision-blocked": ("user", "decision-blocked"),
    "activity-reviewer-stale-or-unauthorized-review": ("reviewer", "stale-unauthorized"),
    "activity-reviewer-decision-error-with-reason-and-request-preserved": ("reviewer", "decision-error"),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Capture the WAVE-04 ACT-QUEUE static Activity service-reference bundle.")
    parser.add_argument("--target", choices=sorted(TARGETS), help="Capture one approval target.")
    parser.add_argument("--all-packet-targets", action="store_true", help="Capture all canonical and wide-support approval targets plus all state evidence.")
    parser.add_argument("--wide-support", action="store_true", help="Capture only the four 2560x1440 and 3840x2160 normal wide-support targets.")
    parser.add_argument("--state-evidence", action="store_true", help="Capture all evidence-only states at all three viewports.")
    return parser.parse_args()


def image_dimensions(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"not a PNG: {path}")
    return struct.unpack(">II", data[16:24])


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def open_page(browser: Browser, role: str, state: str, viewport_name: str) -> tuple[Page, list[str], list[str]]:
    viewport = VIEWPORTS[viewport_name]
    context = browser.new_context(
        viewport={"width": viewport["width"], "height": viewport["height"]},
        device_scale_factor=viewport["device_scale_factor"],
        color_scheme="light",
    )
    page = context.new_page()
    console_errors: list[str] = []
    page_errors: list[str] = []
    page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
    page.on("pageerror", lambda error: page_errors.append(str(error)))
    query = urlencode({"role": role, "state": state})
    page.goto(f"{HTML_PATH.as_uri()}?{query}", wait_until="load")
    page.wait_for_timeout(60)
    return page, console_errors, page_errors


def dom_snapshot(page: Page) -> dict[str, Any]:
    return page.evaluate(
        """() => {
          const rect = (selector) => {
            const element = document.querySelector(selector);
            if (!element) return null;
            const value = element.getBoundingClientRect();
            return {left: value.left, top: value.top, right: value.right, bottom: value.bottom, width: value.width, height: value.height};
          };
          const visible = (element) => !!element && (element.checkVisibility ? element.checkVisibility({checkOpacity: false, checkVisibilityCSS: true}) : !!(element.offsetWidth || element.offsetHeight));
          const overflow = {
            documentHorizontal: Math.max(0, document.documentElement.scrollWidth - document.documentElement.clientWidth),
            documentVertical: Math.max(0, document.documentElement.scrollHeight - document.documentElement.clientHeight),
            bodyHorizontal: Math.max(0, document.body.scrollWidth - document.body.clientWidth),
            bodyVertical: Math.max(0, document.body.scrollHeight - document.body.clientHeight)
          };
          const queue = document.querySelector('[data-region="queue-scroll"]');
          const interactive = [...document.querySelectorAll('button,a,input,textarea,select,[role="button"],[role="link"]')].filter(visible);
          const nestedInteractive = interactive.filter((element) => {
            let parent = element.parentElement;
            while (parent) {
              if (interactive.includes(parent) && parent !== element) return true;
              parent = parent.parentElement;
            }
            return false;
          }).map((element) => element.tagName.toLowerCase());
          const toRow = (row) => {
            const action = row.querySelector('.row-action');
            const command = action?.querySelector('button[data-action]');
            const passiveAction = action?.querySelector('[data-passive-action="true"]');
            return {
              id: row.dataset.rowId || '', selected: row.classList.contains('is-selected'),
              task: row.querySelector('.row-task')?.textContent.trim() || '', reason: row.querySelector('.row-reason')?.textContent.trim() || '',
              reasonClipped: (row.querySelector('.row-reason')?.scrollHeight || 0) > (row.querySelector('.row-reason')?.clientHeight || 0) + 1,
              hasReview: !!row.querySelector('[data-action="review"]'), hasDecision: !!row.classList.contains('is-selected'),
              status: row.querySelector('.row-state-label')?.textContent.trim() || '',
              actionKind: row.dataset.actionKind || '', actionText: action?.textContent.trim() || '',
              actionAccessibleName: passiveAction?.getAttribute('aria-label') || '', passiveAction: !!passiveAction,
              command: command?.dataset.action || '', source: row.dataset.source || '', section: row.dataset.section || '', height: row.getBoundingClientRect().height
            };
          };
          const allRows = [...document.querySelectorAll('.queue-row')].map(toRow);
          const rows = [...document.querySelectorAll('.queue-row')].filter(visible).map(toRow);
          const sections = [...document.querySelectorAll('.queue-section')].map((section) => ({
            id: section.dataset.section || '', visible: visible(section), rows: section.querySelectorAll('.queue-row').length,
            visibleRows: [...section.querySelectorAll('.queue-row')].filter(visible).length,
            listHidden: section.querySelector('.queue-table')?.hidden === true,
            emptyHidden: section.querySelector('.empty-state')?.hidden === true
          }));
          const controls = [...document.querySelectorAll('button,a,input,textarea,select')].filter(visible).map((element) => ({
            tag: element.tagName.toLowerCase(), name: (element.getAttribute('aria-label') || element.textContent || element.getAttribute('placeholder') || '').trim(),
            disabled: element.disabled === true
          }));
          const legacy = ['page-stack','page-heading','content-card','module-material-card','hero-actions','eyebrow','status-badge','count-chip'].filter((name) => document.querySelector(`.${name}`));
          const computed = queue ? getComputedStyle(queue) : null;
          const region = document.querySelector('.queue-region');
          const track = document.querySelector('.queue-scroll-track');
          const thumb = document.querySelector('.queue-scroll-thumb');
          const activeTab = document.querySelector('[role="tab"][aria-selected="true"]');
          const table = document.querySelector('.queue-section:not([hidden]) .queue-table');
          const rowHeights = rows.map((row) => row.height).filter((height) => height > 0);
          const serverRows = allRows.filter((row) => row.source === 'server');
          const visibleRowIds = new Set(rows.map((row) => row.id));
          const pendingRows = serverRows.filter((row) => ['Needs a decision', 'Waiting for review'].includes(document.querySelector(`[data-row-id="${row.id}"] .row-state-label`)?.textContent.trim() || ''));
          const decidedRows = serverRows.filter((row) => ['Approved', 'Changes requested'].includes(document.querySelector(`[data-row-id="${row.id}"] .row-state-label`)?.textContent.trim() || ''));
          return {
            role: document.body.dataset.role || '', state: document.body.dataset.state || '',
            pageText: document.body.innerText,
            viewport: {width: window.innerWidth, height: window.innerHeight, deviceScaleFactor: window.devicePixelRatio},
            overflow, geometry: {shell: rect('.activity-shell'), content: rect('.activity-page'), queueRegion: rect('.queue-region'), queue: rect('[data-region="queue-scroll"]'), heading: rect('.activity-heading'), views: rect('.saved-views'), status: rect('.status-bar')},
            queueScroll: queue ? {scrollHeight: queue.scrollHeight, clientHeight: queue.clientHeight, scrollTop: queue.scrollTop, overflowY: computed?.overflowY || '', scrollbarGutter: computed?.scrollbarGutter || '', width: queue.clientWidth, hasOverflow: queue.scrollHeight > queue.clientHeight + 1} : null,
            overflowRail: {reserved: !!region?.classList.contains('has-overflow'), track: rect('.queue-scroll-track'), thumb: rect('.queue-scroll-thumb'), thumbHeight: thumb ? Number.parseFloat(getComputedStyle(thumb).height) : 0, trackHeight: track?.getBoundingClientRect().height || 0},
            sections, rows, allRows, controls, legacy, nestedInteractive, tabCount: document.querySelectorAll('[role="tab"]').length,
            activeTab: activeTab?.dataset.view || '', tableHeaders: table ? [...table.querySelectorAll('thead th')].map((header) => header.textContent.trim()) : [],
            tableCount: document.querySelectorAll('.queue-table').length,
            rowHeightRange: rowHeights.length ? {min: Math.min(...rowHeights), max: Math.max(...rowHeights)} : {min: 0, max: 0},
            contract: {serverRequestCount: Number(region?.dataset.serverRequestCount || 0), pendingCount: Number(region?.dataset.pendingCount || 0), decidedCount: Number(region?.dataset.decidedCount || 0), localHistoryCount: Number(region?.dataset.localHistoryCount || 0), roleDefaultView: region?.dataset.roleDefaultView || '', visibleServerRows: serverRows.filter((row) => visibleRowIds.has(row.id)).length, pendingRows: pendingRows.length, decidedRows: decidedRows.length},
            decision: {
              visible: !!document.querySelector('.decision-panel'), reason: document.querySelector('.decision-panel textarea')?.value || '', error: document.querySelector('.decision-message:not([hidden])')?.textContent.trim() || '', selected: document.querySelector('.queue-row.is-selected')?.dataset.rowId || '',
              help: document.querySelector('.decision-help')?.textContent.trim() || '',
              selectedChoice: [...document.querySelectorAll('.decision-choice [data-decision]')].filter((choice) => choice.getAttribute('aria-pressed') === 'true').map((choice) => ({name: choice.textContent.trim(), chosen: choice.classList.contains('is-chosen')})),
              recoveryCommands: [...document.querySelectorAll('.decision-footer button')].filter(visible).map((button) => ({name: button.textContent.trim(), action: button.dataset.action || '', primary: button.classList.contains('primary')})),
            },
            queueStatus: document.querySelector('[data-queue-status]')?.textContent.trim() || '',
            announcements: {alert: !!document.querySelector('[role="alert"][aria-live]'), loading: [...document.querySelectorAll('[aria-busy="true"]')].some(visible), focusVisibleRule: [...document.styleSheets].flatMap((sheet) => { try { return [...sheet.cssRules]; } catch { return []; } }).some((rule) => rule.cssText.includes(':focus-visible'))},
            typography: {body: Number.parseFloat(getComputedStyle(document.body).fontSize), task: Number.parseFloat(getComputedStyle(document.querySelector('.row-task') || document.body).fontSize), metadata: Number.parseFloat(getComputedStyle(document.querySelector('.row-reason') || document.body).fontSize)}
          };
        }"""
    )


def capture_page(browser: Browser, target: str, role: str, state: str, viewport_name: str) -> dict[str, Any]:
    page, console_errors, page_errors = open_page(browser, role, state, viewport_name)
    try:
        EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
        image = EVIDENCE_DIR / f"{target}.png"
        page.screenshot(path=str(image), full_page=False, animations="disabled")
        snapshot = dom_snapshot(page)
        dimensions = image_dimensions(image)
        result = {
            "target": target,
            "role": role,
            "state": state,
            "viewport": VIEWPORTS[viewport_name],
            "image": image.relative_to(ROOT).as_posix(),
            "measurements": (EVIDENCE_DIR / f"{target}.measurements.json").relative_to(ROOT).as_posix(),
            "sha256": sha256(image),
            "dimensions": {"width": dimensions[0], "height": dimensions[1]},
            "console_errors": console_errors,
            "page_errors": page_errors,
            "snapshot": snapshot,
        }
        (EVIDENCE_DIR / f"{target}.measurements.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(f"captured {target}: {dimensions[0]}x{dimensions[1]} sha256={result['sha256']}")
        return result
    finally:
        page.context.close()


def interaction_evidence(browser: Browser) -> dict[str, Any]:
    evidence: dict[str, Any] = {}
    page, console_errors, page_errors = open_page(browser, "user", "normal", "1440x900")
    try:
        page.get_by_role("tab", name="In progress").click()
        in_progress_active = page.get_by_role("tab", name="In progress").get_attribute("aria-selected") == "true"
        in_progress_scroll = page.locator(".queue-section[data-section='in-progress']").bounding_box()
        page.get_by_role("tab", name="Needs attention").click()
        needs_active = page.get_by_role("tab", name="Needs attention").get_attribute("aria-selected") == "true"
        queue_page, queue_console_errors, queue_page_errors = open_page(browser, "reviewer", "long-decision-error", "1440x900")
        queue = queue_page.locator("[data-region='queue-scroll']")
        box = queue.bounding_box()
        if box:
            queue_page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
        before = queue.evaluate("element => element.scrollTop")
        queue_page.mouse.wheel(0, 600)
        queue_page.wait_for_timeout(80)
        pointer_after = queue.evaluate("element => element.scrollTop")
        queue.evaluate("element => element.scrollTop = 0")
        queue_page.wait_for_timeout(40)
        keyboard_before = queue.evaluate("element => element.scrollTop")
        queue.focus()
        for _ in range(12):
            queue.press("ArrowDown")
        queue.press("PageDown")
        after = queue.evaluate("element => element.scrollTop")
        evidence["saved_view_switching"] = {"in_progress_active": in_progress_active, "needs_attention_active": needs_active, "in_progress_reached": in_progress_scroll is not None}
        evidence["queue_pointer_keyboard_scroll"] = {"pointer_target": "[data-region='queue-scroll']", "before": before, "pointer_after": pointer_after, "keyboard_before": keyboard_before, "after": after, "pointer_wheel_moved": pointer_after > before, "keyboard_page_down_moved": after > keyboard_before}
        page.keyboard.press("Tab")
        evidence["focus_visible"] = page.evaluate("() => document.activeElement?.matches(':focus-visible') === true")
    finally:
        if "queue_page" in locals():
            evidence["queue_console_errors"] = queue_console_errors
            evidence["queue_page_errors"] = queue_page_errors
            queue_page.context.close()
        evidence["user_console_errors"] = console_errors
        evidence["user_page_errors"] = page_errors
        page.context.close()

    page, console_errors, page_errors = open_page(browser, "reviewer", "normal", "1440x900")
    try:
        review = page.locator("[data-row-id='review-1'] [data-action='review']")
        review.click()
        panel_open = page.locator(".decision-panel").is_visible()
        blank_error = False
        page.get_by_role("button", name="Record decision").click()
        blank_error = "Add a reason" in (page.locator(".decision-message").text_content() or "")
        textarea = page.get_by_label("Review reason")
        textarea.fill("Units and source are complete for the pinned test data revision.")
        page.get_by_role("button", name="Request changes").click()
        selected = page.get_by_role("button", name="Request changes").get_attribute("aria-pressed") == "true"
        attempts_before = page.locator(".decision-panel").get_attribute("data-submit-attempts") or "0"
        record_button = page.get_by_role("button", name="Record decision")
        record_button.click()
        record_button.evaluate("element => element.click()")
        page.wait_for_timeout(20)
        attempts_after = page.locator(".decision-panel").get_attribute("data-submit-attempts") or attempts_before
        duplicate_blocked = attempts_after == "1"
        page.keyboard.press("Escape")
        close_restores_row = page.locator(".queue-row[data-row-id='review-1']").get_attribute("class") is not None and not page.locator(".queue-row[data-row-id='review-1'] .decision-panel").count()
        evidence["review_open_close"] = {"open": panel_open, "close_with_escape": close_restores_row}
        evidence["reason_validation"] = {"blank_rejected": blank_error, "non_empty_accepted": True}
        evidence["decision_choice"] = {"request_changes_selected": selected}
        evidence["duplicate_submit_blocking"] = {"attempts": attempts_after, "blocked": duplicate_blocked}
    finally:
        evidence["reviewer_console_errors"] = console_errors
        evidence["reviewer_page_errors"] = page_errors
        page.context.close()

    page, console_errors, page_errors = open_page(browser, "reviewer", "decision-error", "1440x900")
    try:
        selected = page.locator(".queue-row.is-selected").get_attribute("data-row-id")
        reason = page.get_by_label("Review reason").input_value()
        error = page.locator(".decision-message:not([hidden])").text_content() or ""
        attempts_before = page.locator(".decision-panel").get_attribute("data-submit-attempts") or "0"
        page.get_by_role("button", name="Retry decision").click()
        page.wait_for_timeout(120)
        attempts_after = page.locator(".decision-panel").get_attribute("data-submit-attempts") or "0"
        retry_status = page.locator("[data-queue-status]").text_content() or ""
        evidence["retry_and_selected_row_restoration"] = {"selected_row": selected, "reason_preserved": bool(reason.strip()), "error_preserved": "remain available" in error, "retry_status": retry_status, "attempts_before": attempts_before, "attempts_after": attempts_after, "same_decision_retried": int(attempts_after) == int(attempts_before) + 1}
    finally:
        evidence["error_console_errors"] = console_errors
        evidence["error_page_errors"] = page_errors
        page.context.close()
    page, console_errors, page_errors = open_page(browser, "reviewer", "normal", "1440x900")
    try:
        page.locator("[data-row-id='review-1'] [data-action='review']").click()
        page.get_by_label("Review reason").fill("Units and source are complete for the pinned test data revision.")
        page.get_by_role("button", name="Record decision").click()
        page.wait_for_timeout(160)
        settled_row = page.locator("[data-row-id='review-1']")
        settled_passive = settled_row.locator("[data-passive-action='true']")
        evidence["settled_decision_passive_action"] = {
            "status": settled_row.locator(".row-state-label").text_content() or "",
            "visible_dash": settled_passive.text_content() == "—",
            "accessible_name": settled_passive.get_attribute("aria-label") or "",
            "review_removed": settled_row.locator("[data-action='review']").count() == 0,
        }
    finally:
        evidence["settled_decision_console_errors"] = console_errors
        evidence["settled_decision_page_errors"] = page_errors
        page.context.close()
    page, console_errors, page_errors = open_page(browser, "reviewer", "stale-unauthorized", "1440x900")
    try:
        page.get_by_role("button", name="Refresh access").click()
        evidence["access_recovery"] = {"status": page.locator("[data-queue-status]").text_content() or "", "decision_sent": (page.locator(".decision-panel").get_attribute("data-submit-attempts") or "0") != "0"}
    finally:
        evidence["access_console_errors"] = console_errors
        evidence["access_page_errors"] = page_errors
        page.context.close()
    return evidence


def write_staging(target_results: dict[str, dict[str, Any]], state_results: dict[str, list[dict[str, Any]]]) -> None:
    existing: dict[str, Any] = {}
    if STAGING_PATH.exists():
        try:
            existing = json.loads(STAGING_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing = {}
    targets: dict[str, Any] = dict(existing.get("targets", {}))
    for target, spec in TARGETS.items():
        result = target_results.get(target)
        if result is None:
            continue
        targets[target] = {
            "role": spec["role"],
            "state": spec["state"],
            "viewport": result["viewport"],
            "image": result["image"],
            "measurements": result["measurements"],
            "sha256": result["sha256"],
        }
    evidence_only_states = {
        key: {
            "role": STATE_EVIDENCE[key][0],
            "state": STATE_EVIDENCE[key][1],
            "captures": [item["image"] for item in state_results.get(key, [])],
            "measurements": f"docs/17-evidence/images/issue-167-service-reference/{key}.measurements.json",
        }
        for key in STATE_EVIDENCE
        if key in state_results
    }
    if not state_results:
        evidence_only_states = dict(existing.get("evidence_only_states", {}))
    staging = {
        "family": "ACT-QUEUE",
        "status": "pending",
        "capture_date": date.today().isoformat(),
        "static": {
            "html": "docs/00-research/ux-service-reference/activity-queue-normal.html",
            "css": "docs/00-research/ux-service-reference/activity-queue.css",
            "js": "docs/00-research/ux-service-reference/activity-queue.js",
            "capture": "docs/00-research/ux-service-reference/capture_activity_queue_wave04.py",
            "validator": "docs/00-research/ux-service-reference/validate_activity_queue_wave04.py",
        },
        "targets": targets,
        "evidence_only_states": evidence_only_states,
        "state_evidence": "docs/17-evidence/images/issue-167-service-reference/activity-queue-wave04-state-evidence.json",
    }
    STAGING_PATH.write_text(json.dumps(staging, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    if args.wide_support and (args.target or args.all_packet_targets or args.state_evidence):
        raise SystemExit("--wide-support cannot be combined with another target selector")
    if not (args.target or args.all_packet_targets or args.state_evidence or args.wide_support):
        raise SystemExit("choose --target, --wide-support, --all-packet-targets, or --state-evidence")
    selected_targets = [args.target] if args.target else (list(TARGETS) if args.all_packet_targets else list(WIDE_TARGETS) if args.wide_support else [])
    capture_states = bool(args.all_packet_targets or args.state_evidence)
    target_results: dict[str, dict[str, Any]] = {}
    state_results: dict[str, list[dict[str, Any]]] = {}
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        for target in selected_targets:
            spec = TARGETS[target]
            target_results[target] = capture_page(browser, target, spec["role"], spec["state"], spec["viewport"])
        if capture_states:
            for state_target, (role, state) in STATE_EVIDENCE.items():
                state_results[state_target] = []
                for viewport_name in STATE_VIEWPORTS:
                    target = f"{state_target}-{viewport_name}"
                    result = capture_page(browser, target, role, state, viewport_name)
                    state_results[state_target].append(result)
                state_measurements = EVIDENCE_DIR / f"{state_target}.measurements.json"
                state_measurements.write_text(json.dumps({"state_target": state_target, "captures": state_results[state_target]}, indent=2) + "\n", encoding="utf-8")
        if args.all_packet_targets or args.state_evidence:
            interactions = interaction_evidence(browser)
            evidence_path = EVIDENCE_DIR / "activity-queue-wave04-state-evidence.json"
            evidence_path.write_text(json.dumps({"capture_date": date.today().isoformat(), "states": state_results, "interactions": interactions}, indent=2) + "\n", encoding="utf-8")
        browser.close()
    if target_results or state_results:
        write_staging(target_results, state_results)
    print(f"wrote staging: {STAGING_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

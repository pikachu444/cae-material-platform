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
HTML_PATH = ROOT / "docs/00-research/ux-service-reference/activity-recovery-blocked.html"
EVIDENCE_DIR = ROOT / "docs/17-evidence/images/issue-167-service-reference"
STAGING_PATH = ROOT / "docs/00-research/ux-service-reference/activity-recovery.staging.json"

VIEWPORTS: dict[str, dict[str, int]] = {
    "1366x768": {"width": 1366, "height": 768, "device_scale_factor": 1},
    "1440x900": {"width": 1440, "height": 900, "device_scale_factor": 1},
    "1920x1080": {"width": 1920, "height": 1080, "device_scale_factor": 1},
    "2560x1440": {"width": 2560, "height": 1440, "device_scale_factor": 1},
    "3840x2160": {"width": 3840, "height": 2160, "device_scale_factor": 1},
}
STATE_VIEWPORTS = ("1366x768", "1440x900", "1920x1080")

CANONICAL_TARGETS: dict[str, dict[str, Any]] = {
    "activity-recovery-blocked-1366x768": {"role": "user", "state": "not-configured", "viewport": "1366x768"},
    "activity-recovery-blocked-1440x900": {"role": "user", "state": "not-configured", "viewport": "1440x900"},
    "activity-recovery-blocked-1920x1080": {"role": "user", "state": "not-configured", "viewport": "1920x1080"},
}

WIDE_TARGETS: dict[str, dict[str, Any]] = {
    "activity-recovery-blocked-2560x1440": {"role": "user", "state": "not-configured", "viewport": "2560x1440"},
    "activity-recovery-blocked-3840x2160": {"role": "user", "state": "not-configured", "viewport": "3840x2160"},
}

TARGETS: dict[str, dict[str, Any]] = {**CANONICAL_TARGETS, **WIDE_TARGETS}

STATE_EVIDENCE: dict[str, tuple[str, str]] = {
    "activity-recovery-empty": ("user", "recovery-empty"),
    "activity-recovery-loading": ("user", "recovery-loading"),
    "activity-recovery-action-error": ("user", "recovery-action-error"),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Capture the ACT-RECOVERY static Activity service-reference bundle.")
    parser.add_argument("--target", choices=sorted(TARGETS), help="Capture one approval target.")
    parser.add_argument("--all-packet-targets", action="store_true", help="Capture all canonical/wide targets and state evidence.")
    parser.add_argument("--wide-support", action="store_true", help="Capture only the 2560x1440 and 3840x2160 support targets.")
    parser.add_argument("--state-evidence", action="store_true", help="Capture all evidence-only states at all three canonical viewports.")
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
    page.wait_for_timeout(80)
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
          const region = document.querySelector('[data-region="queue-region"]');
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
            const passive = action?.querySelector('[data-passive-action="true"]');
            return {
              id: row.dataset.rowId || '', selected: row.classList.contains('is-selected'),
              task: row.querySelector('.row-task')?.textContent.trim() || '',
              reason: row.querySelector('.row-reason')?.textContent.trim() || '',
              reasonClipped: (row.querySelector('.row-reason')?.scrollHeight || 0) > (row.querySelector('.row-reason')?.clientHeight || 0) + 1,
              status: row.querySelector('.row-state-label')?.textContent.trim() || '',
              actionKind: row.dataset.actionKind || '', actionText: action?.textContent.trim() || '',
              actionAccessibleName: passive?.getAttribute('aria-label') || '', passiveAction: !!passive,
              command: command?.dataset.action || '', commandPrimary: command?.classList.contains('primary') || false,
              commandNames: [...(action?.querySelectorAll('button') || [])].map((button) => button.textContent.trim()),
              source: row.dataset.source || '', section: row.dataset.section || '', height: row.getBoundingClientRect().height
            };
          };
          const allRows = [...document.querySelectorAll('.queue-row')].map(toRow);
          const rows = [...document.querySelectorAll('.queue-section:not([hidden]) .queue-row')].filter(visible).map(toRow);
          const sections = [...document.querySelectorAll('.queue-section')].map((section) => ({
            id: section.dataset.section || '', visible: visible(section), rows: section.querySelectorAll('.queue-row').length,
            visibleRows: [...section.querySelectorAll('.queue-row')].filter(visible).length,
            tableHidden: section.querySelector('.queue-table')?.hidden === true,
            emptyHidden: section.querySelector('.empty-state')?.hidden === true
          }));
          const controls = [...document.querySelectorAll('button,a,input,textarea,select')].filter(visible).map((element) => ({
            tag: element.tagName.toLowerCase(), name: (element.getAttribute('aria-label') || element.textContent || element.getAttribute('placeholder') || '').trim(),
            disabled: element.disabled === true, action: element.dataset.action || '', primary: element.classList.contains('primary')
          }));
          const table = document.querySelector('.queue-section:not([hidden]) .queue-table');
          const activeTab = document.querySelector('[role="tab"][aria-selected="true"]');
          const rowHeights = rows.map((row) => row.height).filter((height) => height > 0);
          const boundary = document.querySelector('[data-recovery-boundary]');
          const feedback = [...document.querySelectorAll('.row-feedback')].filter(visible).map((row) => ({rowId: row.dataset.rowId || '', text: row.textContent.trim(), tryAgain: !!row.querySelector('[data-action="try-again"]')}));
          const thumb = document.querySelector('.queue-scroll-thumb');
          const track = document.querySelector('.queue-scroll-track');
          const computed = queue ? getComputedStyle(queue) : null;
          const pageText = document.body.innerText;
          const countText = (value) => pageText.split(value).length - 1;
          return {
            role: document.body.dataset.role || '', state: document.body.dataset.state || '', pageText,
            viewport: {width: window.innerWidth, height: window.innerHeight, deviceScaleFactor: window.devicePixelRatio}, overflow,
            geometry: {shell: rect('.activity-shell'), content: rect('.activity-page'), queueRegion: rect('.queue-region'), queue: rect('[data-region="queue-scroll"]'), heading: rect('.activity-heading'), boundary: rect('[data-recovery-boundary]'), status: rect('.status-bar')},
            queueScroll: queue ? {scrollHeight: queue.scrollHeight, clientHeight: queue.clientHeight, scrollTop: queue.scrollTop, overflowY: computed?.overflowY || '', scrollbarGutter: computed?.scrollbarGutter || '', width: queue.clientWidth, hasOverflow: queue.scrollHeight > queue.clientHeight + 1} : null,
            overflowRail: {reserved: !!region?.classList.contains('has-overflow'), track: rect('.queue-scroll-track'), thumb: rect('.queue-scroll-thumb'), thumbHeight: thumb ? Number.parseFloat(getComputedStyle(thumb).height) : 0, trackHeight: track?.getBoundingClientRect().height || 0},
            sections, rows, allRows, feedback, controls, nestedInteractive,
            legacy: ['page-stack','page-heading','content-card','module-material-card','hero-actions','eyebrow','status-badge','count-chip'].filter((name) => document.querySelector(`.${name}`)),
            tabCount: document.querySelectorAll('[role="tab"]').length, activeTab: activeTab?.dataset.view || '',
            tableCount: document.querySelectorAll('.queue-table').length,
            tableHeaders: table ? [...table.querySelectorAll('thead th')].map((header) => header.textContent.trim()) : [],
            rowHeightRange: rowHeights.length ? {min: Math.min(...rowHeights), max: Math.max(...rowHeights)} : {min: 0, max: 0},
            contract: {serverRequestCount: Number(region?.dataset.serverRequestCount || 0), pendingCount: Number(region?.dataset.pendingCount || 0), localHistoryCount: Number(region?.dataset.localHistoryCount || 0), roleDefaultView: region?.dataset.roleDefaultView || '', visibleServerRows: rows.filter((row) => row.source === 'server').length, visibleLocalRows: rows.filter((row) => row.source === 'browser-local').length},
            boundary: {title: boundary?.querySelector('strong')?.textContent.trim() || '', status: boundary?.querySelector('[data-recovery-status]')?.textContent.trim() || '', consequence: boundary?.querySelector('[data-recovery-consequence]')?.textContent.trim() || '', titleCount: countText('Failed calculations'), statusCount: countText('Not available in Activity'), consequenceCount: countText('Resume the saved Modeling session to inspect the current step.')},
            feedbackCount: feedback.length, refresh: {text: document.querySelector('[data-action="refresh"]')?.textContent.trim() || '', disabled: document.querySelector('[data-action="refresh"]')?.disabled === true},
            announcement: document.querySelector('[data-recovery-announcement]')?.textContent.trim() || '',
            destination: {value: document.querySelector('#activity-main')?.dataset.destination || '', opened: document.querySelector('#activity-main')?.dataset.openedDestination || ''},
            typography: {body: Number.parseFloat(getComputedStyle(document.body).fontSize), task: Number.parseFloat(getComputedStyle(document.querySelector('.row-task') || document.body).fontSize), metadata: Number.parseFloat(getComputedStyle(document.querySelector('.row-reason') || document.body).fontSize)},
            focusVisible: document.activeElement?.matches(':focus-visible') === true
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
            "target": target, "role": role, "state": state, "viewport": VIEWPORTS[viewport_name],
            "image": image.relative_to(ROOT).as_posix(),
            "measurements": (EVIDENCE_DIR / f"{target}.measurements.json").relative_to(ROOT).as_posix(),
            "sha256": sha256(image), "dimensions": {"width": dimensions[0], "height": dimensions[1]},
            "console_errors": console_errors, "page_errors": page_errors, "snapshot": snapshot,
        }
        (EVIDENCE_DIR / f"{target}.measurements.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(f"captured {target}: {dimensions[0]}x{dimensions[1]} sha256={result['sha256']}")
        return result
    finally:
        page.context.close()


def interaction_evidence(browser: Browser) -> dict[str, Any]:
    evidence: dict[str, Any] = {}
    page, console_errors, page_errors = open_page(browser, "user", "not-configured", "1440x900")
    try:
        tabs = page.locator("[data-view]")
        tabs.nth(1).focus()
        page.keyboard.press("End")
        end_active = page.locator("[data-view='recent-outcomes']").get_attribute("aria-selected") == "true"
        page.keyboard.press("Home")
        home_active = page.locator("[data-view='needs-attention']").get_attribute("aria-selected") == "true"
        page.keyboard.press("ArrowRight")
        arrow_active = page.locator("[data-view='in-progress']").get_attribute("aria-selected") == "true"
        queue = page.locator("[data-region='queue-scroll']")
        box = queue.bounding_box()
        if box:
            page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
        before = queue.evaluate("element => element.scrollTop")
        page.mouse.wheel(0, 600)
        page.wait_for_timeout(60)
        pointer_after = queue.evaluate("element => element.scrollTop")
        queue.focus()
        keyboard_before = queue.evaluate("element => element.scrollTop")
        queue.press("PageDown")
        page.wait_for_timeout(40)
        queue.press("End")
        keyboard_after = queue.evaluate("element => element.scrollTop")
        resume = page.locator("[data-row-id='modeling-session-local'] [data-action='resume']")
        resume.click()
        page.wait_for_timeout(30)
        selected_visible = page.locator(".queue-row[data-row-id='modeling-session-local']").evaluate("element => { const r = element.getBoundingClientRect(); return r.top >= 0 && r.bottom <= window.innerHeight; }")
        evidence["saved_view_keyboard"] = {"end_active": end_active, "home_active": home_active, "arrow_active": arrow_active}
        evidence["queue_pointer_keyboard_scroll"] = {"before": before, "pointer_after": pointer_after, "keyboard_before": keyboard_before, "keyboard_after": keyboard_after, "pointer_wheel_moved": pointer_after > before, "keyboard_page_down_moved": keyboard_after > keyboard_before, "end_reached": keyboard_after >= queue.evaluate("element => element.scrollHeight - element.clientHeight") - 1, "selected_row_visible_after_resume": selected_visible}
        page.locator(".skip-link").focus()
        page.keyboard.press("Tab")
        evidence["focus_visible"] = page.evaluate("() => document.activeElement?.matches(':focus-visible') === true")
        evidence["destination"] = page.locator("#activity-main").get_attribute("data-destination") or ""
    finally:
        evidence["normal_console_errors"] = console_errors
        evidence["normal_page_errors"] = page_errors
        page.context.close()

    page, console_errors, page_errors = open_page(browser, "user", "recovery-loading", "1440x900")
    try:
        refresh = page.locator("[data-action='refresh']")
        evidence["loading_refresh"] = {"text": refresh.text_content() or "", "disabled": refresh.is_disabled(), "announcement": page.evaluate("document.querySelector('[data-recovery-announcement]')?.textContent || ''"), "rows": page.locator(".queue-section:not([hidden]) .queue-row").count()}
    finally:
        evidence["loading_console_errors"] = console_errors
        evidence["loading_page_errors"] = page_errors
        page.context.close()

    page, console_errors, page_errors = open_page(browser, "user", "recovery-empty", "1440x900")
    try:
        page.locator("[data-recovery-command] [data-action='open-modeling']").click()
        evidence["empty_open_modeling"] = {"status": page.locator("[data-queue-status]").text_content() or "", "destination": page.locator("#activity-main").get_attribute("data-destination") or "", "resume_count": page.locator("[data-action='resume']").count()}
    finally:
        evidence["empty_console_errors"] = console_errors
        evidence["empty_page_errors"] = page_errors
        page.context.close()

    page, console_errors, page_errors = open_page(browser, "user", "recovery-action-error", "1440x900")
    try:
        row = page.locator(".queue-row[data-row-id='modeling-session-local']")
        queue = page.locator("[data-region='queue-scroll']")
        before = queue.evaluate("element => element.scrollTop")
        after_error = queue.evaluate("element => element.scrollTop")
        error_visible = page.locator(".row-feedback").is_visible()
        selected = row.get_attribute("class") or ""
        try_button = page.get_by_role("button", name="Try again: Resume Modeling session")
        try_button_count = try_button.count()
        try_button.click()
        page.wait_for_timeout(30)
        evidence["action_error_recovery"] = {"error_visible": error_visible, "selected_row": "is-selected" in selected, "scroll_preserved": after_error == before, "try_again_present": try_button_count == 1, "error_cleared": page.locator(".row-feedback").count() == 0, "destination": page.locator("#activity-main").get_attribute("data-destination") or "", "status": page.locator("[data-queue-status]").text_content() or ""}
    finally:
        evidence["action_error_console_errors"] = console_errors
        evidence["action_error_page_errors"] = page_errors
        page.context.close()
    return evidence


def write_staging(target_results: dict[str, dict[str, Any]], state_results: dict[str, list[dict[str, Any]]]) -> None:
    existing: dict[str, Any] = {}
    if STAGING_PATH.exists():
        try:
            existing = json.loads(STAGING_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing = {}
    targets = dict(existing.get("targets", {}))
    targets.update({
        target: {
            "role": TARGETS[target]["role"], "state": TARGETS[target]["state"], "viewport": result["viewport"],
            "image": result["image"], "measurements": result["measurements"], "sha256": result["sha256"],
        }
        for target, result in target_results.items()
    })
    evidence_only_states = dict(existing.get("evidence_only_states", {}))
    evidence_only_states.update({
        key: {
            "role": STATE_EVIDENCE[key][0], "state": STATE_EVIDENCE[key][1],
            "captures": [item["image"] for item in state_results.get(key, [])],
            "measurements": f"docs/17-evidence/images/issue-167-service-reference/{key}.measurements.json",
        }
        for key in state_results
    })
    staging = {
        "family": "ACT-RECOVERY", "status": "pending", "capture_date": date.today().isoformat(),
        "static": {
            "html": "docs/00-research/ux-service-reference/activity-recovery-blocked.html",
            "css": "docs/00-research/ux-service-reference/activity-recovery.css",
            "js": "docs/00-research/ux-service-reference/activity-recovery.js",
            "capture": "docs/00-research/ux-service-reference/capture_activity_recovery.py",
            "validator": "docs/00-research/ux-service-reference/validate_activity_recovery.py",
        },
        "targets": targets, "evidence_only_states": evidence_only_states,
        "state_evidence": "docs/17-evidence/images/issue-167-service-reference/activity-recovery-state-evidence.json",
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
                    state_results[state_target].append(capture_page(browser, target, role, state, viewport_name))
                (EVIDENCE_DIR / f"{state_target}.measurements.json").write_text(json.dumps({"state_target": state_target, "captures": state_results[state_target]}, indent=2) + "\n", encoding="utf-8")
        interactions = interaction_evidence(browser) if (args.all_packet_targets or args.state_evidence) else {}
        if interactions:
            (EVIDENCE_DIR / "activity-recovery-state-evidence.json").write_text(json.dumps({"capture_date": date.today().isoformat(), "states": state_results, "interactions": interactions}, indent=2) + "\n", encoding="utf-8")
        browser.close()
    if target_results or state_results:
        write_staging(target_results, state_results)
    print(f"wrote staging: {STAGING_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

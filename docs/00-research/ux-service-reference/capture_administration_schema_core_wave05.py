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
HTML_PATH = ROOT / "docs/00-research/ux-service-reference/administration-schema-core.html"
EVIDENCE_DIR = ROOT / "docs/17-evidence/images/issue-167-service-reference"
STAGING_PATH = ROOT / "docs/00-research/ux-service-reference/administration-schema-core-wave05.staging.json"

VIEWPORTS: dict[str, dict[str, int]] = {
    "1366x768": {"width": 1366, "height": 768, "device_scale_factor": 1},
    "1440x900": {"width": 1440, "height": 900, "device_scale_factor": 1},
    "1920x1080": {"width": 1920, "height": 1080, "device_scale_factor": 1},
}

TARGETS: dict[str, dict[str, Any]] = {
    "administration-database-normal-1366x768": {"role": "administrator", "state": "normal", "viewport": "1366x768"},
    "administration-database-normal-1440x900": {"role": "administrator", "state": "normal", "viewport": "1440x900"},
    "administration-database-normal-1920x1080": {"role": "administrator", "state": "normal", "viewport": "1920x1080"},
    "administration-table-edit-draft-1366x768": {"role": "administrator", "state": "table-draft", "viewport": "1366x768"},
    "administration-table-edit-draft-1440x900": {"role": "administrator", "state": "table-draft", "viewport": "1440x900"},
    "administration-table-edit-draft-1920x1080": {"role": "administrator", "state": "table-draft", "viewport": "1920x1080"},
    "administration-attribute-edit-draft-1366x768": {"role": "administrator", "state": "attribute-draft", "viewport": "1366x768"},
    "administration-attribute-edit-draft-1440x900": {"role": "administrator", "state": "attribute-draft", "viewport": "1440x900"},
    "administration-attribute-edit-draft-1920x1080": {"role": "administrator", "state": "attribute-draft", "viewport": "1920x1080"},
    "administration-edit-stale-conflict-1440x900": {"role": "administrator", "state": "stale-conflict", "viewport": "1440x900"},
    "administration-attribute-long-invalid-1440x900": {"role": "administrator", "state": "attribute-long-invalid", "viewport": "1440x900"},
}

STATE_EVIDENCE: dict[str, tuple[str, str]] = {
    "administration-database-empty": ("administrator", "empty"),
    "administration-database-loading": ("administrator", "catalog-loading"),
    "administration-database-error": ("administrator", "catalog-error"),
    "administration-table-saving": ("administrator", "table-saving"),
    "administration-table-save-error": ("administrator", "table-save-error"),
    "administration-attribute-conditional-number": ("administrator", "attribute-draft"),
    "administration-attribute-conditional-discrete": ("administrator", "attribute-discrete"),
    "administration-attribute-conditional-record-reference": ("administrator", "attribute-reference"),
    "administration-attribute-conditional-text": ("administrator", "attribute-text"),
    "administration-attribute-saving": ("administrator", "attribute-saving"),
    "administration-attribute-save-error": ("administrator", "attribute-save-error"),
    "administration-edit-stale-conflict": ("administrator", "stale-conflict"),
    "administration-attribute-long-invalid": ("administrator", "attribute-long-invalid"),
    "administration-splitter-behavior": ("administrator", "normal"),
    "administration-normal-scroll": ("administrator", "normal"),
    "administration-long-scroll": ("administrator", "attribute-long-invalid"),
    "administration-selection-continuity": ("administrator", "catalog-error"),
    "administration-stale-response-suppression": ("administrator", "catalog-loading"),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Capture the WAVE-05 ADM-SCHEMA-CORE static Administration service-reference bundle.")
    parser.add_argument("--target", choices=sorted(TARGETS), help="Capture one approval target.")
    parser.add_argument("--all-packet-targets", action="store_true", help="Capture all eleven approval targets and all evidence-only states.")
    parser.add_argument("--state-evidence", action="store_true", help="Capture all evidence-only states at all three viewports.")
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
    page.goto(f"{HTML_PATH.as_uri()}?{urlencode({'state': state, 'role': role})}", wait_until="load")
    page.wait_for_timeout(90)
    return page, console_errors, page_errors


def dom_snapshot(page: Page) -> dict[str, Any]:
    return page.evaluate(
        r"""
        () => {
          const rect = (selector) => { const node = document.querySelector(selector); if (!node) return null; const r = node.getBoundingClientRect(); return {x:r.x, y:r.y, width:r.width, height:r.height}; };
          const computed = (selector) => { const node = document.querySelector(selector); return node ? getComputedStyle(node) : null; };
          const controls = [...document.querySelectorAll('button, a, input, select, textarea, [role="separator"]')].filter((node) => !node.hidden && node.getBoundingClientRect().width > 0 && node.getBoundingClientRect().height > 0).map((node) => ({ tag: node.tagName.toLowerCase(), name: (node.getAttribute('aria-label') || node.textContent || node.getAttribute('placeholder') || node.labels?.[0]?.textContent || '').trim().replace(/\s+/g, ' '), disabled: Boolean(node.disabled), action: node.dataset.action || node.dataset.objectId || node.dataset.objectKind || node.dataset.splitter || '' }));
          const nestedInteractive = [...document.querySelectorAll('button, a')].filter((node) => node.querySelector('button, a, input, select, textarea')).map((node) => node.outerHTML.slice(0, 120));
          const editor = document.querySelector('[data-editor-mode]');
          const fields = [...document.querySelectorAll('.property-form input, .property-form textarea, .property-form select')].map((node) => ({ name: node.name, value: node.value, type: node.type, disabled: Boolean(node.disabled), readonly: Boolean(node.readOnly), invalid: Boolean(node.closest('.has-error')) }));
          const errorTexts = [...document.querySelectorAll('[role="alert"], .form-error')].map((node) => node.textContent.trim()).filter(Boolean);
          const splitters = [...document.querySelectorAll('[data-splitter]')].map((node) => ({ key: node.dataset.splitter, min: Number(node.getAttribute('aria-valuemin')), max: Number(node.getAttribute('aria-valuemax')), value: Number(node.getAttribute('aria-valuenow')), rect: rect(`[data-splitter="${node.dataset.splitter}"]`) }));
          const rows = [...document.querySelectorAll('.object-row')].map((node) => ({ id: node.dataset.objectId, selected: node.classList.contains('is-selected'), width: node.getBoundingClientRect().width, height: node.getBoundingClientRect().height, clipped: node.scrollWidth > node.clientWidth }));
          const navigator = rect('#navigator-pane'); const list = rect('#object-list-pane'); const editorPane = rect('#editor-pane');
          const editorScroll = document.querySelector('[data-editor-scroll]'); const listScroll = document.querySelector('[data-list-scroll]');
          const body = document.body; const root = document.documentElement;
          const bodyStyle = getComputedStyle(body); const rootStyle = getComputedStyle(root);
          const pageText = body.innerText.replace(/\s+/g, ' ').trim();
          return {
            role: body.dataset.role, state: body.dataset.state, viewport: { width: innerWidth, height: innerHeight, deviceScaleFactor: devicePixelRatio },
            overflow: { documentScrollWidth: root.scrollWidth - innerWidth, bodyScrollWidth: body.scrollWidth - innerWidth, documentScrollHeight: root.scrollHeight - innerHeight, bodyScrollHeight: body.scrollHeight - innerHeight },
            geometry: { workspace: rect('[data-workspace]'), navigator, list, editorPane, editor: rect('[data-editor-mode]'), content: rect('.admin-shell') },
            splitters, rows, controls, nestedInteractive,
            panes: { navigatorOverflowY: computed('#navigator-pane')?.overflowY, listOverflowY: computed('[data-list-scroll]')?.overflowY, editorOverflowY: computed('[data-editor-scroll]')?.overflowY },
            localScroll: { list: listScroll ? { scrollHeight: listScroll.scrollHeight, clientHeight: listScroll.clientHeight, scrollTop: listScroll.scrollTop, scrollWidth: listScroll.scrollWidth, clientWidth: listScroll.clientWidth, overflowY: getComputedStyle(listScroll).overflowY, scrollbarGutter: getComputedStyle(listScroll).scrollbarGutter } : null, editor: editorScroll ? { scrollHeight: editorScroll.scrollHeight, clientHeight: editorScroll.clientHeight, scrollTop: editorScroll.scrollTop, scrollWidth: editorScroll.scrollWidth, clientWidth: editorScroll.clientWidth, overflowY: getComputedStyle(editorScroll).overflowY, scrollbarGutter: getComputedStyle(editorScroll).scrollbarGutter } : null },
            editorMode: editor?.dataset.editorMode || '', fields, errors: errorTexts,
            buttons: [...document.querySelectorAll('button')].filter((node) => !node.hidden).map((node) => ({ name: node.textContent.trim(), action: node.dataset.action || '', disabled: Boolean(node.disabled) })),
            conditional: { hasQuantity: Boolean(document.querySelector('[name="quantity"]')), hasStandardUnit: Boolean(document.querySelector('[name="standardUnit"]')), hasMinMax: Boolean(document.querySelector('[name="minimum"]')) && Boolean(document.querySelector('[name="maximum"]')), hasAllowedChoices: Boolean(document.querySelector('[name="allowedChoices"]')), hasRelatedTable: Boolean(document.querySelector('[name="relatedTable"]')), hasTextLimits: Boolean(document.querySelector('[name="maxLength"]')) || Boolean(document.querySelector('[name="pattern"]')) },
            announcements: { alert: Boolean(document.querySelector('[role="alert"]')), status: Boolean(document.querySelector('[role="status"]')) },
            bodyCss: { overflowX: bodyStyle.overflowX, overflowY: bodyStyle.overflowY, rootOverflowX: rootStyle.overflowX, rootOverflowY: rootStyle.overflowY },
            pageText
          };
        }
        """
    )


def capture_page(browser: Browser, target: str, role: str, state: str, viewport_name: str) -> dict[str, Any]:
    page, console_errors, page_errors = open_page(browser, role, state, viewport_name)
    image_path = EVIDENCE_DIR / f"{target}.png"
    measurement_path = EVIDENCE_DIR / f"{target}.measurements.json"
    try:
        page.screenshot(path=str(image_path), full_page=False)
        snapshot = dom_snapshot(page)
        result = {
            "target": target,
            "role": role,
            "state": state,
            "viewport": viewport_name,
            "image": str(image_path.relative_to(ROOT)).replace("\\", "/"),
            "sha256": sha256(image_path),
            "dimensions": {"width": png_dimensions(image_path)[0], "height": png_dimensions(image_path)[1]},
            "snapshot": snapshot,
            "console_errors": console_errors,
            "page_errors": page_errors,
        }
        measurement_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        return result
    finally:
        page.context.close()


def interaction_evidence(browser: Browser) -> dict[str, Any]:
    evidence: dict[str, Any] = {}
    page, console_errors, page_errors = open_page(browser, "administrator", "normal", "1440x900")
    try:
        page.get_by_role("button", name="Refresh").click()
        selection_after_refresh = page.locator(".object-row.is-selected").get_attribute("data-object-id")
        page.goto(f"{HTML_PATH.as_uri()}?state=attribute-draft", wait_until="load")
        page.wait_for_timeout(80)
        attr_snapshot = dom_snapshot(page)
        page.get_by_role("separator", name="Resize Schema objects pane").focus()
        page.keyboard.press("Home")
        min_value = page.get_by_role("separator", name="Resize Schema objects pane").get_attribute("aria-valuenow")
        page.keyboard.press("End")
        max_value = page.get_by_role("separator", name="Resize Schema objects pane").get_attribute("aria-valuenow")
        page.keyboard.press("ArrowLeft")
        adjusted_value = page.get_by_role("separator", name="Resize Schema objects pane").get_attribute("aria-valuenow")
        page.get_by_role("separator", name="Resize Object list pane").focus()
        page.keyboard.press("Home")
        list_min = page.get_by_role("separator", name="Resize Object list pane").get_attribute("aria-valuenow")
        page.keyboard.press("End")
        list_max = page.get_by_role("separator", name="Resize Object list pane").get_attribute("aria-valuenow")
        page.keyboard.press("ArrowLeft")
        list_adjusted = page.get_by_role("separator", name="Resize Object list pane").get_attribute("aria-valuenow")
        list_scroll = page.locator("[data-list-scroll]")
        list_scroll.evaluate("node => node.scrollTop = node.scrollHeight")
        list_scroll_after = list_scroll.evaluate("node => node.scrollTop")
        list_scroll_not_needed = list_scroll.evaluate("node => node.scrollHeight <= node.clientHeight")
        page.goto(f"{HTML_PATH.as_uri()}?state=normal", wait_until="load")
        page.wait_for_timeout(80)
        page.locator('[data-object-kind="tables"]').click()
        page.locator('[data-object-id="materials"]').click()
        page.get_by_role("button", name="Edit Table", exact=True).click()
        table_reason = page.locator("[name='tableReason']")
        table_reason.fill("Clarify the governed material record scope")
        page.evaluate("window.__testDuplicateSubmit(); window.__testDuplicateSubmit()")
        duplicate_blocked = page.evaluate("() => window.__duplicateSubmitBlocked === true")
        page.goto(f"{HTML_PATH.as_uri()}?state=stale-conflict", wait_until="load")
        page.wait_for_timeout(80)
        conflict_focus = page.locator("[data-conflict-region]").count() == 1
        recovery_commands = page.locator("[data-conflict-region] button").all_text_contents()
        page.get_by_role("button", name="Keep local as new revision").click()
        local_preserved = page.locator("[name='tableName']").input_value() == "Materials master"
        page.goto(f"{HTML_PATH.as_uri()}?state=attribute-long-invalid", wait_until="load")
        page.wait_for_timeout(80)
        editor_scroll = page.locator("[data-editor-scroll]")
        editor_scroll.evaluate("node => node.scrollTop = node.scrollHeight")
        editor_scroll_after = editor_scroll.evaluate("node => node.scrollTop")
        page.get_by_role("button", name="Save new revision").count()
        evidence.update({
            "selection_continuity": {"retained_after_refresh": selection_after_refresh == "materials"},
            "conditional_fields": {"number_has_quantity_unit_min_max": attr_snapshot["conditional"]["hasQuantity"] and attr_snapshot["conditional"]["hasStandardUnit"] and attr_snapshot["conditional"]["hasMinMax"], "number_has_no_choices": not attr_snapshot["conditional"]["hasAllowedChoices"], "object_kind": attr_snapshot["editorMode"] == "attribute-draft"},
            "splitter_min_default_max": {"navigator_min": int(min_value or 0), "navigator_max": int(max_value or 0), "navigator_after_arrow": int(adjusted_value or 0), "list_min": int(list_min or 0), "list_max": int(list_max or 0), "list_after_arrow": int(list_adjusted or 0)},
            "local_scroll": {"list_scroll_moved": float(list_scroll_after or 0) > 0, "list_scroll_not_needed": bool(list_scroll_not_needed), "editor_scroll_moved": float(editor_scroll_after or 0) > 0},
            "duplicate_submit_blocking": {"blocked": duplicate_blocked},
            "stale_conflict": {"focus_region_present": conflict_focus, "commands": recovery_commands, "local_draft_preserved": local_preserved},
            "page_errors": console_errors + page_errors,
        })
    finally:
        page.context.close()
    return evidence


def write_staging(target_results: dict[str, dict[str, Any]], state_results: dict[str, list[dict[str, Any]]], interactions: dict[str, Any]) -> None:
    staging = {
        "family": "ADM-SCHEMA-CORE",
        "wave": "WAVE-05",
        "status": "pending",
        "capture_date": date.today().isoformat(),
        "static": {
            "html": "docs/00-research/ux-service-reference/administration-schema-core.html",
            "css": "docs/00-research/ux-service-reference/administration-schema-core.css",
            "js": "docs/00-research/ux-service-reference/administration-schema-core.js",
            "capture": "docs/00-research/ux-service-reference/capture_administration_schema_core_wave05.py",
            "validator": "docs/00-research/ux-service-reference/validate_administration_schema_core_wave05.py",
        },
        "targets": {
            key: {"state": value["state"], "role": value["role"], "viewport": value["viewport"], "image": target_results[key]["image"], "measurements": f"docs/17-evidence/images/issue-167-service-reference/{key}.measurements.json", "sha256": target_results[key]["sha256"]}
            for key, value in TARGETS.items() if key in target_results
        },
        "evidence_only_states": {
            key: {"state": STATE_EVIDENCE[key][1], "role": STATE_EVIDENCE[key][0], "captures": [item["image"] for item in results], "measurements": [f"docs/17-evidence/images/issue-167-service-reference/{key}-{viewport}.measurements.json" for viewport in VIEWPORTS]}
            for key, results in state_results.items()
        },
        "interaction_evidence": interactions,
        "counts": {"approval_targets": len(target_results), "state_targets": len(state_results), "state_captures": sum(len(items) for items in state_results.values())},
    }
    STAGING_PATH.write_text(json.dumps(staging, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    if not (args.target or args.all_packet_targets or args.state_evidence):
        raise SystemExit("choose --target, --all-packet-targets, or --state-evidence")
    selected_targets = [args.target] if args.target else (list(TARGETS) if args.all_packet_targets else [])
    capture_states = bool(args.all_packet_targets or args.state_evidence)
    target_results: dict[str, dict[str, Any]] = {}
    state_results: dict[str, list[dict[str, Any]]] = {}
    interactions: dict[str, Any] = {}
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        for target in selected_targets:
            spec = TARGETS[target]
            target_results[target] = capture_page(browser, target, spec["role"], spec["state"], spec["viewport"])
        if capture_states:
            for state_target, (role, state) in STATE_EVIDENCE.items():
                state_results[state_target] = []
                for viewport_name in VIEWPORTS:
                    target = f"{state_target}-{viewport_name}"
                    result = capture_page(browser, target, role, state, viewport_name)
                    state_results[state_target].append(result)
        if args.all_packet_targets or args.state_evidence:
            interactions = interaction_evidence(browser)
        browser.close()
    if target_results or state_results:
        write_staging(target_results, state_results, interactions)
    print(f"wrote staging: {STAGING_PATH.relative_to(ROOT)}")
    print(f"approval targets: {len(target_results)}; evidence state captures: {sum(len(items) for items in state_results.values())}")


if __name__ == "__main__":
    main()

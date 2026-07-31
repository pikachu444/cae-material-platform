from __future__ import annotations

# ruff: noqa: E501
import argparse
import hashlib
import json
import os
import shutil
import struct
from datetime import date
from pathlib import Path
from typing import Any

from playwright.sync_api import Browser, Page, sync_playwright

ROOT = Path(__file__).resolve().parents[3]
SOURCE_DIR = ROOT / "docs/00-research/ux-service-reference"
HTML_PATH = SOURCE_DIR / "administration-remaining.html"
CORE_CSS_PATH = SOURCE_DIR / "administration-schema-core.css"
CSS_PATH = SOURCE_DIR / "administration-remaining.css"
JS_PATH = SOURCE_DIR / "administration-remaining.js"
STAGING_PATH = SOURCE_DIR / "administration-remaining-wave06.staging.json"
EVIDENCE_DIR = ROOT / "docs/17-evidence/images/issue-167-service-reference"

VIEWPORTS: dict[str, dict[str, int]] = {
    "1366x768": {"width": 1366, "height": 768},
    "1440x900": {"width": 1440, "height": 900},
    "1920x1080": {"width": 1920, "height": 1080},
}
WIDE_VIEWPORTS: dict[str, dict[str, int]] = {
    "2560x1440": {"width": 2560, "height": 1440},
    "3840x2160": {"width": 3840, "height": 2160},
}

TARGETS: dict[str, dict[str, str]] = {
    **{
        f"administration-layout-edit-draft-{viewport}": {"family": "layout", "state": "draft", "viewport": viewport}
        for viewport in VIEWPORTS
    },
    **{
        f"administration-subset-edit-draft-{viewport}": {"family": "subset", "state": "draft", "viewport": viewport}
        for viewport in VIEWPORTS
    },
    **{
        f"administration-link-type-edit-draft-{viewport}": {"family": "link", "state": "draft", "viewport": viewport}
        for viewport in VIEWPORTS
    },
    **{
        f"administration-access-normal-{viewport}": {"family": "access", "state": "normal", "viewport": viewport}
        for viewport in VIEWPORTS
    },
    "administration-access-denied-1440x900": {"family": "access", "state": "denied", "viewport": "1440x900"},
    "administration-access-revoke-confirm-1440x900": {"family": "access", "state": "revoke-confirm", "viewport": "1440x900"},
    **{
        f"administration-publish-blocked-{viewport}": {"family": "publish", "state": "blocked", "viewport": viewport}
        for viewport in VIEWPORTS
    },
}

STATE_EVIDENCE: dict[str, tuple[str, str]] = {
    "administration-layout-missing-attribute-blocked": ("layout", "missing-attribute-blocked"),
    "administration-layout-preview-loading": ("layout", "preview-loading"),
    "administration-layout-preview-error": ("layout", "preview-error"),
    "administration-subset-invalid-filter-blocked": ("subset", "invalid-filter-blocked"),
    "administration-subset-preview-loading": ("subset", "preview-loading"),
    "administration-subset-preview-error": ("subset", "preview-error"),
    "administration-link-type-invalid-endpoint-or-cardinality-blocked": ("link", "link-invalid"),
    "administration-link-type-validation-loading": ("link", "validation-loading"),
    "administration-link-type-related-test-error": ("link", "related-error"),
    "administration-access-empty": ("access", "empty"),
    "administration-access-loading": ("access", "loading"),
    "administration-access-service-error": ("access", "service-error"),
    "administration-publish-validation-blocked": ("publish", "validation-blocked"),
    "administration-publish-validation-loading": ("publish", "validation-loading"),
    "administration-publish-error": ("publish", "publish-error"),
}

WIDE_EVIDENCE: dict[str, dict[str, str]] = {
    **{
        f"administration-layout-edit-draft-wide-{viewport}": {"family": "layout", "state": "draft", "viewport": viewport}
        for viewport in WIDE_VIEWPORTS
    },
    **{
        f"administration-subset-edit-draft-wide-{viewport}": {"family": "subset", "state": "draft", "viewport": viewport}
        for viewport in WIDE_VIEWPORTS
    },
    **{
        f"administration-link-type-edit-draft-wide-{viewport}": {"family": "link", "state": "draft", "viewport": viewport}
        for viewport in WIDE_VIEWPORTS
    },
    **{
        f"administration-access-normal-wide-{viewport}": {"family": "access", "state": "normal", "viewport": viewport}
        for viewport in WIDE_VIEWPORTS
    },
    **{
        f"administration-publish-blocked-wide-{viewport}": {"family": "publish", "state": "blocked", "viewport": viewport}
        for viewport in WIDE_VIEWPORTS
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Capture WAVE-06 Administration relationship, access, and publish references.")
    parser.add_argument("--target", choices=sorted(TARGETS), help="Capture one approval target.")
    parser.add_argument("--all-packet-targets", action="store_true", help="Capture all 17 approval targets, all evidence states, and wide evidence.")
    parser.add_argument("--state-evidence", action="store_true", help="Capture all evidence-only states at the three canonical viewports.")
    parser.add_argument("--wide-evidence", action="store_true", help="Capture normal-state wide evidence at 2560 and 3840.")
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


def composed_html(family: str, state: str) -> str:
    html = HTML_PATH.read_text(encoding="utf-8")
    core_css = CORE_CSS_PATH.read_text(encoding="utf-8")
    css = CSS_PATH.read_text(encoding="utf-8")
    javascript = JS_PATH.read_text(encoding="utf-8")
    html = html.replace('<link rel="stylesheet" href="administration-schema-core.css">', f"<style>{core_css}</style>")
    html = html.replace('<link rel="stylesheet" href="administration-remaining.css">', f"<style>{css}</style>")
    html = html.replace('<script src="administration-remaining.js" defer></script>', "")
    query = json.dumps({"family": family, "state": state, "role": "administrator"}, separators=(",", ":"))
    return html.replace("</body>", f"<script>window.__REFERENCE_QUERY__={query};</script><script>{javascript}</script></body>")


def rect(page: Page, selector: str) -> dict[str, float] | None:
    return page.evaluate(
        """
        (selector) => {
          const node = document.querySelector(selector);
          if (!node) return null;
          const r = node.getBoundingClientRect();
          return {x:r.x, y:r.y, width:r.width, height:r.height, right:r.right, bottom:r.bottom};
        }
        """,
        selector,
    )


def snapshot(page: Page, family: str, state: str) -> dict[str, Any]:
    value = page.evaluate(
        r"""
        () => {
          const visible = (node) => Boolean(node && !node.hidden && node.getBoundingClientRect().width > 0 && node.getBoundingClientRect().height > 0);
          const name = (node) => (node.getAttribute('aria-label') || node.textContent || node.getAttribute('placeholder') || node.labels?.[0]?.textContent || '').trim().replace(/\s+/g, ' ');
          const controls = [...document.querySelectorAll('button, a, input, select, textarea, [role="separator"]')].filter(visible).map((node) => ({tag:node.tagName.toLowerCase(), name:name(node), disabled:Boolean(node.disabled), action:node.dataset.action || node.dataset.splitter || ''}));
          const activePrimary = [...document.querySelectorAll('button.primary')].filter((node) => visible(node) && !node.disabled).map(name);
          const nestedInteractive = [...document.querySelectorAll('button, a')].filter((node) => node.querySelector('button, a, input, select, textarea')).map((node) => node.outerHTML.slice(0, 160));
          const legacySelectors = ['.page-stack','.page-heading','.content-card','.hero-actions','.eyebrow','.status-badge','.count-chip'].map((selector) => ({selector,count:document.querySelectorAll(selector).length}));
          const bodyStyle = getComputedStyle(document.body);
          const dataText = [...document.querySelectorAll('.remaining-row,.definition-row,.ordered-field-row,.filter-row,.task-row,.readiness-row,.link-test-row,.preview-table td')].filter(visible).map((node) => parseFloat(getComputedStyle(node).fontSize)).filter(Number.isFinite);
          const labels = [...document.querySelectorAll('label')].filter(visible).map((node) => node.textContent.trim().replace(/\s+/g,' '));
          const fieldValues = [...document.querySelectorAll('input, select, textarea')].filter(visible).map((node) => ({id:node.id, value:node.value, disabled:Boolean(node.disabled)}));
          const alerts = [...document.querySelectorAll('[role="alert"]')].filter(visible).map((node) => node.textContent.trim().replace(/\s+/g,' '));
          const listRows = [...document.querySelectorAll('.remaining-row')].filter(visible).map((node) => node.textContent.trim().replace(/\s+/g,' '));
          const tasks = [...document.querySelectorAll('.task-row')].filter(visible).map((node) => node.textContent.trim().replace(/\s+/g,' '));
          const readiness = [...document.querySelectorAll('.readiness-row')].filter(visible).map((node) => node.textContent.trim().replace(/\s+/g,' '));
          const related = [...document.querySelectorAll('.link-test-row')].filter(visible).map((node) => node.textContent.trim().replace(/\s+/g,' '));
          const orderedFields = [...document.querySelectorAll('.ordered-field-row')].filter(visible).map((node) => node.textContent.trim().replace(/\s+/g,' '));
          const filters = [...document.querySelectorAll('.filter-row')].filter(visible).map((node) => node.textContent.trim().replace(/\s+/g,' '));
          const documentText = document.body.innerText.replace(/\s+/g,' ');
          const documentOverflow = {
            horizontal: document.documentElement.scrollWidth - document.documentElement.clientWidth,
            vertical: document.documentElement.scrollHeight - document.documentElement.clientHeight,
          };
          const editor = document.querySelector('[data-region="editor"]');
          const editorScroll = document.querySelector('[data-editor-scroll]');
          const listScroll = document.querySelector('[data-list-scroll]');
          return {
            ready: document.body.dataset.ready === 'true',
            family: document.body.dataset.referenceFamily,
            state: document.body.dataset.referenceState,
            pageTitle: document.querySelector('[data-page-title]')?.textContent.trim() || '',
            topbarContext: document.querySelector('[data-topbar-context]')?.textContent.trim() || '',
            activePrimary,
            controls,
            nestedInteractive,
            legacySelectors,
            bodyFontPx: parseFloat(bodyStyle.fontSize),
            maximumDataFontPx: dataText.length ? Math.max(...dataText) : 0,
            labels,
            fieldValues,
            alerts,
            listRows,
            tasks,
            readiness,
            related,
            orderedFields,
            filters,
            documentText,
            documentOverflow,
            editorScroll: editorScroll ? {scrollHeight:editorScroll.scrollHeight, clientHeight:editorScroll.clientHeight, scrollTop:editorScroll.scrollTop} : null,
            listScroll: listScroll ? {scrollHeight:listScroll.scrollHeight, clientHeight:listScroll.clientHeight, scrollTop:listScroll.scrollTop} : null,
            editorTextClipped: editor ? editor.scrollWidth > editor.clientWidth + 1 : false,
            publishButtons: [...document.querySelectorAll('[data-action="publish"]')].filter(visible).map((node) => ({disabled:Boolean(node.disabled), text:name(node)})),
            selectedRowCount: document.querySelectorAll('.remaining-row.is-selected').length,
            previewTables: document.querySelectorAll('.preview-table').length,
          };
        }
        """
    )
    value["geometry"] = {
        "application_bar": rect(page, '[data-region="application-bar"]'),
        "command_bar": rect(page, '[data-region="command-bar"]'),
        "workspace": rect(page, '[data-region="workspace"]'),
        "navigator": rect(page, '[data-region="navigator"]'),
        "object_list": rect(page, '[data-region="object-list"]'),
        "editor": rect(page, '[data-region="editor"]'),
        "editor_grid": rect(page, ".remaining-editor-grid"),
        "editor_column": rect(page, ".editor-column"),
        "preview_column": rect(page, ".preview-column"),
        "status_bar": rect(page, "[data-status-bar]"),
    }
    return value


def interaction_checks(page: Page, family: str, state: str) -> dict[str, Any]:
    checks: dict[str, Any] = {}
    separator = page.locator('[data-splitter="navigator"]')
    if separator.count():
        before = int(separator.get_attribute("aria-valuenow") or "0")
        separator.focus()
        separator.press("ArrowRight")
        after = int(separator.get_attribute("aria-valuenow") or "0")
        checks["keyboard_splitter_delta"] = after - before
    if family in {"layout", "subset", "link"} and state == "draft":
        page.keyboard.press("Control+s")
        checks["ctrl_s_status"] = page.locator("[data-status-bar]").inner_text().strip()
    if family == "access" and state == "normal":
        page.locator('[data-action="revoke"]').click()
        checks["revoke_confirmation_visible"] = page.locator("text=Revoke material-reviewers access").count() == 1
        checks["revoke_reason_preserved"] = page.locator("#revoke-reason-live").input_value() if page.locator("#revoke-reason-live").count() else ""
    return checks


def capture_page(browser: Browser, target: str, family: str, state: str, viewport_name: str) -> dict[str, Any]:
    viewport = (VIEWPORTS | WIDE_VIEWPORTS)[viewport_name]
    context = browser.new_context(viewport=viewport, device_scale_factor=1, color_scheme="light")
    page = context.new_page()
    console_errors: list[str] = []
    page_errors: list[str] = []
    page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
    page.on("pageerror", lambda error: page_errors.append(str(error)))
    try:
        page.set_content(composed_html(family, state), wait_until="load")
        page.wait_for_function("document.body.dataset.ready === 'true'")
        page.evaluate("document.fonts?.ready")
        page.wait_for_timeout(60)
        snap = snapshot(page, family, state)
        interactions = interaction_checks(page, family, state)
        # Restore the target's canonical static state after interaction checks.
        if interactions:
            page.set_content(composed_html(family, state), wait_until="load")
            page.wait_for_function("document.body.dataset.ready === 'true'")
            page.wait_for_timeout(40)
            snap = snapshot(page, family, state)
        image_path = EVIDENCE_DIR / f"{target}.png"
        measurement_path = EVIDENCE_DIR / f"{target}.measurements.json"
        page.screenshot(path=str(image_path), full_page=False)
        width, height = png_dimensions(image_path)
        result = {
            "target": target,
            "family": family,
            "state": state,
            "viewport": viewport_name,
            "width": width,
            "height": height,
            "image": image_path.relative_to(ROOT).as_posix(),
            "image_sha256": sha256(image_path),
            "snapshot": snap,
            "interactions": interactions,
            "console_errors": console_errors,
            "page_errors": page_errors,
        }
        measurement_path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return result
    finally:
        context.close()


def _load_measurement(target: str) -> dict[str, Any] | None:
    path = EVIDENCE_DIR / f"{target}.measurements.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def write_staging(
    target_results: dict[str, dict[str, Any]],
    state_results: dict[str, list[dict[str, Any]]],
    wide_results: dict[str, dict[str, Any]],
) -> None:
    for target in TARGETS:
        if target not in target_results:
            loaded = _load_measurement(target)
            if loaded is not None:
                target_results[target] = loaded
    for base in STATE_EVIDENCE:
        if base not in state_results:
            loaded_items = []
            for viewport_name in VIEWPORTS:
                loaded = _load_measurement(f"{base}-{viewport_name}")
                if loaded is not None:
                    loaded_items.append(loaded)
            if loaded_items:
                state_results[base] = loaded_items
    for target in WIDE_EVIDENCE:
        if target not in wide_results:
            loaded = _load_measurement(target)
            if loaded is not None:
                wide_results[target] = loaded
    staging = {
        "family": "ADMINISTRATION-REMAINING",
        "bundles": ["ADM-SCHEMA-RELATIONS", "ADM-ACCESS", "ADM-PUBLISH"],
        "wave": "WAVE-06",
        "status": "pending_product_owner_review",
        "capture_date": date.today().isoformat(),
        "static": {
            "html": HTML_PATH.relative_to(ROOT).as_posix(),
            "base_css": CORE_CSS_PATH.relative_to(ROOT).as_posix(),
            "css": CSS_PATH.relative_to(ROOT).as_posix(),
            "javascript": JS_PATH.relative_to(ROOT).as_posix(),
            "capture": Path(__file__).relative_to(ROOT).as_posix(),
            "validator": "docs/00-research/ux-service-reference/validate_administration_remaining_wave06.py",
        },
        "targets": {
            key: {
                "family": value["family"],
                "state": value["state"],
                "viewport": value["viewport"],
                "image": value["image"],
                "measurements": f"docs/17-evidence/images/issue-167-service-reference/{key}.measurements.json",
                "sha256": value["image_sha256"],
            }
            for key, value in target_results.items()
        },
        "evidence_only_states": {
            key: {
                "family": STATE_EVIDENCE[key][0],
                "state": STATE_EVIDENCE[key][1],
                "captures": [item["image"] for item in results],
                "measurements": [f"docs/17-evidence/images/issue-167-service-reference/{key}-{item['viewport']}.measurements.json" for item in results],
            }
            for key, results in state_results.items()
        },
        "wide_evidence": {
            key: {
                "family": value["family"],
                "state": value["state"],
                "viewport": value["viewport"],
                "image": value["image"],
                "measurements": f"docs/17-evidence/images/issue-167-service-reference/{key}.measurements.json",
                "sha256": value["image_sha256"],
            }
            for key, value in wide_results.items()
        },
        "counts": {
            "approval_targets": len(target_results),
            "evidence_state_families": len(state_results),
            "evidence_state_captures": sum(len(items) for items in state_results.values()),
            "wide_evidence": len(wide_results),
        },
    }
    STAGING_PATH.write_text(json.dumps(staging, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    if not any((args.target, args.all_packet_targets, args.state_evidence, args.wide_evidence)):
        raise SystemExit("choose --target, --all-packet-targets, --state-evidence, or --wide-evidence")
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    target_results: dict[str, dict[str, Any]] = {}
    state_results: dict[str, list[dict[str, Any]]] = {}
    wide_results: dict[str, dict[str, Any]] = {}
    selected_targets = [args.target] if args.target else (list(TARGETS) if args.all_packet_targets else [])
    with sync_playwright() as playwright:
        configured_executable = os.environ.get("CMP_CHROMIUM_EXECUTABLE")
        executable_path = configured_executable or shutil.which("chromium") or shutil.which("chromium-browser")
        browser = playwright.chromium.launch(
            headless=True,
            executable_path=executable_path,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu", "--no-first-run", "--no-default-browser-check"],
        )
        try:
            for target in selected_targets:
                spec = TARGETS[target]
                target_results[target] = capture_page(browser, target, spec["family"], spec["state"], spec["viewport"])
            if args.all_packet_targets or args.state_evidence:
                for base, (family, state) in STATE_EVIDENCE.items():
                    state_results[base] = []
                    for viewport_name in VIEWPORTS:
                        target = f"{base}-{viewport_name}"
                        state_results[base].append(capture_page(browser, target, family, state, viewport_name))
            if args.all_packet_targets or args.wide_evidence:
                for target, spec in WIDE_EVIDENCE.items():
                    wide_results[target] = capture_page(browser, target, spec["family"], spec["state"], spec["viewport"])
        finally:
            browser.close()
    write_staging(target_results, state_results, wide_results)
    print(f"wrote {STAGING_PATH.relative_to(ROOT)}")
    print(f"approval={len(target_results)} state={sum(len(items) for items in state_results.values())} wide={len(wide_results)}")


if __name__ == "__main__":
    main()

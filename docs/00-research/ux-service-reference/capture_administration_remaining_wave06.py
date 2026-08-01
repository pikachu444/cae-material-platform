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

FAMILY_TARGETS = {
    "relations": {"layout", "subset", "link"},
    "access": {"access"},
    "publish": {"publish"},
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Capture WAVE-06 Administration relationship, access, and publish references.")
    parser.add_argument("--target", choices=sorted(TARGETS), help="Capture one approval target.")
    parser.add_argument("--all-packet-targets", action="store_true", help="Capture all 17 approval targets, all evidence states, and wide evidence.")
    parser.add_argument("--state-evidence", action="store_true", help="Capture all evidence-only states at the three canonical viewports.")
    parser.add_argument("--state-target", choices=sorted(STATE_EVIDENCE), help="Capture one evidence-only state at the three canonical viewports.")
    parser.add_argument("--wide-evidence", action="store_true", help="Capture normal-state wide evidence at 2560 and 3840.")
    parser.add_argument("--family-targets", nargs="+", choices=sorted(FAMILY_TARGETS), help="Capture only the named WAVE-06 family bundles and preserve other evidence files.")
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
          const collect = (selectors) => [...new Set(selectors.flatMap((selector) => [...document.querySelectorAll(selector)]))].filter(visible);
          const fontStats = (selectors) => {
            const values = collect(selectors).map((node) => parseFloat(getComputedStyle(node).fontSize)).filter(Number.isFinite);
            return {count: values.length, min: values.length ? Math.min(...values) : 0, max: values.length ? Math.max(...values) : 0};
          };
          const typography = {
            data: fontStats(['.remaining-row .row-name','.object-family','.ordered-field-row','.filter-row','.task-row','.readiness-row','.link-test-row','.preview-table td','.compact-property-form input','.compact-property-form select','.compact-property-form textarea','.assignment-summary dd','.empty-flat']),
            metadata: fontStats(['.remaining-list-columns','.remaining-row .row-meta','.remaining-row .row-revision','.remaining-row .row-status','.family-count','.editor-heading p','.editor-heading .editor-state','.form-help','.filter-operator','.field-type','.link-test-row .revision','.preview-surface-header p','.preview-surface-header span','.exact-pin-note','.validation-strip','.blocked-strip','.denied-strip','.service-error-strip','.confirm-strip','.pane-foot','.current-table-wrap span','.task-status','.save-disabled-reason','.publish-boundary p','.status-bar']),
            ordinaryWeight: (() => {
              const values = collect(['.remaining-row .row-name','.remaining-row .row-meta','.object-family','.button','.ordered-field-row','.filter-row','.task-row','.readiness-row','.link-test-row','.preview-table td','.compact-property-form input','.compact-property-form select','.compact-property-form textarea','.assignment-summary dd','.validation-strip','.blocked-strip','.denied-strip','.service-error-strip','.confirm-strip','.publish-boundary p','.empty-flat']).map((node) => parseFloat(getComputedStyle(node).fontWeight)).filter(Number.isFinite);
              return {count: values.length, max: values.length ? Math.max(...values) : 0};
            })(),
          };
          const rectValue = (node) => {
            const value = node.getBoundingClientRect();
            return {x:value.x, y:value.y, width:value.width, height:value.height, right:value.right, bottom:value.bottom};
          };
          const intersects = (a, b) => Boolean(a && b && a.left < b.right - 1 && a.right > b.left + 1 && a.top < b.bottom - 1 && a.bottom > b.top + 1);
          const clippedValues = (selectors) => collect(selectors).filter((node) => node.scrollWidth > node.clientWidth + 1).map((node) => ({
            id: node.dataset.rowId || node.id || '',
            text: (node.textContent || '').trim().replace(/\s+/g, ' '),
            width: node.clientWidth,
            scrollWidth: node.scrollWidth,
            fullAffordance: Boolean(node.getAttribute('title') || node.getAttribute('aria-label')),
          }));
          const clipping = {
            listNames: clippedValues(['.remaining-row .row-name']),
            previewValues: clippedValues(['.preview-table td','.link-test-row .source','.link-test-row .target']),
          };
          const revisionMetrics = collect(['.link-test-row .revision']).map((node) => {
            const revisionRect = node.getBoundingClientRect();
            const rowRect = node.closest('.link-test-row')?.getBoundingClientRect();
            const panelRect = node.closest('.preview-surface')?.getBoundingClientRect();
            const text = (node.textContent || '').trim().replace(/\s+/g, ' ');
            return {
              text,
              complete: /^r\d+$/.test(text),
              width: revisionRect.width,
              right: revisionRect.right,
              rowRight: rowRect?.right ?? 0,
              panelRight: panelRect?.right ?? 0,
              viewportRight: window.innerWidth,
              rowRightClearance: rowRect ? rowRect.right - revisionRect.right : 0,
              panelRightClearance: panelRect ? panelRect.right - revisionRect.right : 0,
              viewportRightClearance: window.innerWidth - revisionRect.right,
              withinRow: Boolean(rowRect && revisionRect.left >= rowRect.left - 1 && revisionRect.right <= rowRect.right + 1),
              withinPanel: Boolean(panelRect && revisionRect.left >= panelRect.left - 1 && revisionRect.right <= panelRect.right + 1),
            };
          });
          const overlapNodes = [...document.querySelectorAll('.remaining-list-columns > span,.remaining-row > span,.link-test-row > span,.preview-table th,.preview-table td,.editor-actions > *')].filter(visible);
          const overlapPairs = [];
          for (let index = 0; index < overlapNodes.length; index += 1) {
            for (let other = index + 1; other < overlapNodes.length; other += 1) {
              const first = overlapNodes[index];
              const second = overlapNodes[other];
              if (first.parentElement === second.parentElement && intersects(first.getBoundingClientRect(), second.getBoundingClientRect())) {
                overlapPairs.push({first: first.className || first.tagName, second: second.className || second.tagName});
              }
            }
          }
          const splitter = document.querySelector('[data-splitter="list"]');
          const splitterRect = splitter?.getBoundingClientRect();
          const splitterCandidates = [...document.querySelectorAll('.remaining-list-columns,.remaining-row,.remaining-editor-grid .editor-heading,.remaining-editor-grid .editor-actions,.link-test-row,.preview-table')].filter(visible);
          const splitterCollisions = splitterRect ? splitterCandidates.filter((node) => intersects(node.getBoundingClientRect(), splitterRect)).map((node) => node.className || node.tagName) : [];
          const labels = [...document.querySelectorAll('label')].filter(visible).map((node) => node.textContent.trim().replace(/\s+/g,' '));
          const fieldValues = [...document.querySelectorAll('input, select, textarea')].filter(visible).map((node) => ({id:node.id, value:node.value, disabled:Boolean(node.disabled)}));
          const alerts = [...document.querySelectorAll('[role="alert"]')].filter(visible).map((node) => node.textContent.trim().replace(/\s+/g,' '));
          const listRows = [...document.querySelectorAll('.remaining-row')].filter(visible).map((node) => node.textContent.trim().replace(/\s+/g,' '));
          const rowAccessibleNames = [...document.querySelectorAll('.remaining-row')].filter(visible).map((node) => ({id: node.dataset.rowId || '', name: node.getAttribute('aria-label') || ''}));
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
          const insideHorizontally = (node, bounds) => {
            if (!node || !bounds) return false;
            const rect = node.getBoundingClientRect();
            return rect.left >= bounds.left - 1 && rect.right <= bounds.right + 1;
          };
          const editorBounds = editorScroll?.getBoundingClientRect();
          const editorGrid = document.querySelector('.remaining-editor-grid');
          const editorColumn = document.querySelector('.editor-column');
          const previewColumn = document.querySelector('.preview-column');
          const editorHeadings = [...document.querySelectorAll('.remaining-editor-grid .editor-heading')].filter(visible);
          const editorActions = [...document.querySelectorAll('.remaining-editor-grid .editor-actions')].filter(visible);
          const parentColumnBounds = (node) => node.closest('.editor-column, .preview-column')?.getBoundingClientRect();
          return {
            ready: document.body.dataset.ready === 'true',
            family: document.body.dataset.referenceFamily,
            state: document.body.dataset.referenceState,
            pageTitle: document.querySelector('[data-page-title]')?.textContent.trim() || '',
            navTitle: document.querySelector('[data-nav-title]')?.textContent.trim() || '',
            listTitle: document.querySelector('[data-list-title]')?.textContent.trim() || '',
            topbarContext: document.querySelector('[data-topbar-context]')?.textContent.trim() || '',
            statusSelection: document.querySelector('[data-status-bar] span')?.textContent.trim() || '',
            statusBarFontPx: (() => { const node = document.querySelector('.status-bar'); return visible(node) ? parseFloat(getComputedStyle(node).fontSize) : 0; })(),
            activePrimary,
            controls,
            nestedInteractive,
            legacySelectors,
            bodyFontPx: parseFloat(bodyStyle.fontSize),
            maximumDataFontPx: dataText.length ? Math.max(...dataText) : 0,
            typography,
            clipping,
            revisionMetrics,
            overlap: {pairs: overlapPairs, noOverlaps: overlapPairs.length === 0, splitterCollisions, splitterSafe: splitterCollisions.length === 0},
            labels,
            fieldValues,
            alerts,
            listRows,
            rowAccessibleNames,
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
            remainingContainment: {
              gridInsideEditor: insideHorizontally(editorGrid, editorBounds),
              editorColumnInsideGrid: insideHorizontally(editorColumn, editorGrid?.getBoundingClientRect()),
              previewColumnInsideGrid: !previewColumn || insideHorizontally(previewColumn, editorGrid?.getBoundingClientRect()),
              headingsInsideColumns: editorHeadings.length > 0 && editorHeadings.every((node) => insideHorizontally(node, parentColumnBounds(node))),
              actionsInsideColumns: editorActions.every((node) => insideHorizontally(node, parentColumnBounds(node))),
            },
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
        rows = page.locator(".remaining-row")
        expected_rows = [rows.nth(index).locator(".row-name").inner_text().strip() for index in range(rows.count())]
        expected_meta = [rows.nth(index).locator(".row-meta").inner_text().strip() for index in range(rows.count())]
        family_label = {"layout": "Layout", "subset": "Subset", "link": "Link Type"}[family]

        def selection_state() -> dict[str, Any]:
            return page.evaluate(
                r"""
                () => {
                  const rows = [...document.querySelectorAll('.remaining-row')];
                  const selected = rows.filter((node) => node.classList.contains('is-selected'));
                  const row = selected[0];
                  const preview = document.querySelector('.preview-surface');
                  const editorHeading = document.querySelector('.editor-column .editor-heading h2');
                  const statusSelection = document.querySelector('[data-status-bar] span');
                  return {
                    selectedId: row?.dataset.rowId || '',
                    selectedPressed: row?.getAttribute('aria-pressed') || '',
                    selectedCount: selected.length,
                    pressedTrueCount: rows.filter((node) => node.getAttribute('aria-pressed') === 'true').length,
                    focusedId: document.activeElement?.dataset?.rowId || '',
                    selectedTabindex: row?.getAttribute('tabindex') || '',
                    editorHeading: editorHeading?.textContent.trim() || '',
                    previewText: preview?.textContent.trim().replace(/\s+/g, ' ') || '',
                    selectionStatus: statusSelection?.textContent.trim() || '',
                  };
                }
                """
            )

        selection_records: list[dict[str, Any]] = []
        for index in range(1, rows.count()):
            row = page.locator(".remaining-row").nth(index)
            row.click()
            current = selection_state()
            current["expectedId"] = row.get_attribute("data-row-id") or ""
            current["expectedName"] = expected_rows[index]
            current["expectedContext"] = expected_meta[index]
            current["expectedStatus"] = f"{family_label} · {expected_rows[index]}"
            current["passed"] = bool(
                current["selectedId"] == current["expectedId"]
                and current["selectedPressed"] == "true"
                and current["selectedCount"] == 1
                and current["pressedTrueCount"] == 1
                and current["focusedId"] == current["expectedId"]
                and current["selectedTabindex"] == "0"
                and current["editorHeading"] == current["expectedName"]
                and current["expectedName"] in current["previewText"]
                and current["expectedContext"] in current["previewText"]
                and current["selectionStatus"] == current["expectedStatus"]
            )
            selection_records.append(current)
        checks["selection_records"] = selection_records
        checks["selection_passed"] = bool(selection_records) and all(record["passed"] for record in selection_records)

        # Exercise the single roving-tab-stop path and ensure keyboard selection uses the same renderer.
        page.locator(".remaining-row").nth(0).focus()
        keyboard_records: list[dict[str, Any]] = []
        keyboard_steps = [("ArrowDown", 1), ("ArrowUp", 0), ("Home", 0), ("End", rows.count() - 1)]
        for key, expected_index in keyboard_steps:
            page.keyboard.press(key)
            current = selection_state()
            expected_id = rows.nth(expected_index).get_attribute("data-row-id") or ""
            expected_name = expected_rows[expected_index]
            current.update({"key": key, "expectedId": expected_id, "expectedName": expected_name, "expectedStatus": f"{family_label} · {expected_name}"})
            current["passed"] = bool(
                current["selectedId"] == expected_id
                and current["selectedPressed"] == "true"
                and current["selectedCount"] == 1
                and current["pressedTrueCount"] == 1
                and current["focusedId"] == expected_id
                and current["selectedTabindex"] == "0"
                and current["editorHeading"] == expected_name
                and expected_name in current["previewText"]
                and current["selectionStatus"] == current["expectedStatus"]
            )
            keyboard_records.append(current)
        page.locator(".remaining-row").nth(0).focus()
        page.keyboard.press("ArrowDown")
        page.keyboard.press("Enter")
        current = selection_state()
        expected_id = rows.nth(1).get_attribute("data-row-id") or ""
        expected_name = expected_rows[1]
        current.update({"key": "Enter", "expectedId": expected_id, "expectedName": expected_name, "expectedStatus": f"{family_label} · {expected_name}"})
        current["passed"] = bool(
            current["selectedId"] == expected_id
            and current["selectedPressed"] == "true"
            and current["selectedCount"] == 1
            and current["pressedTrueCount"] == 1
            and current["focusedId"] == expected_id
            and current["selectedTabindex"] == "0"
            and current["editorHeading"] == expected_name
            and expected_name in current["previewText"]
            and current["selectionStatus"] == current["expectedStatus"]
        )
        keyboard_records.append(current)
        checks["keyboard_records"] = keyboard_records
        checks["keyboard_passed"] = all(record["passed"] for record in keyboard_records)
    if family == "access" and state == "normal":
        rows = page.locator(".remaining-row")
        expected_rows = [rows.nth(index).locator(".row-name").inner_text().strip() for index in range(rows.count())]

        def access_selection_state() -> dict[str, Any]:
            return page.evaluate(
                r"""
                () => {
                  const rows = [...document.querySelectorAll('.remaining-row')];
                  const selected = rows.filter((node) => node.classList.contains('is-selected'));
                  const row = selected[0];
                  const preview = document.querySelector('.preview-column');
                  const editorHeading = document.querySelector('.editor-column .editor-heading h2');
                  const summary = document.querySelector('.assignment-summary');
                  const status = document.querySelector('[data-status-bar]');
                  const summaryFields = Object.fromEntries([...document.querySelectorAll('.assignment-summary .definition-row')].map((row) => [row.querySelector('dt')?.textContent.trim() || '', row.querySelector('dd')?.textContent.trim() || '']));
                  return {
                    selectedId: row?.dataset.rowId || '',
                    selectedPressed: row?.getAttribute('aria-pressed') || '',
                    selectedCount: selected.length,
                    pressedTrueCount: rows.filter((node) => node.getAttribute('aria-pressed') === 'true').length,
                    focusedId: document.activeElement?.dataset?.rowId || '',
                    selectedTabindex: row?.getAttribute('tabindex') || '',
                    editorHeading: editorHeading?.textContent.trim() || '',
                    summaryText: summary?.innerText.trim().replace(/\s+/g, ' ') || '',
                    summaryFields,
                    previewText: preview?.textContent.trim().replace(/\s+/g, ' ') || '',
                    statusText: status?.textContent.trim().replace(/\s+/g, ' ') || '',
                    referenceState: document.body.dataset.referenceState || '',
                  };
                }
                """
            )

        rows.nth(1).click()
        pointer = access_selection_state()
        pointer.update({"expectedId": rows.nth(1).get_attribute("data-row-id") or "", "expectedName": expected_rows[1]})
        pointer["passed"] = bool(
            pointer["selectedId"] == pointer["expectedId"]
            and pointer["selectedPressed"] == "true"
            and pointer["selectedCount"] == 1
            and pointer["pressedTrueCount"] == 1
            and pointer["focusedId"] == pointer["expectedId"]
            and pointer["selectedTabindex"] == "0"
            and pointer["editorHeading"] == pointer["expectedName"]
            and pointer["summaryFields"].get("User or team") == pointer["expectedName"]
            and "User access" in pointer["previewText"]
            and "Not granted" in pointer["previewText"]
            and "Role User" in pointer["summaryText"]
            and "Scope Atlas workspace" in pointer["summaryText"]
            and "Confidential" in pointer["summaryText"]
            and "Assignment · material-engineers" in pointer["statusText"]
        )
        checks["access_pointer_records"] = [pointer]
        checks["access_pointer_passed"] = pointer["passed"]

        page.locator(".remaining-row").nth(0).focus()
        keyboard_records: list[dict[str, Any]] = []
        keyboard_steps = [("ArrowDown", 1), ("ArrowUp", 0), ("Home", 0), ("End", rows.count() - 1)]
        for key, expected_index in keyboard_steps:
            page.keyboard.press(key)
            current = access_selection_state()
            expected_id = rows.nth(expected_index).get_attribute("data-row-id") or ""
            expected_name = expected_rows[expected_index]
            current.update({"key": key, "expectedId": expected_id, "expectedName": expected_name})
            current["passed"] = bool(
                current["selectedId"] == expected_id
                and current["selectedPressed"] == "true"
                and current["selectedCount"] == 1
                and current["pressedTrueCount"] == 1
                and current["focusedId"] == expected_id
                and current["selectedTabindex"] == "0"
                and current["editorHeading"] == expected_name
                and current["summaryFields"].get("User or team") == expected_name
                and expected_name in current["summaryText"]
                and bool(current["previewText"])
            )
            current["passed"] = current["passed"] and f"Assignment · {expected_name}" in current["statusText"]
            keyboard_records.append(current)
        page.locator(".remaining-row").nth(0).focus()
        page.keyboard.press("ArrowDown")
        page.keyboard.press("Enter")
        current = access_selection_state()
        expected_id = rows.nth(1).get_attribute("data-row-id") or ""
        expected_name = expected_rows[1]
        current.update({"key": "Enter", "expectedId": expected_id, "expectedName": expected_name})
        current["passed"] = bool(
            current["selectedId"] == expected_id
            and current["selectedPressed"] == "true"
            and current["selectedCount"] == 1
            and current["pressedTrueCount"] == 1
            and current["focusedId"] == expected_id
            and current["selectedTabindex"] == "0"
            and current["editorHeading"] == expected_name
            and current["summaryFields"].get("User or team") == expected_name
            and "User access" in current["previewText"]
            and f"Assignment · {expected_name}" in current["statusText"]
        )
        keyboard_records.append(current)
        checks["access_keyboard_records"] = keyboard_records
        checks["access_keyboard_passed"] = all(record["passed"] for record in keyboard_records)

        rows.nth(0).click()
        page.locator('[data-action="revoke"]').click()
        confirmation = page.evaluate(
            r"""
            () => {
              const actions = [...document.querySelectorAll('.editor-actions [data-action]')];
              const summary = document.querySelector('.assignment-summary');
              const preview = document.querySelector('.preview-column');
              const heading = document.querySelector('.editor-column .editor-heading h2');
              const reason = document.querySelector('#revoke-reason-live, #revoke-reason');
              const summaryFields = Object.fromEntries([...document.querySelectorAll('.assignment-summary .definition-row')].map((row) => [row.querySelector('dt')?.textContent.trim() || '', row.querySelector('dd')?.textContent.trim() || '']));
              const warningText = document.querySelector('.confirm-strip')?.innerText.trim().replace(/\s+/g, ' ') || '';
              return {
                referenceState: document.body.dataset.referenceState || '',
                heading: heading?.textContent.trim() || '',
                summaryText: summary?.innerText.trim().replace(/\s+/g, ' ') || '',
                summaryFields,
                previewText: preview?.textContent.trim().replace(/\s+/g, ' ') || '',
                warningText,
                reason: reason?.value || '',
                destructiveCount: actions.filter((node) => node.dataset.action === 'confirm-revoke' && node.classList.contains('danger')).length,
                cancelCount: actions.filter((node) => node.dataset.action === 'cancel-revoke').length,
                actionLabels: actions.map((node) => node.textContent.trim()),
              };
            }
            """
        )
        confirmation["passed"] = bool(
            confirmation["referenceState"] == "revoke-confirm"
            and confirmation["heading"] == "Revoke material-reviewers access"
            and confirmation["summaryFields"].get("User or team") == "material-reviewers"
            and "Role Reviewer" in confirmation["summaryText"]
            and "Scope Atlas workspace" in confirmation["summaryText"]
            and "Confidential" in confirmation["summaryText"]
            and confirmation["reason"]
            and confirmation["warningText"] == "This removes task access for the selected team. Existing immutable review decisions remain preserved. New actions granted by this assignment will be blocked after revocation."
            and "Reviewer access" in confirmation["previewText"]
            and "Included in this assignment" in page.locator(".preview-column").inner_text()
            and confirmation["destructiveCount"] == 1
            and confirmation["cancelCount"] == 1
        )
        checks["access_revoke_confirmation"] = confirmation

        page.locator('[data-action="cancel-revoke"]').click()
        cancelled = access_selection_state()
        cancelled["passed"] = bool(
            cancelled["referenceState"] == "normal"
            and cancelled["selectedId"] == "acc-reviewers"
            and cancelled["selectedPressed"] == "true"
            and cancelled["selectedCount"] == 1
            and cancelled["focusedId"] == "acc-reviewers"
            and cancelled["editorHeading"] == "material-reviewers"
            and "Reviewer access" in cancelled["previewText"]
            and page.locator('[data-action="revoke"]').count() == 1
            and "Revocation cancelled" in cancelled["statusText"]
        )
        checks["access_cancel_recovery"] = cancelled
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
        if family == "access" and state == "empty":
            status_selection = snap.get("statusSelection", "")
            snap["emptyStatusValid"] = status_selection == "Assignments · none" and "material-reviewers" not in status_selection
        interactions = interaction_checks(page, family, state)
        # Restore the target's canonical static state after interaction checks.
        if interactions:
            page.set_content(composed_html(family, state), wait_until="load")
            page.wait_for_function("document.body.dataset.ready === 'true'")
            page.wait_for_timeout(40)
            snap = snapshot(page, family, state)
            if family == "access" and state == "empty":
                status_selection = snap.get("statusSelection", "")
                snap["emptyStatusValid"] = status_selection == "Assignments · none" and "material-reviewers" not in status_selection
        image_path = EVIDENCE_DIR / f"{target}.png"
        measurement_path = EVIDENCE_DIR / f"{target}.measurements.json"
        # Collect bytes before replacing so a rapid bounded family batch does
        # not race Playwright's asynchronous file helper on Windows.
        temp_image_path = image_path.with_name(f".{image_path.name}.tmp")
        temp_image_path.write_bytes(page.screenshot(full_page=False))
        temp_image_path.replace(image_path)
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
        "status": "approved",
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
    if not any((args.target, args.all_packet_targets, args.state_evidence, args.state_target, args.wide_evidence, args.family_targets)):
        raise SystemExit("choose --target, --all-packet-targets, --state-evidence, --state-target, --wide-evidence, or --family-targets")
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    target_results: dict[str, dict[str, Any]] = {}
    state_results: dict[str, list[dict[str, Any]]] = {}
    wide_results: dict[str, dict[str, Any]] = {}
    selected_families = set().union(*(FAMILY_TARGETS[name] for name in (args.family_targets or [])))
    selected_targets = [args.target] if args.target else (
        [target for target, spec in TARGETS.items() if not selected_families or spec["family"] in selected_families]
        if args.all_packet_targets or args.family_targets else []
    )
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
            if args.all_packet_targets or args.state_evidence or args.family_targets:
                for base, (family, state) in STATE_EVIDENCE.items():
                    if selected_families and family not in selected_families:
                        continue
                    state_results[base] = []
                    for viewport_name in VIEWPORTS:
                        target = f"{base}-{viewport_name}"
                        state_results[base].append(capture_page(browser, target, family, state, viewport_name))
            elif args.state_target:
                family, state = STATE_EVIDENCE[args.state_target]
                state_results[args.state_target] = [
                    capture_page(browser, f"{args.state_target}-{viewport_name}", family, state, viewport_name)
                    for viewport_name in VIEWPORTS
                ]
            if args.all_packet_targets or args.wide_evidence or args.family_targets:
                for target, spec in WIDE_EVIDENCE.items():
                    if selected_families and spec["family"] not in selected_families:
                        continue
                    wide_results[target] = capture_page(browser, target, spec["family"], spec["state"], spec["viewport"])
        finally:
            browser.close()
    write_staging(target_results, state_results, wide_results)
    print(f"wrote {STAGING_PATH.relative_to(ROOT)}")
    print(f"approval={len(target_results)} state={sum(len(items) for items in state_results.values())} wide={len(wide_results)}")


if __name__ == "__main__":
    main()

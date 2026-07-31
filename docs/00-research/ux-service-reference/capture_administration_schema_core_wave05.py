from __future__ import annotations

# ruff: noqa: E501
import argparse
import hashlib
import json
import struct
import time
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
WIDE_VIEWPORTS: dict[str, dict[str, int]] = {
    "2560x1440": {"width": 2560, "height": 1440, "device_scale_factor": 1},
    "3840x2160": {"width": 3840, "height": 2160, "device_scale_factor": 1},
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
    "administration-table-add-draft": ("administrator", "table-add"),
    "administration-table-saving": ("administrator", "table-saving"),
    "administration-table-save-error": ("administrator", "table-save-error"),
    "administration-attribute-add-draft": ("administrator", "attribute-add"),
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

WIDE_EVIDENCE: dict[str, dict[str, Any]] = {
    "administration-database-normal-wide-2560x1440": {"role": "administrator", "state": "normal", "viewport": "2560x1440"},
    "administration-database-normal-wide-3840x2160": {"role": "administrator", "state": "normal", "viewport": "3840x2160"},
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Capture the WAVE-05 ADM-SCHEMA-CORE static Administration service-reference bundle.")
    parser.add_argument("--target", choices=sorted(TARGETS), help="Capture one approval target.")
    parser.add_argument("--all-packet-targets", action="store_true", help="Capture all eleven approval targets and all evidence-only states.")
    parser.add_argument("--state-evidence", action="store_true", help="Capture all evidence-only states at all three viewports.")
    parser.add_argument("--state-target", choices=sorted(STATE_EVIDENCE), help="Capture one evidence-only state without rewriting the shared staging index.")
    parser.add_argument("--state-viewport", choices=sorted(VIEWPORTS), help="Limit --state-target to one viewport; omit to capture all three.")
    parser.add_argument("--wide-evidence", action="store_true", help="Capture the two normal-state wide evidence siblings.")
    args = parser.parse_args()
    if args.state_viewport and not args.state_target:
        parser.error("--state-viewport requires --state-target")
    if args.state_target and any((args.target, args.all_packet_targets, args.state_evidence, args.wide_evidence)):
        parser.error("--state-target is a bounded standalone capture mode")
    return args


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


def open_page(browser: Browser, role: str, state: str, viewport_name: str, *, preview: str | None = None, projection: str | None = None, field: str | None = None) -> tuple[Page, list[str], list[str]]:
    viewport = (VIEWPORTS | WIDE_VIEWPORTS)[viewport_name]
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
    query = {"state": state, "role": role}
    if preview:
        query["preview"] = preview
    if projection:
        query["projection"] = projection
    if field:
        query["field"] = field
    page.goto(f"{HTML_PATH.as_uri()}?{urlencode(query)}", wait_until="load")
    page.wait_for_timeout(90)
    return page, console_errors, page_errors


def dom_snapshot(page: Page) -> dict[str, Any]:
    return page.evaluate(
        r"""
        () => {
          const box = (node) => { if (!node) return null; const r = node.getBoundingClientRect(); return {x:r.x, y:r.y, width:r.width, height:r.height}; };
          const rect = (selector) => box(document.querySelector(selector));
          const computed = (selector) => { const node = document.querySelector(selector); return node ? getComputedStyle(node) : null; };
          const controls = [...document.querySelectorAll('button, a, input, select, textarea, [role="separator"], [role="scrollbar"]')].filter((node) => !node.hidden && node.getBoundingClientRect().width > 0 && node.getBoundingClientRect().height > 0).map((node) => ({ tag: node.tagName.toLowerCase(), name: (node.getAttribute('aria-label') || node.textContent || node.getAttribute('placeholder') || node.labels?.[0]?.textContent || '').trim().replace(/\s+/g, ' '), disabled: Boolean(node.disabled), action: node.dataset.action || node.dataset.objectId || node.dataset.objectKind || node.dataset.splitter || '' }));
          const nestedInteractive = [...document.querySelectorAll('button, a')].filter((node) => node.querySelector('button, a, input, select, textarea')).map((node) => node.outerHTML.slice(0, 120));
          const editor = document.querySelector('[data-editor-mode]');
          const selectedRow = document.querySelector('.object-row.is-selected');
          const selectedRowCells = selectedRow ? {
            name: selectedRow.querySelector('.object-name'),
            primaryName: selectedRow.querySelector('.object-primary-name'),
            definition: selectedRow.querySelector('.object-definition'),
            revision: selectedRow.querySelector('.object-revision')
          } : null;
          const fields = [...document.querySelectorAll('.property-form input, .property-form textarea, .property-form select')].map((node) => ({ name: node.name, value: node.value, type: node.type, disabled: Boolean(node.disabled), readonly: Boolean(node.readOnly), invalid: Boolean(node.closest('.has-error')) }));
          const errorTexts = [...document.querySelectorAll('[role="alert"], .form-error')].map((node) => node.textContent.trim()).filter(Boolean);
          const splitters = [...document.querySelectorAll('[data-splitter]')].map((node) => ({ key: node.dataset.splitter, min: Number(node.getAttribute('aria-valuemin')), max: Number(node.getAttribute('aria-valuemax')), value: Number(node.getAttribute('aria-valuenow')), rect: rect(`[data-splitter="${node.dataset.splitter}"]`) }));
          const rows = [...document.querySelectorAll('.object-row')].map((node) => ({ id: node.dataset.objectId, selected: node.classList.contains('is-selected'), width: node.getBoundingClientRect().width, height: node.getBoundingClientRect().height, clipped: node.scrollWidth > node.clientWidth }));
          const listColumns = [...document.querySelectorAll('[data-list-columns] > span')].map((node) => node.textContent.trim());
          const listRows = [...document.querySelectorAll('.object-row')].map((node) => ({
            id: node.dataset.objectId,
            name: node.querySelector('.object-primary-name')?.textContent.trim() || '',
            metadata: node.querySelector('.object-definition')?.textContent.trim() || null,
            revision: node.querySelector('.object-revision')?.textContent.trim() || '',
            columnCount: node.children.length
          }));
           const navigator = rect('#navigator-pane'); const list = rect('#object-list-pane'); const editorPane = rect('#editor-pane'); const editorContent = rect('.editor-content'); const previewPanel = rect('#datasheet-preview'); const statusBar = rect('.status-bar');
           const editorScroll = document.querySelector('[data-editor-scroll]'); const listScroll = document.querySelector('[data-list-scroll]'); const previewScroll = document.querySelector('[data-preview-scroll]'); const previewValueTableScroll = document.querySelector('[data-preview-values-scroll]'); const previewLayoutTableScroll = document.querySelector('[data-preview-layout-scroll]');
          const editorScrollRail = document.querySelector('[data-editor-scroll-rail]'); const editorScrollThumb = document.querySelector('[data-editor-scroll-thumb]'); const previewContent = document.querySelector('[data-preview-content]'); const previewHeading = document.querySelector('.preview-heading'); const previewContext = document.querySelector('[data-preview-context]'); const previewTabs = [...document.querySelectorAll('[data-action="preview-projection"]')]; const activePreviewSection = document.querySelector('[data-preview-active-section]');
           const previewPlot = document.querySelector('[data-preview-plot]'); const previewPlotFrame = document.querySelector('[data-preview-plot-frame]'); const previewGraphSection = document.querySelector('[data-preview-graph-section]'); const previewPlotPath = previewPlot?.querySelector('.preview-response-line'); const previewGraphHeading = previewGraphSection?.querySelector('h3'); const previewText = [previewContent?.innerText || '', previewGraphSection?.innerText || ''].join(' ').replace(/\s+/g, ' ').trim();
          const body = document.body; const root = document.documentElement;
          const bodyStyle = getComputedStyle(body); const rootStyle = getComputedStyle(root);
          const pageText = body.innerText.replace(/\s+/g, ' ').trim();
          return {
            role: body.dataset.role, state: body.dataset.state, viewport: { width: innerWidth, height: innerHeight, deviceScaleFactor: devicePixelRatio },
            overflow: { documentScrollWidth: root.scrollWidth - innerWidth, bodyScrollWidth: body.scrollWidth - innerWidth, documentScrollHeight: root.scrollHeight - innerHeight, bodyScrollHeight: body.scrollHeight - innerHeight },
            geometry: { workspace: rect('[data-workspace]'), navigator, list, editorPane, editorScroll: box(editorScroll), editorContent, preview: previewPanel, previewContent: box(previewContent), statusBar, editor: rect('[data-editor-mode]'), content: rect('.admin-shell') },
            splitters, rows, controls, nestedInteractive, listColumns, listRows,
            objectNameSecondaryCount: document.querySelectorAll('.object-name small').length,
            panes: { navigatorOverflowY: computed('#navigator-pane')?.overflowY, listOverflowY: computed('[data-list-scroll]')?.overflowY, editorOverflowY: computed('[data-editor-scroll]')?.overflowY },
            localScroll: {
              list: listScroll ? { scrollHeight: listScroll.scrollHeight, clientHeight: listScroll.clientHeight, scrollTop: listScroll.scrollTop, scrollWidth: listScroll.scrollWidth, clientWidth: listScroll.clientWidth, overflowY: getComputedStyle(listScroll).overflowY, scrollbarGutter: getComputedStyle(listScroll).scrollbarGutter, reservedScrollbarWidth: listScroll.offsetWidth - listScroll.clientWidth } : null,
              editor: editorScroll ? { scrollHeight: editorScroll.scrollHeight, clientHeight: editorScroll.clientHeight, scrollTop: editorScroll.scrollTop, scrollWidth: editorScroll.scrollWidth, clientWidth: editorScroll.clientWidth, overflowY: getComputedStyle(editorScroll).overflowY, scrollbarGutter: getComputedStyle(editorScroll).scrollbarGutter, scrollbarColor: getComputedStyle(editorScroll).scrollbarColor, reservedScrollbarWidth: editorScroll.offsetWidth - editorScroll.clientWidth } : null,
               preview: previewScroll ? { scrollHeight: previewScroll.scrollHeight, clientHeight: previewScroll.clientHeight, scrollTop: previewScroll.scrollTop, scrollWidth: previewScroll.scrollWidth, clientWidth: previewScroll.clientWidth, overflowY: getComputedStyle(previewScroll).overflowY, scrollbarGutter: getComputedStyle(previewScroll).scrollbarGutter, reservedScrollbarWidth: previewScroll.offsetWidth - previewScroll.clientWidth } : null,
               previewTables: [previewValueTableScroll, previewLayoutTableScroll].map((node) => { const region = node?.closest('[data-preview-table-region]'); const rail = region?.querySelector('[data-preview-table-rail]'); const thumb = region?.querySelector('[data-preview-table-thumb]'); const clientBox = node ? box(node) : null; const partialRows = node ? [...node.querySelectorAll('tbody tr')].filter((row) => { const rowBox = box(row); const bottom = clientBox.y + clientBox.height; return rowBox.y < bottom - 0.5 && rowBox.y + rowBox.height > clientBox.y + 0.5 && (rowBox.y < clientBox.y - 0.5 || rowBox.y + rowBox.height > bottom + 0.5); }).length : null; return node ? ({ rect: clientBox, regionRect: box(region), tableRect: box(node.querySelector('table')), scrollHeight: node.scrollHeight, clientHeight: node.clientHeight, overflowY: getComputedStyle(node).overflowY, scrollbarGutter: getComputedStyle(node).scrollbarGutter, partialRows, rail: rail ? { hidden: rail.hidden, rect: box(rail), thumbRect: box(thumb), ariaMin: Number(rail.getAttribute('aria-valuemin')), ariaMax: Number(rail.getAttribute('aria-valuemax')), ariaNow: Number(rail.getAttribute('aria-valuenow')) } : null }) : null; }),
              editorRail: editorScrollRail ? {
                hidden: editorScrollRail.hidden,
                rect: box(editorScrollRail),
                thumbRect: box(editorScrollThumb),
                ariaMin: Number(editorScrollRail.getAttribute('aria-valuemin')),
                ariaMax: Number(editorScrollRail.getAttribute('aria-valuemax')),
                ariaNow: Number(editorScrollRail.getAttribute('aria-valuenow'))
              } : null
            },
            editorMode: editor?.dataset.editorMode || '',
            editorTitle: editor?.querySelector('h2')?.textContent.trim() || '',
            selectedRow: selectedRow ? {
              id: selectedRow.dataset.objectId || '',
              name: selectedRow.querySelector('.object-name > span')?.textContent.trim() || '',
              cells: {
                name: box(selectedRowCells.name),
                definition: box(selectedRowCells.definition),
                revision: box(selectedRowCells.revision),
                primaryName: selectedRowCells.primaryName ? {
                  clientWidth: selectedRowCells.primaryName.clientWidth,
                  scrollWidth: selectedRowCells.primaryName.scrollWidth,
                  overflow: getComputedStyle(selectedRowCells.primaryName).overflow,
                  textOverflow: getComputedStyle(selectedRowCells.primaryName).textOverflow,
                  whiteSpace: getComputedStyle(selectedRowCells.primaryName).whiteSpace
                } : null
              }
            } : null,
            fields, errors: errorTexts,
            preview: {
              visible: Boolean(document.querySelector('[data-preview-panel]') && !document.querySelector('[data-preview-panel]').hidden && document.querySelector('[data-preview-panel]').getBoundingClientRect().width > 0),
              open: document.querySelector('[data-preview-command]')?.getAttribute('aria-expanded') === 'true',
              commandLabel: document.querySelector('[data-preview-command]')?.textContent.trim() || '',
              title: document.querySelector('[data-preview-title]')?.textContent.trim() || '',
              subtitle: document.querySelector('[data-preview-subtitle]')?.textContent.trim() || '',
              record: document.querySelector('[data-preview-record]')?.textContent.trim() || '',
              table: document.querySelector('[data-preview-table]')?.textContent.trim() || '',
              selection: document.querySelector('[data-preview-selection]')?.textContent.trim() || '',
              note: document.querySelector('[data-preview-note]')?.textContent.trim() || '',
              sections: [...document.querySelectorAll('[data-preview-sections] > section')].map((node) => ({ heading: node.querySelector('h3')?.textContent.trim() || '', rect: box(node), active: node.classList.contains('is-active') || node === previewGraphSection })),
              activeProjection: previewContent?.dataset.previewActiveTask || '',
              projectionTabs: previewTabs.map((node) => ({ name: node.textContent.trim(), selected: node.getAttribute('aria-selected') === 'true', focusable: node.tabIndex >= 0 })),
              activeTable: activePreviewSection?.querySelector('table')?.dataset.previewValues !== undefined ? 'record' : activePreviewSection?.querySelector('table')?.dataset.previewLayout !== undefined ? 'layout' : '',
              activeRowCount: activePreviewSection?.querySelectorAll('tbody tr[data-preview-row], tbody tr[data-layout-field]').length || 0,
              activeSectionRect: box(activePreviewSection),
              activeTableRegionRect: box(activePreviewSection?.querySelector('[data-preview-table-region]')),
              activeTableScrollRect: box(activePreviewSection?.querySelector('.preview-table-scroll')),
              valueRows: [...document.querySelectorAll('[data-preview-values] [data-preview-row]')].map((node) => ({ id: node.dataset.previewFieldId, selected: node.dataset.previewSelected === 'true', revisionId: node.dataset.previewAttributeRevisionId || '', artifactId: node.dataset.artifactId || '', artifactSha256: node.dataset.artifactSha256 || '', label: node.querySelector('th strong')?.textContent.trim() || '', value: node.querySelector('[data-preview-value]')?.textContent.trim() || '', condition: node.querySelector('.preview-condition')?.textContent.trim() || '', text: node.textContent.trim() })),
              layoutRows: [...document.querySelectorAll('[data-preview-layout] [data-layout-field]')].map((node) => ({ id: node.dataset.previewFieldId, selected: node.dataset.previewSelected === 'true', ordinal: Number(node.dataset.layoutOrdinal), revisionId: node.dataset.previewAttributeRevisionId || '', artifactId: node.dataset.artifactId || '', artifactSha256: node.dataset.artifactSha256 || '', label: node.querySelector('td strong')?.textContent.trim() || '', text: node.textContent.trim() })),
              graph: {
                visible: Boolean(previewPlot && previewPlot.getBoundingClientRect().width > 0 && previewPlot.getBoundingClientRect().height > 0),
                section: box(previewGraphSection),
                frame: box(previewPlotFrame),
                plotBox: box(previewPlot),
                title: previewPlot?.querySelector('title')?.textContent.trim() || '',
                description: previewPlot?.querySelector('desc')?.textContent.trim() || '',
                axisTitles: [...(previewPlot?.querySelectorAll('[data-axis-title]') || [])].map((node) => node.textContent.trim()),
                ticks: [...(previewPlot?.querySelectorAll('[data-tick]') || [])].map((node) => node.textContent.trim()),
                viewBox: (previewPlot?.getAttribute('viewBox') || '').trim().split(/\s+/).map(Number).filter((value) => Number.isFinite(value)),
                rendered: { width: Number(previewPlot?.dataset.renderedWidth || 0), height: Number(previewPlot?.dataset.renderedHeight || 0) },
                plotArea: { left: Number(previewPlot?.dataset.plotLeft || 0), right: Number(previewPlot?.dataset.plotRight || 0), top: Number(previewPlot?.dataset.plotTop || 0), bottom: Number(previewPlot?.dataset.plotBottom || 0) },
                path: { d: previewPlotPath?.getAttribute('d') || '', left: Number(previewPlot?.dataset.pathLeft || 0), right: Number(previewPlot?.dataset.pathRight || 0), top: Number(previewPlot?.dataset.pathTop || 0), bottom: Number(previewPlot?.dataset.pathBottom || 0) },
                series: { minStrain: Number(previewPlot?.dataset.seriesMinStrain || 0), maxStrain: Number(previewPlot?.dataset.seriesMaxStrain || 0), minStressMpa: Number(previewPlot?.dataset.seriesMinStressMpa || 0), maxStressMpa: Number(previewPlot?.dataset.seriesMaxStressMpa || 0) },
                axis: { headroomRatio: Number(previewPlot?.dataset.axisHeadroomRatio || 0), maxStrain: Number(previewPlot?.dataset.axisMaxStrain || 0), maxStressMpa: Number(previewPlot?.dataset.axisMaxStressMpa || 0) },
                artifactId: previewPlot?.dataset.artifactId || '',
                artifactSha256: previewPlot?.dataset.artifactSha256 || '',
                curveSelected: previewPlot?.dataset.curveSelected === 'true'
              },
              layoutRevisionId: previewContent?.dataset.layoutRevisionId || '',
              recordRevisionId: previewContent?.dataset.recordRevisionId || '',
              recordTableRevisionId: previewContent?.dataset.recordTableRevisionId || '',
              toggleLabel: document.querySelector('[data-action="preview-toggle"]')?.textContent.trim() || '',
              projectionState: previewContent?.dataset.previewProjection || '',
              returnActions: [...document.querySelectorAll('[data-preview-command], [data-action="preview-close"]')].filter((node) => !node.hidden && node.getBoundingClientRect().width > 0 && node.getBoundingClientRect().height > 0).map((node) => ({ name: node.textContent.trim(), action: node.dataset.action || '', disabled: Boolean(node.disabled), rect: box(node) })),
              composition: (() => {
                if (!editorPane || !editorContent || !previewPanel || !previewContent) return null;
                const previewContentRect = box(previewContent);
                const previewContentStyle = getComputedStyle(previewContent);
                const contentLeft = previewContentRect.x + parseFloat(previewContentStyle.paddingLeft || '0');
                const contentRight = previewContentRect.x + previewContentRect.width - parseFloat(previewContentStyle.paddingRight || '0');
                const activeSectionRect = box(activePreviewSection);
                const activeTableRegionRect = box(activePreviewSection?.querySelector('[data-preview-table-region]'));
                const activeTableScrollRect = box(activePreviewSection?.querySelector('.preview-table-scroll'));
                const graphSectionRect = box(previewGraphSection);
                if (!activeSectionRect || !activeTableRegionRect || !activeTableScrollRect || !graphSectionRect) return null;
                return {
                  editorPane: editorPane,
                  editorContent,
                  previewPanel,
                  previewContent: previewContentRect,
                  recordSection: activeSectionRect,
                  recordTableRegion: activeTableRegionRect,
                  recordTableScroll: activeTableScrollRect,
                  graphSection: graphSectionRect,
                  taskChrome: {
                    content: { left: contentLeft, right: contentRight, width: contentRight - contentLeft },
                    heading: box(previewHeading),
                    tabs: box(document.querySelector('.preview-tabs')),
                    context: box(previewContext),
                    clusterRight: Math.max(activeSectionRect.x + activeSectionRect.width, graphSectionRect.x + graphSectionRect.width)
                  },
                  contentGap: previewContentRect.x - (editorContent.x + editorContent.width),
                  componentGutter: graphSectionRect.x - (activeSectionRect.x + activeSectionRect.width),
                  topAlignmentDelta: graphSectionRect.y - activeSectionRect.y
                };
              })(),
               text: previewText,
            },
            buttons: [...document.querySelectorAll('button')].filter((node) => !node.hidden && node.getBoundingClientRect().width > 0 && node.getBoundingClientRect().height > 0).map((node) => ({ name: node.textContent.trim(), action: node.dataset.action || '', disabled: Boolean(node.disabled), rect: box(node) })),
            conditional: { hasQuantity: Boolean(document.querySelector('[name="quantity"]')), hasStandardUnit: Boolean(document.querySelector('[name="standardUnit"]')), hasMinMax: Boolean(document.querySelector('[name="minimum"]')) && Boolean(document.querySelector('[name="maximum"]')), hasAllowedChoices: Boolean(document.querySelector('[name="allowedChoices"], [name="newAttributeChoices"]')), hasRelatedTable: Boolean(document.querySelector('[name="relatedTable"]')), hasTextLimits: Boolean(document.querySelector('[name="maxLength"]')) || Boolean(document.querySelector('[name="pattern"]')) },
            announcements: { alert: Boolean(document.querySelector('[role="alert"]')), status: Boolean(document.querySelector('[role="status"]')) },
            bodyCss: { overflowX: bodyStyle.overflowX, overflowY: bodyStyle.overflowY, rootOverflowX: rootStyle.overflowX, rootOverflowY: rootStyle.overflowY },
            pageText
          };
        }
        """
    )


def capture_page(browser: Browser, target: str, role: str, state: str, viewport_name: str) -> dict[str, Any]:
    preview = "open" if target.endswith("normal-1920x1080") or "wide-" in target else None
    field = "representative-response" if "wide-" in target else None
    page, console_errors, page_errors = open_page(browser, role, state, viewport_name, preview=preview, field=field)
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
        page.get_by_role("button", name="Add Table", exact=True).click()
        table_add = dom_snapshot(page)
        page.get_by_role("button", name="Cancel", exact=True).click()
        page.locator('[data-object-kind="attributes"]').click()
        page.get_by_role("button", name="Add Attribute", exact=True).click()
        attribute_add = dom_snapshot(page)
        page.locator("[name='newAttributeType']").select_option(label="Record reference")
        attribute_reference_add = dom_snapshot(page)
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
        editor_scroll_rail = page.get_by_role("scrollbar", name="Scroll property editor")
        editor_rail_initial = dom_snapshot(page)["localScroll"]["editorRail"]
        editor_scroll_rail.focus()
        page.keyboard.press("End")
        editor_scroll_after = editor_scroll.evaluate("node => node.scrollTop")
        editor_rail_end = dom_snapshot(page)["localScroll"]["editorRail"]
        page.keyboard.press("Home")
        editor_scroll_home = editor_scroll.evaluate("node => node.scrollTop")
        page.keyboard.press("ArrowDown")
        editor_scroll_arrow_down = editor_scroll.evaluate("node => node.scrollTop")
        editor_rail_arrow_down = dom_snapshot(page)["localScroll"]["editorRail"]
        page.get_by_role("button", name="Save new revision").count()
        wide_page, wide_console_errors, wide_page_errors = open_page(browser, "administrator", "normal", "1920x1080", preview="open", field="representative-response")
        try:
            wide_initial = dom_snapshot(wide_page)
            value_table_scroll = wide_page.locator("[data-preview-values-scroll]")
            value_table_rail = wide_page.get_by_role("scrollbar", name="Scroll saved Record values")
            value_table_rail.focus()
            wide_page.keyboard.press("ArrowDown")
            preview_value_keyboard_scroll = value_table_scroll.evaluate("node => node.scrollTop")
            value_table_rail.press("PageDown")
            preview_value_page_down_scroll = value_table_scroll.evaluate("node => node.scrollTop")
            value_table_rail.press("Home")
            preview_value_home_scroll = value_table_scroll.evaluate("node => node.scrollTop")
            value_table_rail.press("End")
            preview_value_end_scroll = value_table_scroll.evaluate("node => node.scrollTop")
            value_table_rail.press("Home")
            rail_box = value_table_rail.bounding_box()
            if rail_box:
                wide_page.mouse.click(rail_box["x"] + rail_box["width"] / 2, rail_box["y"] + rail_box["height"] * .55)
            preview_value_pointer_scroll = value_table_scroll.evaluate("node => node.scrollTop")
            wide_page.get_by_role("tab", name="Layout definition").click()
            wide_layout = dom_snapshot(wide_page)
            layout_table_scroll = wide_page.locator("[data-preview-layout-scroll]")
            layout_table_rail = wide_page.get_by_role("scrollbar", name="Scroll ordered Layout definition")
            layout_table_rail.hover()
            wide_page.mouse.wheel(0, 120)
            preview_layout_wheel_scroll = layout_table_scroll.evaluate("node => node.scrollTop")
            wide_page.get_by_role("tab", name="Record preview").click()
            wide_page.locator("[data-preview-command]").click()
            wide_hidden = dom_snapshot(wide_page)
            wide_taskbar_return_focus = wide_page.evaluate("() => document.activeElement?.matches('[data-preview-command]') === true")
            wide_page.locator("[data-preview-command]").click()
            wide_reopened = dom_snapshot(wide_page)
            wide_page.locator('[data-object-kind="attributes"]').click()
            wide_page.locator('[data-object-id="density"]').click()
            wide_density = dom_snapshot(wide_page)
            wide_page.locator('[data-object-id="yield-strength"]').click()
            wide_yield = dom_snapshot(wide_page)
            wide_page.goto(f"{HTML_PATH.as_uri()}?state=attribute-draft&preview=open", wait_until="load")
            wide_page.wait_for_timeout(80)
            wide_page.locator("[name='attributeName']").evaluate("(node) => { node.value = 'Density draft label'; node.dispatchEvent(new Event('input', { bubbles: true })); }")
            wide_attribute_draft = dom_snapshot(wide_page)
            wide_page.goto(f"{HTML_PATH.as_uri()}?state=table-add&preview=open", wait_until="load")
            wide_page.wait_for_timeout(80)
            wide_table_add = dom_snapshot(wide_page)
            wide_page.goto(f"{HTML_PATH.as_uri()}?state=empty&preview=open", wait_until="load")
            wide_page.wait_for_timeout(80)
            wide_empty = dom_snapshot(wide_page)
        finally:
            wide_page.context.close()
        compact_page, compact_console_errors, compact_page_errors = open_page(browser, "administrator", "normal", "1440x900")
        try:
            compact_page.locator("[data-preview-command]").click()
            compact_open = dom_snapshot(compact_page)
            compact_page.get_by_role("button", name="Back to editor", exact=True).click()
            compact_closed = dom_snapshot(compact_page)
            compact_return_focus = compact_page.evaluate("() => document.activeElement?.matches('[data-preview-command]') === true")
        finally:
            compact_page.context.close()
        evidence.update({
            "selection_continuity": {"retained_after_refresh": selection_after_refresh == "materials"},
            "add_flows": {
                "table": {
                    "editor_mode": table_add["editorMode"],
                    "editor_title": table_add["editorTitle"],
                    "list_columns": table_add["listColumns"],
                    "selected_row": table_add["selectedRow"]["id"] if table_add["selectedRow"] else None,
                    "field_names": [field["name"] for field in table_add["fields"]],
                },
                "attribute": {
                    "editor_mode": attribute_add["editorMode"],
                    "editor_title": attribute_add["editorTitle"],
                    "list_columns": attribute_add["listColumns"],
                    "selected_row": attribute_add["selectedRow"]["id"] if attribute_add["selectedRow"] else None,
                    "value_type_editable": any(field["name"] == "newAttributeType" and not field["disabled"] and not field["readonly"] for field in attribute_add["fields"]),
                    "discrete_fields": attribute_add["conditional"],
                    "reference_fields": attribute_reference_add["conditional"],
                },
            },
            "conditional_fields": {"number_has_quantity_unit_min_max": attr_snapshot["conditional"]["hasQuantity"] and attr_snapshot["conditional"]["hasStandardUnit"] and attr_snapshot["conditional"]["hasMinMax"], "number_has_no_choices": not attr_snapshot["conditional"]["hasAllowedChoices"], "object_kind": attr_snapshot["editorMode"] == "attribute-draft"},
            "splitter_min_default_max": {"navigator_min": int(min_value or 0), "navigator_max": int(max_value or 0), "navigator_after_arrow": int(adjusted_value or 0), "list_min": int(list_min or 0), "list_max": int(list_max or 0), "list_after_arrow": int(list_adjusted or 0)},
            "local_scroll": {
                "list_scroll_moved": float(list_scroll_after or 0) > 0,
                "list_scroll_not_needed": bool(list_scroll_not_needed),
                "editor_scroll_moved": float(editor_scroll_after or 0) > 0,
                "editor_rail_initial": editor_rail_initial,
                "editor_rail_end": editor_rail_end,
                "editor_home_scroll_top": float(editor_scroll_home or 0),
                "editor_arrow_down_scroll_top": float(editor_scroll_arrow_down or 0),
                "editor_rail_arrow_down": editor_rail_arrow_down,
            },
            "duplicate_submit_blocking": {"blocked": duplicate_blocked},
            "stale_conflict": {"focus_region_present": conflict_focus, "commands": recovery_commands, "local_draft_preserved": local_preserved},
            "wide_preview": {
                "initial_visible": wide_initial["preview"]["visible"],
                "initial_sections": [section["heading"] for section in wide_initial["preview"]["sections"]],
                "initial_projection": wide_initial["preview"].get("activeProjection"),
                "projection_switch": wide_initial["preview"].get("activeProjection") == "record" and wide_layout["preview"].get("activeProjection") == "layout" and wide_layout["preview"].get("activeTable") == "layout",
                "hidden_after_toggle": not wide_hidden["preview"]["visible"] and wide_hidden["preview"]["open"] is False,
                "reopened": wide_reopened["preview"]["visible"] and wide_reopened["preview"]["open"] is True,
                "wide_return_actions": wide_initial["preview"]["returnActions"],
                "wide_taskbar_return_focus": wide_taskbar_return_focus,
                "density_selected_rows": [row["id"] for row in wide_density["preview"]["valueRows"] if row["selected"]],
                "yield_selected_rows": [row["id"] for row in wide_yield["preview"]["valueRows"] if row["selected"]],
                "draft_label_preserves_saved_projection": all(
                    row["label"] == "Density"
                    for rows in (wide_attribute_draft["preview"]["valueRows"],)
                    for row in rows
                    if row["id"] == "density"
                ),
                "draft_saved_value_unchanged": any("7,800 kg/m³" in row["text"] for row in wide_attribute_draft["preview"]["valueRows"] if row["id"] == "density"),
                "table_rails_visible": all(item and item["rail"] and item["rail"]["hidden"] is False and item["rail"]["ariaMax"] > 0 for item in wide_initial["localScroll"]["previewTables"] if item),
                "value_table_keyboard_scroll": float(preview_value_keyboard_scroll or 0) > 0,
                "value_table_page_down_scroll": float(preview_value_page_down_scroll or 0) > float(preview_value_keyboard_scroll or 0),
                "value_table_home_scroll": float(preview_value_home_scroll or 0) == 0,
                "value_table_end_scroll": float(preview_value_end_scroll or 0) > 0,
                "value_table_pointer_scroll": float(preview_value_pointer_scroll or 0) > 0,
                "layout_table_wheel_scroll": float(preview_layout_wheel_scroll or 0) > 0,
                "new_table_has_no_projection": wide_table_add["preview"]["projectionState"] == "unavailable" and not wide_table_add["preview"]["valueRows"] and not wide_table_add["preview"]["layoutRows"] and all(stale not in wide_table_add["preview"]["text"] for stale in ("Materials master", "DP780 synthetic demo steel", "Material datasheet")),
                "empty_has_no_projection": wide_empty["preview"]["projectionState"] == "unavailable" and not wide_empty["preview"]["record"] and not wide_empty["preview"]["table"] and not wide_empty["preview"]["valueRows"] and not wide_empty["preview"]["layoutRows"] and all(stale not in wide_empty["preview"]["text"] for stale in ("Materials master", "DP780 synthetic demo steel", "Material datasheet")),
                "compact_return_actions": compact_open["preview"]["returnActions"],
                "compact_closed_and_focus_returned": not compact_closed["preview"]["visible"] and compact_closed["preview"]["open"] is False and compact_return_focus,
            },
            "page_errors": console_errors + page_errors + wide_console_errors + wide_page_errors + compact_console_errors + compact_page_errors,
        })
    finally:
        page.context.close()
    return evidence


def write_staging(target_results: dict[str, dict[str, Any]], state_results: dict[str, list[dict[str, Any]]], interactions: dict[str, Any], wide_results: dict[str, dict[str, Any]]) -> None:
    existing_status = "pending"
    if STAGING_PATH.exists():
        existing_status = json.loads(STAGING_PATH.read_text(encoding="utf-8")).get("status", existing_status)
    staging = {
        "family": "ADM-SCHEMA-CORE",
        "wave": "WAVE-05",
        "status": existing_status,
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
        "wide_evidence": {
            key: {"state": value["state"], "role": value["role"], "viewport": value["viewport"], "image": wide_results[key]["image"], "measurements": f"docs/17-evidence/images/issue-167-service-reference/{key}.measurements.json", "sha256": wide_results[key]["sha256"]}
            for key, value in WIDE_EVIDENCE.items() if key in wide_results
        },
        "interaction_evidence": interactions,
        "counts": {"approval_targets": len(target_results), "state_targets": len(state_results), "state_captures": sum(len(items) for items in state_results.values())},
    }
    STAGING_PATH.write_text(json.dumps(staging, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    if not (args.target or args.all_packet_targets or args.state_evidence or args.state_target or args.wide_evidence):
        raise SystemExit("choose --target, --all-packet-targets, --state-evidence, --state-target, or --wide-evidence")
    selected_targets = [args.target] if args.target else (list(TARGETS) if args.all_packet_targets else [])
    capture_states = bool(args.all_packet_targets or args.state_evidence)
    target_results: dict[str, dict[str, Any]] = {}
    state_results: dict[str, list[dict[str, Any]]] = {}
    interactions: dict[str, Any] = {}
    wide_results: dict[str, dict[str, Any]] = {}
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        def capture_isolated(target: str, role: str, state: str, viewport_name: str) -> dict[str, Any]:
            last_error: Exception | None = None
            for attempt in range(2):
                browser = playwright.chromium.launch(headless=True)
                try:
                    return capture_page(browser, target, role, state, viewport_name)
                except Exception as error:  # Capture can race Chromium teardown on this Windows host.
                    last_error = error
                    if attempt == 1:
                        raise
                finally:
                    browser.close()
                    time.sleep(0.35)
            raise last_error or RuntimeError(f"capture failed without an error: {target}")

        for target in selected_targets:
            spec = TARGETS[target]
            target_results[target] = capture_isolated(target, spec["role"], spec["state"], spec["viewport"])
        if capture_states:
            for state_target, (role, state) in STATE_EVIDENCE.items():
                state_results[state_target] = []
                for viewport_name in VIEWPORTS:
                    target = f"{state_target}-{viewport_name}"
                    state_results[state_target].append(capture_isolated(target, role, state, viewport_name))
        if args.state_target:
            role, state = STATE_EVIDENCE[args.state_target]
            state_results[args.state_target] = []
            selected_viewports = [args.state_viewport] if args.state_viewport else list(VIEWPORTS)
            for viewport_name in selected_viewports:
                target = f"{args.state_target}-{viewport_name}"
                state_results[args.state_target].append(
                    capture_isolated(target, role, state, viewport_name)
                )
        if args.all_packet_targets or args.state_evidence:
            browser = playwright.chromium.launch(headless=True)
            try:
                interactions = interaction_evidence(browser)
            finally:
                browser.close()
        if args.wide_evidence or args.all_packet_targets:
            for target, spec in WIDE_EVIDENCE.items():
                wide_results[target] = capture_isolated(target, spec["role"], spec["state"], spec["viewport"])
    if args.state_target:
        print(
            f"captured bounded state: {args.state_target}; "
            f"viewports: {', '.join(item['viewport'] for item in state_results[args.state_target])}"
        )
        return
    if target_results or state_results or wide_results:
        write_staging(target_results, state_results, interactions, wide_results)
    print(f"wrote staging: {STAGING_PATH.relative_to(ROOT)}")
    print(f"approval targets: {len(target_results)}; evidence state captures: {sum(len(items) for items in state_results.values())}; wide evidence: {len(wide_results)}")


if __name__ == "__main__":
    main()

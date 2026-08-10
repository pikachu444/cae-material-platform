"""Capture the isolated Issue #221 high-DPI policy comparison packet.

The script runs against canonical Compose and imports the product capture
helpers only for deterministic state setup.  Candidate CSS is evidence-only:
it is injected into a settled live page and is never part of the web bundle.

Run with the explicit on-demand browser and crop dependencies:

    uv run --with playwright==1.62.0 --with pillow==11.3.0 \
      python scripts/capture_high_dpi_decision.py
"""

# Embedded Playwright/PowerShell snippets and exact UI labels intentionally
# exceed Ruff's line length. Crop coordinates are rounded pixel boundaries.
# The capture helper import must follow the local scripts path insertion.
# ruff: noqa: E501, RUF046, I001

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from PIL import Image
from playwright.sync_api import (
    Browser,
    Page,
    Playwright,
    Route,
    TimeoutError as PlaywrightTimeoutError,
    sync_playwright,
)

SCRIPT_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_ROOT.parent
sys.path.insert(0, str(SCRIPT_ROOT))

import capture_current_product as current  # noqa: E402


VIEWPORTS = (*current.VIEWPORTS, *current.WIDE_VIEWPORTS)
WIDE_CROP_VIEWPORTS = frozenset((*current.WIDE_VIEWPORTS, (1920, 1080)))
PROTOTYPE_STYLESHEET = SCRIPT_ROOT / "high_dpi_decision_prototype.css"
DEFAULT_OUTPUT = Path("docs/17-evidence/images/issue-221-high-dpi-decision")
BASE_COMMIT = "ca7c97869522e3fe5d889fdc5f834bd963f85340"
READ_ONLY_POST_PATHS = frozenset({"/api/v1/catalog/records:search"})


@dataclass(frozen=True)
class Variant:
    name: str
    candidate: str | None
    density: str | None


VARIANTS = (
    Variant("baseline", None, None),
    Variant("p1", "p1", "compact"),
    Variant("p2-compact", "p2", "compact"),
    Variant("p2-standard", "p2", "standard"),
    Variant("p2-large", "p2", "large"),
)


@dataclass(frozen=True)
class Surface:
    name: str
    regions: dict[str, str]
    crop_roles: tuple[str, ...]
    administration_kind: str | None = None


SURFACES = {
    "materials-search": Surface(
        "materials-search",
        {
            "navigator": ".materials-workspace-panel.navigator-panel",
            "primary": ".materials-workspace-panel.main-panel",
            "context": ".materials-workspace-panel.context-panel",
            "table": ".materials-result-table",
        },
        ("header", "navigator", "table"),
    ),
    "materials-datasheet": Surface(
        "materials-datasheet",
        {
            "navigator": ".materials-workspace-panel.navigator-panel",
            "primary": ".materials-workspace-panel.main-panel",
            "form": ".material-detail-shell",
            "graph": ".material-detail-shell svg",
            "table": ".material-response-points",
        },
        ("header", "navigator", "form", "graph"),
    ),
    "modeling-data": Surface(
        "modeling-data",
        {
            "navigator": ".modeling-workspace-rail",
            "primary": ".modeling-main-panel",
            "table": ".data-library-list",
            "graph": ".persistent-modeling-plot svg",
        },
        ("header", "navigator", "table", "graph"),
    ),
    "modeling-fit": Surface(
        "modeling-fit",
        {
            "navigator": ".modeling-workspace-rail",
            "primary": ".modeling-main-panel",
            "form": ".modeling-task-ribbon",
            "graph": ".persistent-modeling-plot svg",
        },
        ("header", "navigator", "form", "graph"),
    ),
    "modeling-export": Surface(
        "modeling-export",
        {
            "primary": ".export-main",
            "form": ".export-properties",
            "context": ".export-result",
            "table": ".export-mapping-list",
            "graph": ".export-fit-source svg",
            "preview": ".export-native-preview-shell",
        },
        ("header", "form", "table", "graph", "preview"),
    ),
    "activity-normal": Surface(
        "activity-normal",
        {"primary": "#activity-queue-scroll", "table": ".activity-table"},
        ("header", "table"),
    ),
    "activity-history": Surface(
        "activity-history",
        {"primary": "#activity-queue-scroll", "table": ".activity-table"},
        ("header", "table"),
    ),
    "activity-decision-error": Surface(
        "activity-decision-error",
        {"primary": "#activity-queue-scroll", "table": ".activity-table"},
        ("header", "table"),
    ),
    "activity-recovery": Surface(
        "activity-recovery",
        {"primary": "#activity-queue-scroll", "table": ".activity-recovery-list"},
        ("header", "table"),
    ),
    "administration-database": Surface(
        "administration-database",
        {
            "navigator": ".schema-object-navigator",
            "primary": ".schema-object-list",
            "form": ".schema-property-editor",
            "table": ".schema-list-rows",
        },
        ("header", "navigator", "table", "form"),
        administration_kind="database",
    ),
    "administration-records": Surface(
        "administration-records",
        {
            "navigator": ".catalog-record-grid > .content-card:nth-child(1)",
            "primary": ".catalog-record-grid > .content-card:nth-child(2)",
            "form": ".catalog-record-grid > .content-card:nth-child(3)",
            "table": ".record-result-table",
        },
        ("header", "navigator", "table", "form"),
        administration_kind="records",
    ),
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _manifest_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return resolved.as_posix()


def _json_hash(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _duplicate_image_allowances(output: Path) -> list[dict[str, Any]]:
    """Register exact equal-byte groups that contain Issue #221 evidence.

    Pixel identity is a result for this decision packet: baseline, P1, and P2
    Compact are expected to match where the semantic policy has no visual
    consequence. Keep the original bytes and declare the complete repository
    hash group instead of altering or relabeling an image to evade inventory
    checks.
    """
    image_roots = (
        PROJECT_ROOT / "docs" / "00-research",
        PROJECT_ROOT / "docs" / "17-evidence" / "images",
        PROJECT_ROOT / "docs" / "user-guide" / "images",
    )
    by_hash: dict[str, list[Path]] = {}
    for root in image_roots:
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            if path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg"}:
                by_hash.setdefault(_sha256(path), []).append(path.resolve())

    resolved_output = output.resolve()
    groups = [
        sorted(_manifest_path(path) for path in paths)
        for paths in by_hash.values()
        if len(paths) > 1
        and any(path.is_relative_to(resolved_output) for path in paths)
    ]
    return [
        {
            "rationale": (
                "Issue #221 preserves pixel-identical originals and direct crops when "
                "baseline, P1, or a P2 tier has no rendered consequence for that exact "
                "surface/viewport/role; the complete equal-byte group is retained as "
                "decision evidence and is neither relabeled nor modified."
            ),
            "images": group,
        }
        for group in sorted(groups, key=lambda paths: paths[0])
    ]


def _wait_for_frames(page: Page) -> None:
    page.evaluate(
        """async () => {
          await new Promise(requestAnimationFrame);
          await new Promise(requestAnimationFrame);
          if (document.fonts?.ready) await document.fonts.ready;
        }"""
    )


def _wait_for_zoom_ui_settled(page: Page) -> None:
    """Wait for rendered UI state without requiring polling APIs to go idle."""
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_function(
        """() => {
          const unfinished =
            /^(Checking|Loading|Calculating|Resolving|Updating|Preparing|Creating)\\b.*(?:…|\\.\\.\\.)$/i;
          const visible = element => element.getClientRects().length > 0;
          const textPending = document.body.innerText
            .split("\\n")
            .some(line => unfinished.test(line.trim()));
          const activeStatus = [...document.querySelectorAll('[role="status"], .loading-state')]
            .some(element => visible(element)
              && (element.textContent ?? "").split("\\n")
                .some(line => unfinished.test(line.trim())));
          const activeBusy = [...document.querySelectorAll('[aria-busy="true"]')]
            .some(visible);
          return !activeBusy && !textPending && !activeStatus;
        }""",
        timeout=30_000,
    )
    _wait_for_frames(page)


def _set_variant(page: Page, variant: Variant) -> None:
    page.evaluate(
        """value => {
          const root = document.documentElement;
          if (value.candidate) root.dataset.cmpPrototype = value.candidate;
          else delete root.dataset.cmpPrototype;
          if (value.density) root.dataset.cmpDensity = value.density;
          else delete root.dataset.cmpDensity;
        }""",
        {"candidate": variant.candidate, "density": variant.density},
    )
    _wait_for_frames(page)


def _annotate_semantic_regions(page: Page, surface: Surface) -> None:
    page.evaluate(
        """value => {
          document.querySelectorAll('[data-cmp-region], [data-cmp-prototype-workspace], [data-cmp-prototype-span], [data-cmp-prototype-pane], [data-cmp-prototype-pane-mode]')
            .forEach(element => {
              element.removeAttribute('data-cmp-region');
              element.removeAttribute('data-cmp-prototype-workspace');
              element.removeAttribute('data-cmp-prototype-span');
              element.removeAttribute('data-cmp-prototype-pane');
              element.removeAttribute('data-cmp-prototype-pane-mode');
            });
          for (const [role, selector] of Object.entries(value.regions)) {
            const element = document.querySelector(selector);
            if (element) element.setAttribute('data-cmp-region', role);
          }
          const resizablePanes = document.querySelector('.materials-workspace');
          const contextPane = document.querySelector('.materials-workspace-panel.context-panel')
            ?.closest('[data-panel="true"]');
          resizablePanes?.setAttribute('data-cmp-prototype-workspace', 'resizable-panes');
          contextPane?.setAttribute('data-cmp-prototype-pane', 'context');
          if (value.administrationKind === 'database') {
            document.querySelector('.schema-editor-grid')
              ?.setAttribute('data-cmp-prototype-workspace', 'three-pane');
            document.querySelector('.schema-editor-header')
              ?.setAttribute('data-cmp-prototype-span', 'workspace');
          }
          if (value.administrationKind === 'records') {
            document.querySelector('.catalog-record-grid')
              ?.setAttribute('data-cmp-prototype-workspace', 'three-pane');
            for (const selector of [
              '.record-administration-header',
              '.catalog-search-panel',
              '.registration-panel',
              '.error-banner',
              '.success-banner',
            ]) {
              document.querySelector(selector)
                ?.setAttribute('data-cmp-prototype-span', 'workspace');
            }
          }
        }""",
        {
            "regions": surface.regions,
            "administrationKind": surface.administration_kind,
        },
    )


def _rect_payload(page: Page, selector: str) -> dict[str, float] | None:
    return page.evaluate(
        """selector => {
          const element = document.querySelector(selector);
          if (!element || !element.getClientRects().length) return null;
          const rect = element.getBoundingClientRect();
          return {
            x: rect.x, y: rect.y, width: rect.width, height: rect.height,
            left: rect.left, top: rect.top, right: rect.right, bottom: rect.bottom,
          };
        }""",
        selector,
    )


def _measure(page: Page, surface: Surface, variant: Variant) -> dict[str, Any]:
    return page.evaluate(
        """value => {
          const visible = element => {
            if (!element || !element.getClientRects().length) return false;
            const style = getComputedStyle(element);
            if (style.display === 'none' || style.visibility === 'hidden'
                || Number(style.opacity) === 0 || element.closest('[aria-hidden="true"]')) return false;
            const closed = element.closest('details:not([open])');
            if (!closed) return true;
            const summary = closed.querySelector(':scope > summary');
            return Boolean(summary && summary.contains(element));
          };
          const rect = element => {
            if (!visible(element)) return null;
            const box = element.getBoundingClientRect();
            const style = getComputedStyle(element);
            return {
              x: box.x, y: box.y, width: box.width, height: box.height,
              left: box.left, top: box.top, right: box.right, bottom: box.bottom,
              clientWidth: element.clientWidth, clientHeight: element.clientHeight,
              scrollWidth: element.scrollWidth, scrollHeight: element.scrollHeight,
              overflowX: style.overflowX, overflowY: style.overflowY,
              fontSize: style.fontSize, lineHeight: style.lineHeight,
            };
          };
          const regions = {};
          for (const [role, selector] of Object.entries(value.regions)) {
            regions[role] = rect(document.querySelector(selector));
          }
          regions.header = rect(document.querySelector('.application-menu-bar'));
          const workspace = rect(document.querySelector('.application-workspace'));
          const shell = rect(document.querySelector('.application-shell'));
          const regionBoxes = Object.entries(regions)
            .filter(([name, box]) => name !== 'header' && box)
            .map(([, box]) => box)
            .sort((a, b) => a.left - b.left);
          let maximumHorizontalGap = 0;
          for (let index = 1; index < regionBoxes.length; index += 1) {
            maximumHorizontalGap = Math.max(
              maximumHorizontalGap,
              regionBoxes[index].left - regionBoxes[index - 1].right,
            );
          }
          const union = regionBoxes.length ? {
            left: Math.min(...regionBoxes.map(box => box.left)),
            right: Math.max(...regionBoxes.map(box => box.right)),
            top: Math.min(...regionBoxes.map(box => box.top)),
            bottom: Math.max(...regionBoxes.map(box => box.bottom)),
          } : null;
          const controls = [...document.querySelectorAll('button, input, select, textarea')]
            .filter(visible)
            .slice(0, 250)
            .map(element => {
              const box = element.getBoundingClientRect();
              const style = getComputedStyle(element);
              return { height: box.height, width: box.width, fontSize: style.fontSize };
            });
          const rows = [...document.querySelectorAll('tbody tr, [role="row"], .data-library-row, .record-result, .schema-list-rows > button')]
            .filter(visible)
            .slice(0, 100)
            .map(element => element.getBoundingClientRect().height);
          const percentile = (values, fraction) => {
            if (!values.length) return null;
            const sorted = [...values].sort((a, b) => a - b);
            return sorted[Math.min(sorted.length - 1, Math.floor((sorted.length - 1) * fraction))];
          };
          const typography = [...document.querySelectorAll('main *')]
            .filter(element => visible(element) && element.children.length === 0 && (element.textContent ?? '').trim())
            .slice(0, 500)
            .map(element => getComputedStyle(element).fontSize);
          const typographyCounts = Object.fromEntries(
            [...new Set(typography)].sort((a, b) => parseFloat(a) - parseFloat(b))
              .map(size => [size, typography.filter(value => value === size).length]),
          );
          const tokenNames = [
            '--ux-data-font-size', '--ux-emphasis-font-size', '--ux-metadata-font-size',
            '--ux-table-heading-font-size', '--ux-control-min-block-size',
            '--ux-interactive-min-block-size', '--ux-input-min-block-size',
            '--ux-work-row-min-block-size', '--ux-navigator-row-block-size',
            '--ux-pane-padding', '--ux-cell-padding-block', '--ux-cell-padding-inline',
            '--ux-table-cell-padding-block', '--ux-table-cell-padding-inline',
            '--ux-navigator-default-inline-size', '--ux-context-default-inline-size',
            '--ux-readable-form-max-inline-size', '--ux-splitter-inline-size',
            '--ux-workbench-splitter-size', '--ux-plot-min-block-size',
            '--ux-native-preview-min-block-size',
            '--ux-application-bar-height', '--ux-command-bar-height', '--ux-status-bar-height',
          ];
          const rootStyle = getComputedStyle(document.documentElement);
          const tokenValues = Object.fromEntries(
            tokenNames.map(name => [name, rootStyle.getPropertyValue(name).trim()]),
          );
          const splitters = [...document.querySelectorAll('[role="separator"]')]
            .filter(visible)
            .map(element => {
              const box = element.getBoundingClientRect();
              return { width: box.width, height: box.height, orientation: element.getAttribute('aria-orientation') ?? 'vertical' };
            });
          const table = document.querySelector(value.regions.table ?? 'table');
          const columnWidths = table
            ? [...table.querySelectorAll('thead tr:first-child > th')].map(cell => cell.getBoundingClientRect().width)
            : [];
          const graph = value.regions.graph ? document.querySelector(value.regions.graph) : null;
          const graphBox = graph ? graph.getBoundingClientRect() : null;
          const graphCenterTarget = graphBox
            ? document.elementFromPoint(graphBox.left + graphBox.width / 2, graphBox.top + graphBox.height / 2)
            : null;
          const legendBoxes = graph
            ? [...document.querySelectorAll('.curve-legend, .chart-legend, .fit-source-legend')]
                .filter(visible).map(rect)
            : [];
          const labelBoxes = graph
            ? [...document.querySelectorAll('.chart-axis-label, .chart-tick, .engineering-curve-legend text')]
                .filter(visible).slice(0, 100).map(rect)
            : [];
          const overlaps = [];
          const named = Object.entries(regions).filter(([, box]) => box);
          for (let leftIndex = 0; leftIndex < named.length; leftIndex += 1) {
            for (let rightIndex = leftIndex + 1; rightIndex < named.length; rightIndex += 1) {
              const [leftName, left] = named[leftIndex];
              const [rightName, right] = named[rightIndex];
              if (leftName === 'header' || rightName === 'header') continue;
              if ((leftName === 'primary' && ['table', 'graph', 'preview', 'form'].includes(rightName))
                || (rightName === 'primary' && ['table', 'graph', 'preview', 'form'].includes(leftName))) continue;
              if ((leftName === 'context' && ['table', 'graph'].includes(rightName))
                || (rightName === 'context' && ['table', 'graph'].includes(leftName))) continue;
              const width = Math.min(left.right, right.right) - Math.max(left.left, right.left);
              const height = Math.min(left.bottom, right.bottom) - Math.max(left.top, right.top);
              if (width > 2 && height > 2) overlaps.push({ left: leftName, right: rightName, width, height });
            }
          }
          const documentElement = document.documentElement;
          return {
            candidate: value.variant.candidate ?? 'baseline',
            density: value.variant.density ?? 'baseline',
            url: location.href,
            environment: {
              innerWidth, innerHeight, outerWidth, outerHeight,
              screenWidth: screen.width, screenHeight: screen.height,
              devicePixelRatio,
              visualViewportScale: visualViewport?.scale ?? null,
            },
            shell,
            workspace,
            regions,
            workspaceUse: workspace && union ? {
              usedWidth: union.right - union.left,
              usedWidthRatio: (union.right - union.left) / workspace.width,
              leftGutter: union.left - workspace.left,
              rightGutter: workspace.right - union.right,
              gutterImbalance: Math.abs((union.left - workspace.left) - (workspace.right - union.right)),
              maximumHorizontalGap,
            } : null,
            pageOverflow: {
              x: documentElement.scrollWidth - documentElement.clientWidth,
              y: documentElement.scrollHeight - documentElement.clientHeight,
            },
            controls: {
              count: controls.length,
              minimumHeight: controls.length ? Math.min(...controls.map(item => item.height)) : null,
              lowerQuartileHeight: percentile(controls.map(item => item.height), 0.25),
              medianHeight: percentile(controls.map(item => item.height), 0.5),
              upperQuartileHeight: percentile(controls.map(item => item.height), 0.75),
              maximumHeight: controls.length ? Math.max(...controls.map(item => item.height)) : null,
              fontSizes: [...new Set(controls.map(item => item.fontSize))].sort(),
            },
            rows: {
              count: rows.length,
              minimumHeight: rows.length ? Math.min(...rows) : null,
              medianHeight: percentile(rows, 0.5),
              upperQuartileHeight: percentile(rows, 0.75),
              maximumHeight: rows.length ? Math.max(...rows) : null,
            },
            typography: { count: typography.length, fontSizeCounts: typographyCounts },
            tokenValues,
            splitters,
            table: {
              columnWidths,
              totalColumnWidth: columnWidths.reduce((sum, width) => sum + width, 0),
              localOverflowX: table ? table.scrollWidth - table.clientWidth : null,
            },
            graph: graph ? {
              rect: rect(graph),
              viewBox: graph.getAttribute('viewBox'),
              preserveAspectRatio: graph.getAttribute('preserveAspectRatio'),
              centerHitTag: graphCenterTarget?.tagName ?? null,
              centerHitClass: graphCenterTarget?.getAttribute?.('class') ?? null,
              legendBoxes,
              labelBoxes,
            } : null,
            overlaps,
          };
        }""",
        {
            "regions": surface.regions,
            "variant": {
                "candidate": variant.candidate,
                "density": variant.density,
            },
        },
    )


def _state_fingerprint(page: Page, surface: Surface) -> dict[str, Any]:
    state = page.evaluate(
        r"""surface => {
          const text = selector => document.querySelector(selector)?.textContent?.trim() ?? null;
          const session = sessionStorage.getItem('cmp.modeling.recent-session.v4');
          let parsedSession = null;
          try { parsedSession = session ? JSON.parse(session) : null; } catch { parsedSession = 'invalid'; }
          return {
            surface,
            path: `${location.pathname}${location.search}`,
            title: document.title,
            statusRevision: text('.application-status-bar'),
            mainHeading: text('main h1, main h2'),
            modeling: parsedSession ? {
              material: parsedSession.material ?? null,
              materialState: parsedSession.materialState ?? null,
              testData: parsedSession.testData ?? null,
              mappingProfile: parsedSession.mappingProfile ?? null,
              processingOutput: parsedSession.processingOutput ?? null,
              selection: parsedSession.selection ?? null,
              materialModelIr: parsedSession.materialModelIr ?? null,
            } : null,
            visibleRevisionText: [...document.querySelectorAll('main *')]
              .filter(element => element.children.length === 0 && /\br[1-9]\d*\b/.test(element.textContent ?? ''))
              .slice(0, 30)
              .map(element => element.textContent?.trim()),
          };
        }""",
        surface.name,
    )
    state["sha256"] = _json_hash(state)
    return state


def _crop_original(
    original: Path,
    output: Path,
    box: dict[str, float],
) -> dict[str, Any]:
    with Image.open(original) as image:
        left = max(0, int(round(box["left"])))
        top = max(0, int(round(box["top"])))
        right = min(image.width, int(round(box["right"])))
        bottom = min(image.height, int(round(box["bottom"])))
        if right <= left or bottom <= top:
            raise RuntimeError(f"invalid crop rectangle for {original}: {(left, top, right, bottom)}")
        output.parent.mkdir(parents=True, exist_ok=True)
        image.crop((left, top, right, bottom)).save(output, format="PNG", optimize=False)
    return {
        "path": _manifest_path(output),
        "source_rectangle": {"left": left, "top": top, "right": right, "bottom": bottom},
        "width": right - left,
        "height": bottom - top,
        "sha256": _sha256(output),
        "scale": "100 percent / direct 1:1 source pixels",
        "interpolation": "none",
    }


def _install_write_guard(page: Page, writes: list[dict[str, str]]) -> None:
    def guard(route: Route) -> None:
        request = route.request
        request_path = re.sub(r"^https?://[^/]+", "", request.url).split("?", 1)[0]
        if request.method in {"GET", "HEAD", "OPTIONS"} or (
            request.method == "POST" and request_path in READ_ONLY_POST_PATHS
        ):
            route.continue_()
            return
        writes.append({"method": request.method, "url": request.url})
        route.abort("blockedbyclient")

    page.route("**/api/v1/**", guard)


def _capture_surface(
    page: Page,
    surface: Surface,
    width: int,
    height: int,
    output: Path,
    measurements: list[dict[str, Any]],
    images: list[dict[str, Any]],
    crops: list[dict[str, Any]],
    fingerprints: list[dict[str, Any]],
    writes: list[dict[str, str]],
) -> None:
    page.add_style_tag(path=str(PROTOTYPE_STYLESHEET))
    _annotate_semantic_regions(page, surface)
    fingerprint = _state_fingerprint(page, surface)
    fingerprints.append(fingerprint)
    _install_write_guard(page, writes)

    fingerprint["viewport"] = f"{width}x{height}"
    fingerprint["comparison_group"] = f"{surface.name}:{width}x{height}"

    # Current main is always measured first. All candidates then reuse this
    # exact page, API state, session state, and viewport.
    for variant in VARIANTS:
        _set_variant(page, variant)
        current._wait_for_settled(page)
        measured = _measure(page, surface, variant)
        measured.update(
            {
                "surface": surface.name,
                "viewport": f"{width}x{height}",
                "state_fingerprint": fingerprint["sha256"],
                "comparison_group": fingerprint["comparison_group"],
            }
        )
        measurements.append(measured)
        destination = (
            output
            / "originals"
            / variant.name
            / surface.name
            / f"{surface.name}-{width}x{height}.png"
        )
        destination.parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(destination), full_page=False, animations="disabled")
        with Image.open(destination) as image:
            if image.size != (width, height):
                raise RuntimeError(
                    f"viewport image drift for {destination}: {image.size} != {(width, height)}"
                )
        image_record = {
            "path": _manifest_path(destination),
            "surface": surface.name,
            "variant": variant.name,
            "viewport": f"{width}x{height}",
            "width": width,
            "height": height,
            "sha256": _sha256(destination),
            "state_fingerprint": fingerprint["sha256"],
            "comparison_group": fingerprint["comparison_group"],
        }
        images.append(image_record)
        if (width, height) not in WIDE_CROP_VIEWPORTS:
            continue
        for role in surface.crop_roles:
            box = measured["regions"].get(role)
            if box is None:
                continue
            crop_path = (
                output
                / "crops"
                / variant.name
                / surface.name
                / f"{surface.name}-{width}x{height}-{role}-100pct.png"
            )
            crop = _crop_original(destination, crop_path, box)
            crop.update(
                {
                    "surface": surface.name,
                    "variant": variant.name,
                    "viewport": f"{width}x{height}",
                    "role": role,
                    "source": _manifest_path(destination),
                }
            )
            crops.append(crop)

    _set_variant(page, VARIANTS[0])


def _new_page(
    browser: Browser,
    base_url: str,
    width: int,
    height: int,
    *,
    persona: str = "administrator",
) -> Page:
    return current._new_page(browser, base_url, width, height, persona=persona)


def _setup_materials_search(page: Page, base_url: str) -> None:
    current._open_materials_search(page, base_url)


def _setup_materials_datasheet(
    page: Page,
    base_url: str,
    setup_retries: list[dict[str, Any]],
) -> None:
    try:
        current._open_material_detail(page, base_url)
        return
    except PlaywrightTimeoutError as error:
        probe = page.evaluate(
            """async ({ baseUrl }) => {
              const config = JSON.parse(
                localStorage.getItem('cmp.material-platform.api-config') || '{}'
              );
              const url = new URL(location.href);
              const recordId = url.searchParams.get('record_id');
              const revisionId = url.searchParams.get('record_revision_id');
              if (!recordId || !revisionId) return { status: 0, recordId, revisionId };
              const response = await fetch(
                `${baseUrl}/api/v1/catalog/workflow-explorer/${recordId}`
                  + `/revisions/${revisionId}?depth=6&published_only=true`,
                { headers: { Accept: 'application/json', Authorization: `Bearer ${config.accessToken}` } },
              );
              const text = await response.text();
              let nodeCount = null;
              if (response.ok) {
                const graph = JSON.parse(text);
                nodeCount = (graph.nodes || []).length;
              }
              return { status: response.status, recordId, revisionId, nodeCount, detail: text.slice(0, 500) };
            }""",
            {"baseUrl": base_url},
        )
        if not isinstance(probe, dict) or probe.get("status") != 200:
            raise RuntimeError(
                f"Materials datasheet timed out and exact published graph did not read back: {probe!r}"
            ) from error
        setup_retries.append(
            {
                "surface": "materials-datasheet",
                "reason": (
                    "UI detail readiness timed out; exact published graph read-back "
                    "passed before an extended semantic UI wait"
                ),
                **probe,
            }
        )
        page.get_by_role("heading", name="Key properties", exact=True).wait_for(
            timeout=90_000
        )
        for tab_name in ("Overview", "Properties", "Curves", "CAE Cards", "Evidence"):
            page.get_by_role("tab", name=tab_name, exact=True).wait_for(timeout=30_000)
        _wait_for_zoom_ui_settled(page)
        page.get_by_text(
            re.compile(
                r"^(Request review|Waiting for review|Approved|Changes requested)$"
            )
        ).first.wait_for(timeout=30_000)
        page.locator(".application-status-bar").get_by_text(
            current.REVISION_LABEL_PATTERN
        ).wait_for(timeout=30_000)
        for selector in (
            ".material-detail-header",
            '[aria-label="Related exact records"]',
            ".application-status-bar",
        ):
            region = page.locator(selector)
            region.wait_for(timeout=30_000)
            region_text = region.inner_text()
            if current.NORMAL_SURFACE_TECHNICAL_LABELS.search(region_text):
                raise RuntimeError(
                    "normal Material detail surface exposes technical label in "
                    f"{selector}: {region_text}"
                ) from error


def _ensure_published_material_workflow(page: Page, base_url: str) -> dict[str, Any]:
    """Recover the append-only demo publication left pending by its E2E flow.

    The canonical review-publication-recovery Playwright test intentionally
    finishes with a new Record revision awaiting a Reviewer decision.  A
    visual packet needs the normal published datasheet, so this setup approves
    that already-requested exact revision and appends exact source pointers to
    its existing active links. It never deletes or overwrites a revision.
    """

    result = page.evaluate(
        """async ({ baseUrl }) => {
          const api = `${baseUrl}/api/v1`;
          const token = async persona => {
            const response = await fetch(`${api}/demo-identity/token?persona=${persona}`);
            if (!response.ok) throw new Error(`demo identity ${persona}: ${response.status}`);
            return (await response.json()).access_token;
          };
          const [administratorToken, reviewerToken] = await Promise.all([
            token('administrator'), token('reviewer'),
          ]);
          const call = async (accessToken, path, options = {}) => {
            const response = await fetch(`${api}${path}`, {
              method: options.method || 'GET',
              headers: {
                Accept: 'application/json',
                Authorization: `Bearer ${accessToken}`,
                ...(options.body === undefined ? {} : { 'Content-Type': 'application/json' }),
                ...(options.headers || {}),
              },
              body: options.body === undefined ? undefined : JSON.stringify(options.body),
            });
            const text = await response.text();
            if (!response.ok) throw new Error(`${options.method || 'GET'} ${path}: ${response.status} ${text.slice(0, 500)}`);
            return { data: text ? JSON.parse(text) : {}, headers: Object.fromEntries(response.headers.entries()) };
          };
          const tables = await call(administratorToken, '/catalog/tables?limit=50');
          const table = (tables.data.items || []).find(item =>
            item.current_revision?.content?.key === 'demo_material_records');
          if (!table) throw new Error('canonical Material Records table is missing');
          const search = await call(administratorToken, '/catalog/records:search', {
            method: 'POST',
            body: {
              table_id: table.table_id,
              text: 'CMP-DEMO-DP780',
              domain_binding_kind: 'material',
              published_only: false,
              limit: 100,
            },
          });
          const record = (search.data.items || []).find(item =>
            item.domain_binding?.kind === 'material'
            && item.current_revision?.content?.external_key === 'CMP-DEMO-DP780');
          if (!record) throw new Error('canonical DP780 Material Record is missing');
          const recordId = record.record_id;
          const revision = record.current_revision;
          const graphPath = `/catalog/workflow-explorer/${recordId}/revisions/${revision.id}?depth=6&published_only=true`;
          const published = await fetch(`${api}${graphPath}`, {
            headers: { Accept: 'application/json', Authorization: `Bearer ${reviewerToken}` },
          });
          if (published.ok) {
            const graph = await published.json();
            if (graph.root?.record_revision_id !== revision.id || !(graph.nodes || []).length) {
              throw new Error('published workflow read-back does not pin the current exact revision');
            }
            return {
              status: 'reused',
              recordId,
              revisionId: revision.id,
              revisionNo: revision.revision_no,
              linkRevisionsAppended: [],
              reviewDecisionAppended: null,
              nodeCount: graph.nodes.length,
            };
          }
          if (published.status !== 404) {
            throw new Error(`published workflow probe: ${published.status} ${(await published.text()).slice(0, 500)}`);
          }

          const links = await call(
            administratorToken,
            `/catalog/records/${recordId}/links?include_inactive=true`,
          );
          const linkRevisionsAppended = [];
          for (const link of links.data.items || []) {
            const linkRevision = link.current_revision;
            const content = linkRevision?.content;
            if (!content?.active || content.source_record_id !== recordId
                || content.source_record_revision_id === revision.id) continue;
            const etag = `"revision:${linkRevision.revision_no}:sha256:${linkRevision.content_hash}"`;
            const revised = await call(
              administratorToken,
              `/catalog/record-links/${link.record_link_id}/revisions`,
              {
                method: 'POST',
                headers: { 'If-Match': etag },
                body: {
                  content: { ...content, source_record_revision_id: revision.id },
                  change_reason: 'Reconnect exact links for Issue 221 canonical visual evidence',
                },
              },
            );
            linkRevisionsAppended.push({
              recordLinkId: link.record_link_id,
              revisionId: revised.data.current_revision?.id,
              sourceRecordRevisionId: revised.data.current_revision?.content?.source_record_revision_id,
            });
          }

          const reviews = await call(
            reviewerToken,
            `/review-requests?aggregate_type=catalog.configurable_record&aggregate_id=${recordId}&limit=200`,
          );
          const pending = (reviews.data.items || []).filter(item =>
            item.revision_id === revision.id && !item.decision);
          let reviewDecisionAppended = null;
          if (pending.length === 1) {
            const review = pending[0];
            const decided = await call(
              reviewerToken,
              `/review-requests/${review.review_request_id}/decisions`,
              {
                method: 'POST',
                body: {
                  expected_manifest_sha256: review.manifest_sha256,
                  decision: 'approved',
                  reason: 'Approve the exact synthetic demo revision for Issue 221 visual comparison',
                },
              },
            );
            reviewDecisionAppended = decided.data.decision?.review_decision_id
              || decided.data.review_decision_id
              || review.review_request_id;
          } else if (pending.length > 1) {
            throw new Error(`current exact Record has ${pending.length} pending reviews`);
          }

          const graph = (await call(reviewerToken, graphPath)).data;
          if (graph.root?.record_revision_id !== revision.id || !(graph.nodes || []).length) {
            throw new Error('recovered workflow does not pin the current exact revision and nodes');
          }
          return {
            status: 'recovered_append_only',
            recordId,
            revisionId: revision.id,
            revisionNo: revision.revision_no,
            linkRevisionsAppended,
            reviewDecisionAppended,
            nodeCount: graph.nodes.length,
          };
        }""",
        {"baseUrl": base_url},
    )
    if not isinstance(result, dict) or result.get("status") not in {
        "reused",
        "recovered_append_only",
    }:
        raise RuntimeError(f"unexpected canonical Materials setup result: {result!r}")
    return result


def _setup_activity_normal(page: Page, base_url: str) -> None:
    current._ensure_activity_review_fixture(page, base_url)
    page.goto(f"{base_url}/activity")
    _wait_for_activity_view(page)


def _wait_for_activity_view(
    page: Page,
    *,
    view: str = "needs-attention",
    expect_review_action: bool = True,
) -> None:
    labels = {
        "needs-attention": "Needs attention",
        "in-progress": "In progress",
        "recent-outcomes": "Recent outcomes",
    }
    page.locator(".activity-heading h1").filter(has_text="Activity").wait_for(
        timeout=30_000
    )
    tab = page.get_by_role("tab", name=labels[view], exact=True)
    tab.click()
    page.wait_for_function(
        """value => document.querySelector(`#view-${value}`)?.getAttribute('aria-selected') === 'true'""",
        arg=view,
        timeout=30_000,
    )
    panel = page.locator(f"#section-{view}")
    panel.wait_for(state="visible", timeout=30_000)
    panel.get_by_role("heading", name=labels[view], exact=True).wait_for(
        timeout=30_000
    )
    page.locator("#activity-queue-scroll").wait_for(state="visible", timeout=30_000)
    if expect_review_action:
        panel.get_by_role("button", name="Review", exact=True).first.wait_for(
            timeout=30_000
        )


def _setup_activity_history(page: Page, base_url: str) -> None:
    current._ensure_activity_review_fixture(page, base_url)
    current._seed_activity_delivery_history(page)
    current._seed_activity_recovery_history(page, base_url)
    page.goto(f"{base_url}/activity")
    _wait_for_activity_view(page)
    current._wait_for_settled(page)
    _wait_for_activity_view(
        page, view="recent-outcomes", expect_review_action=False
    )


def _setup_activity_decision_error(page: Page, base_url: str) -> None:
    current._ensure_activity_review_fixture(page, base_url)
    page.route(
        "**/api/v1/review-requests/*/decisions",
        lambda route: route.fulfill(
            status=503,
            content_type="application/problem+json",
            body=json.dumps(
                {
                    "title": "Review service unavailable",
                    "status": 503,
                    "detail": "The selected request and reason remain available; retry when the review service is available.",
                }
            ),
        ),
    )
    page.goto(f"{base_url}/activity")
    _wait_for_activity_view(page)
    page.get_by_role("button", name="Review", exact=True).first.click()
    reason = page.get_by_role("textbox", name="Review reason", exact=True)
    reason.fill(
        "Units, source text, test condition, and exact revision are complete; retain this reason while the review service recovers."
    )
    page.get_by_role("button", name="Approve", exact=True).click()
    page.get_by_role("alert").wait_for(timeout=30_000)


def _setup_activity_recovery(page: Page, base_url: str) -> None:
    page.evaluate(
        """async ({ baseUrl }) => {
          const config = JSON.parse(localStorage.getItem('cmp.material-platform.api-config') || '{}');
          const response = await fetch(`${baseUrl}/api/v1/me`, {
            headers: { Accept: 'application/json', Authorization: `Bearer ${config.accessToken}` },
          });
          if (!response.ok) throw new Error(`cannot read Activity principal: ${response.status}`);
          const principal = await response.json();
          const key = `cmp.activity.recovery.v1:${principal.organization_id}:${principal.project_id}:${principal.principal_id}:activity`;
          localStorage.setItem(key, JSON.stringify([{
            schemaVersion: 1,
            id: 'activity-density-recovery',
            principalId: principal.principal_id,
            organizationId: principal.organization_id,
            projectId: principal.project_id,
            workspace: 'activity',
            context: {
              kind: 'selected_model_json',
              path: '/modeling?stage=fit&family=metal',
              materialModelId: 'dp780-selected-model',
              materialModelRevisionId: 'dp780-selected-model-r3',
              target: 'selected-model.json',
            },
            status: 'failed',
            message: 'Selected model download failed; the exact model revision remains selected for retry.',
            occurredAt: '2026-08-09T05:35:00Z',
          }]));
        }""",
        {"baseUrl": base_url},
    )
    page.goto(f"{base_url}/activity")
    _wait_for_activity_view(page)
    page.get_by_role("heading", name="Recovery needed", exact=True).wait_for(timeout=30_000)
    page.get_by_role("button", name="Open exact selection", exact=True).wait_for(timeout=30_000)


def _setup_administration_database(page: Page, base_url: str) -> None:
    page.goto(f"{base_url}/administration/database")
    page.get_by_role("heading", name="Database design", exact=True).wait_for(timeout=30_000)
    page.get_by_role("navigation", name="Database objects").wait_for(timeout=30_000)
    page.locator(".schema-property-editor .property-sheet").wait_for(timeout=30_000)


def _setup_administration_records(page: Page, base_url: str) -> None:
    page.goto(f"{base_url}/administration/records")
    page.get_by_role("heading", name="Single entry or multiple rows", exact=True).wait_for(timeout=30_000)
    rows = page.locator(".record-result")
    rows.first.wait_for(state="visible", timeout=30_000)
    rows.first.click()
    page.get_by_role("heading", name=re.compile(r"^Edit revision \d+$")).wait_for(
        state="visible", timeout=30_000
    )


def _collect_windows_display_metadata() -> dict[str, Any]:
    if os.name != "nt":
        return {"platform": os.name, "status": "not-windows"}
    script = r"""
      Add-Type -AssemblyName System.Windows.Forms
      $screens = [System.Windows.Forms.Screen]::AllScreens | ForEach-Object {
        [pscustomobject]@{
          device_name = $_.DeviceName
          primary = $_.Primary
          bounds = [pscustomobject]@{ width = $_.Bounds.Width; height = $_.Bounds.Height }
          working_area = [pscustomobject]@{ width = $_.WorkingArea.Width; height = $_.WorkingArea.Height }
        }
      }
      $ids = Get-CimInstance -Namespace root\wmi -ClassName WmiMonitorID -ErrorAction SilentlyContinue | ForEach-Object {
        $decode = { param($value) -join ($value | Where-Object { $_ -ne 0 } | ForEach-Object { [char]$_ }) }
        [pscustomobject]@{
          instance = $_.InstanceName
          manufacturer = & $decode $_.ManufacturerName
          product_code = & $decode $_.ProductCodeID
          serial = & $decode $_.SerialNumberID
          user_friendly_name = & $decode $_.UserFriendlyName
          active = $_.Active
        }
      }
      $sizes = Get-CimInstance -Namespace root\wmi -ClassName WmiMonitorBasicDisplayParams -ErrorAction SilentlyContinue | ForEach-Object {
        [pscustomobject]@{
          instance = $_.InstanceName
          horizontal_cm = $_.MaxHorizontalImageSize
          vertical_cm = $_.MaxVerticalImageSize
          active = $_.Active
        }
      }
      $desktop = Get-ItemProperty 'HKCU:\Control Panel\Desktop' -ErrorAction SilentlyContinue
      [pscustomobject]@{
        screens = @($screens)
        monitor_ids = @($ids)
        physical_sizes = @($sizes)
        log_pixels = $desktop.LogPixels
        win8_dpi_scaling = $desktop.Win8DpiScaling
      } | ConvertTo-Json -Depth 8 -Compress
    """
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", script],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if result.returncode:
        return {"status": "error", "detail": (result.stderr or result.stdout).strip()}
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"status": "error", "detail": "display metadata was not valid JSON"}
    value["physical_4k_available"] = any(
        screen.get("bounds", {}).get("width") == 3840
        and screen.get("bounds", {}).get("height") == 2160
        for screen in value.get("screens", [])
    )
    value["physical_evidence_status"] = (
        "COMPLETE" if value["physical_4k_available"] else "DEFERRED_TO_223"
    )
    return value


def _run_materials_interaction_audit(page: Page) -> dict[str, Any]:
    page.set_viewport_size({"width": 1920, "height": 1080})
    _set_variant(page, VARIANTS[1])
    navigator = page.locator(".materials-workspace-panel.navigator-panel")
    separator = page.locator(".materials-resize-handle").first
    separator_label = separator.get_attribute("aria-label")
    if not separator_label or not separator_label.startswith("Resize "):
        raise RuntimeError("Materials navigator separator has no semantic resize label")
    navigator_label = separator_label.removeprefix("Resize ")
    storage_before = page.evaluate(
        "() => Object.fromEntries(Object.entries(localStorage).filter(([key]) => key.includes('cmp-materials-results-v5')))"
    )
    before = navigator.bounding_box()
    separator.focus()
    separator.press("ArrowRight")
    separator.press("ArrowRight")
    _wait_for_frames(page)
    resized = navigator.bounding_box()
    collapse = page.get_by_role(
        "button", name=f"Collapse {navigator_label} pane", exact=True
    )
    collapse.click()
    expand = page.get_by_role(
        "button", name=f"Expand {navigator_label} pane", exact=True
    )
    expand.wait_for(timeout=10_000)
    collapsed_box = navigator.bounding_box()
    collapsed = collapsed_box is None or collapsed_box["width"] <= 1
    expand.click()
    navigator.wait_for(state="visible", timeout=10_000)
    separator.dblclick()
    _wait_for_frames(page)
    reset = navigator.bounding_box()
    return {
        "before": before,
        "separator_label": separator_label,
        "after_keyboard_resize": resized,
        "collapsed": collapsed,
        "collapsed_box": collapsed_box,
        "after_double_click_reset": reset,
        "local_storage_before": storage_before,
        "local_storage_after": page.evaluate(
            "() => Object.fromEntries(Object.entries(localStorage).filter(([key]) => key.includes('cmp-materials-results-v5')))"
        ),
    }


def _run_modeling_interaction_audit(page: Page) -> dict[str, Any]:
    page.set_viewport_size({"width": 1920, "height": 1080})
    current._wait_for_settled(page)
    _set_variant(page, VARIANTS[1])
    navigator = page.locator(".modeling-workspace-rail")
    navigator_restored_for_audit = False
    if navigator.count() == 0 or not navigator.is_visible():
        expand = page.get_by_role(
            "button", name="Expand curve and process navigator", exact=True
        )
        expand.click()
        navigator.wait_for(state="visible", timeout=10_000)
        navigator_restored_for_audit = True
    graph = page.locator(".persistent-modeling-plot svg")
    navigator_separator = page.get_by_role(
        "separator", name="Resize curve and process navigator", exact=True
    )
    data_separator = page.get_by_role(
        "separator", name="Resize Test Data controls and curve plot", exact=True
    )
    before_navigator = navigator.bounding_box()
    before_graph = graph.bounding_box()
    graph_before_metrics = _measure(
        page, SURFACES["modeling-data"], VARIANTS[1]
    )["graph"]
    storage_before = page.evaluate(
        "() => Object.fromEntries(Object.entries(localStorage).filter(([key]) => key.includes('modeling-workspace-v1')))"
    )
    navigator_separator.focus()
    navigator_separator.press("ArrowRight")
    data_separator.focus()
    data_separator.press("ArrowUp")
    _wait_for_frames(page)
    resized_navigator = navigator.bounding_box()
    resized_graph = graph.bounding_box()
    graph_resized_metrics = _measure(
        page, SURFACES["modeling-data"], VARIANTS[1]
    )["graph"]
    data_separator.dblclick()
    _wait_for_frames(page)
    graph_reset_metrics = _measure(
        page, SURFACES["modeling-data"], VARIANTS[1]
    )["graph"]
    collapse = page.get_by_role(
        "button", name="Collapse curve and process navigator", exact=True
    )
    collapse.click()
    collapsed_box = navigator.bounding_box()
    collapsed = collapsed_box is None or collapsed_box["width"] <= 1
    page.get_by_role(
        "button", name="Expand curve and process navigator", exact=True
    ).click()
    navigator.wait_for(state="visible", timeout=10_000)
    return {
        "navigator_restored_for_audit": navigator_restored_for_audit,
        "navigator_before": before_navigator,
        "navigator_after_keyboard_resize": resized_navigator,
        "navigator_collapsed": collapsed,
        "navigator_collapsed_box": collapsed_box,
        "navigator_reset": "not exposed by current main; #184 implementation input",
        "graph_before": before_graph,
        "graph_before_metrics": graph_before_metrics,
        "graph_after_keyboard_resize": resized_graph,
        "graph_after_keyboard_resize_metrics": graph_resized_metrics,
        "graph_after_reset": graph.bounding_box(),
        "graph_after_reset_metrics": graph_reset_metrics,
        "local_storage_before": storage_before,
        "local_storage_after": page.evaluate(
            "() => Object.fromEntries(Object.entries(localStorage).filter(([key]) => key.includes('modeling-workspace-v1')))"
        ),
    }


def _setup_modeling_data(
    page: Page,
    base_url: str,
    setup_retries: list[dict[str, Any]],
) -> None:
    try:
        current._prepare_modeling(page, base_url)
        return
    except PlaywrightTimeoutError as error:
        probe = page.evaluate(
            """() => {
              const raw = sessionStorage.getItem('cmp.modeling.recent-session.v4');
              const workspace = raw ? (JSON.parse(raw).workspace || {}) : {};
              return {
                selectedRefs: workspace.selectedTestDataRefs?.length ?? -1,
                includedIds: workspace.selectedDocumentIds?.length ?? -1,
                visibleKeys: workspace.visibleTestDataKeys?.length ?? -1,
                includedControls: document.querySelectorAll(
                  '.modeling-workspace-rail .curve-include-toggle input:checked'
                ).length,
                visibleControls: document.querySelectorAll(
                  '.modeling-workspace-rail .curve-visibility-toggle[aria-pressed="true"]'
                ).length,
                lines: document.querySelectorAll('.curve-line.data-observed').length,
                legends: document.querySelectorAll(
                  '.persistent-modeling-plot .curve-legend.interactive button'
                ).length,
                error: document.querySelector('.error-banner')?.textContent?.trim() || null,
              };
            }"""
        )
        expected = {
            "selectedRefs": 3,
            "includedIds": 2,
            "visibleKeys": 3,
            "includedControls": 2,
            "visibleControls": 3,
        }
        if (
            not isinstance(probe, dict)
            or probe.get("error")
            or any(probe.get(key) != value for key, value in expected.items())
        ):
            raise RuntimeError(
                "Modeling Data timed out without the exact preserved session needed "
                f"for a read-only plot retry: {probe!r}"
            ) from error

        before = current._data_session_snapshot(page)
        page.reload(wait_until="domcontentloaded")
        current._wait_for_modeling_data_surface(page)
        page.locator(".data-library-list .data-library-row").first.wait_for(timeout=30_000)
        page.wait_for_function(
            """() => document.querySelectorAll(
              '.modeling-workspace-rail .curve-include-toggle input:checked'
            ).length === 2 && document.querySelectorAll(
              '.modeling-workspace-rail .curve-visibility-toggle[aria-pressed="true"]'
            ).length === 3 && document.querySelectorAll(
              '.curve-line.data-observed'
            ).length === 3 && document.querySelectorAll(
              '.persistent-modeling-plot .curve-legend.interactive button'
            ).length === 3""",
            timeout=60_000,
        )
        _wait_for_zoom_ui_settled(page)
        after = current._data_session_snapshot(page)
        if after != before:
            raise RuntimeError(
                "Modeling Data exact session changed during the read-only plot retry: "
                f"before={before!r}, after={after!r}"
            ) from error
        viewport = page.viewport_size
        if viewport is None:
            raise RuntimeError("Modeling Data retry lost its viewport size") from error
        current._assert_modeling_data_surface(
            page, viewport["width"], viewport["height"]
        )
        setup_retries.append(
            {
                "surface": "modeling-data",
                "reason": (
                    "plot readiness timed out after route reload; exact session and "
                    "control state passed before one read-only reload retry"
                ),
                "probe": probe,
                "preserved_session": before,
            }
        )


def _setup_modeling_fit(page: Page, base_url: str, width: int, height: int) -> None:
    current._prepare_fit_for_export(
        page,
        base_url,
        label=f"Issue 221 Fit source {width}x{height}",
    )


def _setup_modeling_export(page: Page, base_url: str, width: int, height: int) -> None:
    current._prepare_fit_for_export(
        page,
        base_url,
        label=f"Issue 221 Export source {width}x{height}",
    )
    current._save_exact_fit_selection(
        page, candidate_key="swift+voce", require_warning=False
    )
    current._open_modeling_stage(page, "export")
    page.wait_for_url(re.compile(r"stage=export"), timeout=30_000)
    current._prepare_exact_metal_source_if_needed(page)
    current._prepare_exact_target_preview(page)


def _browser_zoom_100_signal(page: Page) -> dict[str, Any]:
    return page.evaluate(
        """() => ({
          declaredBrowserZoomPercent: 100,
          innerWidth, innerHeight, outerWidth, outerHeight,
          devicePixelRatio,
          screenWidth: screen.width, screenHeight: screen.height,
          visualViewportScale: visualViewport?.scale ?? null,
          documentWidth: document.documentElement.clientWidth,
          documentScrollWidth: document.documentElement.scrollWidth,
        })"""
    )


def _restore_zoom_surface(
    page: Page,
    surface: Surface,
    source_url: str,
    base_url: str,
    setup_retries: list[dict[str, Any]],
) -> None:
    if surface.name == "activity-decision-error":
        page.goto(base_url)
        _setup_activity_decision_error(page, base_url)
        return

    page.goto(source_url, wait_until="domcontentloaded")
    if surface.name == "materials-search":
        page.locator(".materials-result-table tbody tr").first.wait_for(timeout=30_000)
    elif surface.name == "materials-datasheet":
        page.locator(".material-detail-shell").wait_for(timeout=30_000)
        page.get_by_role("heading", name="Key properties", exact=True).wait_for(
            timeout=90_000
        )
    elif surface.name == "modeling-data":
        current._wait_for_modeling_data_surface(page)
        page.locator(".data-library-list .data-library-row").first.wait_for(timeout=90_000)
        try:
            current._wait_for_data_plot(page)
        except PlaywrightTimeoutError as error:
            probe = page.evaluate(
                """() => {
                  const raw = sessionStorage.getItem('cmp.modeling.recent-session.v4');
                  const workspace = raw ? (JSON.parse(raw).workspace || {}) : {};
                  return {
                    selectedRefs: workspace.selectedTestDataRefs?.length ?? -1,
                    includedIds: workspace.selectedDocumentIds?.length ?? -1,
                    visibleKeys: workspace.visibleTestDataKeys?.length ?? -1,
                    lines: document.querySelectorAll('.curve-line.data-observed').length,
                    legends: document.querySelectorAll(
                      '.persistent-modeling-plot .curve-legend.interactive button'
                    ).length,
                    error: document.querySelector('.error-banner')?.textContent?.trim() || null,
                  };
                }"""
            )
            expected = {"selectedRefs": 3, "includedIds": 2, "visibleKeys": 3}
            if (
                not isinstance(probe, dict)
                or probe.get("error")
                or any(probe.get(key) != value for key, value in expected.items())
            ):
                raise RuntimeError(
                    "Modeling Data zoom restore timed out without the exact preserved "
                    f"session needed for a read-only retry: {probe!r}"
                ) from error
            before = current._data_session_snapshot(page)
            page.reload(wait_until="domcontentloaded")
            current._wait_for_modeling_data_surface(page)
            page.locator(".data-library-list .data-library-row").first.wait_for(
                timeout=30_000
            )
            page.wait_for_function(
                """() => document.querySelectorAll(
                  '.curve-line.data-observed'
                ).length === 3 && document.querySelectorAll(
                  '.persistent-modeling-plot .curve-legend.interactive button'
                ).length === 3""",
                timeout=60_000,
            )
            after = current._data_session_snapshot(page)
            if after != before:
                raise RuntimeError(
                    "Modeling Data exact session changed during the zoom plot retry: "
                    f"before={before!r}, after={after!r}"
                ) from error
            setup_retries.append(
                {
                    "surface": "modeling-data-zoom-200",
                    "reason": (
                        "plot readiness timed out in the zoom context; exact session "
                        "passed before one read-only reload retry"
                    ),
                    "probe": probe,
                    "preserved_session": before,
                }
            )
    elif surface.name == "modeling-fit":
        page.locator(".modeling-workspace-stage-fit").wait_for(timeout=30_000)
        page.locator(".persistent-modeling-plot svg").wait_for(timeout=30_000)
    elif surface.name == "modeling-export":
        page.locator(".export-main").wait_for(timeout=30_000)
        current._prepare_exact_metal_source_if_needed(page)
        current._prepare_exact_target_preview(page)
        page.get_by_label("Native preview", exact=True).locator("pre").wait_for(
            timeout=30_000
        )
    elif surface.name == "activity-history":
        _wait_for_activity_view(page)
        _wait_for_zoom_ui_settled(page)
        _wait_for_activity_view(
            page, view="recent-outcomes", expect_review_action=False
        )
    elif surface.name == "activity-recovery":
        _wait_for_activity_view(page)
        page.get_by_role("heading", name="Recovery needed", exact=True).wait_for(
            timeout=30_000
        )
    elif surface.name == "activity-normal":
        _wait_for_activity_view(page)
    elif surface.name == "administration-database":
        page.get_by_role("heading", name="Database design", exact=True).wait_for(
            timeout=30_000
        )
    elif surface.name == "administration-records":
        rows = page.locator(".record-result")
        rows.first.wait_for(state="visible", timeout=30_000)
        rows.first.click()
        page.get_by_role("heading", name=re.compile(r"^Edit revision \d+$")).wait_for(
            state="visible", timeout=30_000
        )
    _wait_for_zoom_ui_settled(page)


def _zoom_functionality_audit(page: Page, surface: Surface) -> dict[str, Any]:
    _set_variant(page, VARIANTS[3])
    context_overlay_used = False
    if surface.name == "materials-search":
        expand_details = page.get_by_role(
            "button", name="Expand details pane", exact=True
        )
        if expand_details.count() and expand_details.is_visible():
            expand_details.click()
            _wait_for_frames(page)
        context_pane = page.locator('[data-cmp-prototype-pane="context"]')
        if context_pane.count():
            allocated_width = context_pane.evaluate(
                "element => element.getBoundingClientRect().width"
            )
            if allocated_width < 1:
                context_pane.evaluate(
                    "element => element.setAttribute("
                    "'data-cmp-prototype-pane-mode', 'overlay')"
                )
                context_overlay_used = True
                _wait_for_frames(page)
    audit = page.evaluate(
        """regions => {
          const visible = element => {
            if (!element || !element.getClientRects().length) return false;
            const style = getComputedStyle(element);
            if (style.display === 'none' || style.visibility === 'hidden'
                || Number(style.opacity) === 0 || element.closest('[aria-hidden="true"]')) return false;
            const closed = element.closest('details:not([open])');
            if (!closed) return true;
            const summary = closed.querySelector(':scope > summary');
            return Boolean(summary && summary.contains(element));
          };
          const intersectsViewport = (rect, viewport) => !(
            rect.right <= 0 || rect.bottom <= 0
            || rect.left >= viewport.width || rect.top >= viewport.height
          );
          const containedByViewport = (rect, viewport) => (
            rect.left >= 0 && rect.top >= 0
            && rect.right <= viewport.width && rect.bottom <= viewport.height
          );
          const hasReachableInteractionPoint = (element, viewport) => {
            const rect = element.getBoundingClientRect();
            const left = Math.max(0, rect.left);
            const right = Math.min(viewport.width, rect.right);
            const top = Math.max(0, rect.top);
            const bottom = Math.min(viewport.height, rect.bottom);
            if (right - left < 1 || bottom - top < 1) return false;
            const points = [
              [(left + right) / 2, (top + bottom) / 2],
              [left + Math.min(4, (right - left) / 2), top + Math.min(4, (bottom - top) / 2)],
              [right - Math.min(4, (right - left) / 2), bottom - Math.min(4, (bottom - top) / 2)],
            ];
            const hit = points.some(([x, y]) => document.elementsFromPoint(x, y)
              .some(node => node === element || element.contains(node) || node.contains(element)));
            if (hit) return true;
            if (element.matches(':disabled, [aria-disabled="true"]')) return false;
            const previous = document.activeElement;
            element.focus({ preventScroll: true });
            const focused = document.activeElement === element || element.contains(document.activeElement);
            if (previous instanceof HTMLElement) previous.focus({ preventScroll: true });
            return focused;
          };
          const viewport = { width: innerWidth, height: innerHeight };
          const controls = [...document.querySelectorAll('button, input, select, textarea, [role="separator"]')]
            .filter(visible);
          const sampledControls = controls.slice(0, 200);
          const names = sampledControls.map(element => ({
            tag: element.tagName.toLowerCase(),
            role: element.getAttribute('role'),
            name: element.getAttribute('aria-label') || element.textContent?.trim().slice(0, 100) || null,
            disabled: Boolean(element.disabled || element.getAttribute('aria-disabled') === 'true'),
            rect: (() => { const box = element.getBoundingClientRect(); return {
              left: box.left, top: box.top, right: box.right, bottom: box.bottom,
              width: box.width, height: box.height,
            }; })(),
          }));
          const offViewportIndexes = names
            .map((item, index) => intersectsViewport(item.rect, viewport) ? null : index)
            .filter(index => index !== null);
          const clippedIndexes = names
            .map((item, index) => containedByViewport(item.rect, viewport) ? null : index)
            .filter(index => index !== null);
          const scrollState = [document.scrollingElement, ...document.querySelectorAll('*')]
            .filter((element, index, values) => element && values.indexOf(element) === index)
            .filter(element => element.scrollWidth > element.clientWidth || element.scrollHeight > element.clientHeight)
            .map(element => ({ element, left: element.scrollLeft, top: element.scrollTop }));
          const unreachable = [];
          const clippedAfterScroll = [];
          for (const index of clippedIndexes) {
            const element = sampledControls[index];
            element.scrollIntoView({ block: 'center', inline: 'center' });
            const rect = element.getBoundingClientRect();
            if (!containedByViewport(rect, viewport)) clippedAfterScroll.push(names[index]);
            if (!hasReachableInteractionPoint(element, viewport)) unreachable.push(names[index]);
          }
          for (const item of scrollState) {
            item.element.scrollLeft = item.left;
            item.element.scrollTop = item.top;
          }
          const regionPresence = Object.fromEntries(Object.entries(regions).map(([role, selector]) => {
            const element = document.querySelector(selector);
            const box = visible(element) ? element.getBoundingClientRect() : null;
            return [role, box ? { width: box.width, height: box.height } : null];
          }));
          const root = document.documentElement;
          const pageOverflow = {
            x: root.scrollWidth - root.clientWidth,
            y: root.scrollHeight - root.clientHeight,
          };
          return {
            viewport,
            regionPresence,
            interactiveCount: controls.length,
            enabledInteractiveCount: names.filter(item => !item.disabled).length,
            initiallyOffViewportInteractiveCount: offViewportIndexes.length,
            initiallyOffViewportInteractiveNames: offViewportIndexes.slice(0, 30).map(index => names[index].name),
            initiallyClippedInteractiveCount: clippedIndexes.length,
            initiallyClippedInteractiveNames: clippedIndexes.slice(0, 30).map(index => names[index].name),
            clippedAfterScrollInteractiveCount: clippedAfterScroll.length,
            clippedAfterScrollInteractiveNames: clippedAfterScroll.slice(0, 30).map(item => item.name),
            unreachableInteractiveCount: unreachable.length,
            unreachableInteractiveNames: unreachable.slice(0, 30).map(item => item.name),
            scrollContainerCount: scrollState.length,
            pageOverflow,
            unnecessaryBidirectionalPageScroll: pageOverflow.x > 1 && pageOverflow.y > 1,
          };
        }""",
        surface.regions,
    )
    toggles: list[str] = []
    if surface.name.startswith("materials-"):
        collapse = page.get_by_role("button", name=re.compile(r"^Collapse .* pane$"))
        if collapse.count() and collapse.first.is_visible():
            label = collapse.first.get_attribute("aria-label") or "Materials pane"
            collapse.first.click()
            expand = page.get_by_role("button", name=re.compile(r"^Expand .* pane$"))
            expand.first.wait_for(state="visible", timeout=10_000)
            expand.first.click()
            toggles.append(f"{label}: collapse/expand passed")
    alternative_coverage: list[str] = []
    covered_unreachable_names: set[str] = set()
    if surface.name == "materials-search":
        direct_action = page.get_by_role(
            "button", name="Open datasheet", exact=True
        )
        direct_action.scroll_into_view_if_needed()
        direct_action.click()
        page.wait_for_url(
            re.compile(
                r"/materials/[0-9a-f-]+\?record_id=[0-9a-f-]+"
                r"&record_revision_id=[0-9a-f-]+&material_revision_id=[0-9a-f-]+$"
            ),
            timeout=30_000,
        )
        toggles.append(
            "Expand details pane and direct Open datasheet action passed"
        )
        audit["context_overlay_used_after_zero_allocation"] = context_overlay_used
        audit["context_overlay_width"] = audit["regionPresence"]["context"]["width"]
    if surface.name in {"modeling-data", "modeling-fit"}:
        collapse = page.get_by_role(
            "button", name="Collapse curve and process navigator", exact=True
        )
        if collapse.count() and collapse.is_visible():
            collapse.click()
            expand = page.get_by_role(
                "button", name="Expand curve and process navigator", exact=True
            )
            expand.wait_for(state="visible", timeout=10_000)
            expand.click()
            toggles.append("Modeling navigator collapse/expand passed")
    audit["safe_interactions"] = toggles
    audit["functional_alternative_coverage"] = alternative_coverage
    audit["uncovered_unreachable_interactive_names"] = [
        name
        for name in audit["unreachableInteractiveNames"]
        if name not in covered_unreachable_names
    ]
    audit["functional_loss_count"] = len(
        audit["uncovered_unreachable_interactive_names"]
    )
    return audit


def _capture_zoom_200_from_source(
    playwright: Playwright,
    source_page: Page,
    surface: Surface,
    base_url: str,
    output: Path,
    run: dict[str, Any],
) -> None:
    storage_state = source_page.context.storage_state()
    origin = f"{urlsplit(base_url).scheme}://{urlsplit(base_url).netloc}"
    local_storage = next(
        (
            item.get("localStorage", [])
            for item in storage_state.get("origins", [])
            if item.get("origin") == origin
        ),
        [],
    )
    session_storage = source_page.evaluate("() => Object.fromEntries(Object.entries(sessionStorage))")
    source_url = source_page.url
    zoom_level = math.log(2) / math.log(1.2)
    with tempfile.TemporaryDirectory(prefix="cmp-issue-221-zoom-") as profile_dir:
        profile_root = Path(profile_dir)
        preferences = profile_root / "Default" / "Preferences"
        preferences.parent.mkdir(parents=True, exist_ok=True)
        preferences.write_text(
            json.dumps({"partition": {"default_zoom_level": {"x": zoom_level}}}),
            encoding="utf-8",
        )
        context = playwright.chromium.launch_persistent_context(
            profile_dir,
            channel="chrome",
            headless=True,
            viewport={"width": 1920, "height": 1080},
        )
        try:
            if storage_state.get("cookies"):
                context.add_cookies(storage_state["cookies"])
            storage_payload = json.dumps(
                {"origin": origin, "local": local_storage, "session": session_storage}
            )
            context.add_init_script(
                script=(
                    f"const payload = {storage_payload}; "
                    "if (location.origin === payload.origin) { "
                    "for (const item of payload.local) localStorage.setItem(item.name, item.value); "
                    "for (const [key, value] of Object.entries(payload.session)) sessionStorage.setItem(key, value); "
                    "}"
                )
            )
            page = context.pages[0]
            _restore_zoom_surface(
                page, surface, source_url, base_url, run["setup_retries"]
            )
            page.add_style_tag(path=str(PROTOTYPE_STYLESHEET))
            _annotate_semantic_regions(page, surface)
            environment = _browser_zoom_100_signal(page)
            environment["declaredBrowserZoomPercent"] = 200
            environment["inferredBrowserZoomPercent"] = round(
                environment["devicePixelRatio"] * 100, 2
            )
            if (
                abs(environment["devicePixelRatio"] - 2) > 0.01
                or environment["innerWidth"] != 960
                or environment["innerHeight"] != 540
            ):
                raise RuntimeError(f"Chrome did not enter exact browser zoom 200%: {environment}")
            fingerprint = _state_fingerprint(page, surface)
            writes: list[dict[str, str]] = []
            _install_write_guard(page, writes)
            comparison_group = f"{surface.name}:browser-zoom-200"
            for variant in VARIANTS:
                _set_variant(page, variant)
                if surface.name == "modeling-export":
                    page.locator(surface.regions["preview"]).scroll_into_view_if_needed()
                    _wait_for_frames(page)
                measured = _measure(page, surface, variant)
                measured.update(
                    {
                        "surface": surface.name,
                        "outer_viewport": "1920x1080",
                        "css_viewport": "960x540",
                        "browser_zoom_percent": 200,
                        "comparison_group": comparison_group,
                        "state_fingerprint": fingerprint["sha256"],
                    }
                )
                run["zoom_200_measurements"].append(measured)
                destination = (
                    output
                    / "zoom-200"
                    / "originals"
                    / variant.name
                    / f"{surface.name}-outer-1920x1080-css-960x540.png"
                )
                destination.parent.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(destination), full_page=False, animations="disabled")
                with Image.open(destination) as image:
                    if image.size != (1920, 1080):
                        raise RuntimeError(
                            f"zoom-200 raster drift for {destination}: {image.size}"
                        )
                run["zoom_200_images"].append(
                    {
                        "path": _manifest_path(destination),
                        "surface": surface.name,
                        "variant": variant.name,
                        "outer_viewport": "1920x1080",
                        "css_viewport": "960x540",
                        "browser_zoom_percent": 200,
                        "sha256": _sha256(destination),
                        "comparison_group": comparison_group,
                        "state_fingerprint": fingerprint["sha256"],
                    }
                )
            run["zoom_200_functionality"][surface.name] = _zoom_functionality_audit(
                page, surface
            )
            run["zoom_200_environments"][surface.name] = environment
            run["blocked_api_writes"].extend(writes)
        finally:
            context.close()


def _capture_across_viewports(
    playwright: Playwright,
    browser: Browser,
    base_url: str,
    output: Path,
    surface: Surface,
    setup: Callable[[Page, str, int, int], None],
    run: dict[str, Any],
    *,
    persona: str = "administrator",
    interaction_name: str | None = None,
    interaction: Callable[[Page], dict[str, Any]] | None = None,
) -> None:
    for width, height in VIEWPORTS:
        page = _new_page(browser, base_url, width, height, persona=persona)
        try:
            setup(page, base_url, width, height)
            current._wait_for_settled(page)
            _capture_surface(
                page,
                surface,
                width,
                height,
                output,
                run["measurements"],
                run["images"],
                run["crops"],
                run["state_fingerprints"],
                run["blocked_api_writes"],
            )
            signal_key = f"{surface.name}:{width}x{height}"
            run["browser_zoom_signals"][signal_key] = _browser_zoom_100_signal(page)
            if (width, height) == (1920, 1080):
                _capture_zoom_200_from_source(
                    playwright, page, surface, base_url, output, run
                )
            if (
                interaction_name
                and interaction
                and (width, height) == (1920, 1080)
            ):
                run["interaction_audits"][interaction_name] = interaction(page)
        finally:
            page.context.close()


RUN_LIST_FIELDS = (
    "measurements",
    "images",
    "crops",
    "state_fingerprints",
    "blocked_api_writes",
    "zoom_200_measurements",
    "zoom_200_images",
    "setup_retries",
)
RUN_DICT_FIELDS = (
    "interaction_audits",
    "browser_zoom_signals",
    "zoom_200_environments",
    "zoom_200_functionality",
    "canonical_setup",
)


def _complete_run(run: dict[str, Any]) -> None:
    run["completed_at"] = datetime.now(UTC).isoformat()
    run["counts"] = {
        "measurements": len(run["measurements"]),
        "images": len(run["images"]),
        "crops": len(run["crops"]),
        "state_fingerprints": len(run["state_fingerprints"]),
        "blocked_api_writes": len(run["blocked_api_writes"]),
        "zoom_200_measurements": len(run["zoom_200_measurements"]),
        "zoom_200_images": len(run["zoom_200_images"]),
    }


def _write_run_manifest(path: Path, run: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(run, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _manifest_record_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def _validate_surface_manifest(
    surface_name: str,
    run: dict[str, Any],
    output: Path,
) -> set[str]:
    if run.get("surfaces") != [surface_name]:
        raise RuntimeError(
            f"surface manifest mismatch for {surface_name}: {run.get('surfaces')!r}"
        )
    for key, expected in (
        ("issue", 221),
        ("status", "PENDING_PRODUCT_OWNER"),
        ("base_commit", BASE_COMMIT),
        ("viewports", [f"{width}x{height}" for width, height in VIEWPORTS]),
        ("variants", [variant.name for variant in VARIANTS]),
    ):
        if run.get(key) != expected:
            raise RuntimeError(
                f"surface manifest {surface_name} has invalid {key}: {run.get(key)!r}"
            )
    expected_counts = {
        "measurements": len(VIEWPORTS) * len(VARIANTS),
        "images": len(VIEWPORTS) * len(VARIANTS),
        "crops": len(WIDE_CROP_VIEWPORTS)
        * len(VARIANTS)
        * len(SURFACES[surface_name].crop_roles),
        "state_fingerprints": len(VIEWPORTS),
        "blocked_api_writes": 0,
        "zoom_200_measurements": len(VARIANTS),
        "zoom_200_images": len(VARIANTS),
    }
    for key, expected in expected_counts.items():
        actual = len(run.get(key, []))
        if actual != expected:
            raise RuntimeError(
                f"surface manifest {surface_name} has {key}={actual}, expected {expected}"
            )

    expected_pngs: set[str] = set()
    resolved_output = output.resolve()
    for field in ("images", "crops", "zoom_200_images"):
        for record in run[field]:
            if record.get("surface") != surface_name:
                raise RuntimeError(
                    f"surface manifest {surface_name} contains foreign {field} record: {record!r}"
                )
            path = _manifest_record_path(record["path"]).resolve()
            try:
                path.relative_to(resolved_output)
            except ValueError as error:
                raise RuntimeError(
                    f"surface manifest path escapes evidence output: {path}"
                ) from error
            if not path.is_file():
                raise RuntimeError(f"surface manifest image is missing: {path}")
            if _sha256(path) != record["sha256"]:
                raise RuntimeError(f"surface manifest image hash drift: {path}")
            expected_pngs.add(_manifest_path(path))
    return expected_pngs


def _merge_surface_manifests(output: Path) -> int:
    manifests: dict[str, dict[str, Any]] = {}
    expected_pngs: set[str] = set()
    for surface_name in SURFACES:
        path = output / f"measurements-{surface_name}.json"
        if not path.is_file():
            raise RuntimeError(f"missing successful surface manifest: {path}")
        run = json.loads(path.read_text(encoding="utf-8"))
        manifests[surface_name] = run
        expected_pngs.update(_validate_surface_manifest(surface_name, run, output))

    first = manifests[next(iter(SURFACES))]
    merged = {
        key: value
        for key, value in first.items()
        if key not in {*RUN_LIST_FIELDS, *RUN_DICT_FIELDS, "counts", "completed_at"}
    }
    merged["started_at"] = min(run["started_at"] for run in manifests.values())
    merged["completed_at"] = max(run["completed_at"] for run in manifests.values())
    merged["surfaces"] = list(SURFACES)
    merged["display_by_surface"] = {
        surface_name: run["display"] for surface_name, run in manifests.items()
    }
    merged["surface_manifest_paths"] = {
        surface_name: _manifest_path(
            output / f"measurements-{surface_name}.json"
        )
        for surface_name in SURFACES
    }
    for field in RUN_LIST_FIELDS:
        merged[field] = [
            item
            for surface_name in SURFACES
            for item in manifests[surface_name].get(field, [])
        ]
    for field in RUN_DICT_FIELDS:
        merged[field] = {}
        for surface_name in SURFACES:
            overlap = set(merged[field]) & set(manifests[surface_name].get(field, {}))
            if overlap:
                raise RuntimeError(
                    f"surface manifests conflict in {field}: {sorted(overlap)}"
                )
            merged[field].update(manifests[surface_name].get(field, {}))
    for audit in merged["zoom_200_functionality"].values():
        audit.setdefault("functional_alternative_coverage", [])
        audit.setdefault(
            "uncovered_unreachable_interactive_names",
            list(audit.get("unreachableInteractiveNames", [])),
        )
        audit.setdefault(
            "functional_loss_count",
            len(audit["uncovered_unreachable_interactive_names"]),
        )
    _complete_run(merged)
    merged["completed_at"] = max(run["completed_at"] for run in manifests.values())

    actual_pngs = {_manifest_path(path) for path in output.rglob("*.png")}
    if actual_pngs != expected_pngs:
        raise RuntimeError(
            "evidence PNG set differs from successful surface manifests: "
            f"missing={sorted(expected_pngs - actual_pngs)[:20]!r}, "
            f"unexpected={sorted(actual_pngs - expected_pngs)[:20]!r}"
        )
    merged["allowed_duplicate_groups"] = _duplicate_image_allowances(output)
    merged["counts"]["allowed_duplicate_groups"] = len(
        merged["allowed_duplicate_groups"]
    )
    _write_run_manifest(output / "measurements.json", merged)
    print(
        "Issue #221 surface manifests merged: "
        f"images={merged['counts']['images']}, crops={merged['counts']['crops']}, "
        f"measurements={merged['counts']['measurements']}, output={output}"
    )
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:5173")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--only-surface",
        action="append",
        choices=tuple(SURFACES),
        help="Capture only a named representative surface; may be repeated.",
    )
    parser.add_argument(
        "--allow-nonempty-output",
        action="store_true",
        help="Allow an issue-owned output directory to be incrementally completed.",
    )
    parser.add_argument(
        "--merge-surface-manifests",
        action="store_true",
        help=(
            "Validate and merge one successful measurements-<surface>.json file "
            "for every representative surface without launching a browser."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    output = args.output.resolve()
    if (
        output.exists()
        and any(output.iterdir())
        and not args.allow_nonempty_output
        and not args.merge_surface_manifests
    ):
        raise RuntimeError(
            f"output directory is not empty: {output}; use a fresh path or --allow-nonempty-output"
        )
    output.mkdir(parents=True, exist_ok=True)
    if args.merge_surface_manifests:
        return _merge_surface_manifests(output)
    requested = set(args.only_surface or SURFACES)
    invalid = requested - set(SURFACES)
    if invalid:
        raise RuntimeError(f"unknown surfaces: {sorted(invalid)}")

    run: dict[str, Any] = {
        "schema_version": 1,
        "issue": 221,
        "status": "PENDING_PRODUCT_OWNER",
        "base_commit": BASE_COMMIT,
        "started_at": datetime.now(UTC).isoformat(),
        "base_url": args.base_url,
        "viewports": [f"{width}x{height}" for width, height in VIEWPORTS],
        "variants": [variant.name for variant in VARIANTS],
        "surfaces": sorted(requested),
        "display": _collect_windows_display_metadata(),
        "measurements": [],
        "images": [],
        "crops": [],
        "state_fingerprints": [],
        "blocked_api_writes": [],
        "interaction_audits": {},
        "browser_zoom_signals": {},
        "zoom_200_measurements": [],
        "zoom_200_images": [],
        "zoom_200_environments": {},
        "zoom_200_functionality": {},
        "canonical_setup": {},
        "setup_retries": [],
        "setup_mutations_are_outside_candidate_comparison": True,
    }

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            if "materials-datasheet" in requested:
                setup_page = _new_page(
                    browser, args.base_url, 1366, 768, persona="administrator"
                )
                try:
                    run["canonical_setup"]["materials_workflow"] = (
                        _ensure_published_material_workflow(setup_page, args.base_url)
                    )
                finally:
                    setup_page.context.close()
            setup_matrix: dict[
                str, tuple[Callable[[Page, str, int, int], None], str]
            ] = {
                "materials-search": (
                    lambda page, base_url, _width, _height: _setup_materials_search(
                        page, base_url
                    ),
                    "administrator",
                ),
                "materials-datasheet": (
                    lambda page, base_url, _width, _height: _setup_materials_datasheet(
                        page, base_url, run["setup_retries"]
                    ),
                    "administrator",
                ),
                "modeling-data": (
                    lambda page, base_url, _width, _height: _setup_modeling_data(
                        page, base_url, run["setup_retries"]
                    ),
                    "administrator",
                ),
                "modeling-fit": (_setup_modeling_fit, "administrator"),
                "modeling-export": (_setup_modeling_export, "administrator"),
                "activity-normal": (
                    lambda page, base_url, _width, _height: _setup_activity_normal(
                        page, base_url
                    ),
                    "reviewer",
                ),
                "activity-history": (
                    lambda page, base_url, _width, _height: _setup_activity_history(
                        page, base_url
                    ),
                    "reviewer",
                ),
                "activity-decision-error": (
                    lambda page, base_url, _width, _height: _setup_activity_decision_error(
                        page, base_url
                    ),
                    "reviewer",
                ),
                "activity-recovery": (
                    lambda page, base_url, _width, _height: _setup_activity_recovery(
                        page, base_url
                    ),
                    "reviewer",
                ),
                "administration-database": (
                    lambda page, base_url, _width, _height: _setup_administration_database(
                        page, base_url
                    ),
                    "administrator",
                ),
                "administration-records": (
                    lambda page, base_url, _width, _height: _setup_administration_records(
                        page, base_url
                    ),
                    "administrator",
                ),
            }
            for name in SURFACES:
                if name not in requested:
                    continue
                setup, persona = setup_matrix[name]
                interaction_name = None
                interaction = None
                if name == "materials-search":
                    interaction_name = "materials"
                    interaction = _run_materials_interaction_audit
                elif name == "modeling-data":
                    interaction_name = "modeling-data"
                    interaction = _run_modeling_interaction_audit
                _capture_across_viewports(
                    playwright,
                    browser,
                    args.base_url,
                    output,
                    SURFACES[name],
                    setup,
                    run,
                    persona=persona,
                    interaction_name=interaction_name,
                    interaction=interaction,
                )
        finally:
            browser.close()

    _complete_run(run)
    measurement_path = output / "measurements.json"
    _write_run_manifest(measurement_path, run)
    if len(requested) == 1:
        surface_name = next(iter(requested))
        _write_run_manifest(output / f"measurements-{surface_name}.json", run)
    print(
        "Issue #221 evidence captured: "
        f"images={run['counts']['images']}, crops={run['counts']['crops']}, "
        f"measurements={run['counts']['measurements']}, output={output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

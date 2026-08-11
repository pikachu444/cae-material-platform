"""Capture issue #184 production UI at real Chrome browser zoom 200%."""

# Embedded browser snippets and exact accessible labels intentionally exceed
# the repository's normal line length.
# ruff: noqa: E501

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import struct
import sys
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright

SCRIPT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_ROOT))

import capture_current_product as current  # noqa: E402
import capture_high_dpi_decision as decision  # noqa: E402

DEFAULT_OUTPUT = Path(
    "docs/17-evidence/images/issue-184-high-dpi-global-implementation/zoom-200"
)
OUTER_VIEWPORT = (1920, 1080)
CSS_VIEWPORT = (960, 540)


@dataclass(frozen=True)
class Snapshot:
    url: str
    cookies: list[dict[str, Any]]
    local_storage: list[dict[str, str]]
    session_storage: dict[str, str]


def _snapshot(page: Page, base_url: str) -> Snapshot:
    origin = f"{urlsplit(base_url).scheme}://{urlsplit(base_url).netloc}"
    state = page.context.storage_state()
    local_storage = next(
        (
            entry.get("localStorage", [])
            for entry in state.get("origins", [])
            if entry.get("origin") == origin
        ),
        [],
    )
    return Snapshot(
        url=page.url,
        cookies=state.get("cookies", []),
        local_storage=local_storage,
        session_storage=page.evaluate(
            "() => Object.fromEntries(Object.entries(sessionStorage))"
        ),
    )


def _source_snapshot(
    browser: Browser,
    base_url: str,
    setup: Callable[[Page], None],
) -> Snapshot:
    page = current._new_page(browser, base_url, *OUTER_VIEWPORT)
    try:
        setup(page)
        current._wait_for_settled(page)
        return _snapshot(page, base_url)
    finally:
        page.context.close()


def _zoom_context(
    playwright: Any,
    snapshot: Snapshot,
    base_url: str,
    profile_dir: Path,
) -> BrowserContext:
    zoom_level = math.log(2) / math.log(1.2)
    preferences = profile_dir / "Default" / "Preferences"
    preferences.parent.mkdir(parents=True, exist_ok=True)
    preferences.write_text(
        json.dumps({"partition": {"default_zoom_level": {"x": zoom_level}}}),
        encoding="utf-8",
    )
    context = playwright.chromium.launch_persistent_context(
        profile_dir,
        channel="chrome",
        headless=True,
        viewport={"width": OUTER_VIEWPORT[0], "height": OUTER_VIEWPORT[1]},
    )
    if snapshot.cookies:
        context.add_cookies(snapshot.cookies)
    origin = f"{urlsplit(base_url).scheme}://{urlsplit(base_url).netloc}"
    payload = json.dumps(
        {
            "origin": origin,
            "local": snapshot.local_storage,
            "session": snapshot.session_storage,
        }
    )
    context.add_init_script(
        script=(
            f"const payload = {payload};"
            "if (location.origin === payload.origin) {"
            "for (const item of payload.local) localStorage.setItem(item.name, item.value);"
            "for (const [key, value] of Object.entries(payload.session)) sessionStorage.setItem(key, value);"
            "}"
        )
    )
    return context


def _wait_frames(page: Page) -> None:
    page.wait_for_load_state("domcontentloaded")
    page.evaluate(
        """async () => {
          await new Promise(requestAnimationFrame);
          await new Promise(requestAnimationFrame);
          if (document.fonts?.ready) await document.fonts.ready;
        }"""
    )


def _page_origin(page: Page) -> str:
    parsed = urlsplit(page.url)
    return f"{parsed.scheme}://{parsed.netloc}"


def _environment(page: Page) -> dict[str, Any]:
    environment = page.evaluate(
        """() => ({
          innerWidth, innerHeight, outerWidth, outerHeight, devicePixelRatio,
          screenWidth: screen.width, screenHeight: screen.height,
          visualViewportScale: visualViewport?.scale ?? null,
          documentWidth: document.documentElement.clientWidth,
          documentScrollWidth: document.documentElement.scrollWidth,
          density: document.documentElement.dataset.displayDensity || null,
        })"""
    )
    if (
        abs(float(environment["devicePixelRatio"]) - 2) > 0.01
        or environment["innerWidth"] != CSS_VIEWPORT[0]
        or environment["innerHeight"] != CSS_VIEWPORT[1]
        or environment["density"] != "standard"
    ):
        raise RuntimeError(f"Chrome did not enter the Standard zoom-200 contract: {environment}")
    return environment


def _geometry(page: Page) -> dict[str, Any]:
    result = page.evaluate(
        """() => {
          const visible = node => Boolean(node && node.getClientRects().length
            && getComputedStyle(node).visibility !== 'hidden');
          const localScroll = [...document.querySelectorAll('*')]
            .filter(visible)
            .map(node => ({
              tag: node.tagName.toLowerCase(),
              id: node.id || null,
              className: typeof node.className === 'string' ? node.className : '',
              x: node.scrollWidth > node.clientWidth + 1,
              y: node.scrollHeight > node.clientHeight + 1,
              clientWidth: node.clientWidth,
              clientHeight: node.clientHeight,
              scrollWidth: node.scrollWidth,
              scrollHeight: node.scrollHeight,
            }))
            .filter(item => item.x || item.y)
            .slice(0, 80);
          const boxes = selectors => Object.fromEntries(selectors.map(selector => {
            const node = document.querySelector(selector);
            const box = node?.getBoundingClientRect();
            return [selector, box ? {
              left: box.left, right: box.right, top: box.top, bottom: box.bottom,
              width: box.width, height: box.height,
            } : null];
          }));
          return {
            page: {
              clientWidth: document.documentElement.clientWidth,
              clientHeight: document.documentElement.clientHeight,
              scrollWidth: document.documentElement.scrollWidth,
              scrollHeight: document.documentElement.scrollHeight,
            },
            localScroll,
            dualAxisLocalScrollCount: localScroll.filter(item => item.x && item.y).length,
            boxes: boxes([
              '.application-workspace', '.materials-workspace', '.modeling-workspace-shell',
              '.modeling-workspace-rail', '.persistent-modeling-plot', '.modeling-task-ribbon',
              '.export-workspace', '.native-preview', '.activity-shell',
              '.administration-workspace', '.administration-record-workbench',
            ]),
          };
        }"""
    )
    page_box = result["page"]
    if page_box["scrollWidth"] > page_box["clientWidth"] + 1:
        raise RuntimeError(f"zoom-200 introduced page horizontal overflow: {result}")
    return result


def _fingerprint(page: Page, name: str) -> str:
    payload = page.evaluate(
        """name => ({
          name,
          url: location.href,
          density: document.documentElement.dataset.displayDensity || null,
          headings: [...document.querySelectorAll('h1,h2,h3')]
            .filter(node => node.getClientRects().length)
            .map(node => node.textContent?.trim() || ''),
          controls: [...document.querySelectorAll('button,input,select,textarea,a[href]')]
            .filter(node => node.getClientRects().length)
            .map(node => ({
              role: node.getAttribute('role') || node.tagName.toLowerCase(),
              name: node.getAttribute('aria-label') || node.textContent?.trim() || '',
              disabled: Boolean(node.disabled),
            })),
        })""",
        name,
    )
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _capture(
    page: Page,
    output: Path,
    name: str,
    interactions: list[str],
) -> dict[str, Any]:
    _wait_frames(page)
    environment = _environment(page)
    geometry = _geometry(page)
    destination = output / f"{name}-outer-1920x1080-css-960x540.png"
    destination.parent.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(destination), full_page=False, animations="disabled")
    raw = destination.read_bytes()
    if raw[:8] != b"\x89PNG\r\n\x1a\n" or struct.unpack(">II", raw[16:24]) != OUTER_VIEWPORT:
        raise RuntimeError(f"zoom-200 raster drift: {destination}")
    return {
        "path": destination.as_posix(),
        "surface": name,
        "outer_viewport": "1920x1080",
        "css_viewport": "960x540",
        "browser_zoom_percent": 200,
        "dpr": environment["devicePixelRatio"],
        "density": environment["density"],
        "sha256": _sha256(destination),
        "state_fingerprint": _fingerprint(page, name),
        "environment": environment,
        "geometry": geometry,
        "interactions": interactions,
    }


def _run_zoom_surface(
    playwright: Any,
    snapshot: Snapshot,
    base_url: str,
    output: Path,
    prepare: Callable[[Page], list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    with tempfile.TemporaryDirectory(prefix="cmp-issue-184-zoom-") as directory:
        context = _zoom_context(playwright, snapshot, base_url, Path(directory))
        try:
            page = context.pages[0]
            page.goto(snapshot.url, wait_until="domcontentloaded")
            return prepare(page)
        finally:
            context.close()


def _materials_zoom(page: Page, output: Path) -> list[dict[str, Any]]:
    current._wait_for_settled(page)
    row = page.locator(".materials-result-table tbody tr").first
    row.wait_for(state="visible", timeout=30_000)
    row.click()
    trigger = page.get_by_role("button", name="Expand details pane", exact=True)
    trigger.click()
    dialog = page.get_by_role("dialog", name="details pane", exact=True)
    dialog.wait_for(state="visible", timeout=10_000)
    close = dialog.get_by_role("button", name="Close details pane", exact=True)
    if not close.evaluate("node => document.activeElement === node"):
        raise RuntimeError("Materials context overlay did not move focus to Close")
    record = _capture(
        page,
        output,
        "materials-context-overlay",
        ["allocation<1px overlay opened", "focus moved to Close"],
    )
    dialog.press("Escape")
    page.wait_for_function(
        """() => !document.querySelector('[role="dialog"][aria-label="details pane"]')""",
        timeout=10_000,
    )
    page.wait_for_function(
        """() => {
          const trigger = document.querySelector('button[aria-label="Expand details pane"]');
          return Boolean(trigger && document.activeElement === trigger);
        }""",
        timeout=10_000,
    )
    trigger.click()
    dialog.get_by_role("button", name="Open datasheet", exact=True).click()
    page.wait_for_url(re.compile(r"/materials/[0-9a-f-]+"), timeout=30_000)
    record["interactions"].extend(["Escape closed overlay", "focus returned", "Open datasheet navigated"])
    return [record]


def _data_zoom(page: Page, output: Path) -> list[dict[str, Any]]:
    current._wait_for_modeling_data_surface(page)
    current._wait_for_data_plot(page)
    records = [
        _capture(page, output, "modeling-data-expanded", ["exact Data graph restored"])
    ]
    collapse = page.get_by_role(
        "button", name="Collapse curve and process navigator", exact=True
    )
    collapse.click()
    page.get_by_role(
        "button", name="Expand curve and process navigator", exact=True
    ).wait_for(state="visible", timeout=10_000)
    rail_width = page.locator(".modeling-workspace-rail").evaluate(
        "node => node.getBoundingClientRect().width"
    )
    if rail_width >= 1:
        raise RuntimeError(f"Modeling Data navigator did not collapse: {rail_width}")
    records.append(
        _capture(page, output, "modeling-data-collapsed", ["navigator collapsed"])
    )
    page.get_by_role(
        "button", name="Expand curve and process navigator", exact=True
    ).click()
    page.get_by_role(
        "separator", name="Resize curve and process navigator", exact=True
    ).dblclick()
    current._wait_for_data_plot(page)
    split = page.locator(".modeling-data-split")
    split.evaluate("node => { node.scrollTop = node.scrollHeight; }")
    page.evaluate(
        """async () => {
          await new Promise(requestAnimationFrame);
          await new Promise(requestAnimationFrame);
        }"""
    )
    visible_graph = page.evaluate(
        """() => {
          const split = document.querySelector('.modeling-data-split');
          const svg = document.querySelector('.persistent-modeling-plot svg.processing-curve');
          const legend = document.querySelector('.persistent-modeling-plot .curve-legend');
          const xAxis = [...document.querySelectorAll('.persistent-modeling-plot .chart-axis-label')]
            .find(node => (node.textContent ?? '').includes('strain'));
          const compact = node => {
            const value = node?.getBoundingClientRect();
            return value ? {
              left: value.left, right: value.right, top: value.top,
              bottom: value.bottom, width: value.width, height: value.height,
            } : null;
          };
          const splitBox = compact(split);
          const svgBox = compact(svg);
          const legendBox = compact(legend);
          const xAxisBox = compact(xAxis);
          const visibleCenter = svgBox && splitBox ? {
            x: (Math.max(svgBox.left, splitBox.left) + Math.min(svgBox.right, splitBox.right)) / 2,
            y: (Math.max(svgBox.top, splitBox.top) + Math.min(svgBox.bottom, splitBox.bottom)) / 2,
          } : null;
          const hit = visibleCenter ? document.elementFromPoint(visibleCenter.x, visibleCenter.y) : null;
          return {
            split: splitBox, svg: svgBox, legend: legendBox, xAxis: xAxisBox,
            scrollTop: split?.scrollTop ?? 0,
            hitGraph: Boolean(hit && (hit === svg || svg?.contains(hit))),
            hit: hit?.className?.baseVal || hit?.className || hit?.tagName || null,
          };
        }"""
    )
    split_box = visible_graph.get("split") if isinstance(visible_graph, dict) else None
    axis_box = visible_graph.get("xAxis") if isinstance(visible_graph, dict) else None
    legend_box = visible_graph.get("legend") if isinstance(visible_graph, dict) else None
    if (
        not isinstance(split_box, dict)
        or not isinstance(axis_box, dict)
        or not isinstance(legend_box, dict)
        or float(visible_graph.get("scrollTop", 0)) <= 0
        or float(axis_box.get("top", 0)) < float(split_box.get("top", 0)) - 1
        or float(axis_box.get("bottom", 0)) > float(split_box.get("bottom", 0)) + 1
        or float(legend_box.get("bottom", 0)) > float(split_box.get("bottom", 0)) + 1
        or not visible_graph.get("hitGraph")
    ):
        raise RuntimeError(
            f"zoom-200 Data graph axis/legend/hit region is not reachable after local scroll: {visible_graph}"
        )
    records[0]["interactions"].extend(["navigator expanded", "navigator reset", "graph recalculated"])
    records.append(
        _capture(
            page,
            output,
            "modeling-data-graph-reachable",
            ["one-axis local scroll", "x axis and legend visible", "graph hit region reachable"],
        )
    )
    return records


def _process_zoom(page: Page, output: Path) -> list[dict[str, Any]]:
    current._wait_modeling_process_panel(page)
    current._click_modeling_process_preview_and_wait(page)
    panel = page.locator('[data-modeling-process-panel="ready"]')
    panel.get_by_role("combobox", name="Evaluation method", exact=True).select_option("manual")
    panel.get_by_role("spinbutton", name="Manual Young's modulus", exact=True).wait_for(timeout=30_000)
    panel.get_by_role(
        "textbox", name="Manual Young's modulus reason", exact=True
    ).fill("Zoom 200 check")
    current._click_modeling_process_preview_and_wait(page)
    if panel.get_by_role("button", name="Save processed curves", exact=True).is_disabled():
        raise RuntimeError("zoom-200 valid manual Process preview did not enable Save")
    records = [
        _capture(
            page,
            output,
            "modeling-process-manual-controls",
            ["manual controls visible", "graph recalculated after density-sized ribbon"],
        )
    ]
    panel.locator(".process-band-save").scroll_into_view_if_needed()
    save = panel.get_by_role("button", name="Save processed curves", exact=True)
    save.focus()
    reachability = save.evaluate(
        """node => {
          const box = node.getBoundingClientRect();
          const ribbon = node.closest('.modeling-task-ribbon');
          const ribbonBox = ribbon?.getBoundingClientRect();
          const hit = document.elementFromPoint(box.left + box.width / 2, box.top + box.height / 2);
          const compact = value => value ? {
            left: value.left, right: value.right, top: value.top,
            bottom: value.bottom, width: value.width, height: value.height,
          } : null;
          return {
            reachable: Boolean(document.activeElement === node && hit
              && (hit === node || node.contains(hit))),
            action: compact(box),
            ribbon: compact(ribbonBox),
            hit: hit?.textContent?.trim() || hit?.tagName || null,
            focused: document.activeElement === node,
            scrollTop: ribbon?.scrollTop ?? null,
            innerHeight,
          };
        }"""
    )
    if not isinstance(reachability, dict) or not reachability.get("reachable"):
        raise RuntimeError(
            f"zoom-200 manual Process Save action is not focusable/hittable: {reachability}"
        )
    plot_frame = page.locator(
        ".persistent-modeling-plot .engineering-plot-frame"
    ).bounding_box()
    if not isinstance(plot_frame, dict) or float(plot_frame.get("height", 0)) <= 0:
        raise RuntimeError("zoom-200 Process plot frame is missing")
    current._measure_process_fit(
        page,
        "process",
        *CSS_VIEWPORT,
        minimum_svg_height=max(1, int(float(plot_frame["height"])) - 1),
    )
    records.append(
        _capture(
            page,
            output,
            "modeling-process-save-reachable",
            ["local ribbon scroll", "Save focus/hit", "graph geometry pass"],
        )
    )
    return records


def _fit_zoom(page: Page, output: Path) -> list[dict[str, Any]]:
    page.locator(".modeling-workspace-stage-fit").wait_for(timeout=30_000)
    current._click_modeling_fit_preview_and_wait(page)
    fit_trigger = page.get_by_role("button", name="Candidate parameters", exact=True)
    fit_trigger.click()
    page.wait_for_timeout(500)
    drawer_diagnostic = page.evaluate(
        """() => {
          const surface = document.querySelector('.modeling-main-surface');
          const dock = document.querySelector('.modeling-workspace-dock');
          const drawer = document.querySelector('.fit-evidence-drawer');
          const frame = document.querySelector('.engineering-plot-frame');
          const snapshot = node => {
            if (!node) return null;
            const box = node.getBoundingClientRect();
            const style = getComputedStyle(node);
            return {
              className: node.className,
              box: { left: box.left, right: box.right, top: box.top, bottom: box.bottom, width: box.width, height: box.height },
              display: style.display,
              visibility: style.visibility,
              position: style.position,
              height: style.height,
              maxHeight: style.maxHeight,
              overflow: style.overflow,
            };
          };
          return { surface: snapshot(surface), dock: snapshot(dock), drawer: snapshot(drawer), frame: snapshot(frame) };
        }"""
    )
    if not page.locator(".fit-evidence-drawer#fit-evidence-dock").is_visible():
        raise RuntimeError(f"zoom-200 Fit drawer is hidden after disclosure: {drawer_diagnostic}")
    trigger, _body, _table = current._open_fit_evidence(page)
    page.wait_for_function(
        """() => document.querySelector('.modeling-main-surface')
          ?.getAttribute('data-dock-presentation') === 'overlay'""",
        timeout=30_000,
    )
    page.wait_for_function(
        """() => document.activeElement
          ?.classList.contains('fit-evidence-body')""",
        timeout=30_000,
    )
    plot_frame = page.locator(
        ".persistent-modeling-plot .engineering-plot-frame"
    ).bounding_box()
    if not isinstance(plot_frame, dict) or float(plot_frame.get("height", 0)) < 1:
        raise RuntimeError(f"zoom-200 Fit drawer collapsed the graph: {plot_frame}")
    current._measure_process_fit(
        page,
        "fit",
        *CSS_VIEWPORT,
        minimum_svg_height=max(1, int(float(plot_frame["height"])) - 1),
    )
    records = [
        _capture(
            page,
            output,
            "modeling-fit-evidence",
            ["candidate evidence drawer opened", "focus moved", "bounded overlay", "graph geometry pass"],
        )
    ]
    current._close_fit_evidence(page, trigger)
    if not trigger.evaluate("node => document.activeElement === node"):
        raise RuntimeError("Fit evidence drawer did not return focus")
    trigger.click()
    records[0]["interactions"].extend(["drawer closed", "focus returned", "drawer reopened"])
    return records


def _export_zoom(page: Page, output: Path) -> list[dict[str, Any]]:
    page.locator(".export-main").wait_for(timeout=30_000)
    current._prepare_exact_metal_source_if_needed(page)
    current._prepare_exact_target_preview(page)
    preview = page.get_by_label("Native preview", exact=True)
    preview.locator("pre").wait_for(timeout=30_000)
    preview.scroll_into_view_if_needed()
    return [
        _capture(page, output, "modeling-export-preview", ["native preview generated", "preview reached by one-axis scroll"])
    ]


def _activity_zoom(page: Page, output: Path) -> list[dict[str, Any]]:
    current._wait_for_settled(page)
    decision._wait_for_activity_view(page, view="recent-outcomes", expect_review_action=False)
    current._wait_for_settled(page)
    decision._wait_for_activity_view(page, view="recent-outcomes", expect_review_action=False)
    selected = page.get_by_role("tab", name="Recent outcomes", exact=True)
    if selected.get_attribute("aria-selected") != "true":
        raise RuntimeError("zoom-200 Activity did not retain Recent outcomes after queue settlement")
    page.locator("#activity-queue-scroll").focus()
    return [
        _capture(page, output, "activity-history", ["recent outcomes selected", "history scroll region focused"])
    ]


def _setup_activity_history_source(page: Page, base_url: str) -> None:
    current._ensure_activity_review_fixture(page, base_url)
    current._seed_activity_delivery_history(page)
    current._seed_activity_recovery_history(page, base_url)
    page.goto(f"{base_url}/activity")
    decision._wait_for_activity_view(
        page,
        view="recent-outcomes",
        expect_review_action=False,
    )


def _administration_database_zoom(page: Page, output: Path) -> list[dict[str, Any]]:
    decision._setup_administration_database(page, _page_origin(page))
    page.locator(".application-workspace").evaluate("node => node.scrollTo({ top: 0, left: 0 })")
    records = [
        _capture(page, output, "administration-database", ["three-pane database surface", "route top restored"])
    ]
    table = page.get_by_role("combobox", name="Current table", exact=True)
    table.focus()
    if not table.evaluate("node => document.activeElement === node"):
        raise RuntimeError("zoom-200 Administration Database table control did not receive focus")
    records.append(
        _capture(
            page,
            output,
            "administration-database-table-control",
            ["table control focused", "one-axis workspace scroll", "form action reachable"],
        )
    )
    return records


def _administration_records_zoom(page: Page, output: Path) -> list[dict[str, Any]]:
    base_url = _page_origin(page)
    page.goto(f"{base_url}/administration/records")
    page.get_by_role("heading", name="Single entry or multiple rows", exact=True).wait_for(timeout=30_000)
    page.get_by_role("button", name="Multiple rows", exact=True).click()
    file_input = page.get_by_label("Source file", exact=True)
    file_input.wait_for(timeout=30_000)
    file_input.focus()
    return [
        _capture(page, output, "administration-records-file-input", ["multiple rows selected", "native file input focused"])
    ]


def _administration_access_zoom(page: Page, output: Path) -> list[dict[str, Any]]:
    base_url = _page_origin(page)
    page.goto(f"{base_url}/administration/access")
    page.get_by_role("heading", name="Choose what each team can do", exact=True).wait_for(timeout=30_000)
    page.locator(".application-workspace").evaluate("node => node.scrollTo({ top: 0, left: 0 })")
    records = [
        _capture(page, output, "administration-access", ["Users and access route top", "shared workspace width"])
    ]
    role = page.get_by_role("combobox", name="Role", exact=True)
    role.select_option("reviewer")
    role.focus()
    if not role.evaluate("node => document.activeElement === node"):
        raise RuntimeError("zoom-200 Administration role control did not receive focus")
    records.append(
        _capture(
            page,
            output,
            "administration-access-role-control",
            ["reviewer role selected", "role control focused", "one-axis workspace scroll"],
        )
    )
    return records


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:5173")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    surface_keys = (
        "materials",
        "data",
        "process",
        "fit",
        "export",
        "activity",
        "administration-database",
        "administration-records",
        "administration-access",
    )
    parser.add_argument(
        "--only-surface",
        action="append",
        choices=surface_keys,
        help="Capture only the named zoom surface; repeat for more than one.",
    )
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    requested = set(args.only_surface or surface_keys)
    records: list[dict[str, Any]] = []
    surfaces: list[tuple[Snapshot, Callable[[Page, Path], list[dict[str, Any]]]]] = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            base_keys = {
                "materials": _materials_zoom,
                "administration-database": _administration_database_zoom,
                "administration-records": _administration_records_zoom,
                "administration-access": _administration_access_zoom,
            }
            if requested.intersection(base_keys):
                base = _source_snapshot(
                    browser,
                    args.base_url,
                    lambda page: current._open_materials_search(page, args.base_url),
                )
                surfaces.extend(
                    (base, prepare)
                    for key, prepare in base_keys.items()
                    if key in requested
                )
            if "data" in requested:
                data = _source_snapshot(
                    browser,
                    args.base_url,
                    lambda page: current._prepare_modeling(
                        page, args.base_url, verify_reload=False
                    ),
                )
                surfaces.append((data, _data_zoom))
            if "process" in requested:
                process = _source_snapshot(
                    browser,
                    args.base_url,
                    lambda page: current._prepare_modeling_process(
                        page, args.base_url, verify_data_reload=False
                    ),
                )
                surfaces.append((process, _process_zoom))
            if requested.intersection({"fit", "export"}):
                fit_page = current._new_page(browser, args.base_url, *OUTER_VIEWPORT)
                try:
                    current._prepare_fit_for_export(
                        fit_page,
                        args.base_url,
                        label="Issue 184 zoom-200 exact Process source",
                    )
                    if "fit" in requested:
                        surfaces.append((_snapshot(fit_page, args.base_url), _fit_zoom))
                    if "export" in requested:
                        current._save_exact_fit_selection(
                            fit_page, candidate_key="swift+voce", require_warning=False
                        )
                        current._open_modeling_stage(fit_page, "export")
                        fit_page.wait_for_url(re.compile(r"stage=export"), timeout=30_000)
                        current._prepare_exact_metal_source_if_needed(fit_page)
                        current._prepare_exact_target_preview(fit_page)
                        surfaces.append((_snapshot(fit_page, args.base_url), _export_zoom))
                finally:
                    fit_page.context.close()
            if "activity" in requested:
                activity = _source_snapshot(
                    browser,
                    args.base_url,
                    lambda page: _setup_activity_history_source(page, args.base_url),
                )
                surfaces.append((activity, _activity_zoom))
        finally:
            browser.close()

        for snapshot, prepare in surfaces:
            records.extend(
                _run_zoom_surface(
                    playwright,
                    snapshot,
                    args.base_url,
                    args.output,
                    lambda page, prepare=prepare: prepare(page, args.output),
                )
            )

    manifest_path = args.output / "manifest.json"
    existing_records: list[dict[str, Any]] = []
    if args.only_surface and manifest_path.exists():
        existing = json.loads(manifest_path.read_text(encoding="utf-8"))
        if isinstance(existing, dict) and isinstance(existing.get("images"), list):
            surface_prefixes = {
                "materials": "materials-",
                "data": "modeling-data-",
                "process": "modeling-process-",
                "fit": "modeling-fit-",
                "export": "modeling-export-",
                "activity": "activity-",
                "administration-database": "administration-database",
                "administration-records": "administration-records-",
                "administration-access": "administration-access",
            }
            replaced_prefixes = tuple(
                surface_prefixes[key] for key in requested
            )
            existing_records = [
                record
                for record in existing["images"]
                if isinstance(record, dict)
                and not str(record.get("surface", "")).startswith(replaced_prefixes)
            ]
    merged_records = sorted(
        [*existing_records, *records],
        key=lambda record: str(record.get("surface", "")),
    )
    manifest = {
        "schema_version": 1,
        "capture": "issue-184-production-browser-zoom-200",
        "physical_4k_readability": "DEFERRED_TO_223",
        "images": merged_records,
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"output": args.output.as_posix(), "captures": len(records)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

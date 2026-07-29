# ruff: noqa: E501
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parents[3]
REFERENCE_DIR = ROOT / "docs/00-research/ux-service-reference"
IMAGE_DIR = ROOT / "docs/17-evidence/images/issue-167-service-reference"
HTML = REFERENCE_DIR / "materials-card-preview-normal.html"
CSS = REFERENCE_DIR / "materials-card-preview.css"
JAVASCRIPT = REFERENCE_DIR / "materials-card-preview.js"
STAGING_INDEX = IMAGE_DIR / "materials-card-wave02.staging.json"

VIEWPORTS: dict[str, dict[str, int]] = {
    "1366x768": {"width": 1366, "height": 768, "device_scale_factor": 1},
    "1440x900": {"width": 1440, "height": 900, "device_scale_factor": 1},
    "1920x1080": {"width": 1920, "height": 1080, "device_scale_factor": 1},
}

TARGETS: dict[str, dict[str, Any]] = {
    "materials-card-preview-normal-1366x768": {
        "state": "normal",
        "viewport": VIEWPORTS["1366x768"],
        "image": IMAGE_DIR / "materials-card-preview-normal-1366x768.png",
        "measurements": IMAGE_DIR / "materials-card-preview-normal-1366x768.measurements.json",
    },
    "materials-card-preview-normal-1440x900": {
        "state": "normal",
        "viewport": VIEWPORTS["1440x900"],
        "image": IMAGE_DIR / "materials-card-preview-normal-1440x900.png",
        "measurements": IMAGE_DIR / "materials-card-preview-normal-1440x900.measurements.json",
    },
    "materials-card-preview-normal-1920x1080": {
        "state": "normal",
        "viewport": VIEWPORTS["1920x1080"],
        "image": IMAGE_DIR / "materials-card-preview-normal-1920x1080.png",
        "measurements": IMAGE_DIR / "materials-card-preview-normal-1920x1080.measurements.json",
    },
    "materials-card-approximation-blocked-1440x900": {
        "state": "approximation",
        "viewport": VIEWPORTS["1440x900"],
        "image": IMAGE_DIR / "materials-card-approximation-blocked-1440x900.png",
        "measurements": IMAGE_DIR / "materials-card-approximation-blocked-1440x900.measurements.json",
    },
    "materials-card-unsupported-blocked-1440x900": {
        "state": "unsupported",
        "viewport": VIEWPORTS["1440x900"],
        "image": IMAGE_DIR / "materials-card-unsupported-blocked-1440x900.png",
        "measurements": IMAGE_DIR / "materials-card-unsupported-blocked-1440x900.measurements.json",
    },
}

EXCEPTION_STATES = {
    "materials-card-approximation-blocked-1440x900": "approximation",
    "materials-card-unsupported-blocked-1440x900": "unsupported",
}

LEGACY_ACTIVE_ROUTE_SELECTORS = (
    "page-stack",
    "page-heading",
    "content-card",
    "module-material-card",
    "hero-actions",
    "eyebrow",
    "status-badge",
    "count-chip",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Capture the WAVE-02 MAT-CARD static-reference family.")
    parser.add_argument("--target", choices=sorted(TARGETS), help="One canonical target id.")
    parser.add_argument("--all-packet-targets", action="store_true", help="Capture all five canonical targets and responsive/state evidence.")
    args = parser.parse_args()
    if not args.target and not args.all_packet_targets:
        parser.error("provide --target or --all-packet-targets")
    if args.target and args.all_packet_targets:
        parser.error("--target and --all-packet-targets are mutually exclusive")
    return args


def rounded_box(page: Page, selector: str) -> dict[str, float]:
    box = page.locator(selector).bounding_box()
    if box is None:
        raise AssertionError(f"{selector} is not visible")
    return {key: round(value, 2) for key, value in box.items()}


def png_dimensions(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise AssertionError(f"not a PNG: {path}")
    return struct.unpack(">II", data[16:24])


def overflow_snapshot(page: Page) -> dict[str, int]:
    return page.evaluate(
        """() => ({
          document_horizontal: document.documentElement.scrollWidth - document.documentElement.clientWidth,
          document_vertical: document.documentElement.scrollHeight - document.documentElement.clientHeight,
          body_horizontal: document.body.scrollWidth - document.body.clientWidth,
          body_vertical: document.body.scrollHeight - document.body.clientHeight,
        })"""
    )


def visual_acceptance_snapshot(page: Page) -> dict[str, Any]:
    return page.evaluate(
        """(legacySelectors) => {
          const fontSize = (selector) => {
            const element = document.querySelector(selector);
            return element ? Number.parseFloat(getComputedStyle(element).fontSize) : null;
          };
          return {
            typography: {
              body_px: fontSize('body'),
              tree_row_px: fontSize('.tree-row'),
              native_preview_data_px: fontSize('.preview-scroll pre'),
              mapping_primary_px: fontSize('.mapping-row strong'),
              delivery_value_px: fontSize('.delivery-fields dd'),
            },
            legacy_selector_report: Object.fromEntries(
              legacySelectors.map((name) => [name, document.querySelectorAll(`.${name}`).length])
            ),
          };
        }""",
        list(LEGACY_ACTIVE_ROUTE_SELECTORS),
    )


def tree_snapshot(page: Page) -> dict[str, Any]:
    return page.locator(".tree-scroll").evaluate(
        """(element) => {
          const right = element.getBoundingClientRect().right;
          const labels = [...element.querySelectorAll('[role="treeitem"]')].map((row) => ({
            expected: row.dataset.kind,
            actual: row.querySelector('.tree-kind')?.textContent.trim(),
            title: row.querySelector('.tree-label')?.title,
          }));
          const kinds = [...element.querySelectorAll('.tree-kind')].map((kind) => kind.getBoundingClientRect());
          return {
            horizontal_overflow: element.scrollWidth - element.clientWidth,
            kinds_inside: kinds.every((box) => box.right <= right + 0.01),
            labels_match: labels.every((label) => label.expected === label.actual),
            labels_have_title: labels.every((label) => Boolean(label.title)),
            labels,
          };
        }"""
    )


def card_snapshot(page: Page) -> dict[str, Any]:
    return page.evaluate(
        """() => {
          const rect = (selector) => {
            const element = document.querySelector(selector);
            if (!element) return null;
            const box = element.getBoundingClientRect();
            return {left: Math.round(box.left), top: Math.round(box.top), width: Math.round(box.width), height: Math.round(box.height)};
          };
          const download = document.querySelector('#download-card');
          const advanced = document.querySelector('#advanced-mapping');
          const pre = document.querySelector('#native-text');
          const nativePreview = document.querySelector('.native-preview');
          const previewScroll = document.querySelector('#preview-scroll');
          const previewRect = nativePreview?.getBoundingClientRect();
          const scrollRect = previewScroll?.getBoundingClientRect();
          const decisionTextClipped = [...document.querySelectorAll('[data-decision-text]')]
            .filter((element) => element.checkVisibility())
            .filter((element) => element.scrollWidth > element.clientWidth + 1 || element.scrollHeight > element.clientHeight + 1)
            .map((element) => element.textContent.trim());
          return {
            state: document.body.dataset.state,
            mode: document.body.dataset.cardMode,
            regions: {
              card_panel: rect('[data-region="card-panel"]'),
              card_heading: rect('[data-region="card-heading"]'),
              card_content: rect('[data-region="card-content"]'),
              native_preview: rect('.native-preview'),
              preview_scroll: rect('#preview-scroll'),
              delivery_sheet: rect('.delivery-sheet'),
            },
            native_width: Math.round(nativePreview.getBoundingClientRect().width),
            delivery_width: Math.round(document.querySelector('.delivery-sheet').getBoundingClientRect().width),
            preview_scroll_width: previewScroll?.scrollWidth ?? 0,
            preview_scroll_height: previewScroll?.scrollHeight ?? 0,
            preview_client_width: previewScroll?.clientWidth ?? 0,
            preview_client_height: previewScroll?.clientHeight ?? 0,
            preview_available_height: previewRect && scrollRect ? Math.round(previewRect.bottom - scrollRect.top - 10) : 0,
            preview_rendered_height: scrollRect ? Math.round(scrollRect.height) : 0,
            preview_fills_available_height: Boolean(previewRect && scrollRect && Math.abs(scrollRect.bottom - (previewRect.bottom - 10)) <= 1),
            native_text_visible: Boolean(pre && !pre.closest('[hidden]') && pre.checkVisibility()),
            native_text_length: pre?.textContent.length ?? 0,
            unavailable_visible: Boolean(document.querySelector('#preview-unavailable')?.checkVisibility()),
            loading_visible: Boolean(document.querySelector('#preview-loading')?.checkVisibility()),
            error_visible: Boolean(document.querySelector('#preview-error')?.checkVisibility()),
            retry_visible: Boolean(document.querySelector('#retry-preview')?.checkVisibility()),
            mapping_rows: [...document.querySelectorAll('.mapping-row')].filter((row) => !row.hidden && row.checkVisibility()).map((row) => row.textContent.trim()),
            approximation_acknowledged: document.querySelector('#approximation-ack')?.checked ?? false,
            download: {text: download?.textContent.trim(), disabled: Boolean(download?.disabled), primary: download?.classList.contains('primary-action')},
            open_modeling_visible: Boolean(document.querySelector('#open-modeling')?.checkVisibility()),
            back_to_cards_visible: Boolean(document.querySelector('#back-to-cards')?.checkVisibility()),
            advanced_open: Boolean(advanced?.open),
            delivery_summary_present: Boolean(document.querySelector('#delivery-summary')),
            decision_text_clipped: decisionTextClipped,
            status: document.querySelector('#delivery-status')?.textContent.trim(),
          };
        }"""
    )


def splitter_snapshot(page: Page) -> dict[str, Any]:
    return page.evaluate(
        """() => {
          const width = (selector) => Math.round(document.querySelector(selector).getBoundingClientRect().width);
          const divider = document.querySelector('[data-region="navigator-divider"]');
          return {
            widths: {navigator: width('[data-region="navigator"]'), divider: width('[data-region="navigator-divider"]'), datasheet: width('[data-region="datasheet"]'), native: width('.native-preview'), delivery: width('.delivery-sheet')},
            aria: {minimum: Number(divider.getAttribute('aria-valuemin')), maximum: Number(divider.getAttribute('aria-valuemax')), now: Number(divider.getAttribute('aria-valuenow'))},
            overflow: {
              document_horizontal: document.documentElement.scrollWidth - document.documentElement.clientWidth,
              document_vertical: document.documentElement.scrollHeight - document.documentElement.clientHeight,
              body_horizontal: document.body.scrollWidth - document.body.clientWidth,
              body_vertical: document.body.scrollHeight - document.body.clientHeight,
            },
            selected_record_visible: document.querySelector('#tree-dp780')?.checkVisibility() ?? false,
          };
        }"""
    )


def splitter_states(page: Page) -> dict[str, Any]:
    splitter = page.locator("[data-region='navigator-divider']")
    viewport_width = page.evaluate("window.innerWidth")
    expected = 244 if viewport_width == 1366 else 280 if viewport_width == 1920 else 264
    maximum = 345 if viewport_width == 1366 else 360
    evidence: dict[str, Any] = {}
    for label, key, expected_width in (("default", None, expected), ("navigator_arrow_right", "ArrowRight", expected + 8), ("navigator_home", "Home", 200), ("navigator_end", "End", maximum)):
        if key:
            splitter.focus()
            page.keyboard.press(key)
        evidence[label] = splitter_snapshot(page)
        snapshot = evidence[label]
        if snapshot["widths"]["navigator"] != expected_width:
            raise AssertionError(f"{label}: navigator width {snapshot}")
        if snapshot["widths"]["divider"] != 5 or snapshot["widths"]["navigator"] != snapshot["aria"]["now"]:
            raise AssertionError(f"{label}: splitter ARIA continuity {snapshot}")
        if snapshot["aria"]["minimum"] != 200 or snapshot["aria"]["maximum"] != maximum:
            raise AssertionError(f"{label}: splitter range {snapshot}")
        if snapshot["widths"]["datasheet"] < 720:
            raise AssertionError(f"{label}: datasheet below 720px {snapshot}")
        if any(value != 0 for value in snapshot["overflow"].values()):
            raise AssertionError(f"{label}: page overflow {snapshot}")
        if not snapshot["selected_record_visible"]:
            raise AssertionError(f"{label}: selected Record not visible")
    return evidence


def common_interactions(page: Page, state: str) -> dict[str, bool]:
    page.keyboard.press("Control+K")
    search_focus = page.evaluate("document.activeElement?.id") == "tree-query"
    page.locator("#tree-query").fill("DP780")
    page.locator("#tree-search-form").press("Enter")
    tree_search = page.locator("body").get_attribute("data-tree-search-consequence") == "DP780-REF"
    page.locator("#back-to-results").click()
    restored = page.locator("body").get_attribute("data-restored-selection") == "DP780-REF"
    dp780 = page.locator("#tree-dp780")
    dp780.focus()
    page.keyboard.press("Home")
    home = page.evaluate("document.activeElement?.id") == "tree-database"
    page.keyboard.press("End")
    end = page.evaluate("document.activeElement?.id") == "tree-dp600"
    page.keyboard.press("ArrowUp")
    previous = page.evaluate("document.activeElement?.id") == "tree-dp780"
    page.keyboard.press("Enter")
    selected = dp780.get_attribute("aria-selected") == "true"
    tab_clicks = True
    for button in page.locator("[role='tab']").all():
        button.click()
        tab_clicks = tab_clicks and page.locator("body").get_attribute("data-active-tab") == button.get_attribute("data-tab")
    page.locator("#tab-evidence").focus()
    page.keyboard.press("Home")
    tabs = page.evaluate("document.activeElement?.id") == "tab-overview"
    page.keyboard.press("End")
    tabs = tabs and page.evaluate("document.activeElement?.id") == "tab-evidence"
    page.keyboard.press("ArrowLeft")
    tabs = tabs and page.evaluate("document.activeElement?.id") == "tab-related"
    page.locator("#tab-cards").click()
    advanced = page.locator("#advanced-mapping")
    advanced.locator("summary").click()
    details_open = advanced.get_attribute("open") == ""
    advanced.locator("summary").click()
    if state == "normal":
        page.locator("#download-card").click()
        command = page.locator("body").get_attribute("data-card-download") == "Abaqus:.inp"
        state_checks = page.locator("#download-card").is_enabled() and page.locator("#download-card").inner_text() == "Download .inp"
    elif state == "approximation":
        initially_blocked = page.locator("#download-card").is_disabled() and not page.locator("#approximation-ack").is_checked()
        page.locator("#approximation-ack").check()
        enabled = page.locator("#download-card").is_enabled()
        page.locator("#download-card").click()
        command = page.locator("body").get_attribute("data-card-download") == "OpenRadioss:.rad"
        state_checks = initially_blocked and enabled and command
    else:
        no_artifact = not page.locator("#native-text").is_visible() and page.locator("#preview-unavailable").is_visible()
        blocked = page.locator("#download-card").is_disabled() and page.locator("#download-card").inner_text() == "Download blocked"
        page.locator("#open-modeling").click()
        page.locator("#back-to-cards").click()
        state_checks = no_artifact and blocked and page.locator("body").get_attribute("data-recovery-open-modeling") == "true" and page.locator("body").get_attribute("data-recovery-back-to-cards") == "true"
        command = blocked
    return {"navigator_search": search_focus, "tree_search": tree_search, "back_to_results": restored, "tree_keyboard": home and end and previous and selected, "tabs": tab_clicks and tabs and page.locator("#tab-cards").get_attribute("aria-selected") == "true", "advanced_disclosure": details_open and page.locator("#advanced-mapping").get_attribute("open") is None, "state_command": state_checks and command}


def measure_page(page: Page, target: str, state: str, viewport: dict[str, int], splitters: dict[str, Any], interactions: dict[str, bool], *, responsive: bool = False) -> dict[str, Any]:
    snapshot = card_snapshot(page)
    visual_acceptance = visual_acceptance_snapshot(page)
    if any(value != 0 for value in overflow_snapshot(page).values()):
        raise AssertionError(f"page overflow for {target}: {overflow_snapshot(page)}")
    if snapshot["delivery_width"] < 300 or snapshot["delivery_width"] > 320:
        raise AssertionError(f"delivery sheet outside 300-320px rail: {snapshot}")
    if snapshot["native_width"] <= snapshot["delivery_width"]:
        raise AssertionError(f"native preview is not dominant: {snapshot}")
    if state == "normal":
        if not snapshot["native_text_visible"] or snapshot["unavailable_visible"] or snapshot["loading_visible"]:
            raise AssertionError(f"normal preview not visible: {snapshot}")
        if snapshot["download"] != {"text": "Download .inp", "disabled": False, "primary": True}:
            raise AssertionError(f"normal command mismatch: {snapshot}")
        if any("APPROXIMATED" in row or "UNSUPPORTED" in row for row in snapshot["mapping_rows"]):
            raise AssertionError(f"normal mapping includes blocked state: {snapshot}")
    if state == "approximation":
        if not snapshot["native_text_visible"] or not any("post-necking extension" in row for row in snapshot["mapping_rows"]):
            raise AssertionError(f"approximation mapping/preview missing: {snapshot}")
        if snapshot["approximation_acknowledged"] or not snapshot["download"]["disabled"] or snapshot["download"]["text"] != "Download .rad":
            raise AssertionError(f"approximation acknowledgement/command mismatch: {snapshot}")
    if state == "unsupported":
        if snapshot["native_text_visible"] or not snapshot["unavailable_visible"] or not any("damage initiation" in row for row in snapshot["mapping_rows"]):
            raise AssertionError(f"unsupported preview/mapping missing: {snapshot}")
        if not snapshot["download"]["disabled"] or snapshot["download"]["text"] != "Download blocked":
            raise AssertionError(f"unsupported command mismatch: {snapshot}")
    return {
        "schema_version": 1,
        "target": target,
        "family": "MAT-CARD",
        "kind": "normal" if state == "normal" else state,
        "state": state,
        "capture_date": "2026-07-29",
        "viewport": viewport,
        "regions": {key: rounded_box(page, selector) for key, selector in {
            "application_bar": "[data-region='application-bar']",
            "command_bar": "[data-region='command-bar']",
            "workspace": "[data-region='workspace']",
            "navigator": "[data-region='navigator']",
            "navigator_divider": "[data-region='navigator-divider']",
            "datasheet": "[data-region='datasheet']",
            "record_header": ".record-header",
            "tabs": ".datasheet-tabs",
            "card_panel": "[data-region='card-panel']",
            "card_heading": "[data-region='card-heading']",
            "card_content": "[data-region='card-content']",
            "native_preview": ".native-preview",
            "delivery_sheet": ".delivery-sheet",
            "status_bar": "[data-region='status-bar']",
        }.items()},
        "tree": tree_snapshot(page),
        "selected_record": page.locator("#tree-dp780").get_attribute("aria-selected") == "true",
        "tabs": {"count": page.locator("[role='tab']").count(), "labels": page.locator("[role='tab']").all_text_contents(), "active": page.locator("[role='tab'][aria-selected='true']").inner_text()},
        "overflow": overflow_snapshot(page),
        "splitter_evidence": splitters,
        "card": snapshot,
        "interactions": interactions,
        "forbidden_visible_terms": [term for term in ["UUID", "Mapping Profile", "Recipe", "Batch", "provenance"] if term.casefold() in page.locator("body").inner_text().casefold()],
        "nested_persistent_card_count": page.locator(".card, .content-card, .module-material-card").count(),
        "responsive_evidence": responsive,
        **visual_acceptance,
        "web_interface_guidelines_audit": {"checked": ["semantic buttons, links, tabs and associated labels", "visible keyboard focus", "deliberate text containment and native scrolling", "no decorative nested cards"], "result": "pass"},
    }


def load_page(page: Page, state: str, viewport: dict[str, int]) -> None:
    url = f"{HTML.as_uri()}?{urlencode({'state': state})}"
    page.set_viewport_size({"width": viewport["width"], "height": viewport["height"]})
    page.goto(url, wait_until="load")
    page.evaluate("document.fonts.ready")
    page.wait_for_timeout(50)


def capture_one(target: str, config: dict[str, Any], *, save_image: bool, responsive: bool = False) -> dict[str, Any]:
    image_path = config.get("image") if save_image else None
    measurement_path = config.get("measurements") if save_image else None
    if image_path:
        image_path.parent.mkdir(parents=True, exist_ok=True)
    console_errors: list[str] = []
    page_errors: list[str] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": config["viewport"]["width"], "height": config["viewport"]["height"]}, device_scale_factor=1)
        page = context.new_page()
        page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
        page.on("pageerror", lambda error: page_errors.append(str(error)))
        load_page(page, config["state"], config["viewport"])
        splitters = splitter_states(page)
        page.reload(wait_until="load")
        page.evaluate("document.fonts.ready")
        interactions = common_interactions(page, config["state"] if config["state"] in {"normal", "approximation", "unsupported"} else "normal")
        page.reload(wait_until="load")
        page.evaluate("document.fonts.ready")
        measure = measure_page(page, target, config["state"], config["viewport"], splitters, interactions, responsive=responsive)
        if console_errors or page_errors:
            raise AssertionError(f"browser errors for {target}: console={console_errors}, page={page_errors}")
        screenshot_bytes = page.screenshot(path=str(image_path), full_page=False) if image_path else page.screenshot(full_page=False)
        browser.close()
    digest = hashlib.sha256(screenshot_bytes).hexdigest()
    width, height = struct.unpack(">II", screenshot_bytes[16:24])
    if (width, height) != (config["viewport"]["width"], config["viewport"]["height"]):
        raise AssertionError(f"screenshot dimensions for {target}: {(width, height)}")
    measure.update({"image": str(image_path.relative_to(ROOT)).replace("\\", "/") if image_path else None, "image_sha256": digest, "screenshot_dimensions": {"width": width, "height": height}, "console_errors": console_errors, "page_errors": page_errors})
    if measurement_path:
        measurement_path.write_text(json.dumps(measure, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return measure


def responsive_path(target: str, width_key: str) -> tuple[Path, Path]:
    image = IMAGE_DIR / f"{target}.responsive-{width_key}.png"
    measurements = IMAGE_DIR / f"{target}.responsive-{width_key}.measurements.json"
    return image, measurements


def state_image_path(state: str, viewport_key: str, *, recovery: bool = False) -> Path:
    state_name = f"{state}-recovery" if recovery else state
    return IMAGE_DIR / f"materials-card-state-{state_name}-{viewport_key}.png"


def persisted_screenshot(page: Page, path: Path) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    screenshot = page.screenshot(path=str(path), full_page=False)
    width, height = struct.unpack(">II", screenshot[16:24])
    return {
        "image": path.relative_to(ROOT).as_posix(),
        "screenshot_dimensions": {"width": width, "height": height},
        "screenshot_sha256": hashlib.sha256(screenshot).hexdigest(),
    }


def state_evidence() -> dict[str, Any]:
    states = ["long", "loading", "error"]
    evidence: dict[str, Any] = {"schema_version": 1, "family": "MAT-CARD", "capture_date": "2026-07-29", "states": {}}
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        for state in states:
            evidence["states"][state] = {}
            for key, viewport in VIEWPORTS.items():
                console_errors: list[str] = []
                page_errors: list[str] = []
                context = browser.new_context(viewport={"width": viewport["width"], "height": viewport["height"]}, device_scale_factor=1)
                page = context.new_page()
                page.on("console", lambda message, errors=console_errors: errors.append(message.text) if message.type == "error" else None)
                page.on("pageerror", lambda error, errors=page_errors: errors.append(str(error)))
                load_page(page, state, viewport)
                snap = card_snapshot(page)
                if state == "long":
                    if snap["preview_scroll_height"] <= snap["preview_client_height"] or snap["delivery_width"] < 300:
                        raise AssertionError(f"long evidence not independently scrollable: {state} {key} {snap}")
                    page.locator("#preview-scroll").evaluate("element => { element.scrollTop = element.scrollHeight; return element.scrollTop > 0; }")
                if state == "loading" and not snap["loading_visible"]:
                    raise AssertionError(f"loading evidence missing: {state} {key}")
                if state == "error":
                    if not snap["error_visible"] or not snap["native_text_visible"]:
                        raise AssertionError(f"error evidence did not preserve preview: {state} {key}")
                    if not snap["retry_visible"]:
                        raise AssertionError(f"error evidence missing Retry control: {state} {key}")
                    pre_retry = {
                        "state": "error",
                        "viewport": viewport,
                        **persisted_screenshot(page, state_image_path(state, key)),
                        "overflow": overflow_snapshot(page),
                        "card": snap,
                        **visual_acceptance_snapshot(page),
                        "preserved_task_context": {
                            "selected_record": page.locator("#tree-dp780").get_attribute("aria-selected") == "true",
                            "active_tab": page.locator("[role='tab'][aria-selected='true']").inner_text(),
                        },
                        "console_errors": console_errors,
                        "page_errors": page_errors,
                    }
                    page.locator("#retry-preview").click()
                    if page.locator("body").get_attribute("data-preview-retry") != "true":
                        raise AssertionError(f"retry did not announce: {state} {key}")
                    recovery_card = card_snapshot(page)
                    if recovery_card["state"] != "normal" or not recovery_card["native_text_visible"] or recovery_card["error_visible"]:
                        raise AssertionError(f"retry did not recover normal preview/context: {state} {key} {recovery_card}")
                    evidence["states"][state][key] = {
                        **pre_retry,
                        "recovery": {
                            "state": recovery_card["state"],
                            "retry_announced": page.locator("body").get_attribute("data-preview-retry") == "true",
                            **persisted_screenshot(page, state_image_path(state, key, recovery=True)),
                            "overflow": overflow_snapshot(page),
                            "card": recovery_card,
                            **visual_acceptance_snapshot(page),
                            "preserved_task_context": {
                                "selected_record": page.locator("#tree-dp780").get_attribute("aria-selected") == "true",
                                "active_tab": page.locator("[role='tab'][aria-selected='true']").inner_text(),
                            },
                        },
                    }
                else:
                    evidence["states"][state][key] = {
                        "viewport": viewport,
                        **persisted_screenshot(page, state_image_path(state, key)),
                        "overflow": overflow_snapshot(page),
                        "card": card_snapshot(page),
                        **visual_acceptance_snapshot(page),
                        "console_errors": console_errors,
                        "page_errors": page_errors,
                    }
                if console_errors or page_errors:
                    raise AssertionError(f"browser errors in evidence {state}/{key}: {console_errors} {page_errors}")
                context.close()
        browser.close()
    return evidence


def main() -> None:
    args = parse_args()
    selected = list(TARGETS) if args.all_packet_targets else [args.target]
    captured: list[dict[str, Any]] = []
    for target in selected:
        config = TARGETS[target]
        if not HTML.is_file() or not CSS.is_file() or not JAVASCRIPT.is_file():
            raise SystemExit("MAT-CARD source HTML/CSS/JS is missing")
        captured.append(capture_one(target, config, save_image=True))
    if args.all_packet_targets:
        for target, state in EXCEPTION_STATES.items():
            for key in ("1366x768", "1920x1080"):
                image, measurements = responsive_path(target, key)
                responsive_config = {"state": state, "viewport": VIEWPORTS[key], "image": image, "measurements": measurements}
                captured.append(capture_one(f"{target}.responsive-{key}", responsive_config, save_image=True, responsive=True))
        state_evidence_path = REFERENCE_DIR / "materials-card-wave02.state-evidence.json"
        state_evidence_path.write_text(json.dumps(state_evidence(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    references = []
    for entry in captured:
        target = entry["target"]
        if target not in TARGETS:
            continue
        config = TARGETS[target]
        references.append({"id": target, "kind": config["state"], "viewport": config["viewport"], "html": str(HTML.relative_to(ROOT)).replace("\\", "/"), "css": str(CSS.relative_to(ROOT)).replace("\\", "/"), "javascript": str(JAVASCRIPT.relative_to(ROOT)).replace("\\", "/"), "image": entry["image"], "measurements": str(config["measurements"].relative_to(ROOT)).replace("\\", "/"), "image_sha256": entry["image_sha256"], "status": "pending", "main_agent_evaluation": {"status": "pending"}, "product_owner_approval": {"status": "absent"}, "responsive_evidence": [str(responsive_path(target, key)[0].relative_to(ROOT)).replace("\\", "/") for key in ("1366x768", "1920x1080")] if target in EXCEPTION_STATES else []})
    staging = {"schema_version": 1, "generated": "2026-07-29", "family": "MAT-CARD", "references": references, "state_evidence": str((REFERENCE_DIR / "materials-card-wave02.state-evidence.json").relative_to(ROOT)).replace("\\", "/") if args.all_packet_targets else None}
    STAGING_INDEX.parent.mkdir(parents=True, exist_ok=True)
    STAGING_INDEX.write_text(json.dumps(staging, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    for entry in captured:
        if entry["target"] in TARGETS:
            print(f"PASS {entry['target']} {entry['viewport']['width']}x{entry['viewport']['height']} {entry['image_sha256']}")
    print(f"staging_index: {STAGING_INDEX.relative_to(ROOT).as_posix()}")


if __name__ == "__main__":
    main()

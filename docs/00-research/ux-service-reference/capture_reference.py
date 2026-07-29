from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from playwright.sync_api import Page, sync_playwright

TARGET_ID_1440 = "materials-search-normal-1440x900"
TARGET_ID_1366 = "materials-search-normal-1366x768"
TARGET_ID_1920 = "materials-search-normal-1920x1080"
ROOT = Path(__file__).resolve().parents[3]
TARGETS = {
    TARGET_ID_1440: {
        "html": ROOT / "docs/00-research/ux-service-reference/materials-search-normal.html",
        "image": ROOT
        / (
            "docs/17-evidence/images/issue-167-service-reference/"
            "materials-search-normal-1440x900.png"
        ),
        "measurements": ROOT
        / (
            "docs/17-evidence/images/issue-167-service-reference/"
            "materials-search-normal-1440x900.measurements.json"
        ),
        "viewport": {"width": 1440, "height": 900, "device_scale_factor": 1},
        "navigator_width": 264,
        "context_visible": True,
        "context_width": 280,
        "expected_divider_count": 2,
        "result_width": {"exact": 870},
    },
    TARGET_ID_1366: {
        "html": ROOT / "docs/00-research/ux-service-reference/materials-search-normal.html",
        "css_override": ROOT
        / "docs/00-research/ux-service-reference/materials-search-normal-1366x768.css",
        "javascript_override": ROOT
        / "docs/00-research/ux-service-reference/materials-search-normal-1366x768.js",
        "image": ROOT
        / (
            "docs/17-evidence/images/issue-167-service-reference/"
            "materials-search-normal-1366x768.png"
        ),
        "measurements": ROOT
        / (
            "docs/17-evidence/images/issue-167-service-reference/"
            "materials-search-normal-1366x768.measurements.json"
        ),
        "viewport": {"width": 1366, "height": 768, "device_scale_factor": 1},
        "navigator_width": 244,
        "context_visible": True,
        "context_width": 280,
        "expected_divider_count": 2,
        "result_width": {"exact": 816},
        "splitter_expectations": {
            "default": {
                "widths": [244, 816, 280],
                "aria_now": [244, 280],
                "aria_maximum": [340, 376],
            },
            "navigator_arrow_right": {
                "widths": [252, 808, 280],
                "aria_now": [252, 280],
                "aria_maximum": [340, 368],
            },
            "navigator_home": {
                "widths": [200, 860, 280],
                "aria_now": [200, 280],
                "aria_maximum": [340, 420],
            },
            "navigator_end": {
                "widths": [340, 720, 280],
                "aria_now": [340, 280],
                "aria_maximum": [340, 280],
            },
            "context_arrow_left": {
                "widths": [244, 808, 288],
                "aria_now": [244, 288],
                "aria_maximum": [332, 376],
            },
            "context_home": {
                "widths": [244, 836, 260],
                "aria_now": [244, 260],
                "aria_maximum": [360, 376],
            },
            "context_end": {
                "widths": [244, 720, 376],
                "aria_now": [244, 376],
                "aria_maximum": [244, 376],
            },
        },
        "splitter_steps": [
            {"label": "navigator_arrow_right", "splitter": "navigator", "key": "ArrowRight"},
            {"label": "navigator_home", "splitter": "navigator", "key": "Home"},
            {"label": "navigator_end", "splitter": "navigator", "key": "End"},
            {
                "label": "context_arrow_left",
                "splitter": "context",
                "key": "ArrowLeft",
                "reload": True,
            },
            {"label": "context_home", "splitter": "context", "key": "Home"},
            {"label": "context_end", "splitter": "context", "key": "End"},
        ],
    },
    TARGET_ID_1920: {
        "html": ROOT / "docs/00-research/ux-service-reference/materials-search-normal.html",
        "css_override": ROOT
        / "docs/00-research/ux-service-reference/materials-search-normal-1920x1080.css",
        "javascript_override": ROOT
        / "docs/00-research/ux-service-reference/materials-search-normal-1920x1080.js",
        "image": ROOT
        / (
            "docs/17-evidence/images/issue-167-service-reference/"
            "materials-search-normal-1920x1080.png"
        ),
        "measurements": ROOT
        / (
            "docs/17-evidence/images/issue-167-service-reference/"
            "materials-search-normal-1920x1080.measurements.json"
        ),
        "viewport": {"width": 1920, "height": 1080, "device_scale_factor": 1},
        "navigator_width": 280,
        "context_visible": True,
        "context_width": 300,
        "expected_divider_count": 2,
        "result_width": {"exact": 1314},
        "splitter_expectations": {
            "default": {
                "widths": [280, 1314, 300],
                "aria_now": [280, 300],
                "aria_maximum": [360, 480],
            },
            "navigator_arrow_right": {
                "widths": [288, 1306, 300],
                "aria_now": [288, 300],
                "aria_maximum": [360, 480],
            },
            "navigator_home": {
                "widths": [200, 1394, 300],
                "aria_now": [200, 300],
                "aria_maximum": [360, 480],
            },
            "navigator_end": {
                "widths": [360, 1234, 300],
                "aria_now": [360, 300],
                "aria_maximum": [360, 480],
            },
            "context_arrow_left": {
                "widths": [280, 1306, 308],
                "aria_now": [280, 308],
                "aria_maximum": [360, 480],
            },
            "context_home": {
                "widths": [280, 1354, 260],
                "aria_now": [280, 260],
                "aria_maximum": [360, 480],
            },
            "context_end": {
                "widths": [280, 1134, 480],
                "aria_now": [280, 480],
                "aria_maximum": [360, 480],
            },
        },
        "splitter_steps": [
            {"label": "navigator_arrow_right", "splitter": "navigator", "key": "ArrowRight"},
            {"label": "navigator_home", "splitter": "navigator", "key": "Home"},
            {"label": "navigator_end", "splitter": "navigator", "key": "End"},
            {
                "label": "context_arrow_left",
                "splitter": "context",
                "key": "ArrowLeft",
                "reload": True,
            },
            {"label": "context_home", "splitter": "context", "key": "Home"},
            {"label": "context_end", "splitter": "context", "key": "End"},
        ],
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Capture and measure a static CAE Material Platform service reference."
    )
    parser.add_argument("--target", choices=sorted(TARGETS), help="Registered reference target id.")
    parser.add_argument("--html", type=Path, help="Exact static HTML path.")
    parser.add_argument("--image", type=Path, help="Exact output PNG path.")
    parser.add_argument("--measurements", type=Path, help="Exact output measurement JSON path.")
    args = parser.parse_args()

    if args.target is None and (args.html is None or args.image is None):
        parser.error("provide --target or both --html and --image")
    return args


def resolve_paths(args: argparse.Namespace) -> tuple[str, Path, Path, Path, dict[str, Any]]:
    registered = TARGETS.get(args.target, {}) if args.target else {}
    html_path = args.html or registered.get("html")
    image_path = args.image or registered.get("image")
    if html_path is None or image_path is None:
        raise SystemExit("target configuration is missing HTML or image path")
    html = html_path.resolve()
    image = image_path.resolve()
    measurements_arg = args.measurements or registered.get("measurements")
    measurements = (
        measurements_arg.resolve()
        if measurements_arg
        else image.with_suffix(".measurements.json")
    )
    target = args.target or image.stem
    config = TARGETS.get(target, TARGETS[TARGET_ID_1440])
    return target, html, image, measurements, config


def rounded_box(page: Page, selector: str) -> dict[str, float]:
    box = page.locator(selector).bounding_box()
    if box is None:
        raise AssertionError(f"{selector} is not visible")
    return {key: round(value, 2) for key, value in box.items()}


def assert_close(actual: float, expected: float, name: str, tolerance: float = 0.6) -> None:
    if abs(actual - expected) > tolerance:
        raise AssertionError(f"{name}: expected {expected}px, got {actual}px")


def assert_between(actual: float, minimum: float, maximum: float, name: str) -> None:
    if actual < minimum or actual > maximum:
        raise AssertionError(f"{name}: expected {minimum} to {maximum}px, got {actual}px")


def collect_measurements(
    page: Page,
    target: str,
    config: dict[str, Any],
    splitter_evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    context_visible = page.locator("[data-region='selected-context']").is_visible()
    regions = {
        "application_bar": rounded_box(page, "[data-region='application-bar']"),
        "command_bar": rounded_box(page, "[data-region='command-bar']"),
        "search_band": rounded_box(page, "[data-region='search-band']"),
        "workspace": rounded_box(page, "[data-region='materials-workspace']"),
        "navigator": rounded_box(page, "[data-region='navigator']"),
        "navigator_divider": rounded_box(page, "[data-region='navigator-divider']"),
        "results": rounded_box(page, "[data-region='results']"),
        "context_divider": (
            rounded_box(page, "[data-region='context-divider']") if context_visible else None
        ),
        "selected_context": (
            rounded_box(page, "[data-region='selected-context']") if context_visible else None
        ),
        "status_bar": rounded_box(page, "[data-region='status-bar']"),
    }
    divider_visual_widths = page.locator(".splitter > span").evaluate_all(
        """(elements) => elements
          .filter((element) => {
            const parent = element.parentElement;
            const parentBox = parent?.getBoundingClientRect();
            const style = parent ? getComputedStyle(parent) : null;
            return style?.display !== "none" && parentBox?.width > 0 && parentBox?.height > 0;
          })
          .map((element) => element.getBoundingClientRect().width)"""
    )
    tree_row_heights = page.locator("[role='treeitem']").evaluate_all(
        "(elements) => elements.map((element) => element.getBoundingClientRect().height)"
    )
    result_row_heights = page.locator("[data-result-row]").evaluate_all(
        "(elements) => elements.map((element) => element.getBoundingClientRect().height)"
    )
    overflow = page.evaluate(
        """() => ({
          documentHorizontal:
            document.documentElement.scrollWidth - document.documentElement.clientWidth,
          documentVertical:
            document.documentElement.scrollHeight - document.documentElement.clientHeight,
          bodyHorizontal: document.body.scrollWidth - document.body.clientWidth,
          bodyVertical: document.body.scrollHeight - document.body.clientHeight
        })"""
    )
    table_headers = page.locator(".results-table th .column-label").all_text_contents()
    sticky_header = page.locator(".results-table th").first.evaluate(
        "(element) => getComputedStyle(element).position"
    )
    tree_scroller = page.locator(".tree-scroll").evaluate(
        """(element) => {
          const contentRight = element.getBoundingClientRect().right;
          const kindRightEdges = [...element.querySelectorAll(".tree-kind")]
            .map((kind) => kind.getBoundingClientRect().right);
          return {
            horizontal_overflow: element.scrollWidth - element.clientWidth,
            content_right: contentRight,
            tree_kind_right_edges: kindRightEdges,
            all_tree_kind_right_edges_within_content:
              kindRightEdges.every((right) => right <= contentRight + 0.01)
          };
        }"""
    )
    context_content = {
        "selected_summary": page.locator(".selected-summary").is_visible(),
        "open_datasheet": page.locator("#open-datasheet").is_visible(),
    }

    return {
        "target": target,
        "capture_date": "2026-07-28",
        "viewport": config["viewport"],
        "regions": regions,
        "divider_visual_widths": divider_visual_widths,
        "visible_splitter_count": len(divider_visual_widths),
        "row_density": {
            "tree": {
                "count": len(tree_row_heights),
                "minimum": min(tree_row_heights),
                "maximum": max(tree_row_heights),
            },
            "results": {
                "count": len(result_row_heights),
                "minimum": min(result_row_heights),
                "maximum": max(result_row_heights),
            },
        },
        "table_headers": table_headers,
        "table_header_position": sticky_header,
        "tree_scroller": tree_scroller,
        "context_content": context_content,
        "selected_result_rows": page.locator("[data-result-row][aria-selected='true']").count(),
        "selected_tree_rows": page.locator("[role='treeitem'][aria-selected='true']").count(),
        "visible_selected_context": context_visible,
        "context_state": "visible" if context_visible else "collapsed",
        "primary_command_count": page.locator(".primary-action").count(),
        "nested_persistent_card_count": page.locator(
            ".card, .content-card, .module-material-card"
        ).count(),
        "overflow": overflow,
        "interactions": {
            "search_shortcut": page.locator("body").get_attribute("data-query-applied") == "steel",
            "tree_keyboard": page.locator("body").get_attribute("data-selected-tree-id")
            == "tree-dp780",
            "result_enter": page.locator("body").get_attribute("data-datasheet-consequence")
            == "DP780-REF",
        },
        "splitter_evidence": splitter_evidence,
    }


def exercise_interactions(page: Page) -> None:
    page.keyboard.press("Control+K")
    active_id = page.evaluate("document.activeElement?.id")
    if active_id != "material-query":
        raise AssertionError(f"Control+K did not focus material-query: {active_id}")
    page.keyboard.press("Enter")
    if page.locator("body").get_attribute("data-query-applied") != "steel":
        raise AssertionError("search submit did not preserve and apply the steel query")

    dp780 = page.locator("#tree-dp780")
    dp780.focus()
    page.keyboard.press("Home")
    if page.evaluate("document.activeElement?.id") != "tree-database":
        raise AssertionError("tree Home did not focus the first row")
    page.keyboard.press("End")
    if page.evaluate("document.activeElement?.id") != "tree-dp600":
        raise AssertionError("tree End did not focus the last row")
    page.keyboard.press("ArrowUp")
    if page.evaluate("document.activeElement?.id") != "tree-dp780":
        raise AssertionError("tree ArrowUp did not move to the previous row")
    page.keyboard.press("ArrowDown")
    if page.evaluate("document.activeElement?.id") != "tree-dp600":
        raise AssertionError("tree ArrowDown did not move to the next row")
    dp780.focus()
    page.keyboard.press("Enter")
    if dp780.get_attribute("aria-selected") != "true":
        raise AssertionError("tree Enter did not select DP780")

    selected_row = page.locator("[data-result-row]").first
    selected_row.focus()
    page.keyboard.press("Enter")
    if page.locator("body").get_attribute("data-datasheet-consequence") != "DP780-REF":
        raise AssertionError("result-row Enter did not expose the datasheet consequence")
    open_datasheet = page.locator("#open-datasheet")
    if open_datasheet.is_visible():
        open_datasheet.click()
        if page.locator("body").get_attribute("data-datasheet-consequence") != "DP780-REF":
            raise AssertionError(
                "Open datasheet did not preserve the selected datasheet consequence"
            )
    page.evaluate("document.activeElement?.blur()")


def splitter_snapshot(page: Page) -> dict[str, Any]:
    return page.evaluate(
        """() => {
          const region = (selector) => Math.round(
            document.querySelector(selector).getBoundingClientRect().width
          );
          const separator = (selector) => {
            const element = document.querySelector(selector);
            return {
              minimum: Number(element.getAttribute('aria-valuemin')),
              maximum: Number(element.getAttribute('aria-valuemax')),
              now: Number(element.getAttribute('aria-valuenow')),
            };
          };
          const treeScroller = document.querySelector('.tree-scroll');
          const treeContentRight = treeScroller.getBoundingClientRect().right;
          const treeKindRightEdges = [...treeScroller.querySelectorAll('.tree-kind')]
            .map((kind) => kind.getBoundingClientRect().right);
          return {
            widths: {
              navigator: region("[data-region='navigator']"),
              results: region("[data-region='results']"),
              context: region("[data-region='selected-context']"),
            },
            aria: {
              navigator: separator("[data-region='navigator-divider']"),
              context: separator("[data-region='context-divider']"),
            },
            selected_context_visible: document.querySelector(
              "[data-region='selected-context']"
            ).checkVisibility(),
            tree_scroller: {
              horizontal_overflow: treeScroller.scrollWidth - treeScroller.clientWidth,
              content_right: treeContentRight,
              tree_kind_right_edges: treeKindRightEdges,
              all_tree_kind_right_edges_within_content:
                treeKindRightEdges.every((right) => right <= treeContentRight + 0.01),
            },
            overflow: {
              documentHorizontal:
                document.documentElement.scrollWidth - document.documentElement.clientWidth,
              documentVertical:
                document.documentElement.scrollHeight - document.documentElement.clientHeight,
              bodyHorizontal: document.body.scrollWidth - document.body.clientWidth,
              bodyVertical: document.body.scrollHeight - document.body.clientHeight,
            },
          };
        }"""
    )


def assert_splitter_snapshot(
    label: str,
    snapshot: dict[str, Any],
    expected: dict[str, list[int]],
) -> None:
    expected_widths = tuple(expected["widths"])
    expected_now = tuple(expected["aria_now"])
    expected_maximum = tuple(expected["aria_maximum"])
    widths = snapshot["widths"]
    actual_widths = (widths["navigator"], widths["results"], widths["context"])
    if actual_widths != expected_widths:
        raise AssertionError(f"{label} widths: expected {expected_widths}, got {actual_widths}")
    navigator_aria = snapshot["aria"]["navigator"]
    context_aria = snapshot["aria"]["context"]
    if (navigator_aria["now"], context_aria["now"]) != expected_now:
        raise AssertionError(
            f"{label} aria now: expected {expected_now}, got "
            f"{(navigator_aria['now'], context_aria['now'])}"
        )
    if (navigator_aria["maximum"], context_aria["maximum"]) != expected_maximum:
        raise AssertionError(
            f"{label} aria maximum: expected {expected_maximum}, got "
            f"{(navigator_aria['maximum'], context_aria['maximum'])}"
        )
    if (navigator_aria["minimum"], context_aria["minimum"]) != (200, 260):
        raise AssertionError(f"{label} aria minimum is not truthful")
    if navigator_aria["now"] != widths["navigator"] or context_aria["now"] != widths["context"]:
        raise AssertionError(f"{label} visible and ARIA pane widths are not synchronized")
    if widths["results"] < 720:
        raise AssertionError(f"{label} result region is below 720px")
    if not snapshot["selected_context_visible"]:
        raise AssertionError(f"{label} selected context is not visible")
    if any(value != 0 for value in snapshot["overflow"].values()):
        raise AssertionError(f"{label} has page overflow: {snapshot['overflow']}")
    tree_scroller = snapshot["tree_scroller"]
    if tree_scroller["horizontal_overflow"] != 0:
        raise AssertionError(
            f"{label} tree scroller horizontal overflow: "
            f"{tree_scroller['horizontal_overflow']}px"
        )
    if not tree_scroller["all_tree_kind_right_edges_within_content"]:
        raise AssertionError(f"{label} tree kind labels extend beyond the content edge")


def exercise_splitters(page: Page, config: dict[str, Any]) -> dict[str, Any]:
    navigator = page.locator("[data-region='navigator-divider']")
    context = page.locator("[data-region='context-divider']")
    evidence: dict[str, Any] = {}
    expectations = config["splitter_expectations"]

    evidence["default"] = splitter_snapshot(page)
    assert_splitter_snapshot("default", evidence["default"], expectations["default"])

    for step in config["splitter_steps"]:
        if step.get("reload"):
            page.reload(wait_until="load")
            page.evaluate("document.fonts.ready")
            inject_target_overrides(page, config)
        splitter = navigator if step["splitter"] == "navigator" else context
        splitter.focus()
        page.keyboard.press(step["key"])
        label = step["label"]
        evidence[label] = splitter_snapshot(page)
        assert_splitter_snapshot(label, evidence[label], expectations[label])

    return evidence


def inject_target_overrides(page: Page, config: dict[str, Any]) -> None:
    if css_override := config.get("css_override"):
        page.add_style_tag(path=str(css_override))
    if javascript_override := config.get("javascript_override"):
        page.add_script_tag(path=str(javascript_override))


def validate_measurements(measurements: dict[str, Any], config: dict[str, Any]) -> None:
    regions = measurements["regions"]
    viewport = config["viewport"]
    assert_close(regions["application_bar"]["height"], 46, "application bar height")
    assert_close(regions["command_bar"]["height"], 38, "command bar height")
    assert_close(regions["search_band"]["height"], 40, "search band height")
    assert_close(regions["status_bar"]["height"], 24, "status bar height")
    assert_close(regions["workspace"]["x"], 8, "workspace left margin")
    assert_close(
        viewport["width"] - regions["workspace"]["x"] - regions["workspace"]["width"],
        8,
        "workspace right margin",
    )
    assert_close(regions["navigator"]["width"], config["navigator_width"], "navigator width")
    assert_close(regions["navigator_divider"]["width"], 5, "navigator divider hit width")
    if config["context_visible"]:
        if regions["selected_context"] is None or regions["context_divider"] is None:
            raise AssertionError("selected context is unexpectedly collapsed")
        assert_close(
            regions["selected_context"]["width"], config["context_width"], "selected context width"
        )
        assert_close(regions["context_divider"]["width"], 5, "context divider hit width")
    elif regions["selected_context"] is not None or regions["context_divider"] is not None:
        raise AssertionError("compact context must be represented as collapsed/null regions")
    if measurements["visible_splitter_count"] != config["expected_divider_count"]:
        raise AssertionError(
            "unexpected visible splitter count: "
            f"{measurements['visible_splitter_count']} (expected "
            f"{config['expected_divider_count']})"
        )
    for index, width in enumerate(measurements["divider_visual_widths"], start=1):
        assert_close(width, 1, f"divider {index} visual width")
    result_width = config["result_width"]
    if "exact" in result_width:
        assert_close(regions["results"]["width"], result_width["exact"], "result width")
    else:
        assert_between(
            regions["results"]["width"],
            result_width["minimum"],
            result_width["maximum"],
            "result width",
        )
    if regions["results"]["width"] < 720:
        raise AssertionError(f"result width below 720px: {regions['results']['width']}px")
    if (
        config["context_visible"]
        and regions["results"]["width"] <= regions["selected_context"]["width"]
    ):
        raise AssertionError("results are not wider than selected context")

    tree_density = measurements["row_density"]["tree"]
    result_density = measurements["row_density"]["results"]
    assert_between(tree_density["minimum"], 24, 26, "minimum tree row height")
    assert_between(tree_density["maximum"], 24, 26, "maximum tree row height")
    assert_between(result_density["minimum"], 32, 36, "minimum result row height")
    assert_between(result_density["maximum"], 32, 36, "maximum result row height")
    if result_density["count"] != 6:
        raise AssertionError(f"expected 6 result rows, got {result_density['count']}")
    if measurements["table_headers"] != [
        "Compare",
        "Material / grade",
        "Family",
        "Description",
        "Status",
    ]:
        raise AssertionError(f"unexpected table headers: {measurements['table_headers']}")
    if measurements["table_header_position"] != "sticky":
        raise AssertionError("table headers are not sticky")
    if measurements["selected_result_rows"] != 1:
        raise AssertionError("normal state must have exactly one selected result row")
    if measurements["selected_tree_rows"] != 1:
        raise AssertionError("normal state must have exactly one selected tree row")
    if measurements["visible_selected_context"] != config["context_visible"]:
        raise AssertionError(
            "selected context visibility mismatch: "
            f"{measurements['visible_selected_context']} (expected "
            f"{config['context_visible']})"
        )
    expected_context_state = "visible" if config["context_visible"] else "collapsed"
    if measurements.get("context_state") != expected_context_state:
        raise AssertionError(
            f"selected context state must be {expected_context_state!r}, "
            f"got {measurements.get('context_state')!r}"
        )
    if measurements["primary_command_count"] != 1:
        raise AssertionError("normal task context must have one filled primary command")
    if measurements["nested_persistent_card_count"] != 0:
        raise AssertionError("nested persistent cards are present")
    tree_scroller = measurements["tree_scroller"]
    if tree_scroller["horizontal_overflow"] != 0:
        raise AssertionError(
            "tree scroller horizontal overflow: "
            f"{tree_scroller['horizontal_overflow']}px"
        )
    if not tree_scroller["all_tree_kind_right_edges_within_content"]:
        raise AssertionError("tree kind labels extend beyond the navigator content edge")
    if config["context_visible"] and not all(measurements["context_content"].values()):
        raise AssertionError(
            "visible selected context is missing its summary or Open datasheet action"
        )
    if any(value != 0 for value in measurements["overflow"].values()):
        raise AssertionError(f"page-level overflow detected: {measurements['overflow']}")
    if not all(measurements["interactions"].values()):
        raise AssertionError(f"interaction exercise failed: {measurements['interactions']}")


def main() -> None:
    args = parse_args()
    target, html, image, measurements_path, config = resolve_paths(args)
    if not html.is_file():
        raise SystemExit(f"HTML does not exist: {html}")
    image.parent.mkdir(parents=True, exist_ok=True)
    measurements_path.parent.mkdir(parents=True, exist_ok=True)

    console_errors: list[str] = []
    page_errors: list[str] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        viewport = config["viewport"]
        context = browser.new_context(
            viewport={"width": viewport["width"], "height": viewport["height"]},
            device_scale_factor=viewport["device_scale_factor"],
        )
        page = context.new_page()
        page.on(
            "console",
            lambda message: console_errors.append(message.text)
            if message.type == "error"
            else None,
        )
        page.on("pageerror", lambda error: page_errors.append(str(error)))
        page.goto(html.as_uri(), wait_until="load")
        page.evaluate("document.fonts.ready")
        inject_target_overrides(page, config)
        splitter_evidence = None
        if config.get("splitter_steps"):
            splitter_evidence = exercise_splitters(page, config)
            page.reload(wait_until="load")
            page.evaluate("document.fonts.ready")
            inject_target_overrides(page, config)
        exercise_interactions(page)
        measurements = collect_measurements(page, target, config, splitter_evidence)
        validate_measurements(measurements, config)
        if console_errors:
            raise AssertionError(f"browser console errors: {console_errors}")
        if page_errors:
            raise AssertionError(f"uncaught page errors: {page_errors}")
        page.screenshot(path=str(image), full_page=False)
        browser.close()

    measurements["image_sha256"] = hashlib.sha256(image.read_bytes()).hexdigest()
    measurements["console_errors"] = console_errors
    measurements["page_errors"] = page_errors
    measurements_path.write_text(
        json.dumps(measurements, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"PASS {target}")
    print(f"image: {image.relative_to(ROOT)}")
    print(f"measurements: {measurements_path.relative_to(ROOT)}")
    context_region = measurements["regions"]["selected_context"]
    context_width = context_region["width"] if context_region else "collapsed"
    print(
        "regions: "
        f"navigator={measurements['regions']['navigator']['width']}px "
        f"results={measurements['regions']['results']['width']}px "
        f"context={context_width}"
    )


if __name__ == "__main__":
    main()

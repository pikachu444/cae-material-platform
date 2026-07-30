from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

import yaml

TARGET_ID_1440 = "materials-search-normal-1440x900"
TARGET_ID_1366 = "materials-search-normal-1366x768"
TARGET_ID_1920 = "materials-search-normal-1920x1080"
ROOT = Path(__file__).resolve().parents[3]
WIDE_VIEWPORTS = ((2560, 1440), (3840, 2160))
MANIFEST_PATH = ROOT / "docs/01-product/service-reference-manifest.yaml"
SHARED_SOURCES = {
    "html": "docs/00-research/ux-service-reference/materials-search-normal.html",
    "css": "docs/00-research/ux-service-reference/reference.css",
    "javascript": "docs/00-research/ux-service-reference/reference.js",
    "capture": "docs/00-research/ux-service-reference/capture_reference.py",
    "validation": "docs/00-research/ux-service-reference/validate_reference.py",
}
NAVIGATOR_SOURCES = {
    "css_navigator": "docs/00-research/ux-service-reference/materials-navigator.css",
    "javascript_navigator": "docs/00-research/ux-service-reference/materials-navigator.js",
}
TARGETS = {
    TARGET_ID_1440: {
        **SHARED_SOURCES,
        **NAVIGATOR_SOURCES,
        "image": (
            "docs/17-evidence/images/issue-167-service-reference/"
            "materials-search-normal-1440x900.png"
        ),
        "measurements": (
            "docs/17-evidence/images/issue-167-service-reference/"
            "materials-search-normal-1440x900.measurements.json"
        ),
        "viewport": {"width": 1440, "height": 900, "device_scale_factor": 1},
        "navigator_width": 264,
        "context_visible": True,
        "context_width": 280,
        "expected_divider_count": 2,
        "result_width": {"exact": 870},
        "splitter_expectations": {
            "default": {
                "widths": [264, 870, 280],
                "aria_now": [264, 280],
                "aria_maximum": [360, 480],
            },
            "navigator_arrow_right": {
                "widths": [272, 862, 280],
                "aria_now": [272, 280],
                "aria_maximum": [360, 480],
            },
            "navigator_home": {
                "widths": [200, 934, 280],
                "aria_now": [200, 280],
                "aria_maximum": [360, 480],
                "tree_horizontal_overflow": 41,
                "tree_horizontal_rail": True,
            },
            "navigator_end": {
                "widths": [360, 774, 280],
                "aria_now": [360, 280],
                "aria_maximum": [360, 480],
            },
        },
        "date": "2026-07-30",
        "reference_status": "approved",
        "approval_date": "2026-07-30",
        "evaluation_status": "accepted",
    },
    TARGET_ID_1366: {
        **SHARED_SOURCES,
        **NAVIGATOR_SOURCES,
        "css_override": (
            "docs/00-research/ux-service-reference/materials-search-normal-1366x768.css"
        ),
        "javascript_override": (
            "docs/00-research/ux-service-reference/materials-search-normal-1366x768.js"
        ),
        "image": (
            "docs/17-evidence/images/issue-167-service-reference/"
            "materials-search-normal-1366x768.png"
        ),
        "measurements": (
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
                "tree_horizontal_overflow": 41,
                "tree_horizontal_rail": True,
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
        "date": "2026-07-30",
        "reference_status": "approved",
        "approval_date": "2026-07-30",
        "evaluation_status": "accepted",
    },
    TARGET_ID_1920: {
        **SHARED_SOURCES,
        **NAVIGATOR_SOURCES,
        "css_override": (
            "docs/00-research/ux-service-reference/materials-search-normal-1920x1080.css"
        ),
        "javascript_override": (
            "docs/00-research/ux-service-reference/materials-search-normal-1920x1080.js"
        ),
        "image": (
            "docs/17-evidence/images/issue-167-service-reference/"
            "materials-search-normal-1920x1080.png"
        ),
        "measurements": (
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
                "tree_horizontal_overflow": 41,
                "tree_horizontal_rail": True,
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
        "date": "2026-07-30",
        "reference_status": "approved",
        "approval_date": "2026-07-30",
        "evaluation_status": "accepted",
    },
}
EXPECTED_COLUMNS = ["Compare", "Material / grade", "Family", "Description", "Status"]
EXPECTED_RESULT_COUNT = "1\u201350 of 10,000 matches"
EXPECTED_RESULT_RANGE = "Rows 1\u201350 of 10,000 matches"
EXPECTED_FIRST_RESULT = ("DP780 synthetic demo steel", "DP780-REF")
EXPECTED_LAST_RESULT = ("Synthetic steel demo record 50", "STEEL-DEMO-50")
FORBIDDEN_VISIBLE_TERMS = [
    "provider",
    "manufacturer",
    "source",
    "yield",
    "condition",
    "property value",
    "solver",
    "card readiness",
    "release",
    "approval",
    "approved",
    "download",
]


class VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style"}:
            self.skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"} and self.skip_depth:
            self.skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self.skip_depth:
            self.parts.append(data)

    def text(self) -> str:
        return " ".join(" ".join(self.parts).split())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate a registered CAE Material Platform static service reference."
    )
    parser.add_argument(
        "--target", choices=sorted(TARGETS), help="Registered reference target id."
    )
    parser.add_argument(
        "--image",
        type=Path,
        help="Exact PNG path; may override the registered image.",
    )
    parser.add_argument(
        "--expect-main-agent-status",
        choices=["pending", "accepted", "rejected"],
        help="Optional expected lifecycle status for the main-agent evaluation.",
    )
    parser.add_argument(
        "--wide-evidence",
        action="store_true",
        help="Validate 2560x1440 and 3840x2160 supporting evidence for the 1920 target.",
    )
    args = parser.parse_args()
    if args.target is None and args.image is None:
        parser.error("provide --target or --image")
    if args.wide_evidence and args.target != TARGET_ID_1920:
        parser.error("--wide-evidence requires --target materials-search-normal-1920x1080")
    return args


def image_dimensions(path: Path) -> tuple[int, int]:
    data = path.read_bytes()[:24]
    if len(data) != 24 or data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        raise ValueError("not a valid PNG with an IHDR header")
    return struct.unpack(">II", data[16:24])


def iso_date(value: Any) -> str:
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def main() -> None:
    args = parse_args()
    target = args.target or TARGET_ID_1440
    expected = TARGETS[target]
    failures: list[str] = []
    checks = 0

    def check(condition: bool, label: str, detail: str) -> None:
        nonlocal checks
        checks += 1
        if not condition:
            failures.append(f"{label}: {detail}")

    required_paths = [
        MANIFEST_PATH,
        *(ROOT / expected[key] for key in (*SHARED_SOURCES, *NAVIGATOR_SOURCES)),
        ROOT / expected["image"],
        ROOT / expected["measurements"],
    ]
    if css_override := expected.get("css_override"):
        required_paths.append(ROOT / css_override)
    if javascript_override := expected.get("javascript_override"):
        required_paths.append(ROOT / javascript_override)
    for path in required_paths:
        check(path.is_file(), "required-files", f"missing {path.relative_to(ROOT)}")
    if failures:
        for failure in failures:
            print(f"FAIL {failure}")
        raise SystemExit(1)

    manifest = yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))
    references = manifest.get("references", [])
    matches = [entry for entry in references if entry.get("id") == target]
    check(
        len(matches) == 1,
        "manifest-entry",
        f"expected one {target} entry, got {len(matches)}",
    )
    if not matches:
        for failure in failures:
            print(f"FAIL {failure}")
        raise SystemExit(1)
    entry = matches[0]

    sources = entry.get("sources", {})
    for key in (*SHARED_SOURCES, *NAVIGATOR_SOURCES):
        check(
            sources.get(key) == expected[key],
            "manifest-source",
            f"{key} must be {expected[key]!r}, got {sources.get(key)!r}",
        )
    check(
        sources.get("css_override") == expected.get("css_override"),
        "manifest-source",
        "css_override must match the target-specific capture source",
    )
    check(
        sources.get("javascript_override") == expected.get("javascript_override"),
        "manifest-source",
        "javascript_override must match the target-specific capture source",
    )
    check(
        entry.get("image") == expected["image"],
        "manifest-image",
        f"expected {expected['image']!r}, got {entry.get('image')!r}",
    )
    check(
        entry.get("measurements") == expected["measurements"],
        "manifest-measurements",
        f"expected {expected['measurements']!r}, got {entry.get('measurements')!r}",
    )

    image = (args.image.resolve() if args.image else ROOT / expected["image"])
    width, height = image_dimensions(image)
    expected_viewport = expected["viewport"]
    check(
        (width, height) == (expected_viewport["width"], expected_viewport["height"]),
        "png-dimensions",
        f"got {width}x{height}",
    )
    viewport = entry.get("viewport", {})
    check(
        viewport == expected_viewport,
        "manifest-viewport",
        f"got {viewport!r}",
    )

    digest = hashlib.sha256(image.read_bytes()).hexdigest()
    check(entry.get("image_sha256") == digest, "sha256", f"expected {digest}")
    check(
        iso_date(entry.get("date")) == expected["date"],
        "date",
        f"expected {expected['date']!r}, got {entry.get('date')!r}",
    )

    vocabulary = manifest.get("status_vocabulary", {})
    reference_statuses = vocabulary.get("reference", [])
    evaluation_statuses = vocabulary.get("main_agent_evaluation", [])
    check(
        set(reference_statuses) == {"pending", "approved", "rejected"},
        "status-vocabulary",
        f"reference vocabulary is {reference_statuses!r}",
    )
    check(
        set(evaluation_statuses) == {"pending", "accepted", "rejected"},
        "status-vocabulary",
        f"evaluation vocabulary is {evaluation_statuses!r}",
    )
    check(
        entry.get("status") in reference_statuses,
        "reference-status",
        f"got {entry.get('status')!r}",
    )
    check(
        entry.get("status") == expected["reference_status"],
        "reference-status",
        f"expected {expected['reference_status']!r}, got {entry.get('status')!r}",
    )
    evaluation = entry.get("main_agent_evaluation", {})
    expected_evaluation_status = (
        args.expect_main_agent_status or expected["evaluation_status"]
    )
    check(
        evaluation.get("status") in evaluation_statuses,
        "main-agent-evaluation",
        f"got {evaluation.get('status')!r}",
    )
    check(
        evaluation.get("status") == expected_evaluation_status,
        "main-agent-evaluation",
        f"expected {expected_evaluation_status!r}, got {evaluation.get('status')!r}",
    )
    if evaluation.get("status") == "pending":
        check(
            evaluation.get("notes") is None,
            "main-agent-evaluation",
            "pending evaluation notes must be unset",
        )
    else:
        check(
            isinstance(evaluation.get("notes"), str) and bool(evaluation["notes"].strip()),
            "main-agent-evaluation",
            "completed evaluation must include notes",
        )
    product_owner_approval = entry.get("product_owner_approval")
    if entry.get("status") == "pending":
        check(
            product_owner_approval == {"status": "absent"},
            "product-owner-approval",
            "pending reference must use the manifest's absent approval convention",
        )
    else:
        check(
            isinstance(product_owner_approval, dict),
            "product-owner-approval",
            "completed reference disposition must include approval evidence",
        )
        if isinstance(product_owner_approval, dict):
            check(
                product_owner_approval.get("status") == entry.get("status"),
                "product-owner-approval",
                "approval status must match the reference status",
            )
            check(
                iso_date(product_owner_approval.get("date")) == expected["approval_date"],
                "product-owner-approval",
                f"unexpected approval date {product_owner_approval.get('date')!r}",
            )

    html_path = ROOT / expected["html"]
    html = html_path.read_text(encoding="utf-8")
    parser = VisibleTextParser()
    parser.feed(html)
    visible_text = parser.text()
    normalized_visible = visible_text.casefold().replace(
        "not validated engineering data.", ""
    )
    for term in FORBIDDEN_VISIBLE_TERMS:
        check(
            re.search(rf"\b{re.escape(term.casefold())}\b", normalized_visible) is None,
            "forbidden-visible-term",
            f"{term!r} is present",
        )
    check(
        re.search(r"\bvalidated\b", normalized_visible) is None,
        "forbidden-visible-term",
        "validated state is present outside the required negated description",
    )
    check(
        re.search(r"\bvalidation\b", normalized_visible) is None,
        "forbidden-visible-term",
        "validation is present",
    )

    columns = re.findall(r'<th[^>]+data-column="([^"]+)"', html)
    check(columns == EXPECTED_COLUMNS, "result-columns", f"got {columns!r}")
    check(html.count("data-result-row") == 50, "result-rows", "expected exactly 50 rows")
    result_names = re.findall(r'data-result-row[^>]+data-name="([^"]+)"', html)
    result_grades = re.findall(r'data-result-row[^>]+data-grade="([^"]+)"', html)
    check(
        len(result_names) == 50 and len(set(result_names)) == 50,
        "result-identities",
        f"expected 50 distinct names, got {len(result_names)}",
    )
    check(
        len(result_grades) == 50 and len(set(result_grades)) == 50,
        "result-identities",
        f"expected 50 distinct grades, got {len(result_grades)}",
    )
    check(
        html.count("data-result-grade=") == 2,
        "tree-result-binding",
        "expected the two visible Record rows to declare exact result bindings",
    )
    required_copy = [
        "steel",
        "Materials Database",
        "Engineering Materials",
        "Demo Material Records",
        "Find folder or record",
        EXPECTED_RESULT_COUNT,
        EXPECTED_RESULT_RANGE,
        "Next page available",
        "Next page",
        "Enter opens · select up to 3 to compare",
        "DP780 synthetic demo steel",
        "DP780-REF",
        "Synthetic local-demo data; not validated engineering data.",
        "Selected material",
        "Open datasheet",
        "r1 · draft",
        "No active job",
        "0 warnings",
        "Online",
    ]
    for text in required_copy:
        check(text in visible_text or text in html, "required-copy", f"missing {text!r}")

    measurements_path = ROOT / expected["measurements"]
    measurements = json.loads(measurements_path.read_text(encoding="utf-8"))
    check(measurements.get("target") == target, "measurements-target", "target id mismatch")
    check(
        measurements.get("viewport") == expected_viewport,
        "measurements-viewport",
        f"got {measurements.get('viewport')!r}",
    )
    check(measurements.get("image_sha256") == digest, "measurements-sha256", "image hash mismatch")
    check(
        not measurements.get("console_errors"),
        "console-errors",
        f"{measurements.get('console_errors')!r}",
    )
    check(
        not measurements.get("page_errors"),
        "page-errors",
        f"{measurements.get('page_errors')!r}",
    )
    check(
        all(value == 0 for value in measurements.get("overflow", {}).values()),
        "page-overflow",
        f"{measurements.get('overflow')!r}",
    )
    check(
        all(measurements.get("interactions", {}).values()),
        "interactions",
        f"{measurements.get('interactions')!r}",
    )

    regions = measurements.get("regions", {})
    check(
        regions.get("navigator", {}).get("width") == expected["navigator_width"],
        "navigator-width",
        f"expected {expected['navigator_width']}px",
    )
    result_width = regions.get("results", {}).get("width")
    expected_result_width = expected["result_width"].get("exact")
    if expected_result_width is not None:
        check(
            result_width == expected_result_width,
            "result-width",
            f"expected {expected_result_width}px, got {result_width}px",
        )
    check(
        result_width is not None and result_width >= 720,
        "result-width",
        f"expected at least 720px, got {result_width}px",
    )
    visible_splitter_count = measurements.get(
        "visible_splitter_count", len(measurements.get("divider_visual_widths", []))
    )
    check(
        visible_splitter_count == expected["expected_divider_count"],
        "splitter-count",
        f"expected {expected['expected_divider_count']}, got {visible_splitter_count}",
    )
    check(
        all(width == 1 for width in measurements.get("divider_visual_widths", [])),
        "splitter-visual-width",
        f"got {measurements.get('divider_visual_widths')!r}",
    )
    context_visible = expected["context_visible"]
    check(
        measurements.get("visible_selected_context") is context_visible,
        "context-visibility",
        f"expected {context_visible}, got {measurements.get('visible_selected_context')!r}",
    )
    expected_context_state = "visible" if context_visible else "collapsed"
    check(
        measurements.get("context_state", expected_context_state) == expected_context_state,
        "context-state",
        f"expected {expected_context_state!r}, got {measurements.get('context_state')!r}",
    )
    if context_visible:
        check(
            regions.get("selected_context", {}).get("width") == expected["context_width"],
            "context-width",
            f"expected {expected['context_width']}px",
        )
        check(
            regions.get("context_divider", {}).get("width") == 5,
            "context-divider",
            f"expected 5px hit width, got {regions.get('context_divider')!r}",
        )
    else:
        check(
            regions.get("selected_context") is None,
            "context-collapsed",
            "compact selected context must be null",
        )
        check(
            regions.get("context_divider") is None,
            "context-collapsed",
            "compact context divider must be null",
        )
    row_density = measurements.get("row_density", {})
    tree_density = row_density.get("tree", {})
    result_density = row_density.get("results", {})
    check(
        tree_density.get("count") == 7
        and tree_density.get("minimum") == 25
        and tree_density.get("maximum") == 25,
        "tree-density",
        f"got {tree_density!r}",
    )
    check(
        result_density.get("count") == 50
        and result_density.get("minimum") == 36
        and result_density.get("maximum") == 36,
        "result-density",
        f"got {result_density!r}",
    )
    check(
        measurements.get("result_count") == EXPECTED_RESULT_COUNT,
        "result-count",
        f"got {measurements.get('result_count')!r}",
    )
    check(
        measurements.get("result_range") == EXPECTED_RESULT_RANGE,
        "result-range",
        f"got {measurements.get('result_range')!r}",
    )
    result_scroller = measurements.get("result_scroller", {})
    result_rows = result_scroller.get("rows", {})
    check(
        result_rows.get("count") == 50,
        "result-scroller-rows",
        f"got {result_rows.get('count')!r}",
    )
    first_result = result_rows.get("first", {})
    check(
        (first_result.get("name"), first_result.get("grade")) == EXPECTED_FIRST_RESULT,
        "result-first-identity",
        f"got {first_result!r}",
    )
    last_result = result_rows.get("last", {})
    check(
        (last_result.get("name"), last_result.get("grade")) == EXPECTED_LAST_RESULT,
        "result-last-identity",
        f"got {last_result!r}",
    )
    check(
        result_scroller.get("horizontal_overflow") == 0,
        "result-scroller-horizontal-overflow",
        f"got {result_scroller.get('horizontal_overflow')!r}",
    )
    check(
        result_scroller.get("visible_rows_fully_contained") is True,
        "result-row-containment",
        f"got {result_scroller.get('visible_rows_fully_contained')!r}",
    )
    result_fixture = measurements.get("result_fixture") or {}
    check(
        result_fixture.get("overflowing") is not None
        and result_fixture.get("sticky_header_at_end") is True
        and result_fixture.get("footer_fixed_at_end") is True
        and result_fixture.get("rails_outside_text") is True,
        "result-scroll-fixture",
        f"got {result_fixture!r}",
    )
    if result_fixture.get("overflowing"):
        check(
            all(
                result_fixture.get(key)
                for key in (
                    "wheel_moved",
                    "page_down_moved",
                    "vertical_end_reached",
                    "vertical_arrow_moved",
                    "vertical_pointer_moved",
                )
            ),
            "result-scroll-interactions",
            f"got {result_fixture!r}",
        )
        check(
            result_scroller.get("rails", {}).get("vertical", {}).get("visible") is True,
            "result-scroll-rail",
            f"got {result_scroller.get('rails', {}).get('vertical')!r}",
        )
    else:
        check(
            result_scroller.get("rails", {}).get("vertical", {}).get("visible") is False,
            "result-scroll-rail",
            f"fake rail got {result_scroller.get('rails', {}).get('vertical')!r}",
        )
    check(
        measurements.get("table_headers") == EXPECTED_COLUMNS,
        "result-columns",
        f"got {measurements.get('table_headers')!r}",
    )
    check(
        measurements.get("table_header_position") == "sticky",
        "sticky-header",
        f"got {measurements.get('table_header_position')!r}",
    )
    check(
        measurements.get("selected_result_rows") == 1,
        "selected-result-row",
        f"got {measurements.get('selected_result_rows')!r}",
    )
    check(
        measurements.get("selected_tree_rows") == 1,
        "selected-tree-row",
        f"got {measurements.get('selected_tree_rows')!r}",
    )
    check(
        measurements.get("primary_command_count") == 1,
        "primary-command",
        f"got {measurements.get('primary_command_count')!r}",
    )
    check(
        measurements.get("nested_persistent_card_count") == 0,
        "nested-persistent-cards",
        f"got {measurements.get('nested_persistent_card_count')!r}",
    )
    if expected.get("splitter_expectations"):
        tree_scroller = measurements.get("tree_scroller", {})
        check(
            tree_scroller.get("horizontal_overflow") == 0,
            "tree-scroller-overflow",
            f"got {tree_scroller.get('horizontal_overflow')!r}",
        )
        check(
            tree_scroller.get("all_tree_kind_right_edges_within_content") is True,
            "tree-kind-containment",
            f"got {tree_scroller.get('tree_kind_right_edges')!r}",
        )
        check(
            tree_scroller.get("vertical_overflow") == 0
            and tree_scroller.get("rails", {}).get("horizontal", {}).get("visible") is False
            and tree_scroller.get("rails", {}).get("vertical", {}).get("visible") is False,
            "tree-scroller-rails",
            f"got {tree_scroller.get('rails')!r}",
        )
        identities = tree_scroller.get("identities") or []
        check(
            len(identities) == 7
            and all(
                item.get("identity") == item.get("title")
                and item.get("glyph_kind") == item.get("kind")
                and item.get("glyph_title") == item.get("kind")
                and item.get("glyph_font_size") == "0px"
                and item.get("accessible_name", "").startswith(f"{item.get('kind')}: ")
                for item in identities
            ),
            "tree-identity-glyphs",
            f"got {identities!r}",
        )
        fixture = measurements.get("navigator_fixture") or {}
        fixture_keys = (
            "wheel_moved",
            "page_down_moved",
            "vertical_end_reached",
            "vertical_arrow_moved",
            "horizontal_end_reached",
            "horizontal_arrow_moved",
            "identity_reachable_at_horizontal_end",
            "vertical_pointer_moved",
            "horizontal_pointer_moved",
            "rails_outside_text",
            "proportional_thumbs",
        )
        check(
            all(fixture.get(key) for key in fixture_keys),
            "navigator-fixture",
            f"got {fixture!r}",
        )
        context_content = measurements.get("context_content", {})
        check(
            context_content.get("selected_summary") is True
            and context_content.get("open_datasheet") is True,
            "selected-context-content",
            f"got {context_content!r}",
        )
        splitter_evidence = measurements.get("splitter_evidence")
        expected_splitter_states = expected["splitter_expectations"]
        check(
            isinstance(splitter_evidence, dict),
            "splitter-evidence",
            "missing target splitter interaction evidence",
        )
        if isinstance(splitter_evidence, dict):
            for label, expected_state in expected_splitter_states.items():
                snapshot = splitter_evidence.get(label, {})
                widths = snapshot.get("widths", {})
                aria = snapshot.get("aria", {})
                navigator_aria = aria.get("navigator", {})
                context_aria = aria.get("context", {})
                actual_widths = (
                    widths.get("navigator"),
                    widths.get("results"),
                    widths.get("context"),
                )
                actual_now = (navigator_aria.get("now"), context_aria.get("now"))
                actual_maximum = (
                    navigator_aria.get("maximum"),
                    context_aria.get("maximum"),
                )
                actual_minimum = (
                    navigator_aria.get("minimum"),
                    context_aria.get("minimum"),
                )
                expected_widths = tuple(expected_state["widths"])
                expected_now = tuple(expected_state["aria_now"])
                expected_maximum = tuple(expected_state["aria_maximum"])
                check(
                    actual_widths == expected_widths,
                    "splitter-evidence",
                    f"{label} widths expected {expected_widths}, got {actual_widths}",
                )
                check(
                    actual_now == expected_now,
                    "splitter-evidence",
                    f"{label} aria now expected {expected_now}, got {actual_now}",
                )
                check(
                    actual_maximum == expected_maximum,
                    "splitter-evidence",
                    f"{label} aria max expected {expected_maximum}, got {actual_maximum}",
                )
                check(
                    actual_minimum == (200, 260),
                    "splitter-evidence",
                    f"{label} aria minimum expected (200, 260), got {actual_minimum}",
                )
                check(
                    actual_now == (widths.get("navigator"), widths.get("context")),
                    "splitter-evidence",
                    f"{label} ARIA now must match visible pane widths",
                )
                check(
                    widths.get("results", 0) >= 720,
                    "splitter-evidence",
                    f"{label} result width is below 720px",
                )
                check(
                    snapshot.get("selected_context_visible") is True,
                    "splitter-evidence",
                    f"{label} selected context is not visible",
                )
                check(
                    all(value == 0 for value in snapshot.get("overflow", {}).values()),
                    "splitter-evidence",
                    f"{label} page overflow {snapshot.get('overflow')!r}",
                )
                snapshot_tree_scroller = snapshot.get("tree_scroller", {})
                expected_tree_overflow = expected_state.get("tree_horizontal_overflow", 0)
                check(
                    snapshot_tree_scroller.get("horizontal_overflow") == expected_tree_overflow,
                    "splitter-evidence",
                    f"{label} tree horizontal overflow expected {expected_tree_overflow}, "
                    f"got {snapshot_tree_scroller.get('horizontal_overflow')!r}",
                )
                check(
                    snapshot_tree_scroller.get("vertical_overflow") == 0
                    and snapshot_tree_scroller.get("rails", {}).get("horizontal")
                    is (expected_tree_overflow > 0)
                    and snapshot_tree_scroller.get("rails", {}).get("vertical") is False,
                    "splitter-evidence",
                    f"{label} tree rail state {snapshot_tree_scroller.get('rails')!r}",
                )
                check(
                    snapshot_tree_scroller.get("all_tree_kind_right_edges_within_content") is True,
                    "splitter-evidence",
                    f"{label} tree kind containment "
                    f"{snapshot_tree_scroller.get('tree_kind_right_edges')!r}",
                )

    if args.wide_evidence:
        for wide_width, wide_height in WIDE_VIEWPORTS:
            wide_stem = (
                f"{Path(expected['image']).stem}.wide-evidence-"
                f"{wide_width}x{wide_height}"
            )
            wide_image = ROOT / Path(expected["image"]).with_name(f"{wide_stem}.png")
            wide_measurements = ROOT / Path(expected["measurements"]).with_name(
                f"{wide_stem}.measurements.json"
            )
            check(wide_image.is_file(), "wide-evidence-files", f"missing {wide_image}")
            check(
                wide_measurements.is_file(),
                "wide-evidence-files",
                f"missing {wide_measurements}",
            )
            if wide_image.is_file() and wide_measurements.is_file():
                wide_data = json.loads(wide_measurements.read_text(encoding="utf-8"))
                check(
                    image_dimensions(wide_image) == (wide_width, wide_height),
                    "wide-evidence-dimensions",
                    f"got {image_dimensions(wide_image)}",
                )
                check(
                    wide_data.get("target") == target
                    and wide_data.get("wide_evidence") is True
                    and wide_data.get("viewport") == {
                        "width": wide_width,
                        "height": wide_height,
                        "device_scale_factor": 1,
                    },
                    "wide-evidence-measurement",
                    f"unexpected metadata {wide_data.get('target')!r}/"
                    f"{wide_data.get('viewport')!r}",
                )
                check(
                    wide_data.get("image_sha256")
                    == hashlib.sha256(wide_image.read_bytes()).hexdigest(),
                    "wide-evidence-sha256",
                    "measurement digest does not match PNG",
                )
                check(
                    not wide_data.get("console_errors") and not wide_data.get("page_errors"),
                    "wide-evidence-browser-errors",
                    f"console={wide_data.get('console_errors')!r}, "
                    f"page={wide_data.get('page_errors')!r}",
                )
                check(
                    all(value == 0 for value in wide_data.get("overflow", {}).values()),
                    "wide-evidence-page-overflow",
                    f"got {wide_data.get('overflow')!r}",
                )
                wide_tree = wide_data.get("tree_scroller", {})
                check(
                    wide_tree.get("horizontal_overflow") == 0
                    and wide_tree.get("vertical_overflow") == 0
                    and wide_tree.get("rails", {}).get("horizontal", {}).get("visible") is False
                    and wide_tree.get("rails", {}).get("vertical", {}).get("visible") is False
                    and len(wide_tree.get("identities", [])) == 7,
                    "wide-evidence-navigator",
                    f"got {wide_tree!r}",
                )
                wide_result = wide_data.get("result_scroller", {})
                wide_result_rows = wide_result.get("rows", {})
                check(
                    wide_result_rows.get("count") == 50
                    and (
                        wide_result_rows.get("first", {}).get("name"),
                        wide_result_rows.get("first", {}).get("grade"),
                    )
                    == EXPECTED_FIRST_RESULT
                    and (
                        wide_result_rows.get("last", {}).get("name"),
                        wide_result_rows.get("last", {}).get("grade"),
                    )
                    == EXPECTED_LAST_RESULT
                    and wide_result.get("horizontal_overflow") == 0,
                    "wide-evidence-results",
                    f"got {wide_result!r}",
                )
                check(
                    wide_result.get("visible_rows_fully_contained") is True,
                    "wide-evidence-result-containment",
                    f"got {wide_result.get('visible_rows_fully_contained')!r}",
                )
                wide_fixture = wide_data.get("result_fixture") or {}
                check(
                    wide_fixture.get("overflowing") is not None
                    and wide_fixture.get("sticky_header_at_end") is True
                    and wide_fixture.get("footer_fixed_at_end") is True,
                    "wide-evidence-result-fixture",
                    f"got {wide_fixture!r}",
                )
                if wide_fixture.get("overflowing"):
                    check(
                        wide_result.get("rails", {}).get("vertical", {}).get("visible") is True
                        and all(
                            wide_fixture.get(key)
                            for key in (
                                "wheel_moved",
                                "page_down_moved",
                                "vertical_end_reached",
                                "vertical_arrow_moved",
                                "vertical_pointer_moved",
                            )
                        ),
                        "wide-evidence-result-rail",
                        f"got {wide_result.get('rails')!r}/{wide_fixture!r}",
                    )
                else:
                    check(
                        wide_result.get("rails", {}).get("vertical", {}).get("visible") is False,
                        "wide-evidence-result-rail",
                        f"fake rail got {wide_result.get('rails')!r}",
                    )

    if failures:
        for failure in failures:
            print(f"FAIL {failure}")
        raise SystemExit(1)
    print(f"PASS {target}: {checks} checks")
    print(
        f"PNG {expected_viewport['width']}x{expected_viewport['height']} · SHA-256 {digest}"
    )
    approval = (
        "unset"
        if product_owner_approval is None
        else str(product_owner_approval.get("status", "recorded"))
    )
    print(
        f"status {entry.get('status')} · "
        f"main-agent evaluation {evaluation.get('status')} · "
        f"product-owner approval {approval}"
    )


if __name__ == "__main__":
    main()

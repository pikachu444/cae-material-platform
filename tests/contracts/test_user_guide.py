from __future__ import annotations

from pathlib import Path

from cmp.tools.user_guide import _documentation_classes, verify_user_guide


def test_user_guide_navigation_links_and_screenshot_evidence_are_current() -> None:
    root = Path(__file__).parents[2]

    report = verify_user_guide(root)

    assert report.document_count >= 10
    assert report.capture_count == 20
    assert report.archived_capture_count >= 100
    assert report.historical_capture_script_count == 12
    assert report.navigation_count == 3
    assert report.classified_markdown_count >= 195
    assert report.current_document_count >= 40
    assert report.local_link_count >= 300
    assert report.image_count >= 200
    assert report.orphan_image_count == 0
    assert report.duplicate_image_group_count == 10


def test_superseded_ux_package_is_historical_not_authoritative() -> None:
    root = Path(__file__).parents[2]

    classes = _documentation_classes(root)

    assert classes["docs/01-product/ux-redesign-package/04_CODEX_MASTER_PROMPT.md"] == "historical"
    assert classes["docs/01-product/desktop-engineering-ui-program-brief.md"] == "authoritative"
    assert classes["docs/user-guide/02-steel-elastoplastic.md"] == "current"
    assert classes["docs/17-evidence/reports/dui-04-modeling-workspace.md"] == "historical"

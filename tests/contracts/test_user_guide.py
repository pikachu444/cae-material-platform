from __future__ import annotations

from pathlib import Path

from cmp.tools.user_guide import verify_user_guide


def test_user_guide_navigation_links_and_screenshot_evidence_are_current() -> None:
    root = Path(__file__).parents[2]

    report = verify_user_guide(root)

    assert report.document_count >= 10
    assert report.capture_count >= 12
    assert report.navigation_count == 3
    assert report.classified_markdown_count >= 175
    assert report.current_document_count >= 15

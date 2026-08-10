from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).parents[2]
CAPTURE = (ROOT / "scripts/capture_high_dpi_decision.py").read_text(encoding="utf-8")
PROTOTYPE = (ROOT / "scripts/high_dpi_decision_prototype.css").read_text(
    encoding="utf-8"
)
PRODUCT_SOURCE = "\n".join(
    path.read_text(encoding="utf-8")
    for path in sorted((ROOT / "apps/web/src").rglob("*"))
    if path.suffix in {".css", ".ts", ".tsx"}
)
VARIANT_BASELINE_FIRST = """VARIANTS = (
    Variant("baseline", None, None),"""


def test_issue_221_capture_has_the_exact_decision_matrix() -> None:
    current_capture = (ROOT / "scripts/capture_current_product.py").read_text(
        encoding="utf-8"
    )
    assert "VIEWPORTS = ((1366, 768), (1440, 900), (1920, 1080))" in current_capture
    assert "WIDE_VIEWPORTS = ((2560, 1440), (3840, 2160))" in current_capture
    assert "VIEWPORTS = (*current.VIEWPORTS, *current.WIDE_VIEWPORTS)" in CAPTURE

    for variant in (
        'Variant("baseline", None, None)',
        'Variant("p1", "p1", "compact")',
        'Variant("p2-compact", "p2", "compact")',
        'Variant("p2-standard", "p2", "standard")',
        'Variant("p2-large", "p2", "large")',
    ):
        assert variant in CAPTURE
    for surface in (
        "materials-search",
        "materials-datasheet",
        "modeling-data",
        "modeling-fit",
        "modeling-export",
        "activity-normal",
        "activity-history",
        "activity-decision-error",
        "activity-recovery",
        "administration-database",
        "administration-records",
    ):
        assert f'"{surface}": Surface(' in CAPTURE


def test_prototype_is_evidence_only_semantic_and_free_of_forbidden_scaling() -> None:
    assert "high_dpi_decision_prototype.css" not in PRODUCT_SOURCE
    assert '[data-cmp-prototype-workspace="three-pane"]' in PROTOTYPE
    assert '[data-cmp-prototype-span="workspace"]' in PROTOTYPE
    assert 'data-cmp-density="standard"' in PROTOTYPE
    assert 'data-cmp-density="large"' in PROTOTYPE

    lowered = PROTOTYPE.lower()
    for forbidden in (
        "zoom:",
        "transform: scale",
        "@media",
        "devicepixelratio",
        "resolution",
        "/materials",
        "/modeling",
        "/activity",
        "/administration",
    ):
        assert forbidden not in lowered


def test_candidate_three_is_measured_but_never_implemented() -> None:
    assert "p3" not in PROTOTYPE
    assert "candidate-three" not in PROTOTYPE
    assert "devicePixelRatio" in CAPTURE
    assert "default_zoom_level" in CAPTURE
    assert '"declaredBrowserZoomPercent"' in CAPTURE
    assert "Chrome did not enter exact browser zoom 200%" in CAPTURE


def test_capture_preserves_state_and_direct_pixel_evidence_contracts() -> None:
    assert CAPTURE.index("for variant in VARIANTS:") > CAPTURE.index(
        "fingerprint = _state_fingerprint(page, surface)"
    )
    assert VARIANT_BASELINE_FIRST in CAPTURE
    assert '"state_fingerprint": fingerprint["sha256"]' in CAPTURE
    assert '"blocked_api_writes": []' in CAPTURE
    assert '"scale": "100 percent / direct 1:1 source pixels"' in CAPTURE
    assert '"status": "PENDING_PRODUCT_OWNER"' in CAPTURE
    assert '"DEFERRED_TO_223"' in CAPTURE
    assert "unnecessaryBidirectionalPageScroll" in CAPTURE
    assert "unreachableInteractiveCount" in CAPTURE
    assert "initiallyClippedInteractiveCount" in CAPTURE
    assert "clippedAfterScrollInteractiveCount" in CAPTURE
    assert "hasReachableInteractionPoint" in CAPTURE
    assert "document.elementsFromPoint" in CAPTURE
    assert "Expand details pane and direct Open datasheet action passed" in CAPTURE
    assert "'data-cmp-prototype-pane-mode', 'overlay'" in CAPTURE
    assert 'data-cmp-prototype-pane="context"' in PROTOTYPE
    assert 'audit["functional_loss_count"]' in CAPTURE
    assert 'audit.setdefault("functional_alternative_coverage", [])' in CAPTURE
    assert '"--merge-surface-manifests"' in CAPTURE
    assert 'f"measurements-{surface_name}.json"' in CAPTURE
    assert "surface manifest image hash drift" in CAPTURE
    assert "evidence PNG set differs from successful surface manifests" in CAPTURE
    assert 'merged["allowed_duplicate_groups"] = _duplicate_image_allowances(output)' in CAPTURE
    assert "relative_to(PROJECT_ROOT)" in CAPTURE
    assert "details:not([open])" in CAPTURE
    assert "current._prepare_exact_target_preview(page)" in CAPTURE
    assert "recovered_append_only" in CAPTURE
    assert "PlaywrightTimeoutError" in CAPTURE
    assert "passed before an extended semantic UI wait" in CAPTURE
    assert "control state passed before one read-only reload retry" in CAPTURE
    assert '"surface": "modeling-data-zoom-200"' in CAPTURE
    assert "plot readiness timed out in the zoom context; exact session" in CAPTURE
    assert "current._data_session_snapshot(page)" in CAPTURE
    assert '"preserved_session": before' in CAPTURE
    restore_zoom = CAPTURE.split("def _restore_zoom_surface", 1)[1].split(
        "def _zoom_functionality_audit", 1
    )[0]
    assert "current._wait_for_settled" not in restore_zoom
    assert "_wait_for_zoom_ui_settled" in restore_zoom

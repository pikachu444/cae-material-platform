from __future__ import annotations

from pathlib import Path

_ROOT = Path(__file__).parents[2]
_TOKENS = (_ROOT / "apps/web/src/design/tokens.css").read_text(encoding="utf-8")
_LAYOUT = (_ROOT / "apps/web/src/design/layout.css").read_text(encoding="utf-8")
_ACTIVITY = _LAYOUT.split(".activity-shell", 1)[1].split(
    "/* Search-first Modeling shell", 1
)[0]
_MARKUP = (_ROOT / "apps/web/src/material-library.tsx").read_text(encoding="utf-8")


def test_activity_consumes_the_shared_compact_baseline() -> None:
    expected_tokens = {
        "--ux-compact-data-font-size": "13px",
        "--ux-compact-emphasis-font-size": "14px",
        "--ux-compact-metadata-font-size": "12px",
        "--ux-compact-table-heading-font-size": "11px",
        "--ux-compact-control-min-height": "36px",
        "--ux-compact-row-min-height": "46px",
        "--ux-compact-pane-padding": "12px",
        "--ux-compact-cell-padding-block": "8px",
        "--ux-compact-cell-padding-inline": "7px",
        "--ux-compact-wide-content-max": "166rem",
    }
    for name, value in expected_tokens.items():
        assert f"{name}: {value};" in _TOKENS
        assert f"var({name})" in _ACTIVITY

    # These selectors must outrank the inherited `.ux-page td/button` baseline;
    # otherwise the semantic tokens appear in source without reaching the UI.
    assert ".activity-saved-views .activity-saved-view {" in _ACTIVITY
    assert ".activity-table .activity-cell-reason {" in _ACTIVITY
    assert ".activity-table .activity-cell-status {" in _ACTIVITY
    assert ".activity-table .activity-cell-updated {" in _ACTIVITY


def test_activity_grid_keeps_semantic_columns_adjacent_without_a_high_dpi_override() -> None:
    assert "max-width: var(--ux-compact-wide-content-max);" in _ACTIVITY
    assert "width: min(100%, var(--ux-compact-wide-content-max));" in _ACTIVITY
    assert ".activity-column-task { width: 20%; }" in _ACTIVITY
    assert ".activity-column-reason { width: 48%; }" in _ACTIVITY
    assert ".activity-column-status { width: 12%; }" in _ACTIVITY
    assert ".activity-column-updated { width: 12%; }" in _ACTIVITY
    assert ".activity-column-action { width: 8%; }" in _ACTIVITY
    assert '<col className="activity-column-task" />' in _MARKUP
    assert "@media (min-width" not in _ACTIVITY
    assert "zoom:" not in _ACTIVITY
    assert "transform: scale" not in _ACTIVITY

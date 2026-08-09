from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).parents[2]
TOKENS = (ROOT / "apps/web/src/design/tokens.css").read_text(encoding="utf-8")
LAYOUT = (ROOT / "apps/web/src/design/layout.css").read_text(encoding="utf-8")
PRIMITIVES = (ROOT / "apps/web/src/design/primitives.css").read_text(encoding="utf-8")
SHELL = (ROOT / "apps/web/src/design/shell.css").read_text(encoding="utf-8")
LEGACY = (ROOT / "apps/web/src/styles.css").read_text(encoding="utf-8")
METRICS = (ROOT / "apps/web/src/design/metrics.ts").read_text(encoding="utf-8")
ACTIVE_CSS = "\n".join((TOKENS, LAYOUT, PRIMITIVES, SHELL, LEGACY))
DESIGN_CSS = "\n".join(
    path.read_text(encoding="utf-8")
    for path in sorted((ROOT / "apps/web/src/design").glob("*.css"))
)


def test_shared_semantic_tokens_own_desktop_density_and_layout_boundaries() -> None:
    required = (
        "--ux-text-subtle",
        "--ux-selection",
        "--ux-success-soft",
        "--ux-danger-soft",
        "--ux-shadow-float",
        "--ux-space-8",
        "--ux-data-font-size",
        "--ux-metadata-font-size",
        "--ux-control-min-block-size",
        "--ux-work-row-min-block-size",
        "--ux-navigator-row-block-size",
        "--ux-pane-padding",
        "--ux-workspace-max-inline-size: none",
        "--ux-workspace-max-block-size: none",
        "--ux-readable-form-max-inline-size",
        "--ux-comparison-table-max-inline-size",
        "--ux-splitter-inline-size",
        "--ux-scrollbar-thumb-min-size",
        "--ux-plot-min-block-size",
    )
    for token in required:
        assert token in TOKENS

    assert "--ux-compact-" not in ACTIVE_CSS


def test_every_design_token_reference_has_a_declaration() -> None:
    used = set(re.findall(r"var\((--ux-[a-z0-9-]+)", DESIGN_CSS))
    declared = set(re.findall(r"(--ux-[a-z0-9-]+)\s*:", DESIGN_CSS))

    assert used <= declared, sorted(used - declared)


def test_active_routes_do_not_restore_retired_fixed_width_or_scale_workarounds() -> None:
    forbidden = (
        "max-width: 1920px",
        "max-width: 120rem",
        "max-height: 878px",
        "height: 878px",
        "zoom:",
        "transform: scale(",
        "modeling-data-workspace-bounded",
        "modeling-process-workspace-bounded",
        "modeling-fit-workspace-bounded",
    )
    for value in forbidden:
        assert value not in ACTIVE_CSS

    assert "@media (min-width: 2560px)" not in ACTIVE_CSS
    assert "@media (min-width: 3840px)" not in ACTIVE_CSS


def test_shared_typescript_metrics_replace_component_local_geometry() -> None:
    for export_name in (
        "DESKTOP_VIEWPORT_BREAKPOINTS",
        "MATERIALS_PANE_METRICS",
        "MODELING_PANE_METRICS",
        "MATERIALS_TREE_METRICS",
        "ENGINEERING_PLOT_MARGIN",
        "COLUMN_RESIZE_KEYBOARD_STEP",
        "SCROLL_RAIL_METRICS",
    ):
        assert f"export const {export_name}" in METRICS

    consumers = {
        "design/resizable-split-pane.tsx": "MATERIALS_PANE_METRICS",
        "design/modeling-workspace-layout.tsx": "MODELING_PANE_METRICS",
        "materials-browse-tree.tsx": "MATERIALS_TREE_METRICS",
        "materials-scroll-rail.tsx": "SCROLL_RAIL_METRICS",
        "engineering-curve-plot.tsx": "ENGINEERING_PLOT_MARGIN",
        "design/engineering-column-resize-handle.tsx": "COLUMN_RESIZE_KEYBOARD_STEP",
    }
    source_root = ROOT / "apps/web/src"
    for relative, metric in consumers.items():
        assert metric in (source_root / relative).read_text(encoding="utf-8")


def test_administration_structure_has_one_active_owner() -> None:
    selectors = (
        ".administration-workspace {",
        ".administration-navigation {",
        ".administration-content {",
        ".administration-task-grid {",
        ".administration-principle {",
    )
    for selector in selectors:
        assert selector in LAYOUT
        assert selector not in LEGACY

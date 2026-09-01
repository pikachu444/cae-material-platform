from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).parents[2]
TOKENS = (ROOT / "apps/web/src/design/tokens.css").read_text(encoding="utf-8")
LAYOUT = (ROOT / "apps/web/src/design/layout.css").read_text(encoding="utf-8")
PRIMITIVES = (ROOT / "apps/web/src/design/primitives.css").read_text(encoding="utf-8")
SHELL = (ROOT / "apps/web/src/design/shell.css").read_text(encoding="utf-8")
LEGACY = (ROOT / "apps/web/src/styles.css").read_text(encoding="utf-8")
MODELING_CORE = (
    ROOT / "apps/web/src/features/modeling/ui/modeling-core-workbench.css"
).read_text(encoding="utf-8")
MODELING_PLOT = (
    ROOT / "apps/web/src/features/modeling/ui/modeling-engineering-curve-plot.css"
).read_text(encoding="utf-8")
MODELING_PROCESS = (
    ROOT
    / "apps/web/src/features/modeling/ui/stages/process/modeling-process-stage.css"
).read_text(encoding="utf-8")
ADMINISTRATION = (
    ROOT / "apps/web/src/features/administration/ui/administration.css"
).read_text(encoding="utf-8")
METRICS = (ROOT / "apps/web/src/design/metrics.ts").read_text(encoding="utf-8")
ACTIVE_CSS = "\n".join((TOKENS, LAYOUT, PRIMITIVES, SHELL, LEGACY))
DESIGN_CSS = "\n".join(
    path.read_text(encoding="utf-8")
    for path in sorted((ROOT / "apps/web/src/design").glob("*.css"))
)
RETIRED_ADMINISTRATION_SELECTOR_GROUPS = (
    ".connection-dot.online",
    ".material-context-tabs button.active",
    ".material-list.compact",
    ".connection-panel > .muted",
    ".material-database-toolbar .eyebrow",
    ".database-projection-switch button.active",
    ".database-tree-node.selected",
    ".database-tree-node.record",
    ".record-view-tabs button.active",
    ".material-workflow-node.current",
    ".database-context-tabs button.active",
    ".database-revision-list button.active",
    ".record-heading-actions .text-button",
    ".database-facet-group button.active",
)

RETIRED_MODELING_SELECTOR_GROUPS = (
    ".stage-data > .section-heading",
    ".curve-tree-group > details > article.active",
    ".processing-hero .eyebrow",
    ".stage-chip-rail button.active",
    ".stage-item.active",
    ".stage-item.active > span",
)

MOVED_MODELING_SELECTOR_GROUPS = (
    ".configured-step-list > button.active",
    ".processing-curve.interactive.interaction-pan:not(.is-panning)",
    ".processing-curve.interactive.is-panning",
)


def _contains_exact_css_rule(css: str, selector: str) -> bool:
    css_without_comments = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)
    return re.search(
        rf"(?:^|[}},])\s*{re.escape(selector)}\s*\{{",
        css_without_comments,
        flags=re.MULTILINE,
    ) is not None


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
        "--ux-bounded-workgroup-max-inline-size",
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
        ".administration-taskbar {",
        ".administration-content {",
        ".administration-record-workbench {",
        ".schema-editor-grid {",
    )
    for selector in selectors:
        assert selector in ADMINISTRATION
        assert selector not in LAYOUT
        assert selector not in LEGACY


def test_retired_administration_css_groups_have_no_production_consumers() -> None:
    source_css = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((ROOT / "apps/web/src").rglob("*.css"))
    )
    for selector in RETIRED_ADMINISTRATION_SELECTOR_GROUPS:
        assert not _contains_exact_css_rule(source_css, selector), selector

    dist_root = ROOT / "apps/web/dist"
    if dist_root.exists():
        dist_css = "\n".join(
            path.read_text(encoding="utf-8")
            for path in sorted(dist_root.rglob("*.css"))
        )
        for selector in RETIRED_ADMINISTRATION_SELECTOR_GROUPS:
            assert not _contains_exact_css_rule(dist_css, selector), selector


def test_administration_elastic_workgroups_keep_forms_on_shared_semantic_boundaries() -> None:
    assert ".schema-editor-header," in ADMINISTRATION
    assert ".schema-editor-grid {" in ADMINISTRATION
    assert "minmax(0, var(--ux-navigator-default-inline-size))" in ADMINISTRATION
    assert "minmax(18rem, 1fr)" in ADMINISTRATION
    assert "var(--ux-readable-form-max-inline-size)" in ADMINISTRATION

    assert ".administration-record-workbench" in ADMINISTRATION
    assert "max-width: var(--ux-workspace-max-inline-size)" in ADMINISTRATION


def test_retired_modeling_css_groups_have_no_production_or_built_consumers() -> None:
    source_css = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((ROOT / "apps/web/src").rglob("*.css"))
    )
    for selector in RETIRED_MODELING_SELECTOR_GROUPS:
        assert not _contains_exact_css_rule(source_css, selector), selector

    dist_root = ROOT / "apps/web/dist"
    if dist_root.exists():
        dist_css = "\n".join(
            path.read_text(encoding="utf-8")
            for path in sorted(dist_root.rglob("*.css"))
        )
        for selector in RETIRED_MODELING_SELECTOR_GROUPS:
            assert not _contains_exact_css_rule(dist_css, selector), selector


def test_modeling_css_moves_keep_one_exact_feature_owner_and_do_not_claim_fragments() -> None:
    for selector, owner in (
        (".configured-step-list > button.active", MODELING_CORE),
        (
            ".processing-curve.interactive.interaction-pan:not(.is-panning)",
            MODELING_PLOT,
        ),
        (".processing-curve.interactive.is-panning", MODELING_PLOT),
    ):
        assert _contains_exact_css_rule(owner, selector), selector

    assert not _contains_exact_css_rule(LAYOUT, ".configured-step-list > button.active")
    assert not _contains_exact_css_rule(LEGACY, ".configured-step-list > button.active")
    assert not _contains_exact_css_rule(
        LEGACY, ".processing-curve.interactive.interaction-pan:not(.is-panning)"
    )
    assert not _contains_exact_css_rule(
        MODELING_PROCESS, ".processing-curve.interactive.is-panning"
    )

    # The shared plot base/focus rules remain valid contextual peers; only the
    # exact moved declarations are required to have a single producer.
    assert ".processing-curve.interactive {" in MODELING_PROCESS
    assert ".processing-curve.interactive:focus-visible {" in MODELING_PROCESS

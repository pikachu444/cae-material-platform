import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ADMIN_COMPONENTS = (
    ROOT
    / "apps/web/src/features/administration/database-design/database-design-workspace.tsx",
    ROOT
    / "apps/web/src/features/administration/records/configurable-catalog-records.tsx",
    ROOT
    / "apps/web/src/features/administration/access/product-access-center.tsx",
    ROOT
    / "apps/web/src/features/administration/definition-bundles/schema-definition-bundle-admin.tsx",
)
ADMIN_ROUTE = ROOT / "apps/web/src/features/administration/routes/administration-workspace.tsx"
LEGACY_BUTTON_CLASS = re.compile(
    r'className="(?:button(?:\s[^\"]*)?|text-button)"'
)
LEGACY_TEAL = ("#147a76", "#0f6966")


def test_administration_commands_do_not_use_the_legacy_button_system() -> None:
    for path in ADMIN_COMPONENTS:
        source = path.read_text(encoding="utf-8")
        assert LEGACY_BUTTON_CLASS.search(source) is None, path
        assert all(color not in source.lower() for color in LEGACY_TEAL), path

    administration_route = ADMIN_ROUTE.read_text(encoding="utf-8")
    assert LEGACY_BUTTON_CLASS.search(administration_route) is None
    assert 'aria-label="Administration tasks"' in administration_route
    assert "Open Materials" not in administration_route


def test_shared_button_primitive_owns_administration_semantics() -> None:
    tokens = (ROOT / "apps/web/src/design/tokens.css").read_text(encoding="utf-8")
    primitives = (ROOT / "apps/web/src/design/primitives.css").read_text(
        encoding="utf-8"
    )
    assert "--ux-accent: #245ea8" in tokens
    assert "--ux-success: #176b45" in tokens
    assert "--ux-danger: #a62929" in tokens

    primary = re.search(r"\.ux-button\.primary\s*\{(?P<body>[^}]*)\}", primitives)
    danger = re.search(r"\.ux-button\.danger\s*\{(?P<body>[^}]*)\}", primitives)
    local_action = re.search(
        r"\.ux-button\.local-action\s*\{(?P<body>[^}]*)\}", primitives
    )
    base = re.search(r"\.ux-button\s*\{(?P<body>[^}]*)\}", primitives)
    assert primary is not None and "var(--ux-accent)" in primary["body"]
    assert "--ux-success" not in primary["body"]
    assert danger is not None and "var(--ux-danger" in danger["body"]
    assert local_action is not None
    assert "var(--ux-data-font-size)" in local_action["body"]
    assert "var(--ux-font-weight-label)" in local_action["body"]
    assert base is not None and "var(--ux-shadow-none)" in base["body"]
    assert '.ux-button[aria-busy="true"]' in primitives


def test_database_edit_groups_have_only_one_primary_command() -> None:
    source = ADMIN_COMPONENTS[0].read_text(encoding="utf-8")
    layout_editor = (
        ROOT
        / "apps/web/src/features/administration/database-design/datasheet-layout-editor.tsx"
    ).read_text(encoding="utf-8")
    database_css = (
        ROOT
        / "apps/web/src/features/administration/database-design/database-design.css"
    ).read_text(encoding="utf-8")
    revision_footers = [
        footer
        for footer in re.findall(r"<footer>(.*?)</footer>", source, re.DOTALL)
        if "Save new " in footer and " revision</button>" in footer
    ]
    assert len(revision_footers) == 6
    for footer in revision_footers:
        assert footer.count('className="ux-button primary"') == 1
        assert 'className="ux-button" type="button" disabled={saving}' in footer

    assert layout_editor.count('className="ux-button primary"') == 1
    assert '>\n          Save\n        </button>' in layout_editor
    assert '<summary className="ux-button local-action" aria-label={`More actions for ${title}`}>More</summary>' in layout_editor
    assert layout_editor.count('className="ux-button local-action"') == 2
    assert 'className="ux-button local-action" type="button"' in source
    assert 'className="layout-drag-handle"' in layout_editor
    assert 'className="layout-drag-glyph"' in layout_editor
    assert 'aria-keyshortcuts="Alt+ArrowUp Alt+ArrowDown"' in layout_editor
    assert "layout-field-order" not in layout_editor
    assert "autoScrollStep" in layout_editor
    assert "Math.ceil(12 * proximity)" in layout_editor
    assert "grid-template-rows: auto auto minmax(0, 1fr) auto" in database_css
    assert "overflow-y: scroll" in database_css
    assert "position: sticky" not in database_css.split(
        ".catalog-schema-editor .datasheet-layout-editor > footer", 1
    )[1].split("}", 1)[0]
    assert "Delete layout" in layout_editor
    assert "Validate layout" not in layout_editor
    assert "Reload server state" not in source

    access = ADMIN_COMPONENTS[2].read_text(encoding="utf-8")
    assert 'className="ux-button danger"' in access
    assert (
        'className="ux-button primary" type="submit" disabled={saving} '
        'aria-busy={saving}'
    ) in access

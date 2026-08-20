import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ADMIN_COMPONENTS = (
    ROOT
    / "apps/web/src/features/administration/database-design/database-design-workspace.tsx",
    ROOT / "apps/web/src/configurable-catalog-records.tsx",
    ROOT / "apps/web/src/product-access-center.tsx",
)
LEGACY_BUTTON_CLASS = re.compile(
    r'className="(?:button(?:\s[^\"]*)?|text-button)"'
)
LEGACY_TEAL = ("#147a76", "#0f6966")


def test_administration_commands_do_not_use_the_legacy_button_system() -> None:
    for path in ADMIN_COMPONENTS:
        source = path.read_text(encoding="utf-8")
        assert LEGACY_BUTTON_CLASS.search(source) is None, path
        assert all(color not in source.lower() for color in LEGACY_TEAL), path

    app = (ROOT / "apps/web/src/app.tsx").read_text(encoding="utf-8")
    administration = app.split("function AdministrationWorkspace", 1)[1].split(
        "function ErrorNotice", 1
    )[0]
    assert LEGACY_BUTTON_CLASS.search(administration) is None
    assert 'className="ux-button tertiary"' in administration


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
    base = re.search(r"\.ux-button\s*\{(?P<body>[^}]*)\}", primitives)
    assert primary is not None and "var(--ux-accent)" in primary["body"]
    assert "--ux-success" not in primary["body"]
    assert danger is not None and "var(--ux-danger" in danger["body"]
    assert base is not None and "var(--ux-shadow-none)" in base["body"]
    assert '.ux-button[aria-busy="true"]' in primitives
    assert all(color not in primitives.lower() for color in LEGACY_TEAL)


def test_database_edit_groups_have_only_one_primary_command() -> None:
    source = ADMIN_COMPONENTS[0].read_text(encoding="utf-8")
    publish_footers = [
        footer
        for footer in re.findall(r"<footer>(.*?)</footer>", source, re.DOTALL)
        if "Publish — Not configured</button>" in footer
    ]
    assert len(publish_footers) == 7
    for footer in publish_footers:
        assert footer.count('className="ux-button primary"') == 1
        assert 'className="ux-button" type="submit" disabled={saving}>Save draft' in footer
        assert 'className="ux-button" type="button" disabled={saving}' in footer

    access = ADMIN_COMPONENTS[2].read_text(encoding="utf-8")
    assert 'className="ux-button danger"' in access
    assert (
        'className="ux-button primary" type="submit" disabled={saving} '
        'aria-busy={saving}'
    ) in access

from __future__ import annotations

from pathlib import Path

import pytest
from cmp.tools.documentation_impact import (
    DocumentationImpactError,
    DocumentationImpactException,
    _parse_name_status,
    _parse_name_status_entries,
    _validate_exception,
    evaluate_documentation_impact,
)

BASE_SHA = "a" * 40
PRIMITIVES_PATH = "apps/web/src/design/primitives.css"
BASE_PRIMITIVES = ".ux-button { font-weight: 650; }\n"
CURRENT_PRIMITIVES = """\
.ux-button { font-weight: 650; }
.ux-semantic-text { color: var(--ux-text); }
"""


def foundation_exception(
    *,
    visual_files: tuple[str, ...] = (
        PRIMITIVES_PATH,
        "apps/web/src/design/semantic-ui.tsx",
    ),
    source_sha: str = BASE_SHA,
    preserved_computed_value_files: tuple[str, ...] = (
        PRIMITIVES_PATH,
    ),
) -> DocumentationImpactException:
    return DocumentationImpactException(
        path="docs/14-testing/documentation-impact-exceptions/issue-257.yaml",
        issue="#257",
        source_sha=source_sha,
        classification="non-user-visible-foundation",
        reason="The shared foundation has no current product route consumer.",
        visual_files=visual_files,
        unconsumed_modules=("apps/web/src/design/semantic-ui.tsx",),
        preserved_computed_value_files=preserved_computed_value_files,
    )


def write_foundation(
    tmp_path: Path,
    *,
    primitives: str = CURRENT_PRIMITIVES,
) -> dict[str, str]:
    module = tmp_path / "apps/web/src/design/semantic-ui.tsx"
    module.parent.mkdir(parents=True)
    module.write_text("export const SemanticText = () => null;\n", encoding="utf-8")
    (tmp_path / PRIMITIVES_PATH).write_text(primitives, encoding="utf-8")
    return {PRIMITIVES_PATH: BASE_PRIMITIVES}


def test_visual_source_alone_is_rejected() -> None:
    with pytest.raises(DocumentationImpactError, match="current docs/user-guide"):
        evaluate_documentation_impact({"apps/web/src/material-library.tsx"})


def test_visual_source_and_guide_without_evidence_are_rejected() -> None:
    with pytest.raises(DocumentationImpactError, match="screenshot-manifest"):
        evaluate_documentation_impact(
            {
                "apps/web/src/material-library.tsx",
                "docs/user-guide/18-search-first-materials.md",
            }
        )


def test_visual_source_with_guide_manifest_and_png_is_accepted() -> None:
    report = evaluate_documentation_impact(
        {
            "apps/web/src/material-library.tsx",
            "docs/user-guide/18-search-first-materials.md",
            "docs/user-guide/screenshot-manifest.yaml",
            "docs/user-guide/images/current/materials-search-next.png",
        }
    )
    assert report.visual_files == ("apps/web/src/material-library.tsx",)


def test_app_route_change_without_navigation_contract_is_rejected() -> None:
    with pytest.raises(DocumentationImpactError, match="navigation-contract"):
        evaluate_documentation_impact(
            {
                "apps/web/src/app.tsx",
                "docs/user-guide/18-search-first-materials.md",
                "docs/user-guide/screenshot-manifest.yaml",
                "docs/user-guide/images/current/navigation-next.png",
            }
        )


def test_test_only_change_is_accepted() -> None:
    report = evaluate_documentation_impact(
        {
            "apps/web/src/material-library.test.tsx",
            "tests/contracts/test_documentation_impact.py",
        }
    )
    assert report.visual_files == ()


def test_storybook_only_change_is_accepted_without_product_documentation() -> None:
    report = evaluate_documentation_impact(
        {
            "apps/web/.storybook/preview.css",
            "apps/web/src/design/semantic-ui.stories.tsx",
        }
    )

    assert report.visual_files == ()


def test_exact_non_user_visible_foundation_exception_is_accepted(tmp_path: Path) -> None:
    base_files = write_foundation(tmp_path)
    (tmp_path / "apps/web/src/main.tsx").write_text(
        'import "./styles.css";\n',
        encoding="utf-8",
    )
    exception = foundation_exception()
    visual_files = set(exception.visual_files)

    validated = _validate_exception(
        tmp_path,
        exception,
        visual_files,
        BASE_SHA,
        base_files=base_files,
    )
    report = evaluate_documentation_impact(visual_files, exception=validated)

    assert report.exempted_visual_files == exception.visual_files
    assert report.exception_issue == "#257"
    assert validated.derived_selectors == ("ux-semantic-text",)


def test_foundation_exception_cannot_bypass_repository_validation() -> None:
    exception = foundation_exception()

    with pytest.raises(DocumentationImpactError, match="must pass repository validation"):
        evaluate_documentation_impact(  # type: ignore[arg-type]
            set(exception.visual_files),
            exception=exception,
        )


def test_foundation_exception_rejects_route_or_feature_visual_source(
    tmp_path: Path,
) -> None:
    exception = foundation_exception(
        visual_files=("apps/web/src/material-library.tsx",),
    )

    with pytest.raises(DocumentationImpactError, match="only files under"):
        _validate_exception(
            tmp_path,
            exception,
            {"apps/web/src/material-library.tsx"},
            BASE_SHA,
        )


def test_foundation_exception_rejects_shared_layout_as_preserved_value(tmp_path: Path) -> None:
    exception = foundation_exception(
        visual_files=(
            "apps/web/src/design/layout.css",
            "apps/web/src/design/semantic-ui.tsx",
        ),
        preserved_computed_value_files=("apps/web/src/design/layout.css",),
    )

    with pytest.raises(DocumentationImpactError, match="only shared tokens"):
        _validate_exception(
            tmp_path,
            exception,
            set(exception.visual_files),
            BASE_SHA,
        )


def test_foundation_exception_requires_exact_sha_and_visual_paths(tmp_path: Path) -> None:
    exception = foundation_exception(source_sha="b" * 40)

    with pytest.raises(DocumentationImpactError, match="does not match"):
        _validate_exception(tmp_path, exception, set(exception.visual_files), BASE_SHA)

    exception = foundation_exception()
    with pytest.raises(DocumentationImpactError, match="must exactly match"):
        _validate_exception(
            tmp_path,
            exception,
            set(exception.visual_files) | {"apps/web/src/design/typography.css"},
            BASE_SHA,
        )


def test_foundation_exception_rejects_a_product_module_consumer(tmp_path: Path) -> None:
    base_files = write_foundation(tmp_path)
    (tmp_path / "apps/web/src/app.tsx").write_text(
        'import { SemanticText } from "./design/semantic-ui";\n',
        encoding="utf-8",
    )
    exception = foundation_exception()

    with pytest.raises(DocumentationImpactError, match="referenced by product source"):
        _validate_exception(
            tmp_path,
            exception,
            set(exception.visual_files),
            BASE_SHA,
            base_files=base_files,
        )


def test_foundation_exception_rejects_product_selector_use(tmp_path: Path) -> None:
    base_files = write_foundation(tmp_path)
    (tmp_path / "apps/web/src/materials.tsx").write_text(
        'export const Materials = () => <span className="ux-semantic-text" />;\n',
        encoding="utf-8",
    )
    exception = foundation_exception()

    with pytest.raises(DocumentationImpactError, match="used by product source"):
        _validate_exception(
            tmp_path,
            exception,
            set(exception.visual_files),
            BASE_SHA,
            base_files=base_files,
        )


def test_foundation_exception_scans_css_consumers_for_derived_selectors(
    tmp_path: Path,
) -> None:
    base_files = write_foundation(tmp_path)
    (tmp_path / "apps/web/src/materials.css").write_text(
        ".materials .ux-semantic-text { color: red; }\n",
        encoding="utf-8",
    )
    exception = foundation_exception()

    with pytest.raises(DocumentationImpactError, match="used by product source"):
        _validate_exception(
            tmp_path,
            exception,
            set(exception.visual_files),
            BASE_SHA,
            base_files=base_files,
        )


def test_foundation_exception_rejects_unproven_existing_appearance_change(
    tmp_path: Path,
) -> None:
    base_files = write_foundation(
        tmp_path,
        primitives="""\
.ux-button { font-weight: 700; }
.ux-semantic-text { color: var(--ux-text); }
""",
    )
    exception = foundation_exception()

    with pytest.raises(DocumentationImpactError, match="cannot prove unchanged appearance"):
        _validate_exception(
            tmp_path,
            exception,
            set(exception.visual_files),
            BASE_SHA,
            base_files=base_files,
        )


def test_foundation_exception_rejects_new_rule_for_an_existing_selector(
    tmp_path: Path,
) -> None:
    base_files = write_foundation(
        tmp_path,
        primitives="""\
.ux-button { font-weight: 650; }
.ux-button:hover { color: red; }
""",
    )
    exception = foundation_exception()

    with pytest.raises(DocumentationImpactError, match="isolated class"):
        _validate_exception(
            tmp_path,
            exception,
            set(exception.visual_files),
            BASE_SHA,
            base_files=base_files,
        )


def test_foundation_exception_rejects_negated_novel_class_bypass(
    tmp_path: Path,
) -> None:
    base_files = write_foundation(
        tmp_path,
        primitives="""\
.ux-button { font-weight: 650; }
.ux-button:not(.ux-foundation-new) { color: red; }
""",
    )
    exception = foundation_exception()

    with pytest.raises(DocumentationImpactError, match="positive isolated class"):
        _validate_exception(
            tmp_path,
            exception,
            set(exception.visual_files),
            BASE_SHA,
            base_files=base_files,
        )


def test_openapi_workflow_change_requires_current_guide() -> None:
    with pytest.raises(DocumentationImpactError, match="OpenAPI workflow"):
        evaluate_documentation_impact({"contracts/http/openapi.yaml"})

    report = evaluate_documentation_impact(
        {
            "contracts/http/openapi.yaml",
            "docs/user-guide/18-search-first-materials.md",
        }
    )
    assert report.changed_files


def test_name_status_collector_keeps_deletion_rename_source_and_type_change() -> None:
    paths = _parse_name_status(
        b"D\0apps/web/src/deleted.tsx\0"
        b"R100\0apps/web/src/renamed.css\0archive/renamed.txt\0"
        b"T\0apps/web/src/type-changed.css\0"
    )

    assert paths == {
        "apps/web/src/deleted.tsx",
        "apps/web/src/renamed.css",
        "archive/renamed.txt",
        "apps/web/src/type-changed.css",
    }
    with pytest.raises(DocumentationImpactError, match="visual sources"):
        evaluate_documentation_impact(paths)


def test_deleted_visual_evidence_cannot_satisfy_current_documentation_gate() -> None:
    entries = _parse_name_status_entries(
        b"M\0apps/web/src/app.tsx\0"
        b"M\0docs/user-guide/navigation-contract.yaml\0"
        b"M\0docs/user-guide/screenshot-manifest.yaml\0"
        b"D\0docs/user-guide/deleted.md\0"
        b"D\0docs/user-guide/images/current/deleted.png\0"
    )

    with pytest.raises(DocumentationImpactError, match="current docs/user-guide"):
        evaluate_documentation_impact(entries)
    with pytest.raises(DocumentationImpactError, match="current user-guide PNG"):
        evaluate_documentation_impact(entries)

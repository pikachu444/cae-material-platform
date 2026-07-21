from __future__ import annotations

import pytest
from cmp.tools.documentation_impact import (
    DocumentationImpactError,
    evaluate_documentation_impact,
)


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
            "docs/15-demo/images/ux-redesign-v2/materials-search-next.png",
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
                "docs/15-demo/images/ux-redesign-v2/navigation-next.png",
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

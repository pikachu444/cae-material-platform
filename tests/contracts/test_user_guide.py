from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from cmp.tools.user_guide import (
    UserGuideContractError,
    _documentation_classes,
    _verify_document_links,
    _verify_image_inventory,
    verify_user_guide,
)

_PNG = b"\x89PNG\r\n\x1a\ncontract-test"


def test_user_guide_navigation_links_and_screenshot_evidence_are_current() -> None:
    root = Path(__file__).parents[2]

    report = verify_user_guide(root)

    assert report.document_count >= 10
    assert report.capture_count == 26
    assert report.archived_capture_count >= 100
    assert report.historical_capture_script_count == 12
    assert report.navigation_count == 3
    assert report.classified_markdown_count >= 195
    assert report.current_document_count >= 40
    assert report.local_link_count >= 300
    assert report.image_count >= 200
    assert report.orphan_image_count == 0


def test_incoming_integration_package_is_reference_not_authoritative() -> None:
    root = Path(__file__).parents[2]

    classes = _documentation_classes(root)

    assert classes["docs/_incoming/2026-07-24-organic-ux-update/04_WORKFLOW_STATE_AND_INVALIDATION_CONTRACT.md"] == "reference"
    assert classes["docs/01-product/desktop-engineering-ui-program-brief.md"] == "authoritative"
    assert classes["docs/user-guide/02-steel-elastoplastic.md"] == "current"
    assert classes["docs/17-evidence/reports/dui-04-modeling-workspace.md"] == "historical"


def test_current_manifest_does_not_claim_pending_dui_acceptance() -> None:
    root = Path(__file__).parents[2]
    manifest = yaml.safe_load(
        (root / "docs/user-guide/screenshot-manifest.yaml").read_text(encoding="utf-8")
    )
    captures = {capture["id"]: capture for capture in manifest["captures"]}
    provenance_ids = [
        capture_id
        for provenance in manifest["capture_provenance"]
        for capture_id in provenance["ids"]
    ]

    assert manifest["source_commit"] == "971d5d9"
    assert len(provenance_ids) == len(set(provenance_ids))
    assert set(provenance_ids) == set(captures)
    assert {
        provenance["source_commit"]
        for provenance in manifest["capture_provenance"]
    } == {"971d5d9"}
    assert "exact implementation commit 971d5d9" in manifest["capture_provenance"][0]["command"]

    activity = captures["activity-1440"]
    assert activity["workflow"] == "recent-browser-local-solver-card-delivery"
    assert "DUI-08 pending" in activity["fixture"]
    for capture_id in (
        "modeling-export-1366",
        "modeling-export-1440",
        "modeling-export-1920",
    ):
        capture = captures[capture_id]
        assert capture["workflow"] == "exact-neutral-mapping-preflight-and-native-card-delivery"
        assert "DUI-06 acceptance" in capture["fixture"]


def test_orphan_detection_uses_resolved_paths_not_filenames_or_audit_text(
    tmp_path: Path,
) -> None:
    current = tmp_path / "docs/user-guide/images/current/shared.png"
    historical = tmp_path / "docs/17-evidence/images/shared.png"
    current.parent.mkdir(parents=True)
    historical.parent.mkdir(parents=True)
    current.write_bytes(_PNG + b"-current")
    historical.write_bytes(_PNG + b"-historical")
    audit = tmp_path / "docs/audit.md"
    audit.write_text(
        "![owned](user-guide/images/current/shared.png)\n\n"
        "Delete candidate: `docs/17-evidence/images/shared.png`\n",
        encoding="utf-8",
    )

    _, referenced, _ = _verify_document_links(
        tmp_path, {"docs/audit.md": "historical"}
    )

    assert referenced == {"docs/user-guide/images/current/shared.png"}
    with pytest.raises(
        UserGuideContractError,
        match=r"docs/17-evidence/images/shared\.png",
    ):
        _verify_image_inventory(tmp_path, referenced, set())


def test_duplicate_group_with_multiple_historical_files_is_rejected(
    tmp_path: Path,
) -> None:
    relative_paths = (
        "docs/user-guide/images/current/current.png",
        "docs/17-evidence/images/first.png",
        "docs/17-evidence/images/nested/second.png",
    )
    for relative in relative_paths:
        image = tmp_path / relative
        image.parent.mkdir(parents=True, exist_ok=True)
        image.write_bytes(_PNG + b"-same")
    allowed_pair = frozenset(relative_paths[:2])

    with pytest.raises(UserGuideContractError, match="explicit current/historical pair"):
        _verify_image_inventory(tmp_path, set(relative_paths), {allowed_pair})


def test_exact_explicit_current_historical_duplicate_pair_is_allowed(
    tmp_path: Path,
) -> None:
    relative_paths = (
        "docs/user-guide/images/current/current.png",
        "docs/17-evidence/images/historical.png",
    )
    for relative in relative_paths:
        image = tmp_path / relative
        image.parent.mkdir(parents=True, exist_ok=True)
        image.write_bytes(_PNG + b"-same")

    result = _verify_image_inventory(
        tmp_path,
        set(relative_paths),
        {frozenset(relative_paths)},
    )

    assert result == (2, 0, 1)

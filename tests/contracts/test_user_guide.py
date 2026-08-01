from __future__ import annotations

import json
from pathlib import Path

import cmp.tools.user_guide as user_guide
import pytest
import yaml
from cmp.tools.user_guide import (
    UserGuideContractError,
    _documentation_classes,
    _duplicate_allowances,
    _verify_document_links,
    _verify_image_inventory,
    verify_user_guide,
)

_PNG = b"\x89PNG\r\n\x1a\ncontract-test"


def test_structured_image_references_must_be_exact_existing_repository_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest_relative = "docs/17-evidence/images/issue-167-service-reference/manifest.json"
    image_relative = "docs/17-evidence/images/issue-167-service-reference/evidence.png"
    image = tmp_path / image_relative
    image.parent.mkdir(parents=True)
    image.write_bytes(_PNG)
    manifest = tmp_path / manifest_relative
    manifest.write_text(json.dumps({"image": image_relative}), encoding="utf-8")
    monkeypatch.setattr(user_guide, "_STRUCTURED_IMAGE_MANIFESTS", (manifest_relative,))
    monkeypatch.setattr(user_guide, "_STRUCTURED_IMAGE_MANIFEST_GLOBS", ())
    monkeypatch.setattr(user_guide, "_STRUCTURED_IMAGE_YAML_MANIFESTS", ())
    monkeypatch.setattr(user_guide, "_IMAGE_PATH_MANIFESTS", ())

    assert user_guide._structured_manifest_images(tmp_path) == {image_relative}


@pytest.mark.parametrize(
    ("image_ref", "message"),
    [
        ("docs/17-evidence/images/issue-167-service-reference/missing.png", "missing"),
        ("../outside.png", "escapes"),
        (
            "docs/17-evidence/images/issue-167-service-reference/one.png "
            "docs/17-evidence/images/issue-167-service-reference/two.png",
            "whitespace",
        ),
    ],
)
def test_structured_image_references_reject_invalid_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    image_ref: str,
    message: str,
) -> None:
    manifest_relative = "docs/17-evidence/images/issue-167-service-reference/manifest.json"
    manifest = tmp_path / manifest_relative
    manifest.parent.mkdir(parents=True)
    manifest.write_text(json.dumps({"image": image_ref}), encoding="utf-8")
    monkeypatch.setattr(user_guide, "_STRUCTURED_IMAGE_MANIFESTS", (manifest_relative,))
    monkeypatch.setattr(user_guide, "_STRUCTURED_IMAGE_MANIFEST_GLOBS", ())
    monkeypatch.setattr(user_guide, "_STRUCTURED_IMAGE_YAML_MANIFESTS", ())
    monkeypatch.setattr(user_guide, "_IMAGE_PATH_MANIFESTS", ())

    with pytest.raises(UserGuideContractError, match=message):
        user_guide._structured_manifest_images(tmp_path)


def test_user_guide_navigation_links_and_screenshot_evidence_are_current() -> None:
    root = Path(__file__).parents[2]

    report = verify_user_guide(root)

    assert report.document_count >= 10
    assert report.capture_count == 32
    assert report.navigation_count == 3
    assert report.classified_markdown_count >= 100
    assert report.current_document_count >= 40
    assert report.local_link_count >= 150
    assert report.image_count >= 120
    assert report.orphan_image_count == 0
    assert report.duplicate_image_group_count == 0


def test_incoming_integration_package_is_reference_not_authoritative() -> None:
    root = Path(__file__).parents[2]

    classes = _documentation_classes(root)

    assert (
        classes[
            "docs/_incoming/2026-07-24-organic-ux-update/"
            "04_WORKFLOW_STATE_AND_INVALIDATION_CONTRACT.md"
        ]
        == "reference"
    )
    assert classes["docs/01-product/desktop-engineering-ui-program-brief.md"] == "authoritative"
    assert classes["docs/user-guide/02-steel-elastoplastic.md"] == "current"


def test_permanent_reference_catalog_and_image_roots_are_retained() -> None:
    root = Path(__file__).parents[2]
    catalog = json.loads(
        (root / "docs/00-research/product-reference-source-catalog.json").read_text(
            encoding="utf-8"
        )
    )
    source_ids = {source["id"] for source in catalog["sources"]}

    assert len(source_ids) >= 24
    assert {
        "granta-gateway-filters",
        "granta-read-edit",
        "smdc-review",
        "material-modeler-curve-fitting",
    } <= source_ids
    assert all(source["url"].startswith("https://") for source in catalog["sources"])
    assert len(list((root / "docs/00-research/ux-reference-gallery/images").glob("*"))) >= 5
    assert len(list((root / "docs/00-research/images/gui-reference").glob("*.png"))) >= 20


def test_current_manifest_has_one_current_provenance_record_per_capture() -> None:
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

    assert manifest["source_commit"] == "55cfa62"
    assert len(provenance_ids) == len(set(provenance_ids))
    assert set(provenance_ids) == set(captures)
    assert {provenance["source_commit"] for provenance in manifest["capture_provenance"]} == {
        "55cfa62",
        "e4dd176",
        "a0136b4",
        "65eddb0",
        "b566a04",
        "3bfc0d7",
    }
    uxc04e_commands = [
        provenance["command"]
        for provenance in manifest["capture_provenance"]
        if provenance["source_commit"] == "55cfa62"
    ]
    assert any(
        "targeted live Playwright Modeling consistency capture" in command
        for command in uxc04e_commands
    )

    activity = captures["activity-1440"]
    assert activity["workflow"] == "role-aware-review-queue-with-resume-and-outcomes"
    assert "real pending exact-revision Material and Solver Card requests" in activity["fixture"]
    for capture_id in ("administration-access-1366", "administration-access-1440"):
        capture = captures[capture_id]
        assert capture["workflow"] == "user-reviewer-administrator-task-preset-assignment"
        assert "feature checkbox editing is absent" in capture["fixture"]
    for capture_id in (
        "modeling-export-1366",
        "modeling-export-1440",
        "modeling-export-1920",
    ):
        capture = captures[capture_id]
        assert (
            capture["workflow"]
            == "uxc-06c2-exact-target-preflight-and-atomic-delivery"
        )
        assert "one immutable card/receipt" in capture["fixture"]


def test_current_images_are_product_routes_and_storybook_captures_are_untracked() -> None:
    root = Path(__file__).parents[2]
    manifest = yaml.safe_load(
        (root / "docs/user-guide/screenshot-manifest.yaml").read_text(encoding="utf-8")
    )
    current_images = root / "docs/user-guide/images/current"
    assert len(manifest["captures"]) == 32
    assert all(not capture["route"].startswith("/iframe.html") for capture in manifest["captures"])
    assert not list(current_images.glob("storybook-*.png"))
    assert len(list(current_images.glob("*.png"))) == 32
    assert not list((root / "docs/17-evidence/images").glob("**/storybook-*.png"))


def test_orphan_detection_uses_resolved_paths_not_filenames_or_audit_text(
    tmp_path: Path,
) -> None:
    current = tmp_path / "docs/user-guide/images/current/shared.png"
    reference = tmp_path / "docs/17-evidence/images/issue-167-service-reference/shared.png"
    current.parent.mkdir(parents=True)
    reference.parent.mkdir(parents=True)
    current.write_bytes(_PNG + b"-current")
    reference.write_bytes(_PNG + b"-reference")
    audit = tmp_path / "docs/audit.md"
    audit.write_text(
        "![owned](user-guide/images/current/shared.png)\n\n"
        "Delete candidate: `docs/17-evidence/images/issue-167-service-reference/shared.png`\n",
        encoding="utf-8",
    )

    _, referenced, _ = _verify_document_links(
        tmp_path, {"docs/audit.md": "reference"}
    )

    assert referenced == {"docs/user-guide/images/current/shared.png"}
    with pytest.raises(
        UserGuideContractError,
        match=r"docs/17-evidence/images/issue-167-service-reference/shared\.png",
    ):
        _verify_image_inventory(tmp_path, referenced, set())


def test_duplicate_group_mixing_current_and_reference_files_is_rejected(
    tmp_path: Path,
) -> None:
    relative_paths = (
        "docs/user-guide/images/current/current.png",
        "docs/17-evidence/images/issue-167-service-reference/first.png",
        "docs/17-evidence/images/issue-167-service-reference/nested/second.png",
    )
    for relative in relative_paths:
        image = tmp_path / relative
        image.parent.mkdir(parents=True, exist_ok=True)
        image.write_bytes(_PNG + b"-same")
    allowed_group = frozenset(relative_paths[:2])

    with pytest.raises(UserGuideContractError, match="explicit reference group"):
        _verify_image_inventory(tmp_path, set(relative_paths), {allowed_group})


def test_exact_explicit_reference_duplicate_group_is_allowed(
    tmp_path: Path,
) -> None:
    relative_paths = (
        "docs/17-evidence/images/issue-167-service-reference/first.png",
        "docs/17-evidence/images/issue-167-service-reference/reference.png",
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


@pytest.mark.parametrize(
    ("entry", "message"),
    [
        (
            {
                "images": [
                    "docs/17-evidence/images/issue-167-service-reference/first.png"
                ]
            },
            "rationale",
        ),
        (
            {
                "rationale": "reason",
                "images": ["docs/17-evidence/images/issue-167-service-reference/first.png"],
            },
            "at least two exact images",
        ),
        (
            {
                "rationale": "reason",
                "images": [
                    "docs/17-evidence/images/issue-167-service-reference/*.png",
                    "docs/17-evidence/images/issue-167-service-reference/second.png",
                ],
            },
            "exact path",
        ),
        (
            {
                "rationale": "reason",
                "images": [
                    "docs/17-evidence/images/issue-167-service-reference/first.png "
                    "docs/17-evidence/images/issue-167-service-reference/second.png",
                    "docs/17-evidence/images/issue-167-service-reference/second.png",
                ],
            },
            "exact path",
        ),
        (
            {
                "rationale": "reason",
                "images": [
                    "docs/user-guide/images/current/current.png",
                    "docs/17-evidence/images/issue-167-service-reference/second.png",
                ],
            },
            "escapes",
        ),
    ],
)
def test_duplicate_allowance_rejects_malformed_entries(
    tmp_path: Path, entry: dict[str, object], message: str
) -> None:
    for relative in (
        "docs/17-evidence/images/issue-167-service-reference/first.png",
        "docs/17-evidence/images/issue-167-service-reference/second.png",
        "docs/user-guide/images/current/current.png",
    ):
        image = tmp_path / relative
        image.parent.mkdir(parents=True, exist_ok=True)
        image.write_bytes(_PNG)

    with pytest.raises(UserGuideContractError, match=message):
        _duplicate_allowances(tmp_path, {"allowed_duplicate_groups": [entry]})


def test_duplicate_allowance_rejects_repeated_or_unused_groups(tmp_path: Path) -> None:
    relative_paths = (
        "docs/17-evidence/images/issue-167-service-reference/first.png",
        "docs/17-evidence/images/issue-167-service-reference/second.png",
    )
    for relative in relative_paths:
        image = tmp_path / relative
        image.parent.mkdir(parents=True, exist_ok=True)
        image.write_bytes(_PNG + b"-same")
    entry = {"rationale": "same intentional approved reference", "images": list(relative_paths)}

    with pytest.raises(UserGuideContractError, match="repeated"):
        _duplicate_allowances(
            tmp_path, {"allowed_duplicate_groups": [entry, entry]}
        )
    with pytest.raises(UserGuideContractError, match="no longer match equal bytes"):
        _verify_image_inventory(
            tmp_path,
            set(relative_paths),
            {
                frozenset(relative_paths),
                frozenset(
                    (
                        relative_paths[0],
                        "docs/17-evidence/images/issue-167-service-reference/missing.png",
                    )
                ),
            },
        )

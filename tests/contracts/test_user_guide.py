from __future__ import annotations

import json
import re
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


def test_historical_evidence_to_current_duplicate_allowance_can_expire(
    tmp_path: Path,
) -> None:
    evidence_relative = "docs/17-evidence/images/issue-old/screen.png"
    current_relative = "docs/user-guide/images/current/screen.png"
    evidence = tmp_path / evidence_relative
    current = tmp_path / current_relative
    evidence.parent.mkdir(parents=True)
    current.parent.mkdir(parents=True)
    evidence.write_bytes(_PNG + b"-old")
    current.write_bytes(_PNG + b"-new")

    report = _verify_image_inventory(
        tmp_path,
        {evidence_relative, current_relative},
        {frozenset({evidence_relative, current_relative})},
    )

    assert report == (2, 0, 0)


def test_stale_evidence_only_duplicate_allowance_remains_an_error(
    tmp_path: Path,
) -> None:
    first_relative = "docs/17-evidence/images/issue-old/first.png"
    second_relative = "docs/17-evidence/images/issue-old/second.png"
    first = tmp_path / first_relative
    second = tmp_path / second_relative
    first.parent.mkdir(parents=True)
    first.write_bytes(_PNG + b"-first")
    second.write_bytes(_PNG + b"-second")

    with pytest.raises(UserGuideContractError, match="no longer match"):
        _verify_image_inventory(
            tmp_path,
            {first_relative, second_relative},
            {frozenset({first_relative, second_relative})},
        )


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


def test_structured_yaml_path_references_register_visual_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest_relative = "docs/17-evidence/images/issue-161/visual-evidence.yaml"
    image_relative = "docs/17-evidence/images/issue-161/before.png"
    image = tmp_path / image_relative
    image.parent.mkdir(parents=True)
    image.write_bytes(_PNG)
    manifest = tmp_path / manifest_relative
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(
        yaml.safe_dump({"comparison": {"before": {"path": image_relative}}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(user_guide, "_STRUCTURED_IMAGE_MANIFESTS", ())
    monkeypatch.setattr(user_guide, "_STRUCTURED_IMAGE_MANIFEST_GLOBS", ())
    monkeypatch.setattr(user_guide, "_STRUCTURED_IMAGE_YAML_MANIFESTS", (manifest_relative,))
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
    assert report.capture_count == 95
    assert report.navigation_count == 3
    assert report.classified_markdown_count >= 100
    assert report.current_document_count >= 40
    assert report.local_link_count >= 150
    assert report.image_count >= 120
    assert report.orphan_image_count == 0
    assert report.duplicate_image_group_count == 266


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
    previous_provenance = manifest["previous_capture_provenance"]
    previous_provenance_ids = [
        capture_id for provenance in previous_provenance for capture_id in provenance["ids"]
    ]

    prior_source = "31f9a3f+task3b-worktree"
    correction_source = "7394070+fit-ui-correction-worktree"
    process_ids = {
        "MOD-PROCESS-CURRENT-LINEAR-1366",
        "MOD-PROCESS-CURRENT-BLOCKED-1440",
        "MOD-PROCESS-CURRENT-EXACT-READ-FAILED-1440",
        "MOD-PROCESS-CURRENT-SIBLINGS-1440",
    }

    current_source = manifest["source_commit"]
    assert manifest["scope"] == "issue-206-curve-channel-metadata-and-deviation"
    assert re.fullmatch(r"[0-9a-f]{40}", current_source)
    assert manifest["source_commit"] == current_source
    assert len(provenance_ids) == len(set(provenance_ids))
    preserved_fixture_ids = {
        "modeling-export-delivered",
        "solver-card-preview-1366",
        "solver-card-preview-1440",
        "solver-card-preview-1920",
    }
    assert set(captures) - set(provenance_ids) == preserved_fixture_ids
    assert {provenance["source_commit"] for provenance in manifest["capture_provenance"]} == {
        current_source,
        "97f850acf454a8fb6d8caeb8cf5e9ccb5d413a16",
    }
    assert len(previous_provenance_ids) == len(set(previous_provenance_ids))
    new_issue_184_captures = {
        "MOD-PROCESS-CURRENT-MANUAL-1366",
        "administration-access-role-control-1366",
        "modeling-data-invalid-scrolled-1440",
        "administration-access-1920",
        "administration-access-2560",
        "administration-access-3840",
    }
    new_issue_206_captures = {
        "material-curves-1366",
        "material-curves-1440",
        "material-curves-1920",
        "material-curves-2560",
        "material-curves-3840",
    }
    assert set(previous_provenance_ids) == (
        set(captures) - new_issue_184_captures - new_issue_206_captures
    )
    assert {
        prior_source,
        correction_source,
        "25bd0d4",
        "960d476",
        "55cfa62",
        "3bfc0d7",
        "94387e4",
        "working-tree-issue-160",
        "working-tree-issue-160-task-2",
    } == {provenance["source_commit"] for provenance in previous_provenance}
    issue_206_provenance = next(
        provenance
        for provenance in manifest["capture_provenance"]
        if provenance["source_commit"] == current_source
    )
    assert "--only-materials" in issue_206_provenance["command"]
    assert new_issue_206_captures <= set(issue_206_provenance["ids"])
    process_provenance = [
        provenance
        for provenance in previous_provenance
        if provenance["source_commit"] == prior_source
        and "--only-modeling-process" in provenance["command"]
        and "--only-modeling-process-fit" not in provenance["command"]
    ]
    assert len(process_provenance) == 1
    assert set(process_provenance[0]["ids"]) == process_ids
    assert "--only-modeling-process" in process_provenance[0]["command"]
    assert "accepted the qualitative visual checks" in process_provenance[0]["command"]
    uxc04e_commands = [
        provenance["command"]
        for provenance in previous_provenance
        if provenance["source_commit"] == "55cfa62"
    ]
    assert any(
        "targeted live Playwright Modeling Export capture" in command for command in uxc04e_commands
    )
    data_provenance = [
        provenance
        for provenance in previous_provenance
        if provenance["source_commit"] == correction_source
        and "--only-modeling-data-session" in provenance["command"]
    ]
    assert len(data_provenance) == 1
    assert set(data_provenance[0]["ids"]) == {
        "modeling-data-1366",
        "modeling-data-1440",
        "modeling-data-1920",
        "modeling-data-2560",
        "modeling-data-3840",
    }
    assert "temporary staging" in data_provenance[0]["command"]
    assert "copied into the tracked current directory" in data_provenance[0]["command"]
    process_fit_provenance = [
        provenance
        for provenance in previous_provenance
        if provenance["source_commit"] == correction_source
        and "--only-modeling-process-fit" in provenance["command"]
    ]
    assert len(process_fit_provenance) == 1
    assert {
        "MOD-PROCESS-CURRENT-1366",
        "MOD-PROCESS-CURRENT-1440",
        "MOD-PROCESS-CURRENT-1920",
        "MOD-PROCESS-CURRENT-2560",
        "MOD-PROCESS-CURRENT-3840",
        "modeling-fit-1366",
        "modeling-fit-1440",
        "modeling-fit-1920",
        "modeling-fit-2560",
        "modeling-fit-3840",
        "modeling-fit-candidate-parameters-long-1440",
        "modeling-fit-candidate-evidence-scrolled-1440",
        "modeling-fit-calculation-failed-1920",
        "modeling-fit-save-failed-1920",
        "modeling-fit-exact-source-blocked-1920",
        "modeling-fit-exact-read-failed-1920",
        "modeling-fit-restored-1920",
    } == set(process_fit_provenance[0]["ids"])
    assert "accepted the qualitative visual checks" in process_fit_provenance[0]["command"]

    activity = captures["activity-1440"]
    assert activity["workflow"] == "role-aware-review-queue-with-resume-and-outcomes"
    assert (
        "pending exact-revision DP780 Selected model and Solver card reviews" in activity["fixture"]
    )
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
        assert capture["workflow"] == "uxc-06c2-capability-backed-preview-and-atomic-delivery"
        assert "one immutable card/receipt" in capture["fixture"]


def test_mat_detail_captures_resolve_to_approved_references_and_comparison_evidence() -> None:
    root = Path(__file__).parents[2]
    manifest = yaml.safe_load(
        (root / "docs/user-guide/screenshot-manifest.yaml").read_text(encoding="utf-8")
    )
    references_manifest = yaml.safe_load(
        (root / "docs/01-product/service-reference-manifest.yaml").read_text(encoding="utf-8")
    )
    references = references_manifest["references"]
    reference_ids = {entry["id"] for entry in references}
    detail_captures = [
        capture for capture in manifest["captures"] if capture["id"].startswith("material-detail-")
    ]
    assert {capture["width"] for capture in detail_captures} == {1366, 1440, 1920, 2560, 3840}
    for capture in detail_captures:
        approved_ids = capture.get("approved_reference_ids")
        assert approved_ids
        assert set(approved_ids) <= reference_ids
        comparison = root / capture["comparison_evidence"]
        assert comparison.is_file()
        current_image = root / "docs/user-guide" / capture["image"]
        assert current_image.is_file()
        linked_images = {
            (comparison.parent / target).resolve()
            for target in re.findall(r"\]\(([^)\s]+)\)", comparison.read_text(encoding="utf-8"))
        }
        assert current_image.resolve() in linked_images
        for reference_id in approved_ids:
            reference = next(entry for entry in references if entry["id"] == reference_id)
            reference_image = root / reference["image"]
            assert reference_image.is_file()
            assert reference_image.resolve() in linked_images


def test_current_images_are_product_routes_and_storybook_captures_are_untracked() -> None:
    root = Path(__file__).parents[2]
    manifest = yaml.safe_load(
        (root / "docs/user-guide/screenshot-manifest.yaml").read_text(encoding="utf-8")
    )
    current_images = root / "docs/user-guide/images/current"
    assert len(manifest["captures"]) == 95
    assert all(not capture["route"].startswith("/iframe.html") for capture in manifest["captures"])
    assert not list(current_images.glob("storybook-*.png"))
    assert len(list(current_images.glob("*.png"))) == 95
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

    _, referenced, _ = _verify_document_links(tmp_path, {"docs/audit.md": "reference"})

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

    with pytest.raises(UserGuideContractError, match="explicit duplicate group"):
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


def test_exact_evidence_and_current_duplicate_group_is_allowed(
    tmp_path: Path,
) -> None:
    relative_paths = (
        "docs/17-evidence/images/issue-161/before.png",
        "docs/user-guide/images/current/after.png",
    )
    for relative in relative_paths:
        image = tmp_path / relative
        image.parent.mkdir(parents=True, exist_ok=True)
        image.write_bytes(_PNG + b"-same-independent-pixels")

    result = _verify_image_inventory(
        tmp_path,
        set(relative_paths),
        {frozenset(relative_paths)},
    )

    assert result == (2, 0, 1)


def test_duplicate_group_with_two_current_images_is_rejected(
    tmp_path: Path,
) -> None:
    relative_paths = (
        "docs/user-guide/images/current/first.png",
        "docs/user-guide/images/current/second.png",
    )
    for relative in relative_paths:
        image = tmp_path / relative
        image.parent.mkdir(parents=True, exist_ok=True)
        image.write_bytes(_PNG + b"-same-current-pixels")

    with pytest.raises(UserGuideContractError, match="explicit duplicate group"):
        _verify_image_inventory(
            tmp_path,
            set(relative_paths),
            {frozenset(relative_paths)},
        )


@pytest.mark.parametrize(
    ("entry", "message"),
    [
        (
            {"images": ["docs/17-evidence/images/issue-167-service-reference/first.png"]},
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
            "unsupported lifecycle mix",
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
        _duplicate_allowances(tmp_path, {"allowed_duplicate_groups": [entry, entry]})
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

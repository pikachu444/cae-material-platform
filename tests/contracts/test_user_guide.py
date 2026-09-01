from __future__ import annotations

import hashlib
import json
import re
import struct
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
    _verify_repository_guidance,
    _verify_service_reference_manifest,
    verify_user_guide,
)

_PNG = b"\x89PNG\r\n\x1a\ncontract-test"


def _png_with_dimensions(width: int, height: int, suffix: bytes) -> bytes:
    return b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + struct.pack(">II", width, height) + suffix


def _write_dual_lifecycle_service_reference_fixture(
    root: Path,
) -> tuple[Path, Path, Path, list[dict[str, object]]]:
    source = root / "docs/00-research/ux-service-reference/reference.html"
    source.parent.mkdir(parents=True)
    source.write_text("<!doctype html><title>Reference</title>", encoding="utf-8")

    static_root = root / "docs/17-evidence/images/issue-167-service-reference"
    static_root.mkdir(parents=True)
    references: list[dict[str, object]] = []
    for ordinal in range(65):
        image = static_root / f"legacy-{ordinal:02d}.png"
        image_bytes = _png_with_dimensions(32, 24, f"legacy-{ordinal}".encode())
        image.write_bytes(image_bytes)
        measurement = static_root / f"legacy-{ordinal:02d}.measurements.json"
        measurement.write_text("{}", encoding="utf-8")
        references.append(
            {
                "id": f"legacy-{ordinal:02d}-32x24",
                "screen": "legacy",
                "state": "normal",
                "viewport": {"width": 32, "height": 24, "device_scale_factor": 1},
                "sources": {"html": source.relative_to(root).as_posix()},
                "image": image.relative_to(root).as_posix(),
                "measurements": measurement.relative_to(root).as_posix(),
                "image_sha256": hashlib.sha256(image_bytes).hexdigest(),
                "date": "2026-07-31",
                "status": "approved",
                "product_owner_approval": {"status": "approved", "date": "2026-07-31"},
            }
        )

    evidence_root = root / "docs/17-evidence/images/issue-289-administration-database-workflow"
    originals = evidence_root / "after/originals"
    originals.mkdir(parents=True)
    viewports: list[dict[str, object]] = []
    evidence_manifest = evidence_root / "visual-evidence.yaml"
    for width, height in ((1920, 1080), (2560, 1440), (3840, 2160)):
        image = originals / f"administration-database-{width}x{height}.png"
        image_bytes = _png_with_dimensions(width, height, f"current-{width}x{height}".encode())
        image.write_bytes(image_bytes)
        digest = hashlib.sha256(image_bytes).hexdigest()
        viewports.append(
            {
                "viewport": f"{width}x{height}",
                "after_editor": {
                    "path": image.relative_to(evidence_root).as_posix(),
                    "width": width,
                    "height": height,
                    "sha256": digest,
                },
            }
        )
        references.append(
            {
                "id": f"administration-database-normal-{width}x{height}",
                "screen": "administration-database",
                "state": "normal",
                "lifecycle": "current-product-evidence",
                "viewport": {"width": width, "height": height, "device_scale_factor": 1},
                "evidence_manifest": evidence_manifest.relative_to(root).as_posix(),
                "evidence_key": "after_editor",
                "image": image.relative_to(root).as_posix(),
                "image_sha256": digest,
                "date": "2026-08-20",
                "status": "approved",
                "product_owner_approval": {"status": "approved", "date": "2026-08-20"},
            }
        )
    evidence_manifest.write_text(
        yaml.safe_dump({"schema_version": "cmp.visual-evidence.v1", "viewports": viewports}),
        encoding="utf-8",
    )

    guide_root = root / "docs/user-guide"
    guide_images = guide_root / "images/current"
    guide_images.mkdir(parents=True)
    guide_captures: list[dict[str, object]] = []
    guide_targets = (
        ("modeling-fit-1366", "normal", 1366, 768, "modeling-fit-1366x768.png"),
        ("modeling-fit-1440", "normal", 1440, 900, "modeling-fit-1440x900.png"),
        ("modeling-fit-1920", "normal", 1920, 1080, "modeling-fit-1920x1080.png"),
        ("modeling-fit-2560", "normal-wide", 2560, 1440, "modeling-fit-2560x1440.png"),
        ("modeling-fit-3840", "normal-wide", 3840, 2160, "modeling-fit-3840x2160.png"),
    )
    for guide_id, state, width, height, filename in guide_targets:
        image = guide_images / filename
        image_bytes = _png_with_dimensions(width, height, f"guide-{guide_id}".encode())
        image.write_bytes(image_bytes)
        guide_captures.append(
            {
                "id": guide_id,
                "route": "/modeling?stage=fit&family=metal",
                "workflow": "contract fixture Fit capture",
                "fixture": f"contract fixture Fit {state}",
                "image": f"images/current/{filename}",
                "width": width,
                "height": height,
            }
        )
        references.append(
            {
                "id": f"modeling-fit-normal-{width}x{height}",
                "screen": "modeling-fit",
                "state": state,
                "lifecycle": "current-guide",
                "viewport": {"width": width, "height": height, "device_scale_factor": 1},
                "guide_manifest": "docs/user-guide/screenshot-manifest.yaml",
                "guide_screenshot_id": guide_id,
                "image": image.relative_to(root).as_posix(),
                "image_sha256": hashlib.sha256(image_bytes).hexdigest(),
                "date": "2026-08-30",
                "status": "approved",
                "product_owner_approval": {"status": "approved", "date": "2026-08-30"},
            }
        )
    (guide_root / "screenshot-manifest.yaml").write_text(
        yaml.safe_dump({"captures": guide_captures}, sort_keys=False), encoding="utf-8"
    )

    inventory = root / "docs/product/service-reference-inventory.yaml"
    inventory.parent.mkdir(parents=True, exist_ok=True)
    inventory.write_text(
        yaml.safe_dump(
            {
                "schema_version": 3,
                "policy": {"default_lifecycle": "static-bundle"},
                "families": [
                    {
                        "id": "ADM-DB",
                        "normal": {
                            "target_base": "administration-database-normal",
                            "state": "normal",
                            "lifecycle": "current-product-evidence",
                            "approved_viewports": [
                                "1920x1080",
                                "2560x1440",
                                "3840x2160",
                            ],
                            "images": 3,
                        },
                        "image_count": 3,
                    },
                    {
                        "id": "MOD-FIT",
                        "normal": {
                            "target_base": "modeling-fit-normal",
                            "state": "normal",
                            "lifecycle": "current-guide",
                            "approved_viewports": [
                                "1366x768",
                                "1440x900",
                                "1920x1080",
                                "2560x1440",
                                "3840x2160",
                            ],
                            "images": 5,
                        },
                        "exceptions": [],
                        "image_count": 5,
                    },
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    manifest = root / "docs/product/service-reference-manifest.yaml"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(
        yaml.safe_dump(
            {
                "schema_version": 3,
                "retention": "approved-targets-only",
                "default_lifecycle": "static-bundle",
                "references": references,
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return manifest, inventory, evidence_manifest, references


def _write_material_current_lifecycle_fixture(
    root: Path, *, approved: bool = False, operational: bool = False
) -> tuple[Path, list[dict[str, object]]]:
    if approved and operational:
        raise ValueError("fixture dispositions are mutually exclusive")
    manifest, inventory, _, references = _write_dual_lifecycle_service_reference_fixture(root)

    # Replace exactly fifteen synthetic legacy targets with the source-v2
    # Materials current-product shape.  The fixture deliberately uses small
    # deterministic PNGs: this exercises schema, identity, route and hash
    # checks without presenting them as product acceptance evidence.
    for reference in references[:15]:
        (root / str(reference["image"])).unlink()
        (root / str(reference["measurements"])).unlink()

    captures: list[dict[str, object]] = []
    current_references: list[dict[str, object]] = []
    for reference_id, (
        screen,
        state,
        width,
        height,
        image_ref,
        evidence_key,
    ) in user_guide._CURRENT_PRODUCT_SCREENSHOT_REFERENCE_TARGETS.items():
        image = root / image_ref
        image.parent.mkdir(parents=True, exist_ok=True)
        image_bytes = _png_with_dimensions(width, height, reference_id.encode())
        image.write_bytes(image_bytes)
        current_references.append(
            {
                "id": reference_id,
                "screen": screen,
                "state": state,
                "lifecycle": "current-product-evidence",
                "viewport": {
                    "width": width,
                    "height": height,
                    "device_scale_factor": 1,
                },
                "evidence_manifest": "docs/user-guide/screenshot-manifest.yaml",
                "evidence_key": evidence_key,
                "image": image_ref,
                "image_sha256": hashlib.sha256(image_bytes).hexdigest(),
                "date": "2026-08-30",
                "status": (
                    "approved"
                    if approved
                    else "operational-evidence-accepted"
                    if operational
                    else "pending-owner-disposition"
                ),
                "product_owner_approval": (
                    {"status": "approved", "date": "2026-08-30"} if approved else None
                ),
            }
        )
        captures.append(
            {
                "id": evidence_key,
                "route": user_guide._CURRENT_PRODUCT_SCREENSHOT_REFERENCE_ROUTES[reference_id],
                "workflow": "synthetic current-product contract fixture",
                "fixture": "synthetic source-v2 Materials records",
                "image": image_ref.removeprefix("docs/user-guide/"),
                "width": width,
                "height": height,
            }
        )

    # The fixture retains the four current-guide Fit references from the
    # shared dual-lifecycle setup.  Keep their screenshot IDs registered too;
    # the service-reference verifier validates both current-product and
    # current-guide consumers in one manifest.
    for reference in references:
        if reference.get("screen") != "modeling-fit":
            continue
        image_ref = str(reference["image"])
        viewport = reference.get("viewport")
        if not isinstance(viewport, dict):
            raise AssertionError("contract fixture Fit reference has no viewport mapping")
        fit_width = viewport.get("width")
        fit_height = viewport.get("height")
        if not isinstance(fit_width, int) or not isinstance(fit_height, int):
            raise AssertionError("contract fixture Fit reference has invalid viewport dimensions")
        captures.append(
            {
                "id": reference["guide_screenshot_id"],
                "route": "/modeling?stage=fit&family=metal",
                "workflow": "contract fixture Fit capture",
                "fixture": "synthetic current-guide Fit reference",
                "image": image_ref.removeprefix("docs/user-guide/"),
                "width": fit_width,
                "height": fit_height,
            }
        )

    content = yaml.safe_load(manifest.read_text(encoding="utf-8"))
    content["references"] = current_references + references[15:]
    if operational:
        content["current_materials_operational_disposition"] = {
            "status": "accepted",
            "date": "2026-08-31",
            "scope": "behavioral-operation-evidence-only",
            "visual_quality": "pending-owner-disposition",
            "targets": [reference["id"] for reference in current_references],
        }
    manifest.write_text(yaml.safe_dump(content, sort_keys=False), encoding="utf-8")

    inventory_content = yaml.safe_load(inventory.read_text(encoding="utf-8"))
    inventory_content["families"].extend(
        [
            {
                "id": "MAT-EXP",
                "normal": {
                    "target_base": "materials-search-normal",
                    "state": "normal",
                    "lifecycle": "current-product-evidence",
                    "approved_viewports": ["1366x768", "1440x900", "1920x1080"],
                    "images": 3,
                },
                "exceptions": [
                    {"id": "materials-search-long-1440x900"},
                    {"id": "materials-search-empty-1440x900"},
                ],
                "image_count": 5,
            },
            {
                "id": "MAT-DETAIL",
                "normal": {
                    "target_base": "materials-datasheet-overview-normal",
                    "state": "normal",
                    "lifecycle": "current-product-evidence",
                    "approved_viewports": ["1366x768", "1440x900", "1920x1080"],
                    "images": 3,
                },
                "exceptions": [
                    {"id": "materials-datasheet-related-long-1440x900"},
                    {"id": "materials-datasheet-empty-1440x900"},
                ],
                "image_count": 5,
            },
            {
                "id": "MAT-CARD",
                "normal": {
                    "target_base": "materials-card-preview-normal",
                    "state": "normal",
                    "lifecycle": "current-product-evidence",
                    "approved_viewports": ["1366x768", "1440x900", "1920x1080"],
                    "images": 3,
                },
                "exceptions": [
                    {"id": "materials-card-approximation-blocked-1440x900"},
                    {"id": "materials-card-unsupported-blocked-1440x900"},
                ],
                "image_count": 5,
            },
        ]
    )
    inventory.write_text(yaml.safe_dump(inventory_content, sort_keys=False), encoding="utf-8")

    screenshot_manifest = root / "docs/user-guide/screenshot-manifest.yaml"
    screenshot_manifest.parent.mkdir(parents=True, exist_ok=True)
    screenshot_manifest.write_text(
        yaml.safe_dump({"version": 1, "captures": captures}, sort_keys=False),
        encoding="utf-8",
    )
    return manifest, current_references


def test_service_reference_manifest_accepts_phase_a_fifteen_pending_materials(
    tmp_path: Path,
) -> None:
    _, references = _write_material_current_lifecycle_fixture(tmp_path)

    registered = _verify_service_reference_manifest(tmp_path)

    assert len(references) == 15
    assert len(registered) == 73
    assert sum(reference["status"] == "approved" for reference in references) == 0
    assert sum(reference["status"] == "pending-owner-disposition" for reference in references) == 15

    with pytest.raises(UserGuideContractError, match="final publication requires zero pending"):
        _verify_service_reference_manifest(tmp_path, final_publication=True)


def test_service_reference_manifest_accepts_complete_administration_pending_set(
    tmp_path: Path,
) -> None:
    manifest, _ = _write_material_current_lifecycle_fixture(tmp_path, approved=True)
    content = yaml.safe_load(manifest.read_text(encoding="utf-8"))
    administration_ids = {
        "administration-database-normal-1920x1080",
        "administration-database-normal-2560x1440",
        "administration-database-normal-3840x2160",
    }
    for reference in content["references"]:
        if reference["id"] in administration_ids:
            reference["status"] = "pending-owner-disposition"
            reference.pop("product_owner_approval", None)
    manifest.write_text(yaml.safe_dump(content, sort_keys=False), encoding="utf-8")

    registered = _verify_service_reference_manifest(tmp_path)

    assert len(registered) == 73
    assert {
        reference["id"]
        for reference in content["references"]
        if reference["status"] == "pending-owner-disposition"
    } == administration_ids
    with pytest.raises(UserGuideContractError, match="final publication requires zero pending"):
        _verify_service_reference_manifest(tmp_path, final_publication=True)


def test_service_reference_manifest_rejects_partial_administration_pending_set(
    tmp_path: Path,
) -> None:
    manifest, _ = _write_material_current_lifecycle_fixture(tmp_path, approved=True)
    content = yaml.safe_load(manifest.read_text(encoding="utf-8"))
    target = next(
        reference
        for reference in content["references"]
        if reference["id"] == "administration-database-normal-1920x1080"
    )
    target["status"] = "pending-owner-disposition"
    target.pop("product_owner_approval", None)
    manifest.write_text(yaml.safe_dump(content, sort_keys=False), encoding="utf-8")

    with pytest.raises(
        UserGuideContractError,
        match="complete three-reference Administration Database",
    ):
        _verify_service_reference_manifest(tmp_path)


def test_service_reference_manifest_accepts_final_seventy_three_approved_targets(
    tmp_path: Path,
) -> None:
    manifest, _ = _write_material_current_lifecycle_fixture(tmp_path, approved=True)

    registered = _verify_service_reference_manifest(tmp_path, final_publication=True)

    assert len(registered) == 73
    content = yaml.safe_load(manifest.read_text(encoding="utf-8"))
    references = content["references"]
    assert sum(reference["status"] == "approved" for reference in references) == 73
    assert (
        sum(reference.get("status") == "pending-owner-disposition" for reference in references) == 0
    )


def test_service_reference_manifest_accepts_operational_materials_at_final_publication(
    tmp_path: Path,
) -> None:
    manifest, references = _write_material_current_lifecycle_fixture(tmp_path, operational=True)

    registered = _verify_service_reference_manifest(tmp_path, final_publication=True)

    assert len(registered) == 73
    content = yaml.safe_load(manifest.read_text(encoding="utf-8"))
    assert (
        sum(reference["status"] == "operational-evidence-accepted" for reference in references)
        == 15
    )
    assert content["current_materials_operational_disposition"]["visual_quality"] == (
        "pending-owner-disposition"
    )


def test_service_reference_manifest_rejects_operational_scope_drift(
    tmp_path: Path,
) -> None:
    manifest, _ = _write_material_current_lifecycle_fixture(tmp_path, operational=True)
    content = yaml.safe_load(manifest.read_text(encoding="utf-8"))
    content["current_materials_operational_disposition"]["scope"] = "visual-approval"
    manifest.write_text(yaml.safe_dump(content, sort_keys=False), encoding="utf-8")

    with pytest.raises(UserGuideContractError, match="operational evidence scope drifted"):
        _verify_service_reference_manifest(tmp_path, final_publication=True)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("foreign-pending", "ordinary service-reference verification requires exactly"),
        ("missing-image", "service reference image is missing"),
        ("route", "current product reference route drifted"),
    ],
)
def test_service_reference_manifest_rejects_phase_a_scope_or_evidence_drift(
    tmp_path: Path, mutation: str, message: str
) -> None:
    manifest, _ = _write_material_current_lifecycle_fixture(tmp_path)
    content = yaml.safe_load(manifest.read_text(encoding="utf-8"))
    references = content["references"]
    if mutation == "foreign-pending":
        references[15]["status"] = "pending-owner-disposition"
        references[15]["product_owner_approval"] = None
    elif mutation == "missing-image":
        (tmp_path / references[0]["image"]).unlink()
    else:
        screenshot_manifest = tmp_path / "docs/user-guide/screenshot-manifest.yaml"
        captures = yaml.safe_load(screenshot_manifest.read_text(encoding="utf-8"))
        captures["captures"][5]["route"] = "/wrong-route"
        screenshot_manifest.write_text(yaml.safe_dump(captures), encoding="utf-8")
    manifest.write_text(yaml.safe_dump(content, sort_keys=False), encoding="utf-8")

    with pytest.raises(UserGuideContractError, match=message):
        _verify_service_reference_manifest(tmp_path)


def test_service_reference_manifest_accepts_strict_dual_lifecycle(tmp_path: Path) -> None:
    _, _, _, references = _write_dual_lifecycle_service_reference_fixture(tmp_path)
    retained_image = (
        tmp_path / "docs/17-evidence/images/issue-167-service-reference/retained-historical.png"
    )
    retained_image.write_bytes(_png_with_dimensions(32, 24, b"retained-by-other-evidence"))

    registered = _verify_service_reference_manifest(tmp_path)

    assert len(references) == len(registered) == 73
    assert all("measurements" in reference for reference in references[:65])
    assert all("measurements" not in reference for reference in references[65:])
    assert all(reference["lifecycle"] == "current-guide" for reference in references[68:])


def test_service_reference_manifest_keeps_legacy_measurements_strict(tmp_path: Path) -> None:
    _, _, _, references = _write_dual_lifecycle_service_reference_fixture(tmp_path)
    measurement = tmp_path / str(references[0]["measurements"])
    measurement.unlink()

    with pytest.raises(UserGuideContractError, match="measurements are missing"):
        _verify_service_reference_manifest(tmp_path)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("evidence-hash", "hash differs from visual evidence"),
        ("evidence-path-escape", "escapes"),
        ("fake-measurements", "current guide reference contains forbidden fields"),
    ],
)
def test_current_product_reference_rejects_invalid_evidence_lifecycle(
    tmp_path: Path,
    mutation: str,
    message: str,
) -> None:
    manifest, _, evidence_manifest, references = _write_dual_lifecycle_service_reference_fixture(
        tmp_path
    )
    if mutation == "evidence-hash":
        evidence = yaml.safe_load(evidence_manifest.read_text(encoding="utf-8"))
        evidence["viewports"][0]["after_editor"]["sha256"] = "0" * 64
        evidence_manifest.write_text(yaml.safe_dump(evidence), encoding="utf-8")
    elif mutation == "evidence-path-escape":
        evidence = yaml.safe_load(evidence_manifest.read_text(encoding="utf-8"))
        evidence["viewports"][0]["after_editor"]["path"] = "../outside.png"
        evidence_manifest.write_text(yaml.safe_dump(evidence), encoding="utf-8")
    else:
        references[68]["measurements"] = (
            "docs/17-evidence/images/issue-167-service-reference/fake.measurements.json"
        )
        content = yaml.safe_load(manifest.read_text(encoding="utf-8"))
        content["references"] = references
        manifest.write_text(yaml.safe_dump(content, sort_keys=False), encoding="utf-8")

    with pytest.raises(UserGuideContractError, match=message):
        _verify_service_reference_manifest(tmp_path)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("lifecycle-split", "current product reference targets drifted"),
        ("target-identity", "current guide reference targets drifted"),
        ("viewport-set", "current guide reference viewport contract drifted"),
        ("evidence-declaration", "current guide reference contains forbidden fields"),
        ("inventory-viewports", "inventory ADM-DB approved viewports drifted"),
    ],
)
def test_service_reference_manifest_rejects_dual_lifecycle_contract_drift(
    tmp_path: Path,
    mutation: str,
    message: str,
) -> None:
    manifest, inventory, _, references = _write_dual_lifecycle_service_reference_fixture(tmp_path)
    if mutation == "lifecycle-split":
        references[0]["lifecycle"] = "current-product-evidence"
    elif mutation == "target-identity":
        references[69]["id"] = "unsupported-current-guide-id"
    elif mutation == "viewport-set":
        references[69]["viewport"] = {
            "width": 1440,
            "height": 900,
            "device_scale_factor": 2,
        }
    elif mutation == "evidence-declaration":
        references[68]["evidence_manifest"] = (
            "docs/17-evidence/images/issue-290-unapproved/visual-evidence.yaml"
        )
    else:
        content = yaml.safe_load(inventory.read_text(encoding="utf-8"))
        content["families"][0]["normal"]["approved_viewports"][0] = "1366x768"
        inventory.write_text(yaml.safe_dump(content, sort_keys=False), encoding="utf-8")

    if mutation != "inventory-viewports":
        content = yaml.safe_load(manifest.read_text(encoding="utf-8"))
        content["references"] = references
        manifest.write_text(yaml.safe_dump(content, sort_keys=False), encoding="utf-8")

    with pytest.raises(UserGuideContractError, match=message):
        _verify_service_reference_manifest(tmp_path)


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


def test_m1e4_evidence_manifest_is_registered_for_future_capture_paths() -> None:
    assert (
        "docs/17-evidence/images/issue-261-m1e4-modeling-core-stage-ownership/manifest.json"
        in user_guide._STRUCTURED_IMAGE_MANIFESTS
    )


def test_m1e5_evidence_manifest_is_registered_for_future_capture_paths() -> None:
    assert (
        "docs/17-evidence/images/issue-261-m1e5-producer-routed-residual/manifest.json"
        in user_guide._STRUCTURED_IMAGE_MANIFESTS
    )


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
    assert report.capture_count == 158
    assert report.navigation_count == 3
    assert report.classified_markdown_count >= 100
    assert report.current_document_count >= 40
    assert report.local_link_count >= 150
    assert report.image_count >= 120
    assert report.orphan_image_count == 0
    # The current source-v2 Materials captures are intentionally distinct from
    # the retired historical packet; the exact zero-consumer retirement removes
    # the stale duplicate groups while independently-owned evidence remains
    # declared in its manifests.
    assert report.duplicate_image_group_count == 1419


@pytest.mark.parametrize(
    "heading",
    ("# Q-08", "## T-10", "### 12.3", "Q-08\n----", "T-10\n===="),
)
def test_number_only_headings_are_rejected_in_current_documents(
    tmp_path: Path, heading: str
) -> None:
    document = tmp_path / "current.md"
    document.write_text(f"{heading}\n", encoding="utf-8")

    with pytest.raises(UserGuideContractError, match="number-only Markdown heading"):
        _verify_document_links(tmp_path, {"current.md": "current"})


def test_meaningful_headings_and_fenced_examples_remain_allowed(tmp_path: Path) -> None:
    document = tmp_path / "current.md"
    document.write_text(
        "# 긴 목록 스크롤 (Q-01)\n\n```markdown\n# Q-08\n\nQ-08\n----\n```\n",
        encoding="utf-8",
    )

    assert _verify_document_links(tmp_path, {"current.md": "current"}) == (set(), set(), 0)


def test_repository_map_and_current_readme_guidance_are_preserved() -> None:
    _verify_repository_guidance(Path(__file__).parents[2])


@pytest.mark.parametrize(
    ("mutation", "message"),
    (
        ("missing-map", "missing repository map guidance"),
        ("missing-157", "missing the closed #157 current guidance"),
        ("stale-157-old", "stale open-issue guidance for closed #157"),
        ("stale-157-reworded", "stale open-issue guidance for closed #157"),
        ("fixed-tunnel", "must not pin a temporary Quick Tunnel URL"),
    ),
)
def test_repository_guidance_rejects_narrow_documentation_drift(
    tmp_path: Path, mutation: str, message: str
) -> None:
    root = Path(__file__).parents[2]
    portal = (root / "docs/README.md").read_text(encoding="utf-8")
    readme = (root / "README.md").read_text(encoding="utf-8")
    if mutation == "missing-map":
        portal = portal.replace("## 저장소 지도", "## 문서 찾기")
    elif mutation == "missing-157":
        readme = readme.replace("issues/157)에서 완료", "issues/157)을 참고")
    elif mutation == "stale-157-old":
        readme += (
            "\n새 volume에서 전체 seed를 끝까지\n재현하는 실패가 "
            "[#157](https://github.com/pikachu444/cae-material-platform/issues/157)에 "
            "남아 있습니다.\n"
        )
    elif mutation == "stale-157-reworded":
        readme += (
            "\n[#157](https://github.com/pikachu444/cae-material-platform/issues/157)은 "
            "아직 열려 있으며 seed 문제는 미해결입니다.\n"
        )
    else:
        readme += "\nhttps://temporary-demo.trycloudflare.com\n"
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs/README.md").write_text(portal, encoding="utf-8")
    (tmp_path / "README.md").write_text(readme, encoding="utf-8")

    with pytest.raises(UserGuideContractError, match=message):
        _verify_repository_guidance(tmp_path)


def test_documentation_classes_preserve_reference_and_current_boundaries() -> None:
    root = Path(__file__).parents[2]

    classes = _documentation_classes(root)

    assert classes["docs/product/desktop-engineering-ui-program-brief.md"] == "reference"
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

    manifest_source = manifest["source_commit"]
    capture_source = manifest["visual_evidence"]["capture_source"]
    issue260_source = "4f753deaeb4dae9dc48ea2c63fd313c6fe5e7b01+issue260-fe05-worktree"
    fe04d_source = "c1e64be9c05c5a2039ae99aa5867a5f8b11f6621+issue259-fe04d-worktree"
    issue331_source = "working-tree-issue-331-fit-css-ownership"
    administration_source = "working-tree-issue-331-administration-css-retirement"
    issue262_source = "5de648936887422191b08ed227b5680015f16a22+issue262-owner-correction-worktree"
    issue262_fe07b_source = "1333c64553c884fcc9187f39d862cd2146880dc5+issue262-fe07b-worktree"
    issue342_source = "713bafc75a9b0974281126f30b50c78eb1a9dd2a+issue342-task1b-worktree"
    issue371_source = (
        "e55d30f597923509607dd7651d734bda3867b583+issue371-catalog-single-owner-worktree"
    )
    issue377_source = "aa8c6e942420cc67b637edd92d988c9fbf678b27+issue377-worktree"
    assert manifest["version"] == 142
    assert manifest["scope"] == "issue-377-polymer-linear-viscoelastic-fit-ui"
    assert manifest_source == issue377_source
    assert re.fullmatch(r"[0-9a-f]{40}\+issue309-worktree", capture_source)
    assert manifest["visual_evidence"]["baseline_source"] == capture_source.split("+")[0]
    assert manifest["visual_evidence"]["current_source"] == capture_source
    assert {
        "b4_combined_manifest",
        "b4_combined_report",
        "geometry_measurements",
        "issue_261_m1e3_after_provenance",
        "issue_261_m1e3_before_after",
        "issue_261_m1e3_before_provenance",
        "issue_261_m1e3_report",
        "sidecar",
    }.isdisjoint(manifest["visual_evidence"])
    assert manifest["visual_evidence"]["issue_309_evidence_after_original_count"] == 5
    assert "Preserved-volume cmp-377-ui-dense Compose" in manifest["capture_command"]
    assert "Thirty-one reviewed originals" in manifest["capture_command"]
    assert len(provenance_ids) == len(set(provenance_ids))
    preserved_fixture_ids = {
        "solver-card-preview-1366",
        "solver-card-preview-1440",
        "solver-card-preview-1920",
    }
    assert set(captures) - set(provenance_ids) == preserved_fixture_ids
    assert {provenance["source_commit"] for provenance in manifest["capture_provenance"]} == {
        issue377_source,
        issue371_source,
        issue331_source,
        administration_source,
        issue342_source,
        capture_source,
        issue262_source,
        issue262_fe07b_source,
        issue260_source,
        fe04d_source,
        "ef364087147e51e22cc02534645ba23b628c23d7+issue253-demo-token-refresh-worktree",
        "971ea100b6d7032eb1308b01b455c95cb9773408+issue246-live-data-correction-v4",
        "f8fe6ef85d345837a6252b6ba8b3b706ccbe009f",
        "ff9ba293222ea5a9e17821e4dc8c4ef1b0bcb1a5",
        "e9b523a7f7b613d8d6efc0396160f0ceb2aff2c4",
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
    historically_new_issue_206_captures = {
        "material-curves-1366",
        "material-curves-1440",
        "material-curves-1920",
        "material-curves-2560",
        "material-curves-3840",
    }
    new_issue_210_captures = {
        capture_id for capture_id in captures if capture_id.startswith("modeling-distribution-")
    }
    new_issue_246_captures = {
        "material-database-categories-1440",
        "material-database-linked-test-1440",
    }
    historically_new_issue_246_schema_captures = {"administration-schema-bundle-1440"}
    new_issue_253_captures = {"demo-session-recovery-1440"}
    new_issue_262_fe07a_captures = {
        "materials-search-1366",
        "materials-search-1440",
        "materials-search-1920",
        "materials-search-2560",
        "materials-search-3840",
        "materials-browse-1440",
        "material-detail-1366",
        "material-detail-1440",
        "material-detail-1920",
        "material-detail-2560",
        "material-detail-3840",
        "material-curves-1366",
        "material-curves-1440",
        "material-curves-1920",
        "material-curves-2560",
        "material-curves-3840",
    }
    new_issue_262_fe07b_captures = {
        "administration-format-definitions-1440",
        "administration-access-1366",
        "administration-access-1440",
        "administration-access-1920",
        "administration-access-2560",
        "administration-access-3840",
    }
    new_administration_captures = {
        "administration-database-1366",
        "administration-database-1440",
        "administration-database-1920",
        "administration-database-2560",
        "administration-database-3840",
        "administration-database-preview-1366",
        "administration-database-preview-1440",
        "administration-database-preview-1920",
        "administration-database-preview-2560",
        "administration-database-preview-3840",
        "administration-records-1366",
        "administration-records-1440",
        "administration-records-1920",
        "administration-records-2560",
        "administration-records-3840",
    }
    new_issue_342_captures = {
        "administration-records-import-json-1366",
        "administration-records-import-json-1440",
        "administration-records-import-json-1920",
        "administration-records-import-json-2560",
        "administration-records-import-json-3840",
    }
    historically_new_issue_289_preview_captures = {
        "administration-database-preview-1366",
        "administration-database-preview-1440",
        "administration-database-preview-1920",
        "administration-database-preview-2560",
        "administration-database-preview-3840",
    }
    retained_issue_206_captures = {
        "materials-scroll-long-1366",
        "materials-scroll-long-1440",
        "materials-scroll-long-1920",
        "materials-scroll-short-1440",
        "materials-scroll-empty-1440",
        "material-cae-cards-1440",
    }
    new_issue_309_captures = {"modeling-data-1366"}
    new_issue_260_captures = {
        "modeling-data-1440",
        "modeling-data-1920",
        "modeling-data-2560",
        "modeling-data-3840",
        "modeling-session-1366",
        "modeling-session-1440",
        "modeling-session-1920",
        "modeling-data-empty-1440",
        "modeling-data-invalid-1440",
        "modeling-data-invalid-scrolled-1440",
        "modeling-export-1366",
        "modeling-export-1440",
        "modeling-export-1920",
        "modeling-export-2560",
        "modeling-export-3840",
        "modeling-export-source-blocked",
        "modeling-export-approximation-blocked",
        "modeling-export-delivered",
    }
    new_issue_259_fe04d_captures = {
        "MOD-PROCESS-CURRENT-LINEAR-1366",
        "MOD-PROCESS-CURRENT-MANUAL-1366",
        "MOD-PROCESS-CURRENT-BLOCKED-1440",
        "MOD-PROCESS-CURRENT-EXACT-READ-FAILED-1440",
        "MOD-PROCESS-CURRENT-SIBLINGS-1440",
    }
    new_issue_331_captures = {
        "MOD-PROCESS-CURRENT-1366",
        "MOD-PROCESS-CURRENT-1440",
        "MOD-PROCESS-CURRENT-1920",
        "MOD-PROCESS-CURRENT-2560",
        "MOD-PROCESS-CURRENT-3840",
        "modeling-fit-calculation-failed-1920",
        "modeling-fit-save-failed-1920",
        "modeling-fit-exact-source-blocked-1920",
        "modeling-fit-exact-read-failed-1920",
        "modeling-fit-restored-1920",
    }
    new_issue_209_captures = {
        capture_id
        for capture_id in captures
        if capture_id.startswith(("modeling-data-dma-", "modeling-data-fld-"))
    }
    new_issue_371_captures = {
        "material-detail-related-long-1440",
        "material-detail-empty-1440",
        "solver-card-preview-2560",
        "solver-card-preview-3840",
        "solver-card-approximation-blocked-1440",
        "solver-card-unsupported-blocked-1440",
    }
    new_issue_377_captures = {
        capture_id
        for capture_id in captures
        if capture_id.startswith(("modeling-fit-polymer-", "modeling-process-polymer-dma-tts"))
        or capture_id in {
            "modeling-fit-1366",
            "modeling-fit-1440",
            "modeling-fit-1920",
            "modeling-fit-2560",
            "modeling-fit-3840",
        }
    }
    assert set(previous_provenance_ids) == (
        set(captures)
        - new_issue_184_captures
        - historically_new_issue_206_captures
        - new_issue_210_captures
        - new_issue_246_captures
        - historically_new_issue_246_schema_captures
        - new_issue_253_captures
        - new_issue_209_captures
        - historically_new_issue_289_preview_captures
        - new_administration_captures
        - {"administration-format-definitions-1440"}
        - new_issue_342_captures
        - new_issue_371_captures
        - new_issue_377_captures
    )
    assert {
        prior_source,
        correction_source,
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
        if provenance["source_commit"] == "e9b523a7f7b613d8d6efc0396160f0ceb2aff2c4"
    )
    assert "--only-materials" in issue_206_provenance["command"]
    assert retained_issue_206_captures == set(issue_206_provenance["ids"])
    issue_262_provenance = next(
        provenance
        for provenance in manifest["capture_provenance"]
        if provenance["source_commit"] == issue262_source
    )
    assert "capture_issue_262_fe07a_visual_evidence.py" in issue_262_provenance["command"]
    assert "query-error retention/retry" in issue_262_provenance["command"]
    assert new_issue_262_fe07a_captures == set(issue_262_provenance["ids"])
    issue_262_fe07b_provenance = next(
        provenance
        for provenance in manifest["capture_provenance"]
        if provenance["source_commit"] == issue262_fe07b_source
    )
    assert "issue262-administration-visual.spec.ts" in issue_262_fe07b_provenance["command"]
    assert "actual demo API" in issue_262_fe07b_provenance["command"]
    assert new_issue_262_fe07b_captures == set(issue_262_fe07b_provenance["ids"])
    issue_342_provenance = next(
        provenance
        for provenance in manifest["capture_provenance"]
        if provenance["source_commit"] == issue342_source
    )
    assert "fresh-Docker PostgreSQL/API/browser run" in issue_342_provenance["command"]
    assert (
        "captured the valid-preview state at 1366x768, 1440x900, 1920x1080, "
        "2560x1440 and 3840x2160 at browser zoom 100% and DPR 1" in issue_342_provenance["command"]
    )
    assert new_issue_342_captures == set(issue_342_provenance["ids"])
    issue_377_provenance = next(
        provenance
        for provenance in manifest["capture_provenance"]
        if provenance["source_commit"] == issue377_source
    )
    assert "browser zoom 100%, DPR 1" in issue_377_provenance["command"]
    assert new_issue_377_captures == set(issue_377_provenance["ids"])
    issue_210_provenance = next(
        provenance
        for provenance in manifest["capture_provenance"]
        if provenance["source_commit"] == "ff9ba293222ea5a9e17821e4dc8c4ef1b0bcb1a5"
    )
    assert "--only-modeling-distribution" in issue_210_provenance["command"]
    assert new_issue_210_captures == set(issue_210_provenance["ids"])
    issue_246_provenance = next(
        provenance
        for provenance in manifest["capture_provenance"]
        if provenance["source_commit"].endswith("+issue246-live-data-correction-v4")
    )
    assert "capture_issue246_live_evidence.mjs" in issue_246_provenance["command"]
    assert new_issue_246_captures == set(issue_246_provenance["ids"])
    issue_253_provenance = next(
        provenance
        for provenance in manifest["capture_provenance"]
        if provenance["source_commit"].endswith("+issue253-demo-token-refresh-worktree")
    )
    assert "native Python Playwright 1.62" in issue_253_provenance["command"]
    assert new_issue_253_captures == set(issue_253_provenance["ids"])
    issue_260_provenance = next(
        provenance
        for provenance in manifest["capture_provenance"]
        if provenance["source_commit"] == issue260_source
    )
    assert "--only-modeling-data-session" in issue_260_provenance["command"]
    assert "--only-modeling-process-fit-viewports" in issue_260_provenance["command"]
    assert "--only-modeling-export" in issue_260_provenance["command"]
    assert "--only-modeling-consistency" in issue_260_provenance["command"]
    assert new_issue_260_captures == set(issue_260_provenance["ids"])
    issue_309_provenance = next(
        provenance
        for provenance in manifest["capture_provenance"]
        if provenance["source_commit"] == capture_source
    )
    assert "native Python Playwright 1.62" in issue_309_provenance["command"]
    assert "Data to Process to Data" in issue_309_provenance["command"]
    assert new_issue_309_captures == set(issue_309_provenance["ids"])
    issue_331_provenance = next(
        provenance
        for provenance in manifest["capture_provenance"]
        if provenance["source_commit"] == issue331_source
    )
    assert "--only-modeling-process-fit" in issue_331_provenance["command"]
    assert new_issue_331_captures == set(issue_331_provenance["ids"])
    administration_provenance = next(
        provenance
        for provenance in manifest["capture_provenance"]
        if provenance["source_commit"] == administration_source
    )
    assert "--only-administration-database" in administration_provenance["command"]
    assert "--only-administration-records" in administration_provenance["command"]
    assert new_administration_captures == set(administration_provenance["ids"])
    for capture_id in new_administration_captures:
        if capture_id.startswith("administration-records-"):
            fixture = captures[capture_id]["fixture"]
            assert "Record Revision 1" in fixture
            assert "Revision 2" not in fixture
            assert "create/revise" not in fixture
    issue_259_fe04d_provenance = next(
        provenance
        for provenance in manifest["capture_provenance"]
        if provenance["source_commit"] == fe04d_source
    )
    assert "--only-modeling-process" in issue_259_fe04d_provenance["command"]
    assert new_issue_259_fe04d_captures == set(issue_259_fe04d_provenance["ids"])
    issue_209_provenance = next(
        provenance
        for provenance in manifest["capture_provenance"]
        if provenance["source_commit"] == "f8fe6ef85d345837a6252b6ba8b3b706ccbe009f"
    )
    assert "capture_issue209_visual_evidence.py" in issue_209_provenance["command"]
    assert new_issue_209_captures == set(issue_209_provenance["ids"])
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
    for capture_id in (
        "administration-access-1366",
        "administration-access-1440",
        "administration-access-1920",
        "administration-access-2560",
        "administration-access-3840",
    ):
        capture = captures[capture_id]
        assert capture["workflow"] == ("inspect-active-access-and-grant-remove-exact-assignment")
        assert (
            "Member, Role, server-derived Permissions and row-level Remove access"
            in capture["fixture"]
        )
    for capture_id in (
        "modeling-export-1366",
        "modeling-export-1440",
        "modeling-export-1920",
    ):
        capture = captures[capture_id]
        assert capture["workflow"] == (
            "one-selected-model solver-card setup, native preview, mapping review and atomic delivery"
        )
        assert "one immutable card/receipt" in capture["fixture"]


def test_mat_detail_captures_do_not_claim_stale_approved_references() -> None:
    root = Path(__file__).parents[2]
    manifest = yaml.safe_load(
        (root / "docs/user-guide/screenshot-manifest.yaml").read_text(encoding="utf-8")
    )
    detail_captures = [
        capture for capture in manifest["captures"] if capture["id"].startswith("material-detail-")
    ]
    assert {capture["width"] for capture in detail_captures} == {1366, 1440, 1920, 2560, 3840}
    retired_fields = {"comparison_evidence", "evidence_source", "owner_direction_images"}
    assert all(retired_fields.isdisjoint(capture) for capture in manifest["captures"])
    for capture in detail_captures:
        assert "approved_reference_ids" not in capture
        current_image = root / "docs/user-guide" / capture["image"]
        assert current_image.is_file()


def test_current_images_are_product_routes_and_storybook_captures_are_untracked() -> None:
    root = Path(__file__).parents[2]
    manifest = yaml.safe_load(
        (root / "docs/user-guide/screenshot-manifest.yaml").read_text(encoding="utf-8")
    )
    current_images = root / "docs/user-guide/images/current"
    assert len(manifest["captures"]) == 158
    assert all(not capture["route"].startswith("/iframe.html") for capture in manifest["captures"])
    assert not list(current_images.glob("storybook-*.png"))
    assert len(list(current_images.glob("*.png"))) == 160
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

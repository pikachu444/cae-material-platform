from __future__ import annotations

from collections import Counter, deque
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[3]
INVENTORY_PATH = ROOT / "docs/01-product/service-reference-inventory.yaml"
MANIFEST_PATH = ROOT / "docs/01-product/service-reference-manifest.yaml"


def fail(message: str) -> None:
    raise AssertionError(message)


def expanded_family_targets(
    family: dict[str, Any], viewport_keys: list[str]
) -> list[str]:
    normal = family["normal"]
    targets = [f"{normal['target_base']}-{key}" for key in viewport_keys]
    targets.extend(item["id"] for item in family.get("exceptions", []))
    return targets


def assert_acyclic(bundles: list[dict[str, Any]]) -> None:
    identifiers = {bundle["id"] for bundle in bundles}
    indegree = {identifier: 0 for identifier in identifiers}
    followers: dict[str, list[str]] = {identifier: [] for identifier in identifiers}
    for bundle in bundles:
        for dependency in bundle.get("depends_on", []):
            if dependency not in identifiers:
                fail(f"unknown bundle dependency: {bundle['id']} -> {dependency}")
            indegree[bundle["id"]] += 1
            followers[dependency].append(bundle["id"])
    queue = deque(identifier for identifier, degree in indegree.items() if degree == 0)
    visited = 0
    while queue:
        identifier = queue.popleft()
        visited += 1
        for follower in followers[identifier]:
            indegree[follower] -= 1
            if indegree[follower] == 0:
                queue.append(follower)
    if visited != len(identifiers):
        fail("bundle dependency graph contains a cycle")


def main() -> None:
    inventory = yaml.safe_load(INVENTORY_PATH.read_text(encoding="utf-8"))
    manifest = yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))
    if inventory.get("schema_version") != 1 or inventory.get("issue") != 167:
        fail("unexpected inventory schema or issue")

    policy = inventory["policy"]
    viewport_keys = [item["key"] for item in policy["normal_viewports"]]
    if viewport_keys != ["1366x768", "1440x900", "1920x1080"]:
        fail(f"unexpected normal viewport order: {viewport_keys}")
    exceptional_key = policy["exceptional_image_viewport"]["key"]
    if exceptional_key != "1440x900":
        fail(f"unexpected exceptional viewport: {exceptional_key}")

    families = inventory["families"]
    bundles = inventory["bundles"]
    family_ids = [family["id"] for family in families]
    bundle_ids = [bundle["id"] for bundle in bundles]
    if len(family_ids) != len(set(family_ids)):
        fail("duplicate family id")
    if len(bundle_ids) != len(set(bundle_ids)):
        fail("duplicate bundle id")
    if set(family_ids) != {
        family_id for bundle in bundles for family_id in bundle["family_ids"]
    }:
        fail("bundle family coverage is incomplete or contains an unknown family")

    expanded_targets: list[str] = []
    family_counts: Counter[str] = Counter()
    for family in families:
        normal = family["normal"]
        if normal.get("images") != 3:
            fail(f"{family['id']} normal target count is not three")
        exceptions = family.get("exceptions", [])
        if any(not item["id"].endswith(f"-{exceptional_key}") for item in exceptions):
            fail(f"{family['id']} exceptional target is not canonical 1440x900")
        expected_count = normal["images"] + len(exceptions)
        if family.get("image_count") != expected_count:
            fail(f"{family['id']} image_count mismatch")
        if not family.get("evidence_only_states"):
            fail(f"{family['id']} has no deterministic exceptional-state evidence")
        targets = expanded_family_targets(family, viewport_keys)
        expanded_targets.extend(targets)
        family_counts[family["bundle"]] += len(targets)

    if len(expanded_targets) != len(set(expanded_targets)):
        duplicates = [
            target
            for target, count in Counter(expanded_targets).items()
            if count > 1
        ]
        fail(f"duplicate expanded target id: {duplicates}")

    for bundle in bundles:
        if family_counts[bundle["id"]] != bundle["image_count"]:
            fail(
                f"{bundle['id']} image_count mismatch: "
                f"{family_counts[bundle['id']]} != {bundle['image_count']}"
            )
    assert_acyclic(bundles)

    counts = inventory["counts"]
    normal_images = len(families) * len(viewport_keys)
    exceptional_images = sum(len(family.get("exceptions", [])) for family in families)
    total_images = len(expanded_targets)
    expected_counts = {
        "families": len(families),
        "bundles": len(bundles),
        "normal_images": normal_images,
        "exceptional_images": exceptional_images,
        "total_images": total_images,
    }
    for key, value in expected_counts.items():
        if counts.get(key) != value:
            fail(f"inventory {key} mismatch: {counts.get(key)} != {value}")

    manifest_entries = manifest.get("references", [])
    manifest_ids = [entry["id"] for entry in manifest_entries]
    if len(manifest_ids) != len(set(manifest_ids)):
        fail("duplicate manifest target id")
    unknown_manifest = sorted(set(manifest_ids) - set(expanded_targets))
    if unknown_manifest:
        fail(f"manifest targets absent from inventory: {unknown_manifest}")
    approved = sum(entry.get("status") == "approved" for entry in manifest_entries)
    if counts["approved_images_at_freeze"] != 5:
        fail("approved_images_at_freeze must preserve the original five-image baseline")
    if counts["remaining_images_at_freeze"] != total_images - counts["approved_images_at_freeze"]:
        fail("remaining_images_at_freeze mismatch")
    if approved != counts["approved_images_current"]:
        fail(
            "approved_images_current no longer matches manifest; "
            "advance inventory progress evidence deliberately"
        )
    if counts["remaining_images_current"] != total_images - approved:
        fail("remaining_images_current mismatch")

    first_wave = inventory["first_parallel_wave"]
    wave_bundles = first_wave["bundles"]
    if len(wave_bundles) != 2 or len(set(wave_bundles)) != 2:
        fail("first wave must contain exactly two independent bundles")
    dependency_map = {
        bundle["id"]: set(bundle.get("depends_on", [])) for bundle in bundles
    }
    if (
        wave_bundles[0] in dependency_map[wave_bundles[1]]
        or wave_bundles[1] in dependency_map[wave_bundles[0]]
    ):
        fail(f"first-wave bundles are directly dependent: {wave_bundles}")
    wave_targets = first_wave["targets"]
    if any(target not in expanded_targets for target in wave_targets):
        fail("first wave names a target outside the inventory")
    if first_wave.get("status") == "planned":
        if any(target in manifest_ids for target in wave_targets):
            fail("planned first wave includes an already registered target")
    elif first_wave.get("status") in {
        "registered-pending-main-review",
        "review-pending",
        "product-owner-pending",
        "approved",
    }:
        missing = sorted(set(wave_targets) - set(manifest_ids))
        if missing:
            fail(f"registered first wave is incomplete in the manifest: {missing}")
    else:
        fail(f"unexpected first-wave status: {first_wave.get('status')!r}")

    print(
        "PASS issue-167 service-reference inventory: "
        f"{len(families)} families, {len(bundles)} bundles, "
        f"{normal_images} normal + {exceptional_images} exceptional = "
        f"{total_images} images"
    )
    print(
        f"progress: {approved}/{total_images} approved; "
        f"{total_images - approved} remaining"
    )
    print(f"first parallel wave: {' + '.join(wave_bundles)}")


if __name__ == "__main__":
    main()

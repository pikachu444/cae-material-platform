"""Validate the bounded Issue #261 M1E5 visual-evidence acceptance record.

Main owns the disposable browser/Compose capture and promotion of image records. This
helper validates the durable contract and the recorded final packet without fabricating
captures or accepting incomplete evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "docs/17-evidence/images/issue-261-m1e5-producer-routed-residual/manifest.json"
FIXTURE_PATH = ROOT / "scripts/fixtures/issue-261-m1e5-producer-routed-residual.json"
EVIDENCE_ROOT = ROOT / "docs/17-evidence/images/issue-261-m1e5-producer-routed-residual"
VIEWPORTS = ["1366x768", "1440x900", "1920x1080", "2560x1440", "3840x2160"]
CROPS = {"header", "navigator", "table-form", "stage-controls", "engineering-graph", "native-preview"}
CLASSIFICATIONS = {"primary", "technical", "negative"}
PRIMARY_JOURNEY_IDS = [
    "modeling-data-metal",
    "modeling-process-metal",
]
CAPTURED_TARGET_TOPOLOGY_IDS = [
    "modeling-data-metal",
    "materials-curves",
    "governed-import",
    "canonical-test-json",
    "exports",
    "modeling-fit-elastomer",
]
NO_SCREENSHOT_STATE_IDS = {
    "modeling-process-metal",
    "modeling-fit-metal",
    "modeling-export-metal",
    "modeling-fit-polymer",
    "modeling-export-polymer",
    "modeling-export-elastomer",
}
PRODUCER_PATHS = {
    "apps/web/src/neutral-hyperelastic-export.tsx",
    "apps/web/src/reference-elastoplastic-workbench.tsx",
    "apps/web/src/reference-linear-viscoelastic-export.tsx",
}
RENDERED_PRODUCER_JOURNEY_ID = "authenticated-elastomer-fit-neutral-export"
RENDERED_PRODUCER_PATH = "apps/web/src/neutral-hyperelastic-export.tsx"
RENDERED_PRODUCER_SELECTORS = [
    'section.neutral-solver-export[aria-label="Reviewed Neutral Material and solver card delivery"] .mapping-report-heading',
    'section.neutral-solver-export[aria-label="Reviewed Neutral Material and solver card delivery"] .mapping-list',
]
SHA256_LENGTH = 64
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg"}
M1E5_IMAGE_PREFIX = "docs/17-evidence/images/issue-261-m1e5-producer-routed-residual/"
DUPLICATE_IMAGE_ROOTS = (
    ROOT / "docs/00-research",
    ROOT / "docs/17-evidence/images",
    ROOT / "docs/user-guide/images/current",
)
DUPLICATE_GROUP_COUNT = 115
DUPLICATE_IMAGE_PATH_COUNT = 821
DUPLICATE_GROUP_MAX_SIZE = 128
DUPLICATE_GROUP_CROSS_EVIDENCE_COUNT = 21
DUPLICATE_GROUP_RATIONALE = (
    "Byte-identical before/after, crop, and prior-evidence files are equivalent existing evidence bytes; "
    "no new capture is implied."
)
# The current-guide manifest remains the accepted pre-existing image set. Keep this
# declaration literal so the documentation contract can verify the existing image
# inventory without creating or promoting any additional capture.
CURRENT_CAPTURE_OUTPUTS = (
    "materials-search-1366x768.png",
    "materials-search-1440x900.png",
    "materials-search-1920x1080.png",
    "materials-search-2560x1440.png",
    "materials-search-3840x2160.png",
    "materials-search-long-1366x768.png",
    "materials-search-long-1440x900.png",
    "materials-search-long-1920x1080.png",
    "materials-search-short-1440x900.png",
    "materials-search-empty-1440x900.png",
    "materials-browse-1440x900.png",
    "demo-session-recovery-1440x900.png",
    "material-database-categories-1440x900.png",
    "material-database-linked-test-1440x900.png",
    "material-detail-1440x900.png",
    "material-detail-1366x768.png",
    "material-detail-1920x1080.png",
    "material-detail-2560x1440.png",
    "material-detail-3840x2160.png",
    "material-curves-1366x768.png",
    "material-curves-1440x900.png",
    "material-curves-1920x1080.png",
    "material-curves-2560x1440.png",
    "material-curves-3840x2160.png",
    "material-cae-cards-1440x900.png",
    "solver-card-preview-1366x768.png",
    "solver-card-preview-1440x900.png",
    "solver-card-preview-1920x1080.png",
    "modeling-data-1366x768.png",
    "modeling-session-1366x768.png",
    "modeling-session-1440x900.png",
    "modeling-session-1920x1080.png",
    "modeling-data-1440x900.png",
    "modeling-data-1920x1080.png",
    "modeling-data-2560x1440.png",
    "modeling-data-3840x2160.png",
    "modeling-data-dma-1366x768.png",
    "modeling-data-dma-1440x900.png",
    "modeling-data-dma-1920x1080.png",
    "modeling-data-dma-2560x1440.png",
    "modeling-data-dma-3840x2160.png",
    "modeling-data-dma-rejected-1366x768.png",
    "modeling-data-dma-rejected-1440x900.png",
    "modeling-data-dma-rejected-1920x1080.png",
    "modeling-data-dma-rejected-2560x1440.png",
    "modeling-data-dma-rejected-3840x2160.png",
    "modeling-data-fld-1366x768.png",
    "modeling-data-fld-1440x900.png",
    "modeling-data-fld-1920x1080.png",
    "modeling-data-fld-2560x1440.png",
    "modeling-data-fld-3840x2160.png",
    "modeling-data-empty-1440x900.png",
    "modeling-data-invalid-1440x900.png",
    "modeling-data-invalid-scrolled-1440x900.png",
    "modeling-process-1366x768.png",
    "modeling-process-linear-regression-1366x768.png",
    "modeling-process-manual-1366x768.png",
    "modeling-process-1440x900.png",
    "modeling-process-1920x1080.png",
    "modeling-process-2560x1440.png",
    "modeling-process-3840x2160.png",
    "modeling-process-blocked-1440x900.png",
    "modeling-process-exact-read-failed-1440x900.png",
    "modeling-process-siblings-1440x900.png",
    "modeling-fit-1366x768.png",
    "modeling-fit-1440x900.png",
    "modeling-fit-1920x1080.png",
    "modeling-fit-2560x1440.png",
    "modeling-fit-3840x2160.png",
    "modeling-fit-candidate-parameters-long-1440x900.png",
    "modeling-fit-candidate-evidence-scrolled-1440x900.png",
    "modeling-fit-calculation-failed-1920x1080.png",
    "modeling-fit-save-failed-1920x1080.png",
    "modeling-fit-exact-source-blocked-1920x1080.png",
    "modeling-fit-exact-read-failed-1920x1080.png",
    "modeling-fit-restored-1920x1080.png",
    "modeling-export-1366x768.png",
    "modeling-export-1440x900.png",
    "modeling-export-1920x1080.png",
    "modeling-export-2560x1440.png",
    "modeling-export-3840x2160.png",
    "modeling-export-source-blocked-1440x900.png",
    "modeling-export-approximation-blocked-1440x900.png",
    "modeling-export-delivered-1440x900.png",
    "activity-1366x768.png",
    "activity-1440x900.png",
    "activity-1920x1080.png",
    "activity-2560x1440.png",
    "activity-3840x2160.png",
    "activity-history-1440x900.png",
    "activity-history-1920x1080.png",
    "activity-history-2560x1440.png",
    "activity-history-3840x2160.png",
    "activity-user-1440x900.png",
    "activity-administrator-1440x900.png",
    "activity-decision-error-1440x900.png",
    "activity-recovery-1440x900.png",
    "administration-schema-bundle-1440x900.png",
    "administration-database-1366x768.png",
    "administration-database-1440x900.png",
    "administration-database-1920x1080.png",
    "administration-database-2560x1440.png",
    "administration-database-3840x2160.png",
    "administration-database-preview-1366x768.png",
    "administration-database-preview-1440x900.png",
    "administration-database-preview-1920x1080.png",
    "administration-database-preview-2560x1440.png",
    "administration-database-preview-3840x2160.png",
    "administration-records-1366x768.png",
    "administration-records-1440x900.png",
    "administration-records-1920x1080.png",
    "administration-records-2560x1440.png",
    "administration-records-3840x2160.png",
    "administration-access-1366x768.png",
    "administration-access-role-control-1366x768.png",
    "administration-access-1440x900.png",
    "administration-access-1920x1080.png",
    "administration-access-2560x1440.png",
    "administration-access-3840x2160.png",
    "modeling-distribution-1366x768.png",
    "modeling-distribution-1440x900.png",
    "modeling-distribution-1920x1080.png",
    "modeling-distribution-2560x1440.png",
    "modeling-distribution-3840x2160.png",
)
EXPECTED_ROUTE_IDS = {
    "modeling-data-metal",
    "modeling-process-metal",
    "modeling-fit-metal",
    "modeling-export-metal",
    "modeling-process-elastomer-hold",
    "modeling-alias-process",
    "materials-curves",
    "governed-import",
    "canonical-test-json",
    "exports",
    "modeling-fit-polymer",
    "modeling-export-polymer",
    "modeling-fit-elastomer",
    "modeling-export-elastomer",
    "modeling-alias-data",
}
LIVE_SELECTOR_IDS = [
    "CSS-0160", "CSS-0161", "CSS-0162", "CSS-0164", "CSS-0165", "CSS-0167", "CSS-0168", "CSS-0169", "CSS-0170", "CSS-0171", "CSS-0178", "CSS-0179", "CSS-0180", "CSS-0181", "CSS-0182", "CSS-0183", "CSS-0455", "CSS-0886", "CSS-0897", "CSS-0898", "CSS-0961", "CSS-1008", "CSS-1009", "CSS-1010", "CSS-1011", "CSS-1012", "CSS-1013", "CSS-1014", "CSS-1114", "CSS-1115", "CSS-1116", "CSS-1117", "CSS-1118", "CSS-1120", "CSS-1122", "CSS-1123", "CSS-1124", "CSS-1126",
]
NA_SOURCE_TEST_SELECTOR_IDS = [
    "CSS-0158", "CSS-0163", "CSS-0166", "CSS-0172", "CSS-0173", "CSS-0174", "CSS-0175", "CSS-0176", "CSS-0887", "CSS-0984", "CSS-0985", "CSS-1019", "CSS-1020", "CSS-1057", "CSS-1058", "CSS-1059", "CSS-1121", "CSS-1125", "CSS-1157", "CSS-1158",
]
LIVE_ROUTE_COUNTS = {
    "materials-curves": 16,
    "modeling-data-metal": 11,
    "governed-import": 7,
    "exports": 2,
    "canonical-test-json": 1,
    "modeling-fit-elastomer": 1,
}
CONDITIONAL_CURVE_GROUP_IDS = ["CSS-0172", "CSS-0173", "CSS-0174", "CSS-0175", "CSS-0176"]
CONDITIONAL_CURVE_GROUP_REASON = "The normal producer SVG five-viewport route does not materialize the conditional active/tooltip state; CSS-0172–CSS-0176 remain source/bundle/component-tested with no DOM/state fabrication."
GOVERNED_IMPORT_0887_REASON = "The normal governed-import producer does not materialize the conditional preview .curve-heading row; CSS-0887 remains source/component/bundle-tested and no live locator is claimed."
ACCEPTED_MANIFEST_STATUS = "ACCEPTED_MAIN_VISUAL_AND_RUNTIME"
ACCEPTED_CAPTURE_EVIDENCE = "ACCEPTED_MAIN_CAPTURE"
N_A_CAPTURE_EVIDENCE = "N/A_SOURCE_TEST"
EQUIVALENCE_CAPTURE_EVIDENCE = "ACCEPTED_MAIN_EQUIVALENCE"


class ContractError(ValueError):
    """Raised when the M1E5 evidence contract is malformed."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractError(message)


def load_manifest(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractError(f"cannot read manifest {path}: {exc}") from exc
    require(isinstance(value, dict), "manifest root must be an object")
    return value


def validate_selector_application(manifest: dict[str, Any]) -> None:
    try:
        fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractError(f"cannot read selector fixture {FIXTURE_PATH}: {exc}") from exc
    application = manifest.get("capture_plan", {}).get("selector_application")
    require(isinstance(application, dict), "capture_plan.selector_application is required")
    require(application.get("status_counts") == {"LIVE": 38, "N_A_SOURCE_TEST": 20, "RETAINED_HOLD": 2}, "selector application counts drifted")
    require(application.get("live_ids") == LIVE_SELECTOR_IDS, "LIVE selector partition drifted")
    na = application.get("na_source_test")
    require(isinstance(na, list) and [item.get("id") for item in na] == NA_SOURCE_TEST_SELECTOR_IDS, "N/A selector partition drifted")
    conditional_curve_group = [item for item in na if item.get("id") in CONDITIONAL_CURVE_GROUP_IDS]
    require([item.get("id") for item in conditional_curve_group] == CONDITIONAL_CURVE_GROUP_IDS, "conditional curve group partition drifted")
    for item in conditional_curve_group:
        require(item.get("reason") == CONDITIONAL_CURVE_GROUP_REASON, f"{item.get('id')}: conditional group reason drifted")
        require("curve-contract-chart.tsx" in item.get("source_evidence", {}).get("source", ""), f"{item.get('id')}: source proof missing")
        require("curve-contract-chart.test.tsx" in item.get("source_evidence", {}).get("component", ""), f"{item.get('id')}: component-test proof missing")
    governed_import_0887 = next((item for item in na if item.get("id") == "CSS-0887"), None)
    require(governed_import_0887 is not None and governed_import_0887.get("reason") == GOVERNED_IMPORT_0887_REASON, "CSS-0887 N/A reason drifted")
    require("design/primitives.css" in governed_import_0887["source_evidence"]["source"], "CSS-0887 source proof missing")
    require("governed-import-workbench.tsx" in governed_import_0887["source_evidence"]["component"], "CSS-0887 component proof missing")
    require("app.tsx" in governed_import_0887["source_evidence"]["import_chain"] and "governed-import-workbench" in governed_import_0887["source_evidence"]["import_chain"], "CSS-0887 import proof missing")
    require(application.get("retained_hold_ids") == ["CSS-1446", "CSS-1447"], "retained hold selector partition drifted")
    require(application.get("live_route_counts") == LIVE_ROUTE_COUNTS, "LIVE route counts drifted")
    target_rows = {row[0]: row for row in fixture.get("targetTuples", [])}
    properties = application.get("intended_properties")
    require(isinstance(properties, dict) and list(properties) == LIVE_SELECTOR_IDS, "intended property map drifted")
    contracts = application.get("live_contracts")
    require(isinstance(contracts, list) and [item.get("id") for item in contracts] == LIVE_SELECTOR_IDS, "LIVE locator contract drifted")
    observed_route_counts: dict[str, int] = {}
    for contract in contracts:
        require(isinstance(contract.get("locator"), str) and contract["locator"], f"{contract.get('id')}: LIVE locator required")
        require(isinstance(contract.get("base_selector"), str) and contract["base_selector"], f"{contract.get('id')}: base selector required")
        require(properties.get(contract["id"]) == target_rows[contract["id"]][8], f"{contract['id']}: intended properties must match frozen fixture")
        if contract.get("route_id") == "modeling-data-metal":
            require(contract["locator"].startswith(".modeling-workspace-stage-data "), f"{contract['id']}: Data locator must use the visible stage scope")
            require(".modeling-data-plot" not in contract["locator"], f"{contract['id']}: stale Data plot scope")
        route_id = contract.get("route_id")
        observed_route_counts[route_id] = observed_route_counts.get(route_id, 0) + 1
    require(observed_route_counts == LIVE_ROUTE_COUNTS, "LIVE route contract counts drifted")
    for record in na:
        require(record.get("disposition") == "N/A_SOURCE_TEST", f"{record.get('id')}: N/A disposition drifted")
        proof = record.get("source_evidence")
        require(isinstance(proof, dict) and all(isinstance(proof.get(key), str) and proof[key] for key in ("source", "component", "import_chain", "bundle")), f"{record.get('id')}: exact source/component/import/bundle proof required")
    focus_record = next((record for record in na if record.get("id") == "CSS-0158"), None)
    require(focus_record is not None, "CSS-0158 N/A source-test record is required")
    require(focus_record["reason"] == "The normal Materials curve SVG is captured at all five required viewports; the focus pseudo-state is source/bundle/component-tested per the owner verification-reduction direction and is not fabricated.", "CSS-0158 N/A reason drifted")
    require("curve-contract-chart.test.tsx" in focus_record["source_evidence"]["component"], "CSS-0158 component-test proof is required")


def validate_registered_images(manifest: dict[str, Any]) -> None:
    registered = manifest.get("registered_images")
    require(isinstance(registered, list), "registered_images must be a list")
    require(len(registered) == 390, "registered_images must contain exactly 390 PNG entries")
    paths: list[str] = []
    for ordinal, record in enumerate(registered, start=1):
        require(isinstance(record, dict), f"registered_images[{ordinal}] must be an object")
        image = record.get("image")
        require(isinstance(image, str) and image, f"registered_images[{ordinal}].image is required")
        require(image.startswith("docs/17-evidence/images/issue-261-m1e5-producer-routed-residual/"), f"registered_images[{ordinal}] must stay in the M1E5 evidence root")
        require(image.lower().endswith(".png"), f"registered_images[{ordinal}] must reference a PNG")
        paths.append(image)
    require(len(set(paths)) == len(paths), "registered_images must contain unique paths")
    require(paths == sorted(paths), "registered_images must be lexicographically sorted")

    expected = sorted(
        path.relative_to(ROOT).as_posix()
        for phase in ("before", "after")
        for path in (EVIDENCE_ROOT / phase).rglob("*.png")
        if path.is_file()
    )
    require(paths == expected, "registered_images must exactly match PNG files under before/after evidence trees")


def current_duplicate_image_groups(registered_paths: set[str]) -> list[tuple[str, list[str]]]:
    """Return the complete current repository-wide duplicate-image groups for M1E5."""

    hashes: dict[str, list[str]] = {}
    for image_root in DUPLICATE_IMAGE_ROOTS:
        for path in image_root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in IMAGE_EXTENSIONS:
                continue
            relative = path.relative_to(ROOT).as_posix()
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            hashes.setdefault(digest, []).append(relative)

    groups = [
        (digest, sorted(paths))
        for digest, paths in hashes.items()
        if len(paths) >= 2 and any(path in registered_paths for path in paths)
    ]
    return sorted(groups, key=lambda item: item[1][0])


def validate_duplicate_image_groups(manifest: dict[str, Any]) -> None:
    """Validate explicit equivalence provenance for every current M1E5 duplicate group."""

    registered = manifest.get("registered_images")
    require(isinstance(registered, list), "registered_images must be a list before duplicate-group validation")
    registered_paths = {
        record["image"]
        for record in registered
        if isinstance(record, dict) and isinstance(record.get("image"), str)
    }
    declared = manifest.get("allowed_duplicate_groups")
    require(isinstance(declared, list), "allowed_duplicate_groups must be a list")
    require(len(declared) == DUPLICATE_GROUP_COUNT, f"allowed_duplicate_groups must contain exactly {DUPLICATE_GROUP_COUNT} groups")

    declared_paths: list[list[str]] = []
    seen_paths: set[str] = set()
    previous_first: str | None = None
    for ordinal, record in enumerate(declared, start=1):
        require(isinstance(record, dict), f"allowed_duplicate_groups[{ordinal}] must be an object")
        require(record.get("rationale") == DUPLICATE_GROUP_RATIONALE, f"allowed_duplicate_groups[{ordinal}] rationale drifted")
        images = record.get("images")
        require(isinstance(images, list) and len(images) >= 2, f"allowed_duplicate_groups[{ordinal}].images must contain at least two paths")
        require(all(isinstance(path, str) and path for path in images), f"allowed_duplicate_groups[{ordinal}].images must contain non-empty strings")
        require(images == sorted(images), f"allowed_duplicate_groups[{ordinal}].images must be lexicographically sorted")
        require(len(images) == len(set(images)), f"allowed_duplicate_groups[{ordinal}].images must contain unique paths")
        first_path = images[0]
        require(previous_first is None or previous_first < first_path, "allowed_duplicate_groups must be deterministically ordered by first path")
        previous_first = first_path
        require(not seen_paths.intersection(images), f"allowed_duplicate_groups[{ordinal}] overlaps a previous group")
        seen_paths.update(images)
        require(any(path in registered_paths for path in images), f"allowed_duplicate_groups[{ordinal}] must include an M1E5 registered image")

        digests: set[str] = set()
        for path_text in images:
            path = Path(path_text)
            require(not path.is_absolute() and path.suffix.lower() in IMAGE_EXTENSIONS, f"allowed_duplicate_groups[{ordinal}] contains an invalid image path")
            candidate = ROOT / path
            try:
                relative = candidate.resolve().relative_to(ROOT.resolve()).as_posix()
            except ValueError as exc:
                raise ContractError(f"allowed_duplicate_groups[{ordinal}] escapes the repository root") from exc
            require(relative == path_text and candidate.is_file(), f"allowed_duplicate_groups[{ordinal}] references a missing image: {path_text}")
            digests.add(hashlib.sha256(candidate.read_bytes()).hexdigest())
        require(len(digests) == 1, f"allowed_duplicate_groups[{ordinal}] paths must share one SHA-256 digest")
        declared_paths.append(images)

    expected = current_duplicate_image_groups(registered_paths)
    require(len(expected) == DUPLICATE_GROUP_COUNT, "current repository duplicate-image group count drifted")
    expected_paths = [paths for _, paths in expected]
    require(declared_paths == expected_paths, "allowed_duplicate_groups must exactly match current repository-wide duplicate groups containing M1E5 registered images")
    require(sum(len(paths) for paths in declared_paths) == DUPLICATE_IMAGE_PATH_COUNT, "allowed_duplicate_groups image-path count drifted")
    require(max(len(paths) for paths in declared_paths) == DUPLICATE_GROUP_MAX_SIZE, "allowed_duplicate_groups maximum group size drifted")
    cross_evidence_count = sum(
        any(path.startswith(M1E5_IMAGE_PREFIX) for path in paths)
        and any(not path.startswith(M1E5_IMAGE_PREFIX) for path in paths)
        for paths in declared_paths
    )
    require(cross_evidence_count == DUPLICATE_GROUP_CROSS_EVIDENCE_COUNT, "allowed_duplicate_groups cross-evidence count drifted")


def validate_acceptance(manifest: dict[str, Any]) -> None:
    """Validate Main's durable capture, runtime, and visual-review facts."""

    require(manifest.get("status") == ACCEPTED_MANIFEST_STATUS, "accepted manifest status is required")
    serialized = json.dumps(manifest, sort_keys=True)
    require("PENDING_MAIN_CAPTURE" not in serialized, "accepted manifest contains pending capture evidence")
    validate_registered_images(manifest)
    validate_duplicate_image_groups(manifest)
    acceptance = manifest.get("acceptance")
    require(isinstance(acceptance, dict), "acceptance record is required")
    require(acceptance.get("owner_direction") == "OWNER_DIRECTION_APPLIED_MAIN_INSPECTED", "owner direction record drifted")

    partition = acceptance.get("selector_partition")
    require(
        partition == {
            "status_counts": {"LIVE": 38, "N_A_SOURCE_TEST": 20, "RETAINED_HOLD": 2},
            "focus_visible": "CSS-0158:N_A_SOURCE_TEST",
            "digest_line": ["CSS-1057", "CSS-1058", "CSS-1059"],
            "governed_import_curve_heading": "CSS-0887:N_A_SOURCE_TEST",
        },
        "accepted selector partition summary drifted",
    )

    inventory = acceptance.get("capture_inventory")
    require(isinstance(inventory, dict), "acceptance.capture_inventory is required")
    require(inventory.get("captured_topology_count") == 7, "seven captured topologies are required")
    require(inventory.get("viewports_each") == 5, "each captured topology must cover five viewports")
    require(
        inventory.get("before") == {
            "file_count": 230,
            "png_count": 195,
            "computed_json_count": 35,
            "tree_sha256": "aa04391a18abefa75333233f242ec10a5ef52710d057fdf2edf0eaac6991b795",
        },
        "before capture inventory drifted",
    )
    require(
        inventory.get("after") == {
            "file_count": 230,
            "png_count": 195,
            "computed_json_count": 35,
            "tree_sha256": "5034120f72edca441c1ac20d5b49a0238b65a1c2322153d4add99ad2b3d3dc5f",
        },
        "after capture inventory drifted",
    )
    require(
        inventory.get("captured_topologies") == [
            "modeling-data-metal",
            "materials-curves",
            "governed-import",
            "canonical-test-json",
            "exports",
            "modeling-fit-elastomer",
            "modeling-process-elastomer-hold",
        ],
        "captured topology list drifted",
    )
    require(
        inventory.get("no_screenshot_state_ids") == [
            "modeling-process-metal",
            "modeling-fit-metal",
            "modeling-export-metal",
            "modeling-fit-polymer",
            "modeling-export-polymer",
            "modeling-export-elastomer",
        ],
        "no-screenshot acceptance list drifted",
    )
    require(
        inventory.get("equivalence_aliases") == [
            {"id": "modeling-alias-process", "equivalent_to": "modeling-process-metal", "viewport": "1440x900", "disposition": EQUIVALENCE_CAPTURE_EVIDENCE},
            {"id": "modeling-alias-data", "equivalent_to": "modeling-data-metal", "viewport": "1440x900", "disposition": EQUIVALENCE_CAPTURE_EVIDENCE},
        ],
        "equivalence acceptance list drifted",
    )
    require(
        inventory.get("recovery") == {
            "id": "modeling-exact-revision-recovery-1440",
            "disposition": N_A_CAPTURE_EVIDENCE,
            "reason": "Exact recovery route was unavailable; source-test N/A retained.",
        },
        "recovery acceptance record drifted",
    )

    runtime = acceptance.get("runtime")
    require(isinstance(runtime, dict), "acceptance.runtime is required")
    require(
        runtime.get("exact_base_targeted") == {
            "data_materials": "PASS_MAIN_RUNTIME",
            "governed_canonical_exports": "PASS_MAIN_RUNTIME",
            "fit_hold": "PASS_MAIN_RUNTIME",
        },
        "exact-base runtime acceptance drifted",
    )
    require(
        runtime.get("candidate_disposable_specs") == {
            "modeling-data-metal": "PASS_MAIN_RUNTIME",
            "modeling-fit-elastomer": "PASS_MAIN_RUNTIME",
            "modeling-process-elastomer-hold": "PASS_MAIN_RUNTIME",
            "materials-curves": "PASS_MAIN_RUNTIME",
            "governed-import": "PASS_MAIN_RUNTIME",
            "canonical-test-json": "PASS_MAIN_RUNTIME",
            "exports": "PASS_MAIN_RUNTIME",
        },
        "candidate disposable runtime acceptance drifted",
    )
    require(runtime.get("aliases") == "PASS_MAIN_RUNTIME", "alias runtime acceptance drifted")
    require(runtime.get("isolated_seed_runs") == 1, "isolated seed run count drifted")
    require(
        runtime.get("cleanup") == {
            "disposable_projects_containers_images_volumes_removed": True,
            "permanent_cmp_local_demo_volumes_untouched": True,
            "compose_preflight_foreign_stopped_permanent_cmp_local_demo_identified": True,
        },
        "runtime cleanup record drifted",
    )

    metrics = acceptance.get("metrics")
    require(isinstance(metrics, dict), "acceptance.metrics is required")
    require(metrics.get("selector_computed_equality") == {"matched": 190, "total": 190}, "selector computed equality drifted")
    require(metrics.get("page_geometry") == {"matched": 35, "total": 35}, "page geometry result drifted")
    require(metrics.get("crop_geometry_display_overflow") == {"matched": 160, "total": 160}, "crop geometry result drifted")
    require(
        metrics.get("selector_geometry") == {
            "exact": 175,
            "total": 190,
            "difference_count": 15,
            "differences": [
                {
                    "selectors": ["CSS-0161", "CSS-0162", "CSS-0164"],
                    "viewport_count": 5,
                    "route_id": "materials-curves",
                    "before_width": 230.375,
                    "after_width": 226.5625,
                    "x_y_height_unchanged": True,
                    "reason": "Seed-generated revision prefix 2a942de3 vs 2f24caad glyph width; no CSS regression.",
                }
            ],
        },
        "selector geometry result drifted",
    )
    require(metrics.get("png_byte_identity") == {"identical": 160, "total": 195}, "PNG identity result drifted")
    require(
        metrics.get("topology_pixel_summary") == {
            "canonical-test-json": {"identical": 24, "total": 25},
            "exports": {"identical": 15, "total": 30},
            "governed-import": {"identical": 25, "total": 25},
            "materials-curves": {"identical": 21, "total": 25},
            "modeling-data-metal": {"identical": 30, "total": 30},
            "modeling-fit-elastomer": {"identical": 20, "total": 35},
            "modeling-process-elastomer-hold": {"identical": 25, "total": 25},
        },
        "topology pixel summary drifted",
    )

    visual_review = acceptance.get("visual_review")
    require(isinstance(visual_review, dict), "acceptance.visual_review is required")
    require(visual_review.get("native_originals_opened") is True, "native originals must be opened")
    require(visual_review.get("representative_crops_opened") is True, "representative crops must be opened")
    require(visual_review.get("crop_viewports") == ["1366x768", "3840x2160"], "representative crop viewports drifted")
    require(visual_review.get("browser_zoom_percent") == 100 and visual_review.get("device_pixel_ratio") == 1, "visual review zoom/DPR drifted")
    require(
        visual_review.get("design_synthesis") == {
            "information_hierarchy": "PASS_MAIN",
            "engineering_task_flow": "PASS_MAIN",
            "responsive_wide_screen_composition": "PASS_MAIN",
        },
        "#249 design synthesis review drifted",
    )
    require(visual_review.get("no_clipping_overflow_topology_regression") is True, "visual regression disposition drifted")
    require(visual_review.get("physical_readability") == "DEFERRED_TO_223", "physical readability must remain deferred to #223")

    require(
        manifest.get("records") == [
            {"id": "main-capture-tree-before", "phase": "before", "file_count": 230, "png_count": 195, "computed_json_count": 35, "tree_sha256": "aa04391a18abefa75333233f242ec10a5ef52710d057fdf2edf0eaac6991b795", "disposition": "PASS_MAIN_CAPTURE"},
            {"id": "main-capture-tree-after", "phase": "after", "file_count": 230, "png_count": 195, "computed_json_count": 35, "tree_sha256": "5034120f72edca441c1ac20d5b49a0238b65a1c2322153d4add99ad2b3d3dc5f", "disposition": "PASS_MAIN_CAPTURE"},
            {"id": "main-visual-comparison", "selector_computed_equality": "190/190", "page_geometry": "35/35", "crop_geometry_display_overflow": "160/160", "selector_geometry": "175/190", "png_byte_identity": "160/195", "disposition": "PASS_MAIN_VISUAL"},
            {"id": "main-runtime-topology", "captured_topologies": 7, "viewports_each": 5, "aliases": "2/2", "disposition": "PASS_MAIN_RUNTIME"},
        ],
        "acceptance records drifted",
    )

    review = manifest.get("review")
    require(isinstance(review, dict), "review object is required")
    require(review.get("main_visual_runtime_acceptance") == "PASS_MAIN", "Main visual/runtime acceptance must be PASS")
    require(review.get("product_owner_original_resolution_review") == "OWNER_DIRECTION_APPLIED_MAIN_INSPECTED", "owner direction review record drifted")
    require(review.get("physical_windows_4k_readability") == "DEFERRED_TO_223", "physical readability status drifted")
    require(isinstance(review.get("notes"), str) and "Physical Windows 4K readability remains deferred to #223" in review["notes"], "review notes must retain the #223 physical gate")


def validate_manifest(manifest: dict[str, Any], path: Path) -> None:
    require(manifest.get("schema_version") == 1, "schema_version must be 1")
    require(manifest.get("issue") == "#261", "issue must be #261")
    require(manifest.get("unit") == "M1E5-producer-routed-residual", "wrong M1E5 unit")
    require(manifest.get("status") == ACCEPTED_MANIFEST_STATUS, "manifest must record accepted Main visual/runtime evidence")
    require(manifest.get("browser_zoom_percent") == 100, "browser zoom must be fixed at 100%")
    require(manifest.get("device_pixel_ratio") == 1, "device pixel ratio must be recorded as 1")
    require(manifest.get("viewports") == VIEWPORTS, "five required CSS viewports are incomplete or reordered")

    ownership = manifest.get("ownership")
    require(isinstance(ownership, dict), "ownership object is required")
    expected_counts = {
        "candidate_selector_rows": 60,
        "candidate_rule_groups": 51,
        "approved_selector_rows": 58,
        "approved_rule_groups": 49,
        "retained_hold_rows": 2,
        "retained_hold_groups": 2,
    }
    for key, expected in expected_counts.items():
        require(ownership.get(key) == expected, f"ownership.{key} must be {expected}")
    for key in ("approved_tuple_sha256", "candidate_tuple_sha256", "retained_tuple_sha256"):
        value = ownership.get(key)
        require(isinstance(value, str) and len(value) == SHA256_LENGTH, f"ownership.{key} must be a SHA-256 digest")

    journey = manifest.get("journey")
    require(isinstance(journey, dict), "journey is required")
    require(
        journey.get("behavior_disposition") == "PRESERVED_PRE_EXISTING_BEHAVIOR_OUTSIDE_M1E5",
        "journey.behavior_disposition must preserve pre-existing behavior outside M1E5",
    )

    capture_plan = manifest.get("capture_plan")
    require(isinstance(capture_plan, dict), "capture_plan is required")
    require(capture_plan.get("phases") == ["before", "after"], "before/after phases are required")
    require(capture_plan.get("required_viewports") == VIEWPORTS, "capture viewport matrix is incomplete")
    require(set(capture_plan.get("required_crops", [])) == CROPS, "required direct crop set changed")
    require(capture_plan.get("original_resolution_required") is True, "original-resolution review is required")
    require(capture_plan.get("zoom_fixed_percent") == 100, "capture zoom must be 100%")
    require(capture_plan.get("device_pixel_ratio") == 1, "capture DPR must be 1")
    require(capture_plan.get("physical_readability") == "DEFERRED_TO_223", "physical 4K gate must remain deferred to #223")
    validate_selector_application(manifest)
    topology = capture_plan.get("topology_matrix")
    require(isinstance(topology, dict), "topology_matrix is required")
    require(topology.get("unique_topologies") == [
        "modeling-data-metal", "modeling-process-elastomer-hold", "materials-curves", "governed-import", "canonical-test-json", "exports", "modeling-fit-polymer", "modeling-export-polymer", "modeling-fit-elastomer", "modeling-export-elastomer",
    ], "captured topology matrix drifted")
    require(topology.get("captured_target_topologies") == CAPTURED_TARGET_TOPOLOGY_IDS, "captured target topology accounting drifted")
    no_screenshot = topology.get("no_screenshot_states")
    require(isinstance(no_screenshot, list) and [item.get("id") for item in no_screenshot] == ["modeling-process-metal", "modeling-fit-metal", "modeling-export-metal", "modeling-fit-polymer", "modeling-export-polymer", "modeling-export-elastomer"], "no-screenshot state accounting drifted")
    for item in no_screenshot:
        require(item.get("disposition") == "N/A_REDUNDANT_NO_LIVE_TARGETS" and isinstance(item.get("reason"), str) and item["reason"], f"{item.get('id')}: no-screenshot reason is required")
    require(topology.get("equivalence_groups") == [
        {"id": "modeling-data-metal", "canonical": "modeling-data-metal", "aliases": ["modeling-alias-data"], "source_routes": ["/modeling", "/datasets/processing"]},
        {"id": "modeling-process-metal", "canonical": "modeling-process-metal", "aliases": ["modeling-alias-process"], "source_routes": ["/modeling", "/datasets/processing"]},
    ], "direct-route equivalence groups drifted")

    primary_journey = capture_plan.get("primary_journey")
    require(isinstance(primary_journey, dict), "primary_journey is required")
    require(primary_journey.get("id") == "authenticated-modeling-data-process-handoff", "primary journey id drifted")
    require(primary_journey.get("authentication") and "demo-identity/token" in primary_journey["authentication"], "primary journey must record demo authentication")
    require(primary_journey.get("exact_fixture") == "CMP-DEMO-DP780-TEST-JSON@r1", "primary journey must pin the exact Test Data fixture")
    sequence = primary_journey.get("route_sequence")
    require(isinstance(sequence, list) and [item.get("id") for item in sequence if isinstance(item, dict)] == PRIMARY_JOURNEY_IDS, "primary journey route sequence drifted")
    require(primary_journey.get("coverage_role") == "normal Data producer plus one representative no-screenshot Process handoff recovery; no Fit/Export mutation or screenshot claim", "primary journey must identify the common-workbench boundary")
    require(primary_journey.get("evidence") == ACCEPTED_CAPTURE_EVIDENCE, "primary journey must record accepted capture evidence")

    producer_coverage = capture_plan.get("producer_coverage")
    require(isinstance(producer_coverage, dict), "producer_coverage must partition rendered and unreachable producers")
    rendered = producer_coverage.get("rendered")
    require(isinstance(rendered, list) and len(rendered) == 1, "producer_coverage.rendered must contain one supported producer journey")
    rendered_journey = rendered[0]
    require(isinstance(rendered_journey, dict), "rendered producer journey must be an object")
    require(rendered_journey.get("id") == RENDERED_PRODUCER_JOURNEY_ID, "rendered producer journey id drifted")
    require(rendered_journey.get("producer_paths") == [RENDERED_PRODUCER_PATH], "rendered producer path must be the Neutral export consumer")
    require(rendered_journey.get("rendered_selectors") == RENDERED_PRODUCER_SELECTORS, "rendered producer selectors drifted")
    rendered_sequence = rendered_journey.get("route_sequence")
    require(
        isinstance(rendered_sequence, list)
        and len(rendered_sequence) == 1
        and isinstance(rendered_sequence[0], dict)
        and rendered_sequence[0].get("id") == "modeling-fit-elastomer"
        and rendered_sequence[0].get("route") == "/modeling?stage=fit&family=elastomer",
        "rendered producer route must be the supported elastomer Fit journey",
    )
    require(isinstance(rendered_journey.get("authentication"), str) and "demo-identity/token" in rendered_journey["authentication"], "rendered producer journey must record demo authentication")
    require(isinstance(rendered_journey.get("exact_fixture"), str) and "Synthetic Elastomer" in rendered_journey["exact_fixture"], "rendered producer journey must pin the synthetic elastomer fixture")
    require(rendered_journey.get("evidence") == ACCEPTED_CAPTURE_EVIDENCE, "rendered producer journey must record accepted capture evidence")
    unreachable = producer_coverage.get("unreachable")
    require(isinstance(unreachable, list) and len(unreachable) == 2, "producer_coverage.unreachable must record the two unsupported producer routes")
    unreachable_paths = set()
    for item in unreachable:
        require(isinstance(item, dict), "unreachable producer records must be objects")
        path_value = item.get("producer_path")
        require(path_value in PRODUCER_PATHS, f"unreachable producer path is not in the M1E5 roster: {path_value}")
        unreachable_paths.add(path_value)
        require(path_value != RENDERED_PRODUCER_PATH, "the rendered Neutral producer cannot also be unreachable")
        require(item.get("status") == "UNREACHABLE_WITHOUT_PRODUCT_ROUTE", f"{path_value}: unsupported route status must be explicit")
        evidence = item.get("source_evidence")
        require(isinstance(evidence, list) and evidence, f"{path_value}: source evidence is required for an unreachable producer")
        require(isinstance(item.get("decision"), str) and "Do not claim rendered producer coverage" in item["decision"], f"{path_value}: unreachable decision must forbid false coverage")
    require(unreachable_paths | {RENDERED_PRODUCER_PATH} == PRODUCER_PATHS, "producer coverage must partition all three mapping-report consumers exactly once")

    route_matrix = capture_plan.get("route_matrix")
    require(isinstance(route_matrix, list), "route_matrix must enumerate every browser producer case")
    route_ids = {route.get("id") for route in route_matrix if isinstance(route, dict)}
    require(route_ids == EXPECTED_ROUTE_IDS, "route_matrix ids drifted from the M1E5 browser producer matrix")
    for route in route_matrix:
        require(isinstance(route, dict), "route_matrix records must be objects")
        require(isinstance(route.get("route"), str) and route["route"], f"{route.get('id')}: route is required")
        require(isinstance(route.get("selectors"), list) and route["selectors"], f"{route.get('id')}: producer selectors are required")
        require(route.get("classification") in CLASSIFICATIONS, f"{route.get('id')}: classification must be primary, technical, or negative")
        if "rendered_selectors" in route:
            require(isinstance(route.get("rendered_selectors"), list) and route["rendered_selectors"], f"{route.get('id')}: rendered producer selectors must be non-empty")
        if route.get("capture_disposition") in {"collapsed-equivalence", "no-screenshot-technical"}:
            require(route.get("required_viewports") == [] and route.get("required_crops") == [], f"{route.get('id')}: collapsed alias must not duplicate captures")
            if route.get("capture_disposition") == "collapsed-equivalence":
                require(route.get("equivalence_group") and route.get("equivalent_to") == route.get("equivalence_group"), f"{route.get('id')}: equivalence target is required")
            else:
                require(route.get("id") in NO_SCREENSHOT_STATE_IDS and isinstance(route.get("reason"), str) and route["reason"].startswith("N/A_REDUNDANT_NO_LIVE_TARGETS:"), f"{route.get('id')}: no-screenshot reason is required")
        else:
            require(route.get("required_viewports") == VIEWPORTS, f"{route.get('id')}: viewport matrix drifted")
        crops = route.get("required_crops")
        require(isinstance(crops, list) and set(crops).issubset(CROPS), f"{route.get('id')}: crop set is invalid")
        disposition = route.get("capture_disposition")
        expected_evidence = (
            N_A_CAPTURE_EVIDENCE
            if disposition == "no-screenshot-technical"
            else EQUIVALENCE_CAPTURE_EVIDENCE
            if disposition == "collapsed-equivalence"
            else ACCEPTED_CAPTURE_EVIDENCE
        )
        require(route.get("evidence") == expected_evidence, f"{route.get('id')}: evidence disposition drifted")
    elastomer_route = next((route for route in route_matrix if route.get("id") == "modeling-fit-elastomer"), None)
    require(isinstance(elastomer_route, dict), "modeling-fit-elastomer producer route is required")
    require(elastomer_route.get("classification") == "primary", "modeling-fit-elastomer must be the rendered primary producer route")
    require(elastomer_route.get("rendered_selectors") == RENDERED_PRODUCER_SELECTORS, "modeling-fit-elastomer rendered selectors drifted")
    require(elastomer_route.get("selectors") == [".mapping-report-heading", ".mapping-list"], "modeling-fit-elastomer CSSOM selectors must name the mapping report")

    states = capture_plan.get("state_matrix")
    require(isinstance(states, list) and states, "state_matrix must contain bounded states")
    state_ids = {state.get("id") for state in states if isinstance(state, dict)}
    require(state_ids == EXPECTED_ROUTE_IDS, "state_matrix must enumerate the same route ids as route_matrix")
    for state in states:
        require(isinstance(state, dict), "state records must be objects")
        require(state.get("classification") in CLASSIFICATIONS, f"{state.get('id')}: classification must be primary, technical, or negative")
        disposition = state.get("capture_disposition")
        expected_evidence = (
            N_A_CAPTURE_EVIDENCE
            if disposition == "no-screenshot-technical"
            else EQUIVALENCE_CAPTURE_EVIDENCE
            if disposition == "collapsed-equivalence"
            else ACCEPTED_CAPTURE_EVIDENCE
        )
        require(state.get("evidence") == expected_evidence, f"{state.get('id')}: evidence disposition drifted")
        if state.get("capture_disposition") in {"collapsed-equivalence", "no-screenshot-technical"}:
            require(state.get("required_viewports") == [] and state.get("required_crops") == [], f"{state.get('id')}: collapsed alias must not duplicate captures")
            if state.get("capture_disposition") == "no-screenshot-technical":
                require(state.get("id") in NO_SCREENSHOT_STATE_IDS and isinstance(state.get("reason"), str) and state["reason"].startswith("N/A_REDUNDANT_NO_LIVE_TARGETS:"), f"{state.get('id')}: no-screenshot reason is required")
        else:
            require(state.get("required_viewports") == VIEWPORTS, f"{state.get('id')}: viewport matrix drifted")

    recovery_matrix = capture_plan.get("recovery_matrix")
    require(isinstance(recovery_matrix, list) and recovery_matrix, "recovery_matrix must record source-test/N/A recovery states")
    for recovery in recovery_matrix:
        require(isinstance(recovery, dict), "recovery records must be objects")
        require(recovery.get("viewport") == "1440x900", f"{recovery.get('id')}: recovery viewport must be 1440x900")
        require(recovery.get("disposition") == "N/A_SOURCE_TEST", f"{recovery.get('id')}: recovery must remain source-tested/N/A")

    validate_acceptance(manifest)
    print(f"PASS {path}: M1E5 accepted Main visual/runtime evidence valid; physical Windows 4K readability deferred to #223")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()
    path = args.manifest if args.manifest.is_absolute() else ROOT / args.manifest
    try:
        validate_manifest(load_manifest(path), path)
    except ContractError as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

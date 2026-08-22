"""Validate the approved Issue #261 M1E4 visual-evidence contract.

This is intentionally a no-fabrication validator.  Main runs the existing disposable
Compose/Product and Storybook capture stack; this helper only proves that the v5 plan is
complete before any evidence is promoted.  Pending image/hash fields are allowed, but
incomplete state, selector, source-pair, runtime, keyboard, or review contracts fail.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / (
    "docs/17-evidence/images/issue-261-m1e4-modeling-core-stage-ownership/manifest.json"
)
REQUIRED_VIEWPORTS = ["1366x768", "1440x900", "1920x1080", "2560x1440", "3840x2160"]
REQUIRED_CROPS = {
    "header",
    "navigator",
    "table-form",
    "stage-controls",
    "engineering-graph",
    "native-preview",
}
FAMILIES = {
    "MOD-DATA": "data",
    "MOD-PROCESS": "process",
    "MOD-FIT": "fit",
    "MOD-EXPORT": "export",
}
NORMAL_STATE_IDS = {f"{family}.normal" for family in FAMILIES}
EXPECTED_STATE_IDS = {
    *NORMAL_STATE_IDS,
    "MOD-DATA.empty-new-session",
    "MOD-DATA.long-invalid-mapping-blocked",
    "MOD-DATA.detecting-loading",
    "MOD-DATA.saving-loading",
    "MOD-DATA.parse-error",
    "MOD-DATA.import-error",
    "MOD-DATA.save-error",
    "MOD-PROCESS.prerequisite-blocked",
    "MOD-PROCESS.long-curve-rail-and-operation-list",
    "MOD-PROCESS.preview-or-commit-loading",
    "MOD-PROCESS.preview-or-commit-error-with-graph-preserved",
    "MOD-FIT.candidate-parameters-long",
    "MOD-FIT.no-candidate-empty",
    "MOD-FIT.calculating",
    "MOD-FIT.stale-or-no-selection-blocked",
    "MOD-FIT.fit-error-with-rail-ribbon-and-graph-preserved",
    "MOD-EXPORT.source-blocked",
    "MOD-EXPORT.approximation-blocked",
    "MOD-EXPORT.delivered",
    "MOD-EXPORT.no-target-empty",
    "MOD-EXPORT.preflight-or-delivering-loading",
    "MOD-EXPORT.delivery-error-with-preflight-preserved",
    "MOD-EXPORT.long-mapping-disclosure",
    "modeling-alias.normal",
    "modeling-reload-readback",
    "materials-browse-lineage-readback",
}
TARGET_MATCHES = {
    "MOD-DATA": [
        "CSS-0133..0135",
        "CSS-0324",
        "CSS-0326",
        "CSS-1214",
        "CSS-1219",
        "CSS-1226..1227",
        "CSS-1233",
        "CSS-1245",
    ],
    "MOD-PROCESS": [
        "CSS-0133..0135",
        "CSS-0324",
        "CSS-0326",
        "CSS-0371..0373",
        "CSS-0396..0401",
    ],
    "MOD-FIT": [
        "CSS-0133..0135",
        "CSS-0217",
        "CSS-0225..0227",
        "CSS-0324",
        "CSS-0326",
        "CSS-0371..0378",
    ],
    "MOD-EXPORT": [
        "CSS-0133..0135",
        "CSS-0217",
        "CSS-0225..0227",
        "CSS-0324",
        "CSS-0326",
        "CSS-0371..0378",
        "CSS-0396..0401",
    ],
}
EVIDENCE_ONLY_IDS = EXPECTED_STATE_IDS - NORMAL_STATE_IDS - {
    "modeling-alias.normal",
    "modeling-reload-readback",
    "materials-browse-lineage-readback",
}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class ContractError(ValueError):
    """Raised when the durable capture contract is incomplete or malformed."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractError(message)


def require_text(value: Any, label: str) -> None:
    require(isinstance(value, str) and bool(value.strip()), f"{label} must be non-empty text")


def require_sha(value: Any, label: str, *, allow_pending: bool = True) -> None:
    if allow_pending and value is None:
        return
    require(isinstance(value, str) and SHA256_RE.fullmatch(value) is not None, f"{label} must be a SHA-256 hex digest or null pending value")


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ContractError(f"cannot read manifest {path}: {error}") from error
    require(isinstance(payload, dict), "manifest root must be an object")
    return payload


def check_reference_artifact(entry: dict[str, Any], label: str) -> None:
    require("path" in entry and "sha256" in entry, f"{label} needs path and sha256 fields")
    path = entry["path"]
    require_text(path, f"{label}.path")
    digest = entry["sha256"]
    require_sha(digest, f"{label}.sha256", allow_pending=False)
    artifact = ROOT / path
    require(artifact.is_file(), f"{label} reference artifact is missing: {path}")
    actual = hashlib.sha256(artifact.read_bytes()).hexdigest()
    require(actual == digest, f"{label} reference artifact hash differs: {path}")


def check_planned_artifact(entry: dict[str, Any], label: str) -> None:
    require(("path" in entry or "path_pattern" in entry) and "sha256" in entry and "status" in entry, f"{label} needs path/path_pattern, sha256 and status")
    if "path_pattern" in entry:
        require_text(entry["path_pattern"], f"{label}.path_pattern")
        viewport_hashes = entry.get("sha256_by_viewport")
        if viewport_hashes is not None:
            require(isinstance(viewport_hashes, dict) and set(viewport_hashes) == set(REQUIRED_VIEWPORTS), f"{label}.sha256_by_viewport must cover all five viewports")
            for viewport, digest in viewport_hashes.items():
                require_sha(digest, f"{label}.sha256_by_viewport[{viewport}]")
    else:
        require(isinstance(entry["path"], str), f"{label}.path must be text")
    require_sha(entry["sha256"], f"{label}.sha256")
    if entry["status"] == "PENDING_MAIN_CAPTURE":
        require(entry["sha256"] is None, f"{label} pending capture cannot claim a hash")
    else:
        require_text(entry["status"], f"{label}.status")
        require(isinstance(entry.get("path") or entry.get("path_pattern"), str), f"{label} needs a path once captured")


def check_region_map(pair: dict[str, Any], family: str) -> None:
    regions = pair.get("region_map")
    require(isinstance(regions, list), f"{family} region_map must be a list")
    names = {item.get("region") for item in regions if isinstance(item, dict)}
    require(names == REQUIRED_CROPS, f"{family} region_map must cover exactly {sorted(REQUIRED_CROPS)}")
    for item in regions:
        require(isinstance(item, dict), f"{family} region_map entries must be objects")
        require_text(item.get("reference_selector"), f"{family} reference selector")
        require_text(item.get("current_selector"), f"{family} current selector")
        matches = item.get("target_selector_matches")
        require(isinstance(matches, list), f"{family} region target_selector_matches must be a list")
        if item["region"] == "native-preview" and family != "MOD-EXPORT":
            require(matches == [], f"{family} native-preview must be an explicit zero-match region")
            proof = item.get("na_proof")
            require(isinstance(proof, dict) and proof.get("match_count") == 0, f"{family} native-preview needs machine N/A proof")
            require_text(proof.get("reason"), f"{family} native-preview N/A reason")
        else:
            require(matches, f"{family} {item['region']} must record target selector matches")


def check_source_pairs(payload: dict[str, Any]) -> None:
    pairs = payload.get("approved_static_source_pairs")
    require(isinstance(pairs, list), "approved_static_source_pairs must be a list")
    require({item.get("id") for item in pairs if isinstance(item, dict)} == set(FAMILIES), "static source pairs must cover MOD-DATA/PROCESS/FIT/EXPORT exactly")
    for pair in pairs:
        family = pair["id"]
        reference = pair.get("reference")
        current = pair.get("current")
        require(isinstance(reference, dict) and isinstance(current, dict), f"{family} needs reference and current source records")
        for key in ("html", "css", "javascript"):
            path = reference.get(key)
            require_text(path, f"{family}.reference.{key}")
            require((ROOT / path).is_file(), f"{family} reference source missing: {path}")
        require_text(reference.get("identity_classification"), f"{family} reference identity classification")
        require_text(current.get("production_component"), f"{family} production component")
        require_text(current.get("event"), f"{family} event")
        require_text(current.get("state_source"), f"{family} state source")
        for key in ("production_component", "state_source"):
            path = current[key]
            if path.startswith("apps/"):
                require((ROOT / path).is_file(), f"{family} current source missing: {path}")
        require_text(current.get("identity_classification"), f"{family} current identity classification")
        originals = reference.get("originals")
        require(isinstance(originals, list) and originals, f"{family} reference originals are required")
        for index, entry in enumerate(originals):
            check_reference_artifact(entry, f"{family}.reference.originals[{index}]")
        for side in ("reference", "current"):
            crops = pair[side].get("crops")
            require(isinstance(crops, list), f"{family}.{side}.crops must be a list")
            require({entry.get("region") for entry in crops} == REQUIRED_CROPS, f"{family}.{side}.crops must cover all required regions")
            for index, entry in enumerate(crops):
                if side == "reference" and entry.get("status") == "APPROVED_STATIC_REFERENCE":
                    require_sha(entry.get("sha256"), f"{family}.reference.crops[{index}].sha256", allow_pending=False)
                else:
                    check_planned_artifact(entry, f"{family}.{side}.crops[{index}]")
        current_originals = current.get("originals")
        require(isinstance(current_originals, list) and len(current_originals) == 2, f"{family} current before/after originals are required")
        require({entry.get("phase") for entry in current_originals} == {"before", "after"}, f"{family} current originals must have before and after")
        for index, entry in enumerate(current_originals):
            check_planned_artifact(entry, f"{family}.current.originals[{index}]")
        differences = pair.get("pre_existing_difference_dispositions")
        require(isinstance(differences, list) and len(differences) >= 3, f"{family} needs explicit pre-existing difference dispositions")
        for item in differences:
            require_text(item.get("classification"), f"{family} difference classification")
            require_text(item.get("disposition"), f"{family} difference disposition")
        check_region_map(pair, family)


def check_state_matrix(payload: dict[str, Any]) -> None:
    matrix = payload.get("capture_plan", {}).get("state_matrix")
    require(isinstance(matrix, list), "capture_plan.state_matrix must be a list")
    by_id = {item.get("id"): item for item in matrix if isinstance(item, dict)}
    require(set(by_id) == EXPECTED_STATE_IDS, "capture state matrix is missing or has unapproved state IDs")
    for state_id, item in by_id.items():
        require_text(item.get("family"), f"{state_id}.family")
        require_text(item.get("route"), f"{state_id}.route")
        viewports = item.get("required_viewports")
        require(isinstance(viewports, list) and viewports, f"{state_id}.required_viewports must be non-empty")
        require(set(viewports) <= set(REQUIRED_VIEWPORTS), f"{state_id} has an unknown viewport")
        matches = item.get("target_selector_matches")
        require(isinstance(matches, list), f"{state_id}.target_selector_matches must be a list")
        if state_id == "materials-browse-lineage-readback":
            proof = item.get("selector_scan")
            require(matches == [] and isinstance(proof, dict) and proof.get("match_count") == 0, f"{state_id} needs zero-match selector proof")
            require_text(proof.get("reason"), f"{state_id} N/A reason")
        elif state_id == "MOD-DATA.normal":
            require(viewports == REQUIRED_VIEWPORTS, f"{state_id} must cover all five viewports")
        elif state_id in NORMAL_STATE_IDS:
            require(viewports == REQUIRED_VIEWPORTS, f"{state_id} must cover all five viewports")
            require(matches, f"{state_id} must prove target selector matches")
        elif state_id == "modeling-alias.normal" or state_id == "modeling-reload-readback":
            require(viewports == REQUIRED_VIEWPORTS, f"{state_id} must cover all five viewports")
            require(matches, f"{state_id} must prove target selector matches")
        else:
            require(viewports == ["1440x900"], f"{state_id} evidence-only state must be captured at 1440x900")
            require(matches, f"{state_id} must prove target selector matches")
        if payload.get("status") == "ACCEPTED_MAIN_VISUAL_AND_RUNTIME":
            require(
                item.get("evidence")
                in {"ACCEPTED_MAIN_CAPTURE", "ACCEPTED_DURABLE_SOURCE_ORACLE_ONLY"},
                f"{state_id} final evidence disposition is invalid",
            )
        else:
            require(
                item.get("evidence") == "PENDING_MAIN_CAPTURE",
                f"{state_id} cannot claim capture acceptance",
            )


def check_runtime_contract(payload: dict[str, Any]) -> None:
    contract = payload.get("runtime_identity_contract")
    require(isinstance(contract, dict), "runtime_identity_contract is required")
    require(contract.get("schema_version") == "cmp.issue-261.m1e4.runtime-identity.v1", "runtime identity schema drifted")
    fields = contract.get("server_returned_fields")
    required_fields = {"material_id", "material_revision_id", "material_revision", "state_id", "state_revision_id", "state_revision", "test_data_id", "test_data_revision_id", "test_data_revision", "process_output_id", "process_output_revision_id", "process_output_sha256", "fit_output_id", "fit_output_revision_id", "fit_output_sha256", "material_model_id", "material_model_revision_id", "material_model_ir_sha256", "solver_card_id", "solver_card_revision_id", "mapping_digest", "native_preview_sha256", "download_sha256"}
    require(isinstance(fields, dict) and set(fields) == required_fields, "runtime identity server_returned_fields must cover every ID/revision/digest/resource field")
    require(all(value is None for value in fields.values()), "writer may not freeze runtime UUIDs or digests")
    resources = contract.get("resources")
    require(isinstance(resources, list) and len(resources) >= 10, "runtime identity must list every read-back API resource")
    for resource in resources:
        require_text(resource.get("name"), "runtime resource name")
        require_text(resource.get("method"), "runtime resource method")
        require_text(resource.get("url_template"), "runtime resource URL")
        require(resource.get("read_back_assertion") is not None, "runtime resources need exact read-back assertions")
    assertions = contract.get("exact_within_run_assertions")
    require(isinstance(assertions, list) and len(assertions) >= 12, "runtime identity needs exact within-run/read-back assertions")
    accepted = payload.get("status") == "ACCEPTED_MAIN_VISUAL_AND_RUNTIME"
    for assertion in assertions:
        require_text(assertion.get("id"), "runtime assertion id")
        require_text(assertion.get("rule"), "runtime assertion rule")
        expected = "PASS_MAIN_RUNTIME_READBACK" if accepted else "PENDING_MAIN"
        require(assertion.get("result") == expected, "runtime assertion disposition drifted")
    forbidden = contract.get("forbidden_fallbacks")
    require(isinstance(forbidden, list) and {"latest", "first", "global-output", "other-session"}.issubset(set(forbidden)), "runtime contract must prohibit all fallback classes")


def check_quality_contract(payload: dict[str, Any]) -> None:
    interaction = payload.get("interaction_contract")
    require(isinstance(interaction, dict), "interaction_contract is required")
    require(isinstance(interaction.get("tab_order"), list) and len(interaction["tab_order"]) >= 6, "keyboard tab order is incomplete")
    require(isinstance(interaction.get("action_reachability"), list) and len(interaction["action_reachability"]) >= 8, "keyboard action reachability is incomplete")
    require(isinstance(interaction.get("focus_preservation"), list) and len(interaction["focus_preservation"]) >= 4, "focus preservation records are incomplete")
    require(interaction.get("page_horizontal_overflow") == 0, "page overflow contract must require zero")
    require(interaction.get("console_error_count") == 0, "console error contract must require zero")
    synthesis = payload.get("design_synthesis")
    require(isinstance(synthesis, dict), "design_synthesis is required")
    accepted = payload.get("status") == "ACCEPTED_MAIN_VISUAL_AND_RUNTIME"
    expected_axis = "PASS_MAIN" if accepted else "PENDING_MAIN_VISUAL_REVIEW"
    for axis in ("information_hierarchy", "engineering_task_flow", "responsive_wide_screen_composition"):
        require(synthesis.get(axis) == expected_axis, f"{axis} disposition drifted")
    storybook = payload.get("storybook_contract")
    require(isinstance(storybook, dict), "storybook_contract is required")
    empty_series = storybook.get("EngineeringCurvePlot_EmptyCompatibleSeries")
    require(isinstance(empty_series, dict), "EngineeringCurvePlot EmptyCompatibleSeries contract is required")
    require(empty_series.get("story") == "EngineeringCurvePlot EmptyCompatibleSeries", "Storybook story identity drifted")
    require(empty_series.get("viewport") == "1440x900" and empty_series.get("device_pixel_ratio") == 1 and empty_series.get("browser_zoom_percent") == 100, "Storybook EmptyCompatibleSeries must be exactly 1440x900 at DPR1/100%")
    expected_storybook = "PASS_MAIN_PIXEL_EXACT" if accepted else "PENDING_MAIN_CAPTURE"
    require(empty_series.get("evidence") == expected_storybook, "Storybook story disposition drifted")
    if accepted:
        declared_digests: list[str] = []
        for phase in ("before", "after"):
            path_value = empty_series.get(f"{phase}_path")
            digest_value = empty_series.get(f"{phase}_sha256")
            require_text(path_value, f"Storybook {phase} path")
            require_sha(digest_value, f"Storybook {phase} SHA-256", allow_pending=False)
            artifact = ROOT / path_value
            require(artifact.is_file(), f"Storybook {phase} artifact is missing: {path_value}")
            actual_digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
            require(actual_digest == digest_value, f"Storybook {phase} SHA-256 differs")
            declared_digests.append(digest_value)
        require(len(set(declared_digests)) == 1, "Storybook before/after bytes are not pixel-exact")


def check_q_matrix(payload: dict[str, Any]) -> None:
    records = payload.get("quality_review", {}).get("Q01_Q20")
    require(isinstance(records, list), "quality_review.Q01_Q20 must be a list")
    by_id = {item.get("id"): item for item in records if isinstance(item, dict)}
    require(set(by_id) == {f"Q{index:02d}" for index in range(1, 21)}, "Q01..Q20 records are required exactly once")
    for item in records:
        require_text(item.get("applicability_rule"), f"{item['id']} applicability rule")
        require(isinstance(item.get("evidence"), list), f"{item['id']} evidence must be an array")
        allowed = {"PASS_MAIN", "EXPLICIT_NA"} if payload.get("status") == "ACCEPTED_MAIN_VISUAL_AND_RUNTIME" else {"PENDING_MAIN", "EXPLICIT_NA"}
        require(item.get("disposition") in allowed, f"{item['id']} disposition is invalid for the manifest lifecycle")
        if item["disposition"] == "EXPLICIT_NA":
            require(item.get("selector_scan", {}).get("match_count") == 0, f"{item['id']} N/A needs zero selector matches")
            require_text(item.get("selector_scan", {}).get("reason"), f"{item['id']} N/A reason")


def load_manifest(path: Path) -> dict[str, Any]:
    payload = read_json(path)
    require(payload.get("issue") == "#261", "manifest is not the bounded #261 contract")
    require(payload.get("unit") == "M1E4-modeling-core-stage-ownership", "manifest unit drifted")
    require(payload.get("contract_schema") == "cmp.issue-261.m1e4.visual-evidence.v5", "manifest must use approved packet v5 schema")
    require(payload.get("viewports") == REQUIRED_VIEWPORTS, "manifest viewport matrix drifted")
    require(payload.get("browser_zoom_percent") == 100 and payload.get("device_pixel_ratio") == 1, "manifest must pin browser zoom 100% and DPR 1")
    require(payload.get("capture_plan", {}).get("required_crops") == sorted(REQUIRED_CROPS), "manifest crop contract drifted")
    check_state_matrix(payload)
    check_source_pairs(payload)
    check_runtime_contract(payload)
    check_quality_contract(payload)
    check_q_matrix(payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--check-only", action="store_true", help="validate the contract without touching evidence files")
    args = parser.parse_args()
    payload = load_manifest(args.manifest.resolve())
    matrix = payload["capture_plan"]["state_matrix"]
    accepted = sum(item.get("evidence") == "ACCEPTED_MAIN_CAPTURE" for item in matrix)
    source_only = sum(item.get("evidence") == "ACCEPTED_DURABLE_SOURCE_ORACLE_ONLY" for item in matrix)
    pending = sum(item.get("evidence") == "PENDING_MAIN_CAPTURE" for item in matrix)
    print(f"{payload['unit']}: manifest PASS; schema={payload['contract_schema']}; states={len(matrix)}; accepted={accepted}; source-only={source_only}; pending={pending}")
    print("required viewports:", ", ".join(payload["viewports"]))
    print("required crops:", ", ".join(payload["capture_plan"]["required_crops"]))
    print("static source pairs: MOD-DATA, MOD-PROCESS, MOD-FIT, MOD-EXPORT")
    print(f"manifest lifecycle: {payload['status']}")
    if not args.check_only:
        print("No capture was started. Main must run the approved disposable Compose/browser workflow.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

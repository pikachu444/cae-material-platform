from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import replace
from itertools import permutations
from pathlib import Path
from typing import Any, cast
from uuid import UUID

import pytest
from cmp.modules.catalog.domain.schema_bundles import (
    CatalogSnapshot,
    CatalogStateObject,
    PlanDisposition,
    SchemaBundlePlan,
    SourceArtifactIdentity,
    build_schema_bundle_plan,
)
from cmp.modules.identity_access.domain.authorization import DataClassification
from cmp.shared.domain.revisions import canonical_json_bytes, content_sha256
from jsonschema import Draft202012Validator, FormatChecker

PROJECT_ROOT = Path(__file__).parents[2]
ORG = UUID("20400000-0000-4000-8000-000000000001")
PROJECT = UUID("20400000-0000-4000-8000-000000000002")
ARTIFACT = UUID("20400000-0000-4000-8000-000000000003")


def _fixture(name: str) -> dict[str, Any]:
    return cast(
        dict[str, Any],
        json.loads(
            (
                PROJECT_ROOT
                / "contracts"
                / "examples"
                / "positive"
                / f"schema-definition-bundle-{name}.json"
            ).read_text(encoding="utf-8")
        ),
    )


def _raw(value: dict[str, Any]) -> bytes:
    return canonical_json_bytes(value)


def _source(raw: bytes, *, digest: str | None = None) -> SourceArtifactIdentity:
    return SourceArtifactIdentity(
        ARTIFACT,
        ORG,
        PROJECT,
        DataClassification.INTERNAL,
        "application/vnd.cmp.catalog-schema-definition-bundle+json",
        len(raw),
        digest or content_sha256({"bytes": raw.hex()}),
    )


def _plan(value: dict[str, Any], snapshot: CatalogSnapshot | None = None) -> SchemaBundlePlan:
    raw = _raw(value)
    return build_schema_bundle_plan(
        source=_source(raw),
        raw_bytes=raw,
        snapshot=snapshot or CatalogSnapshot(ORG, PROJECT, ()),
        organization_id=ORG,
        project_id=PROJECT,
        classification_allowed=lambda _: True,
    )


def _rechecksum(entry: dict[str, Any]) -> None:
    entry["schema_sha256"] = content_sha256(entry["schema"])


def test_one_and_many_record_bundles_project_without_fixed_cardinality() -> None:
    one = _plan(_fixture("one"))
    many = _plan(_fixture("many"))

    assert one.valid
    assert one.bundle is not None
    assert one.bundle.dependency_order == ("materials",)
    assert many.valid
    assert many.bundle is not None
    assert many.bundle.dependency_order == ("materials", "tensile_tests", "curves")
    assert [action.external_key for action in many.actions if action.target_type == "table"] == [
        "materials",
        "tensile_tests",
        "curves",
    ]
    assert {
        action.external_key for action in many.actions if action.target_type == "link_type"
    } == {
        "curve_tensile_test",
        "tensile_test_material",
    }

    expanded = _fixture("one")
    template = expanded["record_schemas"][0]
    expanded["record_schemas"] = []
    for index in range(17):
        entry = deepcopy(template)
        entry["key"] = f"synthetic_record_{index}"
        entry["name"] = f"Synthetic record {index}"
        entry["schema"]["$id"] = f"urn:cmp:catalog-schema:synthetic_record_{index}:1.0.0"
        _rechecksum(entry)
        expanded["record_schemas"].append(entry)

    expanded_plan = _plan(expanded)

    assert expanded_plan.valid
    assert expanded_plan.bundle is not None
    assert expanded_plan.bundle.summary()["record_schema_count"] == 17
    assert len([action for action in expanded_plan.actions if action.target_type == "table"]) == 17


def test_repeat_plan_is_byte_equivalent_and_has_the_same_fingerprint() -> None:
    document = _fixture("many")

    first = _plan(document)
    second = _plan(document)

    assert first.plan_fingerprint == second.plan_fingerprint
    assert canonical_json_bytes(first.canonical()) == canonical_json_bytes(second.canonical())


@pytest.mark.parametrize("unit", ("degC", "kg/m^3", "psi", "dimensionless"))
def test_x_unit_handoff_requires_a_stable_common_unit_identifier(unit: str) -> None:
    document = _fixture("one")
    entry = document["record_schemas"][0]
    entry["schema"]["properties"]["youngs_modulus"]["x-unit"] = unit
    _rechecksum(entry)

    result = _plan(document)

    assert not result.valid
    diagnostic = next(
        item for item in result.diagnostics if item.location.endswith("/x-unit")
    )
    assert diagnostic.code == "CMP-SCHEMA-BUNDLE-0002"
    assert "stable canonical" in diagnostic.message
    assert result.canonical()["write_set"] == []


@pytest.mark.parametrize("order", tuple(permutations(range(3))))
def test_record_entry_order_does_not_change_dependency_or_action_semantics(
    order: tuple[int, ...],
) -> None:
    original = _fixture("many")
    reordered = deepcopy(original)
    reordered["record_schemas"] = [reordered["record_schemas"][index] for index in order]

    first = _plan(original)
    second = _plan(reordered)

    assert first.bundle is not None and second.bundle is not None
    assert first.bundle.dependency_order == second.bundle.dependency_order
    assert [action.canonical() for action in first.actions] == [
        action.canonical() for action in second.actions
    ]


def test_negative_reference_key_pointer_cycle_version_and_extension_cases() -> None:
    cases: list[tuple[dict[str, Any], str]] = []

    external = _fixture("many")
    external_entry = external["record_schemas"][2]
    external_entry["schema"]["properties"]["material_id"]["$ref"] = (
        "https://example.invalid/material.schema.json#/properties/record_id"
    )
    _rechecksum(external_entry)
    cases.append((external, "CMP-SCHEMA-BUNDLE-0007"))

    missing = _fixture("many")
    missing_entry = missing["record_schemas"][2]
    missing_entry["schema"]["properties"]["material_id"]["$ref"] = (
        "urn:cmp:catalog-schema:missing:1.0.0#/properties/record_id"
    )
    _rechecksum(missing_entry)
    cases.append((missing, "CMP-SCHEMA-BUNDLE-0008"))

    bad_pointer = _fixture("many")
    bad_pointer_entry = bad_pointer["record_schemas"][2]
    bad_pointer_entry["schema"]["properties"]["material_id"]["$ref"] = (
        "urn:cmp:catalog-schema:materials:1.0.0#/properties/missing"
    )
    _rechecksum(bad_pointer_entry)
    cases.append((bad_pointer, "CMP-SCHEMA-BUNDLE-0009"))

    duplicate = _fixture("many")
    duplicate["record_schemas"].append(deepcopy(duplicate["record_schemas"][1]))
    cases.append((duplicate, "CMP-SCHEMA-BUNDLE-0006"))

    unsupported = _fixture("one")
    unsupported["contract_version"] = "2.0.0"
    cases.append((unsupported, "CMP-SCHEMA-BUNDLE-0003"))

    unknown_extension = _fixture("one")
    unknown_entry = unknown_extension["record_schemas"][0]
    unknown_entry["schema"]["properties"]["record_id"]["x-plugin"] = "run"
    _rechecksum(unknown_entry)
    cases.append((unknown_extension, "CMP-SCHEMA-BUNDLE-0010"))

    checksum_mismatch = _fixture("one")
    checksum_mismatch["record_schemas"][0]["schema_sha256"] = "0" * 64
    cases.append((checksum_mismatch, "CMP-SCHEMA-BUNDLE-0005"))

    invalid_stable_key = _fixture("one")
    invalid_stable_key["record_schemas"][0]["key"] = "Invalid Key"
    cases.append((invalid_stable_key, "CMP-SCHEMA-BUNDLE-0002"))

    trailing_separator = _fixture("one")
    trailing_separator["catalog"]["database"]["key"] = "synthetic_database_"
    cases.append((trailing_separator, "CMP-SCHEMA-BUNDLE-0002"))

    for keyword, value in (
        ("$id", "urn:cmp:catalog-schema:nested:1.0.0"),
        ("$schema", "https://json-schema.org/draft/2020-12/schema"),
    ):
        nested_scope = _fixture("one")
        nested_entry = nested_scope["record_schemas"][0]
        nested_entry["schema"]["properties"]["active"][keyword] = value
        _rechecksum(nested_entry)
        cases.append((nested_scope, "CMP-SCHEMA-BUNDLE-0010"))

    cycle = _fixture("many")
    materials = cycle["record_schemas"][1]
    materials["schema"]["properties"]["test_id"] = {
        "$ref": "urn:cmp:catalog-schema:tensile_tests:1.0.0#/properties/test_id",
        "title": "Test",
        "x-reference": {
            "link_key": "material_tensile_test",
            "forward_label": "test",
            "reverse_label": "materials",
            "source_cardinality": "many",
            "target_cardinality": "one",
        },
    }
    _rechecksum(materials)
    cases.append((cycle, "CMP-SCHEMA-BUNDLE-0011"))

    for document, expected_code in cases:
        result = _plan(document)
        assert not result.valid
        assert result.actions[0].disposition is PlanDisposition.ERROR
        assert expected_code in {item.code for item in result.diagnostics}
        assert all(item.location is not None and item.remediation for item in result.diagnostics)


def test_duplicate_json_members_are_rejected_without_precedence() -> None:
    raw = b'{"contract_version":"1.0.0","contract_version":"2.0.0"}'

    result = build_schema_bundle_plan(
        source=_source(raw),
        raw_bytes=raw,
        snapshot=CatalogSnapshot(ORG, PROJECT, ()),
        organization_id=ORG,
        project_id=PROJECT,
        classification_allowed=lambda _: True,
    )

    assert not result.valid
    assert result.diagnostics[0].code == "CMP-SCHEMA-BUNDLE-0006"


def test_nested_id_negative_fixture_matches_runtime_scope_rejection() -> None:
    document = cast(
        dict[str, Any],
        json.loads(
            (
                PROJECT_ROOT
                / "contracts/examples/negative/schema-definition-bundle-nested-id.json"
            ).read_text(encoding="utf-8")
        ),
    )

    result = _plan(document)

    assert not result.valid
    assert {item.code for item in result.diagnostics} == {"CMP-SCHEMA-BUNDLE-0010"}
    assert any(item.location.endswith("/active/$id") for item in result.diagnostics)


def test_non_finite_json_number_is_a_repairable_validation_error() -> None:
    raw = _raw(_fixture("one")).replace(b'"minimum":0', b'"minimum":1e400', 1)

    result = build_schema_bundle_plan(
        source=_source(raw),
        raw_bytes=raw,
        snapshot=CatalogSnapshot(ORG, PROJECT, ()),
        organization_id=ORG,
        project_id=PROJECT,
        classification_allowed=lambda _: True,
    )

    assert not result.valid
    assert "CMP-SCHEMA-BUNDLE-0002" in {item.code for item in result.diagnostics}


def test_local_defs_refs_project_and_filesystem_refs_remain_forbidden() -> None:
    local = _fixture("one")
    record = local["record_schemas"][0]
    record["schema"]["$defs"] = {"record_identifier": {"type": "string", "maxLength": 64}}
    record["schema"]["properties"]["record_id"] = {
        "$ref": "#/$defs/record_identifier",
        "title": "Record ID",
        "x-business-key": True,
        "x-indexed": True,
        "x-searchable": True,
    }
    _rechecksum(record)

    result = _plan(local)

    assert result.valid
    record_id = next(
        action
        for action in result.actions
        if action.target_type == "attribute" and action.external_key == "record_id"
    )
    assert record_id.projected is not None
    assert record_id.projected["data_type"] == "text"
    assert record_id.projected["maximum_length"] == 64

    for reference in (
        "../material.schema.json#/properties/record_id",
        "C:\\schemas\\material.json#/properties/record_id",
        "file:///tmp/material.json#/properties/record_id",
    ):
        forbidden = _fixture("many")
        entry = forbidden["record_schemas"][2]
        entry["schema"]["properties"]["material_id"]["$ref"] = reference
        _rechecksum(entry)
        invalid = _plan(forbidden)
        assert not invalid.valid
        assert "CMP-SCHEMA-BUNDLE-0007" in {diagnostic.code for diagnostic in invalid.diagnostics}

    constrained_ref = _fixture("one")
    constrained_entry = constrained_ref["record_schemas"][0]
    constrained_entry["schema"]["$defs"] = {"text": {"type": "string"}}
    constrained_entry["schema"]["properties"]["record_id"] = {
        "$ref": "#/$defs/text",
        "minLength": 3,
    }
    _rechecksum(constrained_entry)
    constrained_plan = _plan(constrained_ref)
    assert not constrained_plan.valid
    assert "CMP-SCHEMA-BUNDLE-0012" in {
        diagnostic.code for diagnostic in constrained_plan.diagnostics
    }

    recursive = _fixture("one")
    recursive_entry = recursive["record_schemas"][0]
    recursive_entry["schema"]["$defs"] = {
        "node": {
            "type": "object",
            "properties": {"child": {"$ref": "#/$defs/node"}},
            "additionalProperties": False,
        }
    }
    recursive_entry["schema"]["properties"]["recursive_node"] = {"$ref": "#/$defs/node"}
    _rechecksum(recursive_entry)
    recursive_plan = _plan(recursive)
    assert not recursive_plan.valid
    assert "CMP-SCHEMA-BUNDLE-0011" in {
        diagnostic.code for diagnostic in recursive_plan.diagnostics
    }


def test_unsafe_shape_and_flattened_key_collision_fail_closed() -> None:
    malformed_type = _fixture("one")
    malformed_entry = malformed_type["record_schemas"][0]
    malformed_entry["schema"]["properties"]["active"]["type"] = [{}, "null"]
    _rechecksum(malformed_entry)
    malformed = _plan(malformed_type)
    assert not malformed.valid
    assert "CMP-SCHEMA-BUNDLE-0002" in {diagnostic.code for diagnostic in malformed.diagnostics}

    missing_id = _fixture("one")
    missing_id_entry = missing_id["record_schemas"][0]
    del missing_id_entry["schema"]["$id"]
    _rechecksum(missing_id_entry)
    missing_id_plan = _plan(missing_id)
    assert not missing_id_plan.valid
    assert "CMP-SCHEMA-BUNDLE-0002" in {
        diagnostic.code for diagnostic in missing_id_plan.diagnostics
    }

    malformed_scope = _fixture("one")
    malformed_scope["scope"]["organization_id"] = 204
    malformed_scope_plan = _plan(malformed_scope)
    assert not malformed_scope_plan.valid
    assert "CMP-SCHEMA-BUNDLE-0002" in {
        diagnostic.code for diagnostic in malformed_scope_plan.diagnostics
    }

    artifact_scope_mismatch = _fixture("one")
    artifact_scope_mismatch["scope"]["classification"] = "confidential"
    artifact_scope_plan = _plan(artifact_scope_mismatch)
    assert not artifact_scope_plan.valid
    assert "CMP-SCHEMA-BUNDLE-0004" in {
        diagnostic.code for diagnostic in artifact_scope_plan.diagnostics
    }

    oversized_title = _fixture("one")
    oversized_title_entry = oversized_title["record_schemas"][0]
    oversized_title_entry["schema"]["properties"]["active"]["title"] = "x" * 201
    _rechecksum(oversized_title_entry)
    oversized_title_plan = _plan(oversized_title)
    assert not oversized_title_plan.valid
    assert "CMP-SCHEMA-BUNDLE-0002" in {
        diagnostic.code for diagnostic in oversized_title_plan.diagnostics
    }

    ignored_structural_keyword = _fixture("one")
    ignored_structural_entry = ignored_structural_keyword["record_schemas"][0]
    ignored_structural_entry["schema"]["properties"]["active"]["properties"] = {}
    _rechecksum(ignored_structural_entry)
    ignored_structural_plan = _plan(ignored_structural_keyword)
    assert not ignored_structural_plan.valid
    assert "CMP-SCHEMA-BUNDLE-0012" in {
        diagnostic.code for diagnostic in ignored_structural_plan.diagnostics
    }

    oversized_generated_layout = _fixture("one")
    oversized_generated_layout["record_schemas"][0]["name"] = "x" * 200
    oversized_layout_plan = _plan(oversized_generated_layout)
    assert not oversized_layout_plan.valid
    assert "CMP-SCHEMA-BUNDLE-0012" in {
        diagnostic.code for diagnostic in oversized_layout_plan.diagnostics
    }

    collision = _fixture("one")
    collision_entry = collision["record_schemas"][0]
    collision_entry["schema"]["properties"].update(
        {
            "a__b": {"type": "string"},
            "a": {
                "type": "object",
                "properties": {"b": {"type": "string"}},
                "additionalProperties": False,
            },
        }
    )
    _rechecksum(collision_entry)
    duplicate = _plan(collision)
    assert not duplicate.valid
    assert "CMP-SCHEMA-BUNDLE-0006" in {diagnostic.code for diagnostic in duplicate.diagnostics}

    too_deep = _fixture("one")
    deep_entry = too_deep["record_schemas"][0]
    node: dict[str, Any] = {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    }
    deep_entry["schema"]["properties"]["deep"] = node
    for index in range(70):
        child: dict[str, Any] = {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        }
        cast(dict[str, Any], node["properties"])[f"level_{index}"] = child
        node = child
    cast(dict[str, Any], node["properties"])["value"] = {"type": "string"}
    _rechecksum(deep_entry)
    deep_result = _plan(too_deep)
    assert not deep_result.valid
    assert "CMP-SCHEMA-BUNDLE-0012" in {diagnostic.code for diagnostic in deep_result.diagnostics}


def test_projection_rejects_constraints_that_existing_catalog_cannot_preserve() -> None:
    uuid_text = _fixture("one")
    uuid_entry = uuid_text["record_schemas"][0]
    uuid_entry["schema"]["properties"]["record_id"]["format"] = "uuid"
    _rechecksum(uuid_entry)
    uuid_plan = _plan(uuid_text)
    assert uuid_plan.valid
    uuid_attribute = next(
        action
        for action in uuid_plan.actions
        if action.target_type == "attribute" and action.external_key == "record_id"
    )
    assert uuid_attribute.projected is not None
    assert uuid_attribute.projected["pattern"] is not None

    required_nullable = _fixture("one")
    nullable_entry = required_nullable["record_schemas"][0]
    nullable_entry["schema"]["required"].append("youngs_modulus")
    _rechecksum(nullable_entry)
    nullable_plan = _plan(required_nullable)
    assert not nullable_plan.valid
    assert "CMP-SCHEMA-BUNDLE-0012" in {diagnostic.code for diagnostic in nullable_plan.diagnostics}

    indexed_boolean = _fixture("one")
    boolean_entry = indexed_boolean["record_schemas"][0]
    boolean_entry["schema"]["properties"]["active"]["x-indexed"] = True
    _rechecksum(boolean_entry)
    boolean_plan = _plan(indexed_boolean)
    assert not boolean_plan.valid
    assert "CMP-SCHEMA-BUNDLE-0012" in {diagnostic.code for diagnostic in boolean_plan.diagnostics}

    oversized_help = _fixture("one")
    help_entry = oversized_help["record_schemas"][0]
    help_entry["schema"]["properties"]["active"]["description"] = "x" * 2001
    _rechecksum(help_entry)
    help_plan = _plan(oversized_help)
    assert not help_plan.valid
    assert "CMP-SCHEMA-BUNDLE-0012" in {diagnostic.code for diagnostic in help_plan.diagnostics}


def _state_from_action(action: Any, index: int) -> CatalogStateObject:
    assert action.projected is not None
    object_id = None if action.target_type == "profile_table_placement" else UUID(int=index * 2 + 1)
    revision_id = (
        None if action.target_type == "profile_table_placement" else UUID(int=index * 2 + 2)
    )
    return CatalogStateObject(
        action.target_type,
        action.external_key,
        action.parent_external_key,
        object_id,
        revision_id,
        content_sha256(action.projected),
        False,
        deepcopy(action.projected),
        classification=DataClassification.INTERNAL,
    )


def test_stale_exact_dependency_pin_plans_a_deterministic_update() -> None:
    document = _fixture("one")
    create_plan = _plan(document)
    states = tuple(
        replace(state, dependency_heads_match=False) if state.target_type == "profile" else state
        for state in (
            _state_from_action(action, index + 1)
            for index, action in enumerate(create_plan.actions)
        )
    )

    result = _plan(document, CatalogSnapshot(ORG, PROJECT, states))
    profile_action = next(action for action in result.actions if action.target_type == "profile")
    database_action = next(action for action in result.actions if action.target_type == "database")

    assert profile_action.disposition is PlanDisposition.UPDATE
    assert profile_action.reason_codes == ("dependency_revision_changes",)
    assert database_action.disposition is PlanDisposition.NO_OP


def test_profile_key_owned_by_another_database_is_an_immutable_conflict() -> None:
    document = _fixture("one")
    create_plan = _plan(document)
    profile_action = next(
        action for action in create_plan.actions if action.target_type == "profile"
    )
    profile_state = _state_from_action(profile_action, 1)
    profile_state = replace(profile_state, parent_external_key="another_database")

    result = _plan(document, CatalogSnapshot(ORG, PROJECT, (profile_state,)))
    planned_profile = next(action for action in result.actions if action.target_type == "profile")

    assert planned_profile.disposition is PlanDisposition.CONFLICT
    assert planned_profile.reason_codes == ("profile_database_conflict",)
    assert not result.valid


def test_existing_identity_with_another_classification_is_a_conflict() -> None:
    document = _fixture("one")
    create_plan = _plan(document)
    table_action = next(action for action in create_plan.actions if action.target_type == "table")
    table_state = replace(
        _state_from_action(table_action, 1),
        classification=DataClassification.CONFIDENTIAL,
    )

    result = _plan(document, CatalogSnapshot(ORG, PROJECT, (table_state,)))
    planned_table = next(action for action in result.actions if action.target_type == "table")

    assert planned_table.disposition is PlanDisposition.CONFLICT
    assert planned_table.reason_codes == ("classification_conflict",)
    assert not result.valid


def test_existing_catalog_yields_create_update_noop_conflict_without_deleting_missing() -> None:
    document = _fixture("one")
    create_plan = _plan(document)
    states = {
        action.external_key: _state_from_action(action, index + 1)
        for index, action in enumerate(create_plan.actions)
        if action.target_type != "layout"
    }
    profile = states["synthetic_materials"]
    profile.content["name"] = "Previous profile name"
    states["youngs_modulus"].content["name"] = "Previous modulus name"
    states["active"].content["data_type"] = "text"
    extra = CatalogStateObject(
        "table",
        "legacy_records",
        None,
        UUID(int=100),
        UUID(int=101),
        "f" * 64,
        True,
        {"key": "legacy_records", "name": "Legacy records", "description": None},
        classification=DataClassification.INTERNAL,
    )
    snapshot = CatalogSnapshot(ORG, PROJECT, (*states.values(), extra))

    result = _plan(document, snapshot)
    dispositions = {action.disposition for action in result.actions}

    assert PlanDisposition.CREATE in dispositions
    assert PlanDisposition.UPDATE in dispositions
    assert PlanDisposition.NO_OP in dispositions
    assert PlanDisposition.CONFLICT in dispositions
    assert not result.valid
    assert not any(action.external_key == "legacy_records" for action in result.actions)
    assert result.canonical()["delete_missing"] is False
    assert result.canonical()["write_set"] == []


def test_plan_response_validates_against_the_public_machine_contract() -> None:
    result = _plan(_fixture("many"))
    schema = json.loads(
        (PROJECT_ROOT / "contracts" / "catalog" / "schema-definition-plan.schema.json").read_text(
            encoding="utf-8"
        )
    )

    errors = list(
        Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(result.canonical())
    )

    assert errors == []

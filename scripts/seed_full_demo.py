"""Prepare the three public synthetic modeling journeys in a clean Docker demo.

The normal ``cmp-demo-seed`` command owns the metal journey.  This companion
uses the same protected HTTP API to create the polymer and elastomer baselines,
then runs their deterministic public processing/calibration fixtures.  It has no
database access and must never be used for production or confidential data.
"""

from __future__ import annotations

import argparse
import math
import os
import time
from collections.abc import Mapping, Sequence
from copy import deepcopy
from typing import Any

import seed_ogden_calibration_demo
import seed_viscoelastic_master_demo
from cmp.apps.demo_seed import DemoApi, DemoSeedError


def _items(response: Mapping[str, Any]) -> list[dict[str, Any]]:
    value = response.get("items")
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _id(value: Mapping[str, Any], key: str) -> str:
    result = value.get(key)
    if not isinstance(result, str) or not result:
        raise DemoSeedError(f"full demo response did not contain {key}")
    return result


def _revision_id(value: Mapping[str, Any]) -> str:
    revision = value.get("current_revision")
    if not isinstance(revision, Mapping):
        raise DemoSeedError("full demo response did not contain current_revision")
    return _id(revision, "id")


def _content(value: Mapping[str, Any]) -> Mapping[str, Any]:
    direct_content = value.get("content")
    if isinstance(direct_content, Mapping):
        return direct_content
    revision = value.get("current_revision")
    content = revision.get("content") if isinstance(revision, Mapping) else None
    return content if isinstance(content, Mapping) else {}


def _find_by_content(
    values: Sequence[Mapping[str, Any]], key: str, expected: object
) -> dict[str, Any] | None:
    return next((dict(value) for value in values if _content(value).get(key) == expected), None)


def _revision_hash(value: Mapping[str, Any]) -> str:
    revision = value.get("current_revision")
    if not isinstance(revision, Mapping):
        raise DemoSeedError("full demo response did not contain current_revision")
    return _id(revision, "content_hash")


def _revision_etag(value: Mapping[str, Any]) -> str:
    revision = value.get("current_revision")
    if not isinstance(revision, Mapping):
        raise DemoSeedError("full demo response did not contain current_revision")
    revision_no = revision.get("revision_no")
    if not isinstance(revision_no, int):
        raise DemoSeedError("full demo response did not contain a revision number")
    return f'"revision:{revision_no}:sha256:{_revision_hash(value)}"'


def _ensure_catalog_binding(
    api: DemoApi,
    *,
    material: Mapping[str, Any],
    workflow_nodes: Sequence[Mapping[str, str]],
) -> dict[str, str]:
    """Expose the domain Material through the configurable Catalog Explorer."""

    tables = _items(api.get("/catalog/tables"))
    table = _find_by_content(tables, "key", "demo_material_records")
    if table is None:
        table = api.post(
            "/catalog/tables",
            {
                "classification": "internal",
                "content": {
                    "key": "demo_material_records",
                    "name": "Demo Material Records",
                    "description": (
                        "Configurable Catalog projection of the synthetic demo Materials."
                    ),
                },
                "change_reason": "Create the configurable Catalog table used by the clean demo.",
            },
        )
    table_id = _id(table, "table_id")
    table_revision_id = _revision_id(table)

    attributes = _items(api.get(f"/catalog/tables/{table_id}/attributes"))
    attribute = _find_by_content(attributes, "key", "material_code")
    if attribute is None:
        attribute = api.post(
            f"/catalog/tables/{table_id}/attributes",
            {
                "content": {
                    "table_revision_id": table_revision_id,
                    "key": "material_code",
                    "name": "Material code",
                    "data_type": "text",
                    "required": True,
                    "help_text": "Stable user-facing code for this synthetic demonstration.",
                },
                "change_reason": "Add the demo Material code attribute without a DB migration.",
            },
        )

    def ensure_attribute(
        key: str,
        name: str,
        data_type: str,
        *,
        quantity_semantics: str | None = None,
        normalized_unit: str | None = None,
        allowed_values: Sequence[str] = (),
        minimum_number: float | None = None,
        maximum_number: float | None = None,
    ) -> dict[str, Any]:
        existing = _find_by_content(attributes, "key", key)
        if existing is not None:
            return existing
        content: dict[str, Any] = {
            "table_revision_id": table_revision_id,
            "key": key,
            "name": name,
            "data_type": data_type,
            "required": False,
            "help_text": f"Synthetic demo {name.lower()} used in the product datasheet.",
        }
        if quantity_semantics is not None:
            content["quantity_semantics"] = quantity_semantics
        if normalized_unit is not None:
            content["normalized_unit"] = normalized_unit
        if allowed_values:
            content["allowed_values"] = list(allowed_values)
        if minimum_number is not None:
            content["minimum_number"] = minimum_number
        if maximum_number is not None:
            content["maximum_number"] = maximum_number
        created = api.post(
            f"/catalog/tables/{table_id}/attributes",
            {
                "content": content,
                "change_reason": f"Add the {name} demo datasheet Attribute.",
            },
        )
        attributes.append(created)
        return created

    attribute_by_key = {
        "material_code": attribute,
        "material_family": ensure_attribute(
            "material_family",
            "Material family",
            "discrete",
            allowed_values=(
                "Steel",
                "Material state",
                "Test data",
                "Processing",
                "Material model",
                "Neutral material",
                "Solver card",
                "Release",
            ),
        ),
        "manufacturer": ensure_attribute("manufacturer", "Manufacturer", "text"),
        "grade": ensure_attribute("grade", "Grade", "text"),
        "density": ensure_attribute(
            "density",
            "Density",
            "number",
            quantity_semantics="mass.density",
            normalized_unit="kg/m^3",
            minimum_number=0,
        ),
        "youngs_modulus": ensure_attribute(
            "youngs_modulus",
            "Young's modulus",
            "number",
            quantity_semantics="modulus.elastic.young",
            normalized_unit="Pa",
            minimum_number=0,
        ),
        "poisson_ratio": ensure_attribute(
            "poisson_ratio",
            "Poisson's ratio",
            "number",
            quantity_semantics="ratio.poisson",
            normalized_unit="1",
            minimum_number=0,
            maximum_number=0.5,
        ),
        "yield_stress": ensure_attribute(
            "yield_stress",
            "Yield stress",
            "number",
            quantity_semantics="stress.yield",
            normalized_unit="Pa",
            minimum_number=0,
        ),
    }

    layouts = _items(api.get(f"/catalog/tables/{table_id}/layouts"))
    if not any(item.get("name") == "Material overview" for item in layouts):
        sections = {
            "material_code": "Identity",
            "material_family": "Identity",
            "manufacturer": "Identity",
            "grade": "Identity",
            "density": "Physical properties",
            "youngs_modulus": "Elastic properties",
            "poisson_ratio": "Elastic properties",
            "yield_stress": "Plasticity",
        }
        api.post(
            f"/catalog/tables/{table_id}/layouts",
            {
                "table_revision_id": table_revision_id,
                "name": "Material overview",
                "description": "Identity, physical, elastic and plastic properties for CAE use.",
                "items": [
                    {
                        "attribute_definition_id": _id(
                            attribute_by_key[key], "attribute_definition_id"
                        ),
                        "attribute_definition_revision_id": _revision_id(attribute_by_key[key]),
                        "section": section,
                        "ordinal": ordinal,
                    }
                    for ordinal, (key, section) in enumerate(sections.items())
                ],
                "change_reason": "Create the product Material overview datasheet Layout.",
            },
        )

    def text_value(key: str, value: str) -> dict[str, Any]:
        definition = attribute_by_key[key]
        return {
            "data_type": (
                "discrete" if _content(definition).get("data_type") == "discrete" else "text"
            ),
            "attribute_definition_id": _id(definition, "attribute_definition_id"),
            "attribute_definition_revision_id": _revision_id(definition),
            "value": value,
        }

    def number_value(
        key: str,
        original_value: str,
        original_unit: str,
        normalized_value: str,
    ) -> dict[str, Any]:
        definition = attribute_by_key[key]
        content = _content(definition)
        return {
            "data_type": "number",
            "attribute_definition_id": _id(definition, "attribute_definition_id"),
            "attribute_definition_revision_id": _revision_id(definition),
            "original_value": original_value,
            "original_unit_string": original_unit,
            "normalized_value": normalized_value,
            "normalized_unit": content["normalized_unit"],
            "quantity_semantics": content["quantity_semantics"],
        }

    material_values = [
        text_value(
            "material_code",
            str(_content(material).get("material_code") or "CMP-DEMO-DP780"),
        ),
        text_value("material_family", "Steel"),
        text_value("manufacturer", "CMP Synthetic Materials"),
        text_value("grade", "DP780 dual-phase sheet"),
        number_value("density", "7.85", "g/cm^3", "7850"),
        number_value("youngs_modulus", "210000", "MPa", "210000000000"),
        number_value("poisson_ratio", "0.30", "1", "0.30"),
        number_value("yield_stress", "560", "MPa", "560000000"),
    ]

    folders = _items(api.get(f"/catalog/tables/{table_id}/folders"))

    def ensure_folder(
        name: str,
        description: str,
        parent: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        parent_id = _id(parent, "folder_id") if parent is not None else None
        candidates = [
            item
            for item in folders
            if _content(item).get("name") == name
            and _content(item).get("parent_folder_id") == parent_id
        ]
        existing = max(
            candidates,
            key=lambda item: str(item.get("current_revision", {}).get("created_at", "")),
            default=None,
        )
        if existing is not None:
            return existing
        created = api.post(
            f"/catalog/tables/{table_id}/folders",
            {
                "classification": "internal",
                "content": {
                    "table_revision_id": table_revision_id,
                    "name": name,
                    "description": description,
                    "parent_folder_id": parent_id,
                    "parent_folder_revision_id": (
                        _revision_id(parent) if parent is not None else None
                    ),
                },
                "change_reason": f"Create the {name} Contents Tree folder.",
            },
        )
        folders.append(created)
        return created

    material_library = ensure_folder(
        "Material Library",
        "Approved and working material records arranged by engineering family.",
    )
    metals = ensure_folder(
        "Metals",
        "Metal material families and their governed states.",
        material_library,
    )
    steels = ensure_folder(
        "Steels",
        "Steel grades available for product design and CAE use.",
        metals,
    )
    dp780_folder = ensure_folder(
        "DP780 Dual-Phase Steel",
        "Synthetic DP780 reference material and state records.",
        steels,
    )
    test_data_folder = ensure_folder(
        "Test Data",
        "Source tests and normalized test documents.",
    )
    tensile_folder = ensure_folder(
        "Tensile",
        "Uniaxial tensile evidence linked to material revisions.",
        test_data_folder,
    )
    models_and_cards = ensure_folder(
        "Models & Cards",
        "Processed data, neutral models and solver-native deliverables.",
    )
    elastoplastic_folder = ensure_folder(
        "Elastoplastic",
        "Metal elastoplastic processing, models and solver cards.",
        models_and_cards,
    )

    def place_record(
        record_to_place: Mapping[str, Any],
        folder: Mapping[str, Any],
        values: Sequence[Mapping[str, Any]] | None = None,
    ) -> dict[str, Any]:
        content = dict(_content(record_to_place))
        folder_id = _id(folder, "folder_id")
        folder_revision_id = _revision_id(folder)
        already_placed = (
            content.get("folder_id") == folder_id
            and content.get("folder_revision_id") == folder_revision_id
        )
        current_values = content.get("values")
        values_match = values is None or (
            isinstance(current_values, list)
            and sorted(current_values, key=lambda item: str(item["attribute_definition_id"]))
            == sorted(
                [dict(item) for item in values],
                key=lambda item: str(item["attribute_definition_id"]),
            )
        )
        if already_placed and values_match:
            return dict(record_to_place)
        content["folder_id"] = folder_id
        content["folder_revision_id"] = folder_revision_id
        if values is not None:
            content["values"] = list(values)
        return api.post(
            f"/catalog/records/{_id(record_to_place, 'record_id')}/revisions",
            {
                "content": content,
                "change_reason": (
                    f"Place the record in the {_content(folder).get('name')!s} "
                    "Contents Tree folder."
                ),
            },
            headers={"If-Match": _revision_etag(record_to_place)},
        )

    material_content = _content(material)
    material_code = str(material_content.get("material_code") or "CMP-DEMO-DP780")
    subsets = _items(api.get(f"/catalog/tables/{table_id}/subsets"))
    workflow_subset = next(
        (item for item in subsets if item.get("name") == "DP780 workflow records"),
        None,
    )
    if workflow_subset is None:
        workflow_subset = api.post(
            f"/catalog/tables/{table_id}/subsets",
            {
                "table_revision_id": table_revision_id,
                "name": "DP780 workflow records",
                "description": (
                    "Reusable Explorer search for the exact clean-demo Material workflow."
                ),
                "filter_definition": {
                    "text": "DP780",
                    "folder_id": None,
                    "discrete_filters": {},
                    "number_attribute_id": None,
                    "number_minimum": None,
                    "number_maximum": None,
                },
                "change_reason": "Seed the reusable clean-demo Explorer Subset.",
            },
        )
    searched = api.post(
        "/catalog/records:search",
        {"table_id": table_id, "text": material_code, "limit": 20},
    )
    record = next(
        (item for item in _items(searched) if _content(item).get("external_key") == material_code),
        None,
    )
    if record is None:
        record = api.post(
            f"/catalog/tables/{table_id}/records",
            {
                "classification": "internal",
                "content": {
                    "table_revision_id": table_revision_id,
                    "name": str(material_content.get("name") or material_code),
                    "external_key": material_code,
                    "description": "Revision-pinned Catalog entry for the clean product demo.",
                    "folder_id": _id(dp780_folder, "folder_id"),
                    "folder_revision_id": _revision_id(dp780_folder),
                    "values": material_values,
                },
                "change_reason": "Create the configurable Catalog record for the demo Material.",
            },
        )
    else:
        record = place_record(record, dp780_folder, material_values)
    record_id = _id(record, "record_id")
    record_revision_id = _revision_id(record)
    binding_path = f"/catalog/records/{record_id}/revisions/{record_revision_id}/domain-binding"
    try:
        binding = api.get(binding_path)
    except DemoSeedError:
        binding = api.post(
            binding_path,
            {
                "kind": "material",
                "object_id": _id(material, "material_id"),
                "revision_id": _revision_id(material),
            },
        )
    records_by_key: dict[str, dict[str, Any]] = {material_code: record}
    node_folders = {
        "material_state": dp780_folder,
        "test_data": tensile_folder,
        "processing_output": elastoplastic_folder,
        "material_model": elastoplastic_folder,
        "neutral_material": elastoplastic_folder,
        "solver_card": elastoplastic_folder,
        "neutral_solver_card": elastoplastic_folder,
        "release": models_and_cards,
    }
    for node in workflow_nodes:
        external_key = node["external_key"]
        family_by_kind = {
            "material_state": "Material state",
            "test_data": "Test data",
            "processing_output": "Processing",
            "material_model": "Material model",
            "neutral_material": "Neutral material",
            "solver_card": "Solver card",
            "neutral_solver_card": "Solver card",
            "release": "Release",
        }
        node_values = [
            text_value("material_code", external_key),
            text_value("material_family", family_by_kind.get(node["kind"], "Release")),
        ]
        node_search = api.post(
            "/catalog/records:search",
            {"table_id": table_id, "text": external_key, "limit": 20},
        )
        node_record = next(
            (
                item
                for item in _items(node_search)
                if _content(item).get("external_key") == external_key
            ),
            None,
        )
        if node_record is None:
            node_folder = node_folders.get(node["kind"], models_and_cards)
            node_record = api.post(
                f"/catalog/tables/{table_id}/records",
                {
                    "classification": "internal",
                    "content": {
                        "table_revision_id": table_revision_id,
                        "name": node["name"],
                        "external_key": external_key,
                        "description": "Exact governed node in the clean demo Workflow Explorer.",
                        "folder_id": _id(node_folder, "folder_id"),
                        "folder_revision_id": _revision_id(node_folder),
                        "values": node_values,
                    },
                    "change_reason": f"Create the clean demo {node['kind']} workflow node.",
                },
            )
        else:
            node_record = place_record(
                node_record,
                node_folders.get(node["kind"], models_and_cards),
                node_values,
            )
        node_record_id = _id(node_record, "record_id")
        node_record_revision_id = _revision_id(node_record)
        node_binding_path = (
            f"/catalog/records/{node_record_id}/revisions/{node_record_revision_id}/domain-binding"
        )
        try:
            api.get(node_binding_path)
        except DemoSeedError:
            api.post(
                node_binding_path,
                {
                    "kind": node["kind"],
                    "object_id": node["object_id"],
                    "revision_id": node["revision_id"],
                },
            )
        records_by_key[external_key] = node_record

    link_type = next(
        (
            item
            for item in _items(api.get("/catalog/link-types"))
            if _content(item).get("key") == "demo_workflow_next"
        ),
        None,
    )
    if link_type is None:
        link_type = api.post(
            "/catalog/link-types",
            {
                "classification": "internal",
                "content": {
                    "key": "demo_workflow_next",
                    "name": "Clean demo workflow next",
                    "source_table_id": table_id,
                    "source_table_revision_id": table_revision_id,
                    "target_table_id": table_id,
                    "target_table_revision_id": table_revision_id,
                    "forward_label": "produces next governed revision",
                    "reverse_label": "was produced from exact revision",
                    "source_cardinality": "many",
                    "target_cardinality": "many",
                    "description": "Task-oriented exact-revision projection for the clean demo.",
                },
                "change_reason": "Create the clean demo workflow Link Type.",
            },
        )
    link_type_id = _id(link_type, "link_type_id")
    link_type_revision_id = _revision_id(link_type)
    for node in workflow_nodes:
        source = records_by_key[node["parent_external_key"]]
        target = records_by_key[node["external_key"]]
        source_id = _id(source, "record_id")
        source_revision_id = _revision_id(source)
        target_id = _id(target, "record_id")
        desired_content = {
            "link_type_id": link_type_id,
            "link_type_revision_id": link_type_revision_id,
            "source_record_id": source_id,
            "source_record_revision_id": source_revision_id,
            "target_record_id": target_id,
            "target_record_revision_id": _revision_id(target),
            "active": True,
            "note": "Clean demo exact-revision product flow.",
        }
        linked = _items(api.get(f"/catalog/records/{source_id}/links?include_inactive=true"))
        existing_link = next(
            (
                item
                for item in linked
                if isinstance(item.get("target"), Mapping)
                and item["target"].get("record_id") == target_id
                and _content(item).get("link_type_id") == link_type_id
            ),
            None,
        )
        if existing_link is None:
            api.post(
                "/catalog/record-links",
                {
                    "classification": "internal",
                    "content": desired_content,
                    "change_reason": "Connect the next exact clean-demo workflow revision.",
                },
            )
        elif dict(_content(existing_link)) != desired_content:
            api.post(
                f"/catalog/record-links/{_id(existing_link, 'record_link_id')}/revisions",
                {
                    "content": desired_content,
                    "change_reason": (
                        "Advance the clean demo link to the reorganized exact record revisions."
                    ),
                },
                headers={"If-Match": _revision_etag(existing_link)},
            )
    return {
        "catalog_table_id": table_id,
        "catalog_subset_id": _id(workflow_subset, "subset_id"),
        "catalog_record_id": record_id,
        "catalog_record_revision_id": record_revision_id,
        "catalog_binding_id": _id(binding, "binding_id"),
        "catalog_workflow_node_count": str(1 + len(workflow_nodes)),
    }


def _ensure_test_json(api: DemoApi) -> dict[str, str]:
    document_key = "CMP-DEMO-DP780-TEST-JSON"
    existing = next(
        (
            item
            for item in _items(api.get("/test-data-documents"))
            if item.get("document_key") == document_key
        ),
        None,
    )
    if existing is None:
        document = {
            "document_type": "cmp.test-data",
            "schema_version": "1.0.0",
            "document_id": document_key,
            "material": {
                "maker": "CMP Synthetic Materials",
                "grade": "DP780",
                "lot_batch": "CMP-DEMO-LOT-001",
            },
            "test": {
                "date": "2026-07-18",
                "operator": "Demo Operator",
                "laboratory": "CMP Demo Laboratory",
                "method": "uniaxial tensile reference method",
                "equipment_maker": "Demo Instruments",
                "equipment_model": "UTM-01",
            },
            "specimen": {"specimen_id": "CMP-DEMO-S-JSON", "description": "sheet coupon"},
            "conditions": [
                {
                    "key": "temperature",
                    "quantity_semantics": "temperature.test",
                    "original_value": "23",
                    "original_unit_string": "Cel",
                    "normalized_value": "296.15",
                    "normalized_unit": "K",
                }
            ],
            "channels": [
                {
                    "key": "engineering_strain",
                    "name": "Engineering strain",
                    "quantity_semantics": "mechanics.strain.engineering",
                    "axis_role": "independent",
                    "original_unit_string": "1",
                    "normalized_unit": "1",
                    "normalization": {"scale": "1", "offset": "0"},
                    "original_values": [
                        "0",
                        "0.0005",
                        "0.001",
                        "0.0015",
                        "0.002",
                        "0.003",
                        "0.005",
                        "0.01",
                        "0.02",
                        "0.05",
                        "0.1",
                        "0.15",
                    ],
                    "normalized_values": [
                        "0",
                        "0.0005",
                        "0.001",
                        "0.0015",
                        "0.002",
                        "0.003",
                        "0.005",
                        "0.01",
                        "0.02",
                        "0.05",
                        "0.1",
                        "0.15",
                    ],
                    "missing_reasons": [None] * 12,
                },
                {
                    "key": "engineering_stress",
                    "name": "Engineering stress",
                    "quantity_semantics": "mechanics.stress.engineering",
                    "axis_role": "dependent",
                    "original_unit_string": "Pa",
                    "normalized_unit": "Pa",
                    "normalization": {"scale": "1", "offset": "0"},
                    "original_values": [
                        "0",
                        "105000000",
                        "210000000",
                        "315000000",
                        "420000000",
                        "450000000",
                        "480000000",
                        "520000000",
                        "560000000",
                        "600000000",
                        "620000000",
                        "610000000",
                    ],
                    "normalized_values": [
                        "0",
                        "105000000",
                        "210000000",
                        "315000000",
                        "420000000",
                        "450000000",
                        "480000000",
                        "520000000",
                        "560000000",
                        "600000000",
                        "620000000",
                        "610000000",
                    ],
                    "missing_reasons": [None] * 12,
                },
            ],
            "source": {
                "file_name": "cmp-demo-dp780-test.json",
                "media_type": "application/json",
                "sha256": "a" * 64,
            },
        }
        existing = api.post(
            "/test-data-documents",
            {
                "classification": "internal",
                "document": document,
                "change_reason": "Import the canonical JSON evidence for the clean demo.",
            },
        )
    primary_id = _id(existing, "test_data_document_id")
    primary_revision_id = _revision_id(existing)
    primary_document = api.get(
        f"/test-data-documents/{primary_id}/revisions/{primary_revision_id}/content"
    )
    listed_documents = _items(api.get("/test-data-documents"))
    for ordinal, scale in ((2, 0.985), (3, 1.018)):
        replica_key = f"CMP-DEMO-DP780-TEST-JSON-{ordinal:02d}"
        if any(item.get("document_key") == replica_key for item in listed_documents):
            continue
        replica = deepcopy(primary_document)
        replica["document_id"] = replica_key
        material = replica.get("material")
        if isinstance(material, dict):
            material["lot_batch"] = f"CMP-DEMO-LOT-{ordinal:03d}"
        specimen = replica.get("specimen")
        if isinstance(specimen, dict):
            specimen["specimen_id"] = f"CMP-DEMO-S-JSON-{ordinal:02d}"
        test = replica.get("test")
        if isinstance(test, dict):
            test["operator"] = f"Demo Operator {ordinal}"
        channels = replica.get("channels")
        if isinstance(channels, list):
            stress_channel = next(
                (
                    channel
                    for channel in channels
                    if isinstance(channel, dict)
                    and channel.get("quantity_semantics") == "mechanics.stress.engineering"
                ),
                None,
            )
            if isinstance(stress_channel, dict):
                scaled = [
                    format(float(value) * scale, ".12g")
                    for value in stress_channel.get("normalized_values", [])
                ]
                stress_channel["normalized_values"] = scaled
                stress_channel["original_values"] = list(scaled)
        source = replica.get("source")
        if isinstance(source, dict):
            source["file_name"] = f"cmp-demo-dp780-test-{ordinal:02d}.json"
            source["sha256"] = ("b" if ordinal == 2 else "c") * 64
        api.post(
            "/test-data-documents",
            {
                "classification": "internal",
                "document": replica,
                "change_reason": (
                    "Import a distinct synthetic tensile replicate for mean, scatter, and "
                    "confidence-band demonstration."
                ),
            },
        )
    return {
        "test_data_document_id": primary_id,
        "test_data_document_revision_id": primary_revision_id,
    }


def _ensure_processing_journey(api: DemoApi, *, test_data: Mapping[str, str]) -> dict[str, str]:
    profile = next(
        (
            item
            for item in _items(api.get("/mapping-profiles"))
            if item.get("content", {}).get("profile_key") == "cmp_demo_tensile_json"
        ),
        None,
    )
    if profile is None:
        profile = api.post(
            "/mapping-profiles",
            {
                "classification": "internal",
                "content": {
                    "profile_key": "cmp_demo_tensile_json",
                    "label": "CMP demo tensile JSON mapping",
                    "independent_quantity": "strain.engineering",
                    "missing_data_policy": "drop_any",
                    "bindings": [
                        {
                            "channel_key": "engineering_strain",
                            "target_quantity": "strain.engineering",
                            "accepted_normalized_units": ["1"],
                        },
                        {
                            "channel_key": "engineering_stress",
                            "target_quantity": "stress.engineering",
                            "accepted_normalized_units": ["Pa"],
                        },
                    ],
                },
                "change_reason": "Save the reusable canonical tensile Mapping Profile.",
            },
        )
    profile_id = _id(profile, "mapping_profile_id")
    profile_revision_id = _revision_id(profile)
    profile_hash = _revision_hash(profile)

    recipe = next(
        (
            item
            for item in _items(api.get("/common-processing-recipes"))
            if item.get("content", {}).get("recipe_key") == "cmp_demo_tensile_cleanup"
        ),
        None,
    )
    if recipe is None:
        content = {
            "recipe_key": "cmp_demo_tensile_cleanup",
            "label": "CMP demo tensile cleanup",
            "description": "Deterministic reusable clean-up of canonical tensile JSON.",
            "mapping_profile_id": profile_id,
            "mapping_profile_revision_id": profile_revision_id,
            "mapping_profile_sha256": profile_hash,
            "steps": [
                {
                    "method_id": "rows.sort_unique",
                    "method_version": "1.0.0",
                    "options": {"duplicate_policy": "reject"},
                },
                {
                    "method_id": "metal.engineering_to_true_plastic",
                    "method_version": "1.0.0",
                    "options": {
                        "strain_quantity": "strain.engineering",
                        "stress_quantity": "stress.engineering",
                        "youngs_modulus_pa": 210000000000,
                        "necking_policy": "manual_index",
                        "manual_necking_index": 10,
                        "negative_plastic_policy": "drop",
                    },
                },
                {
                    "method_id": "metal.hardening_fit_extrapolate",
                    "method_version": "1.0.0",
                    "options": {
                        "plastic_strain_quantity": "strain.true_plastic",
                        "stress_quantity": "stress.true",
                        "families": ["voce", "swift", "hockett_sherby", "ghosh"],
                        "fit_minimum_strain": 0.0001,
                        "fit_maximum_strain": 0.1,
                        "extrapolation_maximum_strain": 0.5,
                        "output_point_count": 101,
                        "primary_family": "swift",
                        "secondary_family": "voce",
                        "primary_weight": 0.5,
                        "normalization_stress_pa": 100000000,
                        "maximum_function_evaluations": 10000,
                    },
                },
            ],
            "lifecycle_state": "draft",
        }
        recipe = api.post(
            "/common-processing-recipes",
            {
                "classification": "internal",
                "content": content,
                "change_reason": "Draft the reusable clean demo Processing Recipe.",
            },
        )
        content["lifecycle_state"] = "published"
        recipe = api.post(
            f"/common-processing-recipes/{_id(recipe, 'processing_recipe_id')}/revisions",
            {
                "content": content,
                "change_reason": "Publish the reviewed clean demo Processing Recipe.",
            },
            headers={"If-Match": _revision_etag(recipe)},
        )
    recipe_id = _id(recipe, "processing_recipe_id")
    recipe_revision_id = _revision_id(recipe)
    batch_label = "CMP clean demo canonical JSON batch"
    batch = next(
        (
            item
            for item in _items(api.get("/common-processing-batches"))
            if item.get("label") == batch_label
        ),
        None,
    )
    source = {
        "document_id": test_data["test_data_document_id"],
        "revision_id": test_data["test_data_document_revision_id"],
    }
    if batch is None:
        preflight = api.post(
            "/common-processing-batches:preflight",
            {
                "classification": "internal",
                "recipe_id": recipe_id,
                "recipe_revision_id": recipe_revision_id,
                "sources": [source],
            },
        )
        if preflight.get("compatible") is not True:
            raise DemoSeedError("clean demo Processing Recipe preflight was not compatible")
        batch = api.post(
            "/common-processing-batches",
            {
                "classification": "internal",
                "recipe_id": recipe_id,
                "recipe_revision_id": recipe_revision_id,
                "sources": [source],
                "label": batch_label,
                "change_reason": "Execute the exact published Recipe against canonical Test JSON.",
            },
        )
    if batch.get("status") != "succeeded":
        raise DemoSeedError("clean demo canonical JSON batch did not succeed")
    attempts = batch.get("attempts")
    if not isinstance(attempts, list):
        raise DemoSeedError("clean demo canonical JSON batch has no attempts")
    output = next(
        (
            item
            for item in attempts
            if isinstance(item, Mapping)
            and item.get("status") == "succeeded"
            and item.get("output_id")
        ),
        None,
    )
    if output is None:
        raise DemoSeedError("clean demo canonical JSON batch has no committed output")
    return {
        "mapping_profile_id": profile_id,
        "mapping_profile_revision_id": profile_revision_id,
        "processing_recipe_id": recipe_id,
        "processing_recipe_revision_id": recipe_revision_id,
        "processing_batch_id": _id(batch, "batch_id"),
        "processing_output_id": _id(output, "output_id"),
        "processing_output_revision_id": _id(output, "output_revision_id"),
    }


def _ensure_material(
    api: DemoApi,
    *,
    name: str,
    material_code: str,
    material_family: str,
    material_class: str,
) -> dict[str, Any]:
    listed = _items(api.get(f"/materials?q={material_code}&limit=20"))
    material = _find_by_content(listed, "material_code", material_code)
    if material is None:
        material = api.post(
            "/materials",
            {
                "classification": "internal",
                "content": {
                    "name": name,
                    "material_code": material_code,
                    "material_family": material_family,
                    "material_class": material_class,
                    "description": (
                        "Public synthetic T-60 reference fixture; not validated engineering data."
                    ),
                },
                "change_reason": f"Create the synthetic {material_class} demo Material.",
            },
        )
    return api.get(f"/materials/{_id(material, 'material_id')}")


def _ensure_state(
    api: DemoApi, detail: Mapping[str, Any], *, name: str, lot: str
) -> dict[str, Any]:
    material = detail.get("material")
    if not isinstance(material, Mapping):
        raise DemoSeedError("full demo Material detail is incomplete")
    state = _find_by_content(_items({"items": detail.get("states")}), "name", name)
    if state is not None:
        return state
    return api.post(
        f"/materials/{_id(material, 'material_id')}/states",
        {
            "content": {
                "material_revision_id": _revision_id(material),
                "name": name,
                "manufacturing_route": "Public synthetic reference route",
                "heat_treatment": None,
                "lot_or_batch": lot,
                "description": "Deterministic T-60 demo state.",
            },
            "change_reason": "Create the synthetic modeling demo State.",
        },
    )


def _ensure_properties(
    api: DemoApi,
    detail: Mapping[str, Any],
    state: Mapping[str, Any],
    *,
    density: float,
    youngs_modulus: float,
    poisson_ratio: float,
) -> dict[str, Any]:
    state_id = _id(state, "material_state_id")
    existing = next(
        (
            item
            for item in _items({"items": detail.get("property_sets")})
            if item.get("material_state_id") == state_id
        ),
        None,
    )
    if existing is not None:
        return existing
    source = {"kind": "manual", "reference": "Public synthetic T-60 fixture"}
    return api.post(
        f"/material-states/{state_id}/property-sets",
        {
            "content": {
                "material_state_revision_id": _revision_id(state),
                "density_kg_per_m3": density,
                "density_source": source,
                "youngs_modulus_pa": youngs_modulus,
                "youngs_modulus_source": source,
                "poisson_ratio": poisson_ratio,
                "poisson_ratio_source": source,
                "yield_stress_pa": None,
                "yield_stress_source": None,
                "applicability": {
                    "temperature_min_k": 273.15,
                    "temperature_max_k": 313.15,
                    "strain_rate_min_per_s": None,
                    "strain_rate_max_per_s": None,
                    "note": "Public synthetic reference range only.",
                },
            },
            "change_reason": "Create typed synthetic modeling properties.",
        },
    )


def _ensure_shear_method(api: DemoApi) -> None:
    methods = _items(api.get("/test-methods"))
    if _find_by_content(methods, "method_code", "reference_shear_relaxation") is None:
        api.post(
            "/test-methods/reference-shear-relaxation",
            {
                "classification": "internal",
                "change_reason": "Create the public synthetic shear-relaxation method.",
            },
        )


def _fixture_complete(
    api: DemoApi,
    *,
    material_id: str,
    specimen_prefix: str,
    expected_count: int,
) -> bool:
    detail = api.get(f"/materials/{material_id}")
    states = detail.get("states")
    if not isinstance(states, list) or not states or not isinstance(states[0], Mapping):
        raise DemoSeedError("full demo Material has no Material State")
    state_id = _id(states[0], "material_state_id")
    specimens = _items(api.get(f"/material-states/{state_id}/specimens"))
    matching = [
        item
        for item in specimens
        if str(_content(item).get("specimen_code", "")).startswith(specimen_prefix)
    ]
    if not matching:
        return False
    if len(matching) != expected_count:
        raise DemoSeedError(
            f"full demo fixture {specimen_prefix} is partial "
            f"({len(matching)}/{expected_count}); remove only the demo volumes and reseed"
        )
    return True


def _ensure_polymer_baseline(api: DemoApi) -> str:
    detail = _ensure_material(
        api,
        name="Demo Polymer Prony",
        material_code="CMP-DEMO-POLYMER-PRONY",
        material_family="linear viscoelastic polymer",
        material_class="polymer",
    )
    state = _ensure_state(api, detail, name="Reference conditioned", lot="CMP-DEMO-POLYMER-001")
    properties = _ensure_properties(
        api,
        detail,
        state,
        density=1200.0,
        # Keep the synthetic instantaneous shear modulus at 1.111... GPa while making the
        # reference eligible for ADR-0032's nearly-incompressible LPRONY path.
        youngs_modulus=3_322_222_222.0,
        poisson_ratio=0.495,
    )
    state_id = _id(state, "material_state_id")
    models = _items(api.get(f"/material-states/{state_id}/linear-viscoelastic-models"))
    model = (
        models[0]
        if models
        else api.post(
            f"/material-states/{state_id}/linear-viscoelastic-models",
            {
                "property_set_revision_id": _revision_id(properties),
                "bulk_relaxation_status": "not_characterized",
                "terms": [
                    {"g_ratio": 0.2, "k_ratio": 0.0, "relaxation_time_s": 0.1},
                    {"g_ratio": 0.3, "k_ratio": 0.0, "relaxation_time_s": 10.0},
                ],
                "change_reason": "Create the public synthetic two-term Prony baseline.",
            },
        )
    )
    model_id = _id(model, "material_model_id")
    cards = _items(api.get(f"/linear-viscoelastic-models/{model_id}/solver-cards"))
    if not cards:
        target = {"solver": "abaqus", "version": "2025", "unit_system": "kg_m_s"}
        report = api.post(
            f"/linear-viscoelastic-models/{model_id}/mapping-preflight",
            {"material_model_revision_id": _revision_id(model), "target": target},
        )
        api.post(
            f"/linear-viscoelastic-models/{model_id}/solver-cards",
            {
                "material_model_revision_id": _revision_id(model),
                "target": target,
                "expected_mapping_report_sha256": _id(report, "mapping_report_sha256"),
                "solver_material_id": 1200,
                "material_name": "CMP_DEMO_POLYMER_PRONY",
                "change_reason": "Generate the public synthetic Abaqus Prony card.",
            },
        )
    _ensure_shear_method(api)
    material = detail.get("material")
    if not isinstance(material, Mapping):
        raise DemoSeedError("polymer material detail is incomplete")
    return _id(material, "material_id")


def _ensure_polymer_processing_card(api: DemoApi, *, material_id: str) -> dict[str, str]:
    """Seed the reviewed common-Processing-to-Abaqus polymer vertical."""

    detail = api.get(f"/materials/{material_id}")
    states = detail.get("states")
    properties = detail.get("property_sets")
    if (
        not isinstance(states, list)
        or not states
        or not isinstance(states[0], Mapping)
        or not isinstance(properties, list)
        or not properties
        or not isinstance(properties[0], Mapping)
    ):
        raise DemoSeedError("polymer Processing demo requires one State and Property Set")
    state = states[0]
    property_set = properties[0]
    document_key = "CMP-DEMO-POLYMER-RELAXATION-JSON"
    test_data = next(
        (
            item
            for item in _items(api.get("/test-data-documents"))
            if item.get("document_key") == document_key
        ),
        None,
    )
    if test_data is None:
        times = ["0.01", "0.03", "0.1", "0.3", "1", "3", "10", "30", "100"]
        moduli = [
            "1089000000",
            "1050000000",
            "954000000",
            "869000000",
            "814000000",
            "766000000",
            "678000000",
            "572000000",
            "555000000",
        ]
        test_data = api.post(
            "/test-data-documents",
            {
                "classification": "internal",
                "document": {
                    "document_type": "cmp.test-data",
                    "schema_version": "1.0.0",
                    "document_id": document_key,
                    "material": {
                        "maker": "CMP Synthetic Materials",
                        "grade": "Demo Polymer Prony",
                        "lot_batch": "CMP-DEMO-POLYMER-001",
                    },
                    "test": {
                        "date": "2026-07-19",
                        "operator": "Demo Operator",
                        "laboratory": "CMP Demo Laboratory",
                        "method": "synthetic shear relaxation reference",
                        "equipment_maker": "Demo Instruments",
                        "equipment_model": "Relaxometer-01",
                    },
                    "specimen": {
                        "specimen_id": "CMP-DEMO-POLYMER-SR-01",
                        "description": "public synthetic relaxation specimen",
                    },
                    "conditions": [
                        {
                            "key": "temperature",
                            "quantity_semantics": "temperature.test",
                            "original_value": "23",
                            "original_unit_string": "Cel",
                            "normalized_value": "296.15",
                            "normalized_unit": "K",
                        }
                    ],
                    "channels": [
                        {
                            "key": "time_s",
                            "name": "Time",
                            "quantity_semantics": "time.elapsed",
                            "axis_role": "independent",
                            "original_unit_string": "s",
                            "normalized_unit": "s",
                            "normalization": {"scale": "1", "offset": "0"},
                            "original_values": times,
                            "normalized_values": times,
                            "missing_reasons": [None] * len(times),
                        },
                        {
                            "key": "shear_modulus_pa",
                            "name": "Shear relaxation modulus",
                            "quantity_semantics": "modulus.shear.relaxation",
                            "axis_role": "dependent",
                            "original_unit_string": "Pa",
                            "normalized_unit": "Pa",
                            "normalization": {"scale": "1", "offset": "0"},
                            "original_values": moduli,
                            "normalized_values": moduli,
                            "missing_reasons": [None] * len(moduli),
                        },
                    ],
                    "source": {
                        "file_name": "cmp-demo-polymer-relaxation.json",
                        "media_type": "application/json",
                        "sha256": "7" * 64,
                    },
                },
                "change_reason": "Import public synthetic polymer relaxation Test JSON.",
            },
        )

    profile = next(
        (
            item
            for item in _items(api.get("/mapping-profiles"))
            if item.get("content", {}).get("profile_key") == "cmp_demo_polymer_relaxation"
        ),
        None,
    )
    if profile is None:
        profile = api.post(
            "/mapping-profiles",
            {
                "classification": "internal",
                "content": {
                    "profile_key": "cmp_demo_polymer_relaxation",
                    "label": "CMP demo polymer relaxation mapping",
                    "independent_quantity": "time",
                    "missing_data_policy": "drop_any",
                    "bindings": [
                        {
                            "channel_key": "time_s",
                            "target_quantity": "time",
                            "accepted_normalized_units": ["s"],
                        },
                        {
                            "channel_key": "shear_modulus_pa",
                            "target_quantity": "modulus.shear.relaxation",
                            "accepted_normalized_units": ["Pa"],
                        },
                    ],
                },
                "change_reason": "Save the reusable polymer relaxation Mapping Profile.",
            },
        )

    steps = [
        {
            "method_id": "rows.sort_unique",
            "method_version": "1.0.0",
            "options": {"duplicate_policy": "reject"},
        },
        {
            "method_id": "polymer.log_time_resample",
            "method_version": "1.0.0",
            "options": {
                "start_time_s": 0.01,
                "end_time_s": 100,
                "count": 41,
                "extrapolation": "reject",
            },
        },
        {
            "method_id": "polymer.prony_fit_compare",
            "method_version": "1.0.0",
            "options": {
                "time_quantity": "time",
                "modulus_quantity": "modulus.shear.relaxation",
                "candidate_term_counts": [1, 2, 3, 4],
                "selection_mode": "automatic_bic",
                "selected_term_count": 2,
                "normalization_modulus_pa": 1111111111,
                "minimum_relaxation_time_s": 0.0001,
                "maximum_relaxation_time_s": 1000000,
                "maximum_function_evaluations": 5000,
                "selection_reason": (
                    "Lowest BIC with stable monotonic relaxation over the observed time domain."
                ),
            },
        },
    ]
    recipe = next(
        (
            item
            for item in _items(api.get("/common-processing-recipes"))
            if item.get("content", {}).get("recipe_key") == "cmp_demo_polymer_prony"
        ),
        None,
    )
    if recipe is None:
        recipe_content = {
            "recipe_key": "cmp_demo_polymer_prony",
            "label": "CMP demo polymer Prony processing",
            "description": (
                "Reusable deterministic log-time resampling and generalized-Maxwell fitting."
            ),
            "mapping_profile_id": _id(profile, "mapping_profile_id"),
            "mapping_profile_revision_id": _revision_id(profile),
            "mapping_profile_sha256": _revision_hash(profile),
            "steps": steps,
            "lifecycle_state": "draft",
        }
        recipe = api.post(
            "/common-processing-recipes",
            {
                "classification": "internal",
                "content": recipe_content,
                "change_reason": "Draft the reusable synthetic polymer Prony Recipe.",
            },
        )
        recipe_content["lifecycle_state"] = "published"
        recipe = api.post(
            f"/common-processing-recipes/{_id(recipe, 'processing_recipe_id')}/revisions",
            {
                "content": recipe_content,
                "change_reason": "Publish the reviewed synthetic polymer Prony Recipe.",
            },
            headers={"If-Match": _revision_etag(recipe)},
        )
    batch_label = "CMP demo polymer Prony batch"
    batch = next(
        (
            item
            for item in _items(api.get("/common-processing-batches"))
            if item.get("label") == batch_label
            and item.get("recipe_revision_id") == _revision_id(recipe)
        ),
        None,
    )
    batch_source = {
        "document_id": _id(test_data, "test_data_document_id"),
        "revision_id": _revision_id(test_data),
    }
    if batch is None:
        preflight = api.post(
            "/common-processing-batches:preflight",
            {
                "classification": "internal",
                "recipe_id": _id(recipe, "processing_recipe_id"),
                "recipe_revision_id": _revision_id(recipe),
                "sources": [batch_source],
            },
        )
        if preflight.get("compatible") is not True:
            raise DemoSeedError("polymer Processing Recipe preflight was not compatible")
        batch = api.post(
            "/common-processing-batches",
            {
                "classification": "internal",
                "recipe_id": _id(recipe, "processing_recipe_id"),
                "recipe_revision_id": _revision_id(recipe),
                "sources": [batch_source],
                "label": batch_label,
                "change_reason": "Execute the exact published polymer Prony Recipe.",
            },
        )
    if batch.get("status") != "succeeded":
        raise DemoSeedError("polymer Processing Recipe batch did not succeed")
    output_attempt = next(
        (
            item
            for item in batch.get("attempts", [])
            if isinstance(item, Mapping)
            and item.get("status") == "succeeded"
            and item.get("output_id")
        ),
        None,
    )
    if output_attempt is None:
        raise DemoSeedError("polymer Processing Batch has no successful Output")
    output = next(
        (
            item
            for item in _items(api.get("/processing-outputs"))
            if item.get("processing_output_id") == _id(output_attempt, "output_id")
        ),
        None,
    )
    if output is None:
        raise DemoSeedError("polymer Batch Output is not visible")

    models = _items(
        api.get(f"/material-states/{_id(state, 'material_state_id')}/linear-viscoelastic-models")
    )

    def promoted_output_id(item: Mapping[str, Any]) -> object:
        evidence = _content(item).get("processing_promotion_evidence")
        processing_output = (
            evidence.get("processing_output") if isinstance(evidence, Mapping) else None
        )
        return processing_output.get("id") if isinstance(processing_output, Mapping) else None

    model = next(
        (
            item
            for item in models
            if promoted_output_id(item) == _id(output, "processing_output_id")
        ),
        None,
    )
    if model is None:
        model = api.post(
            f"/processing-outputs/{_id(output, 'processing_output_id')}/linear-viscoelastic-models",
            {
                "material_state_id": _id(state, "material_state_id"),
                "property_set_revision_id": _revision_id(property_set),
                "processing_output_revision_id": _revision_id(output),
                "acknowledged_maximum_relative_mismatch": 0.1,
                "review_acknowledged": True,
                "change_reason": "Promote reviewed synthetic Prony Processing Output.",
            },
        )

    neutral = None
    for candidate in _items(api.get(f"/bulk-export-candidates?material_id={material_id}")):
        source = candidate.get("source")
        if not isinstance(source, Mapping) or source.get("kind") != "neutral_material_json":
            continue
        candidate_id = source.get("neutral_material_id")
        if not isinstance(candidate_id, str):
            continue
        value = api.get(f"/neutral-materials/{candidate_id}")
        selection = value.get("document", {}).get("candidate_selection", {})
        if (
            isinstance(selection, Mapping)
            and selection.get("kind") == "prony_processing_output_selection"
            and selection.get("processing_output", {}).get("id")
            == _id(output, "processing_output_id")
        ):
            neutral = value
            break
    if neutral is None:
        neutral = api.post(
            "/neutral-materials:promote-linear-viscoelastic",
            {
                "material_model_id": _id(model, "material_model_id"),
                "material_model_revision_id": _revision_id(model),
                "selection_reason": "Select the reviewed synthetic Prony Processing result.",
                "change_reason": "Create reproducible polymer Neutral Material JSON.",
            },
        )

    neutral_id = _id(neutral, "neutral_material_id")
    cards = _items(api.get(f"/neutral-materials/{neutral_id}/solver-cards"))
    abaqus_card = next(
        (
            item
            for item in cards
            if isinstance(item.get("target"), Mapping) and item["target"].get("solver") == "abaqus"
        ),
        None,
    )
    if abaqus_card is None:
        target = {"solver": "abaqus", "version": "2025", "unit_system": "kg_m_s"}
        report = api.post(
            f"/neutral-materials/{neutral_id}/solver-card-preflight",
            {
                "neutral_material_revision_id": _id(neutral, "neutral_material_revision_id"),
                "target": target,
            },
        )
        abaqus_card = api.post(
            f"/neutral-materials/{neutral_id}/solver-cards",
            {
                "neutral_material_revision_id": _id(neutral, "neutral_material_revision_id"),
                "target": target,
                "expected_mapping_report_sha256": _id(report, "mapping_report_sha256"),
                "solver_material_id": 1201,
                "material_name": "CMP_DEMO_POLYMER_PROCESSED",
                "change_reason": "Generate Abaqus Prony card from exact Neutral JSON.",
            },
        )
    openradioss_card = next(
        (
            item
            for item in cards
            if isinstance(item.get("target"), Mapping)
            and item["target"].get("solver") == "openradioss"
        ),
        None,
    )
    if openradioss_card is None:
        target = {"solver": "openradioss", "version": "2025", "unit_system": "kg_m_s"}
        report = api.post(
            f"/neutral-materials/{neutral_id}/solver-card-preflight",
            {
                "neutral_material_revision_id": _id(neutral, "neutral_material_revision_id"),
                "target": target,
            },
        )
        if not report.get("exportable"):
            raise DemoSeedError("synthetic polymer did not pass OpenRadioss LPRONY preflight")
        openradioss_card = api.post(
            f"/neutral-materials/{neutral_id}/solver-cards",
            {
                "neutral_material_revision_id": _id(neutral, "neutral_material_revision_id"),
                "target": target,
                "expected_mapping_report_sha256": _id(report, "mapping_report_sha256"),
                "solver_material_id": 1202,
                "material_name": "CMP_DEMO_POLYMER_LPRONY",
                "change_reason": "Generate acknowledged OpenRadioss LPRONY reference fragment.",
            },
        )

    dma_document_key = "CMP-DEMO-POLYMER-DMA-JSON"
    dma_test_data = next(
        (
            item
            for item in _items(api.get("/test-data-documents"))
            if item.get("document_key") == dma_document_key
        ),
        None,
    )
    if dma_test_data is None:
        frequencies = [10 ** (-2 + ordinal * 4 / 32) for ordinal in range(33)]
        amplitudes = (300_000_000.0, 500_000_000.0)
        relaxation_times = (0.08, 8.0)
        equilibrium = 300_000_000.0
        storage = [
            equilibrium
            + sum(
                amplitude
                * (2 * math.pi * frequency * tau) ** 2
                / (1 + (2 * math.pi * frequency * tau) ** 2)
                for amplitude, tau in zip(amplitudes, relaxation_times, strict=True)
            )
            for frequency in frequencies
        ]
        loss = [
            sum(
                amplitude
                * (2 * math.pi * frequency * tau)
                / (1 + (2 * math.pi * frequency * tau) ** 2)
                for amplitude, tau in zip(amplitudes, relaxation_times, strict=True)
            )
            for frequency in frequencies
        ]

        def string_values(values: list[float]) -> list[str]:
            return [f"{value:.12g}" for value in values]

        dma_test_data = api.post(
            "/test-data-documents",
            {
                "classification": "internal",
                "document": {
                    "document_type": "cmp.test-data",
                    "schema_version": "1.0.0",
                    "document_id": dma_document_key,
                    "material": {
                        "maker": "CMP Synthetic Materials",
                        "grade": "Demo Polymer Prony",
                        "lot_batch": "CMP-DEMO-POLYMER-001",
                    },
                    "test": {
                        "date": "2026-07-20",
                        "operator": "Demo Operator",
                        "laboratory": "CMP Demo Laboratory",
                        "method": "synthetic DMA frequency sweep reference",
                        "equipment_maker": "Demo Instruments",
                        "equipment_model": "DMA-01",
                    },
                    "specimen": {
                        "specimen_id": "CMP-DEMO-POLYMER-DMA-01",
                        "description": "public synthetic storage/loss modulus frequency sweep",
                    },
                    "conditions": [
                        {
                            "key": "temperature",
                            "quantity_semantics": "temperature.test",
                            "original_value": "23",
                            "original_unit_string": "Cel",
                            "normalized_value": "296.15",
                            "normalized_unit": "K",
                        }
                    ],
                    "channels": [
                        {
                            "key": "frequency_hz",
                            "name": "Cyclic frequency",
                            "quantity_semantics": "frequency.cyclic",
                            "axis_role": "independent",
                            "original_unit_string": "Hz",
                            "normalized_unit": "Hz",
                            "normalization": {"scale": "1", "offset": "0"},
                            "original_values": string_values(frequencies),
                            "normalized_values": string_values(frequencies),
                            "missing_reasons": [None] * len(frequencies),
                        },
                        {
                            "key": "storage_modulus_pa",
                            "name": "Storage modulus",
                            "quantity_semantics": "modulus.shear.storage",
                            "axis_role": "dependent",
                            "original_unit_string": "Pa",
                            "normalized_unit": "Pa",
                            "normalization": {"scale": "1", "offset": "0"},
                            "original_values": string_values(storage),
                            "normalized_values": string_values(storage),
                            "missing_reasons": [None] * len(storage),
                        },
                        {
                            "key": "loss_modulus_pa",
                            "name": "Loss modulus",
                            "quantity_semantics": "modulus.shear.loss",
                            "axis_role": "dependent",
                            "original_unit_string": "Pa",
                            "normalized_unit": "Pa",
                            "normalization": {"scale": "1", "offset": "0"},
                            "original_values": string_values(loss),
                            "normalized_values": string_values(loss),
                            "missing_reasons": [None] * len(loss),
                        },
                    ],
                    "source": {
                        "file_name": "cmp-demo-polymer-dma.json",
                        "media_type": "application/json",
                        "sha256": "8" * 64,
                    },
                },
                "change_reason": "Import public synthetic polymer DMA Test JSON.",
            },
        )
    dma_profile = next(
        (
            item
            for item in _items(api.get("/mapping-profiles"))
            if item.get("content", {}).get("profile_key") == "polymer-dma-frequency"
        ),
        None,
    )
    if dma_profile is None:
        dma_profile = api.post(
            "/mapping-profiles",
            {
                "classification": "internal",
                "content": {
                    "profile_key": "polymer-dma-frequency",
                    "label": "CMP demo polymer DMA mapping",
                    "independent_quantity": "frequency",
                    "missing_data_policy": "drop_any",
                    "bindings": [
                        {
                            "channel_key": "frequency_hz",
                            "target_quantity": "frequency",
                            "accepted_normalized_units": ["Hz"],
                        },
                        {
                            "channel_key": "storage_modulus_pa",
                            "target_quantity": "modulus.shear.storage",
                            "accepted_normalized_units": ["Pa"],
                        },
                        {
                            "channel_key": "loss_modulus_pa",
                            "target_quantity": "modulus.shear.loss",
                            "accepted_normalized_units": ["Pa"],
                        },
                    ],
                },
                "change_reason": "Save the reusable polymer DMA Mapping Profile.",
            },
        )
    dma_steps = [
        {
            "method_id": "rows.sort_unique",
            "method_version": "1.0.0",
            "options": {"duplicate_policy": "reject"},
        },
        {
            "method_id": "polymer.dma_prony_fit_compare",
            "method_version": "1.0.0",
            "options": {
                "frequency_quantity": "frequency",
                "storage_modulus_quantity": "modulus.shear.storage",
                "loss_modulus_quantity": "modulus.shear.loss",
                "candidate_term_counts": [1, 2, 3, 4],
                "selection_mode": "automatic_bic",
                "selected_term_count": 2,
                "normalization_modulus_pa": 1_100_000_000,
                "minimum_relaxation_time_s": 0.0001,
                "maximum_relaxation_time_s": 1000000,
                "maximum_function_evaluations": 5000,
                "selection_reason": (
                    "Lowest joint storage/loss BIC over the measured frequency domain."
                ),
            },
        },
    ]
    dma_recipe = next(
        (
            item
            for item in _items(api.get("/common-processing-recipes"))
            if item.get("content", {}).get("recipe_key") == "cmp_demo_polymer_dma_prony"
        ),
        None,
    )
    if dma_recipe is None:
        dma_recipe_content = {
            "recipe_key": "cmp_demo_polymer_dma_prony",
            "label": "CMP demo polymer DMA Prony processing",
            "description": ("Reusable joint storage/loss generalized-Maxwell frequency fitting."),
            "mapping_profile_id": _id(dma_profile, "mapping_profile_id"),
            "mapping_profile_revision_id": _revision_id(dma_profile),
            "mapping_profile_sha256": _revision_hash(dma_profile),
            "steps": dma_steps,
            "lifecycle_state": "draft",
        }
        dma_recipe = api.post(
            "/common-processing-recipes",
            {
                "classification": "internal",
                "content": dma_recipe_content,
                "change_reason": "Draft the reusable synthetic polymer DMA Recipe.",
            },
        )
        dma_recipe_content["lifecycle_state"] = "published"
        dma_recipe = api.post(
            f"/common-processing-recipes/{_id(dma_recipe, 'processing_recipe_id')}/revisions",
            {
                "content": dma_recipe_content,
                "change_reason": "Publish the reviewed synthetic polymer DMA Recipe.",
            },
            headers={"If-Match": _revision_etag(dma_recipe)},
        )
    dma_batch_label = "CMP demo polymer DMA Prony batch"
    dma_batch = next(
        (
            item
            for item in _items(api.get("/common-processing-batches"))
            if item.get("label") == dma_batch_label
            and item.get("recipe_revision_id") == _revision_id(dma_recipe)
        ),
        None,
    )
    dma_batch_source = {
        "document_id": _id(dma_test_data, "test_data_document_id"),
        "revision_id": _revision_id(dma_test_data),
    }
    if dma_batch is None:
        dma_preflight = api.post(
            "/common-processing-batches:preflight",
            {
                "classification": "internal",
                "recipe_id": _id(dma_recipe, "processing_recipe_id"),
                "recipe_revision_id": _revision_id(dma_recipe),
                "sources": [dma_batch_source],
            },
        )
        if dma_preflight.get("compatible") is not True:
            raise DemoSeedError("polymer DMA Processing Recipe preflight was not compatible")
        dma_batch = api.post(
            "/common-processing-batches",
            {
                "classification": "internal",
                "recipe_id": _id(dma_recipe, "processing_recipe_id"),
                "recipe_revision_id": _revision_id(dma_recipe),
                "sources": [dma_batch_source],
                "label": dma_batch_label,
                "change_reason": "Execute the exact published polymer DMA Prony Recipe.",
            },
        )
    if dma_batch.get("status") != "succeeded":
        raise DemoSeedError("polymer DMA Processing Recipe batch did not succeed")
    dma_output_attempt = next(
        (
            item
            for item in dma_batch.get("attempts", [])
            if isinstance(item, Mapping)
            and item.get("status") == "succeeded"
            and item.get("output_id")
        ),
        None,
    )
    if dma_output_attempt is None:
        raise DemoSeedError("polymer DMA Processing Batch has no successful Output")
    dma_output = next(
        (
            item
            for item in _items(api.get("/processing-outputs"))
            if item.get("processing_output_id") == dma_output_attempt.get("output_id")
        ),
        None,
    )
    if dma_output is None:
        raise DemoSeedError("polymer DMA Processing Output was not retained")
    dma_model = next(
        (
            item
            for item in _items(
                api.get(
                    f"/material-states/{_id(state, 'material_state_id')}/linear-viscoelastic-models"
                )
            )
            if promoted_output_id(item) == _id(dma_output, "processing_output_id")
        ),
        None,
    )
    if dma_model is None:
        dma_model = api.post(
            f"/processing-outputs/{_id(dma_output, 'processing_output_id')}"
            "/linear-viscoelastic-models",
            {
                "material_state_id": _id(state, "material_state_id"),
                "property_set_revision_id": _revision_id(property_set),
                "processing_output_revision_id": _revision_id(dma_output),
                "acknowledged_maximum_relative_mismatch": 0.1,
                "review_acknowledged": True,
                "change_reason": "Promote reviewed synthetic DMA Prony Processing Output.",
            },
        )
    dma_neutral = None
    for candidate in _items(api.get(f"/bulk-export-candidates?material_id={material_id}")):
        candidate_source = candidate.get("source")
        if (
            not isinstance(candidate_source, Mapping)
            or candidate_source.get("kind") != "neutral_material_json"
        ):
            continue
        candidate_id = candidate_source.get("neutral_material_id")
        if not isinstance(candidate_id, str):
            continue
        candidate_neutral = api.get(f"/neutral-materials/{candidate_id}")
        candidate_selection = candidate_neutral.get("document", {}).get("candidate_selection", {})
        if (
            isinstance(candidate_selection, Mapping)
            and candidate_selection.get("kind") == "prony_processing_output_selection"
            and candidate_selection.get("processing_output", {}).get("id")
            == _id(dma_output, "processing_output_id")
        ):
            dma_neutral = candidate_neutral
            break
    if dma_neutral is None:
        dma_neutral = api.post(
            "/neutral-materials:promote-linear-viscoelastic",
            {
                "material_model_id": _id(dma_model, "material_model_id"),
                "material_model_revision_id": _revision_id(dma_model),
                "selection_reason": ("Select the joint storage/loss DMA Prony Processing result."),
                "change_reason": "Create reproducible DMA Neutral Material JSON.",
            },
        )
    dma_neutral_id = _id(dma_neutral, "neutral_material_id")
    dma_cards = _items(api.get(f"/neutral-materials/{dma_neutral_id}/solver-cards"))
    dma_card_ids: dict[str, str] = {}
    for solver, material_id_number, material_name in (
        ("abaqus", 1211, "CMP_DEMO_POLYMER_DMA"),
        ("openradioss", 1212, "CMP_DEMO_POLYMER_DMA_LPRONY"),
    ):
        dma_card = next(
            (
                item
                for item in dma_cards
                if isinstance(item.get("target"), Mapping)
                and item["target"].get("solver") == solver
            ),
            None,
        )
        if dma_card is None:
            target = {"solver": solver, "version": "2025", "unit_system": "kg_m_s"}
            report = api.post(
                f"/neutral-materials/{dma_neutral_id}/solver-card-preflight",
                {
                    "neutral_material_revision_id": _id(
                        dma_neutral, "neutral_material_revision_id"
                    ),
                    "target": target,
                },
            )
            if not report.get("exportable"):
                raise DemoSeedError(f"synthetic DMA did not pass {solver} preflight")
            dma_card = api.post(
                f"/neutral-materials/{dma_neutral_id}/solver-cards",
                {
                    "neutral_material_revision_id": _id(
                        dma_neutral, "neutral_material_revision_id"
                    ),
                    "target": target,
                    "expected_mapping_report_sha256": _id(report, "mapping_report_sha256"),
                    "solver_material_id": material_id_number,
                    "material_name": material_name,
                    "change_reason": (f"Generate {solver} Prony card from exact DMA Neutral JSON."),
                },
            )
        dma_card_ids[solver] = _id(dma_card, "solver_card_id")
    return {
        "polymer_test_data_document_id": _id(test_data, "test_data_document_id"),
        "polymer_processing_recipe_id": _id(recipe, "processing_recipe_id"),
        "polymer_processing_batch_id": _id(batch, "batch_id"),
        "polymer_processing_output_id": _id(output, "processing_output_id"),
        "polymer_processing_model_id": _id(model, "material_model_id"),
        "polymer_processing_neutral_id": neutral_id,
        "polymer_processing_card_id": _id(abaqus_card, "solver_card_id"),
        "polymer_processing_openradioss_card_id": _id(openradioss_card, "solver_card_id"),
        "polymer_dma_test_data_document_id": _id(dma_test_data, "test_data_document_id"),
        "polymer_dma_mapping_profile_id": _id(dma_profile, "mapping_profile_id"),
        "polymer_dma_processing_recipe_id": _id(dma_recipe, "processing_recipe_id"),
        "polymer_dma_processing_batch_id": _id(dma_batch, "batch_id"),
        "polymer_dma_processing_output_id": _id(dma_output, "processing_output_id"),
        "polymer_dma_processing_model_id": _id(dma_model, "material_model_id"),
        "polymer_dma_processing_neutral_id": dma_neutral_id,
        "polymer_dma_abaqus_card_id": dma_card_ids["abaqus"],
        "polymer_dma_openradioss_card_id": dma_card_ids["openradioss"],
    }


def _ensure_elastomer_baseline(api: DemoApi) -> str:
    detail = _ensure_material(
        api,
        name="Demo Elastomer Ogden-Prony",
        material_code="CMP-DEMO-ELASTOMER-OGDEN",
        material_family="Ogden hyper-viscoelastic elastomer",
        material_class="elastomer",
    )
    state = _ensure_state(api, detail, name="Reference cured", lot="CMP-DEMO-ELASTOMER-001")
    properties = _ensure_properties(
        api,
        detail,
        state,
        density=1100.0,
        youngs_modulus=6_000_000.0,
        poisson_ratio=0.49,
    )
    state_id = _id(state, "material_state_id")
    models = _items(api.get(f"/material-states/{state_id}/ogden-prony-models"))
    model = (
        models[0]
        if models
        else api.post(
            f"/material-states/{state_id}/ogden-prony-models",
            {
                "property_set_revision_id": _revision_id(properties),
                "ogden_mu_pa": 2_000_000.0,
                "ogden_alpha": 2.0,
                "prony_terms": [
                    {"g_ratio": 0.15, "relaxation_time_s": 0.2},
                    {"g_ratio": 0.25, "relaxation_time_s": 8.0},
                ],
                "change_reason": "Create the public synthetic Ogden-Prony baseline.",
            },
        )
    )
    model_id = _id(model, "material_model_id")
    existing = _items(api.get(f"/ogden-prony-models/{model_id}/solver-cards"))
    existing_solvers = {
        str(item.get("target", {}).get("solver"))
        for item in existing
        if isinstance(item.get("target"), Mapping)
    }
    for solver, solver_material_id in (("abaqus", 2100), ("openradioss", 2101)):
        if solver in existing_solvers:
            continue
        target = {"solver": solver, "version": "2025", "unit_system": "kg_m_s"}
        report = api.post(
            f"/ogden-prony-models/{model_id}/solver-card-preflight",
            {"material_model_revision_id": _revision_id(model), "target": target},
        )
        api.post(
            f"/ogden-prony-models/{model_id}/solver-cards",
            {
                "material_model_revision_id": _revision_id(model),
                "target": target,
                "expected_mapping_report_sha256": _id(report, "mapping_report_sha256"),
                "solver_material_id": solver_material_id,
                "material_name": "CMP_DEMO_ELASTOMER_OGDEN",
                "change_reason": f"Generate the public synthetic {solver} Ogden-Prony card.",
            },
        )
    material = detail.get("material")
    if not isinstance(material, Mapping):
        raise DemoSeedError("elastomer material detail is incomplete")
    return _id(material, "material_id")


def _ensure_metal_neutral_and_cards(
    api: DemoApi, *, material_id: str, processing_batch_id: str
) -> dict[str, str]:
    detail = api.get(f"/materials/{material_id}")
    states = detail.get("states")
    if not isinstance(states, list) or not states or not isinstance(states[0], Mapping):
        raise DemoSeedError("clean demo metal Material has no State")
    state = states[0]
    models = _items(
        api.get(f"/material-states/{_id(state, 'material_state_id')}/tabulated-plasticity-models")
    )
    model = next(
        (item for item in models if _content(item).get("processing_projection") is not None),
        None,
    )
    if model is None:
        batch = api.get(f"/common-processing-batches/{processing_batch_id}")
        attempts = batch.get("attempts")
        if not isinstance(attempts, list) or not attempts:
            raise DemoSeedError("clean demo Processing Batch has no committed output")
        succeeded = next(
            (
                item
                for item in attempts
                if isinstance(item, Mapping)
                and item.get("status") == "succeeded"
                and item.get("output_id")
                and item.get("output_revision_id")
            ),
            None,
        )
        if succeeded is None:
            raise DemoSeedError("clean demo Processing Batch has no successful output")
        property_sets = detail.get("property_sets")
        if (
            not isinstance(property_sets, list)
            or not property_sets
            or not isinstance(property_sets[0], Mapping)
        ):
            raise DemoSeedError("clean demo metal Material has no Property Set")
        model = api.post(
            f"/processing-outputs/{succeeded['output_id']}/tabulated-plasticity-models",
            {
                "material_state_id": _id(state, "material_state_id"),
                "property_set_revision_id": _revision_id(property_sets[0]),
                "processing_output_revision_id": succeeded["output_revision_id"],
                "acknowledge_bounded_extrapolation": True,
                "change_reason": (
                    "Promote the selected fitted clean-demo output to tabulated plasticity IR."
                ),
            },
        )

    neutral: dict[str, Any] | None = None
    candidates = _items(api.get(f"/bulk-export-candidates?material_id={material_id}"))
    for candidate in candidates:
        source = candidate.get("source")
        if not isinstance(source, Mapping) or source.get("kind") != "neutral_material_json":
            continue
        candidate_id = source.get("neutral_material_id")
        if not isinstance(candidate_id, str):
            continue
        value = api.get(f"/neutral-materials/{candidate_id}")
        ir = value.get("document", {}).get("material_model_ir", {})
        if isinstance(ir, Mapping) and ir.get("model_family") == "isotropic_tabulated_plasticity":
            neutral = value
            break
    if neutral is None:
        neutral = api.post(
            "/neutral-materials:promote-metal",
            {
                "material_model_id": _id(model, "material_model_id"),
                "material_model_revision_id": _revision_id(model),
                "selection_reason": (
                    "Select the public synthetic tabulated-plasticity reference for the clean demo."
                ),
                "change_reason": "Promote the exact metal IR to canonical Neutral Material JSON.",
            },
        )

    neutral_id = _id(neutral, "neutral_material_id")
    neutral_revision_id = _id(neutral, "neutral_material_revision_id")
    cards = _items(api.get(f"/neutral-materials/{neutral_id}/solver-cards"))
    by_solver = {
        str(item.get("target", {}).get("solver")): item
        for item in cards
        if isinstance(item.get("target"), Mapping)
    }
    result = {
        "neutral_material_id": neutral_id,
        "neutral_material_revision_id": neutral_revision_id,
        "selected_material_model_id": _id(model, "material_model_id"),
        "selected_material_model_revision_id": _revision_id(model),
    }
    for solver, solver_material_id in (("abaqus", 5780), ("openradioss", 5781)):
        card = by_solver.get(solver)
        if card is None:
            target = {"solver": solver, "version": "2025", "unit_system": "kg_m_s"}
            report = api.post(
                f"/neutral-materials/{neutral_id}/solver-card-preflight",
                {"neutral_material_revision_id": neutral_revision_id, "target": target},
            )
            if report.get("exportable") is not True:
                raise DemoSeedError(f"clean demo {solver} Neutral mapping was not exportable")
            card = api.post(
                f"/neutral-materials/{neutral_id}/solver-cards",
                {
                    "neutral_material_revision_id": neutral_revision_id,
                    "target": target,
                    "expected_mapping_report_sha256": _id(report, "mapping_report_sha256"),
                    "solver_material_id": solver_material_id,
                    "material_name": "CMP_DEMO_DP780_NEUTRAL",
                    "change_reason": (
                        f"Generate the clean demo {solver} card from the exact Neutral revision."
                    ),
                },
            )
        result[f"{solver}_neutral_solver_card_id"] = _id(card, "solver_card_id")
        result[f"{solver}_neutral_solver_card_revision_id"] = _revision_id(card)
    return result


def _ensure_bulk_bundle(
    api: DemoApi,
    *,
    material_id: str,
    selection_label: str = "CMP clean demo complete governed transfer",
) -> dict[str, str]:
    jobs = _items(api.get("/export-jobs"))
    for job in jobs:
        selection_id = job.get("export_selection_id")
        if not isinstance(selection_id, str):
            continue
        selection = api.get(f"/export-selections/{selection_id}")
        content = selection.get("current_revision", {}).get("content", {})
        if isinstance(content, Mapping) and content.get("selection_label") == selection_label:
            bundle_id = job.get("bundle_id")
            if isinstance(bundle_id, str) and job.get("state") == "succeeded":
                bundle = api.get(f"/export-bundles/{bundle_id}")
                return {
                    "export_selection_id": selection_id,
                    "export_job_id": _id(job, "export_job_id"),
                    "export_bundle_id": bundle_id,
                    "export_bundle_sha256": _id(bundle, "archive_sha256"),
                }

    candidates = _items(api.get(f"/bulk-export-candidates?material_id={material_id}"))
    required_kinds = {
        "test_data_json",
        "mapping_profile_json",
        "processing_recipe_json",
        "neutral_material_json",
        "neutral_solver_mapping_report",
        "neutral_solver_card_native",
    }
    available_kinds = {
        str(candidate.get("source", {}).get("kind"))
        for candidate in candidates
        if isinstance(candidate.get("source"), Mapping)
    }
    missing = required_kinds - available_kinds
    if missing:
        raise DemoSeedError(
            "clean demo Bulk Export discovery is missing " + ", ".join(sorted(missing))
        )
    selected = [
        candidate
        for candidate in candidates
        if candidate.get("source", {}).get("kind") in required_kinds
    ]
    selection = api.post(
        "/export-selections",
        {
            "classification": "internal",
            "selection_label": selection_label,
            "members": [
                {
                    "ordinal": ordinal,
                    "source": candidate["source"],
                    "required": True,
                    "archive_path": candidate["default_archive_path"],
                }
                for ordinal, candidate in enumerate(selected, 1)
            ],
            "change_reason": "Pin every exact clean-demo exchange representation.",
        },
    )
    job = api.post("/export-jobs", {"export_selection_id": _id(selection, "export_selection_id")})
    for _ in range(60):
        if job.get("state") in {"succeeded", "failed"}:
            break
        time.sleep(1)
        job = api.get(f"/export-jobs/{_id(job, 'export_job_id')}")
    if job.get("state") != "succeeded":
        raise DemoSeedError(f"clean demo Bulk Export job ended in {job.get('state')}")
    bundle_id = _id(job, "bundle_id")
    bundle = api.get(f"/export-bundles/{bundle_id}")
    return {
        "export_selection_id": _id(selection, "export_selection_id"),
        "export_job_id": _id(job, "export_job_id"),
        "export_bundle_id": bundle_id,
        "export_bundle_sha256": _id(bundle, "archive_sha256"),
    }


def seed_full_demo(base_url: str) -> dict[str, str]:
    api = DemoApi(base_url)
    api.wait_until_healthy()
    api.authenticate()
    metal = _find_by_content(
        _items(api.get("/materials?q=CMP-DEMO-DP780&limit=20")),
        "material_code",
        "CMP-DEMO-DP780",
    )
    if metal is None:
        raise DemoSeedError("normal demo seed did not create CMP-DEMO-DP780")
    metal_id = _id(metal, "material_id")
    polymer_id = _ensure_polymer_baseline(api)
    polymer_processing = _ensure_polymer_processing_card(api, material_id=polymer_id)
    elastomer_id = _ensure_elastomer_baseline(api)

    stamp = os.getenv("CMP_DEMO_FIXTURE_STAMP") or "t60-reference"
    os.environ["CMP_DEMO_FIXTURE_STAMP"] = stamp
    seed_viscoelastic_master_demo.BASE_URL = base_url
    seed_ogden_calibration_demo.BASE_URL = base_url
    if not _fixture_complete(
        api,
        material_id=polymer_id,
        specimen_prefix=f"TTS-{stamp}-",
        expected_count=6,
    ):
        seed_viscoelastic_master_demo.main()
    if not _fixture_complete(
        api,
        material_id=elastomer_id,
        specimen_prefix=f"OGDEN-{stamp}-",
        expected_count=4,
    ):
        seed_ogden_calibration_demo.main(promote=True)
    test_data = _ensure_test_json(api)
    processing = _ensure_processing_journey(api, test_data=test_data)
    neutral = _ensure_metal_neutral_and_cards(
        api,
        material_id=metal_id,
        processing_batch_id=processing["processing_batch_id"],
    )
    metal_detail = api.get(f"/materials/{metal_id}")
    metal_states = metal_detail.get("states")
    if (
        not isinstance(metal_states, list)
        or not metal_states
        or not isinstance(metal_states[0], Mapping)
    ):
        raise DemoSeedError("clean demo metal Material has no workflow State")
    metal_state = metal_states[0]
    catalog = _ensure_catalog_binding(
        api,
        material=metal,
        workflow_nodes=(
            {
                "kind": "material_state",
                "object_id": _id(metal_state, "material_state_id"),
                "revision_id": _revision_id(metal_state),
                "name": "DP780 reference Material State",
                "external_key": "CMP-DEMO-DP780-STATE",
                "parent_external_key": "CMP-DEMO-DP780",
            },
            {
                "kind": "test_data",
                "object_id": test_data["test_data_document_id"],
                "revision_id": test_data["test_data_document_revision_id"],
                "name": "DP780 canonical tensile Test JSON",
                "external_key": "CMP-DEMO-DP780-TEST-JSON-NODE",
                "parent_external_key": "CMP-DEMO-DP780-STATE",
            },
            {
                "kind": "processing_output",
                "object_id": processing["processing_output_id"],
                "revision_id": processing["processing_output_revision_id"],
                "name": "DP780 fitted hardening Processing Output",
                "external_key": "CMP-DEMO-DP780-PROCESSING",
                "parent_external_key": "CMP-DEMO-DP780-TEST-JSON-NODE",
            },
            {
                "kind": "material_model",
                "object_id": neutral["selected_material_model_id"],
                "revision_id": neutral["selected_material_model_revision_id"],
                "name": "DP780 tabulated-plasticity Material Model IR",
                "external_key": "CMP-DEMO-DP780-IR",
                "parent_external_key": "CMP-DEMO-DP780-PROCESSING",
            },
            {
                "kind": "neutral_material",
                "object_id": neutral["neutral_material_id"],
                "revision_id": neutral["neutral_material_revision_id"],
                "name": "DP780 canonical Neutral Material JSON",
                "external_key": "CMP-DEMO-DP780-NEUTRAL",
                "parent_external_key": "CMP-DEMO-DP780-IR",
            },
            {
                "kind": "neutral_solver_card",
                "object_id": neutral["abaqus_neutral_solver_card_id"],
                "revision_id": neutral["abaqus_neutral_solver_card_revision_id"],
                "name": "DP780 Abaqus native material card",
                "external_key": "CMP-DEMO-DP780-ABAQUS-CARD",
                "parent_external_key": "CMP-DEMO-DP780-NEUTRAL",
            },
            {
                "kind": "neutral_solver_card",
                "object_id": neutral["openradioss_neutral_solver_card_id"],
                "revision_id": neutral["openradioss_neutral_solver_card_revision_id"],
                "name": "DP780 OpenRadioss native material card",
                "external_key": "CMP-DEMO-DP780-OPENRADIOSS-CARD",
                "parent_external_key": "CMP-DEMO-DP780-NEUTRAL",
            },
        ),
    )
    bulk = _ensure_bulk_bundle(api, material_id=metal_id)
    polymer_bulk_source = _ensure_bulk_bundle(
        api,
        material_id=polymer_id,
        selection_label="CMP polymer Recipe to dual-solver governed transfer",
    )
    polymer_bulk = {f"polymer_{key}": value for key, value in polymer_bulk_source.items()}
    return {
        "metal_material_id": metal_id,
        "polymer_material_id": polymer_id,
        "elastomer_material_id": elastomer_id,
        **catalog,
        **test_data,
        **processing,
        **neutral,
        **bulk,
        **polymer_bulk,
        **polymer_processing,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Seed all public synthetic modeling journeys.")
    parser.add_argument(
        "--api-base-url",
        default=os.getenv("CMP_DEMO_API_BASE_URL", "http://127.0.0.1:8000/api/v1"),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    result = seed_full_demo(args.api_base_url)
    print(f"CMP full demo seed completed: {result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

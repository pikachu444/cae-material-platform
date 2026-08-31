"""Verify the clean three-family demo through protected HTTP resources."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import zipfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, cast

import httpx

MATERIALS = {
    "CMP-DEMO-DP780": ("tabulated-plasticity-models", {"abaqus", "openradioss"}),
    "CMP-DEMO-POLYMER-PRONY": ("linear-viscoelastic-models", {"abaqus"}),
    "CMP-DEMO-ELASTOMER-OGDEN": ("ogden-prony-models", {"abaqus", "openradioss"}),
}
EXPECTED_SYNTHETIC_STATE_ROUTE = "Synthetic reference preparation; not for engineering use"
FORBIDDEN_SYNTHETIC_STATE_ROUTE = "Synthetic reference production route"
CANONICAL_RECIPE_KEY = "cmp_demo_tensile_cleanup"
CANONICAL_BATCH_LABEL = "CMP clean demo canonical JSON batch · 2025 hardening contract"
HARDENING_EQUATION_CONTRACT = "altair-material-modeler-2025-v1"
HARDENING_FAMILIES = ["voce", "swift", "hockett_sherby", "ghosh"]
STATISTICS_ALIGNED_SELECTION_LABEL = "CMP demo DP780 aligned tensile replicates"
STATISTICS_PLAN_LABEL = "CMP demo DP780 replicate curve statistics"
MEANINGFUL_DEMO_TEST_RECORDS = {
    "CMP-246-TENSILE-ROOM": "DP780 room tensile",
    "CMP-246-TENSILE-HOT": "DP780 hot tensile",
    "CMP-246-TENSILE-SLOW": "DP780 slow tensile",
    "CMP-246-TENSILE-FAST": "DP780 fast tensile",
    "CMP-246-DMA-+00C": "Polymer DMA 000C",
    "CMP-246-DMA-+23C": "Polymer DMA 023C",
    "CMP-246-DMA-+60C": "Polymer DMA 060C",
    "CMP-246-FLD-NAKAJIMA": "DP780 Nakajima FLD",
    "CMP-246-FLD-MARCINIAK": "DP780 Marciniak FLD",
}
MEANINGFUL_DEMO_SIMULATION_RECORDS = {
    "CMP-246-EP-VOCE": "DP780 Voce model",
    "CMP-246-EP-TABULATED": (
        "DP780 tabulated model"
    ),
    "CMP-246-STAT-TENSILE": "DP780 tensile statistics",
}
MEANINGFUL_DEMO_BINDING_KINDS = {
    **{key: "test_data" for key in MEANINGFUL_DEMO_TEST_RECORDS},
    "CMP-246-EP-VOCE": "processing_output",
    "CMP-246-EP-TABULATED": "material_model",
    "CMP-246-STAT-TENSILE": None,
}
MEANINGFUL_DEMO_RECORD_DESCRIPTIONS = {
    **{key: None for key in MEANINGFUL_DEMO_TEST_RECORDS},
    "CMP-246-EP-VOCE": None,
    "CMP-246-EP-TABULATED": None,
    "CMP-246-STAT-TENSILE": None,
}
MEANINGFUL_DEMO_TECHNICAL_RECORDS = {
    "CMP-246-TECH-DP780": "DP780 technical data",
    "CMP-246-TECH-POLYMER": "Polymer technical data",
    "CMP-246-TECH-ELASTOMER": "Elastomer technical data",
}
SOURCE_V2_TECHNICAL_FAMILIES = {
    "CMP-246-TECH-DP780": "Metal",
    "CMP-246-TECH-POLYMER": "Plastic",
    "CMP-246-TECH-ELASTOMER": "Rubber",
}
SOURCE_V2_TECHNICAL_ATTRIBUTE_SECTIONS = {
    "data_information__record_name": "Data Information",
    "data_information__technical_data_id": "Data Information",
    "material_information__category": "Material Information",
    "material_information__details": "Material Information",
    "material_information__family": "Material Information",
    "material_information__grade": "Material Information",
    "material_information__orientation": "Material Information",
    "material_information__spec_thickness": "Material Information",
    "sample_information__applied_part": "Sample Information",
    "sample_information__applied_product": "Sample Information",
    "sample_information__density": "Sample Information",
    "sample_information__distributor": "Sample Information",
    "sample_information__manufacturer": "Sample Information",
    "sample_information__poisson_ratio": "Sample Information",
    "sample_information__primary_vendor": "Sample Information",
    "sample_information__production_date": "Sample Information",
    "sample_information__sales_type": "Sample Information",
    "sample_information__sample_type_id": "Sample Information",
}
CATALOG_DATA_CATEGORIES = (
    "technical_data",
    "test_data",
    "simulation_data",
    "solver_cards",
)
MEANINGFUL_DEMO_REPLICATE_KEYS = {
    "CMP-DEMO-DP780-TEST-JSON",
    "CMP-DEMO-DP780-TEST-JSON-02",
    "CMP-DEMO-DP780-TEST-JSON-03",
}


class ProcessingLineageError(ValueError):
    """The model projection does not resolve to one exact Processing execution."""


@dataclass(frozen=True, slots=True)
class ProcessingContractExecutionIdentity:
    """The exact execution/output tuple currently required by the demo contract.

    The verifier uses every field.  The optional fields make the pure resolver useful for
    focused checks that only have the stable execution identities available.
    """

    recipe_id: str | None = None
    recipe_revision_id: str | None = None
    recipe_sha256: str | None = None
    batch_id: str | None = None
    batch_member_id: str | None = None
    batch_attempt_id: str | None = None
    batch_attempt_no: int | None = None
    output_id: str | None = None
    output_revision_id: str | None = None
    output_sha256: str | None = None


@dataclass(frozen=True, slots=True)
class ProcessingLineageResolution:
    """Resolved immutable lineage and its relationship to the current contract execution."""

    recipe_id: str
    recipe_revision_id: str
    recipe_sha256: str
    batch_id: str
    batch_member_id: str
    batch_attempt_id: str
    batch_attempt_no: int
    output_id: str
    output_revision_id: str
    output_sha256: str
    batch: Mapping[str, Any]
    attempt: Mapping[str, Any]
    output: Mapping[str, Any]
    is_current_contract_execution: bool
    is_immutable_predecessor: bool

    @property
    def is_predecessor(self) -> bool:
        """Compatibility alias for callers that use the shorter state name."""

        return self.is_immutable_predecessor


def _required_text(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise ProcessingLineageError(f"{field} must be a non-empty string")
    return value


def _required_attempt_no(value: object, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ProcessingLineageError(f"{field} must be a positive integer")
    return value


def _normalise_sha256(value: object, *, field: str) -> str:
    digest = _required_text(value, field=field)
    return digest.removeprefix("sha256:")


def _mapping(value: object, *, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ProcessingLineageError(f"{field} must be an object")
    return value


def _identity_value(
    identity: Mapping[str, Any],
    *,
    nested: Mapping[str, Any] | None,
    keys: Sequence[str],
) -> object | None:
    for key in keys:
        if key in identity:
            return cast(object, identity[key])
    if nested is not None:
        for key in keys:
            if key in nested:
                return cast(object, nested[key])
    return None


def _current_identity(
    value: ProcessingContractExecutionIdentity | Mapping[str, Any],
) -> ProcessingContractExecutionIdentity:
    if isinstance(value, ProcessingContractExecutionIdentity):
        return value
    identity = _mapping(value, field="current contract execution/output identity")
    recipe = next(
        (
            candidate
            for key in ("processing_recipe", "recipe")
            if isinstance((candidate := identity.get(key)), Mapping)
        ),
        None,
    )
    batch = next(
        (
            candidate
            for key in ("processing_batch", "batch")
            if isinstance((candidate := identity.get(key)), Mapping)
        ),
        None,
    )
    attempt = next(
        (
            candidate
            for key in ("batch_attempt", "attempt")
            if isinstance((candidate := identity.get(key)), Mapping)
        ),
        None,
    )
    output = next(
        (
            candidate
            for key in ("processing_output", "output")
            if isinstance((candidate := identity.get(key)), Mapping)
        ),
        None,
    )

    def optional_text(keys: Sequence[str], nested: Mapping[str, Any] | None) -> str | None:
        found = _identity_value(identity, nested=nested, keys=keys)
        return None if found is None else _required_text(found, field=keys[0])

    def optional_digest(keys: Sequence[str], nested: Mapping[str, Any] | None) -> str | None:
        found = _identity_value(identity, nested=nested, keys=keys)
        return None if found is None else _normalise_sha256(found, field=keys[0])

    attempt_no_value = _identity_value(
        identity,
        nested=attempt,
        keys=("batch_attempt_no", "attempt_no"),
    )
    if attempt_no_value is not None:
        attempt_no = _required_attempt_no(attempt_no_value, field="batch_attempt_no")
    else:
        attempt_no = None
    return ProcessingContractExecutionIdentity(
        recipe_id=optional_text(("recipe_id", "processing_recipe_id"), recipe),
        recipe_revision_id=optional_text(
            ("recipe_revision_id", "processing_recipe_revision_id"), recipe
        ),
        recipe_sha256=optional_digest(("recipe_sha256", "processing_recipe_sha256"), recipe),
        batch_id=optional_text(("batch_id", "processing_batch_id"), batch),
        batch_member_id=optional_text(("batch_member_id", "processing_batch_member_id"), batch),
        batch_attempt_id=optional_text(
            ("batch_attempt_id", "processing_batch_attempt_id", "attempt_id"), attempt
        ),
        batch_attempt_no=attempt_no,
        output_id=optional_text(("output_id", "processing_output_id"), output),
        output_revision_id=optional_text(
            ("output_revision_id", "processing_output_revision_id"), output
        ),
        output_sha256=optional_digest(("output_sha256", "processing_output_sha256"), output),
    )


def resolve_processing_projection_lineage(
    processing_projection: Mapping[str, Any],
    batch_responses: Sequence[Mapping[str, Any]],
    processing_output_responses: Sequence[Mapping[str, Any]],
    current_contract_execution: ProcessingContractExecutionIdentity | Mapping[str, Any],
) -> ProcessingLineageResolution:
    """Resolve a projection through one exact immutable Recipe/Batch/Output execution.

    Every lookup is fail-closed: missing, duplicate, mismatched, or non-successful records are
    rejected.  A resolved tuple is either the supplied current contract execution or a distinct
    immutable predecessor; a predecessor may not reuse any current revision/execution/output ID.
    """

    projection = _mapping(processing_projection, field="processing_projection")
    recipe_batch = _mapping(
        projection.get("recipe_batch"), field="processing_projection.recipe_batch"
    )
    processing_recipe = _mapping(
        recipe_batch.get("processing_recipe"),
        field="processing_projection.recipe_batch.processing_recipe",
    )
    recipe_id = _required_text(processing_recipe.get("id"), field="processing recipe id")
    recipe_revision_id = _required_text(
        processing_recipe.get("revision_id"), field="processing recipe revision id"
    )
    recipe_sha256 = _normalise_sha256(
        processing_recipe.get("sha256"), field="processing recipe sha256"
    )
    batch_id = _required_text(recipe_batch.get("processing_batch_id"), field="processing batch id")
    batch_member_id = _required_text(
        recipe_batch.get("batch_member_id"), field="processing batch member id"
    )
    batch_attempt_id = _required_text(
        recipe_batch.get("batch_attempt_id"), field="processing batch attempt id"
    )
    batch_attempt_no = _required_attempt_no(
        recipe_batch.get("batch_attempt_no"), field="processing batch attempt no"
    )
    output_id = _required_text(projection.get("output_id"), field="processing output id")
    output_revision_id = _required_text(
        projection.get("output_revision_id"), field="processing output revision id"
    )
    output_sha256 = _normalise_sha256(
        projection.get("output_sha256"), field="processing output sha256"
    )

    matching_batches = [
        item
        for item in batch_responses
        if isinstance(item, Mapping) and item.get("batch_id") == batch_id
    ]
    if len(matching_batches) != 1:
        raise ProcessingLineageError(
            f"processing batch {batch_id} must resolve to exactly one response"
        )
    batch = matching_batches[0]
    if (
        batch.get("recipe_id") != recipe_id
        or batch.get("recipe_revision_id") != recipe_revision_id
        or _normalise_sha256(batch.get("recipe_sha256"), field="batch recipe sha256")
        != recipe_sha256
    ):
        raise ProcessingLineageError("processing batch recipe pin does not match the projection")

    members = batch.get("members")
    if not isinstance(members, list):
        raise ProcessingLineageError("processing batch has no member records")
    matching_members = [
        member
        for member in members
        if isinstance(member, Mapping) and member.get("member_id") == batch_member_id
    ]
    if len(matching_members) != 1:
        raise ProcessingLineageError(
            f"processing batch member {batch_member_id} must resolve to exactly one record"
        )

    attempts = batch.get("attempts")
    if not isinstance(attempts, list):
        raise ProcessingLineageError("processing batch has no attempt records")
    matching_attempts = [
        attempt
        for attempt in attempts
        if isinstance(attempt, Mapping)
        and attempt.get("attempt_id") == batch_attempt_id
        and attempt.get("member_id") == batch_member_id
    ]
    if len(matching_attempts) != 1:
        raise ProcessingLineageError(
            f"processing batch attempt {batch_attempt_id} must resolve to exactly one "
            "member attempt"
        )
    attempt = matching_attempts[0]
    if (
        attempt.get("status") != "succeeded"
        or attempt.get("attempt_no") != batch_attempt_no
        or attempt.get("output_id") != output_id
        or attempt.get("output_revision_id") != output_revision_id
    ):
        raise ProcessingLineageError(
            "processing batch attempt is not the successful exact projection output"
        )

    matching_outputs = [
        item
        for item in processing_output_responses
        if isinstance(item, Mapping) and item.get("processing_output_id") == output_id
    ]
    if len(matching_outputs) != 1:
        raise ProcessingLineageError(
            f"processing output {output_id} must resolve to exactly one response"
        )
    output = matching_outputs[0]
    output_revision = _mapping(
        output.get("current_revision"), field="processing output current revision"
    )
    if output_revision.get("id") != output_revision_id:
        raise ProcessingLineageError(
            "processing output current revision does not match the projection"
        )
    if (
        _normalise_sha256(output.get("output_sha256"), field="processing output sha256")
        != output_sha256
    ):
        raise ProcessingLineageError("processing output digest does not match the projection")

    current = _current_identity(current_contract_execution)
    resolved_values: dict[str, str | int] = {
        "recipe_id": recipe_id,
        "recipe_revision_id": recipe_revision_id,
        "recipe_sha256": recipe_sha256,
        "batch_id": batch_id,
        "batch_member_id": batch_member_id,
        "batch_attempt_id": batch_attempt_id,
        "batch_attempt_no": batch_attempt_no,
        "output_id": output_id,
        "output_revision_id": output_revision_id,
        "output_sha256": output_sha256,
    }
    current_values: dict[str, str | int] = {
        key: value
        for key, value in (
            ("recipe_id", current.recipe_id),
            ("recipe_revision_id", current.recipe_revision_id),
            ("recipe_sha256", current.recipe_sha256),
            ("batch_id", current.batch_id),
            ("batch_member_id", current.batch_member_id),
            ("batch_attempt_id", current.batch_attempt_id),
            ("batch_attempt_no", current.batch_attempt_no),
            ("output_id", current.output_id),
            ("output_revision_id", current.output_revision_id),
            ("output_sha256", current.output_sha256),
        )
        if value is not None
    }
    is_current = bool(current_values) and all(
        resolved_values[key] == value for key, value in current_values.items()
    )
    predecessor_identity_fields = (
        "recipe_revision_id",
        "batch_id",
        "batch_attempt_id",
        "output_id",
        "output_revision_id",
    )
    if not is_current and any(
        key in current_values and resolved_values[key] == current_values[key]
        for key in predecessor_identity_fields
    ):
        raise ProcessingLineageError(
            "immutable predecessor reuses a current recipe revision, batch, attempt, or "
            "output identity"
        )

    return ProcessingLineageResolution(
        recipe_id=recipe_id,
        recipe_revision_id=recipe_revision_id,
        recipe_sha256=recipe_sha256,
        batch_id=batch_id,
        batch_member_id=batch_member_id,
        batch_attempt_id=batch_attempt_id,
        batch_attempt_no=batch_attempt_no,
        output_id=output_id,
        output_revision_id=output_revision_id,
        output_sha256=output_sha256,
        batch=batch,
        attempt=attempt,
        output=output,
        is_current_contract_execution=is_current,
        is_immutable_predecessor=not is_current,
    )


# Keep the shorter name available to lightweight callers and focused tests.
resolve_processing_lineage = resolve_processing_projection_lineage


def _json(response: httpx.Response) -> dict[str, Any]:
    response.raise_for_status()
    value = response.json()
    if not isinstance(value, dict):
        raise RuntimeError(f"{response.request.url.path} did not return an object")
    return cast(dict[str, Any], value)


def _items(response: Mapping[str, Any]) -> list[dict[str, Any]]:
    value = response.get("items")
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _strict_items(response: Mapping[str, Any], *, stage: str) -> list[dict[str, Any]]:
    value = response.get("items")
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise RuntimeError(f"{stage} response has no complete item list")
    return cast(list[dict[str, Any]], value)


def _catalog_category_search(
    client: httpx.Client,
    category: str,
    *,
    text: str | None = None,
    limit: int = 100,
    published_only: bool = True,
) -> tuple[list[dict[str, Any]], int]:
    """Read one complete published category without manufacturing a Table scope."""

    if category not in CATALOG_DATA_CATEGORIES:
        raise ValueError(f"unsupported Catalog category {category!r}")
    payload: dict[str, Any] = {
        "table_id": None,
        "data_category": category,
        "offset": 0,
        "limit": limit,
        "published_only": published_only,
    }
    if text is not None:
        payload["text"] = text
    response = _json(client.post("/catalog/records:search", json=payload))
    items = _strict_items(response, stage=f"Catalog {category} search")
    total_count = response.get("total_count")
    if isinstance(total_count, bool) or not isinstance(total_count, int) or total_count < 0:
        raise RuntimeError(f"Catalog {category} search has no valid total_count")
    if response.get("offset") != 0 or response.get("limit") != limit:
        raise RuntimeError(f"Catalog {category} search did not preserve its requested page")
    if total_count != len(items):
        raise RuntimeError(
            f"Catalog {category} search is incomplete; total={total_count}; loaded={len(items)}"
        )
    return items, total_count


def _domain_binding_kinds(value: Mapping[str, Any]) -> tuple[str, ...]:
    kinds: list[str] = []
    bindings = value.get("domain_bindings")
    if isinstance(bindings, list):
        kinds.extend(
            str(binding["kind"])
            for binding in bindings
            if isinstance(binding, Mapping) and isinstance(binding.get("kind"), str)
        )
    binding = value.get("domain_binding")
    if isinstance(binding, Mapping) and isinstance(binding.get("kind"), str):
        kinds.append(str(binding["kind"]))
    return tuple(dict.fromkeys(kinds))


def _domain_binding_kind(value: Mapping[str, Any]) -> str | None:
    kinds = _domain_binding_kinds(value)
    return kinds[0] if kinds else None


def _exact_forward_link_target(
    links: Sequence[Mapping[str, Any]],
    *,
    source_record_id: str,
    source_record_revision_id: str,
    link_type_key: str,
    target_external_key: str,
    stage: str,
) -> Mapping[str, Any]:
    matches = [
        link
        for link in links
        if isinstance(link.get("current_revision"), Mapping)
        and isinstance(link["current_revision"].get("content"), Mapping)
        and link["current_revision"]["content"].get("active") is True
        and link["current_revision"]["content"].get("source_record_id")
        == source_record_id
        and link["current_revision"]["content"].get("source_record_revision_id")
        == source_record_revision_id
        and isinstance(link.get("link_type_revision"), Mapping)
        and isinstance(link["link_type_revision"].get("content"), Mapping)
        and link["link_type_revision"]["content"].get("key") == link_type_key
        and isinstance(link.get("target"), Mapping)
        and link["target"].get("external_key") == target_external_key
    ]
    if len(matches) != 1:
        raise RuntimeError(
            f"{stage} requires exactly one active exact-revision {link_type_key} link "
            f"to {target_external_key}; found={len(matches)}"
        )
    target = matches[0]["target"]
    if not isinstance(target.get("record_id"), str) or not isinstance(
        target.get("record_revision_id"), str
    ):
        raise RuntimeError(f"{stage} target does not expose an exact record revision")
    return cast(Mapping[str, Any], target)


def _content(value: Mapping[str, Any]) -> Mapping[str, Any]:
    revision = value.get("current_revision")
    content = revision.get("content") if isinstance(revision, Mapping) else None
    return content if isinstance(content, Mapping) else {}


def _meaningful_demo_records(
    records: Sequence[Mapping[str, Any]],
    *,
    expected_names: Mapping[str, str],
    stage: str,
    expected_descriptions: Mapping[str, str | None] | None = None,
    expected_binding_kinds: Mapping[str, str | None] | None = None,
) -> dict[str, Mapping[str, Any]]:
    """Fail closed when the small synthetic catalog story drifts or becomes ambiguous."""

    if expected_descriptions is not None and set(expected_descriptions) != set(expected_names):
        raise RuntimeError(f"{stage} expected description set is incomplete")
    if expected_binding_kinds is not None and set(expected_binding_kinds) != set(expected_names):
        raise RuntimeError(f"{stage} expected binding set is incomplete")

    by_key: dict[str, list[Mapping[str, Any]]] = {}
    for record in records:
        key = _content(record).get("external_key")
        if isinstance(key, str):
            by_key.setdefault(key, []).append(record)
    duplicates = sorted(key for key, matches in by_key.items() if len(matches) != 1)
    if duplicates:
        raise RuntimeError(f"{stage} has duplicate external keys: {', '.join(duplicates)}")
    missing = sorted(set(expected_names) - set(by_key))
    unexpected = sorted(set(by_key) - set(expected_names))
    if missing or unexpected:
        raise RuntimeError(
            f"{stage} record set differs; missing={missing}; unexpected={unexpected}"
        )

    result = {key: matches[0] for key, matches in by_key.items()}
    for key, expected_name in expected_names.items():
        record = result[key]
        revision = record.get("current_revision")
        content = _content(record)
        if not isinstance(revision, Mapping) or revision.get("revision_no") != 1:
            raise RuntimeError(f"{stage} {key} is not the clean exact r1 revision")
        if content.get("name") != expected_name:
            raise RuntimeError(
                f"{stage} {key} name differs; expected={expected_name!r}; "
                f"actual={content.get('name')!r}"
            )
        description = content.get("description")
        if expected_descriptions is None:
            if not isinstance(description, str) or not {
                "synthetic",
                "non-production",
            } <= set(description.lower().split()):
                raise RuntimeError(
                    f"{stage} {key} does not clearly identify synthetic non-production data"
                )
        elif description != expected_descriptions[key]:
            raise RuntimeError(
                f"{stage} {key} description differs; expected={expected_descriptions[key]!r}; "
                f"actual={description!r}"
            )
        expected_kind = (
            expected_binding_kinds[key]
            if expected_binding_kinds is not None
            else MEANINGFUL_DEMO_BINDING_KINDS[key]
        )
        kinds = _domain_binding_kinds(record)
        if expected_kind is None:
            if kinds:
                raise RuntimeError(f"{stage} {key} must remain distinct from domain bindings")
        elif expected_kind not in kinds:
            raise RuntimeError(
                f"{stage} {key} does not pin its expected {expected_kind} domain object"
            )
    return result


def _source_v2_technical_schema(
    table: Mapping[str, Any],
    attributes: Sequence[Mapping[str, Any]],
    layouts: Sequence[Mapping[str, Any]],
    *,
    stage: str,
) -> dict[str, str]:
    """Validate the generated source-v2 technical Layout and return its id-to-key map."""

    table_revision = table.get("current_revision")
    if not isinstance(table_revision, Mapping) or not isinstance(table_revision.get("id"), str):
        raise RuntimeError(f"{stage} Table has no exact current revision")
    table_revision_id = str(table_revision["id"])
    attribute_keys: dict[str, str] = {}
    attribute_revision_ids: dict[str, str] = {}
    for attribute in attributes:
        attribute_id = attribute.get("attribute_definition_id")
        revision = attribute.get("current_revision")
        content = _content(attribute)
        key = content.get("key")
        if (
            not isinstance(attribute_id, str)
            or not isinstance(revision, Mapping)
            or revision.get("revision_no") != 1
            or not isinstance(revision.get("id"), str)
            or not isinstance(key, str)
            or key in attribute_keys.values()
        ):
            raise RuntimeError(f"{stage} has a duplicate or non-r1 Attribute")
        attribute_keys[attribute_id] = key
        attribute_revision_ids[attribute_id] = str(revision["id"])
    if set(attribute_keys.values()) != set(SOURCE_V2_TECHNICAL_ATTRIBUTE_SECTIONS):
        raise RuntimeError(
            f"{stage} Attribute keys differ; "
            f"expected={sorted(SOURCE_V2_TECHNICAL_ATTRIBUTE_SECTIONS)}; "
            f"actual={sorted(attribute_keys.values())}"
        )

    matching_layouts = [
        layout
        for layout in layouts
        if layout.get("table_revision_id") == table_revision_id
    ]
    if len(matching_layouts) != 1:
        raise RuntimeError(
            f"{stage} requires exactly one Layout for the current Table revision; "
            f"found={len(matching_layouts)}"
        )
    layout = matching_layouts[0]
    layout_revision = layout.get("revision")
    layout_items = layout.get("items")
    if (
        layout.get("name") != "Technical Data default layout"
        or not isinstance(layout_revision, Mapping)
        or layout_revision.get("revision_no") != 1
        or not isinstance(layout_items, list)
        or any(not isinstance(item, Mapping) for item in layout_items)
    ):
        raise RuntimeError(f"{stage} does not expose the exact current default Layout")
    if len(layout_items) != len(attribute_keys):
        raise RuntimeError(f"{stage} Layout does not include every source-v2 Attribute")
    seen_keys: set[str] = set()
    seen_ordinals: set[int] = set()
    for item in layout_items:
        assert isinstance(item, Mapping)
        attribute_id = item.get("attribute_definition_id")
        key = attribute_keys.get(str(attribute_id))
        ordinal = item.get("ordinal")
        if (
            key is None
            or key in seen_keys
            or item.get("attribute_definition_revision_id")
            != attribute_revision_ids[str(attribute_id)]
            or item.get("section") != SOURCE_V2_TECHNICAL_ATTRIBUTE_SECTIONS[key]
            or isinstance(ordinal, bool)
            or not isinstance(ordinal, int)
            or ordinal in seen_ordinals
        ):
            raise RuntimeError(f"{stage} contains a stale, duplicated, or foreign Layout item")
        seen_keys.add(key)
        seen_ordinals.add(ordinal)
    if seen_keys != set(attribute_keys.values()) or seen_ordinals != set(
        range(len(attribute_keys))
    ):
        raise RuntimeError(
            f"{stage} Layout order is not a complete contiguous source-v2 projection"
        )
    return attribute_keys


def _source_v2_scalar_values(
    record: Mapping[str, Any],
    attribute_keys: Mapping[str, str],
    *,
    stage: str,
) -> dict[str, object]:
    values = _content(record).get("values")
    if not isinstance(values, list):
        raise RuntimeError(f"{stage} has no typed source-v2 values")
    result: dict[str, object] = {}
    for value in values:
        if not isinstance(value, Mapping):
            raise RuntimeError(f"{stage} contains an invalid typed value")
        key = attribute_keys.get(str(value.get("attribute_definition_id")))
        if key is None:
            raise RuntimeError(f"{stage} contains a value for an unknown Attribute")
        if key in result:
            raise RuntimeError(f"{stage} contains a duplicate value for {key}")
        if "value" not in value:
            # Number/file/curve/reference values are valid source-v2 fields, but
            # this helper only reads scalar technical identity/family projections.
            continue
        result[key] = value["value"]
    return result


def _model_and_pending_review(
    models: Sequence[Mapping[str, Any]],
    requests: Sequence[Mapping[str, Any]],
    *,
    label: str,
) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
    """Join one pending request to its exact immutable model revision and digest."""

    matches: list[tuple[Mapping[str, Any], Mapping[str, Any]]] = []
    for model in models:
        model_id = str(model.get("material_model_id"))
        revision = model.get("current_revision")
        if not isinstance(revision, Mapping):
            continue
        revision_id = str(revision.get("id"))
        for request in requests:
            if (
                request.get("aggregate_type") == "modeling.material_model"
                and request.get("aggregate_id") == model_id
                and request.get("revision_id") == revision_id
                and request.get("manifest_sha256") == revision.get("content_hash")
                and request.get("lifecycle_state") == "review"
                and request.get("decision") is None
            ):
                matches.append((model, request))
    if len(matches) != 1:
        raise RuntimeError(f"{label} does not have exactly one exact pending review request")
    return matches[0]


def verify_full_demo(base_url: str) -> dict[str, object]:
    with httpx.Client(base_url=base_url, timeout=60.0) as anonymous:
        token = str(_json(anonymous.get("/demo-identity/token"))["access_token"])
    result: dict[str, object] = {}
    with httpx.Client(
        base_url=base_url,
        headers={"Authorization": f"Bearer {token}"},
        timeout=60.0,
    ) as client:
        materials = _items(_json(client.get("/materials?limit=100")))
        for material_code, (model_path, required_solvers) in MATERIALS.items():
            material = next(
                (
                    item
                    for item in materials
                    if _content(item).get("material_code") == material_code
                ),
                None,
            )
            if material is None:
                raise RuntimeError(f"clean demo is missing {material_code}")
            material_id = str(material["material_id"])
            detail = _json(client.get(f"/materials/{material_id}"))
            states = detail.get("states")
            if not isinstance(states, list) or not states or not isinstance(states[0], dict):
                raise RuntimeError(f"{material_code} has no Material State")
            state_content = _content(states[0])
            route = state_content.get("manufacturing_route")
            if material_code == "CMP-DEMO-DP780" and (
                route != EXPECTED_SYNTHETIC_STATE_ROUTE or route == FORBIDDEN_SYNTHETIC_STATE_ROUTE
            ):
                raise RuntimeError(
                    f"{material_code} has an invalid synthetic State preparation label"
                )
            state_id = str(states[0]["material_state_id"])
            models = _items(_json(client.get(f"/material-states/{state_id}/{model_path}")))
            if not models:
                raise RuntimeError(f"{material_code} has no {model_path}")
            solvers: set[str] = set()
            selected_model = models[0]
            for candidate_model in models:
                candidate_model_id = str(candidate_model["material_model_id"])
                cards = _items(
                    _json(client.get(f"/{model_path}/{candidate_model_id}/solver-cards"))
                )
                candidate_solvers = {
                    str(target.get("solver"))
                    for item in cards
                    if isinstance((target := item.get("target")), Mapping)
                }
                solvers.update(candidate_solvers)
                if required_solvers <= candidate_solvers:
                    selected_model = candidate_model
            model = selected_model
            model_id = str(model["material_model_id"])
            missing = required_solvers - solvers
            if missing:
                raise RuntimeError(f"{material_code} is missing cards for {sorted(missing)}")
            revision = model.get("current_revision")
            result[material_code] = {
                "material_id": material_id,
                "material_state_id": state_id,
                "material_model_id": model_id,
                "material_model_revision_no": (
                    revision.get("revision_no") if isinstance(revision, Mapping) else None
                ),
                "solver_cards": sorted(solvers),
            }

        elastomer = next(
            item
            for item in materials
            if _content(item).get("material_code") == "CMP-DEMO-ELASTOMER-OGDEN"
        )
        elastomer_id = str(elastomer["material_id"])
        elastomer_neutral = None
        for candidate in _items(
            _json(client.get(f"/bulk-export-candidates?material_id={elastomer_id}"))
        ):
            source = candidate.get("source")
            if not isinstance(source, Mapping) or source.get("kind") != "neutral_material_json":
                continue
            neutral_id = source.get("neutral_material_id")
            if not isinstance(neutral_id, str):
                continue
            candidate_neutral = _json(client.get(f"/neutral-materials/{neutral_id}"))
            model_ir = candidate_neutral.get("document", {}).get("material_model_ir", {})
            if (
                isinstance(model_ir, Mapping)
                and model_ir.get("model_family") == "hyperelastic"
                and model_ir.get("constitutive_model", {}).get("family") == "ogden_1"
            ):
                elastomer_neutral = candidate_neutral
                break
        if elastomer_neutral is None:
            raise RuntimeError("clean demo elastomer has no reviewed Ogden Neutral JSON")
        elastomer_sources = elastomer_neutral["document"]["sources"]
        elastomer_datasets = elastomer_sources.get("datasets")
        if not isinstance(elastomer_datasets, list) or len(elastomer_datasets) != 4:
            raise RuntimeError("elastomer Neutral JSON does not pin four exact Datasets")
        roles = [item.get("role") for item in elastomer_datasets if isinstance(item, Mapping)]
        modes = {
            str(item.get("test_mode")) for item in elastomer_datasets if isinstance(item, Mapping)
        }
        if (
            roles.count("calibration") != 3
            or roles.count("holdout") != 1
            or modes
            != {
                "uniaxial_tension",
                "planar_tension",
                "biaxial_tension",
            }
        ):
            raise RuntimeError("elastomer Neutral JSON roles or test modes are incomplete")
        selection = elastomer_neutral["document"]["candidate_selection"]
        run_id = str(selection["calibration_run_id"])
        family_candidate_id = str(selection["candidate_id"])
        elastomer_run = _json(client.get(f"/ogden-calibration-runs/{run_id}"))
        families = elastomer_run.get("family_candidates")
        if (
            elastomer_run.get("calibration_curve_count") != 3
            or elastomer_run.get("holdout_curve_count") != 1
            or elastomer_run.get("test_mode_count") != 3
            or elastomer_run.get("candidate_count") != 8
            or not isinstance(families, list)
            or {item.get("family") for item in families if isinstance(item, Mapping)}
            != {"neo_hookean", "mooney_rivlin", "yeoh", "ogden_1"}
        ):
            raise RuntimeError("elastomer calibration Run is not the complete multi-mode fit")
        diagnostics = _json(
            client.get(f"/hyperelastic-family-candidates/{family_candidate_id}/diagnostics")
        )
        diagnostic_points = diagnostics.get("points")
        if not isinstance(diagnostic_points, list) or len(diagnostic_points) != 52:
            raise RuntimeError("elastomer family Candidate does not preserve 52 diagnostics points")
        prony = elastomer_neutral["document"]["material_model_ir"].get("prony_overlay")
        if (
            not isinstance(prony, Mapping)
            or prony.get("status") != "exact_revision"
            or not isinstance(prony.get("terms"), list)
            or len(prony["terms"]) != 2
        ):
            raise RuntimeError("elastomer Neutral JSON lost its exact two-term Prony overlay")
        elastomer_neutral_id = str(elastomer_neutral["neutral_material_id"])
        elastomer_cards = _items(
            _json(client.get(f"/neutral-materials/{elastomer_neutral_id}/solver-cards"))
        )
        elastomer_native: dict[str, str] = {}
        for solver, keyword in (
            ("abaqus", b"*HYPERELASTIC, OGDEN, N=1"),
            ("openradioss", b"/MAT/LAW62"),
        ):
            card = next(
                (
                    item
                    for item in elastomer_cards
                    if item.get("target", {}).get("solver") == solver
                ),
                None,
            )
            if card is None:
                raise RuntimeError(f"elastomer Neutral JSON has no {solver} native card")
            native = client.get(f"/neutral-solver-cards/{card['solver_card_id']}/download")
            native.raise_for_status()
            if keyword not in native.content:
                raise RuntimeError(f"elastomer {solver} card is missing its native keyword")
            elastomer_native[solver] = hashlib.sha256(native.content).hexdigest()
        result["elastomer_modeling_journey"] = {
            "neutral_material_id": elastomer_neutral_id,
            "calibration_plan_id": elastomer_sources["calibration_plan"]["id"],
            "calibration_run_id": run_id,
            "family_candidate_id": family_candidate_id,
            "dataset_count": len(elastomer_datasets),
            "diagnostics_point_count": len(diagnostic_points),
            "prony_term_count": len(prony["terms"]),
            "neutral_solver_card_sha256": elastomer_native,
        }

        polymer = next(
            item
            for item in materials
            if _content(item).get("material_code") == "CMP-DEMO-POLYMER-PRONY"
        )
        polymer_id = str(polymer["material_id"])
        polymer_detail = _json(client.get(f"/materials/{polymer_id}"))
        polymer_states = polymer_detail.get("states")
        if (
            not isinstance(polymer_states, list)
            or not polymer_states
            or not isinstance(polymer_states[0], Mapping)
        ):
            raise RuntimeError("clean demo polymer has no Material State")
        polymer_state_id = str(polymer_states[0]["material_state_id"])
        polymer_models = _items(
            _json(client.get(f"/material-states/{polymer_state_id}/linear-viscoelastic-models"))
        )
        polymer_recipe = next(
            item
            for item in _items(_json(client.get("/common-processing-recipes")))
            if item.get("content", {}).get("recipe_key") == "cmp_demo_polymer_prony"
        )
        polymer_batch = next(
            item
            for item in _items(_json(client.get("/common-processing-batches")))
            if item.get("label") == "CMP demo polymer Prony batch"
        )
        if polymer_batch.get("status") != "succeeded":
            raise RuntimeError("polymer Processing Recipe batch did not succeed")
        polymer_attempt = next(
            item
            for item in polymer_batch.get("attempts", [])
            if isinstance(item, Mapping) and item.get("status") == "succeeded"
        )
        polymer_output = next(
            item
            for item in _items(_json(client.get("/processing-outputs")))
            if item.get("processing_output_id") == polymer_attempt.get("output_id")
        )
        polymer_members = polymer_batch.get("members")
        polymer_source = (
            polymer_members[0].get("source")
            if isinstance(polymer_members, list)
            and len(polymer_members) == 1
            and isinstance(polymer_members[0], Mapping)
            else None
        )
        if (
            not isinstance(polymer_members, list)
            or len(polymer_members) != 1
            or not isinstance(polymer_members[0], Mapping)
            or not isinstance(polymer_source, Mapping)
            or polymer_source.get("fit_decision") is None
            or polymer_source.get("workup_overrides") != []
            or polymer_output.get("fit_decision") != polymer_source.get("fit_decision")
            or polymer_output.get("workup_overrides") != polymer_source.get("workup_overrides")
        ):
            raise RuntimeError("polymer batch/output did not preserve explicit fit evidence")
        processed_model = next(
            (
                item
                for item in polymer_models
                if isinstance(_content(item).get("processing_promotion_evidence"), Mapping)
                and _content(item)["processing_promotion_evidence"]
                .get("processing_output", {})
                .get("id")
                == polymer_output.get("processing_output_id")
            ),
            None,
        )
        if processed_model is None:
            raise RuntimeError("clean demo polymer has no exact Processing-promoted IR")
        processed_content = _content(processed_model)
        processing_evidence = processed_content["processing_promotion_evidence"]
        assert isinstance(processing_evidence, Mapping)
        terms = processed_content.get("terms")
        if (
            not isinstance(terms, list)
            or not 1 <= len(terms) <= 10
            or processing_evidence.get("selected_term_count") != len(terms)
        ):
            raise RuntimeError("processed polymer IR does not preserve selected Prony terms")
        exact_output = processing_evidence.get("processing_output")
        recipe_batch = processing_evidence.get("recipe_batch")
        exact_recipe = (
            recipe_batch.get("processing_recipe") if isinstance(recipe_batch, Mapping) else None
        )
        if (
            not isinstance(exact_output, Mapping)
            or exact_output.get("id") != polymer_output.get("processing_output_id")
            or exact_output.get("revision_id")
            != polymer_output.get("current_revision", {}).get("id")
            or exact_output.get("sha256") != polymer_output.get("output_sha256")
            or not isinstance(exact_recipe, Mapping)
            or exact_recipe.get("id") != polymer_recipe.get("processing_recipe_id")
            or exact_recipe.get("revision_id")
            != polymer_recipe.get("current_revision", {}).get("id")
            or not isinstance(recipe_batch, Mapping)
            or not isinstance(polymer_attempt, Mapping)
            or recipe_batch.get("processing_batch_id") != polymer_batch.get("batch_id")
            or recipe_batch.get("batch_attempt_id") != polymer_attempt.get("attempt_id")
        ):
            raise RuntimeError(
                "processed polymer IR does not pin the exact Recipe/Batch/Output execution"
            )
        polymer_candidates = _items(
            _json(client.get(f"/bulk-export-candidates?material_id={polymer_id}"))
        )
        polymer_neutral = None
        for candidate in polymer_candidates:
            source = candidate.get("source")
            if not isinstance(source, Mapping) or source.get("kind") != "neutral_material_json":
                continue
            candidate_id = source.get("neutral_material_id")
            if not isinstance(candidate_id, str):
                continue
            candidate_neutral = _json(client.get(f"/neutral-materials/{candidate_id}"))
            selection = candidate_neutral.get("document", {}).get("candidate_selection", {})
            candidate_recipe = (
                candidate_neutral.get("document", {})
                .get("sources", {})
                .get("processing_recipe", {})
                .get("reference", {})
            )
            if (
                isinstance(selection, Mapping)
                and selection.get("kind") == "prony_processing_output_selection"
                and isinstance(candidate_recipe, Mapping)
                and candidate_recipe.get("id") == polymer_recipe.get("processing_recipe_id")
            ):
                polymer_neutral = candidate_neutral
                break
        if polymer_neutral is None:
            raise RuntimeError("clean demo polymer has no Processing-selected Neutral JSON")
        polymer_neutral_id = str(polymer_neutral["neutral_material_id"])
        neutral_recipe = (
            polymer_neutral.get("document", {}).get("sources", {}).get("processing_recipe", {})
        )
        if (
            neutral_recipe.get("status") != "exact_revision"
            or neutral_recipe.get("reference", {}).get("id")
            != polymer_recipe.get("processing_recipe_id")
            or neutral_recipe.get("reference", {}).get("revision_id")
            != polymer_recipe.get("current_revision", {}).get("id")
        ):
            raise RuntimeError("polymer Neutral JSON does not pin the exact Processing Recipe")
        polymer_cards = _items(
            _json(client.get(f"/neutral-materials/{polymer_neutral_id}/solver-cards"))
        )
        polymer_native_cards: dict[str, dict[str, str]] = {}
        for solver, keyword in {
            "abaqus": b"*VISCOELASTIC, TIME=PRONY",
            "openradioss": b"/VISC/LPRONY/",
        }.items():
            polymer_card = next(
                (item for item in polymer_cards if item.get("target", {}).get("solver") == solver),
                None,
            )
            if polymer_card is None:
                raise RuntimeError(f"clean demo polymer Neutral JSON has no {solver} card")
            polymer_native = client.get(
                f"/neutral-solver-cards/{polymer_card['solver_card_id']}/download"
            )
            polymer_native.raise_for_status()
            if keyword not in polymer_native.content:
                raise RuntimeError(f"clean demo polymer native card omits {solver} Prony data")
            polymer_native_cards[solver] = {
                "solver_card_id": str(polymer_card["solver_card_id"]),
                "sha256": hashlib.sha256(polymer_native.content).hexdigest(),
            }
        polymer_bundle_id = None
        polymer_selection_content: Mapping[str, Any] | None = None
        for export_job in _items(_json(client.get("/export-jobs"))):
            selection_id = export_job.get("export_selection_id")
            if not isinstance(selection_id, str):
                continue
            export_selection = _json(client.get(f"/export-selections/{selection_id}"))
            selection_content = export_selection.get("current_revision", {}).get("content", {})
            if (
                isinstance(selection_content, Mapping)
                and selection_content.get("selection_label")
                == "CMP polymer Recipe to dual-solver governed transfer"
                and export_job.get("state") == "succeeded"
                and isinstance(export_job.get("bundle_id"), str)
            ):
                polymer_bundle_id = str(export_job["bundle_id"])
                polymer_selection_content = selection_content
                break
        if polymer_bundle_id is None or polymer_selection_content is None:
            raise RuntimeError("polymer Recipe-to-card Bulk ZIP was not generated")
        polymer_bundle = _json(client.get(f"/export-bundles/{polymer_bundle_id}"))
        required_kinds = {
            "test_data_json",
            "mapping_profile_json",
            "processing_recipe_json",
            "neutral_material_json",
            "neutral_solver_mapping_report",
            "neutral_solver_card_native",
        }
        component_kinds = {
            component.get("source", {}).get("kind")
            for component in polymer_selection_content.get("members", [])
            if isinstance(component, Mapping)
        }
        if not required_kinds <= component_kinds:
            raise RuntimeError("polymer Bulk ZIP omits a Recipe-to-card representation")
        result["polymer_processing_journey"] = {
            "processing_recipe_id": polymer_recipe["processing_recipe_id"],
            "processing_batch_id": polymer_batch["batch_id"],
            "processing_output_id": polymer_output["processing_output_id"],
            "material_model_id": processed_model["material_model_id"],
            "selected_term_count": len(terms),
            "neutral_material_id": polymer_neutral_id,
            "bulk_bundle_id": polymer_bundle_id,
            "bulk_component_count": polymer_bundle["component_count"],
            "solver_cards": polymer_native_cards,
        }

        dma_document = next(
            item
            for item in _items(_json(client.get("/test-data-documents")))
            if item.get("document_key") == "CMP-DEMO-POLYMER-DMA-JSON"
        )
        dma_profile = next(
            item
            for item in _items(_json(client.get("/mapping-profiles")))
            if item.get("content", {}).get("profile_key") == "polymer-dma-frequency"
        )
        dma_recipe = next(
            item
            for item in _items(_json(client.get("/common-processing-recipes")))
            if item.get("content", {}).get("recipe_key") == "cmp_demo_polymer_dma_prony"
        )
        dma_batch = next(
            item
            for item in _items(_json(client.get("/common-processing-batches")))
            if item.get("label") == "CMP demo polymer DMA Prony batch"
            and item.get("recipe_revision_id") == dma_recipe.get("current_revision", {}).get("id")
        )
        if dma_batch.get("status") != "succeeded":
            raise RuntimeError("polymer DMA Processing Recipe batch did not succeed")
        dma_attempt = next(
            item
            for item in dma_batch.get("attempts", [])
            if isinstance(item, Mapping) and item.get("status") == "succeeded"
        )
        dma_output = next(
            item
            for item in _items(_json(client.get("/processing-outputs")))
            if item.get("processing_output_id") == dma_attempt.get("output_id")
        )
        dma_members = dma_batch.get("members")
        dma_source = (
            dma_members[0].get("source")
            if isinstance(dma_members, list)
            and len(dma_members) == 1
            and isinstance(dma_members[0], Mapping)
            else None
        )
        if (
            not isinstance(dma_members, list)
            or len(dma_members) != 1
            or not isinstance(dma_members[0], Mapping)
            or not isinstance(dma_source, Mapping)
            or dma_source.get("fit_decision") is None
            or dma_source.get("workup_overrides") != []
            or dma_output.get("fit_decision") != dma_source.get("fit_decision")
            or dma_output.get("workup_overrides") != dma_source.get("workup_overrides")
        ):
            raise RuntimeError("DMA batch/output did not preserve explicit fit evidence")
        dma_model = next(
            (
                item
                for item in polymer_models
                if _content(item)
                .get("processing_promotion_evidence", {})
                .get("processing_output", {})
                .get("id")
                == dma_output.get("processing_output_id")
            ),
            None,
        )
        if dma_model is None:
            raise RuntimeError("clean demo polymer has no exact DMA-promoted IR")
        dma_content = _content(dma_model)
        dma_evidence = dma_content.get("processing_promotion_evidence", {})
        dma_terms = dma_content.get("terms")
        if (
            not isinstance(dma_evidence, Mapping)
            or dma_evidence.get("selected_term_count") != 2
            or not isinstance(dma_terms, list)
            or len(dma_terms) != 2
        ):
            raise RuntimeError("DMA IR does not preserve the joint storage/loss Prony selection")
        dma_neutral = None
        for candidate in polymer_candidates:
            source = candidate.get("source")
            if not isinstance(source, Mapping) or source.get("kind") != "neutral_material_json":
                continue
            candidate_id = source.get("neutral_material_id")
            if not isinstance(candidate_id, str):
                continue
            candidate_neutral = _json(client.get(f"/neutral-materials/{candidate_id}"))
            selection = candidate_neutral.get("document", {}).get("candidate_selection", {})
            if (
                isinstance(selection, Mapping)
                and selection.get("processing_output", {}).get("id")
                == dma_output.get("processing_output_id")
                and selection.get("selected_series")
                == "modulus.storage.prony.selected+modulus.loss.prony.selected"
            ):
                dma_neutral = candidate_neutral
                break
        if dma_neutral is None:
            raise RuntimeError("clean demo polymer has no DMA Neutral Material JSON")
        dma_sources = dma_neutral.get("document", {}).get("sources", {})
        dma_tests = dma_sources.get("datasets", []) if isinstance(dma_sources, Mapping) else []
        if (
            not isinstance(dma_tests, list)
            or len(dma_tests) != 1
            or dma_tests[0].get("test_mode") != "dma_frequency"
            or dma_sources.get("mapping_profile", {}).get("reference", {}).get("id")
            != dma_profile.get("mapping_profile_id")
        ):
            raise RuntimeError(
                "DMA Neutral JSON does not pin its exact test mode and Mapping Profile"
            )
        dma_cards = _items(
            _json(
                client.get(f"/neutral-materials/{dma_neutral['neutral_material_id']}/solver-cards")
            )
        )
        dma_native_cards: dict[str, dict[str, str]] = {}
        for solver, keyword in (
            ("abaqus", b"*VISCOELASTIC, TIME=PRONY"),
            ("openradioss", b"/VISC/LPRONY"),
        ):
            card = next(
                item for item in dma_cards if item.get("target", {}).get("solver") == solver
            )
            native = client.get(f"/neutral-solver-cards/{card['solver_card_id']}/download")
            native.raise_for_status()
            if keyword not in native.content:
                raise RuntimeError(f"DMA native card omits {solver} Prony data")
            dma_native_cards[solver] = {
                "solver_card_id": str(card["solver_card_id"]),
                "sha256": hashlib.sha256(native.content).hexdigest(),
            }
        result["polymer_dma_journey"] = {
            "test_data_document_id": dma_document["test_data_document_id"],
            "mapping_profile_id": dma_profile["mapping_profile_id"],
            "processing_recipe_id": dma_recipe["processing_recipe_id"],
            "processing_batch_id": dma_batch["batch_id"],
            "processing_output_id": dma_output["processing_output_id"],
            "material_model_id": dma_model["material_model_id"],
            "neutral_material_id": dma_neutral["neutral_material_id"],
            "selected_term_count": len(dma_terms),
            "solver_cards": dma_native_cards,
        }

        metal = next(
            item for item in materials if _content(item).get("material_code") == "CMP-DEMO-DP780"
        )
        metal_id = str(metal["material_id"])
        category_records: dict[str, list[dict[str, Any]]] = {}
        category_totals: dict[str, int] = {}
        expected_category_keys = {
            "technical_data": set(MEANINGFUL_DEMO_TECHNICAL_RECORDS),
            "test_data": set(MEANINGFUL_DEMO_TEST_RECORDS),
            "simulation_data": set(MEANINGFUL_DEMO_SIMULATION_RECORDS)
            - {"CMP-246-SOLVER-ABAQUS"},
            # A category result is one Catalog Record, even when that Record
            # owns both exact native cards.
            "solver_cards": {"CMP-246-EP-TABULATED"},
        }
        for category in CATALOG_DATA_CATEGORIES:
            found, total = _catalog_category_search(client, category)
            found_keys = {
                external_key
                for item in found
                if isinstance((external_key := _content(item).get("external_key")), str)
            }
            if found_keys != expected_category_keys[category]:
                raise RuntimeError(
                    f"clean demo {category} category differs; "
                    f"expected={sorted(expected_category_keys[category])}; "
                    f"actual={sorted(found_keys)}"
                )
            category_records[category] = found
            category_totals[category] = total

        meaningful_test_records = _meaningful_demo_records(
            category_records["test_data"],
            expected_names=MEANINGFUL_DEMO_TEST_RECORDS,
            stage="meaningful Demo Test Data",
            expected_descriptions={
                key: MEANINGFUL_DEMO_RECORD_DESCRIPTIONS[key]
                for key in MEANINGFUL_DEMO_TEST_RECORDS
            },
        )
        meaningful_simulation_records = _meaningful_demo_records(
            category_records["simulation_data"],
            expected_names=MEANINGFUL_DEMO_SIMULATION_RECORDS,
            stage="meaningful Demo Simulation Data",
            expected_descriptions={
                key: MEANINGFUL_DEMO_RECORD_DESCRIPTIONS[key]
                for key in MEANINGFUL_DEMO_SIMULATION_RECORDS
            },
        )
        meaningful_technical_records = _meaningful_demo_records(
            category_records["technical_data"],
            expected_names=MEANINGFUL_DEMO_TECHNICAL_RECORDS,
            stage="meaningful Demo Technical Data",
            expected_descriptions={key: None for key in MEANINGFUL_DEMO_TECHNICAL_RECORDS},
            expected_binding_kinds={key: "material" for key in MEANINGFUL_DEMO_TECHNICAL_RECORDS},
        )
        solver_category_record = next(
            item
            for item in category_records["solver_cards"]
            if _content(item).get("external_key") == "CMP-246-EP-TABULATED"
        )
        if "neutral_solver_card" not in _domain_binding_kinds(solver_category_record):
            raise RuntimeError("clean demo Solver Cards category is not owned by EP-TABULATED")

        tables = _items(_json(client.get("/catalog/tables")))
        technical_tables = [
            item
            for item in tables
            if _content(item).get("key") == "technical_data"
            and _content(item).get("data_category") == "technical_data"
        ]
        if len(technical_tables) != 1:
            raise RuntimeError(
                "clean demo must expose exactly one current source-v2 technical_data Table"
            )
        technical_table = technical_tables[0]
        table_revision = technical_table.get("current_revision")
        if (
            not isinstance(table_revision, Mapping)
            or not isinstance(technical_table.get("table_id"), str)
            or not isinstance(table_revision.get("id"), str)
            or table_revision.get("revision_no") != 1
        ):
            raise RuntimeError("clean demo source-v2 technical_data Table has no exact r1 revision")
        technical_table_id = str(technical_table["table_id"])
        technical_table_revision_id = str(table_revision["id"])
        searched = _json(
            client.post(
                "/catalog/records:search",
                json={
                    "table_id": technical_table_id,
                    "text": "CMP-246-TECH-DP780",
                    "limit": 20,
                    "published_only": True,
                },
            )
        )
        records = _strict_items(searched, stage="source-v2 DP780 technical_data search")
        if searched.get("total_count") != 1 or len(records) != 1:
            raise RuntimeError("clean demo DP780 technical_data record is missing or ambiguous")
        catalog_record = records[0]
        if (
            _content(catalog_record).get("external_key") != "CMP-246-TECH-DP780"
            or catalog_record.get("record_id")
            != meaningful_technical_records["CMP-246-TECH-DP780"].get("record_id")
        ):
            raise RuntimeError("clean demo DP780 technical_data search returned the wrong Record")
        catalog_revision = catalog_record.get("current_revision")
        if (
            not isinstance(catalog_revision, Mapping)
            or catalog_revision.get("revision_no") != 1
            or catalog_revision.get("content", {}).get("table_revision_id")
            != technical_table_revision_id
        ):
            raise RuntimeError("clean demo DP780 technical_data Record is not the exact Table r1")
        catalog_record_id = str(catalog_record["record_id"])
        catalog_record_revision_id = str(catalog_revision["id"])
        catalog_attributes = _items(
            _json(client.get(f"/catalog/tables/{technical_table_id}/attributes"))
        )
        catalog_layouts = _items(
            _json(client.get(f"/catalog/tables/{technical_table_id}/layouts"))
        )
        attribute_keys = _source_v2_technical_schema(
            technical_table,
            catalog_attributes,
            catalog_layouts,
            stage="clean demo source-v2 technical_data schema",
        )
        for technical_key, expected_family in SOURCE_V2_TECHNICAL_FAMILIES.items():
            record = meaningful_technical_records[technical_key]
            revision = record.get("current_revision")
            if not isinstance(revision, Mapping) or not isinstance(revision.get("id"), str):
                raise RuntimeError(f"clean demo {technical_key} has no exact Record revision")
            values = _source_v2_scalar_values(
                record,
                attribute_keys,
                stage=f"clean demo {technical_key} source-v2 values",
            )
            if (
                values.get("data_information__technical_data_id") != technical_key
                or values.get("material_information__family") != expected_family
            ):
                raise RuntimeError(f"clean demo {technical_key} has the wrong source-v2 projection")
            expected_material = {
                "CMP-246-TECH-DP780": metal,
                "CMP-246-TECH-POLYMER": polymer,
                "CMP-246-TECH-ELASTOMER": elastomer,
            }[technical_key]
            material_revision = expected_material.get("current_revision")
            if not isinstance(material_revision, Mapping) or not isinstance(
                material_revision.get("id"), str
            ):
                raise RuntimeError(f"clean demo {technical_key} has no exact Material revision")
            binding = _json(
                client.get(
                    f"/catalog/records/{record['record_id']}/revisions/{revision['id']}"
                    "/domain-binding"
                )
            )
            if (
                binding.get("kind") != "material"
                or binding.get("object_id") != expected_material.get("material_id")
                or binding.get("revision_id") != material_revision["id"]
            ):
                raise RuntimeError(f"clean demo {technical_key} binding is not the exact Material")
        material_links = _items(
            _json(
                client.get(
                    f"/catalog/records/{catalog_record_id}/links"
                    f"?revision_id={catalog_record_revision_id}"
                )
            )
        )
        dp780_direct_test_links = {
            "CMP-246-TENSILE-ROOM": "technical_to_tensile",
            "CMP-246-TENSILE-HOT": "technical_to_tensile",
            "CMP-246-TENSILE-SLOW": "technical_to_tensile",
            "CMP-246-TENSILE-FAST": "technical_to_tensile",
            "CMP-246-FLD-NAKAJIMA": "technical_to_fld",
            "CMP-246-FLD-MARCINIAK": "technical_to_fld",
        }
        dp780_test_targets: dict[str, Mapping[str, Any]] = {}
        for target_key, link_type_key in dp780_direct_test_links.items():
            target = _exact_forward_link_target(
                material_links,
                source_record_id=str(catalog_record["record_id"]),
                source_record_revision_id=str(catalog_revision["id"]),
                link_type_key=link_type_key,
                target_external_key=target_key,
                stage=f"DP780 Technical Data to {target_key}",
            )
            expected_record = meaningful_test_records[target_key]
            expected_revision = expected_record.get("current_revision")
            if (
                not isinstance(expected_revision, Mapping)
                or target.get("record_id") != expected_record.get("record_id")
                or target.get("record_revision_id") != expected_revision.get("id")
                or target.get("revision_no") != 1
                or "test_data" not in _domain_binding_kinds(target)
            ):
                raise RuntimeError(
                    f"DP780 Technical Data to {target_key} does not pin its clean exact "
                    "Test Data r1"
                )
            dp780_test_targets[target_key] = target
        fast_tensile = dp780_test_targets["CMP-246-TENSILE-FAST"]
        tensile_links = _items(
            _json(
                client.get(
                    f"/catalog/records/{fast_tensile['record_id']}/links"
                    f"?revision_id={fast_tensile['record_revision_id']}"
                )
            )
        )
        selected_model_record = _exact_forward_link_target(
            tensile_links,
            source_record_id=str(fast_tensile["record_id"]),
            source_record_revision_id=str(fast_tensile["record_revision_id"]),
            link_type_key="tensile_to_elastoplasticity",
            target_external_key="CMP-246-EP-TABULATED",
            stage="DP780 fast Tensile direct link",
        )
        if "material_model" not in _domain_binding_kinds(selected_model_record):
            raise RuntimeError("DP780 selected model link does not pin exact Material Model")
        if selected_model_record.get("revision_no") != 1:
            raise RuntimeError("DP780 selected model example is not the clean r1 revision")
        expected_selected_model = meaningful_simulation_records["CMP-246-EP-TABULATED"]
        expected_selected_revision = expected_selected_model.get("current_revision")
        if (
            not isinstance(expected_selected_revision, Mapping)
            or selected_model_record.get("record_id") != expected_selected_model.get("record_id")
            or selected_model_record.get("record_revision_id")
            != expected_selected_revision.get("id")
        ):
            raise RuntimeError(
                "DP780 fast Tensile direct link does not pin the discoverable selected-model record"
            )

        documents = _items(_json(client.get("/test-data-documents")))
        metal_replicates = [
            item
            for item in documents
            if str(item.get("document_key", "")).startswith("CMP-DEMO-DP780-TEST-JSON")
        ]
        metal_replicate_keys = {str(item.get("document_key")) for item in metal_replicates}
        if metal_replicate_keys != MEANINGFUL_DEMO_REPLICATE_KEYS:
            raise RuntimeError(
                "meaningful Demo Modeling repeats differ; "
                f"missing={sorted(MEANINGFUL_DEMO_REPLICATE_KEYS - metal_replicate_keys)}; "
                f"unexpected={sorted(metal_replicate_keys - MEANINGFUL_DEMO_REPLICATE_KEYS)}"
            )
        document = next(
            item for item in documents if item.get("document_key") == "CMP-DEMO-DP780-TEST-JSON"
        )
        document_revision = document.get("current_revision")
        if not isinstance(document_revision, Mapping):
            raise RuntimeError("clean demo Test JSON has no exact revision")
        downloaded_test = client.get(
            f"/test-data-documents/{document['test_data_document_id']}/revisions/"
            f"{document_revision['id']}/content"
        )
        downloaded_test.raise_for_status()
        canonical_test = downloaded_test.json()
        if canonical_test["material"]["grade"] != "DP780":
            raise RuntimeError("clean demo Test JSON did not preserve Material metadata")

        profile = next(
            item
            for item in _items(_json(client.get("/mapping-profiles")))
            if item.get("content", {}).get("profile_key") == "cmp_demo_tensile_json"
        )
        recipes = [
            item
            for item in _items(_json(client.get("/common-processing-recipes")))
            if item.get("content", {}).get("recipe_key") == CANONICAL_RECIPE_KEY
        ]
        if len(recipes) != 1:
            raise RuntimeError("clean demo must expose exactly one canonical Processing Recipe")
        recipe = recipes[0]
        recipe_content = recipe.get("content")
        recipe_revision = recipe.get("current_revision")
        if (
            not isinstance(recipe_content, Mapping)
            or recipe_content.get("lifecycle_state") != "published"
            or not isinstance(recipe_revision, Mapping)
            or not isinstance(recipe_revision.get("id"), str)
            or not isinstance(recipe_revision.get("content_hash"), str)
        ):
            raise RuntimeError(
                "clean demo canonical Processing Recipe is not an exact published revision"
            )
        recipe_steps = recipe_content.get("steps")
        if (
            not isinstance(recipe_steps, list)
            or not recipe_steps
            or not isinstance(recipe_steps[-1], Mapping)
            or recipe_steps[-1].get("method_id") != "metal.hardening_fit_extrapolate"
            or not isinstance(recipe_steps[-1].get("options"), Mapping)
        ):
            raise RuntimeError("clean demo canonical Recipe has no final hardening step")
        hardening_options = recipe_steps[-1]["options"]
        if (
            hardening_options.get("equation_contract") != HARDENING_EQUATION_CONTRACT
            or hardening_options.get("families") != HARDENING_FAMILIES
        ):
            raise RuntimeError("clean demo canonical Recipe has the wrong hardening contract")
        all_batch_responses = _items(_json(client.get("/common-processing-batches")))
        canonical_batches = [
            item
            for item in all_batch_responses
            if (
                item.get("label") == CANONICAL_BATCH_LABEL
                and item.get("recipe_id") == recipe.get("processing_recipe_id")
                and item.get("recipe_revision_id") == recipe_revision.get("id")
                and item.get("recipe_sha256") == recipe_revision.get("content_hash")
            )
        ]
        if len(canonical_batches) != 1:
            raise RuntimeError(
                "clean demo must expose exactly one canonical Batch pinned to the current Recipe"
            )
        batch = canonical_batches[0]
        if batch.get("status") != "succeeded":
            raise RuntimeError("clean demo Processing Batch did not succeed")
        succeeded_attempts = [
            item
            for item in batch.get("attempts", [])
            if isinstance(item, Mapping) and item.get("status") == "succeeded"
        ]
        if len(succeeded_attempts) != 1:
            raise RuntimeError("clean demo canonical Batch must have exactly one succeeded attempt")
        batch_attempt = succeeded_attempts[0]
        all_processing_output_responses = _items(_json(client.get("/processing-outputs")))
        matching_metal_outputs = [
            item
            for item in all_processing_output_responses
            if item.get("processing_output_id") == batch_attempt.get("output_id")
        ]
        if len(matching_metal_outputs) != 1:
            raise RuntimeError("clean demo canonical Batch output must resolve exactly once")
        metal_output = matching_metal_outputs[0]
        metal_members = batch.get("members")
        metal_source = (
            metal_members[0].get("source")
            if isinstance(metal_members, list)
            and len(metal_members) == 1
            and isinstance(metal_members[0], Mapping)
            else None
        )
        metal_workup = (
            metal_source.get("workup_overrides") if isinstance(metal_source, Mapping) else None
        )
        metal_output_revision = metal_output.get("current_revision")
        if (
            not isinstance(metal_members, list)
            or len(metal_members) != 1
            or not isinstance(metal_members[0], Mapping)
            or not isinstance(metal_source, Mapping)
            or not isinstance(metal_workup, list)
            or len(metal_workup) != 1
            or metal_workup[0].get("kind") != "necking_boundary"
            or metal_source.get("fit_decision") is None
            or metal_output.get("fit_decision") != metal_source.get("fit_decision")
            or metal_output.get("workup_overrides") != metal_workup
            or batch_attempt.get("member_id") != metal_members[0].get("member_id")
            or batch_attempt.get("output_id") != metal_output.get("processing_output_id")
            or not isinstance(metal_output_revision, Mapping)
            or batch_attempt.get("output_revision_id") != metal_output_revision.get("id")
        ):
            raise RuntimeError("metal batch/output did not preserve fit and necking evidence")
        metal_detail = _json(client.get(f"/materials/{metal_id}"))
        metal_states = metal_detail.get("states")
        if not isinstance(metal_states, list) or not metal_states:
            raise RuntimeError("clean demo metal Material has no State for Recipe evidence")
        metal_state_id = str(metal_states[0]["material_state_id"])
        replicate_selections = _items(
            _json(
                client.get(
                    "/dataset-selections/reference-tensile-replicates"
                    f"?material_state_id={metal_state_id}"
                )
            )
        )
        aligned_selection = next(
            (
                item
                for item in replicate_selections
                if item.get("selection_label") == STATISTICS_ALIGNED_SELECTION_LABEL
            ),
            None,
        )
        if aligned_selection is None:
            raise RuntimeError("clean demo has no exact aligned replicate Selection")
        aligned_revision = aligned_selection.get("current_revision")
        aligned_content = _content(aligned_selection)
        if (
            not isinstance(aligned_revision, Mapping)
            or not isinstance(aligned_revision.get("id"), str)
            or aligned_content.get("member_count") != 8
        ):
            raise RuntimeError(
                "clean demo aligned replicate Selection is not an exact n=8 revision"
            )
        statistics_plans = _items(
            _json(
                client.get(
                    "/replicate-statistical-plans"
                    f"?selection_revision_id={aligned_revision['id']}&limit=100"
                )
            )
        )
        distribution_plan = next(
            (
                item
                for item in statistics_plans
                if str(item.get("plan_label", "")).startswith(STATISTICS_PLAN_LABEL)
                and isinstance(_content(item).get("scalar_distribution"), Mapping)
            ),
            None,
        )
        if distribution_plan is None:
            raise RuntimeError("clean demo has no scalar-distribution Statistical Plan")
        distribution_plan_revision = distribution_plan.get("current_revision")
        distribution_options = _content(distribution_plan).get("scalar_distribution")
        if (
            not isinstance(distribution_plan_revision, Mapping)
            or not isinstance(distribution_plan_revision.get("id"), str)
            or not isinstance(distribution_options, Mapping)
            or distribution_options.get("seed") != 210
            or distribution_options.get("bootstrap_samples") != 999
            or distribution_options.get("unit_profile") is not None
        ):
            raise RuntimeError("clean demo scalar-distribution Plan has unexpected replay options")
        statistics_runs = _items(
            _json(
                client.get(
                    "/replicate-statistical-runs"
                    f"?plan_revision_id={distribution_plan_revision['id']}&limit=100"
                )
            )
        )
        distribution_run = next(
            (
                item
                for item in statistics_runs
                if item.get("status") == "succeeded"
                and isinstance(item.get("scalar_distribution_result_id"), str)
            ),
            None,
        )
        if distribution_run is None:
            raise RuntimeError("clean demo scalar-distribution Statistics Run did not succeed")
        distribution_result = _json(
            client.get(
                f"/scalar-distribution-results/{distribution_run['scalar_distribution_result_id']}"
            )
        )
        candidates = distribution_result.get("candidates")
        if (
            distribution_result.get("sample_count") != 8
            or distribution_result.get("scalar_feature") != "peak_engineering_stress_pa"
            or distribution_result.get("bootstrap_samples") != 999
            or distribution_result.get("artifact_sha256")
            != distribution_run.get("scalar_distribution_sha256")
            or not isinstance(candidates, list)
            or {item.get("family") for item in candidates if isinstance(item, Mapping)}
            != {"normal", "lognormal", "weibull"}
            or any(
                not isinstance(item, Mapping)
                or item.get("status") != "succeeded"
                or not isinstance(item.get("candidate_sha256"), str)
                for item in candidates
            )
        ):
            raise RuntimeError("clean demo scalar-distribution Result is incomplete")
        distribution_candidate_count = len(candidates)
        metal_models = _items(
            _json(client.get(f"/material-states/{metal_state_id}/tabulated-plasticity-models"))
        )
        metal_review_requests = _items(
            _json(client.get("/review-requests?aggregate_type=modeling.material_model&limit=200"))
        )
        metal_model, metal_review = _model_and_pending_review(
            metal_models,
            metal_review_requests,
            label="metal selected model",
        )
        if not isinstance(_content(metal_model).get("processing_projection"), Mapping):
            raise RuntimeError("metal selected model has no Processing projection")
        metal_projection = _content(metal_model)["processing_projection"]
        assert isinstance(metal_projection, Mapping)
        if not isinstance(metal_output_revision, Mapping):
            raise RuntimeError("clean demo canonical Processing Output has no current revision")
        metal_output_sha256 = metal_output.get("output_sha256")
        if not isinstance(metal_output_sha256, str) or not metal_output_sha256:
            raise RuntimeError("clean demo canonical Processing Output has no output digest")
        current_contract = ProcessingContractExecutionIdentity(
            recipe_id=str(recipe["processing_recipe_id"]),
            recipe_revision_id=str(recipe_revision["id"]),
            recipe_sha256=str(recipe_revision["content_hash"]),
            batch_id=str(batch["batch_id"]),
            batch_member_id=str(metal_members[0]["member_id"]),
            batch_attempt_id=str(batch_attempt["attempt_id"]),
            batch_attempt_no=(
                int(batch_attempt["attempt_no"])
                if isinstance(batch_attempt.get("attempt_no"), int)
                and not isinstance(batch_attempt.get("attempt_no"), bool)
                else None
            ),
            output_id=str(metal_output["processing_output_id"]),
            output_revision_id=str(metal_output_revision["id"]),
            output_sha256=metal_output_sha256,
        )
        metal_lineage = resolve_processing_projection_lineage(
            metal_projection,
            all_batch_responses,
            all_processing_output_responses,
            current_contract,
        )
        metal_recipe_batch = metal_projection.get("recipe_batch")
        exact_metal_recipe = (
            metal_recipe_batch.get("processing_recipe")
            if isinstance(metal_recipe_batch, Mapping)
            else None
        )
        if (
            not isinstance(exact_metal_recipe, Mapping)
            or exact_metal_recipe.get("id") != metal_lineage.recipe_id
            or exact_metal_recipe.get("revision_id") != metal_lineage.recipe_revision_id
            or not isinstance(metal_recipe_batch, Mapping)
            or not isinstance(batch_attempt, Mapping)
            or metal_recipe_batch.get("processing_batch_id") != metal_lineage.batch_id
            or metal_recipe_batch.get("batch_attempt_id") != metal_lineage.batch_attempt_id
            or metal_projection.get("output_id") != metal_lineage.output_id
            or metal_projection.get("output_revision_id") != metal_lineage.output_revision_id
        ):
            raise RuntimeError("metal IR does not pin the exact Recipe/Batch/Output execution")
        if metal_lineage.is_immutable_predecessor:
            current_claims = {
                "recipe_revision_id": current_contract.recipe_revision_id,
                "batch_id": current_contract.batch_id,
                "batch_attempt_id": current_contract.batch_attempt_id,
                "output_id": current_contract.output_id,
                "output_revision_id": current_contract.output_revision_id,
            }
            predecessor_claims = {
                "recipe_revision_id": metal_lineage.recipe_revision_id,
                "batch_id": metal_lineage.batch_id,
                "batch_attempt_id": metal_lineage.batch_attempt_id,
                "output_id": metal_lineage.output_id,
                "output_revision_id": metal_lineage.output_revision_id,
            }
            if any(
                current_value is not None and predecessor_claims[key] == current_value
                for key, current_value in current_claims.items()
            ):
                raise RuntimeError(
                    "metal predecessor IR claims a current Recipe/Batch/Attempt/Output identity"
                )

        candidates = _items(_json(client.get(f"/bulk-export-candidates?material_id={metal_id}")))
        metal_neutral: Mapping[str, Any] | None = None
        metal_neutral_id: str | None = None
        for candidate in candidates:
            source = candidate.get("source")
            if not isinstance(source, Mapping) or source.get("kind") != "neutral_material_json":
                continue
            candidate_id = source.get("neutral_material_id")
            if not isinstance(candidate_id, str):
                continue
            candidate_neutral = _json(client.get(f"/neutral-materials/{candidate_id}"))
            metal_document = candidate_neutral.get("document")
            if not isinstance(metal_document, Mapping):
                continue
            material_model_ir = metal_document.get("material_model_ir")
            sources = metal_document.get("sources")
            neutral_recipe = (
                sources.get("processing_recipe") if isinstance(sources, Mapping) else None
            )
            neutral_selection = metal_document.get("candidate_selection")
            neutral_output = (
                neutral_selection.get("processing_output")
                if isinstance(neutral_selection, Mapping)
                else None
            )
            neutral_output_sha256 = (
                neutral_selection.get("processing_output_sha256")
                if isinstance(neutral_selection, Mapping)
                else None
            )
            if (
                isinstance(material_model_ir, Mapping)
                and material_model_ir.get("model_family") == "isotropic_tabulated_plasticity"
                and isinstance(neutral_recipe, Mapping)
                and neutral_recipe.get("status") == "exact_revision"
                and neutral_recipe.get("reference", {}).get("id") == metal_lineage.recipe_id
                and neutral_recipe.get("reference", {}).get("revision_id")
                == metal_lineage.recipe_revision_id
                and isinstance(neutral_output, Mapping)
                and neutral_output.get("id") == metal_lineage.output_id
                and neutral_output.get("revision_id") == metal_lineage.output_revision_id
                and isinstance(neutral_output_sha256, str)
                and _normalise_sha256(
                    neutral_output_sha256, field="neutral processing output sha256"
                )
                == metal_lineage.output_sha256
            ):
                metal_neutral = candidate_neutral
                metal_neutral_id = candidate_id
                break
        if metal_neutral is None or metal_neutral_id is None:
            raise RuntimeError(
                "metal Neutral JSON does not pin the exact resolved Processing Recipe/Output"
            )
        neutral_download = client.get(f"/neutral-materials/{metal_neutral_id}/download")
        neutral_download.raise_for_status()
        if (
            hashlib.sha256(neutral_download.content).hexdigest()
            != metal_neutral["document_artifact"]["sha256"]
        ):
            raise RuntimeError("downloaded Neutral JSON digest does not match its Artifact")

        neutral_cards = _items(
            _json(client.get(f"/neutral-materials/{metal_neutral_id}/solver-cards"))
        )
        if len(neutral_cards) != 2:
            raise RuntimeError("clean demo Neutral JSON does not have exactly two native cards")
        neutral_solvers = {
            str(card.get("target", {}).get("solver")): card for card in neutral_cards
        }
        if set(neutral_solvers) != {"abaqus", "openradioss"}:
            raise RuntimeError("clean demo Neutral JSON does not have both native cards")
        neutral_revision_id = metal_neutral.get("neutral_material_revision_id")
        if not isinstance(neutral_revision_id, str):
            raise RuntimeError("clean demo Neutral JSON has no exact current revision")
        selected_model_id = selected_model_record.get("record_id")
        selected_model_revision_id = selected_model_record.get("record_revision_id")
        if not isinstance(selected_model_id, str) or not isinstance(
            selected_model_revision_id, str
        ):
            raise RuntimeError("DP780 selected model link has no exact Catalog revision")
        selected_bindings = _strict_items(
            _json(
                client.get(
                    f"/catalog/records/{selected_model_id}/revisions/"
                    f"{selected_model_revision_id}/domain-bindings"
                )
            ),
            stage="DP780 selected-model Catalog ownership",
        )
        bindings_by_kind: dict[str, list[Mapping[str, Any]]] = {}
        for selected_binding in selected_bindings:
            kind = selected_binding.get("kind")
            if (
                not isinstance(kind, str)
                or selected_binding.get("record_id") != selected_model_id
                or selected_binding.get("record_revision_id") != selected_model_revision_id
                or not isinstance(selected_binding.get("object_id"), str)
                or not isinstance(selected_binding.get("revision_id"), str)
            ):
                raise RuntimeError("DP780 selected-model Catalog ownership is not exact")
            bindings_by_kind.setdefault(kind, []).append(selected_binding)
        expected_binding_kinds = {"material_model", "neutral_material", "neutral_solver_card"}
        if set(bindings_by_kind) != expected_binding_kinds or any(
            len(bindings_by_kind[kind]) != (2 if kind == "neutral_solver_card" else 1)
            for kind in expected_binding_kinds
        ):
            raise RuntimeError(
                "DP780 selected-model Catalog ownership must contain one model, one Neutral, "
                "and two native-card bindings"
            )
        model_revision = metal_model.get("current_revision")
        if not isinstance(model_revision, Mapping) or not isinstance(model_revision.get("id"), str):
            raise RuntimeError("clean demo selected Material Model has no exact revision")
        model_binding = bindings_by_kind["material_model"][0]
        neutral_binding = bindings_by_kind["neutral_material"][0]
        if (
            model_binding.get("object_id") != metal_model.get("material_model_id")
            or model_binding.get("revision_id") != model_revision.get("id")
            or neutral_binding.get("object_id") != metal_neutral_id
            or neutral_binding.get("revision_id") != neutral_revision_id
        ):
            raise RuntimeError(
                "DP780 selected-model Catalog ownership does not pin the exact Model/Neutral"
            )
        selected_model_binding_summary: dict[str, Any] = {
            "material_model": {
                "object_id": str(model_binding["object_id"]),
                "revision_id": str(model_binding["revision_id"]),
            },
            "neutral_material": {
                "object_id": str(neutral_binding["object_id"]),
                "revision_id": str(neutral_binding["revision_id"]),
            },
        }
        card_binding_pairs: set[tuple[str, str]] = set()
        native_downloads: dict[str, str] = {}
        native_card_revisions: dict[str, str] = {}
        for solver, card in neutral_solvers.items():
            card_id = card.get("solver_card_id")
            card_revision = card.get("current_revision")
            card_target = card.get("target")
            if (
                not isinstance(card_id, str)
                or not isinstance(card_revision, Mapping)
                or not isinstance(card_revision.get("id"), str)
                or card_revision.get("revision_no") != 1
                or not isinstance(card_target, Mapping)
                or card.get("neutral_material_id") != metal_neutral_id
            ):
                raise RuntimeError(f"clean demo {solver} card has no exact Neutral pin")
            card_revision_id = str(card_revision["id"])
            exact_card = _json(
                client.get(
                    f"/neutral-solver-cards/{card_id}?revision_id={card_revision_id}"
                )
            )
            exact_card_revision = exact_card.get("current_revision")
            exact_card_content = (
                exact_card_revision.get("content")
                if isinstance(exact_card_revision, Mapping)
                else None
            )
            exact_target = exact_card.get("target")
            if (
                exact_card.get("solver_card_id") != card_id
                or exact_card.get("neutral_material_id") != metal_neutral_id
                or not isinstance(exact_card_revision, Mapping)
                or exact_card_revision.get("id") != card_revision_id
                or exact_card_revision.get("revision_no") != 1
                or exact_target != card_target
                or not isinstance(exact_card_content, Mapping)
                or exact_card_content.get("neutral_material_revision_id") != neutral_revision_id
            ):
                raise RuntimeError(f"clean demo {solver} card read-back lost its exact source pin")
            card_binding_pairs.add((card_id, card_revision_id))
            native = client.get(
                f"/neutral-solver-cards/{card_id}/download?revision_id={card_revision_id}"
            )
            native.raise_for_status()
            expected = card_revision.get("content", {}).get("card_sha256")
            if not isinstance(expected, str):
                raise RuntimeError(f"clean demo {solver} card has no committed digest")
            actual = hashlib.sha256(native.content).hexdigest()
            if actual != expected:
                raise RuntimeError(f"downloaded {solver} card digest does not match")
            native_downloads[solver] = actual
            native_card_revisions[solver] = card_revision_id
        card_bindings = bindings_by_kind["neutral_solver_card"]
        actual_card_binding_pairs = {
            (str(binding["object_id"]), str(binding["revision_id"]))
            for binding in card_bindings
        }
        if actual_card_binding_pairs != card_binding_pairs:
            raise RuntimeError(
                "DP780 selected-model Catalog ownership does not pin both exact native cards"
            )
        selected_model_binding_summary["neutral_solver_card"] = {
            solver: {
                "object_id": str(card["solver_card_id"]),
                "revision_id": native_card_revisions[solver],
            }
            for solver, card in neutral_solvers.items()
        }

        job = None
        for candidate_job in _items(_json(client.get("/export-jobs"))):
            selection_id = candidate_job.get("export_selection_id")
            if not isinstance(selection_id, str):
                continue
            candidate_selection = _json(client.get(f"/export-selections/{selection_id}"))
            candidate_content = candidate_selection.get("current_revision", {}).get("content", {})
            if (
                isinstance(candidate_content, Mapping)
                and candidate_content.get("selection_label")
                == "CMP clean demo complete governed transfer"
                and candidate_job.get("state") == "succeeded"
                and candidate_job.get("bundle_id")
            ):
                job = candidate_job
                break
        if job is None:
            raise RuntimeError("clean demo metal Bulk ZIP was not generated")
        bundle_id = str(job["bundle_id"])
        bundle = _json(client.get(f"/export-bundles/{bundle_id}"))
        authorization = _json(client.post(f"/export-bundles/{bundle_id}/download-authorizations"))
        parsed_base = httpx.URL(base_url)
        authority = parsed_base.host
        if parsed_base.port is not None:
            authority = f"{authority}:{parsed_base.port}"
        transfer_url = (
            f"{parsed_base.scheme}://{authority}/{str(authorization['transfer_url']).lstrip('/')}"
        )
        archive = httpx.get(
            transfer_url,
            headers={
                "Authorization": f"Bearer {token}",
                "Artifact-Transfer-Token": authorization["transfer_token"],
            },
            timeout=60.0,
        )
        archive.raise_for_status()
        archive_digest = hashlib.sha256(archive.content).hexdigest()
        if f"sha256:{archive_digest}" != bundle["archive_sha256"]:
            raise RuntimeError("downloaded Bulk ZIP digest does not match its committed Bundle")
        with zipfile.ZipFile(io.BytesIO(archive.content)) as package:
            names = set(package.namelist())
            if {"manifest.json", "checksums.sha256", "README.txt"} - names:
                raise RuntimeError(
                    "clean demo Bulk ZIP is missing its governed sidecars: "
                    + ", ".join(sorted(names))
                )
            manifest = json.loads(package.read("manifest.json"))

        result["clean_product_journey"] = {
            "catalog_record_id": catalog_record_id,
            "catalog_record_revision_id": catalog_record_revision_id,
            "catalog_record_key": "CMP-246-TECH-DP780",
            "catalog_category_searches": {
                category: {
                    "category": category,
                    "published_only": True,
                    "total_count": category_totals[category],
                    "loaded_count": len(category_records[category]),
                    "external_keys": sorted(
                        str(_content(item).get("external_key"))
                        for item in category_records[category]
                    ),
                }
                for category in CATALOG_DATA_CATEGORIES
            },
            "catalog_direct_link_path": [
                _content(catalog_record).get("external_key"),
                fast_tensile.get("external_key"),
                selected_model_record.get("external_key"),
            ],
            "test_data_document_id": document["test_data_document_id"],
            "metal_test_data_replicate_count": len(metal_replicates),
            "representative_tensile_records": sorted(
                key for key in meaningful_test_records if key.startswith("CMP-246-TENSILE-")
            ),
            "representative_fld_records": sorted(
                key for key in meaningful_test_records if key.startswith("CMP-246-FLD-")
            ),
            "selected_model_record_key": "CMP-246-EP-TABULATED",
            "selected_model_record_id": selected_model_id,
            "selected_model_record_revision_id": selected_model_revision_id,
            "selected_model_bindings": selected_model_binding_summary,
            "scalar_distribution_result_id": distribution_result["scalar_distribution_result_id"],
            "scalar_distribution_candidate_count": distribution_candidate_count,
            "mapping_profile_id": profile["mapping_profile_id"],
            "processing_recipe_id": recipe["processing_recipe_id"],
            "processing_batch_id": batch["batch_id"],
            "processing_batch_attempt_id": batch_attempt["attempt_id"],
            "metal_model_schema_version": _content(metal_model)["model_schema_version"],
            "review_request_id": metal_review["review_request_id"],
            "neutral_material_id": metal_neutral_id,
            "neutral_solver_card_sha256": native_downloads,
            "bulk_bundle_id": bundle_id,
            "bulk_bundle_sha256": archive_digest,
            "bulk_component_count": len(manifest["components"]),
        }
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify the clean public synthetic demo.")
    parser.add_argument(
        "--api-base-url",
        default=os.getenv("CMP_DEMO_API_BASE_URL", "http://127.0.0.1:8000/api/v1"),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    result = verify_full_demo(_parser().parse_args(argv).api_base_url)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

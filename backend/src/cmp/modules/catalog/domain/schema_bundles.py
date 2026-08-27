"""Deterministic Schema Definition Bundle validation, resolution, and Catalog projection."""

from __future__ import annotations

import json
import math
import re
from collections import Counter, defaultdict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from heapq import heappop, heappush
from typing import Any, cast
from urllib.parse import unquote
from uuid import UUID

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

from cmp.modules.identity_access.domain.authorization import DataClassification
from cmp.modules.units.domain.system import UnitError, canonical_unit_id
from cmp.shared.domain.revisions import canonical_json_bytes, content_sha256

BUNDLE_CONTRACT_ID = "https://cmp.example/contracts/catalog/schema-definition-bundle.schema.json"
BUNDLE_CONTRACT_VERSION = "1.0.0"
PLAN_CONTRACT_ID = "https://cmp.example/contracts/catalog/schema-definition-plan.schema.json"
PLAN_CONTRACT_VERSION = "1.0.0"
JSON_SCHEMA_2020_12 = "https://json-schema.org/draft/2020-12/schema"

_KEY = re.compile(r"^[a-z][a-z0-9_]{0,62}[a-z0-9]$|^[a-z]$")
_SEMVER = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
_UNIT = re.compile(r"^[A-Za-z0-9%_.*/^()\[\]{}'+-]{1,64}$")
_UUID_VALUE_PATTERN = (
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)
_ALLOWED_MEDIA_TYPES = frozenset(
    {
        "application/json",
        "application/schema+json",
        "application/vnd.cmp.catalog-schema-definition-bundle+json",
    }
)
_SCHEMA_KEYS = frozenset(
    {
        "$schema",
        "$id",
        "$defs",
        "$ref",
        "type",
        "title",
        "description",
        "properties",
        "required",
        "additionalProperties",
        "enum",
        "minimum",
        "maximum",
        "minLength",
        "maxLength",
        "pattern",
        "format",
        "x-business-key",
        "x-id-rule",
        "x-reference",
        "x-curve",
        "x-unit",
        "x-quantity",
        "x-suggested-values",
        "x-indexed",
        "x-searchable",
        "x-source-origin",
    }
)
_REFERENCE_KEYS = frozenset(
    {
        "link_key",
        "forward_label",
        "reverse_label",
        "source_cardinality",
        "target_cardinality",
    }
)
_REF_SIBLING_KEYS = frozenset(
    {
        "$ref",
        "$defs",
        "title",
        "description",
        "x-business-key",
        "x-id-rule",
        "x-reference",
        "x-curve",
        "x-unit",
        "x-quantity",
        "x-suggested-values",
        "x-indexed",
        "x-searchable",
        "x-source-origin",
    }
)
_REFERENCE_OPTIONAL_KEYS = frozenset(
    {"source_table_key", "target_table_key", "reference_only"}
)
_EXPLICIT_LEGACY_SCHEMA_UNITS = frozenset({"Hz"})
_ACTION_ORDER = {
    "database": 0,
    "profile": 1,
    "table": 2,
    "attribute": 3,
    "layout": 4,
    "profile_table_placement": 5,
    "link_type": 6,
    "bundle": 7,
}


class PlanDisposition(StrEnum):
    CREATE = "create"
    UPDATE = "update"
    NO_OP = "no-op"
    CONFLICT = "conflict"
    ERROR = "error"


class DiagnosticSeverity(StrEnum):
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class BundleDiagnostic:
    severity: DiagnosticSeverity
    code: str
    location: str
    message: str
    remediation: str

    def canonical(self) -> dict[str, Any]:
        return {
            "severity": self.severity.value,
            "code": self.code,
            "location": self.location,
            "message": self.message,
            "remediation": self.remediation,
        }


@dataclass(frozen=True, slots=True)
class BundleScope:
    organization_id: UUID
    project_id: UUID
    classification: DataClassification


@dataclass(frozen=True, slots=True)
class CatalogDefinition:
    key: str
    name: str
    description: str | None


@dataclass(frozen=True, slots=True)
class RecordSchemaDefinition:
    key: str
    name: str
    description: str | None
    schema_sha256: str
    schema: dict[str, Any]
    schema_version: str | None = None
    data_category: str | None = None

    @property
    def schema_id(self) -> str:
        return cast(str, self.schema["$id"])


@dataclass(frozen=True, slots=True)
class SchemaDefinitionBundle:
    bundle_key: str
    bundle_version: str
    scope: BundleScope
    database: CatalogDefinition
    profile: CatalogDefinition
    record_schemas: tuple[RecordSchemaDefinition, ...]
    dependency_order: tuple[str, ...]
    unit_profiles: tuple[dict[str, Any], ...] = ()

    def summary(self) -> dict[str, Any]:
        return {
            "bundle_key": self.bundle_key,
            "bundle_version": self.bundle_version,
            "scope": {
                "organization_id": str(self.scope.organization_id),
                "project_id": str(self.scope.project_id),
                "classification": self.scope.classification.value,
            },
            "database_key": self.database.key,
            "profile_key": self.profile.key,
            "record_schema_count": len(self.record_schemas),
            "unit_profile_count": len(self.unit_profiles),
            "dependency_order": list(self.dependency_order),
        }


@dataclass(frozen=True, slots=True)
class SourceArtifactIdentity:
    artifact_id: UUID
    organization_id: UUID
    project_id: UUID
    classification: DataClassification
    media_type: str
    size_bytes: int
    sha256: str

    def canonical(self) -> dict[str, Any]:
        return {
            "artifact_id": str(self.artifact_id),
            "organization_id": str(self.organization_id),
            "project_id": str(self.project_id),
            "classification": self.classification.value,
            "media_type": self.media_type,
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
        }


@dataclass(frozen=True, slots=True)
class CatalogStateObject:
    target_type: str
    external_key: str
    parent_external_key: str | None
    object_id: UUID | None
    revision_id: UUID | None
    content_hash: str
    published: bool
    content: dict[str, Any]
    dependency_heads_match: bool = True
    classification: DataClassification | None = None
    has_current_records: bool = False
    has_current_values: bool = False

    def key(self) -> tuple[str, str | None, str]:
        return self.target_type, self.parent_external_key, self.external_key

    def canonical(self) -> dict[str, Any]:
        return {
            "target_type": self.target_type,
            "external_key": self.external_key,
            "parent_external_key": self.parent_external_key,
            "object_id": str(self.object_id) if self.object_id is not None else None,
            "revision_id": str(self.revision_id) if self.revision_id is not None else None,
            "content_hash": self.content_hash,
            "published": self.published,
            "content": self.content,
            "dependency_heads_match": self.dependency_heads_match,
            "classification": self.classification.value
            if self.classification is not None
            else None,
            "has_current_records": self.has_current_records,
            "has_current_values": self.has_current_values,
        }


@dataclass(frozen=True, slots=True)
class CatalogSnapshot:
    organization_id: UUID
    project_id: UUID
    objects: tuple[CatalogStateObject, ...]

    @property
    def fingerprint(self) -> str:
        ordered = sorted(
            (item.canonical() for item in self.objects),
            key=lambda item: (
                _ACTION_ORDER.get(cast(str, item["target_type"]), 99),
                cast(str | None, item["parent_external_key"]) or "",
                cast(str, item["external_key"]),
                cast(str | None, item["object_id"]) or "",
            ),
        )
        return content_sha256(
            {
                "organization_id": str(self.organization_id),
                "project_id": str(self.project_id),
                "objects": ordered,
            }
        )


@dataclass(frozen=True, slots=True)
class ProjectedCatalogObject:
    target_type: str
    external_key: str
    parent_external_key: str | None
    content: dict[str, Any]
    dependencies: tuple[tuple[str, str | None, str], ...] = ()

    def key(self) -> tuple[str, str | None, str]:
        return self.target_type, self.parent_external_key, self.external_key


@dataclass(frozen=True, slots=True)
class CurrentPlanIdentity:
    object_id: UUID | None
    revision_id: UUID | None
    content_hash: str
    published: bool

    @classmethod
    def from_state(cls, value: CatalogStateObject) -> CurrentPlanIdentity:
        return cls(value.object_id, value.revision_id, value.content_hash, value.published)

    def canonical(self) -> dict[str, Any]:
        return {
            "id": str(self.object_id) if self.object_id is not None else None,
            "revision_id": str(self.revision_id) if self.revision_id is not None else None,
            "content_hash": self.content_hash,
            "published": self.published,
        }


@dataclass(frozen=True, slots=True)
class SchemaBundlePlanAction:
    sequence: int
    disposition: PlanDisposition
    target_type: str
    external_key: str
    parent_external_key: str | None
    current: CurrentPlanIdentity | None
    projected: dict[str, Any] | None
    reason_codes: tuple[str, ...]

    def canonical(self) -> dict[str, Any]:
        return {
            "sequence": self.sequence,
            "disposition": self.disposition.value,
            "target_type": self.target_type,
            "external_key": self.external_key,
            "parent_external_key": self.parent_external_key,
            "current": self.current.canonical() if self.current is not None else None,
            "projected": self.projected,
            "reason_codes": list(self.reason_codes),
        }


@dataclass(frozen=True, slots=True)
class SchemaBundlePlan:
    source_artifact: SourceArtifactIdentity
    bundle: SchemaDefinitionBundle | None
    catalog_snapshot_fingerprint: str
    actions: tuple[SchemaBundlePlanAction, ...]
    diagnostics: tuple[BundleDiagnostic, ...]
    plan_fingerprint: str

    @property
    def valid(self) -> bool:
        return not any(
            item.severity is DiagnosticSeverity.ERROR for item in self.diagnostics
        ) and not any(
            item.disposition in {PlanDisposition.CONFLICT, PlanDisposition.ERROR}
            for item in self.actions
        )

    def canonical(self, *, include_fingerprint: bool = True) -> dict[str, Any]:
        counts = {item.value: 0 for item in PlanDisposition}
        for action in self.actions:
            counts[action.disposition.value] += 1
        value: dict[str, Any] = {
            "$schema": PLAN_CONTRACT_ID,
            "contract_version": PLAN_CONTRACT_VERSION,
            "source_artifact": self.source_artifact.canonical(),
            "bundle": self.bundle.summary() if self.bundle is not None else None,
            "catalog_snapshot_fingerprint": self.catalog_snapshot_fingerprint,
            "plan_fingerprint": self.plan_fingerprint if include_fingerprint else None,
            "valid": self.valid,
            "action_counts": counts,
            "actions": [item.canonical() for item in self.actions],
            "diagnostics": [item.canonical() for item in self.diagnostics],
            "mutations_applied": False,
            "delete_missing": False,
            "write_set": [],
        }
        if not include_fingerprint:
            del value["plan_fingerprint"]
        return value


class _DuplicateJsonKey(ValueError):
    pass


def _pairs(pairs: Sequence[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise _DuplicateJsonKey(key)
        value[key] = item
    return value


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON number {value} is not supported")


def _escape_pointer(value: str) -> str:
    return value.replace("~", "~0").replace("/", "~1")


def _location(*parts: str | int) -> str:
    return "".join(f"/{_escape_pointer(str(part))}" for part in parts)


def _error(
    code: int,
    location: str,
    message: str,
    remediation: str,
) -> BundleDiagnostic:
    return BundleDiagnostic(
        DiagnosticSeverity.ERROR,
        f"CMP-SCHEMA-BUNDLE-{code:04d}",
        location,
        message,
        remediation,
    )


def _is_text(value: object, *, maximum: int) -> bool:
    return (
        isinstance(value, str)
        and bool(value)
        and value == value.strip()
        and len(value) <= maximum
        and "\x00" not in value
    )


def _is_finite_number(value: object) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return True
    return isinstance(value, float) and math.isfinite(value)


def _exact_keys(
    value: Mapping[str, Any],
    *,
    required: frozenset[str],
    allowed: frozenset[str],
    location: str,
    diagnostics: list[BundleDiagnostic],
) -> bool:
    valid = True
    for key in sorted(required - set(value)):
        diagnostics.append(
            _error(2, location, f"Required member '{key}' is missing.", f"Add '{key}'.")
        )
        valid = False
    for key in sorted(set(value) - allowed):
        diagnostics.append(
            _error(
                10,
                f"{location}/{_escape_pointer(key)}",
                f"Member '{key}' is not supported by Bundle v1.",
                "Remove the member or use a supported, versioned keyword.",
            )
        )
        valid = False
    return valid


def _validate_schema_type(
    value: object, location: str, diagnostics: list[BundleDiagnostic]
) -> tuple[str, bool] | None:
    allowed = {"object", "string", "number", "integer", "boolean", "null"}
    if isinstance(value, str):
        if value in allowed:
            return value, False
    elif (
        isinstance(value, list)
        and len(value) == 2
        and all(isinstance(item, str) for item in value)
        and len(set(cast(list[str], value))) == 2
        and "null" in value
    ):
        non_null = next(item for item in cast(list[str], value) if item != "null")
        if non_null in allowed - {"object", "null"}:
            return non_null, True
    diagnostics.append(
        _error(
            2,
            location,
            "Schema type must be one supported scalar/object type or that scalar plus null.",
            "Use object, string, number, integer, boolean, null, or [supported scalar, null].",
        )
    )
    return None


def _validate_reference_extension(
    value: object, location: str, diagnostics: list[BundleDiagnostic]
) -> None:
    if not isinstance(value, dict):
        diagnostics.append(
            _error(2, location, "x-reference must be an object.", "Supply the v1 link metadata.")
        )
        return
    required = _REFERENCE_KEYS
    if not _exact_keys(
        value,
        required=required,
        allowed=required | _REFERENCE_OPTIONAL_KEYS,
        location=location,
        diagnostics=diagnostics,
    ):
        return
    if not isinstance(value.get("link_key"), str) or _KEY.fullmatch(value["link_key"]) is None:
        diagnostics.append(
            _error(2, f"{location}/link_key", "link_key is invalid.", "Use lower_snake_case.")
        )
    for key in ("forward_label", "reverse_label"):
        if not _is_text(value.get(key), maximum=200):
            diagnostics.append(
                _error(
                    2, f"{location}/{key}", f"{key} is invalid.", "Use 1..200 trimmed characters."
                )
            )
    for key in ("source_cardinality", "target_cardinality"):
        if value.get(key) not in {"one", "many"}:
            diagnostics.append(
                _error(2, f"{location}/{key}", f"{key} is invalid.", "Use 'one' or 'many'.")
            )
    endpoint_keys = ("source_table_key", "target_table_key")
    if any(key in value for key in endpoint_keys):
        if not all(key in value for key in endpoint_keys):
            diagnostics.append(
                _error(
                    2,
                    location,
                    "Explicit reference endpoints must be supplied together.",
                    "Supply both source_table_key and target_table_key.",
                )
            )
        for key in endpoint_keys:
            if key in value and (
                not isinstance(value[key], str) or _KEY.fullmatch(value[key]) is None
            ):
                diagnostics.append(
                    _error(
                        2,
                        f"{location}/{key}",
                        f"{key} is invalid.",
                        "Use lower_snake_case.",
                    )
                )
    if "reference_only" in value and not isinstance(value["reference_only"], bool):
        diagnostics.append(
            _error(
                2,
                f"{location}/reference_only",
                "reference_only must be boolean.",
                "Use true or false.",
            )
        )


def _validate_schema_node(
    node: object,
    *,
    path: tuple[str | int, ...],
    diagnostics: list[BundleDiagnostic],
    root: bool,
    depth: int = 0,
) -> None:
    location = _location(*path)
    if depth > 64:
        diagnostics.append(
            _error(
                12,
                location,
                "Schema nesting exceeds the safe v1 depth.",
                "Flatten the schema below 64 levels.",
            )
        )
        return
    if not isinstance(node, dict):
        diagnostics.append(
            _error(
                2,
                location,
                "Every schema node must be an object.",
                "Replace this value with a JSON Schema object.",
            )
        )
        return
    for key in sorted(set(node) - _SCHEMA_KEYS):
        diagnostics.append(
            _error(
                10,
                f"{location}/{_escape_pointer(key)}",
                f"JSON Schema keyword '{key}' is not supported by Bundle v1.",
                "Remove the keyword or express the constraint with the documented v1 subset.",
            )
        )
    if "$ref" in node:
        for key in sorted(set(node) - _REF_SIBLING_KEYS):
            diagnostics.append(
                _error(
                    12,
                    f"{location}/{_escape_pointer(key)}",
                    f"JSON Schema keyword '{key}' cannot be combined losslessly with $ref.",
                    "Move the constraint into the referenced schema or remove the sibling keyword.",
                )
            )
    if not root and ("$schema" in node or "$id" in node):
        for key in ("$schema", "$id"):
            if key in node:
                diagnostics.append(
                    _error(
                        10,
                        f"{location}/{_escape_pointer(key)}",
                        f"Nested {key} changes resolver scope and is not supported.",
                        f"Keep {key} only on the record schema root.",
                    )
                )
    if "$schema" in node and node["$schema"] != JSON_SCHEMA_2020_12:
        diagnostics.append(
            _error(
                3,
                f"{location}/$schema",
                "Only JSON Schema draft 2020-12 is supported.",
                f"Use '{JSON_SCHEMA_2020_12}'.",
            )
        )
    schema_type = (
        _validate_schema_type(node["type"], f"{location}/type", diagnostics)
        if "type" in node
        else None
    )
    for key, maximum in (("title", 200), ("description", 4000)):
        if key in node and not _is_text(node[key], maximum=maximum):
            diagnostics.append(
                _error(
                    2,
                    f"{location}/{key}",
                    f"{key} is outside the supported text contract.",
                    f"Use 1..{maximum} trimmed characters.",
                )
            )
    if "$ref" in node and not _is_text(node["$ref"], maximum=1000):
        diagnostics.append(
            _error(
                2,
                f"{location}/$ref",
                "$ref must be a non-empty reference of at most 1000 characters.",
                "Use a local JSON Pointer or exact record $id reference.",
            )
        )
    if schema_type is not None:
        structural = {"properties", "required", "additionalProperties"}
        scalar_only = {
            "enum",
            "minimum",
            "maximum",
            "minLength",
            "maxLength",
            "pattern",
            "format",
            "x-business-key",
            "x-id-rule",
            "x-reference",
            "x-curve",
            "x-unit",
            "x-quantity",
            "x-suggested-values",
            "x-indexed",
            "x-searchable",
        }
        incompatible = (
            set(node) & scalar_only if schema_type[0] == "object" else set(node) & structural
        )
        for key in sorted(incompatible):
            diagnostics.append(
                _error(
                    12,
                    f"{location}/{_escape_pointer(key)}",
                    f"Keyword '{key}' would be ignored for schema type '{schema_type[0]}'.",
                    "Move the keyword to a schema node whose type can preserve its semantics.",
                )
            )
    if "properties" in node:
        properties = node["properties"]
        if not isinstance(properties, dict):
            diagnostics.append(
                _error(
                    2,
                    f"{location}/properties",
                    "properties must be an object.",
                    "Map property names to schema objects.",
                )
            )
        else:
            for key, value in sorted(properties.items()):
                if not _is_text(key, maximum=200):
                    diagnostics.append(
                        _error(
                            2,
                            f"{location}/properties",
                            "A property name is invalid.",
                            "Use a trimmed property name of 1..200 characters.",
                        )
                    )
                    continue
                _validate_schema_node(
                    value,
                    path=(*path, "properties", key),
                    diagnostics=diagnostics,
                    root=False,
                    depth=depth + 1,
                )
    if "$defs" in node:
        definitions = node["$defs"]
        if not isinstance(definitions, dict):
            diagnostics.append(
                _error(
                    2,
                    f"{location}/$defs",
                    "$defs must be an object.",
                    "Map definition names to schema objects.",
                )
            )
        else:
            for key, value in sorted(definitions.items()):
                _validate_schema_node(
                    value,
                    path=(*path, "$defs", key),
                    diagnostics=diagnostics,
                    root=False,
                    depth=depth + 1,
                )
    if "required" in node:
        required = node["required"]
        properties = node.get("properties", {})
        if (
            not isinstance(required, list)
            or not all(_is_text(item, maximum=200) for item in required)
            or len(set(cast(list[str], required))) != len(required)
        ):
            diagnostics.append(
                _error(
                    2,
                    f"{location}/required",
                    "required must contain unique property names.",
                    "Use a unique string array.",
                )
            )
        elif isinstance(properties, dict):
            for item in required:
                if item not in properties:
                    diagnostics.append(
                        _error(
                            2,
                            f"{location}/required",
                            f"Required property '{item}' is not declared.",
                            "Declare the property or remove it from required.",
                        )
                    )
    node_type = node.get("type")
    if node_type == "object" and node.get("additionalProperties") is not False:
        diagnostics.append(
            _error(
                12,
                f"{location}/additionalProperties",
                "Projected object schemas must close additional properties.",
                "Set additionalProperties to false to avoid opaque Catalog authority.",
            )
        )
    if "enum" in node:
        enum = node["enum"]
        if (
            not isinstance(enum, list)
            or not enum
            or not all(_is_text(item, maximum=255) for item in enum)
            or len(set(cast(list[str], enum))) != len(enum)
        ):
            diagnostics.append(
                _error(
                    2,
                    f"{location}/enum",
                    "enum must contain unique non-empty strings.",
                    "Provide a unique string enum.",
                )
            )
    if "minimum" in node and not _is_finite_number(node["minimum"]):
        diagnostics.append(
            _error(
                2,
                f"{location}/minimum",
                "minimum must be numeric.",
                "Provide a finite JSON number.",
            )
        )
    if "maximum" in node and not _is_finite_number(node["maximum"]):
        diagnostics.append(
            _error(
                2,
                f"{location}/maximum",
                "maximum must be numeric.",
                "Provide a finite JSON number.",
            )
        )
    if (
        isinstance(node.get("minimum"), int | float)
        and isinstance(node.get("maximum"), int | float)
        and node["minimum"] > node["maximum"]
    ):
        diagnostics.append(
            _error(2, location, "minimum exceeds maximum.", "Correct the numeric bounds.")
        )
    for key, minimum_value in (("minLength", 0), ("maxLength", 1)):
        if key in node and (
            not isinstance(node[key], int)
            or isinstance(node[key], bool)
            or node[key] < minimum_value
        ):
            diagnostics.append(
                _error(
                    2,
                    f"{location}/{key}",
                    f"{key} is outside the supported integer range.",
                    f"Use an integer greater than or equal to {minimum_value}.",
                )
            )
    if (
        isinstance(node.get("minLength"), int)
        and not isinstance(node.get("minLength"), bool)
        and isinstance(node.get("maxLength"), int)
        and not isinstance(node.get("maxLength"), bool)
        and node["minLength"] > node["maxLength"]
    ):
        diagnostics.append(
            _error(2, location, "minLength exceeds maxLength.", "Correct the string bounds.")
        )
    if "pattern" in node:
        pattern = node["pattern"]
        try:
            if not _is_text(pattern, maximum=500):
                raise re.error("invalid length")
            re.compile(cast(str, pattern))
        except re.error:
            diagnostics.append(
                _error(
                    2,
                    f"{location}/pattern",
                    "pattern is not a supported regular expression.",
                    "Provide a valid expression of at most 500 characters.",
                )
            )
    if "format" in node and node["format"] not in {"date", "uuid"}:
        diagnostics.append(
            _error(
                10,
                f"{location}/format",
                "Only date and uuid formats are projectable.",
                "Use date, uuid, or omit format.",
            )
        )
    if "x-business-key" in node and node["x-business-key"] is not True:
        diagnostics.append(
            _error(
                2,
                f"{location}/x-business-key",
                "x-business-key must be true when present.",
                "Remove it or set it to true.",
            )
        )
    if "x-reference" in node:
        _validate_reference_extension(node["x-reference"], f"{location}/x-reference", diagnostics)
        if "$ref" not in node:
            diagnostics.append(
                _error(
                    12,
                    f"{location}/x-reference",
                    "x-reference requires a bundle-local $ref target.",
                    "Add a $ref to a declared record schema business-key property.",
                )
            )
    if "x-curve" in node:
        curve = node["x-curve"]
        curve_keys = {
            "x_pointer",
            "x_unit",
            "x_quantity",
            "x_scale",
            "y_pointer",
            "y_unit",
            "y_quantity",
            "series_pointer",
            "series_unit",
            "deviation_pointer",
            "deviation_unit",
        }
        if curve is not True and (
            not isinstance(curve, dict)
            or not {"x_pointer", "y_pointer"}.issubset(curve)
            or not set(curve).issubset(curve_keys)
            or not all(isinstance(item, str) and item for item in curve.values())
            or curve.get("x_scale", "linear") not in {"linear", "log10"}
        ):
            diagnostics.append(
                _error(
                    2,
                    f"{location}/x-curve",
                    "x-curve must be true or reviewed channel-pointer metadata.",
                    "Use x/y pointers and optional unit, quantity, series, "
                    "deviation, and scale members.",
                )
            )
        if isinstance(curve, dict):
            for key, supplied_unit in curve.items():
                if not key.endswith("_unit"):
                    continue
                curve_stable_unit: str | None = None
                if supplied_unit in _EXPLICIT_LEGACY_SCHEMA_UNITS:
                    curve_stable_unit = cast(str, supplied_unit)
                elif isinstance(supplied_unit, str) and _UNIT.fullmatch(supplied_unit):
                    try:
                        curve_stable_unit = canonical_unit_id(
                            supplied_unit, location=f"{location}/x-curve/{key}"
                        )
                    except UnitError:
                        curve_stable_unit = None
                if curve_stable_unit != supplied_unit:
                    diagnostics.append(
                        _error(
                            2,
                            f"{location}/x-curve/{key}",
                            f"Curve channel unit '{supplied_unit}' is not a stable common unit.",
                            "Use a canonical unit_id from the bounded common unit registry.",
                        )
                    )
    if "x-unit" in node:
        supplied_unit = node["x-unit"]
        stable_unit: str | None = None
        if supplied_unit in _EXPLICIT_LEGACY_SCHEMA_UNITS:
            stable_unit = cast(str, supplied_unit)
        elif isinstance(supplied_unit, str) and _UNIT.fullmatch(supplied_unit) is not None:
            try:
                stable_unit = canonical_unit_id(
                    supplied_unit, location=f"{location}/x-unit"
                )
            except UnitError:
                stable_unit = None
        if stable_unit != supplied_unit:
            diagnostics.append(
                _error(
                    2,
                    f"{location}/x-unit",
                    "x-unit is not a stable canonical common-unit identifier.",
                    "Use a canonical unit_id from the bounded common unit registry; "
                    "do not use an alias.",
                )
            )
    for key in ("x-indexed", "x-searchable"):
        if key in node and not isinstance(node[key], bool):
            diagnostics.append(
                _error(2, f"{location}/{key}", f"{key} must be boolean.", "Use true or false.")
            )
    for key, maximum in (("x-quantity", 255), ("x-id-rule", 1000)):
        if key in node and not _is_text(node[key], maximum=maximum):
            diagnostics.append(
                _error(
                    2,
                    f"{location}/{key}",
                    f"{key} is invalid.",
                    f"Use 1..{maximum} trimmed characters.",
                )
            )
    if "x-suggested-values" in node:
        suggestions = node["x-suggested-values"]
        if (
            not isinstance(suggestions, list)
            or not suggestions
            or not all(_is_text(item, maximum=255) for item in suggestions)
            or len(set(cast(list[str], suggestions))) != len(suggestions)
        ):
            diagnostics.append(
                _error(
                    2,
                    f"{location}/x-suggested-values",
                    "x-suggested-values must contain unique non-empty strings.",
                    "Provide a unique suggestion list.",
                )
            )


def _parse_definition(
    value: object, location: str, diagnostics: list[BundleDiagnostic]
) -> CatalogDefinition | None:
    if not isinstance(value, dict):
        diagnostics.append(
            _error(
                2,
                location,
                "Catalog definition must be an object.",
                "Supply key, name, and description.",
            )
        )
        return None
    if not _exact_keys(
        value,
        required=frozenset({"key", "name", "description"}),
        allowed=frozenset({"key", "name", "description"}),
        location=location,
        diagnostics=diagnostics,
    ):
        return None
    key = value.get("key")
    name = value.get("name")
    description = value.get("description")
    valid = True
    if not isinstance(key, str) or _KEY.fullmatch(key) is None:
        diagnostics.append(
            _error(
                2,
                f"{location}/key",
                "Stable key is invalid.",
                "Use lower_snake_case of 1..64 characters.",
            )
        )
        valid = False
    if not _is_text(name, maximum=200):
        diagnostics.append(
            _error(2, f"{location}/name", "Name is invalid.", "Use 1..200 trimmed characters.")
        )
        valid = False
    if description is not None and not _is_text(description, maximum=4000):
        diagnostics.append(
            _error(
                2,
                f"{location}/description",
                "Description is invalid.",
                "Use null or 1..4000 trimmed characters.",
            )
        )
        valid = False
    if not valid:
        return None
    return CatalogDefinition(cast(str, key), cast(str, name), cast(str | None, description))


def _parse_record_schema(
    value: object,
    *,
    index: int,
    bundle_version: str,
    diagnostics: list[BundleDiagnostic],
) -> RecordSchemaDefinition | None:
    location = _location("record_schemas", index)
    if not isinstance(value, dict):
        diagnostics.append(
            _error(
                2,
                location,
                "Record schema entry must be an object.",
                "Supply the v1 record entry fields.",
            )
        )
        return None
    required = frozenset({"key", "name", "description", "schema_sha256", "schema"})
    if not _exact_keys(
        value,
        required=required,
        allowed=required | {"schema_version", "data_category"},
        location=location,
        diagnostics=diagnostics,
    ):
        return None
    key = value.get("key")
    name = value.get("name")
    description = value.get("description")
    schema_sha256 = value.get("schema_sha256")
    schema = value.get("schema")
    schema_version = value.get("schema_version")
    data_category = value.get("data_category")
    valid = True
    if not isinstance(key, str) or _KEY.fullmatch(key) is None:
        diagnostics.append(
            _error(
                2,
                f"{location}/key",
                "Record stable key is invalid.",
                "Use lower_snake_case of 1..64 characters.",
            )
        )
        valid = False
    if not _is_text(name, maximum=200):
        diagnostics.append(
            _error(
                2, f"{location}/name", "Record name is invalid.", "Use 1..200 trimmed characters."
            )
        )
        valid = False
    if description is not None and not _is_text(description, maximum=4000):
        diagnostics.append(
            _error(
                2,
                f"{location}/description",
                "Record description is invalid.",
                "Use null or 1..4000 trimmed characters.",
            )
        )
        valid = False
    if data_category not in {None, "technical_data", "test_data", "simulation_data"}:
        diagnostics.append(
            _error(
                2,
                f"{location}/data_category",
                "Record data_category is invalid.",
                "Use technical_data, test_data, simulation_data, or null.",
            )
        )
        valid = False
    if schema_version is not None and (
        not isinstance(schema_version, str) or _SEMVER.fullmatch(schema_version) is None
    ):
        diagnostics.append(
            _error(
                2,
                f"{location}/schema_version",
                "Record schema_version is invalid.",
                "Use a three-part semantic version.",
            )
        )
        valid = False
    if not isinstance(schema_sha256, str) or re.fullmatch(r"[0-9a-f]{64}", schema_sha256) is None:
        diagnostics.append(
            _error(
                2,
                f"{location}/schema_sha256",
                "schema_sha256 is invalid.",
                "Supply the lowercase SHA-256 of canonical schema JSON.",
            )
        )
        valid = False
    if not isinstance(schema, dict):
        diagnostics.append(
            _error(
                2,
                f"{location}/schema",
                "schema must be an object.",
                "Supply a draft 2020-12 record schema.",
            )
        )
        valid = False
    if not valid:
        return None
    assert isinstance(key, str)
    assert isinstance(name, str)
    assert isinstance(schema_sha256, str)
    assert isinstance(schema, dict)
    schema_diagnostic_start = len(diagnostics)
    _validate_schema_node(
        schema,
        path=("record_schemas", index, "schema"),
        diagnostics=diagnostics,
        root=True,
    )
    required_root = {"$schema", "$id", "type", "properties", "additionalProperties"}
    for member in sorted(required_root - set(schema)):
        diagnostics.append(
            _error(
                2,
                f"{location}/schema",
                f"Record schema root is missing '{member}'.",
                f"Add '{member}' to the record schema root.",
            )
        )
    if schema.get("$schema") != JSON_SCHEMA_2020_12:
        diagnostics.append(
            _error(
                3,
                f"{location}/schema/$schema",
                "Record schema is not draft 2020-12.",
                f"Use '{JSON_SCHEMA_2020_12}'.",
            )
        )
    effective_schema_version = cast(str, schema_version or bundle_version)
    expected_id = f"urn:cmp:catalog-schema:{key}:{effective_schema_version}"
    if schema.get("$id") != expected_id:
        diagnostics.append(
            _error(
                2,
                f"{location}/schema/$id",
                "Record schema $id does not match its stable key and bundle version.",
                f"Use '{expected_id}'.",
            )
        )
    if schema.get("type") != "object" or schema.get("additionalProperties") is not False:
        diagnostics.append(
            _error(
                12,
                f"{location}/schema",
                "Record schema root must be a closed object.",
                "Use type object and additionalProperties false.",
            )
        )
    if not any(
        item.severity is DiagnosticSeverity.ERROR for item in diagnostics[schema_diagnostic_start:]
    ):
        try:
            Draft202012Validator.check_schema(schema)
        except SchemaError as error:
            suffix = tuple(error.absolute_path)
            diagnostics.append(
                _error(
                    2,
                    _location("record_schemas", index, "schema", *suffix),
                    f"Record schema is not valid draft 2020-12: {error.message}",
                    "Correct the JSON Schema before retrying.",
                )
            )
        except RecursionError:
            diagnostics.append(
                _error(
                    12,
                    f"{location}/schema",
                    "Record schema nesting exceeds the safe validator limit.",
                    "Flatten the schema below 64 levels.",
                )
            )
    if not any(
        item.severity is DiagnosticSeverity.ERROR for item in diagnostics[schema_diagnostic_start:]
    ):
        try:
            observed_sha256 = content_sha256(schema)
        except (RecursionError, TypeError, ValueError):
            diagnostics.append(
                _error(
                    12,
                    f"{location}/schema",
                    "Record schema cannot be canonicalized within the safe v1 limits.",
                    "Reduce schema nesting and retry.",
                )
            )
        else:
            if observed_sha256 != schema_sha256:
                diagnostics.append(
                    _error(
                        5,
                        f"{location}/schema_sha256",
                        "Record schema checksum does not match canonical schema JSON.",
                        f"Replace schema_sha256 with '{observed_sha256}' "
                        "or restore the intended schema.",
                    )
                )
    if any(
        item.severity is DiagnosticSeverity.ERROR for item in diagnostics[schema_diagnostic_start:]
    ):
        return None
    return RecordSchemaDefinition(
        key,
        name,
        cast(str | None, description),
        schema_sha256,
        cast(dict[str, Any], schema),
        cast(str | None, schema_version),
        cast(str | None, data_category),
    )


def _decode_pointer_token(value: str) -> str:
    result: list[str] = []
    index = 0
    while index < len(value):
        if value[index] != "~":
            result.append(value[index])
            index += 1
            continue
        if index + 1 >= len(value) or value[index + 1] not in {"0", "1"}:
            raise ValueError("invalid JSON Pointer escape")
        result.append("~" if value[index + 1] == "0" else "/")
        index += 2
    return "".join(result)


def _pointer_get(document: object, fragment: str) -> object:
    if fragment in {"", "#"}:
        return document
    if not fragment.startswith("#/"):
        raise ValueError("only JSON Pointer fragments are supported")
    current = document
    for encoded in fragment[2:].split("/"):
        token = _decode_pointer_token(unquote(encoded))
        if isinstance(current, dict) and token in current:
            current = current[token]
        elif isinstance(current, list) and token.isdigit() and int(token) < len(current):
            current = current[int(token)]
        else:
            raise KeyError(token)
    return current


@dataclass(frozen=True, slots=True)
class _ResolvedReference:
    record_key: str
    fragment: str
    node: dict[str, Any]


def _resolve_reference(
    reference: str,
    *,
    current: RecordSchemaDefinition,
    by_id: Mapping[str, RecordSchemaDefinition],
) -> _ResolvedReference:
    if reference.startswith("#"):
        target = current
        fragment = reference
    else:
        if "#" in reference:
            base, suffix = reference.split("#", maxsplit=1)
            fragment = f"#{suffix}"
        else:
            base = reference
            fragment = ""
        if base not in by_id:
            if base.startswith("urn:cmp:catalog-schema:"):
                raise LookupError(base)
            raise PermissionError(base)
        target = by_id[base]
    value = _pointer_get(target.schema, fragment)
    if not isinstance(value, dict):
        raise TypeError("reference target is not a schema object")
    return _ResolvedReference(target.key, fragment, cast(dict[str, Any], value))


def _walk_refs(
    node: object, path: tuple[str | int, ...] = ()
) -> tuple[tuple[tuple[str | int, ...], str], ...]:
    found: list[tuple[tuple[str | int, ...], str]] = []
    if not isinstance(node, dict):
        return ()
    reference = node.get("$ref")
    if isinstance(reference, str):
        found.append(((*path, "$ref"), reference))
    for container in ("properties", "$defs"):
        values = node.get(container)
        if isinstance(values, dict):
            for key, child in sorted(values.items()):
                found.extend(_walk_refs(child, (*path, container, key)))
    return tuple(found)


def _resolve_dependencies(
    records: tuple[RecordSchemaDefinition, ...],
    diagnostics: list[BundleDiagnostic],
) -> tuple[str, ...]:
    by_id = {item.schema_id: item for item in records}
    record_index = {item.key: index for index, item in enumerate(records)}
    dependencies: dict[str, set[str]] = {item.key: set() for item in records}
    for record in records:
        for path, reference in _walk_refs(record.schema):
            location = _location("record_schemas", record_index[record.key], "schema", *path)
            try:
                resolved = _resolve_reference(reference, current=record, by_id=by_id)
            except PermissionError:
                diagnostics.append(
                    _error(
                        7,
                        location,
                        "External URL, file, path, or network $ref is forbidden.",
                        "Reference only a declared record $id or a local JSON Pointer fragment.",
                    )
                )
                continue
            except (KeyError, ValueError, TypeError):
                diagnostics.append(
                    _error(
                        9,
                        location,
                        f"$ref pointer '{reference}' does not resolve to a schema object.",
                        "Correct the RFC 6901 pointer and target node.",
                    )
                )
                continue
            except LookupError:
                diagnostics.append(
                    _error(
                        8,
                        location,
                        f"$ref target '{reference}' is not declared in this bundle.",
                        "Reference an exact record schema $id from this bundle.",
                    )
                )
                continue
            if resolved.record_key != record.key:
                dependencies[record.key].add(resolved.record_key)

    dependents: dict[str, set[str]] = defaultdict(set)
    indegree = {key: len(value) for key, value in dependencies.items()}
    for dependent, required_keys in dependencies.items():
        for required_key in required_keys:
            dependents[required_key].add(dependent)
    order: list[str] = []
    ready = [key for key, count in indegree.items() if count == 0]
    ready.sort()
    while ready:
        key = heappop(ready)
        order.append(key)
        for candidate in sorted(dependents.get(key, ())):
            indegree[candidate] -= 1
            if indegree[candidate] == 0:
                heappush(ready, candidate)
    if len(order) != len(records):
        cycle = sorted(key for key, count in indegree.items() if count > 0)
        diagnostics.append(
            _error(
                11,
                "/record_schemas",
                f"Record schema dependency cycle detected: {', '.join(cycle)}.",
                "Break the cross-record reference cycle and retry.",
            )
        )
        return tuple(sorted(record_index, key=lambda key: (record_index[key], key)))
    return tuple(order)


def parse_schema_definition_bundle(
    raw_bytes: bytes,
    *,
    organization_id: UUID,
    project_id: UUID,
    source_classification: DataClassification,
    classification_allowed: Callable[[DataClassification], bool],
) -> tuple[SchemaDefinitionBundle | None, tuple[BundleDiagnostic, ...]]:
    diagnostics: list[BundleDiagnostic] = []
    try:
        text = raw_bytes.decode("utf-8")
        document = json.loads(text, object_pairs_hook=_pairs, parse_constant=_reject_constant)
    except UnicodeDecodeError:
        return None, (
            _error(
                1, "", "Bundle bytes are not valid UTF-8.", "Encode the JSON document as UTF-8."
            ),
        )
    except _DuplicateJsonKey as error:
        return None, (
            _error(
                6,
                "",
                f"Duplicate JSON member '{error}' was found.",
                "Remove the duplicate member; duplicate-key precedence is forbidden.",
            ),
        )
    except (json.JSONDecodeError, RecursionError, ValueError) as error:
        return None, (
            _error(
                1,
                "",
                f"Bundle is not strict JSON: {error}.",
                "Correct the JSON syntax and retry with a new immutable Artifact.",
            ),
        )
    if not isinstance(document, dict):
        return None, (
            _error(
                2,
                "",
                "Bundle root must be an object.",
                "Supply a Schema Definition Bundle v1 object.",
            ),
        )
    root_required = frozenset(
        {
            "$schema",
            "contract_version",
            "bundle_key",
            "bundle_version",
            "scope",
            "catalog",
            "record_schemas",
        }
    )
    _exact_keys(
        document,
        required=root_required,
        allowed=root_required | {"unit_profiles"},
        location="",
        diagnostics=diagnostics,
    )
    if document.get("$schema") != BUNDLE_CONTRACT_ID:
        diagnostics.append(
            _error(
                3,
                "/$schema",
                "Bundle contract identifier is unsupported.",
                f"Use '{BUNDLE_CONTRACT_ID}'.",
            )
        )
    if document.get("contract_version") != BUNDLE_CONTRACT_VERSION:
        diagnostics.append(
            _error(
                3,
                "/contract_version",
                "Bundle contract version is unsupported.",
                f"Use '{BUNDLE_CONTRACT_VERSION}'.",
            )
        )
    bundle_key = document.get("bundle_key")
    bundle_version = document.get("bundle_version")
    if not isinstance(bundle_key, str) or _KEY.fullmatch(bundle_key) is None:
        diagnostics.append(
            _error(
                2,
                "/bundle_key",
                "Bundle stable key is invalid.",
                "Use lower_snake_case of 1..64 characters.",
            )
        )
    if (
        not isinstance(bundle_version, str)
        or len(bundle_version) > 64
        or _SEMVER.fullmatch(bundle_version) is None
    ):
        diagnostics.append(
            _error(
                2,
                "/bundle_version",
                "Bundle version is invalid.",
                "Use a release semantic version such as 1.0.0.",
            )
        )

    scope_value = document.get("scope")
    scope: BundleScope | None = None
    if not isinstance(scope_value, dict):
        diagnostics.append(
            _error(
                2,
                "/scope",
                "scope must be an object.",
                "Supply organization_id, project_id, and classification.",
            )
        )
    else:
        scope_keys = frozenset({"organization_id", "project_id", "classification"})
        if _exact_keys(
            scope_value,
            required=scope_keys,
            allowed=scope_keys,
            location="/scope",
            diagnostics=diagnostics,
        ):
            try:
                scope_org_value = scope_value["organization_id"]
                scope_project_value = scope_value["project_id"]
                scope_classification_value = scope_value["classification"]
                if not all(
                    isinstance(item, str)
                    for item in (
                        scope_org_value,
                        scope_project_value,
                        scope_classification_value,
                    )
                ):
                    raise ValueError("scope fields must be strings")
                scope_org = UUID(scope_org_value)
                scope_project = UUID(scope_project_value)
                scope_classification = DataClassification(scope_classification_value)
                if scope_org.int == 0 or scope_project.int == 0:
                    raise ValueError("zero UUID")
                scope = BundleScope(scope_org, scope_project, scope_classification)
                if scope_org != organization_id or scope_project != project_id:
                    diagnostics.append(
                        _error(
                            4,
                            "/scope",
                            "Bundle tenant scope does not match the authenticated request context.",
                            "Create a bundle for the selected organization and project.",
                        )
                    )
                if not classification_allowed(scope_classification):
                    diagnostics.append(
                        _error(
                            4,
                            "/scope/classification",
                            "Bundle classification exceeds the authorized clearance.",
                            "Use an authorized classification or request the required access.",
                        )
                    )
                if scope_classification is not source_classification:
                    diagnostics.append(
                        _error(
                            4,
                            "/scope/classification",
                            "Bundle classification differs from its immutable source Artifact.",
                            "Create a new Artifact whose classification matches the bundle scope.",
                        )
                    )
            except (ValueError, TypeError):
                diagnostics.append(
                    _error(
                        2,
                        "/scope",
                        "Bundle scope contains an invalid UUID or classification.",
                        "Use non-zero UUIDs and a supported classification.",
                    )
                )

    catalog_value = document.get("catalog")
    database: CatalogDefinition | None = None
    profile: CatalogDefinition | None = None
    if not isinstance(catalog_value, dict):
        diagnostics.append(
            _error(
                2,
                "/catalog",
                "catalog must be an object.",
                "Supply database and profile definitions.",
            )
        )
    else:
        catalog_keys = frozenset({"database", "profile"})
        _exact_keys(
            catalog_value,
            required=catalog_keys,
            allowed=catalog_keys,
            location="/catalog",
            diagnostics=diagnostics,
        )
        database = _parse_definition(
            catalog_value.get("database"), "/catalog/database", diagnostics
        )
        profile = _parse_definition(catalog_value.get("profile"), "/catalog/profile", diagnostics)

    records_value = document.get("record_schemas")
    records: list[RecordSchemaDefinition] = []
    if not isinstance(records_value, list) or not records_value:
        diagnostics.append(
            _error(
                2,
                "/record_schemas",
                "record_schemas must be a non-empty array.",
                "Supply one or more record schemas; cardinality is otherwise dynamic.",
            )
        )
    elif isinstance(bundle_version, str):
        for index, value in enumerate(records_value):
            record = _parse_record_schema(
                value, index=index, bundle_version=bundle_version, diagnostics=diagnostics
            )
            if record is not None:
                records.append(record)
    keys = [item.key for item in records]
    ids = [item.schema_id for item in records]
    for label, values in (("record key", keys), ("record $id", ids)):
        duplicates = sorted(item for item, count in Counter(values).items() if count > 1)
        for duplicate in duplicates:
            diagnostics.append(
                _error(
                    6,
                    "/record_schemas",
                    f"Duplicate {label} '{duplicate}' was found.",
                    f"Keep exactly one entry for each {label}.",
                )
            )
    unit_profiles_value = document.get("unit_profiles", [])
    unit_profiles: list[dict[str, Any]] = []
    if not isinstance(unit_profiles_value, list):
        diagnostics.append(
            _error(
                2,
                "/unit_profiles",
                "unit_profiles must be an array.",
                "Supply zero or more key/name/units definitions.",
            )
        )
    else:
        seen_profile_keys: set[str] = set()
        for index, value in enumerate(unit_profiles_value):
            location = f"/unit_profiles/{index}"
            if not isinstance(value, dict) or set(value) != {"key", "name", "units"}:
                diagnostics.append(
                    _error(
                        2,
                        location,
                        "Unit Profile requires only key, name, and units.",
                        "Correct the exact profile definition.",
                    )
                )
                continue
            profile_key = value.get("key")
            profile_name = value.get("name")
            units = value.get("units")
            if (
                not isinstance(profile_key, str)
                or _KEY.fullmatch(profile_key) is None
                or profile_key in seen_profile_keys
            ):
                diagnostics.append(
                    _error(
                        2,
                        f"{location}/key",
                        "Unit Profile key is invalid or duplicated.",
                        "Use a unique lower_snake_case key.",
                    )
                )
                continue
            if not _is_text(profile_name, maximum=200):
                diagnostics.append(
                    _error(
                        2,
                        f"{location}/name",
                        "Unit Profile name is invalid.",
                        "Use 1..200 trimmed characters.",
                    )
                )
                continue
            if (
                not isinstance(units, dict)
                or not units
                or not all(
                    isinstance(key, str)
                    and _KEY.fullmatch(key) is not None
                    and isinstance(unit, str)
                    and _UNIT.fullmatch(unit) is not None
                    for key, unit in units.items()
                )
            ):
                diagnostics.append(
                    _error(
                        2,
                        f"{location}/units",
                        "Unit Profile units must map stable quantity keys to unit strings.",
                        "Correct the bounded unit map.",
                    )
                )
                continue
            for quantity_key, supplied_unit in sorted(units.items()):
                stable_unit: str | None = None
                try:
                    stable_unit = canonical_unit_id(
                        cast(str, supplied_unit),
                        location=f"{location}/units/{_escape_pointer(cast(str, quantity_key))}",
                    )
                except UnitError:
                    stable_unit = None
                if stable_unit != supplied_unit:
                    diagnostics.append(
                        _error(
                            2,
                            f"{location}/units/{_escape_pointer(cast(str, quantity_key))}",
                            f"Unit Profile unit '{supplied_unit}' is not a stable common unit.",
                            "Use a canonical unit_id from the bounded common unit registry.",
                        )
                    )
            seen_profile_keys.add(profile_key)
            unit_profiles.append(_canonical_mapping(value))
    dependency_order = (
        _resolve_dependencies(tuple(records), diagnostics)
        if records and not any(item.severity is DiagnosticSeverity.ERROR for item in diagnostics)
        else ()
    )
    diagnostics.sort(key=lambda item: (item.location, item.code, item.message))
    if (
        not isinstance(bundle_key, str)
        or _KEY.fullmatch(bundle_key) is None
        or not isinstance(bundle_version, str)
        or len(bundle_version) > 64
        or _SEMVER.fullmatch(bundle_version) is None
        or scope is None
        or database is None
        or profile is None
        or not records
        or any(item.severity is DiagnosticSeverity.ERROR for item in diagnostics)
    ):
        return None, tuple(diagnostics)
    return (
        SchemaDefinitionBundle(
            bundle_key,
            bundle_version,
            scope,
            database,
            profile,
            tuple(records),
            dependency_order,
            tuple(unit_profiles),
        ),
        tuple(diagnostics),
    )


@dataclass(frozen=True, slots=True)
class _LeafProjection:
    record_key: str
    source_pointer: str
    attribute_key: str
    section: str
    required: bool
    node: dict[str, Any]
    resolved_reference: _ResolvedReference | None


def _human_name(key: str) -> str:
    return " ".join(part.capitalize() for part in key.split("_"))


def _canonical_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(canonical_json_bytes(dict(value))))


def _effective_node(
    node: dict[str, Any],
    *,
    record: RecordSchemaDefinition,
    by_id: Mapping[str, RecordSchemaDefinition],
    diagnostics: list[BundleDiagnostic],
    location: str,
    seen: frozenset[tuple[str, str]] = frozenset(),
) -> tuple[dict[str, Any], _ResolvedReference | None]:
    reference = node.get("$ref")
    if not isinstance(reference, str):
        return node, None
    try:
        resolved = _resolve_reference(reference, current=record, by_id=by_id)
    except (PermissionError, LookupError, KeyError, ValueError, TypeError):
        return node, None
    token = (resolved.record_key, resolved.fragment)
    if token in seen:
        diagnostics.append(
            _error(
                11,
                location,
                "Recursive local $ref cannot be projected to finite Catalog attributes.",
                "Replace the recursive definition with bounded scalar fields.",
            )
        )
        return node, resolved
    if len(seen) >= 64:
        diagnostics.append(
            _error(
                12,
                location,
                "Resolved $ref chain exceeds the safe v1 projection depth.",
                "Flatten the reference chain below 64 levels.",
            )
        )
        return node, resolved
    target_record = next(item for item in by_id.values() if item.key == resolved.record_key)
    effective, _ = _effective_node(
        resolved.node,
        record=target_record,
        by_id=by_id,
        diagnostics=diagnostics,
        location=location,
        seen=seen | {token},
    )
    merged = dict(effective)
    for key in (
        "x-business-key",
        "x-id-rule",
        "x-reference",
        "x-curve",
        "x-unit",
        "x-quantity",
        "x-suggested-values",
        "x-indexed",
        "x-searchable",
        "x-source-origin",
    ):
        merged.pop(key, None)
    for key in (
        "title",
        "description",
        "x-business-key",
        "x-id-rule",
        "x-reference",
        "x-curve",
        "x-unit",
        "x-quantity",
        "x-suggested-values",
        "x-indexed",
        "x-searchable",
        "x-source-origin",
    ):
        if key in node:
            merged[key] = node[key]
    return merged, resolved


def _collect_leaves(
    record: RecordSchemaDefinition,
    *,
    by_id: Mapping[str, RecordSchemaDefinition],
    diagnostics: list[BundleDiagnostic],
) -> tuple[_LeafProjection, ...]:
    leaves: list[_LeafProjection] = []

    def visit(
        node: dict[str, Any],
        *,
        property_path: tuple[str, ...],
        schema_path: tuple[str | int, ...],
        required_chain: bool,
        sections: tuple[str, ...],
        reference_path: frozenset[tuple[str, str]],
        depth: int,
    ) -> None:
        location = _location(*schema_path)
        if depth > 64:
            diagnostics.append(
                _error(
                    12,
                    location,
                    "Resolved schema nesting exceeds the safe v1 projection depth.",
                    "Flatten the referenced schema below 64 levels.",
                )
            )
            return
        effective, resolved = _effective_node(
            node,
            record=record,
            by_id=by_id,
            diagnostics=diagnostics,
            location=location,
        )
        next_reference_path = reference_path
        if resolved is not None:
            token = (resolved.record_key, resolved.fragment)
            if token in reference_path:
                diagnostics.append(
                    _error(
                        11,
                        location,
                        "Recursive local $ref cannot be projected to finite Catalog attributes.",
                        "Replace the recursive definition with bounded scalar fields.",
                    )
                )
                return
            next_reference_path = reference_path | {token}
        schema_type = (
            _validate_schema_type(effective.get("type"), f"{location}/type", diagnostics)
            if "type" in effective
            else None
        )
        if schema_type is not None and schema_type[0] == "object":
            properties = effective.get("properties")
            if not isinstance(properties, dict):
                diagnostics.append(
                    _error(
                        12,
                        location,
                        "Object schema has no projectable properties.",
                        "Declare closed object properties.",
                    )
                )
                return
            required_names = (
                set(effective.get("required", ()))
                if isinstance(effective.get("required"), list)
                else set()
            )
            next_sections = sections
            if property_path:
                section_name = effective.get("title") or _human_name(property_path[-1])
                if not _is_text(section_name, maximum=100):
                    diagnostics.append(
                        _error(
                            12,
                            location,
                            "Layout section name exceeds the Catalog limit.",
                            "Use a title of at most 100 trimmed characters.",
                        )
                    )
                    return
                next_sections = (*sections, cast(str, section_name))
            for key, child in sorted(properties.items()):
                if _KEY.fullmatch(key) is None:
                    diagnostics.append(
                        _error(
                            12,
                            _location(*schema_path, "properties", key),
                            f"Property key '{key}' cannot become a stable Catalog Attribute key.",
                            "Use lower_snake_case property keys and keep display text in title.",
                        )
                    )
                    continue
                if isinstance(child, dict):
                    visit(
                        cast(dict[str, Any], child),
                        property_path=(*property_path, key),
                        schema_path=(*schema_path, "properties", key),
                        required_chain=required_chain and key in required_names,
                        sections=next_sections,
                        reference_path=next_reference_path,
                        depth=depth + 1,
                    )
            return
        if not property_path:
            diagnostics.append(
                _error(
                    12,
                    location,
                    "Record schema root cannot project to a scalar.",
                    "Use a closed object record schema.",
                )
            )
            return
        attribute_key = "__".join(property_path)
        if _KEY.fullmatch(attribute_key) is None:
            diagnostics.append(
                _error(
                    12,
                    location,
                    f"Flattened Attribute key '{attribute_key}' exceeds the Catalog key contract.",
                    "Shorten the nested property keys so the joined key is at most 64 characters.",
                )
            )
            return
        section = " / ".join(sections) if sections else "General"
        if len(section) > 100:
            diagnostics.append(
                _error(
                    12,
                    location,
                    "Flattened Layout section exceeds 100 characters.",
                    "Shorten group titles.",
                )
            )
            return
        pointer = _location(*schema_path)
        leaves.append(
            _LeafProjection(
                record.key,
                pointer,
                attribute_key,
                section,
                required_chain,
                effective,
                resolved,
            )
        )

    visit(
        record.schema,
        property_path=(),
        schema_path=("record_schemas", record.key, "schema"),
        required_chain=True,
        sections=(),
        reference_path=frozenset(),
        depth=0,
    )
    return tuple(sorted(leaves, key=lambda item: (item.source_pointer, item.attribute_key)))


def _attribute_content(
    leaf: _LeafProjection,
    *,
    by_key: Mapping[str, RecordSchemaDefinition],
    diagnostics: list[BundleDiagnostic],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    node = leaf.node
    source_origin = node.get("x-source-origin")
    if not isinstance(source_origin, dict):
        source_origin = {}
    location = leaf.source_pointer
    parsed_type = (
        _validate_schema_type(node.get("type"), f"{location}/type", diagnostics)
        if "type" in node
        else None
    )
    base_type = parsed_type[0] if parsed_type is not None else None
    source_type = base_type
    nullable = parsed_type[1] if parsed_type is not None else False
    reference = node.get("x-reference")
    link: dict[str, Any] | None = None
    reference_table_key: str | None = None
    if isinstance(node.get("description"), str) and len(node["description"]) > 2000:
        diagnostics.append(
            _error(
                12,
                f"{location}/description",
                "Projected Attribute/Link Type help text exceeds the Catalog limit.",
                "Shorten the leaf description to at most 2000 characters.",
            )
        )
        return None, None
    if reference is not None:
        if leaf.resolved_reference is None:
            diagnostics.append(
                _error(
                    12,
                    location,
                    "Reference target could not be resolved for projection.",
                    "Correct the bundle-local $ref.",
                )
            )
            return None, None
        target = leaf.resolved_reference
        if target.record_key == leaf.record_key:
            diagnostics.append(
                _error(
                    11,
                    location,
                    "A record reference cannot target the same record schema in Bundle v1.",
                    "Use a cross-record reference without a cycle.",
                )
            )
            return None, None
        target_node = target.node
        if target_node.get("x-business-key") is not True:
            diagnostics.append(
                _error(
                    12,
                    location,
                    "x-reference must target an x-business-key property.",
                    "Point the $ref at the target record business-key schema.",
                )
            )
            return None, None
        reference_table_key = target.record_key
        base_type = "record_reference"
        assert isinstance(reference, dict)
        link = {
            "key": reference["link_key"],
            "name": node.get("title") or _human_name(cast(str, reference["link_key"])),
            "source_table_key": reference.get("source_table_key", leaf.record_key),
            "target_table_key": reference.get("target_table_key", target.record_key),
            "forward_label": reference["forward_label"],
            "reverse_label": reference["reverse_label"],
            "source_cardinality": reference["source_cardinality"],
            "target_cardinality": reference["target_cardinality"],
            "description": node.get("description"),
        }
    elif node.get("x-curve") is not None:
        if source_type != "string" or node.get("format") != "uuid":
            diagnostics.append(
                _error(
                    12,
                    location,
                    "x-curve must be a UUID string Artifact pointer.",
                    "Use type string, format uuid, and x-curve true.",
                )
            )
            return None, None
        if any(
            key in node
            for key in ("enum", "minimum", "maximum", "minLength", "maxLength", "pattern")
        ):
            diagnostics.append(
                _error(
                    12,
                    location,
                    "Additional scalar constraints on an x-curve pointer would be lost.",
                    "Use only type string, format uuid, x-curve, and optional x-unit/index hints.",
                )
            )
            return None, None
        base_type = "curve"
    elif "enum" in node:
        if base_type != "string":
            diagnostics.append(
                _error(
                    12,
                    location,
                    "Only string enum can project to a discrete Attribute.",
                    "Use type string with a unique string enum.",
                )
            )
            return None, None
        base_type = "discrete"
    elif base_type == "string":
        base_type = "date" if node.get("format") == "date" else "text"
    if base_type not in {
        "number",
        "integer",
        "text",
        "boolean",
        "date",
        "discrete",
        "curve",
        "record_reference",
    }:
        diagnostics.append(
            _error(
                12,
                location,
                "Schema leaf type cannot project to a typed Catalog Attribute.",
                "Use a supported scalar, enum, curve, or record reference.",
            )
        )
        return None, None
    if nullable and leaf.required:
        diagnostics.append(
            _error(
                12,
                location,
                "A required nullable value cannot be represented by the current "
                "Catalog value store.",
                "Remove null from the required field or make the property optional.",
            )
        )
        return None, None
    if ("minimum" in node or "maximum" in node) and source_type not in {
        "number",
        "integer",
    }:
        diagnostics.append(
            _error(
                12,
                location,
                "Numeric bounds would be ignored for this schema type.",
                "Keep minimum/maximum only on numeric fields.",
            )
        )
        return None, None
    if (
        any(key in node for key in ("minLength", "maxLength", "pattern"))
        and source_type != "string"
    ):
        diagnostics.append(
            _error(
                12,
                location,
                "String constraints would be ignored for this schema type.",
                "Keep minLength, maxLength, and pattern only on string fields.",
            )
        )
        return None, None
    if "format" in node and source_type != "string":
        diagnostics.append(
            _error(
                12,
                f"{location}/format",
                "The declared format cannot project from a non-string field.",
                "Use a string schema for date or uuid format.",
            )
        )
        return None, None
    if "format" in node and "enum" in node:
        diagnostics.append(
            _error(
                12,
                f"{location}/format",
                "Format plus enum cannot project to one Catalog Attribute type.",
                "Use a formatted string or a discrete enum, but not both.",
            )
        )
        return None, None
    if node.get("format") == "date" and any(
        key in node for key in ("minLength", "maxLength", "pattern")
    ):
        diagnostics.append(
            _error(
                12,
                f"{location}/format",
                "Date plus string/enum constraints cannot project without loss.",
                "Use a plain date field or a constrained text/discrete field.",
            )
        )
        return None, None
    if node.get("format") == "uuid" and base_type == "text" and "pattern" in node:
        diagnostics.append(
            _error(
                12,
                f"{location}/format",
                "UUID format plus a custom pattern cannot project to one Catalog pattern.",
                "Use format uuid without pattern, or use a plain patterned string.",
            )
        )
        return None, None
    if base_type == "integer" and ("minimum" in node or "maximum" in node):
        diagnostics.append(
            _error(
                12,
                location,
                "Integer numeric bounds are not represented by the current Attribute contract.",
                "Remove the bounds for #204 or use a number Attribute; "
                "#204 will not silently drop them.",
            )
        )
        return None, None
    if node.get("x-indexed") is True and base_type not in {"number", "text", "discrete"}:
        diagnostics.append(
            _error(
                12,
                f"{location}/x-indexed",
                f"Indexed {base_type} is not represented by the current Catalog indexes.",
                "Set x-indexed to false or omit it.",
            )
        )
        return None, None
    if node.get("x-searchable") is True and base_type not in {"number", "text", "discrete"}:
        diagnostics.append(
            _error(
                12,
                f"{location}/x-searchable",
                f"Searchable {base_type} is not represented by the current Catalog query contract.",
                "Set x-searchable to false or omit it.",
            )
        )
        return None, None
    if "x-unit" in node and base_type not in {"number", "curve"}:
        diagnostics.append(
            _error(
                12,
                f"{location}/x-unit",
                f"Unit metadata is not represented for {base_type} Attributes.",
                "Keep x-unit on number or curve fields; Unit Profiles remain #205.",
            )
        )
        return None, None
    if node.get("x-business-key") is True and base_type not in {"text", "discrete"}:
        diagnostics.append(
            _error(
                12,
                f"{location}/x-business-key",
                "Business keys must project to text or discrete values.",
                "Use a string schema for the business key.",
            )
        )
        return None, None
    content = {
        "key": leaf.attribute_key,
        "name": node.get("title") or _human_name(leaf.attribute_key),
        "data_type": base_type,
        "required": leaf.required,
        "quantity_semantics": node.get("x-quantity"),
        "normalized_unit": node.get("x-unit"),
        "minimum_number": node.get("minimum") if base_type == "number" else None,
        "maximum_number": node.get("maximum") if base_type == "number" else None,
        "minimum_length": node.get("minLength") if base_type in {"text", "discrete"} else None,
        "maximum_length": node.get("maxLength") if base_type in {"text", "discrete"} else None,
        "pattern": (
            _UUID_VALUE_PATTERN
            if node.get("format") == "uuid" and base_type == "text"
            else node.get("pattern")
            if base_type in {"text", "discrete"}
            else None
        ),
        "allowed_values": node.get("enum", []) if base_type == "discrete" else [],
        "reference_table_key": reference_table_key,
        "help_text": node.get("description"),
        "source_pointer": source_origin.get("pointer") or leaf.source_pointer,
        "adapter_semantics": {
            "business_key": node.get("x-business-key") is True,
            "identity_rule": node.get("x-id-rule"),
            "nullable": nullable,
            "suggested_values": node.get("x-suggested-values"),
            "curve": node.get("x-curve") if isinstance(node.get("x-curve"), dict) else None,
            "indexed": node.get("x-indexed"),
            "searchable": node.get("x-searchable"),
        },
    }
    if source_origin:
        content.update(
            {
                "source_schema_id": source_origin.get("schema_id"),
                "source_schema_version": source_origin.get("schema_version"),
                "source_file": source_origin.get("file"),
                "source_file_sha256": source_origin.get("file_sha256"),
            }
        )
    if node.get("x-business-key") is True:
        content["business_key"] = True
    del by_key  # reserved for future versioned quantity/reference policies
    if isinstance(reference, dict) and reference.get("reference_only") is True:
        return None, _canonical_mapping(link) if link is not None else None
    return _canonical_mapping(content), _canonical_mapping(link) if link is not None else None


def project_schema_definition_bundle(
    bundle: SchemaDefinitionBundle,
) -> tuple[tuple[ProjectedCatalogObject, ...], tuple[BundleDiagnostic, ...]]:
    diagnostics: list[BundleDiagnostic] = []
    by_key = {item.key: item for item in bundle.record_schemas}
    by_id = {item.schema_id: item for item in bundle.record_schemas}
    leaves: dict[str, tuple[_LeafProjection, ...]] = {}
    for key in bundle.dependency_order:
        leaves[key] = _collect_leaves(by_key[key], by_id=by_id, diagnostics=diagnostics)
    for key, values in leaves.items():
        business_keys = [item for item in values if item.node.get("x-business-key") is True]
        if len(business_keys) > 1:
            diagnostics.append(
                _error(
                    6,
                    f"/record_schemas/{_escape_pointer(key)}",
                    "A record schema declares more than one x-business-key.",
                    "Keep at most one business-key property per record schema.",
                )
            )
        duplicate_attribute_keys = sorted(
            item
            for item, count in Counter(value.attribute_key for value in values).items()
            if count > 1
        )
        for duplicate in duplicate_attribute_keys:
            diagnostics.append(
                _error(
                    6,
                    f"/record_schemas/{_escape_pointer(key)}",
                    f"Flattened Attribute key '{duplicate}' is produced more than once.",
                    "Rename or restructure the source properties so every flattened key is unique.",
                )
            )

    projected: list[ProjectedCatalogObject] = [
        ProjectedCatalogObject(
            "database",
            bundle.database.key,
            None,
            _canonical_mapping(
                {
                    "key": bundle.database.key,
                    "name": bundle.database.name,
                    "description": bundle.database.description,
                }
            ),
        ),
        ProjectedCatalogObject(
            "profile",
            bundle.profile.key,
            bundle.database.key,
            _canonical_mapping(
                {
                    "database_key": bundle.database.key,
                    "key": bundle.profile.key,
                    "name": bundle.profile.name,
                    "description": bundle.profile.description,
                }
            ),
            (("database", None, bundle.database.key),),
        ),
    ]
    for key in bundle.dependency_order:
        record = by_key[key]
        projected.append(
            ProjectedCatalogObject(
                "table",
                record.key,
                None,
                _canonical_mapping(
                    {
                        "key": record.key,
                        "name": record.name,
                        "description": record.description,
                        **(
                            {"data_category": record.data_category}
                            if record.data_category is not None
                            else {}
                        ),
                    }
                ),
            )
        )

    link_contents: list[dict[str, Any]] = []
    for key in bundle.dependency_order:
        record = by_key[key]
        attribute_dependencies: list[tuple[str, str | None, str]] = []
        projected_attribute_leaves: list[_LeafProjection] = []
        for leaf in leaves[key]:
            content, link = _attribute_content(leaf, by_key=by_key, diagnostics=diagnostics)
            if link is not None:
                link_contents.append(link)
            if content is None:
                continue
            dependencies: list[tuple[str, str | None, str]] = [("table", None, key)]
            reference_table_key = content.get("reference_table_key")
            if isinstance(reference_table_key, str):
                dependencies.append(("table", None, reference_table_key))
            projected.append(
                ProjectedCatalogObject(
                    "attribute",
                    leaf.attribute_key,
                    key,
                    content,
                    tuple(dependencies),
                )
            )
            attribute_dependencies.append(("attribute", key, leaf.attribute_key))
            projected_attribute_leaves.append(leaf)
        layout_key = f"{bundle.bundle_key}.{record.key}.default"
        layout_name = f"{record.name} default layout"
        if len(layout_name) > 200:
            diagnostics.append(
                _error(
                    12,
                    f"/record_schemas/{_escape_pointer(record.key)}/name",
                    "The generated default Layout name exceeds the Catalog limit.",
                    "Shorten the record display name to at most 185 characters.",
                )
            )
        layout_items = [
            {
                "attribute_key": leaf.attribute_key,
                "section": leaf.section,
                "ordinal": ordinal,
            }
            for ordinal, leaf in enumerate(projected_attribute_leaves)
        ]
        projected.append(
            ProjectedCatalogObject(
                "layout",
                layout_key,
                key,
                _canonical_mapping(
                    {
                        "name": layout_name,
                        "description": (
                            "Projected default layout for Schema Definition Bundle "
                            f"record '{record.key}'."
                        ),
                        "items": layout_items,
                    }
                ),
                (("table", None, key), *attribute_dependencies),
            )
        )
        placement_key = f"{bundle.profile.key}.{record.key}"
        projected.append(
            ProjectedCatalogObject(
                "profile_table_placement",
                placement_key,
                bundle.profile.key,
                _canonical_mapping({"profile_key": bundle.profile.key, "table_key": record.key}),
                (("profile", bundle.database.key, bundle.profile.key), ("table", None, key)),
            )
        )

    seen_links: dict[str, dict[str, Any]] = {}
    for content in sorted(link_contents, key=lambda item: cast(str, item["key"])):
        key = cast(str, content["key"])
        if key in seen_links:
            diagnostics.append(
                _error(
                    6,
                    "/record_schemas",
                    f"Duplicate x-reference link_key '{key}' was found.",
                    "Use a unique stable link_key for every projected Link Type.",
                )
            )
            continue
        seen_links[key] = content
        source = cast(str, content["source_table_key"])
        target = cast(str, content["target_table_key"])
        projected.append(
            ProjectedCatalogObject(
                "link_type",
                key,
                None,
                content,
                (("table", None, source), ("table", None, target)),
            )
        )
    diagnostics.sort(key=lambda item: (item.location, item.code, item.message))
    return tuple(projected), tuple(diagnostics)


def _comparable_content(target_type: str, value: Mapping[str, Any]) -> dict[str, Any]:
    content = dict(value)
    if target_type == "attribute":
        content.pop("source_pointer", None)
        content.pop("source_schema_id", None)
        content.pop("source_schema_version", None)
        content.pop("source_file", None)
        content.pop("source_file_sha256", None)
        content.pop("adapter_semantics", None)
    return _canonical_mapping(content)


def _immutable_conflict(
    projected: ProjectedCatalogObject,
    current: CatalogStateObject,
    classification: DataClassification,
) -> str | None:
    if current.classification is not None and current.classification is not classification:
        return "classification_conflict"
    if (
        projected.target_type == "profile"
        and projected.parent_external_key != current.parent_external_key
    ):
        return "profile_database_conflict"
    if projected.target_type == "attribute" and projected.content.get(
        "data_type"
    ) != current.content.get("data_type"):
        return "attribute_type_conflict"
    if projected.target_type == "link_type":
        endpoint_fields = ("source_table_key", "target_table_key")
        if any(projected.content.get(key) != current.content.get(key) for key in endpoint_fields):
            return "link_endpoint_conflict"
    return None


def _invalid_plan(
    source: SourceArtifactIdentity,
    snapshot: CatalogSnapshot,
    diagnostics: Sequence[BundleDiagnostic],
    *,
    bundle: SchemaDefinitionBundle | None = None,
) -> SchemaBundlePlan:
    action = SchemaBundlePlanAction(
        0,
        PlanDisposition.ERROR,
        "bundle",
        bundle.bundle_key if bundle is not None else "bundle",
        None,
        None,
        None,
        ("bundle_validation_failed",),
    )
    ordered = tuple(sorted(diagnostics, key=lambda item: (item.location, item.code, item.message)))
    provisional = SchemaBundlePlan(source, bundle, snapshot.fingerprint, (action,), ordered, "")
    return SchemaBundlePlan(
        source,
        bundle,
        snapshot.fingerprint,
        (action,),
        ordered,
        content_sha256(provisional.canonical(include_fingerprint=False)),
    )


def build_schema_bundle_plan(
    *,
    source: SourceArtifactIdentity,
    raw_bytes: bytes | None,
    snapshot: CatalogSnapshot,
    organization_id: UUID,
    project_id: UUID,
    classification_allowed: Callable[[DataClassification], bool],
    source_diagnostics: Sequence[BundleDiagnostic] = (),
) -> SchemaBundlePlan:
    if raw_bytes is None:
        return _invalid_plan(source, snapshot, source_diagnostics)
    bundle, parse_diagnostics = parse_schema_definition_bundle(
        raw_bytes,
        organization_id=organization_id,
        project_id=project_id,
        source_classification=source.classification,
        classification_allowed=classification_allowed,
    )
    diagnostics = [*source_diagnostics, *parse_diagnostics]
    if bundle is None:
        return _invalid_plan(source, snapshot, diagnostics)
    projected, projection_diagnostics = project_schema_definition_bundle(bundle)
    diagnostics.extend(projection_diagnostics)
    if any(item.severity is DiagnosticSeverity.ERROR for item in diagnostics):
        return _invalid_plan(source, snapshot, diagnostics, bundle=bundle)

    resulting_business_keys: dict[str, set[str]] = defaultdict(set)
    for state_item in snapshot.objects:
        if (
            state_item.target_type == "attribute"
            and state_item.parent_external_key is not None
            and state_item.content.get("business_key") is True
        ):
            resulting_business_keys[state_item.parent_external_key].add(
                state_item.external_key
            )
    for projected_item in projected:
        if (
            projected_item.target_type != "attribute"
            or projected_item.parent_external_key is None
        ):
            continue
        keys = resulting_business_keys[projected_item.parent_external_key]
        keys.discard(projected_item.external_key)
        if projected_item.content.get("business_key") is True:
            keys.add(projected_item.external_key)
    for table_key, keys in sorted(resulting_business_keys.items()):
        if len(keys) > 1:
            diagnostics.append(
                _error(
                    15,
                    f"/catalog/table/{_escape_pointer(table_key)}/business_key",
                    "Bundle apply would leave more than one governed business-key Attribute.",
                    "Explicitly retire the existing business-key designation before applying "
                    "a different key; delete_missing=false never demotes it silently.",
                )
            )
    if any(item.severity is DiagnosticSeverity.ERROR for item in diagnostics):
        return _invalid_plan(source, snapshot, diagnostics, bundle=bundle)

    current_by_key: dict[tuple[str, str | None, str], list[CatalogStateObject]] = defaultdict(list)
    current_by_type_parent: dict[tuple[str, str | None], list[CatalogStateObject]] = defaultdict(
        list
    )
    profiles_by_external_key: dict[str, list[CatalogStateObject]] = defaultdict(list)
    for state_item in snapshot.objects:
        current_by_key[state_item.key()].append(state_item)
        current_by_type_parent[(state_item.target_type, state_item.parent_external_key)].append(
            state_item
        )
        if state_item.target_type == "profile":
            profiles_by_external_key[state_item.external_key].append(state_item)

    actions: list[SchemaBundlePlanAction] = []
    dispositions: dict[tuple[str, str | None, str], PlanDisposition] = {}
    for projected_item in projected:
        match_candidates = (
            profiles_by_external_key.get(projected_item.external_key, ())
            if projected_item.target_type == "profile"
            else current_by_key.get(projected_item.key(), ())
        )
        matches = sorted(
            match_candidates,
            key=lambda value: (
                str(value.object_id) if value.object_id is not None else "",
                str(value.revision_id) if value.revision_id is not None else "",
            ),
        )
        current: CatalogStateObject | None = matches[0] if len(matches) == 1 else None
        reason_codes: tuple[str, ...]
        if len(matches) > 1:
            disposition = PlanDisposition.CONFLICT
            reason_codes = ("ambiguous_stable_identity",)
            diagnostics.append(
                _error(
                    13,
                    f"/catalog/{projected_item.target_type}/"
                    f"{_escape_pointer(projected_item.external_key)}",
                    "More than one current Catalog object matches the projected stable identity.",
                    "Resolve the duplicate identities before retrying; the planner "
                    "will not take ownership.",
                )
            )
        elif projected_item.target_type == "layout" and current is None:
            same_name = [
                value
                for value in current_by_type_parent.get(
                    ("layout", projected_item.parent_external_key), ()
                )
                if value.content.get("name") == projected_item.content.get("name")
            ]
            if same_name:
                disposition = PlanDisposition.CONFLICT
                reason_codes = ("unowned_layout_name_conflict",)
                diagnostics.append(
                    _error(
                        13,
                        f"/catalog/layout/{_escape_pointer(projected_item.external_key)}",
                        "An existing Layout has the projected name but no exact "
                        "bundle-owned identity.",
                        "Rename the existing Layout or establish ownership during "
                        "the later governed apply flow.",
                    )
                )
            else:
                disposition = PlanDisposition.CREATE
                reason_codes = ("target_missing",)
        elif current is None:
            disposition = PlanDisposition.CREATE
            reason_codes = ("target_missing",)
        else:
            immutable = _immutable_conflict(
                projected_item,
                current,
                bundle.scope.classification,
            )
            if immutable is not None:
                disposition = PlanDisposition.CONFLICT
                reason_codes = (immutable,)
                diagnostics.append(
                    _error(
                        13,
                        f"/catalog/{projected_item.target_type}/"
                        f"{_escape_pointer(projected_item.external_key)}",
                        "Projected content conflicts with an immutable Catalog identity rule.",
                        "Use a new stable external key or correct the bundle mapping.",
                    )
                )
            else:
                changed_dependency = not current.dependency_heads_match or any(
                    dispositions.get(dependency)
                    in {
                        PlanDisposition.CREATE,
                        PlanDisposition.UPDATE,
                        PlanDisposition.CONFLICT,
                        PlanDisposition.ERROR,
                    }
                    for dependency in projected_item.dependencies
                )
                same_content = _comparable_content(
                    projected_item.target_type, projected_item.content
                ) == _comparable_content(projected_item.target_type, current.content)
                if same_content and not changed_dependency:
                    disposition = PlanDisposition.NO_OP
                    reason_codes = ("projected_content_matches",)
                else:
                    disposition = PlanDisposition.UPDATE
                    reason_codes = (
                        "dependency_revision_changes"
                        if changed_dependency and same_content
                        else "projected_content_changed",
                    )
        migration_message: str | None = None
        if disposition is PlanDisposition.UPDATE and current is not None:
            if projected_item.target_type == "table" and current.has_current_records:
                migration_message = (
                    f"Table '{projected_item.external_key}' has current Records "
                    "that pin its old revision."
                )
            elif projected_item.target_type == "attribute" and current.has_current_values:
                migration_message = (
                    f"Attribute '{projected_item.external_key}' has current values "
                    "that pin its old revision."
                )
        elif (
            disposition is PlanDisposition.CREATE
            and projected_item.target_type == "attribute"
            and projected_item.content.get("required") is True
            and projected_item.parent_external_key is not None
        ):
            parent_tables = current_by_key.get(
                ("table", None, projected_item.parent_external_key), ()
            )
            if len(parent_tables) == 1 and parent_tables[0].has_current_records:
                migration_message = (
                    f"Required Attribute '{projected_item.external_key}' is missing "
                    "from current Records."
                )
        if migration_message is not None:
            disposition = PlanDisposition.ERROR
            reason_codes = ("record_migration_required",)
            diagnostics.append(
                _error(
                    14,
                    f"/catalog/{projected_item.target_type}/"
                    f"{_escape_pointer(projected_item.external_key)}",
                    migration_message,
                    "Migrate the affected current Records through an approved workflow, "
                    "then request a fresh server plan.",
                )
            )
        dispositions[projected_item.key()] = disposition
        actions.append(
            SchemaBundlePlanAction(
                len(actions),
                disposition,
                projected_item.target_type,
                projected_item.external_key,
                projected_item.parent_external_key,
                CurrentPlanIdentity.from_state(current) if current is not None else None,
                projected_item.content,
                reason_codes,
            )
        )

    diagnostics.sort(key=lambda value: (value.location, value.code, value.message))
    provisional = SchemaBundlePlan(
        source,
        bundle,
        snapshot.fingerprint,
        tuple(actions),
        tuple(diagnostics),
        "",
    )
    return SchemaBundlePlan(
        source,
        bundle,
        snapshot.fingerprint,
        tuple(actions),
        tuple(diagnostics),
        content_sha256(provisional.canonical(include_fingerprint=False)),
    )


def media_type_supported(value: str) -> bool:
    """Return whether an immutable Artifact media type is eligible for Bundle v1 parsing."""

    media_type = value.split(";", maxsplit=1)[0].strip().lower()
    return media_type in _ALLOWED_MEDIA_TYPES

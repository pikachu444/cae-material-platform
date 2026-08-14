"""Format adapters for immutable Catalog Schema Definition Bundle sources.

The Catalog planner consumes one canonical bundle document.  This module keeps
file packaging and the source-v2 dialect outside that domain contract: exact
source bytes remain the immutable Artifact, while a deterministic adapter
produces the canonical bytes used by plan/apply/export.
"""

from __future__ import annotations

import hashlib
import io
import json
import posixpath
import re
import zipfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any, cast
from uuid import UUID

from cmp.modules.catalog.domain.schema_bundles import (
    BUNDLE_CONTRACT_ID,
    BUNDLE_CONTRACT_VERSION,
    BundleDiagnostic,
    DiagnosticSeverity,
)
from cmp.modules.identity_access.domain.authorization import DataClassification
from cmp.modules.units.domain.system import UnitError, canonical_unit_id
from cmp.shared.domain.revisions import canonical_json_bytes, content_sha256

SOURCE_SET_CONTRACT_ID = (
    "https://cmp.example/contracts/catalog/schema-definition-source-set.schema.json"
)
SOURCE_SET_CONTRACT_VERSION = "1.0.0"
SOURCE_SET_MEDIA_TYPE = "application/vnd.cmp.catalog-schema-source-set+json"
SOURCE_ZIP_MEDIA_TYPE = "application/vnd.cmp.catalog-schema-source-set+zip"
SOURCE_V2_DOCUMENT_TYPE = "cmp.catalog-schema-bundle"
SOURCE_V2_SCHEMA_VERSION = "1.0.0"

_CANONICAL_MEDIA_TYPES = frozenset(
    {
        "application/json",
        "application/schema+json",
        "application/vnd.cmp.catalog-schema-definition-bundle+json",
    }
)
_SOURCE_SET_MEDIA_TYPES = frozenset({SOURCE_SET_MEDIA_TYPE})
_ZIP_MEDIA_TYPES = frozenset({"application/zip", SOURCE_ZIP_MEDIA_TYPE})
_SAFE_KEY = re.compile(r"^[a-z][a-z0-9_]{0,62}[a-z0-9]$|^[a-z]$")
_SOURCE_KEY = re.compile(r"^[a-z][a-z0-9_-]{0,126}[a-z0-9]$|^[a-z]$")
_SEMVER_PARTS = re.compile(r"^([0-9]+)\.([0-9]+)\.([0-9]+)$")
_SOURCE_SCHEMA_KEYS = frozenset(
    {
        "$schema",
        "$id",
        "title",
        "description",
        "type",
        "properties",
        "required",
        "additionalProperties",
        "items",
        "minimum",
        "maximum",
        "minLength",
        "maxLength",
        "minItems",
        "maxItems",
        "pattern",
        "format",
        "x-table-key",
        "x-key",
        "x-business-key",
        "x-id-rule",
        "x-reference",
        "x-curve",
        "x-unit",
        "x-quantity",
        "x-discrete",
        "x-discrete-open",
        "x-indexed",
        "x-searchable",
    }
)
_MANIFEST_KEYS = frozenset(
    {
        "document_type",
        "schema_version",
        "bundle_id",
        "bundle_version",
        "description",
        "database",
        "profile",
        "tables",
        "link_types",
        "unit_profiles",
        "import_policy",
    }
)
_TABLE_KEYS = frozenset({"key", "name", "record_schema_ref", "folder_tree", "description"})
_LINK_KEYS = frozenset(
    {
        "key",
        "source_table",
        "target_table",
        "forward_label",
        "reverse_label",
        "source_cardinality",
        "target_cardinality",
        "derived_from",
    }
)
_DERIVED_KEYS = frozenset({"record_schema", "x_reference_property"})
_SUPPRESSED_SOURCE_LINKS = frozenset({"dma_to_elastoplasticity"})
_CURVE_KEYS = frozenset(
    {
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
)
_CATEGORY_BY_TABLE = {
    "technical_data": "technical_data",
    "tensile_test": "test_data",
    "dma_test": "test_data",
    "fld_test": "test_data",
    "elastoplasticity_data": "simulation_data",
    "statistics_data": "simulation_data",
}
_DISPLAY_NAME_BY_TABLE = {
    "technical_data": "Technical Data",
    "tensile_test": "Tensile Test",
    "dma_test": "DMA Test",
    "fld_test": "FLD Test",
    "elastoplasticity_data": "Elastoplasticity",
    "statistics_data": "Statistics",
}


class _DuplicateJsonKey(ValueError):
    pass


def _pairs(values: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in values:
        if key in result:
            raise _DuplicateJsonKey(key)
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON constant {value}")


def _pointer(value: str) -> str:
    return value.replace("~", "~0").replace("/", "~1")


def _source_diagnostic(
    number: int,
    severity: DiagnosticSeverity,
    location: str,
    message: str,
    remediation: str,
) -> BundleDiagnostic:
    return BundleDiagnostic(
        severity,
        f"CMP-SCHEMA-SOURCE-{number:04d}",
        location,
        message,
        remediation,
    )


def _error(number: int, location: str, message: str, remediation: str) -> BundleDiagnostic:
    return _source_diagnostic(number, DiagnosticSeverity.ERROR, location, message, remediation)


def _warning(number: int, location: str, message: str, remediation: str) -> BundleDiagnostic:
    return _source_diagnostic(number, DiagnosticSeverity.WARNING, location, message, remediation)


@dataclass(frozen=True, slots=True)
class NormalizedSchemaDefinitionSource:
    canonical_bytes: bytes | None
    source_format: str
    file_count: int
    diagnostics: tuple[BundleDiagnostic, ...]

    @property
    def valid(self) -> bool:
        return self.canonical_bytes is not None and not any(
            item.severity is DiagnosticSeverity.ERROR for item in self.diagnostics
        )


def _strict_json(raw: bytes, *, location: str) -> tuple[Any | None, BundleDiagnostic | None]:
    try:
        return (
            json.loads(
                raw.decode("utf-8"),
                object_pairs_hook=_pairs,
                parse_constant=_reject_constant,
            ),
            None,
        )
    except UnicodeDecodeError:
        return None, _error(
            1,
            location,
            "Source file is not valid UTF-8.",
            "Encode every JSON source file as UTF-8.",
        )
    except _DuplicateJsonKey as error:
        return None, _error(
            2,
            location,
            f"Duplicate JSON member '{error}' was found.",
            "Remove the duplicate member; precedence is forbidden.",
        )
    except (json.JSONDecodeError, RecursionError, ValueError) as error:
        return None, _error(
            1,
            location,
            f"Source file is not strict JSON: {error}.",
            "Correct the exact source file and upload a new immutable Artifact.",
        )


def _safe_path(value: str) -> str | None:
    if not value or "\\" in value or "\x00" in value or value.startswith("/"):
        return None
    normalized = posixpath.normpath(value)
    if normalized in {".", ".."} or normalized.startswith("../"):
        return None
    if PurePosixPath(normalized).is_absolute():
        return None
    return normalized


def _read_source_set_envelope(
    raw_bytes: bytes,
) -> tuple[dict[str, bytes] | None, list[BundleDiagnostic]]:
    document, diagnostic = _strict_json(raw_bytes, location="")
    if diagnostic is not None:
        return None, [diagnostic]
    if not isinstance(document, dict):
        return None, [
            _error(3, "", "Source-set root must be an object.", "Use the source-set v1 envelope.")
        ]
    diagnostics: list[BundleDiagnostic] = []
    required = {"$schema", "contract_version", "files"}
    for key in sorted(required - set(document)):
        diagnostics.append(_error(3, "", f"Required member '{key}' is missing.", f"Add '{key}'."))
    for key in sorted(set(document) - required):
        diagnostics.append(
            _error(4, f"/{_pointer(key)}", f"Unsupported source-set member '{key}'.", "Remove it.")
        )
    if document.get("$schema") != SOURCE_SET_CONTRACT_ID:
        diagnostics.append(
            _error(
                3,
                "/$schema",
                "Source-set contract identifier is unsupported.",
                f"Use '{SOURCE_SET_CONTRACT_ID}'.",
            )
        )
    if document.get("contract_version") != SOURCE_SET_CONTRACT_VERSION:
        diagnostics.append(
            _error(
                3,
                "/contract_version",
                "Source-set contract version is unsupported.",
                f"Use '{SOURCE_SET_CONTRACT_VERSION}'.",
            )
        )
    files = document.get("files")
    if not isinstance(files, list) or not 2 <= len(files) <= 128:
        diagnostics.append(
            _error(
                3,
                "/files",
                "Source set must contain 2..128 files.",
                "Include one manifest and all referenced record schemas.",
            )
        )
        return None, diagnostics
    result: dict[str, bytes] = {}
    for index, item in enumerate(files):
        location = f"/files/{index}"
        if not isinstance(item, dict) or set(item) != {"path", "sha256", "content"}:
            diagnostics.append(
                _error(
                    3,
                    location,
                    "Each source file requires only path, sha256, and content.",
                    "Rebuild the deterministic source-set envelope.",
                )
            )
            continue
        raw_path = item.get("path")
        path = _safe_path(raw_path) if isinstance(raw_path, str) else None
        content = item.get("content")
        digest = item.get("sha256")
        if path is None:
            diagnostics.append(
                _error(
                    5,
                    f"{location}/path",
                    "Source file path is unsafe.",
                    "Use a relative POSIX path without '..' or backslashes.",
                )
            )
            continue
        if path in result:
            diagnostics.append(
                _error(
                    5,
                    f"{location}/path",
                    f"Source path '{path}' is duplicated.",
                    "Include every source file once.",
                )
            )
            continue
        if not isinstance(content, str):
            diagnostics.append(
                _error(
                    3,
                    f"{location}/content",
                    "Source content must be a UTF-8 text string.",
                    "Supply exact JSON text.",
                )
            )
            continue
        encoded = content.encode("utf-8")
        actual = hashlib.sha256(encoded).hexdigest()
        if digest != actual:
            diagnostics.append(
                _error(
                    6,
                    f"{location}/sha256",
                    f"Source file digest differs for '{path}'.",
                    "Rebuild the envelope from unchanged file bytes.",
                )
            )
            continue
        result[path] = encoded
    return (
        result
        if not any(item.severity is DiagnosticSeverity.ERROR for item in diagnostics)
        else None
    ), diagnostics


def _read_source_zip(
    raw_bytes: bytes,
) -> tuple[dict[str, bytes] | None, list[BundleDiagnostic]]:
    diagnostics: list[BundleDiagnostic] = []
    files: dict[str, bytes] = {}
    try:
        with zipfile.ZipFile(io.BytesIO(raw_bytes)) as archive:
            members = [item for item in archive.infolist() if not item.is_dir()]
            if not 2 <= len(members) <= 128:
                diagnostics.append(
                    _error(
                        7,
                        "",
                        "ZIP source set must contain 2..128 files.",
                        "Include one manifest and all referenced record schemas.",
                    )
                )
                return None, diagnostics
            total = 0
            for index, member in enumerate(members):
                location = f"/zip/{index}"
                path = _safe_path(member.filename)
                if path is None:
                    diagnostics.append(
                        _error(
                            5,
                            location,
                            f"ZIP member path '{member.filename}' is unsafe.",
                            "Use relative POSIX paths without traversal.",
                        )
                    )
                    continue
                if member.flag_bits & 0x1:
                    diagnostics.append(
                        _error(
                            7,
                            location,
                            f"ZIP member '{path}' is encrypted.",
                            "Use an unencrypted source package.",
                        )
                    )
                    continue
                if path in files:
                    diagnostics.append(
                        _error(
                            5,
                            location,
                            f"ZIP member '{path}' is duplicated.",
                            "Include every source file once.",
                        )
                    )
                    continue
                if member.file_size > 16 * 1024 * 1024:
                    diagnostics.append(
                        _error(
                            7,
                            location,
                            f"ZIP member '{path}' exceeds 16 MiB.",
                            "Reduce the schema file size.",
                        )
                    )
                    continue
                total += member.file_size
                if total > 64 * 1024 * 1024:
                    diagnostics.append(
                        _error(
                            7,
                            location,
                            "Expanded ZIP source set exceeds 64 MiB.",
                            "Reduce the source package size.",
                        )
                    )
                    break
                files[path] = archive.read(member)
    except (zipfile.BadZipFile, RuntimeError, OSError) as error:
        diagnostics.append(
            _error(
                7,
                "",
                f"Source package is not a readable ZIP: {error}.",
                "Upload an unencrypted ZIP source set.",
            )
        )
    return (
        files
        if files and not any(item.severity is DiagnosticSeverity.ERROR for item in diagnostics)
        else None
    ), diagnostics


def _normalized_key(
    value: object, *, location: str, diagnostics: list[BundleDiagnostic]
) -> str | None:
    if not isinstance(value, str) or _SOURCE_KEY.fullmatch(value) is None:
        diagnostics.append(
            _error(
                8,
                location,
                "Source stable key is invalid.",
                "Use lowercase letters, digits, '-' or '_'.",
            )
        )
        return None
    normalized = value.replace("-", "_")
    if _SAFE_KEY.fullmatch(normalized) is None:
        diagnostics.append(
            _error(
                8,
                location,
                "Source key cannot map to a Catalog stable key.",
                "Shorten it to 1..64 lowercase snake-case characters.",
            )
        )
        return None
    if normalized != value:
        diagnostics.append(
            _warning(
                8,
                location,
                f"Source key '{value}' is normalized to '{normalized}'.",
                "The exact source spelling remains in the immutable Artifact.",
            )
        )
    return normalized


def _normalized_semver(
    value: object, *, location: str, diagnostics: list[BundleDiagnostic]
) -> str | None:
    match = _SEMVER_PARTS.fullmatch(value) if isinstance(value, str) else None
    if match is None:
        diagnostics.append(
            _error(
                9,
                location,
                "Source version is not a three-part numeric version.",
                "Use a version such as 2.0.0.",
            )
        )
        return None
    normalized = ".".join(str(int(item)) for item in match.groups())
    if normalized != value:
        diagnostics.append(
            _warning(
                9,
                location,
                f"Source version '{value}' is normalized to '{normalized}'.",
                "The exact source spelling remains in the immutable Artifact.",
            )
        )
    return normalized


def _slug(value: str) -> str:
    candidate = re.sub(r"[^a-z0-9]+", "_", value.casefold()).strip("_")
    if not candidate or not candidate[0].isalpha():
        candidate = f"group_{candidate}" if candidate else "group"
    return candidate[:64].rstrip("_")


def _canonical_type(value: object) -> tuple[str | None, bool]:
    if isinstance(value, str):
        return value, False
    if isinstance(value, list) and len(value) == 2 and "null" in value:
        other = next((item for item in value if item != "null"), None)
        return cast(str | None, other), True
    return None, False


def _with_null(base: str, nullable: bool) -> str | list[str]:
    return [base, "null"] if nullable else base


def _canonical_unit(value: object) -> object:
    if not isinstance(value, str):
        return value
    try:
        return canonical_unit_id(value, location="source.x-unit")
    except UnitError:
        return value


def _schema_property_by_source_path(
    schema: Mapping[str, Any], pointer: str
) -> tuple[dict[str, Any], tuple[str, ...]] | None:
    segments = [segment.replace("~1", "/").replace("~0", "~") for segment in pointer.split("/")[1:]]
    node: object = schema
    canonical_path: list[str] = []
    root_properties = schema.get("properties")
    wrapper_key = (
        _slug(next(iter(root_properties)))
        if isinstance(root_properties, dict) and len(root_properties) == 1
        else None
    )
    for index, segment in enumerate(segments):
        if not isinstance(node, dict) or not isinstance(node.get("properties"), dict):
            return None
        child = node["properties"].get(segment)
        if not isinstance(child, dict):
            return None
        source_key = child.get("x-key")
        key = source_key if isinstance(source_key, str) else _slug(segment)
        # source-v2 wraps every record in one table-named object. The wrapper
        # is packaging, not a Catalog Attribute or layout section, so refs are
        # rebased to the unwrapped canonical record root below.
        if not (index == 0 and key == wrapper_key):
            canonical_path.extend(("properties", key))
        node = child
    return cast(dict[str, Any], node), tuple(canonical_path)


def _canonical_ref(schema_id: str, path: tuple[str, ...]) -> str:
    fragment = "/".join(_pointer(item) for item in path)
    return f"{schema_id}#/{fragment}"


@dataclass(frozen=True, slots=True)
class _SourceTable:
    index: int
    key: str
    name: str
    description: str | None
    reference: str
    source_schema: dict[str, Any]
    canonical_schema_id: str
    canonical_schema_version: str


def _link_for_property(
    *,
    links: list[dict[str, Any]],
    record_filename: str,
    property_name: str,
) -> dict[str, Any] | None:
    matches = [
        item
        for item in links
        if isinstance(item.get("derived_from"), dict)
        and item["derived_from"].get("record_schema") == record_filename
        and item["derived_from"].get("x_reference_property") == property_name
    ]
    return matches[0] if len(matches) == 1 else None


def _convert_schema_node(
    node: dict[str, Any],
    *,
    location: str,
    property_name: str | None,
    record_filename: str,
    source_schema_id: str,
    source_schema_version: str,
    source_file: str,
    source_file_sha256: str,
    links: list[dict[str, Any]],
    tables_by_source_key: Mapping[str, _SourceTable],
    diagnostics: list[BundleDiagnostic],
) -> dict[str, Any] | None:
    for key in sorted(set(node) - _SOURCE_SCHEMA_KEYS):
        diagnostics.append(
            _error(
                10,
                f"{location}/{_pointer(key)}",
                f"Source schema keyword '{key}' is unsupported.",
                "Add an explicit versioned adapter mapping or remove the keyword.",
            )
        )
    source_type, nullable = _canonical_type(node.get("type"))
    output: dict[str, Any] = {}
    output["x-source-origin"] = {
        "schema_id": source_schema_id,
        "schema_version": source_schema_version,
        "file": source_file,
        "file_sha256": source_file_sha256,
        "pointer": location,
    }
    for key in (
        "title",
        "description",
        "minimum",
        "maximum",
        "minLength",
        "maxLength",
        "pattern",
        "format",
    ):
        if key in node:
            output[key] = node[key]
    if property_name is not None and "title" not in output:
        output["title"] = property_name
    if property_name == "Force maximum (MPa)":
        output["title"] = "Tensile strength"

    curve = node.get("x-curve")
    reference = node.get("x-reference")
    if curve is not None:
        if not isinstance(curve, dict) or not set(curve).issubset(_CURVE_KEYS):
            diagnostics.append(
                _error(
                    11,
                    f"{location}/x-curve",
                    "Object x-curve metadata is invalid or contains unsupported members.",
                    "Use the reviewed x/y/series/deviation pointer contract.",
                )
            )
            return None
        if "x_pointer" not in curve or "y_pointer" not in curve:
            diagnostics.append(
                _error(
                    11,
                    f"{location}/x-curve",
                    "Curve metadata requires x_pointer and y_pointer.",
                    "Declare both channel pointers.",
                )
            )
            return None
        output["type"] = _with_null("string", nullable)
        output["format"] = "uuid"
        output["x-curve"] = {
            key: _canonical_unit(value) if key.endswith("_unit") else value
            for key, value in curve.items()
        }
    elif reference is not None:
        if not isinstance(reference, dict) or not {"schema_key", "pointer"}.issubset(reference):
            diagnostics.append(
                _error(
                    12,
                    f"{location}/x-reference",
                    "Source x-reference requires schema_key and pointer.",
                    "Correct the reference descriptor.",
                )
            )
            return None
        unsupported = set(reference) - {"schema_key", "pointer", "cardinality"}
        if unsupported:
            diagnostics.append(
                _error(
                    12,
                    f"{location}/x-reference",
                    f"Unsupported x-reference members: {', '.join(sorted(unsupported))}.",
                    "Use only schema_key, pointer, and optional cardinality.",
                )
            )
            return None
        target_key = str(reference["schema_key"]).replace("-", "_")
        target = tables_by_source_key.get(target_key)
        resolved = (
            _schema_property_by_source_path(target.source_schema, str(reference["pointer"]))
            if target is not None
            else None
        )
        if target is None or resolved is None or resolved[0].get("x-business-key") is not True:
            diagnostics.append(
                _error(
                    12,
                    f"{location}/x-reference",
                    "Reference does not resolve to one declared business-key property.",
                    "Correct schema_key and pointer.",
                )
            )
            return None
        manifest_link = _link_for_property(
            links=links,
            record_filename=record_filename,
            property_name=property_name or "",
        )
        if manifest_link is None:
            # The reviewed elastoplasticity DMA value is evidence, not a product relation.
            output["type"] = _with_null("string", nullable)
            evidence_note = f"Evidence reference to {target.name}; no product relation is created."
            output["description"] = (
                f"{output['description']} {evidence_note}"
                if isinstance(output.get("description"), str)
                else evidence_note
            )
            diagnostics.append(
                _warning(
                    21,
                    f"{location}/x-reference",
                    "Reference is retained as evidence and does not create a product relation.",
                    "Use Related only for a reviewed manifest Link Type.",
                )
            )
        else:
            many = reference.get("cardinality") == "many" or source_type == "array"
            output["$ref"] = _canonical_ref(target.canonical_schema_id, resolved[1])
            output["x-reference"] = {
                "link_key": manifest_link["key"],
                "forward_label": manifest_link["forward_label"],
                "reverse_label": manifest_link["reverse_label"],
                # Source-v2 names endpoint participation; the platform names
                # maximum current links at each record endpoint.
                "source_cardinality": manifest_link["target_cardinality"],
                "target_cardinality": manifest_link["source_cardinality"],
                "source_table_key": manifest_link["source_table"],
                "target_table_key": manifest_link["target_table"],
                "reference_only": many,
            }
    elif source_type == "object":
        properties = node.get("properties")
        if not isinstance(properties, dict):
            if node.get("additionalProperties") is True:
                diagnostics.append(
                    _warning(
                        16,
                        location,
                        "Open source object is retained as source evidence and is not "
                        "projected as generic editable data.",
                        "Use the governed typed distribution resource when the value "
                        "becomes product data; generic EAV is forbidden.",
                    )
                )
                return None
            diagnostics.append(
                _error(
                    13,
                    location,
                    "Source object has no declared properties.",
                    "Declare typed properties; opaque objects are not Catalog authority.",
                )
            )
            return None
        output["type"] = "object"
        output["properties"] = {}
        required = (
            set(node.get("required", ())) if isinstance(node.get("required"), list) else set()
        )
        canonical_required: list[str] = []
        seen: set[str] = set()
        for child_name, child in properties.items():
            child_location = f"{location}/properties/{_pointer(child_name)}"
            if not isinstance(child, dict):
                diagnostics.append(
                    _error(
                        13,
                        child_location,
                        "Source property schema must be an object.",
                        "Supply a typed property schema.",
                    )
                )
                continue
            child_type, _ = _canonical_type(child.get("type"))
            child_key: str | None
            if child_type == "object" and child.get("x-curve") is None:
                child_key = _slug(child_name)
            else:
                source_child_key = child.get("x-key")
                child_key = source_child_key if isinstance(source_child_key, str) else None
                if child_key is None:
                    diagnostics.append(
                        _error(
                            14,
                            child_location,
                            f"Leaf property '{child_name}' has no x-key.",
                            "Declare a stable lower_snake_case x-key.",
                        )
                    )
                    continue
                if _SAFE_KEY.fullmatch(child_key) is None:
                    diagnostics.append(
                        _error(
                            14,
                            f"{child_location}/x-key",
                            f"x-key '{child_key}' is invalid.",
                            "Use 1..64 lower_snake_case characters.",
                        )
                    )
                    continue
            if record_filename == "tensile-test-v2.json" and child_key == "force_maximum":
                child_key = "tensile_strength"
                diagnostics.append(
                    _warning(
                        24,
                        f"{child_location}/x-key",
                        "Source field force_maximum is presented as tensile_strength.",
                        "The exact source name remains in Artifact evidence.",
                    )
                )
            if child_key in seen:
                diagnostics.append(
                    _error(
                        14,
                        child_location,
                        f"Mapped property key '{child_key}' is duplicated.",
                        "Use unique x-key values.",
                    )
                )
                continue
            seen.add(child_key)
            converted = _convert_schema_node(
                child,
                location=child_location,
                property_name=child_name,
                record_filename=record_filename,
                source_schema_id=source_schema_id,
                source_schema_version=source_schema_version,
                source_file=source_file,
                source_file_sha256=source_file_sha256,
                links=links,
                tables_by_source_key=tables_by_source_key,
                diagnostics=diagnostics,
            )
            if converted is None:
                continue
            cast(dict[str, Any], output["properties"])[child_key] = converted
            if child_name in required:
                canonical_required.append(child_key)
        if canonical_required:
            output["required"] = canonical_required
        output["additionalProperties"] = False
        if node.get("additionalProperties") is True:
            diagnostics.append(
                _warning(
                    15,
                    f"{location}/additionalProperties",
                    "Open source object is normalized to its declared typed properties.",
                    "Unmodeled values remain in the exact source Artifact and are "
                    "rejected by governed Record entry; generic EAV is forbidden.",
                )
            )
    elif source_type == "array":
        item_type, _ = _canonical_type(
            node.get("items", {}).get("type") if isinstance(node.get("items"), dict) else None
        )
        output["type"] = _with_null("text", nullable)
        output["x-source-array"] = {
            "item_type": item_type,
            "min_items": node.get("minItems"),
            "max_items": node.get("maxItems"),
        }
        diagnostics.append(
            _warning(
                16,
                location,
                "Typed source array is retained as source evidence and is not projected "
                "as an editable scalar Attribute.",
                "Record-data import is outside P1; use a governed typed domain resource "
                "before exposing array editing.",
            )
        )
        return None
    elif source_type in {"string", "number", "integer", "boolean"}:
        if "x-discrete" in node:
            values = node["x-discrete"]
            if (
                not isinstance(values, list)
                or not values
                or not all(isinstance(item, str) and item for item in values)
                or len(values) != len(set(values))
            ):
                diagnostics.append(
                    _error(
                        17,
                        f"{location}/x-discrete",
                        "x-discrete must contain non-empty unique strings.",
                        "Correct the choice list.",
                    )
                )
                return None
            output["type"] = _with_null("string", nullable)
            output["enum"] = values
        else:
            output["type"] = _with_null(source_type, nullable)
        if "x-discrete-open" in node:
            suggestions = node["x-discrete-open"]
            if (
                not isinstance(suggestions, list)
                or not all(isinstance(item, str) and item for item in suggestions)
                or len(suggestions) != len(set(suggestions))
            ):
                diagnostics.append(
                    _error(
                        17,
                        f"{location}/x-discrete-open",
                        "x-discrete-open must contain unique non-empty strings.",
                        "Correct the suggestion list.",
                    )
                )
                return None
            output["x-suggested-values"] = suggestions
        if "x-unit" in node:
            output["x-unit"] = _canonical_unit(node["x-unit"])
        if "x-quantity" in node:
            output["x-quantity"] = node["x-quantity"]
    else:
        diagnostics.append(
            _error(
                13,
                f"{location}/type",
                f"Source type '{node.get('type')}' is unsupported.",
                "Use a supported scalar, object, curve, or reference schema.",
            )
        )
        return None

    for key in ("x-business-key", "x-id-rule", "x-indexed", "x-searchable"):
        if key in node:
            output[key] = node[key]
    return output


def _normalize_source_v2(
    files: Mapping[str, bytes],
    *,
    organization_id: UUID,
    project_id: UUID,
    source_classification: DataClassification,
) -> NormalizedSchemaDefinitionSource:
    diagnostics: list[BundleDiagnostic] = []
    manifest_paths = sorted(
        path for path in files if path.endswith("catalog-schema-bundle.manifest.json")
    )
    if len(manifest_paths) != 1:
        return NormalizedSchemaDefinitionSource(
            None,
            "source-v2",
            len(files),
            (
                _error(
                    18,
                    "",
                    "Source set must contain exactly one catalog-schema-bundle.manifest.json.",
                    "Remove duplicate manifests or include the missing manifest.",
                ),
            ),
        )
    manifest_path = manifest_paths[0]
    manifest_value, diagnostic = _strict_json(
        files[manifest_path], location=f"/files/{_pointer(manifest_path)}"
    )
    if diagnostic is not None or not isinstance(manifest_value, dict):
        return NormalizedSchemaDefinitionSource(
            None,
            "source-v2",
            len(files),
            (
                diagnostic
                or _error(
                    3, "/manifest", "Manifest root must be an object.", "Correct the manifest."
                ),
            ),
        )
    manifest = cast(dict[str, Any], manifest_value)
    for key in sorted(set(manifest) - _MANIFEST_KEYS):
        diagnostics.append(
            _error(
                10,
                f"/manifest/{_pointer(key)}",
                f"Manifest member '{key}' is unsupported.",
                "Add an explicit adapter mapping or remove it.",
            )
        )
    for key in sorted(_MANIFEST_KEYS - set(manifest)):
        diagnostics.append(
            _error(3, "/manifest", f"Required manifest member '{key}' is missing.", f"Add '{key}'.")
        )
    if manifest.get("document_type") != SOURCE_V2_DOCUMENT_TYPE:
        diagnostics.append(
            _error(
                3,
                "/manifest/document_type",
                "Source document_type is unsupported.",
                f"Use '{SOURCE_V2_DOCUMENT_TYPE}'.",
            )
        )
    if manifest.get("schema_version") != SOURCE_V2_SCHEMA_VERSION:
        diagnostics.append(
            _error(
                3,
                "/manifest/schema_version",
                "Source schema_version is unsupported.",
                f"Use '{SOURCE_V2_SCHEMA_VERSION}'.",
            )
        )
    bundle_key = _normalized_key(
        manifest.get("bundle_id"), location="/manifest/bundle_id", diagnostics=diagnostics
    )
    bundle_version = _normalized_semver(
        manifest.get("bundle_version"), location="/manifest/bundle_version", diagnostics=diagnostics
    )
    database = manifest.get("database")
    profile = manifest.get("profile")
    if not isinstance(database, dict) or not isinstance(profile, dict):
        diagnostics.append(
            _error(
                3,
                "/manifest",
                "database and profile must be objects.",
                "Supply key and name for both definitions.",
            )
        )
    else:
        for label, definition in (("database", database), ("profile", profile)):
            if set(definition) != {"key", "name"}:
                diagnostics.append(
                    _error(
                        3,
                        f"/manifest/{label}",
                        f"{label} must contain only key and name.",
                        f"Correct the source-v2 {label} definition.",
                    )
                )
    tables_value = manifest.get("tables")
    links_value = manifest.get("link_types")
    if not isinstance(tables_value, list) or not tables_value:
        diagnostics.append(
            _error(
                3,
                "/manifest/tables",
                "Manifest tables must be a non-empty array.",
                "Declare every source Table.",
            )
        )
        tables_value = []
    if not isinstance(links_value, list):
        diagnostics.append(
            _error(
                3,
                "/manifest/link_types",
                "Manifest link_types must be an array.",
                "Declare reviewed relations.",
            )
        )
        links_value = []
    links: list[dict[str, Any]] = []
    for index, item in enumerate(links_value):
        if not isinstance(item, dict) or set(item) != _LINK_KEYS:
            diagnostics.append(
                _error(
                    3,
                    f"/manifest/link_types/{index}",
                    "Link Type must contain the exact source-v2 members.",
                    "Correct the manifest Link Type.",
                )
            )
            continue
        derived = item.get("derived_from")
        if (
            not isinstance(derived, dict)
            or set(derived) != _DERIVED_KEYS
            or not all(isinstance(derived.get(key), str) and derived[key] for key in _DERIVED_KEYS)
        ):
            diagnostics.append(
                _error(
                    3,
                    f"/manifest/link_types/{index}/derived_from",
                    "Link Type source evidence is incomplete or has unsupported members.",
                    "Supply record_schema and x_reference_property only.",
                )
            )
            continue
        if item.get("key") in _SUPPRESSED_SOURCE_LINKS:
            diagnostics.append(
                _warning(
                    29,
                    f"/manifest/link_types/{index}",
                    "The source relation is preserved as evidence but is not an approved "
                    "product link.",
                    "No DMA-to-elastoplasticity relation is created; retain the original "
                    "source artifact for audit.",
                )
            )
            continue
        links.append(cast(dict[str, Any], item))
    manifest_directory = posixpath.dirname(manifest_path)
    source_tables: list[_SourceTable] = []
    for index, item in enumerate(tables_value):
        location = f"/manifest/tables/{index}"
        if not isinstance(item, dict) or set(item) != _TABLE_KEYS:
            diagnostics.append(
                _error(
                    3,
                    location,
                    "Table must contain the exact source-v2 members.",
                    "Correct the manifest Table.",
                )
            )
            continue
        folder_tree = item.get("folder_tree")
        if not isinstance(folder_tree, list) or not all(
            isinstance(level, str) and level.strip() == level and level for level in folder_tree
        ):
            diagnostics.append(
                _error(
                    3,
                    f"{location}/folder_tree",
                    "folder_tree must contain trimmed source field names.",
                    "Correct the source-v2 folder dimensions.",
                )
            )
        elif folder_tree:
            diagnostics.append(
                _warning(
                    26,
                    f"{location}/folder_tree",
                    "Folder fields are saved with the data format, but no folders are created "
                    "until matching data exists.",
                    "Use Administration to inspect the internal storage structure. Applying a "
                    "data format does not create empty folders.",
                )
            )
        table_key = _normalized_key(
            item.get("key"), location=f"{location}/key", diagnostics=diagnostics
        )
        reference = _safe_path(str(item.get("record_schema_ref", "")))
        resolved_path = posixpath.normpath(posixpath.join(manifest_directory, reference or ""))
        if table_key is None or reference is None or resolved_path not in files:
            diagnostics.append(
                _error(
                    19,
                    f"{location}/record_schema_ref",
                    f"Referenced source schema '{item.get('record_schema_ref')}' is unavailable.",
                    "Include the exact referenced file in the source set.",
                )
            )
            continue
        schema_value, schema_diagnostic = _strict_json(
            files[resolved_path], location=f"/files/{_pointer(resolved_path)}"
        )
        if schema_diagnostic is not None or not isinstance(schema_value, dict):
            diagnostics.append(
                schema_diagnostic
                or _error(
                    3,
                    f"/files/{_pointer(resolved_path)}",
                    "Record schema root must be an object.",
                    "Correct the schema.",
                )
            )
            continue
        source_schema = cast(dict[str, Any], schema_value)
        source_version = _normalized_semver(
            str(source_schema.get("$id", "")).rsplit(":", 1)[-1],
            location=f"/files/{_pointer(resolved_path)}/$id",
            diagnostics=diagnostics,
        )
        if source_version is None:
            continue
        canonical_schema_id = f"urn:cmp:catalog-schema:{table_key}:{source_version}"
        source_tables.append(
            _SourceTable(
                index,
                table_key,
                _DISPLAY_NAME_BY_TABLE.get(table_key, str(item.get("name") or table_key)),
                cast(str | None, item.get("description")),
                resolved_path,
                source_schema,
                canonical_schema_id,
                source_version,
            )
        )
        reviewed_name = _DISPLAY_NAME_BY_TABLE.get(table_key)
        if reviewed_name is not None and item.get("name") != reviewed_name:
            diagnostics.append(
                _warning(
                    25,
                    f"{location}/name",
                    f"Source Table name is presented as '{reviewed_name}'.",
                    "The exact source label remains in immutable Artifact evidence.",
                )
            )
    tables_by_key = {item.key: item for item in source_tables}
    if len(tables_by_key) != len(source_tables):
        diagnostics.append(
            _error(
                8,
                "/manifest/tables",
                "Mapped Table keys are not unique.",
                "Use one stable key per Table.",
            )
        )

    referenced_files = {manifest_path, *(item.reference for item in source_tables)}
    for path in sorted(set(files) - referenced_files):
        diagnostics.append(
            _warning(
                27,
                f"/files/{_pointer(path)}",
                "Unreferenced package file remains Artifact evidence and is not schema input.",
                "Reference it from the manifest to make it part of governed schema apply.",
            )
        )
    declared_link_keys: set[str] = set()
    for index, link in enumerate(links):
        location = f"/manifest/link_types/{index}"
        link_key = link.get("key")
        source = link.get("source_table")
        target = link.get("target_table")
        if (
            not isinstance(link_key, str)
            or _SAFE_KEY.fullmatch(link_key) is None
            or link_key in declared_link_keys
        ):
            diagnostics.append(
                _error(
                    8,
                    f"{location}/key",
                    "Link Type key is invalid or duplicated.",
                    "Use a unique lower_snake_case key.",
                )
            )
        else:
            declared_link_keys.add(link_key)
        if source not in tables_by_key or target not in tables_by_key:
            diagnostics.append(
                _error(
                    12,
                    location,
                    "Link Type endpoint does not name a declared Table.",
                    "Correct source_table and target_table.",
                )
            )
        if link.get("source_cardinality") not in {"one", "many"} or link.get(
            "target_cardinality"
        ) not in {"one", "many"}:
            diagnostics.append(
                _error(
                    12,
                    location,
                    "Link Type cardinality is invalid.",
                    "Use one or many at each endpoint.",
                )
            )

    record_entries: list[dict[str, Any]] = []
    for table in source_tables:
        schema_location = f"/files/{_pointer(table.reference)}"
        if table.source_schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
            diagnostics.append(
                _error(
                    3,
                    f"{schema_location}/$schema",
                    "Record schema draft is unsupported.",
                    "Use JSON Schema draft 2020-12.",
                )
            )
        source_table_key = str(table.source_schema.get("x-table-key", "")).replace("-", "_")
        if source_table_key != table.key:
            diagnostics.append(
                _error(
                    12,
                    f"{schema_location}/x-table-key",
                    "x-table-key does not match its manifest Table.",
                    "Use the exact manifest Table key.",
                )
            )
        converted = _convert_schema_node(
            table.source_schema,
            location=schema_location,
            property_name=None,
            record_filename=posixpath.basename(table.reference),
            source_schema_id=str(table.source_schema["$id"]),
            source_schema_version=table.canonical_schema_version,
            source_file=table.reference,
            source_file_sha256=hashlib.sha256(files[table.reference]).hexdigest(),
            links=links,
            tables_by_source_key=tables_by_key,
            diagnostics=diagnostics,
        )
        if converted is None:
            continue
        source_properties = table.source_schema.get("properties")
        wrapper = (
            next(iter(source_properties))
            if isinstance(source_properties, dict) and len(source_properties) == 1
            else None
        )
        wrapper_key = _slug(wrapper) if isinstance(wrapper, str) else None
        converted_properties = converted.get("properties")
        if (
            wrapper_key in {table.key, table.key.removesuffix("_data")}
            and isinstance(converted_properties, dict)
            and isinstance(converted_properties.get(wrapper_key), dict)
        ):
            converted = dict(converted_properties[wrapper_key])
        else:
            diagnostics.append(
                _error(
                    23,
                    schema_location,
                    "Source record does not have its one table-named packaging wrapper.",
                    "Keep one top-level object matching x-table-key in source-v2.",
                )
            )
        if _CATEGORY_BY_TABLE.get(table.key) == "test_data":
            data_information = (
                converted.get("properties", {}).get("data_information")
                if isinstance(converted.get("properties"), dict)
                else None
            )
            reference_properties = (
                data_information.get("properties") if isinstance(data_information, dict) else None
            )
            if not isinstance(reference_properties, dict) or not isinstance(
                reference_properties.get("technical_data_ref"), dict
            ):
                diagnostics.append(
                    _error(
                        28,
                        schema_location,
                        "Test Data has no governed Technical Data reference.",
                        "Declare Technical Data ID as an x-reference in source-v2.",
                    )
                )
            else:
                assert isinstance(data_information, dict)
                root_required = set(converted.get("required", ()))
                root_required.add("data_information")
                converted["required"] = sorted(root_required)
                required = set(data_information.get("required", ()))
                required.add("technical_data_ref")
                data_information["required"] = sorted(required)
                diagnostics.append(
                    _warning(
                        28,
                        f"{schema_location}/properties/{wrapper_key}/properties/"
                        "Data Information/properties/Technical Data ID",
                        "Optional source reference is required by the reviewed "
                        "Test Data product rule.",
                        "Choose an existing Technical Data item before registering Test Data.",
                    )
                )
        converted["$schema"] = "https://json-schema.org/draft/2020-12/schema"
        converted["$id"] = table.canonical_schema_id
        converted["title"] = table.name
        converted["additionalProperties"] = False
        entry = {
            "key": table.key,
            "name": table.name,
            "description": table.description,
            "schema_version": table.canonical_schema_version,
            "data_category": _CATEGORY_BY_TABLE.get(table.key),
            "schema": converted,
        }
        entry["schema_sha256"] = content_sha256(converted)
        record_entries.append(entry)

    policy = manifest.get("import_policy")
    expected_policy = {
        "conflict_strategy": "upsert_by_key",
        "publish": "all_or_nothing",
        "dry_run_default": True,
        "on_schema_change": "new_revision",
        "delete_missing": False,
    }
    if policy != expected_policy:
        diagnostics.append(
            _error(
                22,
                "/manifest/import_policy",
                "Source import policy is not the atomic non-destructive policy.",
                "Use upsert_by_key, all_or_nothing, dry-run, new revisions, and "
                "delete_missing=false.",
            )
        )
    unit_profiles = manifest.get("unit_profiles")
    if not isinstance(unit_profiles, list):
        diagnostics.append(
            _error(
                3,
                "/manifest/unit_profiles",
                "unit_profiles must be an array.",
                "Declare zero or more bounded profiles.",
            )
        )
        unit_profiles = []

    canonical: dict[str, Any] | None = None
    if (
        bundle_key is not None
        and bundle_version is not None
        and isinstance(database, dict)
        and isinstance(profile, dict)
        and len(record_entries) == len(source_tables) == len(tables_value)
    ):
        canonical = {
            "$schema": BUNDLE_CONTRACT_ID,
            "contract_version": BUNDLE_CONTRACT_VERSION,
            "bundle_key": bundle_key,
            "bundle_version": bundle_version,
            "scope": {
                "organization_id": str(organization_id),
                "project_id": str(project_id),
                "classification": source_classification.value,
            },
            "catalog": {
                "database": {
                    "key": database.get("key"),
                    "name": database.get("name"),
                    "description": manifest.get("description"),
                },
                "profile": {
                    "key": profile.get("key"),
                    "name": profile.get("name"),
                    "description": None,
                },
            },
            "record_schemas": record_entries,
            "unit_profiles": unit_profiles,
        }
    ordered = tuple(sorted(diagnostics, key=lambda item: (item.location, item.code, item.message)))
    if canonical is None or any(item.severity is DiagnosticSeverity.ERROR for item in ordered):
        return NormalizedSchemaDefinitionSource(None, "source-v2", len(files), ordered)
    return NormalizedSchemaDefinitionSource(
        canonical_json_bytes(canonical), "source-v2", len(files), ordered
    )


def normalize_schema_definition_source(
    raw_bytes: bytes,
    *,
    media_type: str,
    organization_id: UUID,
    project_id: UUID,
    source_classification: DataClassification,
) -> NormalizedSchemaDefinitionSource:
    """Normalize a canonical JSON document, source-set envelope, or ZIP package."""

    normalized_media = media_type.split(";", maxsplit=1)[0].strip().lower()
    if normalized_media in _CANONICAL_MEDIA_TYPES:
        document, diagnostic = _strict_json(raw_bytes, location="")
        if diagnostic is not None:
            return NormalizedSchemaDefinitionSource(None, "canonical-json", 1, (diagnostic,))
        if isinstance(document, dict) and document.get("$schema") == SOURCE_SET_CONTRACT_ID:
            files, diagnostics = _read_source_set_envelope(raw_bytes)
            if files is None:
                return NormalizedSchemaDefinitionSource(None, "source-set", 0, tuple(diagnostics))
            return _normalize_source_v2(
                files,
                organization_id=organization_id,
                project_id=project_id,
                source_classification=source_classification,
            )
        if isinstance(document, dict) and document.get("document_type") == SOURCE_V2_DOCUMENT_TYPE:
            return NormalizedSchemaDefinitionSource(
                None,
                "source-v2-manifest",
                1,
                (
                    _error(
                        19,
                        "/tables",
                        "A manifest alone cannot resolve record_schema_ref files.",
                        "Choose the manifest and all referenced JSON files, or upload one ZIP.",
                    ),
                ),
            )
        return NormalizedSchemaDefinitionSource(raw_bytes, "canonical-json", 1, ())
    if normalized_media in _SOURCE_SET_MEDIA_TYPES:
        files, diagnostics = _read_source_set_envelope(raw_bytes)
        if files is None:
            return NormalizedSchemaDefinitionSource(None, "source-set", 0, tuple(diagnostics))
        result = _normalize_source_v2(
            files,
            organization_id=organization_id,
            project_id=project_id,
            source_classification=source_classification,
        )
        return NormalizedSchemaDefinitionSource(
            result.canonical_bytes,
            result.source_format,
            result.file_count,
            tuple(
                sorted(
                    (*diagnostics, *result.diagnostics),
                    key=lambda item: (item.location, item.code, item.message),
                )
            ),
        )
    if normalized_media in _ZIP_MEDIA_TYPES:
        files, diagnostics = _read_source_zip(raw_bytes)
        if files is None:
            return NormalizedSchemaDefinitionSource(None, "source-zip", 0, tuple(diagnostics))
        result = _normalize_source_v2(
            files,
            organization_id=organization_id,
            project_id=project_id,
            source_classification=source_classification,
        )
        return NormalizedSchemaDefinitionSource(
            result.canonical_bytes,
            result.source_format,
            result.file_count,
            tuple(
                sorted(
                    (*diagnostics, *result.diagnostics),
                    key=lambda item: (item.location, item.code, item.message),
                )
            ),
        )
    return NormalizedSchemaDefinitionSource(
        None,
        "unsupported",
        0,
        (
            _error(
                23,
                "/media_type",
                f"Artifact media type '{normalized_media}' has no Schema Definition "
                "source adapter.",
                "Use canonical JSON, a source-set envelope, or ZIP. Add a versioned "
                "adapter before accepting another format.",
            ),
        ),
    )


def source_media_type_supported(value: str) -> bool:
    media_type = value.split(";", maxsplit=1)[0].strip().lower()
    return media_type in _CANONICAL_MEDIA_TYPES | _SOURCE_SET_MEDIA_TYPES | _ZIP_MEDIA_TYPES


__all__ = [
    "SOURCE_SET_CONTRACT_ID",
    "SOURCE_SET_MEDIA_TYPE",
    "SOURCE_ZIP_MEDIA_TYPE",
    "NormalizedSchemaDefinitionSource",
    "normalize_schema_definition_source",
    "source_media_type_supported",
]

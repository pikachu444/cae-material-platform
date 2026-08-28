"""Strict, deterministic JSON Record registration primitives (Issue #342).

This module is deliberately independent of the HTTP and PostgreSQL adapters.  It is the
single place that defines the byte-level package contract, diagnostics, JSON Pointer
resolution, and the source-aware CSV representation used by the registration command.
The Catalog application layer is responsible for resolving installed revisions and writing
typed values; this module never treats the source JSON as business authority.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import posixpath
import re
import struct
import unicodedata
import zipfile
import zlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

JSON_REGISTRATION_CONTRACT_ID = (
    "https://cmp.example/contracts/catalog/json-record-registration.schema.json"
)
JSON_REGISTRATION_CONTRACT_VERSION = "1.0.0"
JSON_PACKAGE_CONTRACT_ID = "cmp.catalog-record-registration-package"
JSON_PACKAGE_CONTRACT_VERSION = "1.0.0"
JSON_PACKAGE_MEDIA_TYPE = "application/zip"
JSON_MEDIA_TYPE = "application/json"
MAX_SINGLE_JSON_BYTES = 25 * 1024 * 1024
MAX_PACKAGE_ENTRIES = 100
MAX_PACKAGE_ENTRY_BYTES = 250 * 1024 * 1024
MAX_PACKAGE_UNCOMPRESSED_BYTES = 250 * 1024 * 1024
# The upload service's existing verified Artifact cap is 64 MiB.  Keep the package
# contract below that transport ceiling; larger source sets must be split into a
# subsequent registration batch rather than widening the global Artifact reader.
MAX_PACKAGE_ARCHIVE_BYTES = 64 * 1024 * 1024

SOURCE_CSV_HEADER = (
    "section",
    "json_pointer",
    "label",
    "value",
    "original_unit",
    "normalized_value",
    "normalized_unit",
    "missing_reason",
    "curve_index",
    "x",
    "y",
    "x_unit",
    "y_unit",
)


class JsonRegistrationError(ValueError):
    """A stable per-file registration diagnostic."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        pointer: str | None = None,
        recovery: str = "Correct the source file and preview again.",
        line: int | None = None,
        column: int | None = None,
        byte_offset: int | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.pointer = pointer
        self.recovery = recovery
        self.line = line
        self.column = column
        self.byte_offset = byte_offset
        super().__init__(message)

    def as_dict(self, filename: str) -> dict[str, Any]:
        result: dict[str, Any] = {
            "filename": filename,
            "code": self.code,
            "message": self.message,
            "recovery": self.recovery,
        }
        if self.pointer is not None:
            result["json_pointer"] = self.pointer
        if self.line is not None:
            result["line"] = self.line
        if self.column is not None:
            result["column"] = self.column
        if self.byte_offset is not None:
            result["byte_offset"] = self.byte_offset
        return result


@dataclass(frozen=True, slots=True)
class JsonRegistrationDiagnostic:
    filename: str
    code: str
    message: str
    recovery: str
    pointer: str | None = None
    line: int | None = None
    column: int | None = None
    byte_offset: int | None = None
    severity: str = "error"

    def as_dict(self) -> dict[str, Any]:
        return JsonRegistrationError(
            self.code,
            self.message,
            pointer=self.pointer,
            recovery=self.recovery,
            line=self.line,
            column=self.column,
            byte_offset=self.byte_offset,
        ).as_dict(self.filename) | {"severity": self.severity}


@dataclass(frozen=True, slots=True)
class JsonRegistrationFile:
    """One immutable input component supplied to preview."""

    filename: str
    content: bytes
    media_type: str = JSON_MEDIA_TYPE
    artifact_id: str | None = None
    artifact_sha256: str | None = None
    # Set only when this component was extracted from an uploaded canonical package.  It is
    # provenance metadata, not part of the component value/equality contract used by the package
    # builder and validator.
    package_path: str | None = field(default=None, compare=False, repr=False)

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.content).hexdigest()

    @property
    def size_bytes(self) -> int:
        return len(self.content)

    def __post_init__(self) -> None:
        if not self.filename or self.filename != unicodedata.normalize("NFC", self.filename):
            raise ValueError("JSON source filename must be non-empty NFC text")
        if self.media_type != JSON_MEDIA_TYPE:
            raise ValueError("JSON source component media type must be application/json")
        if not self.content:
            raise ValueError("JSON source component must not be empty")
        if self.artifact_sha256 is not None and self.artifact_sha256 != self.sha256:
            raise ValueError("source Artifact SHA-256 does not match supplied bytes")


@dataclass(frozen=True, slots=True)
class JsonRegistrationPreviewField:
    """One server-projected source field for the registration preview.

    The projection deliberately contains only displayable source values.  It is not a
    second client-side schema model: pointers are retained solely as stable evidence for
    a field/diagnostic association, while curve data is represented by a bounded summary.
    """

    section: str
    label: str
    pointer: str
    kind: str
    value: str | None = None
    unit: str | None = None
    summary: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "section": self.section,
            "label": self.label,
            "pointer": self.pointer,
            "kind": self.kind,
            "value": self.value,
            "unit": self.unit,
            "summary": self.summary,
        }


@dataclass(frozen=True, slots=True)
class JsonRegistrationFileResult:
    filename: str
    sha256: str
    size_bytes: int
    valid: bool
    warnings: tuple[JsonRegistrationDiagnostic, ...] = ()
    errors: tuple[JsonRegistrationDiagnostic, ...] = ()
    external_key: str | None = None
    record_id: str | None = None
    record_revision_id: str | None = None
    lifecycle: str | None = None
    fields: tuple[JsonRegistrationPreviewField, ...] = ()
    record_name: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "filename": self.filename,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
            "valid": self.valid,
            "warnings": [item.as_dict() for item in self.warnings],
            "errors": [item.as_dict() for item in self.errors],
            "external_key": self.external_key,
            "record_id": self.record_id,
            "record_revision_id": self.record_revision_id,
            "lifecycle": self.lifecycle,
            "fields": [item.as_dict() for item in self.fields],
            "record_name": self.record_name,
        }


@dataclass(frozen=True, slots=True)
class JsonRegistrationPreview:
    token: str
    expires_at: str
    package_sha256: str
    package_media_type: str
    files: tuple[JsonRegistrationFileResult, ...]
    valid: bool
    format_revision_id: str | None
    source_package_artifact_id: str | None = None
    detected_record_type: str | None = None
    format: Mapping[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "$schema": JSON_REGISTRATION_CONTRACT_ID,
            "contract_version": JSON_REGISTRATION_CONTRACT_VERSION,
            "preview_token": self.token,
            "expires_at": self.expires_at,
            "package": {
                "media_type": self.package_media_type,
                "sha256": self.package_sha256,
                "artifact_id": self.source_package_artifact_id,
            },
            "format_revision_id": self.format_revision_id,
            "detected_record_type": self.detected_record_type,
            "format": dict(self.format) if self.format is not None else None,
            "valid": self.valid,
            "files": [item.as_dict() for item in self.files],
        }


@dataclass(frozen=True, slots=True)
class JsonRegistrationReferencePin:
    file: str
    pointer: str
    identifier: str
    record_id: str
    revision_id: str
    content_hash: str


@dataclass(frozen=True, slots=True)
class JsonRegistrationPackage:
    archive: bytes
    manifest: bytes
    checksums: bytes
    paths: tuple[str, ...]
    sha256: str


@dataclass(frozen=True, slots=True)
class JsonField:
    """A schema property flattened to one source pointer."""

    pointer: str
    label: str
    section: str
    schema: Mapping[str, Any]
    curve: Mapping[str, Any] | None = None

    @property
    def source_unit(self) -> str | None:
        value = self.schema.get("x-unit")
        return value if isinstance(value, str) and value else None

    @property
    def quantity_semantics(self) -> str | None:
        value = self.schema.get("x-quantity")
        return value if isinstance(value, str) and value else None


class _DuplicateKey(ValueError):
    def __init__(self, key: str) -> None:
        self.key = key
        super().__init__(key)


def _reject_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateKey(key)
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON constant {value}")


def _location(raw: bytes, offset: int) -> tuple[int, int]:
    prefix = raw[: max(0, min(offset, len(raw)))]
    return prefix.count(b"\n") + 1, len(prefix.rsplit(b"\n", 1)[-1]) + 1


def _duplicate_location(raw: bytes, key: str) -> tuple[int, int, int] | None:
    """Best-effort location for the second spelling of a duplicate member."""

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return None
    seen = 0
    member = re.compile(r'("(?:\\.|[^"\\])*")\s*:')
    for match in member.finditer(text):
        try:
            candidate = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        if candidate != key:
            continue
        seen += 1
        if seen < 2:
            continue
        byte_offset = len(text[: match.start()].encode("utf-8"))
        line, column = _location(raw, byte_offset)
        return line, column, byte_offset
    return None


def _constant_location(raw: bytes, constant: str) -> tuple[int, int, int] | None:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return None
    pattern = rf"\b{re.escape(constant)}\b" if constant[0].isalnum() else re.escape(constant)
    match = re.search(pattern, text)
    if match is None:
        return None
    byte_offset = len(text[: match.start()].encode("utf-8"))
    line, column = _location(raw, byte_offset)
    return line, column, byte_offset


def parse_strict_json(raw: bytes, *, filename: str = "source.json") -> Any:
    """Decode strict UTF-8 JSON and reject duplicate keys and non-finite numbers."""

    try:
        raw.decode("utf-8")
    except UnicodeDecodeError as error:
        line, column = _location(raw, error.start)
        raise JsonRegistrationError(
            "invalid_utf8",
            f"{filename} is not valid UTF-8.",
            recovery="Encode the JSON source as UTF-8 without a BOM.",
            line=line,
            column=column,
            byte_offset=error.start,
        ) from error
    try:
        return json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_pairs,
            parse_constant=_reject_constant,
        )
    except _DuplicateKey as error:
        location = _duplicate_location(raw, error.key)
        raise JsonRegistrationError(
            "duplicate_json_key",
            f"Duplicate JSON member '{error.key}' was found.",
            recovery="Remove the duplicate member; precedence is forbidden.",
            line=location[0] if location else None,
            column=location[1] if location else None,
            byte_offset=location[2] if location else None,
        ) from error
    except json.JSONDecodeError as error:
        line, column = _location(raw, error.pos)
        raise JsonRegistrationError(
            "invalid_json",
            f"JSON lexical or syntax error: {error.msg}.",
            recovery="Correct the JSON syntax and preview the same file again.",
            line=line,
            column=column,
            byte_offset=error.pos,
        ) from error
    except ValueError as error:
        text = str(error)
        constant = next(
            (item for item in ("NaN", "Infinity", "-Infinity") if item in text),
            "NaN",
        )
        location = _constant_location(raw, constant)
        raise JsonRegistrationError(
            "non_finite_number",
            "NaN and Infinity are not valid JSON numbers.",
            recovery="Use finite JSON numbers or an explicit null where the schema permits it.",
            line=location[0] if location else None,
            column=location[1] if location else None,
            byte_offset=location[2] if location else None,
        ) from error
    except RecursionError as error:
        raise JsonRegistrationError(
            "json_nesting_limit",
            "JSON nesting exceeds the deployment parser limit.",
            recovery="Flatten the source document and preview again.",
        ) from error


def _escape_pointer(value: str) -> str:
    return value.replace("~", "~0").replace("/", "~1")


def json_pointer(document: Any, pointer: str) -> Any:
    """Resolve RFC 6901 JSON Pointer; the empty pointer addresses the document."""

    if pointer == "":
        return document
    if not pointer.startswith("/"):
        raise KeyError(pointer)
    value = document
    for token in pointer[1:].split("/"):
        token = token.replace("~1", "/").replace("~0", "~")
        if isinstance(value, Mapping):
            value = value[token]
        elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
            value = value[int(token)]
        else:
            raise KeyError(pointer)
    return value


def _schema_type_allows_null(schema: Mapping[str, Any]) -> bool:
    value = schema.get("type")
    return value == "null" or (isinstance(value, list) and "null" in value)


def _schema_type_allows_number(schema: Mapping[str, Any]) -> bool:
    value = schema.get("type")
    return (isinstance(value, str) and value in {"number", "integer"}) or (
        isinstance(value, list) and any(item in {"number", "integer"} for item in value)
    )


def flatten_schema_fields(schema: Mapping[str, Any]) -> tuple[JsonField, ...]:
    """Flatten the selected wrapper's object properties in source/layout order."""

    wrapper = schema.get("x-wrapper") or next(
        (key for key in schema.get("properties", {}) if isinstance(key, str)), None
    )
    if not isinstance(wrapper, str):
        return ()
    result: list[JsonField] = []

    def visit(node: Mapping[str, Any], prefix: str, section: str) -> None:
        properties = node.get("properties")
        if not isinstance(properties, Mapping):
            return
        for label, child in properties.items():
            if not isinstance(label, str) or not isinstance(child, Mapping):
                continue
            pointer = f"{prefix}/{_escape_pointer(label)}"
            child_section = section or label
            curve = child.get("x-curve")
            if isinstance(curve, Mapping):
                result.append(JsonField(pointer, label, child_section, child, curve))
            elif isinstance(child.get("properties"), Mapping):
                visit(child, pointer, child_section)
            else:
                result.append(JsonField(pointer, label, child_section, child))

    wrapper_node = schema.get("properties", {}).get(wrapper)
    if isinstance(wrapper_node, Mapping):
        visit(wrapper_node, f"/{_escape_pointer(wrapper)}", "")
    return tuple(result)


def _schema_error_pointer(error: Any) -> str:
    path = list(error.absolute_path)
    pointer = ""
    for item in path:
        pointer += "/" + _escape_pointer(str(item))
    return pointer or "/"


def _iter_numbers(value: Any, pointer: str = "") -> Sequence[tuple[str, float]]:
    found: list[tuple[str, float]] = []
    if isinstance(value, bool):
        return found
    if isinstance(value, (int, float, Decimal)):
        try:
            number = float(value)
        except (OverflowError, ValueError):
            number = math.inf
        found.append((pointer or "/", number))
    elif isinstance(value, Mapping):
        for key, child in value.items():
            found.extend(_iter_numbers(child, f"{pointer}/{_escape_pointer(str(key))}"))
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, child in enumerate(value):
            found.extend(_iter_numbers(child, f"{pointer}/{index}"))
    return found


def _curve_rows(document: Any, field: JsonField) -> tuple[tuple[float, float], ...]:
    """Resolve one source-v2 curve to finite, equal-length x/y pairs."""

    if field.curve is None:
        return ()
    x_pointer = field.curve.get("x_pointer")
    y_pointer = field.curve.get("y_pointer")
    if not isinstance(x_pointer, str) or not isinstance(y_pointer, str):
        raise JsonRegistrationError(
            "curve_definition_invalid",
            "Curve binding must declare x_pointer and y_pointer.",
            pointer=field.pointer,
            recovery="Use the installed curve binding without changing its pointers.",
        )
    parent_pointer = field.pointer.rsplit("/", 1)[0]

    def resolve_axis(pointer: str) -> Any:
        try:
            return json_pointer(document, pointer)
        except (KeyError, IndexError, TypeError, ValueError):
            # source-v2 curve pointers are commonly rooted inside the curve value itself
            # (``<curve>/Series 1/Value``), while some installed bindings carry a pointer
            # relative to the containing section.  Try both exact source-v2 forms after the
            # document-rooted pointer so we never infer or transform a curve axis.
            if pointer.startswith("/"):
                for prefix in (field.pointer, parent_pointer):
                    if prefix:
                        try:
                            return json_pointer(document, prefix + pointer)
                        except (KeyError, IndexError, TypeError, ValueError):
                            continue
            raise

    try:
        x_values = resolve_axis(x_pointer)
        y_values = resolve_axis(y_pointer)
    except (KeyError, IndexError, TypeError, ValueError) as error:
        raise JsonRegistrationError(
            "curve_reference_missing",
            "Curve x/y source pointer is missing.",
            pointer=field.pointer,
            recovery="Provide both declared curve arrays in the source JSON.",
        ) from error
    if not isinstance(x_values, Sequence) or isinstance(x_values, (str, bytes)):
        raise JsonRegistrationError(
            "curve_axis_not_array",
            "Curve x source pointer must resolve to an array.",
            pointer=x_pointer,
            recovery="Provide a JSON array for the declared curve axis.",
        )
    if not isinstance(y_values, Sequence) or isinstance(y_values, (str, bytes)):
        raise JsonRegistrationError(
            "curve_axis_not_array",
            "Curve y source pointer must resolve to an array.",
            pointer=y_pointer,
            recovery="Provide a JSON array for the declared curve axis.",
        )
    if not x_values or len(x_values) != len(y_values):
        raise JsonRegistrationError(
            "curve_length_mismatch",
            "Curve x/y arrays must be non-empty and have equal lengths.",
            pointer=field.pointer,
            recovery="Correct the curve arrays without resampling or interpolation.",
        )
    pairs: list[tuple[float, float]] = []
    for index, (x_value, y_value) in enumerate(zip(x_values, y_values, strict=True)):
        if isinstance(x_value, bool) or isinstance(y_value, bool):
            raise JsonRegistrationError(
                "curve_value_not_numeric",
                "Curve axes must contain only finite numbers.",
                pointer=f"{x_pointer}/{index}",
                recovery="Replace the curve point with a finite numeric value.",
            )
        try:
            x_number, y_number = float(x_value), float(y_value)
        except (TypeError, ValueError) as error:
            raise JsonRegistrationError(
                "curve_value_not_numeric",
                "Curve axes must contain only finite numbers.",
                pointer=f"{x_pointer}/{index}",
                recovery="Replace the curve point with a finite numeric value.",
            ) from error
        if not math.isfinite(x_number) or not math.isfinite(y_number):
            raise JsonRegistrationError(
                "curve_value_not_finite",
                "Curve axes must contain only finite numbers.",
                pointer=f"{x_pointer}/{index}",
                recovery="Replace NaN or Infinity with a finite source value.",
            )
        pairs.append((x_number, y_number))
    return tuple(pairs)


def curve_source_rows(
    document: Any, *, pointer: str, curve: Mapping[str, Any]
) -> tuple[tuple[float, float], ...]:
    """Return exact x/y rows for one installed curve binding.

    Preview, save, and source-aware CSV share this boundary so materializing a derived
    columnar Artifact cannot introduce sampling, interpolation, or hidden conversion.
    """

    return _curve_rows(document, JsonField(pointer, pointer.rsplit("/", 1)[-1], "", {}, curve))


def _unmapped_property_warnings(
    value: Any,
    schema: Mapping[str, Any],
    filename: str,
    pointer: str = "",
) -> list[JsonRegistrationDiagnostic]:
    warnings: list[JsonRegistrationDiagnostic] = []
    if isinstance(value, Mapping):
        properties = schema.get("properties")
        known = set(properties) if isinstance(properties, Mapping) else set()
        if schema.get("additionalProperties") is True:
            for key in value:
                if key not in known:
                    warnings.append(
                        JsonRegistrationDiagnostic(
                            filename,
                            "unmapped_extra_property",
                            "Unmapped property is retained only in immutable raw evidence.",
                            (
                                "Map the property in a new installed format revision if it "
                                "is business data."
                            ),
                            f"{pointer}/{_escape_pointer(str(key))}",
                            severity="warning",
                        )
                    )
        for key, child in value.items():
            child_schema = properties.get(key) if isinstance(properties, Mapping) else None
            if isinstance(child_schema, Mapping):
                warnings.extend(
                    _unmapped_property_warnings(
                        child,
                        child_schema,
                        filename,
                        f"{pointer}/{_escape_pointer(str(key))}",
                    )
                )
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        child_schema = schema.get("items")
        if isinstance(child_schema, Mapping):
            for index, child in enumerate(value):
                warnings.extend(
                    _unmapped_property_warnings(child, child_schema, filename, f"{pointer}/{index}")
                )
    return warnings


def validate_json_record(
    raw: bytes,
    schema: Mapping[str, Any],
    *,
    filename: str = "source.json",
    extra_warning: bool = True,
) -> tuple[Any, tuple[JsonRegistrationDiagnostic, ...], tuple[JsonRegistrationDiagnostic, ...]]:
    """Parse and validate one JSON record against an installed exact schema."""

    document = parse_strict_json(raw, filename=filename)
    if not isinstance(document, Mapping):
        raise JsonRegistrationError(
            "root_not_object",
            "A Record source must be a JSON object.",
            pointer="/",
            recovery="Wrap the exact installed Record wrapper in a JSON object.",
        )
    wrapper = schema.get("x-wrapper") or next(
        (key for key in schema.get("properties", {}) if isinstance(key, str)), None
    )
    if not isinstance(wrapper, str):
        raise JsonRegistrationError(
            "format_wrapper_unconfigured",
            "The installed format does not declare one exact wrapper.",
            recovery="Select an installed JSON format revision with an exact wrapper.",
        )
    if set(document) != {wrapper}:
        missing = wrapper not in document
        code = "wrapper_missing" if missing else "wrapper_mismatch"
        message = (
            f"Required JSON wrapper '{wrapper}' is missing."
            if missing
            else f"JSON must contain exactly the '{wrapper}' wrapper."
        )
        raise JsonRegistrationError(
            code,
            message,
            pointer=f"/{_escape_pointer(wrapper)}",
            recovery=(
                "Use exactly the selected installed format wrapper and no sibling root properties."
            ),
        )
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors: list[JsonRegistrationDiagnostic] = []
    for item in sorted(
        validator.iter_errors(document), key=lambda value: tuple(value.absolute_path)
    ):
        errors.append(
            JsonRegistrationDiagnostic(
                filename,
                "schema_validation_failed",
                item.message,
                "Correct the value at this exact JSON Pointer and preview again.",
                _schema_error_pointer(item),
            )
        )
    warnings: list[JsonRegistrationDiagnostic] = []
    fields = flatten_schema_fields(schema)
    for schema_field in fields:
        discrete_values = schema_field.schema.get("x-discrete")
        if isinstance(discrete_values, list):
            try:
                candidate = json_pointer(document, schema_field.pointer)
            except (KeyError, IndexError, TypeError, ValueError):
                candidate = None
            if candidate is not None and candidate not in discrete_values:
                allowed = ", ".join(str(value) for value in discrete_values)
                errors.append(
                    JsonRegistrationDiagnostic(
                        filename,
                        "discrete_value_invalid",
                        (
                            f"Value {candidate!r} is not one of the installed choices "
                            f"for '{schema_field.label}'."
                        ),
                        f"Use one of the installed choices: {allowed}.",
                        schema_field.pointer,
                    )
                )
        if schema_field.schema.get("x-business-key") is True:
            try:
                candidate = json_pointer(document, schema_field.pointer)
            except (KeyError, IndexError, TypeError, ValueError):
                candidate = None
            if not isinstance(candidate, str) or not candidate.strip():
                errors.append(
                    JsonRegistrationDiagnostic(
                        filename,
                        "business_key_required",
                        "Business key must be a non-empty string.",
                        "Enter a non-empty value at the exact business-key pointer.",
                        schema_field.pointer,
                    )
                )
        if schema_field.curve is not None:
            curve_missing = False
            try:
                try:
                    curve_value = json_pointer(document, schema_field.pointer)
                except (KeyError, IndexError, TypeError, ValueError):
                    curve_value = None
                    curve_missing = True
                if curve_missing:
                    # Optional source-v2 fields may be absent.  An explicit null is
                    # different: it would discard the declared curve and is rejected.
                    continue
                if curve_value is None:
                    raise JsonRegistrationError(
                        "curve_null_invalid",
                        (
                            "A source-v2 curve must contain its declared source arrays; "
                            "null is not valid."
                        ),
                        pointer=schema_field.pointer,
                        recovery="Provide the complete curve object and its declared x/y arrays.",
                    )
                _curve_rows(document, schema_field)
            except JsonRegistrationError as error:
                errors.append(
                    JsonRegistrationDiagnostic(
                        filename,
                        error.code,
                        str(error),
                        error.recovery,
                        error.pointer,
                        error.line,
                        error.column,
                        error.byte_offset,
                    )
                )
    for pointer, number in _iter_numbers(document):
        if not math.isfinite(number):
            errors.append(
                JsonRegistrationDiagnostic(
                    filename,
                    "non_finite_number",
                    "JSON number must be finite.",
                    "Replace NaN or Infinity with a finite number or permitted null.",
                    pointer,
                )
            )
    if extra_warning:
        warnings.extend(_unmapped_property_warnings(document, schema, filename))
    return document, tuple(warnings), tuple(errors)


def _valid_filename(filename: str) -> str:
    normalized = unicodedata.normalize("NFC", filename)
    if filename != normalized or not filename or filename != filename.strip():
        raise ValueError("package filenames must be non-empty NFC text")
    if "\\" in filename or ":" in filename or "\x00" in filename:
        raise ValueError("package filenames cannot contain backslash, colon, or NUL")
    if filename.startswith("/") or filename.endswith("/"):
        raise ValueError("package filenames must be relative files")
    if any(ord(char) < 0x20 or ord(char) == 0x7F for char in filename):
        raise ValueError("package filenames cannot contain control characters")
    parts = filename.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise ValueError("package filenames cannot contain empty, dot, or dotdot segments")
    if posixpath.normpath(filename) != filename:
        raise ValueError("package filename path is not normalized")
    return normalized


def _package_manifest(
    files: Sequence[JsonRegistrationFile],
    paths: Sequence[str],
    *,
    scope: Mapping[str, Any] | None = None,
    format_pins: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    value: dict[str, Any] = {
        "$schema": JSON_REGISTRATION_CONTRACT_ID,
        "contract": JSON_PACKAGE_CONTRACT_ID,
        "contract_version": JSON_PACKAGE_CONTRACT_VERSION,
        "media_type": JSON_PACKAGE_MEDIA_TYPE,
        "scope": dict(scope or {"classification": "internal"}),
        "components": [
            {
                "ordinal": index + 1,
                "original_name": item.filename,
                "path": paths[index],
                "media_type": item.media_type,
                "size_bytes": item.size_bytes,
                "sha256": item.sha256,
            }
            for index, item in enumerate(files)
        ],
    }
    if format_pins is not None:
        value["format"] = dict(format_pins)
    return value


def _canonical_manifest_bytes(value: Mapping[str, Any]) -> bytes:
    # RFC 8785's JSON serialization for this contract is restricted to NFC text,
    # finite numbers, and ordinary object/array members.  Python's compact encoder
    # gives the same UTF-8 bytes for those values and emits no BOM.
    return (
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
        + b"\n"
    )


def _deterministic_zip(entries: Sequence[tuple[str, bytes]]) -> bytes:
    """Write the v1 package without zipfile's flag-reset/data-descriptor defaults."""

    output = io.BytesIO()
    central: list[tuple[str, bytes, int, int, int]] = []
    for name, value in entries:
        encoded_name = name.encode("utf-8")
        offset = output.tell()
        crc = zlib.crc32(value) & 0xFFFFFFFF
        output.write(
            struct.pack(
                "<4s5H3I2H",
                b"PK\x03\x04",
                20,
                0x800,
                zipfile.ZIP_STORED,
                0,
                33,
                crc,
                len(value),
                len(value),
                len(encoded_name),
                0,
            )
        )
        output.write(encoded_name)
        output.write(value)
        central.append((name, encoded_name, crc, offset, len(value)))
    central_offset = output.tell()
    for name, encoded_name, crc, offset, size in central:
        del name
        output.write(
            struct.pack(
                "<4s6H3I5H2I",
                b"PK\x01\x02",
                (3 << 8) | 20,
                20,
                0x800,
                zipfile.ZIP_STORED,
                0,
                33,
                crc,
                size,
                size,
                len(encoded_name),
                0,
                0,
                0,
                0,
                0o100644 << 16,
                offset,
            )
        )
        output.write(encoded_name)
    central_size = output.tell() - central_offset
    output.write(
        struct.pack(
            "<4s4H2IH",
            b"PK\x05\x06",
            0,
            0,
            len(central),
            len(central),
            central_size,
            central_offset,
            0,
        )
    )
    return output.getvalue()


def build_registration_package(
    files: Sequence[JsonRegistrationFile],
    *,
    scope: Mapping[str, Any] | None = None,
    format_pins: Mapping[str, Any] | None = None,
) -> JsonRegistrationPackage:
    """Build the deterministic STORED package and its exact manifest/checksum bytes."""

    if not files:
        raise ValueError("registration package requires at least one JSON file")
    if len(files) > MAX_PACKAGE_ENTRIES:
        raise ValueError("registration package contains more than 100 entries")
    normalized_names = [_valid_filename(item.filename) for item in files]
    folded = [name.casefold() for name in normalized_names]
    if len(set(folded)) != len(folded):
        raise ValueError("registration package filenames collide under Unicode case-folding")
    if any(item.size_bytes > MAX_PACKAGE_ENTRY_BYTES for item in files):
        raise ValueError("registration package entry exceeds 250 MiB")
    if sum(item.size_bytes for item in files) > MAX_PACKAGE_UNCOMPRESSED_BYTES:
        raise ValueError("registration package exceeds 250 MiB uncompressed")
    ordered = sorted(
        files,
        key=lambda item: (
            unicodedata.normalize("NFC", item.filename).encode("utf-8"),
            item.sha256,
        ),
    )
    paths = tuple(
        f"records/{index:03d}-{item.sha256}.json" for index, item in enumerate(ordered, start=1)
    )
    manifest = _canonical_manifest_bytes(
        _package_manifest(ordered, paths, scope=scope, format_pins=format_pins)
    )
    checksum_lines = [
        f"{hashlib.sha256(manifest).hexdigest()}  manifest.json",
        *(f"{item.sha256}  {path}" for item, path in zip(ordered, paths, strict=True)),
    ]
    checksums = ("\n".join(checksum_lines) + "\n").encode("utf-8")
    archive_bytes = _deterministic_zip(
        (
            ("manifest.json", manifest),
            ("checksums.sha256", checksums),
            *((path, item.content) for item, path in zip(ordered, paths, strict=True)),
        )
    )
    if len(archive_bytes) > MAX_PACKAGE_ARCHIVE_BYTES:
        raise ValueError("registration package archive exceeds 64 MiB")
    return JsonRegistrationPackage(
        archive_bytes,
        manifest,
        checksums,
        ("manifest.json", "checksums.sha256", *paths),
        hashlib.sha256(archive_bytes).hexdigest(),
    )


def verify_registration_package(
    raw: bytes, *, expected_classification: str | None = None
) -> tuple[JsonRegistrationFile, ...]:
    """Verify package limits, metadata, order, checksums and duplicate names."""

    if len(raw) > MAX_PACKAGE_ARCHIVE_BYTES:
        raise ValueError("registration package archive exceeds 64 MiB")
    try:
        archive = zipfile.ZipFile(io.BytesIO(raw))
    except (OSError, zipfile.BadZipFile) as error:
        raise ValueError("registration package is not a readable ZIP archive") from error
    with archive:
        infos = archive.infolist()
        if len(infos) < 3 or len(infos) > MAX_PACKAGE_ENTRIES + 2:
            raise ValueError("registration package entry count is outside the allowed range")
        if len({info.filename for info in infos}) != len(infos):
            raise ValueError("registration package contains duplicate ZIP paths")
        if archive.comment or any(info.is_dir() or info.comment or info.extra for info in infos):
            raise ValueError("registration package cannot contain directory/comment/extra entries")
        if any(info.compress_type != zipfile.ZIP_STORED for info in infos):
            raise ValueError("registration package entries must be STORED")
        if any(info.flag_bits != 0x800 for info in infos):
            raise ValueError("registration package entries must set the UTF-8 flag")
        if any(info.create_version != 20 or info.extract_version != 20 for info in infos):
            raise ValueError("Zip64 package entries are forbidden")
        for info in infos:
            if info.create_system != 3 or info.external_attr != 0o100644 << 16:
                raise ValueError("registration package file mode/creator is not canonical")
            if info.date_time != (1980, 1, 1, 0, 0, 0):
                raise ValueError("registration package timestamps must be 1980-01-01")
        if infos[0].filename != "manifest.json" or infos[1].filename != "checksums.sha256":
            raise ValueError("manifest and checksums must be the first package entries")
        manifest = archive.read("manifest.json")
        checksums = archive.read("checksums.sha256")
        if manifest.decode("utf-8").encode("utf-8") != manifest or not manifest.endswith(b"\n"):
            raise ValueError("manifest must be UTF-8 with one trailing LF")
        try:
            manifest_document = parse_strict_json(manifest, filename="manifest.json")
        except (JsonRegistrationError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError("manifest is not strict UTF-8 JSON") from error
        if not isinstance(manifest_document, Mapping) or (
            _canonical_manifest_bytes(manifest_document) != manifest
        ):
            raise ValueError("manifest bytes are not canonical JCS UTF-8")
        if (
            manifest_document.get("$schema") != JSON_REGISTRATION_CONTRACT_ID
            or manifest_document.get("contract") != JSON_PACKAGE_CONTRACT_ID
            or manifest_document.get("contract_version") != JSON_PACKAGE_CONTRACT_VERSION
            or manifest_document.get("media_type") != JSON_PACKAGE_MEDIA_TYPE
        ):
            raise ValueError("registration package contract identity is invalid")
        scope = manifest_document.get("scope")
        if not isinstance(scope, Mapping) or scope.get("classification") not in {
            "internal",
            "confidential",
            "restricted",
            "export_controlled",
        }:
            raise ValueError("registration package scope classification is invalid")
        if (
            expected_classification is not None
            and scope.get("classification") != expected_classification
        ):
            raise ValueError(
                "registration package classification does not match "
                "the requested batch"
            )
        checksum_text = checksums.decode("utf-8")
        if checksum_text.encode("utf-8") != checksums or not checksum_text.endswith("\n"):
            raise ValueError("checksums.sha256 must be UTF-8 with one trailing LF")
        checksum_map: dict[str, str] = {}
        for line in checksum_text[:-1].split("\n"):
            parts = line.split("  ", 1)
            if (
                len(parts) != 2
                or len(parts[0]) != 64
                or parts[0].lower() != parts[0]
                or any(char not in "0123456789abcdef" for char in parts[0])
            ):
                raise ValueError("checksums.sha256 line is not canonical")
            if parts[1] in checksum_map:
                raise ValueError("checksums.sha256 contains a duplicate path")
            checksum_map[parts[1]] = parts[0]
        if checksum_map.get("manifest.json") != hashlib.sha256(manifest).hexdigest():
            raise ValueError("manifest checksum does not match package bytes")
        components = manifest_document.get("components")
        if not isinstance(components, list) or len(components) != len(infos) - 2:
            raise ValueError("manifest component count does not match package entries")
        expected_checksum_lines = [
            (hashlib.sha256(manifest).hexdigest(), "manifest.json"),
            *(
                (str(component.get("sha256")), str(component.get("path")))
                for component in components
                if isinstance(component, Mapping)
            ),
        ]
        actual_checksum_lines = [
            tuple(line.split("  ", 1))
            for line in checksum_text[:-1].split("\n")
        ]
        if actual_checksum_lines != expected_checksum_lines:
            raise ValueError("checksums.sha256 entries are not in canonical manifest order")
        files: list[JsonRegistrationFile] = []
        previous_sort_key: tuple[bytes, str] | None = None
        for ordinal, (component, info) in enumerate(
            zip(components, infos[2:], strict=True), start=1
        ):
            if not isinstance(component, Mapping):
                raise ValueError("manifest component is not an object")
            path = component.get("path")
            name = component.get("original_name")
            digest = component.get("sha256")
            if (
                component.get("ordinal") != ordinal
                or component.get("media_type") != JSON_MEDIA_TYPE
            ):
                raise ValueError("manifest component ordinal or media type is invalid")
            if not isinstance(path, str) or info.filename != path:
                raise ValueError("record package path/ordinal is not canonical")
            if not isinstance(name, str) or _valid_filename(name) != name:
                raise ValueError("manifest original filename is not canonical")
            name_bytes = name.encode("utf-8")
            sort_key = (name_bytes, digest if isinstance(digest, str) else "")
            if previous_sort_key is not None and sort_key < previous_sort_key:
                raise ValueError("record package entries are not ordered by original filename")
            previous_sort_key = sort_key
            value = archive.read(info)
            if sum(item.size_bytes for item in files) + len(value) > MAX_PACKAGE_UNCOMPRESSED_BYTES:
                raise ValueError("registration package exceeds 250 MiB uncompressed")
            observed = hashlib.sha256(value).hexdigest()
            if path != f"records/{ordinal:03d}-{observed}.json":
                raise ValueError("record package path is not derived from ordinal and SHA-256")
            if digest != observed or checksum_map.get(path) != observed:
                raise ValueError("record package component checksum does not match bytes")
            if component.get("size_bytes") != len(value) or info.file_size != len(value):
                raise ValueError("record package component size does not match bytes")
            files.append(JsonRegistrationFile(name, value, package_path=path))
        if tuple(item.filename for item in infos[2:]) != tuple(
            item.get("path") for item in components
        ):
            raise ValueError("record package entry order differs from manifest order")
        expected_checksum_paths = {"manifest.json", *(item.get("path") for item in components)}
        if set(checksum_map) != expected_checksum_paths:
            raise ValueError("checksums.sha256 contains an unexpected or missing path")
        folded = [item.filename.casefold() for item in files]
        if len(set(folded)) != len(folded):
            raise ValueError("manifest original filenames collide under Unicode case-folding")
        return tuple(files)


def _finite_json_number(value: Any) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        return ""
    decimal = Decimal(str(value))
    if not decimal.is_finite():
        raise ValueError("CSV value must be finite")
    if decimal == 0:
        return "0"
    text = format(decimal, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


def _csv_scalar(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float, Decimal)):
        return _finite_json_number(value)
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    )


def source_csv_bytes(
    document: Mapping[str, Any],
    schema: Mapping[str, Any],
    *,
    normalized_values: Mapping[str, tuple[str, str]] | None = None,
) -> bytes:
    """Render source-aware CSV in binding order, preserving curve source order."""

    normalized_values = normalized_values or {}
    output = io.StringIO(newline="")
    writer = csv.writer(output, delimiter=",", quotechar='"', lineterminator="\n")
    writer.writerow(SOURCE_CSV_HEADER)
    for schema_field in flatten_schema_fields(schema):
        try:
            value = json_pointer(document, schema_field.pointer)
        except (KeyError, IndexError, TypeError, ValueError):
            continue
        if value is None:
            writer.writerow(
                [
                    schema_field.section,
                    schema_field.pointer,
                    schema_field.label,
                    "",
                    schema_field.source_unit or "",
                    "",
                    "",
                    "source_null",
                    "",
                    "",
                    "",
                    "",
                    "",
                ]
            )
            continue
        if schema_field.curve is None:
            normalized_value, normalized_unit = normalized_values.get(
                schema_field.pointer, ("", "")
            )
            original_unit = schema_field.source_unit or ""
            if isinstance(value, Mapping) and "value" in value:
                original = value.get("value")
                original_unit = str(
                    value.get("unit") or value.get("original_unit_string") or original_unit
                )
                value_text = _csv_scalar(original)
            else:
                value_text = _csv_scalar(value)
            writer.writerow(
                [
                    schema_field.section,
                    schema_field.pointer,
                    schema_field.label,
                    value_text,
                    original_unit,
                    normalized_value,
                    normalized_unit,
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                ]
            )
            continue
        pairs = _curve_rows(document, schema_field)
        for index, (x_value, y_value) in enumerate(pairs):
            writer.writerow(
                [
                    schema_field.section,
                    schema_field.pointer,
                    schema_field.label,
                    "",
                    "",
                    "",
                    "",
                    "",
                    index,
                    _finite_json_number(x_value),
                    _finite_json_number(y_value),
                    str(schema_field.curve.get("x_unit") or ""),
                    str(schema_field.curve.get("y_unit") or ""),
                ]
            )
    return output.getvalue().encode("utf-8")


def exact_json_filename(external_key: str, revision_no: int) -> str:
    if not external_key or external_key != external_key.strip() or revision_no < 1:
        raise ValueError("exact JSON/CSV download identity is invalid")
    return f"{external_key}__r{revision_no}.json"


def exact_csv_filename(external_key: str, revision_no: int) -> str:
    if not external_key or external_key != external_key.strip() or revision_no < 1:
        raise ValueError("exact JSON/CSV download identity is invalid")
    return f"{external_key}__r{revision_no}.csv"


__all__ = [
    "JSON_MEDIA_TYPE",
    "JSON_PACKAGE_CONTRACT_ID",
    "JSON_PACKAGE_CONTRACT_VERSION",
    "JSON_REGISTRATION_CONTRACT_ID",
    "MAX_PACKAGE_ARCHIVE_BYTES",
    "MAX_PACKAGE_ENTRIES",
    "MAX_PACKAGE_ENTRY_BYTES",
    "MAX_PACKAGE_UNCOMPRESSED_BYTES",
    "MAX_SINGLE_JSON_BYTES",
    "SOURCE_CSV_HEADER",
    "JsonField",
    "JsonRegistrationDiagnostic",
    "JsonRegistrationError",
    "JsonRegistrationFile",
    "JsonRegistrationFileResult",
    "JsonRegistrationPackage",
    "JsonRegistrationPreview",
    "JsonRegistrationPreviewField",
    "JsonRegistrationReferencePin",
    "build_registration_package",
    "curve_source_rows",
    "exact_csv_filename",
    "exact_json_filename",
    "flatten_schema_fields",
    "json_pointer",
    "parse_strict_json",
    "source_csv_bytes",
    "validate_json_record",
    "verify_registration_package",
]

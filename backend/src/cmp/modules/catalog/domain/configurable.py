"""Framework-free configurable catalog schema value objects (ADR-0028, T-49)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Any
from uuid import UUID

_KEY = re.compile(r"^[a-z][a-z0-9_]{0,62}[a-z0-9]$|^[a-z]$")
_UNIT = re.compile(r"^[A-Za-z0-9%_.*/^()\[\]{}'+-]{1,64}$")


class ConfigurableCatalogError(RuntimeError):
    """Base error for configurable catalog schema operations."""


class ConfigurableCatalogConflict(ConfigurableCatalogError):
    """A schema command conflicts with an existing identity or revision."""


class ConfigurableCatalogNotFound(ConfigurableCatalogError):
    """A configurable schema identity or revision was not found."""


class AttributeDataType(StrEnum):
    NUMBER = "number"
    INTEGER = "integer"
    TEXT = "text"
    BOOLEAN = "boolean"
    DATE = "date"
    DISCRETE = "discrete"
    FILE = "file"
    CURVE = "curve"
    RECORD_REFERENCE = "record_reference"


def _trimmed(name: str, value: str, maximum: int) -> None:
    if not value or value != value.strip() or len(value) > maximum or "\x00" in value:
        raise ValueError(f"{name} must be trimmed and contain 1..{maximum} characters")


def _key(name: str, value: str) -> None:
    if _KEY.fullmatch(value) is None:
        raise ValueError(f"{name} must be a lower_snake_case key of 1..64 characters")


@dataclass(frozen=True, slots=True)
class CatalogTableContent:
    key: str
    name: str
    description: str | None = None

    def __post_init__(self) -> None:
        _key("table key", self.key)
        _trimmed("table name", self.name, 200)
        if self.description is not None:
            _trimmed("table description", self.description, 4000)


@dataclass(frozen=True, slots=True)
class AttributeDefinitionContent:
    table_id: UUID
    table_revision_id: UUID
    key: str
    name: str
    data_type: AttributeDataType
    required: bool = False
    quantity_semantics: str | None = None
    normalized_unit: str | None = None
    minimum_number: float | None = None
    maximum_number: float | None = None
    minimum_length: int | None = None
    maximum_length: int | None = None
    pattern: str | None = None
    allowed_values: tuple[str, ...] = ()
    reference_table_id: UUID | None = None
    help_text: str | None = None

    def __post_init__(self) -> None:
        if self.table_id.int == 0 or self.table_revision_id.int == 0:
            raise ValueError("Attribute Table identity and revision UUIDs must be non-zero")
        _key("attribute key", self.key)
        _trimmed("attribute name", self.name, 200)
        if self.quantity_semantics is not None:
            _trimmed("quantity_semantics", self.quantity_semantics, 255)
        if self.normalized_unit is not None and _UNIT.fullmatch(self.normalized_unit) is None:
            raise ValueError("normalized_unit must be a trimmed UCUM-compatible unit string")
        if self.minimum_number is not None and self.data_type is not AttributeDataType.NUMBER:
            raise ValueError("numeric bounds are valid only for number attributes")
        if self.maximum_number is not None and self.data_type is not AttributeDataType.NUMBER:
            raise ValueError("numeric bounds are valid only for number attributes")
        if (
            self.minimum_number is not None
            and self.maximum_number is not None
            and self.minimum_number > self.maximum_number
        ):
            raise ValueError("minimum_number cannot exceed maximum_number")
        if self.minimum_length is not None and self.minimum_length < 0:
            raise ValueError("minimum_length must be non-negative")
        if self.maximum_length is not None and self.maximum_length < 1:
            raise ValueError("maximum_length must be positive")
        if (
            self.minimum_length is not None
            and self.maximum_length is not None
            and self.minimum_length > self.maximum_length
        ):
            raise ValueError("minimum_length cannot exceed maximum_length")
        if self.data_type not in {AttributeDataType.TEXT, AttributeDataType.DISCRETE} and (
            self.minimum_length is not None or self.maximum_length is not None or self.pattern
        ):
            raise ValueError("text validation applies only to text/discrete attributes")
        if self.pattern is not None:
            _trimmed("pattern", self.pattern, 500)
            re.compile(self.pattern)
        if self.data_type is AttributeDataType.DISCRETE:
            if not self.allowed_values:
                raise ValueError("discrete attributes require allowed_values")
            if tuple(dict.fromkeys(self.allowed_values)) != self.allowed_values:
                raise ValueError("allowed_values must be unique and ordered")
            for value in self.allowed_values:
                _trimmed("allowed value", value, 255)
        elif self.allowed_values:
            raise ValueError("allowed_values are valid only for discrete attributes")
        if self.data_type is AttributeDataType.RECORD_REFERENCE:
            if self.reference_table_id is None or self.reference_table_id.int == 0:
                raise ValueError("record_reference attributes require reference_table_id")
        elif self.reference_table_id is not None:
            raise ValueError("reference_table_id is valid only for record_reference attributes")
        if self.help_text is not None:
            _trimmed("help_text", self.help_text, 2000)


@dataclass(frozen=True, slots=True)
class LayoutItem:
    attribute_definition_id: UUID
    attribute_definition_revision_id: UUID
    section: str
    ordinal: int

    def __post_init__(self) -> None:
        if self.attribute_definition_id.int == 0 or self.attribute_definition_revision_id.int == 0:
            raise ValueError("Layout item Attribute UUIDs must be non-zero")
        _trimmed("layout section", self.section, 100)
        if self.ordinal < 0:
            raise ValueError("layout item ordinal must be non-negative")


@dataclass(frozen=True, slots=True)
class LayoutContent:
    table_id: UUID
    table_revision_id: UUID
    name: str
    description: str | None = None
    items: tuple[LayoutItem, ...] = ()

    def __post_init__(self) -> None:
        if self.table_id.int == 0 or self.table_revision_id.int == 0:
            raise ValueError("Layout Table UUIDs must be non-zero")
        _trimmed("layout name", self.name, 200)
        if self.description is not None:
            _trimmed("layout description", self.description, 2000)
        ordinals = tuple(item.ordinal for item in self.items)
        if ordinals != tuple(range(len(self.items))):
            raise ValueError("layout item ordinals must be contiguous from zero")
        identities = tuple(item.attribute_definition_id for item in self.items)
        if len(set(identities)) != len(identities):
            raise ValueError("a layout cannot contain an Attribute more than once")


@dataclass(frozen=True, slots=True)
class SubsetContent:
    table_id: UUID
    table_revision_id: UUID
    name: str
    description: str | None = None
    filter_definition: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.table_id.int == 0 or self.table_revision_id.int == 0:
            raise ValueError("Subset Table UUIDs must be non-zero")
        _trimmed("subset name", self.name, 200)
        if self.description is not None:
            _trimmed("subset description", self.description, 2000)
        if self.filter_definition is not None and not isinstance(self.filter_definition, dict):
            raise ValueError("filter_definition must be a JSON object")


def table_canonical(content: CatalogTableContent) -> dict[str, Any]:
    return {"key": content.key, "name": content.name, "description": content.description}


def attribute_canonical(content: AttributeDefinitionContent) -> dict[str, Any]:
    return {
        "table_id": str(content.table_id),
        "table_revision_id": str(content.table_revision_id),
        "key": content.key,
        "name": content.name,
        "data_type": content.data_type.value,
        "required": content.required,
        "quantity_semantics": content.quantity_semantics,
        "normalized_unit": content.normalized_unit,
        "minimum_number": content.minimum_number,
        "maximum_number": content.maximum_number,
        "minimum_length": content.minimum_length,
        "maximum_length": content.maximum_length,
        "pattern": content.pattern,
        "allowed_values": list(content.allowed_values),
        "reference_table_id": (
            str(content.reference_table_id) if content.reference_table_id is not None else None
        ),
        "help_text": content.help_text,
    }


def layout_canonical(content: LayoutContent) -> dict[str, Any]:
    return {
        "table_id": str(content.table_id),
        "table_revision_id": str(content.table_revision_id),
        "name": content.name,
        "description": content.description,
        "items": [
            {
                "attribute_definition_id": str(item.attribute_definition_id),
                "attribute_definition_revision_id": str(item.attribute_definition_revision_id),
                "section": item.section,
                "ordinal": item.ordinal,
            }
            for item in content.items
        ],
    }


def subset_canonical(content: SubsetContent) -> dict[str, Any]:
    return {
        "table_id": str(content.table_id),
        "table_revision_id": str(content.table_revision_id),
        "name": content.name,
        "description": content.description,
        "filter_definition": content.filter_definition,
    }

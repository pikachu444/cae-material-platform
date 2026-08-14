"""Typed configurable Catalog records and folders (T-50)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from cmp.modules.catalog.domain.configurable import AttributeDataType

_DIGEST = re.compile(r"^[0-9a-f]{64}$")


def _text(name: str, value: str, maximum: int) -> None:
    if not value or value != value.strip() or len(value) > maximum or "\x00" in value:
        raise ValueError(f"{name} must be trimmed and contain 1..{maximum} characters")


@dataclass(frozen=True, slots=True)
class CatalogFolderContent:
    table_id: UUID
    table_revision_id: UUID
    name: str
    description: str | None = None
    parent_folder_id: UUID | None = None
    parent_folder_revision_id: UUID | None = None

    def __post_init__(self) -> None:
        if self.table_id.int == 0 or self.table_revision_id.int == 0:
            raise ValueError("Folder Table identity and revision must be non-zero")
        _text("folder name", self.name, 200)
        if self.description is not None:
            _text("folder description", self.description, 2000)
        if (self.parent_folder_id is None) != (self.parent_folder_revision_id is None):
            raise ValueError("parent folder identity and exact revision must be supplied together")
        if self.parent_folder_id is not None and self.parent_folder_id.int == 0:
            raise ValueError("parent folder identity must be non-zero")


@dataclass(frozen=True, slots=True)
class CatalogRecordValue:
    attribute_definition_id: UUID
    attribute_definition_revision_id: UUID
    data_type: AttributeDataType
    value: str | int | bool | date | None = None
    original_value: Decimal | None = None
    original_unit_string: str | None = None
    normalized_value: Decimal | None = None
    normalized_unit: str | None = None
    quantity_semantics: str | None = None
    artifact_id: UUID | None = None
    artifact_sha256: str | None = None
    target_record_id: UUID | None = None
    target_record_revision_id: UUID | None = None

    def __post_init__(self) -> None:
        if self.attribute_definition_id.int == 0 or self.attribute_definition_revision_id.int == 0:
            raise ValueError("record value Attribute identity and revision must be non-zero")
        scalar_types = {
            AttributeDataType.INTEGER,
            AttributeDataType.TEXT,
            AttributeDataType.BOOLEAN,
            AttributeDataType.DATE,
            AttributeDataType.DISCRETE,
        }
        if self.data_type in scalar_types:
            if self.value is None:
                raise ValueError(f"{self.data_type.value} record values require value")
            expected: type[object] = {
                AttributeDataType.INTEGER: int,
                AttributeDataType.TEXT: str,
                AttributeDataType.BOOLEAN: bool,
                AttributeDataType.DATE: date,
                AttributeDataType.DISCRETE: str,
            }[self.data_type]
            if type(self.value) is not expected:
                raise ValueError(f"{self.data_type.value} record value has the wrong scalar type")
            if isinstance(self.value, str):
                _text("record scalar value", self.value, 10000)
        elif self.value is not None:
            raise ValueError(f"{self.data_type.value} record values cannot carry scalar value")

        numeric = (
            self.original_value,
            self.original_unit_string,
            self.normalized_value,
            self.normalized_unit,
            self.quantity_semantics,
        )
        if self.data_type is AttributeDataType.NUMBER:
            if any(item is None for item in numeric):
                raise ValueError(
                    "number values require original and normalized value/unit metadata"
                )
            assert self.original_unit_string is not None
            assert self.normalized_unit is not None
            assert self.quantity_semantics is not None
            _text("original unit string", self.original_unit_string, 64)
            _text("normalized unit", self.normalized_unit, 64)
            _text("quantity semantics", self.quantity_semantics, 255)
            assert self.original_value is not None and self.normalized_value is not None
            if not self.original_value.is_finite() or not self.normalized_value.is_finite():
                raise ValueError("number record values must be finite")
        elif any(item is not None for item in numeric):
            raise ValueError("only number record values can carry unit and quantity metadata")

        artifact = (self.artifact_id, self.artifact_sha256)
        if self.data_type in {AttributeDataType.FILE, AttributeDataType.CURVE}:
            if any(item is None for item in artifact):
                raise ValueError("file and curve values require an exact artifact id and digest")
            assert self.artifact_id is not None and self.artifact_sha256 is not None
            if self.artifact_id.int == 0 or _DIGEST.fullmatch(self.artifact_sha256) is None:
                raise ValueError("artifact value requires a non-zero id and lowercase SHA-256")
        elif any(item is not None for item in artifact):
            raise ValueError("only file and curve record values can carry artifact references")

        reference = (self.target_record_id, self.target_record_revision_id)
        if self.data_type is AttributeDataType.RECORD_REFERENCE:
            if any(item is None for item in reference):
                raise ValueError("record-reference values require an exact target revision")
            assert self.target_record_id is not None and self.target_record_revision_id is not None
            if self.target_record_id.int == 0 or self.target_record_revision_id.int == 0:
                raise ValueError("record-reference target ids must be non-zero")
        elif any(item is not None for item in reference):
            raise ValueError("only record-reference values can carry a target record")


@dataclass(frozen=True, slots=True)
class CatalogRecordContent:
    table_id: UUID
    table_revision_id: UUID
    name: str
    external_key: str | None = None
    description: str | None = None
    folder_id: UUID | None = None
    folder_revision_id: UUID | None = None
    values: tuple[CatalogRecordValue, ...] = ()

    def __post_init__(self) -> None:
        if self.table_id.int == 0 or self.table_revision_id.int == 0:
            raise ValueError("Record Table identity and revision must be non-zero")
        _text("record name", self.name, 200)
        if self.external_key is not None:
            _text("record external key", self.external_key, 255)
        if self.description is not None:
            _text("record description", self.description, 4000)
        if (self.folder_id is None) != (self.folder_revision_id is None):
            raise ValueError("record folder identity and exact revision must be supplied together")
        attribute_ids = tuple(item.attribute_definition_id for item in self.values)
        if len(attribute_ids) != len(set(attribute_ids)):
            raise ValueError("a Record revision can contain at most one value per Attribute")


@dataclass(frozen=True, slots=True)
class DiscreteFilter:
    attribute_definition_id: UUID
    values: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.attribute_definition_id.int == 0 or not self.values:
            raise ValueError("discrete filter requires an Attribute and at least one value")
        for value in self.values:
            _text("discrete filter value", value, 255)


@dataclass(frozen=True, slots=True)
class NumberRangeFilter:
    attribute_definition_id: UUID
    minimum: Decimal | None = None
    maximum: Decimal | None = None

    def __post_init__(self) -> None:
        if self.attribute_definition_id.int == 0:
            raise ValueError("number filter Attribute must be non-zero")
        if self.minimum is None and self.maximum is None:
            raise ValueError("number filter requires a minimum or maximum")
        if self.minimum is not None and not self.minimum.is_finite():
            raise ValueError("number filter minimum must be finite")
        if self.maximum is not None and not self.maximum.is_finite():
            raise ValueError("number filter maximum must be finite")
        if self.minimum is not None and self.maximum is not None and self.minimum > self.maximum:
            raise ValueError("number filter minimum cannot exceed maximum")


@dataclass(frozen=True, slots=True)
class CatalogRecordQuery:
    table_id: UUID | None
    text: str | None = None
    folder_id: UUID | None = None
    discrete_filters: tuple[DiscreteFilter, ...] = ()
    number_filters: tuple[NumberRangeFilter, ...] = ()
    facet_attribute_ids: tuple[UUID, ...] = ()
    offset: int = 0
    limit: int = 50
    # These fields are optional so existing table-scoped callers keep their
    # original behaviour.  Materials uses the binding discriminator as its
    # governed projection instead of maintaining a second search source.
    domain_binding_kind: str | None = None
    include_descendants: bool = False
    sort_by: Literal["name", "external_key", "attribute"] = "name"
    sort_attribute_id: UUID | None = None
    sort_direction: Literal["ascending", "descending"] = "ascending"
    record_id: UUID | None = None
    published_only: bool = False
    # Materials workflow reads can require one exact governed binding in addition
    # to the Record publication marker.  Search/filter callers that only need a
    # binding kind leave these pins unset.
    domain_binding_object_id: UUID | None = None
    domain_binding_revision_id: UUID | None = None
    data_category: (
        Literal["technical_data", "test_data", "simulation_data", "solver_cards"] | None
    ) = None

    def __post_init__(self) -> None:
        if self.table_id is not None and self.table_id.int == 0:
            raise ValueError("record query Table must be non-zero")
        if (self.table_id is None) == (self.data_category is None):
            raise ValueError("record query requires exactly one Table or data category")
        if self.data_category is not None and (
            self.folder_id is not None
            or self.discrete_filters
            or self.number_filters
            or self.facet_attribute_ids
            or self.sort_by == "attribute"
        ):
            raise ValueError("data-category browse does not accept Table-specific controls")
        if self.text is not None:
            _text("record query text", self.text, 200)
        if self.offset < 0 or not 1 <= self.limit <= 100:
            raise ValueError("record query offset/limit is outside the bounded range")
        if len(self.discrete_filters) > 20 or len(self.number_filters) > 20:
            raise ValueError("record query supports at most 20 typed filters")
        if len(self.facet_attribute_ids) > 20:
            raise ValueError("record query supports at most 20 requested facets")
        if self.domain_binding_kind is not None:
            allowed_bindings = {
                "material",
                "material_state",
                "specimen",
                "test_run",
                "test_data",
                "processing_output",
                "material_model",
                "neutral_material",
                "solver_card",
                "neutral_solver_card",
                "release",
            }
            if self.domain_binding_kind not in allowed_bindings:
                raise ValueError("record query domain_binding_kind is not supported")
        if (self.domain_binding_object_id is None) != (self.domain_binding_revision_id is None):
            raise ValueError("domain binding object and revision pins must be paired")
        if self.domain_binding_object_id is not None:
            if self.domain_binding_kind is None:
                raise ValueError("domain binding pins require domain_binding_kind")
            if (
                self.domain_binding_object_id.int == 0
                or self.domain_binding_revision_id is None
                or self.domain_binding_revision_id.int == 0
            ):
                raise ValueError("domain binding pins must be non-zero UUIDs")
        if self.sort_by == "attribute" and self.sort_attribute_id is None:
            raise ValueError("attribute sort requires sort_attribute_id")
        if self.sort_by != "attribute" and self.sort_attribute_id is not None:
            raise ValueError("sort_attribute_id is valid only for attribute sorting")


def folder_canonical(content: CatalogFolderContent) -> dict[str, Any]:
    return {
        "table_id": str(content.table_id),
        "table_revision_id": str(content.table_revision_id),
        "name": content.name,
        "description": content.description,
        "parent_folder_id": str(content.parent_folder_id) if content.parent_folder_id else None,
        "parent_folder_revision_id": (
            str(content.parent_folder_revision_id) if content.parent_folder_revision_id else None
        ),
    }


def record_value_canonical(value: CatalogRecordValue) -> dict[str, Any]:
    scalar: object = value.value
    if isinstance(scalar, date):
        scalar = scalar.isoformat()
    return {
        "attribute_definition_id": str(value.attribute_definition_id),
        "attribute_definition_revision_id": str(value.attribute_definition_revision_id),
        "data_type": value.data_type.value,
        "value": scalar,
        "original_value": str(value.original_value) if value.original_value is not None else None,
        "original_unit_string": value.original_unit_string,
        "normalized_value": (
            str(value.normalized_value) if value.normalized_value is not None else None
        ),
        "normalized_unit": value.normalized_unit,
        "quantity_semantics": value.quantity_semantics,
        "artifact_id": str(value.artifact_id) if value.artifact_id else None,
        "artifact_sha256": value.artifact_sha256,
        "target_record_id": str(value.target_record_id) if value.target_record_id else None,
        "target_record_revision_id": (
            str(value.target_record_revision_id) if value.target_record_revision_id else None
        ),
    }


def record_canonical(content: CatalogRecordContent) -> dict[str, Any]:
    return {
        "table_id": str(content.table_id),
        "table_revision_id": str(content.table_revision_id),
        "name": content.name,
        "external_key": content.external_key,
        "description": content.description,
        "folder_id": str(content.folder_id) if content.folder_id else None,
        "folder_revision_id": (
            str(content.folder_revision_id) if content.folder_revision_id else None
        ),
        "values": [
            record_value_canonical(value)
            for value in sorted(content.values, key=lambda item: str(item.attribute_definition_id))
        ],
    }

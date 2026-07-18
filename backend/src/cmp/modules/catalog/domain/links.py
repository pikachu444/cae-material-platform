"""Typed exact-revision links for the configurable Material Information System (T-51)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Any
from uuid import UUID

_KEY = re.compile(r"^[a-z][a-z0-9_]{0,63}$")


class LinkCardinality(StrEnum):
    """Maximum number of current active links on one side of a Link Type."""

    ONE = "one"
    MANY = "many"


def _uuid(name: str, value: UUID) -> None:
    if value.int == 0:
        raise ValueError(f"{name} must be a non-zero UUID")


def _text(name: str, value: str, maximum: int) -> None:
    if not value or value != value.strip() or len(value) > maximum or "\x00" in value:
        raise ValueError(f"{name} must be trimmed and contain 1..{maximum} characters")


@dataclass(frozen=True, slots=True)
class LinkTypeContent:
    key: str
    name: str
    source_table_id: UUID
    source_table_revision_id: UUID
    target_table_id: UUID
    target_table_revision_id: UUID
    forward_label: str
    reverse_label: str
    source_cardinality: LinkCardinality = LinkCardinality.MANY
    target_cardinality: LinkCardinality = LinkCardinality.MANY
    description: str | None = None

    def __post_init__(self) -> None:
        if _KEY.fullmatch(self.key) is None:
            raise ValueError("Link Type key must be lower_snake_case and contain 1..64 characters")
        _text("Link Type name", self.name, 200)
        _uuid("source Table identity", self.source_table_id)
        _uuid("source Table revision", self.source_table_revision_id)
        _uuid("target Table identity", self.target_table_id)
        _uuid("target Table revision", self.target_table_revision_id)
        _text("forward label", self.forward_label, 200)
        _text("reverse label", self.reverse_label, 200)
        if self.description is not None:
            _text("Link Type description", self.description, 2000)


@dataclass(frozen=True, slots=True)
class RecordLinkContent:
    link_type_id: UUID
    link_type_revision_id: UUID
    source_record_id: UUID
    source_record_revision_id: UUID
    target_record_id: UUID
    target_record_revision_id: UUID
    active: bool = True
    note: str | None = None

    def __post_init__(self) -> None:
        _uuid("Link Type identity", self.link_type_id)
        _uuid("Link Type revision", self.link_type_revision_id)
        _uuid("source Record identity", self.source_record_id)
        _uuid("source Record revision", self.source_record_revision_id)
        _uuid("target Record identity", self.target_record_id)
        _uuid("target Record revision", self.target_record_revision_id)
        if (
            self.source_record_id == self.target_record_id
            and self.source_record_revision_id == self.target_record_revision_id
        ):
            raise ValueError("a Record Link cannot point an exact revision to itself")
        if self.note is not None:
            _text("Record Link note", self.note, 2000)


def link_type_canonical(content: LinkTypeContent) -> dict[str, Any]:
    return {
        "key": content.key,
        "name": content.name,
        "source_table_id": str(content.source_table_id),
        "source_table_revision_id": str(content.source_table_revision_id),
        "target_table_id": str(content.target_table_id),
        "target_table_revision_id": str(content.target_table_revision_id),
        "forward_label": content.forward_label,
        "reverse_label": content.reverse_label,
        "source_cardinality": content.source_cardinality.value,
        "target_cardinality": content.target_cardinality.value,
        "description": content.description,
    }


def record_link_canonical(content: RecordLinkContent) -> dict[str, Any]:
    return {
        "link_type_id": str(content.link_type_id),
        "link_type_revision_id": str(content.link_type_revision_id),
        "source_record_id": str(content.source_record_id),
        "source_record_revision_id": str(content.source_record_revision_id),
        "target_record_id": str(content.target_record_id),
        "target_record_revision_id": str(content.target_record_revision_id),
        "active": content.active,
        "note": content.note,
    }

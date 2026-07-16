"""Exact Lot revision sources for immutable Specimen revisions."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from cmp.modules.testing.domain.reference_tensile import InvalidTestingData


@dataclass(frozen=True, slots=True)
class SpecimenSourceLot:
    material_lot_id: UUID
    material_lot_revision_id: UUID
    note: str | None = None

    def __post_init__(self) -> None:
        if self.material_lot_id.int == 0 or self.material_lot_revision_id.int == 0:
            raise InvalidTestingData("Specimen source Lot references must be non-zero")
        if self.note is not None and (
            not self.note
            or self.note != self.note.strip()
            or len(self.note) > 1000
            or "\x00" in self.note
        ):
            raise InvalidTestingData("source Lot note must be trimmed and at most 1000 characters")


@dataclass(frozen=True, slots=True)
class SpecimenSourceContent:
    specimen_id: UUID
    specimen_revision_id: UUID
    sources: tuple[SpecimenSourceLot, ...]
    note: str | None = None

    def __post_init__(self) -> None:
        if self.specimen_id.int == 0 or self.specimen_revision_id.int == 0:
            raise InvalidTestingData("Specimen source references must be non-zero")
        if not self.sources:
            raise InvalidTestingData("Specimen source genealogy requires at least one Lot")
        refs = tuple((item.material_lot_id, item.material_lot_revision_id) for item in self.sources)
        if len(set(refs)) != len(refs):
            raise InvalidTestingData("a source Lot revision may appear only once")
        if self.note is not None and (
            not self.note
            or self.note != self.note.strip()
            or len(self.note) > 2000
            or "\x00" in self.note
        ):
            raise InvalidTestingData("genealogy note must be trimmed and at most 2000 characters")


def specimen_source_canonical(value: SpecimenSourceContent) -> dict[str, object]:
    return {
        "specimen_id": str(value.specimen_id),
        "specimen_revision_id": str(value.specimen_revision_id),
        "sources": [
            {
                "material_lot_id": str(item.material_lot_id),
                "material_lot_revision_id": str(item.material_lot_revision_id),
                "note": item.note,
            }
            for item in value.sources
        ],
        "note": value.note,
    }

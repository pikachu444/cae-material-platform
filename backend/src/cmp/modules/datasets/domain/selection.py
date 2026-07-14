"""Explicit, immutable one-curve Dataset Selections for reference downstream workflows.

The production Selection aggregate will ultimately support ordered multi-curve membership.  The
first vertical slices deliberately pin exactly one normalized or processed reference tensile
Dataset revision instead of hiding a future general membership model in JSON or an EAV table.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from cmp.modules.datasets.domain.reference_tensile import InvalidDatasetData

REFERENCE_DATASET_SELECTION_SCHEMA_VERSION = "1.0.0"


def _uuid(name: str, value: UUID) -> None:
    if value.int == 0:
        raise InvalidDatasetData(f"{name} must be non-zero")


def _text(name: str, value: str, maximum: int) -> None:
    if not value or value != value.strip() or len(value) > maximum or "\x00" in value:
        raise InvalidDatasetData(f"{name} must be trimmed and contain 1..{maximum} characters")


@dataclass(frozen=True, slots=True)
class ReferenceDatasetSelectionContent:
    """One concrete normalized/processed Dataset revision, never a moving head alias."""

    selection_label: str
    dataset_id: UUID
    dataset_revision_id: UUID

    def __post_init__(self) -> None:
        _text("selection_label", self.selection_label, 160)
        _uuid("dataset_id", self.dataset_id)
        _uuid("dataset_revision_id", self.dataset_revision_id)


def reference_dataset_selection_canonical(
    value: ReferenceDatasetSelectionContent,
) -> dict[str, object]:
    """Canonical typed content for the Selection revision hash."""

    return {
        "selection_kind": "reference_curve_dataset_revision",
        "selection_label": value.selection_label,
        "member_count": 1,
        "members": [
            {
                "ordinal": 0,
                "dataset_id": str(value.dataset_id),
                "dataset_revision_id": str(value.dataset_revision_id),
            }
        ],
    }


def validate_selection_label(value: str) -> str:
    _text("selection_label", value, 160)
    return value

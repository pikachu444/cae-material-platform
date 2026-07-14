"""Explicit, immutable Dataset Selections for reference downstream workflows.

The production Selection aggregate will ultimately support ordered multi-curve membership.  The
first vertical slices deliberately pin exactly one normalized or processed reference tensile
Dataset revision instead of hiding a future general membership model in JSON or an EAV table.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from cmp.modules.datasets.domain.reference_tensile import InvalidDatasetData

REFERENCE_DATASET_SELECTION_SCHEMA_VERSION = "1.0.0"
REFERENCE_TENSILE_REPLICATE_SELECTION_SCHEMA_VERSION = "1.0.0"
REFERENCE_TENSILE_REPLICATE_SELECTION_KIND = "reference_tensile_replicate_set"
MAX_REFERENCE_TENSILE_REPLICATE_MEMBERS = 50


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


@dataclass(frozen=True, slots=True)
class ReferenceTensileReplicateSelectionMember:
    """One ordered, concrete Dataset/Test Run revision in a replicate set."""

    ordinal: int
    dataset_id: UUID
    dataset_revision_id: UUID
    test_run_id: UUID
    test_run_revision_id: UUID

    def __post_init__(self) -> None:
        if self.ordinal < 0 or self.ordinal >= MAX_REFERENCE_TENSILE_REPLICATE_MEMBERS:
            raise InvalidDatasetData("replicate member ordinal is outside the supported range")
        for name, value in (
            ("dataset_id", self.dataset_id),
            ("dataset_revision_id", self.dataset_revision_id),
            ("test_run_id", self.test_run_id),
            ("test_run_revision_id", self.test_run_revision_id),
        ):
            _uuid(name, value)


@dataclass(frozen=True, slots=True)
class ReferenceTensileReplicateSelectionContent:
    """An ordered set of independent tensile Dataset revisions from distinct Test Runs."""

    selection_label: str
    members: tuple[ReferenceTensileReplicateSelectionMember, ...]

    def __post_init__(self) -> None:
        _text("selection_label", self.selection_label, 160)
        if not 2 <= len(self.members) <= MAX_REFERENCE_TENSILE_REPLICATE_MEMBERS:
            raise InvalidDatasetData("replicate Selection requires between 2 and 50 members")
        if tuple(member.ordinal for member in self.members) != tuple(range(len(self.members))):
            raise InvalidDatasetData("replicate Selection member ordinals must be contiguous")
        dataset_revisions = {member.dataset_revision_id for member in self.members}
        test_run_revisions = {member.test_run_revision_id for member in self.members}
        if len(dataset_revisions) != len(self.members):
            raise InvalidDatasetData("replicate Selection Dataset revisions must be distinct")
        if len(test_run_revisions) != len(self.members):
            raise InvalidDatasetData("replicate Selection Test Run revisions must be distinct")


def reference_tensile_replicate_selection_canonical(
    value: ReferenceTensileReplicateSelectionContent,
) -> dict[str, object]:
    """Canonical ordered membership used by the immutable revision digest."""

    return {
        "selection_kind": REFERENCE_TENSILE_REPLICATE_SELECTION_KIND,
        "selection_label": value.selection_label,
        "member_count": len(value.members),
        "members": [
            {
                "ordinal": member.ordinal,
                "dataset_id": str(member.dataset_id),
                "dataset_revision_id": str(member.dataset_revision_id),
                "test_run_id": str(member.test_run_id),
                "test_run_revision_id": str(member.test_run_revision_id),
            }
            for member in value.members
        ],
    }

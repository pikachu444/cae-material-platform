"""Typed Dataset Selection and derived representations for viscoelastic master curves."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from cmp.shared.domain.revisions import content_sha256

VISCOELASTIC_SELECTION_SCHEMA_ID = "urn:cmp:datasets:viscoelastic-selection:1.0.0"
VISCOELASTIC_DERIVED_DATASET_SCHEMA_ID = (
    "urn:cmp:datasets:viscoelastic-derived-dataset:1.0.0"
)
VISCOELASTIC_DATASET_SCHEMA_VERSION = "1.0.0"
MAX_VISCOELASTIC_SELECTION_MEMBERS = 50


class InvalidViscoelasticDataset(ValueError):
    """A Selection or derived Dataset violates its explicit contract."""


class ViscoelasticDerivedRepresentation(StrEnum):
    ALIGNED = "aligned"
    STATISTICS = "statistics"
    MASTER_CURVE = "master_curve"


def _uuid(name: str, value: UUID) -> None:
    if value.int == 0:
        raise InvalidViscoelasticDataset(f"{name} must be non-zero")


def _text(name: str, value: str, maximum: int) -> None:
    if not value or value != value.strip() or len(value) > maximum or "\x00" in value:
        raise InvalidViscoelasticDataset(
            f"{name} must be trimmed and contain 1..{maximum} characters"
        )


@dataclass(frozen=True, slots=True)
class ViscoelasticSelectionMember:
    ordinal: int
    dataset_id: UUID
    dataset_revision_id: UUID
    test_run_id: UUID
    test_run_revision_id: UUID
    temperature_k: float
    outlier_status: str = "not_assessed"

    def __post_init__(self) -> None:
        if not 0 <= self.ordinal < MAX_VISCOELASTIC_SELECTION_MEMBERS:
            raise InvalidViscoelasticDataset("Selection member ordinal is outside 0..49")
        for name, value in (
            ("dataset_id", self.dataset_id),
            ("dataset_revision_id", self.dataset_revision_id),
            ("test_run_id", self.test_run_id),
            ("test_run_revision_id", self.test_run_revision_id),
        ):
            _uuid(name, value)
        if not math.isfinite(self.temperature_k) or self.temperature_k <= 0:
            raise InvalidViscoelasticDataset("temperature_k must be positive Kelvin")
        if self.outlier_status != "not_assessed":
            raise InvalidViscoelasticDataset(
                "viscoelastic outlier assessment is not yet implemented"
            )


@dataclass(frozen=True, slots=True)
class ViscoelasticSelectionContent:
    selection_label: str
    material_state_id: UUID
    material_state_revision_id: UUID
    members: tuple[ViscoelasticSelectionMember, ...]

    def __post_init__(self) -> None:
        _text("selection_label", self.selection_label, 160)
        _uuid("material_state_id", self.material_state_id)
        _uuid("material_state_revision_id", self.material_state_revision_id)
        if not 2 <= len(self.members) <= MAX_VISCOELASTIC_SELECTION_MEMBERS:
            raise InvalidViscoelasticDataset("Selection requires between 2 and 50 curves")
        if tuple(item.ordinal for item in self.members) != tuple(range(len(self.members))):
            raise InvalidViscoelasticDataset("Selection member ordinals must be contiguous")
        if len({item.dataset_revision_id for item in self.members}) != len(self.members):
            raise InvalidViscoelasticDataset("Dataset revisions must be distinct")
        if len({item.test_run_revision_id for item in self.members}) != len(self.members):
            raise InvalidViscoelasticDataset("Test Run revisions must be distinct")
        if len({item.temperature_k for item in self.members}) < 2:
            raise InvalidViscoelasticDataset("Selection requires at least two temperatures")

    def canonical(self) -> dict[str, object]:
        return {
            "selection_kind": "viscoelastic_temperature_replicates",
            "selection_label": self.selection_label,
            "material_state_id": str(self.material_state_id),
            "material_state_revision_id": str(self.material_state_revision_id),
            "member_count": len(self.members),
            "members": [
                {
                    "ordinal": item.ordinal,
                    "dataset_id": str(item.dataset_id),
                    "dataset_revision_id": str(item.dataset_revision_id),
                    "test_run_id": str(item.test_run_id),
                    "test_run_revision_id": str(item.test_run_revision_id),
                    "temperature_k": item.temperature_k,
                    "outlier_status": item.outlier_status,
                }
                for item in self.members
            ],
        }
    @property
    def digest(self) -> str:
        return content_sha256(self.canonical())


@dataclass(frozen=True, slots=True)
class ViscoelasticDerivedDatasetContent:
    material_state_id: UUID
    material_state_revision_id: UUID
    selection_id: UUID
    selection_revision_id: UUID
    processing_plan_id: UUID
    processing_plan_revision_id: UUID
    processing_run_id: UUID
    representation: ViscoelasticDerivedRepresentation
    data_artifact_id: UUID
    data_sha256: str
    row_count: int
    source_curve_count: int
    reference_temperature_k: float
    schema_ref: str

    def __post_init__(self) -> None:
        for name, value in (
            ("material_state_id", self.material_state_id),
            ("material_state_revision_id", self.material_state_revision_id),
            ("selection_id", self.selection_id),
            ("selection_revision_id", self.selection_revision_id),
            ("processing_plan_id", self.processing_plan_id),
            ("processing_plan_revision_id", self.processing_plan_revision_id),
            ("processing_run_id", self.processing_run_id),
            ("data_artifact_id", self.data_artifact_id),
        ):
            _uuid(name, value)
        if not re.fullmatch(r"[0-9a-f]{64}", self.data_sha256):
            raise InvalidViscoelasticDataset("data_sha256 must be lowercase SHA-256")
        if not 1 <= self.row_count <= 1_000_000:
            raise InvalidViscoelasticDataset("row_count must be within 1..1000000")
        if not 2 <= self.source_curve_count <= MAX_VISCOELASTIC_SELECTION_MEMBERS:
            raise InvalidViscoelasticDataset("source_curve_count must be within 2..50")
        if not math.isfinite(self.reference_temperature_k) or self.reference_temperature_k <= 0:
            raise InvalidViscoelasticDataset("reference_temperature_k must be positive Kelvin")
        _text("schema_ref", self.schema_ref, 500)

    def canonical(self) -> dict[str, object]:
        return {
            "material_state_id": str(self.material_state_id),
            "material_state_revision_id": str(self.material_state_revision_id),
            "selection_id": str(self.selection_id),
            "selection_revision_id": str(self.selection_revision_id),
            "processing_plan_id": str(self.processing_plan_id),
            "processing_plan_revision_id": str(self.processing_plan_revision_id),
            "processing_run_id": str(self.processing_run_id),
            "representation": self.representation.value,
            "data_artifact_id": str(self.data_artifact_id),
            "data_sha256": self.data_sha256,
            "row_count": self.row_count,
            "source_curve_count": self.source_curve_count,
            "reference_temperature_k": self.reference_temperature_k,
            "schema_ref": self.schema_ref,
        }

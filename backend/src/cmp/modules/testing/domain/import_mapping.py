"""Typed, non-production detection and human-approved mapping values for T-11.

This module deliberately knows only enough about a reference CSV header to make the human
confirmation boundary explicit.  It is not a production parser and it never turns a header name
or unit-looking suffix into a committed quantity decision by itself.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from cmp.modules.testing.domain.reference_tensile import InvalidTestingData
from cmp.shared.domain.revisions import content_sha256

REFERENCE_SYNTHETIC_CSV_HEADER_IMPORTER_ID = (
    "urn:cmp:testing:synthetic-csv-header-importer:1.0.0"
)
REFERENCE_SYNTHETIC_CSV_HEADER_IMPORTER_VERSION = "1.0.0"
REFERENCE_IMPORT_MAPPING_SCHEMA_VERSION = "1.0.0"
REFERENCE_IMPORT_MAPPING_SCHEMA_ID = "urn:cmp:testing:reference-import-mapping:1.0.0"
MAX_DETECTED_COLUMNS = 512

_STRAIN_UNITS = frozenset(("1", "%"))
_STRESS_UNITS = frozenset(("Pa", "kPa", "MPa", "GPa"))


class ImportDetectionStatus(StrEnum):
    """Detection never crosses the user-confirmation boundary by itself."""

    NEEDS_INPUT = "needs_input"


class MappingSuggestionConfidence(StrEnum):
    NONE = "none"
    LOW = "low"


def _uuid(name: str, value: UUID) -> None:
    if value.int == 0:
        raise InvalidTestingData(f"{name} must be non-zero")


def _text(name: str, value: str, maximum: int) -> None:
    if not value or value != value.strip() or len(value) > maximum or "\x00" in value:
        raise InvalidTestingData(f"{name} must be trimmed and contain 1..{maximum} characters")


def _optional_text(name: str, value: str | None, maximum: int) -> None:
    if value is not None:
        _text(name, value, maximum)


@dataclass(frozen=True, slots=True)
class SyntheticCsvDetectionReport:
    """Immutable evidence from a verified Raw Artifact before mapping approval."""

    raw_asset_id: UUID
    raw_artifact_id: UUID
    raw_sha256: str
    header_columns: tuple[str, ...]
    status: ImportDetectionStatus
    suggested_strain_column: str | None
    suggested_strain_unit: str | None
    strain_confidence: MappingSuggestionConfidence
    suggested_stress_column: str | None
    suggested_stress_unit: str | None
    stress_confidence: MappingSuggestionConfidence
    importer_id: str = REFERENCE_SYNTHETIC_CSV_HEADER_IMPORTER_ID
    importer_version: str = REFERENCE_SYNTHETIC_CSV_HEADER_IMPORTER_VERSION
    reference_only: bool = True

    def __post_init__(self) -> None:
        _uuid("raw_asset_id", self.raw_asset_id)
        _uuid("raw_artifact_id", self.raw_artifact_id)
        if len(self.raw_sha256) != 64 or any(
            character not in "0123456789abcdef" for character in self.raw_sha256
        ):
            raise InvalidTestingData("raw_sha256 must be a lowercase SHA-256 digest")
        if not 1 <= len(self.header_columns) <= MAX_DETECTED_COLUMNS:
            raise InvalidTestingData("header_columns must contain 1..512 names")
        if len(set(self.header_columns)) != len(self.header_columns):
            raise InvalidTestingData("CSV header columns must be unique after normalization")
        for name in self.header_columns:
            _text("CSV header column", name, 255)
        if self.status is not ImportDetectionStatus.NEEDS_INPUT:
            raise InvalidTestingData("synthetic detection must remain needs_input")
        if self.importer_id != REFERENCE_SYNTHETIC_CSV_HEADER_IMPORTER_ID:
            raise InvalidTestingData("synthetic importer identity is fixed")
        if self.importer_version != REFERENCE_SYNTHETIC_CSV_HEADER_IMPORTER_VERSION:
            raise InvalidTestingData("synthetic importer version is fixed")
        if not self.reference_only:
            raise InvalidTestingData("synthetic detection must remain non-production")
        self._validate_suggestion(
            "strain",
            self.suggested_strain_column,
            self.suggested_strain_unit,
            self.strain_confidence,
            _STRAIN_UNITS,
        )
        self._validate_suggestion(
            "stress",
            self.suggested_stress_column,
            self.suggested_stress_unit,
            self.stress_confidence,
            _STRESS_UNITS,
        )

    def _validate_suggestion(
        self,
        name: str,
        column: str | None,
        unit: str | None,
        confidence: MappingSuggestionConfidence,
        allowed_units: frozenset[str],
    ) -> None:
        _optional_text(f"suggested_{name}_column", column, 255)
        if confidence is MappingSuggestionConfidence.NONE:
            if column is not None or unit is not None:
                raise InvalidTestingData(
                    f"{name} suggestion values require a non-none confidence"
                )
            return
        if confidence is not MappingSuggestionConfidence.LOW:
            raise InvalidTestingData("synthetic suggestions may not exceed low confidence")
        if column is None or unit is None or column not in self.header_columns:
            raise InvalidTestingData(f"low-confidence {name} suggestion is incomplete")
        if unit not in allowed_units:
            raise InvalidTestingData(f"{name} suggestion unit is unsupported")

    @property
    def digest(self) -> str:
        return content_sha256(synthetic_csv_detection_canonical(self))


@dataclass(frozen=True, slots=True)
class ReferenceImportMappingContent:
    """One human-approved explicit reference mapping revision.

    The mapping belongs to a stable identity.  The identity's label, Raw Artifact, and synthetic
    detection profile are immutable; columns/units may only change through an appended revision.
    """

    mapping_label: str
    detection_report_id: UUID
    raw_asset_id: UUID
    raw_artifact_id: UUID
    strain_column: str
    stress_column: str
    strain_unit: str
    stress_unit: str
    importer_id: str = REFERENCE_SYNTHETIC_CSV_HEADER_IMPORTER_ID
    importer_version: str = REFERENCE_SYNTHETIC_CSV_HEADER_IMPORTER_VERSION
    approval_kind: str = "human_confirmed"
    reference_only: bool = True

    def __post_init__(self) -> None:
        _text("mapping_label", self.mapping_label, 160)
        for name, value in (
            ("detection_report_id", self.detection_report_id),
            ("raw_asset_id", self.raw_asset_id),
            ("raw_artifact_id", self.raw_artifact_id),
        ):
            _uuid(name, value)
        _text("strain_column", self.strain_column, 255)
        _text("stress_column", self.stress_column, 255)
        if self.strain_column == self.stress_column:
            raise InvalidTestingData("strain and stress mapping columns must be distinct")
        if self.strain_unit not in _STRAIN_UNITS:
            raise InvalidTestingData("strain_unit must be one of 1 or %")
        if self.stress_unit not in _STRESS_UNITS:
            raise InvalidTestingData("stress_unit must be Pa, kPa, MPa, or GPa")
        if self.importer_id != REFERENCE_SYNTHETIC_CSV_HEADER_IMPORTER_ID:
            raise InvalidTestingData("mapping importer identity is fixed")
        if self.importer_version != REFERENCE_SYNTHETIC_CSV_HEADER_IMPORTER_VERSION:
            raise InvalidTestingData("mapping importer version is fixed")
        if self.approval_kind != "human_confirmed":
            raise InvalidTestingData("mapping approval_kind must be human_confirmed")
        if not self.reference_only:
            raise InvalidTestingData("reference mapping must remain non-production")

    @property
    def dataset_mapping_digest(self) -> str:
        """Match the T-12 Dataset mapping digest without making Dataset a private dependency."""

        return content_sha256(
            {
                "strain_column": self.strain_column,
                "stress_column": self.stress_column,
                "strain_unit": self.strain_unit,
                "stress_unit": self.stress_unit,
            }
        )


def synthetic_csv_detection_canonical(value: SyntheticCsvDetectionReport) -> dict[str, object]:
    return {
        "raw_asset_id": str(value.raw_asset_id),
        "raw_artifact_id": str(value.raw_artifact_id),
        "raw_sha256": value.raw_sha256,
        "header_columns": list(value.header_columns),
        "status": value.status.value,
        "suggested_strain_column": value.suggested_strain_column,
        "suggested_strain_unit": value.suggested_strain_unit,
        "strain_confidence": value.strain_confidence.value,
        "suggested_stress_column": value.suggested_stress_column,
        "suggested_stress_unit": value.suggested_stress_unit,
        "stress_confidence": value.stress_confidence.value,
        "importer_id": value.importer_id,
        "importer_version": value.importer_version,
        "reference_only": value.reference_only,
    }


def reference_import_mapping_canonical(value: ReferenceImportMappingContent) -> dict[str, object]:
    return {
        "mapping_label": value.mapping_label,
        "detection_report_id": str(value.detection_report_id),
        "raw_asset_id": str(value.raw_asset_id),
        "raw_artifact_id": str(value.raw_artifact_id),
        "strain_column": value.strain_column,
        "stress_column": value.stress_column,
        "strain_unit": value.strain_unit,
        "stress_unit": value.stress_unit,
        "dataset_mapping_sha256": value.dataset_mapping_digest,
        "importer_id": value.importer_id,
        "importer_version": value.importer_version,
        "approval_kind": value.approval_kind,
        "reference_only": value.reference_only,
    }


def _header_suggestion(
    headers: tuple[str, ...],
    candidates: tuple[tuple[str, str], ...],
) -> tuple[str | None, str | None, MappingSuggestionConfidence]:
    for column, unit in candidates:
        if column in headers:
            return column, unit, MappingSuggestionConfidence.LOW
    return None, None, MappingSuggestionConfidence.NONE


def detect_synthetic_csv_header(
    value: bytes,
    *,
    raw_asset_id: UUID,
    raw_artifact_id: UUID,
    raw_sha256: str,
) -> SyntheticCsvDetectionReport:
    """Inspect one UTF-8 header without parsing values or silently choosing semantics."""

    try:
        text = value.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise InvalidTestingData("synthetic CSV detection requires UTF-8 input") from error
    try:
        row = next(csv.reader(io.StringIO(text)))
    except StopIteration as error:
        raise InvalidTestingData("synthetic CSV detection requires a header row") from error
    headers = tuple(item.strip() for item in row)
    if any(not item for item in headers):
        raise InvalidTestingData("synthetic CSV detection rejects empty header names")
    strain_column, strain_unit, strain_confidence = _header_suggestion(
        headers,
        (
            ("strain_pct", "%"),
            ("engineering_strain_pct", "%"),
            ("engineering_strain", "1"),
        ),
    )
    stress_column, stress_unit, stress_confidence = _header_suggestion(
        headers,
        (
            ("stress_mpa", "MPa"),
            ("engineering_stress_mpa", "MPa"),
            ("engineering_stress_pa", "Pa"),
        ),
    )
    return SyntheticCsvDetectionReport(
        raw_asset_id=raw_asset_id,
        raw_artifact_id=raw_artifact_id,
        raw_sha256=raw_sha256,
        header_columns=headers,
        status=ImportDetectionStatus.NEEDS_INPUT,
        suggested_strain_column=strain_column,
        suggested_strain_unit=strain_unit,
        strain_confidence=strain_confidence,
        suggested_stress_column=stress_column,
        suggested_stress_unit=stress_unit,
        stress_confidence=stress_confidence,
    )

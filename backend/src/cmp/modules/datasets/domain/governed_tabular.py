"""Governed tabular test-data schemas and safe CSV/TSV/XLSX parsing for T-41.

The supported schemas and quantity/unit relations are deliberately closed.  Channel rows are
typed relations, not arbitrary attributes, and the original file always remains the authority.
"""

from __future__ import annotations

import csv
import io
import math
import re
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import PurePosixPath
from typing import cast
from uuid import UUID
from xml.etree import ElementTree as ET

import pyarrow as pa
import pyarrow.parquet as pq

from cmp.modules.units.domain.system import (
    DimensionId,
    QuantityReference,
    UnitError,
    convert_value,
    unit_definition,
)
from cmp.shared.domain.revisions import content_sha256

GOVERNED_IMPORT_PROFILE_SCHEMA_ID = "urn:cmp:datasets:governed-import-profile:1.1.0"
GOVERNED_IMPORT_PROFILE_SCHEMA_ID_1_0 = "urn:cmp:datasets:governed-import-profile:1.0.0"
GOVERNED_IMPORT_PROFILE_SCHEMA_ID_1_2 = "urn:cmp:datasets:governed-import-profile:1.2.0"
GOVERNED_IMPORT_PROFILE_SCHEMA_ID_1_3 = "urn:cmp:datasets:governed-import-profile:1.3.0"
GOVERNED_IMPORT_PROFILE_SCHEMA_VERSION_1_0 = "1.0.0"
GOVERNED_IMPORT_PROFILE_SCHEMA_VERSION_1_1 = "1.1.0"
GOVERNED_IMPORT_PROFILE_SCHEMA_VERSION_1_2 = "1.2.0"
GOVERNED_IMPORT_PROFILE_SCHEMA_VERSION_1_3 = "1.3.0"
GOVERNED_DATASET_SCHEMA_ID = "urn:cmp:datasets:governed-tabular-dataset:1.1.0"
GOVERNED_IMPORTER_ID = "urn:cmp:datasets:governed-tabular-importer:1.1.0"
GOVERNED_IMPORTER_VERSION = "1.1.0"
GOVERNED_PARQUET_SCHEMA = "urn:cmp:datasets:governed-tabular-normalized-parquet:1.1.0"
MAX_SOURCE_BYTES = 16 * 1024 * 1024
MAX_ROWS = 100_000
MAX_COLUMNS = 512
MAX_XLSX_MEMBERS = 128
MAX_XLSX_UNCOMPRESSED_BYTES = 32 * 1024 * 1024
MAX_XLSX_COMPRESSION_RATIO = 100

_write_parquet = cast(Callable[..., None], pq.write_table)


class GovernedImportError(Exception):
    """Base error for the governed tabular intake boundary."""


class InvalidGovernedImport(GovernedImportError, ValueError):
    """A parser setting, profile, row, or schema is invalid."""

    def __init__(
        self,
        message: str,
        diagnostics: tuple[ImportDiagnostic, ...] = (),
    ) -> None:
        super().__init__(message)
        self.diagnostics = diagnostics


class GovernedImportNotFound(GovernedImportError):
    """A tenant-scoped governed import record is absent."""


class GovernedImportConflict(GovernedImportError):
    """Pinned evidence conflicts with the requested import."""


class TabularFileFormat(StrEnum):
    CSV = "csv"
    TSV = "tsv"
    XLSX = "xlsx"


class TabularDataSchema(StrEnum):
    MONOTONIC_TENSION = "monotonic_tension"
    MONOTONIC_COMPRESSION = "monotonic_compression"
    PLANAR_TENSION = "planar_tension"
    BIAXIAL_TENSION = "biaxial_tension"
    SIMPLE_SHEAR = "simple_shear"
    SHEAR_RELAXATION = "shear_relaxation"
    DMA_FREQUENCY_TEMPERATURE_SWEEP = "dma_frequency_temperature_sweep"
    DMA_TEMPERATURE_SWEEP = "dma_temperature_sweep"
    FORMING_LIMIT = "forming_limit_diagram"


class QuantityKind(StrEnum):
    ENGINEERING_STRAIN = "engineering_strain"
    ENGINEERING_STRESS = "engineering_stress"
    SHEAR_STRAIN = "shear_strain"
    SHEAR_STRESS = "shear_stress"
    TIME = "time"
    SHEAR_MODULUS = "shear_modulus"
    DISPLACEMENT = "displacement"
    FORCE = "force"
    TEMPERATURE = "temperature"
    FREQUENCY = "frequency"
    STORAGE_MODULUS = "storage_modulus"
    LOSS_MODULUS = "loss_modulus"
    TAN_DELTA = "tan_delta"
    MINOR_STRAIN = "minor_strain"
    MAJOR_STRAIN = "major_strain"


class AxisRole(StrEnum):
    INDEPENDENT = "independent"
    DEPENDENT = "dependent"


class GovernedDatasetRepresentation(StrEnum):
    RAW = "raw"
    NORMALIZED = "normalized"


class ImportRunStatus(StrEnum):
    EXECUTING = "executing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class ImportDiagnostic:
    ordinal: int
    row_number: int | None
    column_name: str | None
    channel_key: str | None
    error_code: str
    error_detail: str
    recovery_hint: str

    def __post_init__(self) -> None:
        if not 0 <= self.ordinal <= 99:
            raise ValueError("diagnostic ordinal must be within 0..99")
        if self.row_number is not None and self.row_number < 1:
            raise ValueError("diagnostic row_number must be positive")
        if self.column_name is not None:
            _text("diagnostic column_name", self.column_name, 255)
        if self.channel_key is not None:
            _text("diagnostic channel_key", self.channel_key, 64)
        _text("diagnostic error_code", self.error_code, 100)
        _text("diagnostic error_detail", self.error_detail, 1000)
        _text("diagnostic recovery_hint", self.recovery_hint, 500)


_NORMALIZED_UNITS: dict[QuantityKind, str] = {
    QuantityKind.ENGINEERING_STRAIN: "1",
    QuantityKind.SHEAR_STRAIN: "1",
    QuantityKind.ENGINEERING_STRESS: "Pa",
    QuantityKind.SHEAR_STRESS: "Pa",
    QuantityKind.SHEAR_MODULUS: "Pa",
    QuantityKind.TIME: "s",
    QuantityKind.DISPLACEMENT: "m",
    QuantityKind.FORCE: "N",
    QuantityKind.TEMPERATURE: "K",
    QuantityKind.FREQUENCY: "Hz",
    QuantityKind.STORAGE_MODULUS: "Pa",
    QuantityKind.LOSS_MODULUS: "Pa",
    QuantityKind.TAN_DELTA: "1",
    QuantityKind.MINOR_STRAIN: "1",
    QuantityKind.MAJOR_STRAIN: "1",
}

_QUANTITY_CONTRACT: dict[QuantityKind, tuple[DimensionId, str]] = {
    QuantityKind.ENGINEERING_STRAIN: (
        DimensionId.STRAIN,
        "mechanics.strain.engineering",
    ),
    QuantityKind.SHEAR_STRAIN: (DimensionId.STRAIN, "mechanics.strain.shear"),
    QuantityKind.ENGINEERING_STRESS: (
        DimensionId.FORCE_PER_AREA,
        "mechanics.stress.engineering",
    ),
    QuantityKind.SHEAR_STRESS: (
        DimensionId.FORCE_PER_AREA,
        "mechanics.stress.shear",
    ),
    QuantityKind.SHEAR_MODULUS: (
        DimensionId.FORCE_PER_AREA,
        "mechanics.modulus.shear.relaxation",
    ),
    QuantityKind.TIME: (DimensionId.TIME, "time.elapsed"),
    QuantityKind.DISPLACEMENT: (DimensionId.LENGTH, "displacement"),
    QuantityKind.FORCE: (DimensionId.FORCE, "mechanics.force"),
    QuantityKind.TEMPERATURE: (DimensionId.TEMPERATURE, "temperature.test"),
    QuantityKind.STORAGE_MODULUS: (
        DimensionId.FORCE_PER_AREA,
        "mechanics.modulus.storage",
    ),
    QuantityKind.LOSS_MODULUS: (
        DimensionId.FORCE_PER_AREA,
        "mechanics.modulus.loss",
    ),
    QuantityKind.TAN_DELTA: (DimensionId.STRAIN, "mechanics.loss_factor"),
    QuantityKind.MINOR_STRAIN: (DimensionId.STRAIN, "mechanics.strain.minor"),
    QuantityKind.MAJOR_STRAIN: (DimensionId.STRAIN, "mechanics.strain.major"),
}


def _conversion_parameters(quantity: QuantityKind, original_unit: str) -> tuple[float, float]:
    if quantity is QuantityKind.FREQUENCY:
        if original_unit != "Hz":
            raise InvalidGovernedImport("frequency requires the bounded explicit-legacy Hz unit")
        return 1.0, 0.0
    dimension, semantics = _QUANTITY_CONTRACT[quantity]
    try:
        result = convert_value(
            "1",
            original_unit_string=original_unit,
            source=QuantityReference(dimension, semantics, original_unit),
            target=QuantityReference(dimension, semantics, _NORMALIZED_UNITS[quantity]),
            location=f"governed_import.{quantity.value}",
        )
    except UnitError as error:
        raise InvalidGovernedImport(error.message) from error
    return float(result.scale), float(result.offset)


def _text(name: str, value: str, maximum: int) -> None:
    if not value or value != value.strip() or len(value) > maximum or "\x00" in value:
        raise InvalidGovernedImport(f"{name} must be trimmed and contain 1..{maximum} characters")


def _uuid(name: str, value: UUID) -> None:
    if value.int == 0:
        raise InvalidGovernedImport(f"{name} must be non-zero")


def normalized_quantity(source: QuantityKind) -> QuantityKind:
    if source is QuantityKind.DISPLACEMENT:
        return QuantityKind.ENGINEERING_STRAIN
    if source is QuantityKind.FORCE:
        return QuantityKind.ENGINEERING_STRESS
    return source


@dataclass(frozen=True, slots=True)
class GovernedChannelMapping:
    ordinal: int
    source_column: str
    source_quantity: QuantityKind
    original_unit: str
    axis_role: AxisRole

    def __post_init__(self) -> None:
        if not 0 <= self.ordinal <= 4:
            raise InvalidGovernedImport("channel ordinal must be within 0..4")
        _text("source_column", self.source_column, 255)
        if self.source_quantity is QuantityKind.FREQUENCY:
            _conversion_parameters(self.source_quantity, self.original_unit)
            return
        expected_dimension, _ = _QUANTITY_CONTRACT[self.source_quantity]
        try:
            actual_dimension = unit_definition(self.original_unit).dimension
        except UnitError as error:
            raise InvalidGovernedImport(error.message) from error
        if actual_dimension is not expected_dimension:
            raise InvalidGovernedImport(
                f"unit {self.original_unit!r} is not valid for {self.source_quantity.value}"
            )

    @property
    def normalized_quantity(self) -> QuantityKind:
        return normalized_quantity(self.source_quantity)

    @property
    def normalized_unit(self) -> str:
        return _NORMALIZED_UNITS[self.normalized_quantity]


@dataclass(frozen=True, slots=True)
class GovernedImportProfileContent:
    profile_label: str
    data_schema: TabularDataSchema
    file_format: TabularFileFormat
    sheet_name: str | None
    header_row: int
    encoding: str
    delimiter: str | None
    decimal_separator: str
    channels: tuple[GovernedChannelMapping, ...]
    initial_gauge_length_m: float | None = None
    initial_cross_section_area_m2: float | None = None
    approval_kind: str = "human_confirmed"
    # These fields were appended to preserve positional construction and the exact
    # canonical bytes of historical 1.0/1.1 revisions.
    schema_version: str = GOVERNED_IMPORT_PROFILE_SCHEMA_VERSION_1_1
    deformation_mode: str | None = None

    def __post_init__(self) -> None:
        _text("profile_label", self.profile_label, 160)
        if self.schema_version not in {
            GOVERNED_IMPORT_PROFILE_SCHEMA_VERSION_1_0,
            GOVERNED_IMPORT_PROFILE_SCHEMA_VERSION_1_1,
            GOVERNED_IMPORT_PROFILE_SCHEMA_VERSION_1_2,
            GOVERNED_IMPORT_PROFILE_SCHEMA_VERSION_1_3,
        }:
            raise InvalidGovernedImport("unsupported governed Import Profile schema_version")
        if self.deformation_mode not in (None, "shear"):
            raise InvalidGovernedImport("deformation_mode is nullable and only permits shear")
        if (
            self.schema_version
            not in {
                GOVERNED_IMPORT_PROFILE_SCHEMA_VERSION_1_2,
                GOVERNED_IMPORT_PROFILE_SCHEMA_VERSION_1_3,
            }
            and self.deformation_mode is not None
        ):
            raise InvalidGovernedImport(
                "historical Import Profile revisions cannot carry deformation_mode"
            )
        if not 1 <= self.header_row <= 100:
            raise InvalidGovernedImport("header_row must be within 1..100")
        if self.decimal_separator not in (".", ","):
            raise InvalidGovernedImport("decimal_separator must be '.' or ','")
        if self.file_format is TabularFileFormat.XLSX:
            if self.sheet_name is None:
                raise InvalidGovernedImport("XLSX profile requires an explicit sheet_name")
            _text("sheet_name", self.sheet_name, 255)
            if self.encoding != "binary" or self.delimiter is not None:
                raise InvalidGovernedImport(
                    "XLSX profile requires binary encoding and no delimiter"
                )
        else:
            if self.sheet_name is not None:
                raise InvalidGovernedImport("CSV/TSV profile cannot name a worksheet")
            if self.encoding not in ("utf-8", "utf-8-sig"):
                raise InvalidGovernedImport("CSV/TSV encoding must be utf-8 or utf-8-sig")
            expected = "\t" if self.file_format is TabularFileFormat.TSV else None
            if expected is not None and self.delimiter != expected:
                raise InvalidGovernedImport("TSV profile delimiter must be a tab")
            if self.file_format is TabularFileFormat.CSV and self.delimiter not in (",", ";"):
                raise InvalidGovernedImport("CSV delimiter must be comma or semicolon")
            if self.delimiter == self.decimal_separator:
                raise InvalidGovernedImport("delimiter and decimal_separator must differ")
        if not 2 <= len(self.channels) <= 5:
            raise InvalidGovernedImport("a governed curve profile requires two to five channels")
        channels = tuple(sorted(self.channels, key=lambda item: item.ordinal))
        if tuple(channel.ordinal for channel in channels) != tuple(range(len(channels))):
            raise InvalidGovernedImport("channel ordinals must be contiguous")
        if len({channel.source_column for channel in channels}) != len(channels):
            raise InvalidGovernedImport("source columns must be distinct")
        self._validate_schema(channels)
        object.__setattr__(self, "channels", channels)
        if (
            self.schema_version
            in {
                GOVERNED_IMPORT_PROFILE_SCHEMA_VERSION_1_2,
                GOVERNED_IMPORT_PROFILE_SCHEMA_VERSION_1_3,
            }
            and self.data_schema
            not in {
                TabularDataSchema.DMA_FREQUENCY_TEMPERATURE_SWEEP,
                TabularDataSchema.DMA_TEMPERATURE_SWEEP,
            }
            and self.deformation_mode is not None
        ):
            raise InvalidGovernedImport("non-DMA 1.2 profiles require deformation_mode=null")
        if self.approval_kind != "human_confirmed":
            raise InvalidGovernedImport("Import Profile approval must be human_confirmed")

    @property
    def effective_deformation_mode(self) -> str:
        """Internal mode for eligibility checks; legacy response/canonical bytes omit it."""

        return self.deformation_mode or "not-characterized"

    def _validate_schema(self, channels: tuple[GovernedChannelMapping, ...]) -> None:
        kinds = tuple(channel.source_quantity for channel in channels)
        roles = tuple(channel.axis_role for channel in channels)
        direct_axial = (QuantityKind.ENGINEERING_STRAIN, QuantityKind.ENGINEERING_STRESS)
        geometry_axial = (QuantityKind.DISPLACEMENT, QuantityKind.FORCE)
        if self.data_schema in (
            TabularDataSchema.MONOTONIC_TENSION,
            TabularDataSchema.MONOTONIC_COMPRESSION,
        ):
            if kinds not in (direct_axial, geometry_axial):
                raise InvalidGovernedImport(
                    "uniaxial schema requires strain/stress or displacement/force"
                )
            geometry_required = kinds == geometry_axial
        elif self.data_schema in (
            TabularDataSchema.PLANAR_TENSION,
            TabularDataSchema.BIAXIAL_TENSION,
        ):
            if kinds != direct_axial:
                raise InvalidGovernedImport("planar/biaxial schema requires strain/stress")
            geometry_required = False
        elif self.data_schema is TabularDataSchema.SIMPLE_SHEAR:
            if kinds != (QuantityKind.SHEAR_STRAIN, QuantityKind.SHEAR_STRESS):
                raise InvalidGovernedImport("simple shear requires shear_strain/shear_stress")
            geometry_required = False
        elif self.data_schema is TabularDataSchema.SHEAR_RELAXATION:
            if kinds != (QuantityKind.TIME, QuantityKind.SHEAR_MODULUS):
                raise InvalidGovernedImport("shear relaxation requires time/shear_modulus")
            geometry_required = False
        elif self.data_schema is TabularDataSchema.DMA_FREQUENCY_TEMPERATURE_SWEEP:
            required = (
                QuantityKind.TEMPERATURE,
                QuantityKind.FREQUENCY,
                QuantityKind.STORAGE_MODULUS,
                QuantityKind.LOSS_MODULUS,
            )
            if kinds not in (required, (*required, QuantityKind.TAN_DELTA)):
                raise InvalidGovernedImport(
                    "DMA frequency-temperature sweep requires temperature/frequency/"
                    "storage_modulus/loss_modulus and optional tan_delta"
                )
            expected_roles = (
                AxisRole.INDEPENDENT,
                AxisRole.INDEPENDENT,
                *(AxisRole.DEPENDENT for _ in kinds[2:]),
            )
            if roles != expected_roles:
                raise InvalidGovernedImport(
                    "DMA temperature/frequency must be independent and response channels dependent"
                )
            geometry_required = False
        elif self.data_schema is TabularDataSchema.DMA_TEMPERATURE_SWEEP:
            if self.schema_version != GOVERNED_IMPORT_PROFILE_SCHEMA_VERSION_1_3:
                raise InvalidGovernedImport(
                    "DMA temperature sweep requires Import Profile schema 1.3.0"
                )
            if self.deformation_mode != "shear":
                raise InvalidGovernedImport("DMA temperature sweep requires deformation_mode=shear")
            accepted = {
                (
                    QuantityKind.TEMPERATURE,
                    QuantityKind.STORAGE_MODULUS,
                    QuantityKind.LOSS_MODULUS,
                ),
                (
                    QuantityKind.TEMPERATURE,
                    QuantityKind.STORAGE_MODULUS,
                    QuantityKind.TAN_DELTA,
                ),
                (
                    QuantityKind.TEMPERATURE,
                    QuantityKind.STORAGE_MODULUS,
                    QuantityKind.LOSS_MODULUS,
                    QuantityKind.TAN_DELTA,
                ),
            }
            if kinds not in accepted:
                raise InvalidGovernedImport(
                    "DMA temperature sweep requires temperature/storage_modulus and "
                    "loss_modulus, tan_delta, or both"
                )
            if roles != (
                AxisRole.INDEPENDENT,
                *(AxisRole.DEPENDENT for _ in kinds[1:]),
            ):
                raise InvalidGovernedImport(
                    "DMA temperature must be independent and response channels dependent"
                )
            geometry_required = False
        else:
            if kinds != (QuantityKind.MINOR_STRAIN, QuantityKind.MAJOR_STRAIN):
                raise InvalidGovernedImport("forming limit requires minor_strain/major_strain")
            geometry_required = False
        if self.data_schema not in (
            TabularDataSchema.DMA_FREQUENCY_TEMPERATURE_SWEEP,
            TabularDataSchema.DMA_TEMPERATURE_SWEEP,
        ) and roles != (AxisRole.INDEPENDENT, AxisRole.DEPENDENT):
            raise InvalidGovernedImport("channel 0/1 must be independent/dependent")
        geometry = (self.initial_gauge_length_m, self.initial_cross_section_area_m2)
        if geometry_required:
            if any(value is None or not math.isfinite(value) or value <= 0 for value in geometry):
                raise InvalidGovernedImport(
                    "displacement/force requires positive gauge length and cross-section area"
                )
        elif any(value is not None for value in geometry):
            raise InvalidGovernedImport("specimen geometry is only accepted for displacement/force")

    @property
    def digest(self) -> str:
        return content_sha256(import_profile_canonical(self))


@dataclass(frozen=True, slots=True)
class TabularPreview:
    raw_asset_id: UUID
    raw_artifact_id: UUID
    raw_sha256: str
    file_format: TabularFileFormat
    sheet_names: tuple[str, ...]
    selected_sheet_name: str | None
    header_row: int
    encoding: str
    delimiter: str | None
    decimal_separator: str
    header_columns: tuple[str, ...]
    sample_rows: tuple[tuple[str, ...], ...]
    status: str = "needs_input"

    def __post_init__(self) -> None:
        _uuid("raw_asset_id", self.raw_asset_id)
        _uuid("raw_artifact_id", self.raw_artifact_id)
        if not re.fullmatch(r"[0-9a-f]{64}", self.raw_sha256):
            raise InvalidGovernedImport("raw_sha256 must be lowercase SHA-256")
        is_sheet_discovery = (
            self.file_format is TabularFileFormat.XLSX
            and self.selected_sheet_name is None
            and len(self.sheet_names) > 1
            and not self.header_columns
            and not self.sample_rows
        )
        if not is_sheet_discovery and not 1 <= len(self.header_columns) <= MAX_COLUMNS:
            raise InvalidGovernedImport("preview must expose 1..512 columns")
        if len(set(self.header_columns)) != len(self.header_columns):
            raise InvalidGovernedImport("header columns must be unique")
        if self.status != "needs_input":
            raise InvalidGovernedImport("preview cannot approve a semantic mapping")

    @property
    def digest(self) -> str:
        return content_sha256(
            {
                "raw_asset_id": str(self.raw_asset_id),
                "raw_artifact_id": str(self.raw_artifact_id),
                "raw_sha256": self.raw_sha256,
                "file_format": self.file_format.value,
                "sheet_names": list(self.sheet_names),
                "selected_sheet_name": self.selected_sheet_name,
                "header_row": self.header_row,
                "encoding": self.encoding,
                "delimiter": self.delimiter,
                "decimal_separator": self.decimal_separator,
                "header_columns": list(self.header_columns),
                "status": self.status,
            }
        )


@dataclass(frozen=True, slots=True)
class NormalizedTabularData:
    columns: tuple[QuantityKind, ...]
    rows: tuple[tuple[float, ...], ...]

    def __post_init__(self) -> None:
        if not 2 <= len(self.rows) <= MAX_ROWS:
            raise InvalidGovernedImport("normalized curve requires 2..100000 rows")
        if not 2 <= len(self.columns) <= 5:
            raise InvalidGovernedImport("normalized curve requires two to five columns")
        if any(len(row) != len(self.columns) for row in self.rows):
            raise InvalidGovernedImport("normalized rows must match the declared columns")


@dataclass(frozen=True, slots=True)
class GovernedTabularEvidence:
    """Original mapped values plus their explicit normalized calculation values."""

    original_rows: tuple[tuple[float, ...], ...]
    normalized: NormalizedTabularData
    normalization_scales: tuple[float, ...]
    normalization_offsets: tuple[float, ...]

    def __post_init__(self) -> None:
        if len(self.original_rows) != len(self.normalized.rows):
            raise InvalidGovernedImport("original and normalized row counts must match")
        if len(self.normalization_scales) != len(self.normalized.columns):
            raise InvalidGovernedImport("normalization scales must match normalized columns")
        if len(self.normalization_offsets) != len(self.normalized.columns):
            raise InvalidGovernedImport("normalization offsets must match normalized columns")
        if any(not math.isfinite(value) or value <= 0 for value in self.normalization_scales):
            raise InvalidGovernedImport("normalization scales must be finite and positive")
        if any(not math.isfinite(value) for value in self.normalization_offsets):
            raise InvalidGovernedImport("normalization offsets must be finite")


@dataclass(frozen=True, slots=True)
class GovernedDatasetContent:
    test_run_id: UUID
    test_run_revision_id: UUID
    raw_asset_id: UUID
    raw_artifact_id: UUID
    import_profile_id: UUID
    import_profile_revision_id: UUID
    representation: GovernedDatasetRepresentation
    data_schema: TabularDataSchema
    data_artifact_id: UUID
    data_sha256: str
    source_dataset_revision_id: UUID | None
    row_count: int
    channels: tuple[GovernedChannelMapping, ...]

    def __post_init__(self) -> None:
        for name, value in (
            ("test_run_id", self.test_run_id),
            ("test_run_revision_id", self.test_run_revision_id),
            ("raw_asset_id", self.raw_asset_id),
            ("raw_artifact_id", self.raw_artifact_id),
            ("import_profile_id", self.import_profile_id),
            ("import_profile_revision_id", self.import_profile_revision_id),
            ("data_artifact_id", self.data_artifact_id),
        ):
            _uuid(name, value)
        if not re.fullmatch(r"[0-9a-f]{64}", self.data_sha256):
            raise InvalidGovernedImport("data_sha256 must be lowercase SHA-256")
        if not 2 <= self.row_count <= MAX_ROWS:
            raise InvalidGovernedImport("Dataset row_count must be 2..100000")
        if self.representation is GovernedDatasetRepresentation.RAW:
            if self.source_dataset_revision_id is not None:
                raise InvalidGovernedImport("raw Dataset cannot name a source Dataset revision")
            if self.data_artifact_id != self.raw_artifact_id:
                raise InvalidGovernedImport("raw Dataset must reference the original Artifact")
        else:
            if self.source_dataset_revision_id is None:
                raise InvalidGovernedImport("normalized Dataset requires an exact raw revision")
            _uuid("source_dataset_revision_id", self.source_dataset_revision_id)
            if self.data_artifact_id == self.raw_artifact_id:
                raise InvalidGovernedImport("normalized Dataset requires a derived Artifact")


def _channel_canonical(value: GovernedChannelMapping) -> dict[str, object]:
    return {
        "ordinal": value.ordinal,
        "source_column": value.source_column,
        "source_quantity": value.source_quantity.value,
        "original_unit": value.original_unit,
        "normalized_quantity": value.normalized_quantity.value,
        "normalized_unit": value.normalized_unit,
        "axis_role": value.axis_role.value,
    }


def import_profile_canonical(value: GovernedImportProfileContent) -> dict[str, object]:
    result: dict[str, object] = {
        "profile_label": value.profile_label,
        "data_schema": value.data_schema.value,
        "file_format": value.file_format.value,
        "sheet_name": value.sheet_name,
        "header_row": value.header_row,
        "encoding": value.encoding,
        "delimiter": value.delimiter,
        "decimal_separator": value.decimal_separator,
        "initial_gauge_length_m": value.initial_gauge_length_m,
        "initial_cross_section_area_m2": value.initial_cross_section_area_m2,
        "approval_kind": value.approval_kind,
        "channels": [_channel_canonical(item) for item in value.channels],
        "importer_id": GOVERNED_IMPORTER_ID,
        "importer_version": GOVERNED_IMPORTER_VERSION,
    }
    if value.schema_version in {
        GOVERNED_IMPORT_PROFILE_SCHEMA_VERSION_1_2,
        GOVERNED_IMPORT_PROFILE_SCHEMA_VERSION_1_3,
    }:
        result["schema_version"] = value.schema_version
        result["deformation_mode"] = value.deformation_mode
    return result


def governed_dataset_canonical(value: GovernedDatasetContent) -> dict[str, object]:
    return {
        "test_run_id": str(value.test_run_id),
        "test_run_revision_id": str(value.test_run_revision_id),
        "raw_asset_id": str(value.raw_asset_id),
        "raw_artifact_id": str(value.raw_artifact_id),
        "import_profile_id": str(value.import_profile_id),
        "import_profile_revision_id": str(value.import_profile_revision_id),
        "representation": value.representation.value,
        "data_schema": value.data_schema.value,
        "data_artifact_id": str(value.data_artifact_id),
        "data_sha256": value.data_sha256,
        "source_dataset_revision_id": (
            str(value.source_dataset_revision_id)
            if value.source_dataset_revision_id is not None
            else None
        ),
        "row_count": value.row_count,
        "channels": [_channel_canonical(item) for item in value.channels],
        "importer_id": GOVERNED_IMPORTER_ID,
        "importer_version": GOVERNED_IMPORTER_VERSION,
    }


def _decode_delimited(value: bytes, profile: GovernedImportProfileContent) -> list[list[str]]:
    codec = "utf-8-sig" if profile.encoding == "utf-8-sig" else "utf-8"
    try:
        text = value.decode(codec)
    except UnicodeDecodeError as error:
        raise InvalidGovernedImport(f"source bytes are not valid {profile.encoding}") from error
    reader = csv.reader(io.StringIO(text), delimiter=profile.delimiter or ",", strict=True)
    try:
        rows = [list(row) for row in reader]
    except csv.Error as error:
        raise InvalidGovernedImport("delimited source is malformed") from error
    if len(rows) > MAX_ROWS + profile.header_row:
        raise InvalidGovernedImport("source exceeds the 100000-row limit")
    return rows


def _xlsx_text(root: ET.Element, shared: tuple[str, ...]) -> str:
    namespace = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    cell_type = root.attrib.get("t")
    if root.find(f"{namespace}f") is not None:
        raise InvalidGovernedImport("XLSX formulas are not accepted as test evidence")
    if cell_type == "inlineStr":
        return "".join(node.text or "" for node in root.findall(f".//{namespace}t"))
    value = root.find(f"{namespace}v")
    raw = "" if value is None or value.text is None else value.text
    if cell_type == "s":
        try:
            return shared[int(raw)]
        except (ValueError, IndexError) as error:
            raise InvalidGovernedImport("XLSX shared-string reference is invalid") from error
    if cell_type == "b":
        return "TRUE" if raw == "1" else "FALSE"
    return raw


def _column_index(reference: str) -> int:
    match = re.fullmatch(r"([A-Z]+)[0-9]+", reference)
    if match is None:
        raise InvalidGovernedImport("XLSX cell reference is invalid")
    result = 0
    for character in match.group(1):
        result = result * 26 + ord(character) - ord("A") + 1
    if not 1 <= result <= MAX_COLUMNS:
        raise InvalidGovernedImport("XLSX exceeds the 512-column limit")
    return result - 1


def _safe_xlsx_rows(
    value: bytes, sheet_name: str | None
) -> tuple[tuple[str, ...], list[list[str]]]:
    try:
        archive = zipfile.ZipFile(io.BytesIO(value))
    except zipfile.BadZipFile as error:
        raise InvalidGovernedImport("source is not a valid XLSX package") from error
    with archive:
        members = archive.infolist()
        if len(members) > MAX_XLSX_MEMBERS:
            raise InvalidGovernedImport("XLSX package contains too many members")
        total = 0
        for member in members:
            path = PurePosixPath(member.filename)
            if path.is_absolute() or ".." in path.parts or "\\" in member.filename:
                raise InvalidGovernedImport("XLSX package contains an unsafe member path")
            total += member.file_size
            if total > MAX_XLSX_UNCOMPRESSED_BYTES:
                raise InvalidGovernedImport("XLSX uncompressed content exceeds 32 MiB")
            if member.file_size > 0 and member.compress_size == 0:
                raise InvalidGovernedImport("XLSX member has an invalid compression manifest")
            if (
                member.compress_size
                and member.file_size / member.compress_size > MAX_XLSX_COMPRESSION_RATIO
            ):
                raise InvalidGovernedImport("XLSX compression ratio exceeds the safety limit")
            if member.filename.startswith("xl/externalLinks/") or member.filename.endswith(
                "vbaProject.bin"
            ):
                raise InvalidGovernedImport("XLSX external links and macros are not accepted")
        names = {member.filename for member in members}
        required = {"xl/workbook.xml", "xl/_rels/workbook.xml.rels"}
        if not required.issubset(names):
            raise InvalidGovernedImport("XLSX workbook manifest is incomplete")
        ns = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
        rel_ns = "{http://schemas.openxmlformats.org/package/2006/relationships}"
        office_rel = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        relationships = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        rel_targets = {
            item.attrib["Id"]: item.attrib["Target"]
            for item in relationships.findall(f"{rel_ns}Relationship")
        }
        sheets = tuple(workbook.findall(f".//{ns}sheet"))
        sheet_names = tuple(item.attrib.get("name", "") for item in sheets)
        if sheet_name is None:
            if len(sheet_names) != 1:
                return sheet_names, []
            sheet_name = sheet_names[0]
        if sheet_name not in sheet_names:
            raise InvalidGovernedImport("selected XLSX sheet does not exist")
        sheet = sheets[sheet_names.index(sheet_name)]
        target = rel_targets.get(sheet.attrib.get(office_rel, ""))
        if target is None:
            raise InvalidGovernedImport("selected XLSX sheet relationship is missing")
        relationship_target = PurePosixPath(target)
        if "\\" in target or ".." in relationship_target.parts:
            raise InvalidGovernedImport("selected XLSX worksheet relationship is unsafe")
        target_path_value = (
            PurePosixPath(*relationship_target.parts[1:])
            if relationship_target.is_absolute()
            else PurePosixPath("xl") / relationship_target
        )
        target_path = target_path_value.as_posix()
        if target_path not in names:
            raise InvalidGovernedImport("selected XLSX worksheet payload is missing")
        shared: tuple[str, ...] = ()
        if "xl/sharedStrings.xml" in names:
            shared_root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            shared = tuple(
                "".join(node.text or "" for node in item.findall(f".//{ns}t"))
                for item in shared_root.findall(f"{ns}si")
            )
        root = ET.fromstring(archive.read(target_path))
        rows: list[list[str]] = []
        for row in root.findall(f".//{ns}row"):
            values: list[str] = []
            for cell in row.findall(f"{ns}c"):
                index = _column_index(cell.attrib.get("r", ""))
                if index >= MAX_COLUMNS:
                    raise InvalidGovernedImport("XLSX exceeds the 512-column limit")
                if len(values) <= index:
                    values.extend("" for _ in range(index + 1 - len(values)))
                values[index] = _xlsx_text(cell, shared)
            rows.append(values)
            if len(rows) > MAX_ROWS + 100:
                raise InvalidGovernedImport("XLSX exceeds the 100000-row limit")
        return sheet_names, rows


def _rows(
    value: bytes, profile: GovernedImportProfileContent
) -> tuple[tuple[str, ...], list[list[str]]]:
    if len(value) > MAX_SOURCE_BYTES:
        raise InvalidGovernedImport("source exceeds the 16 MiB importer limit")
    if profile.file_format is TabularFileFormat.XLSX:
        return _safe_xlsx_rows(value, profile.sheet_name)
    return (), _decode_delimited(value, profile)


def inspect_tabular_source(
    value: bytes,
    *,
    raw_asset_id: UUID,
    raw_artifact_id: UUID,
    raw_sha256: str,
    file_format: TabularFileFormat,
    sheet_name: str | None,
    header_row: int,
    encoding: str,
    delimiter: str | None,
    decimal_separator: str,
) -> TabularPreview:
    if file_format is TabularFileFormat.XLSX and sheet_name is None:
        sheet_names, rows = _safe_xlsx_rows(value, None)
        if not rows:
            return TabularPreview(
                raw_asset_id=raw_asset_id,
                raw_artifact_id=raw_artifact_id,
                raw_sha256=raw_sha256,
                file_format=file_format,
                sheet_names=sheet_names,
                selected_sheet_name=None,
                header_row=header_row,
                encoding=encoding,
                delimiter=delimiter,
                decimal_separator=decimal_separator,
                header_columns=(),
                sample_rows=(),
            )
        sheet_name = sheet_names[0]
    dummy_channels = (
        GovernedChannelMapping(0, "x", QuantityKind.ENGINEERING_STRAIN, "1", AxisRole.INDEPENDENT),
        GovernedChannelMapping(1, "y", QuantityKind.ENGINEERING_STRESS, "Pa", AxisRole.DEPENDENT),
    )
    profile = GovernedImportProfileContent(
        profile_label="preview",
        data_schema=TabularDataSchema.MONOTONIC_TENSION,
        file_format=file_format,
        sheet_name=sheet_name,
        header_row=header_row,
        encoding=encoding,
        delimiter=delimiter,
        decimal_separator=decimal_separator,
        channels=dummy_channels,
    )
    sheet_names, rows = _rows(value, profile)
    if len(rows) < header_row:
        raise InvalidGovernedImport("source does not contain the selected header row")
    headers = tuple(item.strip() for item in rows[header_row - 1])
    while headers and not headers[-1]:
        headers = headers[:-1]
    if not headers or any(not item for item in headers):
        raise InvalidGovernedImport("header contains an empty column name")
    if len(headers) > MAX_COLUMNS or len(set(headers)) != len(headers):
        raise InvalidGovernedImport("header must contain at most 512 unique names")
    samples = tuple(
        tuple((row[index] if index < len(row) else "") for index in range(len(headers)))
        for row in rows[header_row : header_row + 5]
        if any(item.strip() for item in row)
    )
    return TabularPreview(
        raw_asset_id=raw_asset_id,
        raw_artifact_id=raw_artifact_id,
        raw_sha256=raw_sha256,
        file_format=file_format,
        sheet_names=sheet_names,
        selected_sheet_name=sheet_name,
        header_row=header_row,
        encoding=encoding,
        delimiter=delimiter,
        decimal_separator=decimal_separator,
        header_columns=headers,
        sample_rows=samples,
    )


def read_tabular_source_rows(
    value: bytes,
    *,
    file_format: TabularFileFormat,
    sheet_name: str | None,
    header_row: int,
    encoding: str,
    delimiter: str | None,
    decimal_separator: str,
) -> tuple[tuple[str, ...], str | None, tuple[dict[str, str], ...]]:
    """Return every non-empty data row using the governed safe parser limits.

    Catalog registration uses the same CSV/TSV/XLSX safety boundary as governed test-data
    import, while applying its own Attribute and unit semantics after parsing.
    """

    dummy_channels = (
        GovernedChannelMapping(0, "x", QuantityKind.ENGINEERING_STRAIN, "1", AxisRole.INDEPENDENT),
        GovernedChannelMapping(1, "y", QuantityKind.ENGINEERING_STRESS, "Pa", AxisRole.DEPENDENT),
    )
    profile = GovernedImportProfileContent(
        profile_label="catalog registration",
        data_schema=TabularDataSchema.MONOTONIC_TENSION,
        file_format=file_format,
        sheet_name=sheet_name,
        header_row=header_row,
        encoding=encoding,
        delimiter=delimiter,
        decimal_separator=decimal_separator,
        channels=dummy_channels,
    )
    sheet_names, rows = _rows(value, profile)
    selected_sheet = sheet_name
    if file_format is TabularFileFormat.XLSX and selected_sheet is None:
        if len(sheet_names) != 1:
            raise InvalidGovernedImport("select one XLSX sheet before checking rows")
        selected_sheet = sheet_names[0]
    if len(rows) < header_row:
        raise InvalidGovernedImport("source does not contain the selected header row")
    headers = tuple(item.strip() for item in rows[header_row - 1])
    while headers and not headers[-1]:
        headers = headers[:-1]
    if not headers or any(not item for item in headers):
        raise InvalidGovernedImport("header contains an empty column name")
    if len(headers) > MAX_COLUMNS or len(set(headers)) != len(headers):
        raise InvalidGovernedImport("header must contain at most 512 unique names")
    parsed = tuple(
        {header: row[index] if index < len(row) else "" for index, header in enumerate(headers)}
        for row in rows[header_row:]
        if any(item.strip() for item in row)
    )
    if not parsed:
        raise InvalidGovernedImport("source does not contain a data row")
    if len(parsed) > MAX_ROWS:
        raise InvalidGovernedImport("source exceeds the 100000-row limit")
    return sheet_names, selected_sheet, parsed


def _number(value: str, *, row: int, column: str, decimal_separator: str) -> float:
    stripped = value.strip()
    if not stripped:
        raise InvalidGovernedImport(f"row {row}: {column} is missing")
    if decimal_separator == ",":
        if "." in stripped:
            raise InvalidGovernedImport(f"row {row}: {column} uses an unexpected decimal point")
        stripped = stripped.replace(",", ".")
    elif "," in stripped:
        raise InvalidGovernedImport(f"row {row}: {column} uses an unexpected decimal comma")
    try:
        result = float(stripped)
    except ValueError as error:
        raise InvalidGovernedImport(f"row {row}: {column} is not numeric") from error
    if not math.isfinite(result):
        raise InvalidGovernedImport(f"row {row}: {column} must be finite")
    return result


def parse_governed_source(
    value: bytes, profile: GovernedImportProfileContent
) -> NormalizedTabularData:
    return parse_governed_source_evidence(value, profile).normalized


def parse_governed_source_evidence(
    value: bytes, profile: GovernedImportProfileContent
) -> GovernedTabularEvidence:
    _, rows = _rows(value, profile)
    if len(rows) < profile.header_row:
        raise InvalidGovernedImport("source does not contain the approved header row")
    headers = tuple(item.strip() for item in rows[profile.header_row - 1])
    diagnostics: list[ImportDiagnostic] = []
    diagnostic_total = 0

    def add_diagnostic(
        *,
        row_number: int | None,
        column_name: str | None,
        channel_key: str | None,
        error_code: str,
        error_detail: str,
        recovery_hint: str,
    ) -> None:
        nonlocal diagnostic_total
        diagnostic_total += 1
        if len(diagnostics) >= 100:
            return
        diagnostics.append(
            ImportDiagnostic(
                ordinal=len(diagnostics),
                row_number=row_number,
                column_name=column_name,
                channel_key=channel_key,
                error_code=error_code,
                error_detail=error_detail,
                recovery_hint=recovery_hint,
            )
        )

    indexes: list[int] = []
    for channel in profile.channels:
        try:
            indexes.append(headers.index(channel.source_column))
        except ValueError:
            add_diagnostic(
                row_number=profile.header_row,
                column_name=channel.source_column,
                channel_key=channel.source_quantity.value,
                error_code="missing_required_column",
                error_detail=f"approved column {channel.source_column!r} is absent",
                recovery_hint="Choose the source column required by this approved profile.",
            )
    if diagnostics:
        raise InvalidGovernedImport(
            f"{diagnostic_total} governed import validation error(s); "
            f"first: {diagnostics[0].error_detail}",
            tuple(diagnostics),
        )
    original: list[tuple[float, ...]] = []
    normalized: list[tuple[float, ...]] = []
    parameters = [
        _conversion_parameters(channel.source_quantity, channel.original_unit)
        for channel in profile.channels
    ]
    scales = [item[0] for item in parameters]
    offsets = [item[1] for item in parameters]
    if profile.channels[0].source_quantity is QuantityKind.DISPLACEMENT:
        scales[0] /= profile.initial_gauge_length_m or 0.0
        scales[1] /= profile.initial_cross_section_area_m2 or 0.0
    seen_coordinates: set[tuple[float, ...]] = set()
    for row_number, row in enumerate(rows[profile.header_row :], start=profile.header_row + 1):
        if not any(item.strip() for item in row):
            continue
        raw_row: list[float] = []
        row_invalid = False
        for index, channel in zip(indexes, profile.channels, strict=True):
            try:
                raw_row.append(
                    _number(
                        row[index] if index < len(row) else "",
                        row=row_number,
                        column=channel.source_column,
                        decimal_separator=profile.decimal_separator,
                    )
                )
            except InvalidGovernedImport as error:
                detail = str(error)
                code = (
                    "missing_value"
                    if detail.endswith(" is missing")
                    else "invalid_decimal_separator"
                    if "unexpected decimal" in detail
                    else "non_finite_value"
                    if detail.endswith(" must be finite")
                    else "non_numeric_value"
                )
                add_diagnostic(
                    row_number=row_number,
                    column_name=channel.source_column,
                    channel_key=channel.source_quantity.value,
                    error_code=code,
                    error_detail=detail,
                    recovery_hint=(
                        "Provide one finite numeric value using the approved decimal separator."
                    ),
                )
                row_invalid = True
        if row_invalid:
            continue
        raw_values = tuple(raw_row)
        point = tuple(
            raw * scale + offset
            for raw, scale, offset in zip(raw_values, scales, offsets, strict=True)
        )
        if profile.data_schema in (
            TabularDataSchema.MONOTONIC_TENSION,
            TabularDataSchema.MONOTONIC_COMPRESSION,
            TabularDataSchema.PLANAR_TENSION,
            TabularDataSchema.BIAXIAL_TENSION,
            TabularDataSchema.SHEAR_RELAXATION,
        ) and (point[0] < 0 or point[1] < 0):
            add_diagnostic(
                row_number=row_number,
                column_name=None,
                channel_key=None,
                error_code="negative_value",
                error_detail=f"row {row_number}: schema requires non-negative values",
                recovery_hint="Correct the signed source value or choose the matching test schema.",
            )
            continue
        if (
            profile.data_schema
            in (
                TabularDataSchema.MONOTONIC_TENSION,
                TabularDataSchema.MONOTONIC_COMPRESSION,
                TabularDataSchema.PLANAR_TENSION,
                TabularDataSchema.BIAXIAL_TENSION,
                TabularDataSchema.SIMPLE_SHEAR,
                TabularDataSchema.SHEAR_RELAXATION,
            )
            and normalized
            and point[0] <= normalized[-1][0]
        ):
            add_diagnostic(
                row_number=row_number,
                column_name=profile.channels[0].source_column,
                channel_key=profile.channels[0].source_quantity.value,
                error_code="non_increasing_independent",
                error_detail=f"row {row_number}: independent values must be strictly increasing",
                recovery_hint="Order unique independent values without modifying the raw evidence.",
            )
            continue
        if (
            profile.data_schema is TabularDataSchema.SHEAR_RELAXATION
            and normalized
            and point[1] > normalized[-1][1]
        ):
            add_diagnostic(
                row_number=row_number,
                column_name=profile.channels[1].source_column,
                channel_key=profile.channels[1].source_quantity.value,
                error_code="increasing_relaxation_modulus",
                error_detail=f"row {row_number}: shear modulus must be non-increasing",
                recovery_hint="Correct the relaxation response or choose the matching test schema.",
            )
            continue
        coordinate: tuple[float, ...]
        if profile.data_schema is TabularDataSchema.DMA_FREQUENCY_TEMPERATURE_SWEEP:
            if point[0] < 0:
                add_diagnostic(
                    row_number=row_number,
                    column_name=profile.channels[0].source_column,
                    channel_key=QuantityKind.TEMPERATURE.value,
                    error_code="temperature_below_absolute_zero",
                    error_detail=f"row {row_number}: normalized temperature must be at least 0 K",
                    recovery_hint="Correct the temperature value or its declared degC/K unit.",
                )
                continue
            if point[1] <= 0:
                add_diagnostic(
                    row_number=row_number,
                    column_name=profile.channels[1].source_column,
                    channel_key=QuantityKind.FREQUENCY.value,
                    error_code="frequency_not_positive",
                    error_detail=f"row {row_number}: frequency must be greater than 0 Hz",
                    recovery_hint=(
                        "Provide the positive oscillation frequency recorded by the test."
                    ),
                )
                continue
            negative_response = next(
                (index for index, response in enumerate(point[2:], start=2) if response < 0),
                None,
            )
            if negative_response is not None:
                channel = profile.channels[negative_response]
                add_diagnostic(
                    row_number=row_number,
                    column_name=channel.source_column,
                    channel_key=channel.source_quantity.value,
                    error_code="negative_dma_response",
                    error_detail=(
                        f"row {row_number}: {channel.source_quantity.value} must be non-negative"
                    ),
                    recovery_hint="Correct the DMA response value or its declared unit.",
                )
                continue
            coordinate = (point[0], point[1])
        elif profile.data_schema is TabularDataSchema.DMA_TEMPERATURE_SWEEP:
            if point[0] <= 0:
                add_diagnostic(
                    row_number=row_number,
                    column_name=profile.channels[0].source_column,
                    channel_key=QuantityKind.TEMPERATURE.value,
                    error_code="temperature_not_positive_kelvin",
                    error_detail=(
                        f"row {row_number}: normalized temperature must be greater than 0 K"
                    ),
                    recovery_hint="Correct the temperature value or its declared degC/K unit.",
                )
                continue
            negative_response = next(
                (
                    index
                    for index, channel in enumerate(profile.channels[1:], start=1)
                    if channel.source_quantity
                    in {QuantityKind.STORAGE_MODULUS, QuantityKind.LOSS_MODULUS}
                    and point[index] < 0
                ),
                None,
            )
            if negative_response is not None:
                channel = profile.channels[negative_response]
                add_diagnostic(
                    row_number=row_number,
                    column_name=channel.source_column,
                    channel_key=channel.source_quantity.value,
                    error_code="negative_dma_modulus",
                    error_detail=(
                        f"row {row_number}: {channel.source_quantity.value} must be non-negative"
                    ),
                    recovery_hint="Correct the modulus value or its declared unit.",
                )
                continue
            coordinate = (point[0],)
        elif profile.data_schema is TabularDataSchema.FORMING_LIMIT:
            coordinate = (point[0],)
        else:
            coordinate = ()
        if coordinate:
            if coordinate in seen_coordinates:
                add_diagnostic(
                    row_number=row_number,
                    column_name=None,
                    channel_key=(
                        "temperature_frequency"
                        if len(coordinate) == 2
                        else QuantityKind.TEMPERATURE.value
                        if profile.data_schema is TabularDataSchema.DMA_TEMPERATURE_SWEEP
                        else QuantityKind.MINOR_STRAIN.value
                    ),
                    error_code="duplicate_coordinate",
                    error_detail=f"row {row_number}: governed coordinate is duplicated",
                    recovery_hint=(
                        "Remove the duplicate measurement or record a distinct coordinate."
                    ),
                )
                continue
            seen_coordinates.add(coordinate)
        original.append(raw_values)
        normalized.append(point)
        if len(normalized) > MAX_ROWS:
            raise InvalidGovernedImport("source exceeds the 100000-row limit")
    if len(normalized) < 2:
        add_diagnostic(
            row_number=None,
            column_name=None,
            channel_key=None,
            error_code="insufficient_valid_rows",
            error_detail="governed source requires at least two valid data rows",
            recovery_hint="Provide at least two complete, distinct measurements.",
        )
    if diagnostics:
        raise InvalidGovernedImport(
            f"{diagnostic_total} governed import validation error(s); "
            f"first: {diagnostics[0].error_detail}",
            tuple(diagnostics),
        )
    return GovernedTabularEvidence(
        original_rows=tuple(original),
        normalized=NormalizedTabularData(
            columns=tuple(channel.normalized_quantity for channel in profile.channels),
            rows=tuple(normalized),
        ),
        normalization_scales=tuple(scales),
        normalization_offsets=tuple(offsets),
    )


def normalized_parquet_bytes(value: NormalizedTabularData) -> bytes:
    names = tuple(
        f"{quantity.value}_{_NORMALIZED_UNITS[quantity].lower().replace('%', 'pct')}"
        for quantity in value.columns
    )
    table = pa.table(
        {
            name: pa.array((row[index] for row in value.rows), type=pa.float64())
            for index, name in enumerate(names)
        }
    )
    sink = pa.BufferOutputStream()
    _write_parquet(
        table,
        sink,
        compression="zstd",
        version="2.6",
        data_page_version="2.0",
        use_dictionary=False,
        write_statistics=True,
    )
    return cast(bytes, sink.getvalue().to_pybytes())


def normalized_rows_from_parquet(
    value: bytes,
    content: GovernedDatasetContent,
) -> NormalizedTabularData:
    """Decode one exact normalized Artifact under its typed Dataset contract."""

    if content.representation is not GovernedDatasetRepresentation.NORMALIZED:
        raise InvalidGovernedImport("only normalized Dataset Artifacts can be decoded")
    expected_quantities = tuple(channel.normalized_quantity for channel in content.channels)
    expected_names = tuple(
        f"{quantity.value}_{_NORMALIZED_UNITS[quantity].lower().replace('%', 'pct')}"
        for quantity in expected_quantities
    )
    try:
        table = cast(Callable[..., pa.Table], pq.read_table)(pa.BufferReader(value))
    except Exception as error:
        raise InvalidGovernedImport("normalized Dataset Artifact is not valid Parquet") from error
    if (
        tuple(table.column_names) != expected_names
        or table.num_rows != content.row_count
        or table.num_columns != len(expected_names)
    ):
        raise InvalidGovernedImport(
            "normalized Dataset Artifact does not match its immutable schema and row count"
        )
    try:
        columns = tuple(table.column(name).to_pylist() for name in expected_names)
        rows = tuple(tuple(float(item) for item in row) for row in zip(*columns, strict=True))
    except (TypeError, ValueError) as error:
        raise InvalidGovernedImport(
            "normalized Dataset Artifact contains invalid values"
        ) from error
    return NormalizedTabularData(
        columns=expected_quantities,
        rows=rows,
    )

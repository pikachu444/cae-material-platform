"""Typed loader for the checked-in public shear-DMA frequency-sweep reference fixture.

The fixture is deliberately a source-evidence adapter, not a numerical transform.  It validates
the repository manifest, derived file digest, and published column order before either the
acceptance script or CI tests can consume the bytes.
"""

from __future__ import annotations

import csv
import hashlib
import io
import re
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from types import MappingProxyType
from typing import Any, cast

import yaml


class PublicShearDmaFixtureError(ValueError):
    """The public shear-DMA fixture or its provenance manifest is inconsistent."""


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_MD5 = re.compile(r"^[0-9a-f]{32}$")


@dataclass(frozen=True, slots=True)
class PublicShearDmaFixture:
    """Immutable public fixture bytes plus manifest-controlled mapping evidence."""

    source_bytes: bytes
    raw_source_bytes: bytes
    provenance: Mapping[str, Any]
    platform_fixture: Mapping[str, Any]
    source_file: Mapping[str, Any]
    derived_fixture: Mapping[str, Any]
    record: Mapping[str, Any]
    source_columns: tuple[str, ...]
    raw_source_columns: tuple[str, ...]
    channels: tuple[Mapping[str, Any], ...]
    conditions: tuple[Mapping[str, Any], ...]
    row_count: int
    derived_sha256: str


def _mapping(value: object, name: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise PublicShearDmaFixtureError(f"{name} must be a JSON object")
    return cast(Mapping[str, Any], value)


def _text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PublicShearDmaFixtureError(f"{name} must be non-empty text")
    return value


def _mapping_items(value: object, name: str) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(value, list) or not value:
        raise PublicShearDmaFixtureError(f"{name} must be a non-empty JSON array")
    return tuple(_mapping(item, f"{name}[{index}]") for index, item in enumerate(value))


def _decimal_text(value: object, name: str) -> Decimal:
    """Parse one manifest-selected numeric value without changing source precision."""

    if isinstance(value, bool) or value is None:
        raise PublicShearDmaFixtureError(f"{name} must be numeric text")
    try:
        parsed = Decimal(str(value).strip())
    except (InvalidOperation, ValueError) as error:
        raise PublicShearDmaFixtureError(f"{name} must be numeric text") from error
    if not parsed.is_finite():
        raise PublicShearDmaFixtureError(f"{name} must be finite")
    return parsed


def _verify_declared_derivation(
    *,
    raw_rows: tuple[list[str], ...],
    raw_source_columns: tuple[str, ...],
    derived_rows: tuple[dict[str, str | None], ...],
    source_columns: tuple[str, ...],
    derivation: Mapping[str, Any],
    row_count: int,
) -> None:
    """Rebuild the derived view from manifest-selected raw rows and column mappings."""

    mappings = _mapping(derivation.get("column_mappings"), "derivation.column_mappings")
    if set(mappings) != set(source_columns) or len(mappings) != len(source_columns):
        raise PublicShearDmaFixtureError(
            "derivation.column_mappings must cover every derived source column exactly once"
        )
    mapped_columns: dict[str, str] = {}
    for derived_column in source_columns:
        raw_column = _text(
            mappings.get(derived_column),
            f"derivation.column_mappings.{derived_column}",
        )
        if raw_column not in raw_source_columns:
            raise PublicShearDmaFixtureError(
                f"derivation.column_mappings.{derived_column} is not a raw source column"
            )
        mapped_columns[derived_column] = raw_column
    if len(set(mapped_columns.values())) != len(mapped_columns):
        raise PublicShearDmaFixtureError(
            "derivation.column_mappings must not reuse raw source columns"
        )

    selection = _mapping(derivation.get("selection_columns"), "derivation.selection_columns")
    result_column = _text(
        selection.get("result_number"), "derivation.selection_columns.result_number"
    )
    temperature_column = _text(
        selection.get("temperature"), "derivation.selection_columns.temperature"
    )
    if result_column not in raw_source_columns or temperature_column not in raw_source_columns:
        raise PublicShearDmaFixtureError("derivation selection columns are not raw source columns")
    selected_result = _decimal_text(
        derivation.get("selected_result_number"), "derivation.selected_result_number"
    )
    selected_temperature = _decimal_text(
        derivation.get("selected_temperature_c"), "derivation.selected_temperature_c"
    )
    if selected_result != selected_result.to_integral_value():
        raise PublicShearDmaFixtureError("derivation.selected_result_number must be integral")

    selected_rows: list[dict[str, str]] = []
    for row_number, row in enumerate(raw_rows[2:], start=3):
        if not row or all(not value.strip() for value in row):
            continue
        if len(row) != len(raw_source_columns):
            raise PublicShearDmaFixtureError(
                f"raw source row {row_number} has a different column count"
            )
        raw_row = dict(zip(raw_source_columns, row, strict=True))
        if (
            _decimal_text(raw_row[result_column], f"raw row {row_number} result number")
            == selected_result
            and _decimal_text(raw_row[temperature_column], f"raw row {row_number} temperature")
            == selected_temperature
        ):
            selected_rows.append(raw_row)
    if len(selected_rows) != row_count:
        raise PublicShearDmaFixtureError(
            "declared derivation row count does not match selected raw source rows"
        )
    if len(derived_rows) != len(selected_rows):
        raise PublicShearDmaFixtureError("derived fixture row count changed")
    for ordinal, (derived_row, raw_row) in enumerate(zip(derived_rows, selected_rows, strict=True)):
        for derived_column, raw_column in mapped_columns.items():
            if derived_row.get(derived_column) != raw_row[raw_column]:
                raise PublicShearDmaFixtureError(
                    "derived fixture does not match the manifest-selected raw source "
                    f"at row {ordinal} column {derived_column}"
                )


def load_public_shear_dma_fixture(
    path: str | Path,
    manifest_path: str | Path | None = None,
) -> PublicShearDmaFixture:
    """Read one exact fixture and its repository manifest without changing source values/order."""

    fixture_path = Path(path)
    resolved_manifest = (
        Path(manifest_path)
        if manifest_path is not None
        else fixture_path.parent.parent / "manifests" / f"{fixture_path.stem}.yaml"
    )
    try:
        source = fixture_path.read_bytes()
        raw_manifest = yaml.safe_load(resolved_manifest.read_text("utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as error:
        raise PublicShearDmaFixtureError(
            f"cannot read public shear-DMA fixture and manifest at {fixture_path}"
        ) from error
    manifest = _mapping(raw_manifest, "manifest")
    fixture = _mapping(manifest.get("fixture"), "fixture")
    digest = _mapping(fixture.get("digest"), "fixture.digest")
    source_metadata = _mapping(manifest.get("source"), "source")
    derivation = _mapping(manifest.get("derivation"), "derivation")
    record = _mapping(manifest.get("record"), "record")
    platform_fixture = _mapping(manifest.get("platform_fixture"), "platform_fixture")
    _text(
        platform_fixture.get("test_run_performed_at"),
        "platform_fixture.test_run_performed_at",
    )
    if platform_fixture.get("metadata_role") != "deterministic_test_fixture_metadata":
        raise PublicShearDmaFixtureError(
            "platform fixture timestamp must be classified as fixture metadata"
        )
    fixture_manifest_path = _text(fixture.get("path"), "fixture.path")
    derived_manifest_path = _text(
        derivation.get("derived_fixture_path"), "derivation.derived_fixture_path"
    )
    if fixture_manifest_path != derived_manifest_path:
        raise PublicShearDmaFixtureError("derivation.derived_fixture_path must match fixture.path")
    source_file = {
        "name": source_metadata.get("file_name"),
        "data_file_id": source_metadata.get("data_file_id"),
        "download_url": source_metadata.get("download_url"),
        "sha256": source_metadata.get("sha256"),
        "md5": source_metadata.get("md5"),
        "raw_fixture_path": source_metadata.get("raw_fixture_path"),
        "raw_fixture_sha256": source_metadata.get("raw_fixture_sha256"),
        "raw_fixture_md5": source_metadata.get("raw_fixture_md5"),
    }
    derived_fixture = {
        "file_name": Path(fixture_manifest_path).name,
        "path": fixture_manifest_path,
        "columns": manifest.get("governed_channels"),
        "source_columns": derivation.get("source_columns"),
        "conditions": manifest.get("conditions"),
    }

    source_sha256 = _text(source_file["sha256"], "source.sha256")
    source_md5 = _text(source_file["md5"], "source.md5")
    if _SHA256.fullmatch(source_sha256) is None:
        raise PublicShearDmaFixtureError("source_file.sha256 must be lowercase SHA-256")
    if _MD5.fullmatch(source_md5) is None:
        raise PublicShearDmaFixtureError("source.md5 must be lowercase MD5")
    raw_fixture_name = _text(source_file["raw_fixture_path"], "source.raw_fixture_path")
    raw_source_sha256 = _text(source_file["raw_fixture_sha256"], "source.raw_fixture_sha256")
    raw_source_md5 = _text(source_file["raw_fixture_md5"], "source.raw_fixture_md5")
    if _SHA256.fullmatch(raw_source_sha256) is None:
        raise PublicShearDmaFixtureError("source.raw_fixture_sha256 must be lowercase SHA-256")
    if _MD5.fullmatch(raw_source_md5) is None:
        raise PublicShearDmaFixtureError("source.raw_fixture_md5 must be lowercase MD5")
    if raw_source_sha256 != source_sha256 or raw_source_md5 != source_md5:
        raise PublicShearDmaFixtureError(
            "raw source fixture digests must match source publication digests"
        )
    repository_root = resolved_manifest.parent.parent.parent
    raw_fixture_path = Path(raw_fixture_name)
    if not raw_fixture_path.is_absolute():
        raw_fixture_path = repository_root / raw_fixture_path
    try:
        raw_source = raw_fixture_path.read_bytes()
    except OSError as error:
        raise PublicShearDmaFixtureError(
            f"cannot read checked-in raw source fixture at {raw_fixture_path}"
        ) from error
    if hashlib.sha256(raw_source).hexdigest() != raw_source_sha256:
        raise PublicShearDmaFixtureError("raw source fixture SHA-256 changed")
    if hashlib.md5(raw_source).hexdigest() != raw_source_md5:
        raise PublicShearDmaFixtureError("raw source fixture MD5 changed")
    derived_sha256 = hashlib.sha256(source).hexdigest()
    if digest.get("algorithm") != "sha256" or digest.get("value") != derived_sha256:
        raise PublicShearDmaFixtureError("fixture digest does not match its manifest")
    if derived_fixture["file_name"] != fixture_path.name:
        raise PublicShearDmaFixtureError(
            "derived_fixture.file_name does not match the fixture path"
        )
    row_count = derivation.get("rows")
    if not isinstance(row_count, int) or row_count < 3:
        raise PublicShearDmaFixtureError("fixture_derivation.rows must contain at least 3 rows")

    raw_columns = derived_fixture["source_columns"]
    if (
        not isinstance(raw_columns, list)
        or not raw_columns
        or any(not isinstance(value, str) or not value.strip() for value in raw_columns)
    ):
        raise PublicShearDmaFixtureError("derived_fixture.source_columns must be ordered text")
    source_columns = tuple(cast(str, value) for value in raw_columns)
    raw_columns_value = derivation.get("raw_source_columns")
    if (
        not isinstance(raw_columns_value, list)
        or not raw_columns_value
        or any(not isinstance(value, str) or not value.strip() for value in raw_columns_value)
    ):
        raise PublicShearDmaFixtureError("derivation.raw_source_columns must be ordered text")
    raw_source_columns = tuple(cast(str, value) for value in raw_columns_value)
    try:
        raw_rows = tuple(csv.reader(io.StringIO(raw_source.decode("utf-8"))))
    except (UnicodeDecodeError, csv.Error) as error:
        raise PublicShearDmaFixtureError("raw source fixture must be a UTF-8 CSV") from error
    if len(raw_rows) < 2 or tuple(raw_rows[0]) != raw_source_columns:
        raise PublicShearDmaFixtureError("raw source columns changed")
    channels = _mapping_items(derived_fixture["columns"], "governed_channels")
    conditions = _mapping_items(derived_fixture["conditions"], "conditions")
    channel_ordinals = tuple(item.get("ordinal") for item in channels)
    if channel_ordinals != tuple(range(len(channels))):
        raise PublicShearDmaFixtureError("derived fixture channel ordinals must be contiguous")
    channel_columns = tuple(
        _text(item.get("source_column"), "channel.source_column") for item in channels
    )
    if len(set(channel_columns)) != len(channel_columns) or any(
        column not in source_columns for column in channel_columns
    ):
        raise PublicShearDmaFixtureError("derived fixture channels must pin source columns")

    try:
        rows = tuple(csv.DictReader(io.StringIO(source.decode("utf-8"))))
    except (UnicodeDecodeError, csv.Error) as error:
        raise PublicShearDmaFixtureError("derived fixture must be a UTF-8 CSV") from error
    headers = tuple(rows[0].keys()) if rows else ()
    if headers != source_columns or len(rows) != row_count:
        raise PublicShearDmaFixtureError("derived fixture source columns or row count changed")
    _verify_declared_derivation(
        raw_rows=raw_rows,
        raw_source_columns=raw_source_columns,
        derived_rows=rows,
        source_columns=source_columns,
        derivation=derivation,
        row_count=row_count,
    )
    if not all(value.get("source_quantity") for value in channels):
        raise PublicShearDmaFixtureError("every derived channel must declare a quantity")
    # The public manifest is immutable evidence.  Mapping proxies stop a caller from accidentally
    # altering the provenance that is later included in an acceptance report.
    immutable_manifest = MappingProxyType(dict(manifest))
    return PublicShearDmaFixture(
        source_bytes=source,
        raw_source_bytes=raw_source,
        provenance=immutable_manifest,
        platform_fixture=MappingProxyType(dict(platform_fixture)),
        source_file=MappingProxyType(dict(source_file)),
        derived_fixture=MappingProxyType(dict(derived_fixture)),
        record=MappingProxyType(dict(record)),
        source_columns=source_columns,
        raw_source_columns=raw_source_columns,
        channels=tuple(MappingProxyType(dict(item)) for item in channels),
        conditions=tuple(MappingProxyType(dict(item)) for item in conditions),
        row_count=row_count,
        derived_sha256=derived_sha256,
    )

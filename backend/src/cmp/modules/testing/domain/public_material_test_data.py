"""Validated archive-backed public material test data used by regression acceptance.

Source-specific paths, columns, units, and eligibility dispositions belong to repository
manifests.  This module enforces the bounded archive contract and never supplies missing
engineering properties or a production fitting policy.
"""

from __future__ import annotations

import csv
import hashlib
import io
import math
import zipfile
from collections import Counter, defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path
from types import MappingProxyType
from typing import Any, cast

import yaml


class PublicMaterialTestDataError(ValueError):
    """A public reference archive or its manifest is inconsistent."""


SUPPORTED_KINDS = frozenset(
    {
        "shear_dma_frequency_sweep",
        "shear_dma_temperature_ramp",
        "shear_relaxation",
        "arrhenius_summary",
        "tensile",
        "viscoelastic_master_curve",
        "time_temperature_shift",
    }
)


@dataclass(frozen=True, slots=True)
class PublicArchiveMember:
    """One non-directory ZIP member and its manifest-declared disposition."""

    path: str
    size: int
    sha256: str
    disposition: str
    role: str


@dataclass(frozen=True, slots=True)
class PublicFrequencyGroup:
    """One published frequency-sweep result without temperature merging."""

    experiment_id: str
    result_number: str
    temperature_texts: tuple[str, ...]
    row_count: int
    calibration_eligible: bool
    ineligibility_reason: str | None


@dataclass(frozen=True, slots=True)
class PublicFrequencyValidationSpec:
    """Manifest-owned source contract for exact frequency-group eligibility."""

    frequency_group_key: tuple[str, str]
    frequency_columns: Mapping[str, str]
    frequency_units: Mapping[str, str]
    selection_rule: str
    temperature_tolerance: str


# These are the only frequency eligibility semantics implemented by this bounded loader.  They
# are compared with the manifest declaration so a source change cannot silently select a new rule.
FREQUENCY_SELECTION_RULE = (
    "only a complete Result No. group with one exact published temperature text, at least "
    "three points, and strictly increasing positive frequency is calibration-eligible"
)
FREQUENCY_TEMPERATURE_TOLERANCE = "not_defined_no_rows_are_merged"
_FREQUENCY_COLUMN_KEYS = frozenset({"frequency", "storage_modulus", "loss_modulus"})
_FREQUENCY_UNIT_KEYS = frozenset(
    {"frequency", "storage_modulus", "loss_modulus", "temperature"}
)
_COLUMN_MAPPING_FIELDS = frozenset(
    {"column", "quantity", "source_unit", "normalized_unit"}
)


@dataclass(frozen=True, slots=True)
class PublicMaterialExperiment:
    """One manifest-declared member and its validated source rows."""

    id: str
    member: str
    kind: str
    sample: str
    conditions: Mapping[str, str]
    column_mapping: Mapping[str, Mapping[str, str]]
    header: tuple[str, ...]
    units: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]
    sha256: str
    calibration_eligibility: str
    ineligibility_reason: str | None
    export_eligibility: str
    static_property_set: str
    frequency_groups: tuple[PublicFrequencyGroup, ...] = ()

    @property
    def calibration_eligible(self) -> bool:
        if self.calibration_eligibility == "eligible":
            return True
        return any(group.calibration_eligible for group in self.frequency_groups)

    @property
    def export_eligible(self) -> bool:
        return self.export_eligibility == "eligible"


@dataclass(frozen=True, slots=True)
class PublicMaterialTestData:
    """One immutable public dataset archive plus validated experiment members."""

    manifest_path: Path
    archive_path: Path
    archive_sha256: str
    source: Mapping[str, Any]
    member_inventory: tuple[PublicArchiveMember, ...]
    experiments: tuple[PublicMaterialExperiment, ...]
    ignored_members: tuple[str, ...]
    frequency_validation: PublicFrequencyValidationSpec | None = None

    @property
    def eligible_frequency_groups(self) -> tuple[PublicFrequencyGroup, ...]:
        return tuple(
            group
            for experiment in self.experiments
            for group in experiment.frequency_groups
            if group.calibration_eligible
        )


def _mapping(value: object, name: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise PublicMaterialTestDataError(f"{name} must be an object")
    return cast(Mapping[str, Any], value)


def _text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise PublicMaterialTestDataError(f"{name} must be non-empty trimmed text")
    return value


def _integer(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise PublicMaterialTestDataError(f"{name} must be a non-negative integer")
    return value


def _text_list(value: object, name: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise PublicMaterialTestDataError(f"{name} must be an array")
    return tuple(_text(item, f"{name}[{index}]") for index, item in enumerate(value))


def _digest(value: object, name: str) -> str:
    digest = _text(value, name).lower()
    if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
        raise PublicMaterialTestDataError(f"{name} must be a lowercase SHA-256 digest")
    return digest


def _optional_text(value: object, name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or value != value.strip():
        raise PublicMaterialTestDataError(f"{name} must be text or null")
    return value


def _source_cell_list(value: object, name: str) -> tuple[str, ...]:
    """Return exact source cells, including meaningful empty unit/header cells."""

    if not isinstance(value, list):
        raise PublicMaterialTestDataError(f"{name} must be an array")
    cells: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str):
            raise PublicMaterialTestDataError(f"{name}[{index}] must be text")
        cells.append(item)
    return tuple(cells)


def _member_inventory(value: object, name: str) -> tuple[PublicArchiveMember, ...]:
    """Parse the complete source archive inventory, including ignored members."""

    if not isinstance(value, list) or not value:
        raise PublicMaterialTestDataError(f"{name} must be a non-empty array")
    result: list[PublicArchiveMember] = []
    for index, raw_member in enumerate(value):
        member = _mapping(raw_member, f"{name}[{index}]")
        disposition = _text(member.get("disposition"), f"{name}[{index}].disposition")
        if disposition not in {"validated", "ignored"}:
            raise PublicMaterialTestDataError(
                f"{name}[{index}].disposition must be validated or ignored"
            )
        result.append(
            PublicArchiveMember(
                path=_text(member.get("path"), f"{name}[{index}].path"),
                size=_integer(member.get("size"), f"{name}[{index}].size"),
                sha256=_digest(member.get("sha256"), f"{name}[{index}].sha256"),
                disposition=disposition,
                role=_text(member.get("role"), f"{name}[{index}].role"),
            )
        )
    if len({member.path for member in result}) != len(result):
        raise PublicMaterialTestDataError(f"{name} paths must be unique")
    return tuple(result)


def _text_mapping(value: object, name: str, keys: frozenset[str]) -> Mapping[str, str]:
    mapping = _mapping(value, name)
    if set(mapping) != keys:
        raise PublicMaterialTestDataError(
            f"{name} must contain exactly {sorted(keys)}"
        )
    return MappingProxyType(
        {
            key: _text(mapping.get(key), f"{name}.{key}")
            for key in sorted(keys)
        }
    )


def _frequency_validation_spec(
    validation: Mapping[str, Any],
) -> PublicFrequencyValidationSpec | None:
    names = (
        "frequency_group_key",
        "frequency_columns",
        "frequency_units",
        "selection_rule",
        "temperature_tolerance",
    )
    present = [name in validation for name in names]
    if not any(present):
        return None
    if not all(present):
        raise PublicMaterialTestDataError(
            "frequency validation must declare group key, columns, units, selection rule, "
            "and temperature tolerance together"
        )
    group_key = _text_list(validation.get("frequency_group_key"), "frequency_group_key")
    if len(group_key) != 2 or len(set(group_key)) != 2:
        raise PublicMaterialTestDataError(
            "frequency_group_key must contain two distinct source columns"
        )
    selection_rule = _text(validation.get("selection_rule"), "selection_rule")
    if selection_rule != FREQUENCY_SELECTION_RULE:
        raise PublicMaterialTestDataError("selection_rule is not the supported exact-group rule")
    temperature_tolerance = _text(
        validation.get("temperature_tolerance"), "temperature_tolerance"
    )
    if temperature_tolerance != FREQUENCY_TEMPERATURE_TOLERANCE:
        raise PublicMaterialTestDataError(
            "temperature_tolerance must state that no rows are merged"
        )
    frequency_columns = _text_mapping(
        validation.get("frequency_columns"), "frequency_columns", _FREQUENCY_COLUMN_KEYS
    )
    frequency_units = _text_mapping(
        validation.get("frequency_units"), "frequency_units", _FREQUENCY_UNIT_KEYS
    )
    return PublicFrequencyValidationSpec(
        frequency_group_key=(group_key[0], group_key[1]),
        frequency_columns=frequency_columns,
        frequency_units=frequency_units,
        selection_rule=selection_rule,
        temperature_tolerance=temperature_tolerance,
    )


def _unit_key(value: str) -> str:
    """Compare source notation without changing or rewriting the source unit text."""

    normalized = value.strip()
    if normalized.startswith("[") and normalized.endswith("]"):
        normalized = normalized[1:-1]
    return "".join(normalized.casefold().split())


def _validate_frequency_units(
    experiment_id: str,
    header: tuple[str, ...],
    units: tuple[str, ...],
    spec: PublicFrequencyValidationSpec,
) -> None:
    """Require each manifest semantic unit to match the archive's unit row."""

    if len(header) != len(units):
        raise PublicMaterialTestDataError(
            f"experiment {experiment_id} header and source unit rows differ in length"
        )
    for semantic, column in spec.frequency_columns.items():
        index = _column(header, column, experiment_id)
        declared = spec.frequency_units[semantic]
        actual = units[index]
        if _unit_key(actual) != _unit_key(declared):
            raise PublicMaterialTestDataError(
                f"experiment {experiment_id} unit declaration for {column} does not match "
                f"the source unit row"
            )
    temperature_column = spec.frequency_group_key[1]
    temperature_index = _column(header, temperature_column, experiment_id)
    if _unit_key(units[temperature_index]) != _unit_key(spec.frequency_units["temperature"]):
        raise PublicMaterialTestDataError(
            f"experiment {experiment_id} unit declaration for {temperature_column} does not "
            "match the source unit row"
        )


def _finite(value: str, name: str) -> float:
    try:
        result = float(value)
    except ValueError as error:
        raise PublicMaterialTestDataError(f"{name} must be numeric") from error
    if not math.isfinite(result):
        raise PublicMaterialTestDataError(f"{name} must be finite")
    return result


def _column(header: tuple[str, ...], name: str, experiment_id: str) -> int:
    try:
        return header.index(name)
    except ValueError as error:
        raise PublicMaterialTestDataError(
            f"experiment {experiment_id} is missing required column {name}"
        ) from error


def _validate_column_mapping(
    experiment_id: str,
    experiment: Mapping[str, Any],
    header: tuple[str, ...],
    units: tuple[str, ...],
    required: tuple[str, ...],
) -> Mapping[str, str]:
    """Resolve source columns from manifest evidence, never from source-name constants."""

    raw_mapping = experiment.get("column_mapping")
    mapping = _mapping(raw_mapping, f"experiment {experiment_id}.column_mapping")
    resolved: dict[str, str] = {}
    for semantic in required:
        entry = _mapping(
            mapping.get(semantic), f"experiment {experiment_id}.column_mapping.{semantic}"
        )
        column = _text(
            entry.get("column"), f"experiment {experiment_id}.column_mapping.{semantic}.column"
        )
        index = _column(header, column, experiment_id)
        source_unit = entry.get("source_unit")
        if not isinstance(source_unit, str):
            raise PublicMaterialTestDataError(
                f"experiment {experiment_id}.column_mapping.{semantic}.source_unit must be text"
            )
        if _unit_key(units[index]) != _unit_key(source_unit):
            raise PublicMaterialTestDataError(
                f"experiment {experiment_id} source unit for {column} does not match mapping"
            )
        _text(
            entry.get("quantity"),
            f"experiment {experiment_id}.column_mapping.{semantic}.quantity",
        )
        _text(
            entry.get("normalized_unit"),
            f"experiment {experiment_id}.column_mapping.{semantic}.normalized_unit",
        )
        resolved[semantic] = column
    return MappingProxyType(resolved)


def _column_mapping_evidence(
    value: object, name: str
) -> Mapping[str, Mapping[str, str]]:
    raw_mapping = _mapping(value, name)
    if not raw_mapping:
        raise PublicMaterialTestDataError(f"{name} must not be empty")
    result: dict[str, Mapping[str, str]] = {}
    for semantic, raw_entry in raw_mapping.items():
        semantic_name = _text(semantic, f"{name} key")
        entry = _mapping(raw_entry, f"{name}.{semantic_name}")
        if set(entry) != _COLUMN_MAPPING_FIELDS:
            raise PublicMaterialTestDataError(
                f"{name}.{semantic_name} must contain column, quantity, source_unit, "
                "and normalized_unit"
            )
        values: dict[str, str] = {}
        for field in sorted(_COLUMN_MAPPING_FIELDS):
            field_value = entry.get(field)
            if field == "source_unit":
                if not isinstance(field_value, str) or field_value != field_value.strip():
                    raise PublicMaterialTestDataError(
                        f"{name}.{semantic_name}.{field} must be trimmed text"
                    )
                values[field] = field_value
            else:
                values[field] = _text(field_value, f"{name}.{semantic_name}.{field}")
        result[semantic_name] = MappingProxyType(values)
    return MappingProxyType(result)


def _validate_positive_column(
    rows: tuple[tuple[str, ...], ...], index: int, *, experiment_id: str, column: str
) -> None:
    values = [_finite(row[index], f"{experiment_id}.{column}") for row in rows if row[index]]
    if not values or any(value <= 0 for value in values):
        raise PublicMaterialTestDataError(
            f"experiment {experiment_id} requires positive {column} values"
        )


def _validate_finite_column(
    rows: tuple[tuple[str, ...], ...], index: int, *, experiment_id: str, column: str
) -> None:
    values = [_finite(row[index], f"{experiment_id}.{column}") for row in rows if row[index]]
    if not values:
        raise PublicMaterialTestDataError(
            f"experiment {experiment_id} requires finite {column} values"
        )


def _frequency_groups(
    experiment_id: str,
    header: tuple[str, ...],
    units: tuple[str, ...],
    rows: tuple[tuple[str, ...], ...],
    spec: PublicFrequencyValidationSpec,
    column_mapping: Mapping[str, str],
) -> tuple[PublicFrequencyGroup, ...]:
    # Keep the manifest-level validation declaration authoritative as well as the per-member
    # semantic mapping.  A changed declaration must fail closed instead of being ignored because
    # the member mapping happens to still resolve.
    for column in spec.frequency_group_key:
        _column(header, column, experiment_id)
    for column in spec.frequency_columns.values():
        _column(header, column, experiment_id)
    _validate_frequency_units(experiment_id, header, units, spec)
    result_index = _column(header, column_mapping["result_number"], experiment_id)
    temperature_index = _column(header, column_mapping["temperature"], experiment_id)
    frequency_index = _column(header, column_mapping["frequency"], experiment_id)
    storage_index = _column(header, column_mapping["storage_modulus"], experiment_id)
    loss_index = _column(header, column_mapping["loss_modulus"], experiment_id)
    grouped: dict[str, list[tuple[str, ...]]] = defaultdict(list)
    for row in rows:
        grouped[row[result_index]].append(row)
    result: list[PublicFrequencyGroup] = []
    for result_number, group_rows in grouped.items():
        temperatures = tuple(dict.fromkeys(row[temperature_index] for row in group_rows))
        frequencies = [
            _finite(row[frequency_index], f"{experiment_id}.Frequency") for row in group_rows
        ]
        storage = [
            _finite(row[storage_index], f"{experiment_id}.Storage Modulus") for row in group_rows
        ]
        loss = [_finite(row[loss_index], f"{experiment_id}.Loss Modulus") for row in group_rows]
        reason: str | None = None
        if len(group_rows) < 3:
            reason = "fewer_than_three_points"
        elif len(temperatures) != 1:
            reason = "published_temperature_text_varies_within_result"
        elif any(value <= 0 for value in frequencies + storage + loss):
            reason = "nonpositive_frequency_or_modulus"
        elif any(right <= left for left, right in pairwise(frequencies)):
            reason = "frequency_not_strictly_increasing"
        result.append(
            PublicFrequencyGroup(
                experiment_id=experiment_id,
                result_number=result_number,
                temperature_texts=temperatures,
                row_count=len(group_rows),
                calibration_eligible=reason is None,
                ineligibility_reason=reason,
            )
        )
    return tuple(result)


def _validate_kind(
    experiment_id: str,
    kind: str,
    experiment: Mapping[str, Any],
    header: tuple[str, ...],
    units: tuple[str, ...],
    rows: tuple[tuple[str, ...], ...],
    frequency_validation: PublicFrequencyValidationSpec | None,
) -> tuple[PublicFrequencyGroup, ...]:
    if kind == "shear_dma_frequency_sweep":
        if frequency_validation is None:
            raise PublicMaterialTestDataError(
                "frequency-sweep experiments require a manifest frequency validation spec"
            )
        columns = _validate_column_mapping(
            experiment_id,
            experiment,
            header,
            units,
            ("result_number", "temperature", "frequency", "storage_modulus", "loss_modulus"),
        )
        return _frequency_groups(
            experiment_id, header, units, rows, frequency_validation, columns
        )
    if kind == "shear_dma_temperature_ramp":
        columns = _validate_column_mapping(
            experiment_id,
            experiment,
            header,
            units,
            ("temperature", "storage_modulus", "tan_delta"),
        )
        _validate_positive_column(
            rows,
            _column(header, columns["storage_modulus"], experiment_id),
            experiment_id=experiment_id,
            column=columns["storage_modulus"],
        )
        _validate_positive_column(
            rows,
            _column(header, columns["temperature"], experiment_id),
            experiment_id=experiment_id,
            column=columns["temperature"],
        )
        return ()
    if kind == "shear_relaxation":
        columns = _validate_column_mapping(
            experiment_id, experiment, header, units, ("time", "modulus")
        )
        time_index = _column(header, columns["time"], experiment_id)
        ratio_index = _column(header, columns["modulus"], experiment_id)
        pairs = [row for row in rows if row[time_index] and row[ratio_index]]
        _validate_positive_column(
            tuple(pairs), time_index, experiment_id=experiment_id, column=columns["time"]
        )
        _validate_finite_column(
            tuple(pairs), ratio_index, experiment_id=experiment_id, column=columns["modulus"]
        )
        times = [_finite(row[time_index], f"{experiment_id}.{columns['time']}") for row in pairs]
        if any(right <= left for left, right in pairwise(times)):
            raise PublicMaterialTestDataError(
                f"experiment {experiment_id} {columns['time']} must be strictly increasing"
            )
        return ()
    if kind == "arrhenius_summary":
        columns = _validate_column_mapping(
            experiment_id, experiment, header, units, ("inverse_temperature", "log_time")
        )
        inverse_temperature_index = _column(
            header, columns["inverse_temperature"], experiment_id
        )
        log_time_index = _column(header, columns["log_time"], experiment_id)
        _validate_positive_column(
            rows,
            inverse_temperature_index,
            experiment_id=experiment_id,
            column=columns["inverse_temperature"],
        )
        if not any(row[log_time_index] for row in rows):
            raise PublicMaterialTestDataError(
                f"experiment {experiment_id} has no {columns['log_time']}"
            )
        for row in rows:
            if row[log_time_index]:
                _finite(row[log_time_index], f"{experiment_id}.{columns['log_time']}")
        return ()
    if kind == "tensile":
        _validate_column_mapping(
            experiment_id,
            experiment,
            header,
            units,
            tuple(f"column_{index}" for index in range(len(header))),
        )
        for row_number, row in enumerate(rows, start=1):
            for column_number, value in enumerate(row):
                if value:
                    _finite(value, f"{experiment_id}[{row_number},{column_number}]")
        return ()
    if kind in {"viscoelastic_master_curve", "time_temperature_shift"}:
        _validate_column_mapping(
            experiment_id,
            experiment,
            header,
            units,
            tuple(f"column_{index}" for index in range(len(header))),
        )
        for row_number, row in enumerate(rows, start=1):
            if not any(value and _finite(value, f"{experiment_id}[{row_number}]") for value in row):
                raise PublicMaterialTestDataError(
                    f"experiment {experiment_id} row {row_number} has no numeric source value"
                )
        return ()
    raise PublicMaterialTestDataError(f"unsupported experiment kind {kind}")


def load_public_material_test_data_manifest(
    manifest_path: str | Path,
) -> PublicMaterialTestData:
    """Load and validate one public non-production archive from its exact manifest."""

    resolved_manifest = Path(manifest_path)
    try:
        document = _mapping(
            yaml.safe_load(resolved_manifest.read_text(encoding="utf-8")), "manifest"
        )
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as error:
        raise PublicMaterialTestDataError(
            f"cannot read public material test-data manifest {resolved_manifest}"
        ) from error
    if document.get("schema_version") != "1.0":
        raise PublicMaterialTestDataError("unsupported public test-data manifest version")
    if (
        document.get("classification") != "public_reference_non_production"
        or document.get("non_production") is not True
    ):
        raise PublicMaterialTestDataError(
            "public test data must remain public_reference_non_production"
        )
    source = _mapping(document.get("source"), "source")
    for key in ("dataset_title", "doi", "version", "landing_page", "license"):
        _text(source.get(key), f"source.{key}")
    archive = _mapping(document.get("archive"), "archive")
    archive_relative = Path(_text(archive.get("path"), "archive.path"))
    repository_root = resolved_manifest.parent.parent.parent
    archive_path = (
        archive_relative if archive_relative.is_absolute() else repository_root / archive_relative
    )
    try:
        archive_bytes = archive_path.read_bytes()
    except OSError as error:
        raise PublicMaterialTestDataError(f"cannot read public archive {archive_path}") from error
    archive_sha256 = hashlib.sha256(archive_bytes).hexdigest()
    if archive_sha256 != _digest(archive.get("sha256"), "archive.sha256"):
        raise PublicMaterialTestDataError("public archive SHA-256 changed")
    if archive.get("md5") is not None and hashlib.md5(archive_bytes).hexdigest() != _text(
        archive.get("md5"), "archive.md5"
    ):
        raise PublicMaterialTestDataError("public archive MD5 changed")
    ignored_members = _text_list(archive.get("ignored_members"), "archive.ignored_members")
    raw_experiments = document.get("experiments")
    if not isinstance(raw_experiments, list) or not raw_experiments:
        raise PublicMaterialTestDataError("experiments must be a non-empty array")
    validation = _mapping(document.get("validation"), "validation")
    frequency_validation = _frequency_validation_spec(validation)
    member_inventory = _member_inventory(
        archive.get("member_inventory"), "archive.member_inventory"
    )
    expected_experiments = _integer(
        validation.get("expected_experiment_count"), "validation.expected_experiment_count"
    )
    if len(raw_experiments) != expected_experiments:
        raise PublicMaterialTestDataError("manifest experiment count changed")
    experiments: list[PublicMaterialExperiment] = []
    try:
        bundle = zipfile.ZipFile(io.BytesIO(archive_bytes))
    except zipfile.BadZipFile as error:
        raise PublicMaterialTestDataError(
            f"public archive is not a readable ZIP: {archive_path}"
        ) from error
    with bundle:
        archive_members = tuple(item.filename for item in bundle.infolist() if not item.is_dir())
        if len(archive_members) != _integer(
            archive.get("expected_file_count"), "archive.expected_file_count"
        ):
            raise PublicMaterialTestDataError("public archive file count changed")
        inventory_paths = tuple(item.path for item in member_inventory)
        if inventory_paths != archive_members:
            raise PublicMaterialTestDataError(
                "archive member inventory does not match the ZIP member order"
            )
        for item in member_inventory:
            member_bytes = bundle.read(item.path)
            if len(member_bytes) != item.size:
                raise PublicMaterialTestDataError(
                    f"public archive member size changed: {item.path}"
                )
            if hashlib.sha256(member_bytes).hexdigest() != item.sha256:
                raise PublicMaterialTestDataError(
                    f"public archive member inventory digest changed: {item.path}"
                )
        declared_members: list[str] = []
        declared_ids: list[str] = []
        for ordinal, raw_experiment in enumerate(raw_experiments):
            experiment = _mapping(raw_experiment, f"experiments[{ordinal}]")
            experiment_id = _text(experiment.get("id"), f"experiments[{ordinal}].id")
            member = _text(experiment.get("member"), f"experiments[{ordinal}].member")
            kind = _text(experiment.get("kind"), f"experiments[{ordinal}].kind")
            if kind not in SUPPORTED_KINDS:
                raise PublicMaterialTestDataError(f"unsupported experiment kind {kind}")
            declared_ids.append(experiment_id)
            declared_members.append(member)
            if member not in archive_members:
                raise PublicMaterialTestDataError(f"public archive member is missing: {member}")
            member_bytes = bundle.read(member)
            member_sha256 = hashlib.sha256(member_bytes).hexdigest()
            if member_sha256 != _digest(
                experiment.get("sha256"), f"experiments[{ordinal}].sha256"
            ):
                raise PublicMaterialTestDataError(
                    f"public archive member SHA-256 changed: {member}"
                )
            encoding = _text(experiment.get("encoding"), f"experiments[{ordinal}].encoding")
            try:
                parsed = tuple(
                    tuple(row)
                    for row in csv.reader(io.StringIO(member_bytes.decode(encoding)))
                    if any(value.strip() for value in row)
                )
            except (UnicodeDecodeError, LookupError, csv.Error) as error:
                raise PublicMaterialTestDataError(
                    f"cannot decode public archive member {member}"
                ) from error
            if len(parsed) < 3:
                raise PublicMaterialTestDataError(
                    f"public archive member has no source rows: {member}"
                )
            expected_header = _source_cell_list(
                experiment.get("expected_header"), f"experiments[{ordinal}].expected_header"
            )
            expected_units = _source_cell_list(
                experiment.get("expected_units"), f"experiments[{ordinal}].expected_units"
            )
            if parsed[0] != expected_header or parsed[1] != expected_units:
                raise PublicMaterialTestDataError(
                    f"public archive member header or units changed: {member}"
                )
            rows = parsed[2:]
            if len(rows) != _integer(
                experiment.get("expected_data_rows"),
                f"experiments[{ordinal}].expected_data_rows",
            ):
                raise PublicMaterialTestDataError(
                    f"public archive member row count changed: {member}"
                )
            if any(len(row) != len(expected_header) for row in rows):
                raise PublicMaterialTestDataError(
                    f"public archive member column count changed: {member}"
                )
            conditions = _mapping(experiment.get("conditions", {}), "experiment.conditions")
            condition_text = {
                _text(key, "condition key"): _text(value, f"condition {key}")
                for key, value in conditions.items()
            }
            column_mapping = _column_mapping_evidence(
                experiment.get("column_mapping"),
                f"experiments[{ordinal}].column_mapping",
            )
            eligibility = _text(
                experiment.get("calibration_eligibility"),
                f"experiments[{ordinal}].calibration_eligibility",
            )
            reason_value = experiment.get("ineligibility_reason")
            reason = None if reason_value is None else _text(reason_value, "ineligibility_reason")
            frequency_groups = _validate_kind(
                experiment_id,
                kind,
                experiment,
                expected_header,
                expected_units,
                rows,
                frequency_validation,
            )
            static_property_set = _text(
                experiment.get("static_property_set"), "static_property_set"
            )
            export_eligibility = _text(experiment.get("export_eligibility"), "export_eligibility")
            if (
                static_property_set != "absent"
                or export_eligibility != "blocked_missing_static_property_set"
            ):
                raise PublicMaterialTestDataError(
                    "public experimental fixtures cannot fabricate a static Property Set"
                )
            experiments.append(
                PublicMaterialExperiment(
                    id=experiment_id,
                    member=member,
                    kind=kind,
                    sample=_text(experiment.get("sample"), "experiment.sample"),
                    conditions=MappingProxyType(condition_text),
                    column_mapping=column_mapping,
                    header=expected_header,
                    units=expected_units,
                    rows=rows,
                    sha256=member_sha256,
                    calibration_eligibility=eligibility,
                    ineligibility_reason=reason,
                    export_eligibility=export_eligibility,
                    static_property_set=static_property_set,
                    frequency_groups=frequency_groups,
                )
            )
        if (
            len(set(declared_ids)) != len(declared_ids)
            or len(set(declared_members)) != len(declared_members)
            or len(set(ignored_members)) != len(ignored_members)
        ):
            raise PublicMaterialTestDataError(
                "experiment ids and all declared archive members must be unique"
            )
        if set(declared_members) & set(ignored_members):
            raise PublicMaterialTestDataError(
                "validated and ignored public archive members must be disjoint"
            )
        if set(declared_members) | set(ignored_members) != set(archive_members):
            raise PublicMaterialTestDataError(
                "manifest must classify every public archive member exactly once"
            )
        inventory_validated = {
            item.path for item in member_inventory if item.disposition == "validated"
        }
        inventory_ignored = {
            item.path for item in member_inventory if item.disposition == "ignored"
        }
        if inventory_validated != set(declared_members) or inventory_ignored != set(
            ignored_members
        ):
            raise PublicMaterialTestDataError(
                "archive member inventory dispositions do not match experiment declarations"
            )
    if len(experiments) != _integer(
        archive.get("validated_member_count"), "archive.validated_member_count"
    ):
        raise PublicMaterialTestDataError("validated public member count changed")
    expected_kind_counts = validation.get("expected_kind_counts")
    if expected_kind_counts is not None:
        actual = Counter(item.kind for item in experiments)
        expected = {
            _text(key, "expected kind"): _integer(value, f"expected kind {key}")
            for key, value in _mapping(
                expected_kind_counts, "validation.expected_kind_counts"
            ).items()
        }
        if actual != expected:
            raise PublicMaterialTestDataError("public experiment kind counts changed")
    result = PublicMaterialTestData(
        manifest_path=resolved_manifest,
        archive_path=archive_path,
        archive_sha256=archive_sha256,
        source=MappingProxyType(
            {
                key: tuple(value) if isinstance(value, list) else value
                for key, value in source.items()
            }
        ),
        member_inventory=member_inventory,
        experiments=tuple(experiments),
        ignored_members=ignored_members,
        frequency_validation=frequency_validation,
    )
    expected_groups = validation.get("expected_exact_temperature_frequency_group_count")
    if expected_groups is not None and len(result.eligible_frequency_groups) != _integer(
        expected_groups, "validation.expected_exact_temperature_frequency_group_count"
    ):
        raise PublicMaterialTestDataError("eligible exact-temperature frequency groups changed")
    expected_eligible = validation.get("expected_calibration_eligible_count")
    if expected_eligible is not None and sum(
        item.calibration_eligible for item in result.experiments
    ) != _integer(expected_eligible, "validation.expected_calibration_eligible_count"):
        raise PublicMaterialTestDataError("public calibration eligibility count changed")
    return result


def discover_public_material_test_data_manifests(
    repository_root: str | Path,
) -> tuple[Path, ...]:
    """Find public archive manifests deterministically without naming a dataset in code."""

    root = Path(repository_root)
    manifest_root = root / "fixtures" / "manifests"
    candidates: list[Path] = []
    for path in sorted(manifest_root.glob("*.yaml")):
        try:
            document = _mapping(yaml.safe_load(path.read_text(encoding="utf-8")), "manifest")
        except (OSError, UnicodeDecodeError, yaml.YAMLError, PublicMaterialTestDataError):
            continue
        archive = document.get("archive")
        if (
            document.get("classification") == "public_reference_non_production"
            and document.get("non_production") is True
            and isinstance(archive, dict)
            and "member_inventory" in archive
        ):
            candidates.append(path)
    return tuple(candidates)

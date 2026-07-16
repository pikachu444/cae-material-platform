"""Typed immutable Bulk Export Selection and deterministic ZIP assembly."""

from __future__ import annotations

import hashlib
import io
import json
import re
import zipfile
from dataclasses import dataclass
from enum import StrEnum
from pathlib import PurePosixPath
from typing import Any
from uuid import UUID

from cmp.modules.identity_access.domain.authorization import DataClassification

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)


class BulkExportError(Exception):
    """Base error for the bounded Bulk Export workflow."""


class InvalidBulkExport(BulkExportError, ValueError):
    """The selection or generated archive violates the explicit contract."""


class BulkExportNotFound(BulkExportError):
    """A requested Selection, Job, Bundle, or exact source is not visible."""


class BulkExportConflict(BulkExportError):
    """The immutable source changed or a job transition is invalid."""


class BulkExportLimitExceeded(BulkExportError):
    """The selected component count or byte size exceeds policy."""


class ExportMemberKind(StrEnum):
    RAW_ORIGINAL = "raw_original"
    DATASET_PARQUET = "dataset_parquet"
    DATASET_CSV = "dataset_csv"
    MODEL_IR_JSON = "model_ir_json"
    MODEL_IR_SCHEMA = "model_ir_schema"
    SOLVER_MAPPING_REPORT = "solver_mapping_report"
    SOLVER_CARD_NATIVE = "solver_card_native"


class BulkExportJobState(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    RECONCILIATION_REQUIRED = "reconciliation_required"
    RECONCILING = "reconciling"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


_CLASSIFICATION_RANK = {
    DataClassification.INTERNAL: 0,
    DataClassification.CONFIDENTIAL: 1,
    DataClassification.RESTRICTED: 2,
    DataClassification.EXPORT_CONTROLLED: 3,
}


def maximum_classification(
    values: tuple[DataClassification, ...],
) -> DataClassification:
    if not values:
        raise InvalidBulkExport("at least one included component is required")
    return max(values, key=_CLASSIFICATION_RANK.__getitem__)


def canonical_json_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _nonzero(name: str, value: UUID | None) -> None:
    if value is not None and value.int == 0:
        raise InvalidBulkExport(f"{name} must be non-zero")


def _archive_path(value: str) -> None:
    if not value or value != value.strip() or len(value) > 512 or "\\" in value:
        raise InvalidBulkExport("archive_path must be a trimmed POSIX path")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or value.endswith("/"):
        raise InvalidBulkExport("archive_path must stay inside the bundle root")
    if path.parts[0] in {"manifest.json", "checksums.sha256", "README.md"}:
        raise InvalidBulkExport("archive_path collides with a reserved bundle entry")


@dataclass(frozen=True, slots=True)
class ExportSourceRef:
    kind: ExportMemberKind
    raw_asset_id: UUID | None = None
    artifact_id: UUID | None = None
    dataset_id: UUID | None = None
    dataset_revision_id: UUID | None = None
    material_model_id: UUID | None = None
    material_model_revision_id: UUID | None = None
    solver_card_id: UUID | None = None
    solver_card_revision_id: UUID | None = None

    def __post_init__(self) -> None:
        for name, value in (
            ("raw_asset_id", self.raw_asset_id),
            ("artifact_id", self.artifact_id),
            ("dataset_id", self.dataset_id),
            ("dataset_revision_id", self.dataset_revision_id),
            ("material_model_id", self.material_model_id),
            ("material_model_revision_id", self.material_model_revision_id),
            ("solver_card_id", self.solver_card_id),
            ("solver_card_revision_id", self.solver_card_revision_id),
        ):
            _nonzero(name, value)
        raw = self.raw_asset_id is not None and self.artifact_id is not None
        dataset = self.dataset_id is not None and self.dataset_revision_id is not None
        model = self.material_model_id is not None and self.material_model_revision_id is not None
        card = self.solver_card_id is not None and self.solver_card_revision_id is not None
        valid = {
            ExportMemberKind.RAW_ORIGINAL: raw and not dataset and not model and not card,
            ExportMemberKind.DATASET_PARQUET: dataset
            and self.artifact_id is not None
            and not raw
            and not model
            and not card,
            ExportMemberKind.DATASET_CSV: dataset
            and self.artifact_id is not None
            and not raw
            and not model
            and not card,
            ExportMemberKind.MODEL_IR_JSON: model and not raw and not dataset and not card,
            ExportMemberKind.MODEL_IR_SCHEMA: model and not raw and not dataset and not card,
            ExportMemberKind.SOLVER_MAPPING_REPORT: card and not raw and not dataset and not model,
            ExportMemberKind.SOLVER_CARD_NATIVE: card and not raw and not dataset and not model,
        }[self.kind]
        if not valid:
            raise InvalidBulkExport(f"{self.kind.value} has an invalid typed source reference")

    def canonical(self) -> dict[str, str | None]:
        return {
            "kind": self.kind.value,
            "raw_asset_id": str(self.raw_asset_id) if self.raw_asset_id else None,
            "artifact_id": str(self.artifact_id) if self.artifact_id else None,
            "dataset_id": str(self.dataset_id) if self.dataset_id else None,
            "dataset_revision_id": (
                str(self.dataset_revision_id) if self.dataset_revision_id else None
            ),
            "material_model_id": (str(self.material_model_id) if self.material_model_id else None),
            "material_model_revision_id": (
                str(self.material_model_revision_id) if self.material_model_revision_id else None
            ),
            "solver_card_id": str(self.solver_card_id) if self.solver_card_id else None,
            "solver_card_revision_id": (
                str(self.solver_card_revision_id) if self.solver_card_revision_id else None
            ),
        }


@dataclass(frozen=True, slots=True)
class ExportSelectionMember:
    ordinal: int
    source: ExportSourceRef
    archive_path: str
    source_sha256: str
    source_size_bytes: int
    media_type: str
    classification: DataClassification
    label: str

    def __post_init__(self) -> None:
        if not 1 <= self.ordinal <= 1000:
            raise InvalidBulkExport("member ordinal must be between 1 and 1000")
        _archive_path(self.archive_path)
        if _SHA256.fullmatch(self.source_sha256) is None:
            raise InvalidBulkExport("source_sha256 must be lowercase SHA-256 hex")
        if self.source_size_bytes < 0:
            raise InvalidBulkExport("source_size_bytes cannot be negative")
        if not self.media_type or len(self.media_type) > 255:
            raise InvalidBulkExport("media_type must contain 1..255 characters")
        if not self.label or self.label != self.label.strip() or len(self.label) > 255:
            raise InvalidBulkExport("label must be trimmed and contain 1..255 characters")

    def canonical(self) -> dict[str, Any]:
        return {
            "ordinal": self.ordinal,
            "source": self.source.canonical(),
            "archive_path": self.archive_path,
            "source_sha256": self.source_sha256,
            "source_size_bytes": self.source_size_bytes,
            "media_type": self.media_type,
            "classification": self.classification.value,
            "label": self.label,
        }


@dataclass(frozen=True, slots=True)
class ExportSelectionOmission:
    ordinal: int
    source: ExportSourceRef
    reason_code: str
    reason: str

    def __post_init__(self) -> None:
        if not 1 <= self.ordinal <= 1000:
            raise InvalidBulkExport("omission ordinal must be between 1 and 1000")
        for name, value, maximum in (
            ("reason_code", self.reason_code, 80),
            ("reason", self.reason, 1000),
        ):
            if not value or value != value.strip() or len(value) > maximum:
                raise InvalidBulkExport(f"{name} must be trimmed")

    def canonical(self) -> dict[str, Any]:
        return {
            "ordinal": self.ordinal,
            "source": self.source.canonical(),
            "reason_code": self.reason_code,
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class ExportSelectionContent:
    selection_label: str
    members: tuple[ExportSelectionMember, ...]
    omissions: tuple[ExportSelectionOmission, ...]

    def __post_init__(self) -> None:
        if (
            not self.selection_label
            or self.selection_label != self.selection_label.strip()
            or len(self.selection_label) > 160
        ):
            raise InvalidBulkExport("selection_label must be trimmed")
        if not self.members:
            raise InvalidBulkExport("at least one export member is required")
        all_ordinals = tuple(member.ordinal for member in self.members) + tuple(
            omission.ordinal for omission in self.omissions
        )
        if len(all_ordinals) > 1000 or len(set(all_ordinals)) != len(all_ordinals):
            raise InvalidBulkExport("selection ordinals must be unique and at most 1000")
        paths = tuple(member.archive_path for member in self.members)
        if len(set(paths)) != len(paths):
            raise InvalidBulkExport("archive_path values must be unique")

    @property
    def classification(self) -> DataClassification:
        return maximum_classification(tuple(member.classification for member in self.members))

    @property
    def expected_size_bytes(self) -> int:
        return sum(member.source_size_bytes for member in self.members)

    def canonical(self) -> dict[str, Any]:
        return {
            "selection_label": self.selection_label,
            "members": [member.canonical() for member in self.members],
            "omissions": [omission.canonical() for omission in self.omissions],
        }

    @property
    def digest(self) -> str:
        return sha256_bytes(canonical_json_bytes(self.canonical()))


@dataclass(frozen=True, slots=True)
class ResolvedBundleFile:
    member: ExportSelectionMember
    value: bytes

    def __post_init__(self) -> None:
        if sha256_bytes(self.value) != self.member.source_sha256:
            raise BulkExportConflict(f"resolved bytes changed for {self.member.archive_path}")
        if len(self.value) != self.member.source_size_bytes:
            raise BulkExportConflict(f"resolved byte size changed for {self.member.archive_path}")


@dataclass(frozen=True, slots=True)
class BuiltBulkExportBundle:
    archive: bytes
    archive_sha256: str
    manifest: bytes
    manifest_sha256: str
    checksums: bytes

    @property
    def evidence(self) -> BulkExportArchiveEvidence:
        return BulkExportArchiveEvidence(
            archive_sha256=self.archive_sha256,
            archive_size_bytes=len(self.archive),
            manifest_sha256=self.manifest_sha256,
        )


@dataclass(frozen=True, slots=True)
class BulkExportArchiveEvidence:
    archive_sha256: str
    archive_size_bytes: int
    manifest_sha256: str

    def __post_init__(self) -> None:
        if _SHA256.fullmatch(self.archive_sha256) is None:
            raise InvalidBulkExport("archive_sha256 must be lowercase SHA-256")
        if _SHA256.fullmatch(self.manifest_sha256) is None:
            raise InvalidBulkExport("manifest_sha256 must be lowercase SHA-256")
        if not 1 <= self.archive_size_bytes <= 5 * 1024 * 1024 * 1024:
            raise InvalidBulkExport("archive_size_bytes is outside the Bundle limit")


@dataclass(frozen=True, slots=True)
class BundleControlFiles:
    manifest: bytes
    manifest_sha256: str
    checksums: bytes
    readme: bytes

    def archive_entries(self) -> dict[str, bytes]:
        return {
            "README.md": self.readme,
            "checksums.sha256": self.checksums,
            "manifest.json": self.manifest,
        }


def deterministic_zip_info(path: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(path, date_time=_ZIP_TIMESTAMP)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = 0o100644 << 16
    info.flag_bits = 0
    return info


def build_bundle_control_files(
    *,
    selection_id: UUID,
    selection_revision_id: UUID,
    content: ExportSelectionContent,
) -> BundleControlFiles:
    component_entries = [
        {
            **member.canonical(),
            "bundle_sha256": member.source_sha256,
            "bundle_size_bytes": member.source_size_bytes,
            "status": "included",
        }
        for member in content.members
    ]
    manifest_document = {
        "schema": "urn:cmp:exporting:bulk-bundle-manifest:1.0.0",
        "selection_id": str(selection_id),
        "selection_revision_id": str(selection_revision_id),
        "selection_digest": content.digest,
        "classification": content.classification.value,
        "components": component_entries,
        "omissions": [omission.canonical() for omission in content.omissions],
        "determinism": {
            "ordering": "lexicographic_path",
            "zip_timestamp": "1980-01-01T00:00:00Z",
            "permissions": "0644",
        },
    }
    manifest = canonical_json_bytes(manifest_document)
    readme = (
        b"# CAE Material Platform Bulk Export Bundle\n\n"
        b"This archive is an authorized transfer, not an approved Release.\n"
        b"Verify every line in checksums.sha256 before use. Exact source identities, "
        b"revisions, classifications and omissions are recorded in manifest.json.\n"
    )
    checksummed = {
        **{member.archive_path: member.source_sha256 for member in content.members},
        "README.md": sha256_bytes(readme),
        "manifest.json": sha256_bytes(manifest),
    }
    checksums = "".join(
        f"{digest}  {path}\n" for path, digest in sorted(checksummed.items())
    ).encode("utf-8")
    return BundleControlFiles(
        manifest=manifest,
        manifest_sha256=sha256_bytes(manifest),
        checksums=checksums,
        readme=readme,
    )


def build_deterministic_bundle(
    *,
    selection_id: UUID,
    selection_revision_id: UUID,
    content: ExportSelectionContent,
    files: tuple[ResolvedBundleFile, ...],
) -> BuiltBulkExportBundle:
    if tuple(file.member for file in files) != content.members:
        raise InvalidBulkExport("resolved files must follow immutable member order")
    archive_entries: dict[str, bytes] = {}
    for resolved in files:
        member = resolved.member
        archive_entries[member.archive_path] = resolved.value
    control = build_bundle_control_files(
        selection_id=selection_id,
        selection_revision_id=selection_revision_id,
        content=content,
    )
    archive_entries.update(control.archive_entries())
    output = io.BytesIO()
    with zipfile.ZipFile(
        output, mode="w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as bundle:
        for path, value in sorted(archive_entries.items()):
            bundle.writestr(deterministic_zip_info(path), value)
    archive = output.getvalue()
    return BuiltBulkExportBundle(
        archive,
        sha256_bytes(archive),
        control.manifest,
        control.manifest_sha256,
        control.checksums,
    )

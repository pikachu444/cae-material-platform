from __future__ import annotations

import hashlib
import io
import json
import zipfile
from dataclasses import replace
from uuid import UUID

import pytest
from cmp.modules.exporting.domain.bulk_bundle import (
    BulkExportConflict,
    ExportMemberKind,
    ExportSelectionContent,
    ExportSelectionMember,
    ExportSourceRef,
    InvalidBulkExport,
    ResolvedBundleFile,
    build_deterministic_bundle,
)
from cmp.modules.identity_access.domain.authorization import DataClassification


def _id(value: int) -> UUID:
    return UUID(int=value)


def _member(
    ordinal: int,
    *,
    path: str,
    value: bytes,
    classification: DataClassification = DataClassification.INTERNAL,
) -> ExportSelectionMember:
    return ExportSelectionMember(
        ordinal=ordinal,
        source=ExportSourceRef(
            ExportMemberKind.MODEL_IR_JSON,
            material_model_id=_id(10 + ordinal),
            material_model_revision_id=_id(20 + ordinal),
        ),
        archive_path=path,
        source_sha256=hashlib.sha256(value).hexdigest(),
        source_size_bytes=len(value),
        media_type="application/json",
        classification=classification,
        label=f"Model IR {ordinal}",
    )


def test_bundle_is_byte_deterministic_and_self_verifying() -> None:
    first_value = b'{"model":"elastic"}\n'
    second_value = b'{"model":"plastic"}\n'
    first = _member(1, path="models/a/ir.json", value=first_value)
    second = _member(
        2,
        path="models/b/ir.json",
        value=second_value,
        classification=DataClassification.CONFIDENTIAL,
    )
    content = ExportSelectionContent("Two exact model revisions", (first, second), ())
    files = (
        ResolvedBundleFile(first, first_value),
        ResolvedBundleFile(second, second_value),
    )

    one = build_deterministic_bundle(
        selection_id=_id(1),
        selection_revision_id=_id(2),
        content=content,
        files=files,
    )
    two = build_deterministic_bundle(
        selection_id=_id(1),
        selection_revision_id=_id(2),
        content=content,
        files=files,
    )

    assert one.archive == two.archive
    assert one.archive_sha256 == hashlib.sha256(one.archive).hexdigest()
    with zipfile.ZipFile(io.BytesIO(one.archive)) as archive:
        assert archive.namelist() == sorted(archive.namelist())
        assert "README.txt" in archive.namelist()
        assert all(item.date_time == (1980, 1, 1, 0, 0, 0) for item in archive.infolist())
        manifest = json.loads(archive.read("manifest.json"))
        assert manifest["classification"] == "confidential"
        assert [item["archive_path"] for item in manifest["components"]] == [
            "models/a/ir.json",
            "models/b/ir.json",
        ]
        for line in archive.read("checksums.sha256").decode().splitlines():
            digest, path = line.split("  ", 1)
            assert hashlib.sha256(archive.read(path)).hexdigest() == digest


def test_selection_rejects_path_traversal_duplicates_and_reserved_names() -> None:
    value = b"{}\n"
    member = _member(1, path="models/a/ir.json", value=value)
    with pytest.raises(InvalidBulkExport, match="bundle root"):
        replace(member, archive_path="../outside.json")
    with pytest.raises(InvalidBulkExport, match="reserved"):
        replace(member, archive_path="manifest.json")
    with pytest.raises(InvalidBulkExport, match="reserved"):
        replace(member, archive_path="README.txt")
    duplicate = _member(2, path=member.archive_path, value=value)
    with pytest.raises(InvalidBulkExport, match="archive_path"):
        ExportSelectionContent("Duplicate", (member, duplicate), ())


def test_resolved_bytes_must_still_match_the_pinned_source_digest() -> None:
    member = _member(1, path="models/a/ir.json", value=b"original")
    with pytest.raises(BulkExportConflict, match="changed"):
        ResolvedBundleFile(member, b"modified")


def test_source_reference_is_a_typed_union_not_a_generic_payload() -> None:
    with pytest.raises(InvalidBulkExport, match="typed source"):
        ExportSourceRef(
            ExportMemberKind.SOLVER_CARD_NATIVE,
            material_model_id=_id(1),
            material_model_revision_id=_id(2),
        )


@pytest.mark.parametrize(
    ("kind", "fields"),
    [
        (
            ExportMemberKind.TEST_DATA_JSON,
            {
                "artifact_id": _id(1),
                "test_data_document_id": _id(2),
                "test_data_document_revision_id": _id(3),
            },
        ),
        (
            ExportMemberKind.MAPPING_PROFILE_JSON,
            {"mapping_profile_id": _id(4), "mapping_profile_revision_id": _id(5)},
        ),
        (
            ExportMemberKind.PROCESSING_RECIPE_JSON,
            {"processing_recipe_id": _id(6), "processing_recipe_revision_id": _id(7)},
        ),
        (
            ExportMemberKind.NEUTRAL_MATERIAL_JSON,
            {
                "artifact_id": _id(8),
                "neutral_material_id": _id(9),
                "neutral_material_revision_id": _id(10),
            },
        ),
        (
            ExportMemberKind.NEUTRAL_SOLVER_MAPPING_REPORT,
            {
                "neutral_solver_card_id": _id(11),
                "neutral_solver_card_revision_id": _id(12),
            },
        ),
        (
            ExportMemberKind.NEUTRAL_SOLVER_CARD_NATIVE,
            {
                "neutral_solver_card_id": _id(13),
                "neutral_solver_card_revision_id": _id(14),
            },
        ),
    ],
)
def test_canonical_package_source_references_are_explicit_typed_pairs(
    kind: ExportMemberKind, fields: dict[str, UUID]
) -> None:
    source = ExportSourceRef(kind, **fields)

    assert source.kind is kind
    assert source.canonical()["kind"] == kind.value


def test_canonical_package_source_rejects_cross_kind_identifiers() -> None:
    with pytest.raises(InvalidBulkExport, match="typed source"):
        ExportSourceRef(
            ExportMemberKind.NEUTRAL_MATERIAL_JSON,
            artifact_id=_id(1),
            neutral_material_id=_id(2),
            neutral_material_revision_id=_id(3),
            mapping_profile_id=_id(4),
            mapping_profile_revision_id=_id(5),
        )


def test_neutral_json_and_native_card_are_distinct_manifest_components() -> None:
    neutral_value = b'{"neutral_material":"neutral-r1"}\n'
    native_value = b"*MATERIAL, NAME=REFERENCE\n"
    neutral = ExportSelectionMember(
        ordinal=1,
        source=ExportSourceRef(
            ExportMemberKind.NEUTRAL_MATERIAL_JSON,
            artifact_id=_id(30),
            neutral_material_id=_id(31),
            neutral_material_revision_id=_id(32),
        ),
        archive_path="neutral/neutral-material.json",
        source_sha256=hashlib.sha256(neutral_value).hexdigest(),
        source_size_bytes=len(neutral_value),
        media_type="application/json",
        classification=DataClassification.INTERNAL,
        label="Neutral material JSON",
    )
    native = ExportSelectionMember(
        ordinal=2,
        source=ExportSourceRef(
            ExportMemberKind.NEUTRAL_SOLVER_CARD_NATIVE,
            neutral_solver_card_id=_id(33),
            neutral_solver_card_revision_id=_id(34),
        ),
        archive_path="solver-cards/reference.inp",
        source_sha256=hashlib.sha256(native_value).hexdigest(),
        source_size_bytes=len(native_value),
        media_type="text/plain",
        classification=DataClassification.INTERNAL,
        label="Native solver card",
    )
    content = ExportSelectionContent("Neutral export pair", (neutral, native), ())
    bundle = build_deterministic_bundle(
        selection_id=_id(35),
        selection_revision_id=_id(36),
        content=content,
        files=(
            ResolvedBundleFile(neutral, neutral_value),
            ResolvedBundleFile(native, native_value),
        ),
    )

    with zipfile.ZipFile(io.BytesIO(bundle.archive)) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        components = manifest["components"]
        assert [component["source"]["kind"] for component in components] == [
            "neutral_material_json",
            "neutral_solver_card_native",
        ]
        assert [component["archive_path"] for component in components] == [
            "neutral/neutral-material.json",
            "solver-cards/reference.inp",
        ]
        assert components[0]["source"]["neutral_material_id"] == str(_id(31))
        assert components[0]["source"]["neutral_material_revision_id"] == str(_id(32))
        assert components[1]["source"]["neutral_solver_card_id"] == str(_id(33))
        assert components[1]["source"]["neutral_solver_card_revision_id"] == str(_id(34))
        assert components[0]["media_type"] == "application/json"
        assert components[1]["media_type"] == "text/plain"
        assert archive.read("neutral/neutral-material.json") == neutral_value
        assert archive.read("solver-cards/reference.inp") == native_value

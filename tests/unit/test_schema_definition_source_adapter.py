from __future__ import annotations

import hashlib
import io
import json
import zipfile
from pathlib import Path
from uuid import UUID

from cmp.modules.catalog.domain.schema_bundles import (
    CatalogSnapshot,
    SourceArtifactIdentity,
    build_schema_bundle_plan,
)
from cmp.modules.catalog.domain.schema_sources import (
    SOURCE_SET_CONTRACT_ID,
    SOURCE_SET_MEDIA_TYPE,
    SOURCE_ZIP_MEDIA_TYPE,
    NormalizedSchemaDefinitionSource,
    normalize_schema_definition_source,
)
from cmp.modules.identity_access.domain.authorization import DataClassification
from jsonschema import Draft202012Validator

ROOT = Path(__file__).parents[2]
SOURCE = ROOT / "fixtures" / "schema-definition-bundle" / "source-v2"
ORG = UUID("11111111-1111-4111-8111-111111111111")
PROJECT = UUID("22222222-2222-4222-8222-222222222222")


def _files() -> dict[str, bytes]:
    return {
        path.relative_to(SOURCE).as_posix(): path.read_bytes()
        for path in SOURCE.rglob("*")
        if path.is_file()
    }


def _envelope(files: dict[str, bytes]) -> bytes:
    value = {
        "$schema": SOURCE_SET_CONTRACT_ID,
        "contract_version": "1.0.0",
        "files": [
            {
                "path": path,
                "sha256": hashlib.sha256(content).hexdigest(),
                "content": content.decode("utf-8"),
            }
            for path, content in sorted(files.items())
        ],
    }
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False).encode()


def _normalize(raw: bytes, media_type: str) -> NormalizedSchemaDefinitionSource:
    return normalize_schema_definition_source(
        raw,
        media_type=media_type,
        organization_id=ORG,
        project_id=PROJECT,
        source_classification=DataClassification.INTERNAL,
    )


def test_approved_source_v2_set_normalizes_with_only_direct_product_relations() -> None:
    raw = _envelope(_files())
    contract = json.loads(
        (ROOT / "contracts/catalog/schema-definition-source-set.schema.json").read_text(
            encoding="utf-8"
        )
    )
    assert list(Draft202012Validator(contract).iter_errors(json.loads(raw))) == []

    first = _normalize(raw, SOURCE_SET_MEDIA_TYPE)
    second = _normalize(raw, SOURCE_SET_MEDIA_TYPE)

    assert first.valid
    assert first.canonical_bytes == second.canonical_bytes
    document = json.loads(first.canonical_bytes or b"null")
    assert [item["key"] for item in document["record_schemas"]] == [
        "technical_data",
        "tensile_test",
        "dma_test",
        "fld_test",
        "elastoplasticity_data",
        "statistics_data",
    ]
    assert [item["data_category"] for item in document["record_schemas"]] == [
        "technical_data",
        "test_data",
        "test_data",
        "test_data",
        "simulation_data",
        "simulation_data",
    ]
    encoded = first.canonical_bytes or b""
    assert b'"tensile_strength"' in encoded
    assert b'"title":"Tensile strength"' in encoded
    for link_key in (
        b'"technical_to_tensile"',
        b'"technical_to_dma"',
        b'"technical_to_fld"',
        b'"tensile_to_elastoplasticity"',
        b'"tensile_to_statistics"',
    ):
        assert link_key in encoded
    assert b'"technical_to_elastoplasticity"' not in encoded
    assert b'"dma_to_elastoplasticity"' not in encoded
    by_key = {item["key"]: item for item in document["record_schemas"]}
    technical_id = by_key["technical_data"]["schema"]["properties"]["data_information"][
        "properties"
    ]["technical_data_id"]
    technical_source = _files()["record-schemas/technical-data-v2.json"]
    assert technical_id["x-source-origin"] == {
        "schema_id": "urn:smx:schema:technical-data:2.0.0",
        "schema_version": "2.0.0",
        "file": "record-schemas/technical-data-v2.json",
        "file_sha256": hashlib.sha256(technical_source).hexdigest(),
        "pointer": (
            "/files/record-schemas~1technical-data-v2.json/properties/technical-data/"
            "properties/Data Information/properties/Technical Data ID"
        ),
    }
    specimen_standard = by_key["tensile_test"]["schema"]["properties"]["test_condition"][
        "properties"
    ]["specimen_standard"]
    storage_curve = by_key["dma_test"]["schema"]["properties"]["test_result"]["properties"][
        "storage_modulus_curve"
    ]
    for table_key in ("tensile_test", "dma_test", "fld_test"):
        test_schema = by_key[table_key]["schema"]
        assert "data_information" in test_schema["required"]
        assert "technical_data_ref" in test_schema["properties"]["data_information"]["required"]
    assert technical_id["x-business-key"] is True
    assert technical_id["x-id-rule"].startswith("TechnicalData_")
    assert specimen_standard["x-suggested-values"] == [
        "ASTM E8 Sheet-type",
        "ASTM D638 Type1",
        "ISO 527-2 1A",
    ]
    assert storage_curve["x-curve"]["series_unit"] == "Hz"
    assert all(item.code != "CMP-SCHEMA-SOURCE-0020" for item in first.diagnostics)
    assert any(item.code == "CMP-SCHEMA-SOURCE-0025" for item in first.diagnostics)
    assert any(item.code == "CMP-SCHEMA-SOURCE-0026" for item in first.diagnostics)
    assert any(item.code == "CMP-SCHEMA-SOURCE-0027" for item in first.diagnostics)
    assert any(item.code == "CMP-SCHEMA-SOURCE-0028" for item in first.diagnostics)
    assert any(
        item.code == "CMP-SCHEMA-SOURCE-0029"
        and item.location == "/manifest/link_types/4"
        for item in first.diagnostics
    )


def test_source_v2_plan_accepts_task2_units_and_reuses_explicit_legacy_hz() -> None:
    normalized = _normalize(_envelope(_files()), SOURCE_SET_MEDIA_TYPE)
    source = SourceArtifactIdentity(
        UUID("33333333-3333-4333-8333-333333333333"),
        ORG,
        PROJECT,
        DataClassification.INTERNAL,
        SOURCE_SET_MEDIA_TYPE,
        1,
        "a" * 64,
    )

    plan = build_schema_bundle_plan(
        source=source,
        raw_bytes=normalized.canonical_bytes,
        source_diagnostics=normalized.diagnostics,
        snapshot=CatalogSnapshot(ORG, PROJECT, ()),
        organization_id=ORG,
        project_id=PROJECT,
        classification_allowed=lambda _: True,
    )

    assert plan.valid
    errors = [item for item in plan.diagnostics if item.severity.value == "error"]
    assert errors == []
    assert all(item.code != "CMP-SCHEMA-BUNDLE-0002" for item in plan.diagnostics)
    assert any(
        item.code == "CMP-SCHEMA-SOURCE-0029"
        and item.location == "/manifest/link_types/4"
        for item in plan.diagnostics
    )
    assert any(
        item.code == "CMP-SCHEMA-SOURCE-0030"
        and item.location == "/manifest/unit_profiles/0/units/mass"
        for item in plan.diagnostics
    )
    assert plan.bundle is not None
    assert plan.bundle.summary()["unit_profile_count"] == 2
    task2_profile = next(
        item for item in plan.bundle.unit_profiles if item["key"] == "cae_mm_t_s"
    )
    assert task2_profile["units"] == {
        "density": "tonne/mm3",
        "length": "mm",
        "stress": "MPa",
        "time": "s",
    }


def test_zip_and_json_source_set_have_the_same_canonical_result() -> None:
    files = _files()
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as output:
        for path, content in sorted(files.items()):
            output.writestr(path, content)

    from_json = _normalize(_envelope(files), SOURCE_SET_MEDIA_TYPE)
    from_zip = _normalize(archive.getvalue(), SOURCE_ZIP_MEDIA_TYPE)

    assert from_json.valid and from_zip.valid
    assert from_json.canonical_bytes == from_zip.canonical_bytes


def test_source_set_digest_failure_returns_the_exact_file_location() -> None:
    document = json.loads(_envelope(_files()))
    document["files"][1]["sha256"] = "0" * 64

    result = _normalize(json.dumps(document).encode(), SOURCE_SET_MEDIA_TYPE)

    assert not result.valid
    assert any(
        item.code == "CMP-SCHEMA-SOURCE-0006" and item.location == "/files/1/sha256"
        for item in result.diagnostics
    )


def test_unsupported_source_extension_and_manifest_member_fail_at_the_exact_location() -> None:
    files = _files()
    technical_path = "record-schemas/technical-data-v2.json"
    technical = json.loads(files[technical_path])
    technical["properties"]["technical-data"]["properties"]["Data Information"]["properties"][
        "Technical Data ID"
    ]["x-implicit-default"] = "forbidden"
    files[technical_path] = json.dumps(technical).encode()

    extension = _normalize(_envelope(files), SOURCE_SET_MEDIA_TYPE)

    assert not extension.valid
    assert any(
        item.code == "CMP-SCHEMA-SOURCE-0010"
        and item.location.endswith("/Technical Data ID/x-implicit-default")
        for item in extension.diagnostics
    )

    files = _files()
    manifest_path = "catalog-schema-bundle.manifest.json"
    manifest = json.loads(files[manifest_path])
    manifest["database"]["implicit_policy"] = "forbidden"
    files[manifest_path] = json.dumps(manifest).encode()

    member = _normalize(_envelope(files), SOURCE_SET_MEDIA_TYPE)

    assert not member.valid
    assert any(
        item.code == "CMP-SCHEMA-SOURCE-0003" and item.location == "/manifest/database"
        for item in member.diagnostics
    )

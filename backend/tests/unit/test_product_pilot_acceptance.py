from __future__ import annotations

import hashlib
import io
import json
import zipfile

import pytest
from cmp.shared.domain.revisions import canonical_json_bytes
from cmp.tools.product_pilot_acceptance import (
    ProductPilotAcceptanceError,
    verify_bundle_bytes,
)

KINDS = (
    "raw_original",
    "dataset_parquet",
    "dataset_csv",
    "model_ir_json",
    "model_ir_schema",
    "solver_mapping_report",
    "solver_card_native",
)


def _bundle(*, kinds: tuple[str, ...] = KINDS, corrupt_checksum: bool = False) -> tuple[bytes, str]:
    components = [
        {
            "archive_path": f"payload/{ordinal}.bin",
            "source": {"kind": kind},
            "status": "included",
        }
        for ordinal, kind in enumerate(kinds, start=1)
    ]
    manifest = canonical_json_bytes(
        {
            "schema": "cmp.bulk-export-manifest.v1",
            "components": components,
            "omissions": [],
        }
    )
    files: dict[str, bytes] = {"manifest.json": manifest}
    for ordinal, component in enumerate(components, start=1):
        files[str(component["archive_path"])] = f"component-{ordinal}".encode()
    checksum_lines = []
    for path, value in sorted(files.items()):
        digest = hashlib.sha256(value).hexdigest()
        if corrupt_checksum and path == "payload/1.bin":
            digest = "0" * 64
        checksum_lines.append(f"{digest}  {path}\n")
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path, value in files.items():
            archive.writestr(path, value)
        archive.writestr("checksums.sha256", "".join(checksum_lines).encode("ascii"))
    return output.getvalue(), hashlib.sha256(manifest).hexdigest()


def test_verify_product_pilot_bundle_checks_every_representation() -> None:
    archive, manifest_sha256 = _bundle()

    result = verify_bundle_bytes(
        archive,
        archive_sha256=hashlib.sha256(archive).hexdigest(),
        manifest_sha256=manifest_sha256,
        component_count=7,
        omission_count=0,
    )

    assert result["component_count"] == 7
    assert result["representation_kinds"] == sorted(KINDS)


def test_verify_product_pilot_bundle_rejects_a_component_checksum_mismatch() -> None:
    archive, manifest_sha256 = _bundle(corrupt_checksum=True)

    with pytest.raises(ProductPilotAcceptanceError, match="component digest mismatch"):
        verify_bundle_bytes(
            archive,
            archive_sha256=hashlib.sha256(archive).hexdigest(),
            manifest_sha256=manifest_sha256,
            component_count=7,
            omission_count=0,
        )


def test_verify_product_pilot_bundle_requires_raw_neutral_and_solver_representations() -> None:
    archive, manifest_sha256 = _bundle(kinds=KINDS[:-1])

    with pytest.raises(ProductPilotAcceptanceError, match="solver_card_native"):
        verify_bundle_bytes(
            archive,
            archive_sha256=hashlib.sha256(archive).hexdigest(),
            manifest_sha256=manifest_sha256,
            component_count=6,
            omission_count=0,
        )


def test_verify_product_pilot_bundle_rejects_archive_digest_mismatch() -> None:
    archive, manifest_sha256 = _bundle()

    with pytest.raises(ProductPilotAcceptanceError, match="ZIP digest"):
        verify_bundle_bytes(
            archive,
            archive_sha256="0" * 64,
            manifest_sha256=manifest_sha256,
            component_count=7,
            omission_count=0,
        )


def test_synthetic_bundle_fixture_is_canonical_json() -> None:
    archive, _ = _bundle()
    with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
        manifest = bundle.read("manifest.json")
    assert canonical_json_bytes(json.loads(manifest)) == manifest

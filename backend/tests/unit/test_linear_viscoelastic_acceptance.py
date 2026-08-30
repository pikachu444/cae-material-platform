"""Regression checks for the fixture-backed linear-viscoelastic acceptance harness."""

from __future__ import annotations

import ast
import hashlib
import shutil
from pathlib import Path

import pytest
import yaml
from cmp.modules.testing.domain.public_shear_dma import (
    PublicShearDmaFixtureError,
    load_public_shear_dma_fixture,
)
from cmp.tools.linear_viscoelastic_acceptance_http import current_revision_content

ROOT = Path(__file__).parents[3]
PUBLIC_FIXTURE = ROOT / "fixtures/public/smp-shear-dma-283.15k-v1.csv"
ACCEPTANCE_CLI = ROOT / "scripts/verify_linear_viscoelastic_calibration_acceptance.py"


def test_public_fixture_preserves_manifest_units_order_and_fixture_timestamp_role() -> None:
    fixture = load_public_shear_dma_fixture(PUBLIC_FIXTURE)

    assert fixture.row_count >= 3
    assert tuple(channel["ordinal"] for channel in fixture.channels) == tuple(
        range(len(fixture.channels))
    )
    assert {channel["source_quantity"] for channel in fixture.channels} >= {
        "frequency",
        "storage_modulus",
        "loss_modulus",
    }
    assert all(channel["source_column"] in fixture.source_columns for channel in fixture.channels)
    assert all(channel["original_unit"] for channel in fixture.channels)
    temperature = next(
        condition
        for condition in fixture.conditions
        if condition["quantity_semantics"] == "temperature.absolute"
    )
    assert temperature["original_unit_string"]
    assert temperature["normalized_unit"] == "K"
    assert float(temperature["normalized_value"]) > 0
    assert fixture.platform_fixture["metadata_role"] == "deterministic_test_fixture_metadata"


def test_public_fixture_rejects_derived_values_republished_with_new_digests(
    tmp_path: Path,
) -> None:
    fixture_root = tmp_path / "fixtures"
    public_root = fixture_root / "public"
    manifest_root = fixture_root / "manifests"
    public_root.mkdir(parents=True)
    manifest_root.mkdir()
    shutil.copyfile(
        ROOT / "fixtures/public/frequency-sweep-SMP-30-original.tab",
        public_root / "frequency-sweep-SMP-30-original.tab",
    )
    derived_path = public_root / PUBLIC_FIXTURE.name
    original = PUBLIC_FIXTURE.read_bytes()
    altered = original.replace(b"559.29", b"559.30", 1)
    derived_path.write_bytes(altered)
    manifest = yaml.safe_load(
        (ROOT / "fixtures/manifests/smp-shear-dma-283.15k-v1.yaml").read_text(encoding="utf-8")
    )
    digest = hashlib.sha256(altered).hexdigest()
    manifest["fixture"]["digest"]["value"] = digest
    manifest["derivation"]["derived_fixture_sha256"] = digest
    manifest_path = manifest_root / "smp-shear-dma-283.15k-v1.yaml"
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")

    with pytest.raises(PublicShearDmaFixtureError, match="does not match"):
        load_public_shear_dma_fixture(derived_path, manifest_path)


def test_acceptance_cli_is_a_thin_mode_selector() -> None:
    tree = ast.parse(ACCEPTANCE_CLI.read_text(encoding="utf-8"))
    functions = {
        node.name for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }

    assert functions == {"main"}
    assert len(ACCEPTANCE_CLI.read_text(encoding="utf-8").splitlines()) < 100


def test_acceptance_reads_revision_content_from_supported_resource_shapes() -> None:
    content = {"profile_label": "governed mapping"}

    assert current_revision_content({"current_revision": {"content": content}}) == content
    assert (
        current_revision_content({"current_revision": {"id": "revision"}, "content": content})
        == content
    )

"""Fixture-driven public shear-DMA resources for linear-viscoelastic acceptance."""

from __future__ import annotations

import base64
import hashlib
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

import httpx

from cmp.modules.testing.domain.public_shear_dma import (
    PublicShearDmaFixtureError,
    load_public_shear_dma_fixture,
)
from cmp.tools.linear_viscoelastic_acceptance_http import (
    LinearViscoelasticAcceptanceError,
    current_revision_content,
    required_mapping,
    required_string,
    response_items,
    response_json,
    revision_id,
    upload_artifact,
)

PUBLIC_DMA_METHOD_PATH = "/test-methods/reference-shear-dma-frequency-sweep"
PUBLIC_DMA_RUN_PATH = "/test-runs/reference-shear-dma-frequency-sweep"


def create_public_material_and_state(
    client: httpx.Client,
    record: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Ensure the exact fixture-declared Material and State identities exist."""

    material_code = required_string(record.get("material_code"), "record.material_code")
    material_name = required_string(record.get("material_name"), "record.material_name")
    material_family = required_string(record.get("material_family"), "record.material_family")
    material_class = required_string(record.get("material_class"), "record.material_class")
    material_description = required_string(
        record.get("material_description"), "record.material_description"
    )
    state_name = required_string(record.get("state_name"), "record.state_name")
    state_lot_or_batch = required_string(
        record.get("state_lot_or_batch"), "record.state_lot_or_batch"
    )
    state_description = required_string(record.get("state_description"), "record.state_description")
    materials = response_items(response_json(client.get(f"/materials?q={material_code}&limit=20")))
    material = next(
        (
            item
            for item in materials
            if current_revision_content(item).get("material_code") == material_code
        ),
        None,
    )
    if material is None:
        material = response_json(
            client.post(
                "/materials",
                json={
                    "classification": "internal",
                    "content": {
                        "name": material_name,
                        "material_code": material_code,
                        "material_family": material_family,
                        "description": material_description,
                        "material_class": material_class,
                    },
                    "change_reason": "Register public shear-DMA reference material",
                },
            )
        )
    material_id = required_string(material.get("material_id"), "material_id")
    material_detail = response_json(client.get(f"/materials/{material_id}"))
    material_value = required_mapping(material_detail.get("material"), "material")
    persisted_material_id = required_string(material_value.get("material_id"), "material_id")
    states = cast(list[dict[str, Any]], material_detail.get("states") or [])
    state = next(
        (item for item in states if current_revision_content(item).get("name") == state_name),
        None,
    )
    if state is None:
        state = response_json(
            client.post(
                f"/materials/{persisted_material_id}/states",
                json={
                    "content": {
                        "material_revision_id": revision_id(material_value),
                        "name": state_name,
                        "manufacturing_route": None,
                        "heat_treatment": None,
                        "lot_or_batch": state_lot_or_batch,
                        "description": state_description,
                    },
                    "change_reason": "Register public shear-DMA test state",
                },
            )
        )
    return material_value, state


def create_public_shear_dma_test_data(
    client: httpx.Client,
    *,
    fixture_path: Path,
    manifest_path: Path | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Create public Test Data from fixture manifest/raw/derived facts only."""

    try:
        fixture = load_public_shear_dma_fixture(fixture_path, manifest_path)
    except PublicShearDmaFixtureError as error:
        raise LinearViscoelasticAcceptanceError(str(error)) from error
    source = fixture.source_bytes
    # Keep the domain fixture immutable while returning a normal JSON/report mapping from the
    # acceptance setup boundary.
    provenance = dict(fixture.provenance)
    source_file = fixture.source_file
    record = fixture.record
    source_file_name = required_string(source_file.get("name"), "source file name")
    source_file_id = required_string(str(source_file.get("data_file_id")), "source data file id")
    specimen_code = required_string(record.get("specimen_code"), "record.specimen_code")
    method_code = required_string(record.get("test_method_code"), "record.test_method_code")
    run_label = required_string(record.get("test_run_label"), "record.test_run_label")
    profile_label = required_string(record.get("profile_label"), "record.profile_label")
    document_id = required_string(
        record.get("test_data_document_id"), "record.test_data_document_id"
    )
    specimen_description = required_string(
        record.get("specimen_description"), "record.specimen_description"
    )
    performed_at = required_string(
        fixture.platform_fixture.get("test_run_performed_at"),
        "platform_fixture.test_run_performed_at",
    )
    temperature_condition = next(
        (
            condition
            for condition in fixture.conditions
            if condition.get("quantity_semantics") == "temperature.absolute"
        ),
        None,
    )
    if temperature_condition is None:
        raise LinearViscoelasticAcceptanceError(
            "public fixture has no temperature.absolute condition"
        )
    test_temperature_k = float(
        required_string(temperature_condition.get("normalized_value"), "normalized temperature")
    )
    profile_channels = [dict(item) for item in fixture.channels]
    profile_conditions = [dict(item) for item in fixture.conditions]
    material, state = create_public_material_and_state(client, record)
    methods = response_items(response_json(client.get("/test-methods")))
    method = next(
        (
            item
            for item in methods
            if current_revision_content(item).get("method_code") == method_code
        ),
        None,
    )
    if method is None:
        method = response_json(
            client.post(
                PUBLIC_DMA_METHOD_PATH,
                json={
                    "classification": "internal",
                    "change_reason": "Register public shear DMA frequency-sweep method",
                },
            )
        )
    state_id = required_string(state.get("material_state_id"), "material_state_id")
    specimens = response_items(response_json(client.get(f"/material-states/{state_id}/specimens")))
    specimen = next(
        (
            item
            for item in specimens
            if current_revision_content(item).get("specimen_code") == specimen_code
        ),
        None,
    )
    if specimen is None:
        specimen = response_json(
            client.post(
                f"/material-states/{state_id}/specimens",
                json={
                    "material_state_revision_id": revision_id(state),
                    "specimen_code": specimen_code,
                    "orientation": None,
                    "preparation_note": specimen_description,
                    "change_reason": "Register public shear-DMA specimen",
                },
            )
        )
    runs = response_items(response_json(client.get(f"/material-states/{state_id}/test-runs")))
    test_run = next(
        (item for item in runs if current_revision_content(item).get("run_label") == run_label),
        None,
    )
    if test_run is None:
        test_run = response_json(
            client.post(
                PUBLIC_DMA_RUN_PATH,
                json={
                    "specimen_id": specimen["specimen_id"],
                    "specimen_revision_id": revision_id(specimen),
                    "test_method_id": method["test_method_id"],
                    "test_method_revision_id": revision_id(method),
                    "run_label": run_label,
                    "performed_at": performed_at,
                    "test_temperature_k": test_temperature_k,
                    "change_reason": "Register exact public shear-DMA execution",
                },
            )
        )
    uploaded = upload_artifact(
        client,
        value=source,
        filename=f"{source_file_name}.derived.csv",
        media_type="text/csv",
        idempotency_key=(
            f"public-darus-{source_file_id}-source:{hashlib.sha256(source).hexdigest()}"
        ),
        test_run_revision_id=revision_id(test_run),
    )
    profile_content = {
        "profile_label": profile_label,
        "data_schema": "dma_frequency_temperature_sweep",
        "file_format": "csv",
        "sheet_name": None,
        "header_row": 1,
        "encoding": "utf-8",
        "delimiter": ",",
        "decimal_separator": ".",
        "channels": profile_channels,
        "initial_gauge_length_m": None,
        "initial_cross_section_area_m2": None,
        "approval_kind": "human_confirmed",
        "schema_version": "1.2.0",
        "deformation_mode": "shear",
    }
    profiles = response_items(response_json(client.get("/import-profiles")))
    profile = next(
        (
            item
            for item in profiles
            if current_revision_content(item).get("profile_label") == profile_label
            and current_revision_content(item).get("schema_version") == "1.2.0"
            and current_revision_content(item).get("deformation_mode") == "shear"
        ),
        None,
    )
    if profile is None:
        profile = response_json(
            client.post(
                "/import-profiles",
                json={
                    "classification": "internal",
                    "content": profile_content,
                    "change_reason": "Approve exact public shear-DMA quantity and unit mapping",
                },
            )
        )
    import_key = f"public-darus-{source_file_id}-import:{hashlib.sha256(source).hexdigest()}"
    import_run = response_json(
        client.post(
            "/tabular-import-runs",
            json={
                "test_run_id": test_run["test_run_id"],
                "test_run_revision_id": revision_id(test_run),
                "raw_asset_id": uploaded["raw_asset_id"],
                "raw_artifact_id": uploaded["artifact_id"],
                "import_profile_id": profile["import_profile_id"],
                "import_profile_revision_id": revision_id(profile),
                "change_reason": "Create exact public normalized shear-DMA dataset",
            },
            headers={"Idempotency-Key": import_key},
        )
    )
    if import_run.get("status") != "succeeded":
        raise LinearViscoelasticAcceptanceError(f"public governed import failed: {import_run}")
    converted = response_json(
        client.post(
            "/test-data:convert-tabular",
            json={
                "document_id": document_id,
                "material": {
                    "maker": required_string(
                        record.get("canonical_maker"), "record.canonical_maker"
                    ),
                    "grade": required_string(
                        record.get("canonical_grade"), "record.canonical_grade"
                    ),
                    "lot_batch": required_string(
                        record.get("state_lot_or_batch"), "record.state_lot_or_batch"
                    ),
                },
                "test": {
                    "date": performed_at[:10],
                    "operator": required_string(
                        record.get("canonical_operator"), "record.canonical_operator"
                    ),
                    "laboratory": required_string(
                        record.get("canonical_laboratory"), "record.canonical_laboratory"
                    ),
                    "method": required_string(
                        record.get("canonical_method"), "record.canonical_method"
                    ),
                    "equipment_maker": None,
                    "equipment_model": None,
                },
                "specimen": {
                    "specimen_id": specimen_code,
                    "description": required_string(
                        record.get("canonical_specimen_description"),
                        "record.canonical_specimen_description",
                    ),
                },
                "conditions": profile_conditions,
                "source_file_name": fixture_path.name,
                "source_base64": base64.b64encode(source).decode("ascii"),
                "profile": profile_content,
            },
        )
    )
    normalized_id = required_string(
        import_run.get("normalized_dataset_id"), "normalized_dataset_id"
    )
    normalized_revision = required_string(
        import_run.get("normalized_dataset_revision_id"),
        "normalized_dataset_revision_id",
    )
    governed_source = {
        "material": {
            "aggregate_id": material["material_id"],
            "revision_id": revision_id(material),
        },
        "material_state": {
            "aggregate_id": state_id,
            "revision_id": revision_id(state),
        },
        "test_run": {
            "aggregate_id": test_run["test_run_id"],
            "revision_id": revision_id(test_run),
        },
        "tabular_import": {
            "raw_asset_id": uploaded["raw_asset_id"],
            "raw_artifact_id": uploaded["artifact_id"],
            "import_run_id": import_run["import_run_id"],
            "import_profile": {
                "aggregate_id": profile["import_profile_id"],
                "revision_id": revision_id(profile),
            },
            "normalized_dataset": {
                "aggregate_id": normalized_id,
                "revision_id": normalized_revision,
            },
        },
    }
    documents = response_items(response_json(client.get("/test-data-documents")))
    test_data = next(
        (item for item in documents if item.get("document_key") == document_id),
        None,
    )
    if test_data is None:
        test_data = response_json(
            client.post(
                "/test-data-documents",
                json={
                    "classification": "internal",
                    "document": converted["canonical_document"],
                    "change_reason": "Save exact public shear-DMA Test Data",
                    "governed_source": governed_source,
                },
            )
        )
    elif (
        test_data.get("point_count") != fixture.row_count
        or test_data.get("governed_source") != governed_source
    ):
        raise LinearViscoelasticAcceptanceError(
            "existing public Test Data identity points to different input evidence; "
            "use a new fixture document identity or restore the exact governed source"
        )
    return test_data, {
        "material": material,
        "state": state,
        "specimen": specimen,
        "test_run": test_run,
        "profile": profile,
        "source_provenance": provenance,
        "public_no_static_property_set": True,
        "fixture_record": dict(record),
        "fixture_row_count": fixture.row_count,
        "selected_temperature_k": test_temperature_k,
        "source_file_id": source_file_id,
    }

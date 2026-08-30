"""Fixture-backed synthetic resources for linear-viscoelastic acceptance."""

from __future__ import annotations

import base64
import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

import httpx

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


def relaxation_source_bytes() -> bytes:
    """Return the small deterministic relaxation fixture used by the demo composition."""

    return (
        b"time_s,shear_modulus_pa\n"
        b"0.01,1089000000\n"
        b"0.03,1050000000\n"
        b"0.1,954000000\n"
        b"0.3,869000000\n"
        b"1,814000000\n"
        b"3,766000000\n"
        b"10,678000000\n"
        b"30,572000000\n"
        b"100,555000000\n"
    )


def _synthetic_material_catalog(
    client: httpx.Client,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    materials = response_items(
        response_json(client.get("/materials?q=CMP-DEMO-POLYMER-PRONY&limit=20"))
    )
    material = next(
        (
            item
            for item in materials
            if required_mapping(item.get("current_revision"), "material revision")
            .get("content", {})
            .get("material_code")
            == "CMP-DEMO-POLYMER-PRONY"
        ),
        None,
    )
    if material is None:
        raise LinearViscoelasticAcceptanceError("synthetic polymer Material is not seeded")
    material_id = required_string(material.get("material_id"), "material_id")
    detail = response_json(client.get(f"/materials/{material_id}"))
    material = required_mapping(detail.get("material"), "material")
    states = cast(list[dict[str, Any]], detail.get("states"))
    properties = cast(list[dict[str, Any]], detail.get("property_sets"))
    if not states or not properties:
        raise LinearViscoelasticAcceptanceError("synthetic polymer lacks State or Property Set")
    return dict(material), states[0], properties[0]


def create_governed_relaxation_test_data(
    client: httpx.Client,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Create exact governed synthetic Test Data and return its supporting catalog."""

    material, state, property_set = _synthetic_material_catalog(client)
    methods = response_items(response_json(client.get("/test-methods")))
    method = next(
        (
            item
            for item in methods
            if required_mapping(item.get("current_revision"), "method revision")
            .get("content", {})
            .get("method_code")
            == "reference_shear_relaxation"
        ),
        None,
    )
    if method is None:
        raise LinearViscoelasticAcceptanceError("shear-relaxation Test Method is not seeded")
    state_id = required_string(state.get("material_state_id"), "material_state_id")
    specimen_code = "LVE-ACCEPTANCE-RELAXATION-01"
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
                    "preparation_note": "Synthetic backend acceptance evidence",
                    "change_reason": "Create governed calibration acceptance specimen",
                },
            )
        )
    run_label = "Governed 296.15 K shear relaxation acceptance"
    runs = response_items(response_json(client.get(f"/material-states/{state_id}/test-runs")))
    test_run = next(
        (item for item in runs if current_revision_content(item).get("run_label") == run_label),
        None,
    )
    if test_run is None:
        test_run = response_json(
            client.post(
                "/test-runs/reference-shear-relaxation",
                json={
                    "specimen_id": specimen["specimen_id"],
                    "specimen_revision_id": revision_id(specimen),
                    "test_method_id": method["test_method_id"],
                    "test_method_revision_id": revision_id(method),
                    "run_label": run_label,
                    "performed_at": "2026-08-28T09:00:00Z",
                    "test_temperature_k": 296.15,
                    "change_reason": "Register exact synthetic shear-relaxation execution",
                },
            )
        )
    source = relaxation_source_bytes()
    point_count = len(source.splitlines()) - 1
    uploaded = upload_artifact(
        client,
        value=source,
        filename="lve-acceptance-relaxation.csv",
        media_type="text/csv",
        idempotency_key=f"lve-acceptance-source:{hashlib.sha256(source).hexdigest()}",
        test_run_revision_id=revision_id(test_run),
    )
    profile_content = {
        "profile_label": "Governed shear relaxation acceptance",
        "data_schema": "shear_relaxation",
        "file_format": "csv",
        "sheet_name": None,
        "header_row": 1,
        "encoding": "utf-8",
        "delimiter": ",",
        "decimal_separator": ".",
        "channels": [
            {
                "ordinal": 0,
                "source_column": "time_s",
                "source_quantity": "time",
                "original_unit": "s",
                "axis_role": "independent",
            },
            {
                "ordinal": 1,
                "source_column": "shear_modulus_pa",
                "source_quantity": "shear_modulus",
                "original_unit": "Pa",
                "axis_role": "dependent",
            },
        ],
        "initial_gauge_length_m": None,
        "initial_cross_section_area_m2": None,
        "approval_kind": "human_confirmed",
        "schema_version": "1.2.0",
        "deformation_mode": None,
    }
    profiles = response_items(response_json(client.get("/import-profiles")))
    profile = next(
        (
            item
            for item in profiles
            if current_revision_content(item).get("profile_label")
            == profile_content["profile_label"]
            and current_revision_content(item).get("schema_version") == "1.2.0"
            and current_revision_content(item).get("deformation_mode") is None
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
                    "change_reason": "Approve exact relaxation quantity and unit mapping",
                },
            )
        )
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
                "change_reason": "Create exact normalized relaxation Dataset",
            },
            headers={"Idempotency-Key": "lve-acceptance-governed-import"},
        )
    )
    if import_run.get("status") != "succeeded":
        raise LinearViscoelasticAcceptanceError(f"governed import failed: {import_run}")
    converted = response_json(
        client.post(
            "/test-data:convert-tabular",
            json={
                "document_id": "CMP-LVE-ACCEPTANCE-RELAXATION",
                "material": {
                    "maker": "CMP Synthetic Materials",
                    "grade": "Demo Polymer Prony",
                    "lot_batch": "CMP-DEMO-POLYMER-001",
                },
                "test": {
                    "date": "2026-08-28",
                    "operator": "Acceptance Operator",
                    "laboratory": "CMP Disposable Demo",
                    "method": "governed synthetic shear relaxation",
                    "equipment_maker": "CMP Synthetic Instruments",
                    "equipment_model": "Relaxometer-A",
                },
                "specimen": {
                    "specimen_id": "LVE-ACCEPTANCE-RELAXATION-01",
                    "description": "Synthetic backend acceptance specimen",
                },
                "conditions": [
                    {
                        "key": "temperature",
                        "quantity_semantics": "temperature.test",
                        "original_value": "23",
                        "original_unit_string": "Cel",
                        "normalized_value": "296.15",
                        "normalized_unit": "K",
                    }
                ],
                "source_file_name": "lve-acceptance-relaxation.csv",
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
        (
            item
            for item in documents
            if item.get("document_key") == "CMP-LVE-ACCEPTANCE-RELAXATION"
        ),
        None,
    )
    if test_data is None:
        test_data = response_json(
            client.post(
                "/test-data-documents",
                json={
                    "classification": "internal",
                    "document": converted["canonical_document"],
                    "change_reason": "Save governed relaxation calibration input",
                    "governed_source": governed_source,
                },
            )
        )
    elif (
        test_data.get("point_count") != point_count
        or test_data.get("governed_source") != governed_source
    ):
        raise LinearViscoelasticAcceptanceError(
            "existing synthetic relaxation Test Data points to different input evidence"
        )
    return test_data, {
        "material": material,
        "state": state,
        "property_set": property_set,
        "profile": profile,
    }


def load_dma_temperature_reference(path: Path) -> dict[str, Any]:
    """Load the checked-in closed-form DMA reference used by API acceptance."""

    try:
        document = json.loads(path.read_bytes())
    except (OSError, json.JSONDecodeError) as error:
        raise LinearViscoelasticAcceptanceError(
            f"cannot read DMA temperature-sweep reference at {path}"
        ) from error
    if not isinstance(document, dict):
        raise LinearViscoelasticAcceptanceError("DMA reference must be a JSON object")
    if (
        document.get("classification") != "synthetic_non_confidential_non_production"
        or document.get("non_production") is not True
    ):
        raise LinearViscoelasticAcceptanceError("DMA reference must remain non-production")
    source = required_mapping(document.get("input"), "DMA reference input")
    rows = source.get("rows")
    if (
        not isinstance(rows, list)
        or len(rows) < 3
        or not all(isinstance(row, dict) for row in rows)
    ):
        raise LinearViscoelasticAcceptanceError("DMA reference must contain at least three rows")
    frequency = required_mapping(source.get("frequency"), "DMA reference frequency")
    if frequency.get("unit") != "Hz" or float(frequency.get("value", 0)) <= 0:
        raise LinearViscoelasticAcceptanceError("DMA reference frequency must be positive Hz")
    shift_law = required_mapping(source.get("shift_law"), "DMA reference shift law")
    reference_temperature = str(shift_law.get("reference_temperature_k"))
    if not any(
        str(row.get("temperature_k")) == reference_temperature
        and float(row.get("log10_a_t", 1)) == 0.0
        for row in rows
    ):
        raise LinearViscoelasticAcceptanceError(
            "DMA reference must define zero shift at its reference temperature"
        )
    return document


def dma_temperature_source_bytes(reference: Mapping[str, Any]) -> bytes:
    """Render the fixture rows as the exact governed source CSV."""

    source = required_mapping(reference.get("input"), "DMA reference input")
    rows = cast(list[dict[str, Any]], source.get("rows"))
    lines = ["temperature_k,storage_modulus_pa,loss_modulus_pa"]
    lines.extend(
        ",".join(
            (
                str(row["temperature_k"]),
                str(row["storage_modulus_pa"]),
                str(row["loss_modulus_pa"]),
            )
        )
        for row in rows
    )
    return ("\n".join(lines) + "\n").encode("utf-8")


def create_governed_dma_temperature_sweep(
    client: httpx.Client,
    fixture_path: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Create exact governed Test Data for the fixed-frequency DMA reference."""

    reference = load_dma_temperature_reference(fixture_path)
    source_document = required_mapping(reference.get("input"), "DMA reference input")
    fixture_rows = cast(list[dict[str, Any]], source_document.get("rows"))
    frequency = required_mapping(source_document.get("frequency"), "DMA reference frequency")
    source = dma_temperature_source_bytes(reference)
    source_sha256 = hashlib.sha256(source).hexdigest()
    material, state, property_set = _synthetic_material_catalog(client)
    methods = response_items(response_json(client.get("/test-methods")))
    method = next(
        (
            item
            for item in methods
            if current_revision_content(item).get("method_code")
            == "reference_shear_dma_temperature_sweep"
        ),
        None,
    )
    if method is None:
        method = response_json(
            client.post(
                "/test-methods/reference-shear-dma-temperature-sweep",
                json={
                    "classification": "internal",
                    "change_reason": "Register fixed-frequency DMA temperature-sweep method",
                },
            )
        )
    state_id = required_string(state.get("material_state_id"), "material_state_id")
    specimen_code = "DMA-TEMPERATURE-SWEEP-REFERENCE-01"
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
                    "preparation_note": "Synthetic closed-form DMA temperature-sweep reference",
                    "change_reason": "Create governed DMA temperature-sweep specimen",
                },
            )
        )
    run_label = "Fixed-frequency DMA temperature-sweep numerical reference"
    runs = response_items(response_json(client.get(f"/material-states/{state_id}/test-runs")))
    test_run = next(
        (item for item in runs if current_revision_content(item).get("run_label") == run_label),
        None,
    )
    if test_run is None:
        test_run = response_json(
            client.post(
                "/test-runs/reference-shear-dma-temperature-sweep",
                json={
                    "specimen_id": specimen["specimen_id"],
                    "specimen_revision_id": revision_id(specimen),
                    "test_method_id": method["test_method_id"],
                    "test_method_revision_id": revision_id(method),
                    "run_label": run_label,
                    "performed_at": "2000-01-01T00:00:00Z",
                    "change_reason": "Register synthetic DMA temperature-sweep execution",
                },
            )
        )
    uploaded = upload_artifact(
        client,
        value=source,
        filename=fixture_path.with_suffix(".csv").name,
        media_type="text/csv",
        idempotency_key=f"dma-temperature-sweep-source:{source_sha256}",
        test_run_revision_id=revision_id(test_run),
    )
    profile_content = {
        "profile_label": "Fixed-frequency shear DMA temperature sweep",
        "data_schema": "dma_temperature_sweep",
        "file_format": "csv",
        "sheet_name": None,
        "header_row": 1,
        "encoding": "utf-8",
        "delimiter": ",",
        "decimal_separator": ".",
        "channels": [
            {
                "ordinal": 0,
                "source_column": "temperature_k",
                "source_quantity": "temperature",
                "original_unit": "K",
                "axis_role": "independent",
            },
            {
                "ordinal": 1,
                "source_column": "storage_modulus_pa",
                "source_quantity": "storage_modulus",
                "original_unit": "Pa",
                "axis_role": "dependent",
            },
            {
                "ordinal": 2,
                "source_column": "loss_modulus_pa",
                "source_quantity": "loss_modulus",
                "original_unit": "Pa",
                "axis_role": "dependent",
            },
        ],
        "initial_gauge_length_m": None,
        "initial_cross_section_area_m2": None,
        "approval_kind": "human_confirmed",
        "schema_version": "1.3.0",
        "deformation_mode": "shear",
    }
    profiles = response_items(response_json(client.get("/import-profiles")))
    profile = next(
        (
            item
            for item in profiles
            if current_revision_content(item).get("profile_label")
            == profile_content["profile_label"]
            and current_revision_content(item).get("schema_version") == "1.3.0"
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
                    "change_reason": "Approve DMA temperature, modulus, and unit mapping",
                },
            )
        )
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
                "change_reason": "Create exact normalized DMA temperature-sweep Dataset",
            },
            headers={"Idempotency-Key": f"dma-temperature-sweep-import:{source_sha256}"},
        )
    )
    if import_run.get("status") != "succeeded":
        raise LinearViscoelasticAcceptanceError(f"DMA governed import failed: {import_run}")
    converted = response_json(
        client.post(
            "/test-data:convert-tabular",
            json={
                "document_id": "CMP-DMA-TEMPERATURE-SWEEP-REFERENCE",
                "material": {
                    "maker": "CMP Synthetic Materials",
                    "grade": "Closed-form generalized Maxwell reference",
                    "lot_batch": "SYNTHETIC-LVE-REFERENCE-001",
                },
                "test": {
                    "date": "2000-01-01",
                    "operator": "Automated numerical reference",
                    "laboratory": "CMP verification",
                    "method": "fixed-frequency shear DMA temperature sweep",
                    "equipment_maker": None,
                    "equipment_model": None,
                },
                "specimen": {
                    "specimen_id": specimen_code,
                    "description": "Synthetic closed-form DMA reference",
                },
                "conditions": [
                    {
                        "key": "frequency",
                        "quantity_semantics": "frequency.cyclic",
                        "original_value": str(frequency["value"]),
                        "original_unit_string": "Hz",
                        "normalized_value": str(frequency["value"]),
                        "normalized_unit": "Hz",
                    }
                ],
                "source_file_name": fixture_path.with_suffix(".csv").name,
                "source_base64": base64.b64encode(source).decode("ascii"),
                "profile": profile_content,
            },
        )
    )
    normalized_id = required_string(
        import_run.get("normalized_dataset_id"), "normalized_dataset_id"
    )
    normalized_revision = required_string(
        import_run.get("normalized_dataset_revision_id"), "normalized_dataset_revision_id"
    )
    governed_source = {
        "material": {
            "aggregate_id": material["material_id"],
            "revision_id": revision_id(material),
        },
        "material_state": {"aggregate_id": state_id, "revision_id": revision_id(state)},
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
        (
            item
            for item in documents
            if item.get("document_key") == "CMP-DMA-TEMPERATURE-SWEEP-REFERENCE"
        ),
        None,
    )
    if test_data is None:
        test_data = response_json(
            client.post(
                "/test-data-documents",
                json={
                    "classification": "internal",
                    "document": converted["canonical_document"],
                    "change_reason": "Save governed DMA temperature-sweep calibration input",
                    "governed_source": governed_source,
                },
            )
        )
    elif (
        test_data.get("point_count") != len(fixture_rows)
        or test_data.get("governed_source") != governed_source
    ):
        raise LinearViscoelasticAcceptanceError(
            "existing DMA Test Data points to different governed source evidence"
        )
    return test_data, {
        "material": material,
        "state": state,
        "property_set": property_set,
        "profile": profile,
        "reference": reference,
    }


def calibration_bounds(term_count: int) -> list[dict[str, Any]]:
    """Return the explicit bounded parameter rows used by both acceptance workflows."""

    values = [
        {
            "name": "G_inf_pa",
            "lower": 1_000_000.0,
            "start": 500_000_000.0,
            "upper": 2_000_000_000.0,
            "unit": "Pa",
            "transform": "ln",
        }
    ]
    for ordinal in range(1, term_count + 1):
        values.append(
            {
                "name": f"G_{ordinal}_pa",
                "lower": 1_000_000.0,
                "start": 300_000_000.0 if ordinal == 1 else 500_000_000.0,
                "upper": 2_000_000_000.0,
                "unit": "Pa",
                "transform": "ln",
            }
        )
    for ordinal in range(1, term_count + 1):
        lower = 0.0001 if ordinal == 1 else 10.0 ** (ordinal - 2) + 0.0001
        upper = 1.0 if ordinal == 1 else 10.0 ** (ordinal - 1)
        values.append(
            {
                "name": f"tau_{ordinal}_s",
                "lower": lower,
                "start": 0.08 if ordinal == 1 else (lower + upper) / 2.0,
                "upper": upper,
                "unit": "s",
                "transform": "ln",
            }
        )
    return values


def calibration_start_vectors(term_counts: tuple[int, ...]) -> dict[str, list[list[float]]]:
    """Build one explicit interior start vector from each acceptance bound declaration."""

    return {
        str(term_count): [
            [float(bound["start"]) for bound in calibration_bounds(term_count)]
        ]
        for term_count in term_counts
    }

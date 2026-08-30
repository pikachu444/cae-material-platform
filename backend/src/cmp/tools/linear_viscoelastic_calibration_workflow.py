"""Calibration execution, selection, promotion, and reload assertions for acceptance."""

from __future__ import annotations

import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

import httpx

from cmp.modules.modeling.domain.linear_viscoelastic_contracts import (
    LINEAR_VISCOELASTIC_RECOMMENDATION_POLICY,
)
from cmp.tools.linear_viscoelastic_acceptance_http import (
    LinearViscoelasticAcceptanceError,
    required_mapping,
    required_string,
    response_items,
    response_json,
    response_list,
    revision_id,
)
from cmp.tools.linear_viscoelastic_acceptance_setup import register_calibrator
from cmp.tools.linear_viscoelastic_public_dma_acceptance import create_public_shear_dma_test_data
from cmp.tools.linear_viscoelastic_synthetic_acceptance import (
    calibration_bounds,
    calibration_start_vectors,
    create_governed_dma_temperature_sweep,
    create_governed_relaxation_test_data,
)


def _run_until_succeeded(
    client: httpx.Client,
    *,
    run_id: str,
    label: str,
) -> dict[str, Any]:
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        run = response_json(client.get(f"/linear-viscoelastic-calibration-runs/{run_id}"))
        if run.get("status") == "succeeded":
            return run
        if run.get("status") in {"failed", "cancelled", "timed_out"}:
            raise LinearViscoelasticAcceptanceError(f"{label} Run failed: {run}")
        time.sleep(1)
    raise LinearViscoelasticAcceptanceError(f"{label} Run did not finish within 180 seconds")


def execute_synthetic_relaxation(
    client: httpx.Client,
    test_data: Mapping[str, Any],
    catalog: Mapping[str, Any],
) -> dict[str, Any]:
    """Execute the explicit relaxation calibration through Selection and exact IR promotion."""

    term_counts = (1, 2)
    plan = response_json(
        client.post(
            "/linear-viscoelastic-calibration-plans",
            json={
                "test_data": {
                    "id": test_data["test_data_document_id"],
                    "revision_id": revision_id(test_data),
                },
                "selected_temperature_k": "296.15",
                "point_dispositions": [
                    {
                        "ordinal": ordinal,
                        "partition": "HOLDOUT" if ordinal == 8 else "CALIBRATION",
                        "exclusion_reason": None,
                    }
                    for ordinal in range(9)
                ],
                "availability": {
                    "ramp": "NOT_PROVIDED",
                    "sweep": "NOT_PROVIDED",
                    "preconditioning": "NOT_PROVIDED",
                    "linear_range": "NOT_PROVIDED",
                },
                "recommendation_policy": LINEAR_VISCOELASTIC_RECOMMENDATION_POLICY,
                "term_counts": list(term_counts),
                "parameter_bounds": {"1": calibration_bounds(1), "2": calibration_bounds(2)},
                "start_vectors": calibration_start_vectors(term_counts),
                "weights": {
                    "relaxation_weight": "1",
                    "dma_storage_weight": "0.5",
                    "dma_loss_weight": "0.5",
                    "relaxation_scale_pa": "1000000000",
                    "dma_storage_scale_pa": "1000000000",
                    "dma_loss_scale_pa": "1000000000",
                    "q_rule_version": "equal_per_point@1.0.0",
                },
                "optimizer": {
                    "method": "trf",
                    "x_scale": "jac",
                    "transform": "ln",
                    "ftol": 1e-8,
                    "xtol": 1e-8,
                    "gtol": 1e-8,
                    "max_nfev": 5000,
                },
                "change_reason": "Create fully explicit governed calibration Plan",
            },
            headers={"Idempotency-Key": "lve-acceptance-plan"},
        )
    )
    plan_id = required_string(plan.get("plan_id"), "plan_id")
    plan_revision = required_mapping(plan.get("current_revision"), "plan revision")
    run = response_json(
        client.post(
            f"/linear-viscoelastic-calibration-plans/{plan_id}/runs",
            json={
                "plan_revision_id": plan_revision["id"],
                "change_reason": "Execute governed relaxation calibration",
            },
            headers={"Idempotency-Key": "lve-acceptance-run"},
        )
    )
    run_id = required_string(run.get("run_id"), "run_id")
    _run_until_succeeded(client, run_id=run_id, label="calibration")
    recommendation = response_json(
        client.get(f"/linear-viscoelastic-calibration-runs/{run_id}/recommendation")
    )
    selection = response_json(
        client.post(
            "/linear-viscoelastic-calibration-selections",
            json={
                "plan_revision_id": plan_revision["id"],
                "run_id": run_id,
                "candidate_id": recommendation["candidate_id"],
                "candidate_sha256": recommendation["candidate_digest"],
                "reason": "Engineer selected the BIC recommendation after residual review",
                "warning_acknowledgements": [],
                "change_reason": "Record explicit engineer candidate selection",
            },
            headers={"Idempotency-Key": "lve-acceptance-selection"},
        )
    )
    selection_id = required_string(selection.get("selection_id"), "selection_id")
    material = cast(Mapping[str, Any], catalog["material"])
    state = cast(Mapping[str, Any], catalog["state"])
    property_set = cast(Mapping[str, Any], catalog["property_set"])
    promotion_body = {
        "material": {"id": material["material_id"], "revision_id": revision_id(material)},
        "material_state": {
            "id": state["material_state_id"],
            "revision_id": revision_id(state),
        },
        "property_set": {
            "id": property_set["property_set_id"],
            "revision_id": revision_id(property_set),
        },
        "change_reason": "Promote exact engineer Selection to immutable IR",
    }
    promoted = response_json(
        client.post(
            f"/linear-viscoelastic-calibration-selections/{selection_id}/linear-viscoelastic-model",
            json=promotion_body,
        )
    )
    replayed = response_json(
        client.post(
            f"/linear-viscoelastic-calibration-selections/{selection_id}/linear-viscoelastic-model",
            json=promotion_body,
        )
    )
    model_id = required_string(promoted.get("material_model_id"), "material_model_id")
    reloaded = response_json(client.get(f"/linear-viscoelastic-models/{model_id}"))
    if replayed.get("material_model_id") != model_id or reloaded != promoted:
        raise LinearViscoelasticAcceptanceError(
            "idempotent promotion or exact API reload changed the saved IR"
        )
    revision = required_mapping(reloaded.get("current_revision"), "model revision")
    content = required_mapping(revision.get("content"), "model content")
    evidence = required_mapping(
        content.get("calibration_promotion_evidence"), "calibration promotion evidence"
    )
    plan_evidence = required_mapping(evidence.get("plan"), "calibration Plan evidence")
    run_evidence = required_mapping(evidence.get("run"), "calibration Run evidence")
    selection_evidence = required_mapping(
        evidence.get("selection"), "calibration Selection evidence"
    )
    test_data_evidence = required_mapping(
        evidence.get("canonical_test_data"), "canonical Test Data evidence"
    )
    if (
        revision.get("schema_version") != "1.4.0"
        or content.get("non_production") is not True
        or plan_evidence.get("revision_id") != plan_revision["id"]
        or run_evidence.get("id") != run_id
        or selection_evidence.get("id") != selection_id
        or test_data_evidence.get("revision_id") != revision_id(test_data)
    ):
        raise LinearViscoelasticAcceptanceError(
            "reloaded IR lost exact non-production calibration evidence"
        )
    return {
        "plan_id": plan_id,
        "plan_revision_id": plan_revision["id"],
        "run_id": run_id,
        "recommendation_id": recommendation["recommendation_id"],
        "selection_id": selection_id,
        "material_model_id": model_id,
        "material_model_revision_id": revision["id"],
        "material_model_sha256": revision["content_hash"],
        "non_production": True,
    }


def execute_public_shear_dma(
    client: httpx.Client,
    *,
    test_data: Mapping[str, Any],
    point_count: int,
    selected_temperature_k: float,
    source_file_id: str,
    record: Mapping[str, Any],
) -> dict[str, Any]:
    """Execute public DMA through Selection; no static Property Set means no IR promotion."""

    if point_count < 3:
        raise LinearViscoelasticAcceptanceError(
            "public fixture must provide at least three data points"
        )
    material_name = required_string(record.get("material_name"), "record.material_name")
    term_counts = (1, 2)
    plan = response_json(
        client.post(
            "/linear-viscoelastic-calibration-plans",
            json={
                "test_data": {
                    "id": test_data["test_data_document_id"],
                    "revision_id": revision_id(test_data),
                },
                "selected_temperature_k": str(selected_temperature_k),
                "point_dispositions": [
                    {
                        "ordinal": ordinal,
                        "partition": (
                            "HOLDOUT" if ordinal >= point_count - 2 else "CALIBRATION"
                        ),
                        "exclusion_reason": None,
                    }
                    for ordinal in range(point_count)
                ],
                "availability": {
                    "ramp": "NOT_PROVIDED",
                    "sweep": "PROVIDED",
                    "preconditioning": "NOT_PROVIDED",
                    "linear_range": "NOT_PROVIDED",
                },
                "recommendation_policy": LINEAR_VISCOELASTIC_RECOMMENDATION_POLICY,
                "term_counts": list(term_counts),
                "parameter_bounds": {"1": calibration_bounds(1), "2": calibration_bounds(2)},
                "start_vectors": calibration_start_vectors(term_counts),
                "weights": {
                    "relaxation_weight": "1",
                    "dma_storage_weight": "0.5",
                    "dma_loss_weight": "0.5",
                    "relaxation_scale_pa": "1000000000",
                    "dma_storage_scale_pa": "1000000000",
                    "dma_loss_scale_pa": "1000000000",
                    "q_rule_version": "equal_per_point@1.0.0",
                },
                "optimizer": {
                    "method": "trf",
                    "x_scale": "jac",
                    "transform": "ln",
                    "ftol": 1e-8,
                    "xtol": 1e-8,
                    "gtol": 1e-8,
                    "max_nfev": 5000,
                },
                "change_reason": "Create explicit public isothermal shear-DMA Plan",
            },
            headers={"Idempotency-Key": f"public-shear-dma-{source_file_id}-calibration-plan"},
        )
    )
    plan_id = required_string(plan.get("plan_id"), "public plan_id")
    plan_revision = required_mapping(plan.get("current_revision"), "public plan revision")
    plan_revision_id = required_string(plan_revision.get("id"), "public plan revision.id")
    accepted = response_json(
        client.post(
            f"/linear-viscoelastic-calibration-plans/{plan_id}/runs",
            json={
                "plan_revision_id": plan_revision_id,
                "change_reason": "Execute public shear-DMA calibration",
            },
            headers={"Idempotency-Key": f"public-shear-dma-{source_file_id}-calibration-run"},
        )
    )
    run_id = required_string(accepted.get("run_id"), "public run_id")
    _run_until_succeeded(client, run_id=run_id, label="public shear-DMA calibration")
    candidates = response_list(
        client.get(f"/linear-viscoelastic-calibration-runs/{run_id}/candidates")
    )
    if not candidates:
        raise LinearViscoelasticAcceptanceError(
            "public shear-DMA calibration produced no candidates"
        )
    recommendation = response_json(
        client.get(f"/linear-viscoelastic-calibration-runs/{run_id}/recommendation")
    )
    candidate_id = required_string(recommendation.get("candidate_id"), "public candidate_id")
    candidate_digest = required_string(
        recommendation.get("candidate_digest"), "public candidate_digest"
    )
    selection = response_json(
        client.post(
            "/linear-viscoelastic-calibration-selections",
            json={
                "plan_revision_id": plan_revision_id,
                "run_id": run_id,
                "candidate_id": candidate_id,
                "candidate_sha256": candidate_digest,
                "reason": (
                    f"Engineer selected the public {material_name} recommendation after reviewing "
                    "calibration residuals; no static Property Set is available for promotion."
                ),
                "warning_acknowledgements": [],
                "change_reason": "Record explicit engineer selection for public DMA evidence",
            },
            headers={
                "Idempotency-Key": f"public-shear-dma-{source_file_id}-calibration-selection"
            },
        )
    )
    selection_id = required_string(selection.get("selection_id"), "public selection_id")
    reloaded_plan = response_json(client.get(f"/linear-viscoelastic-calibration-plans/{plan_id}"))
    reloaded_run = response_json(client.get(f"/linear-viscoelastic-calibration-runs/{run_id}"))
    reloaded_recommendation = response_json(
        client.get(f"/linear-viscoelastic-calibration-runs/{run_id}/recommendation")
    )
    reloaded_selection = response_json(
        client.get(f"/linear-viscoelastic-calibration-selections/{selection_id}")
    )
    if (
        revision_id(reloaded_plan) != plan_revision_id
        or reloaded_run.get("run_id") != run_id
        or reloaded_run.get("status") != "succeeded"
        or reloaded_recommendation.get("candidate_id") != candidate_id
        or reloaded_selection.get("selection_id") != selection_id
    ):
        raise LinearViscoelasticAcceptanceError(
            "public Plan/Run/Recommendation/Selection reload changed evidence"
        )
    return {
        "role": "public_reference_shear_dma_frequency_sweep",
        "test_data_id": test_data["test_data_document_id"],
        "test_data_revision_id": revision_id(test_data),
        "plan_id": plan_id,
        "plan_revision_id": plan_revision_id,
        "run_id": run_id,
        "recommendation_id": required_string(
            recommendation.get("recommendation_id"), "public recommendation_id"
        ),
        "selection_id": selection_id,
        "selected_candidate_id": candidate_id,
        "non_production": True,
        "ir_promotion": {
            "attempted": False,
            "status": "not_promoted",
            "reason": "public isotherm has no governed static Property Set values",
        },
    }


def execute_synthetic_dma_temperature_sweep(
    client: httpx.Client,
    *,
    test_data: Mapping[str, Any],
    catalog: Mapping[str, Any],
) -> dict[str, Any]:
    """Execute fixed-frequency DMA through TTS, Prony calibration, and Selection reload."""

    reference = required_mapping(catalog.get("reference"), "DMA reference")
    source = required_mapping(reference.get("input"), "DMA reference input")
    rows = cast(list[dict[str, Any]], source.get("rows"))
    shift_law = required_mapping(source.get("shift_law"), "DMA reference shift law")
    profile = required_mapping(catalog.get("profile"), "DMA Import Profile")
    test_revision = required_mapping(test_data.get("current_revision"), "DMA Test Data revision")
    profile_revision = required_mapping(profile.get("current_revision"), "DMA profile revision")
    created = response_json(
        client.post(
            "/processing/dma-frequency-master-curves",
            json={
                "classification": "internal",
                "label": "Fixed-frequency DMA TTS numerical reference",
                "test_data": {
                    "document_id": test_data["test_data_document_id"],
                    "revision_id": test_revision["id"],
                    "content_sha256": test_revision["content_hash"],
                },
                "import_profile": {
                    "profile_id": profile["import_profile_id"],
                    "revision_id": profile_revision["id"],
                    "content_sha256": profile_revision["content_hash"],
                },
                "dispositions": [
                    {
                        "source_ordinal": int(row["source_ordinal"]),
                        "partition": row["partition"],
                        "exclusion_reason": None,
                    }
                    for row in rows
                ],
                "shift_law": {
                    "kind": "tabulated",
                    "reference_temperature_k": float(
                        shift_law["reference_temperature_k"]
                    ),
                    "factors": [
                        {
                            "temperature_k": float(row["temperature_k"]),
                            "log10_a_t": float(row["log10_a_t"]),
                        }
                        for row in rows
                    ],
                    "value_origin": "engineer_entered",
                },
                "confirmation": {
                    "confirmed": True,
                    "reason": "Use the fixture-declared exact tabulated shift factors",
                },
                "recommendation_sha256": None,
                "change_reason": "Create governed fixed-frequency DMA master curve",
            },
        )
    )
    master = required_mapping(created.get("master_curve_output"), "DMA master curve output")
    fit_policy = required_mapping(reference.get("fit_policy"), "DMA fit policy")
    bounds = cast(list[dict[str, Any]], fit_policy.get("bounds"))
    plan = response_json(
        client.post(
            "/linear-viscoelastic-calibration-plans/from-processing-output",
            json={
                "processing_output": {
                    "id": master["output_id"],
                    "revision_id": master["revision_id"],
                },
                "availability": {
                    "ramp": "NOT_PROVIDED",
                    "sweep": "PROVIDED",
                    "preconditioning": "NOT_PROVIDED",
                    "linear_range": "NOT_PROVIDED",
                },
                "recommendation_policy": LINEAR_VISCOELASTIC_RECOMMENDATION_POLICY,
                "term_counts": fit_policy["term_counts"],
                "parameter_bounds": {"1": bounds},
                "start_vectors": {"1": [[item["start"] for item in bounds]]},
                "weights": fit_policy["weights"],
                "optimizer": fit_policy["optimizer"],
                "change_reason": "Create explicit Prony calibration Plan from DMA TTS output",
            },
            headers={"Idempotency-Key": "dma-temperature-sweep-calibration-plan"},
        )
    )
    plan_id = required_string(plan.get("plan_id"), "DMA plan_id")
    plan_revision = required_mapping(plan.get("current_revision"), "DMA plan revision")
    plan_revision_id = required_string(plan_revision.get("id"), "DMA plan revision.id")
    accepted = response_json(
        client.post(
            f"/linear-viscoelastic-calibration-plans/{plan_id}/runs",
            json={
                "plan_revision_id": plan_revision_id,
                "change_reason": "Execute Prony calibration from fixed-frequency DMA TTS",
            },
            headers={"Idempotency-Key": "dma-temperature-sweep-calibration-run"},
        )
    )
    run_id = required_string(accepted.get("run_id"), "DMA run_id")
    _run_until_succeeded(client, run_id=run_id, label="DMA TTS calibration")
    recommendation = response_json(
        client.get(f"/linear-viscoelastic-calibration-runs/{run_id}/recommendation")
    )
    selection = response_json(
        client.post(
            "/linear-viscoelastic-calibration-selections",
            json={
                "plan_revision_id": plan_revision_id,
                "run_id": run_id,
                "candidate_id": recommendation["candidate_id"],
                "candidate_sha256": recommendation["candidate_digest"],
                "reason": "Engineer selected the exact synthetic-reference recommendation",
                "warning_acknowledgements": [],
                "change_reason": "Record explicit DMA TTS Prony candidate selection",
            },
            headers={"Idempotency-Key": "dma-temperature-sweep-calibration-selection"},
        )
    )
    selection_id = required_string(selection.get("selection_id"), "DMA selection_id")
    reloaded_plan = response_json(client.get(f"/linear-viscoelastic-calibration-plans/{plan_id}"))
    reloaded_run = response_json(client.get(f"/linear-viscoelastic-calibration-runs/{run_id}"))
    reloaded_selection = response_json(
        client.get(f"/linear-viscoelastic-calibration-selections/{selection_id}")
    )
    reloaded_content = required_mapping(
        required_mapping(reloaded_plan.get("current_revision"), "reloaded DMA Plan revision").get(
            "content"
        ),
        "reloaded DMA Plan content",
    )
    output_pin = required_mapping(
        reloaded_content.get("processing_output"), "reloaded processing output pin"
    )
    if (
        revision_id(reloaded_plan) != plan_revision_id
        or reloaded_run.get("run_id") != run_id
        or reloaded_run.get("status") != "succeeded"
        or reloaded_selection.get("selection_id") != selection_id
        or output_pin.get("id") != master["output_id"]
        or output_pin.get("revision_id") != master["revision_id"]
        or output_pin.get("sha256") != master["content_sha256"]
    ):
        raise LinearViscoelasticAcceptanceError(
            "DMA Processing Output, Plan, Run, or Selection changed during API reload"
        )
    return {
        "test_data_id": test_data["test_data_document_id"],
        "test_data_revision_id": test_revision["id"],
        "processing_output_id": master["output_id"],
        "processing_output_revision_id": master["revision_id"],
        "processing_output_sha256": master["content_sha256"],
        "plan_id": plan_id,
        "plan_revision_id": plan_revision_id,
        "run_id": run_id,
        "selection_id": selection_id,
        "selected_candidate_id": recommendation["candidate_id"],
        "non_production": True,
    }


def verify(api_base_url: str, package_root: Path) -> dict[str, Any]:
    """Run the synthetic relaxation journey from package registration through IR reload."""

    from cmp.tools.linear_viscoelastic_acceptance_http import authenticated_client

    with authenticated_client(api_base_url) as client:
        package = register_calibrator(client, package_root)
        test_data, catalog = create_governed_relaxation_test_data(client)
        result = execute_synthetic_relaxation(client, test_data, catalog)
        return {
            "package_id": package["package_id"],
            "package_digest": package["package_digest"],
            "test_data_id": test_data["test_data_document_id"],
            "test_data_revision_id": revision_id(test_data),
            **result,
        }


def verify_public_shear_dma(
    api_base_url: str,
    package_root: Path,
    fixture_path: Path,
    manifest_path: Path | None = None,
) -> dict[str, Any]:
    """Run public fixture ingestion and calibration without static-property promotion."""

    from cmp.tools.linear_viscoelastic_acceptance_http import authenticated_client

    with authenticated_client(api_base_url) as client:
        package = register_calibrator(client, package_root)
        test_data, catalog = create_public_shear_dma_test_data(
            client,
            fixture_path=fixture_path,
            manifest_path=manifest_path,
        )
        result = execute_public_shear_dma(
            client,
            test_data=test_data,
            point_count=int(catalog["fixture_row_count"]),
            selected_temperature_k=float(catalog["selected_temperature_k"]),
            source_file_id=str(catalog["source_file_id"]),
            record=required_mapping(catalog.get("fixture_record"), "fixture record"),
        )
        source_provenance = required_mapping(catalog.get("source_provenance"), "source provenance")
        return {
            "role": "public_reference_shear_dma_frequency_sweep",
            "package_id": package["package_id"],
            "package_digest": package["package_digest"],
            "source_provenance": source_provenance,
            **result,
        }


def verify_dma_temperature_sweep(
    api_base_url: str,
    package_root: Path,
    fixture_path: Path,
) -> dict[str, Any]:
    """Run the fixture-backed DMA temperature sweep through Selection read-back."""

    from cmp.tools.linear_viscoelastic_acceptance_http import authenticated_client

    with authenticated_client(api_base_url) as client:
        package = register_calibrator(client, package_root)
        test_data, catalog = create_governed_dma_temperature_sweep(client, fixture_path)
        result = execute_synthetic_dma_temperature_sweep(
            client,
            test_data=test_data,
            catalog=catalog,
        )
        return {
            "role": "synthetic_fixed_frequency_dma_tts_prony",
            "package_id": package["package_id"],
            "package_digest": package["package_digest"],
            **result,
        }


def verify_dma_readback(
    api_base_url: str,
    *,
    processing_output_id: str,
    processing_output_revision_id: str,
    processing_output_sha256: str,
    plan_id: str,
    plan_revision_id: str,
    run_id: str,
    selection_id: str,
) -> dict[str, Any]:
    """Reload the exact DMA evidence through a new API session after restart."""

    from cmp.tools.linear_viscoelastic_acceptance_http import authenticated_client

    with authenticated_client(api_base_url) as client:
        outputs = response_items(response_json(client.get("/processing-outputs")))
        output = next(
            (item for item in outputs if item.get("processing_output_id") == processing_output_id),
            None,
        )
        if output is None:
            raise LinearViscoelasticAcceptanceError("saved DMA Processing Output is absent")
        output_revision = required_mapping(
            output.get("current_revision"), "DMA Processing Output revision"
        )
        plan = response_json(client.get(f"/linear-viscoelastic-calibration-plans/{plan_id}"))
        run = response_json(client.get(f"/linear-viscoelastic-calibration-runs/{run_id}"))
        selection = response_json(
            client.get(f"/linear-viscoelastic-calibration-selections/{selection_id}")
        )
        plan_revision = required_mapping(plan.get("current_revision"), "DMA Plan revision")
        plan_content = required_mapping(plan_revision.get("content"), "DMA Plan content")
        output_pin = required_mapping(plan_content.get("processing_output"), "DMA output pin")
        if (
            output_revision.get("id") != processing_output_revision_id
            or output_revision.get("content_hash") != processing_output_sha256
            or plan_revision.get("id") != plan_revision_id
            or output_pin.get("id") != processing_output_id
            or output_pin.get("revision_id") != processing_output_revision_id
            or output_pin.get("sha256") != processing_output_sha256
            or run.get("run_id") != run_id
            or run.get("status") != "succeeded"
            or selection.get("selection_id") != selection_id
        ):
            raise LinearViscoelasticAcceptanceError(
                "restarted API changed exact DMA Processing Output, Plan, Run, or Selection"
            )
    return {
        "processing_output_id": processing_output_id,
        "processing_output_revision_id": processing_output_revision_id,
        "processing_output_sha256": processing_output_sha256,
        "plan_id": plan_id,
        "plan_revision_id": plan_revision_id,
        "run_id": run_id,
        "selection_id": selection_id,
        "restarted_api_readback": True,
    }


def verify_readback(
    api_base_url: str,
    *,
    material_model_id: str,
    material_model_revision_id: str,
    material_model_sha256: str,
) -> dict[str, Any]:
    """Read one promoted immutable revision through a freshly addressed API session."""

    from cmp.tools.linear_viscoelastic_acceptance_http import authenticated_client

    with authenticated_client(api_base_url) as client:
        reloaded = response_json(client.get(f"/linear-viscoelastic-models/{material_model_id}"))
    revision = required_mapping(reloaded.get("current_revision"), "model revision")
    content = required_mapping(revision.get("content"), "model content")
    evidence = required_mapping(
        content.get("calibration_promotion_evidence"), "calibration promotion evidence"
    )
    test_data_evidence = required_mapping(
        evidence.get("canonical_test_data"), "canonical Test Data evidence"
    )
    if (
        revision.get("id") != material_model_revision_id
        or revision.get("content_hash") != material_model_sha256
        or revision.get("schema_version") != "1.4.0"
        or content.get("non_production") is not True
        or not test_data_evidence.get("revision_id")
    ):
        raise LinearViscoelasticAcceptanceError(
            "restarted API did not reload the exact saved IR revision"
        )
    return {
        "material_model_id": material_model_id,
        "material_model_revision_id": material_model_revision_id,
        "material_model_sha256": material_model_sha256,
        "restarted_api_readback": True,
    }

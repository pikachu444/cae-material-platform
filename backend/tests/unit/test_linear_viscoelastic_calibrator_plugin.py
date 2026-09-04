from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import math
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pyarrow as pa
import pyarrow.parquet as pq
from cmp.modules.exporting.domain.reference_linear_viscoelasticity import (
    render_abaqus_linear_viscoelastic_card,
)
from cmp.modules.jobs.application.linear_viscoelastic_calibration import (
    build_linear_viscoelastic_job_spec,
    linear_viscoelastic_deadline,
)
from cmp.modules.modeling.domain.linear_viscoelastic_calibration import (
    LINEAR_VISCOELASTIC_RECOMMENDATION_POLICY,
)
from cmp.modules.modeling.domain.reference_linear_viscoelasticity import (
    BulkRelaxationStatus,
    PronyTerm,
    ReferenceLinearViscoelasticContent,
)
from cmp.modules.processing.domain.dma_frequency_master_curve import (
    DmaPartition,
    DmaRowDisposition,
    DmaTemperatureSweepRow,
    TabulatedShiftLaw,
    build_frequency_master_curve,
    frequency_master_curve_parquet_bytes,
)
from cmp_plugin_sdk import ExtensionStatus, RunContext, RunnerJobSpec
from cmp_plugin_sdk.context import InputBinding, OutputRule

ROOT = Path(__file__).parents[3]
DMA_TTS_REFERENCE_PATH = (
    ROOT / "fixtures/synthetic/dma-temperature-sweep-linear-viscoelastic-v1.json"
)
PLUGIN_PATH = (
    ROOT
    / "plugins/production/linear_viscoelastic_calibrator/linear_viscoelastic_calibrator/plugin.py"
)
_spec = importlib.util.spec_from_file_location("test_linear_viscoelastic_calibrator", PLUGIN_PATH)
assert _spec is not None and _spec.loader is not None
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)


def test_plugin_descriptor_job_validation_and_normalized_float64_boundary() -> None:
    plugin = _module.LinearViscoelasticCalibrator()
    descriptor = plugin.describe()
    assert descriptor.extension_type.value == "calibrator"
    assert descriptor.capabilities == ("generalized-maxwell-shear",)
    spec, _ = build_linear_viscoelastic_job_spec(
        job_id=UUID(int=1),
        attempt_id=UUID(int=2),
        run_id=UUID(int=3),
        plan_revision_id=UUID(int=4),
        plan_sha256="a" * 64,
        plan_artifact_id=UUID(int=5),
        canonical_test_data_revision_id=UUID(int=6),
        canonical_test_data_artifact_id=UUID(int=7),
        canonical_test_data_sha256="b" * 64,
        normalized_test_data_revision_id=UUID(int=8),
        normalized_test_data_artifact_id=UUID(int=9),
        normalized_test_data_sha256="c" * 64,
        package_sha256="d" * 64,
        recommendation_policy=LINEAR_VISCOELASTIC_RECOMMENDATION_POLICY,
        deadline=linear_viscoelastic_deadline(datetime.now(UTC)),
        traceparent="00-00000000000000000000000000000001-0000000000000001-01",
    )
    job = RunnerJobSpec.from_validated_document(spec.document())
    assert plugin.validate_job(job).accepted
    assert job.config["recommendation_policy"] == LINEAR_VISCOELASTIC_RECOMMENDATION_POLICY
    stream = io.BytesIO()
    # pyarrow has no usable write_table stub in this environment.
    pq.write_table(  # type: ignore[no-untyped-call]
        pa.table(
            {
                "elapsed": pa.array([0.1, 0.2, 0.3], type=pa.float64()),
                "relaxation_modulus": pa.array([3.0, 2.0, 1.0], type=pa.float64()),
            }
        ),
        stream,
    )
    canonical = {
        "channels": [
            {
                "key": "elapsed",
                "quantity_semantics": "time.elapsed",
                "axis_role": "independent",
                "original_unit_string": "s",
                "normalized_unit": "s",
                "normalization": {"scale": "1", "offset": "0"},
                "normalized_values": ["0.1", "0.2", "0.3"],
            },
            {
                "key": "relaxation_modulus",
                "quantity_semantics": "mechanics.modulus.shear.relaxation",
                "axis_role": "dependent",
                "original_unit_string": "MPa",
                "normalized_unit": "Pa",
                "normalization": {"scale": "1000000", "offset": "0"},
                "normalized_values": ["3", "2", "1"],
            },
        ]
    }
    plan = {
        "input_semantics": {
            "mode": "relaxation",
            "deformation_mode": "shear",
            "channels": [
                {
                    "key": "elapsed",
                    "quantity_semantics": "time.elapsed",
                    "axis_role": "independent",
                    "original_unit_string": "s",
                    "normalized_unit": "s",
                },
                {
                    "key": "relaxation_modulus",
                    "quantity_semantics": "mechanics.modulus.shear.relaxation",
                    "axis_role": "dependent",
                    "original_unit_string": "MPa",
                    "normalized_unit": "Pa",
                },
            ],
            "point_dispositions": [
                {
                    "ordinal": index,
                    "partition": "CALIBRATION",
                    "exclusion_reason": None,
                }
                for index in range(3)
            ],
            "selected_temperature_k": "298.15",
        }
    }
    mode, decoded = _module._normalized_observations(stream.getvalue(), canonical, plan)
    assert mode == "relaxation"
    assert [row["time_s"] for row in decoded] == [0.1, 0.2, 0.3]


def test_plugin_runs_actual_canonical_test_data_to_three_declared_outputs(
    tmp_path: Path,
) -> None:
    times = [0.1, 0.3, 1.0, 3.0, 10.0, 30.0]
    modulus = [1_000_000.0 + 2_000_000.0 * math.exp(-value) for value in times]
    canonical = {
        "channels": [
            {
                "key": "elapsed",
                "quantity_semantics": "time.elapsed",
                "axis_role": "independent",
                "original_unit_string": "s",
                "normalized_unit": "s",
                "normalization": {"scale": "1", "offset": "0"},
                "normalized_values": [str(value) for value in times],
            },
            {
                "key": "relaxation_modulus",
                "quantity_semantics": "mechanics.modulus.shear.relaxation",
                "axis_role": "dependent",
                "original_unit_string": "MPa",
                "normalized_unit": "Pa",
                "normalization": {"scale": "1000000", "offset": "0"},
                "normalized_values": [str(value) for value in modulus],
            },
        ]
    }
    plan = {
        "input_semantics": {
            "mode": "relaxation",
            "deformation_mode": "shear",
            "channels": [
                {
                    "key": "elapsed",
                    "quantity_semantics": "time.elapsed",
                    "axis_role": "independent",
                    "original_unit_string": "s",
                    "normalized_unit": "s",
                },
                {
                    "key": "relaxation_modulus",
                    "quantity_semantics": "mechanics.modulus.shear.relaxation",
                    "axis_role": "dependent",
                    "original_unit_string": "MPa",
                    "normalized_unit": "Pa",
                },
            ],
            "point_dispositions": [
                {
                    "ordinal": index,
                    "partition": "HOLDOUT" if index == len(times) - 1 else "CALIBRATION",
                    "exclusion_reason": None,
                }
                for index in range(len(times))
            ],
            "selected_temperature_k": "298.15",
        },
        "recommendation_policy": LINEAR_VISCOELASTIC_RECOMMENDATION_POLICY,
        "term_counts": [1],
        "parameter_bounds": {
            "1": [
                {
                    "name": "G_inf_pa",
                    "lower": "100000",
                    "start": "900000",
                    "upper": "5000000",
                    "unit": "Pa",
                    "transform": "ln",
                },
                {
                    "name": "G_1_pa",
                    "lower": "100000",
                    "start": "1800000",
                    "upper": "5000000",
                    "unit": "Pa",
                    "transform": "ln",
                },
                {
                    "name": "tau_1_s",
                    "lower": "0.01",
                    "start": "0.8",
                    "upper": "100",
                    "unit": "s",
                    "transform": "ln",
                },
            ]
        },
        "start_vectors": {"1": [["900000", "1800000", "0.8"]]},
        "weights": {
            "relaxation_scale_pa": "1000000",
            "dma_storage_weight": "0.5",
            "dma_loss_weight": "0.5",
            "dma_storage_scale_pa": "1000000",
            "dma_loss_scale_pa": "1000000",
        },
        "optimizer": {
            "ftol": 1e-10,
            "xtol": 1e-10,
            "gtol": 1e-10,
            "max_nfev": 2000,
        },
    }
    plan_payload = json.dumps(plan, separators=(",", ":"), sort_keys=True).encode()
    canonical_payload = json.dumps(canonical, separators=(",", ":"), sort_keys=True).encode()
    normalized_stream = io.BytesIO()
    # pyarrow has no usable write_table stub in this environment.
    pq.write_table(  # type: ignore[no-untyped-call]
        pa.table(
            {
                "elapsed": pa.array(times, type=pa.float64()),
                "relaxation_modulus": pa.array(modulus, type=pa.float64()),
            }
        ),
        normalized_stream,
    )
    normalized_payload = normalized_stream.getvalue()
    payloads = {
        "calibration.plan": plan_payload,
        "test-data.canonical": canonical_payload,
        "test-data.normalized": normalized_payload,
    }
    paths: dict[str, Path] = {}
    for role, payload in payloads.items():
        path = tmp_path / f"{role}.bin"
        path.write_bytes(payload)
        paths[role] = path
    spec, _ = build_linear_viscoelastic_job_spec(
        job_id=UUID(int=11),
        attempt_id=UUID(int=12),
        run_id=UUID(int=13),
        plan_revision_id=UUID(int=14),
        plan_sha256=hashlib.sha256(plan_payload).hexdigest(),
        plan_artifact_id=UUID(int=15),
        canonical_test_data_revision_id=UUID(int=16),
        canonical_test_data_artifact_id=UUID(int=17),
        canonical_test_data_sha256=hashlib.sha256(canonical_payload).hexdigest(),
        normalized_test_data_revision_id=UUID(int=18),
        normalized_test_data_artifact_id=UUID(int=19),
        normalized_test_data_sha256=hashlib.sha256(normalized_payload).hexdigest(),
        package_sha256="d" * 64,
        recommendation_policy=LINEAR_VISCOELASTIC_RECOMMENDATION_POLICY,
        deadline=linear_viscoelastic_deadline(datetime.now(UTC)),
        traceparent="00-00000000000000000000000000000001-0000000000000001-01",
    )
    job = RunnerJobSpec.from_validated_document(spec.document())
    media_types = {
        "calibration.plan": "application/json",
        "test-data.canonical": "application/vnd.cmp.test-data+json",
        "test-data.normalized": "application/vnd.apache.parquet",
    }
    bindings = tuple(
        InputBinding(
            role,
            item.artifact_id,
            hashlib.sha256(payloads[role]).hexdigest(),
            media_types[role],
            paths[role],
            len(payloads[role]),
        )
        for role, item in ((item.role, item) for item in job.inputs)
    )
    output = tmp_path / "outputs"
    workspace = tmp_path / "workspace"
    output.mkdir()
    workspace.mkdir()
    output_media = {
        "calibration.run-result": "application/json",
        "response-residuals": "application/vnd.apache.parquet",
        "objective-history": "application/vnd.apache.parquet",
    }
    context = RunContext(
        job=job,
        inputs=bindings,
        output_rules=tuple(
            OutputRule(item.role, item.schema_ref, (output_media[item.role],), 32_000_000)
            for item in job.expected_outputs
        ),
        output_root=output,
        workspace_root=workspace,
        cancellation_marker=workspace / "cancel.requested",
        max_total_output_bytes=96_000_000,
    )

    outcome = _module.LinearViscoelasticCalibrator().run(context, job)

    assert outcome.status is ExtensionStatus.SUCCEEDED
    assert {item.role for item in context.outputs} == set(output_media)
    result_output = next(item for item in context.outputs if item.role == "calibration.run-result")
    result = json.loads(result_output.path.read_bytes())
    assert result["status"] == "succeeded"
    assert result["plan_revision_id"] == str(UUID(int=14))
    assert result["candidates"][0]["term_count"] == 1
    assert len(result["candidates"][0]["holdout_residuals"]) == 1


def test_plugin_fits_exact_dma_tts_processing_output(tmp_path: Path) -> None:
    reference = json.loads(DMA_TTS_REFERENCE_PATH.read_bytes())
    source = reference["input"]
    source_rows = source["rows"]
    frequency_hz = float(source["frequency"]["value"])
    result_rows = build_frequency_master_curve(
        tuple(
            DmaTemperatureSweepRow(
                source_ordinal=int(row["source_ordinal"]),
                temperature_k=float(row["temperature_k"]),
                frequency_hz=frequency_hz,
                storage_modulus_pa=float(row["storage_modulus_pa"]),
                loss_modulus_pa=float(row["loss_modulus_pa"]),
            )
            for row in source_rows
        ),
        tuple(
            DmaRowDisposition(int(row["source_ordinal"]), DmaPartition(row["partition"]))
            for row in source_rows
        ),
        TabulatedShiftLaw(
            float(source["shift_law"]["reference_temperature_k"]),
            tuple((float(row["temperature_k"]), float(row["log10_a_t"])) for row in source_rows),
        ),
        confirmed=True,
        confirmation_reason="Use the fixture-declared exact tabulated shifts",
    )
    truth = reference["closed_form_truth"]
    truth_term = truth["terms"][0]
    fit_policy = reference["fit_policy"]
    relative_tolerance = float(reference["acceptance_tolerances"]["fitted_parameter_relative"])
    processed_payload = frequency_master_curve_parquet_bytes(result_rows)
    result_artifact_id = UUID(int=31)
    result_sha = hashlib.sha256(processed_payload).hexdigest()
    normalized_payload = b"exact-source-parquet-is-staged-but-processed-result-is-consumed"
    normalized_sha = hashlib.sha256(normalized_payload).hexdigest()
    manual_table = [
        {
            "temperature_k": float(row["temperature_k"]),
            "log10_a_t": float(row["log10_a_t"]),
        }
        for row in source_rows
    ]
    metadata = {
        "document_type": "cmp.processing-output",
        "document_version": "1.6.0",
        "output_id": str(UUID(int=21)),
        "step": {
            "method_id": "polymer.dma_frequency_master_curve",
            "method_version": "1.0.0",
            "options": {
                "input_mode": "fixed_frequency_temperature_sweep",
                "source_normalized_artifact_id": str(UUID(int=48)),
                "source_normalized_artifact_sha256": normalized_sha,
                "result_row_count": len(result_rows),
                "frequency_conversion": "omega_rad_per_s=2*pi*frequency_hz",
                "shift_direction": "omega_reduced=omega*10**log10_a_t",
                "log_base": 10,
                "reference": {
                    "source_sweep_ordinal": None,
                    "source_ordinal": 3,
                    "representative_temperature_k": 293.15,
                },
                "shift_law": {
                    "kind": "manual_tabulated",
                    "reference_temperature_k": 293.15,
                    "parameter_source": "supplied",
                    "manual_table": manual_table,
                },
                "scoring": None,
                "adjacent_optimizer": None,
                "law_optimizer": None,
                "residual_summary": None,
                "application_range": None,
                "recommendation": {
                    "recommendation_sha256": "d" * 64,
                    "rule_id": "cmp.processing.dma_tts.synthetic_test",
                    "rule_version": "1.0.0",
                },
                "assessment": {
                    "adequacy": "not_assessed",
                    "uncertainty": "not_provided",
                    "identifiability": "not_assessed",
                    "production_readiness": "non_production",
                },
                "warnings": [
                    "DMA_TTS_LVR_EVIDENCE_MISSING",
                    "DMA_TTS_TEMPERATURE_EQUILIBRIUM_EVIDENCE_MISSING",
                    "DMA_TTS_PRECONDITIONING_EVIDENCE_MISSING",
                ],
            },
        },
        "result_artifact": {
            "artifact_id": str(result_artifact_id),
            "sha256": result_sha,
            "schema_ref": "urn:cmp:processing:dma-frequency-master-curve-parquet:1.0.0",
            "media_type": "application/vnd.apache.parquet",
        },
    }
    metadata_payload = json.dumps(metadata, separators=(",", ":"), sort_keys=True).encode()
    metadata_sha = hashlib.sha256(metadata_payload).hexdigest()
    dispositions = [
        {
            "ordinal": ordinal,
            "partition": row.partition.value,
            "exclusion_reason": None,
        }
        for ordinal, row in enumerate(
            row for row in result_rows if row.partition is DmaPartition.CALIBRATION
        )
    ]
    plan = {
        "processing_output": {
            "id": str(UUID(int=21)),
            "revision_id": str(UUID(int=22)),
            "sha256": "a" * 64,
        },
        "processing_metadata_artifact": {
            "artifact_id": str(UUID(int=30)),
            "sha256": metadata_sha,
            "media_type": "application/vnd.cmp.processing-output+json",
        },
        "processing_result_artifact": {
            "artifact_id": str(result_artifact_id),
            "sha256": result_sha,
            "media_type": "application/vnd.apache.parquet",
        },
        "input_semantics": {
            "mode": "dma_frequency_master_curve",
            "deformation_mode": "shear",
            "source_kind": "processing_output",
            "processing_method": "polymer.dma_frequency_master_curve@1.0.0",
            "frequency_kind": "reduced_angular_rad_per_s",
            "angular_frequency_conversion": (
                "omega_reduced_rad_per_s=omega_rad_per_s*shift_factor;"
                "frequency_reduced_hz=omega_reduced_rad_per_s/(2*pi)"
            ),
            "dma_domain_policy": "nondecreasing_observations",
            "point_dispositions": dispositions,
        },
        "recommendation_policy": LINEAR_VISCOELASTIC_RECOMMENDATION_POLICY,
        "term_counts": fit_policy["term_counts"],
        "parameter_bounds": {
            "1": [
                {"name": item["name"], "lower": item["lower"], "upper": item["upper"]}
                for item in fit_policy["bounds"]
            ]
        },
        "start_vectors": {"1": [[item["start"] for item in fit_policy["bounds"]]]},
        "weights": fit_policy["weights"],
        "optimizer": fit_policy["optimizer"],
    }
    plan_payload = json.dumps(plan, separators=(",", ":"), sort_keys=True).encode()
    canonical_payload = b"{}"
    payloads = {
        "calibration.plan": plan_payload,
        "test-data.canonical": canonical_payload,
        "test-data.normalized": normalized_payload,
        "processing-output.metadata": metadata_payload,
        "processing-output.result": processed_payload,
    }
    paths: dict[str, Path] = {}
    for role, payload in payloads.items():
        path = tmp_path / f"{role}.bin"
        path.write_bytes(payload)
        paths[role] = path
    spec, _ = build_linear_viscoelastic_job_spec(
        job_id=UUID(int=41),
        attempt_id=UUID(int=42),
        run_id=UUID(int=43),
        plan_revision_id=UUID(int=44),
        plan_sha256=hashlib.sha256(plan_payload).hexdigest(),
        plan_artifact_id=UUID(int=45),
        canonical_test_data_revision_id=UUID(int=46),
        canonical_test_data_artifact_id=UUID(int=47),
        canonical_test_data_sha256=hashlib.sha256(canonical_payload).hexdigest(),
        normalized_test_data_revision_id=UUID(int=46),
        normalized_test_data_artifact_id=UUID(int=48),
        normalized_test_data_sha256=hashlib.sha256(normalized_payload).hexdigest(),
        package_sha256="d" * 64,
        recommendation_policy=LINEAR_VISCOELASTIC_RECOMMENDATION_POLICY,
        deadline=linear_viscoelastic_deadline(datetime.now(UTC)),
        traceparent="00-00000000000000000000000000000001-0000000000000001-01",
        processing_output_revision_id=UUID(int=22),
        processing_metadata_artifact_id=UUID(int=30),
        processing_metadata_sha256=metadata_sha,
        processing_result_artifact_id=result_artifact_id,
        processing_result_sha256=result_sha,
    )
    job = RunnerJobSpec.from_validated_document(spec.document())
    assert _module.LinearViscoelasticCalibrator().validate_job(job).accepted
    media_types = {
        "calibration.plan": "application/json",
        "test-data.canonical": "application/vnd.cmp.test-data+json",
        "test-data.normalized": "application/vnd.apache.parquet",
        "processing-output.metadata": "application/vnd.cmp.processing-output+json",
        "processing-output.result": "application/vnd.apache.parquet",
    }
    bindings = tuple(
        InputBinding(
            item.role,
            item.artifact_id,
            hashlib.sha256(payloads[item.role]).hexdigest(),
            media_types[item.role],
            paths[item.role],
            len(payloads[item.role]),
        )
        for item in job.inputs
    )
    output = tmp_path / "outputs"
    workspace = tmp_path / "workspace"
    output.mkdir()
    workspace.mkdir()
    output_media = {
        "calibration.run-result": "application/json",
        "response-residuals": "application/vnd.apache.parquet",
        "objective-history": "application/vnd.apache.parquet",
    }
    context = RunContext(
        job=job,
        inputs=bindings,
        output_rules=tuple(
            OutputRule(item.role, item.schema_ref, (output_media[item.role],), 32_000_000)
            for item in job.expected_outputs
        ),
        output_root=output,
        workspace_root=workspace,
        cancellation_marker=workspace / "cancel.requested",
        max_total_output_bytes=96_000_000,
    )

    outcome = _module.LinearViscoelasticCalibrator().run(context, job)

    assert outcome.status is ExtensionStatus.SUCCEEDED
    result_output = next(item for item in context.outputs if item.role == "calibration.run-result")
    fit = json.loads(result_output.path.read_bytes())
    assert fit["status"] == "succeeded"
    candidate = fit["candidates"][0]
    assert candidate["term_count"] == 1
    assert len(candidate["holdout_residuals"]) == 2
    assert math.isclose(
        candidate["physical_parameters"][0],
        float(truth["g_inf_pa"]),
        rel_tol=relative_tolerance,
    )
    assert math.isclose(
        candidate["physical_parameters"][1],
        float(truth_term["g_i_pa"]),
        rel_tol=relative_tolerance,
    )
    assert math.isclose(
        candidate["physical_parameters"][2],
        float(truth_term["tau_i_s"]),
        rel_tol=relative_tolerance,
    )
    fitted_g_inf, fitted_g_1, fitted_tau = candidate["physical_parameters"]
    instantaneous_shear = fitted_g_inf + fitted_g_1
    static = reference["static_properties"]
    export = reference["export"]
    source_properties = ReferenceLinearViscoelasticContent(
        material_id=UUID(int=51),
        material_revision_id=UUID(int=52),
        material_state_id=UUID(int=53),
        material_state_revision_id=UUID(int=54),
        property_set_id=UUID(int=55),
        property_set_revision_id=UUID(int=56),
        density_kg_per_m3=float(static["density_kg_per_m3"]),
        youngs_modulus_pa=float(static["youngs_modulus_pa"]),
        poisson_ratio=float(static["poisson_ratio"]),
        bulk_relaxation_status=BulkRelaxationStatus(static["bulk_relaxation_status"]),
        terms=(PronyTerm(fitted_g_1 / instantaneous_shear, 0.0, fitted_tau),),
    )
    card = render_abaqus_linear_viscoelastic_card(
        material_name=export["material_name"],
        source=source_properties,
    )
    golden = ROOT / export["golden_card_path"]
    expected_prony = reference["expected_prony"]["terms"][0]
    expected_card = render_abaqus_linear_viscoelastic_card(
        material_name=export["material_name"],
        source=replace(
            source_properties,
            terms=(
                PronyTerm(
                    float(expected_prony["shear_ratio"]),
                    float(expected_prony["bulk_ratio"]),
                    float(expected_prony["relaxation_time_s"]),
                ),
            ),
        ),
    )
    assert expected_card == golden.read_text(encoding="utf-8")
    actual_prony = tuple(float(value.strip()) for value in card.splitlines()[-1].split(","))
    assert math.isclose(
        actual_prony[0], float(expected_prony["shear_ratio"]), rel_tol=relative_tolerance
    )
    assert actual_prony[1] == 0.0
    assert math.isclose(
        actual_prony[2],
        float(expected_prony["relaxation_time_s"]),
        rel_tol=relative_tolerance,
    )

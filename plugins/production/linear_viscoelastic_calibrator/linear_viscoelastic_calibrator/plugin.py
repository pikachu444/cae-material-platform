"""Isolated generalized-Maxwell shear calibrator entrypoint.

The package deliberately talks to the platform only through ``cmp_plugin_sdk``.  It reads
the exact Plan/canonical/normalized bindings staged by T-18 and writes the three declared
result artifacts.  No network, ambient filesystem, or platform service import is used.
"""

from __future__ import annotations

import hashlib
import io
import json
import math
from typing import Any
from uuid import NAMESPACE_URL, uuid5

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
from cmp_plugin_sdk import (
    Diagnostic,
    DiagnosticSeverity,
    ExtensionDescriptor,
    ExtensionOutcome,
    ExtensionStatus,
    ExtensionType,
    RunContext,
    RunnerJobSpec,
    ValidationReport,
)
from scipy.optimize import least_squares

PLUGIN_ID = "cmp.linear_viscoelastic.calibrator"
PLUGIN_VERSION = "1.0.0"
RESULT_SCHEMA = "urn:cmp:modeling:linear-viscoelastic-calibration-result:1.0.0"
RESIDUAL_SCHEMA = "urn:cmp:modeling:linear-viscoelastic-calibration-response-residuals:1.0.0"
HISTORY_SCHEMA = "urn:cmp:modeling:linear-viscoelastic-calibration-objective-history:1.0.0"
CONFIG_SCHEMA = "urn:cmp:plugin:linear-viscoelastic-calibrator:config:1.0.0"
RECOMMENDATION_POLICY = "lowest_bic_then_term_count_then_attempt_ordinal@1.0.0"
DMA_MASTER_CURVE_SCHEMA = "urn:cmp:processing:dma-frequency-master-curve-parquet:1.0.0"
DMA_MASTER_CURVE_COLUMNS = (
    "source_ordinal",
    "temperature_k",
    "source_frequency_hz",
    "angular_frequency_rad_per_s",
    "log10_a_t",
    "shift_factor",
    "reduced_angular_frequency_rad_per_s",
    "storage_modulus_pa",
    "loss_modulus_pa",
    "partition",
    "exclusion_reason",
)


def _error(code: str, message: str) -> Diagnostic:
    return Diagnostic(code, DiagnosticSeverity.ERROR, message)


def _recommendation_key(item: dict[str, Any], policy: object) -> tuple[float, int, int]:
    """Apply the one serialized recommendation policy supported by this package."""

    if policy != RECOMMENDATION_POLICY:
        raise ValueError("unsupported recommendation policy")
    return (float(item["bic"]), int(item["term_count"]), int(item["attempt_ordinal"]))


def _parameter_names(term_count: int) -> tuple[str, ...]:
    return (
        "G_inf_pa",
        *(f"G_{index}_pa" for index in range(1, term_count + 1)),
        *(f"tau_{index}_s" for index in range(1, term_count + 1)),
    )


def _evaluate(
    term_count: int, parameters: np.ndarray, domain: np.ndarray, mode: str
) -> tuple[np.ndarray, np.ndarray | None]:
    g_inf = parameters[0]
    gi = parameters[1 : term_count + 1]
    taus = parameters[term_count + 1 :]
    if mode == "relaxation":
        return g_inf + np.sum(gi[:, None] * np.exp(-domain[None, :] / taus[:, None]), axis=0), None
    x = (2.0 * math.pi * domain)[None, :] * taus[:, None]
    storage = g_inf + np.sum(gi[:, None] * (x * x) / (1.0 + x * x), axis=0)
    loss = np.sum(gi[:, None] * x / (1.0 + x * x), axis=0)
    return storage, loss


def _load_plan(context: RunContext) -> dict[str, Any]:
    payload = context.read_input("calibration.plan", maximum_bytes=32 * 1024 * 1024)
    value = json.loads(payload.decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError("calibration Plan input must be a JSON object")
    return value


def _parquet_bytes(columns: dict[str, list[Any]]) -> bytes:
    """Create deterministic compact Parquet evidence for the generic Result Manifest."""

    table = pa.table(columns)
    stream = io.BytesIO()
    pq.write_table(table, stream, compression=None, version="2.6", write_statistics=False)
    return stream.getvalue()


def _float64_column(table: pa.Table, names: tuple[str, ...]) -> list[float]:
    """Read one exact float64 normalized channel, accepting governed aliases only."""

    name = next((candidate for candidate in names if candidate in table.column_names), None)
    if name is None:
        raise ValueError(f"normalized Parquet is missing one of {names!r}")
    column = table.column(name)
    if not pa.types.is_float64(column.type):
        raise ValueError(f"normalized Parquet column {name!r} must be float64")
    values = [float(item) for item in column.to_pylist()]
    if any(not math.isfinite(item) for item in values):
        raise ValueError(f"normalized Parquet column {name!r} contains a non-finite value")
    return values


def _normalized_observations(
    normalized: bytes,
    canonical: dict[str, Any],
    plan: dict[str, Any],
) -> tuple[str, list[dict[str, Any]]]:
    """Decode and cross-check normalized float64 arrays before numerical evaluation.

    Canonical Test Data supplies immutable quantity/unit rows, while the Plan supplies the
    engineer's explicit calibration/holdout/excluded decision for every source ordinal.
    Numeric vectors used by the optimizer are always loaded from normalized Parquet and
    cross-checked against the canonical JSON arrays by the server-resolved channel keys.
    """

    try:
        table = pq.read_table(pa.BufferReader(normalized))
    except Exception as error:
        raise ValueError("test-data.normalized is not a valid Parquet Artifact") from error
    semantics = plan.get("input_semantics")
    if not isinstance(semantics, dict):
        raise ValueError("Plan is missing server-resolved input_semantics")
    mode = semantics.get("mode")
    if mode not in {"relaxation", "dma"} or semantics.get("deformation_mode") != "shear":
        raise ValueError("Plan input mode or deformation mode is unsupported")
    channel_contracts = semantics.get("channels")
    dispositions = semantics.get("point_dispositions")
    canonical_channels = canonical.get("channels")
    if (
        not isinstance(channel_contracts, list)
        or not isinstance(dispositions, list)
        or not isinstance(canonical_channels, list)
    ):
        raise ValueError("Plan or canonical Test Data channel arrays are missing")
    by_key: dict[str, dict[str, Any]] = {}
    for value in canonical_channels:
        if not isinstance(value, dict) or not isinstance(value.get("key"), str):
            raise ValueError("canonical Test Data channel entry is invalid")
        key = value["key"]
        if key in by_key:
            raise ValueError("canonical Test Data channel keys are duplicated")
        by_key[key] = value
    active: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for contract in channel_contracts:
        if not isinstance(contract, dict) or not isinstance(contract.get("key"), str):
            raise ValueError("Plan input channel contract is invalid")
        source = by_key.get(contract["key"])
        if source is None:
            raise ValueError("Plan input channel key is absent from canonical Test Data")
        normalization = source.get("normalization")
        if not isinstance(normalization, dict):
            raise ValueError("canonical Test Data channel normalization is invalid")
        actual = (
            source.get("quantity_semantics"),
            source.get("axis_role"),
            source.get("original_unit_string"),
            source.get("normalized_unit"),
        )
        expected = (
            contract.get("quantity_semantics"),
            contract.get("axis_role"),
            contract.get("original_unit_string"),
            contract.get("normalized_unit"),
        )
        if actual != expected:
            raise ValueError("Plan input channel semantics differ from canonical Test Data")
        values = source.get("normalized_values")
        if not isinstance(values, list) or any(item is None for item in values):
            raise ValueError("canonical active channel normalized values are incomplete")
        active.append((contract, source))
    if not active:
        raise ValueError("Plan does not declare active governed channels")
    row_count = len(active[0][1]["normalized_values"])
    if (
        table.num_rows != row_count
        or len(dispositions) != row_count
        or any(len(source["normalized_values"]) != row_count for _, source in active)
    ):
        raise ValueError("Plan, Parquet, and canonical Test Data row counts differ")
    expected_semantics = (
        (
            ("time.elapsed", "independent", "s"),
            ("mechanics.modulus.shear.relaxation", "dependent", "Pa"),
        )
        if mode == "relaxation"
        else (
            ("physics.temperature", "independent", "K"),
            ("frequency.cyclic", "independent", "Hz"),
            ("mechanics.modulus.storage", "dependent", "Pa"),
            ("mechanics.modulus.loss", "dependent", "Pa"),
        )
    )
    actual_semantics = tuple(
        (
            contract.get("quantity_semantics"),
            contract.get("axis_role"),
            contract.get("normalized_unit"),
        )
        for contract, _ in active
    )
    if actual_semantics != expected_semantics:
        raise ValueError("Plan active channel quantity, role, or normalized unit is unsupported")
    values_by_semantics: dict[str, list[float]] = {}
    for contract, source in active:
        key = str(contract["key"])
        values = _float64_column(table, (key,))
        canonical_values = source["normalized_values"]
        if any(float(value) != values[index] for index, value in enumerate(canonical_values)):
            raise ValueError("normalized Parquet value differs from canonical Test Data")
        values_by_semantics[str(contract["quantity_semantics"])] = values
    if mode == "relaxation":
        columns = {
            "time_s": values_by_semantics["time.elapsed"],
            "modulus_pa": values_by_semantics["mechanics.modulus.shear.relaxation"],
        }
    else:
        columns = {
            "temperature_k": values_by_semantics["physics.temperature"],
            "frequency_hz": values_by_semantics["frequency.cyclic"],
            "storage_modulus_pa": values_by_semantics["mechanics.modulus.storage"],
            "loss_modulus_pa": values_by_semantics["mechanics.modulus.loss"],
        }
    metadata = table.schema.metadata or {}
    metadata_keys = tuple(metadata)
    if any(b"quantity_semantics" in key for key in metadata_keys):
        semantic_values = tuple(
            metadata[key] for key in metadata_keys if key.endswith(b"quantity_semantics")
        )
        required_semantics = tuple(
            str(contract["quantity_semantics"]).encode() for contract, _ in active
        )
        if not all(expected in semantic_values for expected in required_semantics):
            raise ValueError("normalized Parquet channel semantics do not match governed mode")
    result: list[dict[str, Any]] = []
    for index, disposition in enumerate(dispositions):
        if (
            not isinstance(disposition, dict)
            or disposition.get("ordinal") != index
            or disposition.get("partition") not in {"CALIBRATION", "HOLDOUT", "EXCLUDED"}
        ):
            raise ValueError("Plan point dispositions must cover every ordinal exactly once")
        row = {
            "ordinal": index,
            "partition": disposition["partition"],
            "exclusion_reason": disposition.get("exclusion_reason"),
        }
        for name, values in columns.items():
            row[name] = values[index]
        result.append(row)
    if mode == "dma":
        selected = float(semantics.get("selected_temperature_k"))
        if not math.isfinite(selected) or selected <= 0:
            raise ValueError("Plan selected DMA temperature is invalid")
        if any(
            row["temperature_k"] != selected and row["partition"] != "EXCLUDED" for row in result
        ):
            raise ValueError("DMA rows outside the selected temperature were not excluded")
    return mode, result


def _processed_dma_observations(
    result_bytes: bytes,
    metadata_bytes: bytes,
    plan: dict[str, Any],
) -> tuple[str, list[dict[str, Any]]]:
    """Decode one exact governed DMA TTS result and its serialized processing policy."""

    semantics = plan.get("input_semantics")
    output_pin = plan.get("processing_output")
    metadata_pin = plan.get("processing_metadata_artifact")
    result_pin = plan.get("processing_result_artifact")
    if not all(
        isinstance(value, dict) for value in (semantics, output_pin, metadata_pin, result_pin)
    ):
        raise ValueError("processed Plan is missing exact Processing Output evidence")
    assert isinstance(semantics, dict)
    assert isinstance(output_pin, dict)
    assert isinstance(metadata_pin, dict)
    assert isinstance(result_pin, dict)
    if (
        semantics.get("mode") != "dma_frequency_master_curve"
        or semantics.get("source_kind") != "processing_output"
        or semantics.get("processing_method") != "polymer.dma_frequency_master_curve@1.0.0"
        or semantics.get("frequency_kind") != "reduced_angular_rad_per_s"
        or semantics.get("angular_frequency_conversion")
        != (
            "omega_reduced_rad_per_s=omega_rad_per_s*shift_factor;"
            "frequency_reduced_hz=omega_reduced_rad_per_s/(2*pi)"
        )
    ):
        raise ValueError("processed Plan DMA master-curve semantics are unsupported")
    if hashlib.sha256(metadata_bytes).hexdigest() != metadata_pin.get("sha256"):
        raise ValueError("Processing Output metadata digest differs from the Plan pin")
    if hashlib.sha256(result_bytes).hexdigest() != result_pin.get("sha256"):
        raise ValueError("Processing Output result digest differs from the Plan pin")
    metadata = json.loads(metadata_bytes.decode("utf-8"))
    if not isinstance(metadata, dict):
        raise ValueError("Processing Output metadata must be a JSON object")
    result_artifact = metadata.get("result_artifact")
    step = metadata.get("step")
    if (
        metadata.get("document_type") != "cmp.processing-output"
        or metadata.get("document_version") != "1.6.0"
        or metadata.get("output_id") != output_pin.get("id")
        or not isinstance(result_artifact, dict)
        or result_artifact.get("artifact_id") != result_pin.get("artifact_id")
        or result_artifact.get("sha256") != result_pin.get("sha256")
        or result_artifact.get("schema_ref") != DMA_MASTER_CURVE_SCHEMA
        or result_artifact.get("media_type") != "application/vnd.apache.parquet"
        or not isinstance(step, dict)
        or step.get("method_id") != "polymer.dma_frequency_master_curve"
        or step.get("method_version") != "1.0.0"
    ):
        raise ValueError("Processing Output metadata does not match the Plan or DMA schema")
    options = step.get("options")
    if (
        not isinstance(options, dict)
        or options.get("horizontal_shift_only") is not True
        or options.get("vertical_shift") is not False
        or options.get("interpolation") is not False
        or options.get("resampling") is not False
        or options.get("smoothing") is not False
        or options.get("tts_adequacy") != "not_assessed"
    ):
        raise ValueError("DMA master-curve Processing policy is incomplete or unsupported")
    try:
        table = pq.read_table(pa.BufferReader(result_bytes))
    except Exception as error:
        raise ValueError("processing-output.result is not valid Parquet") from error
    if tuple(table.column_names) != DMA_MASTER_CURVE_COLUMNS:
        raise ValueError("DMA master-curve Parquet columns are not exact")
    dispositions = semantics.get("point_dispositions")
    if not isinstance(dispositions, list) or len(dispositions) != table.num_rows:
        raise ValueError("processed Plan dispositions do not cover the result rows")
    rows: list[dict[str, Any]] = []
    for index, (source, disposition) in enumerate(
        zip(table.to_pylist(), dispositions, strict=True)
    ):
        if (
            not isinstance(disposition, dict)
            or source.get("source_ordinal") != index
            or disposition.get("ordinal") != index
            or source.get("partition") != disposition.get("partition")
            or source.get("exclusion_reason") != disposition.get("exclusion_reason")
        ):
            raise ValueError("DMA result row decisions differ from the immutable Plan")
        partition = source.get("partition")
        reduced_omega = source.get("reduced_angular_frequency_rad_per_s")
        storage = source.get("storage_modulus_pa")
        loss = source.get("loss_modulus_pa")
        if partition == "EXCLUDED":
            if reduced_omega is not None or not source.get("exclusion_reason"):
                raise ValueError("excluded DMA result row is invalid")
            frequency_hz = 0.0
        else:
            if partition not in {"CALIBRATION", "HOLDOUT"}:
                raise ValueError("DMA result row partition is invalid")
            numeric = (reduced_omega, storage, loss)
            if any(
                not isinstance(value, (int, float)) or not math.isfinite(float(value))
                for value in numeric
            ):
                raise ValueError("included DMA result row contains a non-finite value")
            if float(reduced_omega) <= 0 or float(storage) <= 0 or float(loss) < 0:
                raise ValueError("included DMA result row violates the response domain")
            frequency_hz = float(reduced_omega) / (2.0 * math.pi)
        rows.append(
            {
                "ordinal": index,
                "partition": partition,
                "exclusion_reason": source.get("exclusion_reason"),
                "frequency_hz": frequency_hz,
                "storage_modulus_pa": float(storage),
                "loss_modulus_pa": float(loss),
            }
        )
    if len([row for row in rows if row["partition"] == "CALIBRATION"]) < 3:
        raise ValueError("processed DMA input requires at least three calibration rows")
    return "dma", rows


def _rank_diagnostic(jacobian: np.ndarray, parameter_count: int) -> dict[str, Any]:
    """Record the prescribed terminal scaled-Jacobian SVD evidence."""

    matrix = np.asarray(jacobian, dtype=np.float64)
    m, _ = matrix.shape
    norms = np.linalg.norm(matrix, axis=0)
    scaled = matrix / np.where(norms > 0, norms, 1.0)
    singular = np.linalg.svd(scaled, compute_uv=False)
    sigma_max = float(singular[0]) if singular.size else 0.0
    threshold = float(max(m, parameter_count) * np.finfo(np.float64).eps * sigma_max)
    rank = int(np.count_nonzero(singular > threshold)) if sigma_max else 0
    status = "FULL_RANK" if rank >= parameter_count else "RANK_DEFICIENT"
    return {
        "singular_values": [float(item) for item in singular],
        "sigma_max": sigma_max,
        "threshold": threshold,
        "rank": rank,
        "status": status,
        "warning_code": "RANK_DEFICIENT" if status == "RANK_DEFICIENT" else None,
    }


class LinearViscoelasticCalibrator:
    def describe(self) -> ExtensionDescriptor:
        return ExtensionDescriptor(ExtensionType.CALIBRATOR, ("generalized-maxwell-shear",))

    def validate_job(self, job: RunnerJobSpec) -> ValidationReport:
        if job.operation != "execute_plan":
            return ValidationReport.reject(
                _error("CMP-LVE-0001", "linear-viscoelastic calibrator requires execute_plan")
            )
        if job.seed != 0:
            return ValidationReport.reject(
                _error("CMP-LVE-0002", "transport seed must be zero/not_applicable")
            )
        if job.config_schema_ref != CONFIG_SCHEMA:
            return ValidationReport.reject(
                _error("CMP-LVE-0003", "calibrator config schema is not the exact 1.0.0 schema")
            )
        config = job.config
        if (
            config.get("schema_version") != "1.0.0"
            or config.get("seed_status") != "not_applicable"
            or config.get("recommendation_policy") != RECOMMENDATION_POLICY
        ):
            return ValidationReport.reject(
                _error("CMP-LVE-0004", "calibrator config version or seed status is invalid")
            )
        required_roles = {
            "calibration.plan",
            "test-data.canonical",
            "test-data.normalized",
        }
        processed_roles = {
            *required_roles,
            "processing-output.metadata",
            "processing-output.result",
        }
        actual_roles = {item.role for item in job.inputs}
        if actual_roles not in (required_roles, processed_roles):
            return ValidationReport.reject(
                _error(
                    "CMP-LVE-0005",
                    "calibrator requires exact direct or processed scoped input roles",
                )
            )
        output_roles = {item.role for item in job.expected_outputs}
        if output_roles != {"calibration.run-result", "response-residuals", "objective-history"}:
            return ValidationReport.reject(
                _error("CMP-LVE-0006", "calibrator output roles are not the exact declared set")
            )
        return ValidationReport.ok()

    def run(self, context: RunContext, job: RunnerJobSpec) -> ExtensionOutcome:
        try:
            plan = _load_plan(context)
            if plan.get("recommendation_policy") != RECOMMENDATION_POLICY:
                raise ValueError("Plan recommendation policy is unsupported")
            if job.config.get("recommendation_policy") != plan["recommendation_policy"]:
                raise ValueError("Job and Plan recommendation policies differ")
            canonical = json.loads(
                context.read_input("test-data.canonical", maximum_bytes=32 * 1024 * 1024)
            )
            # Reading the normalized Arrow payload is mandatory even when the canonical JSON
            # carries the same rows: it proves the worker used the exact normalized Artifact.
            normalized = context.read_input("test-data.normalized", maximum_bytes=268_435_456)
            if not normalized:
                raise ValueError("normalized Artifact is empty")
            if plan.get("processing_output") is None:
                mode, observations = _normalized_observations(normalized, canonical, plan)
            else:
                metadata = context.read_input(
                    "processing-output.metadata", maximum_bytes=64 * 1024 * 1024
                )
                processed = context.read_input(
                    "processing-output.result", maximum_bytes=268_435_456
                )
                mode, observations = _processed_dma_observations(processed, metadata, plan)
            calibration = [item for item in observations if item.get("partition") == "CALIBRATION"]
            holdout = [item for item in observations if item.get("partition") == "HOLDOUT"]
            if len(calibration) < 3:
                raise ValueError("at least three calibration rows are required")
            term_counts = [int(item) for item in plan.get("term_counts", [])]
            bounds_document = plan.get("parameter_bounds", {})
            starts_document = plan.get("start_vectors", {})
            attempts: list[dict[str, Any]] = []
            candidates: list[dict[str, Any]] = []
            ordinal = 0
            for term_count in term_counts:
                bounds = bounds_document.get(str(term_count), bounds_document.get(term_count))
                starts = starts_document.get(str(term_count), starts_document.get(term_count))
                if not isinstance(bounds, list) or not isinstance(starts, list):
                    raise ValueError("Plan bounds/starts are missing for a declared term count")
                lower = np.log(
                    np.asarray([float(item["lower"]) for item in bounds], dtype=np.float64)
                )
                upper = np.log(
                    np.asarray([float(item["upper"]) for item in bounds], dtype=np.float64)
                )
                for start in starts:
                    ordinal += 1
                    start_physical = np.asarray([float(item) for item in start], dtype=np.float64)
                    history: list[dict[str, Any]] = []
                    if mode == "relaxation":
                        domain = np.asarray(
                            [float(item["time_s"]) for item in calibration], dtype=np.float64
                        )
                        observed = np.asarray(
                            [
                                float(item.get("modulus_pa", item.get("shear_modulus_pa")))
                                for item in calibration
                            ],
                            dtype=np.float64,
                        )
                        scale = float(plan["weights"]["relaxation_scale_pa"])

                        def residual(
                            transformed: np.ndarray,
                            _term_count: int = term_count,
                            _domain: np.ndarray = domain,
                            _observed: np.ndarray = observed,
                            _scale: float = scale,
                            _history: list[dict[str, Any]] = history,
                        ) -> np.ndarray:
                            physical = np.exp(transformed)
                            prediction, _ = _evaluate(_term_count, physical, _domain, mode)
                            result = (prediction - _observed) / _scale / math.sqrt(len(calibration))
                            _history.append(
                                {
                                    "ordinal": len(_history),
                                    "objective": float(np.dot(result, result)),
                                }
                            )
                            return result
                    else:
                        domain = np.asarray(
                            [float(item["frequency_hz"]) for item in calibration], dtype=np.float64
                        )
                        observed_storage = np.asarray(
                            [float(item["storage_modulus_pa"]) for item in calibration],
                            dtype=np.float64,
                        )
                        observed_loss = np.asarray(
                            [float(item["loss_modulus_pa"]) for item in calibration],
                            dtype=np.float64,
                        )
                        weights = plan["weights"]

                        def residual(
                            transformed: np.ndarray,
                            _term_count: int = term_count,
                            _domain: np.ndarray = domain,
                            _observed_storage: np.ndarray = observed_storage,
                            _observed_loss: np.ndarray = observed_loss,
                            _weights: dict[str, Any] = weights,
                            _history: list[dict[str, Any]] = history,
                        ) -> np.ndarray:
                            physical = np.exp(transformed)
                            prediction_storage, prediction_loss = _evaluate(
                                _term_count, physical, _domain, mode
                            )
                            result = np.concatenate(
                                (
                                    (prediction_storage - _observed_storage)
                                    / float(_weights["dma_storage_scale_pa"])
                                    * math.sqrt(
                                        float(_weights["dma_storage_weight"]) / len(calibration)
                                    ),
                                    (prediction_loss - _observed_loss)
                                    / float(_weights["dma_loss_scale_pa"])
                                    * math.sqrt(
                                        float(_weights["dma_loss_weight"]) / len(calibration)
                                    ),
                                )
                            )
                            _history.append(
                                {
                                    "ordinal": len(_history),
                                    "objective": float(np.dot(result, result)),
                                }
                            )
                            return result

                    try:
                        result = least_squares(
                            residual,
                            np.log(start_physical),
                            bounds=(lower, upper),
                            method="trf",
                            x_scale="jac",
                            ftol=float(plan["optimizer"]["ftol"]),
                            xtol=float(plan["optimizer"]["xtol"]),
                            gtol=float(plan["optimizer"]["gtol"]),
                            max_nfev=int(plan["optimizer"]["max_nfev"]),
                        )
                        physical = np.exp(result.x)
                        residuals = residual(result.x)
                        success = bool(result.success and np.all(np.isfinite(physical)))
                        rank = _rank_diagnostic(
                            np.asarray(result.jac, dtype=np.float64), physical.size
                        )
                        warnings = [rank["warning_code"]] if rank["warning_code"] else []
                        attempt = {
                            "ordinal": ordinal,
                            "term_count": term_count,
                            "start_vector": start_physical.tolist(),
                            "transformed_start_vector": np.log(start_physical).tolist(),
                            "status": int(result.status),
                            "message": str(result.message),
                            "nfev": int(result.nfev),
                            "cost": float(result.cost),
                            "optimality": float(result.optimality),
                            "active_mask": [int(item) for item in result.active_mask],
                            "physical_parameters": physical.tolist(),
                            "transformed_parameters": result.x.tolist(),
                            "residuals": residuals.tolist(),
                            "rss": float(np.dot(residuals, residuals)),
                            "rank": rank,
                            "warnings": warnings,
                            "objective_history": history,
                            "converged": success,
                            "physical": success,
                        }
                    except (ValueError, FloatingPointError) as error:
                        attempt = {
                            "ordinal": ordinal,
                            "term_count": term_count,
                            "start_vector": start_physical.tolist(),
                            "transformed_start_vector": np.log(start_physical).tolist(),
                            "status": 0,
                            "message": str(error),
                            "nfev": 0,
                            "cost": 0.0,
                            "optimality": 0.0,
                            "active_mask": [0] * len(start_physical),
                            "physical_parameters": start_physical.tolist(),
                            "transformed_parameters": np.log(start_physical).tolist(),
                            "residuals": [],
                            "rss": 0.0,
                            "rank": {
                                "singular_values": [],
                                "sigma_max": 0.0,
                                "threshold": 0.0,
                                "rank": 0,
                                "status": "RANK_DEFICIENT",
                                "warning_code": "RANK_DEFICIENT",
                            },
                            "warnings": ["EXECUTION_REQUEST_INVALID"],
                            "objective_history": history,
                            "converged": False,
                            "physical": False,
                        }
                    attempts.append(attempt)
                    if attempt["converged"] and attempt["physical"]:
                        holdout_residuals: list[float] = []
                        if holdout:
                            if mode == "relaxation":
                                holdout_domain = np.asarray(
                                    [float(item["time_s"]) for item in holdout], dtype=np.float64
                                )
                                holdout_observed = np.asarray(
                                    [float(item["modulus_pa"]) for item in holdout],
                                    dtype=np.float64,
                                )
                                holdout_residuals = (
                                    (
                                        _evaluate(term_count, physical, holdout_domain, mode)[0]
                                        - holdout_observed
                                    )
                                    / float(plan["weights"]["relaxation_scale_pa"])
                                ).tolist()
                            else:
                                holdout_domain = np.asarray(
                                    [float(item["frequency_hz"]) for item in holdout],
                                    dtype=np.float64,
                                )
                                holdout_storage = np.asarray(
                                    [float(item["storage_modulus_pa"]) for item in holdout],
                                    dtype=np.float64,
                                )
                                holdout_loss = np.asarray(
                                    [float(item["loss_modulus_pa"]) for item in holdout],
                                    dtype=np.float64,
                                )
                                holdout_prediction = _evaluate(
                                    term_count, physical, holdout_domain, mode
                                )
                                holdout_residuals = np.concatenate(
                                    (
                                        (holdout_prediction[0] - holdout_storage)
                                        / float(plan["weights"]["dma_storage_scale_pa"]),
                                        (holdout_prediction[1] - holdout_loss)
                                        / float(plan["weights"]["dma_loss_scale_pa"]),
                                    )
                                ).tolist()
                        candidate = {
                            "candidate_id": str(
                                uuid5(
                                    NAMESPACE_URL,
                                    f"{job.config.get('run_id', job.job_id)}:candidate:{ordinal}",
                                )
                            ),
                            "attempt_ordinal": ordinal,
                            "term_count": term_count,
                            "physical_parameters": attempt["physical_parameters"],
                            "transformed_parameters": attempt["transformed_parameters"],
                            "rss": attempt["rss"],
                            "bic": float(
                                len(attempt["residuals"])
                                * math.log(
                                    max(
                                        attempt["rss"] / len(attempt["residuals"]),
                                        np.finfo(np.float64).tiny,
                                    )
                                )
                                + (1 + 2 * term_count) * math.log(len(attempt["residuals"]))
                            ),
                            "calibration_residuals": attempt["residuals"],
                            "holdout_residuals": holdout_residuals,
                            "rank": attempt["rank"],
                            "warnings": attempt.get("warnings", []),
                            "uncertainty_status": "NOT_PROVIDED",
                        }
                        candidates.append(candidate)
            candidates.sort(
                key=lambda item: _recommendation_key(item, plan["recommendation_policy"])
            )
            status = "succeeded" if candidates else "failed"
            recommendation = None
            if candidates:
                winner = candidates[0]
                recommendation = {
                    "recommendation_id": str(
                        uuid5(
                            NAMESPACE_URL, f"{job.config.get('run_id', job.job_id)}:recommendation"
                        )
                    ),
                    "candidate_id": winner["candidate_id"],
                    "candidate_digest": hashlib.sha256(
                        json.dumps(
                            winner, allow_nan=False, separators=(",", ":"), sort_keys=True
                        ).encode("utf-8")
                    ).hexdigest(),
                    "rule_version": "linear_viscoelastic_bic@1.0.0",
                }
            result_document = {
                "schema_id": RESULT_SCHEMA,
                "schema_version": "1.0.0",
                "run_id": str(job.config.get("run_id", job.job_id)),
                "plan_revision_id": str(job.config.get("plan_revision_id")),
                "status": status,
                "attempts": attempts,
                "candidates": candidates,
                "recommendation": recommendation,
                "failure_code": None if candidates else "CALCULATION_FAILED",
                "failure_detail": None if candidates else "No candidate converged",
                "recovery_hint": None
                if candidates
                else "Create a new immutable Plan with reviewed bounds or starts.",
            }
            residual_columns: dict[str, list[Any]] = {
                "ordinal": [],
                "channel": [],
                "observed": [],
                "predicted": [],
                "residual": [],
                "partition": [],
            }
            winner_parameters = (
                np.asarray(candidates[0]["physical_parameters"], dtype=np.float64)
                if candidates
                else None
            )
            for point in observations:
                if mode == "relaxation":
                    prediction = 0.0
                    if winner_parameters is not None:
                        prediction = float(
                            _evaluate(
                                candidates[0]["term_count"],
                                winner_parameters,
                                np.asarray([float(point["time_s"])], dtype=np.float64),
                                mode,
                            )[0][0]
                        )
                    residual_columns["ordinal"].append(int(point["ordinal"]))
                    residual_columns["channel"].append("relaxation")
                    residual_columns["observed"].append(float(point["modulus_pa"]))
                    residual_columns["predicted"].append(prediction)
                    residual_columns["residual"].append(prediction - float(point["modulus_pa"]))
                    residual_columns["partition"].append(str(point.get("partition", "CALIBRATION")))
                else:
                    for channel, observed_key in (
                        ("dma_storage", "storage_modulus_pa"),
                        ("dma_loss", "loss_modulus_pa"),
                    ):
                        prediction = 0.0
                        if winner_parameters is not None:
                            values = _evaluate(
                                candidates[0]["term_count"],
                                winner_parameters,
                                np.asarray([float(point["frequency_hz"])], dtype=np.float64),
                                mode,
                            )
                            prediction = float(values[0 if channel == "dma_storage" else 1][0])
                        residual_columns["ordinal"].append(int(point["ordinal"]))
                        residual_columns["channel"].append(channel)
                        residual_columns["observed"].append(float(point[observed_key]))
                        residual_columns["predicted"].append(prediction)
                        residual_columns["residual"].append(prediction - float(point[observed_key]))
                        residual_columns["partition"].append(
                            str(point.get("partition", "CALIBRATION"))
                        )
            residual_payload = _parquet_bytes(residual_columns)
            evaluations = [
                item for attempt in attempts for item in attempt.get("objective_history", [])
            ]
            history_payload = _parquet_bytes(
                {
                    "ordinal": [int(item.get("ordinal", 0)) for item in evaluations],
                    "objective": [float(item.get("objective", 0.0)) for item in evaluations],
                }
            )
            context.write_output(
                role="calibration.run-result",
                media_type="application/json",
                schema_ref=RESULT_SCHEMA,
                data=json.dumps(
                    result_document, allow_nan=False, separators=(",", ":"), sort_keys=True
                ).encode("utf-8"),
            )
            context.write_output(
                role="response-residuals",
                media_type="application/vnd.apache.parquet",
                schema_ref=RESIDUAL_SCHEMA,
                data=residual_payload,
            )
            context.write_output(
                role="objective-history",
                media_type="application/vnd.apache.parquet",
                schema_ref=HISTORY_SCHEMA,
                data=history_payload,
            )
            return ExtensionOutcome(
                ExtensionStatus.SUCCEEDED if candidates else ExtensionStatus.FAILED
            )
        except Exception as error:
            return ExtensionOutcome(ExtensionStatus.FAILED, (_error("CMP-LVE-0007", str(error)),))

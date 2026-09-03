from __future__ import annotations

import ast
import hashlib
import importlib.util
import io
import json
import math
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from cmp.modules.jobs.application.linear_viscoelastic_calibration import (
    build_linear_viscoelastic_job_spec,
)
from cmp.modules.modeling.application.linear_viscoelastic_result_import import (
    parse_calibration_run_result,
)
from cmp.modules.modeling.domain.linear_viscoelastic_calibration import (
    calculate_bic,
    evaluate_dma_moduli,
    evaluate_relaxation_modulus,
    rank_diagnostic,
    recommend_candidate,
    selected_arrays_digest,
)
from cmp_plugin_sdk import RunContext, RunnerJobSpec
from cmp_plugin_sdk.context import InputBinding, OutputRule

ROOT = Path(__file__).parents[3]
GENERATOR = ROOT / "scripts/generate_linear_viscoelastic_oracle.py"
MANIFEST = ROOT / "tests/fixtures/linear_viscoelastic/oracle-manifest.json"
PLUGIN_PATH = (
    ROOT
    / "plugins/production/linear_viscoelastic_calibrator/linear_viscoelastic_calibrator/plugin.py"
)
RECOMMENDATION_POLICY = "lowest_bic_then_term_count_then_attempt_ordinal@1.0.0"
_oracle_spec = importlib.util.spec_from_file_location("decimal_oracle", GENERATOR)
assert _oracle_spec is not None and _oracle_spec.loader is not None
_oracle_module = importlib.util.module_from_spec(_oracle_spec)
_oracle_spec.loader.exec_module(_oracle_module)
decimal_bic = _oracle_module.bic
dma_loss = _oracle_module.dma_loss
dma_storage = _oracle_module.dma_storage
relaxation = _oracle_module.relaxation


def _load_plugin() -> Any:
    module_spec = importlib.util.spec_from_file_location(
        "oracle_linear_viscoelastic_calibrator", PLUGIN_PATH
    )
    assert module_spec is not None and module_spec.loader is not None
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    return module


def _oracle() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(MANIFEST.read_text(encoding="utf-8")))


def _recommendation_candidate(identity: int, *, bic: float, terms: int, attempt: int) -> Any:
    return SimpleNamespace(
        candidate_id=UUID(int=identity),
        digest=f"{identity:064x}",
        bic=bic,
        term_count=terms,
        attempt_ordinal=attempt,
    )


def test_recommendation_uses_bic_then_fewer_terms_then_earlier_attempt() -> None:
    lower_bic = _recommendation_candidate(1, bic=-20, terms=5, attempt=3)
    higher_bic = _recommendation_candidate(2, bic=-10, terms=1, attempt=1)
    recommendation = recommend_candidate(
        [higher_bic, lower_bic], recommendation_policy=RECOMMENDATION_POLICY
    )
    assert recommendation is not None
    assert recommendation.candidate_id == lower_bic.candidate_id

    fewer_terms = _recommendation_candidate(3, bic=-20, terms=3, attempt=4)
    more_terms = _recommendation_candidate(4, bic=-20, terms=5, attempt=1)
    recommendation = recommend_candidate(
        [more_terms, fewer_terms], recommendation_policy=RECOMMENDATION_POLICY
    )
    assert recommendation is not None
    assert recommendation.candidate_id == fewer_terms.candidate_id

    earlier_attempt = _recommendation_candidate(5, bic=-20, terms=3, attempt=1)
    later_attempt = _recommendation_candidate(6, bic=-20, terms=3, attempt=2)
    recommendation = recommend_candidate(
        [later_attempt, earlier_attempt], recommendation_policy=RECOMMENDATION_POLICY
    )
    assert recommendation is not None
    assert recommendation.candidate_id == earlier_attempt.candidate_id


def _oracle_plan(mode: str, row_count: int) -> dict[str, Any]:
    channels = (
        [
            {
                "key": "time",
                "quantity_semantics": "time.elapsed",
                "axis_role": "independent",
                "original_unit_string": "s",
                "normalized_unit": "s",
            },
            {
                "key": "relaxation",
                "quantity_semantics": "mechanics.modulus.shear.relaxation",
                "axis_role": "dependent",
                "original_unit_string": "Pa",
                "normalized_unit": "Pa",
            },
        ]
        if mode == "relaxation"
        else [
            {
                "key": "temperature",
                "quantity_semantics": "physics.temperature",
                "axis_role": "independent",
                "original_unit_string": "K",
                "normalized_unit": "K",
            },
            {
                "key": "frequency",
                "quantity_semantics": "frequency.cyclic",
                "axis_role": "independent",
                "original_unit_string": "Hz",
                "normalized_unit": "Hz",
            },
            {
                "key": "storage",
                "quantity_semantics": "mechanics.modulus.storage",
                "axis_role": "dependent",
                "original_unit_string": "Pa",
                "normalized_unit": "Pa",
            },
            {
                "key": "loss",
                "quantity_semantics": "mechanics.modulus.loss",
                "axis_role": "dependent",
                "original_unit_string": "Pa",
                "normalized_unit": "Pa",
            },
        ]
    )
    semantics: dict[str, Any] = {
        "mode": mode,
        "deformation_mode": "shear",
        "channels": channels,
        "point_dispositions": [
            {
                "ordinal": ordinal,
                "partition": "HOLDOUT" if ordinal == row_count - 1 else "CALIBRATION",
                "exclusion_reason": None,
            }
            for ordinal in range(row_count)
        ],
        "selected_temperature_k": "283.15",
        "temperature_source": "condition",
        "strain_amplitude": "0.001",
        "strain_amplitude_quantity": "mechanics.strain.shear",
        "strain_amplitude_unit": "1",
        "frequency_kind": "cyclic_hz" if mode == "dma" else "not_applicable",
        "angular_frequency_conversion": (
            "omega_rad_per_s=2*pi*frequency_hz" if mode == "dma" else "not_applicable"
        ),
    }
    if mode == "dma":
        semantics["dma_domain_policy"] = "strict_unique"
    bounds = {
        "1": [
            {
                "name": "G_inf_pa",
                "lower": "1",
                "start": "4",
                "upper": "20",
                "unit": "Pa",
                "transform": "ln",
            },
            {
                "name": "G_1_pa",
                "lower": "1",
                "start": "2",
                "upper": "10",
                "unit": "Pa",
                "transform": "ln",
            },
            {
                "name": "tau_1_s",
                "lower": "0.01",
                "start": "0.1",
                "upper": "1",
                "unit": "s",
                "transform": "ln",
            },
        ],
        "2": [
            {
                "name": "G_inf_pa",
                "lower": "1",
                "start": "4",
                "upper": "20",
                "unit": "Pa",
                "transform": "ln",
            },
            {
                "name": "G_1_pa",
                "lower": "1",
                "start": "2",
                "upper": "10",
                "unit": "Pa",
                "transform": "ln",
            },
            {
                "name": "G_2_pa",
                "lower": "0.1",
                "start": "1",
                "upper": "10",
                "unit": "Pa",
                "transform": "ln",
            },
            {
                "name": "tau_1_s",
                "lower": "0.01",
                "start": "0.1",
                "upper": "0.2",
                "unit": "s",
                "transform": "ln",
            },
            {
                "name": "tau_2_s",
                "lower": "0.3",
                "start": "0.5",
                "upper": "2",
                "unit": "s",
                "transform": "ln",
            },
        ],
    }
    return {
        "schema_id": "urn:cmp:modeling:linear-viscoelastic-calibration-plan:1.0.0",
        "schema_version": "1.0.0",
        "input_semantics": semantics,
        "recommendation_policy": RECOMMENDATION_POLICY,
        "term_counts": [1, 2],
        "parameter_bounds": bounds,
        "start_vectors": {
            "1": [["4", "2", "0.1"]],
            "2": [["4", "2", "1", "0.1", "0.5"]],
        },
        "weights": {
            "relaxation_scale_pa": "1",
            "dma_storage_weight": "0.5",
            "dma_loss_weight": "0.5",
            "dma_storage_scale_pa": "1",
            "dma_loss_scale_pa": "1",
        },
        "optimizer": {
            "ftol": 1e-10,
            "xtol": 1e-10,
            "gtol": 1e-10,
            "max_nfev": 2000,
        },
    }


def _run_plugin(
    mode: str, temporary_root: Path, *, term_count: int | None = None
) -> tuple[dict[str, Any], list[dict[str, Decimal]], dict[str, Any]]:
    """Run the checked-in package entrypoint against Decimal-generated observations."""

    if term_count is not None and mode != "relaxation":
        raise ValueError("high-order regression fixture is relaxation-only")
    g_inf = Decimal("4")
    moduli: tuple[Decimal, ...]
    taus: tuple[Decimal, ...]
    columns: dict[str, list[float]]
    if term_count is None:
        moduli = (Decimal("2"),)
        taus = (Decimal("0.1"),)
    else:
        moduli = tuple(
            Decimal(term_count + 1 - index) / Decimal(2) for index in range(1, term_count + 1)
        )
        taus = tuple(Decimal(10) ** Decimal(index - 5) for index in range(term_count))
    if mode == "relaxation" and term_count is not None:
        domains = [
            Decimal(coefficient) * (Decimal(10) ** Decimal(exponent))
            for exponent in range(-6, 6)
            for coefficient in (1, 3)
        ] + [Decimal("1e6")]
        observations = [
            {"time": value, "relaxation": relaxation(g_inf, moduli, taus, value)}
            for value in domains
        ]
        columns = {
            "time": [float(item["time"]) for item in observations],
            "relaxation": [float(item["relaxation"]) for item in observations],
        }
    elif mode == "relaxation":
        domains = [Decimal("0.01"), Decimal("0.1"), Decimal("1"), Decimal("2")]
        observations = [
            {"time": value, "relaxation": relaxation(g_inf, moduli, taus, value)}
            for value in domains
        ]
        columns = {
            "time": [float(item["time"]) for item in observations],
            "relaxation": [float(item["relaxation"]) for item in observations],
        }
    else:
        domains = [Decimal("0.01"), Decimal("0.1"), Decimal("1"), Decimal("10")]
        observations = [
            {
                "temperature": Decimal("283.15"),
                "frequency": value,
                "storage": dma_storage(g_inf, moduli, taus, value),
                "loss": dma_loss(moduli, taus, value),
            }
            for value in domains
        ]
        columns = {
            "temperature": [float(item["temperature"]) for item in observations],
            "frequency": [float(item["frequency"]) for item in observations],
            "storage": [float(item["storage"]) for item in observations],
            "loss": [float(item["loss"]) for item in observations],
        }
    row_count = len(observations)
    plan = _oracle_plan(mode, row_count)
    if term_count is not None:
        physical = (g_inf, *moduli, *taus)
        names = (
            "G_inf_pa",
            *(f"G_{index}_pa" for index in range(1, term_count + 1)),
            *(f"tau_{index}_s" for index in range(1, term_count + 1)),
        )
        units = ("Pa", *("Pa" for _ in moduli), *("s" for _ in taus))
        bounds: list[dict[str, str]] = []
        starts: list[str] = []
        for name, unit, truth in zip(names, units, physical, strict=True):
            factor = Decimal(3) if unit == "s" else Decimal(2)
            start = truth * Decimal("1.02")
            bounds.append(
                {
                    "name": name,
                    "lower": str(truth / factor),
                    "start": str(start),
                    "upper": str(truth * factor),
                    "unit": unit,
                    "transform": "ln",
                }
            )
            starts.append(str(start))
        plan["term_counts"] = [term_count]
        plan["parameter_bounds"] = {str(term_count): bounds}
        plan["start_vectors"] = {str(term_count): [starts]}
    plan["plan_revision_id"] = str(UUID(int=301 if mode == "relaxation" else 302))
    plan["run_id"] = str(UUID(int=303 if mode == "relaxation" else 304))
    plan_bytes = json.dumps(plan, sort_keys=True, separators=(",", ":")).encode("utf-8")
    canonical = {
        "channels": [
            {
                "key": channel["key"],
                "quantity_semantics": channel["quantity_semantics"],
                "axis_role": channel["axis_role"],
                "original_unit_string": channel["original_unit_string"],
                "normalized_unit": channel["normalized_unit"],
                "normalization": {"scale": "1", "offset": "0"},
                "normalized_values": [str(item[str(channel["key"])]) for item in observations],
            }
            for channel in cast(list[dict[str, Any]], plan["input_semantics"]["channels"])
        ]
    }
    canonical_bytes = json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")
    normalized_stream = io.BytesIO()
    pq.write_table(  # type: ignore[no-untyped-call]
        pa.table(columns), normalized_stream, compression=None, write_statistics=False
    )
    normalized_bytes = normalized_stream.getvalue()
    input_payloads = {
        "calibration.plan": plan_bytes,
        "test-data.canonical": canonical_bytes,
        "test-data.normalized": normalized_bytes,
    }
    input_media = {
        "calibration.plan": "application/json",
        "test-data.canonical": "application/vnd.cmp.test-data+json",
        "test-data.normalized": "application/vnd.apache.parquet",
    }
    input_ids = {
        "calibration.plan": UUID(int=305),
        "test-data.canonical": UUID(int=306),
        "test-data.normalized": UUID(int=307),
    }
    temporary_root.mkdir(parents=True, exist_ok=True)
    bindings: list[InputBinding] = []
    for role, payload in input_payloads.items():
        path = temporary_root / f"{role.replace('.', '-')}.input"
        path.write_bytes(payload)
        bindings.append(
            InputBinding(
                role,
                input_ids[role],
                hashlib.sha256(payload).hexdigest(),
                input_media[role],
                path,
                len(payload),
            )
        )
    job_spec, _ = build_linear_viscoelastic_job_spec(
        job_id=UUID(int=308 if mode == "relaxation" else 309),
        attempt_id=UUID(int=310 if mode == "relaxation" else 311),
        run_id=UUID(str(plan["run_id"])),
        plan_revision_id=UUID(str(plan["plan_revision_id"])),
        plan_sha256=hashlib.sha256(plan_bytes).hexdigest(),
        plan_artifact_id=input_ids["calibration.plan"],
        canonical_test_data_revision_id=UUID(int=312),
        canonical_test_data_artifact_id=input_ids["test-data.canonical"],
        canonical_test_data_sha256=hashlib.sha256(canonical_bytes).hexdigest(),
        normalized_test_data_revision_id=UUID(int=313),
        normalized_test_data_artifact_id=input_ids["test-data.normalized"],
        normalized_test_data_sha256=hashlib.sha256(normalized_bytes).hexdigest(),
        package_sha256="d" * 64,
        recommendation_policy=RECOMMENDATION_POLICY,
        deadline=datetime.now(UTC) + timedelta(hours=1),
        traceparent="00-00000000000000000000000000000001-0000000000000001-01",
    )
    job = RunnerJobSpec.from_validated_document(job_spec.document())
    output_root = temporary_root / "outputs"
    workspace_root = temporary_root / "workspace"
    output_root.mkdir()
    workspace_root.mkdir()
    media_types = {
        "calibration.run-result": "application/json",
        "response-residuals": "application/vnd.apache.parquet",
        "objective-history": "application/vnd.apache.parquet",
    }
    context = RunContext(
        job=job,
        inputs=tuple(bindings),
        output_rules=tuple(
            OutputRule(item.role, item.schema_ref, (media_types[item.role],), 32_000_000)
            for item in job.expected_outputs
        ),
        output_root=output_root,
        workspace_root=workspace_root,
        cancellation_marker=workspace_root / "cancel.requested",
        max_total_output_bytes=96_000_000,
    )
    plugin = _load_plugin().LinearViscoelasticCalibrator()
    outcome = plugin.run(context, job)
    assert outcome.status.value == "succeeded"
    result_output = next(item for item in context.outputs if item.role == "calibration.run-result")
    result = cast(dict[str, Any], json.loads(result_output.path.read_bytes()))
    return result, observations, plan


@pytest.mark.parametrize("term_count", (3, 5, 10))
def test_actual_plugin_preserves_supported_high_order_parameter_vectors(
    tmp_path: Path,
    term_count: int,
) -> None:
    result, observations, plan = _run_plugin(
        "relaxation",
        tmp_path / f"relaxation-{term_count}-term",
        term_count=term_count,
    )
    parameter_count = 1 + 2 * term_count
    attempts = cast(list[dict[str, Any]], result["attempts"])
    candidates = cast(list[dict[str, Any]], result["candidates"])

    assert len(observations) == 25
    assert plan["term_counts"] == [term_count]
    assert len(attempts) == len(candidates) == 1
    attempt = attempts[0]
    candidate = candidates[0]
    assert int(attempt["term_count"]) == int(candidate["term_count"]) == term_count
    assert int(attempt["nfev"]) > 0
    for key in (
        "start_vector",
        "transformed_start_vector",
        "active_mask",
        "physical_parameters",
        "transformed_parameters",
    ):
        assert len(cast(list[object], attempt[key])) == parameter_count
    for key in ("physical_parameters", "transformed_parameters"):
        assert len(cast(list[object], candidate[key])) == parameter_count
        assert candidate[key] == attempt[key]
    assert all(
        math.isfinite(float(value)) and float(value) > 0
        for value in cast(list[float], candidate["physical_parameters"])
    )

    parsed = parse_calibration_run_result(result)
    assert parsed.status.value == "succeeded"
    assert len(parsed.candidates[0].physical_parameters) == parameter_count


def test_decimal_oracle_is_independent_deterministic_and_unit_explicit(tmp_path: Path) -> None:
    tree = ast.parse(GENERATOR.read_text(encoding="utf-8"))
    imported_roots = {
        alias.name.split(".", 1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported_roots.update(
        node.module.split(".", 1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    )
    assert imported_roots.isdisjoint({"cmp", "numpy", "scipy", "pyarrow"})

    regenerated = tmp_path / "oracle-manifest.json"
    subprocess.run(
        [sys.executable, str(GENERATOR), "--output", str(regenerated)],
        cwd=ROOT,
        check=True,
    )
    assert regenerated.read_bytes() == MANIFEST.read_bytes()
    oracle = _oracle()
    assert oracle["production_imports"] == []
    assert oracle["quality_thresholds"] == []
    assert oracle["units"] == {
        "modulus": "Pa",
        "time": "s",
        "frequency": "Hz",
        "angular_frequency": "rad/s",
    }


def test_production_equations_bic_rank_and_digest_match_decimal_oracle() -> None:
    oracle = _oracle()
    cases = oracle["cases"]
    tolerances = oracle["comparison_tolerances"]
    relative = float(tolerances["closed_form_relative"])
    absolute = float(tolerances["closed_form_absolute"])
    parameters_pa_s = (4.0, 2.0, 0.1)

    relaxation_pa = evaluate_relaxation_modulus(1, parameters_pa_s, (0.1,))[0]
    assert math.isclose(
        relaxation_pa,
        float(cases["R01_relaxation_closed_form"]["value"]),
        rel_tol=relative,
        abs_tol=absolute,
    )
    storage_pa, loss_pa = evaluate_dma_moduli(1, parameters_pa_s, (1.0,))
    assert math.isclose(
        storage_pa[0],
        float(cases["R02_dma_storage_closed_form"]["value"]),
        rel_tol=relative,
        abs_tol=absolute,
    )
    assert math.isclose(
        loss_pa[0],
        float(cases["R03_dma_loss_closed_form"]["value"]),
        rel_tol=relative,
        abs_tol=absolute,
    )
    assert math.isclose(
        calculate_bic(rss=2.0, m=6, parameter_count=3),
        float(cases["R08_bic_rule"]["value"]),
        rel_tol=0.0,
        abs_tol=float(tolerances["bic_absolute"]),
    )

    rank_case = cases["R09_svd_rank"]
    rank = rank_diagnostic(np.asarray(rank_case["matrix"], dtype=np.float64))
    assert rank.rank == rank_case["expected_rank"]
    assert np.allclose(
        rank.singular_values,
        np.asarray(rank_case["expected_singular_values"], dtype=np.float64),
        rtol=0.0,
        atol=float(tolerances["rank_singular_absolute"]),
    )

    digest_case = cases["R13_exact_selected_array_digest"]
    assert (
        selected_arrays_digest(
            np.asarray(digest_case["matrix"], dtype="<f8"),
            channels=tuple(digest_case["channels"]),
            source_ordinals=tuple(digest_case["source_ordinals"]),
        )
        == digest_case["digest"]
    )


def test_actual_plugin_outputs_match_independent_decimal_response_objective_and_policy(
    tmp_path: Path,
) -> None:
    """Check both governed modes at the production plugin boundary with Decimal equations."""

    oracle = _oracle()
    tolerances = oracle["comparison_tolerances"]
    residual_tolerance = float(tolerances["plugin_residual_absolute"])
    objective_tolerance = float(tolerances["plugin_objective_absolute"])
    bic_tolerance = float(tolerances["plugin_bic_absolute"])
    plugin_source = PLUGIN_PATH.read_text(encoding="utf-8")
    assert "generate_linear_viscoelastic_oracle" not in plugin_source

    for mode in ("relaxation", "dma"):
        result, observations, plan = _run_plugin(mode, tmp_path / mode)
        assert plan["recommendation_policy"] == RECOMMENDATION_POLICY
        candidates = cast(list[dict[str, Any]], result["candidates"])
        assert candidates
        calibration = observations[:-1]
        for candidate in candidates:
            term_count = int(candidate["term_count"])
            parameters = tuple(Decimal(str(value)) for value in candidate["physical_parameters"])
            g_inf = parameters[0]
            moduli = parameters[1 : term_count + 1]
            taus = parameters[term_count + 1 :]
            expected_residuals: list[Decimal] = []
            if mode == "relaxation":
                for row in calibration:
                    prediction = relaxation(g_inf, moduli, taus, row["time"])
                    expected_residuals.append(
                        (prediction - row["relaxation"]) / Decimal(len(calibration)).sqrt()
                    )
            else:
                for row in calibration:
                    prediction = dma_storage(g_inf, moduli, taus, row["frequency"])
                    expected_residuals.append(
                        (prediction - row["storage"])
                        * (Decimal("0.5") / Decimal(len(calibration))).sqrt()
                    )
                for row in calibration:
                    prediction = dma_loss(moduli, taus, row["frequency"])
                    expected_residuals.append(
                        (prediction - row["loss"])
                        * (Decimal("0.5") / Decimal(len(calibration))).sqrt()
                    )
            rss = sum((value * value for value in expected_residuals), Decimal(0))
            assert math.isclose(
                float(candidate["rss"]),
                float(rss),
                rel_tol=0.0,
                abs_tol=objective_tolerance,
            )
            actual_residuals = [float(value) for value in candidate["calibration_residuals"]]
            assert len(actual_residuals) == len(expected_residuals)
            for actual, expected in zip(actual_residuals, expected_residuals, strict=True):
                assert math.isclose(
                    actual,
                    float(expected),
                    rel_tol=0.0,
                    abs_tol=residual_tolerance,
                )
            # The production BIC applies the declared float64 tiny floor.  Use the plugin's
            # serialized objective here so a mathematically exact fit does not turn harmless
            # binary-rounding noise into a different logarithmic scale.
            bic_rss = max(
                Decimal(str(candidate["rss"])),
                Decimal(str(np.finfo(np.float64).tiny)) * Decimal(len(expected_residuals)),
            )
            expected_bic = decimal_bic(bic_rss, len(expected_residuals), 1 + 2 * term_count)
            assert math.isclose(
                float(candidate["bic"]),
                float(expected_bic),
                rel_tol=0.0,
                abs_tol=bic_tolerance,
            )
        winner = min(
            candidates,
            key=lambda item: (
                float(item["bic"]),
                int(item["term_count"]),
                int(item["attempt_ordinal"]),
            ),
        )
        recommendation = cast(dict[str, Any], result["recommendation"])
        assert recommendation["candidate_id"] == winner["candidate_id"]
        assert recommendation["rule_version"] == "linear_viscoelastic_bic@1.0.0"
        winner_digest = hashlib.sha256(
            json.dumps(winner, allow_nan=False, separators=(",", ":"), sort_keys=True).encode(
                "utf-8"
            )
        ).hexdigest()
        assert recommendation["candidate_digest"] == winner_digest

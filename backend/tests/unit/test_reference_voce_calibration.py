from __future__ import annotations

import math
from uuid import UUID

import numpy as np
import pytest
from cmp.modules.datasets.domain.reference_tensile import CurvePoint
from cmp.modules.modeling.domain.reference_voce_calibration import (
    EqualSpecimenNormalizedObjectiveEngine,
    InvalidVoceCalibration,
    ReferenceUniaxialTensionTestModeAdapter,
    ReferenceVoceCalibrationPlanContent,
    ReferenceVoceMaterialModelEvaluator,
    VoceCalibrationCurve,
    VoceEngineeringCurveInput,
    VoceParameterPlan,
    VocePlasticObservation,
    calibrate_reference_voce_curves,
    reference_voce_calibration_plan_canonical,
    reference_voce_diagnostics_from_parquet,
    reference_voce_diagnostics_parquet_bytes,
)


def _uuid(number: int) -> UUID:
    return UUID(int=number)


def _plan(*, multistart_count: int = 3) -> ReferenceVoceCalibrationPlanContent:
    return ReferenceVoceCalibrationPlanContent(
        plan_label="Synthetic multi-curve Voce reference",
        calibration_input_scope_id=_uuid(1),
        calibration_input_scope_revision_id=_uuid(2),
        material_state_id=_uuid(3),
        material_state_revision_id=_uuid(4),
        property_set_id=_uuid(5),
        property_set_revision_id=_uuid(6),
        youngs_modulus_pa=210.0e9,
        sigma_0=VoceParameterPlan("sigma_0_pa", "Pa", 200.0e6, 280.0e6, 400.0e6, 300.0e6),
        q=VoceParameterPlan("q_pa", "Pa", 50.0e6, 140.0e6, 300.0e6, 150.0e6),
        b=VoceParameterPlan("b", "1", 1.0, 10.0, 40.0, 10.0),
        normalization_stress_scale_pa=100.0e6,
        multistart_count=multistart_count,
        random_seed=20260715,
    )


def _engineering_curve(
    member_ordinal: int,
    *,
    sigma_0: float = 300.0e6,
    q: float = 160.0e6,
    b: float = 12.0,
    stress_factor: float = 1.0,
    plastic_strains: tuple[float, ...] = (0.0, 0.004, 0.01, 0.02, 0.04, 0.07),
) -> VoceEngineeringCurveInput:
    youngs_modulus = 210.0e9
    points: list[CurvePoint] = [CurvePoint(0.0, 0.0)]
    for plastic_strain in plastic_strains:
        true_stress = (sigma_0 + q * (1.0 - math.exp(-b * plastic_strain))) * stress_factor
        true_total_strain = plastic_strain + true_stress / youngs_modulus
        engineering_strain = math.exp(true_total_strain) - 1.0
        engineering_stress = true_stress / (1.0 + engineering_strain)
        points.append(CurvePoint(engineering_strain, engineering_stress))
    last = points[-1]
    points.append(CurvePoint(last.engineering_strain + 0.03, last.engineering_stress * 0.80))
    return VoceEngineeringCurveInput(
        member_ordinal=member_ordinal,
        dataset_id=_uuid(100 + member_ordinal),
        dataset_revision_id=_uuid(200 + member_ordinal),
        test_run_id=_uuid(300 + member_ordinal),
        test_run_revision_id=_uuid(400 + member_ordinal),
        points=tuple(points),
    )


def test_multi_curve_voce_fit_is_deterministic_and_recovers_reference_parameters() -> None:
    plan = _plan()
    inputs = (
        _engineering_curve(0, stress_factor=0.995),
        _engineering_curve(1, stress_factor=1.005),
        _engineering_curve(2, stress_factor=1.0),
    )

    first = calibrate_reference_voce_curves(plan, inputs)
    second = calibrate_reference_voce_curves(plan, inputs)

    assert len(first) == 3
    assert first == second
    assert all(candidate.converged for candidate in first)
    assert all(candidate.identifiability_status == "not_assessed_reference" for candidate in first)
    assert all(candidate.uncertainty_status == "not_provided_reference" for candidate in first)
    best = min(first, key=lambda candidate: candidate.objective_total)
    sigma_0, q, b = best.calibrated_parameters
    assert sigma_0 == pytest.approx(300.0e6, rel=0.01)
    assert q == pytest.approx(160.0e6, rel=0.03)
    assert b == pytest.approx(12.0, rel=0.04)
    assert len(best.objective_terms) == 3
    assert all(term.point_count >= 5 for term in best.objective_terms)
    assert len(best.diagnostics) == sum(term.point_count for term in best.objective_terms)
    assert best.function_evaluations > 0
    assert best.residual_root_mean_square_pa < 3.0e6


def test_objective_gives_each_specimen_equal_total_weight() -> None:
    evaluator = ReferenceVoceMaterialModelEvaluator()
    objective = EqualSpecimenNormalizedObjectiveEngine()
    parameters = np.asarray([300.0e6, 100.0e6, 10.0], dtype=np.float64)

    def curve(ordinal: int, point_count: int, offset: float) -> VoceCalibrationCurve:
        observations = tuple(
            VocePlasticObservation(
                point_ordinal=index,
                true_plastic_strain=0.01 * (index + 1),
                observed_true_yield_stress_pa=float(
                    evaluator.evaluate(
                        parameters, np.asarray([0.01 * (index + 1)], dtype=np.float64)
                    )[0]
                )
                - offset,
            )
            for index in range(point_count)
        )
        return VoceCalibrationCurve(
            member_ordinal=ordinal,
            dataset_id=_uuid(500 + ordinal),
            dataset_revision_id=_uuid(600 + ordinal),
            test_run_id=_uuid(700 + ordinal),
            test_run_revision_id=_uuid(800 + ordinal),
            observations=observations,
        )

    residuals = objective.residual_vector(
        parameters,
        (curve(0, 3, 10.0e6), curve(1, 12, 10.0e6)),
        evaluator,
        100.0e6,
    )

    assert np.sum(residuals[:3] ** 2) == pytest.approx(np.sum(residuals[3:] ** 2))
    assert np.sum(residuals**2) == pytest.approx(0.01)


def test_test_mode_adapter_rejects_duplicate_test_run_revisions() -> None:
    first = _engineering_curve(0)
    second = _engineering_curve(1)
    duplicate = VoceEngineeringCurveInput(
        member_ordinal=1,
        dataset_id=second.dataset_id,
        dataset_revision_id=second.dataset_revision_id,
        test_run_id=second.test_run_id,
        test_run_revision_id=first.test_run_revision_id,
        points=second.points,
    )

    with pytest.raises(InvalidVoceCalibration, match="Test Run revisions must be distinct"):
        ReferenceUniaxialTensionTestModeAdapter().adapt(
            (first, duplicate), youngs_modulus_pa=210.0e9
        )


def test_test_mode_adapter_does_not_hide_pre_necking_softening() -> None:
    first = _engineering_curve(0)
    second = _engineering_curve(1)
    points = list(second.points)
    points[4] = CurvePoint(points[4].engineering_strain, points[3].engineering_stress * 0.90)
    points[5] = CurvePoint(points[5].engineering_strain, points[3].engineering_stress * 1.02)
    softened = VoceEngineeringCurveInput(
        member_ordinal=1,
        dataset_id=second.dataset_id,
        dataset_revision_id=second.dataset_revision_id,
        test_run_id=second.test_run_id,
        test_run_revision_id=second.test_run_revision_id,
        points=tuple(points),
    )

    with pytest.raises(InvalidVoceCalibration, match="softens"):
        ReferenceUniaxialTensionTestModeAdapter().adapt(
            (first, softened), youngs_modulus_pa=210.0e9
        )


def test_plan_canonical_pins_scope_weighting_optimizer_and_environment() -> None:
    canonical = reference_voce_calibration_plan_canonical(_plan())

    assert canonical["calibration_input_scope_revision_id"] == str(_uuid(2))
    assert canonical["model_family_id"] == "urn:cmp:reference:voce-saturation-hardening:1.0.0"
    objective = canonical["objective"]
    optimizer = canonical["optimizer"]
    assert isinstance(objective, dict)
    assert isinstance(optimizer, dict)
    assert objective["specimen_weighting"] == "equal_specimen"
    assert objective["missing_data_policy"] == "reject"
    assert optimizer["method"] == "trf"
    assert optimizer["rng_algorithm"] == "numpy.random.PCG64"
    assert isinstance(optimizer["environment_digest"], str)
    assert len(optimizer["environment_digest"]) == 64


def test_candidate_diagnostics_round_trip_as_typed_parquet() -> None:
    candidate = calibrate_reference_voce_curves(
        _plan(multistart_count=1),
        (_engineering_curve(0), _engineering_curve(1)),
    )[0]

    restored = reference_voce_diagnostics_from_parquet(
        reference_voce_diagnostics_parquet_bytes(candidate.diagnostics)
    )

    assert restored == candidate.diagnostics


def test_parameter_plan_rejects_initial_value_outside_bounds() -> None:
    with pytest.raises(InvalidVoceCalibration, match="initial value"):
        VoceParameterPlan("q_pa", "Pa", 1.0, 3.0, 2.0, 1.0)

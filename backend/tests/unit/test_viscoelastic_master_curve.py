from __future__ import annotations

import math
from uuid import uuid4

import pytest
from cmp.modules.datasets.domain.reference_shear_relaxation import ShearRelaxationPoint
from cmp.modules.processing.domain.viscoelastic_master_curve import (
    InvalidViscoelasticMasterPlan,
    ManualShiftFactor,
    ReplicateCurve,
    ShiftMethod,
    ViscoelasticMasterPlanContent,
    aligned_replicates_from_parquet,
    aligned_replicates_parquet_bytes,
    compute_viscoelastic_master_curve,
    master_curve_from_parquet,
    master_curve_parquet_bytes,
    temperature_statistics_from_parquet,
    temperature_statistics_parquet_bytes,
)


def _plan(
    *,
    reference_temperature_k: float,
    method: ShiftMethod,
    factors: tuple[ManualShiftFactor, ...] = (),
    grid: int = 31,
) -> ViscoelasticMasterPlanContent:
    return ViscoelasticMasterPlanContent(
        plan_label="Reference TTS master curve",
        selection_id=uuid4(),
        selection_revision_id=uuid4(),
        reference_temperature_k=reference_temperature_k,
        grid_point_count=grid,
        shift_method=method,
        manual_shift_factors=factors,
    )


def _curve(
    ordinal: int,
    temperature: float,
    log10_shift: float,
    scale: float = 1.0,
) -> ReplicateCurve:
    points = tuple(
        ShearRelaxationPoint(
            time_s=10.0**x,
            shear_modulus_pa=scale
            * (
                2_000_000.0
                + 8_000_000.0 / (1.0 + 10.0 ** (0.6 * (x - log10_shift)))
            ),
        )
        for x in (index / 4 - 4 for index in range(41))
    )
    return ReplicateCurve(ordinal, uuid4(), uuid4(), temperature, points)


def test_manual_shifts_align_replicates_and_preserve_pointwise_statistics() -> None:
    curves = (
        _curve(0, 293.15, 0.0),
        _curve(1, 293.15, 0.0, 1.01),
        _curve(2, 313.15, -1.0),
        _curve(3, 313.15, -1.0, 0.99),
    )
    result = compute_viscoelastic_master_curve(
        curves,
        _plan(
            reference_temperature_k=293.15,
            method=ShiftMethod.MANUAL,
            factors=(ManualShiftFactor(293.15, 0.0), ManualShiftFactor(313.15, -1.0)),
        ),
    )

    assert len(result.aligned_curves) == 4
    assert [item.replicate_count for item in result.temperature_statistics] == [2, 2]
    assert all(point.replicate_count == 2 for point in result.temperature_statistics[0].points)
    assert result.shift_factors[1].log10_a_t == -1.0
    assert len(result.master_curve) == 31
    assert all(point.contributing_curve_count >= 2 for point in result.master_curve)
    assert aligned_replicates_parquet_bytes(result).startswith(b"PAR1")
    assert temperature_statistics_parquet_bytes(result).startswith(b"PAR1")
    assert master_curve_parquet_bytes(result).startswith(b"PAR1")

    evidence = {
        curve.member_ordinal: (curve.dataset_revision_id, curve.test_run_revision_id)
        for curve in curves
    }
    restored_aligned = aligned_replicates_from_parquet(
        aligned_replicates_parquet_bytes(result), evidence
    )
    restored_statistics = temperature_statistics_from_parquet(
        temperature_statistics_parquet_bytes(result)
    )
    restored_master = master_curve_from_parquet(master_curve_parquet_bytes(result))
    assert restored_aligned == result.aligned_curves
    assert restored_statistics == result.temperature_statistics
    assert restored_master == result.master_curve
    assert aligned_replicates_parquet_bytes(result) == aligned_replicates_parquet_bytes(result)


def test_wlf_fit_recovers_synthetic_three_temperature_shifts() -> None:
    reference = 293.15
    c1 = 8.0
    c2 = 120.0
    temperatures = (273.15, reference, 313.15)
    shifts = tuple(
        -c1 * (temperature - reference) / (c2 + temperature - reference)
        for temperature in temperatures
    )
    curves = tuple(
        _curve(index, temperature, shift)
        for index, (temperature, shift) in enumerate(
            zip(temperatures, shifts, strict=True)
        )
    )

    result = compute_viscoelastic_master_curve(
        curves,
        _plan(reference_temperature_k=reference, method=ShiftMethod.WLF_FIT, grid=51),
    )

    assert result.wlf_c1 == pytest.approx(c1, rel=0.06)
    assert result.wlf_c2_k == pytest.approx(c2, rel=0.08)
    assert tuple(item.log10_a_t for item in result.shift_factors) == pytest.approx(shifts, abs=0.04)
    assert max(abs(item.residual_log10_a_t or 0.0) for item in result.shift_factors) < 0.04
    assert all(math.isfinite(point.mean_shear_modulus_pa) for point in result.master_curve)


def test_wlf_requires_three_temperatures_and_no_extrapolation() -> None:
    with pytest.raises(InvalidViscoelasticMasterPlan, match="at least three temperatures"):
        compute_viscoelastic_master_curve(
            (_curve(0, 293.15, 0.0), _curve(1, 313.15, -1.0)),
            _plan(reference_temperature_k=293.15, method=ShiftMethod.WLF_FIT),
        )

    first = _curve(0, 293.15, 0.0)
    disjoint = ReplicateCurve(
        1,
        uuid4(),
        uuid4(),
        293.15,
        tuple(
            ShearRelaxationPoint(10.0**x, 10_000_000.0 - index * 100_000.0)
            for index, x in enumerate((20.0, 21.0, 22.0))
        ),
    )
    with pytest.raises(InvalidViscoelasticMasterPlan, match="no common positive log-time domain"):
        compute_viscoelastic_master_curve(
            (first, disjoint),
            _plan(
                reference_temperature_k=293.15,
                method=ShiftMethod.MANUAL,
                factors=(ManualShiftFactor(293.15, 0.0),),
            ),
        )


def test_manual_shift_factors_must_cover_every_temperature() -> None:
    with pytest.raises(InvalidViscoelasticMasterPlan, match="cover every selected temperature"):
        compute_viscoelastic_master_curve(
            (_curve(0, 293.15, 0.0), _curve(1, 313.15, -1.0)),
            _plan(
                reference_temperature_k=293.15,
                method=ShiftMethod.MANUAL,
                factors=(ManualShiftFactor(293.15, 0.0),),
            ),
        )

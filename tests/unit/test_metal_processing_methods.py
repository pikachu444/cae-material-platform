from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

import pytest
from cmp.modules.datasets.domain.canonical_test_data import (
    CanonicalTestDataDocument,
    CanonicalTestDataError,
    ChannelAxisRole,
)
from cmp.modules.datasets.domain.canonical_test_data import (
    TestDataChannel as CanonicalChannel,
)
from cmp.modules.datasets.domain.canonical_test_data import (
    TestDataSource as CanonicalSource,
)
from cmp.modules.datasets.domain.canonical_test_data import (
    TestExecutionMetadata as ExecutionMetadata,
)
from cmp.modules.datasets.domain.canonical_test_data import (
    TestMaterialMetadata as MaterialMetadata,
)
from cmp.modules.datasets.domain.canonical_test_data import (
    TestSpecimenMetadata as SpecimenMetadata,
)
from cmp.modules.datasets.domain.curve_metadata import AxisRole
from cmp.modules.processing.domain.common_pipeline import (
    COMMON_METHOD_VERSION,
    MAX_PREVIEW_POINTS,
    ChannelBinding,
    CommonPipelineError,
    MappingProfileContent,
    MissingDataPolicy,
    ProcessingStep,
    curve_stage_series,
    preview_pipeline,
    processing_preview_canonical,
    toe_warning_codes,
)
from cmp.modules.processing.domain.metal_hardening import HARDENING_EQUATION_CONTRACT


def _values(items: tuple[float, ...]) -> tuple[Decimal, ...]:
    return tuple(Decimal(str(item)) for item in items)


STRAIN = (0.0, 0.0005, 0.001, 0.0015, 0.002, 0.003, 0.005, 0.01, 0.02, 0.05, 0.1, 0.15)
STRESS = (
    0.0,
    105e6,
    210e6,
    315e6,
    420e6,
    450e6,
    480e6,
    520e6,
    560e6,
    600e6,
    620e6,
    610e6,
)


def _document() -> CanonicalTestDataDocument:
    strain = _values(STRAIN)
    stress = _values(STRESS)
    missing = (None,) * len(strain)
    return CanonicalTestDataDocument(
        document_id="dp600-metal-method-fixture",
        material=MaterialMetadata("CMP Demo Metals", "DP600"),
        test=ExecutionMetadata(date(2026, 7, 18), "operator", "lab", "uniaxial tension"),
        specimen=SpecimenMetadata("DP600-S-1"),
        conditions=(),
        channels=(
            CanonicalChannel(
                "engineering_strain",
                "Engineering strain",
                "strain.engineering",
                ChannelAxisRole.INDEPENDENT,
                "1",
                "1",
                Decimal("1"),
                Decimal("0"),
                strain,
                strain,
                missing,
            ),
            CanonicalChannel(
                "engineering_stress",
                "Engineering stress",
                "stress.engineering",
                ChannelAxisRole.DEPENDENT,
                "Pa",
                "Pa",
                Decimal("1"),
                Decimal("0"),
                stress,
                stress,
                missing,
            ),
        ),
        source=CanonicalSource("dp600.json", "application/json", "0" * 64),
    )


def _profile() -> MappingProfileContent:
    return MappingProfileContent(
        profile_key="metal-tensile",
        label="Metal tensile quantities",
        independent_quantity="strain.engineering",
        missing_data_policy=MissingDataPolicy.REJECT,
        bindings=(
            ChannelBinding("engineering_strain", "strain.engineering", ("1",)),
            ChannelBinding("engineering_stress", "stress.engineering", ("Pa",)),
        ),
    )


def _toe_fixture() -> dict[str, Any]:
    return cast(
        dict[str, Any],
        json.loads(
            Path("fixtures/synthetic/tensile-toe-zero-intercept-v1.json").read_text(
                encoding="utf-8"
            )
        ),
    )


def _toe_document(
    strain_values: list[float],
    stress_values: list[float],
    *,
    strain_unit: str = "1",
    stress_unit: str = "Pa",
) -> CanonicalTestDataDocument:
    strain = _values(tuple(strain_values))
    stress = _values(tuple(stress_values))
    missing = (None,) * len(strain)
    return CanonicalTestDataDocument(
        document_id="synthetic-toe-fixture",
        material=MaterialMetadata("CMP synthetic", "Toe reference"),
        test=ExecutionMetadata(date(2026, 8, 13), "fixture", "fixture", "synthetic tensile"),
        specimen=SpecimenMetadata("TOE-S-1"),
        conditions=(),
        channels=(
            CanonicalChannel(
                "engineering_strain",
                "Engineering strain",
                "strain.engineering",
                ChannelAxisRole.INDEPENDENT,
                strain_unit,
                strain_unit,
                Decimal("1"),
                Decimal("0"),
                strain,
                strain,
                missing,
            ),
            CanonicalChannel(
                "engineering_stress",
                "Engineering stress",
                "stress.engineering",
                ChannelAxisRole.DEPENDENT,
                stress_unit,
                stress_unit,
                Decimal("1"),
                Decimal("0"),
                stress,
                stress,
                missing,
            ),
        ),
        source=CanonicalSource("synthetic-toe.json", "application/json", "2" * 64),
    )


def _toe_profile(*, strain_unit: str = "1", stress_unit: str = "Pa") -> MappingProfileContent:
    return MappingProfileContent(
        profile_key="synthetic-toe",
        label="Synthetic toe quantities",
        independent_quantity="strain.engineering",
        missing_data_policy=MissingDataPolicy.REJECT,
        bindings=(
            ChannelBinding("engineering_strain", "strain.engineering", (strain_unit,)),
            ChannelBinding("engineering_stress", "stress.engineering", (stress_unit,)),
        ),
    )


def _toe_step(
    minimum: float,
    maximum: float,
    *,
    warning_acknowledged: bool = False,
) -> ProcessingStep:
    return ProcessingStep(
        "tensile.toe_zero_intercept",
        COMMON_METHOD_VERSION,
        {
            "strain_quantity": "strain.engineering",
            "stress_quantity": "stress.engineering",
            "minimum_strain": minimum,
            "maximum_strain": maximum,
            "equipment_compliance": "not_provided",
            "warning_acknowledged": warning_acknowledged,
        },
    )


def _elastic(method: str, manual: float = 210e9) -> ProcessingStep:
    return ProcessingStep(
        "metal.elastic_modulus",
        COMMON_METHOD_VERSION,
        {
            "strain_quantity": "strain.engineering",
            "stress_quantity": "stress.engineering",
            "method": method,
            "minimum_strain": 0.0005,
            "maximum_strain": 0.002,
            "manual_modulus_pa": manual,
        },
    )


def test_toe_zero_intercept_recovers_synthetic_offsets_and_replays_deterministically() -> None:
    fixture = _toe_fixture()
    cases = fixture["cases"]
    assert isinstance(cases, dict)

    for name in ("noiseless_known_offset", "no_toe", "bounded_noise"):
        case = cases[name]
        assert isinstance(case, dict)
        source_strain = [float(value) for value in case["source_strain"]]
        source_stress = [float(value) for value in case["source_stress_pa"]]
        step = _toe_step(float(case["minimum_strain"]), float(case["maximum_strain"]))
        document = _toe_document(source_strain, source_stress)
        first = preview_pipeline(document, _toe_profile(), (step,))
        second = preview_pipeline(document, _toe_profile(), (step,))
        assert processing_preview_canonical(first) == processing_preview_canonical(second)

        stage = first.stages[-1]
        scalars = {item.key: item.value for item in stage.scalar_results}
        expected_offset = float(case["expected_offset"])
        tolerance = 2e-5 if name == "bounded_noise" else 1e-12
        assert abs(scalars["toe_strain_offset"] - expected_offset) <= tolerance
        assert scalars["toe_estimated_slope"] == pytest.approx(
            float(case["expected_slope_pa"]), rel=1e-12, abs=1e-15
        )
        corrected = next(
            item.values for item in stage.series if item.quantity == "strain.engineering"
        )
        persisted_stress = next(
            item.values for item in stage.series if item.quantity == "stress.engineering"
        )
        assert corrected == pytest.approx(
            tuple(value - scalars["toe_strain_offset"] for value in source_strain),
            rel=1e-12,
            abs=1e-15,
        )
        assert persisted_stress == tuple(source_stress)
        assert "equipment_compliance=not_provided" in stage.diagnostics[1]
        if name == "no_toe":
            assert corrected == pytest.approx(tuple(source_strain), abs=1e-15)


def test_toe_zero_intercept_exposes_quality_warning_without_hiding_preview() -> None:
    strain = [0.0002, 0.0006, 0.0010, 0.0014, 0.0018, 0.0022]
    stress = [0.0, 30e6, 170e6, 115e6, 390e6, 300e6]
    stage = preview_pipeline(
        _toe_document(strain, stress),
        _toe_profile(),
        (_toe_step(0.0002, 0.0022),),
    ).stages[-1]

    warnings = toe_warning_codes(stage)
    assert "toe.warning.low_linearity" in warnings
    assert next(item.value for item in stage.scalar_results if item.key == "toe_r_squared") < 0.995
    assert next(
        item.values for item in stage.series if item.quantity == "stress.engineering"
    ) == tuple(stress)

    offset_warning_stage = preview_pipeline(
        _toe_document(
            [0.0, 0.0004, 0.0008, 0.0012, 0.0016, 0.0020],
            [2.0e9, 2.08e9, 2.16e9, 2.24e9, 2.32e9, 2.4e9],
        ),
        _toe_profile(),
        (_toe_step(0.0, 0.0020),),
    ).stages[-1]
    assert "toe.warning.offset_exceeds_domain" in toe_warning_codes(offset_warning_stage)


@pytest.mark.parametrize(
    ("strain", "stress", "minimum", "maximum", "message"),
    [
        ([0.0, 0.0005, 0.001, 0.0015], [0.0, 1.0, 2.0, 3.0], 0.0, 0.0015, "at least five"),
        (
            [0.0, 0.0005, 0.0005, 0.0015, 0.002],
            [0.0, 1.0, 2.0, 3.0, 4.0],
            0.0,
            0.002,
            "strictly increasing",
        ),
        (
            [0.0, 0.001, 0.0005, 0.0015, 0.002],
            [0.0, 1.0, 2.0, 3.0, 4.0],
            0.0,
            0.002,
            "strictly increasing",
        ),
        (
            [0.0, 0.0005, 0.001, 0.0015, 0.002],
            [5.0, 4.0, 3.0, 2.0, 1.0],
            0.0,
            0.002,
            "positive and numerically stable",
        ),
    ],
)
def test_toe_zero_intercept_rejects_ineligible_domains(
    strain: list[float],
    stress: list[float],
    minimum: float,
    maximum: float,
    message: str,
) -> None:
    with pytest.raises(CommonPipelineError, match=message):
        preview_pipeline(
            _toe_document(strain, stress),
            _toe_profile(),
            (_toe_step(minimum, maximum),),
        )


def test_toe_zero_intercept_rejects_incompatible_normalized_units() -> None:
    fixture = _toe_fixture()
    case = fixture["cases"]["noiseless_known_offset"]
    assert isinstance(case, dict)
    with pytest.raises(CommonPipelineError, match="normalized strain unit 1 and stress unit Pa"):
        preview_pipeline(
            _toe_document(
                [float(value) for value in case["source_strain"]],
                [float(value) for value in case["source_stress_pa"]],
                stress_unit="MPa",
            ),
            _toe_profile(stress_unit="MPa"),
            (_toe_step(float(case["minimum_strain"]), float(case["maximum_strain"])),),
        )


def test_toe_zero_intercept_rejects_non_finite_source_values() -> None:
    with pytest.raises(CanonicalTestDataError, match="original point 2 must be finite"):
        _toe_document(
            [0.0, 0.0005, 0.001, 0.0015, 0.002],
            [0.0, 100e6, float("nan"), 300e6, 400e6],
        )


def test_toe_preview_retains_the_deterministic_interactive_point_bound() -> None:
    oversized = cast(Any, type("OversizedDocument", (), {"point_count": MAX_PREVIEW_POINTS + 1})())
    with pytest.raises(CommonPipelineError, match="at most 100000 points"):
        preview_pipeline(oversized, _toe_profile(), (_toe_step(0.0, 0.002),))


@pytest.mark.parametrize(
    ("method", "expected"),
    [
        ("linear_regression", 210e9),
        ("robust_huber", 210e9),
        ("chord", 210e9),
        ("secant", 210e9),
        ("manual", 205e9),
    ],
)
def test_elastic_modulus_methods_have_explicit_reproducible_results(
    method: str, expected: float
) -> None:
    stage = preview_pipeline(
        _document(), _profile(), (_elastic(method, 205e9),)
    ).stages[-1]
    modulus = next(item for item in stage.scalar_results if item.key == "youngs_modulus")
    assert modulus.value == pytest.approx(expected, rel=1e-10)
    assert modulus.unit == "Pa"
    assert method in stage.diagnostics[0]


def test_offset_proof_stress_and_true_plastic_conversion_are_explicit() -> None:
    proof = ProcessingStep(
        "metal.proof_stress",
        COMMON_METHOD_VERSION,
        {
            "strain_quantity": "strain.engineering",
            "stress_quantity": "stress.engineering",
            "youngs_modulus_pa": 210e9,
            "offset_strain": 0.002,
            "search_start": 0.002,
            "search_end": 0.02,
        },
    )
    conversion = ProcessingStep(
        "metal.engineering_to_true_plastic",
        COMMON_METHOD_VERSION,
        {
            "strain_quantity": "strain.engineering",
            "stress_quantity": "stress.engineering",
            "youngs_modulus_pa": 210e9,
            "necking_policy": "manual_index",
            "manual_necking_index": 10,
            "negative_plastic_policy": "drop",
        },
    )
    necking_candidate = ProcessingStep(
        "metal.necking_candidate",
        COMMON_METHOD_VERSION,
        {
            "strain_quantity": "strain.engineering",
            "stress_quantity": "stress.engineering",
            "method": "peak_engineering_stress",
        },
    )
    result = preview_pipeline(
        _document(),
        _profile(),
        (_elastic("robust_huber"), proof, necking_candidate, conversion),
    )

    proof_stage = result.stages[2]
    proof_stress = next(
        item.value for item in proof_stage.scalar_results if item.key == "proof_stress"
    )
    proof_strain = next(
        item.value for item in proof_stage.scalar_results if item.key == "proof_strain"
    )
    assert proof_stress == pytest.approx(468_461_538.46153843)
    assert proof_strain == pytest.approx(0.004230769230769231)

    candidate = result.stages[3]
    assert candidate.point_count == len(STRAIN)
    candidate_values = {item.key: item.value for item in candidate.scalar_results}
    assert candidate_values["necking_candidate_index"] == 10
    assert "no point was cropped or confirmed" in candidate.diagnostics[0]

    converted = result.stages[4]
    series = {item.quantity: item.values for item in converted.series}
    assert converted.point_count == 6
    assert series["stress.true"][-1] == pytest.approx(682e6)
    assert series["strain.true"][-1] == pytest.approx(0.09531017980432487)
    assert series["strain.true_plastic"][-1] == pytest.approx(
        0.09531017980432487 - 682e6 / 210e9
    )
    necking = {item.key: item.value for item in converted.scalar_results}
    assert necking["necking_index"] == 10
    assert necking["necking_engineering_stress"] == 620e6


def test_metal_methods_reject_non_si_normalized_units() -> None:
    incompatible = MappingProfileContent(
        profile_key="metal-tensile-mpa",
        label="Non-normalized metal tensile quantities",
        independent_quantity="strain.engineering",
        missing_data_policy=MissingDataPolicy.REJECT,
        bindings=(
            ChannelBinding("engineering_strain", "strain.engineering", ("1",)),
            ChannelBinding("engineering_stress", "stress.engineering", ("Pa",)),
        ),
    )
    document = _document()
    stress = document.channels[1]
    mpa_values = tuple(
        value / Decimal("1e6") if value is not None else None
        for value in stress.original_values
    )
    document = CanonicalTestDataDocument(
        document_id=document.document_id,
        material=document.material,
        test=document.test,
        specimen=document.specimen,
        conditions=document.conditions,
        channels=(
            document.channels[0],
            CanonicalChannel(
                stress.key,
                stress.name,
                stress.quantity_semantics,
                stress.axis_role,
                stress.original_unit_string,
                "MPa",
                Decimal("1e-6"),
                stress.normalization_offset,
                stress.original_values,
                mpa_values,
                stress.missing_reasons,
            ),
        ),
        source=document.source,
    )
    incompatible = MappingProfileContent(
        profile_key=incompatible.profile_key,
        label=incompatible.label,
        independent_quantity=incompatible.independent_quantity,
        missing_data_policy=incompatible.missing_data_policy,
        bindings=(
            incompatible.bindings[0],
            ChannelBinding("engineering_stress", "stress.engineering", ("MPa",)),
        ),
    )

    with pytest.raises(CommonPipelineError, match="normalized strain unit 1 and stress unit Pa"):
        preview_pipeline(document, incompatible, (_elastic("linear_regression"),))


def test_processed_true_plastic_curve_feeds_bounded_hardening_candidates() -> None:
    conversion = ProcessingStep(
        "metal.engineering_to_true_plastic",
        COMMON_METHOD_VERSION,
        {
            "strain_quantity": "strain.engineering",
            "stress_quantity": "stress.engineering",
            "youngs_modulus_pa": 210e9,
            "necking_policy": "manual_index",
            "manual_necking_index": 10,
            "negative_plastic_policy": "drop",
        },
    )
    hardening = ProcessingStep(
        "metal.hardening_fit_extrapolate",
        COMMON_METHOD_VERSION,
        {
            "equation_contract": HARDENING_EQUATION_CONTRACT,
            "plastic_strain_quantity": "strain.true_plastic",
            "stress_quantity": "stress.true",
            "families": ["voce", "swift", "hockett_sherby", "ghosh"],
            "fit_minimum_strain": 0.0001,
            "fit_maximum_strain": 0.1,
            "extrapolation_maximum_strain": 0.5,
            "output_point_count": 101,
            "primary_family": "swift",
            "secondary_family": "voce",
            "primary_weight": 0.5,
            "normalization_stress_pa": 100e6,
            "maximum_function_evaluations": 10_000,
        },
    )

    preview = preview_pipeline(_document(), _profile(), (conversion, hardening))
    stage = preview.stages[-1]
    series = {item.quantity: item.values for item in stage.series}
    assert stage.point_count == 101
    assert series["strain.true_plastic"][-1] == 0.5
    assert "stress.hardening.selected" in series
    assert all(
        right >= left
        for left, right in zip(
            series["stress.hardening.selected"],
            series["stress.hardening.selected"][1:],
            strict=False,
        )
    )
    assert any(item.key == "voce.relative_rmse" for item in stage.scalar_results)
    assert any("extrapolated domain" in item for item in stage.diagnostics)
    assert stage.independent_quantity == "strain.true_plastic"
    definition = curve_stage_series(stage, preview.independent_quantity).definition
    assert [
        channel.key
        for channel in definition.channels
        if channel.axis_role is AxisRole.INDEPENDENT
    ] == ["strain.true_plastic"]
    assert {
        channel.label
        for channel in definition.channels
        if channel.quantity_semantics.startswith("stress.hardening.")
    } == {"Hardening stress"}
    hardening_channels = [
        channel
        for channel in definition.channels
        if channel.quantity_semantics.startswith("stress.hardening.")
    ]
    assert {channel.unit_contract.value for channel in hardening_channels} == {
        "explicit_legacy"
    }
    assert {channel.normalized_unit for channel in hardening_channels} == {"Pa"}
    assert {channel.display_unit for channel in hardening_channels} == {"MPa"}
    assert {channel.display_scale for channel in hardening_channels} == {"0.000001"}
    canonical = processing_preview_canonical(preview)
    stages = canonical["stages"]
    assert isinstance(stages, list)
    final_stage = stages[-1]
    assert isinstance(final_stage, dict)
    assert final_stage["curve_definition_sha256"] == definition.sha256

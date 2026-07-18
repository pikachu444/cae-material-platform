import math
from datetime import date
from decimal import Decimal

import pytest
from cmp.modules.datasets.domain.canonical_test_data import (
    CanonicalTestDataDocument,
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
from cmp.modules.processing.domain.common_pipeline import (
    COMMON_METHOD_VERSION,
    METHOD_REGISTRY,
    ChannelBinding,
    CommonPipelineError,
    MappingProfileContent,
    MissingDataPolicy,
    ProcessingStep,
    preview_pipeline,
)


def _document(*, duplicate: bool = False) -> CanonicalTestDataDocument:
    x = (Decimal("0"), Decimal("1"), Decimal("1" if duplicate else "2"), Decimal("3"), Decimal("4"))
    y = (Decimal("0"), Decimal("2"), Decimal("5"), Decimal("6"), Decimal("9"))
    return CanonicalTestDataDocument(
        document_id="curve-001",
        material=MaterialMetadata("Demo", "Generic"),
        test=ExecutionMetadata(date(2026, 7, 18), "operator", "lab", "generic curve"),
        specimen=SpecimenMetadata("S-1"),
        conditions=(),
        channels=(
            CanonicalChannel(
                "x",
                "X",
                "axis.x",
                ChannelAxisRole.INDEPENDENT,
                "s",
                "s",
                Decimal("1"),
                Decimal("0"),
                x,
                x,
                (None,) * 5,
            ),
            CanonicalChannel(
                "y",
                "Y",
                "response.y",
                ChannelAxisRole.DEPENDENT,
                "Pa",
                "Pa",
                Decimal("1"),
                Decimal("0"),
                y,
                y,
                (None,) * 5,
            ),
        ),
        source=CanonicalSource("curve.json", "application/json", "0" * 64),
    )


def _profile() -> MappingProfileContent:
    return MappingProfileContent(
        profile_key="generic-x-y",
        label="Generic X/Y",
        independent_quantity="calculation.x",
        missing_data_policy=MissingDataPolicy.REJECT,
        bindings=(
            ChannelBinding("x", "calculation.x", ("s",)),
            ChannelBinding("y", "calculation.y", ("Pa",)),
        ),
    )


def _relaxation_document() -> CanonicalTestDataDocument:
    times = tuple(Decimal(str(10 ** (-2 + ordinal * 4 / 30))) for ordinal in range(31))
    moduli = tuple(
        Decimal(
            str(
                2.0e6 + 3.0e6 * math.exp(-float(time) / 0.1) + 5.0e6 * math.exp(-float(time) / 10.0)
            )
        )
        for time in times
    )
    return CanonicalTestDataDocument(
        document_id="relaxation-001",
        material=MaterialMetadata("Demo", "Polymer"),
        test=ExecutionMetadata(date(2026, 7, 18), "operator", "lab", "shear relaxation"),
        specimen=SpecimenMetadata("P-1"),
        conditions=(),
        channels=(
            CanonicalChannel(
                "time",
                "Time",
                "time",
                ChannelAxisRole.INDEPENDENT,
                "s",
                "s",
                Decimal("1"),
                Decimal("0"),
                times,
                times,
                (None,) * len(times),
            ),
            CanonicalChannel(
                "modulus",
                "Shear modulus",
                "modulus.shear.relaxation",
                ChannelAxisRole.DEPENDENT,
                "Pa",
                "Pa",
                Decimal("1"),
                Decimal("0"),
                moduli,
                moduli,
                (None,) * len(moduli),
            ),
        ),
        source=CanonicalSource("relaxation.json", "application/json", "1" * 64),
    )


def _relaxation_profile() -> MappingProfileContent:
    return MappingProfileContent(
        profile_key="polymer-relaxation",
        label="Polymer shear relaxation",
        independent_quantity="time",
        missing_data_policy=MissingDataPolicy.REJECT,
        bindings=(
            ChannelBinding("time", "time", ("s",)),
            ChannelBinding("modulus", "modulus.shear.relaxation", ("Pa",)),
        ),
    )


def _step(method: str, **options: object) -> ProcessingStep:
    return ProcessingStep(method, COMMON_METHOD_VERSION, dict(options))


def test_registry_exposes_versioned_solver_neutral_methods() -> None:
    assert {item.method_id for item in METHOD_REGISTRY} == {
        "rows.sort_unique",
        "curve.crop",
        "curve.scale_shift",
        "curve.resample_linear",
        "curve.moving_average",
        "curve.savitzky_golay",
        "curve.smoothing_spline",
        "metal.elastic_modulus",
        "metal.proof_stress",
        "metal.necking_candidate",
        "metal.engineering_to_true_plastic",
        "metal.hardening_fit_extrapolate",
        "polymer.log_time_resample",
        "polymer.prony_fit_compare",
    }
    assert all(item.deterministic for item in METHOD_REGISTRY)
    assert {item.method_id for item in METHOD_REGISTRY if item.allows_extrapolation} == {
        "metal.hardening_fit_extrapolate"
    }


def test_polymer_log_time_and_prony_candidates_are_explicit_and_deterministic() -> None:
    steps = (
        _step("rows.sort_unique", duplicate_policy="reject"),
        _step(
            "polymer.log_time_resample",
            start_time_s=0.01,
            end_time_s=100.0,
            count=31,
            extrapolation="reject",
        ),
        _step(
            "polymer.prony_fit_compare",
            time_quantity="time",
            modulus_quantity="modulus.shear.relaxation",
            candidate_term_counts=[1, 2, 3],
            selection_mode="automatic_bic",
            selected_term_count=2,
            normalization_modulus_pa=10.0e6,
            minimum_relaxation_time_s=0.001,
            maximum_relaxation_time_s=1000.0,
            maximum_function_evaluations=5000,
        ),
    )
    first = preview_pipeline(_relaxation_document(), _relaxation_profile(), steps)
    second = preview_pipeline(_relaxation_document(), _relaxation_profile(), steps)
    assert first == second
    assert first.stages[2].point_count == 31
    assert "extrapolation rejected" in first.stages[2].diagnostics[-1]
    fitted = first.stages[-1]
    quantities = {item.quantity for item in fitted.series}
    assert {
        "modulus.prony.candidate_1_term",
        "modulus.prony.candidate_2_term",
        "modulus.prony.candidate_3_term",
        "modulus.prony.selected",
    } <= quantities
    scalars = {item.key: item.value for item in fitted.scalar_results}
    assert scalars["prony_selected_term_count"] == 2
    assert scalars["prony_g_ratio_1"] + scalars["prony_g_ratio_2"] < 1
    assert scalars["prony_2_normalized_rmse"] < 1e-7


def test_polymer_methods_reject_nonpositive_time_and_unfitted_manual_choice() -> None:
    with pytest.raises(CommonPipelineError, match="positive"):
        preview_pipeline(
            _document(),
            _profile(),
            (
                _step(
                    "polymer.log_time_resample",
                    start_time_s=0.1,
                    end_time_s=4.0,
                    count=10,
                    extrapolation="reject",
                ),
            ),
        )
    with pytest.raises(CommonPipelineError, match="manual selected_term_count"):
        preview_pipeline(
            _relaxation_document(),
            _relaxation_profile(),
            (
                _step("rows.sort_unique", duplicate_policy="reject"),
                _step(
                    "polymer.prony_fit_compare",
                    time_quantity="time",
                    modulus_quantity="modulus.shear.relaxation",
                    candidate_term_counts=[1, 2],
                    selection_mode="manual",
                    selected_term_count=3,
                    normalization_modulus_pa=10.0e6,
                    minimum_relaxation_time_s=0.001,
                    maximum_relaxation_time_s=1000.0,
                    maximum_function_evaluations=5000,
                ),
            ),
        )


def test_pipeline_preserves_every_stage_and_applies_explicit_operations() -> None:
    result = preview_pipeline(
        _document(),
        _profile(),
        (
            _step("rows.sort_unique", duplicate_policy="reject"),
            _step("curve.crop", minimum=1.0, maximum=4.0),
            _step("curve.scale_shift", quantity="calculation.y", scale=2.0, offset=-1.0),
            _step("curve.resample_linear", start=1.0, end=4.0, count=7, extrapolation="reject"),
            _step("curve.savitzky_golay", quantity="calculation.y", window=5, polynomial_order=2),
        ),
    )

    assert [stage.method_id for stage in result.stages] == [
        "mapping",
        "rows.sort_unique",
        "curve.crop",
        "curve.scale_shift",
        "curve.resample_linear",
        "curve.savitzky_golay",
    ]
    assert result.stages[0].point_count == 5
    assert result.stages[2].point_count == 4
    assert result.stages[4].point_count == 7
    final_y = next(
        item.values for item in result.stages[-1].series if item.quantity == "calculation.y"
    )
    assert len(final_y) == 7
    assert result.source_document_sha256 == _document().digest
    assert result.mapping_profile_sha256 == _profile().digest


def test_duplicate_and_extrapolation_policies_are_never_silent() -> None:
    with pytest.raises(CommonPipelineError, match="duplicates"):
        preview_pipeline(
            _document(duplicate=True),
            _profile(),
            (_step("rows.sort_unique", duplicate_policy="reject"),),
        )

    with pytest.raises(CommonPipelineError, match="extrapolate"):
        preview_pipeline(
            _document(),
            _profile(),
            (
                _step("rows.sort_unique", duplicate_policy="reject"),
                _step(
                    "curve.resample_linear",
                    start=-1.0,
                    end=4.0,
                    count=5,
                    extrapolation="reject",
                ),
            ),
        )


def test_public_smoothing_fixtures_are_deterministic() -> None:
    steps = (
        _step("rows.sort_unique", duplicate_policy="reject"),
        _step("curve.moving_average", quantity="calculation.y", window=3),
        _step("curve.smoothing_spline", quantity="calculation.y", smoothing_factor=0.0),
    )
    first = preview_pipeline(_document(), _profile(), steps)
    second = preview_pipeline(_document(), _profile(), steps)
    assert first == second
    moving = next(
        item.values for item in first.stages[2].series if item.quantity == "calculation.y"
    )
    assert moving == pytest.approx((4 / 3, 7 / 3, 13 / 3, 20 / 3, 7.0))

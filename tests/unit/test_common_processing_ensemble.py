from __future__ import annotations

import copy
import json
from decimal import Decimal
from pathlib import Path

import pytest
from cmp.modules.datasets.domain.canonical_test_data import (
    CanonicalTestDataDocument,
    parse_canonical_test_data,
)
from cmp.modules.processing.domain.common_ensemble import (
    EnsembleAlignmentOptions,
    preview_ensemble,
)
from cmp.modules.processing.domain.common_pipeline import (
    ChannelBinding,
    CommonPipelineError,
    MappingProfileContent,
    MissingDataPolicy,
    ProcessingStep,
)


def _document(
    stress_scale: float, strain_shift: float = 0.0, *, reverse: bool = False
) -> CanonicalTestDataDocument:
    value = json.loads(
        Path("contracts/examples/positive/canonical-test-data.json").read_text(
            encoding="utf-8"
        )
    )
    value = copy.deepcopy(value)
    for channel in value["channels"]:
        if channel["key"] == "engineering_strain":
            channel["original_values"] = [
                None if item is None else str(Decimal(item) + Decimal(str(strain_shift)))
                for item in channel["original_values"]
            ]
        if channel["key"] == "engineering_stress":
            channel["original_values"] = [
                None if item is None else str(Decimal(item) * Decimal(str(stress_scale)))
                for item in channel["original_values"]
            ]
        scale = Decimal(channel["normalization"]["scale"])
        offset = Decimal(channel["normalization"]["offset"])
        channel["normalized_values"] = [
            None if item is None else str(Decimal(item) * scale + offset)
            for item in channel["original_values"]
        ]
        if reverse:
            channel["original_values"].reverse()
            channel["normalized_values"].reverse()
            channel["missing_reasons"].reverse()
    value["document_id"] = f"replicate-{stress_scale}-{strain_shift}"
    return parse_canonical_test_data(value)


def _profile() -> MappingProfileContent:
    return MappingProfileContent(
        profile_key="replicate-tensile",
        label="Replicate tensile",
        independent_quantity="strain.engineering",
        missing_data_policy=MissingDataPolicy.DROP_ANY,
        bindings=(
            ChannelBinding("engineering_strain", "strain.engineering", ("1",)),
            ChannelBinding("engineering_stress", "stress.engineering", ("Pa",)),
        ),
    )


def test_ensemble_retains_members_and_computes_public_pointwise_statistics() -> None:
    result = preview_ensemble(
        (_document(1.0), _document(1.2)),
        _profile(),
        (ProcessingStep("rows.sort_unique", "1.0.0", {"duplicate_policy": "reject"}),),
        EnsembleAlignmentOptions(point_count=3),
    )
    assert len(result.members) == 2
    assert result.grid == pytest.approx((0.0, 0.0005, 0.001))
    stress = result.statistics[0]
    assert stress.quantity == "stress.engineering"
    assert stress.mean[-1] == pytest.approx(225_500_000.0)
    assert stress.median[-1] == pytest.approx(225_500_000.0)
    assert stress.standard_deviation[-1] == pytest.approx(28_991_378.02864845)
    assert stress.mad[-1] == pytest.approx(20_500_000.0)
    assert stress.q1[-1] == pytest.approx(215_250_000.0)
    assert stress.q3[-1] == pytest.approx(235_750_000.0)


def test_ensemble_uses_observed_intersection_and_rejects_unsorted_input() -> None:
    result = preview_ensemble(
        (_document(1.0), _document(1.0, 0.02)),
        _profile(),
        (ProcessingStep("rows.sort_unique", "1.0.0", {"duplicate_policy": "reject"}),),
        EnsembleAlignmentOptions(point_count=2),
    )
    assert result.grid == pytest.approx((0.0002, 0.001))

    with pytest.raises(CommonPipelineError, match="sorted unique"):
        preview_ensemble(
            (_document(1.0), _document(1.2, reverse=True)),
            _profile(),
            (),
            EnsembleAlignmentOptions(point_count=3),
        )

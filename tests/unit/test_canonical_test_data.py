from datetime import date
from decimal import Decimal

import pytest
from cmp.modules.datasets.domain.canonical_test_data import (
    CanonicalTestDataDocument,
    CanonicalTestDataError,
    ChannelAxisRole,
    canonical_test_data,
)
from cmp.modules.datasets.domain.canonical_test_data import TestDataChannel as DataChannel
from cmp.modules.datasets.domain.canonical_test_data import TestDataSource as DataSource
from cmp.modules.datasets.domain.canonical_test_data import (
    TestExecutionMetadata as ExecutionMetadata,
)
from cmp.modules.datasets.domain.canonical_test_data import (
    TestMaterialMetadata as MaterialMetadata,
)
from cmp.modules.datasets.domain.canonical_test_data import (
    TestSpecimenMetadata as SpecimenMetadata,
)


def _channel(key: str, role: ChannelAxisRole, *, bad: bool = False) -> DataChannel:
    return DataChannel(
        key=key,
        name=key.replace("_", " ").title(),
        quantity_semantics=f"mechanics.{key}",
        axis_role=role,
        original_unit_string="MPa" if role is ChannelAxisRole.DEPENDENT else "%",
        normalized_unit="Pa" if role is ChannelAxisRole.DEPENDENT else "1",
        normalization_scale=Decimal("1000000")
        if role is ChannelAxisRole.DEPENDENT
        else Decimal("0.01"),
        normalization_offset=Decimal("0"),
        original_values=(Decimal("0"), Decimal("1"), None),
        normalized_values=(
            Decimal("0"),
            Decimal("999")
            if bad
            else (Decimal("1000000") if role is ChannelAxisRole.DEPENDENT else Decimal("0.01")),
            None,
        ),
        missing_reasons=(None, None, "instrument dropout"),
    )


def _document(*, bad: bool = False) -> CanonicalTestDataDocument:
    return CanonicalTestDataDocument(
        document_id="DP600-TENSILE-01",
        material=MaterialMetadata("CMP Demo Metals", "DP600", "LOT-2026-07"),
        test=ExecutionMetadata(
            date(2026, 7, 18),
            "Kim Tester",
            "CMP Laboratory",
            "uniaxial tensile reference method",
            "Demo Instruments",
            "UTM-01",
        ),
        specimen=SpecimenMetadata("S-01", "sheet coupon"),
        conditions=(),
        channels=(
            _channel("engineering_strain", ChannelAxisRole.INDEPENDENT),
            _channel("engineering_stress", ChannelAxisRole.DEPENDENT, bad=bad),
        ),
        source=DataSource("dp600.csv", "text/csv", "a" * 64),
    )


def test_canonical_test_data_preserves_units_missingness_and_deterministic_digest() -> None:
    document = _document()
    encoded = canonical_test_data(document)

    assert document.point_count == 3
    assert encoded["channels"][1]["original_unit_string"] == "MPa"
    assert encoded["channels"][1]["normalized_unit"] == "Pa"
    assert encoded["channels"][1]["missing_reasons"][-1] == "instrument dropout"
    assert document.digest == _document().digest


def test_canonical_test_data_rejects_hidden_or_incorrect_normalization() -> None:
    with pytest.raises(CanonicalTestDataError, match="explicit normalization"):
        _document(bad=True)


def test_canonical_test_data_requires_reason_for_every_missing_point() -> None:
    with pytest.raises(CanonicalTestDataError, match="requires a missing reason"):
        DataChannel(
            key="time",
            name="Time",
            quantity_semantics="time.elapsed",
            axis_role=ChannelAxisRole.INDEPENDENT,
            original_unit_string="s",
            normalized_unit="s",
            normalization_scale=Decimal("1"),
            normalization_offset=Decimal("0"),
            original_values=(Decimal("0"), None),
            normalized_values=(Decimal("0"), None),
            missing_reasons=(None, None),
        )

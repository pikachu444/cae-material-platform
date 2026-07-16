from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import pytest
from cmp.modules.testing.domain.reference_tensile import InvalidTestingData
from cmp.modules.testing.domain.test_context import (
    CalibrationResult,
    InstrumentCalibrationContent,
    LoadingRateUnit,
    StandardConformance,
)
from cmp.modules.testing.domain.test_context import (
    TestCampaignContent as _TestCampaignContent,
)
from cmp.modules.testing.domain.test_context import (
    TestConditionContent as _TestConditionContent,
)


def _id(value: int) -> UUID:
    return UUID(f"40000000-0000-4000-8000-{value:012d}")


def _calibration(
    value: int,
    start: datetime,
    end: datetime,
    result: CalibrationResult = CalibrationResult.PASSED,
) -> InstrumentCalibrationContent:
    return InstrumentCalibrationContent(
        instrument_id=_id(1),
        instrument_revision_id=_id(2),
        calibration_code=f"CAL-{value}",
        certificate_reference=f"CERT-{value}",
        provider="Reference laboratory",
        calibrated_at=start,
        valid_from=start,
        valid_until=end,
        result=result,
        limitation_note="axial channel only" if result is CalibrationResult.LIMITED else None,
    )


def test_campaign_requires_explicit_standard_deviation_evidence() -> None:
    with pytest.raises(InvalidTestingData, match="standard_deviation_reason"):
        _TestCampaignContent(
            _id(1),
            _id(2),
            "CMP-001",
            "Reference campaign",
            "Characterize tensile response",
            "Three rolling-direction coupons",
            3,
            StandardConformance.DEVIATION_APPROVED,
            "ISO 6892-1",
            "2019",
            None,
        )


def test_calibration_validity_is_half_open_and_overlap_is_explicit() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    first = _calibration(1, start, start + timedelta(days=365))
    overlapping = _calibration(2, start + timedelta(days=300), start + timedelta(days=600))
    adjacent = _calibration(3, start + timedelta(days=365), start + timedelta(days=700))

    assert first.covers(start)
    assert not first.covers(start + timedelta(days=365))
    assert first.overlaps(overlapping)
    assert not first.overlaps(adjacent)


def test_condition_snapshot_rejects_empty_or_partial_loading_rate() -> None:
    with pytest.raises(InvalidTestingData, match="cannot be empty"):
        _TestConditionContent(
            _id(1),
            _id(2),
            datetime(2026, 7, 16, tzinfo=UTC),
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
        )
    with pytest.raises(InvalidTestingData, match="supplied together"):
        _TestConditionContent(
            _id(1),
            _id(2),
            datetime(2026, 7, 16, tzinfo=UTC),
            Decimal("296.15"),
            None,
            None,
            None,
            Decimal("2"),
            None,
            "rolling",
            "air",
            None,
        )

    value = _TestConditionContent(
        _id(1),
        _id(2),
        datetime(2026, 7, 16, tzinfo=UTC),
        Decimal("296.15"),
        Decimal("296.2"),
        Decimal("50"),
        Decimal("49.8"),
        Decimal("2"),
        LoadingRateUnit.MILLIMETER_PER_MINUTE,
        "rolling",
        "air",
        None,
    )
    assert value.loading_rate_unit is LoadingRateUnit.MILLIMETER_PER_MINUTE

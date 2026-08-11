from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from uuid import UUID

import pytest
from cmp.modules.catalog.application.records import CatalogRecordService
from cmp.modules.catalog.domain.configurable import AttributeDataType
from cmp.modules.catalog.domain.records import CatalogRecordContent, CatalogRecordValue

TABLE = UUID("c6000000-0000-4000-8000-000000000001")
TABLE_REVISION = UUID("c6000000-0000-4000-8000-000000000002")
NUMBER_ATTRIBUTE = UUID("c6000000-0000-4000-8000-000000000003")
NUMBER_REVISION = UUID("c6000000-0000-4000-8000-000000000004")
CURVE_ATTRIBUTE = UUID("c6000000-0000-4000-8000-000000000005")
CURVE_REVISION = UUID("c6000000-0000-4000-8000-000000000006")
CURVE_ARTIFACT = UUID("c6000000-0000-4000-8000-000000000007")


def _legacy_number() -> CatalogRecordValue:
    return CatalogRecordValue(
        NUMBER_ATTRIBUTE,
        NUMBER_REVISION,
        AttributeDataType.NUMBER,
        original_value=Decimal("560"),
        original_unit_string="MPa",
        normalized_value=Decimal("560000000"),
        normalized_unit="Pa",
        quantity_semantics="stress.yield",
    )


def _content(*values: CatalogRecordValue) -> CatalogRecordContent:
    return CatalogRecordContent(
        TABLE,
        TABLE_REVISION,
        "Historical material",
        values=values,
    )


def test_unchanged_number_outside_closed_registry_survives_curve_only_revision() -> None:
    legacy = _legacy_number()
    previous = _content(legacy)
    curve = CatalogRecordValue(
        CURVE_ATTRIBUTE,
        CURVE_REVISION,
        AttributeDataType.CURVE,
        artifact_id=CURVE_ARTIFACT,
        artifact_sha256="a" * 64,
    )

    normalized = CatalogRecordService._normalize_record_content(
        _content(legacy, curve), previous=previous
    )

    assert normalized.values == (legacy, curve)


def test_changed_number_outside_closed_registry_is_not_silently_accepted() -> None:
    legacy = _legacy_number()

    with pytest.raises(ValueError, match="알 수 없는 단위"):
        CatalogRecordService._normalize_record_content(
            _content(replace(legacy, original_value=Decimal("570"))),
            previous=_content(legacy),
        )

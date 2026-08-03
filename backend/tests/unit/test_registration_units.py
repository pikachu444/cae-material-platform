from decimal import Decimal

import pytest
from cmp.modules.catalog.domain.registration_units import normalize_registration_value


def test_registration_unit_mapping_returns_normalized_value_and_evidence() -> None:
    value, evidence = normalize_registration_value(Decimal("210.5"), "GPa", "Pa")

    assert value == Decimal("210500000000.0")
    assert evidence == {
        "library_version": "cmp-registration-units/1",
        "source_unit": "GPa",
        "target_unit": "Pa",
        "factor": "1000000000",
        "offset": "0",
        "rule": "linear_scale",
    }


def test_registration_unit_mapping_rejects_unknown_unit_without_default() -> None:
    with pytest.raises(ValueError, match="알 수 없는 단위"):
        normalize_registration_value(Decimal("1"), "psi", "Pa")

from decimal import Decimal

import pytest
from cmp.modules.catalog.domain.registration_units import (
    normalize_registration_value,
    registration_unit_evidence,
)


@pytest.mark.parametrize(
    ("source", "target", "factor", "semantics"),
    (
        ("Pa", "kPa", "0.001", "stress.engineering"),
        ("Pa", "MPa", "0.000001", "stress.engineering"),
        ("Pa", "GPa", "0.000000001", "stress.engineering"),
        ("kPa", "Pa", "1000", "stress.engineering"),
        ("MPa", "Pa", "1000000", "stress.engineering"),
        ("GPa", "Pa", "1000000000", "modulus.elastic.young"),
        ("MPa", "GPa", "0.001", "modulus.elastic.young"),
        ("GPa", "MPa", "1000", "modulus.elastic.young"),
        ("mm", "m", "0.001", "length"),
        ("cm", "m", "0.01", "length"),
        ("m", "mm", "1000", "length"),
        ("%", "1", "0.01", "strain.engineering"),
        ("1", "%", "100", "strain.engineering"),
    ),
)
def test_all_thirteen_registration_mappings_keep_exact_evidence_and_values(
    source: str, target: str, factor: str, semantics: str
) -> None:
    value, evidence = normalize_registration_value(
        Decimal("2"), source, target, quantity_semantics=semantics
    )

    assert value == Decimal("2") * Decimal(factor)
    assert evidence == registration_unit_evidence(source, target)
    assert evidence["library_version"] == "cmp-registration-units/1"
    assert evidence["factor"] == factor
    assert evidence["offset"] == "0"
    assert evidence["rule"] == "linear_scale"


def test_registration_unit_mapping_returns_normalized_value_and_evidence() -> None:
    value, evidence = normalize_registration_value(
        Decimal("210.5"),
        "GPa",
        "Pa",
        quantity_semantics="modulus.elastic.young",
    )

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
        normalize_registration_value(
            Decimal("1"),
            "psi",
            "Pa",
            quantity_semantics="modulus.elastic.young",
        )

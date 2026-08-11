"""Bounded, evidence-bearing unit mappings for configurable Record registration."""

from __future__ import annotations

import json
from decimal import Decimal
from importlib.resources import files
from typing import TypedDict

from cmp.modules.units.domain.system import (
    QuantityReference,
    UnitError,
    convert_value,
    dimension_for_quantity_semantics,
)


class UnitMappingEvidence(TypedDict):
    library_version: str
    source_unit: str
    target_unit: str
    factor: str
    offset: str
    rule: str


def _load() -> tuple[str, dict[tuple[str, str], UnitMappingEvidence]]:
    payload = json.loads(
        files(__package__).joinpath("registration-unit-mappings.json").read_text("utf-8")
    )
    version = str(payload["version"])
    mappings: dict[tuple[str, str], UnitMappingEvidence] = {}
    for item in payload["mappings"]:
        evidence: UnitMappingEvidence = {
            "library_version": version,
            "source_unit": str(item["source"]),
            "target_unit": str(item["target"]),
            "factor": str(item["factor"]),
            "offset": str(item["offset"]),
            "rule": str(item["rule"]),
        }
        mappings[(evidence["source_unit"], evidence["target_unit"])] = evidence
    return version, mappings


UNIT_MAPPING_LIBRARY_VERSION, _UNIT_MAPPINGS = _load()


def registration_unit_evidence(source_unit: str, target_unit: str) -> UnitMappingEvidence | None:
    if source_unit == target_unit:
        return {
            "library_version": UNIT_MAPPING_LIBRARY_VERSION,
            "source_unit": source_unit,
            "target_unit": target_unit,
            "factor": "1",
            "offset": "0",
            "rule": "identity",
        }
    return _UNIT_MAPPINGS.get((source_unit, target_unit))


def normalize_registration_value(
    value: Decimal,
    source_unit: str,
    target_unit: str,
    *,
    quantity_semantics: str,
) -> tuple[Decimal, UnitMappingEvidence]:
    evidence = registration_unit_evidence(source_unit, target_unit)
    if evidence is None:
        raise ValueError("알 수 없는 단위입니다. 표준 단위를 선택하세요.")
    try:
        dimension = dimension_for_quantity_semantics(quantity_semantics)
        result = convert_value(
            value,
            original_unit_string=source_unit,
            source=QuantityReference(dimension, quantity_semantics, source_unit),
            target=QuantityReference(dimension, quantity_semantics, target_unit),
            location="catalog.record.number",
        )
    except UnitError as error:
        raise ValueError("알 수 없는 단위입니다. 표준 단위를 선택하세요.") from error
    if (
        result.scale != Decimal(evidence["factor"])
        or result.offset != Decimal(evidence["offset"])
    ):
        raise RuntimeError("registration mapping evidence differs from the common unit contract")
    return result.converted_value, evidence


__all__ = [
    "UNIT_MAPPING_LIBRARY_VERSION",
    "UnitMappingEvidence",
    "normalize_registration_value",
    "registration_unit_evidence",
]

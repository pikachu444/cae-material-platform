"""Typed, non-production reference tensile testing records.

The first Dataset slice deliberately supports one openly described uniaxial tensile CSV shape.
It does not claim a particular test standard, instrument format, or production acceptance policy.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

REFERENCE_TENSILE_METHOD_CODE = "reference_uniaxial_tensile"
REFERENCE_TENSILE_METHOD_DISPLAY_NAME = "Reference uniaxial tensile CSV"
REFERENCE_PLANAR_TENSION_METHOD_CODE = "reference_planar_tension"
REFERENCE_PLANAR_TENSION_METHOD_DISPLAY_NAME = "Reference planar tension CSV"
REFERENCE_BIAXIAL_TENSION_METHOD_CODE = "reference_biaxial_tension"
REFERENCE_BIAXIAL_TENSION_METHOD_DISPLAY_NAME = "Reference biaxial tension CSV"
REFERENCE_SHEAR_RELAXATION_METHOD_CODE = "reference_shear_relaxation"
REFERENCE_SHEAR_RELAXATION_METHOD_DISPLAY_NAME = "Reference shear relaxation CSV"
REFERENCE_TENSILE_SCHEMA_VERSION = "1.0.0"


class ReferenceTensionMode(StrEnum):
    """Explicit physical loading modes supported by the bounded tension intake."""

    PLANAR_TENSION = "planar_tension"
    BIAXIAL_TENSION = "biaxial_tension"


REFERENCE_TENSION_METHODS = {
    REFERENCE_TENSILE_METHOD_CODE: REFERENCE_TENSILE_METHOD_DISPLAY_NAME,
    REFERENCE_PLANAR_TENSION_METHOD_CODE: REFERENCE_PLANAR_TENSION_METHOD_DISPLAY_NAME,
    REFERENCE_BIAXIAL_TENSION_METHOD_CODE: REFERENCE_BIAXIAL_TENSION_METHOD_DISPLAY_NAME,
}


def reference_tension_method(mode: ReferenceTensionMode) -> tuple[str, str]:
    if mode is ReferenceTensionMode.PLANAR_TENSION:
        return REFERENCE_PLANAR_TENSION_METHOD_CODE, REFERENCE_PLANAR_TENSION_METHOD_DISPLAY_NAME
    return REFERENCE_BIAXIAL_TENSION_METHOD_CODE, REFERENCE_BIAXIAL_TENSION_METHOD_DISPLAY_NAME


class TestingError(Exception):
    """Base error for the typed testing slice."""


class InvalidTestingData(TestingError, ValueError):
    """A testing record does not satisfy the explicit reference schema."""


class TestingNotFound(TestingError):
    """A requested testing record is absent or not visible in the tenant."""


class TestingConflict(TestingError):
    """Immutable testing state or provenance context conflicts."""


def _uuid(name: str, value: UUID) -> None:
    if value.int == 0:
        raise InvalidTestingData(f"{name} must be non-zero")


def _text(name: str, value: str, maximum: int) -> None:
    if not value or value != value.strip() or len(value) > maximum or "\x00" in value:
        raise InvalidTestingData(f"{name} must be trimmed and contain 1..{maximum} characters")


def _optional_text(name: str, value: str | None, maximum: int) -> None:
    if value is None:
        return
    _text(name, value, maximum)


def _finite_positive(name: str, value: float | None) -> None:
    if value is not None and (not math.isfinite(value) or value <= 0.0):
        raise InvalidTestingData(f"{name} must be finite and positive when supplied")


def _aware(name: str, value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise InvalidTestingData(f"{name} must be timezone-aware")


@dataclass(frozen=True, slots=True)
class SpecimenContent:
    """One physical coupon tied to concrete Material and Material State revisions."""

    material_id: UUID
    material_revision_id: UUID
    material_state_id: UUID
    material_state_revision_id: UUID
    specimen_code: str
    orientation: str | None
    preparation_note: str | None

    def __post_init__(self) -> None:
        for name, value in (
            ("material_id", self.material_id),
            ("material_revision_id", self.material_revision_id),
            ("material_state_id", self.material_state_id),
            ("material_state_revision_id", self.material_state_revision_id),
        ):
            _uuid(name, value)
        _text("specimen_code", self.specimen_code, 100)
        _optional_text("orientation", self.orientation, 100)
        _optional_text("preparation_note", self.preparation_note, 2000)


@dataclass(frozen=True, slots=True)
class TestMethodContent:
    """The explicit, reference-only method definition used by this MVP."""

    method_code: str
    display_name: str
    reference_only: bool = True

    def __post_init__(self) -> None:
        expected = {
            **REFERENCE_TENSION_METHODS,
            REFERENCE_SHEAR_RELAXATION_METHOD_CODE: (
                REFERENCE_SHEAR_RELAXATION_METHOD_DISPLAY_NAME
            ),
        }
        if expected.get(self.method_code) != self.display_name:
            raise InvalidTestingData("reference Test Method code and display name are not declared")
        if not self.reference_only:
            raise InvalidTestingData("reference Test Method must remain non-production")


@dataclass(frozen=True, slots=True)
class TestRunContent:
    """One actual reference tensile run, pinned to concrete specimen/method revisions."""

    specimen_id: UUID
    specimen_revision_id: UUID
    test_method_id: UUID
    test_method_revision_id: UUID
    run_label: str
    performed_at: datetime
    test_temperature_k: float | None
    crosshead_speed_mm_per_min: float | None
    reference_only: bool = True

    def __post_init__(self) -> None:
        for name, value in (
            ("specimen_id", self.specimen_id),
            ("specimen_revision_id", self.specimen_revision_id),
            ("test_method_id", self.test_method_id),
            ("test_method_revision_id", self.test_method_revision_id),
        ):
            _uuid(name, value)
        _text("run_label", self.run_label, 160)
        _aware("performed_at", self.performed_at)
        _finite_positive("test_temperature_k", self.test_temperature_k)
        _finite_positive("crosshead_speed_mm_per_min", self.crosshead_speed_mm_per_min)
        if not self.reference_only:
            raise InvalidTestingData("reference tensile Test Run must remain non-production")


def specimen_canonical(value: SpecimenContent) -> dict[str, object]:
    return {
        "material_id": str(value.material_id),
        "material_revision_id": str(value.material_revision_id),
        "material_state_id": str(value.material_state_id),
        "material_state_revision_id": str(value.material_state_revision_id),
        "specimen_code": value.specimen_code,
        "orientation": value.orientation,
        "preparation_note": value.preparation_note,
    }


def test_method_canonical(value: TestMethodContent) -> dict[str, object]:
    return {
        "method_code": value.method_code,
        "display_name": value.display_name,
        "reference_only": value.reference_only,
    }


def test_run_canonical(value: TestRunContent) -> dict[str, object]:
    return {
        "specimen_id": str(value.specimen_id),
        "specimen_revision_id": str(value.specimen_revision_id),
        "test_method_id": str(value.test_method_id),
        "test_method_revision_id": str(value.test_method_revision_id),
        "run_label": value.run_label,
        "performed_at": value.performed_at.isoformat(),
        "test_temperature_k": value.test_temperature_k,
        "crosshead_speed_mm_per_min": value.crosshead_speed_mm_per_min,
        "reference_only": value.reference_only,
    }

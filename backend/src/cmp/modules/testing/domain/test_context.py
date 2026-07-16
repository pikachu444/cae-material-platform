"""Governed Test Campaign, Instrument, calibration, condition, and Run context."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from cmp.modules.testing.domain.reference_tensile import InvalidTestingData


class StandardConformance(StrEnum):
    CONFORMANT = "conformant"
    DEVIATION_APPROVED = "deviation_approved"
    NOT_CLAIMED = "not_claimed"


class CalibrationResult(StrEnum):
    PASSED = "passed"
    LIMITED = "limited"
    FAILED = "failed"


class LoadingRateUnit(StrEnum):
    MILLIMETER_PER_MINUTE = "mm/min"
    PER_SECOND = "1/s"
    NEWTON_PER_SECOND = "N/s"
    PASCAL_PER_SECOND = "Pa/s"


def _uuid(name: str, value: UUID) -> None:
    if value.int == 0:
        raise InvalidTestingData(f"{name} must be non-zero")


def _text(name: str, value: str, maximum: int) -> None:
    if not value or value != value.strip() or len(value) > maximum or "\x00" in value:
        raise InvalidTestingData(f"{name} must be trimmed and contain 1..{maximum} characters")


def _optional_text(name: str, value: str | None, maximum: int) -> None:
    if value is not None:
        _text(name, value, maximum)


def _aware(name: str, value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise InvalidTestingData(f"{name} must be timezone-aware")


def _decimal_range(
    name: str,
    value: Decimal | None,
    *,
    minimum: Decimal,
    maximum: Decimal | None = None,
) -> None:
    if value is None:
        return
    if not value.is_finite() or value < minimum or (maximum is not None and value > maximum):
        upper = f" and <= {maximum}" if maximum is not None else ""
        raise InvalidTestingData(f"{name} must be finite, >= {minimum}{upper}")


def _decimal_text(value: Decimal | None) -> str | None:
    if value is None:
        return None
    normalized = value.normalize()
    return "0" if normalized == 0 else format(normalized, "f")


@dataclass(frozen=True, slots=True)
class TestCampaignContent:
    test_method_id: UUID
    test_method_revision_id: UUID
    campaign_code: str
    name: str
    objective: str
    population_description: str
    planned_specimen_count: int
    standard_conformance: StandardConformance
    standard_designation: str | None
    standard_edition: str | None
    standard_deviation_reason: str | None
    reference_only: bool = True

    def __post_init__(self) -> None:
        _uuid("test_method_id", self.test_method_id)
        _uuid("test_method_revision_id", self.test_method_revision_id)
        _text("campaign_code", self.campaign_code, 100)
        _text("name", self.name, 200)
        _text("objective", self.objective, 2000)
        _text("population_description", self.population_description, 2000)
        if not 1 <= self.planned_specimen_count <= 1_000_000:
            raise InvalidTestingData("planned_specimen_count must be within 1..1000000")
        if self.standard_conformance is StandardConformance.NOT_CLAIMED:
            if any(
                value is not None
                for value in (
                    self.standard_designation,
                    self.standard_edition,
                    self.standard_deviation_reason,
                )
            ):
                raise InvalidTestingData("not_claimed cannot include standard or deviation fields")
        else:
            _text("standard_designation", self.standard_designation or "", 200)
            _text("standard_edition", self.standard_edition or "", 100)
            if self.standard_conformance is StandardConformance.CONFORMANT:
                if self.standard_deviation_reason is not None:
                    raise InvalidTestingData("conformant Campaign cannot declare a deviation")
            else:
                _text(
                    "standard_deviation_reason",
                    self.standard_deviation_reason or "",
                    2000,
                )
        if not self.reference_only:
            raise InvalidTestingData("current Campaign capability must remain reference-only")


@dataclass(frozen=True, slots=True)
class InstrumentContent:
    instrument_code: str
    name: str
    serial_number: str
    manufacturer: str | None
    model: str | None
    location: str | None
    description: str | None

    def __post_init__(self) -> None:
        _text("instrument_code", self.instrument_code, 100)
        _text("name", self.name, 200)
        _text("serial_number", self.serial_number, 200)
        _optional_text("manufacturer", self.manufacturer, 200)
        _optional_text("model", self.model, 200)
        _optional_text("location", self.location, 255)
        _optional_text("description", self.description, 2000)


@dataclass(frozen=True, slots=True)
class InstrumentCalibrationContent:
    instrument_id: UUID
    instrument_revision_id: UUID
    calibration_code: str
    certificate_reference: str
    provider: str
    calibrated_at: datetime
    valid_from: datetime
    valid_until: datetime
    result: CalibrationResult
    limitation_note: str | None

    def __post_init__(self) -> None:
        _uuid("instrument_id", self.instrument_id)
        _uuid("instrument_revision_id", self.instrument_revision_id)
        _text("calibration_code", self.calibration_code, 100)
        _text("certificate_reference", self.certificate_reference, 255)
        _text("provider", self.provider, 200)
        for name, value in (
            ("calibrated_at", self.calibrated_at),
            ("valid_from", self.valid_from),
            ("valid_until", self.valid_until),
        ):
            _aware(name, value)
        if self.valid_from < self.calibrated_at:
            raise InvalidTestingData("valid_from cannot precede calibrated_at")
        if self.valid_until <= self.valid_from:
            raise InvalidTestingData("valid_until must be later than valid_from")
        if self.result is CalibrationResult.LIMITED:
            _text("limitation_note", self.limitation_note or "", 2000)
        elif self.limitation_note is not None:
            raise InvalidTestingData("limitation_note is allowed only for limited calibration")

    @property
    def usable(self) -> bool:
        return self.result in (CalibrationResult.PASSED, CalibrationResult.LIMITED)

    def covers(self, occurred_at: datetime) -> bool:
        _aware("occurred_at", occurred_at)
        return self.usable and self.valid_from <= occurred_at < self.valid_until

    def overlaps(self, other: InstrumentCalibrationContent) -> bool:
        return (
            self.instrument_id == other.instrument_id
            and self.usable
            and other.usable
            and self.valid_from < other.valid_until
            and other.valid_from < self.valid_until
        )


@dataclass(frozen=True, slots=True)
class TestConditionContent:
    test_method_id: UUID
    test_method_revision_id: UUID
    captured_at: datetime
    temperature_setpoint_k: Decimal | None
    temperature_observed_k: Decimal | None
    humidity_setpoint_pct: Decimal | None
    humidity_observed_pct: Decimal | None
    loading_rate_value: Decimal | None
    loading_rate_unit: LoadingRateUnit | None
    orientation: str | None
    medium: str | None
    note: str | None

    def __post_init__(self) -> None:
        _uuid("test_method_id", self.test_method_id)
        _uuid("test_method_revision_id", self.test_method_revision_id)
        _aware("captured_at", self.captured_at)
        _decimal_range("temperature_setpoint_k", self.temperature_setpoint_k, minimum=Decimal("0"))
        _decimal_range("temperature_observed_k", self.temperature_observed_k, minimum=Decimal("0"))
        _decimal_range(
            "humidity_setpoint_pct",
            self.humidity_setpoint_pct,
            minimum=Decimal("0"),
            maximum=Decimal("100"),
        )
        _decimal_range(
            "humidity_observed_pct",
            self.humidity_observed_pct,
            minimum=Decimal("0"),
            maximum=Decimal("100"),
        )
        _decimal_range("loading_rate_value", self.loading_rate_value, minimum=Decimal("0"))
        if (self.loading_rate_value is None) != (self.loading_rate_unit is None):
            raise InvalidTestingData("loading rate value and unit must be supplied together")
        _optional_text("orientation", self.orientation, 100)
        _optional_text("medium", self.medium, 200)
        _optional_text("note", self.note, 2000)
        if all(
            value is None
            for value in (
                self.temperature_setpoint_k,
                self.temperature_observed_k,
                self.humidity_setpoint_pct,
                self.humidity_observed_pct,
                self.loading_rate_value,
                self.orientation,
                self.medium,
                self.note,
            )
        ):
            raise InvalidTestingData("Condition Snapshot cannot be empty")


@dataclass(frozen=True, slots=True)
class TestRunContextContent:
    test_run_id: UUID
    test_run_revision_id: UUID
    test_campaign_id: UUID
    test_campaign_revision_id: UUID
    test_condition_id: UUID
    test_condition_revision_id: UUID
    instrument_id: UUID
    instrument_revision_id: UUID
    calibration_id: UUID
    calibration_revision_id: UUID
    note: str | None

    def __post_init__(self) -> None:
        for name, value in (
            ("test_run_id", self.test_run_id),
            ("test_run_revision_id", self.test_run_revision_id),
            ("test_campaign_id", self.test_campaign_id),
            ("test_campaign_revision_id", self.test_campaign_revision_id),
            ("test_condition_id", self.test_condition_id),
            ("test_condition_revision_id", self.test_condition_revision_id),
            ("instrument_id", self.instrument_id),
            ("instrument_revision_id", self.instrument_revision_id),
            ("calibration_id", self.calibration_id),
            ("calibration_revision_id", self.calibration_revision_id),
        ):
            _uuid(name, value)
        _optional_text("note", self.note, 2000)


def campaign_canonical(value: TestCampaignContent) -> dict[str, object]:
    return {
        "test_method_id": str(value.test_method_id),
        "test_method_revision_id": str(value.test_method_revision_id),
        "campaign_code": value.campaign_code,
        "name": value.name,
        "objective": value.objective,
        "population_description": value.population_description,
        "planned_specimen_count": value.planned_specimen_count,
        "standard_conformance": value.standard_conformance.value,
        "standard_designation": value.standard_designation,
        "standard_edition": value.standard_edition,
        "standard_deviation_reason": value.standard_deviation_reason,
        "reference_only": value.reference_only,
    }


def instrument_canonical(value: InstrumentContent) -> dict[str, object]:
    return {
        "instrument_code": value.instrument_code,
        "name": value.name,
        "serial_number": value.serial_number,
        "manufacturer": value.manufacturer,
        "model": value.model,
        "location": value.location,
        "description": value.description,
    }


def calibration_canonical(value: InstrumentCalibrationContent) -> dict[str, object]:
    return {
        "instrument_id": str(value.instrument_id),
        "instrument_revision_id": str(value.instrument_revision_id),
        "calibration_code": value.calibration_code,
        "certificate_reference": value.certificate_reference,
        "provider": value.provider,
        "calibrated_at": value.calibrated_at.isoformat(),
        "valid_from": value.valid_from.isoformat(),
        "valid_until": value.valid_until.isoformat(),
        "result": value.result.value,
        "limitation_note": value.limitation_note,
    }


def condition_canonical(value: TestConditionContent) -> dict[str, object]:
    return {
        "test_method_id": str(value.test_method_id),
        "test_method_revision_id": str(value.test_method_revision_id),
        "captured_at": value.captured_at.isoformat(),
        "temperature_setpoint_k": _decimal_text(value.temperature_setpoint_k),
        "temperature_observed_k": _decimal_text(value.temperature_observed_k),
        "humidity_setpoint_pct": _decimal_text(value.humidity_setpoint_pct),
        "humidity_observed_pct": _decimal_text(value.humidity_observed_pct),
        "loading_rate_value": _decimal_text(value.loading_rate_value),
        "loading_rate_unit": (
            value.loading_rate_unit.value if value.loading_rate_unit is not None else None
        ),
        "orientation": value.orientation,
        "medium": value.medium,
        "note": value.note,
    }


def run_context_canonical(value: TestRunContextContent) -> dict[str, object]:
    return {
        "test_run_id": str(value.test_run_id),
        "test_run_revision_id": str(value.test_run_revision_id),
        "test_campaign_id": str(value.test_campaign_id),
        "test_campaign_revision_id": str(value.test_campaign_revision_id),
        "test_condition_id": str(value.test_condition_id),
        "test_condition_revision_id": str(value.test_condition_revision_id),
        "instrument_id": str(value.instrument_id),
        "instrument_revision_id": str(value.instrument_revision_id),
        "calibration_id": str(value.calibration_id),
        "calibration_revision_id": str(value.calibration_revision_id),
        "note": value.note,
    }

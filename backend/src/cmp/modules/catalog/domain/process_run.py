"""Immutable Process Run revisions and their typed Lot input/output flows."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_EVEN, Decimal, InvalidOperation, localcontext
from enum import StrEnum
from uuid import UUID

from cmp.modules.catalog.domain.model import InvalidCatalogCommand
from cmp.modules.units.domain.system import (
    DimensionId,
    QuantityReference,
    UnitError,
    convert_value,
)


class BalanceBasis(StrEnum):
    MASS = "mass"
    VOLUME = "volume"
    COUNT = "count"
    NOT_ASSESSED = "not_assessed"


_UNIT_NORMALIZATION: dict[str, tuple[BalanceBasis, str, Decimal]] = {
    "m3": (BalanceBasis.VOLUME, "m3", Decimal("1")),
    "L": (BalanceBasis.VOLUME, "m3", Decimal("0.001")),
    "mL": (BalanceBasis.VOLUME, "m3", Decimal("0.000001")),
    "cm3": (BalanceBasis.VOLUME, "m3", Decimal("0.000001")),
    "1": (BalanceBasis.COUNT, "1", Decimal("1")),
}

_STORAGE_QUANTUM = Decimal("0.000000000000000000000001")


def _decimal_text(value: Decimal) -> str:
    normalized = value.normalize()
    return "0" if normalized == 0 else format(normalized, "f")


def _storable_decimal(name: str, value: Decimal) -> None:
    if not value.is_finite():
        raise InvalidCatalogCommand(f"{name} must be finite")
    _, digits, decimal_exponent = value.as_tuple()
    if not isinstance(decimal_exponent, int):
        raise InvalidCatalogCommand(f"{name} must be finite")
    exponent = decimal_exponent
    fractional_digits = max(-exponent, 0)
    integer_digits = max(len(digits) + exponent, 0)
    if fractional_digits > 24 or integer_digits > 30:
        raise InvalidCatalogCommand(f"{name} supports at most 30 integer and 24 fractional digits")


def _nonzero(name: str, value: UUID) -> None:
    if value.int == 0:
        raise InvalidCatalogCommand(f"{name} must be non-zero")


def _text(name: str, value: str, maximum: int) -> None:
    if not value or value != value.strip() or len(value) > maximum or "\x00" in value:
        raise InvalidCatalogCommand(f"{name} must be trimmed and contain 1..{maximum} characters")


def _optional_text(name: str, value: str | None, maximum: int) -> None:
    if value is not None:
        _text(name, value, maximum)


def _unit_normalization(original_unit: str) -> tuple[BalanceBasis, str, Decimal]:
    if original_unit in {"kg", "g", "mg"}:
        try:
            result = convert_value(
                "1",
                original_unit_string=original_unit,
                source=QuantityReference(DimensionId.MASS, "mass", original_unit),
                target=QuantityReference(DimensionId.MASS, "mass", "kg"),
                location="process_run.lot_flow.mass",
            )
        except UnitError as error:
            raise InvalidCatalogCommand(error.message) from error
        return BalanceBasis.MASS, "kg", result.scale
    try:
        return _UNIT_NORMALIZATION[original_unit]
    except KeyError as error:
        raise InvalidCatalogCommand(
            "original_unit must be one of kg, g, mg, m3, L, mL, cm3, or 1"
        ) from error


@dataclass(frozen=True, slots=True)
class LotFlow:
    """One exact Lot revision and an explicit original-to-SI quantity conversion."""

    material_lot_id: UUID
    material_lot_revision_id: UUID
    original_quantity: Decimal
    original_unit: str
    quantity_basis: BalanceBasis
    normalized_quantity: Decimal
    normalized_unit: str
    normalization_factor: Decimal

    @classmethod
    def from_original(
        cls,
        *,
        material_lot_id: UUID,
        material_lot_revision_id: UUID,
        original_quantity: Decimal,
        original_unit: str,
    ) -> LotFlow:
        basis, normalized_unit, factor = _unit_normalization(original_unit)
        return cls(
            material_lot_id=material_lot_id,
            material_lot_revision_id=material_lot_revision_id,
            original_quantity=original_quantity,
            original_unit=original_unit,
            quantity_basis=basis,
            normalized_quantity=original_quantity * factor,
            normalized_unit=normalized_unit,
            normalization_factor=factor,
        )

    def __post_init__(self) -> None:
        _nonzero("material_lot_id", self.material_lot_id)
        _nonzero("material_lot_revision_id", self.material_lot_revision_id)
        _text("original_unit", self.original_unit, 16)
        _text("normalized_unit", self.normalized_unit, 16)
        _storable_decimal("original_quantity", self.original_quantity)
        _storable_decimal("normalized_quantity", self.normalized_quantity)
        _storable_decimal("normalization_factor", self.normalization_factor)
        if self.original_quantity <= 0 or self.normalized_quantity <= 0:
            raise InvalidCatalogCommand("Lot flow quantities must be greater than zero")
        if self.normalization_factor <= 0:
            raise InvalidCatalogCommand("normalization_factor must be greater than zero")
        expected = _unit_normalization(self.original_unit)
        if expected != (
            self.quantity_basis,
            self.normalized_unit,
            self.normalization_factor,
        ):
            raise InvalidCatalogCommand("Lot flow unit normalization is not the governed mapping")
        if self.normalized_quantity != self.original_quantity * self.normalization_factor:
            raise InvalidCatalogCommand("Lot flow normalized quantity is inconsistent")


@dataclass(frozen=True, slots=True)
class ProcessBalance:
    input_total: Decimal
    output_total: Decimal
    relative_difference: Decimal
    within_tolerance: bool


@dataclass(frozen=True, slots=True)
class ProcessRunContent:
    process_definition_id: UUID
    process_definition_revision_id: UUID
    material_state_id: UUID
    material_state_revision_id: UUID
    run_code: str
    started_at: datetime
    ended_at: datetime | None
    operator_name: str | None
    equipment_reference: str | None
    balance_basis: BalanceBasis
    balance_tolerance_fraction: Decimal | None
    balance_not_assessed_reason: str | None
    inputs: tuple[LotFlow, ...]
    outputs: tuple[LotFlow, ...]
    note: str | None = None

    def __post_init__(self) -> None:
        _nonzero("process_definition_id", self.process_definition_id)
        _nonzero("process_definition_revision_id", self.process_definition_revision_id)
        _nonzero("material_state_id", self.material_state_id)
        _nonzero("material_state_revision_id", self.material_state_revision_id)
        _text("run_code", self.run_code, 100)
        _optional_text("operator_name", self.operator_name, 200)
        _optional_text("equipment_reference", self.equipment_reference, 255)
        _optional_text("note", self.note, 2000)
        if self.started_at.tzinfo is None:
            raise InvalidCatalogCommand("started_at must include a timezone")
        if self.ended_at is not None:
            if self.ended_at.tzinfo is None:
                raise InvalidCatalogCommand("ended_at must include a timezone")
            if self.ended_at < self.started_at:
                raise InvalidCatalogCommand("ended_at cannot be earlier than started_at")
        if not self.inputs or not self.outputs:
            raise InvalidCatalogCommand("Process Run requires at least one input and output Lot")
        input_refs = tuple(
            (item.material_lot_id, item.material_lot_revision_id) for item in self.inputs
        )
        output_refs = tuple(
            (item.material_lot_id, item.material_lot_revision_id) for item in self.outputs
        )
        if len(set(input_refs)) != len(input_refs) or len(set(output_refs)) != len(output_refs):
            raise InvalidCatalogCommand("a Lot revision may appear only once in each flow role")
        if set(input_refs).intersection(output_refs):
            raise InvalidCatalogCommand("the same Lot revision cannot be both input and output")
        if self.balance_basis is BalanceBasis.NOT_ASSESSED:
            if self.balance_tolerance_fraction is not None:
                raise InvalidCatalogCommand("not_assessed balance cannot set a tolerance")
            _text(
                "balance_not_assessed_reason",
                self.balance_not_assessed_reason or "",
                2000,
            )
        else:
            if self.balance_not_assessed_reason is not None:
                raise InvalidCatalogCommand("assessed balance cannot set a not-assessed reason")
            if self.balance_tolerance_fraction is None:
                raise InvalidCatalogCommand("assessed balance requires a tolerance")
            _storable_decimal("balance_tolerance_fraction", self.balance_tolerance_fraction)
            if not Decimal("0") <= self.balance_tolerance_fraction <= Decimal("1"):
                raise InvalidCatalogCommand("balance tolerance must be within [0, 1]")
            if any(
                item.quantity_basis is not self.balance_basis
                for item in (*self.inputs, *self.outputs)
            ):
                raise InvalidCatalogCommand("assessed Lot flow dimensions must match balance_basis")
            balance = self.balance
            assert balance is not None
            if not balance.within_tolerance:
                raise InvalidCatalogCommand(
                    "Process Run output is outside the declared balance tolerance"
                )

    @property
    def balance(self) -> ProcessBalance | None:
        if self.balance_basis is BalanceBasis.NOT_ASSESSED:
            return None
        input_total = sum((item.normalized_quantity for item in self.inputs), Decimal("0"))
        output_total = sum((item.normalized_quantity for item in self.outputs), Decimal("0"))
        with localcontext() as context:
            context.prec = 80
            exact_relative = abs(input_total - output_total) / input_total
            try:
                relative = exact_relative.quantize(
                    _STORAGE_QUANTUM,
                    rounding=ROUND_HALF_EVEN,
                )
            except InvalidOperation as error:
                raise InvalidCatalogCommand(
                    "Process Run balance exceeds supported decimal precision"
                ) from error
        if relative == 0:
            relative = Decimal("0")
        assert self.balance_tolerance_fraction is not None
        return ProcessBalance(
            input_total=input_total,
            output_total=output_total,
            relative_difference=relative,
            within_tolerance=exact_relative <= self.balance_tolerance_fraction,
        )


def lot_flow_canonical(value: LotFlow) -> dict[str, str]:
    return {
        "material_lot_id": str(value.material_lot_id),
        "material_lot_revision_id": str(value.material_lot_revision_id),
        "original_quantity": _decimal_text(value.original_quantity),
        "original_unit": value.original_unit,
        "quantity_basis": value.quantity_basis.value,
        "normalized_quantity": _decimal_text(value.normalized_quantity),
        "normalized_unit": value.normalized_unit,
        "normalization_factor": _decimal_text(value.normalization_factor),
    }


def process_run_canonical(value: ProcessRunContent) -> dict[str, object]:
    balance = value.balance
    return {
        "process_definition_id": str(value.process_definition_id),
        "process_definition_revision_id": str(value.process_definition_revision_id),
        "material_state_id": str(value.material_state_id),
        "material_state_revision_id": str(value.material_state_revision_id),
        "run_code": value.run_code,
        "started_at": value.started_at.isoformat(),
        "ended_at": value.ended_at.isoformat() if value.ended_at is not None else None,
        "operator_name": value.operator_name,
        "equipment_reference": value.equipment_reference,
        "balance_basis": value.balance_basis.value,
        "balance_tolerance_fraction": (
            _decimal_text(value.balance_tolerance_fraction)
            if value.balance_tolerance_fraction is not None
            else None
        ),
        "balance_not_assessed_reason": value.balance_not_assessed_reason,
        "balance": (
            {
                "input_total": _decimal_text(balance.input_total),
                "output_total": _decimal_text(balance.output_total),
                "relative_difference": _decimal_text(balance.relative_difference),
                "within_tolerance": balance.within_tolerance,
            }
            if balance is not None
            else None
        ),
        "inputs": [lot_flow_canonical(item) for item in value.inputs],
        "outputs": [lot_flow_canonical(item) for item in value.outputs],
        "note": value.note,
    }

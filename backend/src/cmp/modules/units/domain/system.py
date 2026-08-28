"""Bounded common CAE dimensions, units, and explicit conversion rules.

This is intentionally not a general-purpose unit library.  Every supported identifier is
part of the issue-205 production contract and every conversion carries an explicit dimension
and quantity semantic.  Adapters may use the closed compatibility semantic table, but the
public conversion boundary never infers either value from a unit string.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import (
    Context,
    Decimal,
    DecimalException,
    InvalidOperation,
    Overflow,
    localcontext,
)
from enum import StrEnum
from types import MappingProxyType
from typing import Final


class DimensionId(StrEnum):
    FORCE_PER_AREA = "force_per_area"
    LENGTH = "length"
    SPEED = "speed"
    TIME = "time"
    FORCE = "force"
    MASS = "mass"
    MASS_PER_VOLUME = "mass_per_volume"
    TEMPERATURE = "temperature"
    STRAIN = "strain"


class ConversionKind(StrEnum):
    MULTIPLICATIVE = "multiplicative"
    AFFINE_ABSOLUTE = "affine_absolute"


class UnitError(ValueError):
    """Structured common-unit failure suitable for the public error contract."""

    def __init__(
        self,
        *,
        code: str,
        message: str,
        location: str,
        source_dimension: DimensionId | None = None,
        target_dimension: DimensionId | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.location = location
        self.source_dimension = source_dimension
        self.target_dimension = target_dimension
        super().__init__(message)

    def detail(self) -> dict[str, str | None]:
        return {
            "code": self.code,
            "message": self.message,
            "location": self.location,
            "source_dimension": (
                None if self.source_dimension is None else self.source_dimension.value
            ),
            "target_dimension": (
                None if self.target_dimension is None else self.target_dimension.value
            ),
        }

    def contextual_message(self) -> str:
        """Keep the public location and dimension evidence across module boundaries."""

        detail = self.detail()
        return (
            f"{self.message}; code={self.code}; location={self.location}; "
            f"source_dimension={detail['source_dimension']}; "
            f"target_dimension={detail['target_dimension']}"
        )


@dataclass(frozen=True, slots=True)
class UnitDefinition:
    unit_id: str
    symbol: str
    dimension: DimensionId
    conversion_kind: ConversionKind
    scale_to_canonical: Decimal
    offset_to_canonical: Decimal = Decimal("0")
    backward_compatible_aliases: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class DimensionDefinition:
    dimension: DimensionId
    canonical_unit_id: str
    absolute_tolerance: Decimal
    relative_tolerance: Decimal
    units: tuple[UnitDefinition, ...]


@dataclass(frozen=True, slots=True)
class QuantityReference:
    dimension: DimensionId
    quantity_semantics: str
    unit_id: str

    def __post_init__(self) -> None:
        if not _SEMANTICS.fullmatch(self.quantity_semantics):
            raise UnitError(
                code="CMP-UNIT-0005",
                message="quantity_semantics must be a stable lower-case identifier",
                location="quantity_semantics",
                source_dimension=self.dimension,
            )


@dataclass(frozen=True, slots=True)
class ConversionResult:
    location: str
    original_value: Decimal
    original_unit_string: str
    source: QuantityReference
    target: QuantityReference
    converted_value: Decimal
    conversion_kind: ConversionKind
    scale: Decimal
    offset: Decimal
    absolute_tolerance: Decimal
    relative_tolerance: Decimal


_SEMANTICS = re.compile(r"^[a-z][a-z0-9_.-]{0,159}$")
NUMERIC_SIGNIFICANT_DIGITS: Final = 34
MINIMUM_ADJUSTED_EXPONENT: Final = -308
MAXIMUM_ADJUSTED_EXPONENT: Final = 308
_DECIMAL_CONTEXT = Context(
    prec=NUMERIC_SIGNIFICANT_DIGITS,
    Emin=MINIMUM_ADJUSTED_EXPONENT,
    Emax=MAXIMUM_ADJUSTED_EXPONENT,
)
_DECIMAL_CONTEXT.traps[InvalidOperation] = True
_DECIMAL_CONTEXT.traps[Overflow] = True


def _unit(
    unit_id: str,
    dimension: DimensionId,
    scale: str,
    *,
    offset: str = "0",
    affine: bool = False,
    aliases: tuple[str, ...] = (),
) -> UnitDefinition:
    return UnitDefinition(
        unit_id=unit_id,
        symbol=unit_id,
        dimension=dimension,
        conversion_kind=(
            ConversionKind.AFFINE_ABSOLUTE if affine else ConversionKind.MULTIPLICATIVE
        ),
        scale_to_canonical=Decimal(scale),
        offset_to_canonical=Decimal(offset),
        backward_compatible_aliases=aliases,
    )


DIMENSIONS: Final[tuple[DimensionDefinition, ...]] = (
    DimensionDefinition(
        DimensionId.FORCE_PER_AREA,
        "Pa",
        Decimal("1e-6"),
        Decimal("1e-12"),
        (
            _unit("Pa", DimensionId.FORCE_PER_AREA, "1"),
            _unit("kPa", DimensionId.FORCE_PER_AREA, "1e3"),
            _unit("MPa", DimensionId.FORCE_PER_AREA, "1e6"),
            _unit("GPa", DimensionId.FORCE_PER_AREA, "1e9"),
        ),
    ),
    DimensionDefinition(
        DimensionId.LENGTH,
        "m",
        Decimal("1e-12"),
        Decimal("1e-12"),
        (
            _unit("m", DimensionId.LENGTH, "1"),
            _unit("cm", DimensionId.LENGTH, "1e-2"),
            _unit("mm", DimensionId.LENGTH, "1e-3"),
            _unit("um", DimensionId.LENGTH, "1e-6", aliases=("µm", "μm")),
        ),
    ),
    DimensionDefinition(
        DimensionId.SPEED,
        "m/s",
        Decimal("1e-12"),
        Decimal("1e-12"),
        (
            _unit("m/s", DimensionId.SPEED, "1"),
            _unit("mm/s", DimensionId.SPEED, "1e-3"),
            _unit(
                "mm/min",
                DimensionId.SPEED,
                "1.666666666666666666666666666666667e-5",
            ),
        ),
    ),
    DimensionDefinition(
        DimensionId.TIME,
        "s",
        Decimal("1e-12"),
        Decimal("1e-12"),
        (
            _unit("s", DimensionId.TIME, "1"),
            _unit("ms", DimensionId.TIME, "1e-3"),
            _unit("min", DimensionId.TIME, "60"),
            _unit("h", DimensionId.TIME, "3600"),
        ),
    ),
    DimensionDefinition(
        DimensionId.FORCE,
        "N",
        Decimal("1e-9"),
        Decimal("1e-12"),
        (
            _unit("N", DimensionId.FORCE, "1"),
            _unit("kN", DimensionId.FORCE, "1e3"),
        ),
    ),
    DimensionDefinition(
        DimensionId.MASS,
        "kg",
        Decimal("1e-12"),
        Decimal("1e-12"),
        (
            _unit("kg", DimensionId.MASS, "1"),
            _unit("g", DimensionId.MASS, "1e-3"),
            _unit("mg", DimensionId.MASS, "1e-6"),
        ),
    ),
    DimensionDefinition(
        DimensionId.MASS_PER_VOLUME,
        "kg/m3",
        Decimal("1e-9"),
        Decimal("1e-12"),
        (
            _unit(
                "kg/m3",
                DimensionId.MASS_PER_VOLUME,
                "1",
                aliases=("kg/m^3",),
            ),
            _unit(
                "g/cm3",
                DimensionId.MASS_PER_VOLUME,
                "1e3",
                aliases=("g/cm^3",),
            ),
            _unit("tonne/mm3", DimensionId.MASS_PER_VOLUME, "1e12"),
        ),
    ),
    DimensionDefinition(
        DimensionId.TEMPERATURE,
        "K",
        Decimal("1e-12"),
        Decimal("1e-12"),
        (
            _unit("K", DimensionId.TEMPERATURE, "1", affine=True),
            _unit(
                "Cel",
                DimensionId.TEMPERATURE,
                "1",
                offset="273.15",
                affine=True,
                aliases=("degC", "°C"),
            ),
        ),
    ),
    DimensionDefinition(
        DimensionId.STRAIN,
        "1",
        Decimal("1e-12"),
        Decimal("1e-12"),
        (
            _unit("1", DimensionId.STRAIN, "1"),
            _unit("%", DimensionId.STRAIN, "1e-2"),
        ),
    ),
)

_DIMENSION_BY_ID: Final = MappingProxyType({item.dimension: item for item in DIMENSIONS})
_UNITS: Final = MappingProxyType(
    {unit.unit_id: unit for dimension in DIMENSIONS for unit in dimension.units}
)
_ALIASES: Final = MappingProxyType(
    {
        alias: unit.unit_id
        for dimension in DIMENSIONS
        for unit in dimension.units
        for alias in unit.backward_compatible_aliases
    }
)

# This table exists only for current adapters that historically supplied semantics but no
# dimension.  Public conversion calls must always supply the dimension explicitly.
_COMPATIBILITY_SEMANTICS: Final[Mapping[str, DimensionId]] = MappingProxyType(
    {
        **{
            item: DimensionId.FORCE_PER_AREA
            for item in (
                "mechanics.stress.engineering",
                "mechanics.stress.shear",
                "mechanics.modulus.shear.relaxation",
                "mechanics.engineering_stress",
                "stress",
                "stress.engineering",
                "stress.shear",
                "stress.true",
                "stress.proof",
                "stress.intercept",
                "modulus.young",
                "modulus.elastic.young",
                "modulus.shear.relaxation",
                "modulus.shear.storage",
                "modulus.shear.loss",
                "metal.elastic_modulus",
                "metal.proof_stress",
                "pressure",
            )
        },
        **{
            item: DimensionId.STRAIN
            for item in (
                "mechanics.strain.engineering",
                "mechanics.strain.shear",
                "mechanics.engineering_strain",
                "strain",
                "strain.engineering",
                "strain.shear",
                "strain.true",
                "strain.true_plastic",
                "strain.proof",
                "strain.offset",
            )
        },
        **{item: DimensionId.TIME for item in ("time", "time.elapsed", "time.relaxation")},
        **{item: DimensionId.FORCE for item in ("force", "mechanics.force")},
        **{
            item: DimensionId.LENGTH
            for item in ("length", "displacement", "axial.displacement")
        },
        **{item: DimensionId.SPEED for item in ("kinematics.speed",)},
        **{item: DimensionId.MASS for item in ("mass", "mass.sample")},
        **{
            item: DimensionId.MASS_PER_VOLUME
            for item in ("density", "mass.density", "physics.density")
        },
        **{
            item: DimensionId.TEMPERATURE
            for item in ("temperature.absolute", "temperature.test", "temperature.difference")
        },
    }
)

KG_M_S_COMPATIBILITY_UNITS: Final[Mapping[DimensionId, str]] = MappingProxyType(
    {
        DimensionId.FORCE_PER_AREA: "Pa",
        DimensionId.LENGTH: "m",
        DimensionId.SPEED: "m/s",
        DimensionId.TIME: "s",
        DimensionId.FORCE: "N",
        DimensionId.MASS: "kg",
        DimensionId.MASS_PER_VOLUME: "kg/m3",
        DimensionId.TEMPERATURE: "K",
        DimensionId.STRAIN: "1",
    }
)


def dimension_definition(dimension: DimensionId) -> DimensionDefinition:
    return _DIMENSION_BY_ID[dimension]


def canonical_unit_id(unit_text: str, *, location: str = "unit") -> str:
    """Resolve a stable ID or one bounded historical display alias."""

    if unit_text in _UNITS:
        return unit_text
    if unit_text in _ALIASES:
        return _ALIASES[unit_text]
    raise UnitError(
        code="CMP-UNIT-0001",
        message=f"unsupported unit identifier: {unit_text}",
        location=location,
    )


def unit_definition(unit_id: str, *, location: str = "unit") -> UnitDefinition:
    resolved = canonical_unit_id(unit_id, location=location)
    return _UNITS[resolved]


def dimension_for_quantity_semantics(
    quantity_semantics: str, *, location: str = "quantity_semantics"
) -> DimensionId:
    """Return the closed legacy adapter mapping; never infer from spelling or unit."""

    try:
        return _COMPATIBILITY_SEMANTICS[quantity_semantics]
    except KeyError as error:
        raise UnitError(
            code="CMP-UNIT-0005",
            message=f"unsupported compatibility quantity semantics: {quantity_semantics}",
            location=location,
        ) from error


def parse_decimal(value: str | Decimal, *, location: str) -> Decimal:
    try:
        result = value if isinstance(value, Decimal) else Decimal(value)
    except (DecimalException, ValueError) as error:
        raise UnitError(
            code="CMP-UNIT-0004",
            message="value must be a finite decimal string",
            location=location,
        ) from error
    result = _bounded(result, location=location)
    if len(result.as_tuple().digits) > NUMERIC_SIGNIFICANT_DIGITS:
        raise UnitError(
            code="CMP-UNIT-0004",
            message=f"value must contain at most {NUMERIC_SIGNIFICANT_DIGITS} significant digits",
            location=location,
        )
    return result


def decimal_text(value: Decimal) -> str:
    """Stable, lossless text for the public decimal contract."""

    if value.is_zero():
        return "0"
    return str(value)


def _bounded(value: Decimal, *, location: str) -> Decimal:
    if not value.is_finite():
        raise UnitError(
            code="CMP-UNIT-0004",
            message="NaN and Infinity are not supported",
            location=location,
        )
    if not value.is_zero() and not (
        MINIMUM_ADJUSTED_EXPONENT <= value.adjusted() <= MAXIMUM_ADJUSTED_EXPONENT
    ):
        raise UnitError(
            code="CMP-UNIT-0004",
            message=(
                "decimal adjusted exponent must be between "
                f"{MINIMUM_ADJUSTED_EXPONENT} and {MAXIMUM_ADJUSTED_EXPONENT}"
            ),
            location=location,
        )
    return value


def _validate_reference(reference: QuantityReference, *, location: str) -> UnitDefinition:
    unit = unit_definition(reference.unit_id, location=f"{location}.unit_id")
    if unit.dimension is not reference.dimension:
        raise UnitError(
            code="CMP-UNIT-0002",
            message="unit identifier does not belong to the declared dimension",
            location=location,
            source_dimension=unit.dimension,
            target_dimension=reference.dimension,
        )
    if reference.dimension is DimensionId.TEMPERATURE and reference.quantity_semantics not in {
        "temperature.absolute",
        "temperature.test",
        "temperature.difference",
    }:
        raise UnitError(
            code="CMP-UNIT-0005",
            message=(
                "temperature quantity semantics must explicitly select absolute/test or difference"
            ),
            location=f"{location}.quantity_semantics",
            source_dimension=reference.dimension,
        )
    return unit


def convert_value(
    value: str | Decimal,
    *,
    original_unit_string: str,
    source: QuantityReference,
    target: QuantityReference,
    location: str,
) -> ConversionResult:
    """Convert one explicit same-dimension, same-semantics value."""

    if not location or location != location.strip() or len(location) > 255:
        raise UnitError(
            code="CMP-UNIT-0005",
            message="location must contain 1..255 trimmed characters",
            location="location",
        )
    if not original_unit_string or len(original_unit_string) > 64:
        raise UnitError(
            code="CMP-UNIT-0005",
            message="original_unit_string must contain 1..64 characters",
            location=f"{location}.original_unit_string",
        )
    if source.dimension is not target.dimension:
        raise UnitError(
            code="CMP-UNIT-0002",
            message="cross-dimension conversion is not supported",
            location=location,
            source_dimension=source.dimension,
            target_dimension=target.dimension,
        )
    if source.quantity_semantics != target.quantity_semantics:
        raise UnitError(
            code="CMP-UNIT-0003",
            message="conversion cannot change quantity semantics",
            location=location,
            source_dimension=source.dimension,
            target_dimension=target.dimension,
        )

    source_unit = _validate_reference(source, location=f"{location}.source")
    original_unit_id = canonical_unit_id(
        original_unit_string,
        location=f"{location}.original_unit_string",
    )
    if original_unit_id != source_unit.unit_id:
        original_unit = unit_definition(original_unit_id)
        raise UnitError(
            code="CMP-UNIT-0005",
            message="original_unit_string does not identify the declared source unit",
            location=f"{location}.original_unit_string",
            source_dimension=original_unit.dimension,
            target_dimension=source_unit.dimension,
        )
    target_unit = _validate_reference(target, location=f"{location}.target")
    try:
        parsed = parse_decimal(value, location=f"{location}.value")
    except UnitError as error:
        raise UnitError(
            code=error.code,
            message=error.message,
            location=error.location,
            source_dimension=source.dimension,
            target_dimension=target.dimension,
        ) from error
    is_temperature_difference = (
        source.dimension is DimensionId.TEMPERATURE
        and source.quantity_semantics == "temperature.difference"
    )
    try:
        with localcontext(_DECIMAL_CONTEXT):
            direct_scale = source_unit.scale_to_canonical / target_unit.scale_to_canonical
            direct_offset = (
                Decimal("0")
                if is_temperature_difference
                else (
                    source_unit.offset_to_canonical - target_unit.offset_to_canonical
                )
                / target_unit.scale_to_canonical
            )
            converted = parsed * direct_scale + direct_offset
    except DecimalException as error:
        raise UnitError(
            code="CMP-UNIT-0004",
            message="conversion exceeded the supported decimal precision/range",
            location=f"{location}.value",
            source_dimension=source.dimension,
            target_dimension=target.dimension,
        ) from error
    try:
        _bounded(converted, location=f"{location}.value")
    except UnitError as error:
        raise UnitError(
            code=error.code,
            message=error.message,
            location=error.location,
            source_dimension=source.dimension,
            target_dimension=target.dimension,
        ) from error
    definition = dimension_definition(source.dimension)
    return ConversionResult(
        location=location,
        original_value=parsed,
        original_unit_string=original_unit_string,
        source=QuantityReference(
            source.dimension,
            source.quantity_semantics,
            source_unit.unit_id,
        ),
        target=QuantityReference(
            target.dimension,
            target.quantity_semantics,
            target_unit.unit_id,
        ),
        converted_value=converted,
        conversion_kind=(
            ConversionKind.MULTIPLICATIVE
            if is_temperature_difference
            else (
                ConversionKind.AFFINE_ABSOLUTE
                if source.dimension is DimensionId.TEMPERATURE
                else ConversionKind.MULTIPLICATIVE
            )
        ),
        scale=direct_scale,
        offset=direct_offset,
        absolute_tolerance=definition.absolute_tolerance,
        relative_tolerance=definition.relative_tolerance,
    )


def unit_system_contract() -> dict[str, object]:
    return {
        "contract_version": "1.1.0",
        "numeric_policy": {
            "significant_digits": NUMERIC_SIGNIFICANT_DIGITS,
            "minimum_adjusted_exponent": MINIMUM_ADJUSTED_EXPONENT,
            "maximum_adjusted_exponent": MAXIMUM_ADJUSTED_EXPONENT,
        },
        "dimensions": [
            {
                "dimension": definition.dimension.value,
                "canonical_unit_id": definition.canonical_unit_id,
                "absolute_tolerance": decimal_text(definition.absolute_tolerance),
                "relative_tolerance": decimal_text(definition.relative_tolerance),
                "units": [
                    {
                        "unit_id": unit.unit_id,
                        "symbol": unit.symbol,
                        "dimension": unit.dimension.value,
                        "conversion_kind": unit.conversion_kind.value,
                        "scale_to_canonical": decimal_text(unit.scale_to_canonical),
                        "offset_to_canonical": decimal_text(unit.offset_to_canonical),
                        "backward_compatible_aliases": list(
                            unit.backward_compatible_aliases
                        ),
                    }
                    for unit in definition.units
                ],
            }
            for definition in DIMENSIONS
        ],
        "compatibility_unit_systems": [
            {
                "unit_system_id": "kg_m_s",
                "production_default": False,
                "units": {
                    dimension.value: unit_id
                    for dimension, unit_id in KG_M_S_COMPATIBILITY_UNITS.items()
                },
            }
        ],
    }


__all__ = [
    "DIMENSIONS",
    "KG_M_S_COMPATIBILITY_UNITS",
    "ConversionKind",
    "ConversionResult",
    "DimensionDefinition",
    "DimensionId",
    "QuantityReference",
    "UnitDefinition",
    "UnitError",
    "canonical_unit_id",
    "convert_value",
    "decimal_text",
    "dimension_definition",
    "dimension_for_quantity_semantics",
    "parse_decimal",
    "unit_definition",
    "unit_system_contract",
]

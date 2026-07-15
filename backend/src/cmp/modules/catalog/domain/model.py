"""Typed Material Catalog content owned by immutable revisions.

Core engineering properties intentionally have one named field each.  Additional property
families will receive their own typed schemas/revisions instead of silently falling back to an
EAV table or an unbounded JSON document.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID


class CatalogError(Exception):
    """Base error for catalog commands and queries."""


class CatalogNotFound(CatalogError):
    """A catalog aggregate or immutable revision is absent or not visible."""


class CatalogConflict(CatalogError):
    """A catalog command conflicts with the immutable aggregate history."""


class InvalidCatalogCommand(CatalogError, ValueError):
    """Typed catalog content fails a semantic invariant."""


class PropertySourceKind(StrEnum):
    MANUAL = "manual"
    SUPPLIER_DATASHEET = "supplier_datasheet"
    TEST_DERIVED = "test_derived"
    LITERATURE = "literature"
    CALIBRATION = "calibration"


class MaterialClass(StrEnum):
    """Governed top-level class used to route compatible modeling workflows."""

    UNCLASSIFIED = "unclassified"
    METAL = "metal"
    POLYMER = "polymer"
    ELASTOMER = "elastomer"
    COMPOSITE = "composite"
    CERAMIC = "ceramic"
    OTHER = "other"


def _nonzero(name: str, value: UUID) -> None:
    if value.int == 0:
        raise InvalidCatalogCommand(f"{name} must be non-zero")


def _required_text(name: str, value: str, maximum: int) -> None:
    if not value or value != value.strip() or len(value) > maximum or "\x00" in value:
        raise InvalidCatalogCommand(
            f"{name} must be trimmed and contain 1..{maximum} characters"
        )


def _optional_text(name: str, value: str | None, maximum: int) -> None:
    if value is not None:
        _required_text(name, value, maximum)


def _finite(name: str, value: float) -> None:
    if not math.isfinite(value):
        raise InvalidCatalogCommand(f"{name} must be finite")


def _optional_finite(name: str, value: float | None) -> None:
    if value is not None:
        _finite(name, value)


@dataclass(frozen=True, slots=True)
class PropertySource:
    """Provenance label for a typed engineering value.

    The full source artifact or test relation will be added in the testing/dataset slice.  The
    source reference is retained now so manual and published property values remain explicit.
    """

    kind: PropertySourceKind
    reference: str | None = None

    def __post_init__(self) -> None:
        _optional_text("property source reference", self.reference, 2000)
        if self.kind is not PropertySourceKind.MANUAL and self.reference is None:
            raise InvalidCatalogCommand(
                "a non-manual property source requires a stable source reference"
            )


@dataclass(frozen=True, slots=True)
class Applicability:
    """Typed applicability range for the initial elastic property set."""

    temperature_min_k: float | None = None
    temperature_max_k: float | None = None
    strain_rate_min_per_s: float | None = None
    strain_rate_max_per_s: float | None = None
    note: str | None = None

    def __post_init__(self) -> None:
        _optional_finite("temperature_min_k", self.temperature_min_k)
        _optional_finite("temperature_max_k", self.temperature_max_k)
        _optional_finite("strain_rate_min_per_s", self.strain_rate_min_per_s)
        _optional_finite("strain_rate_max_per_s", self.strain_rate_max_per_s)
        _optional_text("applicability note", self.note, 2000)
        if self.temperature_min_k is not None and self.temperature_min_k <= 0:
            raise InvalidCatalogCommand("temperature_min_k must be greater than zero")
        if self.temperature_max_k is not None and self.temperature_max_k <= 0:
            raise InvalidCatalogCommand("temperature_max_k must be greater than zero")
        if (
            self.temperature_min_k is not None
            and self.temperature_max_k is not None
            and self.temperature_min_k > self.temperature_max_k
        ):
            raise InvalidCatalogCommand("temperature applicability range is inverted")
        if self.strain_rate_min_per_s is not None and self.strain_rate_min_per_s < 0:
            raise InvalidCatalogCommand("strain_rate_min_per_s cannot be negative")
        if self.strain_rate_max_per_s is not None and self.strain_rate_max_per_s < 0:
            raise InvalidCatalogCommand("strain_rate_max_per_s cannot be negative")
        if (
            self.strain_rate_min_per_s is not None
            and self.strain_rate_max_per_s is not None
            and self.strain_rate_min_per_s > self.strain_rate_max_per_s
        ):
            raise InvalidCatalogCommand("strain-rate applicability range is inverted")


@dataclass(frozen=True, slots=True)
class MaterialContent:
    """Human-facing fields for one Material revision."""

    name: str
    material_code: str | None = None
    material_family: str | None = None
    description: str | None = None
    material_class: MaterialClass = MaterialClass.UNCLASSIFIED

    def __post_init__(self) -> None:
        _required_text("material name", self.name, 200)
        _optional_text("material code", self.material_code, 100)
        _optional_text("material family", self.material_family, 100)
        _optional_text("material description", self.description, 4000)


@dataclass(frozen=True, slots=True)
class MaterialStateContent:
    """A versioned manufacturing/process condition for one stable Material State identity."""

    material_id: UUID
    material_revision_id: UUID
    name: str
    manufacturing_route: str | None = None
    heat_treatment: str | None = None
    lot_or_batch: str | None = None
    description: str | None = None

    def __post_init__(self) -> None:
        _nonzero("material_id", self.material_id)
        _nonzero("material_revision_id", self.material_revision_id)
        _required_text("material state name", self.name, 200)
        _optional_text("manufacturing route", self.manufacturing_route, 500)
        _optional_text("heat treatment", self.heat_treatment, 500)
        _optional_text("lot or batch", self.lot_or_batch, 255)
        _optional_text("material state description", self.description, 4000)


@dataclass(frozen=True, slots=True)
class PropertySetContent:
    """Initial explicitly typed mechanical property set.

    All values use SI units: kg/m³, Pa, dimensionless Poisson ratio, and Pa.  The first
    Material Model IR consumes density, Young's modulus, and Poisson ratio.  Yield stress is
    intentionally optional because the reference MVP model is linear elastic.
    """

    material_state_id: UUID
    material_state_revision_id: UUID
    density_kg_per_m3: float
    density_source: PropertySource
    youngs_modulus_pa: float
    youngs_modulus_source: PropertySource
    poisson_ratio: float
    poisson_ratio_source: PropertySource
    yield_stress_pa: float | None = None
    yield_stress_source: PropertySource | None = None
    applicability: Applicability = Applicability()

    def __post_init__(self) -> None:
        _nonzero("material_state_id", self.material_state_id)
        _nonzero("material_state_revision_id", self.material_state_revision_id)
        _finite("density_kg_per_m3", self.density_kg_per_m3)
        _finite("youngs_modulus_pa", self.youngs_modulus_pa)
        _finite("poisson_ratio", self.poisson_ratio)
        _optional_finite("yield_stress_pa", self.yield_stress_pa)
        if self.density_kg_per_m3 <= 0:
            raise InvalidCatalogCommand("density_kg_per_m3 must be greater than zero")
        if self.youngs_modulus_pa <= 0:
            raise InvalidCatalogCommand("youngs_modulus_pa must be greater than zero")
        if not -1.0 < self.poisson_ratio < 0.5:
            raise InvalidCatalogCommand(
                "poisson_ratio must be within the stable isotropic interval (-1, 0.5)"
            )
        if self.yield_stress_pa is not None and self.yield_stress_pa <= 0:
            raise InvalidCatalogCommand("yield_stress_pa must be greater than zero")
        if (self.yield_stress_pa is None) != (self.yield_stress_source is None):
            raise InvalidCatalogCommand(
                "yield_stress_pa and yield_stress_source must be supplied together"
            )


def material_canonical(content: MaterialContent) -> dict[str, str | None]:
    return {
        "name": content.name,
        "material_code": content.material_code,
        "material_family": content.material_family,
        "description": content.description,
        "material_class": content.material_class.value,
    }


def material_state_canonical(content: MaterialStateContent) -> dict[str, str | None]:
    return {
        "material_id": str(content.material_id),
        "material_revision_id": str(content.material_revision_id),
        "name": content.name,
        "manufacturing_route": content.manufacturing_route,
        "heat_treatment": content.heat_treatment,
        "lot_or_batch": content.lot_or_batch,
        "description": content.description,
    }


def property_set_canonical(content: PropertySetContent) -> dict[str, object]:
    return {
        "material_state_id": str(content.material_state_id),
        "material_state_revision_id": str(content.material_state_revision_id),
        "density_kg_per_m3": content.density_kg_per_m3,
        "density_source": {
            "kind": content.density_source.kind.value,
            "reference": content.density_source.reference,
        },
        "youngs_modulus_pa": content.youngs_modulus_pa,
        "youngs_modulus_source": {
            "kind": content.youngs_modulus_source.kind.value,
            "reference": content.youngs_modulus_source.reference,
        },
        "poisson_ratio": content.poisson_ratio,
        "poisson_ratio_source": {
            "kind": content.poisson_ratio_source.kind.value,
            "reference": content.poisson_ratio_source.reference,
        },
        "yield_stress_pa": content.yield_stress_pa,
        "yield_stress_source": (
            {
                "kind": content.yield_stress_source.kind.value,
                "reference": content.yield_stress_source.reference,
            }
            if content.yield_stress_source is not None
            else None
        ),
        "applicability": {
            "temperature_min_k": content.applicability.temperature_min_k,
            "temperature_max_k": content.applicability.temperature_max_k,
            "strain_rate_min_per_s": content.applicability.strain_rate_min_per_s,
            "strain_rate_max_per_s": content.applicability.strain_rate_max_per_s,
            "note": content.applicability.note,
        },
    }

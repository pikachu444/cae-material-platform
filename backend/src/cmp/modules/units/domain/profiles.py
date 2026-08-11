"""Typed immutable Unit Profile content and exact usage pins."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from cmp.modules.units.domain.system import (
    DimensionId,
    UnitError,
    canonical_unit_id,
    unit_definition,
)
from cmp.shared.domain.revisions import content_sha256

_KEY = re.compile(r"^[a-z][a-z0-9_-]{0,159}$")
_SEMANTICS = re.compile(r"^[a-z][a-z0-9_.-]{0,159}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class UnitApplicationRole(StrEnum):
    INPUT = "input"
    DISPLAY = "display"
    SOLVER_EXPORT = "solver_export"


@dataclass(frozen=True, slots=True)
class UnitProfileSelection:
    quantity_semantics: str
    dimension: DimensionId
    input_unit_id: str
    display_unit_id: str
    solver_export_unit_id: str | None = None

    def __post_init__(self) -> None:
        if not _SEMANTICS.fullmatch(self.quantity_semantics):
            raise UnitError(
                code="CMP-UNIT-0005",
                message="Unit Profile quantity_semantics is invalid",
                location="selections.quantity_semantics",
                source_dimension=self.dimension,
            )
        for role, supplied in (
            ("input_unit_id", self.input_unit_id),
            ("display_unit_id", self.display_unit_id),
            ("solver_export_unit_id", self.solver_export_unit_id),
        ):
            if supplied is None:
                continue
            unit = unit_definition(supplied, location=f"selections.{role}")
            if unit.unit_id != supplied:
                raise UnitError(
                    code="CMP-UNIT-0001",
                    message="Unit Profile selections must use stable canonical unit identifiers",
                    location=f"selections.{role}",
                    source_dimension=unit.dimension,
                    target_dimension=self.dimension,
                )
            if unit.dimension is not self.dimension:
                raise UnitError(
                    code="CMP-UNIT-0002",
                    message="Unit Profile unit does not belong to the declared dimension",
                    location=f"selections.{role}",
                    source_dimension=unit.dimension,
                    target_dimension=self.dimension,
                )
        # Reuse the stricter absolute/difference validation without inventing a conversion.
        if self.dimension is DimensionId.TEMPERATURE and self.quantity_semantics not in {
            "temperature.absolute",
            "temperature.test",
            "temperature.difference",
        }:
            raise UnitError(
                code="CMP-UNIT-0005",
                message="temperature selection must declare absolute/test or difference semantics",
                location="selections.quantity_semantics",
                source_dimension=self.dimension,
            )

    def unit_for(self, role: UnitApplicationRole) -> str:
        if role is UnitApplicationRole.INPUT:
            return self.input_unit_id
        if role is UnitApplicationRole.DISPLAY:
            return self.display_unit_id
        if self.solver_export_unit_id is None:
            raise UnitError(
                code="CMP-UNIT-0006",
                message="Unit Profile has no solver export unit for this quantity",
                location=f"selections.{self.quantity_semantics}.solver_export_unit_id",
                source_dimension=self.dimension,
            )
        return self.solver_export_unit_id


@dataclass(frozen=True, slots=True)
class UnitProfileContent:
    profile_key: str
    label: str
    description: str | None
    non_production: bool
    selections: tuple[UnitProfileSelection, ...]

    def __post_init__(self) -> None:
        if not _KEY.fullmatch(self.profile_key):
            raise UnitError(
                code="CMP-UNIT-0005",
                message="profile_key must be a stable lower-case key",
                location="content.profile_key",
            )
        if not self.label or self.label != self.label.strip() or len(self.label) > 200:
            raise UnitError(
                code="CMP-UNIT-0005",
                message="label must contain 1..200 trimmed characters",
                location="content.label",
            )
        if self.description is not None and (
            not self.description
            or self.description != self.description.strip()
            or len(self.description) > 1000
        ):
            raise UnitError(
                code="CMP-UNIT-0005",
                message="description must be null or contain 1..1000 trimmed characters",
                location="content.description",
            )
        if not 1 <= len(self.selections) <= 128:
            raise UnitError(
                code="CMP-UNIT-0005",
                message="a Unit Profile requires 1..128 selections",
                location="content.selections",
            )
        semantics = [item.quantity_semantics for item in self.selections]
        if len(set(semantics)) != len(semantics):
            raise UnitError(
                code="CMP-UNIT-0005",
                message="Unit Profile quantity semantics must be unique",
                location="content.selections",
            )

    @property
    def digest(self) -> str:
        return content_sha256(unit_profile_canonical(self))

    def selection(self, quantity_semantics: str, *, location: str) -> UnitProfileSelection:
        for selection in self.selections:
            if selection.quantity_semantics == quantity_semantics:
                return selection
        raise UnitError(
            code="CMP-UNIT-0006",
            message=f"Unit Profile has no selection for {quantity_semantics}",
            location=location,
        )


@dataclass(frozen=True, slots=True)
class UnitProfilePin:
    profile_id: UUID
    revision_id: UUID
    content_sha256: str

    def __post_init__(self) -> None:
        if (
            not isinstance(self.profile_id, UUID)
            or not isinstance(self.revision_id, UUID)
            or self.profile_id.int == 0
            or self.revision_id.int == 0
        ):
            raise UnitError(
                code="CMP-UNIT-0005",
                message="Unit Profile pin UUIDs must be non-zero",
                location="unit_profile",
            )
        if not _SHA256.fullmatch(self.content_sha256):
            raise UnitError(
                code="CMP-UNIT-0005",
                message="Unit Profile pin requires an exact lowercase SHA-256 digest",
                location="unit_profile.content_sha256",
            )


@dataclass(frozen=True, slots=True)
class UnitApplication:
    location: str
    role: UnitApplicationRole
    quantity_semantics: str
    dimension: DimensionId
    unit_id: str

    def __post_init__(self) -> None:
        if not self.location or self.location != self.location.strip() or len(self.location) > 255:
            raise UnitError(
                code="CMP-UNIT-0005",
                message="unit application location must contain 1..255 trimmed characters",
                location="unit_application.location",
            )
        selection = UnitProfileSelection(
            quantity_semantics=self.quantity_semantics,
            dimension=self.dimension,
            input_unit_id=self.unit_id,
            display_unit_id=self.unit_id,
        )
        object.__setattr__(self, "unit_id", canonical_unit_id(selection.input_unit_id))


def unit_profile_canonical(value: UnitProfileContent) -> dict[str, object]:
    return {
        "profile_key": value.profile_key,
        "label": value.label,
        "description": value.description,
        "non_production": value.non_production,
        "selections": [
            {
                "quantity_semantics": item.quantity_semantics,
                "dimension": item.dimension.value,
                "input_unit_id": item.input_unit_id,
                "display_unit_id": item.display_unit_id,
                "solver_export_unit_id": item.solver_export_unit_id,
            }
            for item in value.selections
        ],
    }


def unit_profile_pin_canonical(value: UnitProfilePin) -> dict[str, str]:
    return {
        "profile_id": str(value.profile_id),
        "revision_id": str(value.revision_id),
        "content_sha256": value.content_sha256,
    }


def unit_application_canonical(value: UnitApplication) -> dict[str, str]:
    return {
        "location": value.location,
        "role": value.role.value,
        "quantity_semantics": value.quantity_semantics,
        "dimension": value.dimension.value,
        "unit_id": value.unit_id,
    }


def applications_for_profile(
    content: UnitProfileContent,
    *,
    uses: tuple[tuple[str, UnitApplicationRole, str, DimensionId], ...],
) -> tuple[UnitApplication, ...]:
    """Resolve explicit application locations against one exact profile content."""

    result: list[UnitApplication] = []
    seen: set[tuple[str, UnitApplicationRole]] = set()
    for location, role, semantics, dimension in uses:
        if (location, role) in seen:
            raise UnitError(
                code="CMP-UNIT-0005",
                message="unit application location/role pairs must be unique",
                location=location,
            )
        seen.add((location, role))
        selection = content.selection(semantics, location=location)
        if selection.dimension is not dimension:
            raise UnitError(
                code="CMP-UNIT-0002",
                message="Unit Profile selection has the wrong dimension for the application",
                location=location,
                source_dimension=selection.dimension,
                target_dimension=dimension,
            )
        result.append(
            UnitApplication(
                location=location,
                role=role,
                quantity_semantics=semantics,
                dimension=dimension,
                unit_id=selection.unit_for(role),
            )
        )
    return tuple(result)


__all__ = [
    "UnitApplication",
    "UnitApplicationRole",
    "UnitProfileContent",
    "UnitProfilePin",
    "UnitProfileSelection",
    "applications_for_profile",
    "unit_application_canonical",
    "unit_profile_canonical",
    "unit_profile_pin_canonical",
]

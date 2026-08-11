"""Public API value contracts shared by bounded Unit Profile consumers."""

from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, StringConstraints

from cmp.modules.units.domain.profiles import UnitProfilePin
from cmp.modules.units.domain.system import DimensionId


class UnitProfilePinInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    profile_id: UUID
    revision_id: UUID
    content_sha256: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]

    def to_domain(self) -> UnitProfilePin:
        return UnitProfilePin(self.profile_id, self.revision_id, self.content_sha256)


class UnitApplicationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    location: str
    role: Literal["input", "display", "solver_export"]
    quantity_semantics: str
    dimension: DimensionId
    unit_id: str


__all__ = ["UnitApplicationResponse", "UnitProfilePinInput"]

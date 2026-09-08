"""Project-scoped, read-only index of all persisted Solver Card families."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from cmp.modules.identity_access.domain.authorization import AuthorizationDecision, Permission
from cmp.modules.identity_access.domain.security import SecurityContext

CARD_FAMILY_REFERENCE_ELASTIC = "reference_elastic"
CARD_FAMILY_LINEAR_VISCOELASTIC = "linear_viscoelastic"
CARD_FAMILY_OGDEN_PRONY = "ogden_prony"
CARD_FAMILY_TABULATED_PLASTICITY = "tabulated_plasticity"
CARD_FAMILY_NEUTRAL_SOLVER = "neutral_solver"
CARD_FAMILY_NEUTRAL_HYPERELASTIC = "neutral_hyperelastic"
CARD_FAMILY_UNSUPPORTED = "unsupported"

_SCHEMA_FAMILIES = {
    "urn:cmp:exporting:reference-openradioss-elast:1.0.0": CARD_FAMILY_REFERENCE_ELASTIC,
    "urn:cmp:exporting:reference-linear-viscoelastic-prony-card:1.0.0": (
        CARD_FAMILY_LINEAR_VISCOELASTIC
    ),
    "urn:cmp:exporting:reference-ogden-prony-card:1.0.0": CARD_FAMILY_OGDEN_PRONY,
    "urn:cmp:exporting:reference-isotropic-tabulated-plasticity-card:1.0.0": (
        CARD_FAMILY_TABULATED_PLASTICITY
    ),
}
_NEUTRAL_SCHEMAS = frozenset(
    {
        "urn:cmp:exporting:neutral-hyperelastic-card:1.0.0",
        "urn:cmp:exporting:neutral-hyperelastic-card:1.1.0",
        "urn:cmp:exporting:neutral-family-card:2.0.0",
        "urn:cmp:exporting:neutral-family-card:2.1.0",
    }
)
_KNOWN_FAMILIES = frozenset(
    {
        CARD_FAMILY_REFERENCE_ELASTIC,
        CARD_FAMILY_LINEAR_VISCOELASTIC,
        CARD_FAMILY_OGDEN_PRONY,
        CARD_FAMILY_TABULATED_PLASTICITY,
        CARD_FAMILY_NEUTRAL_SOLVER,
        CARD_FAMILY_NEUTRAL_HYPERELASTIC,
        CARD_FAMILY_UNSUPPORTED,
    }
)


@dataclass(frozen=True, slots=True)
class ProjectCardIndexRow:
    solver_card_id: UUID
    revision_id: UUID
    revision_no: int
    schema_id: str
    content_hash: str
    title: str
    material_model_id: UUID | None
    material_model_revision_id: UUID | None
    neutral_material_id: UUID | None
    material_id: UUID | None
    target_solver: str
    target_version: str
    target_unit_system: str
    solver_material_id: int
    card_sha256: str
    exporter_id: str | None
    model_family: str | None
    family: str | None
    created_at: datetime

    @property
    def card_family(self) -> str:
        family = _SCHEMA_FAMILIES.get(self.schema_id)
        if family is not None:
            return family
        if self.schema_id in _NEUTRAL_SCHEMAS:
            if self.model_family == "hyperelastic" or self.model_family is None:
                return CARD_FAMILY_NEUTRAL_HYPERELASTIC
            if self.model_family in {"isotropic_tabulated_plasticity", "generalized_maxwell"}:
                return CARD_FAMILY_NEUTRAL_SOLVER
        return CARD_FAMILY_UNSUPPORTED

    @property
    def unsupported_reason(self) -> str | None:
        if self.card_family != CARD_FAMILY_UNSUPPORTED:
            return None
        return f"Solver Card schema is not supported by this reader: {self.schema_id}"


@dataclass(frozen=True, slots=True)
class ProjectCardIndexPage:
    items: tuple[ProjectCardIndexRow, ...]
    total_count: int
    page_size: int = 12


class ProjectCardIndexRepository(Protocol):
    def list_current_cards(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
    ) -> tuple[ProjectCardIndexRow, ...]: ...


def _require_read(context: SecurityContext, decision: AuthorizationDecision) -> None:
    if (
        decision.permission is not Permission.EXPORT_READ
        or decision.principal_id != context.principal.id
        or decision.organization_id != context.organization_id
        or decision.project_id != context.project_id
        or decision.request_id != context.request_id
        or decision.trace_id != context.trace_id
    ):
        raise ValueError("authorization decision does not match Solver Card index request")


class ProjectCardIndexService:
    def __init__(self, *, repository: ProjectCardIndexRepository) -> None:
        self._repository = repository

    def list(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        *,
        query: str = "",
        family: str | None = None,
        material_id: UUID | None = None,
    ) -> ProjectCardIndexPage:
        _require_read(context, decision)
        if family is not None and family not in _KNOWN_FAMILIES:
            raise ValueError(f"unsupported Solver Card family filter: {family}")
        normalized_query = query.strip().casefold()
        rows: Sequence[ProjectCardIndexRow] = self._repository.list_current_cards(
            context=context,
            decision=decision,
        )
        filtered = [
            row
            for row in rows
            if (family is None or row.card_family == family)
            and (material_id is None or row.material_id == material_id)
            and (
                not normalized_query
                or normalized_query in row.title.casefold()
                or normalized_query in str(row.solver_card_id).casefold()
                or normalized_query in str(row.revision_id).casefold()
                or normalized_query in row.card_family.casefold()
                or normalized_query in row.target_solver.casefold()
                or (row.exporter_id is not None and normalized_query in row.exporter_id.casefold())
            )
        ]
        filtered.sort(key=lambda row: (row.title.casefold(), str(row.solver_card_id)))
        return ProjectCardIndexPage(
            items=tuple(filtered),
            total_count=len(filtered),
        )


__all__ = [
    "CARD_FAMILY_LINEAR_VISCOELASTIC",
    "CARD_FAMILY_NEUTRAL_HYPERELASTIC",
    "CARD_FAMILY_NEUTRAL_SOLVER",
    "CARD_FAMILY_OGDEN_PRONY",
    "CARD_FAMILY_REFERENCE_ELASTIC",
    "CARD_FAMILY_TABULATED_PLASTICITY",
    "CARD_FAMILY_UNSUPPORTED",
    "ProjectCardIndexPage",
    "ProjectCardIndexRepository",
    "ProjectCardIndexRow",
    "ProjectCardIndexService",
]

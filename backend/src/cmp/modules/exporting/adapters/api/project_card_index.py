"""Direct project-scoped Solver Card index for the connected reader."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from cmp.modules.exporting.application.project_card_index import (
    CARD_FAMILY_LINEAR_VISCOELASTIC,
    CARD_FAMILY_NEUTRAL_HYPERELASTIC,
    CARD_FAMILY_NEUTRAL_SOLVER,
    CARD_FAMILY_OGDEN_PRONY,
    CARD_FAMILY_REFERENCE_ELASTIC,
    CARD_FAMILY_TABULATED_PLASTICITY,
    ProjectCardIndexPage,
    ProjectCardIndexRow,
    ProjectCardIndexService,
)
from cmp.modules.identity_access.domain.authorization import AuthorizationDecision
from cmp.modules.identity_access.domain.security import SecurityContext

type Dependency = Callable[..., object]


class ProjectCardTargetResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    solver: str
    version: str
    unit_system: str


class ProjectCardIndexItemResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    solver_card_id: UUID
    revision_id: UUID
    revision_no: int = Field(ge=1)
    schema_id: str
    content_sha256: str
    card_sha256: str
    family: str
    title: str
    material_id: UUID | None
    material_model_id: UUID | None
    material_model_revision_id: UUID | None
    neutral_material_id: UUID | None
    target: ProjectCardTargetResponse
    solver_material_id: int
    exporter_id: str | None
    model_family: str | None
    neutral_family: str | None
    unsupported_reason: str | None
    links: dict[str, str]

    @classmethod
    def from_row(cls, value: ProjectCardIndexRow) -> ProjectCardIndexItemResponse:
        query = f"?revision_id={value.revision_id}"
        family_paths = {
            CARD_FAMILY_REFERENCE_ELASTIC: "solver-cards",
            CARD_FAMILY_LINEAR_VISCOELASTIC: "linear-viscoelastic-solver-cards",
            CARD_FAMILY_OGDEN_PRONY: "ogden-prony-solver-cards",
            CARD_FAMILY_TABULATED_PLASTICITY: "elastoplastic-solver-cards",
            CARD_FAMILY_NEUTRAL_HYPERELASTIC: "neutral-solver-cards",
            CARD_FAMILY_NEUTRAL_SOLVER: "neutral-solver-cards",
        }
        route = family_paths.get(value.card_family, "solver-cards")
        root = f"/api/v1/{route}/{value.solver_card_id}"
        return cls(
            solver_card_id=value.solver_card_id,
            revision_id=value.revision_id,
            revision_no=value.revision_no,
            schema_id=value.schema_id,
            content_sha256=value.content_hash,
            card_sha256=value.card_sha256,
            family=value.card_family,
            title=value.title,
            material_id=value.material_id,
            material_model_id=value.material_model_id,
            material_model_revision_id=value.material_model_revision_id,
            neutral_material_id=value.neutral_material_id,
            target=ProjectCardTargetResponse(
                solver=value.target_solver,
                version=value.target_version,
                unit_system=value.target_unit_system,
            ),
            solver_material_id=value.solver_material_id,
            exporter_id=value.exporter_id,
            model_family=value.model_family,
            neutral_family=value.family,
            unsupported_reason=value.unsupported_reason,
            links={
                "self": f"{root}{query}",
                "preview": f"{root}/preview{query}",
                "download": f"{root}/download{query}",
            },
        )


class ProjectCardIndexResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: tuple[ProjectCardIndexItemResponse, ...]
    total_count: int = Field(ge=0)
    page_size: int = Field(default=12, ge=1, le=12)

    @classmethod
    def from_page(cls, value: ProjectCardIndexPage) -> ProjectCardIndexResponse:
        return cls(
            items=tuple(ProjectCardIndexItemResponse.from_row(item) for item in value.items),
            total_count=value.total_count,
            page_size=value.page_size,
        )


def _scope(request: Request) -> tuple[SecurityContext, AuthorizationDecision]:
    context = getattr(request.state, "security_context", None)
    decision = getattr(request.state, "authorization_decision", None)
    if context is None or decision is None:
        raise RuntimeError("Solver Card index route dependencies did not initialize request scope")
    return context, decision


def install_project_card_index_api(
    app: FastAPI,
    *,
    service: ProjectCardIndexService | None,
    security_dependency: Dependency,
    read_dependency: Dependency,
) -> None:
    @app.get(
        "/api/v1/solver-cards",
        response_model=ProjectCardIndexResponse,
        operation_id="listProjectSolverCards",
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["exporting"],
        summary="List every current Solver Card family visible in the project.",
    )
    def list_project_solver_cards(
        request: Request,
        q: Annotated[str, Query(max_length=200)] = "",
        family: Annotated[str | None, Query(max_length=80)] = None,
        material_id: Annotated[UUID | None, Query()] = None,
    ) -> ProjectCardIndexResponse:
        context, decision = _scope(request)
        if service is None:
            raise HTTPException(status_code=503, detail="Solver Card index unavailable")
        try:
            page = service.list(
                context,
                decision,
                query=q,
                family=family,
                material_id=material_id,
            )
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        return ProjectCardIndexResponse.from_page(page)


__all__ = ["install_project_card_index_api"]

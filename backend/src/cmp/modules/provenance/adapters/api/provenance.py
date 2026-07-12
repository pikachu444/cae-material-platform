"""Protected T-13 Entity lookup and bounded lineage API."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Annotated, Any, cast
from uuid import UUID

from fastapi import Depends, FastAPI, Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.provenance.application.service import ProvenanceService
from cmp.modules.provenance.domain.model import (
    CompletenessState,
    EntityReferenceKind,
    GenerationRequirement,
    ProvenanceConflict,
    ProvenanceError,
    ProvenanceNotFound,
    ProvenanceRecord,
)

type Label = Annotated[str, StringConstraints(min_length=1, max_length=255)]
type Sha256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
type Dependency = Callable[..., object]


class EntityReferenceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: EntityReferenceKind
    type: str
    id: UUID
    sha256: Sha256


class CompletenessResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: CompletenessState
    issues: tuple[str, ...]


class ProvenanceLinks(BaseModel):
    model_config = ConfigDict(extra="forbid")

    self: str


class ProvenanceEntityResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entity_id: UUID
    organization_id: UUID
    project_id: UUID
    classification: DataClassification
    entity_type: str
    reference: EntityReferenceResponse
    generation_requirement: GenerationRequirement
    generation_activity_id: UUID | None
    created_at: datetime
    recorded_at: datetime
    recorded_by: UUID
    completeness: CompletenessResponse
    links: ProvenanceLinks

    @classmethod
    def from_record(cls, value: ProvenanceRecord) -> ProvenanceEntityResponse:
        entity = value.entity
        root = f"/api/v1/provenance/entities/{entity.id}"
        return cls(
            entity_id=entity.id,
            organization_id=entity.scope.organization_id,
            project_id=entity.scope.project_id,
            classification=entity.scope.classification,
            entity_type=entity.entity_type,
            reference=EntityReferenceResponse(
                kind=entity.reference.kind,
                type=entity.reference.reference_type,
                id=entity.reference.reference_id,
                sha256=entity.reference.content_sha256,
            ),
            generation_requirement=entity.generation_requirement,
            generation_activity_id=value.generation_activity_id,
            created_at=entity.created_at,
            recorded_at=entity.recorded_at,
            recorded_by=entity.recorded_by,
            completeness=CompletenessResponse(
                state=value.completeness.state,
                issues=value.completeness.issues,
            ),
            links=ProvenanceLinks(
                self=root,
            ),
        )


class ProvenanceProblem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Label
    title: Label
    status: Annotated[int, Field(ge=400, le=599)]
    detail: Annotated[str, StringConstraints(min_length=1, max_length=2000)]
    code: Annotated[str, StringConstraints(pattern=r"^CMP-PROVENANCE-[0-9]{4}$")]
    trace_id: Label


class ProvenanceHttpError(Exception):
    def __init__(
        self,
        *,
        context: SecurityContext,
        status: int,
        title: str,
        detail: str,
        code: str,
    ) -> None:
        self.context = context
        self.problem = ProvenanceProblem(
            type="urn:cmp:problem:provenance",
            title=title,
            status=status,
            detail=detail,
            code=code,
            trace_id=context.trace_id,
        )
        super().__init__(title)


def _request_scope(request: Request) -> tuple[SecurityContext, AuthorizationDecision]:
    context = getattr(request.state, "security_context", None)
    decision = getattr(request.state, "authorization_decision", None)
    if not isinstance(context, SecurityContext) or not isinstance(
        decision, AuthorizationDecision
    ):
        raise RuntimeError("provenance route dependencies did not initialize request scope")
    return context, decision


def _unavailable(context: SecurityContext) -> ProvenanceHttpError:
    return ProvenanceHttpError(
        context=context,
        status=503,
        title="Provenance service unavailable",
        detail="The authoritative provenance store is not configured for this deployment.",
        code="CMP-PROVENANCE-0003",
    )


def _translate(context: SecurityContext, error: Exception) -> ProvenanceHttpError:
    if isinstance(error, ProvenanceNotFound):
        return ProvenanceHttpError(
            context=context,
            status=404,
            title="Provenance Entity not found",
            detail="No Entity is visible in the selected tenant context.",
            code="CMP-PROVENANCE-0001",
        )
    if isinstance(error, ValueError):
        return ProvenanceHttpError(
            context=context,
            status=422,
            title="Invalid provenance query",
            detail="The query does not satisfy the bounded lineage contract.",
            code="CMP-PROVENANCE-0002",
        )
    if isinstance(error, ProvenanceConflict):
        return ProvenanceHttpError(
            context=context,
            status=409,
            title="Provenance query conflict",
            detail="The provenance query conflicts with immutable graph state.",
            code="CMP-PROVENANCE-0004",
        )
    return ProvenanceHttpError(
        context=context,
        status=409,
        title="Provenance query rejected",
        detail="The provenance query could not be completed.",
        code="CMP-PROVENANCE-0004",
    )


def install_provenance_api(
    application: FastAPI,
    *,
    service: ProvenanceService | None,
    security_dependency: Dependency,
    read_dependency: Dependency,
) -> None:
    previous_validation_handler = cast(
        Callable[[Request, RequestValidationError], Awaitable[Response]],
        application.exception_handlers.get(
            RequestValidationError, request_validation_exception_handler
        ),
    )

    @application.exception_handler(ProvenanceHttpError)
    async def provenance_error_handler(
        request: Request, error: ProvenanceHttpError
    ) -> JSONResponse:
        del request
        return JSONResponse(
            status_code=error.problem.status,
            content=error.problem.model_dump(mode="json"),
            media_type="application/problem+json",
            headers={"Cache-Control": "no-store"},
        )

    @application.exception_handler(RequestValidationError)
    async def provenance_validation_error_handler(
        request: Request, error: RequestValidationError
    ) -> JSONResponse:
        if not request.url.path.startswith("/api/v1/provenance"):
            return cast(JSONResponse, await previous_validation_handler(request, error))
        context = getattr(request.state, "security_context", None)
        if not isinstance(context, SecurityContext):
            return await request_validation_exception_handler(request, error)
        problem = _translate(context, ValueError("invalid query")).problem
        return JSONResponse(
            status_code=problem.status,
            content=problem.model_dump(mode="json"),
            media_type="application/problem+json",
            headers={"Cache-Control": "no-store"},
        )

    responses: dict[int | str, dict[str, Any]] = {
        401: {"description": "Authentication required."},
        403: {"model": ProvenanceProblem},
        404: {"model": ProvenanceProblem},
        409: {"model": ProvenanceProblem},
        422: {"model": ProvenanceProblem},
        503: {"model": ProvenanceProblem},
    }

    @application.get(
        "/api/v1/provenance/entities/{entity_id}",
        operation_id="getProvenanceEntity",
        response_model=ProvenanceEntityResponse,
        responses=responses,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["provenance"],
        summary="Read one immutable provenance Entity and completeness status.",
    )
    def get_entity(request: Request, entity_id: UUID) -> ProvenanceEntityResponse:
        context, decision = _request_scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            record = service.get_entity(context, decision, entity_id)
        except ProvenanceError as error:
            raise _translate(context, error) from error
        return ProvenanceEntityResponse.from_record(record)

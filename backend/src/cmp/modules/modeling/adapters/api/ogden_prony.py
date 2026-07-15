"""Protected API for the bounded Ogden-Prony reference IR."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends, FastAPI, Request, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from cmp.modules.identity_access.domain.authorization import AuthorizationDecision
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.modeling.application.ogden_prony import (
    CreateReferenceOgdenPronyModel,
    OgdenPronyModelService,
    OgdenPronyModelSnapshot,
)
from cmp.modules.modeling.domain.reference_ogden_prony import (
    InvalidReferenceOgdenProny,
    ReferenceOgdenPronyConflict,
    ReferenceOgdenPronyNotFound,
    ReferenceShearPronyTerm,
)
from cmp.shared.contracts.revisions import RevisionETag, RevisionMetadataResponse

type Dependency = Callable[..., object]
type Reason = Annotated[str, StringConstraints(min_length=1, max_length=2000)]


class OgdenPronyTermRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    g_ratio: Annotated[float, Field(gt=0, lt=1)]
    relaxation_time_s: Annotated[float, Field(gt=0)]


class OgdenPronyCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    property_set_revision_id: UUID
    ogden_mu_pa: Annotated[float, Field(gt=0)]
    ogden_alpha: Annotated[float, Field(gt=0)]
    prony_terms: Annotated[tuple[OgdenPronyTermRequest, ...], Field(min_length=1, max_length=5)]
    change_reason: Reason


class OgdenPronyRevisionResponse(RevisionMetadataResponse):
    content: dict[str, object]


class OgdenPronyModelResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    material_model_id: UUID
    material_state_id: UUID
    current_revision: OgdenPronyRevisionResponse
    links: dict[str, str]

    @classmethod
    def from_snapshot(cls, value: OgdenPronyModelSnapshot) -> OgdenPronyModelResponse:
        metadata = RevisionMetadataResponse.from_record(value.current.record, "draft")
        root = f"/api/v1/ogden-prony-models/{value.id}"
        return cls(
            material_model_id=value.id,
            material_state_id=value.material_state_id,
            current_revision=OgdenPronyRevisionResponse(
                **metadata.model_dump(), content=value.current.content.canonical()
            ),
            links={"self": root, "solver_cards": f"{root}/solver-cards"},
        )


class OgdenPronyListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: tuple[OgdenPronyModelResponse, ...]


class OgdenPronyProblem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    title: str
    status: int
    detail: str
    code: str
    trace_id: str


class OgdenPronyHttpError(Exception):
    def __init__(self, context: SecurityContext, status_code: int, detail: str) -> None:
        self.problem = OgdenPronyProblem(
            type="urn:cmp:problem:modeling:ogden-prony",
            title="Ogden-Prony Material Model request failed",
            status=status_code,
            detail=detail,
            code=f"CMP-MODELING-{status_code}",
            trace_id=context.trace_id,
        )


def _scope(request: Request) -> tuple[SecurityContext, AuthorizationDecision]:
    return request.state.security_context, request.state.authorization_decision


def _translate(context: SecurityContext, error: Exception) -> OgdenPronyHttpError:
    if isinstance(error, ReferenceOgdenPronyNotFound):
        return OgdenPronyHttpError(context, 404, str(error))
    if isinstance(error, ReferenceOgdenPronyConflict):
        return OgdenPronyHttpError(context, 409, str(error))
    if isinstance(error, (InvalidReferenceOgdenProny, ValueError)):
        return OgdenPronyHttpError(context, 422, str(error))
    return OgdenPronyHttpError(context, 503, "service is unavailable")


def install_ogden_prony_api(
    application: FastAPI,
    *,
    service: OgdenPronyModelService | None,
    security_dependency: Dependency,
    read_dependency: Dependency,
    write_dependency: Dependency,
) -> None:
    @application.exception_handler(OgdenPronyHttpError)
    async def handle_error(_: Request, error: OgdenPronyHttpError) -> JSONResponse:
        return JSONResponse(error.problem.model_dump(mode="json"), status_code=error.problem.status)

    errors: dict[int | str, dict[str, Any]] = {
        code: {"model": OgdenPronyProblem} for code in (404, 409, 422, 503)
    }

    @application.post(
        "/api/v1/material-states/{material_state_id}/ogden-prony-models",
        operation_id="createOgdenPronyModel",
        response_model=OgdenPronyModelResponse,
        status_code=status.HTTP_201_CREATED,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(write_dependency)],
        tags=["modeling"],
    )
    def create_model(
        request: Request,
        response: Response,
        material_state_id: UUID,
        body: OgdenPronyCreateRequest,
    ) -> OgdenPronyModelResponse:
        context, decision = _scope(request)
        if service is None:
            raise OgdenPronyHttpError(context, 503, "service is unavailable")
        try:
            snapshot = service.create_model(
                context,
                decision,
                CreateReferenceOgdenPronyModel(
                    material_state_id,
                    body.property_set_revision_id,
                    body.ogden_mu_pa,
                    body.ogden_alpha,
                    tuple(
                        ReferenceShearPronyTerm(term.g_ratio, term.relaxation_time_s)
                        for term in body.prony_terms
                    ),
                    body.change_reason,
                ),
            )
        except Exception as error:
            raise _translate(context, error) from error
        response.headers["ETag"] = str(RevisionETag.from_ref(snapshot.current.record.ref))
        response.headers["Location"] = f"/api/v1/ogden-prony-models/{snapshot.id}"
        return OgdenPronyModelResponse.from_snapshot(snapshot)

    @application.get(
        "/api/v1/material-states/{material_state_id}/ogden-prony-models",
        operation_id="listOgdenPronyModels",
        response_model=OgdenPronyListResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["modeling"],
    )
    def list_models(request: Request, material_state_id: UUID) -> OgdenPronyListResponse:
        context, decision = _scope(request)
        if service is None:
            raise OgdenPronyHttpError(context, 503, "service is unavailable")
        try:
            values = service.list_models_for_state(context, decision, material_state_id)
        except Exception as error:
            raise _translate(context, error) from error
        return OgdenPronyListResponse(
            items=tuple(OgdenPronyModelResponse.from_snapshot(value) for value in values)
        )

    @application.get(
        "/api/v1/ogden-prony-models/{material_model_id}",
        operation_id="getOgdenPronyModel",
        response_model=OgdenPronyModelResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["modeling"],
    )
    def get_model(
        request: Request, response: Response, material_model_id: UUID
    ) -> OgdenPronyModelResponse:
        context, decision = _scope(request)
        if service is None:
            raise OgdenPronyHttpError(context, 503, "service is unavailable")
        try:
            snapshot = service.get_model(context, decision, material_model_id)
        except Exception as error:
            raise _translate(context, error) from error
        response.headers["ETag"] = str(RevisionETag.from_ref(snapshot.current.record.ref))
        return OgdenPronyModelResponse.from_snapshot(snapshot)

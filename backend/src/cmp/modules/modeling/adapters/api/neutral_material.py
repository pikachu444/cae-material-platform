"""HTTP contract for T-56 Neutral Material promotion, validation, and download."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends, FastAPI, Request, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from cmp.modules.identity_access.domain.authorization import AuthorizationDecision
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.modeling.application.neutral_material import (
    ImportNeutralMaterial,
    NeutralMaterialConflict,
    NeutralMaterialNotFound,
    NeutralMaterialService,
    NeutralMaterialSnapshot,
    PromoteHyperelasticFamilyCandidate,
)
from cmp.modules.modeling.domain.neutral_material import InvalidNeutralMaterial
from cmp.shared.domain.revisions import AggregateAlreadyExists

logger = logging.getLogger(__name__)


type Dependency = Callable[..., object]


class PromoteNeutralMaterialRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: UUID
    selection_reason: Annotated[str, Field(min_length=1, max_length=2000)]
    change_reason: Annotated[str, Field(min_length=1, max_length=2000)]


class ImportNeutralMaterialRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document: dict[str, Any]
    change_reason: Annotated[str, Field(min_length=1, max_length=2000)]


class ArtifactPointerResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact_id: UUID
    sha256: str


class NeutralMaterialResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    neutral_material_id: UUID
    neutral_material_revision_id: UUID
    revision_no: int
    content_hash: str
    document_artifact: ArtifactPointerResponse
    document: dict[str, Any]
    links: dict[str, str]

    @classmethod
    def from_snapshot(cls, value: NeutralMaterialSnapshot) -> NeutralMaterialResponse:
        root = f"/api/v1/neutral-materials/{value.id}"
        return cls(
            neutral_material_id=value.id,
            neutral_material_revision_id=value.current.revision_id,
            revision_no=value.current.revision_no,
            content_hash=value.current.content_hash,
            document_artifact=ArtifactPointerResponse(
                artifact_id=value.document_artifact_id,
                sha256=value.document_artifact_sha256,
            ),
            document=value.document.canonical(),
            links={"self": root, "download": f"{root}/download"},
        )


class NeutralMaterialValidationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    valid: bool
    document_id: UUID
    content_sha256: str
    family: str
    source_dataset_count: int
    curve_stage_count: int


class NeutralMaterialProblem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    title: str
    status: int
    detail: str
    code: str
    trace_id: str


class NeutralMaterialHttpError(Exception):
    def __init__(self, context: SecurityContext, status_code: int, detail: str) -> None:
        self.problem = NeutralMaterialProblem(
            type="urn:cmp:problem:modeling:neutral-material",
            title="Neutral Material request failed",
            status=status_code,
            detail=detail,
            code=f"CMP-NEUTRAL-{status_code}",
            trace_id=context.trace_id,
        )
        super().__init__(detail)


def _scope(request: Request) -> tuple[SecurityContext, AuthorizationDecision]:
    context = getattr(request.state, "security_context", None)
    decision = getattr(request.state, "authorization_decision", None)
    if not isinstance(context, SecurityContext) or not isinstance(decision, AuthorizationDecision):
        raise RuntimeError("Neutral Material dependencies did not initialize request scope")
    return context, decision


def _translate(context: SecurityContext, error: Exception) -> NeutralMaterialHttpError:
    if isinstance(error, NeutralMaterialNotFound):
        return NeutralMaterialHttpError(context, 404, str(error))
    if isinstance(error, (NeutralMaterialConflict, AggregateAlreadyExists)):
        return NeutralMaterialHttpError(context, 409, str(error))
    if isinstance(error, (InvalidNeutralMaterial, ValueError)):
        return NeutralMaterialHttpError(context, 422, str(error))
    logger.exception("unexpected Neutral Material API failure", exc_info=error)
    return NeutralMaterialHttpError(context, 503, "service is unavailable")


def install_neutral_material_api(
    application: FastAPI,
    *,
    service: NeutralMaterialService | None,
    security_dependency: Dependency,
    read_dependency: Dependency,
    write_dependency: Dependency,
) -> None:
    @application.exception_handler(NeutralMaterialHttpError)
    async def handle_error(_: Request, error: NeutralMaterialHttpError) -> JSONResponse:
        return JSONResponse(error.problem.model_dump(mode="json"), status_code=error.problem.status)

    errors: dict[int | str, dict[str, Any]] = {
        code: {"model": NeutralMaterialProblem} for code in (404, 409, 422, 503)
    }

    @application.post(
        "/api/v1/neutral-materials:promote",
        operation_id="promoteHyperelasticCandidateToNeutralMaterial",
        response_model=NeutralMaterialResponse,
        status_code=status.HTTP_201_CREATED,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(write_dependency)],
        tags=["modeling"],
    )
    async def promote(
        request: Request,
        response: Response,
        body: PromoteNeutralMaterialRequest,
    ) -> NeutralMaterialResponse:
        context, decision = _scope(request)
        if service is None:
            raise NeutralMaterialHttpError(context, 503, "service is unavailable")
        try:
            value = await service.promote_family_candidate(
                context,
                decision,
                PromoteHyperelasticFamilyCandidate(
                    candidate_id=body.candidate_id,
                    selection_reason=body.selection_reason,
                    change_reason=body.change_reason,
                ),
            )
        except Exception as error:
            raise _translate(context, error) from error
        response.headers["Location"] = f"/api/v1/neutral-materials/{value.id}"
        return NeutralMaterialResponse.from_snapshot(value)

    @application.post(
        "/api/v1/neutral-materials:import",
        operation_id="importNeutralMaterial",
        response_model=NeutralMaterialResponse,
        status_code=status.HTTP_201_CREATED,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(write_dependency)],
        tags=["modeling"],
    )
    async def import_document(
        request: Request,
        response: Response,
        body: ImportNeutralMaterialRequest,
    ) -> NeutralMaterialResponse:
        context, decision = _scope(request)
        if service is None:
            raise NeutralMaterialHttpError(context, 503, "service is unavailable")
        try:
            value = await service.import_neutral_material(
                context,
                decision,
                ImportNeutralMaterial(
                    value=json.dumps(body.document, sort_keys=True, separators=(",", ":")).encode(
                        "utf-8"
                    ),
                    change_reason=body.change_reason,
                ),
            )
        except Exception as error:
            raise _translate(context, error) from error
        response.headers["Location"] = f"/api/v1/neutral-materials/{value.id}"
        return NeutralMaterialResponse.from_snapshot(value)

    @application.get(
        "/api/v1/neutral-materials/{neutral_material_id}",
        operation_id="getNeutralMaterial",
        response_model=NeutralMaterialResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["modeling"],
    )
    async def get_neutral_material(
        request: Request, neutral_material_id: UUID
    ) -> NeutralMaterialResponse:
        context, decision = _scope(request)
        if service is None:
            raise NeutralMaterialHttpError(context, 503, "service is unavailable")
        try:
            value = await service.get_neutral_material(context, decision, neutral_material_id)
        except Exception as error:
            raise _translate(context, error) from error
        return NeutralMaterialResponse.from_snapshot(value)

    @application.get(
        "/api/v1/neutral-materials/{neutral_material_id}/download",
        operation_id="downloadNeutralMaterial",
        responses={
            200: {
                "description": "Canonical cmp.neutral-material JSON",
                "content": {"application/json": {}},
            },
            **errors,
        },
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["modeling"],
    )
    async def download(request: Request, neutral_material_id: UUID) -> Response:
        context, decision = _scope(request)
        if service is None:
            raise NeutralMaterialHttpError(context, 503, "service is unavailable")
        try:
            value = await service.get_neutral_material(context, decision, neutral_material_id)
        except Exception as error:
            raise _translate(context, error) from error
        return Response(
            value.document.to_json_bytes(),
            media_type="application/json",
            headers={
                "Content-Disposition": (
                    f'attachment; filename="neutral-material-{neutral_material_id}.json"'
                ),
                "X-Content-SHA256": value.document.content_sha256,
            },
        )

    @application.post(
        "/api/v1/neutral-materials:validate",
        operation_id="validateNeutralMaterial",
        response_model=NeutralMaterialValidationResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["modeling"],
    )
    def validate(request: Request, body: dict[str, Any]) -> NeutralMaterialValidationResponse:
        context, _decision = _scope(request)
        if service is None:
            raise NeutralMaterialHttpError(context, 503, "service is unavailable")
        try:
            document = service.validate_json(
                json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
            )
        except Exception as error:
            raise _translate(context, error) from error
        return NeutralMaterialValidationResponse(
            valid=True,
            document_id=document.document_id,
            content_sha256=document.content_sha256,
            family=document.material_model_ir.parameters.family.value,
            source_dataset_count=len(document.source_datasets),
            curve_stage_count=len(document.curves),
        )

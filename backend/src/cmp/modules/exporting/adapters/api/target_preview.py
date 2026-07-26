"""HTTP adapter for the non-persistent UXC-06C1 target preview."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from cmp.modules.exporting.application.target_preview import (
    CreateTargetPreview,
    TargetPreview,
    TargetPreviewConflict,
    TargetPreviewService,
)
from cmp.modules.exporting.domain.neutral_hyperelastic import NeutralHyperelasticExportTarget
from cmp.modules.identity_access.domain.authorization import AuthorizationDecision
from cmp.modules.identity_access.domain.security import SecurityContext

type Dependency = Callable[..., object]
type Sha256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]


class TargetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    solver: str
    version: str
    unit_system: str


class TargetPreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    processing_output_id: UUID
    processing_output_revision_id: UUID
    neutral_material_id: UUID
    neutral_material_revision_id: UUID
    target: TargetRequest
    solver_material_id: Annotated[int, Field(ge=1, le=9_999_999_999)]
    material_name: Annotated[str, StringConstraints(pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,79}$")]
    expected_mapping_report_sha256: Annotated[
        str | None, StringConstraints(pattern=r"^[0-9a-f]{64}$")
    ] = None


class TargetPreviewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    preview_identity: Sha256
    filename: str
    native_text: str
    native_sha256: Sha256
    mapping_report_sha256: Sha256
    mapping: TargetPreviewMappingResponse
    source: TargetPreviewSourceResponse
    target: TargetPreviewTargetResponse
    acknowledgement_identity: Sha256 | None
    non_production: bool
    delivery_status: str

    @classmethod
    def from_domain(cls, preview: TargetPreview) -> TargetPreviewResponse:
        return cls(
            preview_identity=preview.preview_identity,
            filename=preview.filename,
            native_text=preview.native_text,
            native_sha256=preview.native_sha256,
            mapping_report_sha256=preview.mapping_report_sha256,
            mapping=TargetPreviewMappingResponse.model_validate(preview.mapping),
            source=TargetPreviewSourceResponse.model_validate(preview.source),
            target=TargetPreviewTargetResponse.model_validate(preview.target),
            acknowledgement_identity=preview.acknowledgement_identity,
            non_production=preview.non_production,
            delivery_status=preview.delivery_status,
        )


class TargetPreviewMappingItemResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    ir_path: str
    target_representation: str | None
    status: str
    detail: str


class TargetPreviewMappingResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    items: list[TargetPreviewMappingItemResponse]


class TargetPreviewSourceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    processing_output_id: UUID
    processing_output_revision_id: UUID
    processing_output_sha256: Sha256
    material_id: UUID
    material_revision_id: UUID
    material_state_id: UUID
    material_state_revision_id: UUID
    material_model_ir_revision_id: UUID
    neutral_material_id: UUID
    neutral_material_revision_id: UUID


class TargetPreviewTargetResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    solver: str
    version: str
    unit_system: str
    solver_material_id: int
    material_name: str


class PreviewProblem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: str
    title: str
    status: int
    detail: str
    code: str
    trace_id: str


class PreviewHttpError(Exception):
    def __init__(self, context: SecurityContext, status: int, detail: str) -> None:
        self.problem = PreviewProblem(
            type="urn:cmp:problem:exporting:target-preview",
            title="Target preview request failed",
            status=status,
            detail=detail,
            code=f"CMP-TARGET-PREVIEW-{status}",
            trace_id=context.trace_id,
        )


def install_target_preview_api(
    application: FastAPI,
    *,
    service: TargetPreviewService | None,
    security_dependency: Dependency,
    read_dependency: Dependency,
) -> None:
    @application.exception_handler(PreviewHttpError)
    async def error_handler(_: Request, error: PreviewHttpError) -> JSONResponse:
        return JSONResponse(error.problem.model_dump(), status_code=error.problem.status)

    @application.post(
        "/api/v1/exporting/target-previews",
        operation_id="createExactTargetPreview",
        response_model=TargetPreviewResponse,
        responses={code: {"model": PreviewProblem} for code in (409, 422, 503)},
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["exporting"],
    )
    async def create_preview(request: Request, body: TargetPreviewRequest) -> TargetPreviewResponse:
        context: SecurityContext = request.state.security_context
        decision: AuthorizationDecision = request.state.authorization_decision
        if service is None:
            raise PreviewHttpError(
                context, 503, "exact target-preview source resolver is unavailable"
            )
        try:
            preview = await service.preview(
                context,
                decision,
                CreateTargetPreview(
                    processing_output_id=body.processing_output_id,
                    processing_output_revision_id=body.processing_output_revision_id,
                    neutral_material_id=body.neutral_material_id,
                    neutral_material_revision_id=body.neutral_material_revision_id,
                    target=NeutralHyperelasticExportTarget(
                        body.target.solver, body.target.version, body.target.unit_system
                    ),
                    solver_material_id=body.solver_material_id,
                    material_name=body.material_name,
                    expected_mapping_report_sha256=body.expected_mapping_report_sha256,
                ),
            )
        except TargetPreviewConflict as error:
            raise PreviewHttpError(context, 409, str(error)) from error
        except ValueError as error:
            raise PreviewHttpError(context, 422, str(error)) from error
        return TargetPreviewResponse.from_domain(preview)

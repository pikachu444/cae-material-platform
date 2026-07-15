"""Protected preflight, preview, and download API for Ogden-Prony cards."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends, FastAPI, Request, Response, status
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from cmp.modules.exporting.application.ogden_prony_service import (
    CreateReferenceOgdenPronySolverCard,
    OgdenPronySolverCardService,
    OgdenPronySolverCardSnapshot,
)
from cmp.modules.exporting.domain.reference_ogden_prony import (
    InvalidOgdenPronyExport,
    OgdenPronyExportTarget,
    OgdenPronyMappingReport,
    OgdenPronyMappingReportMismatch,
    OgdenPronySolverCardConflict,
    OgdenPronySolverCardNotFound,
)
from cmp.modules.identity_access.domain.authorization import AuthorizationDecision
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.modeling.domain.reference_ogden_prony import ReferenceOgdenPronyConflict
from cmp.shared.contracts.revisions import RevisionETag, RevisionMetadataResponse

type Dependency = Callable[..., object]
type Reason = Annotated[str, StringConstraints(min_length=1, max_length=2000)]


class TargetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    solver: str
    version: str = "2025"
    unit_system: str = "kg_m_s"

    def domain(self) -> OgdenPronyExportTarget:
        return OgdenPronyExportTarget(self.solver, self.version, self.unit_system)


class PreflightRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    material_model_revision_id: UUID
    target: TargetRequest


class CreateCardRequest(PreflightRequest):
    expected_mapping_report_sha256: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
    solver_material_id: Annotated[int, Field(ge=1, le=9_999_999_999)]
    material_name: Annotated[str, StringConstraints(pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,79}$")]
    change_reason: Reason


class OgdenPronyMappingReportResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mapping_report_sha256: str
    exportable: bool
    report: dict[str, object]

    @classmethod
    def from_domain(cls, value: OgdenPronyMappingReport) -> OgdenPronyMappingReportResponse:
        return cls(
            mapping_report_sha256=value.digest,
            exportable=value.exportable,
            report=value.canonical(),
        )


class CardRevisionResponse(RevisionMetadataResponse):
    content: dict[str, object]


class CardResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    solver_card_id: UUID
    material_model_id: UUID
    target: TargetRequest
    current_revision: CardRevisionResponse
    links: dict[str, str]

    @classmethod
    def from_snapshot(cls, value: OgdenPronySolverCardSnapshot) -> CardResponse:
        metadata = RevisionMetadataResponse.from_record(value.current.record, "draft")
        root = f"/api/v1/ogden-prony-solver-cards/{value.id}"
        return cls(
            solver_card_id=value.id,
            material_model_id=value.material_model_id,
            target=TargetRequest(
                solver=value.target.solver,
                version=value.target.version,
                unit_system=value.target.unit_system,
            ),
            current_revision=CardRevisionResponse(
                **metadata.model_dump(), content=value.current.content.canonical()
            ),
            links={"self": root, "preview": f"{root}/preview", "download": f"{root}/download"},
        )


class CardListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: tuple[CardResponse, ...]


class ExportProblem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    title: str
    status: int
    detail: str
    code: str
    trace_id: str


class ExportHttpError(Exception):
    def __init__(self, context: SecurityContext, status_code: int, detail: str) -> None:
        self.problem = ExportProblem(
            type="urn:cmp:problem:exporting:ogden-prony",
            title="Ogden-Prony Solver Card request failed",
            status=status_code,
            detail=detail,
            code=f"CMP-EXPORT-{status_code}",
            trace_id=context.trace_id,
        )


def _scope(request: Request) -> tuple[SecurityContext, AuthorizationDecision]:
    return request.state.security_context, request.state.authorization_decision


def _translate(context: SecurityContext, error: Exception) -> ExportHttpError:
    if isinstance(error, OgdenPronySolverCardNotFound):
        return ExportHttpError(context, 404, str(error))
    if isinstance(
        error,
        (
            OgdenPronyMappingReportMismatch,
            OgdenPronySolverCardConflict,
            ReferenceOgdenPronyConflict,
        ),
    ):
        return ExportHttpError(context, 409, str(error))
    if isinstance(error, (InvalidOgdenPronyExport, ValueError)):
        return ExportHttpError(context, 422, str(error))
    return ExportHttpError(context, 503, "service is unavailable")


def install_ogden_prony_solver_card_api(
    application: FastAPI,
    *,
    service: OgdenPronySolverCardService | None,
    security_dependency: Dependency,
    read_dependency: Dependency,
    execute_dependency: Dependency,
) -> None:
    @application.exception_handler(ExportHttpError)
    async def handle_error(_: Request, error: ExportHttpError) -> JSONResponse:
        return JSONResponse(error.problem.model_dump(mode="json"), status_code=error.problem.status)

    errors: dict[int | str, dict[str, Any]] = {
        code: {"model": ExportProblem} for code in (404, 409, 422, 503)
    }

    @application.post(
        "/api/v1/ogden-prony-models/{material_model_id}/solver-card-preflight",
        operation_id="preflightOgdenPronySolverCard",
        response_model=OgdenPronyMappingReportResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["exporting"],
    )
    def preflight(
        request: Request, material_model_id: UUID, body: PreflightRequest
    ) -> OgdenPronyMappingReportResponse:
        context, decision = _scope(request)
        if service is None:
            raise ExportHttpError(context, 503, "service is unavailable")
        try:
            report = service.preflight(
                context,
                decision,
                material_model_id=material_model_id,
                material_model_revision_id=body.material_model_revision_id,
                target=body.target.domain(),
            )
        except Exception as error:
            raise _translate(context, error) from error
        return OgdenPronyMappingReportResponse.from_domain(report)

    @application.post(
        "/api/v1/ogden-prony-models/{material_model_id}/solver-cards",
        operation_id="createOgdenPronySolverCard",
        response_model=CardResponse,
        status_code=status.HTTP_201_CREATED,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(execute_dependency)],
        tags=["exporting"],
    )
    def create_card(
        request: Request,
        response: Response,
        material_model_id: UUID,
        body: CreateCardRequest,
    ) -> CardResponse:
        context, decision = _scope(request)
        if service is None:
            raise ExportHttpError(context, 503, "service is unavailable")
        try:
            snapshot, _ = service.create_card(
                context,
                decision,
                CreateReferenceOgdenPronySolverCard(
                    material_model_id,
                    body.material_model_revision_id,
                    body.target.domain(),
                    body.expected_mapping_report_sha256,
                    body.solver_material_id,
                    body.material_name,
                    body.change_reason,
                ),
            )
        except Exception as error:
            raise _translate(context, error) from error
        response.headers["ETag"] = str(RevisionETag.from_ref(snapshot.current.record.ref))
        response.headers["Location"] = f"/api/v1/ogden-prony-solver-cards/{snapshot.id}"
        return CardResponse.from_snapshot(snapshot)

    @application.get(
        "/api/v1/ogden-prony-models/{material_model_id}/solver-cards",
        operation_id="listOgdenPronySolverCards",
        response_model=CardListResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["exporting"],
    )
    def list_cards(request: Request, material_model_id: UUID) -> CardListResponse:
        context, decision = _scope(request)
        if service is None:
            raise ExportHttpError(context, 503, "service is unavailable")
        try:
            values = service.list_cards_for_model(context, decision, material_model_id)
        except Exception as error:
            raise _translate(context, error) from error
        return CardListResponse(items=tuple(CardResponse.from_snapshot(value) for value in values))

    def _get(request: Request, solver_card_id: UUID) -> OgdenPronySolverCardSnapshot:
        context, decision = _scope(request)
        if service is None:
            raise ExportHttpError(context, 503, "service is unavailable")
        try:
            return service.get_card(context, decision, solver_card_id)
        except Exception as error:
            raise _translate(context, error) from error

    @application.get(
        "/api/v1/ogden-prony-solver-cards/{solver_card_id}",
        operation_id="getOgdenPronySolverCard",
        response_model=CardResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["exporting"],
    )
    def get_card(request: Request, solver_card_id: UUID) -> CardResponse:
        return CardResponse.from_snapshot(_get(request, solver_card_id))

    @application.get(
        "/api/v1/ogden-prony-solver-cards/{solver_card_id}/preview",
        operation_id="previewOgdenPronySolverCard",
        response_class=PlainTextResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["exporting"],
    )
    def preview(request: Request, solver_card_id: UUID) -> PlainTextResponse:
        snapshot = _get(request, solver_card_id)
        return PlainTextResponse(snapshot.current.content.card_text)

    @application.get(
        "/api/v1/ogden-prony-solver-cards/{solver_card_id}/download",
        operation_id="downloadOgdenPronySolverCard",
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["exporting"],
    )
    def download(request: Request, solver_card_id: UUID) -> Response:
        snapshot = _get(request, solver_card_id)
        suffix = "inp" if snapshot.target.is_abaqus else "rad"
        filename = f"{snapshot.material_name}-{snapshot.id}.{suffix}"
        return Response(
            content=snapshot.current.content.card_text,
            media_type="text/plain; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "X-CMP-Card-Sha256": snapshot.current.content.card_sha256,
            },
        )

"""Protected Neutral Material preflight, mapping-report, preview and download API."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends, FastAPI, Request, Response, status
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from cmp.modules.exporting.application.neutral_hyperelastic_service import (
    CreateNeutralHyperelasticSolverCard,
    NeutralHyperelasticSolverCardService,
    NeutralHyperelasticSolverCardSnapshot,
)
from cmp.modules.exporting.domain.neutral_hyperelastic import (
    InvalidNeutralHyperelasticExport,
    NeutralHyperelasticExportTarget,
    NeutralHyperelasticMappingReport,
    NeutralHyperelasticMappingReportMismatch,
    NeutralHyperelasticSolverCardConflict,
    NeutralHyperelasticSolverCardNotFound,
    neutral_hyperelastic_capability_manifest,
)
from cmp.modules.identity_access.domain.authorization import AuthorizationDecision
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.modeling.application.neutral_material import (
    NeutralMaterialConflict,
    NeutralMaterialNotFound,
)
from cmp.shared.contracts.revisions import RevisionETag, RevisionMetadataResponse

type Dependency = Callable[..., object]
type Reason = Annotated[str, StringConstraints(min_length=1, max_length=2000)]


class TargetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    solver: str
    version: str = "2025"
    unit_system: str = "kg_m_s"

    def domain(self) -> NeutralHyperelasticExportTarget:
        return NeutralHyperelasticExportTarget(self.solver, self.version, self.unit_system)


class PreflightRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    neutral_material_revision_id: UUID
    target: TargetRequest


class CreateCardRequest(PreflightRequest):
    expected_mapping_report_sha256: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
    solver_material_id: Annotated[int, Field(ge=1, le=9_999_999_999)]
    material_name: Annotated[str, StringConstraints(pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,79}$")]
    change_reason: Reason


class NeutralHyperelasticMappingReportResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mapping_report_sha256: str
    exportable: bool
    report: dict[str, object]

    @classmethod
    def from_domain(
        cls, value: NeutralHyperelasticMappingReport
    ) -> NeutralHyperelasticMappingReportResponse:
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
    neutral_material_id: UUID
    target: TargetRequest
    current_revision: CardRevisionResponse
    links: dict[str, str]

    @classmethod
    def from_snapshot(cls, value: NeutralHyperelasticSolverCardSnapshot) -> CardResponse:
        metadata = RevisionMetadataResponse.from_record(value.current.record, "draft")
        root = f"/api/v1/neutral-hyperelastic-solver-cards/{value.id}"
        return cls(
            solver_card_id=value.id,
            neutral_material_id=value.neutral_material_id,
            target=TargetRequest(
                solver=value.target.solver,
                version=value.target.version,
                unit_system=value.target.unit_system,
            ),
            current_revision=CardRevisionResponse(
                **metadata.model_dump(), content=value.current.content.canonical()
            ),
            links={
                "self": root,
                "mapping_report": f"{root}/mapping-report",
                "preview": f"{root}/preview",
                "download": f"{root}/download",
            },
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
            type="urn:cmp:problem:exporting:neutral-hyperelastic",
            title="Neutral Material Solver Card request failed",
            status=status_code,
            detail=detail,
            code=f"CMP-EXPORT-{status_code}",
            trace_id=context.trace_id,
        )


def _scope(request: Request) -> tuple[SecurityContext, AuthorizationDecision]:
    return request.state.security_context, request.state.authorization_decision


def _translate(context: SecurityContext, error: Exception) -> ExportHttpError:
    if isinstance(error, (NeutralHyperelasticSolverCardNotFound, NeutralMaterialNotFound)):
        return ExportHttpError(context, 404, str(error))
    if isinstance(
        error,
        (
            NeutralHyperelasticMappingReportMismatch,
            NeutralHyperelasticSolverCardConflict,
            NeutralMaterialConflict,
        ),
    ):
        return ExportHttpError(context, 409, str(error))
    if isinstance(error, (InvalidNeutralHyperelasticExport, ValueError)):
        return ExportHttpError(context, 422, str(error))
    return ExportHttpError(context, 503, "service is unavailable")


def install_neutral_hyperelastic_solver_card_api(
    application: FastAPI,
    *,
    service: NeutralHyperelasticSolverCardService | None,
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

    @application.get(
        "/api/v1/neutral-hyperelastic-export-capabilities",
        operation_id="getNeutralHyperelasticExportCapabilities",
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["exporting"],
    )
    def capabilities() -> dict[str, object]:
        return neutral_hyperelastic_capability_manifest()

    @application.post(
        "/api/v1/neutral-materials/{neutral_material_id}/solver-card-preflight",
        operation_id="preflightNeutralHyperelasticSolverCard",
        response_model=NeutralHyperelasticMappingReportResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["exporting"],
    )
    async def preflight(
        request: Request, neutral_material_id: UUID, body: PreflightRequest
    ) -> NeutralHyperelasticMappingReportResponse:
        context, decision = _scope(request)
        if service is None:
            raise ExportHttpError(context, 503, "service is unavailable")
        try:
            report = await service.preflight(
                context,
                decision,
                neutral_material_id=neutral_material_id,
                neutral_material_revision_id=body.neutral_material_revision_id,
                target=body.target.domain(),
            )
        except Exception as error:
            raise _translate(context, error) from error
        return NeutralHyperelasticMappingReportResponse.from_domain(report)

    @application.post(
        "/api/v1/neutral-materials/{neutral_material_id}/solver-cards",
        operation_id="createNeutralHyperelasticSolverCard",
        response_model=CardResponse,
        status_code=status.HTTP_201_CREATED,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(execute_dependency)],
        tags=["exporting"],
    )
    async def create_card(
        request: Request,
        response: Response,
        neutral_material_id: UUID,
        body: CreateCardRequest,
    ) -> CardResponse:
        context, decision = _scope(request)
        if service is None:
            raise ExportHttpError(context, 503, "service is unavailable")
        try:
            snapshot, _ = await service.create_card(
                context,
                decision,
                CreateNeutralHyperelasticSolverCard(
                    neutral_material_id,
                    body.neutral_material_revision_id,
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
        response.headers["Location"] = f"/api/v1/neutral-hyperelastic-solver-cards/{snapshot.id}"
        return CardResponse.from_snapshot(snapshot)

    @application.get(
        "/api/v1/neutral-materials/{neutral_material_id}/solver-cards",
        operation_id="listNeutralHyperelasticSolverCards",
        response_model=CardListResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["exporting"],
    )
    def list_cards(request: Request, neutral_material_id: UUID) -> CardListResponse:
        context, decision = _scope(request)
        if service is None:
            raise ExportHttpError(context, 503, "service is unavailable")
        try:
            values = service.list_cards(context, decision, neutral_material_id)
        except Exception as error:
            raise _translate(context, error) from error
        return CardListResponse(items=tuple(CardResponse.from_snapshot(value) for value in values))

    def _get(request: Request, solver_card_id: UUID) -> NeutralHyperelasticSolverCardSnapshot:
        context, decision = _scope(request)
        if service is None:
            raise ExportHttpError(context, 503, "service is unavailable")
        try:
            return service.get_card(context, decision, solver_card_id)
        except Exception as error:
            raise _translate(context, error) from error

    @application.get(
        "/api/v1/neutral-hyperelastic-solver-cards/{solver_card_id}",
        operation_id="getNeutralHyperelasticSolverCard",
        response_model=CardResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["exporting"],
    )
    def get_card(request: Request, solver_card_id: UUID) -> CardResponse:
        return CardResponse.from_snapshot(_get(request, solver_card_id))

    @application.get(
        "/api/v1/neutral-hyperelastic-solver-cards/{solver_card_id}/mapping-report",
        operation_id="getNeutralHyperelasticMappingReport",
        response_model=NeutralHyperelasticMappingReportResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["exporting"],
    )
    async def mapping_report(
        request: Request, solver_card_id: UUID
    ) -> NeutralHyperelasticMappingReportResponse:
        context, decision = _scope(request)
        if service is None:
            raise ExportHttpError(context, 503, "service is unavailable")
        try:
            report = await service.mapping_report(context, decision, solver_card_id)
        except Exception as error:
            raise _translate(context, error) from error
        return NeutralHyperelasticMappingReportResponse.from_domain(report)

    @application.get(
        "/api/v1/neutral-hyperelastic-solver-cards/{solver_card_id}/preview",
        operation_id="previewNeutralHyperelasticSolverCard",
        response_class=PlainTextResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["exporting"],
    )
    def preview(request: Request, solver_card_id: UUID) -> PlainTextResponse:
        return PlainTextResponse(_get(request, solver_card_id).current.content.card_text)

    @application.get(
        "/api/v1/neutral-hyperelastic-solver-cards/{solver_card_id}/download",
        operation_id="downloadNeutralHyperelasticSolverCard",
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
                "X-CMP-Mapping-Report-Sha256": (snapshot.current.content.mapping_report_sha256),
            },
        )

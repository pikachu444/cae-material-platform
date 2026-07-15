"""HTTP mapping, preview, and download for the Abaqus reference linear-Prony card."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends, FastAPI, Request, Response, status
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from sqlalchemy.exc import IntegrityError

from cmp.modules.exporting.application.linear_viscoelastic_service import (
    CreateReferenceLinearViscoelasticSolverCard,
    LinearViscoelasticSolverCardService,
    LinearViscoelasticSolverCardSnapshot,
)
from cmp.modules.exporting.domain.reference_linear_viscoelasticity import (
    ABAQUS_PRONY_EXPORTER_DIGEST,
    ABAQUS_PRONY_EXPORTER_ID,
    ABAQUS_PRONY_EXPORTER_VERSION,
    LinearViscoelasticExportError,
    LinearViscoelasticExportTarget,
    LinearViscoelasticMappingItem,
    LinearViscoelasticMappingReport,
    LinearViscoelasticMappingReportMismatch,
    LinearViscoelasticSolverCardConflict,
    LinearViscoelasticSolverCardNotFound,
    MappingStatus,
    ReferenceLinearViscoelasticSolverCardContent,
)
from cmp.modules.identity_access.domain.authorization import AuthorizationDecision
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.modeling.domain.reference_linear_viscoelasticity import (
    REFERENCE_LINEAR_VISCOELASTIC_FAMILY_ID,
    REFERENCE_LINEAR_VISCOELASTIC_SCHEMA_DIGEST,
    REFERENCE_LINEAR_VISCOELASTIC_SCHEMA_VERSION,
    LinearViscoelasticError,
    LinearViscoelasticNotFound,
)
from cmp.shared.contracts.revisions import RevisionETag, RevisionMetadataResponse
from cmp.shared.domain.revisions import AggregateNotFound, RevisionKernelError, RevisionRecord

type Dependency = Callable[..., object]


class LinearViscoelasticTargetInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    solver: Annotated[str, StringConstraints(min_length=1, max_length=64)]
    version: Annotated[str, StringConstraints(min_length=1, max_length=64)]
    unit_system: Annotated[str, StringConstraints(min_length=1, max_length=64)]

    def to_domain(self) -> LinearViscoelasticExportTarget:
        return LinearViscoelasticExportTarget(self.solver, self.version, self.unit_system)


class LinearViscoelasticPreflightRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    material_model_revision_id: UUID
    target: LinearViscoelasticTargetInput


class LinearViscoelasticCardCreateRequest(LinearViscoelasticPreflightRequest):
    expected_mapping_report_sha256: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
    solver_material_id: Annotated[int, Field(ge=1, le=9_999_999_999)]
    material_name: Annotated[str, StringConstraints(pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,79}$")]
    change_reason: Annotated[str, StringConstraints(min_length=1, max_length=2000)]


class LinearViscoelasticMappingItemResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    ir_path: str
    target_representation: str | None
    status: MappingStatus
    detail: str

    @classmethod
    def from_domain(
        cls, value: LinearViscoelasticMappingItem
    ) -> LinearViscoelasticMappingItemResponse:
        return cls(
            name=value.name,
            ir_path=value.ir_path,
            target_representation=value.target_representation,
            status=value.status,
            detail=value.detail,
        )


class LinearViscoelasticMappingReportResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    material_model_id: UUID
    material_model_revision_id: UUID
    model_schema_digest: str
    target: LinearViscoelasticTargetInput
    items: tuple[LinearViscoelasticMappingItemResponse, ...]
    exporter_id: str
    exporter_version: str
    exporter_digest: str
    mapping_report_sha256: str
    exportable: bool
    non_production: bool

    @classmethod
    def from_domain(
        cls, value: LinearViscoelasticMappingReport
    ) -> LinearViscoelasticMappingReportResponse:
        return cls(
            material_model_id=value.material_model_id,
            material_model_revision_id=value.material_model_revision_id,
            model_schema_digest=value.model_schema_digest,
            target=LinearViscoelasticTargetInput(
                solver=value.target.solver,
                version=value.target.version,
                unit_system=value.target.unit_system,
            ),
            items=tuple(
                LinearViscoelasticMappingItemResponse.from_domain(item)
                for item in value.items
            ),
            exporter_id=value.exporter_id,
            exporter_version=value.exporter_version,
            exporter_digest=value.exporter_digest,
            mapping_report_sha256=value.digest,
            exportable=value.exportable,
            non_production=value.non_production,
        )


class PronyTermResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ordinal: int
    g_ratio: float
    k_ratio: float
    relaxation_time_s: float


class CardContentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    material_model_id: UUID
    material_model_revision_id: UUID
    model_schema_digest: str
    target: LinearViscoelasticTargetInput
    solver_material_id: int
    material_name: str
    density_kg_per_m3: float
    youngs_modulus_pa: float
    poisson_ratio: float
    bulk_relaxation_status: str
    terms: tuple[PronyTermResponse, ...]
    mapping_statuses: dict[str, MappingStatus]
    mapping_report_sha256: str
    card_sha256: str
    exporter_id: str
    exporter_version: str
    exporter_digest: str
    non_production: bool

    @classmethod
    def from_domain(
        cls, value: ReferenceLinearViscoelasticSolverCardContent
    ) -> CardContentResponse:
        return cls(
            material_model_id=value.material_model_id,
            material_model_revision_id=value.material_model_revision_id,
            model_schema_digest=value.model_schema_digest,
            target=LinearViscoelasticTargetInput(
                solver=value.target.solver,
                version=value.target.version,
                unit_system=value.target.unit_system,
            ),
            solver_material_id=value.solver_material_id,
            material_name=value.material_name,
            density_kg_per_m3=value.density_kg_per_m3,
            youngs_modulus_pa=value.youngs_modulus_pa,
            poisson_ratio=value.poisson_ratio,
            bulk_relaxation_status=value.bulk_relaxation_status.value,
            terms=tuple(
                PronyTermResponse(
                    ordinal=ordinal,
                    g_ratio=term.g_ratio,
                    k_ratio=term.k_ratio,
                    relaxation_time_s=term.relaxation_time_s,
                )
                for ordinal, term in enumerate(value.terms, 1)
            ),
            mapping_statuses={
                "density": value.density_mapping_status,
                "instantaneous_isotropic_elasticity": value.elasticity_mapping_status,
                "shear_prony_terms": value.prony_terms_mapping_status,
                "bulk_relaxation": value.bulk_mapping_status,
                "temperature_dependence": value.temperature_mapping_status,
                "unit_system": value.unit_system_mapping_status,
            },
            mapping_report_sha256=value.mapping_report_sha256,
            card_sha256=value.card_sha256,
            exporter_id=value.exporter_id,
            exporter_version=value.exporter_version,
            exporter_digest=value.exporter_digest,
            non_production=value.non_production,
        )


class CardProvenanceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reference_type: str
    revision_id: UUID
    content_sha256: str
    source_material_model_revision_id: UUID
    mapping_report_sha256: str
    recorded_at: datetime
    recorded_by: UUID

    @classmethod
    def from_record(
        cls, record: RevisionRecord, content: ReferenceLinearViscoelasticSolverCardContent
    ) -> CardProvenanceResponse:
        return cls(
            reference_type="exporting.solver_card.revision",
            revision_id=record.revision_id,
            content_sha256=record.content_hash,
            source_material_model_revision_id=content.material_model_revision_id,
            mapping_report_sha256=content.mapping_report_sha256,
            recorded_at=record.created_at,
            recorded_by=record.created_by,
        )


class CardRevisionResponse(RevisionMetadataResponse):
    content: CardContentResponse
    provenance: CardProvenanceResponse


class CardResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    solver_card_id: UUID
    material_model_id: UUID
    target: LinearViscoelasticTargetInput
    solver_material_id: int
    material_name: str
    current_revision: CardRevisionResponse
    links: dict[str, str]

    @classmethod
    def from_snapshot(cls, value: LinearViscoelasticSolverCardSnapshot) -> CardResponse:
        root = f"/api/v1/linear-viscoelastic-solver-cards/{value.id}"
        metadata = RevisionMetadataResponse.from_record(value.current.record, "draft")
        revision = CardRevisionResponse(
            **metadata.model_dump(),
            content=CardContentResponse.from_domain(value.current.content),
            provenance=CardProvenanceResponse.from_record(
                value.current.record, value.current.content
            ),
        )
        return cls(
            solver_card_id=value.id,
            material_model_id=value.material_model_id,
            target=LinearViscoelasticTargetInput(
                solver=value.target.solver,
                version=value.target.version,
                unit_system=value.target.unit_system,
            ),
            solver_material_id=value.solver_material_id,
            material_name=value.material_name,
            current_revision=revision,
            links={"self": root, "preview": f"{root}/preview", "download": f"{root}/download"},
        )


class CardListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: tuple[CardResponse, ...]


class CardCreatedResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    card: CardResponse
    mapping_report: LinearViscoelasticMappingReportResponse


class CapabilitiesResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    model_family_id: str
    model_schema_version: str
    model_schema_digest: str
    exporter_id: str
    exporter_version: str
    exporter_digest: str
    solver: str
    version: str
    unit_system: str
    keywords: tuple[str, ...]
    non_production: bool


class ExportProblem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: str
    title: str
    status: Annotated[int, Field(ge=400, le=599)]
    detail: Annotated[str, StringConstraints(min_length=1, max_length=2000)]
    code: Annotated[str, StringConstraints(pattern=r"^CMP-EXPORT-[0-9]{4}$")]
    trace_id: str


class ExportHttpError(Exception):
    def __init__(
        self, context: SecurityContext, status_code: int, title: str, detail: str, code: str
    ):
        self.context = context
        self.problem = ExportProblem(
            type="urn:cmp:problem:exporting:linear-viscoelastic",
            title=title,
            status=status_code,
            detail=detail,
            code=code,
            trace_id=context.trace_id,
        )
        super().__init__(title)


def _scope(request: Request) -> tuple[SecurityContext, AuthorizationDecision]:
    context = getattr(request.state, "security_context", None)
    decision = getattr(request.state, "authorization_decision", None)
    if not isinstance(context, SecurityContext) or not isinstance(decision, AuthorizationDecision):
        raise RuntimeError("linear-viscoelastic export request scope is unavailable")
    return context, decision


def _translate(context: SecurityContext, error: Exception) -> ExportHttpError:
    if isinstance(
        error,
        (LinearViscoelasticSolverCardNotFound, LinearViscoelasticNotFound, AggregateNotFound),
    ):
        return ExportHttpError(
            context,
            404,
            "Linear-viscoelastic export not found",
            "The exact IR revision or Solver Card is not visible.",
            "CMP-EXPORT-0021",
        )
    if isinstance(
        error,
        (
            LinearViscoelasticMappingReportMismatch,
            LinearViscoelasticSolverCardConflict,
            RevisionKernelError,
            IntegrityError,
        ),
    ):
        return ExportHttpError(
            context,
            409,
            "Linear-viscoelastic export conflict",
            "The immutable source or mapping acknowledgement conflicts.",
            "CMP-EXPORT-0023",
        )
    return ExportHttpError(
        context,
        422,
        "Invalid linear-viscoelastic export",
        "Use the declared Abaqus target and acknowledge the exact preflight report.",
        "CMP-EXPORT-0022",
    )


def install_linear_viscoelastic_solver_card_api(
    application: FastAPI,
    *,
    service: LinearViscoelasticSolverCardService | None,
    security_dependency: Dependency,
    read_dependency: Dependency,
    execute_dependency: Dependency,
) -> None:
    @application.exception_handler(ExportHttpError)
    async def error_handler(request: Request, error: ExportHttpError) -> JSONResponse:
        del request
        return JSONResponse(
            status_code=error.problem.status,
            content=error.problem.model_dump(mode="json"),
            media_type="application/problem+json",
            headers={"Cache-Control": "no-store", "X-Request-ID": str(error.context.request_id)},
        )

    errors: dict[int | str, dict[str, Any]] = {
        401: {"description": "Authentication required."},
        403: {"description": "Export permission is not authorized."},
        404: {"model": ExportProblem},
        409: {"model": ExportProblem},
        422: {"model": ExportProblem},
        503: {"model": ExportProblem},
    }

    def require_service(context: SecurityContext) -> LinearViscoelasticSolverCardService:
        if service is None:
            raise ExportHttpError(
                context,
                503,
                "Export service unavailable",
                "PostgreSQL export persistence is not configured.",
                "CMP-EXPORT-0025",
            )
        return service

    @application.get(
        "/api/v1/exporters/reference-linear-viscoelastic/capabilities",
        response_model=CapabilitiesResponse,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["exporting"],
    )
    def capabilities() -> CapabilitiesResponse:
        return CapabilitiesResponse(
            model_family_id=REFERENCE_LINEAR_VISCOELASTIC_FAMILY_ID,
            model_schema_version=REFERENCE_LINEAR_VISCOELASTIC_SCHEMA_VERSION,
            model_schema_digest=REFERENCE_LINEAR_VISCOELASTIC_SCHEMA_DIGEST,
            exporter_id=ABAQUS_PRONY_EXPORTER_ID,
            exporter_version=ABAQUS_PRONY_EXPORTER_VERSION,
            exporter_digest=ABAQUS_PRONY_EXPORTER_DIGEST,
            solver="abaqus",
            version="2025",
            unit_system="kg_m_s",
            keywords=("*MATERIAL", "*DENSITY", "*ELASTIC", "*VISCOELASTIC"),
            non_production=True,
        )

    @application.post(
        "/api/v1/linear-viscoelastic-models/{material_model_id}/mapping-preflight",
        response_model=LinearViscoelasticMappingReportResponse,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        responses=errors,
        tags=["exporting"],
    )
    def preflight(
        request: Request, material_model_id: UUID, body: LinearViscoelasticPreflightRequest
    ) -> LinearViscoelasticMappingReportResponse:
        context, decision = _scope(request)
        try:
            report = require_service(context).preflight(
                context,
                decision,
                material_model_id=material_model_id,
                material_model_revision_id=body.material_model_revision_id,
                target=body.target.to_domain(),
            )
        except (LinearViscoelasticExportError, LinearViscoelasticError, ValueError) as error:
            raise _translate(context, error) from error
        return LinearViscoelasticMappingReportResponse.from_domain(report)

    @application.get(
        "/api/v1/linear-viscoelastic-models/{material_model_id}/solver-cards",
        response_model=CardListResponse,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        responses=errors,
        tags=["exporting"],
    )
    def list_cards(request: Request, material_model_id: UUID) -> CardListResponse:
        context, decision = _scope(request)
        try:
            cards = require_service(context).list_cards_for_model(
                context, decision, material_model_id
            )
        except (LinearViscoelasticExportError, RevisionKernelError, ValueError) as error:
            raise _translate(context, error) from error
        return CardListResponse(items=tuple(CardResponse.from_snapshot(card) for card in cards))

    @application.post(
        "/api/v1/linear-viscoelastic-models/{material_model_id}/solver-cards",
        response_model=CardCreatedResponse,
        status_code=status.HTTP_201_CREATED,
        dependencies=[Depends(security_dependency), Depends(execute_dependency)],
        responses=errors,
        tags=["exporting"],
    )
    def create_card(
        request: Request,
        response: Response,
        material_model_id: UUID,
        body: LinearViscoelasticCardCreateRequest,
    ) -> CardCreatedResponse:
        context, decision = _scope(request)
        try:
            card, report = require_service(context).create_card(
                context,
                decision,
                CreateReferenceLinearViscoelasticSolverCard(
                    material_model_id=material_model_id,
                    material_model_revision_id=body.material_model_revision_id,
                    target=body.target.to_domain(),
                    expected_mapping_report_sha256=body.expected_mapping_report_sha256,
                    solver_material_id=body.solver_material_id,
                    material_name=body.material_name,
                    change_reason=body.change_reason,
                ),
            )
        except (
            LinearViscoelasticExportError,
            LinearViscoelasticError,
            RevisionKernelError,
            IntegrityError,
            ValueError,
        ) as error:
            raise _translate(context, error) from error
        response.headers["ETag"] = str(RevisionETag.from_ref(card.current.record.ref))
        response.headers["Cache-Control"] = "no-store"
        return CardCreatedResponse(
            card=CardResponse.from_snapshot(card),
            mapping_report=LinearViscoelasticMappingReportResponse.from_domain(report),
        )

    def card_for_text(
        request: Request, solver_card_id: UUID
    ) -> LinearViscoelasticSolverCardSnapshot:
        context, decision = _scope(request)
        try:
            return require_service(context).get_card(context, decision, solver_card_id)
        except (LinearViscoelasticExportError, RevisionKernelError, ValueError) as error:
            raise _translate(context, error) from error

    @application.get(
        "/api/v1/linear-viscoelastic-solver-cards/{solver_card_id}",
        response_model=CardResponse,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        responses=errors,
        tags=["exporting"],
    )
    def get_card(request: Request, response: Response, solver_card_id: UUID) -> CardResponse:
        card = card_for_text(request, solver_card_id)
        response.headers["ETag"] = str(RevisionETag.from_ref(card.current.record.ref))
        response.headers["Cache-Control"] = "no-store"
        return CardResponse.from_snapshot(card)

    @application.get(
        "/api/v1/linear-viscoelastic-solver-cards/{solver_card_id}/preview",
        response_class=PlainTextResponse,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        responses=errors,
        tags=["exporting"],
    )
    def preview(request: Request, solver_card_id: UUID) -> PlainTextResponse:
        card = card_for_text(request, solver_card_id)
        return PlainTextResponse(
            card.current.content.card_text,
            headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
        )

    @application.get(
        "/api/v1/linear-viscoelastic-solver-cards/{solver_card_id}/download",
        response_class=PlainTextResponse,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        responses=errors,
        tags=["exporting"],
    )
    def download(request: Request, solver_card_id: UUID) -> PlainTextResponse:
        card = card_for_text(request, solver_card_id)
        return PlainTextResponse(
            card.current.content.card_text,
            media_type="text/plain; charset=utf-8",
            headers={
                "Cache-Control": "no-store",
                "Content-Disposition": (
                    f'attachment; filename="{card.material_name}-{str(card.id)[:8]}.inp"'
                ),
                "X-Content-Type-Options": "nosniff",
                "X-CMP-Card-SHA256": card.current.content.card_sha256,
            },
        )

"""Protected mapping-preflight, immutable Solver Card, preview, and download resources."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends, FastAPI, Request, Response, status
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from sqlalchemy.exc import IntegrityError

from cmp.modules.exporting.application.service import (
    CreateReferenceOpenRadiossCard,
    RevisionSnapshot,
    SolverCardService,
    SolverCardSnapshot,
)
from cmp.modules.exporting.domain.openradioss_elast import (
    EXPORTER_DIGEST,
    EXPORTER_ID,
    EXPORTER_VERSION,
    ExportError,
    ExportTarget,
    InvalidExportRequest,
    MappingItem,
    MappingReportMismatch,
    MappingStatus,
    ReferenceMappingReport,
    ReferenceOpenRadiossCardContent,
    SolverCardConflict,
    SolverCardNotFound,
    UnsupportedExportTarget,
    mapping_report_from_card_content,
)
from cmp.modules.identity_access.domain.authorization import AuthorizationDecision
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.modeling.domain.reference_linear_elasticity import (
    REFERENCE_MODEL_FAMILY_ID,
    REFERENCE_MODEL_SCHEMA_DIGEST,
    REFERENCE_MODEL_SCHEMA_VERSION,
)
from cmp.shared.contracts.revisions import RevisionETag, RevisionMetadataResponse
from cmp.shared.domain.revisions import AggregateNotFound, RevisionKernelError, RevisionRecord

type Label = Annotated[str, StringConstraints(min_length=1, max_length=255)]
type Dependency = Callable[..., object]


class ExportTargetInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    solver: Annotated[str, StringConstraints(min_length=1, max_length=64)]
    version: Annotated[str, StringConstraints(min_length=1, max_length=64)]
    unit_system: Annotated[str, StringConstraints(min_length=1, max_length=64)]

    def to_domain(self) -> ExportTarget:
        return ExportTarget(self.solver, self.version, self.unit_system)


class ExportTargetResponse(ExportTargetInput):
    pass


class MappingItemResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    ir_path: str
    target_representation: str | None
    status: MappingStatus
    detail: str

    @classmethod
    def from_domain(cls, value: MappingItem) -> MappingItemResponse:
        return cls(
            name=value.name,
            ir_path=value.ir_path,
            target_representation=value.target_representation,
            status=value.status,
            detail=value.detail,
        )


class MappingReportResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    material_model_id: UUID
    material_model_revision_id: UUID
    model_schema_digest: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
    target: ExportTargetResponse
    items: tuple[MappingItemResponse, ...]
    exporter_id: str
    exporter_version: str
    exporter_digest: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
    mapping_report_sha256: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
    exportable: bool
    non_production: bool

    @classmethod
    def from_domain(cls, value: ReferenceMappingReport) -> MappingReportResponse:
        return cls(
            material_model_id=value.material_model_id,
            material_model_revision_id=value.material_model_revision_id,
            model_schema_digest=value.model_schema_digest,
            target=ExportTargetResponse(
                solver=value.target.solver,
                version=value.target.version,
                unit_system=value.target.unit_system,
            ),
            items=tuple(MappingItemResponse.from_domain(item) for item in value.items),
            exporter_id=value.exporter_id,
            exporter_version=value.exporter_version,
            exporter_digest=value.exporter_digest,
            mapping_report_sha256=value.digest,
            exportable=value.exportable,
            non_production=value.non_production,
        )


class MappingPreflightRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target: ExportTargetInput


class SolverCardCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    material_model_revision_id: UUID
    target: ExportTargetInput
    expected_mapping_report_sha256: Annotated[
        str, StringConstraints(pattern=r"^[0-9a-f]{64}$")
    ]
    solver_material_id: Annotated[int, Field(ge=1, le=9_999_999_999)]
    card_title: Annotated[str, StringConstraints(min_length=1, max_length=100)]
    change_reason: Annotated[str, StringConstraints(min_length=1, max_length=2000)]


class SolverCardContentResponse(BaseModel):
    """Typed values and mapping statuses; card text has its own preview/download route."""

    model_config = ConfigDict(extra="forbid")

    material_model_id: UUID
    material_model_revision_id: UUID
    model_schema_digest: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
    target: ExportTargetResponse
    solver_material_id: int
    card_title: str
    density_kg_per_m3: float
    youngs_modulus_pa: float
    poisson_ratio: float
    source_yield_stress_pa: float | None
    applicable_temperature_min_k: float | None
    applicable_temperature_max_k: float | None
    applicable_strain_rate_min_per_s: float | None
    applicable_strain_rate_max_per_s: float | None
    mapping_report_sha256: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
    card_sha256: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
    exporter_id: str
    exporter_version: str
    exporter_digest: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
    non_production: bool

    @classmethod
    def from_domain(cls, value: ReferenceOpenRadiossCardContent) -> SolverCardContentResponse:
        return cls(
            material_model_id=value.material_model_id,
            material_model_revision_id=value.material_model_revision_id,
            model_schema_digest=value.model_schema_digest,
            target=ExportTargetResponse(
                solver=value.target_solver,
                version=value.target_version,
                unit_system=value.target_unit_system,
            ),
            solver_material_id=value.solver_material_id,
            card_title=value.card_title,
            density_kg_per_m3=value.density_kg_per_m3,
            youngs_modulus_pa=value.youngs_modulus_pa,
            poisson_ratio=value.poisson_ratio,
            source_yield_stress_pa=value.source_yield_stress_pa,
            applicable_temperature_min_k=value.applicable_temperature_min_k,
            applicable_temperature_max_k=value.applicable_temperature_max_k,
            applicable_strain_rate_min_per_s=value.applicable_strain_rate_min_per_s,
            applicable_strain_rate_max_per_s=value.applicable_strain_rate_max_per_s,
            mapping_report_sha256=value.mapping_report_sha256,
            card_sha256=value.card_sha256,
            exporter_id=value.exporter_id,
            exporter_version=value.exporter_version,
            exporter_digest=value.exporter_digest,
            non_production=value.non_production,
        )


class SolverCardProvenanceSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entity_type: str
    reference_type: str
    revision_id: UUID
    content_sha256: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
    based_on_revision_id: UUID | None
    source_material_model_revision_id: UUID
    mapping_report_sha256: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
    recorded_at: datetime
    recorded_by: UUID

    @classmethod
    def from_record(
        cls,
        record: RevisionRecord,
        content: ReferenceOpenRadiossCardContent,
    ) -> SolverCardProvenanceSummary:
        reference_type = "exporting.solver_card.revision"
        return cls(
            entity_type=reference_type,
            reference_type=reference_type,
            revision_id=record.revision_id,
            content_sha256=record.content_hash,
            based_on_revision_id=record.based_on_revision_id,
            source_material_model_revision_id=content.material_model_revision_id,
            mapping_report_sha256=content.mapping_report_sha256,
            recorded_at=record.created_at,
            recorded_by=record.created_by,
        )


class SolverCardRevisionResponse(RevisionMetadataResponse):
    content: SolverCardContentResponse
    mapping_report: MappingReportResponse
    provenance: SolverCardProvenanceSummary

    @classmethod
    def from_snapshot(
        cls,
        solver_card_id: UUID,
        value: RevisionSnapshot[ReferenceOpenRadiossCardContent],
    ) -> SolverCardRevisionResponse:
        del solver_card_id
        metadata = RevisionMetadataResponse.from_record(value.record, "draft")
        report = mapping_report_from_card_content(value.content)
        return cls(
            **metadata.model_dump(),
            content=SolverCardContentResponse.from_domain(value.content),
            mapping_report=MappingReportResponse.from_domain(report),
            provenance=SolverCardProvenanceSummary.from_record(value.record, value.content),
        )


class SolverCardResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    solver_card_id: UUID
    material_model_id: UUID
    target: ExportTargetResponse
    solver_material_id: int
    current_revision: SolverCardRevisionResponse
    links: dict[str, str]

    @classmethod
    def from_snapshot(cls, value: SolverCardSnapshot) -> SolverCardResponse:
        root = f"/api/v1/solver-cards/{value.id}"
        return cls(
            solver_card_id=value.id,
            material_model_id=value.material_model_id,
            target=ExportTargetResponse(
                solver=value.target.solver,
                version=value.target.version,
                unit_system=value.target.unit_system,
            ),
            solver_material_id=value.solver_material_id,
            current_revision=SolverCardRevisionResponse.from_snapshot(value.id, value.current),
            links={
                "self": root,
                "revisions": f"{root}/revisions",
                "preview": f"{root}/preview",
                "download": f"{root}/download",
            },
        )


class SolverCardListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: tuple[SolverCardResponse, ...]


class SolverCardRevisionListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    solver_card_id: UUID
    revisions: tuple[SolverCardRevisionResponse, ...]


class TargetCapabilityResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    solver: str
    version: str
    unit_system: str
    keyword: str


class ModelCapabilityResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    schema_version: str
    schema_digest: str


class ExporterCapabilityResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    exporter_id: str
    exporter_version: str
    exporter_digest: str
    non_production: bool
    targets: tuple[TargetCapabilityResponse, ...]
    supported_model_families: tuple[ModelCapabilityResponse, ...]
    mapping_statuses: tuple[MappingStatus, ...]

    @classmethod
    def reference(cls) -> ExporterCapabilityResponse:
        return cls(
            exporter_id=EXPORTER_ID,
            exporter_version=EXPORTER_VERSION,
            exporter_digest=f"sha256:{EXPORTER_DIGEST}",
            non_production=True,
            targets=(
                TargetCapabilityResponse(
                    solver="openradioss",
                    version="2025",
                    unit_system="kg_m_s",
                    keyword="/MAT/ELAST",
                ),
            ),
            supported_model_families=(
                ModelCapabilityResponse(
                    id=REFERENCE_MODEL_FAMILY_ID,
                    schema_version=REFERENCE_MODEL_SCHEMA_VERSION,
                    schema_digest=f"sha256:{REFERENCE_MODEL_SCHEMA_DIGEST}",
                ),
            ),
            mapping_statuses=(
                "exact",
                "transformed",
                "approximated",
                "ignored",
                "unsupported",
                "not_applicable",
            ),
        )


class ExportingProblem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Label
    title: Label
    status: Annotated[int, Field(ge=400, le=599)]
    detail: Annotated[str, StringConstraints(min_length=1, max_length=2000)]
    code: Annotated[str, StringConstraints(pattern=r"^CMP-EXPORT-[0-9]{4}$")]
    trace_id: Label


class ExportingHttpError(Exception):
    def __init__(
        self,
        *,
        context: SecurityContext,
        status_code: int,
        title: str,
        detail: str,
        code: str,
    ) -> None:
        self.context = context
        self.problem = ExportingProblem(
            type="urn:cmp:problem:exporting",
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
        raise RuntimeError("Solver Card route dependencies did not initialize request scope")
    return context, decision


def _unavailable(context: SecurityContext) -> ExportingHttpError:
    return ExportingHttpError(
        context=context,
        status_code=503,
        title="Solver Card service unavailable",
        detail="The authoritative Solver Card store is not configured for this deployment.",
        code="CMP-EXPORT-0005",
    )


def _translate(context: SecurityContext, error: Exception) -> ExportingHttpError:
    if isinstance(error, (SolverCardNotFound, AggregateNotFound)):
        return ExportingHttpError(
            context=context,
            status_code=404,
            title="Solver Card resource not found",
            detail="No requested concrete Material Model or Solver Card is visible in this tenant.",
            code="CMP-EXPORT-0001",
        )
    if isinstance(
        error,
        (MappingReportMismatch, SolverCardConflict, RevisionKernelError, IntegrityError),
    ):
        return ExportingHttpError(
            context=context,
            status_code=409,
            title="Solver Card state conflict",
            detail="The frozen source, target identity, or mapping acknowledgement conflicts.",
            code="CMP-EXPORT-0003",
        )
    if isinstance(error, (InvalidExportRequest, UnsupportedExportTarget, ValueError)):
        return ExportingHttpError(
            context=context,
            status_code=422,
            title="Invalid Solver Card export request",
            detail="Use a supported explicit target and a valid typed reference Material Model IR.",
            code="CMP-EXPORT-0002",
        )
    return ExportingHttpError(
        context=context,
        status_code=409,
        title="Solver Card command rejected",
        detail="The reference Solver Card command could not be completed.",
        code="CMP-EXPORT-0003",
    )


def _etag(response: Response, record: RevisionRecord) -> None:
    response.headers["ETag"] = str(RevisionETag.from_ref(record.ref))
    response.headers["Cache-Control"] = "no-store"


def install_solver_card_api(
    application: FastAPI,
    *,
    service: SolverCardService | None,
    security_dependency: Dependency,
    read_dependency: Dependency,
    execute_dependency: Dependency,
) -> None:
    @application.exception_handler(ExportingHttpError)
    async def exporting_error_handler(
        request: Request,
        error: ExportingHttpError,
    ) -> JSONResponse:
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
        404: {"model": ExportingProblem},
        409: {"model": ExportingProblem},
        422: {"model": ExportingProblem},
        503: {"model": ExportingProblem},
    }

    @application.get(
        "/api/v1/exporters/reference-openradioss-elast/capabilities",
        operation_id="getReferenceOpenRadiossExporterCapabilities",
        response_model=ExporterCapabilityResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["exporting"],
        summary="Read the narrow non-production reference exporter capability manifest.",
    )
    def get_reference_openradioss_exporter_capabilities() -> ExporterCapabilityResponse:
        return ExporterCapabilityResponse.reference()

    @application.post(
        "/api/v1/material-models/{material_model_id}/mapping-preflight",
        operation_id="preflightReferenceOpenRadiossMapping",
        response_model=MappingReportResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["exporting"],
        summary=(
            "Map the current reference IR revision to an explicit target without creating a card."
        ),
    )
    def preflight_reference_openradioss_mapping(
        request: Request,
        material_model_id: UUID,
        body: MappingPreflightRequest,
    ) -> MappingReportResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            report = service.preflight_reference_openradioss(
                context,
                decision,
                material_model_id,
                body.target.to_domain(),
            )
        except (ExportError, RevisionKernelError, IntegrityError, ValueError) as error:
            raise _translate(context, error) from error
        return MappingReportResponse.from_domain(report)

    @application.get(
        "/api/v1/material-models/{material_model_id}/solver-cards",
        operation_id="listSolverCardsForMaterialModel",
        response_model=SolverCardListResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["exporting"],
        summary="List current Solver Cards generated from a Material Model identity.",
    )
    def list_solver_cards_for_material_model(
        request: Request,
        material_model_id: UUID,
    ) -> SolverCardListResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            values = service.list_solver_cards_for_model(context, decision, material_model_id)
        except (ExportError, RevisionKernelError, IntegrityError, ValueError) as error:
            raise _translate(context, error) from error
        return SolverCardListResponse(
            items=tuple(SolverCardResponse.from_snapshot(value) for value in values)
        )

    @application.post(
        "/api/v1/material-models/{material_model_id}/solver-cards",
        operation_id="createReferenceOpenRadiossSolverCard",
        response_model=SolverCardResponse,
        status_code=status.HTTP_201_CREATED,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(execute_dependency)],
        tags=["exporting"],
        summary="Create an immutable reference OpenRadioss card from one acknowledged IR mapping.",
    )
    def create_reference_openradioss_solver_card(
        request: Request,
        response: Response,
        material_model_id: UUID,
        body: SolverCardCreateRequest,
    ) -> SolverCardResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            value, _report = service.create_reference_openradioss_card(
                context,
                decision,
                CreateReferenceOpenRadiossCard(
                    material_model_id=material_model_id,
                    material_model_revision_id=body.material_model_revision_id,
                    target=body.target.to_domain(),
                    expected_mapping_report_sha256=body.expected_mapping_report_sha256,
                    solver_material_id=body.solver_material_id,
                    card_title=body.card_title,
                    change_reason=body.change_reason,
                ),
            )
        except (ExportError, RevisionKernelError, IntegrityError, ValueError) as error:
            raise _translate(context, error) from error
        _etag(response, value.current.record)
        return SolverCardResponse.from_snapshot(value)

    @application.get(
        "/api/v1/solver-cards/{solver_card_id}",
        operation_id="getSolverCard",
        response_model=SolverCardResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["exporting"],
        summary="Read one current immutable Solver Card revision and its mapping report.",
    )
    def get_solver_card(
        request: Request,
        response: Response,
        solver_card_id: UUID,
    ) -> SolverCardResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            value = service.get_solver_card(context, decision, solver_card_id)
        except (ExportError, RevisionKernelError, IntegrityError, ValueError) as error:
            raise _translate(context, error) from error
        _etag(response, value.current.record)
        return SolverCardResponse.from_snapshot(value)

    @application.get(
        "/api/v1/solver-cards/{solver_card_id}/revisions",
        operation_id="listSolverCardRevisions",
        response_model=SolverCardRevisionListResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["exporting"],
        summary="List immutable revisions for one Solver Card identity.",
    )
    def list_solver_card_revisions(
        request: Request,
        solver_card_id: UUID,
    ) -> SolverCardRevisionListResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            values = service.list_solver_card_revisions(context, decision, solver_card_id)
        except (ExportError, RevisionKernelError, IntegrityError, ValueError) as error:
            raise _translate(context, error) from error
        return SolverCardRevisionListResponse(
            solver_card_id=solver_card_id,
            revisions=tuple(
                SolverCardRevisionResponse.from_snapshot(solver_card_id, value)
                for value in values
            ),
        )

    @application.get(
        "/api/v1/solver-cards/{solver_card_id}/preview",
        operation_id="previewSolverCard",
        responses={**errors, 200: {"description": "Plain-text Solver Card preview."}},
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["exporting"],
        summary="Preview the exact immutable Solver Card text.",
    )
    def preview_solver_card(request: Request, solver_card_id: UUID) -> PlainTextResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            value = service.get_solver_card(context, decision, solver_card_id)
        except (ExportError, RevisionKernelError, IntegrityError, ValueError) as error:
            raise _translate(context, error) from error
        return PlainTextResponse(
            value.current.content.card_text,
            media_type="text/plain; charset=utf-8",
            headers={"Cache-Control": "no-store"},
        )

    @application.get(
        "/api/v1/solver-cards/{solver_card_id}/download",
        operation_id="downloadSolverCard",
        responses={**errors, 200: {"description": "Solver Card text attachment."}},
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["exporting"],
        summary="Download the exact immutable Solver Card text.",
    )
    def download_solver_card(request: Request, solver_card_id: UUID) -> PlainTextResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            value = service.get_solver_card(context, decision, solver_card_id)
        except (ExportError, RevisionKernelError, IntegrityError, ValueError) as error:
            raise _translate(context, error) from error
        filename = f"openradioss-mat-{value.solver_material_id}.rad"
        return PlainTextResponse(
            value.current.content.card_text,
            media_type="text/plain; charset=utf-8",
            headers={
                "Cache-Control": "no-store",
                "Content-Disposition": f'attachment; filename="{filename}"',
            },
        )

"""HTTP preflight, preview, and download for OpenRadioss/Abaqus elastoplastic cards."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends, FastAPI, Request, Response, status
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from sqlalchemy.exc import IntegrityError

from cmp.modules.artifacts.domain.content import ArtifactError, ArtifactNotFound
from cmp.modules.exporting.application.elastoplastic_service import (
    CreateReferenceElastoplasticSolverCard,
    ElastoplasticSolverCardService,
    ElastoplasticSolverCardSnapshot,
)
from cmp.modules.exporting.domain.reference_isotropic_tabulated_plasticity import (
    ABAQUS_PLASTIC_EXPORTER_DIGEST,
    ABAQUS_PLASTIC_EXPORTER_ID,
    ABAQUS_PLASTIC_EXPORTER_VERSION,
    OPENRADIOSS_LAW36_EXPORTER_DIGEST,
    OPENRADIOSS_LAW36_EXPORTER_ID,
    OPENRADIOSS_LAW36_EXPORTER_VERSION,
    ElastoplasticExportError,
    ElastoplasticExportTarget,
    ElastoplasticMappingItem,
    ElastoplasticMappingReport,
    ElastoplasticMappingReportMismatch,
    ElastoplasticSolverCardConflict,
    ElastoplasticSolverCardNotFound,
    MappingStatus,
    ReferenceElastoplasticSolverCardContent,
)
from cmp.modules.identity_access.domain.authorization import AuthorizationDecision
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.modeling.domain.reference_isotropic_tabulated_plasticity import (
    REFERENCE_TABULATED_PLASTICITY_FAMILY_ID,
    REFERENCE_TABULATED_PLASTICITY_SCHEMA_DIGEST,
    REFERENCE_TABULATED_PLASTICITY_SCHEMA_VERSION,
    TabulatedPlasticityError,
    TabulatedPlasticityNotFound,
)
from cmp.shared.contracts.revisions import RevisionETag, RevisionMetadataResponse
from cmp.shared.domain.revisions import AggregateNotFound, RevisionKernelError, RevisionRecord

type Dependency = Callable[..., object]


class ElastoplasticTargetInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    solver: Annotated[str, StringConstraints(min_length=1, max_length=64)]
    version: Annotated[str, StringConstraints(min_length=1, max_length=64)]
    unit_system: Annotated[str, StringConstraints(min_length=1, max_length=64)]

    def to_domain(self) -> ElastoplasticExportTarget:
        return ElastoplasticExportTarget(self.solver, self.version, self.unit_system)


class ElastoplasticPreflightRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    material_model_revision_id: UUID
    target: ElastoplasticTargetInput


class ElastoplasticCardCreateRequest(ElastoplasticPreflightRequest):
    expected_mapping_report_sha256: Annotated[
        str, StringConstraints(pattern=r"^[0-9a-f]{64}$")
    ]
    solver_material_id: Annotated[int, Field(ge=1, le=9_999_999_999)]
    material_name: Annotated[
        str, StringConstraints(pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,79}$")
    ]
    change_reason: Annotated[str, StringConstraints(min_length=1, max_length=2000)]


class ElastoplasticMappingItemResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    ir_path: str
    target_representation: str | None
    status: MappingStatus
    detail: str

    @classmethod
    def from_domain(
        cls, value: ElastoplasticMappingItem
    ) -> ElastoplasticMappingItemResponse:
        return cls(
            name=value.name,
            ir_path=value.ir_path,
            target_representation=value.target_representation,
            status=value.status,
            detail=value.detail,
        )


class ElastoplasticMappingReportResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    material_model_id: UUID
    material_model_revision_id: UUID
    model_schema_digest: str
    target: ElastoplasticTargetInput
    items: tuple[ElastoplasticMappingItemResponse, ...]
    exporter_id: str
    exporter_version: str
    exporter_digest: str
    mapping_report_sha256: str
    exportable: bool
    non_production: bool

    @classmethod
    def from_domain(
        cls, value: ElastoplasticMappingReport
    ) -> ElastoplasticMappingReportResponse:
        return cls(
            material_model_id=value.material_model_id,
            material_model_revision_id=value.material_model_revision_id,
            model_schema_digest=value.model_schema_digest,
            target=ElastoplasticTargetInput(
                solver=value.target.solver,
                version=value.target.version,
                unit_system=value.target.unit_system,
            ),
            items=tuple(
                ElastoplasticMappingItemResponse.from_domain(item) for item in value.items
            ),
            exporter_id=value.exporter_id,
            exporter_version=value.exporter_version,
            exporter_digest=value.exporter_digest,
            mapping_report_sha256=value.digest,
            exportable=value.exportable,
            non_production=value.non_production,
        )


class ElastoplasticApplicabilityResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    temperature_min_k: float | None
    temperature_max_k: float | None
    strain_rate_min_per_s: float | None
    strain_rate_max_per_s: float | None
    note: str | None


class ElastoplasticCardContentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    material_model_id: UUID
    material_model_revision_id: UUID
    model_schema_digest: str
    target: ElastoplasticTargetInput
    solver_material_id: int
    material_name: str
    density_kg_per_m3: float
    youngs_modulus_pa: float
    poisson_ratio: float
    initial_yield_stress_pa: float
    hardening_curve_artifact_id: UUID
    hardening_curve_sha256: str
    hardening_curve_point_count: int
    extension_max_true_plastic_strain: float
    post_necking_extension_policy: str
    applicability: ElastoplasticApplicabilityResponse
    mapping_statuses: dict[str, MappingStatus]
    mapping_report_sha256: str
    card_sha256: str
    exporter_id: str
    exporter_version: str
    exporter_digest: str
    non_production: bool

    @classmethod
    def from_domain(
        cls, value: ReferenceElastoplasticSolverCardContent
    ) -> ElastoplasticCardContentResponse:
        return cls(
            material_model_id=value.material_model_id,
            material_model_revision_id=value.material_model_revision_id,
            model_schema_digest=value.model_schema_digest,
            target=ElastoplasticTargetInput(
                solver=value.target.solver,
                version=value.target.version,
                unit_system=value.target.unit_system,
            ),
            solver_material_id=value.solver_material_id,
            material_name=value.material_name,
            density_kg_per_m3=value.density_kg_per_m3,
            youngs_modulus_pa=value.youngs_modulus_pa,
            poisson_ratio=value.poisson_ratio,
            initial_yield_stress_pa=value.initial_yield_stress_pa,
            hardening_curve_artifact_id=value.hardening_curve_artifact_id,
            hardening_curve_sha256=value.hardening_curve_sha256,
            hardening_curve_point_count=value.hardening_curve_point_count,
            extension_max_true_plastic_strain=value.extension_max_true_plastic_strain,
            post_necking_extension_policy=value.post_necking_extension_policy,
            applicability=ElastoplasticApplicabilityResponse(
                temperature_min_k=value.applicable_temperature_min_k,
                temperature_max_k=value.applicable_temperature_max_k,
                strain_rate_min_per_s=value.applicable_strain_rate_min_per_s,
                strain_rate_max_per_s=value.applicable_strain_rate_max_per_s,
                note=value.applicability_note,
            ),
            mapping_statuses={
                "density": value.density_mapping_status,
                "isotropic_elasticity": value.elasticity_mapping_status,
                "initial_yield": value.initial_yield_mapping_status,
                "isotropic_hardening_curve": value.hardening_curve_mapping_status,
                "post_necking_extension": value.extension_mapping_status,
                "temperature_dependence": value.temperature_mapping_status,
                "strain_rate_dependence": value.strain_rate_mapping_status,
                "unit_system": value.unit_system_mapping_status,
            },
            mapping_report_sha256=value.mapping_report_sha256,
            card_sha256=value.card_sha256,
            exporter_id=value.exporter_id,
            exporter_version=value.exporter_version,
            exporter_digest=value.exporter_digest,
            non_production=value.non_production,
        )


class ElastoplasticCardProvenanceSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entity_type: str
    reference_type: str
    revision_id: UUID
    content_sha256: str
    based_on_revision_id: UUID | None
    source_material_model_revision_id: UUID
    source_hardening_curve_artifact_id: UUID
    source_hardening_curve_sha256: str
    mapping_report_sha256: str
    recorded_at: datetime
    recorded_by: UUID

    @classmethod
    def from_record(
        cls,
        record: RevisionRecord,
        content: ReferenceElastoplasticSolverCardContent,
    ) -> ElastoplasticCardProvenanceSummary:
        reference_type = "exporting.solver_card.revision"
        return cls(
            entity_type=reference_type,
            reference_type=reference_type,
            revision_id=record.revision_id,
            content_sha256=record.content_hash,
            based_on_revision_id=record.based_on_revision_id,
            source_material_model_revision_id=content.material_model_revision_id,
            source_hardening_curve_artifact_id=content.hardening_curve_artifact_id,
            source_hardening_curve_sha256=content.hardening_curve_sha256,
            mapping_report_sha256=content.mapping_report_sha256,
            recorded_at=record.created_at,
            recorded_by=record.created_by,
        )


class ElastoplasticCardRevisionResponse(RevisionMetadataResponse):
    content: ElastoplasticCardContentResponse
    provenance: ElastoplasticCardProvenanceSummary

    @classmethod
    def from_snapshot(cls, snapshot: Any) -> ElastoplasticCardRevisionResponse:
        metadata = RevisionMetadataResponse.from_record(snapshot.record, "draft")
        return cls(
            **metadata.model_dump(),
            content=ElastoplasticCardContentResponse.from_domain(snapshot.content),
            provenance=ElastoplasticCardProvenanceSummary.from_record(
                snapshot.record, snapshot.content
            ),
        )


class ElastoplasticCardResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    solver_card_id: UUID
    material_model_id: UUID
    target: ElastoplasticTargetInput
    solver_material_id: int
    material_name: str
    current_revision: ElastoplasticCardRevisionResponse
    links: dict[str, str]

    @classmethod
    def from_snapshot(
        cls, value: ElastoplasticSolverCardSnapshot
    ) -> ElastoplasticCardResponse:
        root = f"/api/v1/elastoplastic-solver-cards/{value.id}"
        return cls(
            solver_card_id=value.id,
            material_model_id=value.material_model_id,
            target=ElastoplasticTargetInput(
                solver=value.target.solver,
                version=value.target.version,
                unit_system=value.target.unit_system,
            ),
            solver_material_id=value.solver_material_id,
            material_name=value.material_name,
            current_revision=ElastoplasticCardRevisionResponse.from_snapshot(value.current),
            links={"self": root, "preview": f"{root}/preview", "download": f"{root}/download"},
        )


class ElastoplasticCardListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: tuple[ElastoplasticCardResponse, ...]


class ElastoplasticCardCreatedResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    card: ElastoplasticCardResponse
    mapping_report: ElastoplasticMappingReportResponse


class ElastoplasticExporterResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    exporter_id: str
    exporter_version: str
    exporter_digest: str
    solver: str
    version: str
    unit_system: str
    keywords: tuple[str, ...]


class ElastoplasticCapabilitiesResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model_family_id: str
    model_schema_version: str
    model_schema_digest: str
    exporters: tuple[ElastoplasticExporterResponse, ...]
    mapping_statuses: tuple[str, ...]
    non_production: bool


class ElastoplasticExportProblem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    title: str
    status: Annotated[int, Field(ge=400, le=599)]
    detail: Annotated[str, StringConstraints(min_length=1, max_length=2000)]
    code: Annotated[str, StringConstraints(pattern=r"^CMP-EXPORT-[0-9]{4}$")]
    trace_id: str


class ElastoplasticExportHttpError(Exception):
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
        self.problem = ElastoplasticExportProblem(
            type="urn:cmp:problem:exporting:elastoplastic",
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
        raise RuntimeError("elastoplastic export dependencies did not initialize request scope")
    return context, decision


def _unavailable(context: SecurityContext) -> ElastoplasticExportHttpError:
    return ElastoplasticExportHttpError(
        context=context,
        status_code=503,
        title="Elastoplastic export service unavailable",
        detail="The authoritative Modeling, Artifact, and Export stores are not configured.",
        code="CMP-EXPORT-0015",
    )


def _translate(context: SecurityContext, error: Exception) -> ElastoplasticExportHttpError:
    if isinstance(
        error,
        (
            ElastoplasticSolverCardNotFound,
            TabulatedPlasticityNotFound,
            ArtifactNotFound,
            AggregateNotFound,
        ),
    ):
        return ElastoplasticExportHttpError(
            context=context,
            status_code=404,
            title="Elastoplastic export resource not found",
            detail="No requested concrete model revision or Solver Card is visible.",
            code="CMP-EXPORT-0011",
        )
    if isinstance(
        error,
        (
            ElastoplasticMappingReportMismatch,
            ElastoplasticSolverCardConflict,
            ArtifactError,
            RevisionKernelError,
            IntegrityError,
        ),
    ):
        return ElastoplasticExportHttpError(
            context=context,
            status_code=409,
            title="Elastoplastic export conflict",
            detail="The immutable source, curve Artifact, or mapping acknowledgement conflicts.",
            code="CMP-EXPORT-0013",
        )
    return ElastoplasticExportHttpError(
        context=context,
        status_code=422,
        title="Invalid elastoplastic export request",
        detail="Select a declared target and acknowledge the exact current mapping report.",
        code="CMP-EXPORT-0012",
    )


def _etag(response: Response, record: RevisionRecord) -> None:
    response.headers["ETag"] = str(RevisionETag.from_ref(record.ref))
    response.headers["Cache-Control"] = "no-store"


def install_elastoplastic_solver_card_api(
    application: FastAPI,
    *,
    service: ElastoplasticSolverCardService | None,
    security_dependency: Dependency,
    read_dependency: Dependency,
    execute_dependency: Dependency,
) -> None:
    @application.exception_handler(ElastoplasticExportHttpError)
    async def elastoplastic_export_error_handler(
        request: Request, error: ElastoplasticExportHttpError
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
        404: {"model": ElastoplasticExportProblem},
        409: {"model": ElastoplasticExportProblem},
        422: {"model": ElastoplasticExportProblem},
        503: {"model": ElastoplasticExportProblem},
    }

    @application.get(
        "/api/v1/exporters/reference-elastoplastic/capabilities",
        operation_id="getReferenceElastoplasticExporterCapabilities",
        response_model=ElastoplasticCapabilitiesResponse,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        responses=errors,
        tags=["exporting"],
    )
    def capabilities() -> ElastoplasticCapabilitiesResponse:
        return ElastoplasticCapabilitiesResponse(
            model_family_id=REFERENCE_TABULATED_PLASTICITY_FAMILY_ID,
            model_schema_version=REFERENCE_TABULATED_PLASTICITY_SCHEMA_VERSION,
            model_schema_digest=REFERENCE_TABULATED_PLASTICITY_SCHEMA_DIGEST,
            exporters=(
                ElastoplasticExporterResponse(
                    exporter_id=OPENRADIOSS_LAW36_EXPORTER_ID,
                    exporter_version=OPENRADIOSS_LAW36_EXPORTER_VERSION,
                    exporter_digest=OPENRADIOSS_LAW36_EXPORTER_DIGEST,
                    solver="openradioss",
                    version="2025",
                    unit_system="kg_m_s",
                    keywords=("/MAT/LAW36", "/FUNCT"),
                ),
                ElastoplasticExporterResponse(
                    exporter_id=ABAQUS_PLASTIC_EXPORTER_ID,
                    exporter_version=ABAQUS_PLASTIC_EXPORTER_VERSION,
                    exporter_digest=ABAQUS_PLASTIC_EXPORTER_DIGEST,
                    solver="abaqus",
                    version="2025",
                    unit_system="kg_m_s",
                    keywords=("*DENSITY", "*ELASTIC", "*PLASTIC"),
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
            non_production=True,
        )

    @application.post(
        "/api/v1/tabulated-plasticity-models/{material_model_id}/mapping-preflight",
        operation_id="preflightReferenceElastoplasticMapping",
        response_model=ElastoplasticMappingReportResponse,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        responses=errors,
        tags=["exporting"],
    )
    def preflight(
        request: Request,
        material_model_id: UUID,
        body: ElastoplasticPreflightRequest,
    ) -> ElastoplasticMappingReportResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            value = service.preflight(
                context,
                decision,
                material_model_id=material_model_id,
                material_model_revision_id=body.material_model_revision_id,
                target=body.target.to_domain(),
            )
        except (
            ElastoplasticExportError,
            TabulatedPlasticityError,
            ArtifactError,
            ValueError,
        ) as error:
            raise _translate(context, error) from error
        return ElastoplasticMappingReportResponse.from_domain(value)

    @application.get(
        "/api/v1/tabulated-plasticity-models/{material_model_id}/solver-cards",
        operation_id="listReferenceElastoplasticSolverCards",
        response_model=ElastoplasticCardListResponse,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        responses=errors,
        tags=["exporting"],
    )
    def list_cards(
        request: Request, material_model_id: UUID
    ) -> ElastoplasticCardListResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            values = service.list_cards_for_model(context, decision, material_model_id)
        except (ElastoplasticExportError, RevisionKernelError, ValueError) as error:
            raise _translate(context, error) from error
        return ElastoplasticCardListResponse(
            items=tuple(ElastoplasticCardResponse.from_snapshot(value) for value in values)
        )

    @application.post(
        "/api/v1/tabulated-plasticity-models/{material_model_id}/solver-cards",
        operation_id="createReferenceElastoplasticSolverCard",
        response_model=ElastoplasticCardCreatedResponse,
        status_code=status.HTTP_201_CREATED,
        dependencies=[Depends(security_dependency), Depends(execute_dependency)],
        responses=errors,
        tags=["exporting"],
    )
    async def create_card(
        request: Request,
        response: Response,
        material_model_id: UUID,
        body: ElastoplasticCardCreateRequest,
    ) -> ElastoplasticCardCreatedResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            card, report = await service.create_card(
                context,
                decision,
                CreateReferenceElastoplasticSolverCard(
                    material_model_id=material_model_id,
                    material_model_revision_id=body.material_model_revision_id,
                    target=body.target.to_domain(),
                    expected_mapping_report_sha256=(
                        body.expected_mapping_report_sha256
                    ),
                    solver_material_id=body.solver_material_id,
                    material_name=body.material_name,
                    change_reason=body.change_reason,
                ),
            )
        except (
            ElastoplasticExportError,
            TabulatedPlasticityError,
            ArtifactError,
            RevisionKernelError,
            IntegrityError,
            ValueError,
        ) as error:
            raise _translate(context, error) from error
        _etag(response, card.current.record)
        return ElastoplasticCardCreatedResponse(
            card=ElastoplasticCardResponse.from_snapshot(card),
            mapping_report=ElastoplasticMappingReportResponse.from_domain(report),
        )

    @application.get(
        "/api/v1/elastoplastic-solver-cards/{solver_card_id}",
        operation_id="getReferenceElastoplasticSolverCard",
        response_model=ElastoplasticCardResponse,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        responses=errors,
        tags=["exporting"],
    )
    def get_card(
        request: Request, response: Response, solver_card_id: UUID
    ) -> ElastoplasticCardResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            value = service.get_card(context, decision, solver_card_id)
        except (ElastoplasticExportError, RevisionKernelError, ValueError) as error:
            raise _translate(context, error) from error
        _etag(response, value.current.record)
        return ElastoplasticCardResponse.from_snapshot(value)

    def _card_for_text(request: Request, solver_card_id: UUID) -> ElastoplasticSolverCardSnapshot:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            return service.get_card(context, decision, solver_card_id)
        except (ElastoplasticExportError, RevisionKernelError, ValueError) as error:
            raise _translate(context, error) from error

    @application.get(
        "/api/v1/elastoplastic-solver-cards/{solver_card_id}/preview",
        operation_id="previewReferenceElastoplasticSolverCard",
        response_class=PlainTextResponse,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        responses=errors,
        tags=["exporting"],
    )
    def preview(request: Request, solver_card_id: UUID) -> PlainTextResponse:
        card = _card_for_text(request, solver_card_id)
        return PlainTextResponse(
            card.current.content.card_text,
            headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
        )

    @application.get(
        "/api/v1/elastoplastic-solver-cards/{solver_card_id}/download",
        operation_id="downloadReferenceElastoplasticSolverCard",
        response_class=PlainTextResponse,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        responses=errors,
        tags=["exporting"],
    )
    def download(request: Request, solver_card_id: UUID) -> PlainTextResponse:
        card = _card_for_text(request, solver_card_id)
        extension = "rad" if card.target.is_openradioss else "inp"
        filename = f"{card.material_name}-{str(card.id)[:8]}.{extension}"
        return PlainTextResponse(
            card.current.content.card_text,
            media_type="text/plain; charset=utf-8",
            headers={
                "Cache-Control": "no-store",
                "Content-Disposition": f'attachment; filename="{filename}"',
                "X-Content-Type-Options": "nosniff",
                "X-CMP-Card-SHA256": card.current.content.card_sha256,
            },
        )

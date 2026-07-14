"""Protected HTTP resources for the reference linear-elastic Material Model IR."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends, FastAPI, Request, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from sqlalchemy.exc import IntegrityError

from cmp.modules.identity_access.domain.authorization import AuthorizationDecision
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.modeling.application.service import (
    CreateReferenceLinearElasticModel,
    MaterialModelService,
    MaterialModelSnapshot,
    RevisionSnapshot,
)
from cmp.modules.modeling.domain.reference_linear_elasticity import (
    REFERENCE_MODEL_FAMILY_ID,
    REFERENCE_MODEL_SCHEMA_DIGEST,
    REFERENCE_MODEL_SCHEMA_VERSION,
    InvalidReferenceModel,
    ModelingError,
    ReferenceCalibrationEvidence,
    ReferenceLinearElasticContent,
    ReferenceModelConflict,
    ReferenceModelNotFound,
    reference_linear_elastic_ir,
)
from cmp.shared.contracts.revisions import RevisionETag, RevisionMetadataResponse
from cmp.shared.domain.revisions import AggregateNotFound, RevisionKernelError, RevisionRecord

type Label = Annotated[str, StringConstraints(min_length=1, max_length=255)]
type Dependency = Callable[..., object]


class ReferenceModelCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    property_set_revision_id: UUID
    change_reason: Annotated[str, StringConstraints(min_length=1, max_length=2000)]


class ReferenceCalibrationEvidenceResponse(BaseModel):
    """Explicit provenance of a human-selected reference calibration Candidate."""

    model_config = ConfigDict(extra="forbid")

    calibration_selection_id: UUID
    calibration_selection_revision_id: UUID
    calibration_run_id: UUID
    calibration_candidate_id: UUID
    calibration_candidate_sha256: str
    diagnostics_artifact_id: UUID
    diagnostics_sha256: str

    @classmethod
    def from_domain(
        cls, value: ReferenceCalibrationEvidence
    ) -> ReferenceCalibrationEvidenceResponse:
        return cls(
            calibration_selection_id=value.calibration_selection_id,
            calibration_selection_revision_id=value.calibration_selection_revision_id,
            calibration_run_id=value.calibration_run_id,
            calibration_candidate_id=value.calibration_candidate_id,
            calibration_candidate_sha256=f"sha256:{value.calibration_candidate_sha256}",
            diagnostics_artifact_id=value.diagnostics_artifact_id,
            diagnostics_sha256=f"sha256:{value.diagnostics_sha256}",
        )


class ReferenceLinearElasticContentResponse(BaseModel):
    """Typed source and SI values, rather than a free-form model payload."""

    model_config = ConfigDict(extra="forbid")

    model_family_id: str
    model_schema_version: str
    model_schema_digest: str
    material_id: UUID
    material_revision_id: UUID
    material_state_id: UUID
    material_state_revision_id: UUID
    property_set_id: UUID
    property_set_revision_id: UUID
    density_kg_per_m3: float
    youngs_modulus_pa: float
    poisson_ratio: float
    source_yield_stress_pa: float | None
    applicable_temperature_min_k: float | None
    applicable_temperature_max_k: float | None
    applicable_strain_rate_min_per_s: float | None
    applicable_strain_rate_max_per_s: float | None
    applicability_note: str | None
    reference_temperature_k: float
    calibration_evidence: ReferenceCalibrationEvidenceResponse | None
    non_production: bool

    @classmethod
    def from_domain(
        cls, value: ReferenceLinearElasticContent
    ) -> ReferenceLinearElasticContentResponse:
        return cls(
            model_family_id=REFERENCE_MODEL_FAMILY_ID,
            model_schema_version=REFERENCE_MODEL_SCHEMA_VERSION,
            model_schema_digest=f"sha256:{REFERENCE_MODEL_SCHEMA_DIGEST}",
            material_id=value.material_id,
            material_revision_id=value.material_revision_id,
            material_state_id=value.material_state_id,
            material_state_revision_id=value.material_state_revision_id,
            property_set_id=value.property_set_id,
            property_set_revision_id=value.property_set_revision_id,
            density_kg_per_m3=value.density_kg_per_m3,
            youngs_modulus_pa=value.youngs_modulus_pa,
            poisson_ratio=value.poisson_ratio,
            source_yield_stress_pa=value.source_yield_stress_pa,
            applicable_temperature_min_k=value.applicable_temperature_min_k,
            applicable_temperature_max_k=value.applicable_temperature_max_k,
            applicable_strain_rate_min_per_s=value.applicable_strain_rate_min_per_s,
            applicable_strain_rate_max_per_s=value.applicable_strain_rate_max_per_s,
            applicability_note=value.applicability_note,
            reference_temperature_k=value.reference_temperature_k,
            calibration_evidence=(
                ReferenceCalibrationEvidenceResponse.from_domain(value.calibration_evidence)
                if value.calibration_evidence is not None
                else None
            ),
            non_production=True,
        )


class ModelProvenanceSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entity_type: str
    reference_type: str
    revision_id: UUID
    content_sha256: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
    based_on_revision_id: UUID | None
    source_property_set_revision_id: UUID
    calibration_selection_revision_id: UUID | None
    recorded_at: datetime
    recorded_by: UUID

    @classmethod
    def from_record(
        cls, record: RevisionRecord, content: ReferenceLinearElasticContent
    ) -> ModelProvenanceSummary:
        reference_type = "modeling.material_model.revision"
        return cls(
            entity_type=reference_type,
            reference_type=reference_type,
            revision_id=record.revision_id,
            content_sha256=record.content_hash,
            based_on_revision_id=record.based_on_revision_id,
            source_property_set_revision_id=content.property_set_revision_id,
            calibration_selection_revision_id=(
                content.calibration_evidence.calibration_selection_revision_id
                if content.calibration_evidence is not None
                else None
            ),
            recorded_at=record.created_at,
            recorded_by=record.created_by,
        )


class MaterialModelRevisionResponse(RevisionMetadataResponse):
    content: ReferenceLinearElasticContentResponse
    ir: dict[str, Any]
    provenance: ModelProvenanceSummary

    @classmethod
    def from_snapshot(
        cls,
        material_model_id: UUID,
        value: RevisionSnapshot[ReferenceLinearElasticContent],
    ) -> MaterialModelRevisionResponse:
        metadata = RevisionMetadataResponse.from_record(value.record, "draft")
        return cls(
            **metadata.model_dump(),
            content=ReferenceLinearElasticContentResponse.from_domain(value.content),
            ir=reference_linear_elastic_ir(
                value.content,
                material_model_id=material_model_id,
                material_model_revision_id=value.record.revision_id,
            ),
            provenance=ModelProvenanceSummary.from_record(value.record, value.content),
        )


class MaterialModelResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    material_model_id: UUID
    material_state_id: UUID
    current_revision: MaterialModelRevisionResponse
    links: dict[str, str]

    @classmethod
    def from_snapshot(cls, value: MaterialModelSnapshot) -> MaterialModelResponse:
        root = f"/api/v1/material-models/{value.id}"
        return cls(
            material_model_id=value.id,
            material_state_id=value.material_state_id,
            current_revision=MaterialModelRevisionResponse.from_snapshot(value.id, value.current),
            links={
                "self": root,
                "revisions": f"{root}/revisions",
                "preflight": f"{root}/preflight",
                "solver_cards": f"{root}/solver-cards",
            },
        )


class MaterialModelListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: tuple[MaterialModelResponse, ...]


class MaterialModelRevisionListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    material_model_id: UUID
    revisions: tuple[MaterialModelRevisionResponse, ...]


class ModelingProblem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Label
    title: Label
    status: Annotated[int, Field(ge=400, le=599)]
    detail: Annotated[str, StringConstraints(min_length=1, max_length=2000)]
    code: Annotated[str, StringConstraints(pattern=r"^CMP-MODELING-[0-9]{4}$")]
    trace_id: Label


class ModelingHttpError(Exception):
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
        self.problem = ModelingProblem(
            type="urn:cmp:problem:modeling",
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
        raise RuntimeError("Material Model route dependencies did not initialize request scope")
    return context, decision


def _unavailable(context: SecurityContext) -> ModelingHttpError:
    return ModelingHttpError(
        context=context,
        status_code=503,
        title="Material Model service unavailable",
        detail="The authoritative Material Model store is not configured for this deployment.",
        code="CMP-MODELING-0005",
    )


def _translate(context: SecurityContext, error: Exception) -> ModelingHttpError:
    if isinstance(error, (ReferenceModelNotFound, AggregateNotFound)):
        return ModelingHttpError(
            context=context,
            status_code=404,
            title="Material Model resource not found",
            detail=(
                "No requested concrete Material Model or Property Set revision is visible "
                "in this tenant."
            ),
            code="CMP-MODELING-0001",
        )
    if isinstance(error, (InvalidReferenceModel, ValueError)):
        return ModelingHttpError(
            context=context,
            status_code=422,
            title="Invalid Material Model request",
            detail=(
                "The reference linear-elastic IR requires valid typed SI values and a concrete "
                "source revision."
            ),
            code="CMP-MODELING-0002",
        )
    if isinstance(error, (ReferenceModelConflict, RevisionKernelError, IntegrityError)):
        return ModelingHttpError(
            context=context,
            status_code=409,
            title="Material Model state conflict",
            detail="The Material Model command conflicts with immutable source or revision state.",
            code="CMP-MODELING-0003",
        )
    return ModelingHttpError(
        context=context,
        status_code=409,
        title="Material Model command rejected",
        detail="The reference Material Model command could not be completed.",
        code="CMP-MODELING-0003",
    )


def _etag(response: Response, record: RevisionRecord) -> None:
    response.headers["ETag"] = str(RevisionETag.from_ref(record.ref))
    response.headers["Cache-Control"] = "no-store"


def install_material_model_api(
    application: FastAPI,
    *,
    service: MaterialModelService | None,
    security_dependency: Dependency,
    read_dependency: Dependency,
    write_dependency: Dependency,
) -> None:
    @application.exception_handler(ModelingHttpError)
    async def modeling_error_handler(
        request: Request, error: ModelingHttpError
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
        403: {"description": "Modeling permission is not authorized."},
        404: {"model": ModelingProblem},
        409: {"model": ModelingProblem},
        422: {"model": ModelingProblem},
        503: {"model": ModelingProblem},
    }

    @application.post(
        "/api/v1/material-states/{material_state_id}/material-models",
        operation_id="createReferenceLinearElasticMaterialModel",
        response_model=MaterialModelResponse,
        status_code=status.HTTP_201_CREATED,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(write_dependency)],
        tags=["modeling"],
        summary=(
            "Create a non-production reference linear-elastic IR from one Property Set revision."
        ),
    )
    def create_reference_linear_elastic_material_model(
        request: Request,
        response: Response,
        material_state_id: UUID,
        body: ReferenceModelCreateRequest,
    ) -> MaterialModelResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            value = service.create_reference_linear_elastic_model(
                context,
                decision,
                CreateReferenceLinearElasticModel(
                    material_state_id=material_state_id,
                    property_set_revision_id=body.property_set_revision_id,
                    change_reason=body.change_reason,
                ),
            )
        except (ModelingError, RevisionKernelError, IntegrityError, ValueError) as error:
            raise _translate(context, error) from error
        _etag(response, value.current.record)
        return MaterialModelResponse.from_snapshot(value)

    @application.get(
        "/api/v1/material-states/{material_state_id}/material-models",
        operation_id="listMaterialModelsForState",
        response_model=MaterialModelListResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["modeling"],
        summary="List current Material Model IR revisions for one Material State.",
    )
    def list_material_models_for_state(
        request: Request, material_state_id: UUID
    ) -> MaterialModelListResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            values = service.list_material_models_for_state(context, decision, material_state_id)
        except (ModelingError, RevisionKernelError, IntegrityError, ValueError) as error:
            raise _translate(context, error) from error
        return MaterialModelListResponse(
            items=tuple(MaterialModelResponse.from_snapshot(value) for value in values)
        )

    @application.get(
        "/api/v1/material-models/{material_model_id}",
        operation_id="getMaterialModel",
        response_model=MaterialModelResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["modeling"],
        summary="Read one current immutable Material Model IR revision.",
    )
    def get_material_model(
        request: Request, response: Response, material_model_id: UUID
    ) -> MaterialModelResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            value = service.get_material_model(context, decision, material_model_id)
        except (ModelingError, RevisionKernelError, IntegrityError, ValueError) as error:
            raise _translate(context, error) from error
        _etag(response, value.current.record)
        return MaterialModelResponse.from_snapshot(value)

    @application.get(
        "/api/v1/material-models/{material_model_id}/revisions",
        operation_id="listMaterialModelRevisions",
        response_model=MaterialModelRevisionListResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["modeling"],
        summary="List immutable revisions for one Material Model IR.",
    )
    def list_material_model_revisions(
        request: Request, material_model_id: UUID
    ) -> MaterialModelRevisionListResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            values = service.list_material_model_revisions(context, decision, material_model_id)
        except (ModelingError, RevisionKernelError, IntegrityError, ValueError) as error:
            raise _translate(context, error) from error
        return MaterialModelRevisionListResponse(
            material_model_id=material_model_id,
            revisions=tuple(
                MaterialModelRevisionResponse.from_snapshot(material_model_id, value)
                for value in values
            ),
        )

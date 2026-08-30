"""Protected API for the bounded reference linear-viscoelastic Prony IR."""

from __future__ import annotations

import logging
import math
from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends, FastAPI, Query, Request, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from cmp.modules.identity_access.domain.authorization import AuthorizationDecision
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.modeling.application.linear_viscoelasticity import (
    CreateReferenceLinearViscoelasticModel,
    LinearViscoelasticModelService,
    LinearViscoelasticModelSnapshot,
    PromotePronyProcessingOutput,
)
from cmp.modules.modeling.domain.reference_linear_viscoelasticity import (
    BulkRelaxationStatus,
    InvalidLinearViscoelasticModel,
    LinearViscoelasticConflict,
    LinearViscoelasticNotFound,
    PronyTerm,
    ReferenceLinearViscoelasticContent,
    evaluate_relaxation,
    reference_linear_viscoelastic_canonical,
)
from cmp.shared.contracts.revisions import RevisionETag, RevisionMetadataResponse

type Dependency = Callable[..., object]
type Reason = Annotated[str, StringConstraints(min_length=1, max_length=2000)]

logger = logging.getLogger(__name__)


class PronyTermRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    g_ratio: Annotated[float, Field(ge=0, lt=1)]
    k_ratio: Annotated[float, Field(ge=0, lt=1)]
    relaxation_time_s: Annotated[float, Field(gt=0)]


class LinearViscoelasticCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    property_set_revision_id: UUID
    bulk_relaxation_status: BulkRelaxationStatus
    terms: Annotated[tuple[PronyTermRequest, ...], Field(min_length=1, max_length=5)]
    change_reason: Reason


class ProcessingOutputPromotionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    material_state_id: UUID
    property_set_revision_id: UUID
    processing_output_revision_id: UUID
    acknowledged_maximum_relative_mismatch: Annotated[float, Field(ge=0, le=1)]
    review_acknowledged: bool
    change_reason: Reason


class PronyTermResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ordinal: int
    g_ratio: float
    k_ratio: float
    relaxation_time_s: float


class LinearViscoelasticContentResponse(BaseModel):
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
    elastic_moduli_convention: str
    bulk_relaxation_status: BulkRelaxationStatus
    terms: tuple[PronyTermResponse, ...]
    reference_temperature_k: float
    non_production: bool
    prony_promotion_evidence: dict[str, object] | None = None
    processing_promotion_evidence: dict[str, object] | None = None
    calibration_promotion_evidence: dict[str, object] | None = None

    @classmethod
    def from_domain(
        cls, value: ReferenceLinearViscoelasticContent, schema_version: str
    ) -> LinearViscoelasticContentResponse:
        canonical = reference_linear_viscoelastic_canonical(value)
        promotion_evidence = canonical.get("prony_promotion_evidence")
        if not isinstance(promotion_evidence, dict):
            promotion_evidence = None
        processing_evidence = canonical.get("processing_promotion_evidence")
        if not isinstance(processing_evidence, dict):
            processing_evidence = None
        calibration_evidence = canonical.get("calibration_promotion_evidence")
        if not isinstance(calibration_evidence, dict):
            calibration_evidence = None
        return cls(
            model_family_id=value.model_family_id,
            model_schema_version=schema_version,
            model_schema_digest=f"sha256:{value.model_schema_digest}",
            material_id=value.material_id,
            material_revision_id=value.material_revision_id,
            material_state_id=value.material_state_id,
            material_state_revision_id=value.material_state_revision_id,
            property_set_id=value.property_set_id,
            property_set_revision_id=value.property_set_revision_id,
            density_kg_per_m3=value.density_kg_per_m3,
            youngs_modulus_pa=value.youngs_modulus_pa,
            poisson_ratio=value.poisson_ratio,
            elastic_moduli_convention=value.elastic_moduli_convention,
            bulk_relaxation_status=value.bulk_relaxation_status,
            terms=tuple(
                PronyTermResponse(
                    ordinal=index,
                    g_ratio=term.g_ratio,
                    k_ratio=term.k_ratio,
                    relaxation_time_s=term.relaxation_time_s,
                )
                for index, term in enumerate(value.terms, 1)
            ),
            reference_temperature_k=value.reference_temperature_k,
            non_production=value.non_production,
            prony_promotion_evidence=promotion_evidence,
            processing_promotion_evidence=processing_evidence,
            calibration_promotion_evidence=calibration_evidence,
        )


class LinearViscoelasticRevisionResponse(RevisionMetadataResponse):
    content: LinearViscoelasticContentResponse
    ir: dict[str, object]


class LinearViscoelasticModelResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    material_model_id: UUID
    material_state_id: UUID
    current_revision: LinearViscoelasticRevisionResponse
    links: dict[str, str]

    @classmethod
    def from_snapshot(
        cls, value: LinearViscoelasticModelSnapshot
    ) -> LinearViscoelasticModelResponse:
        metadata = RevisionMetadataResponse.from_record(value.current.record, "draft")
        root = f"/api/v1/linear-viscoelastic-models/{value.id}"
        return cls(
            material_model_id=value.id,
            material_state_id=value.material_state_id,
            current_revision=LinearViscoelasticRevisionResponse(
                **metadata.model_dump(),
                content=LinearViscoelasticContentResponse.from_domain(
                    value.current.content, value.current.record.schema_version
                ),
                ir=reference_linear_viscoelastic_canonical(value.current.content),
            ),
            links={"self": root, "response": f"{root}/response"},
        )


class LinearViscoelasticListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: tuple[LinearViscoelasticModelResponse, ...]


class RelaxationPointResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    time_s: float
    shear_modulus_pa: float
    bulk_modulus_pa: float


class RelaxationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    material_model_id: UUID
    material_model_revision_id: UUID
    elastic_moduli_convention: str
    time_unit: str
    modulus_unit: str
    points: tuple[RelaxationPointResponse, ...]


class LinearViscoelasticProblem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    title: str
    status: int
    detail: str
    code: str
    trace_id: str


class LinearViscoelasticHttpError(Exception):
    def __init__(self, context: SecurityContext, status_code: int, detail: str) -> None:
        self.problem = LinearViscoelasticProblem(
            type="urn:cmp:problem:modeling:linear-viscoelasticity",
            title="Linear-viscoelastic Material Model request failed",
            status=status_code,
            detail=detail,
            code=f"CMP-MODELING-{status_code}",
            trace_id=context.trace_id,
        )
        super().__init__(detail)


def _scope(request: Request) -> tuple[SecurityContext, AuthorizationDecision]:
    context = getattr(request.state, "security_context", None)
    decision = getattr(request.state, "authorization_decision", None)
    if not isinstance(context, SecurityContext) or not isinstance(decision, AuthorizationDecision):
        raise RuntimeError("linear-viscoelastic dependencies did not initialize request scope")
    return context, decision


def _translate(context: SecurityContext, error: Exception) -> LinearViscoelasticHttpError:
    if isinstance(error, LinearViscoelasticNotFound):
        return LinearViscoelasticHttpError(context, 404, str(error))
    if isinstance(error, LinearViscoelasticConflict):
        return LinearViscoelasticHttpError(context, 409, str(error))
    if isinstance(error, (InvalidLinearViscoelasticModel, ValueError)):
        return LinearViscoelasticHttpError(context, 422, str(error))
    logger.exception("unexpected linear-viscoelastic API failure", exc_info=error)
    return LinearViscoelasticHttpError(context, 503, "service is unavailable")


def _default_times(content: ReferenceLinearViscoelasticContent) -> tuple[float, ...]:
    lower = math.log10(content.terms[0].relaxation_time_s / 100)
    upper = math.log10(content.terms[-1].relaxation_time_s * 100)
    return (0.0, *tuple(10 ** (lower + index * (upper - lower) / 39) for index in range(40)))


def install_linear_viscoelastic_api(
    application: FastAPI,
    *,
    service: LinearViscoelasticModelService | None,
    security_dependency: Dependency,
    read_dependency: Dependency,
    write_dependency: Dependency,
) -> None:
    @application.exception_handler(LinearViscoelasticHttpError)
    async def handle_error(_: Request, error: LinearViscoelasticHttpError) -> JSONResponse:
        return JSONResponse(error.problem.model_dump(mode="json"), status_code=error.problem.status)

    errors: dict[int | str, dict[str, Any]] = {
        status_code: {"model": LinearViscoelasticProblem} for status_code in (404, 409, 422, 503)
    }

    @application.post(
        "/api/v1/material-states/{material_state_id}/linear-viscoelastic-models",
        operation_id="createLinearViscoelasticModel",
        response_model=LinearViscoelasticModelResponse,
        status_code=status.HTTP_201_CREATED,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(write_dependency)],
        tags=["modeling"],
    )
    def create_model(
        request: Request,
        response: Response,
        material_state_id: UUID,
        body: LinearViscoelasticCreateRequest,
    ) -> LinearViscoelasticModelResponse:
        context, decision = _scope(request)
        if service is None:
            raise LinearViscoelasticHttpError(context, 503, "service is unavailable")
        try:
            snapshot = service.create_model(
                context,
                decision,
                CreateReferenceLinearViscoelasticModel(
                    material_state_id=material_state_id,
                    property_set_revision_id=body.property_set_revision_id,
                    bulk_relaxation_status=body.bulk_relaxation_status,
                    terms=tuple(
                        PronyTerm(term.g_ratio, term.k_ratio, term.relaxation_time_s)
                        for term in body.terms
                    ),
                    change_reason=body.change_reason,
                ),
            )
        except Exception as error:
            raise _translate(context, error) from error
        response.headers["ETag"] = str(RevisionETag.from_ref(snapshot.current.record.ref))
        response.headers["Location"] = f"/api/v1/linear-viscoelastic-models/{snapshot.id}"
        return LinearViscoelasticModelResponse.from_snapshot(snapshot)

    @application.post(
        "/api/v1/processing-outputs/{processing_output_id}/linear-viscoelastic-models",
        operation_id="promotePronyProcessingOutputToLinearViscoelasticModel",
        response_model=LinearViscoelasticModelResponse,
        status_code=status.HTTP_201_CREATED,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(write_dependency)],
        tags=["modeling"],
        summary="Promote one exact selected generalized-Maxwell Processing Output into IR 1.2.",
    )
    async def promote_processing_output(
        request: Request,
        response: Response,
        processing_output_id: UUID,
        body: ProcessingOutputPromotionRequest,
    ) -> LinearViscoelasticModelResponse:
        context, decision = _scope(request)
        if service is None:
            raise LinearViscoelasticHttpError(context, 503, "service is unavailable")
        try:
            snapshot = await service.promote_processing_output(
                context,
                decision,
                PromotePronyProcessingOutput(
                    material_state_id=body.material_state_id,
                    property_set_revision_id=body.property_set_revision_id,
                    processing_output_id=processing_output_id,
                    processing_output_revision_id=body.processing_output_revision_id,
                    acknowledged_maximum_relative_mismatch=(
                        body.acknowledged_maximum_relative_mismatch
                    ),
                    review_acknowledged=body.review_acknowledged,
                    change_reason=body.change_reason,
                ),
            )
        except Exception as error:
            raise _translate(context, error) from error
        response.headers["ETag"] = str(RevisionETag.from_ref(snapshot.current.record.ref))
        response.headers["Location"] = f"/api/v1/linear-viscoelastic-models/{snapshot.id}"
        return LinearViscoelasticModelResponse.from_snapshot(snapshot)

    @application.get(
        "/api/v1/material-states/{material_state_id}/linear-viscoelastic-models",
        operation_id="listLinearViscoelasticModels",
        response_model=LinearViscoelasticListResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["modeling"],
    )
    def list_models(request: Request, material_state_id: UUID) -> LinearViscoelasticListResponse:
        context, decision = _scope(request)
        if service is None:
            raise LinearViscoelasticHttpError(context, 503, "service is unavailable")
        try:
            values = service.list_models_for_state(context, decision, material_state_id)
        except Exception as error:
            raise _translate(context, error) from error
        return LinearViscoelasticListResponse(
            items=tuple(LinearViscoelasticModelResponse.from_snapshot(value) for value in values)
        )

    @application.get(
        "/api/v1/linear-viscoelastic-models/{material_model_id}",
        operation_id="getLinearViscoelasticModel",
        response_model=LinearViscoelasticModelResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["modeling"],
    )
    def get_model(
        request: Request, response: Response, material_model_id: UUID
    ) -> LinearViscoelasticModelResponse:
        context, decision = _scope(request)
        if service is None:
            raise LinearViscoelasticHttpError(context, 503, "service is unavailable")
        try:
            snapshot = service.get_model(context, decision, material_model_id)
        except Exception as error:
            raise _translate(context, error) from error
        response.headers["ETag"] = str(RevisionETag.from_ref(snapshot.current.record.ref))
        return LinearViscoelasticModelResponse.from_snapshot(snapshot)

    @application.get(
        "/api/v1/linear-viscoelastic-models/{material_model_id}/response",
        operation_id="previewLinearViscoelasticResponse",
        response_model=RelaxationResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["modeling"],
    )
    def response_preview(
        request: Request,
        material_model_id: UUID,
        time_s: Annotated[list[float] | None, Query()] = None,
    ) -> RelaxationResponse:
        context, decision = _scope(request)
        if service is None:
            raise LinearViscoelasticHttpError(context, 503, "service is unavailable")
        try:
            snapshot = service.get_model(context, decision, material_model_id)
            times = (
                tuple(time_s) if time_s is not None else _default_times(snapshot.current.content)
            )
            points = evaluate_relaxation(snapshot.current.content, times)
        except Exception as error:
            raise _translate(context, error) from error
        return RelaxationResponse(
            material_model_id=snapshot.id,
            material_model_revision_id=snapshot.current.record.revision_id,
            elastic_moduli_convention="instantaneous",
            time_unit="s",
            modulus_unit="Pa",
            points=tuple(
                RelaxationPointResponse(
                    time_s=point.time_s,
                    shear_modulus_pa=point.relaxation_shear_modulus_pa,
                    bulk_modulus_pa=point.relaxation_bulk_modulus_pa,
                )
                for point in points
            ),
        )

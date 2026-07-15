"""HTTP contract for explicit reference shear-relaxation processing."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends, FastAPI, Request, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.processing.application.shear_relaxation import (
    CreateShearRelaxationCropRecipe,
    ExecuteShearRelaxationCrop,
    ShearRelaxationProcessingRun,
    ShearRelaxationProcessingService,
    ShearRelaxationRecipeSnapshot,
)
from cmp.modules.processing.domain.reference_shear_relaxation_crop import (
    REFERENCE_SHEAR_RELAXATION_CROP_INPUT_SCHEMA,
    REFERENCE_SHEAR_RELAXATION_CROP_OUTPUT_SCHEMA,
    REFERENCE_SHEAR_RELAXATION_CROP_RECIPE_KIND,
    ReferenceShearRelaxationCropRecipeContent,
)
from cmp.modules.processing.domain.reference_tensile_crop import (
    InvalidProcessingRequest,
    ProcessingConflict,
    ProcessingError,
    ProcessingNotFound,
)
from cmp.shared.contracts.revisions import RevisionETag, RevisionMetadataResponse

type Dependency = Callable[..., object]
type Reason = Annotated[str, StringConstraints(min_length=1, max_length=2000)]


class CreateShearRelaxationRecipeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    classification: DataClassification
    recipe_label: Annotated[str, StringConstraints(min_length=1, max_length=160)]
    minimum_time_s: Annotated[float, Field(ge=0)]
    maximum_time_s: Annotated[float, Field(gt=0)]
    change_reason: Reason


class ExecuteShearRelaxationCropRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recipe_id: UUID
    recipe_revision_id: UUID
    input_dataset_id: UUID
    input_dataset_revision_id: UUID
    change_reason: Reason


class ShearRelaxationRecipeContentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recipe_kind: str = REFERENCE_SHEAR_RELAXATION_CROP_RECIPE_KIND
    recipe_label: str
    minimum_time_s: float
    maximum_time_s: float
    input_schema_ref: str = REFERENCE_SHEAR_RELAXATION_CROP_INPUT_SCHEMA
    output_schema_ref: str = REFERENCE_SHEAR_RELAXATION_CROP_OUTPUT_SCHEMA
    boundary_policy: str = "select_observed_points_inclusive_no_interpolation"


class ShearRelaxationRecipeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recipe_id: UUID
    current_revision: RevisionMetadataResponse
    content: ShearRelaxationRecipeContentResponse
    links: dict[str, str]

    @classmethod
    def from_domain(cls, value: ShearRelaxationRecipeSnapshot) -> ShearRelaxationRecipeResponse:
        content = value.current.content
        return cls(
            recipe_id=value.id,
            current_revision=RevisionMetadataResponse.from_record(
                value.current.record, "draft"
            ),
            content=ShearRelaxationRecipeContentResponse(
                recipe_label=content.recipe_label,
                minimum_time_s=content.minimum_time_s,
                maximum_time_s=content.maximum_time_s,
            ),
            links={"execute": "/api/v1/processing-runs/reference-shear-relaxation-crop"},
        )


class ShearRelaxationProcessingRunResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    processing_run_id: UUID
    classification: DataClassification
    recipe_id: UUID
    recipe_revision_id: UUID
    input_dataset_id: UUID
    input_dataset_revision_id: UUID
    status: str
    input_point_count: int
    output_point_count: int | None
    removed_point_count: int | None
    result_artifact_id: UUID | None
    result_sha256: str | None
    output_dataset_id: UUID | None
    output_dataset_revision_id: UUID | None
    failure_code: str | None
    started_at: str
    ended_at: str | None
    links: dict[str, str]

    @classmethod
    def from_domain(
        cls, value: ShearRelaxationProcessingRun
    ) -> ShearRelaxationProcessingRunResponse:
        links = {
            "self": f"/api/v1/processing-runs/reference-shear-relaxation/{value.id}",
            "input_dataset": (
                f"/api/v1/shear-relaxation-datasets/{value.input_dataset_id}/preview"
            ),
        }
        if value.output_dataset_id is not None:
            links["output_dataset"] = (
                f"/api/v1/shear-relaxation-datasets/{value.output_dataset_id}/preview"
            )
        return cls(
            processing_run_id=value.id,
            classification=value.classification,
            recipe_id=value.recipe_id,
            recipe_revision_id=value.recipe_revision_id,
            input_dataset_id=value.input_dataset_id,
            input_dataset_revision_id=value.input_dataset_revision_id,
            status=value.status.value,
            input_point_count=value.input_point_count,
            output_point_count=value.output_point_count,
            removed_point_count=value.removed_point_count,
            result_artifact_id=value.result_artifact_id,
            result_sha256=value.result_sha256,
            output_dataset_id=value.output_dataset_id,
            output_dataset_revision_id=value.output_dataset_revision_id,
            failure_code=value.failure_code,
            started_at=value.started_at.isoformat(),
            ended_at=value.ended_at.isoformat() if value.ended_at else None,
            links=links,
        )


class ProcessingProblem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    title: str
    status: int
    detail: str
    code: str
    trace_id: str


class ProcessingHttpError(Exception):
    def __init__(self, context: SecurityContext, status_code: int, title: str, code: str) -> None:
        self.context = context
        self.problem = ProcessingProblem(
            type="urn:cmp:problem:shear-relaxation-processing",
            title=title,
            status=status_code,
            detail="The explicit shear-relaxation Processing command could not be completed.",
            code=code,
            trace_id=context.trace_id,
        )
        super().__init__(title)


def _scope(request: Request) -> tuple[SecurityContext, AuthorizationDecision]:
    context = getattr(request.state, "security_context", None)
    decision = getattr(request.state, "authorization_decision", None)
    if not isinstance(context, SecurityContext) or not isinstance(decision, AuthorizationDecision):
        raise RuntimeError("Processing route dependencies did not initialize request scope")
    return context, decision


def _translate(context: SecurityContext, error: Exception) -> ProcessingHttpError:
    if isinstance(error, ProcessingNotFound):
        return ProcessingHttpError(
            context, 404, "Processing resource not found", "CMP-PROCESSING-0101"
        )
    if isinstance(error, (InvalidProcessingRequest, ValueError)):
        return ProcessingHttpError(
            context, 422, "Invalid Processing request", "CMP-PROCESSING-0102"
        )
    if isinstance(error, (ProcessingConflict, ProcessingError)):
        return ProcessingHttpError(context, 409, "Processing state conflict", "CMP-PROCESSING-0103")
    return ProcessingHttpError(context, 409, "Processing command rejected", "CMP-PROCESSING-0103")


def install_shear_relaxation_processing_api(
    application: FastAPI,
    *,
    service: ShearRelaxationProcessingService | None,
    security_dependency: Dependency,
    read_dependency: Dependency,
    execute_dependency: Dependency,
) -> None:
    @application.exception_handler(ProcessingHttpError)
    async def error_handler(request: Request, error: ProcessingHttpError) -> JSONResponse:
        del request
        return JSONResponse(
            status_code=error.problem.status,
            content=error.problem.model_dump(mode="json"),
            media_type="application/problem+json",
        )

    errors: dict[int | str, dict[str, Any]] = {
        401: {"description": "Authentication required."},
        403: {"model": ProcessingProblem},
        404: {"model": ProcessingProblem},
        409: {"model": ProcessingProblem},
        422: {"model": ProcessingProblem},
        503: {"model": ProcessingProblem},
    }

    @application.post(
        "/api/v1/processing-recipes/reference-shear-relaxation-crop",
        operation_id="createReferenceShearRelaxationCropRecipe",
        response_model=ShearRelaxationRecipeResponse,
        status_code=status.HTTP_201_CREATED,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(execute_dependency)],
        tags=["processing"],
    )
    def create_recipe(
        request: Request, response: Response, body: CreateShearRelaxationRecipeRequest
    ) -> ShearRelaxationRecipeResponse:
        context, decision = _scope(request)
        if service is None:
            raise ProcessingHttpError(
                context, 503, "Processing service unavailable", "CMP-PROCESSING-0105"
            )
        try:
            result = service.create_recipe(
                context,
                decision,
                CreateShearRelaxationCropRecipe(
                    classification=body.classification,
                    content=ReferenceShearRelaxationCropRecipeContent(
                        body.recipe_label, body.minimum_time_s, body.maximum_time_s
                    ),
                    change_reason=body.change_reason,
                ),
            )
        except Exception as error:
            raise _translate(context, error) from error
        response.headers["Location"] = f"/api/v1/processing-recipes/{result.id}"
        response.headers["ETag"] = str(RevisionETag.from_ref(result.current.record.ref))
        return ShearRelaxationRecipeResponse.from_domain(result)

    @application.post(
        "/api/v1/processing-runs/reference-shear-relaxation-crop",
        operation_id="executeReferenceShearRelaxationCrop",
        response_model=ShearRelaxationProcessingRunResponse,
        status_code=status.HTTP_201_CREATED,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(execute_dependency)],
        tags=["processing"],
    )
    async def execute(
        request: Request, response: Response, body: ExecuteShearRelaxationCropRequest
    ) -> ShearRelaxationProcessingRunResponse:
        context, decision = _scope(request)
        if service is None:
            raise ProcessingHttpError(
                context, 503, "Processing service unavailable", "CMP-PROCESSING-0105"
            )
        try:
            result = await service.execute(
                context,
                decision,
                ExecuteShearRelaxationCrop(**body.model_dump()),
            )
        except Exception as error:
            raise _translate(context, error) from error
        response.headers["Location"] = (
            f"/api/v1/processing-runs/reference-shear-relaxation/{result.id}"
        )
        return ShearRelaxationProcessingRunResponse.from_domain(result)

    @application.get(
        "/api/v1/processing-runs/reference-shear-relaxation/{run_id}",
        operation_id="getReferenceShearRelaxationProcessingRun",
        response_model=ShearRelaxationProcessingRunResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["processing"],
    )
    def get_run(request: Request, run_id: UUID) -> ShearRelaxationProcessingRunResponse:
        context, decision = _scope(request)
        if service is None:
            raise ProcessingHttpError(
                context, 503, "Processing service unavailable", "CMP-PROCESSING-0105"
            )
        try:
            result = service.get_run(context, decision, run_id)
        except Exception as error:
            raise _translate(context, error) from error
        return ShearRelaxationProcessingRunResponse.from_domain(result)

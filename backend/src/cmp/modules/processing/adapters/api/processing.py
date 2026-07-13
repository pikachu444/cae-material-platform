"""Protected HTTP resources for the committed reference tensile crop workflow."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends, FastAPI, Query, Request, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from sqlalchemy.exc import IntegrityError

from cmp.modules.artifacts.domain.content import (
    ArtifactAccessDenied,
    ArtifactError,
    ArtifactIntegrityError,
    ArtifactNotFound,
    InvalidArtifact,
)
from cmp.modules.datasets.domain.reference_tensile import DatasetError, DatasetNotFound
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.processing.application.service import (
    CreateReferenceTensileCropRecipe,
    ExecuteReferenceTensileCrop,
    ProcessingRecipeSnapshot,
    ProcessingRun,
    ProcessingService,
    ReviseReferenceTensileCropRecipe,
    RevisionSnapshot,
)
from cmp.modules.processing.domain.reference_tensile_crop import (
    REFERENCE_TENSILE_CROP_DIAGNOSTICS_SCHEMA,
    REFERENCE_TENSILE_CROP_INPUT_SCHEMA,
    REFERENCE_TENSILE_CROP_OUTPUT_SCHEMA,
    REFERENCE_TENSILE_CROP_RECIPE_KIND,
    InvalidProcessingRequest,
    ProcessingConflict,
    ProcessingError,
    ProcessingNotFound,
    ProcessingRunStatus,
    ReferenceTensileCropRecipeContent,
)
from cmp.shared.contracts.revisions import RevisionETag, RevisionMetadataResponse
from cmp.shared.domain.revisions import RevisionKernelError, RevisionRecord

type Label = Annotated[str, StringConstraints(min_length=1, max_length=255)]
type Dependency = Callable[..., object]


class ReferenceTensileCropRecipeInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recipe_label: Annotated[str, StringConstraints(min_length=1, max_length=160)]
    minimum_engineering_strain: Annotated[float, Field(ge=0)]
    maximum_engineering_strain: float

    def to_domain(self) -> ReferenceTensileCropRecipeContent:
        return ReferenceTensileCropRecipeContent(
            recipe_label=self.recipe_label,
            minimum_engineering_strain=self.minimum_engineering_strain,
            maximum_engineering_strain=self.maximum_engineering_strain,
        )


class CreateReferenceTensileCropRecipeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    classification: DataClassification
    content: ReferenceTensileCropRecipeInput
    change_reason: Annotated[str, StringConstraints(min_length=1, max_length=2000)]


class ReviseReferenceTensileCropRecipeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_current_revision_id: UUID
    recipe_label: Annotated[str, StringConstraints(min_length=1, max_length=160)]
    minimum_engineering_strain: Annotated[float, Field(ge=0)]
    maximum_engineering_strain: float
    change_reason: Annotated[str, StringConstraints(min_length=1, max_length=2000)]


class ExecuteReferenceTensileCropRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    selection_id: UUID
    selection_revision_id: UUID
    recipe_id: UUID
    recipe_revision_id: UUID
    change_reason: Annotated[str, StringConstraints(min_length=1, max_length=2000)]


class ReferenceTensileCropRecipeContentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recipe_kind: str
    step_count: int
    minimum_engineering_strain: float
    maximum_engineering_strain: float
    input_schema_ref: str
    output_schema_ref: str
    diagnostics_schema_ref: str
    boundary_policy: str

    @classmethod
    def from_domain(
        cls, value: ReferenceTensileCropRecipeContent
    ) -> ReferenceTensileCropRecipeContentResponse:
        return cls(
            recipe_kind=REFERENCE_TENSILE_CROP_RECIPE_KIND,
            step_count=1,
            minimum_engineering_strain=value.minimum_engineering_strain,
            maximum_engineering_strain=value.maximum_engineering_strain,
            input_schema_ref=REFERENCE_TENSILE_CROP_INPUT_SCHEMA,
            output_schema_ref=REFERENCE_TENSILE_CROP_OUTPUT_SCHEMA,
            diagnostics_schema_ref=REFERENCE_TENSILE_CROP_DIAGNOSTICS_SCHEMA,
            boundary_policy="select_observed_points_inclusive_no_interpolation",
        )


class ProcessingRecipeRevisionResponse(RevisionMetadataResponse):
    content: ReferenceTensileCropRecipeContentResponse

    @classmethod
    def from_snapshot(
        cls, value: RevisionSnapshot[ReferenceTensileCropRecipeContent]
    ) -> ProcessingRecipeRevisionResponse:
        metadata = RevisionMetadataResponse.from_record(value.record, "draft")
        return cls(
            **metadata.model_dump(),
            content=ReferenceTensileCropRecipeContentResponse.from_domain(value.content),
        )


class ProcessingRecipeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recipe_id: UUID
    recipe_label: str
    current_revision: ProcessingRecipeRevisionResponse
    links: dict[str, str]

    @classmethod
    def from_snapshot(cls, value: ProcessingRecipeSnapshot) -> ProcessingRecipeResponse:
        root = f"/api/v1/processing-recipes/{value.id}"
        return cls(
            recipe_id=value.id,
            recipe_label=value.current.content.recipe_label,
            current_revision=ProcessingRecipeRevisionResponse.from_snapshot(value.current),
            links={"self": root, "revisions": f"{root}/revisions"},
        )


class ProcessingRecipeListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: tuple[ProcessingRecipeResponse, ...]


class ProcessingRunResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    processing_run_id: UUID
    classification: DataClassification
    execution_mode: str
    status: ProcessingRunStatus
    selection_id: UUID
    selection_revision_id: UUID
    recipe_id: UUID
    recipe_revision_id: UUID
    input_dataset_id: UUID
    input_dataset_revision_id: UUID
    input_point_count: int
    output_point_count: int | None
    removed_point_count: int | None
    result_artifact_id: UUID | None
    result_sha256: str | None
    output_dataset_id: UUID | None
    output_dataset_revision_id: UUID | None
    failure_code: str | None
    change_reason: str
    started_at: str
    ended_at: str | None
    links: dict[str, str]

    @classmethod
    def from_domain(cls, value: ProcessingRun) -> ProcessingRunResponse:
        root = f"/api/v1/processing-runs/{value.id}"
        links = {"self": root}
        if value.output_dataset_id is not None:
            links["output_dataset"] = f"/api/v1/datasets/{value.output_dataset_id}"
        if value.output_dataset_revision_id is not None:
            links["output_curve"] = (
                f"/api/v1/dataset-revisions/{value.output_dataset_revision_id}/curve"
            )
        return cls(
            processing_run_id=value.id,
            classification=value.classification,
            execution_mode="committed",
            status=value.status,
            selection_id=value.selection_id,
            selection_revision_id=value.selection_revision_id,
            recipe_id=value.recipe_id,
            recipe_revision_id=value.recipe_revision_id,
            input_dataset_id=value.input_dataset_id,
            input_dataset_revision_id=value.input_dataset_revision_id,
            input_point_count=value.input_point_count,
            output_point_count=value.output_point_count,
            removed_point_count=value.removed_point_count,
            result_artifact_id=value.result_artifact_id,
            result_sha256=value.result_sha256,
            output_dataset_id=value.output_dataset_id,
            output_dataset_revision_id=value.output_dataset_revision_id,
            failure_code=value.failure_code,
            change_reason=value.change_reason,
            started_at=value.started_at.isoformat(),
            ended_at=value.ended_at.isoformat() if value.ended_at is not None else None,
            links=links,
        )


class ProcessingProblem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Label
    title: Label
    status: Annotated[int, Field(ge=400, le=599)]
    detail: Annotated[str, StringConstraints(min_length=1, max_length=2000)]
    code: Annotated[str, StringConstraints(pattern=r"^CMP-PROCESSING-[0-9]{4}$")]
    trace_id: Label


class ProcessingHttpError(Exception):
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
        self.problem = ProcessingProblem(
            type="urn:cmp:problem:processing",
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
        raise RuntimeError("Processing route dependencies did not initialize request scope")
    return context, decision


def _unavailable(context: SecurityContext) -> ProcessingHttpError:
    return ProcessingHttpError(
        context=context,
        status_code=503,
        title="Processing service unavailable",
        detail=(
            "The authoritative Processing, Dataset, or immutable Artifact store is not "
            "configured."
        ),
        code="CMP-PROCESSING-0005",
    )


def _translate(context: SecurityContext, error: Exception) -> ProcessingHttpError:
    if isinstance(error, (ProcessingNotFound, DatasetNotFound, ArtifactNotFound)):
        return ProcessingHttpError(
            context=context,
            status_code=404,
            title="Processing resource not found",
            detail=(
                "No requested Recipe, Selection revision, Dataset revision, or Artifact is "
                "visible."
            ),
            code="CMP-PROCESSING-0001",
        )
    if isinstance(error, (InvalidProcessingRequest, InvalidArtifact, ValueError)):
        return ProcessingHttpError(
            context=context,
            status_code=422,
            title="Invalid Processing request",
            detail=(
                "The reference crop requires finite ordered bounds and declared compatible "
                "input."
            ),
            code="CMP-PROCESSING-0002",
        )
    if isinstance(error, (ArtifactAccessDenied, ArtifactIntegrityError)):
        return ProcessingHttpError(
            context=context,
            status_code=409,
            title="Processing input unavailable",
            detail="The pinned immutable input Artifact is not currently usable for Processing.",
            code="CMP-PROCESSING-0003",
        )
    if isinstance(error, (ProcessingConflict, DatasetError, RevisionKernelError, IntegrityError)):
        return ProcessingHttpError(
            context=context,
            status_code=409,
            title="Processing state conflict",
            detail="The committed run conflicts with immutable pinned input or output state.",
            code="CMP-PROCESSING-0003",
        )
    if isinstance(error, (ProcessingError, ArtifactError)):
        return ProcessingHttpError(
            context=context,
            status_code=409,
            title="Processing command rejected",
            detail="The Processing command could not be completed.",
            code="CMP-PROCESSING-0003",
        )
    return ProcessingHttpError(
        context=context,
        status_code=409,
        title="Processing command rejected",
        detail="The Processing command could not be completed.",
        code="CMP-PROCESSING-0003",
    )


def _etag(response: Response, record: RevisionRecord) -> None:
    response.headers["ETag"] = str(RevisionETag.from_ref(record.ref))
    response.headers["Cache-Control"] = "no-store"


def install_processing_api(
    application: FastAPI,
    *,
    service: ProcessingService | None,
    security_dependency: Dependency,
    read_dependency: Dependency,
    execute_dependency: Dependency,
) -> None:
    @application.exception_handler(ProcessingHttpError)
    async def processing_error_handler(
        request: Request, error: ProcessingHttpError
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
        403: {"model": ProcessingProblem},
        404: {"model": ProcessingProblem},
        409: {"model": ProcessingProblem},
        422: {"model": ProcessingProblem},
        503: {"model": ProcessingProblem},
    }

    @application.post(
        "/api/v1/processing-recipes/reference-tensile-crop",
        operation_id="createReferenceTensileCropRecipe",
        response_model=ProcessingRecipeResponse,
        status_code=status.HTTP_201_CREATED,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(execute_dependency)],
        tags=["processing"],
    )
    def create_recipe(
        request: Request,
        response: Response,
        body: CreateReferenceTensileCropRecipeRequest,
    ) -> ProcessingRecipeResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            result = service.create_reference_tensile_crop_recipe(
                context,
                decision,
                CreateReferenceTensileCropRecipe(
                    classification=body.classification,
                    content=body.content.to_domain(),
                    change_reason=body.change_reason,
                ),
            )
        except Exception as error:
            raise _translate(context, error) from error
        response.headers["Location"] = f"/api/v1/processing-recipes/{result.id}"
        _etag(response, result.current.record)
        return ProcessingRecipeResponse.from_snapshot(result)

    @application.get(
        "/api/v1/processing-recipes",
        operation_id="listProcessingRecipes",
        response_model=ProcessingRecipeListResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["processing"],
    )
    def list_recipes(
        request: Request,
        limit: Annotated[int, Query(ge=1, le=200)] = 100,
    ) -> ProcessingRecipeListResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            items = service.list_recipes(context, decision, limit=limit)
        except Exception as error:
            raise _translate(context, error) from error
        return ProcessingRecipeListResponse(
            items=tuple(ProcessingRecipeResponse.from_snapshot(item) for item in items)
        )

    @application.get(
        "/api/v1/processing-recipes/{recipe_id}",
        operation_id="getProcessingRecipe",
        response_model=ProcessingRecipeResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["processing"],
    )
    def get_recipe(
        request: Request, response: Response, recipe_id: UUID
    ) -> ProcessingRecipeResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            result = service.get_recipe(context, decision, recipe_id)
        except Exception as error:
            raise _translate(context, error) from error
        _etag(response, result.current.record)
        return ProcessingRecipeResponse.from_snapshot(result)

    @application.post(
        "/api/v1/processing-recipes/{recipe_id}/revisions",
        operation_id="reviseReferenceTensileCropRecipe",
        response_model=ProcessingRecipeResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(execute_dependency)],
        tags=["processing"],
    )
    def revise_recipe(
        request: Request,
        response: Response,
        recipe_id: UUID,
        body: ReviseReferenceTensileCropRecipeRequest,
    ) -> ProcessingRecipeResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            result = service.revise_reference_tensile_crop_recipe(
                context,
                decision,
                recipe_id,
                ReviseReferenceTensileCropRecipe(
                    expected_current_revision_id=body.expected_current_revision_id,
                    content=ReferenceTensileCropRecipeContent(
                        recipe_label=body.recipe_label,
                        minimum_engineering_strain=body.minimum_engineering_strain,
                        maximum_engineering_strain=body.maximum_engineering_strain,
                    ),
                    change_reason=body.change_reason,
                ),
            )
        except Exception as error:
            raise _translate(context, error) from error
        _etag(response, result.current.record)
        return ProcessingRecipeResponse.from_snapshot(result)

    @application.post(
        "/api/v1/processing-runs/reference-tensile-crop",
        operation_id="executeReferenceTensileCrop",
        response_model=ProcessingRunResponse,
        status_code=status.HTTP_201_CREATED,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(execute_dependency)],
        tags=["processing"],
    )
    async def execute_crop(
        request: Request,
        response: Response,
        body: ExecuteReferenceTensileCropRequest,
    ) -> ProcessingRunResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            result = await service.execute_reference_tensile_crop(
                context,
                decision,
                ExecuteReferenceTensileCrop(
                    selection_id=body.selection_id,
                    selection_revision_id=body.selection_revision_id,
                    recipe_id=body.recipe_id,
                    recipe_revision_id=body.recipe_revision_id,
                    change_reason=body.change_reason,
                ),
            )
        except Exception as error:
            raise _translate(context, error) from error
        response.headers["Location"] = f"/api/v1/processing-runs/{result.id}"
        response.headers["Cache-Control"] = "no-store"
        return ProcessingRunResponse.from_domain(result)

    @application.get(
        "/api/v1/processing-runs/{run_id}",
        operation_id="getProcessingRun",
        response_model=ProcessingRunResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["processing"],
    )
    def get_run(request: Request, run_id: UUID) -> ProcessingRunResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            result = service.get_run(context, decision, run_id)
        except Exception as error:
            raise _translate(context, error) from error
        return ProcessingRunResponse.from_domain(result)

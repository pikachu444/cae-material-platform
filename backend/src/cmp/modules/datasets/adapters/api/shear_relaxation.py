"""HTTP resources for typed reference shear-relaxation Dataset revisions."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends, FastAPI, Query, Request, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from sqlalchemy.exc import IntegrityError

from cmp.modules.datasets.application.shear_relaxation import (
    ImportReferenceShearRelaxationCsv,
    ShearRelaxationCurvePreview,
    ShearRelaxationDatasetService,
    ShearRelaxationDatasetSnapshot,
)
from cmp.modules.datasets.domain.reference_shear_relaxation import (
    InvalidShearRelaxationData,
    ShearRelaxationConflict,
    ShearRelaxationError,
    ShearRelaxationMapping,
    ShearRelaxationNotFound,
)
from cmp.modules.identity_access.domain.authorization import AuthorizationDecision
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.shared.contracts.revisions import RevisionETag, RevisionMetadataResponse
from cmp.shared.domain.revisions import AggregateAlreadyExists, RevisionKernelError

type Dependency = Callable[..., object]
type Text = Annotated[str, StringConstraints(min_length=1, max_length=255)]

logger = logging.getLogger(__name__)


class ShearRelaxationMappingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    time_column: Text
    shear_modulus_column: Text
    time_unit: Annotated[str, StringConstraints(pattern=r"^(s|ms|min|h)$")]
    shear_modulus_unit: Annotated[str, StringConstraints(pattern=r"^(Pa|kPa|MPa|GPa)$")]


class ShearRelaxationImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    test_run_id: UUID
    test_run_revision_id: UUID
    raw_asset_id: UUID
    raw_artifact_id: UUID
    mapping: ShearRelaxationMappingRequest
    change_reason: Annotated[str, StringConstraints(min_length=1, max_length=2000)]


class ShearRelaxationContentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    material_state_id: UUID
    material_state_revision_id: UUID
    test_run_id: UUID
    test_run_revision_id: UUID
    raw_asset_id: UUID
    raw_artifact_id: UUID
    data_artifact_id: UUID
    data_sha256: str
    representation: str
    source_dataset_revision_id: UUID | None
    processing_run_id: UUID | None
    point_count: int
    time_column: str
    shear_modulus_column: str
    time_original_unit: str
    shear_modulus_original_unit: str
    normalized_time_unit: str = "s"
    normalized_shear_modulus_unit: str = "Pa"
    importer_id: str
    importer_version: str


class ShearRelaxationRevisionResponse(RevisionMetadataResponse):
    content: ShearRelaxationContentResponse


class ShearRelaxationDatasetResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset_id: UUID
    material_state_id: UUID
    current_revision: ShearRelaxationRevisionResponse
    links: dict[str, str]

    @classmethod
    def from_snapshot(cls, value: ShearRelaxationDatasetSnapshot) -> ShearRelaxationDatasetResponse:
        content = value.current.content
        metadata = RevisionMetadataResponse.from_record(value.current.record, "draft")
        root = f"/api/v1/shear-relaxation-datasets/{value.id}"
        return cls(
            dataset_id=value.id,
            material_state_id=value.material_state_id,
            current_revision=ShearRelaxationRevisionResponse(
                **metadata.model_dump(),
                content=ShearRelaxationContentResponse(
                    material_state_id=content.material_state_id,
                    material_state_revision_id=content.material_state_revision_id,
                    test_run_id=content.test_run_id,
                    test_run_revision_id=content.test_run_revision_id,
                    raw_asset_id=content.raw_asset_id,
                    raw_artifact_id=content.raw_artifact_id,
                    data_artifact_id=content.data_artifact_id,
                    data_sha256=content.data_sha256,
                    representation=content.representation,
                    source_dataset_revision_id=content.source_dataset_revision_id,
                    processing_run_id=content.processing_run_id,
                    point_count=content.point_count,
                    time_column=content.mapping.time_column,
                    shear_modulus_column=content.mapping.shear_modulus_column,
                    time_original_unit=content.mapping.time_unit,
                    shear_modulus_original_unit=content.mapping.shear_modulus_unit,
                    importer_id=content.importer_id,
                    importer_version=content.importer_version,
                ),
            ),
            links={"self": root, "preview": f"{root}/preview"},
        )


class ShearRelaxationDatasetListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: tuple[ShearRelaxationDatasetResponse, ...]


class ShearRelaxationPointResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    time: float
    shear_modulus: float


class ShearRelaxationPreviewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset_id: UUID
    dataset_revision_id: UUID
    representation: str
    point_count: int
    returned_point_count: int
    time_unit: str
    shear_modulus_unit: str
    points: tuple[ShearRelaxationPointResponse, ...]

    @classmethod
    def from_domain(cls, value: ShearRelaxationCurvePreview) -> ShearRelaxationPreviewResponse:
        return cls(
            dataset_id=value.dataset_id,
            dataset_revision_id=value.dataset_revision_id,
            representation=value.representation,
            point_count=value.point_count,
            returned_point_count=value.returned_point_count,
            time_unit=value.time_unit,
            shear_modulus_unit=value.modulus_unit,
            points=tuple(
                ShearRelaxationPointResponse(
                    time=point.time_s, shear_modulus=point.shear_modulus_pa
                )
                for point in value.points
            ),
        )


class ShearRelaxationProblem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    title: str
    status: Annotated[int, Field(ge=400, le=599)]
    detail: str
    code: str
    trace_id: str


class ShearRelaxationHttpError(Exception):
    def __init__(self, context: SecurityContext, status_code: int, title: str, code: str) -> None:
        self.context = context
        self.problem = ShearRelaxationProblem(
            type="urn:cmp:problem:shear-relaxation-dataset",
            title=title,
            status=status_code,
            detail=title,
            code=code,
            trace_id=context.trace_id,
        )
        super().__init__(title)


def _scope(request: Request) -> tuple[SecurityContext, AuthorizationDecision]:
    context = getattr(request.state, "security_context", None)
    decision = getattr(request.state, "authorization_decision", None)
    if not isinstance(context, SecurityContext) or not isinstance(decision, AuthorizationDecision):
        raise RuntimeError("Dataset route dependencies did not initialize request scope")
    return context, decision


def _translate(context: SecurityContext, error: Exception) -> ShearRelaxationHttpError:
    logger.warning("shear-relaxation Dataset request failed", exc_info=error)
    if isinstance(error, ShearRelaxationNotFound):
        return ShearRelaxationHttpError(context, 404, "Dataset not found", "CMP-DATASET-0101")
    if isinstance(error, (InvalidShearRelaxationData, ValueError)):
        return ShearRelaxationHttpError(
            context, 422, "Invalid shear-relaxation data", "CMP-DATASET-0102"
        )
    if isinstance(
        error,
        (
            ShearRelaxationConflict,
            ShearRelaxationError,
            AggregateAlreadyExists,
            RevisionKernelError,
            IntegrityError,
        ),
    ):
        return ShearRelaxationHttpError(
            context, 409, "Shear-relaxation Dataset conflict", "CMP-DATASET-0103"
        )
    return ShearRelaxationHttpError(
        context, 409, "Shear-relaxation Dataset rejected", "CMP-DATASET-0103"
    )


def install_shear_relaxation_dataset_api(
    application: FastAPI,
    *,
    service: ShearRelaxationDatasetService | None,
    security_dependency: Dependency,
    read_dependency: Dependency,
    write_dependency: Dependency,
) -> None:
    @application.exception_handler(ShearRelaxationHttpError)
    async def error_handler(request: Request, error: ShearRelaxationHttpError) -> JSONResponse:
        del request
        return JSONResponse(
            status_code=error.problem.status,
            content=error.problem.model_dump(mode="json"),
            media_type="application/problem+json",
            headers={"Cache-Control": "no-store"},
        )

    errors: dict[int | str, dict[str, Any]] = {
        401: {"description": "Authentication required."},
        403: {"model": ShearRelaxationProblem},
        404: {"model": ShearRelaxationProblem},
        409: {"model": ShearRelaxationProblem},
        422: {"model": ShearRelaxationProblem},
        503: {"model": ShearRelaxationProblem},
    }

    @application.post(
        "/api/v1/shear-relaxation-datasets",
        operation_id="importReferenceShearRelaxationDataset",
        response_model=ShearRelaxationDatasetResponse,
        status_code=status.HTTP_201_CREATED,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(write_dependency)],
        tags=["datasets"],
    )
    async def import_dataset(
        request: Request, response: Response, body: ShearRelaxationImportRequest
    ) -> ShearRelaxationDatasetResponse:
        context, decision = _scope(request)
        if service is None:
            raise ShearRelaxationHttpError(
                context, 503, "Dataset service unavailable", "CMP-DATASET-0105"
            )
        try:
            result = await service.import_csv(
                context,
                decision,
                ImportReferenceShearRelaxationCsv(
                    test_run_id=body.test_run_id,
                    test_run_revision_id=body.test_run_revision_id,
                    raw_asset_id=body.raw_asset_id,
                    raw_artifact_id=body.raw_artifact_id,
                    mapping=ShearRelaxationMapping(
                        body.mapping.time_column,
                        body.mapping.shear_modulus_column,
                        body.mapping.time_unit,
                        body.mapping.shear_modulus_unit,
                    ),
                    change_reason=body.change_reason,
                ),
            )
        except Exception as error:
            raise _translate(context, error) from error
        response.headers["Location"] = f"/api/v1/shear-relaxation-datasets/{result.id}"
        response.headers["ETag"] = str(RevisionETag.from_ref(result.current.record.ref))
        return ShearRelaxationDatasetResponse.from_snapshot(result)

    @application.get(
        "/api/v1/material-states/{material_state_id}/shear-relaxation-datasets",
        operation_id="listMaterialStateShearRelaxationDatasets",
        response_model=ShearRelaxationDatasetListResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["datasets"],
    )
    def list_datasets(
        request: Request, material_state_id: UUID
    ) -> ShearRelaxationDatasetListResponse:
        context, decision = _scope(request)
        if service is None:
            raise ShearRelaxationHttpError(
                context, 503, "Dataset service unavailable", "CMP-DATASET-0105"
            )
        try:
            items = service.list_for_material_state(context, decision, material_state_id)
        except Exception as error:
            raise _translate(context, error) from error
        return ShearRelaxationDatasetListResponse(
            items=tuple(ShearRelaxationDatasetResponse.from_snapshot(item) for item in items)
        )

    @application.get(
        "/api/v1/shear-relaxation-datasets/{dataset_id}/preview",
        operation_id="previewShearRelaxationDataset",
        response_model=ShearRelaxationPreviewResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["datasets"],
    )
    async def preview_dataset(
        request: Request,
        dataset_id: UUID,
        maximum_points: Annotated[int, Query(ge=3, le=10_000)] = 500,
    ) -> ShearRelaxationPreviewResponse:
        context, decision = _scope(request)
        if service is None:
            raise ShearRelaxationHttpError(
                context, 503, "Dataset service unavailable", "CMP-DATASET-0105"
            )
        try:
            result = await service.preview(context, decision, dataset_id, maximum_points)
        except Exception as error:
            raise _translate(context, error) from error
        return ShearRelaxationPreviewResponse.from_domain(result)

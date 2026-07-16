"""HTTP contract for immutable viscoelastic replicate Selections."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends, FastAPI, Query, Request, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from cmp.modules.datasets.application.viscoelastic_master import (
    CreateViscoelasticSelection,
    ViscoelasticDatasetConflict,
    ViscoelasticDatasetNotFound,
    ViscoelasticDatasetService,
    ViscoelasticSelectionMemberRef,
    ViscoelasticSelectionSnapshot,
)
from cmp.modules.datasets.domain.viscoelastic_master import InvalidViscoelasticDataset
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.shared.contracts.revisions import RevisionETag, RevisionMetadataResponse

type Dependency = Callable[..., object]
type Reason = Annotated[str, StringConstraints(min_length=1, max_length=2000)]

logger = logging.getLogger(__name__)


class SelectionMemberRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset_id: UUID
    dataset_revision_id: UUID


class CreateViscoelasticSelectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    classification: DataClassification
    selection_label: Annotated[str, StringConstraints(min_length=1, max_length=160)]
    members: Annotated[list[SelectionMemberRequest], Field(min_length=2, max_length=50)]
    change_reason: Reason


class SelectionMemberResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ordinal: int
    dataset_id: UUID
    dataset_revision_id: UUID
    test_run_id: UUID
    test_run_revision_id: UUID
    temperature_k: float
    outlier_status: str


class ViscoelasticSelectionContentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    selection_label: str
    material_state_id: UUID
    material_state_revision_id: UUID
    member_count: int
    temperature_count: int
    members: list[SelectionMemberResponse]


class ViscoelasticSelectionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    selection_id: UUID
    current_revision: RevisionMetadataResponse
    content: ViscoelasticSelectionContentResponse
    links: dict[str, str]

    @classmethod
    def from_domain(
        cls, value: ViscoelasticSelectionSnapshot
    ) -> ViscoelasticSelectionResponse:
        content = value.current.content
        return cls(
            selection_id=value.id,
            current_revision=RevisionMetadataResponse.from_record(
                value.current.record, "draft"
            ),
            content=ViscoelasticSelectionContentResponse(
                selection_label=content.selection_label,
                material_state_id=content.material_state_id,
                material_state_revision_id=content.material_state_revision_id,
                member_count=len(content.members),
                temperature_count=len({item.temperature_k for item in content.members}),
                members=[
                    SelectionMemberResponse(
                        ordinal=item.ordinal,
                        dataset_id=item.dataset_id,
                        dataset_revision_id=item.dataset_revision_id,
                        test_run_id=item.test_run_id,
                        test_run_revision_id=item.test_run_revision_id,
                        temperature_k=item.temperature_k,
                        outlier_status=item.outlier_status,
                    )
                    for item in content.members
                ],
            ),
            links={
                "self": f"/api/v1/viscoelastic-selections/{value.id}",
                "create_plan": "/api/v1/processing-plans/viscoelastic-master-curve",
            },
        )


class ViscoelasticSelectionListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ViscoelasticSelectionResponse]


class DatasetProblem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    title: str
    status: int
    detail: str
    code: str
    trace_id: str


class DatasetHttpError(Exception):
    def __init__(self, context: SecurityContext, status_code: int, title: str, code: str) -> None:
        self.problem = DatasetProblem(
            type="urn:cmp:problem:viscoelastic-selection",
            title=title,
            status=status_code,
            detail="The immutable viscoelastic Selection request could not be completed.",
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


def _translate(context: SecurityContext, error: Exception) -> DatasetHttpError:
    if isinstance(error, ViscoelasticDatasetNotFound):
        return DatasetHttpError(context, 404, "Selection not found", "CMP-DATASET-4201")
    if isinstance(error, InvalidViscoelasticDataset):
        return DatasetHttpError(context, 422, "Invalid Selection", "CMP-DATASET-4202")
    if isinstance(error, ViscoelasticDatasetConflict):
        return DatasetHttpError(context, 409, "Selection conflict", "CMP-DATASET-4203")
    return DatasetHttpError(context, 409, "Selection rejected", "CMP-DATASET-4203")


def install_viscoelastic_selection_api(
    application: FastAPI,
    *,
    service: ViscoelasticDatasetService | None,
    security_dependency: Dependency,
    read_dependency: Dependency,
    write_dependency: Dependency,
) -> None:
    @application.exception_handler(DatasetHttpError)
    async def error_handler(request: Request, error: DatasetHttpError) -> JSONResponse:
        del request
        return JSONResponse(
            status_code=error.problem.status,
            content=error.problem.model_dump(mode="json"),
            media_type="application/problem+json",
        )

    errors: dict[int | str, dict[str, Any]] = {
        401: {"description": "Authentication required."},
        403: {"model": DatasetProblem},
        404: {"model": DatasetProblem},
        409: {"model": DatasetProblem},
        422: {"model": DatasetProblem},
        503: {"model": DatasetProblem},
    }

    @application.post(
        "/api/v1/viscoelastic-selections",
        operation_id="createViscoelasticSelection",
        response_model=ViscoelasticSelectionResponse,
        status_code=status.HTTP_201_CREATED,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(write_dependency)],
        tags=["datasets"],
    )
    def create_selection(
        request: Request,
        response: Response,
        body: CreateViscoelasticSelectionRequest,
    ) -> ViscoelasticSelectionResponse:
        context, decision = _scope(request)
        if service is None:
            raise DatasetHttpError(
                context, 503, "Dataset service unavailable", "CMP-DATASET-4205"
            )
        try:
            value = service.create_selection(
                context,
                decision,
                CreateViscoelasticSelection(
                    classification=body.classification,
                    selection_label=body.selection_label,
                    members=tuple(
                        ViscoelasticSelectionMemberRef(
                            item.dataset_id, item.dataset_revision_id
                        )
                        for item in body.members
                    ),
                    change_reason=body.change_reason,
                ),
            )
        except Exception as error:
            logger.exception("viscoelastic Selection create failed")
            raise _translate(context, error) from error
        response.headers["Location"] = f"/api/v1/viscoelastic-selections/{value.id}"
        response.headers["ETag"] = str(RevisionETag.from_ref(value.current.record.ref))
        return ViscoelasticSelectionResponse.from_domain(value)

    @application.get(
        "/api/v1/viscoelastic-selections",
        operation_id="listViscoelasticSelections",
        response_model=ViscoelasticSelectionListResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["datasets"],
    )
    def list_selections(
        request: Request,
        material_state_id: Annotated[UUID, Query()],
    ) -> ViscoelasticSelectionListResponse:
        context, decision = _scope(request)
        if service is None:
            raise DatasetHttpError(
                context, 503, "Dataset service unavailable", "CMP-DATASET-4205"
            )
        try:
            values = service.list_selections(
                context, decision, material_state_id
            )
        except Exception as error:
            raise _translate(context, error) from error
        return ViscoelasticSelectionListResponse(
            items=[ViscoelasticSelectionResponse.from_domain(item) for item in values]
        )

    @application.get(
        "/api/v1/viscoelastic-selections/{selection_id}",
        operation_id="getViscoelasticSelection",
        response_model=ViscoelasticSelectionResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["datasets"],
    )
    def get_selection(
        request: Request, selection_id: UUID
    ) -> ViscoelasticSelectionResponse:
        context, decision = _scope(request)
        if service is None:
            raise DatasetHttpError(
                context, 503, "Dataset service unavailable", "CMP-DATASET-4205"
            )
        try:
            value = service.get_selection(context, decision, selection_id)
        except Exception as error:
            raise _translate(context, error) from error
        return ViscoelasticSelectionResponse.from_domain(value)

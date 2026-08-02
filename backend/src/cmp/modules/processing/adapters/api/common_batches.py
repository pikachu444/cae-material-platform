"""HTTP API for Processing Recipe batch preflight, execution, and failed retry (T-54)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from sqlalchemy.exc import IntegrityError

from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.processing.adapters.api.common_pipeline import (
    FitDecisionInput,
    ProcessingWorkupOverrideInput,
)
from cmp.modules.processing.application.common_batches import (
    BatchPreflight,
    BatchPreflightMember,
    BatchSourceInput,
    CommonBatchNotFound,
    CommonBatchService,
    ExecuteBatch,
    PreflightBatch,
)
from cmp.modules.processing.application.common_outputs import (
    FitDecisionSnapshot,
    ProcessingWorkupOverride,
    fit_decision_canonical,
)
from cmp.modules.processing.domain.common_batches import (
    BatchAttempt,
    BatchMemberPlan,
    CommonProcessingBatch,
)
from cmp.modules.processing.domain.common_pipeline import CommonPipelineError

type Dependency = Callable[..., object]
type Text200 = Annotated[str, StringConstraints(min_length=1, max_length=200)]
type Reason = Annotated[str, StringConstraints(min_length=1, max_length=2000)]


def _fit_decision_input(value: FitDecisionSnapshot | None) -> FitDecisionInput | None:
    if value is None:
        return None
    return FitDecisionInput.model_validate(fit_decision_canonical(value))


def _workup_override_inputs(
    value: tuple[ProcessingWorkupOverride, ...],
) -> tuple[ProcessingWorkupOverrideInput, ...]:
    return tuple(
        ProcessingWorkupOverrideInput(
            kind=override.kind,
            original_value=override.original_value,
            original_unit=override.original_unit,
            canonical_value=override.canonical_value,
            canonical_unit=override.canonical_unit,
            reason=override.reason,
        )
        for override in value
    )


class BatchSourceInputModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    document_id: UUID
    revision_id: UUID
    workup_overrides: Annotated[tuple[ProcessingWorkupOverrideInput, ...], Field(max_length=2)] = ()
    fit_decision: FitDecisionInput | None = None

    def to_domain(self) -> BatchSourceInput:
        return BatchSourceInput(
            self.document_id,
            self.revision_id,
            tuple(item.to_domain() for item in self.workup_overrides),
            self.fit_decision.to_domain() if self.fit_decision else None,
        )


class BatchPreflightRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    classification: DataClassification
    recipe_id: UUID
    recipe_revision_id: UUID
    sources: Annotated[tuple[BatchSourceInputModel, ...], Field(min_length=1, max_length=500)]


class ExecuteBatchRequest(BatchPreflightRequest):
    label: Text200
    change_reason: Reason


class BatchPreflightMemberResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ordinal: int
    source: BatchSourceInputModel
    compatible: bool
    source_document_sha256: str | None
    final_point_count: int | None
    diagnostic: str | None

    @classmethod
    def from_domain(cls, value: BatchPreflightMember) -> BatchPreflightMemberResponse:
        return cls(
            ordinal=value.ordinal,
            source=BatchSourceInputModel(
                document_id=value.source.document_id,
                revision_id=value.source.revision_id,
                workup_overrides=_workup_override_inputs(value.workup_overrides),
                fit_decision=_fit_decision_input(value.fit_decision),
            ),
            compatible=value.compatible,
            source_document_sha256=value.source_document_sha256,
            final_point_count=value.final_point_count,
            diagnostic=value.diagnostic,
        )


class BatchPreflightResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    recipe_id: UUID
    recipe_revision_id: UUID
    recipe_sha256: str
    compatible: bool
    members: tuple[BatchPreflightMemberResponse, ...]

    @classmethod
    def from_domain(cls, value: BatchPreflight) -> BatchPreflightResponse:
        return cls(
            recipe_id=value.recipe_id,
            recipe_revision_id=value.recipe_revision_id,
            recipe_sha256=value.recipe_sha256,
            compatible=value.compatible,
            members=tuple(BatchPreflightMemberResponse.from_domain(item) for item in value.members),
        )


class BatchMemberResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    member_id: UUID
    ordinal: int
    source: BatchSourceInputModel
    source_document_sha256: str

    @classmethod
    def from_domain(cls, value: BatchMemberPlan) -> BatchMemberResponse:
        return cls(
            member_id=value.member_id,
            ordinal=value.ordinal,
            source=BatchSourceInputModel(
                document_id=value.source_document.aggregate_id,
                revision_id=value.source_document.revision_id,
                workup_overrides=_workup_override_inputs(value.workup_overrides),
                fit_decision=_fit_decision_input(value.fit_decision),
            ),
            source_document_sha256=value.source_document_sha256,
        )


class BatchAttemptResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    attempt_id: UUID
    member_id: UUID
    attempt_no: int
    status: str
    output_id: UUID | None
    output_revision_id: UUID | None
    error_code: str | None
    error_detail: str | None
    started_at: datetime
    completed_at: datetime

    @classmethod
    def from_domain(cls, value: BatchAttempt) -> BatchAttemptResponse:
        return cls(
            attempt_id=value.attempt_id,
            member_id=value.member_id,
            attempt_no=value.attempt_no,
            status=value.status.value,
            output_id=value.output.aggregate_id if value.output else None,
            output_revision_id=value.output.revision_id if value.output else None,
            error_code=value.error_code,
            error_detail=value.error_detail,
            started_at=value.started_at,
            completed_at=value.completed_at,
        )


class CommonBatchResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    batch_id: UUID
    classification: str
    label: str
    recipe_id: UUID
    recipe_revision_id: UUID
    recipe_sha256: str
    status: str
    members: tuple[BatchMemberResponse, ...]
    attempts: tuple[BatchAttemptResponse, ...]
    created_at: datetime
    created_by: UUID

    @classmethod
    def from_domain(cls, value: CommonProcessingBatch) -> CommonBatchResponse:
        return cls(
            batch_id=value.batch_id,
            classification=value.scope.classification,
            label=value.label,
            recipe_id=value.recipe.aggregate_id,
            recipe_revision_id=value.recipe.revision_id,
            recipe_sha256=value.recipe_sha256,
            status=value.status.value,
            members=tuple(BatchMemberResponse.from_domain(item) for item in value.members),
            attempts=tuple(BatchAttemptResponse.from_domain(item) for item in value.attempts),
            created_at=value.created_at,
            created_by=value.created_by,
        )


class CommonBatchListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: tuple[CommonBatchResponse, ...]


def install_common_batch_api(
    app: FastAPI,
    *,
    service: CommonBatchService | None,
    security_dependency: Dependency,
    read_dependency: Dependency,
    execute_dependency: Dependency,
) -> None:
    def scope(request: Request) -> tuple[SecurityContext, AuthorizationDecision]:
        context = getattr(request.state, "security_context", None)
        decision = getattr(request.state, "authorization_decision", None)
        if not isinstance(context, SecurityContext) or not isinstance(
            decision, AuthorizationDecision
        ):
            raise RuntimeError("Processing Batch dependencies did not initialize request scope")
        return context, decision

    def require_service() -> CommonBatchService:
        if service is None:
            raise HTTPException(status_code=503, detail="Processing Batch store unavailable")
        return service

    @app.post(
        "/api/v1/common-processing-batches:preflight",
        response_model=BatchPreflightResponse,
        dependencies=[Depends(security_dependency), Depends(execute_dependency)],
        tags=["processing-batches"],
    )
    async def preflight_batch(
        body: BatchPreflightRequest, request: Request
    ) -> BatchPreflightResponse:
        context, decision = scope(request)
        try:
            result = await require_service().preflight(
                context,
                decision,
                PreflightBatch(
                    body.classification,
                    body.recipe_id,
                    body.recipe_revision_id,
                    tuple(item.to_domain() for item in body.sources),
                ),
            )
            return BatchPreflightResponse.from_domain(result)
        except (CommonPipelineError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @app.post(
        "/api/v1/common-processing-batches",
        response_model=CommonBatchResponse,
        status_code=status.HTTP_201_CREATED,
        dependencies=[Depends(security_dependency), Depends(execute_dependency)],
        tags=["processing-batches"],
    )
    async def execute_batch(body: ExecuteBatchRequest, request: Request) -> CommonBatchResponse:
        context, decision = scope(request)
        try:
            result = await require_service().execute(
                context,
                decision,
                ExecuteBatch(
                    body.classification,
                    body.label,
                    body.recipe_id,
                    body.recipe_revision_id,
                    tuple(item.to_domain() for item in body.sources),
                    body.change_reason,
                ),
            )
            return CommonBatchResponse.from_domain(result)
        except (CommonPipelineError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        except IntegrityError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.get(
        "/api/v1/common-processing-batches",
        response_model=CommonBatchListResponse,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["processing-batches"],
    )
    def list_batches(request: Request) -> CommonBatchListResponse:
        context, decision = scope(request)
        return CommonBatchListResponse(
            items=tuple(
                CommonBatchResponse.from_domain(item)
                for item in require_service().list_batches(context, decision)
            )
        )

    @app.get(
        "/api/v1/common-processing-batches/{batch_id}",
        response_model=CommonBatchResponse,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["processing-batches"],
    )
    def get_batch(batch_id: UUID, request: Request) -> CommonBatchResponse:
        context, decision = scope(request)
        try:
            return CommonBatchResponse.from_domain(
                require_service().get_batch(context, decision, batch_id)
            )
        except CommonBatchNotFound as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @app.post(
        "/api/v1/common-processing-batches/{batch_id}:retry-failed",
        response_model=CommonBatchResponse,
        dependencies=[Depends(security_dependency), Depends(execute_dependency)],
        tags=["processing-batches"],
    )
    async def retry_failed(batch_id: UUID, request: Request) -> CommonBatchResponse:
        context, decision = scope(request)
        try:
            result = await require_service().retry_failed(context, decision, batch_id)
            return CommonBatchResponse.from_domain(result)
        except CommonBatchNotFound as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except (CommonPipelineError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        except IntegrityError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

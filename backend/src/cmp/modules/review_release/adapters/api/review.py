"""Protected T-29 review request and decision resources."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends, FastAPI, Query, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, StringConstraints

from cmp.modules.identity_access.domain.authorization import DataClassification
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.review_release.application.service import ReviewService
from cmp.modules.review_release.domain.lifecycle import (
    DecideReviewRequest,
    InvalidReview,
    ReviewConflict,
    ReviewDecisionKind,
    ReviewNotFound,
    ReviewRequestRecord,
    SubmitReviewRequest,
)

type Dependency = Callable[..., object]
type Label = Annotated[str, StringConstraints(min_length=1, max_length=255)]


class ReviewRequestCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    classification: DataClassification
    aggregate_type: Annotated[str, StringConstraints(min_length=1, max_length=100)]
    aggregate_id: UUID
    revision_id: UUID
    manifest_sha256: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
    reason: Annotated[str, StringConstraints(min_length=1, max_length=2000)]


class ReviewDecisionCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_manifest_sha256: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
    decision: ReviewDecisionKind
    reason: Annotated[str, StringConstraints(min_length=1, max_length=2000)]


class ReviewDecisionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    review_decision_id: UUID
    review_request_id: UUID
    aggregate_type: str
    aggregate_id: UUID
    revision_id: UUID
    manifest_sha256: str
    decision: ReviewDecisionKind
    decided_by: UUID
    decided_at: str
    reason: str


class ReviewRequestResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    review_request_id: UUID
    classification: DataClassification
    aggregate_type: str
    aggregate_id: UUID
    revision_id: UUID
    manifest_sha256: str
    required_role: str
    requested_by: UUID
    requested_at: str
    reason: str
    lifecycle_state: str
    decision: ReviewDecisionResponse | None
    links: dict[str, str]

    @classmethod
    def from_domain(cls, value: ReviewRequestRecord) -> ReviewRequestResponse:
        decision = value.decision
        return cls(
            review_request_id=value.id,
            classification=value.classification,
            aggregate_type=value.aggregate_type,
            aggregate_id=value.aggregate_id,
            revision_id=value.revision_id,
            manifest_sha256=value.manifest_sha256,
            required_role=value.required_role,
            requested_by=value.requested_by,
            requested_at=value.requested_at.isoformat(),
            reason=value.reason,
            lifecycle_state=value.lifecycle_state.value,
            decision=(
                ReviewDecisionResponse(
                    review_decision_id=decision.id,
                    review_request_id=decision.review_request_id,
                    aggregate_type=decision.aggregate_type,
                    aggregate_id=decision.aggregate_id,
                    revision_id=decision.revision_id,
                    manifest_sha256=decision.manifest_sha256,
                    decision=decision.decision,
                    decided_by=decision.decided_by,
                    decided_at=decision.decided_at.isoformat(),
                    reason=decision.reason,
                )
                if decision is not None
                else None
            ),
            links={
                "self": f"/api/v1/review-requests/{value.id}",
                "decisions": f"/api/v1/review-requests/{value.id}/decisions",
            },
        )


class ReviewRequestListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: tuple[ReviewRequestResponse, ...]


class ReviewProblem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Label
    title: Label
    status: int
    detail: Annotated[str, StringConstraints(min_length=1, max_length=2000)]
    code: Annotated[str, StringConstraints(pattern=r"^CMP-REVIEW-[0-9]{4}$")]
    trace_id: Label


class ReviewHttpError(Exception):
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
        self.problem = ReviewProblem(
            type="urn:cmp:problem:review",
            title=title,
            status=status_code,
            detail=detail,
            code=code,
            trace_id=context.trace_id,
        )
        super().__init__(title)


def _scope(request: Request) -> SecurityContext:
    context = getattr(request.state, "security_context", None)
    if not isinstance(context, SecurityContext):
        raise RuntimeError("review route dependencies did not initialize request scope")
    return context


def _translate(context: SecurityContext, error: Exception) -> ReviewHttpError:
    if isinstance(error, ReviewNotFound):
        return ReviewHttpError(
            context=context,
            status_code=404,
            title="Review resource not found",
            detail="No immutable review request or lifecycle target is visible in this tenant.",
            code="CMP-REVIEW-0001",
        )
    if isinstance(error, (InvalidReview, ValueError)):
        return ReviewHttpError(
            context=context,
            status_code=422,
            title="Invalid review request",
            detail="The typed target, manifest digest, or reason is invalid.",
            code="CMP-REVIEW-0002",
        )
    if isinstance(error, ReviewConflict):
        return ReviewHttpError(
            context=context,
            status_code=409,
            title="Review lifecycle conflict",
            detail=(
                "The immutable revision is stale, already decided, or violates the review state "
                "and separation-of-duties policy."
            ),
            code="CMP-REVIEW-0003",
        )
    return ReviewHttpError(
        context=context,
        status_code=409,
        title="Review command rejected",
        detail="The review command could not be committed.",
        code="CMP-REVIEW-0004",
    )


def _unavailable(context: SecurityContext) -> ReviewHttpError:
    return ReviewHttpError(
        context=context,
        status_code=503,
        title="Review service unavailable",
        detail="The review persistence boundary is not configured for this API process.",
        code="CMP-REVIEW-0005",
    )


def install_review_api(
    application: FastAPI,
    *,
    service: ReviewService | None,
    security_dependency: Dependency,
    read_dependency: Dependency,
    request_dependency: Dependency,
    decide_dependency: Dependency,
) -> None:
    @application.exception_handler(ReviewHttpError)
    async def review_error_handler(
        request: Request, error: ReviewHttpError
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
        403: {"description": "Review read, request, or decision is not authorized."},
        404: {"description": "No visible review request or lifecycle target matches."},
        409: {"description": "Immutable, stale, lifecycle, or separation-of-duties conflict."},
        422: {"description": "Typed review input is invalid."},
        503: {"description": "Review service unavailable."},
    }

    @application.post(
        "/api/v1/review-requests",
        operation_id="createReviewRequest",
        response_model=ReviewRequestResponse,
        status_code=status.HTTP_201_CREATED,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(request_dependency)],
        tags=["governance", "review"],
        summary="Submit one immutable candidate revision for human review.",
    )
    def create_request(body: ReviewRequestCreateRequest, request: Request) -> ReviewRequestResponse:
        context = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            value = service.create_request(
                context,
                request.state.authorization_decision,
                SubmitReviewRequest(
                    classification=body.classification,
                    aggregate_type=body.aggregate_type,
                    aggregate_id=body.aggregate_id,
                    revision_id=body.revision_id,
                    manifest_sha256=body.manifest_sha256,
                    reason=body.reason,
                ),
            )
        except Exception as error:
            raise _translate(context, error) from error
        return ReviewRequestResponse.from_domain(value)

    @application.get(
        "/api/v1/review-requests",
        operation_id="listReviewRequests",
        response_model=ReviewRequestListResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["governance", "review"],
        summary="List immutable review requests visible in the selected tenant.",
    )
    def list_requests(
        request: Request,
        limit: Annotated[int, Query(ge=1, le=200)] = 100,
        aggregate_type: Annotated[str | None, Query(min_length=1, max_length=100)] = None,
        aggregate_id: UUID | None = None,
        revision_id: UUID | None = None,
    ) -> ReviewRequestListResponse:
        context = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            values = service.list_requests(
                context,
                request.state.authorization_decision,
                limit=limit,
                aggregate_type=aggregate_type,
                aggregate_id=aggregate_id,
                revision_id=revision_id,
            )
        except Exception as error:
            raise _translate(context, error) from error
        return ReviewRequestListResponse(
            items=tuple(ReviewRequestResponse.from_domain(value) for value in values)
        )

    @application.get(
        "/api/v1/review-requests/{review_request_id}",
        operation_id="getReviewRequest",
        response_model=ReviewRequestResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["governance", "review"],
        summary="Read one immutable review request and its append-only decision.",
    )
    def get_request(review_request_id: UUID, request: Request) -> ReviewRequestResponse:
        context = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            value = service.get_request(
                context,
                request.state.authorization_decision,
                review_request_id,
            )
        except Exception as error:
            raise _translate(context, error) from error
        return ReviewRequestResponse.from_domain(value)

    @application.post(
        "/api/v1/review-requests/{review_request_id}/decisions",
        operation_id="createReviewDecision",
        response_model=ReviewRequestResponse,
        status_code=status.HTTP_201_CREATED,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(decide_dependency)],
        tags=["governance", "review"],
        summary="Append one separated human decision to an immutable review request.",
    )
    def create_decision(
        review_request_id: UUID,
        body: ReviewDecisionCreateRequest,
        request: Request,
    ) -> ReviewRequestResponse:
        context = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            value = service.decide(
                context,
                request.state.authorization_decision,
                review_request_id,
                DecideReviewRequest(
                    expected_manifest_sha256=body.expected_manifest_sha256,
                    decision=body.decision,
                    reason=body.reason,
                ),
            )
        except Exception as error:
            raise _translate(context, error) from error
        return ReviewRequestResponse.from_domain(value)

"""Protected T-15 submit/read/cancel/retry HTTP resources."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends, FastAPI, Header, Request, Response
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.jobs.application.jobs import (
    CancelJob,
    JobService,
    RetryJob,
    SubmitJob,
)
from cmp.modules.jobs.domain.jobs import (
    AttemptRecord,
    AttemptState,
    InvalidJobSpec,
    JobConflict,
    JobDetails,
    JobError,
    JobNotFound,
    JobState,
    ResourcePolicy,
    RetryNotAllowed,
)

type Label = Annotated[str, StringConstraints(min_length=1, max_length=255)]
type Reason = Annotated[str, StringConstraints(min_length=1, max_length=2000)]
type FailureDetail = Annotated[str, StringConstraints(min_length=1, max_length=4000)]
type Sha256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
type Dependency = Callable[..., object]


class ResourcePolicyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cpu_millis: Annotated[int, Field(ge=1, le=10_000_000)]
    memory_mb: Annotated[int, Field(ge=1, le=100_000_000)]
    gpu_count: Annotated[int, Field(ge=0, le=1024)]
    max_attempts: Annotated[int, Field(ge=1, le=100)]

    def domain(self) -> ResourcePolicy:
        return ResourcePolicy(
            self.cpu_millis, self.memory_mb, self.gpu_count, self.max_attempts
        )


class SubmitJobRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_type: Annotated[
        str, StringConstraints(pattern=r"^[a-z][a-z0-9_.-]{0,99}$")
    ]
    classification: DataClassification
    job_spec: dict[str, Any]
    resource_policy: ResourcePolicyRequest
    priority: Annotated[int, Field(ge=-32768, le=32767)] = 0


class ControlJobRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: Reason


class FailureResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: Label
    code: Label
    detail: FailureDetail


class ProgressResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fraction: Annotated[float | None, Field(ge=0, le=1)]
    phase: Label | None
    updated_at: datetime | None


class AttemptResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    attempt_id: UUID
    attempt_no: int
    state: AttemptState
    retry_kind: Label
    retry_reason: Reason
    job_spec_digest: Sha256
    runner_id: UUID | None
    claimed_at: datetime | None
    started_at: datetime | None
    ended_at: datetime | None
    progress: ProgressResponse | None
    result_manifest_id: UUID | None
    result_manifest_digest: Sha256 | None
    failure: FailureResponse | None

    @classmethod
    def from_record(cls, attempt: AttemptRecord) -> AttemptResponse:
        progress = None
        if attempt.progress_updated_at is not None:
            progress = ProgressResponse(
                fraction=attempt.progress_fraction,
                phase=attempt.progress_phase,
                updated_at=attempt.progress_updated_at,
            )
        failure = None
        if attempt.failure is not None:
            failure = FailureResponse(
                category=attempt.failure.category.value,
                code=attempt.failure.code,
                detail=attempt.failure.detail,
            )
        return cls(
            attempt_id=attempt.id,
            attempt_no=attempt.attempt_no,
            state=attempt.state,
            retry_kind=attempt.retry_kind.value,
            retry_reason=attempt.retry_reason,
            job_spec_digest=attempt.spec.digest,
            runner_id=attempt.runner_id,
            claimed_at=attempt.claimed_at,
            started_at=attempt.started_at,
            ended_at=attempt.ended_at,
            progress=progress,
            result_manifest_id=attempt.result_manifest_id,
            result_manifest_digest=attempt.result_manifest_digest,
            failure=failure,
        )


class JobLinks(BaseModel):
    model_config = ConfigDict(extra="forbid")

    self: str


class JobResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: UUID
    job_type: Label
    state: JobState
    organization_id: UUID
    project_id: UUID
    classification: DataClassification
    submitted_at: datetime
    submitted_by: UUID
    deadline: datetime
    current_attempt: int
    result_manifest_id: UUID | None
    result_manifest_digest: Sha256 | None
    failure: FailureResponse | None
    attempts: list[AttemptResponse]
    links: JobLinks

    @classmethod
    def from_details(cls, details: JobDetails) -> JobResponse:
        failure = None
        if details.job.failure is not None:
            failure = FailureResponse(
                category=details.job.failure.category.value,
                code=details.job.failure.code,
                detail=details.job.failure.detail,
            )
        return cls(
            job_id=details.job.id,
            job_type=details.job.job_type,
            state=details.job.state,
            organization_id=details.job.organization_id,
            project_id=details.job.project_id,
            classification=details.job.classification,
            submitted_at=details.job.submitted_at,
            submitted_by=details.job.submitted_by,
            deadline=details.job.deadline,
            current_attempt=details.job.attempt_count,
            result_manifest_id=details.job.result_manifest_id,
            result_manifest_digest=details.job.result_manifest_digest,
            failure=failure,
            attempts=[AttemptResponse.from_record(item) for item in details.attempts],
            links=JobLinks(self=f"/api/v1/jobs/{details.job.id}"),
        )


class JobProblem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Label
    title: Label
    status: Annotated[int, Field(ge=400, le=599)]
    detail: Reason
    code: Annotated[str, StringConstraints(pattern=r"^CMP-JOB-[0-9]{4}$")]
    trace_id: Label


class JobHttpError(Exception):
    def __init__(
        self,
        *,
        context: SecurityContext,
        status: int,
        title: str,
        detail: str,
        code: str,
    ) -> None:
        self.context = context
        self.problem = JobProblem(
            type="urn:cmp:problem:job",
            title=title,
            status=status,
            detail=detail,
            code=code,
            trace_id=context.trace_id,
        )
        super().__init__(title)


def _request_scope(request: Request) -> tuple[SecurityContext, AuthorizationDecision]:
    context = getattr(request.state, "security_context", None)
    decision = getattr(request.state, "authorization_decision", None)
    if not isinstance(context, SecurityContext) or not isinstance(
        decision, AuthorizationDecision
    ):
        raise RuntimeError("job route dependencies did not initialize request scope")
    return context, decision


def _unavailable(context: SecurityContext) -> JobHttpError:
    return JobHttpError(
        context=context,
        status=503,
        title="Job service unavailable",
        detail="The durable job store is not configured for this deployment.",
        code="CMP-JOB-0005",
    )


def _translate(context: SecurityContext, error: Exception) -> JobHttpError:
    if isinstance(error, JobNotFound):
        return JobHttpError(
            context=context,
            status=404,
            title="Job not found",
            detail="No job is visible for the supplied identifier and tenant context.",
            code="CMP-JOB-0001",
        )
    if isinstance(error, InvalidJobSpec):
        return JobHttpError(
            context=context,
            status=422,
            title="Invalid Job Spec",
            detail=str(error),
            code="CMP-JOB-0002",
        )
    if isinstance(error, ValueError):
        return JobHttpError(
            context=context,
            status=422,
            title="Invalid job request",
            detail="The request violates a durable Job command invariant.",
            code="CMP-JOB-0002",
        )
    if isinstance(error, (JobConflict, RetryNotAllowed)):
        return JobHttpError(
            context=context,
            status=409,
            title="Job command conflict",
            detail=str(error),
            code="CMP-JOB-0003",
        )
    return JobHttpError(
        context=context,
        status=409,
        title="Invalid job state",
        detail="The job cannot accept this command in its current state.",
        code="CMP-JOB-0004",
    )


def install_jobs_api(
    application: FastAPI,
    *,
    service: JobService | None,
    security_dependency: Dependency,
    read_dependency: Dependency,
    submit_dependency: Dependency,
    control_dependency: Dependency,
) -> None:
    @application.exception_handler(JobHttpError)
    async def job_error_handler(request: Request, error: JobHttpError) -> JSONResponse:
        del request
        return JSONResponse(
            status_code=error.problem.status,
            content=error.problem.model_dump(mode="json"),
            media_type="application/problem+json",
            headers={
                "Cache-Control": "no-store",
                "X-Request-ID": str(error.context.request_id),
            },
        )

    @application.exception_handler(RequestValidationError)
    async def job_validation_error_handler(
        request: Request, error: RequestValidationError
    ) -> JSONResponse:
        if not request.url.path.startswith("/api/v1/jobs"):
            return await request_validation_exception_handler(request, error)
        context = getattr(request.state, "security_context", None)
        if not isinstance(context, SecurityContext):
            return await request_validation_exception_handler(request, error)
        problem = JobProblem(
            type="urn:cmp:problem:job",
            title="Invalid job request",
            status=422,
            detail="The request does not satisfy the versioned Job API contract.",
            code="CMP-JOB-0002",
            trace_id=context.trace_id,
        )
        return JSONResponse(
            status_code=422,
            content=problem.model_dump(mode="json"),
            media_type="application/problem+json",
            headers={
                "Cache-Control": "no-store",
                "X-Request-ID": str(context.request_id),
            },
        )

    authentication_errors: dict[int | str, dict[str, Any]] = {
        401: {"description": "Authentication required."},
        403: {"description": "The job action is not authorized."},
    }
    problem_errors: dict[int | str, dict[str, Any]] = {
        404: {"model": JobProblem},
        409: {"model": JobProblem},
        422: {"model": JobProblem},
        503: {"model": JobProblem},
    }
    submit_errors: dict[int | str, dict[str, Any]] = {
        **authentication_errors,
        409: problem_errors[409],
        422: problem_errors[422],
        503: problem_errors[503],
    }
    read_errors: dict[int | str, dict[str, Any]] = {
        **authentication_errors,
        404: problem_errors[404],
        422: problem_errors[422],
        503: problem_errors[503],
    }
    control_errors: dict[int | str, dict[str, Any]] = {
        **authentication_errors,
        **problem_errors,
    }

    @application.post(
        "/api/v1/jobs",
        operation_id="submitJob",
        response_model=JobResponse,
        status_code=202,
        responses=submit_errors,
        dependencies=[Depends(security_dependency), Depends(submit_dependency)],
        tags=["jobs"],
        summary="Submit one immutable Job Spec for durable execution.",
    )
    def submit_job(
        request: Request,
        response: Response,
        body: SubmitJobRequest,
        idempotency_key: Annotated[
            str,
            Header(
                alias="Idempotency-Key",
                min_length=1,
                max_length=255,
                pattern=r"^[\x21-\x7e]+$",
            ),
        ],
    ) -> JobResponse:
        context, decision = _request_scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            result = service.submit(
                context,
                decision,
                SubmitJob(
                    body.job_type,
                    body.classification,
                    body.job_spec,
                    body.resource_policy.domain(),
                    body.priority,
                    idempotency_key,
                ),
            )
        except (JobError, ValueError) as error:
            raise _translate(context, error) from error
        response.headers["Location"] = f"/api/v1/jobs/{result.details.job.id}"
        response.headers["Idempotent-Replay"] = (
            "true" if result.replayed else "false"
        )
        return JobResponse.from_details(result.details)

    @application.get(
        "/api/v1/jobs/{job_id}",
        operation_id="getJob",
        response_model=JobResponse,
        responses=read_errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["jobs"],
        summary="Return job, attempt, progress, and terminal result references.",
    )
    def get_job(request: Request, job_id: UUID) -> JobResponse:
        context, decision = _request_scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            details = service.get(context, decision, job_id)
        except (JobError, ValueError) as error:
            raise _translate(context, error) from error
        return JobResponse.from_details(details)

    @application.post(
        "/api/v1/jobs/{job_id}:cancel",
        operation_id="cancelJob",
        response_model=JobResponse,
        status_code=202,
        responses=control_errors,
        dependencies=[Depends(security_dependency), Depends(control_dependency)],
        tags=["jobs"],
        summary="Request cooperative cancellation without deleting execution facts.",
    )
    def cancel_job(
        request: Request, job_id: UUID, body: ControlJobRequest
    ) -> JobResponse:
        context, decision = _request_scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            details = service.cancel(context, decision, CancelJob(job_id, body.reason))
        except (JobError, ValueError) as error:
            raise _translate(context, error) from error
        return JobResponse.from_details(details)

    @application.post(
        "/api/v1/jobs/{job_id}:retry",
        operation_id="retryJob",
        response_model=JobResponse,
        status_code=202,
        responses=control_errors,
        dependencies=[Depends(security_dependency), Depends(control_dependency)],
        tags=["jobs"],
        summary="Append a new attempt for a retryable terminal job.",
    )
    def retry_job(
        request: Request, job_id: UUID, body: ControlJobRequest
    ) -> JobResponse:
        context, decision = _request_scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            details = service.retry(context, decision, RetryJob(job_id, body.reason))
        except (JobError, ValueError) as error:
            raise _translate(context, error) from error
        return JobResponse.from_details(details)

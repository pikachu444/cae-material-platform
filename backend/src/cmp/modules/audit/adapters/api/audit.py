"""Auditor-only T-05 event query, bounded export, and integrity report API."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Annotated, Any, Literal, cast
from uuid import UUID

from fastapi import Depends, FastAPI, Query, Request, Response
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from cmp.modules.audit.application.service import (
    AuditEventPage,
    AuditEventQuery,
    AuditExportSegment,
    AuditService,
)
from cmp.modules.audit.domain.model import (
    AuditActorType,
    AuditConflict,
    AuditError,
    AuditEvent,
    AuditIntegrityIssue,
    AuditIntegrityReport,
    AuditIntegrityState,
    AuditOutcome,
    AuditSegmentRoot,
)
from cmp.modules.identity_access.domain.authorization import AuthorizationDecision
from cmp.modules.identity_access.domain.security import SecurityContext

type Label = Annotated[str, StringConstraints(min_length=1, max_length=255)]
type Sha256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
type Dependency = Callable[..., object]


class AuditActorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: AuditActorType
    id: UUID


class AuditTargetResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    id: UUID | None


class AuditEventResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: UUID
    sequence_no: Annotated[int, Field(gt=0)]
    occurred_at: datetime
    recorded_at: datetime
    actor: AuditActorResponse
    organization_id: UUID
    project_id: UUID
    action: str
    target: AuditTargetResponse
    outcome: AuditOutcome
    request_id: UUID
    trace_id: Label
    ip_or_client: Annotated[str, Field(pattern=r"^policy-redacted$")]
    reason: Annotated[str, StringConstraints(min_length=1, max_length=2000)]
    previous_hash: Sha256
    event_hash: Sha256

    @classmethod
    def from_event(cls, value: AuditEvent) -> AuditEventResponse:
        return cls(
            event_id=value.id,
            sequence_no=value.sequence_no,
            occurred_at=value.occurred_at,
            recorded_at=value.recorded_at,
            actor=AuditActorResponse(type=value.actor_type, id=value.actor_id),
            organization_id=value.scope.organization_id,
            project_id=value.scope.project_id,
            action=value.action,
            target=AuditTargetResponse(type=value.target_type, id=value.target_id),
            outcome=value.outcome,
            request_id=value.request_id,
            trace_id=value.trace_id,
            ip_or_client=value.ip_or_client,
            reason=value.reason,
            previous_hash=value.previous_hash,
            event_hash=value.event_hash,
        )


class AuditEventPageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    events: tuple[AuditEventResponse, ...]
    next_after_sequence: int | None

    @classmethod
    def from_page(cls, value: AuditEventPage) -> AuditEventPageResponse:
        return cls(
            events=tuple(AuditEventResponse.from_event(event) for event in value.events),
            next_after_sequence=value.next_after_sequence,
        )


class AuditSegmentRootResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    segment_id: UUID
    segment_no: Annotated[int, Field(gt=0)]
    first_sequence_no: Annotated[int, Field(gt=0)]
    last_sequence_no: Annotated[int, Field(gt=0)]
    event_count: Annotated[int, Field(ge=1, le=10000)]
    first_event_hash: Sha256
    last_event_hash: Sha256
    previous_root_hash: Sha256
    root_hash: Sha256
    created_at: datetime
    created_by: UUID
    request_id: UUID
    trace_id: Label

    @classmethod
    def from_root(cls, value: AuditSegmentRoot) -> AuditSegmentRootResponse:
        return cls(
            segment_id=value.id,
            segment_no=value.segment_no,
            first_sequence_no=value.first_sequence_no,
            last_sequence_no=value.last_sequence_no,
            event_count=value.event_count,
            first_event_hash=value.first_event_hash,
            last_event_hash=value.last_event_hash,
            previous_root_hash=value.previous_root_hash,
            root_hash=value.root_hash,
            created_at=value.created_at,
            created_by=value.created_by,
            request_id=value.request_id,
            trace_id=value.trace_id,
        )


class AuditIntegrityIssueResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    event_sequence_no: int | None
    segment_no: int | None

    @classmethod
    def from_issue(cls, value: AuditIntegrityIssue) -> AuditIntegrityIssueResponse:
        return cls(
            code=value.code.value,
            event_sequence_no=value.event_sequence_no,
            segment_no=value.segment_no,
        )


class AuditIntegrityResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: AuditIntegrityState
    event_count: Annotated[int, Field(ge=0)]
    last_sequence_no: Annotated[int, Field(ge=0)]
    segment_count: Annotated[int, Field(ge=0)]
    sealed_through_sequence_no: Annotated[int, Field(ge=0)]
    unsealed_event_count: Annotated[int, Field(ge=0)]
    issues: tuple[AuditIntegrityIssueResponse, ...]

    @classmethod
    def from_report(cls, value: AuditIntegrityReport) -> AuditIntegrityResponse:
        return cls(
            state=value.state,
            event_count=value.event_count,
            last_sequence_no=value.last_sequence_no,
            segment_count=value.segment_count,
            sealed_through_sequence_no=value.sealed_through_sequence_no,
            unsealed_event_count=value.unsealed_event_count,
            issues=tuple(
                AuditIntegrityIssueResponse.from_issue(issue) for issue in value.issues
            ),
        )


class AuditExportResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    export_version: Literal["1.0"]
    organization_id: UUID
    project_id: UUID
    from_sequence: Annotated[int, Field(gt=0)]
    to_sequence: Annotated[int, Field(gt=0)]
    anchor_previous_hash: Sha256
    events: tuple[AuditEventResponse, ...]
    segment_roots: tuple[AuditSegmentRootResponse, ...]
    integrity: AuditIntegrityResponse

    @classmethod
    def from_export(
        cls,
        value: AuditExportSegment,
        context: SecurityContext,
    ) -> AuditExportResponse:
        return cls(
            export_version="1.0",
            organization_id=context.organization_id,
            project_id=context.project_id,
            from_sequence=value.from_sequence,
            to_sequence=value.to_sequence,
            anchor_previous_hash=value.anchor_previous_hash,
            events=tuple(AuditEventResponse.from_event(event) for event in value.events),
            segment_roots=tuple(
                AuditSegmentRootResponse.from_root(root) for root in value.segment_roots
            ),
            integrity=AuditIntegrityResponse.from_report(value.integrity),
        )


class AuditProblem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Label
    title: Label
    status: Annotated[int, Field(ge=400, le=599)]
    detail: Annotated[str, StringConstraints(min_length=1, max_length=2000)]
    code: Annotated[str, StringConstraints(pattern=r"^CMP-AUDIT-[0-9]{4}$")]
    trace_id: Label


class AuditHttpError(Exception):
    def __init__(
        self,
        *,
        context: SecurityContext,
        status: int,
        title: str,
        detail: str,
        code: str,
    ) -> None:
        self.problem = AuditProblem(
            type="urn:cmp:problem:audit",
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
    if not isinstance(context, SecurityContext) or not isinstance(decision, AuthorizationDecision):
        raise RuntimeError("audit route dependencies did not initialize request scope")
    return context, decision


def _translate(context: SecurityContext, error: Exception) -> AuditHttpError:
    if isinstance(error, ValueError):
        return AuditHttpError(
            context=context,
            status=422,
            title="Invalid audit query",
            detail="The query does not satisfy the bounded audit contract.",
            code="CMP-AUDIT-0002",
        )
    if isinstance(error, AuditConflict):
        return AuditHttpError(
            context=context,
            status=409,
            title="Audit query conflict",
            detail="The audit operation conflicts with its immutable security scope.",
            code="CMP-AUDIT-0004",
        )
    return AuditHttpError(
        context=context,
        status=409,
        title="Audit query rejected",
        detail="The audit query could not be completed.",
        code="CMP-AUDIT-0004",
    )


def install_audit_api(
    application: FastAPI,
    *,
    service: AuditService | None,
    security_dependency: Dependency,
    read_dependency: Dependency,
) -> None:
    previous_validation_handler = cast(
        Callable[[Request, RequestValidationError], Awaitable[Response]],
        application.exception_handlers.get(
            RequestValidationError, request_validation_exception_handler
        ),
    )

    @application.exception_handler(AuditHttpError)
    async def audit_error_handler(request: Request, error: AuditHttpError) -> JSONResponse:
        del request
        return JSONResponse(
            status_code=error.problem.status,
            content=error.problem.model_dump(mode="json"),
            media_type="application/problem+json",
            headers={"Cache-Control": "no-store"},
        )

    @application.exception_handler(RequestValidationError)
    async def audit_validation_error_handler(
        request: Request,
        error: RequestValidationError,
    ) -> JSONResponse:
        if not request.url.path.startswith("/api/v1/audit"):
            return cast(JSONResponse, await previous_validation_handler(request, error))
        context = getattr(request.state, "security_context", None)
        if not isinstance(context, SecurityContext):
            return await request_validation_exception_handler(request, error)
        problem = _translate(context, ValueError("invalid query")).problem
        return JSONResponse(
            status_code=problem.status,
            content=problem.model_dump(mode="json"),
            media_type="application/problem+json",
            headers={"Cache-Control": "no-store"},
        )

    responses: dict[int | str, dict[str, Any]] = {
        401: {"description": "Authentication required."},
        403: {"model": AuditProblem},
        409: {"model": AuditProblem},
        422: {"model": AuditProblem},
        503: {"model": AuditProblem},
    }

    def require_service(context: SecurityContext) -> AuditService:
        if service is None:
            raise AuditHttpError(
                context=context,
                status=503,
                title="Audit service unavailable",
                detail="The authoritative audit store is not configured for this deployment.",
                code="CMP-AUDIT-0003",
            )
        return service

    @application.get(
        "/api/v1/audit/events",
        operation_id="listAuditEvents",
        response_model=AuditEventPageResponse,
        responses=responses,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["audit"],
        summary="Query tenant-scoped append-only audit events.",
    )
    def list_events(
        request: Request,
        response: Response,
        after_sequence: Annotated[int, Query(ge=0)] = 0,
        limit: Annotated[int, Query(ge=1, le=1000)] = 100,
        action: Annotated[str | None, Query(min_length=3, max_length=150)] = None,
        actor_id: UUID | None = None,
        target_type: Annotated[str | None, Query(min_length=1, max_length=150)] = None,
        target_id: UUID | None = None,
        outcome: AuditOutcome | None = None,
        occurred_from: datetime | None = None,
        occurred_to: datetime | None = None,
    ) -> AuditEventPageResponse:
        context, decision = _request_scope(request)
        resolved = require_service(context)
        try:
            page = resolved.query_events(
                context,
                decision,
                AuditEventQuery(
                    after_sequence=after_sequence,
                    limit=limit,
                    action=action,
                    actor_id=actor_id,
                    target_type=target_type,
                    target_id=target_id,
                    outcome=outcome,
                    occurred_from=occurred_from,
                    occurred_to=occurred_to,
                ),
            )
        except (AuditError, ValueError) as error:
            raise _translate(context, error) from error
        response.headers["Cache-Control"] = "no-store"
        return AuditEventPageResponse.from_page(page)

    @application.get(
        "/api/v1/audit/integrity",
        operation_id="getAuditIntegrity",
        response_model=AuditIntegrityResponse,
        responses=responses,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["audit"],
        summary="Verify the complete visible event chain and periodic segment roots.",
    )
    def get_integrity(request: Request, response: Response) -> AuditIntegrityResponse:
        context, decision = _request_scope(request)
        resolved = require_service(context)
        try:
            report = resolved.integrity(context, decision)
        except AuditError as error:
            raise _translate(context, error) from error
        response.headers["Cache-Control"] = "no-store"
        return AuditIntegrityResponse.from_report(report)

    @application.get(
        "/api/v1/audit/export",
        operation_id="exportAuditSegment",
        response_model=AuditExportResponse,
        responses=responses,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["audit"],
        summary="Export a bounded event range with chain anchor, roots, and integrity report.",
    )
    def export_events(
        request: Request,
        response: Response,
        from_sequence: Annotated[int, Query(ge=1)],
        to_sequence: Annotated[int, Query(ge=1)],
    ) -> AuditExportResponse:
        context, decision = _request_scope(request)
        resolved = require_service(context)
        try:
            exported = resolved.export(
                context,
                decision,
                from_sequence=from_sequence,
                to_sequence=to_sequence,
            )
        except (AuditError, ValueError) as error:
            raise _translate(context, error) from error
        response.headers["Cache-Control"] = "no-store"
        return AuditExportResponse.from_export(exported, context)

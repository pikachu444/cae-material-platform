"""Bearer authentication dependency and `/api/v1/me` resource."""

from __future__ import annotations

import re
from typing import Annotated
from uuid import UUID, uuid4

from cmp.modules.identity_access.application.security import SecurityContextService
from cmp.modules.identity_access.domain.security import (
    AccessDenied,
    AuthenticationFailed,
    AuthenticationRequest,
    AuthenticationUnavailable,
    PrincipalType,
    SecurityContext,
)
from fastapi import Depends, FastAPI, Header, Request, Response, Security
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

_TRACEPARENT = re.compile(
    r"^(?!ff)[0-9a-f]{2}-(?!0{32})[0-9a-f]{32}-(?!0{16})[0-9a-f]{16}-[0-9a-f]{2}$"
)
_TRACEPARENT_SCHEMA = r"^[0-9a-f]{2}-[0-9a-f]{32}-[0-9a-f]{16}-[0-9a-f]{2}$"
type ContextLabel = Annotated[str, StringConstraints(min_length=1, max_length=255)]
type TraceParent = Annotated[str, StringConstraints(pattern=_TRACEPARENT_SCHEMA)]
_bearer = HTTPBearer(
    auto_error=False,
    scheme_name="BearerAuth",
    bearerFormat="JWT access token",
    description="RFC 6750 bearer access token; ID tokens are rejected.",
)


class AuthenticationProblem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: ContextLabel
    title: ContextLabel
    status: Annotated[int, Field(ge=400, le=599)]
    detail: Annotated[str, StringConstraints(min_length=1, max_length=2048)]
    code: Annotated[str, StringConstraints(pattern=r"^CMP-[A-Z]+-[0-9]{4}$")]
    trace_id: TraceParent


class MeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    principal_id: UUID
    principal_type: PrincipalType
    display_name: ContextLabel
    organization_id: UUID
    project_id: UUID
    groups: Annotated[list[ContextLabel], Field(max_length=200)]
    scopes: list[ContextLabel]
    request_id: UUID
    trace_id: TraceParent

    @classmethod
    def from_context(cls, context: SecurityContext) -> MeResponse:
        return cls(
            principal_id=context.principal.id,
            principal_type=context.principal.principal_type,
            display_name=context.principal.display_name,
            organization_id=context.organization_id,
            project_id=context.project_id,
            groups=list(context.groups),
            scopes=list(context.scopes),
            request_id=context.request_id,
            trace_id=context.trace_id,
        )


class IdentityHttpError(Exception):
    def __init__(
        self,
        *,
        status: int,
        title: str,
        detail: str,
        code: str,
        request_id: UUID,
        trace_id: str,
        authenticate: str | None = None,
        problem_type: str = "urn:cmp:problem:authentication",
    ) -> None:
        self.problem = AuthenticationProblem(
            type=problem_type,
            title=title,
            status=status,
            detail=detail,
            code=code,
            trace_id=trace_id,
        )
        self.request_id = request_id
        self.authenticate = authenticate
        super().__init__(title)


def _new_traceparent() -> str:
    return f"00-{uuid4().hex}-{uuid4().hex[:16]}-01"


def _request_metadata(
    request_id_text: str | None, traceparent: str | None
) -> tuple[UUID, str]:
    generated_request_id = uuid4()
    try:
        request_id = UUID(request_id_text) if request_id_text else generated_request_id
    except ValueError as error:
        raise IdentityHttpError(
            status=400,
            title="Invalid request identifier",
            detail="X-Request-ID must be a UUID.",
            code="CMP-API-0001",
            request_id=generated_request_id,
            trace_id=_new_traceparent(),
        ) from error
    if traceparent is not None and _TRACEPARENT.fullmatch(traceparent) is None:
        raise IdentityHttpError(
            status=400,
            title="Invalid trace context",
            detail="traceparent is malformed.",
            code="CMP-API-0002",
            request_id=request_id,
            trace_id=_new_traceparent(),
        )
    return request_id, traceparent or _new_traceparent()


class RequestSecurityContextDependency:
    """Reusable authentication boundary for every protected API command/query."""

    def __init__(self, security_service: SecurityContextService | None) -> None:
        self._security_service = security_service

    def __call__(
        self,
        request: Request,
        response: Response,
        credentials: Annotated[
            HTTPAuthorizationCredentials | None, Security(_bearer)
        ],
        x_request_id: Annotated[str | None, Header(alias="X-Request-ID")] = None,
        traceparent: Annotated[str | None, Header()] = None,
    ) -> SecurityContext:
        request_id, trace_id = _request_metadata(x_request_id, traceparent)
        response.headers["X-Request-ID"] = str(request_id)
        response.headers["Cache-Control"] = "no-store"
        if self._security_service is None:
            raise IdentityHttpError(
                status=503,
                title="Authentication unavailable",
                detail="OIDC authentication is not configured.",
                code="CMP-AUTH-0003",
                request_id=request_id,
                trace_id=trace_id,
            )
        if (
            credentials is None
            or credentials.scheme.lower() != "bearer"
            or not credentials.credentials
        ):
            raise IdentityHttpError(
                status=401,
                title="Authentication required",
                detail="A valid bearer access token is required.",
                code="CMP-AUTH-0001",
                request_id=request_id,
                trace_id=trace_id,
                authenticate="Bearer",
            )
        try:
            context = self._security_service.authenticate(
                AuthenticationRequest(
                    access_token=credentials.credentials,
                    request_id=request_id,
                    trace_id=trace_id,
                )
            )
        except AuthenticationUnavailable as error:
            raise IdentityHttpError(
                status=503,
                title="Authentication unavailable",
                detail="The configured identity provider is temporarily unavailable.",
                code="CMP-AUTH-0003",
                request_id=request_id,
                trace_id=trace_id,
            ) from error
        except AuthenticationFailed as error:
            raise IdentityHttpError(
                status=401,
                title="Invalid access token",
                detail="The bearer access token is invalid or expired.",
                code="CMP-AUTH-0001",
                request_id=request_id,
                trace_id=trace_id,
                authenticate='Bearer error="invalid_token"',
            ) from error
        except AccessDenied as error:
            raise IdentityHttpError(
                status=403,
                title="Access denied",
                detail="The authenticated principal is not enabled for this platform.",
                code="CMP-AUTH-0002",
                request_id=request_id,
                trace_id=trace_id,
            ) from error
        request.state.security_context = context
        return context


def install_identity_api(
    application: FastAPI, security_service: SecurityContextService | None
) -> RequestSecurityContextDependency:
    security_context = RequestSecurityContextDependency(security_service)
    application.state.security_context_dependency = security_context

    @application.exception_handler(IdentityHttpError)
    async def identity_error_handler(
        request: Request, error: IdentityHttpError
    ) -> JSONResponse:
        del request
        headers = {
            "Cache-Control": "no-store",
            "X-Request-ID": str(error.request_id),
        }
        if error.authenticate is not None:
            headers["WWW-Authenticate"] = error.authenticate
        return JSONResponse(
            status_code=error.problem.status,
            content=error.problem.model_dump(mode="json"),
            media_type="application/problem+json",
            headers=headers,
        )

    @application.get(
        "/api/v1/me",
        operation_id="getMe",
        response_model=MeResponse,
        responses={
            400: {
                "model": AuthenticationProblem,
                "headers": {
                    "X-Request-ID": {
                        "schema": {"type": "string", "format": "uuid"}
                    }
                },
            },
            401: {
                "model": AuthenticationProblem,
                "headers": {
                    "X-Request-ID": {
                        "schema": {"type": "string", "format": "uuid"}
                    },
                    "WWW-Authenticate": {
                        "schema": {"type": "string"},
                        "description": "RFC 6750 bearer challenge.",
                    }
                },
            },
            403: {
                "model": AuthenticationProblem,
                "headers": {
                    "X-Request-ID": {
                        "schema": {"type": "string", "format": "uuid"}
                    }
                },
            },
            503: {
                "model": AuthenticationProblem,
                "headers": {
                    "X-Request-ID": {
                        "schema": {"type": "string", "format": "uuid"}
                    }
                },
            },
        },
        dependencies=[Depends(security_context)],
        tags=["identity"],
        summary="Return the authenticated principal and selected tenant context.",
    )
    def get_me(
        request: Request,
    ) -> MeResponse:
        context = request.state.security_context
        if not isinstance(context, SecurityContext):
            raise RuntimeError("security context dependency did not initialize request state")
        return MeResponse.from_context(context)

    return security_context

"""Reusable T-04 service-layer authorization dependency for protected routes."""

from __future__ import annotations

from cmp.modules.identity_access.adapters.api.security import IdentityHttpError
from cmp.modules.identity_access.application.authorization import AuthorizationService
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    AuthorizationDenied,
    AuthorizationUnavailable,
    Permission,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from fastapi import Request


class RequestAuthorizationDependency:
    """Authorize one explicit action after the authentication dependency has run."""

    def __init__(
        self,
        authorization_service: AuthorizationService | None,
        permission: Permission,
    ) -> None:
        self._authorization_service = authorization_service
        self.permission = permission

    def __call__(self, request: Request) -> AuthorizationDecision:
        context = getattr(request.state, "security_context", None)
        if not isinstance(context, SecurityContext):
            raise RuntimeError("authentication dependency must run before authorization")
        if self._authorization_service is None:
            raise IdentityHttpError(
                status=503,
                title="Authorization unavailable",
                detail="Authorization is not configured for this deployment.",
                code="CMP-AUTHZ-0002",
                request_id=context.request_id,
                trace_id=context.trace_id,
                problem_type="urn:cmp:problem:authorization",
            )
        try:
            decision = self._authorization_service.authorize(context, self.permission)
        except AuthorizationUnavailable as error:
            raise IdentityHttpError(
                status=503,
                title="Authorization unavailable",
                detail="The authorization policy store is temporarily unavailable.",
                code="CMP-AUTHZ-0002",
                request_id=context.request_id,
                trace_id=context.trace_id,
                problem_type="urn:cmp:problem:authorization",
            ) from error
        except AuthorizationDenied as error:
            raise IdentityHttpError(
                status=403,
                title="Access denied",
                detail="The authenticated principal is not allowed to perform this action.",
                code="CMP-AUTHZ-0001",
                request_id=context.request_id,
                trace_id=context.trace_id,
                problem_type="urn:cmp:problem:authorization",
            ) from error
        request.state.authorization_decision = decision
        return decision

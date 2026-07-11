"""Authenticate verified access tokens and construct request security contexts."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Protocol

from cmp.modules.identity_access.domain.security import (
    AccessDenied,
    AuthenticationRequest,
    Principal,
    SecurityContext,
    VerifiedAccessToken,
)


class AccessTokenVerifier(Protocol):
    def verify(self, access_token: str) -> VerifiedAccessToken: ...


class PrincipalRepository(Protocol):
    def resolve_or_provision(
        self, token: VerifiedAccessToken, observed_at: datetime
    ) -> Principal: ...


class SecurityContextService:
    def __init__(
        self,
        *,
        verifier: AccessTokenVerifier,
        principals: PrincipalRepository,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._verifier = verifier
        self._principals = principals
        self._clock = clock or (lambda: datetime.now(UTC))

    def authenticate(self, request: AuthenticationRequest) -> SecurityContext:
        token = self._verifier.verify(request.access_token)
        observed_at = self._clock()
        principal = self._principals.resolve_or_provision(token, observed_at)
        if not principal.active:
            raise AccessDenied("principal_inactive")
        return SecurityContext(
            principal=principal,
            organization_id=token.organization_id,
            project_id=token.project_id,
            issuer=token.issuer,
            subject=token.subject,
            token_id=token.token_id,
            groups=token.groups,
            scopes=token.scopes,
            request_id=request.request_id,
            trace_id=request.trace_id,
            authenticated_at=observed_at,
        )

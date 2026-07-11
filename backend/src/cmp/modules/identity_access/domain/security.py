"""T-03 principal, verified token, and request security-context value objects."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class IdentityAccessError(Exception):
    """Base error for identity and authentication operations."""


class AuthenticationFailed(IdentityAccessError):
    """A bearer token could not be trusted or mapped safely."""

    def __init__(self, code: str = "invalid_token") -> None:
        self.code = code
        super().__init__(code)


class AccessDenied(IdentityAccessError):
    """The token is valid, but its principal cannot use the platform."""

    def __init__(self, code: str = "access_denied") -> None:
        self.code = code
        super().__init__(code)


class AuthenticationUnavailable(IdentityAccessError):
    """Authentication is intentionally fail-closed because it is not configured."""


class PrincipalType(StrEnum):
    USER = "user"
    SERVICE = "service"


def _require_trimmed(name: str, value: str, maximum: int) -> None:
    if not value or value != value.strip() or len(value) > maximum:
        raise ValueError(f"{name} must be trimmed and contain 1..{maximum} characters")


def _require_aware(name: str, value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")


@dataclass(frozen=True, slots=True)
class Principal:
    id: UUID
    principal_type: PrincipalType
    display_name: str
    active: bool

    def __post_init__(self) -> None:
        _require_trimmed("display_name", self.display_name, 255)


@dataclass(frozen=True, slots=True)
class VerifiedAccessToken:
    """Claims accepted only after signature, type, issuer, audience, and time validation."""

    issuer: str
    subject: str
    audiences: tuple[str, ...]
    expires_at: datetime
    issued_at: datetime
    token_id: str
    client_id: str
    principal_type: PrincipalType
    display_name: str
    organization_id: UUID
    project_id: UUID
    groups: tuple[str, ...]
    scopes: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_trimmed("issuer", self.issuer, 2048)
        _require_trimmed("subject", self.subject, 255)
        if not self.subject.isascii():
            raise ValueError("subject must be ASCII")
        if not self.audiences or any(not audience for audience in self.audiences):
            raise ValueError("at least one audience is required")
        _require_aware("expires_at", self.expires_at)
        _require_aware("issued_at", self.issued_at)
        if self.expires_at <= self.issued_at:
            raise ValueError("access token expiry must follow its issue time")
        _require_trimmed("token_id", self.token_id, 255)
        _require_trimmed("client_id", self.client_id, 255)
        _require_trimmed("display_name", self.display_name, 255)
        if self.organization_id.int == 0 or self.project_id.int == 0:
            raise ValueError("organization_id and project_id must be non-zero UUIDs")
        if tuple(sorted(set(self.groups))) != self.groups:
            raise ValueError("groups must be sorted and unique")
        if len(self.groups) > 200:
            raise ValueError("groups must contain at most 200 entries")
        if any(not group or group != group.strip() or len(group) > 255 for group in self.groups):
            raise ValueError("groups must be trimmed and contain 1..255 characters")
        if tuple(sorted(set(self.scopes))) != self.scopes:
            raise ValueError("scopes must be sorted and unique")
        if any(not scope or len(scope) > 255 for scope in self.scopes):
            raise ValueError("scopes must contain 1..255 characters")


@dataclass(frozen=True, slots=True)
class AuthenticationRequest:
    access_token: str = field(repr=False)
    request_id: UUID
    trace_id: str

    def __post_init__(self) -> None:
        _require_trimmed("access_token", self.access_token, 16_384)
        _require_trimmed("trace_id", self.trace_id, 255)


@dataclass(frozen=True, slots=True)
class SecurityContext:
    principal: Principal
    organization_id: UUID
    project_id: UUID
    issuer: str
    subject: str
    token_id: str
    groups: tuple[str, ...]
    scopes: tuple[str, ...]
    request_id: UUID
    trace_id: str
    authenticated_at: datetime

    def __post_init__(self) -> None:
        _require_aware("authenticated_at", self.authenticated_at)

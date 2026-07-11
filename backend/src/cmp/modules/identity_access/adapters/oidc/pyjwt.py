"""Strict RFC 9068-style JWT access-token validation using PyJWT."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol
from urllib.parse import urlsplit
from uuid import UUID

import jwt
from cmp.modules.identity_access.domain.security import (
    AuthenticationFailed,
    AuthenticationUnavailable,
    PrincipalType,
    VerifiedAccessToken,
)
from jwt import PyJWKClient
from jwt.exceptions import (
    ExpiredSignatureError,
    ImmatureSignatureError,
    InvalidAudienceError,
    InvalidIssuerError,
    MissingRequiredClaimError,
    PyJWKClientConnectionError,
    PyJWTError,
)

_ASYMMETRIC_ALGORITHMS = frozenset(
    {
        "RS256",
        "RS384",
        "RS512",
        "PS256",
        "PS384",
        "PS512",
        "ES256",
        "ES384",
        "ES512",
        "EdDSA",
    }
)


class SigningKeyResolver(Protocol):
    def resolve(self, access_token: str, key_id: str) -> Any: ...


@dataclass(frozen=True, slots=True)
class OidcAccessTokenConfig:
    issuer: str
    audience: str
    algorithms: tuple[str, ...] = ("RS256",)
    token_types: tuple[str, ...] = ("at+jwt", "application/at+jwt")
    clock_skew_seconds: int = 60
    client_id_claim: str = "client_id"
    organization_claim: str = "organization_id"
    project_claim: str = "project_id"
    groups_claim: str = "groups"
    display_name_claim: str = "preferred_username"
    service_grant_claim: str = "gty"
    service_grant_values: tuple[str, ...] = ("client-credentials",)
    maximum_groups: int = 200

    def __post_init__(self) -> None:
        if not self.issuer or self.issuer != self.issuer.strip():
            raise ValueError("OIDC issuer must be non-empty and trimmed")
        if not self.audience or self.audience != self.audience.strip():
            raise ValueError("OIDC audience must be non-empty and trimmed")
        if not self.algorithms or any(
            algorithm not in _ASYMMETRIC_ALGORITHMS for algorithm in self.algorithms
        ):
            raise ValueError("OIDC algorithms must be an explicit asymmetric allowlist")
        if len(set(self.algorithms)) != len(self.algorithms):
            raise ValueError("OIDC algorithm allowlist must not contain duplicates")
        if not self.token_types:
            raise ValueError("at least one JWT access-token type is required")
        if len({value.lower() for value in self.token_types}) != len(self.token_types):
            raise ValueError("JWT access-token types must not contain duplicates")
        if not 0 <= self.clock_skew_seconds <= 300:
            raise ValueError("clock skew must be between 0 and 300 seconds")
        if not 0 <= self.maximum_groups <= 200:
            raise ValueError("maximum_groups must be between 0 and 200")
        claim_names = (
            self.client_id_claim,
            self.organization_claim,
            self.project_claim,
            self.groups_claim,
            self.display_name_claim,
            self.service_grant_claim,
        )
        if any(
            not name or name != name.strip() or len(name) > 255 for name in claim_names
        ):
            raise ValueError("OIDC claim names must be trimmed and contain 1..255 characters")
        if self.organization_claim == self.project_claim:
            raise ValueError("organization and project claims must be distinct")
        if not self.service_grant_values or any(
            not value or value != value.strip() or len(value) > 255
            for value in self.service_grant_values
        ):
            raise ValueError("service grant values must be non-empty, trimmed strings")
        if len(set(self.service_grant_values)) != len(self.service_grant_values):
            raise ValueError("service grant values must not contain duplicates")


class PyJwkClientSigningKeyResolver:
    """Resolve only from an operator-configured JWKS URL; no token-driven discovery."""

    def __init__(
        self,
        jwks_url: str,
        *,
        timeout_seconds: float = 5.0,
        cache_lifespan_seconds: int = 300,
        allow_loopback_http: bool = False,
    ) -> None:
        parsed = urlsplit(jwks_url)
        loopback = parsed.hostname in {"127.0.0.1", "::1", "localhost"}
        if parsed.scheme != "https" and not (
            allow_loopback_http and parsed.scheme == "http" and loopback
        ):
            raise ValueError("JWKS URL must use HTTPS (loopback HTTP is development-only)")
        if parsed.username or parsed.password or parsed.fragment:
            raise ValueError("JWKS URL must not contain credentials or a fragment")
        self._client = PyJWKClient(
            jwks_url,
            cache_keys=False,
            cache_jwk_set=True,
            lifespan=cache_lifespan_seconds,
            timeout=timeout_seconds,
        )

    def resolve(self, access_token: str, key_id: str) -> Any:
        key = self._client.get_signing_key_from_jwt(access_token)
        if key.key_id != key_id:
            raise AuthenticationFailed("signing_key_mismatch")
        return key.key


class StaticSigningKeyResolver:
    """In-memory resolver for the development IdP and deterministic tests."""

    def __init__(self, keys: Mapping[str, Any]) -> None:
        self._keys = dict(keys)

    def resolve(self, access_token: str, key_id: str) -> Any:
        del access_token
        try:
            return self._keys[key_id]
        except KeyError as error:
            raise AuthenticationFailed("unknown_signing_key") from error


def _claim_string(claims: Mapping[str, Any], name: str, maximum: int = 255) -> str:
    value = claims.get(name)
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or "\x00" in value
    ):
        raise AuthenticationFailed("invalid_claims")
    if len(value) > maximum:
        raise AuthenticationFailed("invalid_claims")
    return value


def _claim_timestamp(claims: Mapping[str, Any], name: str) -> datetime:
    value = claims.get(name)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise AuthenticationFailed("invalid_claims")
    try:
        return datetime.fromtimestamp(value, UTC)
    except (OSError, OverflowError, ValueError) as error:
        raise AuthenticationFailed("invalid_claims") from error


class PyJwtAccessTokenVerifier:
    def __init__(
        self,
        *,
        config: OidcAccessTokenConfig,
        signing_keys: SigningKeyResolver,
    ) -> None:
        self._config = config
        self._signing_keys = signing_keys

    def _validate_header(self, access_token: str) -> tuple[str, str]:
        try:
            header = jwt.get_unverified_header(access_token)
        except PyJWTError as error:
            raise AuthenticationFailed("malformed_token") from error
        token_type = header.get("typ")
        if not isinstance(token_type, str) or token_type.lower() not in {
            allowed.lower() for allowed in self._config.token_types
        }:
            raise AuthenticationFailed("invalid_token_type")
        algorithm = header.get("alg")
        if not isinstance(algorithm, str) or algorithm not in self._config.algorithms:
            raise AuthenticationFailed("algorithm_not_allowed")
        key_id = header.get("kid")
        if not isinstance(key_id, str) or not key_id or len(key_id) > 255:
            raise AuthenticationFailed("missing_signing_key_id")
        return algorithm, key_id

    def verify(self, access_token: str) -> VerifiedAccessToken:
        if not access_token or len(access_token) > 16_384 or access_token.count(".") != 2:
            raise AuthenticationFailed("malformed_token")
        algorithm, key_id = self._validate_header(access_token)
        try:
            signing_key = self._signing_keys.resolve(access_token, key_id)
            claims = jwt.decode(
                access_token,
                signing_key,
                algorithms=list(self._config.algorithms),
                audience=self._config.audience,
                issuer=self._config.issuer,
                leeway=self._config.clock_skew_seconds,
                options={
                    "require": [
                        "iss",
                        "sub",
                        "aud",
                        "exp",
                        "iat",
                        "jti",
                        self._config.client_id_claim,
                    ],
                },
            )
        except ExpiredSignatureError as error:
            raise AuthenticationFailed("token_expired") from error
        except ImmatureSignatureError as error:
            raise AuthenticationFailed("token_not_yet_valid") from error
        except InvalidAudienceError as error:
            raise AuthenticationFailed("invalid_audience") from error
        except InvalidIssuerError as error:
            raise AuthenticationFailed("invalid_issuer") from error
        except MissingRequiredClaimError as error:
            raise AuthenticationFailed("missing_required_claim") from error
        except PyJWKClientConnectionError as error:
            raise AuthenticationUnavailable("JWKS endpoint is unavailable") from error
        except AuthenticationFailed:
            raise
        except PyJWTError as error:
            raise AuthenticationFailed("invalid_token") from error

        if algorithm not in self._config.algorithms:
            raise AuthenticationFailed("algorithm_not_allowed")
        try:
            return self._map_claims(claims)
        except (TypeError, ValueError) as error:
            raise AuthenticationFailed("invalid_claims") from error

    def _map_claims(self, claims: Mapping[str, Any]) -> VerifiedAccessToken:
        issuer = _claim_string(claims, "iss", 2048)
        subject = _claim_string(claims, "sub")
        token_id = _claim_string(claims, "jti")
        client_id = _claim_string(claims, self._config.client_id_claim)
        audience_claim = claims.get("aud")
        if isinstance(audience_claim, str):
            audiences = (audience_claim,)
        elif isinstance(audience_claim, list) and audience_claim and all(
            isinstance(item, str) and item for item in audience_claim
        ):
            audiences = tuple(audience_claim)
        else:
            raise AuthenticationFailed("invalid_claims")

        grant = claims.get(self._config.service_grant_claim)
        if grant is not None and not isinstance(grant, str):
            raise AuthenticationFailed("invalid_claims")
        principal_type = (
            PrincipalType.SERVICE
            if isinstance(grant, str) and grant in self._config.service_grant_values
            else PrincipalType.USER
        )
        if principal_type is PrincipalType.SERVICE and subject != client_id:
            raise AuthenticationFailed("service_subject_mismatch")
        display_value = claims.get(self._config.display_name_claim)
        if display_value is None:
            display_name = client_id if principal_type is PrincipalType.SERVICE else subject
        elif (
            not isinstance(display_value, str)
            or not display_value
            or display_value != display_value.strip()
            or len(display_value) > 255
            or "\x00" in display_value
        ):
            raise AuthenticationFailed("invalid_claims")
        else:
            display_name = display_value

        organization_id = UUID(_claim_string(claims, self._config.organization_claim))
        project_id = UUID(_claim_string(claims, self._config.project_claim))
        groups_value = claims.get(self._config.groups_claim, [])
        if not isinstance(groups_value, list) or not all(
            isinstance(item, str)
            and item
            and item == item.strip()
            and len(item) <= 255
            and "\x00" not in item
            for item in groups_value
        ):
            raise AuthenticationFailed("invalid_claims")
        if len(groups_value) > self._config.maximum_groups:
            raise AuthenticationFailed("too_many_groups")
        groups = tuple(sorted(set(groups_value)))

        scope_value = claims.get("scope", "")
        if not isinstance(scope_value, str):
            raise AuthenticationFailed("invalid_claims")
        scopes = tuple(sorted(set(scope_value.split())))
        if any(len(scope) > 255 or "\x00" in scope for scope in scopes):
            raise AuthenticationFailed("invalid_claims")
        return VerifiedAccessToken(
            issuer=issuer,
            subject=subject,
            audiences=audiences,
            expires_at=_claim_timestamp(claims, "exp"),
            issued_at=_claim_timestamp(claims, "iat"),
            token_id=token_id,
            client_id=client_id,
            principal_type=principal_type,
            display_name=display_name.strip(),
            organization_id=organization_id,
            project_id=project_id,
            groups=groups,
            scopes=scopes,
        )

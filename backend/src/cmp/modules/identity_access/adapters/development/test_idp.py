"""Small non-production RSA issuer for deterministic OIDC integration tests."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import jwt
from cmp.modules.identity_access.adapters.oidc.pyjwt import StaticSigningKeyResolver
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm


class DevelopmentTestIdp:
    """Issue signed synthetic access tokens; this is not an authorization server."""

    def __init__(
        self,
        *,
        issuer: str = "https://test-idp.invalid",
        audience: str = "urn:cmp:test-api",
        key_id: str = "cmp-test-key-1",
    ) -> None:
        self.issuer = issuer
        self.audience = audience
        self.key_id = key_id
        self._private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    def signing_key_resolver(self) -> StaticSigningKeyResolver:
        return StaticSigningKeyResolver({self.key_id: self._private_key.public_key()})

    def jwks_document(self) -> dict[str, object]:
        """Return only the public key material needed by an integration-test resource server."""

        key = RSAAlgorithm.to_jwk(self._private_key.public_key(), as_dict=True)
        if not isinstance(key, dict):
            raise RuntimeError("PyJWT did not render an RSA JWK mapping")
        key.update({"kid": self.key_id, "alg": "RS256", "use": "sig"})
        return {"keys": [key]}

    def issue_user_token(
        self,
        *,
        subject: str,
        organization_id: UUID,
        project_id: UUID,
        display_name: str,
        groups: Iterable[str] = (),
        scopes: Iterable[str] = ("openid",),
        now: datetime | None = None,
        lifetime: timedelta = timedelta(minutes=5),
        token_type: str = "at+jwt",
        issuer: str | None = None,
        audience: str | None = None,
        overrides: Mapping[str, Any] | None = None,
        drop_claims: Iterable[str] = (),
    ) -> str:
        return self._issue(
            subject=subject,
            client_id="cmp-test-web",
            organization_id=organization_id,
            project_id=project_id,
            display_name=display_name,
            grant_type="authorization_code",
            groups=groups,
            scopes=scopes,
            now=now,
            lifetime=lifetime,
            token_type=token_type,
            issuer=issuer,
            audience=audience,
            overrides=overrides,
            drop_claims=drop_claims,
        )

    def issue_service_token(
        self,
        *,
        client_id: str,
        organization_id: UUID,
        project_id: UUID,
        groups: Iterable[str] = (),
        scopes: Iterable[str] = (),
        now: datetime | None = None,
        lifetime: timedelta = timedelta(minutes=5),
        token_type: str = "at+jwt",
        overrides: Mapping[str, Any] | None = None,
        drop_claims: Iterable[str] = (),
    ) -> str:
        return self._issue(
            subject=client_id,
            client_id=client_id,
            organization_id=organization_id,
            project_id=project_id,
            display_name=client_id,
            grant_type="client-credentials",
            groups=groups,
            scopes=scopes,
            now=now,
            lifetime=lifetime,
            token_type=token_type,
            overrides=overrides,
            drop_claims=drop_claims,
        )

    def _issue(
        self,
        *,
        subject: str,
        client_id: str,
        organization_id: UUID,
        project_id: UUID,
        display_name: str,
        grant_type: str,
        groups: Iterable[str],
        scopes: Iterable[str],
        now: datetime | None,
        lifetime: timedelta,
        token_type: str,
        issuer: str | None = None,
        audience: str | None = None,
        overrides: Mapping[str, Any] | None = None,
        drop_claims: Iterable[str] = (),
    ) -> str:
        issued_at = now or datetime.now(UTC)
        claims: dict[str, Any] = {
            "iss": issuer or self.issuer,
            "sub": subject,
            "aud": audience or self.audience,
            "exp": issued_at + lifetime,
            "iat": issued_at,
            "jti": str(uuid4()),
            "client_id": client_id,
            "organization_id": str(organization_id),
            "project_id": str(project_id),
            "preferred_username": display_name,
            "groups": list(groups),
            "scope": " ".join(scopes),
            "gty": grant_type,
        }
        claims.update(overrides or {})
        for name in drop_claims:
            claims.pop(name, None)
        return jwt.encode(
            claims,
            self._private_key,
            algorithm="RS256",
            headers={"alg": "RS256", "kid": self.key_id, "typ": token_type},
        )

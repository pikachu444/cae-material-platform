from __future__ import annotations

import asyncio
import json
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from uuid import UUID, uuid5

import httpx
from cmp.apps.api import create_app
from cmp.bootstrap.settings import Settings
from cmp.modules.identity_access.adapters.development.test_idp import DevelopmentTestIdp
from cmp.modules.identity_access.adapters.oidc.pyjwt import (
    OidcAccessTokenConfig,
    PyJwkClientSigningKeyResolver,
    PyJwtAccessTokenVerifier,
)
from cmp.modules.identity_access.application.security import SecurityContextService
from cmp.modules.identity_access.domain.security import (
    AuthenticationUnavailable,
    Principal,
    VerifiedAccessToken,
)
from fastapi import FastAPI

ORG = UUID("40000000-0000-4000-8000-000000000001")
PROJECT = UUID("40000000-0000-4000-8000-000000000002")
REQUEST = UUID("40000000-0000-4000-8000-000000000003")
TRACE = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
NAMESPACE = UUID("40000000-0000-4000-8000-000000000004")


class _JwksHandler(BaseHTTPRequestHandler):
    document = b""

    def do_GET(self) -> None:
        if self.path != "/jwks":
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(self.document)))
        self.end_headers()
        self.wfile.write(self.document)

    def log_message(self, format: str, *args: object) -> None:
        del format, args


class _Principals:
    def resolve_or_provision(
        self, token: VerifiedAccessToken, observed_at: datetime
    ) -> Principal:
        del observed_at
        return Principal(
            uuid5(NAMESPACE, f"{token.issuer}\0{token.subject}"),
            token.principal_type,
            token.display_name,
            True,
        )


class _UnavailableKeys:
    def resolve(self, access_token: str, key_id: str) -> object:
        del access_token, key_id
        raise AuthenticationUnavailable("synthetic JWKS outage")


def _security(idp: DevelopmentTestIdp) -> SecurityContextService:
    verifier = PyJwtAccessTokenVerifier(
        config=OidcAccessTokenConfig(
            issuer=idp.issuer,
            audience=idp.audience,
            clock_skew_seconds=0,
        ),
        signing_keys=idp.signing_key_resolver(),
    )
    return SecurityContextService(verifier=verifier, principals=_Principals())


def _request(
    app: FastAPI,
    token: str | None,
    extra_headers: dict[str, str] | None = None,
) -> httpx.Response:
    async def send() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        headers = {"X-Request-ID": str(REQUEST), "traceparent": TRACE}
        headers.update(extra_headers or {})
        if token is not None:
            headers["Authorization"] = f"Bearer {token}"
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.get("/api/v1/me", headers=headers)

    return asyncio.run(send())


def test_user_and_service_tokens_resolve_distinct_me_contexts() -> None:
    idp = DevelopmentTestIdp()
    app = create_app(Settings(environment="test"), _security(idp))
    user = idp.issue_user_token(
        subject="api-user",
        organization_id=ORG,
        project_id=PROJECT,
        display_name="API User",
        groups=("test-engineers",),
        scopes=("openid", "profile"),
    )
    service = idp.issue_service_token(
        client_id="api-worker",
        organization_id=ORG,
        project_id=PROJECT,
        scopes=("jobs:submit",),
    )

    user_response = _request(app, user)
    service_response = _request(app, service)

    assert user_response.status_code == 200
    assert user_response.json()["principal_type"] == "user"
    assert user_response.json()["organization_id"] == str(ORG)
    assert user_response.json()["project_id"] == str(PROJECT)
    assert user_response.json()["request_id"] == str(REQUEST)
    assert user_response.headers["x-request-id"] == str(REQUEST)
    assert user_response.headers["cache-control"] == "no-store"
    assert service_response.status_code == 200
    assert service_response.json()["principal_type"] == "service"
    assert service_response.json()["display_name"] == "api-worker"


def test_configured_loopback_jwks_validates_test_idp_access_token() -> None:
    idp = DevelopmentTestIdp()
    _JwksHandler.document = json.dumps(idp.jwks_document()).encode("utf-8")
    server = ThreadingHTTPServer(("127.0.0.1", 0), _JwksHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        verifier = PyJwtAccessTokenVerifier(
            config=OidcAccessTokenConfig(
                issuer=idp.issuer,
                audience=idp.audience,
                clock_skew_seconds=0,
            ),
            signing_keys=PyJwkClientSigningKeyResolver(
                f"http://127.0.0.1:{server.server_port}/jwks",
                allow_loopback_http=True,
            ),
        )
        app = create_app(
            Settings(environment="test"),
            SecurityContextService(verifier=verifier, principals=_Principals()),
        )
        token = idp.issue_user_token(
            subject="jwks-user",
            organization_id=ORG,
            project_id=PROJECT,
            display_name="JWKS User",
        )

        response = _request(app, token)

        assert response.status_code == 200
        assert response.json()["display_name"] == "JWKS User"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_missing_bearer_and_id_token_confusion_return_sanitized_401() -> None:
    idp = DevelopmentTestIdp()
    app = create_app(Settings(environment="test"), _security(idp))
    id_token = idp.issue_user_token(
        subject="api-user",
        organization_id=ORG,
        project_id=PROJECT,
        display_name="API User",
        token_type="JWT",
    )

    missing = _request(app, None)
    confused = _request(app, id_token)

    assert missing.status_code == 401
    assert missing.headers["www-authenticate"] == "Bearer"
    assert confused.status_code == 401
    assert confused.headers["www-authenticate"] == 'Bearer error="invalid_token"'
    assert confused.headers["content-type"].startswith("application/problem+json")
    assert id_token not in confused.text


def test_me_fails_closed_when_oidc_is_not_configured() -> None:
    response = _request(create_app(Settings(environment="test")), "not-a-token")

    assert response.status_code == 503
    assert response.json()["code"] == "CMP-AUTH-0003"


def test_me_fails_closed_and_sanitizes_temporary_jwks_failure() -> None:
    idp = DevelopmentTestIdp()
    verifier = PyJwtAccessTokenVerifier(
        config=OidcAccessTokenConfig(issuer=idp.issuer, audience=idp.audience),
        signing_keys=_UnavailableKeys(),
    )
    app = create_app(
        Settings(environment="test"),
        SecurityContextService(verifier=verifier, principals=_Principals()),
    )
    token = idp.issue_user_token(
        subject="outage-user",
        organization_id=ORG,
        project_id=PROJECT,
        display_name="Outage User",
    )

    response = _request(app, token)

    assert response.status_code == 503
    assert response.json()["code"] == "CMP-AUTH-0003"
    assert "synthetic JWKS outage" not in response.text
    assert token not in response.text


def test_missing_project_claim_is_never_accepted_as_request_context() -> None:
    idp = DevelopmentTestIdp()
    app = create_app(Settings(environment="test"), _security(idp))
    token = idp.issue_user_token(
        subject="api-user",
        organization_id=ORG,
        project_id=PROJECT,
        display_name="API User",
        drop_claims=("project_id",),
    )

    response = _request(app, token)

    assert response.status_code == 401
    assert response.json()["code"] == "CMP-AUTH-0001"


def test_error_responses_keep_a_sanitized_request_correlation_id() -> None:
    app = create_app(Settings(environment="test"))

    response = _request(app, "not-a-token", {"X-Request-ID": "not-a-uuid"})

    assert response.status_code == 400
    assert UUID(response.headers["x-request-id"])
    assert response.headers["cache-control"] == "no-store"
    assert "not-a-token" not in response.text

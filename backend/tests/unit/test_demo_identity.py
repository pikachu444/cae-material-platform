from __future__ import annotations

import asyncio

import httpx
import jwt
import pytest
from cmp.bootstrap.demo_identity import (
    DEMO_GROUP,
    DEMO_ORGANIZATION_ID,
    DEMO_PROJECT_ID,
    DemoIdentity,
    install_demo_identity_api,
)
from cmp.bootstrap.settings import Settings
from fastapi import FastAPI


def _get(application: FastAPI, path: str) -> httpx.Response:
    async def send() -> httpx.Response:
        transport = httpx.ASGITransport(app=application)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.get(path)

    return asyncio.run(send())


def test_demo_identity_requires_explicit_demo_environment() -> None:
    with pytest.raises(ValueError, match="CMP_ENVIRONMENT=demo"):
        DemoIdentity.from_settings(Settings(environment="development", demo_identity=True))

    with pytest.raises(ValueError, match="cannot be combined"):
        DemoIdentity.from_settings(
            Settings(
                environment="demo",
                demo_identity=True,
                oidc_issuer="https://idp.example.test",
            )
        )


def test_demo_identity_route_is_absent_without_explicit_opt_in() -> None:
    application = FastAPI()
    install_demo_identity_api(application, None)

    response = _get(application, "/api/v1/demo-identity/token")

    assert response.status_code == 404
    assert application.state.demo_identity_enabled is False


def test_explicit_demo_identity_issues_short_lived_signed_tenant_token() -> None:
    identity = DemoIdentity.from_settings(Settings(environment="demo", demo_identity=True))
    assert identity is not None
    application = FastAPI()
    install_demo_identity_api(application, identity)

    response = _get(application, "/api/v1/demo-identity/token")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    body = response.json()
    claims = jwt.decode(
        body["access_token"],
        options={"verify_signature": False, "verify_aud": False},
    )
    assert claims["iss"] == identity.issuer
    assert claims["aud"] == identity.audience
    assert claims["organization_id"] == str(DEMO_ORGANIZATION_ID)
    assert claims["project_id"] == str(DEMO_PROJECT_ID)
    assert claims["groups"] == [DEMO_GROUP]
    assert body["expires_in_seconds"] == 15 * 60
    assert application.state.demo_identity_enabled is True

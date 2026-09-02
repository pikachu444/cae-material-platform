from __future__ import annotations

import asyncio

import httpx
import jwt
import pytest
from cmp.bootstrap.demo_identity import (
    DEMO_GROUP,
    DEMO_ORGANIZATION_ID,
    DEMO_PLAN_AUTHOR_SUBJECT,
    DEMO_PROJECT_ID,
    DEMO_REVIEWER_GROUP,
    DEMO_USER_GROUP,
    DEMO_WORKER_CLIENT_ID,
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
    assert body["persona"] == "administrator"
    assert body["expires_in_seconds"] == 15 * 60
    assert application.state.demo_identity_enabled is True


def test_explicit_demo_identity_issues_distinct_user_and_reviewer_personas() -> None:
    identity = DemoIdentity.from_settings(Settings(environment="demo", demo_identity=True))
    assert identity is not None
    application = FastAPI()
    install_demo_identity_api(application, identity)

    user_response = _get(application, "/api/v1/demo-identity/token?persona=user")
    assert user_response.status_code == 200
    user_body = user_response.json()
    user_claims = jwt.decode(
        user_body["access_token"],
        options={"verify_signature": False, "verify_aud": False},
    )
    assert user_body["persona"] == "user"
    assert user_body["group"] == DEMO_USER_GROUP
    assert user_claims["sub"] == "cmp-demo-user"
    assert user_claims["groups"] == [DEMO_USER_GROUP]

    response = _get(application, "/api/v1/demo-identity/token?persona=reviewer")

    assert response.status_code == 200
    body = response.json()
    claims = jwt.decode(
        body["access_token"],
        options={"verify_signature": False, "verify_aud": False},
    )
    assert body["persona"] == "reviewer"
    assert body["group"] == DEMO_REVIEWER_GROUP
    assert claims["sub"] == "cmp-demo-reviewer"
    assert claims["groups"] == [DEMO_REVIEWER_GROUP]

    author_response = _get(application, "/api/v1/demo-identity/token?persona=plan_author")
    assert author_response.status_code == 200
    author_body = author_response.json()
    author_claims = jwt.decode(
        author_body["access_token"],
        options={"verify_signature": False, "verify_aud": False},
    )
    assert author_body["persona"] == "plan_author"
    assert author_body["group"] == DEMO_REVIEWER_GROUP
    assert author_claims["sub"] == DEMO_PLAN_AUTHOR_SUBJECT
    assert author_claims["sub"] != claims["sub"]
    assert author_claims["groups"] == [DEMO_GROUP, DEMO_REVIEWER_GROUP]


def test_demo_worker_token_is_a_distinct_service_principal() -> None:
    identity = DemoIdentity.from_settings(Settings(environment="demo", demo_identity=True))
    assert identity is not None

    claims = jwt.decode(
        identity.issue_worker_access_token(),
        options={"verify_signature": False, "verify_aud": False},
    )

    assert claims["sub"] == DEMO_WORKER_CLIENT_ID
    assert claims["client_id"] == DEMO_WORKER_CLIENT_ID
    assert claims["gty"] == "client-credentials"
    assert claims["groups"] == []
    assert claims["organization_id"] == str(DEMO_ORGANIZATION_ID)
    assert claims["project_id"] == str(DEMO_PROJECT_ID)


def test_demo_identity_rejects_unknown_persona() -> None:
    identity = DemoIdentity.from_settings(Settings(environment="demo", demo_identity=True))
    assert identity is not None
    application = FastAPI()
    install_demo_identity_api(application, identity)

    response = _get(application, "/api/v1/demo-identity/token?persona=operator")

    assert response.status_code == 422

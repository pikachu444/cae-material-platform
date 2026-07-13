"""Explicit, local-only identity composition for the runnable product demo.

The demo issuer remains a signed JWT issuer and is verified by the same request
security boundary as an operator-configured OIDC issuer.  It is intentionally
unavailable unless both ``CMP_ENVIRONMENT=demo`` and ``CMP_DEMO_IDENTITY=true``
are set; this module never supplies a production authentication fallback.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Final
from uuid import UUID

from fastapi import FastAPI, Response
from pydantic import BaseModel, ConfigDict, Field

from cmp.bootstrap.settings import Settings
from cmp.modules.identity_access.adapters.development.test_idp import DevelopmentTestIdp

DEMO_ORGANIZATION_ID: Final = UUID("d0000000-0000-4000-8000-000000000001")
DEMO_PROJECT_ID: Final = UUID("d0000000-0000-4000-8000-000000000002")
DEMO_GROUP: Final = "cmp-demo-material-team"
DEMO_SUBJECT: Final = "cmp-demo-user"


@dataclass(frozen=True, slots=True)
class DemoIdentity:
    """One in-process issuer and its fixed, clearly synthetic tenant context."""

    issuer: str
    audience: str
    idp: DevelopmentTestIdp

    @classmethod
    def from_settings(cls, settings: Settings) -> DemoIdentity | None:
        if not settings.demo_identity:
            return None
        if settings.environment != "demo":
            raise ValueError("CMP_DEMO_IDENTITY is permitted only when CMP_ENVIRONMENT=demo")
        if any((settings.oidc_issuer, settings.oidc_audience, settings.oidc_jwks_url)):
            raise ValueError(
                "CMP_DEMO_IDENTITY cannot be combined with CMP_OIDC_ISSUER, "
                "CMP_OIDC_AUDIENCE, or CMP_OIDC_JWKS_URL"
            )
        if not settings.demo_identity_issuer.strip() or not settings.demo_identity_audience.strip():
            raise ValueError("demo identity issuer and audience must be non-empty")
        issuer = settings.demo_identity_issuer.strip()
        audience = settings.demo_identity_audience.strip()
        return cls(issuer, audience, DevelopmentTestIdp(issuer=issuer, audience=audience))

    def issue_access_token(self) -> str:
        """Issue a deliberately short-lived browser token for the synthetic demo tenant."""

        return self.idp.issue_user_token(
            subject=DEMO_SUBJECT,
            organization_id=DEMO_ORGANIZATION_ID,
            project_id=DEMO_PROJECT_ID,
            display_name="CMP local demo user",
            groups=(DEMO_GROUP,),
            scopes=("openid", "profile"),
            lifetime=timedelta(minutes=15),
        )


class DemoAccessTokenResponse(BaseModel):
    """Public only in the explicit local-demo composition."""

    model_config = ConfigDict(extra="forbid")

    access_token: str = Field(min_length=1)
    token_type: str = "Bearer"
    expires_in_seconds: int = Field(ge=1)
    organization_id: UUID
    project_id: UUID
    group: str


def install_demo_identity_api(application: FastAPI, identity: DemoIdentity | None) -> None:
    """Install no route unless the explicit demo composition constructed an issuer."""

    application.state.demo_identity_enabled = identity is not None
    if identity is None:
        return

    @application.get(
        "/api/v1/demo-identity/token",
        operation_id="issueLocalDemoAccessToken",
        response_model=DemoAccessTokenResponse,
        tags=["development"],
        summary="Issue a short-lived token for the explicit local demo tenant.",
    )
    def issue_local_demo_access_token(response: Response) -> DemoAccessTokenResponse:
        response.headers["Cache-Control"] = "no-store"
        return DemoAccessTokenResponse(
            access_token=identity.issue_access_token(),
            expires_in_seconds=15 * 60,
            organization_id=DEMO_ORGANIZATION_ID,
            project_id=DEMO_PROJECT_ID,
            group=DEMO_GROUP,
        )

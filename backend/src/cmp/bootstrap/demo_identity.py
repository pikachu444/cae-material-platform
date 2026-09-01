"""Explicit, local-only identity composition for the runnable product demo.

The demo issuer remains a signed JWT issuer and is verified by the same request
security boundary as an operator-configured OIDC issuer.  It is intentionally
unavailable unless both ``CMP_ENVIRONMENT=demo`` and ``CMP_DEMO_IDENTITY=true``
are set; this module never supplies a production authentication fallback.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Final, Literal
from uuid import UUID

from fastapi import FastAPI, Response
from pydantic import BaseModel, ConfigDict, Field

from cmp.bootstrap.settings import Settings
from cmp.modules.identity_access.adapters.development.test_idp import DevelopmentTestIdp

DEMO_ORGANIZATION_ID: Final = UUID("d0000000-0000-4000-8000-000000000001")
DEMO_PROJECT_ID: Final = UUID("d0000000-0000-4000-8000-000000000002")
DEMO_GROUP: Final = "cmp-demo-material-team"
DEMO_SUBJECT: Final = "cmp-demo-administrator"
DEMO_USER_GROUP: Final = "cmp-demo-user-team"
DEMO_USER_SUBJECT: Final = "cmp-demo-user"
DEMO_REVIEWER_GROUP: Final = "cmp-demo-reviewer-team"
DEMO_REVIEWER_SUBJECT: Final = "cmp-demo-reviewer"
DEMO_PLAN_AUTHOR_SUBJECT: Final = "cmp-demo-plan-author"
DEMO_WORKER_CLIENT_ID: Final = "cmp-demo-worker"
# The local worker is an operator-provisioned runner, not an arbitrary caller.  Keep
# its durable identity separate from the service-principal identity so restarts reuse
# the same runner row and lease/fencing history.
DEMO_WORKER_RUNNER_ID: Final = UUID("d0000000-0000-4000-8000-000000000005")
DemoPersona = Literal["administrator", "user", "reviewer", "plan_author"]


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

    def issue_access_token(self, persona: DemoPersona = "administrator") -> str:
        """Issue a deliberately short-lived browser token for one demo persona.

        These personas are intentionally local-only fixtures.  The default remains
        the historical Administrator token so existing seed scripts keep their
        deterministic behavior; ``user`` and ``reviewer`` are explicit additional
        personas used by the review/publication browser journey. ``plan_author`` has
        the reviewer grant but a distinct principal so a governed Plan can be authored
        and approved without violating separation of duties.
        """

        if persona == "plan_author":
            subject = DEMO_PLAN_AUTHOR_SUBJECT
            display_name = "CMP local demo Plan author"
            # Governed Plan authoring requires both calibration execution and the
            # domain-reviewer role. Reuse the two explicit demo groups instead of
            # manufacturing a production authorization shortcut.
            groups = (DEMO_GROUP, DEMO_REVIEWER_GROUP)
        elif persona == "reviewer":
            subject = DEMO_REVIEWER_SUBJECT
            display_name = "CMP local demo reviewer"
            groups = (DEMO_REVIEWER_GROUP,)
        elif persona == "user":
            subject = DEMO_USER_SUBJECT
            display_name = "CMP local demo user"
            groups = (DEMO_USER_GROUP,)
        elif persona == "administrator":
            subject = DEMO_SUBJECT
            display_name = "CMP local demo administrator"
            groups = (DEMO_GROUP,)
        else:  # pragma: no cover - Literal callers and the HTTP query constrain this.
            raise ValueError(f"unsupported demo persona: {persona}")
        return self.idp.issue_user_token(
            subject=subject,
            organization_id=DEMO_ORGANIZATION_ID,
            project_id=DEMO_PROJECT_ID,
            display_name=display_name,
            groups=groups,
            scopes=("openid", "profile"),
            lifetime=timedelta(minutes=15),
        )

    def issue_worker_access_token(self) -> str:
        """Issue the explicit service-principal token used by the local worker.

        The worker must not reuse the administrator's user token: its operational
        ``job_runner`` grant is bound to this fixed service identity only.
        """

        return self.idp.issue_service_token(
            client_id=DEMO_WORKER_CLIENT_ID,
            organization_id=DEMO_ORGANIZATION_ID,
            project_id=DEMO_PROJECT_ID,
            lifetime=timedelta(minutes=5),
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
    persona: DemoPersona


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
    def issue_local_demo_access_token(
        response: Response,
        persona: DemoPersona = "administrator",
    ) -> DemoAccessTokenResponse:
        response.headers["Cache-Control"] = "no-store"
        group = {
            "administrator": DEMO_GROUP,
            "user": DEMO_USER_GROUP,
            "reviewer": DEMO_REVIEWER_GROUP,
            "plan_author": DEMO_REVIEWER_GROUP,
        }[persona]
        return DemoAccessTokenResponse(
            access_token=identity.issue_access_token(persona),
            expires_in_seconds=15 * 60,
            organization_id=DEMO_ORGANIZATION_ID,
            project_id=DEMO_PROJECT_ID,
            group=group,
            persona=persona,
        )

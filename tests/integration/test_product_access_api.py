from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4, uuid5

import httpx
from cmp.apps.api import create_app
from cmp.bootstrap.settings import Settings
from cmp.modules.identity_access.adapters.development.test_idp import DevelopmentTestIdp
from cmp.modules.identity_access.adapters.oidc.pyjwt import (
    OidcAccessTokenConfig,
    PyJwtAccessTokenVerifier,
)
from cmp.modules.identity_access.application.authorization import (
    AuthorizationService,
    ProductAccessAdministrationService,
)
from cmp.modules.identity_access.application.security import SecurityContextService
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    BindingSubject,
    DataClassification,
    FeatureGrant,
    ProductAccessAssignment,
    ProductRole,
    Role,
    RoleBinding,
)
from cmp.modules.identity_access.domain.security import (
    Principal,
    SecurityContext,
    VerifiedAccessToken,
)
from fastapi import FastAPI

ORG = UUID("84000000-0000-4000-8000-000000000001")
PROJECT = UUID("84000000-0000-4000-8000-000000000002")
NAMESPACE = UUID("84000000-0000-4000-8000-000000000003")
NOW = datetime(2026, 9, 9, 9, 0, tzinfo=UTC)


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


class _Bindings:
    def __init__(self, *bindings: RoleBinding) -> None:
        self.bindings = bindings

    def find_applicable(
        self, context: SecurityContext, observed_at: datetime
    ) -> tuple[RoleBinding, ...]:
        del context, observed_at
        return self.bindings


class _Assignments:
    def __init__(self) -> None:
        self.items: list[ProductAccessAssignment] = []

    def find_applicable(
        self, context: SecurityContext, observed_at: datetime
    ) -> tuple[ProductAccessAssignment, ...]:
        del context, observed_at
        return tuple(self.items)

    def list_assignments(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
    ) -> tuple[ProductAccessAssignment, ...]:
        del context, decision
        return tuple(self.items)

    def append_assignment(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        assignment: ProductAccessAssignment,
        created_at: datetime,
        grant_reason: str,
    ) -> ProductAccessAssignment:
        del context, decision, created_at, grant_reason
        self.items.append(assignment)
        return assignment

    def revoke_assignment(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        assignment_id: UUID,
        revoked_at: datetime,
        reason: str,
    ) -> None:
        del context, decision, reason
        self.items = [
            ProductAccessAssignment(
                id=item.id,
                organization_id=item.organization_id,
                project_id=item.project_id,
                subject=item.subject,
                product_role=item.product_role,
                feature_grants=item.feature_grants,
                max_classification=item.max_classification,
                allow_export_controlled=item.allow_export_controlled,
                valid_from=item.valid_from,
                expires_at=item.expires_at,
                revoked_at=revoked_at if item.id == assignment_id else item.revoked_at,
            )
            for item in self.items
        ]


def _security(idp: DevelopmentTestIdp) -> SecurityContextService:
    return SecurityContextService(
        verifier=PyJwtAccessTokenVerifier(
            config=OidcAccessTokenConfig(
                issuer=idp.issuer,
                audience=idp.audience,
                clock_skew_seconds=0,
            ),
            signing_keys=idp.signing_key_resolver(),
        ),
        principals=_Principals(),
    )


def _request(
    app: FastAPI,
    token: str,
    method: str,
    path: str,
    payload: dict[str, object] | None = None,
) -> httpx.Response:
    async def send() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.request(
                method,
                path,
                headers={"Authorization": f"Bearer {token}"},
                json=payload,
            )

    return asyncio.run(send())


def test_administrator_assigns_task_presets_and_reviewer_receives_review_access() -> None:
    idp = DevelopmentTestIdp()
    assignments = _Assignments()
    admin_binding = RoleBinding(
        id=uuid4(),
        organization_id=ORG,
        project_id=PROJECT,
        subject=BindingSubject.for_group(idp.issuer, "administrators"),
        role=Role.ORG_ADMIN,
        max_classification=DataClassification.RESTRICTED,
        allow_export_controlled=False,
        valid_from=NOW - timedelta(days=1),
    )
    authorization = AuthorizationService(
        bindings=_Bindings(admin_binding),
        product_assignments=assignments,
        clock=lambda: NOW,
    )
    access = ProductAccessAdministrationService(
        authorization=authorization,
        repository=assignments,
        clock=lambda: NOW,
    )
    app = create_app(
        Settings(environment="test"),
        _security(idp),
        authorization,
        product_access_service=access,
    )
    admin_token = idp.issue_user_token(
        subject="admin",
        organization_id=ORG,
        project_id=PROJECT,
        display_name="Administrator",
        groups=("administrators",),
    )

    admin_summary = _request(app, admin_token, "GET", "/api/v1/product-access/me")
    created = _request(
        app,
        admin_token,
        "POST",
        "/api/v1/product-access/assignments",
        {
            "subject_type": "group",
            "group_issuer": idp.issuer,
            "group_name": "modelers",
            "product_role": "user",
            "feature_grants": ["catalog_edit"],
            "max_classification": "confidential",
            "allow_export_controlled": False,
            "organization_wide": False,
            "grant_reason": "Assign the modeling workbench capability.",
        },
    )
    modeler_token = idp.issue_user_token(
        subject="modeler",
        organization_id=ORG,
        project_id=PROJECT,
        display_name="Modeler",
        groups=("modelers",),
    )
    user_summary = _request(app, modeler_token, "GET", "/api/v1/product-access/me")
    reviewer_created = _request(
        app,
        admin_token,
        "POST",
        "/api/v1/product-access/assignments",
        {
            "subject_type": "group",
            "group_issuer": idp.issuer,
            "group_name": "reviewers",
            "product_role": "reviewer",
            "feature_grants": [],
            "max_classification": "confidential",
            "allow_export_controlled": False,
            "organization_wide": False,
            "grant_reason": "Assign review and publication work.",
        },
    )
    reviewer_token = idp.issue_user_token(
        subject="reviewer", organization_id=ORG, project_id=PROJECT,
        display_name="Reviewer", groups=("reviewers",),
    )
    reviewer_summary = _request(app, reviewer_token, "GET", "/api/v1/product-access/me")

    assert admin_summary.status_code == 200
    assert admin_summary.json()["product_role"] == ProductRole.ADMINISTRATOR
    assert set(admin_summary.json()["feature_grants"]) == {
        grant.value for grant in FeatureGrant
    }
    assert created.status_code == 201
    assert created.json()["feature_grants"] == ["processing_calibration", "solver_card_export"]
    assert user_summary.status_code == 200
    assert user_summary.json() == {
        "product_role": "user",
        "feature_grants": ["processing_calibration", "solver_card_export"],
        "legacy_compatible": False,
    }
    assert reviewer_created.status_code == 201
    assert reviewer_created.json()["feature_grants"] == [
        "model_approval", "processing_calibration", "solver_card_export"
    ]
    assert reviewer_summary.json()["product_role"] == "reviewer"


def test_user_without_identity_management_cannot_list_or_create_assignments() -> None:
    idp = DevelopmentTestIdp()
    assignments = _Assignments()
    authorization = AuthorizationService(
        bindings=_Bindings(),
        product_assignments=assignments,
        clock=lambda: NOW,
    )
    app = create_app(
        Settings(environment="test"),
        _security(idp),
        authorization,
        product_access_service=ProductAccessAdministrationService(
            authorization=authorization,
            repository=assignments,
            clock=lambda: NOW,
        ),
    )
    token = idp.issue_user_token(
        subject="plain-user",
        organization_id=ORG,
        project_id=PROJECT,
        display_name="Plain User",
    )

    response = _request(app, token, "GET", "/api/v1/product-access/assignments")

    assert response.status_code == 403
    assert response.json()["code"] == "CMP-AUTHZ-0001"

"""Compose T-03/T-04 identity adapters only from explicit operator configuration."""

from __future__ import annotations

from dataclasses import dataclass

import sqlalchemy as sa
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from cmp.bootstrap.settings import Settings
from cmp.modules.identity_access.adapters.development.test_idp import DevelopmentTestIdp
from cmp.modules.identity_access.adapters.oidc.pyjwt import (
    OidcAccessTokenConfig,
    PyJwkClientSigningKeyResolver,
    PyJwtAccessTokenVerifier,
)
from cmp.modules.identity_access.adapters.persistence.principals import (
    SqlAlchemyPrincipalRepository,
)
from cmp.modules.identity_access.adapters.persistence.product_access import (
    SqlAlchemyProductAccessRepository,
)
from cmp.modules.identity_access.adapters.persistence.rls import SqlAlchemyRlsContext
from cmp.modules.identity_access.adapters.persistence.role_bindings import (
    SqlAlchemyRoleBindingRepository,
)
from cmp.modules.identity_access.application.authorization import (
    AuthorizationService,
    ProductAccessAdministrationService,
)
from cmp.modules.identity_access.application.security import SecurityContextService


@dataclass(frozen=True, slots=True)
class IdentityServices:
    security: SecurityContextService | None
    authorization: AuthorizationService | None
    rls_context: SqlAlchemyRlsContext | None
    engine: Engine | None
    product_access: ProductAccessAdministrationService | None = None


def build_identity_services(settings: Settings) -> IdentityServices:
    oidc_values = (settings.oidc_issuer, settings.oidc_audience, settings.oidc_jwks_url)
    if all(value is None for value in oidc_values):
        return IdentityServices(None, None, None, None)
    if any(value is None for value in oidc_values):
        raise ValueError(
            "CMP_OIDC_ISSUER, CMP_OIDC_AUDIENCE, and CMP_OIDC_JWKS_URL are all required"
        )
    if not settings.database_url:
        raise ValueError("CMP_DATABASE_URL is required when OIDC authentication is configured")
    issuer, audience, jwks_url = oidc_values
    assert issuer is not None and audience is not None and jwks_url is not None
    config = OidcAccessTokenConfig(
        issuer=issuer,
        audience=audience,
        algorithms=settings.oidc_algorithms,
        clock_skew_seconds=settings.oidc_clock_skew_seconds,
        client_id_claim=settings.oidc_client_id_claim,
        organization_claim=settings.oidc_organization_claim,
        project_claim=settings.oidc_project_claim,
        groups_claim=settings.oidc_groups_claim,
        display_name_claim=settings.oidc_display_name_claim,
        service_grant_claim=settings.oidc_service_grant_claim,
        service_grant_values=settings.oidc_service_grant_values,
    )
    keys = PyJwkClientSigningKeyResolver(
        jwks_url,
        allow_loopback_http=settings.oidc_allow_loopback_http,
    )
    verifier = PyJwtAccessTokenVerifier(config=config, signing_keys=keys)
    return _build_persisted_identity_services(
        settings,
        verifier=verifier,
        auto_provision=settings.oidc_auto_provision,
    )


def build_demo_identity_services(
    settings: Settings, identity: DevelopmentTestIdp
) -> IdentityServices:
    """Compose local demo JWT verification without weakening normal OIDC behavior."""

    if settings.environment != "demo" or not settings.demo_identity:
        raise ValueError("demo identity services require explicit demo environment configuration")
    if not settings.database_url:
        raise ValueError("CMP_DATABASE_URL is required when demo identity is configured")
    verifier = PyJwtAccessTokenVerifier(
        config=OidcAccessTokenConfig(
            issuer=identity.issuer,
            audience=identity.audience,
            algorithms=("RS256",),
            clock_skew_seconds=settings.oidc_clock_skew_seconds,
            client_id_claim=settings.oidc_client_id_claim,
            organization_claim=settings.oidc_organization_claim,
            project_claim=settings.oidc_project_claim,
            groups_claim=settings.oidc_groups_claim,
            display_name_claim=settings.oidc_display_name_claim,
            service_grant_claim=settings.oidc_service_grant_claim,
            service_grant_values=settings.oidc_service_grant_values,
        ),
        signing_keys=identity.signing_key_resolver(),
    )
    return _build_persisted_identity_services(
        settings,
        verifier=verifier,
        auto_provision=True,
    )


def _build_persisted_identity_services(
    settings: Settings,
    *,
    verifier: PyJwtAccessTokenVerifier,
    auto_provision: bool,
) -> IdentityServices:
    """Create the shared persistence/RLS boundary after a verifier was selected."""

    if not settings.database_url:
        raise ValueError("CMP_DATABASE_URL is required when OIDC authentication is configured")
    engine = sa.create_engine(settings.database_url, pool_pre_ping=True)
    sessions = sessionmaker(engine, class_=Session, expire_on_commit=False)
    principals = SqlAlchemyPrincipalRepository(
        session_factory=sessions,
        auto_provision=auto_provision,
    )
    rls_context = SqlAlchemyRlsContext()
    try:
        with sessions() as session, session.begin():
            rls_context.assert_application_role(session)
    except Exception:
        engine.dispose()
        raise
    bindings = SqlAlchemyRoleBindingRepository(
        session_factory=sessions,
        rls_context=rls_context,
    )
    product_assignments = SqlAlchemyProductAccessRepository(
        session_factory=sessions,
        rls_context=rls_context,
    )
    authorization = AuthorizationService(
        bindings=bindings,
        product_assignments=product_assignments,
    )
    return IdentityServices(
        security=SecurityContextService(verifier=verifier, principals=principals),
        authorization=authorization,
        rls_context=rls_context,
        engine=engine,
        product_access=ProductAccessAdministrationService(
            authorization=authorization,
            repository=product_assignments,
        ),
    )

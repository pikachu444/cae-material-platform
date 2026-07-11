from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from cmp.bootstrap.security import build_security_service
from cmp.bootstrap.settings import Settings
from cmp.modules.identity_access.adapters.development.test_idp import DevelopmentTestIdp
from cmp.modules.identity_access.adapters.oidc.pyjwt import (
    OidcAccessTokenConfig,
    PyJwkClientSigningKeyResolver,
    PyJwtAccessTokenVerifier,
)
from cmp.modules.identity_access.application.security import SecurityContextService
from cmp.modules.identity_access.domain.security import (
    AccessDenied,
    AuthenticationFailed,
    AuthenticationRequest,
    Principal,
    PrincipalType,
    VerifiedAccessToken,
)

ORG = UUID("30000000-0000-4000-8000-000000000001")
PROJECT = UUID("30000000-0000-4000-8000-000000000002")
PRINCIPAL = UUID("30000000-0000-4000-8000-000000000003")
REQUEST = UUID("30000000-0000-4000-8000-000000000004")
TRACE = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"


@pytest.fixture(scope="module")
def idp() -> DevelopmentTestIdp:
    return DevelopmentTestIdp()


def _verifier(idp: DevelopmentTestIdp) -> PyJwtAccessTokenVerifier:
    return PyJwtAccessTokenVerifier(
        config=OidcAccessTokenConfig(
            issuer=idp.issuer,
            audience=idp.audience,
            clock_skew_seconds=0,
        ),
        signing_keys=idp.signing_key_resolver(),
    )


class _PrincipalRepository:
    def __init__(self, *, active: bool = True) -> None:
        self.active = active
        self.last_token: VerifiedAccessToken | None = None

    def resolve_or_provision(
        self, token: VerifiedAccessToken, observed_at: datetime
    ) -> Principal:
        assert observed_at.tzinfo is not None
        self.last_token = token
        return Principal(PRINCIPAL, token.principal_type, token.display_name, self.active)


def test_user_access_token_maps_required_tenant_groups_and_scopes(
    idp: DevelopmentTestIdp,
) -> None:
    token = idp.issue_user_token(
        subject="synthetic-user-1",
        organization_id=ORG,
        project_id=PROJECT,
        display_name="Synthetic User",
        groups=("test-engineers", "data-stewards", "test-engineers"),
        scopes=("profile", "openid"),
    )

    verified = _verifier(idp).verify(token)

    assert verified.principal_type is PrincipalType.USER
    assert verified.organization_id == ORG
    assert verified.project_id == PROJECT
    assert verified.groups == ("data-stewards", "test-engineers")
    assert verified.scopes == ("openid", "profile")


def test_client_credentials_token_maps_to_service_principal(
    idp: DevelopmentTestIdp,
) -> None:
    token = idp.issue_service_token(
        client_id="synthetic-worker",
        organization_id=ORG,
        project_id=PROJECT,
        scopes=("jobs:submit",),
    )

    verified = _verifier(idp).verify(token)

    assert verified.principal_type is PrincipalType.SERVICE
    assert verified.subject == "synthetic-worker"
    assert verified.display_name == "synthetic-worker"


def test_client_credentials_subject_must_equal_client_id(
    idp: DevelopmentTestIdp,
) -> None:
    token = idp.issue_service_token(
        client_id="synthetic-worker",
        organization_id=ORG,
        project_id=PROJECT,
        overrides={"sub": "different-subject"},
    )

    with pytest.raises(AuthenticationFailed) as raised:
        _verifier(idp).verify(token)

    assert raised.value.code == "service_subject_mismatch"


@pytest.mark.parametrize(
    ("case", "expected_code"),
    [
        ("id-token-type", "invalid_token_type"),
        ("wrong-issuer", "invalid_issuer"),
        ("wrong-audience", "invalid_audience"),
        ("expired", "token_expired"),
        ("missing-project", "invalid_claims"),
    ],
)
def test_invalid_and_confused_tokens_are_rejected(
    idp: DevelopmentTestIdp, case: str, expected_code: str
) -> None:
    now = datetime.now(UTC)
    options: dict[str, object] = {}
    if case == "id-token-type":
        options["token_type"] = "JWT"
    elif case == "wrong-issuer":
        options["issuer"] = "https://attacker.invalid"
    elif case == "wrong-audience":
        options["audience"] = "urn:attacker-api"
    elif case == "expired":
        options["now"] = now - timedelta(minutes=10)
        options["lifetime"] = timedelta(minutes=1)
    elif case == "missing-project":
        options["drop_claims"] = ("project_id",)
    token = idp.issue_user_token(
        subject="synthetic-user-2",
        organization_id=ORG,
        project_id=PROJECT,
        display_name="Synthetic User",
        **options,  # type: ignore[arg-type]
    )

    with pytest.raises(AuthenticationFailed) as raised:
        _verifier(idp).verify(token)

    assert raised.value.code == expected_code
    assert token not in str(raised.value)


def test_symmetric_or_none_algorithm_cannot_enter_allowlist() -> None:
    with pytest.raises(ValueError, match="asymmetric"):
        OidcAccessTokenConfig(
            issuer="https://test-idp.invalid",
            audience="urn:cmp:test-api",
            algorithms=("HS256",),
        )


def test_claim_names_and_service_mapping_are_operator_configurable(
    idp: DevelopmentTestIdp,
) -> None:
    token = idp.issue_service_token(
        client_id="custom-worker",
        organization_id=ORG,
        project_id=PROJECT,
        overrides={
            "azp": "custom-worker",
            "org_context": str(ORG),
            "project_context": str(PROJECT),
            "roles": ["workers"],
            "display": "Custom Worker",
            "grant": "workload",
        },
        drop_claims=(
            "client_id",
            "organization_id",
            "project_id",
            "groups",
            "preferred_username",
            "gty",
        ),
    )
    verifier = PyJwtAccessTokenVerifier(
        config=OidcAccessTokenConfig(
            issuer=idp.issuer,
            audience=idp.audience,
            clock_skew_seconds=0,
            client_id_claim="azp",
            organization_claim="org_context",
            project_claim="project_context",
            groups_claim="roles",
            display_name_claim="display",
            service_grant_claim="grant",
            service_grant_values=("workload",),
        ),
        signing_keys=idp.signing_key_resolver(),
    )

    verified = verifier.verify(token)

    assert verified.principal_type is PrincipalType.SERVICE
    assert verified.display_name == "Custom Worker"
    assert verified.groups == ("workers",)


def test_oidc_configuration_rejects_ambiguous_tenant_claims_and_insecure_jwks() -> None:
    with pytest.raises(ValueError, match="must be distinct"):
        OidcAccessTokenConfig(
            issuer="https://test-idp.invalid",
            audience="urn:cmp:test-api",
            organization_claim="tenant",
            project_claim="tenant",
        )
    with pytest.raises(ValueError, match="HTTPS"):
        PyJwkClientSigningKeyResolver("http://idp.example.test/jwks")


def test_environment_settings_parse_claim_mapping_and_partial_oidc_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CMP_OIDC_CLIENT_ID_CLAIM", "azp")
    monkeypatch.setenv("CMP_OIDC_GROUPS_CLAIM", "roles")
    monkeypatch.setenv("CMP_OIDC_SERVICE_GRANT_VALUES", "client_credentials,workload")

    settings = Settings.from_environment()

    assert settings.oidc_client_id_claim == "azp"
    assert settings.oidc_groups_claim == "roles"
    assert settings.oidc_service_grant_values == ("client_credentials", "workload")
    with pytest.raises(ValueError, match="all required"):
        build_security_service(Settings(oidc_issuer="https://idp.example.test"))


def test_security_service_builds_request_context_only_after_principal_resolution(
    idp: DevelopmentTestIdp,
) -> None:
    now = datetime.now(UTC)
    principals = _PrincipalRepository()
    service = SecurityContextService(
        verifier=_verifier(idp),
        principals=principals,
        clock=lambda: now,
    )
    token = idp.issue_user_token(
        subject="synthetic-user-3",
        organization_id=ORG,
        project_id=PROJECT,
        display_name="Context User",
    )

    context = service.authenticate(AuthenticationRequest(token, REQUEST, TRACE))

    assert context.principal.id == PRINCIPAL
    assert context.organization_id == ORG
    assert context.project_id == PROJECT
    assert context.request_id == REQUEST
    assert context.trace_id == TRACE
    assert context.authenticated_at == now


def test_authentication_request_repr_never_contains_bearer_token() -> None:
    request = AuthenticationRequest("header.payload.signature", REQUEST, TRACE)

    assert "header.payload.signature" not in repr(request)


def test_inactive_principal_is_denied_even_with_valid_token(
    idp: DevelopmentTestIdp,
) -> None:
    service = SecurityContextService(
        verifier=_verifier(idp),
        principals=_PrincipalRepository(active=False),
    )
    token = idp.issue_user_token(
        subject="synthetic-user-4",
        organization_id=ORG,
        project_id=PROJECT,
        display_name="Inactive User",
    )

    with pytest.raises(AccessDenied, match="principal_inactive"):
        service.authenticate(AuthenticationRequest(token, REQUEST, TRACE))

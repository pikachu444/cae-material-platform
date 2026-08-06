from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid5

import httpx
from cmp.apps import api as api_bootstrap
from cmp.bootstrap.settings import Settings
from cmp.modules.identity_access.adapters.development.test_idp import DevelopmentTestIdp
from cmp.modules.identity_access.adapters.oidc.pyjwt import (
    OidcAccessTokenConfig,
    PyJwtAccessTokenVerifier,
)
from cmp.modules.identity_access.application.authorization import AuthorizationService
from cmp.modules.identity_access.application.security import SecurityContextService
from cmp.modules.identity_access.domain.authorization import (
    BindingSubject,
    DataClassification,
    Permission,
    Role,
    RoleBinding,
)
from cmp.modules.identity_access.domain.security import Principal, VerifiedAccessToken
from fastapi.routing import APIRoute

ORG = UUID("15800000-0000-4000-8000-000000000001")
PROJECT = UUID("15800000-0000-4000-8000-000000000002")
ACTOR = UUID("15800000-0000-4000-8000-000000000003")
NAMESPACE = UUID("15800000-0000-4000-8000-000000000004")


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
    def __init__(self, binding: RoleBinding) -> None:
        self._binding = binding

    def find_applicable(
        self, context: object, observed_at: datetime
    ) -> tuple[RoleBinding, ...]:
        del context, observed_at
        return (self._binding,)


class _FitRunSentinel:
    def __init__(self) -> None:
        self.list_calls = 0

    def list(self, context: object, decision: object) -> tuple[object, ...]:
        del context, decision
        self.list_calls += 1
        return ()


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


def _route(app: Any, path: str, method: str) -> APIRoute:
    for route in app.routes:
        if isinstance(route, APIRoute) and route.path == path:
            methods = route.methods
            if methods is not None and method in methods:
                return route
    raise AssertionError(f"route not found: {method} {path}")


def _request(app: Any, token: str) -> httpx.Response:
    async def send() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.get(
                "/api/v1/metal-fit-runs",
                headers={"Authorization": f"Bearer {token}"},
            )

    return asyncio.run(send())


def test_create_app_composes_metal_fit_store_without_changing_processing_dependencies(
    monkeypatch: Any,
) -> None:
    output_sentinel = object()
    fit_sentinel = _FitRunSentinel()
    builder_inputs: dict[str, object] = {}

    def build_outputs(*args: object) -> object:
        builder_inputs["output_args"] = args[-1]
        return output_sentinel

    def build_fit_runs(identity: object, outputs: object) -> object:
        builder_inputs["identity"] = identity
        builder_inputs["outputs"] = outputs
        return fit_sentinel

    monkeypatch.setattr(api_bootstrap, "build_common_processing_output_service", build_outputs)
    monkeypatch.setattr(api_bootstrap, "build_metal_fit_run_service", build_fit_runs)

    idp = DevelopmentTestIdp()
    binding = RoleBinding(
        id=UUID("15800000-0000-4000-8000-000000000005"),
        organization_id=ORG,
        project_id=PROJECT,
        subject=BindingSubject.for_group(idp.issuer, "fit-users"),
        role=Role.MATERIAL_MODELER,
        max_classification=DataClassification.INTERNAL,
        allow_export_controlled=False,
        valid_from=datetime.now(UTC) - timedelta(minutes=1),
    )
    authorization = AuthorizationService(bindings=_Bindings(binding))
    app = api_bootstrap.create_app(
        Settings(environment="test"),
        _security(idp),
        authorization,
    )

    assert builder_inputs["outputs"] is output_sentinel
    assert _route(app, "/api/v1/metal-fit-runs", "GET").dependant.dependencies
    assert [
        getattr(dependency.call, "permission", None)
        for dependency in _route(app, "/api/v1/metal-fit-runs", "GET").dependant.dependencies
        if dependency.call is not None
        and getattr(dependency.call, "permission", None) is not None
    ] == [Permission.PROCESSING_READ]
    assert [
        getattr(dependency.call, "permission", None)
        for dependency in _route(app, "/api/v1/metal-fit-runs", "POST").dependant.dependencies
        if dependency.call is not None
        and getattr(dependency.call, "permission", None) is not None
    ] == [Permission.PROCESSING_EXECUTE]

    token = idp.issue_user_token(
        subject="fit-user",
        organization_id=ORG,
        project_id=PROJECT,
        display_name="Fit User",
        groups=("fit-users",),
    )
    response = _request(app, token)
    assert response.status_code == 200, response.text
    assert response.json() == []
    assert fit_sentinel.list_calls == 1

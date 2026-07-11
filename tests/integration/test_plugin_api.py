from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast
from uuid import UUID, uuid5

import httpx
from cmp.apps.api import create_app
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
    Role,
    RoleBinding,
)
from cmp.modules.identity_access.domain.security import (
    Principal,
    SecurityContext,
    VerifiedAccessToken,
)
from cmp.modules.plugins.application.registry import PackageRegistrationResult
from cmp.modules.plugins.domain.registry import (
    ActivationRecord,
    ArtifactReference,
    ImmutablePluginManifest,
    PackageNotFound,
    PackageRecord,
    PackageState,
    PackageStateEventRecord,
    SchemaDocument,
    SchemaRole,
)
from cmp.shared.domain.revisions import content_sha256

PROJECT_ROOT = Path(__file__).parents[2]
ORG = UUID("86000000-0000-4000-8000-000000000001")
PROJECT = UUID("86000000-0000-4000-8000-000000000002")
REQUEST = UUID("86000000-0000-4000-8000-000000000003")
PACKAGE = UUID("86000000-0000-4000-8000-000000000004")
DEFINITION = UUID("86000000-0000-4000-8000-000000000005")
NAMESPACE = UUID("86000000-0000-4000-8000-000000000006")
NOW = datetime(2026, 7, 11, 9, 30, tzinfo=UTC)
TRACE = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"


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


def _manifest() -> dict[str, Any]:
    return cast(
        dict[str, Any],
        json.loads(
            (PROJECT_ROOT / "contracts/examples/positive/plugin-manifest.json").read_text(
                encoding="utf-8"
            )
        ),
    )


def _schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "urn:cmp:plugin:reference-processor:config:1.0.0",
        "type": "object",
    }


def _record(
    context: SecurityContext,
    state: PackageState,
    *,
    active: bool = False,
) -> PackageRecord:
    manifest = ImmutablePluginManifest.from_validated_document(_manifest())
    schema = _schema()
    events = [
        PackageStateEventRecord(
            UUID("86000000-0000-4000-8000-000000000007"),
            PACKAGE,
            1,
            None,
            PackageState.CONTRACT_VALIDATED,
            NOW,
            context.principal.id,
            "manifest and schemas contract validated",
            context.request_id,
            context.trace_id,
        )
    ]
    if state is not PackageState.CONTRACT_VALIDATED:
        target = PackageState.ELIGIBLE if active else state
        events.append(
            PackageStateEventRecord(
                UUID("86000000-0000-4000-8000-000000000008"),
                PACKAGE,
                2,
                PackageState.CONTRACT_VALIDATED,
                target,
                NOW,
                context.principal.id,
                "operator policy verification",
                context.request_id,
                context.trace_id,
            )
        )
    activation = None
    if active:
        activation = ActivationRecord(
            UUID("86000000-0000-4000-8000-000000000009"),
            PACKAGE,
            NOW,
            context.principal.id,
            "approved for project",
            context.request_id,
            context.trace_id,
        )
    return PackageRecord(
        PACKAGE,
        DEFINITION,
        ORG,
        PROJECT,
        DataClassification.INTERNAL,
        manifest,
        ArtifactReference(uuid5(NAMESPACE, "package"), "0" * 64, 1024, "application/zip"),
        ArtifactReference(uuid5(NAMESPACE, "signature"), "1" * 64, 256, "application/json"),
        ArtifactReference(uuid5(NAMESPACE, "sbom"), "2" * 64, 512, "application/spdx+json"),
        (
            SchemaDocument.from_validated_document(
                schema_id=str(schema["$id"]),
                extension_ordinal=1,
                role=SchemaRole.CONFIG,
                document=schema,
                expected_sha256=content_sha256(schema),
            ),
        ),
        PackageState.ELIGIBLE if active else state,
        tuple(events),
        NOW,
        context.principal.id,
        context.request_id,
        context.trace_id,
        activation,
    )


class _PluginService:
    def __init__(self) -> None:
        self.registrations = 0

    def register(
        self, context: SecurityContext, decision: object, command: object
    ) -> PackageRegistrationResult:
        del decision, command
        self.registrations += 1
        return PackageRegistrationResult(_record(context, PackageState.CONTRACT_VALIDATED), False)

    def get(
        self, context: SecurityContext, decision: object, package_id: UUID
    ) -> PackageRecord:
        del decision
        if package_id != PACKAGE:
            raise PackageNotFound(str(package_id))
        return _record(context, PackageState.CONTRACT_VALIDATED)

    def verify(
        self, context: SecurityContext, decision: object, command: object
    ) -> PackageRecord:
        del decision, command
        return _record(context, PackageState.ELIGIBLE)

    def activate(
        self, context: SecurityContext, decision: object, command: object
    ) -> PackageRecord:
        del decision, command
        return _record(context, PackageState.ELIGIBLE, active=True)

    def revoke(
        self, context: SecurityContext, decision: object, command: object
    ) -> PackageRecord:
        del decision, command
        return _record(context, PackageState.REVOKED)


def _application() -> tuple[object, DevelopmentTestIdp, _PluginService]:
    idp = DevelopmentTestIdp()
    valid_from = datetime.now(UTC) - timedelta(minutes=1)
    bindings = (
        RoleBinding(
            uuid5(NAMESPACE, "maintainer-binding"),
            ORG,
            PROJECT,
            BindingSubject.for_group(idp.issuer, "plugin-maintainers"),
            Role.PLUGIN_MAINTAINER,
            DataClassification.INTERNAL,
            False,
            valid_from,
        ),
        RoleBinding(
            uuid5(NAMESPACE, "admin-binding"),
            ORG,
            PROJECT,
            BindingSubject.for_group(idp.issuer, "plugin-admins"),
            Role.ORG_ADMIN,
            DataClassification.INTERNAL,
            False,
            valid_from,
        ),
    )
    plugins = _PluginService()
    application = create_app(
        Settings(environment="test"),
        _security(idp),
        AuthorizationService(bindings=_Bindings(*bindings)),
        None,
        cast(Any, plugins),
    )
    return application, idp, plugins


def _token(idp: DevelopmentTestIdp, group: str) -> str:
    return idp.issue_user_token(
        subject=group,
        organization_id=ORG,
        project_id=PROJECT,
        display_name=group,
        groups=(group,),
    )


def _request(
    application: object,
    token: str,
    method: str,
    path: str,
    *,
    body: object | None = None,
    extra_headers: dict[str, str] | None = None,
) -> httpx.Response:
    async def send() -> httpx.Response:
        transport = httpx.ASGITransport(app=cast(Any, application))
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Request-ID": str(REQUEST),
            "traceparent": TRACE,
            **(extra_headers or {}),
        }
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            return await client.request(method, path, json=body, headers=headers)

    return asyncio.run(send())


def _body() -> dict[str, Any]:
    schema = _schema()
    return {
        "classification": "internal",
        "manifest": _manifest(),
        "package_artifact": {
            "artifact_id": str(uuid5(NAMESPACE, "package")),
            "sha256": "0" * 64,
            "size_bytes": 1024,
            "media_type": "application/zip",
        },
        "signature_artifact": {
            "artifact_id": str(uuid5(NAMESPACE, "signature")),
            "sha256": "1" * 64,
            "size_bytes": 256,
            "media_type": "application/json",
        },
        "sbom_artifact": {
            "artifact_id": str(uuid5(NAMESPACE, "sbom")),
            "sha256": "2" * 64,
            "size_bytes": 512,
            "media_type": "application/spdx+json",
        },
        "schemas": [
            {
                "schema_id": schema["$id"],
                "extension_ordinal": 1,
                "role": "config",
                "document": schema,
                "sha256": content_sha256(schema),
            }
        ],
    }


def test_plugin_registration_api_returns_immutable_identity_and_provenance() -> None:
    application, idp, plugins = _application()
    response = _request(
        application,
        _token(idp, "plugin-maintainers"),
        "POST",
        "/api/v1/plugins/packages",
        body=_body(),
        extra_headers={"Idempotency-Key": "plugin-package-api-1"},
    )

    assert response.status_code == 201
    assert response.headers["location"] == f"/api/v1/plugins/packages/{PACKAGE}"
    assert response.headers["idempotent-replay"] == "false"
    document = response.json()
    assert document["package_id"] != document["definition_id"]
    assert document["package_digest"] == "sha256:" + "0" * 64
    assert document["schemas"][0]["sha256"] == content_sha256(_schema())
    assert document["state_history"][0]["to_state"] == "contract_validated"
    assert plugins.registrations == 1

    invalid = _request(
        application,
        _token(idp, "plugin-maintainers"),
        "POST",
        "/api/v1/plugins/packages",
        body={"classification": "internal"},
        extra_headers={"Idempotency-Key": "plugin-package-api-2"},
    )
    assert invalid.status_code == 422
    assert invalid.json()["code"] == "CMP-PLUGIN-0002"
    assert plugins.registrations == 1


def test_plugin_activation_requires_admin_and_missing_package_is_sanitized() -> None:
    application, idp, _ = _application()
    body = {"reason": "signature, SBOM, and policy evidence approved"}
    denied = _request(
        application,
        _token(idp, "plugin-maintainers"),
        "POST",
        f"/api/v1/plugins/packages/{PACKAGE}:activate",
        body=body,
    )
    assert denied.status_code == 403

    verified = _request(
        application,
        _token(idp, "plugin-admins"),
        "POST",
        f"/api/v1/plugins/packages/{PACKAGE}:verify",
        body=body,
    )
    assert verified.status_code == 200
    assert verified.json()["state"] == "eligible"

    activated = _request(
        application,
        _token(idp, "plugin-admins"),
        "POST",
        f"/api/v1/plugins/packages/{PACKAGE}:activate",
        body=body,
    )
    assert activated.status_code == 200
    assert activated.json()["active"] is True
    assert activated.json()["activation"]["activated_by"]

    missing = _request(
        application,
        _token(idp, "plugin-admins"),
        "GET",
        f"/api/v1/plugins/packages/{uuid5(NAMESPACE, 'missing')}",
    )
    assert missing.status_code == 404
    assert missing.json()["code"] == "CMP-PLUGIN-0001"
    assert "tenant" in missing.json()["detail"]

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
from uuid import UUID, uuid4

import httpx
from cmp.modules.catalog.adapters.api.schema_bundles import install_schema_bundle_planner_api
from cmp.modules.catalog.application.schema_bundles import SchemaBundleSourceConflict
from cmp.modules.catalog.domain.schema_bundles import (
    CatalogSnapshot,
    SchemaBundlePlan,
    SourceArtifactIdentity,
    build_schema_bundle_plan,
)
from cmp.modules.identity_access.application.authorization import database_permissions_for
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
    Permission,
    Role,
)
from cmp.modules.identity_access.domain.security import Principal, PrincipalType, SecurityContext
from fastapi import FastAPI, Request
from jsonschema import Draft202012Validator, FormatChecker

PROJECT_ROOT = Path(__file__).parents[2]
NOW = datetime(2026, 8, 11, 9, 0, tzinfo=UTC)
ORG = UUID("20400000-0000-4000-8000-000000000001")
PROJECT = UUID("20400000-0000-4000-8000-000000000002")
ACTOR = UUID("20400000-0000-4000-8000-000000000004")
ARTIFACT = UUID("20400000-0000-4000-8000-000000000005")


def _context() -> SecurityContext:
    return SecurityContext(
        principal=Principal(ACTOR, PrincipalType.USER, "Schema administrator", True),
        organization_id=ORG,
        project_id=PROJECT,
        issuer="https://test-idp.invalid",
        subject=str(ACTOR),
        token_id=str(uuid4()),
        groups=(),
        scopes=("openid",),
        request_id=uuid4(),
        trace_id="00-00000000000000000000000000000204-0000000000000204-01",
        authenticated_at=NOW,
    )


CONTEXT = _context()


def _decision() -> AuthorizationDecision:
    return AuthorizationDecision(
        principal_id=ACTOR,
        organization_id=ORG,
        project_id=PROJECT,
        permission=Permission.CATALOG_WRITE,
        roles=(Role.DATA_STEWARD,),
        database_permissions=database_permissions_for(Permission.CATALOG_WRITE),
        max_classification=DataClassification.INTERNAL,
        allow_export_controlled=False,
        request_id=CONTEXT.request_id,
        trace_id=CONTEXT.trace_id,
        decided_at=NOW,
    )


class _Planner:
    def __init__(self, raw: bytes) -> None:
        self.raw = raw
        self.digest = hashlib.sha256(raw).hexdigest()
        self.calls = 0

    async def plan(self, context: Any, decision: Any, command: Any) -> SchemaBundlePlan:
        assert context == CONTEXT
        assert decision.permission is Permission.CATALOG_WRITE
        assert command.artifact_id == ARTIFACT
        assert command.expected_sha256 == self.digest
        self.calls += 1
        return build_schema_bundle_plan(
            source=SourceArtifactIdentity(
                ARTIFACT,
                ORG,
                PROJECT,
                DataClassification.INTERNAL,
                "application/vnd.cmp.catalog-schema-definition-bundle+json",
                len(self.raw),
                self.digest,
            ),
            raw_bytes=self.raw,
            snapshot=CatalogSnapshot(ORG, PROJECT, ()),
            organization_id=ORG,
            project_id=PROJECT,
            classification_allowed=lambda _: True,
        )


class _ConflictingPlanner:
    async def plan(self, context: Any, decision: Any, command: Any) -> None:
        del context, decision, command
        raise SchemaBundleSourceConflict("exact digest mismatch")


def _app(service: object) -> FastAPI:
    application = FastAPI()

    def security(request: Request) -> None:
        request.state.security_context = CONTEXT

    def write(request: Request) -> None:
        request.state.authorization_decision = _decision()

    install_schema_bundle_planner_api(
        application,
        service=cast(Any, service),
        security_dependency=security,
        write_dependency=write,
    )
    return application


def _request(application: FastAPI, **kwargs: Any) -> httpx.Response:
    async def run() -> httpx.Response:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=application),
            base_url="http://test",
        ) as client:
            return await client.post(
                "/api/v1/catalog/schema-definition-bundles:plan",
                **kwargs,
            )

    import asyncio

    return asyncio.run(run())


def test_schema_bundle_plan_api_is_repeatable_and_reports_no_write_contract() -> None:
    raw = (
        PROJECT_ROOT / "contracts" / "examples" / "positive" / "schema-definition-bundle-many.json"
    ).read_bytes()
    planner = _Planner(raw)
    application = _app(planner)
    body = {"artifact_id": str(ARTIFACT), "artifact_sha256": planner.digest}

    first = _request(application, json=body)
    second = _request(application, json=body)

    assert first.status_code == 200
    assert first.content == second.content
    response = first.json()
    assert response["source_artifact"] == {
        "artifact_id": str(ARTIFACT),
        "organization_id": str(ORG),
        "project_id": str(PROJECT),
        "classification": "internal",
        "media_type": "application/vnd.cmp.catalog-schema-definition-bundle+json",
        "size_bytes": len(raw),
        "sha256": planner.digest,
    }
    assert response["bundle"]["record_schema_count"] == 3
    assert response["bundle"]["scope"] == {
        "organization_id": str(ORG),
        "project_id": str(PROJECT),
        "classification": "internal",
    }
    assert response["mutations_applied"] is False
    assert response["delete_missing"] is False
    assert response["write_set"] == []
    assert planner.calls == 2
    operation = application.openapi()["paths"]["/api/v1/catalog/schema-definition-bundles:plan"][
        "post"
    ]
    assert operation["operationId"] == "planCatalogSchemaDefinitionBundle"


def test_schema_bundle_plan_api_rejects_invalid_digest_shape_and_source_conflict() -> None:
    validation = _request(
        _app(_ConflictingPlanner()),
        json={"artifact_id": str(ARTIFACT), "artifact_sha256": "not-a-digest"},
    )
    conflict = _request(
        _app(_ConflictingPlanner()),
        json={"artifact_id": str(ARTIFACT), "artifact_sha256": "a" * 64},
    )

    assert validation.status_code == 422
    assert conflict.status_code == 409
    assert conflict.headers["content-type"].startswith("application/problem+json")
    assert conflict.json()["code"] == "CMP-CATALOG-0202"


def test_schema_bundle_plan_api_returns_repairable_semantic_errors_without_transport_failure() -> (
    None
):
    raw = (
        PROJECT_ROOT
        / "contracts"
        / "examples"
        / "negative"
        / "schema-definition-bundle-unsupported-version.json"
    ).read_bytes()
    planner = _Planner(raw)

    response = _request(
        _app(planner),
        json={"artifact_id": str(ARTIFACT), "artifact_sha256": planner.digest},
    )

    assert response.status_code == 200
    plan = response.json()
    assert plan["valid"] is False
    assert plan["action_counts"]["error"] == 1
    assert plan["actions"][0]["projected"] is None
    assert plan["diagnostics"][0]["code"] == "CMP-SCHEMA-BUNDLE-0003"
    assert plan["diagnostics"][0]["location"] == "/contract_version"
    assert plan["diagnostics"][0]["remediation"]
    assert plan["mutations_applied"] is False
    assert plan["write_set"] == []


def test_empty_verified_artifact_preserves_zero_byte_identity_in_repairable_plan() -> None:
    planner = _Planner(b"")

    response = _request(
        _app(planner),
        json={"artifact_id": str(ARTIFACT), "artifact_sha256": planner.digest},
    )

    assert response.status_code == 200
    plan = response.json()
    assert plan["valid"] is False
    assert plan["source_artifact"]["size_bytes"] == 0
    assert plan["source_artifact"]["sha256"] == hashlib.sha256(b"").hexdigest()
    assert plan["diagnostics"][0]["code"] == "CMP-SCHEMA-BUNDLE-0001"
    schema = json.loads(
        (PROJECT_ROOT / "contracts" / "catalog" / "schema-definition-plan.schema.json").read_text(
            encoding="utf-8"
        )
    )
    assert list(
        Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(plan)
    ) == []

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
from uuid import UUID, uuid4

import httpx
from cmp.modules.catalog.adapters.api.schema_bundles import install_schema_bundle_planner_api
from cmp.modules.catalog.application.schema_bundles import (
    AppliedSchemaObject,
    ExportedSchemaDefinitionBundle,
    SchemaBundleApplication,
    SchemaBundleSourceConflict,
    SchemaBundleStalePlan,
)
from cmp.modules.catalog.domain.schema_bundles import (
    CatalogSnapshot,
    PlanDisposition,
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


def _decision(permission: Permission = Permission.CATALOG_WRITE) -> AuthorizationDecision:
    return AuthorizationDecision(
        principal_id=ACTOR,
        organization_id=ORG,
        project_id=PROJECT,
        permission=permission,
        roles=(Role.DATA_STEWARD,),
        database_permissions=database_permissions_for(permission),
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


class _ApplyExportService(_Planner):
    def __init__(self, raw: bytes) -> None:
        super().__init__(raw)
        source = SourceArtifactIdentity(
            ARTIFACT,
            ORG,
            PROJECT,
            DataClassification.INTERNAL,
            "application/vnd.cmp.catalog-schema-definition-bundle+json",
            len(raw),
            self.digest,
        )
        self.application = SchemaBundleApplication(
            application_id=UUID("20700000-0000-4000-8000-000000000001"),
            bundle_id=UUID("20700000-0000-4000-8000-000000000002"),
            bundle_key="synthetic_dependency_chain",
            bundle_version="1.0.0",
            classification="internal",
            source_artifact=source,
            plan_fingerprint="b" * 64,
            before_snapshot_fingerprint="c" * 64,
            after_snapshot_fingerprint="d" * 64,
            results=(
                AppliedSchemaObject(
                    sequence=1,
                    disposition=PlanDisposition.CREATE,
                    target_type="database",
                    external_key="synthetic_engineering",
                    parent_external_key=None,
                    aggregate_id=UUID("20700000-0000-4000-8000-000000000003"),
                    revision_id=UUID("20700000-0000-4000-8000-000000000004"),
                    content_hash="e" * 64,
                    published=True,
                    source_schema_id="urn:cmp:catalog-schema-definition-bundle:1.0.0",
                    source_schema_version="1.0.0",
                    source_pointer="/catalog/database",
                ),
            ),
            mutations_applied=True,
            applied_at=NOW,
            applied_by=ACTOR,
            idempotency_key="issue-207-api-apply",
        )
        self.apply_calls = 0
        self.get_calls = 0
        self.export_calls = 0

    async def apply(self, context: Any, decision: Any, command: Any) -> SchemaBundleApplication:
        assert context == CONTEXT
        assert decision.permission is Permission.CATALOG_SCHEMA_APPLY
        assert command.artifact_id == ARTIFACT
        assert command.expected_sha256 == self.digest
        assert command.plan_fingerprint == "b" * 64
        assert command.delete_missing is False
        self.apply_calls += 1
        replayed = command.idempotency_key == "issue-207-api-replay"
        return replace(
            self.application,
            idempotency_key=command.idempotency_key,
            replayed=replayed,
        )

    def get_application(
        self, context: Any, decision: Any, application_id: UUID
    ) -> SchemaBundleApplication:
        assert context == CONTEXT
        assert decision.permission is Permission.CATALOG_SCHEMA_APPLY
        assert application_id == self.application.application_id
        self.get_calls += 1
        return self.application

    async def export(
        self, context: Any, decision: Any, bundle_key: str
    ) -> ExportedSchemaDefinitionBundle:
        assert context == CONTEXT
        assert decision.permission is Permission.CATALOG_SCHEMA_APPLY
        assert bundle_key == self.application.bundle_key
        self.export_calls += 1
        canonical = json.dumps(
            json.loads(self.raw), ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()
        return ExportedSchemaDefinitionBundle(
            value=canonical,
            sha256=hashlib.sha256(canonical).hexdigest(),
            application_id=self.application.application_id,
            bundle_key=self.application.bundle_key,
            bundle_version=self.application.bundle_version,
            source_artifact_id=ARTIFACT,
            source_artifact_sha256=self.digest,
        )


class _StaleApplyService(_ApplyExportService):
    async def apply(
        self, context: Any, decision: Any, command: Any
    ) -> SchemaBundleApplication:
        del context, decision, command
        raise SchemaBundleStalePlan("server re-plan differs")


def _app(service: object) -> FastAPI:
    application = FastAPI()

    def security(request: Request) -> None:
        request.state.security_context = CONTEXT

    def write(request: Request) -> None:
        request.state.authorization_decision = _decision()

    def apply(request: Request) -> None:
        request.state.authorization_decision = _decision(Permission.CATALOG_SCHEMA_APPLY)

    install_schema_bundle_planner_api(
        application,
        service=cast(Any, service),
        security_dependency=security,
        write_dependency=write,
        apply_dependency=apply,
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


def _http_request(
    application: FastAPI,
    method: str,
    path: str,
    **kwargs: Any,
) -> httpx.Response:
    async def run() -> httpx.Response:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=application),
            base_url="http://test",
        ) as client:
            return await client.request(method, path, **kwargs)

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
    assert (
        list(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(plan)) == []
    )


def test_schema_bundle_apply_read_back_and_export_use_server_owned_evidence() -> None:
    raw = (
        PROJECT_ROOT / "contracts" / "examples" / "positive" / "schema-definition-bundle-many.json"
    ).read_bytes()
    service = _ApplyExportService(raw)
    application = _app(service)
    body = {
        "artifact_id": str(ARTIFACT),
        "artifact_sha256": service.digest,
        "plan_fingerprint": "b" * 64,
        "delete_missing": False,
    }
    applied = _http_request(
        application,
        "POST",
        "/api/v1/catalog/schema-definition-bundles:apply",
        json=body,
        headers={"Idempotency-Key": "issue-207-api-apply"},
    )

    assert applied.status_code == 201
    assert applied.headers["idempotent-replay"] == "false"
    assert applied.headers["location"].endswith(str(service.application.application_id))
    assert applied.json()["plan_fingerprint"] == "b" * 64
    assert applied.json()["delete_missing"] is False
    assert applied.json()["results"][0]["published"] is True
    application_contract = json.loads(
        (
            PROJECT_ROOT
            / "contracts"
            / "catalog"
            / "schema-definition-bundle-application.schema.json"
        ).read_text(encoding="utf-8")
    )
    assert (
        list(
            Draft202012Validator(application_contract, format_checker=FormatChecker()).iter_errors(
                applied.json()
            )
        )
        == []
    )

    replay = _http_request(
        application,
        "POST",
        "/api/v1/catalog/schema-definition-bundles:apply",
        json=body,
        headers={"Idempotency-Key": "issue-207-api-replay"},
    )
    assert replay.status_code == 200
    assert replay.headers["idempotent-replay"] == "true"

    read_back = _http_request(application, "GET", applied.headers["location"])
    assert read_back.status_code == 200
    assert read_back.json() == service.application.canonical()

    exported = _http_request(
        application,
        "GET",
        "/api/v1/catalog/schema-definition-bundles/synthetic_dependency_chain:export",
    )
    assert exported.status_code == 200
    assert exported.headers["content-type"].startswith(
        "application/vnd.cmp.catalog-schema-definition-bundle+json"
    )
    assert exported.headers["x-cmp-source-artifact-id"] == str(ARTIFACT)
    assert exported.headers["x-cmp-source-artifact-sha256"] == service.digest
    assert exported.headers["etag"] == f'"sha256:{hashlib.sha256(exported.content).hexdigest()}"'
    assert json.loads(exported.content) == json.loads(raw)
    assert service.apply_calls == 2
    assert service.get_calls == 1
    assert service.export_calls == 1


def test_schema_bundle_apply_rejects_client_actions_and_maps_stale_fingerprint() -> None:
    raw = (
        PROJECT_ROOT / "contracts" / "examples" / "positive" / "schema-definition-bundle-many.json"
    ).read_bytes()
    application = _app(_StaleApplyService(raw))
    body = {
        "artifact_id": str(ARTIFACT),
        "artifact_sha256": hashlib.sha256(raw).hexdigest(),
        "plan_fingerprint": "b" * 64,
        "delete_missing": False,
    }
    untrusted_action = _http_request(
        application,
        "POST",
        "/api/v1/catalog/schema-definition-bundles:apply",
        json={**body, "actions": [{"disposition": "create"}]},
        headers={"Idempotency-Key": "issue-207-api-untrusted-action"},
    )
    stale = _http_request(
        application,
        "POST",
        "/api/v1/catalog/schema-definition-bundles:apply",
        json=body,
        headers={"Idempotency-Key": "issue-207-api-stale"},
    )

    assert untrusted_action.status_code == 422
    assert stale.status_code == 409
    assert stale.headers["content-type"].startswith("application/problem+json")
    assert stale.json()["code"] == "CMP-CATALOG-0207"
    operations = application.openapi()["paths"]
    assert (
        operations["/api/v1/catalog/schema-definition-bundles:apply"]["post"]["operationId"]
        == "applyCatalogSchemaDefinitionBundle"
    )
    assert (
        operations["/api/v1/catalog/schema-definition-bundle-applications/{application_id}"]["get"][
            "operationId"
        ]
        == "getCatalogSchemaDefinitionBundleApplication"
    )
    assert (
        operations["/api/v1/catalog/schema-definition-bundles/{bundle_key}:export"]["get"][
            "operationId"
        ]
        == "exportCatalogSchemaDefinitionBundle"
    )

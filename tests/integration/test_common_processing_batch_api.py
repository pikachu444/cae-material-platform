from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID, uuid4

import httpx
from cmp.modules.identity_access.application.authorization import database_permissions_for
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
    Permission,
    Role,
)
from cmp.modules.identity_access.domain.security import Principal, PrincipalType, SecurityContext
from cmp.modules.processing.adapters.api.common_batches import install_common_batch_api
from cmp.modules.processing.application.common_batches import (
    BatchPreflight,
    BatchPreflightMember,
    BatchSourceInput,
    CommonBatchService,
)
from cmp.modules.processing.domain.common_batches import (
    BatchAttempt,
    BatchAttemptStatus,
    BatchMemberPlan,
    BatchRevisionPin,
    CommonProcessingBatch,
)
from cmp.shared.domain.revisions import TenantScope
from fastapi import FastAPI, Request

NOW = datetime(2026, 7, 18, 21, 0, tzinfo=UTC)
ORG = UUID("d5420000-0000-4000-8000-000000000001")
PROJECT = UUID("d5420000-0000-4000-8000-000000000002")
ACTOR = UUID("d5420000-0000-4000-8000-000000000003")
RECIPE = UUID("d5420000-0000-4000-8000-000000000004")
RECIPE_REVISION = UUID("d5420000-0000-4000-8000-000000000005")
DOCUMENT = UUID("d5420000-0000-4000-8000-000000000006")
DOCUMENT_REVISION = UUID("d5420000-0000-4000-8000-000000000007")
BATCH = UUID("d5420000-0000-4000-8000-000000000008")
MEMBER = UUID("d5420000-0000-4000-8000-000000000009")


CONTEXT = SecurityContext(
    principal=Principal(ACTOR, PrincipalType.USER, "Modeler", True),
    organization_id=ORG,
    project_id=PROJECT,
    issuer="urn:cmp:test",
    subject=str(ACTOR),
    token_id=str(uuid4()),
    groups=(),
    scopes=("openid",),
    request_id=uuid4(),
    trace_id="00-0000000000000000000000000000d542-000000000000d542-01",
    authenticated_at=NOW,
)


def _decision(permission: Permission) -> AuthorizationDecision:
    return AuthorizationDecision(
        principal_id=ACTOR,
        organization_id=ORG,
        project_id=PROJECT,
        permission=permission,
        roles=(Role.MATERIAL_MODELER,),
        database_permissions=database_permissions_for(permission),
        max_classification=DataClassification.INTERNAL,
        allow_export_controlled=False,
        request_id=CONTEXT.request_id,
        trace_id=CONTEXT.trace_id,
        decided_at=NOW,
    )


def _batch() -> CommonProcessingBatch:
    output = BatchRevisionPin(uuid4(), uuid4())
    return CommonProcessingBatch(
        batch_id=BATCH,
        scope=TenantScope(ORG, PROJECT, "internal"),
        label="DP600 batch",
        recipe=BatchRevisionPin(RECIPE, RECIPE_REVISION),
        recipe_sha256="a" * 64,
        members=(
            BatchMemberPlan(
                MEMBER,
                0,
                BatchRevisionPin(DOCUMENT, DOCUMENT_REVISION),
                "b" * 64,
            ),
        ),
        attempts=(
            BatchAttempt(
                uuid4(),
                MEMBER,
                1,
                BatchAttemptStatus.SUCCEEDED,
                output,
                None,
                None,
                NOW,
                NOW,
            ),
        ),
        created_at=NOW,
        created_by=ACTOR,
        request_id=CONTEXT.request_id,
        trace_id=CONTEXT.trace_id,
    )


class _Service:
    async def preflight(self, *_: Any) -> BatchPreflight:
        source = BatchSourceInput(DOCUMENT, DOCUMENT_REVISION)
        return BatchPreflight(
            RECIPE,
            RECIPE_REVISION,
            "a" * 64,
            (BatchPreflightMember(0, source, True, "b" * 64, 21, None),),
        )

    async def execute(self, *_: Any) -> CommonProcessingBatch:
        return _batch()

    async def retry_failed(self, *_: Any) -> CommonProcessingBatch:
        return _batch()

    def list_batches(self, *_: Any) -> tuple[CommonProcessingBatch, ...]:
        return (_batch(),)

    def get_batch(self, *_: Any) -> CommonProcessingBatch:
        return _batch()


def _app() -> FastAPI:
    app = FastAPI()

    def security(request: Request) -> object:
        request.state.security_context = CONTEXT
        return CONTEXT

    def read(request: Request) -> object:
        decision = _decision(Permission.PROCESSING_READ)
        request.state.authorization_decision = decision
        return decision

    def execute(request: Request) -> object:
        decision = _decision(Permission.PROCESSING_EXECUTE)
        request.state.authorization_decision = decision
        return decision

    install_common_batch_api(
        app,
        service=cast(CommonBatchService, _Service()),
        security_dependency=security,
        read_dependency=read,
        execute_dependency=execute,
    )
    return app


def test_batch_preflight_execute_and_monitor_contracts() -> None:
    async def scenario() -> None:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=_app()), base_url="http://test"
        ) as client:
            body = {
                "classification": "internal",
                "recipe_id": str(RECIPE),
                "recipe_revision_id": str(RECIPE_REVISION),
                "sources": [
                    {"document_id": str(DOCUMENT), "revision_id": str(DOCUMENT_REVISION)}
                ],
            }
            preflight = await client.post(
                "/api/v1/common-processing-batches:preflight", json=body
            )
            assert preflight.status_code == 200
            assert preflight.json()["compatible"] is True
            assert preflight.json()["members"][0]["final_point_count"] == 21

            executed = await client.post(
                "/api/v1/common-processing-batches",
                json={
                    **body,
                    "label": "DP600 batch",
                    "change_reason": "execute exact published recipe",
                },
            )
            assert executed.status_code == 201
            assert executed.json()["status"] == "succeeded"
            assert executed.json()["attempts"][0]["attempt_no"] == 1

            listed = await client.get("/api/v1/common-processing-batches")
            assert listed.status_code == 200
            assert listed.json()["items"][0]["batch_id"] == str(BATCH)

    asyncio.run(scenario())

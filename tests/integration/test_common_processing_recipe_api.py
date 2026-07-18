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
from cmp.modules.processing.adapters.api.common_recipes import install_common_recipe_api
from cmp.modules.processing.application.common_recipes import (
    CommonRecipeService,
    CommonRecipeSnapshot,
    CreateCommonRecipe,
    ReviseCommonRecipe,
)
from cmp.modules.processing.domain.common_recipes import CommonProcessingRecipeContent
from cmp.shared.domain.revisions import RevisionRecord, TenantScope
from fastapi import FastAPI, Request

NOW = datetime(2026, 7, 18, 19, 0, tzinfo=UTC)
ORG = UUID("d5400000-0000-4000-8000-000000000001")
PROJECT = UUID("d5400000-0000-4000-8000-000000000002")
ACTOR = UUID("d5400000-0000-4000-8000-000000000003")
RECIPE = UUID("d5400000-0000-4000-8000-000000000004")
REVISION_ONE = UUID("d5400000-0000-4000-8000-000000000005")
REVISION_TWO = UUID("d5400000-0000-4000-8000-000000000006")
PROFILE = UUID("d5400000-0000-4000-8000-000000000007")
PROFILE_REVISION = UUID("d5400000-0000-4000-8000-000000000008")


def _context() -> SecurityContext:
    return SecurityContext(
        principal=Principal(ACTOR, PrincipalType.USER, "Modeler", True),
        organization_id=ORG,
        project_id=PROJECT,
        issuer="urn:cmp:test",
        subject=str(ACTOR),
        token_id=str(uuid4()),
        groups=(),
        scopes=("openid",),
        request_id=uuid4(),
        trace_id="00-0000000000000000000000000000d540-000000000000d540-01",
        authenticated_at=NOW,
    )


CONTEXT = _context()


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


def _record(
    revision_id: UUID,
    revision_no: int,
    based_on: UUID | None,
    content: CommonProcessingRecipeContent,
) -> RevisionRecord:
    return RevisionRecord(
        revision_id,
        "processing.common_recipe",
        RECIPE,
        TenantScope(ORG, PROJECT, "internal"),
        revision_no,
        based_on,
        "urn:cmp:processing:common-recipe:1.0.0",
        "1.0.0",
        content.digest,
        NOW,
        ACTOR,
        "test change",
        CONTEXT.request_id,
        CONTEXT.trace_id,
    )


class _RecipeService:
    def __init__(self) -> None:
        self.snapshot: CommonRecipeSnapshot | None = None

    def create_recipe(
        self, context: Any, decision: Any, command: CreateCommonRecipe
    ) -> CommonRecipeSnapshot:
        del context, decision
        self.snapshot = CommonRecipeSnapshot(
            RECIPE, _record(REVISION_ONE, 1, None, command.content), command.content
        )
        return self.snapshot

    def list_recipes(self, context: Any, decision: Any) -> tuple[CommonRecipeSnapshot, ...]:
        del context, decision
        return (self.snapshot,) if self.snapshot else ()

    def get_recipe(
        self, context: Any, decision: Any, recipe_id: UUID
    ) -> CommonRecipeSnapshot:
        del context, decision
        assert recipe_id == RECIPE and self.snapshot is not None
        return self.snapshot

    def revise_recipe(
        self,
        context: Any,
        decision: Any,
        recipe_id: UUID,
        command: ReviseCommonRecipe,
    ) -> CommonRecipeSnapshot:
        del context, decision
        assert recipe_id == RECIPE and command.expected_current_revision_id == REVISION_ONE
        self.snapshot = CommonRecipeSnapshot(
            RECIPE,
            _record(REVISION_TWO, 2, REVISION_ONE, command.content),
            command.content,
        )
        return self.snapshot


def _app(service: _RecipeService) -> FastAPI:
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

    install_common_recipe_api(
        app,
        service=cast(CommonRecipeService, service),
        security_dependency=security,
        read_dependency=read,
        execute_dependency=execute,
    )
    return app


def _content(state: str = "draft") -> dict[str, object]:
    return {
        "recipe_key": "dp600-cleanup",
        "label": "DP600 cleanup",
        "description": "Reusable explicit preprocessing",
        "mapping_profile_id": str(PROFILE),
        "mapping_profile_revision_id": str(PROFILE_REVISION),
        "mapping_profile_sha256": "a" * 64,
        "steps": [
            {
                "method_id": "rows.sort_unique",
                "method_version": "1.0.0",
                "options": {"duplicate_policy": "reject"},
            }
        ],
        "lifecycle_state": state,
    }


def test_recipe_create_list_and_publish_revision_with_strong_etag() -> None:
    async def scenario() -> None:
        service = _RecipeService()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=_app(service)), base_url="http://test"
        ) as client:
            created = await client.post(
                "/api/v1/common-processing-recipes",
                json={
                    "classification": "internal",
                    "content": _content(),
                    "change_reason": "save reusable recipe",
                },
            )
            assert created.status_code == 201, created.text
            assert created.json()["current_revision"]["lifecycle_state"] == "draft"
            assert created.headers["etag"].startswith('"revision:1:sha256:')

            listed = await client.get("/api/v1/common-processing-recipes")
            assert listed.status_code == 200
            assert listed.json()["items"][0]["processing_recipe_id"] == str(RECIPE)

            missing = await client.post(
                f"/api/v1/common-processing-recipes/{RECIPE}/revisions",
                json={"content": _content("published"), "change_reason": "publish"},
            )
            assert missing.status_code == 428

            published = await client.post(
                f"/api/v1/common-processing-recipes/{RECIPE}/revisions",
                headers={"If-Match": created.headers["etag"]},
                json={"content": _content("published"), "change_reason": "publish"},
            )
            assert published.status_code == 201, published.text
            assert published.json()["current_revision"]["revision_no"] == 2
            assert published.json()["content"]["lifecycle_state"] == "published"

    asyncio.run(scenario())

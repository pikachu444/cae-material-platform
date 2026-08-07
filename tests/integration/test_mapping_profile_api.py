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
from cmp.modules.processing.adapters.api.common_pipeline import install_common_processing_api
from cmp.modules.processing.application.mapping_profiles import (
    CreateMappingProfile,
    MappingProfileService,
    MappingProfileSnapshot,
    ReviseMappingProfile,
)
from cmp.modules.processing.domain.common_pipeline import MappingProfileContent
from cmp.shared.domain.revisions import RevisionRecord, TenantScope
from fastapi import FastAPI, Request

NOW = datetime(2026, 7, 18, 18, 0, tzinfo=UTC)
ORG = UUID("d5300000-0000-4000-8000-000000000001")
PROJECT = UUID("d5300000-0000-4000-8000-000000000002")
ACTOR = UUID("d5300000-0000-4000-8000-000000000003")
PROFILE = UUID("d5300000-0000-4000-8000-000000000004")
REVISION_ONE = UUID("d5300000-0000-4000-8000-000000000005")
REVISION_TWO = UUID("d5300000-0000-4000-8000-000000000006")


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
        trace_id="00-0000000000000000000000000000d530-000000000000d530-01",
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
    content: MappingProfileContent,
) -> RevisionRecord:
    return RevisionRecord(
        revision_id,
        "processing.mapping_profile",
        PROFILE,
        TenantScope(ORG, PROJECT, "internal"),
        revision_no,
        based_on,
        "urn:cmp:processing:mapping-profile:1.0.0",
        "1.0.0",
        content.digest,
        NOW,
        ACTOR,
        "test change",
        CONTEXT.request_id,
        CONTEXT.trace_id,
    )


class _ProfileService:
    def __init__(self) -> None:
        self.snapshot: MappingProfileSnapshot | None = None

    def create_profile(
        self, context: Any, decision: Any, command: CreateMappingProfile
    ) -> MappingProfileSnapshot:
        del context, decision
        self.snapshot = MappingProfileSnapshot(
            PROFILE, _record(REVISION_ONE, 1, None, command.content), command.content
        )
        return self.snapshot

    def list_profiles(self, context: Any, decision: Any) -> tuple[MappingProfileSnapshot, ...]:
        del context, decision
        return (self.snapshot,) if self.snapshot is not None else ()

    def get_profile(
        self, context: Any, decision: Any, profile_id: UUID, *, write: bool = False
    ) -> MappingProfileSnapshot:
        del context, decision, write
        assert profile_id == PROFILE and self.snapshot is not None
        return self.snapshot

    def revise_profile(
        self,
        context: Any,
        decision: Any,
        profile_id: UUID,
        command: ReviseMappingProfile,
    ) -> MappingProfileSnapshot:
        del context, decision
        assert profile_id == PROFILE and command.expected_current_revision_id == REVISION_ONE
        self.snapshot = MappingProfileSnapshot(
            PROFILE,
            _record(REVISION_TWO, 2, REVISION_ONE, command.content),
            command.content,
        )
        return self.snapshot


def _app(service: _ProfileService) -> FastAPI:
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

    install_common_processing_api(
        app,
        service=cast(MappingProfileService, service),
        security_dependency=security,
        read_dependency=read,
        execute_dependency=execute,
    )
    return app


def _content(label: str) -> dict[str, object]:
    return {
        "profile_key": "reusable-tensile",
        "label": label,
        "independent_quantity": "strain.engineering",
        "missing_data_policy": "drop_any",
        "bindings": [
            {
                "channel_key": "strain",
                "target_quantity": "strain.engineering",
                "accepted_normalized_units": ["1"],
            },
            {
                "channel_key": "stress",
                "target_quantity": "stress.engineering",
                "accepted_normalized_units": ["Pa"],
            },
        ],
        "attribute_bindings": [],
    }


def test_mapping_profile_create_list_and_append_revision() -> None:
    async def scenario() -> None:
        service = _ProfileService()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=_app(service)), base_url="http://test"
        ) as client:
            created = await client.post(
                "/api/v1/mapping-profiles",
                json={
                    "classification": "internal",
                    "content": _content("Reusable tensile mapping"),
                    "change_reason": "create mapping",
                },
            )
            assert created.status_code == 201, created.text
            assert created.json()["current_revision"]["revision_no"] == 1
            assert created.headers["etag"].startswith('"revision:1:sha256:')

            listed = await client.get("/api/v1/mapping-profiles")
            assert listed.status_code == 200
            assert listed.json()["items"][0]["mapping_profile_id"] == str(PROFILE)
            assert listed.json()["items"][0]["current_revision"]["revision_no"] == 1
            assert listed.json()["items"][0]["content"]["label"] == "Reusable tensile mapping"

            missing_precondition = await client.post(
                f"/api/v1/mapping-profiles/{PROFILE}/revisions",
                json={
                    "content": _content("Revised mapping"),
                    "change_reason": "revise mapping",
                },
            )
            assert missing_precondition.status_code == 428

            revised = await client.post(
                f"/api/v1/mapping-profiles/{PROFILE}/revisions",
                headers={"If-Match": created.headers["etag"]},
                json={
                    "content": _content("Revised mapping"),
                    "change_reason": "revise mapping",
                },
            )
            assert revised.status_code == 201, revised.text
            assert revised.json()["current_revision"]["revision_no"] == 2
            assert revised.json()["current_revision"]["based_on_revision_id"] == str(
                REVISION_ONE
            )
            assert revised.json()["content"]["label"] == "Revised mapping"
            assert revised.headers["etag"].startswith('"revision:2:sha256:')

            stale = await client.post(
                f"/api/v1/mapping-profiles/{PROFILE}/revisions",
                headers={"If-Match": '"revision:1:sha256:' + "f" * 64 + '"'},
                json={
                    "content": _content("Stale mapping must not append"),
                    "change_reason": "stale revision",
                },
            )
            assert stale.status_code == 412
            assert service.snapshot is not None
            assert service.snapshot.current.revision_no == 2
            assert service.snapshot.content.label == "Revised mapping"

    asyncio.run(scenario())

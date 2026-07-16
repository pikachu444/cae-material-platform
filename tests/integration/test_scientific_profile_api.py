from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import cast
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
from cmp.modules.modeling.adapters.api.scientific_profile import (
    install_scientific_profile_api,
)
from cmp.modules.modeling.application.scientific_profile import (
    SCIENTIFIC_PROFILE_AGGREGATE_TYPE,
    CreateScientificProfile,
    ReviseScientificProfile,
    RevisionSnapshot,
    ScientificProfileService,
    ScientificProfileSnapshot,
)
from cmp.modules.modeling.domain.scientific_profile import ScientificProfileFamily
from cmp.shared.domain.revisions import RevisionRecord, TenantScope, content_sha256
from fastapi import FastAPI, Request

NOW = datetime(2026, 8, 19, 9, 0, tzinfo=UTC)
ORG, PROJECT, ACTOR, PROFILE, REVISION_1, REVISION_2 = (
    UUID(int=value) for value in range(1, 7)
)
TRACE = "00-00000000000000000000000000000053-0000000000000053-01"
CONTEXT = SecurityContext(
    principal=Principal(ACTOR, PrincipalType.USER, "Elastomer modeler", True),
    organization_id=ORG,
    project_id=PROJECT,
    issuer="https://test.invalid",
    subject=str(ACTOR),
    token_id=str(uuid4()),
    groups=(),
    scopes=("openid",),
    request_id=uuid4(),
    trace_id=TRACE,
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
        trace_id=TRACE,
        decided_at=NOW,
    )


READ = _decision(Permission.MODELING_READ)
WRITE = _decision(Permission.MODELING_WRITE)


def _record(revision_id: UUID, revision_no: int, content: object) -> RevisionRecord:
    return RevisionRecord(
        revision_id=revision_id,
        aggregate_type=SCIENTIFIC_PROFILE_AGGREGATE_TYPE,
        aggregate_id=PROFILE,
        scope=TenantScope(ORG, PROJECT, "internal"),
        revision_no=revision_no,
        based_on_revision_id=REVISION_1 if revision_no == 2 else None,
        schema_id="urn:cmp:modeling:scientific-calibration-profile:1.0.0",
        schema_version="1.0.0",
        content_hash=content_sha256(content),
        created_at=NOW,
        created_by=ACTOR,
        change_reason="API fixture",
        request_id=CONTEXT.request_id,
        trace_id=TRACE,
    )


class _Service:
    def __init__(self) -> None:
        self.snapshot: ScientificProfileSnapshot | None = None

    def create(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CreateScientificProfile,
    ) -> ScientificProfileSnapshot:
        assert context is CONTEXT and decision is WRITE
        record = _record(REVISION_1, 1, command.content.canonical())
        self.snapshot = ScientificProfileSnapshot(
            PROFILE, RevisionSnapshot(record, command.content)
        )
        return self.snapshot

    def revise(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        profile_id: UUID,
        command: ReviseScientificProfile,
    ) -> ScientificProfileSnapshot:
        assert context is CONTEXT and decision is WRITE and profile_id == PROFILE
        assert command.expected_current_revision_id == REVISION_1
        record = _record(REVISION_2, 2, command.content.canonical())
        self.snapshot = ScientificProfileSnapshot(
            PROFILE, RevisionSnapshot(record, command.content)
        )
        return self.snapshot

    def get(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        profile_id: UUID,
    ) -> ScientificProfileSnapshot:
        assert context is CONTEXT and decision is READ and profile_id == PROFILE
        assert self.snapshot is not None
        return self.snapshot

    def list(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        family: ScientificProfileFamily | None = None,
    ) -> tuple[ScientificProfileSnapshot, ...]:
        assert context is CONTEXT and decision is READ
        assert family is ScientificProfileFamily.ELASTOMER_OGDEN_PRONY
        return (self.snapshot,) if self.snapshot is not None else ()


def _application() -> FastAPI:
    application = FastAPI()
    service = _Service()

    def security(request: Request) -> None:
        request.state.security_context = CONTEXT

    def read(request: Request) -> None:
        request.state.authorization_decision = READ

    def write(request: Request) -> None:
        request.state.authorization_decision = WRITE

    install_scientific_profile_api(
        application,
        service=cast(ScientificProfileService, service),
        security_dependency=security,
        read_dependency=read,
        write_dependency=write,
    )
    return application


def _request(
    app: FastAPI, method: str, path: str, body: dict[str, object] | None = None
) -> httpx.Response:
    async def send() -> httpx.Response:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            return await client.request(method, path, json=body)

    return asyncio.run(send())


def _content(multistart_count: int = 8) -> dict[str, object]:
    return {
        "profile_label": "Reference one-term Ogden",
        "family": "elastomer_ogden_prony",
        "approval_status": "reference_unapproved",
        "multistart_count": multistart_count,
        "seed": 20260716,
        "status_note": "Reference only; domain sign-off is not recorded.",
        "ogden": {
            "mu_initial_pa": 1_000_000,
            "mu_lower_pa": 1_000,
            "mu_upper_pa": 100_000_000,
            "mu_scale_pa": 1_000_000,
            "alpha_initial": 2,
            "alpha_lower": 0.1,
            "alpha_upper": 20,
            "alpha_scale": 2,
            "uniaxial_weight": 1,
            "planar_weight": 1,
            "biaxial_weight": 1,
        },
    }


def test_scientific_profile_api_creates_lists_and_revises_typed_profile() -> None:
    app = _application()
    created = _request(
        app,
        "POST",
        "/api/v1/scientific-profiles",
        {
            "classification": "internal",
            "content": _content(),
            "change_reason": "Create reference fitting policy",
        },
    )
    assert created.status_code == 201
    assert created.headers["location"] == f"/api/v1/scientific-profiles/{PROFILE}"
    assert created.json()["current_revision"]["content"]["parameters"]["alpha_upper"] == 20

    listed = _request(
        app,
        "GET",
        "/api/v1/scientific-profiles?family=elastomer_ogden_prony",
    )
    assert listed.status_code == 200
    assert len(listed.json()["items"]) == 1

    revised = _request(
        app,
        "POST",
        f"/api/v1/scientific-profiles/{PROFILE}/revisions",
        {
            "expected_current_revision_id": str(REVISION_1),
            "content": _content(12),
            "change_reason": "Increase deterministic multistart coverage",
        },
    )
    assert revised.status_code == 201
    assert revised.json()["current_revision"]["revision_no"] == 2
    assert revised.json()["current_revision"]["content"]["multistart_count"] == 12

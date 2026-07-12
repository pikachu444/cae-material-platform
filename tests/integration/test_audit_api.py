from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

import httpx
from cmp.modules.audit.adapters.api.audit import install_audit_api
from cmp.modules.audit.application.service import (
    AuditEventPage,
    AuditEventQuery,
    AuditService,
)
from cmp.modules.audit.domain.model import (
    GENESIS_HASH,
    AuditActorType,
    AuditEvent,
    AuditOutcome,
    AuditScope,
    AuditSegmentRoot,
    event_sha256,
    segment_root_sha256,
)
from cmp.modules.identity_access.application.authorization import database_permissions_for
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
    Permission,
    Role,
)
from cmp.modules.identity_access.domain.security import (
    Principal,
    PrincipalType,
    SecurityContext,
)
from fastapi import FastAPI, Request

NOW = datetime(2026, 7, 13, 15, 0, tzinfo=UTC)
ORG = UUID("ab000000-0000-4000-8000-000000000001")
PROJECT = UUID("ab000000-0000-4000-8000-000000000002")
ACTOR = UUID("ab000000-0000-4000-8000-000000000003")
REQUEST = UUID("ab000000-0000-4000-8000-000000000004")
TRACE = "00-000000000000000000000000000000ab-00000000000000ab-01"

CONTEXT = SecurityContext(
    principal=Principal(ACTOR, PrincipalType.USER, "Audit Reader", True),
    organization_id=ORG,
    project_id=PROJECT,
    issuer="https://test-idp.invalid",
    subject=str(ACTOR),
    token_id=str(uuid4()),
    groups=(),
    scopes=("openid",),
    request_id=REQUEST,
    trace_id=TRACE,
    authenticated_at=NOW,
)
DECISION = AuthorizationDecision(
    principal_id=ACTOR,
    organization_id=ORG,
    project_id=PROJECT,
    permission=Permission.AUDIT_READ,
    roles=(Role.AUDITOR,),
    database_permissions=database_permissions_for(Permission.AUDIT_READ),
    max_classification=DataClassification.RESTRICTED,
    allow_export_controlled=False,
    request_id=REQUEST,
    trace_id=TRACE,
    decided_at=NOW,
)


def _event() -> AuditEvent:
    provisional = AuditEvent(
        id=UUID("ab000000-0000-4000-8000-000000000005"),
        scope=AuditScope(ORG, PROJECT),
        sequence_no=1,
        occurred_at=NOW,
        recorded_at=NOW,
        actor_type=AuditActorType.USER,
        actor_id=ACTOR,
        action="synthetic.fixture.revision.create",
        target_type="synthetic.fixture.revision",
        target_id=UUID("ab000000-0000-4000-8000-000000000006"),
        outcome=AuditOutcome.SUCCESS,
        request_id=REQUEST,
        trace_id=TRACE,
        ip_or_client="policy-redacted",
        reason="initial immutable revision",
        previous_hash=GENESIS_HASH,
        event_hash=GENESIS_HASH,
    )
    return replace(provisional, event_hash=event_sha256(provisional))


def _root(event: AuditEvent) -> AuditSegmentRoot:
    provisional = AuditSegmentRoot(
        id=UUID("ab000000-0000-4000-8000-000000000007"),
        scope=event.scope,
        segment_no=1,
        first_sequence_no=1,
        last_sequence_no=1,
        event_count=1,
        first_event_hash=event.event_hash,
        last_event_hash=event.event_hash,
        previous_root_hash=GENESIS_HASH,
        root_hash=GENESIS_HASH,
        created_at=NOW,
        created_by=ACTOR,
        request_id=REQUEST,
        trace_id=TRACE,
    )
    return replace(provisional, root_hash=segment_root_sha256(provisional))


class _Repository:
    def __init__(self) -> None:
        self.event = _event()
        self.root = _root(self.event)

    def query_events(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        query: AuditEventQuery,
    ) -> AuditEventPage:
        del context, decision
        if query.action is not None and query.action != self.event.action:
            return AuditEventPage((), None)
        return AuditEventPage((self.event,), None)

    def load_chain(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
    ) -> tuple[tuple[AuditEvent, ...], tuple[AuditSegmentRoot, ...]]:
        del context, decision
        return (self.event,), (self.root,)

    def export_range(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        from_sequence: int,
        to_sequence: int,
    ) -> tuple[str, tuple[AuditEvent, ...], tuple[AuditSegmentRoot, ...]]:
        del context, decision, from_sequence, to_sequence
        return GENESIS_HASH, (self.event,), (self.root,)

    def seal_next(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        maximum_events: int,
    ) -> AuditSegmentRoot | None:
        del context, decision, maximum_events
        raise AssertionError("the public audit API must not expose sealing")


def _application() -> FastAPI:
    application = FastAPI()

    def security(request: Request) -> None:
        request.state.security_context = CONTEXT

    def read(request: Request) -> None:
        request.state.authorization_decision = DECISION

    install_audit_api(
        application,
        service=AuditService(repository=_Repository()),
        security_dependency=security,
        read_dependency=read,
    )
    return application


async def _get(path: str) -> httpx.Response:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=_application()),
        base_url="http://testserver",
    ) as client:
        return await client.get(path)


def test_auditor_can_query_integrity_and_bounded_export_without_raw_payload() -> None:
    events = asyncio.run(_get("/api/v1/audit/events?limit=10"))
    integrity = asyncio.run(_get("/api/v1/audit/integrity"))
    exported = asyncio.run(_get("/api/v1/audit/export?from_sequence=1&to_sequence=1"))

    assert events.status_code == integrity.status_code == exported.status_code == 200
    event = events.json()["events"][0]
    assert event["actor"] == {"type": "user", "id": str(ACTOR)}
    assert event["ip_or_client"] == "policy-redacted"
    assert "payload" not in event and "storage_key" not in event
    assert integrity.json()["state"] == "valid"
    assert exported.json()["anchor_previous_hash"] == GENESIS_HASH
    assert exported.headers["cache-control"] == "no-store"


def test_invalid_export_range_is_sanitized_and_openapi_has_no_audit_write() -> None:
    response = asyncio.run(_get("/api/v1/audit/export?from_sequence=2&to_sequence=1"))
    schema = _application().openapi()

    assert response.status_code == 422
    assert response.json()["code"] == "CMP-AUDIT-0002"
    assert set(schema["paths"]["/api/v1/audit/events"]) == {"get"}
    assert set(schema["paths"]["/api/v1/audit/integrity"]) == {"get"}
    assert set(schema["paths"]["/api/v1/audit/export"]) == {"get"}

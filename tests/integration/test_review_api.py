from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID

import httpx
import pytest
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
from cmp.modules.review_release.adapters.api.review import install_review_api
from cmp.modules.review_release.application.service import ReviewService
from cmp.modules.review_release.domain.lifecycle import (
    DecideReviewRequest,
    LifecycleState,
    ReviewConflict,
    ReviewDecisionKind,
    ReviewDecisionRecord,
    ReviewNotFound,
    ReviewRequestRecord,
    SubmitReviewRequest,
)
from fastapi import FastAPI, Request

NOW = datetime(2026, 7, 23, 9, 0, tzinfo=UTC)
ORG = UUID("29000000-0000-4000-8000-000000000001")
PROJECT = UUID("29000000-0000-4000-8000-000000000002")
AUTHOR = UUID("29000000-0000-4000-8000-000000000003")
REVIEWER = UUID("29000000-0000-4000-8000-000000000004")
OUTSIDER = UUID("29000000-0000-4000-8000-00000000000b")
AGGREGATE = UUID("29000000-0000-4000-8000-000000000005")
REVISION = UUID("29000000-0000-4000-8000-000000000006")
REQUEST_ID = UUID("29000000-0000-4000-8000-000000000007")
DECISION_ID = UUID("29000000-0000-4000-8000-000000000008")
DIGEST = "c" * 64


def _context(principal_id: UUID, request_id: UUID) -> SecurityContext:
    return SecurityContext(
        principal=Principal(principal_id, PrincipalType.USER, "Review user", True),
        organization_id=ORG,
        project_id=PROJECT,
        issuer="https://test-idp.invalid",
        subject=str(principal_id),
        token_id=str(principal_id),
        groups=(),
        scopes=("openid",),
        request_id=request_id,
        trace_id=f"trace-{principal_id}",
        authenticated_at=NOW,
    )


def _decision(
    context: SecurityContext,
    permission: Permission,
    role: Role,
) -> AuthorizationDecision:
    return AuthorizationDecision(
        principal_id=context.principal.id,
        organization_id=ORG,
        project_id=PROJECT,
        permission=permission,
        roles=(role,),
        database_permissions=database_permissions_for(permission),
        max_classification=DataClassification.INTERNAL,
        allow_export_controlled=False,
        request_id=context.request_id,
        trace_id=context.trace_id,
        decided_at=NOW,
    )


class MemoryReviewRepository:
    def __init__(self) -> None:
        self.value: ReviewRequestRecord | None = None

    def create_request(self, **kwargs: object) -> ReviewRequestRecord:
        command = kwargs["command"]
        assert isinstance(command, SubmitReviewRequest)
        assert command.classification is not None
        assert command.manifest_sha256 is not None
        if self.value is not None:
            raise ReviewConflict("already requested")
        self.value = ReviewRequestRecord(
            id=cast(UUID, kwargs["review_request_id"]),
            organization_id=ORG,
            project_id=PROJECT,
            classification=command.classification,
            aggregate_type=command.aggregate_type,
            aggregate_id=command.aggregate_id,
            revision_id=command.revision_id,
            manifest_sha256=command.manifest_sha256,
            required_role="domain_reviewer",
            requested_by=cast(UUID, kwargs["actor_id"]),
            requested_at=cast(datetime, kwargs["occurred_at"]),
            reason=command.reason,
            lifecycle_state=LifecycleState.REVIEW,
        )
        return self.value

    def get_request(self, **kwargs: object) -> ReviewRequestRecord:
        if self.value is None:
            raise ReviewNotFound("not found")
        context = cast(SecurityContext, kwargs["context"])
        decision = cast(AuthorizationDecision, kwargs["decision"])
        if (
            Role.DOMAIN_REVIEWER not in decision.roles
            and self.value.requested_by != context.principal.id
        ):
            raise ReviewNotFound("not visible")
        return self.value

    def list_requests(self, **kwargs: object) -> tuple[ReviewRequestRecord, ...]:
        if self.value is None:
            return ()
        context = cast(SecurityContext, kwargs["context"])
        decision = cast(AuthorizationDecision, kwargs["decision"])
        if (
            Role.DOMAIN_REVIEWER not in decision.roles
            and self.value.requested_by != context.principal.id
        ):
            return ()
        return (self.value,)

    def decide(self, **kwargs: object) -> ReviewRequestRecord:
        if self.value is None:
            raise ReviewNotFound("not found")
        command = kwargs["command"]
        assert isinstance(command, DecideReviewRequest)
        if self.value.decision is not None:
            raise ReviewConflict("already decided")
        if self.value.requested_by == kwargs["actor_id"]:
            raise ReviewConflict("author cannot decide")
        if command.expected_manifest_sha256 != self.value.manifest_sha256:
            raise ReviewConflict("stale digest")
        decision = ReviewDecisionRecord(
            id=cast(UUID, kwargs["decision_id"]),
            review_request_id=self.value.id,
            organization_id=ORG,
            project_id=PROJECT,
            classification=self.value.classification,
            aggregate_type=self.value.aggregate_type,
            aggregate_id=self.value.aggregate_id,
            revision_id=self.value.revision_id,
            manifest_sha256=self.value.manifest_sha256,
            decision=command.decision,
            decided_by=cast(UUID, kwargs["actor_id"]),
            decided_at=cast(datetime, kwargs["occurred_at"]),
            reason=command.reason,
        )
        self.value = replace(
            self.value,
            lifecycle_state=(
                LifecycleState.APPROVED
                if command.decision is ReviewDecisionKind.APPROVED
                else LifecycleState.CHANGES_REQUESTED
            ),
            decision=decision,
        )
        return self.value


def _app(repository: MemoryReviewRepository, *, read_as: str = "author") -> FastAPI:
    ids = iter((REQUEST_ID, DECISION_ID))
    service = ReviewService(repository=repository, id_factory=lambda: next(ids), clock=lambda: NOW)
    app = FastAPI()
    author_context = _context(AUTHOR, UUID("29000000-0000-4000-8000-000000000009"))
    reviewer_context = _context(REVIEWER, UUID("29000000-0000-4000-8000-00000000000a"))
    outsider_context = _context(OUTSIDER, UUID("29000000-0000-4000-8000-00000000000c"))
    request_decision = _decision(author_context, Permission.REVIEW_REQUEST, Role.MATERIAL_MODELER)
    read_decision = _decision(author_context, Permission.REVIEW_READ, Role.MATERIAL_MODELER)
    reviewer_read_decision = _decision(
        reviewer_context, Permission.REVIEW_READ, Role.DOMAIN_REVIEWER
    )
    outsider_read_decision = _decision(
        outsider_context, Permission.REVIEW_READ, Role.CAE_ANALYST
    )
    decide_decision = _decision(reviewer_context, Permission.REVIEW_DECIDE, Role.DOMAIN_REVIEWER)
    read_contexts = {
        "author": (author_context, read_decision),
        "reviewer": (reviewer_context, reviewer_read_decision),
        "outsider": (outsider_context, outsider_read_decision),
    }
    if read_as not in read_contexts:
        raise ValueError(f"unsupported read_as: {read_as}")
    configured_read_context, configured_read_decision = read_contexts[read_as]

    @app.middleware("http")
    async def context_middleware(request: Request, call_next: Any) -> Any:
        request.state.security_context = author_context
        response = await call_next(request)
        return response

    def security(_: Request) -> None:
        return None

    def request_permission(request: Request) -> AuthorizationDecision:
        request.state.security_context = author_context
        request.state.authorization_decision = request_decision
        return request_decision

    def read_permission(request: Request) -> AuthorizationDecision:
        request.state.security_context = configured_read_context
        request.state.authorization_decision = configured_read_decision
        return configured_read_decision

    def decide_permission(request: Request) -> AuthorizationDecision:
        request.state.security_context = reviewer_context
        request.state.authorization_decision = decide_decision
        return decide_decision

    install_review_api(
        app,
        service=service,
        security_dependency=security,
        read_dependency=read_permission,
        request_dependency=request_permission,
        decide_dependency=decide_permission,
    )
    return app


@pytest.mark.anyio
async def test_review_api_submit_read_and_decide_with_separation_of_duties() -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=_app(MemoryReviewRepository())),
        base_url="http://test",
    ) as client:
        created = await client.post(
            "/api/v1/review-requests",
            json={
                "classification": "internal",
                "aggregate_type": "modeling.material_model",
                "aggregate_id": str(AGGREGATE),
                "revision_id": str(REVISION),
                "manifest_sha256": DIGEST,
                "reason": "Submit exact immutable evidence",
            },
        )
        assert created.status_code == 201
        assert created.json()["lifecycle_state"] == "review"
        assert created.json()["decision"] is None

        listed = await client.get("/api/v1/review-requests")
        assert listed.status_code == 200
        assert len(listed.json()["items"]) == 1

        decided = await client.post(
            f"/api/v1/review-requests/{REQUEST_ID}/decisions",
            json={
                "expected_manifest_sha256": DIGEST,
                "decision": "approved",
                "reason": "Domain review confirms the pinned evidence",
            },
        )
        assert decided.status_code == 201
        assert decided.json()["lifecycle_state"] == "approved"
        assert decided.json()["decision"]["decided_by"] == str(REVIEWER)


@pytest.mark.anyio
async def test_review_api_rejects_stale_digest() -> None:
    repository = MemoryReviewRepository()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=_app(repository)),
        base_url="http://test",
    ) as client:
        await client.post(
            "/api/v1/review-requests",
            json={
                "classification": "internal",
                "aggregate_type": "validation.result",
                "aggregate_id": str(AGGREGATE),
                "revision_id": str(REVISION),
                "manifest_sha256": DIGEST,
                "reason": "Submit exact immutable validation evidence",
            },
        )
        response = await client.post(
            f"/api/v1/review-requests/{REQUEST_ID}/decisions",
            json={
                "expected_manifest_sha256": "d" * 64,
                "decision": "approved",
                "reason": "Digest is intentionally stale",
            },
        )
        assert response.status_code == 409
        assert response.json()["code"] == "CMP-REVIEW-0003"


@pytest.mark.anyio
async def test_reviewer_history_and_direct_reads_remain_visible_after_decision() -> None:
    repository = MemoryReviewRepository()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=_app(repository, read_as="reviewer")),
        base_url="http://test",
    ) as reviewer_client:
        created = await reviewer_client.post(
            "/api/v1/review-requests",
            json={
                "classification": "internal",
                "aggregate_type": "modeling.material_model",
                "aggregate_id": str(AGGREGATE),
                "revision_id": str(REVISION),
                "manifest_sha256": DIGEST,
                "reason": "Cross-principal review history regression",
            },
        )
        assert created.status_code == 201

        pending = await reviewer_client.get(f"/api/v1/review-requests/{REQUEST_ID}")
        assert pending.status_code == 200
        assert pending.json()["lifecycle_state"] == "review"
        assert len((await reviewer_client.get("/api/v1/review-requests")).json()["items"]) == 1

        decided = await reviewer_client.post(
            f"/api/v1/review-requests/{REQUEST_ID}/decisions",
            json={
                "expected_manifest_sha256": DIGEST,
                "decision": "approved",
                "reason": "Reviewer history must remain readable",
            },
        )
        assert decided.status_code == 201

        completed = await reviewer_client.get(f"/api/v1/review-requests/{REQUEST_ID}")
        assert completed.status_code == 200
        assert completed.json()["lifecycle_state"] == "approved"
        assert completed.json()["decision"]["decided_by"] == str(REVIEWER)
        history = await reviewer_client.get("/api/v1/review-requests")
        assert history.status_code == 200
        assert history.json()["items"][0]["lifecycle_state"] == "approved"

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=_app(repository, read_as="outsider")),
        base_url="http://test",
    ) as outsider_client:
        assert (
            await outsider_client.get(f"/api/v1/review-requests/{REQUEST_ID}")
        ).status_code == 404
        assert (await outsider_client.get("/api/v1/review-requests")).json()["items"] == []

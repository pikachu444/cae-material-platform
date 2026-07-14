from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

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
from cmp.modules.review_release.application.service import ReviewService
from cmp.modules.review_release.domain.lifecycle import (
    DecideReviewRequest,
    InvalidReview,
    LifecycleState,
    ReviewConflict,
    ReviewDecisionKind,
    ReviewDecisionRecord,
    ReviewRequestRecord,
    SubmitReviewRequest,
)

NOW = datetime(2026, 7, 23, 9, 0, tzinfo=UTC)
ORG = UUID("28000000-0000-4000-8000-000000000001")
PROJECT = UUID("28000000-0000-4000-8000-000000000002")
AUTHOR = UUID("28000000-0000-4000-8000-000000000003")
REVIEWER = UUID("28000000-0000-4000-8000-000000000004")
AGGREGATE = UUID("28000000-0000-4000-8000-000000000005")
REVISION = UUID("28000000-0000-4000-8000-000000000006")
REVIEW_REQUEST = UUID("28000000-0000-4000-8000-000000000007")
DECISION = UUID("28000000-0000-4000-8000-000000000008")
EXTRA_ID = UUID("28000000-0000-4000-8000-000000000009")
DIGEST = "a" * 64


def _context(principal_id: UUID, request_id: UUID | None = None) -> SecurityContext:
    return SecurityContext(
        principal=Principal(principal_id, PrincipalType.USER, "Review user", True),
        organization_id=ORG,
        project_id=PROJECT,
        issuer="https://test-idp.invalid",
        subject=str(principal_id),
        token_id=str(principal_id),
        groups=(),
        scopes=("openid",),
        request_id=request_id or uuid4(),
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


class FakeReviewRepository:
    def __init__(self) -> None:
        self.value: ReviewRequestRecord | None = None
        self.newer_revision = False

    def create_request(self, **kwargs: object) -> ReviewRequestRecord:
        command = kwargs["command"]
        assert isinstance(command, SubmitReviewRequest)
        self.value = ReviewRequestRecord(
            id=kwargs["review_request_id"],
            organization_id=ORG,
            project_id=PROJECT,
            classification=command.classification,
            aggregate_type=command.aggregate_type,
            aggregate_id=command.aggregate_id,
            revision_id=command.revision_id,
            manifest_sha256=command.manifest_sha256,
            required_role="domain_reviewer",
            requested_by=kwargs["actor_id"],
            requested_at=kwargs["occurred_at"],
            reason=command.reason,
            lifecycle_state=LifecycleState.REVIEW,
        )
        return self.value

    def get_request(self, **kwargs: object) -> ReviewRequestRecord:
        if self.value is None:
            raise ReviewConflict("missing")
        return self.value

    def list_requests(self, **kwargs: object) -> tuple[ReviewRequestRecord, ...]:
        return (self.value,) if self.value is not None else ()

    def decide(self, **kwargs: object) -> ReviewRequestRecord:
        if self.value is None:
            raise ReviewConflict("missing")
        command = kwargs["command"]
        assert isinstance(command, DecideReviewRequest)
        actor_id = kwargs["actor_id"]
        if self.value.requested_by == actor_id:
            raise ReviewConflict("author cannot decide")
        if command.expected_manifest_sha256 != self.value.manifest_sha256:
            raise ReviewConflict("stale digest")
        if self.newer_revision:
            raise ReviewConflict("newer revision")
        decision = ReviewDecisionRecord(
            id=kwargs["decision_id"],
            review_request_id=self.value.id,
            organization_id=ORG,
            project_id=PROJECT,
            classification=self.value.classification,
            aggregate_type=self.value.aggregate_type,
            aggregate_id=self.value.aggregate_id,
            revision_id=self.value.revision_id,
            manifest_sha256=self.value.manifest_sha256,
            decision=command.decision,
            decided_by=actor_id,
            decided_at=kwargs["occurred_at"],
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


def _service(repository: FakeReviewRepository) -> ReviewService:
    ids = iter((REVIEW_REQUEST, DECISION, EXTRA_ID))
    return ReviewService(repository=repository, id_factory=lambda: next(ids), clock=lambda: NOW)


def _command() -> SubmitReviewRequest:
    return SubmitReviewRequest(
        classification=DataClassification.INTERNAL,
        aggregate_type="modeling.material_model",
        aggregate_id=AGGREGATE,
        revision_id=REVISION,
        manifest_sha256=DIGEST,
        reason="Submit the exact model/card/validation manifest for review",
    )


def test_review_request_and_separated_approval_are_append_only() -> None:
    repository = FakeReviewRepository()
    service = _service(repository)
    author_context = _context(AUTHOR)
    request = service.create_request(
        author_context,
        _decision(author_context, Permission.REVIEW_REQUEST, Role.MATERIAL_MODELER),
        _command(),
    )
    assert request.lifecycle_state is LifecycleState.REVIEW
    assert request.decision is None

    reviewer_context = _context(REVIEWER)
    decided = service.decide(
        reviewer_context,
        _decision(reviewer_context, Permission.REVIEW_DECIDE, Role.DOMAIN_REVIEWER),
        REVIEW_REQUEST,
        DecideReviewRequest(
            expected_manifest_sha256=DIGEST,
            decision=ReviewDecisionKind.APPROVED,
            reason="Evidence digest and lineage are acceptable",
        ),
    )
    assert decided.lifecycle_state is LifecycleState.APPROVED
    assert decided.decision is not None
    assert decided.decision.decided_by == REVIEWER
    assert decided.decision.manifest_sha256 == DIGEST


def test_author_only_decision_and_stale_digest_are_rejected() -> None:
    repository = FakeReviewRepository()
    service = _service(repository)
    author_context = _context(AUTHOR)
    service.create_request(
        author_context,
        _decision(author_context, Permission.REVIEW_REQUEST, Role.MATERIAL_MODELER),
        _command(),
    )
    with pytest.raises(ReviewConflict, match="author"):
        service.decide(
            author_context,
            _decision(author_context, Permission.REVIEW_DECIDE, Role.DOMAIN_REVIEWER),
            REVIEW_REQUEST,
            DecideReviewRequest(
                expected_manifest_sha256=DIGEST,
                decision=ReviewDecisionKind.APPROVED,
                reason="The author cannot approve their own candidate",
            ),
        )

    reviewer_context = _context(REVIEWER)
    with pytest.raises(ReviewConflict, match="stale"):
        service.decide(
            reviewer_context,
            _decision(reviewer_context, Permission.REVIEW_DECIDE, Role.DOMAIN_REVIEWER),
            REVIEW_REQUEST,
            DecideReviewRequest(
                expected_manifest_sha256="b" * 64,
                decision=ReviewDecisionKind.APPROVED,
                reason="The client supplied an old digest",
            ),
        )


def test_review_decision_requires_domain_reviewer_and_valid_digest() -> None:
    repository = FakeReviewRepository()
    service = _service(repository)
    author_context = _context(AUTHOR)
    service.create_request(
        author_context,
        _decision(author_context, Permission.REVIEW_REQUEST, Role.MATERIAL_MODELER),
        _command(),
    )
    reviewer_context = _context(REVIEWER)
    with pytest.raises(ReviewConflict, match="domain reviewer"):
        service.decide(
            reviewer_context,
            _decision(reviewer_context, Permission.REVIEW_DECIDE, Role.MATERIAL_MODELER),
            REVIEW_REQUEST,
            DecideReviewRequest(
                expected_manifest_sha256=DIGEST,
                decision=ReviewDecisionKind.CHANGES_REQUESTED,
                reason="A modeler role cannot decide",
            ),
        )
    with pytest.raises(InvalidReview, match="SHA-256"):
        DecideReviewRequest(
            expected_manifest_sha256="not-a-digest",
            decision=ReviewDecisionKind.APPROVED,
            reason="invalid digest",
        )

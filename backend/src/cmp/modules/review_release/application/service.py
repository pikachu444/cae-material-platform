"""Application boundary for T-29 review requests and append-only decisions."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID, uuid4

from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
    Permission,
    Role,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.review_release.domain.lifecycle import (
    DecideReviewRequest,
    InvalidReview,
    ReviewConflict,
    ReviewRequestRecord,
    SubmitReviewRequest,
)


class ReviewRepository(Protocol):
    def create_request(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        review_request_id: UUID,
        command: SubmitReviewRequest,
        actor_id: UUID,
        occurred_at: datetime,
    ) -> ReviewRequestRecord: ...

    def get_request(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        review_request_id: UUID,
    ) -> ReviewRequestRecord: ...

    def list_requests(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        limit: int,
        aggregate_type: str | None = None,
        aggregate_id: UUID | None = None,
        revision_id: UUID | None = None,
    ) -> tuple[ReviewRequestRecord, ...]: ...

    def decide(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        decision_id: UUID,
        review_request_id: UUID,
        command: DecideReviewRequest,
        actor_id: UUID,
        occurred_at: datetime,
    ) -> ReviewRequestRecord: ...


@dataclass(frozen=True, slots=True)
class ReviewService:
    """Enforce authorization, separation of duties, and typed review commands."""

    repository: ReviewRepository
    id_factory: Callable[[], UUID] = uuid4
    clock: Callable[[], datetime] = lambda: datetime.now(UTC)

    @staticmethod
    def _assert_context(
        context: SecurityContext,
        decision: AuthorizationDecision,
        permission: Permission,
    ) -> None:
        if (
            decision.permission is not permission
            or decision.principal_id != context.principal.id
            or decision.organization_id != context.organization_id
            or decision.project_id != context.project_id
            or decision.request_id != context.request_id
            or decision.trace_id != context.trace_id
        ):
            raise ReviewConflict("authorization decision does not match review request context")

    @staticmethod
    def _assert_scope(
        context: SecurityContext,
        decision: AuthorizationDecision,
        classification: DataClassification,
    ) -> None:
        if not decision.allows(context.organization_id, context.project_id, classification):
            raise ReviewConflict("review command is outside the authorized tenant scope")

    def _id(self) -> UUID:
        value = self.id_factory()
        if value.int == 0:
            raise ReviewConflict("review id_factory returned a zero UUID")
        return value

    def create_request(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: SubmitReviewRequest,
    ) -> ReviewRequestRecord:
        self._assert_context(context, decision, Permission.REVIEW_REQUEST)
        self._assert_scope(context, decision, command.classification)
        now = self.clock()
        return self.repository.create_request(
            context=context,
            decision=decision,
            review_request_id=self._id(),
            command=command,
            actor_id=context.principal.id,
            occurred_at=now,
        )

    def get_request(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        review_request_id: UUID,
    ) -> ReviewRequestRecord:
        self._assert_context(context, decision, Permission.REVIEW_READ)
        if review_request_id.int == 0:
            raise InvalidReview("review_request_id must be a non-zero UUID")
        return self.repository.get_request(
            context=context, decision=decision, review_request_id=review_request_id
        )

    def list_requests(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        *,
        limit: int,
        aggregate_type: str | None = None,
        aggregate_id: UUID | None = None,
        revision_id: UUID | None = None,
    ) -> tuple[ReviewRequestRecord, ...]:
        self._assert_context(context, decision, Permission.REVIEW_READ)
        if not 1 <= limit <= 200:
            raise InvalidReview("limit must be between 1 and 200")
        return self.repository.list_requests(
            context=context,
            decision=decision,
            limit=limit,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            revision_id=revision_id,
        )

    def decide(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        review_request_id: UUID,
        command: DecideReviewRequest,
    ) -> ReviewRequestRecord:
        self._assert_context(context, decision, Permission.REVIEW_DECIDE)
        if Role.DOMAIN_REVIEWER not in decision.roles:
            raise ReviewConflict("only a domain reviewer may record a review decision")
        if review_request_id.int == 0:
            raise InvalidReview("review_request_id must be a non-zero UUID")
        return self.repository.decide(
            context=context,
            decision=decision,
            decision_id=self._id(),
            review_request_id=review_request_id,
            command=command,
            actor_id=context.principal.id,
            occurred_at=self.clock(),
        )

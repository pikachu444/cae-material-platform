"""Application boundary for the bounded T-30 reference release channel."""

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
)
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.review_release.domain.release import (
    CreateRelease,
    InvalidRelease,
    ReleaseConflict,
    ReleaseRecord,
)


class ReleaseRepository(Protocol):
    def create(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        release_id: UUID,
        manifest_id: UUID,
        artifact_id: UUID,
        command: CreateRelease,
        actor_id: UUID,
        occurred_at: datetime,
    ) -> ReleaseRecord: ...

    def get(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        release_id: UUID,
    ) -> ReleaseRecord: ...

    def list(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        limit: int,
    ) -> tuple[ReleaseRecord, ...]: ...


@dataclass(frozen=True, slots=True)
class ReleaseService:
    repository: ReleaseRepository
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
            raise ReleaseConflict("authorization decision does not match release request context")

    @staticmethod
    def _assert_scope(
        context: SecurityContext,
        decision: AuthorizationDecision,
        classification: DataClassification,
    ) -> None:
        if not decision.allows(context.organization_id, context.project_id, classification):
            raise ReleaseConflict("release command is outside the authorized tenant scope")

    def _id(self, name: str) -> UUID:
        value = self.id_factory()
        if value.int == 0:
            raise ReleaseConflict(f"{name} id_factory returned a zero UUID")
        return value

    def create(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CreateRelease,
    ) -> ReleaseRecord:
        self._assert_context(context, decision, Permission.RELEASE_PUBLISH)
        self._assert_scope(context, decision, command.classification)
        return self.repository.create(
            context=context,
            decision=decision,
            release_id=self._id("release"),
            manifest_id=self._id("manifest"),
            artifact_id=self._id("artifact"),
            command=command,
            actor_id=context.principal.id,
            occurred_at=self.clock(),
        )

    def get(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        release_id: UUID,
    ) -> ReleaseRecord:
        self._assert_context(context, decision, Permission.RELEASE_READ)
        if release_id.int == 0:
            raise InvalidRelease("release_id must be a non-zero UUID")
        return self.repository.get(context=context, decision=decision, release_id=release_id)

    def list(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        *,
        limit: int,
    ) -> tuple[ReleaseRecord, ...]:
        self._assert_context(context, decision, Permission.RELEASE_READ)
        if not 1 <= limit <= 200:
            raise InvalidRelease("limit must be between 1 and 200")
        return self.repository.list(context=context, decision=decision, limit=limit)

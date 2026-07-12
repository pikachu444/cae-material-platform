"""T-16 durable reconciliation scheduling and staging-only retention cleanup."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import UUID

from cmp.modules.artifacts.application.content import ReconciliationResult
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
    Permission,
)
from cmp.modules.identity_access.domain.security import SecurityContext


@dataclass(frozen=True, slots=True)
class ReconciliationLease:
    schedule_id: UUID
    run_id: UUID
    lease_token: UUID
    lease_expires_at: datetime
    retention: timedelta
    classification: DataClassification


@dataclass(frozen=True, slots=True)
class StagingCleanupCandidate:
    pending_artifact_id: UUID
    staging_object_key: str


@dataclass(frozen=True, slots=True)
class MaintenanceCycleResult:
    status: str
    run_id: UUID | None = None
    artifacts_checked: int = 0
    pending_recovered: int = 0
    issues_recorded: int = 0
    staging_cleaned: int = 0


class MaintenanceRepository(Protocol):
    def ensure_schedule(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        classification: DataClassification,
        interval: timedelta,
        retention: timedelta,
        now: datetime,
    ) -> UUID: ...

    def claim(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        lease_duration: timedelta,
        now: datetime,
    ) -> ReconciliationLease | None: ...

    def cleanup_candidates(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        classification: DataClassification,
        cutoff: datetime,
        limit: int,
    ) -> tuple[StagingCleanupCandidate, ...]: ...

    def record_cleanup(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        lease: ReconciliationLease,
        candidate: StagingCleanupCandidate,
        cleaned_at: datetime,
    ) -> bool: ...

    def complete(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        lease: ReconciliationLease,
        result: ReconciliationResult,
        staging_cleaned: int,
        now: datetime,
    ) -> None: ...

    def fail(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        lease: ReconciliationLease,
        failure_code: str,
        now: datetime,
    ) -> None: ...


class StagingObjectCleaner(Protocol):
    async def discard(self, object_key: str) -> None: ...


class ArtifactMaintenanceCoordinator:
    def __init__(
        self,
        *,
        repository: MaintenanceRepository,
        reconciler: Callable[[], Awaitable[ReconciliationResult]],
        object_store: StagingObjectCleaner,
        clock: Callable[[], datetime] | None = None,
        lease_duration: timedelta = timedelta(minutes=5),
        cleanup_limit: int = 1000,
    ) -> None:
        self._repository = repository
        self._reconciler = reconciler
        self._store = object_store
        self._clock = clock or (lambda: datetime.now(UTC))
        self._lease_duration = lease_duration
        self._cleanup_limit = cleanup_limit

    @staticmethod
    def _scope(context: SecurityContext, decision: AuthorizationDecision) -> None:
        if (
            decision.permission is not Permission.ARTIFACT_WRITE
            or decision.principal_id != context.principal.id
            or decision.organization_id != context.organization_id
            or decision.project_id != context.project_id
        ):
            raise ValueError("artifact maintenance requires exact artifact.write scope")

    async def run_once(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> MaintenanceCycleResult:
        self._scope(context, decision)
        lease = self._repository.claim(
            context=context,
            decision=decision,
            lease_duration=self._lease_duration,
            now=self._clock(),
        )
        if lease is None:
            return MaintenanceCycleResult("idle")
        try:
            result = await self._reconciler()
            cleaned = 0
            cutoff = self._clock() - lease.retention
            for candidate in self._repository.cleanup_candidates(
                context=context,
                decision=decision,
                classification=lease.classification,
                cutoff=cutoff,
                limit=self._cleanup_limit,
            ):
                await self._store.discard(candidate.staging_object_key)
                cleaned += int(
                    self._repository.record_cleanup(
                        context=context,
                        decision=decision,
                        lease=lease,
                        candidate=candidate,
                        cleaned_at=self._clock(),
                    )
                )
            self._repository.complete(
                context=context,
                decision=decision,
                lease=lease,
                result=result,
                staging_cleaned=cleaned,
                now=self._clock(),
            )
        except Exception:
            self._repository.fail(
                context=context,
                decision=decision,
                lease=lease,
                failure_code="maintenance_failed",
                now=self._clock(),
            )
            raise
        return MaintenanceCycleResult(
            "succeeded",
            lease.run_id,
            result.artifacts_checked,
            result.pending_recovered,
            result.issues_recorded,
            cleaned,
        )

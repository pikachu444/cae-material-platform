"""T-16 transactional outbox publisher use cases and persistence ports."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import UUID

from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    Permission,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.jobs.domain.events import (
    ClaimedCloudEvent,
    CloudEventRecord,
    EventLeaseLost,
    validate_failure_code,
)


class OutboxRepository(Protocol):
    def claim(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        limit: int,
        lease_duration: timedelta,
        now: datetime,
    ) -> tuple[ClaimedCloudEvent, ...]: ...

    def published(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        event_id: UUID,
        lease_token: UUID,
        published_at: datetime,
    ) -> None: ...

    def failed(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        event_id: UUID,
        lease_token: UUID,
        failure_code: str,
        retry_at: datetime,
        failed_at: datetime,
        maximum_attempts: int,
    ) -> bool: ...


class EventTransport(Protocol):
    def publish(self, event: CloudEventRecord) -> None:
        """Return only after the transport accepted the immutable CloudEvent."""


@dataclass(frozen=True, slots=True)
class PublishBatchResult:
    claimed: int
    published: int
    retry_scheduled: int
    poisoned: int


class OutboxPublisher:
    """Deliver claimed events at least once; inbox dedup owns duplicate side effects."""

    def __init__(
        self,
        *,
        repository: OutboxRepository,
        transport: EventTransport,
        clock: Callable[[], datetime] | None = None,
        lease_duration: timedelta = timedelta(seconds=30),
        retry_delay: timedelta = timedelta(seconds=5),
        maximum_attempts: int = 5,
        batch_size: int = 100,
    ) -> None:
        if not timedelta(seconds=5) <= lease_duration <= timedelta(hours=1):
            raise ValueError("event lease_duration must be between 5 seconds and one hour")
        if not timedelta(seconds=1) <= retry_delay <= timedelta(hours=24):
            raise ValueError("event retry_delay must be between 1 second and 24 hours")
        if not 1 <= maximum_attempts <= 100:
            raise ValueError("maximum_attempts must be between 1 and 100")
        if not 1 <= batch_size <= 1000:
            raise ValueError("batch_size must be between 1 and 1000")
        self._repository = repository
        self._transport = transport
        self._clock = clock or (lambda: datetime.now(UTC))
        self._lease_duration = lease_duration
        self._retry_delay = retry_delay
        self._maximum_attempts = maximum_attempts
        self._batch_size = batch_size

    @staticmethod
    def _assert_scope(
        context: SecurityContext,
        decision: AuthorizationDecision,
    ) -> None:
        if (
            decision.permission is not Permission.JOB_EXECUTE
            or decision.principal_id != context.principal.id
            or decision.organization_id != context.organization_id
            or decision.project_id != context.project_id
            or decision.request_id != context.request_id
            or decision.trace_id != context.trace_id
        ):
            raise ValueError("outbox dispatch requires exact job.execute scope")

    def publish_batch(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
    ) -> PublishBatchResult:
        self._assert_scope(context, decision)
        claimed = self._repository.claim(
            context=context,
            decision=decision,
            limit=self._batch_size,
            lease_duration=self._lease_duration,
            now=self._clock(),
        )
        published = 0
        retries = 0
        poisoned = 0
        for delivery in claimed:
            try:
                self._transport.publish(delivery.event)
            except Exception as error:
                failure_code = getattr(error, "code", "transport_unavailable")
                if not isinstance(failure_code, str):
                    failure_code = "transport_unavailable"
                validate_failure_code(failure_code)
                failed_at = self._clock()
                is_poison = self._repository.failed(
                    context=context,
                    decision=decision,
                    event_id=delivery.event.id,
                    lease_token=delivery.lease_token,
                    failure_code=failure_code,
                    retry_at=failed_at + self._retry_delay,
                    failed_at=failed_at,
                    maximum_attempts=self._maximum_attempts,
                )
                poisoned += int(is_poison)
                retries += int(not is_poison)
                continue
            self._repository.published(
                context=context,
                decision=decision,
                event_id=delivery.event.id,
                lease_token=delivery.lease_token,
                published_at=self._clock(),
            )
            published += 1
        return PublishBatchResult(len(claimed), published, retries, poisoned)


__all__ = [
    "EventLeaseLost",
    "EventTransport",
    "OutboxPublisher",
    "OutboxRepository",
    "PublishBatchResult",
]

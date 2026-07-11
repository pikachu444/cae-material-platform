"""Bind a trusted job-runner service context to the synchronous JobService."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from uuid import UUID

from cmp.modules.identity_access.domain.authorization import AuthorizationDecision
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.jobs.application.jobs import (
    ClaimedAttempt,
    ClaimJob,
    FinalizeAttempt,
    FinalizeResult,
    HeartbeatAttempt,
    HeartbeatResult,
    JobService,
    StartAttempt,
)


class AuthorizedJobWorkerQueue:
    """Async worker port using one pre-authorized project-scoped service principal."""

    def __init__(
        self,
        *,
        service: JobService,
        context: SecurityContext,
        decision: AuthorizationDecision,
        runner_id: UUID,
        lease_duration: timedelta,
    ) -> None:
        if runner_id.int == 0:
            raise ValueError("runner_id must be non-zero")
        if not timedelta(seconds=5) <= lease_duration <= timedelta(hours=24):
            raise ValueError("lease_duration must be between 5 seconds and 24 hours")
        self._service = service
        self._context = context
        self._decision = decision
        self._runner_id = runner_id
        self._lease_duration = lease_duration

    async def claim(
        self, accepted_job_types: tuple[str, ...]
    ) -> ClaimedAttempt | None:
        return await asyncio.to_thread(
            self._service.claim,
            self._context,
            self._decision,
            ClaimJob(self._runner_id, accepted_job_types, self._lease_duration),
        )

    async def start(self, claimed: ClaimedAttempt) -> ClaimedAttempt:
        token = claimed.attempt.lease_token
        if token is None:
            raise ValueError("claimed attempt has no lease fencing token")
        return await asyncio.to_thread(
            self._service.start,
            self._context,
            self._decision,
            StartAttempt(claimed.attempt.id, token),
        )

    async def heartbeat(self, command: HeartbeatAttempt) -> HeartbeatResult:
        bounded = HeartbeatAttempt(
            attempt_id=command.attempt_id,
            lease_token=command.lease_token,
            lease_duration=self._lease_duration,
            progress_fraction=command.progress_fraction,
            progress_phase=command.progress_phase,
            waiting_external=command.waiting_external,
        )
        return await asyncio.to_thread(
            self._service.heartbeat,
            self._context,
            self._decision,
            bounded,
        )

    async def finalize(self, command: FinalizeAttempt) -> FinalizeResult:
        return await asyncio.to_thread(
            self._service.finalize,
            self._context,
            self._decision,
            command,
        )

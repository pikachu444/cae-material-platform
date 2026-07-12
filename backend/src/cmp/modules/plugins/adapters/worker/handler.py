"""Map isolated plugin execution outcomes onto the durable T-15 Attempt contract."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from cmp.modules.jobs.application.jobs import ClaimedAttempt
from cmp.modules.jobs.domain.jobs import AttemptState, Failure, FailureCategory
from cmp.modules.plugins.application.execution import PluginExecutionService
from cmp.modules.plugins.application.planning import PluginExecutionPlanner
from cmp.modules.plugins.domain.execution import (
    InvalidExecutionRequest,
    InvalidResultManifest,
    IsolationUnavailable,
    PackageIntegrityError,
    PluginExecutionCancelled,
    PluginExecutionTimedOut,
    ResultStatus,
    ValidatedPluginResult,
)

PLUGIN_JOB_TYPE = "plugin.run"


@dataclass(frozen=True, slots=True)
class CommittedResultManifest:
    manifest_id: UUID
    manifest_digest: str

    def __post_init__(self) -> None:
        if self.manifest_id.int == 0:
            raise ValueError("manifest_id must be non-zero")


class PluginResultCommitter(Protocol):
    """Atomically commit validated manifest/output bytes behind the future T-10 port."""

    async def commit(
        self,
        *,
        claimed: ClaimedAttempt,
        result: ValidatedPluginResult,
    ) -> CommittedResultManifest: ...


@dataclass(frozen=True, slots=True)
class PluginAttemptResult:
    outcome: AttemptState
    result_manifest_id: UUID | None = None
    result_manifest_digest: str | None = None
    failure: Failure | None = None


def _failure(category: FailureCategory, code: str, detail: str) -> PluginAttemptResult:
    return PluginAttemptResult(
        AttemptState.FAILED,
        failure=Failure(category, code, detail),
    )


class PluginAttemptHandler:
    """Execute one claimed attempt; never expose plugin exception or filesystem details."""

    def __init__(
        self,
        *,
        planner: PluginExecutionPlanner,
        execution: PluginExecutionService,
        committer: PluginResultCommitter,
    ) -> None:
        self._planner = planner
        self._execution = execution
        self._committer = committer

    async def execute(
        self,
        claimed: ClaimedAttempt,
        cancellation: asyncio.Event,
    ) -> PluginAttemptResult:
        try:
            command = await self._planner.prepare(claimed)
            result = await self._execution.execute(command, cancellation)
            committed = await self._committer.commit(claimed=claimed, result=result)
            if committed.manifest_digest != result.manifest_digest:
                raise RuntimeError("result committer returned a different manifest digest")
        except PluginExecutionCancelled:
            return PluginAttemptResult(AttemptState.CANCELLED)
        except PluginExecutionTimedOut:
            return PluginAttemptResult(
                AttemptState.TIMED_OUT,
                failure=Failure(
                    FailureCategory.DEADLINE_EXCEEDED,
                    "plugin_execution_timed_out",
                    "The isolated plugin execution exceeded its immutable deadline.",
                ),
            )
        except IsolationUnavailable:
            return _failure(
                FailureCategory.POLICY_DENIED,
                "plugin_isolation_unavailable",
                "The required isolated runtime controls were unavailable.",
            )
        except PackageIntegrityError:
            return _failure(
                FailureCategory.POLICY_DENIED,
                "plugin_package_integrity_failed",
                "The approved plugin package failed integrity validation.",
            )
        except InvalidExecutionRequest:
            return _failure(
                FailureCategory.POLICY_DENIED,
                "plugin_execution_request_invalid",
                "The immutable plugin execution request violated platform policy.",
            )
        except InvalidResultManifest:
            return _failure(
                FailureCategory.OUTPUT_INVALID,
                "plugin_result_invalid",
                "The plugin Result Manifest or staged output failed validation.",
            )

        manifest_values = (committed.manifest_id, committed.manifest_digest)
        if result.status is ResultStatus.SUCCEEDED:
            return PluginAttemptResult(AttemptState.SUCCEEDED, *manifest_values)
        if result.status is ResultStatus.CANCELLED:
            return PluginAttemptResult(AttemptState.CANCELLED, *manifest_values)
        if result.status is ResultStatus.TIMED_OUT:
            return PluginAttemptResult(
                AttemptState.TIMED_OUT,
                *manifest_values,
                failure=Failure(
                    FailureCategory.DEADLINE_EXCEEDED,
                    "plugin_reported_timeout",
                    "The plugin reported that its immutable deadline elapsed.",
                ),
            )
        return PluginAttemptResult(
            AttemptState.FAILED,
            *manifest_values,
            failure=Failure(
                FailureCategory.DOMAIN_INVALID,
                "plugin_reported_failure",
                "The plugin reported a generic validation or execution failure.",
            ),
        )

from __future__ import annotations

import asyncio
from typing import cast
from uuid import UUID

import pytest
from cmp.modules.jobs.application.jobs import ClaimedAttempt
from cmp.modules.jobs.domain.jobs import AttemptState
from cmp.modules.plugins.adapters.worker.handler import (
    CommittedResultManifest,
    PluginAttemptHandler,
)
from cmp.modules.plugins.application.execution import ExecutePlugin, PluginExecutionService
from cmp.modules.plugins.application.planning import PluginExecutionPlanner
from cmp.modules.plugins.domain.execution import (
    PluginExecutionCancelled,
    PluginExecutionTimedOut,
    ResultStatus,
    ValidatedPluginResult,
)


class _Planner:
    def __init__(self) -> None:
        self.cleaned: list[ExecutePlugin] = []

    async def prepare(self, claimed: ClaimedAttempt) -> ExecutePlugin:
        del claimed
        return cast(ExecutePlugin, object())

    def cleanup(self, command: ExecutePlugin) -> None:
        self.cleaned.append(command)


class _Execution:
    def __init__(self, status: ResultStatus | None = None, error: Exception | None = None) -> None:
        self._status = status
        self._error = error

    async def execute(
        self,
        command: ExecutePlugin,
        cancellation: asyncio.Event,
    ) -> ValidatedPluginResult:
        del command, cancellation
        if self._error is not None:
            raise self._error
        assert self._status is not None
        return ValidatedPluginResult(self._status, {}, "a" * 64, ())


class _Committer:
    async def commit(
        self,
        *,
        claimed: ClaimedAttempt,
        result: ValidatedPluginResult,
    ) -> CommittedResultManifest:
        del claimed
        return CommittedResultManifest(
            UUID("84000000-0000-4000-8000-000000000001"),
            result.manifest_digest,
        )


@pytest.mark.parametrize(
    ("status", "error", "expected"),
    (
        (ResultStatus.SUCCEEDED, None, AttemptState.SUCCEEDED),
        (ResultStatus.FAILED, None, AttemptState.FAILED),
        (None, PluginExecutionCancelled("cancelled"), AttemptState.CANCELLED),
        (None, PluginExecutionTimedOut("timed out"), AttemptState.TIMED_OUT),
    ),
)
def test_plugin_handler_cleans_planner_owned_attempt_root_for_all_outcomes(
    status: ResultStatus | None,
    error: Exception | None,
    expected: AttemptState,
) -> None:
    planner = _Planner()
    execution = _Execution(status, error)
    handler = PluginAttemptHandler(
        planner=cast(PluginExecutionPlanner, planner),
        execution=cast(PluginExecutionService, execution),
        committer=_Committer(),
    )

    result = asyncio.run(
        handler.execute(
            cast(ClaimedAttempt, object()),
            asyncio.Event(),
        )
    )

    assert result.outcome is expected
    assert len(planner.cleaned) == 1


def test_cleanup_error_fails_closed_after_result_execution() -> None:
    planner = _Planner()

    def fail_cleanup(command: ExecutePlugin) -> None:
        del command
        raise OSError("cleanup unavailable")

    planner.cleanup = fail_cleanup  # type: ignore[method-assign]
    handler = PluginAttemptHandler(
        planner=cast(PluginExecutionPlanner, planner),
        execution=cast(
            PluginExecutionService,
            _Execution(ResultStatus.SUCCEEDED),
        ),
        committer=_Committer(),
    )

    with pytest.raises(OSError, match="cleanup unavailable"):
        asyncio.run(handler.execute(cast(ClaimedAttempt, object()), asyncio.Event()))

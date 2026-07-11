import asyncio

import pytest
from cmp.apps.worker import EmptyWorker


def test_empty_worker_runs_one_idle_cycle() -> None:
    result = asyncio.run(EmptyWorker(poll_interval_seconds=0.01).run_once())

    assert result.status == "idle"
    assert result.handlers_registered == 0


def test_empty_worker_rejects_non_positive_interval() -> None:
    with pytest.raises(ValueError, match="must be positive"):
        EmptyWorker(poll_interval_seconds=0)


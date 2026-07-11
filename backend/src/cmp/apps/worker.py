"""Empty worker process shell for validating deployment and lifecycle behavior."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from collections.abc import Sequence
from dataclasses import asdict, dataclass

from cmp import __version__
from cmp.bootstrap.settings import Settings

LOGGER = logging.getLogger("cmp.worker")


@dataclass(frozen=True, slots=True)
class WorkerCycleResult:
    """Result of one empty worker polling cycle."""

    status: str = "idle"
    service: str = "cmp-worker"
    version: str = __version__
    handlers_registered: int = 0


class EmptyWorker:
    """Lifecycle shell that intentionally contains no domain job handlers."""

    def __init__(self, poll_interval_seconds: float = 1.0) -> None:
        if poll_interval_seconds <= 0:
            raise ValueError("poll_interval_seconds must be positive")
        self._poll_interval_seconds = poll_interval_seconds
        self._stop = asyncio.Event()

    async def run_once(self) -> WorkerCycleResult:
        """Perform one no-op poll to prove that the worker can start."""

        await asyncio.sleep(0)
        return WorkerCycleResult()

    async def serve(self) -> None:
        """Remain alive until cancellation while performing empty poll cycles."""

        LOGGER.info("worker_started", extra={"version": __version__})
        try:
            while not self._stop.is_set():
                await self.run_once()
                try:
                    await asyncio.wait_for(
                        self._stop.wait(), timeout=self._poll_interval_seconds
                    )
                except TimeoutError:
                    continue
        finally:
            LOGGER.info("worker_stopped")

    def stop(self) -> None:
        self._stop.set()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the empty CMP worker shell.")
    parser.add_argument("--once", action="store_true", help="Run one cycle and exit.")
    parser.add_argument("--json", action="store_true", help="Print the cycle result as JSON.")
    parser.add_argument("--poll-interval", type=float, default=None)
    return parser


async def _run(args: argparse.Namespace) -> int:
    settings = Settings.from_environment()
    interval = args.poll_interval or settings.worker_poll_interval_seconds
    worker = EmptyWorker(poll_interval_seconds=interval)
    if args.once:
        result = await worker.run_once()
        if args.json:
            print(json.dumps(asdict(result), sort_keys=True))
        else:
            print(f"{result.service}: {result.status} ({result.handlers_registered} handlers)")
        return 0

    try:
        await worker.serve()
    except asyncio.CancelledError:
        worker.stop()
        raise
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point that is testable without starting a permanent process."""

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    args = _parser().parse_args(argv)
    try:
        return asyncio.run(_run(args))
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())


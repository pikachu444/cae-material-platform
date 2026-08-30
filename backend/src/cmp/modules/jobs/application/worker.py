"""Public application boundary for authorized durable worker queues."""

from cmp.modules.jobs.adapters.worker.queue import AuthorizedJobWorkerQueue

__all__ = ["AuthorizedJobWorkerQueue"]

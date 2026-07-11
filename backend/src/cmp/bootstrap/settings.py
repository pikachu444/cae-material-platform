"""Small environment-backed settings object for the foundation deployables."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Settings:
    """Runtime settings that do not contain secrets."""

    environment: str = "development"
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    worker_poll_interval_seconds: float = 1.0

    @classmethod
    def from_environment(cls) -> Settings:
        """Build settings from the documented CMP_* environment variables."""

        return cls(
            environment=os.getenv("CMP_ENVIRONMENT", "development"),
            api_host=os.getenv("CMP_API_HOST", "127.0.0.1"),
            api_port=int(os.getenv("CMP_API_PORT", "8000")),
            worker_poll_interval_seconds=float(
                os.getenv("CMP_WORKER_POLL_INTERVAL_SECONDS", "1.0")
            ),
        )


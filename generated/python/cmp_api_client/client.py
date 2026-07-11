"""Generated from contracts/http/openapi.yaml; do not edit manually."""

from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.request import Request, urlopen


@dataclass(frozen=True, slots=True)
class HealthResponse:
    status: str
    service: str
    version: str


class Client:
    def __init__(self, base_url: str, timeout_seconds: float = 5.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds

    def get_health(self) -> HealthResponse:
        request = Request(self._base_url + "/api/v1/health", method="GET")
        with urlopen(request, timeout=self._timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("health response must be a JSON object")
        return HealthResponse(
            status=str(payload["status"]),
            service=str(payload["service"]),
            version=str(payload["version"]),
        )

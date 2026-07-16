"""Low-cardinality process metrics used by the in-product operations dashboard."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import UTC, datetime

_LATENCY_BUCKETS_MS = (5, 10, 25, 50, 75, 100, 250, 500, 750, 1_000, 2_500, 5_000, 10_000)
_KNOWN_METHODS = frozenset(
    {"CONNECT", "DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT", "TRACE"}
)


@dataclass(frozen=True, slots=True)
class OperationSeries:
    method: str
    route: str
    status_family: str
    request_count: int
    error_count: int
    duration_sum_ms: float
    p95_upper_bound_ms: int


@dataclass(frozen=True, slots=True)
class OperationalSnapshot:
    started_at: datetime
    observed_at: datetime
    active_requests: int
    request_count: int
    error_count: int
    series: tuple[OperationSeries, ...]


@dataclass(slots=True)
class _MutableSeries:
    request_count: int
    error_count: int
    duration_sum_ms: float
    buckets: list[int]


class OperationalMetrics:
    """A bounded local projection; telemetry backends remain authoritative across replicas."""

    def __init__(self, *, max_routes: int = 256) -> None:
        if not 1 <= max_routes <= 1_024:
            raise ValueError("max_routes must be between 1 and 1024")
        self._started_at = datetime.now(UTC)
        self._max_routes = max_routes
        self._lock = threading.Lock()
        self._active = 0
        self._series: dict[tuple[str, str, str], _MutableSeries] = {}
        self._routes: set[str] = set()

    def start_request(self) -> None:
        with self._lock:
            self._active += 1

    def finish_request(
        self,
        *,
        method: str,
        route: str | None,
        status_code: int,
        duration_ms: float,
    ) -> None:
        bounded_method = method if method in _KNOWN_METHODS else "_OTHER"
        bounded_route = (
            route if route and route.startswith("/") and len(route) <= 255 else "unmatched"
        )
        family = f"{status_code // 100}xx" if 100 <= status_code <= 599 else "error"
        with self._lock:
            self._active = max(0, self._active - 1)
            if bounded_route not in self._routes:
                if len(self._routes) >= self._max_routes:
                    bounded_route = "other"
                else:
                    self._routes.add(bounded_route)
            key = (bounded_method, bounded_route, family)
            mutable = self._series.get(key)
            if mutable is None:
                mutable = _MutableSeries(0, 0, 0.0, [0] * len(_LATENCY_BUCKETS_MS))
                self._series[key] = mutable
            mutable.request_count += 1
            mutable.error_count += int(status_code >= 500)
            mutable.duration_sum_ms += max(0.0, duration_ms)
            for index, upper in enumerate(_LATENCY_BUCKETS_MS):
                if duration_ms <= upper:
                    mutable.buckets[index] += 1

    def snapshot(self) -> OperationalSnapshot:
        with self._lock:
            rows: list[OperationSeries] = []
            for (method, route, family), value in sorted(self._series.items()):
                threshold = max(1, (value.request_count * 95 + 99) // 100)
                upper = _LATENCY_BUCKETS_MS[-1]
                for index, count in enumerate(value.buckets):
                    if count >= threshold:
                        upper = _LATENCY_BUCKETS_MS[index]
                        break
                rows.append(
                    OperationSeries(
                        method,
                        route,
                        family,
                        value.request_count,
                        value.error_count,
                        round(value.duration_sum_ms, 3),
                        upper,
                    )
                )
            return OperationalSnapshot(
                self._started_at,
                datetime.now(UTC),
                self._active,
                sum(item.request_count for item in rows),
                sum(item.error_count for item in rows),
                tuple(rows),
            )

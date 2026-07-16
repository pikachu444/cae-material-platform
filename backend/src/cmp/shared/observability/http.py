"""HTTP request instrumentation that never records URLs, headers, queries, or bodies."""

from __future__ import annotations

import logging
from time import perf_counter

from fastapi import Request
from opentelemetry import trace
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from cmp.shared.observability.metrics import OperationalMetrics

LOGGER = logging.getLogger("cmp.http")


def _route_template(request: Request) -> str | None:
    route = request.scope.get("route")
    path = getattr(route, "path", None)
    return path if isinstance(path, str) else None


class HttpObservabilityMiddleware(BaseHTTPMiddleware):
    """Record one low-cardinality observation after FastAPI resolves the route template."""

    def __init__(self, app: object, metrics: OperationalMetrics) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self._metrics = metrics

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        self._metrics.start_request()
        started = perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            span_context = trace.get_current_span().get_span_context()
            if span_context.is_valid:
                response.headers["traceparent"] = (
                    f"00-{span_context.trace_id:032x}-{span_context.span_id:016x}-01"
                )
            return response
        finally:
            elapsed_ms = (perf_counter() - started) * 1_000
            route = _route_template(request)
            self._metrics.finish_request(
                method=request.method,
                route=route,
                status_code=status_code,
                duration_ms=elapsed_ms,
            )
            LOGGER.info(
                "http.server.request",
                extra={
                    "http_method": request.method if request.method else "_OTHER",
                    "http_route": route or "unmatched",
                    "http_status_code": status_code,
                    "duration_ms": round(elapsed_ms, 3),
                },
            )

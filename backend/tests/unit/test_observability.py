import asyncio
import json
import logging
from io import StringIO

import httpx
from cmp.apps.api import create_app
from cmp.bootstrap.settings import Settings
from cmp.shared.observability.logging import RedactingJsonFormatter, redact_text
from cmp.shared.observability.metrics import OperationalMetrics


def test_redaction_removes_bearer_jwt_uri_and_named_secrets() -> None:
    sensitive = (
        "authorization=Bearer abc.def.ghi "
        "password=hunter2 database_url=postgresql://owner:secret@db/cmp "
        "token=eyJabcdefghijk.abcdefghijk.abcdefghijk"
    )

    redacted = redact_text(sensitive)

    assert "hunter2" not in redacted
    assert "owner:secret" not in redacted
    assert "eyJabcdefghijk" not in redacted
    assert "Bearer abc" not in redacted
    assert redacted.count("[REDACTED]") >= 4


def test_json_formatter_allowlists_fields_and_never_emits_exception_message() -> None:
    stream = StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(RedactingJsonFormatter("cmp-test"))
    logger = logging.getLogger("cmp.test.redaction")
    logger.handlers = [handler]
    logger.propagate = False
    logger.setLevel(logging.INFO)

    try:
        raise RuntimeError("password=fixture-secret raw payload")
    except RuntimeError:
        logger.exception(
            "job_handler_failed",
            extra={"job_id": "job-1", "unapproved_payload": "do-not-emit"},
        )

    document = json.loads(stream.getvalue())
    assert document["event"] == "job_handler_failed"
    assert document["error_type"] == "RuntimeError"
    assert document["job_id"] == "job-1"
    assert "unapproved_payload" not in document
    assert "fixture-secret" not in stream.getvalue()
    assert "raw payload" not in stream.getvalue()


def test_operational_metrics_use_route_templates_and_bound_cardinality() -> None:
    metrics = OperationalMetrics(max_routes=1)
    for route, duration, status in (
        ("/api/v1/materials/{material_id}", 12.0, 200),
        ("/api/v1/materials/{material_id}", 30.0, 503),
        ("/api/v1/another/{id}", 8.0, 200),
    ):
        metrics.start_request()
        metrics.finish_request(
            method="GET",
            route=route,
            status_code=status,
            duration_ms=duration,
        )

    snapshot = metrics.snapshot()
    assert snapshot.active_requests == 0
    assert snapshot.request_count == 3
    assert snapshot.error_count == 1
    assert {series.route for series in snapshot.series} == {
        "/api/v1/materials/{material_id}",
        "other",
    }
    assert all("another" not in series.route for series in snapshot.series)


def test_health_emits_trace_context_and_operations_requires_authentication() -> None:
    async def request() -> tuple[httpx.Response, httpx.Response]:
        app = create_app(Settings(environment="test"))
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            health = await client.get(
                "/api/v1/health",
                headers={
                    "traceparent": "00-11111111111111111111111111111111-2222222222222222-01"
                },
            )
            protected = await client.get("/api/v1/operations/observability")
            return health, protected

    health, protected = asyncio.run(request())

    assert health.status_code == 200
    assert health.headers["traceparent"].startswith(
        "00-11111111111111111111111111111111-"
    )
    assert protected.status_code in {401, 503}
    assert "query" not in health.headers["traceparent"]

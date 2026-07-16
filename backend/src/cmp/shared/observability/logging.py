"""Structured allow-list logging with fail-closed secret redaction."""

from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime
from typing import Final

from opentelemetry import trace

_SAFE_EVENT: Final = re.compile(r"^[a-z][a-z0-9_.-]{0,99}$")
_BEARER: Final = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]+")
_JWT: Final = re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b")
_URI_CREDENTIAL: Final = re.compile(r"(?P<scheme>[a-z][a-z0-9+.-]*://)[^/@\s:]+:[^@\s]+@", re.I)
_NAMED_SECRET: Final = re.compile(
    r"(?i)\b(authorization|cookie|database_url|dsn|password|secret|token)\b"
    r"\s*([=:])\s*([^\s,;]+)"
)
_ALLOWED_EXTRA: Final = (
    "active_requests",
    "attempt_id",
    "duration_ms",
    "error_type",
    "handlers_registered",
    "http_method",
    "http_route",
    "http_status_code",
    "job_id",
    "job_type",
    "outcome",
    "request_id",
    "version",
)


def redact_text(value: str) -> str:
    """Redact known credential shapes without trying to preserve secret fragments."""

    redacted = _BEARER.sub("Bearer [REDACTED]", value)
    redacted = _JWT.sub("[REDACTED]", redacted)
    redacted = _URI_CREDENTIAL.sub(r"\g<scheme>[REDACTED]@", redacted)
    return _NAMED_SECRET.sub(r"\1\2[REDACTED]", redacted)


def _safe_scalar(value: object) -> str | int | float | bool | None:
    if value is None or isinstance(value, (int, float, bool)):
        return value
    return redact_text(str(value))[:512]


class RedactingJsonFormatter(logging.Formatter):
    """Emit only bounded fields; exception messages and arbitrary extras are excluded."""

    def __init__(self, service_name: str) -> None:
        super().__init__()
        self._service_name = service_name

    def format(self, record: logging.LogRecord) -> str:
        message = record.msg if isinstance(record.msg, str) else "unstructured_log"
        event = message if _SAFE_EVENT.fullmatch(message) else "unstructured_log"
        document: dict[str, str | int | float | bool | None] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "severity": record.levelname,
            "service": self._service_name,
            "event": event,
        }
        span = trace.get_current_span().get_span_context()
        if span.is_valid:
            document["trace_id"] = f"{span.trace_id:032x}"
            document["span_id"] = f"{span.span_id:016x}"
        for name in _ALLOWED_EXTRA:
            if hasattr(record, name):
                document[name] = _safe_scalar(getattr(record, name))
        if record.exc_info is not None and record.exc_info[0] is not None:
            document["error_type"] = record.exc_info[0].__name__
        return json.dumps(document, separators=(",", ":"), sort_keys=True)


def configure_structured_logging(service_name: str) -> None:
    """Install one process-local CMP handler without changing third-party loggers."""

    logger = logging.getLogger("cmp")
    logger.setLevel(logging.INFO)
    for handler in logger.handlers:
        if isinstance(handler.formatter, RedactingJsonFormatter):
            handler.setFormatter(RedactingJsonFormatter(service_name))
            return
    handler = logging.StreamHandler()
    handler.setFormatter(RedactingJsonFormatter(service_name))
    logger.addHandler(handler)
    logger.propagate = False

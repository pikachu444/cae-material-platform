"""Auditor-protected process snapshot for the in-product operations dashboard."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Annotated

from fastapi import Depends, FastAPI, Response
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from cmp import __version__
from cmp.shared.observability.metrics import OperationalMetrics, OperationSeries

type Dependency = Callable[..., object]
type RouteLabel = Annotated[str, StringConstraints(min_length=1, max_length=255)]


class OperationSeriesResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    method: Annotated[str, StringConstraints(pattern=r"^(_OTHER|[A-Z]+)$")]
    route: RouteLabel
    status_family: Annotated[str, StringConstraints(pattern=r"^([1-5]xx|error)$")]
    request_count: Annotated[int, Field(ge=1)]
    error_count: Annotated[int, Field(ge=0)]
    duration_sum_ms: Annotated[float, Field(ge=0)]
    p95_upper_bound_ms: Annotated[int, Field(ge=1)]

    @classmethod
    def from_series(cls, value: OperationSeries) -> OperationSeriesResponse:
        return cls(
            method=value.method,
            route=value.route,
            status_family=value.status_family,
            request_count=value.request_count,
            error_count=value.error_count,
            duration_sum_ms=value.duration_sum_ms,
            p95_upper_bound_ms=value.p95_upper_bound_ms,
        )


class OperationalSnapshotResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    service: Annotated[str, StringConstraints(pattern=r"^cmp-api$")]
    version: RouteLabel
    started_at: datetime
    observed_at: datetime
    active_requests: Annotated[int, Field(ge=0)]
    request_count: Annotated[int, Field(ge=0)]
    error_count: Annotated[int, Field(ge=0)]
    series: tuple[OperationSeriesResponse, ...]


def install_operations_api(
    application: FastAPI,
    *,
    metrics: OperationalMetrics,
    security_dependency: Dependency,
    read_dependency: Dependency,
) -> None:
    @application.get(
        "/api/v1/operations/observability",
        operation_id="getOperationalObservability",
        response_model=OperationalSnapshotResponse,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["operations"],
        summary="Read a redacted, low-cardinality process observability snapshot.",
    )
    def get_observability(response: Response) -> OperationalSnapshotResponse:
        snapshot = metrics.snapshot()
        response.headers["Cache-Control"] = "no-store"
        return OperationalSnapshotResponse(
            service="cmp-api",
            version=__version__,
            started_at=snapshot.started_at,
            observed_at=snapshot.observed_at,
            active_requests=snapshot.active_requests,
            request_count=snapshot.request_count,
            error_count=snapshot.error_count,
            series=tuple(OperationSeriesResponse.from_series(row) for row in snapshot.series),
        )

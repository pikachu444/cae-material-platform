"""Protected HTTP API for P0-2 multi-replicate Statistics/QC."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends, FastAPI, Query, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from cmp.modules.datasets.contracts import CurveMetadataResponse, CurveSeriesPreviewResponse
from cmp.modules.identity_access.domain.authorization import DataClassification
from cmp.modules.statistics.adapters.api.statistics import (
    QcObservationResponse,
    StatisticsProblem,
    _etag,
    _scope,
    _translate,
    _unavailable,
)
from cmp.modules.statistics.application.replicate_service import (
    CreateReferenceTensileReplicateStatisticalPlan,
    ExecuteReferenceTensileReplicateStatistics,
    ReplicateRevisionSnapshot,
    ReplicateStatisticalPlanSnapshot,
    ReplicateStatisticalResultSnapshot,
    ReplicateStatisticalRun,
    ReplicateStatisticsService,
)
from cmp.modules.statistics.domain.reference_tensile_pair import StatisticalRunStatus
from cmp.modules.statistics.domain.reference_tensile_replicates import (
    REFERENCE_TENSILE_REPLICATE_CI_METHOD,
    REFERENCE_TENSILE_REPLICATE_GRID_POLICY,
    REFERENCE_TENSILE_REPLICATE_PLAN_KIND,
    REFERENCE_TENSILE_REPLICATE_QUANTILE_METHOD,
    REFERENCE_TENSILE_REPLICATE_SCALAR_FEATURE,
    ReferenceTensileReplicatePlanContent,
    ReferenceTensileReplicateResultContent,
    ReplicateCurvePoint,
    ReplicateScalarStatistics,
)
from cmp.shared.contracts.revisions import RevisionMetadataResponse

type Dependency = Callable[..., object]
type Reason = Annotated[str, StringConstraints(min_length=1, max_length=2000)]


class CreateReplicateStatisticalPlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    classification: DataClassification
    plan_label: Annotated[str, StringConstraints(min_length=1, max_length=160)]
    selection_id: UUID
    selection_revision_id: UUID
    sample_count: Annotated[int, Field(ge=2, le=50)]
    change_reason: Reason

    def to_domain(self) -> ReferenceTensileReplicatePlanContent:
        return ReferenceTensileReplicatePlanContent(
            plan_label=self.plan_label,
            selection_id=self.selection_id,
            selection_revision_id=self.selection_revision_id,
            sample_count=self.sample_count,
        )


class ExecuteReplicateStatisticsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_id: UUID
    plan_revision_id: UUID
    change_reason: Reason


class ReplicatePlanContentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_kind: str
    selection_id: UUID
    selection_revision_id: UUID
    sample_count: int
    required_input_representation: str
    scalar_feature: str
    curve_grid_policy: str
    quantile_method: str
    confidence_interval_method: str
    curve_output_schema_ref: str

    @classmethod
    def from_domain(
        cls, value: ReferenceTensileReplicatePlanContent
    ) -> ReplicatePlanContentResponse:
        return cls(
            plan_kind=REFERENCE_TENSILE_REPLICATE_PLAN_KIND,
            selection_id=value.selection_id,
            selection_revision_id=value.selection_revision_id,
            sample_count=value.sample_count,
            required_input_representation="processed",
            scalar_feature=REFERENCE_TENSILE_REPLICATE_SCALAR_FEATURE,
            curve_grid_policy=REFERENCE_TENSILE_REPLICATE_GRID_POLICY,
            quantile_method=REFERENCE_TENSILE_REPLICATE_QUANTILE_METHOD,
            confidence_interval_method=REFERENCE_TENSILE_REPLICATE_CI_METHOD,
            curve_output_schema_ref=value.curve_output_schema_ref,
        )


class ReplicatePlanRevisionResponse(RevisionMetadataResponse):
    content: ReplicatePlanContentResponse

    @classmethod
    def from_snapshot(
        cls, value: ReplicateRevisionSnapshot[ReferenceTensileReplicatePlanContent]
    ) -> ReplicatePlanRevisionResponse:
        metadata = RevisionMetadataResponse.from_record(value.record, "draft")
        return cls(
            **metadata.model_dump(), content=ReplicatePlanContentResponse.from_domain(value.content)
        )


class ReplicateStatisticalPlanResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    statistical_plan_id: UUID
    plan_label: str
    current_revision: ReplicatePlanRevisionResponse
    links: dict[str, str]

    @classmethod
    def from_snapshot(
        cls, value: ReplicateStatisticalPlanSnapshot
    ) -> ReplicateStatisticalPlanResponse:
        root = f"/api/v1/replicate-statistical-plans/{value.id}"
        return cls(
            statistical_plan_id=value.id,
            plan_label=value.current.content.plan_label,
            current_revision=ReplicatePlanRevisionResponse.from_snapshot(value.current),
            links={"self": root, "runs": "/api/v1/replicate-statistical-runs"},
        )


class ReplicateStatisticalPlanListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: tuple[ReplicateStatisticalPlanResponse, ...]


class ReplicateRunMemberResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ordinal: int
    dataset_id: UUID
    dataset_revision_id: UUID
    test_run_id: UUID
    test_run_revision_id: UUID


class ReplicateStatisticalRunResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    statistical_run_id: UUID
    classification: DataClassification
    execution_mode: str
    status: StatisticalRunStatus
    plan_id: UUID
    plan_revision_id: UUID
    selection_id: UUID
    selection_revision_id: UUID
    sample_count: int
    members: tuple[ReplicateRunMemberResponse, ...]
    result_id: UUID | None
    result_revision_id: UUID | None
    curve_artifact_id: UUID | None
    curve_sha256: str | None
    curve_point_count: int | None
    failure_code: str | None
    qc_observations: tuple[QcObservationResponse, ...]
    change_reason: str
    started_at: str
    ended_at: str | None
    links: dict[str, str]

    @classmethod
    def from_domain(cls, value: ReplicateStatisticalRun) -> ReplicateStatisticalRunResponse:
        return cls(
            statistical_run_id=value.id,
            classification=value.classification,
            execution_mode="committed",
            status=value.status,
            plan_id=value.plan_id,
            plan_revision_id=value.plan_revision_id,
            selection_id=value.selection_id,
            selection_revision_id=value.selection_revision_id,
            sample_count=value.sample_count,
            members=tuple(
                ReplicateRunMemberResponse(
                    ordinal=item.ordinal,
                    dataset_id=item.dataset_id,
                    dataset_revision_id=item.dataset_revision_id,
                    test_run_id=item.test_run_id,
                    test_run_revision_id=item.test_run_revision_id,
                )
                for item in value.members
            ),
            result_id=value.result_id,
            result_revision_id=value.result_revision_id,
            curve_artifact_id=value.curve_artifact_id,
            curve_sha256=value.curve_sha256,
            curve_point_count=value.curve_point_count,
            failure_code=value.failure_code,
            qc_observations=tuple(
                QcObservationResponse.from_domain(item) for item in value.qc_observations
            ),
            change_reason=value.change_reason,
            started_at=value.started_at.isoformat(),
            ended_at=value.ended_at.isoformat() if value.ended_at else None,
            links={
                "self": f"/api/v1/replicate-statistical-runs/{value.id}",
                **(
                    {"result": f"/api/v1/replicate-statistical-results/{value.result_id}"}
                    if value.result_id is not None
                    else {}
                ),
            },
        )


class ReplicateScalarStatisticsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sample_count: int
    mean: float
    sample_standard_deviation: float
    median: float
    median_absolute_deviation: float
    interquartile_range: float
    minimum: float
    maximum: float
    coefficient_of_variation: float | None
    mean_confidence_interval_lower_95: float
    mean_confidence_interval_upper_95: float

    @classmethod
    def from_domain(cls, value: ReplicateScalarStatistics) -> ReplicateScalarStatisticsResponse:
        return cls(**{field: getattr(value, field) for field in cls.model_fields})


class ReplicateStatisticalResultResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    statistical_result_id: UUID
    current_revision: RevisionMetadataResponse
    statistical_run_id: UUID
    plan_id: UUID
    plan_revision_id: UUID
    selection_id: UUID
    selection_revision_id: UUID
    curve_artifact_id: UUID
    curve_sha256: str
    curve_point_count: int
    peak_engineering_stress_pa: ReplicateScalarStatisticsResponse
    methods: dict[str, str]
    links: dict[str, str]

    @classmethod
    def from_snapshot(
        cls, value: ReplicateStatisticalResultSnapshot
    ) -> ReplicateStatisticalResultResponse:
        content: ReferenceTensileReplicateResultContent = value.current.content
        return cls(
            statistical_result_id=value.id,
            current_revision=RevisionMetadataResponse.from_record(value.current.record, "draft"),
            statistical_run_id=content.statistical_run_id,
            plan_id=content.plan_id,
            plan_revision_id=content.plan_revision_id,
            selection_id=content.selection_id,
            selection_revision_id=content.selection_revision_id,
            curve_artifact_id=content.curve_artifact_id,
            curve_sha256=content.curve_sha256,
            curve_point_count=content.curve_point_count,
            peak_engineering_stress_pa=ReplicateScalarStatisticsResponse.from_domain(
                content.peak_engineering_stress_pa
            ),
            methods={
                "grid": REFERENCE_TENSILE_REPLICATE_GRID_POLICY,
                "quantile": REFERENCE_TENSILE_REPLICATE_QUANTILE_METHOD,
                "confidence_interval": REFERENCE_TENSILE_REPLICATE_CI_METHOD,
            },
            links={
                "self": f"/api/v1/replicate-statistical-results/{value.id}",
                "curve_artifact": f"/api/v1/artifacts/{content.curve_artifact_id}/content",
            },
        )


class ReplicateCurvePointResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    engineering_strain: float
    statistics: ReplicateScalarStatisticsResponse

    @classmethod
    def from_domain(cls, value: ReplicateCurvePoint) -> ReplicateCurvePointResponse:
        return cls(
            engineering_strain=value.engineering_strain,
            statistics=ReplicateScalarStatisticsResponse.from_domain(value.stress),
        )


class ReplicateResultCurveResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    result_id: UUID
    grid_policy: str
    points: tuple[ReplicateCurvePointResponse, ...]
    curve_metadata: CurveMetadataResponse
    curve_series: CurveSeriesPreviewResponse


def install_replicate_statistics_api(
    application: FastAPI,
    *,
    service: ReplicateStatisticsService | None,
    security_dependency: Dependency,
    read_dependency: Dependency,
    execute_dependency: Dependency,
) -> None:
    errors: dict[int | str, dict[str, Any]] = {
        401: {"description": "Authentication required."},
        403: {"model": StatisticsProblem},
        404: {"model": StatisticsProblem},
        409: {"model": StatisticsProblem},
        422: {"model": StatisticsProblem},
        503: {"model": StatisticsProblem},
    }

    @application.post(
        "/api/v1/replicate-statistical-plans",
        operation_id="createReferenceTensileReplicateStatisticalPlan",
        response_model=ReplicateStatisticalPlanResponse,
        status_code=status.HTTP_201_CREATED,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(execute_dependency)],
        tags=["statistics"],
    )
    def create_plan(
        request: Request, response: Response, body: CreateReplicateStatisticalPlanRequest
    ) -> ReplicateStatisticalPlanResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            result = service.create_plan(
                context,
                decision,
                CreateReferenceTensileReplicateStatisticalPlan(
                    classification=body.classification,
                    content=body.to_domain(),
                    change_reason=body.change_reason,
                ),
            )
        except Exception as error:
            raise _translate(context, error) from error
        response.headers["Location"] = f"/api/v1/replicate-statistical-plans/{result.id}"
        _etag(response, result.current.record)
        return ReplicateStatisticalPlanResponse.from_snapshot(result)

    @application.get(
        "/api/v1/replicate-statistical-plans",
        operation_id="listReferenceTensileReplicateStatisticalPlans",
        response_model=ReplicateStatisticalPlanListResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["statistics"],
    )
    def list_plans(
        request: Request,
        selection_revision_id: UUID,
        limit: Annotated[int, Query(ge=1, le=200)] = 100,
    ) -> ReplicateStatisticalPlanListResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            items = service.list_plans(context, decision, selection_revision_id, limit=limit)
        except Exception as error:
            raise _translate(context, error) from error
        return ReplicateStatisticalPlanListResponse(
            items=tuple(ReplicateStatisticalPlanResponse.from_snapshot(item) for item in items)
        )

    @application.get(
        "/api/v1/replicate-statistical-plans/{plan_id}",
        operation_id="getReferenceTensileReplicateStatisticalPlan",
        response_model=ReplicateStatisticalPlanResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["statistics"],
    )
    def get_plan(
        request: Request, response: Response, plan_id: UUID
    ) -> ReplicateStatisticalPlanResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            result = service.get_plan(context, decision, plan_id)
        except Exception as error:
            raise _translate(context, error) from error
        _etag(response, result.current.record)
        return ReplicateStatisticalPlanResponse.from_snapshot(result)

    @application.post(
        "/api/v1/replicate-statistical-runs",
        operation_id="executeReferenceTensileReplicateStatistics",
        response_model=ReplicateStatisticalRunResponse,
        status_code=status.HTTP_201_CREATED,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(execute_dependency)],
        tags=["statistics"],
    )
    async def execute(
        request: Request, response: Response, body: ExecuteReplicateStatisticsRequest
    ) -> ReplicateStatisticalRunResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            result = await service.execute(
                context,
                decision,
                ExecuteReferenceTensileReplicateStatistics(
                    plan_id=body.plan_id,
                    plan_revision_id=body.plan_revision_id,
                    change_reason=body.change_reason,
                ),
            )
        except Exception as error:
            raise _translate(context, error) from error
        response.headers["Location"] = f"/api/v1/replicate-statistical-runs/{result.id}"
        response.headers["Cache-Control"] = "no-store"
        return ReplicateStatisticalRunResponse.from_domain(result)

    @application.get(
        "/api/v1/replicate-statistical-runs/{run_id}",
        operation_id="getReferenceTensileReplicateStatisticalRun",
        response_model=ReplicateStatisticalRunResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["statistics"],
    )
    def get_run(request: Request, run_id: UUID) -> ReplicateStatisticalRunResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            result = service.get_run(context, decision, run_id)
        except Exception as error:
            raise _translate(context, error) from error
        return ReplicateStatisticalRunResponse.from_domain(result)

    @application.get(
        "/api/v1/replicate-statistical-results/{result_id}",
        operation_id="getReferenceTensileReplicateStatisticalResult",
        response_model=ReplicateStatisticalResultResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["statistics"],
    )
    def get_result(
        request: Request, response: Response, result_id: UUID
    ) -> ReplicateStatisticalResultResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            result = service.get_result(context, decision, result_id)
        except Exception as error:
            raise _translate(context, error) from error
        _etag(response, result.current.record)
        return ReplicateStatisticalResultResponse.from_snapshot(result)

    @application.get(
        "/api/v1/replicate-statistical-results/{result_id}/curve",
        operation_id="previewReferenceTensileReplicateStatisticalResultCurve",
        response_model=ReplicateResultCurveResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["statistics"],
    )
    async def preview_curve(
        request: Request,
        result_id: UUID,
        maximum_points: Annotated[int, Query(ge=2, le=10_000)] = 1000,
    ) -> ReplicateResultCurveResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            preview = await service.preview_result_curve(
                context, decision, result_id, maximum_points=maximum_points
            )
        except Exception as error:
            raise _translate(context, error) from error
        return ReplicateResultCurveResponse(
            result_id=result_id,
            grid_policy=REFERENCE_TENSILE_REPLICATE_GRID_POLICY,
            points=tuple(
                ReplicateCurvePointResponse.from_domain(item) for item in preview.points
            ),
            curve_metadata=CurveMetadataResponse.from_domain(preview.metadata),
            curve_series=CurveSeriesPreviewResponse.from_domain(preview.series),
        )

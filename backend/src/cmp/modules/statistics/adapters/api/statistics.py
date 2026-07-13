"""Protected HTTP resources for the reference two-sample Statistics/QC workflow."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends, FastAPI, Query, Request, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from sqlalchemy.exc import IntegrityError

from cmp.modules.artifacts.domain.content import (
    ArtifactAccessDenied,
    ArtifactError,
    ArtifactIntegrityError,
    ArtifactNotFound,
    InvalidArtifact,
)
from cmp.modules.datasets.domain.reference_tensile import DatasetError, DatasetNotFound
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.statistics.application.service import (
    CreateReferenceTensilePairPlan,
    ExecuteReferenceTensilePairStatistics,
    ReviseReferenceTensilePairPlan,
    RevisionSnapshot,
    StatisticalPlanSnapshot,
    StatisticalResultSnapshot,
    StatisticalRun,
    StatisticsService,
)
from cmp.modules.statistics.domain.reference_tensile_pair import (
    REFERENCE_TENSILE_PAIR_ASSUMPTION_PROFILE,
    REFERENCE_TENSILE_PAIR_CI_STATUS,
    REFERENCE_TENSILE_PAIR_CURVE_SCHEMA,
    REFERENCE_TENSILE_PAIR_GRID_POLICY,
    REFERENCE_TENSILE_PAIR_PLAN_KIND,
    REFERENCE_TENSILE_PAIR_QUANTILE_METHOD,
    REFERENCE_TENSILE_PAIR_SCALAR_FEATURE,
    InvalidStatisticsRequest,
    QcObservation,
    QcOutcome,
    ReferenceTensilePairCurvePoint,
    ReferenceTensilePairPlanContent,
    ReferenceTensilePairResultContent,
    ReferenceTensilePairScalarStatistics,
    StatisticalRunStatus,
    StatisticsConflict,
    StatisticsError,
    StatisticsNotFound,
)
from cmp.shared.contracts.revisions import RevisionETag, RevisionMetadataResponse
from cmp.shared.domain.revisions import RevisionKernelError, RevisionRecord

type Label = Annotated[str, StringConstraints(min_length=1, max_length=255)]
type Dependency = Callable[..., object]


class ReferenceTensilePairPlanInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_label: Annotated[str, StringConstraints(min_length=1, max_length=160)]
    first_selection_id: UUID
    first_selection_revision_id: UUID
    second_selection_id: UUID
    second_selection_revision_id: UUID

    def to_domain(self) -> ReferenceTensilePairPlanContent:
        return ReferenceTensilePairPlanContent(
            plan_label=self.plan_label,
            first_selection_id=self.first_selection_id,
            first_selection_revision_id=self.first_selection_revision_id,
            second_selection_id=self.second_selection_id,
            second_selection_revision_id=self.second_selection_revision_id,
        )


class CreateReferenceTensilePairPlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    classification: DataClassification
    content: ReferenceTensilePairPlanInput
    change_reason: Annotated[str, StringConstraints(min_length=1, max_length=2000)]


class ReviseReferenceTensilePairPlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_current_revision_id: UUID
    plan_label: Annotated[str, StringConstraints(min_length=1, max_length=160)]
    first_selection_id: UUID
    first_selection_revision_id: UUID
    second_selection_id: UUID
    second_selection_revision_id: UUID
    change_reason: Annotated[str, StringConstraints(min_length=1, max_length=2000)]

    def to_content(self) -> ReferenceTensilePairPlanContent:
        return ReferenceTensilePairPlanContent(
            plan_label=self.plan_label,
            first_selection_id=self.first_selection_id,
            first_selection_revision_id=self.first_selection_revision_id,
            second_selection_id=self.second_selection_id,
            second_selection_revision_id=self.second_selection_revision_id,
        )


class ExecuteReferenceTensilePairStatisticsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_id: UUID
    plan_revision_id: UUID
    change_reason: Annotated[str, StringConstraints(min_length=1, max_length=2000)]


class ReferenceTensilePairPlanContentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_kind: str
    sample_count: int
    first_selection_id: UUID
    first_selection_revision_id: UUID
    second_selection_id: UUID
    second_selection_revision_id: UUID
    input_schema_ref: str
    scalar_feature: str
    curve_grid_policy: str
    assumption_profile: str
    quantile_method: str
    confidence_interval_status: str
    curve_output_schema_ref: str

    @classmethod
    def from_domain(
        cls, value: ReferenceTensilePairPlanContent
    ) -> ReferenceTensilePairPlanContentResponse:
        return cls(
            plan_kind=REFERENCE_TENSILE_PAIR_PLAN_KIND,
            sample_count=2,
            first_selection_id=value.first_selection_id,
            first_selection_revision_id=value.first_selection_revision_id,
            second_selection_id=value.second_selection_id,
            second_selection_revision_id=value.second_selection_revision_id,
            input_schema_ref="urn:cmp:datasets:reference-tensile-normalized-parquet:1.0.0",
            scalar_feature=REFERENCE_TENSILE_PAIR_SCALAR_FEATURE,
            curve_grid_policy=REFERENCE_TENSILE_PAIR_GRID_POLICY,
            assumption_profile=REFERENCE_TENSILE_PAIR_ASSUMPTION_PROFILE,
            quantile_method=REFERENCE_TENSILE_PAIR_QUANTILE_METHOD,
            confidence_interval_status=REFERENCE_TENSILE_PAIR_CI_STATUS,
            curve_output_schema_ref=REFERENCE_TENSILE_PAIR_CURVE_SCHEMA,
        )


class StatisticalPlanRevisionResponse(RevisionMetadataResponse):
    content: ReferenceTensilePairPlanContentResponse

    @classmethod
    def from_snapshot(
        cls, value: RevisionSnapshot[ReferenceTensilePairPlanContent]
    ) -> StatisticalPlanRevisionResponse:
        metadata = RevisionMetadataResponse.from_record(value.record, "draft")
        return cls(
            **metadata.model_dump(),
            content=ReferenceTensilePairPlanContentResponse.from_domain(value.content),
        )


class StatisticalPlanResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    statistical_plan_id: UUID
    plan_label: str
    current_revision: StatisticalPlanRevisionResponse
    links: dict[str, str]

    @classmethod
    def from_snapshot(cls, value: StatisticalPlanSnapshot) -> StatisticalPlanResponse:
        root = f"/api/v1/statistical-plans/{value.id}"
        return cls(
            statistical_plan_id=value.id,
            plan_label=value.current.content.plan_label,
            current_revision=StatisticalPlanRevisionResponse.from_snapshot(value.current),
            links={"self": root, "revisions": f"{root}/revisions"},
        )


class StatisticalPlanListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: tuple[StatisticalPlanResponse, ...]


class QcObservationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    check_code: str
    outcome: QcOutcome
    detail: str
    expected_point_count: int | None
    observed_point_count: int | None
    mismatch_index: int | None

    @classmethod
    def from_domain(cls, value: QcObservation) -> QcObservationResponse:
        return cls(
            check_code=value.check_code,
            outcome=value.outcome,
            detail=value.detail,
            expected_point_count=value.expected_point_count,
            observed_point_count=value.observed_point_count,
            mismatch_index=value.mismatch_index,
        )


class StatisticalRunResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    statistical_run_id: UUID
    classification: DataClassification
    execution_mode: str
    status: StatisticalRunStatus
    plan_id: UUID
    plan_revision_id: UUID
    first_selection_id: UUID
    first_selection_revision_id: UUID
    first_dataset_id: UUID
    first_dataset_revision_id: UUID
    second_selection_id: UUID
    second_selection_revision_id: UUID
    second_dataset_id: UUID
    second_dataset_revision_id: UUID
    sample_count: int
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
    def from_domain(cls, value: StatisticalRun) -> StatisticalRunResponse:
        root = f"/api/v1/statistical-runs/{value.id}"
        links = {"self": root}
        if value.result_id is not None:
            links["result"] = f"/api/v1/statistical-results/{value.result_id}"
        return cls(
            statistical_run_id=value.id,
            classification=value.classification,
            execution_mode="committed",
            status=value.status,
            plan_id=value.plan_id,
            plan_revision_id=value.plan_revision_id,
            first_selection_id=value.first_selection_id,
            first_selection_revision_id=value.first_selection_revision_id,
            first_dataset_id=value.first_dataset_id,
            first_dataset_revision_id=value.first_dataset_revision_id,
            second_selection_id=value.second_selection_id,
            second_selection_revision_id=value.second_selection_revision_id,
            second_dataset_id=value.second_dataset_id,
            second_dataset_revision_id=value.second_dataset_revision_id,
            sample_count=value.sample_count,
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
            ended_at=value.ended_at.isoformat() if value.ended_at is not None else None,
            links=links,
        )


class ReferenceTensilePairScalarStatisticsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    first_peak_engineering_stress_pa: float
    second_peak_engineering_stress_pa: float
    mean_engineering_stress_pa: float
    sample_standard_deviation_engineering_stress_pa: float
    median_engineering_stress_pa: float
    median_absolute_deviation_engineering_stress_pa: float
    interquartile_range_engineering_stress_pa: float
    minimum_engineering_stress_pa: float
    maximum_engineering_stress_pa: float
    coefficient_of_variation: float | None
    confidence_interval_status: str
    quantile_method: str

    @classmethod
    def from_domain(
        cls, value: ReferenceTensilePairScalarStatistics
    ) -> ReferenceTensilePairScalarStatisticsResponse:
        return cls(
            first_peak_engineering_stress_pa=value.first_peak_engineering_stress_pa,
            second_peak_engineering_stress_pa=value.second_peak_engineering_stress_pa,
            mean_engineering_stress_pa=value.mean_engineering_stress_pa,
            sample_standard_deviation_engineering_stress_pa=(
                value.sample_standard_deviation_engineering_stress_pa
            ),
            median_engineering_stress_pa=value.median_engineering_stress_pa,
            median_absolute_deviation_engineering_stress_pa=(
                value.median_absolute_deviation_engineering_stress_pa
            ),
            interquartile_range_engineering_stress_pa=(
                value.interquartile_range_engineering_stress_pa
            ),
            minimum_engineering_stress_pa=value.minimum_engineering_stress_pa,
            maximum_engineering_stress_pa=value.maximum_engineering_stress_pa,
            coefficient_of_variation=value.coefficient_of_variation,
            confidence_interval_status=REFERENCE_TENSILE_PAIR_CI_STATUS,
            quantile_method=REFERENCE_TENSILE_PAIR_QUANTILE_METHOD,
        )


class ReferenceTensilePairResultContentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    result_kind: str
    statistical_run_id: UUID
    plan_id: UUID
    plan_revision_id: UUID
    first_selection_id: UUID
    first_selection_revision_id: UUID
    first_dataset_id: UUID
    first_dataset_revision_id: UUID
    second_selection_id: UUID
    second_selection_revision_id: UUID
    second_dataset_id: UUID
    second_dataset_revision_id: UUID
    sample_count: int
    scalar_feature: str
    curve_artifact_id: UUID
    curve_sha256: str
    curve_point_count: int
    scalar: ReferenceTensilePairScalarStatisticsResponse
    assumption_profile: str
    curve_grid_policy: str

    @classmethod
    def from_domain(
        cls, value: ReferenceTensilePairResultContent
    ) -> ReferenceTensilePairResultContentResponse:
        return cls(
            result_kind=REFERENCE_TENSILE_PAIR_PLAN_KIND,
            statistical_run_id=value.statistical_run_id,
            plan_id=value.plan_id,
            plan_revision_id=value.plan_revision_id,
            first_selection_id=value.first_selection_id,
            first_selection_revision_id=value.first_selection_revision_id,
            first_dataset_id=value.first_dataset_id,
            first_dataset_revision_id=value.first_dataset_revision_id,
            second_selection_id=value.second_selection_id,
            second_selection_revision_id=value.second_selection_revision_id,
            second_dataset_id=value.second_dataset_id,
            second_dataset_revision_id=value.second_dataset_revision_id,
            sample_count=2,
            scalar_feature=REFERENCE_TENSILE_PAIR_SCALAR_FEATURE,
            curve_artifact_id=value.curve_artifact_id,
            curve_sha256=value.curve_sha256,
            curve_point_count=value.curve_point_count,
            scalar=ReferenceTensilePairScalarStatisticsResponse.from_domain(value.scalar),
            assumption_profile=REFERENCE_TENSILE_PAIR_ASSUMPTION_PROFILE,
            curve_grid_policy=REFERENCE_TENSILE_PAIR_GRID_POLICY,
        )


class StatisticalResultRevisionResponse(RevisionMetadataResponse):
    content: ReferenceTensilePairResultContentResponse

    @classmethod
    def from_snapshot(
        cls, value: RevisionSnapshot[ReferenceTensilePairResultContent]
    ) -> StatisticalResultRevisionResponse:
        metadata = RevisionMetadataResponse.from_record(value.record, "draft")
        return cls(
            **metadata.model_dump(),
            content=ReferenceTensilePairResultContentResponse.from_domain(value.content),
        )


class StatisticalResultResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    statistical_result_id: UUID
    current_revision: StatisticalResultRevisionResponse
    links: dict[str, str]

    @classmethod
    def from_snapshot(cls, value: StatisticalResultSnapshot) -> StatisticalResultResponse:
        root = f"/api/v1/statistical-results/{value.id}"
        return cls(
            statistical_result_id=value.id,
            current_revision=StatisticalResultRevisionResponse.from_snapshot(value.current),
            links={"self": root, "curve": f"{root}/curve"},
        )


class ReferenceTensilePairCurvePointResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    engineering_strain: float
    mean_engineering_stress_pa: float
    sample_standard_deviation_engineering_stress_pa: float
    median_engineering_stress_pa: float
    minimum_engineering_stress_pa: float
    maximum_engineering_stress_pa: float

    @classmethod
    def from_domain(
        cls, value: ReferenceTensilePairCurvePoint
    ) -> ReferenceTensilePairCurvePointResponse:
        return cls(
            engineering_strain=value.engineering_strain,
            mean_engineering_stress_pa=value.mean_engineering_stress_pa,
            sample_standard_deviation_engineering_stress_pa=(
                value.sample_standard_deviation_engineering_stress_pa
            ),
            median_engineering_stress_pa=value.median_engineering_stress_pa,
            minimum_engineering_stress_pa=value.minimum_engineering_stress_pa,
            maximum_engineering_stress_pa=value.maximum_engineering_stress_pa,
        )


class StatisticalCurvePreviewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    statistical_result_id: UUID
    point_count: int
    returned_point_count: int
    sampled: bool
    strain_unit: str
    stress_unit: str
    points: tuple[ReferenceTensilePairCurvePointResponse, ...]


class StatisticsProblem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Label
    title: Label
    status: Annotated[int, Field(ge=400, le=599)]
    detail: Annotated[str, StringConstraints(min_length=1, max_length=2000)]
    code: Annotated[str, StringConstraints(pattern=r"^CMP-STATISTICS-[0-9]{4}$")]
    trace_id: Label


class StatisticsHttpError(Exception):
    def __init__(
        self,
        *,
        context: SecurityContext,
        status_code: int,
        title: str,
        detail: str,
        code: str,
    ) -> None:
        self.context = context
        self.problem = StatisticsProblem(
            type="urn:cmp:problem:statistics",
            title=title,
            status=status_code,
            detail=detail,
            code=code,
            trace_id=context.trace_id,
        )
        super().__init__(title)


def _scope(request: Request) -> tuple[SecurityContext, AuthorizationDecision]:
    context = getattr(request.state, "security_context", None)
    decision = getattr(request.state, "authorization_decision", None)
    if not isinstance(context, SecurityContext) or not isinstance(decision, AuthorizationDecision):
        raise RuntimeError("Statistics route dependencies did not initialize request scope")
    return context, decision


def _unavailable(context: SecurityContext) -> StatisticsHttpError:
    return StatisticsHttpError(
        context=context,
        status_code=503,
        title="Statistics service unavailable",
        detail=(
            "The authoritative Statistics, Dataset, or immutable Artifact store is not configured."
        ),
        code="CMP-STATISTICS-0005",
    )


def _translate(context: SecurityContext, error: Exception) -> StatisticsHttpError:
    if isinstance(error, (StatisticsNotFound, DatasetNotFound, ArtifactNotFound)):
        return StatisticsHttpError(
            context=context,
            status_code=404,
            title="Statistics resource not found",
            detail=(
                "No requested Plan, Run, Result, Selection revision, Dataset revision, "
                "or Artifact is visible."
            ),
            code="CMP-STATISTICS-0001",
        )
    if isinstance(error, (InvalidStatisticsRequest, InvalidArtifact, ValueError)):
        return StatisticsHttpError(
            context=context,
            status_code=422,
            title="Invalid Statistics request",
            detail=(
                "The reference method requires two distinct pinned Selection revisions "
                "and declared typed input."
            ),
            code="CMP-STATISTICS-0002",
        )
    if isinstance(error, (ArtifactAccessDenied, ArtifactIntegrityError)):
        return StatisticsHttpError(
            context=context,
            status_code=409,
            title="Statistics input unavailable",
            detail="A pinned immutable input Artifact is not currently usable for Statistics.",
            code="CMP-STATISTICS-0003",
        )
    if isinstance(error, (StatisticsConflict, DatasetError, RevisionKernelError, IntegrityError)):
        return StatisticsHttpError(
            context=context,
            status_code=409,
            title="Statistics state conflict",
            detail="The committed run conflicts with immutable pinned input or output state.",
            code="CMP-STATISTICS-0003",
        )
    if isinstance(error, (StatisticsError, ArtifactError)):
        return StatisticsHttpError(
            context=context,
            status_code=409,
            title="Statistics command rejected",
            detail="The Statistics command could not be completed.",
            code="CMP-STATISTICS-0003",
        )
    return StatisticsHttpError(
        context=context,
        status_code=409,
        title="Statistics command rejected",
        detail="The Statistics command could not be completed.",
        code="CMP-STATISTICS-0003",
    )


def _etag(response: Response, record: RevisionRecord) -> None:
    response.headers["ETag"] = str(RevisionETag.from_ref(record.ref))
    response.headers["Cache-Control"] = "no-store"


def install_statistics_api(
    application: FastAPI,
    *,
    service: StatisticsService | None,
    security_dependency: Dependency,
    read_dependency: Dependency,
    execute_dependency: Dependency,
) -> None:
    @application.exception_handler(StatisticsHttpError)
    async def statistics_error_handler(
        request: Request, error: StatisticsHttpError
    ) -> JSONResponse:
        del request
        return JSONResponse(
            status_code=error.problem.status,
            content=error.problem.model_dump(mode="json"),
            media_type="application/problem+json",
            headers={"Cache-Control": "no-store", "X-Request-ID": str(error.context.request_id)},
        )

    errors: dict[int | str, dict[str, Any]] = {
        401: {"description": "Authentication required."},
        403: {"model": StatisticsProblem},
        404: {"model": StatisticsProblem},
        409: {"model": StatisticsProblem},
        422: {"model": StatisticsProblem},
        503: {"model": StatisticsProblem},
    }

    @application.post(
        "/api/v1/statistical-plans/reference-tensile-pair",
        operation_id="createReferenceTensilePairStatisticalPlan",
        response_model=StatisticalPlanResponse,
        status_code=status.HTTP_201_CREATED,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(execute_dependency)],
        tags=["statistics"],
    )
    def create_plan(
        request: Request,
        response: Response,
        body: CreateReferenceTensilePairPlanRequest,
    ) -> StatisticalPlanResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            result = service.create_reference_tensile_pair_plan(
                context,
                decision,
                CreateReferenceTensilePairPlan(
                    classification=body.classification,
                    content=body.content.to_domain(),
                    change_reason=body.change_reason,
                ),
            )
        except Exception as error:
            raise _translate(context, error) from error
        response.headers["Location"] = f"/api/v1/statistical-plans/{result.id}"
        _etag(response, result.current.record)
        return StatisticalPlanResponse.from_snapshot(result)

    @application.get(
        "/api/v1/statistical-plans",
        operation_id="listStatisticalPlans",
        response_model=StatisticalPlanListResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["statistics"],
    )
    def list_plans(
        request: Request,
        limit: Annotated[int, Query(ge=1, le=200)] = 100,
    ) -> StatisticalPlanListResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            items = service.list_plans(context, decision, limit=limit)
        except Exception as error:
            raise _translate(context, error) from error
        return StatisticalPlanListResponse(
            items=tuple(StatisticalPlanResponse.from_snapshot(item) for item in items)
        )

    @application.get(
        "/api/v1/statistical-plans/{plan_id}",
        operation_id="getStatisticalPlan",
        response_model=StatisticalPlanResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["statistics"],
    )
    def get_plan(request: Request, response: Response, plan_id: UUID) -> StatisticalPlanResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            result = service.get_plan(context, decision, plan_id)
        except Exception as error:
            raise _translate(context, error) from error
        _etag(response, result.current.record)
        return StatisticalPlanResponse.from_snapshot(result)

    @application.post(
        "/api/v1/statistical-plans/{plan_id}/revisions",
        operation_id="reviseReferenceTensilePairStatisticalPlan",
        response_model=StatisticalPlanResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(execute_dependency)],
        tags=["statistics"],
    )
    def revise_plan(
        request: Request,
        response: Response,
        plan_id: UUID,
        body: ReviseReferenceTensilePairPlanRequest,
    ) -> StatisticalPlanResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            result = service.revise_reference_tensile_pair_plan(
                context,
                decision,
                plan_id,
                ReviseReferenceTensilePairPlan(
                    expected_current_revision_id=body.expected_current_revision_id,
                    content=body.to_content(),
                    change_reason=body.change_reason,
                ),
            )
        except Exception as error:
            raise _translate(context, error) from error
        _etag(response, result.current.record)
        return StatisticalPlanResponse.from_snapshot(result)

    @application.post(
        "/api/v1/statistical-runs/reference-tensile-pair",
        operation_id="executeReferenceTensilePairStatistics",
        response_model=StatisticalRunResponse,
        status_code=status.HTTP_201_CREATED,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(execute_dependency)],
        tags=["statistics"],
    )
    async def execute_statistics(
        request: Request,
        response: Response,
        body: ExecuteReferenceTensilePairStatisticsRequest,
    ) -> StatisticalRunResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            result = await service.execute_reference_tensile_pair_statistics(
                context,
                decision,
                ExecuteReferenceTensilePairStatistics(
                    plan_id=body.plan_id,
                    plan_revision_id=body.plan_revision_id,
                    change_reason=body.change_reason,
                ),
            )
        except Exception as error:
            raise _translate(context, error) from error
        response.headers["Location"] = f"/api/v1/statistical-runs/{result.id}"
        response.headers["Cache-Control"] = "no-store"
        return StatisticalRunResponse.from_domain(result)

    @application.get(
        "/api/v1/statistical-runs/{run_id}",
        operation_id="getStatisticalRun",
        response_model=StatisticalRunResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["statistics"],
    )
    def get_run(request: Request, run_id: UUID) -> StatisticalRunResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            result = service.get_run(context, decision, run_id)
        except Exception as error:
            raise _translate(context, error) from error
        return StatisticalRunResponse.from_domain(result)

    @application.get(
        "/api/v1/statistical-results/{result_id}",
        operation_id="getStatisticalResult",
        response_model=StatisticalResultResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["statistics"],
    )
    def get_result(
        request: Request, response: Response, result_id: UUID
    ) -> StatisticalResultResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            result = service.get_result(context, decision, result_id)
        except Exception as error:
            raise _translate(context, error) from error
        _etag(response, result.current.record)
        return StatisticalResultResponse.from_snapshot(result)

    @application.get(
        "/api/v1/statistical-results/{result_id}/curve",
        operation_id="previewStatisticalResultCurve",
        response_model=StatisticalCurvePreviewResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["statistics"],
    )
    async def preview_curve(
        request: Request,
        result_id: UUID,
        maximum_points: Annotated[int, Query(ge=2, le=10_000)] = 1_000,
    ) -> StatisticalCurvePreviewResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            result = service.get_result(context, decision, result_id)
            points = await service.preview_reference_tensile_pair_result_curve(
                context,
                decision,
                result_id,
                maximum_points=maximum_points,
            )
        except Exception as error:
            raise _translate(context, error) from error
        return StatisticalCurvePreviewResponse(
            statistical_result_id=result.id,
            point_count=result.current.content.curve_point_count,
            returned_point_count=len(points),
            sampled=len(points) != result.current.content.curve_point_count,
            strain_unit="1",
            stress_unit="Pa",
            points=tuple(
                ReferenceTensilePairCurvePointResponse.from_domain(item) for item in points
            ),
        )

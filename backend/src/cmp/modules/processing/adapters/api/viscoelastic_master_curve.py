"""HTTP contract for T-42 viscoelastic statistics, shift evidence, and master curve."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends, FastAPI, Request, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.processing.application.viscoelastic_master_curve import (
    CreateViscoelasticMasterPlan,
    ExecuteViscoelasticMasterPlan,
    ViscoelasticMasterPlanSnapshot,
    ViscoelasticMasterPreview,
    ViscoelasticMasterRun,
    ViscoelasticMasterService,
)
from cmp.modules.processing.domain.reference_tensile_crop import (
    ProcessingConflict,
    ProcessingError,
    ProcessingNotFound,
)
from cmp.modules.processing.domain.viscoelastic_master_curve import (
    InvalidViscoelasticMasterPlan,
    ManualShiftFactor,
    ShiftMethod,
    ViscoelasticMasterPlanContent,
)
from cmp.shared.contracts.revisions import RevisionETag, RevisionMetadataResponse

type Dependency = Callable[..., object]
type Reason = Annotated[str, StringConstraints(min_length=1, max_length=2000)]

logger = logging.getLogger(__name__)


class ManualShiftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    temperature_k: Annotated[float, Field(gt=0)]
    log10_a_t: Annotated[float, Field(ge=-20, le=20)]


class CreateViscoelasticMasterPlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    classification: DataClassification
    plan_label: Annotated[str, StringConstraints(min_length=1, max_length=160)]
    selection_id: UUID
    selection_revision_id: UUID
    reference_temperature_k: Annotated[float, Field(gt=0)]
    grid_point_count: Annotated[int, Field(ge=3, le=501)] = 101
    shift_method: ShiftMethod
    manual_shift_factors: list[ManualShiftRequest] = Field(
        default_factory=list, max_length=50
    )
    change_reason: Reason


class ExecuteViscoelasticMasterPlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_id: UUID
    plan_revision_id: UUID
    change_reason: Reason


class ViscoelasticMasterPlanContentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_label: str
    selection_id: UUID
    selection_revision_id: UUID
    reference_temperature_k: float
    grid_point_count: int
    shift_method: ShiftMethod
    manual_shift_factors: list[ManualShiftRequest]
    interpolation: str
    domain_policy: str
    reduced_time_convention: str


class ViscoelasticMasterPlanResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_id: UUID
    current_revision: RevisionMetadataResponse
    content: ViscoelasticMasterPlanContentResponse
    links: dict[str, str]

    @classmethod
    def from_domain(
        cls, value: ViscoelasticMasterPlanSnapshot
    ) -> ViscoelasticMasterPlanResponse:
        content = value.current.content
        return cls(
            plan_id=value.id,
            current_revision=RevisionMetadataResponse.from_record(
                value.current.record, "draft"
            ),
            content=ViscoelasticMasterPlanContentResponse(
                plan_label=content.plan_label,
                selection_id=content.selection_id,
                selection_revision_id=content.selection_revision_id,
                reference_temperature_k=content.reference_temperature_k,
                grid_point_count=content.grid_point_count,
                shift_method=content.shift_method,
                manual_shift_factors=[
                    ManualShiftRequest(
                        temperature_k=item.temperature_k,
                        log10_a_t=item.log10_a_t,
                    )
                    for item in content.manual_shift_factors
                ],
                interpolation=content.interpolation,
                domain_policy=content.domain_policy,
                reduced_time_convention=content.reduced_time_convention,
            ),
            links={"execute": "/api/v1/processing-runs/viscoelastic-master-curve"},
        )


class ShiftFactorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    temperature_k: float
    log10_a_t: float
    source: str
    observed_log10_a_t: float | None
    residual_log10_a_t: float | None
    alignment_rmse_pa: float | None


class ViscoelasticMasterRunResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    processing_run_id: UUID
    classification: DataClassification
    plan_id: UUID
    plan_revision_id: UUID
    selection_id: UUID
    selection_revision_id: UUID
    status: str
    source_curve_count: int
    temperature_count: int
    aligned_row_count: int | None
    statistics_row_count: int | None
    master_row_count: int | None
    aligned_dataset_id: UUID | None
    aligned_dataset_revision_id: UUID | None
    statistics_dataset_id: UUID | None
    statistics_dataset_revision_id: UUID | None
    master_dataset_id: UUID | None
    master_dataset_revision_id: UUID | None
    wlf_c1: float | None
    wlf_c2_k: float | None
    arrhenius_activation_energy_j_per_mol: float | None
    shift_factors: list[ShiftFactorResponse]
    failure_code: str | None
    started_at: str
    ended_at: str | None
    links: dict[str, str]

    @classmethod
    def from_domain(cls, value: ViscoelasticMasterRun) -> ViscoelasticMasterRunResponse:
        root = f"/api/v1/processing-runs/viscoelastic-master-curve/{value.id}"
        return cls(
            processing_run_id=value.id,
            classification=DataClassification(value.scope.classification),
            plan_id=value.plan_id,
            plan_revision_id=value.plan_revision_id,
            selection_id=value.selection_id,
            selection_revision_id=value.selection_revision_id,
            status=value.status.value,
            source_curve_count=value.source_curve_count,
            temperature_count=value.temperature_count,
            aligned_row_count=value.aligned_row_count,
            statistics_row_count=value.statistics_row_count,
            master_row_count=value.master_row_count,
            aligned_dataset_id=value.aligned_dataset_id,
            aligned_dataset_revision_id=value.aligned_dataset_revision_id,
            statistics_dataset_id=value.statistics_dataset_id,
            statistics_dataset_revision_id=value.statistics_dataset_revision_id,
            master_dataset_id=value.master_dataset_id,
            master_dataset_revision_id=value.master_dataset_revision_id,
            wlf_c1=value.wlf_c1,
            wlf_c2_k=value.wlf_c2_k,
            arrhenius_activation_energy_j_per_mol=(
                value.arrhenius_activation_energy_j_per_mol
            ),
            shift_factors=[
                ShiftFactorResponse(
                    temperature_k=item.temperature_k,
                    log10_a_t=item.log10_a_t,
                    source=item.source,
                    observed_log10_a_t=item.observed_log10_a_t,
                    residual_log10_a_t=item.residual_log10_a_t,
                    alignment_rmse_pa=item.alignment_rmse_pa,
                )
                for item in value.shift_factors
            ],
            failure_code=value.failure_code,
            started_at=value.started_at.isoformat(),
            ended_at=value.ended_at.isoformat() if value.ended_at else None,
            links={"self": root, "preview": f"{root}/preview"},
        )


class CurvePointResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    time_s: float
    shear_modulus_pa: float


class AlignedCurveResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    member_ordinal: int
    dataset_revision_id: UUID
    test_run_revision_id: UUID
    temperature_k: float
    outlier_status: str
    points: list[CurvePointResponse]


class StatisticsPointResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    time_s: float
    replicate_count: int
    mean_shear_modulus_pa: float
    sample_standard_deviation_pa: float | None
    median_shear_modulus_pa: float
    minimum_shear_modulus_pa: float
    maximum_shear_modulus_pa: float


class TemperatureStatisticsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    temperature_k: float
    replicate_count: int
    points: list[StatisticsPointResponse]


class MasterCurvePointResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reduced_time_s: float
    contributing_curve_count: int
    mean_shear_modulus_pa: float
    sample_standard_deviation_pa: float | None
    minimum_shear_modulus_pa: float
    maximum_shear_modulus_pa: float


class ViscoelasticMasterPreviewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run: ViscoelasticMasterRunResponse
    reference_temperature_k: float
    aligned_curves: list[AlignedCurveResponse]
    temperature_statistics: list[TemperatureStatisticsResponse]
    master_curve: list[MasterCurvePointResponse]
    policy: dict[str, str]

    @classmethod
    def from_domain(
        cls, value: ViscoelasticMasterPreview
    ) -> ViscoelasticMasterPreviewResponse:
        outlier_status = {
            item.ordinal: item.outlier_status for item in value.selection.content.members
        }
        return cls(
            run=ViscoelasticMasterRunResponse.from_domain(value.run),
            reference_temperature_k=value.run.shift_factors[
                next(
                    index
                    for index, item in enumerate(value.run.shift_factors)
                    if item.source == "reference"
                )
            ].temperature_k,
            aligned_curves=[
                AlignedCurveResponse(
                    member_ordinal=curve.member_ordinal,
                    dataset_revision_id=curve.dataset_revision_id,
                    test_run_revision_id=curve.test_run_revision_id,
                    temperature_k=curve.temperature_k,
                    outlier_status=outlier_status[curve.member_ordinal],
                    points=[
                        CurvePointResponse(
                            time_s=point.time_s,
                            shear_modulus_pa=point.shear_modulus_pa,
                        )
                        for point in curve.points
                    ],
                )
                for curve in value.aligned_curves
            ],
            temperature_statistics=[
                TemperatureStatisticsResponse(
                    temperature_k=item.temperature_k,
                    replicate_count=item.replicate_count,
                    points=[
                        StatisticsPointResponse(
                            time_s=point.time_s,
                            replicate_count=point.replicate_count,
                            mean_shear_modulus_pa=point.mean_shear_modulus_pa,
                            sample_standard_deviation_pa=(
                                point.sample_standard_deviation_pa
                            ),
                            median_shear_modulus_pa=point.median_shear_modulus_pa,
                            minimum_shear_modulus_pa=point.minimum_shear_modulus_pa,
                            maximum_shear_modulus_pa=point.maximum_shear_modulus_pa,
                        )
                        for point in item.points
                    ],
                )
                for item in value.temperature_statistics
            ],
            master_curve=[
                MasterCurvePointResponse(
                    reduced_time_s=point.reduced_time_s,
                    contributing_curve_count=point.contributing_curve_count,
                    mean_shear_modulus_pa=point.mean_shear_modulus_pa,
                    sample_standard_deviation_pa=point.sample_standard_deviation_pa,
                    minimum_shear_modulus_pa=point.minimum_shear_modulus_pa,
                    maximum_shear_modulus_pa=point.maximum_shear_modulus_pa,
                )
                for point in value.master_curve
            ],
            policy={
                "interpolation": "piecewise_linear_log_time",
                "domain": "common_intersection_no_extrapolation",
                "reduced_time": "time_divided_by_a_t",
            },
        )


class ProcessingProblem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    title: str
    status: int
    detail: str
    code: str
    trace_id: str


class ProcessingHttpError(Exception):
    def __init__(self, context: SecurityContext, status_code: int, title: str, code: str) -> None:
        self.problem = ProcessingProblem(
            type="urn:cmp:problem:viscoelastic-master-curve",
            title=title,
            status=status_code,
            detail="The viscoelastic master-curve request could not be completed.",
            code=code,
            trace_id=context.trace_id,
        )
        super().__init__(title)


def _scope(request: Request) -> tuple[SecurityContext, AuthorizationDecision]:
    context = getattr(request.state, "security_context", None)
    decision = getattr(request.state, "authorization_decision", None)
    if not isinstance(context, SecurityContext) or not isinstance(decision, AuthorizationDecision):
        raise RuntimeError("Processing route dependencies did not initialize request scope")
    return context, decision


def _translate(context: SecurityContext, error: Exception) -> ProcessingHttpError:
    if isinstance(error, ProcessingNotFound):
        return ProcessingHttpError(
            context, 404, "Processing resource not found", "CMP-PROCESSING-4201"
        )
    if isinstance(error, (InvalidViscoelasticMasterPlan, ValueError)):
        return ProcessingHttpError(
            context, 422, "Invalid master-curve request", "CMP-PROCESSING-4202"
        )
    if isinstance(error, (ProcessingConflict, ProcessingError)):
        return ProcessingHttpError(context, 409, "Master-curve conflict", "CMP-PROCESSING-4203")
    return ProcessingHttpError(context, 409, "Master-curve request rejected", "CMP-PROCESSING-4203")


def install_viscoelastic_master_api(
    application: FastAPI,
    *,
    service: ViscoelasticMasterService | None,
    security_dependency: Dependency,
    read_dependency: Dependency,
    execute_dependency: Dependency,
) -> None:
    @application.exception_handler(ProcessingHttpError)
    async def error_handler(request: Request, error: ProcessingHttpError) -> JSONResponse:
        del request
        return JSONResponse(
            status_code=error.problem.status,
            content=error.problem.model_dump(mode="json"),
            media_type="application/problem+json",
        )

    errors: dict[int | str, dict[str, Any]] = {
        401: {"description": "Authentication required."},
        403: {"model": ProcessingProblem},
        404: {"model": ProcessingProblem},
        409: {"model": ProcessingProblem},
        422: {"model": ProcessingProblem},
        503: {"model": ProcessingProblem},
    }

    @application.post(
        "/api/v1/processing-plans/viscoelastic-master-curve",
        operation_id="createViscoelasticMasterPlan",
        response_model=ViscoelasticMasterPlanResponse,
        status_code=status.HTTP_201_CREATED,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(execute_dependency)],
        tags=["processing"],
    )
    def create_plan(
        request: Request,
        response: Response,
        body: CreateViscoelasticMasterPlanRequest,
    ) -> ViscoelasticMasterPlanResponse:
        context, decision = _scope(request)
        if service is None:
            raise ProcessingHttpError(
                context, 503, "Processing service unavailable", "CMP-PROCESSING-4205"
            )
        try:
            value = service.create_plan(
                context,
                decision,
                CreateViscoelasticMasterPlan(
                    classification=body.classification,
                    content=ViscoelasticMasterPlanContent(
                        plan_label=body.plan_label,
                        selection_id=body.selection_id,
                        selection_revision_id=body.selection_revision_id,
                        reference_temperature_k=body.reference_temperature_k,
                        grid_point_count=body.grid_point_count,
                        shift_method=body.shift_method,
                        manual_shift_factors=tuple(
                            ManualShiftFactor(item.temperature_k, item.log10_a_t)
                            for item in body.manual_shift_factors
                        ),
                    ),
                    change_reason=body.change_reason,
                ),
            )
        except Exception as error:
            raise _translate(context, error) from error
        response.headers["Location"] = (
            f"/api/v1/processing-plans/viscoelastic-master-curve/{value.id}"
        )
        response.headers["ETag"] = str(RevisionETag.from_ref(value.current.record.ref))
        return ViscoelasticMasterPlanResponse.from_domain(value)

    @application.post(
        "/api/v1/processing-runs/viscoelastic-master-curve",
        operation_id="executeViscoelasticMasterPlan",
        response_model=ViscoelasticMasterRunResponse,
        status_code=status.HTTP_201_CREATED,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(execute_dependency)],
        tags=["processing"],
    )
    async def execute(
        request: Request,
        response: Response,
        body: ExecuteViscoelasticMasterPlanRequest,
    ) -> ViscoelasticMasterRunResponse:
        context, decision = _scope(request)
        if service is None:
            raise ProcessingHttpError(
                context, 503, "Processing service unavailable", "CMP-PROCESSING-4205"
            )
        try:
            value = await service.execute(
                context,
                decision,
                ExecuteViscoelasticMasterPlan(**body.model_dump()),
            )
        except Exception as error:
            logger.exception("viscoelastic master-curve execution failed")
            raise _translate(context, error) from error
        response.headers["Location"] = (
            f"/api/v1/processing-runs/viscoelastic-master-curve/{value.id}"
        )
        return ViscoelasticMasterRunResponse.from_domain(value)

    @application.get(
        "/api/v1/processing-runs/viscoelastic-master-curve/{run_id}",
        operation_id="getViscoelasticMasterRun",
        response_model=ViscoelasticMasterRunResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["processing"],
    )
    def get_run(request: Request, run_id: UUID) -> ViscoelasticMasterRunResponse:
        context, decision = _scope(request)
        if service is None:
            raise ProcessingHttpError(
                context, 503, "Processing service unavailable", "CMP-PROCESSING-4205"
            )
        try:
            value = service.get_run(context, decision, run_id)
        except Exception as error:
            raise _translate(context, error) from error
        return ViscoelasticMasterRunResponse.from_domain(value)

    @application.get(
        "/api/v1/processing-runs/viscoelastic-master-curve/{run_id}/preview",
        operation_id="previewViscoelasticMasterRun",
        response_model=ViscoelasticMasterPreviewResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["processing"],
    )
    async def preview(
        request: Request, run_id: UUID
    ) -> ViscoelasticMasterPreviewResponse:
        context, decision = _scope(request)
        if service is None:
            raise ProcessingHttpError(
                context, 503, "Processing service unavailable", "CMP-PROCESSING-4205"
            )
        try:
            value = await service.preview(context, decision, run_id)
        except Exception as error:
            logger.exception("viscoelastic master-curve preview failed")
            raise _translate(context, error) from error
        return ViscoelasticMasterPreviewResponse.from_domain(value)

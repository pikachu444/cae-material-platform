"""Protected HTTP resources for the bounded non-production reference calibration slice."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends, FastAPI, Query, Request, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from sqlalchemy.exc import IntegrityError

from cmp.modules.datasets.domain.reference_tensile import DatasetError
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.modeling.application.calibration import (
    CalibrationAttempt,
    CalibrationCandidate,
    CalibrationDiagnosticPreview,
    CalibrationPlanSnapshot,
    CalibrationRunDetail,
    CreateReferenceLinearElasticCalibrationPlan,
    ExecuteReferenceLinearElasticCalibration,
    ReferenceCalibrationService,
    ReviseReferenceLinearElasticCalibrationPlan,
)
from cmp.modules.modeling.application.service import RevisionSnapshot
from cmp.modules.modeling.domain.reference_linear_elastic_calibration import (
    CalibrationConflict,
    CalibrationCurvePoint,
    CalibrationNotFound,
    InvalidCalibrationPlan,
    ReferenceLinearElasticCalibrationPlanContent,
)
from cmp.modules.modeling.domain.reference_linear_elasticity import (
    ModelingError,
    ReferenceModelNotFound,
)
from cmp.shared.contracts.revisions import RevisionETag, RevisionMetadataResponse
from cmp.shared.domain.revisions import AggregateNotFound, RevisionKernelError, RevisionRecord

type Label = Annotated[str, StringConstraints(min_length=1, max_length=255)]
type Dependency = Callable[..., object]


class ReferenceCalibrationPlanContentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_label: Annotated[str, StringConstraints(min_length=1, max_length=160)]
    selection_id: UUID
    selection_revision_id: UUID
    material_model_id: UUID
    material_model_revision_id: UUID
    youngs_modulus_lower_bound_pa: Annotated[float, Field(gt=0)]
    youngs_modulus_initial_value_pa: Annotated[float, Field(gt=0)]
    youngs_modulus_upper_bound_pa: Annotated[float, Field(gt=0)]
    normalization_stress_scale_pa: Annotated[float, Field(gt=0)]
    multistart_count: Annotated[int, Field(ge=1, le=16)] = 1
    random_seed: Annotated[int, Field(ge=-(2**63), lt=2**63)] = 0
    change_reason: Annotated[str, StringConstraints(min_length=1, max_length=2000)]

    def content(self) -> ReferenceLinearElasticCalibrationPlanContent:
        return ReferenceLinearElasticCalibrationPlanContent(
            plan_label=self.plan_label,
            selection_id=self.selection_id,
            selection_revision_id=self.selection_revision_id,
            material_model_id=self.material_model_id,
            material_model_revision_id=self.material_model_revision_id,
            youngs_modulus_lower_bound_pa=self.youngs_modulus_lower_bound_pa,
            youngs_modulus_initial_value_pa=self.youngs_modulus_initial_value_pa,
            youngs_modulus_upper_bound_pa=self.youngs_modulus_upper_bound_pa,
            normalization_stress_scale_pa=self.normalization_stress_scale_pa,
            multistart_count=self.multistart_count,
            random_seed=self.random_seed,
        )


class ReferenceCalibrationPlanCreateRequest(ReferenceCalibrationPlanContentRequest):
    classification: DataClassification
    change_reason: Annotated[str, StringConstraints(min_length=1, max_length=2000)]


class ReferenceCalibrationPlanReviseRequest(ReferenceCalibrationPlanContentRequest):
    expected_current_revision_id: UUID
    change_reason: Annotated[str, StringConstraints(min_length=1, max_length=2000)]


class ReferenceCalibrationExecuteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_id: UUID
    plan_revision_id: UUID
    change_reason: Annotated[str, StringConstraints(min_length=1, max_length=2000)]


class ReferenceCalibrationPlanContentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_kind: str
    plan_label: str
    selection_id: UUID
    selection_revision_id: UUID
    material_model_id: UUID
    material_model_revision_id: UUID
    model_family_id: str
    model_schema_version: str
    model_schema_digest: str
    test_mode: str
    evaluator_id: str
    evaluator_version: str
    evaluation_mode: str
    calibrator_id: str
    calibrator_version: str
    parameter_name: str
    youngs_modulus_lower_bound_pa: float
    youngs_modulus_initial_value_pa: float
    youngs_modulus_upper_bound_pa: float
    normalization_stress_scale_pa: float
    point_weighting: str
    objective_aggregation: str
    x_domain_policy: str
    missing_data_policy: str
    multistart_count: int
    random_seed: int
    non_production: bool

    @classmethod
    def from_domain(
        cls, value: ReferenceLinearElasticCalibrationPlanContent
    ) -> ReferenceCalibrationPlanContentResponse:
        return cls(
            plan_kind=value.plan_kind,
            plan_label=value.plan_label,
            selection_id=value.selection_id,
            selection_revision_id=value.selection_revision_id,
            material_model_id=value.material_model_id,
            material_model_revision_id=value.material_model_revision_id,
            model_family_id=value.model_family_id,
            model_schema_version=value.model_schema_version,
            model_schema_digest=f"sha256:{value.model_schema_digest}",
            test_mode=value.test_mode,
            evaluator_id=value.evaluator_id,
            evaluator_version=value.evaluator_version,
            evaluation_mode=value.evaluation_mode,
            calibrator_id=value.calibrator_id,
            calibrator_version=value.calibrator_version,
            parameter_name=value.parameter_name,
            youngs_modulus_lower_bound_pa=value.youngs_modulus_lower_bound_pa,
            youngs_modulus_initial_value_pa=value.youngs_modulus_initial_value_pa,
            youngs_modulus_upper_bound_pa=value.youngs_modulus_upper_bound_pa,
            normalization_stress_scale_pa=value.normalization_stress_scale_pa,
            point_weighting=value.point_weighting,
            objective_aggregation=value.objective_aggregation,
            x_domain_policy=value.x_domain_policy,
            missing_data_policy=value.missing_data_policy,
            multistart_count=value.multistart_count,
            random_seed=value.random_seed,
            non_production=value.non_production,
        )


class CalibrationPlanRevisionResponse(RevisionMetadataResponse):
    content: ReferenceCalibrationPlanContentResponse

    @classmethod
    def from_snapshot(
        cls, value: RevisionSnapshot[ReferenceLinearElasticCalibrationPlanContent]
    ) -> CalibrationPlanRevisionResponse:
        metadata = RevisionMetadataResponse.from_record(value.record, "draft")
        return cls(
            **metadata.model_dump(),
            content=ReferenceCalibrationPlanContentResponse.from_domain(value.content),
        )


class CalibrationPlanResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    calibration_plan_id: UUID
    current_revision: CalibrationPlanRevisionResponse
    links: dict[str, str]

    @classmethod
    def from_snapshot(cls, value: CalibrationPlanSnapshot) -> CalibrationPlanResponse:
        root = f"/api/v1/calibration-plans/{value.id}"
        return cls(
            calibration_plan_id=value.id,
            current_revision=CalibrationPlanRevisionResponse.from_snapshot(value.current),
            links={"self": root, "runs": "/api/v1/calibration-runs"},
        )


class CalibrationPlanListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: tuple[CalibrationPlanResponse, ...]


class CalibrationAttemptResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    calibration_attempt_id: UUID
    calibration_run_id: UUID
    attempt_ordinal: int
    initial_youngs_modulus_pa: float
    random_seed: int
    status: str
    candidate_id: UUID | None
    failure_code: str | None
    started_at: datetime
    ended_at: datetime | None

    @classmethod
    def from_domain(cls, value: CalibrationAttempt) -> CalibrationAttemptResponse:
        return cls(
            calibration_attempt_id=value.id,
            calibration_run_id=value.calibration_run_id,
            attempt_ordinal=value.attempt_ordinal,
            initial_youngs_modulus_pa=value.initial_youngs_modulus_pa,
            random_seed=value.random_seed,
            status=value.status.value,
            candidate_id=value.candidate_id,
            failure_code=value.failure_code,
            started_at=value.started_at,
            ended_at=value.ended_at,
        )


class CalibrationCandidateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    calibration_candidate_id: UUID
    calibration_run_id: UUID
    calibration_attempt_id: UUID
    attempt_ordinal: int
    status: str
    candidate_sha256: str
    youngs_modulus_pa: float
    objective_total: float
    residual_root_mean_square_pa: float
    residual_mean_pa: float
    bound_sticking: bool
    convergence_reason: str
    identifiability_status: str
    uncertainty_status: str
    diagnostics_artifact_id: UUID
    diagnostics_sha256: str
    diagnostics_point_count: int
    created_at: datetime
    created_by: UUID
    links: dict[str, str]

    @classmethod
    def from_domain(cls, value: CalibrationCandidate) -> CalibrationCandidateResponse:
        return cls(
            calibration_candidate_id=value.id,
            calibration_run_id=value.calibration_run_id,
            calibration_attempt_id=value.calibration_attempt_id,
            attempt_ordinal=value.attempt_ordinal,
            status=value.status.value,
            candidate_sha256=f"sha256:{value.candidate_sha256}",
            youngs_modulus_pa=value.youngs_modulus_pa,
            objective_total=value.objective_total,
            residual_root_mean_square_pa=value.residual_root_mean_square_pa,
            residual_mean_pa=value.residual_mean_pa,
            bound_sticking=value.bound_sticking,
            convergence_reason=value.convergence_reason,
            identifiability_status=value.identifiability_status,
            uncertainty_status=value.uncertainty_status,
            diagnostics_artifact_id=value.diagnostics_artifact_id,
            diagnostics_sha256=f"sha256:{value.diagnostics_sha256}",
            diagnostics_point_count=value.diagnostics_point_count,
            created_at=value.created_at,
            created_by=value.created_by,
            links={
                "diagnostics_preview": (
                    f"/api/v1/calibration-candidates/{value.id}/diagnostics-preview"
                )
            },
        )


class CalibrationRunResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    calibration_run_id: UUID
    classification: DataClassification
    calibration_plan_id: UUID
    calibration_plan_revision_id: UUID
    selection_id: UUID
    selection_revision_id: UUID
    dataset_id: UUID
    dataset_revision_id: UUID
    material_model_id: UUID
    material_model_revision_id: UUID
    execution_mode: str
    reproducibility_level: str
    environment_digest: str
    status: str
    attempt_count: int
    candidate_count: int
    failure_code: str | None
    change_reason: str
    started_at: datetime
    ended_at: datetime | None
    created_by: UUID
    request_id: UUID
    trace_id: str
    attempts: tuple[CalibrationAttemptResponse, ...]
    candidates: tuple[CalibrationCandidateResponse, ...]
    links: dict[str, str]

    @classmethod
    def from_detail(cls, value: CalibrationRunDetail) -> CalibrationRunResponse:
        run = value.run
        return cls(
            calibration_run_id=run.id,
            classification=run.classification,
            calibration_plan_id=run.plan_id,
            calibration_plan_revision_id=run.plan_revision_id,
            selection_id=run.selection_id,
            selection_revision_id=run.selection_revision_id,
            dataset_id=run.dataset_id,
            dataset_revision_id=run.dataset_revision_id,
            material_model_id=run.material_model_id,
            material_model_revision_id=run.material_model_revision_id,
            execution_mode=run.execution_mode,
            reproducibility_level=run.reproducibility_level,
            environment_digest=f"sha256:{run.environment_digest}",
            status=run.status.value,
            attempt_count=run.attempt_count,
            candidate_count=run.candidate_count,
            failure_code=run.failure_code,
            change_reason=run.change_reason,
            started_at=run.started_at,
            ended_at=run.ended_at,
            created_by=run.created_by,
            request_id=run.request_id,
            trace_id=run.trace_id,
            attempts=tuple(CalibrationAttemptResponse.from_domain(item) for item in value.attempts),
            candidates=tuple(
                CalibrationCandidateResponse.from_domain(item) for item in value.candidates
            ),
            links={"self": f"/api/v1/calibration-runs/{run.id}"},
        )


class CalibrationDiagnosticPointResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    engineering_strain: float
    observed_engineering_stress_pa: float
    predicted_engineering_stress_pa: float
    residual_engineering_stress_pa: float
    normalized_residual: float

    @classmethod
    def from_domain(cls, value: CalibrationCurvePoint) -> CalibrationDiagnosticPointResponse:
        return cls(
            engineering_strain=value.engineering_strain,
            observed_engineering_stress_pa=value.observed_engineering_stress_pa,
            predicted_engineering_stress_pa=value.predicted_engineering_stress_pa,
            residual_engineering_stress_pa=value.residual_engineering_stress_pa,
            normalized_residual=value.normalized_residual,
        )


class CalibrationDiagnosticPreviewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    calibration_candidate_id: UUID
    point_count: int
    returned_point_count: int
    sampled: bool
    points: tuple[CalibrationDiagnosticPointResponse, ...]

    @classmethod
    def from_domain(
        cls, value: CalibrationDiagnosticPreview
    ) -> CalibrationDiagnosticPreviewResponse:
        return cls(
            calibration_candidate_id=value.calibration_candidate_id,
            point_count=value.point_count,
            returned_point_count=value.returned_point_count,
            sampled=value.sampled,
            points=tuple(
                CalibrationDiagnosticPointResponse.from_domain(point) for point in value.points
            ),
        )


class CalibrationProblem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Label
    title: Label
    status: Annotated[int, Field(ge=400, le=599)]
    detail: Annotated[str, StringConstraints(min_length=1, max_length=2000)]
    code: Annotated[str, StringConstraints(pattern=r"^CMP-CALIBRATION-[0-9]{4}$")]
    trace_id: Label


class CalibrationHttpError(Exception):
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
        self.problem = CalibrationProblem(
            type="urn:cmp:problem:calibration",
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
        raise RuntimeError("Calibration route dependencies did not initialize request scope")
    return context, decision


def _unavailable(context: SecurityContext) -> CalibrationHttpError:
    return CalibrationHttpError(
        context=context,
        status_code=503,
        title="Calibration service unavailable",
        detail=(
            "The authoritative reference Calibration store is not configured for this deployment."
        ),
        code="CMP-CALIBRATION-0005",
    )


def _translate(context: SecurityContext, error: Exception) -> CalibrationHttpError:
    if isinstance(error, (CalibrationNotFound, ReferenceModelNotFound, AggregateNotFound)):
        return CalibrationHttpError(
            context=context,
            status_code=404,
            title="Calibration resource not found",
            detail=(
                "No requested Calibration, Material Model, Dataset Selection, or Candidate is "
                "visible in this tenant."
            ),
            code="CMP-CALIBRATION-0001",
        )
    if isinstance(error, (InvalidCalibrationPlan, DatasetError, ValueError)):
        return CalibrationHttpError(
            context=context,
            status_code=422,
            title="Invalid Calibration request",
            detail=(
                "The reference calibration requires explicit compatible inputs and numerical "
                "conventions."
            ),
            code="CMP-CALIBRATION-0002",
        )
    if isinstance(error, (CalibrationConflict, ModelingError, RevisionKernelError, IntegrityError)):
        return CalibrationHttpError(
            context=context,
            status_code=409,
            title="Calibration state conflict",
            detail=(
                "The Calibration command conflicts with immutable Plan, input, or execution "
                "state."
            ),
            code="CMP-CALIBRATION-0003",
        )
    return CalibrationHttpError(
        context=context,
        status_code=409,
        title="Calibration command rejected",
        detail="The reference Calibration command could not be completed.",
        code="CMP-CALIBRATION-0003",
    )


def _etag(response: Response, record: RevisionRecord) -> None:
    response.headers["ETag"] = str(RevisionETag.from_ref(record.ref))
    response.headers["Cache-Control"] = "no-store"


def install_calibration_api(
    application: FastAPI,
    *,
    service: ReferenceCalibrationService | None,
    security_dependency: Dependency,
    read_dependency: Dependency,
    execute_dependency: Dependency,
) -> None:
    @application.exception_handler(CalibrationHttpError)
    async def calibration_error_handler(
        request: Request, error: CalibrationHttpError
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
        403: {"description": "Calibration permission is not authorized."},
        404: {"model": CalibrationProblem},
        409: {"model": CalibrationProblem},
        422: {"model": CalibrationProblem},
        503: {"model": CalibrationProblem},
    }

    @application.post(
        "/api/v1/calibration-plans",
        operation_id="createReferenceLinearElasticCalibrationPlan",
        response_model=CalibrationPlanResponse,
        status_code=status.HTTP_201_CREATED,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(execute_dependency)],
        tags=["modeling", "calibration"],
        summary="Create an immutable Plan for the non-production reference tensile calibration.",
    )
    def create_plan(
        request: Request, response: Response, body: ReferenceCalibrationPlanCreateRequest
    ) -> CalibrationPlanResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            value = service.create_plan(
                context,
                decision,
                CreateReferenceLinearElasticCalibrationPlan(
                    classification=body.classification,
                    content=body.content(),
                    change_reason=body.change_reason,
                ),
            )
        except Exception as error:
            raise _translate(context, error) from error
        _etag(response, value.current.record)
        return CalibrationPlanResponse.from_snapshot(value)

    @application.patch(
        "/api/v1/calibration-plans/{plan_id}",
        operation_id="reviseReferenceLinearElasticCalibrationPlan",
        response_model=CalibrationPlanResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(execute_dependency)],
        tags=["modeling", "calibration"],
        summary="Append a new immutable reference Calibration Plan revision.",
    )
    def revise_plan(
        request: Request,
        response: Response,
        plan_id: UUID,
        body: ReferenceCalibrationPlanReviseRequest,
    ) -> CalibrationPlanResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            value = service.revise_plan(
                context,
                decision,
                plan_id,
                ReviseReferenceLinearElasticCalibrationPlan(
                    expected_current_revision_id=body.expected_current_revision_id,
                    content=body.content(),
                    change_reason=body.change_reason,
                ),
            )
        except Exception as error:
            raise _translate(context, error) from error
        _etag(response, value.current.record)
        return CalibrationPlanResponse.from_snapshot(value)

    @application.get(
        "/api/v1/calibration-plans",
        operation_id="listCalibrationPlans",
        response_model=CalibrationPlanListResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["modeling", "calibration"],
        summary="List current immutable Calibration Plan revisions visible in this tenant.",
    )
    def list_plans(
        request: Request, limit: Annotated[int, Query(ge=1, le=200)] = 100
    ) -> CalibrationPlanListResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            values = service.list_plans(context, decision, limit=limit)
        except Exception as error:
            raise _translate(context, error) from error
        return CalibrationPlanListResponse(
            items=tuple(CalibrationPlanResponse.from_snapshot(item) for item in values)
        )

    @application.get(
        "/api/v1/calibration-plans/{plan_id}",
        operation_id="getCalibrationPlan",
        response_model=CalibrationPlanResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["modeling", "calibration"],
        summary="Read one current immutable Calibration Plan revision.",
    )
    def get_plan(request: Request, response: Response, plan_id: UUID) -> CalibrationPlanResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            value = service.get_plan(context, decision, plan_id)
        except Exception as error:
            raise _translate(context, error) from error
        _etag(response, value.current.record)
        return CalibrationPlanResponse.from_snapshot(value)

    @application.post(
        "/api/v1/calibration-runs",
        operation_id="executeReferenceLinearElasticCalibration",
        response_model=CalibrationRunResponse,
        status_code=status.HTTP_201_CREATED,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(execute_dependency)],
        tags=["modeling", "calibration"],
        summary=(
            "Execute the deterministic non-production reference Calibration against fixed "
            "revisions."
        ),
    )
    async def execute(
        request: Request, body: ReferenceCalibrationExecuteRequest
    ) -> CalibrationRunResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            value = await service.execute(
                context,
                decision,
                ExecuteReferenceLinearElasticCalibration(
                    plan_id=body.plan_id,
                    plan_revision_id=body.plan_revision_id,
                    change_reason=body.change_reason,
                ),
            )
        except Exception as error:
            raise _translate(context, error) from error
        return CalibrationRunResponse.from_detail(value)

    @application.get(
        "/api/v1/calibration-runs/{run_id}",
        operation_id="getCalibrationRun",
        response_model=CalibrationRunResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["modeling", "calibration"],
        summary="Read one durable Calibration Run with preserved Attempts and Candidates.",
    )
    def get_run(request: Request, run_id: UUID) -> CalibrationRunResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            value = service.get_run(context, decision, run_id)
        except Exception as error:
            raise _translate(context, error) from error
        return CalibrationRunResponse.from_detail(value)

    @application.get(
        "/api/v1/calibration-candidates/{candidate_id}/diagnostics-preview",
        operation_id="previewCalibrationCandidateDiagnostics",
        response_model=CalibrationDiagnosticPreviewResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["modeling", "calibration"],
        summary=(
            "Preview typed observed/predicted/residual diagnostics for one immutable Candidate."
        ),
    )
    async def preview_candidate_diagnostics(
        request: Request,
        candidate_id: UUID,
        maximum_points: Annotated[int, Query(ge=2, le=10000)] = 500,
    ) -> CalibrationDiagnosticPreviewResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            value = await service.preview_candidate_diagnostics(
                context,
                decision,
                candidate_id,
                maximum_points=maximum_points,
            )
        except Exception as error:
            raise _translate(context, error) from error
        return CalibrationDiagnosticPreviewResponse.from_domain(value)

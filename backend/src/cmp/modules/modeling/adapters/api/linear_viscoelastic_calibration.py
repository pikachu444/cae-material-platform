"""HTTP contract for governed linear-viscoelastic calibration Plans and Runs."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import Depends, FastAPI, Header, Request, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.modeling.adapters.api.linear_viscoelasticity import (
    LinearViscoelasticModelResponse,
)
from cmp.modules.modeling.application.linear_viscoelastic_calibration import (
    CalibrationJobReference,
    CalibrationPlanSnapshot,
    CalibrationRunProjection,
    CalibrationSelectionSnapshot,
    CreateGovernedLinearViscoelasticCalibrationPlan,
    CreateLinearViscoelasticCalibrationSelection,
    CreateProcessedLinearViscoelasticCalibrationPlan,
    LinearViscoelasticCalibrationConflict,
    LinearViscoelasticCalibrationNotFound,
    LinearViscoelasticCalibrationService,
    PromoteLinearViscoelasticCalibrationSelection,
    QueueLinearViscoelasticCalibrationRun,
)
from cmp.modules.modeling.domain.linear_viscoelastic_calibration import (
    CalibrationWeights,
    ChannelAvailability,
    DataAvailability,
    ParameterBound,
    PointDisposition,
    PointPartition,
)

type Dependency = Callable[..., object]
type Reason = Annotated[str, StringConstraints(min_length=1, max_length=2000)]


class ParameterBoundRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    lower: float
    start: float
    upper: float
    unit: str
    transform: Literal["ln"]

    def to_domain(self) -> ParameterBound:
        return ParameterBound(
            self.name, self.lower, self.start, self.upper, self.unit, self.transform
        )


class ExactRevisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID
    revision_id: UUID


class CalibrationWeightsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    relaxation_weight: str
    dma_storage_weight: str
    dma_loss_weight: str
    relaxation_scale_pa: str
    dma_storage_scale_pa: str
    dma_loss_scale_pa: str
    q_rule_version: str

    def to_domain(self) -> CalibrationWeights:
        return CalibrationWeights(**self.model_dump())


class OptimizerPolicyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    method: Literal["trf"]
    x_scale: Literal["jac"]
    transform: Literal["ln"]
    ftol: float
    xtol: float
    gtol: float
    max_nfev: int


class LinearViscoelasticPlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    test_data: ExactRevisionRequest
    selected_temperature_k: Decimal
    point_dispositions: tuple[PointDispositionRequest, ...] = Field(min_length=1)
    availability: ChannelAvailabilityRequest
    term_counts: tuple[int, ...] = Field(min_length=1)
    parameter_bounds: dict[int, tuple[ParameterBoundRequest, ...]]
    start_vectors: dict[int, tuple[tuple[float, ...], ...]]
    weights: CalibrationWeightsRequest
    optimizer: OptimizerPolicyRequest
    recommendation_policy: Literal["lowest_bic_then_term_count_then_attempt_ordinal@1.0.0"]
    change_reason: Reason

    def to_command(
        self, idempotency_key: str | None
    ) -> CreateGovernedLinearViscoelasticCalibrationPlan:
        return CreateGovernedLinearViscoelasticCalibrationPlan(
            test_data_id=self.test_data.id,
            test_data_revision_id=self.test_data.revision_id,
            selected_temperature_k=self.selected_temperature_k,
            point_dispositions=tuple(item.to_domain() for item in self.point_dispositions),
            availability=self.availability.to_domain(),
            term_counts=self.term_counts,
            parameter_bounds={
                key: tuple(item.to_domain() for item in values)
                for key, values in self.parameter_bounds.items()
            },
            start_vectors=self.start_vectors,
            weights=self.weights.to_domain(),
            recommendation_policy=self.recommendation_policy,
            ftol=self.optimizer.ftol,
            xtol=self.optimizer.xtol,
            gtol=self.optimizer.gtol,
            max_nfev=self.optimizer.max_nfev,
            change_reason=self.change_reason,
            idempotency_key=idempotency_key,
        )


class ProcessedLinearViscoelasticPlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    processing_output: ExactRevisionRequest
    availability: ChannelAvailabilityRequest
    term_counts: tuple[int, ...] = Field(min_length=1)
    parameter_bounds: dict[int, tuple[ParameterBoundRequest, ...]]
    start_vectors: dict[int, tuple[tuple[float, ...], ...]]
    weights: CalibrationWeightsRequest
    optimizer: OptimizerPolicyRequest
    recommendation_policy: Literal["lowest_bic_then_term_count_then_attempt_ordinal@1.0.0"]
    change_reason: Reason

    def to_command(
        self, idempotency_key: str | None
    ) -> CreateProcessedLinearViscoelasticCalibrationPlan:
        return CreateProcessedLinearViscoelasticCalibrationPlan(
            processing_output_id=self.processing_output.id,
            processing_output_revision_id=self.processing_output.revision_id,
            availability=self.availability.to_domain(),
            term_counts=self.term_counts,
            parameter_bounds={
                key: tuple(item.to_domain() for item in values)
                for key, values in self.parameter_bounds.items()
            },
            start_vectors=self.start_vectors,
            weights=self.weights.to_domain(),
            recommendation_policy=self.recommendation_policy,
            ftol=self.optimizer.ftol,
            xtol=self.optimizer.xtol,
            gtol=self.optimizer.gtol,
            max_nfev=self.optimizer.max_nfev,
            change_reason=self.change_reason,
            idempotency_key=idempotency_key,
        )


class PointDispositionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ordinal: int = Field(ge=0)
    partition: PointPartition
    exclusion_reason: str | None = Field(max_length=500)

    def to_domain(self) -> PointDisposition:
        return PointDisposition(self.ordinal, self.partition, self.exclusion_reason)


class ChannelAvailabilityRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ramp: DataAvailability
    sweep: DataAvailability
    preconditioning: DataAvailability
    linear_range: DataAvailability

    def to_domain(self) -> ChannelAvailability:
        return ChannelAvailability(**self.model_dump())


class RevisionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID
    aggregate_id: UUID
    revision_no: int = 1
    schema_id: str
    schema_version: str
    content_hash: str
    created_at: datetime
    created_by: UUID
    change_reason: str
    classification: DataClassification
    content: dict[str, Any]


class PlanResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    plan_id: UUID
    current_revision: RevisionResponse
    links: dict[str, str]

    @classmethod
    def from_domain(cls, value: CalibrationPlanSnapshot) -> PlanResponse:
        return cls(
            plan_id=value.id,
            current_revision=RevisionResponse(
                id=value.current.plan_revision_id,
                aggregate_id=value.id,
                schema_id=value.current.schema_id,
                schema_version=value.current.schema_version,
                content_hash=value.content_hash,
                created_at=value.created_at,
                created_by=value.created_by,
                change_reason=value.change_reason,
                classification=value.classification,
                content=value.current.canonical(),
            ),
            links={
                "self": f"/api/v1/linear-viscoelastic-calibration-plans/{value.id}",
                "runs": f"/api/v1/linear-viscoelastic-calibration-plans/{value.id}/runs",
            },
        )


class RunAcceptedResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    run_id: UUID
    job_id: UUID
    run_url: str
    job_url: str
    status: str = "queued"

    @classmethod
    def from_domain(cls, value: CalibrationJobReference) -> RunAcceptedResponse:
        return cls(
            run_id=value.run_id,
            job_id=value.job_id,
            run_url=value.run_url,
            job_url=value.job_url,
            status=value.status,
        )


class RunCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    plan_revision_id: UUID
    change_reason: Reason


class RunResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    run_id: UUID
    plan_revision_id: UUID
    status: str
    attempts: tuple[dict[str, Any], ...]
    candidates: tuple[dict[str, Any], ...]
    recommendation: dict[str, Any] | None
    failure_code: str | None
    failure_detail: str | None
    recovery_hint: str | None
    execution_ledger_sha256: str

    @classmethod
    def from_domain(cls, value: CalibrationRunProjection) -> RunResponse:
        result = value.result
        return cls(
            run_id=value.id,
            plan_revision_id=value.plan_revision_id,
            status=value.status,
            attempts=tuple(item.canonical() for item in result.attempts) if result else (),
            candidates=tuple(item.canonical() for item in result.candidates) if result else (),
            recommendation=result.recommendation.canonical()
            if result and result.recommendation
            else None,
            failure_code=value.failure_code,
            failure_detail=value.failure_detail,
            recovery_hint=value.recovery_hint,
            execution_ledger_sha256=value.execution_ledger_sha256,
        )


class SelectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    plan_revision_id: UUID
    run_id: UUID
    candidate_id: UUID
    candidate_sha256: str
    reason: Reason
    warning_acknowledgements: tuple[dict[str, Any], ...] = ()
    change_reason: Reason


class PromotionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    material: ExactRevisionRequest
    material_state: ExactRevisionRequest
    property_set: ExactRevisionRequest
    change_reason: Reason


class SelectionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    selection_id: UUID
    selection_revision_id: UUID
    plan_revision_id: UUID
    run_id: UUID
    candidate_id: UUID
    candidate_sha256: str
    reason: str
    warning_acknowledgements: tuple[dict[str, Any], ...]
    actor: UUID
    created_at: datetime

    @classmethod
    def from_domain(cls, value: CalibrationSelectionSnapshot) -> SelectionResponse:
        document = value.value.canonical()
        document["candidate_sha256"] = document.pop("candidate_digest")
        return cls.model_validate(document)


class LinearViscoelasticProblem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: str = "urn:cmp:problem:modeling:linear-viscoelastic-calibration"
    title: str
    status: int
    detail: str
    code: str
    location: str
    recovery_hint: str


class LinearViscoelasticHttpError(Exception):
    def __init__(
        self,
        context: SecurityContext,
        status_code: int,
        detail: str,
        *,
        code: str = "REQUEST_INVALID",
        location: str = "request",
        recovery_hint: str = "Review the exact immutable revision and create a new request.",
    ) -> None:
        self.problem = LinearViscoelasticProblem(
            status=status_code,
            title="Linear-viscoelastic calibration request failed",
            detail=detail,
            code=f"CMP-MODELING-{code}",
            location=location,
            recovery_hint=recovery_hint,
        )
        super().__init__(detail)


def _scope(request: Request) -> tuple[SecurityContext, AuthorizationDecision]:
    context = getattr(request.state, "security_context", None)
    decision = getattr(request.state, "authorization_decision", None)
    if not isinstance(context, SecurityContext) or not isinstance(decision, AuthorizationDecision):
        raise RuntimeError(
            "linear-viscoelastic calibration dependencies did not initialize request scope"
        )
    return context, decision


def _translate(context: SecurityContext, error: Exception) -> LinearViscoelasticHttpError:
    if isinstance(error, LinearViscoelasticCalibrationNotFound):
        return LinearViscoelasticHttpError(
            context,
            404,
            str(error),
            code="RESOURCE_NOT_FOUND",
            location="resource",
            recovery_hint="Use an exact visible revision; unavailable resources are never rebound.",
        )
    if isinstance(error, LinearViscoelasticCalibrationConflict):
        return LinearViscoelasticHttpError(
            context,
            409,
            str(error),
            code="IMMUTABLE_CONFLICT",
            location="revision_or_idempotency",
            recovery_hint="Read the exact current resource and create a new immutable request.",
        )
    if isinstance(error, ValueError):
        return LinearViscoelasticHttpError(
            context,
            422,
            str(error),
            code="REQUEST_INVALID",
            location="body",
            recovery_hint="Correct the typed channel, bound, start, or objective declaration.",
        )
    return LinearViscoelasticHttpError(
        context,
        503,
        "service is unavailable",
        code="SERVICE_UNAVAILABLE",
        location="service",
        recovery_hint="Retry after the modeling service is available.",
    )


def install_linear_viscoelastic_calibration_api(
    application: FastAPI,
    *,
    service: LinearViscoelasticCalibrationService | None,
    security_dependency: Dependency,
    read_dependency: Dependency,
    write_dependency: Dependency,
    execute_dependency: Dependency,
) -> None:
    @application.exception_handler(LinearViscoelasticHttpError)
    async def handle_error(_: Request, error: LinearViscoelasticHttpError) -> JSONResponse:
        return JSONResponse(error.problem.model_dump(mode="json"), status_code=error.problem.status)

    errors: dict[int | str, dict[str, Any]] = {
        code: {"model": LinearViscoelasticProblem} for code in (403, 404, 409, 422, 503)
    }

    @application.post(
        "/api/v1/linear-viscoelastic-calibration-plans",
        operation_id="createLinearViscoelasticCalibrationPlan",
        response_model=PlanResponse,
        status_code=status.HTTP_201_CREATED,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(execute_dependency)],
        tags=["modeling"],
    )
    def create_plan(
        request: Request,
        response: Response,
        body: LinearViscoelasticPlanRequest,
        idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    ) -> PlanResponse:
        context, decision = _scope(request)
        if service is None:
            raise LinearViscoelasticHttpError(
                context,
                503,
                "service is unavailable",
                code="SERVICE_UNAVAILABLE",
                location="service",
                recovery_hint="Retry after the modeling service is available.",
            )
        try:
            value = service.create_governed_plan(
                context,
                decision,
                body.to_command(idempotency_key),
            )
        except Exception as error:
            raise _translate(context, error) from error
        response.headers["Location"] = f"/api/v1/linear-viscoelastic-calibration-plans/{value.id}"
        return PlanResponse.from_domain(value)

    @application.get(
        "/api/v1/linear-viscoelastic-calibration-plans/{plan_id}",
        operation_id="getLinearViscoelasticCalibrationPlan",
        response_model=PlanResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["modeling"],
    )
    def get_plan(request: Request, plan_id: UUID) -> PlanResponse:
        context, decision = _scope(request)
        if service is None:
            raise LinearViscoelasticHttpError(
                context,
                503,
                "service is unavailable",
                code="SERVICE_UNAVAILABLE",
                location="service",
                recovery_hint="Retry after the modeling service is available.",
            )
        try:
            return PlanResponse.from_domain(service.get_plan(context, decision, plan_id))
        except Exception as error:
            raise _translate(context, error) from error

    @application.post(
        "/api/v1/linear-viscoelastic-calibration-plans/from-processing-output",
        operation_id="createLinearViscoelasticCalibrationPlanFromProcessingOutput",
        response_model=PlanResponse,
        status_code=status.HTTP_201_CREATED,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(execute_dependency)],
        tags=["modeling"],
    )
    def create_processed_plan(
        request: Request,
        response: Response,
        body: ProcessedLinearViscoelasticPlanRequest,
        idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    ) -> PlanResponse:
        context, decision = _scope(request)
        if service is None:
            raise LinearViscoelasticHttpError(
                context,
                503,
                "service is unavailable",
                code="SERVICE_UNAVAILABLE",
                location="service",
                recovery_hint="Retry after the modeling service is available.",
            )
        try:
            value = service.create_processed_plan(
                context,
                decision,
                body.to_command(idempotency_key),
            )
        except Exception as error:
            raise _translate(context, error) from error
        response.headers["Location"] = f"/api/v1/linear-viscoelastic-calibration-plans/{value.id}"
        return PlanResponse.from_domain(value)

    @application.post(
        "/api/v1/linear-viscoelastic-calibration-plans/{plan_id}/runs",
        operation_id="createLinearViscoelasticCalibrationRun",
        response_model=RunAcceptedResponse,
        status_code=status.HTTP_202_ACCEPTED,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(execute_dependency)],
        tags=["modeling"],
    )
    def queue_run(
        request: Request,
        plan_id: UUID,
        response: Response,
        body: RunCreateRequest,
        idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    ) -> RunAcceptedResponse:
        context, decision = _scope(request)
        if service is None:
            raise LinearViscoelasticHttpError(
                context,
                503,
                "service is unavailable",
                code="SERVICE_UNAVAILABLE",
                location="service",
                recovery_hint="Retry after the modeling service is available.",
            )
        try:
            value = service.queue_run(
                context,
                decision,
                QueueLinearViscoelasticCalibrationRun(
                    plan_id, body.plan_revision_id, body.change_reason, idempotency_key
                ),
            )
        except Exception as error:
            raise _translate(context, error) from error
        response.headers["Location"] = value.run_url
        return RunAcceptedResponse.from_domain(value)

    @application.get(
        "/api/v1/linear-viscoelastic-calibration-runs/{run_id}",
        operation_id="getLinearViscoelasticCalibrationRun",
        response_model=RunResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["modeling"],
    )
    def get_run(request: Request, run_id: UUID) -> RunResponse:
        context, decision = _scope(request)
        if service is None:
            raise LinearViscoelasticHttpError(
                context,
                503,
                "service is unavailable",
                code="SERVICE_UNAVAILABLE",
                location="service",
                recovery_hint="Retry after the modeling service is available.",
            )
        try:
            return RunResponse.from_domain(service.get_run(context, decision, run_id))
        except Exception as error:
            raise _translate(context, error) from error

    @application.get(
        "/api/v1/linear-viscoelastic-calibration-runs/{run_id}/candidates",
        operation_id="listLinearViscoelasticCalibrationCandidates",
        response_model=tuple[dict[str, Any], ...],
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["modeling"],
    )
    def list_candidates(request: Request, run_id: UUID) -> tuple[dict[str, Any], ...]:
        context, decision = _scope(request)
        if service is None:
            raise LinearViscoelasticHttpError(
                context,
                503,
                "service is unavailable",
                code="SERVICE_UNAVAILABLE",
                location="service",
                recovery_hint="Retry after the modeling service is available.",
            )
        try:
            return tuple(
                item.canonical() for item in service.list_candidates(context, decision, run_id)
            )
        except Exception as error:
            raise _translate(context, error) from error

    @application.get(
        "/api/v1/linear-viscoelastic-calibration-runs/{run_id}/recommendation",
        operation_id="getLinearViscoelasticCalibrationRecommendation",
        response_model=dict[str, Any] | None,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["modeling"],
    )
    def recommendation(request: Request, run_id: UUID) -> dict[str, Any] | None:
        context, decision = _scope(request)
        if service is None:
            raise LinearViscoelasticHttpError(
                context,
                503,
                "service is unavailable",
                code="SERVICE_UNAVAILABLE",
                location="service",
                recovery_hint="Retry after the modeling service is available.",
            )
        try:
            value = service.get_recommendation(context, decision, run_id)
            return value.canonical() if value else None
        except Exception as error:
            raise _translate(context, error) from error

    @application.post(
        "/api/v1/linear-viscoelastic-calibration-selections",
        operation_id="createLinearViscoelasticCalibrationSelection",
        response_model=SelectionResponse,
        status_code=status.HTTP_201_CREATED,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(write_dependency)],
        tags=["modeling"],
    )
    def create_selection(
        request: Request,
        response: Response,
        body: SelectionRequest,
        idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    ) -> SelectionResponse:
        context, decision = _scope(request)
        if service is None:
            raise LinearViscoelasticHttpError(
                context,
                503,
                "service is unavailable",
                code="SERVICE_UNAVAILABLE",
                location="service",
                recovery_hint="Retry after the modeling service is available.",
            )
        try:
            value = service.create_selection(
                context,
                decision,
                CreateLinearViscoelasticCalibrationSelection(
                    body.plan_revision_id,
                    body.run_id,
                    body.candidate_id,
                    body.candidate_sha256,
                    body.reason,
                    body.warning_acknowledgements,
                    body.change_reason,
                    idempotency_key,
                ),
            )
        except Exception as error:
            raise _translate(context, error) from error
        response.headers["Location"] = (
            f"/api/v1/linear-viscoelastic-calibration-selections/{value.value.selection_id}"
        )
        return SelectionResponse.from_domain(value)

    @application.get(
        "/api/v1/linear-viscoelastic-calibration-selections/{selection_id}",
        operation_id="getLinearViscoelasticCalibrationSelection",
        response_model=SelectionResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["modeling"],
    )
    def get_selection(request: Request, selection_id: UUID) -> SelectionResponse:
        context, decision = _scope(request)
        if service is None:
            raise LinearViscoelasticHttpError(
                context,
                503,
                "service is unavailable",
                code="SERVICE_UNAVAILABLE",
                location="service",
                recovery_hint="Retry after the modeling service is available.",
            )
        try:
            return SelectionResponse.from_domain(
                service.get_selection(context, decision, selection_id)
            )
        except Exception as error:
            raise _translate(context, error) from error

    @application.post(
        "/api/v1/linear-viscoelastic-calibration-selections/{selection_id}/linear-viscoelastic-model",
        operation_id="promoteLinearViscoelasticCalibrationSelection",
        response_model=LinearViscoelasticModelResponse,
        status_code=status.HTTP_201_CREATED,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(execute_dependency)],
        tags=["modeling"],
    )
    def promote_selection(
        request: Request,
        response: Response,
        selection_id: UUID,
        body: PromotionRequest,
    ) -> LinearViscoelasticModelResponse:
        context, decision = _scope(request)
        if service is None:
            raise LinearViscoelasticHttpError(
                context,
                503,
                "service is unavailable",
                code="SERVICE_UNAVAILABLE",
                location="service",
                recovery_hint="Retry after the modeling service is available.",
            )
        try:
            value = service.promote_selection(
                context,
                decision,
                PromoteLinearViscoelasticCalibrationSelection(
                    selection_id=selection_id,
                    material_id=body.material.id,
                    material_revision_id=body.material.revision_id,
                    material_state_id=body.material_state.id,
                    material_state_revision_id=body.material_state.revision_id,
                    property_set_id=body.property_set.id,
                    property_set_revision_id=body.property_set.revision_id,
                    change_reason=body.change_reason,
                ),
            )
        except Exception as error:
            raise _translate(context, error) from error
        response.headers["Location"] = f"/api/v1/linear-viscoelastic-models/{value.id}"
        return LinearViscoelasticModelResponse.from_snapshot(value)

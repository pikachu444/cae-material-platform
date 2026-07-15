"""Protected API for bounded reference Prony calibration."""

from __future__ import annotations

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
from cmp.modules.modeling.application.prony_calibration import (
    CreateReferencePronyCalibrationPlan,
    ExecuteReferencePronyCalibration,
    PersistedPronyCandidate,
    PronyCalibrationConflict,
    PronyCalibrationNotFound,
    PronyCalibrationPlanSnapshot,
    PronyCalibrationRun,
    ReferencePronyCalibrationService,
)
from cmp.modules.modeling.domain.reference_prony_calibration import (
    InvalidPronyCalibration,
    PronyParameterPlan,
    ReferencePronyCalibrationPlanContent,
)
from cmp.shared.contracts.revisions import RevisionETag, RevisionMetadataResponse

type Dependency = Callable[..., object]
type Reason = Annotated[str, StringConstraints(min_length=1, max_length=2000)]


class ParameterPlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lower: float
    initial: float
    upper: float


class PronyPlanCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    classification: DataClassification = DataClassification.INTERNAL
    plan_label: Annotated[str, StringConstraints(min_length=1, max_length=160)]
    input_dataset_id: UUID
    input_dataset_revision_id: UUID
    baseline_model_id: UUID
    baseline_model_revision_id: UUID
    total_g_ratio: ParameterPlanRequest
    fast_term_fraction: ParameterPlanRequest
    fast_relaxation_time_s: ParameterPlanRequest
    slow_relaxation_time_s: ParameterPlanRequest
    normalization_modulus_pa: Annotated[float, Field(gt=0)]
    multistart_count: Annotated[int, Field(ge=1, le=16)] = 4
    random_seed: Annotated[int, Field(ge=0, lt=2**63)] = 20260716
    maximum_function_evaluations: Annotated[int, Field(ge=10, le=1_000_000)] = 2_000
    ftol: Annotated[float, Field(gt=0, lt=1)] = 1e-10
    xtol: Annotated[float, Field(gt=0, lt=1)] = 1e-10
    gtol: Annotated[float, Field(gt=0, lt=1)] = 1e-10
    change_reason: Reason


class ExecutePronyCalibrationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_revision_id: UUID
    change_reason: Reason


class ParameterPlanResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    unit: str
    lower: float
    initial: float
    upper: float
    transform: str

    @classmethod
    def from_domain(cls, value: PronyParameterPlan) -> ParameterPlanResponse:
        return cls(**{name: getattr(value, name) for name in cls.model_fields})


class PronyPlanContentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_kind: str
    plan_label: str
    input_dataset_id: UUID
    input_dataset_revision_id: UUID
    baseline_model_id: UUID
    baseline_model_revision_id: UUID
    total_g_ratio: ParameterPlanResponse
    fast_term_fraction: ParameterPlanResponse
    fast_relaxation_time_s: ParameterPlanResponse
    slow_relaxation_time_s: ParameterPlanResponse
    normalization_modulus_pa: float
    multistart_count: int
    random_seed: int
    optimizer_adapter_id: str
    non_production: bool

    @classmethod
    def from_domain(
        cls, value: ReferencePronyCalibrationPlanContent
    ) -> PronyPlanContentResponse:
        return cls(
            plan_kind=value.plan_kind,
            plan_label=value.plan_label,
            input_dataset_id=value.input_dataset_id,
            input_dataset_revision_id=value.input_dataset_revision_id,
            baseline_model_id=value.baseline_model_id,
            baseline_model_revision_id=value.baseline_model_revision_id,
            total_g_ratio=ParameterPlanResponse.from_domain(value.total_g_ratio),
            fast_term_fraction=ParameterPlanResponse.from_domain(
                value.fast_term_fraction
            ),
            fast_relaxation_time_s=ParameterPlanResponse.from_domain(
                value.fast_relaxation_time_s
            ),
            slow_relaxation_time_s=ParameterPlanResponse.from_domain(
                value.slow_relaxation_time_s
            ),
            normalization_modulus_pa=value.normalization_modulus_pa,
            multistart_count=value.multistart_count,
            random_seed=value.random_seed,
            optimizer_adapter_id=value.optimizer_adapter_id,
            non_production=value.non_production,
        )


class PronyPlanRevisionResponse(RevisionMetadataResponse):
    content: PronyPlanContentResponse


class PronyPlanResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prony_calibration_plan_id: UUID
    current_revision: PronyPlanRevisionResponse
    links: dict[str, str]

    @classmethod
    def from_snapshot(cls, value: PronyCalibrationPlanSnapshot) -> PronyPlanResponse:
        metadata = RevisionMetadataResponse.from_record(value.current.record, "draft")
        root = f"/api/v1/prony-calibration-plans/{value.id}"
        return cls(
            prony_calibration_plan_id=value.id,
            current_revision=PronyPlanRevisionResponse(
                **metadata.model_dump(),
                content=PronyPlanContentResponse.from_domain(value.current.content),
            ),
            links={"self": root, "execute": f"{root}/runs"},
        )


class PronyCandidateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prony_calibration_candidate_id: UUID
    attempt_ordinal: int
    status: str
    candidate_sha256: str
    total_g_ratio: float
    fast_term_fraction: float
    fast_g_ratio: float
    slow_g_ratio: float
    fast_relaxation_time_s: float
    slow_relaxation_time_s: float
    objective_total: float
    residual_root_mean_square_pa: float
    residual_mean_pa: float
    convergence_reason: str
    function_evaluations: int
    optimality: float
    parameter_at_bound: bool
    identifiability_status: str
    uncertainty_status: str
    diagnostics_artifact_id: UUID
    diagnostics_point_count: int
    links: dict[str, str]

    @classmethod
    def from_domain(cls, value: PersistedPronyCandidate) -> PronyCandidateResponse:
        candidate = value.value
        root = f"/api/v1/prony-calibration-candidates/{value.id}"
        return cls(
            prony_calibration_candidate_id=value.id,
            attempt_ordinal=candidate.attempt_ordinal,
            status=candidate.status,
            candidate_sha256=f"sha256:{candidate.candidate_sha256}",
            total_g_ratio=candidate.total_g_ratio,
            fast_term_fraction=candidate.fast_term_fraction,
            fast_g_ratio=candidate.fast_g_ratio,
            slow_g_ratio=candidate.slow_g_ratio,
            fast_relaxation_time_s=candidate.fast_relaxation_time_s,
            slow_relaxation_time_s=candidate.slow_relaxation_time_s,
            objective_total=candidate.objective_total,
            residual_root_mean_square_pa=candidate.residual_root_mean_square_pa,
            residual_mean_pa=candidate.residual_mean_pa,
            convergence_reason=candidate.convergence_reason,
            function_evaluations=candidate.function_evaluations,
            optimality=candidate.optimality,
            parameter_at_bound=candidate.parameter_at_bound,
            identifiability_status=candidate.identifiability_status,
            uncertainty_status=candidate.uncertainty_status,
            diagnostics_artifact_id=value.diagnostics_artifact_id,
            diagnostics_point_count=value.diagnostics_point_count,
            links={"diagnostics": f"{root}/diagnostics"},
        )


class PronyRunResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prony_calibration_run_id: UUID
    status: str
    plan_id: UUID
    plan_revision_id: UUID
    input_dataset_id: UUID
    input_dataset_revision_id: UUID
    baseline_model_id: UUID
    baseline_model_revision_id: UUID
    environment_digest: str
    attempt_count: int
    candidate_count: int
    candidates: tuple[PronyCandidateResponse, ...]
    links: dict[str, str]

    @classmethod
    def from_domain(cls, value: PronyCalibrationRun) -> PronyRunResponse:
        root = f"/api/v1/prony-calibration-runs/{value.id}"
        return cls(
            prony_calibration_run_id=value.id,
            status=value.status.value,
            plan_id=value.plan_id,
            plan_revision_id=value.plan_revision_id,
            input_dataset_id=value.input_dataset_id,
            input_dataset_revision_id=value.input_dataset_revision_id,
            baseline_model_id=value.baseline_model_id,
            baseline_model_revision_id=value.baseline_model_revision_id,
            environment_digest=f"sha256:{value.environment_digest}",
            attempt_count=value.attempt_count,
            candidate_count=value.candidate_count,
            candidates=tuple(PronyCandidateResponse.from_domain(item) for item in value.candidates),
            links={"self": root},
        )


class DiagnosticPointResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    point_ordinal: int
    time_s: float
    observed_shear_modulus_pa: float
    predicted_shear_modulus_pa: float
    residual_pa: float


class PronyDiagnosticsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: UUID
    points: tuple[DiagnosticPointResponse, ...]


class PronyProblem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    title: str
    status: int
    detail: str
    code: str
    trace_id: str


class PronyHttpError(Exception):
    def __init__(self, context: SecurityContext, status_code: int, detail: str) -> None:
        self.problem = PronyProblem(
            type="urn:cmp:problem:modeling:reference-prony-calibration",
            title="Reference Prony calibration request failed",
            status=status_code,
            detail=detail,
            code=f"CMP-PRONY-{status_code}",
            trace_id=context.trace_id,
        )
        super().__init__(detail)


def _scope(request: Request) -> tuple[SecurityContext, AuthorizationDecision]:
    context = getattr(request.state, "security_context", None)
    decision = getattr(request.state, "authorization_decision", None)
    if not isinstance(context, SecurityContext) or not isinstance(
        decision, AuthorizationDecision
    ):
        raise RuntimeError("Prony calibration dependencies did not initialize request scope")
    return context, decision


def _translate(context: SecurityContext, error: Exception) -> PronyHttpError:
    if isinstance(error, PronyCalibrationNotFound):
        return PronyHttpError(context, 404, str(error))
    if isinstance(error, PronyCalibrationConflict):
        return PronyHttpError(context, 409, str(error))
    if isinstance(error, (InvalidPronyCalibration, ValueError)):
        return PronyHttpError(context, 422, str(error))
    return PronyHttpError(context, 503, "service is unavailable")


def _content(body: PronyPlanCreateRequest) -> ReferencePronyCalibrationPlanContent:
    def parameter(
        name: str, unit: str, transform: str, value: ParameterPlanRequest
    ) -> PronyParameterPlan:
        return PronyParameterPlan(
            name, unit, value.lower, value.initial, value.upper, transform
        )

    return ReferencePronyCalibrationPlanContent(
        plan_label=body.plan_label,
        input_dataset_id=body.input_dataset_id,
        input_dataset_revision_id=body.input_dataset_revision_id,
        baseline_model_id=body.baseline_model_id,
        baseline_model_revision_id=body.baseline_model_revision_id,
        total_g_ratio=parameter("total_g_ratio", "1", "none", body.total_g_ratio),
        fast_term_fraction=parameter(
            "fast_term_fraction", "1", "none", body.fast_term_fraction
        ),
        fast_relaxation_time_s=parameter(
            "fast_relaxation_time_s", "s", "log", body.fast_relaxation_time_s
        ),
        slow_relaxation_time_s=parameter(
            "slow_relaxation_time_s", "s", "log", body.slow_relaxation_time_s
        ),
        normalization_modulus_pa=body.normalization_modulus_pa,
        multistart_count=body.multistart_count,
        random_seed=body.random_seed,
        maximum_function_evaluations=body.maximum_function_evaluations,
        ftol=body.ftol,
        xtol=body.xtol,
        gtol=body.gtol,
    )


def install_prony_calibration_api(
    application: FastAPI,
    *,
    service: ReferencePronyCalibrationService | None,
    security_dependency: Dependency,
    read_dependency: Dependency,
    execute_dependency: Dependency,
) -> None:
    @application.exception_handler(PronyHttpError)
    async def handle_error(_: Request, error: PronyHttpError) -> JSONResponse:
        return JSONResponse(error.problem.model_dump(mode="json"), status_code=error.problem.status)

    errors: dict[int | str, dict[str, Any]] = {
        code: {"model": PronyProblem} for code in (404, 409, 422, 503)
    }

    @application.post(
        "/api/v1/prony-calibration-plans",
        operation_id="createReferencePronyCalibrationPlan",
        response_model=PronyPlanResponse,
        status_code=status.HTTP_201_CREATED,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(execute_dependency)],
        tags=["modeling"],
    )
    def create_plan(
        request: Request, response: Response, body: PronyPlanCreateRequest
    ) -> PronyPlanResponse:
        context, decision = _scope(request)
        if service is None:
            raise PronyHttpError(context, 503, "service is unavailable")
        try:
            value = service.create_plan(
                context,
                decision,
                CreateReferencePronyCalibrationPlan(
                    body.classification, _content(body), body.change_reason
                ),
            )
        except Exception as error:
            raise _translate(context, error) from error
        response.headers["ETag"] = str(RevisionETag.from_ref(value.current.record.ref))
        response.headers["Location"] = f"/api/v1/prony-calibration-plans/{value.id}"
        return PronyPlanResponse.from_snapshot(value)

    @application.post(
        "/api/v1/prony-calibration-plans/{plan_id}/runs",
        operation_id="executeReferencePronyCalibration",
        response_model=PronyRunResponse,
        status_code=status.HTTP_201_CREATED,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(execute_dependency)],
        tags=["modeling"],
    )
    async def execute(
        request: Request,
        response: Response,
        plan_id: UUID,
        body: ExecutePronyCalibrationRequest,
    ) -> PronyRunResponse:
        context, decision = _scope(request)
        if service is None:
            raise PronyHttpError(context, 503, "service is unavailable")
        try:
            value = await service.execute(
                context,
                decision,
                ExecuteReferencePronyCalibration(
                    plan_id, body.plan_revision_id, body.change_reason
                ),
            )
        except Exception as error:
            raise _translate(context, error) from error
        response.headers["Location"] = f"/api/v1/prony-calibration-runs/{value.id}"
        return PronyRunResponse.from_domain(value)

    @application.get(
        "/api/v1/prony-calibration-runs/{run_id}",
        operation_id="getReferencePronyCalibrationRun",
        response_model=PronyRunResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["modeling"],
    )
    def get_run(request: Request, run_id: UUID) -> PronyRunResponse:
        context, decision = _scope(request)
        if service is None:
            raise PronyHttpError(context, 503, "service is unavailable")
        try:
            return PronyRunResponse.from_domain(service.get_run(context, decision, run_id))
        except Exception as error:
            raise _translate(context, error) from error

    @application.get(
        "/api/v1/prony-calibration-candidates/{candidate_id}/diagnostics",
        operation_id="getReferencePronyCandidateDiagnostics",
        response_model=PronyDiagnosticsResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["modeling"],
    )
    async def diagnostics(request: Request, candidate_id: UUID) -> PronyDiagnosticsResponse:
        context, decision = _scope(request)
        if service is None:
            raise PronyHttpError(context, 503, "service is unavailable")
        try:
            rows = await service.candidate_diagnostics(context, decision, candidate_id)
        except Exception as error:
            raise _translate(context, error) from error
        return PronyDiagnosticsResponse(
            candidate_id=candidate_id,
            points=tuple(
                DiagnosticPointResponse(
                    point_ordinal=int(row["point_ordinal"]),
                    time_s=float(row["time_s"]),
                    observed_shear_modulus_pa=float(
                        row["observed_shear_modulus_pa"]
                    ),
                    predicted_shear_modulus_pa=float(
                        row["predicted_shear_modulus_pa"]
                    ),
                    residual_pa=float(row["residual_pa"]),
                )
                for row in rows
            ),
        )

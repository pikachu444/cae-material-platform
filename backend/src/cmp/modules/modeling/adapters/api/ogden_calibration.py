"""Protected API for governed multi-test reference Ogden calibration."""

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
from cmp.modules.modeling.application.ogden_calibration import (
    CreateReferenceOgdenCalibrationPlan,
    ExecuteReferenceOgdenCalibration,
    OgdenCalibrationConflict,
    OgdenCalibrationNotFound,
    OgdenCalibrationPlanSnapshot,
    OgdenCalibrationRun,
    PersistedHyperelasticFamilyCandidate,
    PersistedOgdenCandidate,
    ReferenceOgdenCalibrationService,
)
from cmp.modules.modeling.domain.hyperelastic_families import HyperelasticDiagnosticPoint
from cmp.modules.modeling.domain.reference_ogden_calibration import (
    InvalidOgdenCalibration,
    OgdenCalibrationMember,
    OgdenCalibrationRole,
    OgdenDiagnosticPoint,
    OgdenTestMode,
    ReferenceOgdenCalibrationPlanContent,
)
from cmp.shared.contracts.revisions import RevisionETag, RevisionMetadataResponse
from cmp.shared.domain.revisions import AggregateAlreadyExists

logger = logging.getLogger(__name__)

type Dependency = Callable[..., object]
type Reason = Annotated[str, StringConstraints(min_length=1, max_length=2000)]


class OgdenMemberRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: OgdenCalibrationRole
    test_mode: OgdenTestMode
    dataset_id: UUID
    dataset_revision_id: UUID
    weight: Annotated[float, Field(gt=0)] = 1.0


class OgdenPlanCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    classification: DataClassification = DataClassification.INTERNAL
    plan_label: Annotated[str, StringConstraints(min_length=1, max_length=160)]
    scientific_profile_id: UUID
    scientific_profile_revision_id: UUID
    material_state_id: UUID
    material_state_revision_id: UUID
    baseline_model_id: UUID
    baseline_model_revision_id: UUID
    members: Annotated[tuple[OgdenMemberRequest, ...], Field(min_length=1, max_length=24)]
    change_reason: Reason


class ExecuteOgdenCalibrationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_revision_id: UUID
    change_reason: Reason


class OgdenMemberResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ordinal: int
    role: str
    test_mode: str
    dataset_id: UUID
    dataset_revision_id: UUID
    weight: float

    @classmethod
    def from_domain(cls, value: OgdenCalibrationMember) -> OgdenMemberResponse:
        return cls(
            ordinal=value.ordinal,
            role=value.role.value,
            test_mode=value.test_mode.value,
            dataset_id=value.dataset_id,
            dataset_revision_id=value.dataset_revision_id,
            weight=value.weight,
        )


class OgdenPlanContentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_label: str
    scientific_profile_id: UUID
    scientific_profile_revision_id: UUID
    material_state_id: UUID
    material_state_revision_id: UUID
    baseline_model_id: UUID
    baseline_model_revision_id: UUID
    members: tuple[OgdenMemberResponse, ...]
    evaluator: str
    objective: str
    aggregation_order: str
    holdout_policy: str
    maximum_function_evaluations: int
    non_production: bool

    @classmethod
    def from_domain(
        cls, value: ReferenceOgdenCalibrationPlanContent
    ) -> OgdenPlanContentResponse:
        return cls(
            plan_label=value.plan_label,
            scientific_profile_id=value.scientific_profile_id,
            scientific_profile_revision_id=value.scientific_profile_revision_id,
            material_state_id=value.material_state_id,
            material_state_revision_id=value.material_state_revision_id,
            baseline_model_id=value.baseline_model_id,
            baseline_model_revision_id=value.baseline_model_revision_id,
            members=tuple(OgdenMemberResponse.from_domain(item) for item in value.members),
            evaluator=value.evaluator,
            objective=value.objective,
            aggregation_order=value.aggregation_order,
            holdout_policy=value.holdout_policy,
            maximum_function_evaluations=value.maximum_function_evaluations,
            non_production=value.non_production,
        )


class OgdenPlanRevisionResponse(RevisionMetadataResponse):
    content: OgdenPlanContentResponse


class OgdenPlanResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ogden_calibration_plan_id: UUID
    current_revision: OgdenPlanRevisionResponse
    links: dict[str, str]

    @classmethod
    def from_snapshot(cls, value: OgdenCalibrationPlanSnapshot) -> OgdenPlanResponse:
        metadata = RevisionMetadataResponse.from_record(value.current.record, "draft")
        root = f"/api/v1/ogden-calibration-plans/{value.id}"
        return cls(
            ogden_calibration_plan_id=value.id,
            current_revision=OgdenPlanRevisionResponse(
                **metadata.model_dump(),
                content=OgdenPlanContentResponse.from_domain(value.current.content),
            ),
            links={"self": root, "execute": f"{root}/runs"},
        )


class OgdenCandidateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ogden_calibration_candidate_id: UUID
    attempt_ordinal: int
    status: str
    candidate_sha256: str
    initial_mu_pa: float
    initial_alpha: float
    mu_pa: float
    alpha: float
    objective_total: float
    objective_by_mode: dict[str, float]
    calibration_rmse_pa: float
    calibration_normalized_rmse: float
    holdout_rmse_pa: float | None
    holdout_normalized_rmse: float | None
    convergence_status_code: int
    convergence_reason: str
    function_evaluations: int
    jacobian_evaluations: int | None
    optimality: float
    parameter_at_bound: bool
    jacobian_rank: int
    jacobian_condition_number: float | None
    identifiability_status: str
    uncertainty_status: str
    mu_standard_error_pa: float | None
    alpha_standard_error: float | None
    mu_confidence_interval_pa: tuple[float, float] | None
    alpha_confidence_interval: tuple[float, float] | None
    warnings: tuple[str, ...]
    diagnostics_artifact_id: UUID
    diagnostics_point_count: int
    links: dict[str, str]

    @classmethod
    def from_domain(cls, value: PersistedOgdenCandidate) -> OgdenCandidateResponse:
        candidate = value.value
        root = f"/api/v1/ogden-calibration-candidates/{value.id}"
        mu_interval = (
            (candidate.mu_confidence_lower_pa, candidate.mu_confidence_upper_pa)
            if candidate.mu_confidence_lower_pa is not None
            and candidate.mu_confidence_upper_pa is not None
            else None
        )
        alpha_interval = (
            (candidate.alpha_confidence_lower, candidate.alpha_confidence_upper)
            if candidate.alpha_confidence_lower is not None
            and candidate.alpha_confidence_upper is not None
            else None
        )
        return cls(
            ogden_calibration_candidate_id=value.id,
            attempt_ordinal=candidate.attempt_ordinal,
            status=candidate.status,
            candidate_sha256=f"sha256:{candidate.candidate_sha256}",
            initial_mu_pa=candidate.initial_mu_pa,
            initial_alpha=candidate.initial_alpha,
            mu_pa=candidate.mu_pa,
            alpha=candidate.alpha,
            objective_total=candidate.objective_total,
            objective_by_mode={
                "uniaxial_tension": candidate.uniaxial_objective,
                "planar_tension": candidate.planar_objective,
                "biaxial_tension": candidate.biaxial_objective,
            },
            calibration_rmse_pa=candidate.calibration_rmse_pa,
            calibration_normalized_rmse=candidate.calibration_normalized_rmse,
            holdout_rmse_pa=candidate.holdout_rmse_pa,
            holdout_normalized_rmse=candidate.holdout_normalized_rmse,
            convergence_status_code=candidate.convergence_status_code,
            convergence_reason=candidate.convergence_reason,
            function_evaluations=candidate.function_evaluations,
            jacobian_evaluations=candidate.jacobian_evaluations,
            optimality=candidate.optimality,
            parameter_at_bound=candidate.parameter_at_bound,
            jacobian_rank=candidate.jacobian_rank,
            jacobian_condition_number=candidate.jacobian_condition_number,
            identifiability_status=candidate.identifiability_status,
            uncertainty_status=candidate.uncertainty_status,
            mu_standard_error_pa=candidate.mu_standard_error_pa,
            alpha_standard_error=candidate.alpha_standard_error,
            mu_confidence_interval_pa=mu_interval,
            alpha_confidence_interval=alpha_interval,
            warnings=candidate.warnings,
            diagnostics_artifact_id=value.diagnostics_artifact_id,
            diagnostics_point_count=value.diagnostics_point_count,
            links={"diagnostics": f"{root}/diagnostics"},
        )


class HyperelasticParameterResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    value: float
    unit: str


class HyperelasticFamilyCandidateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hyperelastic_family_candidate_id: UUID
    family: str
    parameters: tuple[HyperelasticParameterResponse, ...]
    objective_total: float
    objective_by_mode: dict[str, float]
    calibration_normalized_rmse: float
    holdout_normalized_rmse: float | None
    function_evaluations: int
    convergence_reason: str
    stability_status: str
    warnings: tuple[str, ...]
    candidate_sha256: str
    diagnostics_artifact_id: UUID | None
    diagnostics_point_count: int
    links: dict[str, str]

    @classmethod
    def from_domain(
        cls, value: PersistedHyperelasticFamilyCandidate
    ) -> HyperelasticFamilyCandidateResponse:
        candidate = value.value
        return cls(
            hyperelastic_family_candidate_id=value.id,
            family=candidate.family.value,
            parameters=tuple(
                HyperelasticParameterResponse(
                    name=parameter.name,
                    value=parameter.value,
                    unit=parameter.unit,
                )
                for parameter in candidate.parameters
            ),
            objective_total=candidate.objective_total,
            objective_by_mode={
                mode.value: objective for mode, objective in candidate.objective_by_mode
            },
            calibration_normalized_rmse=candidate.calibration_normalized_rmse,
            holdout_normalized_rmse=candidate.holdout_normalized_rmse,
            function_evaluations=candidate.function_evaluations,
            convergence_reason=candidate.convergence_reason,
            stability_status=candidate.stability_status,
            warnings=candidate.warnings,
            candidate_sha256=f"sha256:{candidate.candidate_sha256}",
            diagnostics_artifact_id=value.diagnostics_artifact_id,
            diagnostics_point_count=value.diagnostics_point_count,
            links={
                "diagnostics": (
                    f"/api/v1/hyperelastic-family-candidates/{value.id}/diagnostics"
                )
            }
            if value.diagnostics_artifact_id is not None
            else {},
        )


class OgdenRunResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ogden_calibration_run_id: UUID
    status: str
    plan_id: UUID
    plan_revision_id: UUID
    scientific_profile_id: UUID
    scientific_profile_revision_id: UUID
    material_state_id: UUID
    material_state_revision_id: UUID
    baseline_model_id: UUID
    baseline_model_revision_id: UUID
    environment_digest: str
    calibration_curve_count: int
    holdout_curve_count: int
    test_mode_count: int
    attempt_count: int
    candidate_count: int
    candidates: tuple[OgdenCandidateResponse, ...]
    family_candidate_count: int
    family_candidates: tuple[HyperelasticFamilyCandidateResponse, ...]
    links: dict[str, str]

    @classmethod
    def from_domain(cls, value: OgdenCalibrationRun) -> OgdenRunResponse:
        root = f"/api/v1/ogden-calibration-runs/{value.id}"
        return cls(
            ogden_calibration_run_id=value.id,
            status=value.status.value,
            plan_id=value.plan_id,
            plan_revision_id=value.plan_revision_id,
            scientific_profile_id=value.scientific_profile_id,
            scientific_profile_revision_id=value.scientific_profile_revision_id,
            material_state_id=value.material_state_id,
            material_state_revision_id=value.material_state_revision_id,
            baseline_model_id=value.baseline_model_id,
            baseline_model_revision_id=value.baseline_model_revision_id,
            environment_digest=value.environment_digest,
            calibration_curve_count=value.calibration_curve_count,
            holdout_curve_count=value.holdout_curve_count,
            test_mode_count=value.test_mode_count,
            attempt_count=value.attempt_count,
            candidate_count=value.candidate_count,
            candidates=tuple(
                OgdenCandidateResponse.from_domain(item) for item in value.candidates
            ),
            family_candidate_count=len(value.family_candidates),
            family_candidates=tuple(
                HyperelasticFamilyCandidateResponse.from_domain(item)
                for item in value.family_candidates
            ),
            links={"self": root},
        )


class OgdenDiagnosticPointResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    member_ordinal: int
    role: str
    test_mode: str
    dataset_id: UUID
    dataset_revision_id: UUID
    point_ordinal: int
    engineering_strain: float
    stretch: float
    observed_nominal_stress_pa: float
    predicted_nominal_stress_pa: float
    residual_pa: float
    normalized_residual: float
    effective_weight: float

    @classmethod
    def from_domain(cls, value: OgdenDiagnosticPoint) -> OgdenDiagnosticPointResponse:
        return cls(
            member_ordinal=value.member_ordinal,
            role=value.role.value,
            test_mode=value.test_mode.value,
            dataset_id=value.dataset_id,
            dataset_revision_id=value.dataset_revision_id,
            point_ordinal=value.point_ordinal,
            engineering_strain=value.engineering_strain,
            stretch=value.stretch,
            observed_nominal_stress_pa=value.observed_nominal_stress_pa,
            predicted_nominal_stress_pa=value.predicted_nominal_stress_pa,
            residual_pa=value.residual_pa,
            normalized_residual=value.normalized_residual,
            effective_weight=value.effective_weight,
        )


class OgdenDiagnosticsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: UUID
    points: tuple[OgdenDiagnosticPointResponse, ...]


class HyperelasticDiagnosticPointResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    family: str
    member_ordinal: int
    role: str
    test_mode: str
    dataset_id: UUID
    dataset_revision_id: UUID
    point_ordinal: int
    engineering_strain: float
    stretch: float
    observed_nominal_stress_pa: float
    predicted_nominal_stress_pa: float
    residual_pa: float
    normalized_residual: float
    effective_weight: float

    @classmethod
    def from_domain(
        cls, value: HyperelasticDiagnosticPoint
    ) -> HyperelasticDiagnosticPointResponse:
        return cls(
            family=value.family.value,
            member_ordinal=value.member_ordinal,
            role=value.role.value,
            test_mode=value.test_mode.value,
            dataset_id=value.dataset_id,
            dataset_revision_id=value.dataset_revision_id,
            point_ordinal=value.point_ordinal,
            engineering_strain=value.engineering_strain,
            stretch=1.0 + value.engineering_strain,
            observed_nominal_stress_pa=value.observed_nominal_stress_pa,
            predicted_nominal_stress_pa=value.predicted_nominal_stress_pa,
            residual_pa=value.residual_pa,
            normalized_residual=value.normalized_residual,
            effective_weight=value.effective_weight,
        )


class HyperelasticDiagnosticsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: UUID
    points: tuple[HyperelasticDiagnosticPointResponse, ...]


class OgdenProblem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    title: str
    status: int
    detail: str
    code: str
    trace_id: str


class OgdenHttpError(Exception):
    def __init__(self, context: SecurityContext, status_code: int, detail: str) -> None:
        self.problem = OgdenProblem(
            type="urn:cmp:problem:modeling:reference-ogden-calibration",
            title="Reference Ogden calibration request failed",
            status=status_code,
            detail=detail,
            code=f"CMP-OGDEN-{status_code}",
            trace_id=context.trace_id,
        )
        super().__init__(detail)


def _scope(request: Request) -> tuple[SecurityContext, AuthorizationDecision]:
    context = getattr(request.state, "security_context", None)
    decision = getattr(request.state, "authorization_decision", None)
    if not isinstance(context, SecurityContext) or not isinstance(
        decision, AuthorizationDecision
    ):
        raise RuntimeError("Ogden calibration dependencies did not initialize request scope")
    return context, decision


def _translate(context: SecurityContext, error: Exception) -> OgdenHttpError:
    if isinstance(error, OgdenCalibrationNotFound):
        return OgdenHttpError(context, 404, str(error))
    if isinstance(error, OgdenCalibrationConflict):
        return OgdenHttpError(context, 409, str(error))
    if isinstance(error, AggregateAlreadyExists):
        return OgdenHttpError(
            context,
            409,
            "a Calibration Plan with this label already exists for the same State "
            "and baseline model",
        )
    if isinstance(error, (InvalidOgdenCalibration, ValueError)):
        return OgdenHttpError(context, 422, str(error))
    logger.exception("unexpected Ogden calibration API failure", exc_info=error)
    return OgdenHttpError(context, 503, "service is unavailable")


def _content(body: OgdenPlanCreateRequest) -> ReferenceOgdenCalibrationPlanContent:
    return ReferenceOgdenCalibrationPlanContent(
        plan_label=body.plan_label,
        scientific_profile_id=body.scientific_profile_id,
        scientific_profile_revision_id=body.scientific_profile_revision_id,
        material_state_id=body.material_state_id,
        material_state_revision_id=body.material_state_revision_id,
        baseline_model_id=body.baseline_model_id,
        baseline_model_revision_id=body.baseline_model_revision_id,
        members=tuple(
            OgdenCalibrationMember(
                ordinal=ordinal,
                role=item.role,
                test_mode=item.test_mode,
                dataset_id=item.dataset_id,
                dataset_revision_id=item.dataset_revision_id,
                weight=item.weight,
            )
            for ordinal, item in enumerate(body.members)
        ),
    )


def install_ogden_calibration_api(
    application: FastAPI,
    *,
    service: ReferenceOgdenCalibrationService | None,
    security_dependency: Dependency,
    read_dependency: Dependency,
    execute_dependency: Dependency,
) -> None:
    @application.exception_handler(OgdenHttpError)
    async def handle_error(_: Request, error: OgdenHttpError) -> JSONResponse:
        return JSONResponse(
            error.problem.model_dump(mode="json"), status_code=error.problem.status
        )

    errors: dict[int | str, dict[str, Any]] = {
        code: {"model": OgdenProblem} for code in (404, 409, 422, 503)
    }

    @application.post(
        "/api/v1/ogden-calibration-plans",
        operation_id="createReferenceOgdenCalibrationPlan",
        response_model=OgdenPlanResponse,
        status_code=status.HTTP_201_CREATED,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(execute_dependency)],
        tags=["modeling"],
    )
    def create_plan(
        request: Request, response: Response, body: OgdenPlanCreateRequest
    ) -> OgdenPlanResponse:
        context, decision = _scope(request)
        if service is None:
            raise OgdenHttpError(context, 503, "service is unavailable")
        try:
            value = service.create_plan(
                context,
                decision,
                CreateReferenceOgdenCalibrationPlan(
                    body.classification, _content(body), body.change_reason
                ),
            )
        except Exception as error:
            raise _translate(context, error) from error
        response.headers["ETag"] = str(RevisionETag.from_ref(value.current.record.ref))
        response.headers["Location"] = f"/api/v1/ogden-calibration-plans/{value.id}"
        return OgdenPlanResponse.from_snapshot(value)

    @application.post(
        "/api/v1/ogden-calibration-plans/{plan_id}/runs",
        operation_id="executeReferenceOgdenCalibration",
        response_model=OgdenRunResponse,
        status_code=status.HTTP_201_CREATED,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(execute_dependency)],
        tags=["modeling"],
    )
    async def execute(
        request: Request,
        response: Response,
        plan_id: UUID,
        body: ExecuteOgdenCalibrationRequest,
    ) -> OgdenRunResponse:
        context, decision = _scope(request)
        if service is None:
            raise OgdenHttpError(context, 503, "service is unavailable")
        try:
            value = await service.execute(
                context,
                decision,
                ExecuteReferenceOgdenCalibration(
                    plan_id, body.plan_revision_id, body.change_reason
                ),
            )
        except Exception as error:
            raise _translate(context, error) from error
        response.headers["Location"] = f"/api/v1/ogden-calibration-runs/{value.id}"
        return OgdenRunResponse.from_domain(value)

    @application.get(
        "/api/v1/ogden-calibration-runs/{run_id}",
        operation_id="getReferenceOgdenCalibrationRun",
        response_model=OgdenRunResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["modeling"],
    )
    def get_run(request: Request, run_id: UUID) -> OgdenRunResponse:
        context, decision = _scope(request)
        if service is None:
            raise OgdenHttpError(context, 503, "service is unavailable")
        try:
            return OgdenRunResponse.from_domain(service.get_run(context, decision, run_id))
        except Exception as error:
            raise _translate(context, error) from error

    @application.get(
        "/api/v1/ogden-calibration-candidates/{candidate_id}/diagnostics",
        operation_id="getReferenceOgdenCandidateDiagnostics",
        response_model=OgdenDiagnosticsResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["modeling"],
    )
    async def diagnostics(
        request: Request, candidate_id: UUID
    ) -> OgdenDiagnosticsResponse:
        context, decision = _scope(request)
        if service is None:
            raise OgdenHttpError(context, 503, "service is unavailable")
        try:
            points = await service.candidate_diagnostics(context, decision, candidate_id)
        except Exception as error:
            raise _translate(context, error) from error
        return OgdenDiagnosticsResponse(
            candidate_id=candidate_id,
            points=tuple(OgdenDiagnosticPointResponse.from_domain(item) for item in points),
        )

    @application.get(
        "/api/v1/hyperelastic-family-candidates/{candidate_id}/diagnostics",
        operation_id="getHyperelasticFamilyCandidateDiagnostics",
        response_model=HyperelasticDiagnosticsResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["modeling"],
    )
    async def family_diagnostics(
        request: Request, candidate_id: UUID
    ) -> HyperelasticDiagnosticsResponse:
        context, decision = _scope(request)
        if service is None:
            raise OgdenHttpError(context, 503, "service is unavailable")
        try:
            points = await service.family_candidate_diagnostics(
                context, decision, candidate_id
            )
        except Exception as error:
            raise _translate(context, error) from error
        return HyperelasticDiagnosticsResponse(
            candidate_id=candidate_id,
            points=tuple(
                HyperelasticDiagnosticPointResponse.from_domain(item) for item in points
            ),
        )

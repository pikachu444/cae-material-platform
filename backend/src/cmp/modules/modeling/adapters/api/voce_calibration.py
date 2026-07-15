"""Protected HTTP resources for multi-curve reference Voce calibration."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.modeling.application.service import RevisionSnapshot
from cmp.modules.modeling.application.voce_calibration import (
    CreateReferenceVoceCalibrationPlan,
    ExecuteReferenceVoceCalibration,
    ReferenceVoceCalibrationService,
    ReviseReferenceVoceCalibrationPlan,
    VoceCalibrationAttempt,
    VoceCalibrationCandidate,
    VoceCalibrationConflict,
    VoceCalibrationDiagnosticPreview,
    VoceCalibrationNotFound,
    VoceCalibrationPlanSnapshot,
    VoceCalibrationRunDetail,
)
from cmp.modules.modeling.domain.reference_voce_calibration import (
    InvalidVoceCalibration,
    ReferenceVoceCalibrationPlanContent,
    VoceDiagnosticPoint,
    VoceObjectiveTerm,
    VoceParameterPlan,
)
from cmp.shared.contracts.revisions import RevisionETag, RevisionMetadataResponse
from cmp.shared.domain.revisions import RevisionKernelError

type Dependency = Callable[..., object]
type Reason = Annotated[str, StringConstraints(min_length=1, max_length=2000)]


class VoceParameterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lower: Annotated[float, Field(gt=0)]
    initial: Annotated[float, Field(gt=0)]
    upper: Annotated[float, Field(gt=0)]
    scale: Annotated[float, Field(gt=0)]


class VocePlanContentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_label: Annotated[str, StringConstraints(min_length=1, max_length=160)]
    calibration_input_scope_id: UUID
    calibration_input_scope_revision_id: UUID
    material_state_id: UUID
    material_state_revision_id: UUID
    property_set_id: UUID
    property_set_revision_id: UUID
    youngs_modulus_pa: Annotated[float, Field(gt=0)]
    sigma_0_pa: VoceParameterRequest
    q_pa: VoceParameterRequest
    b: VoceParameterRequest
    normalization_stress_scale_pa: Annotated[float, Field(gt=0)]
    multistart_count: Annotated[int, Field(ge=1, le=16)] = 3
    random_seed: Annotated[int, Field(ge=0, lt=2**63)] = 0
    maximum_function_evaluations: Annotated[int, Field(ge=10, le=1_000_000)] = 2_000
    ftol: Annotated[float, Field(gt=0, lt=1)] = 1e-10
    xtol: Annotated[float, Field(gt=0, lt=1)] = 1e-10
    gtol: Annotated[float, Field(gt=0, lt=1)] = 1e-10

    def content(self) -> ReferenceVoceCalibrationPlanContent:
        return ReferenceVoceCalibrationPlanContent(
            plan_label=self.plan_label,
            calibration_input_scope_id=self.calibration_input_scope_id,
            calibration_input_scope_revision_id=self.calibration_input_scope_revision_id,
            material_state_id=self.material_state_id,
            material_state_revision_id=self.material_state_revision_id,
            property_set_id=self.property_set_id,
            property_set_revision_id=self.property_set_revision_id,
            youngs_modulus_pa=self.youngs_modulus_pa,
            sigma_0=VoceParameterPlan("sigma_0_pa", "Pa", **self.sigma_0_pa.model_dump()),
            q=VoceParameterPlan("q_pa", "Pa", **self.q_pa.model_dump()),
            b=VoceParameterPlan("b", "1", **self.b.model_dump()),
            normalization_stress_scale_pa=self.normalization_stress_scale_pa,
            multistart_count=self.multistart_count,
            random_seed=self.random_seed,
            maximum_function_evaluations=self.maximum_function_evaluations,
            ftol=self.ftol,
            xtol=self.xtol,
            gtol=self.gtol,
        )


class VocePlanCreateRequest(VocePlanContentRequest):
    classification: DataClassification
    change_reason: Reason


class VocePlanReviseRequest(VocePlanContentRequest):
    expected_current_revision_id: UUID
    change_reason: Reason


class VoceExecuteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_revision_id: UUID
    change_reason: Reason


class VoceParameterResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    unit: str
    lower: float
    initial: float
    upper: float
    scale: float
    transform: str

    @classmethod
    def from_domain(cls, value: VoceParameterPlan) -> VoceParameterResponse:
        return cls(
            name=value.name,
            unit=value.unit,
            lower=value.lower,
            initial=value.initial,
            upper=value.upper,
            scale=value.scale,
            transform=value.transform,
        )


class VocePlanContentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_kind: str
    plan_label: str
    calibration_input_scope_id: UUID
    calibration_input_scope_revision_id: UUID
    material_state_id: UUID
    material_state_revision_id: UUID
    property_set_id: UUID
    property_set_revision_id: UUID
    youngs_modulus_pa: float
    parameters: tuple[VoceParameterResponse, ...]
    normalization_stress_scale_pa: float
    multistart_count: int
    random_seed: int
    maximum_function_evaluations: int
    ftol: float
    xtol: float
    gtol: float
    model_family_id: str
    test_mode_adapter_id: str
    evaluator_id: str
    objective_engine_id: str
    optimizer_adapter_id: str
    evaluation_mode: str
    residual_definition: str
    specimen_weighting: str
    point_weighting: str
    objective_aggregation: str
    x_domain_policy: str
    missing_data_policy: str
    optimizer_method: str
    rng_algorithm: str
    non_production: bool

    @classmethod
    def from_domain(cls, value: ReferenceVoceCalibrationPlanContent) -> VocePlanContentResponse:
        return cls(
            plan_kind=value.plan_kind,
            plan_label=value.plan_label,
            calibration_input_scope_id=value.calibration_input_scope_id,
            calibration_input_scope_revision_id=value.calibration_input_scope_revision_id,
            material_state_id=value.material_state_id,
            material_state_revision_id=value.material_state_revision_id,
            property_set_id=value.property_set_id,
            property_set_revision_id=value.property_set_revision_id,
            youngs_modulus_pa=value.youngs_modulus_pa,
            parameters=tuple(
                VoceParameterResponse.from_domain(item)
                for item in (value.sigma_0, value.q, value.b)
            ),
            normalization_stress_scale_pa=value.normalization_stress_scale_pa,
            multistart_count=value.multistart_count,
            random_seed=value.random_seed,
            maximum_function_evaluations=value.maximum_function_evaluations,
            ftol=value.ftol,
            xtol=value.xtol,
            gtol=value.gtol,
            model_family_id=value.model_family_id,
            test_mode_adapter_id=value.test_mode_adapter_id,
            evaluator_id=value.evaluator_id,
            objective_engine_id=value.objective_engine_id,
            optimizer_adapter_id=value.optimizer_adapter_id,
            evaluation_mode=value.evaluation_mode,
            residual_definition=value.residual_definition,
            specimen_weighting=value.specimen_weighting,
            point_weighting=value.point_weighting,
            objective_aggregation=value.objective_aggregation,
            x_domain_policy=value.x_domain_policy,
            missing_data_policy=value.missing_data_policy,
            optimizer_method=value.optimizer_method,
            rng_algorithm=value.rng_algorithm,
            non_production=value.non_production,
        )


class VocePlanRevisionResponse(RevisionMetadataResponse):
    content: VocePlanContentResponse

    @classmethod
    def from_snapshot(
        cls, value: RevisionSnapshot[ReferenceVoceCalibrationPlanContent]
    ) -> VocePlanRevisionResponse:
        metadata = RevisionMetadataResponse.from_record(value.record, "draft")
        return cls(
            **metadata.model_dump(), content=VocePlanContentResponse.from_domain(value.content)
        )


class VocePlanResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    voce_calibration_plan_id: UUID
    current_revision: VocePlanRevisionResponse

    @classmethod
    def from_snapshot(cls, value: VoceCalibrationPlanSnapshot) -> VocePlanResponse:
        return cls(
            voce_calibration_plan_id=value.id,
            current_revision=VocePlanRevisionResponse.from_snapshot(value.current),
        )


class VocePlanListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: tuple[VocePlanResponse, ...]


class VoceObjectiveTermResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    member_ordinal: int
    dataset_id: UUID
    dataset_revision_id: UUID
    point_count: int
    mean_normalized_squared_residual: float

    @classmethod
    def from_domain(cls, value: VoceObjectiveTerm) -> VoceObjectiveTermResponse:
        return cls(
            member_ordinal=value.member_ordinal,
            dataset_id=value.dataset_id,
            dataset_revision_id=value.dataset_revision_id,
            point_count=value.point_count,
            mean_normalized_squared_residual=value.mean_normalized_squared_residual,
        )


class VoceAttemptResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    voce_calibration_attempt_id: UUID
    attempt_ordinal: int
    initial_sigma_0_pa: float
    initial_q_pa: float
    initial_b: float
    random_seed: int
    status: str
    candidate_id: UUID | None
    failure_code: str | None
    started_at: datetime
    ended_at: datetime | None

    @classmethod
    def from_domain(cls, value: VoceCalibrationAttempt) -> VoceAttemptResponse:
        return cls(
            voce_calibration_attempt_id=value.id,
            attempt_ordinal=value.attempt_ordinal,
            initial_sigma_0_pa=value.initial_sigma_0_pa,
            initial_q_pa=value.initial_q_pa,
            initial_b=value.initial_b,
            random_seed=value.random_seed,
            status=value.status.value,
            candidate_id=value.candidate_id,
            failure_code=value.failure_code,
            started_at=value.started_at,
            ended_at=value.ended_at,
        )


class VoceCandidateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    voce_calibration_candidate_id: UUID
    attempt_ordinal: int
    status: str
    candidate_sha256: str
    sigma_0_pa: float
    q_pa: float
    b: float
    objective_total: float
    residual_root_mean_square_pa: float
    residual_mean_pa: float
    bound_sticking_parameters: tuple[str, ...]
    convergence_status_code: int
    convergence_reason: str
    function_evaluations: int
    jacobian_evaluations: int | None
    optimality: float
    warnings: tuple[str, ...]
    identifiability_status: str
    uncertainty_status: str
    diagnostics_artifact_id: UUID
    diagnostics_sha256: str
    diagnostics_point_count: int
    objective_terms: tuple[VoceObjectiveTermResponse, ...]

    @classmethod
    def from_domain(cls, value: VoceCalibrationCandidate) -> VoceCandidateResponse:
        at_bound = tuple(
            name
            for name, active in (
                ("sigma_0_pa", value.sigma_0_at_bound),
                ("q_pa", value.q_at_bound),
                ("b", value.b_at_bound),
            )
            if active
        )
        warnings = tuple(
            name
            for name, active in (
                ("one_or_more_parameters_at_bound", value.warning_at_bound),
                ("optimizer_did_not_converge", value.warning_nonconvergence),
            )
            if active
        )
        return cls(
            voce_calibration_candidate_id=value.id,
            attempt_ordinal=value.attempt_ordinal,
            status=value.status.value,
            candidate_sha256=f"sha256:{value.candidate_sha256}",
            sigma_0_pa=value.sigma_0_pa,
            q_pa=value.q_pa,
            b=value.b,
            objective_total=value.objective_total,
            residual_root_mean_square_pa=value.residual_root_mean_square_pa,
            residual_mean_pa=value.residual_mean_pa,
            bound_sticking_parameters=at_bound,
            convergence_status_code=value.convergence_status_code,
            convergence_reason=value.convergence_reason,
            function_evaluations=value.function_evaluations,
            jacobian_evaluations=value.jacobian_evaluations,
            optimality=value.optimality,
            warnings=warnings,
            identifiability_status=value.identifiability_status,
            uncertainty_status=value.uncertainty_status,
            diagnostics_artifact_id=value.diagnostics_artifact_id,
            diagnostics_sha256=f"sha256:{value.diagnostics_sha256}",
            diagnostics_point_count=value.diagnostics_point_count,
            objective_terms=tuple(
                VoceObjectiveTermResponse.from_domain(item) for item in value.objective_terms
            ),
        )


class VoceRunResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    voce_calibration_run_id: UUID
    classification: DataClassification
    plan_id: UUID
    plan_revision_id: UUID
    calibration_input_scope_id: UUID
    calibration_input_scope_revision_id: UUID
    property_set_id: UUID
    property_set_revision_id: UUID
    source_curve_count: int
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
    attempts: tuple[VoceAttemptResponse, ...]
    candidates: tuple[VoceCandidateResponse, ...]

    @classmethod
    def from_detail(cls, value: VoceCalibrationRunDetail) -> VoceRunResponse:
        run = value.run
        return cls(
            voce_calibration_run_id=run.id,
            classification=run.classification,
            plan_id=run.plan_id,
            plan_revision_id=run.plan_revision_id,
            calibration_input_scope_id=run.calibration_input_scope_id,
            calibration_input_scope_revision_id=run.calibration_input_scope_revision_id,
            property_set_id=run.property_set_id,
            property_set_revision_id=run.property_set_revision_id,
            source_curve_count=run.source_curve_count,
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
            attempts=tuple(VoceAttemptResponse.from_domain(item) for item in value.attempts),
            candidates=tuple(VoceCandidateResponse.from_domain(item) for item in value.candidates),
        )


class VoceDiagnosticPointResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    member_ordinal: int
    dataset_revision_id: UUID
    point_ordinal: int
    true_plastic_strain: float
    observed_true_yield_stress_pa: float
    predicted_true_yield_stress_pa: float
    residual_true_yield_stress_pa: float
    normalized_residual: float
    effective_weight: float

    @classmethod
    def from_domain(cls, value: VoceDiagnosticPoint) -> VoceDiagnosticPointResponse:
        return cls(
            member_ordinal=value.member_ordinal,
            dataset_revision_id=value.dataset_revision_id,
            point_ordinal=value.point_ordinal,
            true_plastic_strain=value.true_plastic_strain,
            observed_true_yield_stress_pa=value.observed_true_yield_stress_pa,
            predicted_true_yield_stress_pa=value.predicted_true_yield_stress_pa,
            residual_true_yield_stress_pa=value.residual_true_yield_stress_pa,
            normalized_residual=value.normalized_residual,
            effective_weight=value.effective_weight,
        )


class VoceDiagnosticPreviewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    calibration_candidate_id: UUID
    point_count: int
    returned_point_count: int
    sampled: bool
    points: tuple[VoceDiagnosticPointResponse, ...]

    @classmethod
    def from_domain(cls, value: VoceCalibrationDiagnosticPreview) -> VoceDiagnosticPreviewResponse:
        return cls(
            calibration_candidate_id=value.calibration_candidate_id,
            point_count=value.point_count,
            returned_point_count=value.returned_point_count,
            sampled=value.sampled,
            points=tuple(VoceDiagnosticPointResponse.from_domain(item) for item in value.points),
        )


def install_voce_calibration_api(
    app: FastAPI,
    *,
    service: ReferenceVoceCalibrationService | None,
    security_dependency: Dependency,
    read_dependency: Dependency,
    execute_dependency: Dependency,
) -> None:
    def available() -> ReferenceVoceCalibrationService:
        if service is None:
            raise HTTPException(status_code=503, detail="Voce calibration service is unavailable")
        return service

    def scope(request: Request) -> tuple[SecurityContext, AuthorizationDecision]:
        return request.state.security_context, request.state.authorization_decision

    @app.exception_handler(InvalidVoceCalibration)
    async def invalid_voce(_: Request, error: InvalidVoceCalibration) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(error)})

    @app.exception_handler(VoceCalibrationConflict)
    async def voce_conflict(_: Request, error: VoceCalibrationConflict) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(error)})

    @app.exception_handler(VoceCalibrationNotFound)
    async def voce_not_found(_: Request, error: VoceCalibrationNotFound) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(error)})

    @app.post(
        "/api/v1/voce-calibration-plans",
        operation_id="createReferenceVoceCalibrationPlan",
        response_model=VocePlanResponse,
        status_code=status.HTTP_201_CREATED,
        dependencies=[Depends(security_dependency), Depends(execute_dependency)],
        tags=["modeling"],
    )
    def create_plan(
        request: Request,
        body: VocePlanCreateRequest,
        response: Response,
    ) -> VocePlanResponse:
        context, decision = scope(request)
        value = available().create_plan(
            context,
            decision,
            CreateReferenceVoceCalibrationPlan(
                classification=body.classification,
                content=body.content(),
                change_reason=body.change_reason,
            ),
        )
        response.headers["ETag"] = str(RevisionETag.from_ref(value.current.record.ref))
        return VocePlanResponse.from_snapshot(value)

    @app.get(
        "/api/v1/voce-calibration-plans",
        operation_id="listReferenceVoceCalibrationPlans",
        response_model=VocePlanListResponse,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["modeling"],
    )
    def list_plans(
        request: Request,
        limit: Annotated[int, Query(ge=1, le=200)] = 100,
    ) -> VocePlanListResponse:
        context, decision = scope(request)
        return VocePlanListResponse(
            items=tuple(
                VocePlanResponse.from_snapshot(item)
                for item in available().list_plans(context, decision, limit=limit)
            )
        )

    @app.get(
        "/api/v1/voce-calibration-plans/{plan_id}",
        operation_id="getReferenceVoceCalibrationPlan",
        response_model=VocePlanResponse,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["modeling"],
    )
    def get_plan(
        request: Request,
        plan_id: UUID,
        response: Response,
    ) -> VocePlanResponse:
        context, decision = scope(request)
        value = available().get_plan(context, decision, plan_id)
        response.headers["ETag"] = str(RevisionETag.from_ref(value.current.record.ref))
        return VocePlanResponse.from_snapshot(value)

    @app.post(
        "/api/v1/voce-calibration-plans/{plan_id}/revisions",
        operation_id="reviseReferenceVoceCalibrationPlan",
        response_model=VocePlanResponse,
        status_code=status.HTTP_201_CREATED,
        dependencies=[Depends(security_dependency), Depends(execute_dependency)],
        tags=["modeling"],
    )
    def revise_plan(
        request: Request,
        plan_id: UUID,
        body: VocePlanReviseRequest,
        response: Response,
    ) -> VocePlanResponse:
        context, decision = scope(request)
        try:
            value = available().revise_plan(
                context,
                decision,
                plan_id,
                ReviseReferenceVoceCalibrationPlan(
                    expected_current_revision_id=body.expected_current_revision_id,
                    content=body.content(),
                    change_reason=body.change_reason,
                ),
            )
        except RevisionKernelError as error:
            raise VoceCalibrationConflict(str(error)) from error
        response.headers["ETag"] = str(RevisionETag.from_ref(value.current.record.ref))
        return VocePlanResponse.from_snapshot(value)

    @app.post(
        "/api/v1/voce-calibration-plans/{plan_id}/runs",
        operation_id="executeReferenceVoceCalibration",
        response_model=VoceRunResponse,
        status_code=status.HTTP_201_CREATED,
        dependencies=[Depends(security_dependency), Depends(execute_dependency)],
        tags=["modeling"],
    )
    async def execute(
        request: Request,
        plan_id: UUID,
        body: VoceExecuteRequest,
    ) -> VoceRunResponse:
        context, decision = scope(request)
        return VoceRunResponse.from_detail(
            await available().execute(
                context,
                decision,
                ExecuteReferenceVoceCalibration(
                    plan_id=plan_id,
                    plan_revision_id=body.plan_revision_id,
                    change_reason=body.change_reason,
                ),
            )
        )

    @app.get(
        "/api/v1/voce-calibration-runs/{run_id}",
        operation_id="getReferenceVoceCalibrationRun",
        response_model=VoceRunResponse,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["modeling"],
    )
    def get_run(
        request: Request,
        run_id: UUID,
    ) -> VoceRunResponse:
        context, decision = scope(request)
        return VoceRunResponse.from_detail(available().get_run(context, decision, run_id))

    @app.get(
        "/api/v1/voce-calibration-candidates/{candidate_id}/diagnostics-preview",
        operation_id="previewReferenceVoceCalibrationCandidateDiagnostics",
        response_model=VoceDiagnosticPreviewResponse,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["modeling"],
    )
    async def preview_diagnostics(
        request: Request,
        candidate_id: UUID,
        maximum_points: Annotated[int, Query(ge=6, le=10_000)] = 1_000,
    ) -> VoceDiagnosticPreviewResponse:
        context, decision = scope(request)
        return VoceDiagnosticPreviewResponse.from_domain(
            await available().preview_candidate_diagnostics(
                context, decision, candidate_id, maximum_points=maximum_points
            )
        )

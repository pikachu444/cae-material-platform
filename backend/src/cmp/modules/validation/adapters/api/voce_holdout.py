"""Protected API for solver-independent reference Voce holdout validation."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends, FastAPI, Query, Request, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from sqlalchemy.exc import IntegrityError

from cmp.modules.artifacts.domain.content import ArtifactError, ArtifactNotFound
from cmp.modules.datasets.domain.reference_tensile import DatasetError, DatasetNotFound
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.modeling.domain.reference_isotropic_tabulated_plasticity import (
    TabulatedPlasticityError,
    TabulatedPlasticityNotFound,
)
from cmp.modules.statistics.domain.reference_tensile_pair import (
    StatisticsConflict,
    StatisticsNotFound,
)
from cmp.modules.validation.application.voce_holdout import (
    CreateReferenceVoceHoldoutPlan,
    ExecuteReferenceVoceHoldout,
    ReferenceVoceHoldoutService,
    VoceHoldoutPlanSnapshot,
)
from cmp.modules.validation.domain.reference_voce_holdout import (
    ReferenceVoceHoldoutPlanContent,
    ReferenceVoceHoldoutResult,
    VoceHoldoutConflict,
    VoceHoldoutError,
    VoceHoldoutNotFound,
)
from cmp.shared.contracts.revisions import RevisionETag, RevisionMetadataResponse
from cmp.shared.domain.revisions import AggregateNotFound, RevisionKernelError, RevisionRecord

type Dependency = Callable[..., object]

logger = logging.getLogger(__name__)


class VoceHoldoutPlanInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_label: Annotated[str, StringConstraints(min_length=1, max_length=160)]
    material_model_id: UUID
    material_model_revision_id: UUID
    holdout_dataset_id: UUID
    holdout_dataset_revision_id: UUID

    def content(self) -> ReferenceVoceHoldoutPlanContent:
        return ReferenceVoceHoldoutPlanContent(
            plan_label=self.plan_label,
            material_model_id=self.material_model_id,
            material_model_revision_id=self.material_model_revision_id,
            holdout_dataset_id=self.holdout_dataset_id,
            holdout_dataset_revision_id=self.holdout_dataset_revision_id,
        )


class VoceHoldoutPlanCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    classification: DataClassification
    content: VoceHoldoutPlanInput
    change_reason: Annotated[str, StringConstraints(min_length=1, max_length=2000)]


class VoceHoldoutExecuteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_revision_id: UUID
    change_reason: Annotated[str, StringConstraints(min_length=1, max_length=2000)]


class VoceHoldoutPlanContentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_label: str
    material_model_id: UUID
    material_model_revision_id: UUID
    holdout_dataset_id: UUID
    holdout_dataset_revision_id: UUID
    metric_profile_id: str
    threshold_profile_id: str
    relative_rmse_threshold: float
    overlap_policy: str
    evaluation_mode: str
    solver_execution: str = "not_used"
    non_production: bool


class VoceHoldoutPlanRevisionResponse(RevisionMetadataResponse):
    content: VoceHoldoutPlanContentResponse


class VoceHoldoutPlanResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    voce_holdout_plan_id: UUID
    current_revision: VoceHoldoutPlanRevisionResponse
    links: dict[str, str]

    @classmethod
    def from_snapshot(cls, value: VoceHoldoutPlanSnapshot) -> VoceHoldoutPlanResponse:
        content = value.current.content
        metadata = RevisionMetadataResponse.from_record(value.current.record, "draft")
        root = f"/api/v1/voce-holdout-validation-plans/{value.id}"
        return cls(
            voce_holdout_plan_id=value.id,
            current_revision=VoceHoldoutPlanRevisionResponse(
                **metadata.model_dump(),
                content=VoceHoldoutPlanContentResponse(
                    plan_label=content.plan_label,
                    material_model_id=content.material_model_id,
                    material_model_revision_id=content.material_model_revision_id,
                    holdout_dataset_id=content.holdout_dataset_id,
                    holdout_dataset_revision_id=content.holdout_dataset_revision_id,
                    metric_profile_id=content.metric_profile_id,
                    threshold_profile_id=content.threshold_profile_id,
                    relative_rmse_threshold=content.relative_rmse_threshold,
                    overlap_policy=content.overlap_policy,
                    evaluation_mode=content.evaluation_mode,
                    non_production=content.non_production,
                ),
            ),
            links={"self": root, "execute": f"{root}/runs"},
        )


class VoceHoldoutPlanListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: tuple[VoceHoldoutPlanResponse, ...]


class VoceHoldoutPointResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_point_ordinal: int
    true_plastic_strain: float
    observed_true_yield_stress_pa: float
    predicted_true_yield_stress_pa: float
    residual_true_yield_stress_pa: float


class VoceHoldoutResultResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    voce_holdout_result_id: UUID
    voce_holdout_run_id: UUID
    plan_id: UUID
    plan_revision_id: UUID
    material_model_id: UUID
    material_model_revision_id: UUID
    calibration_input_scope_id: UUID
    calibration_input_scope_revision_id: UUID
    voce_calibration_run_id: UUID
    voce_calibration_candidate_id: UUID
    voce_candidate_selection_id: UUID
    voce_candidate_selection_revision_id: UUID
    holdout_dataset_id: UUID
    holdout_dataset_revision_id: UUID
    holdout_test_run_id: UUID
    holdout_test_run_revision_id: UUID
    holdout_independence: str = "disjoint_dataset_and_test_run"
    source_data_artifact_id: UUID
    source_data_sha256: str
    comparison_artifact_id: UUID
    comparison_sha256: str
    comparison_point_count: int
    root_mean_squared_error_pa: float
    relative_root_mean_squared_error: float
    normalization_stress_scale_pa: float
    characterized_max_true_plastic_strain: float
    relative_rmse_threshold: float = 0.05
    verdict: str
    evaluation_mode: str = "closed_form_curve"
    solver_execution: str = "not_used"
    non_production: bool = True
    created_at: str
    created_by: UUID
    points: tuple[VoceHoldoutPointResponse, ...]
    links: dict[str, str]

    @classmethod
    def from_domain(cls, value: ReferenceVoceHoldoutResult) -> VoceHoldoutResultResponse:
        root = f"/api/v1/voce-holdout-results/{value.id}"
        return cls(
            voce_holdout_result_id=value.id,
            voce_holdout_run_id=value.run_id,
            plan_id=value.plan_id,
            plan_revision_id=value.plan_revision_id,
            material_model_id=value.material_model_id,
            material_model_revision_id=value.material_model_revision_id,
            calibration_input_scope_id=value.calibration_input_scope_id,
            calibration_input_scope_revision_id=value.calibration_input_scope_revision_id,
            voce_calibration_run_id=value.voce_calibration_run_id,
            voce_calibration_candidate_id=value.voce_calibration_candidate_id,
            voce_candidate_selection_id=value.voce_candidate_selection_id,
            voce_candidate_selection_revision_id=value.voce_candidate_selection_revision_id,
            holdout_dataset_id=value.holdout_dataset_id,
            holdout_dataset_revision_id=value.holdout_dataset_revision_id,
            holdout_test_run_id=value.holdout_test_run_id,
            holdout_test_run_revision_id=value.holdout_test_run_revision_id,
            source_data_artifact_id=value.source_data_artifact_id,
            source_data_sha256=f"sha256:{value.source_data_sha256}",
            comparison_artifact_id=value.comparison_artifact_id,
            comparison_sha256=f"sha256:{value.comparison_sha256}",
            comparison_point_count=len(value.metrics.points),
            root_mean_squared_error_pa=value.metrics.root_mean_squared_error_pa,
            relative_root_mean_squared_error=(value.metrics.relative_root_mean_squared_error),
            normalization_stress_scale_pa=value.metrics.normalization_stress_scale_pa,
            characterized_max_true_plastic_strain=(
                value.metrics.characterized_max_true_plastic_strain
            ),
            verdict=value.metrics.verdict.value,
            created_at=value.created_at.isoformat(),
            created_by=value.created_by,
            points=tuple(
                VoceHoldoutPointResponse(
                    source_point_ordinal=point.source_point_ordinal,
                    true_plastic_strain=point.true_plastic_strain,
                    observed_true_yield_stress_pa=(point.observed_true_yield_stress_pa),
                    predicted_true_yield_stress_pa=(point.predicted_true_yield_stress_pa),
                    residual_true_yield_stress_pa=(point.residual_true_yield_stress_pa),
                )
                for point in value.metrics.points
            ),
            links={
                "self": root,
                "comparison_artifact": (f"/api/v1/artifacts/{value.comparison_artifact_id}"),
            },
        )


class VoceHoldoutResultListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: tuple[VoceHoldoutResultResponse, ...]


class VoceHoldoutProblem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    title: str
    status: Annotated[int, Field(ge=400, le=599)]
    detail: Annotated[str, StringConstraints(min_length=1, max_length=2000)]
    code: Annotated[str, StringConstraints(pattern=r"^CMP-VALIDATION-[0-9]{4}$")]
    trace_id: str


class VoceHoldoutHttpError(Exception):
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
        self.problem = VoceHoldoutProblem(
            type="urn:cmp:problem:validation:voce-holdout",
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
        raise RuntimeError("Voce holdout dependencies did not initialize request scope")
    return context, decision


def _unavailable(context: SecurityContext) -> VoceHoldoutHttpError:
    return VoceHoldoutHttpError(
        context=context,
        status_code=503,
        title="Voce holdout service unavailable",
        detail="The authoritative Validation dependencies are not configured.",
        code="CMP-VALIDATION-0035",
    )


def _translate(context: SecurityContext, error: Exception) -> VoceHoldoutHttpError:
    if isinstance(
        error,
        (
            VoceHoldoutNotFound,
            TabulatedPlasticityNotFound,
            DatasetNotFound,
            StatisticsNotFound,
            ArtifactNotFound,
            AggregateNotFound,
        ),
    ):
        return VoceHoldoutHttpError(
            context=context,
            status_code=404,
            title="Voce holdout resource not found",
            detail="No requested Plan, calibrated IR, Scope, Dataset, or Artifact is visible.",
            code="CMP-VALIDATION-0031",
        )
    if isinstance(error, ValueError) and not isinstance(error, VoceHoldoutConflict):
        return VoceHoldoutHttpError(
            context=context,
            status_code=422,
            title="Invalid Voce holdout request",
            detail="Use one calibrated reference Voce IR and one independent normalized Dataset.",
            code="CMP-VALIDATION-0032",
        )
    if isinstance(
        error,
        (
            VoceHoldoutConflict,
            VoceHoldoutError,
            TabulatedPlasticityError,
            DatasetError,
            StatisticsConflict,
            ArtifactError,
            RevisionKernelError,
            IntegrityError,
        ),
    ):
        return VoceHoldoutHttpError(
            context=context,
            status_code=409,
            title="Voce holdout lineage conflict",
            detail=(
                "The holdout must share tenant and Material State while remaining disjoint from "
                "every Dataset and Test Run in the calibration review scope."
            ),
            code="CMP-VALIDATION-0033",
        )
    return VoceHoldoutHttpError(
        context=context,
        status_code=409,
        title="Voce holdout command rejected",
        detail="The solver-independent holdout command could not be completed.",
        code="CMP-VALIDATION-0033",
    )


def _etag(response: Response, record: RevisionRecord) -> None:
    response.headers["ETag"] = str(RevisionETag.from_ref(record.ref))
    response.headers["Cache-Control"] = "no-store"


def install_voce_holdout_api(
    application: FastAPI,
    *,
    service: ReferenceVoceHoldoutService | None,
    security_dependency: Dependency,
    read_dependency: Dependency,
    execute_dependency: Dependency,
) -> None:
    @application.exception_handler(VoceHoldoutHttpError)
    async def holdout_error_handler(request: Request, error: VoceHoldoutHttpError) -> JSONResponse:
        del request
        return JSONResponse(
            status_code=error.problem.status,
            content=error.problem.model_dump(mode="json"),
            media_type="application/problem+json",
            headers={"Cache-Control": "no-store", "X-Request-ID": str(error.context.request_id)},
        )

    errors: dict[int | str, dict[str, Any]] = {
        401: {"description": "Authentication required."},
        403: {"description": "Validation permission is not authorized."},
        404: {"model": VoceHoldoutProblem},
        409: {"model": VoceHoldoutProblem},
        422: {"model": VoceHoldoutProblem},
        503: {"model": VoceHoldoutProblem},
    }

    @application.post(
        "/api/v1/voce-holdout-validation-plans",
        operation_id="createReferenceVoceHoldoutValidationPlan",
        response_model=VoceHoldoutPlanResponse,
        status_code=status.HTTP_201_CREATED,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(execute_dependency)],
        tags=["validation", "calibration"],
    )
    def create_plan(
        request: Request, response: Response, body: VoceHoldoutPlanCreateRequest
    ) -> VoceHoldoutPlanResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            value = service.create_plan(
                context,
                decision,
                CreateReferenceVoceHoldoutPlan(
                    classification=body.classification,
                    content=body.content.content(),
                    change_reason=body.change_reason,
                ),
            )
        except Exception as error:
            logger.exception("Reference Voce holdout Plan creation failed")
            raise _translate(context, error) from error
        _etag(response, value.current.record)
        return VoceHoldoutPlanResponse.from_snapshot(value)

    @application.get(
        "/api/v1/voce-holdout-validation-plans",
        operation_id="listReferenceVoceHoldoutValidationPlans",
        response_model=VoceHoldoutPlanListResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["validation", "calibration"],
    )
    def list_plans(
        request: Request, limit: Annotated[int, Query(ge=1, le=200)] = 100
    ) -> VoceHoldoutPlanListResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            values = service.list_plans(context, decision, limit=limit)
        except Exception as error:
            raise _translate(context, error) from error
        return VoceHoldoutPlanListResponse(
            items=tuple(VoceHoldoutPlanResponse.from_snapshot(value) for value in values)
        )

    @application.post(
        "/api/v1/voce-holdout-validation-plans/{plan_id}/runs",
        operation_id="executeReferenceVoceHoldoutValidation",
        response_model=VoceHoldoutResultResponse,
        status_code=status.HTTP_201_CREATED,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(execute_dependency)],
        tags=["validation", "calibration"],
    )
    async def execute(
        request: Request,
        plan_id: UUID,
        body: VoceHoldoutExecuteRequest,
    ) -> VoceHoldoutResultResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            value = await service.execute(
                context,
                decision,
                ExecuteReferenceVoceHoldout(
                    plan_id=plan_id,
                    plan_revision_id=body.plan_revision_id,
                    change_reason=body.change_reason,
                ),
            )
        except Exception as error:
            logger.exception("Reference Voce holdout execution failed")
            raise _translate(context, error) from error
        return VoceHoldoutResultResponse.from_domain(value)

    @application.get(
        "/api/v1/voce-holdout-results/{result_id}",
        operation_id="getReferenceVoceHoldoutValidationResult",
        response_model=VoceHoldoutResultResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["validation", "calibration"],
    )
    def get_result(request: Request, result_id: UUID) -> VoceHoldoutResultResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            value = service.get_result(context, decision, result_id)
        except Exception as error:
            raise _translate(context, error) from error
        return VoceHoldoutResultResponse.from_domain(value)

    @application.get(
        "/api/v1/tabulated-plasticity-models/{material_model_id}/voce-holdout-results",
        operation_id="listReferenceVoceHoldoutValidationResults",
        response_model=VoceHoldoutResultListResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["validation", "calibration"],
    )
    def list_results(
        request: Request,
        material_model_id: UUID,
        limit: Annotated[int, Query(ge=1, le=200)] = 100,
    ) -> VoceHoldoutResultListResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            values = service.list_results_for_model(
                context, decision, material_model_id, limit=limit
            )
        except Exception as error:
            raise _translate(context, error) from error
        return VoceHoldoutResultListResponse(
            items=tuple(VoceHoldoutResultResponse.from_domain(value) for value in values)
        )

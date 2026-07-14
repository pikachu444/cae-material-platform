"""Protected T-27 Validation Template, Plan, and reference-run resources."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends, FastAPI, Query, Request, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.validation.application.service import (
    AttachManualValidationResult,
    CreateReferenceValidationPlan,
    CreateReferenceValidationTemplate,
    EvaluateReferenceValidationRun,
    ReferenceValidationResult,
    ReferenceValidationService,
    ReviseReferenceValidationPlan,
    ReviseReferenceValidationTemplate,
    RevisionSnapshot,
    SubmitValidationRun,
    ValidationPlanSnapshot,
    ValidationResultCurvePreview,
    ValidationRunDetail,
    ValidationRunResultManifest,
    ValidationTemplateSnapshot,
)
from cmp.modules.validation.domain.reference_virtual_specimen import (
    InvalidNativeResult,
    InvalidValidationPlan,
    InvalidValidationTemplate,
    ReferenceRunnerOutcome,
    ReferenceValidationPlanContent,
    ReferenceVirtualSpecimenTemplateContent,
    ValidationConflict,
    ValidationError,
    ValidationExecutionMode,
    ValidationNotFound,
)
from cmp.shared.contracts.revisions import RevisionETag, RevisionMetadataResponse
from cmp.shared.domain.revisions import AggregateNotFound, RevisionKernelError, RevisionRecord

type Label = Annotated[str, StringConstraints(min_length=1, max_length=255)]
type Dependency = Callable[..., object]


class ReferenceValidationTemplateInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    template_label: Annotated[str, StringConstraints(min_length=1, max_length=160)]
    gauge_length_m: Annotated[float, Field(gt=0)]
    cross_section_area_m2: Annotated[float, Field(gt=0)]
    axial_element_count: Annotated[int, Field(ge=1, le=10_000)]
    axial_displacement_end_m: Annotated[float, Field(gt=0)]
    output_sample_count: Annotated[int, Field(ge=2, le=10_000)]

    def content(self) -> ReferenceVirtualSpecimenTemplateContent:
        return ReferenceVirtualSpecimenTemplateContent(
            template_label=self.template_label,
            gauge_length_m=self.gauge_length_m,
            cross_section_area_m2=self.cross_section_area_m2,
            axial_element_count=self.axial_element_count,
            axial_displacement_end_m=self.axial_displacement_end_m,
            output_sample_count=self.output_sample_count,
        )


class ReferenceValidationTemplateCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    classification: DataClassification
    content: ReferenceValidationTemplateInput
    change_reason: Annotated[str, StringConstraints(min_length=1, max_length=2000)]


class ReferenceValidationTemplateReviseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_current_revision_id: UUID
    content: ReferenceValidationTemplateInput
    change_reason: Annotated[str, StringConstraints(min_length=1, max_length=2000)]


class ValidationTemplateContentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    template_label: str
    template_kind: str
    gauge_length_m: float
    cross_section_area_m2: float
    axial_element_count: int
    axial_displacement_end_m: float
    output_sample_count: int
    result_extraction_profile_id: str
    metric_profile_id: str
    target_solver: str
    target_version: str
    target_unit_system: str
    runner_command_id: str
    non_production: bool

    @classmethod
    def from_domain(
        cls, value: ReferenceVirtualSpecimenTemplateContent
    ) -> ValidationTemplateContentResponse:
        return cls(
            template_label=value.template_label,
            template_kind=value.template_kind,
            gauge_length_m=value.gauge_length_m,
            cross_section_area_m2=value.cross_section_area_m2,
            axial_element_count=value.axial_element_count,
            axial_displacement_end_m=value.axial_displacement_end_m,
            output_sample_count=value.output_sample_count,
            result_extraction_profile_id=value.result_extraction_profile_id,
            metric_profile_id=value.metric_profile_id,
            target_solver=value.target_solver,
            target_version=value.target_version,
            target_unit_system=value.target_unit_system,
            runner_command_id=value.runner_command_id,
            non_production=value.non_production,
        )


class ValidationTemplateRevisionResponse(RevisionMetadataResponse):
    content: ValidationTemplateContentResponse

    @classmethod
    def from_snapshot(
        cls, value: RevisionSnapshot[ReferenceVirtualSpecimenTemplateContent]
    ) -> ValidationTemplateRevisionResponse:
        return cls(
            **RevisionMetadataResponse.from_record(value.record, "draft").model_dump(),
            content=ValidationTemplateContentResponse.from_domain(value.content),
        )


class ValidationTemplateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    validation_template_id: UUID
    current_revision: ValidationTemplateRevisionResponse
    links: dict[str, str]

    @classmethod
    def from_snapshot(cls, value: ValidationTemplateSnapshot) -> ValidationTemplateResponse:
        return cls(
            validation_template_id=value.id,
            current_revision=ValidationTemplateRevisionResponse.from_snapshot(value.current),
            links={
                "self": f"/api/v1/validation-templates/{value.id}",
                "plans": "/api/v1/validation-plans",
            },
        )


class ValidationTemplateListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: tuple[ValidationTemplateResponse, ...]


class ReferenceValidationPlanInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_label: Annotated[str, StringConstraints(min_length=1, max_length=160)]
    validation_template_id: UUID
    validation_template_revision_id: UUID
    material_model_id: UUID
    material_model_revision_id: UUID
    solver_card_id: UUID
    solver_card_revision_id: UUID
    experimental_selection_id: UUID
    experimental_selection_revision_id: UUID

    def content(self) -> ReferenceValidationPlanContent:
        return ReferenceValidationPlanContent(
            plan_label=self.plan_label,
            template_id=self.validation_template_id,
            template_revision_id=self.validation_template_revision_id,
            material_model_id=self.material_model_id,
            material_model_revision_id=self.material_model_revision_id,
            solver_card_id=self.solver_card_id,
            solver_card_revision_id=self.solver_card_revision_id,
            experimental_selection_id=self.experimental_selection_id,
            experimental_selection_revision_id=self.experimental_selection_revision_id,
        )


class ReferenceValidationPlanCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    classification: DataClassification
    content: ReferenceValidationPlanInput
    change_reason: Annotated[str, StringConstraints(min_length=1, max_length=2000)]


class ReferenceValidationPlanReviseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_current_revision_id: UUID
    content: ReferenceValidationPlanInput
    change_reason: Annotated[str, StringConstraints(min_length=1, max_length=2000)]


class ValidationPlanContentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_label: str
    plan_kind: str
    validation_template_id: UUID
    validation_template_revision_id: UUID
    material_model_id: UUID
    material_model_revision_id: UUID
    solver_card_id: UUID
    solver_card_revision_id: UUID
    experimental_selection_id: UUID
    experimental_selection_revision_id: UUID
    runner_id: str
    runner_version: str
    runner_digest: str
    non_production: bool

    @classmethod
    def from_domain(cls, value: ReferenceValidationPlanContent) -> ValidationPlanContentResponse:
        return cls(
            plan_label=value.plan_label,
            plan_kind=value.plan_kind,
            validation_template_id=value.template_id,
            validation_template_revision_id=value.template_revision_id,
            material_model_id=value.material_model_id,
            material_model_revision_id=value.material_model_revision_id,
            solver_card_id=value.solver_card_id,
            solver_card_revision_id=value.solver_card_revision_id,
            experimental_selection_id=value.experimental_selection_id,
            experimental_selection_revision_id=value.experimental_selection_revision_id,
            runner_id=value.runner_id,
            runner_version=value.runner_version,
            runner_digest=value.runner_digest,
            non_production=value.non_production,
        )


class ValidationPlanRevisionResponse(RevisionMetadataResponse):
    content: ValidationPlanContentResponse

    @classmethod
    def from_snapshot(
        cls, value: RevisionSnapshot[ReferenceValidationPlanContent]
    ) -> ValidationPlanRevisionResponse:
        return cls(
            **RevisionMetadataResponse.from_record(value.record, "draft").model_dump(),
            content=ValidationPlanContentResponse.from_domain(value.content),
        )


class ValidationPlanResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    validation_plan_id: UUID
    current_revision: ValidationPlanRevisionResponse
    links: dict[str, str]

    @classmethod
    def from_snapshot(cls, value: ValidationPlanSnapshot) -> ValidationPlanResponse:
        return cls(
            validation_plan_id=value.id,
            current_revision=ValidationPlanRevisionResponse.from_snapshot(value.current),
            links={
                "self": f"/api/v1/validation-plans/{value.id}",
                "submit": "/api/v1/validation-runs",
            },
        )


class ValidationPlanListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: tuple[ValidationPlanResponse, ...]


class ValidationRunCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    validation_plan_id: UUID
    validation_plan_revision_id: UUID
    execution_mode: ValidationExecutionMode
    external_job_reference: Annotated[str | None, StringConstraints(max_length=256)] = None
    change_reason: Annotated[str, StringConstraints(min_length=1, max_length=2000)]


class ValidationPollRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    change_reason: Annotated[str, StringConstraints(min_length=1, max_length=2000)] = (
        "Poll non-production reference mock runner"
    )
    outcome: ReferenceRunnerOutcome = ReferenceRunnerOutcome.SUCCEEDED


class ValidationCancelRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    change_reason: Annotated[str, StringConstraints(min_length=1, max_length=2000)]


class ValidationEvaluateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    change_reason: Annotated[str, StringConstraints(min_length=1, max_length=2000)]


class ManualValidationAttachRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stdout_text: Annotated[str, StringConstraints(min_length=1, max_length=200_000)]
    stderr_text: Annotated[str, StringConstraints(min_length=1, max_length=200_000)]
    native_result_text: Annotated[str, StringConstraints(min_length=1, max_length=1_000_000)]
    change_reason: Annotated[str, StringConstraints(min_length=1, max_length=2000)]


class ArtifactPointerResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact_id: UUID
    sha256: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]

    @classmethod
    def from_domain(cls, artifact_id: UUID, sha256: str) -> ArtifactPointerResponse:
        return cls(artifact_id=artifact_id, sha256=sha256)


class ValidationResultManifestResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    validation_result_manifest_id: UUID
    validation_run_id: UUID
    execution_mode: ValidationExecutionMode
    solver_termination: str
    external_job_reference: str | None
    deck: ArtifactPointerResponse
    stdout: ArtifactPointerResponse
    stderr: ArtifactPointerResponse
    native_result: ArtifactPointerResponse | None
    native_result_state: str
    manifest_artifact: ArtifactPointerResponse
    manifest_sha256: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
    created_at: datetime
    created_by: UUID

    @classmethod
    def from_domain(cls, value: ValidationRunResultManifest) -> ValidationResultManifestResponse:
        content = value.content
        return cls(
            validation_result_manifest_id=value.id,
            validation_run_id=content.validation_run_id,
            execution_mode=content.execution_mode,
            solver_termination=content.solver_termination.value,
            external_job_reference=content.external_job_reference,
            deck=ArtifactPointerResponse.from_domain(content.deck.artifact_id, content.deck.sha256),
            stdout=ArtifactPointerResponse.from_domain(
                content.stdout.artifact_id, content.stdout.sha256
            ),
            stderr=ArtifactPointerResponse.from_domain(
                content.stderr.artifact_id, content.stderr.sha256
            ),
            native_result=(
                ArtifactPointerResponse.from_domain(
                    content.native_result.artifact_id, content.native_result.sha256
                )
                if content.native_result is not None
                else None
            ),
            native_result_state=content.native_result_state,
            manifest_artifact=ArtifactPointerResponse.from_domain(
                value.manifest_artifact.artifact_id, value.manifest_artifact.sha256
            ),
            manifest_sha256=value.manifest_sha256,
            created_at=value.created_at,
            created_by=value.created_by,
        )


class ValidationResponseExtractionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    response_extraction_id: UUID
    validation_run_id: UUID
    validation_result_manifest_id: UUID
    source_native_result: ArtifactPointerResponse | None
    status: str
    normalized_response: ArtifactPointerResponse | None
    point_count: int | None
    reason_code: str | None
    created_at: datetime
    created_by: UUID

    @classmethod
    def from_domain(cls, value: Any) -> ValidationResponseExtractionResponse:
        return cls(
            response_extraction_id=value.id,
            validation_run_id=value.validation_run_id,
            validation_result_manifest_id=value.validation_result_manifest_id,
            source_native_result=(
                ArtifactPointerResponse.from_domain(
                    value.source_native_result.artifact_id,
                    value.source_native_result.sha256,
                )
                if value.source_native_result is not None
                else None
            ),
            status=value.status.value,
            normalized_response=(
                ArtifactPointerResponse.from_domain(
                    value.normalized_response.artifact_id,
                    value.normalized_response.sha256,
                )
                if value.normalized_response is not None
                else None
            ),
            point_count=value.point_count,
            reason_code=value.reason_code,
            created_at=value.created_at,
            created_by=value.created_by,
        )


class NumericalHealthReportResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    numerical_health_report_id: UUID
    validation_run_id: UUID
    validation_result_manifest_id: UUID
    response_extraction_id: UUID
    status: str
    solver_termination: str
    native_result_state: str
    expected_point_count: int
    observed_point_count: int | None
    output_complete: bool
    finite_values: bool
    strictly_increasing_strain: bool
    reason_code: str | None
    report_artifact: ArtifactPointerResponse
    report_sha256: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
    created_at: datetime
    created_by: UUID

    @classmethod
    def from_domain(cls, value: Any) -> NumericalHealthReportResponse:
        assessment = value.content.assessment
        return cls(
            numerical_health_report_id=value.id,
            validation_run_id=value.validation_run_id,
            validation_result_manifest_id=value.validation_result_manifest_id,
            response_extraction_id=value.response_extraction_id,
            status=assessment.status.value,
            solver_termination=value.content.solver_termination.value,
            native_result_state=value.content.native_result_state,
            expected_point_count=assessment.expected_point_count,
            observed_point_count=assessment.observed_point_count,
            output_complete=assessment.output_complete,
            finite_values=assessment.finite_values,
            strictly_increasing_strain=assessment.strictly_increasing_strain,
            reason_code=assessment.reason_code,
            report_artifact=ArtifactPointerResponse.from_domain(
                value.report_artifact.artifact_id,
                value.report_artifact.sha256,
            ),
            report_sha256=value.report_sha256,
            created_at=value.created_at,
            created_by=value.created_by,
        )


class ReferenceValidationResultResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    validation_result_id: UUID
    validation_run_id: UUID
    validation_result_manifest_id: UUID
    response_extraction: ValidationResponseExtractionResponse
    numerical_health_report: NumericalHealthReportResponse
    experimental_selection_id: UUID
    experimental_selection_revision_id: UUID
    metric_profile_id: str
    threshold_profile_id: str
    alignment_profile_id: str
    relative_rmse_threshold: float
    experimental_point_count: int
    simulated_point_count: int | None
    compared_point_count: int
    root_mean_squared_error_pa: float | None
    relative_root_mean_squared_error: float | None
    normalization_stress_scale_pa: float | None
    holdout_independence: str
    verdict: str
    reason_code: str | None
    result_artifact: ArtifactPointerResponse
    result_sha256: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
    created_at: datetime
    created_by: UUID
    links: dict[str, str]

    @classmethod
    def from_domain(cls, value: ReferenceValidationResult) -> ReferenceValidationResultResponse:
        content = value.content
        metrics = content.metrics
        return cls(
            validation_result_id=value.id,
            validation_run_id=value.validation_run_id,
            validation_result_manifest_id=value.validation_result_manifest_id,
            response_extraction=ValidationResponseExtractionResponse.from_domain(
                value.response_extraction
            ),
            numerical_health_report=NumericalHealthReportResponse.from_domain(
                value.numerical_health_report
            ),
            experimental_selection_id=content.experimental_selection_id,
            experimental_selection_revision_id=content.experimental_selection_revision_id,
            metric_profile_id=content.metric_profile_id,
            threshold_profile_id=content.threshold_profile_id,
            alignment_profile_id=content.alignment_profile_id,
            relative_rmse_threshold=content.relative_rmse_threshold,
            experimental_point_count=content.experimental_point_count,
            simulated_point_count=content.simulated_point_count,
            compared_point_count=len(metrics.comparison_points) if metrics is not None else 0,
            root_mean_squared_error_pa=(
                metrics.root_mean_squared_error_pa if metrics is not None else None
            ),
            relative_root_mean_squared_error=(
                metrics.relative_root_mean_squared_error if metrics is not None else None
            ),
            normalization_stress_scale_pa=(
                metrics.normalization_stress_scale_pa if metrics is not None else None
            ),
            holdout_independence=content.holdout_independence.value,
            verdict=content.verdict.value,
            reason_code=content.reason_code,
            result_artifact=ArtifactPointerResponse.from_domain(
                value.result_artifact.artifact_id,
                value.result_artifact.sha256,
            ),
            result_sha256=value.result_sha256,
            created_at=value.created_at,
            created_by=value.created_by,
            links={
                "self": f"/api/v1/validation-results/{value.id}",
                "curve": f"/api/v1/validation-results/{value.id}/curve",
                "run": f"/api/v1/validation-runs/{value.validation_run_id}",
            },
        )


class ValidationResponseCurvePoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    engineering_strain: float
    engineering_stress_pa: float


class ValidationComparisonCurvePoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    engineering_strain: float
    observed_engineering_stress_pa: float
    simulated_engineering_stress_pa: float
    residual_engineering_stress_pa: float


class ValidationResultCurveResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    validation_result_id: UUID
    verdict: str
    response_point_count: int
    returned_response_point_count: int
    response_sampled: bool
    response_points: tuple[ValidationResponseCurvePoint, ...]
    comparison_point_count: int
    returned_comparison_point_count: int
    comparison_sampled: bool
    comparison_points: tuple[ValidationComparisonCurvePoint, ...]

    @classmethod
    def from_domain(cls, value: ValidationResultCurvePreview) -> ValidationResultCurveResponse:
        return cls(
            validation_result_id=value.validation_result_id,
            verdict=value.verdict.value,
            response_point_count=value.response_point_count,
            returned_response_point_count=value.returned_response_point_count,
            response_sampled=value.response_sampled,
            response_points=tuple(
                ValidationResponseCurvePoint(
                    engineering_strain=point.engineering_strain,
                    engineering_stress_pa=point.engineering_stress_pa,
                )
                for point in value.response_points
            ),
            comparison_point_count=value.comparison_point_count,
            returned_comparison_point_count=value.returned_comparison_point_count,
            comparison_sampled=value.comparison_sampled,
            comparison_points=tuple(
                ValidationComparisonCurvePoint(
                    engineering_strain=point.engineering_strain,
                    observed_engineering_stress_pa=point.observed_engineering_stress_pa,
                    simulated_engineering_stress_pa=point.simulated_engineering_stress_pa,
                    residual_engineering_stress_pa=point.residual_engineering_stress_pa,
                )
                for point in value.comparison_points
            ),
        )


class ValidationRunResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    validation_run_id: UUID
    classification: DataClassification
    validation_plan_id: UUID
    validation_plan_revision_id: UUID
    validation_template_id: UUID
    validation_template_revision_id: UUID
    material_model_id: UUID
    material_model_revision_id: UUID
    solver_card_id: UUID
    solver_card_revision_id: UUID
    experimental_selection_id: UUID
    experimental_selection_revision_id: UUID
    execution_mode: ValidationExecutionMode
    runner_id: str
    runner_version: str
    runner_digest: str
    status: str
    deck: ArtifactPointerResponse
    external_job_reference: str | None
    failure_code: str | None
    submitted_at: datetime
    started_at: datetime | None
    ended_at: datetime | None
    created_by: UUID
    request_id: UUID
    trace_id: str
    change_reason: str
    result_manifest: ValidationResultManifestResponse | None
    validation_result: ReferenceValidationResultResponse | None
    links: dict[str, str]

    @classmethod
    def from_detail(cls, value: ValidationRunDetail) -> ValidationRunResponse:
        run = value.run
        return cls(
            validation_run_id=run.id,
            classification=run.classification,
            validation_plan_id=run.plan_id,
            validation_plan_revision_id=run.plan_revision_id,
            validation_template_id=run.template_id,
            validation_template_revision_id=run.template_revision_id,
            material_model_id=run.material_model_id,
            material_model_revision_id=run.material_model_revision_id,
            solver_card_id=run.solver_card_id,
            solver_card_revision_id=run.solver_card_revision_id,
            experimental_selection_id=run.experimental_selection_id,
            experimental_selection_revision_id=run.experimental_selection_revision_id,
            execution_mode=run.execution_mode,
            runner_id=run.runner_id,
            runner_version=run.runner_version,
            runner_digest=run.runner_digest,
            status=run.status.value,
            deck=ArtifactPointerResponse.from_domain(run.deck.artifact_id, run.deck.sha256),
            external_job_reference=run.external_job_reference,
            failure_code=run.failure_code,
            submitted_at=run.submitted_at,
            started_at=run.started_at,
            ended_at=run.ended_at,
            created_by=run.created_by,
            request_id=run.request_id,
            trace_id=run.trace_id,
            change_reason=run.change_reason,
            result_manifest=(
                ValidationResultManifestResponse.from_domain(value.result_manifest)
                if value.result_manifest is not None
                else None
            ),
            validation_result=(
                ReferenceValidationResultResponse.from_domain(value.validation_result)
                if value.validation_result is not None
                else None
            ),
            links={
                "self": f"/api/v1/validation-runs/{run.id}",
                "poll": f"/api/v1/validation-runs/{run.id}:poll",
                "cancel": f"/api/v1/validation-runs/{run.id}:cancel",
                "attach_result": f"/api/v1/validation-runs/{run.id}:attach-result",
                "evaluate": f"/api/v1/validation-runs/{run.id}:evaluate",
            },
        )


class ValidationProblem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Label
    title: Label
    status: Annotated[int, Field(ge=400, le=599)]
    detail: Annotated[str, StringConstraints(min_length=1, max_length=2000)]
    code: Annotated[str, StringConstraints(pattern=r"^CMP-VALIDATION-[0-9]{4}$")]
    trace_id: Label


class ValidationHttpError(Exception):
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
        self.problem = ValidationProblem(
            type="urn:cmp:problem:validation",
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
        raise RuntimeError("Validation route dependencies did not initialize request scope")
    return context, decision


def _unavailable(context: SecurityContext) -> ValidationHttpError:
    return ValidationHttpError(
        context=context,
        status_code=503,
        title="Validation service unavailable",
        detail=(
            "The authoritative reference Validation store is not configured for this deployment."
        ),
        code="CMP-VALIDATION-0005",
    )


def _translate(context: SecurityContext, error: Exception) -> ValidationHttpError:
    if isinstance(error, (ValidationNotFound, AggregateNotFound)):
        return ValidationHttpError(
            context=context,
            status_code=404,
            title="Validation resource not found",
            detail=(
                "No requested Validation Template, Plan, Run, or immutable input is visible "
                "in this tenant."
            ),
            code="CMP-VALIDATION-0001",
        )
    if isinstance(
        error,
        (InvalidValidationTemplate, InvalidValidationPlan, InvalidNativeResult, ValueError),
    ):
        return ValidationHttpError(
            context=context,
            status_code=422,
            title="Invalid Validation request",
            detail=(
                "The reference validation workflow requires compatible explicit immutable inputs."
            ),
            code="CMP-VALIDATION-0002",
        )
    if isinstance(error, (ValidationConflict, RevisionKernelError, ValidationError)):
        return ValidationHttpError(
            context=context,
            status_code=409,
            title="Validation state conflict",
            detail=(
                "The Validation command conflicts with immutable inputs, result evidence, or "
                "run state."
            ),
            code="CMP-VALIDATION-0003",
        )
    return ValidationHttpError(
        context=context,
        status_code=409,
        title="Validation command rejected",
        detail="The reference Validation command could not be completed.",
        code="CMP-VALIDATION-0003",
    )


def _etag(response: Response, record: RevisionRecord) -> None:
    response.headers["ETag"] = str(RevisionETag.from_ref(record.ref))
    response.headers["Cache-Control"] = "no-store"


def install_validation_api(
    application: FastAPI,
    *,
    service: ReferenceValidationService | None,
    security_dependency: Dependency,
    read_dependency: Dependency,
    execute_dependency: Dependency,
) -> None:
    @application.exception_handler(ValidationHttpError)
    async def validation_error_handler(
        request: Request, error: ValidationHttpError
    ) -> JSONResponse:
        del request
        return JSONResponse(
            status_code=error.problem.status,
            content=error.problem.model_dump(mode="json"),
            media_type="application/problem+json",
            headers={
                "Cache-Control": "no-store",
                "X-Request-ID": str(error.context.request_id),
            },
        )

    errors: dict[int | str, dict[str, Any]] = {
        401: {"description": "Authentication required."},
        403: {"description": "Validation permission is not authorized."},
        404: {"model": ValidationProblem},
        409: {"model": ValidationProblem},
        422: {"model": ValidationProblem},
        503: {"model": ValidationProblem},
    }

    @application.post(
        "/api/v1/validation-templates",
        operation_id="createReferenceValidationTemplate",
        response_model=ValidationTemplateResponse,
        status_code=status.HTTP_201_CREATED,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(execute_dependency)],
        tags=["validation"],
    )
    def create_template(
        request: Request,
        response: Response,
        body: ReferenceValidationTemplateCreateRequest,
    ) -> ValidationTemplateResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            value = service.create_template(
                context,
                decision,
                CreateReferenceValidationTemplate(
                    body.classification,
                    body.content.content(),
                    body.change_reason,
                ),
            )
        except Exception as error:
            raise _translate(context, error) from error
        _etag(response, value.current.record)
        return ValidationTemplateResponse.from_snapshot(value)

    @application.patch(
        "/api/v1/validation-templates/{template_id}",
        operation_id="reviseReferenceValidationTemplate",
        response_model=ValidationTemplateResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(execute_dependency)],
        tags=["validation"],
    )
    def revise_template(
        request: Request,
        response: Response,
        template_id: UUID,
        body: ReferenceValidationTemplateReviseRequest,
    ) -> ValidationTemplateResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            value = service.revise_template(
                context,
                decision,
                template_id,
                ReviseReferenceValidationTemplate(
                    body.expected_current_revision_id, body.content.content(), body.change_reason
                ),
            )
        except Exception as error:
            raise _translate(context, error) from error
        _etag(response, value.current.record)
        return ValidationTemplateResponse.from_snapshot(value)

    @application.get(
        "/api/v1/validation-templates",
        operation_id="listValidationTemplates",
        response_model=ValidationTemplateListResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["validation"],
    )
    def list_templates(
        request: Request, limit: Annotated[int, Query(ge=1, le=200)] = 100
    ) -> ValidationTemplateListResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            items = service.list_templates(context, decision, limit=limit)
        except Exception as error:
            raise _translate(context, error) from error
        return ValidationTemplateListResponse(
            items=tuple(ValidationTemplateResponse.from_snapshot(item) for item in items)
        )

    @application.get(
        "/api/v1/validation-templates/{template_id}",
        operation_id="getValidationTemplate",
        response_model=ValidationTemplateResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["validation"],
    )
    def get_template(
        request: Request, response: Response, template_id: UUID
    ) -> ValidationTemplateResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            value = service.get_template(context, decision, template_id)
        except Exception as error:
            raise _translate(context, error) from error
        _etag(response, value.current.record)
        return ValidationTemplateResponse.from_snapshot(value)

    @application.post(
        "/api/v1/validation-plans",
        operation_id="createReferenceValidationPlan",
        response_model=ValidationPlanResponse,
        status_code=status.HTTP_201_CREATED,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(execute_dependency)],
        tags=["validation"],
    )
    def create_plan(
        request: Request,
        response: Response,
        body: ReferenceValidationPlanCreateRequest,
    ) -> ValidationPlanResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            value = service.create_plan(
                context,
                decision,
                CreateReferenceValidationPlan(
                    body.classification,
                    body.content.content(),
                    body.change_reason,
                ),
            )
        except Exception as error:
            raise _translate(context, error) from error
        _etag(response, value.current.record)
        return ValidationPlanResponse.from_snapshot(value)

    @application.patch(
        "/api/v1/validation-plans/{plan_id}",
        operation_id="reviseReferenceValidationPlan",
        response_model=ValidationPlanResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(execute_dependency)],
        tags=["validation"],
    )
    def revise_plan(
        request: Request,
        response: Response,
        plan_id: UUID,
        body: ReferenceValidationPlanReviseRequest,
    ) -> ValidationPlanResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            value = service.revise_plan(
                context,
                decision,
                plan_id,
                ReviseReferenceValidationPlan(
                    body.expected_current_revision_id, body.content.content(), body.change_reason
                ),
            )
        except Exception as error:
            raise _translate(context, error) from error
        _etag(response, value.current.record)
        return ValidationPlanResponse.from_snapshot(value)

    @application.get(
        "/api/v1/validation-plans",
        operation_id="listValidationPlans",
        response_model=ValidationPlanListResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["validation"],
    )
    def list_plans(
        request: Request, limit: Annotated[int, Query(ge=1, le=200)] = 100
    ) -> ValidationPlanListResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            items = service.list_plans(context, decision, limit=limit)
        except Exception as error:
            raise _translate(context, error) from error
        return ValidationPlanListResponse(
            items=tuple(ValidationPlanResponse.from_snapshot(item) for item in items)
        )

    @application.get(
        "/api/v1/validation-plans/{plan_id}",
        operation_id="getValidationPlan",
        response_model=ValidationPlanResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["validation"],
    )
    def get_plan(request: Request, response: Response, plan_id: UUID) -> ValidationPlanResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            value = service.get_plan(context, decision, plan_id)
        except Exception as error:
            raise _translate(context, error) from error
        _etag(response, value.current.record)
        return ValidationPlanResponse.from_snapshot(value)

    @application.post(
        "/api/v1/validation-runs",
        operation_id="submitReferenceValidationRun",
        response_model=ValidationRunResponse,
        status_code=status.HTTP_202_ACCEPTED,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(execute_dependency)],
        tags=["validation"],
    )
    async def submit_run(
        request: Request, body: ValidationRunCreateRequest
    ) -> ValidationRunResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            value = await service.submit_run(
                context,
                decision,
                SubmitValidationRun(
                    body.validation_plan_id,
                    body.validation_plan_revision_id,
                    body.execution_mode,
                    body.external_job_reference,
                    body.change_reason,
                ),
            )
        except Exception as error:
            raise _translate(context, error) from error
        return ValidationRunResponse.from_detail(value)

    @application.get(
        "/api/v1/validation-runs/{run_id}",
        operation_id="getValidationRun",
        response_model=ValidationRunResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["validation"],
    )
    def get_run(request: Request, run_id: UUID) -> ValidationRunResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            value = service.get_run(context, decision, run_id)
        except Exception as error:
            raise _translate(context, error) from error
        return ValidationRunResponse.from_detail(value)

    @application.post(
        "/api/v1/validation-runs/{run_id}:poll",
        operation_id="pollReferenceValidationRun",
        response_model=ValidationRunResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(execute_dependency)],
        tags=["validation"],
    )
    async def poll_run(
        request: Request, run_id: UUID, body: ValidationPollRequest
    ) -> ValidationRunResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            value = await service.poll_reference_mock_run(
                context,
                decision,
                run_id,
                outcome=body.outcome,
                change_reason=body.change_reason,
            )
        except Exception as error:
            raise _translate(context, error) from error
        return ValidationRunResponse.from_detail(value)

    @application.post(
        "/api/v1/validation-runs/{run_id}:cancel",
        operation_id="cancelValidationRun",
        response_model=ValidationRunResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(execute_dependency)],
        tags=["validation"],
    )
    def cancel_run(
        request: Request, run_id: UUID, body: ValidationCancelRequest
    ) -> ValidationRunResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            value = service.cancel_run(context, decision, run_id, reason=body.change_reason)
        except Exception as error:
            raise _translate(context, error) from error
        return ValidationRunResponse.from_detail(value)

    @application.post(
        "/api/v1/validation-runs/{run_id}:attach-result",
        operation_id="attachManualValidationResult",
        response_model=ValidationRunResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(execute_dependency)],
        tags=["validation"],
    )
    async def attach_result(
        request: Request, run_id: UUID, body: ManualValidationAttachRequest
    ) -> ValidationRunResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            value = await service.attach_manual_result(
                context,
                decision,
                run_id,
                AttachManualValidationResult(
                    body.stdout_text, body.stderr_text, body.native_result_text, body.change_reason
                ),
            )
        except Exception as error:
            raise _translate(context, error) from error
        return ValidationRunResponse.from_detail(value)

    @application.post(
        "/api/v1/validation-runs/{run_id}:evaluate",
        operation_id="evaluateReferenceValidationRun",
        response_model=ValidationRunResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(execute_dependency)],
        tags=["validation"],
    )
    async def evaluate_run(
        request: Request, run_id: UUID, body: ValidationEvaluateRequest
    ) -> ValidationRunResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            value = await service.evaluate_reference_run(
                context,
                decision,
                run_id,
                EvaluateReferenceValidationRun(body.change_reason),
            )
        except Exception as error:
            raise _translate(context, error) from error
        return ValidationRunResponse.from_detail(value)

    @application.get(
        "/api/v1/validation-results/{validation_result_id}",
        operation_id="getValidationResult",
        response_model=ReferenceValidationResultResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["validation"],
    )
    def get_validation_result(
        request: Request, validation_result_id: UUID
    ) -> ReferenceValidationResultResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            value = service.get_validation_result(context, decision, validation_result_id)
        except Exception as error:
            raise _translate(context, error) from error
        return ReferenceValidationResultResponse.from_domain(value)

    @application.get(
        "/api/v1/validation-results/{validation_result_id}/curve",
        operation_id="previewValidationResultCurve",
        response_model=ValidationResultCurveResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["validation"],
    )
    async def preview_validation_result_curve(
        request: Request,
        validation_result_id: UUID,
        maximum_points: Annotated[int, Query(ge=2, le=10_000)] = 1_000,
    ) -> ValidationResultCurveResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            value = await service.preview_validation_result_curve(
                context,
                decision,
                validation_result_id,
                maximum_points=maximum_points,
            )
        except Exception as error:
            raise _translate(context, error) from error
        return ValidationResultCurveResponse.from_domain(value)

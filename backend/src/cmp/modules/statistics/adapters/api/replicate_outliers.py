"""Protected API for multi-replicate outlier review and calibration input scopes."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends, FastAPI, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from cmp.modules.identity_access.domain.authorization import DataClassification
from cmp.modules.statistics.adapters.api.statistics import (
    StatisticsProblem,
    _etag,
    _scope,
    _translate,
    _unavailable,
)
from cmp.modules.statistics.application.replicate_outlier_service import (
    CalibrationInputScopeSnapshot,
    CreateCalibrationInputScope,
    CreateReplicateOutlierAssessment,
    CreateReplicateOutlierPlan,
    ExecuteReplicateOutlierDetection,
    ReplicateOutlierAssessmentSnapshot,
    ReplicateOutlierDetectionRun,
    ReplicateOutlierPlanSnapshot,
    ReplicateOutlierService,
)
from cmp.modules.statistics.domain.reference_tensile_replicate_outlier import (
    CalibrationScopeDisposition,
    ReferenceReplicateOutlierAssessmentContent,
    ReferenceReplicateOutlierPlanContent,
    ReplicateOutlierAssessmentDecision,
    ReplicateOutlierEvidenceCode,
)
from cmp.shared.contracts.revisions import RevisionMetadataResponse

type Dependency = Callable[..., object]
type Reason = Annotated[str, StringConstraints(min_length=1, max_length=2000)]
type Label = Annotated[str, StringConstraints(min_length=1, max_length=160)]


class CreateOutlierPlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    classification: DataClassification
    plan_label: Label
    statistical_result_id: UUID
    statistical_result_revision_id: UUID
    absolute_modified_z_threshold: Annotated[float, Field(gt=0, le=20)] = 3.5
    change_reason: Reason


class ExecuteOutlierDetectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    detection_plan_id: UUID
    detection_plan_revision_id: UUID


class CreateOutlierAssessmentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    classification: DataClassification
    candidate_id: UUID
    detection_plan_id: UUID
    detection_plan_revision_id: UUID
    decision: ReplicateOutlierAssessmentDecision
    assessment_reason: Reason
    change_reason: Reason


class CreateCalibrationScopeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    classification: DataClassification
    scope_label: Label
    detection_run_id: UUID
    assessment_revision_ids: Annotated[tuple[UUID, ...], Field(max_length=50)] = ()
    change_reason: Reason


class OutlierPlanContentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    statistical_result_id: UUID
    statistical_result_revision_id: UUID
    detector: str
    feature: str
    absolute_modified_z_threshold: float
    automatic_exclusion: bool


class OutlierPlanResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    detection_plan_id: UUID
    plan_label: str
    current_revision: RevisionMetadataResponse
    content: OutlierPlanContentResponse

    @classmethod
    def from_snapshot(cls, value: ReplicateOutlierPlanSnapshot) -> OutlierPlanResponse:
        content = value.current.content
        return cls(
            detection_plan_id=value.id,
            plan_label=content.plan_label,
            current_revision=RevisionMetadataResponse.from_record(value.current.record, "draft"),
            content=OutlierPlanContentResponse(
                statistical_result_id=content.statistical_result_id,
                statistical_result_revision_id=content.statistical_result_revision_id,
                detector="absolute_modified_z_score_peak_stress",
                feature="peak_engineering_stress_pa",
                absolute_modified_z_threshold=content.absolute_modified_z_threshold,
                automatic_exclusion=False,
            ),
        )


class OutlierPlanListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: tuple[OutlierPlanResponse, ...]


class ReplicateOutlierCandidateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: UUID
    ordinal: int
    dataset_id: UUID
    dataset_revision_id: UUID
    test_run_id: UUID
    test_run_revision_id: UUID
    peak_engineering_stress_pa: float
    sample_median_peak_stress_pa: float
    sample_mad_peak_stress_pa: float
    absolute_modified_z_score: float | None
    threshold: float
    evidence_code: ReplicateOutlierEvidenceCode
    review_status: str


class ReplicateOutlierDetectionRunResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    detection_run_id: UUID
    classification: DataClassification
    detection_plan_id: UUID
    detection_plan_revision_id: UUID
    statistical_result_id: UUID
    statistical_result_revision_id: UUID
    selection_id: UUID
    selection_revision_id: UUID
    sample_count: int
    sample_median_peak_stress_pa: float
    sample_mad_peak_stress_pa: float
    candidate_count: int
    candidates: tuple[ReplicateOutlierCandidateResponse, ...]
    started_at: str
    ended_at: str

    @classmethod
    def from_domain(
        cls, value: ReplicateOutlierDetectionRun
    ) -> ReplicateOutlierDetectionRunResponse:
        return cls(
            detection_run_id=value.id,
            classification=value.classification,
            detection_plan_id=value.detection_plan_id,
            detection_plan_revision_id=value.detection_plan_revision_id,
            statistical_result_id=value.statistical_result_id,
            statistical_result_revision_id=value.statistical_result_revision_id,
            selection_id=value.selection_id,
            selection_revision_id=value.selection_revision_id,
            sample_count=value.sample_count,
            sample_median_peak_stress_pa=value.sample_median_peak_stress_pa,
            sample_mad_peak_stress_pa=value.sample_mad_peak_stress_pa,
            candidate_count=value.candidate_count,
            candidates=tuple(
                ReplicateOutlierCandidateResponse(
                    candidate_id=item.id,
                    ordinal=item.member.ordinal,
                    dataset_id=item.member.dataset_id,
                    dataset_revision_id=item.member.dataset_revision_id,
                    test_run_id=item.member.test_run_id,
                    test_run_revision_id=item.member.test_run_revision_id,
                    peak_engineering_stress_pa=item.member.peak_engineering_stress_pa,
                    sample_median_peak_stress_pa=item.sample_median_peak_stress_pa,
                    sample_mad_peak_stress_pa=item.sample_mad_peak_stress_pa,
                    absolute_modified_z_score=item.absolute_modified_z_score,
                    threshold=item.threshold,
                    evidence_code=item.evidence_code,
                    review_status="review_required",
                )
                for item in value.candidates
            ),
            started_at=value.started_at.isoformat(),
            ended_at=value.ended_at.isoformat(),
        )


class ReplicateOutlierAssessmentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assessment_id: UUID
    current_revision: RevisionMetadataResponse
    candidate_id: UUID
    detection_plan_id: UUID
    detection_plan_revision_id: UUID
    decision: ReplicateOutlierAssessmentDecision
    assessment_reason: str
    automatic_exclusion: bool

    @classmethod
    def from_snapshot(
        cls, value: ReplicateOutlierAssessmentSnapshot
    ) -> ReplicateOutlierAssessmentResponse:
        content = value.current.content
        return cls(
            assessment_id=value.id,
            current_revision=RevisionMetadataResponse.from_record(value.current.record, "draft"),
            candidate_id=content.candidate_id,
            detection_plan_id=content.detection_plan_id,
            detection_plan_revision_id=content.detection_plan_revision_id,
            decision=content.decision,
            assessment_reason=content.assessment_reason,
            automatic_exclusion=False,
        )


class ReplicateOutlierAssessmentListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: tuple[ReplicateOutlierAssessmentResponse, ...]


class CalibrationScopeMemberResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ordinal: int
    dataset_id: UUID
    dataset_revision_id: UUID
    test_run_id: UUID
    test_run_revision_id: UUID
    disposition: CalibrationScopeDisposition
    candidate_id: UUID | None
    assessment_id: UUID | None
    assessment_revision_id: UUID | None


class CalibrationScopeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scope_id: UUID
    scope_label: str
    current_revision: RevisionMetadataResponse
    source_selection_id: UUID
    source_selection_revision_id: UUID
    statistical_result_id: UUID
    statistical_result_revision_id: UUID
    detection_plan_id: UUID
    detection_plan_revision_id: UUID
    source_member_count: int
    included_member_count: int
    excluded_member_count: int
    members: tuple[CalibrationScopeMemberResponse, ...]

    @classmethod
    def from_snapshot(cls, value: CalibrationInputScopeSnapshot) -> CalibrationScopeResponse:
        content = value.current.content
        members = tuple(
            CalibrationScopeMemberResponse(
                ordinal=item.ordinal,
                dataset_id=item.dataset_id,
                dataset_revision_id=item.dataset_revision_id,
                test_run_id=item.test_run_id,
                test_run_revision_id=item.test_run_revision_id,
                disposition=item.disposition,
                candidate_id=item.candidate_id,
                assessment_id=item.assessment_id,
                assessment_revision_id=item.assessment_revision_id,
            )
            for item in content.members
        )
        return cls(
            scope_id=value.id,
            scope_label=content.scope_label,
            current_revision=RevisionMetadataResponse.from_record(value.current.record, "draft"),
            source_selection_id=content.source_selection_id,
            source_selection_revision_id=content.source_selection_revision_id,
            statistical_result_id=content.statistical_result_id,
            statistical_result_revision_id=content.statistical_result_revision_id,
            detection_plan_id=content.detection_plan_id,
            detection_plan_revision_id=content.detection_plan_revision_id,
            source_member_count=len(members),
            included_member_count=sum(
                item.disposition is CalibrationScopeDisposition.INCLUDED for item in members
            ),
            excluded_member_count=sum(
                item.disposition is CalibrationScopeDisposition.EXCLUDED for item in members
            ),
            members=members,
        )


class CalibrationScopeListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: tuple[CalibrationScopeResponse, ...]


def install_replicate_outlier_api(
    application: FastAPI,
    *,
    service: ReplicateOutlierService | None,
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
        "/api/v1/replicate-outlier-detection-plans",
        operation_id="createReplicateOutlierDetectionPlan",
        response_model=OutlierPlanResponse,
        status_code=status.HTTP_201_CREATED,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(execute_dependency)],
        tags=["statistics"],
    )
    def create_plan(
        request: Request, response: Response, body: CreateOutlierPlanRequest
    ) -> OutlierPlanResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            result = service.create_plan(
                context,
                decision,
                CreateReplicateOutlierPlan(
                    classification=body.classification,
                    content=ReferenceReplicateOutlierPlanContent(
                        plan_label=body.plan_label,
                        statistical_result_id=body.statistical_result_id,
                        statistical_result_revision_id=body.statistical_result_revision_id,
                        absolute_modified_z_threshold=body.absolute_modified_z_threshold,
                    ),
                    change_reason=body.change_reason,
                ),
            )
        except Exception as error:
            raise _translate(context, error) from error
        response.headers["Location"] = f"/api/v1/replicate-outlier-detection-plans/{result.id}"
        _etag(response, result.current.record)
        return OutlierPlanResponse.from_snapshot(result)

    @application.get(
        "/api/v1/replicate-outlier-detection-plans",
        operation_id="listReplicateOutlierDetectionPlans",
        response_model=OutlierPlanListResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["statistics"],
    )
    def list_plans(
        request: Request, statistical_result_revision_id: UUID
    ) -> OutlierPlanListResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            items = service.list_plans(context, decision, statistical_result_revision_id)
        except Exception as error:
            raise _translate(context, error) from error
        return OutlierPlanListResponse(
            items=tuple(OutlierPlanResponse.from_snapshot(item) for item in items)
        )

    @application.post(
        "/api/v1/replicate-outlier-detection-runs",
        operation_id="executeReplicateOutlierDetection",
        response_model=ReplicateOutlierDetectionRunResponse,
        status_code=status.HTTP_201_CREATED,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(execute_dependency)],
        tags=["statistics"],
    )
    async def execute(
        request: Request, response: Response, body: ExecuteOutlierDetectionRequest
    ) -> ReplicateOutlierDetectionRunResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            result = await service.execute(
                context,
                decision,
                ExecuteReplicateOutlierDetection(
                    detection_plan_id=body.detection_plan_id,
                    detection_plan_revision_id=body.detection_plan_revision_id,
                ),
            )
        except Exception as error:
            raise _translate(context, error) from error
        response.headers["Location"] = f"/api/v1/replicate-outlier-detection-runs/{result.id}"
        response.headers["Cache-Control"] = "no-store"
        return ReplicateOutlierDetectionRunResponse.from_domain(result)

    @application.get(
        "/api/v1/replicate-outlier-detection-runs/{run_id}",
        operation_id="getReplicateOutlierDetectionRun",
        response_model=ReplicateOutlierDetectionRunResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["statistics"],
    )
    def get_run(request: Request, run_id: UUID) -> ReplicateOutlierDetectionRunResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            result = service.get_detection_run(context, decision, run_id)
        except Exception as error:
            raise _translate(context, error) from error
        return ReplicateOutlierDetectionRunResponse.from_domain(result)

    @application.post(
        "/api/v1/replicate-outlier-assessments",
        operation_id="createReplicateOutlierAssessment",
        response_model=ReplicateOutlierAssessmentResponse,
        status_code=status.HTTP_201_CREATED,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(execute_dependency)],
        tags=["statistics"],
    )
    def create_assessment(
        request: Request, response: Response, body: CreateOutlierAssessmentRequest
    ) -> ReplicateOutlierAssessmentResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            result = service.create_assessment(
                context,
                decision,
                CreateReplicateOutlierAssessment(
                    classification=body.classification,
                    content=ReferenceReplicateOutlierAssessmentContent(
                        candidate_id=body.candidate_id,
                        detection_plan_id=body.detection_plan_id,
                        detection_plan_revision_id=body.detection_plan_revision_id,
                        decision=body.decision,
                        assessment_reason=body.assessment_reason,
                    ),
                    change_reason=body.change_reason,
                ),
            )
        except Exception as error:
            raise _translate(context, error) from error
        response.headers["Location"] = f"/api/v1/replicate-outlier-assessments/{result.id}"
        _etag(response, result.current.record)
        return ReplicateOutlierAssessmentResponse.from_snapshot(result)

    @application.get(
        "/api/v1/replicate-outlier-assessments",
        operation_id="listReplicateOutlierAssessments",
        response_model=ReplicateOutlierAssessmentListResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["statistics"],
    )
    def list_assessments(
        request: Request, candidate_id: UUID
    ) -> ReplicateOutlierAssessmentListResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            items = service.list_assessments(context, decision, candidate_id)
        except Exception as error:
            raise _translate(context, error) from error
        return ReplicateOutlierAssessmentListResponse(
            items=tuple(
                ReplicateOutlierAssessmentResponse.from_snapshot(item) for item in items
            )
        )

    @application.post(
        "/api/v1/reference-calibration-input-scopes",
        operation_id="createReferenceCalibrationInputScope",
        response_model=CalibrationScopeResponse,
        status_code=status.HTTP_201_CREATED,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(execute_dependency)],
        tags=["statistics"],
    )
    def create_scope(
        request: Request, response: Response, body: CreateCalibrationScopeRequest
    ) -> CalibrationScopeResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            result = service.create_scope(
                context,
                decision,
                CreateCalibrationInputScope(
                    classification=body.classification,
                    scope_label=body.scope_label,
                    detection_run_id=body.detection_run_id,
                    assessment_revision_ids=body.assessment_revision_ids,
                    change_reason=body.change_reason,
                ),
            )
        except Exception as error:
            raise _translate(context, error) from error
        response.headers["Location"] = f"/api/v1/reference-calibration-input-scopes/{result.id}"
        _etag(response, result.current.record)
        return CalibrationScopeResponse.from_snapshot(result)

    @application.get(
        "/api/v1/reference-calibration-input-scopes/{scope_id}",
        operation_id="getReferenceCalibrationInputScope",
        response_model=CalibrationScopeResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["statistics"],
    )
    def get_scope(request: Request, response: Response, scope_id: UUID) -> CalibrationScopeResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            result = service.get_scope(context, decision, scope_id)
        except Exception as error:
            raise _translate(context, error) from error
        _etag(response, result.current.record)
        return CalibrationScopeResponse.from_snapshot(result)

    @application.get(
        "/api/v1/reference-calibration-input-scopes",
        operation_id="listReferenceCalibrationInputScopes",
        response_model=CalibrationScopeListResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["statistics"],
    )
    def list_scopes(
        request: Request, statistical_result_revision_id: UUID
    ) -> CalibrationScopeListResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            items = service.list_scopes(context, decision, statistical_result_revision_id)
        except Exception as error:
            raise _translate(context, error) from error
        return CalibrationScopeListResponse(
            items=tuple(CalibrationScopeResponse.from_snapshot(item) for item in items)
        )

"""HTTP contract for governed linear-viscoelastic calibration Plans and Runs."""

from __future__ import annotations

import logging
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
from cmp.modules.modeling.adapters.api.linear_viscoelastic_calibration_evidence import (
    ResponseResidualEvidenceResponse,
)
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
from cmp.modules.modeling.application.linear_viscoelastic_input_resolution import (
    ProcessedViscoelasticFitInput,
)
from cmp.modules.modeling.application.linear_viscoelastic_plan_governance import (
    PlanApprovalRecord,
    PlanContextQuery,
    PlanGovernanceError,
    PlanUsabilityFact,
)
from cmp.modules.modeling.domain.linear_viscoelastic_calibration import (
    CalibrationWeights,
    ChannelAvailability,
    DataAvailability,
    ExactRevisionPin,
    ParameterBound,
    PointDisposition,
    PointPartition,
)
from cmp.modules.modeling.domain.linear_viscoelastic_contracts import LinearViscoelasticInputError

LOGGER = logging.getLogger("cmp.modeling.linear_viscoelastic_calibration")

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
    candidate_scope_mode: Literal["automatic", "manual"] | None = None
    term_counts: tuple[int, ...] | None = Field(default=None, min_length=1)
    parameter_bounds: dict[int, tuple[ParameterBoundRequest, ...]] | None = None
    start_vectors: dict[int, tuple[tuple[float, ...], ...]] | None = None
    weights: CalibrationWeightsRequest
    optimizer: OptimizerPolicyRequest
    recommendation_policy: Literal["lowest_bic_then_term_count_then_attempt_ordinal@1.0.0"]
    change_reason: Reason
    setup_name: str | None = Field(default=None, max_length=255)
    material: ExactRevisionRequest | None = None
    material_state: ExactRevisionRequest | None = None
    input_mode: Literal["relaxation", "dma", "dma_frequency_master_curve"] | None = None
    based_on_plan_id: UUID | None = None
    based_on_plan_revision_id: UUID | None = None
    override_reason: Reason | None = None

    def to_command(
        self, idempotency_key: str | None
    ) -> CreateGovernedLinearViscoelasticCalibrationPlan:
        return CreateGovernedLinearViscoelasticCalibrationPlan(
            test_data_id=self.test_data.id,
            test_data_revision_id=self.test_data.revision_id,
            selected_temperature_k=self.selected_temperature_k,
            point_dispositions=tuple(item.to_domain() for item in self.point_dispositions),
            availability=self.availability.to_domain(),
            term_counts=self.term_counts or (),
            parameter_bounds={
                key: tuple(item.to_domain() for item in values)
                for key, values in (self.parameter_bounds or {}).items()
            },
            start_vectors=self.start_vectors or {},
            weights=self.weights.to_domain(),
            recommendation_policy=self.recommendation_policy,
            ftol=self.optimizer.ftol,
            xtol=self.optimizer.xtol,
            gtol=self.optimizer.gtol,
            max_nfev=self.optimizer.max_nfev,
            change_reason=self.change_reason,
            idempotency_key=idempotency_key,
            setup_name=self.setup_name,
            material=(
                ExactRevisionPin(self.material.id, self.material.revision_id)
                if self.material is not None
                else None
            ),
            material_state=(
                ExactRevisionPin(self.material_state.id, self.material_state.revision_id)
                if self.material_state is not None
                else None
            ),
            input_mode=self.input_mode,
            based_on_plan_id=self.based_on_plan_id,
            based_on_plan_revision_id=self.based_on_plan_revision_id,
            override_reason=self.override_reason,
            candidate_scope_mode=self.candidate_scope_mode,
        )


class ProcessedLinearViscoelasticPlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    processing_output: ExactRevisionRequest
    availability: ChannelAvailabilityRequest
    candidate_scope_mode: Literal["automatic", "manual"] | None = None
    term_counts: tuple[int, ...] | None = Field(default=None, min_length=1)
    parameter_bounds: dict[int, tuple[ParameterBoundRequest, ...]] | None = None
    start_vectors: dict[int, tuple[tuple[float, ...], ...]] | None = None
    weights: CalibrationWeightsRequest
    optimizer: OptimizerPolicyRequest
    recommendation_policy: Literal["lowest_bic_then_term_count_then_attempt_ordinal@1.0.0"]
    change_reason: Reason
    setup_name: str | None = Field(default=None, max_length=255)
    material: ExactRevisionRequest | None = None
    material_state: ExactRevisionRequest | None = None
    input_mode: Literal["relaxation", "dma", "dma_frequency_master_curve"] | None = None
    based_on_plan_id: UUID | None = None
    based_on_plan_revision_id: UUID | None = None
    override_reason: Reason | None = None

    def to_command(
        self, idempotency_key: str | None
    ) -> CreateProcessedLinearViscoelasticCalibrationPlan:
        return CreateProcessedLinearViscoelasticCalibrationPlan(
            processing_output_id=self.processing_output.id,
            processing_output_revision_id=self.processing_output.revision_id,
            availability=self.availability.to_domain(),
            term_counts=self.term_counts or (),
            parameter_bounds={
                key: tuple(item.to_domain() for item in values)
                for key, values in (self.parameter_bounds or {}).items()
            },
            start_vectors=self.start_vectors or {},
            weights=self.weights.to_domain(),
            recommendation_policy=self.recommendation_policy,
            ftol=self.optimizer.ftol,
            xtol=self.optimizer.xtol,
            gtol=self.optimizer.gtol,
            max_nfev=self.optimizer.max_nfev,
            change_reason=self.change_reason,
            idempotency_key=idempotency_key,
            setup_name=self.setup_name,
            material=(
                ExactRevisionPin(self.material.id, self.material.revision_id)
                if self.material is not None
                else None
            ),
            material_state=(
                ExactRevisionPin(self.material_state.id, self.material_state.revision_id)
                if self.material_state is not None
                else None
            ),
            input_mode=self.input_mode,
            based_on_plan_id=self.based_on_plan_id,
            based_on_plan_revision_id=self.based_on_plan_revision_id,
            override_reason=self.override_reason,
            candidate_scope_mode=self.candidate_scope_mode,
        )


class ProcessedFitInputChannelResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    channel: Literal["dma_storage", "dma_loss"]
    quantity: Literal["mechanics.modulus.storage", "mechanics.modulus.loss"]
    unit: Literal["Pa"]


class ProcessedFitInputRowResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    ordinal: Annotated[int, Field(ge=0)]
    coordinate: float | None
    # Preserve excluded source rows exactly. Positivity is enforced for active rows by
    # the governed input resolver; an excluded row may retain a non-physical source
    # value so the UI can show why it was excluded instead of silently deleting it.
    storage_modulus_pa: float
    loss_modulus_pa: float
    partition: PointPartition
    exclusion_reason: str | None = Field(max_length=500)


class ProcessedFitInputResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    mode: Literal["dma_frequency_master_curve"]
    coordinate_quantity: Literal["frequency.angular.reduced"]
    coordinate_unit: Literal["rad/s"]
    response_channels: tuple[ProcessedFitInputChannelResponse, ...]
    reference_temperature_k: Annotated[Decimal, Field(gt=0)]
    rows: Annotated[tuple[ProcessedFitInputRowResponse, ...], Field(max_length=100_000)]

    @classmethod
    def from_domain(cls, value: ProcessedViscoelasticFitInput) -> ProcessedFitInputResponse:
        return cls.model_validate(
            {
                "mode": value.mode,
                "coordinate_quantity": value.coordinate_quantity,
                "coordinate_unit": value.coordinate_unit,
                "response_channels": [
                    {
                        "channel": channel.channel,
                        "quantity": channel.quantity,
                        "unit": channel.unit,
                    }
                    for channel in value.response_channels
                ],
                "reference_temperature_k": value.reference_temperature_k,
                "rows": [
                    {
                        "ordinal": row.ordinal,
                        "coordinate": row.coordinate,
                        "storage_modulus_pa": row.storage_modulus_pa,
                        "loss_modulus_pa": row.loss_modulus_pa,
                        "partition": row.partition,
                        "exclusion_reason": row.exclusion_reason,
                    }
                    for row in value.rows
                ],
            }
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


class ExactRevisionPinResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID
    revision_id: UUID
    sha256: str | None = None

    @classmethod
    def from_domain(cls, value: ExactRevisionPin) -> ExactRevisionPinResponse:
        return cls(
            id=value.aggregate_id,
            revision_id=value.revision_id,
            sha256=value.sha256,
        )


class PlanApprovalResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    plan_id: UUID
    plan_revision_id: UUID
    plan_sha256: str
    setup_name: str
    input_mode: Literal["relaxation", "dma", "dma_frequency_master_curve"]
    material: ExactRevisionPinResponse
    material_state: ExactRevisionPinResponse
    test_data: ExactRevisionPinResponse
    processing_output: ExactRevisionPinResponse | None
    state: Literal["active", "superseded", "withdrawn"]
    review_request_id: UUID
    review_decision_id: UUID
    evidence_sha256: str
    approved_at: datetime
    approved_by: UUID
    superseded_by_plan_id: UUID | None = None
    superseded_by_plan_revision_id: UUID | None = None

    @classmethod
    def from_domain(cls, value: PlanApprovalRecord) -> PlanApprovalResponse:
        return cls(
            plan_id=value.plan_id,
            plan_revision_id=value.plan_revision_id,
            plan_sha256=value.plan_sha256,
            setup_name=value.setup_name,
            input_mode=value.input_mode,
            material=ExactRevisionPinResponse.from_domain(value.material),
            material_state=ExactRevisionPinResponse.from_domain(value.material_state),
            test_data=ExactRevisionPinResponse.from_domain(value.test_data),
            processing_output=(
                ExactRevisionPinResponse.from_domain(value.processing_output)
                if value.processing_output is not None
                else None
            ),
            state=value.state.value,
            review_request_id=value.review_request_id,
            review_decision_id=value.review_decision_id,
            evidence_sha256=value.evidence_sha256,
            approved_at=value.approved_at,
            approved_by=value.approved_by,
            superseded_by_plan_id=value.superseded_by_plan_id,
            superseded_by_plan_revision_id=value.superseded_by_plan_revision_id,
        )


class PlanContextResolveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    material: ExactRevisionRequest
    material_state: ExactRevisionRequest
    test_data: ExactRevisionRequest
    processing_output: ExactRevisionRequest | None = None
    input_mode: Literal["relaxation", "dma", "dma_frequency_master_curve"]

    def to_query(self) -> PlanContextQuery:
        return PlanContextQuery(
            material=ExactRevisionPin(self.material.id, self.material.revision_id),
            material_state=ExactRevisionPin(
                self.material_state.id, self.material_state.revision_id
            ),
            test_data=ExactRevisionPin(self.test_data.id, self.test_data.revision_id),
            processing_output=(
                ExactRevisionPin(
                    self.processing_output.id,
                    self.processing_output.revision_id,
                )
                if self.processing_output is not None
                else None
            ),
            input_mode=self.input_mode,
        )


class PlanContextMatchResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    plan_id: UUID
    plan_revision_id: UUID
    plan_sha256: str
    setup_name: str
    input_mode: Literal["relaxation", "dma", "dma_frequency_master_curve"]
    material: ExactRevisionPinResponse
    material_state: ExactRevisionPinResponse
    test_data: ExactRevisionPinResponse
    processing_output: ExactRevisionPinResponse | None
    approval: PlanApprovalResponse

    @classmethod
    def from_domain(cls, value: PlanApprovalRecord) -> PlanContextMatchResponse:
        return cls(
            plan_id=value.plan_id,
            plan_revision_id=value.plan_revision_id,
            plan_sha256=value.plan_sha256,
            setup_name=value.setup_name,
            input_mode=value.input_mode,
            material=ExactRevisionPinResponse.from_domain(value.material),
            material_state=ExactRevisionPinResponse.from_domain(value.material_state),
            test_data=ExactRevisionPinResponse.from_domain(value.test_data),
            processing_output=(
                ExactRevisionPinResponse.from_domain(value.processing_output)
                if value.processing_output is not None
                else None
            ),
            approval=PlanApprovalResponse.from_domain(value),
        )


class PlanContextResolveResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    summary: str
    selection_required: bool
    matches: tuple[PlanContextMatchResponse, ...]


class PlanUsabilityChangeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    plan_revision_id: UUID
    reason: Reason


class PlanSupersedeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    plan_revision_id: UUID
    successor_plan_id: UUID
    successor_plan_revision_id: UUID
    reason: Reason


class PlanUsabilityFactResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fact_id: UUID
    plan_id: UUID
    plan_revision_id: UUID
    state: Literal["active", "superseded", "withdrawn"]
    actor_id: UUID
    reason: str
    occurred_at: datetime
    successor_plan_id: UUID | None
    successor_plan_revision_id: UUID | None

    @classmethod
    def from_domain(cls, value: PlanUsabilityFact) -> PlanUsabilityFactResponse:
        return cls(
            fact_id=value.fact_id,
            plan_id=value.plan_id,
            plan_revision_id=value.plan_revision_id,
            state=value.state.value,
            actor_id=value.actor_id,
            reason=value.reason,
            occurred_at=value.occurred_at,
            successor_plan_id=value.successor_plan_id,
            successor_plan_revision_id=value.successor_plan_revision_id,
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
    approval_request_id: UUID | None = None
    approval_decision_id: UUID | None = None
    approval_evidence_sha256: str | None = None
    approval_state: Literal["active", "superseded", "withdrawn"] | None = None
    approval_approved_at: datetime | None = None
    approval_approved_by: UUID | None = None
    execution_context: dict[str, Any] | None = None

    @classmethod
    def from_domain(cls, value: CalibrationRunProjection) -> RunResponse:
        result = value.result
        candidates = []
        if result:
            for item in result.candidates:
                candidate = item.canonical()
                # Selection requires the server's canonical Candidate digest.  Keep the
                # numerical payload untouched and transport the already-computed digest
                # alongside it so clients never have to recreate Python float canonicalisation.
                candidate["candidate_sha256"] = item.digest
                candidates.append(candidate)
        return cls(
            run_id=value.id,
            plan_revision_id=value.plan_revision_id,
            status=value.status,
            attempts=tuple(item.canonical() for item in result.attempts) if result else (),
            candidates=tuple(candidates),
            recommendation=result.recommendation.canonical()
            if result and result.recommendation
            else None,
            failure_code=value.failure_code,
            failure_detail=value.failure_detail,
            recovery_hint=value.recovery_hint,
            execution_ledger_sha256=value.execution_ledger_sha256,
            approval_request_id=value.approval_request_id,
            approval_decision_id=value.approval_decision_id,
            approval_evidence_sha256=value.approval_evidence_sha256,
            approval_state=value.approval_state,
            approval_approved_at=value.approval_approved_at,
            approval_approved_by=value.approval_approved_by,
            execution_context=(
                {
                    "material": ExactRevisionPinResponse.from_domain(
                        value.execution_material
                    ).model_dump(mode="json")
                    if value.execution_material is not None
                    else None,
                    "material_state": ExactRevisionPinResponse.from_domain(
                        value.execution_material_state
                    ).model_dump(mode="json")
                    if value.execution_material_state is not None
                    else None,
                    "test_data": ExactRevisionPinResponse.from_domain(
                        value.execution_test_data
                    ).model_dump(mode="json")
                    if value.execution_test_data is not None
                    else None,
                    "processing_output": ExactRevisionPinResponse.from_domain(
                        value.execution_processing_output
                    ).model_dump(mode="json")
                    if value.execution_processing_output is not None
                    else None,
                    "input_mode": value.execution_input_mode,
                }
                if value.execution_test_data is not None
                else None
            ),
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
    if isinstance(error, PlanGovernanceError):
        unauthorized = error.code in {
            "PLAN_AUTHOR_UNAUTHORIZED",
            "PLAN_APPROVER_UNAUTHORIZED",
            "PLAN_MANAGER_UNAUTHORIZED",
        }
        unavailable = error.code == "PLAN_APPROVAL_UNAVAILABLE"
        return LinearViscoelasticHttpError(
            context,
            503 if unavailable else 403 if unauthorized else 409,
            str(error),
            code=error.code,
            location="approval" if error.code.startswith("PLAN_APPROVAL") else "source",
            recovery_hint=error.recovery_hint,
        )
    if isinstance(error, LinearViscoelasticInputError):
        return LinearViscoelasticHttpError(
            context,
            409 if error.code == "INPUT_UPSTREAM_STALE" else 422,
            str(error),
            code=error.code,
            location="source",
            recovery_hint=error.recovery_hint,
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
    LOGGER.error(
        "unexpected linear-viscoelastic calibration failure",
        exc_info=(type(error), error, error.__traceback__),
    )
    return LinearViscoelasticHttpError(
        context,
        503,
        "service is unavailable",
        code="SERVICE_UNAVAILABLE",
        location="service",
        recovery_hint="Retry after the modeling service is available.",
    )


def _require_governed_request(body: object) -> None:
    if getattr(body, "setup_name", None) is None:
        raise PlanGovernanceError(
            "setup_name is required for a governed calibration Plan",
            code="PLAN_SETUP_REQUIRED",
            recovery_hint="Name the setup before submitting it for review.",
        )


def install_linear_viscoelastic_calibration_api(
    application: FastAPI,
    *,
    service: LinearViscoelasticCalibrationService | None,
    security_dependency: Dependency,
    read_dependency: Dependency,
    write_dependency: Dependency,
    execute_dependency: Dependency,
    review_decide_dependency: Dependency | None = None,
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
            _require_governed_request(body)
            value = service.create_governed_plan(
                context,
                decision,
                body.to_command(idempotency_key),
            )
        except Exception as error:
            raise _translate(context, error) from error
        response.headers["Location"] = f"/api/v1/linear-viscoelastic-calibration-plans/{value.id}"
        return PlanResponse.from_domain(value)

    @application.post(
        "/api/v1/linear-viscoelastic-calibration-plans/resolve",
        operation_id="resolveLinearViscoelasticCalibrationPlanContext",
        response_model=PlanContextResolveResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["modeling"],
        summary="Resolve every active approved setup for one exact source context.",
    )
    def resolve_plan_context(
        request: Request,
        body: PlanContextResolveRequest,
    ) -> PlanContextResolveResponse:
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
            result = service.resolve_plan_context(context, decision, body.to_query())
            return PlanContextResolveResponse(
                summary=result.summary,
                selection_required=result.selection_required,
                matches=tuple(
                    PlanContextMatchResponse.from_domain(item) for item in result.matches
                ),
            )
        except Exception as error:
            raise _translate(context, error) from error

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

    @application.get(
        "/api/v1/linear-viscoelastic-calibration-plans/{plan_id}/approval",
        operation_id="getLinearViscoelasticCalibrationPlanApproval",
        response_model=PlanApprovalResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["modeling"],
    )
    def get_plan_approval(
        request: Request,
        plan_id: UUID,
        plan_revision_id: UUID,
    ) -> PlanApprovalResponse:
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
            return PlanApprovalResponse.from_domain(
                service.get_plan_approval(context, decision, plan_id, plan_revision_id)
            )
        except Exception as error:
            raise _translate(context, error) from error

    manager_dependencies = [Depends(security_dependency)]
    if review_decide_dependency is not None:
        manager_dependencies.append(Depends(review_decide_dependency))

    @application.post(
        "/api/v1/linear-viscoelastic-calibration-plans/{plan_id}/supersede",
        operation_id="supersedeLinearViscoelasticCalibrationPlan",
        response_model=PlanUsabilityFactResponse,
        status_code=status.HTTP_201_CREATED,
        responses=errors,
        dependencies=manager_dependencies,
        tags=["modeling"],
    )
    def supersede_plan(
        request: Request,
        plan_id: UUID,
        body: PlanSupersedeRequest,
    ) -> PlanUsabilityFactResponse:
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
            result = service.supersede_plan(
                context,
                decision,
                plan_id=plan_id,
                plan_revision_id=body.plan_revision_id,
                successor_plan_id=body.successor_plan_id,
                successor_plan_revision_id=body.successor_plan_revision_id,
                reason=body.reason,
            )
            return PlanUsabilityFactResponse.from_domain(result)
        except Exception as error:
            raise _translate(context, error) from error

    @application.post(
        "/api/v1/linear-viscoelastic-calibration-plans/{plan_id}/withdraw",
        operation_id="withdrawLinearViscoelasticCalibrationPlan",
        response_model=PlanUsabilityFactResponse,
        status_code=status.HTTP_201_CREATED,
        responses=errors,
        dependencies=manager_dependencies,
        tags=["modeling"],
    )
    def withdraw_plan(
        request: Request,
        plan_id: UUID,
        body: PlanUsabilityChangeRequest,
    ) -> PlanUsabilityFactResponse:
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
            result = service.withdraw_plan(
                context,
                decision,
                plan_id=plan_id,
                plan_revision_id=body.plan_revision_id,
                reason=body.reason,
            )
            return PlanUsabilityFactResponse.from_domain(result)
        except Exception as error:
            raise _translate(context, error) from error

    @application.get(
        "/api/v1/processing-outputs/{processing_output_id}/revisions/{processing_output_revision_id}/linear-viscoelastic-fit-input",
        operation_id="getProcessedLinearViscoelasticFitInput",
        response_model=ProcessedFitInputResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["modeling"],
        summary="Read the exact validated DMA master-curve values used by polymer calibration.",
    )
    def get_processed_fit_input(
        request: Request,
        processing_output_id: UUID,
        processing_output_revision_id: UUID,
    ) -> ProcessedFitInputResponse:
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
            return ProcessedFitInputResponse.from_domain(
                service.get_processed_fit_input(
                    context,
                    decision,
                    processing_output_id,
                    processing_output_revision_id,
                )
            )
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
            _require_governed_request(body)
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
        "/api/v1/linear-viscoelastic-calibration-runs/{run_id}/response-residuals",
        operation_id="getLinearViscoelasticCalibrationResponseResiduals",
        response_model=ResponseResidualEvidenceResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["modeling"],
        summary=(
            "Read verified response-residual evidence for one exact succeeded calibration Run."
        ),
    )
    async def get_response_residuals(
        request: Request, run_id: UUID
    ) -> ResponseResidualEvidenceResponse:
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
            value = await service.get_response_residual_evidence(context, decision, run_id)
            return ResponseResidualEvidenceResponse.from_domain(value)
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
                {
                    **item.canonical(),
                    # The digest is computed by the immutable domain Candidate and
                    # is required by the Selection request.
                    "candidate_sha256": item.digest,
                }
                for item in service.list_candidates(context, decision, run_id)
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

"""Application commands, immutable projections, and ports for linear-viscoelastic modeling.

This module is deliberately free of persistence and transport implementations.  It defines the
application boundary shared by the plan, run, and selection command components.
"""

from __future__ import annotations

import asyncio
import hashlib
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING, Protocol
from uuid import UUID

from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
    Permission,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.modeling.domain.linear_viscoelastic_calibration import (
    CalibrationRunResult,
    CalibrationWeights,
    CanonicalViscoelasticInput,
    ChannelAvailability,
    ExactRevisionPin,
    LinearViscoelasticCalibrationPlan,
    LinearViscoelasticSelection,
    ParameterBound,
    PointDisposition,
)
from cmp.shared.domain.revisions import canonical_json_bytes

if TYPE_CHECKING:
    from cmp.modules.artifacts.application.content import ArtifactService
    from cmp.modules.identity_access.application.authorization import AuthorizationService
    from cmp.modules.jobs.application.jobs import JobService
    from cmp.modules.modeling.application.linear_viscoelastic_input_resolution import (
        GovernedLinearViscoelasticInputResolver,
    )
    from cmp.modules.modeling.application.linear_viscoelastic_plan_governance import (
        LinearViscoelasticPlanApprovalPort,
    )
    from cmp.modules.modeling.application.linear_viscoelasticity import (
        LinearViscoelasticModelService,
    )
    from cmp.modules.modeling.domain.linear_viscoelastic_response_residuals import (
        LinearViscoelasticResponseResidualRow,
    )
    from cmp.modules.plugins.application.registry import PluginRegistryService

LINEAR_VISCOELASTIC_CALIBRATION_AGGREGATE_TYPE = "modeling.linear_viscoelastic_calibration"
LINEAR_VISCOELASTIC_CALIBRATION_PLAN_AGGREGATE_TYPE = (
    "modeling.linear_viscoelastic_calibration_plan"
)
LINEAR_VISCOELASTIC_CALIBRATION_SELECTION_AGGREGATE_TYPE = (
    "modeling.linear_viscoelastic_calibration_selection"
)


class LinearViscoelasticCalibrationConflict(Exception):
    """An exact revision, idempotency key, state, or result digest conflicts."""


class LinearViscoelasticCalibrationNotFound(Exception):
    """A tenant-scoped Plan, Run, Candidate, or Selection is not visible."""


class CalibrationJobTerminalConflict(LinearViscoelasticCalibrationConflict):
    """A terminal calibration Job cannot be retried in-place."""


class CalibrationAcceptedResultConflict(LinearViscoelasticCalibrationConflict):
    """A terminal Run already accepted a different immutable result digest."""

    code = "accepted_result_conflict"


class CalibrationErrorCode(StrEnum):
    TERMINAL_CALIBRATION_REQUIRES_NEW_RUN = "terminal_calibration_requires_new_run"
    ACCEPTED_RESULT_CONFLICT = "accepted_result_conflict"


@dataclass(frozen=True, slots=True)
class CreateLinearViscoelasticCalibrationPlan:
    plan: LinearViscoelasticCalibrationPlan
    classification: DataClassification
    change_reason: str
    idempotency_key: str | None = None
    request_sha256: str | None = None


@dataclass(frozen=True, slots=True)
class CreateGovernedLinearViscoelasticCalibrationPlan:
    test_data_id: UUID
    test_data_revision_id: UUID
    selected_temperature_k: Decimal | float
    point_dispositions: tuple[PointDisposition, ...]
    availability: ChannelAvailability
    term_counts: tuple[int, ...]
    parameter_bounds: Mapping[int, tuple[ParameterBound, ...]]
    start_vectors: Mapping[int, tuple[tuple[float, ...], ...]]
    weights: CalibrationWeights
    recommendation_policy: str
    ftol: float
    xtol: float
    gtol: float
    max_nfev: int
    change_reason: str
    idempotency_key: str | None = None
    # Client values are optional expected hints.  The application verifies them against the
    # exact server-resolved Test Data/Processing Output lineage before persisting a new Plan.
    setup_name: str | None = None
    material: ExactRevisionPin | None = None
    material_state: ExactRevisionPin | None = None
    input_mode: str | None = None
    based_on_plan_id: UUID | None = None
    based_on_plan_revision_id: UUID | None = None
    override_reason: str | None = None
    # None preserves the legacy/manual transport.  Automatic scope is resolved only after the
    # exact source resolver has returned its immutable row partitions.
    candidate_scope_mode: str | None = None


@dataclass(frozen=True, slots=True)
class CreateProcessedLinearViscoelasticCalibrationPlan:
    processing_output_id: UUID
    processing_output_revision_id: UUID
    availability: ChannelAvailability
    term_counts: tuple[int, ...]
    parameter_bounds: Mapping[int, tuple[ParameterBound, ...]]
    start_vectors: Mapping[int, tuple[tuple[float, ...], ...]]
    weights: CalibrationWeights
    recommendation_policy: str
    ftol: float
    xtol: float
    gtol: float
    max_nfev: int
    change_reason: str
    idempotency_key: str | None = None
    setup_name: str | None = None
    material: ExactRevisionPin | None = None
    material_state: ExactRevisionPin | None = None
    input_mode: str | None = None
    based_on_plan_id: UUID | None = None
    based_on_plan_revision_id: UUID | None = None
    override_reason: str | None = None
    candidate_scope_mode: str | None = None


@dataclass(frozen=True, slots=True)
class QueueLinearViscoelasticCalibrationRun:
    plan_id: UUID
    plan_revision_id: UUID
    change_reason: str
    idempotency_key: str
    request_sha256: str | None = None


@dataclass(frozen=True, slots=True)
class CreateLinearViscoelasticCalibrationSelection:
    plan_revision_id: UUID
    run_id: UUID
    candidate_id: UUID
    candidate_sha256: str
    reason: str
    warning_acknowledgements: tuple[Mapping[str, object], ...]
    change_reason: str
    idempotency_key: str | None = None


@dataclass(frozen=True, slots=True)
class PromoteLinearViscoelasticCalibrationSelection:
    selection_id: UUID
    material_id: UUID
    material_revision_id: UUID
    material_state_id: UUID
    material_state_revision_id: UUID
    property_set_id: UUID
    property_set_revision_id: UUID
    change_reason: str


@dataclass(frozen=True, slots=True)
class CalibrationPlanSnapshot:
    id: UUID
    current: LinearViscoelasticCalibrationPlan
    content_hash: str
    classification: DataClassification
    created_at: datetime
    created_by: UUID
    change_reason: str
    organization_id: UUID | None = None
    project_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class CalibrationJobReference:
    run_id: UUID
    job_id: UUID
    run_url: str
    job_url: str
    status: str = "queued"


@dataclass(frozen=True, slots=True)
class ExecutionLedgerEntry:
    attempt_id: UUID
    job_id: UUID
    job_attempt_no: int
    state: str
    failure_code: str | None = None
    failure_detail: str | None = None
    recovery_hint: str | None = None
    package_sha256: str | None = None
    submitted_at: datetime | None = None
    deadline_at: datetime | None = None
    result_manifest_artifact_id: UUID | None = None
    result_manifest_sha256: str | None = None


@dataclass(frozen=True, slots=True)
class CalibrationRunProjection:
    id: UUID
    plan_id: UUID
    plan_revision_id: UUID
    plan_sha256: str
    classification: DataClassification
    job_id: UUID
    status: str
    result: CalibrationRunResult | None
    execution_ledger: tuple[ExecutionLedgerEntry, ...]
    idempotency_key: str
    request_sha256: str
    created_at: datetime
    created_by: UUID
    failure_code: str | None = None
    failure_detail: str | None = None
    recovery_hint: str | None = None
    organization_id: UUID | None = None
    project_id: UUID | None = None
    # Immutable approval evidence captured at queue time.  Legacy #372 reference fixtures
    # leave these fields null; governed production Plans must populate the complete projection.
    approval_request_id: UUID | None = None
    approval_decision_id: UUID | None = None
    approval_evidence_sha256: str | None = None
    approval_state: str | None = None
    approval_approved_at: datetime | None = None
    approval_approved_by: UUID | None = None
    execution_material: ExactRevisionPin | None = None
    execution_material_state: ExactRevisionPin | None = None
    execution_test_data: ExactRevisionPin | None = None
    execution_processing_output: ExactRevisionPin | None = None
    execution_input_mode: str | None = None

    @property
    def execution_ledger_sha256(self) -> str:
        payload = [
            {
                "attempt_id": str(entry.attempt_id),
                "job_id": str(entry.job_id),
                "job_attempt_no": entry.job_attempt_no,
                "state": entry.state,
                "failure_code": entry.failure_code,
                "package_sha256": entry.package_sha256,
                "result_manifest_artifact_id": (
                    str(entry.result_manifest_artifact_id)
                    if entry.result_manifest_artifact_id is not None
                    else None
                ),
                "result_manifest_sha256": entry.result_manifest_sha256,
            }
            for entry in self.execution_ledger
        ]
        return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


@dataclass(frozen=True, slots=True)
class CalibrationResponseResidualArtifactEvidence:
    artifact_id: UUID
    sha256: str
    artifact_role: str
    schema_ref: str
    media_type: str
    size_bytes: int


@dataclass(frozen=True, slots=True)
class CalibrationResponseResidualProjection:
    run_id: UUID
    plan_revision_id: UUID
    recommendation_id: UUID
    candidate_id: UUID
    candidate_sha256: str
    recommendation_rule_version: str
    artifact: CalibrationResponseResidualArtifactEvidence
    rows: tuple[LinearViscoelasticResponseResidualRow, ...]


@dataclass(frozen=True, slots=True)
class CalibrationSelectionSnapshot:
    value: LinearViscoelasticSelection
    classification: DataClassification
    organization_id: UUID | None = None
    project_id: UUID | None = None


class LinearViscoelasticCalibrationRepository(Protocol):
    def save_plan(
        self,
        value: CalibrationPlanSnapshot,
        *,
        idempotency_key: str | None,
        context: SecurityContext | None = None,
        decision: AuthorizationDecision | None = None,
    ) -> CalibrationPlanSnapshot: ...

    def get_plan(
        self,
        plan_id: UUID,
        *,
        context: SecurityContext | None = None,
        decision: AuthorizationDecision | None = None,
    ) -> CalibrationPlanSnapshot: ...

    def get_plan_revision(
        self,
        plan_id: UUID,
        plan_revision_id: UUID,
        *,
        context: SecurityContext | None = None,
        decision: AuthorizationDecision | None = None,
    ) -> CalibrationPlanSnapshot: ...

    def save_run(
        self,
        value: CalibrationRunProjection,
        *,
        context: SecurityContext | None = None,
        decision: AuthorizationDecision | None = None,
    ) -> CalibrationRunProjection: ...

    def get_run(
        self,
        run_id: UUID,
        *,
        context: SecurityContext | None = None,
        decision: AuthorizationDecision | None = None,
    ) -> CalibrationRunProjection: ...

    def find_run_by_idempotency(
        self,
        idempotency_key: str,
        *,
        context: SecurityContext | None = None,
        decision: AuthorizationDecision | None = None,
    ) -> CalibrationRunProjection | None: ...

    def save_selection(
        self,
        value: CalibrationSelectionSnapshot,
        *,
        idempotency_key: str | None,
        context: SecurityContext | None = None,
        decision: AuthorizationDecision | None = None,
    ) -> CalibrationSelectionSnapshot: ...

    def get_selection(
        self,
        selection_id: UUID,
        *,
        context: SecurityContext | None = None,
        decision: AuthorizationDecision | None = None,
    ) -> CalibrationSelectionSnapshot: ...


class CalibrationApplicationState(Protocol):
    """State supplied by the public service to each cohesive command component."""

    _repository: LinearViscoelasticCalibrationRepository
    _id_factory: Callable[[], UUID]
    _clock: Callable[[], datetime]
    _inputs: dict[UUID, CanonicalViscoelasticInput]
    _job_service: JobService | None
    _artifact_service: ArtifactService | None
    _plugin_registry: PluginRegistryService | None
    _authorization: AuthorizationService | None
    _input_resolver: GovernedLinearViscoelasticInputResolver | None
    _linear_viscoelastic_models: LinearViscoelasticModelService | None
    _allow_reference_execution: bool
    _plan_governance: LinearViscoelasticPlanApprovalPort | None

    def _new_id(self) -> UUID: ...

    def create_plan(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CreateLinearViscoelasticCalibrationPlan,
    ) -> CalibrationPlanSnapshot: ...

    def get_run(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
    ) -> CalibrationRunProjection: ...


def _run_awaitable[T](value: Awaitable[T]) -> T:
    """Bridge synchronous modeling adapters to the async Artifact service."""

    try:
        asyncio.get_running_loop()
    except RuntimeError:

        async def wait_for_value() -> T:
            return await value

        return asyncio.run(wait_for_value())
    raise RuntimeError("durable calibration queue cannot run inside an active event loop")


def _reason(value: str) -> str:
    if not value or value != value.strip() or len(value) > 2_000 or "\x00" in value:
        raise ValueError("change_reason/reason must be trimmed and contain 1..2000 characters")
    return value


def _require(
    context: SecurityContext, decision: AuthorizationDecision, permission: Permission
) -> None:
    if (
        decision.permission is not permission
        or decision.principal_id != context.principal.id
        or decision.organization_id != context.organization_id
        or decision.project_id != context.project_id
        or decision.request_id != context.request_id
        or decision.trace_id != context.trace_id
    ):
        raise LinearViscoelasticCalibrationConflict("authorization decision does not match request")

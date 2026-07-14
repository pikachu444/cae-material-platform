"""Human Candidate Selection and immutable Material Model IR promotion.

This T-24 service deliberately separates a numerical Candidate's convergence from a modeler's
domain decision.  It never updates a Candidate, a Run, or an existing IR revision: a Selection
decision and the promoted IR are both new append-only revisions.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID, uuid4

from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
    Permission,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.modeling.application.calibration import (
    CalibrationCandidate,
    CalibrationRun,
    ReferenceCalibrationService,
)
from cmp.modules.modeling.application.service import (
    MaterialModelService,
    MaterialModelSnapshot,
    PromoteReferenceCalibrationCandidate,
    RevisionSnapshot,
)
from cmp.modules.modeling.domain.reference_calibration_candidate_selection import (
    REFERENCE_CANDIDATE_SELECTION_SCHEMA_ID,
    REFERENCE_CANDIDATE_SELECTION_SCHEMA_VERSION,
    CandidateSelectionConflict,
    InvalidCandidateSelection,
    ReferenceCalibrationCandidateSelectionContent,
)
from cmp.modules.modeling.domain.reference_linear_elastic_calibration import (
    CalibrationCandidateStatus,
    CalibrationRunStatus,
)
from cmp.modules.modeling.domain.reference_linear_elasticity import ReferenceCalibrationEvidence
from cmp.shared.application.revisions import (
    CreateRevisionedAggregate,
    ReviseAggregate,
    RevisionService,
    RevisionStore,
)
from cmp.shared.domain.revisions import TenantScope

CALIBRATION_CANDIDATE_SELECTION_AGGREGATE_TYPE = "modeling.calibration_candidate_selection"


@dataclass(frozen=True, slots=True)
class CalibrationCandidateSelectionSnapshot:
    id: UUID
    current: RevisionSnapshot[ReferenceCalibrationCandidateSelectionContent]


@dataclass(frozen=True, slots=True)
class CreateReferenceCalibrationCandidateSelection:
    classification: DataClassification
    selection_label: str
    calibration_run_id: UUID
    calibration_candidate_id: UUID
    selection_reason: str


@dataclass(frozen=True, slots=True)
class ReviseReferenceCalibrationCandidateSelection:
    expected_current_revision_id: UUID
    selection_label: str
    calibration_run_id: UUID
    calibration_candidate_id: UUID
    selection_reason: str


@dataclass(frozen=True, slots=True)
class PromoteSelectedReferenceCalibrationCandidate:
    selection_revision_id: UUID
    expected_material_model_revision_id: UUID
    change_reason: str


class CandidateSelectionRepository(Protocol):
    def selection_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[ReferenceCalibrationCandidateSelectionContent]: ...

    def get_selection(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        selection_id: UUID,
    ) -> CalibrationCandidateSelectionSnapshot: ...

    def get_selection_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        selection_id: UUID,
        selection_revision_id: UUID,
    ) -> RevisionSnapshot[ReferenceCalibrationCandidateSelectionContent]: ...

    def list_selections(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        limit: int,
    ) -> tuple[CalibrationCandidateSelectionSnapshot, ...]: ...


def _require(
    context: SecurityContext,
    decision: AuthorizationDecision,
    permission: Permission,
) -> None:
    if (
        decision.permission is not permission
        or decision.principal_id != context.principal.id
        or decision.organization_id != context.organization_id
        or decision.project_id != context.project_id
        or decision.request_id != context.request_id
        or decision.trace_id != context.trace_id
    ):
        raise CandidateSelectionConflict(
            "authorization decision does not match Candidate Selection request"
        )


class CandidateSelectionService:
    """Record human acceptance and promote only a non-stale selected Candidate."""

    def __init__(
        self,
        *,
        repository: CandidateSelectionRepository,
        calibrations: ReferenceCalibrationService,
        material_models: MaterialModelService,
        id_factory: Callable[[], UUID] = uuid4,
    ) -> None:
        self._repository = repository
        self._calibrations = calibrations
        self._material_models = material_models
        self._id_factory = id_factory

    def _id(self) -> UUID:
        value = self._id_factory()
        if value.int == 0:
            raise RuntimeError("candidate selection id_factory returned a zero UUID")
        return value

    def _candidate_and_run(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        *,
        calibration_run_id: UUID,
        calibration_candidate_id: UUID,
    ) -> tuple[CalibrationCandidate, CalibrationRun]:
        candidate = self._calibrations.get_candidate_for_selection(
            context,
            decision,
            calibration_candidate_id,
        )
        run = self._calibrations.get_run_for_selection(context, decision, calibration_run_id)
        if candidate.calibration_run_id != run.id:
            raise CandidateSelectionConflict(
                "Candidate does not belong to the selected Calibration Run"
            )
        if run.status is not CalibrationRunStatus.SUCCEEDED:
            raise CandidateSelectionConflict(
                "Candidate Selection requires a succeeded Calibration Run"
            )
        if candidate.status is not CalibrationCandidateStatus.CONVERGED:
            raise CandidateSelectionConflict(
                "numerical convergence is required before a human Candidate Selection"
            )
        return candidate, run

    def _content(
        self,
        command: CreateReferenceCalibrationCandidateSelection
        | ReviseReferenceCalibrationCandidateSelection,
        candidate: CalibrationCandidate,
    ) -> ReferenceCalibrationCandidateSelectionContent:
        return ReferenceCalibrationCandidateSelectionContent(
            selection_label=command.selection_label,
            calibration_run_id=command.calibration_run_id,
            calibration_candidate_id=command.calibration_candidate_id,
            candidate_sha256=candidate.candidate_sha256,
            selection_reason=command.selection_reason,
        )

    def create_selection(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CreateReferenceCalibrationCandidateSelection,
    ) -> CalibrationCandidateSelectionSnapshot:
        _require(context, decision, Permission.MODELING_WRITE)
        candidate, run = self._candidate_and_run(
            context,
            decision,
            calibration_run_id=command.calibration_run_id,
            calibration_candidate_id=command.calibration_candidate_id,
        )
        if run.classification is not command.classification:
            raise CandidateSelectionConflict(
                "Candidate Selection classification must equal the immutable Calibration Run"
            )
        content = self._content(command, candidate)
        aggregate_id = self._id()
        record = RevisionService(
            aggregate_type=CALIBRATION_CANDIDATE_SELECTION_AGGREGATE_TYPE,
            store=self._repository.selection_store(context, decision),
            id_factory=self._id_factory,
        ).create(
            CreateRevisionedAggregate(
                aggregate_id=aggregate_id,
                scope=TenantScope(
                    context.organization_id,
                    context.project_id,
                    command.classification.value,
                ),
                schema_id=REFERENCE_CANDIDATE_SELECTION_SCHEMA_ID,
                schema_version=REFERENCE_CANDIDATE_SELECTION_SCHEMA_VERSION,
                content=content,
                created_by=context.principal.id,
                change_reason=content.selection_reason,
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        return CalibrationCandidateSelectionSnapshot(
            id=aggregate_id,
            current=RevisionSnapshot(record, content),
        )

    def revise_selection(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        selection_id: UUID,
        command: ReviseReferenceCalibrationCandidateSelection,
    ) -> CalibrationCandidateSelectionSnapshot:
        _require(context, decision, Permission.MODELING_WRITE)
        current = self._repository.get_selection(
            context=context, decision=decision, selection_id=selection_id
        )
        if current.current.content.selection_label != command.selection_label:
            raise CandidateSelectionConflict("Candidate Selection label is a stable identity")
        if current.current.content.calibration_run_id != command.calibration_run_id:
            raise CandidateSelectionConflict(
                "Candidate Selection identity is fixed to one Calibration Run"
            )
        candidate, run = self._candidate_and_run(
            context,
            decision,
            calibration_run_id=command.calibration_run_id,
            calibration_candidate_id=command.calibration_candidate_id,
        )
        if run.classification.value != current.current.record.scope.classification:
            raise CandidateSelectionConflict("Candidate Selection revision crosses classification")
        content = self._content(command, candidate)
        record = RevisionService(
            aggregate_type=CALIBRATION_CANDIDATE_SELECTION_AGGREGATE_TYPE,
            store=self._repository.selection_store(context, decision),
            id_factory=self._id_factory,
        ).revise(
            ReviseAggregate(
                aggregate_id=selection_id,
                scope=current.current.record.scope,
                expected_current_revision_id=command.expected_current_revision_id,
                based_on_revision_id=command.expected_current_revision_id,
                schema_id=REFERENCE_CANDIDATE_SELECTION_SCHEMA_ID,
                schema_version=REFERENCE_CANDIDATE_SELECTION_SCHEMA_VERSION,
                content=content,
                created_by=context.principal.id,
                change_reason=content.selection_reason,
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        return CalibrationCandidateSelectionSnapshot(
            id=selection_id,
            current=RevisionSnapshot(record, content),
        )

    def get_selection(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        selection_id: UUID,
    ) -> CalibrationCandidateSelectionSnapshot:
        _require(context, decision, Permission.MODELING_READ)
        return self._repository.get_selection(
            context=context, decision=decision, selection_id=selection_id
        )

    def list_selections(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        *,
        limit: int,
    ) -> tuple[CalibrationCandidateSelectionSnapshot, ...]:
        _require(context, decision, Permission.MODELING_READ)
        if not 1 <= limit <= 200:
            raise InvalidCandidateSelection("limit must be between 1 and 200")
        return self._repository.list_selections(context=context, decision=decision, limit=limit)

    def promote_selected_candidate(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        selection_id: UUID,
        command: PromoteSelectedReferenceCalibrationCandidate,
    ) -> MaterialModelSnapshot:
        _require(context, decision, Permission.MODELING_WRITE)
        current_selection = self._repository.get_selection(
            context=context,
            decision=decision,
            selection_id=selection_id,
        )
        if current_selection.current.record.revision_id != command.selection_revision_id:
            raise CandidateSelectionConflict(
                "Promotion requires the current Candidate Selection revision"
            )
        selection = self._repository.get_selection_revision(
            context=context,
            decision=decision,
            selection_id=selection_id,
            selection_revision_id=command.selection_revision_id,
        )
        candidate, run = self._candidate_and_run(
            context,
            decision,
            calibration_run_id=selection.content.calibration_run_id,
            calibration_candidate_id=selection.content.calibration_candidate_id,
        )
        if candidate.candidate_sha256 != selection.content.candidate_sha256:
            raise CandidateSelectionConflict(
                "Candidate Selection digest differs from the immutable Calibration Candidate"
            )
        if run.material_model_revision_id != command.expected_material_model_revision_id:
            raise CandidateSelectionConflict(
                "Promotion must name the exact IR revision evaluated by the Calibration Run"
            )
        return self._material_models.promote_reference_calibration_candidate(
            context,
            decision,
            run.material_model_id,
            PromoteReferenceCalibrationCandidate(
                expected_current_revision_id=command.expected_material_model_revision_id,
                youngs_modulus_pa=candidate.youngs_modulus_pa,
                calibration_evidence=ReferenceCalibrationEvidence(
                    calibration_selection_id=selection_id,
                    calibration_selection_revision_id=command.selection_revision_id,
                    calibration_run_id=run.id,
                    calibration_candidate_id=candidate.id,
                    calibration_candidate_sha256=candidate.candidate_sha256,
                    diagnostics_artifact_id=candidate.diagnostics_artifact_id,
                    diagnostics_sha256=candidate.diagnostics_sha256,
                ),
                change_reason=command.change_reason,
            ),
        )

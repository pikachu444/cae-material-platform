"""Human Prony Candidate Selection and append-only linear-Prony IR promotion."""

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
from cmp.modules.modeling.application.linear_viscoelasticity import (
    LinearViscoelasticModelService,
    LinearViscoelasticModelSnapshot,
    PromoteReferencePronyCandidate,
)
from cmp.modules.modeling.application.prony_calibration import (
    ReferencePronyCalibrationService,
)
from cmp.modules.modeling.application.service import RevisionSnapshot
from cmp.modules.modeling.domain.reference_linear_viscoelasticity import (
    PronyTerm,
    ReferencePronyPromotionEvidence,
)
from cmp.modules.modeling.domain.reference_prony_candidate_selection import (
    REFERENCE_PRONY_SELECTION_SCHEMA_ID,
    REFERENCE_PRONY_SELECTION_SCHEMA_VERSION,
    PronyCandidateSelectionConflict,
    ReferencePronyCandidateSelectionContent,
)
from cmp.modules.processing.domain.reference_tensile_crop import ProcessingRunStatus
from cmp.shared.application.revisions import (
    CreateRevisionedAggregate,
    RevisionService,
    RevisionStore,
)
from cmp.shared.domain.revisions import TenantScope

PRONY_CANDIDATE_SELECTION_AGGREGATE_TYPE = "modeling.prony_candidate_selection"


@dataclass(frozen=True, slots=True)
class PronyCandidateSelectionSnapshot:
    id: UUID
    current: RevisionSnapshot[ReferencePronyCandidateSelectionContent]


@dataclass(frozen=True, slots=True)
class CreatePronyCandidateSelection:
    classification: DataClassification
    selection_label: str
    calibration_run_id: UUID
    calibration_candidate_id: UUID
    selection_reason: str


@dataclass(frozen=True, slots=True)
class PromoteSelectedPronyCandidate:
    selection_revision_id: UUID
    change_reason: str


class PronyCandidateSelectionRepository(Protocol):
    def selection_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[ReferencePronyCandidateSelectionContent]: ...

    def get_selection(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        selection_id: UUID,
    ) -> PronyCandidateSelectionSnapshot: ...

    def get_selection_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        selection_id: UUID,
        selection_revision_id: UUID,
    ) -> RevisionSnapshot[ReferencePronyCandidateSelectionContent]: ...


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
        raise PronyCandidateSelectionConflict(
            "authorization decision does not match Prony selection request"
        )


def _reason(value: str) -> str:
    if not value or value != value.strip() or len(value) > 2_000 or "\x00" in value:
        raise ValueError("reason must be trimmed and contain 1..2000 characters")
    return value


class PronyCandidatePromotionService:
    def __init__(
        self,
        *,
        selections: PronyCandidateSelectionRepository,
        calibrations: ReferencePronyCalibrationService,
        models: LinearViscoelasticModelService,
        id_factory: Callable[[], UUID] = uuid4,
    ) -> None:
        self._selections = selections
        self._calibrations = calibrations
        self._models = models
        self._id_factory = id_factory

    def create_selection(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CreatePronyCandidateSelection,
    ) -> PronyCandidateSelectionSnapshot:
        _require(context, decision, Permission.MODELING_WRITE)
        run = self._calibrations.get_run_for_promotion(
            context, decision, command.calibration_run_id
        )
        candidate = self._calibrations.get_candidate_for_promotion(
            context, decision, command.calibration_candidate_id
        )
        if run.status is not ProcessingRunStatus.SUCCEEDED:
            raise PronyCandidateSelectionConflict("Selection requires a succeeded Run")
        if candidate.calibration_run_id != run.id:
            raise PronyCandidateSelectionConflict("Candidate does not belong to the selected Run")
        if candidate.value.status != "converged":
            raise PronyCandidateSelectionConflict("only a converged Candidate can be selected")
        if run.classification is not command.classification:
            raise PronyCandidateSelectionConflict("Selection classification must equal Run scope")
        content = ReferencePronyCandidateSelectionContent(
            selection_label=command.selection_label,
            prony_calibration_run_id=run.id,
            prony_calibration_candidate_id=candidate.id,
            candidate_sha256=candidate.value.candidate_sha256,
            baseline_model_id=run.baseline_model_id,
            baseline_model_revision_id=run.baseline_model_revision_id,
            selection_reason=_reason(command.selection_reason),
        )
        selection_id = self._id_factory()
        if selection_id.int == 0:
            raise RuntimeError("Prony selection id_factory returned a zero UUID")
        record = RevisionService(
            aggregate_type=PRONY_CANDIDATE_SELECTION_AGGREGATE_TYPE,
            store=self._selections.selection_store(context, decision),
        ).create(
            CreateRevisionedAggregate(
                aggregate_id=selection_id,
                scope=TenantScope(
                    context.organization_id,
                    context.project_id,
                    command.classification.value,
                ),
                schema_id=REFERENCE_PRONY_SELECTION_SCHEMA_ID,
                schema_version=REFERENCE_PRONY_SELECTION_SCHEMA_VERSION,
                content=content,
                created_by=context.principal.id,
                change_reason=content.selection_reason,
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        return PronyCandidateSelectionSnapshot(
            selection_id, RevisionSnapshot(record, content)
        )

    def get_selection(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        selection_id: UUID,
    ) -> PronyCandidateSelectionSnapshot:
        _require(context, decision, Permission.MODELING_READ)
        return self._selections.get_selection(
            context=context, decision=decision, selection_id=selection_id
        )

    def promote(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        selection_id: UUID,
        command: PromoteSelectedPronyCandidate,
    ) -> LinearViscoelasticModelSnapshot:
        _require(context, decision, Permission.MODELING_WRITE)
        selection = self._selections.get_selection_revision(
            context=context,
            decision=decision,
            selection_id=selection_id,
            selection_revision_id=command.selection_revision_id,
        )
        content = selection.content
        run = self._calibrations.get_run_for_promotion(
            context, decision, content.prony_calibration_run_id
        )
        candidate = self._calibrations.get_candidate_for_promotion(
            context, decision, content.prony_calibration_candidate_id
        )
        if (
            run.status is not ProcessingRunStatus.SUCCEEDED
            or candidate.value.status != "converged"
            or candidate.calibration_run_id != run.id
            or candidate.value.candidate_sha256 != content.candidate_sha256
            or run.baseline_model_id != content.baseline_model_id
            or run.baseline_model_revision_id != content.baseline_model_revision_id
        ):
            raise PronyCandidateSelectionConflict(
                "Selection no longer resolves to its exact calibration lineage"
            )
        value = candidate.value
        evidence = ReferencePronyPromotionEvidence(
            selection_id=selection_id,
            selection_revision_id=selection.record.revision_id,
            calibration_run_id=run.id,
            calibration_candidate_id=candidate.id,
            candidate_sha256=value.candidate_sha256,
            diagnostics_artifact_id=candidate.diagnostics_artifact_id,
            diagnostics_sha256=candidate.diagnostics_sha256,
        )
        return self._models.promote_candidate(
            context,
            decision,
            PromoteReferencePronyCandidate(
                material_model_id=content.baseline_model_id,
                baseline_model_revision_id=content.baseline_model_revision_id,
                terms=(
                    PronyTerm(value.fast_g_ratio, 0.0, value.fast_relaxation_time_s),
                    PronyTerm(value.slow_g_ratio, 0.0, value.slow_relaxation_time_s),
                ),
                evidence=evidence,
                change_reason=_reason(command.change_reason),
            ),
        )

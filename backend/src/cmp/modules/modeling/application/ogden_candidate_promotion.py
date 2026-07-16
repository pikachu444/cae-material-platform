"""Human Ogden Candidate Selection and repeated append-only IR promotion."""

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
from cmp.modules.modeling.application.ogden_calibration import (
    ReferenceOgdenCalibrationService,
)
from cmp.modules.modeling.application.ogden_prony import (
    OgdenPronyModelService,
    OgdenPronyModelSnapshot,
    PromoteReferenceOgdenCandidate,
)
from cmp.modules.modeling.application.service import RevisionSnapshot
from cmp.modules.modeling.domain.reference_ogden_candidate_selection import (
    REFERENCE_OGDEN_SELECTION_SCHEMA_ID,
    REFERENCE_OGDEN_SELECTION_SCHEMA_VERSION,
    OgdenCandidateSelectionConflict,
    ReferenceOgdenCandidateSelectionContent,
)
from cmp.modules.modeling.domain.reference_ogden_prony import (
    ReferenceOgdenPromotionEvidence,
    ReferenceOgdenTerm,
)
from cmp.modules.processing.domain.reference_tensile_crop import ProcessingRunStatus
from cmp.shared.application.revisions import (
    CreateRevisionedAggregate,
    RevisionService,
    RevisionStore,
)
from cmp.shared.domain.revisions import TenantScope

OGDEN_CANDIDATE_SELECTION_AGGREGATE_TYPE = "modeling.ogden_candidate_selection"


@dataclass(frozen=True, slots=True)
class OgdenCandidateSelectionSnapshot:
    id: UUID
    current: RevisionSnapshot[ReferenceOgdenCandidateSelectionContent]


@dataclass(frozen=True, slots=True)
class CreateOgdenCandidateSelection:
    classification: DataClassification
    selection_label: str
    calibration_run_id: UUID
    calibration_candidate_id: UUID
    selection_reason: str


@dataclass(frozen=True, slots=True)
class PromoteSelectedOgdenCandidate:
    selection_revision_id: UUID
    expected_current_model_revision_id: UUID
    change_reason: str


class OgdenCandidateSelectionRepository(Protocol):
    def selection_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[ReferenceOgdenCandidateSelectionContent]: ...

    def get_selection(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        selection_id: UUID,
    ) -> OgdenCandidateSelectionSnapshot: ...

    def get_selection_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        selection_id: UUID,
        selection_revision_id: UUID,
    ) -> RevisionSnapshot[ReferenceOgdenCandidateSelectionContent]: ...


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
        raise OgdenCandidateSelectionConflict(
            "authorization decision does not match Ogden selection request"
        )


def _reason(value: str) -> str:
    if not value or value != value.strip() or len(value) > 2_000 or "\x00" in value:
        raise ValueError("reason must be trimmed and contain 1..2000 characters")
    return value


class OgdenCandidatePromotionService:
    def __init__(
        self,
        *,
        selections: OgdenCandidateSelectionRepository,
        calibrations: ReferenceOgdenCalibrationService,
        models: OgdenPronyModelService,
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
        command: CreateOgdenCandidateSelection,
    ) -> OgdenCandidateSelectionSnapshot:
        _require(context, decision, Permission.MODELING_WRITE)
        run = self._calibrations.get_run_for_promotion(
            context, decision, command.calibration_run_id
        )
        candidate = self._calibrations.get_candidate_for_promotion(
            context, decision, command.calibration_candidate_id
        )
        if run.status is not ProcessingRunStatus.SUCCEEDED:
            raise OgdenCandidateSelectionConflict("Selection requires a succeeded Run")
        if candidate.calibration_run_id != run.id:
            raise OgdenCandidateSelectionConflict(
                "Candidate does not belong to the selected Run"
            )
        if candidate.value.status != "converged":
            raise OgdenCandidateSelectionConflict(
                "only a converged Candidate can be selected"
            )
        if run.classification is not command.classification:
            raise OgdenCandidateSelectionConflict(
                "Selection classification must equal Run scope"
            )
        content = ReferenceOgdenCandidateSelectionContent(
            selection_label=command.selection_label,
            ogden_calibration_run_id=run.id,
            ogden_calibration_candidate_id=candidate.id,
            candidate_sha256=candidate.value.candidate_sha256,
            diagnostics_artifact_id=candidate.diagnostics_artifact_id,
            diagnostics_sha256=candidate.diagnostics_sha256,
            baseline_model_id=run.baseline_model_id,
            baseline_model_revision_id=run.baseline_model_revision_id,
            selection_reason=_reason(command.selection_reason),
        )
        selection_id = self._id_factory()
        if selection_id.int == 0:
            raise RuntimeError("Ogden selection id_factory returned a zero UUID")
        record = RevisionService(
            aggregate_type=OGDEN_CANDIDATE_SELECTION_AGGREGATE_TYPE,
            store=self._selections.selection_store(context, decision),
        ).create(
            CreateRevisionedAggregate(
                aggregate_id=selection_id,
                scope=TenantScope(
                    context.organization_id,
                    context.project_id,
                    command.classification.value,
                ),
                schema_id=REFERENCE_OGDEN_SELECTION_SCHEMA_ID,
                schema_version=REFERENCE_OGDEN_SELECTION_SCHEMA_VERSION,
                content=content,
                created_by=context.principal.id,
                change_reason=content.selection_reason,
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        return OgdenCandidateSelectionSnapshot(
            selection_id, RevisionSnapshot(record, content)
        )

    def get_selection(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        selection_id: UUID,
    ) -> OgdenCandidateSelectionSnapshot:
        _require(context, decision, Permission.MODELING_READ)
        return self._selections.get_selection(
            context=context, decision=decision, selection_id=selection_id
        )

    def get_current_model_for_promotion(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        selection_id: UUID,
        selection_revision_id: UUID,
    ) -> OgdenPronyModelSnapshot:
        _require(context, decision, Permission.MODELING_WRITE)
        selection = self._selections.get_selection_revision(
            context=context,
            decision=decision,
            selection_id=selection_id,
            selection_revision_id=selection_revision_id,
        )
        return self._models.get_model_for_write(
            context, decision, selection.content.baseline_model_id
        )

    def promote(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        selection_id: UUID,
        command: PromoteSelectedOgdenCandidate,
    ) -> OgdenPronyModelSnapshot:
        _require(context, decision, Permission.MODELING_WRITE)
        selection = self._selections.get_selection_revision(
            context=context,
            decision=decision,
            selection_id=selection_id,
            selection_revision_id=command.selection_revision_id,
        )
        content = selection.content
        run = self._calibrations.get_run_for_promotion(
            context, decision, content.ogden_calibration_run_id
        )
        candidate = self._calibrations.get_candidate_for_promotion(
            context, decision, content.ogden_calibration_candidate_id
        )
        if (
            run.status is not ProcessingRunStatus.SUCCEEDED
            or candidate.value.status != "converged"
            or candidate.calibration_run_id != run.id
            or candidate.value.candidate_sha256 != content.candidate_sha256
            or candidate.diagnostics_artifact_id != content.diagnostics_artifact_id
            or candidate.diagnostics_sha256 != content.diagnostics_sha256
            or run.baseline_model_id != content.baseline_model_id
            or run.baseline_model_revision_id != content.baseline_model_revision_id
            or command.expected_current_model_revision_id
            != content.baseline_model_revision_id
        ):
            raise OgdenCandidateSelectionConflict(
                "Selection no longer resolves to its exact calibration lineage and current head"
            )
        evidence = ReferenceOgdenPromotionEvidence(
            selection_id=selection_id,
            selection_revision_id=selection.record.revision_id,
            calibration_run_id=run.id,
            calibration_candidate_id=candidate.id,
            candidate_sha256=candidate.value.candidate_sha256,
            diagnostics_artifact_id=candidate.diagnostics_artifact_id,
            diagnostics_sha256=candidate.diagnostics_sha256,
            promoted_from_model_revision_id=command.expected_current_model_revision_id,
        )
        return self._models.promote_candidate(
            context,
            decision,
            PromoteReferenceOgdenCandidate(
                material_model_id=content.baseline_model_id,
                expected_current_revision_id=command.expected_current_model_revision_id,
                ogden_term=ReferenceOgdenTerm(
                    candidate.value.mu_pa, candidate.value.alpha
                ),
                evidence=evidence,
                change_reason=_reason(command.change_reason),
            ),
        )

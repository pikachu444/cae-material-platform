from __future__ import annotations

from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import cast
from uuid import UUID, uuid4

import pytest
from cmp.modules.identity_access.application.authorization import database_permissions_for
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
    Permission,
    Role,
)
from cmp.modules.identity_access.domain.security import (
    Principal,
    PrincipalType,
    SecurityContext,
)
from cmp.modules.modeling.application.calibration import (
    CalibrationCandidate,
    CalibrationRun,
    ReferenceCalibrationService,
)
from cmp.modules.modeling.application.candidate_selection import (
    CALIBRATION_CANDIDATE_SELECTION_AGGREGATE_TYPE,
    CalibrationCandidateSelectionSnapshot,
    CandidateSelectionRepository,
    CandidateSelectionService,
    CreateReferenceCalibrationCandidateSelection,
    PromoteSelectedReferenceCalibrationCandidate,
    ReviseReferenceCalibrationCandidateSelection,
)
from cmp.modules.modeling.application.service import (
    MATERIAL_MODEL_AGGREGATE_TYPE,
    MaterialModelService,
    MaterialModelSnapshot,
    PromoteReferenceCalibrationCandidate,
    RevisionSnapshot,
)
from cmp.modules.modeling.domain.reference_calibration_candidate_selection import (
    CandidateSelectionConflict,
    ReferenceCalibrationCandidateSelectionContent,
    reference_calibration_candidate_selection_canonical,
)
from cmp.modules.modeling.domain.reference_linear_elastic_calibration import (
    CalibrationCandidateStatus,
    CalibrationRunStatus,
)
from cmp.modules.modeling.domain.reference_linear_elasticity import ReferenceLinearElasticContent
from cmp.shared.application.revisions import RevisionStore, RevisionTransaction
from cmp.shared.domain.revisions import (
    AggregateAlreadyExists,
    AggregateNotFound,
    RevisionConflict,
    RevisionCreated,
    RevisionDraft,
    RevisionRecord,
    TenantScope,
)

NOW = datetime(2026, 7, 20, 9, 0, tzinfo=UTC)
ORG = UUID("fb000000-0000-4000-8000-000000000001")
PROJECT = UUID("fb000000-0000-4000-8000-000000000002")
ACTOR = UUID("fb000000-0000-4000-8000-000000000003")
MODEL = UUID("fb000000-0000-4000-8000-000000000004")
MODEL_REVISION = UUID("fb000000-0000-4000-8000-000000000005")
RUN = UUID("fb000000-0000-4000-8000-000000000006")
CANDIDATE_ONE = UUID("fb000000-0000-4000-8000-000000000007")
CANDIDATE_TWO = UUID("fb000000-0000-4000-8000-000000000008")
ATTEMPT_ONE = UUID("fb000000-0000-4000-8000-000000000009")
ATTEMPT_TWO = UUID("fb000000-0000-4000-8000-00000000000a")
DIAGNOSTICS_ONE = UUID("fb000000-0000-4000-8000-00000000000b")
DIAGNOSTICS_TWO = UUID("fb000000-0000-4000-8000-00000000000c")
SELECTION = UUID("fb000000-0000-4000-8000-00000000000d")
SELECTION_REVISION_ONE = UUID("fb000000-0000-4000-8000-00000000000e")
SELECTION_REVISION_TWO = UUID("fb000000-0000-4000-8000-00000000000f")
PROMOTED_REVISION = UUID("fb000000-0000-4000-8000-000000000010")
TRACE = "00-000000000000000000000000000000fb-00000000000000fb-01"


def _context() -> SecurityContext:
    return SecurityContext(
        principal=Principal(ACTOR, PrincipalType.USER, "Material modeler", True),
        organization_id=ORG,
        project_id=PROJECT,
        issuer="https://test-idp.invalid",
        subject=str(ACTOR),
        token_id=str(uuid4()),
        groups=(),
        scopes=("openid",),
        request_id=uuid4(),
        trace_id=TRACE,
        authenticated_at=NOW,
    )


CONTEXT = _context()
WRITE = AuthorizationDecision(
    principal_id=ACTOR,
    organization_id=ORG,
    project_id=PROJECT,
    permission=Permission.MODELING_WRITE,
    roles=(Role.MATERIAL_MODELER,),
    database_permissions=database_permissions_for(Permission.MODELING_WRITE),
    max_classification=DataClassification.INTERNAL,
    allow_export_controlled=False,
    request_id=CONTEXT.request_id,
    trace_id=TRACE,
    decided_at=NOW,
)


def _record(
    revision_id: UUID,
    aggregate_id: UUID,
    aggregate_type: str,
    *,
    revision_no: int = 1,
    based_on_revision_id: UUID | None = None,
) -> RevisionRecord:
    return RevisionRecord(
        revision_id=revision_id,
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        scope=TenantScope(ORG, PROJECT, DataClassification.INTERNAL.value),
        revision_no=revision_no,
        based_on_revision_id=based_on_revision_id,
        schema_id=f"urn:cmp:test:{aggregate_type}:1.0.0",
        schema_version="1.0.0",
        content_hash="b" * 64,
        created_at=NOW,
        created_by=ACTOR,
        change_reason="reference candidate selection test",
        request_id=CONTEXT.request_id,
        trace_id=TRACE,
    )


@dataclass
class _StoreState:
    heads: dict[UUID, UUID]
    records: dict[UUID, RevisionRecord]
    contents: dict[UUID, ReferenceCalibrationCandidateSelectionContent]
    events: list[RevisionCreated]


class _SelectionTransaction(RevisionTransaction[ReferenceCalibrationCandidateSelectionContent]):
    def __init__(self, state: _StoreState) -> None:
        self._state = state

    @staticmethod
    def _record(
        draft: RevisionDraft[ReferenceCalibrationCandidateSelectionContent],
        revision_no: int,
        based_on_revision_id: UUID | None,
    ) -> RevisionRecord:
        return RevisionRecord(
            revision_id=draft.revision_id,
            aggregate_type=draft.aggregate_type,
            aggregate_id=draft.aggregate_id,
            scope=draft.scope,
            revision_no=revision_no,
            based_on_revision_id=based_on_revision_id,
            schema_id=draft.schema_id,
            schema_version=draft.schema_version,
            content_hash=draft.content_hash,
            created_at=draft.created_at,
            created_by=draft.created_by,
            change_reason=draft.change_reason,
            request_id=draft.request_id,
            trace_id=draft.trace_id,
        )

    def create(
        self, draft: RevisionDraft[ReferenceCalibrationCandidateSelectionContent]
    ) -> RevisionRecord:
        if draft.aggregate_id in self._state.heads:
            raise AggregateAlreadyExists(str(draft.aggregate_id))
        record = self._record(draft, 1, None)
        self._state.heads[record.aggregate_id] = record.revision_id
        self._state.records[record.revision_id] = record
        self._state.contents[record.revision_id] = draft.content
        return record

    def revise(
        self,
        draft: RevisionDraft[ReferenceCalibrationCandidateSelectionContent],
        expected_current_revision_id: UUID,
    ) -> RevisionRecord:
        current_id = self._state.heads.get(draft.aggregate_id)
        if current_id is None:
            raise AggregateNotFound(str(draft.aggregate_id))
        if current_id != expected_current_revision_id:
            raise RevisionConflict(
                expected_current_revision_id, self._state.records[current_id].ref
            )
        current = self._state.records[current_id]
        record = self._record(draft, current.revision_no + 1, current_id)
        self._state.heads[record.aggregate_id] = record.revision_id
        self._state.records[record.revision_id] = record
        self._state.contents[record.revision_id] = draft.content
        return record

    def stage(self, event: RevisionCreated) -> None:
        self._state.events.append(event)


class _SelectionStore(RevisionStore[ReferenceCalibrationCandidateSelectionContent]):
    def __init__(self) -> None:
        self.state = _StoreState({}, {}, {}, [])

    def canonical_content(self, content: ReferenceCalibrationCandidateSelectionContent) -> object:
        return reference_calibration_candidate_selection_canonical(content)

    def transaction(
        self,
    ) -> AbstractContextManager[RevisionTransaction[ReferenceCalibrationCandidateSelectionContent]]:
        return self._transaction()

    @contextmanager
    def _transaction(
        self,
    ) -> Iterator[RevisionTransaction[ReferenceCalibrationCandidateSelectionContent]]:
        yield _SelectionTransaction(self.state)


class _Repository:
    def __init__(self) -> None:
        self.store = _SelectionStore()

    def selection_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[ReferenceCalibrationCandidateSelectionContent]:
        assert context is CONTEXT
        assert decision is WRITE
        return self.store

    def get_selection(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        selection_id: UUID,
    ) -> CalibrationCandidateSelectionSnapshot:
        assert context is CONTEXT
        assert decision is WRITE
        revision_id = self.store.state.heads.get(selection_id)
        if revision_id is None:
            raise AggregateNotFound(str(selection_id))
        return CalibrationCandidateSelectionSnapshot(
            selection_id,
            RevisionSnapshot(
                self.store.state.records[revision_id], self.store.state.contents[revision_id]
            ),
        )

    def get_selection_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        selection_id: UUID,
        selection_revision_id: UUID,
    ) -> RevisionSnapshot[ReferenceCalibrationCandidateSelectionContent]:
        assert context is CONTEXT
        assert decision is WRITE
        record = self.store.state.records.get(selection_revision_id)
        if record is None or record.aggregate_id != selection_id:
            raise AggregateNotFound(str(selection_revision_id))
        return RevisionSnapshot(record, self.store.state.contents[selection_revision_id])

    def list_selections(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        limit: int,
    ) -> tuple[CalibrationCandidateSelectionSnapshot, ...]:
        assert context is CONTEXT
        assert decision is WRITE
        values = tuple(
            self.get_selection(context=context, decision=decision, selection_id=selection_id)
            for selection_id in self.store.state.heads
        )
        return values[:limit]


def _run() -> CalibrationRun:
    return CalibrationRun(
        id=RUN,
        classification=DataClassification.INTERNAL,
        plan_id=uuid4(),
        plan_revision_id=uuid4(),
        selection_id=uuid4(),
        selection_revision_id=uuid4(),
        dataset_id=uuid4(),
        dataset_revision_id=uuid4(),
        material_model_id=MODEL,
        material_model_revision_id=MODEL_REVISION,
        execution_mode="reference_inline",
        reproducibility_level="R3",
        environment_digest="a" * 64,
        status=CalibrationRunStatus.SUCCEEDED,
        attempt_count=2,
        candidate_count=2,
        failure_code=None,
        change_reason="completed reference fit",
        started_at=NOW,
        ended_at=NOW,
        created_by=ACTOR,
        request_id=CONTEXT.request_id,
        trace_id=TRACE,
    )


def _candidate(
    candidate_id: UUID,
    attempt_id: UUID,
    diagnostics_id: UUID,
    *,
    youngs_modulus_pa: float,
    status: CalibrationCandidateStatus = CalibrationCandidateStatus.CONVERGED,
) -> CalibrationCandidate:
    return CalibrationCandidate(
        id=candidate_id,
        calibration_run_id=RUN,
        calibration_attempt_id=attempt_id,
        attempt_ordinal=1 if candidate_id == CANDIDATE_ONE else 2,
        status=status,
        candidate_sha256=("c" if candidate_id == CANDIDATE_ONE else "d") * 64,
        youngs_modulus_pa=youngs_modulus_pa,
        objective_total=0.0,
        residual_root_mean_square_pa=0.0,
        residual_mean_pa=0.0,
        bound_sticking=False,
        convergence_reason="reference_result",
        identifiability_status="not_assessed_reference_one_parameter",
        uncertainty_status="not_estimated_reference",
        diagnostics_artifact_id=diagnostics_id,
        diagnostics_sha256=("e" if candidate_id == CANDIDATE_ONE else "f") * 64,
        diagnostics_point_count=3,
        created_at=NOW,
        created_by=ACTOR,
    )


class _Calibrations:
    def __init__(self) -> None:
        self.run = _run()
        self.candidates = {
            CANDIDATE_ONE: _candidate(
                CANDIDATE_ONE,
                ATTEMPT_ONE,
                DIAGNOSTICS_ONE,
                youngs_modulus_pa=205_000_000_000.0,
            ),
            CANDIDATE_TWO: _candidate(
                CANDIDATE_TWO,
                ATTEMPT_TWO,
                DIAGNOSTICS_TWO,
                youngs_modulus_pa=207_000_000_000.0,
            ),
        }

    def get_run_for_selection(
        self, context: SecurityContext, decision: AuthorizationDecision, run_id: UUID
    ) -> CalibrationRun:
        assert context is CONTEXT
        assert decision is WRITE
        assert run_id == RUN
        return self.run

    def get_candidate_for_selection(
        self, context: SecurityContext, decision: AuthorizationDecision, candidate_id: UUID
    ) -> CalibrationCandidate:
        assert context is CONTEXT
        assert decision is WRITE
        return self.candidates[candidate_id]


def _model_content() -> ReferenceLinearElasticContent:
    return ReferenceLinearElasticContent(
        material_id=uuid4(),
        material_revision_id=uuid4(),
        material_state_id=uuid4(),
        material_state_revision_id=uuid4(),
        property_set_id=uuid4(),
        property_set_revision_id=uuid4(),
        density_kg_per_m3=7850.0,
        youngs_modulus_pa=210_000_000_000.0,
        poisson_ratio=0.3,
    )


class _Models:
    def __init__(self) -> None:
        self.current = RevisionSnapshot(
            _record(MODEL_REVISION, MODEL, MATERIAL_MODEL_AGGREGATE_TYPE), _model_content()
        )
        self.commands: list[PromoteReferenceCalibrationCandidate] = []

    def promote_reference_calibration_candidate(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_model_id: UUID,
        command: PromoteReferenceCalibrationCandidate,
    ) -> MaterialModelSnapshot:
        assert context is CONTEXT
        assert decision is WRITE
        assert material_model_id == MODEL
        self.commands.append(command)
        promoted_content = replace(
            self.current.content,
            youngs_modulus_pa=command.youngs_modulus_pa,
            calibration_evidence=command.calibration_evidence,
        )
        promoted = RevisionSnapshot(
            _record(
                PROMOTED_REVISION,
                MODEL,
                MATERIAL_MODEL_AGGREGATE_TYPE,
                revision_no=2,
                based_on_revision_id=MODEL_REVISION,
            ),
            promoted_content,
        )
        return MaterialModelSnapshot(MODEL, promoted_content.material_state_id, promoted)


def _service() -> tuple[CandidateSelectionService, _Repository, _Calibrations, _Models]:
    identifiers = iter((SELECTION, SELECTION_REVISION_ONE, SELECTION_REVISION_TWO))
    repository = _Repository()
    calibrations = _Calibrations()
    models = _Models()
    return (
        CandidateSelectionService(
            repository=cast(CandidateSelectionRepository, repository),
            calibrations=cast(ReferenceCalibrationService, calibrations),
            material_models=cast(MaterialModelService, models),
            id_factory=lambda: next(identifiers),
        ),
        repository,
        calibrations,
        models,
    )


def _create_command(
    candidate_id: UUID = CANDIDATE_ONE,
) -> CreateReferenceCalibrationCandidateSelection:
    return CreateReferenceCalibrationCandidateSelection(
        classification=DataClassification.INTERNAL,
        selection_label="Elastic candidate accepted after human review",
        calibration_run_id=RUN,
        calibration_candidate_id=candidate_id,
        selection_reason="Human review accepts the converged reference candidate for IR promotion.",
    )


def test_selection_revisions_preserve_human_decision_history_and_stable_run_identity() -> None:
    service, repository, _calibrations, _models = _service()

    created = service.create_selection(CONTEXT, WRITE, _create_command())
    revised = service.revise_selection(
        CONTEXT,
        WRITE,
        SELECTION,
        ReviseReferenceCalibrationCandidateSelection(
            expected_current_revision_id=created.current.record.revision_id,
            selection_label="Elastic candidate accepted after human review",
            calibration_run_id=RUN,
            calibration_candidate_id=CANDIDATE_TWO,
            selection_reason=(
                "Human review changes the accepted converged candidate without mutation."
            ),
        ),
    )

    assert created.current.record.revision_no == 1
    assert revised.current.record.revision_no == 2
    assert revised.current.content.calibration_candidate_id == CANDIDATE_TWO
    assert (
        repository.store.state.contents[created.current.record.revision_id].calibration_candidate_id
        == CANDIDATE_ONE
    )
    assert revised.current.content.calibration_run_id == RUN
    assert [event.revision.aggregate_type for event in repository.store.state.events] == [
        CALIBRATION_CANDIDATE_SELECTION_AGGREGATE_TYPE,
        CALIBRATION_CANDIDATE_SELECTION_AGGREGATE_TYPE,
    ]


def test_selection_rejects_nonconverged_candidate() -> None:
    service, _repository, calibrations, _models = _service()
    calibrations.candidates[CANDIDATE_ONE] = replace(
        calibrations.candidates[CANDIDATE_ONE],
        status=CalibrationCandidateStatus.NONCONVERGED,
    )

    with pytest.raises(CandidateSelectionConflict, match="numerical convergence"):
        service.create_selection(CONTEXT, WRITE, _create_command())


def test_promotion_uses_current_selection_revision_and_typed_candidate_evidence() -> None:
    service, _repository, _calibrations, models = _service()
    selection = service.create_selection(CONTEXT, WRITE, _create_command())

    promoted = service.promote_selected_candidate(
        CONTEXT,
        WRITE,
        SELECTION,
        PromoteSelectedReferenceCalibrationCandidate(
            selection_revision_id=selection.current.record.revision_id,
            expected_material_model_revision_id=MODEL_REVISION,
            change_reason="Promote accepted candidate without rewriting the evaluated IR revision.",
        ),
    )

    assert promoted.current.record.revision_no == 2
    assert promoted.current.content.youngs_modulus_pa == 205_000_000_000.0
    evidence = promoted.current.content.calibration_evidence
    assert evidence is not None
    assert evidence.calibration_selection_id == SELECTION
    assert evidence.calibration_selection_revision_id == selection.current.record.revision_id
    assert evidence.calibration_candidate_id == CANDIDATE_ONE
    assert evidence.diagnostics_artifact_id == DIAGNOSTICS_ONE
    assert models.commands[0].expected_current_revision_id == MODEL_REVISION


def test_promotion_rejects_a_superseded_selection_revision() -> None:
    service, _repository, _calibrations, models = _service()
    first = service.create_selection(CONTEXT, WRITE, _create_command())
    service.revise_selection(
        CONTEXT,
        WRITE,
        SELECTION,
        ReviseReferenceCalibrationCandidateSelection(
            expected_current_revision_id=first.current.record.revision_id,
            selection_label="Elastic candidate accepted after human review",
            calibration_run_id=RUN,
            calibration_candidate_id=CANDIDATE_TWO,
            selection_reason="Use a later explicit human decision instead of the old one.",
        ),
    )

    with pytest.raises(CandidateSelectionConflict, match="current Candidate Selection revision"):
        service.promote_selected_candidate(
            CONTEXT,
            WRITE,
            SELECTION,
            PromoteSelectedReferenceCalibrationCandidate(
                selection_revision_id=first.current.record.revision_id,
                expected_material_model_revision_id=MODEL_REVISION,
                change_reason="Attempt promotion from a superseded human decision.",
            ),
        )
    assert models.commands == []

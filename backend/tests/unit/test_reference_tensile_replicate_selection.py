from __future__ import annotations

from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
from cmp.modules.datasets.application.service import (
    CalibrationDatasetSource,
    CreateReferenceTensileReplicateSelection,
    DatasetRevisionSnapshot,
    DatasetService,
    ReviseReferenceTensileReplicateSelection,
    RevisionSnapshot,
)
from cmp.modules.datasets.domain.reference_tensile import (
    DatasetConflict,
    DatasetContent,
    DatasetRepresentation,
    ReferenceTensileMapping,
)
from cmp.modules.datasets.domain.selection import (
    ReferenceTensileReplicateSelectionContent,
    reference_tensile_replicate_selection_canonical,
)
from cmp.modules.identity_access.application.authorization import database_permissions_for
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
    Permission,
    Role,
)
from cmp.modules.identity_access.domain.security import Principal, PrincipalType, SecurityContext
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

NOW = datetime(2026, 7, 15, 9, 0, tzinfo=UTC)
ORG, PROJECT, ACTOR, STATE = (uuid4() for _ in range(4))
SCOPE = TenantScope(ORG, PROJECT, DataClassification.INTERNAL.value)


class _Transaction(RevisionTransaction[ReferenceTensileReplicateSelectionContent]):
    def __init__(self, store: _Store) -> None:
        self.store = store

    def create(
        self, draft: RevisionDraft[ReferenceTensileReplicateSelectionContent]
    ) -> RevisionRecord:
        if draft.aggregate_id in self.store.heads:
            raise AggregateAlreadyExists(str(draft.aggregate_id))
        return self._save(draft, 1, None)

    def revise(
        self,
        draft: RevisionDraft[ReferenceTensileReplicateSelectionContent],
        expected_current_revision_id: UUID,
    ) -> RevisionRecord:
        current_id = self.store.heads.get(draft.aggregate_id)
        if current_id is None:
            raise AggregateNotFound(str(draft.aggregate_id))
        if current_id != expected_current_revision_id:
            raise RevisionConflict(expected_current_revision_id, self.store.records[current_id].ref)
        return self._save(
            draft, self.store.records[current_id].revision_no + 1, current_id
        )

    def _save(
        self,
        draft: RevisionDraft[ReferenceTensileReplicateSelectionContent],
        revision_no: int,
        based_on: UUID | None,
    ) -> RevisionRecord:
        record = RevisionRecord(
            revision_id=draft.revision_id,
            aggregate_type=draft.aggregate_type,
            aggregate_id=draft.aggregate_id,
            scope=draft.scope,
            revision_no=revision_no,
            based_on_revision_id=based_on,
            schema_id=draft.schema_id,
            schema_version=draft.schema_version,
            content_hash=draft.content_hash,
            created_at=draft.created_at,
            created_by=draft.created_by,
            change_reason=draft.change_reason,
            request_id=draft.request_id,
            trace_id=draft.trace_id,
        )
        self.store.heads[draft.aggregate_id] = draft.revision_id
        self.store.records[draft.revision_id] = record
        self.store.contents[draft.revision_id] = draft.content
        return record

    def stage(self, event: RevisionCreated) -> None:
        del event


class _Store(RevisionStore[ReferenceTensileReplicateSelectionContent]):
    def __init__(self) -> None:
        self.heads: dict[UUID, UUID] = {}
        self.records: dict[UUID, RevisionRecord] = {}
        self.contents: dict[UUID, ReferenceTensileReplicateSelectionContent] = {}

    def canonical_content(self, content: ReferenceTensileReplicateSelectionContent) -> object:
        return reference_tensile_replicate_selection_canonical(content)

    def transaction(
        self,
    ) -> AbstractContextManager[
        RevisionTransaction[ReferenceTensileReplicateSelectionContent]
    ]:
        return self._transaction()

    @contextmanager
    def _transaction(
        self,
    ) -> Iterator[RevisionTransaction[ReferenceTensileReplicateSelectionContent]]:
        yield _Transaction(self)


class _Repository:
    def __init__(self) -> None:
        self.store = _Store()
        self.sources: dict[UUID, CalibrationDatasetSource] = {}

    def replicate_selection_store(self, context: Any, decision: Any) -> _Store:
        del context, decision
        return self.store

    def get_calibration_dataset_source(
        self, *, context: Any, decision: Any, dataset_revision_id: UUID
    ) -> CalibrationDatasetSource:
        del context, decision
        return self.sources[dataset_revision_id]

    def get_tensile_replicate_selection(
        self, *, context: Any, decision: Any, selection_id: UUID
    ) -> Any:
        del context, decision
        revision_id = self.store.heads[selection_id]
        record = self.store.records[revision_id]
        content = self.store.contents[revision_id]
        from cmp.modules.datasets.application.service import TensileReplicateSelectionSnapshot

        return TensileReplicateSelectionSnapshot(
            selection_id, content.selection_label, RevisionSnapshot(record, content)
        )

    def list_tensile_replicate_selections_for_material_state(
        self, **kwargs: Any
    ) -> tuple[Any, ...]:
        del kwargs
        return ()


def _context() -> tuple[SecurityContext, AuthorizationDecision]:
    context = SecurityContext(
        principal=Principal(ACTOR, PrincipalType.USER, "engineer", True),
        organization_id=ORG,
        project_id=PROJECT,
        issuer="https://id.invalid",
        subject=str(ACTOR),
        token_id=str(uuid4()),
        groups=(),
        scopes=("openid",),
        request_id=uuid4(),
        trace_id="replicate-selection-test",
        authenticated_at=NOW,
    )
    decision = AuthorizationDecision(
        principal_id=ACTOR,
        organization_id=ORG,
        project_id=PROJECT,
        permission=Permission.DATASET_WRITE,
        roles=(Role.TEST_ENGINEER,),
        database_permissions=database_permissions_for(Permission.DATASET_WRITE),
        max_classification=DataClassification.INTERNAL,
        allow_export_controlled=False,
        request_id=context.request_id,
        trace_id=context.trace_id,
        decided_at=NOW,
    )
    return context, decision


def _source(material_state_id: UUID, run_revision_id: UUID) -> CalibrationDatasetSource:
    dataset_id, revision_id, run_id = uuid4(), uuid4(), uuid4()
    content = DatasetContent(
        test_run_id=run_id,
        test_run_revision_id=run_revision_id,
        raw_asset_id=uuid4(),
        raw_artifact_id=uuid4(),
        data_artifact_id=uuid4(),
        data_sha256="a" * 64,
        representation=DatasetRepresentation.NORMALIZED,
        source_dataset_revision_id=uuid4(),
        point_count=3,
        mapping=ReferenceTensileMapping("strain", "stress", "1", "Pa"),
    )
    record = RevisionRecord(
        revision_id=revision_id,
        aggregate_type="datasets.dataset",
        aggregate_id=dataset_id,
        scope=SCOPE,
        revision_no=2,
        based_on_revision_id=content.source_dataset_revision_id,
        schema_id="urn:test",
        schema_version="1.0.0",
        content_hash="b" * 64,
        created_at=NOW,
        created_by=ACTOR,
        change_reason="normalize",
        request_id=uuid4(),
        trace_id="source",
    )
    return CalibrationDatasetSource(
        dataset=DatasetRevisionSnapshot(dataset_id, RevisionSnapshot(record, content)),
        material_state_id=material_state_id,
    )


def test_replicate_selection_appends_membership_revision_and_preserves_first() -> None:
    repository = _Repository()
    first, second, third = (_source(STATE, uuid4()) for _ in range(3))
    for source in (first, second, third):
        repository.sources[source.dataset.revision.record.revision_id] = source
    context, decision = _context()
    service = DatasetService(repository=repository, artifacts=None)  # type: ignore[arg-type]

    created = service.create_reference_tensile_replicate_selection(
        context,
        decision,
        CreateReferenceTensileReplicateSelection(
            DataClassification.INTERNAL,
            "three tensile replicates",
            (
                first.dataset.revision.record.revision_id,
                second.dataset.revision.record.revision_id,
            ),
            "pin two independent tests",
        ),
    )
    revised = service.revise_reference_tensile_replicate_selection(
        context,
        decision,
        created.id,
        ReviseReferenceTensileReplicateSelection(
            created.current.record.revision_id,
            (
                first.dataset.revision.record.revision_id,
                second.dataset.revision.record.revision_id,
                third.dataset.revision.record.revision_id,
            ),
            "add third replicate",
        ),
    )

    assert created.current.record.revision_no == 1
    assert len(created.current.content.members) == 2
    assert revised.current.record.revision_no == 2
    assert revised.current.record.based_on_revision_id == created.current.record.revision_id
    assert len(revised.current.content.members) == 3
    assert len(repository.store.contents[created.current.record.revision_id].members) == 2


def test_replicate_selection_rejects_members_from_different_material_states() -> None:
    repository = _Repository()
    first = _source(STATE, uuid4())
    second = _source(uuid4(), uuid4())
    for source in (first, second):
        repository.sources[source.dataset.revision.record.revision_id] = source
    context, decision = _context()
    service = DatasetService(repository=repository, artifacts=None)  # type: ignore[arg-type]

    with pytest.raises(DatasetConflict, match="one Material State"):
        service.create_reference_tensile_replicate_selection(
            context,
            decision,
            CreateReferenceTensileReplicateSelection(
                DataClassification.INTERNAL,
                "invalid mixed state",
                (
                    first.dataset.revision.record.revision_id,
                    second.dataset.revision.record.revision_id,
                ),
                "must reject mixed states",
            ),
        )

from __future__ import annotations

from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager
from copy import deepcopy
from dataclasses import FrozenInstanceError, dataclass
from datetime import UTC, datetime
from uuid import UUID

import pytest
from cmp.shared.application.revisions import (
    CreateRevisionedAggregate,
    ReviseAggregate,
    RevisionService,
    RevisionTransaction,
)
from cmp.shared.contracts.revisions import (
    InvalidRevisionETag,
    RevisionETag,
    RevisionPreconditionFailed,
    require_matching_if_match,
)
from cmp.shared.domain.revisions import (
    AggregateAlreadyExists,
    AggregateNotFound,
    CanonicalizationError,
    InvalidRevisionCommand,
    InvalidRevisionReference,
    RevisionConflict,
    RevisionCreated,
    RevisionDraft,
    RevisionRecord,
    TenantScope,
    canonical_json_bytes,
    concrete_revision_id,
    content_sha256,
)

ORG = UUID("00000000-0000-4000-8000-000000000001")
PROJECT = UUID("00000000-0000-4000-8000-000000000002")
OTHER_PROJECT = UUID("00000000-0000-4000-8000-000000000003")
ACTOR = UUID("00000000-0000-4000-8000-000000000004")
AGGREGATE = UUID("00000000-0000-4000-8000-000000000005")
REQUEST = UUID("00000000-0000-4000-8000-000000000006")
REVISION_1 = UUID("00000000-0000-4000-8000-000000000007")
REVISION_2 = UUID("00000000-0000-4000-8000-000000000008")
REVISION_3 = UUID("00000000-0000-4000-8000-000000000009")
NOW = datetime(2026, 7, 11, tzinfo=UTC)


@dataclass(frozen=True, slots=True)
class NoteContent:
    title: str
    body: str
    pinned: bool = False


def note_json(content: NoteContent) -> object:
    return {"body": content.body, "pinned": content.pinned, "title": content.title}


@dataclass
class _State:
    heads: dict[tuple[UUID, UUID, UUID], UUID]
    records: dict[UUID, RevisionRecord]
    contents: dict[UUID, NoteContent]
    events: list[RevisionCreated]


class _FakeTransaction:
    def __init__(self, state: _State, *, fail_hook: bool) -> None:
        self.state = state
        self.fail_hook = fail_hook

    @staticmethod
    def _key(draft: RevisionDraft[NoteContent]) -> tuple[UUID, UUID, UUID]:
        return (
            draft.scope.organization_id,
            draft.scope.project_id,
            draft.aggregate_id,
        )

    @staticmethod
    def _record(
        draft: RevisionDraft[NoteContent], revision_no: int, based_on: UUID | None
    ) -> RevisionRecord:
        return RevisionRecord(
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

    def create(self, draft: RevisionDraft[NoteContent]) -> RevisionRecord:
        key = self._key(draft)
        if key in self.state.heads:
            raise AggregateAlreadyExists(str(draft.aggregate_id))
        record = self._record(draft, 1, None)
        self.state.heads[key] = record.revision_id
        self.state.records[record.revision_id] = record
        self.state.contents[record.revision_id] = draft.content
        return record

    def revise(
        self,
        draft: RevisionDraft[NoteContent],
        expected_current_revision_id: UUID,
    ) -> RevisionRecord:
        key = self._key(draft)
        current_id = self.state.heads.get(key)
        if current_id is None:
            raise AggregateNotFound(str(draft.aggregate_id))
        current = self.state.records[current_id]
        if current_id != expected_current_revision_id:
            raise RevisionConflict(expected_current_revision_id, current.ref)
        record = self._record(draft, current.revision_no + 1, current_id)
        self.state.heads[key] = record.revision_id
        self.state.records[record.revision_id] = record
        self.state.contents[record.revision_id] = draft.content
        return record

    def stage(self, event: RevisionCreated) -> None:
        if self.fail_hook:
            raise RuntimeError("synthetic provenance hook failure")
        self.state.events.append(event)


class _FakeStore:
    def __init__(self) -> None:
        self.state = _State({}, {}, {}, [])
        self.fail_hook = False

    def canonical_content(self, content: NoteContent) -> object:
        return note_json(content)

    def transaction(
        self,
    ) -> AbstractContextManager[RevisionTransaction[NoteContent]]:
        return self._transaction()

    @contextmanager
    def _transaction(self) -> Iterator[RevisionTransaction[NoteContent]]:
        candidate = deepcopy(self.state)
        transaction = _FakeTransaction(candidate, fail_hook=self.fail_hook)
        yield transaction
        self.state = candidate


def _ids() -> Iterator[UUID]:
    yield REVISION_1
    yield REVISION_2
    yield REVISION_3


def _service(store: _FakeStore) -> RevisionService[NoteContent]:
    identifiers = _ids()
    return RevisionService(
        aggregate_type="test.note",
        store=store,
        id_factory=lambda: next(identifiers),
        clock=lambda: NOW,
    )


def _create(scope: TenantScope | None = None) -> CreateRevisionedAggregate[NoteContent]:
    return CreateRevisionedAggregate(
        aggregate_id=AGGREGATE,
        scope=scope or TenantScope(ORG, PROJECT, "internal"),
        schema_id="urn:cmp:test:typed-note:v1",
        schema_version="1.0.0",
        content=NoteContent("First", "immutable body"),
        created_by=ACTOR,
        change_reason="initial revision",
        request_id=REQUEST,
        trace_id="00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01",
    )


def _revise(
    expected: UUID,
    *,
    scope: TenantScope | None = None,
    based_on: UUID | None = None,
) -> ReviseAggregate[NoteContent]:
    return ReviseAggregate(
        aggregate_id=AGGREGATE,
        scope=scope or TenantScope(ORG, PROJECT, "internal"),
        expected_current_revision_id=expected,
        based_on_revision_id=based_on or expected,
        schema_id="urn:cmp:test:typed-note:v1",
        schema_version="1.0.0",
        content=NoteContent("Second", "new row, old row retained", True),
        created_by=ACTOR,
        change_reason="correct note metadata",
        request_id=REQUEST,
        trace_id="00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01",
    )


def test_canonical_json_hash_is_order_independent_but_array_order_is_not() -> None:
    left = {"z": [1, 2], "a": {"unit": "Pa", "value": 3.0}}
    right = {"a": {"value": 3.0, "unit": "Pa"}, "z": (1, 2)}

    assert canonical_json_bytes(left) == canonical_json_bytes(right)
    assert content_sha256(left) == content_sha256(right)
    assert content_sha256({"z": [2, 1]}) != content_sha256({"z": [1, 2]})


@pytest.mark.parametrize("value", [float("nan"), float("inf"), UUID(int=1)])
def test_canonical_json_rejects_implicit_or_non_finite_values(value: object) -> None:
    with pytest.raises(CanonicalizationError):
        canonical_json_bytes({"value": value})


def test_only_concrete_revision_uuid_is_accepted() -> None:
    assert concrete_revision_id(str(REVISION_1)) == REVISION_1
    with pytest.raises(InvalidRevisionReference):
        concrete_revision_id("latest")


def test_create_and_revise_keep_stable_identity_and_append_rows() -> None:
    store = _FakeStore()
    service = _service(store)

    first = service.create(_create())
    second = service.revise(_revise(first.revision_id))

    assert first.aggregate_id == second.aggregate_id == AGGREGATE
    assert first.revision_no == 1
    assert second.revision_no == 2
    assert second.based_on_revision_id == first.revision_id
    assert store.state.records[first.revision_id] == first
    assert store.state.contents[first.revision_id].body == "immutable body"
    assert len(store.state.records) == 2
    assert [event.revision.revision_no for event in store.state.events] == [1, 2]


def test_caller_owned_transaction_can_stage_multiple_revisions_without_early_commit() -> None:
    store = _FakeStore()
    service = _service(store)
    candidate = deepcopy(store.state)
    transaction = _FakeTransaction(candidate, fail_hook=False)

    first = service.create_in(transaction, _create())
    second = service.revise_in(transaction, _revise(first.revision_id))

    assert store.state.records == {}
    assert store.state.events == []
    assert candidate.heads[(ORG, PROJECT, AGGREGATE)] == second.revision_id
    assert [event.revision.revision_no for event in candidate.events] == [1, 2]


def test_stale_head_is_rejected_without_creating_revision() -> None:
    store = _FakeStore()
    service = _service(store)
    first = service.create(_create())
    second = service.revise(_revise(first.revision_id))

    with pytest.raises(RevisionConflict) as raised:
        service.revise(_revise(first.revision_id))

    assert raised.value.current == second.ref
    assert len(store.state.records) == 2


def test_based_on_must_match_expected_head() -> None:
    store = _FakeStore()
    service = _service(store)
    first = service.create(_create())

    with pytest.raises(InvalidRevisionCommand):
        service.revise(_revise(first.revision_id, based_on=REVISION_3))


def test_cross_project_lookup_is_indistinguishable_from_missing() -> None:
    store = _FakeStore()
    service = _service(store)
    first = service.create(_create())

    with pytest.raises(AggregateNotFound):
        service.revise(
            _revise(
                first.revision_id,
                scope=TenantScope(ORG, OTHER_PROJECT, "internal"),
            )
        )


def test_hook_failure_rolls_back_revision_and_head() -> None:
    store = _FakeStore()
    service = _service(store)
    first = service.create(_create())
    store.fail_hook = True

    with pytest.raises(RuntimeError, match="hook failure"):
        service.revise(_revise(first.revision_id))

    key = (ORG, PROJECT, AGGREGATE)
    assert store.state.heads[key] == first.revision_id
    assert list(store.state.records) == [first.revision_id]
    assert len(store.state.events) == 1


def test_revision_metadata_is_frozen() -> None:
    store = _FakeStore()
    first = _service(store).create(_create())

    with pytest.raises(FrozenInstanceError):
        first.revision_no = 9  # type: ignore[misc]


def test_revision_etag_is_strong_exact_and_maps_to_concrete_revision() -> None:
    store = _FakeStore()
    first = _service(store).create(_create())
    etag = RevisionETag.from_ref(first.ref)

    assert str(etag) == f'"revision:1:sha256:{first.content_hash}"'
    assert RevisionETag.parse(str(etag)) == etag
    assert require_matching_if_match(str(etag), first.ref) == first.revision_id


@pytest.mark.parametrize(
    "value",
    [None, "*", 'W/"revision:1:sha256:' + "a" * 64 + '"', '"revision:1:sha256:bad"'],
)
def test_revision_etag_rejects_missing_wildcard_weak_and_malformed(
    value: str | None,
) -> None:
    current = RevisionRecord(
        revision_id=REVISION_1,
        aggregate_type="test.note",
        aggregate_id=AGGREGATE,
        scope=TenantScope(ORG, PROJECT, "internal"),
        revision_no=1,
        based_on_revision_id=None,
        schema_id="urn:test",
        schema_version="1",
        content_hash="a" * 64,
        created_at=NOW,
        created_by=ACTOR,
        change_reason="initial",
        request_id=REQUEST,
        trace_id="trace",
    ).ref

    with pytest.raises(InvalidRevisionETag):
        require_matching_if_match(value, current)


def test_stale_revision_etag_reports_current_concrete_revision() -> None:
    current = RevisionRecord(
        revision_id=REVISION_2,
        aggregate_type="test.note",
        aggregate_id=AGGREGATE,
        scope=TenantScope(ORG, PROJECT, "internal"),
        revision_no=2,
        based_on_revision_id=REVISION_1,
        schema_id="urn:test",
        schema_version="1",
        content_hash="b" * 64,
        created_at=NOW,
        created_by=ACTOR,
        change_reason="second",
        request_id=REQUEST,
        trace_id="trace",
    ).ref
    stale = RevisionETag(1, "a" * 64)

    with pytest.raises(RevisionPreconditionFailed) as raised:
        require_matching_if_match(str(stale), current)

    assert raised.value.current == current

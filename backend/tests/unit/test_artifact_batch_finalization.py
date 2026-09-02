from __future__ import annotations

import asyncio
import hashlib
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
from cmp.modules.artifacts.application.content import (
    ArtifactService,
    ArtifactTransferCodec,
    FinalizedArtifact,
    PrepareArtifact,
)
from cmp.modules.artifacts.domain.content import (
    Artifact,
    ArtifactAccessDenied,
    ArtifactConflict,
    ArtifactIntegrityError,
    ArtifactKind,
    ArtifactNotFound,
    ArtifactRecord,
    IntegrityStatus,
    PendingArtifact,
    PendingArtifactState,
    StoredObject,
)
from cmp.modules.artifacts.domain.uploads import ObjectStoreError
from cmp.modules.identity_access.application.authorization import database_permissions_for
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
    Permission,
    Role,
)
from cmp.modules.identity_access.domain.security import Principal, PrincipalType, SecurityContext

NOW = datetime(2026, 9, 3, 12, 0, tzinfo=UTC)
ORG = UUID("8e000000-0000-4000-8000-000000000001")
PROJECT = UUID("8e000000-0000-4000-8000-000000000002")
ACTOR = UUID("8e000000-0000-4000-8000-000000000003")
TRACE = "00-0000000000000000000000000000008e-000000000000008e-01"


def _context() -> SecurityContext:
    return SecurityContext(
        principal=Principal(ACTOR, PrincipalType.USER, "DMA artifact test", True),
        organization_id=ORG,
        project_id=PROJECT,
        issuer="urn:cmp:test",
        subject=str(ACTOR),
        token_id="dma-artifact-batch",
        groups=(),
        scopes=("openid",),
        request_id=UUID("8e000000-0000-4000-8000-000000000004"),
        trace_id=TRACE,
        authenticated_at=NOW,
    )


def _decision(context: SecurityContext) -> AuthorizationDecision:
    return AuthorizationDecision(
        principal_id=context.principal.id,
        organization_id=context.organization_id,
        project_id=context.project_id,
        permission=Permission.ARTIFACT_WRITE,
        roles=(Role.DATA_STEWARD,),
        database_permissions=database_permissions_for(Permission.ARTIFACT_WRITE),
        max_classification=DataClassification.RESTRICTED,
        allow_export_controlled=False,
        request_id=context.request_id,
        trace_id=context.trace_id,
        decided_at=NOW,
    )


class _BatchObjectStore:
    def __init__(self, events: list[str], *, fail_promote_at: int | None = None) -> None:
        self.events = events
        self.fail_promote_at = fail_promote_at
        self.promote_calls = 0
        self.staged: dict[str, StoredObject] = {}
        self.promoted: dict[str, StoredObject] = {}

    async def stage_bytes(self, *, object_key: str, value: bytes, media_type: str) -> StoredObject:
        del media_type
        stored = StoredObject(
            object_key=object_key,
            size_bytes=len(value),
            sha256=hashlib.sha256(value).hexdigest(),
            etag=f'"stage-{len(self.staged) + 1}"',
            version_id=f"stage-{len(self.staged) + 1}",
        )
        self.events.append(f"stage:{object_key}")
        self.staged[object_key] = stored
        return stored

    async def promote(
        self,
        *,
        source_key: str,
        target_key: str,
        expected_sha256: str,
        expected_size_bytes: int,
    ) -> StoredObject:
        self.promote_calls += 1
        self.events.append(f"promote:{source_key}")
        if self.fail_promote_at == self.promote_calls:
            raise ObjectStoreError("injected promotion failure")
        staged = self.staged[source_key]
        if staged.sha256 != expected_sha256 or staged.size_bytes != expected_size_bytes:
            raise ObjectStoreError("staged object does not match the promotion manifest")
        promoted = StoredObject(
            object_key=target_key,
            size_bytes=staged.size_bytes,
            sha256=staged.sha256,
            etag=f'"promoted-{self.promote_calls}"',
            version_id=f"promoted-{self.promote_calls}",
        )
        self.promoted[target_key] = promoted
        return promoted

    async def discard(self, object_key: str) -> None:
        self.events.append(f"discard:{object_key}")
        self.staged.pop(object_key, None)


class _BatchRepository:
    """Small repository fake with the same atomic boundary as the SQL adapter."""

    def __init__(self, events: list[str]) -> None:
        self.events = events
        self.pending_by_id: dict[UUID, PendingArtifact] = {}
        self.pending_by_key: dict[str, UUID] = {}
        self.records: dict[UUID, ArtifactRecord] = {}
        self.batch_calls = 0
        self.retryable_calls: list[tuple[UUID, str]] = []

    def prepare(self, *, pending: PendingArtifact, **_: Any) -> tuple[PendingArtifact, bool]:
        existing_id = self.pending_by_key.get(pending.idempotency_key)
        if existing_id is not None:
            return self.pending_by_id[existing_id], True
        self.pending_by_id[pending.id] = pending
        self.pending_by_key[pending.idempotency_key] = pending.id
        return pending, False

    def begin_promotion(self, *, pending_id: UUID, now: datetime, **_: Any) -> PendingArtifact:
        current = self.pending_by_id[pending_id]
        if current.state is PendingArtifactState.AVAILABLE:
            return current
        current = replace(
            current,
            state=PendingArtifactState.PROMOTING,
            attempt_count=current.attempt_count + 1,
            updated_at=now,
        )
        self.pending_by_id[pending_id] = current
        return current

    def mark_retryable(
        self,
        *,
        pending_id: UUID,
        failure_code: str,
        now: datetime,
        **_: Any,
    ) -> PendingArtifact:
        current = self.pending_by_id[pending_id]
        retryable = replace(
            current,
            state=PendingArtifactState.RETRYABLE,
            failure_code=failure_code,
            updated_at=now,
            terminal_at=None,
        )
        self.pending_by_id[pending_id] = retryable
        self.retryable_calls.append((pending_id, failure_code))
        return retryable

    def commit_available_batch(
        self,
        *,
        entries: tuple[tuple[UUID, StoredObject, UUID, datetime], ...],
        commit_hook: Any = None,
        **_: Any,
    ) -> tuple[FinalizedArtifact, ...]:
        self.batch_calls += 1
        self.events.append("repository:batch_commit")
        pending_backup = self.pending_by_id.copy()
        records_backup = self.records.copy()
        finalized: list[FinalizedArtifact] = []
        try:
            for pending_id, stored, observation_id, now in entries:
                pending = self.pending_by_id[pending_id]
                artifact_id = pending.reserved_artifact_id
                assert artifact_id is not None
                artifact = Artifact(
                    id=artifact_id,
                    organization_id=pending.organization_id,
                    project_id=pending.project_id,
                    classification=pending.classification,
                    artifact_kind=pending.artifact_kind,
                    artifact_role=pending.artifact_role,
                    schema_ref=pending.schema_ref,
                    media_type=pending.media_type,
                    size_bytes=stored.size_bytes,
                    sha256=stored.sha256,
                    storage_key=stored.object_key,
                    encryption_profile=pending.encryption_profile,
                    source_raw_asset_id=pending.source_raw_asset_id,
                    source_pending_id=pending.id,
                    created_at=now,
                    created_by=pending.created_by,
                )
                record = ArtifactRecord(
                    artifact=artifact,
                    integrity_status=IntegrityStatus.VERIFIED,
                    last_checked_at=now,
                    last_observation_id=observation_id,
                )
                available = replace(
                    pending,
                    state=PendingArtifactState.AVAILABLE,
                    available_artifact_id=artifact.id,
                    attempt_count=max(1, pending.attempt_count),
                    updated_at=now,
                    terminal_at=now,
                )
                self.pending_by_id[pending_id] = available
                self.records[artifact.id] = record
                finalized.append(FinalizedArtifact(available, record, False))
            if commit_hook is not None:
                commit_hook(object(), tuple(finalized))
        except Exception:
            self.pending_by_id = pending_backup
            self.records = records_backup
            raise
        return tuple(finalized)

    def get_artifact(self, *, artifact_id: UUID, **_: Any) -> ArtifactRecord:
        try:
            return self.records[artifact_id]
        except KeyError as error:
            raise ArtifactNotFound("Artifact is not available") from error


def _entries(context: SecurityContext, suffix: str) -> tuple[tuple[PrepareArtifact, bytes], ...]:
    values = (f"metadata-{suffix}".encode(), f"result-{suffix}".encode())
    return tuple(
        (
            PrepareArtifact(
                classification=DataClassification.INTERNAL,
                artifact_kind=ArtifactKind.DERIVED,
                artifact_role=f"processing.dma-{role}",
                schema_ref=f"urn:cmp:test:{role}:1",
                media_type="application/octet-stream",
                expected_size_bytes=len(value),
                expected_sha256=hashlib.sha256(value).hexdigest(),
                staging_object_key=f"staging/{context.project_id}/{suffix}/{role}",
                idempotency_key=f"dma-batch:{suffix}:{role}",
                reserved_artifact_id=uuid4(),
            ),
            value,
        )
        for role, value in zip(("metadata", "result"), values, strict=True)
    )


def _service(
    repository: _BatchRepository,
    store: _BatchObjectStore,
) -> ArtifactService:
    return ArtifactService(
        repository=repository,
        object_store=store,
        transfers=ArtifactTransferCodec(b"issue391-artifact-batch-test-secret-32-bytes"),
        id_factory=uuid4,
        clock=lambda: NOW,
    )


def test_finalize_derived_batch_promotes_both_before_one_commit_and_passes_both_to_hook() -> None:
    context = _context()
    entries = _entries(context, "success")
    events: list[str] = []
    repository = _BatchRepository(events)
    store = _BatchObjectStore(events)
    hook_records: list[tuple[FinalizedArtifact, ...]] = []

    def commit_hook(_session: object, records: tuple[FinalizedArtifact, ...]) -> None:
        events.append("hook:both_records")
        hook_records.append(records)

    finalized = asyncio.run(
        _service(repository, store).finalize_derived_batch(
            context,
            _decision(context),
            entries=entries,
            commit_hook=commit_hook,
        )
    )

    assert len(finalized) == 2
    assert repository.batch_calls == 1
    assert hook_records == [finalized]
    assert events.index("promote:" + entries[0][0].staging_object_key) < events.index(
        "repository:batch_commit"
    )
    assert events.index("promote:" + entries[1][0].staging_object_key) < events.index(
        "repository:batch_commit"
    )
    assert events.index("hook:both_records") < events.index(
        "discard:" + entries[0][0].staging_object_key
    )
    assert all(item.pending.state is PendingArtifactState.AVAILABLE for item in finalized)


def test_finalize_derived_batch_replay_requires_both_entries_available() -> None:
    context = _context()
    entries = _entries(context, "replay")
    events: list[str] = []
    repository = _BatchRepository(events)
    store = _BatchObjectStore(events)
    service = _service(repository, store)

    first = asyncio.run(
        service.finalize_derived_batch(context, _decision(context), entries=entries)
    )
    promote_count = store.promote_calls
    commit_count = repository.batch_calls
    replay = asyncio.run(
        service.finalize_derived_batch(context, _decision(context), entries=entries)
    )

    assert all(item.replayed for item in replay)
    assert tuple(item.record.artifact.id for item in replay) == tuple(
        item.record.artifact.id for item in first
    )
    assert store.promote_calls == promote_count
    assert repository.batch_calls == commit_count

    pending_id = repository.pending_by_key[entries[0][0].idempotency_key]
    repository.pending_by_id[pending_id] = replace(
        repository.pending_by_id[pending_id],
        state=PendingArtifactState.AVAILABLE,
    )
    second_id = repository.pending_by_key[entries[1][0].idempotency_key]
    repository.pending_by_id[second_id] = replace(
        repository.pending_by_id[second_id],
        state=PendingArtifactState.RETRYABLE,
        available_artifact_id=None,
        failure_code="batch_commit_failed",
        terminal_at=None,
    )
    with pytest.raises(ArtifactConflict, match="only valid when both entries are available"):
        asyncio.run(service.finalize_derived_batch(context, _decision(context), entries=entries))


def test_finalize_derived_batch_marks_promoted_objects_retryable_on_promotion_failure() -> None:
    context = _context()
    events: list[str] = []
    repository = _BatchRepository(events)
    store = _BatchObjectStore(events, fail_promote_at=2)

    with pytest.raises(ObjectStoreError, match="injected promotion failure"):
        asyncio.run(
            _service(repository, store).finalize_derived_batch(
                context,
                _decision(context),
                entries=_entries(context, "promote-failure"),
            )
        )

    assert repository.batch_calls == 0
    assert repository.retryable_calls == [
        (pending_id, "object_store_unavailable") for pending_id, _ in repository.retryable_calls
    ]
    assert all(
        pending.state is not PendingArtifactState.AVAILABLE
        for pending in repository.pending_by_id.values()
    )
    assert repository.records == {}


@pytest.mark.parametrize("failure_kind", ("repository", "hook"))
def test_finalize_derived_batch_never_exposes_authoritative_rows_when_commit_fails(
    failure_kind: str,
) -> None:
    context = _context()
    events: list[str] = []
    repository = _BatchRepository(events)
    store = _BatchObjectStore(events)
    entries = _entries(context, f"commit-failure-{failure_kind}")

    def commit_hook(_session: object, _records: tuple[FinalizedArtifact, ...]) -> None:
        if failure_kind == "hook":
            raise RuntimeError("injected batch commit hook failure")

    original_commit = repository.commit_available_batch

    if failure_kind == "repository":

        def failing_commit(**kwargs: Any) -> tuple[FinalizedArtifact, ...]:
            raise RuntimeError("injected repository batch failure")

        repository.commit_available_batch = failing_commit  # type: ignore[method-assign]

    with pytest.raises(RuntimeError, match="injected"):
        asyncio.run(
            _service(repository, store).finalize_derived_batch(
                context,
                _decision(context),
                entries=entries,
                commit_hook=commit_hook if failure_kind == "hook" else None,
            )
        )

    assert repository.records == {}
    assert all(
        pending.state is not PendingArtifactState.AVAILABLE
        for pending in repository.pending_by_id.values()
    )
    assert len(repository.retryable_calls) == 2
    assert {code for _, code in repository.retryable_calls} == {"batch_commit_failed"}
    if failure_kind == "repository":
        repository.commit_available_batch = original_commit  # type: ignore[method-assign]


def test_finalize_derived_batch_rejects_authorization_and_manifest_integrity_before_promotion() -> (
    None
):
    context = _context()
    entries = _entries(context, "boundary")

    no_artifact_capability = replace(
        _decision(context),
        permission=Permission.DATASET_READ,
        database_permissions=database_permissions_for(Permission.DATASET_READ),
    )
    with pytest.raises(ArtifactAccessDenied):
        asyncio.run(
            _service(_BatchRepository([]), _BatchObjectStore([])).finalize_derived_batch(
                context,
                no_artifact_capability,
                entries=entries,
            )
        )

    bad_manifest = list(entries)
    bad_manifest[0] = (
        replace(entries[0][0], expected_sha256="f" * 64),
        entries[0][1],
    )
    repository = _BatchRepository([])
    store = _BatchObjectStore([])
    with pytest.raises(ArtifactIntegrityError):
        asyncio.run(
            _service(repository, store).finalize_derived_batch(
                context,
                _decision(context),
                entries=tuple(bad_manifest),
            )
        )
    assert repository.pending_by_id == {}
    assert store.promote_calls == 0

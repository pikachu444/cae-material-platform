"""Application service and ports for typed aggregate revision writes."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID, uuid4

from cmp.shared.domain.revisions import (
    InvalidRevisionCommand,
    RevisionCreated,
    RevisionDraft,
    RevisionRecord,
    TenantScope,
    content_sha256,
)


@dataclass(frozen=True, slots=True)
class CreateRevisionedAggregate[ContentT]:
    """Create a stable identity and its first immutable typed revision."""

    aggregate_id: UUID
    scope: TenantScope
    schema_id: str
    schema_version: str
    content: ContentT
    created_by: UUID
    change_reason: str
    request_id: UUID
    trace_id: str


@dataclass(frozen=True, slots=True)
class ReviseAggregate[ContentT]:
    """Append a revision if the supplied concrete base is still the current head."""

    aggregate_id: UUID
    scope: TenantScope
    expected_current_revision_id: UUID
    based_on_revision_id: UUID
    schema_id: str
    schema_version: str
    content: ContentT
    created_by: UUID
    change_reason: str
    request_id: UUID
    trace_id: str


class RevisionTransaction[ContentT](Protocol):
    """Typed repository operations participating in one database transaction."""

    def create(self, draft: RevisionDraft[ContentT]) -> RevisionRecord:
        """Insert identity and revision 1."""

    def revise(
        self, draft: RevisionDraft[ContentT], expected_current_revision_id: UUID
    ) -> RevisionRecord:
        """Compare-and-swap the head, then insert the next revision."""

    def stage(self, event: RevisionCreated) -> None:
        """Run registered fail-closed hooks in the same transaction."""


class RevisionStore[ContentT](Protocol):
    """Factory for atomic, typed revision transactions."""

    def canonical_content(self, content: ContentT) -> object:
        """Map typed content to the exact canonical document used for its digest."""

    def transaction(self) -> AbstractContextManager[RevisionTransaction[ContentT]]: ...


class RevisionService[ContentT]:
    """Hash typed content and coordinate append-only revision transactions."""

    def __init__(
        self,
        *,
        aggregate_type: str,
        store: RevisionStore[ContentT],
        initial_lifecycle_state: str = "draft",
        id_factory: Callable[[], UUID] = uuid4,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._aggregate_type = aggregate_type
        self._store = store
        self._initial_lifecycle_state = initial_lifecycle_state
        self._id_factory = id_factory
        self._clock = clock or (lambda: datetime.now(UTC))

    def _draft(
        self,
        *,
        aggregate_id: UUID,
        scope: TenantScope,
        schema_id: str,
        schema_version: str,
        content: ContentT,
        created_by: UUID,
        change_reason: str,
        request_id: UUID,
        trace_id: str,
    ) -> RevisionDraft[ContentT]:
        return RevisionDraft(
            revision_id=self._id_factory(),
            aggregate_type=self._aggregate_type,
            aggregate_id=aggregate_id,
            scope=scope,
            schema_id=schema_id,
            schema_version=schema_version,
            content=content,
            content_hash=content_sha256(self._store.canonical_content(content)),
            created_at=self._clock(),
            created_by=created_by,
            change_reason=change_reason,
            request_id=request_id,
            trace_id=trace_id,
        )

    def create(self, command: CreateRevisionedAggregate[ContentT]) -> RevisionRecord:
        draft = self._draft(
            aggregate_id=command.aggregate_id,
            scope=command.scope,
            schema_id=command.schema_id,
            schema_version=command.schema_version,
            content=command.content,
            created_by=command.created_by,
            change_reason=command.change_reason,
            request_id=command.request_id,
            trace_id=command.trace_id,
        )
        with self._store.transaction() as transaction:
            record = transaction.create(draft)
            transaction.stage(RevisionCreated(record, self._initial_lifecycle_state))
            return record

    def revise(self, command: ReviseAggregate[ContentT]) -> RevisionRecord:
        if command.based_on_revision_id != command.expected_current_revision_id:
            raise InvalidRevisionCommand(
                "based_on_revision_id must equal the expected current revision"
            )
        draft = self._draft(
            aggregate_id=command.aggregate_id,
            scope=command.scope,
            schema_id=command.schema_id,
            schema_version=command.schema_version,
            content=command.content,
            created_by=command.created_by,
            change_reason=command.change_reason,
            request_id=command.request_id,
            trace_id=command.trace_id,
        )
        with self._store.transaction() as transaction:
            record = transaction.revise(draft, command.expected_current_revision_id)
            transaction.stage(RevisionCreated(record, self._initial_lifecycle_state))
            return record

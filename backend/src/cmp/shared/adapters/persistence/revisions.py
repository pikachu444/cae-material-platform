"""PostgreSQL/SQLAlchemy adapter for explicit typed aggregate and revision tables."""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from cmp.shared.application.revisions import RevisionTransaction
from cmp.shared.domain.revisions import (
    AggregateAlreadyExists,
    AggregateNotFound,
    InvalidRevisionCommand,
    RevisionConflict,
    RevisionCreated,
    RevisionDraft,
    RevisionRecord,
    RevisionRef,
    TenantScope,
    TenantScopeMismatch,
)

_IDENTITY_COLUMNS = frozenset(
    {
        "id",
        "organization_id",
        "project_id",
        "classification",
        "current_revision_id",
        "created_at",
        "created_by",
        "updated_at",
    }
)
_REVISION_COLUMNS = frozenset(
    {
        "id",
        "aggregate_id",
        "organization_id",
        "project_id",
        "classification",
        "revision_no",
        "based_on_revision_id",
        "schema_id",
        "schema_version",
        "content_hash",
        "created_at",
        "created_by",
        "change_reason",
        "request_id",
        "trace_id",
    }
)

SqlRevisionHook = Callable[[Session, RevisionCreated], None]
SqlRevisionContentWriter = Callable[[Session, RevisionDraft[Any]], None]


@dataclass(frozen=True, slots=True)
class TypedRevisionTables[ContentT]:
    """Bind the kernel to one explicit bounded-module table pair.

    ``content_values`` maps a typed object to named columns on ``revision_table``.  It cannot
    write any common metadata column, preventing a generic JSON/EAV fallback.
    """

    aggregate_type: str
    identity_table: sa.Table
    revision_table: sa.Table
    canonical_content: Callable[[ContentT], object]
    content_values: Callable[[ContentT], Mapping[str, Any]]
    identity_values: Callable[[ContentT], Mapping[str, Any]] | None = None
    revision_content_writer: SqlRevisionContentWriter | None = None

    def __post_init__(self) -> None:
        missing_identity = _IDENTITY_COLUMNS.difference(self.identity_table.c.keys())
        missing_revision = _REVISION_COLUMNS.difference(self.revision_table.c.keys())
        if missing_identity:
            raise ValueError(f"identity table is missing columns: {sorted(missing_identity)}")
        if missing_revision:
            raise ValueError(f"revision table is missing columns: {sorted(missing_revision)}")

    def encode_identity_values(self, content: ContentT) -> dict[str, Any]:
        """Return module-owned stable-identity columns for a typed aggregate.

        The revision kernel still owns its common identity columns.  Bounded modules may add
        a small number of immutable parent references to their stable identity (for example,
        a Material State belongs to one Material).  This deliberately remains a named-column
        mapping rather than a generic metadata or attribute payload.
        """

        if self.identity_values is None:
            return {}
        encoded = dict(self.identity_values(content))
        collisions = _IDENTITY_COLUMNS.intersection(encoded)
        if collisions:
            raise InvalidRevisionCommand(
                f"typed identity encoder attempted to replace kernel columns: {sorted(collisions)}"
            )
        unknown = set(encoded).difference(self.identity_table.c.keys())
        if unknown:
            raise InvalidRevisionCommand(
                f"typed identity encoder returned unknown columns: {sorted(unknown)}"
            )
        return encoded


class SqlAlchemyRevisionStore[ContentT]:
    """Create transaction-scoped repositories without sharing SQLAlchemy sessions."""

    def __init__(
        self,
        *,
        session_factory: Callable[[], Session],
        tables: TypedRevisionTables[ContentT],
        hooks: Sequence[SqlRevisionHook] = (),
        session_binder: Callable[[Session], None] | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._tables = tables
        self._hooks = tuple(hooks)
        self._session_binder = session_binder

    def canonical_content(self, content: ContentT) -> object:
        return self._tables.canonical_content(content)

    @contextmanager
    def transaction(self) -> Iterator[RevisionTransaction[ContentT]]:
        with self._session_factory() as session, session.begin():
            if self._session_binder is not None:
                self._session_binder(session)
            yield self.transaction_in(session)

    def transaction_in(self, session: Session) -> SqlAlchemyRevisionTransaction[ContentT]:
        """Join an already-bound caller transaction without committing it independently."""

        return SqlAlchemyRevisionTransaction(session, self._tables, self._hooks)


class SqlAlchemyRevisionTransaction[ContentT]:
    def __init__(
        self,
        session: Session,
        tables: TypedRevisionTables[ContentT],
        hooks: tuple[SqlRevisionHook, ...],
    ) -> None:
        self._session = session
        self._tables = tables
        self._hooks = hooks
        self._scope: TenantScope | None = None

    def _bind_scope(self, scope: TenantScope) -> None:
        if self._scope is not None:
            if self._scope != scope:
                raise TenantScopeMismatch("one transaction cannot mix tenant scopes")
            return
        self._session.execute(
            sa.select(
                sa.func.set_config("cmp.organization_id", str(scope.organization_id), True),
                sa.func.set_config("cmp.project_id", str(scope.project_id), True),
            )
        )
        self._scope = scope

    def _encoded_content(self, content: ContentT) -> dict[str, Any]:
        encoded = dict(self._tables.content_values(content))
        collisions = _REVISION_COLUMNS.intersection(encoded)
        if collisions:
            raise InvalidRevisionCommand(
                f"typed content encoder attempted to replace kernel columns: {sorted(collisions)}"
            )
        unknown = set(encoded).difference(self._tables.revision_table.c.keys())
        if unknown:
            raise InvalidRevisionCommand(
                f"typed content encoder returned unknown columns: {sorted(unknown)}"
            )
        return encoded

    def _record(
        self,
        draft: RevisionDraft[ContentT],
        *,
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

    def _revision_values(
        self,
        draft: RevisionDraft[ContentT],
        *,
        revision_no: int,
        based_on_revision_id: UUID | None,
    ) -> dict[str, Any]:
        values: dict[str, Any] = {
            "id": draft.revision_id,
            "aggregate_id": draft.aggregate_id,
            "organization_id": draft.scope.organization_id,
            "project_id": draft.scope.project_id,
            "classification": draft.scope.classification,
            "revision_no": revision_no,
            "based_on_revision_id": based_on_revision_id,
            "schema_id": draft.schema_id,
            "schema_version": draft.schema_version,
            "content_hash": draft.content_hash,
            "created_at": draft.created_at,
            "created_by": draft.created_by,
            "change_reason": draft.change_reason,
            "request_id": draft.request_id,
            "trace_id": draft.trace_id,
        }
        values.update(self._encoded_content(draft.content))
        return values

    def _identity_values(self, content: ContentT) -> dict[str, Any]:
        return self._tables.encode_identity_values(content)

    def _assert_identity_matches(self, draft: RevisionDraft[ContentT]) -> None:
        """Prevent a later revision from changing module-owned stable parent references."""

        encoded = self._identity_values(draft.content)
        if not encoded:
            return
        identity = self._tables.identity_table
        row = self._session.execute(
            sa.select(*(identity.c[name] for name in encoded)).where(
                identity.c.id == draft.aggregate_id,
                identity.c.organization_id == draft.scope.organization_id,
                identity.c.project_id == draft.scope.project_id,
            )
        ).mappings().one_or_none()
        if row is None:
            raise AggregateNotFound(str(draft.aggregate_id))
        if any(row[name] != value for name, value in encoded.items()):
            raise InvalidRevisionCommand(
                "typed revision content cannot change module-owned stable identity columns"
            )

    def create(self, draft: RevisionDraft[ContentT]) -> RevisionRecord:
        self._bind_scope(draft.scope)
        if draft.aggregate_type != self._tables.aggregate_type:
            raise InvalidRevisionCommand("aggregate type does not match the typed table binding")
        try:
            self._session.execute(
                sa.insert(self._tables.identity_table).values(
                    id=draft.aggregate_id,
                    organization_id=draft.scope.organization_id,
                    project_id=draft.scope.project_id,
                    classification=draft.scope.classification,
                    current_revision_id=draft.revision_id,
                    created_at=draft.created_at,
                    created_by=draft.created_by,
                    updated_at=draft.created_at,
                    **self._identity_values(draft.content),
                )
            )
            self._session.execute(
                sa.insert(self._tables.revision_table).values(
                    self._revision_values(
                        draft, revision_no=1, based_on_revision_id=None
                    )
                )
            )
            if self._tables.revision_content_writer is not None:
                self._tables.revision_content_writer(self._session, draft)
        except IntegrityError as error:
            diagnostic = getattr(error.orig, "diag", None)
            if (
                getattr(error.orig, "sqlstate", None) == "23505"
                and getattr(diagnostic, "table_name", None)
                == self._tables.identity_table.name
            ):
                raise AggregateAlreadyExists(str(draft.aggregate_id)) from error
            raise
        return self._record(draft, revision_no=1, based_on_revision_id=None)

    def _current_ref(self, draft: RevisionDraft[ContentT]) -> RevisionRef | None:
        identity = self._tables.identity_table
        revision = self._tables.revision_table
        row = self._session.execute(
            sa.select(
                revision.c.id,
                revision.c.revision_no,
                revision.c.content_hash,
            )
            .select_from(
                identity.join(
                    revision,
                    sa.and_(
                        revision.c.id == identity.c.current_revision_id,
                        revision.c.aggregate_id == identity.c.id,
                        revision.c.organization_id == identity.c.organization_id,
                        revision.c.project_id == identity.c.project_id,
                    ),
                )
            )
            .where(
                identity.c.id == draft.aggregate_id,
                identity.c.organization_id == draft.scope.organization_id,
                identity.c.project_id == draft.scope.project_id,
            )
        ).one_or_none()
        if row is None:
            return None
        return RevisionRef(row.id, row.revision_no, row.content_hash)

    def revise(
        self, draft: RevisionDraft[ContentT], expected_current_revision_id: UUID
    ) -> RevisionRecord:
        self._bind_scope(draft.scope)
        if draft.aggregate_type != self._tables.aggregate_type:
            raise InvalidRevisionCommand("aggregate type does not match the typed table binding")

        self._assert_identity_matches(draft)

        revision = self._tables.revision_table
        expected_no = self._session.execute(
            sa.select(revision.c.revision_no).where(
                revision.c.id == expected_current_revision_id,
                revision.c.aggregate_id == draft.aggregate_id,
                revision.c.organization_id == draft.scope.organization_id,
                revision.c.project_id == draft.scope.project_id,
            )
        ).scalar_one_or_none()
        if expected_no is None:
            current = self._current_ref(draft)
            if current is None:
                raise AggregateNotFound(str(draft.aggregate_id))
            raise RevisionConflict(expected_current_revision_id, current)

        identity = self._tables.identity_table
        result = self._session.execute(
            sa.update(identity)
            .where(
                identity.c.id == draft.aggregate_id,
                identity.c.organization_id == draft.scope.organization_id,
                identity.c.project_id == draft.scope.project_id,
                identity.c.current_revision_id == expected_current_revision_id,
            )
            .values(
                current_revision_id=draft.revision_id,
                updated_at=draft.created_at,
            )
        )
        if getattr(result, "rowcount", None) != 1:
            current = self._current_ref(draft)
            if current is None:
                raise AggregateNotFound(str(draft.aggregate_id))
            raise RevisionConflict(expected_current_revision_id, current)

        revision_no = int(expected_no) + 1
        self._session.execute(
            sa.insert(revision).values(
                self._revision_values(
                    draft,
                    revision_no=revision_no,
                    based_on_revision_id=expected_current_revision_id,
                )
            )
        )
        if self._tables.revision_content_writer is not None:
            self._tables.revision_content_writer(self._session, draft)
        return self._record(
            draft,
            revision_no=revision_no,
            based_on_revision_id=expected_current_revision_id,
        )

    def stage(self, event: RevisionCreated) -> None:
        for hook in self._hooks:
            hook(self._session, event)

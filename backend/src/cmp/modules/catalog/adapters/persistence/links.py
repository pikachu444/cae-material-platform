"""PostgreSQL persistence for Link Type and exact-revision Record Link aggregates (T-51)."""

from __future__ import annotations

from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session

from cmp.modules.catalog.adapters.persistence.configurable import RlsContext
from cmp.modules.catalog.application.configurable import ConfigRevision
from cmp.modules.catalog.application.links import (
    LINK_TYPE_AGGREGATE_TYPE,
    RECORD_LINK_AGGREGATE_TYPE,
    CatalogLinkRepository,
    DomainBindingKind,
    DomainRevisionBinding,
    LinkTypeSnapshot,
    RecordLinkSnapshot,
)
from cmp.modules.catalog.domain.configurable import ConfigurableCatalogNotFound
from cmp.modules.catalog.domain.links import (
    LinkCardinality,
    LinkTypeContent,
    RecordLinkContent,
    link_type_canonical,
    record_link_canonical,
)
from cmp.modules.identity_access.domain.authorization import AuthorizationDecision
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.shared.adapters.persistence.revisions import (
    SqlAlchemyRevisionStore,
    SqlRevisionHook,
    TypedRevisionTables,
)
from cmp.shared.application.revisions import RevisionStore
from cmp.shared.domain.revisions import RevisionRecord, TenantScope

metadata = sa.MetaData()
_uuid = sa.Uuid()


def _identity_table(name: str, *extra: sa.Column[Any]) -> sa.Table:
    return sa.Table(
        name,
        metadata,
        sa.Column("id", _uuid, nullable=False),
        sa.Column("organization_id", _uuid, nullable=False),
        sa.Column("project_id", _uuid, nullable=False),
        sa.Column("classification", sa.String(64), nullable=False),
        sa.Column("current_revision_id", _uuid, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", _uuid, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        *extra,
        schema="catalog",
    )


def _revision_table(name: str, *extra: sa.Column[Any]) -> sa.Table:
    return sa.Table(
        f"{name}_revision",
        metadata,
        sa.Column("id", _uuid, nullable=False),
        sa.Column("aggregate_id", _uuid, nullable=False),
        sa.Column("organization_id", _uuid, nullable=False),
        sa.Column("project_id", _uuid, nullable=False),
        sa.Column("classification", sa.String(64), nullable=False),
        sa.Column("revision_no", sa.BigInteger(), nullable=False),
        sa.Column("based_on_revision_id", _uuid, nullable=True),
        sa.Column("schema_id", sa.String(255), nullable=False),
        sa.Column("schema_version", sa.String(64), nullable=False),
        sa.Column("content_hash", sa.CHAR(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", _uuid, nullable=False),
        sa.Column("change_reason", sa.Text(), nullable=False),
        sa.Column("request_id", _uuid, nullable=False),
        sa.Column("trace_id", sa.String(255), nullable=False),
        *extra,
        schema="catalog",
    )


link_type = _identity_table(
    "link_type",
    sa.Column("link_key", sa.String(64), nullable=False),
    sa.Column("source_table_id", _uuid, nullable=False),
    sa.Column("target_table_id", _uuid, nullable=False),
)
link_type_revision = _revision_table(
    "link_type",
    sa.Column("link_key", sa.String(64), nullable=False),
    sa.Column("name", sa.String(200), nullable=False),
    sa.Column("source_table_id", _uuid, nullable=False),
    sa.Column("source_table_revision_id", _uuid, nullable=False),
    sa.Column("target_table_id", _uuid, nullable=False),
    sa.Column("target_table_revision_id", _uuid, nullable=False),
    sa.Column("forward_label", sa.String(200), nullable=False),
    sa.Column("reverse_label", sa.String(200), nullable=False),
    sa.Column("source_cardinality", sa.String(16), nullable=False),
    sa.Column("target_cardinality", sa.String(16), nullable=False),
    sa.Column("description", sa.Text(), nullable=True),
)
record_link = _identity_table(
    "record_link",
    sa.Column("link_type_id", _uuid, nullable=False),
    sa.Column("source_record_id", _uuid, nullable=False),
    sa.Column("target_record_id", _uuid, nullable=False),
)
record_link_revision = _revision_table(
    "record_link",
    sa.Column("link_type_id", _uuid, nullable=False),
    sa.Column("link_type_revision_id", _uuid, nullable=False),
    sa.Column("source_record_id", _uuid, nullable=False),
    sa.Column("source_record_revision_id", _uuid, nullable=False),
    sa.Column("target_record_id", _uuid, nullable=False),
    sa.Column("target_record_revision_id", _uuid, nullable=False),
    sa.Column("active", sa.Boolean(), nullable=False),
    sa.Column("note", sa.Text(), nullable=True),
)
domain_record_binding = sa.Table(
    "domain_record_binding",
    metadata,
    sa.Column("id", _uuid, primary_key=True),
    sa.Column("organization_id", _uuid, nullable=False),
    sa.Column("project_id", _uuid, nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("record_id", _uuid, nullable=False),
    sa.Column("record_revision_id", _uuid, nullable=False),
    sa.Column("domain_kind", sa.String(32), nullable=False),
    sa.Column("domain_object_id", _uuid, nullable=False),
    sa.Column("domain_revision_id", _uuid, nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("created_by", _uuid, nullable=False),
    sa.Column("request_id", _uuid, nullable=False),
    sa.Column("trace_id", sa.String(255), nullable=False),
    schema="catalog",
)


def _workbench_path(kind: DomainBindingKind, object_id: UUID, revision_id: UUID) -> str:
    query = f"object_id={object_id}&revision_id={revision_id}"
    roots = {
        DomainBindingKind.MATERIAL: f"/materials/{object_id}?revision_id={revision_id}",
        DomainBindingKind.MATERIAL_STATE: f"/materials?{query}",
        DomainBindingKind.SPECIMEN: f"/tests?{query}",
        DomainBindingKind.TEST_RUN: f"/tests?{query}",
        DomainBindingKind.TEST_DATA: f"/datasets/test-json?{query}",
        DomainBindingKind.PROCESSING_OUTPUT: f"/datasets/processing?{query}",
        DomainBindingKind.MATERIAL_MODEL: f"/models?{query}",
        DomainBindingKind.NEUTRAL_MATERIAL: f"/models?{query}",
        DomainBindingKind.SOLVER_CARD: f"/exports?{query}",
        DomainBindingKind.NEUTRAL_SOLVER_CARD: f"/exports?{query}",
        DomainBindingKind.RELEASE: f"/governance?{query}",
    }
    return roots[kind]


def _domain_binding(row: Any) -> DomainRevisionBinding:
    kind = DomainBindingKind(row["domain_kind"])
    return DomainRevisionBinding(
        id=row["id"],
        record_id=row["record_id"],
        record_revision_id=row["record_revision_id"],
        kind=kind,
        object_id=row["domain_object_id"],
        revision_id=row["domain_revision_id"],
        workbench_path=_workbench_path(kind, row["domain_object_id"], row["domain_revision_id"]),
    )


def _record(row: Any, aggregate_type: str) -> RevisionRecord:
    return RevisionRecord(
        revision_id=row["id"],
        aggregate_type=aggregate_type,
        aggregate_id=row["aggregate_id"],
        scope=TenantScope(row["organization_id"], row["project_id"], row["classification"]),
        revision_no=int(row["revision_no"]),
        based_on_revision_id=row["based_on_revision_id"],
        schema_id=row["schema_id"],
        schema_version=row["schema_version"],
        content_hash=row["content_hash"],
        created_at=row["created_at"],
        created_by=row["created_by"],
        change_reason=row["change_reason"],
        request_id=row["request_id"],
        trace_id=row["trace_id"],
    )


def _link_type_content(row: Any) -> LinkTypeContent:
    return LinkTypeContent(
        key=row["link_key"],
        name=row["name"],
        source_table_id=row["source_table_id"],
        source_table_revision_id=row["source_table_revision_id"],
        target_table_id=row["target_table_id"],
        target_table_revision_id=row["target_table_revision_id"],
        forward_label=row["forward_label"],
        reverse_label=row["reverse_label"],
        source_cardinality=LinkCardinality(row["source_cardinality"]),
        target_cardinality=LinkCardinality(row["target_cardinality"]),
        description=row["description"],
    )


def _record_link_content(row: Any) -> RecordLinkContent:
    return RecordLinkContent(
        link_type_id=row["link_type_id"],
        link_type_revision_id=row["link_type_revision_id"],
        source_record_id=row["source_record_id"],
        source_record_revision_id=row["source_record_revision_id"],
        target_record_id=row["target_record_id"],
        target_record_revision_id=row["target_record_revision_id"],
        active=bool(row["active"]),
        note=row["note"],
    )


def _link_type_values(content: LinkTypeContent) -> dict[str, Any]:
    return {
        "link_key": content.key,
        "name": content.name,
        "source_table_id": content.source_table_id,
        "source_table_revision_id": content.source_table_revision_id,
        "target_table_id": content.target_table_id,
        "target_table_revision_id": content.target_table_revision_id,
        "forward_label": content.forward_label,
        "reverse_label": content.reverse_label,
        "source_cardinality": content.source_cardinality.value,
        "target_cardinality": content.target_cardinality.value,
        "description": content.description,
    }


def _record_link_values(content: RecordLinkContent) -> dict[str, Any]:
    return {
        "link_type_id": content.link_type_id,
        "link_type_revision_id": content.link_type_revision_id,
        "source_record_id": content.source_record_id,
        "source_record_revision_id": content.source_record_revision_id,
        "target_record_id": content.target_record_id,
        "target_record_revision_id": content.target_record_revision_id,
        "active": content.active,
        "note": content.note,
    }


_LINK_TYPES = TypedRevisionTables(
    aggregate_type=LINK_TYPE_AGGREGATE_TYPE,
    identity_table=link_type,
    revision_table=link_type_revision,
    canonical_content=link_type_canonical,
    content_values=_link_type_values,
    identity_values=lambda content: {
        "link_key": content.key,
        "source_table_id": content.source_table_id,
        "target_table_id": content.target_table_id,
    },
)
_RECORD_LINKS = TypedRevisionTables(
    aggregate_type=RECORD_LINK_AGGREGATE_TYPE,
    identity_table=record_link,
    revision_table=record_link_revision,
    canonical_content=record_link_canonical,
    content_values=_record_link_values,
    identity_values=lambda content: {
        "link_type_id": content.link_type_id,
        "source_record_id": content.source_record_id,
        "target_record_id": content.target_record_id,
    },
)


def _revision_columns(table: sa.Table, aggregate_type: str) -> tuple[Any, ...]:
    return (
        table.c.id,
        sa.literal(aggregate_type).label("aggregate_type"),
        table.c.aggregate_id,
        table.c.organization_id,
        table.c.project_id,
        table.c.classification,
        table.c.revision_no,
        table.c.based_on_revision_id,
        table.c.schema_id,
        table.c.schema_version,
        table.c.content_hash,
        table.c.created_at,
        table.c.created_by,
        table.c.change_reason,
        table.c.request_id,
        table.c.trace_id,
    )


def _current_join(identity: sa.Table, revision: sa.Table) -> Any:
    return identity.join(
        revision,
        sa.and_(
            revision.c.id == identity.c.current_revision_id,
            revision.c.aggregate_id == identity.c.id,
            revision.c.organization_id == identity.c.organization_id,
            revision.c.project_id == identity.c.project_id,
            revision.c.classification == identity.c.classification,
        ),
    )


class SqlAlchemyCatalogLinkRepository(CatalogLinkRepository):
    def __init__(
        self,
        *,
        session_factory: Callable[[], Session],
        rls_context: RlsContext,
        revision_hooks: Sequence[SqlRevisionHook] = (),
    ) -> None:
        self._sessions = session_factory
        self._rls = rls_context
        self._hooks = tuple(revision_hooks)

    @contextmanager
    def _transaction(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> Iterator[Session]:
        with self._sessions() as session, session.begin():
            self._rls.bind_authorization(session, context, decision)
            yield session

    def _store[ContentT](
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        tables: TypedRevisionTables[ContentT],
    ) -> RevisionStore[ContentT]:
        return SqlAlchemyRevisionStore(
            session_factory=self._sessions,
            tables=tables,
            hooks=self._hooks,
            session_binder=lambda session: self._rls.bind_authorization(session, context, decision),
        )

    def link_type_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[LinkTypeContent]:
        return self._store(context, decision, _LINK_TYPES)

    def record_link_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[RecordLinkContent]:
        return self._store(context, decision, _RECORD_LINKS)

    @staticmethod
    def _link_type_statement(*, current: bool) -> sa.Select[Any]:
        source = (
            _current_join(link_type, link_type_revision)
            if current
            else link_type.join(
                link_type_revision,
                sa.and_(
                    link_type_revision.c.aggregate_id == link_type.c.id,
                    link_type_revision.c.organization_id == link_type.c.organization_id,
                    link_type_revision.c.project_id == link_type.c.project_id,
                    link_type_revision.c.classification == link_type.c.classification,
                ),
            )
        )
        return sa.select(
            link_type.c.id.label("identity_id"),
            *_revision_columns(link_type_revision, LINK_TYPE_AGGREGATE_TYPE),
            link_type_revision.c.link_key,
            link_type_revision.c.name,
            link_type_revision.c.source_table_id,
            link_type_revision.c.source_table_revision_id,
            link_type_revision.c.target_table_id,
            link_type_revision.c.target_table_revision_id,
            link_type_revision.c.forward_label,
            link_type_revision.c.reverse_label,
            link_type_revision.c.source_cardinality,
            link_type_revision.c.target_cardinality,
            link_type_revision.c.description,
        ).select_from(source)

    @staticmethod
    def _record_link_statement() -> sa.Select[Any]:
        return sa.select(
            record_link.c.id.label("identity_id"),
            *_revision_columns(record_link_revision, RECORD_LINK_AGGREGATE_TYPE),
            record_link_revision.c.link_type_id,
            record_link_revision.c.link_type_revision_id,
            record_link_revision.c.source_record_id,
            record_link_revision.c.source_record_revision_id,
            record_link_revision.c.target_record_id,
            record_link_revision.c.target_record_revision_id,
            record_link_revision.c.active,
            record_link_revision.c.note,
        ).select_from(_current_join(record_link, record_link_revision))

    @staticmethod
    def _link_type_snapshot(row: Any) -> LinkTypeSnapshot:
        return LinkTypeSnapshot(
            row["identity_id"],
            ConfigRevision(_record(row, LINK_TYPE_AGGREGATE_TYPE), _link_type_content(row)),
        )

    @staticmethod
    def _record_link_snapshot(row: Any) -> RecordLinkSnapshot:
        return RecordLinkSnapshot(
            row["identity_id"],
            ConfigRevision(_record(row, RECORD_LINK_AGGREGATE_TYPE), _record_link_content(row)),
        )

    def list_link_types(
        self, *, context: SecurityContext, decision: AuthorizationDecision
    ) -> tuple[LinkTypeSnapshot, ...]:
        with self._transaction(context, decision) as session:
            rows = session.execute(
                self._link_type_statement(current=True).order_by(
                    link_type_revision.c.name.asc(), link_type.c.id.asc()
                )
            ).mappings()
            return tuple(self._link_type_snapshot(row) for row in rows)

    def get_link_type(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        link_type_id: UUID,
    ) -> LinkTypeSnapshot:
        with self._transaction(context, decision) as session:
            row = (
                session.execute(
                    self._link_type_statement(current=True).where(link_type.c.id == link_type_id)
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise ConfigurableCatalogNotFound("Catalog Link Type was not found")
            return self._link_type_snapshot(row)

    def get_link_type_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        link_type_id: UUID,
        revision_id: UUID,
    ) -> ConfigRevision[LinkTypeContent]:
        with self._transaction(context, decision) as session:
            row = (
                session.execute(
                    self._link_type_statement(current=False).where(
                        link_type.c.id == link_type_id,
                        link_type_revision.c.id == revision_id,
                    )
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise ConfigurableCatalogNotFound("Catalog Link Type revision was not found")
            return ConfigRevision(_record(row, LINK_TYPE_AGGREGATE_TYPE), _link_type_content(row))

    def get_record_link(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        record_link_id: UUID,
    ) -> RecordLinkSnapshot:
        with self._transaction(context, decision) as session:
            row = (
                session.execute(
                    self._record_link_statement().where(record_link.c.id == record_link_id)
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise ConfigurableCatalogNotFound("Catalog Record Link was not found")
            return self._record_link_snapshot(row)

    def list_record_links(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        record_id: UUID,
        record_revision_id: UUID | None,
        include_inactive: bool,
    ) -> tuple[RecordLinkSnapshot, ...]:
        statement = self._record_link_statement().where(
            sa.or_(
                record_link_revision.c.source_record_id == record_id,
                record_link_revision.c.target_record_id == record_id,
            )
        )
        if record_revision_id is not None:
            statement = statement.where(
                sa.or_(
                    sa.and_(
                        record_link_revision.c.source_record_id == record_id,
                        record_link_revision.c.source_record_revision_id == record_revision_id,
                    ),
                    sa.and_(
                        record_link_revision.c.target_record_id == record_id,
                        record_link_revision.c.target_record_revision_id == record_revision_id,
                    ),
                )
            )
        if not include_inactive:
            statement = statement.where(record_link_revision.c.active.is_(True))
        with self._transaction(context, decision) as session:
            rows = session.execute(
                statement.order_by(record_link_revision.c.created_at.asc(), record_link.c.id.asc())
            ).mappings()
            return tuple(self._record_link_snapshot(row) for row in rows)

    def active_link_conflicts(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        content: RecordLinkContent,
        link_type: LinkTypeContent,
        exclude_link_id: UUID | None = None,
    ) -> bool:
        base = self._record_link_statement().where(
            record_link_revision.c.active.is_(True),
            record_link_revision.c.link_type_id == content.link_type_id,
        )
        if exclude_link_id is not None:
            base = base.where(record_link.c.id != exclude_link_id)
        duplicate = base.where(
            record_link_revision.c.source_record_id == content.source_record_id,
            record_link_revision.c.source_record_revision_id == content.source_record_revision_id,
            record_link_revision.c.target_record_id == content.target_record_id,
            record_link_revision.c.target_record_revision_id == content.target_record_revision_id,
        )
        source = base.where(
            record_link_revision.c.source_record_id == content.source_record_id,
            record_link_revision.c.source_record_revision_id == content.source_record_revision_id,
        )
        target = base.where(
            record_link_revision.c.target_record_id == content.target_record_id,
            record_link_revision.c.target_record_revision_id == content.target_record_revision_id,
        )
        with self._transaction(context, decision) as session:
            if session.execute(duplicate.limit(1)).first() is not None:
                return True
            if (
                link_type.source_cardinality is LinkCardinality.ONE
                and session.execute(source.limit(1)).first() is not None
            ):
                return True
            return bool(
                link_type.target_cardinality is LinkCardinality.ONE
                and session.execute(target.limit(1)).first() is not None
            )

    def create_domain_binding(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        binding_id: UUID,
        record_id: UUID,
        record_revision_id: UUID,
        kind: DomainBindingKind,
        object_id: UUID,
        revision_id: UUID,
        classification: str,
    ) -> DomainRevisionBinding:
        values = {
            "id": binding_id,
            "organization_id": context.organization_id,
            "project_id": context.project_id,
            "classification": classification,
            "record_id": record_id,
            "record_revision_id": record_revision_id,
            "domain_kind": kind.value,
            "domain_object_id": object_id,
            "domain_revision_id": revision_id,
            "created_at": datetime.now(UTC),
            "created_by": context.principal.id,
            "request_id": context.request_id,
            "trace_id": context.trace_id,
        }
        with self._transaction(context, decision) as session:
            session.execute(sa.insert(domain_record_binding).values(**values))
        return _domain_binding(values)

    def get_domain_binding(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        record_id: UUID,
        record_revision_id: UUID,
    ) -> DomainRevisionBinding | None:
        with self._transaction(context, decision) as session:
            row = (
                session.execute(
                    sa.select(domain_record_binding).where(
                        domain_record_binding.c.record_id == record_id,
                        domain_record_binding.c.record_revision_id == record_revision_id,
                    )
                )
                .mappings()
                .one_or_none()
            )
            return None if row is None else _domain_binding(row)

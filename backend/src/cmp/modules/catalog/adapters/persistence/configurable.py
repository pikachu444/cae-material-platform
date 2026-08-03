"""PostgreSQL adapter for configurable Catalog schema revisions (T-49)."""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session

from cmp.modules.catalog.application.configurable import (
    ATTRIBUTE_AGGREGATE_TYPE,
    DATABASE_AGGREGATE_TYPE,
    LAYOUT_AGGREGATE_TYPE,
    PROFILE_AGGREGATE_TYPE,
    SUBSET_AGGREGATE_TYPE,
    TABLE_AGGREGATE_TYPE,
    AttributeSnapshot,
    ConfigRevision,
    ConfigurableCatalogRepository,
    DatabaseSnapshot,
    LayoutSnapshot,
    ProfileSnapshot,
    SubsetSnapshot,
    TableSnapshot,
)
from cmp.modules.catalog.domain.configurable import (
    AttributeDataType,
    AttributeDefinitionContent,
    CatalogDatabaseContent,
    CatalogProfileContent,
    CatalogTableContent,
    ConfigurableCatalogNotFound,
    LayoutContent,
    LayoutItem,
    SubsetContent,
    attribute_canonical,
    database_canonical,
    layout_canonical,
    profile_canonical,
    subset_canonical,
    table_canonical,
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


class RlsContext(Protocol):
    def bind_authorization(
        self,
        session: Session,
        context: SecurityContext,
        decision: AuthorizationDecision,
    ) -> None: ...


metadata = sa.MetaData()
_uuid = sa.Uuid()


def _identity_table(name: str, *extra: sa.Column[Any]) -> sa.Table:
    return sa.Table(
        name,
        metadata,
        sa.Column("id", _uuid, nullable=False),
        sa.Column("organization_id", _uuid, nullable=False),
        sa.Column("project_id", _uuid, nullable=False),
        sa.Column("classification", sa.String(length=64), nullable=False),
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
        sa.Column("classification", sa.String(length=64), nullable=False),
        sa.Column("revision_no", sa.BigInteger(), nullable=False),
        sa.Column("based_on_revision_id", _uuid, nullable=True),
        sa.Column("schema_id", sa.String(length=255), nullable=False),
        sa.Column("schema_version", sa.String(length=64), nullable=False),
        sa.Column("content_hash", sa.CHAR(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", _uuid, nullable=False),
        sa.Column("change_reason", sa.Text(), nullable=False),
        sa.Column("request_id", _uuid, nullable=False),
        sa.Column("trace_id", sa.String(length=255), nullable=False),
        *extra,
        schema="catalog",
    )


schema_table = _identity_table(
    "schema_table", sa.Column("table_key", sa.String(64), nullable=False)
)
schema_table_revision = _revision_table(
    "schema_table",
    sa.Column("table_key", sa.String(64), nullable=False),
    sa.Column("name", sa.String(200), nullable=False),
    sa.Column("description", sa.Text(), nullable=True),
)
database = _identity_table("database", sa.Column("database_key", sa.String(64), nullable=False))
database_revision = _revision_table(
    "database",
    sa.Column("database_key", sa.String(64), nullable=False),
    sa.Column("name", sa.String(200), nullable=False),
    sa.Column("description", sa.Text(), nullable=True),
)
profile = _identity_table("profile", sa.Column("profile_key", sa.String(64), nullable=False))
profile_revision = _revision_table(
    "profile",
    sa.Column("profile_key", sa.String(64), nullable=False),
    sa.Column("name", sa.String(200), nullable=False),
    sa.Column("description", sa.Text(), nullable=True),
    sa.Column("database_id", _uuid, nullable=False),
    sa.Column("database_revision_id", _uuid, nullable=False),
)
attribute_definition = _identity_table(
    "attribute_definition",
    sa.Column("table_id", _uuid, nullable=False),
    sa.Column("attribute_key", sa.String(64), nullable=False),
)
attribute_definition_revision = _revision_table(
    "attribute_definition",
    sa.Column("table_id", _uuid, nullable=False),
    sa.Column("table_revision_id", _uuid, nullable=False),
    sa.Column("attribute_key", sa.String(64), nullable=False),
    sa.Column("name", sa.String(200), nullable=False),
    sa.Column("data_type", sa.String(32), nullable=False),
    sa.Column("required", sa.Boolean(), nullable=False),
    sa.Column("quantity_semantics", sa.String(255), nullable=True),
    sa.Column("normalized_unit", sa.String(64), nullable=True),
    sa.Column("minimum_number", sa.Numeric(), nullable=True),
    sa.Column("maximum_number", sa.Numeric(), nullable=True),
    sa.Column("minimum_length", sa.Integer(), nullable=True),
    sa.Column("maximum_length", sa.Integer(), nullable=True),
    sa.Column("pattern", sa.String(500), nullable=True),
    sa.Column("allowed_values", postgresql.ARRAY(sa.String(255)), nullable=False),
    sa.Column("reference_table_id", _uuid, nullable=True),
    sa.Column("help_text", sa.Text(), nullable=True),
)
layout = _identity_table("layout", sa.Column("table_id", _uuid, nullable=False))
layout_revision = _revision_table(
    "layout",
    sa.Column("table_id", _uuid, nullable=False),
    sa.Column("table_revision_id", _uuid, nullable=False),
    sa.Column("name", sa.String(200), nullable=False),
    sa.Column("description", sa.Text(), nullable=True),
)
layout_item = sa.Table(
    "layout_item",
    metadata,
    sa.Column("organization_id", _uuid, nullable=False),
    sa.Column("project_id", _uuid, nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("layout_id", _uuid, nullable=False),
    sa.Column("layout_revision_id", _uuid, nullable=False),
    sa.Column("ordinal", sa.Integer(), nullable=False),
    sa.Column("attribute_definition_id", _uuid, nullable=False),
    sa.Column("attribute_definition_revision_id", _uuid, nullable=False),
    sa.Column("section", sa.String(100), nullable=False),
    schema="catalog",
)
subset = _identity_table("subset", sa.Column("table_id", _uuid, nullable=False))
subset_revision = _revision_table(
    "subset",
    sa.Column("table_id", _uuid, nullable=False),
    sa.Column("table_revision_id", _uuid, nullable=False),
    sa.Column("name", sa.String(200), nullable=False),
    sa.Column("description", sa.Text(), nullable=True),
    sa.Column("filter_definition", sa.Text(), nullable=False),
)
folder_identity = _identity_table("folder", sa.Column("table_id", _uuid, nullable=False))
record_identity = _identity_table("catalog_record", sa.Column("table_id", _uuid, nullable=False))
link_type_identity = _identity_table("link_type")

_PUBLISHABLE_IDENTITIES = {
    "catalog.database": database,
    "catalog.profile": profile,
    "catalog.configurable_table": schema_table,
    "catalog.attribute_definition": attribute_definition,
    "catalog.layout": layout,
    "catalog.subset": subset,
    "catalog.folder": folder_identity,
    "catalog.configurable_record": record_identity,
    "catalog.link_type": link_type_identity,
}


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


def _table_content(row: Any) -> CatalogTableContent:
    return CatalogTableContent(row["table_key"], row["name"], row["description"])


def _database_content(row: Any) -> CatalogDatabaseContent:
    return CatalogDatabaseContent(row["database_key"], row["name"], row["description"])


def _profile_content(row: Any) -> CatalogProfileContent:
    return CatalogProfileContent(
        database_id=row["database_id"],
        database_revision_id=row["database_revision_id"],
        key=row["profile_key"],
        name=row["name"],
        description=row["description"],
    )


def _attribute_content(row: Any) -> AttributeDefinitionContent:
    return AttributeDefinitionContent(
        table_id=row["table_id"],
        table_revision_id=row["table_revision_id"],
        key=row["attribute_key"],
        name=row["name"],
        data_type=AttributeDataType(row["data_type"]),
        required=bool(row["required"]),
        quantity_semantics=row["quantity_semantics"],
        normalized_unit=row["normalized_unit"],
        minimum_number=(
            float(row["minimum_number"]) if row["minimum_number"] is not None else None
        ),
        maximum_number=(
            float(row["maximum_number"]) if row["maximum_number"] is not None else None
        ),
        minimum_length=row["minimum_length"],
        maximum_length=row["maximum_length"],
        pattern=row["pattern"],
        allowed_values=tuple(row["allowed_values"]),
        reference_table_id=row["reference_table_id"],
        help_text=row["help_text"],
    )


def _layout_content(row: Any, items: tuple[LayoutItem, ...]) -> LayoutContent:
    return LayoutContent(
        table_id=row["table_id"],
        table_revision_id=row["table_revision_id"],
        name=row["name"],
        description=row["description"],
        items=items,
    )


def _subset_content(row: Any) -> SubsetContent:
    parsed = json.loads(row["filter_definition"])
    if not isinstance(parsed, dict):
        raise ValueError("persisted Subset filter definition must be a JSON object")
    return SubsetContent(
        table_id=row["table_id"],
        table_revision_id=row["table_revision_id"],
        name=row["name"],
        description=row["description"],
        filter_definition=parsed,
    )


def _table_values(content: CatalogTableContent) -> dict[str, Any]:
    return {"table_key": content.key, "name": content.name, "description": content.description}


def _database_values(content: CatalogDatabaseContent) -> dict[str, Any]:
    return {"database_key": content.key, "name": content.name, "description": content.description}


def _profile_values(content: CatalogProfileContent) -> dict[str, Any]:
    return {
        "profile_key": content.key,
        "name": content.name,
        "description": content.description,
        "database_id": content.database_id,
        "database_revision_id": content.database_revision_id,
    }


def _attribute_values(content: AttributeDefinitionContent) -> dict[str, Any]:
    return {
        "table_id": content.table_id,
        "table_revision_id": content.table_revision_id,
        "attribute_key": content.key,
        "name": content.name,
        "data_type": content.data_type.value,
        "required": content.required,
        "quantity_semantics": content.quantity_semantics,
        "normalized_unit": content.normalized_unit,
        "minimum_number": content.minimum_number,
        "maximum_number": content.maximum_number,
        "minimum_length": content.minimum_length,
        "maximum_length": content.maximum_length,
        "pattern": content.pattern,
        "allowed_values": list(content.allowed_values),
        "reference_table_id": content.reference_table_id,
        "help_text": content.help_text,
    }


def _layout_values(content: LayoutContent) -> dict[str, Any]:
    return {
        "table_id": content.table_id,
        "table_revision_id": content.table_revision_id,
        "name": content.name,
        "description": content.description,
    }


def _subset_values(content: SubsetContent) -> dict[str, Any]:
    return {
        "table_id": content.table_id,
        "table_revision_id": content.table_revision_id,
        "name": content.name,
        "description": content.description,
        "filter_definition": json.dumps(
            content.filter_definition or {}, sort_keys=True, separators=(",", ":")
        ),
    }


def _write_layout_items(session: Session, draft: Any) -> None:
    content = draft.content
    if not isinstance(content, LayoutContent):
        raise TypeError("Layout child writer requires LayoutContent")
    if not content.items:
        return
    session.execute(
        sa.insert(layout_item),
        [
            {
                "organization_id": draft.scope.organization_id,
                "project_id": draft.scope.project_id,
                "classification": draft.scope.classification,
                "layout_id": draft.aggregate_id,
                "layout_revision_id": draft.revision_id,
                "ordinal": item.ordinal,
                "attribute_definition_id": item.attribute_definition_id,
                "attribute_definition_revision_id": item.attribute_definition_revision_id,
                "section": item.section,
            }
            for item in content.items
        ],
    )


_TABLES = TypedRevisionTables(
    aggregate_type=TABLE_AGGREGATE_TYPE,
    identity_table=schema_table,
    revision_table=schema_table_revision,
    canonical_content=table_canonical,
    content_values=_table_values,
    identity_values=lambda content: {"table_key": content.key},
)
publication_marker = sa.Table(
    "publication_marker",
    metadata,
    sa.Column("organization_id", _uuid, nullable=False),
    sa.Column("project_id", _uuid, nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("aggregate_type", sa.String(128), nullable=False),
    sa.Column("aggregate_id", _uuid, nullable=False),
    sa.Column("revision_id", _uuid, nullable=False),
    sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("published_by", _uuid, nullable=False),
    schema="catalog",
)
table_profile_placement = sa.Table(
    "table_profile_placement",
    metadata,
    sa.Column("organization_id", _uuid, nullable=False),
    sa.Column("project_id", _uuid, nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("table_id", _uuid, nullable=False),
    sa.Column("table_revision_id", _uuid, nullable=False),
    sa.Column("profile_id", _uuid, nullable=False),
    sa.Column("profile_revision_id", _uuid, nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("created_by", _uuid, nullable=False),
    schema="catalog",
)
_DATABASES = TypedRevisionTables(
    aggregate_type=DATABASE_AGGREGATE_TYPE,
    identity_table=database,
    revision_table=database_revision,
    canonical_content=database_canonical,
    content_values=_database_values,
    identity_values=lambda content: {"database_key": content.key},
)
_PROFILES = TypedRevisionTables(
    aggregate_type=PROFILE_AGGREGATE_TYPE,
    identity_table=profile,
    revision_table=profile_revision,
    canonical_content=profile_canonical,
    content_values=_profile_values,
    identity_values=lambda content: {"profile_key": content.key},
)
_ATTRIBUTES = TypedRevisionTables(
    aggregate_type=ATTRIBUTE_AGGREGATE_TYPE,
    identity_table=attribute_definition,
    revision_table=attribute_definition_revision,
    canonical_content=attribute_canonical,
    content_values=_attribute_values,
    identity_values=lambda content: {
        "table_id": content.table_id,
        "attribute_key": content.key,
    },
)
_LAYOUTS = TypedRevisionTables(
    aggregate_type=LAYOUT_AGGREGATE_TYPE,
    identity_table=layout,
    revision_table=layout_revision,
    canonical_content=layout_canonical,
    content_values=_layout_values,
    identity_values=lambda content: {"table_id": content.table_id},
    revision_content_writer=_write_layout_items,
)
_SUBSETS = TypedRevisionTables(
    aggregate_type=SUBSET_AGGREGATE_TYPE,
    identity_table=subset,
    revision_table=subset_revision,
    canonical_content=subset_canonical,
    content_values=_subset_values,
    identity_values=lambda content: {"table_id": content.table_id},
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


class SqlAlchemyConfigurableCatalogRepository(ConfigurableCatalogRepository):
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

    def table_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[CatalogTableContent]:
        return self._store(context, decision, _TABLES)

    def database_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[CatalogDatabaseContent]:
        return self._store(context, decision, _DATABASES)

    def profile_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[CatalogProfileContent]:
        return self._store(context, decision, _PROFILES)

    def attribute_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[AttributeDefinitionContent]:
        return self._store(context, decision, _ATTRIBUTES)

    def layout_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[LayoutContent]:
        return self._store(context, decision, _LAYOUTS)

    def subset_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[SubsetContent]:
        return self._store(context, decision, _SUBSETS)

    @staticmethod
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

    @staticmethod
    def _table_statement() -> sa.Select[Any]:
        return sa.select(
            schema_table.c.id.label("identity_id"),
            *_revision_columns(schema_table_revision, TABLE_AGGREGATE_TYPE),
            schema_table_revision.c.table_key,
            schema_table_revision.c.name,
            schema_table_revision.c.description,
        ).select_from(
            SqlAlchemyConfigurableCatalogRepository._current_join(
                schema_table, schema_table_revision
            )
        )

    @staticmethod
    def _database_statement() -> sa.Select[Any]:
        return sa.select(
            database.c.id.label("identity_id"),
            *_revision_columns(database_revision, DATABASE_AGGREGATE_TYPE),
            database_revision.c.database_key,
            database_revision.c.name,
            database_revision.c.description,
        ).select_from(
            SqlAlchemyConfigurableCatalogRepository._current_join(database, database_revision)
        )

    @staticmethod
    def _profile_statement() -> sa.Select[Any]:
        return sa.select(
            profile.c.id.label("identity_id"),
            *_revision_columns(profile_revision, PROFILE_AGGREGATE_TYPE),
            profile_revision.c.profile_key,
            profile_revision.c.name,
            profile_revision.c.description,
            profile_revision.c.database_id,
            profile_revision.c.database_revision_id,
        ).select_from(
            SqlAlchemyConfigurableCatalogRepository._current_join(profile, profile_revision)
        )

    @staticmethod
    def _attribute_statement() -> sa.Select[Any]:
        return sa.select(
            attribute_definition.c.id.label("identity_id"),
            attribute_definition.c.table_id.label("identity_table_id"),
            *_revision_columns(attribute_definition_revision, ATTRIBUTE_AGGREGATE_TYPE),
            *(
                column
                for column in attribute_definition_revision.c
                if column.name
                not in {
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
            ),
        ).select_from(
            SqlAlchemyConfigurableCatalogRepository._current_join(
                attribute_definition, attribute_definition_revision
            )
        )

    @staticmethod
    def _table_snapshot(row: Any) -> TableSnapshot:
        return TableSnapshot(
            row["identity_id"],
            ConfigRevision(_record(row, TABLE_AGGREGATE_TYPE), _table_content(row)),
        )

    @staticmethod
    def _database_snapshot(row: Any) -> DatabaseSnapshot:
        return DatabaseSnapshot(
            row["identity_id"],
            ConfigRevision(_record(row, DATABASE_AGGREGATE_TYPE), _database_content(row)),
        )

    @staticmethod
    def _profile_snapshot(row: Any) -> ProfileSnapshot:
        return ProfileSnapshot(
            row["identity_id"],
            ConfigRevision(_record(row, PROFILE_AGGREGATE_TYPE), _profile_content(row)),
        )

    @staticmethod
    def _attribute_snapshot(row: Any) -> AttributeSnapshot:
        return AttributeSnapshot(
            row["identity_id"],
            row["identity_table_id"],
            ConfigRevision(_record(row, ATTRIBUTE_AGGREGATE_TYPE), _attribute_content(row)),
        )

    def list_databases(
        self, *, context: SecurityContext, decision: AuthorizationDecision
    ) -> tuple[DatabaseSnapshot, ...]:
        with self._transaction(context, decision) as session:
            rows = session.execute(
                self._database_statement().order_by(database_revision.c.name.asc())
            ).mappings()
            return tuple(self._database_snapshot(row) for row in rows)

    def get_database(
        self, *, context: SecurityContext, decision: AuthorizationDecision, database_id: UUID
    ) -> DatabaseSnapshot:
        with self._transaction(context, decision) as session:
            row = (
                session.execute(self._database_statement().where(database.c.id == database_id))
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise ConfigurableCatalogNotFound("Catalog Database was not found")
            return self._database_snapshot(row)

    def get_database_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        database_id: UUID,
        revision_id: UUID,
    ) -> ConfigRevision[CatalogDatabaseContent]:
        with self._transaction(context, decision) as session:
            row = (
                session.execute(
                    sa.select(
                        *_revision_columns(database_revision, DATABASE_AGGREGATE_TYPE),
                        database_revision.c.database_key,
                        database_revision.c.name,
                        database_revision.c.description,
                    ).where(
                        database_revision.c.aggregate_id == database_id,
                        database_revision.c.id == revision_id,
                    )
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise ConfigurableCatalogNotFound("Catalog Database revision was not found")
            return ConfigRevision(_record(row, DATABASE_AGGREGATE_TYPE), _database_content(row))

    def list_profiles(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        database_id: UUID | None = None,
    ) -> tuple[ProfileSnapshot, ...]:
        statement = self._profile_statement().order_by(profile_revision.c.name.asc())
        if database_id is not None:
            statement = statement.where(profile_revision.c.database_id == database_id)
        with self._transaction(context, decision) as session:
            rows = session.execute(statement).mappings()
            return tuple(self._profile_snapshot(row) for row in rows)

    def get_profile(
        self, *, context: SecurityContext, decision: AuthorizationDecision, profile_id: UUID
    ) -> ProfileSnapshot:
        with self._transaction(context, decision) as session:
            row = (
                session.execute(self._profile_statement().where(profile.c.id == profile_id))
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise ConfigurableCatalogNotFound("Catalog Profile was not found")
            return self._profile_snapshot(row)

    def list_tables(
        self, *, context: SecurityContext, decision: AuthorizationDecision
    ) -> tuple[TableSnapshot, ...]:
        with self._transaction(context, decision) as session:
            rows = session.execute(
                self._table_statement().order_by(schema_table_revision.c.name.asc())
            ).mappings()
            return tuple(self._table_snapshot(row) for row in rows)

    def get_table(
        self, *, context: SecurityContext, decision: AuthorizationDecision, table_id: UUID
    ) -> TableSnapshot:
        with self._transaction(context, decision) as session:
            row = (
                session.execute(self._table_statement().where(schema_table.c.id == table_id))
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise ConfigurableCatalogNotFound("Catalog Table was not found")
            return self._table_snapshot(row)

    def get_table_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        table_id: UUID,
        revision_id: UUID,
    ) -> ConfigRevision[CatalogTableContent]:
        with self._transaction(context, decision) as session:
            row = (
                session.execute(
                    sa.select(
                        *_revision_columns(schema_table_revision, TABLE_AGGREGATE_TYPE),
                        schema_table_revision.c.table_key,
                        schema_table_revision.c.name,
                        schema_table_revision.c.description,
                    ).where(
                        schema_table_revision.c.aggregate_id == table_id,
                        schema_table_revision.c.id == revision_id,
                    )
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise ConfigurableCatalogNotFound("Catalog Table revision was not found")
            return ConfigRevision(_record(row, TABLE_AGGREGATE_TYPE), _table_content(row))

    def get_attribute(
        self, *, context: SecurityContext, decision: AuthorizationDecision, attribute_id: UUID
    ) -> AttributeSnapshot:
        with self._transaction(context, decision) as session:
            row = (
                session.execute(
                    self._attribute_statement().where(attribute_definition.c.id == attribute_id)
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise ConfigurableCatalogNotFound("Attribute Definition was not found")
            return self._attribute_snapshot(row)

    def get_attribute_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        attribute_id: UUID,
        revision_id: UUID,
    ) -> ConfigRevision[AttributeDefinitionContent]:
        with self._transaction(context, decision) as session:
            statement = sa.select(
                *_revision_columns(attribute_definition_revision, ATTRIBUTE_AGGREGATE_TYPE),
                *(
                    column
                    for column in attribute_definition_revision.c
                    if column.name
                    not in {
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
                ),
            ).where(
                attribute_definition_revision.c.aggregate_id == attribute_id,
                attribute_definition_revision.c.id == revision_id,
            )
            row = session.execute(statement).mappings().one_or_none()
            if row is None:
                raise ConfigurableCatalogNotFound("Attribute Definition revision was not found")
            return ConfigRevision(_record(row, ATTRIBUTE_AGGREGATE_TYPE), _attribute_content(row))

    def find_attribute_by_key(
        self, *, context: SecurityContext, decision: AuthorizationDecision, table_id: UUID, key: str
    ) -> AttributeSnapshot | None:
        with self._transaction(context, decision) as session:
            row = (
                session.execute(
                    self._attribute_statement().where(
                        attribute_definition.c.table_id == table_id,
                        attribute_definition.c.attribute_key == key,
                    )
                )
                .mappings()
                .one_or_none()
            )
            return self._attribute_snapshot(row) if row is not None else None

    def list_attributes(
        self, *, context: SecurityContext, decision: AuthorizationDecision, table_id: UUID
    ) -> tuple[AttributeSnapshot, ...]:
        with self._transaction(context, decision) as session:
            rows = session.execute(
                self._attribute_statement()
                .where(attribute_definition.c.table_id == table_id)
                .order_by(attribute_definition.c.attribute_key.asc())
            ).mappings()
            return tuple(self._attribute_snapshot(row) for row in rows)

    @staticmethod
    def _layout_items(session: Session, revision_id: UUID) -> tuple[LayoutItem, ...]:
        rows = session.execute(
            sa.select(layout_item)
            .where(layout_item.c.layout_revision_id == revision_id)
            .order_by(layout_item.c.ordinal.asc())
        ).mappings()
        return tuple(
            LayoutItem(
                row["attribute_definition_id"],
                row["attribute_definition_revision_id"],
                row["section"],
                row["ordinal"],
            )
            for row in rows
        )

    def list_layouts(
        self, *, context: SecurityContext, decision: AuthorizationDecision, table_id: UUID
    ) -> tuple[LayoutSnapshot, ...]:
        statement = (
            sa.select(
                layout.c.id.label("identity_id"),
                layout.c.table_id.label("identity_table_id"),
                *_revision_columns(layout_revision, LAYOUT_AGGREGATE_TYPE),
                layout_revision.c.table_id,
                layout_revision.c.table_revision_id,
                layout_revision.c.name,
                layout_revision.c.description,
            )
            .select_from(self._current_join(layout, layout_revision))
            .where(layout.c.table_id == table_id)
            .order_by(layout_revision.c.name.asc())
        )
        with self._transaction(context, decision) as session:
            rows = session.execute(statement).mappings().all()
            return tuple(
                LayoutSnapshot(
                    row["identity_id"],
                    row["identity_table_id"],
                    ConfigRevision(
                        _record(row, LAYOUT_AGGREGATE_TYPE),
                        _layout_content(row, self._layout_items(session, row["id"])),
                    ),
                )
                for row in rows
            )

    def get_layout(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        layout_id: UUID,
    ) -> LayoutSnapshot:
        statement = (
            sa.select(
                layout.c.id.label("identity_id"),
                layout.c.table_id.label("identity_table_id"),
                *_revision_columns(layout_revision, LAYOUT_AGGREGATE_TYPE),
                layout_revision.c.table_id,
                layout_revision.c.table_revision_id,
                layout_revision.c.name,
                layout_revision.c.description,
            )
            .select_from(self._current_join(layout, layout_revision))
            .where(layout.c.id == layout_id)
        )
        with self._transaction(context, decision) as session:
            row = session.execute(statement).mappings().one_or_none()
            if row is None:
                raise ConfigurableCatalogNotFound("Catalog Layout was not found")
            return LayoutSnapshot(
                row["identity_id"],
                row["identity_table_id"],
                ConfigRevision(
                    _record(row, LAYOUT_AGGREGATE_TYPE),
                    _layout_content(row, self._layout_items(session, row["id"])),
                ),
            )

    def list_subsets(
        self, *, context: SecurityContext, decision: AuthorizationDecision, table_id: UUID
    ) -> tuple[SubsetSnapshot, ...]:
        statement = (
            sa.select(
                subset.c.id.label("identity_id"),
                subset.c.table_id.label("identity_table_id"),
                *_revision_columns(subset_revision, SUBSET_AGGREGATE_TYPE),
                subset_revision.c.table_id,
                subset_revision.c.table_revision_id,
                subset_revision.c.name,
                subset_revision.c.description,
                subset_revision.c.filter_definition,
            )
            .select_from(self._current_join(subset, subset_revision))
            .where(subset.c.table_id == table_id)
            .order_by(subset_revision.c.name.asc())
        )
        with self._transaction(context, decision) as session:
            rows = session.execute(statement).mappings()
            return tuple(
                SubsetSnapshot(
                    row["identity_id"],
                    row["identity_table_id"],
                    ConfigRevision(_record(row, SUBSET_AGGREGATE_TYPE), _subset_content(row)),
                )
                for row in rows
            )

    def get_subset(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        subset_id: UUID,
    ) -> SubsetSnapshot:
        statement = (
            sa.select(
                subset.c.id.label("identity_id"),
                subset.c.table_id.label("identity_table_id"),
                *_revision_columns(subset_revision, SUBSET_AGGREGATE_TYPE),
                subset_revision.c.table_id,
                subset_revision.c.table_revision_id,
                subset_revision.c.name,
                subset_revision.c.description,
                subset_revision.c.filter_definition,
            )
            .select_from(self._current_join(subset, subset_revision))
            .where(subset.c.id == subset_id)
        )
        with self._transaction(context, decision) as session:
            row = session.execute(statement).mappings().one_or_none()
            if row is None:
                raise ConfigurableCatalogNotFound("Catalog Subset was not found")
            return SubsetSnapshot(
                row["identity_id"],
                row["identity_table_id"],
                ConfigRevision(_record(row, SUBSET_AGGREGATE_TYPE), _subset_content(row)),
            )

    def is_current_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        aggregate_type: str,
        aggregate_id: UUID,
        revision_id: UUID,
    ) -> bool:
        identity = _PUBLISHABLE_IDENTITIES.get(aggregate_type)
        if identity is None:
            return False
        with self._transaction(context, decision) as session:
            return (
                session.execute(
                    sa.select(identity.c.id).where(
                        identity.c.organization_id == context.organization_id,
                        identity.c.project_id == context.project_id,
                        identity.c.id == aggregate_id,
                        identity.c.current_revision_id == revision_id,
                    )
                ).first()
                is not None
            )

    def place_table(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        table_id: UUID,
        table_revision_id: UUID,
        profile_id: UUID,
        profile_revision_id: UUID,
    ) -> None:
        with self._transaction(context, decision) as session:
            classification = session.scalar(
                sa.select(schema_table.c.classification).where(
                    schema_table.c.organization_id == context.organization_id,
                    schema_table.c.project_id == context.project_id,
                    schema_table.c.id == table_id,
                    schema_table.c.current_revision_id == table_revision_id,
                )
            )
            if classification is None:
                raise ConfigurableCatalogNotFound("Catalog Table revision was not found")
            session.execute(
                postgresql.insert(table_profile_placement)
                .values(
                    organization_id=context.organization_id,
                    project_id=context.project_id,
                    classification=classification,
                    table_id=table_id,
                    table_revision_id=table_revision_id,
                    profile_id=profile_id,
                    profile_revision_id=profile_revision_id,
                    created_at=datetime.now(UTC),
                    created_by=context.principal.id,
                )
                .on_conflict_do_nothing()
            )

    def publish_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        aggregate_type: str,
        aggregate_id: UUID,
        revision_id: UUID,
        published_by: UUID,
    ) -> None:
        identity = _PUBLISHABLE_IDENTITIES.get(aggregate_type)
        if identity is None:
            raise ConfigurableCatalogNotFound("Catalog revision was not found")
        with self._transaction(context, decision) as session:
            classification = session.scalar(
                sa.select(identity.c.classification).where(
                    identity.c.organization_id == context.organization_id,
                    identity.c.project_id == context.project_id,
                    identity.c.id == aggregate_id,
                    identity.c.current_revision_id == revision_id,
                )
            )
            if classification is None:
                raise ConfigurableCatalogNotFound("Catalog revision was not found")
            session.execute(
                postgresql.insert(publication_marker)
                .values(
                    organization_id=context.organization_id,
                    project_id=context.project_id,
                    classification=classification,
                    aggregate_type=aggregate_type,
                    aggregate_id=aggregate_id,
                    revision_id=revision_id,
                    published_at=datetime.now(UTC),
                    published_by=published_by,
                )
                .on_conflict_do_nothing()
            )

    def is_published(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        aggregate_type: str,
        aggregate_id: UUID,
        revision_id: UUID,
    ) -> bool:
        """Publication survives workers and restarts because it is an append-only row."""

        with self._transaction(context, decision) as session:
            return (
                session.execute(
                    sa.select(publication_marker.c.revision_id).where(
                        publication_marker.c.organization_id == context.organization_id,
                        publication_marker.c.project_id == context.project_id,
                        publication_marker.c.aggregate_type == aggregate_type,
                        publication_marker.c.aggregate_id == aggregate_id,
                        publication_marker.c.revision_id == revision_id,
                    )
                ).first()
                is not None
            )

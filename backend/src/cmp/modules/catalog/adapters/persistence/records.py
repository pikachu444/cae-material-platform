"""PostgreSQL persistence for configurable Catalog folders and records (T-50)."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from decimal import Decimal
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session

from cmp.modules.catalog.adapters.persistence.configurable import RlsContext
from cmp.modules.catalog.application.configurable import ConfigRevision
from cmp.modules.catalog.application.records import (
    FOLDER_AGGREGATE_TYPE,
    RECORD_AGGREGATE_TYPE,
    CatalogRecordRepository,
    FolderSnapshot,
    RecordFacetBucket,
    RecordSearchResult,
    RecordSnapshot,
)
from cmp.modules.catalog.domain.configurable import (
    AttributeDataType,
    ConfigurableCatalogNotFound,
)
from cmp.modules.catalog.domain.records import (
    CatalogFolderContent,
    CatalogRecordContent,
    CatalogRecordQuery,
    CatalogRecordValue,
    folder_canonical,
    record_canonical,
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


folder = _identity_table("folder", sa.Column("table_id", _uuid, nullable=False))
folder_revision = _revision_table(
    "folder",
    sa.Column("table_id", _uuid, nullable=False),
    sa.Column("table_revision_id", _uuid, nullable=False),
    sa.Column("name", sa.String(200), nullable=False),
    sa.Column("description", sa.Text(), nullable=True),
    sa.Column("parent_folder_id", _uuid, nullable=True),
    sa.Column("parent_folder_revision_id", _uuid, nullable=True),
)
catalog_record = _identity_table("catalog_record", sa.Column("table_id", _uuid, nullable=False))
catalog_record_revision = _revision_table(
    "catalog_record",
    sa.Column("table_id", _uuid, nullable=False),
    sa.Column("table_revision_id", _uuid, nullable=False),
    sa.Column("name", sa.String(200), nullable=False),
    sa.Column("external_key", sa.String(255), nullable=True),
    sa.Column("description", sa.Text(), nullable=True),
    sa.Column("folder_id", _uuid, nullable=True),
    sa.Column("folder_revision_id", _uuid, nullable=True),
)


def _value_table(name: str, *columns: sa.Column[Any]) -> sa.Table:
    return sa.Table(
        name,
        metadata,
        sa.Column("organization_id", _uuid, nullable=False),
        sa.Column("project_id", _uuid, nullable=False),
        sa.Column("classification", sa.String(64), nullable=False),
        sa.Column("record_id", _uuid, nullable=False),
        sa.Column("record_revision_id", _uuid, nullable=False),
        sa.Column("attribute_definition_id", _uuid, nullable=False),
        sa.Column("attribute_definition_revision_id", _uuid, nullable=False),
        *columns,
        schema="catalog",
    )


record_number_value = _value_table(
    "record_number_value",
    sa.Column("original_value", sa.Numeric(), nullable=False),
    sa.Column("original_unit_string", sa.String(64), nullable=False),
    sa.Column("normalized_value", sa.Numeric(), nullable=False),
    sa.Column("normalized_unit", sa.String(64), nullable=False),
    sa.Column("quantity_semantics", sa.String(255), nullable=False),
)
record_integer_value = _value_table(
    "record_integer_value", sa.Column("value", sa.BigInteger(), nullable=False)
)
record_text_value = _value_table("record_text_value", sa.Column("value", sa.Text(), nullable=False))
record_boolean_value = _value_table(
    "record_boolean_value", sa.Column("value", sa.Boolean(), nullable=False)
)
record_date_value = _value_table("record_date_value", sa.Column("value", sa.Date(), nullable=False))
record_discrete_value = _value_table(
    "record_discrete_value", sa.Column("value", sa.String(255), nullable=False)
)
record_file_value = _value_table(
    "record_file_value",
    sa.Column("artifact_id", _uuid, nullable=False),
    sa.Column("artifact_sha256", sa.CHAR(64), nullable=False),
)
record_curve_value = _value_table(
    "record_curve_value",
    sa.Column("artifact_id", _uuid, nullable=False),
    sa.Column("artifact_sha256", sa.CHAR(64), nullable=False),
)
record_reference_value = _value_table(
    "record_reference_value",
    sa.Column("target_record_id", _uuid, nullable=False),
    sa.Column("target_record_revision_id", _uuid, nullable=False),
)

_SCALAR_TABLES: dict[AttributeDataType, sa.Table] = {
    AttributeDataType.INTEGER: record_integer_value,
    AttributeDataType.TEXT: record_text_value,
    AttributeDataType.BOOLEAN: record_boolean_value,
    AttributeDataType.DATE: record_date_value,
    AttributeDataType.DISCRETE: record_discrete_value,
}
_ARTIFACT_TABLES: dict[AttributeDataType, sa.Table] = {
    AttributeDataType.FILE: record_file_value,
    AttributeDataType.CURVE: record_curve_value,
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


def _folder_content(row: Any) -> CatalogFolderContent:
    return CatalogFolderContent(
        table_id=row["table_id"],
        table_revision_id=row["table_revision_id"],
        name=row["name"],
        description=row["description"],
        parent_folder_id=row["parent_folder_id"],
        parent_folder_revision_id=row["parent_folder_revision_id"],
    )


def _record_content(row: Any, values: tuple[CatalogRecordValue, ...]) -> CatalogRecordContent:
    return CatalogRecordContent(
        table_id=row["table_id"],
        table_revision_id=row["table_revision_id"],
        name=row["name"],
        external_key=row["external_key"],
        description=row["description"],
        folder_id=row["folder_id"],
        folder_revision_id=row["folder_revision_id"],
        values=values,
    )


def _folder_values(content: CatalogFolderContent) -> dict[str, Any]:
    return {
        "table_id": content.table_id,
        "table_revision_id": content.table_revision_id,
        "name": content.name,
        "description": content.description,
        "parent_folder_id": content.parent_folder_id,
        "parent_folder_revision_id": content.parent_folder_revision_id,
    }


def _record_values(content: CatalogRecordContent) -> dict[str, Any]:
    return {
        "table_id": content.table_id,
        "table_revision_id": content.table_revision_id,
        "name": content.name,
        "external_key": content.external_key,
        "description": content.description,
        "folder_id": content.folder_id,
        "folder_revision_id": content.folder_revision_id,
    }


def _base_child_values(draft: Any, value: CatalogRecordValue) -> dict[str, Any]:
    return {
        "organization_id": draft.scope.organization_id,
        "project_id": draft.scope.project_id,
        "classification": draft.scope.classification,
        "record_id": draft.aggregate_id,
        "record_revision_id": draft.revision_id,
        "attribute_definition_id": value.attribute_definition_id,
        "attribute_definition_revision_id": value.attribute_definition_revision_id,
    }


def _write_record_children(session: Session, draft: Any) -> None:
    content = draft.content
    if not isinstance(content, CatalogRecordContent):
        raise TypeError("Catalog Record child writer requires CatalogRecordContent")
    grouped: dict[sa.Table, list[dict[str, Any]]] = defaultdict(list)
    for value in content.values:
        encoded = _base_child_values(draft, value)
        if value.data_type is AttributeDataType.NUMBER:
            encoded.update(
                original_value=value.original_value,
                original_unit_string=value.original_unit_string,
                normalized_value=value.normalized_value,
                normalized_unit=value.normalized_unit,
                quantity_semantics=value.quantity_semantics,
            )
            grouped[record_number_value].append(encoded)
        elif value.data_type in _SCALAR_TABLES:
            encoded["value"] = value.value
            grouped[_SCALAR_TABLES[value.data_type]].append(encoded)
        elif value.data_type in _ARTIFACT_TABLES:
            encoded.update(artifact_id=value.artifact_id, artifact_sha256=value.artifact_sha256)
            grouped[_ARTIFACT_TABLES[value.data_type]].append(encoded)
        elif value.data_type is AttributeDataType.RECORD_REFERENCE:
            encoded.update(
                target_record_id=value.target_record_id,
                target_record_revision_id=value.target_record_revision_id,
            )
            grouped[record_reference_value].append(encoded)
        else:  # pragma: no cover - exhaustive enum guard
            raise TypeError(f"unsupported Catalog record value type: {value.data_type}")
    for table, rows in grouped.items():
        session.execute(sa.insert(table), rows)


_FOLDERS = TypedRevisionTables(
    aggregate_type=FOLDER_AGGREGATE_TYPE,
    identity_table=folder,
    revision_table=folder_revision,
    canonical_content=folder_canonical,
    content_values=_folder_values,
    identity_values=lambda content: {"table_id": content.table_id},
)
_RECORDS = TypedRevisionTables(
    aggregate_type=RECORD_AGGREGATE_TYPE,
    identity_table=catalog_record,
    revision_table=catalog_record_revision,
    canonical_content=record_canonical,
    content_values=_record_values,
    identity_values=lambda content: {"table_id": content.table_id},
    revision_content_writer=_write_record_children,
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


class SqlAlchemyCatalogRecordRepository(CatalogRecordRepository):
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

    def folder_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[CatalogFolderContent]:
        return self._store(context, decision, _FOLDERS)

    def record_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[CatalogRecordContent]:
        return self._store(context, decision, _RECORDS)

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
    def _folder_statement() -> sa.Select[Any]:
        return sa.select(
            folder.c.id.label("identity_id"),
            folder.c.table_id.label("identity_table_id"),
            *_revision_columns(folder_revision, FOLDER_AGGREGATE_TYPE),
            folder_revision.c.table_id,
            folder_revision.c.table_revision_id,
            folder_revision.c.name,
            folder_revision.c.description,
            folder_revision.c.parent_folder_id,
            folder_revision.c.parent_folder_revision_id,
        ).select_from(SqlAlchemyCatalogRecordRepository._current_join(folder, folder_revision))

    @staticmethod
    def _record_statement(*, current: bool) -> sa.Select[Any]:
        columns = (
            catalog_record.c.id.label("identity_id"),
            catalog_record.c.table_id.label("identity_table_id"),
            *_revision_columns(catalog_record_revision, RECORD_AGGREGATE_TYPE),
            catalog_record_revision.c.table_id,
            catalog_record_revision.c.table_revision_id,
            catalog_record_revision.c.name,
            catalog_record_revision.c.external_key,
            catalog_record_revision.c.description,
            catalog_record_revision.c.folder_id,
            catalog_record_revision.c.folder_revision_id,
        )
        if current:
            return sa.select(*columns).select_from(
                SqlAlchemyCatalogRecordRepository._current_join(
                    catalog_record, catalog_record_revision
                )
            )
        return sa.select(*columns).select_from(
            catalog_record.join(
                catalog_record_revision,
                sa.and_(
                    catalog_record_revision.c.aggregate_id == catalog_record.c.id,
                    catalog_record_revision.c.organization_id == catalog_record.c.organization_id,
                    catalog_record_revision.c.project_id == catalog_record.c.project_id,
                    catalog_record_revision.c.classification == catalog_record.c.classification,
                ),
            )
        )

    @staticmethod
    def _values_by_revision(
        session: Session, revision_ids: Sequence[UUID]
    ) -> dict[UUID, tuple[CatalogRecordValue, ...]]:
        grouped: dict[UUID, list[CatalogRecordValue]] = defaultdict(list)
        if not revision_ids:
            return {}
        number_rows = session.execute(
            sa.select(record_number_value).where(
                record_number_value.c.record_revision_id.in_(revision_ids)
            )
        ).mappings()
        for row in number_rows:
            grouped[row["record_revision_id"]].append(
                CatalogRecordValue(
                    row["attribute_definition_id"],
                    row["attribute_definition_revision_id"],
                    AttributeDataType.NUMBER,
                    original_value=Decimal(row["original_value"]),
                    original_unit_string=row["original_unit_string"],
                    normalized_value=Decimal(row["normalized_value"]),
                    normalized_unit=row["normalized_unit"],
                    quantity_semantics=row["quantity_semantics"],
                )
            )
        for data_type, table in _SCALAR_TABLES.items():
            rows = session.execute(
                sa.select(table).where(table.c.record_revision_id.in_(revision_ids))
            ).mappings()
            for row in rows:
                grouped[row["record_revision_id"]].append(
                    CatalogRecordValue(
                        row["attribute_definition_id"],
                        row["attribute_definition_revision_id"],
                        data_type,
                        value=row["value"],
                    )
                )
        for data_type, table in _ARTIFACT_TABLES.items():
            rows = session.execute(
                sa.select(table).where(table.c.record_revision_id.in_(revision_ids))
            ).mappings()
            for row in rows:
                grouped[row["record_revision_id"]].append(
                    CatalogRecordValue(
                        row["attribute_definition_id"],
                        row["attribute_definition_revision_id"],
                        data_type,
                        artifact_id=row["artifact_id"],
                        artifact_sha256=row["artifact_sha256"],
                    )
                )
        reference_rows = session.execute(
            sa.select(record_reference_value).where(
                record_reference_value.c.record_revision_id.in_(revision_ids)
            )
        ).mappings()
        for row in reference_rows:
            grouped[row["record_revision_id"]].append(
                CatalogRecordValue(
                    row["attribute_definition_id"],
                    row["attribute_definition_revision_id"],
                    AttributeDataType.RECORD_REFERENCE,
                    target_record_id=row["target_record_id"],
                    target_record_revision_id=row["target_record_revision_id"],
                )
            )
        return {
            revision_id: tuple(
                sorted(values, key=lambda value: str(value.attribute_definition_id))
            )
            for revision_id, values in grouped.items()
        }

    @staticmethod
    def _folder_snapshot(row: Any) -> FolderSnapshot:
        return FolderSnapshot(
            row["identity_id"],
            row["identity_table_id"],
            ConfigRevision(_record(row, FOLDER_AGGREGATE_TYPE), _folder_content(row)),
        )

    @staticmethod
    def _record_snapshot(
        row: Any, values: dict[UUID, tuple[CatalogRecordValue, ...]]
    ) -> RecordSnapshot:
        return RecordSnapshot(
            row["identity_id"],
            row["identity_table_id"],
            ConfigRevision(
                _record(row, RECORD_AGGREGATE_TYPE),
                _record_content(row, values.get(row["id"], ())),
            ),
        )

    def list_folders(
        self, *, context: SecurityContext, decision: AuthorizationDecision, table_id: UUID
    ) -> tuple[FolderSnapshot, ...]:
        with self._transaction(context, decision) as session:
            rows = session.execute(
                self._folder_statement()
                .where(folder.c.table_id == table_id)
                .order_by(folder_revision.c.name.asc(), folder.c.id.asc())
            ).mappings()
            return tuple(self._folder_snapshot(row) for row in rows)

    def get_folder(
        self, *, context: SecurityContext, decision: AuthorizationDecision, folder_id: UUID
    ) -> FolderSnapshot:
        with self._transaction(context, decision) as session:
            row = (
                session.execute(self._folder_statement().where(folder.c.id == folder_id))
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise ConfigurableCatalogNotFound("Catalog Folder was not found")
            return self._folder_snapshot(row)

    def get_folder_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        folder_id: UUID,
        revision_id: UUID,
    ) -> ConfigRevision[CatalogFolderContent]:
        statement = sa.select(
            *_revision_columns(folder_revision, FOLDER_AGGREGATE_TYPE),
            folder_revision.c.table_id,
            folder_revision.c.table_revision_id,
            folder_revision.c.name,
            folder_revision.c.description,
            folder_revision.c.parent_folder_id,
            folder_revision.c.parent_folder_revision_id,
        ).where(
            folder_revision.c.aggregate_id == folder_id,
            folder_revision.c.id == revision_id,
        )
        with self._transaction(context, decision) as session:
            row = session.execute(statement).mappings().one_or_none()
            if row is None:
                raise ConfigurableCatalogNotFound("Catalog Folder revision was not found")
            return ConfigRevision(_record(row, FOLDER_AGGREGATE_TYPE), _folder_content(row))

    def get_record(
        self, *, context: SecurityContext, decision: AuthorizationDecision, record_id: UUID
    ) -> RecordSnapshot:
        with self._transaction(context, decision) as session:
            row = (
                session.execute(
                    self._record_statement(current=True).where(catalog_record.c.id == record_id)
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise ConfigurableCatalogNotFound("Catalog Record was not found")
            values = self._values_by_revision(session, (row["id"],))
            return self._record_snapshot(row, values)

    def get_record_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        record_id: UUID,
        revision_id: UUID,
    ) -> ConfigRevision[CatalogRecordContent]:
        with self._transaction(context, decision) as session:
            row = (
                session.execute(
                    self._record_statement(current=False).where(
                        catalog_record.c.id == record_id,
                        catalog_record_revision.c.id == revision_id,
                    )
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise ConfigurableCatalogNotFound("Catalog Record revision was not found")
            values = self._values_by_revision(session, (revision_id,))
            return ConfigRevision(
                _record(row, RECORD_AGGREGATE_TYPE),
                _record_content(row, values.get(revision_id, ())),
            )

    def list_record_revisions(
        self, *, context: SecurityContext, decision: AuthorizationDecision, record_id: UUID
    ) -> tuple[ConfigRevision[CatalogRecordContent], ...]:
        with self._transaction(context, decision) as session:
            rows = (
                session.execute(
                    self._record_statement(current=False)
                    .where(catalog_record.c.id == record_id)
                    .order_by(catalog_record_revision.c.revision_no.asc())
                )
                .mappings()
                .all()
            )
            if not rows:
                raise ConfigurableCatalogNotFound("Catalog Record was not found")
            values = self._values_by_revision(session, tuple(row["id"] for row in rows))
            return tuple(
                ConfigRevision(
                    _record(row, RECORD_AGGREGATE_TYPE),
                    _record_content(row, values.get(row["id"], ())),
                )
                for row in rows
            )

    @staticmethod
    def _filtered_statement(query: CatalogRecordQuery) -> sa.Select[Any]:
        statement = SqlAlchemyCatalogRecordRepository._record_statement(current=True).where(
            catalog_record.c.table_id == query.table_id
        )
        if query.text is not None:
            pattern = f"%{query.text.lower()}%"
            statement = statement.where(
                sa.or_(
                    sa.func.lower(catalog_record_revision.c.name).like(pattern),
                    sa.func.lower(
                        sa.func.coalesce(catalog_record_revision.c.external_key, "")
                    ).like(pattern),
                    sa.func.lower(sa.func.coalesce(catalog_record_revision.c.description, "")).like(
                        pattern
                    ),
                    sa.exists(
                        sa.select(1).where(
                            record_text_value.c.organization_id
                            == catalog_record_revision.c.organization_id,
                            record_text_value.c.project_id
                            == catalog_record_revision.c.project_id,
                            record_text_value.c.record_revision_id
                            == catalog_record_revision.c.id,
                            sa.func.lower(record_text_value.c.value).like(pattern),
                        )
                    ),
                )
            )
        if query.folder_id is not None:
            statement = statement.where(catalog_record_revision.c.folder_id == query.folder_id)
        for discrete_filter in query.discrete_filters:
            statement = statement.where(
                sa.exists(
                    sa.select(1).where(
                        record_discrete_value.c.organization_id
                        == catalog_record_revision.c.organization_id,
                        record_discrete_value.c.project_id
                        == catalog_record_revision.c.project_id,
                        record_discrete_value.c.record_revision_id
                        == catalog_record_revision.c.id,
                        record_discrete_value.c.attribute_definition_id
                        == discrete_filter.attribute_definition_id,
                        record_discrete_value.c.value.in_(discrete_filter.values),
                    )
                )
            )
        for number_filter in query.number_filters:
            predicates: list[Any] = [
                record_number_value.c.organization_id
                == catalog_record_revision.c.organization_id,
                record_number_value.c.project_id == catalog_record_revision.c.project_id,
                record_number_value.c.record_revision_id == catalog_record_revision.c.id,
                record_number_value.c.attribute_definition_id
                == number_filter.attribute_definition_id,
            ]
            if number_filter.minimum is not None:
                predicates.append(
                    record_number_value.c.normalized_value >= number_filter.minimum
                )
            if number_filter.maximum is not None:
                predicates.append(
                    record_number_value.c.normalized_value <= number_filter.maximum
                )
            statement = statement.where(sa.exists(sa.select(1).where(*predicates)))
        return statement

    def search_records(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        query: CatalogRecordQuery,
    ) -> RecordSearchResult:
        base = self._filtered_statement(query)
        matched = (
            base.with_only_columns(
                catalog_record_revision.c.organization_id.label("organization_id"),
                catalog_record_revision.c.project_id.label("project_id"),
                catalog_record_revision.c.id.label("record_revision_id"),
            )
            .order_by(None)
            .subquery()
        )
        with self._transaction(context, decision) as session:
            total_count = int(session.scalar(sa.select(sa.func.count()).select_from(matched)) or 0)
            rows = (
                session.execute(
                    base.order_by(
                        catalog_record_revision.c.name.asc(), catalog_record.c.id.asc()
                    )
                    .offset(query.offset)
                    .limit(query.limit)
                )
                .mappings()
                .all()
            )
            values = self._values_by_revision(session, tuple(row["id"] for row in rows))
            facets: tuple[RecordFacetBucket, ...] = ()
            if query.facet_attribute_ids:
                facet_rows = session.execute(
                    sa.select(
                        record_discrete_value.c.attribute_definition_id,
                        record_discrete_value.c.value,
                        sa.func.count().label("bucket_count"),
                    )
                    .select_from(
                        record_discrete_value.join(
                            matched,
                            sa.and_(
                                matched.c.organization_id
                                == record_discrete_value.c.organization_id,
                                matched.c.project_id == record_discrete_value.c.project_id,
                                matched.c.record_revision_id
                                == record_discrete_value.c.record_revision_id,
                            ),
                        )
                    )
                    .where(
                        record_discrete_value.c.attribute_definition_id.in_(
                            query.facet_attribute_ids
                        )
                    )
                    .group_by(
                        record_discrete_value.c.attribute_definition_id,
                        record_discrete_value.c.value,
                    )
                    .order_by(
                        record_discrete_value.c.attribute_definition_id.asc(),
                        sa.func.count().desc(),
                        record_discrete_value.c.value.asc(),
                    )
                ).mappings()
                facets = tuple(
                    RecordFacetBucket(
                        row["attribute_definition_id"], row["value"], int(row["bucket_count"])
                    )
                    for row in facet_rows
                )
            return RecordSearchResult(
                tuple(self._record_snapshot(row, values) for row in rows),
                total_count,
                facets,
            )

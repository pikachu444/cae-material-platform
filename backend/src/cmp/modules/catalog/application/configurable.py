"""Application service for administrator-defined catalog schemas (T-49)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID, uuid4

from cmp.modules.catalog.domain.configurable import (
    AttributeDefinitionContent,
    CatalogTableContent,
    ConfigurableCatalogConflict,
    LayoutContent,
    SubsetContent,
)
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
    Permission,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.shared.application.revisions import (
    CreateRevisionedAggregate,
    ReviseAggregate,
    RevisionService,
    RevisionStore,
)
from cmp.shared.domain.revisions import RevisionRecord, TenantScope

TABLE_AGGREGATE_TYPE = "catalog.configurable_table"
ATTRIBUTE_AGGREGATE_TYPE = "catalog.attribute_definition"
LAYOUT_AGGREGATE_TYPE = "catalog.layout"
SUBSET_AGGREGATE_TYPE = "catalog.subset"

TABLE_SCHEMA_ID = "urn:cmp:catalog:configurable-table:1.0.0"
ATTRIBUTE_SCHEMA_ID = "urn:cmp:catalog:attribute-definition:1.0.0"
LAYOUT_SCHEMA_ID = "urn:cmp:catalog:layout:1.0.0"
SUBSET_SCHEMA_ID = "urn:cmp:catalog:subset:1.0.0"
SCHEMA_VERSION = "1.0.0"


@dataclass(frozen=True, slots=True)
class ConfigRevision[ContentT]:
    record: RevisionRecord
    content: ContentT


@dataclass(frozen=True, slots=True)
class TableSnapshot:
    id: UUID
    current: ConfigRevision[CatalogTableContent]


@dataclass(frozen=True, slots=True)
class AttributeSnapshot:
    id: UUID
    table_id: UUID
    current: ConfigRevision[AttributeDefinitionContent]


@dataclass(frozen=True, slots=True)
class LayoutSnapshot:
    id: UUID
    table_id: UUID
    current: ConfigRevision[LayoutContent]


@dataclass(frozen=True, slots=True)
class SubsetSnapshot:
    id: UUID
    table_id: UUID
    current: ConfigRevision[SubsetContent]


@dataclass(frozen=True, slots=True)
class CreateTable:
    classification: DataClassification
    content: CatalogTableContent
    change_reason: str


@dataclass(frozen=True, slots=True)
class ReviseTable:
    expected_current_revision_id: UUID
    content: CatalogTableContent
    change_reason: str


@dataclass(frozen=True, slots=True)
class CreateAttribute:
    content: AttributeDefinitionContent
    change_reason: str


@dataclass(frozen=True, slots=True)
class ReviseAttribute:
    expected_current_revision_id: UUID
    content: AttributeDefinitionContent
    change_reason: str


@dataclass(frozen=True, slots=True)
class CreateLayout:
    content: LayoutContent
    change_reason: str


@dataclass(frozen=True, slots=True)
class ReviseLayout:
    expected_current_revision_id: UUID
    content: LayoutContent
    change_reason: str


@dataclass(frozen=True, slots=True)
class CreateSubset:
    content: SubsetContent
    change_reason: str


@dataclass(frozen=True, slots=True)
class ReviseSubset:
    expected_current_revision_id: UUID
    content: SubsetContent
    change_reason: str


class ConfigurableCatalogRepository(Protocol):
    def table_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[CatalogTableContent]: ...

    def attribute_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[AttributeDefinitionContent]: ...

    def layout_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[LayoutContent]: ...

    def subset_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[SubsetContent]: ...

    def list_tables(
        self, *, context: SecurityContext, decision: AuthorizationDecision
    ) -> tuple[TableSnapshot, ...]: ...

    def get_table(
        self, *, context: SecurityContext, decision: AuthorizationDecision, table_id: UUID
    ) -> TableSnapshot: ...

    def get_table_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        table_id: UUID,
        revision_id: UUID,
    ) -> ConfigRevision[CatalogTableContent]: ...

    def get_attribute(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        attribute_id: UUID,
    ) -> AttributeSnapshot: ...

    def get_attribute_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        attribute_id: UUID,
        revision_id: UUID,
    ) -> ConfigRevision[AttributeDefinitionContent]: ...

    def find_attribute_by_key(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        table_id: UUID,
        key: str,
    ) -> AttributeSnapshot | None: ...

    def list_attributes(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        table_id: UUID,
    ) -> tuple[AttributeSnapshot, ...]: ...

    def list_layouts(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        table_id: UUID,
    ) -> tuple[LayoutSnapshot, ...]: ...

    def get_layout(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        layout_id: UUID,
    ) -> LayoutSnapshot: ...

    def list_subsets(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        table_id: UUID,
    ) -> tuple[SubsetSnapshot, ...]: ...

    def get_subset(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        subset_id: UUID,
    ) -> SubsetSnapshot: ...


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
        raise ConfigurableCatalogConflict(
            "authorization decision does not match configurable catalog request"
        )


def _reason(value: str) -> str:
    if not value or value != value.strip() or len(value) > 2000 or "\x00" in value:
        raise ValueError("change_reason must be trimmed and contain 1..2000 characters")
    return value


class ConfigurableCatalogService:
    def __init__(
        self,
        repository: ConfigurableCatalogRepository,
        *,
        id_factory: Callable[[], UUID] = uuid4,
    ) -> None:
        self._repository = repository
        self._id = id_factory

    @staticmethod
    def _scope(context: SecurityContext, classification: DataClassification) -> TenantScope:
        return TenantScope(context.organization_id, context.project_id, classification.value)

    @staticmethod
    def _revision_service[ContentT](
        aggregate_type: str, store: RevisionStore[ContentT]
    ) -> RevisionService[ContentT]:
        return RevisionService(aggregate_type=aggregate_type, store=store)

    def create_table(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CreateTable,
    ) -> TableSnapshot:
        _require(context, decision, Permission.CATALOG_WRITE)
        if any(
            item.current.content.key == command.content.key
            for item in self._repository.list_tables(context=context, decision=decision)
        ):
            raise ConfigurableCatalogConflict("Catalog Table key already exists")
        aggregate_id = self._id()
        record = self._revision_service(
            TABLE_AGGREGATE_TYPE, self._repository.table_store(context, decision)
        ).create(
            CreateRevisionedAggregate(
                aggregate_id=aggregate_id,
                scope=self._scope(context, command.classification),
                schema_id=TABLE_SCHEMA_ID,
                schema_version=SCHEMA_VERSION,
                content=command.content,
                created_by=context.principal.id,
                change_reason=_reason(command.change_reason),
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        return TableSnapshot(aggregate_id, ConfigRevision(record, command.content))

    def revise_table(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        table_id: UUID,
        command: ReviseTable,
    ) -> TableSnapshot:
        _require(context, decision, Permission.CATALOG_WRITE)
        current = self._repository.get_table(context=context, decision=decision, table_id=table_id)
        if command.content.key != current.current.content.key:
            raise ConfigurableCatalogConflict("Catalog Table stable key cannot change")
        record = self._revision_service(
            TABLE_AGGREGATE_TYPE, self._repository.table_store(context, decision)
        ).revise(
            ReviseAggregate(
                aggregate_id=table_id,
                scope=current.current.record.scope,
                expected_current_revision_id=command.expected_current_revision_id,
                based_on_revision_id=command.expected_current_revision_id,
                schema_id=TABLE_SCHEMA_ID,
                schema_version=SCHEMA_VERSION,
                content=command.content,
                created_by=context.principal.id,
                change_reason=_reason(command.change_reason),
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        return TableSnapshot(table_id, ConfigRevision(record, command.content))

    def _require_current_table_revision(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        table_id: UUID,
        table_revision_id: UUID,
    ) -> TableSnapshot:
        table = self._repository.get_table(context=context, decision=decision, table_id=table_id)
        if table.current.record.revision_id != table_revision_id:
            raise ConfigurableCatalogConflict("schema command must pin the current Table revision")
        return table

    def create_attribute(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CreateAttribute,
    ) -> AttributeSnapshot:
        _require(context, decision, Permission.CATALOG_WRITE)
        table = self._require_current_table_revision(
            context,
            decision,
            command.content.table_id,
            command.content.table_revision_id,
        )
        if (
            self._repository.find_attribute_by_key(
                context=context,
                decision=decision,
                table_id=command.content.table_id,
                key=command.content.key,
            )
            is not None
        ):
            raise ConfigurableCatalogConflict("Attribute key already exists in this Table")
        if command.content.reference_table_id is not None:
            self._repository.get_table(
                context=context,
                decision=decision,
                table_id=command.content.reference_table_id,
            )
        aggregate_id = self._id()
        record = self._revision_service(
            ATTRIBUTE_AGGREGATE_TYPE, self._repository.attribute_store(context, decision)
        ).create(
            CreateRevisionedAggregate(
                aggregate_id=aggregate_id,
                scope=table.current.record.scope,
                schema_id=ATTRIBUTE_SCHEMA_ID,
                schema_version=SCHEMA_VERSION,
                content=command.content,
                created_by=context.principal.id,
                change_reason=_reason(command.change_reason),
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        return AttributeSnapshot(
            aggregate_id, command.content.table_id, ConfigRevision(record, command.content)
        )

    def revise_attribute(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        attribute_id: UUID,
        command: ReviseAttribute,
    ) -> AttributeSnapshot:
        _require(context, decision, Permission.CATALOG_WRITE)
        current = self._repository.get_attribute(
            context=context, decision=decision, attribute_id=attribute_id
        )
        self._require_current_table_revision(
            context,
            decision,
            command.content.table_id,
            command.content.table_revision_id,
        )
        old = current.current.content
        if (
            command.content.table_id != old.table_id
            or command.content.key != old.key
            or command.content.data_type is not old.data_type
        ):
            raise ConfigurableCatalogConflict(
                "Attribute Table, stable key and data type cannot change"
            )
        record = self._revision_service(
            ATTRIBUTE_AGGREGATE_TYPE, self._repository.attribute_store(context, decision)
        ).revise(
            ReviseAggregate(
                aggregate_id=attribute_id,
                scope=current.current.record.scope,
                expected_current_revision_id=command.expected_current_revision_id,
                based_on_revision_id=command.expected_current_revision_id,
                schema_id=ATTRIBUTE_SCHEMA_ID,
                schema_version=SCHEMA_VERSION,
                content=command.content,
                created_by=context.principal.id,
                change_reason=_reason(command.change_reason),
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        return AttributeSnapshot(
            attribute_id, command.content.table_id, ConfigRevision(record, command.content)
        )

    def _validate_layout(
        self, context: SecurityContext, decision: AuthorizationDecision, content: LayoutContent
    ) -> TableSnapshot:
        table = self._require_current_table_revision(
            context, decision, content.table_id, content.table_revision_id
        )
        for item in content.items:
            attribute = self._repository.get_attribute_revision(
                context=context,
                decision=decision,
                attribute_id=item.attribute_definition_id,
                revision_id=item.attribute_definition_revision_id,
            )
            if attribute.content.table_id != content.table_id:
                raise ConfigurableCatalogConflict("Layout Attribute belongs to another Table")
        return table

    def create_layout(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CreateLayout,
    ) -> LayoutSnapshot:
        _require(context, decision, Permission.CATALOG_WRITE)
        table = self._validate_layout(context, decision, command.content)
        aggregate_id = self._id()
        record = self._revision_service(
            LAYOUT_AGGREGATE_TYPE, self._repository.layout_store(context, decision)
        ).create(
            CreateRevisionedAggregate(
                aggregate_id=aggregate_id,
                scope=table.current.record.scope,
                schema_id=LAYOUT_SCHEMA_ID,
                schema_version=SCHEMA_VERSION,
                content=command.content,
                created_by=context.principal.id,
                change_reason=_reason(command.change_reason),
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        return LayoutSnapshot(
            aggregate_id, command.content.table_id, ConfigRevision(record, command.content)
        )

    def revise_layout(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        layout_id: UUID,
        command: ReviseLayout,
    ) -> LayoutSnapshot:
        _require(context, decision, Permission.CATALOG_WRITE)
        current = self._repository.get_layout(
            context=context, decision=decision, layout_id=layout_id
        )
        table = self._validate_layout(context, decision, command.content)
        if command.content.table_id != current.table_id:
            raise ConfigurableCatalogConflict("Layout Table cannot change")
        record = self._revision_service(
            LAYOUT_AGGREGATE_TYPE, self._repository.layout_store(context, decision)
        ).revise(
            ReviseAggregate(
                aggregate_id=layout_id,
                scope=table.current.record.scope,
                expected_current_revision_id=command.expected_current_revision_id,
                based_on_revision_id=command.expected_current_revision_id,
                schema_id=LAYOUT_SCHEMA_ID,
                schema_version=SCHEMA_VERSION,
                content=command.content,
                created_by=context.principal.id,
                change_reason=_reason(command.change_reason),
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        return LayoutSnapshot(
            layout_id, command.content.table_id, ConfigRevision(record, command.content)
        )

    def create_subset(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CreateSubset,
    ) -> SubsetSnapshot:
        _require(context, decision, Permission.CATALOG_WRITE)
        table = self._require_current_table_revision(
            context,
            decision,
            command.content.table_id,
            command.content.table_revision_id,
        )
        aggregate_id = self._id()
        record = self._revision_service(
            SUBSET_AGGREGATE_TYPE, self._repository.subset_store(context, decision)
        ).create(
            CreateRevisionedAggregate(
                aggregate_id=aggregate_id,
                scope=table.current.record.scope,
                schema_id=SUBSET_SCHEMA_ID,
                schema_version=SCHEMA_VERSION,
                content=command.content,
                created_by=context.principal.id,
                change_reason=_reason(command.change_reason),
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        return SubsetSnapshot(
            aggregate_id, command.content.table_id, ConfigRevision(record, command.content)
        )

    def revise_subset(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        subset_id: UUID,
        command: ReviseSubset,
    ) -> SubsetSnapshot:
        _require(context, decision, Permission.CATALOG_WRITE)
        current = self._repository.get_subset(
            context=context, decision=decision, subset_id=subset_id
        )
        table = self._require_current_table_revision(
            context,
            decision,
            command.content.table_id,
            command.content.table_revision_id,
        )
        if command.content.table_id != current.table_id:
            raise ConfigurableCatalogConflict("Subset Table cannot change")
        record = self._revision_service(
            SUBSET_AGGREGATE_TYPE, self._repository.subset_store(context, decision)
        ).revise(
            ReviseAggregate(
                aggregate_id=subset_id,
                scope=table.current.record.scope,
                expected_current_revision_id=command.expected_current_revision_id,
                based_on_revision_id=command.expected_current_revision_id,
                schema_id=SUBSET_SCHEMA_ID,
                schema_version=SCHEMA_VERSION,
                content=command.content,
                created_by=context.principal.id,
                change_reason=_reason(command.change_reason),
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        return SubsetSnapshot(
            subset_id, command.content.table_id, ConfigRevision(record, command.content)
        )

    def list_tables(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> tuple[TableSnapshot, ...]:
        _require(context, decision, Permission.CATALOG_READ)
        return self._repository.list_tables(context=context, decision=decision)

    def get_table(
        self, context: SecurityContext, decision: AuthorizationDecision, table_id: UUID
    ) -> TableSnapshot:
        _require(context, decision, Permission.CATALOG_READ)
        return self._repository.get_table(context=context, decision=decision, table_id=table_id)

    def get_table_for_write(
        self, context: SecurityContext, decision: AuthorizationDecision, table_id: UUID
    ) -> TableSnapshot:
        _require(context, decision, Permission.CATALOG_WRITE)
        return self._repository.get_table(context=context, decision=decision, table_id=table_id)

    def list_attributes(
        self, context: SecurityContext, decision: AuthorizationDecision, table_id: UUID
    ) -> tuple[AttributeSnapshot, ...]:
        _require(context, decision, Permission.CATALOG_READ)
        self._repository.get_table(context=context, decision=decision, table_id=table_id)
        return self._repository.list_attributes(
            context=context, decision=decision, table_id=table_id
        )

    def get_attribute(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        attribute_id: UUID,
    ) -> AttributeSnapshot:
        _require(context, decision, Permission.CATALOG_READ)
        return self._repository.get_attribute(
            context=context, decision=decision, attribute_id=attribute_id
        )

    def get_attribute_for_write(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        attribute_id: UUID,
    ) -> AttributeSnapshot:
        _require(context, decision, Permission.CATALOG_WRITE)
        return self._repository.get_attribute(
            context=context, decision=decision, attribute_id=attribute_id
        )

    def list_layouts(
        self, context: SecurityContext, decision: AuthorizationDecision, table_id: UUID
    ) -> tuple[LayoutSnapshot, ...]:
        _require(context, decision, Permission.CATALOG_READ)
        self._repository.get_table(context=context, decision=decision, table_id=table_id)
        return self._repository.list_layouts(context=context, decision=decision, table_id=table_id)

    def get_layout_for_write(
        self, context: SecurityContext, decision: AuthorizationDecision, layout_id: UUID
    ) -> LayoutSnapshot:
        _require(context, decision, Permission.CATALOG_WRITE)
        return self._repository.get_layout(context=context, decision=decision, layout_id=layout_id)

    def list_subsets(
        self, context: SecurityContext, decision: AuthorizationDecision, table_id: UUID
    ) -> tuple[SubsetSnapshot, ...]:
        _require(context, decision, Permission.CATALOG_READ)
        self._repository.get_table(context=context, decision=decision, table_id=table_id)
        return self._repository.list_subsets(context=context, decision=decision, table_id=table_id)

    def get_subset_for_write(
        self, context: SecurityContext, decision: AuthorizationDecision, subset_id: UUID
    ) -> SubsetSnapshot:
        _require(context, decision, Permission.CATALOG_WRITE)
        return self._repository.get_subset(context=context, decision=decision, subset_id=subset_id)

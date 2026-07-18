"""Use cases for configurable Catalog folders, records, search and comparison (T-50)."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal, Protocol
from uuid import UUID, uuid4

from cmp.modules.catalog.application.configurable import (
    ConfigRevision,
    ConfigurableCatalogRepository,
)
from cmp.modules.catalog.domain.configurable import (
    AttributeDataType,
    ConfigurableCatalogConflict,
)
from cmp.modules.catalog.domain.records import (
    CatalogFolderContent,
    CatalogRecordContent,
    CatalogRecordQuery,
    CatalogRecordValue,
    folder_canonical,
    record_canonical,
    record_value_canonical,
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
from cmp.shared.domain.revisions import TenantScope

FOLDER_AGGREGATE_TYPE = "catalog.folder"
RECORD_AGGREGATE_TYPE = "catalog.configurable_record"
FOLDER_SCHEMA_ID = "urn:cmp:catalog:folder:1.0.0"
RECORD_SCHEMA_ID = "urn:cmp:catalog:record:1.0.0"
SCHEMA_VERSION = "1.0.0"


@dataclass(frozen=True, slots=True)
class FolderSnapshot:
    id: UUID
    table_id: UUID
    current: ConfigRevision[CatalogFolderContent]


@dataclass(frozen=True, slots=True)
class RecordSnapshot:
    id: UUID
    table_id: UUID
    current: ConfigRevision[CatalogRecordContent]


@dataclass(frozen=True, slots=True)
class RecordFacetBucket:
    attribute_definition_id: UUID
    value: str
    count: int


@dataclass(frozen=True, slots=True)
class RecordSearchResult:
    items: tuple[RecordSnapshot, ...]
    total_count: int
    facets: tuple[RecordFacetBucket, ...]


@dataclass(frozen=True, slots=True)
class RecordValueDifference:
    attribute_definition_id: UUID
    status: Literal["added", "removed", "changed", "unchanged"]
    before: CatalogRecordValue | None
    after: CatalogRecordValue | None


@dataclass(frozen=True, slots=True)
class RecordComparison:
    record_id: UUID
    from_revision: ConfigRevision[CatalogRecordContent]
    to_revision: ConfigRevision[CatalogRecordContent]
    metadata_changed: bool
    value_differences: tuple[RecordValueDifference, ...]


@dataclass(frozen=True, slots=True)
class CreateFolder:
    classification: DataClassification
    content: CatalogFolderContent
    change_reason: str


@dataclass(frozen=True, slots=True)
class ReviseFolder:
    expected_current_revision_id: UUID
    content: CatalogFolderContent
    change_reason: str


@dataclass(frozen=True, slots=True)
class CreateRecord:
    classification: DataClassification
    content: CatalogRecordContent
    change_reason: str


@dataclass(frozen=True, slots=True)
class ReviseRecord:
    expected_current_revision_id: UUID
    content: CatalogRecordContent
    change_reason: str


class CatalogRecordRepository(Protocol):
    def folder_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[CatalogFolderContent]: ...

    def record_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[CatalogRecordContent]: ...

    def list_folders(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        table_id: UUID,
    ) -> tuple[FolderSnapshot, ...]: ...

    def get_folder(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        folder_id: UUID,
    ) -> FolderSnapshot: ...

    def get_folder_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        folder_id: UUID,
        revision_id: UUID,
    ) -> ConfigRevision[CatalogFolderContent]: ...

    def get_record(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        record_id: UUID,
    ) -> RecordSnapshot: ...

    def list_direct_records(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        table_id: UUID,
        folder_id: UUID | None,
    ) -> tuple[RecordSnapshot, ...]: ...

    def get_record_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        record_id: UUID,
        revision_id: UUID,
    ) -> ConfigRevision[CatalogRecordContent]: ...

    def list_record_revisions(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        record_id: UUID,
    ) -> tuple[ConfigRevision[CatalogRecordContent], ...]: ...

    def search_records(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        query: CatalogRecordQuery,
    ) -> RecordSearchResult: ...


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
        raise ConfigurableCatalogConflict("authorization decision does not match Catalog request")


def _reason(value: str) -> str:
    if not value or value != value.strip() or len(value) > 2000 or "\x00" in value:
        raise ValueError("change_reason must be trimmed and contain 1..2000 characters")
    return value


class CatalogRecordService:
    def __init__(
        self,
        repository: CatalogRecordRepository,
        schema_repository: ConfigurableCatalogRepository,
        *,
        id_factory: Callable[[], UUID] = uuid4,
    ) -> None:
        self._repository = repository
        self._schemas = schema_repository
        self._id = id_factory

    @staticmethod
    def _scope(context: SecurityContext, classification: DataClassification) -> TenantScope:
        return TenantScope(context.organization_id, context.project_id, classification.value)

    @staticmethod
    def _revision_service[ContentT](
        aggregate_type: str, store: RevisionStore[ContentT]
    ) -> RevisionService[ContentT]:
        return RevisionService(aggregate_type=aggregate_type, store=store)

    def _require_current_table(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        table_id: UUID,
        revision_id: UUID,
    ) -> None:
        table = self._schemas.get_table(context=context, decision=decision, table_id=table_id)
        if table.current.record.revision_id != revision_id:
            raise ConfigurableCatalogConflict("Record command must pin the current Table revision")

    def _validate_parent(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        content: CatalogFolderContent,
        *,
        folder_id: UUID | None,
    ) -> None:
        if content.parent_folder_id is None or content.parent_folder_revision_id is None:
            return
        seen: set[UUID] = set()
        parent_id = content.parent_folder_id
        parent_revision_id = content.parent_folder_revision_id
        while True:
            if parent_id == folder_id or parent_id in seen:
                raise ConfigurableCatalogConflict("Folder parent relationship would create a cycle")
            seen.add(parent_id)
            parent = self._repository.get_folder_revision(
                context=context,
                decision=decision,
                folder_id=parent_id,
                revision_id=parent_revision_id,
            )
            if parent.content.table_id != content.table_id:
                raise ConfigurableCatalogConflict("Folder parent belongs to another Table")
            if (
                parent.content.parent_folder_id is None
                or parent.content.parent_folder_revision_id is None
            ):
                return
            parent_id = parent.content.parent_folder_id
            parent_revision_id = parent.content.parent_folder_revision_id

    def create_folder(
        self, context: SecurityContext, decision: AuthorizationDecision, command: CreateFolder
    ) -> FolderSnapshot:
        _require(context, decision, Permission.CATALOG_WRITE)
        self._require_current_table(
            context, decision, command.content.table_id, command.content.table_revision_id
        )
        self._validate_parent(context, decision, command.content, folder_id=None)
        folder_id = self._id()
        record = self._revision_service(
            FOLDER_AGGREGATE_TYPE, self._repository.folder_store(context, decision)
        ).create(
            CreateRevisionedAggregate(
                aggregate_id=folder_id,
                scope=self._scope(context, command.classification),
                schema_id=FOLDER_SCHEMA_ID,
                schema_version=SCHEMA_VERSION,
                content=command.content,
                created_by=context.principal.id,
                change_reason=_reason(command.change_reason),
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        return FolderSnapshot(
            folder_id, command.content.table_id, ConfigRevision(record, command.content)
        )

    def revise_folder(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        folder_id: UUID,
        command: ReviseFolder,
    ) -> FolderSnapshot:
        _require(context, decision, Permission.CATALOG_WRITE)
        current = self._repository.get_folder(
            context=context, decision=decision, folder_id=folder_id
        )
        if current.table_id != command.content.table_id:
            raise ConfigurableCatalogConflict("Folder Table cannot change")
        self._require_current_table(
            context, decision, command.content.table_id, command.content.table_revision_id
        )
        self._validate_parent(context, decision, command.content, folder_id=folder_id)
        record = self._revision_service(
            FOLDER_AGGREGATE_TYPE, self._repository.folder_store(context, decision)
        ).revise(
            ReviseAggregate(
                aggregate_id=folder_id,
                scope=current.current.record.scope,
                expected_current_revision_id=command.expected_current_revision_id,
                based_on_revision_id=command.expected_current_revision_id,
                schema_id=FOLDER_SCHEMA_ID,
                schema_version=SCHEMA_VERSION,
                content=command.content,
                created_by=context.principal.id,
                change_reason=_reason(command.change_reason),
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        return FolderSnapshot(
            folder_id, command.content.table_id, ConfigRevision(record, command.content)
        )

    def list_folders(
        self, context: SecurityContext, decision: AuthorizationDecision, table_id: UUID
    ) -> tuple[FolderSnapshot, ...]:
        _require(context, decision, Permission.CATALOG_READ)
        self._schemas.get_table(context=context, decision=decision, table_id=table_id)
        return self._repository.list_folders(context=context, decision=decision, table_id=table_id)

    def get_folder_for_write(
        self, context: SecurityContext, decision: AuthorizationDecision, folder_id: UUID
    ) -> FolderSnapshot:
        _require(context, decision, Permission.CATALOG_WRITE)
        return self._repository.get_folder(context=context, decision=decision, folder_id=folder_id)

    def _validate_record(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        content: CatalogRecordContent,
    ) -> None:
        self._require_current_table(context, decision, content.table_id, content.table_revision_id)
        if content.folder_id is not None and content.folder_revision_id is not None:
            folder = self._repository.get_folder_revision(
                context=context,
                decision=decision,
                folder_id=content.folder_id,
                revision_id=content.folder_revision_id,
            )
            if folder.content.table_id != content.table_id:
                raise ConfigurableCatalogConflict("Record folder belongs to another Table")

        current_attributes = self._schemas.list_attributes(
            context=context, decision=decision, table_id=content.table_id
        )
        definitions = {item.id: item for item in current_attributes}
        supplied = {value.attribute_definition_id: value for value in content.values}
        missing = [
            item.current.content.name
            for item in current_attributes
            if item.current.content.required and item.id not in supplied
        ]
        if missing:
            raise ConfigurableCatalogConflict(
                f"Record is missing required Attributes: {', '.join(sorted(missing))}"
            )
        for value in content.values:
            definition = definitions.get(value.attribute_definition_id)
            if definition is None:
                raise ConfigurableCatalogConflict("Record value Attribute is not current for Table")
            if definition.current.record.revision_id != value.attribute_definition_revision_id:
                raise ConfigurableCatalogConflict(
                    "Record value must pin current Attribute revision"
                )
            attribute = definition.current.content
            if attribute.data_type is not value.data_type:
                raise ConfigurableCatalogConflict("Record value type does not match Attribute")
            if value.data_type is AttributeDataType.NUMBER:
                if (
                    value.quantity_semantics != attribute.quantity_semantics
                    or value.normalized_unit != attribute.normalized_unit
                ):
                    raise ConfigurableCatalogConflict(
                        "Number value unit and quantity semantics must match Attribute revision"
                    )
                assert value.normalized_value is not None
                if (
                    attribute.minimum_number is not None
                    and value.normalized_value < attribute.minimum_number
                ) or (
                    attribute.maximum_number is not None
                    and value.normalized_value > attribute.maximum_number
                ):
                    raise ConfigurableCatalogConflict("Number value is outside Attribute bounds")
            if value.data_type in {AttributeDataType.TEXT, AttributeDataType.DISCRETE}:
                assert isinstance(value.value, str)
                if (
                    attribute.minimum_length is not None
                    and len(value.value) < attribute.minimum_length
                ):
                    raise ConfigurableCatalogConflict(
                        "Text value is shorter than Attribute minimum"
                    )
                if (
                    attribute.maximum_length is not None
                    and len(value.value) > attribute.maximum_length
                ):
                    raise ConfigurableCatalogConflict("Text value exceeds Attribute maximum")
                if (
                    attribute.pattern is not None
                    and re.fullmatch(attribute.pattern, value.value) is None
                ):
                    raise ConfigurableCatalogConflict("Text value does not match Attribute pattern")
                if (
                    value.data_type is AttributeDataType.DISCRETE
                    and value.value not in attribute.allowed_values
                ):
                    raise ConfigurableCatalogConflict("Discrete value is not allowed by Attribute")
            if value.data_type is AttributeDataType.RECORD_REFERENCE:
                assert value.target_record_id is not None
                assert value.target_record_revision_id is not None
                target = self._repository.get_record_revision(
                    context=context,
                    decision=decision,
                    record_id=value.target_record_id,
                    revision_id=value.target_record_revision_id,
                )
                if target.content.table_id != attribute.reference_table_id:
                    raise ConfigurableCatalogConflict(
                        "Record-reference target does not match Attribute target Table"
                    )

    def create_record(
        self, context: SecurityContext, decision: AuthorizationDecision, command: CreateRecord
    ) -> RecordSnapshot:
        _require(context, decision, Permission.CATALOG_WRITE)
        self._validate_record(context, decision, command.content)
        record_id = self._id()
        record = self._revision_service(
            RECORD_AGGREGATE_TYPE, self._repository.record_store(context, decision)
        ).create(
            CreateRevisionedAggregate(
                aggregate_id=record_id,
                scope=self._scope(context, command.classification),
                schema_id=RECORD_SCHEMA_ID,
                schema_version=SCHEMA_VERSION,
                content=command.content,
                created_by=context.principal.id,
                change_reason=_reason(command.change_reason),
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        return RecordSnapshot(
            record_id, command.content.table_id, ConfigRevision(record, command.content)
        )

    def revise_record(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        record_id: UUID,
        command: ReviseRecord,
    ) -> RecordSnapshot:
        _require(context, decision, Permission.CATALOG_WRITE)
        current = self._repository.get_record(
            context=context, decision=decision, record_id=record_id
        )
        if current.table_id != command.content.table_id:
            raise ConfigurableCatalogConflict("Record Table cannot change")
        self._validate_record(context, decision, command.content)
        record = self._revision_service(
            RECORD_AGGREGATE_TYPE, self._repository.record_store(context, decision)
        ).revise(
            ReviseAggregate(
                aggregate_id=record_id,
                scope=current.current.record.scope,
                expected_current_revision_id=command.expected_current_revision_id,
                based_on_revision_id=command.expected_current_revision_id,
                schema_id=RECORD_SCHEMA_ID,
                schema_version=SCHEMA_VERSION,
                content=command.content,
                created_by=context.principal.id,
                change_reason=_reason(command.change_reason),
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        return RecordSnapshot(
            record_id, command.content.table_id, ConfigRevision(record, command.content)
        )

    def get_record(
        self, context: SecurityContext, decision: AuthorizationDecision, record_id: UUID
    ) -> RecordSnapshot:
        _require(context, decision, Permission.CATALOG_READ)
        return self._repository.get_record(context=context, decision=decision, record_id=record_id)

    def get_record_for_write(
        self, context: SecurityContext, decision: AuthorizationDecision, record_id: UUID
    ) -> RecordSnapshot:
        _require(context, decision, Permission.CATALOG_WRITE)
        return self._repository.get_record(context=context, decision=decision, record_id=record_id)

    def list_record_revisions(
        self, context: SecurityContext, decision: AuthorizationDecision, record_id: UUID
    ) -> tuple[ConfigRevision[CatalogRecordContent], ...]:
        _require(context, decision, Permission.CATALOG_READ)
        return self._repository.list_record_revisions(
            context=context, decision=decision, record_id=record_id
        )

    def search_records(
        self, context: SecurityContext, decision: AuthorizationDecision, query: CatalogRecordQuery
    ) -> RecordSearchResult:
        _require(context, decision, Permission.CATALOG_READ)
        self._schemas.get_table(context=context, decision=decision, table_id=query.table_id)
        return self._repository.search_records(context=context, decision=decision, query=query)

    def compare_record_revisions(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        record_id: UUID,
        from_revision_id: UUID,
        to_revision_id: UUID,
    ) -> RecordComparison:
        _require(context, decision, Permission.CATALOG_READ)
        before = self._repository.get_record_revision(
            context=context,
            decision=decision,
            record_id=record_id,
            revision_id=from_revision_id,
        )
        after = self._repository.get_record_revision(
            context=context,
            decision=decision,
            record_id=record_id,
            revision_id=to_revision_id,
        )
        before_values = {item.attribute_definition_id: item for item in before.content.values}
        after_values = {item.attribute_definition_id: item for item in after.content.values}
        differences: list[RecordValueDifference] = []
        for attribute_id in sorted(before_values.keys() | after_values.keys(), key=str):
            left = before_values.get(attribute_id)
            right = after_values.get(attribute_id)
            if left is None:
                status: Literal["added", "removed", "changed", "unchanged"] = "added"
            elif right is None:
                status = "removed"
            elif record_value_canonical(left) == record_value_canonical(right):
                status = "unchanged"
            else:
                status = "changed"
            differences.append(RecordValueDifference(attribute_id, status, left, right))
        before_metadata = record_canonical(
            CatalogRecordContent(
                before.content.table_id,
                before.content.table_revision_id,
                before.content.name,
                before.content.external_key,
                before.content.description,
                before.content.folder_id,
                before.content.folder_revision_id,
            )
        )
        after_metadata = record_canonical(
            CatalogRecordContent(
                after.content.table_id,
                after.content.table_revision_id,
                after.content.name,
                after.content.external_key,
                after.content.description,
                after.content.folder_id,
                after.content.folder_revision_id,
            )
        )
        return RecordComparison(
            record_id,
            before,
            after,
            before_metadata != after_metadata,
            tuple(differences),
        )


__all__ = [
    "CatalogRecordService",
    "CreateFolder",
    "CreateRecord",
    "FolderSnapshot",
    "RecordComparison",
    "RecordFacetBucket",
    "RecordSearchResult",
    "RecordSnapshot",
    "ReviseFolder",
    "ReviseRecord",
    "folder_canonical",
    "record_canonical",
]

"""Use cases for configurable Catalog folders, records, search and comparison (T-50)."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Literal, Protocol
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
from cmp.modules.catalog.domain.registration_units import (
    normalize_registration_value,
    registration_unit_evidence,
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
class RecordDomainBinding:
    """Minimal exact domain projection attached to a governed search row."""

    binding_id: UUID
    kind: str
    object_id: UUID
    revision_id: UUID
    workbench_path: str


@dataclass(frozen=True, slots=True)
class RecordSnapshot:
    id: UUID
    table_id: UUID
    current: ConfigRevision[CatalogRecordContent]
    domain_binding: RecordDomainBinding | None = None
    domain_bindings: tuple[RecordDomainBinding, ...] = ()


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
    domain_bindings: tuple[tuple[str, UUID, UUID], ...] = ()


@dataclass(frozen=True, slots=True)
class ReviseRecord:
    expected_current_revision_id: UUID
    content: CatalogRecordContent
    change_reason: str


@dataclass(frozen=True, slots=True)
class RegistrationCellError:
    row: int
    column: str
    message: str
    action: str


@dataclass(frozen=True, slots=True)
class RegistrationPreview:
    token: str
    valid: bool
    rows: tuple[dict[str, Any], ...]
    errors: tuple[RegistrationCellError, ...]
    source_columns: tuple[str, ...] = ()
    sample_rows: tuple[dict[str, Any], ...] = ()


@dataclass(frozen=True, slots=True)
class RegistrationPublishResult:
    records: tuple[RecordSnapshot, ...]


@dataclass(frozen=True, slots=True)
class RegistrationSourceEvidence:
    artifact_id: UUID | None
    sha256: str
    file_format: str
    sheet_name: str | None = None
    encoding: str | None = None
    delimiter: str | None = None
    decimal_separator: str = "."
    unit_mappings: tuple[dict[str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class StoredRegistrationPreview:
    """Durable, opaque-token registration input owned by the catalog boundary."""

    table_id: UUID
    table_revision_id: UUID
    rows: tuple[dict[str, Any], ...]
    mapping: dict[str, Any]
    common_material_state: dict[str, str] | None
    source: RegistrationSourceEvidence


class CatalogRecordRepository(Protocol):
    def external_key_exists(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        table_id: UUID,
        external_key: str,
    ) -> bool: ...
    def folder_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[CatalogFolderContent]: ...

    def record_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[CatalogRecordContent]: ...

    def create_records_atomically(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        records: tuple[tuple[UUID, CreateRecord], ...],
        registration_token: str | None = None,
    ) -> tuple[RecordSnapshot, ...]: ...

    def save_registration_preview(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        classification: str,
        token: str,
        table_id: UUID,
        table_revision_id: UUID,
        rows: tuple[dict[str, Any], ...],
        mapping: dict[str, Any],
        common_material_state: dict[str, str] | None,
        source: RegistrationSourceEvidence,
        errors: tuple[RegistrationCellError, ...],
    ) -> None: ...

    def get_registration_preview(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        token: str,
    ) -> StoredRegistrationPreview | None: ...

    def consume_registration_preview(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        token: str,
    ) -> bool: ...

    def resolve_registration_material_state(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        selection: dict[str, str],
    ) -> tuple[tuple[str, UUID, UUID], ...] | None: ...

    def resolve_registration_material_state_label(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_code: str,
        state_name: str,
    ) -> tuple[tuple[tuple[str, UUID, UUID], ...], str] | None: ...

    def registration_binding_owner(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        binding: tuple[str, UUID, UUID],
    ) -> UUID | None: ...

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
    ) -> str:
        table = self._schemas.get_table(context=context, decision=decision, table_id=table_id)
        if table.current.record.revision_id != revision_id:
            raise ConfigurableCatalogConflict("Record command must pin the current Table revision")
        return table.current.record.scope.classification

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

    @staticmethod
    def _normalize_record_content(content: CatalogRecordContent) -> CatalogRecordContent:
        values: list[CatalogRecordValue] = []
        for value in content.values:
            if value.data_type is not AttributeDataType.NUMBER:
                values.append(value)
                continue
            assert value.original_value is not None
            assert value.original_unit_string is not None
            assert value.normalized_unit is not None
            normalized, _ = normalize_registration_value(
                value.original_value,
                value.original_unit_string,
                value.normalized_unit,
            )
            values.append(
                CatalogRecordValue(
                    attribute_definition_id=value.attribute_definition_id,
                    attribute_definition_revision_id=value.attribute_definition_revision_id,
                    data_type=value.data_type,
                    original_value=value.original_value,
                    original_unit_string=value.original_unit_string,
                    normalized_value=normalized,
                    normalized_unit=value.normalized_unit,
                    quantity_semantics=value.quantity_semantics,
                )
            )
        return CatalogRecordContent(
            table_id=content.table_id,
            table_revision_id=content.table_revision_id,
            name=content.name,
            external_key=content.external_key,
            description=content.description,
            folder_id=content.folder_id,
            folder_revision_id=content.folder_revision_id,
            values=tuple(values),
        )

    def create_record(
        self, context: SecurityContext, decision: AuthorizationDecision, command: CreateRecord
    ) -> RecordSnapshot:
        _require(context, decision, Permission.CATALOG_WRITE)
        content = self._normalize_record_content(command.content)
        self._validate_record(context, decision, content)
        record_id = self._id()
        record = self._revision_service(
            RECORD_AGGREGATE_TYPE, self._repository.record_store(context, decision)
        ).create(
            CreateRevisionedAggregate(
                aggregate_id=record_id,
                scope=self._scope(context, command.classification),
                schema_id=RECORD_SCHEMA_ID,
                schema_version=SCHEMA_VERSION,
                content=content,
                created_by=context.principal.id,
                change_reason=_reason(command.change_reason),
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        return RecordSnapshot(record_id, content.table_id, ConfigRevision(record, content))

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
        content = self._normalize_record_content(command.content)
        self._validate_record(context, decision, content)
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
                content=content,
                created_by=context.principal.id,
                change_reason=_reason(command.change_reason),
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        return RecordSnapshot(record_id, content.table_id, ConfigRevision(record, content))

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

    @staticmethod
    def _registration_error(
        errors: list[RegistrationCellError], row: int, column: str, message: str, action: str
    ) -> None:
        errors.append(RegistrationCellError(row, column, message, action))

    def preview_registration(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        *,
        table_id: UUID,
        table_revision_id: UUID,
        rows: tuple[dict[str, Any], ...],
        mapping: dict[str, Any],
        common_material_state: dict[str, str] | None = None,
        source: RegistrationSourceEvidence | None = None,
        _token: str | None = None,
        _persist: bool = True,
    ) -> RegistrationPreview:
        """Validate manual/import rows without mutating catalog state."""

        _require(context, decision, Permission.CATALOG_WRITE)
        table_classification = self._require_current_table(
            context, decision, table_id, table_revision_id
        )
        attributes = self._schemas.list_attributes(
            context=context, decision=decision, table_id=table_id
        )
        by_key = {item.current.content.key: item for item in attributes}
        by_id = {str(item.id): item for item in attributes}
        errors: list[RegistrationCellError] = []
        common_bindings: tuple[tuple[str, UUID, UUID], ...] = ()
        if common_material_state is not None:
            required_state_keys = {
                "material_id",
                "material_revision_id",
                "state_id",
                "state_revision_id",
            }
            missing_state = sorted(required_state_keys - set(common_material_state))
            if missing_state:
                self._registration_error(
                    errors,
                    1,
                    "material state",
                    "선택한 재료 상태가 완전하지 않습니다.",
                    "기존 재료와 상태를 모두 선택하세요.",
                )
            else:
                try:
                    for key in required_state_keys:
                        if UUID(str(common_material_state[key])).int == 0:
                            raise ValueError
                except (ValueError, AttributeError):
                    self._registration_error(
                        errors,
                        1,
                        "material state",
                        "재료 상태 선택이 올바르지 않습니다.",
                        "기존 재료 상태를 다시 선택하세요.",
                    )
                else:
                    common_bindings = (
                        self._repository.resolve_registration_material_state(
                            context=context,
                            decision=decision,
                            selection=common_material_state,
                        )
                        or ()
                    )
                    if not common_bindings:
                        self._registration_error(
                            errors,
                            1,
                            "material state",
                            "선택한 재료와 상태의 정확한 개정판을 찾을 수 없습니다.",
                            "기존 재료 상태를 다시 선택하세요.",
                        )
                    elif (
                        self._repository.registration_binding_owner(
                            context=context,
                            decision=decision,
                            binding=common_bindings[0],
                        )
                        is not None
                    ):
                        self._registration_error(
                            errors,
                            1,
                            "material state",
                            "선택한 재료 상태에는 이미 데이터가 등록되어 있습니다.",
                            "검색 결과에서 기존 데이터를 열어 수정하세요.",
                        )
        contents: list[CatalogRecordContent] = []
        normalized_rows: list[dict[str, Any]] = []
        seen_codes: set[str] = set()
        resolved_mapping: dict[str, tuple[Any, str | None]] = {}
        name_source: str | None = None
        code_source: str | None = None
        material_code_source: str | None = None
        state_name_source: str | None = None
        unit_mapping_evidence: list[dict[str, str]] = []
        for source_column, raw_target in mapping.items():
            if isinstance(raw_target, str):
                target = raw_target
                source_unit = None
            elif isinstance(raw_target, dict):
                target = str(raw_target.get("attribute") or "")
                source_unit = str(raw_target.get("unit") or "").strip() or None
            else:
                target = ""
                source_unit = None
            if target == "name":
                name_source = source_column
                continue
            if target in {"external_key", "code"}:
                code_source = source_column
                continue
            if target == "existing_material_code":
                material_code_source = source_column
                material_code_attribute = by_key.get("material_code")
                if material_code_attribute is not None:
                    resolved_mapping[source_column] = (material_code_attribute, source_unit)
                continue
            if target == "existing_state_name":
                state_name_source = source_column
                state_name_attribute = by_key.get("state_name")
                if state_name_attribute is not None:
                    resolved_mapping[source_column] = (state_name_attribute, source_unit)
                continue
            attribute = by_key.get(target) or by_id.get(target)
            if attribute is None:
                self._registration_error(
                    errors,
                    1,
                    source_column,
                    "이 열을 등록할 Attribute를 찾을 수 없습니다.",
                    "Attribute를 다시 선택하세요.",
                )
            else:
                if (
                    source_unit is not None
                    and attribute.current.content.data_type is not AttributeDataType.NUMBER
                ):
                    self._registration_error(
                        errors,
                        1,
                        source_column,
                        "단위는 숫자 Attribute에만 연결할 수 있습니다.",
                        "단위를 비우거나 숫자 Attribute를 선택하세요.",
                    )
                if (
                    source_unit is not None
                    and attribute.current.content.data_type is AttributeDataType.NUMBER
                    and attribute.current.content.normalized_unit is not None
                ):
                    evidence = registration_unit_evidence(
                        source_unit, attribute.current.content.normalized_unit
                    )
                    if evidence is not None:
                        unit_mapping_evidence.append({"source_column": source_column, **evidence})
                resolved_mapping[source_column] = (attribute, source_unit)
        if (material_code_source is None) != (state_name_source is None):
            self._registration_error(
                errors,
                1,
                material_code_source or state_name_source or "material state",
                "재료 코드와 상태 이름 열을 함께 연결해야 합니다.",
                "두 열을 모두 연결하거나 기존 재료 상태를 하나 선택하세요.",
            )
        if common_material_state is not None and material_code_source is not None:
            self._registration_error(
                errors,
                1,
                "material state",
                "행별 재료 상태와 공통 재료 상태를 함께 사용할 수 없습니다.",
                "행별 열 연결 또는 공통 선택 중 하나만 사용하세요.",
            )
        if common_material_state is not None and len(rows) > 1:
            self._registration_error(
                errors,
                1,
                "material state",
                "한 재료 상태에는 하나의 데이터 레코드만 연결할 수 있습니다.",
                "여러 행은 재료 코드와 상태 이름 열을 연결해 등록하세요.",
            )
        for row_number, raw_row in enumerate(rows, start=1):
            if not isinstance(raw_row, dict):
                self._registration_error(
                    errors,
                    row_number,
                    "row",
                    "행 형식을 읽을 수 없습니다.",
                    "행을 객체로 다시 입력하세요.",
                )
                continue
            values: list[CatalogRecordValue] = []
            row_errors_before = len(errors)
            name = str(
                (
                    raw_row.get(name_source)
                    if name_source is not None
                    else raw_row.get("name") or raw_row.get("Name")
                )
                or ""
            ).strip()
            external_key = (
                str(
                    (
                        raw_row.get(code_source)
                        if code_source is not None
                        else raw_row.get("external_key")
                        or raw_row.get("code")
                        or raw_row.get("Code")
                    )
                    or ""
                ).strip()
                or None
            )
            state_display_name: str | None = None
            if material_code_source is not None and state_name_source is not None:
                material_code = str(raw_row.get(material_code_source) or "").strip()
                state_name = str(raw_row.get(state_name_source) or "").strip()
                if not material_code:
                    self._registration_error(
                        errors,
                        row_number,
                        material_code_source,
                        "재료 코드가 필요합니다.",
                        "기존 재료의 코드를 입력하세요.",
                    )
                if not state_name:
                    self._registration_error(
                        errors,
                        row_number,
                        state_name_source,
                        "재료 상태 이름이 필요합니다.",
                        "기존 재료 상태의 이름을 입력하세요.",
                    )
                if material_code and state_name:
                    resolved_state = self._repository.resolve_registration_material_state_label(
                        context=context,
                        decision=decision,
                        material_code=material_code,
                        state_name=state_name,
                    )
                    if resolved_state is None:
                        self._registration_error(
                            errors,
                            row_number,
                            state_name_source,
                            "재료 코드와 상태 이름에 정확히 맞는 항목을 찾을 수 없습니다.",
                            "기존 재료의 코드와 상태 이름을 확인하세요.",
                        )
                    else:
                        resolved_bindings, state_display_name = resolved_state
                        if (
                            self._repository.registration_binding_owner(
                                context=context,
                                decision=decision,
                                binding=resolved_bindings[0],
                            )
                            is not None
                        ):
                            self._registration_error(
                                errors,
                                row_number,
                                state_name_source,
                                "이 재료 상태에는 이미 데이터가 등록되어 있습니다.",
                                "검색 결과에서 기존 데이터를 열어 수정하세요.",
                            )
            if not name:
                self._registration_error(
                    errors,
                    row_number,
                    name_source or "name",
                    "이름이 필요합니다.",
                    "이름을 입력하세요.",
                )
                name = f"Row {row_number}"
            if external_key is not None:
                normalized_code = external_key.casefold()
                if normalized_code in seen_codes:
                    self._registration_error(
                        errors,
                        row_number,
                        code_source or "external_key",
                        "코드가 중복됩니다.",
                        "각 행에 다른 코드를 입력하세요.",
                    )
                else:
                    exists = getattr(self._repository, "external_key_exists", None)
                    if exists is not None and exists(
                        context=context,
                        decision=decision,
                        table_id=table_id,
                        external_key=external_key,
                    ):
                        self._registration_error(
                            errors,
                            row_number,
                            code_source or "external_key",
                            "이미 등록된 코드입니다.",
                            "기존 Record를 수정하지 말고 다른 코드를 입력하세요.",
                        )
                seen_codes.add(normalized_code)
            for source_column, (attribute, source_unit) in resolved_mapping.items():
                raw = raw_row.get(source_column)
                definition = attribute.current.content
                if raw is None or (isinstance(raw, str) and not raw.strip()):
                    if definition.required:
                        self._registration_error(
                            errors,
                            row_number,
                            source_column,
                            "필수 값이 비어 있습니다.",
                            "값을 입력한 뒤 다시 검증하세요.",
                        )
                    continue
                try:
                    value = self._registration_value(
                        attribute.id,
                        definition,
                        attribute.current.record.revision_id,
                        (
                            {"value": raw, "unit": source_unit}
                            if source_unit is not None and not isinstance(raw, dict)
                            else raw
                        ),
                        decimal_separator=(source.decimal_separator if source is not None else "."),
                    )
                    values.append(value)
                except (ValueError, InvalidOperation) as error:
                    self._registration_error(
                        errors,
                        row_number,
                        source_column,
                        str(error),
                        "셀 값을 Attribute 형식에 맞게 고치세요.",
                    )
            mapped_attribute_ids = {
                mapped_attribute.id for mapped_attribute, _ in resolved_mapping.values()
            }
            for attribute in attributes:
                if attribute.current.content.required and attribute.id not in mapped_attribute_ids:
                    self._registration_error(
                        errors,
                        row_number,
                        attribute.current.content.key,
                        "필수 Attribute가 매핑되지 않았습니다.",
                        "열을 매핑하고 값을 입력하세요.",
                    )
            content = CatalogRecordContent(
                table_id,
                table_revision_id,
                name,
                external_key,
                None,
                None,
                None,
                tuple(values),
            )
            if len(errors) == row_errors_before:
                try:
                    self._validate_record(context, decision, content)
                except ConfigurableCatalogConflict as error:
                    self._registration_error(
                        errors,
                        row_number,
                        "row",
                        str(error),
                        "행의 값을 필드 조건에 맞게 고친 뒤 다시 검증하세요.",
                    )
            if len(errors) == row_errors_before:
                contents.append(content)
                normalized_rows.append(
                    {
                        "row": row_number,
                        "name": name,
                        "external_key": external_key,
                        "material_state": state_display_name,
                        "valid": True,
                    }
                )
            else:
                normalized_rows.append(
                    {
                        "row": row_number,
                        "name": name,
                        "external_key": external_key,
                        "material_state": state_display_name,
                        "valid": False,
                    }
                )
        token = _token or str(self._id())
        columns = tuple(dict.fromkeys(key for row in rows for key in row))
        result = RegistrationPreview(
            token,
            not errors,
            tuple(normalized_rows),
            tuple(errors),
            columns,
            rows[:20],
        )
        if _persist:
            if source is None:
                source = RegistrationSourceEvidence(
                    None,
                    "",
                    "manual",
                )
            source = RegistrationSourceEvidence(
                source.artifact_id,
                source.sha256,
                source.file_format,
                source.sheet_name,
                source.encoding,
                source.delimiter,
                source.decimal_separator,
                tuple(unit_mapping_evidence),
            )
            self._repository.save_registration_preview(
                context=context,
                decision=decision,
                classification=table_classification,
                token=token,
                table_id=table_id,
                table_revision_id=table_revision_id,
                rows=rows,
                mapping=mapping,
                common_material_state=common_material_state,
                source=source,
                errors=result.errors,
            )
        return result

    @staticmethod
    def _registration_value(
        attribute_id: UUID,
        definition: Any,
        revision_id: UUID,
        raw: Any,
        *,
        decimal_separator: str = ".",
    ) -> CatalogRecordValue:
        data_type = definition.data_type
        if data_type is AttributeDataType.NUMBER:
            if isinstance(raw, dict):
                original = raw.get("value", raw.get("original_value"))
                unit = str(raw.get("unit", raw.get("original_unit_string", ""))).strip()
            else:
                text = str(raw).strip()
                parts = text.split(maxsplit=1)
                original = parts[0]
                unit = parts[1] if len(parts) > 1 else ""
            if not unit:
                raise ValueError("원본 단위를 입력하세요.")
            if definition.normalized_unit is None or definition.quantity_semantics is None:
                raise ValueError("Attribute에 정규화 단위 계약이 없습니다.")
            original_text = str(original).strip()
            if decimal_separator == ",":
                original_text = original_text.replace(",", ".")
            original_decimal = Decimal(original_text)
            normalized_decimal, _ = normalize_registration_value(
                original_decimal, unit, definition.normalized_unit
            )
            return CatalogRecordValue(
                attribute_id,
                revision_id,
                data_type,
                original_value=original_decimal,
                original_unit_string=unit,
                normalized_value=normalized_decimal,
                normalized_unit=definition.normalized_unit,
                quantity_semantics=definition.quantity_semantics,
            )
        if data_type is AttributeDataType.INTEGER:
            return CatalogRecordValue(
                attribute_id, revision_id, data_type, value=int(str(raw).strip())
            )
        if data_type is AttributeDataType.BOOLEAN:
            value = str(raw).strip().casefold()
            if value not in {"true", "false", "yes", "no", "1", "0"}:
                raise ValueError("불리언 값은 yes/no 또는 true/false여야 합니다.")
            return CatalogRecordValue(
                attribute_id, revision_id, data_type, value=value in {"true", "yes", "1"}
            )
        if data_type is AttributeDataType.DATE:
            return CatalogRecordValue(
                attribute_id, revision_id, data_type, value=date.fromisoformat(str(raw).strip())
            )
        return CatalogRecordValue(attribute_id, revision_id, data_type, value=str(raw).strip())

    def publish_registration(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        *,
        token: str,
        table_id: UUID,
        table_revision_id: UUID,
        change_reason: str,
        classification: DataClassification = DataClassification.INTERNAL,
    ) -> RegistrationPublishResult:
        _require(context, decision, Permission.CATALOG_WRITE)
        pending = self._repository.get_registration_preview(
            context=context, decision=decision, token=token
        )
        if pending is None or (pending.table_id, pending.table_revision_id) != (
            table_id,
            table_revision_id,
        ):
            raise ConfigurableCatalogConflict("registration preview token is stale")
        preview = self.preview_registration(
            context,
            decision,
            table_id=pending.table_id,
            table_revision_id=pending.table_revision_id,
            rows=pending.rows,
            mapping=pending.mapping,
            common_material_state=pending.common_material_state,
            source=pending.source,
            _token=token,
            _persist=False,
        )
        if not preview.valid:
            raise ConfigurableCatalogConflict(
                "registration preview must be corrected before publishing"
            )
        # Re-run every row's semantic validation before the first write. This keeps an
        # expired schema or state mapping from producing a partial registration.
        # The second validation above is performed from durable input; build the
        # exact typed contents once more only after it passed.
        contents: list[CatalogRecordContent] = []
        bindings_by_row: list[tuple[tuple[str, UUID, UUID], ...]] = []

        def mapping_target(value: Any) -> str:
            return value if isinstance(value, str) else str(value.get("attribute") or "")

        name_source = next(
            (
                column
                for column, target in pending.mapping.items()
                if mapping_target(target) == "name"
            ),
            None,
        )
        code_source = next(
            (
                column
                for column, target in pending.mapping.items()
                if mapping_target(target) in {"external_key", "code"}
            ),
            None,
        )
        material_code_source = next(
            (
                column
                for column, target in pending.mapping.items()
                if mapping_target(target) == "existing_material_code"
            ),
            None,
        )
        state_name_source = next(
            (
                column
                for column, target in pending.mapping.items()
                if mapping_target(target) == "existing_state_name"
            ),
            None,
        )
        for row in pending.rows:
            # preview_registration has established the semantic validity. Reuse
            # its normalized rows by reconstructing through the same mapping in
            # a deliberately local helper rather than trusting client output.
            name = str(
                (
                    row.get(name_source)
                    if name_source is not None
                    else row.get("name") or row.get("Name")
                )
                or ""
            ).strip()
            code = (
                str(
                    (
                        row.get(code_source)
                        if code_source is not None
                        else row.get("external_key") or row.get("code") or row.get("Code")
                    )
                    or ""
                ).strip()
                or None
            )
            attributes = self._schemas.list_attributes(
                context=context, decision=decision, table_id=table_id
            )
            by_key = {item.current.content.key: item for item in attributes}
            by_id = {str(item.id): item for item in attributes}
            values: list[CatalogRecordValue] = []
            for source_column, raw_target in pending.mapping.items():
                if isinstance(raw_target, str):
                    target = raw_target
                    source_unit = None
                else:
                    target = str(raw_target.get("attribute") or "")
                    source_unit = str(raw_target.get("unit") or "").strip() or None
                if target in {"name", "external_key", "code"}:
                    continue
                attribute = (
                    by_key.get("material_code")
                    if target == "existing_material_code"
                    else by_key.get("state_name")
                    if target == "existing_state_name"
                    else by_key.get(target) or by_id.get(target)
                )
                if attribute is None:
                    continue
                raw = row.get(source_column)
                if raw is None or (isinstance(raw, str) and not raw.strip()):
                    continue
                values.append(
                    self._registration_value(
                        attribute.id,
                        attribute.current.content,
                        attribute.current.record.revision_id,
                        (
                            {"value": raw, "unit": source_unit}
                            if source_unit is not None and not isinstance(raw, dict)
                            else raw
                        ),
                        decimal_separator=pending.source.decimal_separator,
                    )
                )
            contents.append(
                CatalogRecordContent(
                    table_id, table_revision_id, name, code, None, None, None, tuple(values)
                )
            )
            if material_code_source is not None and state_name_source is not None:
                resolved_state = self._repository.resolve_registration_material_state_label(
                    context=context,
                    decision=decision,
                    material_code=str(row.get(material_code_source) or ""),
                    state_name=str(row.get(state_name_source) or ""),
                )
                if resolved_state is None:
                    raise ConfigurableCatalogConflict(
                        "selected row material state is no longer available"
                    )
                bindings_by_row.append(resolved_state[0])
            elif pending.common_material_state is not None:
                bindings = self._repository.resolve_registration_material_state(
                    context=context,
                    decision=decision,
                    selection=pending.common_material_state,
                )
                if not bindings:
                    raise ConfigurableCatalogConflict(
                        "selected material state is no longer available"
                    )
                bindings_by_row.append(bindings)
            else:
                bindings_by_row.append(())
        for content in contents:
            self._validate_record(context, decision, content)
        commands = tuple(
            (self._id(), CreateRecord(classification, content, change_reason, bindings))
            for content, bindings in zip(contents, bindings_by_row, strict=True)
        )
        records = self._repository.create_records_atomically(
            context=context,
            decision=decision,
            records=commands,
            registration_token=token,
        )
        return RegistrationPublishResult(records)


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

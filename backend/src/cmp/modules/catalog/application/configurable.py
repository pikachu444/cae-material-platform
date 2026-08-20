"""Application service for administrator-defined catalog schemas (T-49)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol
from uuid import UUID, uuid4

from cmp.modules.catalog.domain.configurable import (
    AttributeDefinitionContent,
    CatalogDatabaseContent,
    CatalogProfileContent,
    CatalogTableContent,
    ConfigurableCatalogConflict,
    ConfigurableCatalogDraftDeleteBlocked,
    ConfigurableCatalogNotFound,
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
DATABASE_AGGREGATE_TYPE = "catalog.database"
PROFILE_AGGREGATE_TYPE = "catalog.profile"
ATTRIBUTE_AGGREGATE_TYPE = "catalog.attribute_definition"
LAYOUT_AGGREGATE_TYPE = "catalog.layout"
SUBSET_AGGREGATE_TYPE = "catalog.subset"
FOLDER_AGGREGATE_TYPE = "catalog.folder"
RECORD_AGGREGATE_TYPE = "catalog.configurable_record"
LINK_TYPE_AGGREGATE_TYPE = "catalog.link_type"

TABLE_SCHEMA_ID = "urn:cmp:catalog:configurable-table:1.0.0"
DATABASE_SCHEMA_ID = "urn:cmp:catalog:database:1.0.0"
PROFILE_SCHEMA_ID = "urn:cmp:catalog:profile:1.0.0"
ATTRIBUTE_SCHEMA_ID = "urn:cmp:catalog:attribute-definition:1.0.0"
LAYOUT_SCHEMA_ID = "urn:cmp:catalog:layout:1.0.0"
SUBSET_SCHEMA_ID = "urn:cmp:catalog:subset:1.0.0"
SCHEMA_VERSION = "1.0.0"


@dataclass(frozen=True, slots=True)
class ConfigRevision[ContentT]:
    record: RevisionRecord
    content: ContentT


@dataclass(frozen=True, slots=True)
class DatabaseSnapshot:
    id: UUID
    current: ConfigRevision[CatalogDatabaseContent]


@dataclass(frozen=True, slots=True)
class ProfileSnapshot:
    id: UUID
    current: ConfigRevision[CatalogProfileContent]


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
    profile_id: UUID | None = None
    profile_revision_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class CreateDatabase:
    classification: DataClassification
    content: CatalogDatabaseContent
    change_reason: str


@dataclass(frozen=True, slots=True)
class ReviseDatabase:
    expected_current_revision_id: UUID
    content: CatalogDatabaseContent
    change_reason: str


@dataclass(frozen=True, slots=True)
class CreateProfile:
    classification: DataClassification
    content: CatalogProfileContent
    change_reason: str


@dataclass(frozen=True, slots=True)
class ReviseProfile:
    expected_current_revision_id: UUID
    content: CatalogProfileContent
    change_reason: str


@dataclass(frozen=True, slots=True)
class PublicationValidation:
    aggregate_type: str
    aggregate_id: UUID
    revision_id: UUID
    valid: bool
    errors: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class PublishRevision:
    aggregate_type: str
    aggregate_id: UUID
    revision_id: UUID


@dataclass(frozen=True, slots=True)
class DeleteDraft:
    expected_current_revision_id: UUID


class DraftDeleteResult(StrEnum):
    DELETED = "deleted"
    NOT_FOUND = "not_found"
    STALE = "stale"
    REVISED = "revised"
    PUBLISHED = "published"
    REFERENCED = "referenced"
    UNSUPPORTED = "unsupported"


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
    def delete_draft(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        aggregate_type: str,
        aggregate_id: UUID,
        expected_revision_id: UUID,
    ) -> DraftDeleteResult: ...

    def place_table(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        table_id: UUID,
        table_revision_id: UUID,
        profile_id: UUID,
        profile_revision_id: UUID,
    ) -> None: ...

    def is_current_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        aggregate_type: str,
        aggregate_id: UUID,
        revision_id: UUID,
    ) -> bool: ...

    def publish_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        aggregate_type: str,
        aggregate_id: UUID,
        revision_id: UUID,
        published_by: UUID,
    ) -> None: ...

    def is_published(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        aggregate_type: str,
        aggregate_id: UUID,
        revision_id: UUID,
    ) -> bool: ...

    def database_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[CatalogDatabaseContent]: ...

    def profile_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[CatalogProfileContent]: ...

    def list_databases(
        self, *, context: SecurityContext, decision: AuthorizationDecision
    ) -> tuple[DatabaseSnapshot, ...]: ...

    def get_database(
        self, *, context: SecurityContext, decision: AuthorizationDecision, database_id: UUID
    ) -> DatabaseSnapshot: ...

    def get_database_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        database_id: UUID,
        revision_id: UUID,
    ) -> ConfigRevision[CatalogDatabaseContent]: ...

    def list_profiles(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        database_id: UUID | None = None,
    ) -> tuple[ProfileSnapshot, ...]: ...

    def get_profile(
        self, *, context: SecurityContext, decision: AuthorizationDecision, profile_id: UUID
    ) -> ProfileSnapshot: ...

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
    _require_one_of(context, decision, permission)


def _require_one_of(
    context: SecurityContext,
    decision: AuthorizationDecision,
    *permissions: Permission,
) -> None:
    if (
        decision.permission not in permissions
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

    def delete_draft(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        aggregate_type: str,
        aggregate_id: UUID,
        command: DeleteDraft,
    ) -> None:
        """Physically delete only an unused, unpublished first draft.

        The repository rechecks every condition atomically at the database boundary.
        """

        _require(context, decision, Permission.CATALOG_WRITE)
        result = self._repository.delete_draft(
            context=context,
            decision=decision,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            expected_revision_id=command.expected_current_revision_id,
        )
        if result is DraftDeleteResult.DELETED:
            return
        if result is DraftDeleteResult.NOT_FOUND:
            raise ConfigurableCatalogNotFound("Catalog draft was not found")
        raise ConfigurableCatalogDraftDeleteBlocked(result.value)

    def create_database(
        self, context: SecurityContext, decision: AuthorizationDecision, command: CreateDatabase
    ) -> DatabaseSnapshot:
        _require(context, decision, Permission.CATALOG_WRITE)
        if any(
            item.current.content.key == command.content.key
            for item in self._repository.list_databases(context=context, decision=decision)
        ):
            raise ConfigurableCatalogConflict("Catalog Database key already exists")
        aggregate_id = self._id()
        record = self._revision_service(
            DATABASE_AGGREGATE_TYPE, self._repository.database_store(context, decision)
        ).create(
            CreateRevisionedAggregate(
                aggregate_id=aggregate_id,
                scope=self._scope(context, command.classification),
                schema_id=DATABASE_SCHEMA_ID,
                schema_version=SCHEMA_VERSION,
                content=command.content,
                created_by=context.principal.id,
                change_reason=_reason(command.change_reason),
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        return DatabaseSnapshot(aggregate_id, ConfigRevision(record, command.content))

    def revise_database(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        database_id: UUID,
        command: ReviseDatabase,
    ) -> DatabaseSnapshot:
        _require(context, decision, Permission.CATALOG_WRITE)
        current = self._repository.get_database(
            context=context, decision=decision, database_id=database_id
        )
        if command.content.key != current.current.content.key:
            raise ConfigurableCatalogConflict("Catalog Database stable key cannot change")
        record = self._revision_service(
            DATABASE_AGGREGATE_TYPE, self._repository.database_store(context, decision)
        ).revise(
            ReviseAggregate(
                aggregate_id=database_id,
                scope=current.current.record.scope,
                expected_current_revision_id=command.expected_current_revision_id,
                based_on_revision_id=command.expected_current_revision_id,
                schema_id=DATABASE_SCHEMA_ID,
                schema_version=SCHEMA_VERSION,
                content=command.content,
                created_by=context.principal.id,
                change_reason=_reason(command.change_reason),
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        return DatabaseSnapshot(database_id, ConfigRevision(record, command.content))

    def create_profile(
        self, context: SecurityContext, decision: AuthorizationDecision, command: CreateProfile
    ) -> ProfileSnapshot:
        _require(context, decision, Permission.CATALOG_WRITE)
        database = self._repository.get_database_revision(
            context=context,
            decision=decision,
            database_id=command.content.database_id,
            revision_id=command.content.database_revision_id,
        )
        if any(
            item.current.content.key == command.content.key
            for item in self._repository.list_profiles(
                context=context, decision=decision, database_id=command.content.database_id
            )
        ):
            raise ConfigurableCatalogConflict("Catalog Profile key already exists")
        aggregate_id = self._id()
        record = self._revision_service(
            PROFILE_AGGREGATE_TYPE, self._repository.profile_store(context, decision)
        ).create(
            CreateRevisionedAggregate(
                aggregate_id=aggregate_id,
                scope=database.record.scope,
                schema_id=PROFILE_SCHEMA_ID,
                schema_version=SCHEMA_VERSION,
                content=command.content,
                created_by=context.principal.id,
                change_reason=_reason(command.change_reason),
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        return ProfileSnapshot(aggregate_id, ConfigRevision(record, command.content))

    def revise_profile(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        profile_id: UUID,
        command: ReviseProfile,
    ) -> ProfileSnapshot:
        _require(context, decision, Permission.CATALOG_WRITE)
        current = self._repository.get_profile(
            context=context, decision=decision, profile_id=profile_id
        )
        self._repository.get_database_revision(
            context=context,
            decision=decision,
            database_id=command.content.database_id,
            revision_id=command.content.database_revision_id,
        )
        if command.content.key != current.current.content.key:
            raise ConfigurableCatalogConflict("Catalog Profile stable key cannot change")
        record = self._revision_service(
            PROFILE_AGGREGATE_TYPE, self._repository.profile_store(context, decision)
        ).revise(
            ReviseAggregate(
                aggregate_id=profile_id,
                scope=current.current.record.scope,
                expected_current_revision_id=command.expected_current_revision_id,
                based_on_revision_id=command.expected_current_revision_id,
                schema_id=PROFILE_SCHEMA_ID,
                schema_version=SCHEMA_VERSION,
                content=command.content,
                created_by=context.principal.id,
                change_reason=_reason(command.change_reason),
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        return ProfileSnapshot(profile_id, ConfigRevision(record, command.content))

    def list_databases(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> tuple[DatabaseSnapshot, ...]:
        _require(context, decision, Permission.CATALOG_READ)
        return self._repository.list_databases(context=context, decision=decision)

    def get_database(
        self, context: SecurityContext, decision: AuthorizationDecision, database_id: UUID
    ) -> DatabaseSnapshot:
        _require(context, decision, Permission.CATALOG_READ)
        return self._repository.get_database(
            context=context, decision=decision, database_id=database_id
        )

    def get_database_for_write(
        self, context: SecurityContext, decision: AuthorizationDecision, database_id: UUID
    ) -> DatabaseSnapshot:
        _require(context, decision, Permission.CATALOG_WRITE)
        return self._repository.get_database(
            context=context, decision=decision, database_id=database_id
        )

    def list_profiles(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        database_id: UUID | None = None,
    ) -> tuple[ProfileSnapshot, ...]:
        _require(context, decision, Permission.CATALOG_READ)
        return self._repository.list_profiles(
            context=context, decision=decision, database_id=database_id
        )

    def get_profile_for_write(
        self, context: SecurityContext, decision: AuthorizationDecision, profile_id: UUID
    ) -> ProfileSnapshot:
        _require(context, decision, Permission.CATALOG_WRITE)
        return self._repository.get_profile(
            context=context, decision=decision, profile_id=profile_id
        )

    def get_profile(
        self, context: SecurityContext, decision: AuthorizationDecision, profile_id: UUID
    ) -> ProfileSnapshot:
        _require(context, decision, Permission.CATALOG_READ)
        return self._repository.get_profile(
            context=context, decision=decision, profile_id=profile_id
        )

    def validate_publication(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: PublishRevision,
    ) -> PublicationValidation:
        _require(context, decision, Permission.CATALOG_WRITE)
        errors: list[str] = []
        try:
            if command.aggregate_type == DATABASE_AGGREGATE_TYPE:
                database = self._repository.get_database(
                    context=context, decision=decision, database_id=command.aggregate_id
                )
                if database.current.record.revision_id != command.revision_id:
                    errors.append("선택한 Database 버전이 현재 초안이 아닙니다.")
            elif command.aggregate_type == PROFILE_AGGREGATE_TYPE:
                profile = self._repository.get_profile(
                    context=context, decision=decision, profile_id=command.aggregate_id
                )
                self._repository.get_database_revision(
                    context=context,
                    decision=decision,
                    database_id=profile.current.content.database_id,
                    revision_id=profile.current.content.database_revision_id,
                )
                if profile.current.record.revision_id != command.revision_id:
                    errors.append("선택한 Profile 버전이 현재 초안이 아닙니다.")
            elif command.aggregate_type == TABLE_AGGREGATE_TYPE:
                table = self._repository.get_table(
                    context=context, decision=decision, table_id=command.aggregate_id
                )
                if table.current.record.revision_id != command.revision_id:
                    errors.append("선택한 Table 버전이 현재 초안이 아닙니다.")
                self._repository.list_attributes(
                    context=context, decision=decision, table_id=command.aggregate_id
                )
            elif command.aggregate_type == ATTRIBUTE_AGGREGATE_TYPE:
                attribute = self._repository.get_attribute(
                    context=context, decision=decision, attribute_id=command.aggregate_id
                )
                if attribute.current.record.revision_id != command.revision_id:
                    errors.append("선택한 Attribute 버전이 현재 초안이 아닙니다.")
            elif command.aggregate_type == LAYOUT_AGGREGATE_TYPE:
                layout = self._repository.get_layout(
                    context=context, decision=decision, layout_id=command.aggregate_id
                )
                if layout.current.record.revision_id != command.revision_id:
                    errors.append("선택한 Layout 버전이 현재 초안이 아닙니다.")
            elif command.aggregate_type == SUBSET_AGGREGATE_TYPE:
                subset = self._repository.get_subset(
                    context=context, decision=decision, subset_id=command.aggregate_id
                )
                if subset.current.record.revision_id != command.revision_id:
                    errors.append("선택한 Subset 버전이 현재 초안이 아닙니다.")
            elif command.aggregate_type in {
                FOLDER_AGGREGATE_TYPE,
                RECORD_AGGREGATE_TYPE,
                LINK_TYPE_AGGREGATE_TYPE,
            }:
                if not self._repository.is_current_revision(
                    context=context,
                    decision=decision,
                    aggregate_type=command.aggregate_type,
                    aggregate_id=command.aggregate_id,
                    revision_id=command.revision_id,
                ):
                    errors.append("선택한 항목의 현재 버전을 찾을 수 없습니다.")
            else:
                errors.append("발행할 수 없는 항목입니다.")
        except ConfigurableCatalogNotFound:
            errors.append("선택한 항목을 찾을 수 없습니다.")
        return PublicationValidation(
            command.aggregate_type,
            command.aggregate_id,
            command.revision_id,
            not errors,
            tuple(errors),
        )

    def publish_revision(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: PublishRevision,
    ) -> PublicationValidation:
        validation = self.validate_publication(context, decision, command)
        if not validation.valid:
            raise ConfigurableCatalogConflict("publication validation failed")
        self._repository.publish_revision(
            context=context,
            decision=decision,
            aggregate_type=command.aggregate_type,
            aggregate_id=command.aggregate_id,
            revision_id=command.revision_id,
            published_by=context.principal.id,
        )
        return validation

    def is_published(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        aggregate_type: str,
        aggregate_id: UUID,
        revision_id: UUID,
    ) -> bool:
        """Read the append-only marker; process memory is never publication authority."""

        # Mutation routes use their already-authorized write decision when they
        # render the resulting revision.  Both decisions carry row-level read
        # permissions, but the decision must still match this exact request.
        _require_one_of(
            context,
            decision,
            Permission.CATALOG_READ,
            Permission.CATALOG_WRITE,
        )
        return self._repository.is_published(
            context=context,
            decision=decision,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            revision_id=revision_id,
        )

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
        if (command.profile_id is None) != (command.profile_revision_id is None):
            raise ConfigurableCatalogConflict(
                "Catalog Table placement requires an exact Profile revision"
            )
        if command.profile_id is not None and command.profile_revision_id is not None:
            profile = self._repository.get_profile(
                context=context, decision=decision, profile_id=command.profile_id
            )
            if profile.current.record.revision_id != command.profile_revision_id:
                raise ConfigurableCatalogConflict(
                    "Catalog Table placement must pin the current Profile revision"
                )
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
        if command.profile_id is not None and command.profile_revision_id is not None:
            self._repository.place_table(
                context=context,
                decision=decision,
                table_id=aggregate_id,
                table_revision_id=record.revision_id,
                profile_id=command.profile_id,
                profile_revision_id=command.profile_revision_id,
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
        if command.content.business_key and any(
            item.current.content.business_key
            for item in self._repository.list_attributes(
                context=context,
                decision=decision,
                table_id=command.content.table_id,
            )
        ):
            raise ConfigurableCatalogConflict(
                "A Table can have at most one governed business-key Attribute"
            )
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
        if command.content.business_key and any(
            item.id != attribute_id and item.current.content.business_key
            for item in self._repository.list_attributes(
                context=context,
                decision=decision,
                table_id=command.content.table_id,
            )
        ):
            raise ConfigurableCatalogConflict(
                "A Table can have at most one governed business-key Attribute"
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

    def get_attribute_revision(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        attribute_id: UUID,
        revision_id: UUID,
    ) -> ConfigRevision[AttributeDefinitionContent]:
        _require(context, decision, Permission.CATALOG_READ)
        return self._repository.get_attribute_revision(
            context=context,
            decision=decision,
            attribute_id=attribute_id,
            revision_id=revision_id,
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

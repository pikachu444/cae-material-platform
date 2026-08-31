"""Use cases for Catalog/Workflow explorers and revision-pinned Record Links (T-51)."""

from __future__ import annotations

from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol
from uuid import UUID, uuid4

from cmp.modules.catalog.application.configurable import (
    ConfigRevision,
    ConfigurableCatalogRepository,
    DeleteDraft,
    DraftDeleteResult,
    TableSnapshot,
)
from cmp.modules.catalog.application.records import (
    CatalogRecordRepository,
    FolderSnapshot,
    RecordSnapshot,
)
from cmp.modules.catalog.domain.configurable import (
    CatalogDataCategory,
    ConfigurableCatalogConflict,
    ConfigurableCatalogDraftDeleteBlocked,
    ConfigurableCatalogNotFound,
)
from cmp.modules.catalog.domain.links import (
    LinkTypeContent,
    RecordLinkContent,
)
from cmp.modules.catalog.domain.records import CatalogRecordQuery
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

LINK_TYPE_AGGREGATE_TYPE = "catalog.link_type"
RECORD_LINK_AGGREGATE_TYPE = "catalog.record_link"
LINK_TYPE_SCHEMA_ID = "urn:cmp:catalog:link-type:1.0.0"
RECORD_LINK_SCHEMA_ID = "urn:cmp:catalog:record-link:1.0.0"
SCHEMA_VERSION = "1.0.0"


@dataclass(frozen=True, slots=True)
class LinkTypeSnapshot:
    id: UUID
    current: ConfigRevision[LinkTypeContent]


@dataclass(frozen=True, slots=True)
class RecordLinkSnapshot:
    id: UUID
    current: ConfigRevision[RecordLinkContent]


@dataclass(frozen=True, slots=True)
class CatalogExplorerChildren:
    table: TableSnapshot
    folders: tuple[FolderSnapshot, ...]
    records: tuple[RecordSnapshot, ...]


class DomainBindingKind(StrEnum):
    MATERIAL = "material"
    MATERIAL_STATE = "material_state"
    SPECIMEN = "specimen"
    TEST_RUN = "test_run"
    TEST_DATA = "test_data"
    PROCESSING_OUTPUT = "processing_output"
    MATERIAL_MODEL = "material_model"
    NEUTRAL_MATERIAL = "neutral_material"
    SOLVER_CARD = "solver_card"
    NEUTRAL_SOLVER_CARD = "neutral_solver_card"
    RELEASE = "release"


@dataclass(frozen=True, slots=True)
class DomainRevisionBinding:
    id: UUID
    record_id: UUID
    record_revision_id: UUID
    kind: DomainBindingKind
    object_id: UUID
    revision_id: UUID
    workbench_path: str


@dataclass(frozen=True, slots=True)
class LinkEndpoint:
    record_id: UUID
    record_revision_id: UUID
    revision_no: int
    table_id: UUID
    name: str
    external_key: str | None
    domain_binding: DomainRevisionBinding | None = None
    # All exact governed revisions pinned to this Record revision.  The
    # singular field remains as a deterministic compatibility projection of
    # the first item in this ordered collection.
    domain_bindings: tuple[DomainRevisionBinding, ...] = ()
    # Immutable projection from the exact Table revision pinned by this Record
    # revision. Domain bindings may refine the user-facing category, but are
    # optional for source-defined Catalog Records.
    data_category: CatalogDataCategory | None = None


@dataclass(frozen=True, slots=True)
class RecordLinkView:
    link: RecordLinkSnapshot
    link_type: ConfigRevision[LinkTypeContent]
    source: LinkEndpoint
    target: LinkEndpoint


@dataclass(frozen=True, slots=True)
class WorkflowGraph:
    root: LinkEndpoint
    nodes: tuple[LinkEndpoint, ...]
    links: tuple[RecordLinkView, ...]


@dataclass(frozen=True, slots=True)
class CreateLinkType:
    classification: DataClassification
    content: LinkTypeContent
    change_reason: str


@dataclass(frozen=True, slots=True)
class ReviseLinkType:
    expected_current_revision_id: UUID
    content: LinkTypeContent
    change_reason: str


@dataclass(frozen=True, slots=True)
class CreateRecordLink:
    classification: DataClassification
    content: RecordLinkContent
    change_reason: str


@dataclass(frozen=True, slots=True)
class BindDomainRevision:
    kind: DomainBindingKind
    object_id: UUID
    revision_id: UUID


@dataclass(frozen=True, slots=True)
class ReviseRecordLink:
    expected_current_revision_id: UUID
    content: RecordLinkContent
    change_reason: str


class CatalogLinkRepository(Protocol):
    def delete_link_type_draft(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        link_type_id: UUID,
        expected_revision_id: UUID,
    ) -> DraftDeleteResult: ...

    def link_type_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[LinkTypeContent]: ...

    def record_link_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[RecordLinkContent]: ...

    def list_link_types(
        self, *, context: SecurityContext, decision: AuthorizationDecision
    ) -> tuple[LinkTypeSnapshot, ...]: ...

    def get_link_type(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        link_type_id: UUID,
    ) -> LinkTypeSnapshot: ...

    def get_link_type_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        link_type_id: UUID,
        revision_id: UUID,
    ) -> ConfigRevision[LinkTypeContent]: ...

    def get_record_link(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        record_link_id: UUID,
    ) -> RecordLinkSnapshot: ...

    def list_record_links(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        record_id: UUID,
        record_revision_id: UUID | None,
        include_inactive: bool,
    ) -> tuple[RecordLinkSnapshot, ...]: ...

    def active_link_conflicts(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        content: RecordLinkContent,
        link_type: LinkTypeContent,
        exclude_link_id: UUID | None = None,
    ) -> bool: ...

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
    ) -> DomainRevisionBinding: ...

    def get_domain_binding(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        record_id: UUID,
        record_revision_id: UUID,
    ) -> DomainRevisionBinding | None: ...

    def list_domain_bindings(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        record_id: UUID,
        record_revision_id: UUID,
    ) -> tuple[DomainRevisionBinding, ...]: ...

    def find_domain_binding(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        kind: DomainBindingKind,
        object_id: UUID,
        revision_id: UUID,
    ) -> DomainRevisionBinding | None: ...


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
            "authorization decision does not match Catalog link request"
        )


def _reason(value: str) -> str:
    if not value or value != value.strip() or len(value) > 2000 or "\x00" in value:
        raise ValueError("change_reason must be trimmed and contain 1..2000 characters")
    return value


class CatalogLinkService:
    def __init__(
        self,
        repository: CatalogLinkRepository,
        schema_repository: ConfigurableCatalogRepository,
        record_repository: CatalogRecordRepository,
        *,
        id_factory: Callable[[], UUID] = uuid4,
    ) -> None:
        self._repository = repository
        self._schemas = schema_repository
        self._records = record_repository
        self._id = id_factory

    @staticmethod
    def _scope(context: SecurityContext, classification: DataClassification) -> TenantScope:
        return TenantScope(context.organization_id, context.project_id, classification.value)

    @staticmethod
    def _revision_service[ContentT](
        aggregate_type: str, store: RevisionStore[ContentT]
    ) -> RevisionService[ContentT]:
        return RevisionService(aggregate_type=aggregate_type, store=store)

    def delete_link_type_draft(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        link_type_id: UUID,
        command: DeleteDraft,
    ) -> None:
        _require(context, decision, Permission.CATALOG_WRITE)
        result = self._repository.delete_link_type_draft(
            context=context,
            decision=decision,
            link_type_id=link_type_id,
            expected_revision_id=command.expected_current_revision_id,
        )
        if result is DraftDeleteResult.DELETED:
            return
        if result is DraftDeleteResult.NOT_FOUND:
            raise ConfigurableCatalogNotFound("Link Type draft was not found")
        raise ConfigurableCatalogDraftDeleteBlocked(result.value)

    def _validate_link_type_tables(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        content: LinkTypeContent,
    ) -> None:
        source = self._schemas.get_table(
            context=context, decision=decision, table_id=content.source_table_id
        )
        target = self._schemas.get_table(
            context=context, decision=decision, table_id=content.target_table_id
        )
        if source.current.record.revision_id != content.source_table_revision_id:
            raise ConfigurableCatalogConflict(
                "Link Type must pin the current source Table revision"
            )
        if target.current.record.revision_id != content.target_table_revision_id:
            raise ConfigurableCatalogConflict(
                "Link Type must pin the current target Table revision"
            )

    def create_link_type(
        self, context: SecurityContext, decision: AuthorizationDecision, command: CreateLinkType
    ) -> LinkTypeSnapshot:
        _require(context, decision, Permission.CATALOG_WRITE)
        self._validate_link_type_tables(context, decision, command.content)
        aggregate_id = self._id()
        revision = self._revision_service(
            LINK_TYPE_AGGREGATE_TYPE, self._repository.link_type_store(context, decision)
        ).create(
            CreateRevisionedAggregate(
                aggregate_id=aggregate_id,
                scope=self._scope(context, command.classification),
                schema_id=LINK_TYPE_SCHEMA_ID,
                schema_version=SCHEMA_VERSION,
                content=command.content,
                created_by=context.principal.id,
                change_reason=_reason(command.change_reason),
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        return LinkTypeSnapshot(aggregate_id, ConfigRevision(revision, command.content))

    def revise_link_type(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        link_type_id: UUID,
        command: ReviseLinkType,
    ) -> LinkTypeSnapshot:
        _require(context, decision, Permission.CATALOG_WRITE)
        current = self._repository.get_link_type(
            context=context, decision=decision, link_type_id=link_type_id
        )
        if (
            current.current.content.key != command.content.key
            or current.current.content.source_table_id != command.content.source_table_id
            or current.current.content.target_table_id != command.content.target_table_id
        ):
            raise ConfigurableCatalogConflict(
                "Link Type key and endpoint Table identities cannot change; create a new Link Type"
            )
        self._validate_link_type_tables(context, decision, command.content)
        revision = self._revision_service(
            LINK_TYPE_AGGREGATE_TYPE, self._repository.link_type_store(context, decision)
        ).revise(
            ReviseAggregate(
                aggregate_id=link_type_id,
                scope=current.current.record.scope,
                expected_current_revision_id=command.expected_current_revision_id,
                based_on_revision_id=command.expected_current_revision_id,
                schema_id=LINK_TYPE_SCHEMA_ID,
                schema_version=SCHEMA_VERSION,
                content=command.content,
                created_by=context.principal.id,
                change_reason=_reason(command.change_reason),
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        return LinkTypeSnapshot(link_type_id, ConfigRevision(revision, command.content))

    def _record_endpoint(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        record_id: UUID,
        revision_id: UUID,
        *,
        published_only: bool = False,
        endpoint_cache: dict[tuple[UUID, UUID, bool], LinkEndpoint] | None = None,
    ) -> LinkEndpoint:
        cache_key = (record_id, revision_id, published_only)
        if endpoint_cache is not None:
            cached = endpoint_cache.get(cache_key)
            if cached is not None:
                return cached
        revision = self._records.get_record_revision(
            context=context,
            decision=decision,
            record_id=record_id,
            revision_id=revision_id,
        )
        table_revision = self._schemas.get_table_revision(
            context=context,
            decision=decision,
            table_id=revision.content.table_id,
            revision_id=revision.content.table_revision_id,
        )
        domain_bindings = self._repository.list_domain_bindings(
            context=context,
            decision=decision,
            record_id=record_id,
            record_revision_id=revision_id,
        )
        if published_only:
            published = self._records.search_records(
                context=context,
                decision=decision,
                query=CatalogRecordQuery(
                    table_id=revision.content.table_id,
                    record_id=record_id,
                    limit=1,
                    published_only=True,
                ),
            )
            if not any(
                item.id == record_id and item.current.record.revision_id == revision_id
                for item in published.items
            ):
                raise ConfigurableCatalogNotFound(
                    "Catalog Record revision is not published for Materials"
                )
            filtered_bindings: list[DomainRevisionBinding] = []
            for binding in domain_bindings:
                exact = self._records.search_records(
                    context=context,
                    decision=decision,
                    query=CatalogRecordQuery(
                        table_id=revision.content.table_id,
                        record_id=record_id,
                        limit=1,
                        published_only=True,
                        domain_binding_kind=binding.kind.value,
                        domain_binding_object_id=binding.object_id,
                        domain_binding_revision_id=binding.revision_id,
                    ),
                )
                if any(
                    item.id == record_id and item.current.record.revision_id == revision_id
                    for item in exact.items
                ):
                    filtered_bindings.append(binding)
            domain_bindings = tuple(filtered_bindings)
        endpoint = LinkEndpoint(
            record_id=record_id,
            record_revision_id=revision_id,
            revision_no=revision.record.revision_no,
            table_id=revision.content.table_id,
            name=revision.content.name,
            external_key=revision.content.external_key,
            domain_binding=domain_bindings[0] if domain_bindings else None,
            domain_bindings=domain_bindings,
            data_category=table_revision.content.data_category,
        )
        if endpoint_cache is not None:
            endpoint_cache[cache_key] = endpoint
        return endpoint

    def bind_domain_revision(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        record_id: UUID,
        record_revision_id: UUID,
        command: BindDomainRevision,
    ) -> DomainRevisionBinding:
        """Pin one configurable Record revision to one exact governed domain revision."""

        _require(context, decision, Permission.CATALOG_WRITE)
        record_revision = self._records.get_record_revision(
            context=context,
            decision=decision,
            record_id=record_id,
            revision_id=record_revision_id,
        )
        return self._repository.create_domain_binding(
            context=context,
            decision=decision,
            binding_id=self._id(),
            record_id=record_id,
            record_revision_id=record_revision_id,
            kind=command.kind,
            object_id=command.object_id,
            revision_id=command.revision_id,
            classification=record_revision.record.scope.classification,
        )

    def get_domain_binding(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        record_id: UUID,
        record_revision_id: UUID,
    ) -> DomainRevisionBinding | None:
        _require(context, decision, Permission.CATALOG_READ)
        self._records.get_record_revision(
            context=context,
            decision=decision,
            record_id=record_id,
            revision_id=record_revision_id,
        )
        return self._repository.get_domain_binding(
            context=context,
            decision=decision,
            record_id=record_id,
            record_revision_id=record_revision_id,
        )

    def list_domain_bindings(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        record_id: UUID,
        record_revision_id: UUID,
    ) -> tuple[DomainRevisionBinding, ...]:
        _require(context, decision, Permission.CATALOG_READ)
        self._records.get_record_revision(
            context=context,
            decision=decision,
            record_id=record_id,
            revision_id=record_revision_id,
        )
        return self._repository.list_domain_bindings(
            context=context,
            decision=decision,
            record_id=record_id,
            record_revision_id=record_revision_id,
        )

    def resolve_domain_binding(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        kind: DomainBindingKind,
        object_id: UUID,
        revision_id: UUID,
    ) -> DomainRevisionBinding | None:
        """Resolve an exact governed revision back to its configurable Catalog node."""

        _require(context, decision, Permission.CATALOG_READ)
        return self._repository.find_domain_binding(
            context=context,
            decision=decision,
            kind=kind,
            object_id=object_id,
            revision_id=revision_id,
        )

    def _validate_record_link(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        content: RecordLinkContent,
        *,
        exclude_link_id: UUID | None = None,
    ) -> ConfigRevision[LinkTypeContent]:
        link_type = self._repository.get_link_type(
            context=context, decision=decision, link_type_id=content.link_type_id
        )
        if link_type.current.record.revision_id != content.link_type_revision_id:
            raise ConfigurableCatalogConflict(
                "new Record Links must pin the current Link Type revision"
            )
        source = self._record_endpoint(
            context, decision, content.source_record_id, content.source_record_revision_id
        )
        target = self._record_endpoint(
            context, decision, content.target_record_id, content.target_record_revision_id
        )
        definition = link_type.current.content
        if source.table_id != definition.source_table_id:
            raise ConfigurableCatalogConflict("source Record Table is not allowed by the Link Type")
        if target.table_id != definition.target_table_id:
            raise ConfigurableCatalogConflict("target Record Table is not allowed by the Link Type")
        if content.active and self._repository.active_link_conflicts(
            context=context,
            decision=decision,
            content=content,
            link_type=definition,
            exclude_link_id=exclude_link_id,
        ):
            raise ConfigurableCatalogConflict(
                "Record Link conflicts with uniqueness or cardinality"
            )
        return link_type.current

    def create_record_link(
        self, context: SecurityContext, decision: AuthorizationDecision, command: CreateRecordLink
    ) -> RecordLinkSnapshot:
        _require(context, decision, Permission.CATALOG_WRITE)
        self._validate_record_link(context, decision, command.content)
        aggregate_id = self._id()
        revision = self._revision_service(
            RECORD_LINK_AGGREGATE_TYPE, self._repository.record_link_store(context, decision)
        ).create(
            CreateRevisionedAggregate(
                aggregate_id=aggregate_id,
                scope=self._scope(context, command.classification),
                schema_id=RECORD_LINK_SCHEMA_ID,
                schema_version=SCHEMA_VERSION,
                content=command.content,
                created_by=context.principal.id,
                change_reason=_reason(command.change_reason),
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        return RecordLinkSnapshot(aggregate_id, ConfigRevision(revision, command.content))

    def revise_record_link(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        record_link_id: UUID,
        command: ReviseRecordLink,
    ) -> RecordLinkSnapshot:
        _require(context, decision, Permission.CATALOG_WRITE)
        current = self._repository.get_record_link(
            context=context, decision=decision, record_link_id=record_link_id
        )
        old = current.current.content
        new = command.content
        if (
            old.link_type_id,
            old.source_record_id,
            old.target_record_id,
        ) != (
            new.link_type_id,
            new.source_record_id,
            new.target_record_id,
        ):
            raise ConfigurableCatalogConflict(
                "Record Link Type and stable endpoints are immutable; create a new relationship"
            )
        self._validate_record_link(
            context, decision, command.content, exclude_link_id=record_link_id
        )
        revision = self._revision_service(
            RECORD_LINK_AGGREGATE_TYPE, self._repository.record_link_store(context, decision)
        ).revise(
            ReviseAggregate(
                aggregate_id=record_link_id,
                scope=current.current.record.scope,
                expected_current_revision_id=command.expected_current_revision_id,
                based_on_revision_id=command.expected_current_revision_id,
                schema_id=RECORD_LINK_SCHEMA_ID,
                schema_version=SCHEMA_VERSION,
                content=command.content,
                created_by=context.principal.id,
                change_reason=_reason(command.change_reason),
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        return RecordLinkSnapshot(record_link_id, ConfigRevision(revision, command.content))

    def list_tables(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> tuple[TableSnapshot, ...]:
        _require(context, decision, Permission.CATALOG_READ)
        return self._schemas.list_tables(context=context, decision=decision)

    def explorer_children(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        table_id: UUID,
        parent_folder_id: UUID | None,
    ) -> CatalogExplorerChildren:
        _require(context, decision, Permission.CATALOG_READ)
        table = self._schemas.get_table(context=context, decision=decision, table_id=table_id)
        folders = tuple(
            folder
            for folder in self._records.list_folders(
                context=context, decision=decision, table_id=table_id
            )
            if folder.current.content.parent_folder_id == parent_folder_id
        )
        records = self._records.list_direct_records(
            context=context,
            decision=decision,
            table_id=table_id,
            folder_id=parent_folder_id,
        )
        return CatalogExplorerChildren(table, folders, records)

    def list_link_types(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> tuple[LinkTypeSnapshot, ...]:
        _require(context, decision, Permission.CATALOG_READ)
        return self._repository.list_link_types(context=context, decision=decision)

    def get_link_type_for_write(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        link_type_id: UUID,
    ) -> LinkTypeSnapshot:
        _require(context, decision, Permission.CATALOG_WRITE)
        return self._repository.get_link_type(
            context=context, decision=decision, link_type_id=link_type_id
        )

    def get_record_link_for_write(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        record_link_id: UUID,
    ) -> RecordLinkSnapshot:
        _require(context, decision, Permission.CATALOG_WRITE)
        return self._repository.get_record_link(
            context=context, decision=decision, record_link_id=record_link_id
        )

    def _view(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        link: RecordLinkSnapshot,
        *,
        published_only: bool = False,
        endpoint_cache: dict[tuple[UUID, UUID, bool], LinkEndpoint] | None = None,
        link_type_cache: dict[tuple[UUID, UUID], ConfigRevision[LinkTypeContent]] | None = None,
    ) -> RecordLinkView:
        content = link.current.content
        link_type_key = (content.link_type_id, content.link_type_revision_id)
        link_type = link_type_cache.get(link_type_key) if link_type_cache is not None else None
        if link_type is None:
            link_type = self._repository.get_link_type_revision(
                context=context,
                decision=decision,
                link_type_id=content.link_type_id,
                revision_id=content.link_type_revision_id,
            )
            if link_type_cache is not None:
                link_type_cache[link_type_key] = link_type
        return RecordLinkView(
            link,
            link_type,
            self._record_endpoint(
                context,
                decision,
                content.source_record_id,
                content.source_record_revision_id,
                published_only=published_only,
                endpoint_cache=endpoint_cache,
            ),
            self._record_endpoint(
                context,
                decision,
                content.target_record_id,
                content.target_record_revision_id,
                published_only=published_only,
                endpoint_cache=endpoint_cache,
            ),
        )

    def list_record_links(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        record_id: UUID,
        *,
        record_revision_id: UUID | None = None,
        include_inactive: bool = False,
        published_only: bool = False,
    ) -> tuple[RecordLinkView, ...]:
        return self._list_record_links(
            context,
            decision,
            record_id,
            record_revision_id=record_revision_id,
            include_inactive=include_inactive,
            published_only=published_only,
            endpoint_cache=None,
            link_type_cache=None,
        )

    def _list_record_links(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        record_id: UUID,
        *,
        record_revision_id: UUID | None = None,
        include_inactive: bool = False,
        published_only: bool = False,
        endpoint_cache: dict[tuple[UUID, UUID, bool], LinkEndpoint] | None,
        link_type_cache: dict[tuple[UUID, UUID], ConfigRevision[LinkTypeContent]] | None,
    ) -> tuple[RecordLinkView, ...]:
        _require(context, decision, Permission.CATALOG_READ)
        if published_only:
            self._record_endpoint(
                context,
                decision,
                record_id,
                record_revision_id
                if record_revision_id is not None
                else self._records.get_record(
                    context=context, decision=decision, record_id=record_id
                ).current.record.revision_id,
                published_only=True,
                endpoint_cache=endpoint_cache,
            )
        else:
            self._records.get_record(context=context, decision=decision, record_id=record_id)
        links = self._repository.list_record_links(
            context=context,
            decision=decision,
            record_id=record_id,
            record_revision_id=record_revision_id,
            include_inactive=include_inactive,
        )
        visible: list[RecordLinkView] = []
        for link in links:
            try:
                visible.append(
                    self._view(
                        context,
                        decision,
                        link,
                        published_only=published_only,
                        endpoint_cache=endpoint_cache,
                        link_type_cache=link_type_cache,
                    )
                )
            except ConfigurableCatalogNotFound:
                if not published_only:
                    raise
        return tuple(visible)

    def workflow_graph(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        record_id: UUID,
        revision_id: UUID,
        *,
        depth: int = 3,
        published_only: bool = False,
    ) -> WorkflowGraph:
        _require(context, decision, Permission.CATALOG_READ)
        if not 1 <= depth <= 8:
            raise ValueError("workflow depth must be between 1 and 8")
        endpoint_cache: dict[tuple[UUID, UUID, bool], LinkEndpoint] = {}
        link_type_cache: dict[tuple[UUID, UUID], ConfigRevision[LinkTypeContent]] = {}
        root = self._record_endpoint(
            context,
            decision,
            record_id,
            revision_id,
            published_only=published_only,
            endpoint_cache=endpoint_cache,
        )
        nodes: dict[tuple[UUID, UUID], LinkEndpoint] = {
            (root.record_id, root.record_revision_id): root
        }
        links: dict[UUID, RecordLinkView] = {}
        queue: deque[tuple[LinkEndpoint, int]] = deque([(root, 0)])
        expanded: set[tuple[UUID, UUID]] = set()
        while queue:
            endpoint, level = queue.popleft()
            key = (endpoint.record_id, endpoint.record_revision_id)
            if key in expanded or level >= depth:
                continue
            expanded.add(key)
            for view in self._list_record_links(
                context,
                decision,
                endpoint.record_id,
                record_revision_id=endpoint.record_revision_id,
                published_only=published_only,
                endpoint_cache=endpoint_cache,
                link_type_cache=link_type_cache,
            ):
                links[view.link.id] = view
                for candidate in (view.source, view.target):
                    candidate_key = (candidate.record_id, candidate.record_revision_id)
                    if candidate_key not in nodes:
                        nodes[candidate_key] = candidate
                        queue.append((candidate, level + 1))
        return WorkflowGraph(root, tuple(nodes.values()), tuple(links.values()))

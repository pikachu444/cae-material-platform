"""HTTP API for dual Catalog explorers and revision-pinned Record Links (T-51)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends, FastAPI, Header, Query, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from sqlalchemy.exc import IntegrityError

from cmp.modules.catalog.adapters.api.catalog import CatalogHttpError, _etag, _scope
from cmp.modules.catalog.adapters.api.configurable import TableResponse
from cmp.modules.catalog.adapters.api.records import FolderResponse, RecordResponse
from cmp.modules.catalog.application.configurable import ConfigRevision
from cmp.modules.catalog.application.links import (
    BindDomainRevision,
    CatalogExplorerChildren,
    CatalogLinkService,
    CreateLinkType,
    CreateRecordLink,
    DomainBindingKind,
    DomainRevisionBinding,
    LinkEndpoint,
    LinkTypeSnapshot,
    RecordLinkSnapshot,
    RecordLinkView,
    ReviseLinkType,
    ReviseRecordLink,
    WorkflowGraph,
)
from cmp.modules.catalog.domain.configurable import (
    ConfigurableCatalogConflict,
    ConfigurableCatalogNotFound,
)
from cmp.modules.catalog.domain.links import LinkCardinality, LinkTypeContent, RecordLinkContent
from cmp.modules.identity_access.domain.authorization import DataClassification
from cmp.shared.contracts.revisions import (
    InvalidRevisionETag,
    RevisionETag,
    RevisionMetadataResponse,
    RevisionPreconditionFailed,
    require_matching_if_match,
)
from cmp.shared.domain.revisions import RevisionConflict, RevisionKernelError

type Dependency = Callable[..., object]
type ShortText = Annotated[str, StringConstraints(min_length=1, max_length=200)]


class LinkTypeContentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{0,63}$")]
    name: ShortText
    source_table_id: UUID
    source_table_revision_id: UUID
    target_table_id: UUID
    target_table_revision_id: UUID
    forward_label: ShortText
    reverse_label: ShortText
    source_cardinality: LinkCardinality = LinkCardinality.MANY
    target_cardinality: LinkCardinality = LinkCardinality.MANY
    description: Annotated[str | None, StringConstraints(min_length=1, max_length=2000)] = None

    def to_domain(self) -> LinkTypeContent:
        return LinkTypeContent(
            self.key,
            self.name,
            self.source_table_id,
            self.source_table_revision_id,
            self.target_table_id,
            self.target_table_revision_id,
            self.forward_label,
            self.reverse_label,
            self.source_cardinality,
            self.target_cardinality,
            self.description,
        )


class LinkTypeCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    classification: DataClassification = DataClassification.INTERNAL
    content: LinkTypeContentInput
    change_reason: Annotated[str, StringConstraints(min_length=1, max_length=2000)]


class LinkTypeReviseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    content: LinkTypeContentInput
    change_reason: Annotated[str, StringConstraints(min_length=1, max_length=2000)]


class LinkTypeRevisionResponse(RevisionMetadataResponse):
    content: LinkTypeContentInput

    @classmethod
    def from_revision(cls, value: ConfigRevision[LinkTypeContent]) -> LinkTypeRevisionResponse:
        return cls(
            **RevisionMetadataResponse.from_record(value.record, "draft").model_dump(),
            content=LinkTypeContentInput(
                key=value.content.key,
                name=value.content.name,
                source_table_id=value.content.source_table_id,
                source_table_revision_id=value.content.source_table_revision_id,
                target_table_id=value.content.target_table_id,
                target_table_revision_id=value.content.target_table_revision_id,
                forward_label=value.content.forward_label,
                reverse_label=value.content.reverse_label,
                source_cardinality=value.content.source_cardinality,
                target_cardinality=value.content.target_cardinality,
                description=value.content.description,
            ),
        )


class LinkTypeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    link_type_id: UUID
    current_revision: LinkTypeRevisionResponse

    @classmethod
    def from_snapshot(cls, value: LinkTypeSnapshot) -> LinkTypeResponse:
        return cls(
            link_type_id=value.id,
            current_revision=LinkTypeRevisionResponse.from_revision(value.current),
        )


class LinkTypeListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: tuple[LinkTypeResponse, ...]


class RecordLinkContentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    link_type_id: UUID
    link_type_revision_id: UUID
    source_record_id: UUID
    source_record_revision_id: UUID
    target_record_id: UUID
    target_record_revision_id: UUID
    active: bool = True
    note: Annotated[str | None, StringConstraints(min_length=1, max_length=2000)] = None

    def to_domain(self) -> RecordLinkContent:
        return RecordLinkContent(
            self.link_type_id,
            self.link_type_revision_id,
            self.source_record_id,
            self.source_record_revision_id,
            self.target_record_id,
            self.target_record_revision_id,
            self.active,
            self.note,
        )

    @classmethod
    def from_domain(cls, value: RecordLinkContent) -> RecordLinkContentInput:
        return cls(
            link_type_id=value.link_type_id,
            link_type_revision_id=value.link_type_revision_id,
            source_record_id=value.source_record_id,
            source_record_revision_id=value.source_record_revision_id,
            target_record_id=value.target_record_id,
            target_record_revision_id=value.target_record_revision_id,
            active=value.active,
            note=value.note,
        )


class RecordLinkCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    classification: DataClassification = DataClassification.INTERNAL
    content: RecordLinkContentInput
    change_reason: Annotated[str, StringConstraints(min_length=1, max_length=2000)]


class RecordLinkReviseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    content: RecordLinkContentInput
    change_reason: Annotated[str, StringConstraints(min_length=1, max_length=2000)]


class RecordLinkRevisionResponse(RevisionMetadataResponse):
    content: RecordLinkContentInput

    @classmethod
    def from_snapshot(cls, value: RecordLinkSnapshot) -> RecordLinkRevisionResponse:
        return cls(
            **RevisionMetadataResponse.from_record(value.current.record, "draft").model_dump(),
            content=RecordLinkContentInput.from_domain(value.current.content),
        )


class RecordLinkResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    record_link_id: UUID
    current_revision: RecordLinkRevisionResponse

    @classmethod
    def from_snapshot(cls, value: RecordLinkSnapshot) -> RecordLinkResponse:
        return cls(
            record_link_id=value.id,
            current_revision=RecordLinkRevisionResponse.from_snapshot(value),
        )


class DomainRevisionBindingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: DomainBindingKind
    object_id: UUID
    revision_id: UUID


class DomainRevisionBindingResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    binding_id: UUID
    record_id: UUID
    record_revision_id: UUID
    kind: DomainBindingKind
    object_id: UUID
    revision_id: UUID
    workbench_path: str

    @classmethod
    def from_domain(cls, value: DomainRevisionBinding) -> DomainRevisionBindingResponse:
        return cls(
            binding_id=value.id,
            record_id=value.record_id,
            record_revision_id=value.record_revision_id,
            kind=value.kind,
            object_id=value.object_id,
            revision_id=value.revision_id,
            workbench_path=value.workbench_path,
        )


class LinkEndpointResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    record_id: UUID
    record_revision_id: UUID
    revision_no: int = Field(ge=1)
    table_id: UUID
    name: str
    external_key: str | None
    domain_binding: DomainRevisionBindingResponse | None = None
    domain_bindings: tuple[DomainRevisionBindingResponse, ...] = ()

    @classmethod
    def from_endpoint(cls, value: LinkEndpoint) -> LinkEndpointResponse:
        return cls(
            record_id=value.record_id,
            record_revision_id=value.record_revision_id,
            revision_no=value.revision_no,
            table_id=value.table_id,
            name=value.name,
            external_key=value.external_key,
            domain_binding=(
                None
                if value.domain_binding is None
                else DomainRevisionBindingResponse.from_domain(value.domain_binding)
            ),
            domain_bindings=tuple(
                DomainRevisionBindingResponse.from_domain(binding)
                for binding in value.domain_bindings
            ),
        )


class RecordLinkViewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    record_link_id: UUID
    current_revision: RecordLinkRevisionResponse
    link_type_revision: LinkTypeRevisionResponse
    source: LinkEndpointResponse
    target: LinkEndpointResponse

    @classmethod
    def from_view(cls, value: RecordLinkView) -> RecordLinkViewResponse:
        return cls(
            record_link_id=value.link.id,
            current_revision=RecordLinkRevisionResponse.from_snapshot(value.link),
            link_type_revision=LinkTypeRevisionResponse.from_revision(value.link_type),
            source=LinkEndpointResponse.from_endpoint(value.source),
            target=LinkEndpointResponse.from_endpoint(value.target),
        )


class RecordLinkListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: tuple[RecordLinkViewResponse, ...]


class DomainRevisionBindingListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: tuple[DomainRevisionBindingResponse, ...]


class ExplorerTableListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: tuple[TableResponse, ...]


class ExplorerChildrenResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    table: TableResponse
    folders: tuple[FolderResponse, ...]
    records: tuple[RecordResponse, ...]

    @classmethod
    def from_children(cls, value: CatalogExplorerChildren) -> ExplorerChildrenResponse:
        return cls(
            table=TableResponse.from_snapshot(value.table),
            folders=tuple(FolderResponse.from_snapshot(item) for item in value.folders),
            records=tuple(RecordResponse.from_snapshot(item) for item in value.records),
        )


class WorkflowGraphResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    root: LinkEndpointResponse
    nodes: tuple[LinkEndpointResponse, ...]
    links: tuple[RecordLinkViewResponse, ...]

    @classmethod
    def from_graph(cls, value: WorkflowGraph) -> WorkflowGraphResponse:
        return cls(
            root=LinkEndpointResponse.from_endpoint(value.root),
            nodes=tuple(LinkEndpointResponse.from_endpoint(item) for item in value.nodes),
            links=tuple(RecordLinkViewResponse.from_view(item) for item in value.links),
        )


def _error(context: Any, error: Exception) -> CatalogHttpError:
    if isinstance(error, ConfigurableCatalogNotFound):
        return CatalogHttpError(
            context=context,
            status_code=404,
            title="Catalog link resource not found",
            detail="No Link Type, Record Link or exact endpoint revision is visible in this scope.",
            code="CMP-CATALOG-0015",
        )
    if isinstance(error, (InvalidRevisionETag, ValueError)):
        return CatalogHttpError(
            context=context,
            status_code=422,
            title="Invalid Catalog link request",
            detail="The request must use explicit UUID revisions and valid Link Type fields.",
            code="CMP-CATALOG-0016",
        )
    if isinstance(error, RevisionPreconditionFailed):
        return CatalogHttpError(
            context=context,
            status_code=412,
            title="Catalog link revision precondition failed",
            detail="Reload the current immutable revision before retrying.",
            code="CMP-CATALOG-0017",
            current_etag=RevisionETag.from_ref(error.current),
        )
    if isinstance(
        error, (ConfigurableCatalogConflict, RevisionConflict, RevisionKernelError, IntegrityError)
    ):
        return CatalogHttpError(
            context=context,
            status_code=409,
            title="Catalog link conflict",
            detail=(
                "The command conflicts with endpoint Tables, cardinality, scope or exact revisions."
            ),
            code="CMP-CATALOG-0018",
        )
    return CatalogHttpError(
        context=context,
        status_code=409,
        title="Catalog link command rejected",
        detail="The Catalog link command could not be completed.",
        code="CMP-CATALOG-0018",
    )


def install_catalog_link_api(
    application: FastAPI,
    *,
    service: CatalogLinkService | None,
    security_dependency: Dependency,
    read_dependency: Dependency,
    write_dependency: Dependency,
) -> None:
    def required(context: Any) -> CatalogLinkService:
        if service is None:
            raise CatalogHttpError(
                context=context,
                status_code=503,
                title="Catalog Explorer unavailable",
                detail="The authoritative Catalog link store is not configured.",
                code="CMP-CATALOG-0019",
            )
        return service

    @application.get(
        "/api/v1/catalog/explorer/tables",
        response_model=ExplorerTableListResponse,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["catalog-explorer"],
    )
    def list_explorer_tables(request: Request) -> ExplorerTableListResponse:
        context, decision = _scope(request)
        try:
            values = required(context).list_tables(context, decision)
            return ExplorerTableListResponse(
                items=tuple(TableResponse.from_snapshot(item) for item in values)
            )
        except CatalogHttpError:
            raise
        except Exception as error:
            raise _error(context, error) from error

    @application.get(
        "/api/v1/catalog/explorer/tables/{table_id}/children",
        response_model=ExplorerChildrenResponse,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["catalog-explorer"],
    )
    def explorer_children(
        request: Request,
        table_id: UUID,
        parent_folder_id: Annotated[UUID | None, Query()] = None,
    ) -> ExplorerChildrenResponse:
        context, decision = _scope(request)
        try:
            return ExplorerChildrenResponse.from_children(
                required(context).explorer_children(context, decision, table_id, parent_folder_id)
            )
        except CatalogHttpError:
            raise
        except Exception as error:
            raise _error(context, error) from error

    @application.get(
        "/api/v1/catalog/link-types",
        response_model=LinkTypeListResponse,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["catalog-links"],
    )
    def list_link_types(request: Request) -> LinkTypeListResponse:
        context, decision = _scope(request)
        try:
            values = required(context).list_link_types(context, decision)
            return LinkTypeListResponse(
                items=tuple(LinkTypeResponse.from_snapshot(item) for item in values)
            )
        except CatalogHttpError:
            raise
        except Exception as error:
            raise _error(context, error) from error

    @application.post(
        "/api/v1/catalog/link-types",
        response_model=LinkTypeResponse,
        status_code=status.HTTP_201_CREATED,
        dependencies=[Depends(security_dependency), Depends(write_dependency)],
        tags=["catalog-links"],
    )
    def create_link_type(
        request: Request, response: Response, body: LinkTypeCreateRequest
    ) -> LinkTypeResponse:
        context, decision = _scope(request)
        try:
            value = required(context).create_link_type(
                context,
                decision,
                CreateLinkType(body.classification, body.content.to_domain(), body.change_reason),
            )
            _etag(response, value.current.record)
            return LinkTypeResponse.from_snapshot(value)
        except CatalogHttpError:
            raise
        except Exception as error:
            raise _error(context, error) from error

    @application.post(
        "/api/v1/catalog/link-types/{link_type_id}/revisions",
        response_model=LinkTypeResponse,
        status_code=status.HTTP_201_CREATED,
        dependencies=[Depends(security_dependency), Depends(write_dependency)],
        tags=["catalog-links"],
    )
    def revise_link_type(
        request: Request,
        response: Response,
        link_type_id: UUID,
        body: LinkTypeReviseRequest,
        if_match: Annotated[str | None, Header(alias="If-Match")] = None,
    ) -> LinkTypeResponse:
        context, decision = _scope(request)
        try:
            current = required(context).get_link_type_for_write(context, decision, link_type_id)
            expected = require_matching_if_match(if_match, current.current.record.ref)
            value = required(context).revise_link_type(
                context,
                decision,
                link_type_id,
                ReviseLinkType(expected, body.content.to_domain(), body.change_reason),
            )
            _etag(response, value.current.record)
            return LinkTypeResponse.from_snapshot(value)
        except CatalogHttpError:
            raise
        except Exception as error:
            raise _error(context, error) from error

    @application.get(
        "/api/v1/catalog/records/{record_id}/links",
        response_model=RecordLinkListResponse,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["catalog-links"],
    )
    def list_record_links(
        request: Request,
        record_id: UUID,
        revision_id: Annotated[UUID | None, Query()] = None,
        include_inactive: Annotated[bool, Query()] = False,
    ) -> RecordLinkListResponse:
        context, decision = _scope(request)
        try:
            values = required(context).list_record_links(
                context,
                decision,
                record_id,
                record_revision_id=revision_id,
                include_inactive=include_inactive,
            )
            return RecordLinkListResponse(
                items=tuple(RecordLinkViewResponse.from_view(item) for item in values)
            )
        except CatalogHttpError:
            raise
        except Exception as error:
            raise _error(context, error) from error

    @application.post(
        "/api/v1/catalog/record-links",
        response_model=RecordLinkResponse,
        status_code=status.HTTP_201_CREATED,
        dependencies=[Depends(security_dependency), Depends(write_dependency)],
        tags=["catalog-links"],
    )
    def create_record_link(
        request: Request, response: Response, body: RecordLinkCreateRequest
    ) -> RecordLinkResponse:
        context, decision = _scope(request)
        try:
            value = required(context).create_record_link(
                context,
                decision,
                CreateRecordLink(body.classification, body.content.to_domain(), body.change_reason),
            )
            _etag(response, value.current.record)
            return RecordLinkResponse.from_snapshot(value)
        except CatalogHttpError:
            raise
        except Exception as error:
            raise _error(context, error) from error

    @application.post(
        "/api/v1/catalog/record-links/{record_link_id}/revisions",
        response_model=RecordLinkResponse,
        status_code=status.HTTP_201_CREATED,
        dependencies=[Depends(security_dependency), Depends(write_dependency)],
        tags=["catalog-links"],
    )
    def revise_record_link(
        request: Request,
        response: Response,
        record_link_id: UUID,
        body: RecordLinkReviseRequest,
        if_match: Annotated[str | None, Header(alias="If-Match")] = None,
    ) -> RecordLinkResponse:
        context, decision = _scope(request)
        try:
            current = required(context).get_record_link_for_write(context, decision, record_link_id)
            expected = require_matching_if_match(if_match, current.current.record.ref)
            value = required(context).revise_record_link(
                context,
                decision,
                record_link_id,
                ReviseRecordLink(expected, body.content.to_domain(), body.change_reason),
            )
            _etag(response, value.current.record)
            return RecordLinkResponse.from_snapshot(value)
        except CatalogHttpError:
            raise
        except Exception as error:
            raise _error(context, error) from error

    @application.post(
        "/api/v1/catalog/records/{record_id}/revisions/{revision_id}/domain-binding",
        response_model=DomainRevisionBindingResponse,
        status_code=status.HTTP_201_CREATED,
        dependencies=[Depends(security_dependency), Depends(write_dependency)],
        tags=["catalog-explorer"],
    )
    def bind_domain_revision(
        request: Request,
        record_id: UUID,
        revision_id: UUID,
        body: DomainRevisionBindingRequest,
    ) -> DomainRevisionBindingResponse:
        context, decision = _scope(request)
        try:
            value = required(context).bind_domain_revision(
                context,
                decision,
                record_id,
                revision_id,
                BindDomainRevision(body.kind, body.object_id, body.revision_id),
            )
            return DomainRevisionBindingResponse.from_domain(value)
        except CatalogHttpError:
            raise
        except Exception as error:
            raise _error(context, error) from error

    @application.get(
        "/api/v1/catalog/records/{record_id}/revisions/{revision_id}/domain-binding",
        response_model=DomainRevisionBindingResponse | None,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["catalog-explorer"],
    )
    def get_domain_revision_binding(
        request: Request, record_id: UUID, revision_id: UUID
    ) -> DomainRevisionBindingResponse | None:
        context, decision = _scope(request)
        try:
            value = required(context).get_domain_binding(context, decision, record_id, revision_id)
            return None if value is None else DomainRevisionBindingResponse.from_domain(value)
        except CatalogHttpError:
            raise
        except Exception as error:
            raise _error(context, error) from error

    @application.get(
        "/api/v1/catalog/records/{record_id}/revisions/{revision_id}/domain-bindings",
        response_model=DomainRevisionBindingListResponse,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["catalog-explorer"],
    )
    def list_domain_revision_bindings(
        request: Request, record_id: UUID, revision_id: UUID
    ) -> DomainRevisionBindingListResponse:
        context, decision = _scope(request)
        try:
            values = required(context).list_domain_bindings(
                context, decision, record_id, revision_id
            )
            return DomainRevisionBindingListResponse(
                items=tuple(DomainRevisionBindingResponse.from_domain(value) for value in values)
            )
        except CatalogHttpError:
            raise
        except Exception as error:
            raise _error(context, error) from error

    @application.get(
        "/api/v1/catalog/domain-bindings:resolve",
        response_model=DomainRevisionBindingResponse | None,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["catalog-explorer"],
    )
    def resolve_domain_revision_binding(
        request: Request,
        kind: DomainBindingKind,
        object_id: UUID,
        revision_id: UUID,
    ) -> DomainRevisionBindingResponse | None:
        context, decision = _scope(request)
        try:
            value = required(context).resolve_domain_binding(
                context, decision, kind, object_id, revision_id
            )
            return None if value is None else DomainRevisionBindingResponse.from_domain(value)
        except CatalogHttpError:
            raise
        except Exception as error:
            raise _error(context, error) from error

    @application.get(
        "/api/v1/catalog/workflow-explorer/{record_id}/revisions/{revision_id}",
        response_model=WorkflowGraphResponse,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["catalog-explorer"],
    )
    def workflow_graph(
        request: Request,
        record_id: UUID,
        revision_id: UUID,
        depth: int = Query(default=3, ge=1, le=8),
        published_only: bool = Query(default=False),
    ) -> WorkflowGraphResponse:
        context, decision = _scope(request)
        try:
            return WorkflowGraphResponse.from_graph(
                required(context).workflow_graph(
                    context,
                    decision,
                    record_id,
                    revision_id,
                    depth=depth,
                    published_only=published_only,
                )
            )
        except CatalogHttpError:
            raise
        except Exception as error:
            raise _error(context, error) from error

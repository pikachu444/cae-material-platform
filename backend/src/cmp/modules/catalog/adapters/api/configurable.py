"""Protected HTTP API for configurable Catalog schema administration (T-49)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends, FastAPI, Header, Request, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from sqlalchemy.exc import IntegrityError

from cmp.modules.catalog.adapters.api.catalog import CatalogHttpError, _etag, _scope
from cmp.modules.catalog.application.configurable import (
    AttributeSnapshot,
    ConfigurableCatalogService,
    CreateAttribute,
    CreateLayout,
    CreateSubset,
    CreateTable,
    LayoutSnapshot,
    ReviseAttribute,
    ReviseLayout,
    ReviseSubset,
    ReviseTable,
    SubsetSnapshot,
    TableSnapshot,
)
from cmp.modules.catalog.domain.configurable import (
    AttributeDataType,
    AttributeDefinitionContent,
    CatalogTableContent,
    ConfigurableCatalogConflict,
    ConfigurableCatalogNotFound,
    LayoutContent,
    LayoutItem,
    SubsetContent,
)
from cmp.modules.identity_access.domain.authorization import DataClassification
from cmp.shared.contracts.revisions import (
    InvalidRevisionETag,
    RevisionETag,
    RevisionMetadataResponse,
    RevisionPreconditionFailed,
    require_matching_if_match,
)
from cmp.shared.domain.revisions import RevisionConflict, RevisionKernelError

type Label = Annotated[str, StringConstraints(min_length=1, max_length=255)]
type Dependency = Callable[..., object]


class TableContentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{0,63}$")]
    name: Annotated[str, StringConstraints(min_length=1, max_length=200)]
    description: Annotated[str | None, StringConstraints(min_length=1, max_length=4000)] = None

    def to_domain(self) -> CatalogTableContent:
        return CatalogTableContent(self.key, self.name, self.description)


class TableCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    classification: DataClassification = DataClassification.INTERNAL
    content: TableContentInput
    change_reason: Annotated[str, StringConstraints(min_length=1, max_length=2000)]


class TableReviseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    content: TableContentInput
    change_reason: Annotated[str, StringConstraints(min_length=1, max_length=2000)]


class AttributeContentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    table_revision_id: UUID
    key: Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{0,63}$")]
    name: Annotated[str, StringConstraints(min_length=1, max_length=200)]
    data_type: AttributeDataType
    required: bool = False
    quantity_semantics: Annotated[str | None, StringConstraints(min_length=1, max_length=255)] = (
        None
    )
    normalized_unit: Annotated[str | None, StringConstraints(min_length=1, max_length=64)] = None
    minimum_number: float | None = None
    maximum_number: float | None = None
    minimum_length: int | None = Field(default=None, ge=0)
    maximum_length: int | None = Field(default=None, ge=1)
    pattern: Annotated[str | None, StringConstraints(min_length=1, max_length=500)] = None
    allowed_values: tuple[Annotated[str, StringConstraints(min_length=1, max_length=255)], ...] = ()
    reference_table_id: UUID | None = None
    help_text: Annotated[str | None, StringConstraints(min_length=1, max_length=2000)] = None

    def to_domain(self, table_id: UUID) -> AttributeDefinitionContent:
        return AttributeDefinitionContent(
            table_id=table_id,
            table_revision_id=self.table_revision_id,
            key=self.key,
            name=self.name,
            data_type=self.data_type,
            required=self.required,
            quantity_semantics=self.quantity_semantics,
            normalized_unit=self.normalized_unit,
            minimum_number=self.minimum_number,
            maximum_number=self.maximum_number,
            minimum_length=self.minimum_length,
            maximum_length=self.maximum_length,
            pattern=self.pattern,
            allowed_values=self.allowed_values,
            reference_table_id=self.reference_table_id,
            help_text=self.help_text,
        )


class AttributeCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    content: AttributeContentInput
    change_reason: Annotated[str, StringConstraints(min_length=1, max_length=2000)]


class LayoutItemInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    attribute_definition_id: UUID
    attribute_definition_revision_id: UUID
    section: Annotated[str, StringConstraints(min_length=1, max_length=100)] = "General"
    ordinal: int = Field(ge=0)

    def to_domain(self) -> LayoutItem:
        return LayoutItem(
            self.attribute_definition_id,
            self.attribute_definition_revision_id,
            self.section,
            self.ordinal,
        )


class LayoutCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    table_revision_id: UUID
    name: Annotated[str, StringConstraints(min_length=1, max_length=200)]
    description: Annotated[str | None, StringConstraints(min_length=1, max_length=2000)] = None
    items: tuple[LayoutItemInput, ...] = ()
    change_reason: Annotated[str, StringConstraints(min_length=1, max_length=2000)]

    def to_domain(self, table_id: UUID) -> LayoutContent:
        return LayoutContent(
            table_id,
            self.table_revision_id,
            self.name,
            self.description,
            tuple(item.to_domain() for item in self.items),
        )


class SubsetCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    table_revision_id: UUID
    name: Annotated[str, StringConstraints(min_length=1, max_length=200)]
    description: Annotated[str | None, StringConstraints(min_length=1, max_length=2000)] = None
    filter_definition: dict[str, Any] | None = None
    change_reason: Annotated[str, StringConstraints(min_length=1, max_length=2000)]

    def to_domain(self, table_id: UUID) -> SubsetContent:
        return SubsetContent(
            table_id,
            self.table_revision_id,
            self.name,
            self.description,
            self.filter_definition,
        )


class TableRevisionResponse(RevisionMetadataResponse):
    content: TableContentInput

    @classmethod
    def from_snapshot(cls, value: TableSnapshot) -> TableRevisionResponse:
        revision = value.current
        return cls(
            **RevisionMetadataResponse.from_record(revision.record, "draft").model_dump(),
            content=TableContentInput(
                key=revision.content.key,
                name=revision.content.name,
                description=revision.content.description,
            ),
        )


class TableResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    table_id: UUID
    current_revision: TableRevisionResponse

    @classmethod
    def from_snapshot(cls, value: TableSnapshot) -> TableResponse:
        return cls(table_id=value.id, current_revision=TableRevisionResponse.from_snapshot(value))


class TableListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: tuple[TableResponse, ...]


class AttributeRevisionResponse(RevisionMetadataResponse):
    content: AttributeContentInput

    @classmethod
    def from_snapshot(cls, value: AttributeSnapshot) -> AttributeRevisionResponse:
        revision = value.current
        content = revision.content
        return cls(
            **RevisionMetadataResponse.from_record(revision.record, "draft").model_dump(),
            content=AttributeContentInput(
                table_revision_id=content.table_revision_id,
                key=content.key,
                name=content.name,
                data_type=content.data_type,
                required=content.required,
                quantity_semantics=content.quantity_semantics,
                normalized_unit=content.normalized_unit,
                minimum_number=content.minimum_number,
                maximum_number=content.maximum_number,
                minimum_length=content.minimum_length,
                maximum_length=content.maximum_length,
                pattern=content.pattern,
                allowed_values=content.allowed_values,
                reference_table_id=content.reference_table_id,
                help_text=content.help_text,
            ),
        )


class AttributeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    attribute_definition_id: UUID
    table_id: UUID
    current_revision: AttributeRevisionResponse

    @classmethod
    def from_snapshot(cls, value: AttributeSnapshot) -> AttributeResponse:
        return cls(
            attribute_definition_id=value.id,
            table_id=value.table_id,
            current_revision=AttributeRevisionResponse.from_snapshot(value),
        )


class AttributeListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: tuple[AttributeResponse, ...]


class LayoutResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    layout_id: UUID
    table_id: UUID
    revision: RevisionMetadataResponse
    name: str
    description: str | None
    items: tuple[LayoutItemInput, ...]

    @classmethod
    def from_snapshot(cls, value: LayoutSnapshot) -> LayoutResponse:
        content = value.current.content
        return cls(
            layout_id=value.id,
            table_id=value.table_id,
            revision=RevisionMetadataResponse.from_record(value.current.record, "draft"),
            name=content.name,
            description=content.description,
            items=tuple(
                LayoutItemInput(
                    attribute_definition_id=item.attribute_definition_id,
                    attribute_definition_revision_id=item.attribute_definition_revision_id,
                    section=item.section,
                    ordinal=item.ordinal,
                )
                for item in content.items
            ),
        )


class SubsetResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    subset_id: UUID
    table_id: UUID
    revision: RevisionMetadataResponse
    name: str
    description: str | None
    filter_definition: dict[str, Any] | None

    @classmethod
    def from_snapshot(cls, value: SubsetSnapshot) -> SubsetResponse:
        content = value.current.content
        return cls(
            subset_id=value.id,
            table_id=value.table_id,
            revision=RevisionMetadataResponse.from_record(value.current.record, "draft"),
            name=content.name,
            description=content.description,
            filter_definition=content.filter_definition,
        )


class LayoutListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: tuple[LayoutResponse, ...]


class SubsetListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: tuple[SubsetResponse, ...]


def _error(context: Any, error: Exception) -> CatalogHttpError:
    if isinstance(error, ConfigurableCatalogNotFound):
        return CatalogHttpError(
            context=context,
            status_code=404,
            title="Configurable Catalog resource not found",
            detail="No schema resource is visible in the selected tenant context.",
            code="CMP-CATALOG-0001",
        )
    if isinstance(error, (InvalidRevisionETag, ValueError)):
        return CatalogHttpError(
            context=context,
            status_code=422,
            title="Invalid configurable Catalog request",
            detail="The request does not satisfy the typed schema contract.",
            code="CMP-CATALOG-0002",
        )
    if isinstance(error, RevisionPreconditionFailed):
        return CatalogHttpError(
            context=context,
            status_code=412,
            title="Revision precondition failed",
            detail="Reload the current schema revision before retrying.",
            code="CMP-CATALOG-0003",
            current_etag=RevisionETag.from_ref(error.current),
        )
    if isinstance(
        error, (ConfigurableCatalogConflict, RevisionConflict, RevisionKernelError, IntegrityError)
    ):
        return CatalogHttpError(
            context=context,
            status_code=409,
            title="Configurable Catalog conflict",
            detail="The command conflicts with an immutable schema identity or revision.",
            code="CMP-CATALOG-0004",
        )
    return CatalogHttpError(
        context=context,
        status_code=409,
        title="Configurable Catalog command rejected",
        detail="The schema command could not be completed.",
        code="CMP-CATALOG-0004",
    )


def install_configurable_catalog_api(
    application: FastAPI,
    *,
    service: ConfigurableCatalogService | None,
    security_dependency: Dependency,
    read_dependency: Dependency,
    write_dependency: Dependency,
) -> None:
    common: dict[int | str, dict[str, Any]] = {
        401: {"description": "Authentication required."},
        403: {"description": "Authorization denied."},
    }

    if CatalogHttpError not in application.exception_handlers:

        @application.exception_handler(CatalogHttpError)
        async def configurable_catalog_error_handler(
            request: Request, error: CatalogHttpError
        ) -> JSONResponse:
            del request
            headers = {
                "Cache-Control": "no-store",
                "X-Request-ID": str(error.context.request_id),
            }
            if error.current_etag is not None:
                headers["ETag"] = str(error.current_etag)
            return JSONResponse(
                status_code=error.problem.status,
                content=error.problem.model_dump(mode="json"),
                media_type="application/problem+json",
                headers=headers,
            )

    def required(context: Any) -> ConfigurableCatalogService:
        if service is None:
            raise CatalogHttpError(
                context=context,
                status_code=503,
                title="Configurable Catalog unavailable",
                detail="The authoritative Catalog schema store is not configured.",
                code="CMP-CATALOG-0006",
            )
        return service

    @application.get(
        "/api/v1/catalog/tables",
        operation_id="listConfigurableCatalogTables",
        response_model=TableListResponse,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["catalog-schema"],
    )
    def list_tables(request: Request) -> TableListResponse:
        context, decision = _scope(request)
        try:
            values = required(context).list_tables(context, decision)
            return TableListResponse(
                items=tuple(TableResponse.from_snapshot(item) for item in values)
            )
        except CatalogHttpError:
            raise
        except Exception as error:
            raise _error(context, error) from error

    @application.post(
        "/api/v1/catalog/tables",
        operation_id="createConfigurableCatalogTable",
        response_model=TableResponse,
        status_code=status.HTTP_201_CREATED,
        responses=common,
        dependencies=[Depends(security_dependency), Depends(write_dependency)],
        tags=["catalog-schema"],
    )
    def create_table(
        request: Request, response: Response, body: TableCreateRequest
    ) -> TableResponse:
        context, decision = _scope(request)
        try:
            value = required(context).create_table(
                context,
                decision,
                CreateTable(body.classification, body.content.to_domain(), body.change_reason),
            )
            _etag(response, value.current.record)
            return TableResponse.from_snapshot(value)
        except CatalogHttpError:
            raise
        except Exception as error:
            raise _error(context, error) from error

    @application.get(
        "/api/v1/catalog/tables/{table_id}",
        operation_id="getConfigurableCatalogTable",
        response_model=TableResponse,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["catalog-schema"],
    )
    def get_table(request: Request, response: Response, table_id: UUID) -> TableResponse:
        context, decision = _scope(request)
        try:
            value = required(context).get_table(context, decision, table_id)
            _etag(response, value.current.record)
            return TableResponse.from_snapshot(value)
        except CatalogHttpError:
            raise
        except Exception as error:
            raise _error(context, error) from error

    @application.post(
        "/api/v1/catalog/tables/{table_id}/revisions",
        operation_id="reviseConfigurableCatalogTable",
        response_model=TableResponse,
        status_code=status.HTTP_201_CREATED,
        dependencies=[Depends(security_dependency), Depends(write_dependency)],
        tags=["catalog-schema"],
    )
    def revise_table(
        request: Request,
        response: Response,
        table_id: UUID,
        body: TableReviseRequest,
        if_match: Annotated[str | None, Header(alias="If-Match")] = None,
    ) -> TableResponse:
        context, decision = _scope(request)
        try:
            current = required(context).get_table_for_write(context, decision, table_id)
            expected = require_matching_if_match(if_match, current.current.record.ref)
            value = required(context).revise_table(
                context,
                decision,
                table_id,
                ReviseTable(expected, body.content.to_domain(), body.change_reason),
            )
            _etag(response, value.current.record)
            return TableResponse.from_snapshot(value)
        except CatalogHttpError:
            raise
        except Exception as error:
            raise _error(context, error) from error

    @application.get(
        "/api/v1/catalog/tables/{table_id}/attributes",
        operation_id="listConfigurableCatalogAttributes",
        response_model=AttributeListResponse,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["catalog-schema"],
    )
    def list_attributes(request: Request, table_id: UUID) -> AttributeListResponse:
        context, decision = _scope(request)
        try:
            values = required(context).list_attributes(context, decision, table_id)
            return AttributeListResponse(
                items=tuple(AttributeResponse.from_snapshot(item) for item in values)
            )
        except CatalogHttpError:
            raise
        except Exception as error:
            raise _error(context, error) from error

    @application.post(
        "/api/v1/catalog/tables/{table_id}/attributes",
        operation_id="createConfigurableCatalogAttribute",
        response_model=AttributeResponse,
        status_code=status.HTTP_201_CREATED,
        dependencies=[Depends(security_dependency), Depends(write_dependency)],
        tags=["catalog-schema"],
    )
    def create_attribute(
        request: Request, response: Response, table_id: UUID, body: AttributeCreateRequest
    ) -> AttributeResponse:
        context, decision = _scope(request)
        try:
            value = required(context).create_attribute(
                context,
                decision,
                CreateAttribute(body.content.to_domain(table_id), body.change_reason),
            )
            _etag(response, value.current.record)
            return AttributeResponse.from_snapshot(value)
        except CatalogHttpError:
            raise
        except Exception as error:
            raise _error(context, error) from error

    @application.post(
        "/api/v1/catalog/attributes/{attribute_id}/revisions",
        operation_id="reviseConfigurableCatalogAttribute",
        response_model=AttributeResponse,
        status_code=status.HTTP_201_CREATED,
        dependencies=[Depends(security_dependency), Depends(write_dependency)],
        tags=["catalog-schema"],
    )
    def revise_attribute(
        request: Request,
        response: Response,
        attribute_id: UUID,
        body: AttributeCreateRequest,
        if_match: Annotated[str | None, Header(alias="If-Match")] = None,
    ) -> AttributeResponse:
        context, decision = _scope(request)
        try:
            current = required(context).get_attribute_for_write(context, decision, attribute_id)
            expected = require_matching_if_match(if_match, current.current.record.ref)
            value = required(context).revise_attribute(
                context,
                decision,
                attribute_id,
                ReviseAttribute(
                    expected, body.content.to_domain(current.table_id), body.change_reason
                ),
            )
            _etag(response, value.current.record)
            return AttributeResponse.from_snapshot(value)
        except CatalogHttpError:
            raise
        except Exception as error:
            raise _error(context, error) from error

    @application.get(
        "/api/v1/catalog/tables/{table_id}/layouts",
        operation_id="listConfigurableCatalogLayouts",
        response_model=LayoutListResponse,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["catalog-schema"],
    )
    def list_layouts(request: Request, table_id: UUID) -> LayoutListResponse:
        context, decision = _scope(request)
        try:
            values = required(context).list_layouts(context, decision, table_id)
            return LayoutListResponse(
                items=tuple(LayoutResponse.from_snapshot(item) for item in values)
            )
        except CatalogHttpError:
            raise
        except Exception as error:
            raise _error(context, error) from error

    @application.post(
        "/api/v1/catalog/tables/{table_id}/layouts",
        operation_id="createConfigurableCatalogLayout",
        response_model=LayoutResponse,
        status_code=status.HTTP_201_CREATED,
        dependencies=[Depends(security_dependency), Depends(write_dependency)],
        tags=["catalog-schema"],
    )
    def create_layout(
        request: Request, response: Response, table_id: UUID, body: LayoutCreateRequest
    ) -> LayoutResponse:
        context, decision = _scope(request)
        try:
            value = required(context).create_layout(
                context, decision, CreateLayout(body.to_domain(table_id), body.change_reason)
            )
            _etag(response, value.current.record)
            return LayoutResponse.from_snapshot(value)
        except CatalogHttpError:
            raise
        except Exception as error:
            raise _error(context, error) from error

    @application.post(
        "/api/v1/catalog/layouts/{layout_id}/revisions",
        operation_id="reviseConfigurableCatalogLayout",
        response_model=LayoutResponse,
        status_code=status.HTTP_201_CREATED,
        dependencies=[Depends(security_dependency), Depends(write_dependency)],
        tags=["catalog-schema"],
    )
    def revise_layout(
        request: Request,
        response: Response,
        layout_id: UUID,
        body: LayoutCreateRequest,
        if_match: Annotated[str | None, Header(alias="If-Match")] = None,
    ) -> LayoutResponse:
        context, decision = _scope(request)
        try:
            current = required(context).get_layout_for_write(context, decision, layout_id)
            expected = require_matching_if_match(if_match, current.current.record.ref)
            value = required(context).revise_layout(
                context,
                decision,
                layout_id,
                ReviseLayout(expected, body.to_domain(current.table_id), body.change_reason),
            )
            _etag(response, value.current.record)
            return LayoutResponse.from_snapshot(value)
        except CatalogHttpError:
            raise
        except Exception as error:
            raise _error(context, error) from error

    @application.get(
        "/api/v1/catalog/tables/{table_id}/subsets",
        operation_id="listConfigurableCatalogSubsets",
        response_model=SubsetListResponse,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["catalog-schema"],
    )
    def list_subsets(request: Request, table_id: UUID) -> SubsetListResponse:
        context, decision = _scope(request)
        try:
            values = required(context).list_subsets(context, decision, table_id)
            return SubsetListResponse(
                items=tuple(SubsetResponse.from_snapshot(item) for item in values)
            )
        except CatalogHttpError:
            raise
        except Exception as error:
            raise _error(context, error) from error

    @application.post(
        "/api/v1/catalog/tables/{table_id}/subsets",
        operation_id="createConfigurableCatalogSubset",
        response_model=SubsetResponse,
        status_code=status.HTTP_201_CREATED,
        dependencies=[Depends(security_dependency), Depends(write_dependency)],
        tags=["catalog-schema"],
    )
    def create_subset(
        request: Request, response: Response, table_id: UUID, body: SubsetCreateRequest
    ) -> SubsetResponse:
        context, decision = _scope(request)
        try:
            value = required(context).create_subset(
                context, decision, CreateSubset(body.to_domain(table_id), body.change_reason)
            )
            _etag(response, value.current.record)
            return SubsetResponse.from_snapshot(value)
        except CatalogHttpError:
            raise
        except Exception as error:
            raise _error(context, error) from error

    @application.post(
        "/api/v1/catalog/subsets/{subset_id}/revisions",
        operation_id="reviseConfigurableCatalogSubset",
        response_model=SubsetResponse,
        status_code=status.HTTP_201_CREATED,
        dependencies=[Depends(security_dependency), Depends(write_dependency)],
        tags=["catalog-schema"],
    )
    def revise_subset(
        request: Request,
        response: Response,
        subset_id: UUID,
        body: SubsetCreateRequest,
        if_match: Annotated[str | None, Header(alias="If-Match")] = None,
    ) -> SubsetResponse:
        context, decision = _scope(request)
        try:
            current = required(context).get_subset_for_write(context, decision, subset_id)
            expected = require_matching_if_match(if_match, current.current.record.ref)
            value = required(context).revise_subset(
                context,
                decision,
                subset_id,
                ReviseSubset(expected, body.to_domain(current.table_id), body.change_reason),
            )
            _etag(response, value.current.record)
            return SubsetResponse.from_snapshot(value)
        except CatalogHttpError:
            raise
        except Exception as error:
            raise _error(context, error) from error

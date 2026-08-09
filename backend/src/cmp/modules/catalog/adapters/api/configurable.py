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
    ATTRIBUTE_AGGREGATE_TYPE,
    DATABASE_AGGREGATE_TYPE,
    LAYOUT_AGGREGATE_TYPE,
    PROFILE_AGGREGATE_TYPE,
    SUBSET_AGGREGATE_TYPE,
    TABLE_AGGREGATE_TYPE,
    AttributeSnapshot,
    ConfigurableCatalogService,
    CreateAttribute,
    CreateDatabase,
    CreateLayout,
    CreateProfile,
    CreateSubset,
    CreateTable,
    DatabaseSnapshot,
    LayoutSnapshot,
    ProfileSnapshot,
    PublishRevision,
    ReviseAttribute,
    ReviseDatabase,
    ReviseLayout,
    ReviseProfile,
    ReviseSubset,
    ReviseTable,
    SubsetSnapshot,
    TableSnapshot,
)
from cmp.modules.catalog.domain.configurable import (
    AttributeDataType,
    AttributeDefinitionContent,
    CatalogDatabaseContent,
    CatalogProfileContent,
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


class DatabaseContentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{0,63}$")]
    name: Annotated[str, StringConstraints(min_length=1, max_length=200)]
    description: Annotated[str | None, StringConstraints(min_length=1, max_length=4000)] = None

    def to_domain(self) -> CatalogDatabaseContent:
        return CatalogDatabaseContent(self.key, self.name, self.description)


class DatabaseCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    classification: DataClassification = DataClassification.INTERNAL
    content: DatabaseContentInput
    change_reason: Annotated[str, StringConstraints(min_length=1, max_length=2000)]


class DatabaseReviseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    content: DatabaseContentInput
    change_reason: Annotated[str, StringConstraints(min_length=1, max_length=2000)]


class ProfileContentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    database_id: UUID
    database_revision_id: UUID
    key: Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{0,63}$")]
    name: Annotated[str, StringConstraints(min_length=1, max_length=200)]
    description: Annotated[str | None, StringConstraints(min_length=1, max_length=4000)] = None

    def to_domain(self) -> CatalogProfileContent:
        return CatalogProfileContent(
            self.database_id,
            self.database_revision_id,
            self.key,
            self.name,
            self.description,
        )


class ProfileCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    classification: DataClassification = DataClassification.INTERNAL
    content: ProfileContentInput
    change_reason: Annotated[str, StringConstraints(min_length=1, max_length=2000)]


class ProfileReviseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    content: ProfileContentInput
    change_reason: Annotated[str, StringConstraints(min_length=1, max_length=2000)]


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
    profile_id: UUID | None = None
    profile_revision_id: UUID | None = None


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


class DatabaseRevisionResponse(RevisionMetadataResponse):
    content: DatabaseContentInput

    @classmethod
    def from_snapshot(
        cls, value: DatabaseSnapshot, lifecycle: str = "draft"
    ) -> DatabaseRevisionResponse:
        revision = value.current
        return cls(
            **RevisionMetadataResponse.from_record(revision.record, lifecycle).model_dump(),
            content=DatabaseContentInput(
                key=revision.content.key,
                name=revision.content.name,
                description=revision.content.description,
            ),
        )


class DatabaseResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    database_id: UUID
    current_revision: DatabaseRevisionResponse

    @classmethod
    def from_snapshot(cls, value: DatabaseSnapshot, lifecycle: str = "draft") -> DatabaseResponse:
        return cls(
            database_id=value.id,
            current_revision=DatabaseRevisionResponse.from_snapshot(value, lifecycle),
        )


class DatabaseListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: tuple[DatabaseResponse, ...]


class ProfileRevisionResponse(RevisionMetadataResponse):
    content: ProfileContentInput

    @classmethod
    def from_snapshot(
        cls, value: ProfileSnapshot, lifecycle: str = "draft"
    ) -> ProfileRevisionResponse:
        revision = value.current
        content = revision.content
        return cls(
            **RevisionMetadataResponse.from_record(revision.record, lifecycle).model_dump(),
            content=ProfileContentInput(
                database_id=content.database_id,
                database_revision_id=content.database_revision_id,
                key=content.key,
                name=content.name,
                description=content.description,
            ),
        )


class ProfileResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    profile_id: UUID
    current_revision: ProfileRevisionResponse

    @classmethod
    def from_snapshot(cls, value: ProfileSnapshot, lifecycle: str = "draft") -> ProfileResponse:
        return cls(
            profile_id=value.id,
            current_revision=ProfileRevisionResponse.from_snapshot(value, lifecycle),
        )


class ProfileListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: tuple[ProfileResponse, ...]


class PublicationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    aggregate_type: Annotated[str, StringConstraints(min_length=1, max_length=128)]
    aggregate_id: UUID
    revision_id: UUID


class PublicationValidationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    aggregate_type: str
    aggregate_id: UUID
    revision_id: UUID
    valid: bool
    errors: tuple[str, ...]


class TableRevisionResponse(RevisionMetadataResponse):
    content: TableContentInput

    @classmethod
    def from_snapshot(cls, value: TableSnapshot, lifecycle: str = "draft") -> TableRevisionResponse:
        revision = value.current
        return cls(
            **RevisionMetadataResponse.from_record(revision.record, lifecycle).model_dump(),
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
    def from_snapshot(cls, value: TableSnapshot, lifecycle: str = "draft") -> TableResponse:
        return cls(
            table_id=value.id,
            current_revision=TableRevisionResponse.from_snapshot(value, lifecycle),
        )


class TableListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: tuple[TableResponse, ...]


class AttributeRevisionResponse(RevisionMetadataResponse):
    content: AttributeContentInput

    @classmethod
    def from_snapshot(
        cls, value: AttributeSnapshot, lifecycle: str = "draft"
    ) -> AttributeRevisionResponse:
        revision = value.current
        content = revision.content
        return cls(
            **RevisionMetadataResponse.from_record(revision.record, lifecycle).model_dump(),
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
    def from_snapshot(cls, value: AttributeSnapshot, lifecycle: str = "draft") -> AttributeResponse:
        return cls(
            attribute_definition_id=value.id,
            table_id=value.table_id,
            current_revision=AttributeRevisionResponse.from_snapshot(value, lifecycle),
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
    def from_snapshot(cls, value: LayoutSnapshot, lifecycle: str = "draft") -> LayoutResponse:
        content = value.current.content
        return cls(
            layout_id=value.id,
            table_id=value.table_id,
            revision=RevisionMetadataResponse.from_record(value.current.record, lifecycle),
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
    def from_snapshot(cls, value: SubsetSnapshot, lifecycle: str = "draft") -> SubsetResponse:
        content = value.current.content
        return cls(
            subset_id=value.id,
            table_id=value.table_id,
            revision=RevisionMetadataResponse.from_record(value.current.record, lifecycle),
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

    def lifecycle(context: Any, decision: Any, aggregate_type: str, value: Any) -> str:
        publication_reader = getattr(required(context), "is_published", None)
        if publication_reader is None:
            # Lightweight API fixtures used by contract tests intentionally do
            # not model the database marker.  Production service always does.
            return "draft"
        return (
            "published"
            if publication_reader(
                context,
                decision,
                aggregate_type,
                value.id,
                value.current.record.revision_id,
            )
            else "draft"
        )

    @application.post(
        "/api/v1/catalog/publication:validate",
        operation_id="validateConfigurableCatalogPublication",
        response_model=PublicationValidationResponse,
        dependencies=[Depends(security_dependency), Depends(write_dependency)],
        tags=["catalog-schema"],
    )
    def validate_publication(
        request: Request, body: PublicationRequest
    ) -> PublicationValidationResponse:
        context, decision = _scope(request)
        try:
            value = required(context).validate_publication(
                context,
                decision,
                PublishRevision(body.aggregate_type, body.aggregate_id, body.revision_id),
            )
            return PublicationValidationResponse(
                aggregate_type=value.aggregate_type,
                aggregate_id=value.aggregate_id,
                revision_id=value.revision_id,
                valid=value.valid,
                errors=value.errors,
            )
        except CatalogHttpError:
            raise
        except Exception as error:
            raise _error(context, error) from error

    @application.post(
        "/api/v1/catalog/publication:publish",
        operation_id="publishConfigurableCatalogRevision",
        response_model=PublicationValidationResponse,
        dependencies=[Depends(security_dependency), Depends(write_dependency)],
        tags=["catalog-schema"],
    )
    def publish_revision(
        request: Request, body: PublicationRequest
    ) -> PublicationValidationResponse:
        context, decision = _scope(request)
        # Direct Catalog publication is intentionally no longer a mutating authority.
        # Review approval projects the exact Record marker atomically; callers use the
        # validation endpoint for readiness and the governed review request endpoint to
        # enter the publication workflow.
        del decision, body
        raise _error(
            context,
            ConfigurableCatalogConflict(
                "direct publication is disabled; submit the exact revision for review"
            ),
        )

    @application.get(
        "/api/v1/catalog/databases",
        operation_id="listConfigurableCatalogDatabases",
        response_model=DatabaseListResponse,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["catalog-schema"],
    )
    def list_databases(request: Request) -> DatabaseListResponse:
        context, decision = _scope(request)
        try:
            values = required(context).list_databases(context, decision)
            return DatabaseListResponse(
                items=tuple(
                    DatabaseResponse.from_snapshot(
                        item, lifecycle(context, decision, DATABASE_AGGREGATE_TYPE, item)
                    )
                    for item in values
                )
            )
        except CatalogHttpError:
            raise
        except Exception as error:
            raise _error(context, error) from error

    @application.post(
        "/api/v1/catalog/databases",
        operation_id="createConfigurableCatalogDatabase",
        response_model=DatabaseResponse,
        status_code=status.HTTP_201_CREATED,
        dependencies=[Depends(security_dependency), Depends(write_dependency)],
        tags=["catalog-schema"],
    )
    def create_database(
        request: Request, response: Response, body: DatabaseCreateRequest
    ) -> DatabaseResponse:
        context, decision = _scope(request)
        try:
            value = required(context).create_database(
                context,
                decision,
                CreateDatabase(body.classification, body.content.to_domain(), body.change_reason),
            )
            _etag(response, value.current.record)
            return DatabaseResponse.from_snapshot(
                value, lifecycle(context, decision, DATABASE_AGGREGATE_TYPE, value)
            )
        except CatalogHttpError:
            raise
        except Exception as error:
            raise _error(context, error) from error

    @application.get(
        "/api/v1/catalog/databases/{database_id}",
        operation_id="getConfigurableCatalogDatabase",
        response_model=DatabaseResponse,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["catalog-schema"],
    )
    def get_database(request: Request, response: Response, database_id: UUID) -> DatabaseResponse:
        context, decision = _scope(request)
        try:
            value = required(context).get_database(context, decision, database_id)
            _etag(response, value.current.record)
            return DatabaseResponse.from_snapshot(
                value, lifecycle(context, decision, DATABASE_AGGREGATE_TYPE, value)
            )
        except CatalogHttpError:
            raise
        except Exception as error:
            raise _error(context, error) from error

    @application.post(
        "/api/v1/catalog/databases/{database_id}/revisions",
        operation_id="reviseConfigurableCatalogDatabase",
        response_model=DatabaseResponse,
        status_code=status.HTTP_201_CREATED,
        dependencies=[Depends(security_dependency), Depends(write_dependency)],
        tags=["catalog-schema"],
    )
    def revise_database(
        request: Request,
        response: Response,
        database_id: UUID,
        body: DatabaseReviseRequest,
        if_match: Annotated[str | None, Header(alias="If-Match")] = None,
    ) -> DatabaseResponse:
        context, decision = _scope(request)
        try:
            current = required(context).get_database_for_write(context, decision, database_id)
            expected = require_matching_if_match(if_match, current.current.record.ref)
            value = required(context).revise_database(
                context,
                decision,
                database_id,
                ReviseDatabase(expected, body.content.to_domain(), body.change_reason),
            )
            _etag(response, value.current.record)
            return DatabaseResponse.from_snapshot(value)
        except CatalogHttpError:
            raise
        except Exception as error:
            raise _error(context, error) from error

    @application.get(
        "/api/v1/catalog/profiles",
        operation_id="listConfigurableCatalogProfiles",
        response_model=ProfileListResponse,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["catalog-schema"],
    )
    def list_profiles(request: Request, database_id: UUID | None = None) -> ProfileListResponse:
        context, decision = _scope(request)
        try:
            values = required(context).list_profiles(context, decision, database_id)
            return ProfileListResponse(
                items=tuple(
                    ProfileResponse.from_snapshot(
                        item, lifecycle(context, decision, PROFILE_AGGREGATE_TYPE, item)
                    )
                    for item in values
                )
            )
        except CatalogHttpError:
            raise
        except Exception as error:
            raise _error(context, error) from error

    @application.post(
        "/api/v1/catalog/profiles",
        operation_id="createConfigurableCatalogProfile",
        response_model=ProfileResponse,
        status_code=status.HTTP_201_CREATED,
        dependencies=[Depends(security_dependency), Depends(write_dependency)],
        tags=["catalog-schema"],
    )
    def create_profile(
        request: Request, response: Response, body: ProfileCreateRequest
    ) -> ProfileResponse:
        context, decision = _scope(request)
        try:
            value = required(context).create_profile(
                context,
                decision,
                CreateProfile(body.classification, body.content.to_domain(), body.change_reason),
            )
            _etag(response, value.current.record)
            return ProfileResponse.from_snapshot(
                value, lifecycle(context, decision, PROFILE_AGGREGATE_TYPE, value)
            )
        except CatalogHttpError:
            raise
        except Exception as error:
            raise _error(context, error) from error

    @application.get(
        "/api/v1/catalog/profiles/{profile_id}",
        operation_id="getConfigurableCatalogProfile",
        response_model=ProfileResponse,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["catalog-schema"],
    )
    def get_profile(request: Request, response: Response, profile_id: UUID) -> ProfileResponse:
        context, decision = _scope(request)
        try:
            value = required(context).get_profile(context, decision, profile_id)
            _etag(response, value.current.record)
            return ProfileResponse.from_snapshot(
                value, lifecycle(context, decision, PROFILE_AGGREGATE_TYPE, value)
            )
        except CatalogHttpError:
            raise
        except Exception as error:
            raise _error(context, error) from error

    @application.post(
        "/api/v1/catalog/profiles/{profile_id}/revisions",
        operation_id="reviseConfigurableCatalogProfile",
        response_model=ProfileResponse,
        status_code=status.HTTP_201_CREATED,
        dependencies=[Depends(security_dependency), Depends(write_dependency)],
        tags=["catalog-schema"],
    )
    def revise_profile(
        request: Request,
        response: Response,
        profile_id: UUID,
        body: ProfileReviseRequest,
        if_match: Annotated[str | None, Header(alias="If-Match")] = None,
    ) -> ProfileResponse:
        context, decision = _scope(request)
        try:
            current = required(context).get_profile_for_write(context, decision, profile_id)
            expected = require_matching_if_match(if_match, current.current.record.ref)
            value = required(context).revise_profile(
                context,
                decision,
                profile_id,
                ReviseProfile(expected, body.content.to_domain(), body.change_reason),
            )
            _etag(response, value.current.record)
            return ProfileResponse.from_snapshot(value)
        except CatalogHttpError:
            raise
        except Exception as error:
            raise _error(context, error) from error

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
                items=tuple(
                    TableResponse.from_snapshot(
                        item, lifecycle(context, decision, TABLE_AGGREGATE_TYPE, item)
                    )
                    for item in values
                )
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
            if (body.profile_id is None) != (body.profile_revision_id is None):
                raise ValueError("profile_id and profile_revision_id must be supplied together")
            value = required(context).create_table(
                context,
                decision,
                CreateTable(
                    body.classification,
                    body.content.to_domain(),
                    body.change_reason,
                    body.profile_id,
                    body.profile_revision_id,
                ),
            )
            _etag(response, value.current.record)
            return TableResponse.from_snapshot(
                value, lifecycle(context, decision, TABLE_AGGREGATE_TYPE, value)
            )
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
            return TableResponse.from_snapshot(
                value, lifecycle(context, decision, TABLE_AGGREGATE_TYPE, value)
            )
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
                items=tuple(
                    AttributeResponse.from_snapshot(
                        item, lifecycle(context, decision, ATTRIBUTE_AGGREGATE_TYPE, item)
                    )
                    for item in values
                )
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
                items=tuple(
                    LayoutResponse.from_snapshot(
                        item, lifecycle(context, decision, LAYOUT_AGGREGATE_TYPE, item)
                    )
                    for item in values
                )
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
                items=tuple(
                    SubsetResponse.from_snapshot(
                        item, lifecycle(context, decision, SUBSET_AGGREGATE_TYPE, item)
                    )
                    for item in values
                )
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

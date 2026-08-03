"""HTTP API for configurable Catalog records, datasheets and search (T-50)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from decimal import Decimal
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import Depends, FastAPI, Header, Query, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, StringConstraints
from sqlalchemy.exc import IntegrityError

from cmp.modules.catalog.adapters.api.catalog import CatalogHttpError, _etag, _scope
from cmp.modules.catalog.application.configurable import ConfigRevision
from cmp.modules.catalog.application.records import (
    CatalogRecordService,
    CreateFolder,
    CreateRecord,
    FolderSnapshot,
    RecordComparison,
    RecordDomainBinding,
    RecordSearchResult,
    RecordSnapshot,
    ReviseFolder,
    ReviseRecord,
)
from cmp.modules.catalog.domain.configurable import (
    AttributeDataType,
    ConfigurableCatalogConflict,
    ConfigurableCatalogNotFound,
)
from cmp.modules.catalog.domain.records import (
    CatalogFolderContent,
    CatalogRecordContent,
    CatalogRecordQuery,
    CatalogRecordValue,
    DiscreteFilter,
    NumberRangeFilter,
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

type Dependency = Callable[..., object]
type ShortText = Annotated[str, StringConstraints(min_length=1, max_length=255)]


class NumberValueInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    data_type: Literal[AttributeDataType.NUMBER]
    attribute_definition_id: UUID
    attribute_definition_revision_id: UUID
    original_value: Decimal
    original_unit_string: Annotated[str, StringConstraints(min_length=1, max_length=64)]
    normalized_value: Decimal
    normalized_unit: Annotated[str, StringConstraints(min_length=1, max_length=64)]
    quantity_semantics: Annotated[str, StringConstraints(min_length=1, max_length=255)]


class IntegerValueInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    data_type: Literal[AttributeDataType.INTEGER]
    attribute_definition_id: UUID
    attribute_definition_revision_id: UUID
    value: StrictInt


class TextValueInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    data_type: Literal[AttributeDataType.TEXT]
    attribute_definition_id: UUID
    attribute_definition_revision_id: UUID
    value: Annotated[str, StringConstraints(min_length=1, max_length=10000)]


class BooleanValueInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    data_type: Literal[AttributeDataType.BOOLEAN]
    attribute_definition_id: UUID
    attribute_definition_revision_id: UUID
    value: StrictBool


class DateValueInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    data_type: Literal[AttributeDataType.DATE]
    attribute_definition_id: UUID
    attribute_definition_revision_id: UUID
    value: date


class DiscreteValueInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    data_type: Literal[AttributeDataType.DISCRETE]
    attribute_definition_id: UUID
    attribute_definition_revision_id: UUID
    value: ShortText


class FileValueInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    data_type: Literal[AttributeDataType.FILE]
    attribute_definition_id: UUID
    attribute_definition_revision_id: UUID
    artifact_id: UUID
    artifact_sha256: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]


class CurveValueInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    data_type: Literal[AttributeDataType.CURVE]
    attribute_definition_id: UUID
    attribute_definition_revision_id: UUID
    artifact_id: UUID
    artifact_sha256: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]


class RecordReferenceValueInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    data_type: Literal[AttributeDataType.RECORD_REFERENCE]
    attribute_definition_id: UUID
    attribute_definition_revision_id: UUID
    target_record_id: UUID
    target_record_revision_id: UUID


type RecordValueInput = Annotated[
    NumberValueInput
    | IntegerValueInput
    | TextValueInput
    | BooleanValueInput
    | DateValueInput
    | DiscreteValueInput
    | FileValueInput
    | CurveValueInput
    | RecordReferenceValueInput,
    Field(discriminator="data_type"),
]


def _value_to_domain(value: RecordValueInput) -> CatalogRecordValue:
    if isinstance(value, NumberValueInput):
        return CatalogRecordValue(
            value.attribute_definition_id,
            value.attribute_definition_revision_id,
            AttributeDataType.NUMBER,
            original_value=value.original_value,
            original_unit_string=value.original_unit_string,
            normalized_value=value.normalized_value,
            normalized_unit=value.normalized_unit,
            quantity_semantics=value.quantity_semantics,
        )
    if isinstance(
        value,
        (IntegerValueInput, TextValueInput, BooleanValueInput, DateValueInput, DiscreteValueInput),
    ):
        return CatalogRecordValue(
            value.attribute_definition_id,
            value.attribute_definition_revision_id,
            AttributeDataType(value.data_type),
            value=value.value,
        )
    if isinstance(value, (FileValueInput, CurveValueInput)):
        return CatalogRecordValue(
            value.attribute_definition_id,
            value.attribute_definition_revision_id,
            AttributeDataType(value.data_type),
            artifact_id=value.artifact_id,
            artifact_sha256=value.artifact_sha256,
        )
    return CatalogRecordValue(
        value.attribute_definition_id,
        value.attribute_definition_revision_id,
        AttributeDataType.RECORD_REFERENCE,
        target_record_id=value.target_record_id,
        target_record_revision_id=value.target_record_revision_id,
    )


def _value_response(value: CatalogRecordValue) -> RecordValueInput:
    common = {
        "attribute_definition_id": value.attribute_definition_id,
        "attribute_definition_revision_id": value.attribute_definition_revision_id,
    }
    if value.data_type is AttributeDataType.NUMBER:
        assert value.original_value is not None and value.normalized_value is not None
        assert value.original_unit_string is not None and value.normalized_unit is not None
        assert value.quantity_semantics is not None
        return NumberValueInput(
            data_type=AttributeDataType.NUMBER,
            original_value=value.original_value,
            original_unit_string=value.original_unit_string,
            normalized_value=value.normalized_value,
            normalized_unit=value.normalized_unit,
            quantity_semantics=value.quantity_semantics,
            **common,
        )
    if value.data_type is AttributeDataType.INTEGER:
        assert type(value.value) is int
        return IntegerValueInput(data_type=AttributeDataType.INTEGER, value=value.value, **common)
    if value.data_type is AttributeDataType.TEXT:
        assert isinstance(value.value, str)
        return TextValueInput(data_type=AttributeDataType.TEXT, value=value.value, **common)
    if value.data_type is AttributeDataType.BOOLEAN:
        assert type(value.value) is bool
        return BooleanValueInput(data_type=AttributeDataType.BOOLEAN, value=value.value, **common)
    if value.data_type is AttributeDataType.DATE:
        assert isinstance(value.value, date)
        return DateValueInput(data_type=AttributeDataType.DATE, value=value.value, **common)
    if value.data_type is AttributeDataType.DISCRETE:
        assert isinstance(value.value, str)
        return DiscreteValueInput(data_type=AttributeDataType.DISCRETE, value=value.value, **common)
    if value.data_type is AttributeDataType.FILE:
        assert value.artifact_id is not None and value.artifact_sha256 is not None
        return FileValueInput(
            data_type=AttributeDataType.FILE,
            artifact_id=value.artifact_id,
            artifact_sha256=value.artifact_sha256,
            **common,
        )
    if value.data_type is AttributeDataType.CURVE:
        assert value.artifact_id is not None and value.artifact_sha256 is not None
        return CurveValueInput(
            data_type=AttributeDataType.CURVE,
            artifact_id=value.artifact_id,
            artifact_sha256=value.artifact_sha256,
            **common,
        )
    assert value.target_record_id is not None and value.target_record_revision_id is not None
    return RecordReferenceValueInput(
        data_type=AttributeDataType.RECORD_REFERENCE,
        target_record_id=value.target_record_id,
        target_record_revision_id=value.target_record_revision_id,
        **common,
    )


class FolderInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    table_revision_id: UUID
    name: Annotated[str, StringConstraints(min_length=1, max_length=200)]
    description: Annotated[str | None, StringConstraints(min_length=1, max_length=2000)] = None
    parent_folder_id: UUID | None = None
    parent_folder_revision_id: UUID | None = None

    def to_domain(self, table_id: UUID) -> CatalogFolderContent:
        return CatalogFolderContent(
            table_id,
            self.table_revision_id,
            self.name,
            self.description,
            self.parent_folder_id,
            self.parent_folder_revision_id,
        )


class FolderCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    classification: DataClassification = DataClassification.INTERNAL
    content: FolderInput
    change_reason: Annotated[str, StringConstraints(min_length=1, max_length=2000)]


class FolderReviseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    content: FolderInput
    change_reason: Annotated[str, StringConstraints(min_length=1, max_length=2000)]


class RecordContentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    table_revision_id: UUID
    name: Annotated[str, StringConstraints(min_length=1, max_length=200)]
    external_key: ShortText | None = None
    description: Annotated[str | None, StringConstraints(min_length=1, max_length=4000)] = None
    folder_id: UUID | None = None
    folder_revision_id: UUID | None = None
    values: tuple[RecordValueInput, ...] = ()

    def to_domain(self, table_id: UUID) -> CatalogRecordContent:
        return CatalogRecordContent(
            table_id,
            self.table_revision_id,
            self.name,
            self.external_key,
            self.description,
            self.folder_id,
            self.folder_revision_id,
            tuple(_value_to_domain(value) for value in self.values),
        )


class RecordCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    classification: DataClassification = DataClassification.INTERNAL
    content: RecordContentInput
    change_reason: Annotated[str, StringConstraints(min_length=1, max_length=2000)]


class RecordReviseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    content: RecordContentInput
    change_reason: Annotated[str, StringConstraints(min_length=1, max_length=2000)]


class DiscreteFilterInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    attribute_definition_id: UUID
    values: tuple[ShortText, ...] = Field(min_length=1, max_length=50)


class NumberRangeFilterInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    attribute_definition_id: UUID
    minimum: Decimal | None = None
    maximum: Decimal | None = None


class RecordSearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    table_id: UUID
    text: Annotated[str | None, StringConstraints(min_length=1, max_length=200)] = None
    folder_id: UUID | None = None
    record_id: UUID | None = None
    discrete_filters: tuple[DiscreteFilterInput, ...] = ()
    number_filters: tuple[NumberRangeFilterInput, ...] = ()
    facet_attribute_ids: tuple[UUID, ...] = Field(default=(), max_length=20)
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=50, ge=1, le=100)
    # Optional search refinements are deliberately additive to the existing
    # table-scoped contract.  Materials supplies the binding discriminator so
    # workflow records never appear in the normal result set.
    domain_binding_kind: Literal[
        "material",
        "material_state",
        "specimen",
        "test_run",
        "test_data",
        "processing_output",
        "material_model",
        "neutral_material",
        "solver_card",
        "neutral_solver_card",
        "release",
    ] | None = None
    include_descendants: bool = False
    sort_by: Literal["name", "external_key", "attribute"] = "name"
    sort_attribute_id: UUID | None = None
    sort_direction: Literal["ascending", "descending"] = "ascending"

    def to_domain(self) -> CatalogRecordQuery:
        return CatalogRecordQuery(
            table_id=self.table_id,
            text=self.text,
            folder_id=self.folder_id,
            discrete_filters=tuple(
                DiscreteFilter(item.attribute_definition_id, item.values)
                for item in self.discrete_filters
            ),
            number_filters=tuple(
                NumberRangeFilter(item.attribute_definition_id, item.minimum, item.maximum)
                for item in self.number_filters
            ),
            facet_attribute_ids=self.facet_attribute_ids,
            offset=self.offset,
            limit=self.limit,
            domain_binding_kind=self.domain_binding_kind,
            include_descendants=self.include_descendants,
            sort_by=self.sort_by,
            sort_attribute_id=self.sort_attribute_id,
            sort_direction=self.sort_direction,
            record_id=self.record_id,
        )


class FolderResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    folder_id: UUID
    table_id: UUID
    current_revision: RevisionMetadataResponse
    content: FolderInput

    @classmethod
    def from_snapshot(cls, value: FolderSnapshot) -> FolderResponse:
        content = value.current.content
        return cls(
            folder_id=value.id,
            table_id=value.table_id,
            current_revision=RevisionMetadataResponse.from_record(value.current.record, "draft"),
            content=FolderInput(
                table_revision_id=content.table_revision_id,
                name=content.name,
                description=content.description,
                parent_folder_id=content.parent_folder_id,
                parent_folder_revision_id=content.parent_folder_revision_id,
            ),
        )


class FolderListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: tuple[FolderResponse, ...]


class RecordRevisionResponse(RevisionMetadataResponse):
    content: RecordContentInput

    @classmethod
    def from_revision(
        cls, value: ConfigRevision[CatalogRecordContent]
    ) -> RecordRevisionResponse:
        content = value.content
        return cls(
            **RevisionMetadataResponse.from_record(value.record, "draft").model_dump(),
            content=RecordContentInput(
                table_revision_id=content.table_revision_id,
                name=content.name,
                external_key=content.external_key,
                description=content.description,
                folder_id=content.folder_id,
                folder_revision_id=content.folder_revision_id,
                values=tuple(_value_response(item) for item in content.values),
            ),
        )


class DomainBindingProjectionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    binding_id: UUID
    record_id: UUID
    record_revision_id: UUID
    kind: str
    object_id: UUID
    revision_id: UUID
    workbench_path: str

    @classmethod
    def from_domain(
        cls,
        value: RecordDomainBinding,
        *,
        record_id: UUID,
        record_revision_id: UUID,
    ) -> DomainBindingProjectionResponse:
        return cls(
            binding_id=value.binding_id,
            record_id=record_id,
            record_revision_id=record_revision_id,
            kind=value.kind,
            object_id=value.object_id,
            revision_id=value.revision_id,
            workbench_path=value.workbench_path,
        )


class RecordResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    record_id: UUID
    table_id: UUID
    current_revision: RecordRevisionResponse
    domain_binding: DomainBindingProjectionResponse | None = None

    @classmethod
    def from_snapshot(cls, value: RecordSnapshot) -> RecordResponse:
        return cls(
            record_id=value.id,
            table_id=value.table_id,
            current_revision=RecordRevisionResponse.from_revision(value.current),
            domain_binding=(
                DomainBindingProjectionResponse.from_domain(
                    value.domain_binding,
                    record_id=value.id,
                    record_revision_id=value.current.record.revision_id,
                )
                if value.domain_binding is not None
                else None
            ),
        )


class FacetBucketResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    attribute_definition_id: UUID
    value: str
    count: int


class RecordSearchResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: tuple[RecordResponse, ...]
    total_count: int
    offset: int
    limit: int
    facets: tuple[FacetBucketResponse, ...]

    @classmethod
    def from_result(
        cls, value: RecordSearchResult, *, offset: int, limit: int
    ) -> RecordSearchResponse:
        return cls(
            items=tuple(RecordResponse.from_snapshot(item) for item in value.items),
            total_count=value.total_count,
            offset=offset,
            limit=limit,
            facets=tuple(
                FacetBucketResponse(
                    attribute_definition_id=item.attribute_definition_id,
                    value=item.value,
                    count=item.count,
                )
                for item in value.facets
            ),
        )


class RecordRevisionListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: tuple[RecordRevisionResponse, ...]


class RecordValueDifferenceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    attribute_definition_id: UUID
    status: Literal["added", "removed", "changed", "unchanged"]
    before: RecordValueInput | None
    after: RecordValueInput | None


class RecordComparisonResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    record_id: UUID
    from_revision: RecordRevisionResponse
    to_revision: RecordRevisionResponse
    metadata_changed: bool
    value_differences: tuple[RecordValueDifferenceResponse, ...]

    @classmethod
    def from_comparison(cls, value: RecordComparison) -> RecordComparisonResponse:
        return cls(
            record_id=value.record_id,
            from_revision=RecordRevisionResponse.from_revision(value.from_revision),
            to_revision=RecordRevisionResponse.from_revision(value.to_revision),
            metadata_changed=value.metadata_changed,
            value_differences=tuple(
                RecordValueDifferenceResponse(
                    attribute_definition_id=item.attribute_definition_id,
                    status=item.status,
                    before=_value_response(item.before) if item.before is not None else None,
                    after=_value_response(item.after) if item.after is not None else None,
                )
                for item in value.value_differences
            ),
        )


def _error(context: Any, error: Exception) -> CatalogHttpError:
    if isinstance(error, ConfigurableCatalogNotFound):
        return CatalogHttpError(
            context=context,
            status_code=404,
            title="Catalog record not found",
            detail="No Folder, Record or exact revision is visible in this scope.",
            code="CMP-CATALOG-0010",
        )
    if isinstance(error, (InvalidRevisionETag, ValueError)):
        return CatalogHttpError(
            context=context,
            status_code=422,
            title="Invalid Catalog record request",
            detail="The request does not satisfy the typed Attribute and unit contract.",
            code="CMP-CATALOG-0011",
        )
    if isinstance(error, RevisionPreconditionFailed):
        return CatalogHttpError(
            context=context,
            status_code=412,
            title="Record revision precondition failed",
            detail="Reload the current Record revision before retrying.",
            code="CMP-CATALOG-0012",
            current_etag=RevisionETag.from_ref(error.current),
        )
    if isinstance(
        error, (ConfigurableCatalogConflict, RevisionConflict, RevisionKernelError, IntegrityError)
    ):
        return CatalogHttpError(
            context=context,
            status_code=409,
            title="Catalog record conflict",
            detail="The command conflicts with an exact revision, type, unit or Folder rule.",
            code="CMP-CATALOG-0013",
        )
    return CatalogHttpError(
        context=context,
        status_code=409,
        title="Catalog record command rejected",
        detail="The record command could not be completed.",
        code="CMP-CATALOG-0013",
    )


def install_catalog_record_api(
    application: FastAPI,
    *,
    service: CatalogRecordService | None,
    security_dependency: Dependency,
    read_dependency: Dependency,
    write_dependency: Dependency,
) -> None:
    def required(context: Any) -> CatalogRecordService:
        if service is None:
            raise CatalogHttpError(
                context=context,
                status_code=503,
                title="Configurable Catalog unavailable",
                detail="The authoritative Catalog record store is not configured.",
                code="CMP-CATALOG-0014",
            )
        return service

    @application.get(
        "/api/v1/catalog/tables/{table_id}/folders",
        response_model=FolderListResponse,
        operation_id="listCatalogFolders",
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["catalog-records"],
    )
    def list_folders(request: Request, table_id: UUID) -> FolderListResponse:
        context, decision = _scope(request)
        try:
            values = required(context).list_folders(context, decision, table_id)
            return FolderListResponse(
                items=tuple(FolderResponse.from_snapshot(item) for item in values)
            )
        except CatalogHttpError:
            raise
        except Exception as error:
            raise _error(context, error) from error

    @application.post(
        "/api/v1/catalog/tables/{table_id}/folders",
        response_model=FolderResponse,
        status_code=status.HTTP_201_CREATED,
        operation_id="createCatalogFolder",
        dependencies=[Depends(security_dependency), Depends(write_dependency)],
        tags=["catalog-records"],
    )
    def create_folder(
        request: Request, response: Response, table_id: UUID, body: FolderCreateRequest
    ) -> FolderResponse:
        context, decision = _scope(request)
        try:
            value = required(context).create_folder(
                context,
                decision,
                CreateFolder(
                    body.classification,
                    body.content.to_domain(table_id),
                    body.change_reason,
                ),
            )
            _etag(response, value.current.record)
            return FolderResponse.from_snapshot(value)
        except CatalogHttpError:
            raise
        except Exception as error:
            raise _error(context, error) from error

    @application.post(
        "/api/v1/catalog/folders/{folder_id}/revisions",
        response_model=FolderResponse,
        status_code=status.HTTP_201_CREATED,
        operation_id="reviseCatalogFolder",
        dependencies=[Depends(security_dependency), Depends(write_dependency)],
        tags=["catalog-records"],
    )
    def revise_folder(
        request: Request,
        response: Response,
        folder_id: UUID,
        body: FolderReviseRequest,
        if_match: Annotated[str | None, Header(alias="If-Match")] = None,
    ) -> FolderResponse:
        context, decision = _scope(request)
        try:
            current = required(context).get_folder_for_write(context, decision, folder_id)
            expected = require_matching_if_match(if_match, current.current.record.ref)
            value = required(context).revise_folder(
                context,
                decision,
                folder_id,
                ReviseFolder(
                    expected,
                    body.content.to_domain(current.table_id),
                    body.change_reason,
                ),
            )
            _etag(response, value.current.record)
            return FolderResponse.from_snapshot(value)
        except CatalogHttpError:
            raise
        except Exception as error:
            raise _error(context, error) from error

    @application.post(
        "/api/v1/catalog/records:search",
        response_model=RecordSearchResponse,
        operation_id="searchCatalogRecords",
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["catalog-records"],
    )
    def search_records(request: Request, body: RecordSearchRequest) -> RecordSearchResponse:
        context, decision = _scope(request)
        try:
            result = required(context).search_records(context, decision, body.to_domain())
            return RecordSearchResponse.from_result(result, offset=body.offset, limit=body.limit)
        except CatalogHttpError:
            raise
        except Exception as error:
            raise _error(context, error) from error

    @application.post(
        "/api/v1/catalog/tables/{table_id}/records",
        response_model=RecordResponse,
        status_code=status.HTTP_201_CREATED,
        operation_id="createCatalogRecord",
        dependencies=[Depends(security_dependency), Depends(write_dependency)],
        tags=["catalog-records"],
    )
    def create_record(
        request: Request, response: Response, table_id: UUID, body: RecordCreateRequest
    ) -> RecordResponse:
        context, decision = _scope(request)
        try:
            value = required(context).create_record(
                context,
                decision,
                CreateRecord(
                    body.classification,
                    body.content.to_domain(table_id),
                    body.change_reason,
                ),
            )
            _etag(response, value.current.record)
            return RecordResponse.from_snapshot(value)
        except CatalogHttpError:
            raise
        except Exception as error:
            raise _error(context, error) from error

    @application.get(
        "/api/v1/catalog/records/{record_id}",
        response_model=RecordResponse,
        operation_id="getCatalogRecord",
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["catalog-records"],
    )
    def get_record(request: Request, response: Response, record_id: UUID) -> RecordResponse:
        context, decision = _scope(request)
        try:
            value = required(context).get_record(context, decision, record_id)
            _etag(response, value.current.record)
            return RecordResponse.from_snapshot(value)
        except CatalogHttpError:
            raise
        except Exception as error:
            raise _error(context, error) from error

    @application.post(
        "/api/v1/catalog/records/{record_id}/revisions",
        response_model=RecordResponse,
        status_code=status.HTTP_201_CREATED,
        operation_id="reviseCatalogRecord",
        dependencies=[Depends(security_dependency), Depends(write_dependency)],
        tags=["catalog-records"],
    )
    def revise_record(
        request: Request,
        response: Response,
        record_id: UUID,
        body: RecordReviseRequest,
        if_match: Annotated[str | None, Header(alias="If-Match")] = None,
    ) -> RecordResponse:
        context, decision = _scope(request)
        try:
            current = required(context).get_record_for_write(context, decision, record_id)
            expected = require_matching_if_match(if_match, current.current.record.ref)
            value = required(context).revise_record(
                context,
                decision,
                record_id,
                ReviseRecord(
                    expected,
                    body.content.to_domain(current.table_id),
                    body.change_reason,
                ),
            )
            _etag(response, value.current.record)
            return RecordResponse.from_snapshot(value)
        except CatalogHttpError:
            raise
        except Exception as error:
            raise _error(context, error) from error

    @application.get(
        "/api/v1/catalog/records/{record_id}/revisions",
        response_model=RecordRevisionListResponse,
        operation_id="listCatalogRecordRevisions",
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["catalog-records"],
    )
    def list_record_revisions(
        request: Request, record_id: UUID
    ) -> RecordRevisionListResponse:
        context, decision = _scope(request)
        try:
            values = required(context).list_record_revisions(context, decision, record_id)
            return RecordRevisionListResponse(
                items=tuple(RecordRevisionResponse.from_revision(item) for item in values)
            )
        except CatalogHttpError:
            raise
        except Exception as error:
            raise _error(context, error) from error

    @application.get(
        "/api/v1/catalog/records/{record_id}/revisions:compare",
        response_model=RecordComparisonResponse,
        operation_id="compareCatalogRecordRevisions",
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["catalog-records"],
    )
    def compare_record_revisions(
        request: Request,
        record_id: UUID,
        from_revision_id: Annotated[UUID, Query()],
        to_revision_id: Annotated[UUID, Query()],
    ) -> RecordComparisonResponse:
        context, decision = _scope(request)
        try:
            value = required(context).compare_record_revisions(
                context, decision, record_id, from_revision_id, to_revision_id
            )
            return RecordComparisonResponse.from_comparison(value)
        except CatalogHttpError:
            raise
        except Exception as error:
            raise _error(context, error) from error

"""Protected validation/preview API for the cmp.test-data exchange document (T-52)."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import date
from decimal import Decimal
from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from sqlalchemy.exc import IntegrityError

from cmp.modules.datasets.adapters.api.datasets import _etag, _scope
from cmp.modules.datasets.application.canonical_test_data import (
    CanonicalTestDataService,
    ExactTestDataRevisionRef,
    ImportCanonicalTestData,
    ReviseCanonicalTestData,
    TestDataDocumentSnapshot,
)
from cmp.modules.datasets.domain.canonical_test_data import (
    MAX_CANONICAL_JSON_BYTES,
    CanonicalTestDataDocument,
    CanonicalTestDataError,
    ChannelAxisRole,
    TestCondition,
    TestDataChannel,
    TestDataSource,
    TestExecutionMetadata,
    TestMaterialMetadata,
    TestSpecimenMetadata,
    canonical_test_data,
)
from cmp.modules.datasets.domain.governed_tabular import (
    GovernedImportConflict,
    GovernedImportNotFound,
)
from cmp.modules.identity_access.domain.authorization import DataClassification
from cmp.shared.contracts.revisions import (
    InvalidRevisionETag,
    RevisionMetadataResponse,
    RevisionPreconditionFailed,
    require_matching_if_match,
)
from cmp.shared.domain.revisions import (
    AggregateAlreadyExists,
    RevisionConflict,
    RevisionKernelError,
)

type Dependency = Callable[..., object]

Text200 = Annotated[str, StringConstraints(min_length=1, max_length=200, strip_whitespace=False)]
Unit = Annotated[str, StringConstraints(min_length=1, max_length=64, strip_whitespace=False)]
Key = Annotated[
    str,
    StringConstraints(pattern=r"^[a-z][a-z0-9_.-]{0,127}$", strip_whitespace=False),
]
Semantics = Annotated[
    str,
    StringConstraints(pattern=r"^[a-z][a-z0-9_.-]{0,159}$", strip_whitespace=False),
]


class MaterialInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    maker: Text200
    grade: Text200
    lot_batch: Text200 | None


class TestInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    date: date
    operator: Text200
    laboratory: Text200
    method: Annotated[str, StringConstraints(min_length=1, max_length=300)]
    equipment_maker: Text200 | None
    equipment_model: Text200 | None


class SpecimenInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    specimen_id: Text200
    description: Annotated[str, StringConstraints(min_length=1, max_length=1000)] | None


class ConditionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: Key
    quantity_semantics: Semantics
    original_value: Decimal
    original_unit_string: Unit
    normalized_value: Decimal
    normalized_unit: Unit

    def to_domain(self) -> TestCondition:
        return TestCondition(**self.model_dump())


class NormalizationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scale: Decimal
    offset: Decimal


class ChannelInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: Key
    name: Text200
    quantity_semantics: Semantics
    axis_role: ChannelAxisRole
    original_unit_string: Unit
    normalized_unit: Unit
    normalization: NormalizationInput
    original_values: Annotated[list[Decimal | None], Field(min_length=2, max_length=1_000_000)]
    normalized_values: Annotated[list[Decimal | None], Field(min_length=2, max_length=1_000_000)]
    missing_reasons: Annotated[
        list[Annotated[str, StringConstraints(min_length=1, max_length=200)] | None],
        Field(min_length=2, max_length=1_000_000),
    ]

    def to_domain(self) -> TestDataChannel:
        return TestDataChannel(
            key=self.key,
            name=self.name,
            quantity_semantics=self.quantity_semantics,
            axis_role=self.axis_role,
            original_unit_string=self.original_unit_string,
            normalized_unit=self.normalized_unit,
            normalization_scale=self.normalization.scale,
            normalization_offset=self.normalization.offset,
            original_values=tuple(self.original_values),
            normalized_values=tuple(self.normalized_values),
            missing_reasons=tuple(self.missing_reasons),
        )


class SourceInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    file_name: Annotated[str, StringConstraints(min_length=1, max_length=255)]
    media_type: Annotated[str, StringConstraints(min_length=1, max_length=255)]
    sha256: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]


class CanonicalTestDataInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    document_type: str
    schema_version: str
    document_id: Text200
    material: MaterialInput
    test: TestInput
    specimen: SpecimenInput
    conditions: Annotated[list[ConditionInput], Field(max_length=128)]
    channels: Annotated[list[ChannelInput], Field(min_length=2, max_length=512)]
    source: SourceInput

    def to_domain(self) -> CanonicalTestDataDocument:
        return CanonicalTestDataDocument(
            document_type=self.document_type,
            schema_version=self.schema_version,
            document_id=self.document_id,
            material=TestMaterialMetadata(**self.material.model_dump()),
            test=TestExecutionMetadata(
                test_date=self.test.date,
                **self.test.model_dump(exclude={"date"}),
            ),
            specimen=TestSpecimenMetadata(**self.specimen.model_dump()),
            conditions=tuple(item.to_domain() for item in self.conditions),
            channels=tuple(item.to_domain() for item in self.channels),
            source=TestDataSource(**self.source.model_dump()),
        )


class ChannelPreview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str
    name: str
    quantity_semantics: str
    axis_role: ChannelAxisRole
    original_unit_string: str
    normalized_unit: str
    point_count: int
    missing_count: int


class CanonicalTestDataPreviewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: str
    document_sha256: str
    canonical_size_bytes: int
    point_count: int
    condition_count: int
    material_maker: str
    material_grade: str
    test_date: date
    operator: str
    laboratory: str
    method: str
    specimen_id: str
    channels: tuple[ChannelPreview, ...]
    canonical_document: dict[str, Any]

    @classmethod
    def from_domain(cls, document: CanonicalTestDataDocument) -> CanonicalTestDataPreviewResponse:
        canonical = canonical_test_data(document)
        encoded = json.dumps(
            canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
        if len(encoded) > MAX_CANONICAL_JSON_BYTES:
            raise ValueError("canonical Test Data JSON exceeds the 25 MiB single-document limit")
        return cls(
            status="valid",
            document_sha256=document.digest,
            canonical_size_bytes=len(encoded),
            point_count=document.point_count,
            condition_count=len(document.conditions),
            material_maker=document.material.maker,
            material_grade=document.material.grade,
            test_date=document.test.test_date,
            operator=document.test.operator,
            laboratory=document.test.laboratory,
            method=document.test.method,
            specimen_id=document.specimen.specimen_id,
            channels=tuple(
                ChannelPreview(
                    key=item.key,
                    name=item.name,
                    quantity_semantics=item.quantity_semantics,
                    axis_role=item.axis_role,
                    original_unit_string=item.original_unit_string,
                    normalized_unit=item.normalized_unit,
                    point_count=len(item.original_values),
                    missing_count=sum(point is None for point in item.original_values),
                )
                for item in document.channels
            ),
            canonical_document=canonical,
        )


class CanonicalTestDataImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    classification: DataClassification
    document: CanonicalTestDataInput
    change_reason: Annotated[str, StringConstraints(min_length=1, max_length=2000)]


class CanonicalTestDataReviseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    document: CanonicalTestDataInput
    change_reason: Annotated[str, StringConstraints(min_length=1, max_length=2000)]


class CanonicalTestDataDocumentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    test_data_document_id: UUID
    current_revision: RevisionMetadataResponse
    document_key: str
    material_maker: str
    material_grade: str
    lot_batch: str | None
    test_date: date
    operator: str
    laboratory: str
    method: str
    specimen_id: str
    point_count: int
    canonical_artifact_id: UUID
    canonical_sha256: str
    normalized_artifact_id: UUID
    normalized_sha256: str
    channels: tuple[ChannelPreview, ...]

    @classmethod
    def from_snapshot(
        cls, value: TestDataDocumentSnapshot
    ) -> CanonicalTestDataDocumentResponse:
        content = value.content
        return cls(
            test_data_document_id=value.id,
            current_revision=RevisionMetadataResponse.from_record(value.current, "draft"),
            document_key=content.document_key,
            material_maker=content.material.maker,
            material_grade=content.material.grade,
            lot_batch=content.material.lot_batch,
            test_date=content.test.test_date,
            operator=content.test.operator,
            laboratory=content.test.laboratory,
            method=content.test.method,
            specimen_id=content.specimen.specimen_id,
            point_count=content.point_count,
            canonical_artifact_id=content.canonical_artifact_id,
            canonical_sha256=content.canonical_sha256,
            normalized_artifact_id=content.normalized_artifact_id,
            normalized_sha256=content.normalized_sha256,
            channels=tuple(
                ChannelPreview(
                    key=item.key,
                    name=item.name,
                    quantity_semantics=item.quantity_semantics,
                    axis_role=ChannelAxisRole(item.axis_role),
                    original_unit_string=item.original_unit_string,
                    normalized_unit=item.normalized_unit,
                    point_count=item.point_count,
                    missing_count=item.missing_count,
                )
                for item in content.channels
            ),
        )


class CanonicalTestDataDocumentList(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: tuple[CanonicalTestDataDocumentResponse, ...]


class ExactTestDataRevisionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    document_id: UUID
    revision_id: UUID


class CanonicalTestDataPackageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revisions: Annotated[
        tuple[ExactTestDataRevisionInput, ...], Field(min_length=1, max_length=100)
    ]


def install_canonical_test_data_api(
    app: FastAPI,
    *,
    service: CanonicalTestDataService | None = None,
    security_dependency: Dependency,
    read_dependency: Dependency | None = None,
    write_dependency: Dependency,
) -> None:
    @app.post(
        "/api/v1/test-data:validate",
        response_model=CanonicalTestDataPreviewResponse,
        status_code=status.HTTP_200_OK,
        dependencies=[Depends(security_dependency), Depends(write_dependency)],
        tags=["test-data-json"],
    )
    async def validate_test_data(
        body: CanonicalTestDataInput,
        request: Request,
    ) -> CanonicalTestDataPreviewResponse:
        del request
        try:
            return CanonicalTestDataPreviewResponse.from_domain(body.to_domain())
        except (CanonicalTestDataError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    if read_dependency is None:
        read_dependency = write_dependency

    @app.post(
        "/api/v1/test-data-documents",
        response_model=CanonicalTestDataDocumentResponse,
        status_code=status.HTTP_201_CREATED,
        dependencies=[Depends(security_dependency), Depends(write_dependency)],
        tags=["test-data-json"],
    )
    async def import_test_data(
        body: CanonicalTestDataImportRequest,
        request: Request,
        response: Response,
    ) -> CanonicalTestDataDocumentResponse:
        context, decision = _scope(request)
        if service is None:
            raise HTTPException(status_code=503, detail="canonical Test Data store unavailable")
        try:
            snapshot = await service.import_document(
                context,
                decision,
                ImportCanonicalTestData(
                    classification=body.classification,
                    document=body.document.to_domain(),
                    change_reason=body.change_reason,
                ),
            )
        except (GovernedImportConflict, AggregateAlreadyExists, IntegrityError) as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        except (CanonicalTestDataError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        _etag(response, snapshot.current)
        return CanonicalTestDataDocumentResponse.from_snapshot(snapshot)

    @app.get(
        "/api/v1/test-data-documents",
        response_model=CanonicalTestDataDocumentList,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["test-data-json"],
    )
    def list_test_data(request: Request) -> CanonicalTestDataDocumentList:
        context, decision = _scope(request)
        if service is None:
            raise HTTPException(status_code=503, detail="canonical Test Data store unavailable")
        try:
            return CanonicalTestDataDocumentList(
                items=tuple(
                    CanonicalTestDataDocumentResponse.from_snapshot(item)
                    for item in service.list_documents(context, decision)
                )
            )
        except GovernedImportConflict as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.post(
        "/api/v1/test-data-documents/{document_id}/revisions",
        response_model=CanonicalTestDataDocumentResponse,
        status_code=status.HTTP_201_CREATED,
        dependencies=[Depends(security_dependency), Depends(write_dependency)],
        tags=["test-data-json"],
    )
    async def revise_test_data(
        document_id: UUID,
        body: CanonicalTestDataReviseRequest,
        request: Request,
        response: Response,
        if_match: Annotated[str | None, Header(alias="If-Match")] = None,
    ) -> CanonicalTestDataDocumentResponse:
        context, decision = _scope(request)
        if service is None:
            raise HTTPException(status_code=503, detail="canonical Test Data store unavailable")
        try:
            current = service.get_document_for_write(context, decision, document_id)
            expected = require_matching_if_match(if_match, current.current.ref)
            snapshot = await service.revise_document(
                context,
                decision,
                document_id,
                ReviseCanonicalTestData(
                    expected_current_revision_id=expected,
                    document=body.document.to_domain(),
                    change_reason=body.change_reason,
                ),
            )
        except InvalidRevisionETag as error:
            raise HTTPException(status_code=428, detail=str(error)) from error
        except RevisionPreconditionFailed as error:
            raise HTTPException(status_code=412, detail=str(error)) from error
        except GovernedImportNotFound as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except (GovernedImportConflict, RevisionConflict, RevisionKernelError) as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        except (CanonicalTestDataError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        _etag(response, snapshot.current)
        return CanonicalTestDataDocumentResponse.from_snapshot(snapshot)

    @app.get(
        "/api/v1/test-data-documents/{document_id}/revisions/{revision_id}/content",
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["test-data-json"],
    )
    async def export_test_data(
        document_id: UUID,
        revision_id: UUID,
        request: Request,
    ) -> Response:
        context, decision = _scope(request)
        if service is None:
            raise HTTPException(status_code=503, detail="canonical Test Data store unavailable")
        try:
            snapshot, value = await service.export_document(
                context, decision, document_id, revision_id
            )
        except GovernedImportNotFound as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except GovernedImportConflict as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return Response(
            content=value,
            media_type="application/vnd.cmp.test-data+json",
            headers={
                "Content-Disposition": (
                    f'attachment; filename="{snapshot.content.document_key}.json"'
                ),
                "X-Content-SHA256": snapshot.content.canonical_sha256,
            },
        )

    @app.post(
        "/api/v1/test-data-packages:download",
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["test-data-json"],
    )
    async def download_test_data_package(
        body: CanonicalTestDataPackageRequest,
        request: Request,
    ) -> Response:
        context, decision = _scope(request)
        if service is None:
            raise HTTPException(status_code=503, detail="canonical Test Data store unavailable")
        try:
            value, digest = await service.export_package(
                context,
                decision,
                tuple(
                    ExactTestDataRevisionRef(item.document_id, item.revision_id)
                    for item in body.revisions
                ),
            )
        except GovernedImportNotFound as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except GovernedImportConflict as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return Response(
            content=value,
            media_type="application/vnd.cmp.test-data-package+zip",
            headers={
                "Content-Disposition": 'attachment; filename="cmp-test-data-package.zip"',
                "X-Content-SHA256": digest,
            },
        )

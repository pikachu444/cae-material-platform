"""Protected validation/preview API for the cmp.test-data exchange document (T-52)."""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

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


def install_canonical_test_data_api(
    app: FastAPI,
    *,
    security_dependency: Any,
    write_dependency: Any,
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

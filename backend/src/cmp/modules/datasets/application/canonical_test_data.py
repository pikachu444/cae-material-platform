"""Immutable import/export service for canonical Test Data JSON (T-52)."""

from __future__ import annotations

import io
import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol, cast
from uuid import UUID, uuid4

import pyarrow as pa
import pyarrow.parquet as pq

from cmp.modules.artifacts.application.content import ArtifactService
from cmp.modules.datasets.domain.canonical_test_data import (
    MAX_CANONICAL_JSON_BYTES,
    TEST_DATA_SCHEMA_ID,
    TEST_DATA_SCHEMA_VERSION,
    CanonicalTestDataDocument,
    TestCondition,
    TestDataChannel,
    TestDataSource,
    TestExecutionMetadata,
    TestMaterialMetadata,
    TestSpecimenMetadata,
    canonical_test_data,
)
from cmp.modules.datasets.domain.governed_tabular import GovernedImportConflict
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

TEST_DATA_DOCUMENT_AGGREGATE_TYPE = "datasets.test_data_document"
NORMALIZED_PARQUET_SCHEMA = "urn:cmp:test-data:normalized-parquet:1.0.0"
_write_parquet = cast(Callable[..., None], pq.write_table)


@dataclass(frozen=True, slots=True)
class TestDataChannelSummary:
    key: str
    name: str
    quantity_semantics: str
    axis_role: str
    original_unit_string: str
    normalized_unit: str
    normalization_scale: str
    normalization_offset: str
    point_count: int
    missing_count: int


@dataclass(frozen=True, slots=True)
class TestDataDocumentContent:
    document_key: str
    material: TestMaterialMetadata
    test: TestExecutionMetadata
    specimen: TestSpecimenMetadata
    conditions: tuple[TestCondition, ...]
    channels: tuple[TestDataChannelSummary, ...]
    source: TestDataSource
    canonical_artifact_id: UUID
    canonical_sha256: str
    normalized_artifact_id: UUID
    normalized_sha256: str
    point_count: int


@dataclass(frozen=True, slots=True)
class TestDataDocumentSnapshot:
    id: UUID
    current: RevisionRecord
    content: TestDataDocumentContent


@dataclass(frozen=True, slots=True)
class ImportCanonicalTestData:
    classification: DataClassification
    document: CanonicalTestDataDocument
    change_reason: str


@dataclass(frozen=True, slots=True)
class ReviseCanonicalTestData:
    expected_current_revision_id: UUID
    document: CanonicalTestDataDocument
    change_reason: str


class CanonicalTestDataRepository(Protocol):
    def document_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[TestDataDocumentContent]: ...

    def get_document(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        document_id: UUID,
    ) -> TestDataDocumentSnapshot: ...

    def get_document_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        document_id: UUID,
        revision_id: UUID,
    ) -> TestDataDocumentSnapshot: ...

    def list_documents(
        self, *, context: SecurityContext, decision: AuthorizationDecision
    ) -> tuple[TestDataDocumentSnapshot, ...]: ...


def test_data_content_canonical(value: TestDataDocumentContent) -> dict[str, object]:
    return {
        "document_key": value.document_key,
        "material": {
            "maker": value.material.maker,
            "grade": value.material.grade,
            "lot_batch": value.material.lot_batch,
        },
        "test": {
            "date": value.test.test_date.isoformat(),
            "operator": value.test.operator,
            "laboratory": value.test.laboratory,
            "method": value.test.method,
            "equipment_maker": value.test.equipment_maker,
            "equipment_model": value.test.equipment_model,
        },
        "specimen": {
            "specimen_id": value.specimen.specimen_id,
            "description": value.specimen.description,
        },
        "conditions": [
            {
                "key": item.key,
                "quantity_semantics": item.quantity_semantics,
                "original_value": str(item.original_value),
                "original_unit_string": item.original_unit_string,
                "normalized_value": str(item.normalized_value),
                "normalized_unit": item.normalized_unit,
            }
            for item in value.conditions
        ],
        "channels": [
            {
                key: getattr(item, key)
                for key in TestDataChannelSummary.__dataclass_fields__
            }
            for item in value.channels
        ],
        "source": {
            "file_name": value.source.file_name,
            "media_type": value.source.media_type,
            "sha256": value.source.sha256,
        },
        "canonical_artifact_id": str(value.canonical_artifact_id),
        "canonical_sha256": value.canonical_sha256,
        "normalized_artifact_id": str(value.normalized_artifact_id),
        "normalized_sha256": value.normalized_sha256,
        "point_count": value.point_count,
    }


def canonical_json_bytes(document: CanonicalTestDataDocument) -> bytes:
    value = (
        json.dumps(
            canonical_test_data(document),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        + b"\n"
    )
    if len(value) > MAX_CANONICAL_JSON_BYTES:
        raise ValueError("canonical Test Data JSON exceeds the 25 MiB single-document limit")
    return value


def normalized_parquet_bytes(document: CanonicalTestDataDocument) -> bytes:
    fields: dict[str, pa.Array] = {}
    metadata: dict[bytes, bytes] = {
        b"cmp.schema": NORMALIZED_PARQUET_SCHEMA.encode(),
        b"cmp.document_sha256": document.digest.encode(),
    }
    for channel in document.channels:
        fields[channel.key] = pa.array(
            [float(value) if value is not None else None for value in channel.normalized_values],
            type=pa.float64(),
        )
        prefix = f"cmp.channel.{channel.key}.".encode()
        metadata[prefix + b"quantity_semantics"] = channel.quantity_semantics.encode()
        metadata[prefix + b"normalized_unit"] = channel.normalized_unit.encode()
    table = pa.table(fields).replace_schema_metadata(metadata)
    buffer = io.BytesIO()
    _write_parquet(table, buffer, compression="zstd", write_statistics=True)
    return buffer.getvalue()


def _require(
    context: SecurityContext,
    decision: AuthorizationDecision,
    permission: Permission,
) -> None:
    if (
        decision.principal_id != context.principal.id
        or decision.organization_id != context.organization_id
        or decision.project_id != context.project_id
        or decision.request_id != context.request_id
        or decision.trace_id != context.trace_id
        or permission.value not in decision.database_permissions
    ):
        raise GovernedImportConflict("authorization decision lacks canonical Test Data capability")


class CanonicalTestDataService:
    def __init__(
        self,
        *,
        repository: CanonicalTestDataRepository,
        artifacts: ArtifactService,
        id_factory: Callable[[], UUID] = uuid4,
    ) -> None:
        self._repository = repository
        self._artifacts = artifacts
        self._id = id_factory

    async def import_document(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: ImportCanonicalTestData,
    ) -> TestDataDocumentSnapshot:
        _require(context, decision, Permission.DATASET_WRITE)
        document = command.document
        content = await self._finalize_content(
            context,
            decision,
            classification=command.classification,
            document=document,
        )
        document_id = self._id()
        record = RevisionService(
            aggregate_type=TEST_DATA_DOCUMENT_AGGREGATE_TYPE,
            store=self._repository.document_store(context, decision),
        ).create(
            CreateRevisionedAggregate(
                aggregate_id=document_id,
                scope=TenantScope(
                    context.organization_id,
                    context.project_id,
                    command.classification.value,
                ),
                schema_id=TEST_DATA_SCHEMA_ID,
                schema_version=TEST_DATA_SCHEMA_VERSION,
                content=content,
                created_by=context.principal.id,
                change_reason=command.change_reason,
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        return TestDataDocumentSnapshot(document_id, record, content)

    async def revise_document(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        document_id: UUID,
        command: ReviseCanonicalTestData,
    ) -> TestDataDocumentSnapshot:
        _require(context, decision, Permission.DATASET_WRITE)
        current = self._repository.get_document(
            context=context,
            decision=decision,
            document_id=document_id,
        )
        if current.content.document_key != command.document.document_id:
            raise GovernedImportConflict("Test Data document_id cannot change across revisions")
        classification = DataClassification(current.current.scope.classification)
        content = await self._finalize_content(
            context,
            decision,
            classification=classification,
            document=command.document,
        )
        record = RevisionService(
            aggregate_type=TEST_DATA_DOCUMENT_AGGREGATE_TYPE,
            store=self._repository.document_store(context, decision),
        ).revise(
            ReviseAggregate(
                aggregate_id=document_id,
                scope=current.current.scope,
                expected_current_revision_id=command.expected_current_revision_id,
                based_on_revision_id=command.expected_current_revision_id,
                schema_id=TEST_DATA_SCHEMA_ID,
                schema_version=TEST_DATA_SCHEMA_VERSION,
                content=content,
                created_by=context.principal.id,
                change_reason=command.change_reason,
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        return TestDataDocumentSnapshot(document_id, record, content)

    async def _finalize_content(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        *,
        classification: DataClassification,
        document: CanonicalTestDataDocument,
    ) -> TestDataDocumentContent:
        canonical_bytes = canonical_json_bytes(document)
        canonical_artifact = await self._artifacts.finalize_derived_bytes(
            context,
            decision,
            classification=classification,
            artifact_role="test-data.canonical-json",
            schema_ref=TEST_DATA_SCHEMA_ID,
            media_type="application/vnd.cmp.test-data+json",
            value=canonical_bytes,
            idempotency_key=f"test-data-json:{document.digest}",
        )
        parquet = normalized_parquet_bytes(document)
        normalized_artifact = await self._artifacts.finalize_derived_bytes(
            context,
            decision,
            classification=classification,
            artifact_role="test-data.normalized-parquet",
            schema_ref=NORMALIZED_PARQUET_SCHEMA,
            media_type="application/vnd.apache.parquet",
            value=parquet,
            idempotency_key=f"test-data-parquet:{document.digest}",
        )
        return TestDataDocumentContent(
            document_key=document.document_id,
            material=document.material,
            test=document.test,
            specimen=document.specimen,
            conditions=document.conditions,
            channels=tuple(self._summary(item) for item in document.channels),
            source=document.source,
            canonical_artifact_id=canonical_artifact.artifact.id,
            canonical_sha256=canonical_artifact.artifact.sha256,
            normalized_artifact_id=normalized_artifact.artifact.id,
            normalized_sha256=normalized_artifact.artifact.sha256,
            point_count=document.point_count,
        )

    @staticmethod
    def _summary(channel: TestDataChannel) -> TestDataChannelSummary:
        return TestDataChannelSummary(
            key=channel.key,
            name=channel.name,
            quantity_semantics=channel.quantity_semantics,
            axis_role=channel.axis_role.value,
            original_unit_string=channel.original_unit_string,
            normalized_unit=channel.normalized_unit,
            normalization_scale=str(channel.normalization_scale),
            normalization_offset=str(channel.normalization_offset),
            point_count=len(channel.original_values),
            missing_count=sum(value is None for value in channel.original_values),
        )

    async def export_document(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        document_id: UUID,
        revision_id: UUID,
    ) -> tuple[TestDataDocumentSnapshot, bytes]:
        _require(context, decision, Permission.DATASET_READ)
        snapshot = self._repository.get_document_revision(
            context=context,
            decision=decision,
            document_id=document_id,
            revision_id=revision_id,
        )
        artifact, value = await self._artifacts.read_verified_bytes(
            context,
            decision,
            snapshot.content.canonical_artifact_id,
            maximum_bytes=MAX_CANONICAL_JSON_BYTES,
        )
        if artifact.artifact.sha256 != snapshot.content.canonical_sha256:
            raise GovernedImportConflict("canonical Test Data Artifact digest pin is inconsistent")
        return snapshot, value

    def list_documents(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> tuple[TestDataDocumentSnapshot, ...]:
        _require(context, decision, Permission.DATASET_READ)
        return self._repository.list_documents(context=context, decision=decision)

    def get_document_for_write(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        document_id: UUID,
    ) -> TestDataDocumentSnapshot:
        _require(context, decision, Permission.DATASET_WRITE)
        return self._repository.get_document(
            context=context,
            decision=decision,
            document_id=document_id,
        )

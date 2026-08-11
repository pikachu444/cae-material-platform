"""Immutable import/export service for canonical Test Data JSON (T-52)."""

from __future__ import annotations

import hashlib
import io
import json
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from tempfile import SpooledTemporaryFile
from typing import Protocol, cast
from uuid import UUID, uuid4

import pyarrow as pa
import pyarrow.parquet as pq

from cmp.modules.artifacts.application.content import ArtifactService
from cmp.modules.datasets.curve_artifacts import LegacyParquetAdapter, resolve_curve_artifact
from cmp.modules.datasets.domain.canonical_test_data import (
    MAX_CANONICAL_JSON_BYTES,
    TEST_DATA_SCHEMA_ID,
    TEST_DATA_SCHEMA_VERSION,
    CanonicalTestDataDocument,
    ChannelAxisRole,
    TestCondition,
    TestDataChannel,
    TestDataSource,
    TestExecutionMetadata,
    TestMaterialMetadata,
    TestSpecimenMetadata,
    canonical_test_data,
)
from cmp.modules.datasets.domain.curve_metadata import (
    CURVE_DEFINITION_PARQUET_KEY,
    CURVE_DEFINITION_SHA256_PARQUET_KEY,
    ArtifactPin,
    AxisRole,
    CurveChannel,
    CurveDefinition,
    CurveMetadata,
    CurveSeries,
    CurveSeriesPreview,
    OriginalUnit,
    ProvenanceKind,
    ProvenancePointer,
    RevisionPin,
    SourcePin,
    UnitContract,
    ValueBasis,
    curve_definition_json_bytes,
)
from cmp.modules.datasets.domain.governed_tabular import GovernedImportConflict
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
    Permission,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.units.domain.system import DimensionId, UnitError, dimension_for_quantity_semantics
from cmp.shared.application.revisions import (
    CreateRevisionedAggregate,
    ReviseAggregate,
    RevisionService,
    RevisionStore,
)
from cmp.shared.domain.revisions import RevisionRecord, TenantScope

TEST_DATA_DOCUMENT_AGGREGATE_TYPE = "datasets.test_data_document"
NORMALIZED_PARQUET_SCHEMA_V1 = "urn:cmp:test-data:normalized-parquet:1.0.0"
NORMALIZED_PARQUET_SCHEMA = "urn:cmp:test-data:normalized-parquet:1.1.0"
_write_parquet = cast(Callable[..., None], pq.write_table)


class PackageStream(Protocol):
    def read(self, size: int = -1) -> bytes: ...
    def seek(self, offset: int, whence: int = 0) -> int: ...
    def tell(self) -> int: ...
    def close(self) -> None: ...


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
    governed_source: GovernedTestDataSource | None = None


@dataclass(frozen=True, slots=True)
class ExactRevisionRef:
    aggregate_id: UUID
    revision_id: UUID

    def __post_init__(self) -> None:
        if self.aggregate_id.int == 0 or self.revision_id.int == 0:
            raise GovernedImportConflict("governed source revision pins must be non-zero")


@dataclass(frozen=True, slots=True)
class GovernedTestDataSource:
    """Server-verified, exact context for Export-eligible Test Data only."""

    material: ExactRevisionRef
    material_state: ExactRevisionRef
    test_run: ExactRevisionRef


class GovernedTestDataSourceVerifier(Protocol):
    def verify(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        source: GovernedTestDataSource,
    ) -> None: ...


@dataclass(frozen=True, slots=True)
class TestDataDocumentSnapshot:
    id: UUID
    current: RevisionRecord
    content: TestDataDocumentContent


@dataclass(frozen=True, slots=True)
class CanonicalTestDataCurvePreview:
    metadata: CurveMetadata
    series: CurveSeriesPreview


@dataclass(frozen=True, slots=True)
class ImportCanonicalTestData:
    classification: DataClassification
    document: CanonicalTestDataDocument
    change_reason: str
    governed_source: GovernedTestDataSource | None = None


@dataclass(frozen=True, slots=True)
class ReviseCanonicalTestData:
    expected_current_revision_id: UUID
    document: CanonicalTestDataDocument
    change_reason: str
    governed_source: GovernedTestDataSource | None = None


@dataclass(frozen=True, slots=True)
class ExactTestDataRevisionRef:
    document_id: UUID
    revision_id: UUID


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
            {key: getattr(item, key) for key in TestDataChannelSummary.__dataclass_fields__}
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
        "governed_source": None
        if value.governed_source is None
        else {
            "material": {
                "aggregate_id": str(value.governed_source.material.aggregate_id),
                "revision_id": str(value.governed_source.material.revision_id),
            },
            "material_state": {
                "aggregate_id": str(value.governed_source.material_state.aggregate_id),
                "revision_id": str(value.governed_source.material_state.revision_id),
            },
            "test_run": {
                "aggregate_id": str(value.governed_source.test_run.aggregate_id),
                "revision_id": str(value.governed_source.test_run.revision_id),
            },
        },
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


def canonical_test_data_curve_definition(
    channels: tuple[TestDataChannel | TestDataChannelSummary, ...],
    *,
    value_basis: ValueBasis = ValueBasis.NORMALIZED,
) -> CurveDefinition:
    resolved: list[CurveChannel] = []
    for channel in channels:
        try:
            dimension: DimensionId | None = dimension_for_quantity_semantics(
                channel.quantity_semantics,
                location=f"channels.{channel.key}.quantity_semantics",
            )
            unit_contract = UnitContract.COMMON
        except UnitError:
            dimension = None
            unit_contract = UnitContract.EXPLICIT_LEGACY
        axis_role = AxisRole(
            channel.axis_role.value
            if isinstance(channel.axis_role, ChannelAxisRole)
            else channel.axis_role
        )
        resolved.append(
            CurveChannel(
                key=channel.key,
                label=channel.name,
                quantity_semantics=channel.quantity_semantics,
                axis_role=axis_role,
                unit_contract=unit_contract,
                dimension=dimension,
                original_units=(
                    OriginalUnit(
                        channel.original_unit_string,
                        str(channel.normalization_scale),
                        str(channel.normalization_offset),
                    ),
                ),
                normalized_unit=channel.normalized_unit,
                display_unit=channel.normalized_unit,
                display_scale="1",
                display_offset="0",
                value_basis=value_basis,
            )
        )
    return CurveDefinition(channels=tuple(resolved))


def canonical_test_data_curve_series(
    document: CanonicalTestDataDocument,
) -> CurveSeries:
    definition = canonical_test_data_curve_definition(document.channels)
    return CurveSeries(
        definition=definition,
        channels={
            channel.key: tuple(
                float(value) if value is not None else None
                for value in channel.normalized_values
            )
            for channel in document.channels
        },
        deviations={},
        source_counts={},
    )


def normalized_parquet_bytes(document: CanonicalTestDataDocument) -> bytes:
    definition = canonical_test_data_curve_definition(document.channels)
    fields: dict[str, pa.Array] = {}
    metadata: dict[bytes, bytes] = {
        b"cmp.schema": NORMALIZED_PARQUET_SCHEMA.encode(),
        b"cmp.document_sha256": document.digest.encode(),
        CURVE_DEFINITION_PARQUET_KEY: curve_definition_json_bytes(definition),
        CURVE_DEFINITION_SHA256_PARQUET_KEY: definition.sha256.encode("ascii"),
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
        governed_source_verifier: GovernedTestDataSourceVerifier | None = None,
        id_factory: Callable[[], UUID] = uuid4,
    ) -> None:
        self._repository = repository
        self._artifacts = artifacts
        self._governed_source_verifier = governed_source_verifier
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
            governed_source=command.governed_source,
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
            governed_source=command.governed_source,
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
        governed_source: GovernedTestDataSource | None,
    ) -> TestDataDocumentContent:
        if governed_source is not None:
            if self._governed_source_verifier is None:
                raise GovernedImportConflict(
                    "governed Test Data source verification is unavailable"
                )
            self._governed_source_verifier.verify(context, decision, governed_source)
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
            governed_source=governed_source,
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

    async def preview_curve(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        document_id: UUID,
        revision_id: UUID,
        *,
        maximum_points: int,
    ) -> CanonicalTestDataCurvePreview:
        _require(context, decision, Permission.DATASET_READ)
        snapshot = self._repository.get_document_revision(
            context=context,
            decision=decision,
            document_id=document_id,
            revision_id=revision_id,
        )
        artifact_record, value = await self._artifacts.read_verified_bytes(
            context,
            decision,
            snapshot.content.normalized_artifact_id,
            maximum_bytes=64 * 1024 * 1024,
        )
        artifact = artifact_record.artifact
        if artifact.sha256 != snapshot.content.normalized_sha256:
            raise GovernedImportConflict(
                "normalized Test Data Artifact digest pin is inconsistent"
            )
        if artifact.schema_ref not in {NORMALIZED_PARQUET_SCHEMA_V1, NORMALIZED_PARQUET_SCHEMA}:
            raise GovernedImportConflict(
                "normalized Test Data Artifact schema differs from its typed revision"
            )
        legacy_definition = canonical_test_data_curve_definition(snapshot.content.channels)
        resolution = resolve_curve_artifact(
            value,
            schema_ref=artifact.schema_ref,
            expected_sha256=artifact.sha256,
            legacy_adapter=LegacyParquetAdapter(
                definition=legacy_definition,
                channel_columns={
                    channel.key: channel.key for channel in legacy_definition.channels
                },
                deviation_columns={},
                source_count_columns={},
            ),
            declared_required=artifact.schema_ref == NORMALIZED_PARQUET_SCHEMA,
        )
        assert resolution.series is not None
        if resolution.series.point_count != snapshot.content.point_count:
            raise GovernedImportConflict(
                "normalized Test Data Artifact point count differs from its revision"
            )
        sources: tuple[SourcePin, ...] = ()
        provenance: tuple[ProvenancePointer, ...] = ()
        if snapshot.content.governed_source is not None:
            source = snapshot.content.governed_source.test_run
            sources = (
                SourcePin(
                    entity_type="test_run",
                    entity_id=source.aggregate_id,
                    revision_id=source.revision_id,
                ),
            )
            provenance = (
                ProvenancePointer(
                    kind=ProvenanceKind.INPUT_USAGE,
                    entity_id=source.aggregate_id,
                    revision_id=source.revision_id,
                ),
            )
        metadata = CurveMetadata(
            state=resolution.state,
            definition=resolution.series.definition,
            owning_revision=RevisionPin(
                entity_type="test_data_document",
                entity_id=snapshot.id,
                revision_id=snapshot.current.revision_id,
            ),
            artifact=ArtifactPin(
                artifact_id=artifact.id,
                sha256=artifact.sha256,
                schema_ref=artifact.schema_ref,
                media_type=artifact.media_type,
            ),
            sources=sources,
            provenance=provenance,
        )
        return CanonicalTestDataCurvePreview(
            metadata=metadata,
            series=resolution.series.preview(maximum_points),
        )

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

    async def export_package(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        references: tuple[ExactTestDataRevisionRef, ...],
    ) -> tuple[PackageStream, str, int]:
        _require(context, decision, Permission.DATASET_READ)
        if not 1 <= len(references) <= 100:
            raise GovernedImportConflict("Test Data package requires 1..100 exact revisions")
        if len(set(references)) != len(references):
            raise GovernedImportConflict("Test Data package contains duplicate revision references")
        files: dict[str, bytes] = {}
        entries: list[dict[str, object]] = []
        for reference in sorted(
            references, key=lambda item: (str(item.document_id), str(item.revision_id))
        ):
            snapshot, value = await self.export_document(
                context,
                decision,
                reference.document_id,
                reference.revision_id,
            )
            path = f"test-data/{reference.document_id}/{reference.revision_id}.json"
            files[path] = value
            entries.append(
                {
                    "document_id": str(reference.document_id),
                    "document_key": snapshot.content.document_key,
                    "revision_id": str(reference.revision_id),
                    "revision_no": snapshot.current.revision_no,
                    "path": path,
                    "sha256": snapshot.content.canonical_sha256,
                    "size_bytes": len(value),
                }
            )
        manifest = {
            "document_type": "cmp.test-data-package",
            "schema_version": "1.0.0",
            "entry_count": len(entries),
            "entries": entries,
        }
        files["manifest.json"] = (
            json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
                "utf-8"
            )
            + b"\n"
        )
        files["README.txt"] = (
            b"CMP canonical Test Data package 1.0.0\n"
            b"Verify checksums.sha256 before importing exact revision evidence.\n"
        )
        files["checksums.sha256"] = "".join(
            f"{hashlib.sha256(value).hexdigest()}  {path}\n"
            for path, value in sorted(files.items())
        ).encode("ascii")
        buffer = SpooledTemporaryFile(max_size=8 * 1024 * 1024, mode="w+b")
        with zipfile.ZipFile(
            buffer, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9, strict_timestamps=True
        ) as archive:
            for path, value in sorted(files.items()):
                info = zipfile.ZipInfo(path, date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                archive.writestr(info, value, compresslevel=9)
        size = buffer.tell()
        buffer.seek(0)
        package_hash = hashlib.sha256()
        while chunk := buffer.read(1024 * 1024):
            package_hash.update(chunk)
        buffer.seek(0)
        return buffer, package_hash.hexdigest(), size

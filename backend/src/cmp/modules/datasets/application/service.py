"""Create raw/normalized immutable Dataset revisions from a user-confirmed CSV mapping."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import NAMESPACE_URL, UUID, uuid5

from cmp.modules.artifacts.application.content import ArtifactService
from cmp.modules.artifacts.domain.content import ArtifactKind
from cmp.modules.datasets.domain.reference_tensile import (
    REFERENCE_TENSILE_PARQUET_SCHEMA,
    REFERENCE_TENSILE_SCHEMA_VERSION,
    CurvePoint,
    DatasetConflict,
    DatasetContent,
    DatasetRepresentation,
    InvalidDatasetData,
    ParsedReferenceTensile,
    ReferenceTensileMapping,
    normalized_parquet_bytes,
    normalized_points_from_parquet,
    parse_reference_tensile_csv,
    preview_points,
)
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
    Permission,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.testing.domain.reference_tensile import REFERENCE_TENSILE_METHOD_CODE
from cmp.shared.application.revisions import (
    CreateRevisionedAggregate,
    ReviseAggregate,
    RevisionService,
    RevisionStore,
)
from cmp.shared.domain.revisions import (
    AggregateAlreadyExists,
    RevisionConflict,
    RevisionRecord,
    TenantScope,
)

DATASET_AGGREGATE_TYPE = "datasets.dataset"
DATASET_SCHEMA_ID = "urn:cmp:datasets:reference-uniaxial-tensile:1.0.0"


@dataclass(frozen=True, slots=True)
class RevisionSnapshot[ContentT]:
    record: RevisionRecord
    content: ContentT


@dataclass(frozen=True, slots=True)
class DatasetSnapshot:
    id: UUID
    test_run_id: UUID
    current: RevisionSnapshot[DatasetContent]


@dataclass(frozen=True, slots=True)
class DatasetRevisionSnapshot:
    dataset_id: UUID
    revision: RevisionSnapshot[DatasetContent]


@dataclass(frozen=True, slots=True)
class ReferenceTestRunSource:
    classification: DataClassification
    test_method_code: str


@dataclass(frozen=True, slots=True)
class ImportReferenceTensileCsv:
    test_run_id: UUID
    test_run_revision_id: UUID
    raw_asset_id: UUID
    raw_artifact_id: UUID
    mapping: ReferenceTensileMapping
    change_reason: str


@dataclass(frozen=True, slots=True)
class CurvePreview:
    dataset_id: UUID
    dataset_revision_id: UUID
    representation: DatasetRepresentation
    point_count: int
    returned_point_count: int
    sampled: bool
    strain_unit: str
    stress_unit: str
    points: tuple[CurvePoint, ...]


class DatasetRepository(Protocol):
    def dataset_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[DatasetContent]: ...

    def load_reference_test_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        test_run_id: UUID,
        test_run_revision_id: UUID,
    ) -> ReferenceTestRunSource: ...

    def get_dataset(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        dataset_id: UUID,
    ) -> DatasetSnapshot: ...

    def get_dataset_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        dataset_revision_id: UUID,
    ) -> DatasetRevisionSnapshot: ...

    def list_dataset_revisions(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        dataset_id: UUID,
    ) -> tuple[RevisionSnapshot[DatasetContent], ...]: ...

    def list_datasets_for_material_state(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_state_id: UUID,
    ) -> tuple[DatasetSnapshot, ...]: ...


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
        raise DatasetConflict("authorization decision does not match Dataset request")


class DatasetService:
    """Reference-only importer that preserves raw bytes and creates a Parquet normalization."""

    def __init__(
        self,
        *,
        repository: DatasetRepository,
        artifacts: ArtifactService,
    ) -> None:
        self._repository = repository
        self._artifacts = artifacts

    @staticmethod
    def _dataset_id(
        context: SecurityContext,
        command: ImportReferenceTensileCsv,
    ) -> UUID:
        return uuid5(
            NAMESPACE_URL,
            "cmp:reference-tensile-dataset:"
            f"{context.organization_id}:{context.project_id}:{command.test_run_revision_id}:"
            f"{command.raw_artifact_id}:{command.mapping.digest}",
        )

    @staticmethod
    def _matches_source(existing: DatasetContent, expected: DatasetContent) -> bool:
        """Return whether an existing deterministic Dataset identity has the same source."""

        return (
            existing.test_run_id == expected.test_run_id
            and existing.test_run_revision_id == expected.test_run_revision_id
            and existing.raw_asset_id == expected.raw_asset_id
            and existing.raw_artifact_id == expected.raw_artifact_id
            and existing.mapping == expected.mapping
            and existing.point_count == expected.point_count
        )

    @classmethod
    def _matches_raw_input(cls, existing: DatasetContent, expected: DatasetContent) -> bool:
        return (
            existing.representation is DatasetRepresentation.RAW
            and cls._matches_source(existing, expected)
            and existing.data_artifact_id == expected.data_artifact_id
            and existing.data_sha256 == expected.data_sha256
        )

    @staticmethod
    def _matches_normalized_result(
        existing: DatasetContent,
        expected: DatasetContent,
    ) -> bool:
        return (
            existing.representation is DatasetRepresentation.NORMALIZED
            and existing.test_run_id == expected.test_run_id
            and existing.test_run_revision_id == expected.test_run_revision_id
            and existing.raw_asset_id == expected.raw_asset_id
            and existing.raw_artifact_id == expected.raw_artifact_id
            and existing.data_artifact_id == expected.data_artifact_id
            and existing.data_sha256 == expected.data_sha256
            and existing.source_dataset_revision_id == expected.source_dataset_revision_id
            and existing.mapping == expected.mapping
            and existing.point_count == expected.point_count
        )

    async def import_reference_tensile_csv(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: ImportReferenceTensileCsv,
    ) -> DatasetSnapshot:
        _require(context, decision, Permission.DATASET_WRITE)
        run = self._repository.load_reference_test_run(
            context=context,
            decision=decision,
            test_run_id=command.test_run_id,
            test_run_revision_id=command.test_run_revision_id,
        )
        if run.test_method_code != REFERENCE_TENSILE_METHOD_CODE:
            raise DatasetConflict("reference CSV import requires the reference tensile Test Run")
        raw_record, raw_bytes = await self._artifacts.read_verified_bytes(
            context,
            decision,
            command.raw_artifact_id,
            maximum_bytes=16 * 1024 * 1024,
        )
        artifact = raw_record.artifact
        if (
            artifact.artifact_kind is not ArtifactKind.RAW
            or artifact.source_raw_asset_id != command.raw_asset_id
            or artifact.media_type != "text/csv"
        ):
            raise DatasetConflict(
                "reference CSV import requires the completed text/csv Artifact "
                "for the named Raw Asset"
            )
        if (
            artifact.organization_id != context.organization_id
            or artifact.project_id != context.project_id
            or artifact.classification is not run.classification
        ):
            raise DatasetConflict("Raw Asset classification or tenant differs from the Test Run")
        parsed = parse_reference_tensile_csv(raw_bytes, command.mapping)
        dataset_id = self._dataset_id(context, command)
        scope = TenantScope(
            context.organization_id, context.project_id, run.classification.value
        )
        raw_content = DatasetContent(
            test_run_id=command.test_run_id,
            test_run_revision_id=command.test_run_revision_id,
            raw_asset_id=command.raw_asset_id,
            raw_artifact_id=command.raw_artifact_id,
            data_artifact_id=command.raw_artifact_id,
            data_sha256=artifact.sha256,
            representation=DatasetRepresentation.RAW,
            source_dataset_revision_id=None,
            point_count=len(parsed.raw_points),
            mapping=command.mapping,
        )
        service = RevisionService(
            aggregate_type=DATASET_AGGREGATE_TYPE,
            store=self._repository.dataset_store(context, decision),
        )
        try:
            raw_record_revision = service.create(
                CreateRevisionedAggregate(
                    aggregate_id=dataset_id,
                    scope=scope,
                    schema_id=DATASET_SCHEMA_ID,
                    schema_version=REFERENCE_TENSILE_SCHEMA_VERSION,
                    content=raw_content,
                    created_by=context.principal.id,
                    change_reason=command.change_reason,
                    request_id=context.request_id,
                    trace_id=context.trace_id,
                )
            )
        except AggregateAlreadyExists as error:
            existing = self._repository.get_dataset(
                context=context, decision=decision, dataset_id=dataset_id
            )
            if existing.current.content.representation is DatasetRepresentation.NORMALIZED:
                # The immutable pair was already completed by an equivalent request.
                if not self._matches_source(existing.current.content, raw_content):
                    raise DatasetConflict(
                        "deterministic Dataset identity is already bound to a different source"
                    ) from error
                return existing
            if not self._matches_raw_input(existing.current.content, raw_content):
                raise DatasetConflict(
                    "deterministic Dataset identity is already bound to a different raw source"
                ) from error
            raw_record_revision = existing.current.record
        normalized_bytes = normalized_parquet_bytes(parsed.normalized_points)
        derived = await self._artifacts.finalize_derived_bytes(
            context,
            decision,
            classification=run.classification,
            artifact_role="dataset.normalized_curve",
            schema_ref=REFERENCE_TENSILE_PARQUET_SCHEMA,
            media_type="application/vnd.apache.parquet",
            value=normalized_bytes,
            idempotency_key=(
                f"dataset:{command.test_run_revision_id}:{command.raw_artifact_id}:"
                f"{command.mapping.digest}"
            ),
        )
        normalized_content = DatasetContent(
            test_run_id=command.test_run_id,
            test_run_revision_id=command.test_run_revision_id,
            raw_asset_id=command.raw_asset_id,
            raw_artifact_id=command.raw_artifact_id,
            data_artifact_id=derived.artifact.id,
            data_sha256=derived.artifact.sha256,
            representation=DatasetRepresentation.NORMALIZED,
            source_dataset_revision_id=raw_record_revision.revision_id,
            point_count=len(parsed.normalized_points),
            mapping=command.mapping,
        )
        try:
            normalized_record = service.revise(
                ReviseAggregate(
                    aggregate_id=dataset_id,
                    scope=scope,
                    expected_current_revision_id=raw_record_revision.revision_id,
                    based_on_revision_id=raw_record_revision.revision_id,
                    schema_id=DATASET_SCHEMA_ID,
                    schema_version=REFERENCE_TENSILE_SCHEMA_VERSION,
                    content=normalized_content,
                    created_by=context.principal.id,
                    change_reason="normalize reference tensile CSV",
                    request_id=context.request_id,
                    trace_id=context.trace_id,
                )
            )
        except RevisionConflict as error:
            existing = self._repository.get_dataset(
                context=context, decision=decision, dataset_id=dataset_id
            )
            if self._matches_normalized_result(existing.current.content, normalized_content):
                return existing
            raise DatasetConflict("Dataset normalization head changed concurrently") from error
        return DatasetSnapshot(
            dataset_id,
            command.test_run_id,
            RevisionSnapshot(normalized_record, normalized_content),
        )

    def get_dataset(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        dataset_id: UUID,
    ) -> DatasetSnapshot:
        _require(context, decision, Permission.DATASET_READ)
        return self._repository.get_dataset(
            context=context, decision=decision, dataset_id=dataset_id
        )

    def list_dataset_revisions(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        dataset_id: UUID,
    ) -> tuple[RevisionSnapshot[DatasetContent], ...]:
        _require(context, decision, Permission.DATASET_READ)
        return self._repository.list_dataset_revisions(
            context=context, decision=decision, dataset_id=dataset_id
        )

    def list_datasets_for_material_state(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_state_id: UUID,
    ) -> tuple[DatasetSnapshot, ...]:
        _require(context, decision, Permission.DATASET_READ)
        return self._repository.list_datasets_for_material_state(
            context=context, decision=decision, material_state_id=material_state_id
        )

    async def preview_curve(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        dataset_revision_id: UUID,
        *,
        maximum_points: int,
    ) -> CurvePreview:
        _require(context, decision, Permission.DATASET_READ)
        snapshot = self._repository.get_dataset_revision(
            context=context,
            decision=decision,
            dataset_revision_id=dataset_revision_id,
        )
        content = snapshot.revision.content
        _, data = await self._artifacts.read_verified_bytes(
            context,
            decision,
            content.data_artifact_id,
            maximum_bytes=16 * 1024 * 1024,
        )
        if content.representation is DatasetRepresentation.RAW:
            parsed: ParsedReferenceTensile = parse_reference_tensile_csv(data, content.mapping)
            points = parsed.raw_points
            strain_unit = content.mapping.strain_unit
            stress_unit = content.mapping.stress_unit
        else:
            points = normalized_points_from_parquet(data)
            strain_unit = "1"
            stress_unit = "Pa"
        if len(points) != content.point_count:
            raise InvalidDatasetData("Dataset Artifact point count differs from immutable revision")
        preview = preview_points(points, maximum_points)
        return CurvePreview(
            dataset_id=snapshot.dataset_id,
            dataset_revision_id=snapshot.revision.record.revision_id,
            representation=content.representation,
            point_count=len(points),
            returned_point_count=len(preview),
            sampled=len(preview) != len(points),
            strain_unit=strain_unit,
            stress_unit=stress_unit,
            points=preview,
        )

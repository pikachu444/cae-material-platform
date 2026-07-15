"""Import immutable raw and normalized reference shear-relaxation Datasets."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import NAMESPACE_URL, UUID, uuid5

from cmp.modules.artifacts.application.content import ArtifactService
from cmp.modules.artifacts.domain.content import ArtifactKind
from cmp.modules.datasets.application.service import ReferenceTestRunSource, RevisionSnapshot
from cmp.modules.datasets.domain.reference_shear_relaxation import (
    REFERENCE_SHEAR_RELAXATION_IMPORTER_ID,
    REFERENCE_SHEAR_RELAXATION_PARQUET_SCHEMA,
    REFERENCE_SHEAR_RELAXATION_SCHEMA_VERSION,
    InvalidShearRelaxationData,
    ShearRelaxationConflict,
    ShearRelaxationMapping,
    ShearRelaxationPoint,
    parse_shear_relaxation_csv,
    preview_shear_relaxation_points,
    shear_relaxation_parquet_bytes,
    shear_relaxation_points_from_parquet,
)
from cmp.modules.identity_access.domain.authorization import AuthorizationDecision, Permission
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.testing.domain.reference_tensile import REFERENCE_SHEAR_RELAXATION_METHOD_CODE
from cmp.shared.application.revisions import (
    CreateRevisionedAggregate,
    ReviseAggregate,
    RevisionService,
    RevisionStore,
)
from cmp.shared.domain.revisions import (
    AggregateAlreadyExists,
    RevisionConflict,
    TenantScope,
)

SHEAR_RELAXATION_DATASET_AGGREGATE_TYPE = "datasets.shear_relaxation_dataset"
SHEAR_RELAXATION_DATASET_SCHEMA_ID = "urn:cmp:datasets:reference-shear-relaxation-dataset:1.0.0"


@dataclass(frozen=True, slots=True)
class ShearRelaxationDatasetContent:
    material_state_id: UUID
    material_state_revision_id: UUID
    test_run_id: UUID
    test_run_revision_id: UUID
    raw_asset_id: UUID
    raw_artifact_id: UUID
    data_artifact_id: UUID
    data_sha256: str
    representation: str
    source_dataset_revision_id: UUID | None
    point_count: int
    mapping: ShearRelaxationMapping
    importer_id: str = REFERENCE_SHEAR_RELAXATION_IMPORTER_ID
    importer_version: str = REFERENCE_SHEAR_RELAXATION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name in (
            "material_state_id",
            "material_state_revision_id",
            "test_run_id",
            "test_run_revision_id",
            "raw_asset_id",
            "raw_artifact_id",
            "data_artifact_id",
        ):
            if getattr(self, name).int == 0:
                raise InvalidShearRelaxationData(f"{name} must be non-zero")
        if self.representation not in {"raw", "normalized"}:
            raise InvalidShearRelaxationData("representation must be raw or normalized")
        if not 3 <= self.point_count <= 100_000:
            raise InvalidShearRelaxationData("point_count must be within 3..100000")
        if len(self.data_sha256) != 64 or any(
            c not in "0123456789abcdef" for c in self.data_sha256
        ):
            raise InvalidShearRelaxationData("data_sha256 must be lowercase SHA-256")
        if self.representation == "raw":
            if (
                self.source_dataset_revision_id is not None
                or self.data_artifact_id != self.raw_artifact_id
            ):
                raise InvalidShearRelaxationData("raw revision must point only to its raw Artifact")
        elif (
            self.source_dataset_revision_id is None or self.data_artifact_id == self.raw_artifact_id
        ):
            raise InvalidShearRelaxationData(
                "normalized revision requires a distinct Artifact and exact raw source revision"
            )

    def canonical(self) -> dict[str, object]:
        return {
            "material_state_id": str(self.material_state_id),
            "material_state_revision_id": str(self.material_state_revision_id),
            "test_run_id": str(self.test_run_id),
            "test_run_revision_id": str(self.test_run_revision_id),
            "raw_asset_id": str(self.raw_asset_id),
            "raw_artifact_id": str(self.raw_artifact_id),
            "data_artifact_id": str(self.data_artifact_id),
            "data_sha256": self.data_sha256,
            "representation": self.representation,
            "source_dataset_revision_id": (
                str(self.source_dataset_revision_id)
                if self.source_dataset_revision_id is not None
                else None
            ),
            "point_count": self.point_count,
            "mapping": self.mapping.canonical(),
            "channels": [
                {
                    "name": "time",
                    "quantity_kind": "time",
                    "original_column": self.mapping.time_column,
                    "original_unit": self.mapping.time_unit,
                    "normalized_unit": "s",
                    "axis_role": "independent",
                },
                {
                    "name": "relaxation_shear_modulus",
                    "quantity_kind": "shear_modulus",
                    "original_column": self.mapping.shear_modulus_column,
                    "original_unit": self.mapping.shear_modulus_unit,
                    "normalized_unit": "Pa",
                    "axis_role": "dependent",
                },
            ],
            "importer_id": self.importer_id,
            "importer_version": self.importer_version,
        }


@dataclass(frozen=True, slots=True)
class ImportReferenceShearRelaxationCsv:
    test_run_id: UUID
    test_run_revision_id: UUID
    raw_asset_id: UUID
    raw_artifact_id: UUID
    mapping: ShearRelaxationMapping
    change_reason: str


@dataclass(frozen=True, slots=True)
class ShearRelaxationDatasetSnapshot:
    id: UUID
    material_state_id: UUID
    current: RevisionSnapshot[ShearRelaxationDatasetContent]


@dataclass(frozen=True, slots=True)
class ShearRelaxationCurvePreview:
    dataset_id: UUID
    dataset_revision_id: UUID
    representation: str
    point_count: int
    returned_point_count: int
    time_unit: str
    modulus_unit: str
    points: tuple[ShearRelaxationPoint, ...]


class ShearRelaxationDatasetRepository(Protocol):
    def shear_relaxation_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[ShearRelaxationDatasetContent]: ...

    def load_reference_test_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        test_run_id: UUID,
        test_run_revision_id: UUID,
    ) -> ReferenceTestRunSource: ...

    def get(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        dataset_id: UUID,
    ) -> ShearRelaxationDatasetSnapshot: ...

    def list_for_material_state(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_state_id: UUID,
    ) -> tuple[ShearRelaxationDatasetSnapshot, ...]: ...


def _require(
    context: SecurityContext, decision: AuthorizationDecision, permission: Permission
) -> None:
    if (
        decision.permission is not permission
        or decision.principal_id != context.principal.id
        or decision.organization_id != context.organization_id
        or decision.project_id != context.project_id
        or decision.request_id != context.request_id
        or decision.trace_id != context.trace_id
    ):
        raise ShearRelaxationConflict("authorization decision does not match Dataset request")


class ShearRelaxationDatasetService:
    def __init__(
        self, *, repository: ShearRelaxationDatasetRepository, artifacts: ArtifactService
    ) -> None:
        self._repository = repository
        self._artifacts = artifacts

    async def import_csv(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: ImportReferenceShearRelaxationCsv,
    ) -> ShearRelaxationDatasetSnapshot:
        _require(context, decision, Permission.DATASET_WRITE)
        run = self._repository.load_reference_test_run(
            context=context,
            decision=decision,
            test_run_id=command.test_run_id,
            test_run_revision_id=command.test_run_revision_id,
        )
        if run.test_method_code != REFERENCE_SHEAR_RELAXATION_METHOD_CODE:
            raise ShearRelaxationConflict("import requires a shear-relaxation Test Run")
        raw_record, raw_bytes = await self._artifacts.read_verified_bytes(
            context, decision, command.raw_artifact_id, maximum_bytes=16 * 1024 * 1024
        )
        artifact = raw_record.artifact
        if (
            artifact.artifact_kind is not ArtifactKind.RAW
            or artifact.source_raw_asset_id != command.raw_asset_id
            or artifact.media_type != "text/csv"
            or artifact.classification is not run.classification
        ):
            raise ShearRelaxationConflict(
                "raw Artifact does not match the Test Run and CSV contract"
            )
        parsed = parse_shear_relaxation_csv(raw_bytes, command.mapping)
        dataset_id = uuid5(
            NAMESPACE_URL,
            "cmp:reference-shear-relaxation:"
            f"{context.organization_id}:{context.project_id}:{command.test_run_revision_id}:"
            f"{command.raw_artifact_id}:{command.mapping.digest}",
        )
        scope = TenantScope(context.organization_id, context.project_id, run.classification.value)
        raw = ShearRelaxationDatasetContent(
            run.material_state_id,
            run.material_state_revision_id,
            command.test_run_id,
            command.test_run_revision_id,
            command.raw_asset_id,
            command.raw_artifact_id,
            command.raw_artifact_id,
            artifact.sha256,
            "raw",
            None,
            len(parsed.raw_points),
            command.mapping,
        )
        revisions = RevisionService(
            aggregate_type=SHEAR_RELAXATION_DATASET_AGGREGATE_TYPE,
            store=self._repository.shear_relaxation_store(context, decision),
        )
        try:
            raw_revision = revisions.create(
                CreateRevisionedAggregate(
                    aggregate_id=dataset_id,
                    scope=scope,
                    schema_id=SHEAR_RELAXATION_DATASET_SCHEMA_ID,
                    schema_version=REFERENCE_SHEAR_RELAXATION_SCHEMA_VERSION,
                    content=raw,
                    created_by=context.principal.id,
                    change_reason=command.change_reason,
                    request_id=context.request_id,
                    trace_id=context.trace_id,
                )
            )
        except AggregateAlreadyExists:
            existing = self._repository.get(
                context=context, decision=decision, dataset_id=dataset_id
            )
            if existing.current.content.representation == "normalized":
                return existing
            raw_revision = existing.current.record
        normalized_bytes = shear_relaxation_parquet_bytes(parsed.normalized_points)
        derived = await self._artifacts.finalize_derived_bytes(
            context,
            decision,
            classification=run.classification,
            artifact_role="dataset.normalized_shear_relaxation_curve",
            schema_ref=REFERENCE_SHEAR_RELAXATION_PARQUET_SCHEMA,
            media_type="application/vnd.apache.parquet",
            value=normalized_bytes,
            idempotency_key=(
                f"shear-relaxation:{command.test_run_revision_id}:"
                f"{command.raw_artifact_id}:{command.mapping.digest}"
            ),
        )
        normalized = ShearRelaxationDatasetContent(
            run.material_state_id,
            run.material_state_revision_id,
            command.test_run_id,
            command.test_run_revision_id,
            command.raw_asset_id,
            command.raw_artifact_id,
            derived.artifact.id,
            derived.artifact.sha256,
            "normalized",
            raw_revision.revision_id,
            len(parsed.normalized_points),
            command.mapping,
        )
        try:
            record = revisions.revise(
                ReviseAggregate(
                    aggregate_id=dataset_id,
                    scope=scope,
                    expected_current_revision_id=raw_revision.revision_id,
                    based_on_revision_id=raw_revision.revision_id,
                    schema_id=SHEAR_RELAXATION_DATASET_SCHEMA_ID,
                    schema_version=REFERENCE_SHEAR_RELAXATION_SCHEMA_VERSION,
                    content=normalized,
                    created_by=context.principal.id,
                    change_reason="normalize reference shear-relaxation CSV",
                    request_id=context.request_id,
                    trace_id=context.trace_id,
                )
            )
        except RevisionConflict as error:
            existing = self._repository.get(
                context=context, decision=decision, dataset_id=dataset_id
            )
            if existing.current.content == normalized:
                return existing
            raise ShearRelaxationConflict("Dataset head changed concurrently") from error
        return ShearRelaxationDatasetSnapshot(
            dataset_id, run.material_state_id, RevisionSnapshot(record, normalized)
        )

    def list_for_material_state(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_state_id: UUID,
    ) -> tuple[ShearRelaxationDatasetSnapshot, ...]:
        _require(context, decision, Permission.DATASET_READ)
        return self._repository.list_for_material_state(
            context=context, decision=decision, material_state_id=material_state_id
        )

    async def preview(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        dataset_id: UUID,
        maximum_points: int,
    ) -> ShearRelaxationCurvePreview:
        _require(context, decision, Permission.DATASET_READ)
        snapshot = self._repository.get(context=context, decision=decision, dataset_id=dataset_id)
        content = snapshot.current.content
        _, value = await self._artifacts.read_verified_bytes(
            context, decision, content.data_artifact_id, maximum_bytes=16 * 1024 * 1024
        )
        if content.representation == "raw":
            points = parse_shear_relaxation_csv(value, content.mapping).raw_points
            time_unit = content.mapping.time_unit
            modulus_unit = content.mapping.shear_modulus_unit
        else:
            points = shear_relaxation_points_from_parquet(value)
            time_unit, modulus_unit = "s", "Pa"
        if len(points) != content.point_count:
            raise InvalidShearRelaxationData("Artifact point count differs from revision")
        preview = preview_shear_relaxation_points(points, maximum_points)
        return ShearRelaxationCurvePreview(
            snapshot.id,
            snapshot.current.record.revision_id,
            content.representation,
            len(points),
            len(preview),
            time_unit,
            modulus_unit,
            preview,
        )

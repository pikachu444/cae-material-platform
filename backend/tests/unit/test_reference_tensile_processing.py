from __future__ import annotations

import asyncio
import hashlib
from dataclasses import replace
from datetime import UTC, datetime
from typing import cast
from uuid import UUID, uuid4

import pytest
from cmp.modules.artifacts.application.content import ArtifactService
from cmp.modules.artifacts.domain.content import (
    Artifact,
    ArtifactKind,
    ArtifactRecord,
    IntegrityStatus,
    content_object_key,
)
from cmp.modules.datasets.application.service import (
    DATASET_AGGREGATE_TYPE,
    DATASET_SELECTION_AGGREGATE_TYPE,
    DatasetRevisionSnapshot,
    DatasetSelectionRevisionSnapshot,
    DatasetService,
    DatasetSnapshot,
    RegisterProcessedReferenceTensileDataset,
)
from cmp.modules.datasets.application.service import (
    RevisionSnapshot as DatasetRevisionSnapshotValue,
)
from cmp.modules.datasets.domain.reference_tensile import (
    REFERENCE_TENSILE_PARQUET_SCHEMA,
    REFERENCE_TENSILE_PROCESSED_PARQUET_SCHEMA,
    CurvePoint,
    DatasetContent,
    DatasetRepresentation,
    ReferenceTensileMapping,
    normalized_parquet_bytes,
    normalized_points_from_parquet,
)
from cmp.modules.datasets.domain.selection import ReferenceDatasetSelectionContent
from cmp.modules.identity_access.application.authorization import database_permissions_for
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
    Permission,
    Role,
)
from cmp.modules.identity_access.domain.security import (
    Principal,
    PrincipalType,
    SecurityContext,
)
from cmp.modules.processing.application.service import (
    PROCESSING_RECIPE_AGGREGATE_TYPE,
    ExecuteReferenceTensileCrop,
    ProcessingRecipeSnapshot,
    ProcessingRepository,
    ProcessingRun,
    ProcessingService,
    ReviseReferenceTensileCropRecipe,
)
from cmp.modules.processing.application.service import (
    RevisionSnapshot as ProcessingRevisionSnapshot,
)
from cmp.modules.processing.domain.reference_tensile_crop import (
    ProcessingConflict,
    ProcessingRunStatus,
    ReferenceTensileCropRecipeContent,
    crop_reference_tensile_points,
)
from cmp.shared.domain.revisions import RevisionRecord, TenantScope

NOW = datetime(2026, 7, 15, 10, 0, tzinfo=UTC)
ORG = UUID("f3000000-0000-4000-8000-000000000001")
PROJECT = UUID("f3000000-0000-4000-8000-000000000002")
ACTOR = UUID("f3000000-0000-4000-8000-000000000003")
TEST_RUN = UUID("f3000000-0000-4000-8000-000000000004")
TEST_RUN_REVISION = UUID("f3000000-0000-4000-8000-000000000005")
RAW_ASSET = UUID("f3000000-0000-4000-8000-000000000006")
RAW_ARTIFACT = UUID("f3000000-0000-4000-8000-000000000007")
DATASET = UUID("f3000000-0000-4000-8000-000000000008")
RAW_DATASET_REVISION = UUID("f3000000-0000-4000-8000-000000000009")
NORMALIZED_DATASET_REVISION = UUID("f3000000-0000-4000-8000-00000000000a")
NORMALIZED_ARTIFACT = UUID("f3000000-0000-4000-8000-00000000000b")
SELECTION = UUID("f3000000-0000-4000-8000-00000000000c")
SELECTION_REVISION = UUID("f3000000-0000-4000-8000-00000000000d")
RECIPE = UUID("f3000000-0000-4000-8000-00000000000e")
RECIPE_REVISION = UUID("f3000000-0000-4000-8000-00000000000f")
PROCESSING_RUN = UUID("f3000000-0000-4000-8000-000000000010")
PROCESSED_ARTIFACT = UUID("f3000000-0000-4000-8000-000000000011")
PROCESSED_DATASET = UUID("f3000000-0000-4000-8000-000000000012")
PROCESSED_DATASET_REVISION = UUID("f3000000-0000-4000-8000-000000000013")
TRACE = "00-000000000000000000000000000000f3-00000000000000f3-01"


def _context() -> SecurityContext:
    return SecurityContext(
        principal=Principal(ACTOR, PrincipalType.USER, "Material Modeler", True),
        organization_id=ORG,
        project_id=PROJECT,
        issuer="https://test-idp.invalid",
        subject=str(ACTOR),
        token_id=str(uuid4()),
        groups=(),
        scopes=("openid",),
        request_id=uuid4(),
        trace_id=TRACE,
        authenticated_at=NOW,
    )


CONTEXT = _context()
EXECUTE = AuthorizationDecision(
    principal_id=ACTOR,
    organization_id=ORG,
    project_id=PROJECT,
    permission=Permission.PROCESSING_EXECUTE,
    roles=(Role.MATERIAL_MODELER,),
    database_permissions=database_permissions_for(Permission.PROCESSING_EXECUTE),
    max_classification=DataClassification.INTERNAL,
    allow_export_controlled=False,
    request_id=CONTEXT.request_id,
    trace_id=TRACE,
    decided_at=NOW,
)


def _record(
    *,
    revision_id: UUID,
    aggregate_id: UUID,
    aggregate_type: str,
    revision_no: int = 1,
    based_on_revision_id: UUID | None = None,
) -> RevisionRecord:
    return RevisionRecord(
        revision_id=revision_id,
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        scope=TenantScope(ORG, PROJECT, DataClassification.INTERNAL.value),
        revision_no=revision_no,
        based_on_revision_id=based_on_revision_id,
        schema_id=f"urn:cmp:test:{aggregate_type}:1.0.0",
        schema_version="1.0.0",
        content_hash="a" * 64,
        created_at=NOW,
        created_by=ACTOR,
        change_reason="reference Processing test",
        request_id=CONTEXT.request_id,
        trace_id=TRACE,
    )


def _artifact(
    *,
    artifact_id: UUID,
    payload: bytes,
    schema_ref: str,
    role: str,
) -> ArtifactRecord:
    digest = hashlib.sha256(payload).hexdigest()
    return ArtifactRecord(
        artifact=Artifact(
            id=artifact_id,
            organization_id=ORG,
            project_id=PROJECT,
            classification=DataClassification.INTERNAL,
            artifact_kind=ArtifactKind.DERIVED,
            artifact_role=role,
            schema_ref=schema_ref,
            media_type="application/vnd.apache.parquet",
            size_bytes=len(payload),
            sha256=digest,
            storage_key=content_object_key(ORG, PROJECT, DataClassification.INTERNAL, digest),
            encryption_profile="test",
            source_raw_asset_id=None,
            source_pending_id=uuid4(),
            created_at=NOW,
            created_by=ACTOR,
        ),
        integrity_status=IntegrityStatus.VERIFIED,
        last_checked_at=NOW,
        last_observation_id=uuid4(),
    )


POINTS = (
    CurvePoint(0.0, 0.0),
    CurvePoint(0.01, 100_000_000.0),
    CurvePoint(0.02, 120_000_000.0),
    CurvePoint(0.03, 125_000_000.0),
)
MAPPING = ReferenceTensileMapping("strain_pct", "stress_mpa", "%", "MPa")


def _normalized_snapshot() -> DatasetRevisionSnapshot:
    content = DatasetContent(
        test_run_id=TEST_RUN,
        test_run_revision_id=TEST_RUN_REVISION,
        raw_asset_id=RAW_ASSET,
        raw_artifact_id=RAW_ARTIFACT,
        data_artifact_id=NORMALIZED_ARTIFACT,
        data_sha256="b" * 64,
        representation=DatasetRepresentation.NORMALIZED,
        source_dataset_revision_id=RAW_DATASET_REVISION,
        point_count=len(POINTS),
        mapping=MAPPING,
    )
    return DatasetRevisionSnapshot(
        dataset_id=DATASET,
        revision=DatasetRevisionSnapshotValue(
            _record(
                revision_id=NORMALIZED_DATASET_REVISION,
                aggregate_id=DATASET,
                aggregate_type=DATASET_AGGREGATE_TYPE,
                revision_no=2,
                based_on_revision_id=RAW_DATASET_REVISION,
            ),
            content,
        ),
    )


def _selection() -> DatasetSelectionRevisionSnapshot:
    content = ReferenceDatasetSelectionContent(
        selection_label="Reference crop input",
        dataset_id=DATASET,
        dataset_revision_id=NORMALIZED_DATASET_REVISION,
    )
    return DatasetSelectionRevisionSnapshot(
        selection_id=SELECTION,
        selection_label=content.selection_label,
        revision=DatasetRevisionSnapshotValue(
            _record(
                revision_id=SELECTION_REVISION,
                aggregate_id=SELECTION,
                aggregate_type=DATASET_SELECTION_AGGREGATE_TYPE,
            ),
            content,
        ),
    )


def _recipe() -> ProcessingRecipeSnapshot:
    content = ReferenceTensileCropRecipeContent("Elastic-window crop", 0.01, 0.03)
    return ProcessingRecipeSnapshot(
        id=RECIPE,
        current=ProcessingRevisionSnapshot(
            _record(
                revision_id=RECIPE_REVISION,
                aggregate_id=RECIPE,
                aggregate_type=PROCESSING_RECIPE_AGGREGATE_TYPE,
            ),
            content,
        ),
    )


class _Artifacts:
    def __init__(self, *, fail_finalize: bool = False) -> None:
        self.normalized_bytes = normalized_parquet_bytes(POINTS)
        self.normalized = _artifact(
            artifact_id=NORMALIZED_ARTIFACT,
            payload=self.normalized_bytes,
            schema_ref=REFERENCE_TENSILE_PARQUET_SCHEMA,
            role="dataset.normalized_curve",
        )
        self.processed_bytes: bytes | None = None
        self.fail_finalize = fail_finalize

    async def read_verified_bytes(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        artifact_id: UUID,
        *,
        maximum_bytes: int,
    ) -> tuple[ArtifactRecord, bytes]:
        assert context is CONTEXT
        assert decision is EXECUTE
        assert artifact_id == NORMALIZED_ARTIFACT
        assert maximum_bytes >= len(self.normalized_bytes)
        return self.normalized, self.normalized_bytes

    async def finalize_derived_bytes(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        *,
        classification: DataClassification,
        artifact_role: str,
        schema_ref: str,
        media_type: str,
        value: bytes,
        idempotency_key: str,
    ) -> ArtifactRecord:
        assert context is CONTEXT
        assert decision is EXECUTE
        assert classification is DataClassification.INTERNAL
        assert artifact_role == "dataset.processed_reference_tensile_curve"
        assert schema_ref == REFERENCE_TENSILE_PROCESSED_PARQUET_SCHEMA
        assert media_type == "application/vnd.apache.parquet"
        assert idempotency_key == f"processing:{PROCESSING_RUN}:reference-tensile-crop"
        if self.fail_finalize:
            raise RuntimeError("object storage unavailable")
        self.processed_bytes = value
        return _artifact(
            artifact_id=PROCESSED_ARTIFACT,
            payload=value,
            schema_ref=schema_ref,
            role=artifact_role,
        )


class _Datasets:
    def __init__(self, artifacts: _Artifacts) -> None:
        self.source = _normalized_snapshot()
        self.selection = _selection()
        self.artifacts = artifacts
        self.registered: RegisterProcessedReferenceTensileDataset | None = None

    def get_reference_dataset_selection_revision_for_processing(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        selection_id: UUID,
        selection_revision_id: UUID,
    ) -> DatasetSelectionRevisionSnapshot:
        assert context is CONTEXT
        assert decision is EXECUTE
        assert (selection_id, selection_revision_id) == (SELECTION, SELECTION_REVISION)
        return self.selection

    def get_dataset_revision_for_processing(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        dataset_revision_id: UUID,
    ) -> DatasetRevisionSnapshot:
        assert context is CONTEXT
        assert decision is EXECUTE
        assert dataset_revision_id == NORMALIZED_DATASET_REVISION
        return self.source

    def register_processed_reference_tensile_dataset(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: RegisterProcessedReferenceTensileDataset,
    ) -> DatasetSnapshot:
        assert context is CONTEXT
        assert decision is EXECUTE
        assert command.source_dataset_revision_id == NORMALIZED_DATASET_REVISION
        assert command.processing_run_id == PROCESSING_RUN
        assert command.artifact.artifact.id == PROCESSED_ARTIFACT
        assert command.artifact.artifact.schema_ref == REFERENCE_TENSILE_PROCESSED_PARQUET_SCHEMA
        self.registered = command
        output_content = DatasetContent(
            test_run_id=TEST_RUN,
            test_run_revision_id=TEST_RUN_REVISION,
            raw_asset_id=RAW_ASSET,
            raw_artifact_id=RAW_ARTIFACT,
            data_artifact_id=PROCESSED_ARTIFACT,
            data_sha256=command.artifact.artifact.sha256,
            representation=DatasetRepresentation.PROCESSED,
            source_dataset_revision_id=NORMALIZED_DATASET_REVISION,
            point_count=command.point_count,
            mapping=MAPPING,
            processing_run_id=PROCESSING_RUN,
        )
        return DatasetSnapshot(
            id=PROCESSED_DATASET,
            test_run_id=TEST_RUN,
            current=DatasetRevisionSnapshotValue(
                _record(
                    revision_id=PROCESSED_DATASET_REVISION,
                    aggregate_id=PROCESSED_DATASET,
                    aggregate_type=DATASET_AGGREGATE_TYPE,
                ),
                output_content,
            ),
        )


class _ProcessingRepository:
    def __init__(self, *, fail_succeed: bool = False) -> None:
        self.recipe = _recipe()
        self.runs: dict[UUID, ProcessingRun] = {}
        self.failed: list[ProcessingRun] = []
        self.fail_succeed = fail_succeed

    def get_recipe(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        recipe_id: UUID,
    ) -> ProcessingRecipeSnapshot:
        assert context is CONTEXT
        assert decision is EXECUTE
        assert recipe_id == RECIPE
        return self.recipe

    def get_recipe_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        recipe_id: UUID,
        recipe_revision_id: UUID,
    ) -> ProcessingRevisionSnapshot[ReferenceTensileCropRecipeContent]:
        assert context is CONTEXT
        assert decision is EXECUTE
        assert (recipe_id, recipe_revision_id) == (RECIPE, RECIPE_REVISION)
        return self.recipe.current

    def create_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run: ProcessingRun,
    ) -> ProcessingRun:
        assert context is CONTEXT
        assert decision is EXECUTE
        self.runs[run.id] = run
        return run

    def succeed_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
        artifact: ArtifactRecord,
        output_dataset_id: UUID,
        output_dataset_revision_id: UUID,
        output_point_count: int,
        removed_point_count: int,
    ) -> ProcessingRun:
        assert context is CONTEXT
        assert decision is EXECUTE
        if self.fail_succeed:
            raise RuntimeError("terminal projection unavailable")
        succeeded = replace(
            self.runs[run_id],
            status=ProcessingRunStatus.SUCCEEDED,
            output_point_count=output_point_count,
            removed_point_count=removed_point_count,
            result_artifact_id=artifact.artifact.id,
            result_sha256=artifact.artifact.sha256,
            output_dataset_id=output_dataset_id,
            output_dataset_revision_id=output_dataset_revision_id,
            ended_at=NOW,
        )
        self.runs[run_id] = succeeded
        return succeeded

    def fail_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
        artifact: ArtifactRecord | None,
        failure_code: str,
    ) -> ProcessingRun:
        failed = replace(
            self.runs[run_id],
            status=ProcessingRunStatus.FAILED,
            result_artifact_id=artifact.artifact.id if artifact is not None else None,
            result_sha256=artifact.artifact.sha256 if artifact is not None else None,
            failure_code=failure_code,
            ended_at=NOW,
        )
        self.runs[run_id] = failed
        self.failed.append(failed)
        return failed


def _service(
    *, fail_finalize: bool = False, fail_succeed: bool = False
) -> tuple[ProcessingService, _ProcessingRepository, _Datasets, _Artifacts]:
    artifacts = _Artifacts(fail_finalize=fail_finalize)
    datasets = _Datasets(artifacts)
    repository = _ProcessingRepository(fail_succeed=fail_succeed)
    return (
        ProcessingService(
            repository=cast(ProcessingRepository, repository),
            datasets=cast(DatasetService, datasets),
            artifacts=cast(ArtifactService, artifacts),
            id_factory=lambda: PROCESSING_RUN,
        ),
        repository,
        datasets,
        artifacts,
    )


def _command() -> ExecuteReferenceTensileCrop:
    return ExecuteReferenceTensileCrop(
        selection_id=SELECTION,
        selection_revision_id=SELECTION_REVISION,
        recipe_id=RECIPE,
        recipe_revision_id=RECIPE_REVISION,
        change_reason="Crop normalized curve for the elastic calibration window",
    )


def test_reference_crop_selects_only_observed_inclusive_points() -> None:
    outcome = crop_reference_tensile_points(
        POINTS,
        ReferenceTensileCropRecipeContent("Observed crop", 0.01, 0.02),
    )

    assert outcome.points == POINTS[1:3]
    assert outcome.input_point_count == 4
    assert outcome.removed_point_count == 2
    with pytest.raises(ValueError, match="at least two"):
        crop_reference_tensile_points(
            POINTS,
            ReferenceTensileCropRecipeContent("Too narrow", 0.015, 0.019),
        )


def test_processing_run_creates_separate_processed_dataset_and_preserves_normalized_input() -> None:
    service, repository, datasets, artifacts = _service()

    result = asyncio.run(service.execute_reference_tensile_crop(CONTEXT, EXECUTE, _command()))

    assert result.status is ProcessingRunStatus.SUCCEEDED
    assert result.input_dataset_id == DATASET
    assert result.input_dataset_revision_id == NORMALIZED_DATASET_REVISION
    assert result.output_dataset_id == PROCESSED_DATASET
    assert result.output_dataset_revision_id == PROCESSED_DATASET_REVISION
    assert result.output_point_count == 3
    assert result.removed_point_count == 1
    assert datasets.registered is not None
    assert datasets.source.dataset_id == DATASET
    assert datasets.source.revision.record.revision_id == NORMALIZED_DATASET_REVISION
    assert datasets.source.revision.content.representation is DatasetRepresentation.NORMALIZED
    assert datasets.source.revision.content.processing_run_id is None
    assert artifacts.processed_bytes is not None
    assert normalized_points_from_parquet(artifacts.processed_bytes) == POINTS[1:]
    assert repository.runs[PROCESSING_RUN].status is ProcessingRunStatus.SUCCEEDED


def test_processing_run_records_terminal_failure_without_mutating_input() -> None:
    service, repository, datasets, _ = _service(fail_finalize=True)

    with pytest.raises(RuntimeError, match="object storage unavailable"):
        asyncio.run(service.execute_reference_tensile_crop(CONTEXT, EXECUTE, _command()))

    assert repository.failed[0].status is ProcessingRunStatus.FAILED
    assert repository.failed[0].failure_code == "processing_command_failed"
    assert datasets.registered is None
    assert datasets.source.revision.record.revision_id == NORMALIZED_DATASET_REVISION
    assert datasets.source.revision.content.representation is DatasetRepresentation.NORMALIZED


def test_processing_run_never_marks_a_committed_output_as_failed() -> None:
    service, repository, datasets, _ = _service(fail_succeed=True)

    with pytest.raises(ProcessingConflict, match="requires reconciliation"):
        asyncio.run(service.execute_reference_tensile_crop(CONTEXT, EXECUTE, _command()))

    assert datasets.registered is not None
    assert repository.failed == []
    assert repository.runs[PROCESSING_RUN].status is ProcessingRunStatus.EXECUTING


def test_recipe_revision_cannot_change_its_stable_identity_label() -> None:
    service, _, _, _ = _service()

    with pytest.raises(ProcessingConflict, match="stable identity"):
        service.revise_reference_tensile_crop_recipe(
            CONTEXT,
            EXECUTE,
            RECIPE,
            ReviseReferenceTensileCropRecipe(
                expected_current_revision_id=RECIPE_REVISION,
                content=ReferenceTensileCropRecipeContent("Different label", 0.01, 0.03),
                change_reason="Attempt to rename immutable recipe identity",
            ),
        )

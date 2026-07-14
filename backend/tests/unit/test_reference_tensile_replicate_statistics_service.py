from __future__ import annotations

import asyncio
import hashlib
from dataclasses import replace
from datetime import UTC, datetime
from typing import cast
from uuid import UUID, uuid4

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
    DatasetService,
    TensileReplicateSelectionRevisionSnapshot,
)
from cmp.modules.datasets.application.service import (
    RevisionSnapshot as DatasetRevisionSnapshotValue,
)
from cmp.modules.datasets.domain.reference_tensile import (
    REFERENCE_TENSILE_PROCESSED_PARQUET_SCHEMA,
    CurvePoint,
    DatasetContent,
    DatasetRepresentation,
    ReferenceTensileMapping,
    normalized_parquet_bytes,
)
from cmp.modules.datasets.domain.selection import (
    ReferenceTensileReplicateSelectionContent,
    ReferenceTensileReplicateSelectionMember,
)
from cmp.modules.identity_access.application.authorization import database_permissions_for
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
    Permission,
    Role,
)
from cmp.modules.identity_access.domain.security import Principal, PrincipalType, SecurityContext
from cmp.modules.statistics.application.replicate_service import (
    REPLICATE_STATISTICAL_PLAN_AGGREGATE_TYPE,
    REPLICATE_STATISTICAL_RESULT_AGGREGATE_TYPE,
    ExecuteReferenceTensileReplicateStatistics,
    ReplicateRevisionSnapshot,
    ReplicateStatisticalResultSnapshot,
    ReplicateStatisticalRun,
    ReplicateStatisticsRepository,
    ReplicateStatisticsService,
)
from cmp.modules.statistics.domain.reference_tensile_pair import QcObservation, StatisticalRunStatus
from cmp.modules.statistics.domain.reference_tensile_replicates import (
    REFERENCE_TENSILE_REPLICATE_CURVE_SCHEMA,
    ReferenceTensileReplicatePlanContent,
    ReferenceTensileReplicateResultContent,
    reference_tensile_replicate_curve_from_parquet,
)
from cmp.shared.domain.revisions import RevisionRecord, TenantScope
from pytest import MonkeyPatch

NOW = datetime(2026, 7, 30, 12, 0, tzinfo=UTC)
ORG = UUID(int=1)
PROJECT = UUID(int=2)
ACTOR = UUID(int=3)
PLAN = UUID(int=10)
PLAN_REVISION = UUID(int=11)
SELECTION = UUID(int=12)
SELECTION_REVISION = UUID(int=13)
RUN = UUID(int=14)
RESULT = UUID(int=15)
RESULT_REVISION = UUID(int=16)
CURVE_ARTIFACT = UUID(int=17)
TRACE = "00-00000000000000000000000000000033-0000000000000033-01"
MAPPING = ReferenceTensileMapping("strain", "stress", "1", "Pa")


def _context() -> SecurityContext:
    return SecurityContext(
        principal=Principal(ACTOR, PrincipalType.USER, "Statistical Analyst", True),
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
    permission=Permission.STATISTICS_EXECUTE,
    roles=(Role.STATISTICAL_ANALYST,),
    database_permissions=database_permissions_for(Permission.STATISTICS_EXECUTE),
    max_classification=DataClassification.INTERNAL,
    allow_export_controlled=False,
    request_id=CONTEXT.request_id,
    trace_id=TRACE,
    decided_at=NOW,
)


def _record(revision_id: UUID, aggregate_id: UUID, aggregate_type: str) -> RevisionRecord:
    return RevisionRecord(
        revision_id=revision_id,
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        scope=TenantScope(ORG, PROJECT, DataClassification.INTERNAL.value),
        revision_no=1,
        based_on_revision_id=None,
        schema_id=f"urn:cmp:test:{aggregate_type}:1.0.0",
        schema_version="1.0.0",
        content_hash="a" * 64,
        created_at=NOW,
        created_by=ACTOR,
        change_reason="replicate Statistics service test",
        request_id=CONTEXT.request_id,
        trace_id=TRACE,
    )


def _artifact(artifact_id: UUID, value: bytes, schema_ref: str, role: str) -> ArtifactRecord:
    digest = hashlib.sha256(value).hexdigest()
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
            size_bytes=len(value),
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


CURVES = tuple(
    (
        CurvePoint(0.0, 0.0),
        CurvePoint(0.01, peak - 20_000_000.0),
        CurvePoint(0.02, peak),
    )
    for peak in (500_000_000.0, 520_000_000.0, 540_000_000.0)
)


class _Datasets:
    def __init__(self, curves: tuple[tuple[CurvePoint, ...], ...]) -> None:
        self.values: dict[UUID, DatasetRevisionSnapshot] = {}
        members = []
        for ordinal, points in enumerate(curves):
            dataset_id = UUID(int=100 + ordinal)
            revision_id = UUID(int=200 + ordinal)
            run_id = UUID(int=300 + ordinal)
            run_revision_id = UUID(int=400 + ordinal)
            artifact_id = UUID(int=500 + ordinal)
            payload = normalized_parquet_bytes(points)
            self.values[revision_id] = DatasetRevisionSnapshot(
                dataset_id=dataset_id,
                revision=DatasetRevisionSnapshotValue(
                    _record(revision_id, dataset_id, DATASET_AGGREGATE_TYPE),
                    DatasetContent(
                        test_run_id=run_id,
                        test_run_revision_id=run_revision_id,
                        raw_asset_id=UUID(int=600 + ordinal),
                        raw_artifact_id=UUID(int=700 + ordinal),
                        data_artifact_id=artifact_id,
                        data_sha256=hashlib.sha256(payload).hexdigest(),
                        representation=DatasetRepresentation.PROCESSED,
                        source_dataset_revision_id=UUID(int=800 + ordinal),
                        point_count=len(points),
                        mapping=MAPPING,
                        processing_run_id=UUID(int=900 + ordinal),
                    ),
                ),
            )
            members.append(
                ReferenceTensileReplicateSelectionMember(
                    ordinal=ordinal,
                    dataset_id=dataset_id,
                    dataset_revision_id=revision_id,
                    test_run_id=run_id,
                    test_run_revision_id=run_revision_id,
                )
            )
        content = ReferenceTensileReplicateSelectionContent(
            "Aligned DP780 replicates", tuple(members)
        )
        self.selection = TensileReplicateSelectionRevisionSnapshot(
            selection_id=SELECTION,
            selection_label=content.selection_label,
            revision=DatasetRevisionSnapshotValue(
                _record(SELECTION_REVISION, SELECTION, DATASET_SELECTION_AGGREGATE_TYPE),
                content,
            ),
        )

    def get_reference_tensile_replicate_selection_revision_for_statistics(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        selection_id: UUID,
        selection_revision_id: UUID,
    ) -> TensileReplicateSelectionRevisionSnapshot:
        assert context is CONTEXT and decision is EXECUTE
        assert (selection_id, selection_revision_id) == (SELECTION, SELECTION_REVISION)
        return self.selection

    def get_dataset_revision_for_statistics(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        dataset_revision_id: UUID,
    ) -> DatasetRevisionSnapshot:
        assert context is CONTEXT and decision is EXECUTE
        return self.values[dataset_revision_id]


class _Artifacts:
    def __init__(
        self,
        datasets: _Datasets,
        curves: tuple[tuple[CurvePoint, ...], ...],
    ) -> None:
        self.inputs = {
            snapshot.revision.content.data_artifact_id: (
                _artifact(
                    snapshot.revision.content.data_artifact_id,
                    normalized_parquet_bytes(points),
                    REFERENCE_TENSILE_PROCESSED_PARQUET_SCHEMA,
                    "dataset.processed_curve",
                ),
                normalized_parquet_bytes(points),
            )
            for snapshot, points in zip(datasets.values.values(), curves, strict=True)
        }
        self.curve_bytes: bytes | None = None

    async def read_verified_bytes(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        artifact_id: UUID,
        *,
        maximum_bytes: int,
    ) -> tuple[ArtifactRecord, bytes]:
        assert context is CONTEXT and decision is EXECUTE and maximum_bytes > 0
        return self.inputs[artifact_id]

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
        assert context is CONTEXT and decision is EXECUTE
        assert classification is DataClassification.INTERNAL
        assert artifact_role == "statistics.reference_tensile_replicate_curve"
        assert schema_ref == REFERENCE_TENSILE_REPLICATE_CURVE_SCHEMA
        assert media_type == "application/vnd.apache.parquet"
        assert idempotency_key == f"statistics:{RUN}:reference-tensile-replicates"
        self.curve_bytes = value
        return _artifact(CURVE_ARTIFACT, value, schema_ref, artifact_role)


class _Repository:
    def __init__(self) -> None:
        content = ReferenceTensileReplicatePlanContent(
            "DP780 replicate statistics", SELECTION, SELECTION_REVISION
        )
        self.plan = ReplicateRevisionSnapshot(
            _record(PLAN_REVISION, PLAN, REPLICATE_STATISTICAL_PLAN_AGGREGATE_TYPE),
            content,
        )
        self.runs: dict[UUID, ReplicateStatisticalRun] = {}
        self.result: ReplicateStatisticalResultSnapshot | None = None

    def get_plan_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        plan_id: UUID,
        plan_revision_id: UUID,
    ) -> ReplicateRevisionSnapshot[ReferenceTensileReplicatePlanContent]:
        assert context is CONTEXT and decision is EXECUTE
        assert (plan_id, plan_revision_id) == (PLAN, PLAN_REVISION)
        return self.plan

    def create_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run: ReplicateStatisticalRun,
    ) -> ReplicateStatisticalRun:
        assert context is CONTEXT and decision is EXECUTE
        self.runs[run.id] = run
        return run

    def get_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
    ) -> ReplicateStatisticalRun:
        assert context is CONTEXT and decision is EXECUTE
        return self.runs[run_id]

    def succeed_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
        result: ReplicateStatisticalResultSnapshot,
        qc_observations: tuple[QcObservation, ...],
    ) -> ReplicateStatisticalRun:
        assert context is CONTEXT and decision is EXECUTE
        succeeded = replace(
            self.runs[run_id],
            status=StatisticalRunStatus.SUCCEEDED,
            result_id=result.id,
            result_revision_id=result.current.record.revision_id,
            curve_artifact_id=result.current.content.curve_artifact_id,
            curve_sha256=result.current.content.curve_sha256,
            curve_point_count=result.current.content.curve_point_count,
            ended_at=NOW,
            qc_observations=qc_observations,
        )
        self.runs[run_id] = succeeded
        return succeeded

    def fail_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
        failure_code: str,
        qc_observations: tuple[QcObservation, ...],
    ) -> ReplicateStatisticalRun:
        assert context is CONTEXT and decision is EXECUTE
        failed = replace(
            self.runs[run_id],
            status=StatisticalRunStatus.FAILED,
            failure_code=failure_code,
            ended_at=NOW,
            qc_observations=qc_observations,
        )
        self.runs[run_id] = failed
        return failed


def _service(
    curves: tuple[tuple[CurvePoint, ...], ...] = CURVES,
) -> tuple[ReplicateStatisticsService, _Repository, _Datasets, _Artifacts]:
    datasets = _Datasets(curves)
    artifacts = _Artifacts(datasets, curves)
    repository = _Repository()
    service = ReplicateStatisticsService(
        repository=cast(ReplicateStatisticsRepository, repository),
        datasets=cast(DatasetService, datasets),
        artifacts=cast(ArtifactService, artifacts),
        id_factory=lambda: RUN,
    )
    return service, repository, datasets, artifacts


def _command() -> ExecuteReferenceTensileReplicateStatistics:
    return ExecuteReferenceTensileReplicateStatistics(
        plan_id=PLAN,
        plan_revision_id=PLAN_REVISION,
        change_reason="Calculate aligned replicate statistics",
    )


def test_replicate_statistics_service_commits_result_without_mutating_processed_inputs(
    monkeypatch: MonkeyPatch,
) -> None:
    service, repository, datasets, artifacts = _service()

    def register_result(
        context: SecurityContext,
        decision: AuthorizationDecision,
        content: ReferenceTensileReplicateResultContent,
        reason: str,
    ) -> ReplicateStatisticalResultSnapshot:
        assert context is CONTEXT and decision is EXECUTE
        assert reason == "Calculate aligned replicate statistics"
        result = ReplicateStatisticalResultSnapshot(
            RESULT,
            ReplicateRevisionSnapshot(
                _record(
                    RESULT_REVISION,
                    RESULT,
                    REPLICATE_STATISTICAL_RESULT_AGGREGATE_TYPE,
                ),
                content,
            ),
        )
        repository.result = result
        return result

    monkeypatch.setattr(service, "_register_result", register_result)
    outcome = asyncio.run(service.execute(CONTEXT, EXECUTE, _command()))

    assert outcome.status is StatisticalRunStatus.SUCCEEDED
    assert outcome.sample_count == 3
    assert outcome.result_id == RESULT
    assert all(
        item.outcome is not None and item.outcome.value == "passed"
        for item in outcome.qc_observations
    )
    assert repository.result is not None
    assert repository.result.current.content.peak_engineering_stress_pa.mean == 520_000_000.0
    assert artifacts.curve_bytes is not None
    curve = reference_tensile_replicate_curve_from_parquet(artifacts.curve_bytes)
    assert curve[-1].stress.mean == 520_000_000.0
    assert all(
        value.revision.content.representation is DatasetRepresentation.PROCESSED
        for value in datasets.values.values()
    )


def test_replicate_statistics_service_records_failed_exact_grid_qc() -> None:
    mismatched = (
        CURVES[0],
        (CURVES[1][0], CurvePoint(0.011, CURVES[1][1].engineering_stress), CURVES[1][2]),
        CURVES[2],
    )
    service, repository, _, artifacts = _service(mismatched)

    outcome = asyncio.run(service.execute(CONTEXT, EXECUTE, _command()))

    assert outcome.status is StatisticalRunStatus.FAILED
    assert outcome.failure_code == "input_qc_failed"
    assert repository.result is None
    assert artifacts.curve_bytes is None
    assert any(item.outcome.value == "failed" for item in outcome.qc_observations)

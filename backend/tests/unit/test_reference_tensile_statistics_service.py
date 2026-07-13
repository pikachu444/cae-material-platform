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
    DatasetSelectionRevisionSnapshot,
    DatasetService,
)
from cmp.modules.datasets.application.service import (
    RevisionSnapshot as DatasetRevisionSnapshotValue,
)
from cmp.modules.datasets.domain.reference_tensile import (
    REFERENCE_TENSILE_PARQUET_SCHEMA,
    CurvePoint,
    DatasetContent,
    DatasetRepresentation,
    ReferenceTensileMapping,
    normalized_parquet_bytes,
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
from cmp.modules.statistics.application.service import (
    STATISTICAL_PLAN_AGGREGATE_TYPE,
    STATISTICAL_RESULT_AGGREGATE_TYPE,
    ExecuteReferenceTensilePairStatistics,
    RevisionSnapshot,
    StatisticalResultSnapshot,
    StatisticalRun,
    StatisticsRepository,
    StatisticsService,
)
from cmp.modules.statistics.domain.reference_tensile_pair import (
    REFERENCE_TENSILE_PAIR_CURVE_SCHEMA,
    QcObservation,
    ReferenceTensilePairPlanContent,
    ReferenceTensilePairResultContent,
    StatisticalRunStatus,
    reference_tensile_pair_curve_from_parquet,
)
from cmp.shared.domain.revisions import RevisionRecord, TenantScope
from pytest import MonkeyPatch

NOW = datetime(2026, 7, 16, 12, 0, tzinfo=UTC)
ORG = UUID("f8000000-0000-4000-8000-000000000001")
PROJECT = UUID("f8000000-0000-4000-8000-000000000002")
ACTOR = UUID("f8000000-0000-4000-8000-000000000003")
FIRST_RUN = UUID("f8000000-0000-4000-8000-000000000004")
SECOND_RUN = UUID("f8000000-0000-4000-8000-000000000005")
FIRST_DATASET = UUID("f8000000-0000-4000-8000-000000000006")
SECOND_DATASET = UUID("f8000000-0000-4000-8000-000000000007")
FIRST_DATASET_REVISION = UUID("f8000000-0000-4000-8000-000000000008")
SECOND_DATASET_REVISION = UUID("f8000000-0000-4000-8000-000000000009")
FIRST_ARTIFACT = UUID("f8000000-0000-4000-8000-00000000000a")
SECOND_ARTIFACT = UUID("f8000000-0000-4000-8000-00000000000b")
FIRST_SELECTION = UUID("f8000000-0000-4000-8000-00000000000c")
SECOND_SELECTION = UUID("f8000000-0000-4000-8000-00000000000d")
FIRST_SELECTION_REVISION = UUID("f8000000-0000-4000-8000-00000000000e")
SECOND_SELECTION_REVISION = UUID("f8000000-0000-4000-8000-00000000000f")
PLAN = UUID("f8000000-0000-4000-8000-000000000010")
PLAN_REVISION = UUID("f8000000-0000-4000-8000-000000000011")
STATISTICAL_RUN = UUID("f8000000-0000-4000-8000-000000000012")
RESULT = UUID("f8000000-0000-4000-8000-000000000013")
RESULT_REVISION = UUID("f8000000-0000-4000-8000-000000000014")
CURVE_ARTIFACT = UUID("f8000000-0000-4000-8000-000000000015")
TRACE = "00-000000000000000000000000000000f8-00000000000000f8-01"
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


def _record(*, revision_id: UUID, aggregate_id: UUID, aggregate_type: str) -> RevisionRecord:
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
        change_reason="reference Statistics service test",
        request_id=CONTEXT.request_id,
        trace_id=TRACE,
    )


def _artifact(artifact_id: UUID, payload: bytes, schema_ref: str, role: str) -> ArtifactRecord:
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


FIRST_POINTS = (
    CurvePoint(0.0, 0.0),
    CurvePoint(0.01, 100_000_000.0),
    CurvePoint(0.02, 120_000_000.0),
)
SECOND_POINTS = (
    CurvePoint(0.0, 0.0),
    CurvePoint(0.01, 110_000_000.0),
    CurvePoint(0.02, 140_000_000.0),
)


def _dataset_snapshot(
    *,
    dataset_id: UUID,
    revision_id: UUID,
    artifact_id: UUID,
    test_run_id: UUID,
    points: tuple[CurvePoint, ...],
) -> DatasetRevisionSnapshot:
    return DatasetRevisionSnapshot(
        dataset_id=dataset_id,
        revision=DatasetRevisionSnapshotValue(
            _record(
                revision_id=revision_id,
                aggregate_id=dataset_id,
                aggregate_type=DATASET_AGGREGATE_TYPE,
            ),
            DatasetContent(
                test_run_id=test_run_id,
                test_run_revision_id=uuid4(),
                raw_asset_id=uuid4(),
                raw_artifact_id=uuid4(),
                data_artifact_id=artifact_id,
                data_sha256=hashlib.sha256(normalized_parquet_bytes(points)).hexdigest(),
                representation=DatasetRepresentation.NORMALIZED,
                source_dataset_revision_id=uuid4(),
                point_count=len(points),
                mapping=MAPPING,
            ),
        ),
    )


def _selection(
    *, selection_id: UUID, revision_id: UUID, dataset: DatasetRevisionSnapshot
) -> DatasetSelectionRevisionSnapshot:
    content = ReferenceDatasetSelectionContent(
        selection_label=f"Selection {selection_id}",
        dataset_id=dataset.dataset_id,
        dataset_revision_id=dataset.revision.record.revision_id,
    )
    return DatasetSelectionRevisionSnapshot(
        selection_id=selection_id,
        selection_label=content.selection_label,
        revision=DatasetRevisionSnapshotValue(
            _record(
                revision_id=revision_id,
                aggregate_id=selection_id,
                aggregate_type=DATASET_SELECTION_AGGREGATE_TYPE,
            ),
            content,
        ),
    )


def _plan() -> RevisionSnapshot[ReferenceTensilePairPlanContent]:
    content = ReferenceTensilePairPlanContent(
        plan_label="Reference pair",
        first_selection_id=FIRST_SELECTION,
        first_selection_revision_id=FIRST_SELECTION_REVISION,
        second_selection_id=SECOND_SELECTION,
        second_selection_revision_id=SECOND_SELECTION_REVISION,
    )
    return RevisionSnapshot(
        _record(
            revision_id=PLAN_REVISION,
            aggregate_id=PLAN,
            aggregate_type=STATISTICAL_PLAN_AGGREGATE_TYPE,
        ),
        content,
    )


class _Artifacts:
    def __init__(self, second_points: tuple[CurvePoint, ...]) -> None:
        self.first_bytes = normalized_parquet_bytes(FIRST_POINTS)
        self.second_bytes = normalized_parquet_bytes(second_points)
        self.first = _artifact(
            FIRST_ARTIFACT,
            self.first_bytes,
            REFERENCE_TENSILE_PARQUET_SCHEMA,
            "dataset.normalized_curve",
        )
        self.second = _artifact(
            SECOND_ARTIFACT,
            self.second_bytes,
            REFERENCE_TENSILE_PARQUET_SCHEMA,
            "dataset.normalized_curve",
        )
        self.curve_bytes: bytes | None = None

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
        assert maximum_bytes >= len(self.first_bytes)
        if artifact_id == FIRST_ARTIFACT:
            return self.first, self.first_bytes
        assert artifact_id == SECOND_ARTIFACT
        return self.second, self.second_bytes

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
        assert artifact_role == "statistics.reference_tensile_pair_curve"
        assert schema_ref == REFERENCE_TENSILE_PAIR_CURVE_SCHEMA
        assert media_type == "application/vnd.apache.parquet"
        assert idempotency_key == f"statistics:{STATISTICAL_RUN}:reference-tensile-pair"
        self.curve_bytes = value
        return _artifact(CURVE_ARTIFACT, value, schema_ref, artifact_role)


class _Datasets:
    def __init__(self, second_points: tuple[CurvePoint, ...]) -> None:
        self.first = _dataset_snapshot(
            dataset_id=FIRST_DATASET,
            revision_id=FIRST_DATASET_REVISION,
            artifact_id=FIRST_ARTIFACT,
            test_run_id=FIRST_RUN,
            points=FIRST_POINTS,
        )
        self.second = _dataset_snapshot(
            dataset_id=SECOND_DATASET,
            revision_id=SECOND_DATASET_REVISION,
            artifact_id=SECOND_ARTIFACT,
            test_run_id=SECOND_RUN,
            points=second_points,
        )
        self.first_selection = _selection(
            selection_id=FIRST_SELECTION,
            revision_id=FIRST_SELECTION_REVISION,
            dataset=self.first,
        )
        self.second_selection = _selection(
            selection_id=SECOND_SELECTION,
            revision_id=SECOND_SELECTION_REVISION,
            dataset=self.second,
        )

    def get_reference_dataset_selection_revision_for_statistics(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        selection_id: UUID,
        selection_revision_id: UUID,
    ) -> DatasetSelectionRevisionSnapshot:
        assert context is CONTEXT
        assert decision is EXECUTE
        values = {
            (FIRST_SELECTION, FIRST_SELECTION_REVISION): self.first_selection,
            (SECOND_SELECTION, SECOND_SELECTION_REVISION): self.second_selection,
        }
        return values[(selection_id, selection_revision_id)]

    def get_dataset_revision_for_statistics(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        dataset_revision_id: UUID,
    ) -> DatasetRevisionSnapshot:
        assert context is CONTEXT
        assert decision is EXECUTE
        values = {
            FIRST_DATASET_REVISION: self.first,
            SECOND_DATASET_REVISION: self.second,
        }
        return values[dataset_revision_id]


class _Repository:
    def __init__(self) -> None:
        self.plan = _plan()
        self.runs: dict[UUID, StatisticalRun] = {}
        self.failed: list[StatisticalRun] = []
        self.result: StatisticalResultSnapshot | None = None

    def get_plan_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        plan_id: UUID,
        plan_revision_id: UUID,
    ) -> RevisionSnapshot[ReferenceTensilePairPlanContent]:
        assert context is CONTEXT
        assert decision is EXECUTE
        assert (plan_id, plan_revision_id) == (PLAN, PLAN_REVISION)
        return self.plan

    def create_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run: StatisticalRun,
    ) -> StatisticalRun:
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
        result: StatisticalResultSnapshot,
        qc_observations: tuple[QcObservation, ...],
    ) -> StatisticalRun:
        assert context is CONTEXT
        assert decision is EXECUTE
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
    ) -> StatisticalRun:
        assert context is CONTEXT
        assert decision is EXECUTE
        failed = replace(
            self.runs[run_id],
            status=StatisticalRunStatus.FAILED,
            failure_code=failure_code,
            ended_at=NOW,
            qc_observations=qc_observations,
        )
        self.runs[run_id] = failed
        self.failed.append(failed)
        return failed


def _service(
    second_points: tuple[CurvePoint, ...] = SECOND_POINTS,
) -> tuple[StatisticsService, _Repository, _Datasets, _Artifacts]:
    artifacts = _Artifacts(second_points)
    datasets = _Datasets(second_points)
    repository = _Repository()
    return (
        StatisticsService(
            repository=cast(StatisticsRepository, repository),
            datasets=cast(DatasetService, datasets),
            artifacts=cast(ArtifactService, artifacts),
            id_factory=lambda: STATISTICAL_RUN,
        ),
        repository,
        datasets,
        artifacts,
    )


def _command() -> ExecuteReferenceTensilePairStatistics:
    return ExecuteReferenceTensilePairStatistics(
        plan_id=PLAN,
        plan_revision_id=PLAN_REVISION,
        change_reason="Calculate reference pair statistics",
    )


def test_statistics_run_creates_separate_result_and_preserves_both_normalized_inputs(
    monkeypatch: MonkeyPatch,
) -> None:
    service, repository, datasets, artifacts = _service()

    def register_result(
        context: SecurityContext,
        decision: AuthorizationDecision,
        content: ReferenceTensilePairResultContent,
        reason: str,
    ) -> StatisticalResultSnapshot:
        assert context is CONTEXT
        assert decision is EXECUTE
        assert reason == "Calculate reference pair statistics"
        result = StatisticalResultSnapshot(
            RESULT,
            RevisionSnapshot(
                _record(
                    revision_id=RESULT_REVISION,
                    aggregate_id=RESULT,
                    aggregate_type=STATISTICAL_RESULT_AGGREGATE_TYPE,
                ),
                content,
            ),
        )
        repository.result = result
        return result

    monkeypatch.setattr(service, "_register_result", register_result)
    outcome = asyncio.run(
        service.execute_reference_tensile_pair_statistics(CONTEXT, EXECUTE, _command())
    )

    assert outcome.status is StatisticalRunStatus.SUCCEEDED
    assert outcome.result_id == RESULT
    assert outcome.curve_artifact_id == CURVE_ARTIFACT
    assert all(item.outcome.value == "passed" for item in outcome.qc_observations)
    assert repository.result is not None
    assert repository.result.current.content.scalar.mean_engineering_stress_pa == 130_000_000.0
    assert artifacts.curve_bytes is not None
    curve = reference_tensile_pair_curve_from_parquet(artifacts.curve_bytes)
    assert curve[1].mean_engineering_stress_pa == 105_000_000.0
    assert datasets.first.revision.record.revision_id == FIRST_DATASET_REVISION
    assert datasets.second.revision.record.revision_id == SECOND_DATASET_REVISION
    assert datasets.first.revision.content.representation is DatasetRepresentation.NORMALIZED
    assert datasets.second.revision.content.representation is DatasetRepresentation.NORMALIZED


def test_statistics_run_records_failed_qc_without_creating_a_result_or_mutating_inputs() -> None:
    mismatched = (
        CurvePoint(0.0, 0.0),
        CurvePoint(0.0100000001, 110_000_000.0),
        CurvePoint(0.02, 140_000_000.0),
    )
    service, repository, datasets, artifacts = _service(mismatched)

    outcome = asyncio.run(
        service.execute_reference_tensile_pair_statistics(CONTEXT, EXECUTE, _command())
    )

    assert outcome.status is StatisticalRunStatus.FAILED
    assert outcome.failure_code == "input_qc_failed"
    assert any(item.outcome.value == "failed" for item in outcome.qc_observations)
    assert repository.result is None
    assert artifacts.curve_bytes is None
    assert datasets.first.revision.record.revision_id == FIRST_DATASET_REVISION
    assert datasets.second.revision.record.revision_id == SECOND_DATASET_REVISION

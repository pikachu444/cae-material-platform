from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import UTC, datetime
from typing import cast
from uuid import UUID, uuid4

import pytest
from cmp.modules.artifacts.application.content import ArtifactService
from cmp.modules.datasets.application.service import (
    DatasetService,
    DatasetSnapshot,
    ImportReferenceTensileCsv,
)
from cmp.modules.datasets.application.service import RevisionSnapshot as DatasetRevisionSnapshot
from cmp.modules.datasets.domain.reference_tensile import (
    DatasetContent,
    DatasetRepresentation,
    ReferenceTensileMapping,
)
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
    ExecuteReferenceImport,
    ImportRun,
    ProcessingRepository,
    ProcessingService,
)
from cmp.modules.processing.domain.reference_import import ImportRunStatus
from cmp.modules.processing.domain.reference_tensile_crop import ProcessingConflict
from cmp.modules.testing.application.service import (
    IMPORT_MAPPING_AGGREGATE_TYPE,
    TEST_RUN_AGGREGATE_TYPE,
    ImportMappingRevisionSnapshot,
)
from cmp.modules.testing.application.service import (
    RevisionSnapshot as RunRevisionSnapshot,
)
from cmp.modules.testing.application.service import (
    TestingService as ServicePort,
)
from cmp.modules.testing.domain.import_mapping import ReferenceImportMappingContent
from cmp.modules.testing.domain.reference_tensile import TestRunContent as RunContent
from cmp.shared.domain.revisions import RevisionRecord, TenantScope

NOW = datetime(2026, 7, 18, 11, 0, tzinfo=UTC)
ORG = UUID("f4000000-0000-4000-8000-000000000001")
PROJECT = UUID("f4000000-0000-4000-8000-000000000002")
ACTOR = UUID("f4000000-0000-4000-8000-000000000003")
TEST_RUN = UUID("f4000000-0000-4000-8000-000000000004")
TEST_RUN_REVISION = UUID("f4000000-0000-4000-8000-000000000005")
RAW_ASSET = UUID("f4000000-0000-4000-8000-000000000006")
RAW_ARTIFACT = UUID("f4000000-0000-4000-8000-000000000007")
MAPPING = UUID("f4000000-0000-4000-8000-000000000008")
MAPPING_REVISION = UUID("f4000000-0000-4000-8000-000000000009")
DATASET = UUID("f4000000-0000-4000-8000-00000000000a")
DATASET_REVISION = UUID("f4000000-0000-4000-8000-00000000000b")
IMPORT_RUN = UUID("f4000000-0000-4000-8000-00000000000c")
TRACE = "00-000000000000000000000000000000f4-00000000000000f4-01"


def _context() -> SecurityContext:
    return SecurityContext(
        principal=Principal(ACTOR, PrincipalType.USER, "Test engineer", True),
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
    roles=(Role.TEST_ENGINEER,),
    database_permissions=database_permissions_for(Permission.PROCESSING_EXECUTE),
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
        change_reason="reference import test",
        request_id=CONTEXT.request_id,
        trace_id=TRACE,
    )


class _Testing:
    def __init__(self, *, raw_artifact_id: UUID = RAW_ARTIFACT) -> None:
        self.mapping = ReferenceImportMappingContent(
            mapping_label="confirmed original CSV",
            detection_report_id=UUID("f4000000-0000-4000-8000-00000000000d"),
            raw_asset_id=RAW_ASSET,
            raw_artifact_id=raw_artifact_id,
            strain_column="strain_pct",
            stress_column="stress_mpa",
            strain_unit="%",
            stress_unit="MPa",
        )
        self.mapping_snapshot = ImportMappingRevisionSnapshot(
            mapping_id=MAPPING,
            revision=RunRevisionSnapshot(
                _record(MAPPING_REVISION, MAPPING, IMPORT_MAPPING_AGGREGATE_TYPE), self.mapping
            ),
        )
        self.test_run_snapshot = RunRevisionSnapshot(
            _record(TEST_RUN_REVISION, TEST_RUN, TEST_RUN_AGGREGATE_TYPE),
            RunContent(
                specimen_id=UUID("f4000000-0000-4000-8000-00000000000e"),
                specimen_revision_id=UUID("f4000000-0000-4000-8000-00000000000f"),
                test_method_id=UUID("f4000000-0000-4000-8000-000000000010"),
                test_method_revision_id=UUID("f4000000-0000-4000-8000-000000000011"),
                run_label="run-001",
                performed_at=NOW,
                test_temperature_k=None,
                crosshead_speed_mm_per_min=None,
            ),
        )

    def get_import_mapping_revision_for_processing(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        mapping_id: UUID,
        mapping_revision_id: UUID,
    ) -> ImportMappingRevisionSnapshot:
        assert context is CONTEXT
        assert decision is EXECUTE
        assert (mapping_id, mapping_revision_id) == (MAPPING, MAPPING_REVISION)
        return self.mapping_snapshot

    def get_test_run_revision_for_processing(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        test_run_id: UUID,
        test_run_revision_id: UUID,
    ) -> RunRevisionSnapshot[RunContent]:
        assert context is CONTEXT
        assert decision is EXECUTE
        assert (test_run_id, test_run_revision_id) == (TEST_RUN, TEST_RUN_REVISION)
        return self.test_run_snapshot


class _Datasets:
    def __init__(self, *, fail: bool = False, mismatch: bool = False) -> None:
        self.fail = fail
        self.mismatch = mismatch
        self.calls: list[ImportReferenceTensileCsv] = []

    async def import_reference_tensile_csv_for_processing(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: ImportReferenceTensileCsv,
    ) -> DatasetSnapshot:
        assert context is CONTEXT
        assert decision is EXECUTE
        self.calls.append(command)
        if self.fail:
            raise RuntimeError("synthetic Dataset owner failure")
        mapping = command.mapping
        content = DatasetContent(
            test_run_id=TEST_RUN,
            test_run_revision_id=TEST_RUN_REVISION,
            raw_asset_id=RAW_ASSET,
            raw_artifact_id=(
                UUID("f4000000-0000-4000-8000-000000000015")
                if self.mismatch
                else RAW_ARTIFACT
            ),
            data_artifact_id=UUID("f4000000-0000-4000-8000-000000000012"),
            data_sha256="b" * 64,
            representation=DatasetRepresentation.NORMALIZED,
            source_dataset_revision_id=UUID("f4000000-0000-4000-8000-000000000013"),
            point_count=3,
            mapping=ReferenceTensileMapping(
                mapping.strain_column,
                mapping.stress_column,
                mapping.strain_unit,
                mapping.stress_unit,
            ),
        )
        return DatasetSnapshot(
            id=DATASET,
            test_run_id=TEST_RUN,
            current=DatasetRevisionSnapshot(
                _record(DATASET_REVISION, DATASET, "datasets.dataset"), content
            ),
        )


class _Repository:
    def __init__(self) -> None:
        self.runs: dict[UUID, ImportRun] = {}

    def create_import_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run: ImportRun,
    ) -> ImportRun:
        assert context is CONTEXT
        assert decision is EXECUTE
        self.runs[run.id] = run
        return run

    def succeed_import_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
        output_dataset_id: UUID,
        output_dataset_revision_id: UUID,
    ) -> ImportRun:
        assert context is CONTEXT
        assert decision is EXECUTE
        succeeded = replace(
            self.runs[run_id],
            status=ImportRunStatus.SUCCEEDED,
            output_dataset_id=output_dataset_id,
            output_dataset_revision_id=output_dataset_revision_id,
            ended_at=NOW,
        )
        self.runs[run_id] = succeeded
        return succeeded

    def fail_import_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
        failure_code: str,
    ) -> ImportRun:
        failed = replace(
            self.runs[run_id],
            status=ImportRunStatus.FAILED,
            failure_code=failure_code,
            ended_at=NOW,
        )
        self.runs[run_id] = failed
        return failed


def _command(raw_artifact_id: UUID = RAW_ARTIFACT) -> ExecuteReferenceImport:
    return ExecuteReferenceImport(
        test_run_id=TEST_RUN,
        test_run_revision_id=TEST_RUN_REVISION,
        raw_asset_id=RAW_ASSET,
        raw_artifact_id=raw_artifact_id,
        import_mapping_id=MAPPING,
        import_mapping_revision_id=MAPPING_REVISION,
        change_reason="Import the explicit human-approved reference CSV mapping.",
    )


def _service(
    *,
    testing: _Testing | None = None,
    fail_dataset: bool = False,
    mismatch_dataset: bool = False,
) -> tuple[ProcessingService, _Repository, _Datasets]:
    repository = _Repository()
    datasets = _Datasets(fail=fail_dataset, mismatch=mismatch_dataset)
    return (
        ProcessingService(
            repository=cast(ProcessingRepository, repository),
            datasets=cast(DatasetService, datasets),
            testing=cast(ServicePort, testing or _Testing()),
            artifacts=cast(ArtifactService, object()),
            id_factory=lambda: IMPORT_RUN,
        ),
        repository,
        datasets,
    )


def test_reference_import_pins_mapping_revision_before_dataset_owner_writes_output() -> None:
    service, repository, datasets = _service()

    result = asyncio.run(service.execute_reference_import(CONTEXT, EXECUTE, _command()))

    assert result.status is ImportRunStatus.SUCCEEDED
    assert result.output_dataset_id == DATASET
    assert result.output_dataset_revision_id == DATASET_REVISION
    assert datasets.calls[0].mapping == ReferenceTensileMapping(
        "strain_pct", "stress_mpa", "%", "MPa"
    )
    assert repository.runs[IMPORT_RUN].mapping_sha256 == datasets.calls[0].mapping.digest


def test_reference_import_records_failed_terminal_run_without_mutating_mapping_or_source() -> None:
    service, repository, datasets = _service(fail_dataset=True)

    with pytest.raises(RuntimeError, match="Dataset owner failure"):
        asyncio.run(service.execute_reference_import(CONTEXT, EXECUTE, _command()))

    assert len(datasets.calls) == 1
    assert repository.runs[IMPORT_RUN].status is ImportRunStatus.FAILED
    assert repository.runs[IMPORT_RUN].failure_code == "reference_import_failed"
    assert repository.runs[IMPORT_RUN].output_dataset_id is None


def test_reference_import_rejects_raw_artifact_that_does_not_equal_the_mapping_snapshot() -> None:
    service, repository, datasets = _service()

    with pytest.raises(ProcessingConflict, match="must match the approved Mapping revision"):
        asyncio.run(
            service.execute_reference_import(
                CONTEXT,
                EXECUTE,
                _command(UUID("f4000000-0000-4000-8000-000000000014")),
            )
        )

    assert repository.runs == {}
    assert datasets.calls == []


def test_reference_import_leaves_the_run_reconcilable_when_dataset_output_is_mismatched() -> None:
    service, repository, datasets = _service(mismatch_dataset=True)

    with pytest.raises(ProcessingConflict, match="terminal state requires reconciliation"):
        asyncio.run(service.execute_reference_import(CONTEXT, EXECUTE, _command()))

    assert len(datasets.calls) == 1
    assert repository.runs[IMPORT_RUN].status is ImportRunStatus.EXECUTING

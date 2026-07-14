from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import cast
from uuid import UUID, uuid4

import httpx
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
from cmp.modules.processing.adapters.api.processing import install_processing_api
from cmp.modules.processing.application.service import (
    ExecuteReferenceImport,
    ImportRun,
    ProcessingService,
)
from cmp.modules.processing.domain.reference_import import ImportRunStatus
from cmp.modules.testing.adapters.api.testing import install_testing_api
from cmp.modules.testing.application.service import (
    IMPORT_MAPPING_AGGREGATE_TYPE,
    CreateReferenceImportMapping,
    DetectSyntheticCsvImport,
    ImportDetectionReportSnapshot,
    ImportMappingSnapshot,
    ReviseReferenceImportMapping,
    RevisionSnapshot,
)
from cmp.modules.testing.application.service import (
    TestingService as ServicePort,
)
from cmp.modules.testing.domain.import_mapping import (
    ReferenceImportMappingContent,
    detect_synthetic_csv_header,
)
from cmp.shared.domain.revisions import RevisionRecord, TenantScope
from fastapi import FastAPI, Request

NOW = datetime(2026, 7, 18, 12, 0, tzinfo=UTC)
ORG = UUID("f5000000-0000-4000-8000-000000000001")
PROJECT = UUID("f5000000-0000-4000-8000-000000000002")
ACTOR = UUID("f5000000-0000-4000-8000-000000000003")
RAW_ASSET = UUID("f5000000-0000-4000-8000-000000000004")
RAW_ARTIFACT = UUID("f5000000-0000-4000-8000-000000000005")
REPORT = UUID("f5000000-0000-4000-8000-000000000006")
MAPPING = UUID("f5000000-0000-4000-8000-000000000007")
MAPPING_REVISION = UUID("f5000000-0000-4000-8000-000000000008")
TEST_RUN = UUID("f5000000-0000-4000-8000-000000000009")
TEST_RUN_REVISION = UUID("f5000000-0000-4000-8000-00000000000a")
IMPORT_RUN = UUID("f5000000-0000-4000-8000-00000000000b")
DATASET = UUID("f5000000-0000-4000-8000-00000000000c")
DATASET_REVISION = UUID("f5000000-0000-4000-8000-00000000000d")
TRACE = "00-000000000000000000000000000000f5-00000000000000f5-01"


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


def _decision(permission: Permission) -> AuthorizationDecision:
    return AuthorizationDecision(
        principal_id=ACTOR,
        organization_id=ORG,
        project_id=PROJECT,
        permission=permission,
        roles=(Role.TEST_ENGINEER,),
        database_permissions=database_permissions_for(permission),
        max_classification=DataClassification.INTERNAL,
        allow_export_controlled=False,
        request_id=CONTEXT.request_id,
        trace_id=TRACE,
        decided_at=NOW,
    )


TESTING_READ = _decision(Permission.TESTING_READ)
TESTING_WRITE = _decision(Permission.TESTING_WRITE)
PROCESSING_READ = _decision(Permission.PROCESSING_READ)
PROCESSING_EXECUTE = _decision(Permission.PROCESSING_EXECUTE)


def _record(revision_id: UUID, aggregate_id: UUID) -> RevisionRecord:
    return RevisionRecord(
        revision_id=revision_id,
        aggregate_type=IMPORT_MAPPING_AGGREGATE_TYPE,
        aggregate_id=aggregate_id,
        scope=TenantScope(ORG, PROJECT, DataClassification.INTERNAL.value),
        revision_no=1,
        based_on_revision_id=None,
        schema_id="urn:cmp:testing:reference-import-mapping:1.0.0",
        schema_version="1.0.0",
        content_hash="c" * 64,
        created_at=NOW,
        created_by=ACTOR,
        change_reason="human confirms reference source labels",
        request_id=CONTEXT.request_id,
        trace_id=TRACE,
    )


class _TestingApiService:
    def __init__(self) -> None:
        report = detect_synthetic_csv_header(
            b"strain_pct,stress_mpa\n0,0\n",
            raw_asset_id=RAW_ASSET,
            raw_artifact_id=RAW_ARTIFACT,
            raw_sha256="a" * 64,
        )
        self.report = ImportDetectionReportSnapshot(
            id=REPORT,
            classification=DataClassification.INTERNAL,
            report=report,
            created_at=NOW,
            created_by=ACTOR,
            request_id=CONTEXT.request_id,
            trace_id=TRACE,
        )
        self.mapping: ImportMappingSnapshot | None = None

    async def detect_synthetic_csv_import(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: DetectSyntheticCsvImport,
    ) -> ImportDetectionReportSnapshot:
        assert context is CONTEXT
        assert decision is TESTING_WRITE
        assert (command.raw_asset_id, command.raw_artifact_id) == (RAW_ASSET, RAW_ARTIFACT)
        return self.report

    def get_import_detection_report(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        detection_report_id: UUID,
    ) -> ImportDetectionReportSnapshot:
        assert context is CONTEXT
        assert decision is TESTING_READ
        assert detection_report_id == REPORT
        return self.report

    def create_reference_import_mapping(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CreateReferenceImportMapping,
    ) -> ImportMappingSnapshot:
        assert context is CONTEXT
        assert decision is TESTING_WRITE
        assert command.detection_report_id == REPORT
        content = ReferenceImportMappingContent(
            mapping_label=command.mapping_label,
            detection_report_id=REPORT,
            raw_asset_id=RAW_ASSET,
            raw_artifact_id=RAW_ARTIFACT,
            strain_column=command.strain_column,
            stress_column=command.stress_column,
            strain_unit=command.strain_unit,
            stress_unit=command.stress_unit,
        )
        self.mapping = ImportMappingSnapshot(
            id=MAPPING,
            current=RevisionSnapshot(_record(MAPPING_REVISION, MAPPING), content),
        )
        return self.mapping

    def get_import_mapping(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        mapping_id: UUID,
    ) -> ImportMappingSnapshot:
        assert context is CONTEXT
        assert decision is TESTING_READ
        assert mapping_id == MAPPING
        assert self.mapping is not None
        return self.mapping

    def revise_reference_import_mapping(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        mapping_id: UUID,
        command: ReviseReferenceImportMapping,
    ) -> ImportMappingSnapshot:
        assert context is CONTEXT
        assert decision is TESTING_WRITE
        assert mapping_id == MAPPING
        assert self.mapping is not None
        return self.mapping


class _ProcessingApiService:
    def __init__(self) -> None:
        self.run: ImportRun | None = None

    async def execute_reference_import(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: ExecuteReferenceImport,
    ) -> ImportRun:
        assert context is CONTEXT
        assert decision is PROCESSING_EXECUTE
        assert (command.import_mapping_id, command.import_mapping_revision_id) == (
            MAPPING,
            MAPPING_REVISION,
        )
        self.run = ImportRun(
            id=IMPORT_RUN,
            classification=DataClassification.INTERNAL,
            test_run_id=command.test_run_id,
            test_run_revision_id=command.test_run_revision_id,
            raw_asset_id=command.raw_asset_id,
            raw_artifact_id=command.raw_artifact_id,
            import_mapping_id=command.import_mapping_id,
            import_mapping_revision_id=command.import_mapping_revision_id,
            mapping_sha256="d" * 64,
            importer_id="urn:cmp:testing:synthetic-csv-header-importer:1.0.0",
            importer_version="1.0.0",
            status=ImportRunStatus.SUCCEEDED,
            output_dataset_id=DATASET,
            output_dataset_revision_id=DATASET_REVISION,
            failure_code=None,
            change_reason=command.change_reason,
            started_at=NOW,
            ended_at=NOW,
            created_by=ACTOR,
            request_id=CONTEXT.request_id,
            trace_id=TRACE,
        )
        return self.run

    def get_import_run(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
    ) -> ImportRun:
        assert context is CONTEXT
        assert decision is PROCESSING_READ
        assert run_id == IMPORT_RUN
        assert self.run is not None
        return self.run


def _application() -> FastAPI:
    application = FastAPI()
    testing = _TestingApiService()
    processing = _ProcessingApiService()

    def security(request: Request) -> None:
        request.state.security_context = CONTEXT

    def testing_read(request: Request) -> None:
        request.state.authorization_decision = TESTING_READ

    def testing_write(request: Request) -> None:
        request.state.authorization_decision = TESTING_WRITE

    def processing_read(request: Request) -> None:
        request.state.authorization_decision = PROCESSING_READ

    def processing_execute(request: Request) -> None:
        request.state.authorization_decision = PROCESSING_EXECUTE

    install_testing_api(
        application,
        service=cast(ServicePort, testing),
        security_dependency=security,
        read_dependency=testing_read,
        write_dependency=testing_write,
    )
    install_processing_api(
        application,
        service=cast(ProcessingService, processing),
        security_dependency=security,
        read_dependency=processing_read,
        execute_dependency=processing_execute,
    )
    return application


def _request(
    application: FastAPI,
    method: str,
    path: str,
    *,
    json: dict[str, object] | None = None,
) -> httpx.Response:
    async def send() -> httpx.Response:
        transport = httpx.ASGITransport(app=application)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.request(method, path, json=json)

    return asyncio.run(send())


def test_reference_import_api_requires_visible_detection_then_explicit_mapping_then_run() -> None:
    application = _application()

    detection = _request(
        application,
        "POST",
        "/api/v1/imports:detect",
        json={"raw_asset_id": str(RAW_ASSET), "raw_artifact_id": str(RAW_ARTIFACT)},
    )
    assert detection.status_code == 201
    assert detection.json()["status"] == "needs_input"
    assert detection.json()["strain_suggestion"]["confidence"] == "low"
    assert detection.json()["stress_suggestion"]["confidence"] == "low"

    mapping = _request(
        application,
        "POST",
        "/api/v1/import-mappings",
        json={
            "detection_report_id": str(REPORT),
            "mapping_label": "Human-confirmed original labels",
            "strain_column": "strain_pct",
            "stress_column": "stress_mpa",
            "strain_unit": "%",
            "stress_unit": "MPa",
            "change_reason": "Human confirms original CSV semantics and units.",
        },
    )
    assert mapping.status_code == 201
    assert mapping.headers["ETag"] == '"revision:1:sha256:' + "c" * 64 + '"'
    assert mapping.json()["current_revision"]["content"]["approval_kind"] == "human_confirmed"

    imported = _request(
        application,
        "POST",
        "/api/v1/imports",
        json={
            "test_run_id": str(TEST_RUN),
            "test_run_revision_id": str(TEST_RUN_REVISION),
            "raw_asset_id": str(RAW_ASSET),
            "raw_artifact_id": str(RAW_ARTIFACT),
            "import_mapping_id": str(MAPPING),
            "import_mapping_revision_id": str(MAPPING_REVISION),
            "change_reason": "Create immutable reference Dataset revisions from confirmed mapping.",
        },
    )
    assert imported.status_code == 201
    assert imported.json()["status"] == "succeeded"
    assert imported.json()["execution_mode"] == "reference_inline"
    assert imported.json()["output_dataset_revision_id"] == str(DATASET_REVISION)

    retrieved = _request(application, "GET", f"/api/v1/imports/{IMPORT_RUN}")
    assert retrieved.status_code == 200
    assert retrieved.json()["import_mapping_revision_id"] == str(MAPPING_REVISION)

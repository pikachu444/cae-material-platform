from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import cast
from uuid import UUID

import httpx
from cmp.modules.exporting.adapters.api.bulk_export import install_bulk_export_api
from cmp.modules.exporting.application.bulk_export import (
    BulkExportBundle,
    BulkExportJob,
    BulkExportService,
    CreateExportSelection,
    ExportCandidate,
    ExportSelectionSnapshot,
)
from cmp.modules.exporting.domain.bulk_bundle import (
    BulkExportJobState,
    ExportMemberKind,
    ExportSelectionContent,
    ExportSelectionMember,
    ExportSourceRef,
    sha256_bytes,
)
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
from cmp.shared.domain.revisions import RevisionRecord, TenantScope
from fastapi import FastAPI, Request

NOW = datetime(2026, 8, 22, 9, 0, tzinfo=UTC)
ORG, PROJECT, ACTOR, MATERIAL = (UUID(int=value) for value in range(1, 5))
SELECTION, SELECTION_REVISION, JOB, BUNDLE, MODEL, MODEL_REVISION, ARTIFACT = (
    UUID(int=value) for value in range(10, 17)
)
TRACE = "00-00000000000000000000000000000056-0000000000000056-01"
VALUE = b'{"model":"elastic"}\n'
SOURCE = ExportSourceRef(
    ExportMemberKind.MODEL_IR_JSON,
    material_model_id=MODEL,
    material_model_revision_id=MODEL_REVISION,
)
MEMBER = ExportSelectionMember(
    1,
    SOURCE,
    f"models/{MODEL}/{MODEL_REVISION}/ir.json",
    sha256_bytes(VALUE),
    len(VALUE),
    "application/json",
    DataClassification.INTERNAL,
    "Exact model IR",
)
CONTENT = ExportSelectionContent("API selection", (MEMBER,), ())


def _context() -> SecurityContext:
    return SecurityContext(
        principal=Principal(ACTOR, PrincipalType.USER, "Bulk exporter", True),
        organization_id=ORG,
        project_id=PROJECT,
        issuer="https://test.invalid",
        subject=str(ACTOR),
        token_id="bulk-export-api-test",
        groups=(),
        scopes=("openid",),
        request_id=UUID(int=20),
        trace_id=TRACE,
        authenticated_at=NOW,
    )


CONTEXT = _context()
DECISION = AuthorizationDecision(
    principal_id=ACTOR,
    organization_id=ORG,
    project_id=PROJECT,
    permission=Permission.EXPORT_EXECUTE,
    roles=(Role.MATERIAL_MODELER,),
    database_permissions=(Permission.EXPORT_EXECUTE.value, Permission.EXPORT_READ.value),
    max_classification=DataClassification.INTERNAL,
    allow_export_controlled=False,
    request_id=CONTEXT.request_id,
    trace_id=TRACE,
    decided_at=NOW,
)
RECORD = RevisionRecord(
    SELECTION_REVISION,
    "exporting.bulk_export_selection",
    SELECTION,
    TenantScope(ORG, PROJECT, "internal"),
    1,
    None,
    BulkExportService.SCHEMA_ID,
    BulkExportService.SCHEMA_VERSION,
    CONTENT.digest,
    NOW,
    ACTOR,
    "API integration fixture",
    CONTEXT.request_id,
    TRACE,
)
SNAPSHOT = ExportSelectionSnapshot(SELECTION, RECORD, CONTENT)
JOB_RECORD = BulkExportJob(
    JOB,
    ORG,
    PROJECT,
    DataClassification.INTERNAL,
    SELECTION,
    SELECTION_REVISION,
    BulkExportJobState.SUCCEEDED,
    1,
    BUNDLE,
    None,
    None,
    NOW,
    ACTOR,
    NOW,
    NOW,
)
BUNDLE_RECORD = BulkExportBundle(
    BUNDLE,
    ORG,
    PROJECT,
    DataClassification.INTERNAL,
    SELECTION,
    SELECTION_REVISION,
    ARTIFACT,
    "a" * 64,
    512,
    "b" * 64,
    1,
    0,
    NOW,
    ACTOR,
)


class _Service:
    command: CreateExportSelection | None = None

    async def discover(self, *_: object) -> tuple[ExportCandidate, ...]:
        return (
            ExportCandidate(
                SOURCE,
                DataClassification.INTERNAL,
                sha256_bytes(VALUE),
                len(VALUE),
                "application/json",
                MEMBER.archive_path,
                MEMBER.label,
            ),
        )

    async def create_selection(
        self,
        _: SecurityContext,
        __: AuthorizationDecision,
        command: CreateExportSelection,
    ) -> ExportSelectionSnapshot:
        self.command = command
        return SNAPSHOT

    def get_selection(self, *_: object) -> ExportSelectionSnapshot:
        return SNAPSHOT

    async def create_job(self, *_: object) -> tuple[BulkExportJob, BulkExportBundle]:
        return JOB_RECORD, BUNDLE_RECORD

    def get_job(self, *_: object) -> BulkExportJob:
        return JOB_RECORD

    def get_bundle(self, *_: object) -> BulkExportBundle:
        return BUNDLE_RECORD

    def list_bundles(self, *_: object) -> tuple[BulkExportBundle, ...]:
        return (BUNDLE_RECORD,)


def test_bulk_export_api_exposes_typed_selection_job_and_bundle_resources() -> None:
    application = FastAPI()
    service = _Service()

    async def security(request: Request) -> None:
        request.state.security_context = CONTEXT

    async def authorization(request: Request) -> None:
        request.state.authorization_decision = DECISION

    install_bulk_export_api(
        application,
        service=cast(BulkExportService, service),
        artifacts=None,
        security_dependency=security,
        read_dependency=authorization,
        execute_dependency=authorization,
    )

    async def exercise() -> tuple[httpx.Response, ...]:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=application), base_url="http://test"
        ) as client:
            candidates = await client.get(
                "/api/v1/bulk-export-candidates", params={"material_id": str(MATERIAL)}
            )
            selection = await client.post(
                "/api/v1/export-selections",
                json={
                    "classification": "internal",
                    "selection_label": "API selection",
                    "members": [
                        {
                            "ordinal": 1,
                            "source": {
                                "kind": "model_ir_json",
                                "raw_asset_id": None,
                                "artifact_id": None,
                                "dataset_id": None,
                                "dataset_revision_id": None,
                                "material_model_id": str(MODEL),
                                "material_model_revision_id": str(MODEL_REVISION),
                                "solver_card_id": None,
                                "solver_card_revision_id": None,
                            },
                            "required": True,
                            "archive_path": MEMBER.archive_path,
                        }
                    ],
                    "change_reason": "API integration fixture",
                },
            )
            job = await client.post(
                "/api/v1/export-jobs", json={"export_selection_id": str(SELECTION)}
            )
            bundles = await client.get("/api/v1/export-bundles")
        return candidates, selection, job, bundles

    candidates, selection, job, bundles = asyncio.run(exercise())

    assert candidates.status_code == 200
    assert candidates.json()["items"][0]["source"]["kind"] == "model_ir_json"
    assert selection.status_code == 201
    assert selection.headers["etag"].startswith('"revision:1:sha256:')
    assert service.command is not None and service.command.members[0].source == SOURCE
    assert job.status_code == 201 and job.json()["state"] == "succeeded"
    assert bundles.json()["items"][0]["archive_sha256"] == f"sha256:{'a' * 64}"

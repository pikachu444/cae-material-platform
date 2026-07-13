from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import cast
from uuid import UUID, uuid4

import httpx
from cmp.modules.datasets.adapters.api.datasets import install_dataset_api
from cmp.modules.datasets.application.service import (
    DATASET_SELECTION_AGGREGATE_TYPE,
    CreateReferenceDatasetSelection,
    DatasetSelectionSnapshot,
    DatasetService,
)
from cmp.modules.datasets.application.service import (
    RevisionSnapshot as DatasetRevisionSnapshot,
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
from cmp.modules.processing.adapters.api.processing import install_processing_api
from cmp.modules.processing.application.service import (
    PROCESSING_RECIPE_AGGREGATE_TYPE,
    CreateReferenceTensileCropRecipe,
    ExecuteReferenceTensileCrop,
    ProcessingRecipeSnapshot,
    ProcessingRun,
    ProcessingService,
)
from cmp.modules.processing.application.service import (
    RevisionSnapshot as ProcessingRevisionSnapshot,
)
from cmp.modules.processing.domain.reference_tensile_crop import (
    ProcessingRunStatus,
    ReferenceTensileCropRecipeContent,
)
from cmp.shared.domain.revisions import RevisionRecord, TenantScope
from fastapi import FastAPI, Request

NOW = datetime(2026, 7, 15, 11, 0, tzinfo=UTC)
ORG = UUID("f4000000-0000-4000-8000-000000000001")
PROJECT = UUID("f4000000-0000-4000-8000-000000000002")
ACTOR = UUID("f4000000-0000-4000-8000-000000000003")
DATASET = UUID("f4000000-0000-4000-8000-000000000004")
DATASET_REVISION = UUID("f4000000-0000-4000-8000-000000000005")
SELECTION = UUID("f4000000-0000-4000-8000-000000000006")
SELECTION_REVISION = UUID("f4000000-0000-4000-8000-000000000007")
RECIPE = UUID("f4000000-0000-4000-8000-000000000008")
RECIPE_REVISION = UUID("f4000000-0000-4000-8000-000000000009")
RUN = UUID("f4000000-0000-4000-8000-00000000000a")
ARTIFACT = UUID("f4000000-0000-4000-8000-00000000000b")
OUTPUT_DATASET = UUID("f4000000-0000-4000-8000-00000000000c")
OUTPUT_DATASET_REVISION = UUID("f4000000-0000-4000-8000-00000000000d")
TRACE = "00-000000000000000000000000000000f4-00000000000000f4-01"


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


def _decision(permission: Permission) -> AuthorizationDecision:
    return AuthorizationDecision(
        principal_id=ACTOR,
        organization_id=ORG,
        project_id=PROJECT,
        permission=permission,
        roles=(Role.MATERIAL_MODELER,),
        database_permissions=database_permissions_for(permission),
        max_classification=DataClassification.INTERNAL,
        allow_export_controlled=False,
        request_id=CONTEXT.request_id,
        trace_id=TRACE,
        decided_at=NOW,
    )


DATASET_READ = _decision(Permission.DATASET_READ)
DATASET_WRITE = _decision(Permission.DATASET_WRITE)
PROCESSING_READ = _decision(Permission.PROCESSING_READ)
PROCESSING_EXECUTE = _decision(Permission.PROCESSING_EXECUTE)


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
        content_hash="d" * 64,
        created_at=NOW,
        created_by=ACTOR,
        change_reason="reference API test",
        request_id=CONTEXT.request_id,
        trace_id=TRACE,
    )


def _selection() -> DatasetSelectionSnapshot:
    content = ReferenceDatasetSelectionContent(
        selection_label="Elastic input selection",
        dataset_id=DATASET,
        dataset_revision_id=DATASET_REVISION,
    )
    return DatasetSelectionSnapshot(
        id=SELECTION,
        selection_label=content.selection_label,
        current=DatasetRevisionSnapshot(
            _record(
                revision_id=SELECTION_REVISION,
                aggregate_id=SELECTION,
                aggregate_type=DATASET_SELECTION_AGGREGATE_TYPE,
            ),
            content,
        ),
    )


def _recipe() -> ProcessingRecipeSnapshot:
    content = ReferenceTensileCropRecipeContent("Elastic crop", 0.01, 0.03)
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


def _run() -> ProcessingRun:
    return ProcessingRun(
        id=RUN,
        classification=DataClassification.INTERNAL,
        selection_id=SELECTION,
        selection_revision_id=SELECTION_REVISION,
        recipe_id=RECIPE,
        recipe_revision_id=RECIPE_REVISION,
        input_dataset_id=DATASET,
        input_dataset_revision_id=DATASET_REVISION,
        status=ProcessingRunStatus.SUCCEEDED,
        input_point_count=4,
        output_point_count=3,
        removed_point_count=1,
        result_artifact_id=ARTIFACT,
        result_sha256="e" * 64,
        output_dataset_id=OUTPUT_DATASET,
        output_dataset_revision_id=OUTPUT_DATASET_REVISION,
        failure_code=None,
        change_reason="Commit elastic crop",
        started_at=NOW,
        ended_at=NOW,
        created_by=ACTOR,
        request_id=CONTEXT.request_id,
        trace_id=TRACE,
    )


class _DatasetApiService:
    def create_reference_dataset_selection(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CreateReferenceDatasetSelection,
    ) -> DatasetSelectionSnapshot:
        assert context is CONTEXT
        assert decision is DATASET_WRITE
        assert command.classification is DataClassification.INTERNAL
        assert command.selection_label == "Elastic input selection"
        assert command.dataset_revision_id == DATASET_REVISION
        return _selection()


class _ProcessingApiService:
    def create_reference_tensile_crop_recipe(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CreateReferenceTensileCropRecipe,
    ) -> ProcessingRecipeSnapshot:
        assert context is CONTEXT
        assert decision is PROCESSING_EXECUTE
        assert command.classification is DataClassification.INTERNAL
        assert command.content == ReferenceTensileCropRecipeContent("Elastic crop", 0.01, 0.03)
        return _recipe()

    async def execute_reference_tensile_crop(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: ExecuteReferenceTensileCrop,
    ) -> ProcessingRun:
        assert context is CONTEXT
        assert decision is PROCESSING_EXECUTE
        assert (command.selection_id, command.selection_revision_id) == (
            SELECTION,
            SELECTION_REVISION,
        )
        assert (command.recipe_id, command.recipe_revision_id) == (RECIPE, RECIPE_REVISION)
        return _run()

    def get_run(
        self, context: SecurityContext, decision: AuthorizationDecision, run_id: UUID
    ) -> ProcessingRun:
        assert context is CONTEXT
        assert decision is PROCESSING_READ
        assert run_id == RUN
        return _run()


def _application() -> FastAPI:
    application = FastAPI()

    def security(request: Request) -> None:
        request.state.security_context = CONTEXT

    def dataset_read(request: Request) -> None:
        request.state.authorization_decision = DATASET_READ

    def dataset_write(request: Request) -> None:
        request.state.authorization_decision = DATASET_WRITE

    def processing_read(request: Request) -> None:
        request.state.authorization_decision = PROCESSING_READ

    def processing_execute(request: Request) -> None:
        request.state.authorization_decision = PROCESSING_EXECUTE

    install_dataset_api(
        application,
        service=cast(DatasetService, _DatasetApiService()),
        security_dependency=security,
        read_dependency=dataset_read,
        write_dependency=dataset_write,
    )
    install_processing_api(
        application,
        service=cast(ProcessingService, _ProcessingApiService()),
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


def test_reference_processing_api_pins_selection_recipe_and_exposes_committed_output() -> None:
    application = _application()

    selection = _request(
        application,
        "POST",
        "/api/v1/dataset-selections",
        json={
            "classification": "internal",
            "selection_label": "Elastic input selection",
            "dataset_revision_id": str(DATASET_REVISION),
            "change_reason": "Pin normalized curve for crop",
        },
    )
    assert selection.status_code == 201
    assert selection.headers["Location"] == f"/api/v1/dataset-selections/{SELECTION}"
    assert selection.json()["current_revision"]["content"] == {
        "selection_kind": "reference_normalized_dataset_revision",
        "member_count": 1,
        "dataset_id": str(DATASET),
        "dataset_revision_id": str(DATASET_REVISION),
    }

    recipe = _request(
        application,
        "POST",
        "/api/v1/processing-recipes/reference-tensile-crop",
        json={
            "classification": "internal",
            "content": {
                "recipe_label": "Elastic crop",
                "minimum_engineering_strain": 0.01,
                "maximum_engineering_strain": 0.03,
            },
            "change_reason": "Define observed-point crop",
        },
    )
    assert recipe.status_code == 201
    assert recipe.json()["current_revision"]["content"]["boundary_policy"] == (
        "select_observed_points_inclusive_no_interpolation"
    )

    run = _request(
        application,
        "POST",
        "/api/v1/processing-runs/reference-tensile-crop",
        json={
            "selection_id": str(SELECTION),
            "selection_revision_id": str(SELECTION_REVISION),
            "recipe_id": str(RECIPE),
            "recipe_revision_id": str(RECIPE_REVISION),
            "change_reason": "Commit elastic crop",
        },
    )
    assert run.status_code == 201
    assert run.json()["status"] == "succeeded"
    assert run.json()["output_dataset_id"] == str(OUTPUT_DATASET)
    assert run.json()["links"]["output_curve"] == (
        f"/api/v1/dataset-revisions/{OUTPUT_DATASET_REVISION}/curve"
    )
    assert _request(application, "GET", f"/api/v1/processing-runs/{RUN}").status_code == 200

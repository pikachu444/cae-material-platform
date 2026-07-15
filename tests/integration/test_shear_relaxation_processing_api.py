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
from cmp.modules.processing.adapters.api.shear_relaxation import (
    install_shear_relaxation_processing_api,
)
from cmp.modules.processing.application.shear_relaxation import (
    SHEAR_RELAXATION_RECIPE_AGGREGATE_TYPE,
    CreateShearRelaxationCropRecipe,
    ExecuteShearRelaxationCrop,
    RevisionSnapshot,
    ShearRelaxationProcessingRun,
    ShearRelaxationProcessingService,
    ShearRelaxationRecipeSnapshot,
)
from cmp.modules.processing.domain.reference_shear_relaxation_crop import (
    ReferenceShearRelaxationCropRecipeContent,
)
from cmp.modules.processing.domain.reference_tensile_crop import ProcessingRunStatus
from cmp.shared.domain.revisions import RevisionRecord, TenantScope
from fastapi import FastAPI, Request

NOW = datetime(2026, 8, 9, 9, 0, tzinfo=UTC)
ORG = UUID("fa000000-0000-4000-8000-000000000001")
PROJECT = UUID("fa000000-0000-4000-8000-000000000002")
ACTOR = UUID("fa000000-0000-4000-8000-000000000003")
RECIPE = UUID("fa000000-0000-4000-8000-000000000004")
RECIPE_REVISION = UUID("fa000000-0000-4000-8000-000000000005")
DATASET = UUID("fa000000-0000-4000-8000-000000000006")
DATASET_REVISION = UUID("fa000000-0000-4000-8000-000000000007")
RUN = UUID("fa000000-0000-4000-8000-000000000008")
ARTIFACT = UUID("fa000000-0000-4000-8000-000000000009")
OUTPUT = UUID("fa000000-0000-4000-8000-00000000000a")
OUTPUT_REVISION = UUID("fa000000-0000-4000-8000-00000000000b")
TRACE = "00-000000000000000000000000000000fa-00000000000000fa-01"

CONTEXT = SecurityContext(
    principal=Principal(ACTOR, PrincipalType.USER, "Material Modeler", True),
    organization_id=ORG,
    project_id=PROJECT,
    issuer="https://test.invalid",
    subject=str(ACTOR),
    token_id=str(uuid4()),
    groups=(),
    scopes=("openid",),
    request_id=uuid4(),
    trace_id=TRACE,
    authenticated_at=NOW,
)


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


READ = _decision(Permission.PROCESSING_READ)
EXECUTE = _decision(Permission.PROCESSING_EXECUTE)


def _record() -> RevisionRecord:
    return RevisionRecord(
        revision_id=RECIPE_REVISION,
        aggregate_type=SHEAR_RELAXATION_RECIPE_AGGREGATE_TYPE,
        aggregate_id=RECIPE,
        scope=TenantScope(ORG, PROJECT, "internal"),
        revision_no=1,
        based_on_revision_id=None,
        schema_id="urn:cmp:processing:reference-shear-relaxation-time-crop-recipe:1.0.0",
        schema_version="1.0.0",
        content_hash="a" * 64,
        created_at=NOW,
        created_by=ACTOR,
        change_reason="API test",
        request_id=CONTEXT.request_id,
        trace_id=TRACE,
    )


def _recipe() -> ShearRelaxationRecipeSnapshot:
    return ShearRelaxationRecipeSnapshot(
        RECIPE,
        RevisionSnapshot(
            _record(),
            ReferenceShearRelaxationCropRecipeContent("Calibration window", 1.0, 50.0),
        ),
    )


def _run() -> ShearRelaxationProcessingRun:
    return ShearRelaxationProcessingRun(
        id=RUN,
        classification=DataClassification.INTERNAL,
        recipe_id=RECIPE,
        recipe_revision_id=RECIPE_REVISION,
        input_dataset_id=DATASET,
        input_dataset_revision_id=DATASET_REVISION,
        status=ProcessingRunStatus.SUCCEEDED,
        input_point_count=6,
        output_point_count=4,
        removed_point_count=2,
        result_artifact_id=ARTIFACT,
        result_sha256="b" * 64,
        output_dataset_id=OUTPUT,
        output_dataset_revision_id=OUTPUT_REVISION,
        failure_code=None,
        change_reason="Commit explicit crop",
        started_at=NOW,
        ended_at=NOW,
        created_by=ACTOR,
        request_id=CONTEXT.request_id,
        trace_id=TRACE,
    )


class _Service:
    def create_recipe(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CreateShearRelaxationCropRecipe,
    ) -> ShearRelaxationRecipeSnapshot:
        assert context is CONTEXT and decision is EXECUTE
        assert command.content == ReferenceShearRelaxationCropRecipeContent(
            "Calibration window", 1.0, 50.0
        )
        return _recipe()

    async def execute(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: ExecuteShearRelaxationCrop,
    ) -> ShearRelaxationProcessingRun:
        assert context is CONTEXT and decision is EXECUTE
        assert command.input_dataset_revision_id == DATASET_REVISION
        return _run()

    def get_run(
        self, context: SecurityContext, decision: AuthorizationDecision, run_id: UUID
    ) -> ShearRelaxationProcessingRun:
        assert context is CONTEXT and decision is READ and run_id == RUN
        return _run()


def _application() -> FastAPI:
    application = FastAPI()

    def security(request: Request) -> None:
        request.state.security_context = CONTEXT

    def read(request: Request) -> None:
        request.state.authorization_decision = READ

    def execute(request: Request) -> None:
        request.state.authorization_decision = EXECUTE

    install_shear_relaxation_processing_api(
        application,
        service=cast(ShearRelaxationProcessingService, _Service()),
        security_dependency=security,
        read_dependency=read,
        execute_dependency=execute,
    )
    return application


def _request(method: str, path: str, json: dict[str, object] | None = None) -> httpx.Response:
    async def send() -> httpx.Response:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=_application()), base_url="http://test"
        ) as client:
            return await client.request(method, path, json=json)

    return asyncio.run(send())


def test_shear_processing_api_pins_revisions_and_exposes_processed_dataset() -> None:
    recipe = _request(
        "POST",
        "/api/v1/processing-recipes/reference-shear-relaxation-crop",
        {
            "classification": "internal",
            "recipe_label": "Calibration window",
            "minimum_time_s": 1.0,
            "maximum_time_s": 50.0,
            "change_reason": "Define explicit observed-point window",
        },
    )
    assert recipe.status_code == 201
    assert recipe.json()["content"]["boundary_policy"].endswith("no_interpolation")
    run = _request(
        "POST",
        "/api/v1/processing-runs/reference-shear-relaxation-crop",
        {
            "recipe_id": str(RECIPE),
            "recipe_revision_id": str(RECIPE_REVISION),
            "input_dataset_id": str(DATASET),
            "input_dataset_revision_id": str(DATASET_REVISION),
            "change_reason": "Commit explicit crop",
        },
    )
    assert run.status_code == 201
    assert run.json()["status"] == "succeeded"
    assert run.json()["output_dataset_revision_id"] == str(OUTPUT_REVISION)
    assert _request(
        "GET", f"/api/v1/processing-runs/reference-shear-relaxation/{RUN}"
    ).status_code == 200

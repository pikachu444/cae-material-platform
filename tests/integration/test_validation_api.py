from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any, cast
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
from cmp.modules.validation.adapters.api.validation import install_validation_api
from cmp.modules.validation.application.service import (
    VALIDATION_PLAN_AGGREGATE_TYPE,
    VALIDATION_TEMPLATE_AGGREGATE_TYPE,
    CreateReferenceValidationPlan,
    CreateReferenceValidationTemplate,
    ReferenceValidationService,
    RevisionSnapshot,
    SubmitValidationRun,
    ValidationPlanSnapshot,
    ValidationRun,
    ValidationRunDetail,
    ValidationRunResultManifest,
    ValidationTemplateSnapshot,
)
from cmp.modules.validation.domain.reference_virtual_specimen import (
    ReferenceRunnerOutcome,
    ReferenceValidationPlanContent,
    ReferenceVirtualSpecimenTemplateContent,
    SolverTerminationStatus,
    ValidationArtifactReference,
    ValidationExecutionMode,
    ValidationRunResultManifestContent,
    ValidationRunStatus,
)
from cmp.shared.domain.revisions import RevisionRecord, TenantScope
from fastapi import FastAPI, Request

NOW = datetime(2026, 7, 21, 9, 0, tzinfo=UTC)
ORG = UUID("27000000-0000-4000-8000-000000000101")
PROJECT = UUID("27000000-0000-4000-8000-000000000102")
ACTOR = UUID("27000000-0000-4000-8000-000000000103")
TEMPLATE = UUID("27000000-0000-4000-8000-000000000104")
TEMPLATE_REVISION = UUID("27000000-0000-4000-8000-000000000105")
PLAN = UUID("27000000-0000-4000-8000-000000000106")
PLAN_REVISION = UUID("27000000-0000-4000-8000-000000000107")
MODEL = UUID("27000000-0000-4000-8000-000000000108")
MODEL_REVISION = UUID("27000000-0000-4000-8000-000000000109")
CARD = UUID("27000000-0000-4000-8000-00000000010a")
CARD_REVISION = UUID("27000000-0000-4000-8000-00000000010b")
SELECTION = UUID("27000000-0000-4000-8000-00000000010c")
SELECTION_REVISION = UUID("27000000-0000-4000-8000-00000000010d")
RUN = UUID("27000000-0000-4000-8000-00000000010e")
MANIFEST = UUID("27000000-0000-4000-8000-00000000010f")
DECK = UUID("27000000-0000-4000-8000-000000000110")
STDOUT = UUID("27000000-0000-4000-8000-000000000111")
STDERR = UUID("27000000-0000-4000-8000-000000000112")
NATIVE = UUID("27000000-0000-4000-8000-000000000113")
MANIFEST_ARTIFACT = UUID("27000000-0000-4000-8000-000000000114")
TRACE = "00-00000000000000000000000000000270-0000000000000270-01"

CONTEXT = SecurityContext(
    principal=Principal(ACTOR, PrincipalType.USER, "Validation engineer", True),
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


READ = _decision(Permission.VALIDATION_READ)
EXECUTE = _decision(Permission.VALIDATION_EXECUTE)


def _record(
    revision_id: UUID,
    aggregate_id: UUID,
    aggregate_type: str,
    content_hash: str,
) -> RevisionRecord:
    return RevisionRecord(
        revision_id=revision_id,
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        scope=TenantScope(ORG, PROJECT, DataClassification.INTERNAL.value),
        revision_no=1,
        based_on_revision_id=None,
        schema_id=(
            "urn:cmp:validation:reference-uniaxial-virtual-specimen:1.0.0"
            if aggregate_type == VALIDATION_TEMPLATE_AGGREGATE_TYPE
            else "urn:cmp:validation:reference-uniaxial-validation-plan:1.0.0"
        ),
        schema_version="1.0.0",
        content_hash=content_hash,
        created_at=NOW,
        created_by=ACTOR,
        change_reason="validation API fixture",
        request_id=CONTEXT.request_id,
        trace_id=TRACE,
    )


def _template() -> ReferenceVirtualSpecimenTemplateContent:
    return ReferenceVirtualSpecimenTemplateContent(
        template_label="Reference virtual specimen",
        gauge_length_m=0.05,
        cross_section_area_m2=1e-5,
        axial_element_count=10,
        axial_displacement_end_m=0.001,
        output_sample_count=5,
    )


def _plan() -> ReferenceValidationPlanContent:
    return ReferenceValidationPlanContent(
        plan_label="Reference tensile validation",
        template_id=TEMPLATE,
        template_revision_id=TEMPLATE_REVISION,
        material_model_id=MODEL,
        material_model_revision_id=MODEL_REVISION,
        solver_card_id=CARD,
        solver_card_revision_id=CARD_REVISION,
        experimental_selection_id=SELECTION,
        experimental_selection_revision_id=SELECTION_REVISION,
    )


def _artifact(value: UUID, digest: str) -> ValidationArtifactReference:
    return ValidationArtifactReference(value, digest)


class _ValidationService:
    def __init__(self) -> None:
        self.template = ValidationTemplateSnapshot(
            TEMPLATE,
            RevisionSnapshot(
                _record(TEMPLATE_REVISION, TEMPLATE, VALIDATION_TEMPLATE_AGGREGATE_TYPE, "a" * 64),
                _template(),
            ),
        )
        self.plan = ValidationPlanSnapshot(
            PLAN,
            RevisionSnapshot(
                _record(PLAN_REVISION, PLAN, VALIDATION_PLAN_AGGREGATE_TYPE, "b" * 64), _plan()
            ),
        )
        self.run = self._run(ValidationRunStatus.QUEUED)
        self.manifest: ValidationRunResultManifest | None = None

    def _run(self, status: ValidationRunStatus) -> ValidationRun:
        return ValidationRun(
            id=RUN,
            classification=DataClassification.INTERNAL,
            plan_id=PLAN,
            plan_revision_id=PLAN_REVISION,
            template_id=TEMPLATE,
            template_revision_id=TEMPLATE_REVISION,
            material_model_id=MODEL,
            material_model_revision_id=MODEL_REVISION,
            solver_card_id=CARD,
            solver_card_revision_id=CARD_REVISION,
            experimental_selection_id=SELECTION,
            experimental_selection_revision_id=SELECTION_REVISION,
            execution_mode=ValidationExecutionMode.REFERENCE_INLINE_MOCK,
            runner_id="cmp.reference.inline-mock-runner",
            runner_version="1.0.0",
            runner_digest="c" * 64,
            status=status,
            deck=_artifact(DECK, "d" * 64),
            external_job_reference=None,
            failure_code=None,
            submitted_at=NOW,
            started_at=NOW if status is not ValidationRunStatus.QUEUED else None,
            ended_at=NOW if status is ValidationRunStatus.SUCCEEDED else None,
            created_by=ACTOR,
            request_id=CONTEXT.request_id,
            trace_id=TRACE,
            change_reason="submit reference validation run",
        )

    def create_template(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CreateReferenceValidationTemplate,
    ) -> ValidationTemplateSnapshot:
        assert context is CONTEXT and decision is EXECUTE
        assert command.content.non_production is True
        return self.template

    def revise_template(self, *args: Any, **kwargs: Any) -> ValidationTemplateSnapshot:
        return self.template

    def list_templates(
        self, context: SecurityContext, decision: AuthorizationDecision, *, limit: int
    ) -> tuple[ValidationTemplateSnapshot, ...]:
        assert context is CONTEXT and decision is READ and limit == 100
        return (self.template,)

    def get_template(
        self, context: SecurityContext, decision: AuthorizationDecision, template_id: UUID
    ) -> ValidationTemplateSnapshot:
        assert context is CONTEXT and decision is READ and template_id == TEMPLATE
        return self.template

    def create_plan(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CreateReferenceValidationPlan,
    ) -> ValidationPlanSnapshot:
        assert context is CONTEXT and decision is EXECUTE
        assert command.content.solver_card_revision_id == CARD_REVISION
        assert command.content.experimental_selection_revision_id == SELECTION_REVISION
        return self.plan

    def revise_plan(self, *args: Any, **kwargs: Any) -> ValidationPlanSnapshot:
        return self.plan

    def list_plans(
        self, context: SecurityContext, decision: AuthorizationDecision, *, limit: int
    ) -> tuple[ValidationPlanSnapshot, ...]:
        assert context is CONTEXT and decision is READ and limit == 100
        return (self.plan,)

    def get_plan(
        self, context: SecurityContext, decision: AuthorizationDecision, plan_id: UUID
    ) -> ValidationPlanSnapshot:
        assert context is CONTEXT and decision is READ and plan_id == PLAN
        return self.plan

    async def submit_run(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: SubmitValidationRun,
    ) -> ValidationRunDetail:
        assert context is CONTEXT and decision is EXECUTE
        assert command.execution_mode is ValidationExecutionMode.REFERENCE_INLINE_MOCK
        assert (command.plan_id, command.plan_revision_id) == (PLAN, PLAN_REVISION)
        self.run = self._run(ValidationRunStatus.QUEUED)
        self.manifest = None
        return ValidationRunDetail(self.run, None)

    def get_run(
        self, context: SecurityContext, decision: AuthorizationDecision, run_id: UUID
    ) -> ValidationRunDetail:
        assert context is CONTEXT and decision is READ and run_id == RUN
        return ValidationRunDetail(self.run, self.manifest)

    async def poll_reference_mock_run(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
        *,
        outcome: ReferenceRunnerOutcome,
        change_reason: str,
    ) -> ValidationRunDetail:
        assert context is CONTEXT and decision is EXECUTE and run_id == RUN
        assert outcome is ReferenceRunnerOutcome.SUCCEEDED
        assert change_reason
        self.run = self._run(ValidationRunStatus.SUCCEEDED)
        content = ValidationRunResultManifestContent(
            validation_run_id=RUN,
            execution_mode=ValidationExecutionMode.REFERENCE_INLINE_MOCK,
            solver_termination=SolverTerminationStatus.NORMAL,
            external_job_reference=None,
            deck=self.run.deck,
            stdout=_artifact(STDOUT, "e" * 64),
            stderr=_artifact(STDERR, "f" * 64),
            native_result=_artifact(NATIVE, "1" * 64),
            native_result_state="available",
        )
        self.manifest = ValidationRunResultManifest(
            id=MANIFEST,
            content=content,
            manifest_artifact=_artifact(MANIFEST_ARTIFACT, "2" * 64),
            manifest_sha256="3" * 64,
            created_at=NOW,
            created_by=ACTOR,
        )
        return ValidationRunDetail(self.run, self.manifest)

    def cancel_run(self, *args: Any, **kwargs: Any) -> ValidationRunDetail:
        return ValidationRunDetail(self.run, self.manifest)

    async def attach_manual_result(self, *args: Any, **kwargs: Any) -> ValidationRunDetail:
        return ValidationRunDetail(self.run, self.manifest)


def _application() -> FastAPI:
    application = FastAPI()
    service = _ValidationService()

    def security(request: Request) -> None:
        request.state.security_context = CONTEXT

    def read(request: Request) -> None:
        request.state.authorization_decision = READ

    def execute(request: Request) -> None:
        request.state.authorization_decision = EXECUTE

    install_validation_api(
        application,
        service=cast(ReferenceValidationService, service),
        security_dependency=security,
        read_dependency=read,
        execute_dependency=execute,
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


def test_validation_api_pins_inputs_and_exposes_terminal_artifact_manifest_without_verdict(
) -> None:
    application = _application()

    template = _request(
        application,
        "POST",
        "/api/v1/validation-templates",
        json={
            "classification": "internal",
            "content": {
                "template_label": "Reference virtual specimen",
                "gauge_length_m": 0.05,
                "cross_section_area_m2": 1e-5,
                "axial_element_count": 10,
                "axial_displacement_end_m": 0.001,
                "output_sample_count": 5,
            },
            "change_reason": "Create reference virtual specimen template",
        },
    )
    assert template.status_code == 201
    assert template.headers["etag"] == '"revision:1:sha256:' + "a" * 64 + '"'
    assert template.json()["current_revision"]["content"]["non_production"] is True

    plan = _request(
        application,
        "POST",
        "/api/v1/validation-plans",
        json={
            "classification": "internal",
            "content": {
                "plan_label": "Reference tensile validation",
                "validation_template_id": str(TEMPLATE),
                "validation_template_revision_id": str(TEMPLATE_REVISION),
                "material_model_id": str(MODEL),
                "material_model_revision_id": str(MODEL_REVISION),
                "solver_card_id": str(CARD),
                "solver_card_revision_id": str(CARD_REVISION),
                "experimental_selection_id": str(SELECTION),
                "experimental_selection_revision_id": str(SELECTION_REVISION),
            },
            "change_reason": "Pin reference validation inputs",
        },
    )
    assert plan.status_code == 201
    assert plan.json()["current_revision"]["content"]["runner_id"] == (
        "cmp.reference.inline-mock-runner"
    )

    submitted = _request(
        application,
        "POST",
        "/api/v1/validation-runs",
        json={
            "validation_plan_id": str(PLAN),
            "validation_plan_revision_id": str(PLAN_REVISION),
            "execution_mode": "reference_inline_mock",
            "change_reason": "Submit bounded reference validation run",
        },
    )
    assert submitted.status_code == 202
    assert submitted.json()["status"] == "queued"
    assert submitted.json()["result_manifest"] is None

    collected = _request(
        application,
        "POST",
        f"/api/v1/validation-runs/{RUN}:poll",
        json={"outcome": "succeeded", "change_reason": "Collect explicit mock success"},
    )
    assert collected.status_code == 200
    document = collected.json()
    assert document["status"] == "succeeded"
    assert document["result_manifest"]["solver_termination"] == "normal"
    assert document["result_manifest"]["native_result_state"] == "available"
    assert "verdict" not in document

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
from cmp.modules.identity_access.domain.security import Principal, PrincipalType, SecurityContext
from cmp.modules.modeling.adapters.api.voce_candidate_projection import (
    install_voce_candidate_projection_api,
)
from cmp.modules.modeling.application.service import RevisionSnapshot
from cmp.modules.modeling.application.tabulated_plasticity import TabulatedPlasticityModelSnapshot
from cmp.modules.modeling.application.voce_candidate_projection import (
    VOCE_CANDIDATE_SELECTION_AGGREGATE_TYPE,
    CreateVoceCandidateSelection,
    ProjectSelectedVoceCandidate,
    VoceCandidateProjectionService,
    VoceCandidateSelectionSnapshot,
)
from cmp.modules.modeling.domain.reference_voce_candidate_selection import (
    REFERENCE_VOCE_SELECTION_SCHEMA_ID,
    ReferenceVoceCandidateSelectionContent,
)
from cmp.modules.modeling.domain.reference_voce_tabulated_plasticity import (
    REFERENCE_VOCE_TABULATED_PLASTICITY_SCHEMA_ID,
    ReferenceVoceTabulatedPlasticityContent,
)
from cmp.shared.domain.revisions import RevisionRecord, TenantScope
from fastapi import FastAPI, Request

NOW = datetime(2026, 7, 15, tzinfo=UTC)
IDS = tuple(UUID(int=index) for index in range(1, 30))
ORG, PROJECT, ACTOR, RUN, CANDIDATE, SELECTION, SELECTION_REVISION = IDS[:7]
MODEL, MODEL_REVISION = IDS[7:9]
TRACE = "00-000000000000000000000000000000b1-00000000000000b1-01"
CONTEXT = SecurityContext(
    principal=Principal(ACTOR, PrincipalType.USER, "Modeler", True),
    organization_id=ORG,
    project_id=PROJECT,
    issuer="https://idp.invalid",
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


READ = _decision(Permission.MODELING_READ)
WRITE = _decision(Permission.MODELING_WRITE)


def _record(
    *, revision_id: UUID, aggregate_id: UUID, aggregate_type: str, schema_id: str
) -> RevisionRecord:
    return RevisionRecord(
        revision_id=revision_id,
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        scope=TenantScope(ORG, PROJECT, "internal"),
        revision_no=1,
        based_on_revision_id=None,
        schema_id=schema_id,
        schema_version="1.0.0",
        content_hash="a" * 64,
        created_at=NOW,
        created_by=ACTOR,
        change_reason="explicit selection",
        request_id=CONTEXT.request_id,
        trace_id=TRACE,
    )


def _selection() -> VoceCandidateSelectionSnapshot:
    content = ReferenceVoceCandidateSelectionContent(
        selection_label="Accepted Voce candidate",
        voce_calibration_run_id=RUN,
        voce_calibration_candidate_id=CANDIDATE,
        candidate_sha256="c" * 64,
        selection_reason="Best reviewed objective and residual plot",
    )
    return VoceCandidateSelectionSnapshot(
        SELECTION,
        RevisionSnapshot(
            _record(
                revision_id=SELECTION_REVISION,
                aggregate_id=SELECTION,
                aggregate_type=VOCE_CANDIDATE_SELECTION_AGGREGATE_TYPE,
                schema_id=REFERENCE_VOCE_SELECTION_SCHEMA_ID,
            ),
            content,
        ),
    )


def _model() -> TabulatedPlasticityModelSnapshot:
    values = IDS[9:26]
    content = ReferenceVoceTabulatedPlasticityContent(
        material_id=values[0],
        material_revision_id=values[1],
        material_state_id=values[2],
        material_state_revision_id=values[3],
        property_set_id=values[4],
        property_set_revision_id=values[5],
        calibration_input_scope_id=values[6],
        calibration_input_scope_revision_id=values[7],
        voce_calibration_plan_id=values[8],
        voce_calibration_plan_revision_id=values[9],
        voce_calibration_run_id=RUN,
        voce_calibration_candidate_id=CANDIDATE,
        voce_calibration_candidate_sha256="c" * 64,
        voce_candidate_selection_id=SELECTION,
        voce_candidate_selection_revision_id=SELECTION_REVISION,
        hardening_curve_artifact_id=values[10],
        hardening_curve_sha256="d" * 64,
        hardening_curve_point_count=52,
        sampling_point_count=51,
        density_kg_per_m3=7800,
        youngs_modulus_pa=210e9,
        poisson_ratio=0.3,
        initial_yield_stress_pa=301e6,
        q_pa=159e6,
        b=12.1,
        characterized_max_true_plastic_strain=0.18,
        extension_max_true_plastic_strain=0.5,
        post_necking_approximation_acknowledged=True,
    )
    record = _record(
        revision_id=MODEL_REVISION,
        aggregate_id=MODEL,
        aggregate_type="modeling.material_model",
        schema_id=REFERENCE_VOCE_TABULATED_PLASTICITY_SCHEMA_ID,
    )
    return TabulatedPlasticityModelSnapshot(
        MODEL, content.material_state_id, RevisionSnapshot(record, content)
    )


class _Service:
    def create_selection(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CreateVoceCandidateSelection,
    ) -> VoceCandidateSelectionSnapshot:
        assert context is CONTEXT and decision is WRITE
        assert command.voce_calibration_candidate_id == CANDIDATE
        return _selection()

    def get_selection(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        selection_id: UUID,
    ) -> VoceCandidateSelectionSnapshot:
        assert context is CONTEXT and decision is READ and selection_id == SELECTION
        return _selection()

    async def project(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        selection_id: UUID,
        command: ProjectSelectedVoceCandidate,
    ) -> TabulatedPlasticityModelSnapshot:
        assert context is CONTEXT and decision is WRITE and selection_id == SELECTION
        assert command.selection_revision_id == SELECTION_REVISION
        assert command.acknowledge_constant_extension
        return _model()


def _app() -> FastAPI:
    app = FastAPI()

    def security(request: Request) -> None:
        request.state.security_context = CONTEXT

    def read(request: Request) -> None:
        request.state.authorization_decision = READ

    def write(request: Request) -> None:
        request.state.authorization_decision = WRITE

    install_voce_candidate_projection_api(
        app,
        service=cast(VoceCandidateProjectionService, _Service()),
        security_dependency=security,
        read_dependency=read,
        write_dependency=write,
    )
    return app


def _request(method: str, path: str, body: dict[str, object] | None = None) -> httpx.Response:
    async def send() -> httpx.Response:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=_app()), base_url="http://test"
        ) as client:
            return await client.request(method, path, json=body)

    return asyncio.run(send())


def test_human_selection_projects_solver_neutral_voce_ir() -> None:
    created = _request(
        "POST",
        "/api/v1/voce-candidate-selections",
        {
            "classification": "internal",
            "selection_label": "Accepted Voce candidate",
            "voce_calibration_run_id": str(RUN),
            "voce_calibration_candidate_id": str(CANDIDATE),
            "selection_reason": "Best reviewed objective and residual plot",
        },
    )
    assert created.status_code == 201
    assert created.json()["current_revision"]["content"]["selection_decision"] == (
        "accepted_for_tabulated_ir_projection"
    )

    projected = _request(
        "POST",
        f"/api/v1/voce-candidate-selections/{SELECTION}/tabulated-plasticity-models",
        {
            "selection_revision_id": str(SELECTION_REVISION),
            "sampling_point_count": 51,
            "extension_max_true_plastic_strain": 0.5,
            "acknowledge_constant_extension": True,
            "change_reason": "Project accepted candidate without refitting",
        },
    )
    assert projected.status_code == 201
    body = projected.json()["current_revision"]
    assert body["content"]["calibration_projection"]["candidate_id"] == str(CANDIDATE)
    assert body["content"]["source_dataset_revision_id"] is None
    assert body["ir"]["semantics"]["solver_neutral"] is True

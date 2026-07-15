from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import cast
from uuid import UUID, uuid4

import httpx
from cmp.modules.exporting.adapters.api.linear_viscoelastic_solver_cards import (
    install_linear_viscoelastic_solver_card_api,
)
from cmp.modules.exporting.application.linear_viscoelastic_service import (
    CreateReferenceLinearViscoelasticSolverCard,
    LinearViscoelasticSolverCardService,
    LinearViscoelasticSolverCardSnapshot,
)
from cmp.modules.exporting.application.service import SOLVER_CARD_AGGREGATE_TYPE, RevisionSnapshot
from cmp.modules.exporting.domain.reference_linear_viscoelasticity import (
    LinearViscoelasticExportTarget,
    LinearViscoelasticMappingReport,
    build_reference_linear_viscoelastic_solver_card,
    preflight_reference_linear_viscoelastic_export,
)
from cmp.modules.identity_access.application.authorization import database_permissions_for
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
    Permission,
    Role,
)
from cmp.modules.identity_access.domain.security import Principal, PrincipalType, SecurityContext
from cmp.modules.modeling.application.linear_viscoelasticity import (
    LinearViscoelasticModelSnapshot,
)
from cmp.modules.modeling.application.service import MATERIAL_MODEL_AGGREGATE_TYPE
from cmp.modules.modeling.application.service import RevisionSnapshot as ModelRevisionSnapshot
from cmp.modules.modeling.domain.reference_linear_viscoelasticity import (
    BulkRelaxationStatus,
    PronyTerm,
    ReferenceLinearViscoelasticContent,
)
from cmp.shared.domain.revisions import RevisionRecord, TenantScope, content_sha256
from fastapi import FastAPI, Request

NOW = datetime(2026, 8, 7, 9, 0, tzinfo=UTC)
ORG, PROJECT, ACTOR, MODEL, MODEL_REVISION, CARD, CARD_REVISION = (
    UUID(int=value) for value in range(1, 8)
)
TRACE = "00-00000000000000000000000000000041-0000000000000041-01"


def _context() -> SecurityContext:
    return SecurityContext(
        principal=Principal(ACTOR, PrincipalType.USER, "Polymer modeler", True),
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


CONTENT = ReferenceLinearViscoelasticContent(
    material_id=UUID(int=10),
    material_revision_id=UUID(int=11),
    material_state_id=UUID(int=12),
    material_state_revision_id=UUID(int=13),
    property_set_id=UUID(int=14),
    property_set_revision_id=UUID(int=15),
    density_kg_per_m3=1_200.0,
    youngs_modulus_pa=3_000_000_000.0,
    poisson_ratio=0.35,
    bulk_relaxation_status=BulkRelaxationStatus.NOT_CHARACTERIZED,
    terms=(PronyTerm(0.2, 0.0, 0.1), PronyTerm(0.3, 0.0, 10.0)),
)


def _record(revision: UUID, aggregate_type: str, aggregate: UUID, schema_id: str) -> RevisionRecord:
    return RevisionRecord(
        revision_id=revision,
        aggregate_type=aggregate_type,
        aggregate_id=aggregate,
        scope=TenantScope(ORG, PROJECT, "internal"),
        revision_no=1,
        based_on_revision_id=None,
        schema_id=schema_id,
        schema_version="1.0.0",
        content_hash=content_sha256({"revision": str(revision)}),
        created_at=NOW,
        created_by=ACTOR,
        change_reason="integration fixture",
        request_id=CONTEXT.request_id,
        trace_id=TRACE,
    )


MODEL_SNAPSHOT = LinearViscoelasticModelSnapshot(
    MODEL,
    CONTENT.material_state_id,
    ModelRevisionSnapshot(
        _record(
            MODEL_REVISION,
            MATERIAL_MODEL_AGGREGATE_TYPE,
            MODEL,
            "urn:cmp:modeling:reference-isotropic-linear-viscoelastic-prony:1.0.0",
        ),
        CONTENT,
    ),
)


class _Service:
    def __init__(self) -> None:
        self.card: LinearViscoelasticSolverCardSnapshot | None = None

    def preflight(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        *,
        material_model_id: UUID,
        material_model_revision_id: UUID,
        target: LinearViscoelasticExportTarget,
    ) -> LinearViscoelasticMappingReport:
        del context, decision
        return preflight_reference_linear_viscoelastic_export(
            material_model_id=material_model_id,
            material_model_revision_id=material_model_revision_id,
            source=CONTENT,
            target=target,
        )

    def create_card(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CreateReferenceLinearViscoelasticSolverCard,
    ) -> tuple[LinearViscoelasticSolverCardSnapshot, LinearViscoelasticMappingReport]:
        del context, decision
        report, content = build_reference_linear_viscoelastic_solver_card(
            material_model_id=command.material_model_id,
            material_model_revision_id=command.material_model_revision_id,
            source=CONTENT,
            target=command.target,
            expected_mapping_report_sha256=command.expected_mapping_report_sha256,
            solver_material_id=command.solver_material_id,
            material_name=command.material_name,
        )
        self.card = LinearViscoelasticSolverCardSnapshot(
            CARD,
            MODEL,
            command.target,
            command.solver_material_id,
            command.material_name,
            RevisionSnapshot(
                _record(
                    CARD_REVISION,
                    SOLVER_CARD_AGGREGATE_TYPE,
                    CARD,
                    "urn:cmp:exporting:reference-linear-viscoelastic-prony-card:1.0.0",
                ),
                content,
            ),
        )
        return self.card, report

    def get_card(
        self, context: SecurityContext, decision: AuthorizationDecision, solver_card_id: UUID
    ) -> LinearViscoelasticSolverCardSnapshot:
        del context, decision
        assert solver_card_id == CARD and self.card is not None
        return self.card

    def list_cards_for_model(
        self, context: SecurityContext, decision: AuthorizationDecision, material_model_id: UUID
    ) -> tuple[LinearViscoelasticSolverCardSnapshot, ...]:
        del context, decision
        assert material_model_id == MODEL
        return () if self.card is None else (self.card,)


def _application() -> FastAPI:
    application = FastAPI()
    service = _Service()

    def security(request: Request) -> None:
        request.state.security_context = CONTEXT

    def read(request: Request) -> None:
        request.state.authorization_decision = _decision(Permission.EXPORT_READ)

    def execute(request: Request) -> None:
        request.state.authorization_decision = _decision(Permission.EXPORT_EXECUTE)

    install_linear_viscoelastic_solver_card_api(
        application,
        service=cast(LinearViscoelasticSolverCardService, service),
        security_dependency=security,
        read_dependency=read,
        execute_dependency=execute,
    )
    return application


def _request(
    app: FastAPI,
    method: str,
    path: str,
    json: dict[str, object] | None = None,
) -> httpx.Response:
    async def send() -> httpx.Response:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            return await client.request(method, path, json=json)

    return asyncio.run(send())


def test_prony_ir_to_abaqus_preview_and_download() -> None:
    app = _application()
    target = {"solver": "abaqus", "version": "2025", "unit_system": "kg_m_s"}
    preflight = _request(
        app,
        "POST",
        f"/api/v1/linear-viscoelastic-models/{MODEL}/mapping-preflight",
        {"material_model_revision_id": str(MODEL_REVISION), "target": target},
    )
    assert preflight.status_code == 200
    report = preflight.json()
    assert report["exportable"] is True
    assert next(item for item in report["items"] if item["name"] == "bulk_relaxation")[
        "status"
    ] == "not_applicable"

    created = _request(
        app,
        "POST",
        f"/api/v1/linear-viscoelastic-models/{MODEL}/solver-cards",
        {
            "material_model_revision_id": str(MODEL_REVISION),
            "target": target,
            "expected_mapping_report_sha256": report["mapping_report_sha256"],
            "solver_material_id": 201,
            "material_name": "POLYMER_REFERENCE",
            "change_reason": "generate Abaqus Prony reference card",
        },
    )
    assert created.status_code == 201
    assert created.json()["card"]["current_revision"]["content"]["terms"][1][
        "relaxation_time_s"
    ] == 10.0

    preview = _request(app, "GET", f"/api/v1/linear-viscoelastic-solver-cards/{CARD}/preview")
    assert preview.status_code == 200
    assert "*VISCOELASTIC, TIME=PRONY, TYPE=ISOTROPIC" in preview.text

    download = _request(app, "GET", f"/api/v1/linear-viscoelastic-solver-cards/{CARD}/download")
    assert download.status_code == 200
    assert download.headers["content-disposition"].endswith('.inp"')
    assert download.headers["x-cmp-card-sha256"]

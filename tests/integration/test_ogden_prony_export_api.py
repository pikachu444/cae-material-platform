from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import cast
from uuid import UUID, uuid4

import httpx
import pytest
from cmp.modules.exporting.adapters.api.ogden_prony_solver_cards import (
    install_ogden_prony_solver_card_api,
)
from cmp.modules.exporting.application.ogden_prony_service import (
    CreateReferenceOgdenPronySolverCard,
    OgdenPronySolverCardService,
    OgdenPronySolverCardSnapshot,
)
from cmp.modules.exporting.application.service import SOLVER_CARD_AGGREGATE_TYPE, RevisionSnapshot
from cmp.modules.exporting.domain.reference_ogden_prony import (
    OgdenPronyExportTarget,
    OgdenPronyMappingReport,
    build_reference_ogden_prony_solver_card,
    preflight_reference_ogden_prony_export,
)
from cmp.modules.identity_access.application.authorization import database_permissions_for
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
    Permission,
    Role,
)
from cmp.modules.identity_access.domain.security import Principal, PrincipalType, SecurityContext
from cmp.modules.modeling.domain.reference_ogden_prony import (
    ReferenceOgdenPronyContent,
    ReferenceOgdenTerm,
    ReferenceShearPronyTerm,
)
from cmp.shared.domain.revisions import RevisionRecord, TenantScope, content_sha256
from fastapi import FastAPI, Request

NOW = datetime(2026, 8, 13, 9, 0, tzinfo=UTC)
ORG, PROJECT, ACTOR, MODEL, MODEL_REVISION = (UUID(int=value) for value in range(1, 6))
TRACE = "00-00000000000000000000000000000047-0000000000000047-01"


def _context() -> SecurityContext:
    return SecurityContext(
        principal=Principal(ACTOR, PrincipalType.USER, "Elastomer modeler", True),
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
CONTENT = ReferenceOgdenPronyContent(
    material_id=UUID(int=10),
    material_revision_id=UUID(int=11),
    material_state_id=UUID(int=12),
    material_state_revision_id=UUID(int=13),
    property_set_id=UUID(int=14),
    property_set_revision_id=UUID(int=15),
    density_kg_per_m3=1_100.0,
    catalog_youngs_modulus_pa=3_000_000.0,
    catalog_poisson_ratio=0.49,
    ogden_term=ReferenceOgdenTerm(1_200_000.0, 2.4),
    prony_terms=(
        ReferenceShearPronyTerm(0.2, 0.1),
        ReferenceShearPronyTerm(0.3, 10.0),
    ),
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


def _record(revision: UUID, card: UUID) -> RevisionRecord:
    return RevisionRecord(
        revision_id=revision,
        aggregate_type=SOLVER_CARD_AGGREGATE_TYPE,
        aggregate_id=card,
        scope=TenantScope(ORG, PROJECT, "internal"),
        revision_no=1,
        based_on_revision_id=None,
        schema_id="urn:cmp:exporting:reference-ogden-prony-card:1.0.0",
        schema_version="1.0.0",
        content_hash=content_sha256({"revision": str(revision)}),
        created_at=NOW,
        created_by=ACTOR,
        change_reason="integration fixture",
        request_id=CONTEXT.request_id,
        trace_id=TRACE,
    )


class _Service:
    def __init__(self) -> None:
        self.cards: dict[UUID, OgdenPronySolverCardSnapshot] = {}

    def preflight(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        *,
        material_model_id: UUID,
        material_model_revision_id: UUID,
        target: OgdenPronyExportTarget,
    ) -> OgdenPronyMappingReport:
        del context, decision
        return preflight_reference_ogden_prony_export(
            material_model_id=material_model_id,
            material_model_revision_id=material_model_revision_id,
            source=CONTENT,
            target=target,
        )

    def create_card(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CreateReferenceOgdenPronySolverCard,
    ) -> tuple[OgdenPronySolverCardSnapshot, OgdenPronyMappingReport]:
        del context, decision
        report, content = build_reference_ogden_prony_solver_card(
            material_model_id=command.material_model_id,
            material_model_revision_id=command.material_model_revision_id,
            source=CONTENT,
            target=command.target,
            expected_mapping_report_sha256=command.expected_mapping_report_sha256,
            solver_material_id=command.solver_material_id,
            material_name=command.material_name,
        )
        card_id, revision_id = uuid4(), uuid4()
        snapshot = OgdenPronySolverCardSnapshot(
            card_id,
            MODEL,
            command.target,
            command.solver_material_id,
            command.material_name,
            RevisionSnapshot(_record(revision_id, card_id), content),
        )
        self.cards[card_id] = snapshot
        return snapshot, report

    def get_card(
        self, context: SecurityContext, decision: AuthorizationDecision, solver_card_id: UUID
    ) -> OgdenPronySolverCardSnapshot:
        del context, decision
        return self.cards[solver_card_id]

    def list_cards_for_model(
        self, context: SecurityContext, decision: AuthorizationDecision, material_model_id: UUID
    ) -> tuple[OgdenPronySolverCardSnapshot, ...]:
        del context, decision
        assert material_model_id == MODEL
        return tuple(self.cards.values())


def _application() -> FastAPI:
    application = FastAPI()
    service = _Service()

    def security(request: Request) -> None:
        request.state.security_context = CONTEXT

    def read(request: Request) -> None:
        request.state.authorization_decision = _decision(Permission.EXPORT_READ)

    def execute(request: Request) -> None:
        request.state.authorization_decision = _decision(Permission.EXPORT_EXECUTE)

    install_ogden_prony_solver_card_api(
        application,
        service=cast(OgdenPronySolverCardService, service),
        security_dependency=security,
        read_dependency=read,
        execute_dependency=execute,
    )
    return application


def _request(
    app: FastAPI, method: str, path: str, json: dict[str, object] | None = None
) -> httpx.Response:
    async def send() -> httpx.Response:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            return await client.request(method, path, json=json)

    return asyncio.run(send())


@pytest.mark.parametrize(
    ("solver", "volumetric", "keyword", "suffix"),
    [
        ("abaqus", "exact", "*HYPERELASTIC", '.inp"'),
        ("openradioss", "approximated", "/MAT/LAW62/301/1", '.rad"'),
    ],
)
def test_ogden_prony_preflight_preview_and_download(
    solver: str, volumetric: str, keyword: str, suffix: str
) -> None:
    app = _application()
    target = {"solver": solver, "version": "2025", "unit_system": "kg_m_s"}
    preflight = _request(
        app,
        "POST",
        f"/api/v1/ogden-prony-models/{MODEL}/solver-card-preflight",
        {"material_model_revision_id": str(MODEL_REVISION), "target": target},
    )
    assert preflight.status_code == 200
    report = preflight.json()
    item = next(item for item in report["report"]["items"] if item["name"] == "volumetric_response")
    assert item["status"] == volumetric

    created = _request(
        app,
        "POST",
        f"/api/v1/ogden-prony-models/{MODEL}/solver-cards",
        {
            "material_model_revision_id": str(MODEL_REVISION),
            "target": target,
            "expected_mapping_report_sha256": report["mapping_report_sha256"],
            "solver_material_id": 301,
            "material_name": "ELASTOMER_REFERENCE",
            "change_reason": "generate reference card",
        },
    )
    assert created.status_code == 201
    card_id = created.json()["solver_card_id"]
    preview = _request(app, "GET", f"/api/v1/ogden-prony-solver-cards/{card_id}/preview")
    assert keyword in preview.text
    download = _request(app, "GET", f"/api/v1/ogden-prony-solver-cards/{card_id}/download")
    assert download.headers["content-disposition"].endswith(suffix)
    assert download.headers["x-cmp-card-sha256"] == created.json()["current_revision"]["content"][
        "card_sha256"
    ]

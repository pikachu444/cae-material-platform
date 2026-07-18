from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import cast
from uuid import UUID, uuid4

import httpx
from cmp.modules.exporting.adapters.api.neutral_hyperelastic_solver_cards import (
    install_neutral_hyperelastic_solver_card_api,
)
from cmp.modules.exporting.application.neutral_hyperelastic_service import (
    CreateNeutralHyperelasticSolverCard,
    NeutralHyperelasticSolverCardService,
    NeutralHyperelasticSolverCardSnapshot,
)
from cmp.modules.exporting.application.service import RevisionSnapshot
from cmp.modules.exporting.domain.neutral_hyperelastic import (
    ABAQUS_DOCUMENTATION,
    ABAQUS_EXPORTER_ID,
    NeutralHyperelasticExportTarget,
    NeutralHyperelasticMappingItem,
    NeutralHyperelasticMappingReport,
    NeutralHyperelasticSolverCardContent,
)
from cmp.modules.identity_access.application.authorization import database_permissions_for
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
    Permission,
    Role,
)
from cmp.modules.identity_access.domain.security import Principal, PrincipalType, SecurityContext
from cmp.modules.modeling.domain.hyperelastic_families import HyperelasticFamily
from cmp.modules.modeling.domain.neutral_material import NeutralHyperelasticParameters
from cmp.shared.domain.revisions import RevisionRecord, TenantScope
from fastapi import FastAPI, Request

NOW = datetime(2026, 7, 18, tzinfo=UTC)
IDS = tuple(UUID(int=value) for value in range(1, 12))
ORG, PROJECT, ACTOR, NEUTRAL, NEUTRAL_REVISION, CARD, CARD_REVISION = IDS[:7]
TRACE = "00-000000000000000000000000000000e1-00000000000000e1-01"
CONTEXT = SecurityContext(
    principal=Principal(ACTOR, PrincipalType.USER, "Exporter", True),
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
TARGET = NeutralHyperelasticExportTarget("abaqus", "2025", "kg_m_s")
ITEMS = (
    NeutralHyperelasticMappingItem(
        "density", "/material_model_ir/density", "density", "exact", "SI density."
    ),
)
REPORT = NeutralHyperelasticMappingReport(
    NEUTRAL,
    NEUTRAL_REVISION,
    "a" * 64,
    HyperelasticFamily.NEO_HOOKEAN,
    TARGET,
    ITEMS,
    ABAQUS_EXPORTER_ID,
    "1.0.0",
    "b" * 64,
    ABAQUS_DOCUMENTATION,
)
CONTENT = NeutralHyperelasticSolverCardContent(
    NEUTRAL,
    NEUTRAL_REVISION,
    "a" * 64,
    HyperelasticFamily.NEO_HOOKEAN,
    TARGET,
    301,
    "ELASTOMER_REFERENCE",
    1100.0,
    NeutralHyperelasticParameters(HyperelasticFamily.NEO_HOOKEAN, c10_pa=1_000_000.0),
    0.0,
    0.2,
    (("density", "exact"),),
    REPORT.digest,
    "*MATERIAL, NAME=ELASTOMER_REFERENCE\n*HYPERELASTIC, NEO HOOKE\n",
    "c" * 64,
    ABAQUS_EXPORTER_ID,
    "1.0.0",
    "b" * 64,
)
SNAPSHOT = NeutralHyperelasticSolverCardSnapshot(
    CARD,
    NEUTRAL,
    TARGET,
    301,
    "ELASTOMER_REFERENCE",
    RevisionSnapshot(
        RevisionRecord(
            CARD_REVISION,
            "exporting.neutral_solver_card",
            CARD,
            TenantScope(ORG, PROJECT, "internal"),
            1,
            None,
            "urn:cmp:exporting:neutral-hyperelastic-card:1.0.0",
            "1.0.0",
            "d" * 64,
            NOW,
            ACTOR,
            "Create reviewed solver card.",
            CONTEXT.request_id,
            TRACE,
        ),
        CONTENT,
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


class _Service:
    async def preflight(self, *args: object, **kwargs: object) -> NeutralHyperelasticMappingReport:
        assert kwargs["neutral_material_id"] == NEUTRAL
        assert kwargs["neutral_material_revision_id"] == NEUTRAL_REVISION
        return REPORT

    async def create_card(
        self, context: SecurityContext, decision: AuthorizationDecision, command: object
    ) -> tuple[NeutralHyperelasticSolverCardSnapshot, NeutralHyperelasticMappingReport]:
        assert context is CONTEXT and decision.permission is Permission.EXPORT_EXECUTE
        assert (
            cast(CreateNeutralHyperelasticSolverCard, command).expected_mapping_report_sha256
            == REPORT.digest
        )
        return SNAPSHOT, REPORT

    def get_card(self, *args: object, **kwargs: object) -> NeutralHyperelasticSolverCardSnapshot:
        return SNAPSHOT

    def list_cards(
        self, *args: object, **kwargs: object
    ) -> tuple[NeutralHyperelasticSolverCardSnapshot, ...]:
        return (SNAPSHOT,)

    async def mapping_report(
        self, *args: object, **kwargs: object
    ) -> NeutralHyperelasticMappingReport:
        return REPORT


def _app() -> FastAPI:
    app = FastAPI()

    def security(request: Request) -> None:
        request.state.security_context = CONTEXT

    def read(request: Request) -> None:
        request.state.authorization_decision = _decision(Permission.EXPORT_READ)

    def execute(request: Request) -> None:
        request.state.authorization_decision = _decision(Permission.EXPORT_EXECUTE)

    install_neutral_hyperelastic_solver_card_api(
        app,
        service=cast(NeutralHyperelasticSolverCardService, _Service()),
        security_dependency=security,
        read_dependency=read,
        execute_dependency=execute,
    )
    return app


async def _exercise() -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=_app()), base_url="http://test"
    ) as client:
        capabilities = await client.get("/api/v1/neutral-hyperelastic-export-capabilities")
        assert capabilities.status_code == 200
        assert len(capabilities.json()["capabilities"]) == 8
        neutral_capabilities = await client.get(
            "/api/v1/neutral-solver-export-capabilities"
        )
        assert neutral_capabilities.status_code == 200
        assert set(neutral_capabilities.json()["families"]) == {
            "isotropic_tabulated_plasticity",
            "generalized_maxwell",
            "hyperelastic",
            "hyperelastic_prony_overlay",
        }
        assert neutral_capabilities.json()["families"]["generalized_maxwell"][
            "openradioss"
        ] == "conditional_nearly_incompressible_shear_only"

        preflight = await client.post(
            f"/api/v1/neutral-materials/{NEUTRAL}/solver-card-preflight",
            json={
                "neutral_material_revision_id": str(NEUTRAL_REVISION),
                "target": {"solver": "abaqus", "version": "2025", "unit_system": "kg_m_s"},
            },
        )
        assert preflight.status_code == 200
        assert preflight.json()["mapping_report_sha256"] == REPORT.digest

        created = await client.post(
            f"/api/v1/neutral-materials/{NEUTRAL}/solver-cards",
            json={
                "neutral_material_revision_id": str(NEUTRAL_REVISION),
                "target": {"solver": "abaqus", "version": "2025", "unit_system": "kg_m_s"},
                "expected_mapping_report_sha256": REPORT.digest,
                "solver_material_id": 301,
                "material_name": "ELASTOMER_REFERENCE",
                "change_reason": "Create reviewed solver card.",
            },
        )
        assert created.status_code == 201
        assert created.json()["current_revision"]["content"]["family"] == "neo_hookean"

        report = await client.get(
            f"/api/v1/neutral-hyperelastic-solver-cards/{CARD}/mapping-report"
        )
        assert report.status_code == 200
        assert report.json()["mapping_report_sha256"] == REPORT.digest

        preview = await client.get(f"/api/v1/neutral-hyperelastic-solver-cards/{CARD}/preview")
        assert preview.status_code == 200
        assert "*HYPERELASTIC" in preview.text

        downloaded = await client.get(f"/api/v1/neutral-hyperelastic-solver-cards/{CARD}/download")
        assert downloaded.status_code == 200
        assert downloaded.headers["x-cmp-mapping-report-sha256"] == REPORT.digest
        assert downloaded.headers["content-disposition"].endswith('.inp"')

        generic_report = await client.get(
            f"/api/v1/neutral-solver-cards/{CARD}/mapping-report"
        )
        generic_preview = await client.get(f"/api/v1/neutral-solver-cards/{CARD}/preview")
        generic_download = await client.get(f"/api/v1/neutral-solver-cards/{CARD}/download")
        assert generic_report.json() == report.json()
        assert generic_preview.content == preview.content
        assert generic_download.content == downloaded.content


def test_neutral_hyperelastic_solver_card_api_exposes_preflight_sidecar_and_native_card() -> None:
    asyncio.run(_exercise())

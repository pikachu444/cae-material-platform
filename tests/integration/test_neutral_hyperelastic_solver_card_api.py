from __future__ import annotations

import asyncio
from dataclasses import replace
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
    NeutralHyperelasticSolverCardNotFound,
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
CARD_REVISION_2 = UUID(int=12)
OTHER_CARD = UUID(int=13)
OTHER_CARD_REVISION = UUID(int=14)
R2_CARD_HASH = "e" * 64
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
REPORT_R2 = NeutralHyperelasticMappingReport(
    NEUTRAL,
    NEUTRAL_REVISION,
    "a" * 64,
    HyperelasticFamily.NEO_HOOKEAN,
    TARGET,
    (
        NeutralHyperelasticMappingItem(
            "density",
            "/material_model_ir/density",
            "density",
            "transformed",
            "Updated density mapping.",
        ),
    ),
    ABAQUS_EXPORTER_ID,
    "1.0.0",
    "c" * 64,
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
    def __init__(self) -> None:
        self.current = SNAPSHOT
        self.revisions = {CARD_REVISION: SNAPSHOT.current}
        self.reports = {CARD_REVISION: REPORT}
        self.revisions[OTHER_CARD_REVISION] = replace(
            SNAPSHOT.current,
            record=replace(
                SNAPSHOT.current.record,
                revision_id=OTHER_CARD_REVISION,
                aggregate_id=OTHER_CARD,
            ),
        )

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
        self.current = SNAPSHOT
        self.revisions[CARD_REVISION] = SNAPSHOT.current
        return self.current, REPORT

    def advance_current(self) -> None:
        content = replace(
            self.current.current.content,
            material_name="ELASTOMER_REFERENCE_R2",
            density_kg_per_m3=1125.0,
            mapping_report_sha256=REPORT_R2.digest,
            card_text="*MATERIAL, NAME=ELASTOMER_REFERENCE_R2\n*HYPERELASTIC, NEO HOOKE\n",
            card_sha256=R2_CARD_HASH,
        )
        current = replace(
            self.current.current.record,
            revision_id=CARD_REVISION_2,
            revision_no=2,
            content_hash="f" * 64,
            based_on_revision_id=CARD_REVISION,
        )
        self.current = replace(
            self.current,
            material_name="ELASTOMER_REFERENCE_R2",
            current=replace(self.current.current, record=current, content=content),
        )
        self.revisions[CARD_REVISION_2] = self.current.current
        self.reports[CARD_REVISION_2] = REPORT_R2

    def get_card(self, *args: object, **kwargs: object) -> NeutralHyperelasticSolverCardSnapshot:
        return self.current

    def get_card_revision(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        solver_card_id: UUID,
        solver_card_revision_id: UUID,
    ) -> NeutralHyperelasticSolverCardSnapshot:
        del context, decision
        value = self.revisions.get(solver_card_revision_id)
        if value is None or value.record.aggregate_id != solver_card_id:
            raise NeutralHyperelasticSolverCardNotFound("solver card revision is not visible")
        return replace(self.current, current=value)

    def list_cards(
        self, *args: object, **kwargs: object
    ) -> tuple[NeutralHyperelasticSolverCardSnapshot, ...]:
        return (self.current,)

    async def mapping_report(
        self, *args: object, **kwargs: object
    ) -> NeutralHyperelasticMappingReport:
        revision_id = args[3] if len(args) > 3 else None
        if revision_id is None:
            return self.reports[self.current.current.record.revision_id]
        return self.reports[cast(UUID, revision_id)]


def _app() -> FastAPI:
    app = FastAPI()
    service = _Service()
    app.state.neutral_service = service

    def security(request: Request) -> None:
        request.state.security_context = CONTEXT

    def read(request: Request) -> None:
        request.state.authorization_decision = _decision(Permission.EXPORT_READ)

    def execute(request: Request) -> None:
        request.state.authorization_decision = _decision(Permission.EXPORT_EXECUTE)

    install_neutral_hyperelastic_solver_card_api(
        app,
        service=cast(NeutralHyperelasticSolverCardService, service),
        security_dependency=security,
        read_dependency=read,
        execute_dependency=execute,
    )
    return app


async def _exercise() -> None:
    app = _app()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
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

        service = cast(_Service, app.state.neutral_service)
        service.advance_current()
        exact = await client.get(
            f"/api/v1/neutral-solver-cards/{CARD}?revision_id={CARD_REVISION}"
        )
        current = await client.get(f"/api/v1/neutral-solver-cards/{CARD}")
        exact_report = await client.get(
            f"/api/v1/neutral-solver-cards/{CARD}/mapping-report?revision_id={CARD_REVISION}"
        )
        exact_preview = await client.get(
            f"/api/v1/neutral-solver-cards/{CARD}/preview?revision_id={CARD_REVISION}"
        )
        exact_download = await client.get(
            f"/api/v1/neutral-solver-cards/{CARD}/download?revision_id={CARD_REVISION}"
        )
        assert exact.status_code == 200
        assert exact.json()["current_revision"]["id"] == str(CARD_REVISION)
        assert current.status_code == 200
        assert current.json()["current_revision"]["id"] == str(CARD_REVISION_2)
        assert (
            current.json()["current_revision"]["content"]["material_name"]
            == "ELASTOMER_REFERENCE_R2"
        )
        assert (
            current.json()["current_revision"]["content"]["density_kg_per_m3"]
            != exact.json()["current_revision"]["content"]["density_kg_per_m3"]
        )
        assert current.json()["current_revision"]["content"]["card_sha256"] == R2_CARD_HASH
        assert (
            current.json()["current_revision"]["content"]["mapping_report_sha256"]
            == REPORT_R2.digest
        )
        assert current.json()["links"]["self"] == f"/api/v1/neutral-solver-cards/{CARD}"
        assert exact.json()["links"]["self"] == (
            f"/api/v1/neutral-solver-cards/{CARD}?revision_id={CARD_REVISION}"
        )
        assert exact.json()["links"]["mapping_report"].endswith(
            f"/mapping-report?revision_id={CARD_REVISION}"
        )
        assert exact.json()["links"]["preview"].endswith(f"/preview?revision_id={CARD_REVISION}")
        assert exact.json()["links"]["download"].endswith(f"/download?revision_id={CARD_REVISION}")
        assert exact_report.status_code == 200
        assert exact_report.json()["mapping_report_sha256"] == REPORT.digest
        assert exact_preview.content == preview.content
        assert exact_download.content == downloaded.content
        current_report = await client.get(f"/api/v1/neutral-solver-cards/{CARD}/mapping-report")
        assert current_report.json()["mapping_report_sha256"] == REPORT_R2.digest
        assert current_report.json() != exact_report.json()
        for revision_id in (UUID(int=99), OTHER_CARD_REVISION):
            missing = await client.get(
                f"/api/v1/neutral-solver-cards/{CARD}?revision_id={revision_id}"
            )
            assert missing.status_code == 404


def test_neutral_hyperelastic_solver_card_api_exposes_preflight_sidecar_and_native_card() -> None:
    asyncio.run(_exercise())

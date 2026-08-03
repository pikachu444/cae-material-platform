from __future__ import annotations

import asyncio
import hashlib
from dataclasses import replace
from datetime import UTC, datetime
from typing import cast
from uuid import UUID, uuid4

import httpx
from cmp.modules.exporting.adapters.api.solver_cards import install_solver_card_api
from cmp.modules.exporting.application.service import (
    SOLVER_CARD_AGGREGATE_TYPE,
    CreateReferenceOpenRadiossCard,
    RevisionSnapshot,
    SolverCardService,
    SolverCardSnapshot,
)
from cmp.modules.exporting.domain.openradioss_elast import (
    ExportTarget,
    ReferenceMappingReport,
    ReferenceOpenRadiossCardContent,
    SolverCardNotFound,
    build_reference_openradioss_card,
    preflight_reference_openradioss_elast,
    render_reference_openradioss_elast_card,
)
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
from cmp.modules.modeling.domain.reference_linear_elasticity import (
    ReferenceLinearElasticContent,
)
from cmp.shared.domain.revisions import RevisionRecord, TenantScope
from fastapi import FastAPI, Request

NOW = datetime(2026, 7, 14, 10, 0, tzinfo=UTC)
ORG = UUID("e2000000-0000-4000-8000-000000000001")
PROJECT = UUID("e2000000-0000-4000-8000-000000000002")
ACTOR = UUID("e2000000-0000-4000-8000-000000000003")
MATERIAL = UUID("e2000000-0000-4000-8000-000000000004")
MATERIAL_REVISION = UUID("e2000000-0000-4000-8000-000000000005")
STATE = UUID("e2000000-0000-4000-8000-000000000006")
STATE_REVISION = UUID("e2000000-0000-4000-8000-000000000007")
PROPERTY_SET = UUID("e2000000-0000-4000-8000-000000000008")
PROPERTY_SET_REVISION = UUID("e2000000-0000-4000-8000-000000000009")
MODEL = UUID("e2000000-0000-4000-8000-00000000000a")
MODEL_REVISION = UUID("e2000000-0000-4000-8000-00000000000b")
CARD = UUID("e2000000-0000-4000-8000-00000000000c")
CARD_REVISION = UUID("e2000000-0000-4000-8000-00000000000d")
CARD_REVISION_2 = UUID("e2000000-0000-4000-8000-00000000000e")
OTHER_CARD = UUID("e2000000-0000-4000-8000-00000000000f")
OTHER_CARD_REVISION = UUID("e2000000-0000-4000-8000-000000000010")
CARD_R2_CONTENT_HASH = "f" * 64
TRACE = "00-000000000000000000000000000000e2-00000000000000e2-01"
TARGET = ExportTarget("openradioss", "2025", "kg_m_s")


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


READ = _decision(Permission.EXPORT_READ)
EXECUTE = _decision(Permission.EXPORT_EXECUTE)


def _source() -> ReferenceLinearElasticContent:
    return ReferenceLinearElasticContent(
        material_id=MATERIAL,
        material_revision_id=MATERIAL_REVISION,
        material_state_id=STATE,
        material_state_revision_id=STATE_REVISION,
        property_set_id=PROPERTY_SET,
        property_set_revision_id=PROPERTY_SET_REVISION,
        density_kg_per_m3=7850.0,
        youngs_modulus_pa=210_000_000_000.0,
        poisson_ratio=0.3,
        source_yield_stress_pa=355_000_000.0,
    )


def _record(
    revision_id: UUID = CARD_REVISION,
    revision_no: int = 1,
    content_hash: str = "e" * 64,
    aggregate_id: UUID = CARD,
    based_on_revision_id: UUID | None = None,
) -> RevisionRecord:
    return RevisionRecord(
        revision_id=revision_id,
        aggregate_type=SOLVER_CARD_AGGREGATE_TYPE,
        aggregate_id=aggregate_id,
        scope=TenantScope(ORG, PROJECT, DataClassification.INTERNAL.value),
        revision_no=revision_no,
        based_on_revision_id=based_on_revision_id,
        schema_id="urn:cmp:exporting:reference-openradioss-elast:1.0.0",
        schema_version="1.0.0",
        content_hash=content_hash,
        created_at=NOW,
        created_by=ACTOR,
        change_reason="export reference card",
        request_id=CONTEXT.request_id,
        trace_id=TRACE,
    )


class _SolverCardService:
    def __init__(self) -> None:
        self.snapshot: SolverCardSnapshot | None = None
        self.revisions: dict[UUID, RevisionSnapshot[ReferenceOpenRadiossCardContent]] = {}

    def preflight_reference_openradioss(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_model_id: UUID,
        target: ExportTarget,
    ) -> ReferenceMappingReport:
        del context
        assert decision is READ
        assert material_model_id == MODEL
        return preflight_reference_openradioss_elast(
            material_model_id=MODEL,
            material_model_revision_id=MODEL_REVISION,
            content=_source(),
            target=target,
        )

    def create_reference_openradioss_card(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CreateReferenceOpenRadiossCard,
    ) -> tuple[SolverCardSnapshot, ReferenceMappingReport]:
        del context
        assert decision is EXECUTE
        assert command.material_model_id == MODEL
        assert command.material_model_revision_id == MODEL_REVISION
        report, content = build_reference_openradioss_card(
            material_model_id=MODEL,
            material_model_revision_id=MODEL_REVISION,
            source=_source(),
            target=command.target,
            expected_mapping_report_sha256=command.expected_mapping_report_sha256,
            solver_material_id=command.solver_material_id,
            card_title=command.card_title,
        )
        self.snapshot = SolverCardSnapshot(
            CARD,
            MODEL,
            TARGET,
            command.solver_material_id,
            RevisionSnapshot(_record(), content),
        )
        self.revisions[CARD_REVISION] = self.snapshot.current
        self.revisions[OTHER_CARD_REVISION] = RevisionSnapshot(
            _record(
                revision_id=OTHER_CARD_REVISION,
                aggregate_id=OTHER_CARD,
            ),
            content,
        )
        return self.snapshot, report

    def advance_current(self) -> None:
        assert self.snapshot is not None
        previous = self.snapshot.current
        source_r2 = replace(
            _source(),
            source_yield_stress_pa=650_000_000.0,
            applicable_temperature_min_k=273.15,
        )
        report_r2 = preflight_reference_openradioss_elast(
            material_model_id=MODEL,
            material_model_revision_id=MODEL_REVISION,
            content=source_r2,
            target=TARGET,
        )
        card_text_r2 = render_reference_openradioss_elast_card(
            material_model_id=MODEL,
            material_model_revision_id=MODEL_REVISION,
            report=report_r2,
            solver_material_id=previous.content.solver_material_id,
            card_title="Reference steel revision 2",
            density_kg_per_m3=previous.content.density_kg_per_m3,
            youngs_modulus_pa=previous.content.youngs_modulus_pa,
            poisson_ratio=previous.content.poisson_ratio,
        )
        content = replace(
            previous.content,
            card_title="Reference steel revision 2",
            source_yield_stress_pa=650_000_000.0,
            applicable_temperature_min_k=273.15,
            mapping_report_sha256=report_r2.digest,
            card_text=card_text_r2,
            card_sha256=hashlib.sha256(card_text_r2.encode("utf-8")).hexdigest(),
        )
        current = RevisionSnapshot(
            _record(
                revision_id=CARD_REVISION_2,
                revision_no=2,
                content_hash=CARD_R2_CONTENT_HASH,
                based_on_revision_id=previous.record.revision_id,
            ),
            content,
        )
        self.revisions[CARD_REVISION_2] = current
        self.snapshot = replace(self.snapshot, current=current)

    def get_solver_card(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        solver_card_id: UUID,
    ) -> SolverCardSnapshot:
        del context
        assert decision is READ
        assert solver_card_id == CARD
        assert self.snapshot is not None
        return self.snapshot

    def get_solver_card_revision(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        solver_card_id: UUID,
        solver_card_revision_id: UUID,
    ) -> SolverCardSnapshot:
        del context
        assert decision is READ
        assert solver_card_id == CARD
        value = self.revisions.get(solver_card_revision_id)
        if value is None or value.record.aggregate_id != solver_card_id:
            raise SolverCardNotFound("Solver Card revision is not visible")
        content = value.content
        return SolverCardSnapshot(
            CARD,
            MODEL,
            TARGET,
            content.solver_material_id,
            value,
        )

    def list_solver_cards_for_model(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_model_id: UUID,
    ) -> tuple[SolverCardSnapshot, ...]:
        del context
        assert decision is READ
        assert material_model_id == MODEL
        return () if self.snapshot is None else (self.snapshot,)

    def list_solver_card_revisions(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        solver_card_id: UUID,
    ) -> tuple[RevisionSnapshot[ReferenceOpenRadiossCardContent], ...]:
        return (self.get_solver_card(context, decision, solver_card_id).current,)


def _application() -> FastAPI:
    application = FastAPI()
    service = _SolverCardService()
    application.state.solver_card_service = service

    def security(request: Request) -> None:
        request.state.security_context = CONTEXT

    def read(request: Request) -> None:
        request.state.authorization_decision = READ

    def execute(request: Request) -> None:
        request.state.authorization_decision = EXECUTE

    install_solver_card_api(
        application,
        service=cast(SolverCardService, service),
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


def test_solver_card_api_preflights_creates_previews_and_downloads_a_frozen_card() -> None:
    application = _application()
    target = {"solver": "openradioss", "version": "2025", "unit_system": "kg_m_s"}

    capabilities = _request(
        application,
        "GET",
        "/api/v1/exporters/reference-openradioss-elast/capabilities",
    )
    assert capabilities.status_code == 200
    assert capabilities.json()["non_production"] is True
    assert capabilities.json()["targets"][0]["keyword"] == "/MAT/ELAST"

    preflight = _request(
        application,
        "POST",
        f"/api/v1/material-models/{MODEL}/mapping-preflight",
        json={"target": target},
    )
    assert preflight.status_code == 200
    report = preflight.json()
    assert report["material_model_revision_id"] == str(MODEL_REVISION)
    assert report["exportable"] is True
    assert {item["name"]: item["status"] for item in report["items"]}[
        "source_yield_stress"
    ] == "not_applicable"

    created = _request(
        application,
        "POST",
        f"/api/v1/material-models/{MODEL}/solver-cards",
        json={
            "material_model_revision_id": str(MODEL_REVISION),
            "target": target,
            "expected_mapping_report_sha256": report["mapping_report_sha256"],
            "solver_material_id": 17,
            "card_title": "Reference steel",
            "change_reason": "create reference solver card",
        },
    )
    assert created.status_code == 201
    assert created.headers["ETag"] == '"revision:1:sha256:' + "e" * 64 + '"'
    current = created.json()["current_revision"]
    assert current["content"]["density_kg_per_m3"] == 7850.0
    assert current["mapping_report"]["mapping_report_sha256"] == report["mapping_report_sha256"]
    assert current["provenance"]["source_material_model_revision_id"] == str(MODEL_REVISION)

    listed = _request(
        application,
        "GET",
        f"/api/v1/material-models/{MODEL}/solver-cards",
    )
    assert listed.status_code == 200
    assert listed.json()["items"][0]["solver_card_id"] == str(CARD)

    fetched = _request(application, "GET", f"/api/v1/solver-cards/{CARD}")
    assert fetched.status_code == 200
    assert fetched.headers["ETag"] == created.headers["ETag"]

    revisions = _request(application, "GET", f"/api/v1/solver-cards/{CARD}/revisions")
    assert revisions.status_code == 200
    assert revisions.json()["revisions"][0]["id"] == str(CARD_REVISION)

    preview = _request(application, "GET", f"/api/v1/solver-cards/{CARD}/preview")
    assert preview.status_code == 200
    assert "/MAT/ELAST/17/1" in preview.text

    download = _request(application, "GET", f"/api/v1/solver-cards/{CARD}/download")
    assert download.status_code == 200
    assert download.text == preview.text
    assert download.headers["content-disposition"] == (
        'attachment; filename="openradioss-mat-17.rad"'
    )


def test_solver_card_api_pins_every_read_to_an_exact_revision_and_fails_closed() -> None:
    application = _application()
    target = {"solver": "openradioss", "version": "2025", "unit_system": "kg_m_s"}
    preflight = _request(
        application,
        "POST",
        f"/api/v1/material-models/{MODEL}/mapping-preflight",
        json={"target": target},
    )
    created = _request(
        application,
        "POST",
        f"/api/v1/material-models/{MODEL}/solver-cards",
        json={
            "material_model_revision_id": str(MODEL_REVISION),
            "target": target,
            "expected_mapping_report_sha256": preflight.json()["mapping_report_sha256"],
            "solver_material_id": 17,
            "card_title": "Reference steel",
            "change_reason": "create reference solver card",
        },
    )
    assert created.status_code == 201
    service = cast(_SolverCardService, application.state.solver_card_service)
    service.advance_current()

    exact = _request(
        application,
        "GET",
        f"/api/v1/solver-cards/{CARD}?revision_id={CARD_REVISION}",
    )
    assert exact.status_code == 200
    assert exact.json()["current_revision"]["id"] == str(CARD_REVISION)
    assert exact.json()["current_revision"]["content"]["card_title"] == "Reference steel"

    current = _request(application, "GET", f"/api/v1/solver-cards/{CARD}")
    assert current.status_code == 200
    assert current.json()["current_revision"]["id"] == str(CARD_REVISION_2)
    assert (
        current.json()["current_revision"]["content"]["card_title"]
        == "Reference steel revision 2"
    )
    assert (
        current.json()["current_revision"]["content"]["source_yield_stress_pa"]
        != exact.json()["current_revision"]["content"]["source_yield_stress_pa"]
    )
    assert (
        current.json()["current_revision"]["content"]["card_sha256"]
        != exact.json()["current_revision"]["content"]["card_sha256"]
    )
    assert (
        current.json()["current_revision"]["mapping_report"]["mapping_report_sha256"]
        != exact.json()["current_revision"]["mapping_report"]["mapping_report_sha256"]
    )
    assert current.json()["links"]["self"] == f"/api/v1/solver-cards/{CARD}"
    assert exact.json()["links"]["self"] == (
        f"/api/v1/solver-cards/{CARD}?revision_id={CARD_REVISION}"
    )
    assert exact.json()["links"]["preview"].endswith(f"/preview?revision_id={CARD_REVISION}")
    assert exact.json()["links"]["download"].endswith(f"/download?revision_id={CARD_REVISION}")

    preview = _request(
        application,
        "GET",
        f"/api/v1/solver-cards/{CARD}/preview?revision_id={CARD_REVISION}",
    )
    download = _request(
        application,
        "GET",
        f"/api/v1/solver-cards/{CARD}/download?revision_id={CARD_REVISION}",
    )
    assert preview.status_code == 200
    assert download.status_code == 200
    assert download.text == preview.text

    for revision_id in (UUID(int=999), OTHER_CARD_REVISION):
        missing = _request(
            application,
            "GET",
            f"/api/v1/solver-cards/{CARD}?revision_id={revision_id}",
        )
        assert missing.status_code == 404

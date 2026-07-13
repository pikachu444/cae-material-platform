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
from cmp.modules.modeling.adapters.api.material_models import install_material_model_api
from cmp.modules.modeling.application.service import (
    MATERIAL_MODEL_AGGREGATE_TYPE,
    CreateReferenceLinearElasticModel,
    MaterialModelService,
    MaterialModelSnapshot,
    RevisionSnapshot,
)
from cmp.modules.modeling.domain.reference_linear_elasticity import (
    ReferenceLinearElasticContent,
)
from cmp.shared.domain.revisions import RevisionRecord, TenantScope
from fastapi import FastAPI, Request

NOW = datetime(2026, 7, 14, 9, 0, tzinfo=UTC)
ORG = UUID("d2000000-0000-4000-8000-000000000001")
PROJECT = UUID("d2000000-0000-4000-8000-000000000002")
ACTOR = UUID("d2000000-0000-4000-8000-000000000003")
MATERIAL = UUID("d2000000-0000-4000-8000-000000000004")
MATERIAL_REVISION = UUID("d2000000-0000-4000-8000-000000000005")
STATE = UUID("d2000000-0000-4000-8000-000000000006")
STATE_REVISION = UUID("d2000000-0000-4000-8000-000000000007")
PROPERTY_SET = UUID("d2000000-0000-4000-8000-000000000008")
PROPERTY_SET_REVISION = UUID("d2000000-0000-4000-8000-000000000009")
MODEL = UUID("d2000000-0000-4000-8000-00000000000a")
MODEL_REVISION = UUID("d2000000-0000-4000-8000-00000000000b")
TRACE = "00-000000000000000000000000000000d2-00000000000000d2-01"


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


READ = _decision(Permission.MODELING_READ)
WRITE = _decision(Permission.MODELING_WRITE)


def _content() -> ReferenceLinearElasticContent:
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


def _record() -> RevisionRecord:
    return RevisionRecord(
        revision_id=MODEL_REVISION,
        aggregate_type=MATERIAL_MODEL_AGGREGATE_TYPE,
        aggregate_id=MODEL,
        scope=TenantScope(ORG, PROJECT, DataClassification.INTERNAL.value),
        revision_no=1,
        based_on_revision_id=None,
        schema_id="urn:cmp:modeling:reference-isotropic-linear-elasticity:1.0.0",
        schema_version="1.0.0",
        content_hash="d" * 64,
        created_at=NOW,
        created_by=ACTOR,
        change_reason="create reference model",
        request_id=CONTEXT.request_id,
        trace_id=TRACE,
    )


class _MaterialModelService:
    def __init__(self) -> None:
        self.snapshot = MaterialModelSnapshot(
            MODEL,
            STATE,
            RevisionSnapshot(_record(), _content()),
        )

    def create_reference_linear_elastic_model(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CreateReferenceLinearElasticModel,
    ) -> MaterialModelSnapshot:
        del context, decision
        assert command.material_state_id == STATE
        assert command.property_set_revision_id == PROPERTY_SET_REVISION
        return self.snapshot

    def get_material_model(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_model_id: UUID,
    ) -> MaterialModelSnapshot:
        del context, decision
        assert material_model_id == MODEL
        return self.snapshot

    def list_material_models_for_state(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_state_id: UUID,
    ) -> tuple[MaterialModelSnapshot, ...]:
        del context, decision
        assert material_state_id == STATE
        return (self.snapshot,)

    def list_material_model_revisions(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_model_id: UUID,
    ) -> tuple[RevisionSnapshot[ReferenceLinearElasticContent], ...]:
        del context, decision
        assert material_model_id == MODEL
        return (self.snapshot.current,)


def _application() -> FastAPI:
    application = FastAPI()
    service = _MaterialModelService()

    def security(request: Request) -> None:
        request.state.security_context = CONTEXT

    def read(request: Request) -> None:
        request.state.authorization_decision = READ

    def write(request: Request) -> None:
        request.state.authorization_decision = WRITE

    install_material_model_api(
        application,
        service=cast(MaterialModelService, service),
        security_dependency=security,
        read_dependency=read,
        write_dependency=write,
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


def test_material_model_api_creates_and_reads_typed_reference_ir() -> None:
    application = _application()
    created = _request(
        application,
        "POST",
        f"/api/v1/material-states/{STATE}/material-models",
        json={
            "property_set_revision_id": str(PROPERTY_SET_REVISION),
            "change_reason": "create reference material model",
        },
    )

    assert created.status_code == 201
    assert created.headers["ETag"] == '"revision:1:sha256:' + "d" * 64 + '"'
    current = created.json()["current_revision"]
    assert current["content"]["density_kg_per_m3"] == 7850.0
    assert current["content"]["source_yield_stress_pa"] == 355_000_000.0
    assert current["ir"]["payload"]["model"] == "isotropic_linear_elasticity"
    assert current["ir"]["payload"]["source_property_disposition"]["yield_stress"] == {
        "value": 355_000_000.0,
        "unit": "Pa",
        "status": "not_applicable_to_linear_elasticity",
    }
    assert current["provenance"]["source_property_set_revision_id"] == str(PROPERTY_SET_REVISION)

    listed = _request(application, "GET", f"/api/v1/material-states/{STATE}/material-models")
    assert listed.status_code == 200
    assert listed.json()["items"][0]["material_model_id"] == str(MODEL)

    fetched = _request(application, "GET", f"/api/v1/material-models/{MODEL}")
    assert fetched.status_code == 200
    assert fetched.headers["ETag"] == created.headers["ETag"]

    revisions = _request(application, "GET", f"/api/v1/material-models/{MODEL}/revisions")
    assert revisions.status_code == 200
    assert revisions.json()["revisions"][0]["id"] == str(MODEL_REVISION)

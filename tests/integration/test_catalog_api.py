from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID, uuid4

import httpx
from cmp.modules.catalog.adapters.api.catalog import install_catalog_api
from cmp.modules.catalog.application.service import (
    MATERIAL_AGGREGATE_TYPE,
    MATERIAL_LOT_AGGREGATE_TYPE,
    MATERIAL_STATE_AGGREGATE_TYPE,
    PROCESS_DEFINITION_AGGREGATE_TYPE,
    PROCESS_RUN_AGGREGATE_TYPE,
    PROPERTY_SET_AGGREGATE_TYPE,
    STATE_GENEALOGY_AGGREGATE_TYPE,
    CatalogService,
    MaterialDetail,
    MaterialLotSnapshot,
    MaterialSnapshot,
    MaterialStateSnapshot,
    ProcessDefinitionSnapshot,
    ProcessRunSnapshot,
    PropertySetSnapshot,
    RevisionSnapshot,
    StateGenealogySnapshot,
)
from cmp.modules.catalog.domain.model import (
    LotKind,
    MaterialClass,
    MaterialContent,
    MaterialLotContent,
    MaterialStateContent,
    ProcessDefinitionContent,
    ProcessKind,
    PropertySetContent,
    PropertySource,
    PropertySourceKind,
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
from cmp.shared.domain.revisions import RevisionRecord, TenantScope
from fastapi import FastAPI, Request

NOW = datetime(2026, 7, 13, 10, 0, tzinfo=UTC)
ORG = UUID("c8000000-0000-4000-8000-000000000001")
PROJECT = UUID("c8000000-0000-4000-8000-000000000002")
ACTOR = UUID("c8000000-0000-4000-8000-000000000003")
MATERIAL = UUID("c8000000-0000-4000-8000-000000000004")
MATERIAL_REVISION_1 = UUID("c8000000-0000-4000-8000-000000000005")
MATERIAL_REVISION_2 = UUID("c8000000-0000-4000-8000-000000000006")
STATE = UUID("c8000000-0000-4000-8000-000000000007")
STATE_REVISION = UUID("c8000000-0000-4000-8000-000000000008")
PROPERTY_SET = UUID("c8000000-0000-4000-8000-000000000009")
PROPERTY_SET_REVISION = UUID("c8000000-0000-4000-8000-00000000000a")
PROCESS = UUID("c8000000-0000-4000-8000-00000000000b")
PROCESS_REVISION = UUID("c8000000-0000-4000-8000-00000000000c")
LOT = UUID("c8000000-0000-4000-8000-00000000000d")
LOT_REVISION = UUID("c8000000-0000-4000-8000-00000000000e")
GENEALOGY = UUID("c8000000-0000-4000-8000-00000000000f")
GENEALOGY_REVISION = UUID("c8000000-0000-4000-8000-000000000010")
PROCESS_RUN = UUID("c8000000-0000-4000-8000-000000000011")
PROCESS_RUN_REVISION = UUID("c8000000-0000-4000-8000-000000000012")
OUTPUT_LOT = UUID("c8000000-0000-4000-8000-000000000013")
OUTPUT_LOT_REVISION = UUID("c8000000-0000-4000-8000-000000000014")
TRACE = "00-000000000000000000000000000000c8-00000000000000c8-01"


def _context() -> SecurityContext:
    return SecurityContext(
        principal=Principal(ACTOR, PrincipalType.USER, "Catalog Steward", True),
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
        roles=(Role.DATA_STEWARD,),
        database_permissions=database_permissions_for(permission),
        max_classification=DataClassification.INTERNAL,
        allow_export_controlled=False,
        request_id=CONTEXT.request_id,
        trace_id=TRACE,
        decided_at=NOW,
    )


READ = _decision(Permission.CATALOG_READ)
WRITE = _decision(Permission.CATALOG_WRITE)


def _record(
    aggregate_type: str,
    aggregate_id: UUID,
    revision_id: UUID,
    revision_no: int,
    content_hash: str,
    based_on_revision_id: UUID | None = None,
) -> RevisionRecord:
    return RevisionRecord(
        revision_id=revision_id,
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        scope=TenantScope(ORG, PROJECT, "internal"),
        revision_no=revision_no,
        based_on_revision_id=based_on_revision_id,
        schema_id=f"urn:cmp:{aggregate_type}:1.0.0",
        schema_version="1.0.0",
        content_hash=content_hash,
        created_at=NOW,
        created_by=ACTOR,
        change_reason="catalog test fixture",
        request_id=CONTEXT.request_id,
        trace_id=TRACE,
    )


class _CatalogService:
    def __init__(self) -> None:
        material_content = MaterialContent("S355 Structural Steel", "S355", "steel")
        material_record = _record(
            MATERIAL_AGGREGATE_TYPE, MATERIAL, MATERIAL_REVISION_1, 1, "a" * 64
        )
        self.material = MaterialSnapshot(
            MATERIAL, RevisionSnapshot(material_record, material_content)
        )
        state_content = MaterialStateContent(
            MATERIAL,
            MATERIAL_REVISION_1,
            "As received",
            manufacturing_route="hot rolled",
            lot_or_batch="DEMO-001",
        )
        self.state = MaterialStateSnapshot(
            STATE,
            MATERIAL,
            RevisionSnapshot(
                _record(MATERIAL_STATE_AGGREGATE_TYPE, STATE, STATE_REVISION, 1, "b" * 64),
                state_content,
            ),
        )
        source = PropertySource(PropertySourceKind.MANUAL)
        property_content = PropertySetContent(
            STATE,
            STATE_REVISION,
            density_kg_per_m3=7850.0,
            density_source=source,
            youngs_modulus_pa=210_000_000_000.0,
            youngs_modulus_source=source,
            poisson_ratio=0.3,
            poisson_ratio_source=source,
        )
        self.property_set = PropertySetSnapshot(
            PROPERTY_SET,
            STATE,
            RevisionSnapshot(
                _record(
                    PROPERTY_SET_AGGREGATE_TYPE,
                    PROPERTY_SET,
                    PROPERTY_SET_REVISION,
                    1,
                    "c" * 64,
                ),
                property_content,
            ),
        )
        self.process = ProcessDefinitionSnapshot(
            PROCESS,
            RevisionSnapshot(
                _record(
                    PROCESS_DEFINITION_AGGREGATE_TYPE,
                    PROCESS,
                    PROCESS_REVISION,
                    1,
                    "e" * 64,
                ),
                ProcessDefinitionContent(
                    "HT-QT-01", "Quench and temper", ProcessKind.HEAT_TREATMENT
                ),
            ),
        )
        self.lot = MaterialLotSnapshot(
            LOT,
            MATERIAL,
            RevisionSnapshot(
                _record(MATERIAL_LOT_AGGREGATE_TYPE, LOT, LOT_REVISION, 1, "f" * 64),
                MaterialLotContent(MATERIAL, MATERIAL_REVISION_1, "HEAT-001", LotKind.BATCH),
            ),
        )
        self.genealogy: StateGenealogySnapshot | None = None
        self.process_run: ProcessRunSnapshot | None = None

    def create_material(
        self, context: SecurityContext, decision: AuthorizationDecision, command: Any
    ) -> MaterialSnapshot:
        del context, decision
        self.material = MaterialSnapshot(
            MATERIAL,
            RevisionSnapshot(
                _record(MATERIAL_AGGREGATE_TYPE, MATERIAL, MATERIAL_REVISION_1, 1, "a" * 64),
                command.content,
            ),
        )
        return self.material

    def list_materials(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        *,
        query: str | None,
        material_class: MaterialClass | None,
        limit: int,
    ) -> tuple[MaterialSnapshot, ...]:
        del context, decision, query, material_class, limit
        return (self.material,)

    def get_material_detail(
        self, context: SecurityContext, decision: AuthorizationDecision, material_id: UUID
    ) -> MaterialDetail:
        del context, decision
        assert material_id == MATERIAL
        return MaterialDetail(self.material, (self.state,), (self.property_set,))

    def list_material_revisions(
        self, context: SecurityContext, decision: AuthorizationDecision, material_id: UUID
    ) -> tuple[RevisionSnapshot[MaterialContent], ...]:
        del context, decision
        assert material_id == MATERIAL
        return (self.material.current,)

    def compare_material_revisions(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_id: UUID,
        left_revision_id: UUID,
        right_revision_id: UUID,
    ) -> tuple[
        RevisionSnapshot[MaterialContent], RevisionSnapshot[MaterialContent], tuple[str, ...]
    ]:
        del context, decision, left_revision_id, right_revision_id
        assert material_id == MATERIAL
        return self.material.current, self.material.current, ()

    def get_material_for_write(
        self, context: SecurityContext, decision: AuthorizationDecision, material_id: UUID
    ) -> MaterialSnapshot:
        del context, decision
        assert material_id == MATERIAL
        return self.material

    def revise_material(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_id: UUID,
        command: Any,
    ) -> MaterialSnapshot:
        del context, decision
        assert material_id == MATERIAL
        self.material = MaterialSnapshot(
            MATERIAL,
            RevisionSnapshot(
                _record(
                    MATERIAL_AGGREGATE_TYPE,
                    MATERIAL,
                    MATERIAL_REVISION_2,
                    2,
                    "d" * 64,
                    MATERIAL_REVISION_1,
                ),
                command.content,
            ),
        )
        return self.material

    def create_material_state(
        self, context: SecurityContext, decision: AuthorizationDecision, command: Any
    ) -> MaterialStateSnapshot:
        del context, decision
        self.state = MaterialStateSnapshot(
            STATE,
            command.content.material_id,
            RevisionSnapshot(
                _record(MATERIAL_STATE_AGGREGATE_TYPE, STATE, STATE_REVISION, 1, "b" * 64),
                command.content,
            ),
        )
        return self.state

    def get_material_state(
        self, context: SecurityContext, decision: AuthorizationDecision, material_state_id: UUID
    ) -> MaterialStateSnapshot:
        del context, decision
        assert material_state_id == STATE
        return self.state

    def get_material_state_for_write(
        self, context: SecurityContext, decision: AuthorizationDecision, material_state_id: UUID
    ) -> MaterialStateSnapshot:
        return self.get_material_state(context, decision, material_state_id)

    def revise_material_state(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_state_id: UUID,
        command: Any,
    ) -> MaterialStateSnapshot:
        del context, decision, material_state_id, command
        return self.state

    def create_property_set(
        self, context: SecurityContext, decision: AuthorizationDecision, command: Any
    ) -> PropertySetSnapshot:
        del context, decision
        self.property_set = PropertySetSnapshot(
            PROPERTY_SET,
            command.content.material_state_id,
            RevisionSnapshot(
                _record(
                    PROPERTY_SET_AGGREGATE_TYPE,
                    PROPERTY_SET,
                    PROPERTY_SET_REVISION,
                    1,
                    "c" * 64,
                ),
                command.content,
            ),
        )
        return self.property_set

    def get_property_set(
        self, context: SecurityContext, decision: AuthorizationDecision, property_set_id: UUID
    ) -> PropertySetSnapshot:
        del context, decision
        assert property_set_id == PROPERTY_SET
        return self.property_set

    def get_property_set_for_write(
        self, context: SecurityContext, decision: AuthorizationDecision, property_set_id: UUID
    ) -> PropertySetSnapshot:
        return self.get_property_set(context, decision, property_set_id)

    def revise_property_set(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        property_set_id: UUID,
        command: Any,
    ) -> PropertySetSnapshot:
        del context, decision, property_set_id, command
        return self.property_set

    def create_process_definition(
        self, context: SecurityContext, decision: AuthorizationDecision, command: Any
    ) -> ProcessDefinitionSnapshot:
        del context, decision
        self.process = ProcessDefinitionSnapshot(
            PROCESS,
            RevisionSnapshot(
                _record(
                    PROCESS_DEFINITION_AGGREGATE_TYPE,
                    PROCESS,
                    PROCESS_REVISION,
                    1,
                    "e" * 64,
                ),
                command.content,
            ),
        )
        return self.process

    def list_process_definitions(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        *,
        kind: ProcessKind | None,
        limit: int,
    ) -> tuple[ProcessDefinitionSnapshot, ...]:
        del context, decision, kind, limit
        return (self.process,)

    def create_material_lot(
        self, context: SecurityContext, decision: AuthorizationDecision, command: Any
    ) -> MaterialLotSnapshot:
        del context, decision
        self.lot = MaterialLotSnapshot(
            LOT,
            MATERIAL,
            RevisionSnapshot(
                _record(MATERIAL_LOT_AGGREGATE_TYPE, LOT, LOT_REVISION, 1, "f" * 64),
                command.content,
            ),
        )
        return self.lot

    def list_material_lots(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_id: UUID,
        *,
        limit: int,
    ) -> tuple[MaterialLotSnapshot, ...]:
        del context, decision, limit
        assert material_id == MATERIAL
        return (self.lot,)

    def create_state_genealogy(
        self, context: SecurityContext, decision: AuthorizationDecision, command: Any
    ) -> StateGenealogySnapshot:
        del context, decision
        self.genealogy = StateGenealogySnapshot(
            GENEALOGY,
            STATE,
            RevisionSnapshot(
                _record(
                    STATE_GENEALOGY_AGGREGATE_TYPE,
                    GENEALOGY,
                    GENEALOGY_REVISION,
                    1,
                    "1" * 64,
                ),
                command.content,
            ),
        )
        return self.genealogy

    def get_state_genealogy_for_state(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_state_id: UUID,
    ) -> StateGenealogySnapshot | None:
        del context, decision
        assert material_state_id == STATE
        return self.genealogy

    def create_process_run(
        self, context: SecurityContext, decision: AuthorizationDecision, command: Any
    ) -> ProcessRunSnapshot:
        del context, decision
        self.process_run = ProcessRunSnapshot(
            PROCESS_RUN,
            STATE,
            RevisionSnapshot(
                _record(
                    PROCESS_RUN_AGGREGATE_TYPE,
                    PROCESS_RUN,
                    PROCESS_RUN_REVISION,
                    1,
                    "2" * 64,
                ),
                command.content,
            ),
        )
        return self.process_run

    def list_process_runs_for_state(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_state_id: UUID,
        *,
        limit: int,
    ) -> tuple[ProcessRunSnapshot, ...]:
        del context, decision, limit
        assert material_state_id == STATE
        return (self.process_run,) if self.process_run is not None else ()

    def get_process_run(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        process_run_id: UUID,
    ) -> ProcessRunSnapshot:
        del context, decision
        assert process_run_id == PROCESS_RUN and self.process_run is not None
        return self.process_run


def _application() -> FastAPI:
    application = FastAPI()
    catalog = _CatalogService()

    def security(request: Request) -> None:
        request.state.security_context = CONTEXT

    def read(request: Request) -> None:
        request.state.authorization_decision = READ

    def write(request: Request) -> None:
        request.state.authorization_decision = WRITE

    install_catalog_api(
        application,
        service=cast(CatalogService, catalog),
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
    headers: dict[str, str] | None = None,
    json: dict[str, object] | None = None,
) -> httpx.Response:
    async def send() -> httpx.Response:
        transport = httpx.ASGITransport(app=application)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.request(method, path, headers=headers, json=json)

    return asyncio.run(send())


def test_catalog_api_supports_material_to_typed_properties_with_revision_etags() -> None:
    application = _application()
    create = _request(
        application,
        "POST",
        "/api/v1/materials",
        json={
            "classification": "internal",
            "content": {
                "name": "S355 Structural Steel",
                "material_code": "S355",
                "material_class": "metal",
            },
            "change_reason": "create demo material",
        },
    )

    assert create.status_code == 201
    assert create.headers["ETag"] == '"revision:1:sha256:' + "a" * 64 + '"'
    assert create.json()["current_revision"]["provenance"]["reference_type"] == (
        "catalog.material.revision"
    )

    listed = _request(application, "GET", "/api/v1/materials?q=S355&material_class=metal")
    assert listed.status_code == 200
    assert listed.json()["items"][0]["current_revision"]["content"]["material_code"] == "S355"
    assert listed.json()["items"][0]["current_revision"]["content"]["material_class"] == "metal"

    missing_precondition = _request(
        application,
        "POST",
        f"/api/v1/materials/{MATERIAL}/revisions",
        json={
            "content": {"name": "S355 Structural Steel", "material_code": "S355R"},
            "change_reason": "correct catalog code",
        },
    )
    assert missing_precondition.status_code == 422
    assert missing_precondition.json()["code"] == "CMP-CATALOG-0002"

    revised = _request(
        application,
        "POST",
        f"/api/v1/materials/{MATERIAL}/revisions",
        headers={"If-Match": create.headers["ETag"]},
        json={
            "content": {"name": "S355 Structural Steel", "material_code": "S355R"},
            "change_reason": "correct catalog code",
        },
    )
    assert revised.status_code == 200
    assert revised.json()["current_revision"]["revision_no"] == 2
    assert revised.json()["current_revision"]["content"]["material_class"] == "metal"

    state = _request(
        application,
        "POST",
        f"/api/v1/materials/{MATERIAL}/states",
        json={
            "content": {
                "material_revision_id": str(MATERIAL_REVISION_2),
                "name": "As received",
                "lot_or_batch": "DEMO-001",
            },
            "change_reason": "record supplied state",
        },
    )
    assert state.status_code == 201
    assert state.json()["material_id"] == str(MATERIAL)

    properties = _request(
        application,
        "POST",
        f"/api/v1/material-states/{STATE}/property-sets",
        json={
            "content": {
                "material_state_revision_id": str(STATE_REVISION),
                "density_kg_per_m3": 7850.0,
                "density_source": {"kind": "manual"},
                "youngs_modulus_pa": 210000000000.0,
                "youngs_modulus_source": {"kind": "manual"},
                "poisson_ratio": 0.3,
                "poisson_ratio_source": {"kind": "manual"},
            },
            "change_reason": "record reference elastic properties",
        },
    )
    assert properties.status_code == 201
    content = properties.json()["current_revision"]["content"]
    assert content["density_kg_per_m3"] == 7850.0
    assert content["youngs_modulus_pa"] == 210000000000.0
    assert content["poisson_ratio"] == 0.3
    assert "key" not in content and "value" not in content


def test_catalog_api_creates_exact_process_lot_and_state_genealogy_links() -> None:
    application = _application()
    process = _request(
        application,
        "POST",
        "/api/v1/process-definitions",
        json={
            "classification": "internal",
            "content": {
                "process_code": "HT-QT-01",
                "name": "Quench and temper",
                "kind": "heat_treatment",
            },
            "change_reason": "register governed heat treatment",
        },
    )
    assert process.status_code == 201
    assert process.json()["current_revision"]["content"]["kind"] == "heat_treatment"

    lot = _request(
        application,
        "POST",
        f"/api/v1/materials/{MATERIAL}/lots",
        json={
            "content": {
                "material_revision_id": str(MATERIAL_REVISION_1),
                "lot_code": "HEAT-001",
                "kind": "batch",
            },
            "change_reason": "register source heat",
        },
    )
    assert lot.status_code == 201
    assert lot.json()["current_revision"]["content"]["material_revision_id"] == str(
        MATERIAL_REVISION_1
    )

    genealogy = _request(
        application,
        "POST",
        f"/api/v1/material-states/{STATE}/genealogy",
        json={
            "content": {
                "material_state_revision_id": str(STATE_REVISION),
                "heat_treatment_process_id": str(PROCESS),
                "heat_treatment_process_revision_id": str(PROCESS_REVISION),
                "material_lot_id": str(LOT),
                "material_lot_revision_id": str(LOT_REVISION),
            },
            "change_reason": "pin exact genealogy links",
        },
    )
    assert genealogy.status_code == 201
    genealogy_content = genealogy.json()["current_revision"]["content"]
    assert genealogy_content["heat_treatment_process_revision_id"] == str(PROCESS_REVISION)
    assert genealogy_content["material_lot_revision_id"] == str(LOT_REVISION)

    read_back = _request(application, "GET", f"/api/v1/material-states/{STATE}/genealogy")
    assert read_back.status_code == 200
    assert read_back.headers["ETag"] == genealogy.headers["ETag"]


def test_catalog_api_creates_split_process_run_with_explicit_balance_evidence() -> None:
    application = _application()
    created = _request(
        application,
        "POST",
        f"/api/v1/material-states/{STATE}/process-runs",
        json={
            "content": {
                "process_definition_id": str(PROCESS),
                "process_definition_revision_id": str(PROCESS_REVISION),
                "material_state_revision_id": str(STATE_REVISION),
                "run_code": "SPLIT-001",
                "started_at": "2026-07-16T09:00:00Z",
                "ended_at": "2026-07-16T10:00:00Z",
                "operator_name": "Demo operator",
                "equipment_reference": "CUTTER-01",
                "balance_basis": "mass",
                "balance_tolerance_fraction": "0.001",
                "inputs": [
                    {
                        "material_lot_id": str(LOT),
                        "material_lot_revision_id": str(LOT_REVISION),
                        "original_quantity": "1",
                        "original_unit": "kg",
                    }
                ],
                "outputs": [
                    {
                        "material_lot_id": str(OUTPUT_LOT),
                        "material_lot_revision_id": str(OUTPUT_LOT_REVISION),
                        "original_quantity": "400",
                        "original_unit": "g",
                    },
                    {
                        "material_lot_id": str(UUID(int=OUTPUT_LOT.int + 2)),
                        "material_lot_revision_id": str(UUID(int=OUTPUT_LOT_REVISION.int + 2)),
                        "original_quantity": "600",
                        "original_unit": "g",
                    },
                ],
            },
            "change_reason": "record split flow",
        },
    )

    assert created.status_code == 201, created.text
    content = created.json()["current_revision"]["content"]
    assert content["balance"]["within_tolerance"] is True
    assert content["balance"]["input_total"] == "1"
    assert content["outputs"][0]["normalized_unit"] == "kg"
    assert content["outputs"][0]["normalization_factor"] == "0.001"

    listed = _request(application, "GET", f"/api/v1/material-states/{STATE}/process-runs")
    assert listed.status_code == 200
    assert listed.json()["items"][0]["process_run_id"] == str(PROCESS_RUN)

    read_back = _request(application, "GET", f"/api/v1/process-runs/{PROCESS_RUN}")
    assert read_back.status_code == 200
    assert read_back.headers["ETag"] == created.headers["ETag"]

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import cast
from uuid import UUID, uuid4

import httpx
from cmp.modules.exporting.adapters.api.elastoplastic_solver_cards import (
    install_elastoplastic_solver_card_api,
)
from cmp.modules.exporting.application.elastoplastic_service import (
    CreateReferenceElastoplasticSolverCard,
    ElastoplasticSolverCardService,
    ElastoplasticSolverCardSnapshot,
)
from cmp.modules.exporting.application.service import SOLVER_CARD_AGGREGATE_TYPE, RevisionSnapshot
from cmp.modules.exporting.domain.reference_isotropic_tabulated_plasticity import (
    ElastoplasticExportTarget,
    ElastoplasticMappingReport,
    build_reference_elastoplastic_solver_card,
    preflight_reference_elastoplastic_export,
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
from cmp.modules.modeling.adapters.api.tabulated_plasticity import (
    install_tabulated_plasticity_api,
)
from cmp.modules.modeling.application.service import (
    MATERIAL_MODEL_AGGREGATE_TYPE,
)
from cmp.modules.modeling.application.service import (
    RevisionSnapshot as ModelRevisionSnapshot,
)
from cmp.modules.modeling.application.tabulated_plasticity import (
    CreateReferenceTabulatedPlasticityModel,
    TabulatedPlasticityModelService,
    TabulatedPlasticityModelSnapshot,
)
from cmp.modules.modeling.domain.reference_isotropic_tabulated_plasticity import (
    HardeningCurvePoint,
    HardeningPointOrigin,
    ReferenceIsotropicTabulatedPlasticityContent,
)
from cmp.shared.domain.revisions import RevisionRecord, TenantScope, content_sha256
from fastapi import FastAPI, Request

NOW = datetime(2026, 7, 26, 9, 0, tzinfo=UTC)
ORG = UUID("e3000000-0000-4000-8000-000000000001")
PROJECT = UUID("e3000000-0000-4000-8000-000000000002")
ACTOR = UUID("e3000000-0000-4000-8000-000000000003")
STATE = UUID("e3000000-0000-4000-8000-000000000004")
PROPERTY_REVISION = UUID("e3000000-0000-4000-8000-000000000005")
DATASET_REVISION = UUID("e3000000-0000-4000-8000-000000000006")
MODEL = UUID("e3000000-0000-4000-8000-000000000007")
MODEL_REVISION = UUID("e3000000-0000-4000-8000-000000000008")
CARD = UUID("e3000000-0000-4000-8000-000000000009")
CARD_REVISION = UUID("e3000000-0000-4000-8000-00000000000a")
TRACE = "00-000000000000000000000000000000e3-00000000000000e3-01"


def _context() -> SecurityContext:
    return SecurityContext(
        principal=Principal(ACTOR, PrincipalType.USER, "Elastoplastic modeler", True),
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


def _points() -> tuple[HardeningCurvePoint, ...]:
    return (
        HardeningCurvePoint(0.0, 355_000_000.0, HardeningPointOrigin.CATALOG_YIELD_ANCHOR),
        HardeningCurvePoint(
            0.004,
            420_000_000.0,
            HardeningPointOrigin.PRE_NECKING_OBSERVATION,
        ),
        HardeningCurvePoint(
            0.08,
            535_000_000.0,
            HardeningPointOrigin.PRE_NECKING_OBSERVATION,
        ),
        HardeningCurvePoint(
            0.25,
            535_000_000.0,
            HardeningPointOrigin.APPROVED_CONSTANT_EXTENSION,
        ),
    )


def _content() -> ReferenceIsotropicTabulatedPlasticityContent:
    return ReferenceIsotropicTabulatedPlasticityContent(
        material_id=UUID("e3000000-0000-4000-8000-000000000010"),
        material_revision_id=UUID("e3000000-0000-4000-8000-000000000011"),
        material_state_id=STATE,
        material_state_revision_id=UUID("e3000000-0000-4000-8000-000000000012"),
        property_set_id=UUID("e3000000-0000-4000-8000-000000000013"),
        property_set_revision_id=PROPERTY_REVISION,
        source_dataset_id=UUID("e3000000-0000-4000-8000-000000000014"),
        source_dataset_revision_id=DATASET_REVISION,
        hardening_curve_artifact_id=UUID("e3000000-0000-4000-8000-000000000015"),
        hardening_curve_sha256="a" * 64,
        hardening_curve_point_count=4,
        source_point_count=6,
        pre_yield_excluded_point_count=3,
        post_necking_excluded_point_count=1,
        necking_source_point_index=4,
        density_kg_per_m3=7_850.0,
        youngs_modulus_pa=210_000_000_000.0,
        poisson_ratio=0.3,
        initial_yield_stress_pa=355_000_000.0,
        necking_engineering_strain=0.12,
        characterized_max_true_plastic_strain=0.08,
        extension_max_true_plastic_strain=0.25,
        post_necking_approximation_acknowledged=True,
    )


def _record(
    revision_id: UUID,
    aggregate_type: str,
    aggregate_id: UUID,
    schema_id: str,
    content_hash: str,
) -> RevisionRecord:
    return RevisionRecord(
        revision_id=revision_id,
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        scope=TenantScope(ORG, PROJECT, DataClassification.INTERNAL.value),
        revision_no=1,
        based_on_revision_id=None,
        schema_id=schema_id,
        schema_version="1.0.0",
        content_hash=content_hash,
        created_at=NOW,
        created_by=ACTOR,
        change_reason="reference integration fixture",
        request_id=CONTEXT.request_id,
        trace_id=TRACE,
    )


MODEL_SNAPSHOT = TabulatedPlasticityModelSnapshot(
    id=MODEL,
    material_state_id=STATE,
    current=ModelRevisionSnapshot(
        _record(
            MODEL_REVISION,
            MATERIAL_MODEL_AGGREGATE_TYPE,
            MODEL,
            "urn:cmp:modeling:reference-isotropic-tabulated-plasticity:1.0.0",
            content_sha256({"fixture": "plastic-model"}),
        ),
        _content(),
    ),
)


class _ModelService:
    async def create_model(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CreateReferenceTabulatedPlasticityModel,
    ) -> TabulatedPlasticityModelSnapshot:
        del context, decision
        assert command.material_state_id == STATE
        assert command.property_set_revision_id == PROPERTY_REVISION
        assert command.dataset_revision_id == DATASET_REVISION
        assert command.acknowledge_post_necking_approximation
        return MODEL_SNAPSHOT

    def get_model(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_model_id: UUID,
    ) -> TabulatedPlasticityModelSnapshot:
        del context, decision
        assert material_model_id == MODEL
        return MODEL_SNAPSHOT

    def list_models_for_state(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_state_id: UUID,
    ) -> tuple[TabulatedPlasticityModelSnapshot, ...]:
        del context, decision
        assert material_state_id == STATE
        return (MODEL_SNAPSHOT,)

    async def read_hardening_curve_for_export(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        content: ReferenceIsotropicTabulatedPlasticityContent,
    ) -> tuple[HardeningCurvePoint, ...]:
        del context, decision
        assert content == MODEL_SNAPSHOT.current.content
        return _points()


class _ExportService:
    def __init__(self) -> None:
        self.card: ElastoplasticSolverCardSnapshot | None = None

    def preflight(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        *,
        material_model_id: UUID,
        material_model_revision_id: UUID,
        target: ElastoplasticExportTarget,
    ) -> ElastoplasticMappingReport:
        del context, decision
        return preflight_reference_elastoplastic_export(
            material_model_id=material_model_id,
            material_model_revision_id=material_model_revision_id,
            content=MODEL_SNAPSHOT.current.content,
            target=target,
        )

    async def create_card(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CreateReferenceElastoplasticSolverCard,
    ) -> tuple[ElastoplasticSolverCardSnapshot, ElastoplasticMappingReport]:
        del context, decision
        report, content = build_reference_elastoplastic_solver_card(
            material_model_id=command.material_model_id,
            material_model_revision_id=command.material_model_revision_id,
            source=MODEL_SNAPSHOT.current.content,
            points=_points(),
            target=command.target,
            expected_mapping_report_sha256=command.expected_mapping_report_sha256,
            solver_material_id=command.solver_material_id,
            material_name=command.material_name,
        )
        self.card = ElastoplasticSolverCardSnapshot(
            id=CARD,
            material_model_id=MODEL,
            target=command.target,
            solver_material_id=command.solver_material_id,
            material_name=command.material_name,
            current=RevisionSnapshot(
                _record(
                    CARD_REVISION,
                    SOLVER_CARD_AGGREGATE_TYPE,
                    CARD,
                    "urn:cmp:exporting:reference-isotropic-tabulated-plasticity-card:1.0.0",
                    content_sha256(content.canonical()),
                ),
                content,
            ),
        )
        return self.card, report

    def get_card(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        solver_card_id: UUID,
    ) -> ElastoplasticSolverCardSnapshot:
        del context, decision
        assert solver_card_id == CARD and self.card is not None
        return self.card

    def list_cards_for_model(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_model_id: UUID,
    ) -> tuple[ElastoplasticSolverCardSnapshot, ...]:
        del context, decision
        assert material_model_id == MODEL
        return () if self.card is None else (self.card,)


def _application() -> FastAPI:
    application = FastAPI()
    model_service = _ModelService()
    export_service = _ExportService()

    def security(request: Request) -> None:
        request.state.security_context = CONTEXT

    def modeling_read(request: Request) -> None:
        request.state.authorization_decision = _decision(Permission.MODELING_READ)

    def modeling_write(request: Request) -> None:
        request.state.authorization_decision = _decision(Permission.MODELING_WRITE)

    def export_read(request: Request) -> None:
        request.state.authorization_decision = _decision(Permission.EXPORT_READ)

    def export_execute(request: Request) -> None:
        request.state.authorization_decision = _decision(Permission.EXPORT_EXECUTE)

    install_tabulated_plasticity_api(
        application,
        service=cast(TabulatedPlasticityModelService, model_service),
        security_dependency=security,
        read_dependency=modeling_read,
        write_dependency=modeling_write,
    )
    install_elastoplastic_solver_card_api(
        application,
        service=cast(ElastoplasticSolverCardService, export_service),
        security_dependency=security,
        read_dependency=export_read,
        execute_dependency=export_execute,
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


def test_tensile_ir_to_abaqus_card_preview_and_download() -> None:
    application = _application()
    created_model = _request(
        application,
        "POST",
        f"/api/v1/material-states/{STATE}/tabulated-plasticity-models",
        json={
            "property_set_revision_id": str(PROPERTY_REVISION),
            "dataset_revision_id": str(DATASET_REVISION),
            "extension_max_true_plastic_strain": 0.25,
            "acknowledge_post_necking_approximation": True,
            "change_reason": "derive explicit reference hardening curve",
        },
    )
    assert created_model.status_code == 201
    body = created_model.json()
    assert body["current_revision"]["content"]["source_dataset_revision_id"] == str(
        DATASET_REVISION
    )
    assert body["current_revision"]["content"]["hardening_curve"]["point_count"] == 4
    assert body["current_revision"]["content"]["applicability"] == {
        "temperature_min_k": None,
        "temperature_max_k": None,
        "strain_rate_min_per_s": None,
        "strain_rate_max_per_s": None,
        "note": None,
    }

    curve = _request(
        application,
        "GET",
        f"/api/v1/tabulated-plasticity-models/{MODEL}/hardening-curve",
    )
    assert curve.status_code == 200
    assert curve.json()["points"][0]["origin"] == "catalog_yield_anchor"
    assert curve.json()["points"][-1]["origin"] == "approved_constant_extension"

    target = {"solver": "abaqus", "version": "2025", "unit_system": "kg_m_s"}
    preflight = _request(
        application,
        "POST",
        f"/api/v1/tabulated-plasticity-models/{MODEL}/mapping-preflight",
        json={"material_model_revision_id": str(MODEL_REVISION), "target": target},
    )
    assert preflight.status_code == 200
    mapping = preflight.json()
    assert mapping["exportable"] is True
    assert {item["status"] for item in mapping["items"]} >= {
        "exact",
        "transformed",
        "not_applicable",
    }

    created_card = _request(
        application,
        "POST",
        f"/api/v1/tabulated-plasticity-models/{MODEL}/solver-cards",
        json={
            "material_model_revision_id": str(MODEL_REVISION),
            "target": target,
            "expected_mapping_report_sha256": mapping["mapping_report_sha256"],
            "solver_material_id": 101,
            "material_name": "STEEL_REF",
            "change_reason": "generate explicit Abaqus reference card",
        },
    )
    assert created_card.status_code == 201
    assert created_card.json()["card"]["target"]["solver"] == "abaqus"

    preview = _request(
        application,
        "GET",
        f"/api/v1/elastoplastic-solver-cards/{CARD}/preview",
    )
    assert preview.status_code == 200
    assert "*MATERIAL, NAME=STEEL_REF" in preview.text
    assert "*ELASTIC, TYPE=ISOTROPIC" in preview.text
    assert "*PLASTIC, HARDENING=ISOTROPIC, EXTRAPOLATION=CONSTANT" in preview.text

    download = _request(
        application,
        "GET",
        f"/api/v1/elastoplastic-solver-cards/{CARD}/download",
    )
    assert download.status_code == 200
    assert download.headers["content-disposition"].endswith('.inp"')
    assert download.headers["x-cmp-card-sha256"]

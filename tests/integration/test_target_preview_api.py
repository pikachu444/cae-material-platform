from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import cast
from uuid import UUID

import httpx
from cmp.modules.exporting.adapters.api.target_preview import install_target_preview_api
from cmp.modules.exporting.application.target_preview import (
    TargetPreview,
    TargetPreviewConflict,
    TargetPreviewService,
)
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
    Permission,
    Role,
)
from cmp.modules.identity_access.domain.security import Principal, PrincipalType, SecurityContext
from fastapi import FastAPI, Request
from starlette.middleware.base import RequestResponseEndpoint
from starlette.responses import Response

IDS = tuple(UUID(int=value) for value in range(1, 10))
NOW = datetime(2026, 7, 26, tzinfo=UTC)
CONTEXT = SecurityContext(
    principal=Principal(IDS[0], PrincipalType.USER, "Target Preview", True),
    organization_id=IDS[1],
    project_id=IDS[2],
    issuer="https://idp.invalid",
    subject=str(IDS[0]),
    token_id="target-preview-test",
    groups=(),
    scopes=(),
    request_id=IDS[3],
    trace_id="target-preview-test",
    authenticated_at=NOW,
)
DECISION = AuthorizationDecision(
    principal_id=CONTEXT.principal.id,
    organization_id=CONTEXT.organization_id,
    project_id=CONTEXT.project_id,
    permission=Permission.EXPORT_READ,
    roles=(Role.TEST_ENGINEER,),
    database_permissions=(Permission.EXPORT_READ.value,),
    max_classification=DataClassification.INTERNAL,
    allow_export_controlled=False,
    request_id=CONTEXT.request_id,
    trace_id=CONTEXT.trace_id,
    decided_at=NOW,
)


class _Service:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.commands: list[object] = []

    async def preview(
        self, context: SecurityContext, decision: AuthorizationDecision, command: object
    ) -> TargetPreview:
        assert context is CONTEXT
        assert decision is DECISION
        self.commands.append(command)
        if self.error is not None:
            raise self.error
        return TargetPreview(
            preview_identity="a" * 64,
            filename="REFERENCE-abaqus-2025-cccccccccccc.inp",
            native_text="*MATERIAL, NAME=REFERENCE\n",
            native_sha256="c" * 64,
            mapping_report_sha256="d" * 64,
            mapping={
                "items": [
                    {
                        "name": "volumetric_response",
                        "ir_path": "/material_model_ir/volumetric_response",
                        "target_representation": "LAW82 nu",
                        "status": "approximated",
                        "detail": "Explicit acknowledged approximation.",
                    }
                ]
            },
            source={
                "processing_output_id": str(IDS[4]),
                "processing_output_revision_id": str(IDS[5]),
                "processing_output_sha256": "b" * 64,
                "material_id": str(IDS[0]),
                "material_revision_id": str(IDS[1]),
                "material_state_id": str(IDS[2]),
                "material_state_revision_id": str(IDS[3]),
                "material_model_ir_revision_id": str(IDS[6]),
                "neutral_material_id": str(IDS[7]),
                "neutral_material_revision_id": str(IDS[8]),
            },
            target={
                "solver": "abaqus",
                "version": "2025",
                "unit_system": "kg_m_s",
                "solver_material_id": "101",
                "material_name": "REFERENCE",
            },
            acknowledgement_identity="a" * 64,
        )


def _app(service: _Service | None) -> FastAPI:
    app = FastAPI()

    @app.middleware("http")
    async def scope(request: Request, call_next: RequestResponseEndpoint) -> Response:
        request.state.security_context = CONTEXT
        request.state.authorization_decision = DECISION
        return await call_next(request)

    def security() -> None:
        return None

    def read() -> None:
        return None

    install_target_preview_api(
        app,
        service=cast(TargetPreviewService | None, service),
        security_dependency=security,
        read_dependency=read,
    )
    return app


def _payload() -> dict[str, object]:
    return {
        "processing_output_id": str(IDS[4]),
        "processing_output_revision_id": str(IDS[5]),
        "neutral_material_id": str(IDS[7]),
        "neutral_material_revision_id": str(IDS[8]),
        "target": {"solver": "abaqus", "version": "2025", "unit_system": "kg_m_s"},
        "solver_material_id": 101,
        "material_name": "REFERENCE",
    }


def test_target_preview_api_returns_ephemeral_mapping_and_native_text() -> None:
    service = _Service()

    async def request() -> httpx.Response:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=_app(service)), base_url="http://test"
        ) as client:
            return await client.post("/api/v1/exporting/target-previews", json=_payload())

    response = asyncio.run(request())

    assert response.status_code == 200
    assert response.json()["mapping"]["items"] == [
        {
            "name": "volumetric_response",
            "ir_path": "/material_model_ir/volumetric_response",
            "target_representation": "LAW82 nu",
            "status": "approximated",
            "detail": "Explicit acknowledged approximation.",
        }
    ]
    assert response.json()["acknowledgement_identity"] == "a" * 64
    assert response.json()["delivery_status"] == "preview_only"
    assert len(service.commands) == 1


def test_target_preview_api_fail_closes_source_conflicts_and_unconfigured_service() -> None:
    conflict = _Service(TargetPreviewConflict("exact target-preview source is unavailable"))

    async def request(app: FastAPI) -> httpx.Response:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            return await client.post("/api/v1/exporting/target-previews", json=_payload())

    blocked = asyncio.run(request(_app(conflict)))
    unavailable = asyncio.run(request(_app(None)))

    assert blocked.status_code == 409
    assert blocked.json()["detail"] == "exact target-preview source is unavailable"
    assert unavailable.status_code == 503
    assert unavailable.json()["detail"] == "exact target-preview source resolver is unavailable"

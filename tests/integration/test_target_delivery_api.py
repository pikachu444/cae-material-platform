from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import cast
from uuid import UUID

import httpx
from cmp.modules.exporting.adapters.api.target_delivery import install_target_delivery_api
from cmp.modules.exporting.application.target_delivery import (
    DeliveryReceipt,
    TargetDeliveryConflict,
    TargetDeliveryService,
)
from cmp.modules.exporting.application.target_preview import TargetPreview
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

IDS = tuple(UUID(int=value) for value in range(1, 11))
NOW = datetime(2026, 7, 26, tzinfo=UTC)
CONTEXT = SecurityContext(
    Principal(IDS[0], PrincipalType.USER, "Target Delivery", True),
    IDS[1],
    IDS[2],
    "test",
    "deliver",
    "token",
    (),
    (),
    IDS[3],
    "target-delivery-test",
    NOW,
)
DECISION = AuthorizationDecision(
    IDS[0],
    IDS[1],
    IDS[2],
    Permission.EXPORT_EXECUTE,
    (Role.TEST_ENGINEER,),
    (Permission.EXPORT_EXECUTE.value, Permission.EXPORT_READ.value),
    DataClassification.INTERNAL,
    False,
    IDS[3],
    "target-delivery-test",
    NOW,
)


def _preview() -> TargetPreview:
    return TargetPreview(
        preview_identity="a" * 64,
        filename="REFERENCE.inp",
        native_text="*MATERIAL",
        native_sha256="b" * 64,
        mapping_report_sha256="c" * 64,
        mapping={"items": [{"status": "exact"}]},
        source={
            "processing_output_id": str(IDS[4]),
            "processing_output_revision_id": str(IDS[5]),
            "processing_output_sha256": "d" * 64,
            "material_id": str(IDS[6]),
            "material_revision_id": str(IDS[7]),
            "material_state_id": str(IDS[8]),
            "material_state_revision_id": str(IDS[9]),
            "material_model_ir_revision_id": str(IDS[4]),
            "neutral_material_id": str(IDS[6]),
            "neutral_material_revision_id": str(IDS[7]),
        },
        target={
            "solver": "abaqus",
            "version": "2025",
            "unit_system": "kg_m_s",
            "solver_material_id": "1",
            "material_name": "REFERENCE",
        },
        acknowledgement_identity=None,
    )


RECEIPT = DeliveryReceipt(
    IDS[3],
    "a" * 64,
    IDS[4],
    IDS[5],
    "REFERENCE.inp",
    "b" * 64,
    "c" * 64,
    ("exact",),
    _preview().source,
    _preview().target,
    NOW.isoformat(),
    IDS[0],
)


class _Service:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error

    async def deliver(self, *_: object) -> tuple[TargetPreview, DeliveryReceipt]:
        if self.error is not None:
            raise self.error
        return _preview(), RECEIPT

    def get_receipt(self, *_: object) -> DeliveryReceipt | None:
        return None if self.error is not None else RECEIPT


def _app(service: _Service | None) -> FastAPI:
    app = FastAPI()

    @app.middleware("http")
    async def scope(request: Request, call_next: RequestResponseEndpoint) -> Response:
        request.state.security_context = CONTEXT
        request.state.authorization_decision = DECISION
        return await call_next(request)

    def dependency() -> None:
        return None

    install_target_delivery_api(
        app,
        service=cast(TargetDeliveryService | None, service),
        security_dependency=dependency,
        read_dependency=dependency,
        execute_dependency=dependency,
    )
    return app


def _payload() -> dict[str, object]:
    return {
        "processing_output_id": str(IDS[4]),
        "processing_output_revision_id": str(IDS[5]),
        "neutral_material_id": str(IDS[6]),
        "neutral_material_revision_id": str(IDS[7]),
        "target": {"solver": "abaqus", "version": "2025", "unit_system": "kg_m_s"},
        "solver_material_id": 1,
        "material_name": "REFERENCE",
        "preview_identity": "a" * 64,
        "expected_mapping_report_sha256": "c" * 64,
    }


def test_delivery_post_and_receipt_get_return_the_same_immutable_evidence() -> None:
    async def request() -> tuple[httpx.Response, httpx.Response]:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=_app(_Service())),
            base_url="http://test",
        ) as client:
            delivered = await client.post("/api/v1/exporting/target-deliveries", json=_payload())
            receipt = await client.get(
                f"/api/v1/exporting/target-deliveries/{RECEIPT.receipt_id}"
            )
            return delivered, receipt

    delivered, receipt = asyncio.run(request())

    assert delivered.status_code == 200
    assert receipt.status_code == 200
    assert delivered.json() == receipt.json()
    response = delivered.json()
    assert response["links"]["receipt"].endswith(str(RECEIPT.receipt_id))
    assert response["target"]["solver_material_id"] == 1
    assert isinstance(response["target"]["solver_material_id"], int)
    assert receipt.json()["target"]["solver_material_id"] == 1
    assert isinstance(receipt.json()["target"]["solver_material_id"], int)


def test_delivery_api_fail_closes_conflict_missing_receipt_and_unconfigured_service() -> None:
    async def request(app: FastAPI) -> tuple[httpx.Response, httpx.Response]:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            return (
                await client.post("/api/v1/exporting/target-deliveries", json=_payload()),
                await client.get(f"/api/v1/exporting/target-deliveries/{RECEIPT.receipt_id}"),
            )

    conflict = asyncio.run(request(_app(_Service(TargetDeliveryConflict("stale preview")))))
    unavailable = asyncio.run(request(_app(None)))

    assert (conflict[0].status_code, conflict[1].status_code) == (409, 404)
    assert (unavailable[0].status_code, unavailable[1].status_code) == (503, 503)

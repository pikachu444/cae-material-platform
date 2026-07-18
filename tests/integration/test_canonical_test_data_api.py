from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
from uuid import UUID, uuid4

import httpx
import pytest
from cmp.modules.datasets.adapters.api.canonical_test_data import (
    install_canonical_test_data_api,
)
from cmp.modules.identity_access.application.authorization import database_permissions_for
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
    Permission,
    Role,
)
from cmp.modules.identity_access.domain.security import Principal, PrincipalType, SecurityContext
from fastapi import FastAPI, Request

NOW = datetime(2026, 7, 18, 17, 0, tzinfo=UTC)
ORG = UUID("de000000-0000-4000-8000-000000000001")
PROJECT = UUID("de000000-0000-4000-8000-000000000002")
ACTOR = UUID("de000000-0000-4000-8000-000000000003")


def _context() -> SecurityContext:
    return SecurityContext(
        principal=Principal(ACTOR, PrincipalType.USER, "Dataset User", True),
        organization_id=ORG,
        project_id=PROJECT,
        issuer="urn:cmp:test",
        subject=str(ACTOR),
        token_id=str(uuid4()),
        groups=(),
        scopes=("openid",),
        request_id=uuid4(),
        trace_id="00-000000000000000000000000000000de-00000000000000de-01",
        authenticated_at=NOW,
    )


CONTEXT = _context()


def _decision() -> AuthorizationDecision:
    return AuthorizationDecision(
        principal_id=ACTOR,
        organization_id=ORG,
        project_id=PROJECT,
        permission=Permission.DATASET_WRITE,
        roles=(Role.DATA_STEWARD,),
        database_permissions=database_permissions_for(Permission.DATASET_WRITE),
        max_classification=DataClassification.INTERNAL,
        allow_export_controlled=False,
        request_id=CONTEXT.request_id,
        trace_id=CONTEXT.trace_id,
        decided_at=NOW,
    )


def _app() -> FastAPI:
    app = FastAPI()

    async def security(request: Request) -> SecurityContext:
        request.state.security_context = CONTEXT
        return CONTEXT

    async def write(request: Request) -> AuthorizationDecision:
        decision = _decision()
        request.state.authorization_decision = decision
        return decision

    install_canonical_test_data_api(
        app,
        security_dependency=security,
        write_dependency=write,
    )
    return app


def _fixture() -> dict[str, Any]:
    root = Path(__file__).resolve().parents[2]
    return cast(
        dict[str, Any],
        json.loads(
            (root / "contracts/examples/positive/canonical-test-data.json").read_text(
                encoding="utf-8"
            )
        ),
    )


@pytest.mark.anyio
async def test_test_data_json_preview_preserves_metadata_units_and_missingness() -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=_app()), base_url="http://test"
    ) as client:
        response = await client.post("/api/v1/test-data:validate", json=_fixture())

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "valid"
    assert body["material_maker"] == "CMP Demo Metals"
    assert body["operator"] == "Kim Tester"
    assert body["point_count"] == 3
    assert body["channels"][1]["original_unit_string"] == "MPa"
    assert body["channels"][1]["normalized_unit"] == "Pa"
    assert body["channels"][1]["missing_count"] == 1
    assert body["canonical_document"]["channels"][1]["missing_reasons"][2] == (
        "instrument dropout"
    )


@pytest.mark.anyio
async def test_test_data_json_preview_rejects_incorrect_explicit_normalization() -> None:
    fixture = _fixture()
    fixture["channels"][1]["normalized_values"][1] = "204000000"
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=_app()), base_url="http://test"
    ) as client:
        response = await client.post("/api/v1/test-data:validate", json=fixture)

    assert response.status_code == 422
    assert "explicit normalization" in response.json()["detail"]

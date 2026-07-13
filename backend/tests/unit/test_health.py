import asyncio

import httpx
from cmp import __version__
from cmp.apps.api import create_app
from cmp.bootstrap.settings import Settings


def test_health_endpoint_returns_stable_contract() -> None:
    async def request_health() -> httpx.Response:
        transport = httpx.ASGITransport(app=create_app(Settings(environment="test")))
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.get("/api/v1/health")

    response = asyncio.run(request_health())

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "cmp-api",
        "version": __version__,
    }
    assert response.json()["version"] == "0.20.0"


def test_health_response_rejects_undocumented_fields() -> None:
    schema = create_app(Settings(environment="test")).openapi()["components"]["schemas"][
        "HealthResponse"
    ]

    assert schema["additionalProperties"] is False

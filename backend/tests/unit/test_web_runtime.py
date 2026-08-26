from __future__ import annotations

from pathlib import Path

import httpx
from cmp.apps.web import create_app
from fastapi.testclient import TestClient


def _static_root(tmp_path: Path) -> Path:
    root = tmp_path / "web build with spaces"
    (root / "assets").mkdir(parents=True)
    (root / "index.html").write_text("<main>CMP shell</main>", encoding="utf-8")
    (root / "assets" / "app.js").write_text("globalThis.cmp = true;", encoding="utf-8")
    return root


def test_web_runtime_serves_assets_and_spa_routes_without_node(tmp_path: Path) -> None:
    app = create_app(static_root=_static_root(tmp_path), api_target="http://127.0.0.1:8000")

    with TestClient(app) as client:
        assert client.get("/assets/app.js").text == "globalThis.cmp = true;"
        response = client.get("/materials/example")

    assert response.status_code == 200
    assert response.text == "<main>CMP shell</main>"


def test_web_runtime_proxies_api_through_the_web_front_door(tmp_path: Path) -> None:
    async def upstream(request: httpx.Request) -> httpx.Response:
        assert request.url == httpx.URL("http://127.0.0.1:8000/api/v1/health?detail=1")
        return httpx.Response(200, json={"status": "ok"}, headers={"x-cmp": "api"})

    app = create_app(
        static_root=_static_root(tmp_path),
        api_target="http://127.0.0.1:8000",
        transport=httpx.MockTransport(upstream),
    )

    with TestClient(app) as client:
        response = client.get("/api/v1/health?detail=1")

    assert response.json() == {"status": "ok"}
    assert response.headers["x-cmp"] == "api"


def test_web_runtime_rejects_a_missing_immutable_build(tmp_path: Path) -> None:
    missing = tmp_path / "missing"

    try:
        create_app(static_root=missing, api_target="http://127.0.0.1:8000")
    except ValueError as error:
        assert "missing index.html" in str(error)
    else:  # pragma: no cover - the assertion above is the behavior under test.
        raise AssertionError("missing build must fail closed")

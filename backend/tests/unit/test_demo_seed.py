from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest
from cmp.apps import demo_seed
from cmp.apps.demo_seed import _ensure_elastoplastic_models_and_cards, seed_demo


def _resource(
    stable_key: str,
    stable_id: str,
    revision_id: str,
    content: dict[str, Any],
) -> dict[str, Any]:
    return {stable_key: stable_id, "current_revision": {"id": revision_id, "content": content}}


class _DemoApi:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def wait_until_healthy(self) -> None:
        self.calls.append(("wait", "/health"))

    def authenticate(self) -> None:
        self.calls.append(("auth", "/demo-identity/token"))

    def get(self, path: str) -> dict[str, Any]:
        self.calls.append(("get", path))
        if path.startswith("/materials?"):
            return {"items": []}
        if path.endswith("/material-models") or path.endswith("/solver-cards"):
            return {"items": []}
        if path.endswith("/tabulated-plasticity-models"):
            return {"items": []}
        if path.endswith("/datasets") or path.endswith("/specimens") or path.endswith("/test-runs"):
            return {"items": []}
        if path.startswith("/dataset-selections/reference-tensile-replicates?"):
            return {"items": []}
        if path == "/test-methods":
            return {"items": []}
        raise AssertionError(f"unexpected GET {path}")

    def post(
        self,
        path: str,
        payload: Mapping[str, Any],
        *,
        headers: Mapping[str, str] | None = None,
    ) -> dict[str, Any]:
        del headers
        self.calls.append(("post", path))
        if path == "/materials":
            return _resource("material_id", "material-1", "material-r1", dict(payload["content"]))
        if path == "/materials/material-1/states":
            return _resource("material_state_id", "state-1", "state-r1", dict(payload["content"]))
        if path == "/material-states/state-1/property-sets":
            return _resource(
                "property_set_id",
                "properties-1",
                "properties-r1",
                dict(payload["content"]),
            )
        if path == "/material-states/state-1/material-models":
            return _resource("material_model_id", "model-1", "model-r1", {})
        if path == "/material-models/model-1/mapping-preflight":
            return {"mapping_report_sha256": "a" * 64}
        if path == "/material-models/model-1/solver-cards":
            return _resource("solver_card_id", "card-1", "card-r1", {})
        if path == "/material-states/state-1/specimens":
            return _resource(
                "specimen_id",
                "specimen-1",
                "specimen-r1",
                {"specimen_code": payload["specimen_code"]},
            )
        if path == "/test-methods/reference-uniaxial-tensile":
            return _resource(
                "test_method_id",
                "method-1",
                "method-r1",
                {"method_code": "reference_uniaxial_tensile"},
            )
        if path == "/test-runs":
            return _resource("test_run_id", "run-1", "run-r1", {"run_label": payload["run_label"]})
        if path == "/uploads":
            return {
                "upload": {"upload_id": "upload-1", "expected_part_count": 1},
                "upload_capability": "capability",
            }
        if path == "/uploads/upload-1:complete":
            return {
                "raw_asset": {"raw_asset_id": "raw-1"},
                "available_artifact_id": "artifact-1",
            }
        if path == "/datasets/reference-uniaxial-tensile:import":
            return _resource("dataset_id", "dataset-1", "dataset-r2", {})
        if path == "/dataset-selections/reference-tensile-replicates":
            return _resource("selection_id", "selection-1", "selection-r1", {})
        if path == "/material-states/state-1/tabulated-plasticity-models":
            return _resource("material_model_id", "plastic-model-1", "plastic-model-r1", {})
        if path == "/tabulated-plasticity-models/plastic-model-1/mapping-preflight":
            return {"mapping_report_sha256": "b" * 64}
        if path == "/tabulated-plasticity-models/plastic-model-1/solver-cards":
            return _resource("solver_card_id", "plastic-card-1", "plastic-card-r1", {})
        raise AssertionError(f"unexpected POST {path}")

    def put_bytes(self, path: str, payload: bytes, *, headers: Mapping[str, str]) -> dict[str, Any]:
        assert payload.startswith(b"engineering_strain")
        assert headers["Upload-Capability"] == "capability"
        self.calls.append(("put", path))
        return {"upload_id": "upload-1"}


def test_seed_uses_the_protected_material_to_card_and_dataset_http_flow() -> None:
    api = _DemoApi()

    seed_demo(api)  # type: ignore[arg-type]

    assert api.calls[:2] == [("wait", "/health"), ("auth", "/demo-identity/token")]
    assert ("post", "/materials") in api.calls
    assert ("post", "/material-states/state-1/material-models") in api.calls
    assert ("post", "/material-models/model-1/mapping-preflight") in api.calls
    assert ("post", "/material-models/model-1/solver-cards") in api.calls
    assert ("post", "/uploads") in api.calls
    assert ("put", "/uploads/upload-1/parts/1") in api.calls
    assert ("post", "/datasets/reference-uniaxial-tensile:import") in api.calls
    assert api.calls.count(("post", "/datasets/reference-uniaxial-tensile:import")) == 9
    assert ("post", "/dataset-selections/reference-tensile-replicates") in api.calls
    assert ("post", "/material-states/state-1/tabulated-plasticity-models") in api.calls
    assert (
        api.calls.count(("post", "/tabulated-plasticity-models/plastic-model-1/mapping-preflight"))
        == 2
    )
    assert (
        api.calls.count(("post", "/tabulated-plasticity-models/plastic-model-1/solver-cards")) == 2
    )


def test_demo_api_authenticates_as_administrator(monkeypatch: Any) -> None:
    requests: list[Any] = []

    class _Response:
        def __enter__(self) -> _Response:
            return self

        def __exit__(self, *args: Any) -> None:
            del args

        def read(self) -> bytes:
            return b'{"access_token":"administrator-token"}'

    def fake_urlopen(request: Any, timeout: int) -> _Response:
        assert timeout == 30
        requests.append(request)
        return _Response()

    monkeypatch.setattr(demo_seed, "urlopen", fake_urlopen)

    api = demo_seed.DemoApi("http://demo.local/api/v1")
    api.authenticate()

    assert len(requests) == 1
    assert requests[0].full_url == (
        "http://demo.local/api/v1/demo-identity/token?persona=administrator"
    )


def test_demo_api_timeout_override_is_bounded_and_reports_exact_request(
    monkeypatch: Any,
) -> None:
    requests: list[float] = []

    def fake_urlopen(request: Any, timeout: float) -> Any:
        del request
        requests.append(timeout)
        raise TimeoutError("socket timed out")

    monkeypatch.setattr(demo_seed, "urlopen", fake_urlopen)

    api = demo_seed.DemoApi("http://demo.local/api/v1")
    api._token = "administrator-token"

    with pytest.raises(
        demo_seed.DemoSeedError,
        match=r"demo API POST /catalog/schema-definition-bundles:apply timed out after 180 seconds",
    ):
        api.post(
            "/catalog/schema-definition-bundles:apply",
            {},
            timeout=180,
        )

    assert requests == [180]
    with pytest.raises(ValueError, match="timeout must be positive"):
        api.post("/catalog/schema-definition-bundles:apply", {}, timeout=0)


class _ExistingElastoplasticApi:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def get(self, path: str) -> dict[str, Any]:
        self.calls.append(("get", path))
        if path == "/material-states/state-1/tabulated-plasticity-models":
            return {
                "items": [
                    _resource(
                        "material_model_id",
                        "processed-model",
                        "processed-model-r1",
                        {
                            "source_dataset_revision_id": None,
                            "processing_projection": {"output_revision_id": "output-r1"},
                        },
                    ),
                    _resource(
                        "material_model_id",
                        "direct-model",
                        "direct-model-r1",
                        {
                            "source_dataset_revision_id": "dataset-r2",
                            "processing_projection": None,
                        },
                    ),
                ]
            }
        if path == "/tabulated-plasticity-models/direct-model/solver-cards":
            return {
                "items": [
                    {"target": {"solver": "openradioss"}},
                    {"target": {"solver": "abaqus"}},
                ]
            }
        raise AssertionError(f"unexpected GET {path}")

    def post(
        self,
        path: str,
        payload: Mapping[str, Any],
        *,
        headers: Mapping[str, str] | None = None,
    ) -> dict[str, Any]:
        del payload, headers
        raise AssertionError(f"reseed unexpectedly wrote {path}")


def test_reseed_selects_the_direct_dataset_model_instead_of_a_processed_projection() -> None:
    api = _ExistingElastoplasticApi()

    _ensure_elastoplastic_models_and_cards(
        api,  # type: ignore[arg-type]
        _resource("material_state_id", "state-1", "state-r1", {}),
        _resource("property_set_id", "properties-1", "properties-r1", {}),
        _resource("dataset_id", "dataset-1", "dataset-r2", {}),
    )

    assert api.calls == [
        ("get", "/material-states/state-1/tabulated-plasticity-models"),
        ("get", "/tabulated-plasticity-models/direct-model/solver-cards"),
    ]

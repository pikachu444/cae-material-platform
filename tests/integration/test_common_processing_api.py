from __future__ import annotations

import json
from pathlib import Path

import httpx
from cmp.modules.processing.adapters.api.common_pipeline import install_common_processing_api
from fastapi import FastAPI


async def _allow() -> object:
    return object()


def _app() -> FastAPI:
    app = FastAPI()
    install_common_processing_api(
        app,
        security_dependency=_allow,
        read_dependency=_allow,
        execute_dependency=_allow,
    )
    return app


def _document() -> dict[str, object]:
    path = Path("contracts/examples/positive/canonical-test-data.json")
    value: dict[str, object] = json.loads(path.read_text(encoding="utf-8"))
    return value


async def _request(method: str, url: str, *, json_body: object | None = None) -> httpx.Response:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=_app()), base_url="http://test"
    ) as client:
        return await client.request(method, url, json=json_body)


def test_method_registry_and_preview_share_the_versioned_contract() -> None:
    import asyncio

    methods = asyncio.run(_request("GET", "/api/v1/processing-methods"))
    assert methods.status_code == 200
    assert len(methods.json()["items"]) == 14
    assert methods.json()["items"][0]["method_id"] == "rows.sort_unique"

    preview = asyncio.run(
        _request(
            "POST",
            "/api/v1/processing:preview",
            json_body={
                "document": _document(),
                "mapping_profile": {
                    "profile_key": "tensile-normalized",
                    "label": "Normalized tensile channels",
                    "independent_quantity": "strain.engineering",
                    "missing_data_policy": "drop_any",
                    "bindings": [
                        {
                            "channel_key": "engineering_strain",
                            "target_quantity": "strain.engineering",
                            "accepted_normalized_units": ["1"],
                        },
                        {
                            "channel_key": "engineering_stress",
                            "target_quantity": "stress.engineering",
                            "accepted_normalized_units": ["Pa"],
                        },
                    ],
                },
                "steps": [
                    {
                        "method_id": "rows.sort_unique",
                        "method_version": "1.0.0",
                        "options": {"duplicate_policy": "reject"},
                    },
                    {
                        "method_id": "curve.resample_linear",
                        "method_version": "1.0.0",
                        "options": {
                            "start": 0.0,
                            "end": 0.001,
                            "count": 5,
                            "extrapolation": "reject",
                        },
                    },
                ],
            },
        )
    )
    assert preview.status_code == 200, preview.text
    body = preview.json()
    assert body["execution_mode"] == "preview"
    assert body["promotable"] is False
    assert [stage["method_id"] for stage in body["stages"]] == [
        "mapping",
        "rows.sort_unique",
        "curve.resample_linear",
    ]
    assert body["stages"][-1]["point_count"] == 5


def test_preview_rejects_unknown_method_and_hidden_extrapolation() -> None:
    import asyncio

    base = {
        "document": _document(),
        "mapping_profile": {
            "profile_key": "tensile-normalized",
            "label": "Normalized tensile channels",
            "independent_quantity": "strain.engineering",
            "missing_data_policy": "drop_any",
            "bindings": [
                {
                    "channel_key": "engineering_strain",
                    "target_quantity": "strain.engineering",
                    "accepted_normalized_units": ["1"],
                },
                {
                    "channel_key": "engineering_stress",
                    "target_quantity": "stress.engineering",
                    "accepted_normalized_units": ["Pa"],
                },
            ],
        },
    }
    unknown = asyncio.run(
        _request(
            "POST",
            "/api/v1/processing:preview",
            json_body={
                **base,
                "steps": [{"method_id": "solver.secret", "method_version": "1.0.0", "options": {}}],
            },
        )
    )
    assert unknown.status_code == 422
    assert "unknown processing method" in unknown.text

    extrapolation = asyncio.run(
        _request(
            "POST",
            "/api/v1/processing:preview",
            json_body={
                **base,
                "steps": [
                    {
                        "method_id": "rows.sort_unique",
                        "method_version": "1.0.0",
                        "options": {"duplicate_policy": "reject"},
                    },
                    {
                        "method_id": "curve.resample_linear",
                        "method_version": "1.0.0",
                        "options": {
                            "start": -0.01,
                            "end": 0.001,
                            "count": 5,
                            "extrapolation": "reject",
                        },
                    },
                ],
            },
        )
    )
    assert extrapolation.status_code == 422
    assert "extrapolate" in extrapolation.text


def test_ensemble_registry_alignment_and_pointwise_statistics_contract() -> None:
    import asyncio

    methods = asyncio.run(_request("GET", "/api/v1/processing-ensemble-methods"))
    assert methods.status_code == 200
    assert [item["method_id"] for item in methods.json()["items"]] == [
        "curves.align_linear_intersection",
        "curves.pointwise_statistics",
    ]
    first = _document()
    second = json.loads(json.dumps(first))
    second["document_id"] = "DP600-TENSILE-REPLICATE-02"
    response = asyncio.run(
        _request(
            "POST",
            "/api/v1/processing:preview-ensemble",
            json_body={
                "documents": [first, second],
                "mapping_profile": {
                    "profile_key": "tensile-normalized",
                    "label": "Normalized tensile channels",
                    "independent_quantity": "strain.engineering",
                    "missing_data_policy": "drop_any",
                    "bindings": [
                        {
                            "channel_key": "engineering_strain",
                            "target_quantity": "strain.engineering",
                            "accepted_normalized_units": ["1"],
                        },
                        {
                            "channel_key": "engineering_stress",
                            "target_quantity": "stress.engineering",
                            "accepted_normalized_units": ["Pa"],
                        },
                    ],
                },
                "preprocessing_steps": [
                    {
                        "method_id": "rows.sort_unique",
                        "method_version": "1.0.0",
                        "options": {"duplicate_policy": "reject"},
                    }
                ],
                "alignment": {
                    "point_count": 3,
                    "domain_policy": "intersection",
                    "extrapolation": "reject",
                },
            },
        )
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["promotable"] is False
    assert len(body["members"]) == 2
    assert body["members"][0]["stage"]["method_id"] == "curves.align_linear_intersection"
    assert body["statistics"][0]["quantity"] == "stress.engineering"
    assert body["statistics"][0]["standard_deviation"] == [0.0, 0.0, 0.0]

"""Seed a synthetic end-to-end Material-to-card demo through the protected API.

The seed process has no database connection.  It deliberately calls the same
HTTP resources as the browser, using the explicit demo issuer's short-lived
token, so revision, authorization, RLS, provenance, and artifact handling all
remain in the exercised path.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4

_MATERIAL_CODE = "CMP-DEMO-DP780"
_STATE_NAME = "As received · synthetic reference"
_TENSILE_REPLICATES = (
    ("CMP-DEMO-DP780-T-001", "CMP demo tensile replicate 1", 0, 1.00),
    ("CMP-DEMO-DP780-T-002", "CMP demo tensile replicate 2", 1, 0.97),
    ("CMP-DEMO-DP780-T-003", "CMP demo tensile replicate 3", 2, 1.04),
)
_TENSILE_HOLDOUT = (
    "CMP-DEMO-DP780-T-004",
    "CMP demo tensile holdout",
    3,
    1.02,
)
_CSV_TEMPLATE = """engineering_strain,engineering_stress_mpa
0.0000,0
0.0005,{v1}
0.0010,{v2}
0.0020,{v3}
0.0050,{v4}
0.0100,{v5}
0.0200,{v6}
0.0300,{v7}
"""


def _replicate_csv(scale: float) -> bytes:
    values = [105, 210, 350, 450, 540, 620, 600]
    return _CSV_TEMPLATE.format(
        **{f"v{index}": f"{value * scale:.3f}" for index, value in enumerate(values, 1)}
    ).encode()


class DemoSeedError(RuntimeError):
    """The local composition is not ready or rejected a synthetic request."""


class DemoApi:
    def __init__(self, base_url: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._token: str | None = None

    def wait_until_healthy(self, attempts: int = 60) -> None:
        for attempt in range(attempts):
            try:
                response = self._request("/health", authenticated=False)
            except DemoSeedError:
                if attempt == attempts - 1:
                    raise
                time.sleep(1)
                continue
            if response.get("status") == "ok":
                return
            time.sleep(1)
        raise DemoSeedError("API health endpoint did not report ready")

    def authenticate(self) -> None:
        response = self._request("/demo-identity/token", authenticated=False)
        token = response.get("access_token")
        if not isinstance(token, str) or not token:
            raise DemoSeedError("explicit local demo identity did not return an access token")
        self._token = token

    def get(self, path: str) -> dict[str, Any]:
        return self._request(path)

    def post(
        self,
        path: str,
        payload: Mapping[str, Any],
        *,
        headers: Mapping[str, str] | None = None,
    ) -> dict[str, Any]:
        return self._request(path, method="POST", payload=payload, headers=headers)

    def put_bytes(self, path: str, payload: bytes, *, headers: Mapping[str, str]) -> dict[str, Any]:
        return self._request(path, method="PUT", body=payload, headers=headers)

    def _request(
        self,
        path: str,
        *,
        method: str = "GET",
        payload: Mapping[str, Any] | None = None,
        body: bytes | None = None,
        headers: Mapping[str, str] | None = None,
        authenticated: bool = True,
    ) -> dict[str, Any]:
        request_headers = {"Accept": "application/json", **(headers or {})}
        if authenticated:
            if self._token is None:
                raise DemoSeedError("demo API request attempted before token acquisition")
            request_headers["Authorization"] = f"Bearer {self._token}"
        if payload is not None:
            body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
            request_headers.setdefault("Content-Type", "application/json")
        request = Request(
            f"{self._base_url}{path}", data=body, headers=request_headers, method=method
        )
        try:
            with urlopen(request, timeout=30) as response:
                content = response.read()
        except HTTPError as error:
            detail = error.read(2048).decode("utf-8", errors="replace")
            raise DemoSeedError(
                f"demo API {method} {path} returned {error.code}: {detail[:512]}"
            ) from error
        except URLError as error:
            raise DemoSeedError(f"demo API {method} {path} is unavailable") from error
        try:
            value = json.loads(content)
        except json.JSONDecodeError as error:
            raise DemoSeedError(f"demo API {method} {path} returned invalid JSON") from error
        if not isinstance(value, dict):
            raise DemoSeedError(f"demo API {method} {path} returned an unexpected payload")
        return value


def _current_id(record: Mapping[str, Any], stable_key: str) -> str:
    value = record.get(stable_key)
    if not isinstance(value, str) or not value:
        raise DemoSeedError(f"demo API response did not contain {stable_key}")
    return value


def _revision_id(record: Mapping[str, Any]) -> str:
    revision = record.get("current_revision")
    if not isinstance(revision, Mapping):
        raise DemoSeedError("demo API response did not contain current_revision")
    value = revision.get("id")
    if not isinstance(value, str) or not value:
        raise DemoSeedError("demo API response did not contain current revision ID")
    return value


def _find(
    items: object, predicate: Callable[[dict[str, Any]], bool]
) -> dict[str, Any] | None:
    if not isinstance(items, list):
        return None
    for value in items:
        if isinstance(value, dict) and predicate(value):
            return value
    return None


def _ensure_material(api: DemoApi) -> dict[str, Any]:
    listed = api.get(f"/materials?q={_MATERIAL_CODE}&limit=20")
    found = _find(
        listed.get("items"),
        lambda item: isinstance(item.get("current_revision"), dict)
        and item["current_revision"].get("content", {}).get("material_code") == _MATERIAL_CODE,
    )
    if found is not None:
        return api.get(f"/materials/{_current_id(found, 'material_id')}")
    material = api.post(
        "/materials",
        {
            "classification": "internal",
            "content": {
                "name": "DP780 synthetic demo steel",
                "material_code": _MATERIAL_CODE,
                "material_family": "dual-phase steel",
                "description": "Synthetic local-demo data; not validated engineering data.",
            },
            "change_reason": "Seed the local Material-to-card demonstration.",
        },
    )
    return {"material": material, "states": [], "property_sets": []}


def _ensure_state(api: DemoApi, detail: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    material = detail.get("material")
    if not isinstance(material, dict):
        raise DemoSeedError("Material detail did not contain the Material")
    existing = _find(
        detail.get("states"),
        lambda item: isinstance(item.get("current_revision"), dict)
        and item["current_revision"].get("content", {}).get("name") == _STATE_NAME,
    )
    if existing is not None:
        return material, existing
    state = api.post(
        f"/materials/{_current_id(material, 'material_id')}/states",
        {
            "content": {
                "material_revision_id": _revision_id(material),
                "name": _STATE_NAME,
                "manufacturing_route": "Synthetic reference production route",
                "heat_treatment": None,
                "lot_or_batch": "CMP-DEMO-LOT-001",
                "description": "Reference-only state created by the local demo seed.",
            },
            "change_reason": "Seed the local Material State demonstration.",
        },
    )
    return material, state


def _ensure_properties(
    api: DemoApi, detail: Mapping[str, Any], state: Mapping[str, Any]
) -> dict[str, Any]:
    state_id = _current_id(state, "material_state_id")
    existing = _find(
        detail.get("property_sets"),
        lambda item: item.get("material_state_id") == state_id,
    )
    if existing is not None:
        return existing
    source = {"kind": "manual", "reference": "Synthetic local demo input"}
    return api.post(
        f"/material-states/{state_id}/property-sets",
        {
            "content": {
                "material_state_revision_id": _revision_id(state),
                "density_kg_per_m3": 7800.0,
                "density_source": source,
                "youngs_modulus_pa": 210000000000.0,
                "youngs_modulus_source": source,
                "poisson_ratio": 0.3,
                "poisson_ratio_source": source,
                "yield_stress_pa": 450000000.0,
                "yield_stress_source": source,
                "applicability": {
                    "temperature_min_k": 293.15,
                    "temperature_max_k": 293.15,
                    "strain_rate_min_per_s": None,
                    "strain_rate_max_per_s": None,
                    "note": "Synthetic local demo scope only.",
                },
            },
            "change_reason": "Seed typed basic properties for the local demo.",
        },
    )


def _ensure_model_and_card(
    api: DemoApi, state: Mapping[str, Any], properties: Mapping[str, Any]
) -> None:
    state_id = _current_id(state, "material_state_id")
    models = api.get(f"/material-states/{state_id}/material-models")
    model = _find(models.get("items"), lambda _: True)
    if model is None:
        model = api.post(
            f"/material-states/{state_id}/material-models",
            {
                "property_set_revision_id": _revision_id(properties),
                "change_reason": "Create the reference linear-elastic IR for the local demo.",
            },
        )
    model_id = _current_id(model, "material_model_id")
    cards = api.get(f"/material-models/{model_id}/solver-cards")
    if _find(cards.get("items"), lambda _: True) is not None:
        return
    target = {"solver": "openradioss", "version": "2025", "unit_system": "kg_m_s"}
    report = api.post(f"/material-models/{model_id}/mapping-preflight", {"target": target})
    digest = report.get("mapping_report_sha256")
    if not isinstance(digest, str) or not digest:
        raise DemoSeedError("mapping preflight did not return a report digest")
    api.post(
        f"/material-models/{model_id}/solver-cards",
        {
            "material_model_revision_id": _revision_id(model),
            "target": target,
            "expected_mapping_report_sha256": digest,
            "solver_material_id": 780,
            "card_title": "CMP demo DP780 elastic",
            "change_reason": "Generate the local demo OpenRadioss reference card.",
        },
    )


def _ensure_tensile_dataset(
    api: DemoApi,
    material: Mapping[str, Any],
    state: Mapping[str, Any],
    *,
    specimen_code: str,
    run_label: str,
    day_offset: int,
    csv: bytes,
) -> dict[str, Any]:
    state_id = _current_id(state, "material_state_id")
    specimens = api.get(f"/material-states/{state_id}/specimens")
    specimen = _find(
        specimens.get("items"),
        lambda item: isinstance(item.get("current_revision"), dict)
        and item["current_revision"].get("content", {}).get("specimen_code") == specimen_code,
    )
    if specimen is None:
        specimen = api.post(
            f"/material-states/{state_id}/specimens",
            {
                "material_state_revision_id": _revision_id(state),
                "specimen_code": specimen_code,
                "orientation": "RD",
                "preparation_note": "Synthetic local-demo specimen.",
                "change_reason": "Seed a reference tensile specimen for the local demo.",
            },
        )
    methods = api.get("/test-methods")
    method = _find(
        methods.get("items"),
        lambda item: isinstance(item.get("current_revision"), dict)
        and item["current_revision"].get("content", {}).get("method_code")
        == "reference_uniaxial_tensile",
    )
    if method is None:
        method = api.post(
            "/test-methods/reference-uniaxial-tensile",
            {
                "classification": "internal",
                "change_reason": "Seed the reference tensile method for the local demo.",
            },
        )
    runs = api.get(f"/material-states/{state_id}/test-runs")
    run = _find(
        runs.get("items"),
        lambda item: isinstance(item.get("current_revision"), dict)
        and item["current_revision"].get("content", {}).get("run_label") == run_label,
    )
    if run is None:
        run = api.post(
            "/test-runs",
            {
                "specimen_id": _current_id(specimen, "specimen_id"),
                "specimen_revision_id": _revision_id(specimen),
                "test_method_id": _current_id(method, "test_method_id"),
                "test_method_revision_id": _revision_id(method),
                "run_label": run_label,
                "performed_at": datetime(
                    2026, 1, 15 + day_offset, 10, 0, tzinfo=UTC
                ).isoformat(),
                "test_temperature_k": 293.15,
                "crosshead_speed_mm_per_min": 5.0,
                "change_reason": "Seed a reference tensile Test Run for the local demo.",
            },
        )
    datasets = api.get(f"/material-states/{state_id}/datasets")
    existing = _find(
        datasets.get("items"),
        lambda item: item.get("test_run_id") == _current_id(run, "test_run_id"),
    )
    if existing is not None:
        return existing
    digest = hashlib.sha256(csv).hexdigest()
    upload = api.post(
        "/uploads",
        {
            "classification": "internal",
            "original_filename": f"{specimen_code.lower()}-tensile.csv",
            "media_type": "text/csv",
            "expected_size_bytes": len(csv),
            "expected_sha256": digest,
            "test_run_revision_id": _revision_id(run),
        },
        headers={"Idempotency-Key": str(uuid4())},
    )
    upload_session = upload.get("upload")
    capability = upload.get("upload_capability")
    if not isinstance(upload_session, dict) or not isinstance(capability, str):
        raise DemoSeedError("upload creation did not return a session and capability")
    upload_id = _current_id(upload_session, "upload_id")
    api.put_bytes(
        f"/uploads/{upload_id}/parts/1",
        csv,
        headers={"Content-Type": "text/csv", "Upload-Capability": capability},
    )
    completed = api.post(
        f"/uploads/{upload_id}:complete", {}, headers={"Upload-Capability": capability}
    )
    raw_asset = completed.get("raw_asset")
    artifact_id = completed.get("available_artifact_id")
    if not isinstance(raw_asset, dict) or not isinstance(artifact_id, str):
        raise DemoSeedError("completed raw CSV did not produce an immutable Artifact")
    dataset = api.post(
        "/datasets/reference-uniaxial-tensile:import",
        {
            "test_run_id": _current_id(run, "test_run_id"),
            "test_run_revision_id": _revision_id(run),
            "raw_asset_id": _current_id(raw_asset, "raw_asset_id"),
            "raw_artifact_id": artifact_id,
            "mapping": {
                "strain_column": "engineering_strain",
                "stress_column": "engineering_stress_mpa",
                "strain_unit": "1",
                "stress_unit": "MPa",
            },
            "change_reason": (
                "Create raw and normalized reference tensile Dataset revisions for the local demo."
            ),
        },
    )
    del material
    return dataset


def _ensure_replicate_selection(
    api: DemoApi, state: Mapping[str, Any], datasets: Sequence[Mapping[str, Any]]
) -> None:
    state_id = _current_id(state, "material_state_id")
    selections = api.get(
        f"/dataset-selections/reference-tensile-replicates?material_state_id={state_id}"
    )
    if _find(selections.get("items"), lambda _: True) is not None:
        return
    api.post(
        "/dataset-selections/reference-tensile-replicates",
        {
            "classification": "internal",
            "selection_label": "CMP demo DP780 tensile replicates",
            "dataset_revision_ids": [_revision_id(dataset) for dataset in datasets],
            "change_reason": "Pin three independent synthetic tensile runs for comparison.",
        },
    )


def _ensure_elastoplastic_models_and_cards(
    api: DemoApi,
    state: Mapping[str, Any],
    properties: Mapping[str, Any],
    dataset: Mapping[str, Any],
) -> None:
    state_id = _current_id(state, "material_state_id")
    models = api.get(f"/material-states/{state_id}/tabulated-plasticity-models")
    model = _find(models.get("items"), lambda _: True)
    if model is None:
        model = api.post(
            f"/material-states/{state_id}/tabulated-plasticity-models",
            {
                "property_set_revision_id": _revision_id(properties),
                "dataset_revision_id": _revision_id(dataset),
                "extension_max_true_plastic_strain": 0.25,
                "acknowledge_post_necking_approximation": True,
                "change_reason": (
                    "Derive the reference pre-necking tabulated-plasticity IR for the demo."
                ),
            },
        )
    model_id = _current_id(model, "material_model_id")
    cards = api.get(f"/tabulated-plasticity-models/{model_id}/solver-cards")
    existing = cards.get("items")
    for solver, solver_material_id in (("openradioss", 781), ("abaqus", 782)):
        def matches_solver(item: dict[str, Any], expected_solver: str = solver) -> bool:
            target = item.get("target")
            return isinstance(target, dict) and target.get("solver") == expected_solver

        if _find(
            existing,
            matches_solver,
        ) is not None:
            continue
        target = {"solver": solver, "version": "2025", "unit_system": "kg_m_s"}
        report = api.post(
            f"/tabulated-plasticity-models/{model_id}/mapping-preflight",
            {
                "material_model_revision_id": _revision_id(model),
                "target": target,
            },
        )
        digest = report.get("mapping_report_sha256")
        if not isinstance(digest, str) or not digest:
            raise DemoSeedError("elastoplastic preflight did not return a report digest")
        api.post(
            f"/tabulated-plasticity-models/{model_id}/solver-cards",
            {
                "material_model_revision_id": _revision_id(model),
                "target": target,
                "expected_mapping_report_sha256": digest,
                "solver_material_id": solver_material_id,
                "material_name": "CMP_DEMO_DP780",
                "change_reason": f"Generate the local demo {solver} elastoplastic card.",
            },
        )


def seed_demo(api: DemoApi) -> None:
    api.wait_until_healthy()
    api.authenticate()
    detail = _ensure_material(api)
    material, state = _ensure_state(api, detail)
    properties = _ensure_properties(api, detail, state)
    _ensure_model_and_card(api, state, properties)
    datasets = [
        _ensure_tensile_dataset(
            api,
            material,
            state,
            specimen_code=specimen_code,
            run_label=run_label,
            day_offset=day_offset,
            csv=_replicate_csv(scale),
        )
        for specimen_code, run_label, day_offset, scale in _TENSILE_REPLICATES
    ]
    _ensure_replicate_selection(api, state, datasets)
    specimen_code, run_label, day_offset, scale = _TENSILE_HOLDOUT
    _ensure_tensile_dataset(
        api,
        material,
        state,
        specimen_code=specimen_code,
        run_label=run_label,
        day_offset=day_offset,
        csv=_replicate_csv(scale),
    )
    _ensure_elastoplastic_models_and_cards(api, state, properties, datasets[0])


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Seed the synthetic local CMP end-to-end demo.")
    parser.add_argument(
        "--api-base-url",
        default=os.getenv("CMP_DEMO_API_BASE_URL", "http://127.0.0.1:8000/api/v1"),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    seed_demo(DemoApi(args.api_base_url))
    print("CMP local demo seed completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Deterministic small Python client generator for the HTTP contract."""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast

import yaml


def _load_contract(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("OpenAPI contract must be a mapping")
    return cast(dict[str, Any], data)


def _health_path(contract: Mapping[str, Any]) -> str:
    paths = contract.get("paths")
    if not isinstance(paths, dict):
        raise ValueError("OpenAPI contract has no paths mapping")
    for path, item in paths.items():
        if not isinstance(path, str) or not isinstance(item, dict):
            continue
        operation = item.get("get")
        if isinstance(operation, dict) and operation.get("operationId") == "getHealth":
            return path
    raise ValueError("OpenAPI contract has no getHealth operation")


def render_client(contract_path: Path) -> str:
    """Render the health client plus the additive calibration operations."""

    contract = _load_contract(contract_path)
    path = _health_path(contract)
    return f'''"""Generated from contracts/http/openapi.yaml; do not edit manually."""

from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.request import Request, urlopen


@dataclass(frozen=True, slots=True)
class HealthResponse:
    status: str
    service: str
    version: str


class Client:
    def __init__(self, base_url: str, timeout_seconds: float = 5.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds

    def get_health(self) -> HealthResponse:
        request = Request(self._base_url + "{path}", method="GET")
        with urlopen(request, timeout=self._timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("health response must be a JSON object")
        return HealthResponse(
            status=str(payload["status"]),
            service=str(payload["service"]),
            version=str(payload["version"]),
        )

    def create_reference_shear_dma_frequency_sweep_test_method(self, payload: object) -> object:
        return self._request_json(
            "POST", "/api/v1/test-methods/reference-shear-dma-frequency-sweep", payload
        )

    def create_reference_shear_dma_frequency_sweep_test_run(self, payload: object) -> object:
        return self._request_json(
            "POST", "/api/v1/test-runs/reference-shear-dma-frequency-sweep", payload
        )

    def _request_json(
        self,
        method: str,
        path: str,
        payload: object | None = None,
        *,
        idempotency_key: str | None = None,
    ) -> object:
        data = (
            None
            if payload is None
            else json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        )
        headers = {{"Content-Type": "application/json"}} if data is not None else {{}}
        if idempotency_key is not None:
            headers["Idempotency-Key"] = idempotency_key
        request = Request(self._base_url + path, data=data, headers=headers, method=method)
        with urlopen(request, timeout=self._timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))

    def create_linear_viscoelastic_calibration_plan(
        self, payload: object, *, idempotency_key: str | None = None
    ) -> object:
        return self._request_json(
            "POST",
            "/api/v1/linear-viscoelastic-calibration-plans",
            payload,
            idempotency_key=idempotency_key,
        )

    def recommend_dma_frequency_master_curve(self, payload: object) -> object:
        return self._request_json(
            "POST", "/api/v1/processing/dma-frequency-master-curves/recommendations", payload
        )

    def create_dma_frequency_master_curve(self, payload: object) -> object:
        return self._request_json(
            "POST", "/api/v1/processing/dma-frequency-master-curves", payload
        )

    def create_linear_viscoelastic_calibration_plan_from_processing_output(
        self, payload: object, *, idempotency_key: str | None = None
    ) -> object:
        return self._request_json(
            "POST",
            "/api/v1/linear-viscoelastic-calibration-plans/from-processing-output",
            payload,
            idempotency_key=idempotency_key,
        )

    def get_linear_viscoelastic_calibration_plan(self, plan_id: str) -> object:
        return self._request_json("GET", "/api/v1/linear-viscoelastic-calibration-plans/" + plan_id)

    def create_linear_viscoelastic_calibration_run(
        self, plan_id: str, payload: object, *, idempotency_key: str
    ) -> object:
        return self._request_json(
            "POST",
            "/api/v1/linear-viscoelastic-calibration-plans/" + plan_id + "/runs",
            payload,
            idempotency_key=idempotency_key,
        )

    def get_linear_viscoelastic_calibration_run(self, run_id: str) -> object:
        return self._request_json("GET", "/api/v1/linear-viscoelastic-calibration-runs/" + run_id)

    def list_linear_viscoelastic_calibration_candidates(self, run_id: str) -> object:
        return self._request_json(
            "GET", "/api/v1/linear-viscoelastic-calibration-runs/" + run_id + "/candidates"
        )

    def get_linear_viscoelastic_calibration_recommendation(self, run_id: str) -> object:
        return self._request_json(
            "GET",
            "/api/v1/linear-viscoelastic-calibration-runs/" + run_id + "/recommendation",
        )

    def create_linear_viscoelastic_calibration_selection(
        self, payload: object, *, idempotency_key: str | None = None
    ) -> object:
        return self._request_json(
            "POST",
            "/api/v1/linear-viscoelastic-calibration-selections",
            payload,
            idempotency_key=idempotency_key,
        )

    def get_linear_viscoelastic_calibration_selection(self, selection_id: str) -> object:
        return self._request_json(
            "GET", "/api/v1/linear-viscoelastic-calibration-selections/" + selection_id
        )

    def promote_linear_viscoelastic_calibration_selection(
        self, selection_id: str, payload: object
    ) -> object:
        return self._request_json(
            "POST",
            "/api/v1/linear-viscoelastic-calibration-selections/"
            + selection_id
            + "/linear-viscoelastic-model",
            payload,
        )
'''


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate the baseline Python API client.")
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render_client(args.contract), encoding="utf-8")
    print(f"generated {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

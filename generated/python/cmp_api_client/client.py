"""Generated from contracts/http/openapi.yaml; do not edit manually."""

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
        request = Request(self._base_url + "/api/v1/health", method="GET")
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
        headers = {"Content-Type": "application/json"} if data is not None else {}
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

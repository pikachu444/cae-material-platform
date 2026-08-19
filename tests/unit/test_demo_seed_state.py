from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from cmp.apps import demo_seed


class _StateApi(demo_seed.DemoApi):
    def __init__(self) -> None:
        self.writes: list[dict[str, Any]] = []

    def post(
        self,
        path: str,
        payload: Mapping[str, Any],
        *,
        headers: Mapping[str, str] | None = None,
    ) -> dict[str, Any]:
        self.writes.append({"path": path, "payload": deepcopy(payload), "headers": headers})
        return {
            "material_state_id": "state-1",
            "current_revision": {
                "id": "state-revision-2",
                "revision_no": 2,
                "content_hash": "b" * 64,
                "change_reason": payload["change_reason"],
                "content": deepcopy(payload["content"]),
            },
        }


def test_state_route_repair_is_one_immutable_revision_then_stable() -> None:
    material = {
        "material_id": "material-1",
        "current_revision": {"id": "material-revision-1"},
    }
    detail = {
        "material": material,
        "states": [{
            "material_state_id": "state-1",
            "current_revision": {
                "id": "state-revision-1",
                "revision_no": 1,
                "content_hash": "a" * 64,
                "change_reason": "Seed the local Material State demonstration.",
                "content": {
                    "material_revision_id": "material-revision-1",
                    "name": demo_seed._STATE_NAME,
                    "manufacturing_route": "Synthetic reference production route",
                    "heat_treatment": None,
                    "lot_or_batch": "CMP-DEMO-LOT-001",
                    "description": demo_seed._STATE_DESCRIPTION,
                },
            },
        }],
    }
    api = _StateApi()

    _, repaired = demo_seed._ensure_state(api, detail)
    assert repaired["current_revision"]["content"]["manufacturing_route"] == (
        "Synthetic reference preparation; not for engineering use"
    )
    assert len(api.writes) == 1
    second_detail = {"material": material, "states": [repaired]}
    demo_seed._ensure_state(api, second_detail)
    assert len(api.writes) == 1


class _ModelCardApi(demo_seed.DemoApi):
    def __init__(self) -> None:
        self.reads: list[str] = []

    def get(self, path: str) -> dict[str, Any]:
        self.reads.append(path)
        if path == "/material-states/state-1/material-models":
            return {
                "items": [
                    {
                        "material_model_id": "promoted-model",
                        "current_revision": {
                            "id": "promoted-r1",
                            "content": {
                                "property_set_revision_id": "property-r1",
                                "calibration_evidence": {"selection_id": "selection-1"},
                            },
                        },
                    },
                    {
                        "material_model_id": "baseline-model",
                        "current_revision": {
                            "id": "baseline-r1",
                            "content": {
                                "property_set_revision_id": "property-r0",
                                "calibration_evidence": None,
                            },
                        },
                    },
                ]
            }
        if path == "/material-models/baseline-model/solver-cards":
            return {"items": [{"solver_card_id": "baseline-card"}]}
        raise AssertionError(f"unexpected GET {path}")

    def post(
        self,
        path: str,
        payload: Mapping[str, Any],
        *,
        headers: Mapping[str, str] | None = None,
    ) -> dict[str, Any]:
        raise AssertionError(f"repeat seed must not POST {path}: {payload}, {headers}")


def test_reference_card_repeat_seed_reuses_the_unpromoted_baseline_model() -> None:
    api = _ModelCardApi()
    state = {"material_state_id": "state-1"}
    properties = {"current_revision": {"id": "property-r1"}}

    demo_seed._ensure_model_and_card(api, state, properties)

    assert api.reads[-1] == "/material-models/baseline-model/solver-cards"


class _TabulatedCardApi(demo_seed.DemoApi):
    def __init__(self) -> None:
        self.reads: list[str] = []

    def get(self, path: str) -> dict[str, Any]:
        self.reads.append(path)
        if path == "/material-states/state-1/tabulated-plasticity-models":
            return {
                "items": [
                    {
                        "material_model_id": "processed-model",
                        "current_revision": {
                            "id": "processed-r1",
                            "content": {
                                "source_dataset_revision_id": "dataset-r1",
                                "processing_projection": {"output_id": "output-1"},
                                "calibration_projection": None,
                            },
                        },
                    },
                    {
                        "material_model_id": "baseline-model",
                        "current_revision": {
                            "id": "baseline-r1",
                            "content": {
                                "source_dataset_revision_id": "dataset-r0",
                                "processing_projection": None,
                                "calibration_projection": None,
                            },
                        },
                    },
                ]
            }
        if path == "/tabulated-plasticity-models/baseline-model/solver-cards":
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
        raise AssertionError(f"repeat seed must not POST {path}: {payload}, {headers}")


def test_tabulated_card_repeat_seed_reuses_the_unprojected_baseline_model() -> None:
    api = _TabulatedCardApi()
    state = {"material_state_id": "state-1"}
    properties = {"current_revision": {"id": "property-r1"}}
    dataset = {"current_revision": {"id": "dataset-r1"}}

    demo_seed._ensure_elastoplastic_models_and_cards(api, state, properties, dataset)

    assert api.reads[-1] == "/tabulated-plasticity-models/baseline-model/solver-cards"

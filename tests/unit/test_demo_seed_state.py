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

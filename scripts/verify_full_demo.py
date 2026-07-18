"""Verify the clean three-family demo through protected HTTP resources."""

from __future__ import annotations

import argparse
import json
import os
from collections.abc import Mapping, Sequence
from typing import Any, cast

import httpx

MATERIALS = {
    "CMP-DEMO-DP780": ("tabulated-plasticity-models", {"abaqus", "openradioss"}),
    "CMP-DEMO-POLYMER-PRONY": ("linear-viscoelastic-models", {"abaqus"}),
    "CMP-DEMO-ELASTOMER-OGDEN": ("ogden-prony-models", {"abaqus", "openradioss"}),
}


def _json(response: httpx.Response) -> dict[str, Any]:
    response.raise_for_status()
    value = response.json()
    if not isinstance(value, dict):
        raise RuntimeError(f"{response.request.url.path} did not return an object")
    return cast(dict[str, Any], value)


def _items(response: Mapping[str, Any]) -> list[dict[str, Any]]:
    value = response.get("items")
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _content(value: Mapping[str, Any]) -> Mapping[str, Any]:
    revision = value.get("current_revision")
    content = revision.get("content") if isinstance(revision, Mapping) else None
    return content if isinstance(content, Mapping) else {}


def verify_full_demo(base_url: str) -> dict[str, object]:
    with httpx.Client(base_url=base_url, timeout=60.0) as anonymous:
        token = str(_json(anonymous.get("/demo-identity/token"))["access_token"])
    result: dict[str, object] = {}
    with httpx.Client(
        base_url=base_url,
        headers={"Authorization": f"Bearer {token}"},
        timeout=60.0,
    ) as client:
        materials = _items(_json(client.get("/materials?limit=100")))
        for material_code, (model_path, required_solvers) in MATERIALS.items():
            material = next(
                (
                    item
                    for item in materials
                    if _content(item).get("material_code") == material_code
                ),
                None,
            )
            if material is None:
                raise RuntimeError(f"clean demo is missing {material_code}")
            material_id = str(material["material_id"])
            detail = _json(client.get(f"/materials/{material_id}"))
            states = detail.get("states")
            if not isinstance(states, list) or not states or not isinstance(states[0], dict):
                raise RuntimeError(f"{material_code} has no Material State")
            state_id = str(states[0]["material_state_id"])
            models = _items(_json(client.get(f"/material-states/{state_id}/{model_path}")))
            if not models:
                raise RuntimeError(f"{material_code} has no {model_path}")
            model = models[0]
            model_id = str(model["material_model_id"])
            cards = _items(_json(client.get(f"/{model_path}/{model_id}/solver-cards")))
            solvers = {
                str(target.get("solver"))
                for item in cards
                if isinstance((target := item.get("target")), Mapping)
            }
            missing = required_solvers - solvers
            if missing:
                raise RuntimeError(f"{material_code} is missing cards for {sorted(missing)}")
            revision = model.get("current_revision")
            result[material_code] = {
                "material_id": material_id,
                "material_state_id": state_id,
                "material_model_id": model_id,
                "material_model_revision_no": (
                    revision.get("revision_no") if isinstance(revision, Mapping) else None
                ),
                "solver_cards": sorted(solvers),
            }
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify the clean public synthetic demo.")
    parser.add_argument(
        "--api-base-url",
        default=os.getenv("CMP_DEMO_API_BASE_URL", "http://127.0.0.1:8000/api/v1"),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    result = verify_full_demo(_parser().parse_args(argv).api_base_url)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

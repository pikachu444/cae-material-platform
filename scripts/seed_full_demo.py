"""Prepare the three public synthetic modeling journeys in a clean Docker demo.

The normal ``cmp-demo-seed`` command owns the metal journey.  This companion
uses the same protected HTTP API to create the polymer and elastomer baselines,
then runs their deterministic public processing/calibration fixtures.  It has no
database access and must never be used for production or confidential data.
"""

from __future__ import annotations

import argparse
import os
from collections.abc import Mapping, Sequence
from typing import Any

import seed_ogden_calibration_demo
import seed_viscoelastic_master_demo
from cmp.apps.demo_seed import DemoApi, DemoSeedError


def _items(response: Mapping[str, Any]) -> list[dict[str, Any]]:
    value = response.get("items")
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _id(value: Mapping[str, Any], key: str) -> str:
    result = value.get(key)
    if not isinstance(result, str) or not result:
        raise DemoSeedError(f"full demo response did not contain {key}")
    return result


def _revision_id(value: Mapping[str, Any]) -> str:
    revision = value.get("current_revision")
    if not isinstance(revision, Mapping):
        raise DemoSeedError("full demo response did not contain current_revision")
    return _id(revision, "id")


def _content(value: Mapping[str, Any]) -> Mapping[str, Any]:
    revision = value.get("current_revision")
    content = revision.get("content") if isinstance(revision, Mapping) else None
    return content if isinstance(content, Mapping) else {}


def _find_by_content(
    values: Sequence[Mapping[str, Any]], key: str, expected: object
) -> dict[str, Any] | None:
    return next((dict(value) for value in values if _content(value).get(key) == expected), None)


def _ensure_material(
    api: DemoApi,
    *,
    name: str,
    material_code: str,
    material_family: str,
    material_class: str,
) -> dict[str, Any]:
    listed = _items(api.get(f"/materials?q={material_code}&limit=20"))
    material = _find_by_content(listed, "material_code", material_code)
    if material is None:
        material = api.post(
            "/materials",
            {
                "classification": "internal",
                "content": {
                    "name": name,
                    "material_code": material_code,
                    "material_family": material_family,
                    "material_class": material_class,
                    "description": (
                        "Public synthetic T-60 reference fixture; not validated engineering data."
                    ),
                },
                "change_reason": f"Create the synthetic {material_class} demo Material.",
            },
        )
    return api.get(f"/materials/{_id(material, 'material_id')}")


def _ensure_state(
    api: DemoApi, detail: Mapping[str, Any], *, name: str, lot: str
) -> dict[str, Any]:
    material = detail.get("material")
    if not isinstance(material, Mapping):
        raise DemoSeedError("full demo Material detail is incomplete")
    state = _find_by_content(_items({"items": detail.get("states")}), "name", name)
    if state is not None:
        return state
    return api.post(
        f"/materials/{_id(material, 'material_id')}/states",
        {
            "content": {
                "material_revision_id": _revision_id(material),
                "name": name,
                "manufacturing_route": "Public synthetic reference route",
                "heat_treatment": None,
                "lot_or_batch": lot,
                "description": "Deterministic T-60 demo state.",
            },
            "change_reason": "Create the synthetic modeling demo State.",
        },
    )


def _ensure_properties(
    api: DemoApi,
    detail: Mapping[str, Any],
    state: Mapping[str, Any],
    *,
    density: float,
    youngs_modulus: float,
    poisson_ratio: float,
) -> dict[str, Any]:
    state_id = _id(state, "material_state_id")
    existing = next(
        (
            item
            for item in _items({"items": detail.get("property_sets")})
            if item.get("material_state_id") == state_id
        ),
        None,
    )
    if existing is not None:
        return existing
    source = {"kind": "manual", "reference": "Public synthetic T-60 fixture"}
    return api.post(
        f"/material-states/{state_id}/property-sets",
        {
            "content": {
                "material_state_revision_id": _revision_id(state),
                "density_kg_per_m3": density,
                "density_source": source,
                "youngs_modulus_pa": youngs_modulus,
                "youngs_modulus_source": source,
                "poisson_ratio": poisson_ratio,
                "poisson_ratio_source": source,
                "yield_stress_pa": None,
                "yield_stress_source": None,
                "applicability": {
                    "temperature_min_k": 273.15,
                    "temperature_max_k": 313.15,
                    "strain_rate_min_per_s": None,
                    "strain_rate_max_per_s": None,
                    "note": "Public synthetic reference range only.",
                },
            },
            "change_reason": "Create typed synthetic modeling properties.",
        },
    )


def _ensure_shear_method(api: DemoApi) -> None:
    methods = _items(api.get("/test-methods"))
    if _find_by_content(methods, "method_code", "reference_shear_relaxation") is None:
        api.post(
            "/test-methods/reference-shear-relaxation",
            {
                "classification": "internal",
                "change_reason": "Create the public synthetic shear-relaxation method.",
            },
        )


def _fixture_complete(
    api: DemoApi,
    *,
    material_id: str,
    specimen_prefix: str,
    expected_count: int,
) -> bool:
    detail = api.get(f"/materials/{material_id}")
    states = detail.get("states")
    if not isinstance(states, list) or not states or not isinstance(states[0], Mapping):
        raise DemoSeedError("full demo Material has no Material State")
    state_id = _id(states[0], "material_state_id")
    specimens = _items(api.get(f"/material-states/{state_id}/specimens"))
    matching = [
        item
        for item in specimens
        if str(_content(item).get("specimen_code", "")).startswith(specimen_prefix)
    ]
    if not matching:
        return False
    if len(matching) != expected_count:
        raise DemoSeedError(
            f"full demo fixture {specimen_prefix} is partial "
            f"({len(matching)}/{expected_count}); remove only the demo volumes and reseed"
        )
    return True


def _ensure_polymer_baseline(api: DemoApi) -> str:
    detail = _ensure_material(
        api,
        name="Demo Polymer Prony",
        material_code="CMP-DEMO-POLYMER-PRONY",
        material_family="linear viscoelastic polymer",
        material_class="polymer",
    )
    state = _ensure_state(api, detail, name="Reference conditioned", lot="CMP-DEMO-POLYMER-001")
    properties = _ensure_properties(
        api,
        detail,
        state,
        density=1200.0,
        youngs_modulus=3_000_000_000.0,
        poisson_ratio=0.35,
    )
    state_id = _id(state, "material_state_id")
    models = _items(api.get(f"/material-states/{state_id}/linear-viscoelastic-models"))
    model = models[0] if models else api.post(
        f"/material-states/{state_id}/linear-viscoelastic-models",
        {
            "property_set_revision_id": _revision_id(properties),
            "bulk_relaxation_status": "not_characterized",
            "terms": [
                {"g_ratio": 0.2, "k_ratio": 0.0, "relaxation_time_s": 0.1},
                {"g_ratio": 0.3, "k_ratio": 0.0, "relaxation_time_s": 10.0},
            ],
            "change_reason": "Create the public synthetic two-term Prony baseline.",
        },
    )
    model_id = _id(model, "material_model_id")
    cards = _items(api.get(f"/linear-viscoelastic-models/{model_id}/solver-cards"))
    if not cards:
        target = {"solver": "abaqus", "version": "2025", "unit_system": "kg_m_s"}
        report = api.post(
            f"/linear-viscoelastic-models/{model_id}/mapping-preflight",
            {"material_model_revision_id": _revision_id(model), "target": target},
        )
        api.post(
            f"/linear-viscoelastic-models/{model_id}/solver-cards",
            {
                "material_model_revision_id": _revision_id(model),
                "target": target,
                "expected_mapping_report_sha256": _id(report, "mapping_report_sha256"),
                "solver_material_id": 1200,
                "material_name": "CMP_DEMO_POLYMER_PRONY",
                "change_reason": "Generate the public synthetic Abaqus Prony card.",
            },
        )
    _ensure_shear_method(api)
    material = detail.get("material")
    if not isinstance(material, Mapping):
        raise DemoSeedError("polymer material detail is incomplete")
    return _id(material, "material_id")


def _ensure_elastomer_baseline(api: DemoApi) -> str:
    detail = _ensure_material(
        api,
        name="Demo Elastomer Ogden-Prony",
        material_code="CMP-DEMO-ELASTOMER-OGDEN",
        material_family="Ogden hyper-viscoelastic elastomer",
        material_class="elastomer",
    )
    state = _ensure_state(api, detail, name="Reference cured", lot="CMP-DEMO-ELASTOMER-001")
    properties = _ensure_properties(
        api,
        detail,
        state,
        density=1100.0,
        youngs_modulus=6_000_000.0,
        poisson_ratio=0.49,
    )
    state_id = _id(state, "material_state_id")
    models = _items(api.get(f"/material-states/{state_id}/ogden-prony-models"))
    model = models[0] if models else api.post(
        f"/material-states/{state_id}/ogden-prony-models",
        {
            "property_set_revision_id": _revision_id(properties),
            "ogden_mu_pa": 2_000_000.0,
            "ogden_alpha": 2.0,
            "prony_terms": [
                {"g_ratio": 0.15, "relaxation_time_s": 0.2},
                {"g_ratio": 0.25, "relaxation_time_s": 8.0},
            ],
            "change_reason": "Create the public synthetic Ogden-Prony baseline.",
        },
    )
    model_id = _id(model, "material_model_id")
    existing = _items(api.get(f"/ogden-prony-models/{model_id}/solver-cards"))
    existing_solvers = {
        str(item.get("target", {}).get("solver"))
        for item in existing
        if isinstance(item.get("target"), Mapping)
    }
    for solver, solver_material_id in (("abaqus", 2100), ("openradioss", 2101)):
        if solver in existing_solvers:
            continue
        target = {"solver": solver, "version": "2025", "unit_system": "kg_m_s"}
        report = api.post(
            f"/ogden-prony-models/{model_id}/solver-card-preflight",
            {"material_model_revision_id": _revision_id(model), "target": target},
        )
        api.post(
            f"/ogden-prony-models/{model_id}/solver-cards",
            {
                "material_model_revision_id": _revision_id(model),
                "target": target,
                "expected_mapping_report_sha256": _id(report, "mapping_report_sha256"),
                "solver_material_id": solver_material_id,
                "material_name": "CMP_DEMO_ELASTOMER_OGDEN",
                "change_reason": f"Generate the public synthetic {solver} Ogden-Prony card.",
            },
        )
    material = detail.get("material")
    if not isinstance(material, Mapping):
        raise DemoSeedError("elastomer material detail is incomplete")
    return _id(material, "material_id")


def seed_full_demo(base_url: str) -> dict[str, str]:
    api = DemoApi(base_url)
    api.wait_until_healthy()
    api.authenticate()
    polymer_id = _ensure_polymer_baseline(api)
    elastomer_id = _ensure_elastomer_baseline(api)

    stamp = os.getenv("CMP_DEMO_FIXTURE_STAMP") or "t60-reference"
    os.environ["CMP_DEMO_FIXTURE_STAMP"] = stamp
    seed_viscoelastic_master_demo.BASE_URL = base_url
    seed_ogden_calibration_demo.BASE_URL = base_url
    if not _fixture_complete(
        api,
        material_id=polymer_id,
        specimen_prefix=f"TTS-{stamp}-",
        expected_count=6,
    ):
        seed_viscoelastic_master_demo.main()
    if not _fixture_complete(
        api,
        material_id=elastomer_id,
        specimen_prefix=f"OGDEN-{stamp}-",
        expected_count=4,
    ):
        seed_ogden_calibration_demo.main(promote=True)
    return {"polymer_material_id": polymer_id, "elastomer_material_id": elastomer_id}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Seed all public synthetic modeling journeys.")
    parser.add_argument(
        "--api-base-url",
        default=os.getenv("CMP_DEMO_API_BASE_URL", "http://127.0.0.1:8000/api/v1"),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    result = seed_full_demo(args.api_base_url)
    print(f"CMP full demo seed completed: {result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

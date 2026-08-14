"""Seed public synthetic multi-test Ogden calibration evidence in the local demo.

The generated curves are analytical, deterministic, and explicitly non-production.
They exercise the governed upload -> normalized Dataset -> calibration path without
claiming that the result is suitable for material qualification.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import time
from dataclasses import dataclass
from typing import Any, cast
from uuid import uuid4

import httpx

BASE_URL = os.getenv("CMP_DEMO_API_BASE_URL", "http://127.0.0.1:5173/api/v1")
TARGET_MATERIAL_NAME = "Synthetic Elastomer Ogden-Prony"


@dataclass(frozen=True)
class CurveFixture:
    label: str
    data_schema: str
    test_mode: str
    role: str
    stress_scale: float = 1.0


CURVES = (
    CurveFixture("uniaxial calibration", "monotonic_tension", "uniaxial_tension", "calibration"),
    CurveFixture("planar calibration", "planar_tension", "planar_tension", "calibration"),
    CurveFixture("biaxial calibration", "biaxial_tension", "biaxial_tension", "calibration"),
    CurveFixture("uniaxial holdout", "monotonic_tension", "uniaxial_tension", "holdout", 1.01),
)

METHOD_CODE_BY_MODE = {
    "uniaxial_tension": "reference_uniaxial_tensile",
    "planar_tension": "reference_planar_tension",
    "biaxial_tension": "reference_biaxial_tension",
}


def _json(response: httpx.Response) -> dict[str, Any]:
    if response.is_error:
        try:
            detail = response.json()
        except ValueError:
            detail = response.text[:500]
        raise RuntimeError(
            f"{response.request.method} {response.request.url.path} returned "
            f"{response.status_code}: {detail}"
        )
    return cast(dict[str, Any], response.json())


def _nominal_stress(test_mode: str, stretch: float) -> float:
    mu_pa = 2_000_000.0
    alpha = 2.0
    if test_mode == "uniaxial_tension":
        response = stretch ** (alpha - 1.0) - stretch ** (-alpha / 2.0 - 1.0)
    elif test_mode == "planar_tension":
        response = stretch ** (alpha - 1.0) - stretch ** (-alpha - 1.0)
    elif test_mode == "biaxial_tension":
        response = stretch ** (alpha - 1.0) - stretch ** (-2.0 * alpha - 1.0)
    else:  # pragma: no cover - fixtures above are the complete supported set
        raise ValueError(f"unsupported demo mode: {test_mode}")
    return float((2.0 * mu_pa / alpha) * response)


def _curve_csv(fixture: CurveFixture) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(("engineering_strain", "engineering_stress_pa"))
    for index in range(13):
        strain = index * 0.025
        stress = fixture.stress_scale * _nominal_stress(fixture.test_mode, 1.0 + strain)
        writer.writerow((f"{strain:.12g}", f"{stress:.12g}"))
    return stream.getvalue().encode("utf-8")


def _upload_csv(
    client: httpx.Client,
    *,
    value: bytes,
    filename: str,
    test_run_revision_id: str,
) -> tuple[str, str]:
    created = _json(
        client.post(
            "/uploads",
            headers={"Idempotency-Key": f"ogden-demo-{uuid4()}"},
            json={
                "classification": "internal",
                "original_filename": filename,
                "media_type": "text/csv",
                "expected_size_bytes": len(value),
                "expected_sha256": hashlib.sha256(value).hexdigest(),
                "test_run_revision_id": test_run_revision_id,
            },
        )
    )
    upload = cast(dict[str, Any], created["upload"])
    capability = str(created["upload_capability"])
    part_size = int(upload["part_size_bytes"])
    for part_number in range(1, int(upload["expected_part_count"]) + 1):
        start = (part_number - 1) * part_size
        response = client.put(
            f"/uploads/{upload['upload_id']}/parts/{part_number}",
            headers={"Upload-Capability": capability, "Content-Type": "text/csv"},
            content=value[start : start + part_size],
        )
        response.raise_for_status()
    completed = _json(
        client.post(
            f"/uploads/{upload['upload_id']}:complete",
            headers={"Upload-Capability": capability},
        )
    )
    return str(completed["raw_asset"]["raw_asset_id"]), str(
        completed["available_artifact_id"]
    )


def _scientific_profile(client: httpx.Client) -> dict[str, Any]:
    profiles = cast(
        list[dict[str, Any]],
        _json(client.get("/scientific-profiles?family=elastomer_ogden_prony"))["items"],
    )
    if profiles:
        return profiles[0]
    return _json(
        client.post(
            "/scientific-profiles",
            json={
                "classification": "internal",
                "content": {
                    "profile_label": "Reference elastomer multi-test Ogden",
                    "family": "elastomer_ogden_prony",
                    "approval_status": "reference_unapproved",
                    "multistart_count": 8,
                    "seed": 20260716,
                    "status_note": (
                        "Public synthetic reference bounds; domain sign-off is not recorded."
                    ),
                    "ogden": {
                        "mu_initial_pa": 1_200_000.0,
                        "mu_lower_pa": 1_000.0,
                        "mu_upper_pa": 100_000_000.0,
                        "mu_scale_pa": 1_000_000.0,
                        "alpha_initial": 2.4,
                        "alpha_lower": 0.1,
                        "alpha_upper": 20.0,
                        "alpha_scale": 2.0,
                        "uniaxial_weight": 1.0,
                        "planar_weight": 1.0,
                        "biaxial_weight": 1.0,
                    },
                },
                "change_reason": "Create explicit public synthetic Ogden demo profile",
            },
        )
    )


def _tension_methods(client: httpx.Client) -> dict[str, dict[str, Any]]:
    methods = cast(list[dict[str, Any]], _json(client.get("/test-methods"))["items"])
    by_code = {
        str(item["current_revision"]["content"]["method_code"]): item for item in methods
    }
    for test_mode, method_code in METHOD_CODE_BY_MODE.items():
        if method_code in by_code:
            continue
        if test_mode == "uniaxial_tension":
            endpoint = "/test-methods/reference-uniaxial-tensile"
            payload: dict[str, Any] = {
                "classification": "internal",
                "change_reason": "Create explicit public synthetic uniaxial method",
            }
        else:
            endpoint = "/test-methods/reference-multiaxial-tension"
            payload = {
                "classification": "internal",
                "test_mode": test_mode,
                "change_reason": f"Create explicit public synthetic {test_mode} method",
            }
        by_code[method_code] = _json(client.post(endpoint, json=payload))
    return {mode: by_code[code] for mode, code in METHOD_CODE_BY_MODE.items()}


def _import_curve(
    client: httpx.Client,
    *,
    material_state_id: str,
    material_state_revision_id: str,
    method: dict[str, Any],
    fixture: CurveFixture,
    stamp: str,
) -> dict[str, str]:
    specimen = _json(
        client.post(
            f"/material-states/{material_state_id}/specimens",
            json={
                "material_state_revision_id": material_state_revision_id,
                "specimen_code": f"OGDEN-{stamp}-{fixture.test_mode}-{fixture.role}",
                "orientation": None,
                "preparation_note": "Public synthetic T-43 analytical curve",
                "change_reason": "Create synthetic Ogden calibration specimen",
            },
        )
    )
    test_run = _json(
        client.post(
            "/test-runs",
            json={
                "specimen_id": specimen["specimen_id"],
                "specimen_revision_id": specimen["current_revision"]["id"],
                "test_method_id": method["test_method_id"],
                "test_method_revision_id": method["current_revision"]["id"],
                "run_label": f"Ogden {fixture.label} synthetic demo {stamp}",
                "performed_at": "2026-08-20T09:00:00Z",
                "test_temperature_k": 296.15,
                "crosshead_speed_mm_per_min": 2.0,
                "change_reason": "Register synthetic Ogden multi-test evidence",
            },
        )
    )
    source = _curve_csv(fixture)
    raw_asset_id, raw_artifact_id = _upload_csv(
        client,
        value=source,
        filename=f"synthetic-ogden-{fixture.test_mode}-{fixture.role}.csv",
        test_run_revision_id=str(test_run["current_revision"]["id"]),
    )
    profile = _json(
        client.post(
            "/import-profiles",
            json={
                "classification": "internal",
                "content": {
                    "profile_label": f"Synthetic Ogden {fixture.label} {stamp}",
                    "data_schema": fixture.data_schema,
                    "file_format": "csv",
                    "sheet_name": None,
                    "header_row": 1,
                    "encoding": "utf-8",
                    "delimiter": ",",
                    "decimal_separator": ".",
                    "channels": [
                        {
                            "ordinal": 0,
                            "source_column": "engineering_strain",
                            "source_quantity": "engineering_strain",
                            "original_unit": "1",
                            "axis_role": "independent",
                        },
                        {
                            "ordinal": 1,
                            "source_column": "engineering_stress_pa",
                            "source_quantity": "engineering_stress",
                            "original_unit": "Pa",
                            "axis_role": "dependent",
                        },
                    ],
                    "initial_gauge_length_m": None,
                    "initial_cross_section_area_m2": None,
                    "approval_kind": "human_confirmed",
                },
                "change_reason": "Approve explicit synthetic Ogden column semantics",
            },
        )
    )
    imported = _json(
        client.post(
            "/tabular-import-runs",
            headers={"Idempotency-Key": f"ogden-demo-import-{uuid4()}"},
            json={
                "test_run_id": test_run["test_run_id"],
                "test_run_revision_id": test_run["current_revision"]["id"],
                "raw_asset_id": raw_asset_id,
                "raw_artifact_id": raw_artifact_id,
                "import_profile_id": profile["import_profile_id"],
                "import_profile_revision_id": profile["current_revision"]["id"],
                "change_reason": "Create governed normalized synthetic Ogden Dataset",
            },
        )
    )
    return {
        "role": fixture.role,
        "test_mode": fixture.test_mode,
        "dataset_id": str(imported["normalized_dataset_id"]),
        "dataset_revision_id": str(imported["normalized_dataset_revision_id"]),
    }


def main(*, promote: bool = False) -> None:
    with httpx.Client(base_url=BASE_URL, timeout=60.0) as anonymous:
        token = str(_json(anonymous.get("/demo-identity/token"))["access_token"])
    with httpx.Client(
        base_url=BASE_URL,
        headers={"Authorization": f"Bearer {token}"},
        timeout=60.0,
    ) as client:
        materials = cast(
            list[dict[str, Any]], _json(client.get("/materials?limit=100"))["items"]
        )
        material = next(
            item
            for item in materials
            if item["current_revision"]["content"]["name"] == TARGET_MATERIAL_NAME
        )
        detail = _json(client.get(f"/materials/{material['material_id']}"))
        state = cast(list[dict[str, Any]], detail["states"])[0]
        models = cast(
            list[dict[str, Any]],
            _json(
                client.get(
                    f"/material-states/{state['material_state_id']}/ogden-prony-models"
                )
            )["items"],
        )
        if not models:
            raise RuntimeError("create the bounded reference Ogden-Prony IR before seeding")
        baseline = models[0]
        scientific_profile = _scientific_profile(client)
        methods = _tension_methods(client)
        stamp = os.getenv("CMP_DEMO_FIXTURE_STAMP") or str(int(time.time()))
        members = [
            _import_curve(
                client,
                material_state_id=str(state["material_state_id"]),
                material_state_revision_id=str(state["current_revision"]["id"]),
                method=methods[fixture.test_mode],
                fixture=fixture,
                stamp=stamp,
            )
            for fixture in CURVES
        ]
        plan = _json(
            client.post(
                "/ogden-calibration-plans",
                json={
                    "classification": "internal",
                    "plan_label": f"Public synthetic multi-test Ogden {stamp}",
                    "scientific_profile_id": scientific_profile["scientific_profile_id"],
                    "scientific_profile_revision_id": scientific_profile["current_revision"]["id"],
                    "material_state_id": state["material_state_id"],
                    "material_state_revision_id": state["current_revision"]["id"],
                    "baseline_model_id": baseline["material_model_id"],
                    "baseline_model_revision_id": baseline["current_revision"]["id"],
                    "members": [dict(member, weight=1.0) for member in members],
                    "change_reason": "Pin public synthetic multi-test and holdout evidence",
                },
            )
        )
        run = _json(
            client.post(
                f"/ogden-calibration-plans/{plan['ogden_calibration_plan_id']}/runs",
                json={
                    "plan_revision_id": plan["current_revision"]["id"],
                    "change_reason": "Execute deterministic public synthetic Ogden fit",
                },
            )
        )
        candidates = cast(list[dict[str, Any]], run["candidates"])
        best = min(candidates, key=lambda item: float(item["objective_total"]))
        result: dict[str, object] = {
            "fixture_stamp": stamp,
            "material_id": material["material_id"],
            "material_state_id": state["material_state_id"],
            "plan_id": plan["ogden_calibration_plan_id"],
            "run_id": run["ogden_calibration_run_id"],
            "candidate_id": best["ogden_calibration_candidate_id"],
            "calibration_curve_count": run["calibration_curve_count"],
            "holdout_curve_count": run["holdout_curve_count"],
            "test_mode_count": run["test_mode_count"],
            "mu_pa": best["mu_pa"],
            "alpha": best["alpha"],
            "uncertainty_status": best["uncertainty_status"],
        }
        if promote:
            model_id = str(baseline["material_model_id"])
            before_cards = cast(
                list[dict[str, Any]],
                _json(client.get(f"/ogden-prony-models/{model_id}/solver-cards"))["items"],
            )
            frozen_cards = {
                str(item["solver_card_id"]): (
                    str(item["current_revision"]["id"]),
                    str(item["current_revision"]["content"]["card_sha256"]),
                )
                for item in before_cards
            }
            selection = _json(
                client.post(
                    "/ogden-candidate-selections",
                    json={
                        "classification": "internal",
                        "selection_label": f"Public synthetic Ogden Candidate {stamp}",
                        "calibration_run_id": run["ogden_calibration_run_id"],
                        "calibration_candidate_id": best[
                            "ogden_calibration_candidate_id"
                        ],
                        "selection_reason": (
                            "Reviewed fitted and residual curves, holdout response, "
                            "convergence, bounds, rank, and uncertainty evidence."
                        ),
                    },
                )
            )
            current = cast(dict[str, Any], baseline["current_revision"])
            model_etag = (
                f'"revision:{current["revision_no"]}:sha256:'
                f'{current["content_hash"]}"'
            )
            promoted = _json(
                client.post(
                    f"/ogden-candidate-selections/"
                    f"{selection['ogden_candidate_selection_id']}/promotions",
                    headers={"If-Match": model_etag},
                    json={
                        "selection_revision_id": selection["current_revision"]["id"],
                        "change_reason": (
                            "Append the reviewed public synthetic Candidate as a new "
                            "immutable Ogden-Prony IR revision."
                        ),
                    },
                )
            )
            after_cards = cast(
                list[dict[str, Any]],
                _json(client.get(f"/ogden-prony-models/{model_id}/solver-cards"))["items"],
            )
            after_frozen = {
                str(item["solver_card_id"]): (
                    str(item["current_revision"]["id"]),
                    str(item["current_revision"]["content"]["card_sha256"]),
                )
                for item in after_cards
                if str(item["solver_card_id"]) in frozen_cards
            }
            if after_frozen != frozen_cards:
                raise RuntimeError("a prior immutable Solver Card changed during promotion")
            result.update(
                {
                    "selection_id": selection["ogden_candidate_selection_id"],
                    "promoted_model_id": promoted["material_model_id"],
                    "promoted_revision_id": promoted["current_revision"]["id"],
                    "promoted_revision_no": promoted["current_revision"]["revision_no"],
                    "prior_solver_cards_verified_stable": len(frozen_cards),
                }
            )
        print(
            json.dumps(result, indent=2)
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--promote",
        action="store_true",
        help="record a human-style Selection and append the Candidate to the current IR",
    )
    arguments = parser.parse_args()
    main(promote=arguments.promote)

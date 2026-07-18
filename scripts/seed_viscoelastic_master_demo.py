"""Create public synthetic multi-temperature shear-relaxation evidence in the local demo.

This is a development/demo helper, not an importer or a scientific material database.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import time
from typing import Any, cast
from uuid import uuid4

import httpx

BASE_URL = os.getenv("CMP_DEMO_API_BASE_URL", "http://127.0.0.1:5173/api/v1")
TEMPERATURE_SHIFTS = ((273.15, 1.6), (293.15, 0.0), (313.15, -1.15))


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


def _curve_csv(shift: float, scale: float) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(("time", "shear_modulus"))
    for index in range(43):
        log_time = -3.0 + index / 6.0
        modulus = scale * (
            2_000_000.0 + 8_000_000.0 / (1.0 + 10.0 ** (0.6 * (log_time - shift)))
        )
        writer.writerow((f"{10.0**log_time:.12g}", f"{modulus:.12g}"))
    return stream.getvalue().encode("utf-8")


def _upload_csv(
    client: httpx.Client,
    *,
    value: bytes,
    filename: str,
    test_run_revision_id: str,
) -> tuple[str, str]:
    digest = hashlib.sha256(value).hexdigest()
    created = _json(
        client.post(
            "/uploads",
            headers={"Idempotency-Key": f"tts-demo-{uuid4()}"},
            json={
                "classification": "internal",
                "original_filename": filename,
                "media_type": "text/csv",
                "expected_size_bytes": len(value),
                "expected_sha256": digest,
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
            headers={
                "Upload-Capability": capability,
                "Content-Type": "text/csv",
            },
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


def main() -> None:
    with httpx.Client(base_url=BASE_URL, timeout=60.0) as anonymous:
        token = str(_json(anonymous.get("/demo-identity/token"))["access_token"])
    with httpx.Client(
        base_url=BASE_URL,
        headers={"Authorization": f"Bearer {token}"},
        timeout=60.0,
    ) as client:
        materials = cast(list[dict[str, Any]], _json(client.get("/materials?limit=50"))["items"])
        material = next(
            item
            for item in materials
            if item["current_revision"]["content"]["name"] == "Demo Polymer Prony"
        )
        detail = _json(client.get(f"/materials/{material['material_id']}"))
        state = cast(list[dict[str, Any]], detail["states"])[0]
        methods = cast(list[dict[str, Any]], _json(client.get("/test-methods"))["items"])
        method = next(
            item
            for item in methods
            if item["current_revision"]["content"]["method_code"]
            == "reference_shear_relaxation"
        )
        stamp = os.getenv("CMP_DEMO_FIXTURE_STAMP") or str(int(time.time()))
        normalized: list[dict[str, Any]] = []
        for temperature_index, (temperature, shift) in enumerate(TEMPERATURE_SHIFTS):
            for replicate_index, scale in enumerate((0.995, 1.005)):
                specimen = _json(
                    client.post(
                        f"/material-states/{state['material_state_id']}/specimens",
                        json={
                            "material_state_revision_id": state["current_revision"]["id"],
                            "specimen_code": (
                                f"TTS-{stamp}-{temperature_index + 1}-{replicate_index + 1}"
                            ),
                            "orientation": None,
                            "preparation_note": "Public synthetic T-42 demo fixture",
                            "change_reason": "Create synthetic TTS replicate specimen",
                        },
                    )
                )
                test_run = _json(
                    client.post(
                        "/test-runs/reference-shear-relaxation",
                        json={
                            "specimen_id": specimen["specimen_id"],
                            "specimen_revision_id": specimen["current_revision"]["id"],
                            "test_method_id": method["test_method_id"],
                            "test_method_revision_id": method["current_revision"]["id"],
                            "run_label": (
                                f"TTS {temperature:.2f} K replicate {replicate_index + 1}"
                            ),
                            "performed_at": "2026-08-18T09:00:00Z",
                            "test_temperature_k": temperature,
                            "change_reason": "Register synthetic TTS temperature evidence",
                        },
                    )
                )
                raw_asset_id, raw_artifact_id = _upload_csv(
                    client,
                    value=_curve_csv(shift, scale),
                    filename=(
                        f"synthetic-tts-{temperature:.2f}K-r{replicate_index + 1}.csv"
                    ),
                    test_run_revision_id=str(test_run["current_revision"]["id"]),
                )
                dataset = _json(
                    client.post(
                        "/shear-relaxation-datasets",
                        json={
                            "test_run_id": test_run["test_run_id"],
                            "test_run_revision_id": test_run["current_revision"]["id"],
                            "raw_asset_id": raw_asset_id,
                            "raw_artifact_id": raw_artifact_id,
                            "mapping": {
                                "time_column": "time",
                                "shear_modulus_column": "shear_modulus",
                                "time_unit": "s",
                                "shear_modulus_unit": "Pa",
                            },
                            "change_reason": "Normalize public synthetic TTS curve",
                        },
                    )
                )
                normalized.append(dataset)
        selection = _json(
            client.post(
                "/viscoelastic-selections",
                json={
                    "classification": "internal",
                    "selection_label": f"Synthetic TTS replicate set {stamp}",
                    "members": [
                        {
                            "dataset_id": item["dataset_id"],
                            "dataset_revision_id": item["current_revision"]["id"],
                        }
                        for item in normalized
                    ],
                    "change_reason": "Pin three temperatures and two replicates per temperature",
                },
            )
        )
        plan = _json(
            client.post(
                "/processing-plans/viscoelastic-master-curve",
                json={
                    "classification": "internal",
                    "plan_label": f"Synthetic 293.15 K master curve {stamp}",
                    "selection_id": selection["selection_id"],
                    "selection_revision_id": selection["current_revision"]["id"],
                    "reference_temperature_k": 293.15,
                    "grid_point_count": 101,
                    "shift_method": "manual",
                    "manual_shift_factors": [
                        {"temperature_k": temperature, "log10_a_t": shift}
                        for temperature, shift in TEMPERATURE_SHIFTS
                    ],
                    "change_reason": "Define explicit synthetic shift evidence",
                },
            )
        )
        run = _json(
            client.post(
                "/processing-runs/viscoelastic-master-curve",
                json={
                    "plan_id": plan["plan_id"],
                    "plan_revision_id": plan["current_revision"]["id"],
                    "change_reason": "Commit synthetic aligned, statistics and master Datasets",
                },
            )
        )
        preview = _json(
            client.get(
                f"/processing-runs/viscoelastic-master-curve/"
                f"{run['processing_run_id']}/preview"
            )
        )
        print(
            json.dumps(
                {
                    "material_id": material["material_id"],
                    "material_state_id": state["material_state_id"],
                    "selection_id": selection["selection_id"],
                    "plan_id": plan["plan_id"],
                    "processing_run_id": run["processing_run_id"],
                    "aligned_dataset_revision_id": run["aligned_dataset_revision_id"],
                    "statistics_dataset_revision_id": run[
                        "statistics_dataset_revision_id"
                    ],
                    "master_dataset_revision_id": run["master_dataset_revision_id"],
                    "source_curve_count": run["source_curve_count"],
                    "temperature_count": run["temperature_count"],
                    "master_point_count": len(preview["master_curve"]),
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    main()

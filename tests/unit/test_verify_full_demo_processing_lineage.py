from __future__ import annotations

import sys
from copy import deepcopy
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from typing import Any

import pytest

_SCRIPTS = Path(__file__).parents[2] / "scripts"
sys.path.insert(0, str(_SCRIPTS))
_SPEC = spec_from_file_location("verify_full_demo", _SCRIPTS / "verify_full_demo.py")
assert _SPEC is not None and _SPEC.loader is not None
_VERIFY_FULL_DEMO = module_from_spec(_SPEC)
sys.modules[_SPEC.name] = _VERIFY_FULL_DEMO
_SPEC.loader.exec_module(_VERIFY_FULL_DEMO)

ProcessingContractExecutionIdentity: Any = vars(_VERIFY_FULL_DEMO)[
    "ProcessingContractExecutionIdentity"
]
ProcessingLineageError = _VERIFY_FULL_DEMO.ProcessingLineageError
resolve_processing_projection_lineage = _VERIFY_FULL_DEMO.resolve_processing_projection_lineage

RECIPE_SHA256 = "a" * 64
OUTPUT_SHA256 = "b" * 64


def _fixture() -> tuple[
    dict[str, object],
    list[dict[str, object]],
    list[dict[str, object]],
    ProcessingContractExecutionIdentity,
]:
    projection: dict[str, object] = {
        "output_id": "output-old",
        "output_revision_id": "output-old-r1",
        "output_sha256": f"sha256:{OUTPUT_SHA256}",
        "recipe_batch": {
            "processing_recipe": {
                "id": "recipe",
                "revision_id": "recipe-old-r1",
                "sha256": f"sha256:{RECIPE_SHA256}",
            },
            "processing_batch_id": "batch-old",
            "batch_member_id": "member-old",
            "batch_attempt_id": "attempt-old",
            "batch_attempt_no": 1,
        },
    }
    batches: list[dict[str, object]] = [
        {
            "batch_id": "batch-old",
            "recipe_id": "recipe",
            "recipe_revision_id": "recipe-old-r1",
            "recipe_sha256": RECIPE_SHA256,
            "members": [{"member_id": "member-old"}],
            "attempts": [
                {
                    "attempt_id": "attempt-old",
                    "member_id": "member-old",
                    "attempt_no": 1,
                    "status": "succeeded",
                    "output_id": "output-old",
                    "output_revision_id": "output-old-r1",
                }
            ],
        }
    ]
    outputs: list[dict[str, object]] = [
        {
            "processing_output_id": "output-old",
            "current_revision": {"id": "output-old-r1"},
            "output_sha256": OUTPUT_SHA256,
        }
    ]
    current = ProcessingContractExecutionIdentity(
        recipe_id="recipe",
        recipe_revision_id="recipe-current-r1",
        recipe_sha256=RECIPE_SHA256,
        batch_id="batch-current",
        batch_member_id="member-current",
        batch_attempt_id="attempt-current",
        batch_attempt_no=1,
        output_id="output-current",
        output_revision_id="output-current-r1",
        output_sha256=OUTPUT_SHA256,
    )
    return projection, batches, outputs, current


def test_processing_lineage_resolves_fresh_current_execution() -> None:
    projection, batches, outputs, _ = _fixture()
    projection["output_id"] = "output-current"
    projection["output_revision_id"] = "output-current-r1"
    recipe_batch = projection["recipe_batch"]
    assert isinstance(recipe_batch, dict)
    recipe_batch["processing_batch_id"] = "batch-current"
    recipe_batch["batch_member_id"] = "member-current"
    recipe_batch["batch_attempt_id"] = "attempt-current"
    recipe_batch["processing_recipe"] = {
        "id": "recipe",
        "revision_id": "recipe-current-r1",
        "sha256": f"sha256:{RECIPE_SHA256}",
    }
    batches[0] = {
        **batches[0],
        "batch_id": "batch-current",
        "recipe_revision_id": "recipe-current-r1",
        "members": [{"member_id": "member-current"}],
        "attempts": [
            {
                "attempt_id": "attempt-current",
                "member_id": "member-current",
                "attempt_no": 1,
                "status": "succeeded",
                "output_id": "output-current",
                "output_revision_id": "output-current-r1",
            }
        ],
    }
    outputs[0] = {
        "processing_output_id": "output-current",
        "current_revision": {"id": "output-current-r1"},
        "output_sha256": OUTPUT_SHA256,
    }
    resolution = resolve_processing_projection_lineage(
        projection, batches, outputs, ProcessingContractExecutionIdentity(
            recipe_id="recipe",
            recipe_revision_id="recipe-current-r1",
            recipe_sha256=RECIPE_SHA256,
            batch_id="batch-current",
            batch_member_id="member-current",
            batch_attempt_id="attempt-current",
            batch_attempt_no=1,
            output_id="output-current",
            output_revision_id="output-current-r1",
            output_sha256=OUTPUT_SHA256,
        )
    )
    assert resolution.is_current_contract_execution
    assert not resolution.is_immutable_predecessor


def test_processing_lineage_marks_exact_predecessor_without_relabeling() -> None:
    projection, batches, outputs, current = _fixture()
    resolution = resolve_processing_projection_lineage(projection, batches, outputs, current)
    assert resolution.is_immutable_predecessor
    assert resolution.is_predecessor
    assert not resolution.is_current_contract_execution


def test_processing_lineage_rejects_ambiguous_batch() -> None:
    projection, batches, outputs, current = _fixture()
    batches.append(deepcopy(batches[0]))
    with pytest.raises(ProcessingLineageError, match="exactly one response"):
        resolve_processing_projection_lineage(projection, batches, outputs, current)


def test_processing_lineage_rejects_recipe_digest_mismatch() -> None:
    projection, batches, outputs, current = _fixture()
    batches[0]["recipe_sha256"] = "c" * 64
    with pytest.raises(ProcessingLineageError, match="recipe pin"):
        resolve_processing_projection_lineage(projection, batches, outputs, current)


def test_processing_lineage_rejects_failed_attempt() -> None:
    projection, batches, outputs, current = _fixture()
    attempts = batches[0]["attempts"]
    assert isinstance(attempts, list)
    attempts[0]["status"] = "failed"
    with pytest.raises(ProcessingLineageError, match="successful exact"):
        resolve_processing_projection_lineage(projection, batches, outputs, current)


def test_processing_lineage_rejects_false_predecessor_relabeling() -> None:
    projection, batches, outputs, _ = _fixture()
    with pytest.raises(ProcessingLineageError, match="reuses a current"):
        resolve_processing_projection_lineage(
            projection,
            batches,
            outputs,
            ProcessingContractExecutionIdentity(
                recipe_revision_id="recipe-old-r1",
                batch_id="batch-current",
                batch_attempt_id="attempt-current",
                output_id="output-current",
                output_revision_id="output-current-r1",
            ),
        )

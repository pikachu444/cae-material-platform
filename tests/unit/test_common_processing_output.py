from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

from cmp.modules.datasets.domain.canonical_test_data import parse_canonical_test_data
from cmp.modules.processing.application.common_outputs import (
    ExactRevisionPin,
    ProcessingWorkupOverride,
    processing_output_document,
)
from cmp.modules.processing.domain.common_pipeline import (
    ChannelBinding,
    MappingProfileContent,
    MissingDataPolicy,
    ProcessingStep,
    preview_pipeline,
)
from cmp.shared.domain.revisions import canonical_json_bytes


def test_committed_output_document_contains_exact_pins_steps_and_every_stage() -> None:
    document = parse_canonical_test_data(
        json.loads(
            Path("contracts/examples/positive/canonical-test-data.json").read_text(encoding="utf-8")
        )
    )
    profile = MappingProfileContent(
        profile_key="tensile",
        label="Tensile mapping",
        independent_quantity="strain.engineering",
        missing_data_policy=MissingDataPolicy.DROP_ANY,
        bindings=(
            ChannelBinding("engineering_strain", "strain.engineering", ("1",)),
            ChannelBinding("engineering_stress", "stress.engineering", ("Pa",)),
        ),
    )
    steps = (ProcessingStep("rows.sort_unique", "1.0.0", {"duplicate_policy": "reject"}),)
    preview = preview_pipeline(document, profile, steps)
    value = processing_output_document(
        output_id=UUID("d5400000-0000-4000-8000-000000000001"),
        source=ExactRevisionPin(
            UUID("d5400000-0000-4000-8000-000000000002"),
            UUID("d5400000-0000-4000-8000-000000000003"),
        ),
        source_canonical_sha256="f" * 64,
        profile=ExactRevisionPin(
            UUID("d5400000-0000-4000-8000-000000000004"),
            UUID("d5400000-0000-4000-8000-000000000005"),
        ),
        steps=steps,
        preview=preview,
    )
    encoded = canonical_json_bytes(value)
    decoded = json.loads(encoded)
    assert decoded["document_type"] == "cmp.processing-output"
    assert decoded["source_document"]["revision_id"].endswith("0003")
    assert decoded["source_canonical_artifact_sha256"] == "f" * 64
    assert decoded["mapping_profile"]["revision_id"].endswith("0005")
    assert decoded["steps"] == [
        {
            "method_id": "rows.sort_unique",
            "method_version": "1.0.0",
            "options": {"duplicate_policy": "reject"},
        }
    ]
    assert [stage["method_id"] for stage in decoded["result"]["stages"]] == [
        "mapping",
        "rows.sort_unique",
    ]
    assert decoded["result"]["source_document_sha256"] == document.digest


def test_committed_output_document_preserves_structured_manual_workup_evidence() -> None:
    document = parse_canonical_test_data(
        json.loads(
            Path("contracts/examples/positive/canonical-test-data.json").read_text(encoding="utf-8")
        )
    )
    profile = MappingProfileContent(
        profile_key="tensile",
        label="Tensile mapping",
        independent_quantity="strain.engineering",
        missing_data_policy=MissingDataPolicy.DROP_ANY,
        bindings=(
            ChannelBinding("engineering_strain", "strain.engineering", ("1",)),
            ChannelBinding("engineering_stress", "stress.engineering", ("Pa",)),
        ),
    )
    steps = (ProcessingStep("rows.sort_unique", "1.0.0", {"duplicate_policy": "reject"}),)
    value = processing_output_document(
        output_id=UUID("d5400000-0000-4000-8000-000000000001"),
        source=ExactRevisionPin(
            UUID("d5400000-0000-4000-8000-000000000002"),
            UUID("d5400000-0000-4000-8000-000000000003"),
        ),
        source_canonical_sha256="f" * 64,
        profile=ExactRevisionPin(
            UUID("d5400000-0000-4000-8000-000000000004"),
            UUID("d5400000-0000-4000-8000-000000000005"),
        ),
        steps=steps,
        preview=preview_pipeline(document, profile, steps),
        workup_overrides=(
            ProcessingWorkupOverride(
                kind="youngs_modulus",
                original_value=205,
                original_unit="GPa",
                canonical_value=205_000_000_000,
                canonical_unit="Pa",
                reason="Reconcile the measured elastic range.",
            ),
        ),
    )

    assert value["workup_overrides"] == [
        {
            "kind": "youngs_modulus",
            "original_value": 205,
            "original_unit": "GPa",
            "canonical_value": 205_000_000_000,
            "canonical_unit": "Pa",
            "reason": "Reconcile the measured elastic range.",
        }
    ]

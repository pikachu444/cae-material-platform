from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from cmp.modules.datasets.domain.reference_tensile import ReferenceTensileMapping
from cmp.modules.testing.domain.import_mapping import (
    ImportDetectionStatus,
    MappingSuggestionConfidence,
    ReferenceImportMappingContent,
    SyntheticCsvDetectionReport,
    detect_synthetic_csv_header,
    synthetic_csv_detection_canonical,
)
from cmp.modules.testing.domain.reference_tensile import InvalidTestingData

RAW_ASSET = UUID("f2000000-0000-4000-8000-000000000001")
RAW_ARTIFACT = UUID("f2000000-0000-4000-8000-000000000002")


def _detection(
    payload: bytes = b"strain_pct,stress_mpa\n0,0\n",
) -> SyntheticCsvDetectionReport:
    return detect_synthetic_csv_header(
        payload,
        raw_asset_id=RAW_ASSET,
        raw_artifact_id=RAW_ARTIFACT,
        raw_sha256="a" * 64,
    )


def test_synthetic_header_detection_keeps_low_confidence_needs_input_boundary() -> None:
    result = _detection()

    assert result.status is ImportDetectionStatus.NEEDS_INPUT
    assert result.header_columns == ("strain_pct", "stress_mpa")
    assert result.suggested_strain_unit == "%"
    assert result.suggested_stress_unit == "MPa"
    assert result.strain_confidence is MappingSuggestionConfidence.LOW
    assert result.stress_confidence is MappingSuggestionConfidence.LOW
    assert synthetic_csv_detection_canonical(result)["status"] == "needs_input"


def test_unknown_headers_have_no_silent_semantic_or_unit_decision() -> None:
    result = _detection(b"channel_a,channel_b\n0,0\n")

    assert result.suggested_strain_column is None
    assert result.suggested_stress_column is None
    assert result.strain_confidence is MappingSuggestionConfidence.NONE
    assert result.stress_confidence is MappingSuggestionConfidence.NONE


@pytest.mark.parametrize(
    "payload",
    (
        b"strain,strain\n0,0\n",
        b"strain,\n0,0\n",
        b"\xff\xfeinvalid",
    ),
)
def test_synthetic_header_detection_rejects_unusable_evidence(payload: bytes) -> None:
    with pytest.raises(InvalidTestingData):
        _detection(payload)


def test_human_mapping_digest_matches_existing_dataset_mapping_contract() -> None:
    mapping = ReferenceImportMappingContent(
        mapping_label="run-001 original labels",
        detection_report_id=uuid4(),
        raw_asset_id=RAW_ASSET,
        raw_artifact_id=RAW_ARTIFACT,
        strain_column="strain_pct",
        stress_column="stress_mpa",
        strain_unit="%",
        stress_unit="MPa",
    )

    assert mapping.dataset_mapping_digest == ReferenceTensileMapping(
        "strain_pct", "stress_mpa", "%", "MPa"
    ).digest

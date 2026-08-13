from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from cmp.modules.identity_access.domain.authorization import DataClassification
from cmp.modules.review_release.adapters.persistence.evidence import _SUBJECTS
from cmp.modules.review_release.domain.evidence import (
    LEGACY_REVIEW_SUBJECT_TYPES,
    REGISTERED_REVIEW_SUBJECT_TYPES,
    EvidenceValidationStatus,
    LegacyReviewSubjectResolver,
    ReviewEvidenceError,
    ReviewSubjectEvidence,
    ReviewSubjectEvidenceRegistry,
    SourceArtifactState,
)

NOW = datetime(2026, 9, 25, 9, 0, tzinfo=UTC)
ORG = UUID("16000000-0000-4000-8000-000000000001")
PROJECT = UUID("16000000-0000-4000-8000-000000000002")
PRINCIPAL = UUID("16000000-0000-4000-8000-000000000003")
SUBJECT = UUID("16000000-0000-4000-8000-000000000004")
REVISION = UUID("16000000-0000-4000-8000-000000000005")


def _legacy(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "subject_type": "validation.result",
        "organization_id": ORG,
        "project_id": PROJECT,
        "subject_id": SUBJECT,
        "subject_revision_id": REVISION,
        "expected_manifest_sha256": "a" * 64,
        "expected_classification": DataClassification.INTERNAL,
        "requested_by": PRINCIPAL,
        "reason": "Retain the pre-160 validation result request",
        "occurred_at": NOW,
    }
    value.update(overrides)
    return value


def test_registry_keeps_legacy_validation_requests_explicit_and_rejects_unknown_targets() -> None:
    registry = ReviewSubjectEvidenceRegistry((LegacyReviewSubjectResolver(),))

    assert registry.resolve(**_legacy()) is None
    assert LEGACY_REVIEW_SUBJECT_TYPES == ("validation.result",)
    with pytest.raises(ReviewEvidenceError, match="no resolver"):
        registry.resolve(**_legacy(subject_type="unknown.subject"))
    with pytest.raises(ReviewEvidenceError, match="classification and manifest"):
        registry.resolve(**_legacy(expected_classification=None))
    with pytest.raises(ReviewEvidenceError, match="SHA-256"):
        registry.resolve(**_legacy(expected_manifest_sha256="not-a-digest"))


def test_current_subject_registry_is_closed_and_evidence_round_trips() -> None:
    assert REGISTERED_REVIEW_SUBJECT_TYPES == (
        "catalog.material",
        "catalog.configurable_record",
        "datasets.test_data_document",
        "modeling.material_model",
        "exporting.solver_card",
        "exporting.neutral_solver_card",
    )
    evidence = ReviewSubjectEvidence(
        subject_type="datasets.test_data_document",
        subject_id=SUBJECT,
        subject_revision_id=REVISION,
        label="DP600 Test Data",
        classification=DataClassification.INTERNAL,
        schema_ref="cmp.test-data",
        schema_version="1.0.0",
        server_manifest_sha256="b" * 64,
        source_artifact_state=SourceArtifactState.ATTACHED,
        source_artifact_id=uuid4(),
        source_artifact_sha256="c" * 64,
        validation_status=EvidenceValidationStatus.WARNING,
        validation_summary="Current identity and digest verified.",
        created_by=PRINCIPAL,
        created_at=NOW,
        change_reason="Review the exact imported document",
        exact_input_use=(f"datasets.test_data_document:{SUBJECT}:{REVISION}",),
        affected_material_id=uuid4(),
        affected_material_revision_id=uuid4(),
        affected_record_id=uuid4(),
        affected_record_revision_id=uuid4(),
        affected_table_id=uuid4(),
        affected_table_revision_id=uuid4(),
        output_artifact_sha256="d" * 64,
    )

    restored = ReviewSubjectEvidence.from_document(evidence.to_document())

    assert restored == evidence
    assert (
        restored.to_document()["affected_materials"] == evidence.to_document()["affected_materials"]
    )
    with pytest.raises(ReviewEvidenceError, match="not registered"):
        replace(evidence, subject_type="validation.result")


def test_neutral_solver_card_evidence_uses_the_authoritative_material_name_column() -> None:
    _, revision, label_columns = _SUBJECTS["exporting.neutral_solver_card"]

    assert revision.c.material_name.name == "material_name"
    assert "card_title" not in revision.c
    assert label_columns == ("material_name",)


@pytest.mark.parametrize(
    "field",
    ["affected_table_id", "affected_table_revision_id"],
)
def test_record_table_pins_must_be_paired(field: str) -> None:
    values: dict[str, Any] = dict(
        subject_type="catalog.configurable_record",
        subject_id=SUBJECT,
        subject_revision_id=REVISION,
        label="Material Record",
        classification=DataClassification.INTERNAL,
        schema_ref="cmp.catalog-record",
        schema_version="1.0.0",
        server_manifest_sha256="b" * 64,
        source_artifact_state=SourceArtifactState.UNATTACHED,
        source_artifact_id=None,
        source_artifact_sha256=None,
        validation_status=EvidenceValidationStatus.VALID,
        validation_summary="Current identity and digest verified.",
        created_by=PRINCIPAL,
        created_at=NOW,
        change_reason="Review the exact Catalog Record",
        exact_input_use=(f"catalog.configurable_record:{SUBJECT}:{REVISION}",),
        affected_record_id=SUBJECT,
        affected_record_revision_id=REVISION,
        affected_table_id=uuid4(),
        affected_table_revision_id=uuid4(),
    )
    values[field] = None
    with pytest.raises(ReviewEvidenceError, match="table identity and revision"):
        ReviewSubjectEvidence(**values)


@pytest.mark.parametrize(
    "field",
    ["affected_material_id", "affected_material_revision_id"],
)
def test_affected_material_pins_must_be_paired(field: str) -> None:
    values: dict[str, Any] = dict(
        subject_type="datasets.test_data_document",
        subject_id=SUBJECT,
        subject_revision_id=REVISION,
        label="DMA Test Data",
        classification=DataClassification.INTERNAL,
        schema_ref="cmp.test-data",
        schema_version="1.0.0",
        server_manifest_sha256="b" * 64,
        source_artifact_state=SourceArtifactState.UNATTACHED,
        source_artifact_id=None,
        source_artifact_sha256=None,
        validation_status=EvidenceValidationStatus.VALID,
        validation_summary="Current identity and digest verified.",
        created_by=PRINCIPAL,
        created_at=NOW,
        change_reason="Review exact governed DMA Test Data",
        exact_input_use=(f"datasets.test_data_document:{SUBJECT}:{REVISION}",),
        affected_record_id=None,
        affected_record_revision_id=None,
        affected_material_id=uuid4(),
        affected_material_revision_id=uuid4(),
    )
    values[field] = None
    with pytest.raises(ReviewEvidenceError, match="Material identity and revision"):
        ReviewSubjectEvidence(**values)


def test_output_artifact_digest_requires_lowercase_sha256() -> None:
    with pytest.raises(ReviewEvidenceError, match="output_artifact_sha256"):
        ReviewSubjectEvidence(
            subject_type="exporting.solver_card",
            subject_id=SUBJECT,
            subject_revision_id=REVISION,
            label="OpenRadioss card",
            classification=DataClassification.INTERNAL,
            schema_ref="cmp.solver-card",
            schema_version="1.0.0",
            server_manifest_sha256="b" * 64,
            source_artifact_state=SourceArtifactState.UNATTACHED,
            source_artifact_id=None,
            source_artifact_sha256=None,
            validation_status=EvidenceValidationStatus.VALID,
            validation_summary="Current identity and digest verified.",
            created_by=PRINCIPAL,
            created_at=NOW,
            change_reason="Review the exact solver card",
            exact_input_use=(f"exporting.solver_card:{SUBJECT}:{REVISION}",),
            affected_record_id=uuid4(),
            affected_record_revision_id=uuid4(),
            output_artifact_sha256="NOT-A-DIGEST",
        )


@pytest.mark.parametrize(
    "field",
    [
        "neutral_material_id",
        "neutral_material_revision_id",
        "neutral_artifact_sha256",
    ],
)
def test_neutral_evidence_requires_identity_revision_and_digest_as_one_exact_triple(
    field: str,
) -> None:
    evidence = ReviewSubjectEvidence(
        subject_type="exporting.solver_card",
        subject_id=SUBJECT,
        subject_revision_id=REVISION,
        label="OpenRadioss card",
        classification=DataClassification.INTERNAL,
        schema_ref="cmp.solver-card",
        schema_version="1.0.0",
        server_manifest_sha256="b" * 64,
        source_artifact_state=SourceArtifactState.UNATTACHED,
        source_artifact_id=None,
        source_artifact_sha256=None,
        validation_status=EvidenceValidationStatus.VALID,
        validation_summary="Current identity and digest verified.",
        created_by=PRINCIPAL,
        created_at=NOW,
        change_reason="Review the exact solver card",
        exact_input_use=(f"exporting.solver_card:{SUBJECT}:{REVISION}",),
        affected_record_id=uuid4(),
        affected_record_revision_id=uuid4(),
        affected_table_id=uuid4(),
        affected_table_revision_id=uuid4(),
        neutral_material_id=UUID("16000000-0000-4000-0000-000000000006"),
        neutral_material_revision_id=UUID("16000000-0000-4000-0000-000000000007"),
        neutral_artifact_sha256="d" * 64,
    )

    with pytest.raises(
        ReviewEvidenceError, match="Neutral identity, revision, and artifact digest"
    ):
        replace(evidence, **cast(Any, {field: None}))

from pathlib import Path


def test_uxc06b_migration_adds_nullable_proof_without_backfilling_history() -> None:
    text = Path(
        "backend/migrations/versions/20260726_088_uxc06b_export_provenance.py"
    ).read_text(encoding="utf-8")

    assert "datasets.test_data_document_revision" in text
    assert "processing.common_processing_output_revision" in text
    assert "ADD COLUMN governed_source jsonb NULL" in text
    assert "ADD COLUMN export_provenance jsonb NULL" in text
    assert "UPDATE " not in text
    assert "DROP COLUMN export_provenance" in text
    assert "DROP COLUMN governed_source" in text

from pathlib import Path


def test_uxc07_batch_evidence_migration_adds_typed_json_guards_and_guarded_downgrade() -> None:
    text = Path(
        "backend/migrations/versions/20260922_091_UXC07_batch_evidence.py"
    ).read_text(encoding="utf-8")

    assert "processing.common_processing_batch_member" in text
    assert "ADD COLUMN workup_overrides jsonb NOT NULL DEFAULT '[]'::jsonb" in text
    assert "ADD COLUMN fit_decision jsonb NULL" in text
    assert "jsonb_typeof(workup_overrides) = 'array'" in text
    assert "jsonb_typeof(fit_decision) = 'object'" in text
    assert "cannot downgrade while immutable Processing Batch member evidence exists" in text

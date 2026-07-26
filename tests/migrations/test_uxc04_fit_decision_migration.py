from pathlib import Path


def test_uxc04_fit_decision_migration_preserves_decision_across_downstream_revisions() -> None:
    text = Path(
        "backend/migrations/versions/20260725_087_uxc04_fit_decision_snapshot.py"
    ).read_text(encoding="utf-8")

    for table in (
        "processing.common_processing_output_revision",
        "modeling.material_model_revision",
        "modeling.linear_viscoelastic_processing_evidence",
        "modeling.neutral_material_revision",
    ):
        assert table in text
    assert text.count("fit_decision_evidence jsonb NULL") == 3
    assert "fit_decision jsonb NULL" in text
    assert "cannot downgrade while immutable Processing Output fit decisions exist" in text

from pathlib import Path


def test_issue158_metal_fit_migration_pins_source_and_retains_attempt_evidence() -> None:
    source = Path(
        "backend/migrations/versions/20260924_093_issue158_metal_fit.py"
    ).read_text(encoding="utf-8")
    assert 'down_revision: str | None = "20260923_092_uxc08"' in source
    assert "source_processing_output_id" in source
    assert "source_processing_output_revision_id" in source
    assert "source_processing_output_sha256" in source
    assert "processing.metal_fit_run" in source
    assert "processing.metal_fit_attempt" in source
    assert "objective_history" in source
    assert "reproducibility_evidence" in source
    assert "FORCE ROW LEVEL SECURITY" in source
    assert "processing_metal_fit_run_source" in source
    assert "processing_metal_fit_attempt_run" in source
    assert "status IN ('executing','succeeded','failed','cancelled')" in source
    for column in (
        "source_document_id",
        "source_document_revision_id",
        "mapping_profile_id",
        "mapping_profile_revision_id",
    ):
        assert f"NEW.{column} IS DISTINCT FROM OLD.{column}" in source

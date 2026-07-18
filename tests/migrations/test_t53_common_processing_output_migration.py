from pathlib import Path


def test_t53_common_output_pins_exact_inputs_and_immutable_artifact() -> None:
    source = Path(
        "backend/migrations/versions/20260830_064_T53_common_processing_outputs.py"
    ).read_text(encoding="utf-8")
    assert 'down_revision: str | None = "20260829_063_t53_map"' in source
    for table in (
        "processing.common_processing_output",
        "processing.common_processing_output_revision",
        "processing.common_processing_output_step",
    ):
        assert table in source
    assert "fk_processing_common_output_source_exact" in source
    assert "fk_processing_common_output_profile_exact" in source
    assert "fk_processing_common_output_artifact" in source
    assert "revision_no=1" in source
    assert "based_on_revision_id IS NULL" in source
    assert "method_version" in source
    assert "options_sha256" in source
    assert "reject_immutable_row_mutation" in source
    assert "FORCE ROW LEVEL SECURITY" in source

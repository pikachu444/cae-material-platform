from pathlib import Path

PROJECT_ROOT = Path(__file__).parents[2]


def test_t40_migration_is_typed_scoped_immutable_and_non_eav() -> None:
    source = (
        PROJECT_ROOT / "backend/migrations/versions/20260816_050_T40_test_context.py"
    ).read_text(encoding="utf-8")

    for table in (
        "test_campaign_revision",
        "instrument_revision",
        "instrument_calibration_revision",
        "test_condition_snapshot_revision",
        "test_run_context_revision",
    ):
        assert table in source
    for column in (
        "standard_designation",
        "standard_edition",
        "standard_deviation_reason",
        "valid_from",
        "valid_until",
        "temperature_observed_k",
        "loading_rate_unit",
        "test_run_revision_id",
        "calibration_revision_id",
    ):
        assert column in source
    assert "validate_instrument_calibration_revision" in source
    assert "validate_test_run_context_revision" in source
    assert "FORCE ROW LEVEL SECURITY" in source
    assert "revisioning.reject_immutable_row_mutation()" in source
    assert "revisioning.guard_identity_head_update()" in source
    assert "JSON" not in source
    assert '"attribute"' not in source
    assert '"value"' not in source

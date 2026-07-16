from __future__ import annotations

from pathlib import Path

MIGRATION = (
    Path(__file__).parents[2]
    / "backend/migrations/versions/20260817_051_T41_governed_tabular_import.py"
)


def test_t41_migration_uses_explicit_typed_tables_and_rls() -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    for table in (
        "datasets.import_profile",
        "datasets.import_profile_revision",
        "datasets.import_profile_channel",
        "datasets.tabular_preview_report",
        "datasets.governed_dataset",
        "datasets.governed_dataset_revision",
        "datasets.governed_dataset_channel",
        "datasets.tabular_import_run",
        "datasets.tabular_import_row_error",
    ):
        assert f"CREATE TABLE {table}" in source
    assert "revisioning.reject_immutable_row_mutation()" in source
    assert "revisioning.guard_identity_head_update()" in source
    assert "ENABLE ROW LEVEL SECURITY" in source
    assert "FORCE ROW LEVEL SECURITY" in source
    assert "dataset.read" in source and "dataset.write" in source
    assert "jsonb" not in source.lower()
    assert "attribute_key" not in source.lower()


def test_t41_migration_pins_exact_sources_and_safe_terminal_state() -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    assert "test_run_revision_id uuid NOT NULL" in source
    assert "import_profile_revision_id uuid NOT NULL" in source
    assert "source_dataset_revision_id uuid" in source
    assert "status IN ('executing','succeeded','failed')" in source
    assert "terminal tabular Import Runs are immutable" in source
    assert "ck_datasets_governed_dataset_representation" in source

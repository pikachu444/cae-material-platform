from __future__ import annotations

from pathlib import Path

MIGRATION = (
    Path(__file__).parents[2]
    / "backend/migrations/versions/20260822_056_T45_bulk_export_bundle.py"
)


def test_t45_migration_uses_typed_immutable_resources_and_rls() -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    for table in (
        "exporting.export_selection",
        "exporting.export_selection_revision",
        "exporting.export_selection_member",
        "exporting.export_selection_omission",
        "exporting.bulk_export_job",
        "exporting.bulk_export_bundle",
    ):
        assert f"CREATE TABLE {table}" in source
    assert "guard_bulk_export_immutable()" in source
    assert "ENABLE ROW LEVEL SECURITY" in source
    assert "FORCE ROW LEVEL SECURITY" in source
    assert "export.read" in source and "export.execute" in source
    assert "jsonb" not in source.lower()
    assert "attribute_key" not in source.lower()


def test_t45_migration_pins_every_exact_source_and_enforces_transitions() -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    for exact_reference in (
        "raw_asset_id uuid",
        "artifact_id uuid",
        "dataset_revision_id uuid",
        "material_model_revision_id uuid",
        "solver_card_revision_id uuid",
        "source_sha256 char(64) NOT NULL",
    ):
        assert exact_reference in source
    assert "ck_exporting_export_selection_member_typed_source" in source
    assert "ck_exporting_export_selection_omission_typed_source" in source
    assert "OLD.state='queued' AND NEW.state='running'" in source
    assert "OLD.state='running' AND NEW.state IN ('succeeded','failed')" in source
    assert "selection classification must equal the maximum component classification" in source
    assert "1000" in source
    assert "5368709120" in source

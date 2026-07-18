from io import StringIO
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

PROJECT_ROOT = Path(__file__).parents[2]


def _migration_sql() -> str:
    output = StringIO()
    config = Config(str(PROJECT_ROOT / "alembic.ini"), output_buffer=output)
    script = ScriptDirectory.from_config(config)
    assert script.get_current_head() == "20260908_073_t58_bulk"
    from alembic import command

    command.upgrade(config, "head", sql=True)
    sql = output.getvalue()
    return sql[sql.index("20260908_073_t58_bulk") :]


def test_t58_bulk_sources_are_explicit_typed_revision_pairs() -> None:
    migration = _migration_sql()

    for kind in (
        "test_data_json",
        "mapping_profile_json",
        "processing_recipe_json",
        "neutral_material_json",
        "neutral_solver_mapping_report",
        "neutral_solver_card_native",
    ):
        assert kind in migration
    for revision_column in (
        "test_data_document_revision_id",
        "mapping_profile_revision_id",
        "processing_recipe_revision_id",
        "neutral_material_revision_id",
        "neutral_solver_card_revision_id",
    ):
        assert f"ADD COLUMN {revision_column} uuid" in migration
    assert "num_nonnulls" in migration
    assert "jsonb" not in migration.lower()


def test_t58_member_sources_have_exact_scope_foreign_keys_and_index() -> None:
    migration = _migration_sql()

    for constraint in (
        "fk_export_selection_member_test_json",
        "fk_export_selection_member_mapping_profile",
        "fk_export_selection_member_processing_recipe",
        "fk_export_selection_member_neutral_json",
        "fk_export_selection_member_neutral_card",
    ):
        assert constraint in migration
    assert "ix_export_selection_member_canonical_source" in migration
    assert "processing_mapping_profile_revision_export_select" in migration
    assert "processing_common_recipe_revision_export_select" in migration
    assert "'export.read'" in migration

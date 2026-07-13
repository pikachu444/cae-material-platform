from io import StringIO
from pathlib import Path

from alembic import command
from alembic.config import Config

PROJECT_ROOT = Path(__file__).parents[2]


def _configuration(output: StringIO) -> Config:
    return Config(str(PROJECT_ROOT / "alembic.ini"), output_buffer=output)


def test_t19_migration_renders_typed_selection_processing_and_processed_dataset_guards() -> None:
    output = StringIO()
    command.upgrade(_configuration(output), "head", sql=True)

    sql = output.getvalue()
    for relation in (
        "datasets.dataset_selection",
        "datasets.dataset_selection_revision",
        "processing.processing_recipe",
        "processing.processing_recipe_revision",
        "processing.processing_run",
    ):
        assert f"CREATE TABLE {relation}" in sql
        assert f"ALTER TABLE {relation} FORCE ROW LEVEL SECURITY" in sql
    for constraint in (
        "fk_datasets_dataset_selection_revision_dataset",
        "fk_processing_run_selection_revision",
        "fk_processing_run_recipe_revision",
        "fk_processing_run_input_dataset_revision",
        "fk_processing_run_output_dataset_revision",
        "fk_datasets_dataset_revision_processing_run",
        "ck_processing_run_terminal_shape",
        "ck_datasets_dataset_revision_source_representation",
    ):
        assert constraint in sql
    for index in (
        "ix_datasets_dataset_selection_revision_dataset",
        "ix_processing_recipe_tenant_created",
        "ix_processing_run_input",
        "ix_datasets_dataset_processing_run",
        "ux_datasets_dataset_import_source",
        "ux_datasets_dataset_processing_run",
    ):
        assert index in sql
    assert "representation IN ('raw', 'normalized', 'processed')" in sql
    assert "processing.guard_processing_run_insert()" in sql
    assert "processing.guard_processing_run_transition()" in sql
    assert "datasets.guard_reference_dataset_selection_revision_insert()" in sql
    assert "'processing.read'" in sql
    assert "'processing.execute'" in sql
    assert "postgresql.JSONB" not in sql
    assert '"key"' not in sql
    assert '"value"' not in sql


def test_t19_downgrade_keeps_history_safe_and_removes_triggers_before_functions() -> None:
    output = StringIO()
    command.downgrade(
        _configuration(output),
        "20260715_017_t19:20260714_016_t08_t12",
        sql=True,
    )

    sql = output.getvalue()
    assert "T-19 downgrade requires empty Processing, Selection" in sql
    assert sql.index("DROP TRIGGER processing_run_transition_guard") < sql.index(
        "DROP FUNCTION processing.guard_processing_run_transition()"
    )
    assert "representation IN ('raw', 'normalized')" in sql
    assert "DROP TABLE processing.processing_run" in sql
    assert "DROP TABLE datasets.dataset_selection_revision" in sql

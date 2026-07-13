from io import StringIO
from pathlib import Path

from alembic import command
from alembic.config import Config

PROJECT_ROOT = Path(__file__).parents[2]


def test_reference_tensile_migration_renders_typed_testing_dataset_tables_and_rls() -> None:
    output = StringIO()
    configuration = Config(str(PROJECT_ROOT / "alembic.ini"), output_buffer=output)

    command.upgrade(configuration, "head", sql=True)

    sql = output.getvalue()
    for relation in (
        "testing.specimen",
        "testing.specimen_revision",
        "testing.test_method",
        "testing.test_method_revision",
        "testing.test_run",
        "testing.test_run_revision",
        "datasets.dataset",
        "datasets.dataset_revision",
    ):
        assert f"CREATE TABLE {relation}" in sql
    for constraint in (
        "fk_testing_specimen_revision_material_state",
        "fk_testing_test_run_revision_identity_source",
        "fk_datasets_dataset_revision_test_run",
        "fk_datasets_dataset_revision_data_artifact",
        "uq_datasets_dataset_source",
        "ck_datasets_dataset_revision_source_representation",
    ):
        assert constraint in sql
    for index in (
        "ix_testing_specimen_state",
        "ix_testing_test_run_specimen",
        "ix_datasets_dataset_test_run",
        "ix_datasets_dataset_revision_raw_asset",
    ):
        assert index in sql
    for relation in (
        "testing.specimen",
        "testing.test_method",
        "testing.test_run",
        "datasets.dataset",
        "datasets.dataset_revision",
    ):
        assert f"ALTER TABLE {relation} FORCE ROW LEVEL SECURITY" in sql
    assert "datasets.guard_reference_dataset_revision_insert()" in sql
    assert "revisioning.reject_immutable_row_mutation()" in sql
    assert "'testing.read'" in sql
    assert "'testing.write'" in sql
    assert "'dataset.read'" in sql
    assert "'dataset.write'" in sql
    assert "postgresql.JSONB" not in sql
    assert "sa.JSON" not in sql
    assert '"key"' not in sql
    assert '"value"' not in sql

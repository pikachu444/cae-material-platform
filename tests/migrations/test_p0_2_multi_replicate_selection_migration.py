from io import StringIO
from pathlib import Path

from alembic import command
from alembic.config import Config

PROJECT_ROOT = Path(__file__).parents[2]


def _configuration(output: StringIO) -> Config:
    return Config(str(PROJECT_ROOT / "alembic.ini"), output_buffer=output)


def test_multi_replicate_selection_has_typed_membership_rls_and_guards() -> None:
    output = StringIO()
    command.upgrade(_configuration(output), "head", sql=True)

    sql = output.getvalue()
    assert "CREATE TABLE datasets.dataset_selection_member" in sql
    assert "reference_tensile_replicate_set" in sql
    assert "uq_datasets_dataset_selection_member_dataset" in sql
    assert "uq_datasets_dataset_selection_member_test_run" in sql
    assert "fk_datasets_dataset_selection_member_dataset_revision" in sql
    assert "fk_datasets_dataset_selection_member_test_run_revision" in sql
    assert "ALTER TABLE datasets.dataset_selection_member FORCE ROW LEVEL SECURITY" in sql
    assert "datasets.guard_reference_dataset_selection_member_insert()" in sql
    assert "datasets.validate_dataset_selection_member_count()" in sql
    assert "provenance.guard_activity_input_finalization()" in sql
    assert "activity_authorized_input_finalization" in sql
    assert "postgresql.JSONB" not in sql


def test_multi_replicate_selection_downgrade_refuses_to_destroy_membership() -> None:
    output = StringIO()
    command.downgrade(
        _configuration(output),
        "20260728_030_p02:20260727_029_p0",
        sql=True,
    )

    sql = output.getvalue()
    assert "cannot downgrade while multi-replicate Selections exist" in sql
    assert sql.index("DROP TRIGGER datasets_dataset_selection_member_count_guard") < sql.index(
        "DROP FUNCTION datasets.validate_dataset_selection_member_count()"
    )
    assert "DROP TABLE datasets.dataset_selection_member" in sql

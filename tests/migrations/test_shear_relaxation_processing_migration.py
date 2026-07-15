from io import StringIO
from pathlib import Path

from alembic import command
from alembic.config import Config

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_shear_processing_is_explicit_scoped_immutable_and_non_eav() -> None:
    output = StringIO()
    command.upgrade(
        Config(str(PROJECT_ROOT / "alembic.ini"), output_buffer=output),
        "head",
        sql=True,
    )
    sql = output.getvalue()
    assert "processing.shear_relaxation_recipe" in sql
    assert "processing.shear_relaxation_recipe_revision" in sql
    assert "processing.shear_relaxation_run" in sql
    assert "minimum_time_s double precision" in sql
    assert "input_dataset_revision_id uuid" in sql
    assert "processing_run_id uuid" in sql
    assert "representation='processed'" in sql
    assert "FORCE ROW LEVEL SECURITY" in sql
    assert "guard_shear_relaxation_run_insert" in sql
    assert "guard_shear_relaxation_run_transition" in sql
    migration = (
        PROJECT_ROOT
        / "backend/migrations/versions/20260809_043_shear_relaxation_processing.py"
    ).read_text(encoding="utf-8")
    assert "JSON" not in migration
    assert '"attribute"' not in migration
    assert '"value"' not in migration

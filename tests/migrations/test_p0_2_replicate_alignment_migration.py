from io import StringIO
from pathlib import Path

from alembic import command
from alembic.config import Config

PROJECT_ROOT = Path(__file__).parents[2]


def test_alignment_migration_has_explicit_typed_columns_guards_and_no_eav() -> None:
    output = StringIO()
    command.upgrade(
        Config(str(PROJECT_ROOT / "alembic.ini"), output_buffer=output),
        "head",
        sql=True,
    )
    sql = output.getvalue()
    for value in (
        "grid_start_engineering_strain",
        "grid_end_engineering_strain",
        "grid_point_count",
        "domain_policy",
        "interpolation_policy",
        "extrapolation_policy",
        "ux_processing_run_alignment_batch_member",
        "alignment Run input must equal its ordered replicate member",
        "provenance.guard_association_plan_finalization()",
    ):
        assert value in sql
    assert "postgresql.JSONB" not in sql

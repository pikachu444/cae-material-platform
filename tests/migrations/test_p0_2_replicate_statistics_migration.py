from io import StringIO
from pathlib import Path

from alembic import command
from alembic.config import Config

PROJECT_ROOT = Path(__file__).parents[2]


def test_replicate_statistics_migration_is_typed_scoped_and_non_eav() -> None:
    output = StringIO()
    command.upgrade(
        Config(str(PROJECT_ROOT / "alembic.ini"), output_buffer=output),
        "head",
        sql=True,
    )
    sql = output.getvalue()
    for value in (
        "statistics.replicate_statistical_plan_revision",
        "statistics.replicate_statistical_run_member",
        "statistics.replicate_statistical_result_revision",
        "statistics.replicate_qc_observation",
        "exact_processed_grid_match_no_alignment",
        "student_t_95_two_sided",
        "mean_confidence_interval_lower_95_pa",
        "ALTER TABLE statistics.replicate_statistical_run FORCE ROW LEVEL SECURITY",
        "guard_replicate_run_transition",
        "revisioning.reject_immutable_row_mutation()",
    ):
        assert value in sql
    assert "postgresql.JSONB" not in sql

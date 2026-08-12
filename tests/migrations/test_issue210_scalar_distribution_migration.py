from io import StringIO
from pathlib import Path

from alembic import command
from alembic.config import Config

PROJECT_ROOT = Path(__file__).parents[2]


def test_issue210_distribution_migration_extends_one_typed_statistics_lifecycle() -> None:
    output = StringIO()
    command.upgrade(
        Config(str(PROJECT_ROOT / "alembic.ini"), output_buffer=output),
        "head",
        sql=True,
    )
    sql = output.getvalue()
    for value in (
        "statistics.scalar_distribution_result",
        "statistics.scalar_distribution_result_revision",
        "statistics.scalar_distribution_selection",
        "statistics.scalar_distribution_selection_revision",
        "scalar_distribution_result_revision_id",
        "distribution_bootstrap_samples",
        "fk_statistics_replicate_plan_unit_profile",
        "fk_statistics_scalar_distribution_source_result",
        "fk_statistics_scalar_distribution_artifact",
        "aicc_delta_le_2_at_least_two_successful_candidates_v1",
        "numpy.random.PCG64",
        "guard_scalar_distribution_result_insert",
        "guard_scalar_distribution_selection_insert",
        "revisioning.reject_immutable_row_mutation()",
        "ALTER TABLE statistics.scalar_distribution_result_revision FORCE ROW LEVEL SECURITY",
    ):
        assert value in sql
    assert "CREATE TABLE statistics.scalar_distribution_plan" not in sql
    assert "CREATE TABLE statistics.scalar_distribution_run" not in sql
    assert "postgresql.JSONB" not in sql

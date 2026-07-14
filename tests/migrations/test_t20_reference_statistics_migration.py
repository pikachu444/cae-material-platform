from io import StringIO
from pathlib import Path

from alembic import command
from alembic.config import Config

PROJECT_ROOT = Path(__file__).parents[2]


def _configuration(output: StringIO) -> Config:
    return Config(str(PROJECT_ROOT / "alembic.ini"), output_buffer=output)


def test_t20_migration_renders_typed_statistics_qc_and_immutable_result_guards() -> None:
    output = StringIO()
    command.upgrade(_configuration(output), "head", sql=True)

    sql = output.getvalue()
    for relation in (
        "statistics.statistical_plan",
        "statistics.statistical_plan_revision",
        "statistics.statistical_result",
        "statistics.statistical_result_revision",
        "statistics.statistical_run",
        "statistics.qc_observation",
    ):
        assert f"CREATE TABLE {relation}" in sql
        assert f"ALTER TABLE {relation} FORCE ROW LEVEL SECURITY" in sql
    for constraint in (
        "fk_statistics_plan_revision_first_selection",
        "fk_statistics_plan_revision_second_selection",
        "fk_statistics_statistical_run_plan",
        "fk_statistics_statistical_run_first_dataset",
        "fk_statistics_statistical_run_second_dataset",
        "fk_statistics_statistical_result_revision_run",
        "ck_statistics_statistical_result_revision_first_only",
        "ck_statistics_statistical_run_terminal_shape",
    ):
        assert constraint in sql
    for index in (
        "ix_statistics_plan_tenant_created",
        "ix_statistics_plan_selection",
        "ix_statistics_plan_second_selection",
        "ix_statistics_run_plan",
        "ix_statistics_result_run",
        "ix_statistics_qc_run",
    ):
        assert index in sql
    assert "statistics.guard_statistical_plan_revision_insert()" in sql
    assert "statistics.guard_statistical_run_transition()" in sql
    assert "statistics.guard_statistical_result_revision_insert()" in sql
    assert "statistics.guard_qc_observation_insert()" in sql
    assert (
        "CONSTRAINT uq_statistics_statistical_plan_identity_kind "
        "UNIQUE (organization_id, project_id, classification, id, plan_kind)"
    ) in sql
    assert (
        "FOREIGN KEY(organization_id, project_id, classification, aggregate_id, plan_kind) "
        "REFERENCES statistics.statistical_plan "
        "(organization_id, project_id, classification, id, plan_kind)"
    ) in sql
    assert "exact_observed_grid_match_no_alignment" in sql
    assert "not_provided_reference_pair" in sql
    assert "'statistics.read'" in sql
    assert "'statistics.execute'" in sql
    assert "postgresql.JSONB" not in sql
    assert '"key"' not in sql
    assert '"value"' not in sql


def test_t20_downgrade_keeps_statistics_history_safe_and_removes_triggers_before_functions(
) -> None:
    output = StringIO()
    command.downgrade(
        _configuration(output),
        "20260716_018_t20:20260715_017_t19",
        sql=True,
    )

    sql = output.getvalue()
    assert "T-20 downgrade requires empty Statistics history" in sql
    assert sql.index("DROP TRIGGER statistics_qc_observation_insert_guard") < sql.index(
        "DROP FUNCTION statistics.guard_qc_observation_insert()"
    )
    assert "DROP TABLE statistics.statistical_run" in sql
    assert "DROP TABLE statistics.statistical_plan_revision" in sql

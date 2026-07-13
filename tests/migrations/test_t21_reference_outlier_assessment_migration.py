from io import StringIO
from pathlib import Path

from alembic import command
from alembic.config import Config

PROJECT_ROOT = Path(__file__).parents[2]


def _configuration(output: StringIO) -> Config:
    return Config(str(PROJECT_ROOT / "alembic.ini"), output_buffer=output)


def test_t21_migration_renders_typed_outlier_candidates_assessments_and_tenant_guards() -> None:
    output = StringIO()
    command.upgrade(_configuration(output), "head", sql=True)

    sql = output.getvalue()
    for relation in (
        "statistics.outlier_detection_plan",
        "statistics.outlier_detection_plan_revision",
        "statistics.outlier_detection_run",
        "statistics.outlier_candidate",
        "statistics.outlier_assessment",
        "statistics.outlier_assessment_revision",
    ):
        assert f"CREATE TABLE {relation}" in sql
        assert f"ALTER TABLE {relation} FORCE ROW LEVEL SECURITY" in sql
    for constraint in (
        "fk_statistics_outlier_detection_plan_revision_result",
        "fk_statistics_outlier_detection_run_plan",
        "fk_statistics_outlier_candidate_selection",
        "fk_statistics_outlier_candidate_dataset",
        "fk_statistics_outlier_assessment_revision_candidate",
        "ck_statistics_outlier_assessment_revision_first_only",
        "ck_statistics_outlier_detection_run_terminal_shape",
    ):
        assert constraint in sql
    for index in (
        "ix_statistics_outlier_detection_plan_result",
        "ix_statistics_outlier_detection_run_plan",
        "ix_statistics_outlier_candidate_plan",
        "ix_statistics_outlier_assessment_candidate_scope",
    ):
        assert index in sql
    assert "statistics.guard_outlier_candidate_insert()" in sql
    assert "statistics.guard_outlier_assessment_revision_insert()" in sql
    assert "statistics.validate_outlier_detection_run_candidate_count()" in sql
    assert "DEFERRABLE INITIALLY DEFERRED" in sql
    assert "flag_both_pair_members_for_human_review" in sql
    assert "excluded_from_reference_analysis" in sql
    assert "'statistics.read'" in sql
    assert "'statistics.execute'" in sql
    assert "postgresql.JSONB" not in sql
    assert '"key"' not in sql
    assert '"value"' not in sql


def test_t21_downgrade_drops_triggers_before_their_functions_and_keeps_evidence_safe() -> None:
    output = StringIO()
    command.downgrade(
        _configuration(output),
        "20260717_019_t21:20260716_018_t20",
        sql=True,
    )

    sql = output.getvalue()
    assert "cannot downgrade T-21 while outlier evidence exists" in sql
    assert sql.index("DROP TRIGGER statistics_outlier_candidate_count_guard") < sql.index(
        "DROP FUNCTION statistics.validate_outlier_detection_run_candidate_count()"
    )
    assert sql.index("DROP TRIGGER statistics_outlier_assessment_revision_guard") < sql.index(
        "DROP FUNCTION statistics.guard_outlier_assessment_revision_insert()"
    )
    assert "DROP TABLE statistics.outlier_candidate" in sql
    assert "DROP TABLE statistics.outlier_detection_plan_revision" in sql

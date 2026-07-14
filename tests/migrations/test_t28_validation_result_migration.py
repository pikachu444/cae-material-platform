from io import StringIO
from pathlib import Path

from alembic import command
from alembic.config import Config

PROJECT_ROOT = Path(__file__).parents[2]


def test_t28_migration_renders_typed_validation_interpretation_relations_guards_and_rls() -> None:
    output = StringIO()
    configuration = Config(str(PROJECT_ROOT / "alembic.ini"), output_buffer=output)

    command.upgrade(configuration, "head", sql=True)

    sql = output.getvalue()
    required = {
        "CREATE TABLE validation.validation_response_extraction",
        "CREATE TABLE validation.validation_numerical_health_report",
        "CREATE TABLE validation.validation_result",
        "CREATE TABLE validation.validation_result_comparison_point",
        "source_native_result_artifact_id",
        "normalized_response_artifact_id",
        "health_status",
        "solver_termination",
        "relative_root_mean_squared_error",
        "holdout_independence",
        "comparison_point",
        "CREATE FUNCTION validation.guard_validation_response_extraction_insert()",
        "CREATE FUNCTION validation.guard_validation_numerical_health_report_insert()",
        "CREATE FUNCTION validation.guard_validation_result_insert()",
        "CREATE FUNCTION validation.guard_validation_result_comparison_points()",
        "CREATE TRIGGER validation_response_extraction_input_guard",
        "CREATE TRIGGER validation_numerical_health_report_input_guard",
        "CREATE TRIGGER validation_result_input_guard",
        "CREATE CONSTRAINT TRIGGER validation_result_comparison_point_count_guard",
        "ALTER TABLE validation.validation_response_extraction FORCE ROW LEVEL SECURITY",
        "ALTER TABLE validation.validation_numerical_health_report FORCE ROW LEVEL SECURITY",
        "ALTER TABLE validation.validation_result FORCE ROW LEVEL SECURITY",
        "ALTER TABLE validation.validation_result_comparison_point FORCE ROW LEVEL SECURITY",
        "reference-linear-interpolation-observed-grid",
        "overlaps_calibration_selection",
    }

    assert all(fragment in sql for fragment in required)

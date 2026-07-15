from io import StringIO
from pathlib import Path

from alembic import command
from alembic.config import Config

PROJECT_ROOT = Path(__file__).parents[2]


def test_reference_voce_migration_is_typed_scoped_solver_neutral_and_non_eav() -> None:
    output = StringIO()
    command.upgrade(
        Config(str(PROJECT_ROOT / "alembic.ini"), output_buffer=output),
        "head",
        sql=True,
    )
    sql = output.getvalue()
    for value in (
        "modeling.voce_calibration_plan_revision",
        "modeling.voce_calibration_run",
        "modeling.voce_calibration_attempt",
        "modeling.voce_calibration_candidate",
        "modeling.voce_calibration_objective_term",
        "reference_multi_curve_voce_saturation",
        "mean_of_specimen_mean_normalized_squared_residual",
        "numpy.random.PCG64",
        "scipy-least-squares",
        "statistics.calibration_input_scope_revision",
        "catalog.property_set_revision",
        "ALTER TABLE modeling.voce_calibration_candidate FORCE ROW LEVEL SECURITY",
        "revisioning.reject_immutable_row_mutation()",
    ):
        assert value in sql
    voce_start = sql.index("CREATE TABLE modeling.voce_calibration_plan (")
    voce_end = sql.index("CREATE TABLE modeling.voce_candidate_selection (", voce_start)
    voce_sql = sql[voce_start:voce_end]
    assert "postgresql.JSON" not in voce_sql
    assert "JSONB" not in voce_sql
    assert "abaqus" not in voce_sql.lower()
    assert "radioss" not in voce_sql.lower()

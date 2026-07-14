from io import StringIO
from pathlib import Path

from alembic import command
from alembic.config import Config

PROJECT_ROOT = Path(__file__).parents[2]


def test_t23_downgrade_breaks_candidate_and_identity_head_cycles_first() -> None:
    output = StringIO()
    configuration = Config(str(PROJECT_ROOT / "alembic.ini"), output_buffer=output)
    command.downgrade(
        configuration,
        "20260719_021_t23:20260718_020_t11",
        sql=True,
    )

    sql = output.getvalue()
    attempt_candidate_fk = sql.index(
        "DROP CONSTRAINT IF EXISTS fk_modeling_calibration_attempt_candidate"
    )
    assert attempt_candidate_fk < sql.index("DROP TABLE modeling.calibration_candidate")
    assert sql.index(
        "DROP CONSTRAINT IF EXISTS fk_modeling_calibration_plan_current_revision"
    ) < sql.index("DROP TABLE modeling.calibration_plan_revision")

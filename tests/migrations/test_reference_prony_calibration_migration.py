from io import StringIO
from pathlib import Path

from alembic import command
from alembic.config import Config

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_prony_calibration_is_typed_scoped_immutable_and_non_eav() -> None:
    output = StringIO()
    command.upgrade(
        Config(str(PROJECT_ROOT / "alembic.ini"), output_buffer=output),
        "head",
        sql=True,
    )
    sql = output.getvalue()
    for table in (
        "modeling.prony_calibration_plan",
        "modeling.prony_calibration_plan_revision",
        "modeling.prony_calibration_run",
        "modeling.prony_calibration_attempt",
        "modeling.prony_calibration_candidate",
    ):
        assert table in sql
    assert "input_dataset_revision_id uuid" in sql
    assert "baseline_model_revision_id uuid" in sql
    assert "fast_relaxation_time_s float8" in sql
    assert "diagnostics_artifact_id uuid" in sql
    assert "validate_reference_prony_plan_revision" in sql
    assert "FORCE ROW LEVEL SECURITY" in sql
    migration = (
        PROJECT_ROOT
        / "backend/migrations/versions/20260810_044_reference_prony_calibration.py"
    ).read_text(encoding="utf-8")
    assert "JSON" not in migration
    assert '"attribute"' not in migration
    assert '"value"' not in migration

from io import StringIO
from pathlib import Path

from alembic import command
from alembic.config import Config

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_t43_ogden_calibration_is_explicit_revisioned_and_non_eav() -> None:
    output = StringIO()
    command.upgrade(
        Config(str(PROJECT_ROOT / "alembic.ini"), output_buffer=output),
        "head",
        sql=True,
    )
    sql = output.getvalue()
    for table in (
        "modeling.ogden_calibration_plan_revision",
        "modeling.ogden_calibration_plan_member",
        "modeling.ogden_calibration_run",
        "modeling.ogden_calibration_attempt",
        "modeling.ogden_calibration_candidate",
        "modeling.ogden_calibration_candidate_warning",
    ):
        assert table in sql
    assert "uniaxial_objective double precision" in sql
    assert "holdout_normalized_rmse double precision" in sql
    assert "uncertainty_status varchar(48)" in sql
    assert "FORCE ROW LEVEL SECURITY" in sql
    assert "guard_identity_head_update" in sql
    assert "reject_immutable_row_mutation" in sql
    assert "reference_planar_tension" in sql
    assert "reference_biaxial_tension" in sql
    migration = (
        PROJECT_ROOT
        / "backend/migrations/versions/20260820_054_T43_ogden_calibration.py"
    ).read_text(encoding="utf-8")
    assert "JSONB" not in migration
    assert '"attribute"' not in migration
    assert '"value"' not in migration
    assert "cannot downgrade while immutable planar or biaxial Test Methods exist" in migration

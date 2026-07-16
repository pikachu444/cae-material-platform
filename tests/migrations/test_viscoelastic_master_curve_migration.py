from io import StringIO
from pathlib import Path

from alembic import command
from alembic.config import Config

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_viscoelastic_master_migration_is_typed_scoped_immutable_and_non_eav() -> None:
    output = StringIO()
    command.upgrade(
        Config(str(PROJECT_ROOT / "alembic.ini"), output_buffer=output),
        "head",
        sql=True,
    )
    sql = output.getvalue()
    for table in (
        "datasets.viscoelastic_selection_revision",
        "datasets.viscoelastic_selection_member",
        "processing.viscoelastic_master_plan_revision",
        "processing.viscoelastic_master_run",
        "processing.viscoelastic_master_shift_factor",
        "datasets.viscoelastic_derived_dataset_revision",
    ):
        assert table in sql
    for column in (
        "temperature_k double precision",
        "log10_a_t double precision",
        "outlier_status varchar(32)",
        "reference_temperature_k double precision",
        "representation varchar(32)",
    ):
        assert column in sql
    assert "common_intersection_no_extrapolation" in sql
    assert "piecewise_linear_log_time" in sql
    assert "FORCE ROW LEVEL SECURITY" in sql
    assert "reject_immutable_row_mutation" in sql
    assert "guard_identity_head_update" in sql
    assert "guard_viscoelastic_master_run_mutation" in sql
    assert "validate_viscoelastic_selection_counts" in sql
    migration = (
        PROJECT_ROOT
        / "backend/migrations/versions/20260818_052_T42_viscoelastic_master_curve.py"
    ).read_text(encoding="utf-8")
    assert "JSONB" not in migration
    assert '"attribute"' not in migration
    assert '"value"' not in migration

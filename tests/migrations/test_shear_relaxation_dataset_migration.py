from io import StringIO
from pathlib import Path

from alembic import command
from alembic.config import Config

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_shear_relaxation_dataset_is_typed_scoped_immutable_and_non_eav() -> None:
    output = StringIO()
    command.upgrade(
        Config(str(PROJECT_ROOT / "alembic.ini"), output_buffer=output),
        "head",
        sql=True,
    )
    sql = output.getvalue()
    assert "datasets.shear_relaxation_dataset" in sql
    assert "datasets.shear_relaxation_dataset_revision" in sql
    assert "material_state_revision_id uuid" in sql
    assert "test_run_revision_id uuid" in sql
    assert "time_original_unit varchar(16)" in sql
    assert "shear_modulus_original_unit varchar(16)" in sql
    assert "FORCE ROW LEVEL SECURITY" in sql
    assert "datasets_shear_relaxation_dataset_update" in sql
    assert "reject_immutable_row_mutation" in sql
    migration = (
        PROJECT_ROOT
        / "backend/migrations/versions/20260808_042_shear_relaxation_dataset.py"
    ).read_text(encoding="utf-8")
    assert "JSON" not in migration
    assert '"attribute"' not in migration
    assert '"value"' not in migration

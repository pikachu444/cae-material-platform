from io import StringIO
from pathlib import Path

from alembic import command
from alembic.config import Config

PROJECT_ROOT = Path(__file__).parents[2]


def test_t55p_arrhenius_shift_is_explicit_typed_and_constrained() -> None:
    output = StringIO()
    command.upgrade(
        Config(str(PROJECT_ROOT / "alembic.ini"), output_buffer=output), "head", sql=True
    )
    sql = output.getvalue()
    migration = sql[sql.index("20260903_068_t55p_arrhenius") :]
    for value in (
        "arrhenius_fit",
        "arrhenius_activation_energy_j_per_mol double precision",
        "ck_processing_viscoelastic_master_run_arrhenius",
        "ck_processing_viscoelastic_master_plan_revision",
        "ck_processing_viscoelastic_master_shift_factor",
    ):
        assert value in migration
    assert "attribute_value" not in migration
    assert "value_json" not in migration

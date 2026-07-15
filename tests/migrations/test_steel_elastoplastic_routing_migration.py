from io import StringIO
from pathlib import Path

from alembic import command
from alembic.config import Config

PROJECT_ROOT = Path(__file__).parents[2]


def _configuration(output: StringIO) -> Config:
    return Config(str(PROJECT_ROOT / "alembic.ini"), output_buffer=output)


def test_plasticity_guard_pins_metal_class_to_exact_material_revision() -> None:
    output = StringIO()
    command.upgrade(_configuration(output), "head", sql=True)

    sql = " ".join(output.getvalue().split())
    assert "CREATE FUNCTION modeling.guard_metal_plasticity_source()" in sql
    assert "aggregate_id = NEW.material_id" in sql
    assert "id = NEW.material_revision_id" in sql
    assert "source_class IS DISTINCT FROM 'metal'" in sql
    assert "modeling_material_model_metal_plasticity_guard" in sql

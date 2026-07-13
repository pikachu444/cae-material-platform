from io import StringIO
from pathlib import Path

from alembic import command
from alembic.config import Config

PROJECT_ROOT = Path(__file__).parents[2]


def test_t22_renders_typed_material_model_ir_tables_lineage_constraints_and_rls() -> None:
    output = StringIO()
    configuration = Config(str(PROJECT_ROOT / "alembic.ini"), output_buffer=output)

    command.upgrade(configuration, "head", sql=True)

    sql = output.getvalue()
    required = {
        "CREATE SCHEMA modeling",
        "CREATE TABLE modeling.material_model",
        "CREATE TABLE modeling.material_model_revision",
        "fk_modeling_material_model_current_revision",
        "fk_modeling_material_model_revision_state_material_revision",
        "fk_modeling_material_model_revision_property_source",
        "uq_catalog_material_state_revision_model_source",
        "uq_catalog_property_set_revision_model_source",
        "ck_modeling_material_model_poisson_ratio",
        "ck_modeling_material_model_source_yield_stress",
        "ix_modeling_material_model_tenant_state",
        "ALTER TABLE modeling.material_model FORCE ROW LEVEL SECURITY",
        "ALTER TABLE modeling.material_model_revision FORCE ROW LEVEL SECURITY",
        "revisioning.reject_immutable_row_mutation()",
        "'modeling.read'",
        "'modeling.write'",
    }

    assert all(fragment in sql for fragment in required)
    assert "postgresql.JSONB" not in sql
    assert '"key"' not in sql
    assert '"value"' not in sql

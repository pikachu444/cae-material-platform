from io import StringIO
from pathlib import Path

from alembic import command
from alembic.config import Config

PROJECT_ROOT = Path(__file__).parents[2]


def test_t07_renders_typed_catalog_tables_constraints_indexes_and_rls() -> None:
    output = StringIO()
    configuration = Config(str(PROJECT_ROOT / "alembic.ini"), output_buffer=output)

    command.upgrade(configuration, "head", sql=True)

    sql = output.getvalue()
    for relation in (
        "catalog.material",
        "catalog.material_revision",
        "catalog.material_state",
        "catalog.material_state_revision",
        "catalog.property_set",
        "catalog.property_set_revision",
    ):
        assert f"CREATE TABLE {relation}" in sql
    for constraint in (
        "fk_catalog_material_current_revision",
        "fk_catalog_material_state_revision_material_revision",
        "fk_catalog_property_set_revision_state_revision",
        "ck_catalog_property_set_poisson_ratio",
    ):
        assert constraint in sql
    for index in (
        "ix_catalog_material_revision_tenant_name",
        "ix_catalog_material_state_tenant_material",
        "ix_catalog_property_set_tenant_state",
    ):
        assert index in sql
    assert sql.count("FORCE ROW LEVEL SECURITY") >= 6
    assert "postgresql.JSONB" not in sql

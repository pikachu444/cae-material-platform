from io import StringIO
from pathlib import Path

from alembic import command
from alembic.config import Config

PROJECT_ROOT = Path(__file__).parents[2]


def test_t25_renders_typed_solver_card_tables_constraints_indexes_and_rls() -> None:
    output = StringIO()
    configuration = Config(str(PROJECT_ROOT / "alembic.ini"), output_buffer=output)

    command.upgrade(configuration, "head", sql=True)

    sql = output.getvalue()
    required = {
        "CREATE SCHEMA exporting",
        "CREATE TABLE exporting.solver_card",
        "CREATE TABLE exporting.solver_card_revision",
        "fk_exporting_solver_card_current_revision",
        "fk_exporting_solver_card_revision_model_revision",
        "uq_exporting_solver_card_identity_target",
        "ck_exporting_solver_card_yield_map_status",
        "ck_exporting_solver_card_unit_map_status",
        "ix_exporting_solver_card_tenant_model",
        "ALTER TABLE exporting.solver_card FORCE ROW LEVEL SECURITY",
        "ALTER TABLE exporting.solver_card_revision FORCE ROW LEVEL SECURITY",
        "revisioning.reject_immutable_row_mutation()",
        "'export.read'",
        "'export.execute'",
    }

    assert all(fragment in sql for fragment in required)
    assert "postgresql.JSONB" not in sql
    assert "sa.JSON" not in sql
    assert '"key"' not in sql
    assert '"value"' not in sql

from io import StringIO
from pathlib import Path

from alembic import command
from alembic.config import Config

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_linear_viscoelastic_migration_is_typed_scoped_immutable_and_non_eav() -> None:
    output = StringIO()
    command.upgrade(
        Config(str(PROJECT_ROOT / "alembic.ini"), output_buffer=output),
        "head",
        sql=True,
    )
    sql = output.getvalue()
    assert "modeling.linear_viscoelastic_revision" in sql
    assert "modeling.linear_viscoelastic_prony_term" in sql
    assert "bulk_relaxation_status varchar(32)" in sql
    assert "g_ratio double precision" in sql
    assert "k_ratio double precision" in sql
    assert "relaxation_time_s double precision" in sql
    assert "FORCE ROW LEVEL SECURITY" in sql
    assert "reject_immutable_row_mutation" in sql
    assert "validate_linear_viscoelastic_terms" in sql
    assert "guard_linear_viscoelastic_source" in sql
    migration = (
        PROJECT_ROOT
        / "backend/migrations/versions/20260806_040_linear_viscoelastic_ir.py"
    ).read_text(encoding="utf-8")
    assert "JSON" not in migration
    assert '"attribute"' not in migration
    assert '"value"' not in migration

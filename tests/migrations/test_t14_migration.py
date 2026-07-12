from io import StringIO
from pathlib import Path

from alembic import command
from alembic.config import Config

PROJECT_ROOT = Path(__file__).parents[2]


def test_t14_migration_renders_security_invoker_typed_read_models() -> None:
    output = StringIO()
    configuration = Config(str(PROJECT_ROOT / "alembic.ini"), output_buffer=output)
    command.upgrade(configuration, "head", sql=True)
    sql = output.getvalue()

    required = {
        "CREATE VIEW provenance.dependency_edge",
        "CREATE VIEW provenance.entity_completeness",
        "CREATE VIEW provenance.activity_completeness",
        "security_invoker = true",
        "'derivation'::text AS relation",
        "'usage_generation'::text AS relation",
        "'revision'::text AS relation",
    }
    assert all(fragment in sql for fragment in required)


def test_t14_read_models_have_no_generic_edge_table_jsonb_or_business_schema() -> None:
    migration = (
        PROJECT_ROOT / "backend/migrations/versions/20260713_009_T14_lineage_read_model.py"
    ).read_text(encoding="utf-8")

    assert "op.create_table" not in migration
    assert "postgresql.JSONB" not in migration
    assert "sa.JSON" not in migration
    assert '"material"' not in migration
    assert '"dataset"' not in migration
    assert '"solver_card"' not in migration

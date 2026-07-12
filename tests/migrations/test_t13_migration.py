from io import StringIO
from pathlib import Path

from alembic import command
from alembic.config import Config

PROJECT_ROOT = Path(__file__).parents[2]


def test_t13_migration_renders_typed_relations_cycles_completeness_and_rls() -> None:
    output = StringIO()
    configuration = Config(str(PROJECT_ROOT / "alembic.ini"), output_buffer=output)
    command.upgrade(configuration, "head", sql=True)
    sql = output.getvalue()

    required = {
        "CREATE SCHEMA provenance",
        "CREATE TABLE provenance.entity",
        "CREATE TABLE provenance.activity",
        "CREATE TABLE provenance.agent",
        "CREATE TABLE provenance.usage",
        "CREATE TABLE provenance.generation",
        "CREATE TABLE provenance.derivation",
        "CREATE TABLE provenance.association",
        "CREATE TABLE provenance.revision",
        "CREATE TABLE provenance.attribution",
        "CREATE FUNCTION provenance.entity_depends_on(",
        "CREATE CONSTRAINT TRIGGER provenance_entity_completeness",
        "CREATE CONSTRAINT TRIGGER provenance_activity_completeness",
        "CREATE TRIGGER provenance_revision_insert_guard",
        "ALTER TABLE provenance.entity FORCE ROW LEVEL SECURITY",
        "ALTER TABLE provenance.generation FORCE ROW LEVEL SECURITY",
        "'provenance.read'",
        "'provenance.write'",
    }
    assert all(fragment in sql for fragment in required)


def test_t13_has_no_unrestricted_edge_jsonb_eav_or_business_schema() -> None:
    migration = (
        PROJECT_ROOT
        / "backend/migrations/versions/20260713_008_T13_typed_provenance.py"
    ).read_text(encoding="utf-8")

    assert "postgresql.JSONB" not in migration
    assert "sa.JSON" not in migration
    assert '"edge"' not in migration
    assert '"edge_type"' not in migration
    assert '"key"' not in migration
    assert '"value"' not in migration
    assert '"material"' not in migration
    assert '"test_run"' not in migration
    assert '"dataset"' not in migration
    assert '"solver_card"' not in migration

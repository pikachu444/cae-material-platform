from io import StringIO
from pathlib import Path

from alembic import command
from alembic.config import Config

PROJECT_ROOT = Path(__file__).parents[2]


def _offline_upgrade_sql() -> str:
    output = StringIO()
    configuration = Config(str(PROJECT_ROOT / "alembic.ini"), output_buffer=output)
    command.upgrade(configuration, "head", sql=True)
    return output.getvalue()


def test_t06_migration_renders_postgresql_guards_tables_rls_and_indexes() -> None:
    sql = _offline_upgrade_sql()

    required_fragments = {
        "CREATE SCHEMA revisioning",
        "CREATE SCHEMA governance",
        "CREATE FUNCTION revisioning.reject_immutable_row_mutation()",
        "CREATE FUNCTION revisioning.guard_identity_head_update()",
        "CREATE TABLE governance.lifecycle_event",
        "CREATE TABLE governance.lifecycle_projection",
        "CREATE INDEX ix_lifecycle_event_tenant_aggregate",
        "CREATE INDEX ix_lifecycle_projection_tenant_state",
        "ENABLE ROW LEVEL SECURITY",
        "FORCE ROW LEVEL SECURITY",
        "CREATE POLICY lifecycle_event_tenant_isolation",
        "CREATE POLICY lifecycle_projection_tenant_isolation",
    }
    assert all(fragment in sql for fragment in required_fragments)


def test_typed_fixture_uses_explicit_content_and_composite_tenant_constraints() -> None:
    fixture = (
        PROJECT_ROOT / "tests/migrations/fixtures/T06_typed_revision_fixture.sql"
    ).read_text(encoding="utf-8")

    assert "title varchar(200)" in fixture
    assert "body text" in fixture
    assert "pinned boolean" in fixture
    assert "JSONB" not in fixture.upper()
    assert "organization_id, project_id, aggregate_id, revision_no" in fixture
    assert "revisioning.reject_immutable_row_mutation()" in fixture
    assert "revisioning.guard_identity_head_update()" in fixture
    assert fixture.count("FORCE ROW LEVEL SECURITY") == 2

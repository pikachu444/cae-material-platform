from io import StringIO
from pathlib import Path

from alembic import command
from alembic.config import Config

PROJECT_ROOT = Path(__file__).parents[2]


def test_t04_migration_renders_explicit_role_binding_and_authorized_rls() -> None:
    output = StringIO()
    configuration = Config(str(PROJECT_ROOT / "alembic.ini"), output_buffer=output)
    command.upgrade(configuration, "head", sql=True)
    sql = output.getvalue()

    required = {
        "CREATE SCHEMA access_control",
        "CREATE TABLE identity.role_binding",
        "CONSTRAINT ck_role_binding_subject CHECK",
        "CONSTRAINT ck_role_binding_role CHECK",
        "CONSTRAINT ck_role_binding_platform_admin_subject CHECK",
        "CREATE INDEX ix_role_binding_tenant_active",
        "CREATE UNIQUE INDEX uq_role_binding_principal_grant",
        "CREATE FUNCTION access_control.assert_application_role()",
        "CREATE FUNCTION access_control.can_access_row(",
        "CREATE TRIGGER role_binding_guard",
        "ALTER TABLE identity.role_binding FORCE ROW LEVEL SECURITY",
        "CREATE POLICY role_binding_own_select",
        "CREATE POLICY lifecycle_event_authorized_select",
        "CREATE POLICY lifecycle_projection_authorized_update",
    }
    assert all(fragment in sql for fragment in required)

    migration = (
        PROJECT_ROOT
        / "backend/migrations/versions/20260711_003_T04_authorization_rls.py"
    ).read_text(encoding="utf-8")
    assert "postgresql.JSONB" not in migration
    assert "sa.JSON" not in migration
    assert '"material"' not in migration
    assert '"artifact"' not in migration
    assert "CREATE ROLE" not in sql

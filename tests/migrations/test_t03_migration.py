from io import StringIO
from pathlib import Path

from alembic import command
from alembic.config import Config

PROJECT_ROOT = Path(__file__).parents[2]


def test_t03_migration_renders_explicit_identity_tables_guards_and_indexes() -> None:
    output = StringIO()
    configuration = Config(str(PROJECT_ROOT / "alembic.ini"), output_buffer=output)
    command.upgrade(configuration, "head", sql=True)
    sql = output.getvalue()

    required = {
        "CREATE SCHEMA identity",
        "CREATE TABLE identity.principal",
        "CREATE TABLE identity.external_identity",
        "CONSTRAINT ck_principal_nonzero_id CHECK",
        "CONSTRAINT ck_external_identity_nonzero_id CHECK",
        "CONSTRAINT uq_external_identity_issuer_subject UNIQUE (issuer, subject)",
        "CREATE INDEX ix_principal_type_active",
        "CREATE INDEX ix_external_identity_principal",
        "CREATE FUNCTION identity.guard_principal_update()",
        "CREATE FUNCTION identity.guard_external_identity_update()",
        "CREATE TRIGGER principal_guard",
        "CREATE TRIGGER external_identity_guard",
    }
    assert all(fragment in sql for fragment in required)

    migration_source = (
        PROJECT_ROOT
        / "backend/migrations/versions/20260711_002_T03_identity_principal.py"
    ).read_text(encoding="utf-8")
    assert "sa.JSON" not in migration_source
    assert "postgresql.JSONB" not in migration_source

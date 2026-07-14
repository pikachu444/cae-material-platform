from io import StringIO
from pathlib import Path

from alembic import command
from alembic.config import Config

PROJECT_ROOT = Path(__file__).parents[2]


def test_t29_migration_renders_explicit_review_relations_guards_and_rls() -> None:
    output = StringIO()
    configuration = Config(str(PROJECT_ROOT / "alembic.ini"), output_buffer=output)

    command.upgrade(configuration, "head", sql=True)

    sql = output.getvalue()
    required = {
        "CREATE TABLE governance.review_request",
        "CREATE TABLE governance.review_decision",
        "CREATE INDEX ix_review_request_tenant_state_lookup",
        "CREATE INDEX ix_review_request_target_lookup",
        "CREATE INDEX ix_review_decision_tenant_request",
        "fk_review_request_lifecycle_projection",
        "fk_review_decision_exact_manifest",
        "uq_review_decision_request",
        "review_request_immutable",
        "review_decision_immutable",
        "CREATE POLICY review_request_authorized_select",
        "CREATE POLICY review_request_authorized_insert",
        "CREATE POLICY review_decision_authorized_select",
        "CREATE POLICY review_decision_authorized_insert",
        "ALTER TABLE governance.review_request FORCE ROW LEVEL SECURITY",
        "ALTER TABLE governance.review_decision FORCE ROW LEVEL SECURITY",
        "required_role = 'domain_reviewer'",
        "decision IN ('approved', 'changes_requested')",
        "manifest_sha256 ~ '^[0-9a-f]{64}$'",
    }
    assert all(fragment in sql for fragment in required)


def test_t29_migration_does_not_add_generic_business_payloads() -> None:
    migration = (
        PROJECT_ROOT / "backend/migrations/versions/20260723_025_T29_review_lifecycle.py"
    ).read_text(encoding="utf-8")
    assert "postgresql.JSONB" not in migration
    assert 'sa.Column("content"' not in migration
    assert 'sa.Column("key"' not in migration
    assert 'sa.Column("value"' not in migration


from io import StringIO
from pathlib import Path

from alembic import command
from alembic.config import Config

PROJECT_ROOT = Path(__file__).parents[2]


def test_t30_migration_renders_explicit_release_package_relations_and_rls() -> None:
    output = StringIO()
    configuration = Config(str(PROJECT_ROOT / "alembic.ini"), output_buffer=output)

    command.upgrade(configuration, "head", sql=True)

    sql = output.getvalue()
    required = {
        "CREATE TABLE governance.release",
        "CREATE TABLE governance.release_manifest",
        "CREATE TABLE governance.release_artifact",
        "CREATE INDEX ix_governance_release_tenant_created",
        "CREATE INDEX ix_governance_release_manifest_review",
        "fk_governance_release_manifest_model_revision",
        "fk_governance_release_manifest_card_revision",
        "fk_governance_release_manifest_validation_result",
        "fk_governance_release_manifest_review_request",
        "release_immutable",
        "release_manifest_immutable",
        "release_artifact_immutable",
        "CREATE POLICY release_authorized_select",
        "CREATE POLICY release_manifest_authorized_insert",
        "ALTER TABLE governance.release FORCE ROW LEVEL SECURITY",
        "ALTER TABLE governance.release_artifact FORCE ROW LEVEL SECURITY",
        "package_media_type = 'application/vnd.cmp.release-manifest+json'",
        "state = 'released'",
        "channel = 'reference'",
    }
    assert all(fragment in sql for fragment in required)


def test_t30_migration_does_not_add_generic_eav_or_mutable_package_payloads() -> None:
    migration = (
        PROJECT_ROOT / "backend/migrations/versions/20260724_026_T30_release_completeness.py"
    ).read_text(encoding="utf-8")
    assert "postgresql.JSONB" not in migration
    assert 'sa.Column("key"' not in migration
    assert 'sa.Column("value"' not in migration
    assert 'sa.Column("content", postgresql.JSONB' not in migration
    assert "reject_immutable_row_mutation" in migration

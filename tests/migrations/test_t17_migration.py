from io import StringIO
from pathlib import Path

from alembic import command
from alembic.config import Config

PROJECT_ROOT = Path(__file__).parents[2]


def test_t17_migration_renders_explicit_registry_state_activation_and_rls() -> None:
    output = StringIO()
    configuration = Config(str(PROJECT_ROOT / "alembic.ini"), output_buffer=output)
    command.upgrade(configuration, "head", sql=True)
    sql = output.getvalue()

    required = {
        "CREATE SCHEMA plugin",
        "CREATE TABLE plugin.definition",
        "CREATE TABLE plugin.package",
        "CREATE TABLE plugin.extension",
        "CREATE TABLE plugin.capability",
        "CREATE TABLE plugin.schema",
        "CREATE TABLE plugin.artifact_role",
        "CREATE TABLE plugin.package_state_event",
        "CREATE TABLE plugin.package_state_projection",
        "CREATE TABLE plugin.activation",
        "CONSTRAINT uq_plugin_package_definition_version",
        "CONSTRAINT uq_plugin_package_digest",
        "CREATE FUNCTION plugin.require_matching_definition()",
        "CREATE FUNCTION plugin.require_initial_package_projection()",
        "CREATE FUNCTION plugin.require_unsealed_package()",
        "CREATE FUNCTION plugin.guard_package_state_event_insert()",
        "CREATE FUNCTION plugin.require_state_event_projection()",
        "CREATE FUNCTION plugin.guard_package_state_projection()",
        "CREATE FUNCTION plugin.require_eligible_activation()",
        "CREATE TRIGGER activation_eligibility_guard",
        "CREATE CONSTRAINT TRIGGER package_state_event_projected",
        "CREATE CONSTRAINT TRIGGER package_initial_projection",
        "ALTER TABLE plugin.package FORCE ROW LEVEL SECURITY",
        "CREATE POLICY package_authorized_insert",
        "CREATE POLICY activation_authorized_insert",
    }
    assert all(fragment in sql for fragment in required)


def test_t17_uses_jsonb_only_for_named_versioned_contract_documents() -> None:
    migration = (
        PROJECT_ROOT
        / "backend/migrations/versions/20260711_005_T17_plugin_registry.py"
    ).read_text(encoding="utf-8")

    assert migration.count("postgresql.JSONB") == 2
    assert 'sa.Column("manifest", postgresql.JSONB' in migration
    assert 'sa.Column("document", postgresql.JSONB' in migration
    assert '"attribute"' not in migration
    assert '"entity_type"' not in migration
    assert '"material"' not in migration
    assert '"test_run"' not in migration
    assert '"solver_card"' not in migration

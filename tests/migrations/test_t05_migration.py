from io import StringIO
from pathlib import Path

from alembic import command
from alembic.config import Config

PROJECT_ROOT = Path(__file__).parents[2]


def test_t05_migration_renders_explicit_append_only_audit_chain() -> None:
    output = StringIO()
    configuration = Config(str(PROJECT_ROOT / "alembic.ini"), output_buffer=output)
    command.upgrade(configuration, "head", sql=True)
    sql = output.getvalue()

    required = {
        "CREATE TABLE audit.event",
        "CREATE TABLE audit.segment_root",
        "uq_audit_event_tenant_sequence",
        "uq_audit_segment_tenant_sequence",
        "audit.compute_event_hash",
        "audit.compute_segment_root_hash",
        "audit_event_immutable",
        "audit_segment_root_immutable",
        "ENABLE ROW LEVEL SECURITY",
        "FORCE ROW LEVEL SECURITY",
        "'audit.append'",
        "'audit.read'",
        "'audit.seal'",
    }
    assert all(fragment in sql for fragment in required)


def test_t05_has_no_generic_payload_eav_or_domain_specific_schema() -> None:
    migration = (
        PROJECT_ROOT / "backend/migrations/versions/20260713_012_T05_append_only_audit.py"
    ).read_text(encoding="utf-8")

    assert "postgresql.JSONB" not in migration
    assert 'sa.Column("payload"' not in migration
    assert 'sa.Column("attribute"' not in migration
    assert 'sa.Column("value"' not in migration
    assert '"material"' not in migration
    assert '"solver"' not in migration

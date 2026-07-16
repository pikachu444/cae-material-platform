from __future__ import annotations

from pathlib import Path

MIGRATION = (
    Path(__file__).parents[2]
    / "backend/migrations/versions/20260824_058_T47_bulk_export_job_leases.py"
)


def test_t47_lease_migration_adds_expiry_index_and_fencing_guard() -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    for fragment in (
        "ADD COLUMN lease_token uuid",
        "ADD COLUMN lease_expires_at timestamptz",
        "ADD COLUMN heartbeat_at timestamptz",
        "ck_exporting_bulk_export_job_lease",
        "ix_exporting_bulk_export_job_expired_lease",
        "is_heartbeat",
        "is_reclaim",
        "OLD.lease_expires_at > NEW.heartbeat_at",
        "OLD.lease_expires_at <= NEW.heartbeat_at",
        "NEW.lease_token IS DISTINCT FROM OLD.lease_token",
        "20260824-058-bootstrap",
        "state IN ('running','reconciling') AND lease_token IS NULL",
    ):
        assert fragment in source
    assert "jsonb" not in source.lower()
    assert "attribute_key" not in source.lower()


def test_t47_lease_migration_keeps_inline_and_terminal_jobs_unleased() -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    assert "lease_token IS NULL AND lease_expires_at IS NULL AND heartbeat_at IS NULL" in source
    assert "state IN ('running','reconciling')" in source
    assert "state='succeeded'" in source and "lease_token IS NULL" in source
    assert "cannot downgrade with active leased Bulk Export Jobs" in source
    assert "DROP COLUMN lease_token" in source

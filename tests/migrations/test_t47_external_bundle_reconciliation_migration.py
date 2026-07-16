from __future__ import annotations

from pathlib import Path

MIGRATION = (
    Path(__file__).parents[2]
    / "backend/migrations/versions/20260823_057_T47_external_bundle_reconciliation.py"
)


def test_t47_migration_adds_typed_committed_output_and_visible_reconciliation() -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    for fragment in (
        "CREATE TABLE exporting.bulk_export_output_commit",
        "archive_artifact_id uuid NOT NULL",
        "archive_sha256 char(64) NOT NULL",
        "manifest_sha256 char(64) NOT NULL",
        "reconciliation_required",
        "reconciling",
        "committed_output_pending",
        "bulk_export_output_commit_immutable",
        "FORCE ROW LEVEL SECURITY",
        "export.read",
        "export.execute",
    ):
        assert fragment in source
    assert "jsonb" not in source.lower()
    assert "attribute_key" not in source.lower()


def test_t47_migration_allows_only_fenced_output_reconciliation_transitions() -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    assert "OLD.state='running' AND NEW.state IN" in source
    assert "OLD.state='reconciliation_required' AND NEW.state='reconciling'" in source
    assert "OLD.state='reconciling' AND NEW.state IN" in source
    assert "NEW.attempt_count=OLD.attempt_count+1" in source
    assert "cannot downgrade with committed Bundle output evidence" in source

from pathlib import Path

PROJECT_ROOT = Path(__file__).parents[2]
MIGRATION = (
    PROJECT_ROOT / "backend/migrations/versions/20260928_097_issue207_schema_bundle_apply_export.py"
)


def test_issue207_adds_normalized_immutable_bundle_application_authority() -> None:
    source = MIGRATION.read_text(encoding="utf-8")

    assert 'revision: str = "20260928_097_issue207_bundle"' in source
    assert 'down_revision: str | None = "20260927_096_issue206_curve"' in source
    for table in (
        "schema_definition_bundle",
        "schema_definition_bundle_version",
        "schema_definition_bundle_application",
        "schema_definition_bundle_binding",
    ):
        assert f'"{table}"' in source
    assert "CREATE POLICY catalog_{table}_read" in source
    assert "CREATE POLICY catalog_{table}_apply_insert" in source
    assert "catalog.schema.apply" in source
    assert "first_source_artifact_id" in source
    assert "first_source_artifact_sha256" in source
    assert "plan_fingerprint" in source
    assert "before_snapshot_fingerprint" in source
    assert "after_snapshot_fingerprint" in source
    assert "idempotency_key" in source
    assert "delete_missing = false" in source
    assert "profile_table_placement" in source
    assert "reject_immutable_row_mutation" in source
    assert "deferrable=True" in source
    assert 'ondelete="RESTRICT"' in source


def test_issue207_downgrade_refuses_to_discard_immutable_apply_evidence() -> None:
    source = MIGRATION.read_text(encoding="utf-8")

    assert "Issue #207 downgrade refused" in source
    assert "schema_definition_bundle_application" in source[source.index("def downgrade") :]

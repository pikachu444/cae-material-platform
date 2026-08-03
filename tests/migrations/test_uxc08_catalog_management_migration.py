from pathlib import Path

PROJECT_ROOT = Path(__file__).parents[2]
MIGRATION = PROJECT_ROOT / "backend/migrations/versions/20260923_092_uxc08_catalog_management.py"


def test_uxc08_adds_append_only_publication_boundary_and_catalog_identities() -> None:
    source = MIGRATION.read_text(encoding="utf-8")

    assert 'revision: str = "20260923_092_uxc08"' in source
    assert 'down_revision: str | None = "20260922_091_uxc07_evidence"' in source
    assert '"publication_marker"' in source
    assert '"database"' in source
    assert '"profile"' in source
    assert "fk_catalog_profile_revision_database" in source
    assert "uq_catalog_publication_marker_revision" in source
    # Existing reader-visible heads are explicitly marked so the new boundary
    # does not make a migrated catalog disappear from Materials.
    assert "Existing reader-visible heads remain searchable" in source
    assert "catalog.configurable_record" in source
    assert "catalog.folder" in source
    assert "ENABLE ROW LEVEL SECURITY" in source
    assert "guard_identity_head_update" in source
    assert "reject_immutable_row_mutation" in source
    assert "encode(sha256(convert_to(" in source
    assert "guard_catalog_record_external_key" in source
    assert "'materials_catalog'" in source
    assert "'materials-catalog'" not in source


def test_uxc08_keeps_table_profile_placement_and_registration_previews_outside_revisions() -> None:
    source = MIGRATION.read_text(encoding="utf-8")

    assert '"table_profile_placement"' in source
    assert '"record_registration_preview"' in source
    assert "fk_catalog_table_profile_placement_table" in source
    assert "fk_catalog_table_profile_placement_profile" in source
    assert "uq_catalog_registration_preview_token" in source
    assert "source_artifact_id" in source
    assert "source_digest" in source
    assert "Materials catalog" in source
    assert "Compatibility catalog hierarchy" in source

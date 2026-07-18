from pathlib import Path


def test_t53_mapping_profile_migration_has_typed_exact_revision_storage() -> None:
    path = Path(
        "backend/migrations/versions/20260829_063_T53_mapping_profiles.py"
    )
    value = path.read_text(encoding="utf-8")
    assert 'down_revision: str | None = "20260828_062_test_json"' in value
    for table in (
        "processing.mapping_profile",
        "processing.mapping_profile_revision",
        "processing.mapping_profile_channel_binding",
        "processing.mapping_profile_attribute_binding",
    ):
        assert table in value
    assert "attribute_definition_revision_id" in value
    assert "fk_processing_mapping_profile_attribute_exact_revision" in value
    assert "guard_identity_head_update" in value
    assert "for table in _TABLES[1:]" in value
    assert "reject_immutable_row_mutation" in value
    assert "FORCE ROW LEVEL SECURITY" in value
    assert "jsonb" not in value.lower()

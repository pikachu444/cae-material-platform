from pathlib import Path

PROJECT_ROOT = Path(__file__).parents[2]


def test_implemented_tasks_are_the_only_database_migrations() -> None:
    migrations = sorted((PROJECT_ROOT / "backend/migrations/versions").glob("*.py"))

    assert [path.name for path in migrations] == [
        "20260711_001_T06_revision_kernel.py",
        "20260711_002_T03_identity_principal.py",
        "20260711_003_T04_authorization_rls.py",
        "20260711_004_T15_job_engine.py",
        "20260711_005_T17_plugin_registry.py",
        "20260712_006_T09_streaming_upload.py",
        "20260712_007_T10_content_artifacts.py",
        "20260713_008_T13_typed_provenance.py",
        "20260713_009_T14_lineage_read_model.py",
        "20260713_010_T16_transactional_outbox.py",
        "20260713_011_T16_reconciliation_schedule.py",
        "20260713_012_T05_append_only_audit.py",
        "20260713_013_T07_material_catalog.py",
        "20260714_014_T22_reference_material_model.py",
        "20260714_015_T25_reference_openradioss_export.py",
        "20260714_016_T08_T12_reference_tensile_dataset.py",
    ]


def test_t06_migration_does_not_introduce_domain_or_generic_content_tables() -> None:
    migration = (
        PROJECT_ROOT
        / "backend/migrations/versions/20260711_001_T06_revision_kernel.py"
    ).read_text(encoding="utf-8")
    forbidden_table_names = (
        '"material"',
        '"test_run"',
        '"dataset"',
        '"solver_card"',
        '"aggregate_revision"',
        '"generic_revision"',
    )

    assert all(name not in migration for name in forbidden_table_names)
    assert '"content", postgresql.JSONB' not in migration


def test_t03_migration_stops_before_roles_and_business_resources() -> None:
    migration = (
        PROJECT_ROOT
        / "backend/migrations/versions/20260711_002_T03_identity_principal.py"
    ).read_text(encoding="utf-8")

    assert '"role_binding"' not in migration
    assert '"material"' not in migration
    assert '"test_run"' not in migration
    assert '"solver_card"' not in migration
    assert "sa.JSON" not in migration
    assert "postgresql.JSONB" not in migration


def test_t04_migration_adds_access_control_without_business_tables() -> None:
    migration = (
        PROJECT_ROOT
        / "backend/migrations/versions/20260711_003_T04_authorization_rls.py"
    ).read_text(encoding="utf-8")

    assert '"role_binding"' in migration
    assert '"material"' not in migration
    assert '"test_run"' not in migration
    assert '"artifact"' not in migration
    assert '"solver_card"' not in migration
    assert "sa.JSON" not in migration
    assert "postgresql.JSONB" not in migration


def test_t15_job_spec_jsonb_is_not_a_generic_eav_or_business_payload() -> None:
    migration = (
        PROJECT_ROOT
        / "backend/migrations/versions/20260711_004_T15_job_engine.py"
    ).read_text(encoding="utf-8")

    assert migration.count("postgresql.JSONB") == 1
    assert 'sa.Column("job_spec", postgresql.JSONB' in migration
    assert '"key"' not in migration
    assert '"value"' not in migration
    assert '"material"' not in migration
    assert '"test_run"' not in migration
    assert '"solver_card"' not in migration


def test_t17_jsonb_is_limited_to_versioned_manifest_and_schema_contracts() -> None:
    migration = (
        PROJECT_ROOT
        / "backend/migrations/versions/20260711_005_T17_plugin_registry.py"
    ).read_text(encoding="utf-8")

    assert migration.count("postgresql.JSONB") == 2
    assert 'sa.Column("manifest", postgresql.JSONB' in migration
    assert 'sa.Column("document", postgresql.JSONB' in migration
    assert '"key"' not in migration
    assert '"value"' not in migration
    assert '"material"' not in migration
    assert '"test_run"' not in migration
    assert '"solver_card"' not in migration


def test_t09_uses_explicit_upload_raw_and_ingestion_relations_without_jsonb() -> None:
    migration = (
        PROJECT_ROOT
        / "backend/migrations/versions/20260712_006_T09_streaming_upload.py"
    ).read_text(encoding="utf-8")

    assert '"upload_session"' in migration
    assert '"upload_part"' in migration
    assert '"raw_asset"' in migration
    assert '"ingestion_event"' in migration
    assert "postgresql.JSONB" not in migration
    assert '"material"' not in migration
    assert '"dataset"' not in migration
    assert '"solver_card"' not in migration


def test_t10_uses_explicit_manifest_integrity_relations_without_eav_json() -> None:
    migration = (
        PROJECT_ROOT
        / "backend/migrations/versions/20260712_007_T10_content_artifacts.py"
    ).read_text(encoding="utf-8")

    assert '"artifact_pending"' in migration
    assert '"artifact"' in migration
    assert '"integrity_observation"' in migration
    assert '"integrity_projection"' in migration
    assert '"reconciliation_issue"' in migration
    assert "postgresql.JSONB" not in migration
    assert "sa.JSON" not in migration
    assert '"key"' not in migration
    assert '"value"' not in migration
    assert '"material"' not in migration
    assert '"dataset"' not in migration
    assert '"solver_card"' not in migration


def test_t13_uses_typed_provenance_relations_without_generic_edges_or_jsonb() -> None:
    migration = (
        PROJECT_ROOT
        / "backend/migrations/versions/20260713_008_T13_typed_provenance.py"
    ).read_text(encoding="utf-8")

    for table in (
        "entity",
        "activity",
        "agent",
        "usage",
        "generation",
        "derivation",
        "association",
        "revision",
        "attribution",
    ):
        assert f'"{table}"' in migration
    assert "postgresql.JSONB" not in migration
    assert "sa.JSON" not in migration
    assert '"edge"' not in migration
    assert '"edge_type"' not in migration
    assert '"key"' not in migration
    assert '"value"' not in migration
    assert '"material"' not in migration
    assert '"dataset"' not in migration
    assert '"solver_card"' not in migration


def test_t14_adds_security_invoker_read_models_without_new_domain_tables() -> None:
    migration = (
        PROJECT_ROOT
        / "backend/migrations/versions/20260713_009_T14_lineage_read_model.py"
    ).read_text(encoding="utf-8")

    assert "security_invoker = true" in migration
    assert "provenance.dependency_edge" in migration
    assert "provenance.entity_completeness" in migration
    assert "provenance.activity_completeness" in migration
    assert "op.create_table" not in migration
    assert "postgresql.JSONB" not in migration
    assert '"material"' not in migration
    assert '"dataset"' not in migration
    assert '"solver_card"' not in migration


def test_t07_uses_explicit_catalog_revisions_and_typed_property_columns_without_eav() -> None:
    migration = (
        PROJECT_ROOT
        / "backend/migrations/versions/20260713_013_T07_material_catalog.py"
    ).read_text(encoding="utf-8")

    for table in (
        "material",
        "material_revision",
        "material_state",
        "material_state_revision",
        "property_set",
        "property_set_revision",
    ):
        assert f'"{table}"' in migration
    for column in (
        '"density_kg_per_m3"',
        '"youngs_modulus_pa"',
        '"poisson_ratio"',
        '"yield_stress_pa"',
        '"applicable_temperature_min_k"',
    ):
        assert column in migration
    assert "postgresql.JSONB" not in migration
    assert "sa.JSON" not in migration
    assert '"key"' not in migration
    assert '"value"' not in migration
    assert "for table in (identity, revision_table):" in migration
    assert "FORCE ROW LEVEL SECURITY" in migration
    assert "revisioning.reject_immutable_row_mutation()" in migration
    assert "revisioning.guard_identity_head_update()" in migration


def test_t22_uses_typed_reference_model_revisions_without_generic_model_payload() -> None:
    migration = (
        PROJECT_ROOT
        / "backend/migrations/versions/20260714_014_T22_reference_material_model.py"
    ).read_text(encoding="utf-8")

    for table in ("material_model", "material_model_revision"):
        assert f'"{table}"' in migration
    for column in (
        '"density_kg_per_m3"',
        '"youngs_modulus_pa"',
        '"poisson_ratio"',
        '"source_yield_stress_pa"',
        '"property_set_revision_id"',
    ):
        assert column in migration
    assert "postgresql.JSONB" not in migration
    assert "sa.JSON" not in migration
    assert '"key"' not in migration
    assert '"value"' not in migration
    assert "FORCE ROW LEVEL SECURITY" in migration
    assert "revisioning.reject_immutable_row_mutation()" in migration


def test_t25_uses_typed_solver_card_revisions_without_generic_card_payload() -> None:
    migration = (
        PROJECT_ROOT
        / "backend/migrations/versions/20260714_015_T25_reference_openradioss_export.py"
    ).read_text(encoding="utf-8")

    for table in ("solver_card", "solver_card_revision"):
        assert f'"{table}"' in migration
    for column in (
        '"material_model_revision_id"',
        '"density_kg_per_m3"',
        '"youngs_modulus_pa"',
        '"poisson_ratio"',
        '"mapping_report_sha256"',
        '"card_sha256"',
        '"card_text"',
    ):
        assert column in migration
    assert "postgresql.JSONB" not in migration
    assert "sa.JSON" not in migration
    assert '"key"' not in migration
    assert '"value"' not in migration
    assert "FORCE ROW LEVEL SECURITY" in migration
    assert "revisioning.reject_immutable_row_mutation()" in migration


def test_t08_t12_use_explicit_test_dataset_revisions_and_artifact_references_without_eav() -> None:
    migration = (
        PROJECT_ROOT
        / "backend/migrations/versions/20260714_016_T08_T12_reference_tensile_dataset.py"
    ).read_text(encoding="utf-8")

    for table in (
        "specimen",
        "specimen_revision",
        "test_method",
        "test_method_revision",
        "test_run",
        "test_run_revision",
        "dataset",
        "dataset_revision",
    ):
        assert f'"{table}"' in migration
    for column in (
        '"material_state_revision_id"',
        '"test_run_revision_id"',
        '"raw_artifact_id"',
        '"data_artifact_id"',
        '"strain_original_unit"',
        '"stress_original_unit"',
        '"mapping_sha256"',
    ):
        assert column in migration
    assert "postgresql.JSONB" not in migration
    assert "sa.JSON" not in migration
    assert '"key"' not in migration
    assert '"value"' not in migration
    assert "FORCE ROW LEVEL SECURITY" in migration
    assert "revisioning.reject_immutable_row_mutation()" in migration


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


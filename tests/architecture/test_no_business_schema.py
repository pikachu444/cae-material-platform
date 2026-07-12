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


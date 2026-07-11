from pathlib import Path

PROJECT_ROOT = Path(__file__).parents[2]


def test_implemented_tasks_are_the_only_database_migrations() -> None:
    migrations = sorted((PROJECT_ROOT / "backend/migrations/versions").glob("*.py"))

    assert [path.name for path in migrations] == [
        "20260711_001_T06_revision_kernel.py",
        "20260711_002_T03_identity_principal.py",
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


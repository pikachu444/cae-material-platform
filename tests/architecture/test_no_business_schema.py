from pathlib import Path

PROJECT_ROOT = Path(__file__).parents[2]


def test_foundation_has_no_database_migration_code() -> None:
    migrations = list((PROJECT_ROOT / "backend/migrations").glob("*.py"))

    assert migrations == []


from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).parents[2]
MIGRATION = (
    ROOT
    / "backend/migrations/versions/20261003_102_issue246_task2_common_units.py"
)


def test_task2_unit_migration_is_additive_and_follows_current_head() -> None:
    source = MIGRATION.read_text(encoding="utf-8")

    assert 'revision: str = "20261003_102_issue246_units"' in source
    assert 'down_revision: str | None = "20261002_101_issue289_delete"' in source
    assert "'speed'" in source
    assert "'m/s','mm/s','mm/min'" in source
    assert "'kg/m3','g/cm3','tonne/mm3'" in source
    assert "(dimension = 'speed' AND unit_id = 'm/s')" in source
    assert "DELETE FROM" not in source.upper()
    assert "UPDATE " not in source.upper()

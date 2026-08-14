from io import StringIO
from pathlib import Path

from alembic import command
from alembic.config import Config

ROOT = Path(__file__).parents[2]
MIGRATION = ROOT / "backend/migrations/versions/20261001_100_issue246_source_v2.py"


def test_issue246_migration_follows_issue209_and_adds_bounded_projection_fields() -> None:
    source = MIGRATION.read_text(encoding="utf-8")

    assert 'revision: str = "20261001_100_issue246_source_v2"' in source
    assert 'down_revision: str | None = "20260930_099_issue209_dma_fld"' in source
    assert "ADD COLUMN data_category varchar(32)" in source
    assert "'technical_data', 'test_data', 'simulation_data'" in source
    assert "ADD COLUMN business_key boolean NOT NULL DEFAULT false" in source
    assert "data_type IN ('text', 'discrete')" in source
    assert "jsonb" not in source.casefold()


def test_issue246_fields_are_present_in_head_sql() -> None:
    output = StringIO()
    configuration = Config(str(ROOT / "alembic.ini"), output_buffer=output)

    command.upgrade(configuration, "head", sql=True)

    sql = output.getvalue()
    assert "ALTER TABLE catalog.schema_table_revision" in sql
    assert "ADD COLUMN data_category varchar(32)" in sql
    assert "ALTER TABLE catalog.attribute_definition_revision" in sql
    assert "ADD COLUMN business_key boolean" in sql

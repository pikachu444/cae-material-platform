from io import StringIO
from pathlib import Path

from alembic import command
from alembic.config import Config

PROJECT_ROOT = Path(__file__).parents[2]


def test_t11_migration_renders_reference_import_contract_constants() -> None:
    output = StringIO()
    configuration = Config(
        str(PROJECT_ROOT / "alembic.ini"),
        output_buffer=output,
    )

    command.upgrade(configuration, "head", sql=True)

    sql = output.getvalue()
    assert "CREATE TABLE testing.import_mapping_revision" in sql
    assert "{_ZERO}" not in sql
    assert "{_MAPPING_SCHEMA}" not in sql
    assert "{_IMPORTER_ID}" not in sql
    assert "{_IMPORTER_VERSION}" not in sql
    assert "urn:cmp:testing:reference-import-mapping:1.0.0" in sql
    assert "urn:cmp:testing:synthetic-csv-header-importer:1.0.0" in sql

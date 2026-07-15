from io import StringIO
from pathlib import Path

from alembic import command
from alembic.config import Config

PROJECT_ROOT = Path(__file__).parents[2]


def _configuration(output: StringIO) -> Config:
    return Config(str(PROJECT_ROOT / "alembic.ini"), output_buffer=output)


def test_material_classification_adds_typed_v2_constraint_and_scope_index() -> None:
    output = StringIO()
    command.upgrade(_configuration(output), "head", sql=True)

    sql = " ".join(output.getvalue().split())
    assert "ALTER TABLE catalog.material_revision ADD COLUMN material_class VARCHAR(32)" in sql
    assert "ck_catalog_material_revision_schema_class" in sql
    assert "schema_version = '2.0.0'" in sql
    for material_class in (
        "unclassified",
        "metal",
        "polymer",
        "elastomer",
        "composite",
        "ceramic",
        "other",
    ):
        assert f"'{material_class}'" in sql
    assert "ix_catalog_material_revision_class" in sql


def test_material_classification_downgrade_refuses_to_erase_v2_semantics() -> None:
    output = StringIO()
    command.downgrade(
        _configuration(output),
        "20260804_038_catalog:20260803_037_p1",
        sql=True,
    )

    sql = output.getvalue()
    refusal = "cannot downgrade Material classification while immutable schema v2 revisions exist"
    assert refusal in sql
    assert sql.index(refusal) < sql.index("DROP COLUMN material_class")

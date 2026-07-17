from io import StringIO
from pathlib import Path

from alembic import command
from alembic.config import Config

PROJECT_ROOT = Path(__file__).parents[2]


def test_t49_renders_configurable_schema_and_typed_value_relations() -> None:
    output = StringIO()
    configuration = Config(str(PROJECT_ROOT / "alembic.ini"), output_buffer=output)

    command.upgrade(configuration, "head", sql=True)

    sql = output.getvalue()
    for relation in (
        "catalog.schema_table",
        "catalog.schema_table_revision",
        "catalog.attribute_definition",
        "catalog.attribute_definition_revision",
        "catalog.layout",
        "catalog.layout_revision",
        "catalog.layout_item",
        "catalog.subset",
        "catalog.subset_revision",
        "catalog.catalog_record",
        "catalog.catalog_record_revision",
        "catalog.record_number_value",
        "catalog.record_integer_value",
        "catalog.record_text_value",
        "catalog.record_boolean_value",
        "catalog.record_date_value",
        "catalog.record_discrete_value",
        "catalog.record_file_value",
        "catalog.record_curve_value",
        "catalog.record_reference_value",
    ):
        assert f"CREATE TABLE {relation}" in sql
    for constraint in (
        "uq_catalog_schema_table_tenant_key",
        "uq_catalog_attribute_definition_table_key",
        "fk_catalog_attribute_revision_table_revision",
        "fk_catalog_attribute_revision_reference_table",
        "fk_catalog_layout_item_attribute_revision",
        "fk_catalog_record_reference_value_target_revision",
        "ck_catalog_record_number_value_semantics",
    ):
        assert constraint in sql
    for index in (
        "ix_catalog_attribute_definition_table",
        "ix_catalog_record_number_search",
        "ix_catalog_record_text_search",
    ):
        assert index in sql
    assert "guard_typed_record_value" in sql
    assert "number value metadata must match Attribute revision" in sql
    assert "discrete value is not allowed by Attribute revision" in sql
    assert sql.count("FORCE ROW LEVEL SECURITY") >= 20
    assert "record_attribute_value" not in sql
    assert "value_json" not in sql

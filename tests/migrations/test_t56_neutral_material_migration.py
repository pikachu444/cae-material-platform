from io import StringIO
from pathlib import Path

from alembic.config import Config

PROJECT_ROOT = Path(__file__).parents[2]


def _migration_sql() -> str:
    output = StringIO()
    config = Config(str(PROJECT_ROOT / "alembic.ini"), output_buffer=output)
    from alembic import command

    command.upgrade(config, "head", sql=True)
    sql = output.getvalue()
    start = sql.index("20260906_071_t56_neutral")
    end = sql.index("20260907_072_t57_cards", start)
    return sql[start:end]


def test_t56_uses_typed_projection_and_exact_revision_foreign_keys() -> None:
    migration = _migration_sql()

    assert "CREATE TABLE modeling.neutral_material_revision" in migration
    assert "CREATE TABLE modeling.neutral_material_source_dataset" in migration
    assert "family='neo_hookean'" in migration
    assert "family='mooney_rivlin'" in migration
    assert "family='yeoh'" in migration
    assert "family='ogden_1'" in migration
    assert "family_candidate_id uuid NOT NULL" in migration
    assert "document_artifact_id uuid NOT NULL" in migration
    assert "mapping_profile_status='not_applicable'" in migration
    assert "processing_recipe_status='not_applicable'" in migration
    assert "REFERENCES catalog.material_revision" in migration
    assert "REFERENCES catalog.material_state_revision" in migration
    assert "REFERENCES catalog.property_set_revision" in migration
    assert "REFERENCES datasets.governed_dataset_revision" in migration
    assert "modeling.hyperelastic_family_candidate" in migration
    assert "jsonb" not in migration.lower()
    assert "value_json" not in migration.lower()


def test_t56_identity_and_evidence_rows_are_append_only_and_tenant_scoped() -> None:
    migration = _migration_sql()

    assert "revisioning.guard_identity_head_update()" in migration
    assert migration.count("revisioning.reject_immutable_row_mutation()") >= 2
    assert "ENABLE ROW LEVEL SECURITY" in migration
    assert "FORCE ROW LEVEL SECURITY" in migration
    assert "uq_modeling_neutral_material_candidate" in migration
    assert "fk_modeling_neutral_material_current" in migration

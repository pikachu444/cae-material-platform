from io import StringIO
from pathlib import Path

from alembic import command
from alembic.config import Config

PROJECT_ROOT = Path(__file__).parents[2]
MIGRATION = (
    PROJECT_ROOT
    / "backend/migrations/versions/20260726_028_TD03_reference_elastoplastic_multisolver.py"
)


def test_td03_migration_renders_typed_ir_artifact_and_multisolver_constraints() -> None:
    output = StringIO()
    configuration = Config(str(PROJECT_ROOT / "alembic.ini"), output_buffer=output)
    command.upgrade(configuration, "head", sql=True)
    sql = output.getvalue()
    required = {
        "ADD COLUMN source_dataset_revision_id UUID",
        "ADD COLUMN hardening_curve_artifact_id UUID",
        "ADD COLUMN transformation_profile_digest CHAR(64)",
        "ADD COLUMN source_point_count BIGINT",
        "ADD COLUMN pre_yield_excluded_point_count BIGINT",
        "ADD COLUMN post_necking_excluded_point_count BIGINT",
        "ADD COLUMN necking_source_point_index BIGINT",
        "ck_modeling_material_model_plastic_counts",
        "ADD COLUMN post_necking_approximation_acknowledged BOOLEAN",
        "fk_modeling_material_model_plastic_dataset_revision",
        "fk_modeling_material_model_hardening_artifact",
        "modeling_material_model_family_stable",
        "modeling_material_model_hardening_artifact_valid",
        "approved_constant_true_stress",
        "target_solver = 'abaqus'",
        "cmp.reference.openradioss-law36",
        "cmp.reference.abaqus-isotropic-plasticity",
        "hardening_curve_mapping_status",
        "extension_mapping_status",
        "fk_exporting_solver_card_hardening_artifact",
    }
    assert all(fragment in sql for fragment in required)


def test_td03_migration_avoids_generic_eav_and_row_per_curve_point_storage() -> None:
    migration = MIGRATION.read_text(encoding="utf-8")
    assert "postgresql.JSONB" not in migration
    assert 'sa.Column("key"' not in migration
    assert 'sa.Column("value"' not in migration
    assert 'op.create_table("hardening_curve_point"' not in migration
    assert "organization_id" in migration and "project_id" in migration
    assert "source_dataset_revision_id" in migration
    assert "hardening_curve_sha256" in migration

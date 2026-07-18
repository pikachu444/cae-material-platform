"""T-58 exact canonical JSON and Neutral solver sources for Bulk Export.

Revision ID: 20260908_073_t58_bulk
Revises: 20260907_072_t57_cards
"""

# ruff: noqa: E501

from __future__ import annotations

from alembic import op

revision = "20260908_073_t58_bulk"
down_revision = "20260907_072_t57_cards"
branch_labels = None
depends_on = None

_NEW_COLUMNS = (
    "test_data_document_id",
    "test_data_document_revision_id",
    "mapping_profile_id",
    "mapping_profile_revision_id",
    "processing_recipe_id",
    "processing_recipe_revision_id",
    "neutral_material_id",
    "neutral_material_revision_id",
    "neutral_solver_card_id",
    "neutral_solver_card_revision_id",
)

_ALL_SOURCE_COLUMNS = (
    "raw_asset_id",
    "artifact_id",
    "dataset_id",
    "dataset_revision_id",
    "material_model_id",
    "material_model_revision_id",
    "solver_card_id",
    "solver_card_revision_id",
    *_NEW_COLUMNS,
)

_KINDS = (
    "raw_original",
    "dataset_parquet",
    "dataset_csv",
    "model_ir_json",
    "model_ir_schema",
    "solver_mapping_report",
    "solver_card_native",
    "test_data_json",
    "mapping_profile_json",
    "processing_recipe_json",
    "neutral_material_json",
    "neutral_solver_mapping_report",
    "neutral_solver_card_native",
)


def _quoted(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def _typed_source_check() -> str:
    columns = ", ".join(_ALL_SOURCE_COLUMNS)
    return f"""
      (member_kind='raw_original' AND raw_asset_id IS NOT NULL AND artifact_id IS NOT NULL
       AND num_nonnulls({columns})=2)
      OR (member_kind IN ('dataset_parquet','dataset_csv') AND artifact_id IS NOT NULL
       AND dataset_id IS NOT NULL AND dataset_revision_id IS NOT NULL
       AND num_nonnulls({columns})=3)
      OR (member_kind IN ('model_ir_json','model_ir_schema') AND material_model_id IS NOT NULL
       AND material_model_revision_id IS NOT NULL AND num_nonnulls({columns})=2)
      OR (member_kind IN ('solver_mapping_report','solver_card_native') AND solver_card_id IS NOT NULL
       AND solver_card_revision_id IS NOT NULL AND num_nonnulls({columns})=2)
      OR (member_kind='test_data_json' AND artifact_id IS NOT NULL
       AND test_data_document_id IS NOT NULL AND test_data_document_revision_id IS NOT NULL
       AND num_nonnulls({columns})=3)
      OR (member_kind='mapping_profile_json' AND mapping_profile_id IS NOT NULL
       AND mapping_profile_revision_id IS NOT NULL AND num_nonnulls({columns})=2)
      OR (member_kind='processing_recipe_json' AND processing_recipe_id IS NOT NULL
       AND processing_recipe_revision_id IS NOT NULL AND num_nonnulls({columns})=2)
      OR (member_kind='neutral_material_json' AND artifact_id IS NOT NULL
       AND neutral_material_id IS NOT NULL AND neutral_material_revision_id IS NOT NULL
       AND num_nonnulls({columns})=3)
      OR (member_kind IN ('neutral_solver_mapping_report','neutral_solver_card_native')
       AND neutral_solver_card_id IS NOT NULL AND neutral_solver_card_revision_id IS NOT NULL
       AND num_nonnulls({columns})=2)
    """


def upgrade() -> None:
    kinds = _quoted(_KINDS)
    for table in ("export_selection_member", "export_selection_omission"):
        for column in _NEW_COLUMNS:
            op.execute(f"ALTER TABLE exporting.{table} ADD COLUMN {column} uuid")
        op.execute(
            f"ALTER TABLE exporting.{table} DROP CONSTRAINT ck_exporting_{table}_kind"
        )
        op.execute(
            f"ALTER TABLE exporting.{table} DROP CONSTRAINT ck_exporting_{table}_typed_source"
        )
        op.execute(
            f"ALTER TABLE exporting.{table} ADD CONSTRAINT ck_exporting_{table}_kind "
            f"CHECK (member_kind IN ({kinds}))"
        )
        op.execute(
            f"ALTER TABLE exporting.{table} ADD CONSTRAINT ck_exporting_{table}_typed_source "
            f"CHECK ({_typed_source_check()})"
        )

    op.execute(
        """
        ALTER TABLE exporting.export_selection_member ADD CONSTRAINT
          fk_export_selection_member_test_json FOREIGN KEY
          (organization_id, project_id, classification, test_data_document_id,
           test_data_document_revision_id) REFERENCES datasets.test_data_document_revision
          (organization_id, project_id, classification, aggregate_id, id);
        ALTER TABLE exporting.export_selection_member ADD CONSTRAINT
          fk_export_selection_member_mapping_profile FOREIGN KEY
          (organization_id, project_id, classification, mapping_profile_id,
           mapping_profile_revision_id) REFERENCES processing.mapping_profile_revision
          (organization_id, project_id, classification, aggregate_id, id);
        ALTER TABLE exporting.export_selection_member ADD CONSTRAINT
          fk_export_selection_member_processing_recipe FOREIGN KEY
          (organization_id, project_id, classification, processing_recipe_id,
           processing_recipe_revision_id) REFERENCES processing.common_processing_recipe_revision
          (organization_id, project_id, classification, aggregate_id, id);
        ALTER TABLE exporting.export_selection_member ADD CONSTRAINT
          fk_export_selection_member_neutral_json FOREIGN KEY
          (organization_id, project_id, classification, neutral_material_id,
           neutral_material_revision_id) REFERENCES modeling.neutral_material_revision
          (organization_id, project_id, classification, aggregate_id, id);
        ALTER TABLE exporting.export_selection_member ADD CONSTRAINT
          fk_export_selection_member_neutral_card FOREIGN KEY
          (organization_id, project_id, classification, neutral_solver_card_id,
           neutral_solver_card_revision_id) REFERENCES exporting.neutral_solver_card_revision
          (organization_id, project_id, classification, aggregate_id, id);
        CREATE INDEX ix_export_selection_member_canonical_source ON
          exporting.export_selection_member
          (organization_id, project_id, member_kind, test_data_document_revision_id,
           mapping_profile_revision_id, processing_recipe_revision_id,
           neutral_material_revision_id, neutral_solver_card_revision_id);
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX exporting.ix_export_selection_member_canonical_source")
    for constraint in (
        "fk_export_selection_member_neutral_card",
        "fk_export_selection_member_neutral_json",
        "fk_export_selection_member_processing_recipe",
        "fk_export_selection_member_mapping_profile",
        "fk_export_selection_member_test_json",
    ):
        op.execute(
            f"ALTER TABLE exporting.export_selection_member DROP CONSTRAINT {constraint}"
        )
    legacy_kinds = _quoted(_KINDS[:7])
    legacy_columns = ", ".join(_ALL_SOURCE_COLUMNS[:8])
    legacy_check = f"""
      (member_kind='raw_original' AND raw_asset_id IS NOT NULL AND artifact_id IS NOT NULL
       AND num_nonnulls({legacy_columns})=2)
      OR (member_kind IN ('dataset_parquet','dataset_csv') AND artifact_id IS NOT NULL
       AND dataset_id IS NOT NULL AND dataset_revision_id IS NOT NULL
       AND num_nonnulls({legacy_columns})=3)
      OR (member_kind IN ('model_ir_json','model_ir_schema') AND material_model_id IS NOT NULL
       AND material_model_revision_id IS NOT NULL AND num_nonnulls({legacy_columns})=2)
      OR (member_kind IN ('solver_mapping_report','solver_card_native') AND solver_card_id IS NOT NULL
       AND solver_card_revision_id IS NOT NULL AND num_nonnulls({legacy_columns})=2)
    """
    for table in ("export_selection_member", "export_selection_omission"):
        op.execute(
            f"ALTER TABLE exporting.{table} DROP CONSTRAINT ck_exporting_{table}_typed_source"
        )
        op.execute(
            f"ALTER TABLE exporting.{table} DROP CONSTRAINT ck_exporting_{table}_kind"
        )
        for column in reversed(_NEW_COLUMNS):
            op.execute(f"ALTER TABLE exporting.{table} DROP COLUMN {column}")
        op.execute(
            f"ALTER TABLE exporting.{table} ADD CONSTRAINT ck_exporting_{table}_kind "
            f"CHECK (member_kind IN ({legacy_kinds}))"
        )
        op.execute(
            f"ALTER TABLE exporting.{table} ADD CONSTRAINT ck_exporting_{table}_typed_source "
            f"CHECK ({legacy_check})"
        )

"""Add typed elastoplastic IR evidence and OpenRadioss/Abaqus reference cards.

Revision ID: 20260726_028_td03
Revises: 20260725_027_t31
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260726_028_td03"
down_revision: str | None = "20260725_027_t31"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_LINEAR_FAMILY = "urn:cmp:reference:isotropic-linear-elasticity:1.0.0"
_PLASTIC_FAMILY = "urn:cmp:reference:isotropic-tabulated-plasticity:1.0.0"
_LINEAR_MODEL_DIGEST = "a4e39b23b5d656abb50399b1ae76b799e01872f4f6ebe44a59bc8c901b622cd6"
_PLASTIC_MODEL_DIGEST = "18fd736897f26e6472443a5acf50bf899f8eb8f510ae0eca80dada81047a706f"
_TRANSFORMATION_PROFILE = (
    "urn:cmp:processing:reference-pre-necking-true-plastic-reduction:1.0.0"
)
_TRANSFORMATION_DIGEST = "309b38a58988f0c26a1dfeca702e91283abe025370471def0bf50f257c5e15bf"
_HARDENING_SCHEMA = (
    "urn:cmp:modeling:reference-true-stress-plastic-strain-parquet:1.0.0"
)
_EXTENSION_POLICY = "approved_constant_true_stress"
_LINEAR_EXPORTER = "cmp.reference.openradioss-elast"
_LINEAR_EXPORTER_DIGEST = (
    "65a3f7ea55150a9c660b4303d12a168d8366bb1e41c6c86684a1e8a2fde20a20"
)
_LAW36_EXPORTER = "cmp.reference.openradioss-law36"
_LAW36_EXPORTER_DIGEST = (
    "713da51619eedfeda972205426fe86ae25e0d9f75d85554183f35bca76f73be2"
)
_ABAQUS_EXPORTER = "cmp.reference.abaqus-isotropic-plasticity"
_ABAQUS_EXPORTER_DIGEST = (
    "0585a5dbf0898fcea74009120045b29bf52fef6c428e1285c6603aaee5dd05ad"
)
_STATUS_VALUES = (
    "'exact', 'transformed', 'approximated', 'ignored', 'unsupported', 'not_applicable'"
)


def _extend_material_model_revision() -> None:
    table = "material_model_revision"
    schema = "modeling"
    uuid = postgresql.UUID(as_uuid=True)
    for column in (
        sa.Column("source_dataset_id", uuid, nullable=True),
        sa.Column("source_dataset_revision_id", uuid, nullable=True),
        sa.Column("hardening_curve_artifact_id", uuid, nullable=True),
        sa.Column("hardening_curve_sha256", sa.CHAR(length=64, collation="C"), nullable=True),
        sa.Column("hardening_curve_schema_ref", sa.String(length=255), nullable=True),
        sa.Column("hardening_curve_point_count", sa.BigInteger(), nullable=True),
        sa.Column("source_point_count", sa.BigInteger(), nullable=True),
        sa.Column("pre_yield_excluded_point_count", sa.BigInteger(), nullable=True),
        sa.Column("post_necking_excluded_point_count", sa.BigInteger(), nullable=True),
        sa.Column("necking_source_point_index", sa.BigInteger(), nullable=True),
        sa.Column("transformation_profile_id", sa.String(length=255), nullable=True),
        sa.Column("transformation_profile_version", sa.String(length=64), nullable=True),
        sa.Column(
            "transformation_profile_digest",
            sa.CHAR(length=64, collation="C"),
            nullable=True,
        ),
        sa.Column("necking_engineering_strain", sa.Double(), nullable=True),
        sa.Column("characterized_max_true_plastic_strain", sa.Double(), nullable=True),
        sa.Column("extension_max_true_plastic_strain", sa.Double(), nullable=True),
        sa.Column("post_necking_extension_policy", sa.String(length=64), nullable=True),
        sa.Column("post_necking_approximation_acknowledged", sa.Boolean(), nullable=True),
    ):
        op.add_column(table, column, schema=schema)

    op.drop_constraint(
        "ck_modeling_material_model_reference_family",
        table,
        schema=schema,
        type_="check",
    )
    op.create_check_constraint(
        "ck_modeling_material_model_family",
        table,
        f"model_family_id IN ('{_LINEAR_FAMILY}', '{_PLASTIC_FAMILY}')",
        schema=schema,
    )
    op.create_check_constraint(
        "ck_modeling_material_model_family_digest",
        table,
        "(model_family_id = '"
        + _LINEAR_FAMILY
        + "' AND model_schema_digest = '"
        + _LINEAR_MODEL_DIGEST
        + "') OR (model_family_id = '"
        + _PLASTIC_FAMILY
        + "' AND model_schema_digest = '"
        + _PLASTIC_MODEL_DIGEST
        + "')",
        schema=schema,
    )
    plastic_required = (
        "source_dataset_id IS NOT NULL AND source_dataset_revision_id IS NOT NULL "
        "AND hardening_curve_artifact_id IS NOT NULL AND hardening_curve_sha256 IS NOT NULL "
        "AND hardening_curve_schema_ref IS NOT NULL AND hardening_curve_point_count IS NOT NULL "
        "AND source_point_count IS NOT NULL "
        "AND pre_yield_excluded_point_count IS NOT NULL "
        "AND post_necking_excluded_point_count IS NOT NULL "
        "AND necking_source_point_index IS NOT NULL "
        "AND transformation_profile_id IS NOT NULL "
        "AND transformation_profile_version IS NOT NULL "
        "AND transformation_profile_digest IS NOT NULL "
        "AND necking_engineering_strain IS NOT NULL "
        "AND characterized_max_true_plastic_strain IS NOT NULL "
        "AND extension_max_true_plastic_strain IS NOT NULL "
        "AND post_necking_extension_policy IS NOT NULL "
        "AND post_necking_approximation_acknowledged IS TRUE "
        "AND source_yield_stress_pa IS NOT NULL"
    )
    plastic_empty = (
        "source_dataset_id IS NULL AND source_dataset_revision_id IS NULL "
        "AND hardening_curve_artifact_id IS NULL AND hardening_curve_sha256 IS NULL "
        "AND hardening_curve_schema_ref IS NULL AND hardening_curve_point_count IS NULL "
        "AND source_point_count IS NULL AND pre_yield_excluded_point_count IS NULL "
        "AND post_necking_excluded_point_count IS NULL "
        "AND necking_source_point_index IS NULL "
        "AND transformation_profile_id IS NULL AND transformation_profile_version IS NULL "
        "AND transformation_profile_digest IS NULL AND necking_engineering_strain IS NULL "
        "AND characterized_max_true_plastic_strain IS NULL "
        "AND extension_max_true_plastic_strain IS NULL "
        "AND post_necking_extension_policy IS NULL "
        "AND post_necking_approximation_acknowledged IS NULL"
    )
    op.create_check_constraint(
        "ck_modeling_material_model_plastic_payload",
        table,
        f"(model_family_id = '{_PLASTIC_FAMILY}' AND {plastic_required}) "
        f"OR (model_family_id = '{_LINEAR_FAMILY}' AND {plastic_empty})",
        schema=schema,
    )
    op.create_check_constraint(
        "ck_modeling_material_model_hardening_digest",
        table,
        "hardening_curve_sha256 IS NULL OR hardening_curve_sha256 ~ '^[0-9a-f]{64}$'",
        schema=schema,
    )
    op.create_check_constraint(
        "ck_modeling_material_model_hardening_points",
        table,
        "hardening_curve_point_count IS NULL OR hardening_curve_point_count BETWEEN 2 AND 5000",
        schema=schema,
    )
    op.create_check_constraint(
        "ck_modeling_material_model_plastic_counts",
        table,
        "source_point_count IS NULL OR "
        "(source_point_count BETWEEN 4 AND 5000 "
        "AND pre_yield_excluded_point_count BETWEEN 0 AND source_point_count "
        "AND post_necking_excluded_point_count BETWEEN 0 AND source_point_count - 1 "
        "AND necking_source_point_index BETWEEN 0 AND source_point_count - 1 "
        "AND necking_source_point_index + post_necking_excluded_point_count + 1 "
        "= source_point_count "
        "AND hardening_curve_point_count = source_point_count "
        "- pre_yield_excluded_point_count - post_necking_excluded_point_count + 2)",
        schema=schema,
    )
    op.create_check_constraint(
        "ck_modeling_material_model_plastic_profile",
        table,
        "transformation_profile_id IS NULL OR "
        f"(transformation_profile_id = '{_TRANSFORMATION_PROFILE}' "
        "AND transformation_profile_version = '1.0.0' "
        f"AND transformation_profile_digest = '{_TRANSFORMATION_DIGEST}' "
        f"AND hardening_curve_schema_ref = '{_HARDENING_SCHEMA}' "
        f"AND post_necking_extension_policy = '{_EXTENSION_POLICY}')",
        schema=schema,
    )
    op.create_check_constraint(
        "ck_modeling_material_model_plastic_ranges",
        table,
        "necking_engineering_strain IS NULL OR "
        "(necking_engineering_strain >= 0 "
        "AND characterized_max_true_plastic_strain >= 0 "
        "AND extension_max_true_plastic_strain > characterized_max_true_plastic_strain)",
        schema=schema,
    )
    op.create_foreign_key(
        "fk_modeling_material_model_plastic_dataset_revision",
        table,
        "dataset_revision",
        [
            "organization_id",
            "project_id",
            "classification",
            "source_dataset_id",
            "source_dataset_revision_id",
        ],
        [
            "organization_id",
            "project_id",
            "classification",
            "aggregate_id",
            "id",
        ],
        source_schema=schema,
        referent_schema="datasets",
        ondelete="RESTRICT",
        deferrable=True,
        initially="DEFERRED",
    )
    op.create_foreign_key(
        "fk_modeling_material_model_hardening_artifact",
        table,
        "artifact",
        [
            "organization_id",
            "project_id",
            "classification",
            "hardening_curve_artifact_id",
            "hardening_curve_sha256",
        ],
        ["organization_id", "project_id", "classification", "id", "sha256"],
        source_schema=schema,
        referent_schema="artifact",
        ondelete="RESTRICT",
        deferrable=True,
        initially="DEFERRED",
    )
    op.create_index(
        "ix_modeling_material_model_revision_plastic_dataset",
        table,
        ["organization_id", "project_id", "source_dataset_revision_id"],
        schema=schema,
        postgresql_where=sa.text("source_dataset_revision_id IS NOT NULL"),
    )
    op.execute(
        """
        CREATE FUNCTION modeling.enforce_material_model_family_stability()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE previous_family text;
        BEGIN
          IF NEW.based_on_revision_id IS NULL THEN
            RETURN NEW;
          END IF;
          SELECT model_family_id INTO previous_family
          FROM modeling.material_model_revision
          WHERE organization_id = NEW.organization_id
            AND project_id = NEW.project_id
            AND aggregate_id = NEW.aggregate_id
            AND id = NEW.based_on_revision_id;
          IF previous_family IS NULL OR previous_family IS DISTINCT FROM NEW.model_family_id THEN
            RAISE EXCEPTION 'material model family cannot change across revisions'
              USING ERRCODE = '23514';
          END IF;
          RETURN NEW;
        END;
        $$;
        CREATE TRIGGER modeling_material_model_family_stable
        BEFORE INSERT ON modeling.material_model_revision
        FOR EACH ROW EXECUTE FUNCTION modeling.enforce_material_model_family_stability();
        """
    )
    op.execute(
        f"""
        CREATE FUNCTION modeling.validate_reference_hardening_artifact()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE artifact_kind text;
        DECLARE artifact_role text;
        DECLARE artifact_schema text;
        DECLARE artifact_digest text;
        BEGIN
          IF NEW.model_family_id <> '{_PLASTIC_FAMILY}' THEN
            RETURN NEW;
          END IF;
          SELECT a.artifact_kind, a.artifact_role, a.schema_ref, a.sha256
          INTO artifact_kind, artifact_role, artifact_schema, artifact_digest
          FROM artifact.artifact AS a
          WHERE a.organization_id = NEW.organization_id
            AND a.project_id = NEW.project_id
            AND a.classification = NEW.classification
            AND a.id = NEW.hardening_curve_artifact_id;
          IF artifact_kind IS DISTINCT FROM 'derived'
             OR artifact_role IS DISTINCT FROM 'modeling.hardening_curve'
             OR artifact_schema IS DISTINCT FROM '{_HARDENING_SCHEMA}'
             OR artifact_digest IS DISTINCT FROM NEW.hardening_curve_sha256 THEN
            RAISE EXCEPTION 'hardening curve Artifact contract is invalid'
              USING ERRCODE = '23514';
          END IF;
          RETURN NEW;
        END;
        $$;
        CREATE TRIGGER modeling_material_model_hardening_artifact_valid
        BEFORE INSERT ON modeling.material_model_revision
        FOR EACH ROW EXECUTE FUNCTION modeling.validate_reference_hardening_artifact();
        """
    )


def _extend_solver_card_revision() -> None:
    identity = "solver_card"
    revision_table = "solver_card_revision"
    schema = "exporting"
    uuid = postgresql.UUID(as_uuid=True)
    for constraint in (
        "ck_exporting_solver_card_target_solver",
        "ck_exporting_solver_card_target_version",
        "ck_exporting_solver_card_target_unit_system",
    ):
        op.drop_constraint(constraint, identity, schema=schema, type_="check")
    op.create_check_constraint(
        "ck_exporting_solver_card_target",
        identity,
        "((target_solver = 'openradioss' AND target_version = '2025') "
        "OR (target_solver = 'abaqus' AND target_version = '2025')) "
        "AND target_unit_system = 'kg_m_s'",
        schema=schema,
    )

    for column in (
        sa.Column("material_name", sa.String(length=80), nullable=True),
        sa.Column("hardening_curve_artifact_id", uuid, nullable=True),
        sa.Column("hardening_curve_sha256", sa.CHAR(length=64, collation="C"), nullable=True),
        sa.Column("hardening_curve_point_count", sa.BigInteger(), nullable=True),
        sa.Column("extension_max_true_plastic_strain", sa.Double(), nullable=True),
        sa.Column("post_necking_extension_policy", sa.String(length=64), nullable=True),
        sa.Column("hardening_curve_mapping_status", sa.String(length=32), nullable=True),
        sa.Column("extension_mapping_status", sa.String(length=32), nullable=True),
    ):
        op.add_column(revision_table, column, schema=schema)

    for constraint in (
        "ck_exporting_solver_card_model_digest",
        "ck_exporting_solver_card_revision_target_solver",
        "ck_exporting_solver_card_revision_target_version",
        "ck_exporting_solver_card_revision_target_unit_system",
        "ck_exporting_solver_card_text",
        "ck_exporting_solver_card_exporter_id",
        "ck_exporting_solver_card_exporter_version",
        "ck_exporting_solver_card_exporter_digest",
    ):
        op.drop_constraint(constraint, revision_table, schema=schema, type_="check")

    op.create_check_constraint(
        "ck_exporting_solver_card_model_digest",
        revision_table,
        f"model_schema_digest IN ('{_LINEAR_MODEL_DIGEST}', '{_PLASTIC_MODEL_DIGEST}')",
        schema=schema,
    )
    op.create_check_constraint(
        "ck_exporting_solver_card_revision_target",
        revision_table,
        "((target_solver = 'openradioss' AND target_version = '2025') "
        "OR (target_solver = 'abaqus' AND target_version = '2025')) "
        "AND target_unit_system = 'kg_m_s'",
        schema=schema,
    )
    op.create_check_constraint(
        "ck_exporting_solver_card_text",
        revision_table,
        "length(card_text) BETWEEN 1 AND 2000000",
        schema=schema,
    )
    plastic_required = (
        "material_name IS NOT NULL AND source_yield_stress_pa IS NOT NULL "
        "AND hardening_curve_artifact_id IS NOT NULL AND hardening_curve_sha256 IS NOT NULL "
        "AND hardening_curve_point_count IS NOT NULL "
        "AND extension_max_true_plastic_strain IS NOT NULL "
        "AND post_necking_extension_policy IS NOT NULL "
        "AND hardening_curve_mapping_status IS NOT NULL "
        "AND extension_mapping_status IS NOT NULL "
        "AND density_mapping_status = 'exact' "
        "AND youngs_modulus_mapping_status = 'exact' "
        "AND poisson_ratio_mapping_status = 'exact' "
        "AND source_yield_mapping_status = 'transformed' "
        "AND hardening_curve_mapping_status = 'transformed' "
        "AND extension_mapping_status = 'approximated' "
        "AND temperature_applicability_mapping_status = 'not_applicable' "
        "AND strain_rate_applicability_mapping_status = 'not_applicable'"
    )
    plastic_empty = (
        "material_name IS NULL AND hardening_curve_artifact_id IS NULL "
        "AND hardening_curve_sha256 IS NULL AND hardening_curve_point_count IS NULL "
        "AND extension_max_true_plastic_strain IS NULL "
        "AND post_necking_extension_policy IS NULL "
        "AND hardening_curve_mapping_status IS NULL AND extension_mapping_status IS NULL"
    )
    exporter_contract = (
        "(exporter_id = '"
        + _LINEAR_EXPORTER
        + "' AND exporter_version = '1.0.0' AND exporter_digest = '"
        + _LINEAR_EXPORTER_DIGEST
        + "' AND target_solver = 'openradioss' AND model_schema_digest = '"
        + _LINEAR_MODEL_DIGEST
        + "' AND "
        + plastic_empty
        + ") OR (exporter_id = '"
        + _LAW36_EXPORTER
        + "' AND exporter_version = '1.0.0' AND exporter_digest = '"
        + _LAW36_EXPORTER_DIGEST
        + "' AND target_solver = 'openradioss' AND model_schema_digest = '"
        + _PLASTIC_MODEL_DIGEST
        + "' AND unit_system_mapping_status = 'exact' AND "
        + plastic_required
        + ") OR (exporter_id = '"
        + _ABAQUS_EXPORTER
        + "' AND exporter_version = '1.0.0' AND exporter_digest = '"
        + _ABAQUS_EXPORTER_DIGEST
        + "' AND target_solver = 'abaqus' AND model_schema_digest = '"
        + _PLASTIC_MODEL_DIGEST
        + "' AND unit_system_mapping_status = 'transformed' AND "
        + plastic_required
        + ")"
    )
    op.create_check_constraint(
        "ck_exporting_solver_card_exporter_contract",
        revision_table,
        exporter_contract,
        schema=schema,
    )
    op.create_check_constraint(
        "ck_exporting_solver_card_material_name",
        revision_table,
        "material_name IS NULL OR material_name ~ '^[A-Za-z][A-Za-z0-9_-]{0,79}$'",
        schema=schema,
    )
    op.create_check_constraint(
        "ck_exporting_solver_card_hardening_digest",
        revision_table,
        "hardening_curve_sha256 IS NULL OR hardening_curve_sha256 ~ '^[0-9a-f]{64}$'",
        schema=schema,
    )
    op.create_check_constraint(
        "ck_exporting_solver_card_hardening_points",
        revision_table,
        "hardening_curve_point_count IS NULL OR hardening_curve_point_count BETWEEN 2 AND 5000",
        schema=schema,
    )
    op.create_check_constraint(
        "ck_exporting_solver_card_extension",
        revision_table,
        "extension_max_true_plastic_strain IS NULL OR "
        "(extension_max_true_plastic_strain > 0 AND "
        f"post_necking_extension_policy = '{_EXTENSION_POLICY}')",
        schema=schema,
    )
    for column, suffix in (
        ("hardening_curve_mapping_status", "hardening_map_status"),
        ("extension_mapping_status", "extension_map_status"),
    ):
        op.create_check_constraint(
            f"ck_exporting_solver_card_{suffix}",
            revision_table,
            f"{column} IS NULL OR {column} IN ({_STATUS_VALUES})",
            schema=schema,
        )
    op.create_foreign_key(
        "fk_exporting_solver_card_hardening_artifact",
        revision_table,
        "artifact",
        [
            "organization_id",
            "project_id",
            "classification",
            "hardening_curve_artifact_id",
            "hardening_curve_sha256",
        ],
        ["organization_id", "project_id", "classification", "id", "sha256"],
        source_schema=schema,
        referent_schema="artifact",
        ondelete="RESTRICT",
        deferrable=True,
        initially="DEFERRED",
    )
    op.create_index(
        "ix_exporting_solver_card_revision_hardening_artifact",
        revision_table,
        ["organization_id", "project_id", "hardening_curve_artifact_id"],
        schema=schema,
        postgresql_where=sa.text("hardening_curve_artifact_id IS NOT NULL"),
    )


def upgrade() -> None:
    _extend_material_model_revision()
    _extend_solver_card_revision()


def downgrade() -> None:
    op.drop_index(
        "ix_exporting_solver_card_revision_hardening_artifact",
        table_name="solver_card_revision",
        schema="exporting",
    )
    op.drop_constraint(
        "fk_exporting_solver_card_hardening_artifact",
        "solver_card_revision",
        schema="exporting",
        type_="foreignkey",
    )
    for constraint in (
        "ck_exporting_solver_card_extension_map_status",
        "ck_exporting_solver_card_hardening_map_status",
        "ck_exporting_solver_card_extension",
        "ck_exporting_solver_card_hardening_points",
        "ck_exporting_solver_card_hardening_digest",
        "ck_exporting_solver_card_material_name",
        "ck_exporting_solver_card_exporter_contract",
        "ck_exporting_solver_card_text",
        "ck_exporting_solver_card_revision_target",
        "ck_exporting_solver_card_model_digest",
    ):
        op.drop_constraint(
            constraint,
            "solver_card_revision",
            schema="exporting",
            type_="check",
        )
    for column in (
        "extension_mapping_status",
        "hardening_curve_mapping_status",
        "post_necking_extension_policy",
        "extension_max_true_plastic_strain",
        "hardening_curve_point_count",
        "hardening_curve_sha256",
        "hardening_curve_artifact_id",
        "material_name",
    ):
        op.drop_column("solver_card_revision", column, schema="exporting")
    op.drop_constraint(
        "ck_exporting_solver_card_target", "solver_card", schema="exporting", type_="check"
    )
    op.create_check_constraint(
        "ck_exporting_solver_card_target_solver",
        "solver_card",
        "target_solver = 'openradioss'",
        schema="exporting",
    )
    op.create_check_constraint(
        "ck_exporting_solver_card_target_version",
        "solver_card",
        "target_version = '2025'",
        schema="exporting",
    )
    op.create_check_constraint(
        "ck_exporting_solver_card_target_unit_system",
        "solver_card",
        "target_unit_system = 'kg_m_s'",
        schema="exporting",
    )
    op.create_check_constraint(
        "ck_exporting_solver_card_model_digest",
        "solver_card_revision",
        f"model_schema_digest = '{_LINEAR_MODEL_DIGEST}'",
        schema="exporting",
    )
    op.create_check_constraint(
        "ck_exporting_solver_card_revision_target_solver",
        "solver_card_revision",
        "target_solver = 'openradioss'",
        schema="exporting",
    )
    op.create_check_constraint(
        "ck_exporting_solver_card_revision_target_version",
        "solver_card_revision",
        "target_version = '2025'",
        schema="exporting",
    )
    op.create_check_constraint(
        "ck_exporting_solver_card_revision_target_unit_system",
        "solver_card_revision",
        "target_unit_system = 'kg_m_s'",
        schema="exporting",
    )
    op.create_check_constraint(
        "ck_exporting_solver_card_text",
        "solver_card_revision",
        "length(card_text) BETWEEN 1 AND 20000",
        schema="exporting",
    )
    op.create_check_constraint(
        "ck_exporting_solver_card_exporter_id",
        "solver_card_revision",
        f"exporter_id = '{_LINEAR_EXPORTER}'",
        schema="exporting",
    )
    op.create_check_constraint(
        "ck_exporting_solver_card_exporter_version",
        "solver_card_revision",
        "exporter_version = '1.0.0'",
        schema="exporting",
    )
    op.create_check_constraint(
        "ck_exporting_solver_card_exporter_digest",
        "solver_card_revision",
        f"exporter_digest = '{_LINEAR_EXPORTER_DIGEST}'",
        schema="exporting",
    )

    op.execute(
        "DROP TRIGGER modeling_material_model_hardening_artifact_valid "
        "ON modeling.material_model_revision"
    )
    op.execute("DROP FUNCTION modeling.validate_reference_hardening_artifact()")
    op.execute(
        "DROP TRIGGER modeling_material_model_family_stable "
        "ON modeling.material_model_revision"
    )
    op.execute("DROP FUNCTION modeling.enforce_material_model_family_stability()")
    op.drop_index(
        "ix_modeling_material_model_revision_plastic_dataset",
        table_name="material_model_revision",
        schema="modeling",
    )
    op.drop_constraint(
        "fk_modeling_material_model_hardening_artifact",
        "material_model_revision",
        schema="modeling",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_modeling_material_model_plastic_dataset_revision",
        "material_model_revision",
        schema="modeling",
        type_="foreignkey",
    )
    for constraint in (
        "ck_modeling_material_model_plastic_ranges",
        "ck_modeling_material_model_plastic_profile",
        "ck_modeling_material_model_plastic_counts",
        "ck_modeling_material_model_hardening_points",
        "ck_modeling_material_model_hardening_digest",
        "ck_modeling_material_model_plastic_payload",
        "ck_modeling_material_model_family_digest",
        "ck_modeling_material_model_family",
    ):
        op.drop_constraint(
            constraint,
            "material_model_revision",
            schema="modeling",
            type_="check",
        )
    for column in (
        "post_necking_approximation_acknowledged",
        "post_necking_extension_policy",
        "extension_max_true_plastic_strain",
        "characterized_max_true_plastic_strain",
        "necking_engineering_strain",
        "transformation_profile_digest",
        "transformation_profile_version",
        "transformation_profile_id",
        "necking_source_point_index",
        "post_necking_excluded_point_count",
        "pre_yield_excluded_point_count",
        "source_point_count",
        "hardening_curve_point_count",
        "hardening_curve_schema_ref",
        "hardening_curve_sha256",
        "hardening_curve_artifact_id",
        "source_dataset_revision_id",
        "source_dataset_id",
    ):
        op.drop_column("material_model_revision", column, schema="modeling")
    op.create_check_constraint(
        "ck_modeling_material_model_reference_family",
        "material_model_revision",
        f"model_family_id = '{_LINEAR_FAMILY}'",
        schema="modeling",
    )

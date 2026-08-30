"""Add governed DMA result evidence to Common Processing Output revisions."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261006_105_dma_tts"
down_revision: str | None = "20261005_104_lve_calibration"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "common_processing_output_revision"
_SCHEMA = "processing"


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE testing.test_method
          DROP CONSTRAINT ck_testing_test_method_code;
        ALTER TABLE testing.test_method_revision
          DROP CONSTRAINT ck_testing_test_method_revision_declared;
        ALTER TABLE testing.test_method
          ADD CONSTRAINT ck_testing_test_method_code CHECK
          (method_code IN (
            'reference_uniaxial_tensile',
            'reference_planar_tension',
            'reference_biaxial_tension',
            'reference_shear_relaxation',
            'reference_shear_dma_frequency_sweep',
            'reference_shear_dma_temperature_sweep'
          ));
        ALTER TABLE testing.test_method_revision
          ADD CONSTRAINT ck_testing_test_method_revision_declared CHECK
          ((method_code='reference_uniaxial_tensile' AND
            display_name='Reference uniaxial tensile CSV') OR
           (method_code='reference_planar_tension' AND
            display_name='Reference planar tension CSV') OR
           (method_code='reference_biaxial_tension' AND
            display_name='Reference biaxial tension CSV') OR
           (method_code='reference_shear_relaxation' AND
            display_name='Reference shear relaxation CSV') OR
           (method_code='reference_shear_dma_frequency_sweep' AND
            display_name='Reference shear DMA frequency sweep') OR
           (method_code='reference_shear_dma_temperature_sweep' AND
            display_name='Reference fixed-frequency shear DMA temperature sweep'));
        """
    )
    op.execute(
        """
        ALTER TABLE datasets.import_profile_revision
          DROP CONSTRAINT import_profile_revision_data_schema_check,
          ADD CONSTRAINT import_profile_revision_data_schema_check CHECK (data_schema IN
            ('monotonic_tension','monotonic_compression','planar_tension','biaxial_tension',
             'simple_shear','shear_relaxation','dma_frequency_temperature_sweep',
             'dma_temperature_sweep','forming_limit_diagram'))
        """
    )
    op.add_column(
        _TABLE,
        sa.Column(
            "source_profile_kind",
            sa.String(64),
            nullable=False,
            server_default=sa.text("'common_mapping_profile'"),
        ),
        schema=_SCHEMA,
    )
    op.add_column(
        _TABLE,
        sa.Column("governed_import_profile_id", sa.Uuid(), nullable=True),
        schema=_SCHEMA,
    )
    op.add_column(
        _TABLE,
        sa.Column("governed_import_profile_revision_id", sa.Uuid(), nullable=True),
        schema=_SCHEMA,
    )
    op.add_column(
        _TABLE,
        sa.Column("governed_import_profile_sha256", sa.CHAR(64), nullable=True),
        schema=_SCHEMA,
    )
    op.add_column(
        _TABLE,
        sa.Column("result_artifact_id", sa.Uuid(), nullable=True),
        schema=_SCHEMA,
    )
    op.add_column(
        _TABLE,
        sa.Column("result_sha256", sa.CHAR(64), nullable=True),
        schema=_SCHEMA,
    )
    op.add_column(
        _TABLE,
        sa.Column("result_schema_ref", sa.String(255), nullable=True),
        schema=_SCHEMA,
    )
    op.add_column(
        _TABLE,
        sa.Column("result_media_type", sa.String(255), nullable=True),
        schema=_SCHEMA,
    )
    op.alter_column(
        _TABLE,
        "source_profile_kind",
        existing_type=sa.String(64),
        server_default=None,
        nullable=False,
        schema=_SCHEMA,
    )
    for column in (
        "mapping_profile_id",
        "mapping_profile_revision_id",
        "mapping_profile_sha256",
    ):
        op.alter_column(_TABLE, column, nullable=True, schema=_SCHEMA)
    op.create_check_constraint(
        "ck_common_processing_output_source_profile_xor",
        _TABLE,
        "(source_profile_kind = 'common_mapping_profile' "
        "AND mapping_profile_id IS NOT NULL "
        "AND mapping_profile_revision_id IS NOT NULL "
        "AND mapping_profile_sha256 IS NOT NULL "
        "AND governed_import_profile_id IS NULL "
        "AND governed_import_profile_revision_id IS NULL "
        "AND governed_import_profile_sha256 IS NULL) OR "
        "(source_profile_kind = 'governed_import_profile' "
        "AND mapping_profile_id IS NULL "
        "AND mapping_profile_revision_id IS NULL "
        "AND mapping_profile_sha256 IS NULL "
        "AND governed_import_profile_id IS NOT NULL "
        "AND governed_import_profile_revision_id IS NOT NULL "
        "AND governed_import_profile_sha256 IS NOT NULL)",
        schema=_SCHEMA,
    )
    plan_table = "linear_viscoelastic_calibration_plan_revision"
    plan_schema = "modeling"
    for column in (
        sa.Column("processing_output_id", sa.Uuid(), nullable=True),
        sa.Column("processing_output_revision_id", sa.Uuid(), nullable=True),
        sa.Column("processing_output_sha256", sa.CHAR(64), nullable=True),
        sa.Column("processing_metadata_artifact_id", sa.Uuid(), nullable=True),
        sa.Column("processing_metadata_artifact_sha256", sa.CHAR(64), nullable=True),
        sa.Column("processing_metadata_artifact_media_type", sa.String(255), nullable=True),
        sa.Column("processing_result_artifact_id", sa.Uuid(), nullable=True),
        sa.Column("processing_result_artifact_sha256", sa.CHAR(64), nullable=True),
        sa.Column("processing_result_artifact_media_type", sa.String(255), nullable=True),
    ):
        op.add_column(plan_table, column, schema=plan_schema)
    op.create_check_constraint(
        "ck_lve_calibration_processing_input_all_or_none",
        plan_table,
        "(processing_output_id IS NULL "
        "AND processing_output_revision_id IS NULL "
        "AND processing_output_sha256 IS NULL "
        "AND processing_metadata_artifact_id IS NULL "
        "AND processing_metadata_artifact_sha256 IS NULL "
        "AND processing_metadata_artifact_media_type IS NULL "
        "AND processing_result_artifact_id IS NULL "
        "AND processing_result_artifact_sha256 IS NULL "
        "AND processing_result_artifact_media_type IS NULL) OR "
        "(processing_output_id IS NOT NULL "
        "AND processing_output_revision_id IS NOT NULL "
        "AND processing_output_sha256 ~ '^[0-9a-f]{64}$' "
        "AND processing_metadata_artifact_id IS NOT NULL "
        "AND processing_metadata_artifact_sha256 ~ '^[0-9a-f]{64}$' "
        "AND processing_metadata_artifact_media_type IS NOT NULL "
        "AND processing_result_artifact_id IS NOT NULL "
        "AND processing_result_artifact_sha256 ~ '^[0-9a-f]{64}$' "
        "AND processing_result_artifact_media_type IS NOT NULL)",
        schema=plan_schema,
    )
    op.create_check_constraint(
        "ck_common_processing_output_result_artifact_all_or_none",
        _TABLE,
        "(result_artifact_id IS NULL AND result_sha256 IS NULL "
        "AND result_schema_ref IS NULL AND result_media_type IS NULL) OR "
        "(result_artifact_id IS NOT NULL AND result_sha256 IS NOT NULL "
        "AND result_schema_ref IS NOT NULL AND result_media_type IS NOT NULL)",
        schema=_SCHEMA,
    )
    op.create_check_constraint(
        "ck_common_processing_output_governed_result_required",
        _TABLE,
        "source_profile_kind <> 'governed_import_profile' OR result_artifact_id IS NOT NULL",
        schema=_SCHEMA,
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$ BEGIN
          IF EXISTS (
            SELECT 1 FROM testing.test_method
            WHERE method_code='reference_shear_dma_temperature_sweep'
          ) OR EXISTS (
            SELECT 1 FROM testing.test_method_revision
            WHERE method_code='reference_shear_dma_temperature_sweep'
          ) THEN
            RAISE EXCEPTION
              'cannot downgrade while DMA temperature-sweep Test Method records exist';
          END IF;
        END $$;
        ALTER TABLE testing.test_method
          DROP CONSTRAINT ck_testing_test_method_code;
        ALTER TABLE testing.test_method_revision
          DROP CONSTRAINT ck_testing_test_method_revision_declared;
        ALTER TABLE testing.test_method
          ADD CONSTRAINT ck_testing_test_method_code CHECK
          (method_code IN (
            'reference_uniaxial_tensile',
            'reference_planar_tension',
            'reference_biaxial_tension',
            'reference_shear_relaxation',
            'reference_shear_dma_frequency_sweep'
          ));
        ALTER TABLE testing.test_method_revision
          ADD CONSTRAINT ck_testing_test_method_revision_declared CHECK
          ((method_code='reference_uniaxial_tensile' AND
            display_name='Reference uniaxial tensile CSV') OR
           (method_code='reference_planar_tension' AND
            display_name='Reference planar tension CSV') OR
           (method_code='reference_biaxial_tension' AND
            display_name='Reference biaxial tension CSV') OR
           (method_code='reference_shear_relaxation' AND
            display_name='Reference shear relaxation CSV') OR
           (method_code='reference_shear_dma_frequency_sweep' AND
            display_name='Reference shear DMA frequency sweep'));
        """
    )
    op.drop_constraint(
        "ck_lve_calibration_processing_input_all_or_none",
        "linear_viscoelastic_calibration_plan_revision",
        type_="check",
        schema="modeling",
    )
    for column in (
        "processing_result_artifact_media_type",
        "processing_result_artifact_sha256",
        "processing_result_artifact_id",
        "processing_metadata_artifact_media_type",
        "processing_metadata_artifact_sha256",
        "processing_metadata_artifact_id",
        "processing_output_sha256",
        "processing_output_revision_id",
        "processing_output_id",
    ):
        op.drop_column(
            "linear_viscoelastic_calibration_plan_revision",
            column,
            schema="modeling",
        )
    op.drop_constraint(
        "ck_common_processing_output_governed_result_required",
        _TABLE,
        type_="check",
        schema=_SCHEMA,
    )
    op.execute(
        """
        DO $$ BEGIN
          IF EXISTS (
            SELECT 1 FROM processing.common_processing_output_revision
            WHERE source_profile_kind = 'governed_import_profile'
          ) OR EXISTS (
            SELECT 1 FROM datasets.import_profile_revision
            WHERE data_schema = 'dma_temperature_sweep'
          ) THEN
            RAISE EXCEPTION
              'cannot downgrade while governed DMA temperature-sweep records exist';
          END IF;
        END $$
        """
    )
    op.drop_constraint(
        "ck_common_processing_output_result_artifact_all_or_none",
        _TABLE,
        type_="check",
        schema=_SCHEMA,
    )
    op.drop_constraint(
        "ck_common_processing_output_source_profile_xor",
        _TABLE,
        type_="check",
        schema=_SCHEMA,
    )
    for column in (
        "mapping_profile_id",
        "mapping_profile_revision_id",
        "mapping_profile_sha256",
    ):
        op.alter_column(_TABLE, column, nullable=False, schema=_SCHEMA)
    for column in (
        "result_media_type",
        "result_schema_ref",
        "result_sha256",
        "result_artifact_id",
        "governed_import_profile_sha256",
        "governed_import_profile_revision_id",
        "governed_import_profile_id",
        "source_profile_kind",
    ):
        op.drop_column(_TABLE, column, schema=_SCHEMA)
    op.execute(
        """
        ALTER TABLE datasets.import_profile_revision
          DROP CONSTRAINT import_profile_revision_data_schema_check,
          ADD CONSTRAINT import_profile_revision_data_schema_check CHECK (data_schema IN
            ('monotonic_tension','monotonic_compression','planar_tension','biaxial_tension',
             'simple_shear','shear_relaxation','dma_frequency_temperature_sweep',
             'forming_limit_diagram'))
        """
    )

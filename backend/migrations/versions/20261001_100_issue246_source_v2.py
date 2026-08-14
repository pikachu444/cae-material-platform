"""Issue #246 source-v2 category and business-key projection.

Revision ID: 20261001_100_issue246_source_v2
Revises: 20260930_099_issue209_dma_fld
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20261001_100_issue246_source_v2"
down_revision: str | None = "20260930_099_issue209_dma_fld"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE catalog.schema_table_revision
          ADD COLUMN data_category varchar(32),
          ADD CONSTRAINT schema_table_revision_data_category_check CHECK (
            data_category IS NULL OR data_category IN
              ('technical_data', 'test_data', 'simulation_data')
          );

        ALTER TABLE catalog.attribute_definition_revision
          ADD COLUMN business_key boolean NOT NULL DEFAULT false,
          ADD CONSTRAINT attribute_definition_revision_business_key_check CHECK (
            NOT business_key OR data_type IN ('text', 'discrete')
          );

        ALTER TABLE catalog.schema_definition_bundle_binding
          ADD COLUMN source_file varchar(1000),
          ADD COLUMN source_file_sha256 char(64),
          ADD CONSTRAINT schema_definition_bundle_binding_source_file_check CHECK (
            (source_file IS NULL AND source_file_sha256 IS NULL) OR
            (source_file IS NOT NULL AND source_file_sha256 ~ '^[0-9a-f]{64}$')
          );
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE catalog.attribute_definition_revision
          DROP CONSTRAINT attribute_definition_revision_business_key_check,
          DROP COLUMN business_key;

        ALTER TABLE catalog.schema_definition_bundle_binding
          DROP CONSTRAINT schema_definition_bundle_binding_source_file_check,
          DROP COLUMN source_file_sha256,
          DROP COLUMN source_file;

        ALTER TABLE catalog.schema_table_revision
          DROP CONSTRAINT schema_table_revision_data_category_check,
          DROP COLUMN data_category;
        """
    )

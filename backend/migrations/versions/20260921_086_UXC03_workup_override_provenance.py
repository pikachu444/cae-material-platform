"""Persist structured manual Processing Output workup evidence.

Revision ID: 20260724_086_uxc03_workup
Revises: 20260920_085_t89_dma_source

Traceability: UXC-03, T-53.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260724_086_uxc03_workup"
down_revision: str | None = "20260920_085_t89_dma_source"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE processing.common_processing_output_revision
          ADD COLUMN workup_overrides jsonb NOT NULL DEFAULT '[]'::jsonb,
          ADD CONSTRAINT ck_processing_common_output_workup_overrides
            CHECK (jsonb_typeof(workup_overrides) = 'array');
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$ BEGIN
          IF EXISTS (
            SELECT 1 FROM processing.common_processing_output_revision
            WHERE workup_overrides <> '[]'::jsonb
          ) THEN
            RAISE EXCEPTION
              'cannot downgrade while immutable Processing Output workup evidence exists';
          END IF;
        END $$;
        ALTER TABLE processing.common_processing_output_revision
          DROP CONSTRAINT ck_processing_common_output_workup_overrides,
          DROP COLUMN workup_overrides;
        """
    )

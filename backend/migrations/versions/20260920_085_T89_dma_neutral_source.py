"""Allow the explicit DMA frequency test mode on Neutral source revisions.

Revision ID: 20260920_085_t89_dma_source
Revises: 20260919_084_t89_dma_neutral

Traceability: T-89.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260920_085_t89_dma_source"
down_revision: str | None = "20260919_084_t89_dma_neutral"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE modeling.neutral_material_source_dataset
          DROP CONSTRAINT ck_modeling_neutral_material_source_test_mode,
          ADD CONSTRAINT ck_modeling_neutral_material_source_test_mode CHECK
          (test_mode IN ('uniaxial_tension','planar_tension','biaxial_tension',
                         'stress_relaxation','dma_frequency'));
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$ BEGIN
          IF EXISTS (
            SELECT 1 FROM modeling.neutral_material_source_dataset
            WHERE test_mode='dma_frequency'
          ) THEN
            RAISE EXCEPTION 'cannot downgrade while immutable DMA source evidence exists';
          END IF;
        END $$;
        ALTER TABLE modeling.neutral_material_source_dataset
          DROP CONSTRAINT ck_modeling_neutral_material_source_test_mode,
          ADD CONSTRAINT ck_modeling_neutral_material_source_test_mode CHECK
          (test_mode IN ('uniaxial_tension','planar_tension','biaxial_tension',
                         'stress_relaxation'));
        """
    )

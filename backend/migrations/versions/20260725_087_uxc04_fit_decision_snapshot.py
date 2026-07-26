"""Persist the optional immutable UXC-04 Fit Decision snapshot.

Revision ID: 20260725_087_uxc04_fit_decision
Revises: 20260724_086_uxc03_workup
Traceability: UXC-04, FR-DAT-005, FR-JSON-007.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260725_087_uxc04_fit_decision"
down_revision: str | None = "20260724_086_uxc03_workup"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE processing.common_processing_output_revision
          ADD COLUMN fit_decision jsonb NULL,
          ADD CONSTRAINT ck_processing_common_output_fit_decision
            CHECK (fit_decision IS NULL OR jsonb_typeof(fit_decision) = 'object');

        ALTER TABLE modeling.material_model_revision
          ADD COLUMN fit_decision_evidence jsonb NULL,
          ADD CONSTRAINT ck_modeling_material_model_fit_decision
            CHECK (
              fit_decision_evidence IS NULL
              OR jsonb_typeof(fit_decision_evidence) = 'object'
            );

        ALTER TABLE modeling.linear_viscoelastic_processing_evidence
          ADD COLUMN fit_decision_evidence jsonb NULL,
          ADD CONSTRAINT ck_modeling_linear_fit_decision
            CHECK (
              fit_decision_evidence IS NULL
              OR jsonb_typeof(fit_decision_evidence) = 'object'
            );

        ALTER TABLE modeling.neutral_material_revision
          ADD COLUMN fit_decision_evidence jsonb NULL,
          ADD CONSTRAINT ck_modeling_neutral_fit_decision
            CHECK (
              fit_decision_evidence IS NULL
              OR jsonb_typeof(fit_decision_evidence) = 'object'
            );
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$ BEGIN
          IF EXISTS (
            SELECT 1 FROM processing.common_processing_output_revision
            WHERE fit_decision IS NOT NULL
            UNION ALL
            SELECT 1 FROM modeling.material_model_revision
            WHERE fit_decision_evidence IS NOT NULL
            UNION ALL
            SELECT 1 FROM modeling.linear_viscoelastic_processing_evidence
            WHERE fit_decision_evidence IS NOT NULL
            UNION ALL
            SELECT 1 FROM modeling.neutral_material_revision
            WHERE fit_decision_evidence IS NOT NULL
          ) THEN
            RAISE EXCEPTION
              'cannot downgrade while immutable Processing Output fit decisions exist';
          END IF;
        END $$;
        ALTER TABLE processing.common_processing_output_revision
          DROP CONSTRAINT ck_processing_common_output_fit_decision,
          DROP COLUMN fit_decision;
        ALTER TABLE modeling.material_model_revision
          DROP CONSTRAINT ck_modeling_material_model_fit_decision,
          DROP COLUMN fit_decision_evidence;
        ALTER TABLE modeling.linear_viscoelastic_processing_evidence
          DROP CONSTRAINT ck_modeling_linear_fit_decision,
          DROP COLUMN fit_decision_evidence;
        ALTER TABLE modeling.neutral_material_revision
          DROP CONSTRAINT ck_modeling_neutral_fit_decision,
          DROP COLUMN fit_decision_evidence;
        """
    )

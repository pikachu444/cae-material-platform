"""Persist exact Processing Batch member workup and fit evidence (Issue #157).

Revision ID: 20260922_091_uxc07_evidence
Revises: 20260726_090_uxc00g
Traceability: Issue #157, FR-BAT-001..007, FR-MOD-M-004..006, FR-MOD-P-004.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260922_091_uxc07_evidence"
down_revision: str | None = "20260726_090_uxc00g"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE processing.common_processing_batch_member
          ADD COLUMN workup_overrides jsonb NOT NULL DEFAULT '[]'::jsonb,
          ADD COLUMN fit_decision jsonb NULL,
          ADD CONSTRAINT ck_processing_common_batch_member_workup_overrides
            CHECK (jsonb_typeof(workup_overrides) = 'array'),
          ADD CONSTRAINT ck_processing_common_batch_member_fit_decision
            CHECK (fit_decision IS NULL OR jsonb_typeof(fit_decision) = 'object');
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$ BEGIN
          IF EXISTS (
            SELECT 1 FROM processing.common_processing_batch_member
            WHERE workup_overrides <> '[]'::jsonb OR fit_decision IS NOT NULL
          ) THEN
            RAISE EXCEPTION
              'cannot downgrade while immutable Processing Batch member evidence exists';
          END IF;
        END $$;
        ALTER TABLE processing.common_processing_batch_member
          DROP CONSTRAINT ck_processing_common_batch_member_fit_decision,
          DROP CONSTRAINT ck_processing_common_batch_member_workup_overrides,
          DROP COLUMN fit_decision,
          DROP COLUMN workup_overrides;
        """
    )

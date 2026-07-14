"""Persist the frozen applicability note on elastoplastic Solver Card revisions.

Revision ID: 20260727_029_p0
Revises: 20260726_028_td03
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260727_029_p0"
down_revision: str | None = "20260726_028_td03"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE exporting.solver_card_revision "
        "ADD COLUMN applicability_note text NULL"
    )
    op.execute(
        "ALTER TABLE exporting.solver_card_revision "
        "ADD CONSTRAINT ck_exporting_solver_card_applicability_note "
        "CHECK (applicability_note IS NULL "
        "OR length(btrim(applicability_note)) BETWEEN 1 AND 2000)"
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (
            SELECT 1 FROM exporting.solver_card_revision
            WHERE applicability_note IS NOT NULL
          ) THEN
            RAISE EXCEPTION USING
              ERRCODE = '55000',
              MESSAGE = 'cannot downgrade while Solver Card applicability evidence exists';
          END IF;
        END;
        $$
        """
    )
    op.execute(
        "ALTER TABLE exporting.solver_card_revision "
        "DROP CONSTRAINT ck_exporting_solver_card_applicability_note"
    )
    op.execute(
        "ALTER TABLE exporting.solver_card_revision DROP COLUMN applicability_note"
    )

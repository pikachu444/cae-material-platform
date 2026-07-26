"""Add nullable immutable governed-source projections for UXC-06B.

Revision ID: 20260726_088_uxc06b
Revises: 20260725_087_uxc04_fit_decision
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260726_088_uxc06b"
down_revision: str | None = "20260725_087_uxc04_fit_decision"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE datasets.test_data_document_revision "
        "ADD COLUMN governed_source jsonb NULL "
        "CHECK (governed_source IS NULL OR jsonb_typeof(governed_source) = 'object')"
    )
    op.execute(
        "ALTER TABLE processing.common_processing_output_revision "
        "ADD COLUMN export_provenance jsonb NULL "
        "CHECK (export_provenance IS NULL OR jsonb_typeof(export_provenance) = 'object')"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE processing.common_processing_output_revision "
        "DROP COLUMN export_provenance"
    )
    op.execute("ALTER TABLE datasets.test_data_document_revision DROP COLUMN governed_source")

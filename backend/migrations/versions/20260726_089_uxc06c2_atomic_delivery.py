"""Add immutable UXC-06C2 Solver Card delivery receipts.

Revision ID: 20260726_089_uxc06c2
Revises: 20260726_088_uxc06b
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260726_089_uxc06c2"
down_revision = "20260726_088_uxc06b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    op.create_table(
        "solver_card_delivery_receipt",
        sa.Column("organization_id", uuid, nullable=False),
        sa.Column("project_id", uuid, nullable=False),
        sa.Column("classification", sa.String(64), nullable=False),
        sa.Column("receipt_id", uuid, nullable=False),
        sa.Column("delivery_identity", sa.CHAR(64), nullable=False),
        sa.Column("solver_card_id", uuid, nullable=False),
        sa.Column("solver_card_revision_id", uuid, nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("native_sha256", sa.CHAR(64), nullable=False),
        sa.Column("mapping_report_sha256", sa.CHAR(64), nullable=False),
        sa.Column("mapping_statuses", postgresql.JSONB(), nullable=False),
        sa.Column("source", postgresql.JSONB(), nullable=False),
        sa.Column("target", postgresql.JSONB(), nullable=False),
        sa.Column("outbox_event_id", uuid, nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recorded_by", uuid, nullable=False),
        sa.PrimaryKeyConstraint("organization_id", "project_id", "receipt_id"),
        sa.UniqueConstraint("organization_id", "project_id", "delivery_identity"),
        sa.UniqueConstraint("organization_id", "project_id", "solver_card_revision_id"),
        sa.CheckConstraint(
            "native_sha256 ~ '^[0-9a-f]{64}$' AND "
            "mapping_report_sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_solver_card_delivery_receipt_hashes",
        ),
        sa.CheckConstraint(
            "length(btrim(filename)) BETWEEN 1 AND 255 AND "
            "jsonb_typeof(mapping_statuses) = 'array' AND "
            "jsonb_typeof(source) = 'object' AND jsonb_typeof(target) = 'object'",
            name="ck_solver_card_delivery_receipt_evidence",
        ),
        sa.ForeignKeyConstraint(["recorded_by"], ["identity.principal.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            [
                "organization_id",
                "project_id",
                "classification",
                "solver_card_id",
                "solver_card_revision_id",
            ],
            [
                "exporting.neutral_solver_card_revision.organization_id",
                "exporting.neutral_solver_card_revision.project_id",
                "exporting.neutral_solver_card_revision.classification",
                "exporting.neutral_solver_card_revision.aggregate_id",
                "exporting.neutral_solver_card_revision.id",
            ],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "classification", "outbox_event_id"],
            [
                "events.outbox_event.organization_id",
                "events.outbox_event.project_id",
                "events.outbox_event.classification",
                "events.outbox_event.id",
            ],
            ondelete="RESTRICT",
        ), schema="exporting",
    )
    op.execute("ALTER TABLE exporting.solver_card_delivery_receipt ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE exporting.solver_card_delivery_receipt FORCE ROW LEVEL SECURITY")
    op.execute("""
      CREATE POLICY solver_card_delivery_receipt_select ON exporting.solver_card_delivery_receipt
      FOR SELECT USING (access_control.can_access_row(
        organization_id, project_id, classification, 'export.read'))
    """)
    op.execute("""
      CREATE POLICY solver_card_delivery_receipt_insert ON exporting.solver_card_delivery_receipt
      FOR INSERT WITH CHECK (recorded_by = access_control.current_principal_id()
        AND access_control.can_access_row(
          organization_id, project_id, classification, 'export.execute'))
    """)
    op.execute("""
      CREATE TRIGGER exporting_solver_card_delivery_receipt_immutable
      BEFORE UPDATE OR DELETE ON exporting.solver_card_delivery_receipt
      FOR EACH ROW EXECUTE FUNCTION revisioning.reject_immutable_row_mutation()
    """)


def downgrade() -> None:
    op.drop_table("solver_card_delivery_receipt", schema="exporting")

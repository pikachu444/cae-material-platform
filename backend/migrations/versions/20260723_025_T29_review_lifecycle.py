"""T-29 immutable review requests, decisions, and lifecycle transition guards."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260723_025_t29"
down_revision: str | None = "20260722_024_t28"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ZERO = "'00000000-0000-0000-0000-000000000000'::uuid"


def _secure(table: str, *, allow_update: bool = False) -> None:
    op.execute(
        f"""
        CREATE TRIGGER {table}_immutable
        BEFORE UPDATE OR DELETE ON governance.{table}
        FOR EACH ROW EXECUTE FUNCTION revisioning.reject_immutable_row_mutation()
        """
    )
    op.execute(f"ALTER TABLE governance.{table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE governance.{table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY {table}_authorized_select
        ON governance.{table}
        FOR SELECT
        USING (
          access_control.can_access_row(
            organization_id, project_id, classification, 'governance.read'
          )
        )
        """
    )
    op.execute(
        f"""
        CREATE POLICY {table}_authorized_insert
        ON governance.{table}
        FOR INSERT
        WITH CHECK (
          access_control.can_access_row(
            organization_id, project_id, classification, 'governance.write'
          )
        )
        """
    )


def upgrade() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    op.create_table(
        "review_request",
        sa.Column("id", uuid, nullable=False),
        sa.Column("organization_id", uuid, nullable=False),
        sa.Column("project_id", uuid, nullable=False),
        sa.Column("classification", sa.String(length=64), nullable=False),
        sa.Column("aggregate_type", sa.String(length=100), nullable=False),
        sa.Column("aggregate_id", uuid, nullable=False),
        sa.Column("revision_id", uuid, nullable=False),
        sa.Column("manifest_sha256", sa.CHAR(length=64, collation="C"), nullable=False),
        sa.Column("required_role", sa.String(length=100), nullable=False),
        sa.Column("requested_by", uuid, nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("request_id", uuid, nullable=False),
        sa.Column("trace_id", sa.String(length=255), nullable=False),
        sa.CheckConstraint(
            "id <> " + _ZERO + " AND organization_id <> " + _ZERO + " AND project_id <> " + _ZERO,
            name="ck_review_request_nonzero_scope_ids",
        ),
        sa.CheckConstraint(
            "aggregate_id <> "
            + _ZERO
            + " AND revision_id <> "
            + _ZERO
            + " AND requested_by <> "
            + _ZERO,
            name="ck_review_request_nonzero_target_ids",
        ),
        sa.CheckConstraint(
            "request_id <> " + _ZERO,
            name="ck_review_request_nonzero_request_id",
        ),
        sa.CheckConstraint(
            "classification ~ '^[a-z][a-z0-9_.-]{0,63}$'",
            name="ck_review_request_classification",
        ),
        sa.CheckConstraint(
            "aggregate_type ~ '^[a-z][a-z0-9_.-]{0,99}$'",
            name="ck_review_request_aggregate_type",
        ),
        sa.CheckConstraint(
            "manifest_sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_review_request_manifest_sha256",
        ),
        sa.CheckConstraint(
            "required_role = 'domain_reviewer'",
            name="ck_review_request_required_role",
        ),
        sa.CheckConstraint(
            "length(btrim(reason)) BETWEEN 1 AND 2000",
            name="ck_review_request_reason",
        ),
        sa.CheckConstraint(
            "length(btrim(trace_id)) BETWEEN 1 AND 255",
            name="ck_review_request_trace",
        ),
        sa.PrimaryKeyConstraint("organization_id", "project_id", "id", name="pk_review_request"),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "aggregate_type",
            "aggregate_id",
            "revision_id",
            name="uq_review_request_revision",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "id",
            "aggregate_type",
            "aggregate_id",
            "revision_id",
            "manifest_sha256",
            name="uq_review_request_manifest_reference",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "aggregate_type", "aggregate_id", "revision_id"],
            [
                "governance.lifecycle_projection.organization_id",
                "governance.lifecycle_projection.project_id",
                "governance.lifecycle_projection.aggregate_type",
                "governance.lifecycle_projection.aggregate_id",
                "governance.lifecycle_projection.revision_id",
            ],
            name="fk_review_request_lifecycle_projection",
            ondelete="RESTRICT",
        ),
        schema="governance",
    )
    op.create_index(
        "ix_review_request_tenant_state_lookup",
        "review_request",
        ["organization_id", "project_id", "classification", "requested_at"],
        schema="governance",
    )
    op.create_index(
        "ix_review_request_target_lookup",
        "review_request",
        ["organization_id", "project_id", "aggregate_type", "aggregate_id", "revision_id"],
        schema="governance",
    )

    op.create_table(
        "review_decision",
        sa.Column("id", uuid, nullable=False),
        sa.Column("organization_id", uuid, nullable=False),
        sa.Column("project_id", uuid, nullable=False),
        sa.Column("classification", sa.String(length=64), nullable=False),
        sa.Column("review_request_id", uuid, nullable=False),
        sa.Column("aggregate_type", sa.String(length=100), nullable=False),
        sa.Column("aggregate_id", uuid, nullable=False),
        sa.Column("revision_id", uuid, nullable=False),
        sa.Column("manifest_sha256", sa.CHAR(length=64, collation="C"), nullable=False),
        sa.Column("decision", sa.String(length=64), nullable=False),
        sa.Column("decided_by", uuid, nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("request_id", uuid, nullable=False),
        sa.Column("trace_id", sa.String(length=255), nullable=False),
        sa.CheckConstraint(
            "id <> " + _ZERO + " AND review_request_id <> " + _ZERO + " AND decided_by <> " + _ZERO,
            name="ck_review_decision_nonzero_ids",
        ),
        sa.CheckConstraint(
            "organization_id <> "
            + _ZERO
            + " AND project_id <> "
            + _ZERO
            + " AND request_id <> "
            + _ZERO,
            name="ck_review_decision_nonzero_scope_ids",
        ),
        sa.CheckConstraint(
            "aggregate_id <> " + _ZERO + " AND revision_id <> " + _ZERO,
            name="ck_review_decision_nonzero_target_ids",
        ),
        sa.CheckConstraint(
            "classification ~ '^[a-z][a-z0-9_.-]{0,63}$'",
            name="ck_review_decision_classification",
        ),
        sa.CheckConstraint(
            "aggregate_type ~ '^[a-z][a-z0-9_.-]{0,99}$'",
            name="ck_review_decision_aggregate_type",
        ),
        sa.CheckConstraint(
            "manifest_sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_review_decision_manifest_sha256",
        ),
        sa.CheckConstraint(
            "decision IN ('approved', 'changes_requested')",
            name="ck_review_decision_kind",
        ),
        sa.CheckConstraint(
            "length(btrim(reason)) BETWEEN 1 AND 2000",
            name="ck_review_decision_reason",
        ),
        sa.CheckConstraint(
            "length(btrim(trace_id)) BETWEEN 1 AND 255",
            name="ck_review_decision_trace",
        ),
        sa.PrimaryKeyConstraint("organization_id", "project_id", "id", name="pk_review_decision"),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "review_request_id",
            name="uq_review_decision_request",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "review_request_id"],
            [
                "governance.review_request.organization_id",
                "governance.review_request.project_id",
                "governance.review_request.id",
            ],
            name="fk_review_decision_request",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            [
                "organization_id",
                "project_id",
                "review_request_id",
                "aggregate_type",
                "aggregate_id",
                "revision_id",
                "manifest_sha256",
            ],
            [
                "governance.review_request.organization_id",
                "governance.review_request.project_id",
                "governance.review_request.id",
                "governance.review_request.aggregate_type",
                "governance.review_request.aggregate_id",
                "governance.review_request.revision_id",
                "governance.review_request.manifest_sha256",
            ],
            name="fk_review_decision_exact_manifest",
            ondelete="RESTRICT",
        ),
        schema="governance",
    )
    op.create_index(
        "ix_review_decision_tenant_request",
        "review_decision",
        ["organization_id", "project_id", "review_request_id", "decided_at"],
        schema="governance",
    )
    _secure("review_request")
    _secure("review_decision")


def downgrade() -> None:
    for table in ("review_decision", "review_request"):
        op.execute(
            f"DROP TRIGGER {table}_immutable ON governance.{table}"
        )
        op.execute(f"DROP POLICY {table}_authorized_insert ON governance.{table}")
        op.execute(f"DROP POLICY {table}_authorized_select ON governance.{table}")
    op.drop_index(
        "ix_review_decision_tenant_request",
        table_name="review_decision",
        schema="governance",
    )
    op.drop_table("review_decision", schema="governance")
    op.drop_index(
        "ix_review_request_target_lookup",
        table_name="review_request",
        schema="governance",
    )
    op.drop_index(
        "ix_review_request_tenant_state_lookup",
        table_name="review_request",
        schema="governance",
    )
    op.drop_table("review_request", schema="governance")

"""T-06 aggregate revision kernel PostgreSQL primitives.

Traceability: T-06, FR-CAT-001, FR-DAT-001/006, FR-API-001,
NFR-INT-001, NFR-SEC-003/006, ADR-001/002/003.

This migration intentionally does not create a generic revision/content table.  Every bounded
module creates an explicit stable-identity and typed-revision table pair.  The shared migration
owns only mutation guards, tenant-context helpers, and lifecycle event/projection storage.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260711_001_t06"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _create_revision_functions() -> None:
    op.execute(
        """
        CREATE FUNCTION revisioning.current_organization_id()
        RETURNS uuid
        LANGUAGE sql
        STABLE
        PARALLEL SAFE
        AS $$
          SELECT NULLIF(current_setting('cmp.organization_id', true), '')::uuid
        $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION revisioning.current_project_id()
        RETURNS uuid
        LANGUAGE sql
        STABLE
        PARALLEL SAFE
        AS $$
          SELECT NULLIF(current_setting('cmp.project_id', true), '')::uuid
        $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION revisioning.reject_immutable_row_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
          RAISE EXCEPTION USING
            ERRCODE = '55000',
            MESSAGE = format('%I.%I rows are immutable', TG_TABLE_SCHEMA, TG_TABLE_NAME);
        END
        $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION revisioning.reject_row_deletion()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
          RAISE EXCEPTION USING
            ERRCODE = '55000',
            MESSAGE = format('%I.%I rows cannot be deleted', TG_TABLE_SCHEMA, TG_TABLE_NAME);
        END
        $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION revisioning.guard_identity_head_update()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
          IF TG_OP = 'DELETE' THEN
            RAISE EXCEPTION USING
              ERRCODE = '55000',
              MESSAGE = format(
                '%I.%I identities cannot be deleted',
                TG_TABLE_SCHEMA,
                TG_TABLE_NAME
              );
          END IF;
          IF (to_jsonb(NEW) - ARRAY['current_revision_id', 'updated_at'])
             IS DISTINCT FROM
             (to_jsonb(OLD) - ARRAY['current_revision_id', 'updated_at']) THEN
            RAISE EXCEPTION USING
              ERRCODE = '55000',
              MESSAGE = format(
                '%I.%I updates may change only current_revision_id and updated_at',
                TG_TABLE_SCHEMA,
                TG_TABLE_NAME
              );
          END IF;
          RETURN NEW;
        END
        $$
        """
    )


def _create_lifecycle_tables() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    op.create_table(
        "lifecycle_event",
        sa.Column("id", uuid, nullable=False),
        sa.Column("organization_id", uuid, nullable=False),
        sa.Column("project_id", uuid, nullable=False),
        sa.Column("classification", sa.String(length=64), nullable=False),
        sa.Column("aggregate_type", sa.String(length=100), nullable=False),
        sa.Column("aggregate_id", uuid, nullable=False),
        sa.Column("revision_id", uuid, nullable=False),
        sa.Column("sequence_no", sa.BigInteger(), nullable=False),
        sa.Column("from_state", sa.String(length=64), nullable=True),
        sa.Column("to_state", sa.String(length=64), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor_id", uuid, nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("request_id", uuid, nullable=False),
        sa.Column("trace_id", sa.String(length=255), nullable=False),
        sa.CheckConstraint("sequence_no > 0", name="ck_lifecycle_event_sequence_positive"),
        sa.CheckConstraint(
            "aggregate_type ~ '^[a-z][a-z0-9_.-]{0,99}$'",
            name="ck_lifecycle_event_aggregate_type",
        ),
        sa.CheckConstraint(
            "classification ~ '^[a-z][a-z0-9_.-]{0,63}$'",
            name="ck_lifecycle_event_classification",
        ),
        sa.CheckConstraint(
            "to_state ~ '^[a-z][a-z0-9_.-]{0,63}$'",
            name="ck_lifecycle_event_to_state",
        ),
        sa.CheckConstraint(
            "from_state IS NULL OR from_state ~ '^[a-z][a-z0-9_.-]{0,63}$'",
            name="ck_lifecycle_event_from_state",
        ),
        sa.CheckConstraint("length(btrim(reason)) > 0", name="ck_lifecycle_event_reason"),
        sa.PrimaryKeyConstraint("id", name="pk_lifecycle_event"),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "classification",
            "aggregate_type",
            "aggregate_id",
            "revision_id",
            "id",
            name="uq_lifecycle_event_scoped_reference",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "aggregate_type",
            "aggregate_id",
            "revision_id",
            "sequence_no",
            name="uq_lifecycle_event_sequence",
        ),
        schema="governance",
    )
    op.create_index(
        "ix_lifecycle_event_tenant_aggregate",
        "lifecycle_event",
        [
            "organization_id",
            "project_id",
            "aggregate_type",
            "aggregate_id",
            "revision_id",
            "occurred_at",
        ],
        schema="governance",
    )

    op.create_table(
        "lifecycle_projection",
        sa.Column("organization_id", uuid, nullable=False),
        sa.Column("project_id", uuid, nullable=False),
        sa.Column("classification", sa.String(length=64), nullable=False),
        sa.Column("aggregate_type", sa.String(length=100), nullable=False),
        sa.Column("aggregate_id", uuid, nullable=False),
        sa.Column("revision_id", uuid, nullable=False),
        sa.Column("lifecycle_state", sa.String(length=64), nullable=False),
        sa.Column("sequence_no", sa.BigInteger(), nullable=False),
        sa.Column("last_event_id", uuid, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "sequence_no > 0", name="ck_lifecycle_projection_sequence_positive"
        ),
        sa.CheckConstraint(
            "lifecycle_state ~ '^[a-z][a-z0-9_.-]{0,63}$'",
            name="ck_lifecycle_projection_state",
        ),
        sa.PrimaryKeyConstraint(
            "organization_id",
            "project_id",
            "aggregate_type",
            "aggregate_id",
            "revision_id",
            name="pk_lifecycle_projection",
        ),
        sa.ForeignKeyConstraint(
            [
                "organization_id",
                "project_id",
                "classification",
                "aggregate_type",
                "aggregate_id",
                "revision_id",
                "last_event_id",
            ],
            [
                "governance.lifecycle_event.organization_id",
                "governance.lifecycle_event.project_id",
                "governance.lifecycle_event.classification",
                "governance.lifecycle_event.aggregate_type",
                "governance.lifecycle_event.aggregate_id",
                "governance.lifecycle_event.revision_id",
                "governance.lifecycle_event.id",
            ],
            name="fk_lifecycle_projection_last_event",
            ondelete="RESTRICT",
        ),
        schema="governance",
    )
    op.create_index(
        "ix_lifecycle_projection_tenant_state",
        "lifecycle_projection",
        ["organization_id", "project_id", "lifecycle_state", "aggregate_type"],
        schema="governance",
    )


def _secure_lifecycle_tables() -> None:
    op.execute(
        """
        CREATE TRIGGER lifecycle_event_immutable
        BEFORE UPDATE OR DELETE ON governance.lifecycle_event
        FOR EACH ROW EXECUTE FUNCTION revisioning.reject_immutable_row_mutation()
        """
    )
    op.execute(
        """
        CREATE TRIGGER lifecycle_projection_no_delete
        BEFORE DELETE ON governance.lifecycle_projection
        FOR EACH ROW EXECUTE FUNCTION revisioning.reject_row_deletion()
        """
    )
    for table in ("lifecycle_event", "lifecycle_projection"):
        op.execute(f"ALTER TABLE governance.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE governance.{table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY {table}_tenant_isolation
            ON governance.{table}
            USING (
              organization_id = revisioning.current_organization_id()
              AND project_id = revisioning.current_project_id()
            )
            WITH CHECK (
              organization_id = revisioning.current_organization_id()
              AND project_id = revisioning.current_project_id()
            )
            """
        )


def upgrade() -> None:
    op.execute("CREATE SCHEMA revisioning")
    op.execute("CREATE SCHEMA governance")
    _create_revision_functions()
    _create_lifecycle_tables()
    _secure_lifecycle_tables()


def downgrade() -> None:
    op.drop_index(
        "ix_lifecycle_projection_tenant_state",
        table_name="lifecycle_projection",
        schema="governance",
    )
    op.drop_table("lifecycle_projection", schema="governance")
    op.drop_index(
        "ix_lifecycle_event_tenant_aggregate",
        table_name="lifecycle_event",
        schema="governance",
    )
    op.drop_table("lifecycle_event", schema="governance")
    op.execute("DROP FUNCTION revisioning.guard_identity_head_update()")
    op.execute("DROP FUNCTION revisioning.reject_row_deletion()")
    op.execute("DROP FUNCTION revisioning.reject_immutable_row_mutation()")
    op.execute("DROP FUNCTION revisioning.current_project_id()")
    op.execute("DROP FUNCTION revisioning.current_organization_id()")
    op.execute("DROP SCHEMA governance")
    op.execute("DROP SCHEMA revisioning")

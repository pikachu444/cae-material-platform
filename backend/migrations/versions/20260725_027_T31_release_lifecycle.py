"""T-31 append-only Release lifecycle, usage, and downstream impact facts."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260725_027_t31"
down_revision: str | None = "20260724_026_t30"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ZERO = "'00000000-0000-0000-0000-000000000000'::uuid"


def _secure_append_only(table: str, *, insert_permission: str = "release.publish") -> None:
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
            organization_id, project_id, classification, 'release.read'
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
            organization_id, project_id, classification, '{insert_permission}'
          )
        )
        """
    )


def upgrade() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    op.create_table(
        "release_lifecycle_projection",
        sa.Column("release_id", uuid, nullable=False),
        sa.Column("organization_id", uuid, nullable=False),
        sa.Column("project_id", uuid, nullable=False),
        sa.Column("classification", sa.String(64), nullable=False),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("sequence_no", sa.Integer(), nullable=False),
        sa.Column("last_event_id", uuid, nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_by", uuid, nullable=False),
        sa.Column("request_id", uuid, nullable=False),
        sa.Column("trace_id", sa.String(255), nullable=False),
        sa.CheckConstraint(
            "release_id <> " + _ZERO + " AND organization_id <> " + _ZERO
            + " AND project_id <> " + _ZERO + " AND updated_by <> " + _ZERO
            + " AND request_id <> " + _ZERO,
            name="ck_release_lifecycle_projection_nonzero_ids",
        ),
        sa.CheckConstraint(
            "classification ~ '^[a-z][a-z0-9_.-]{0,63}$'",
            name="ck_release_lifecycle_projection_classification",
        ),
        sa.CheckConstraint(
            "state IN ('released', 'superseded', 'withdrawn') AND sequence_no >= 0",
            name="ck_release_lifecycle_projection_state",
        ),
        sa.CheckConstraint(
            "length(btrim(trace_id)) BETWEEN 1 AND 255",
            name="ck_release_lifecycle_projection_trace",
        ),
        sa.PrimaryKeyConstraint(
            "organization_id", "project_id", "release_id",
            name="pk_release_lifecycle_projection",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "release_id"],
            [
                "governance.release.organization_id",
                "governance.release.project_id",
                "governance.release.id",
            ],
            name="fk_release_lifecycle_projection_release",
            ondelete="RESTRICT",
        ),
        schema="governance",
    )
    op.create_index(
        "ix_release_lifecycle_projection_state",
        "release_lifecycle_projection",
        ["organization_id", "project_id", "classification", "state", "updated_at"],
        schema="governance",
    )

    op.create_table(
        "release_lifecycle_event",
        sa.Column("id", uuid, nullable=False),
        sa.Column("release_id", uuid, nullable=False),
        sa.Column("organization_id", uuid, nullable=False),
        sa.Column("project_id", uuid, nullable=False),
        sa.Column("classification", sa.String(64), nullable=False),
        sa.Column("sequence_no", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("from_state", sa.String(32), nullable=False),
        sa.Column("to_state", sa.String(32), nullable=False),
        sa.Column("successor_release_id", uuid, nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("occurred_by", uuid, nullable=False),
        sa.Column("request_id", uuid, nullable=False),
        sa.Column("trace_id", sa.String(255), nullable=False),
        sa.CheckConstraint(
            "id <> " + _ZERO + " AND release_id <> " + _ZERO
            + " AND organization_id <> " + _ZERO + " AND project_id <> " + _ZERO
            + " AND occurred_by <> " + _ZERO + " AND request_id <> " + _ZERO,
            name="ck_release_lifecycle_event_nonzero_ids",
        ),
        sa.CheckConstraint(
            "classification ~ '^[a-z][a-z0-9_.-]{0,63}$' AND sequence_no > 0",
            name="ck_release_lifecycle_event_identity",
        ),
        sa.CheckConstraint(
            "(kind = 'supersede' AND from_state = 'released' AND to_state = 'superseded'"
            " AND successor_release_id IS NOT NULL)"
            " OR (kind = 'withdraw' AND from_state = 'released' AND to_state = 'withdrawn'"
            " AND successor_release_id IS NULL)",
            name="ck_release_lifecycle_event_transition",
        ),
        sa.CheckConstraint(
            "length(btrim(reason)) BETWEEN 1 AND 2000"
            " AND length(btrim(trace_id)) BETWEEN 1 AND 255",
            name="ck_release_lifecycle_event_text",
        ),
        sa.PrimaryKeyConstraint(
            "organization_id", "project_id", "id",
            name="pk_release_lifecycle_event",
        ),
        sa.UniqueConstraint(
            "organization_id", "project_id", "release_id", "sequence_no",
            name="uq_release_lifecycle_event_sequence",
        ),
        sa.UniqueConstraint(
            "organization_id", "project_id", "release_id", "id",
            name="uq_release_lifecycle_event_scoped_id",
        ),
        sa.UniqueConstraint(
            "organization_id", "project_id", "successor_release_id",
            name="uq_release_lifecycle_event_successor",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "release_id"],
            [
                "governance.release.organization_id",
                "governance.release.project_id",
                "governance.release.id",
            ],
            name="fk_release_lifecycle_event_release",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "successor_release_id"],
            [
                "governance.release.organization_id",
                "governance.release.project_id",
                "governance.release.id",
            ],
            name="fk_release_lifecycle_event_successor",
            ondelete="RESTRICT",
        ),
        schema="governance",
    )
    op.create_foreign_key(
        "fk_release_lifecycle_projection_event",
        "release_lifecycle_projection",
        "release_lifecycle_event",
        ["organization_id", "project_id", "release_id", "last_event_id"],
        ["organization_id", "project_id", "release_id", "id"],
        source_schema="governance",
        referent_schema="governance",
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_release_lifecycle_event_release_history",
        "release_lifecycle_event",
        ["organization_id", "project_id", "release_id", "occurred_at"],
        schema="governance",
    )
    op.create_index(
        "ix_release_lifecycle_event_successor_lookup",
        "release_lifecycle_event",
        ["organization_id", "project_id", "successor_release_id"],
        schema="governance",
    )

    op.create_table(
        "release_usage",
        sa.Column("id", uuid, nullable=False),
        sa.Column("release_id", uuid, nullable=False),
        sa.Column("organization_id", uuid, nullable=False),
        sa.Column("project_id", uuid, nullable=False),
        sa.Column("classification", sa.String(64), nullable=False),
        sa.Column("usage_kind", sa.String(32), nullable=False),
        sa.Column("lifecycle_state", sa.String(32), nullable=False),
        sa.Column("used_by", uuid, nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("request_id", uuid, nullable=False),
        sa.Column("trace_id", sa.String(255), nullable=False),
        sa.CheckConstraint(
            "id <> " + _ZERO + " AND release_id <> " + _ZERO
            + " AND organization_id <> " + _ZERO + " AND project_id <> " + _ZERO
            + " AND used_by <> " + _ZERO + " AND request_id <> " + _ZERO,
            name="ck_release_usage_nonzero_ids",
        ),
        sa.CheckConstraint(
            "classification ~ '^[a-z][a-z0-9_.-]{0,63}$'"
            " AND usage_kind IN ('download', 'consume')"
            " AND lifecycle_state = 'released'",
            name="ck_release_usage_kind_state",
        ),
        sa.CheckConstraint(
            "length(btrim(reason)) BETWEEN 1 AND 2000"
            " AND length(btrim(trace_id)) BETWEEN 1 AND 255",
            name="ck_release_usage_text",
        ),
        sa.PrimaryKeyConstraint(
            "organization_id", "project_id", "id",
            name="pk_release_usage",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "release_id"],
            [
                "governance.release.organization_id",
                "governance.release.project_id",
                "governance.release.id",
            ],
            name="fk_release_usage_release",
            ondelete="RESTRICT",
        ),
        schema="governance",
    )
    op.create_index(
        "ix_release_usage_release_history",
        "release_usage",
        ["organization_id", "project_id", "release_id", "used_at"],
        schema="governance",
    )

    op.execute(
        """
        INSERT INTO governance.release_lifecycle_projection
          (release_id, organization_id, project_id, classification, state, sequence_no,
           last_event_id, updated_at, updated_by, request_id, trace_id)
        SELECT id, organization_id, project_id, classification, 'released', 0,
               NULL, created_at, created_by, request_id, trace_id
        FROM governance.release
        ON CONFLICT (organization_id, project_id, release_id) DO NOTHING
        """
    )
    op.execute(
        """
        CREATE FUNCTION governance.guard_release_lifecycle_projection_update()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
          IF OLD.state <> 'released' THEN
            RAISE EXCEPTION 'terminal Release lifecycle projection is immutable';
          END IF;
          IF NEW.state NOT IN ('superseded', 'withdrawn')
             OR NEW.sequence_no <> OLD.sequence_no + 1
             OR NEW.last_event_id IS NULL
             OR NOT EXISTS (
               SELECT 1
               FROM governance.release_lifecycle_event lifecycle_event
               WHERE lifecycle_event.organization_id = NEW.organization_id
                 AND lifecycle_event.project_id = NEW.project_id
                 AND lifecycle_event.release_id = NEW.release_id
                 AND lifecycle_event.id = NEW.last_event_id
                 AND lifecycle_event.sequence_no = NEW.sequence_no
                 AND lifecycle_event.from_state = 'released'
                 AND lifecycle_event.to_state = NEW.state
             ) THEN
            RAISE EXCEPTION 'invalid Release lifecycle transition projection';
          END IF;
          RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER release_lifecycle_projection_transition_guard
        BEFORE UPDATE ON governance.release_lifecycle_projection
        FOR EACH ROW EXECUTE FUNCTION governance.guard_release_lifecycle_projection_update()
        """
    )
    op.execute("ALTER TABLE governance.release_lifecycle_projection ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE governance.release_lifecycle_projection FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY release_lifecycle_projection_authorized_select
        ON governance.release_lifecycle_projection FOR SELECT
        USING (access_control.can_access_row(
          organization_id, project_id, classification, 'release.read'))
        """
    )
    op.execute(
        """
        CREATE POLICY release_lifecycle_projection_authorized_insert
        ON governance.release_lifecycle_projection FOR INSERT
        WITH CHECK (access_control.can_access_row(
          organization_id, project_id, classification, 'release.publish'))
        """
    )
    op.execute(
        """
        CREATE POLICY release_lifecycle_projection_authorized_update
        ON governance.release_lifecycle_projection FOR UPDATE
        USING (access_control.can_access_row(
          organization_id, project_id, classification, 'release.publish'))
        WITH CHECK (access_control.can_access_row(
          organization_id, project_id, classification, 'release.publish'))
        """
    )
    _secure_append_only("release_lifecycle_event")
    _secure_append_only("release_usage", insert_permission="release.read")


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER release_lifecycle_projection_transition_guard "
        "ON governance.release_lifecycle_projection"
    )
    op.drop_constraint(
        "fk_release_lifecycle_projection_event",
        "release_lifecycle_projection",
        schema="governance",
        type_="foreignkey",
    )
    op.execute("DROP FUNCTION governance.guard_release_lifecycle_projection_update()")
    op.execute(
        "DROP POLICY release_lifecycle_projection_authorized_update "
        "ON governance.release_lifecycle_projection"
    )
    op.execute(
        "DROP POLICY release_lifecycle_projection_authorized_insert "
        "ON governance.release_lifecycle_projection"
    )
    op.execute(
        "DROP POLICY release_lifecycle_projection_authorized_select "
        "ON governance.release_lifecycle_projection"
    )
    op.execute("ALTER TABLE governance.release_lifecycle_projection NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE governance.release_lifecycle_projection DISABLE ROW LEVEL SECURITY")
    for table in ("release_usage", "release_lifecycle_event"):
        op.execute(f"DROP TRIGGER {table}_immutable ON governance.{table}")
        op.execute(f"DROP POLICY {table}_authorized_insert ON governance.{table}")
        op.execute(f"DROP POLICY {table}_authorized_select ON governance.{table}")
    op.drop_index(
        "ix_release_usage_release_history",
        table_name="release_usage",
        schema="governance",
    )
    op.drop_table("release_usage", schema="governance")
    op.drop_index(
        "ix_release_lifecycle_event_successor_lookup",
        table_name="release_lifecycle_event",
        schema="governance",
    )
    op.drop_index(
        "ix_release_lifecycle_event_release_history",
        table_name="release_lifecycle_event",
        schema="governance",
    )
    op.drop_table("release_lifecycle_event", schema="governance")
    op.drop_index(
        "ix_release_lifecycle_projection_state",
        table_name="release_lifecycle_projection",
        schema="governance",
    )
    op.drop_table("release_lifecycle_projection", schema="governance")

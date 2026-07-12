"""T-16 transactional CloudEvent outbox, delivery lease, and consumer inbox.

Revision ID: 20260713_010_t16
Revises: 20260713_009_t14
Create Date: 2026-07-13
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260713_010_t16"
down_revision = "20260713_009_t14"
branch_labels = None
depends_on = None


def _scope_columns() -> list[sa.Column[object]]:
    uuid = postgresql.UUID(as_uuid=True)
    return [
        sa.Column("organization_id", uuid, nullable=False),
        sa.Column("project_id", uuid, nullable=False),
        sa.Column("classification", sa.String(length=64), nullable=False),
    ]


def upgrade() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    op.execute("CREATE SCHEMA events")
    op.create_table(
        "outbox_event",
        *_scope_columns(),
        sa.Column("id", uuid, nullable=False),
        sa.Column("aggregate_type", sa.String(length=100), nullable=False),
        sa.Column("aggregate_id", uuid, nullable=False),
        sa.Column("sequence_no", sa.BigInteger(), nullable=False),
        sa.Column("event_type", sa.String(length=200), nullable=False),
        sa.Column("source", sa.String(length=500), nullable=False),
        sa.Column("subject", sa.String(length=500), nullable=False),
        sa.Column("data_schema", sa.String(length=500), nullable=False),
        sa.Column("data", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("data_sha256", sa.CHAR(length=64), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recorded_by", uuid, nullable=False),
        sa.Column("request_id", uuid, nullable=False),
        sa.Column("trace_id", sa.String(length=255), nullable=False),
        sa.Column("deduplication_key", sa.String(length=255), nullable=False),
        sa.CheckConstraint("sequence_no >= 1", name="ck_outbox_event_sequence"),
        sa.CheckConstraint(
            "aggregate_type ~ '^[a-z][a-z0-9]*(\\.[a-z][a-z0-9_-]*)+$'",
            name="ck_outbox_event_aggregate_type",
        ),
        sa.CheckConstraint(
            "event_type ~ '^[a-z][a-z0-9]*(\\.[a-z0-9_-]+)+\\.v[1-9][0-9]*$'",
            name="ck_outbox_event_type",
        ),
        sa.CheckConstraint("jsonb_typeof(data) = 'object'", name="ck_outbox_event_data_object"),
        sa.CheckConstraint("data_sha256 ~ '^[0-9a-f]{64}$'", name="ck_outbox_event_data_sha256"),
        sa.CheckConstraint(
            "length(btrim(source)) BETWEEN 1 AND 500 AND source = btrim(source)",
            name="ck_outbox_event_source",
        ),
        sa.CheckConstraint(
            "length(btrim(subject)) BETWEEN 1 AND 500 AND subject = btrim(subject)",
            name="ck_outbox_event_subject",
        ),
        sa.CheckConstraint(
            "length(btrim(data_schema)) BETWEEN 1 AND 500 AND data_schema = btrim(data_schema)",
            name="ck_outbox_event_data_schema",
        ),
        sa.CheckConstraint(
            "length(btrim(deduplication_key)) BETWEEN 1 AND 255 "
            "AND deduplication_key = btrim(deduplication_key)",
            name="ck_outbox_event_deduplication_key",
        ),
        sa.CheckConstraint("recorded_at >= occurred_at", name="ck_outbox_event_recording_order"),
        sa.PrimaryKeyConstraint(
            "organization_id", "project_id", "id", name="pk_events_outbox_event"
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "classification",
            "id",
            name="uq_events_outbox_event_classified",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "aggregate_type",
            "aggregate_id",
            "sequence_no",
            name="uq_events_outbox_aggregate_sequence",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "deduplication_key",
            name="uq_events_outbox_deduplication",
        ),
        sa.ForeignKeyConstraint(
            ["recorded_by"],
            ["identity.principal.id"],
            name="fk_events_outbox_recorded_by",
            ondelete="RESTRICT",
        ),
        schema="events",
    )
    op.create_index(
        "ix_events_outbox_type_time",
        "outbox_event",
        ["organization_id", "project_id", "event_type", "occurred_at", "id"],
        schema="events",
    )

    op.create_table(
        "outbox_delivery",
        *_scope_columns(),
        sa.Column("event_id", uuid, nullable=False),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lease_token", uuid, nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_failure_code", sa.String(length=100), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "state IN ('pending', 'claimed', 'published', 'poison')",
            name="ck_outbox_delivery_state",
        ),
        sa.CheckConstraint("attempt_count >= 0", name="ck_outbox_delivery_attempt_count"),
        sa.CheckConstraint(
            "last_failure_code IS NULL OR last_failure_code ~ '^[a-z][a-z0-9_.-]{0,99}$'",
            name="ck_outbox_delivery_failure_code",
        ),
        sa.CheckConstraint(
            "(state = 'claimed') = (lease_token IS NOT NULL AND lease_expires_at IS NOT NULL)",
            name="ck_outbox_delivery_lease_state",
        ),
        sa.CheckConstraint(
            "(state = 'published') = (published_at IS NOT NULL)",
            name="ck_outbox_delivery_published_state",
        ),
        sa.CheckConstraint(
            "state <> 'poison' OR last_failure_code IS NOT NULL",
            name="ck_outbox_delivery_poison_failure",
        ),
        sa.PrimaryKeyConstraint(
            "organization_id", "project_id", "event_id", name="pk_events_outbox_delivery"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "classification", "event_id"],
            [
                "events.outbox_event.organization_id",
                "events.outbox_event.project_id",
                "events.outbox_event.classification",
                "events.outbox_event.id",
            ],
            name="fk_events_outbox_delivery_event",
            ondelete="RESTRICT",
        ),
        schema="events",
    )
    op.create_index(
        "ix_events_outbox_delivery_claim",
        "outbox_delivery",
        ["organization_id", "project_id", "state", "available_at", "event_id"],
        schema="events",
    )

    op.create_table(
        "consumer_inbox",
        *_scope_columns(),
        sa.Column("consumer_name", sa.String(length=200), nullable=False),
        sa.Column("event_id", uuid, nullable=False),
        sa.Column("event_type", sa.String(length=200), nullable=False),
        sa.Column("data_sha256", sa.CHAR(length=64), nullable=False),
        sa.Column("outcome", sa.String(length=16), nullable=False),
        sa.Column("side_effect_key", sa.String(length=255), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_by", uuid, nullable=False),
        sa.Column("trace_id", sa.String(length=255), nullable=False),
        sa.CheckConstraint(
            "consumer_name ~ '^[a-z][a-z0-9]*(\\.[a-z0-9_-]+)+$'",
            name="ck_consumer_inbox_name",
        ),
        sa.CheckConstraint(
            "event_type ~ '^[a-z][a-z0-9]*(\\.[a-z0-9_-]+)+\\.v[1-9][0-9]*$'",
            name="ck_consumer_inbox_event_type",
        ),
        sa.CheckConstraint("data_sha256 ~ '^[0-9a-f]{64}$'", name="ck_consumer_inbox_data_sha256"),
        sa.CheckConstraint("outcome IN ('completed', 'ignored')", name="ck_consumer_inbox_outcome"),
        sa.CheckConstraint(
            "side_effect_key IS NULL OR (length(btrim(side_effect_key)) BETWEEN 1 AND 255 "
            "AND side_effect_key = btrim(side_effect_key))",
            name="ck_consumer_inbox_side_effect_key",
        ),
        sa.CheckConstraint("processed_at >= received_at", name="ck_consumer_inbox_time_order"),
        sa.PrimaryKeyConstraint(
            "organization_id",
            "project_id",
            "consumer_name",
            "event_id",
            name="pk_events_consumer_inbox",
        ),
        sa.ForeignKeyConstraint(
            ["processed_by"],
            ["identity.principal.id"],
            name="fk_events_consumer_inbox_processed_by",
            ondelete="RESTRICT",
        ),
        schema="events",
    )

    op.execute(
        """
        CREATE TRIGGER events_outbox_event_immutable
        BEFORE UPDATE OR DELETE ON events.outbox_event
        FOR EACH ROW EXECUTE FUNCTION revisioning.reject_immutable_row_mutation()
        """
    )
    op.execute(
        """
        CREATE TRIGGER events_consumer_inbox_immutable
        BEFORE UPDATE OR DELETE ON events.consumer_inbox
        FOR EACH ROW EXECUTE FUNCTION revisioning.reject_immutable_row_mutation()
        """
    )
    op.execute(
        """
        CREATE FUNCTION events.guard_delivery_mutation()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF TG_OP = 'DELETE' THEN
            RAISE EXCEPTION USING ERRCODE = '55000',
              MESSAGE = 'outbox delivery history cannot be deleted';
          END IF;
          IF (NEW.organization_id, NEW.project_id, NEW.classification, NEW.event_id)
             IS DISTINCT FROM
             (OLD.organization_id, OLD.project_id, OLD.classification, OLD.event_id) THEN
            RAISE EXCEPTION USING ERRCODE = '55000',
              MESSAGE = 'outbox delivery identity is immutable';
          END IF;
          IF OLD.state = 'published' OR OLD.state = 'poison' THEN
            RAISE EXCEPTION USING ERRCODE = '55000',
              MESSAGE = 'terminal outbox delivery is immutable';
          END IF;
          IF OLD.state = 'pending' AND NEW.state <> 'claimed' THEN
            RAISE EXCEPTION USING ERRCODE = '23514',
              MESSAGE = 'pending delivery may only be claimed';
          END IF;
          IF OLD.state = 'claimed'
             AND NEW.state NOT IN ('claimed', 'pending', 'published', 'poison') THEN
            RAISE EXCEPTION USING ERRCODE = '23514',
              MESSAGE = 'invalid claimed delivery transition';
          END IF;
          IF NEW.attempt_count < OLD.attempt_count THEN
            RAISE EXCEPTION USING ERRCODE = '23514',
              MESSAGE = 'outbox delivery attempts are monotonic';
          END IF;
          RETURN NEW;
        END $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER events_outbox_delivery_guard
        BEFORE UPDATE OR DELETE ON events.outbox_delivery
        FOR EACH ROW EXECUTE FUNCTION events.guard_delivery_mutation()
        """
    )

    for table in ("outbox_event", "outbox_delivery", "consumer_inbox"):
        op.execute(f"ALTER TABLE events.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE events.{table} FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY outbox_event_select ON events.outbox_event FOR SELECT USING (
          access_control.can_access_row(
            organization_id, project_id, classification, 'events.dispatch'
          ) OR access_control.can_access_row(
            organization_id, project_id, classification, 'events.consume'
          ) OR access_control.can_access_row(
            organization_id, project_id, classification, 'events.publish'
          )
        )
        """
    )
    op.execute(
        """
        CREATE POLICY outbox_event_insert ON events.outbox_event FOR INSERT WITH CHECK (
          recorded_by = access_control.current_principal_id()
          AND access_control.can_access_row(
            organization_id, project_id, classification, 'events.publish'
          )
        )
        """
    )
    op.execute(
        """
        CREATE POLICY outbox_delivery_select ON events.outbox_delivery FOR SELECT USING (
          access_control.can_access_row(
            organization_id, project_id, classification, 'events.dispatch'
          )
        )
        """
    )
    op.execute(
        """
        CREATE POLICY outbox_delivery_insert ON events.outbox_delivery FOR INSERT WITH CHECK (
          access_control.can_access_row(
            organization_id, project_id, classification, 'events.publish'
          )
        )
        """
    )
    op.execute(
        """
        CREATE POLICY outbox_delivery_update ON events.outbox_delivery FOR UPDATE USING (
          access_control.can_access_row(
            organization_id, project_id, classification, 'events.dispatch'
          )
        ) WITH CHECK (
          access_control.can_access_row(
            organization_id, project_id, classification, 'events.dispatch'
          )
        )
        """
    )
    op.execute(
        """
        CREATE POLICY consumer_inbox_select ON events.consumer_inbox FOR SELECT USING (
          access_control.can_access_row(
            organization_id, project_id, classification, 'events.consume'
          )
        )
        """
    )
    op.execute(
        """
        CREATE POLICY consumer_inbox_insert ON events.consumer_inbox FOR INSERT WITH CHECK (
          processed_by = access_control.current_principal_id()
          AND access_control.can_access_row(
            organization_id, project_id, classification, 'events.consume'
          )
        )
        """
    )


def downgrade() -> None:
    op.drop_table("consumer_inbox", schema="events")
    op.drop_table("outbox_delivery", schema="events")
    op.drop_table("outbox_event", schema="events")
    op.execute("DROP FUNCTION events.guard_delivery_mutation()")
    op.execute("DROP SCHEMA events")

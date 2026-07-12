"""T-05 project-scoped append-only audit chain and periodic segment roots.

Traceability: T-05, NFR-AUD-001/002, NFR-SEC-003/006, ADR-001/002.
The schema contains no generic attribute/value or raw command payload storage.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260713_012_t05"
down_revision: str | None = "20260713_011_t16"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_GENESIS_HASH = "0" * 64


def _create_tables() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    op.create_table(
        "event",
        sa.Column("id", uuid, nullable=False),
        sa.Column("organization_id", uuid, nullable=False),
        sa.Column("project_id", uuid, nullable=False),
        sa.Column("sequence_no", sa.BigInteger(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor_type", sa.String(length=16), nullable=False),
        sa.Column("actor_id", uuid, nullable=False),
        sa.Column("action", sa.String(length=150), nullable=False),
        sa.Column("target_type", sa.String(length=150), nullable=False),
        sa.Column("target_id", uuid, nullable=True),
        sa.Column("outcome", sa.String(length=16), nullable=False),
        sa.Column("request_id", uuid, nullable=False),
        sa.Column("trace_id", sa.String(length=255), nullable=False),
        sa.Column("ip_or_client", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("previous_hash", sa.CHAR(length=64, collation="C"), nullable=False),
        sa.Column("event_hash", sa.CHAR(length=64, collation="C"), nullable=False),
        sa.CheckConstraint("sequence_no > 0", name="ck_audit_event_sequence_positive"),
        sa.CheckConstraint(
            "actor_type IN ('user', 'service')", name="ck_audit_event_actor_type"
        ),
        sa.CheckConstraint(
            "action ~ '^[a-z][a-z0-9_-]*(\\.[a-z0-9_-]+)+$'",
            name="ck_audit_event_action",
        ),
        sa.CheckConstraint(
            "target_type ~ '^[a-z][a-z0-9_.-]{0,149}$'",
            name="ck_audit_event_target_type",
        ),
        sa.CheckConstraint(
            "outcome IN ('success', 'failure', 'denied')",
            name="ck_audit_event_outcome",
        ),
        sa.CheckConstraint(
            "ip_or_client = 'policy-redacted'", name="ck_audit_event_client_redacted"
        ),
        sa.CheckConstraint(
            "length(btrim(trace_id)) BETWEEN 1 AND 255",
            name="ck_audit_event_trace_id",
        ),
        sa.CheckConstraint(
            "length(btrim(reason)) BETWEEN 1 AND 2000",
            name="ck_audit_event_reason",
        ),
        sa.CheckConstraint(
            "previous_hash ~ '^[0-9a-f]{64}$' AND event_hash ~ '^[0-9a-f]{64}$'",
            name="ck_audit_event_hashes",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_audit_event"),
        sa.ForeignKeyConstraint(
            ["actor_id"],
            ["identity.principal.id"],
            name="fk_audit_event_actor",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "sequence_no",
            name="uq_audit_event_tenant_sequence",
        ),
        schema="audit",
    )
    op.create_index(
        "ix_audit_event_tenant_occurred",
        "event",
        ["organization_id", "project_id", "occurred_at", "sequence_no"],
        schema="audit",
    )
    op.create_index(
        "ix_audit_event_tenant_action",
        "event",
        ["organization_id", "project_id", "action", "sequence_no"],
        schema="audit",
    )
    op.create_index(
        "ix_audit_event_tenant_actor",
        "event",
        ["organization_id", "project_id", "actor_id", "sequence_no"],
        schema="audit",
    )
    op.create_index(
        "ix_audit_event_tenant_target",
        "event",
        ["organization_id", "project_id", "target_type", "target_id", "sequence_no"],
        schema="audit",
    )
    op.create_index(
        "ix_audit_event_tenant_request",
        "event",
        ["organization_id", "project_id", "request_id"],
        schema="audit",
    )

    op.create_table(
        "segment_root",
        sa.Column("id", uuid, nullable=False),
        sa.Column("organization_id", uuid, nullable=False),
        sa.Column("project_id", uuid, nullable=False),
        sa.Column("segment_no", sa.BigInteger(), nullable=False),
        sa.Column("first_sequence_no", sa.BigInteger(), nullable=False),
        sa.Column("last_sequence_no", sa.BigInteger(), nullable=False),
        sa.Column("event_count", sa.Integer(), nullable=False),
        sa.Column("first_event_hash", sa.CHAR(length=64, collation="C"), nullable=False),
        sa.Column("last_event_hash", sa.CHAR(length=64, collation="C"), nullable=False),
        sa.Column("previous_root_hash", sa.CHAR(length=64, collation="C"), nullable=False),
        sa.Column("root_hash", sa.CHAR(length=64, collation="C"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", uuid, nullable=False),
        sa.Column("request_id", uuid, nullable=False),
        sa.Column("trace_id", sa.String(length=255), nullable=False),
        sa.CheckConstraint("segment_no > 0", name="ck_audit_segment_no_positive"),
        sa.CheckConstraint(
            "first_sequence_no > 0 AND last_sequence_no >= first_sequence_no",
            name="ck_audit_segment_range",
        ),
        sa.CheckConstraint(
            "event_count = last_sequence_no - first_sequence_no + 1 "
            "AND event_count BETWEEN 1 AND 10000",
            name="ck_audit_segment_event_count",
        ),
        sa.CheckConstraint(
            "first_event_hash ~ '^[0-9a-f]{64}$' "
            "AND last_event_hash ~ '^[0-9a-f]{64}$' "
            "AND previous_root_hash ~ '^[0-9a-f]{64}$' "
            "AND root_hash ~ '^[0-9a-f]{64}$'",
            name="ck_audit_segment_hashes",
        ),
        sa.CheckConstraint(
            "length(btrim(trace_id)) BETWEEN 1 AND 255",
            name="ck_audit_segment_trace_id",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_audit_segment_root"),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["identity.principal.id"],
            name="fk_audit_segment_created_by",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "segment_no",
            name="uq_audit_segment_tenant_sequence",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "first_sequence_no",
            "last_sequence_no",
            name="uq_audit_segment_tenant_range",
        ),
        schema="audit",
    )
    op.create_index(
        "ix_audit_segment_tenant_range",
        "segment_root",
        ["organization_id", "project_id", "first_sequence_no", "last_sequence_no"],
        schema="audit",
    )


def _create_hash_functions() -> None:
    op.execute(
        """
        CREATE FUNCTION audit.hash_frame(value text)
        RETURNS text
        LANGUAGE sql
        IMMUTABLE
        PARALLEL SAFE
        AS $$
          SELECT CASE
            WHEN value IS NULL THEN '-1:'
            ELSE octet_length(convert_to(value, 'UTF8'))::text || ':' || value
          END
        $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION audit.utc_timestamp(value timestamptz)
        RETURNS text
        LANGUAGE sql
        IMMUTABLE
        PARALLEL SAFE
        STRICT
        AS $$
          SELECT to_char(value AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US"Z"')
        $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION audit.compute_event_hash(value audit.event)
        RETURNS text
        LANGUAGE sql
        IMMUTABLE
        PARALLEL SAFE
        STRICT
        AS $$
          SELECT encode(sha256(convert_to(
            audit.hash_frame('cmp-audit-event-v1')
            || audit.hash_frame(value.organization_id::text)
            || audit.hash_frame(value.project_id::text)
            || audit.hash_frame(value.sequence_no::text)
            || audit.hash_frame(value.id::text)
            || audit.hash_frame(audit.utc_timestamp(value.occurred_at))
            || audit.hash_frame(audit.utc_timestamp(value.recorded_at))
            || audit.hash_frame(value.actor_type)
            || audit.hash_frame(value.actor_id::text)
            || audit.hash_frame(value.action)
            || audit.hash_frame(value.target_type)
            || audit.hash_frame(value.target_id::text)
            || audit.hash_frame(value.outcome)
            || audit.hash_frame(value.request_id::text)
            || audit.hash_frame(value.trace_id)
            || audit.hash_frame(value.ip_or_client)
            || audit.hash_frame(value.reason)
            || audit.hash_frame(value.previous_hash::text),
            'UTF8'
          )), 'hex')
        $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION audit.compute_segment_root_hash(value audit.segment_root)
        RETURNS text
        LANGUAGE sql
        IMMUTABLE
        PARALLEL SAFE
        STRICT
        AS $$
          SELECT encode(sha256(convert_to(
            audit.hash_frame('cmp-audit-segment-v1')
            || audit.hash_frame(value.organization_id::text)
            || audit.hash_frame(value.project_id::text)
            || audit.hash_frame(value.segment_no::text)
            || audit.hash_frame(value.first_sequence_no::text)
            || audit.hash_frame(value.last_sequence_no::text)
            || audit.hash_frame(value.event_count::text)
            || audit.hash_frame(value.first_event_hash::text)
            || audit.hash_frame(value.last_event_hash::text)
            || audit.hash_frame(value.previous_root_hash::text)
            || audit.hash_frame(audit.utc_timestamp(value.created_at))
            || audit.hash_frame(value.created_by::text)
            || audit.hash_frame(value.request_id::text)
            || audit.hash_frame(value.trace_id),
            'UTF8'
          )), 'hex')
        $$
        """
    )


def _create_guards() -> None:
    op.execute(
        f"""
        CREATE FUNCTION audit.prepare_event_insert()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
          prior_sequence bigint;
          prior_hash text;
        BEGIN
          IF NOT access_control.tenant_matches(NEW.organization_id, NEW.project_id)
             OR NOT access_control.has_permission('audit.append') THEN
            RAISE EXCEPTION USING ERRCODE = '42501', MESSAGE = 'audit append denied';
          END IF;
          IF NEW.actor_id IS DISTINCT FROM access_control.current_principal_id()
             OR NEW.actor_type IS DISTINCT FROM current_setting('cmp.principal_type', true)
             OR NEW.request_id::text IS DISTINCT FROM current_setting('cmp.request_id', true)
             OR NEW.trace_id IS DISTINCT FROM current_setting('cmp.trace_id', true) THEN
            RAISE EXCEPTION USING
              ERRCODE = '42501',
              MESSAGE = 'audit actor and request context must match the transaction';
          END IF;

          PERFORM pg_advisory_xact_lock(hashtextextended(
            'audit-event:' || NEW.organization_id::text || ':' || NEW.project_id::text,
            0
          ));
          SELECT value.sequence_no, value.event_hash::text
            INTO prior_sequence, prior_hash
          FROM audit.event AS value
          WHERE value.organization_id = NEW.organization_id
            AND value.project_id = NEW.project_id
          ORDER BY value.sequence_no DESC
          LIMIT 1;

          NEW.sequence_no := COALESCE(prior_sequence, 0) + 1;
          NEW.previous_hash := COALESCE(prior_hash, '{_GENESIS_HASH}');
          NEW.recorded_at := clock_timestamp();
          NEW.event_hash := audit.compute_event_hash(NEW);
          RETURN NEW;
        END
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER audit_event_prepare
        BEFORE INSERT ON audit.event
        FOR EACH ROW EXECUTE FUNCTION audit.prepare_event_insert()
        """
    )
    op.execute(
        """
        CREATE TRIGGER audit_event_immutable
        BEFORE UPDATE OR DELETE ON audit.event
        FOR EACH ROW EXECUTE FUNCTION revisioning.reject_immutable_row_mutation()
        """
    )
    op.execute(
        f"""
        CREATE FUNCTION audit.prepare_segment_root_insert()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
          prior_segment_no bigint;
          prior_last_sequence bigint;
          prior_root_hash text;
          observed_count bigint;
          observed_first_hash text;
          observed_last_hash text;
        BEGIN
          IF NOT access_control.tenant_matches(NEW.organization_id, NEW.project_id)
             OR NOT access_control.has_permission('audit.seal') THEN
            RAISE EXCEPTION USING ERRCODE = '42501', MESSAGE = 'audit seal denied';
          END IF;
          IF NEW.created_by IS DISTINCT FROM access_control.current_principal_id()
             OR NEW.request_id::text IS DISTINCT FROM current_setting('cmp.request_id', true)
             OR NEW.trace_id IS DISTINCT FROM current_setting('cmp.trace_id', true) THEN
            RAISE EXCEPTION USING
              ERRCODE = '42501',
              MESSAGE = 'audit seal context must match the transaction';
          END IF;

          PERFORM pg_advisory_xact_lock(hashtextextended(
            'audit-segment:' || NEW.organization_id::text || ':' || NEW.project_id::text,
            0
          ));
          SELECT value.segment_no, value.last_sequence_no, value.root_hash::text
            INTO prior_segment_no, prior_last_sequence, prior_root_hash
          FROM audit.segment_root AS value
          WHERE value.organization_id = NEW.organization_id
            AND value.project_id = NEW.project_id
          ORDER BY value.segment_no DESC
          LIMIT 1;

          IF NEW.first_sequence_no <> COALESCE(prior_last_sequence, 0) + 1 THEN
            RAISE EXCEPTION USING
              ERRCODE = '23514',
              MESSAGE = 'audit segment must start after the prior sealed range';
          END IF;
          IF NEW.last_sequence_no < NEW.first_sequence_no
             OR NEW.last_sequence_no - NEW.first_sequence_no + 1 > 10000 THEN
            RAISE EXCEPTION USING ERRCODE = '23514', MESSAGE = 'invalid audit segment range';
          END IF;

          SELECT count(*),
                 min(value.event_hash::text) FILTER (
                   WHERE value.sequence_no = NEW.first_sequence_no
                 ),
                 min(value.event_hash::text) FILTER (
                   WHERE value.sequence_no = NEW.last_sequence_no
                 )
            INTO observed_count, observed_first_hash, observed_last_hash
          FROM audit.event AS value
          WHERE value.organization_id = NEW.organization_id
            AND value.project_id = NEW.project_id
            AND value.sequence_no BETWEEN NEW.first_sequence_no AND NEW.last_sequence_no;
          IF observed_count <> NEW.last_sequence_no - NEW.first_sequence_no + 1
             OR observed_first_hash IS NULL OR observed_last_hash IS NULL THEN
            RAISE EXCEPTION USING
              ERRCODE = '23514',
              MESSAGE = 'audit segment must cover a contiguous persisted event range';
          END IF;

          NEW.segment_no := COALESCE(prior_segment_no, 0) + 1;
          NEW.event_count := observed_count;
          NEW.first_event_hash := observed_first_hash;
          NEW.last_event_hash := observed_last_hash;
          NEW.previous_root_hash := COALESCE(prior_root_hash, '{_GENESIS_HASH}');
          NEW.created_at := clock_timestamp();
          NEW.root_hash := audit.compute_segment_root_hash(NEW);
          RETURN NEW;
        END
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER audit_segment_root_prepare
        BEFORE INSERT ON audit.segment_root
        FOR EACH ROW EXECUTE FUNCTION audit.prepare_segment_root_insert()
        """
    )
    op.execute(
        """
        CREATE TRIGGER audit_segment_root_immutable
        BEFORE UPDATE OR DELETE ON audit.segment_root
        FOR EACH ROW EXECUTE FUNCTION revisioning.reject_immutable_row_mutation()
        """
    )


def _secure_tables() -> None:
    for table in ("event", "segment_root"):
        op.execute(f"ALTER TABLE audit.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE audit.{table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY audit_{table}_select
            ON audit.{table}
            FOR SELECT
            USING (
              access_control.tenant_matches(organization_id, project_id)
              AND (
                access_control.has_permission('audit.read')
                OR access_control.has_permission('audit.append')
                OR access_control.has_permission('audit.seal')
              )
            )
            """
        )
        op.execute(
            f"""
            CREATE POLICY audit_{table}_immutable_update
            ON audit.{table}
            FOR UPDATE
            USING (
              access_control.tenant_matches(organization_id, project_id)
              AND access_control.has_permission('audit.read')
            )
            WITH CHECK (false)
            """
        )
        op.execute(
            f"""
            CREATE POLICY audit_{table}_immutable_delete
            ON audit.{table}
            FOR DELETE
            USING (
              access_control.tenant_matches(organization_id, project_id)
              AND access_control.has_permission('audit.read')
            )
            """
        )
    op.execute(
        """
        CREATE POLICY audit_event_insert
        ON audit.event
        FOR INSERT
        WITH CHECK (
          access_control.tenant_matches(organization_id, project_id)
          AND access_control.has_permission('audit.append')
          AND actor_id = access_control.current_principal_id()
          AND actor_type = current_setting('cmp.principal_type', true)
          AND request_id::text = current_setting('cmp.request_id', true)
          AND trace_id = current_setting('cmp.trace_id', true)
        )
        """
    )
    op.execute(
        """
        CREATE POLICY audit_segment_root_insert
        ON audit.segment_root
        FOR INSERT
        WITH CHECK (
          access_control.tenant_matches(organization_id, project_id)
          AND access_control.has_permission('audit.seal')
          AND created_by = access_control.current_principal_id()
          AND request_id::text = current_setting('cmp.request_id', true)
          AND trace_id = current_setting('cmp.trace_id', true)
        )
        """
    )


def upgrade() -> None:
    op.execute("CREATE SCHEMA audit")
    _create_tables()
    _create_hash_functions()
    _create_guards()
    _secure_tables()


def downgrade() -> None:
    op.execute("DROP TRIGGER audit_segment_root_immutable ON audit.segment_root")
    op.execute("DROP TRIGGER audit_segment_root_prepare ON audit.segment_root")
    op.execute("DROP TRIGGER audit_event_immutable ON audit.event")
    op.execute("DROP TRIGGER audit_event_prepare ON audit.event")
    op.execute("DROP FUNCTION audit.prepare_segment_root_insert()")
    op.execute("DROP FUNCTION audit.prepare_event_insert()")
    op.execute("DROP FUNCTION audit.compute_segment_root_hash(audit.segment_root)")
    op.execute("DROP FUNCTION audit.compute_event_hash(audit.event)")
    op.execute("DROP FUNCTION audit.utc_timestamp(timestamptz)")
    op.execute("DROP FUNCTION audit.hash_frame(text)")
    op.drop_index(
        "ix_audit_segment_tenant_range", table_name="segment_root", schema="audit"
    )
    op.drop_table("segment_root", schema="audit")
    for name in (
        "ix_audit_event_tenant_request",
        "ix_audit_event_tenant_target",
        "ix_audit_event_tenant_actor",
        "ix_audit_event_tenant_action",
        "ix_audit_event_tenant_occurred",
    ):
        op.drop_index(name, table_name="event", schema="audit")
    op.drop_table("event", schema="audit")
    op.execute("DROP SCHEMA audit")

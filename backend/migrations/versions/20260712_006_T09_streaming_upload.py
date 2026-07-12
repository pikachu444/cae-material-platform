"""T-09 streaming multipart upload, Raw Asset, and ingestion event.

Traceability: T-09, NFR-INT-001, NFR-PERF-004, NFR-SEC-002/003/004/006,
ADR-002/003. T-09 stores only verified staging objects. T-10 owns the generic
content-addressed Artifact, final-object state, and integrity reconciliation.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260712_006_t09"
down_revision: str | None = "20260711_005_t17"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CLASSIFICATIONS = (
    "internal",
    "confidential",
    "restricted",
    "export_controlled",
)
_UPLOAD_STATES = ("open", "completing", "completed", "failed", "cancelled")


def _quoted(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def _create_raw_asset() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    op.create_table(
        "raw_asset",
        sa.Column("organization_id", uuid, nullable=False),
        sa.Column("project_id", uuid, nullable=False),
        sa.Column("id", uuid, nullable=False),
        sa.Column("classification", sa.String(length=64), nullable=False),
        sa.Column("sha256", sa.CHAR(length=64, collation="C"), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("media_type", sa.String(length=255), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("storage_state", sa.String(length=32), nullable=False),
        sa.Column(
            "staging_object_key",
            sa.String(length=1024, collation="C"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", uuid, nullable=False),
        sa.CheckConstraint(
            "organization_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND project_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND created_by <> '00000000-0000-0000-0000-000000000000'::uuid",
            name="ck_artifact_raw_asset_nonzero_ids",
        ),
        sa.CheckConstraint(
            f"classification IN ({_quoted(_CLASSIFICATIONS)})",
            name="ck_artifact_raw_asset_classification",
        ),
        sa.CheckConstraint(
            "sha256 ~ '^[0-9a-f]{64}$' AND size_bytes > 0",
            name="ck_artifact_raw_asset_content",
        ),
        sa.CheckConstraint(
            "length(btrim(media_type)) BETWEEN 1 AND 255 "
            "AND media_type = btrim(media_type) "
            "AND length(btrim(original_filename)) BETWEEN 1 AND 255 "
            "AND original_filename = btrim(original_filename) "
            "AND original_filename !~ '[/\\\\]'",
            name="ck_artifact_raw_asset_labels",
        ),
        sa.CheckConstraint(
            "storage_state = 'staged_verified' "
            "AND length(staging_object_key) BETWEEN 1 AND 1024 "
            "AND staging_object_key = btrim(staging_object_key)",
            name="ck_artifact_raw_asset_staging",
        ),
        sa.PrimaryKeyConstraint(
            "organization_id", "project_id", "id", name="pk_artifact_raw_asset"
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "classification",
            "id",
            name="uq_artifact_raw_asset_classified_reference",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "classification",
            "sha256",
            "size_bytes",
            name="uq_artifact_raw_asset_content",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "staging_object_key",
            name="uq_artifact_raw_asset_staging_key",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["identity.principal.id"],
            name="fk_artifact_raw_asset_created_by",
            ondelete="RESTRICT",
        ),
        schema="artifact",
    )
    op.create_index(
        "ix_artifact_raw_asset_digest",
        "raw_asset",
        ["organization_id", "project_id", "sha256", "size_bytes"],
        schema="artifact",
    )


def _create_upload_session() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    op.create_table(
        "upload_session",
        sa.Column("organization_id", uuid, nullable=False),
        sa.Column("project_id", uuid, nullable=False),
        sa.Column("id", uuid, nullable=False),
        sa.Column("classification", sa.String(length=64), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("media_type", sa.String(length=255), nullable=False),
        sa.Column("expected_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column(
            "expected_sha256", sa.CHAR(length=64, collation="C"), nullable=False
        ),
        sa.Column("part_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("expected_part_count", sa.Integer(), nullable=False),
        sa.Column("test_run_revision_id", uuid, nullable=True),
        sa.Column(
            "staging_object_key",
            sa.String(length=1024, collation="C"),
            nullable=False,
        ),
        sa.Column(
            "object_upload_id",
            sa.String(length=1024, collation="C"),
            nullable=False,
        ),
        sa.Column(
            "idempotency_key", sa.String(length=255, collation="C"), nullable=False
        ),
        sa.Column(
            "submission_digest", sa.CHAR(length=64, collation="C"), nullable=False
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", uuid, nullable=False),
        sa.Column("request_id", uuid, nullable=False),
        sa.Column("trace_id", sa.String(length=255), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("terminal_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("raw_asset_id", uuid, nullable=True),
        sa.Column("failure_code", sa.String(length=100, collation="C"), nullable=True),
        sa.CheckConstraint(
            "organization_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND project_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND created_by <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND request_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND (test_run_revision_id IS NULL OR test_run_revision_id <> "
            "'00000000-0000-0000-0000-000000000000'::uuid)",
            name="ck_artifact_upload_session_nonzero_ids",
        ),
        sa.CheckConstraint(
            f"classification IN ({_quoted(_CLASSIFICATIONS)})",
            name="ck_artifact_upload_session_classification",
        ),
        sa.CheckConstraint(
            f"state IN ({_quoted(_UPLOAD_STATES)})",
            name="ck_artifact_upload_session_state",
        ),
        sa.CheckConstraint(
            "length(btrim(original_filename)) BETWEEN 1 AND 255 "
            "AND original_filename = btrim(original_filename) "
            "AND original_filename !~ '[/\\\\]' "
            "AND length(btrim(media_type)) BETWEEN 1 AND 255 "
            "AND media_type = btrim(media_type)",
            name="ck_artifact_upload_session_labels",
        ),
        sa.CheckConstraint(
            "expected_size_bytes > 0 AND expected_sha256 ~ '^[0-9a-f]{64}$' "
            "AND part_size_bytes > 0 AND part_size_bytes <= expected_size_bytes "
            "AND expected_part_count = "
            "((expected_size_bytes + part_size_bytes - 1) / part_size_bytes)::integer "
            "AND expected_part_count BETWEEN 1 AND 100000",
            name="ck_artifact_upload_session_manifest",
        ),
        sa.CheckConstraint(
            "length(staging_object_key) BETWEEN 1 AND 1024 "
            "AND staging_object_key = btrim(staging_object_key) "
            "AND length(object_upload_id) BETWEEN 1 AND 1024 "
            "AND object_upload_id = btrim(object_upload_id)",
            name="ck_artifact_upload_session_storage",
        ),
        sa.CheckConstraint(
            "idempotency_key ~ '^[!-~]{1,255}$' "
            "AND submission_digest ~ '^[0-9a-f]{64}$' "
            "AND length(btrim(trace_id)) BETWEEN 1 AND 255 "
            "AND trace_id = btrim(trace_id)",
            name="ck_artifact_upload_session_submission",
        ),
        sa.CheckConstraint(
            "expires_at > created_at AND updated_at >= created_at "
            "AND ((state IN ('completed', 'failed', 'cancelled')) = "
            "(terminal_at IS NOT NULL)) "
            "AND ((state = 'completed' AND raw_asset_id IS NOT NULL "
            "AND failure_code IS NULL) OR "
            "(state = 'failed' AND raw_asset_id IS NULL "
            "AND failure_code ~ '^[a-z][a-z0-9_]{0,99}$') OR "
            "(state IN ('open', 'completing', 'cancelled') "
            "AND raw_asset_id IS NULL AND failure_code IS NULL))",
            name="ck_artifact_upload_session_terminal",
        ),
        sa.PrimaryKeyConstraint(
            "organization_id", "project_id", "id", name="pk_artifact_upload_session"
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "classification",
            "id",
            name="uq_artifact_upload_session_classified_reference",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "idempotency_key",
            name="uq_artifact_upload_session_idempotency",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "staging_object_key",
            name="uq_artifact_upload_session_staging_key",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "object_upload_id",
            name="uq_artifact_upload_session_object_upload",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "classification", "raw_asset_id"],
            [
                "artifact.raw_asset.organization_id",
                "artifact.raw_asset.project_id",
                "artifact.raw_asset.classification",
                "artifact.raw_asset.id",
            ],
            name="fk_artifact_upload_session_raw_asset",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["identity.principal.id"],
            name="fk_artifact_upload_session_created_by",
            ondelete="RESTRICT",
        ),
        schema="artifact",
    )
    op.create_index(
        "ix_artifact_upload_session_state_expiry",
        "upload_session",
        ["organization_id", "project_id", "state", "expires_at"],
        schema="artifact",
    )


def _create_part_and_event() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    op.create_table(
        "upload_part",
        sa.Column("organization_id", uuid, nullable=False),
        sa.Column("project_id", uuid, nullable=False),
        sa.Column("classification", sa.String(length=64), nullable=False),
        sa.Column("upload_session_id", uuid, nullable=False),
        sa.Column("part_number", sa.Integer(), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.CHAR(length=64, collation="C"), nullable=False),
        sa.Column("storage_etag", sa.String(length=255, collation="C"), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recorded_by", uuid, nullable=False),
        sa.CheckConstraint(
            "part_number BETWEEN 1 AND 100000 AND size_bytes > 0 "
            "AND sha256 ~ '^[0-9a-f]{64}$' "
            "AND storage_etag ~ '^[!-~]{1,255}$'",
            name="ck_artifact_upload_part_manifest",
        ),
        sa.CheckConstraint(
            "recorded_by <> '00000000-0000-0000-0000-000000000000'::uuid",
            name="ck_artifact_upload_part_actor",
        ),
        sa.PrimaryKeyConstraint(
            "organization_id",
            "project_id",
            "upload_session_id",
            "part_number",
            name="pk_artifact_upload_part",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "classification", "upload_session_id"],
            [
                "artifact.upload_session.organization_id",
                "artifact.upload_session.project_id",
                "artifact.upload_session.classification",
                "artifact.upload_session.id",
            ],
            name="fk_artifact_upload_part_session",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["recorded_by"],
            ["identity.principal.id"],
            name="fk_artifact_upload_part_recorded_by",
            ondelete="RESTRICT",
        ),
        schema="artifact",
    )

    op.create_table(
        "ingestion_event",
        sa.Column("organization_id", uuid, nullable=False),
        sa.Column("project_id", uuid, nullable=False),
        sa.Column("id", uuid, nullable=False),
        sa.Column("classification", sa.String(length=64), nullable=False),
        sa.Column("raw_asset_id", uuid, nullable=False),
        sa.Column("upload_session_id", uuid, nullable=False),
        sa.Column("test_run_revision_id", uuid, nullable=True),
        sa.Column("duplicate_content", sa.Boolean(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor_id", uuid, nullable=False),
        sa.Column("request_id", uuid, nullable=False),
        sa.Column("trace_id", sa.String(length=255), nullable=False),
        sa.CheckConstraint(
            "id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND raw_asset_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND upload_session_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND actor_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND request_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND (test_run_revision_id IS NULL OR test_run_revision_id <> "
            "'00000000-0000-0000-0000-000000000000'::uuid)",
            name="ck_artifact_ingestion_event_nonzero_ids",
        ),
        sa.CheckConstraint(
            "length(btrim(trace_id)) BETWEEN 1 AND 255 "
            "AND trace_id = btrim(trace_id)",
            name="ck_artifact_ingestion_event_trace",
        ),
        sa.PrimaryKeyConstraint(
            "organization_id", "project_id", "id", name="pk_artifact_ingestion_event"
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "upload_session_id",
            name="uq_artifact_ingestion_event_upload",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "classification", "raw_asset_id"],
            [
                "artifact.raw_asset.organization_id",
                "artifact.raw_asset.project_id",
                "artifact.raw_asset.classification",
                "artifact.raw_asset.id",
            ],
            name="fk_artifact_ingestion_event_raw_asset",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "classification", "upload_session_id"],
            [
                "artifact.upload_session.organization_id",
                "artifact.upload_session.project_id",
                "artifact.upload_session.classification",
                "artifact.upload_session.id",
            ],
            name="fk_artifact_ingestion_event_upload",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["actor_id"],
            ["identity.principal.id"],
            name="fk_artifact_ingestion_event_actor",
            ondelete="RESTRICT",
        ),
        schema="artifact",
    )
    op.create_index(
        "ix_artifact_ingestion_event_raw_asset",
        "ingestion_event",
        ["organization_id", "project_id", "raw_asset_id", "occurred_at"],
        schema="artifact",
    )
    op.create_index(
        "ix_artifact_ingestion_event_test_run",
        "ingestion_event",
        ["organization_id", "project_id", "test_run_revision_id"],
        schema="artifact",
        postgresql_where=sa.text("test_run_revision_id IS NOT NULL"),
    )


def _create_guards() -> None:
    for table in ("raw_asset", "upload_part", "ingestion_event"):
        op.execute(
            f"""
            CREATE TRIGGER {table}_immutable
            BEFORE UPDATE OR DELETE ON artifact.{table}
            FOR EACH ROW EXECUTE FUNCTION revisioning.reject_immutable_row_mutation()
            """
        )

    op.execute(
        """
        CREATE FUNCTION artifact.guard_upload_part_insert()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
          upload artifact.upload_session%ROWTYPE;
          expected_part_size bigint;
        BEGIN
          SELECT * INTO upload
          FROM artifact.upload_session
          WHERE organization_id = NEW.organization_id
            AND project_id = NEW.project_id
            AND id = NEW.upload_session_id
          FOR UPDATE;
          IF NOT FOUND OR upload.state <> 'open' THEN
            RAISE EXCEPTION USING ERRCODE = '55000',
              MESSAGE = 'upload parts require an open session';
          END IF;
          IF NEW.part_number < 1 OR NEW.part_number > upload.expected_part_count THEN
            RAISE EXCEPTION USING ERRCODE = '22023',
              MESSAGE = 'upload part number is outside the immutable manifest';
          END IF;
          expected_part_size := CASE
            WHEN NEW.part_number < upload.expected_part_count
              THEN upload.part_size_bytes
            ELSE upload.expected_size_bytes
              - upload.part_size_bytes * (upload.expected_part_count - 1)
          END;
          IF NEW.size_bytes <> expected_part_size THEN
            RAISE EXCEPTION USING ERRCODE = '22023',
              MESSAGE = 'upload part size differs from the immutable manifest';
          END IF;
          RETURN NEW;
        END
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER upload_part_insert_guard
        BEFORE INSERT ON artifact.upload_part
        FOR EACH ROW EXECUTE FUNCTION artifact.guard_upload_part_insert()
        """
    )

    op.execute(
        """
        CREATE FUNCTION artifact.guard_raw_asset_insert()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
          IF NOT EXISTS (
            SELECT 1
            FROM artifact.upload_session upload
            WHERE upload.organization_id = NEW.organization_id
              AND upload.project_id = NEW.project_id
              AND upload.classification = NEW.classification
              AND upload.state = 'completing'
              AND upload.expected_sha256 = NEW.sha256
              AND upload.expected_size_bytes = NEW.size_bytes
              AND upload.media_type = NEW.media_type
              AND upload.staging_object_key = NEW.staging_object_key
              AND upload.created_by = NEW.created_by
          ) THEN
            RAISE EXCEPTION USING ERRCODE = '55000',
              MESSAGE = 'Raw Asset requires its verified completing upload';
          END IF;
          RETURN NEW;
        END
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER raw_asset_insert_guard
        BEFORE INSERT ON artifact.raw_asset
        FOR EACH ROW EXECUTE FUNCTION artifact.guard_raw_asset_insert()
        """
    )

    op.execute(
        """
        CREATE FUNCTION artifact.guard_ingestion_event_insert()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
          upload artifact.upload_session%ROWTYPE;
          raw artifact.raw_asset%ROWTYPE;
        BEGIN
          SELECT * INTO upload
          FROM artifact.upload_session
          WHERE organization_id = NEW.organization_id
            AND project_id = NEW.project_id
            AND id = NEW.upload_session_id
          FOR UPDATE;
          SELECT * INTO raw
          FROM artifact.raw_asset
          WHERE organization_id = NEW.organization_id
            AND project_id = NEW.project_id
            AND id = NEW.raw_asset_id;
          IF upload.state <> 'completing'
             OR raw.sha256 <> upload.expected_sha256
             OR raw.size_bytes <> upload.expected_size_bytes
             OR upload.test_run_revision_id IS DISTINCT FROM NEW.test_run_revision_id
             OR NEW.duplicate_content <> (raw.staging_object_key <> upload.staging_object_key)
             OR NEW.actor_id <> upload.created_by THEN
            RAISE EXCEPTION USING ERRCODE = '55000',
              MESSAGE = 'ingestion event differs from upload and Raw Asset facts';
          END IF;
          RETURN NEW;
        END
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER ingestion_event_insert_guard
        BEFORE INSERT ON artifact.ingestion_event
        FOR EACH ROW EXECUTE FUNCTION artifact.guard_ingestion_event_insert()
        """
    )

    op.execute(
        """
        CREATE FUNCTION artifact.guard_upload_session_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
          expected_count integer;
          observed_count integer;
          observed_size bigint;
        BEGIN
          IF TG_OP = 'DELETE' THEN
            RAISE EXCEPTION USING ERRCODE = '55000',
              MESSAGE = 'upload sessions cannot be deleted';
          END IF;
          IF (to_jsonb(NEW) - ARRAY[
                'state', 'updated_at', 'terminal_at', 'raw_asset_id', 'failure_code'
              ]) IS DISTINCT FROM
             (to_jsonb(OLD) - ARRAY[
                'state', 'updated_at', 'terminal_at', 'raw_asset_id', 'failure_code'
              ]) THEN
            RAISE EXCEPTION USING ERRCODE = '55000',
              MESSAGE = 'upload session manifest and identity are immutable';
          END IF;
          IF NEW.updated_at < OLD.updated_at THEN
            RAISE EXCEPTION USING ERRCODE = '40001',
              MESSAGE = 'upload session time cannot move backwards';
          END IF;
          IF OLD.state IN ('completed', 'failed', 'cancelled') THEN
            RAISE EXCEPTION USING ERRCODE = '55000',
              MESSAGE = 'terminal upload sessions are immutable';
          END IF;
          IF NEW.state = OLD.state THEN
            RAISE EXCEPTION USING ERRCODE = '55000',
              MESSAGE = 'upload state projection may change only with a transition';
          END IF;
          IF NOT (
            (OLD.state = 'open' AND NEW.state IN ('completing', 'failed', 'cancelled'))
            OR (OLD.state = 'completing' AND NEW.state IN ('completed', 'failed', 'cancelled'))
          ) THEN
            RAISE EXCEPTION USING ERRCODE = '55000',
              MESSAGE = format('invalid upload transition %s -> %s', OLD.state, NEW.state);
          END IF;
          IF NEW.state = 'completing' THEN
            expected_count := NEW.expected_part_count;
            SELECT count(*)::integer, COALESCE(sum(size_bytes), 0)
            INTO observed_count, observed_size
            FROM artifact.upload_part
            WHERE organization_id = NEW.organization_id
              AND project_id = NEW.project_id
              AND upload_session_id = NEW.id;
            IF observed_count <> expected_count OR observed_size <> NEW.expected_size_bytes THEN
              RAISE EXCEPTION USING ERRCODE = '55000',
                MESSAGE = 'upload completion requires every immutable part';
            END IF;
          END IF;
          IF NEW.state = 'completed' AND NOT EXISTS (
            SELECT 1
            FROM artifact.ingestion_event event
            WHERE event.organization_id = NEW.organization_id
              AND event.project_id = NEW.project_id
              AND event.upload_session_id = NEW.id
              AND event.raw_asset_id = NEW.raw_asset_id
          ) THEN
            RAISE EXCEPTION USING ERRCODE = '55000',
              MESSAGE = 'completed upload requires an ingestion event';
          END IF;
          RETURN NEW;
        END
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER upload_session_mutation_guard
        BEFORE UPDATE OR DELETE ON artifact.upload_session
        FOR EACH ROW EXECUTE FUNCTION artifact.guard_upload_session_mutation()
        """
    )


def _secure_tables() -> None:
    for table in ("raw_asset", "upload_session", "upload_part", "ingestion_event"):
        op.execute(f"ALTER TABLE artifact.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE artifact.{table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY {table}_authorized_select
            ON artifact.{table} FOR SELECT
            USING (
              access_control.can_access_row(
                organization_id, project_id, classification, 'artifact.read'
              )
            )
            """
        )

    actor_columns = {
        "raw_asset": "created_by",
        "upload_session": "created_by",
        "upload_part": "recorded_by",
        "ingestion_event": "actor_id",
    }
    for table, actor in actor_columns.items():
        op.execute(
            f"""
            CREATE POLICY {table}_authorized_insert
            ON artifact.{table} FOR INSERT
            WITH CHECK (
              {actor} = access_control.current_principal_id()
              AND access_control.can_access_row(
                organization_id, project_id, classification, 'artifact.write'
              )
            )
            """
        )
    op.execute(
        """
        CREATE POLICY upload_session_authorized_update
        ON artifact.upload_session FOR UPDATE
        USING (
          created_by = access_control.current_principal_id()
          AND access_control.can_access_row(
            organization_id, project_id, classification, 'artifact.write'
          )
        )
        WITH CHECK (
          created_by = access_control.current_principal_id()
          AND access_control.can_access_row(
            organization_id, project_id, classification, 'artifact.write'
          )
        )
        """
    )


def upgrade() -> None:
    op.execute("CREATE SCHEMA artifact")
    _create_raw_asset()
    _create_upload_session()
    _create_part_and_event()
    _create_guards()
    _secure_tables()


def downgrade() -> None:
    op.execute("DROP FUNCTION artifact.guard_upload_session_mutation() CASCADE")
    op.execute("DROP FUNCTION artifact.guard_ingestion_event_insert() CASCADE")
    op.execute("DROP FUNCTION artifact.guard_raw_asset_insert() CASCADE")
    op.execute("DROP FUNCTION artifact.guard_upload_part_insert() CASCADE")
    op.drop_index(
        "ix_artifact_ingestion_event_test_run",
        table_name="ingestion_event",
        schema="artifact",
    )
    op.drop_index(
        "ix_artifact_ingestion_event_raw_asset",
        table_name="ingestion_event",
        schema="artifact",
    )
    op.drop_table("ingestion_event", schema="artifact")
    op.drop_table("upload_part", schema="artifact")
    op.drop_index(
        "ix_artifact_upload_session_state_expiry",
        table_name="upload_session",
        schema="artifact",
    )
    op.drop_table("upload_session", schema="artifact")
    op.drop_index(
        "ix_artifact_raw_asset_digest",
        table_name="raw_asset",
        schema="artifact",
    )
    op.drop_table("raw_asset", schema="artifact")
    op.execute("DROP SCHEMA artifact")

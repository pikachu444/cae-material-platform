"""T-10 content-addressed Artifact and integrity reconciliation.

Traceability: T-10, FR-ING-002, FR-DAT-008, NFR-INT-001/002,
NFR-SEC-002/003/004/006, ADR-002/003. T-16 owns durable scheduling,
transactional outbox delivery, and retention cleanup automation.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260712_007_t10"
down_revision: str | None = "20260712_006_t09"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CLASSIFICATIONS = (
    "internal",
    "confidential",
    "restricted",
    "export_controlled",
)
_PENDING_STATES = ("pending", "promoting", "available", "retryable", "rejected")
_ARTIFACT_KINDS = ("raw", "derived", "release")
_INTEGRITY_STATUSES = ("verified", "missing", "corrupt")
_CHECK_KINDS = ("finalization", "reconciliation", "download")
_ISSUE_TYPES = (
    "orphan_object",
    "pending_missing_staging",
    "pending_staging_corrupt",
    "pending_final_corrupt",
)


def _quoted(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def _create_content_key_function() -> None:
    op.execute(
        """
        CREATE FUNCTION artifact.content_object_key(
          organization_id uuid,
          project_id uuid,
          classification text,
          sha256 text
        )
        RETURNS text
        LANGUAGE sql
        IMMUTABLE
        STRICT
        PARALLEL SAFE
        AS $$
          SELECT 'final/' || organization_id::text || '/' || project_id::text || '/'
            || classification || '/sha256/' || substr(sha256, 1, 2) || '/'
            || substr(sha256, 3, 2) || '/' || sha256
        $$
        """
    )


def _create_pending() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    op.create_table(
        "artifact_pending",
        sa.Column("organization_id", uuid, nullable=False),
        sa.Column("project_id", uuid, nullable=False),
        sa.Column("id", uuid, nullable=False),
        sa.Column("classification", sa.String(length=64), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("artifact_kind", sa.String(length=32), nullable=False),
        sa.Column("artifact_role", sa.String(length=100), nullable=False),
        sa.Column("schema_ref", sa.String(length=500), nullable=True),
        sa.Column("media_type", sa.String(length=255), nullable=False),
        sa.Column("expected_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column(
            "expected_sha256", sa.CHAR(length=64, collation="C"), nullable=False
        ),
        sa.Column(
            "staging_object_key",
            sa.String(length=1024, collation="C"),
            nullable=False,
        ),
        sa.Column(
            "final_object_key",
            sa.String(length=1024, collation="C"),
            nullable=False,
        ),
        sa.Column("encryption_profile", sa.String(length=255), nullable=False),
        sa.Column("source_raw_asset_id", uuid, nullable=True),
        sa.Column(
            "idempotency_key", sa.String(length=255, collation="C"), nullable=False
        ),
        sa.Column(
            "submission_digest", sa.CHAR(length=64, collation="C"), nullable=False
        ),
        sa.Column("reserved_artifact_id", uuid, nullable=False),
        sa.Column("available_artifact_id", uuid, nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("failure_code", sa.String(length=100, collation="C"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", uuid, nullable=False),
        sa.Column("request_id", uuid, nullable=False),
        sa.Column("trace_id", sa.String(length=255), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("terminal_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "organization_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND project_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND reserved_artifact_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND created_by <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND request_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND (source_raw_asset_id IS NULL OR source_raw_asset_id <> "
            "'00000000-0000-0000-0000-000000000000'::uuid) "
            "AND (available_artifact_id IS NULL OR available_artifact_id <> "
            "'00000000-0000-0000-0000-000000000000'::uuid)",
            name="ck_artifact_pending_nonzero_ids",
        ),
        sa.CheckConstraint(
            f"classification IN ({_quoted(_CLASSIFICATIONS)}) "
            f"AND state IN ({_quoted(_PENDING_STATES)}) "
            f"AND artifact_kind IN ({_quoted(_ARTIFACT_KINDS)})",
            name="ck_artifact_pending_enums",
        ),
        sa.CheckConstraint(
            "artifact_role ~ '^[a-z][a-z0-9_.-]{0,99}$' "
            "AND length(btrim(media_type)) BETWEEN 1 AND 255 "
            "AND media_type = btrim(media_type) "
            "AND length(btrim(encryption_profile)) BETWEEN 1 AND 255 "
            "AND encryption_profile = btrim(encryption_profile)",
            name="ck_artifact_pending_labels",
        ),
        sa.CheckConstraint(
            "((artifact_kind = 'raw' AND source_raw_asset_id IS NOT NULL "
            "AND schema_ref IS NULL) OR "
            "(artifact_kind IN ('derived', 'release') "
            "AND source_raw_asset_id IS NULL "
            "AND length(btrim(schema_ref)) BETWEEN 1 AND 500 "
            "AND schema_ref = btrim(schema_ref)))",
            name="ck_artifact_pending_kind_source",
        ),
        sa.CheckConstraint(
            "expected_size_bytes >= 0 AND expected_sha256 ~ '^[0-9a-f]{64}$' "
            "AND length(staging_object_key) BETWEEN 1 AND 1024 "
            "AND staging_object_key = btrim(staging_object_key) "
            "AND final_object_key = artifact.content_object_key("
            "organization_id, project_id, classification, expected_sha256)",
            name="ck_artifact_pending_content",
        ),
        sa.CheckConstraint(
            "idempotency_key ~ '^[!-~]{1,255}$' "
            "AND submission_digest ~ '^[0-9a-f]{64}$' "
            "AND length(btrim(trace_id)) BETWEEN 1 AND 255 "
            "AND trace_id = btrim(trace_id) "
            "AND updated_at >= created_at",
            name="ck_artifact_pending_submission",
        ),
        sa.CheckConstraint(
            "attempt_count >= 0 AND ("
            "(state = 'pending' AND attempt_count = 0 "
            "AND available_artifact_id IS NULL AND failure_code IS NULL "
            "AND terminal_at IS NULL) OR "
            "(state = 'promoting' AND attempt_count >= 1 "
            "AND available_artifact_id IS NULL AND failure_code IS NULL "
            "AND terminal_at IS NULL) OR "
            "(state = 'retryable' AND attempt_count >= 1 "
            "AND available_artifact_id IS NULL "
            "AND failure_code ~ '^[a-z][a-z0-9_]{0,99}$' "
            "AND terminal_at IS NULL) OR "
            "(state = 'available' AND attempt_count >= 1 "
            "AND available_artifact_id = reserved_artifact_id "
            "AND failure_code IS NULL AND terminal_at IS NOT NULL) OR "
            "(state = 'rejected' AND attempt_count >= 1 "
            "AND available_artifact_id IS NULL "
            "AND failure_code ~ '^[a-z][a-z0-9_]{0,99}$' "
            "AND terminal_at IS NOT NULL))",
            name="ck_artifact_pending_state_projection",
        ),
        sa.PrimaryKeyConstraint(
            "organization_id", "project_id", "id", name="pk_artifact_pending"
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "classification",
            "id",
            name="uq_artifact_pending_classified_reference",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "idempotency_key",
            name="uq_artifact_pending_idempotency",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "reserved_artifact_id",
            name="uq_artifact_pending_reserved_artifact",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "source_raw_asset_id",
            name="uq_artifact_pending_raw_asset",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "classification", "source_raw_asset_id"],
            [
                "artifact.raw_asset.organization_id",
                "artifact.raw_asset.project_id",
                "artifact.raw_asset.classification",
                "artifact.raw_asset.id",
            ],
            name="fk_artifact_pending_raw_asset",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["identity.principal.id"],
            name="fk_artifact_pending_created_by",
            ondelete="RESTRICT",
        ),
        schema="artifact",
    )
    op.create_index(
        "ix_artifact_pending_state_updated",
        "artifact_pending",
        ["organization_id", "project_id", "state", "updated_at"],
        schema="artifact",
    )
    op.create_index(
        "ix_artifact_pending_final_key",
        "artifact_pending",
        ["organization_id", "project_id", "final_object_key"],
        schema="artifact",
    )


def _create_artifact() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    op.create_table(
        "artifact",
        sa.Column("organization_id", uuid, nullable=False),
        sa.Column("project_id", uuid, nullable=False),
        sa.Column("id", uuid, nullable=False),
        sa.Column("classification", sa.String(length=64), nullable=False),
        sa.Column("artifact_kind", sa.String(length=32), nullable=False),
        sa.Column("artifact_role", sa.String(length=100), nullable=False),
        sa.Column("schema_ref", sa.String(length=500), nullable=True),
        sa.Column("media_type", sa.String(length=255), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.CHAR(length=64, collation="C"), nullable=False),
        sa.Column(
            "storage_key", sa.String(length=1024, collation="C"), nullable=False
        ),
        sa.Column("encryption_profile", sa.String(length=255), nullable=False),
        sa.Column("source_raw_asset_id", uuid, nullable=True),
        sa.Column("source_pending_id", uuid, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", uuid, nullable=False),
        sa.CheckConstraint(
            "organization_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND project_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND source_pending_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND created_by <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND (source_raw_asset_id IS NULL OR source_raw_asset_id <> "
            "'00000000-0000-0000-0000-000000000000'::uuid)",
            name="ck_artifact_manifest_nonzero_ids",
        ),
        sa.CheckConstraint(
            f"classification IN ({_quoted(_CLASSIFICATIONS)}) "
            f"AND artifact_kind IN ({_quoted(_ARTIFACT_KINDS)})",
            name="ck_artifact_manifest_enums",
        ),
        sa.CheckConstraint(
            "artifact_role ~ '^[a-z][a-z0-9_.-]{0,99}$' "
            "AND length(btrim(media_type)) BETWEEN 1 AND 255 "
            "AND media_type = btrim(media_type) "
            "AND length(btrim(encryption_profile)) BETWEEN 1 AND 255 "
            "AND encryption_profile = btrim(encryption_profile)",
            name="ck_artifact_manifest_labels",
        ),
        sa.CheckConstraint(
            "((artifact_kind = 'raw' AND source_raw_asset_id IS NOT NULL "
            "AND schema_ref IS NULL) OR "
            "(artifact_kind IN ('derived', 'release') "
            "AND source_raw_asset_id IS NULL "
            "AND length(btrim(schema_ref)) BETWEEN 1 AND 500 "
            "AND schema_ref = btrim(schema_ref)))",
            name="ck_artifact_manifest_kind_source",
        ),
        sa.CheckConstraint(
            "size_bytes >= 0 AND sha256 ~ '^[0-9a-f]{64}$' "
            "AND storage_key = artifact.content_object_key("
            "organization_id, project_id, classification, sha256)",
            name="ck_artifact_manifest_content_key",
        ),
        sa.PrimaryKeyConstraint(
            "organization_id", "project_id", "id", name="pk_artifact_manifest"
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "classification",
            "id",
            name="uq_artifact_manifest_classified_reference",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "source_pending_id",
            name="uq_artifact_manifest_pending",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "source_raw_asset_id",
            name="uq_artifact_manifest_raw_asset",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "classification", "source_pending_id"],
            [
                "artifact.artifact_pending.organization_id",
                "artifact.artifact_pending.project_id",
                "artifact.artifact_pending.classification",
                "artifact.artifact_pending.id",
            ],
            name="fk_artifact_manifest_pending",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "classification", "source_raw_asset_id"],
            [
                "artifact.raw_asset.organization_id",
                "artifact.raw_asset.project_id",
                "artifact.raw_asset.classification",
                "artifact.raw_asset.id",
            ],
            name="fk_artifact_manifest_raw_asset",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["identity.principal.id"],
            name="fk_artifact_manifest_created_by",
            ondelete="RESTRICT",
        ),
        schema="artifact",
    )
    op.create_foreign_key(
        "fk_artifact_pending_available_artifact",
        "artifact_pending",
        "artifact",
        ["organization_id", "project_id", "classification", "available_artifact_id"],
        ["organization_id", "project_id", "classification", "id"],
        source_schema="artifact",
        referent_schema="artifact",
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_artifact_manifest_digest",
        "artifact",
        ["organization_id", "project_id", "sha256", "size_bytes"],
        schema="artifact",
    )
    op.create_index(
        "ix_artifact_manifest_storage_key",
        "artifact",
        ["organization_id", "project_id", "storage_key"],
        schema="artifact",
    )


def _create_integrity() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    op.create_table(
        "integrity_observation",
        sa.Column("organization_id", uuid, nullable=False),
        sa.Column("project_id", uuid, nullable=False),
        sa.Column("id", uuid, nullable=False),
        sa.Column("classification", sa.String(length=64), nullable=False),
        sa.Column("artifact_id", uuid, nullable=False),
        sa.Column("check_kind", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column(
            "expected_sha256", sa.CHAR(length=64, collation="C"), nullable=False
        ),
        sa.Column("expected_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column(
            "observed_sha256", sa.CHAR(length=64, collation="C"), nullable=True
        ),
        sa.Column("observed_size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("object_version_id", sa.String(length=1024), nullable=True),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("checked_by", uuid, nullable=False),
        sa.Column("request_id", uuid, nullable=False),
        sa.Column("trace_id", sa.String(length=255), nullable=False),
        sa.CheckConstraint(
            "id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND artifact_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND checked_by <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND request_id <> '00000000-0000-0000-0000-000000000000'::uuid",
            name="ck_artifact_integrity_observation_nonzero_ids",
        ),
        sa.CheckConstraint(
            f"classification IN ({_quoted(_CLASSIFICATIONS)}) "
            f"AND check_kind IN ({_quoted(_CHECK_KINDS)}) "
            f"AND status IN ({_quoted(_INTEGRITY_STATUSES)})",
            name="ck_artifact_integrity_observation_enums",
        ),
        sa.CheckConstraint(
            "expected_sha256 ~ '^[0-9a-f]{64}$' AND expected_size_bytes >= 0 "
            "AND (observed_sha256 IS NULL OR observed_sha256 ~ '^[0-9a-f]{64}$') "
            "AND (observed_size_bytes IS NULL OR observed_size_bytes >= 0) "
            "AND (object_version_id IS NULL OR "
            "(length(btrim(object_version_id)) BETWEEN 1 AND 1024 "
            "AND object_version_id = btrim(object_version_id)))",
            name="ck_artifact_integrity_observation_content",
        ),
        sa.CheckConstraint(
            "((status = 'verified' AND observed_sha256 = expected_sha256 "
            "AND observed_size_bytes = expected_size_bytes "
            "AND object_version_id IS NOT NULL) OR "
            "(status = 'missing' AND observed_sha256 IS NULL "
            "AND observed_size_bytes IS NULL AND object_version_id IS NULL) OR "
            "(status = 'corrupt' AND observed_sha256 IS NOT NULL "
            "AND observed_size_bytes IS NOT NULL "
            "AND (observed_sha256 <> expected_sha256 "
            "OR observed_size_bytes <> expected_size_bytes)))",
            name="ck_artifact_integrity_observation_status",
        ),
        sa.CheckConstraint(
            "length(btrim(trace_id)) BETWEEN 1 AND 255 "
            "AND trace_id = btrim(trace_id)",
            name="ck_artifact_integrity_observation_trace",
        ),
        sa.PrimaryKeyConstraint(
            "organization_id",
            "project_id",
            "id",
            name="pk_artifact_integrity_observation",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "classification",
            "artifact_id",
            "id",
            name="uq_artifact_integrity_observation_reference",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "classification", "artifact_id"],
            [
                "artifact.artifact.organization_id",
                "artifact.artifact.project_id",
                "artifact.artifact.classification",
                "artifact.artifact.id",
            ],
            name="fk_artifact_integrity_observation_artifact",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["checked_by"],
            ["identity.principal.id"],
            name="fk_artifact_integrity_observation_checked_by",
            ondelete="RESTRICT",
        ),
        schema="artifact",
    )
    op.create_index(
        "ix_artifact_integrity_observation_artifact_time",
        "integrity_observation",
        ["organization_id", "project_id", "artifact_id", "checked_at"],
        schema="artifact",
    )
    op.create_index(
        "ix_artifact_integrity_observation_status_time",
        "integrity_observation",
        ["organization_id", "project_id", "status", "checked_at"],
        schema="artifact",
    )

    op.create_table(
        "integrity_projection",
        sa.Column("organization_id", uuid, nullable=False),
        sa.Column("project_id", uuid, nullable=False),
        sa.Column("artifact_id", uuid, nullable=False),
        sa.Column("classification", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("last_observation_id", uuid, nullable=False),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            f"classification IN ({_quoted(_CLASSIFICATIONS)}) "
            f"AND status IN ({_quoted(_INTEGRITY_STATUSES)}) "
            "AND artifact_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND last_observation_id <> "
            "'00000000-0000-0000-0000-000000000000'::uuid "
            "AND updated_at >= last_checked_at",
            name="ck_artifact_integrity_projection",
        ),
        sa.PrimaryKeyConstraint(
            "organization_id",
            "project_id",
            "artifact_id",
            name="pk_artifact_integrity_projection",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "classification", "artifact_id"],
            [
                "artifact.artifact.organization_id",
                "artifact.artifact.project_id",
                "artifact.artifact.classification",
                "artifact.artifact.id",
            ],
            name="fk_artifact_integrity_projection_artifact",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            [
                "organization_id",
                "project_id",
                "classification",
                "artifact_id",
                "last_observation_id",
            ],
            [
                "artifact.integrity_observation.organization_id",
                "artifact.integrity_observation.project_id",
                "artifact.integrity_observation.classification",
                "artifact.integrity_observation.artifact_id",
                "artifact.integrity_observation.id",
            ],
            name="fk_artifact_integrity_projection_observation",
            ondelete="RESTRICT",
        ),
        schema="artifact",
    )
    op.create_index(
        "ix_artifact_integrity_projection_status",
        "integrity_projection",
        ["organization_id", "project_id", "status", "last_checked_at"],
        schema="artifact",
    )


def _create_issues() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    op.create_table(
        "reconciliation_issue",
        sa.Column("organization_id", uuid, nullable=False),
        sa.Column("project_id", uuid, nullable=False),
        sa.Column("id", uuid, nullable=False),
        sa.Column("classification", sa.String(length=64), nullable=False),
        sa.Column("issue_type", sa.String(length=64), nullable=False),
        sa.Column("artifact_id", uuid, nullable=True),
        sa.Column("pending_artifact_id", uuid, nullable=True),
        sa.Column(
            "object_key", sa.String(length=1024, collation="C"), nullable=False
        ),
        sa.Column(
            "expected_sha256", sa.CHAR(length=64, collation="C"), nullable=True
        ),
        sa.Column("expected_size_bytes", sa.BigInteger(), nullable=True),
        sa.Column(
            "observed_sha256", sa.CHAR(length=64, collation="C"), nullable=True
        ),
        sa.Column("observed_size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("detected_by", uuid, nullable=False),
        sa.Column("request_id", uuid, nullable=False),
        sa.Column("trace_id", sa.String(length=255), nullable=False),
        sa.CheckConstraint(
            "id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND detected_by <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND request_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND (artifact_id IS NULL OR artifact_id <> "
            "'00000000-0000-0000-0000-000000000000'::uuid) "
            "AND (pending_artifact_id IS NULL OR pending_artifact_id <> "
            "'00000000-0000-0000-0000-000000000000'::uuid)",
            name="ck_artifact_reconciliation_issue_nonzero_ids",
        ),
        sa.CheckConstraint(
            f"classification IN ({_quoted(_CLASSIFICATIONS)}) "
            f"AND issue_type IN ({_quoted(_ISSUE_TYPES)}) "
            "AND ((issue_type = 'orphan_object' AND artifact_id IS NULL "
            "AND pending_artifact_id IS NULL) OR "
            "(issue_type <> 'orphan_object' AND pending_artifact_id IS NOT NULL))",
            name="ck_artifact_reconciliation_issue_kind",
        ),
        sa.CheckConstraint(
            "length(object_key) BETWEEN 1 AND 1024 "
            "AND object_key = btrim(object_key) "
            "AND (expected_sha256 IS NULL OR expected_sha256 ~ '^[0-9a-f]{64}$') "
            "AND (observed_sha256 IS NULL OR observed_sha256 ~ '^[0-9a-f]{64}$') "
            "AND (expected_size_bytes IS NULL OR expected_size_bytes >= 0) "
            "AND (observed_size_bytes IS NULL OR observed_size_bytes >= 0) "
            "AND length(btrim(trace_id)) BETWEEN 1 AND 255 "
            "AND trace_id = btrim(trace_id)",
            name="ck_artifact_reconciliation_issue_content",
        ),
        sa.PrimaryKeyConstraint(
            "organization_id",
            "project_id",
            "id",
            name="pk_artifact_reconciliation_issue",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "classification", "artifact_id"],
            [
                "artifact.artifact.organization_id",
                "artifact.artifact.project_id",
                "artifact.artifact.classification",
                "artifact.artifact.id",
            ],
            name="fk_artifact_reconciliation_issue_artifact",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            [
                "organization_id",
                "project_id",
                "classification",
                "pending_artifact_id",
            ],
            [
                "artifact.artifact_pending.organization_id",
                "artifact.artifact_pending.project_id",
                "artifact.artifact_pending.classification",
                "artifact.artifact_pending.id",
            ],
            name="fk_artifact_reconciliation_issue_pending",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["detected_by"],
            ["identity.principal.id"],
            name="fk_artifact_reconciliation_issue_detected_by",
            ondelete="RESTRICT",
        ),
        schema="artifact",
    )
    op.create_index(
        "ix_artifact_reconciliation_issue_type_time",
        "reconciliation_issue",
        ["organization_id", "project_id", "issue_type", "detected_at"],
        schema="artifact",
    )


def _create_guards() -> None:
    op.execute(
        """
        CREATE FUNCTION artifact.guard_pending_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
          IF TG_OP = 'DELETE' THEN
            RAISE EXCEPTION USING ERRCODE = '55000',
              MESSAGE = 'pending Artifact records cannot be deleted';
          END IF;
          IF OLD.state IN ('available', 'rejected') THEN
            RAISE EXCEPTION USING ERRCODE = '55000',
              MESSAGE = 'terminal pending Artifact records are immutable';
          END IF;
          IF (to_jsonb(NEW) - ARRAY[
                'state', 'available_artifact_id', 'attempt_count', 'failure_code',
                'updated_at', 'terminal_at'
              ]) IS DISTINCT FROM
             (to_jsonb(OLD) - ARRAY[
                'state', 'available_artifact_id', 'attempt_count', 'failure_code',
                'updated_at', 'terminal_at'
              ]) THEN
            RAISE EXCEPTION USING ERRCODE = '55000',
              MESSAGE = 'pending Artifact identity and manifest are immutable';
          END IF;
          IF NEW.updated_at < OLD.updated_at OR NEW.state = OLD.state THEN
            RAISE EXCEPTION USING ERRCODE = '55000',
              MESSAGE = 'pending Artifact update requires a forward state transition';
          END IF;
          IF NOT (
            (OLD.state IN ('pending', 'retryable') AND NEW.state = 'promoting')
            OR (OLD.state = 'promoting'
              AND NEW.state IN ('available', 'retryable', 'rejected'))
          ) THEN
            RAISE EXCEPTION USING ERRCODE = '55000',
              MESSAGE = format('invalid pending Artifact transition %s -> %s',
                OLD.state, NEW.state);
          END IF;
          IF NEW.state = 'promoting' THEN
            IF NEW.attempt_count <> OLD.attempt_count + 1 THEN
              RAISE EXCEPTION USING ERRCODE = '55000',
                MESSAGE = 'promotion attempt count must advance exactly once';
            END IF;
          ELSIF NEW.attempt_count <> OLD.attempt_count THEN
            RAISE EXCEPTION USING ERRCODE = '55000',
              MESSAGE = 'promotion result cannot change attempt count';
          END IF;
          IF NEW.state = 'available' AND NOT EXISTS (
            SELECT 1 FROM artifact.artifact value
            WHERE value.organization_id = NEW.organization_id
              AND value.project_id = NEW.project_id
              AND value.classification = NEW.classification
              AND value.id = NEW.available_artifact_id
              AND value.id = NEW.reserved_artifact_id
              AND value.source_pending_id = NEW.id
          ) THEN
            RAISE EXCEPTION USING ERRCODE = '55000',
              MESSAGE = 'available pending Artifact requires its immutable Artifact';
          END IF;
          RETURN NEW;
        END
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER artifact_pending_mutation_guard
        BEFORE UPDATE OR DELETE ON artifact.artifact_pending
        FOR EACH ROW EXECUTE FUNCTION artifact.guard_pending_mutation()
        """
    )

    op.execute(
        """
        CREATE FUNCTION artifact.guard_artifact_insert()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
          IF NOT EXISTS (
            SELECT 1 FROM artifact.artifact_pending pending
            WHERE pending.organization_id = NEW.organization_id
              AND pending.project_id = NEW.project_id
              AND pending.classification = NEW.classification
              AND pending.id = NEW.source_pending_id
              AND pending.state = 'promoting'
              AND pending.reserved_artifact_id = NEW.id
              AND pending.artifact_kind = NEW.artifact_kind
              AND pending.artifact_role = NEW.artifact_role
              AND pending.schema_ref IS NOT DISTINCT FROM NEW.schema_ref
              AND pending.media_type = NEW.media_type
              AND pending.expected_size_bytes = NEW.size_bytes
              AND pending.expected_sha256 = NEW.sha256
              AND pending.final_object_key = NEW.storage_key
              AND pending.encryption_profile = NEW.encryption_profile
              AND pending.source_raw_asset_id IS NOT DISTINCT FROM NEW.source_raw_asset_id
          ) THEN
            RAISE EXCEPTION USING ERRCODE = '55000',
              MESSAGE = 'Artifact must exactly match its promoting pending manifest';
          END IF;
          IF EXISTS (
            SELECT 1 FROM artifact.artifact existing
            WHERE existing.organization_id = NEW.organization_id
              AND existing.project_id = NEW.project_id
              AND existing.classification = NEW.classification
              AND existing.storage_key = NEW.storage_key
              AND existing.encryption_profile <> NEW.encryption_profile
          ) THEN
            RAISE EXCEPTION USING ERRCODE = '55000',
              MESSAGE = 'one content object cannot claim different encryption profiles';
          END IF;
          RETURN NEW;
        END
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER artifact_manifest_insert_guard
        BEFORE INSERT ON artifact.artifact
        FOR EACH ROW EXECUTE FUNCTION artifact.guard_artifact_insert()
        """
    )
    op.execute(
        """
        CREATE TRIGGER artifact_manifest_immutable
        BEFORE UPDATE OR DELETE ON artifact.artifact
        FOR EACH ROW EXECUTE FUNCTION revisioning.reject_immutable_row_mutation()
        """
    )

    op.execute(
        """
        CREATE FUNCTION artifact.guard_integrity_observation_insert()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
          IF NOT EXISTS (
            SELECT 1 FROM artifact.artifact value
            WHERE value.organization_id = NEW.organization_id
              AND value.project_id = NEW.project_id
              AND value.classification = NEW.classification
              AND value.id = NEW.artifact_id
              AND value.sha256 = NEW.expected_sha256
              AND value.size_bytes = NEW.expected_size_bytes
          ) THEN
            RAISE EXCEPTION USING ERRCODE = '55000',
              MESSAGE = 'integrity observation differs from immutable Artifact facts';
          END IF;
          RETURN NEW;
        END
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER integrity_observation_insert_guard
        BEFORE INSERT ON artifact.integrity_observation
        FOR EACH ROW EXECUTE FUNCTION artifact.guard_integrity_observation_insert()
        """
    )
    op.execute(
        """
        CREATE TRIGGER integrity_observation_immutable
        BEFORE UPDATE OR DELETE ON artifact.integrity_observation
        FOR EACH ROW EXECUTE FUNCTION revisioning.reject_immutable_row_mutation()
        """
    )

    op.execute(
        """
        CREATE FUNCTION artifact.guard_integrity_projection_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
          IF TG_OP = 'DELETE' THEN
            RAISE EXCEPTION USING ERRCODE = '55000',
              MESSAGE = 'integrity projection cannot be deleted';
          END IF;
          IF TG_OP = 'UPDATE' THEN
            IF NEW.organization_id <> OLD.organization_id
               OR NEW.project_id <> OLD.project_id
               OR NEW.classification <> OLD.classification
               OR NEW.artifact_id <> OLD.artifact_id
               OR NEW.last_observation_id = OLD.last_observation_id
               OR NEW.last_checked_at < OLD.last_checked_at THEN
              RAISE EXCEPTION USING ERRCODE = '55000',
                MESSAGE = 'integrity projection identity/time is invalid';
            END IF;
          END IF;
          IF NOT EXISTS (
            SELECT 1 FROM artifact.integrity_observation observation
            WHERE observation.organization_id = NEW.organization_id
              AND observation.project_id = NEW.project_id
              AND observation.classification = NEW.classification
              AND observation.artifact_id = NEW.artifact_id
              AND observation.id = NEW.last_observation_id
              AND observation.status = NEW.status
              AND observation.checked_at = NEW.last_checked_at
          ) THEN
            RAISE EXCEPTION USING ERRCODE = '55000',
              MESSAGE = 'integrity projection requires its immutable observation';
          END IF;
          RETURN NEW;
        END
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER integrity_projection_mutation_guard
        BEFORE INSERT OR UPDATE OR DELETE ON artifact.integrity_projection
        FOR EACH ROW EXECUTE FUNCTION artifact.guard_integrity_projection_mutation()
        """
    )

    op.execute(
        """
        CREATE TRIGGER reconciliation_issue_immutable
        BEFORE UPDATE OR DELETE ON artifact.reconciliation_issue
        FOR EACH ROW EXECUTE FUNCTION revisioning.reject_immutable_row_mutation()
        """
    )


def _secure_tables() -> None:
    tables = (
        "artifact_pending",
        "artifact",
        "integrity_observation",
        "integrity_projection",
        "reconciliation_issue",
    )
    for table in tables:
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
        "artifact_pending": "created_by",
        "artifact": "created_by",
        "integrity_observation": "checked_by",
        "reconciliation_issue": "detected_by",
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
        CREATE POLICY integrity_projection_authorized_insert
        ON artifact.integrity_projection FOR INSERT
        WITH CHECK (
          access_control.can_access_row(
            organization_id, project_id, classification, 'artifact.write'
          )
        )
        """
    )
    for table in ("artifact_pending", "integrity_projection"):
        op.execute(
            f"""
            CREATE POLICY {table}_authorized_update
            ON artifact.{table} FOR UPDATE
            USING (
              access_control.can_access_row(
                organization_id, project_id, classification, 'artifact.write'
              )
            )
            WITH CHECK (
              access_control.can_access_row(
                organization_id, project_id, classification, 'artifact.write'
              )
            )
            """
        )


def upgrade() -> None:
    _create_content_key_function()
    _create_pending()
    _create_artifact()
    _create_integrity()
    _create_issues()
    _create_guards()
    _secure_tables()


def downgrade() -> None:
    op.execute("DROP FUNCTION artifact.guard_integrity_projection_mutation() CASCADE")
    op.execute("DROP FUNCTION artifact.guard_integrity_observation_insert() CASCADE")
    op.execute("DROP FUNCTION artifact.guard_artifact_insert() CASCADE")
    op.execute("DROP FUNCTION artifact.guard_pending_mutation() CASCADE")
    op.drop_index(
        "ix_artifact_reconciliation_issue_type_time",
        table_name="reconciliation_issue",
        schema="artifact",
    )
    op.drop_table("reconciliation_issue", schema="artifact")
    op.drop_index(
        "ix_artifact_integrity_projection_status",
        table_name="integrity_projection",
        schema="artifact",
    )
    op.drop_table("integrity_projection", schema="artifact")
    op.drop_index(
        "ix_artifact_integrity_observation_status_time",
        table_name="integrity_observation",
        schema="artifact",
    )
    op.drop_index(
        "ix_artifact_integrity_observation_artifact_time",
        table_name="integrity_observation",
        schema="artifact",
    )
    op.drop_table("integrity_observation", schema="artifact")
    op.drop_index(
        "ix_artifact_manifest_storage_key",
        table_name="artifact",
        schema="artifact",
    )
    op.drop_index(
        "ix_artifact_manifest_digest",
        table_name="artifact",
        schema="artifact",
    )
    op.drop_constraint(
        "fk_artifact_pending_available_artifact",
        "artifact_pending",
        schema="artifact",
        type_="foreignkey",
    )
    op.drop_table("artifact", schema="artifact")
    op.drop_index(
        "ix_artifact_pending_final_key",
        table_name="artifact_pending",
        schema="artifact",
    )
    op.drop_index(
        "ix_artifact_pending_state_updated",
        table_name="artifact_pending",
        schema="artifact",
    )
    op.drop_table("artifact_pending", schema="artifact")
    op.execute("DROP FUNCTION artifact.content_object_key(uuid, uuid, text, text)")

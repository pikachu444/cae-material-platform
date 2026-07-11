"""T-15 PostgreSQL Job/Attempt/Lease engine.

Traceability: T-15, FR-API-002, FR-PLG-004, NFR-DR-002, NFR-PERF-006,
NFR-SEC-002/003/006, ADR-001/002.

``jobs.job`` is the stable operational projection. ``jobs.job_attempt`` keeps one immutable
schema-validated Job Spec per execution. JSONB is limited to that named versioned contract;
resource, state, lease, result, failure, runner, and tenant fields remain explicit columns.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260711_004_t15"
down_revision: str | None = "20260711_003_t04"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_T04_ROLES = (
    "platform_admin",
    "org_admin",
    "project_admin",
    "test_engineer",
    "data_steward",
    "statistical_analyst",
    "material_modeler",
    "cae_analyst",
    "domain_reviewer",
    "release_approver",
    "consumer",
    "plugin_maintainer",
    "auditor",
)
_ROLES = (*_T04_ROLES[:-1], "job_runner", _T04_ROLES[-1])
_CLASSIFICATIONS = (
    "internal",
    "confidential",
    "restricted",
    "export_controlled",
)
_JOB_STATES = (
    "planned",
    "needs_input",
    "queued",
    "claimed",
    "running",
    "waiting_external",
    "cancel_requested",
    "succeeded",
    "failed",
    "cancelled",
    "timed_out",
)
_ATTEMPT_STATES = (
    "queued",
    "claimed",
    "running",
    "waiting_external",
    "succeeded",
    "failed",
    "cancelled",
    "timed_out",
)
_FAILURE_CATEGORIES = (
    "transient_infrastructure",
    "resource_exhausted",
    "external_unavailable",
    "domain_invalid",
    "policy_denied",
    "output_invalid",
    "deadline_exceeded",
    "internal_error",
)
_RETRY_KINDS = ("initial", "automatic", "manual", "lease_recovery")


def _quoted(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def _extend_operational_role() -> None:
    op.drop_constraint(
        "ck_role_binding_role", "role_binding", schema="identity", type_="check"
    )
    op.create_check_constraint(
        "ck_role_binding_role",
        "role_binding",
        f"role IN ({_quoted(_ROLES)})",
        schema="identity",
    )
    op.create_check_constraint(
        "ck_role_binding_job_runner_scope",
        "role_binding",
        "role <> 'job_runner' OR (subject_type = 'principal' AND project_id IS NOT NULL)",
        schema="identity",
    )


def _create_runner_tables() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    op.create_table(
        "runner",
        sa.Column("organization_id", uuid, nullable=False),
        sa.Column("project_id", uuid, nullable=False),
        sa.Column("id", uuid, nullable=False),
        sa.Column("classification", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("max_concurrency", sa.Integer(), nullable=False),
        sa.Column("cpu_capacity_millis", sa.Integer(), nullable=False),
        sa.Column("memory_capacity_mb", sa.Integer(), nullable=False),
        sa.Column("gpu_capacity", sa.Integer(), nullable=False),
        sa.Column("registered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", uuid, nullable=False),
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "organization_id <> '00000000-0000-0000-0000-000000000000'::uuid",
            name="ck_runner_nonzero_organization",
        ),
        sa.CheckConstraint(
            "project_id <> '00000000-0000-0000-0000-000000000000'::uuid",
            name="ck_runner_nonzero_project",
        ),
        sa.CheckConstraint(
            "id <> '00000000-0000-0000-0000-000000000000'::uuid",
            name="ck_runner_nonzero_id",
        ),
        sa.CheckConstraint(
            f"classification IN ({_quoted(_CLASSIFICATIONS)})",
            name="ck_runner_classification",
        ),
        sa.CheckConstraint(
            "length(btrim(name)) BETWEEN 1 AND 200", name="ck_runner_name"
        ),
        sa.CheckConstraint(
            "status IN ('active', 'draining', 'offline')", name="ck_runner_status"
        ),
        sa.CheckConstraint(
            "max_concurrency BETWEEN 1 AND 100000", name="ck_runner_concurrency"
        ),
        sa.CheckConstraint(
            "cpu_capacity_millis BETWEEN 1 AND 10000000",
            name="ck_runner_cpu_capacity",
        ),
        sa.CheckConstraint(
            "memory_capacity_mb BETWEEN 1 AND 100000000",
            name="ck_runner_memory_capacity",
        ),
        sa.CheckConstraint(
            "gpu_capacity BETWEEN 0 AND 1024", name="ck_runner_gpu_capacity"
        ),
        sa.CheckConstraint(
            "last_heartbeat_at IS NULL OR last_heartbeat_at >= registered_at",
            name="ck_runner_heartbeat_order",
        ),
        sa.PrimaryKeyConstraint(
            "organization_id", "project_id", "id", name="pk_runner"
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "classification",
            "id",
            name="uq_runner_classified_reference",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["identity.principal.id"],
            name="fk_runner_created_by",
            ondelete="RESTRICT",
        ),
        schema="jobs",
    )
    op.create_index(
        "ix_runner_tenant_status",
        "runner",
        ["organization_id", "project_id", "status"],
        schema="jobs",
    )
    op.create_table(
        "runner_job_type",
        sa.Column("organization_id", uuid, nullable=False),
        sa.Column("project_id", uuid, nullable=False),
        sa.Column("classification", sa.String(length=64), nullable=False),
        sa.Column("runner_id", uuid, nullable=False),
        sa.Column("job_type", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", uuid, nullable=False),
        sa.CheckConstraint(
            "job_type ~ '^[a-z][a-z0-9_.-]{0,99}$'",
            name="ck_runner_job_type_identifier",
        ),
        sa.PrimaryKeyConstraint(
            "organization_id",
            "project_id",
            "runner_id",
            "job_type",
            name="pk_runner_job_type",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "classification", "runner_id"],
            [
                "jobs.runner.organization_id",
                "jobs.runner.project_id",
                "jobs.runner.classification",
                "jobs.runner.id",
            ],
            name="fk_runner_job_type_runner",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["identity.principal.id"],
            name="fk_runner_job_type_created_by",
            ondelete="RESTRICT",
        ),
        schema="jobs",
    )


def _create_job_table() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    op.create_table(
        "job",
        sa.Column("organization_id", uuid, nullable=False),
        sa.Column("project_id", uuid, nullable=False),
        sa.Column("id", uuid, nullable=False),
        sa.Column("classification", sa.String(length=64), nullable=False),
        sa.Column("job_type", sa.String(length=100), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("priority", sa.SmallInteger(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255, collation="C"), nullable=False),
        sa.Column("submission_digest", sa.CHAR(length=64, collation="C"), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("submitted_by", uuid, nullable=False),
        sa.Column("request_id", uuid, nullable=False),
        sa.Column("trace_id", sa.String(length=255), nullable=False),
        sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("requested_cpu_millis", sa.Integer(), nullable=False),
        sa.Column("requested_memory_mb", sa.Integer(), nullable=False),
        sa.Column("requested_gpu_count", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.SmallInteger(), nullable=False),
        sa.Column("attempt_count", sa.SmallInteger(), nullable=False),
        sa.Column("current_attempt_id", uuid, nullable=False),
        sa.Column("cancel_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_requested_by", uuid, nullable=True),
        sa.Column("cancel_reason", sa.Text(), nullable=True),
        sa.Column("result_manifest_id", uuid, nullable=True),
        sa.Column("result_manifest_digest", sa.CHAR(length=64, collation="C"), nullable=True),
        sa.Column("failure_category", sa.String(length=64), nullable=True),
        sa.Column("failure_code", sa.String(length=100), nullable=True),
        sa.Column("failure_detail", sa.Text(), nullable=True),
        sa.Column("terminal_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("row_version", sa.BigInteger(), nullable=False),
        sa.CheckConstraint(
            "organization_id <> '00000000-0000-0000-0000-000000000000'::uuid",
            name="ck_job_nonzero_organization",
        ),
        sa.CheckConstraint(
            "project_id <> '00000000-0000-0000-0000-000000000000'::uuid",
            name="ck_job_nonzero_project",
        ),
        sa.CheckConstraint(
            "id <> '00000000-0000-0000-0000-000000000000'::uuid",
            name="ck_job_nonzero_id",
        ),
        sa.CheckConstraint(
            f"classification IN ({_quoted(_CLASSIFICATIONS)})",
            name="ck_job_classification",
        ),
        sa.CheckConstraint(
            "job_type ~ '^[a-z][a-z0-9_.-]{0,99}$'", name="ck_job_type"
        ),
        sa.CheckConstraint(
            f"state IN ({_quoted(_JOB_STATES)})", name="ck_job_state"
        ),
        sa.CheckConstraint(
            "length(idempotency_key) BETWEEN 1 AND 255",
            name="ck_job_idempotency_key",
        ),
        sa.CheckConstraint(
            "submission_digest ~ '^[0-9a-f]{64}$'", name="ck_job_submission_digest"
        ),
        sa.CheckConstraint("deadline_at > submitted_at", name="ck_job_deadline"),
        sa.CheckConstraint(
            "requested_cpu_millis BETWEEN 1 AND 10000000", name="ck_job_requested_cpu"
        ),
        sa.CheckConstraint(
            "requested_memory_mb BETWEEN 1 AND 100000000",
            name="ck_job_requested_memory",
        ),
        sa.CheckConstraint(
            "requested_gpu_count BETWEEN 0 AND 1024", name="ck_job_requested_gpu"
        ),
        sa.CheckConstraint("max_attempts BETWEEN 1 AND 100", name="ck_job_max_attempts"),
        sa.CheckConstraint(
            "attempt_count BETWEEN 1 AND max_attempts", name="ck_job_attempt_count"
        ),
        sa.CheckConstraint(
            "row_version > 0 AND updated_at >= submitted_at", name="ck_job_projection_order"
        ),
        sa.CheckConstraint(
            "(cancel_requested_at IS NULL AND cancel_requested_by IS NULL "
            "AND cancel_reason IS NULL) OR "
            "(cancel_requested_at IS NOT NULL AND cancel_requested_by IS NOT NULL "
            "AND length(btrim(cancel_reason)) BETWEEN 1 AND 2000)",
            name="ck_job_cancel_tuple",
        ),
        sa.CheckConstraint(
            "(result_manifest_id IS NULL AND result_manifest_digest IS NULL) OR "
            "(result_manifest_id IS NOT NULL "
            "AND result_manifest_digest ~ '^[0-9a-f]{64}$')",
            name="ck_job_result_tuple",
        ),
        sa.CheckConstraint(
            "(failure_category IS NULL AND failure_code IS NULL AND failure_detail IS NULL) OR "
            f"(failure_category IN ({_quoted(_FAILURE_CATEGORIES)}) "
            "AND failure_code ~ '^[a-z][a-z0-9_.-]{0,99}$' "
            "AND length(btrim(failure_detail)) BETWEEN 1 AND 4000)",
            name="ck_job_failure_tuple",
        ),
        sa.CheckConstraint(
            "(state IN ('succeeded', 'failed', 'cancelled', 'timed_out')) "
            "= (terminal_at IS NOT NULL)",
            name="ck_job_terminal_at",
        ),
        sa.CheckConstraint(
            "state <> 'succeeded' OR "
            "(result_manifest_id IS NOT NULL AND failure_category IS NULL)",
            name="ck_job_succeeded_result",
        ),
        sa.CheckConstraint(
            "state NOT IN ('failed', 'timed_out') OR failure_category IS NOT NULL",
            name="ck_job_failed_problem",
        ),
        sa.CheckConstraint(
            "state IN ('succeeded', 'failed', 'cancelled', 'timed_out') OR "
            "(result_manifest_id IS NULL AND failure_category IS NULL)",
            name="ck_job_nonterminal_payload",
        ),
        sa.CheckConstraint(
            "state <> 'cancel_requested' OR cancel_requested_at IS NOT NULL",
            name="ck_job_cancel_requested_fields",
        ),
        sa.CheckConstraint(
            "cancel_requested_at IS NULL OR state IN ("
            "'cancel_requested', 'succeeded', 'failed', 'cancelled', 'timed_out')",
            name="ck_job_cancel_state",
        ),
        sa.PrimaryKeyConstraint(
            "organization_id", "project_id", "id", name="pk_job"
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "classification",
            "id",
            name="uq_job_classified_reference",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "idempotency_key",
            name="uq_job_tenant_idempotency",
        ),
        sa.ForeignKeyConstraint(
            ["submitted_by"],
            ["identity.principal.id"],
            name="fk_job_submitted_by",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["cancel_requested_by"],
            ["identity.principal.id"],
            name="fk_job_cancel_requested_by",
            ondelete="RESTRICT",
        ),
        schema="jobs",
    )
    op.create_index(
        "ix_job_tenant_state",
        "job",
        ["organization_id", "project_id", "state", "job_type", "updated_at"],
        schema="jobs",
    )
    op.create_index(
        "ix_job_queue_claim",
        "job",
        [
            "organization_id",
            "project_id",
            "priority",
            "submitted_at",
            "id",
        ],
        schema="jobs",
        postgresql_where=sa.text("state = 'queued'"),
    )


def _create_attempt_table() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    op.create_table(
        "job_attempt",
        sa.Column("organization_id", uuid, nullable=False),
        sa.Column("project_id", uuid, nullable=False),
        sa.Column("classification", sa.String(length=64), nullable=False),
        sa.Column("id", uuid, nullable=False),
        sa.Column("job_id", uuid, nullable=False),
        sa.Column("attempt_no", sa.SmallInteger(), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("retry_kind", sa.String(length=32), nullable=False),
        sa.Column("retry_reason", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", uuid, nullable=False),
        sa.Column("job_spec", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("job_spec_digest", sa.CHAR(length=64, collation="C"), nullable=False),
        sa.Column("runner_id", uuid, nullable=True),
        sa.Column("lease_token", uuid, nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("progress_fraction", sa.Numeric(precision=7, scale=6), nullable=True),
        sa.Column("progress_phase", sa.String(length=255), nullable=True),
        sa.Column("progress_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("result_manifest_id", uuid, nullable=True),
        sa.Column("result_manifest_digest", sa.CHAR(length=64, collation="C"), nullable=True),
        sa.Column("failure_category", sa.String(length=64), nullable=True),
        sa.Column("failure_code", sa.String(length=100), nullable=True),
        sa.Column("failure_detail", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "id <> '00000000-0000-0000-0000-000000000000'::uuid",
            name="ck_job_attempt_nonzero_id",
        ),
        sa.CheckConstraint("attempt_no BETWEEN 1 AND 100", name="ck_job_attempt_number"),
        sa.CheckConstraint(
            f"state IN ({_quoted(_ATTEMPT_STATES)})", name="ck_job_attempt_state"
        ),
        sa.CheckConstraint(
            f"retry_kind IN ({_quoted(_RETRY_KINDS)})", name="ck_job_attempt_retry_kind"
        ),
        sa.CheckConstraint(
            "length(btrim(retry_reason)) BETWEEN 1 AND 2000",
            name="ck_job_attempt_retry_reason",
        ),
        sa.CheckConstraint(
            "job_spec->>'job_spec_version' = '1.0' "
            "AND (job_spec->>'job_id')::uuid = job_id "
            "AND (job_spec->>'attempt_id')::uuid = id",
            name="ck_job_attempt_spec_identity",
        ),
        sa.CheckConstraint(
            "job_spec_digest ~ '^[0-9a-f]{64}$'", name="ck_job_attempt_spec_digest"
        ),
        sa.CheckConstraint(
            "(runner_id IS NULL AND lease_token IS NULL AND lease_expires_at IS NULL "
            "AND heartbeat_at IS NULL AND claimed_at IS NULL) OR "
            "(runner_id IS NOT NULL AND lease_token IS NOT NULL "
            "AND lease_expires_at IS NOT NULL AND heartbeat_at IS NOT NULL "
            "AND claimed_at IS NOT NULL)",
            name="ck_job_attempt_lease_tuple",
        ),
        sa.CheckConstraint(
            "state NOT IN ('claimed', 'running', 'waiting_external') OR runner_id IS NOT NULL",
            name="ck_job_attempt_active_lease",
        ),
        sa.CheckConstraint(
            "lease_expires_at IS NULL OR lease_expires_at > heartbeat_at",
            name="ck_job_attempt_lease_order",
        ),
        sa.CheckConstraint(
            "started_at IS NULL OR (claimed_at IS NOT NULL AND started_at >= claimed_at)",
            name="ck_job_attempt_start_order",
        ),
        sa.CheckConstraint(
            "(state IN ('succeeded', 'failed', 'cancelled', 'timed_out')) "
            "= (ended_at IS NOT NULL)",
            name="ck_job_attempt_terminal_at",
        ),
        sa.CheckConstraint(
            "ended_at IS NULL OR ended_at >= COALESCE(started_at, claimed_at, created_at)",
            name="ck_job_attempt_end_order",
        ),
        sa.CheckConstraint(
            "progress_fraction IS NULL OR progress_fraction BETWEEN 0 AND 1",
            name="ck_job_attempt_progress_fraction",
        ),
        sa.CheckConstraint(
            "(progress_fraction IS NULL AND progress_phase IS NULL "
            "AND progress_updated_at IS NULL) OR "
            "(progress_updated_at IS NOT NULL "
            "AND (progress_fraction IS NOT NULL OR "
            "length(btrim(progress_phase)) BETWEEN 1 AND 255))",
            name="ck_job_attempt_progress_tuple",
        ),
        sa.CheckConstraint(
            "(result_manifest_id IS NULL AND result_manifest_digest IS NULL) OR "
            "(result_manifest_id IS NOT NULL "
            "AND result_manifest_digest ~ '^[0-9a-f]{64}$')",
            name="ck_job_attempt_result_tuple",
        ),
        sa.CheckConstraint(
            "(failure_category IS NULL AND failure_code IS NULL AND failure_detail IS NULL) OR "
            f"(failure_category IN ({_quoted(_FAILURE_CATEGORIES)}) "
            "AND failure_code ~ '^[a-z][a-z0-9_.-]{0,99}$' "
            "AND length(btrim(failure_detail)) BETWEEN 1 AND 4000)",
            name="ck_job_attempt_failure_tuple",
        ),
        sa.CheckConstraint(
            "state <> 'succeeded' OR "
            "(result_manifest_id IS NOT NULL AND failure_category IS NULL)",
            name="ck_job_attempt_succeeded_result",
        ),
        sa.CheckConstraint(
            "state NOT IN ('failed', 'timed_out') OR failure_category IS NOT NULL",
            name="ck_job_attempt_failed_problem",
        ),
        sa.CheckConstraint(
            "state IN ('succeeded', 'failed', 'cancelled', 'timed_out') OR "
            "(result_manifest_id IS NULL AND failure_category IS NULL)",
            name="ck_job_attempt_nonterminal_payload",
        ),
        sa.PrimaryKeyConstraint(
            "organization_id", "project_id", "id", name="pk_job_attempt"
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "classification",
            "job_id",
            "id",
            name="uq_job_attempt_current_reference",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "job_id",
            "attempt_no",
            name="uq_job_attempt_number",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "classification", "job_id"],
            [
                "jobs.job.organization_id",
                "jobs.job.project_id",
                "jobs.job.classification",
                "jobs.job.id",
            ],
            name="fk_job_attempt_job",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "runner_id"],
            ["jobs.runner.organization_id", "jobs.runner.project_id", "jobs.runner.id"],
            name="fk_job_attempt_runner",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["identity.principal.id"],
            name="fk_job_attempt_created_by",
            ondelete="RESTRICT",
        ),
        schema="jobs",
    )
    op.create_foreign_key(
        "fk_job_current_attempt",
        "job",
        "job_attempt",
        ["organization_id", "project_id", "classification", "id", "current_attempt_id"],
        ["organization_id", "project_id", "classification", "job_id", "id"],
        source_schema="jobs",
        referent_schema="jobs",
        ondelete="RESTRICT",
        deferrable=True,
        initially="DEFERRED",
    )
    op.create_index(
        "ix_job_attempt_job_history",
        "job_attempt",
        ["organization_id", "project_id", "job_id", "attempt_no"],
        schema="jobs",
    )
    op.create_index(
        "ix_job_attempt_expired_lease",
        "job_attempt",
        ["organization_id", "project_id", "lease_expires_at", "id"],
        schema="jobs",
        postgresql_where=sa.text("state IN ('claimed', 'running', 'waiting_external')"),
    )
    op.create_index(
        "ix_job_attempt_runner_active",
        "job_attempt",
        ["organization_id", "project_id", "runner_id", "state", "lease_expires_at"],
        schema="jobs",
        postgresql_where=sa.text("state IN ('claimed', 'running', 'waiting_external')"),
    )
    op.create_index(
        "uq_job_succeeded_manifest_digest",
        "job_attempt",
        ["organization_id", "project_id", "job_id", "result_manifest_digest"],
        unique=True,
        schema="jobs",
        postgresql_where=sa.text("state = 'succeeded'"),
    )


def _create_mutation_guards() -> None:
    op.execute(
        """
        CREATE FUNCTION jobs.guard_job_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
          transition_allowed boolean;
        BEGIN
          IF TG_OP = 'DELETE' THEN
            RAISE EXCEPTION USING ERRCODE = '55000', MESSAGE = 'jobs.job rows cannot be deleted';
          END IF;
          IF (to_jsonb(NEW) - ARRAY[
                'state', 'attempt_count', 'current_attempt_id',
                'cancel_requested_at', 'cancel_requested_by', 'cancel_reason',
                'result_manifest_id', 'result_manifest_digest',
                'failure_category', 'failure_code', 'failure_detail',
                'terminal_at', 'updated_at', 'row_version'
              ]) IS DISTINCT FROM
             (to_jsonb(OLD) - ARRAY[
                'state', 'attempt_count', 'current_attempt_id',
                'cancel_requested_at', 'cancel_requested_by', 'cancel_reason',
                'result_manifest_id', 'result_manifest_digest',
                'failure_category', 'failure_code', 'failure_detail',
                'terminal_at', 'updated_at', 'row_version'
              ]) THEN
            RAISE EXCEPTION USING
              ERRCODE = '55000',
              MESSAGE = 'job identity, submission, resource policy, and tenant are immutable';
          END IF;
          IF OLD.cancel_requested_at IS NOT NULL AND (
              NEW.cancel_requested_at IS DISTINCT FROM OLD.cancel_requested_at
              OR NEW.cancel_requested_by IS DISTINCT FROM OLD.cancel_requested_by
              OR NEW.cancel_reason IS DISTINCT FROM OLD.cancel_reason
          ) THEN
            RAISE EXCEPTION USING
              ERRCODE = '55000', MESSAGE = 'job cancellation request facts are immutable';
          END IF;
          IF OLD.state IN ('succeeded', 'failed', 'cancelled', 'timed_out')
             AND NEW.state = OLD.state THEN
            RAISE EXCEPTION USING
              ERRCODE = '55000', MESSAGE = 'terminal job projections are immutable';
          END IF;
          IF NEW.row_version <> OLD.row_version + 1 OR NEW.updated_at < OLD.updated_at THEN
            RAISE EXCEPTION USING
              ERRCODE = '40001',
              MESSAGE = 'job projection version and time must advance exactly once';
          END IF;
          IF NEW.state IS DISTINCT FROM OLD.state THEN
            transition_allowed := CASE OLD.state
              WHEN 'planned' THEN NEW.state IN (
                'needs_input', 'queued', 'failed', 'cancel_requested', 'cancelled'
              )
              WHEN 'needs_input' THEN NEW.state IN (
                'queued', 'failed', 'cancel_requested', 'cancelled'
              )
              WHEN 'queued' THEN NEW.state IN ('claimed', 'cancelled', 'timed_out')
              WHEN 'claimed' THEN NEW.state IN (
                'running', 'cancel_requested', 'failed', 'timed_out'
              )
              WHEN 'running' THEN NEW.state IN (
                'waiting_external', 'cancel_requested', 'succeeded', 'failed',
                'cancelled', 'timed_out'
              )
              WHEN 'waiting_external' THEN NEW.state IN (
                'running', 'cancel_requested', 'succeeded', 'failed', 'cancelled', 'timed_out'
              )
              WHEN 'cancel_requested' THEN NEW.state IN (
                'succeeded', 'failed', 'cancelled', 'timed_out'
              )
              WHEN 'failed' THEN NEW.state = 'queued'
              WHEN 'timed_out' THEN NEW.state = 'queued'
              ELSE false
            END;
            IF NOT COALESCE(transition_allowed, false) THEN
              RAISE EXCEPTION USING
                ERRCODE = '55000',
                MESSAGE = format('invalid job transition %s -> %s', OLD.state, NEW.state);
            END IF;
            IF OLD.state IN ('failed', 'timed_out') AND NEW.state = 'queued' THEN
              IF NEW.attempt_count <> OLD.attempt_count + 1
                 OR NEW.current_attempt_id = OLD.current_attempt_id THEN
                RAISE EXCEPTION USING
                  ERRCODE = '55000',
                  MESSAGE = 'retry must advance to a distinct new attempt';
              END IF;
            ELSIF NEW.attempt_count <> OLD.attempt_count
                  OR NEW.current_attempt_id <> OLD.current_attempt_id THEN
              RAISE EXCEPTION USING
                ERRCODE = '55000',
                MESSAGE = 'attempt pointer can change only during explicit retry';
            END IF;
          ELSIF NEW.attempt_count <> OLD.attempt_count
                OR NEW.current_attempt_id <> OLD.current_attempt_id THEN
            RAISE EXCEPTION USING
              ERRCODE = '55000',
              MESSAGE = 'attempt pointer cannot change without retry transition';
          END IF;
          RETURN NEW;
        END
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER job_mutation_guard
        BEFORE UPDATE OR DELETE ON jobs.job
        FOR EACH ROW EXECUTE FUNCTION jobs.guard_job_mutation()
        """
    )
    op.execute(
        """
        CREATE FUNCTION jobs.guard_job_attempt_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
          transition_allowed boolean;
        BEGIN
          IF TG_OP = 'DELETE' THEN
            RAISE EXCEPTION USING
              ERRCODE = '55000', MESSAGE = 'jobs.job_attempt rows cannot be deleted';
          END IF;
          IF OLD.state IN ('succeeded', 'failed', 'cancelled', 'timed_out') THEN
            RAISE EXCEPTION USING
              ERRCODE = '55000', MESSAGE = 'terminal job attempts are immutable';
          END IF;
          IF (to_jsonb(NEW) - ARRAY[
                'state', 'runner_id', 'lease_token', 'lease_expires_at', 'heartbeat_at',
                'claimed_at', 'started_at', 'ended_at',
                'progress_fraction', 'progress_phase', 'progress_updated_at',
                'result_manifest_id', 'result_manifest_digest',
                'failure_category', 'failure_code', 'failure_detail'
              ]) IS DISTINCT FROM
             (to_jsonb(OLD) - ARRAY[
                'state', 'runner_id', 'lease_token', 'lease_expires_at', 'heartbeat_at',
                'claimed_at', 'started_at', 'ended_at',
                'progress_fraction', 'progress_phase', 'progress_updated_at',
                'result_manifest_id', 'result_manifest_digest',
                'failure_category', 'failure_code', 'failure_detail'
              ]) THEN
            RAISE EXCEPTION USING
              ERRCODE = '55000',
              MESSAGE = 'attempt identity, Job Spec, digest, retry facts, and tenant are immutable';
          END IF;
          IF OLD.runner_id IS NOT NULL AND (
              NEW.runner_id IS DISTINCT FROM OLD.runner_id
              OR NEW.lease_token IS DISTINCT FROM OLD.lease_token
              OR NEW.claimed_at IS DISTINCT FROM OLD.claimed_at
          ) THEN
            RAISE EXCEPTION USING
              ERRCODE = '55000', MESSAGE = 'attempt lease ownership is fenced and immutable';
          END IF;
          IF OLD.heartbeat_at IS NOT NULL AND NEW.heartbeat_at < OLD.heartbeat_at THEN
            RAISE EXCEPTION USING
              ERRCODE = '55000', MESSAGE = 'attempt heartbeat cannot move backwards';
          END IF;
          IF OLD.lease_expires_at IS NOT NULL
             AND NEW.lease_expires_at < OLD.lease_expires_at THEN
            RAISE EXCEPTION USING
              ERRCODE = '55000', MESSAGE = 'attempt lease expiry cannot move backwards';
          END IF;
          IF OLD.started_at IS NOT NULL AND NEW.started_at IS DISTINCT FROM OLD.started_at THEN
            RAISE EXCEPTION USING
              ERRCODE = '55000', MESSAGE = 'attempt start time is immutable once set';
          END IF;
          IF OLD.progress_fraction IS NOT NULL
             AND NEW.progress_fraction < OLD.progress_fraction THEN
            RAISE EXCEPTION USING
              ERRCODE = '55000', MESSAGE = 'attempt progress cannot move backwards';
          END IF;
          IF NEW.state IS DISTINCT FROM OLD.state THEN
            transition_allowed := CASE OLD.state
              WHEN 'queued' THEN NEW.state IN ('claimed', 'cancelled', 'timed_out')
              WHEN 'claimed' THEN NEW.state IN ('running', 'failed', 'cancelled', 'timed_out')
              WHEN 'running' THEN NEW.state IN (
                'waiting_external', 'succeeded', 'failed', 'cancelled', 'timed_out'
              )
              WHEN 'waiting_external' THEN NEW.state IN (
                'running', 'succeeded', 'failed', 'cancelled', 'timed_out'
              )
              ELSE false
            END;
            IF NOT COALESCE(transition_allowed, false) THEN
              RAISE EXCEPTION USING
                ERRCODE = '55000',
                MESSAGE = format('invalid attempt transition %s -> %s', OLD.state, NEW.state);
            END IF;
          END IF;
          RETURN NEW;
        END
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER job_attempt_mutation_guard
        BEFORE UPDATE OR DELETE ON jobs.job_attempt
        FOR EACH ROW EXECUTE FUNCTION jobs.guard_job_attempt_mutation()
        """
    )


def _secure_tables() -> None:
    for table in ("runner", "runner_job_type", "job", "job_attempt"):
        op.execute(f"ALTER TABLE jobs.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE jobs.{table} FORCE ROW LEVEL SECURITY")

    for table in ("job", "job_attempt"):
        op.execute(
            f"""
            CREATE POLICY {table}_authorized_select
            ON jobs.{table} FOR SELECT
            USING (
              access_control.can_access_row(
                organization_id, project_id, classification, 'job.read'
              )
            )
            """
        )
    op.execute(
        """
        CREATE POLICY job_authorized_insert
        ON jobs.job FOR INSERT
        WITH CHECK (
          access_control.can_access_row(
            organization_id, project_id, classification, 'job.submit'
          )
          AND submitted_by = access_control.current_principal_id()
        )
        """
    )
    op.execute(
        """
        CREATE POLICY job_authorized_update
        ON jobs.job FOR UPDATE
        USING (
          access_control.can_access_row(
            organization_id, project_id, classification, 'job.control'
          )
          OR access_control.can_access_row(
            organization_id, project_id, classification, 'job.execute'
          )
        )
        WITH CHECK (
          access_control.can_access_row(
            organization_id, project_id, classification, 'job.control'
          )
          OR access_control.can_access_row(
            organization_id, project_id, classification, 'job.execute'
          )
        )
        """
    )
    op.execute(
        """
        CREATE POLICY job_attempt_authorized_insert
        ON jobs.job_attempt FOR INSERT
        WITH CHECK (
          access_control.can_access_row(
            organization_id, project_id, classification, 'job.submit'
          )
          OR access_control.can_access_row(
            organization_id, project_id, classification, 'job.control'
          )
          OR access_control.can_access_row(
            organization_id, project_id, classification, 'job.execute'
          )
        )
        """
    )
    op.execute(
        """
        CREATE POLICY job_attempt_authorized_update
        ON jobs.job_attempt FOR UPDATE
        USING (
          access_control.can_access_row(
            organization_id, project_id, classification, 'job.execute'
          )
          OR (
            state = 'queued'
            AND access_control.can_access_row(
              organization_id, project_id, classification, 'job.control'
            )
          )
        )
        WITH CHECK (
          access_control.can_access_row(
            organization_id, project_id, classification, 'job.execute'
          )
          OR access_control.can_access_row(
            organization_id, project_id, classification, 'job.control'
          )
        )
        """
    )
    for table in ("runner", "runner_job_type"):
        op.execute(
            f"""
            CREATE POLICY {table}_authorized_select
            ON jobs.{table} FOR SELECT
            USING (
              access_control.can_access_row(
                organization_id, project_id, classification, 'job.execute'
              )
              OR access_control.can_access_row(
                organization_id, project_id, classification, 'platform.manage'
              )
            )
            """
        )
        op.execute(
            f"""
            CREATE POLICY {table}_platform_insert
            ON jobs.{table} FOR INSERT
            WITH CHECK (
              access_control.can_access_row(
                organization_id, project_id, classification, 'platform.manage'
              )
            )
            """
        )
    op.execute(
        """
        CREATE POLICY runner_execute_update
        ON jobs.runner FOR UPDATE
        USING (
          access_control.can_access_row(
            organization_id, project_id, classification, 'job.execute'
          )
          OR access_control.can_access_row(
            organization_id, project_id, classification, 'platform.manage'
          )
        )
        WITH CHECK (
          access_control.can_access_row(
            organization_id, project_id, classification, 'job.execute'
          )
          OR access_control.can_access_row(
            organization_id, project_id, classification, 'platform.manage'
          )
        )
        """
    )


def upgrade() -> None:
    _extend_operational_role()
    op.execute("CREATE SCHEMA jobs")
    _create_runner_tables()
    _create_job_table()
    _create_attempt_table()
    _create_mutation_guards()
    _secure_tables()


def _restore_t04_role_constraint() -> None:
    op.drop_constraint(
        "ck_role_binding_job_runner_scope",
        "role_binding",
        schema="identity",
        type_="check",
    )
    op.drop_constraint(
        "ck_role_binding_role", "role_binding", schema="identity", type_="check"
    )
    op.create_check_constraint(
        "ck_role_binding_role",
        "role_binding",
        f"role IN ({_quoted(_T04_ROLES)})",
        schema="identity",
    )


def downgrade() -> None:
    op.execute("DROP FUNCTION jobs.guard_job_attempt_mutation() CASCADE")
    op.execute("DROP FUNCTION jobs.guard_job_mutation() CASCADE")
    op.drop_constraint(
        "fk_job_current_attempt", "job", schema="jobs", type_="foreignkey"
    )
    op.drop_index(
        "uq_job_succeeded_manifest_digest", table_name="job_attempt", schema="jobs"
    )
    op.drop_index("ix_job_attempt_runner_active", table_name="job_attempt", schema="jobs")
    op.drop_index("ix_job_attempt_expired_lease", table_name="job_attempt", schema="jobs")
    op.drop_index("ix_job_attempt_job_history", table_name="job_attempt", schema="jobs")
    op.drop_table("job_attempt", schema="jobs")
    op.drop_index("ix_job_queue_claim", table_name="job", schema="jobs")
    op.drop_index("ix_job_tenant_state", table_name="job", schema="jobs")
    op.drop_table("job", schema="jobs")
    op.drop_table("runner_job_type", schema="jobs")
    op.drop_index("ix_runner_tenant_status", table_name="runner", schema="jobs")
    op.drop_table("runner", schema="jobs")
    op.execute("DROP SCHEMA jobs")
    _restore_t04_role_constraint()

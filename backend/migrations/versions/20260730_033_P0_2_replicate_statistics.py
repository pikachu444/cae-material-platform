"""Add typed multi-replicate Statistics/QC Plan, Run, Result, and member tables.

Revision ID: 20260730_033_p02
Revises: 20260729_032_p02
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260730_033_p02"
down_revision: str | None = "20260729_032_p02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ZERO = "'00000000-0000-0000-0000-000000000000'::uuid"
_KIND = "reference_tensile_replicate_scalar_and_curve"
_PLAN_SCHEMA = "urn:cmp:statistics:reference-tensile-replicate-plan:1.0.0"
_RESULT_SCHEMA = "urn:cmp:statistics:reference-tensile-replicate-result:1.0.0"
_CURVE_SCHEMA = "urn:cmp:statistics:reference-tensile-replicate-curve-parquet:1.0.0"
_GRID_POLICY = "exact_processed_grid_match_no_alignment"
_QUANTILE = "linear_inclusive"
_CI_METHOD = "student_t_95_two_sided"
_SCALAR = "peak_engineering_stress_pa"


def _identity_columns(uuid: postgresql.UUID) -> list[sa.Column[object]]:
    return [
        sa.Column("id", uuid, nullable=False),
        sa.Column("organization_id", uuid, nullable=False),
        sa.Column("project_id", uuid, nullable=False),
        sa.Column("classification", sa.String(64), nullable=False),
        sa.Column("current_revision_id", uuid, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", uuid, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]


def _revision_columns(uuid: postgresql.UUID) -> list[sa.Column[object]]:
    return [
        sa.Column("id", uuid, nullable=False),
        sa.Column("aggregate_id", uuid, nullable=False),
        sa.Column("organization_id", uuid, nullable=False),
        sa.Column("project_id", uuid, nullable=False),
        sa.Column("classification", sa.String(64), nullable=False),
        sa.Column("revision_no", sa.BigInteger(), nullable=False),
        sa.Column("based_on_revision_id", uuid, nullable=True),
        sa.Column("schema_id", sa.String(255), nullable=False),
        sa.Column("schema_version", sa.String(64), nullable=False),
        sa.Column("content_hash", sa.CHAR(64, collation="C"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", uuid, nullable=False),
        sa.Column("change_reason", sa.Text(), nullable=False),
        sa.Column("request_id", uuid, nullable=False),
        sa.Column("trace_id", sa.String(255), nullable=False),
    ]


def _identity_constraints(prefix: str) -> list[sa.Constraint]:
    return [
        sa.PrimaryKeyConstraint("organization_id", "project_id", "id", name=f"pk_{prefix}"),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "classification",
            "id",
            name=f"uq_{prefix}_scoped",
        ),
        sa.CheckConstraint(
            f"id <> {_ZERO} AND current_revision_id <> {_ZERO} AND created_by <> {_ZERO}",
            name=f"ck_{prefix}_ids",
        ),
        sa.CheckConstraint(
            "classification ~ '^[a-z][a-z0-9_.-]{0,63}$'",
            name=f"ck_{prefix}_classification",
        ),
    ]


def _revision_constraints(prefix: str) -> list[sa.Constraint]:
    return [
        sa.PrimaryKeyConstraint(
            "organization_id", "project_id", "id", name=f"pk_{prefix}_revision"
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "aggregate_id",
            "id",
            name=f"uq_{prefix}_revision_id",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "classification",
            "aggregate_id",
            "id",
            name=f"uq_{prefix}_revision_scoped",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "aggregate_id",
            "revision_no",
            name=f"uq_{prefix}_revision_no",
        ),
        sa.CheckConstraint(
            f"id <> {_ZERO} AND aggregate_id <> {_ZERO} AND created_by <> {_ZERO} "
            f"AND request_id <> {_ZERO}",
            name=f"ck_{prefix}_revision_ids",
        ),
        sa.CheckConstraint("revision_no > 0", name=f"ck_{prefix}_revision_no"),
        sa.CheckConstraint(
            "(revision_no = 1 AND based_on_revision_id IS NULL) OR "
            "(revision_no > 1 AND based_on_revision_id IS NOT NULL)",
            name=f"ck_{prefix}_revision_base",
        ),
        sa.CheckConstraint("content_hash ~ '^[0-9a-f]{64}$'", name=f"ck_{prefix}_revision_hash"),
        sa.CheckConstraint(
            "length(btrim(change_reason)) BETWEEN 1 AND 2000",
            name=f"ck_{prefix}_revision_reason",
        ),
        sa.CheckConstraint(
            "length(btrim(trace_id)) BETWEEN 1 AND 255",
            name=f"ck_{prefix}_revision_trace",
        ),
    ]


def _secure(table: str, *, mutable: bool = True) -> None:
    op.execute(f"ALTER TABLE statistics.{table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE statistics.{table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY statistics_{table}_select ON statistics.{table} FOR SELECT "
        "USING (access_control.can_access_row(organization_id, project_id, "
        "classification, 'statistics.read'))"
    )
    op.execute(
        f"CREATE POLICY statistics_{table}_insert ON statistics.{table} FOR INSERT "
        "WITH CHECK (access_control.can_access_row(organization_id, project_id, "
        "classification, 'statistics.execute'))"
    )
    if mutable:
        op.execute(
            f"CREATE POLICY statistics_{table}_update ON statistics.{table} FOR UPDATE "
            "USING (access_control.can_access_row(organization_id, project_id, "
            "classification, 'statistics.execute')) WITH CHECK "
            "(access_control.can_access_row(organization_id, project_id, "
            "classification, 'statistics.execute'))"
        )


def _create_plan_tables() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    op.create_table(
        "replicate_statistical_plan",
        *_identity_columns(uuid),
        sa.Column("plan_label", sa.String(160), nullable=False),
        sa.Column("plan_kind", sa.String(100), nullable=False),
        *_identity_constraints("statistics_replicate_plan"),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "classification",
            "plan_label",
            name="uq_statistics_replicate_plan_label",
        ),
        sa.CheckConstraint(
            "length(btrim(plan_label)) BETWEEN 1 AND 160 AND plan_label = btrim(plan_label)",
            name="ck_statistics_replicate_plan_label",
        ),
        sa.CheckConstraint(f"plan_kind = '{_KIND}'", name="ck_statistics_replicate_plan_kind"),
        schema="statistics",
    )
    op.create_table(
        "replicate_statistical_plan_revision",
        *_revision_columns(uuid),
        sa.Column("plan_kind", sa.String(100), nullable=False),
        sa.Column("selection_id", uuid, nullable=False),
        sa.Column("selection_revision_id", uuid, nullable=False),
        sa.Column("sample_count", sa.SmallInteger(), nullable=False),
        sa.Column("required_input_representation", sa.String(32), nullable=False),
        sa.Column("scalar_feature", sa.String(100), nullable=False),
        sa.Column("curve_grid_policy", sa.String(100), nullable=False),
        sa.Column("quantile_method", sa.String(100), nullable=False),
        sa.Column("confidence_interval_method", sa.String(100), nullable=False),
        sa.Column("curve_output_schema_ref", sa.String(500), nullable=False),
        *_revision_constraints("statistics_replicate_plan"),
        sa.CheckConstraint(f"plan_kind = '{_KIND}'", name="ck_statistics_replicate_plan_rev_kind"),
        sa.CheckConstraint(
            "sample_count BETWEEN 2 AND 50", name="ck_statistics_replicate_plan_rev_n"
        ),
        sa.CheckConstraint(
            "required_input_representation = 'processed'",
            name="ck_statistics_replicate_plan_rev_representation",
        ),
        sa.CheckConstraint(
            f"scalar_feature = '{_SCALAR}'",
            name="ck_statistics_replicate_plan_rev_scalar",
        ),
        sa.CheckConstraint(
            f"curve_grid_policy = '{_GRID_POLICY}'",
            name="ck_statistics_replicate_plan_rev_grid",
        ),
        sa.CheckConstraint(
            f"quantile_method = '{_QUANTILE}'",
            name="ck_statistics_replicate_plan_rev_quantile",
        ),
        sa.CheckConstraint(
            f"confidence_interval_method = '{_CI_METHOD}'",
            name="ck_statistics_replicate_plan_rev_ci",
        ),
        sa.CheckConstraint(
            f"curve_output_schema_ref = '{_CURVE_SCHEMA}'",
            name="ck_statistics_replicate_plan_rev_curve_schema",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "aggregate_id"],
            [
                "statistics.replicate_statistical_plan.organization_id",
                "statistics.replicate_statistical_plan.project_id",
                "statistics.replicate_statistical_plan.id",
            ],
            name="fk_statistics_replicate_plan_rev_identity",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "aggregate_id", "based_on_revision_id"],
            [
                "statistics.replicate_statistical_plan_revision.organization_id",
                "statistics.replicate_statistical_plan_revision.project_id",
                "statistics.replicate_statistical_plan_revision.aggregate_id",
                "statistics.replicate_statistical_plan_revision.id",
            ],
            name="fk_statistics_replicate_plan_rev_base",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.ForeignKeyConstraint(
            [
                "organization_id",
                "project_id",
                "classification",
                "selection_id",
                "selection_revision_id",
            ],
            [
                "datasets.dataset_selection_revision.organization_id",
                "datasets.dataset_selection_revision.project_id",
                "datasets.dataset_selection_revision.classification",
                "datasets.dataset_selection_revision.aggregate_id",
                "datasets.dataset_selection_revision.id",
            ],
            name="fk_statistics_replicate_plan_rev_selection",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        schema="statistics",
    )
    op.create_foreign_key(
        "fk_statistics_replicate_plan_current",
        "replicate_statistical_plan",
        "replicate_statistical_plan_revision",
        ["organization_id", "project_id", "id", "current_revision_id"],
        ["organization_id", "project_id", "aggregate_id", "id"],
        source_schema="statistics",
        referent_schema="statistics",
        ondelete="RESTRICT",
        deferrable=True,
        initially="DEFERRED",
    )


def _create_run_tables() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    op.create_table(
        "replicate_statistical_run",
        sa.Column("id", uuid, nullable=False),
        sa.Column("organization_id", uuid, nullable=False),
        sa.Column("project_id", uuid, nullable=False),
        sa.Column("classification", sa.String(64), nullable=False),
        sa.Column("plan_id", uuid, nullable=False),
        sa.Column("plan_revision_id", uuid, nullable=False),
        sa.Column("selection_id", uuid, nullable=False),
        sa.Column("selection_revision_id", uuid, nullable=False),
        sa.Column("execution_mode", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("sample_count", sa.SmallInteger(), nullable=False),
        sa.Column("result_id", uuid, nullable=True),
        sa.Column("result_revision_id", uuid, nullable=True),
        sa.Column("curve_artifact_id", uuid, nullable=True),
        sa.Column("curve_sha256", sa.CHAR(64, collation="C"), nullable=True),
        sa.Column("curve_point_count", sa.BigInteger(), nullable=True),
        sa.Column("failure_code", sa.String(100), nullable=True),
        sa.Column("change_reason", sa.Text(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", uuid, nullable=False),
        sa.Column("request_id", uuid, nullable=False),
        sa.Column("trace_id", sa.String(255), nullable=False),
        sa.PrimaryKeyConstraint(
            "organization_id", "project_id", "id", name="pk_statistics_replicate_run"
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "classification",
            "id",
            name="uq_statistics_replicate_run_scoped",
        ),
        sa.CheckConstraint(
            f"id <> {_ZERO} AND plan_id <> {_ZERO} AND plan_revision_id <> {_ZERO} "
            f"AND selection_id <> {_ZERO} AND selection_revision_id <> {_ZERO} "
            f"AND created_by <> {_ZERO} AND request_id <> {_ZERO}",
            name="ck_statistics_replicate_run_ids",
        ),
        sa.CheckConstraint("execution_mode = 'committed'", name="ck_statistics_replicate_run_mode"),
        sa.CheckConstraint(
            "status IN ('executing', 'succeeded', 'failed')",
            name="ck_statistics_replicate_run_status",
        ),
        sa.CheckConstraint("sample_count BETWEEN 2 AND 50", name="ck_statistics_replicate_run_n"),
        sa.CheckConstraint(
            "(status = 'executing' AND ended_at IS NULL AND result_id IS NULL AND "
            "result_revision_id IS NULL AND curve_artifact_id IS NULL AND curve_sha256 IS NULL "
            "AND curve_point_count IS NULL AND failure_code IS NULL) OR "
            "(status = 'succeeded' AND ended_at IS NOT NULL AND result_id IS NOT NULL AND "
            "result_revision_id IS NOT NULL AND curve_artifact_id IS NOT NULL AND "
            "curve_sha256 ~ '^[0-9a-f]{64}$' AND curve_point_count BETWEEN 2 AND 100000 "
            "AND failure_code IS NULL) OR "
            "(status = 'failed' AND ended_at IS NOT NULL AND result_id IS NULL AND "
            "result_revision_id IS NULL AND curve_artifact_id IS NULL AND curve_sha256 IS NULL "
            "AND curve_point_count IS NULL AND length(btrim(failure_code)) BETWEEN 1 AND 100)",
            name="ck_statistics_replicate_run_terminal",
        ),
        sa.CheckConstraint(
            "ended_at IS NULL OR ended_at >= started_at",
            name="ck_statistics_replicate_run_time",
        ),
        sa.CheckConstraint(
            "length(btrim(change_reason)) BETWEEN 1 AND 2000",
            name="ck_statistics_replicate_run_reason",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "classification", "plan_id", "plan_revision_id"],
            [
                "statistics.replicate_statistical_plan_revision.organization_id",
                "statistics.replicate_statistical_plan_revision.project_id",
                "statistics.replicate_statistical_plan_revision.classification",
                "statistics.replicate_statistical_plan_revision.aggregate_id",
                "statistics.replicate_statistical_plan_revision.id",
            ],
            name="fk_statistics_replicate_run_plan",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.ForeignKeyConstraint(
            [
                "organization_id",
                "project_id",
                "classification",
                "selection_id",
                "selection_revision_id",
            ],
            [
                "datasets.dataset_selection_revision.organization_id",
                "datasets.dataset_selection_revision.project_id",
                "datasets.dataset_selection_revision.classification",
                "datasets.dataset_selection_revision.aggregate_id",
                "datasets.dataset_selection_revision.id",
            ],
            name="fk_statistics_replicate_run_selection",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        schema="statistics",
    )
    op.create_table(
        "replicate_statistical_run_member",
        sa.Column("organization_id", uuid, nullable=False),
        sa.Column("project_id", uuid, nullable=False),
        sa.Column("classification", sa.String(64), nullable=False),
        sa.Column("statistical_run_id", uuid, nullable=False),
        sa.Column("ordinal", sa.SmallInteger(), nullable=False),
        sa.Column("dataset_id", uuid, nullable=False),
        sa.Column("dataset_revision_id", uuid, nullable=False),
        sa.Column("test_run_id", uuid, nullable=False),
        sa.Column("test_run_revision_id", uuid, nullable=False),
        sa.PrimaryKeyConstraint(
            "organization_id",
            "project_id",
            "statistical_run_id",
            "ordinal",
            name="pk_statistics_replicate_run_member",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "statistical_run_id",
            "dataset_revision_id",
            name="uq_statistics_replicate_run_member_dataset",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "statistical_run_id",
            "test_run_revision_id",
            name="uq_statistics_replicate_run_member_test_run",
        ),
        sa.CheckConstraint(
            "ordinal BETWEEN 0 AND 49", name="ck_statistics_replicate_run_member_ordinal"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "classification", "statistical_run_id"],
            [
                "statistics.replicate_statistical_run.organization_id",
                "statistics.replicate_statistical_run.project_id",
                "statistics.replicate_statistical_run.classification",
                "statistics.replicate_statistical_run.id",
            ],
            name="fk_statistics_replicate_run_member_run",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            [
                "organization_id",
                "project_id",
                "classification",
                "dataset_id",
                "dataset_revision_id",
            ],
            [
                "datasets.dataset_revision.organization_id",
                "datasets.dataset_revision.project_id",
                "datasets.dataset_revision.classification",
                "datasets.dataset_revision.aggregate_id",
                "datasets.dataset_revision.id",
            ],
            name="fk_statistics_replicate_run_member_dataset",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.ForeignKeyConstraint(
            [
                "organization_id",
                "project_id",
                "classification",
                "test_run_id",
                "test_run_revision_id",
            ],
            [
                "testing.test_run_revision.organization_id",
                "testing.test_run_revision.project_id",
                "testing.test_run_revision.classification",
                "testing.test_run_revision.aggregate_id",
                "testing.test_run_revision.id",
            ],
            name="fk_statistics_replicate_run_member_test_run",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        schema="statistics",
    )


def _create_result_tables() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    op.create_table(
        "replicate_statistical_result",
        *_identity_columns(uuid),
        sa.Column("statistical_run_id", uuid, nullable=False),
        sa.Column("result_kind", sa.String(100), nullable=False),
        *_identity_constraints("statistics_replicate_result"),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "classification",
            "statistical_run_id",
            name="uq_statistics_replicate_result_run",
        ),
        sa.CheckConstraint(f"result_kind = '{_KIND}'", name="ck_statistics_replicate_result_kind"),
        schema="statistics",
    )
    op.create_table(
        "replicate_statistical_result_revision",
        *_revision_columns(uuid),
        sa.Column("result_kind", sa.String(100), nullable=False),
        sa.Column("statistical_run_id", uuid, nullable=False),
        sa.Column("plan_id", uuid, nullable=False),
        sa.Column("plan_revision_id", uuid, nullable=False),
        sa.Column("selection_id", uuid, nullable=False),
        sa.Column("selection_revision_id", uuid, nullable=False),
        sa.Column("sample_count", sa.SmallInteger(), nullable=False),
        sa.Column("scalar_feature", sa.String(100), nullable=False),
        sa.Column("curve_artifact_id", uuid, nullable=False),
        sa.Column("curve_sha256", sa.CHAR(64, collation="C"), nullable=False),
        sa.Column("curve_point_count", sa.BigInteger(), nullable=False),
        sa.Column("mean_engineering_stress_pa", sa.Double(), nullable=False),
        sa.Column("sample_standard_deviation_engineering_stress_pa", sa.Double(), nullable=False),
        sa.Column("median_engineering_stress_pa", sa.Double(), nullable=False),
        sa.Column("median_absolute_deviation_engineering_stress_pa", sa.Double(), nullable=False),
        sa.Column("interquartile_range_engineering_stress_pa", sa.Double(), nullable=False),
        sa.Column("minimum_engineering_stress_pa", sa.Double(), nullable=False),
        sa.Column("maximum_engineering_stress_pa", sa.Double(), nullable=False),
        sa.Column("coefficient_of_variation", sa.Double(), nullable=True),
        sa.Column("mean_confidence_interval_lower_95_pa", sa.Double(), nullable=False),
        sa.Column("mean_confidence_interval_upper_95_pa", sa.Double(), nullable=False),
        sa.Column("curve_grid_policy", sa.String(100), nullable=False),
        sa.Column("quantile_method", sa.String(100), nullable=False),
        sa.Column("confidence_interval_method", sa.String(100), nullable=False),
        *_revision_constraints("statistics_replicate_result"),
        sa.CheckConstraint(
            f"result_kind = '{_KIND}'", name="ck_statistics_replicate_result_rev_kind"
        ),
        sa.CheckConstraint(
            "sample_count BETWEEN 2 AND 50", name="ck_statistics_replicate_result_rev_n"
        ),
        sa.CheckConstraint(
            f"scalar_feature = '{_SCALAR}'",
            name="ck_statistics_replicate_result_rev_scalar",
        ),
        sa.CheckConstraint(
            "curve_sha256 ~ '^[0-9a-f]{64}$' AND curve_point_count BETWEEN 2 AND 100000",
            name="ck_statistics_replicate_result_rev_curve",
        ),
        sa.CheckConstraint(
            "mean_engineering_stress_pa >= 0 AND "
            "sample_standard_deviation_engineering_stress_pa >= 0 AND "
            "median_engineering_stress_pa >= 0 AND "
            "median_absolute_deviation_engineering_stress_pa >= 0 AND "
            "interquartile_range_engineering_stress_pa >= 0 AND "
            "minimum_engineering_stress_pa >= 0 AND maximum_engineering_stress_pa >= 0 AND "
            "(coefficient_of_variation IS NULL OR coefficient_of_variation >= 0) AND "
            "mean_confidence_interval_lower_95_pa >= 0 AND "
            "mean_confidence_interval_upper_95_pa >= mean_confidence_interval_lower_95_pa",
            name="ck_statistics_replicate_result_rev_scalar_values",
        ),
        sa.CheckConstraint(
            f"curve_grid_policy = '{_GRID_POLICY}' AND quantile_method = '{_QUANTILE}' "
            f"AND confidence_interval_method = '{_CI_METHOD}'",
            name="ck_statistics_replicate_result_rev_methods",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "aggregate_id"],
            [
                "statistics.replicate_statistical_result.organization_id",
                "statistics.replicate_statistical_result.project_id",
                "statistics.replicate_statistical_result.id",
            ],
            name="fk_statistics_replicate_result_rev_identity",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "aggregate_id", "based_on_revision_id"],
            [
                "statistics.replicate_statistical_result_revision.organization_id",
                "statistics.replicate_statistical_result_revision.project_id",
                "statistics.replicate_statistical_result_revision.aggregate_id",
                "statistics.replicate_statistical_result_revision.id",
            ],
            name="fk_statistics_replicate_result_rev_base",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "classification", "statistical_run_id"],
            [
                "statistics.replicate_statistical_run.organization_id",
                "statistics.replicate_statistical_run.project_id",
                "statistics.replicate_statistical_run.classification",
                "statistics.replicate_statistical_run.id",
            ],
            name="fk_statistics_replicate_result_rev_run",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.ForeignKeyConstraint(
            [
                "organization_id",
                "project_id",
                "classification",
                "curve_artifact_id",
                "curve_sha256",
            ],
            [
                "artifact.artifact.organization_id",
                "artifact.artifact.project_id",
                "artifact.artifact.classification",
                "artifact.artifact.id",
                "artifact.artifact.sha256",
            ],
            name="fk_statistics_replicate_result_rev_artifact",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        schema="statistics",
    )
    op.create_foreign_key(
        "fk_statistics_replicate_result_current",
        "replicate_statistical_result",
        "replicate_statistical_result_revision",
        ["organization_id", "project_id", "id", "current_revision_id"],
        ["organization_id", "project_id", "aggregate_id", "id"],
        source_schema="statistics",
        referent_schema="statistics",
        ondelete="RESTRICT",
        deferrable=True,
        initially="DEFERRED",
    )
    op.create_foreign_key(
        "fk_statistics_replicate_run_result",
        "replicate_statistical_run",
        "replicate_statistical_result_revision",
        ["organization_id", "project_id", "classification", "result_id", "result_revision_id"],
        ["organization_id", "project_id", "classification", "aggregate_id", "id"],
        source_schema="statistics",
        referent_schema="statistics",
        ondelete="RESTRICT",
        deferrable=True,
        initially="DEFERRED",
    )
    op.create_foreign_key(
        "fk_statistics_replicate_run_artifact",
        "replicate_statistical_run",
        "artifact",
        ["organization_id", "project_id", "classification", "curve_artifact_id", "curve_sha256"],
        ["organization_id", "project_id", "classification", "id", "sha256"],
        source_schema="statistics",
        referent_schema="artifact",
        ondelete="RESTRICT",
        deferrable=True,
        initially="DEFERRED",
    )
    op.create_table(
        "replicate_qc_observation",
        sa.Column("organization_id", uuid, nullable=False),
        sa.Column("project_id", uuid, nullable=False),
        sa.Column("classification", sa.String(64), nullable=False),
        sa.Column("statistical_run_id", uuid, nullable=False),
        sa.Column("ordinal", sa.SmallInteger(), nullable=False),
        sa.Column("check_code", sa.String(100), nullable=False),
        sa.Column("outcome", sa.String(16), nullable=False),
        sa.Column("detail", sa.String(500), nullable=False),
        sa.Column("expected_point_count", sa.BigInteger(), nullable=True),
        sa.Column("observed_point_count", sa.BigInteger(), nullable=True),
        sa.Column("mismatch_index", sa.BigInteger(), nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recorded_by", uuid, nullable=False),
        sa.PrimaryKeyConstraint(
            "organization_id",
            "project_id",
            "statistical_run_id",
            "ordinal",
            name="pk_statistics_replicate_qc",
        ),
        sa.CheckConstraint("ordinal BETWEEN 0 AND 9", name="ck_statistics_replicate_qc_ordinal"),
        sa.CheckConstraint(
            "check_code IN ('distinct_test_runs', "
            "'identical_observed_engineering_strain_grid', 'input_artifact_readable')",
            name="ck_statistics_replicate_qc_code",
        ),
        sa.CheckConstraint(
            "outcome IN ('passed', 'failed')", name="ck_statistics_replicate_qc_outcome"
        ),
        sa.CheckConstraint(
            "length(btrim(detail)) BETWEEN 1 AND 500",
            name="ck_statistics_replicate_qc_detail",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "classification", "statistical_run_id"],
            [
                "statistics.replicate_statistical_run.organization_id",
                "statistics.replicate_statistical_run.project_id",
                "statistics.replicate_statistical_run.classification",
                "statistics.replicate_statistical_run.id",
            ],
            name="fk_statistics_replicate_qc_run",
            ondelete="RESTRICT",
        ),
        schema="statistics",
    )


def _create_guards() -> None:
    op.execute(
        f"""
        CREATE FUNCTION statistics.guard_replicate_plan_revision_insert()
        RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE selected_kind text; selected_count integer;
        BEGIN
            IF NEW.schema_id <> '{_PLAN_SCHEMA}' OR NEW.schema_version <> '1.0.0' THEN
                RAISE EXCEPTION 'replicate Statistical Plan schema is fixed';
            END IF;
            SELECT selection_kind, member_count INTO selected_kind, selected_count
              FROM datasets.dataset_selection_revision
             WHERE organization_id = NEW.organization_id AND project_id = NEW.project_id
               AND classification = NEW.classification AND aggregate_id = NEW.selection_id
               AND id = NEW.selection_revision_id;
            IF selected_kind IS DISTINCT FROM 'reference_tensile_replicate_set'
               OR selected_count IS DISTINCT FROM NEW.sample_count THEN
                RAISE EXCEPTION 'replicate Plan must pin one complete Selection';
            END IF;
            RETURN NEW;
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER statistics_replicate_plan_rev_guard BEFORE INSERT ON "
        "statistics.replicate_statistical_plan_revision FOR EACH ROW EXECUTE FUNCTION "
        "statistics.guard_replicate_plan_revision_insert()"
    )
    op.execute(
        """
        CREATE FUNCTION statistics.guard_replicate_run_insert()
        RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE pinned_selection uuid; pinned_revision uuid; pinned_count integer;
        BEGIN
            SELECT selection_id, selection_revision_id, sample_count
              INTO pinned_selection, pinned_revision, pinned_count
              FROM statistics.replicate_statistical_plan_revision
             WHERE organization_id = NEW.organization_id AND project_id = NEW.project_id
               AND classification = NEW.classification AND aggregate_id = NEW.plan_id
               AND id = NEW.plan_revision_id;
            IF pinned_selection IS DISTINCT FROM NEW.selection_id
               OR pinned_revision IS DISTINCT FROM NEW.selection_revision_id
               OR pinned_count IS DISTINCT FROM NEW.sample_count THEN
                RAISE EXCEPTION 'replicate Statistical Run does not match its immutable Plan';
            END IF;
            RETURN NEW;
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER statistics_replicate_run_insert_guard BEFORE INSERT ON "
        "statistics.replicate_statistical_run FOR EACH ROW EXECUTE FUNCTION "
        "statistics.guard_replicate_run_insert()"
    )
    op.execute(
        """
        CREATE FUNCTION statistics.guard_replicate_run_member_insert()
        RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE sid uuid; srid uuid; expected_count integer;
        BEGIN
            SELECT selection_id, selection_revision_id, sample_count
              INTO sid, srid, expected_count
              FROM statistics.replicate_statistical_run
             WHERE organization_id = NEW.organization_id AND project_id = NEW.project_id
               AND classification = NEW.classification AND id = NEW.statistical_run_id;
            IF NEW.ordinal >= expected_count OR NOT EXISTS (
                SELECT 1 FROM datasets.dataset_selection_member
                 WHERE organization_id = NEW.organization_id AND project_id = NEW.project_id
                   AND classification = NEW.classification AND selection_id = sid
                   AND selection_revision_id = srid AND ordinal = NEW.ordinal
                   AND dataset_id = NEW.dataset_id AND dataset_revision_id = NEW.dataset_revision_id
                   AND test_run_id = NEW.test_run_id
                   AND test_run_revision_id = NEW.test_run_revision_id
            ) THEN
                RAISE EXCEPTION 'replicate Run member is not the pinned Selection member';
            END IF;
            RETURN NEW;
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER statistics_replicate_run_member_guard BEFORE INSERT ON "
        "statistics.replicate_statistical_run_member FOR EACH ROW EXECUTE FUNCTION "
        "statistics.guard_replicate_run_member_insert()"
    )
    op.execute(
        """
        CREATE FUNCTION statistics.guard_replicate_run_transition()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'replicate Statistical Runs are immutable';
            END IF;
            IF OLD.status <> 'executing' OR NEW.status NOT IN ('succeeded', 'failed')
               OR NEW.id <> OLD.id OR NEW.organization_id <> OLD.organization_id
               OR NEW.project_id <> OLD.project_id OR NEW.classification <> OLD.classification
               OR NEW.plan_id <> OLD.plan_id OR NEW.plan_revision_id <> OLD.plan_revision_id
               OR NEW.selection_id <> OLD.selection_id
               OR NEW.selection_revision_id <> OLD.selection_revision_id
               OR NEW.sample_count <> OLD.sample_count OR NEW.change_reason <> OLD.change_reason
               OR NEW.started_at <> OLD.started_at OR NEW.created_by <> OLD.created_by
               OR NEW.request_id <> OLD.request_id OR NEW.trace_id <> OLD.trace_id
               OR NEW.request_id::text <> current_setting('cmp.request_id', true) THEN
                RAISE EXCEPTION 'invalid replicate Statistical Run transition';
            END IF;
            IF (SELECT count(*) FROM statistics.replicate_statistical_run_member
                 WHERE organization_id = OLD.organization_id AND project_id = OLD.project_id
                   AND statistical_run_id = OLD.id) <> OLD.sample_count THEN
                RAISE EXCEPTION 'replicate Statistical Run membership is incomplete';
            END IF;
            RETURN NEW;
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER statistics_replicate_run_transition BEFORE UPDATE OR DELETE ON "
        "statistics.replicate_statistical_run FOR EACH ROW EXECUTE FUNCTION "
        "statistics.guard_replicate_run_transition()"
    )
    op.execute(
        f"""
        CREATE FUNCTION statistics.guard_replicate_result_revision_insert()
        RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE run_row statistics.replicate_statistical_run%ROWTYPE;
        BEGIN
            IF NEW.schema_id <> '{_RESULT_SCHEMA}' OR NEW.schema_version <> '1.0.0' THEN
                RAISE EXCEPTION 'replicate Statistical Result schema is fixed';
            END IF;
            SELECT * INTO run_row FROM statistics.replicate_statistical_run
             WHERE organization_id = NEW.organization_id AND project_id = NEW.project_id
               AND classification = NEW.classification AND id = NEW.statistical_run_id;
            IF run_row.status <> 'executing' OR run_row.plan_id <> NEW.plan_id
               OR run_row.plan_revision_id <> NEW.plan_revision_id
               OR run_row.selection_id <> NEW.selection_id
               OR run_row.selection_revision_id <> NEW.selection_revision_id
               OR run_row.sample_count <> NEW.sample_count THEN
                RAISE EXCEPTION 'replicate Statistical Result does not match its Run';
            END IF;
            RETURN NEW;
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER statistics_replicate_result_rev_guard BEFORE INSERT ON "
        "statistics.replicate_statistical_result_revision FOR EACH ROW EXECUTE FUNCTION "
        "statistics.guard_replicate_result_revision_insert()"
    )


def upgrade() -> None:
    _create_plan_tables()
    _create_run_tables()
    _create_result_tables()
    _create_guards()
    for table in (
        "replicate_statistical_plan",
        "replicate_statistical_plan_revision",
        "replicate_statistical_run",
        "replicate_statistical_run_member",
        "replicate_statistical_result",
        "replicate_statistical_result_revision",
        "replicate_qc_observation",
    ):
        _secure(
            table,
            mutable=table
            in {
                "replicate_statistical_plan",
                "replicate_statistical_result",
                "replicate_statistical_run",
            },
        )
    for table in ("replicate_statistical_plan", "replicate_statistical_result"):
        op.execute(
            f"CREATE TRIGGER statistics_{table}_head BEFORE UPDATE OR DELETE ON statistics.{table} "
            "FOR EACH ROW EXECUTE FUNCTION revisioning.guard_identity_head_update()"
        )
    for table in (
        "replicate_statistical_plan_revision",
        "replicate_statistical_result_revision",
        "replicate_statistical_run_member",
        "replicate_qc_observation",
    ):
        op.execute(
            f"CREATE TRIGGER statistics_{table}_immutable BEFORE UPDATE OR DELETE ON "
            f"statistics.{table} FOR EACH ROW EXECUTE FUNCTION "
            "revisioning.reject_immutable_row_mutation()"
        )
    op.create_index(
        "ix_statistics_replicate_plan_selection",
        "replicate_statistical_plan_revision",
        ["organization_id", "project_id", "classification", "selection_revision_id"],
        schema="statistics",
    )
    op.create_index(
        "ix_statistics_replicate_run_plan",
        "replicate_statistical_run",
        ["organization_id", "project_id", "classification", "plan_revision_id", "started_at"],
        schema="statistics",
    )
    op.create_index(
        "ix_statistics_replicate_run_member_dataset",
        "replicate_statistical_run_member",
        ["organization_id", "project_id", "classification", "dataset_revision_id"],
        schema="statistics",
    )


def downgrade() -> None:
    op.drop_table("replicate_qc_observation", schema="statistics")
    op.drop_constraint(
        "fk_statistics_replicate_run_artifact",
        "replicate_statistical_run",
        schema="statistics",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_statistics_replicate_run_result",
        "replicate_statistical_run",
        schema="statistics",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_statistics_replicate_result_current",
        "replicate_statistical_result",
        schema="statistics",
        type_="foreignkey",
    )
    op.drop_table("replicate_statistical_result_revision", schema="statistics")
    op.drop_table("replicate_statistical_result", schema="statistics")
    op.drop_table("replicate_statistical_run_member", schema="statistics")
    op.drop_table("replicate_statistical_run", schema="statistics")
    op.drop_constraint(
        "fk_statistics_replicate_plan_current",
        "replicate_statistical_plan",
        schema="statistics",
        type_="foreignkey",
    )
    op.drop_table("replicate_statistical_plan_revision", schema="statistics")
    op.drop_table("replicate_statistical_plan", schema="statistics")
    for function in (
        "guard_replicate_result_revision_insert",
        "guard_replicate_run_transition",
        "guard_replicate_run_member_insert",
        "guard_replicate_run_insert",
        "guard_replicate_plan_revision_insert",
    ):
        op.execute(f"DROP FUNCTION IF EXISTS statistics.{function}()")

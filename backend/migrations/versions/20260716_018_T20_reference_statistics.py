"""Add typed reference Statistics/QC Plans, Runs, Results, and pointwise curve outputs.

Revision ID: 20260716_018_t20
Revises: 20260715_017_t19
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260716_018_t20"
down_revision: str | None = "20260715_017_t19"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ZERO = "'00000000-0000-0000-0000-000000000000'::uuid"
_KIND = "reference_tensile_pair_scalar_and_curve"
_INPUT_SCHEMA = "urn:cmp:datasets:reference-tensile-normalized-parquet:1.0.0"
_PLAN_SCHEMA = "urn:cmp:statistics:reference-tensile-pair-plan:1.0.0"
_RESULT_SCHEMA = "urn:cmp:statistics:reference-tensile-pair-result:1.0.0"
_CURVE_SCHEMA = "urn:cmp:statistics:reference-tensile-pair-curve-parquet:1.0.0"
_SCALAR_FEATURE = "peak_engineering_stress_pa"
_GRID_POLICY = "exact_observed_grid_match_no_alignment"
_ASSUMPTION_PROFILE = "identical_observed_engineering_strain_grid"
_QUANTILE_METHOD = "linear_inclusive"
_CI_STATUS = "not_provided_reference_pair"


def _identity_columns(uuid: postgresql.UUID) -> list[sa.Column[object]]:
    return [
        sa.Column("id", uuid, nullable=False),
        sa.Column("organization_id", uuid, nullable=False),
        sa.Column("project_id", uuid, nullable=False),
        sa.Column("classification", sa.String(length=64), nullable=False),
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
        sa.Column("classification", sa.String(length=64), nullable=False),
        sa.Column("revision_no", sa.BigInteger(), nullable=False),
        sa.Column("based_on_revision_id", uuid, nullable=True),
        sa.Column("schema_id", sa.String(length=255), nullable=False),
        sa.Column("schema_version", sa.String(length=64), nullable=False),
        sa.Column("content_hash", sa.CHAR(length=64, collation="C"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", uuid, nullable=False),
        sa.Column("change_reason", sa.Text(), nullable=False),
        sa.Column("request_id", uuid, nullable=False),
        sa.Column("trace_id", sa.String(length=255), nullable=False),
    ]


def _identity_constraints(prefix: str) -> list[sa.Constraint]:
    return [
        sa.PrimaryKeyConstraint("organization_id", "project_id", "id", name=f"pk_{prefix}"),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "classification",
            "id",
            name=f"uq_{prefix}_scope_identity",
        ),
        sa.CheckConstraint(
            "id <> "
            + _ZERO
            + " AND current_revision_id <> "
            + _ZERO
            + " AND created_by <> "
            + _ZERO,
            name=f"ck_{prefix}_nonzero_ids",
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
            name=f"uq_{prefix}_revision_scope_id",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "classification",
            "aggregate_id",
            "id",
            name=f"uq_{prefix}_revision_scoped_ref",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "aggregate_id",
            "revision_no",
            name=f"uq_{prefix}_revision_number",
        ),
        sa.CheckConstraint(
            "id <> "
            + _ZERO
            + " AND aggregate_id <> "
            + _ZERO
            + " AND created_by <> "
            + _ZERO
            + " AND request_id <> "
            + _ZERO,
            name=f"ck_{prefix}_revision_nonzero_ids",
        ),
        sa.CheckConstraint("revision_no > 0", name=f"ck_{prefix}_revision_number"),
        sa.CheckConstraint(
            "(revision_no = 1 AND based_on_revision_id IS NULL) "
            "OR (revision_no > 1 AND based_on_revision_id IS NOT NULL)",
            name=f"ck_{prefix}_revision_base",
        ),
        sa.CheckConstraint("content_hash ~ '^[0-9a-f]{64}$'", name=f"ck_{prefix}_revision_hash"),
        sa.CheckConstraint(
            "length(btrim(schema_id)) BETWEEN 1 AND 255", name=f"ck_{prefix}_revision_schema_id"
        ),
        sa.CheckConstraint(
            "length(btrim(schema_version)) BETWEEN 1 AND 64",
            name=f"ck_{prefix}_revision_schema_version",
        ),
        sa.CheckConstraint(
            "length(btrim(change_reason)) BETWEEN 1 AND 2000",
            name=f"ck_{prefix}_revision_reason",
        ),
        sa.CheckConstraint(
            "length(btrim(trace_id)) BETWEEN 1 AND 255",
            name=f"ck_{prefix}_revision_trace",
        ),
        sa.CheckConstraint(
            "classification ~ '^[a-z][a-z0-9_.-]{0,63}$'",
            name=f"ck_{prefix}_revision_classification",
        ),
    ]


def _secure(table: str) -> None:
    for operation, predicate, permission in (
        ("select", "USING", "statistics.read"),
        ("insert", "WITH CHECK", "statistics.execute"),
    ):
        op.execute(
            f"CREATE POLICY statistics_{table}_{operation} ON statistics.{table} "
            f"FOR {operation.upper()} {predicate} (access_control.can_access_row("
            f"organization_id, project_id, classification, '{permission}'))"
        )
    op.execute(
        f"CREATE POLICY statistics_{table}_update ON statistics.{table} FOR UPDATE "
        "USING (access_control.can_access_row(organization_id, project_id, classification, "
        "'statistics.execute')) WITH CHECK (access_control.can_access_row(organization_id, "
        "project_id, classification, 'statistics.execute'))"
    )


def _create_plan_tables() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    op.create_table(
        "statistical_plan",
        *_identity_columns(uuid),
        sa.Column("plan_label", sa.String(length=160), nullable=False),
        sa.Column("plan_kind", sa.String(length=100), nullable=False),
        *_identity_constraints("statistics_statistical_plan"),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "classification",
            "plan_label",
            name="uq_statistics_statistical_plan_label",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "classification",
            "id",
            "plan_kind",
            name="uq_statistics_statistical_plan_identity_kind",
        ),
        sa.CheckConstraint(
            "length(btrim(plan_label)) BETWEEN 1 AND 160 AND plan_label = btrim(plan_label)",
            name="ck_statistics_statistical_plan_label",
        ),
        sa.CheckConstraint(f"plan_kind = '{_KIND}'", name="ck_statistics_statistical_plan_kind"),
        schema="statistics",
    )
    op.create_table(
        "statistical_plan_revision",
        *_revision_columns(uuid),
        sa.Column("plan_kind", sa.String(length=100), nullable=False),
        sa.Column("sample_count", sa.SmallInteger(), nullable=False),
        sa.Column("first_selection_id", uuid, nullable=False),
        sa.Column("first_selection_revision_id", uuid, nullable=False),
        sa.Column("second_selection_id", uuid, nullable=False),
        sa.Column("second_selection_revision_id", uuid, nullable=False),
        sa.Column("input_schema_ref", sa.String(length=500), nullable=False),
        sa.Column("scalar_feature", sa.String(length=100), nullable=False),
        sa.Column("curve_grid_policy", sa.String(length=100), nullable=False),
        sa.Column("assumption_profile", sa.String(length=100), nullable=False),
        sa.Column("quantile_method", sa.String(length=100), nullable=False),
        sa.Column("confidence_interval_status", sa.String(length=100), nullable=False),
        sa.Column("curve_output_schema_ref", sa.String(length=500), nullable=False),
        *_revision_constraints("statistics_statistical_plan"),
        sa.CheckConstraint(
            f"plan_kind = '{_KIND}'", name="ck_statistics_statistical_plan_revision_kind"
        ),
        sa.CheckConstraint(
            "sample_count = 2", name="ck_statistics_statistical_plan_revision_sample_count"
        ),
        sa.CheckConstraint(
            "first_selection_revision_id <> second_selection_revision_id",
            name="ck_statistics_statistical_plan_revision_distinct_selections",
        ),
        sa.CheckConstraint(
            f"input_schema_ref = '{_INPUT_SCHEMA}'",
            name="ck_statistics_statistical_plan_revision_input_schema",
        ),
        sa.CheckConstraint(
            f"scalar_feature = '{_SCALAR_FEATURE}'",
            name="ck_statistics_statistical_plan_revision_scalar_feature",
        ),
        sa.CheckConstraint(
            f"curve_grid_policy = '{_GRID_POLICY}'",
            name="ck_statistics_statistical_plan_revision_grid_policy",
        ),
        sa.CheckConstraint(
            f"assumption_profile = '{_ASSUMPTION_PROFILE}'",
            name="ck_statistics_statistical_plan_revision_assumption_profile",
        ),
        sa.CheckConstraint(
            f"quantile_method = '{_QUANTILE_METHOD}'",
            name="ck_statistics_statistical_plan_revision_quantile_method",
        ),
        sa.CheckConstraint(
            f"confidence_interval_status = '{_CI_STATUS}'",
            name="ck_statistics_statistical_plan_revision_ci_status",
        ),
        sa.CheckConstraint(
            f"curve_output_schema_ref = '{_CURVE_SCHEMA}'",
            name="ck_statistics_statistical_plan_revision_curve_schema",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "classification",
            "id",
            name="uq_statistics_statistical_plan_revision_classified_id",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "aggregate_id"],
            [
                "statistics.statistical_plan.organization_id",
                "statistics.statistical_plan.project_id",
                "statistics.statistical_plan.id",
            ],
            name="fk_statistics_statistical_plan_revision_identity",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "classification", "aggregate_id", "plan_kind"],
            [
                "statistics.statistical_plan.organization_id",
                "statistics.statistical_plan.project_id",
                "statistics.statistical_plan.classification",
                "statistics.statistical_plan.id",
                "statistics.statistical_plan.plan_kind",
            ],
            name="fk_statistics_statistical_plan_revision_identity_kind",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.ForeignKeyConstraint(
            [
                "organization_id",
                "project_id",
                "classification",
                "first_selection_id",
                "first_selection_revision_id",
            ],
            [
                "datasets.dataset_selection_revision.organization_id",
                "datasets.dataset_selection_revision.project_id",
                "datasets.dataset_selection_revision.classification",
                "datasets.dataset_selection_revision.aggregate_id",
                "datasets.dataset_selection_revision.id",
            ],
            name="fk_statistics_plan_revision_first_selection",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.ForeignKeyConstraint(
            [
                "organization_id",
                "project_id",
                "classification",
                "second_selection_id",
                "second_selection_revision_id",
            ],
            [
                "datasets.dataset_selection_revision.organization_id",
                "datasets.dataset_selection_revision.project_id",
                "datasets.dataset_selection_revision.classification",
                "datasets.dataset_selection_revision.aggregate_id",
                "datasets.dataset_selection_revision.id",
            ],
            name="fk_statistics_plan_revision_second_selection",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "aggregate_id", "based_on_revision_id"],
            [
                "statistics.statistical_plan_revision.organization_id",
                "statistics.statistical_plan_revision.project_id",
                "statistics.statistical_plan_revision.aggregate_id",
                "statistics.statistical_plan_revision.id",
            ],
            name="fk_statistics_statistical_plan_revision_base",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        schema="statistics",
    )
    op.create_foreign_key(
        "fk_statistics_statistical_plan_current_revision",
        "statistical_plan",
        "statistical_plan_revision",
        ["organization_id", "project_id", "id", "current_revision_id"],
        ["organization_id", "project_id", "aggregate_id", "id"],
        source_schema="statistics",
        referent_schema="statistics",
        ondelete="RESTRICT",
        deferrable=True,
        initially="DEFERRED",
    )


def _create_result_and_run_tables() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    op.create_table(
        "statistical_result",
        *_identity_columns(uuid),
        sa.Column("statistical_run_id", uuid, nullable=False),
        sa.Column("result_kind", sa.String(length=100), nullable=False),
        *_identity_constraints("statistics_statistical_result"),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "classification",
            "statistical_run_id",
            name="uq_statistics_statistical_result_run",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "classification",
            "id",
            "statistical_run_id",
            "result_kind",
            name="uq_statistics_statistical_result_identity_kind",
        ),
        sa.CheckConstraint(
            "statistical_run_id <> " + _ZERO,
            name="ck_statistics_statistical_result_run_nonzero",
        ),
        sa.CheckConstraint(
            f"result_kind = '{_KIND}'", name="ck_statistics_statistical_result_kind"
        ),
        schema="statistics",
    )
    op.create_table(
        "statistical_result_revision",
        *_revision_columns(uuid),
        sa.Column("result_kind", sa.String(length=100), nullable=False),
        sa.Column("statistical_run_id", uuid, nullable=False),
        sa.Column("plan_id", uuid, nullable=False),
        sa.Column("plan_revision_id", uuid, nullable=False),
        sa.Column("first_selection_id", uuid, nullable=False),
        sa.Column("first_selection_revision_id", uuid, nullable=False),
        sa.Column("first_dataset_id", uuid, nullable=False),
        sa.Column("first_dataset_revision_id", uuid, nullable=False),
        sa.Column("second_selection_id", uuid, nullable=False),
        sa.Column("second_selection_revision_id", uuid, nullable=False),
        sa.Column("second_dataset_id", uuid, nullable=False),
        sa.Column("second_dataset_revision_id", uuid, nullable=False),
        sa.Column("sample_count", sa.SmallInteger(), nullable=False),
        sa.Column("scalar_feature", sa.String(length=100), nullable=False),
        sa.Column("curve_artifact_id", uuid, nullable=False),
        sa.Column("curve_sha256", sa.CHAR(length=64, collation="C"), nullable=False),
        sa.Column("curve_point_count", sa.BigInteger(), nullable=False),
        sa.Column("first_peak_engineering_stress_pa", sa.Double(), nullable=False),
        sa.Column("second_peak_engineering_stress_pa", sa.Double(), nullable=False),
        sa.Column("mean_engineering_stress_pa", sa.Double(), nullable=False),
        sa.Column("sample_standard_deviation_engineering_stress_pa", sa.Double(), nullable=False),
        sa.Column("median_engineering_stress_pa", sa.Double(), nullable=False),
        sa.Column("median_absolute_deviation_engineering_stress_pa", sa.Double(), nullable=False),
        sa.Column("interquartile_range_engineering_stress_pa", sa.Double(), nullable=False),
        sa.Column("minimum_engineering_stress_pa", sa.Double(), nullable=False),
        sa.Column("maximum_engineering_stress_pa", sa.Double(), nullable=False),
        sa.Column("coefficient_of_variation", sa.Double(), nullable=True),
        sa.Column("assumption_profile", sa.String(length=100), nullable=False),
        sa.Column("curve_grid_policy", sa.String(length=100), nullable=False),
        sa.Column("quantile_method", sa.String(length=100), nullable=False),
        sa.Column("confidence_interval_status", sa.String(length=100), nullable=False),
        *_revision_constraints("statistics_statistical_result"),
        sa.CheckConstraint(
            "revision_no = 1 AND based_on_revision_id IS NULL",
            name="ck_statistics_statistical_result_revision_first_only",
        ),
        sa.CheckConstraint(
            f"result_kind = '{_KIND}'", name="ck_statistics_statistical_result_revision_kind"
        ),
        sa.CheckConstraint(
            "sample_count = 2", name="ck_statistics_statistical_result_revision_sample_count"
        ),
        sa.CheckConstraint(
            "first_selection_revision_id <> second_selection_revision_id",
            name="ck_statistics_statistical_result_revision_distinct_selections",
        ),
        sa.CheckConstraint(
            "first_dataset_revision_id <> second_dataset_revision_id",
            name="ck_statistics_statistical_result_revision_distinct_datasets",
        ),
        sa.CheckConstraint(
            f"scalar_feature = '{_SCALAR_FEATURE}'",
            name="ck_statistics_statistical_result_revision_scalar_feature",
        ),
        sa.CheckConstraint(
            "curve_sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_statistics_statistical_result_revision_curve_hash",
        ),
        sa.CheckConstraint(
            "curve_point_count BETWEEN 2 AND 100000",
            name="ck_statistics_statistical_result_revision_curve_points",
        ),
        sa.CheckConstraint(
            "first_peak_engineering_stress_pa >= 0 "
            "AND first_peak_engineering_stress_pa < 'Infinity'::float8 "
            "AND second_peak_engineering_stress_pa >= 0 "
            "AND second_peak_engineering_stress_pa < 'Infinity'::float8 "
            "AND mean_engineering_stress_pa >= 0 "
            "AND mean_engineering_stress_pa < 'Infinity'::float8 "
            "AND sample_standard_deviation_engineering_stress_pa >= 0 "
            "AND sample_standard_deviation_engineering_stress_pa < 'Infinity'::float8 "
            "AND median_engineering_stress_pa >= 0 "
            "AND median_engineering_stress_pa < 'Infinity'::float8 "
            "AND median_absolute_deviation_engineering_stress_pa >= 0 "
            "AND median_absolute_deviation_engineering_stress_pa < 'Infinity'::float8 "
            "AND interquartile_range_engineering_stress_pa >= 0 "
            "AND interquartile_range_engineering_stress_pa < 'Infinity'::float8 "
            "AND minimum_engineering_stress_pa >= 0 "
            "AND minimum_engineering_stress_pa < 'Infinity'::float8 "
            "AND maximum_engineering_stress_pa >= 0 "
            "AND maximum_engineering_stress_pa < 'Infinity'::float8 "
            "AND (coefficient_of_variation IS NULL OR (coefficient_of_variation >= 0 "
            "AND coefficient_of_variation < 'Infinity'::float8))",
            name="ck_statistics_statistical_result_revision_finite_values",
        ),
        sa.CheckConstraint(
            f"assumption_profile = '{_ASSUMPTION_PROFILE}'",
            name="ck_statistics_statistical_result_revision_assumption_profile",
        ),
        sa.CheckConstraint(
            f"curve_grid_policy = '{_GRID_POLICY}'",
            name="ck_statistics_statistical_result_revision_grid_policy",
        ),
        sa.CheckConstraint(
            f"quantile_method = '{_QUANTILE_METHOD}'",
            name="ck_statistics_statistical_result_revision_quantile_method",
        ),
        sa.CheckConstraint(
            f"confidence_interval_status = '{_CI_STATUS}'",
            name="ck_statistics_statistical_result_revision_ci_status",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "classification",
            "id",
            name="uq_statistics_statistical_result_revision_classified_id",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "aggregate_id"],
            [
                "statistics.statistical_result.organization_id",
                "statistics.statistical_result.project_id",
                "statistics.statistical_result.id",
            ],
            name="fk_statistics_statistical_result_revision_identity",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.ForeignKeyConstraint(
            [
                "organization_id",
                "project_id",
                "classification",
                "aggregate_id",
                "statistical_run_id",
                "result_kind",
            ],
            [
                "statistics.statistical_result.organization_id",
                "statistics.statistical_result.project_id",
                "statistics.statistical_result.classification",
                "statistics.statistical_result.id",
                "statistics.statistical_result.statistical_run_id",
                "statistics.statistical_result.result_kind",
            ],
            name="fk_statistics_statistical_result_revision_identity_kind",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "classification", "plan_id", "plan_revision_id"],
            [
                "statistics.statistical_plan_revision.organization_id",
                "statistics.statistical_plan_revision.project_id",
                "statistics.statistical_plan_revision.classification",
                "statistics.statistical_plan_revision.aggregate_id",
                "statistics.statistical_plan_revision.id",
            ],
            name="fk_statistics_result_revision_plan",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.ForeignKeyConstraint(
            [
                "organization_id",
                "project_id",
                "classification",
                "first_selection_id",
                "first_selection_revision_id",
            ],
            [
                "datasets.dataset_selection_revision.organization_id",
                "datasets.dataset_selection_revision.project_id",
                "datasets.dataset_selection_revision.classification",
                "datasets.dataset_selection_revision.aggregate_id",
                "datasets.dataset_selection_revision.id",
            ],
            name="fk_statistics_result_revision_first_selection",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.ForeignKeyConstraint(
            [
                "organization_id",
                "project_id",
                "classification",
                "second_selection_id",
                "second_selection_revision_id",
            ],
            [
                "datasets.dataset_selection_revision.organization_id",
                "datasets.dataset_selection_revision.project_id",
                "datasets.dataset_selection_revision.classification",
                "datasets.dataset_selection_revision.aggregate_id",
                "datasets.dataset_selection_revision.id",
            ],
            name="fk_statistics_result_revision_second_selection",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.ForeignKeyConstraint(
            [
                "organization_id",
                "project_id",
                "classification",
                "first_dataset_id",
                "first_dataset_revision_id",
            ],
            [
                "datasets.dataset_revision.organization_id",
                "datasets.dataset_revision.project_id",
                "datasets.dataset_revision.classification",
                "datasets.dataset_revision.aggregate_id",
                "datasets.dataset_revision.id",
            ],
            name="fk_statistics_result_revision_first_dataset",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.ForeignKeyConstraint(
            [
                "organization_id",
                "project_id",
                "classification",
                "second_dataset_id",
                "second_dataset_revision_id",
            ],
            [
                "datasets.dataset_revision.organization_id",
                "datasets.dataset_revision.project_id",
                "datasets.dataset_revision.classification",
                "datasets.dataset_revision.aggregate_id",
                "datasets.dataset_revision.id",
            ],
            name="fk_statistics_result_revision_second_dataset",
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
            name="fk_statistics_result_revision_curve_artifact",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        schema="statistics",
    )
    op.create_foreign_key(
        "fk_statistics_statistical_result_current_revision",
        "statistical_result",
        "statistical_result_revision",
        ["organization_id", "project_id", "id", "current_revision_id"],
        ["organization_id", "project_id", "aggregate_id", "id"],
        source_schema="statistics",
        referent_schema="statistics",
        ondelete="RESTRICT",
        deferrable=True,
        initially="DEFERRED",
    )
    op.create_table(
        "statistical_run",
        sa.Column("id", uuid, nullable=False),
        sa.Column("organization_id", uuid, nullable=False),
        sa.Column("project_id", uuid, nullable=False),
        sa.Column("classification", sa.String(length=64), nullable=False),
        sa.Column("plan_id", uuid, nullable=False),
        sa.Column("plan_revision_id", uuid, nullable=False),
        sa.Column("first_selection_id", uuid, nullable=False),
        sa.Column("first_selection_revision_id", uuid, nullable=False),
        sa.Column("first_dataset_id", uuid, nullable=False),
        sa.Column("first_dataset_revision_id", uuid, nullable=False),
        sa.Column("second_selection_id", uuid, nullable=False),
        sa.Column("second_selection_revision_id", uuid, nullable=False),
        sa.Column("second_dataset_id", uuid, nullable=False),
        sa.Column("second_dataset_revision_id", uuid, nullable=False),
        sa.Column("execution_mode", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("sample_count", sa.SmallInteger(), nullable=False),
        sa.Column("result_id", uuid, nullable=True),
        sa.Column("result_revision_id", uuid, nullable=True),
        sa.Column("curve_artifact_id", uuid, nullable=True),
        sa.Column("curve_sha256", sa.CHAR(length=64, collation="C"), nullable=True),
        sa.Column("curve_point_count", sa.BigInteger(), nullable=True),
        sa.Column("failure_code", sa.String(length=100), nullable=True),
        sa.Column("change_reason", sa.Text(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", uuid, nullable=False),
        sa.Column("request_id", uuid, nullable=False),
        sa.Column("trace_id", sa.String(length=255), nullable=False),
        sa.PrimaryKeyConstraint(
            "organization_id", "project_id", "id", name="pk_statistics_statistical_run"
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "classification",
            "id",
            name="uq_statistics_statistical_run_scope_identity",
        ),
        sa.CheckConstraint(
            "id <> "
            + _ZERO
            + " AND plan_id <> "
            + _ZERO
            + " AND plan_revision_id <> "
            + _ZERO
            + " AND first_selection_id <> "
            + _ZERO
            + " AND first_selection_revision_id <> "
            + _ZERO
            + " AND first_dataset_id <> "
            + _ZERO
            + " AND first_dataset_revision_id <> "
            + _ZERO
            + " AND second_selection_id <> "
            + _ZERO
            + " AND second_selection_revision_id <> "
            + _ZERO
            + " AND second_dataset_id <> "
            + _ZERO
            + " AND second_dataset_revision_id <> "
            + _ZERO
            + " AND created_by <> "
            + _ZERO
            + " AND request_id <> "
            + _ZERO,
            name="ck_statistics_statistical_run_nonzero_ids",
        ),
        sa.CheckConstraint(
            "classification ~ '^[a-z][a-z0-9_.-]{0,63}$'",
            name="ck_statistics_statistical_run_classification",
        ),
        sa.CheckConstraint(
            "execution_mode = 'committed'", name="ck_statistics_statistical_run_execution_mode"
        ),
        sa.CheckConstraint(
            "status IN ('executing', 'succeeded', 'failed')",
            name="ck_statistics_statistical_run_status",
        ),
        sa.CheckConstraint("sample_count = 2", name="ck_statistics_statistical_run_sample_count"),
        sa.CheckConstraint(
            "first_selection_revision_id <> second_selection_revision_id "
            "AND first_dataset_revision_id <> second_dataset_revision_id",
            name="ck_statistics_statistical_run_distinct_inputs",
        ),
        sa.CheckConstraint(
            "(result_id IS NULL) = (result_revision_id IS NULL) "
            "AND (curve_artifact_id IS NULL) = (curve_sha256 IS NULL)",
            name="ck_statistics_statistical_run_output_pairs",
        ),
        sa.CheckConstraint(
            "curve_sha256 IS NULL OR curve_sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_statistics_statistical_run_curve_hash",
        ),
        sa.CheckConstraint(
            "(status = 'executing' AND ended_at IS NULL AND result_id IS NULL "
            "AND curve_artifact_id IS NULL AND curve_point_count IS NULL "
            "AND failure_code IS NULL) OR "
            "(status = 'succeeded' AND ended_at IS NOT NULL AND result_id IS NOT NULL "
            "AND curve_artifact_id IS NOT NULL AND curve_point_count BETWEEN 2 AND 100000 "
            "AND failure_code IS NULL) OR "
            "(status = 'failed' AND ended_at IS NOT NULL AND result_id IS NULL "
            "AND curve_artifact_id IS NULL AND curve_point_count IS NULL "
            "AND length(btrim(failure_code)) BETWEEN 1 AND 100)",
            name="ck_statistics_statistical_run_terminal_shape",
        ),
        sa.CheckConstraint(
            "ended_at IS NULL OR ended_at >= started_at",
            name="ck_statistics_statistical_run_time",
        ),
        sa.CheckConstraint(
            "length(btrim(change_reason)) BETWEEN 1 AND 2000",
            name="ck_statistics_statistical_run_reason",
        ),
        sa.CheckConstraint(
            "length(btrim(trace_id)) BETWEEN 1 AND 255",
            name="ck_statistics_statistical_run_trace",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "classification", "plan_id", "plan_revision_id"],
            [
                "statistics.statistical_plan_revision.organization_id",
                "statistics.statistical_plan_revision.project_id",
                "statistics.statistical_plan_revision.classification",
                "statistics.statistical_plan_revision.aggregate_id",
                "statistics.statistical_plan_revision.id",
            ],
            name="fk_statistics_statistical_run_plan",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.ForeignKeyConstraint(
            [
                "organization_id",
                "project_id",
                "classification",
                "first_selection_id",
                "first_selection_revision_id",
            ],
            [
                "datasets.dataset_selection_revision.organization_id",
                "datasets.dataset_selection_revision.project_id",
                "datasets.dataset_selection_revision.classification",
                "datasets.dataset_selection_revision.aggregate_id",
                "datasets.dataset_selection_revision.id",
            ],
            name="fk_statistics_statistical_run_first_selection",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.ForeignKeyConstraint(
            [
                "organization_id",
                "project_id",
                "classification",
                "second_selection_id",
                "second_selection_revision_id",
            ],
            [
                "datasets.dataset_selection_revision.organization_id",
                "datasets.dataset_selection_revision.project_id",
                "datasets.dataset_selection_revision.classification",
                "datasets.dataset_selection_revision.aggregate_id",
                "datasets.dataset_selection_revision.id",
            ],
            name="fk_statistics_statistical_run_second_selection",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.ForeignKeyConstraint(
            [
                "organization_id",
                "project_id",
                "classification",
                "first_dataset_id",
                "first_dataset_revision_id",
            ],
            [
                "datasets.dataset_revision.organization_id",
                "datasets.dataset_revision.project_id",
                "datasets.dataset_revision.classification",
                "datasets.dataset_revision.aggregate_id",
                "datasets.dataset_revision.id",
            ],
            name="fk_statistics_statistical_run_first_dataset",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.ForeignKeyConstraint(
            [
                "organization_id",
                "project_id",
                "classification",
                "second_dataset_id",
                "second_dataset_revision_id",
            ],
            [
                "datasets.dataset_revision.organization_id",
                "datasets.dataset_revision.project_id",
                "datasets.dataset_revision.classification",
                "datasets.dataset_revision.aggregate_id",
                "datasets.dataset_revision.id",
            ],
            name="fk_statistics_statistical_run_second_dataset",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "classification", "result_id", "result_revision_id"],
            [
                "statistics.statistical_result_revision.organization_id",
                "statistics.statistical_result_revision.project_id",
                "statistics.statistical_result_revision.classification",
                "statistics.statistical_result_revision.aggregate_id",
                "statistics.statistical_result_revision.id",
            ],
            name="fk_statistics_statistical_run_result",
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
            name="fk_statistics_statistical_run_curve_artifact",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        schema="statistics",
    )
    op.create_foreign_key(
        "fk_statistics_statistical_result_run",
        "statistical_result",
        "statistical_run",
        ["organization_id", "project_id", "classification", "statistical_run_id"],
        ["organization_id", "project_id", "classification", "id"],
        source_schema="statistics",
        referent_schema="statistics",
        ondelete="RESTRICT",
        deferrable=True,
        initially="DEFERRED",
    )
    op.create_foreign_key(
        "fk_statistics_statistical_result_revision_run",
        "statistical_result_revision",
        "statistical_run",
        ["organization_id", "project_id", "classification", "statistical_run_id"],
        ["organization_id", "project_id", "classification", "id"],
        source_schema="statistics",
        referent_schema="statistics",
        ondelete="RESTRICT",
        deferrable=True,
        initially="DEFERRED",
    )
    op.create_table(
        "qc_observation",
        sa.Column("organization_id", uuid, nullable=False),
        sa.Column("project_id", uuid, nullable=False),
        sa.Column("classification", sa.String(length=64), nullable=False),
        sa.Column("statistical_run_id", uuid, nullable=False),
        sa.Column("ordinal", sa.SmallInteger(), nullable=False),
        sa.Column("check_code", sa.String(length=100), nullable=False),
        sa.Column("outcome", sa.String(length=16), nullable=False),
        sa.Column("detail", sa.String(length=500), nullable=False),
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
            name="pk_statistics_qc_observation",
        ),
        sa.CheckConstraint("ordinal BETWEEN 0 AND 2", name="ck_statistics_qc_observation_ordinal"),
        sa.CheckConstraint(
            "check_code IN ('distinct_test_runs', 'identical_observed_engineering_strain_grid', "
            "'input_artifact_readable')",
            name="ck_statistics_qc_observation_check_code",
        ),
        sa.CheckConstraint(
            "outcome IN ('passed', 'failed')", name="ck_statistics_qc_observation_outcome"
        ),
        sa.CheckConstraint(
            "length(btrim(detail)) BETWEEN 1 AND 500",
            name="ck_statistics_qc_observation_detail",
        ),
        sa.CheckConstraint(
            "expected_point_count IS NULL OR expected_point_count >= 0",
            name="ck_statistics_qc_observation_expected_count",
        ),
        sa.CheckConstraint(
            "observed_point_count IS NULL OR observed_point_count >= 0",
            name="ck_statistics_qc_observation_observed_count",
        ),
        sa.CheckConstraint(
            "mismatch_index IS NULL OR mismatch_index >= 0",
            name="ck_statistics_qc_observation_mismatch_index",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "classification", "statistical_run_id"],
            [
                "statistics.statistical_run.organization_id",
                "statistics.statistical_run.project_id",
                "statistics.statistical_run.classification",
                "statistics.statistical_run.id",
            ],
            name="fk_statistics_qc_observation_run",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        schema="statistics",
    )


def _create_guards() -> None:
    op.execute(
        """
        CREATE FUNCTION statistics.guard_statistical_plan_revision_insert()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
          first_dataset_id uuid;
          first_dataset_revision_id uuid;
          second_dataset_id uuid;
          second_dataset_revision_id uuid;
          first_test_run_id uuid;
          second_test_run_id uuid;
        BEGIN
          SELECT dataset_id, dataset_revision_id
          INTO first_dataset_id, first_dataset_revision_id
          FROM datasets.dataset_selection_revision
          WHERE organization_id = NEW.organization_id
            AND project_id = NEW.project_id
            AND classification = NEW.classification
            AND aggregate_id = NEW.first_selection_id
            AND id = NEW.first_selection_revision_id;
          SELECT dataset_id, dataset_revision_id
          INTO second_dataset_id, second_dataset_revision_id
          FROM datasets.dataset_selection_revision
          WHERE organization_id = NEW.organization_id
            AND project_id = NEW.project_id
            AND classification = NEW.classification
            AND aggregate_id = NEW.second_selection_id
            AND id = NEW.second_selection_revision_id;
          IF first_dataset_id IS NULL OR second_dataset_id IS NULL
             OR first_dataset_revision_id = second_dataset_revision_id THEN
            RAISE EXCEPTION USING ERRCODE = '23514',
              MESSAGE = 'Statistical Plan requires two distinct pinned normalized '
                || 'Dataset selections';
          END IF;
          SELECT test_run_id INTO first_test_run_id
          FROM datasets.dataset_revision
          WHERE organization_id = NEW.organization_id
            AND project_id = NEW.project_id
            AND classification = NEW.classification
            AND aggregate_id = first_dataset_id
            AND id = first_dataset_revision_id
            AND representation = 'normalized';
          SELECT test_run_id INTO second_test_run_id
          FROM datasets.dataset_revision
          WHERE organization_id = NEW.organization_id
            AND project_id = NEW.project_id
            AND classification = NEW.classification
            AND aggregate_id = second_dataset_id
            AND id = second_dataset_revision_id
            AND representation = 'normalized';
          IF first_test_run_id IS NULL OR second_test_run_id IS NULL
             OR first_test_run_id = second_test_run_id THEN
            RAISE EXCEPTION USING ERRCODE = '23514',
              MESSAGE = 'Statistical Plan requires distinct normalized Test Run inputs';
          END IF;
          RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        f"""
        CREATE FUNCTION statistics.guard_statistical_run_insert()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
          first_selection_id uuid;
          first_selection_revision_id uuid;
          second_selection_id uuid;
          second_selection_revision_id uuid;
          first_dataset_id uuid;
          first_dataset_revision_id uuid;
          second_dataset_id uuid;
          second_dataset_revision_id uuid;
          plan_kind text;
        BEGIN
          SELECT plan_kind, first_selection_id, first_selection_revision_id,
                 second_selection_id, second_selection_revision_id
          INTO plan_kind, first_selection_id, first_selection_revision_id,
               second_selection_id, second_selection_revision_id
          FROM statistics.statistical_plan_revision
          WHERE organization_id = NEW.organization_id
            AND project_id = NEW.project_id
            AND classification = NEW.classification
            AND aggregate_id = NEW.plan_id
            AND id = NEW.plan_revision_id;
          IF plan_kind IS DISTINCT FROM '{_KIND}'
             OR first_selection_id <> NEW.first_selection_id
             OR first_selection_revision_id <> NEW.first_selection_revision_id
             OR second_selection_id <> NEW.second_selection_id
             OR second_selection_revision_id <> NEW.second_selection_revision_id THEN
            RAISE EXCEPTION USING ERRCODE = '23514',
              MESSAGE = 'Statistical Run must equal its pinned Statistical Plan revision';
          END IF;
          SELECT dataset_id, dataset_revision_id
          INTO first_dataset_id, first_dataset_revision_id
          FROM datasets.dataset_selection_revision
          WHERE organization_id = NEW.organization_id
            AND project_id = NEW.project_id
            AND classification = NEW.classification
            AND aggregate_id = NEW.first_selection_id
            AND id = NEW.first_selection_revision_id;
          SELECT dataset_id, dataset_revision_id
          INTO second_dataset_id, second_dataset_revision_id
          FROM datasets.dataset_selection_revision
          WHERE organization_id = NEW.organization_id
            AND project_id = NEW.project_id
            AND classification = NEW.classification
            AND aggregate_id = NEW.second_selection_id
            AND id = NEW.second_selection_revision_id;
          IF first_dataset_id <> NEW.first_dataset_id
             OR first_dataset_revision_id <> NEW.first_dataset_revision_id
             OR second_dataset_id <> NEW.second_dataset_id
             OR second_dataset_revision_id <> NEW.second_dataset_revision_id THEN
            RAISE EXCEPTION USING ERRCODE = '23514',
              MESSAGE = 'Statistical Run Dataset inputs must equal the pinned Selection members';
          END IF;
          RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        f"""
        CREATE FUNCTION statistics.guard_statistical_result_revision_insert()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
          run statistics.statistical_run%ROWTYPE;
          artifact_kind text;
          artifact_schema text;
        BEGIN
          SELECT * INTO run
          FROM statistics.statistical_run
          WHERE organization_id = NEW.organization_id
            AND project_id = NEW.project_id
            AND classification = NEW.classification
            AND id = NEW.statistical_run_id;
          IF NOT FOUND OR run.status <> 'executing'
             OR run.plan_id <> NEW.plan_id
             OR run.plan_revision_id <> NEW.plan_revision_id
             OR run.first_selection_id <> NEW.first_selection_id
             OR run.first_selection_revision_id <> NEW.first_selection_revision_id
             OR run.first_dataset_id <> NEW.first_dataset_id
             OR run.first_dataset_revision_id <> NEW.first_dataset_revision_id
             OR run.second_selection_id <> NEW.second_selection_id
             OR run.second_selection_revision_id <> NEW.second_selection_revision_id
             OR run.second_dataset_id <> NEW.second_dataset_id
             OR run.second_dataset_revision_id <> NEW.second_dataset_revision_id THEN
            RAISE EXCEPTION USING ERRCODE = '23514',
              MESSAGE = 'Statistical Result must match one executing immutable Statistical Run';
          END IF;
          SELECT artifact_kind, schema_ref INTO artifact_kind, artifact_schema
          FROM artifact.artifact
          WHERE organization_id = NEW.organization_id
            AND project_id = NEW.project_id
            AND classification = NEW.classification
            AND id = NEW.curve_artifact_id
            AND sha256 = NEW.curve_sha256;
          IF artifact_kind IS DISTINCT FROM 'derived'
             OR artifact_schema IS DISTINCT FROM '{_CURVE_SCHEMA}' THEN
            RAISE EXCEPTION USING ERRCODE = '23514',
              MESSAGE = 'Statistical Result requires the typed derived curve Artifact';
          END IF;
          RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION statistics.guard_statistical_run_transition()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
          result_run_id uuid;
          result_artifact_id uuid;
          result_sha256 text;
          result_point_count bigint;
        BEGIN
          IF TG_OP = 'DELETE' THEN
            RAISE EXCEPTION USING ERRCODE = '55000',
              MESSAGE = 'Statistical Run rows are append-only and cannot be deleted';
          END IF;
          IF OLD.status <> 'executing' OR NEW.status NOT IN ('succeeded', 'failed') THEN
            RAISE EXCEPTION USING ERRCODE = '55000',
              MESSAGE = 'Statistical Run may transition only once from executing '
                || 'to a terminal state';
          END IF;
          IF NEW.organization_id IS DISTINCT FROM OLD.organization_id
             OR NEW.project_id IS DISTINCT FROM OLD.project_id
             OR NEW.classification IS DISTINCT FROM OLD.classification
             OR NEW.plan_id IS DISTINCT FROM OLD.plan_id
             OR NEW.plan_revision_id IS DISTINCT FROM OLD.plan_revision_id
             OR NEW.first_selection_id IS DISTINCT FROM OLD.first_selection_id
             OR NEW.first_selection_revision_id IS DISTINCT FROM OLD.first_selection_revision_id
             OR NEW.first_dataset_id IS DISTINCT FROM OLD.first_dataset_id
             OR NEW.first_dataset_revision_id IS DISTINCT FROM OLD.first_dataset_revision_id
             OR NEW.second_selection_id IS DISTINCT FROM OLD.second_selection_id
             OR NEW.second_selection_revision_id IS DISTINCT FROM OLD.second_selection_revision_id
             OR NEW.second_dataset_id IS DISTINCT FROM OLD.second_dataset_id
             OR NEW.second_dataset_revision_id IS DISTINCT FROM OLD.second_dataset_revision_id
             OR NEW.execution_mode IS DISTINCT FROM OLD.execution_mode
             OR NEW.sample_count IS DISTINCT FROM OLD.sample_count
             OR NEW.change_reason IS DISTINCT FROM OLD.change_reason
             OR NEW.started_at IS DISTINCT FROM OLD.started_at
             OR NEW.created_by IS DISTINCT FROM OLD.created_by
             OR NEW.request_id IS DISTINCT FROM OLD.request_id
             OR NEW.trace_id IS DISTINCT FROM OLD.trace_id THEN
            RAISE EXCEPTION USING ERRCODE = '55000',
              MESSAGE = 'Statistical Run plan and input snapshot are immutable';
          END IF;
          IF NEW.status = 'succeeded' THEN
            SELECT statistical_run_id, curve_artifact_id, curve_sha256, curve_point_count
            INTO result_run_id, result_artifact_id, result_sha256, result_point_count
            FROM statistics.statistical_result_revision
            WHERE organization_id = NEW.organization_id
              AND project_id = NEW.project_id
              AND classification = NEW.classification
              AND aggregate_id = NEW.result_id
              AND id = NEW.result_revision_id;
            IF NOT FOUND
               OR result_run_id <> NEW.id
               OR result_artifact_id <> NEW.curve_artifact_id
               OR result_sha256 <> NEW.curve_sha256
               OR result_point_count <> NEW.curve_point_count THEN
              RAISE EXCEPTION USING ERRCODE = '23514',
                MESSAGE = 'Statistical Run output must match its immutable '
                  || 'Statistical Result revision';
            END IF;
          END IF;
          RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION statistics.guard_qc_observation_insert()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
          run_status text;
        BEGIN
          SELECT status INTO run_status
          FROM statistics.statistical_run
          WHERE organization_id = NEW.organization_id
            AND project_id = NEW.project_id
            AND classification = NEW.classification
            AND id = NEW.statistical_run_id;
          IF run_status NOT IN ('succeeded', 'failed') THEN
            RAISE EXCEPTION USING ERRCODE = '23514',
              MESSAGE = 'QC observations may be appended only with a terminal Statistical Run';
          END IF;
          RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        "CREATE TRIGGER statistics_statistical_plan_revision_guard BEFORE INSERT "
        "ON statistics.statistical_plan_revision FOR EACH ROW "
        "EXECUTE FUNCTION statistics.guard_statistical_plan_revision_insert()"
    )
    op.execute(
        "CREATE TRIGGER statistics_statistical_run_insert_guard BEFORE INSERT "
        "ON statistics.statistical_run FOR EACH ROW "
        "EXECUTE FUNCTION statistics.guard_statistical_run_insert()"
    )
    op.execute(
        "CREATE TRIGGER statistics_statistical_result_revision_guard BEFORE INSERT "
        "ON statistics.statistical_result_revision FOR EACH ROW "
        "EXECUTE FUNCTION statistics.guard_statistical_result_revision_insert()"
    )
    op.execute(
        "CREATE TRIGGER statistics_statistical_run_transition_guard BEFORE UPDATE OR DELETE "
        "ON statistics.statistical_run FOR EACH ROW "
        "EXECUTE FUNCTION statistics.guard_statistical_run_transition()"
    )
    op.execute(
        "CREATE TRIGGER statistics_qc_observation_insert_guard BEFORE INSERT "
        "ON statistics.qc_observation FOR EACH ROW "
        "EXECUTE FUNCTION statistics.guard_qc_observation_insert()"
    )


def upgrade() -> None:
    op.execute("CREATE SCHEMA statistics")
    _create_plan_tables()
    _create_result_and_run_tables()
    for table in (
        "statistical_plan",
        "statistical_plan_revision",
        "statistical_result",
        "statistical_result_revision",
        "statistical_run",
        "qc_observation",
    ):
        op.execute(f"ALTER TABLE statistics.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE statistics.{table} FORCE ROW LEVEL SECURITY")
        _secure(table)
    op.execute(
        "CREATE TRIGGER statistics_statistical_plan_head_only BEFORE UPDATE OR DELETE "
        "ON statistics.statistical_plan FOR EACH ROW "
        "EXECUTE FUNCTION revisioning.guard_identity_head_update()"
    )
    op.execute(
        "CREATE TRIGGER statistics_statistical_plan_revision_immutable BEFORE UPDATE OR DELETE "
        "ON statistics.statistical_plan_revision FOR EACH ROW "
        "EXECUTE FUNCTION revisioning.reject_immutable_row_mutation()"
    )
    op.execute(
        "CREATE TRIGGER statistics_statistical_result_head_only BEFORE UPDATE OR DELETE "
        "ON statistics.statistical_result FOR EACH ROW "
        "EXECUTE FUNCTION revisioning.guard_identity_head_update()"
    )
    op.execute(
        "CREATE TRIGGER statistics_statistical_result_revision_immutable BEFORE UPDATE OR DELETE "
        "ON statistics.statistical_result_revision FOR EACH ROW "
        "EXECUTE FUNCTION revisioning.reject_immutable_row_mutation()"
    )
    op.execute(
        "CREATE TRIGGER statistics_qc_observation_immutable BEFORE UPDATE OR DELETE "
        "ON statistics.qc_observation FOR EACH ROW "
        "EXECUTE FUNCTION revisioning.reject_immutable_row_mutation()"
    )
    _create_guards()
    op.create_index(
        "ix_statistics_plan_tenant_created",
        "statistical_plan",
        ["organization_id", "project_id", "classification", "created_at"],
        schema="statistics",
    )
    op.create_index(
        "ix_statistics_plan_selection",
        "statistical_plan_revision",
        ["organization_id", "project_id", "classification", "first_selection_revision_id"],
        schema="statistics",
    )
    op.create_index(
        "ix_statistics_plan_second_selection",
        "statistical_plan_revision",
        ["organization_id", "project_id", "classification", "second_selection_revision_id"],
        schema="statistics",
    )
    op.create_index(
        "ix_statistics_run_plan",
        "statistical_run",
        ["organization_id", "project_id", "classification", "plan_revision_id"],
        schema="statistics",
    )
    op.create_index(
        "ix_statistics_run_first_dataset",
        "statistical_run",
        ["organization_id", "project_id", "classification", "first_dataset_revision_id"],
        schema="statistics",
    )
    op.create_index(
        "ix_statistics_run_second_dataset",
        "statistical_run",
        ["organization_id", "project_id", "classification", "second_dataset_revision_id"],
        schema="statistics",
    )
    op.create_index(
        "ix_statistics_result_run",
        "statistical_result",
        ["organization_id", "project_id", "classification", "statistical_run_id"],
        schema="statistics",
    )
    op.create_index(
        "ix_statistics_qc_run",
        "qc_observation",
        ["organization_id", "project_id", "classification", "statistical_run_id"],
        schema="statistics",
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM statistics.statistical_run)
             OR EXISTS (SELECT 1 FROM statistics.statistical_plan)
             OR EXISTS (SELECT 1 FROM statistics.statistical_result)
             OR EXISTS (SELECT 1 FROM statistics.qc_observation) THEN
            RAISE EXCEPTION USING ERRCODE = '55000',
              MESSAGE = 'T-20 downgrade requires empty Statistics history';
          END IF;
        END;
        $$
        """
    )
    for trigger, table in (
        ("statistics_qc_observation_insert_guard", "qc_observation"),
        ("statistics_statistical_run_transition_guard", "statistical_run"),
        ("statistics_statistical_result_revision_guard", "statistical_result_revision"),
        ("statistics_statistical_run_insert_guard", "statistical_run"),
        ("statistics_statistical_plan_revision_guard", "statistical_plan_revision"),
        ("statistics_qc_observation_immutable", "qc_observation"),
        ("statistics_statistical_result_revision_immutable", "statistical_result_revision"),
        ("statistics_statistical_result_head_only", "statistical_result"),
        ("statistics_statistical_plan_revision_immutable", "statistical_plan_revision"),
        ("statistics_statistical_plan_head_only", "statistical_plan"),
    ):
        op.execute(f"DROP TRIGGER {trigger} ON statistics.{table}")
    for function in (
        "guard_qc_observation_insert",
        "guard_statistical_run_transition",
        "guard_statistical_result_revision_insert",
        "guard_statistical_run_insert",
        "guard_statistical_plan_revision_insert",
    ):
        op.execute(f"DROP FUNCTION statistics.{function}()")
    op.drop_constraint(
        "fk_statistics_statistical_result_revision_run",
        "statistical_result_revision",
        schema="statistics",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_statistics_statistical_result_run",
        "statistical_result",
        schema="statistics",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_statistics_statistical_result_current_revision",
        "statistical_result",
        schema="statistics",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_statistics_statistical_plan_current_revision",
        "statistical_plan",
        schema="statistics",
        type_="foreignkey",
    )
    op.drop_table("qc_observation", schema="statistics")
    op.drop_table("statistical_run", schema="statistics")
    op.drop_table("statistical_result_revision", schema="statistics")
    op.drop_table("statistical_result", schema="statistics")
    op.drop_table("statistical_plan_revision", schema="statistics")
    op.drop_table("statistical_plan", schema="statistics")
    op.execute("DROP SCHEMA statistics")

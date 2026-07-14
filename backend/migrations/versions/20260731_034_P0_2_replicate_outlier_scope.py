# ruff: noqa: E501
"""Add persisted multi-replicate outlier evidence, assessment, and calibration scope.

Revision ID: 20260731_034_p02
Revises: 20260730_033_p02
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260731_034_p02"
down_revision: str | None = "20260730_033_p02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ZERO = "'00000000-0000-0000-0000-000000000000'::uuid"
_PLAN_KIND = "reference_tensile_replicate_modified_z_review"
_DETECTOR = "absolute_modified_z_score_peak_stress"
_FEATURE = "peak_engineering_stress_pa"
_SCOPE_KIND = "reference_voce_calibration_input"
_PLAN_SCHEMA = "urn:cmp:statistics:reference-tensile-replicate-outlier-plan:1.0.0"
_ASSESSMENT_SCHEMA = (
    "urn:cmp:statistics:reference-tensile-replicate-outlier-assessment:1.0.0"
)
_SCOPE_SCHEMA = "urn:cmp:statistics:reference-calibration-input-scope:1.0.0"


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
            "organization_id", "project_id", "classification", "id", name=f"uq_{prefix}_scoped"
        ),
        sa.CheckConstraint(
            f"id <> {_ZERO} AND current_revision_id <> {_ZERO} AND created_by <> {_ZERO}",
            name=f"ck_{prefix}_ids",
        ),
        sa.CheckConstraint(
            "classification ~ '^[a-z][a-z0-9_.-]{0,63}$'", name=f"ck_{prefix}_classification"
        ),
    ]


def _revision_constraints(prefix: str) -> list[sa.Constraint]:
    return [
        sa.PrimaryKeyConstraint("organization_id", "project_id", "id", name=f"pk_{prefix}_rev"),
        sa.UniqueConstraint(
            "organization_id", "project_id", "aggregate_id", "id", name=f"uq_{prefix}_rev_id"
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "classification",
            "aggregate_id",
            "id",
            name=f"uq_{prefix}_rev_scoped",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "aggregate_id",
            "revision_no",
            name=f"uq_{prefix}_rev_no",
        ),
        sa.CheckConstraint(
            f"id <> {_ZERO} AND aggregate_id <> {_ZERO} AND created_by <> {_ZERO} "
            f"AND request_id <> {_ZERO}",
            name=f"ck_{prefix}_rev_ids",
        ),
        sa.CheckConstraint("revision_no > 0", name=f"ck_{prefix}_rev_no"),
        sa.CheckConstraint(
            "(revision_no = 1 AND based_on_revision_id IS NULL) OR "
            "(revision_no > 1 AND based_on_revision_id IS NOT NULL)",
            name=f"ck_{prefix}_rev_base",
        ),
        sa.CheckConstraint("content_hash ~ '^[0-9a-f]{64}$'", name=f"ck_{prefix}_rev_hash"),
        sa.CheckConstraint(
            "length(btrim(change_reason)) BETWEEN 1 AND 2000", name=f"ck_{prefix}_rev_reason"
        ),
    ]


def _attach_revision(prefix: str, identity: str, revision_table: str) -> None:
    op.create_foreign_key(
        f"fk_{prefix}_current",
        identity,
        revision_table,
        ["organization_id", "project_id", "id", "current_revision_id"],
        ["organization_id", "project_id", "aggregate_id", "id"],
        source_schema="statistics",
        referent_schema="statistics",
        ondelete="RESTRICT",
        deferrable=True,
        initially="DEFERRED",
    )


def _secure(table: str, *, mutable: bool = False) -> None:
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


def _immutable(table: str) -> None:
    op.execute(
        f"CREATE TRIGGER trg_{table}_immutable BEFORE UPDATE OR DELETE "
        f"ON statistics.{table} FOR EACH ROW "
        "EXECUTE FUNCTION revisioning.reject_immutable_row_mutation()"
    )


def _create_plan(uuid: postgresql.UUID) -> None:
    op.create_table(
        "replicate_outlier_detection_plan",
        *_identity_columns(uuid),
        sa.Column("plan_label", sa.String(160), nullable=False),
        sa.Column("plan_kind", sa.String(100), nullable=False),
        *_identity_constraints("statistics_repl_outlier_plan"),
        sa.UniqueConstraint(
            "organization_id", "project_id", "classification", "plan_label",
            name="uq_statistics_repl_outlier_plan_label",
        ),
        sa.CheckConstraint("length(btrim(plan_label)) BETWEEN 1 AND 160", name="ck_statistics_repl_outlier_plan_label"),
        sa.CheckConstraint(f"plan_kind = '{_PLAN_KIND}'", name="ck_statistics_repl_outlier_plan_kind"),
        schema="statistics",
    )
    op.create_table(
        "replicate_outlier_detection_plan_revision",
        *_revision_columns(uuid),
        sa.Column("plan_kind", sa.String(100), nullable=False),
        sa.Column("statistical_result_id", uuid, nullable=False),
        sa.Column("statistical_result_revision_id", uuid, nullable=False),
        sa.Column("detector", sa.String(100), nullable=False),
        sa.Column("formula_version", sa.String(64), nullable=False),
        sa.Column("feature", sa.String(100), nullable=False),
        sa.Column("absolute_modified_z_threshold", sa.Double(), nullable=False),
        sa.Column("automatic_exclusion", sa.Boolean(), nullable=False),
        *_revision_constraints("statistics_repl_outlier_plan"),
        sa.CheckConstraint(f"plan_kind = '{_PLAN_KIND}'", name="ck_statistics_repl_outlier_plan_rev_kind"),
        sa.CheckConstraint(f"detector = '{_DETECTOR}'", name="ck_statistics_repl_outlier_plan_detector"),
        sa.CheckConstraint("formula_version = '1.0.0'", name="ck_statistics_repl_outlier_plan_formula"),
        sa.CheckConstraint(f"feature = '{_FEATURE}'", name="ck_statistics_repl_outlier_plan_feature"),
        sa.CheckConstraint("absolute_modified_z_threshold > 0 AND absolute_modified_z_threshold <= 20", name="ck_statistics_repl_outlier_plan_threshold"),
        sa.CheckConstraint("automatic_exclusion = false", name="ck_statistics_repl_outlier_plan_no_auto"),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "aggregate_id"],
            ["statistics.replicate_outlier_detection_plan.organization_id", "statistics.replicate_outlier_detection_plan.project_id", "statistics.replicate_outlier_detection_plan.id"],
            name="fk_statistics_repl_outlier_plan_rev_identity", ondelete="RESTRICT", deferrable=True, initially="DEFERRED",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "classification", "statistical_result_id", "statistical_result_revision_id"],
            ["statistics.replicate_statistical_result_revision.organization_id", "statistics.replicate_statistical_result_revision.project_id", "statistics.replicate_statistical_result_revision.classification", "statistics.replicate_statistical_result_revision.aggregate_id", "statistics.replicate_statistical_result_revision.id"],
            name="fk_statistics_repl_outlier_plan_result", ondelete="RESTRICT",
        ),
        schema="statistics",
    )
    _attach_revision("statistics_repl_outlier_plan", "replicate_outlier_detection_plan", "replicate_outlier_detection_plan_revision")


def _create_run_and_candidates(uuid: postgresql.UUID) -> None:
    op.create_table(
        "replicate_outlier_detection_run",
        sa.Column("id", uuid, nullable=False),
        sa.Column("organization_id", uuid, nullable=False),
        sa.Column("project_id", uuid, nullable=False),
        sa.Column("classification", sa.String(64), nullable=False),
        sa.Column("detection_plan_id", uuid, nullable=False),
        sa.Column("detection_plan_revision_id", uuid, nullable=False),
        sa.Column("statistical_result_id", uuid, nullable=False),
        sa.Column("statistical_result_revision_id", uuid, nullable=False),
        sa.Column("statistical_plan_id", uuid, nullable=False),
        sa.Column("statistical_plan_revision_id", uuid, nullable=False),
        sa.Column("selection_id", uuid, nullable=False),
        sa.Column("selection_revision_id", uuid, nullable=False),
        sa.Column("sample_count", sa.SmallInteger(), nullable=False),
        sa.Column("sample_median_peak_stress_pa", sa.Double(), nullable=False),
        sa.Column("sample_mad_peak_stress_pa", sa.Double(), nullable=False),
        sa.Column("candidate_count", sa.SmallInteger(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", uuid, nullable=False),
        sa.Column("request_id", uuid, nullable=False),
        sa.Column("trace_id", sa.String(255), nullable=False),
        sa.PrimaryKeyConstraint("organization_id", "project_id", "id", name="pk_statistics_repl_outlier_run"),
        sa.UniqueConstraint("organization_id", "project_id", "classification", "id", name="uq_statistics_repl_outlier_run_scoped"),
        sa.CheckConstraint("sample_count BETWEEN 3 AND 50 AND candidate_count BETWEEN 0 AND sample_count", name="ck_statistics_repl_outlier_run_counts"),
        sa.CheckConstraint("sample_median_peak_stress_pa >= 0 AND sample_mad_peak_stress_pa >= 0", name="ck_statistics_repl_outlier_run_values"),
        sa.CheckConstraint("ended_at >= started_at", name="ck_statistics_repl_outlier_run_times"),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "classification", "detection_plan_id", "detection_plan_revision_id"],
            ["statistics.replicate_outlier_detection_plan_revision.organization_id", "statistics.replicate_outlier_detection_plan_revision.project_id", "statistics.replicate_outlier_detection_plan_revision.classification", "statistics.replicate_outlier_detection_plan_revision.aggregate_id", "statistics.replicate_outlier_detection_plan_revision.id"],
            name="fk_statistics_repl_outlier_run_plan", ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "classification", "statistical_result_id", "statistical_result_revision_id"],
            ["statistics.replicate_statistical_result_revision.organization_id", "statistics.replicate_statistical_result_revision.project_id", "statistics.replicate_statistical_result_revision.classification", "statistics.replicate_statistical_result_revision.aggregate_id", "statistics.replicate_statistical_result_revision.id"],
            name="fk_statistics_repl_outlier_run_result", ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "classification", "statistical_plan_id", "statistical_plan_revision_id"],
            ["statistics.replicate_statistical_plan_revision.organization_id", "statistics.replicate_statistical_plan_revision.project_id", "statistics.replicate_statistical_plan_revision.classification", "statistics.replicate_statistical_plan_revision.aggregate_id", "statistics.replicate_statistical_plan_revision.id"],
            name="fk_statistics_repl_outlier_run_stat_plan", ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "classification", "selection_id", "selection_revision_id"],
            ["datasets.dataset_selection_revision.organization_id", "datasets.dataset_selection_revision.project_id", "datasets.dataset_selection_revision.classification", "datasets.dataset_selection_revision.aggregate_id", "datasets.dataset_selection_revision.id"],
            name="fk_statistics_repl_outlier_run_selection", ondelete="RESTRICT",
        ),
        schema="statistics",
    )
    op.create_table(
        "replicate_outlier_candidate",
        sa.Column("id", uuid, nullable=False),
        sa.Column("organization_id", uuid, nullable=False),
        sa.Column("project_id", uuid, nullable=False),
        sa.Column("classification", sa.String(64), nullable=False),
        sa.Column("detection_run_id", uuid, nullable=False),
        sa.Column("detection_plan_id", uuid, nullable=False),
        sa.Column("detection_plan_revision_id", uuid, nullable=False),
        sa.Column("statistical_result_id", uuid, nullable=False),
        sa.Column("statistical_result_revision_id", uuid, nullable=False),
        sa.Column("statistical_plan_id", uuid, nullable=False),
        sa.Column("statistical_plan_revision_id", uuid, nullable=False),
        sa.Column("selection_id", uuid, nullable=False),
        sa.Column("selection_revision_id", uuid, nullable=False),
        sa.Column("ordinal", sa.SmallInteger(), nullable=False),
        sa.Column("dataset_id", uuid, nullable=False),
        sa.Column("dataset_revision_id", uuid, nullable=False),
        sa.Column("test_run_id", uuid, nullable=False),
        sa.Column("test_run_revision_id", uuid, nullable=False),
        sa.Column("peak_engineering_stress_pa", sa.Double(), nullable=False),
        sa.Column("sample_count", sa.SmallInteger(), nullable=False),
        sa.Column("sample_median_peak_stress_pa", sa.Double(), nullable=False),
        sa.Column("sample_mad_peak_stress_pa", sa.Double(), nullable=False),
        sa.Column("absolute_modified_z_score", sa.Double(), nullable=True),
        sa.Column("threshold", sa.Double(), nullable=False),
        sa.Column("evidence_code", sa.String(64), nullable=False),
        sa.PrimaryKeyConstraint("organization_id", "project_id", "id", name="pk_statistics_repl_outlier_candidate"),
        sa.UniqueConstraint("organization_id", "project_id", "classification", "id", name="uq_statistics_repl_outlier_candidate_scoped"),
        sa.UniqueConstraint("organization_id", "project_id", "detection_run_id", "ordinal", name="uq_statistics_repl_outlier_candidate_member"),
        sa.CheckConstraint("sample_count BETWEEN 3 AND 50 AND ordinal BETWEEN 0 AND sample_count - 1", name="ck_statistics_repl_outlier_candidate_counts"),
        sa.CheckConstraint("peak_engineering_stress_pa >= 0 AND sample_median_peak_stress_pa >= 0 AND sample_mad_peak_stress_pa >= 0", name="ck_statistics_repl_outlier_candidate_values"),
        sa.CheckConstraint("threshold > 0 AND threshold <= 20", name="ck_statistics_repl_outlier_candidate_threshold"),
        sa.CheckConstraint(
            "(evidence_code = 'modified_z_threshold_exceeded' AND absolute_modified_z_score IS NOT NULL AND absolute_modified_z_score >= threshold AND sample_mad_peak_stress_pa > 0) OR "
            "(evidence_code = 'mad_zero_nonmedian_review' AND absolute_modified_z_score IS NULL AND sample_mad_peak_stress_pa = 0)",
            name="ck_statistics_repl_outlier_candidate_evidence",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "classification", "detection_run_id"],
            ["statistics.replicate_outlier_detection_run.organization_id", "statistics.replicate_outlier_detection_run.project_id", "statistics.replicate_outlier_detection_run.classification", "statistics.replicate_outlier_detection_run.id"],
            name="fk_statistics_repl_outlier_candidate_run", ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "classification", "dataset_id", "dataset_revision_id"],
            ["datasets.dataset_revision.organization_id", "datasets.dataset_revision.project_id", "datasets.dataset_revision.classification", "datasets.dataset_revision.aggregate_id", "datasets.dataset_revision.id"],
            name="fk_statistics_repl_outlier_candidate_dataset", ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "classification", "test_run_id", "test_run_revision_id"],
            ["testing.test_run_revision.organization_id", "testing.test_run_revision.project_id", "testing.test_run_revision.classification", "testing.test_run_revision.aggregate_id", "testing.test_run_revision.id"],
            name="fk_statistics_repl_outlier_candidate_test_run", ondelete="RESTRICT",
        ),
        schema="statistics",
    )


def _create_assessment(uuid: postgresql.UUID) -> None:
    op.create_table(
        "replicate_outlier_assessment",
        *_identity_columns(uuid),
        sa.Column("candidate_id", uuid, nullable=False),
        *_identity_constraints("statistics_repl_outlier_assessment"),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "classification", "candidate_id"],
            ["statistics.replicate_outlier_candidate.organization_id", "statistics.replicate_outlier_candidate.project_id", "statistics.replicate_outlier_candidate.classification", "statistics.replicate_outlier_candidate.id"],
            name="fk_statistics_repl_outlier_assessment_candidate", ondelete="RESTRICT",
        ),
        schema="statistics",
    )
    op.create_table(
        "replicate_outlier_assessment_revision",
        *_revision_columns(uuid),
        sa.Column("candidate_id", uuid, nullable=False),
        sa.Column("detection_plan_id", uuid, nullable=False),
        sa.Column("detection_plan_revision_id", uuid, nullable=False),
        sa.Column("decision", sa.String(40), nullable=False),
        sa.Column("assessment_reason", sa.Text(), nullable=False),
        sa.Column("automatic_exclusion", sa.Boolean(), nullable=False),
        *_revision_constraints("statistics_repl_outlier_assessment"),
        sa.CheckConstraint("decision IN ('retained', 'excluded_from_calibration')", name="ck_statistics_repl_outlier_assessment_decision"),
        sa.CheckConstraint("length(btrim(assessment_reason)) BETWEEN 1 AND 2000", name="ck_statistics_repl_outlier_assessment_reason"),
        sa.CheckConstraint("automatic_exclusion = false", name="ck_statistics_repl_outlier_assessment_no_auto"),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "aggregate_id"],
            ["statistics.replicate_outlier_assessment.organization_id", "statistics.replicate_outlier_assessment.project_id", "statistics.replicate_outlier_assessment.id"],
            name="fk_statistics_repl_outlier_assessment_rev_identity", ondelete="RESTRICT", deferrable=True, initially="DEFERRED",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "classification", "candidate_id"],
            ["statistics.replicate_outlier_candidate.organization_id", "statistics.replicate_outlier_candidate.project_id", "statistics.replicate_outlier_candidate.classification", "statistics.replicate_outlier_candidate.id"],
            name="fk_statistics_repl_outlier_assessment_rev_candidate", ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "classification", "detection_plan_id", "detection_plan_revision_id"],
            ["statistics.replicate_outlier_detection_plan_revision.organization_id", "statistics.replicate_outlier_detection_plan_revision.project_id", "statistics.replicate_outlier_detection_plan_revision.classification", "statistics.replicate_outlier_detection_plan_revision.aggregate_id", "statistics.replicate_outlier_detection_plan_revision.id"],
            name="fk_statistics_repl_outlier_assessment_rev_plan", ondelete="RESTRICT",
        ),
        schema="statistics",
    )
    _attach_revision("statistics_repl_outlier_assessment", "replicate_outlier_assessment", "replicate_outlier_assessment_revision")


def _create_scope(uuid: postgresql.UUID) -> None:
    op.create_table(
        "calibration_input_scope",
        *_identity_columns(uuid),
        sa.Column("scope_label", sa.String(160), nullable=False),
        sa.Column("scope_kind", sa.String(100), nullable=False),
        *_identity_constraints("statistics_calibration_scope"),
        sa.UniqueConstraint("organization_id", "project_id", "classification", "scope_label", name="uq_statistics_calibration_scope_label"),
        sa.CheckConstraint("length(btrim(scope_label)) BETWEEN 1 AND 160", name="ck_statistics_calibration_scope_label"),
        sa.CheckConstraint(f"scope_kind = '{_SCOPE_KIND}'", name="ck_statistics_calibration_scope_kind"),
        schema="statistics",
    )
    op.create_table(
        "calibration_input_scope_revision",
        *_revision_columns(uuid),
        sa.Column("scope_kind", sa.String(100), nullable=False),
        sa.Column("source_selection_id", uuid, nullable=False),
        sa.Column("source_selection_revision_id", uuid, nullable=False),
        sa.Column("statistical_result_id", uuid, nullable=False),
        sa.Column("statistical_result_revision_id", uuid, nullable=False),
        sa.Column("detection_plan_id", uuid, nullable=False),
        sa.Column("detection_plan_revision_id", uuid, nullable=False),
        sa.Column("source_member_count", sa.SmallInteger(), nullable=False),
        sa.Column("included_member_count", sa.SmallInteger(), nullable=False),
        sa.Column("excluded_member_count", sa.SmallInteger(), nullable=False),
        *_revision_constraints("statistics_calibration_scope"),
        sa.CheckConstraint(f"scope_kind = '{_SCOPE_KIND}'", name="ck_statistics_calibration_scope_rev_kind"),
        sa.CheckConstraint("source_member_count BETWEEN 3 AND 50 AND included_member_count >= 2 AND excluded_member_count >= 0 AND included_member_count + excluded_member_count = source_member_count", name="ck_statistics_calibration_scope_counts"),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "aggregate_id"],
            ["statistics.calibration_input_scope.organization_id", "statistics.calibration_input_scope.project_id", "statistics.calibration_input_scope.id"],
            name="fk_statistics_calibration_scope_rev_identity", ondelete="RESTRICT", deferrable=True, initially="DEFERRED",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "classification", "source_selection_id", "source_selection_revision_id"],
            ["datasets.dataset_selection_revision.organization_id", "datasets.dataset_selection_revision.project_id", "datasets.dataset_selection_revision.classification", "datasets.dataset_selection_revision.aggregate_id", "datasets.dataset_selection_revision.id"],
            name="fk_statistics_calibration_scope_selection", ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "classification", "statistical_result_id", "statistical_result_revision_id"],
            ["statistics.replicate_statistical_result_revision.organization_id", "statistics.replicate_statistical_result_revision.project_id", "statistics.replicate_statistical_result_revision.classification", "statistics.replicate_statistical_result_revision.aggregate_id", "statistics.replicate_statistical_result_revision.id"],
            name="fk_statistics_calibration_scope_result", ondelete="RESTRICT",
        ),
        schema="statistics",
    )
    _attach_revision("statistics_calibration_scope", "calibration_input_scope", "calibration_input_scope_revision")
    op.create_table(
        "calibration_input_scope_member",
        sa.Column("organization_id", uuid, nullable=False),
        sa.Column("project_id", uuid, nullable=False),
        sa.Column("classification", sa.String(64), nullable=False),
        sa.Column("scope_id", uuid, nullable=False),
        sa.Column("scope_revision_id", uuid, nullable=False),
        sa.Column("ordinal", sa.SmallInteger(), nullable=False),
        sa.Column("dataset_id", uuid, nullable=False),
        sa.Column("dataset_revision_id", uuid, nullable=False),
        sa.Column("test_run_id", uuid, nullable=False),
        sa.Column("test_run_revision_id", uuid, nullable=False),
        sa.Column("disposition", sa.String(16), nullable=False),
        sa.Column("candidate_id", uuid, nullable=True),
        sa.Column("assessment_id", uuid, nullable=True),
        sa.Column("assessment_revision_id", uuid, nullable=True),
        sa.PrimaryKeyConstraint("organization_id", "project_id", "scope_revision_id", "ordinal", name="pk_statistics_calibration_scope_member"),
        sa.UniqueConstraint("organization_id", "project_id", "scope_revision_id", "dataset_revision_id", name="uq_statistics_calibration_scope_member_dataset"),
        sa.CheckConstraint("ordinal BETWEEN 0 AND 49", name="ck_statistics_calibration_scope_member_ordinal"),
        sa.CheckConstraint("disposition IN ('included', 'excluded')", name="ck_statistics_calibration_scope_member_disposition"),
        sa.CheckConstraint("(candidate_id IS NULL AND assessment_id IS NULL AND assessment_revision_id IS NULL AND disposition = 'included') OR (candidate_id IS NOT NULL AND assessment_id IS NOT NULL AND assessment_revision_id IS NOT NULL)", name="ck_statistics_calibration_scope_member_assessment"),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "classification", "scope_id", "scope_revision_id"],
            ["statistics.calibration_input_scope_revision.organization_id", "statistics.calibration_input_scope_revision.project_id", "statistics.calibration_input_scope_revision.classification", "statistics.calibration_input_scope_revision.aggregate_id", "statistics.calibration_input_scope_revision.id"],
            name="fk_statistics_calibration_scope_member_scope", ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "classification", "dataset_id", "dataset_revision_id"],
            ["datasets.dataset_revision.organization_id", "datasets.dataset_revision.project_id", "datasets.dataset_revision.classification", "datasets.dataset_revision.aggregate_id", "datasets.dataset_revision.id"],
            name="fk_statistics_calibration_scope_member_dataset", ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "classification", "candidate_id"],
            ["statistics.replicate_outlier_candidate.organization_id", "statistics.replicate_outlier_candidate.project_id", "statistics.replicate_outlier_candidate.classification", "statistics.replicate_outlier_candidate.id"],
            name="fk_statistics_calibration_scope_member_candidate", ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "classification", "assessment_id", "assessment_revision_id"],
            ["statistics.replicate_outlier_assessment_revision.organization_id", "statistics.replicate_outlier_assessment_revision.project_id", "statistics.replicate_outlier_assessment_revision.classification", "statistics.replicate_outlier_assessment_revision.aggregate_id", "statistics.replicate_outlier_assessment_revision.id"],
            name="fk_statistics_calibration_scope_member_assessment", ondelete="RESTRICT",
        ),
        schema="statistics",
    )


def upgrade() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    _create_plan(uuid)
    _create_run_and_candidates(uuid)
    _create_assessment(uuid)
    _create_scope(uuid)
    for prefix, table, schema_id in (
        (
            "statistics_repl_outlier_plan",
            "replicate_outlier_detection_plan_revision",
            _PLAN_SCHEMA,
        ),
        (
            "statistics_repl_outlier_assessment",
            "replicate_outlier_assessment_revision",
            _ASSESSMENT_SCHEMA,
        ),
        (
            "statistics_calibration_scope",
            "calibration_input_scope_revision",
            _SCOPE_SCHEMA,
        ),
    ):
        op.create_check_constraint(
            f"ck_{prefix}_rev_schema",
            table,
            f"schema_id = '{schema_id}' AND schema_version = '1.0.0'",
            schema="statistics",
        )
        op.create_foreign_key(
            f"fk_{prefix}_rev_base",
            table,
            table,
            ["organization_id", "project_id", "aggregate_id", "based_on_revision_id"],
            ["organization_id", "project_id", "aggregate_id", "id"],
            source_schema="statistics",
            referent_schema="statistics",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        )
    for table in (
        "replicate_outlier_detection_plan",
        "replicate_outlier_detection_plan_revision",
        "replicate_outlier_detection_run",
        "replicate_outlier_candidate",
        "replicate_outlier_assessment",
        "replicate_outlier_assessment_revision",
        "calibration_input_scope",
        "calibration_input_scope_revision",
        "calibration_input_scope_member",
    ):
        _secure(table, mutable=table in {"replicate_outlier_detection_plan", "replicate_outlier_assessment", "calibration_input_scope"})
    for table in (
        "replicate_outlier_detection_plan",
        "replicate_outlier_assessment",
        "calibration_input_scope",
    ):
        op.execute(
            f"CREATE TRIGGER statistics_{table}_head BEFORE UPDATE OR DELETE ON "
            f"statistics.{table} FOR EACH ROW EXECUTE FUNCTION "
            "revisioning.guard_identity_head_update()"
        )
    for table in (
        "replicate_outlier_detection_plan_revision",
        "replicate_outlier_detection_run",
        "replicate_outlier_candidate",
        "replicate_outlier_assessment_revision",
        "calibration_input_scope_revision",
        "calibration_input_scope_member",
    ):
        _immutable(table)
    op.create_index("ix_statistics_repl_outlier_plan_result", "replicate_outlier_detection_plan_revision", ["organization_id", "project_id", "statistical_result_revision_id"], schema="statistics")
    op.create_index("ix_statistics_repl_outlier_run_result", "replicate_outlier_detection_run", ["organization_id", "project_id", "statistical_result_revision_id"], schema="statistics")
    op.create_index("ix_statistics_repl_outlier_candidate_run", "replicate_outlier_candidate", ["organization_id", "project_id", "detection_run_id"], schema="statistics")
    op.create_index("ix_statistics_repl_outlier_assessment_candidate", "replicate_outlier_assessment_revision", ["organization_id", "project_id", "candidate_id"], schema="statistics")
    op.create_index("ix_statistics_calibration_scope_result", "calibration_input_scope_revision", ["organization_id", "project_id", "statistical_result_revision_id"], schema="statistics")
    op.execute(
        """
        CREATE FUNCTION statistics.guard_replicate_outlier_candidate_count()
        RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE expected_count integer;
        DECLARE actual_count integer;
        BEGIN
            SELECT candidate_count INTO expected_count
              FROM statistics.replicate_outlier_detection_run
             WHERE organization_id = COALESCE(NEW.organization_id, OLD.organization_id)
               AND project_id = COALESCE(NEW.project_id, OLD.project_id)
               AND id = COALESCE(NEW.detection_run_id, OLD.detection_run_id);
            SELECT count(*) INTO actual_count
              FROM statistics.replicate_outlier_candidate
             WHERE organization_id = COALESCE(NEW.organization_id, OLD.organization_id)
               AND project_id = COALESCE(NEW.project_id, OLD.project_id)
               AND detection_run_id = COALESCE(NEW.detection_run_id, OLD.detection_run_id);
            IF expected_count IS DISTINCT FROM actual_count THEN
                RAISE EXCEPTION 'outlier candidate count does not match Detection Run';
            END IF;
            RETURN NULL;
        END $$
        """
    )
    op.execute(
        "CREATE CONSTRAINT TRIGGER statistics_repl_outlier_candidate_count "
        "AFTER INSERT ON statistics.replicate_outlier_candidate DEFERRABLE INITIALLY DEFERRED "
        "FOR EACH ROW EXECUTE FUNCTION statistics.guard_replicate_outlier_candidate_count()"
    )
    op.execute(
        """
        CREATE FUNCTION statistics.guard_calibration_scope_member_count()
        RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE scope_row statistics.calibration_input_scope_revision%ROWTYPE;
        DECLARE source_count integer;
        DECLARE included_count integer;
        DECLARE excluded_count integer;
        BEGIN
            SELECT * INTO scope_row FROM statistics.calibration_input_scope_revision
             WHERE organization_id = COALESCE(NEW.organization_id, OLD.organization_id)
               AND project_id = COALESCE(NEW.project_id, OLD.project_id)
               AND id = COALESCE(NEW.scope_revision_id, OLD.scope_revision_id);
            SELECT count(*), count(*) FILTER (WHERE disposition = 'included'),
                   count(*) FILTER (WHERE disposition = 'excluded')
              INTO source_count, included_count, excluded_count
              FROM statistics.calibration_input_scope_member
             WHERE organization_id = scope_row.organization_id
               AND project_id = scope_row.project_id
               AND scope_revision_id = scope_row.id;
            IF source_count <> scope_row.source_member_count
               OR included_count <> scope_row.included_member_count
               OR excluded_count <> scope_row.excluded_member_count THEN
                RAISE EXCEPTION 'calibration Scope member counts do not match its revision';
            END IF;
            RETURN NULL;
        END $$
        """
    )
    op.execute(
        "CREATE CONSTRAINT TRIGGER statistics_calibration_scope_member_count "
        "AFTER INSERT ON statistics.calibration_input_scope_member DEFERRABLE INITIALLY DEFERRED "
        "FOR EACH ROW EXECUTE FUNCTION statistics.guard_calibration_scope_member_count()"
    )


def downgrade() -> None:
    op.execute(
        "DROP FUNCTION IF EXISTS statistics.guard_calibration_scope_member_count() CASCADE"
    )
    op.execute(
        "DROP FUNCTION IF EXISTS statistics.guard_replicate_outlier_candidate_count() CASCADE"
    )
    op.drop_constraint(
        "fk_statistics_calibration_scope_current",
        "calibration_input_scope",
        schema="statistics",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_statistics_repl_outlier_assessment_current",
        "replicate_outlier_assessment",
        schema="statistics",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_statistics_repl_outlier_plan_current",
        "replicate_outlier_detection_plan",
        schema="statistics",
        type_="foreignkey",
    )
    for table in (
        "calibration_input_scope_member",
        "calibration_input_scope_revision",
        "calibration_input_scope",
        "replicate_outlier_assessment_revision",
        "replicate_outlier_assessment",
        "replicate_outlier_candidate",
        "replicate_outlier_detection_run",
        "replicate_outlier_detection_plan_revision",
        "replicate_outlier_detection_plan",
    ):
        op.drop_table(table, schema="statistics")

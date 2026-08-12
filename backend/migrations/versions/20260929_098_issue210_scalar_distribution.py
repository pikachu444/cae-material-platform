"""Issue #210 deterministic scalar-distribution fitting and explicit selection.

Revision ID: 20260929_098_issue210_dist
Revises: 20260928_097_issue207_bundle
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260929_098_issue210_dist"
down_revision: str | None = "20260928_097_issue207_bundle"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ZERO = "'00000000-0000-0000-0000-000000000000'::uuid"
_PLAN_SCHEMA_V1 = "urn:cmp:statistics:reference-tensile-replicate-plan:1.0.0"
_PLAN_SCHEMA_V11 = "urn:cmp:statistics:reference-tensile-replicate-plan:1.1.0"
_RESULT_SCHEMA = "urn:cmp:statistics:scalar-distribution-result:1.0.0"
_SELECTION_SCHEMA = "urn:cmp:statistics:scalar-distribution-selection:1.0.0"


def _identity_columns(uuid: postgresql.UUID[Any]) -> list[sa.Column[object]]:
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


def _revision_columns(uuid: postgresql.UUID[Any]) -> list[sa.Column[object]]:
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
    ]


def _secure(table: str, *, mutable: bool) -> None:
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


def _extend_plan_and_run() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    op.add_column(
        "replicate_statistical_plan_revision",
        sa.Column(
            "scalar_distribution_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        schema="statistics",
    )
    for column in (
        sa.Column("distribution_seed", sa.BigInteger(), nullable=True),
        sa.Column("distribution_bootstrap_samples", sa.SmallInteger(), nullable=True),
        sa.Column("unit_profile_id", uuid, nullable=True),
        sa.Column("unit_profile_revision_id", uuid, nullable=True),
        sa.Column("unit_profile_sha256", sa.CHAR(64, collation="C"), nullable=True),
    ):
        op.add_column("replicate_statistical_plan_revision", column, schema="statistics")
    op.create_check_constraint(
        "ck_statistics_replicate_plan_distribution",
        "replicate_statistical_plan_revision",
        "(NOT scalar_distribution_enabled AND distribution_seed IS NULL "
        "AND distribution_bootstrap_samples IS NULL AND unit_profile_id IS NULL "
        "AND unit_profile_revision_id IS NULL AND unit_profile_sha256 IS NULL) OR "
        "(scalar_distribution_enabled AND distribution_seed BETWEEN 0 AND 4294967295 "
        "AND distribution_bootstrap_samples = 999 AND ((unit_profile_id IS NULL "
        "AND unit_profile_revision_id IS NULL AND unit_profile_sha256 IS NULL) OR "
        "(unit_profile_id IS NOT NULL AND unit_profile_revision_id IS NOT NULL "
        "AND unit_profile_sha256 ~ '^[0-9a-f]{64}$')))",
        schema="statistics",
    )
    op.alter_column(
        "replicate_statistical_plan_revision",
        "scalar_distribution_enabled",
        server_default=None,
        schema="statistics",
    )
    op.create_foreign_key(
        "fk_statistics_replicate_plan_unit_profile",
        "replicate_statistical_plan_revision",
        "unit_profile_revision",
        [
            "organization_id",
            "project_id",
            "classification",
            "unit_profile_id",
            "unit_profile_revision_id",
            "unit_profile_sha256",
        ],
        [
            "organization_id",
            "project_id",
            "classification",
            "aggregate_id",
            "id",
            "content_hash",
        ],
        source_schema="statistics",
        referent_schema="units",
        ondelete="RESTRICT",
    )
    for column in (
        sa.Column("scalar_distribution_result_id", uuid, nullable=True),
        sa.Column("scalar_distribution_result_revision_id", uuid, nullable=True),
        sa.Column("scalar_distribution_artifact_id", uuid, nullable=True),
        sa.Column("scalar_distribution_sha256", sa.CHAR(64, collation="C"), nullable=True),
    ):
        op.add_column("replicate_statistical_run", column, schema="statistics")
    op.drop_constraint(
        "ck_statistics_replicate_run_terminal",
        "replicate_statistical_run",
        schema="statistics",
        type_="check",
    )
    op.create_check_constraint(
        "ck_statistics_replicate_run_terminal",
        "replicate_statistical_run",
        "(status = 'executing' AND ended_at IS NULL AND result_id IS NULL "
        "AND result_revision_id IS NULL AND curve_artifact_id IS NULL "
        "AND curve_sha256 IS NULL AND curve_point_count IS NULL "
        "AND scalar_distribution_result_id IS NULL "
        "AND scalar_distribution_result_revision_id IS NULL "
        "AND scalar_distribution_artifact_id IS NULL "
        "AND scalar_distribution_sha256 IS NULL AND failure_code IS NULL) OR "
        "(status = 'succeeded' AND ended_at IS NOT NULL AND result_id IS NOT NULL "
        "AND result_revision_id IS NOT NULL AND curve_artifact_id IS NOT NULL "
        "AND curve_sha256 ~ '^[0-9a-f]{64}$' AND curve_point_count BETWEEN 2 AND 100000 "
        "AND failure_code IS NULL AND ((scalar_distribution_result_id IS NULL "
        "AND scalar_distribution_result_revision_id IS NULL "
        "AND scalar_distribution_artifact_id IS NULL "
        "AND scalar_distribution_sha256 IS NULL) OR "
        "(scalar_distribution_result_id IS NOT NULL "
        "AND scalar_distribution_result_revision_id IS NOT NULL "
        "AND scalar_distribution_artifact_id IS NOT NULL "
        "AND scalar_distribution_sha256 ~ '^[0-9a-f]{64}$'))) OR "
        "(status = 'failed' AND ended_at IS NOT NULL AND result_id IS NULL "
        "AND result_revision_id IS NULL AND curve_artifact_id IS NULL "
        "AND curve_sha256 IS NULL AND curve_point_count IS NULL "
        "AND scalar_distribution_result_id IS NULL "
        "AND scalar_distribution_result_revision_id IS NULL "
        "AND scalar_distribution_artifact_id IS NULL "
        "AND scalar_distribution_sha256 IS NULL "
        "AND length(btrim(failure_code)) BETWEEN 1 AND 100)",
        schema="statistics",
    )


def _create_distribution_tables() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    op.create_table(
        "scalar_distribution_result",
        *_identity_columns(uuid),
        sa.Column("statistical_run_id", uuid, nullable=False),
        sa.Column("result_kind", sa.String(100), nullable=False),
        *_identity_constraints("statistics_scalar_distribution_result"),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "classification",
            "statistical_run_id",
            name="uq_statistics_scalar_distribution_result_run",
        ),
        sa.CheckConstraint(
            "result_kind = 'scalar_distribution_comparison'",
            name="ck_statistics_scalar_distribution_result_kind",
        ),
        schema="statistics",
    )
    op.create_table(
        "scalar_distribution_result_revision",
        *_revision_columns(uuid),
        sa.Column("result_kind", sa.String(100), nullable=False),
        sa.Column("statistical_run_id", uuid, nullable=False),
        sa.Column("statistical_result_id", uuid, nullable=False),
        sa.Column("statistical_result_revision_id", uuid, nullable=False),
        sa.Column("plan_id", uuid, nullable=False),
        sa.Column("plan_revision_id", uuid, nullable=False),
        sa.Column("selection_id", uuid, nullable=False),
        sa.Column("selection_revision_id", uuid, nullable=False),
        sa.Column("scalar_feature", sa.String(100), nullable=False),
        sa.Column("sample_count", sa.SmallInteger(), nullable=False),
        sa.Column("minimum_sample_count", sa.SmallInteger(), nullable=False),
        sa.Column("small_sample_warning_below", sa.SmallInteger(), nullable=False),
        sa.Column("seed", sa.BigInteger(), nullable=False),
        sa.Column("bootstrap_samples", sa.SmallInteger(), nullable=False),
        sa.Column("unit_profile_id", uuid, nullable=True),
        sa.Column("unit_profile_revision_id", uuid, nullable=True),
        sa.Column("unit_profile_sha256", sa.CHAR(64, collation="C"), nullable=True),
        sa.Column("unit_application_location", sa.String(255), nullable=True),
        sa.Column("unit_application_role", sa.String(32), nullable=True),
        sa.Column("unit_quantity_semantics", sa.String(160), nullable=True),
        sa.Column("unit_dimension", sa.String(80), nullable=True),
        sa.Column("display_unit_id", sa.String(40), nullable=True),
        sa.Column("observations", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("candidates", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("recommended_families", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("recommendation_method", sa.String(160), nullable=False),
        sa.Column("algorithm_version", sa.String(100), nullable=False),
        sa.Column("python_version", sa.String(80), nullable=False),
        sa.Column("numpy_version", sa.String(80), nullable=False),
        sa.Column("scipy_version", sa.String(80), nullable=False),
        sa.Column("rng", sa.String(80), nullable=False),
        sa.Column("source_sha256", sa.CHAR(64, collation="C"), nullable=False),
        sa.Column("lock_sha256", sa.CHAR(64, collation="C"), nullable=False),
        sa.Column("environment_sha256", sa.CHAR(64, collation="C"), nullable=False),
        sa.Column("artifact_id", uuid, nullable=False),
        sa.Column("artifact_sha256", sa.CHAR(64, collation="C"), nullable=False),
        *_revision_constraints("statistics_scalar_distribution_result"),
        sa.CheckConstraint(
            "result_kind = 'scalar_distribution_comparison' "
            "AND scalar_feature = 'peak_engineering_stress_pa' "
            "AND sample_count BETWEEN 2 AND 50 AND minimum_sample_count = 8 "
            "AND small_sample_warning_below = 20 AND seed BETWEEN 0 AND 4294967295 "
            "AND bootstrap_samples = 999 AND jsonb_typeof(observations) = 'array' "
            "AND jsonb_array_length(observations) = sample_count "
            "AND jsonb_typeof(candidates) = 'array' AND jsonb_array_length(candidates) = 3 "
            "AND jsonb_typeof(recommended_families) = 'array' "
            "AND recommendation_method = "
            "'aicc_delta_le_2_at_least_two_successful_candidates_v1' "
            "AND algorithm_version = 'scalar_distribution_fitting_v1' "
            "AND rng = 'numpy.random.PCG64' "
            "AND source_sha256 ~ '^[0-9a-f]{64}$' "
            "AND lock_sha256 ~ '^[0-9a-f]{64}$' "
            "AND environment_sha256 ~ '^[0-9a-f]{64}$' "
            "AND artifact_sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_statistics_scalar_distribution_result_contract",
        ),
        sa.CheckConstraint(
            "(unit_profile_id IS NULL AND unit_profile_revision_id IS NULL "
            "AND unit_profile_sha256 IS NULL AND unit_application_location IS NULL "
            "AND unit_application_role IS NULL AND unit_quantity_semantics IS NULL "
            "AND unit_dimension IS NULL AND display_unit_id IS NULL) OR "
            "(unit_profile_id IS NOT NULL AND unit_profile_revision_id IS NOT NULL "
            "AND unit_profile_sha256 ~ '^[0-9a-f]{64}$' "
            "AND unit_application_location = "
            "'statistics.scalar_distribution.peak_engineering_stress' "
            "AND unit_application_role = 'display' "
            "AND unit_quantity_semantics = 'mechanics.stress.engineering' "
            "AND unit_dimension = 'force_per_area' AND display_unit_id IS NOT NULL)",
            name="ck_statistics_scalar_distribution_result_units",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "classification", "aggregate_id"],
            [
                "statistics.scalar_distribution_result.organization_id",
                "statistics.scalar_distribution_result.project_id",
                "statistics.scalar_distribution_result.classification",
                "statistics.scalar_distribution_result.id",
            ],
            name="fk_statistics_scalar_distribution_result_identity",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "based_on_revision_id"],
            [
                "statistics.scalar_distribution_result_revision.organization_id",
                "statistics.scalar_distribution_result_revision.project_id",
                "statistics.scalar_distribution_result_revision.id",
            ],
            name="fk_statistics_scalar_distribution_result_base",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.ForeignKeyConstraint(
            [
                "organization_id",
                "project_id",
                "classification",
                "statistical_result_id",
                "statistical_result_revision_id",
            ],
            [
                "statistics.replicate_statistical_result_revision.organization_id",
                "statistics.replicate_statistical_result_revision.project_id",
                "statistics.replicate_statistical_result_revision.classification",
                "statistics.replicate_statistical_result_revision.aggregate_id",
                "statistics.replicate_statistical_result_revision.id",
            ],
            name="fk_statistics_scalar_distribution_source_result",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.ForeignKeyConstraint(
            [
                "organization_id",
                "project_id",
                "classification",
                "unit_profile_id",
                "unit_profile_revision_id",
                "unit_profile_sha256",
            ],
            [
                "units.unit_profile_revision.organization_id",
                "units.unit_profile_revision.project_id",
                "units.unit_profile_revision.classification",
                "units.unit_profile_revision.aggregate_id",
                "units.unit_profile_revision.id",
                "units.unit_profile_revision.content_hash",
            ],
            name="fk_statistics_scalar_distribution_unit_profile",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            [
                "organization_id",
                "project_id",
                "classification",
                "artifact_id",
                "artifact_sha256",
            ],
            [
                "artifact.artifact.organization_id",
                "artifact.artifact.project_id",
                "artifact.artifact.classification",
                "artifact.artifact.id",
                "artifact.artifact.sha256",
            ],
            name="fk_statistics_scalar_distribution_artifact",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        schema="statistics",
    )
    op.create_foreign_key(
        "fk_statistics_scalar_distribution_result_current",
        "scalar_distribution_result",
        "scalar_distribution_result_revision",
        ["organization_id", "project_id", "id", "current_revision_id"],
        ["organization_id", "project_id", "aggregate_id", "id"],
        source_schema="statistics",
        referent_schema="statistics",
        ondelete="RESTRICT",
        deferrable=True,
        initially="DEFERRED",
    )
    op.create_table(
        "scalar_distribution_selection",
        *_identity_columns(uuid),
        sa.Column("distribution_result_id", uuid, nullable=False),
        *_identity_constraints("statistics_scalar_distribution_selection"),
        schema="statistics",
    )
    op.create_table(
        "scalar_distribution_selection_revision",
        *_revision_columns(uuid),
        sa.Column("distribution_result_id", uuid, nullable=False),
        sa.Column("distribution_result_revision_id", uuid, nullable=False),
        sa.Column("selected_family", sa.String(32), nullable=False),
        sa.Column("candidate_sha256", sa.CHAR(64, collation="C"), nullable=False),
        sa.Column("selection_reason", sa.Text(), nullable=False),
        *_revision_constraints("statistics_scalar_distribution_selection"),
        sa.CheckConstraint(
            "selected_family IN ('normal', 'lognormal', 'weibull') "
            "AND candidate_sha256 ~ '^[0-9a-f]{64}$' "
            "AND length(btrim(selection_reason)) BETWEEN 1 AND 2000 "
            "AND selection_reason = btrim(selection_reason)",
            name="ck_statistics_scalar_distribution_selection_contract",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "classification", "aggregate_id"],
            [
                "statistics.scalar_distribution_selection.organization_id",
                "statistics.scalar_distribution_selection.project_id",
                "statistics.scalar_distribution_selection.classification",
                "statistics.scalar_distribution_selection.id",
            ],
            name="fk_statistics_scalar_distribution_selection_identity",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "based_on_revision_id"],
            [
                "statistics.scalar_distribution_selection_revision.organization_id",
                "statistics.scalar_distribution_selection_revision.project_id",
                "statistics.scalar_distribution_selection_revision.id",
            ],
            name="fk_statistics_scalar_distribution_selection_base",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.ForeignKeyConstraint(
            [
                "organization_id",
                "project_id",
                "classification",
                "distribution_result_id",
                "distribution_result_revision_id",
            ],
            [
                "statistics.scalar_distribution_result_revision.organization_id",
                "statistics.scalar_distribution_result_revision.project_id",
                "statistics.scalar_distribution_result_revision.classification",
                "statistics.scalar_distribution_result_revision.aggregate_id",
                "statistics.scalar_distribution_result_revision.id",
            ],
            name="fk_statistics_scalar_distribution_selection_result",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        schema="statistics",
    )
    op.create_foreign_key(
        "fk_statistics_scalar_distribution_selection_current",
        "scalar_distribution_selection",
        "scalar_distribution_selection_revision",
        ["organization_id", "project_id", "id", "current_revision_id"],
        ["organization_id", "project_id", "aggregate_id", "id"],
        source_schema="statistics",
        referent_schema="statistics",
        ondelete="RESTRICT",
        deferrable=True,
        initially="DEFERRED",
    )
    op.create_foreign_key(
        "fk_statistics_replicate_run_distribution_result",
        "replicate_statistical_run",
        "scalar_distribution_result_revision",
        [
            "organization_id",
            "project_id",
            "classification",
            "scalar_distribution_result_id",
            "scalar_distribution_result_revision_id",
        ],
        ["organization_id", "project_id", "classification", "aggregate_id", "id"],
        source_schema="statistics",
        referent_schema="statistics",
        ondelete="RESTRICT",
        deferrable=True,
        initially="DEFERRED",
    )
    op.create_foreign_key(
        "fk_statistics_replicate_run_distribution_artifact",
        "replicate_statistical_run",
        "artifact",
        [
            "organization_id",
            "project_id",
            "classification",
            "scalar_distribution_artifact_id",
            "scalar_distribution_sha256",
        ],
        ["organization_id", "project_id", "classification", "id", "sha256"],
        source_schema="statistics",
        referent_schema="artifact",
        ondelete="RESTRICT",
        deferrable=True,
        initially="DEFERRED",
    )


def _replace_guards() -> None:
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION statistics.guard_replicate_plan_revision_insert()
        RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE selected_kind text; selected_count integer;
        BEGIN
            IF NOT ((NEW.schema_id = '{_PLAN_SCHEMA_V1}' AND NEW.schema_version = '1.0.0'
                     AND NOT NEW.scalar_distribution_enabled)
                    OR (NEW.schema_id = '{_PLAN_SCHEMA_V11}'
                        AND NEW.schema_version = '1.1.0')) THEN
                RAISE EXCEPTION 'replicate Statistical Plan schema is unsupported';
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
        """
        CREATE FUNCTION statistics.guard_scalar_distribution_result_insert()
        RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE run_row statistics.replicate_statistical_run%ROWTYPE;
        DECLARE plan_enabled boolean;
        DECLARE source_run uuid;
        BEGIN
            IF NEW.schema_id <> 'urn:cmp:statistics:scalar-distribution-result:1.0.0'
               OR NEW.schema_version <> '1.0.0' THEN
                RAISE EXCEPTION 'scalar-distribution Result schema is fixed';
            END IF;
            SELECT * INTO run_row FROM statistics.replicate_statistical_run
             WHERE organization_id = NEW.organization_id AND project_id = NEW.project_id
               AND classification = NEW.classification AND id = NEW.statistical_run_id;
            SELECT scalar_distribution_enabled INTO plan_enabled
              FROM statistics.replicate_statistical_plan_revision
             WHERE organization_id = NEW.organization_id AND project_id = NEW.project_id
               AND classification = NEW.classification AND aggregate_id = NEW.plan_id
               AND id = NEW.plan_revision_id;
            SELECT statistical_run_id INTO source_run
              FROM statistics.replicate_statistical_result_revision
             WHERE organization_id = NEW.organization_id AND project_id = NEW.project_id
               AND classification = NEW.classification
               AND aggregate_id = NEW.statistical_result_id
               AND id = NEW.statistical_result_revision_id;
            IF run_row.status <> 'executing' OR NOT plan_enabled
               OR source_run IS DISTINCT FROM NEW.statistical_run_id
               OR run_row.plan_id <> NEW.plan_id
               OR run_row.plan_revision_id <> NEW.plan_revision_id
               OR run_row.selection_id <> NEW.selection_id
               OR run_row.selection_revision_id <> NEW.selection_revision_id
               OR run_row.sample_count <> NEW.sample_count THEN
                RAISE EXCEPTION 'scalar-distribution Result does not match its Run and Plan';
            END IF;
            RETURN NEW;
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER statistics_scalar_distribution_result_guard BEFORE INSERT ON "
        "statistics.scalar_distribution_result_revision FOR EACH ROW EXECUTE FUNCTION "
        "statistics.guard_scalar_distribution_result_insert()"
    )
    op.execute(
        """
        CREATE FUNCTION statistics.guard_scalar_distribution_selection_insert()
        RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE candidate jsonb;
        BEGIN
            IF NEW.schema_id <> 'urn:cmp:statistics:scalar-distribution-selection:1.0.0'
               OR NEW.schema_version <> '1.0.0' THEN
                RAISE EXCEPTION 'scalar-distribution selection schema is fixed';
            END IF;
            SELECT item INTO candidate
              FROM statistics.scalar_distribution_result_revision result,
                   jsonb_array_elements(result.candidates) item
             WHERE result.organization_id = NEW.organization_id
               AND result.project_id = NEW.project_id
               AND result.classification = NEW.classification
               AND result.aggregate_id = NEW.distribution_result_id
               AND result.id = NEW.distribution_result_revision_id
               AND item->>'family' = NEW.selected_family;
            IF candidate IS NULL OR candidate->>'status' <> 'succeeded'
               OR candidate->>'candidate_sha256' <> NEW.candidate_sha256 THEN
                RAISE EXCEPTION 'selection must pin an exact successful candidate digest';
            END IF;
            RETURN NEW;
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER statistics_scalar_distribution_selection_guard BEFORE INSERT ON "
        "statistics.scalar_distribution_selection_revision FOR EACH ROW EXECUTE FUNCTION "
        "statistics.guard_scalar_distribution_selection_insert()"
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION statistics.guard_replicate_run_transition()
        RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE distribution_enabled boolean;
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
            SELECT scalar_distribution_enabled INTO distribution_enabled
              FROM statistics.replicate_statistical_plan_revision
             WHERE organization_id = NEW.organization_id AND project_id = NEW.project_id
               AND classification = NEW.classification AND aggregate_id = NEW.plan_id
               AND id = NEW.plan_revision_id;
            IF NEW.status = 'succeeded' AND distribution_enabled
               AND NEW.scalar_distribution_result_revision_id IS NULL THEN
                RAISE EXCEPTION 'enabled scalar-distribution output is missing';
            END IF;
            IF NEW.status = 'succeeded' AND NOT distribution_enabled
               AND NEW.scalar_distribution_result_revision_id IS NOT NULL THEN
                RAISE EXCEPTION 'disabled scalar-distribution output is unexpected';
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


def upgrade() -> None:
    _extend_plan_and_run()
    _create_distribution_tables()
    _replace_guards()
    for table in (
        "scalar_distribution_result",
        "scalar_distribution_result_revision",
        "scalar_distribution_selection",
        "scalar_distribution_selection_revision",
    ):
        _secure(
            table,
            mutable=table in {"scalar_distribution_result", "scalar_distribution_selection"},
        )
    for table in ("scalar_distribution_result", "scalar_distribution_selection"):
        op.execute(
            f"CREATE TRIGGER statistics_{table}_head BEFORE UPDATE OR DELETE ON "
            f"statistics.{table} FOR EACH ROW EXECUTE FUNCTION "
            "revisioning.guard_identity_head_update()"
        )
    for table in (
        "scalar_distribution_result_revision",
        "scalar_distribution_selection_revision",
    ):
        op.execute(
            f"CREATE TRIGGER statistics_{table}_immutable BEFORE UPDATE OR DELETE ON "
            f"statistics.{table} FOR EACH ROW EXECUTE FUNCTION "
            "revisioning.reject_immutable_row_mutation()"
        )
    op.create_index(
        "ix_statistics_scalar_distribution_result_plan",
        "scalar_distribution_result_revision",
        ["organization_id", "project_id", "classification", "plan_revision_id"],
        schema="statistics",
    )
    op.create_index(
        "ix_statistics_scalar_distribution_selection_result",
        "scalar_distribution_selection_revision",
        ["organization_id", "project_id", "classification", "distribution_result_id"],
        schema="statistics",
    )


def _restore_previous_guards() -> None:
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION statistics.guard_replicate_plan_revision_insert()
        RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE selected_kind text; selected_count integer;
        BEGIN
            IF NEW.schema_id <> '{_PLAN_SCHEMA_V1}' OR NEW.schema_version <> '1.0.0' THEN
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
        """
        CREATE OR REPLACE FUNCTION statistics.guard_replicate_run_transition()
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


def downgrade() -> None:
    connection = op.get_bind()
    if connection.execute(
        sa.text(
            "SELECT EXISTS ("
            "SELECT 1 FROM statistics.replicate_statistical_plan_revision "
            "WHERE schema_id = :schema_id "
            "UNION ALL SELECT 1 FROM statistics.scalar_distribution_result"
            ")"
        ),
        {"schema_id": _PLAN_SCHEMA_V11},
    ).scalar_one():
        raise RuntimeError(
            "Issue #210 downgrade refused: immutable scalar-distribution Plan or Result "
            "evidence exists"
        )
    _restore_previous_guards()
    op.execute("DROP FUNCTION statistics.guard_scalar_distribution_selection_insert() CASCADE")
    op.execute("DROP FUNCTION statistics.guard_scalar_distribution_result_insert() CASCADE")
    op.drop_constraint(
        "fk_statistics_replicate_run_distribution_artifact",
        "replicate_statistical_run",
        schema="statistics",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_statistics_replicate_run_distribution_result",
        "replicate_statistical_run",
        schema="statistics",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_statistics_scalar_distribution_selection_current",
        "scalar_distribution_selection",
        schema="statistics",
        type_="foreignkey",
    )
    op.drop_table("scalar_distribution_selection_revision", schema="statistics")
    op.drop_table("scalar_distribution_selection", schema="statistics")
    op.drop_constraint(
        "fk_statistics_scalar_distribution_result_current",
        "scalar_distribution_result",
        schema="statistics",
        type_="foreignkey",
    )
    op.drop_table("scalar_distribution_result_revision", schema="statistics")
    op.drop_table("scalar_distribution_result", schema="statistics")
    op.drop_constraint(
        "ck_statistics_replicate_run_terminal",
        "replicate_statistical_run",
        schema="statistics",
        type_="check",
    )
    for name in (
        "scalar_distribution_sha256",
        "scalar_distribution_artifact_id",
        "scalar_distribution_result_revision_id",
        "scalar_distribution_result_id",
    ):
        op.drop_column("replicate_statistical_run", name, schema="statistics")
    op.drop_constraint(
        "fk_statistics_replicate_plan_unit_profile",
        "replicate_statistical_plan_revision",
        schema="statistics",
        type_="foreignkey",
    )
    op.drop_constraint(
        "ck_statistics_replicate_plan_distribution",
        "replicate_statistical_plan_revision",
        schema="statistics",
        type_="check",
    )
    for name in (
        "unit_profile_sha256",
        "unit_profile_revision_id",
        "unit_profile_id",
        "distribution_bootstrap_samples",
        "distribution_seed",
        "scalar_distribution_enabled",
    ):
        op.drop_column("replicate_statistical_plan_revision", name, schema="statistics")
    op.create_check_constraint(
        "ck_statistics_replicate_run_terminal",
        "replicate_statistical_run",
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
        schema="statistics",
    )

"""Add the first typed Selection and committed reference crop Processing slice.

Revision ID: 20260715_017_t19
Revises: 20260714_016_t08_t12
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260715_017_t19"
down_revision: str | None = "20260714_016_t08_t12"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ZERO = "'00000000-0000-0000-0000-000000000000'::uuid"
_CROP_KIND = "reference_tensile_inclusive_crop"
_INPUT_SCHEMA = "urn:cmp:datasets:reference-tensile-normalized-parquet:1.0.0"
_OUTPUT_SCHEMA = "urn:cmp:datasets:reference-tensile-processed-parquet:1.0.0"
_DIAGNOSTICS_SCHEMA = "urn:cmp:processing:reference-tensile-crop-diagnostics:1.0.0"


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
        sa.CheckConstraint(
            "content_hash ~ '^[0-9a-f]{64}$'", name=f"ck_{prefix}_revision_hash"
        ),
        sa.CheckConstraint(
            "length(btrim(schema_id)) BETWEEN 1 AND 255",
            name=f"ck_{prefix}_revision_schema_id",
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


def _secure(schema: str, table: str, read_permission: str, write_permission: str) -> None:
    for operation, predicate, permission in (
        ("select", "USING", read_permission),
        ("insert", "WITH CHECK", write_permission),
    ):
        op.execute(
            f"CREATE POLICY {schema}_{table}_{operation} ON {schema}.{table} "
            f"FOR {operation.upper()} {predicate} (access_control.can_access_row("
            f"organization_id, project_id, classification, '{permission}'))"
        )
    op.execute(
        f"CREATE POLICY {schema}_{table}_update ON {schema}.{table} FOR UPDATE "
        "USING (access_control.can_access_row(organization_id, project_id, classification, "
        f"'{write_permission}')) WITH CHECK (access_control.can_access_row(organization_id, "
        f"project_id, classification, '{write_permission}'))"
    )


def _create_selection_tables() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    op.create_table(
        "dataset_selection",
        *_identity_columns(uuid),
        sa.Column("selection_label", sa.String(length=160), nullable=False),
        *_identity_constraints("datasets_dataset_selection"),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "classification",
            "selection_label",
            name="uq_datasets_dataset_selection_label",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "classification",
            "id",
            "selection_label",
            name="uq_datasets_dataset_selection_identity_label",
        ),
        sa.CheckConstraint(
            "length(btrim(selection_label)) BETWEEN 1 AND 160 "
            "AND selection_label = btrim(selection_label)",
            name="ck_datasets_dataset_selection_label",
        ),
        schema="datasets",
    )
    op.create_table(
        "dataset_selection_revision",
        *_revision_columns(uuid),
        sa.Column("dataset_id", uuid, nullable=False),
        sa.Column("dataset_revision_id", uuid, nullable=False),
        sa.Column("member_count", sa.SmallInteger(), nullable=False),
        *_revision_constraints("datasets_dataset_selection"),
        sa.CheckConstraint(
            "member_count = 1", name="ck_datasets_dataset_selection_revision_member_count"
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "classification",
            "id",
            name="uq_datasets_dataset_selection_revision_classified_id",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "aggregate_id"],
            [
                "datasets.dataset_selection.organization_id",
                "datasets.dataset_selection.project_id",
                "datasets.dataset_selection.id",
            ],
            name="fk_datasets_dataset_selection_revision_identity",
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
            ],
            [
                "datasets.dataset_selection.organization_id",
                "datasets.dataset_selection.project_id",
                "datasets.dataset_selection.classification",
                "datasets.dataset_selection.id",
            ],
            name="fk_datasets_dataset_selection_revision_identity_scope",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
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
            name="fk_datasets_dataset_selection_revision_dataset",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "aggregate_id", "based_on_revision_id"],
            [
                "datasets.dataset_selection_revision.organization_id",
                "datasets.dataset_selection_revision.project_id",
                "datasets.dataset_selection_revision.aggregate_id",
                "datasets.dataset_selection_revision.id",
            ],
            name="fk_datasets_dataset_selection_revision_base",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        schema="datasets",
    )
    op.create_foreign_key(
        "fk_datasets_dataset_selection_current_revision",
        "dataset_selection",
        "dataset_selection_revision",
        ["organization_id", "project_id", "id", "current_revision_id"],
        ["organization_id", "project_id", "aggregate_id", "id"],
        source_schema="datasets",
        referent_schema="datasets",
        ondelete="RESTRICT",
        deferrable=True,
        initially="DEFERRED",
    )
    op.create_index(
        "ix_datasets_dataset_selection_revision_dataset",
        "dataset_selection_revision",
        ["organization_id", "project_id", "classification", "dataset_revision_id"],
        schema="datasets",
    )
    for table in ("dataset_selection", "dataset_selection_revision"):
        op.execute(f"ALTER TABLE datasets.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE datasets.{table} FORCE ROW LEVEL SECURITY")
        _secure("datasets", table, "dataset.read", "dataset.write")
    op.execute(
        "CREATE TRIGGER datasets_dataset_selection_head_only BEFORE UPDATE OR DELETE "
        "ON datasets.dataset_selection FOR EACH ROW "
        "EXECUTE FUNCTION revisioning.guard_identity_head_update()"
    )
    op.execute(
        "CREATE TRIGGER datasets_dataset_selection_revision_immutable BEFORE UPDATE OR DELETE "
        "ON datasets.dataset_selection_revision FOR EACH ROW "
        "EXECUTE FUNCTION revisioning.reject_immutable_row_mutation()"
    )
    op.execute(
        """
        CREATE FUNCTION datasets.guard_reference_dataset_selection_revision_insert()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
          selected_representation text;
        BEGIN
          SELECT representation INTO selected_representation
          FROM datasets.dataset_revision
          WHERE organization_id = NEW.organization_id
            AND project_id = NEW.project_id
            AND classification = NEW.classification
            AND aggregate_id = NEW.dataset_id
            AND id = NEW.dataset_revision_id;
          IF selected_representation IS DISTINCT FROM 'normalized' THEN
            RAISE EXCEPTION USING ERRCODE = '23514',
              MESSAGE = 'reference Dataset Selection requires a normalized Dataset revision';
          END IF;
          RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        "CREATE TRIGGER datasets_dataset_selection_revision_reference_guard "
        "BEFORE INSERT ON datasets.dataset_selection_revision FOR EACH ROW "
        "EXECUTE FUNCTION datasets.guard_reference_dataset_selection_revision_insert()"
    )


def _create_processing_tables() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    op.create_table(
        "processing_recipe",
        *_identity_columns(uuid),
        sa.Column("recipe_label", sa.String(length=160), nullable=False),
        sa.Column("recipe_kind", sa.String(length=100), nullable=False),
        *_identity_constraints("processing_processing_recipe"),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "classification",
            "recipe_label",
            name="uq_processing_recipe_label",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "classification",
            "id",
            "recipe_label",
            "recipe_kind",
            name="uq_processing_recipe_identity_kind",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "classification",
            "id",
            "recipe_kind",
            name="uq_processing_recipe_identity_recipe_kind",
        ),
        sa.CheckConstraint(
            "length(btrim(recipe_label)) BETWEEN 1 AND 160 AND recipe_label = btrim(recipe_label)",
            name="ck_processing_recipe_label",
        ),
        sa.CheckConstraint(
            f"recipe_kind = '{_CROP_KIND}'", name="ck_processing_recipe_kind"
        ),
        schema="processing",
    )
    op.create_table(
        "processing_recipe_revision",
        *_revision_columns(uuid),
        sa.Column("recipe_kind", sa.String(length=100), nullable=False),
        sa.Column("step_ordinal", sa.SmallInteger(), nullable=False),
        sa.Column("minimum_engineering_strain", sa.Double(), nullable=False),
        sa.Column("maximum_engineering_strain", sa.Double(), nullable=False),
        sa.Column("input_schema_ref", sa.String(length=500), nullable=False),
        sa.Column("output_schema_ref", sa.String(length=500), nullable=False),
        sa.Column("diagnostics_schema_ref", sa.String(length=500), nullable=False),
        *_revision_constraints("processing_processing_recipe"),
        sa.CheckConstraint(
            f"recipe_kind = '{_CROP_KIND}'", name="ck_processing_recipe_revision_kind"
        ),
        sa.CheckConstraint(
            "step_ordinal = 0", name="ck_processing_recipe_revision_step_ordinal"
        ),
        sa.CheckConstraint(
            "minimum_engineering_strain >= 0 "
            "AND minimum_engineering_strain < 'Infinity'::float8",
            name="ck_processing_recipe_revision_minimum",
        ),
        sa.CheckConstraint(
            "maximum_engineering_strain > minimum_engineering_strain "
            "AND maximum_engineering_strain < 'Infinity'::float8",
            name="ck_processing_recipe_revision_maximum",
        ),
        sa.CheckConstraint(
            f"input_schema_ref = '{_INPUT_SCHEMA}'",
            name="ck_processing_recipe_revision_input_schema",
        ),
        sa.CheckConstraint(
            f"output_schema_ref = '{_OUTPUT_SCHEMA}'",
            name="ck_processing_recipe_revision_output_schema",
        ),
        sa.CheckConstraint(
            f"diagnostics_schema_ref = '{_DIAGNOSTICS_SCHEMA}'",
            name="ck_processing_recipe_revision_diagnostics_schema",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "classification",
            "id",
            name="uq_processing_recipe_revision_classified_id",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "aggregate_id"],
            [
                "processing.processing_recipe.organization_id",
                "processing.processing_recipe.project_id",
                "processing.processing_recipe.id",
            ],
            name="fk_processing_recipe_revision_identity",
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
                "recipe_kind",
            ],
            [
                "processing.processing_recipe.organization_id",
                "processing.processing_recipe.project_id",
                "processing.processing_recipe.classification",
                "processing.processing_recipe.id",
                "processing.processing_recipe.recipe_kind",
            ],
            name="fk_processing_recipe_revision_identity_kind",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "aggregate_id", "based_on_revision_id"],
            [
                "processing.processing_recipe_revision.organization_id",
                "processing.processing_recipe_revision.project_id",
                "processing.processing_recipe_revision.aggregate_id",
                "processing.processing_recipe_revision.id",
            ],
            name="fk_processing_recipe_revision_base",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        schema="processing",
    )
    op.create_foreign_key(
        "fk_processing_recipe_current_revision",
        "processing_recipe",
        "processing_recipe_revision",
        ["organization_id", "project_id", "id", "current_revision_id"],
        ["organization_id", "project_id", "aggregate_id", "id"],
        source_schema="processing",
        referent_schema="processing",
        ondelete="RESTRICT",
        deferrable=True,
        initially="DEFERRED",
    )
    op.create_table(
        "processing_run",
        sa.Column("id", uuid, nullable=False),
        sa.Column("organization_id", uuid, nullable=False),
        sa.Column("project_id", uuid, nullable=False),
        sa.Column("classification", sa.String(length=64), nullable=False),
        sa.Column("selection_id", uuid, nullable=False),
        sa.Column("selection_revision_id", uuid, nullable=False),
        sa.Column("recipe_id", uuid, nullable=False),
        sa.Column("recipe_revision_id", uuid, nullable=False),
        sa.Column("input_dataset_id", uuid, nullable=False),
        sa.Column("input_dataset_revision_id", uuid, nullable=False),
        sa.Column("execution_mode", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("input_point_count", sa.BigInteger(), nullable=False),
        sa.Column("output_point_count", sa.BigInteger(), nullable=True),
        sa.Column("removed_point_count", sa.BigInteger(), nullable=True),
        sa.Column("result_artifact_id", uuid, nullable=True),
        sa.Column("result_sha256", sa.CHAR(length=64, collation="C"), nullable=True),
        sa.Column("output_dataset_id", uuid, nullable=True),
        sa.Column("output_dataset_revision_id", uuid, nullable=True),
        sa.Column("failure_code", sa.String(length=100), nullable=True),
        sa.Column("change_reason", sa.Text(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", uuid, nullable=False),
        sa.Column("request_id", uuid, nullable=False),
        sa.Column("trace_id", sa.String(length=255), nullable=False),
        sa.PrimaryKeyConstraint("organization_id", "project_id", "id", name="pk_processing_run"),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "classification",
            "id",
            name="uq_processing_run_scope_identity",
        ),
        sa.CheckConstraint(
            "id <> "
            + _ZERO
            + " AND selection_id <> "
            + _ZERO
            + " AND selection_revision_id <> "
            + _ZERO
            + " AND recipe_id <> "
            + _ZERO
            + " AND recipe_revision_id <> "
            + _ZERO
            + " AND input_dataset_id <> "
            + _ZERO
            + " AND input_dataset_revision_id <> "
            + _ZERO
            + " AND created_by <> "
            + _ZERO
            + " AND request_id <> "
            + _ZERO,
            name="ck_processing_run_nonzero_ids",
        ),
        sa.CheckConstraint(
            "classification ~ '^[a-z][a-z0-9_.-]{0,63}$'",
            name="ck_processing_run_classification",
        ),
        sa.CheckConstraint(
            "execution_mode = 'committed'", name="ck_processing_run_execution_mode"
        ),
        sa.CheckConstraint(
            "status IN ('executing', 'succeeded', 'failed')", name="ck_processing_run_status"
        ),
        sa.CheckConstraint(
            "input_point_count BETWEEN 2 AND 100000", name="ck_processing_run_input_points"
        ),
        sa.CheckConstraint(
            "length(btrim(change_reason)) BETWEEN 1 AND 2000",
            name="ck_processing_run_reason",
        ),
        sa.CheckConstraint(
            "length(btrim(trace_id)) BETWEEN 1 AND 255", name="ck_processing_run_trace"
        ),
        sa.CheckConstraint(
            "(result_artifact_id IS NULL) = (result_sha256 IS NULL)",
            name="ck_processing_run_result_artifact_pair",
        ),
        sa.CheckConstraint(
            "result_sha256 IS NULL OR result_sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_processing_run_result_hash",
        ),
        sa.CheckConstraint(
            "(status = 'executing' AND ended_at IS NULL AND output_point_count IS NULL "
            "AND removed_point_count IS NULL AND result_artifact_id IS NULL "
            "AND output_dataset_id IS NULL AND output_dataset_revision_id IS NULL "
            "AND failure_code IS NULL) OR "
            "(status = 'succeeded' AND ended_at IS NOT NULL "
            "AND output_point_count BETWEEN 2 AND 100000 AND removed_point_count >= 0 "
            "AND output_point_count + removed_point_count = input_point_count "
            "AND result_artifact_id IS NOT NULL AND output_dataset_id IS NOT NULL "
            "AND output_dataset_revision_id IS NOT NULL AND failure_code IS NULL) OR "
            "(status = 'failed' AND ended_at IS NOT NULL AND output_point_count IS NULL "
            "AND removed_point_count IS NULL AND output_dataset_id IS NULL "
            "AND output_dataset_revision_id IS NULL "
            "AND length(btrim(failure_code)) BETWEEN 1 AND 100)",
            name="ck_processing_run_terminal_shape",
        ),
        sa.CheckConstraint(
            "ended_at IS NULL OR ended_at >= started_at", name="ck_processing_run_time"
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
            name="fk_processing_run_selection_revision",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.ForeignKeyConstraint(
            [
                "organization_id",
                "project_id",
                "classification",
                "recipe_id",
                "recipe_revision_id",
            ],
            [
                "processing.processing_recipe_revision.organization_id",
                "processing.processing_recipe_revision.project_id",
                "processing.processing_recipe_revision.classification",
                "processing.processing_recipe_revision.aggregate_id",
                "processing.processing_recipe_revision.id",
            ],
            name="fk_processing_run_recipe_revision",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.ForeignKeyConstraint(
            [
                "organization_id",
                "project_id",
                "classification",
                "input_dataset_id",
                "input_dataset_revision_id",
            ],
            [
                "datasets.dataset_revision.organization_id",
                "datasets.dataset_revision.project_id",
                "datasets.dataset_revision.classification",
                "datasets.dataset_revision.aggregate_id",
                "datasets.dataset_revision.id",
            ],
            name="fk_processing_run_input_dataset_revision",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.ForeignKeyConstraint(
            [
                "organization_id",
                "project_id",
                "classification",
                "result_artifact_id",
                "result_sha256",
            ],
            [
                "artifact.artifact.organization_id",
                "artifact.artifact.project_id",
                "artifact.artifact.classification",
                "artifact.artifact.id",
                "artifact.artifact.sha256",
            ],
            name="fk_processing_run_result_artifact",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        schema="processing",
    )
    op.create_index(
        "ix_processing_recipe_tenant_created",
        "processing_recipe",
        ["organization_id", "project_id", "classification", "created_at"],
        schema="processing",
    )
    op.create_index(
        "ix_processing_run_input",
        "processing_run",
        ["organization_id", "project_id", "classification", "input_dataset_revision_id"],
        schema="processing",
    )
    for table in ("processing_recipe", "processing_recipe_revision", "processing_run"):
        op.execute(f"ALTER TABLE processing.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE processing.{table} FORCE ROW LEVEL SECURITY")
        _secure("processing", table, "processing.read", "processing.execute")
    op.execute(
        "CREATE TRIGGER processing_recipe_head_only BEFORE UPDATE OR DELETE "
        "ON processing.processing_recipe FOR EACH ROW "
        "EXECUTE FUNCTION revisioning.guard_identity_head_update()"
    )
    op.execute(
        "CREATE TRIGGER processing_recipe_revision_immutable BEFORE UPDATE OR DELETE "
        "ON processing.processing_recipe_revision FOR EACH ROW "
        "EXECUTE FUNCTION revisioning.reject_immutable_row_mutation()"
    )


def _create_processing_run_guards() -> None:
    op.execute(
        f"""
        CREATE FUNCTION processing.guard_processing_run_insert()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
          selected_dataset_id uuid;
          selected_dataset_revision_id uuid;
          selected_representation text;
          selected_recipe_kind text;
        BEGIN
          SELECT dataset_id, dataset_revision_id
          INTO selected_dataset_id, selected_dataset_revision_id
          FROM datasets.dataset_selection_revision
          WHERE organization_id = NEW.organization_id
            AND project_id = NEW.project_id
            AND classification = NEW.classification
            AND aggregate_id = NEW.selection_id
            AND id = NEW.selection_revision_id;
          IF NOT FOUND
             OR selected_dataset_id <> NEW.input_dataset_id
             OR selected_dataset_revision_id <> NEW.input_dataset_revision_id THEN
            RAISE EXCEPTION USING ERRCODE = '23514',
              MESSAGE = 'Processing Run input must equal the pinned Selection revision member';
          END IF;
          SELECT recipe_kind INTO selected_recipe_kind
          FROM processing.processing_recipe_revision
          WHERE organization_id = NEW.organization_id
            AND project_id = NEW.project_id
            AND classification = NEW.classification
            AND aggregate_id = NEW.recipe_id
            AND id = NEW.recipe_revision_id;
          IF selected_recipe_kind IS DISTINCT FROM '{_CROP_KIND}' THEN
            RAISE EXCEPTION USING ERRCODE = '23514',
              MESSAGE = 'Processing Run requires the typed reference crop Recipe revision';
          END IF;
          SELECT representation INTO selected_representation
          FROM datasets.dataset_revision
          WHERE organization_id = NEW.organization_id
            AND project_id = NEW.project_id
            AND classification = NEW.classification
            AND aggregate_id = NEW.input_dataset_id
            AND id = NEW.input_dataset_revision_id;
          IF selected_representation IS DISTINCT FROM 'normalized' THEN
            RAISE EXCEPTION USING ERRCODE = '23514',
              MESSAGE = 'Processing Run requires a normalized reference Dataset revision';
          END IF;
          RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION processing.guard_processing_run_transition()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
          output_run_id uuid;
          output_source_id uuid;
          output_artifact_id uuid;
          output_sha256 text;
        BEGIN
          IF TG_OP = 'DELETE' THEN
            RAISE EXCEPTION USING ERRCODE = '55000',
              MESSAGE = 'Processing Run rows are append-only and cannot be deleted';
          END IF;
          IF OLD.status <> 'executing' OR NEW.status NOT IN ('succeeded', 'failed') THEN
            RAISE EXCEPTION USING ERRCODE = '55000',
              MESSAGE = 'Processing Run may transition only once from executing '
                || 'to a terminal state';
          END IF;
          IF NEW.organization_id IS DISTINCT FROM OLD.organization_id
             OR NEW.project_id IS DISTINCT FROM OLD.project_id
             OR NEW.classification IS DISTINCT FROM OLD.classification
             OR NEW.selection_id IS DISTINCT FROM OLD.selection_id
             OR NEW.selection_revision_id IS DISTINCT FROM OLD.selection_revision_id
             OR NEW.recipe_id IS DISTINCT FROM OLD.recipe_id
             OR NEW.recipe_revision_id IS DISTINCT FROM OLD.recipe_revision_id
             OR NEW.input_dataset_id IS DISTINCT FROM OLD.input_dataset_id
             OR NEW.input_dataset_revision_id IS DISTINCT FROM OLD.input_dataset_revision_id
             OR NEW.execution_mode IS DISTINCT FROM OLD.execution_mode
             OR NEW.input_point_count IS DISTINCT FROM OLD.input_point_count
             OR NEW.change_reason IS DISTINCT FROM OLD.change_reason
             OR NEW.started_at IS DISTINCT FROM OLD.started_at
             OR NEW.created_by IS DISTINCT FROM OLD.created_by
             OR NEW.request_id IS DISTINCT FROM OLD.request_id
             OR NEW.trace_id IS DISTINCT FROM OLD.trace_id THEN
            RAISE EXCEPTION USING ERRCODE = '55000',
              MESSAGE = 'Processing Run plan and input snapshot are immutable';
          END IF;
          IF NEW.status = 'failed' AND EXISTS (
            SELECT 1
            FROM datasets.dataset_revision
            WHERE organization_id = NEW.organization_id
              AND project_id = NEW.project_id
              AND classification = NEW.classification
              AND processing_run_id = NEW.id
          ) THEN
            RAISE EXCEPTION USING ERRCODE = '23514',
              MESSAGE = 'Processing Run with a committed processed Dataset cannot be failed';
          END IF;
          IF NEW.status = 'succeeded' THEN
            SELECT processing_run_id, source_dataset_revision_id, data_artifact_id, data_sha256
            INTO output_run_id, output_source_id, output_artifact_id, output_sha256
            FROM datasets.dataset_revision
            WHERE organization_id = NEW.organization_id
              AND project_id = NEW.project_id
              AND classification = NEW.classification
              AND aggregate_id = NEW.output_dataset_id
              AND id = NEW.output_dataset_revision_id
              AND representation = 'processed';
            IF NOT FOUND
               OR output_run_id <> NEW.id
               OR output_source_id <> NEW.input_dataset_revision_id
               OR output_artifact_id <> NEW.result_artifact_id
               OR output_sha256 <> NEW.result_sha256 THEN
              RAISE EXCEPTION USING ERRCODE = '23514',
                MESSAGE = 'Processing Run result must match its processed Dataset revision';
            END IF;
          END IF;
          RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        "CREATE TRIGGER processing_run_insert_guard BEFORE INSERT ON processing.processing_run "
        "FOR EACH ROW EXECUTE FUNCTION processing.guard_processing_run_insert()"
    )
    op.execute(
        "CREATE TRIGGER processing_run_transition_guard BEFORE UPDATE OR DELETE "
        "ON processing.processing_run FOR EACH ROW "
        "EXECUTE FUNCTION processing.guard_processing_run_transition()"
    )


def _alter_dataset_for_processed_output() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    op.add_column("dataset", sa.Column("processing_run_id", uuid, nullable=True), schema="datasets")
    op.add_column(
        "dataset_revision", sa.Column("processing_run_id", uuid, nullable=True), schema="datasets"
    )
    op.drop_constraint("uq_datasets_dataset_source", "dataset", schema="datasets", type_="unique")
    # Keep the original identity-source FK and its unique key intact: it verifies that each
    # Dataset revision matches *its own* stable identity.  PostgreSQL UNIQUE treats NULLs as
    # distinct, so extending that key with an optional Processing Run would silently weaken the
    # raw/normalized identity check.  Use explicit partial unique indexes for the two disjoint
    # typed source families instead.
    op.create_index(
        "ux_datasets_dataset_import_source",
        "dataset",
        [
            "organization_id",
            "project_id",
            "classification",
            "test_run_id",
            "raw_asset_id",
            "raw_artifact_id",
            "mapping_sha256",
        ],
        schema="datasets",
        unique=True,
        postgresql_where=sa.text("processing_run_id IS NULL"),
    )
    op.create_index(
        "ux_datasets_dataset_processing_run",
        "dataset",
        [
            "organization_id",
            "project_id",
            "classification",
            "processing_run_id",
        ],
        schema="datasets",
        unique=True,
        postgresql_where=sa.text("processing_run_id IS NOT NULL"),
    )
    op.drop_constraint(
        "ck_datasets_dataset_revision_representation",
        "dataset_revision",
        schema="datasets",
        type_="check",
    )
    op.drop_constraint(
        "ck_datasets_dataset_revision_source_representation",
        "dataset_revision",
        schema="datasets",
        type_="check",
    )
    op.drop_constraint(
        "fk_datasets_dataset_revision_source",
        "dataset_revision",
        schema="datasets",
        type_="foreignkey",
    )
    op.create_check_constraint(
        "ck_datasets_dataset_revision_representation",
        "dataset_revision",
        "representation IN ('raw', 'normalized', 'processed')",
        schema="datasets",
    )
    op.create_check_constraint(
        "ck_datasets_dataset_revision_source_representation",
        "dataset_revision",
        "(representation = 'raw' AND revision_no = 1 "
        "AND based_on_revision_id IS NULL AND source_dataset_revision_id IS NULL "
        "AND processing_run_id IS NULL AND data_artifact_id = raw_artifact_id) OR "
        "(representation = 'normalized' AND revision_no = 2 "
        "AND source_dataset_revision_id IS NOT NULL "
        "AND source_dataset_revision_id = based_on_revision_id "
        "AND processing_run_id IS NULL AND data_artifact_id <> raw_artifact_id) OR "
        "(representation = 'processed' AND revision_no = 1 "
        "AND based_on_revision_id IS NULL AND source_dataset_revision_id IS NOT NULL "
        "AND processing_run_id IS NOT NULL AND data_artifact_id <> raw_artifact_id)",
        schema="datasets",
    )
    op.create_foreign_key(
        "fk_datasets_dataset_revision_source",
        "dataset_revision",
        "dataset_revision",
        ["organization_id", "project_id", "source_dataset_revision_id"],
        ["organization_id", "project_id", "id"],
        source_schema="datasets",
        referent_schema="datasets",
        ondelete="RESTRICT",
        deferrable=True,
        initially="DEFERRED",
    )
    op.create_foreign_key(
        "fk_datasets_dataset_processing_run",
        "dataset",
        "processing_run",
        ["organization_id", "project_id", "classification", "processing_run_id"],
        ["organization_id", "project_id", "classification", "id"],
        source_schema="datasets",
        referent_schema="processing",
        ondelete="RESTRICT",
        deferrable=True,
        initially="DEFERRED",
    )
    op.create_foreign_key(
        "fk_datasets_dataset_revision_processing_run",
        "dataset_revision",
        "processing_run",
        ["organization_id", "project_id", "classification", "processing_run_id"],
        ["organization_id", "project_id", "classification", "id"],
        source_schema="datasets",
        referent_schema="processing",
        ondelete="RESTRICT",
        deferrable=True,
        initially="DEFERRED",
    )
    op.create_index(
        "ix_datasets_dataset_processing_run",
        "dataset",
        ["organization_id", "project_id", "classification", "processing_run_id"],
        schema="datasets",
    )


def _replace_dataset_guard() -> None:
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION datasets.guard_reference_dataset_revision_insert()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
          source datasets.dataset_revision%ROWTYPE;
          selected_artifact_kind text;
          selected_artifact_schema text;
          identity_processing_run_id uuid;
          run_input_revision_id uuid;
          run_status text;
        BEGIN
          SELECT processing_run_id INTO identity_processing_run_id
          FROM datasets.dataset
          WHERE organization_id = NEW.organization_id
            AND project_id = NEW.project_id
            AND id = NEW.aggregate_id;
          IF identity_processing_run_id IS DISTINCT FROM NEW.processing_run_id THEN
            RAISE EXCEPTION USING ERRCODE = '23514',
              MESSAGE = 'Dataset identity and revision must agree on Processing Run ownership';
          END IF;
          IF NEW.representation = 'normalized' THEN
            SELECT * INTO source
            FROM datasets.dataset_revision
            WHERE organization_id = NEW.organization_id
              AND project_id = NEW.project_id
              AND aggregate_id = NEW.aggregate_id
              AND id = NEW.source_dataset_revision_id;
            IF NOT FOUND
               OR source.representation <> 'raw'
               OR source.raw_asset_id <> NEW.raw_asset_id
               OR source.raw_artifact_id <> NEW.raw_artifact_id
               OR source.mapping_sha256 <> NEW.mapping_sha256 THEN
              RAISE EXCEPTION USING ERRCODE = '23514',
                MESSAGE = 'normalized Dataset must derive from its matching raw Dataset revision';
            END IF;
          ELSIF NEW.representation = 'processed' THEN
            SELECT * INTO source
            FROM datasets.dataset_revision
            WHERE organization_id = NEW.organization_id
              AND project_id = NEW.project_id
              AND id = NEW.source_dataset_revision_id;
            IF NOT FOUND
               OR source.classification <> NEW.classification
               OR source.representation <> 'normalized'
               OR source.test_run_id <> NEW.test_run_id
               OR source.raw_asset_id <> NEW.raw_asset_id
               OR source.raw_artifact_id <> NEW.raw_artifact_id
               OR source.mapping_sha256 <> NEW.mapping_sha256 THEN
              RAISE EXCEPTION USING ERRCODE = '23514',
                MESSAGE = 'processed Dataset must derive from a matching normalized '
                  || 'Dataset revision';
            END IF;
            SELECT input_dataset_revision_id, status
            INTO run_input_revision_id, run_status
            FROM processing.processing_run
            WHERE organization_id = NEW.organization_id
              AND project_id = NEW.project_id
              AND classification = NEW.classification
              AND id = NEW.processing_run_id;
            IF run_input_revision_id IS DISTINCT FROM NEW.source_dataset_revision_id
               OR run_status NOT IN ('executing', 'succeeded') THEN
              RAISE EXCEPTION USING ERRCODE = '23514',
                MESSAGE = 'processed Dataset must be owned by an active matching Processing Run';
            END IF;
          END IF;
          SELECT a.artifact_kind, a.schema_ref
          INTO selected_artifact_kind, selected_artifact_schema
          FROM artifact.artifact AS a
          WHERE organization_id = NEW.organization_id
            AND project_id = NEW.project_id
            AND classification = NEW.classification
            AND id = NEW.data_artifact_id;
          IF NEW.representation = 'raw' THEN
            IF selected_artifact_kind IS DISTINCT FROM 'raw' THEN
              RAISE EXCEPTION USING ERRCODE = '23514',
                MESSAGE = 'raw Dataset must use a raw Artifact';
            END IF;
          ELSIF NEW.representation = 'normalized' THEN
            IF selected_artifact_kind IS DISTINCT FROM 'derived'
               OR selected_artifact_schema IS DISTINCT FROM '{_INPUT_SCHEMA}' THEN
              RAISE EXCEPTION USING ERRCODE = '23514',
                MESSAGE = 'normalized Dataset must use the reference normalized Parquet Artifact';
            END IF;
          ELSIF selected_artifact_kind IS DISTINCT FROM 'derived'
             OR selected_artifact_schema IS DISTINCT FROM '{_OUTPUT_SCHEMA}' THEN
            RAISE EXCEPTION USING ERRCODE = '23514',
              MESSAGE = 'processed Dataset must use the reference processed Parquet Artifact';
          END IF;
          RETURN NEW;
        END;
        $$
        """
    )


def _restore_normalized_dataset_guard() -> None:
    """Restore the exact raw/normalized guard owned by the preceding Dataset migration."""

    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION datasets.guard_reference_dataset_revision_insert()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
          source datasets.dataset_revision%ROWTYPE;
          selected_artifact_kind text;
          selected_artifact_schema text;
        BEGIN
          IF NEW.representation = 'normalized' THEN
            SELECT * INTO source
            FROM datasets.dataset_revision
            WHERE organization_id = NEW.organization_id
              AND project_id = NEW.project_id
              AND aggregate_id = NEW.aggregate_id
              AND id = NEW.source_dataset_revision_id;
            IF NOT FOUND
               OR source.representation <> 'raw'
               OR source.raw_asset_id <> NEW.raw_asset_id
               OR source.raw_artifact_id <> NEW.raw_artifact_id
               OR source.mapping_sha256 <> NEW.mapping_sha256 THEN
              RAISE EXCEPTION USING ERRCODE = '23514',
                MESSAGE = 'normalized Dataset must derive from its matching raw Dataset revision';
            END IF;
          END IF;
          SELECT a.artifact_kind, a.schema_ref
          INTO selected_artifact_kind, selected_artifact_schema
          FROM artifact.artifact AS a
          WHERE organization_id = NEW.organization_id
            AND project_id = NEW.project_id
            AND classification = NEW.classification
            AND id = NEW.data_artifact_id;
          IF NEW.representation = 'raw' THEN
            IF selected_artifact_kind IS DISTINCT FROM 'raw' THEN
              RAISE EXCEPTION USING ERRCODE = '23514',
                MESSAGE = 'raw Dataset must use a raw Artifact';
            END IF;
          ELSIF selected_artifact_kind IS DISTINCT FROM 'derived'
             OR selected_artifact_schema IS DISTINCT FROM '{_INPUT_SCHEMA}' THEN
            RAISE EXCEPTION USING ERRCODE = '23514',
              MESSAGE = 'normalized Dataset must use the reference Parquet derived Artifact';
          END IF;
          RETURN NEW;
        END;
        $$
        """
    )


def _link_processing_output_foreign_keys() -> None:
    op.create_foreign_key(
        "fk_processing_run_output_dataset",
        "processing_run",
        "dataset",
        ["organization_id", "project_id", "classification", "output_dataset_id"],
        ["organization_id", "project_id", "classification", "id"],
        source_schema="processing",
        referent_schema="datasets",
        ondelete="RESTRICT",
        deferrable=True,
        initially="DEFERRED",
    )
    op.create_foreign_key(
        "fk_processing_run_output_dataset_revision",
        "processing_run",
        "dataset_revision",
        [
            "organization_id",
            "project_id",
            "classification",
            "output_dataset_id",
            "output_dataset_revision_id",
        ],
        [
            "organization_id",
            "project_id",
            "classification",
            "aggregate_id",
            "id",
        ],
        source_schema="processing",
        referent_schema="datasets",
        ondelete="RESTRICT",
        deferrable=True,
        initially="DEFERRED",
    )


def upgrade() -> None:
    op.execute("CREATE SCHEMA processing")
    _create_selection_tables()
    _create_processing_tables()
    _alter_dataset_for_processed_output()
    _replace_dataset_guard()
    _link_processing_output_foreign_keys()
    _create_processing_run_guards()


def downgrade() -> None:
    # A downgrade must never discard immutable Selection, Recipe, Run, or processed Dataset
    # facts.  Operators can only roll back an empty T-19 schema after validating a replacement
    # migration path; production history remains append-only.
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM processing.processing_run)
             OR EXISTS (SELECT 1 FROM processing.processing_recipe)
             OR EXISTS (SELECT 1 FROM datasets.dataset_selection)
             OR EXISTS (
               SELECT 1 FROM datasets.dataset_revision WHERE representation = 'processed'
             ) THEN
            RAISE EXCEPTION USING ERRCODE = '55000',
              MESSAGE = 'T-19 downgrade requires empty Processing, Selection, '
                || 'and processed Dataset history';
          END IF;
        END;
        $$
        """
    )
    op.execute("DROP TRIGGER processing_run_transition_guard ON processing.processing_run")
    op.execute("DROP TRIGGER processing_run_insert_guard ON processing.processing_run")
    op.execute("DROP FUNCTION processing.guard_processing_run_transition()")
    op.execute("DROP FUNCTION processing.guard_processing_run_insert()")
    op.drop_constraint(
        "fk_processing_run_output_dataset_revision",
        "processing_run",
        schema="processing",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_processing_run_output_dataset",
        "processing_run",
        schema="processing",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_datasets_dataset_revision_processing_run",
        "dataset_revision",
        schema="datasets",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_datasets_dataset_processing_run",
        "dataset",
        schema="datasets",
        type_="foreignkey",
    )
    _restore_normalized_dataset_guard()
    op.drop_constraint(
        "fk_datasets_dataset_revision_source",
        "dataset_revision",
        schema="datasets",
        type_="foreignkey",
    )
    op.drop_constraint(
        "ck_datasets_dataset_revision_source_representation",
        "dataset_revision",
        schema="datasets",
        type_="check",
    )
    op.drop_constraint(
        "ck_datasets_dataset_revision_representation",
        "dataset_revision",
        schema="datasets",
        type_="check",
    )
    op.drop_index(
        "ux_datasets_dataset_processing_run", table_name="dataset", schema="datasets"
    )
    op.drop_index(
        "ux_datasets_dataset_import_source", table_name="dataset", schema="datasets"
    )
    op.drop_index("ix_datasets_dataset_processing_run", table_name="dataset", schema="datasets")
    op.drop_column("dataset_revision", "processing_run_id", schema="datasets")
    op.drop_column("dataset", "processing_run_id", schema="datasets")

    op.create_unique_constraint(
        "uq_datasets_dataset_source",
        "dataset",
        [
            "organization_id",
            "project_id",
            "classification",
            "test_run_id",
            "raw_asset_id",
            "raw_artifact_id",
            "mapping_sha256",
        ],
        schema="datasets",
    )
    op.create_check_constraint(
        "ck_datasets_dataset_revision_representation",
        "dataset_revision",
        "representation IN ('raw', 'normalized')",
        schema="datasets",
    )
    op.create_check_constraint(
        "ck_datasets_dataset_revision_source_representation",
        "dataset_revision",
        "(representation = 'raw' AND revision_no = 1 "
        "AND based_on_revision_id IS NULL AND source_dataset_revision_id IS NULL "
        "AND data_artifact_id = raw_artifact_id) OR "
        "(representation = 'normalized' AND revision_no = 2 "
        "AND source_dataset_revision_id IS NOT NULL "
        "AND source_dataset_revision_id = based_on_revision_id "
        "AND data_artifact_id <> raw_artifact_id)",
        schema="datasets",
    )
    op.create_foreign_key(
        "fk_datasets_dataset_revision_source",
        "dataset_revision",
        "dataset_revision",
        ["organization_id", "project_id", "aggregate_id", "source_dataset_revision_id"],
        ["organization_id", "project_id", "aggregate_id", "id"],
        source_schema="datasets",
        referent_schema="datasets",
        ondelete="RESTRICT",
        deferrable=True,
        initially="DEFERRED",
    )

    op.drop_table("processing_run", schema="processing")
    op.drop_constraint(
        "fk_processing_recipe_current_revision",
        "processing_recipe",
        schema="processing",
        type_="foreignkey",
    )
    op.drop_table("processing_recipe_revision", schema="processing")
    op.drop_table("processing_recipe", schema="processing")
    op.execute("DROP SCHEMA processing")
    op.execute(
        "DROP TRIGGER datasets_dataset_selection_revision_reference_guard "
        "ON datasets.dataset_selection_revision"
    )
    op.execute("DROP FUNCTION datasets.guard_reference_dataset_selection_revision_insert()")
    op.drop_constraint(
        "fk_datasets_dataset_selection_current_revision",
        "dataset_selection",
        schema="datasets",
        type_="foreignkey",
    )
    op.drop_table("dataset_selection_revision", schema="datasets")
    op.drop_table("dataset_selection", schema="datasets")

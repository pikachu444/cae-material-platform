"""Issue #206 curve Artifact schema compatibility.

Revision ID: 20260927_096_issue206_curve
Revises: 20260926_095_issue205_units

The curve definition remains inside immutable Artifact bytes.  This migration
does not add a lifecycle or table; it widens existing typed guards so an exact
minor Parquet schema revision can be pinned beside historical 1.0.0 values.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260927_096_issue206_curve"
down_revision: str | None = "20260926_095_issue205_units"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NORMALIZED_V1 = "urn:cmp:datasets:reference-tensile-normalized-parquet:1.0.0"
_NORMALIZED_V11 = "urn:cmp:datasets:reference-tensile-normalized-parquet:1.1.0"
_PROCESSED_V1 = "urn:cmp:datasets:reference-tensile-processed-parquet:1.0.0"
_PROCESSED_V11 = "urn:cmp:datasets:reference-tensile-processed-parquet:1.1.0"
_PAIR_V1 = "urn:cmp:statistics:reference-tensile-pair-curve-parquet:1.0.0"
_PAIR_V11 = "urn:cmp:statistics:reference-tensile-pair-curve-parquet:1.1.0"
_REPLICATE_V1 = "urn:cmp:statistics:reference-tensile-replicate-curve-parquet:1.0.0"
_REPLICATE_V11 = "urn:cmp:statistics:reference-tensile-replicate-curve-parquet:1.1.0"
_CANONICAL_V11 = "urn:cmp:test-data:normalized-parquet:1.1.0"


def _schema_condition(column: str, old: str, current: str, *, legacy_only: bool) -> str:
    if legacy_only:
        return f"{column} = '{old}'"
    return f"{column} IN ('{old}', '{current}')"


def _replace_typed_constraints(*, legacy_only: bool) -> None:
    input_condition = _schema_condition(
        "input_schema_ref", _NORMALIZED_V1, _NORMALIZED_V11, legacy_only=legacy_only
    )
    output_condition = _schema_condition(
        "output_schema_ref", _PROCESSED_V1, _PROCESSED_V11, legacy_only=legacy_only
    )
    pair_condition = _schema_condition(
        "curve_output_schema_ref", _PAIR_V1, _PAIR_V11, legacy_only=legacy_only
    )
    replicate_condition = _schema_condition(
        "curve_output_schema_ref",
        _REPLICATE_V1,
        _REPLICATE_V11,
        legacy_only=legacy_only,
    )
    op.execute(
        f"""
        ALTER TABLE processing.processing_recipe_revision
          DROP CONSTRAINT ck_processing_recipe_revision_input_schema,
          DROP CONSTRAINT ck_processing_recipe_revision_output_schema;
        ALTER TABLE processing.processing_recipe_revision
          ADD CONSTRAINT ck_processing_recipe_revision_input_schema
            CHECK ({input_condition}),
          ADD CONSTRAINT ck_processing_recipe_revision_output_schema
            CHECK ({output_condition});

        ALTER TABLE statistics.statistical_plan_revision
          DROP CONSTRAINT ck_statistics_statistical_plan_revision_input_schema,
          DROP CONSTRAINT ck_statistics_statistical_plan_revision_curve_schema;
        ALTER TABLE statistics.statistical_plan_revision
          ADD CONSTRAINT ck_statistics_statistical_plan_revision_input_schema
            CHECK ({input_condition}),
          ADD CONSTRAINT ck_statistics_statistical_plan_revision_curve_schema
            CHECK ({pair_condition});

        ALTER TABLE statistics.replicate_statistical_plan_revision
          DROP CONSTRAINT ck_statistics_replicate_plan_rev_curve_schema;
        ALTER TABLE statistics.replicate_statistical_plan_revision
          ADD CONSTRAINT ck_statistics_replicate_plan_rev_curve_schema
            CHECK ({replicate_condition});
        """
    )


def _replace_dataset_guard(*, legacy_only: bool) -> None:
    normalized_condition = _schema_condition(
        "selected_artifact_schema",
        _NORMALIZED_V1,
        _NORMALIZED_V11,
        legacy_only=legacy_only,
    )
    processed_condition = _schema_condition(
        "selected_artifact_schema",
        _PROCESSED_V1,
        _PROCESSED_V11,
        legacy_only=legacy_only,
    )
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
               OR selected_artifact_schema IS NULL
               OR NOT ({normalized_condition}) THEN
              RAISE EXCEPTION USING ERRCODE = '23514',
                MESSAGE = 'normalized Dataset must use a reviewed reference normalized '
                  || 'Parquet Artifact';
            END IF;
          ELSIF selected_artifact_kind IS DISTINCT FROM 'derived'
             OR selected_artifact_schema IS NULL
             OR NOT ({processed_condition}) THEN
            RAISE EXCEPTION USING ERRCODE = '23514',
              MESSAGE = 'processed Dataset must use a reviewed reference processed '
                || 'Parquet Artifact';
          END IF;
          RETURN NEW;
        END;
        $$
        """
    )


def _replace_pair_result_guard(*, legacy_only: bool) -> None:
    pair_condition = _schema_condition(
        "artifact_schema", _PAIR_V1, _PAIR_V11, legacy_only=legacy_only
    )
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION statistics.guard_statistical_result_revision_insert()
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
             OR artifact_schema IS NULL OR NOT ({pair_condition}) THEN
            RAISE EXCEPTION USING ERRCODE = '23514',
              MESSAGE = 'Statistical Result requires a reviewed typed curve Artifact';
          END IF;
          RETURN NEW;
        END;
        $$
        """
    )


def _refuse_lossy_downgrade() -> None:
    current_refs = ", ".join(
        f"'{value}'"
        for value in (
            _NORMALIZED_V11,
            _PROCESSED_V11,
            _PAIR_V11,
            _REPLICATE_V11,
            _CANONICAL_V11,
        )
    )
    op.execute(
        f"""
        DO $$
        BEGIN
          IF EXISTS (
            SELECT 1 FROM artifact.artifact WHERE schema_ref IN ({current_refs})
          ) OR EXISTS (
            SELECT 1 FROM processing.processing_recipe_revision
             WHERE input_schema_ref = '{_NORMALIZED_V11}'
                OR output_schema_ref = '{_PROCESSED_V11}'
          ) OR EXISTS (
            SELECT 1 FROM statistics.statistical_plan_revision
             WHERE input_schema_ref = '{_NORMALIZED_V11}'
                OR curve_output_schema_ref = '{_PAIR_V11}'
          ) OR EXISTS (
            SELECT 1 FROM statistics.replicate_statistical_plan_revision
             WHERE curve_output_schema_ref = '{_REPLICATE_V11}'
          ) THEN
            RAISE EXCEPTION
              'Issue #206 downgrade refused: immutable curve schema 1.1.0 evidence exists';
          END IF;
        END
        $$
        """
    )


def upgrade() -> None:
    _replace_typed_constraints(legacy_only=False)
    _replace_dataset_guard(legacy_only=False)
    _replace_pair_result_guard(legacy_only=False)


def downgrade() -> None:
    _refuse_lossy_downgrade()
    _replace_pair_result_guard(legacy_only=True)
    _replace_dataset_guard(legacy_only=True)
    _replace_typed_constraints(legacy_only=True)

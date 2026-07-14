"""Add typed T-28 validation response, health, metric, and verdict records.

Revision ID: 20260722_024_t28
Revises: 20260721_023_t27
"""

# ruff: noqa: E501

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260722_024_t28"
down_revision: str | None = "20260721_023_t27"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ZERO = "'00000000-0000-0000-0000-000000000000'::uuid"
_NATIVE_SCHEMA = "urn:cmp:validation:reference-native-result:1.0.0"
_NORMALIZED_RESPONSE_SCHEMA = "urn:cmp:validation:reference-normalized-response:1.0.0"
_HEALTH_REPORT_SCHEMA = "urn:cmp:validation:reference-numerical-health-report:1.0.0"
_VALIDATION_RESULT_SCHEMA = "urn:cmp:validation:reference-validation-result:1.0.0"
_METRIC_PROFILE = "urn:cmp:validation:reference-relative-rmse:1.0.0"
_THRESHOLD_PROFILE = "urn:cmp:validation:reference-relative-rmse-threshold:1.0.0"
_ALIGNMENT_PROFILE = "urn:cmp:validation:reference-linear-interpolation-observed-grid:1.0.0"


def _secure(table: str) -> None:
    for operation, predicate, permission in (
        ("select", "USING", "validation.read"),
        ("insert", "WITH CHECK", "validation.execute"),
    ):
        op.execute(
            f"CREATE POLICY validation_{table}_{operation} ON validation.{table} "
            f"FOR {operation.upper()} {predicate} (access_control.can_access_row("
            f"organization_id, project_id, classification, '{permission}'))"
        )
    op.execute(
        f"CREATE POLICY validation_{table}_update ON validation.{table} FOR UPDATE "
        "USING (access_control.can_access_row(organization_id, project_id, classification, "
        "'validation.execute')) WITH CHECK (access_control.can_access_row("
        "organization_id, project_id, classification, 'validation.execute'))"
    )


def _create_tables() -> None:
    op.execute(
        f"""
        CREATE TABLE validation.validation_response_extraction (
          id uuid NOT NULL,
          organization_id uuid NOT NULL,
          project_id uuid NOT NULL,
          classification varchar(64) NOT NULL,
          validation_run_id uuid NOT NULL,
          validation_result_manifest_id uuid NOT NULL,
          source_native_result_artifact_id uuid NULL,
          source_native_result_sha256 char(64) COLLATE "C" NULL,
          extraction_status varchar(32) NOT NULL,
          normalized_response_artifact_id uuid NULL,
          normalized_response_sha256 char(64) COLLATE "C" NULL,
          point_count integer NULL,
          reason_code varchar(100) NULL,
          created_at timestamptz NOT NULL,
          created_by uuid NOT NULL,
          CONSTRAINT pk_validation_response_extraction PRIMARY KEY (organization_id, project_id, id),
          CONSTRAINT uq_validation_response_extraction_scope_identity
            UNIQUE (organization_id, project_id, classification, id),
          CONSTRAINT uq_validation_response_extraction_run
            UNIQUE (organization_id, project_id, classification, validation_run_id),
          CONSTRAINT ck_validation_response_extraction_nonzero_ids CHECK (
            id <> {_ZERO} AND validation_run_id <> {_ZERO}
            AND validation_result_manifest_id <> {_ZERO} AND created_by <> {_ZERO}),
          CONSTRAINT ck_validation_response_extraction_classification CHECK (
            classification ~ '^[a-z][a-z0-9_.-]{{0,63}}$'),
          CONSTRAINT ck_validation_response_extraction_hashes CHECK (
            ((source_native_result_artifact_id IS NULL AND source_native_result_sha256 IS NULL)
             OR (source_native_result_artifact_id IS NOT NULL
                 AND source_native_result_sha256 ~ '^[0-9a-f]{{64}}$'))
            AND ((normalized_response_artifact_id IS NULL AND normalized_response_sha256 IS NULL)
                 OR (normalized_response_artifact_id IS NOT NULL
                     AND normalized_response_sha256 ~ '^[0-9a-f]{{64}}$'))),
          CONSTRAINT ck_validation_response_extraction_state CHECK (
            (extraction_status = 'extracted'
             AND normalized_response_artifact_id IS NOT NULL
             AND normalized_response_sha256 IS NOT NULL
             AND point_count BETWEEN 2 AND 10000
             AND reason_code IS NULL)
            OR (extraction_status = 'not_evaluated'
                AND normalized_response_artifact_id IS NULL
                AND normalized_response_sha256 IS NULL
                AND point_count IS NULL)),
          CONSTRAINT ck_validation_response_extraction_reason CHECK (
            reason_code IS NULL OR reason_code ~ '^[a-z][a-z0-9_]{0,99}$'),
          CONSTRAINT fk_validation_response_extraction_run FOREIGN KEY
            (organization_id, project_id, classification, validation_run_id)
            REFERENCES validation.validation_run (organization_id, project_id, classification, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_validation_response_extraction_manifest FOREIGN KEY
            (organization_id, project_id, classification, validation_result_manifest_id)
            REFERENCES validation.validation_run_result_manifest
              (organization_id, project_id, classification, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE validation.validation_numerical_health_report (
          id uuid NOT NULL,
          organization_id uuid NOT NULL,
          project_id uuid NOT NULL,
          classification varchar(64) NOT NULL,
          validation_run_id uuid NOT NULL,
          validation_result_manifest_id uuid NOT NULL,
          response_extraction_id uuid NOT NULL,
          health_status varchar(32) NOT NULL,
          solver_termination varchar(32) NOT NULL,
          native_result_state varchar(32) NOT NULL,
          expected_output_point_count integer NOT NULL,
          observed_output_point_count integer NULL,
          output_complete boolean NOT NULL,
          finite_values boolean NOT NULL,
          strictly_increasing_strain boolean NOT NULL,
          reason_code varchar(100) NULL,
          report_artifact_id uuid NOT NULL,
          report_sha256 char(64) COLLATE "C" NOT NULL,
          created_at timestamptz NOT NULL,
          created_by uuid NOT NULL,
          CONSTRAINT pk_validation_numerical_health_report PRIMARY KEY (organization_id, project_id, id),
          CONSTRAINT uq_validation_numerical_health_report_scope_identity
            UNIQUE (organization_id, project_id, classification, id),
          CONSTRAINT uq_validation_numerical_health_report_run
            UNIQUE (organization_id, project_id, classification, validation_run_id),
          CONSTRAINT ck_validation_numerical_health_report_nonzero_ids CHECK (
            id <> {_ZERO} AND validation_run_id <> {_ZERO}
            AND validation_result_manifest_id <> {_ZERO} AND response_extraction_id <> {_ZERO}
            AND report_artifact_id <> {_ZERO} AND created_by <> {_ZERO}),
          CONSTRAINT ck_validation_numerical_health_report_classification CHECK (
            classification ~ '^[a-z][a-z0-9_.-]{{0,63}}$'),
          CONSTRAINT ck_validation_numerical_health_report_values CHECK (
            expected_output_point_count BETWEEN 2 AND 10000
            AND (observed_output_point_count IS NULL
                 OR observed_output_point_count BETWEEN 0 AND 10000)
            AND report_sha256 ~ '^[0-9a-f]{{64}}$'
            AND solver_termination IN ('normal', 'abnormal', 'not_available')
            AND native_result_state IN ('available', 'not_available')),
          CONSTRAINT ck_validation_numerical_health_report_state CHECK (
            (health_status = 'healthy' AND output_complete AND finite_values
             AND strictly_increasing_strain AND reason_code IS NULL)
            OR (health_status IN ('unhealthy', 'not_evaluated') AND reason_code IS NOT NULL)),
          CONSTRAINT ck_validation_numerical_health_report_reason CHECK (
            reason_code IS NULL OR reason_code ~ '^[a-z][a-z0-9_]{0,99}$'),
          CONSTRAINT fk_validation_numerical_health_report_run FOREIGN KEY
            (organization_id, project_id, classification, validation_run_id)
            REFERENCES validation.validation_run (organization_id, project_id, classification, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_validation_numerical_health_report_manifest FOREIGN KEY
            (organization_id, project_id, classification, validation_result_manifest_id)
            REFERENCES validation.validation_run_result_manifest
              (organization_id, project_id, classification, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_validation_numerical_health_report_extraction FOREIGN KEY
            (organization_id, project_id, classification, response_extraction_id)
            REFERENCES validation.validation_response_extraction
              (organization_id, project_id, classification, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE validation.validation_result (
          id uuid NOT NULL,
          organization_id uuid NOT NULL,
          project_id uuid NOT NULL,
          classification varchar(64) NOT NULL,
          validation_run_id uuid NOT NULL,
          validation_result_manifest_id uuid NOT NULL,
          response_extraction_id uuid NOT NULL,
          numerical_health_report_id uuid NOT NULL,
          experimental_selection_id uuid NOT NULL,
          experimental_selection_revision_id uuid NOT NULL,
          normalized_response_artifact_id uuid NULL,
          normalized_response_sha256 char(64) COLLATE "C" NULL,
          numerical_health_report_artifact_id uuid NOT NULL,
          numerical_health_report_sha256 char(64) COLLATE "C" NOT NULL,
          metric_profile_id varchar(255) NOT NULL,
          threshold_profile_id varchar(255) NOT NULL,
          alignment_profile_id varchar(255) NOT NULL,
          relative_rmse_threshold double precision NOT NULL,
          experimental_point_count integer NOT NULL,
          simulated_point_count integer NULL,
          compared_point_count integer NOT NULL,
          root_mean_squared_error_pa double precision NULL,
          relative_root_mean_squared_error double precision NULL,
          normalization_stress_scale_pa double precision NULL,
          holdout_independence varchar(64) NOT NULL,
          verdict varchar(32) NOT NULL,
          reason_code varchar(100) NULL,
          result_artifact_id uuid NOT NULL,
          result_sha256 char(64) COLLATE "C" NOT NULL,
          created_at timestamptz NOT NULL,
          created_by uuid NOT NULL,
          change_reason text NOT NULL,
          request_id uuid NOT NULL,
          trace_id varchar(255) NOT NULL,
          CONSTRAINT pk_validation_result PRIMARY KEY (organization_id, project_id, id),
          CONSTRAINT uq_validation_result_scope_identity
            UNIQUE (organization_id, project_id, classification, id),
          CONSTRAINT uq_validation_result_run
            UNIQUE (organization_id, project_id, classification, validation_run_id),
          CONSTRAINT ck_validation_result_nonzero_ids CHECK (
            id <> {_ZERO} AND validation_run_id <> {_ZERO}
            AND validation_result_manifest_id <> {_ZERO} AND response_extraction_id <> {_ZERO}
            AND numerical_health_report_id <> {_ZERO} AND experimental_selection_id <> {_ZERO}
            AND experimental_selection_revision_id <> {_ZERO}
            AND numerical_health_report_artifact_id <> {_ZERO} AND result_artifact_id <> {_ZERO}
            AND created_by <> {_ZERO} AND request_id <> {_ZERO}),
          CONSTRAINT ck_validation_result_classification CHECK (
            classification ~ '^[a-z][a-z0-9_.-]{{0,63}}$'),
          CONSTRAINT ck_validation_result_artifact_hashes CHECK (
            ((normalized_response_artifact_id IS NULL AND normalized_response_sha256 IS NULL)
             OR (normalized_response_artifact_id IS NOT NULL
                 AND normalized_response_sha256 ~ '^[0-9a-f]{{64}}$'))
            AND numerical_health_report_sha256 ~ '^[0-9a-f]{{64}}$'
            AND result_sha256 ~ '^[0-9a-f]{{64}}$'),
          CONSTRAINT ck_validation_result_profiles CHECK (
            metric_profile_id = '{_METRIC_PROFILE}'
            AND threshold_profile_id = '{_THRESHOLD_PROFILE}'
            AND alignment_profile_id = '{_ALIGNMENT_PROFILE}'
            AND relative_rmse_threshold = 0.05),
          CONSTRAINT ck_validation_result_numerics CHECK (
            experimental_point_count BETWEEN 2 AND 100000
            AND (simulated_point_count IS NULL OR simulated_point_count BETWEEN 2 AND 10000)
            AND compared_point_count BETWEEN 0 AND 100000
            AND (root_mean_squared_error_pa IS NULL
                 OR (root_mean_squared_error_pa >= 0 AND root_mean_squared_error_pa < 'Infinity'::float8))
            AND (relative_root_mean_squared_error IS NULL
                 OR (relative_root_mean_squared_error >= 0
                     AND relative_root_mean_squared_error < 'Infinity'::float8))
            AND (normalization_stress_scale_pa IS NULL
                 OR (normalization_stress_scale_pa > 0
                     AND normalization_stress_scale_pa < 'Infinity'::float8))),
          CONSTRAINT ck_validation_result_metric_columns CHECK (
            (root_mean_squared_error_pa IS NULL
             AND relative_root_mean_squared_error IS NULL
             AND normalization_stress_scale_pa IS NULL
             AND compared_point_count = 0)
            OR (root_mean_squared_error_pa IS NOT NULL
                AND relative_root_mean_squared_error IS NOT NULL
                AND normalization_stress_scale_pa IS NOT NULL
                AND compared_point_count >= 2)),
          CONSTRAINT ck_validation_result_verdict CHECK (
            holdout_independence IN ('not_applicable_manual_ir', 'independent_selection', 'overlaps_calibration_selection')
            AND ((verdict IN ('passed', 'failed')
                  AND reason_code IS NULL
                  AND holdout_independence <> 'overlaps_calibration_selection'
                  AND root_mean_squared_error_pa IS NOT NULL)
                 OR (verdict = 'not_evaluated' AND reason_code IS NOT NULL))
            AND (verdict <> 'passed' OR relative_root_mean_squared_error <= relative_rmse_threshold)
            AND (verdict <> 'failed' OR relative_root_mean_squared_error > relative_rmse_threshold)),
          CONSTRAINT ck_validation_result_text CHECK (
            (reason_code IS NULL OR reason_code ~ '^[a-z][a-z0-9_]{0,99}$')
            AND length(btrim(change_reason)) BETWEEN 1 AND 2000
            AND length(btrim(trace_id)) BETWEEN 1 AND 255),
          CONSTRAINT fk_validation_result_run FOREIGN KEY
            (organization_id, project_id, classification, validation_run_id)
            REFERENCES validation.validation_run (organization_id, project_id, classification, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_validation_result_manifest FOREIGN KEY
            (organization_id, project_id, classification, validation_result_manifest_id)
            REFERENCES validation.validation_run_result_manifest
              (organization_id, project_id, classification, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_validation_result_extraction FOREIGN KEY
            (organization_id, project_id, classification, response_extraction_id)
            REFERENCES validation.validation_response_extraction
              (organization_id, project_id, classification, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_validation_result_health FOREIGN KEY
            (organization_id, project_id, classification, numerical_health_report_id)
            REFERENCES validation.validation_numerical_health_report
              (organization_id, project_id, classification, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_validation_result_selection FOREIGN KEY
            (organization_id, project_id, classification,
             experimental_selection_id, experimental_selection_revision_id)
            REFERENCES datasets.dataset_selection_revision
              (organization_id, project_id, classification, aggregate_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE validation.validation_result_comparison_point (
          organization_id uuid NOT NULL,
          project_id uuid NOT NULL,
          classification varchar(64) NOT NULL,
          validation_result_id uuid NOT NULL,
          ordinal integer NOT NULL,
          engineering_strain double precision NOT NULL,
          observed_engineering_stress_pa double precision NOT NULL,
          simulated_engineering_stress_pa double precision NOT NULL,
          residual_engineering_stress_pa double precision NOT NULL,
          created_at timestamptz NOT NULL,
          created_by uuid NOT NULL,
          CONSTRAINT pk_validation_result_comparison_point
            PRIMARY KEY (organization_id, project_id, validation_result_id, ordinal),
          CONSTRAINT uq_validation_result_comparison_point_scope_ordinal
            UNIQUE (organization_id, project_id, classification, validation_result_id, ordinal),
          CONSTRAINT ck_validation_result_comparison_point_nonzero_ids CHECK (
            validation_result_id <> {_ZERO} AND created_by <> {_ZERO}),
          CONSTRAINT ck_validation_result_comparison_point_classification CHECK (
            classification ~ '^[a-z][a-z0-9_.-]{{0,63}}$'),
          CONSTRAINT ck_validation_result_comparison_point_values CHECK (
            ordinal >= 0
            AND engineering_strain >= 0 AND engineering_strain < 'Infinity'::float8
            AND observed_engineering_stress_pa >= 0
            AND observed_engineering_stress_pa < 'Infinity'::float8
            AND simulated_engineering_stress_pa >= 0
            AND simulated_engineering_stress_pa < 'Infinity'::float8
            AND residual_engineering_stress_pa > '-Infinity'::float8
            AND residual_engineering_stress_pa < 'Infinity'::float8),
          CONSTRAINT fk_validation_result_comparison_point_result FOREIGN KEY
            (organization_id, project_id, classification, validation_result_id)
            REFERENCES validation.validation_result (organization_id, project_id, classification, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED
        )
        """
    )


def _create_guards() -> None:
    op.execute(
        f"""
        CREATE FUNCTION validation.guard_validation_response_extraction_insert()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
          run validation.validation_run%ROWTYPE;
          manifest validation.validation_run_result_manifest%ROWTYPE;
          artifact_kind text;
          artifact_role text;
          artifact_schema text;
          artifact_digest text;
        BEGIN
          SELECT * INTO run FROM validation.validation_run
          WHERE organization_id = NEW.organization_id AND project_id = NEW.project_id
            AND classification = NEW.classification AND id = NEW.validation_run_id;
          SELECT * INTO manifest FROM validation.validation_run_result_manifest
          WHERE organization_id = NEW.organization_id AND project_id = NEW.project_id
            AND classification = NEW.classification AND id = NEW.validation_result_manifest_id;
          IF NOT FOUND OR run.result_manifest_id IS DISTINCT FROM NEW.validation_result_manifest_id
             OR manifest.validation_run_id IS DISTINCT FROM NEW.validation_run_id
             OR NEW.source_native_result_artifact_id IS DISTINCT FROM manifest.native_result_artifact_id
             OR NEW.source_native_result_sha256 IS DISTINCT FROM manifest.native_result_sha256 THEN
            RAISE EXCEPTION USING ERRCODE = '23514',
              MESSAGE = 'Validation Response Extraction must reproduce its terminal Result Manifest native input';
          END IF;
          IF NEW.extraction_status = 'extracted' THEN
            SELECT artifact_kind, artifact_role, schema_ref, sha256
              INTO artifact_kind, artifact_role, artifact_schema, artifact_digest
            FROM artifact.artifact
            WHERE organization_id = NEW.organization_id AND project_id = NEW.project_id
              AND classification = NEW.classification AND id = NEW.normalized_response_artifact_id;
            IF artifact_kind IS DISTINCT FROM 'derived'
               OR artifact_role IS DISTINCT FROM 'validation.normalized_response'
               OR artifact_schema IS DISTINCT FROM '{_NORMALIZED_RESPONSE_SCHEMA}'
               OR artifact_digest IS DISTINCT FROM NEW.normalized_response_sha256 THEN
              RAISE EXCEPTION USING ERRCODE = '23514',
                MESSAGE = 'Validation Response Extraction normalized response Artifact is invalid';
            END IF;
          END IF;
          RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        f"""
        CREATE FUNCTION validation.guard_validation_numerical_health_report_insert()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
          extraction validation.validation_response_extraction%ROWTYPE;
          manifest validation.validation_run_result_manifest%ROWTYPE;
          artifact_kind text;
          artifact_role text;
          artifact_schema text;
          artifact_digest text;
        BEGIN
          SELECT * INTO extraction FROM validation.validation_response_extraction
          WHERE organization_id = NEW.organization_id AND project_id = NEW.project_id
            AND classification = NEW.classification AND id = NEW.response_extraction_id;
          SELECT * INTO manifest FROM validation.validation_run_result_manifest
          WHERE organization_id = NEW.organization_id AND project_id = NEW.project_id
            AND classification = NEW.classification AND id = NEW.validation_result_manifest_id;
          IF NOT FOUND OR extraction.validation_run_id IS DISTINCT FROM NEW.validation_run_id
             OR extraction.validation_result_manifest_id IS DISTINCT FROM NEW.validation_result_manifest_id
             OR manifest.validation_run_id IS DISTINCT FROM NEW.validation_run_id
             OR manifest.solver_termination IS DISTINCT FROM NEW.solver_termination
             OR manifest.native_result_state IS DISTINCT FROM NEW.native_result_state THEN
            RAISE EXCEPTION USING ERRCODE = '23514',
              MESSAGE = 'Numerical Health Report must reproduce its Run, Manifest, and Extraction inputs';
          END IF;
          IF NEW.health_status = 'healthy'
             AND (NEW.solver_termination <> 'normal' OR extraction.extraction_status <> 'extracted') THEN
            RAISE EXCEPTION USING ERRCODE = '23514',
              MESSAGE = 'Only a normal extracted response can be numerically healthy';
          END IF;
          SELECT artifact_kind, artifact_role, schema_ref, sha256
            INTO artifact_kind, artifact_role, artifact_schema, artifact_digest
          FROM artifact.artifact
          WHERE organization_id = NEW.organization_id AND project_id = NEW.project_id
            AND classification = NEW.classification AND id = NEW.report_artifact_id;
          IF artifact_kind IS DISTINCT FROM 'derived'
             OR artifact_role IS DISTINCT FROM 'validation.numerical_health_report'
             OR artifact_schema IS DISTINCT FROM '{_HEALTH_REPORT_SCHEMA}'
             OR artifact_digest IS DISTINCT FROM NEW.report_sha256 THEN
            RAISE EXCEPTION USING ERRCODE = '23514',
              MESSAGE = 'Numerical Health Report Artifact is invalid';
          END IF;
          RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        f"""
        CREATE FUNCTION validation.guard_validation_result_insert()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
          run validation.validation_run%ROWTYPE;
          manifest validation.validation_run_result_manifest%ROWTYPE;
          extraction validation.validation_response_extraction%ROWTYPE;
          health validation.validation_numerical_health_report%ROWTYPE;
          artifact_kind text;
          artifact_role text;
          artifact_schema text;
          artifact_digest text;
        BEGIN
          SELECT * INTO run FROM validation.validation_run
          WHERE organization_id = NEW.organization_id AND project_id = NEW.project_id
            AND classification = NEW.classification AND id = NEW.validation_run_id;
          SELECT * INTO manifest FROM validation.validation_run_result_manifest
          WHERE organization_id = NEW.organization_id AND project_id = NEW.project_id
            AND classification = NEW.classification AND id = NEW.validation_result_manifest_id;
          SELECT * INTO extraction FROM validation.validation_response_extraction
          WHERE organization_id = NEW.organization_id AND project_id = NEW.project_id
            AND classification = NEW.classification AND id = NEW.response_extraction_id;
          SELECT * INTO health FROM validation.validation_numerical_health_report
          WHERE organization_id = NEW.organization_id AND project_id = NEW.project_id
            AND classification = NEW.classification AND id = NEW.numerical_health_report_id;
          IF NOT FOUND OR run.result_manifest_id IS DISTINCT FROM NEW.validation_result_manifest_id
             OR manifest.validation_run_id IS DISTINCT FROM NEW.validation_run_id
             OR extraction.validation_run_id IS DISTINCT FROM NEW.validation_run_id
             OR extraction.validation_result_manifest_id IS DISTINCT FROM NEW.validation_result_manifest_id
             OR health.validation_run_id IS DISTINCT FROM NEW.validation_run_id
             OR health.validation_result_manifest_id IS DISTINCT FROM NEW.validation_result_manifest_id
             OR health.response_extraction_id IS DISTINCT FROM NEW.response_extraction_id
             OR run.experimental_selection_id IS DISTINCT FROM NEW.experimental_selection_id
             OR run.experimental_selection_revision_id IS DISTINCT FROM NEW.experimental_selection_revision_id
             OR NEW.normalized_response_artifact_id IS DISTINCT FROM extraction.normalized_response_artifact_id
             OR NEW.normalized_response_sha256 IS DISTINCT FROM extraction.normalized_response_sha256
             OR NEW.numerical_health_report_artifact_id IS DISTINCT FROM health.report_artifact_id
             OR NEW.numerical_health_report_sha256 IS DISTINCT FROM health.report_sha256 THEN
            RAISE EXCEPTION USING ERRCODE = '23514',
              MESSAGE = 'Validation Result must reproduce every frozen input and typed report Artifact';
          END IF;
          IF (manifest.solver_termination <> 'normal' OR health.health_status <> 'healthy'
              OR NEW.holdout_independence = 'overlaps_calibration_selection')
             AND NEW.verdict <> 'not_evaluated' THEN
            RAISE EXCEPTION USING ERRCODE = '23514',
              MESSAGE = 'Abnormal, unhealthy, or overlapping holdout Validation Results are not_evaluated';
          END IF;
          SELECT artifact_kind, artifact_role, schema_ref, sha256
            INTO artifact_kind, artifact_role, artifact_schema, artifact_digest
          FROM artifact.artifact
          WHERE organization_id = NEW.organization_id AND project_id = NEW.project_id
            AND classification = NEW.classification AND id = NEW.result_artifact_id;
          IF artifact_kind IS DISTINCT FROM 'derived'
             OR artifact_role IS DISTINCT FROM 'validation.experimental_comparison_result'
             OR artifact_schema IS DISTINCT FROM '{_VALIDATION_RESULT_SCHEMA}'
             OR artifact_digest IS DISTINCT FROM NEW.result_sha256 THEN
            RAISE EXCEPTION USING ERRCODE = '23514',
              MESSAGE = 'Validation Result Artifact is invalid';
          END IF;
          RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION validation.guard_validation_result_comparison_points()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
          expected_count integer;
          actual_count integer;
        BEGIN
          SELECT compared_point_count INTO expected_count
          FROM validation.validation_result
          WHERE organization_id = NEW.organization_id AND project_id = NEW.project_id
            AND classification = NEW.classification AND id = NEW.id;
          SELECT count(*) INTO actual_count
          FROM validation.validation_result_comparison_point
          WHERE organization_id = NEW.organization_id AND project_id = NEW.project_id
            AND classification = NEW.classification AND validation_result_id = NEW.id;
          IF expected_count IS NULL OR actual_count <> expected_count THEN
            RAISE EXCEPTION USING ERRCODE = '23514',
              MESSAGE = 'Validation Result comparison points must match the declared metric point count';
          END IF;
          RETURN NEW;
        END;
        $$
        """
    )


def upgrade() -> None:
    _create_tables()
    for name, table, columns in (
        (
            "ix_validation_response_extraction_manifest",
            "validation_response_extraction",
            ["organization_id", "project_id", "classification", "validation_result_manifest_id"],
        ),
        (
            "ix_validation_numerical_health_status",
            "validation_numerical_health_report",
            ["organization_id", "project_id", "classification", "health_status", "created_at"],
        ),
        (
            "ix_validation_result_verdict_created",
            "validation_result",
            ["organization_id", "project_id", "classification", "verdict", "created_at"],
        ),
        (
            "ix_validation_result_selection_revision",
            "validation_result",
            ["organization_id", "project_id", "classification", "experimental_selection_revision_id"],
        ),
        (
            "ix_validation_result_comparison_point_result",
            "validation_result_comparison_point",
            ["organization_id", "project_id", "classification", "validation_result_id", "ordinal"],
        ),
    ):
        op.create_index(name, table, columns, schema="validation")
    for table in (
        "validation_response_extraction",
        "validation_numerical_health_report",
        "validation_result",
        "validation_result_comparison_point",
    ):
        op.execute(f"ALTER TABLE validation.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE validation.{table} FORCE ROW LEVEL SECURITY")
        _secure(table)
    _create_guards()
    for table in (
        "validation_response_extraction",
        "validation_numerical_health_report",
        "validation_result",
        "validation_result_comparison_point",
    ):
        op.execute(
            f"CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE ON validation.{table} "
            "FOR EACH ROW EXECUTE FUNCTION revisioning.reject_immutable_row_mutation()"
        )
    op.execute(
        "CREATE TRIGGER validation_response_extraction_input_guard "
        "BEFORE INSERT ON validation.validation_response_extraction FOR EACH ROW "
        "EXECUTE FUNCTION validation.guard_validation_response_extraction_insert()"
    )
    op.execute(
        "CREATE TRIGGER validation_numerical_health_report_input_guard "
        "BEFORE INSERT ON validation.validation_numerical_health_report FOR EACH ROW "
        "EXECUTE FUNCTION validation.guard_validation_numerical_health_report_insert()"
    )
    op.execute(
        "CREATE TRIGGER validation_result_input_guard BEFORE INSERT ON validation.validation_result "
        "FOR EACH ROW EXECUTE FUNCTION validation.guard_validation_result_insert()"
    )
    op.execute(
        "CREATE CONSTRAINT TRIGGER validation_result_comparison_point_count_guard "
        "AFTER INSERT ON validation.validation_result DEFERRABLE INITIALLY DEFERRED "
        "FOR EACH ROW EXECUTE FUNCTION validation.guard_validation_result_comparison_points()"
    )


def downgrade() -> None:
    for trigger, table in (
        ("validation_result_comparison_point_count_guard", "validation_result"),
        ("validation_result_input_guard", "validation_result"),
        ("validation_numerical_health_report_input_guard", "validation_numerical_health_report"),
        ("validation_response_extraction_input_guard", "validation_response_extraction"),
        ("validation_result_comparison_point_immutable", "validation_result_comparison_point"),
        ("validation_result_immutable", "validation_result"),
        ("validation_numerical_health_report_immutable", "validation_numerical_health_report"),
        ("validation_response_extraction_immutable", "validation_response_extraction"),
    ):
        op.execute(f"DROP TRIGGER IF EXISTS {trigger} ON validation.{table}")
    for function in (
        "validation.guard_validation_result_comparison_points()",
        "validation.guard_validation_result_insert()",
        "validation.guard_validation_numerical_health_report_insert()",
        "validation.guard_validation_response_extraction_insert()",
    ):
        op.execute(f"DROP FUNCTION IF EXISTS {function}")
    for table in (
        "validation_result_comparison_point",
        "validation_result",
        "validation_numerical_health_report",
        "validation_response_extraction",
    ):
        for operation in ("select", "insert", "update"):
            op.execute(f"DROP POLICY IF EXISTS validation_{table}_{operation} ON validation.{table}")
        op.drop_table(table, schema="validation")

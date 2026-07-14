"""Add typed non-production reference Calibration Plan/Run/Attempt/Candidate orchestration.

Revision ID: 20260719_021_t23
Revises: 20260718_020_t11
"""

# ruff: noqa: E501

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260719_021_t23"
down_revision: str | None = "20260718_020_t11"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ZERO = "'00000000-0000-0000-0000-000000000000'::uuid"
_PLAN_KIND = "reference_uniaxial_linear_elasticity"
_PLAN_SCHEMA = "urn:cmp:modeling:reference-uniaxial-linear-elastic-calibration:1.0.0"
_FAMILY = "urn:cmp:reference:isotropic-linear-elasticity:1.0.0"
_TEST_MODE = "reference_uniaxial_tension"
_EVALUATOR = "urn:cmp:reference:linear-elastic-closed-form-curve-evaluator:1.0.0"
_CALIBRATOR = "urn:cmp:reference:analytic-bounded-weighted-least-squares:1.0.0"
_DIAGNOSTICS_SCHEMA = (
    "urn:cmp:modeling:reference-linear-elastic-calibration-diagnostics-parquet:1.0.0"
)


def _secure(table: str) -> None:
    for operation, predicate, permission in (
        ("select", "USING", "modeling.read"),
        ("insert", "WITH CHECK", "calibration.execute"),
    ):
        op.execute(
            f"CREATE POLICY modeling_{table}_{operation} ON modeling.{table} "
            f"FOR {operation.upper()} {predicate} (access_control.can_access_row("
            f"organization_id, project_id, classification, '{permission}'))"
        )
    op.execute(
        f"CREATE POLICY modeling_{table}_update ON modeling.{table} FOR UPDATE "
        "USING (access_control.can_access_row(organization_id, project_id, classification, "
        "'calibration.execute')) WITH CHECK (access_control.can_access_row("
        "organization_id, project_id, classification, 'calibration.execute'))"
    )


def _create_plan_tables() -> None:
    op.execute(
        f"""
        CREATE TABLE modeling.calibration_plan (
          id uuid NOT NULL,
          organization_id uuid NOT NULL,
          project_id uuid NOT NULL,
          classification varchar(64) NOT NULL,
          current_revision_id uuid NOT NULL,
          created_at timestamptz NOT NULL,
          created_by uuid NOT NULL,
          updated_at timestamptz NOT NULL,
          plan_label varchar(160) NOT NULL,
          plan_kind varchar(100) NOT NULL,
          CONSTRAINT pk_modeling_calibration_plan PRIMARY KEY (organization_id, project_id, id),
          CONSTRAINT uq_modeling_calibration_plan_scope_identity
            UNIQUE (organization_id, project_id, classification, id),
          CONSTRAINT uq_modeling_calibration_plan_label
            UNIQUE (organization_id, project_id, classification, plan_label),
          CONSTRAINT uq_modeling_calibration_plan_identity_fixed_kind
            UNIQUE (organization_id, project_id, classification, id, plan_kind),
          CONSTRAINT ck_modeling_calibration_plan_nonzero_ids CHECK (
            id <> {_ZERO} AND current_revision_id <> {_ZERO} AND created_by <> {_ZERO}),
          CONSTRAINT ck_modeling_calibration_plan_classification CHECK (
            classification ~ '^[a-z][a-z0-9_.-]{{0,63}}$'),
          CONSTRAINT ck_modeling_calibration_plan_label CHECK (
            length(btrim(plan_label)) BETWEEN 1 AND 160 AND plan_label = btrim(plan_label)),
          CONSTRAINT ck_modeling_calibration_plan_kind CHECK (plan_kind = '{_PLAN_KIND}')
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE modeling.calibration_plan_revision (
          id uuid NOT NULL,
          aggregate_id uuid NOT NULL,
          organization_id uuid NOT NULL,
          project_id uuid NOT NULL,
          classification varchar(64) NOT NULL,
          revision_no bigint NOT NULL,
          based_on_revision_id uuid NULL,
          schema_id varchar(255) NOT NULL,
          schema_version varchar(64) NOT NULL,
          content_hash char(64) COLLATE "C" NOT NULL,
          created_at timestamptz NOT NULL,
          created_by uuid NOT NULL,
          change_reason text NOT NULL,
          request_id uuid NOT NULL,
          trace_id varchar(255) NOT NULL,
          plan_kind varchar(100) NOT NULL,
          selection_id uuid NOT NULL,
          selection_revision_id uuid NOT NULL,
          material_model_id uuid NOT NULL,
          material_model_revision_id uuid NOT NULL,
          model_family_id varchar(255) NOT NULL,
          model_schema_version varchar(64) NOT NULL,
          model_schema_digest char(64) COLLATE "C" NOT NULL,
          test_mode varchar(100) NOT NULL,
          evaluator_id varchar(255) NOT NULL,
          evaluator_version varchar(64) NOT NULL,
          evaluation_mode varchar(64) NOT NULL,
          calibrator_id varchar(255) NOT NULL,
          calibrator_version varchar(64) NOT NULL,
          parameter_name varchar(100) NOT NULL,
          youngs_modulus_lower_bound_pa double precision NOT NULL,
          youngs_modulus_initial_value_pa double precision NOT NULL,
          youngs_modulus_upper_bound_pa double precision NOT NULL,
          normalization_stress_scale_pa double precision NOT NULL,
          point_weighting varchar(100) NOT NULL,
          objective_aggregation varchar(100) NOT NULL,
          x_domain_policy varchar(100) NOT NULL,
          missing_data_policy varchar(100) NOT NULL,
          multistart_count smallint NOT NULL,
          random_seed bigint NOT NULL,
          non_production boolean NOT NULL,
          CONSTRAINT pk_modeling_calibration_plan_revision
            PRIMARY KEY (organization_id, project_id, id),
          CONSTRAINT uq_modeling_calibration_plan_revision_scope_id
            UNIQUE (organization_id, project_id, aggregate_id, id),
          CONSTRAINT uq_modeling_calibration_plan_revision_scoped_ref
            UNIQUE (organization_id, project_id, classification, aggregate_id, id),
          CONSTRAINT uq_modeling_calibration_plan_revision_number
            UNIQUE (organization_id, project_id, aggregate_id, revision_no),
          CONSTRAINT uq_modeling_calibration_plan_revision_classified_id
            UNIQUE (organization_id, project_id, classification, id),
          CONSTRAINT ck_modeling_calibration_plan_revision_nonzero_ids CHECK (
            id <> {_ZERO} AND aggregate_id <> {_ZERO} AND created_by <> {_ZERO}
            AND request_id <> {_ZERO} AND selection_id <> {_ZERO}
            AND selection_revision_id <> {_ZERO} AND material_model_id <> {_ZERO}
            AND material_model_revision_id <> {_ZERO}),
          CONSTRAINT ck_modeling_calibration_plan_revision_number CHECK (revision_no > 0),
          CONSTRAINT ck_modeling_calibration_plan_revision_base CHECK (
            (revision_no = 1 AND based_on_revision_id IS NULL)
            OR (revision_no > 1 AND based_on_revision_id IS NOT NULL)),
          CONSTRAINT ck_modeling_calibration_plan_revision_hashes CHECK (
            content_hash ~ '^[0-9a-f]{{64}}$' AND model_schema_digest ~ '^[0-9a-f]{{64}}$'),
          CONSTRAINT ck_modeling_calibration_plan_revision_schema CHECK (
            schema_id = '{_PLAN_SCHEMA}' AND schema_version = '1.0.0'),
          CONSTRAINT ck_modeling_calibration_plan_revision_text CHECK (
            length(btrim(change_reason)) BETWEEN 1 AND 2000
            AND length(btrim(trace_id)) BETWEEN 1 AND 255
            AND classification ~ '^[a-z][a-z0-9_.-]{{0,63}}$'),
          CONSTRAINT ck_modeling_calibration_plan_revision_reference_contract CHECK (
            plan_kind = '{_PLAN_KIND}'
            AND model_family_id = '{_FAMILY}' AND model_schema_version = '1.0.0'
            AND test_mode = '{_TEST_MODE}'
            AND evaluator_id = '{_EVALUATOR}' AND evaluator_version = '1.0.0'
            AND evaluation_mode = 'closed_form_curve'
            AND calibrator_id = '{_CALIBRATOR}' AND calibrator_version = '1.0.0'
            AND parameter_name = 'youngs_modulus_pa'
            AND point_weighting = 'uniform_point_weight'
            AND objective_aggregation = 'mean_normalized_squared_residual'
            AND x_domain_policy = 'all_observed_points'
            AND missing_data_policy = 'reject' AND non_production),
          CONSTRAINT ck_modeling_calibration_plan_revision_bounds CHECK (
            youngs_modulus_lower_bound_pa > 0
            AND youngs_modulus_lower_bound_pa < 'Infinity'::float8
            AND youngs_modulus_initial_value_pa >= youngs_modulus_lower_bound_pa
            AND youngs_modulus_initial_value_pa <= youngs_modulus_upper_bound_pa
            AND youngs_modulus_upper_bound_pa > youngs_modulus_lower_bound_pa
            AND youngs_modulus_upper_bound_pa < 'Infinity'::float8
            AND normalization_stress_scale_pa > 0
            AND normalization_stress_scale_pa < 'Infinity'::float8
            AND multistart_count BETWEEN 1 AND 16),
          CONSTRAINT fk_modeling_calibration_plan_revision_identity FOREIGN KEY
            (organization_id, project_id, aggregate_id)
            REFERENCES modeling.calibration_plan (organization_id, project_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_modeling_calibration_plan_revision_identity_kind FOREIGN KEY
            (organization_id, project_id, classification, aggregate_id, plan_kind)
            REFERENCES modeling.calibration_plan
              (organization_id, project_id, classification, id, plan_kind)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_modeling_calibration_plan_revision_selection FOREIGN KEY
            (organization_id, project_id, classification, selection_id, selection_revision_id)
            REFERENCES datasets.dataset_selection_revision
              (organization_id, project_id, classification, aggregate_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_modeling_calibration_plan_revision_model FOREIGN KEY
            (organization_id, project_id, classification, material_model_id,
             material_model_revision_id)
            REFERENCES modeling.material_model_revision
              (organization_id, project_id, classification, aggregate_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_modeling_calibration_plan_revision_base FOREIGN KEY
            (organization_id, project_id, aggregate_id, based_on_revision_id)
            REFERENCES modeling.calibration_plan_revision
              (organization_id, project_id, aggregate_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED
        )
        """
    )
    op.execute(
        """
        ALTER TABLE modeling.calibration_plan
          ADD CONSTRAINT fk_modeling_calibration_plan_current_revision
          FOREIGN KEY (organization_id, project_id, id, current_revision_id)
          REFERENCES modeling.calibration_plan_revision
            (organization_id, project_id, aggregate_id, id)
          ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED
        """
    )


def _create_execution_tables() -> None:
    op.execute(
        f"""
        CREATE TABLE modeling.calibration_run (
          id uuid NOT NULL,
          organization_id uuid NOT NULL,
          project_id uuid NOT NULL,
          classification varchar(64) NOT NULL,
          plan_id uuid NOT NULL,
          plan_revision_id uuid NOT NULL,
          selection_id uuid NOT NULL,
          selection_revision_id uuid NOT NULL,
          dataset_id uuid NOT NULL,
          dataset_revision_id uuid NOT NULL,
          material_model_id uuid NOT NULL,
          material_model_revision_id uuid NOT NULL,
          execution_mode varchar(32) NOT NULL,
          reproducibility_level varchar(16) NOT NULL,
          environment_digest char(64) COLLATE "C" NOT NULL,
          status varchar(16) NOT NULL,
          attempt_count smallint NOT NULL,
          candidate_count smallint NOT NULL,
          failure_code varchar(100) NULL,
          change_reason text NOT NULL,
          started_at timestamptz NOT NULL,
          ended_at timestamptz NULL,
          created_by uuid NOT NULL,
          request_id uuid NOT NULL,
          trace_id varchar(255) NOT NULL,
          CONSTRAINT pk_modeling_calibration_run PRIMARY KEY (organization_id, project_id, id),
          CONSTRAINT uq_modeling_calibration_run_scope_identity
            UNIQUE (organization_id, project_id, classification, id),
          CONSTRAINT uq_modeling_calibration_run_plan_revision
            UNIQUE (organization_id, project_id, classification, id, plan_id, plan_revision_id),
          CONSTRAINT ck_modeling_calibration_run_nonzero_ids CHECK (
            id <> {_ZERO} AND plan_id <> {_ZERO} AND plan_revision_id <> {_ZERO}
            AND selection_id <> {_ZERO} AND selection_revision_id <> {_ZERO}
            AND dataset_id <> {_ZERO} AND dataset_revision_id <> {_ZERO}
            AND material_model_id <> {_ZERO} AND material_model_revision_id <> {_ZERO}
            AND created_by <> {_ZERO} AND request_id <> {_ZERO}),
          CONSTRAINT ck_modeling_calibration_run_text CHECK (
            classification ~ '^[a-z][a-z0-9_.-]{{0,63}}$'
            AND environment_digest ~ '^[0-9a-f]{{64}}$'
            AND length(btrim(change_reason)) BETWEEN 1 AND 2000
            AND length(btrim(trace_id)) BETWEEN 1 AND 255),
          CONSTRAINT ck_modeling_calibration_run_contract CHECK (
            execution_mode = 'reference_inline' AND reproducibility_level = 'R3'
            AND status IN ('executing', 'succeeded', 'failed')
            AND attempt_count BETWEEN 1 AND 16 AND candidate_count BETWEEN 0 AND attempt_count),
          CONSTRAINT ck_modeling_calibration_run_terminal_shape CHECK (
            (status = 'executing' AND ended_at IS NULL AND candidate_count = 0
             AND failure_code IS NULL)
            OR (status = 'succeeded' AND ended_at IS NOT NULL
                AND candidate_count = attempt_count AND failure_code IS NULL)
            OR (status = 'failed' AND ended_at IS NOT NULL
                AND failure_code ~ '^[a-z][a-z0-9_]{0,99}$')),
          CONSTRAINT fk_modeling_calibration_run_plan FOREIGN KEY
            (organization_id, project_id, classification, plan_id, plan_revision_id)
            REFERENCES modeling.calibration_plan_revision
              (organization_id, project_id, classification, aggregate_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_modeling_calibration_run_selection FOREIGN KEY
            (organization_id, project_id, classification, selection_id, selection_revision_id)
            REFERENCES datasets.dataset_selection_revision
              (organization_id, project_id, classification, aggregate_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_modeling_calibration_run_dataset FOREIGN KEY
            (organization_id, project_id, classification, dataset_id, dataset_revision_id)
            REFERENCES datasets.dataset_revision
              (organization_id, project_id, classification, aggregate_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_modeling_calibration_run_model FOREIGN KEY
            (organization_id, project_id, classification, material_model_id,
             material_model_revision_id)
            REFERENCES modeling.material_model_revision
              (organization_id, project_id, classification, aggregate_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE modeling.calibration_attempt (
          id uuid NOT NULL,
          organization_id uuid NOT NULL,
          project_id uuid NOT NULL,
          classification varchar(64) NOT NULL,
          calibration_run_id uuid NOT NULL,
          attempt_ordinal smallint NOT NULL,
          initial_youngs_modulus_pa double precision NOT NULL,
          random_seed bigint NOT NULL,
          status varchar(16) NOT NULL,
          candidate_id uuid NULL,
          failure_code varchar(100) NULL,
          started_at timestamptz NOT NULL,
          ended_at timestamptz NULL,
          CONSTRAINT pk_modeling_calibration_attempt
            PRIMARY KEY (organization_id, project_id, id),
          CONSTRAINT uq_modeling_calibration_attempt_scope_identity
            UNIQUE (organization_id, project_id, classification, id),
          CONSTRAINT uq_modeling_calibration_attempt_run_ordinal
            UNIQUE (organization_id, project_id, classification, calibration_run_id, attempt_ordinal),
          CONSTRAINT uq_modeling_calibration_attempt_candidate_reference
            UNIQUE (organization_id, project_id, classification, id, calibration_run_id,
                    attempt_ordinal),
          CONSTRAINT ck_modeling_calibration_attempt_nonzero_ids CHECK (
            id <> {_ZERO} AND calibration_run_id <> {_ZERO}
            AND (candidate_id IS NULL OR candidate_id <> {_ZERO})),
          CONSTRAINT ck_modeling_calibration_attempt_classification CHECK (
            classification ~ '^[a-z][a-z0-9_.-]{{0,63}}$'),
          CONSTRAINT ck_modeling_calibration_attempt_initial CHECK (
            initial_youngs_modulus_pa > 0
            AND initial_youngs_modulus_pa < 'Infinity'::float8),
          CONSTRAINT ck_modeling_calibration_attempt_status CHECK (
            status IN ('executing', 'succeeded', 'failed')),
          CONSTRAINT ck_modeling_calibration_attempt_terminal_shape CHECK (
            (status = 'executing' AND candidate_id IS NULL AND failure_code IS NULL
             AND ended_at IS NULL)
            OR (status = 'succeeded' AND candidate_id IS NOT NULL AND failure_code IS NULL
                AND ended_at IS NOT NULL)
            OR (status = 'failed' AND candidate_id IS NULL
                AND failure_code ~ '^[a-z][a-z0-9_]{0,99}$' AND ended_at IS NOT NULL)),
          CONSTRAINT fk_modeling_calibration_attempt_run FOREIGN KEY
            (organization_id, project_id, classification, calibration_run_id)
            REFERENCES modeling.calibration_run
              (organization_id, project_id, classification, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE modeling.calibration_candidate (
          id uuid NOT NULL,
          organization_id uuid NOT NULL,
          project_id uuid NOT NULL,
          classification varchar(64) NOT NULL,
          calibration_run_id uuid NOT NULL,
          calibration_attempt_id uuid NOT NULL,
          attempt_ordinal smallint NOT NULL,
          status varchar(16) NOT NULL,
          candidate_sha256 char(64) COLLATE "C" NOT NULL,
          youngs_modulus_pa double precision NOT NULL,
          objective_total double precision NOT NULL,
          residual_root_mean_square_pa double precision NOT NULL,
          residual_mean_pa double precision NOT NULL,
          bound_sticking boolean NOT NULL,
          convergence_reason varchar(255) NOT NULL,
          identifiability_status varchar(100) NOT NULL,
          uncertainty_status varchar(100) NOT NULL,
          diagnostics_artifact_id uuid NOT NULL,
          diagnostics_sha256 char(64) COLLATE "C" NOT NULL,
          diagnostics_point_count bigint NOT NULL,
          created_at timestamptz NOT NULL,
          created_by uuid NOT NULL,
          CONSTRAINT pk_modeling_calibration_candidate
            PRIMARY KEY (organization_id, project_id, id),
          CONSTRAINT uq_modeling_calibration_candidate_scope_identity
            UNIQUE (organization_id, project_id, classification, id),
          CONSTRAINT uq_modeling_calibration_candidate_attempt
            UNIQUE (organization_id, project_id, classification, calibration_attempt_id),
          CONSTRAINT uq_modeling_calibration_candidate_run_ordinal
            UNIQUE (organization_id, project_id, classification, calibration_run_id, attempt_ordinal),
          CONSTRAINT uq_modeling_calibration_candidate_attempt_reference
            UNIQUE (organization_id, project_id, classification, id, calibration_run_id,
                    calibration_attempt_id, attempt_ordinal),
          CONSTRAINT ck_modeling_calibration_candidate_nonzero_ids CHECK (
            id <> {_ZERO} AND calibration_run_id <> {_ZERO}
            AND calibration_attempt_id <> {_ZERO} AND diagnostics_artifact_id <> {_ZERO}
            AND created_by <> {_ZERO}),
          CONSTRAINT ck_modeling_calibration_candidate_classification CHECK (
            classification ~ '^[a-z][a-z0-9_.-]{{0,63}}$'),
          CONSTRAINT ck_modeling_calibration_candidate_status CHECK (
            status IN ('converged', 'nonconverged', 'failed')),
          CONSTRAINT ck_modeling_calibration_candidate_hashes CHECK (
            candidate_sha256 ~ '^[0-9a-f]{{64}}$'
            AND diagnostics_sha256 ~ '^[0-9a-f]{{64}}$'),
          CONSTRAINT ck_modeling_calibration_candidate_numerics CHECK (
            youngs_modulus_pa > 0 AND youngs_modulus_pa < 'Infinity'::float8
            AND objective_total >= 0 AND objective_total < 'Infinity'::float8
            AND residual_root_mean_square_pa >= 0
            AND residual_root_mean_square_pa < 'Infinity'::float8
            AND residual_mean_pa > '-Infinity'::float8
            AND residual_mean_pa < 'Infinity'::float8
            AND diagnostics_point_count >= 2),
          CONSTRAINT ck_modeling_calibration_candidate_text CHECK (
            length(btrim(convergence_reason)) BETWEEN 1 AND 255
            AND length(btrim(identifiability_status)) BETWEEN 1 AND 100
            AND length(btrim(uncertainty_status)) BETWEEN 1 AND 100),
          CONSTRAINT fk_modeling_calibration_candidate_run FOREIGN KEY
            (organization_id, project_id, classification, calibration_run_id)
            REFERENCES modeling.calibration_run
              (organization_id, project_id, classification, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_modeling_calibration_candidate_attempt FOREIGN KEY
            (organization_id, project_id, classification, calibration_attempt_id,
             calibration_run_id, attempt_ordinal)
            REFERENCES modeling.calibration_attempt
              (organization_id, project_id, classification, id, calibration_run_id,
               attempt_ordinal)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_modeling_calibration_candidate_artifact FOREIGN KEY
            (organization_id, project_id, classification, diagnostics_artifact_id)
            REFERENCES artifact.artifact (organization_id, project_id, classification, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED
        )
        """
    )
    op.execute(
        """
        ALTER TABLE modeling.calibration_attempt
          ADD CONSTRAINT fk_modeling_calibration_attempt_candidate
          FOREIGN KEY (organization_id, project_id, classification, candidate_id,
                       calibration_run_id, id, attempt_ordinal)
          REFERENCES modeling.calibration_candidate
            (organization_id, project_id, classification, id, calibration_run_id,
             calibration_attempt_id, attempt_ordinal)
          ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED
        """
    )


def _create_guards() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION datasets.guard_reference_dataset_selection_revision_insert()
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
          IF selected_representation NOT IN ('normalized', 'processed') THEN
            RAISE EXCEPTION USING ERRCODE = '23514',
              MESSAGE = 'reference Dataset Selection requires a normalized or processed Dataset revision';
          END IF;
          RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION modeling.guard_calibration_run_insert()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
          plan modeling.calibration_plan_revision%ROWTYPE;
          selected_dataset_id uuid;
          selected_dataset_revision_id uuid;
          selected_representation text;
          model_state_id uuid;
          dataset_state_id uuid;
        BEGIN
          SELECT * INTO plan
          FROM modeling.calibration_plan_revision
          WHERE organization_id = NEW.organization_id AND project_id = NEW.project_id
            AND classification = NEW.classification AND aggregate_id = NEW.plan_id
            AND id = NEW.plan_revision_id;
          IF NOT FOUND
             OR plan.selection_id <> NEW.selection_id
             OR plan.selection_revision_id <> NEW.selection_revision_id
             OR plan.material_model_id <> NEW.material_model_id
             OR plan.material_model_revision_id <> NEW.material_model_revision_id THEN
            RAISE EXCEPTION USING ERRCODE = '23514',
              MESSAGE = 'Calibration Run must reproduce the pinned Plan revision inputs';
          END IF;
          SELECT dataset_id, dataset_revision_id INTO selected_dataset_id, selected_dataset_revision_id
          FROM datasets.dataset_selection_revision
          WHERE organization_id = NEW.organization_id AND project_id = NEW.project_id
            AND classification = NEW.classification AND aggregate_id = NEW.selection_id
            AND id = NEW.selection_revision_id;
          IF NOT FOUND OR selected_dataset_id <> NEW.dataset_id
             OR selected_dataset_revision_id <> NEW.dataset_revision_id THEN
            RAISE EXCEPTION USING ERRCODE = '23514',
              MESSAGE = 'Calibration Run Dataset must reproduce the pinned Selection revision';
          END IF;
          SELECT representation INTO selected_representation
          FROM datasets.dataset_revision
          WHERE organization_id = NEW.organization_id AND project_id = NEW.project_id
            AND classification = NEW.classification AND aggregate_id = NEW.dataset_id
            AND id = NEW.dataset_revision_id;
          IF selected_representation NOT IN ('normalized', 'processed') THEN
            RAISE EXCEPTION USING ERRCODE = '23514',
              MESSAGE = 'Calibration Run requires a normalized or processed Dataset revision';
          END IF;
          SELECT material_state_id INTO model_state_id
          FROM modeling.material_model_revision
          WHERE organization_id = NEW.organization_id AND project_id = NEW.project_id
            AND classification = NEW.classification AND aggregate_id = NEW.material_model_id
            AND id = NEW.material_model_revision_id;
          SELECT specimen.material_state_id INTO dataset_state_id
          FROM datasets.dataset_revision dataset
          JOIN testing.test_run run
            ON run.organization_id = dataset.organization_id
            AND run.project_id = dataset.project_id
            AND run.classification = dataset.classification
            AND run.id = dataset.test_run_id
          JOIN testing.specimen specimen
            ON specimen.organization_id = run.organization_id
            AND specimen.project_id = run.project_id
            AND specimen.classification = run.classification
            AND specimen.id = run.specimen_id
          WHERE dataset.organization_id = NEW.organization_id
            AND dataset.project_id = NEW.project_id
            AND dataset.classification = NEW.classification
            AND dataset.aggregate_id = NEW.dataset_id AND dataset.id = NEW.dataset_revision_id;
          IF model_state_id IS NULL OR dataset_state_id IS NULL OR model_state_id <> dataset_state_id THEN
            RAISE EXCEPTION USING ERRCODE = '23514',
              MESSAGE = 'Calibration Run Material Model and Dataset specimen must share Material State';
          END IF;
          RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION modeling.guard_calibration_run_transition()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
          IF OLD.status <> 'executing' OR NEW.status NOT IN ('succeeded', 'failed')
             OR NEW.organization_id <> OLD.organization_id OR NEW.project_id <> OLD.project_id
             OR NEW.classification <> OLD.classification OR NEW.plan_id <> OLD.plan_id
             OR NEW.plan_revision_id <> OLD.plan_revision_id OR NEW.selection_id <> OLD.selection_id
             OR NEW.selection_revision_id <> OLD.selection_revision_id
             OR NEW.dataset_id <> OLD.dataset_id OR NEW.dataset_revision_id <> OLD.dataset_revision_id
             OR NEW.material_model_id <> OLD.material_model_id
             OR NEW.material_model_revision_id <> OLD.material_model_revision_id
             OR NEW.execution_mode <> OLD.execution_mode
             OR NEW.reproducibility_level <> OLD.reproducibility_level
             OR NEW.environment_digest <> OLD.environment_digest
             OR NEW.attempt_count <> OLD.attempt_count OR NEW.change_reason <> OLD.change_reason
             OR NEW.started_at <> OLD.started_at OR NEW.created_by <> OLD.created_by
             OR NEW.request_id <> OLD.request_id OR NEW.trace_id <> OLD.trace_id THEN
            RAISE EXCEPTION USING ERRCODE = '55000',
              MESSAGE = 'Calibration Run allows only one terminal status projection';
          END IF;
          RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION modeling.guard_calibration_attempt_transition()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
          IF OLD.status <> 'executing' OR NEW.status NOT IN ('succeeded', 'failed')
             OR NEW.organization_id <> OLD.organization_id OR NEW.project_id <> OLD.project_id
             OR NEW.classification <> OLD.classification
             OR NEW.calibration_run_id <> OLD.calibration_run_id
             OR NEW.attempt_ordinal <> OLD.attempt_ordinal
             OR NEW.initial_youngs_modulus_pa <> OLD.initial_youngs_modulus_pa
             OR NEW.random_seed <> OLD.random_seed OR NEW.started_at <> OLD.started_at THEN
            RAISE EXCEPTION USING ERRCODE = '55000',
              MESSAGE = 'Calibration Attempt allows only one terminal status projection';
          END IF;
          RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION modeling.guard_calibration_candidate_insert()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
          artifact_kind text;
          artifact_role text;
          artifact_schema text;
          artifact_digest text;
          run_status text;
        BEGIN
          SELECT status INTO run_status FROM modeling.calibration_run
          WHERE organization_id = NEW.organization_id AND project_id = NEW.project_id
            AND classification = NEW.classification AND id = NEW.calibration_run_id;
          IF run_status IS DISTINCT FROM 'executing' THEN
            RAISE EXCEPTION USING ERRCODE = '23514',
              MESSAGE = 'Calibration Candidate can be appended only while its Run is executing';
          END IF;
          SELECT artifact_kind, artifact_role, schema_ref, sha256
            INTO artifact_kind, artifact_role, artifact_schema, artifact_digest
          FROM artifact.artifact
          WHERE organization_id = NEW.organization_id AND project_id = NEW.project_id
            AND classification = NEW.classification AND id = NEW.diagnostics_artifact_id;
          IF artifact_kind IS DISTINCT FROM 'derived'
             OR artifact_role IS DISTINCT FROM 'modeling.reference_linear_elastic_calibration_diagnostics'
             OR artifact_schema IS DISTINCT FROM '{_DIAGNOSTICS_SCHEMA}'
             OR artifact_digest IS DISTINCT FROM NEW.diagnostics_sha256 THEN
            RAISE EXCEPTION USING ERRCODE = '23514',
              MESSAGE = 'Calibration Candidate requires its declared verified diagnostics Artifact';
          END IF;
          RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        "CREATE TRIGGER modeling_calibration_plan_head_only "
        "BEFORE UPDATE OR DELETE ON modeling.calibration_plan FOR EACH ROW "
        "EXECUTE FUNCTION revisioning.guard_identity_head_update()"
    )
    op.execute(
        "CREATE TRIGGER modeling_calibration_plan_revision_immutable "
        "BEFORE UPDATE OR DELETE ON modeling.calibration_plan_revision FOR EACH ROW "
        "EXECUTE FUNCTION revisioning.reject_immutable_row_mutation()"
    )
    op.execute(
        "CREATE TRIGGER modeling_calibration_run_input_guard "
        "BEFORE INSERT ON modeling.calibration_run FOR EACH ROW "
        "EXECUTE FUNCTION modeling.guard_calibration_run_insert()"
    )
    op.execute(
        "CREATE TRIGGER modeling_calibration_run_transition_guard "
        "BEFORE UPDATE ON modeling.calibration_run FOR EACH ROW "
        "EXECUTE FUNCTION modeling.guard_calibration_run_transition()"
    )
    op.execute(
        "CREATE TRIGGER modeling_calibration_run_no_delete "
        "BEFORE DELETE ON modeling.calibration_run FOR EACH ROW "
        "EXECUTE FUNCTION revisioning.reject_immutable_row_mutation()"
    )
    op.execute(
        "CREATE TRIGGER modeling_calibration_attempt_transition_guard "
        "BEFORE UPDATE ON modeling.calibration_attempt FOR EACH ROW "
        "EXECUTE FUNCTION modeling.guard_calibration_attempt_transition()"
    )
    op.execute(
        "CREATE TRIGGER modeling_calibration_attempt_no_delete "
        "BEFORE DELETE ON modeling.calibration_attempt FOR EACH ROW "
        "EXECUTE FUNCTION revisioning.reject_immutable_row_mutation()"
    )
    op.execute(
        "CREATE TRIGGER modeling_calibration_candidate_input_guard "
        "BEFORE INSERT ON modeling.calibration_candidate FOR EACH ROW "
        "EXECUTE FUNCTION modeling.guard_calibration_candidate_insert()"
    )
    op.execute(
        "CREATE TRIGGER modeling_calibration_candidate_immutable "
        "BEFORE UPDATE OR DELETE ON modeling.calibration_candidate FOR EACH ROW "
        "EXECUTE FUNCTION revisioning.reject_immutable_row_mutation()"
    )


def upgrade() -> None:
    _create_plan_tables()
    _create_execution_tables()
    op.create_index(
        "ix_modeling_calibration_plan_tenant_created",
        "calibration_plan",
        ["organization_id", "project_id", "classification", "created_at"],
        schema="modeling",
    )
    op.create_index(
        "ix_modeling_calibration_plan_revision_inputs",
        "calibration_plan_revision",
        [
            "organization_id",
            "project_id",
            "classification",
            "selection_revision_id",
            "material_model_revision_id",
        ],
        schema="modeling",
    )
    op.create_index(
        "ix_modeling_calibration_run_tenant_started",
        "calibration_run",
        ["organization_id", "project_id", "classification", "started_at"],
        schema="modeling",
    )
    op.create_index(
        "ix_modeling_calibration_attempt_run_ordinal",
        "calibration_attempt",
        ["organization_id", "project_id", "classification", "calibration_run_id", "attempt_ordinal"],
        schema="modeling",
    )
    op.create_index(
        "ix_modeling_calibration_candidate_run_objective",
        "calibration_candidate",
        ["organization_id", "project_id", "classification", "calibration_run_id", "objective_total"],
        schema="modeling",
    )
    op.create_index(
        "ix_modeling_calibration_candidate_artifact",
        "calibration_candidate",
        ["organization_id", "project_id", "classification", "diagnostics_artifact_id"],
        schema="modeling",
    )
    for table in (
        "calibration_plan",
        "calibration_plan_revision",
        "calibration_run",
        "calibration_attempt",
        "calibration_candidate",
    ):
        op.execute(f"ALTER TABLE modeling.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE modeling.{table} FORCE ROW LEVEL SECURITY")
        _secure(table)
    _create_guards()


def downgrade() -> None:
    for trigger, table in (
        ("modeling_calibration_candidate_immutable", "calibration_candidate"),
        ("modeling_calibration_candidate_input_guard", "calibration_candidate"),
        ("modeling_calibration_attempt_no_delete", "calibration_attempt"),
        ("modeling_calibration_attempt_transition_guard", "calibration_attempt"),
        ("modeling_calibration_run_no_delete", "calibration_run"),
        ("modeling_calibration_run_transition_guard", "calibration_run"),
        ("modeling_calibration_run_input_guard", "calibration_run"),
        ("modeling_calibration_plan_revision_immutable", "calibration_plan_revision"),
        ("modeling_calibration_plan_head_only", "calibration_plan"),
    ):
        op.execute(f"DROP TRIGGER IF EXISTS {trigger} ON modeling.{table}")
    for function in (
        "modeling.guard_calibration_candidate_insert()",
        "modeling.guard_calibration_attempt_transition()",
        "modeling.guard_calibration_run_transition()",
        "modeling.guard_calibration_run_insert()",
    ):
        op.execute(f"DROP FUNCTION IF EXISTS {function}")
    for table in (
        "calibration_candidate",
        "calibration_attempt",
        "calibration_run",
        "calibration_plan_revision",
        "calibration_plan",
    ):
        op.drop_table(table, schema="modeling")
    op.execute(
        """
        CREATE OR REPLACE FUNCTION datasets.guard_reference_dataset_selection_revision_insert()
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

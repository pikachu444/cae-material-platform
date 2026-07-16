"""Add typed multi-test Ogden calibration Plans, Runs, Candidates, and diagnostics.

Revision ID: 20260820_054_t43_ogden
Revises: 20260819_053_t43_profiles

Traceability: T-43, FR-CAL-002/003/006/007, ADR-0025.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260820_054_t43_ogden"
down_revision: str | None = "20260819_053_t43_profiles"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_TABLES = (
    "ogden_calibration_plan",
    "ogden_calibration_plan_revision",
    "ogden_calibration_plan_member",
    "ogden_calibration_run",
    "ogden_calibration_attempt",
    "ogden_calibration_candidate",
    "ogden_calibration_candidate_warning",
)


def _rls(table: str, *, identity: bool = False) -> None:
    op.execute(f"ALTER TABLE modeling.{table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE modeling.{table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY modeling_{table}_select ON modeling.{table} FOR SELECT USING "
        "(access_control.can_access_row(organization_id, project_id, classification, "
        "'modeling.read'))"
    )
    op.execute(
        f"CREATE POLICY modeling_{table}_insert ON modeling.{table} FOR INSERT WITH CHECK "
        "(access_control.can_access_row(organization_id, project_id, classification, "
        "'calibration.execute'))"
    )
    if identity:
        op.execute(
            f"CREATE POLICY modeling_{table}_update ON modeling.{table} FOR UPDATE USING "
            "(access_control.can_access_row(organization_id, project_id, classification, "
            "'calibration.execute')) WITH CHECK "
            "(access_control.can_access_row(organization_id, project_id, classification, "
            "'calibration.execute'))"
        )


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE testing.test_method DROP CONSTRAINT ck_testing_test_method_code;
        ALTER TABLE testing.test_method_revision
          DROP CONSTRAINT ck_testing_test_method_revision_declared;
        ALTER TABLE testing.test_method ADD CONSTRAINT ck_testing_test_method_code CHECK
          (method_code IN ('reference_uniaxial_tensile','reference_planar_tension',
                           'reference_biaxial_tension','reference_shear_relaxation'));
        ALTER TABLE testing.test_method_revision ADD CONSTRAINT
          ck_testing_test_method_revision_declared CHECK
          ((method_code='reference_uniaxial_tensile' AND
            display_name='Reference uniaxial tensile CSV') OR
           (method_code='reference_planar_tension' AND
            display_name='Reference planar tension CSV') OR
           (method_code='reference_biaxial_tension' AND
            display_name='Reference biaxial tension CSV') OR
           (method_code='reference_shear_relaxation' AND
            display_name='Reference shear relaxation CSV'));
        """
    )
    op.execute(
        """
        CREATE TABLE modeling.ogden_calibration_plan (
          id uuid NOT NULL, organization_id uuid NOT NULL, project_id uuid NOT NULL,
          classification varchar(64) NOT NULL, plan_label varchar(160) NOT NULL,
          material_state_id uuid NOT NULL, baseline_model_id uuid NOT NULL,
          current_revision_id uuid NOT NULL, created_at timestamptz NOT NULL,
          created_by uuid NOT NULL, updated_at timestamptz NOT NULL,
          CONSTRAINT pk_modeling_ogden_calibration_plan PRIMARY KEY
            (organization_id, project_id, id),
          CONSTRAINT uq_modeling_ogden_calibration_plan_scope UNIQUE
            (organization_id, project_id, classification, id),
          CONSTRAINT uq_modeling_ogden_calibration_plan_label UNIQUE
            (organization_id, project_id, classification, material_state_id,
             baseline_model_id, plan_label)
        );

        CREATE TABLE modeling.ogden_calibration_plan_revision (
          id uuid NOT NULL, aggregate_id uuid NOT NULL, organization_id uuid NOT NULL,
          project_id uuid NOT NULL, classification varchar(64) NOT NULL,
          revision_no bigint NOT NULL CHECK (revision_no>0), based_on_revision_id uuid,
          schema_id varchar(255) NOT NULL,
          schema_version varchar(64) NOT NULL CHECK (schema_version='1.0.0'),
          content_hash char(64) NOT NULL CHECK (content_hash ~ '^[0-9a-f]{64}$'),
          created_at timestamptz NOT NULL, created_by uuid NOT NULL,
          change_reason text NOT NULL CHECK (length(btrim(change_reason)) BETWEEN 1 AND 2000),
          request_id uuid NOT NULL, trace_id varchar(255) NOT NULL,
          plan_label varchar(160) NOT NULL,
          scientific_profile_id uuid NOT NULL, scientific_profile_revision_id uuid NOT NULL,
          material_state_id uuid NOT NULL, material_state_revision_id uuid NOT NULL,
          baseline_model_id uuid NOT NULL, baseline_model_revision_id uuid NOT NULL,
          member_count smallint NOT NULL CHECK (member_count BETWEEN 1 AND 24),
          calibration_member_count smallint NOT NULL CHECK
            (calibration_member_count BETWEEN 1 AND 24),
          holdout_member_count smallint NOT NULL CHECK (holdout_member_count BETWEEN 0 AND 23),
          test_mode_count smallint NOT NULL CHECK (test_mode_count BETWEEN 1 AND 3),
          evaluator varchar(80) NOT NULL CHECK
            (evaluator='one_term_incompressible_ogden_nominal'),
          objective varchar(80) NOT NULL CHECK
            (objective='normalized_weighted_least_squares'),
          aggregation_order varchar(80) NOT NULL CHECK
            (aggregation_order='point_then_curve_then_mode'),
          holdout_policy varchar(32) NOT NULL CHECK (holdout_policy='explicit_disjoint'),
          maximum_function_evaluations integer NOT NULL CHECK
            (maximum_function_evaluations=5000),
          non_production boolean NOT NULL CHECK (non_production),
          CONSTRAINT ck_modeling_ogden_plan_member_counts CHECK
            (member_count=calibration_member_count+holdout_member_count),
          CONSTRAINT pk_modeling_ogden_calibration_plan_revision PRIMARY KEY
            (organization_id, project_id, id),
          CONSTRAINT uq_modeling_ogden_calibration_plan_revision_scope UNIQUE
            (organization_id, project_id, classification, aggregate_id, id),
          CONSTRAINT uq_modeling_ogden_calibration_plan_revision_no UNIQUE
            (organization_id, project_id, aggregate_id, revision_no),
          CONSTRAINT fk_modeling_ogden_plan_revision_identity FOREIGN KEY
            (organization_id, project_id, classification, aggregate_id) REFERENCES
            modeling.ogden_calibration_plan
            (organization_id, project_id, classification, id) ON DELETE RESTRICT,
          CONSTRAINT fk_modeling_ogden_plan_revision_base FOREIGN KEY
            (organization_id, project_id, based_on_revision_id) REFERENCES
            modeling.ogden_calibration_plan_revision
            (organization_id, project_id, id) ON DELETE RESTRICT,
          CONSTRAINT fk_modeling_ogden_plan_profile FOREIGN KEY
            (organization_id, project_id, classification, scientific_profile_id,
             scientific_profile_revision_id) REFERENCES modeling.scientific_profile_revision
            (organization_id, project_id, classification, aggregate_id, id) ON DELETE RESTRICT,
          CONSTRAINT fk_modeling_ogden_plan_state FOREIGN KEY
            (organization_id, project_id, classification, material_state_id,
             material_state_revision_id) REFERENCES catalog.material_state_revision
            (organization_id, project_id, classification, aggregate_id, id) ON DELETE RESTRICT,
          CONSTRAINT fk_modeling_ogden_plan_baseline FOREIGN KEY
            (organization_id, project_id, classification, baseline_model_id,
             baseline_model_revision_id) REFERENCES modeling.material_model_revision
            (organization_id, project_id, classification, aggregate_id, id) ON DELETE RESTRICT
        );

        ALTER TABLE modeling.ogden_calibration_plan
          ADD CONSTRAINT fk_modeling_ogden_plan_current FOREIGN KEY
          (organization_id, project_id, classification, id, current_revision_id)
          REFERENCES modeling.ogden_calibration_plan_revision
          (organization_id, project_id, classification, aggregate_id, id)
          DEFERRABLE INITIALLY DEFERRED;

        CREATE TABLE modeling.ogden_calibration_plan_member (
          organization_id uuid NOT NULL, project_id uuid NOT NULL,
          classification varchar(64) NOT NULL, plan_id uuid NOT NULL,
          plan_revision_id uuid NOT NULL, ordinal smallint NOT NULL CHECK
            (ordinal BETWEEN 0 AND 23),
          role varchar(16) NOT NULL CHECK (role IN ('calibration','holdout')),
          test_mode varchar(32) NOT NULL CHECK
            (test_mode IN ('uniaxial_tension','planar_tension','biaxial_tension')),
          dataset_id uuid NOT NULL, dataset_revision_id uuid NOT NULL,
          weight double precision NOT NULL CHECK
            (weight>0 AND weight<'Infinity'::double precision),
          CONSTRAINT pk_modeling_ogden_calibration_member PRIMARY KEY
            (organization_id, project_id, plan_revision_id, ordinal),
          CONSTRAINT uq_modeling_ogden_calibration_member_dataset UNIQUE
            (organization_id, project_id, plan_revision_id, dataset_revision_id),
          CONSTRAINT fk_modeling_ogden_calibration_member_plan FOREIGN KEY
            (organization_id, project_id, classification, plan_id, plan_revision_id) REFERENCES
            modeling.ogden_calibration_plan_revision
            (organization_id, project_id, classification, aggregate_id, id) ON DELETE RESTRICT,
          CONSTRAINT fk_modeling_ogden_calibration_member_dataset FOREIGN KEY
            (organization_id, project_id, classification, dataset_id, dataset_revision_id)
            REFERENCES datasets.governed_dataset_revision
            (organization_id, project_id, classification, aggregate_id, id) ON DELETE RESTRICT
        );

        CREATE TABLE modeling.ogden_calibration_run (
          id uuid NOT NULL, organization_id uuid NOT NULL, project_id uuid NOT NULL,
          classification varchar(64) NOT NULL, plan_id uuid NOT NULL,
          plan_revision_id uuid NOT NULL,
          scientific_profile_id uuid NOT NULL, scientific_profile_revision_id uuid NOT NULL,
          material_state_id uuid NOT NULL, material_state_revision_id uuid NOT NULL,
          baseline_model_id uuid NOT NULL, baseline_model_revision_id uuid NOT NULL,
          status varchar(16) NOT NULL CHECK (status IN ('succeeded','failed')),
          environment_digest varchar(71) NOT NULL CHECK
            (environment_digest ~ '^sha256:[0-9a-f]{64}$'),
          calibration_curve_count smallint NOT NULL CHECK
            (calibration_curve_count BETWEEN 1 AND 24),
          holdout_curve_count smallint NOT NULL CHECK (holdout_curve_count BETWEEN 0 AND 23),
          test_mode_count smallint NOT NULL CHECK (test_mode_count BETWEEN 1 AND 3),
          attempt_count smallint NOT NULL CHECK (attempt_count BETWEEN 0 AND 32),
          candidate_count smallint NOT NULL CHECK (candidate_count BETWEEN 0 AND 32),
          failure_code varchar(100),
          change_reason text NOT NULL CHECK (length(btrim(change_reason)) BETWEEN 1 AND 2000),
          started_at timestamptz NOT NULL, ended_at timestamptz NOT NULL,
          created_by uuid NOT NULL, request_id uuid NOT NULL, trace_id varchar(255) NOT NULL,
          CONSTRAINT pk_modeling_ogden_calibration_run PRIMARY KEY
            (organization_id, project_id, id),
          CONSTRAINT uq_modeling_ogden_calibration_run_scope UNIQUE
            (organization_id, project_id, classification, id),
          CONSTRAINT ck_modeling_ogden_calibration_run_state CHECK
            ((status='succeeded' AND candidate_count>0 AND
              attempt_count=candidate_count AND failure_code IS NULL)
             OR (status='failed' AND candidate_count=0 AND failure_code IS NOT NULL)),
          CONSTRAINT fk_modeling_ogden_calibration_run_plan FOREIGN KEY
            (organization_id, project_id, classification, plan_id, plan_revision_id) REFERENCES
            modeling.ogden_calibration_plan_revision
            (organization_id, project_id, classification, aggregate_id, id) ON DELETE RESTRICT,
          CONSTRAINT fk_modeling_ogden_calibration_run_profile FOREIGN KEY
            (organization_id, project_id, classification, scientific_profile_id,
             scientific_profile_revision_id) REFERENCES modeling.scientific_profile_revision
            (organization_id, project_id, classification, aggregate_id, id) ON DELETE RESTRICT,
          CONSTRAINT fk_modeling_ogden_calibration_run_state FOREIGN KEY
            (organization_id, project_id, classification, material_state_id,
             material_state_revision_id) REFERENCES catalog.material_state_revision
            (organization_id, project_id, classification, aggregate_id, id) ON DELETE RESTRICT,
          CONSTRAINT fk_modeling_ogden_calibration_run_baseline FOREIGN KEY
            (organization_id, project_id, classification, baseline_model_id,
             baseline_model_revision_id) REFERENCES modeling.material_model_revision
            (organization_id, project_id, classification, aggregate_id, id) ON DELETE RESTRICT
        );

        CREATE TABLE modeling.ogden_calibration_attempt (
          id uuid NOT NULL, organization_id uuid NOT NULL, project_id uuid NOT NULL,
          classification varchar(64) NOT NULL, calibration_run_id uuid NOT NULL,
          attempt_ordinal smallint NOT NULL CHECK (attempt_ordinal BETWEEN 0 AND 31),
          initial_mu_pa double precision NOT NULL CHECK
            (initial_mu_pa>0 AND initial_mu_pa<'Infinity'::double precision),
          initial_alpha double precision NOT NULL CHECK
            (initial_alpha>0 AND initial_alpha<'Infinity'::double precision),
          candidate_id uuid NOT NULL,
          CONSTRAINT pk_modeling_ogden_calibration_attempt PRIMARY KEY
            (organization_id, project_id, id),
          CONSTRAINT uq_modeling_ogden_calibration_attempt_scope UNIQUE
            (organization_id, project_id, classification, id),
          CONSTRAINT uq_modeling_ogden_calibration_attempt_ordinal UNIQUE
            (organization_id, project_id, calibration_run_id, attempt_ordinal),
          CONSTRAINT uq_modeling_ogden_calibration_attempt_candidate UNIQUE
            (organization_id, project_id, classification, calibration_run_id, id, candidate_id),
          CONSTRAINT fk_modeling_ogden_calibration_attempt_run FOREIGN KEY
            (organization_id, project_id, classification, calibration_run_id) REFERENCES
            modeling.ogden_calibration_run
            (organization_id, project_id, classification, id) ON DELETE RESTRICT
        );

        CREATE TABLE modeling.ogden_calibration_candidate (
          id uuid NOT NULL, organization_id uuid NOT NULL, project_id uuid NOT NULL,
          classification varchar(64) NOT NULL, calibration_run_id uuid NOT NULL,
          calibration_attempt_id uuid NOT NULL, attempt_ordinal smallint NOT NULL,
          candidate_sha256 char(64) NOT NULL CHECK (candidate_sha256 ~ '^[0-9a-f]{64}$'),
          mu_pa double precision NOT NULL CHECK
            (mu_pa>0 AND mu_pa<'Infinity'::double precision),
          alpha double precision NOT NULL CHECK
            (alpha>0 AND alpha<'Infinity'::double precision),
          objective_total double precision NOT NULL CHECK
            (objective_total>=0 AND objective_total<'Infinity'::double precision),
          uniaxial_objective double precision NOT NULL CHECK
            (uniaxial_objective>=0 AND uniaxial_objective<'Infinity'::double precision),
          planar_objective double precision NOT NULL CHECK
            (planar_objective>=0 AND planar_objective<'Infinity'::double precision),
          biaxial_objective double precision NOT NULL CHECK
            (biaxial_objective>=0 AND biaxial_objective<'Infinity'::double precision),
          calibration_rmse_pa double precision NOT NULL CHECK
            (calibration_rmse_pa>=0 AND
             calibration_rmse_pa<'Infinity'::double precision),
          calibration_normalized_rmse double precision NOT NULL CHECK
            (calibration_normalized_rmse>=0 AND
             calibration_normalized_rmse<'Infinity'::double precision),
          holdout_rmse_pa double precision CHECK
            (holdout_rmse_pa>=0 AND holdout_rmse_pa<'Infinity'::double precision),
          holdout_normalized_rmse double precision CHECK
            (holdout_normalized_rmse>=0 AND
             holdout_normalized_rmse<'Infinity'::double precision),
          status varchar(24) NOT NULL CHECK (status IN ('converged','nonconverged')),
          convergence_status_code integer NOT NULL, convergence_reason varchar(255) NOT NULL,
          function_evaluations integer NOT NULL CHECK (function_evaluations>0),
          jacobian_evaluations integer CHECK (jacobian_evaluations>=0),
          optimality double precision NOT NULL CHECK
            (optimality>=0 AND optimality<'Infinity'::double precision),
          parameter_at_bound boolean NOT NULL,
          jacobian_rank smallint NOT NULL CHECK (jacobian_rank BETWEEN 0 AND 2),
          jacobian_condition_number double precision CHECK
            (jacobian_condition_number>=0 AND
             jacobian_condition_number<'Infinity'::double precision),
          identifiability_status varchar(32) NOT NULL CHECK
            (identifiability_status IN ('full_rank','rank_deficient')),
          uncertainty_status varchar(48) NOT NULL CHECK
            (uncertainty_status IN ('estimated_jacobian_covariance','not_estimable_rank_deficient',
             'not_estimable_insufficient_dof','not_estimable_nonfinite')),
          mu_standard_error_pa double precision, alpha_standard_error double precision,
          mu_confidence_lower_pa double precision, mu_confidence_upper_pa double precision,
          alpha_confidence_lower double precision, alpha_confidence_upper double precision,
          diagnostics_artifact_id uuid NOT NULL,
          diagnostics_sha256 char(64) NOT NULL CHECK (diagnostics_sha256 ~ '^[0-9a-f]{64}$'),
          diagnostics_point_count integer NOT NULL CHECK
            (diagnostics_point_count BETWEEN 5 AND 50000),
          created_at timestamptz NOT NULL, created_by uuid NOT NULL,
          CONSTRAINT pk_modeling_ogden_calibration_candidate PRIMARY KEY
            (organization_id, project_id, id),
          CONSTRAINT uq_modeling_ogden_calibration_candidate_scope UNIQUE
            (organization_id, project_id, classification, id),
          CONSTRAINT uq_modeling_ogden_calibration_candidate_attempt UNIQUE
            (organization_id, project_id, calibration_run_id, calibration_attempt_id),
          CONSTRAINT ck_modeling_ogden_uncertainty_complete CHECK
            ((uncertainty_status='estimated_jacobian_covariance' AND
              mu_standard_error_pa IS NOT NULL AND alpha_standard_error IS NOT NULL AND
              mu_confidence_lower_pa IS NOT NULL AND mu_confidence_upper_pa IS NOT NULL AND
              alpha_confidence_lower IS NOT NULL AND alpha_confidence_upper IS NOT NULL)
             OR (uncertainty_status<>'estimated_jacobian_covariance' AND
              mu_standard_error_pa IS NULL AND alpha_standard_error IS NULL AND
              mu_confidence_lower_pa IS NULL AND mu_confidence_upper_pa IS NULL AND
              alpha_confidence_lower IS NULL AND alpha_confidence_upper IS NULL)),
          CONSTRAINT fk_modeling_ogden_calibration_candidate_run FOREIGN KEY
            (organization_id, project_id, classification, calibration_run_id) REFERENCES
            modeling.ogden_calibration_run
            (organization_id, project_id, classification, id) ON DELETE RESTRICT,
          CONSTRAINT fk_modeling_ogden_calibration_candidate_attempt FOREIGN KEY
            (organization_id, project_id, classification, calibration_run_id,
             calibration_attempt_id, id) REFERENCES modeling.ogden_calibration_attempt
            (organization_id, project_id, classification, calibration_run_id, id, candidate_id)
            ON DELETE RESTRICT,
          CONSTRAINT fk_modeling_ogden_calibration_candidate_artifact FOREIGN KEY
            (organization_id, project_id, classification, diagnostics_artifact_id) REFERENCES
            artifact.artifact (organization_id, project_id, classification, id) ON DELETE RESTRICT
        );

        CREATE TABLE modeling.ogden_calibration_candidate_warning (
          organization_id uuid NOT NULL, project_id uuid NOT NULL,
          classification varchar(64) NOT NULL, candidate_id uuid NOT NULL,
          ordinal smallint NOT NULL CHECK (ordinal BETWEEN 0 AND 15),
          warning_code varchar(64) NOT NULL CHECK (length(btrim(warning_code)) BETWEEN 1 AND 64),
          CONSTRAINT pk_modeling_ogden_calibration_warning PRIMARY KEY
            (organization_id, project_id, candidate_id, ordinal),
          CONSTRAINT fk_modeling_ogden_calibration_warning_candidate FOREIGN KEY
            (organization_id, project_id, classification, candidate_id) REFERENCES
            modeling.ogden_calibration_candidate
            (organization_id, project_id, classification, id) ON DELETE RESTRICT
        );

        CREATE INDEX ix_modeling_ogden_plan_state ON modeling.ogden_calibration_plan
          (organization_id, project_id, material_state_id, updated_at DESC);
        CREATE INDEX ix_modeling_ogden_run_state ON modeling.ogden_calibration_run
          (organization_id, project_id, material_state_id, started_at DESC);
        CREATE INDEX ix_modeling_ogden_candidate_objective
          ON modeling.ogden_calibration_candidate
          (organization_id, project_id, calibration_run_id, objective_total);

        CREATE TRIGGER modeling_ogden_calibration_plan_head_only BEFORE UPDATE OR DELETE
          ON modeling.ogden_calibration_plan FOR EACH ROW
          EXECUTE FUNCTION revisioning.guard_identity_head_update();
        """
    )
    for table in _TABLES[1:]:
        op.execute(
            f"CREATE TRIGGER modeling_{table}_immutable BEFORE UPDATE OR DELETE "
            f"ON modeling.{table} FOR EACH ROW "
            "EXECUTE FUNCTION revisioning.reject_immutable_row_mutation()"
        )
    _rls("ogden_calibration_plan", identity=True)
    for table in _TABLES[1:]:
        _rls(table)


def downgrade() -> None:
    op.execute(
        "ALTER TABLE modeling.ogden_calibration_plan "
        "DROP CONSTRAINT fk_modeling_ogden_plan_current"
    )
    for table in reversed(_TABLES):
        op.execute(f"DROP TABLE modeling.{table}")
    op.execute(
        """
        DO $$ BEGIN
          IF EXISTS (
            SELECT 1 FROM testing.test_method WHERE method_code IN
              ('reference_planar_tension','reference_biaxial_tension')
          ) THEN
            RAISE EXCEPTION
              'cannot downgrade while immutable planar or biaxial Test Methods exist';
          END IF;
        END $$;
        ALTER TABLE testing.test_method DROP CONSTRAINT ck_testing_test_method_code;
        ALTER TABLE testing.test_method_revision
          DROP CONSTRAINT ck_testing_test_method_revision_declared;
        ALTER TABLE testing.test_method ADD CONSTRAINT ck_testing_test_method_code CHECK
          (method_code IN ('reference_uniaxial_tensile','reference_shear_relaxation'));
        ALTER TABLE testing.test_method_revision ADD CONSTRAINT
          ck_testing_test_method_revision_declared CHECK
          ((method_code='reference_uniaxial_tensile' AND
            display_name='Reference uniaxial tensile CSV') OR
           (method_code='reference_shear_relaxation' AND
            display_name='Reference shear relaxation CSV'));
        """
    )

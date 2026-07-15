"""Add bounded two-term reference Prony calibration evidence.

Revision ID: 20260810_044_prony_cal
Revises: 20260809_043_shear_proc
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260810_044_prony_cal"
down_revision: str | None = "20260809_043_shear_proc"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _secure(table: str, *, mutable: bool = False) -> None:
    for operation, permission in (
        ("select", "modeling.read"),
        ("insert", "calibration.execute"),
    ):
        predicate = "USING" if operation == "select" else "WITH CHECK"
        op.execute(
            f"CREATE POLICY modeling_{table}_{operation} ON modeling.{table} "
            f"FOR {operation.upper()} {predicate} "
            "(access_control.can_access_row(organization_id, project_id, "
            f"classification, '{permission}'))"
        )
    if mutable:
        op.execute(
            f"CREATE POLICY modeling_{table}_update ON modeling.{table} FOR UPDATE "
            "USING (access_control.can_access_row(organization_id, project_id, "
            "classification, 'calibration.execute')) WITH CHECK "
            "(access_control.can_access_row(organization_id, project_id, "
            "classification, 'calibration.execute'))"
        )
    op.execute(f"ALTER TABLE modeling.{table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE modeling.{table} FORCE ROW LEVEL SECURITY")


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE modeling.prony_calibration_plan (
          id uuid NOT NULL, organization_id uuid NOT NULL, project_id uuid NOT NULL,
          classification varchar(64) NOT NULL, current_revision_id uuid NOT NULL,
          created_at timestamptz NOT NULL, created_by uuid NOT NULL,
          updated_at timestamptz NOT NULL, plan_label varchar(160) NOT NULL,
          plan_kind varchar(100) NOT NULL,
          CONSTRAINT pk_mdl_prony_plan PRIMARY KEY (organization_id, project_id, id),
          CONSTRAINT uq_mdl_prony_plan_scoped UNIQUE
            (organization_id, project_id, classification, id),
          CONSTRAINT uq_mdl_prony_plan_label UNIQUE
            (organization_id, project_id, classification, plan_label),
          CONSTRAINT ck_mdl_prony_plan_shape CHECK
            (length(btrim(plan_label)) BETWEEN 1 AND 160 AND
             plan_kind='reference_two_term_shear_relaxation_prony')
        );

        CREATE TABLE modeling.prony_calibration_plan_revision (
          id uuid NOT NULL, aggregate_id uuid NOT NULL, organization_id uuid NOT NULL,
          project_id uuid NOT NULL, classification varchar(64) NOT NULL,
          revision_no bigint NOT NULL, based_on_revision_id uuid NULL,
          schema_id varchar(255) NOT NULL, schema_version varchar(64) NOT NULL,
          content_hash char(64) COLLATE "C" NOT NULL, created_at timestamptz NOT NULL,
          created_by uuid NOT NULL, change_reason text NOT NULL, request_id uuid NOT NULL,
          trace_id varchar(255) NOT NULL, plan_kind varchar(100) NOT NULL,
          plan_label varchar(160) NOT NULL, input_dataset_id uuid NOT NULL,
          input_dataset_revision_id uuid NOT NULL, baseline_model_id uuid NOT NULL,
          baseline_model_revision_id uuid NOT NULL,
          total_g_lower float8 NOT NULL, total_g_initial float8 NOT NULL,
          total_g_upper float8 NOT NULL, fast_fraction_lower float8 NOT NULL,
          fast_fraction_initial float8 NOT NULL, fast_fraction_upper float8 NOT NULL,
          fast_tau_lower_s float8 NOT NULL, fast_tau_initial_s float8 NOT NULL,
          fast_tau_upper_s float8 NOT NULL, slow_tau_lower_s float8 NOT NULL,
          slow_tau_initial_s float8 NOT NULL, slow_tau_upper_s float8 NOT NULL,
          normalization_modulus_pa float8 NOT NULL, multistart_count smallint NOT NULL,
          random_seed bigint NOT NULL, maximum_function_evaluations integer NOT NULL,
          ftol float8 NOT NULL, xtol float8 NOT NULL, gtol float8 NOT NULL,
          test_mode_adapter_id varchar(255) NOT NULL, evaluator_id varchar(255) NOT NULL,
          objective_engine_id varchar(255) NOT NULL,
          optimizer_adapter_id varchar(255) NOT NULL,
          residual_definition varchar(100) NOT NULL, point_weighting varchar(32) NOT NULL,
          objective_aggregation varchar(100) NOT NULL,
          missing_data_policy varchar(32) NOT NULL, optimizer_method varchar(32) NOT NULL,
          rng_algorithm varchar(100) NOT NULL, term_count smallint NOT NULL,
          non_production boolean NOT NULL,
          CONSTRAINT pk_mdl_prony_plan_rev PRIMARY KEY (organization_id, project_id, id),
          CONSTRAINT uq_mdl_prony_plan_rev_ref UNIQUE
            (organization_id, project_id, aggregate_id, id),
          CONSTRAINT uq_mdl_prony_plan_rev_scoped UNIQUE
            (organization_id, project_id, classification, aggregate_id, id),
          CONSTRAINT uq_mdl_prony_plan_rev_no UNIQUE
            (organization_id, project_id, aggregate_id, revision_no),
          CONSTRAINT ck_mdl_prony_plan_rev_base CHECK
            ((revision_no=1 AND based_on_revision_id IS NULL) OR
             (revision_no>1 AND based_on_revision_id IS NOT NULL)),
          CONSTRAINT ck_mdl_prony_plan_rev_schema CHECK
            (schema_id='urn:cmp:modeling:reference-prony-calibration-plan:1.0.0' AND
             schema_version='1.0.0' AND content_hash ~ '^[0-9a-f]{64}$'),
          CONSTRAINT ck_mdl_prony_plan_rev_parameters CHECK
            (0<total_g_lower AND total_g_lower<=total_g_initial AND
             total_g_initial<=total_g_upper AND total_g_upper<1 AND
             0<fast_fraction_lower AND fast_fraction_lower<=fast_fraction_initial AND
             fast_fraction_initial<=fast_fraction_upper AND fast_fraction_upper<1 AND
             0<fast_tau_lower_s AND fast_tau_lower_s<=fast_tau_initial_s AND
             fast_tau_initial_s<=fast_tau_upper_s AND
             fast_tau_upper_s<slow_tau_lower_s AND slow_tau_lower_s<=slow_tau_initial_s AND
             slow_tau_initial_s<=slow_tau_upper_s AND normalization_modulus_pa>0 AND
             multistart_count BETWEEN 1 AND 16 AND random_seed>=0 AND
             maximum_function_evaluations BETWEEN 10 AND 1000000 AND
             ftol>0 AND ftol<1 AND xtol>0 AND xtol<1 AND gtol>0 AND gtol<1),
          CONSTRAINT ck_mdl_prony_plan_rev_fixed CHECK
            (plan_kind='reference_two_term_shear_relaxation_prony' AND
             test_mode_adapter_id='urn:cmp:reference:shear-relaxation-observed-points:1.0.0' AND
             evaluator_id='urn:cmp:reference:two-term-generalized-maxwell:1.0.0' AND
             objective_engine_id='urn:cmp:reference:uniform-normalized-modulus-wls:1.0.0' AND
             optimizer_adapter_id='urn:cmp:reference:scipy-least-squares:1.0.0' AND
             residual_definition='predicted_minus_observed_shear_modulus' AND
             point_weighting='uniform' AND
             objective_aggregation='mean_normalized_squared_residual' AND
             missing_data_policy='reject' AND optimizer_method='trf' AND
             rng_algorithm='numpy.random.PCG64' AND term_count=2 AND non_production),
          CONSTRAINT fk_mdl_prony_plan_rev_identity FOREIGN KEY
            (organization_id, project_id, aggregate_id)
            REFERENCES modeling.prony_calibration_plan
            (organization_id, project_id, id) ON DELETE RESTRICT
            DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_mdl_prony_plan_rev_base FOREIGN KEY
            (organization_id, project_id, aggregate_id, based_on_revision_id)
            REFERENCES modeling.prony_calibration_plan_revision
            (organization_id, project_id, aggregate_id, id) ON DELETE RESTRICT
            DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_mdl_prony_plan_rev_dataset FOREIGN KEY
            (organization_id, project_id, classification,
             input_dataset_id, input_dataset_revision_id)
            REFERENCES datasets.shear_relaxation_dataset_revision
            (organization_id, project_id, classification, aggregate_id, id)
            ON DELETE RESTRICT,
          CONSTRAINT fk_mdl_prony_plan_rev_model FOREIGN KEY
            (organization_id, project_id, classification,
             baseline_model_id, baseline_model_revision_id)
            REFERENCES modeling.linear_viscoelastic_revision
            (organization_id, project_id, classification,
             material_model_id, material_model_revision_id) ON DELETE RESTRICT
        );
        ALTER TABLE modeling.prony_calibration_plan ADD CONSTRAINT fk_mdl_prony_plan_current
          FOREIGN KEY (organization_id, project_id, id, current_revision_id)
          REFERENCES modeling.prony_calibration_plan_revision
          (organization_id, project_id, aggregate_id, id)
          ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED;

        CREATE TABLE modeling.prony_calibration_run (
          id uuid NOT NULL, organization_id uuid NOT NULL, project_id uuid NOT NULL,
          classification varchar(64) NOT NULL, plan_id uuid NOT NULL,
          plan_revision_id uuid NOT NULL, input_dataset_id uuid NOT NULL,
          input_dataset_revision_id uuid NOT NULL, baseline_model_id uuid NOT NULL,
          baseline_model_revision_id uuid NOT NULL, status varchar(16) NOT NULL,
          environment_digest char(64) COLLATE "C" NOT NULL, attempt_count smallint NOT NULL,
          candidate_count smallint NOT NULL, failure_code varchar(100) NULL,
          change_reason text NOT NULL, started_at timestamptz NOT NULL,
          ended_at timestamptz NOT NULL, created_by uuid NOT NULL,
          request_id uuid NOT NULL, trace_id varchar(255) NOT NULL,
          CONSTRAINT pk_mdl_prony_run PRIMARY KEY (organization_id, project_id, id),
          CONSTRAINT uq_mdl_prony_run_scoped UNIQUE
            (organization_id, project_id, classification, id),
          CONSTRAINT ck_mdl_prony_run_shape CHECK
            (status='succeeded' AND failure_code IS NULL AND ended_at>=started_at AND
             attempt_count BETWEEN 1 AND 16 AND candidate_count=attempt_count AND
             environment_digest ~ '^[0-9a-f]{64}$' AND
             length(btrim(change_reason)) BETWEEN 1 AND 2000),
          CONSTRAINT fk_mdl_prony_run_plan FOREIGN KEY
            (organization_id, project_id, classification, plan_id, plan_revision_id)
            REFERENCES modeling.prony_calibration_plan_revision
            (organization_id, project_id, classification, aggregate_id, id)
            ON DELETE RESTRICT,
          CONSTRAINT fk_mdl_prony_run_dataset FOREIGN KEY
            (organization_id, project_id, classification,
             input_dataset_id, input_dataset_revision_id)
            REFERENCES datasets.shear_relaxation_dataset_revision
            (organization_id, project_id, classification, aggregate_id, id)
            ON DELETE RESTRICT,
          CONSTRAINT fk_mdl_prony_run_model FOREIGN KEY
            (organization_id, project_id, classification,
             baseline_model_id, baseline_model_revision_id)
            REFERENCES modeling.linear_viscoelastic_revision
            (organization_id, project_id, classification,
             material_model_id, material_model_revision_id) ON DELETE RESTRICT
        );

        CREATE TABLE modeling.prony_calibration_attempt (
          id uuid NOT NULL, organization_id uuid NOT NULL, project_id uuid NOT NULL,
          classification varchar(64) NOT NULL, calibration_run_id uuid NOT NULL,
          attempt_ordinal smallint NOT NULL, initial_total_g_ratio float8 NOT NULL,
          initial_fast_term_fraction float8 NOT NULL, initial_fast_tau_s float8 NOT NULL,
          initial_slow_tau_s float8 NOT NULL, status varchar(16) NOT NULL,
          candidate_id uuid NOT NULL,
          CONSTRAINT pk_mdl_prony_attempt PRIMARY KEY (organization_id, project_id, id),
          CONSTRAINT uq_mdl_prony_attempt_scoped UNIQUE
            (organization_id, project_id, classification, id),
          CONSTRAINT uq_mdl_prony_attempt_ordinal UNIQUE
            (organization_id, project_id, classification, calibration_run_id, attempt_ordinal),
          CONSTRAINT uq_mdl_prony_attempt_ref UNIQUE
            (organization_id, project_id, classification, id,
             calibration_run_id, attempt_ordinal),
          CONSTRAINT ck_mdl_prony_attempt_shape CHECK
            (attempt_ordinal BETWEEN 1 AND 16 AND status IN ('converged','nonconverged') AND
             initial_total_g_ratio>0 AND initial_total_g_ratio<1 AND
             initial_fast_term_fraction>0 AND initial_fast_term_fraction<1 AND
             initial_fast_tau_s>0 AND initial_slow_tau_s>initial_fast_tau_s),
          CONSTRAINT fk_mdl_prony_attempt_run FOREIGN KEY
            (organization_id, project_id, classification, calibration_run_id)
            REFERENCES modeling.prony_calibration_run
            (organization_id, project_id, classification, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED
        );

        CREATE TABLE modeling.prony_calibration_candidate (
          id uuid NOT NULL, organization_id uuid NOT NULL, project_id uuid NOT NULL,
          classification varchar(64) NOT NULL, calibration_run_id uuid NOT NULL,
          calibration_attempt_id uuid NOT NULL, attempt_ordinal smallint NOT NULL,
          status varchar(16) NOT NULL, candidate_sha256 char(64) COLLATE "C" NOT NULL,
          total_g_ratio float8 NOT NULL, fast_term_fraction float8 NOT NULL,
          fast_g_ratio float8 NOT NULL, slow_g_ratio float8 NOT NULL,
          fast_relaxation_time_s float8 NOT NULL, slow_relaxation_time_s float8 NOT NULL,
          objective_total float8 NOT NULL, residual_root_mean_square_pa float8 NOT NULL,
          residual_mean_pa float8 NOT NULL, convergence_status_code smallint NOT NULL,
          convergence_reason varchar(255) NOT NULL, function_evaluations integer NOT NULL,
          jacobian_evaluations integer NULL, optimality float8 NOT NULL,
          parameter_at_bound boolean NOT NULL, identifiability_status varchar(100) NOT NULL,
          uncertainty_status varchar(100) NOT NULL, diagnostics_artifact_id uuid NOT NULL,
          diagnostics_sha256 char(64) COLLATE "C" NOT NULL,
          diagnostics_point_count integer NOT NULL, created_at timestamptz NOT NULL,
          created_by uuid NOT NULL,
          CONSTRAINT pk_mdl_prony_candidate PRIMARY KEY (organization_id, project_id, id),
          CONSTRAINT uq_mdl_prony_candidate_scoped UNIQUE
            (organization_id, project_id, classification, id),
          CONSTRAINT uq_mdl_prony_candidate_attempt UNIQUE
            (organization_id, project_id, classification, calibration_attempt_id),
          CONSTRAINT uq_mdl_prony_candidate_ordinal UNIQUE
            (organization_id, project_id, classification, calibration_run_id, attempt_ordinal),
          CONSTRAINT uq_mdl_prony_candidate_ref UNIQUE
            (organization_id, project_id, classification, id,
             calibration_run_id, calibration_attempt_id, attempt_ordinal),
          CONSTRAINT ck_mdl_prony_candidate_shape CHECK
            (status IN ('converged','nonconverged') AND candidate_sha256 ~ '^[0-9a-f]{64}$' AND
             total_g_ratio>0 AND total_g_ratio<1 AND fast_term_fraction>0 AND
             fast_term_fraction<1 AND fast_g_ratio>0 AND slow_g_ratio>0 AND
             abs((fast_g_ratio+slow_g_ratio)-total_g_ratio)<1e-10 AND
             fast_relaxation_time_s>0 AND
             slow_relaxation_time_s>fast_relaxation_time_s AND objective_total>=0 AND
             residual_root_mean_square_pa>=0 AND function_evaluations>0 AND
             optimality>=0 AND diagnostics_sha256 ~ '^[0-9a-f]{64}$' AND
             diagnostics_point_count>=5),
          CONSTRAINT fk_mdl_prony_candidate_run FOREIGN KEY
            (organization_id, project_id, classification, calibration_run_id)
            REFERENCES modeling.prony_calibration_run
            (organization_id, project_id, classification, id) ON DELETE RESTRICT,
          CONSTRAINT fk_mdl_prony_candidate_attempt FOREIGN KEY
            (organization_id, project_id, classification, calibration_attempt_id,
             calibration_run_id, attempt_ordinal)
            REFERENCES modeling.prony_calibration_attempt
            (organization_id, project_id, classification, id,
             calibration_run_id, attempt_ordinal)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_mdl_prony_candidate_artifact FOREIGN KEY
            (organization_id, project_id, classification,
             diagnostics_artifact_id, diagnostics_sha256)
            REFERENCES artifact.artifact
            (organization_id, project_id, classification, id, sha256) ON DELETE RESTRICT
        );
        ALTER TABLE modeling.prony_calibration_attempt
          ADD CONSTRAINT fk_mdl_prony_attempt_candidate FOREIGN KEY
          (organization_id, project_id, classification, candidate_id,
           calibration_run_id, id, attempt_ordinal)
          REFERENCES modeling.prony_calibration_candidate
          (organization_id, project_id, classification, id,
           calibration_run_id, calibration_attempt_id, attempt_ordinal)
          ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED;
        """
    )
    op.execute(
        """
        CREATE FUNCTION modeling.validate_reference_prony_plan_revision()
        RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE dataset_row record; model_row record;
        BEGIN
          SELECT representation, material_state_id, material_state_revision_id
            INTO dataset_row
            FROM datasets.shear_relaxation_dataset_revision
           WHERE organization_id=NEW.organization_id AND project_id=NEW.project_id
             AND classification=NEW.classification AND aggregate_id=NEW.input_dataset_id
             AND id=NEW.input_dataset_revision_id;
          SELECT r.material_state_id, r.material_state_revision_id, s.bulk_relaxation_status
            INTO model_row FROM modeling.material_model_revision r
            JOIN modeling.linear_viscoelastic_revision s
              ON s.organization_id=r.organization_id AND s.project_id=r.project_id
             AND s.material_model_id=r.aggregate_id AND s.material_model_revision_id=r.id
           WHERE r.organization_id=NEW.organization_id AND r.project_id=NEW.project_id
             AND r.classification=NEW.classification AND r.aggregate_id=NEW.baseline_model_id
             AND r.id=NEW.baseline_model_revision_id;
          IF dataset_row.representation IS DISTINCT FROM 'processed' OR
             model_row.bulk_relaxation_status IS DISTINCT FROM 'not_characterized' OR
             dataset_row.material_state_id IS DISTINCT FROM model_row.material_state_id OR
             dataset_row.material_state_revision_id IS DISTINCT FROM
               model_row.material_state_revision_id THEN
            RAISE EXCEPTION 'invalid reference Prony calibration pins' USING ERRCODE='23514';
          END IF;
          RETURN NEW;
        END $$;
        CREATE TRIGGER modeling_validate_reference_prony_plan_revision
          BEFORE INSERT ON modeling.prony_calibration_plan_revision FOR EACH ROW
          EXECUTE FUNCTION modeling.validate_reference_prony_plan_revision();
        CREATE TRIGGER modeling_prony_plan_head
          BEFORE UPDATE OR DELETE ON modeling.prony_calibration_plan FOR EACH ROW
          EXECUTE FUNCTION revisioning.guard_identity_head_update();
        CREATE TRIGGER modeling_prony_plan_revision_immutable
          BEFORE UPDATE OR DELETE ON modeling.prony_calibration_plan_revision FOR EACH ROW
          EXECUTE FUNCTION revisioning.reject_immutable_row_mutation();
        CREATE TRIGGER modeling_prony_run_immutable
          BEFORE UPDATE OR DELETE ON modeling.prony_calibration_run FOR EACH ROW
          EXECUTE FUNCTION revisioning.reject_immutable_row_mutation();
        CREATE TRIGGER modeling_prony_attempt_immutable
          BEFORE UPDATE OR DELETE ON modeling.prony_calibration_attempt FOR EACH ROW
          EXECUTE FUNCTION revisioning.reject_immutable_row_mutation();
        CREATE TRIGGER modeling_prony_candidate_immutable
          BEFORE UPDATE OR DELETE ON modeling.prony_calibration_candidate FOR EACH ROW
          EXECUTE FUNCTION revisioning.reject_immutable_row_mutation();
        CREATE INDEX ix_mdl_prony_plan_dataset
          ON modeling.prony_calibration_plan_revision
          (organization_id, project_id, input_dataset_revision_id);
        CREATE INDEX ix_mdl_prony_plan_model
          ON modeling.prony_calibration_plan_revision
          (organization_id, project_id, baseline_model_revision_id);
        CREATE INDEX ix_mdl_prony_run_plan
          ON modeling.prony_calibration_run
          (organization_id, project_id, plan_revision_id);
        CREATE INDEX ix_mdl_prony_candidate_run_objective
          ON modeling.prony_calibration_candidate
          (organization_id, project_id, calibration_run_id, objective_total);
        """
    )
    _secure("prony_calibration_plan", mutable=True)
    for table in (
        "prony_calibration_plan_revision",
        "prony_calibration_run",
        "prony_calibration_attempt",
        "prony_calibration_candidate",
    ):
        _secure(table)


def downgrade() -> None:
    op.execute(
        "DROP FUNCTION IF EXISTS modeling.validate_reference_prony_plan_revision() CASCADE"
    )
    op.execute(
        "ALTER TABLE modeling.prony_calibration_plan "
        "DROP CONSTRAINT IF EXISTS fk_mdl_prony_plan_current"
    )
    for table in (
        "prony_calibration_candidate",
        "prony_calibration_attempt",
        "prony_calibration_run",
        "prony_calibration_plan_revision",
        "prony_calibration_plan",
    ):
        op.execute(f"DROP TABLE IF EXISTS modeling.{table} CASCADE")

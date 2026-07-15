# ruff: noqa: E501
"""Add typed multi-curve reference Voce calibration persistence.

Revision ID: 20260801_035_p1
Revises: 20260731_034_p02
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260801_035_p1"
down_revision: str | None = "20260731_034_p02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _secure(table: str, *, update: bool = False) -> None:
    op.execute(f"ALTER TABLE modeling.{table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE modeling.{table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY modeling_{table}_select ON modeling.{table} FOR SELECT "
        "USING (access_control.can_access_row(organization_id, project_id, "
        "classification, 'modeling.read'))"
    )
    op.execute(
        f"CREATE POLICY modeling_{table}_insert ON modeling.{table} FOR INSERT "
        "WITH CHECK (access_control.can_access_row(organization_id, project_id, "
        "classification, 'calibration.execute'))"
    )
    if update:
        op.execute(
            f"CREATE POLICY modeling_{table}_update ON modeling.{table} FOR UPDATE "
            "USING (access_control.can_access_row(organization_id, project_id, "
            "classification, 'calibration.execute')) WITH CHECK "
            "(access_control.can_access_row(organization_id, project_id, "
            "classification, 'calibration.execute'))"
        )


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE modeling.voce_calibration_plan (
          id uuid NOT NULL, organization_id uuid NOT NULL, project_id uuid NOT NULL,
          classification varchar(64) NOT NULL, current_revision_id uuid NOT NULL,
          created_at timestamptz NOT NULL, created_by uuid NOT NULL,
          updated_at timestamptz NOT NULL, plan_label varchar(160) NOT NULL,
          plan_kind varchar(100) NOT NULL,
          CONSTRAINT pk_mdl_voce_plan PRIMARY KEY (organization_id, project_id, id),
          CONSTRAINT uq_mdl_voce_plan_scoped UNIQUE (organization_id, project_id, classification, id),
          CONSTRAINT uq_mdl_voce_plan_label UNIQUE (organization_id, project_id, classification, plan_label),
          CONSTRAINT ck_mdl_voce_plan_ids CHECK (id <> '00000000-0000-0000-0000-000000000000'::uuid AND current_revision_id <> '00000000-0000-0000-0000-000000000000'::uuid AND created_by <> '00000000-0000-0000-0000-000000000000'::uuid),
          CONSTRAINT ck_mdl_voce_plan_label CHECK (length(btrim(plan_label)) BETWEEN 1 AND 160),
          CONSTRAINT ck_mdl_voce_plan_kind CHECK (plan_kind = 'reference_multi_curve_voce_saturation')
        )
        """
    )
    op.execute(
        """
        CREATE TABLE modeling.voce_calibration_plan_revision (
          id uuid NOT NULL, aggregate_id uuid NOT NULL, organization_id uuid NOT NULL,
          project_id uuid NOT NULL, classification varchar(64) NOT NULL,
          revision_no bigint NOT NULL, based_on_revision_id uuid NULL,
          schema_id varchar(255) NOT NULL, schema_version varchar(64) NOT NULL,
          content_hash char(64) COLLATE "C" NOT NULL, created_at timestamptz NOT NULL,
          created_by uuid NOT NULL, change_reason text NOT NULL, request_id uuid NOT NULL,
          trace_id varchar(255) NOT NULL, plan_kind varchar(100) NOT NULL,
          calibration_input_scope_id uuid NOT NULL, calibration_input_scope_revision_id uuid NOT NULL,
          material_state_id uuid NOT NULL, material_state_revision_id uuid NOT NULL,
          property_set_id uuid NOT NULL, property_set_revision_id uuid NOT NULL,
          youngs_modulus_pa float8 NOT NULL,
          sigma_0_lower_pa float8 NOT NULL, sigma_0_initial_pa float8 NOT NULL,
          sigma_0_upper_pa float8 NOT NULL, sigma_0_scale_pa float8 NOT NULL,
          q_lower_pa float8 NOT NULL, q_initial_pa float8 NOT NULL,
          q_upper_pa float8 NOT NULL, q_scale_pa float8 NOT NULL,
          b_lower float8 NOT NULL, b_initial float8 NOT NULL,
          b_upper float8 NOT NULL, b_scale float8 NOT NULL,
          normalization_stress_scale_pa float8 NOT NULL, multistart_count smallint NOT NULL,
          random_seed bigint NOT NULL, maximum_function_evaluations integer NOT NULL,
          ftol float8 NOT NULL, xtol float8 NOT NULL, gtol float8 NOT NULL,
          model_family_id varchar(255) NOT NULL, test_mode_adapter_id varchar(255) NOT NULL,
          evaluator_id varchar(255) NOT NULL, objective_engine_id varchar(255) NOT NULL,
          optimizer_adapter_id varchar(255) NOT NULL, evaluation_mode varchar(64) NOT NULL,
          residual_definition varchar(100) NOT NULL, specimen_weighting varchar(100) NOT NULL,
          point_weighting varchar(100) NOT NULL, objective_aggregation varchar(100) NOT NULL,
          x_domain_policy varchar(100) NOT NULL, missing_data_policy varchar(32) NOT NULL,
          optimizer_method varchar(32) NOT NULL, rng_algorithm varchar(100) NOT NULL,
          non_production boolean NOT NULL,
          CONSTRAINT pk_mdl_voce_plan_rev PRIMARY KEY (organization_id, project_id, id),
          CONSTRAINT uq_mdl_voce_plan_rev_id UNIQUE (organization_id, project_id, aggregate_id, id),
          CONSTRAINT uq_mdl_voce_plan_rev_scoped UNIQUE (organization_id, project_id, classification, aggregate_id, id),
          CONSTRAINT uq_mdl_voce_plan_rev_no UNIQUE (organization_id, project_id, aggregate_id, revision_no),
          CONSTRAINT ck_mdl_voce_plan_rev_base CHECK ((revision_no = 1 AND based_on_revision_id IS NULL) OR (revision_no > 1 AND based_on_revision_id IS NOT NULL)),
          CONSTRAINT ck_mdl_voce_plan_rev_schema CHECK (schema_id = 'urn:cmp:modeling:reference-voce-calibration-plan:1.0.0' AND schema_version = '1.0.0'),
          CONSTRAINT ck_mdl_voce_plan_rev_hash CHECK (content_hash ~ '^[0-9a-f]{64}$'),
          CONSTRAINT ck_mdl_voce_plan_rev_reason CHECK (length(btrim(change_reason)) BETWEEN 1 AND 2000),
          CONSTRAINT ck_mdl_voce_plan_rev_fixed CHECK (
            plan_kind = 'reference_multi_curve_voce_saturation'
            AND model_family_id = 'urn:cmp:reference:voce-saturation-hardening:1.0.0'
            AND test_mode_adapter_id = 'urn:cmp:reference:uniaxial-engineering-to-true-plastic:1.0.0'
            AND evaluator_id = 'urn:cmp:reference:voce-closed-form-curve-evaluator:1.0.0'
            AND objective_engine_id = 'urn:cmp:reference:equal-specimen-normalized-wls:1.0.0'
            AND optimizer_adapter_id = 'urn:cmp:reference:scipy-least-squares:1.0.0'
            AND evaluation_mode = 'closed_form_curve'
            AND residual_definition = 'predicted_minus_observed_true_yield_stress'
            AND specimen_weighting = 'equal_specimen'
            AND point_weighting = 'uniform_within_specimen'
            AND objective_aggregation = 'mean_of_specimen_mean_normalized_squared_residual'
            AND x_domain_policy = 'observed_pre_necking_positive_true_plastic_strain'
            AND missing_data_policy = 'reject' AND optimizer_method = 'trf'
            AND rng_algorithm = 'numpy.random.PCG64' AND non_production),
          CONSTRAINT ck_mdl_voce_plan_rev_numeric CHECK (
            youngs_modulus_pa > 0 AND sigma_0_lower_pa > 0 AND sigma_0_lower_pa <= sigma_0_initial_pa
            AND sigma_0_initial_pa <= sigma_0_upper_pa AND sigma_0_lower_pa < sigma_0_upper_pa
            AND sigma_0_scale_pa > 0
            AND q_lower_pa > 0 AND q_lower_pa <= q_initial_pa AND q_initial_pa <= q_upper_pa
            AND q_lower_pa < q_upper_pa AND q_scale_pa > 0
            AND b_lower > 0 AND b_lower <= b_initial AND b_initial <= b_upper
            AND b_lower < b_upper
            AND b_scale > 0 AND normalization_stress_scale_pa > 0
            AND multistart_count BETWEEN 1 AND 16 AND random_seed >= 0
            AND maximum_function_evaluations BETWEEN 10 AND 1000000
            AND ftol > 0 AND ftol < 1 AND xtol > 0 AND xtol < 1 AND gtol > 0 AND gtol < 1),
          CONSTRAINT fk_mdl_voce_plan_rev_identity FOREIGN KEY (organization_id, project_id, aggregate_id)
            REFERENCES modeling.voce_calibration_plan (organization_id, project_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_mdl_voce_plan_rev_base FOREIGN KEY (organization_id, project_id, aggregate_id, based_on_revision_id)
            REFERENCES modeling.voce_calibration_plan_revision (organization_id, project_id, aggregate_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_mdl_voce_plan_scope FOREIGN KEY (organization_id, project_id, classification, calibration_input_scope_id, calibration_input_scope_revision_id)
            REFERENCES statistics.calibration_input_scope_revision (organization_id, project_id, classification, aggregate_id, id) ON DELETE RESTRICT,
          CONSTRAINT fk_mdl_voce_plan_state FOREIGN KEY (organization_id, project_id, classification, material_state_id, material_state_revision_id)
            REFERENCES catalog.material_state_revision (organization_id, project_id, classification, aggregate_id, id) ON DELETE RESTRICT,
          CONSTRAINT fk_mdl_voce_plan_properties FOREIGN KEY (organization_id, project_id, classification, property_set_id, property_set_revision_id)
            REFERENCES catalog.property_set_revision (organization_id, project_id, classification, aggregate_id, id) ON DELETE RESTRICT
        )
        """
    )
    op.execute(
        """
        ALTER TABLE modeling.voce_calibration_plan ADD CONSTRAINT fk_mdl_voce_plan_current
        FOREIGN KEY (organization_id, project_id, id, current_revision_id)
        REFERENCES modeling.voce_calibration_plan_revision (organization_id, project_id, aggregate_id, id)
        ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED
        """
    )
    op.execute(
        """
        CREATE TABLE modeling.voce_calibration_run (
          id uuid NOT NULL, organization_id uuid NOT NULL, project_id uuid NOT NULL,
          classification varchar(64) NOT NULL, plan_id uuid NOT NULL, plan_revision_id uuid NOT NULL,
          calibration_input_scope_id uuid NOT NULL, calibration_input_scope_revision_id uuid NOT NULL,
          property_set_id uuid NOT NULL, property_set_revision_id uuid NOT NULL,
          source_curve_count smallint NOT NULL, execution_mode varchar(64) NOT NULL,
          reproducibility_level varchar(16) NOT NULL, environment_digest char(64) COLLATE "C" NOT NULL,
          status varchar(16) NOT NULL, attempt_count smallint NOT NULL, candidate_count smallint NOT NULL,
          failure_code varchar(100) NULL, change_reason text NOT NULL, started_at timestamptz NOT NULL,
          ended_at timestamptz NULL, created_by uuid NOT NULL, request_id uuid NOT NULL,
          trace_id varchar(255) NOT NULL,
          CONSTRAINT pk_mdl_voce_run PRIMARY KEY (organization_id, project_id, id),
          CONSTRAINT uq_mdl_voce_run_scoped UNIQUE (organization_id, project_id, classification, id),
          CONSTRAINT ck_mdl_voce_run_shape CHECK (
            source_curve_count BETWEEN 2 AND 50 AND attempt_count BETWEEN 1 AND 16
            AND candidate_count BETWEEN 0 AND attempt_count
            AND execution_mode = 'reference_inline_scipy' AND reproducibility_level = 'R3'
            AND environment_digest ~ '^[0-9a-f]{64}$' AND length(btrim(change_reason)) BETWEEN 1 AND 2000
            AND ((status = 'executing' AND failure_code IS NULL AND ended_at IS NULL)
              OR (status = 'succeeded' AND candidate_count = attempt_count AND failure_code IS NULL AND ended_at IS NOT NULL)
              OR (status = 'failed' AND failure_code ~ '^[a-z][a-z0-9_]{0,99}$' AND ended_at IS NOT NULL))),
          CONSTRAINT fk_mdl_voce_run_plan FOREIGN KEY (organization_id, project_id, classification, plan_id, plan_revision_id)
            REFERENCES modeling.voce_calibration_plan_revision (organization_id, project_id, classification, aggregate_id, id) ON DELETE RESTRICT,
          CONSTRAINT fk_mdl_voce_run_scope FOREIGN KEY (organization_id, project_id, classification, calibration_input_scope_id, calibration_input_scope_revision_id)
            REFERENCES statistics.calibration_input_scope_revision (organization_id, project_id, classification, aggregate_id, id) ON DELETE RESTRICT,
          CONSTRAINT fk_mdl_voce_run_properties FOREIGN KEY (organization_id, project_id, classification, property_set_id, property_set_revision_id)
            REFERENCES catalog.property_set_revision (organization_id, project_id, classification, aggregate_id, id) ON DELETE RESTRICT
        )
        """
    )
    op.execute(
        """
        CREATE TABLE modeling.voce_calibration_attempt (
          id uuid NOT NULL, organization_id uuid NOT NULL, project_id uuid NOT NULL,
          classification varchar(64) NOT NULL, calibration_run_id uuid NOT NULL,
          attempt_ordinal smallint NOT NULL, initial_sigma_0_pa float8 NOT NULL,
          initial_q_pa float8 NOT NULL, initial_b float8 NOT NULL, random_seed bigint NOT NULL,
          status varchar(16) NOT NULL, candidate_id uuid NULL, failure_code varchar(100) NULL,
          started_at timestamptz NOT NULL, ended_at timestamptz NULL,
          CONSTRAINT pk_mdl_voce_attempt PRIMARY KEY (organization_id, project_id, id),
          CONSTRAINT uq_mdl_voce_attempt_scoped UNIQUE (organization_id, project_id, classification, id),
          CONSTRAINT uq_mdl_voce_attempt_ordinal UNIQUE (organization_id, project_id, classification, calibration_run_id, attempt_ordinal),
          CONSTRAINT uq_mdl_voce_attempt_ref UNIQUE (organization_id, project_id, classification, id, calibration_run_id, attempt_ordinal),
          CONSTRAINT ck_mdl_voce_attempt_shape CHECK (
            attempt_ordinal BETWEEN 1 AND 16 AND initial_sigma_0_pa > 0 AND initial_q_pa > 0
            AND initial_b > 0 AND random_seed >= 0
            AND ((status = 'executing' AND candidate_id IS NULL AND failure_code IS NULL AND ended_at IS NULL)
              OR (status = 'succeeded' AND candidate_id IS NOT NULL AND failure_code IS NULL AND ended_at IS NOT NULL)
              OR (status = 'failed' AND candidate_id IS NULL AND failure_code ~ '^[a-z][a-z0-9_]{0,99}$' AND ended_at IS NOT NULL))),
          CONSTRAINT fk_mdl_voce_attempt_run FOREIGN KEY (organization_id, project_id, classification, calibration_run_id)
            REFERENCES modeling.voce_calibration_run (organization_id, project_id, classification, id) ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED
        )
        """
    )
    op.execute(
        """
        CREATE TABLE modeling.voce_calibration_candidate (
          id uuid NOT NULL, organization_id uuid NOT NULL, project_id uuid NOT NULL,
          classification varchar(64) NOT NULL, calibration_run_id uuid NOT NULL,
          calibration_attempt_id uuid NOT NULL, attempt_ordinal smallint NOT NULL,
          status varchar(16) NOT NULL, candidate_sha256 char(64) COLLATE "C" NOT NULL,
          sigma_0_pa float8 NOT NULL, q_pa float8 NOT NULL, b float8 NOT NULL,
          objective_total float8 NOT NULL, residual_root_mean_square_pa float8 NOT NULL,
          residual_mean_pa float8 NOT NULL, sigma_0_at_bound boolean NOT NULL,
          q_at_bound boolean NOT NULL, b_at_bound boolean NOT NULL,
          convergence_status_code smallint NOT NULL, convergence_reason varchar(255) NOT NULL,
          function_evaluations integer NOT NULL, jacobian_evaluations integer NULL,
          optimality float8 NOT NULL, warning_at_bound boolean NOT NULL,
          warning_nonconvergence boolean NOT NULL, identifiability_status varchar(100) NOT NULL,
          uncertainty_status varchar(100) NOT NULL, diagnostics_artifact_id uuid NOT NULL,
          diagnostics_sha256 char(64) COLLATE "C" NOT NULL, diagnostics_point_count integer NOT NULL,
          created_at timestamptz NOT NULL, created_by uuid NOT NULL,
          CONSTRAINT pk_mdl_voce_candidate PRIMARY KEY (organization_id, project_id, id),
          CONSTRAINT uq_mdl_voce_candidate_scoped UNIQUE (organization_id, project_id, classification, id),
          CONSTRAINT uq_mdl_voce_candidate_attempt UNIQUE (organization_id, project_id, classification, calibration_attempt_id),
          CONSTRAINT uq_mdl_voce_candidate_ordinal UNIQUE (organization_id, project_id, classification, calibration_run_id, attempt_ordinal),
          CONSTRAINT uq_mdl_voce_candidate_ref UNIQUE (organization_id, project_id, classification, id, calibration_run_id, calibration_attempt_id, attempt_ordinal),
          CONSTRAINT ck_mdl_voce_candidate_shape CHECK (
            status IN ('converged', 'nonconverged') AND candidate_sha256 ~ '^[0-9a-f]{64}$'
            AND diagnostics_sha256 ~ '^[0-9a-f]{64}$' AND sigma_0_pa > 0 AND q_pa > 0 AND b > 0
            AND objective_total >= 0 AND residual_root_mean_square_pa >= 0
            AND residual_mean_pa > '-Infinity'::float8 AND residual_mean_pa < 'Infinity'::float8
            AND function_evaluations > 0 AND (jacobian_evaluations IS NULL OR jacobian_evaluations > 0)
            AND optimality >= 0 AND diagnostics_point_count >= 6
            AND warning_at_bound = (sigma_0_at_bound OR q_at_bound OR b_at_bound)
            AND warning_nonconvergence = (status = 'nonconverged')),
          CONSTRAINT fk_mdl_voce_candidate_run FOREIGN KEY (organization_id, project_id, classification, calibration_run_id)
            REFERENCES modeling.voce_calibration_run (organization_id, project_id, classification, id) ON DELETE RESTRICT,
          CONSTRAINT fk_mdl_voce_candidate_attempt FOREIGN KEY (organization_id, project_id, classification, calibration_attempt_id, calibration_run_id, attempt_ordinal)
            REFERENCES modeling.voce_calibration_attempt (organization_id, project_id, classification, id, calibration_run_id, attempt_ordinal) ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_mdl_voce_candidate_artifact FOREIGN KEY (organization_id, project_id, classification, diagnostics_artifact_id)
            REFERENCES artifact.artifact (organization_id, project_id, classification, id) ON DELETE RESTRICT
        )
        """
    )
    op.execute(
        """
        ALTER TABLE modeling.voce_calibration_attempt ADD CONSTRAINT fk_mdl_voce_attempt_candidate
        FOREIGN KEY (organization_id, project_id, classification, candidate_id, calibration_run_id, id, attempt_ordinal)
        REFERENCES modeling.voce_calibration_candidate (organization_id, project_id, classification, id, calibration_run_id, calibration_attempt_id, attempt_ordinal)
        ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED
        """
    )
    op.execute(
        """
        CREATE TABLE modeling.voce_calibration_objective_term (
          organization_id uuid NOT NULL, project_id uuid NOT NULL,
          classification varchar(64) NOT NULL, candidate_id uuid NOT NULL,
          member_ordinal smallint NOT NULL, dataset_id uuid NOT NULL, dataset_revision_id uuid NOT NULL,
          point_count integer NOT NULL, mean_normalized_squared_residual float8 NOT NULL,
          CONSTRAINT pk_mdl_voce_term PRIMARY KEY (organization_id, project_id, candidate_id, member_ordinal),
          CONSTRAINT uq_mdl_voce_term_dataset UNIQUE (organization_id, project_id, candidate_id, dataset_revision_id),
          CONSTRAINT ck_mdl_voce_term_shape CHECK (member_ordinal BETWEEN 0 AND 49 AND point_count >= 3 AND mean_normalized_squared_residual >= 0),
          CONSTRAINT fk_mdl_voce_term_candidate FOREIGN KEY (organization_id, project_id, classification, candidate_id)
            REFERENCES modeling.voce_calibration_candidate (organization_id, project_id, classification, id) ON DELETE RESTRICT,
          CONSTRAINT fk_mdl_voce_term_dataset FOREIGN KEY (organization_id, project_id, classification, dataset_id, dataset_revision_id)
            REFERENCES datasets.dataset_revision (organization_id, project_id, classification, aggregate_id, id) ON DELETE RESTRICT
        )
        """
    )
    for table in (
        "voce_calibration_plan", "voce_calibration_plan_revision", "voce_calibration_run",
        "voce_calibration_attempt", "voce_calibration_candidate", "voce_calibration_objective_term",
    ):
        _secure(table, update=table in {"voce_calibration_plan", "voce_calibration_run", "voce_calibration_attempt"})
    op.execute("CREATE TRIGGER modeling_voce_plan_head BEFORE UPDATE OR DELETE ON modeling.voce_calibration_plan FOR EACH ROW EXECUTE FUNCTION revisioning.guard_identity_head_update()")
    for table in ("voce_calibration_plan_revision", "voce_calibration_candidate", "voce_calibration_objective_term"):
        op.execute(f"CREATE TRIGGER modeling_{table}_immutable BEFORE UPDATE OR DELETE ON modeling.{table} FOR EACH ROW EXECUTE FUNCTION revisioning.reject_immutable_row_mutation()")
    op.create_index("ix_mdl_voce_plan_scope", "voce_calibration_plan_revision", ["organization_id", "project_id", "calibration_input_scope_revision_id"], schema="modeling")
    op.create_index("ix_mdl_voce_run_plan", "voce_calibration_run", ["organization_id", "project_id", "plan_revision_id"], schema="modeling")
    op.create_index("ix_mdl_voce_candidate_run", "voce_calibration_candidate", ["organization_id", "project_id", "calibration_run_id", "objective_total"], schema="modeling")
    op.create_index("ix_mdl_voce_term_dataset", "voce_calibration_objective_term", ["organization_id", "project_id", "dataset_revision_id"], schema="modeling")


def downgrade() -> None:
    op.execute("ALTER TABLE modeling.voce_calibration_plan DROP CONSTRAINT IF EXISTS fk_mdl_voce_plan_current")
    for table in (
        "voce_calibration_objective_term", "voce_calibration_candidate", "voce_calibration_attempt",
        "voce_calibration_run", "voce_calibration_plan_revision", "voce_calibration_plan",
    ):
        op.execute(f"DROP TABLE IF EXISTS modeling.{table} CASCADE")

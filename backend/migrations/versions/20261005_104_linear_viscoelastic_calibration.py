"""Governed linear-viscoelastic calibration persistence.

The aggregate is intentionally separate from Common Processing and from the bounded
reference-Prony tables.  Numerical arrays remain T-10 Artifact payloads; these tables
store typed immutable references, scalar diagnostics, and the execution ledger.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261005_104_lve_calibration"
down_revision: str | None = "20261004_103_issue342_json"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PRONY_FAMILY = "urn:cmp:reference:isotropic-linear-viscoelastic-prony:1.0.0"
_CALIBRATED_PRONY_DIGEST = "f4dcd044bd497fe9adccce2921f95a2c02e4ddcec3ccd50374e6e2abcbba5248"
_FAMILY_DIGESTS = (
    (
        "urn:cmp:reference:isotropic-linear-elasticity:1.0.0",
        "a4e39b23b5d656abb50399b1ae76b799e01872f4f6ebe44a59bc8c901b622cd6",
    ),
    (
        "urn:cmp:reference:isotropic-tabulated-plasticity:1.0.0",
        "18fd736897f26e6472443a5acf50bf899f8eb8f510ae0eca80dada81047a706f",
    ),
    (
        "urn:cmp:reference:isotropic-tabulated-plasticity:1.1.0",
        "60174f00940a5e371613f941649a61af20714b5664b8b95672e34e1a718251bd",
    ),
    (
        "urn:cmp:reference:isotropic-tabulated-plasticity:1.2.0",
        "60f4a0806126ccf7c918f664a97b4d49da593f1da9dacab4a843987b34a0c62f",
    ),
    (_PRONY_FAMILY, "84f948444441bf8ead0c3e3a067d78a68335f2160c6d8d5c59348250ff492353"),
    (
        "urn:cmp:reference:ogden-prony-hyperviscoelastic:1.0.0",
        "545ef081fd6b702d99710aa2ba1a253d0ef6961b8084647d157fac03cca29f2f",
    ),
    (_PRONY_FAMILY, "16c70b294290c62d97e7eb42c5af56a4663af19c2b2e139d2fee898f1802889e"),
    (_PRONY_FAMILY, "705e6ca117a42552727b50fb7c0999bb22e4a13c1f1a31ec4afd10d10c248732"),
    (
        "urn:cmp:reference:isotropic-tabulated-plasticity:1.2.0",
        "e99bdd86790a81d2afeca9865bea3747fe5e2ab3001056c1079e7f49f7e16fc5",
    ),
)


def _replace_family_digest_constraint(*, include_calibration: bool) -> None:
    values = list(_FAMILY_DIGESTS)
    if include_calibration:
        values.append((_PRONY_FAMILY, _CALIBRATED_PRONY_DIGEST))
    clauses = " OR ".join(
        f"(model_family_id='{family}' AND model_schema_digest='{digest}')"
        for family, digest in values
    )
    op.execute(
        "ALTER TABLE modeling.material_model_revision "
        "DROP CONSTRAINT ck_modeling_material_model_family_digest, "
        f"ADD CONSTRAINT ck_modeling_material_model_family_digest CHECK ({clauses})"
    )


def _replace_promotion_kind_constraint(*, include_calibration: bool) -> None:
    values = "'manual','candidate_selection','processing_output'"
    if include_calibration:
        values += ",'calibration_selection'"
    op.execute(
        "ALTER TABLE modeling.linear_viscoelastic_revision "
        "DROP CONSTRAINT ck_modeling_linear_viscoelastic_promotion_kind, "
        "ADD CONSTRAINT ck_modeling_linear_viscoelastic_promotion_kind "
        f"CHECK (promotion_kind IN ({values}))"
    )


def _replace_evidence_constraints(*, include_calibration: bool) -> None:
    kinds = (
        "'manual_catalog_projection','reference_candidate_selection',"
        "'reference_prony_candidate_selection','reference_ogden_candidate_selection',"
        "'processing_recipe_selection'"
    )
    null_evidence_kinds = (
        "'manual_catalog_projection','reference_ogden_candidate_selection',"
        "'processing_recipe_selection'"
    )
    if include_calibration:
        kinds += ",'linear_viscoelastic_calibration_selection'"
        null_evidence_kinds += ",'linear_viscoelastic_calibration_selection'"
    all_legacy_null = """
      calibration_selection_id IS NULL AND calibration_selection_revision_id IS NULL
      AND calibration_run_id IS NULL AND calibration_candidate_id IS NULL
      AND calibration_candidate_sha256 IS NULL
      AND calibration_diagnostics_artifact_id IS NULL
      AND calibration_diagnostics_sha256 IS NULL
      AND prony_selection_id IS NULL AND prony_selection_revision_id IS NULL
      AND prony_calibration_run_id IS NULL AND prony_calibration_candidate_id IS NULL
      AND prony_calibration_candidate_sha256 IS NULL
      AND prony_diagnostics_artifact_id IS NULL AND prony_diagnostics_sha256 IS NULL
    """
    op.execute(
        "ALTER TABLE modeling.material_model_revision "
        "DROP CONSTRAINT ck_modeling_material_model_calibration_evidence_shape, "
        "DROP CONSTRAINT ck_modeling_material_model_calibration_evidence_kind"
    )
    op.execute(
        f"""
        ALTER TABLE modeling.material_model_revision
          ADD CONSTRAINT ck_modeling_material_model_calibration_evidence_kind CHECK
            (calibration_evidence_kind IN ({kinds})),
          ADD CONSTRAINT ck_modeling_material_model_calibration_evidence_shape CHECK (
            ((calibration_evidence_kind IN ({null_evidence_kinds}))
             AND {all_legacy_null})
            OR (calibration_evidence_kind='reference_candidate_selection'
             AND calibration_selection_id IS NOT NULL
             AND calibration_selection_revision_id IS NOT NULL
             AND calibration_run_id IS NOT NULL AND calibration_candidate_id IS NOT NULL
             AND calibration_candidate_sha256 ~ '^[0-9a-f]{{64}}$'
             AND calibration_diagnostics_artifact_id IS NOT NULL
             AND calibration_diagnostics_sha256 ~ '^[0-9a-f]{{64}}$'
             AND prony_selection_id IS NULL AND prony_selection_revision_id IS NULL
             AND prony_calibration_run_id IS NULL AND prony_calibration_candidate_id IS NULL
             AND prony_calibration_candidate_sha256 IS NULL
             AND prony_diagnostics_artifact_id IS NULL AND prony_diagnostics_sha256 IS NULL)
            OR (calibration_evidence_kind='reference_prony_candidate_selection'
             AND calibration_selection_id IS NULL
             AND calibration_selection_revision_id IS NULL
             AND calibration_run_id IS NULL AND calibration_candidate_id IS NULL
             AND calibration_candidate_sha256 IS NULL
             AND calibration_diagnostics_artifact_id IS NULL
             AND calibration_diagnostics_sha256 IS NULL
             AND prony_selection_id IS NOT NULL AND prony_selection_revision_id IS NOT NULL
             AND prony_calibration_run_id IS NOT NULL
             AND prony_calibration_candidate_id IS NOT NULL
             AND prony_calibration_candidate_sha256 ~ '^[0-9a-f]{{64}}$'
             AND prony_diagnostics_artifact_id IS NOT NULL
             AND prony_diagnostics_sha256 ~ '^[0-9a-f]{{64}}$'))
        """
    )


def _rls(table: str, write_permission: str) -> None:
    op.execute(f"ALTER TABLE modeling.{table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE modeling.{table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY modeling_{table}_read ON modeling.{table} FOR SELECT USING "
        "(access_control.can_access_row("
        "organization_id, project_id, classification, 'modeling.read'))"
    )
    op.execute(
        f"CREATE POLICY modeling_{table}_write ON modeling.{table} FOR INSERT WITH CHECK "
        f"(access_control.can_access_row("
        f"organization_id, project_id, classification, '{write_permission}'))"
    )
    op.execute(
        f"CREATE POLICY modeling_{table}_update ON modeling.{table} FOR UPDATE USING "
        f"(access_control.can_access_row("
        f"organization_id, project_id, classification, '{write_permission}')) "
        f"WITH CHECK (access_control.can_access_row("
        f"organization_id, project_id, classification, '{write_permission}'))"
    )


def _immutable(table: str, function_name: str) -> None:
    op.execute(
        f"""
        CREATE FUNCTION modeling.{function_name}() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF TG_OP = 'DELETE' THEN
            RAISE EXCEPTION 'immutable linear viscoelastic calibration rows cannot be deleted';
          END IF;
          IF NEW IS DISTINCT FROM OLD THEN
            RAISE EXCEPTION 'immutable linear viscoelastic calibration rows cannot be changed';
          END IF;
          RETURN OLD;
        END;
        $$;
        CREATE TRIGGER trg_{table}_immutable
          BEFORE UPDATE OR DELETE ON modeling.{table}
          FOR EACH ROW EXECUTE FUNCTION modeling.{function_name}();
        """
    )


def _extend_reference_test_method_constraints() -> None:
    """Allow the persisted non-production shear-DMA reference method."""

    op.execute(
        """
        ALTER TABLE testing.test_method
          DROP CONSTRAINT ck_testing_test_method_code;
        ALTER TABLE testing.test_method_revision
          DROP CONSTRAINT ck_testing_test_method_revision_declared;
        ALTER TABLE testing.test_method
          ADD CONSTRAINT ck_testing_test_method_code CHECK
          (method_code IN (
            'reference_uniaxial_tensile',
            'reference_planar_tension',
            'reference_biaxial_tension',
            'reference_shear_relaxation',
            'reference_shear_dma_frequency_sweep'
          ));
        ALTER TABLE testing.test_method_revision
          ADD CONSTRAINT ck_testing_test_method_revision_declared CHECK
          ((method_code='reference_uniaxial_tensile' AND
            display_name='Reference uniaxial tensile CSV') OR
           (method_code='reference_planar_tension' AND
            display_name='Reference planar tension CSV') OR
           (method_code='reference_biaxial_tension' AND
            display_name='Reference biaxial tension CSV') OR
           (method_code='reference_shear_relaxation' AND
            display_name='Reference shear relaxation CSV') OR
           (method_code='reference_shear_dma_frequency_sweep' AND
            display_name='Reference shear DMA frequency sweep'));
        """
    )


def _restore_reference_test_method_constraints() -> None:
    """Restore the pre-calibration method contract without discarding new rows."""

    op.execute(
        """
        DO $$ BEGIN
          IF EXISTS (
            SELECT 1 FROM testing.test_method
            WHERE method_code='reference_shear_dma_frequency_sweep'
          ) OR EXISTS (
            SELECT 1 FROM testing.test_method_revision
            WHERE method_code='reference_shear_dma_frequency_sweep'
          ) THEN
            RAISE EXCEPTION
              'cannot downgrade Test Method constraints while DMA frequency-sweep records exist';
          END IF;
        END $$;
        ALTER TABLE testing.test_method
          DROP CONSTRAINT ck_testing_test_method_code;
        ALTER TABLE testing.test_method_revision
          DROP CONSTRAINT ck_testing_test_method_revision_declared;
        ALTER TABLE testing.test_method
          ADD CONSTRAINT ck_testing_test_method_code CHECK
          (method_code IN (
            'reference_uniaxial_tensile',
            'reference_planar_tension',
            'reference_biaxial_tension',
            'reference_shear_relaxation'
          ));
        ALTER TABLE testing.test_method_revision
          ADD CONSTRAINT ck_testing_test_method_revision_declared CHECK
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


def upgrade() -> None:
    # ``deformation_mode`` is nullable and deliberately not backfilled.  The revision
    # metadata remains the source of historical 1.0/1.1 schema identity.
    _extend_reference_test_method_constraints()
    op.execute(
        """
        ALTER TABLE datasets.import_profile_revision
          ADD COLUMN deformation_mode varchar(32),
          ADD CONSTRAINT ck_datasets_import_profile_deformation_mode
            CHECK (deformation_mode IS NULL OR deformation_mode = 'shear');

        CREATE TABLE modeling.linear_viscoelastic_calibration_plan (
          id uuid NOT NULL, organization_id uuid NOT NULL, project_id uuid NOT NULL,
          classification varchar(64) NOT NULL, current_revision_id uuid NOT NULL,
          created_at timestamptz NOT NULL, created_by uuid NOT NULL,
          updated_at timestamptz NOT NULL, idempotency_key varchar(255),
          idempotency_digest char(64),
          PRIMARY KEY (organization_id, project_id, id),
          CONSTRAINT uq_mdl_lve_plan_scope UNIQUE
            (organization_id, project_id, classification, id),
          CONSTRAINT uq_mdl_lve_plan_idempotency UNIQUE
            (organization_id, project_id, idempotency_key)
        );
        CREATE TABLE modeling.linear_viscoelastic_calibration_plan_revision (
          id uuid NOT NULL, aggregate_id uuid NOT NULL, organization_id uuid NOT NULL,
          project_id uuid NOT NULL, classification varchar(64) NOT NULL,
          revision_no bigint NOT NULL, based_on_revision_id uuid,
          schema_id varchar(255) NOT NULL,
          schema_version varchar(64) NOT NULL,
          content_hash char(64) NOT NULL CHECK (content_hash ~ '^[0-9a-f]{64}$'),
          plan_sha256 char(64) NOT NULL CHECK (plan_sha256 ~ '^[0-9a-f]{64}$'),
          test_data_id uuid NOT NULL, test_data_revision_id uuid NOT NULL,
          test_data_sha256 char(64),
          canonical_artifact_id uuid NOT NULL, canonical_artifact_sha256 char(64) NOT NULL,
          canonical_artifact_media_type varchar(255),
          normalized_artifact_id uuid NOT NULL, normalized_artifact_sha256 char(64) NOT NULL,
          normalized_artifact_media_type varchar(255),
          raw_source_sha256 char(64) NOT NULL,
          import_profile_id uuid NOT NULL, import_profile_revision_id uuid NOT NULL,
          profile_sha256 char(64) NOT NULL,
          input_semantics jsonb NOT NULL CHECK (jsonb_typeof(input_semantics) = 'object'),
          term_counts jsonb NOT NULL CHECK (jsonb_typeof(term_counts) = 'array'),
          parameter_bounds jsonb NOT NULL CHECK (jsonb_typeof(parameter_bounds) = 'object'),
          start_vectors jsonb NOT NULL CHECK (jsonb_typeof(start_vectors) = 'object'),
          objective_policy jsonb NOT NULL CHECK (jsonb_typeof(objective_policy) = 'object'),
          optimizer_policy jsonb NOT NULL CHECK (jsonb_typeof(optimizer_policy) = 'object'),
          statuses jsonb NOT NULL CHECK (jsonb_typeof(statuses) = 'object'),
          plan_payload jsonb NOT NULL CHECK (jsonb_typeof(plan_payload) = 'object'),
          created_at timestamptz NOT NULL, created_by uuid NOT NULL,
          change_reason text NOT NULL, request_id uuid NOT NULL, trace_id varchar(255) NOT NULL,
          PRIMARY KEY (organization_id, project_id, id),
          CONSTRAINT uq_mdl_lve_plan_revision_no UNIQUE
            (organization_id, project_id, aggregate_id, revision_no),
          CONSTRAINT uq_mdl_lve_plan_revision_scope UNIQUE
            (organization_id, project_id, classification, aggregate_id, id),
          CONSTRAINT fk_mdl_lve_plan_revision_identity FOREIGN KEY
            (organization_id, project_id, classification, aggregate_id)
            REFERENCES modeling.linear_viscoelastic_calibration_plan
            (organization_id, project_id, classification, id),
          CONSTRAINT ck_mdl_lve_plan_revision_schema CHECK
            (schema_id = 'urn:cmp:modeling:linear-viscoelastic-calibration-plan:1.0.0'
             AND schema_version = '1.0.0'),
          CONSTRAINT ck_mdl_lve_plan_revision_pin CHECK
            (canonical_artifact_sha256 ~ '^[0-9a-f]{64}$'
             AND normalized_artifact_sha256 ~ '^[0-9a-f]{64}$'
             AND raw_source_sha256 ~ '^[0-9a-f]{64}$'
             AND profile_sha256 ~ '^[0-9a-f]{64}$')
        );
        ALTER TABLE modeling.linear_viscoelastic_calibration_plan
          ADD CONSTRAINT fk_mdl_lve_plan_current_revision FOREIGN KEY
          (organization_id, project_id, classification, id, current_revision_id)
          REFERENCES modeling.linear_viscoelastic_calibration_plan_revision
          (organization_id, project_id, classification, aggregate_id, id)
          DEFERRABLE INITIALLY DEFERRED;

        CREATE TABLE modeling.linear_viscoelastic_calibration_run (
          id uuid NOT NULL, organization_id uuid NOT NULL, project_id uuid NOT NULL,
          classification varchar(64) NOT NULL, plan_id uuid NOT NULL,
          plan_revision_id uuid NOT NULL, plan_sha256 char(64) NOT NULL, job_id uuid NOT NULL,
          status varchar(32) NOT NULL CHECK
            (status IN ('queued','running','succeeded','failed','retrying')),
          terminal_digest char(64), execution_ledger_sha256 char(64),
          failure_code varchar(100), failure_detail text, recovery_hint varchar(1000),
          recommendation_id uuid, idempotency_key varchar(255) NOT NULL,
          request_sha256 char(64) NOT NULL, result_payload jsonb,
          started_at timestamptz NOT NULL,
          finished_at timestamptz, created_at timestamptz NOT NULL, created_by uuid NOT NULL,
          request_id uuid NOT NULL, trace_id varchar(255) NOT NULL,
          PRIMARY KEY (organization_id, project_id, id),
          CONSTRAINT uq_mdl_lve_run_scope UNIQUE
            (organization_id, project_id, classification, id),
          CONSTRAINT uq_mdl_lve_run_idempotency UNIQUE
            (organization_id, project_id, idempotency_key),
          CONSTRAINT fk_mdl_lve_run_plan FOREIGN KEY
            (organization_id, project_id, classification, plan_id, plan_revision_id)
            REFERENCES modeling.linear_viscoelastic_calibration_plan_revision
            (organization_id, project_id, classification, aggregate_id, id),
          CONSTRAINT ck_mdl_lve_run_digests CHECK
            (plan_sha256 ~ '^[0-9a-f]{64}$' AND request_sha256 ~ '^[0-9a-f]{64}$'
             AND (terminal_digest IS NULL OR terminal_digest ~ '^[0-9a-f]{64}$')
             AND (execution_ledger_sha256 IS NULL OR execution_ledger_sha256 ~ '^[0-9a-f]{64}$')),
          CONSTRAINT ck_mdl_lve_run_failure CHECK
            ((status IN ('queued','running','retrying') AND finished_at IS NULL)
             OR (status IN ('succeeded','failed') AND finished_at IS NOT NULL)),
          CONSTRAINT ck_mdl_lve_run_time CHECK (finished_at IS NULL OR finished_at >= started_at)
        );

        CREATE TABLE modeling.linear_viscoelastic_calibration_execution_attempt (
          id uuid NOT NULL, organization_id uuid NOT NULL, project_id uuid NOT NULL,
          classification varchar(64) NOT NULL, run_id uuid NOT NULL,
          job_id uuid NOT NULL, job_attempt_no integer NOT NULL CHECK (job_attempt_no >= 1),
          state varchar(32) NOT NULL CHECK
            (state IN ('claimed','running','succeeded','failed','cancelled','timed_out')),
          failure_code varchar(100), failure_detail text, recovery_hint varchar(1000),
          package_id varchar(255) NOT NULL, package_version varchar(64) NOT NULL,
          package_sha256 char(64) NOT NULL, submitted_at timestamptz NOT NULL,
          deadline_at timestamptz NOT NULL, claimed_at timestamptz, finished_at timestamptz,
          result_manifest_artifact_id uuid, result_manifest_sha256 char(64),
          created_at timestamptz NOT NULL, created_by uuid NOT NULL,
          PRIMARY KEY (organization_id, project_id, id),
          CONSTRAINT uq_mdl_lve_execution_run_attempt UNIQUE
            (organization_id, project_id, run_id, job_attempt_no),
          CONSTRAINT uq_mdl_lve_execution_scope UNIQUE
            (organization_id, project_id, classification, id),
          CONSTRAINT fk_mdl_lve_execution_run FOREIGN KEY
            (organization_id, project_id, classification, run_id)
            REFERENCES modeling.linear_viscoelastic_calibration_run
            (organization_id, project_id, classification, id),
          CONSTRAINT ck_mdl_lve_execution_package_sha CHECK (package_sha256 ~ '^[0-9a-f]{64}$')
        );

        CREATE TABLE modeling.linear_viscoelastic_calibration_numerical_attempt (
          id uuid NOT NULL, organization_id uuid NOT NULL, project_id uuid NOT NULL,
          classification varchar(64) NOT NULL, run_id uuid NOT NULL,
          execution_attempt_id uuid NOT NULL, ordinal integer NOT NULL CHECK (ordinal >= 1),
          term_count integer NOT NULL CHECK (term_count BETWEEN 1 AND 10),
          start_vector jsonb NOT NULL CHECK (jsonb_typeof(start_vector) = 'array'),
          transformed_start_vector jsonb NOT NULL CHECK
            (jsonb_typeof(transformed_start_vector) = 'array'),
          status integer NOT NULL, optimizer_message text NOT NULL, nfev integer NOT NULL,
          cost double precision NOT NULL, optimality double precision NOT NULL,
          active_mask jsonb NOT NULL CHECK (jsonb_typeof(active_mask) = 'array'),
          physical_parameters jsonb NOT NULL CHECK (jsonb_typeof(physical_parameters) = 'array'),
          transformed_parameters jsonb NOT NULL CHECK
            (jsonb_typeof(transformed_parameters) = 'array'),
          residuals_artifact_id uuid, objective_history_artifact_id uuid,
          residuals jsonb NOT NULL CHECK (jsonb_typeof(residuals) = 'array'),
          rank_sigma_max double precision NOT NULL, rank_threshold double precision NOT NULL,
          rank_status varchar(32) NOT NULL, rank_warning_code varchar(100),
          objective_history jsonb NOT NULL CHECK (jsonb_typeof(objective_history) = 'array'),
          rss double precision NOT NULL, rank integer NOT NULL,
          singular_values jsonb NOT NULL CHECK (jsonb_typeof(singular_values) = 'array'),
          warning_codes jsonb NOT NULL CHECK (jsonb_typeof(warning_codes) = 'array'),
          converged boolean NOT NULL, physical boolean NOT NULL,
          created_at timestamptz NOT NULL, created_by uuid NOT NULL,
          PRIMARY KEY (organization_id, project_id, id),
          CONSTRAINT uq_mdl_lve_numerical_attempt_ordinal UNIQUE
            (organization_id, project_id, run_id, ordinal),
          CONSTRAINT uq_mdl_lve_numerical_attempt_scope UNIQUE
            (organization_id, project_id, classification, id),
          CONSTRAINT fk_mdl_lve_numerical_run FOREIGN KEY
            (organization_id, project_id, classification, run_id)
            REFERENCES modeling.linear_viscoelastic_calibration_run
            (organization_id, project_id, classification, id),
          CONSTRAINT fk_mdl_lve_numerical_execution FOREIGN KEY
            (organization_id, project_id, classification, execution_attempt_id)
            REFERENCES modeling.linear_viscoelastic_calibration_execution_attempt
            (organization_id, project_id, classification, id)
        );

        CREATE TABLE modeling.linear_viscoelastic_calibration_candidate (
          id uuid NOT NULL, organization_id uuid NOT NULL, project_id uuid NOT NULL,
          classification varchar(64) NOT NULL, run_id uuid NOT NULL,
          numerical_attempt_id uuid NOT NULL, attempt_ordinal integer NOT NULL,
          term_count integer NOT NULL CHECK (term_count BETWEEN 1 AND 10),
          candidate_sha256 char(64) NOT NULL, physical_parameters jsonb NOT NULL,
          transformed_parameters jsonb NOT NULL, rss double precision NOT NULL,
          bic double precision NOT NULL, calibration_residuals_artifact_id uuid NOT NULL,
          holdout_residuals_artifact_id uuid,
          calibration_residuals jsonb NOT NULL CHECK
            (jsonb_typeof(calibration_residuals) = 'array'),
          holdout_residuals jsonb NOT NULL CHECK (jsonb_typeof(holdout_residuals) = 'array'),
          rank integer NOT NULL,
          singular_values jsonb NOT NULL CHECK (jsonb_typeof(singular_values) = 'array'),
          rank_sigma_max double precision NOT NULL, rank_threshold double precision NOT NULL,
          rank_status varchar(32) NOT NULL, rank_warning_code varchar(100),
          warning_codes jsonb NOT NULL CHECK (jsonb_typeof(warning_codes) = 'array'),
          uncertainty_status varchar(32) NOT NULL CHECK (uncertainty_status = 'NOT_PROVIDED'),
          created_at timestamptz NOT NULL, created_by uuid NOT NULL,
          PRIMARY KEY (organization_id, project_id, id),
          CONSTRAINT uq_mdl_lve_candidate_run_ordinal UNIQUE
            (organization_id, project_id, run_id, attempt_ordinal),
          CONSTRAINT uq_mdl_lve_candidate_scope UNIQUE
            (organization_id, project_id, classification, id),
          CONSTRAINT fk_mdl_lve_candidate_run FOREIGN KEY
            (organization_id, project_id, classification, run_id)
            REFERENCES modeling.linear_viscoelastic_calibration_run
            (organization_id, project_id, classification, id),
          CONSTRAINT fk_mdl_lve_candidate_attempt FOREIGN KEY
            (organization_id, project_id, classification, numerical_attempt_id)
            REFERENCES modeling.linear_viscoelastic_calibration_numerical_attempt
            (organization_id, project_id, classification, id),
          CONSTRAINT ck_mdl_lve_candidate_sha CHECK (candidate_sha256 ~ '^[0-9a-f]{64}$')
        );

        CREATE TABLE modeling.linear_viscoelastic_calibration_recommendation (
          id uuid NOT NULL, organization_id uuid NOT NULL, project_id uuid NOT NULL,
          classification varchar(64) NOT NULL, run_id uuid NOT NULL,
          candidate_id uuid NOT NULL, candidate_sha256 char(64) NOT NULL,
          recommendation_sha256 char(64) NOT NULL,
          rule_version varchar(100) NOT NULL CHECK (rule_version = 'linear_viscoelastic_bic@1.0.0'),
          created_at timestamptz NOT NULL, created_by uuid NOT NULL,
          PRIMARY KEY (organization_id, project_id, id),
          CONSTRAINT uq_mdl_lve_recommendation_scope UNIQUE
            (organization_id, project_id, classification, id),
          CONSTRAINT uq_mdl_lve_recommendation_run UNIQUE
            (organization_id, project_id, run_id),
          CONSTRAINT fk_mdl_lve_recommendation_run FOREIGN KEY
            (organization_id, project_id, classification, run_id)
            REFERENCES modeling.linear_viscoelastic_calibration_run
            (organization_id, project_id, classification, id),
          CONSTRAINT fk_mdl_lve_recommendation_candidate FOREIGN KEY
            (organization_id, project_id, classification, candidate_id)
            REFERENCES modeling.linear_viscoelastic_calibration_candidate
            (organization_id, project_id, classification, id),
          CONSTRAINT ck_mdl_lve_recommendation_sha CHECK
            (candidate_sha256 ~ '^[0-9a-f]{64}$'
             AND recommendation_sha256 ~ '^[0-9a-f]{64}$')
        );

        CREATE TABLE modeling.linear_viscoelastic_calibration_selection (
          id uuid NOT NULL, organization_id uuid NOT NULL, project_id uuid NOT NULL,
          classification varchar(64) NOT NULL, current_revision_id uuid NOT NULL,
          created_at timestamptz NOT NULL, created_by uuid NOT NULL,
          updated_at timestamptz NOT NULL, idempotency_key varchar(255),
          idempotency_digest char(64),
          PRIMARY KEY (organization_id, project_id, id),
          CONSTRAINT uq_mdl_lve_selection_scope UNIQUE
            (organization_id, project_id, classification, id),
          CONSTRAINT uq_mdl_lve_selection_idempotency UNIQUE
            (organization_id, project_id, idempotency_key)
        );
        CREATE TABLE modeling.linear_viscoelastic_calibration_selection_revision (
          id uuid NOT NULL, aggregate_id uuid NOT NULL, organization_id uuid NOT NULL,
          project_id uuid NOT NULL, classification varchar(64) NOT NULL,
          revision_no bigint NOT NULL, based_on_revision_id uuid,
          schema_id varchar(255) NOT NULL, schema_version varchar(64) NOT NULL,
          content_hash char(64) NOT NULL, plan_revision_id uuid NOT NULL, run_id uuid NOT NULL,
          candidate_id uuid NOT NULL, candidate_sha256 char(64) NOT NULL,
          reason text NOT NULL, warning_acknowledgements jsonb NOT NULL
            CHECK (jsonb_typeof(warning_acknowledgements) = 'array'),
          actor uuid NOT NULL, created_at timestamptz NOT NULL, created_by uuid NOT NULL,
          change_reason text NOT NULL, request_id uuid NOT NULL, trace_id varchar(255) NOT NULL,
          selection_payload jsonb NOT NULL CHECK (jsonb_typeof(selection_payload) = 'object'),
          PRIMARY KEY (organization_id, project_id, id),
          CONSTRAINT uq_mdl_lve_selection_revision_no UNIQUE
            (organization_id, project_id, aggregate_id, revision_no),
          CONSTRAINT uq_mdl_lve_selection_revision_scope UNIQUE
            (organization_id, project_id, classification, aggregate_id, id),
          CONSTRAINT fk_mdl_lve_selection_revision_identity FOREIGN KEY
            (organization_id, project_id, classification, aggregate_id)
            REFERENCES modeling.linear_viscoelastic_calibration_selection
            (organization_id, project_id, classification, id),
          CONSTRAINT fk_mdl_lve_selection_revision_run FOREIGN KEY
            (organization_id, project_id, classification, run_id)
            REFERENCES modeling.linear_viscoelastic_calibration_run
            (organization_id, project_id, classification, id),
          CONSTRAINT fk_mdl_lve_selection_revision_candidate FOREIGN KEY
            (organization_id, project_id, classification, candidate_id)
            REFERENCES modeling.linear_viscoelastic_calibration_candidate
            (organization_id, project_id, classification, id),
          CONSTRAINT ck_mdl_lve_selection_candidate_sha CHECK (candidate_sha256 ~ '^[0-9a-f]{64}$')
        );
        ALTER TABLE modeling.linear_viscoelastic_calibration_selection
          ADD CONSTRAINT fk_mdl_lve_selection_current_revision FOREIGN KEY
          (organization_id, project_id, classification, id, current_revision_id)
          REFERENCES modeling.linear_viscoelastic_calibration_selection_revision
          (organization_id, project_id, classification, aggregate_id, id)
          DEFERRABLE INITIALLY DEFERRED;
        """
    )

    _replace_family_digest_constraint(include_calibration=True)
    _replace_evidence_constraints(include_calibration=True)
    _replace_promotion_kind_constraint(include_calibration=True)
    op.execute(
        """
        CREATE TABLE modeling.linear_viscoelastic_calibration_evidence (
          organization_id uuid NOT NULL, project_id uuid NOT NULL,
          classification varchar(64) NOT NULL,
          material_model_id uuid NOT NULL, material_model_revision_id uuid NOT NULL,
          plan_id uuid NOT NULL, plan_revision_id uuid NOT NULL, plan_sha256 char(64) NOT NULL,
          run_id uuid NOT NULL, run_sha256 char(64) NOT NULL,
          candidate_id uuid NOT NULL, candidate_sha256 char(64) NOT NULL,
          selection_id uuid NOT NULL, selection_revision_id uuid NOT NULL,
          selection_sha256 char(64) NOT NULL,
          recommendation_id uuid NOT NULL, recommendation_sha256 char(64) NOT NULL,
          canonical_test_data_id uuid NOT NULL,
          canonical_test_data_revision_id uuid NOT NULL,
          canonical_test_data_sha256 char(64) NOT NULL,
          canonical_artifact_id uuid NOT NULL, canonical_artifact_sha256 char(64) NOT NULL,
          normalized_artifact_id uuid NOT NULL, normalized_artifact_sha256 char(64) NOT NULL,
          import_profile_id uuid NOT NULL, import_profile_revision_id uuid NOT NULL,
          import_profile_sha256 char(64) NOT NULL,
          PRIMARY KEY (organization_id, project_id, material_model_revision_id),
          CONSTRAINT uq_mdl_lve_calibration_evidence_scope UNIQUE
            (organization_id, project_id, classification, material_model_id,
             material_model_revision_id),
          CONSTRAINT uq_mdl_lve_calibration_evidence_selection UNIQUE
            (organization_id, project_id, selection_revision_id),
          CONSTRAINT fk_mdl_lve_calibration_evidence_model FOREIGN KEY
            (organization_id, project_id, classification, material_model_id,
             material_model_revision_id) REFERENCES modeling.material_model_revision
            (organization_id, project_id, classification, aggregate_id, id),
          CONSTRAINT fk_mdl_lve_calibration_evidence_plan FOREIGN KEY
            (organization_id, project_id, classification, plan_id, plan_revision_id)
            REFERENCES modeling.linear_viscoelastic_calibration_plan_revision
            (organization_id, project_id, classification, aggregate_id, id),
          CONSTRAINT fk_mdl_lve_calibration_evidence_run FOREIGN KEY
            (organization_id, project_id, classification, run_id)
            REFERENCES modeling.linear_viscoelastic_calibration_run
            (organization_id, project_id, classification, id),
          CONSTRAINT fk_mdl_lve_calibration_evidence_candidate FOREIGN KEY
            (organization_id, project_id, classification, candidate_id)
            REFERENCES modeling.linear_viscoelastic_calibration_candidate
            (organization_id, project_id, classification, id),
          CONSTRAINT fk_mdl_lve_calibration_evidence_selection FOREIGN KEY
            (organization_id, project_id, classification, selection_id,
             selection_revision_id)
            REFERENCES modeling.linear_viscoelastic_calibration_selection_revision
            (organization_id, project_id, classification, aggregate_id, id),
          CONSTRAINT fk_mdl_lve_calibration_evidence_recommendation FOREIGN KEY
            (organization_id, project_id, classification, recommendation_id)
            REFERENCES modeling.linear_viscoelastic_calibration_recommendation
            (organization_id, project_id, classification, id),
          CONSTRAINT ck_mdl_lve_calibration_evidence_hashes CHECK
            (plan_sha256 ~ '^[0-9a-f]{64}$' AND run_sha256 ~ '^[0-9a-f]{64}$'
             AND candidate_sha256 ~ '^[0-9a-f]{64}$'
             AND selection_sha256 ~ '^[0-9a-f]{64}$'
             AND recommendation_sha256 ~ '^[0-9a-f]{64}$'
             AND canonical_test_data_sha256 ~ '^[0-9a-f]{64}$'
             AND canonical_artifact_sha256 ~ '^[0-9a-f]{64}$'
             AND normalized_artifact_sha256 ~ '^[0-9a-f]{64}$'
             AND import_profile_sha256 ~ '^[0-9a-f]{64}$')
        );

        CREATE FUNCTION modeling.validate_linear_viscoelastic_calibration_evidence()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF NOT EXISTS (
            SELECT 1
              FROM modeling.material_model_revision m
              JOIN modeling.linear_viscoelastic_revision lv
                ON lv.organization_id=m.organization_id
               AND lv.project_id=m.project_id AND lv.classification=m.classification
               AND lv.material_model_id=m.aggregate_id
               AND lv.material_model_revision_id=m.id
              JOIN modeling.linear_viscoelastic_calibration_plan_revision p
                ON p.organization_id=NEW.organization_id AND p.project_id=NEW.project_id
               AND p.classification=NEW.classification AND p.aggregate_id=NEW.plan_id
               AND p.id=NEW.plan_revision_id
              JOIN modeling.linear_viscoelastic_calibration_run r
                ON r.organization_id=NEW.organization_id AND r.project_id=NEW.project_id
               AND r.classification=NEW.classification AND r.id=NEW.run_id
              JOIN modeling.linear_viscoelastic_calibration_candidate c
                ON c.organization_id=NEW.organization_id AND c.project_id=NEW.project_id
               AND c.classification=NEW.classification AND c.id=NEW.candidate_id
              JOIN modeling.linear_viscoelastic_calibration_selection_revision s
                ON s.organization_id=NEW.organization_id AND s.project_id=NEW.project_id
               AND s.classification=NEW.classification AND s.aggregate_id=NEW.selection_id
               AND s.id=NEW.selection_revision_id
              JOIN modeling.linear_viscoelastic_calibration_recommendation rec
                ON rec.organization_id=NEW.organization_id AND rec.project_id=NEW.project_id
               AND rec.classification=NEW.classification AND rec.id=NEW.recommendation_id
             WHERE m.organization_id=NEW.organization_id
               AND m.project_id=NEW.project_id AND m.classification=NEW.classification
               AND m.aggregate_id=NEW.material_model_id AND m.id=NEW.material_model_revision_id
               AND m.calibration_evidence_kind='linear_viscoelastic_calibration_selection'
               AND m.schema_id=
                 'urn:cmp:modeling:reference-isotropic-linear-viscoelastic-prony:1.4.0'
               AND m.schema_version='1.4.0'
               AND lv.promotion_kind='calibration_selection'
               AND p.plan_sha256=NEW.plan_sha256
               AND r.plan_id=NEW.plan_id AND r.plan_revision_id=NEW.plan_revision_id
               AND r.plan_sha256=NEW.plan_sha256 AND r.status='succeeded'
               AND r.terminal_digest=NEW.run_sha256
               AND c.run_id=NEW.run_id AND c.candidate_sha256=NEW.candidate_sha256
               AND s.plan_revision_id=NEW.plan_revision_id AND s.run_id=NEW.run_id
               AND s.candidate_id=NEW.candidate_id
               AND s.candidate_sha256=NEW.candidate_sha256
               AND s.content_hash=NEW.selection_sha256
               AND rec.run_id=NEW.run_id
               AND rec.recommendation_sha256=NEW.recommendation_sha256
               AND p.test_data_id=NEW.canonical_test_data_id
               AND p.test_data_revision_id=NEW.canonical_test_data_revision_id
               AND p.test_data_sha256=NEW.canonical_test_data_sha256
               AND p.canonical_artifact_id=NEW.canonical_artifact_id
               AND p.canonical_artifact_sha256=NEW.canonical_artifact_sha256
               AND p.normalized_artifact_id=NEW.normalized_artifact_id
               AND p.normalized_artifact_sha256=NEW.normalized_artifact_sha256
               AND p.import_profile_id=NEW.import_profile_id
               AND p.import_profile_revision_id=NEW.import_profile_revision_id
               AND p.profile_sha256=NEW.import_profile_sha256
          ) THEN
            RAISE EXCEPTION
              'linear viscoelastic IR differs from exact Plan/Run/Candidate/Selection evidence'
              USING ERRCODE='23514';
          END IF;
          RETURN NEW;
        END $$;
        CREATE CONSTRAINT TRIGGER modeling_linear_viscoelastic_calibration_evidence_validate
          AFTER INSERT ON modeling.linear_viscoelastic_calibration_evidence
          DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
          EXECUTE FUNCTION modeling.validate_linear_viscoelastic_calibration_evidence();
        """
    )

    tables = (
        "linear_viscoelastic_calibration_plan",
        "linear_viscoelastic_calibration_plan_revision",
        "linear_viscoelastic_calibration_run",
        "linear_viscoelastic_calibration_execution_attempt",
        "linear_viscoelastic_calibration_numerical_attempt",
        "linear_viscoelastic_calibration_candidate",
        "linear_viscoelastic_calibration_recommendation",
        "linear_viscoelastic_calibration_selection",
        "linear_viscoelastic_calibration_selection_revision",
        "linear_viscoelastic_calibration_evidence",
    )
    for table in tables:
        _rls(
            table,
            "modeling.write"
            if table.startswith("linear_viscoelastic_calibration_selection")
            or table == "linear_viscoelastic_calibration_evidence"
            else "calibration.execute",
        )
    for table in (
        "linear_viscoelastic_calibration_plan_revision",
        "linear_viscoelastic_calibration_numerical_attempt",
        "linear_viscoelastic_calibration_candidate",
        "linear_viscoelastic_calibration_recommendation",
        "linear_viscoelastic_calibration_selection_revision",
        "linear_viscoelastic_calibration_evidence",
    ):
        _immutable(table, f"guard_{table}_immutable")


def downgrade() -> None:
    bind = op.get_bind()
    rows_exist = bool(
        bind.execute(
            sa.text(
                "SELECT EXISTS ("
                "SELECT 1 FROM modeling.linear_viscoelastic_calibration_plan "
                "UNION ALL SELECT 1 FROM modeling.linear_viscoelastic_calibration_plan_revision "
                "UNION ALL SELECT 1 FROM modeling.linear_viscoelastic_calibration_run "
                "UNION ALL SELECT 1 FROM "
                "modeling.linear_viscoelastic_calibration_execution_attempt "
                "UNION ALL SELECT 1 FROM "
                "modeling.linear_viscoelastic_calibration_numerical_attempt "
                "UNION ALL SELECT 1 FROM modeling.linear_viscoelastic_calibration_candidate "
                "UNION ALL SELECT 1 FROM modeling.linear_viscoelastic_calibration_recommendation "
                "UNION ALL SELECT 1 FROM modeling.linear_viscoelastic_calibration_selection "
                "UNION ALL SELECT 1 FROM "
                "modeling.linear_viscoelastic_calibration_selection_revision "
                "UNION ALL SELECT 1 FROM "
                "modeling.linear_viscoelastic_calibration_evidence"
                ")"
            )
        ).scalar()
    )
    profile_mode_exists = bool(
        bind.execute(
            sa.text(
                "SELECT EXISTS (SELECT 1 FROM datasets.import_profile_revision "
                "WHERE schema_version = '1.2.0' OR deformation_mode IS NOT NULL)"
            )
        ).scalar()
    )
    if rows_exist:
        raise RuntimeError(
            "cannot downgrade linear-viscoelastic calibration while calibration rows exist"
        )
    if profile_mode_exists:
        raise RuntimeError(
            "cannot downgrade governed Import Profile while schema 1.2/mode evidence exists"
        )
    _restore_reference_test_method_constraints()

    # Plan and Selection each have an immutable aggregate row and a current
    # revision pointer, so PostgreSQL sees a two-way FK cycle.  Remove those
    # pointers before dropping either side of the cycle.
    op.execute(
        "DROP TABLE modeling.linear_viscoelastic_calibration_evidence; "
        "DROP FUNCTION modeling.guard_linear_viscoelastic_calibration_evidence_immutable(); "
        "DROP FUNCTION modeling.validate_linear_viscoelastic_calibration_evidence()"
    )
    for constraint, table in (
        (
            "fk_mdl_lve_plan_current_revision",
            "linear_viscoelastic_calibration_plan",
        ),
        (
            "fk_mdl_lve_plan_revision_identity",
            "linear_viscoelastic_calibration_plan_revision",
        ),
        (
            "fk_mdl_lve_selection_current_revision",
            "linear_viscoelastic_calibration_selection",
        ),
        (
            "fk_mdl_lve_selection_revision_identity",
            "linear_viscoelastic_calibration_selection_revision",
        ),
    ):
        op.drop_constraint(constraint, table, schema="modeling", type_="foreignkey")

    for table in (
        "linear_viscoelastic_calibration_selection",
        "linear_viscoelastic_calibration_selection_revision",
        "linear_viscoelastic_calibration_recommendation",
        "linear_viscoelastic_calibration_candidate",
        "linear_viscoelastic_calibration_numerical_attempt",
        "linear_viscoelastic_calibration_execution_attempt",
        "linear_viscoelastic_calibration_run",
        "linear_viscoelastic_calibration_plan",
        "linear_viscoelastic_calibration_plan_revision",
    ):
        op.drop_table(table, schema="modeling")

    for table in (
        "linear_viscoelastic_calibration_plan_revision",
        "linear_viscoelastic_calibration_numerical_attempt",
        "linear_viscoelastic_calibration_candidate",
        "linear_viscoelastic_calibration_recommendation",
        "linear_viscoelastic_calibration_selection_revision",
    ):
        function_name = f"guard_{table}_immutable"
        op.execute(
            sa.text(
                "DROP FUNCTION IF EXISTS modeling."
                + function_name
                + "()"
            )
        )
    _replace_promotion_kind_constraint(include_calibration=False)
    _replace_evidence_constraints(include_calibration=False)
    _replace_family_digest_constraint(include_calibration=False)
    op.drop_constraint(
        "ck_datasets_import_profile_deformation_mode",
        "import_profile_revision",
        schema="datasets",
        type_="check",
    )
    op.drop_column("import_profile_revision", "deformation_mode", schema="datasets")

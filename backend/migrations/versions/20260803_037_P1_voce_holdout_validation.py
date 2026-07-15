"""Add solver-independent reference Voce holdout validation.

Revision ID: 20260803_037_p1
Revises: 20260802_036_p1
"""

# ruff: noqa: E501

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260803_037_p1"
down_revision: str | None = "20260802_036_p1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ZERO = "'00000000-0000-0000-0000-000000000000'::uuid"
_PLAN_SCHEMA = "urn:cmp:validation:reference-voce-holdout-plan:1.0.0"
_VOCE_FAMILY = "urn:cmp:reference:isotropic-tabulated-plasticity:1.1.0"
_METRIC = "urn:cmp:validation:reference-voce-true-stress-relative-rmse:1.0.0"
_THRESHOLD = "urn:cmp:validation:reference-voce-relative-rmse-threshold:1.0.0"
_COMPARISON_SCHEMA = "urn:cmp:validation:reference-voce-holdout-comparison:1.0.0"
_LINEAR_MODEL_DIGEST = "a4e39b23b5d656abb50399b1ae76b799e01872f4f6ebe44a59bc8c901b622cd6"
_PLASTIC_MODEL_DIGEST = "18fd736897f26e6472443a5acf50bf899f8eb8f510ae0eca80dada81047a706f"
_VOCE_MODEL_DIGEST = "60174f00940a5e371613f941649a61af20714b5664b8b95672e34e1a718251bd"
_LINEAR_EXPORTER = "cmp.reference.openradioss-elast"
_LINEAR_EXPORTER_DIGEST = "65a3f7ea55150a9c660b4303d12a168d8366bb1e41c6c86684a1e8a2fde20a20"
_LAW36_EXPORTER = "cmp.reference.openradioss-law36"
_LAW36_EXPORTER_DIGEST = "713da51619eedfeda972205426fe86ae25e0d9f75d85554183f35bca76f73be2"
_ABAQUS_EXPORTER = "cmp.reference.abaqus-isotropic-plasticity"
_ABAQUS_EXPORTER_DIGEST = "0585a5dbf0898fcea74009120045b29bf52fef6c428e1285c6603aaee5dd05ad"


def _secure(table: str, *, mutable_identity: bool = False) -> None:
    op.execute(f"ALTER TABLE validation.{table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE validation.{table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY validation_{table}_select ON validation.{table} FOR SELECT "
        "USING (access_control.can_access_row(organization_id, project_id, classification, "
        "'validation.read'))"
    )
    op.execute(
        f"CREATE POLICY validation_{table}_insert ON validation.{table} FOR INSERT "
        "WITH CHECK (access_control.can_access_row(organization_id, project_id, classification, "
        "'validation.execute'))"
    )
    if mutable_identity:
        op.execute(
            f"CREATE POLICY validation_{table}_update ON validation.{table} FOR UPDATE "
            "USING (access_control.can_access_row(organization_id, project_id, classification, "
            "'validation.execute')) WITH CHECK (access_control.can_access_row(organization_id, "
            "project_id, classification, 'validation.execute'))"
        )


def _replace_exporter_contract(*, include_voce: bool) -> None:
    plastic_required = (
        "material_name IS NOT NULL AND source_yield_stress_pa IS NOT NULL "
        "AND hardening_curve_artifact_id IS NOT NULL AND hardening_curve_sha256 IS NOT NULL "
        "AND hardening_curve_point_count IS NOT NULL AND extension_max_true_plastic_strain IS NOT NULL "
        "AND post_necking_extension_policy IS NOT NULL AND hardening_curve_mapping_status IS NOT NULL "
        "AND extension_mapping_status IS NOT NULL AND density_mapping_status = 'exact' "
        "AND youngs_modulus_mapping_status = 'exact' AND poisson_ratio_mapping_status = 'exact' "
        "AND source_yield_mapping_status = 'transformed' AND hardening_curve_mapping_status = 'transformed' "
        "AND extension_mapping_status = 'approximated' "
        "AND temperature_applicability_mapping_status = 'not_applicable' "
        "AND strain_rate_applicability_mapping_status = 'not_applicable'"
    )
    plastic_empty = (
        "material_name IS NULL AND hardening_curve_artifact_id IS NULL "
        "AND hardening_curve_sha256 IS NULL AND hardening_curve_point_count IS NULL "
        "AND extension_max_true_plastic_strain IS NULL AND post_necking_extension_policy IS NULL "
        "AND hardening_curve_mapping_status IS NULL AND extension_mapping_status IS NULL"
    )
    plastic_digest = (
        f"model_schema_digest IN ('{_PLASTIC_MODEL_DIGEST}','{_VOCE_MODEL_DIGEST}')"
        if include_voce
        else f"model_schema_digest = '{_PLASTIC_MODEL_DIGEST}'"
    )
    contract = (
        f"(exporter_id='{_LINEAR_EXPORTER}' AND exporter_version='1.0.0' "
        f"AND exporter_digest='{_LINEAR_EXPORTER_DIGEST}' AND target_solver='openradioss' "
        f"AND model_schema_digest='{_LINEAR_MODEL_DIGEST}' AND {plastic_empty}) OR "
        f"(exporter_id='{_LAW36_EXPORTER}' AND exporter_version='1.0.0' "
        f"AND exporter_digest='{_LAW36_EXPORTER_DIGEST}' AND target_solver='openradioss' "
        f"AND {plastic_digest} AND unit_system_mapping_status='exact' AND {plastic_required}) OR "
        f"(exporter_id='{_ABAQUS_EXPORTER}' AND exporter_version='1.0.0' "
        f"AND exporter_digest='{_ABAQUS_EXPORTER_DIGEST}' AND target_solver='abaqus' "
        f"AND {plastic_digest} AND unit_system_mapping_status='transformed' AND {plastic_required})"
    )
    op.execute(
        "ALTER TABLE exporting.solver_card_revision DROP CONSTRAINT "
        "ck_exporting_solver_card_exporter_contract"
    )
    op.execute(
        "ALTER TABLE exporting.solver_card_revision ADD CONSTRAINT "
        f"ck_exporting_solver_card_exporter_contract CHECK ({contract})"
    )


def upgrade() -> None:
    _replace_exporter_contract(include_voce=True)
    op.execute(
        f"""
        CREATE TABLE validation.voce_holdout_plan (
          id uuid NOT NULL, organization_id uuid NOT NULL, project_id uuid NOT NULL,
          classification varchar(64) NOT NULL, current_revision_id uuid NOT NULL,
          created_at timestamptz NOT NULL, created_by uuid NOT NULL,
          updated_at timestamptz NOT NULL, plan_label varchar(160) NOT NULL,
          material_model_id uuid NOT NULL,
          CONSTRAINT pk_val_voce_holdout_plan PRIMARY KEY (organization_id, project_id, id),
          CONSTRAINT uq_val_voce_holdout_plan_scoped UNIQUE (organization_id, project_id, classification, id),
          CONSTRAINT uq_val_voce_holdout_plan_label UNIQUE (organization_id, project_id, classification, plan_label),
          CONSTRAINT ck_val_voce_holdout_plan_ids CHECK (id <> {_ZERO} AND current_revision_id <> {_ZERO} AND created_by <> {_ZERO} AND material_model_id <> {_ZERO}),
          CONSTRAINT ck_val_voce_holdout_plan_label CHECK (plan_label=btrim(plan_label) AND length(plan_label) BETWEEN 1 AND 160)
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE validation.voce_holdout_plan_revision (
          id uuid NOT NULL, aggregate_id uuid NOT NULL, organization_id uuid NOT NULL,
          project_id uuid NOT NULL, classification varchar(64) NOT NULL,
          revision_no bigint NOT NULL, based_on_revision_id uuid NULL,
          schema_id varchar(255) NOT NULL, schema_version varchar(64) NOT NULL,
          content_hash char(64) COLLATE "C" NOT NULL, created_at timestamptz NOT NULL,
          created_by uuid NOT NULL, change_reason text NOT NULL, request_id uuid NOT NULL,
          trace_id varchar(255) NOT NULL, material_model_id uuid NOT NULL,
          material_model_revision_id uuid NOT NULL, holdout_dataset_id uuid NOT NULL,
          holdout_dataset_revision_id uuid NOT NULL, metric_profile_id varchar(255) NOT NULL,
          threshold_profile_id varchar(255) NOT NULL, relative_rmse_threshold float8 NOT NULL,
          overlap_policy varchar(128) NOT NULL, evaluation_mode varchar(64) NOT NULL,
          non_production boolean NOT NULL,
          CONSTRAINT pk_val_voce_holdout_plan_revision PRIMARY KEY (organization_id, project_id, id),
          CONSTRAINT uq_val_voce_holdout_plan_revision_ref UNIQUE (organization_id, project_id, aggregate_id, id),
          CONSTRAINT uq_val_voce_holdout_plan_revision_scoped UNIQUE (organization_id, project_id, classification, aggregate_id, id),
          CONSTRAINT uq_val_voce_holdout_plan_revision_no UNIQUE (organization_id, project_id, aggregate_id, revision_no),
          CONSTRAINT ck_val_voce_holdout_plan_revision_ids CHECK (id <> {_ZERO} AND aggregate_id <> {_ZERO} AND material_model_id <> {_ZERO} AND material_model_revision_id <> {_ZERO} AND holdout_dataset_id <> {_ZERO} AND holdout_dataset_revision_id <> {_ZERO} AND created_by <> {_ZERO} AND request_id <> {_ZERO}),
          CONSTRAINT ck_val_voce_holdout_plan_revision_base CHECK ((revision_no=1 AND based_on_revision_id IS NULL) OR (revision_no>1 AND based_on_revision_id IS NOT NULL)),
          CONSTRAINT ck_val_voce_holdout_plan_revision_contract CHECK (schema_id='{_PLAN_SCHEMA}' AND schema_version='1.0.0' AND content_hash ~ '^[0-9a-f]{{64}}$' AND metric_profile_id='{_METRIC}' AND threshold_profile_id='{_THRESHOLD}' AND relative_rmse_threshold=0.05 AND overlap_policy='reject_any_calibration_scope_dataset_or_test_run_overlap' AND evaluation_mode='closed_form_curve' AND non_production),
          CONSTRAINT ck_val_voce_holdout_plan_revision_text CHECK (length(btrim(change_reason)) BETWEEN 1 AND 2000 AND length(btrim(trace_id)) BETWEEN 1 AND 255),
          CONSTRAINT fk_val_voce_holdout_plan_revision_identity FOREIGN KEY (organization_id, project_id, aggregate_id) REFERENCES validation.voce_holdout_plan (organization_id, project_id, id) ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_val_voce_holdout_plan_revision_base FOREIGN KEY (organization_id, project_id, aggregate_id, based_on_revision_id) REFERENCES validation.voce_holdout_plan_revision (organization_id, project_id, aggregate_id, id) ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_val_voce_holdout_plan_revision_model FOREIGN KEY (organization_id, project_id, classification, material_model_id, material_model_revision_id) REFERENCES modeling.material_model_revision (organization_id, project_id, classification, aggregate_id, id) ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_val_voce_holdout_plan_revision_dataset FOREIGN KEY (organization_id, project_id, classification, holdout_dataset_id, holdout_dataset_revision_id) REFERENCES datasets.dataset_revision (organization_id, project_id, classification, aggregate_id, id) ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED
        )
        """
    )
    op.execute(
        "ALTER TABLE validation.voce_holdout_plan ADD CONSTRAINT fk_val_voce_holdout_plan_current "
        "FOREIGN KEY (organization_id, project_id, id, current_revision_id) REFERENCES "
        "validation.voce_holdout_plan_revision (organization_id, project_id, aggregate_id, id) "
        "ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED"
    )
    op.execute(
        f"""
        CREATE TABLE validation.voce_holdout_run (
          id uuid NOT NULL, organization_id uuid NOT NULL, project_id uuid NOT NULL,
          classification varchar(64) NOT NULL, plan_id uuid NOT NULL,
          plan_revision_id uuid NOT NULL, material_model_id uuid NOT NULL,
          material_model_revision_id uuid NOT NULL, holdout_dataset_id uuid NOT NULL,
          holdout_dataset_revision_id uuid NOT NULL, execution_mode varchar(64) NOT NULL,
          status varchar(32) NOT NULL, result_id uuid NOT NULL,
          started_at timestamptz NOT NULL, ended_at timestamptz NOT NULL,
          created_by uuid NOT NULL, request_id uuid NOT NULL, trace_id varchar(255) NOT NULL,
          change_reason text NOT NULL,
          CONSTRAINT pk_val_voce_holdout_run PRIMARY KEY (organization_id, project_id, id),
          CONSTRAINT uq_val_voce_holdout_run_scoped UNIQUE (organization_id, project_id, classification, id),
          CONSTRAINT uq_val_voce_holdout_run_result UNIQUE (organization_id, project_id, classification, result_id),
          CONSTRAINT ck_val_voce_holdout_run_ids CHECK (id <> {_ZERO} AND plan_id <> {_ZERO} AND plan_revision_id <> {_ZERO} AND result_id <> {_ZERO} AND created_by <> {_ZERO} AND request_id <> {_ZERO}),
          CONSTRAINT ck_val_voce_holdout_run_contract CHECK (execution_mode='closed_form_curve' AND status='succeeded' AND ended_at >= started_at AND length(btrim(change_reason)) BETWEEN 1 AND 2000 AND length(btrim(trace_id)) BETWEEN 1 AND 255),
          CONSTRAINT fk_val_voce_holdout_run_plan FOREIGN KEY (organization_id, project_id, classification, plan_id, plan_revision_id) REFERENCES validation.voce_holdout_plan_revision (organization_id, project_id, classification, aggregate_id, id) ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_val_voce_holdout_run_model FOREIGN KEY (organization_id, project_id, classification, material_model_id, material_model_revision_id) REFERENCES modeling.material_model_revision (organization_id, project_id, classification, aggregate_id, id) ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_val_voce_holdout_run_dataset FOREIGN KEY (organization_id, project_id, classification, holdout_dataset_id, holdout_dataset_revision_id) REFERENCES datasets.dataset_revision (organization_id, project_id, classification, aggregate_id, id) ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE validation.voce_holdout_result (
          id uuid NOT NULL, organization_id uuid NOT NULL, project_id uuid NOT NULL,
          classification varchar(64) NOT NULL, run_id uuid NOT NULL, plan_id uuid NOT NULL,
          plan_revision_id uuid NOT NULL, material_model_id uuid NOT NULL,
          material_model_revision_id uuid NOT NULL, calibration_input_scope_id uuid NOT NULL,
          calibration_input_scope_revision_id uuid NOT NULL, voce_calibration_run_id uuid NOT NULL,
          voce_calibration_candidate_id uuid NOT NULL, voce_candidate_selection_id uuid NOT NULL,
          voce_candidate_selection_revision_id uuid NOT NULL, holdout_dataset_id uuid NOT NULL,
          holdout_dataset_revision_id uuid NOT NULL, holdout_test_run_id uuid NOT NULL,
          holdout_test_run_revision_id uuid NOT NULL, source_data_artifact_id uuid NOT NULL,
          source_data_sha256 char(64) COLLATE "C" NOT NULL, comparison_artifact_id uuid NOT NULL,
          comparison_sha256 char(64) COLLATE "C" NOT NULL, comparison_point_count integer NOT NULL,
          root_mean_squared_error_pa float8 NOT NULL, relative_root_mean_squared_error float8 NOT NULL,
          normalization_stress_scale_pa float8 NOT NULL,
          characterized_max_true_plastic_strain float8 NOT NULL, verdict varchar(32) NOT NULL,
          created_at timestamptz NOT NULL, created_by uuid NOT NULL,
          CONSTRAINT pk_val_voce_holdout_result PRIMARY KEY (organization_id, project_id, id),
          CONSTRAINT uq_val_voce_holdout_result_scoped UNIQUE (organization_id, project_id, classification, id),
          CONSTRAINT uq_val_voce_holdout_result_run UNIQUE (organization_id, project_id, classification, run_id),
          CONSTRAINT ck_val_voce_holdout_result_ids CHECK (id <> {_ZERO} AND run_id <> {_ZERO} AND created_by <> {_ZERO}),
          CONSTRAINT ck_val_voce_holdout_result_contract CHECK (source_data_sha256 ~ '^[0-9a-f]{{64}}$' AND comparison_sha256 ~ '^[0-9a-f]{{64}}$' AND comparison_point_count >= 3 AND root_mean_squared_error_pa >= 0 AND relative_root_mean_squared_error >= 0 AND normalization_stress_scale_pa > 0 AND characterized_max_true_plastic_strain > 0 AND verdict IN ('passed','failed') AND ((verdict='passed' AND relative_root_mean_squared_error <= 0.05) OR (verdict='failed' AND relative_root_mean_squared_error > 0.05))),
          CONSTRAINT fk_val_voce_holdout_result_run FOREIGN KEY (organization_id, project_id, classification, run_id) REFERENCES validation.voce_holdout_run (organization_id, project_id, classification, id) ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_val_voce_holdout_result_scope FOREIGN KEY (organization_id, project_id, classification, calibration_input_scope_id, calibration_input_scope_revision_id) REFERENCES statistics.calibration_input_scope_revision (organization_id, project_id, classification, aggregate_id, id) ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_val_voce_holdout_result_candidate FOREIGN KEY (organization_id, project_id, classification, voce_calibration_candidate_id, voce_calibration_run_id) REFERENCES modeling.voce_calibration_candidate (organization_id, project_id, classification, id, calibration_run_id) ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_val_voce_holdout_result_selection FOREIGN KEY (organization_id, project_id, classification, voce_candidate_selection_id, voce_candidate_selection_revision_id) REFERENCES modeling.voce_candidate_selection_revision (organization_id, project_id, classification, aggregate_id, id) ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_val_voce_holdout_result_source_artifact FOREIGN KEY (organization_id, project_id, classification, source_data_artifact_id) REFERENCES artifact.artifact (organization_id, project_id, classification, id) ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_val_voce_holdout_result_comparison_artifact FOREIGN KEY (organization_id, project_id, classification, comparison_artifact_id) REFERENCES artifact.artifact (organization_id, project_id, classification, id) ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED
        )
        """
    )
    op.execute(
        "ALTER TABLE validation.voce_holdout_run ADD CONSTRAINT fk_val_voce_holdout_run_result "
        "FOREIGN KEY (organization_id, project_id, classification, result_id) REFERENCES "
        "validation.voce_holdout_result (organization_id, project_id, classification, id) "
        "ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED"
    )
    op.execute(
        """
        CREATE TABLE validation.voce_holdout_comparison_point (
          organization_id uuid NOT NULL, project_id uuid NOT NULL,
          classification varchar(64) NOT NULL, result_id uuid NOT NULL,
          point_ordinal integer NOT NULL, source_point_ordinal integer NOT NULL,
          true_plastic_strain float8 NOT NULL, observed_true_yield_stress_pa float8 NOT NULL,
          predicted_true_yield_stress_pa float8 NOT NULL,
          residual_true_yield_stress_pa float8 NOT NULL,
          CONSTRAINT pk_val_voce_holdout_point PRIMARY KEY (organization_id, project_id, result_id, point_ordinal),
          CONSTRAINT ck_val_voce_holdout_point_values CHECK (point_ordinal >= 0 AND source_point_ordinal >= 0 AND true_plastic_strain > 0 AND observed_true_yield_stress_pa >= 0 AND predicted_true_yield_stress_pa >= 0),
          CONSTRAINT fk_val_voce_holdout_point_result FOREIGN KEY (organization_id, project_id, classification, result_id) REFERENCES validation.voce_holdout_result (organization_id, project_id, classification, id) ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED
        )
        """
    )
    for table in (
        "voce_holdout_plan_revision",
        "voce_holdout_run",
        "voce_holdout_result",
        "voce_holdout_comparison_point",
    ):
        _secure(table)
    _secure("voce_holdout_plan", mutable_identity=True)
    op.execute("CREATE TRIGGER validation_voce_holdout_plan_head BEFORE UPDATE OR DELETE ON validation.voce_holdout_plan FOR EACH ROW EXECUTE FUNCTION revisioning.guard_identity_head_update()")
    for table in (
        "voce_holdout_plan_revision",
        "voce_holdout_run",
        "voce_holdout_result",
        "voce_holdout_comparison_point",
    ):
        op.execute(f"CREATE TRIGGER validation_{table}_immutable BEFORE UPDATE OR DELETE ON validation.{table} FOR EACH ROW EXECUTE FUNCTION revisioning.reject_immutable_row_mutation()")
    op.execute(
        f"""
        CREATE FUNCTION validation.guard_voce_holdout_plan_insert() RETURNS trigger
        LANGUAGE plpgsql AS $$
        DECLARE model_family text; DECLARE scope_revision uuid; DECLARE holdout_test_run_revision uuid;
        BEGIN
          SELECT model_family_id, calibration_input_scope_revision_id INTO model_family, scope_revision
          FROM modeling.material_model_revision
          WHERE organization_id=NEW.organization_id AND project_id=NEW.project_id
            AND classification=NEW.classification AND aggregate_id=NEW.material_model_id
            AND id=NEW.material_model_revision_id;
          SELECT test_run_revision_id INTO holdout_test_run_revision
          FROM datasets.dataset_revision
          WHERE organization_id=NEW.organization_id AND project_id=NEW.project_id
            AND classification=NEW.classification AND aggregate_id=NEW.holdout_dataset_id
            AND id=NEW.holdout_dataset_revision_id;
          IF model_family IS DISTINCT FROM '{_VOCE_FAMILY}' THEN
            RAISE EXCEPTION USING ERRCODE='23514', MESSAGE='holdout Plan requires a calibrated reference Voce IR';
          END IF;
          IF EXISTS (
            SELECT 1 FROM statistics.calibration_input_scope_member m
            WHERE m.organization_id=NEW.organization_id AND m.project_id=NEW.project_id
              AND m.classification=NEW.classification AND m.scope_revision_id=scope_revision
              AND (m.dataset_revision_id=NEW.holdout_dataset_revision_id
                   OR m.test_run_revision_id=holdout_test_run_revision)
          ) THEN
            RAISE EXCEPTION USING ERRCODE='23514', MESSAGE='holdout Dataset or Test Run overlaps calibration review scope';
          END IF;
          RETURN NEW;
        END $$
        """
    )
    op.execute("CREATE TRIGGER validation_voce_holdout_plan_guard BEFORE INSERT ON validation.voce_holdout_plan_revision FOR EACH ROW EXECUTE FUNCTION validation.guard_voce_holdout_plan_insert()")
    op.execute(
        f"""
        CREATE FUNCTION validation.guard_voce_holdout_result_insert() RETURNS trigger
        LANGUAGE plpgsql AS $$
        DECLARE artifact_role text; DECLARE artifact_schema text; DECLARE artifact_digest text;
        BEGIN
          SELECT a.artifact_role,a.schema_ref,a.sha256 INTO artifact_role,artifact_schema,artifact_digest
          FROM artifact.artifact a WHERE a.organization_id=NEW.organization_id
            AND a.project_id=NEW.project_id AND a.classification=NEW.classification
            AND a.id=NEW.comparison_artifact_id;
          IF artifact_role IS DISTINCT FROM 'validation.reference_voce_holdout_comparison'
             OR artifact_schema IS DISTINCT FROM '{_COMPARISON_SCHEMA}'
             OR artifact_digest IS DISTINCT FROM NEW.comparison_sha256 THEN
            RAISE EXCEPTION USING ERRCODE='23514', MESSAGE='holdout comparison Artifact contract is invalid';
          END IF;
          RETURN NEW;
        END $$
        """
    )
    op.execute("CREATE TRIGGER validation_voce_holdout_result_guard BEFORE INSERT ON validation.voce_holdout_result FOR EACH ROW EXECUTE FUNCTION validation.guard_voce_holdout_result_insert()")
    op.create_index("ix_val_voce_holdout_plan_model", "voce_holdout_plan_revision", ["organization_id", "project_id", "material_model_id", "created_at"], schema="validation")
    op.create_index("ix_val_voce_holdout_result_model", "voce_holdout_result", ["organization_id", "project_id", "material_model_id", "created_at"], schema="validation")
    op.create_index("ix_val_voce_holdout_result_dataset", "voce_holdout_result", ["organization_id", "project_id", "holdout_dataset_revision_id"], schema="validation")


def downgrade() -> None:
    _replace_exporter_contract(include_voce=False)
    op.execute("DROP TRIGGER IF EXISTS validation_voce_holdout_result_guard ON validation.voce_holdout_result")
    op.execute("DROP FUNCTION IF EXISTS validation.guard_voce_holdout_result_insert()")
    op.execute("DROP TRIGGER IF EXISTS validation_voce_holdout_plan_guard ON validation.voce_holdout_plan_revision")
    op.execute("DROP FUNCTION IF EXISTS validation.guard_voce_holdout_plan_insert()")
    op.execute("DROP TABLE IF EXISTS validation.voce_holdout_comparison_point CASCADE")
    op.execute("DROP TABLE IF EXISTS validation.voce_holdout_result CASCADE")
    op.execute("DROP TABLE IF EXISTS validation.voce_holdout_run CASCADE")
    op.execute("DROP TABLE IF EXISTS validation.voce_holdout_plan_revision CASCADE")
    op.execute("DROP TABLE IF EXISTS validation.voce_holdout_plan CASCADE")

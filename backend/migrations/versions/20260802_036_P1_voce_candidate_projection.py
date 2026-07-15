"""Add human Voce selection and calibrated tabulated-plasticity IR 1.1.

Revision ID: 20260802_036_p1
Revises: 20260801_035_p1
"""

# ruff: noqa: E501

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260802_036_p1"
down_revision: str | None = "20260801_035_p1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ZERO = "'00000000-0000-0000-0000-000000000000'::uuid"
_LINEAR_FAMILY = "urn:cmp:reference:isotropic-linear-elasticity:1.0.0"
_TENSILE_FAMILY = "urn:cmp:reference:isotropic-tabulated-plasticity:1.0.0"
_VOCE_FAMILY = "urn:cmp:reference:isotropic-tabulated-plasticity:1.1.0"
_LINEAR_DIGEST = "a4e39b23b5d656abb50399b1ae76b799e01872f4f6ebe44a59bc8c901b622cd6"
_TENSILE_DIGEST = "18fd736897f26e6472443a5acf50bf899f8eb8f510ae0eca80dada81047a706f"
_VOCE_DIGEST = "60174f00940a5e371613f941649a61af20714b5664b8b95672e34e1a718251bd"
_VOCE_PROFILE = "urn:cmp:modeling:reference-voce-fixed-grid-projection:1.0.0"
_VOCE_PROFILE_DIGEST = "64a54f24a263c863682643c5b36621275bcc355254655bdf0aae819b661a0d5d"
_SELECTION_SCHEMA = "urn:cmp:modeling:reference-voce-candidate-selection:1.0.0"
_SELECTION_DECISION = "accepted_for_tabulated_ir_projection"
_HARDENING_SCHEMA = "urn:cmp:modeling:reference-true-stress-plastic-strain-parquet:1.0.0"
_EXTENSION_POLICY = "approved_constant_true_stress"


def _secure(table: str) -> None:
    op.execute(f"ALTER TABLE modeling.{table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE modeling.{table} FORCE ROW LEVEL SECURITY")
    for operation, predicate, permission in (
        ("select", "USING", "modeling.read"),
        ("insert", "WITH CHECK", "modeling.write"),
    ):
        op.execute(
            f"CREATE POLICY modeling_{table}_{operation} ON modeling.{table} "
            f"FOR {operation.upper()} {predicate} (access_control.can_access_row("
            f"organization_id, project_id, classification, '{permission}'))"
        )
    op.execute(
        f"CREATE POLICY modeling_{table}_update ON modeling.{table} FOR UPDATE "
        "USING (access_control.can_access_row(organization_id, project_id, classification, "
        "'modeling.write')) WITH CHECK (access_control.can_access_row("
        "organization_id, project_id, classification, 'modeling.write'))"
    )


def _selection_tables() -> None:
    op.execute(
        f"""
        CREATE TABLE modeling.voce_candidate_selection (
          id uuid NOT NULL, organization_id uuid NOT NULL, project_id uuid NOT NULL,
          classification varchar(64) NOT NULL, current_revision_id uuid NOT NULL,
          created_at timestamptz NOT NULL, created_by uuid NOT NULL,
          updated_at timestamptz NOT NULL, selection_label varchar(160) NOT NULL,
          voce_calibration_run_id uuid NOT NULL,
          CONSTRAINT pk_mdl_voce_selection PRIMARY KEY (organization_id, project_id, id),
          CONSTRAINT uq_mdl_voce_selection_scoped UNIQUE (organization_id, project_id, classification, id),
          CONSTRAINT uq_mdl_voce_selection_label UNIQUE (organization_id, project_id, classification, selection_label),
          CONSTRAINT uq_mdl_voce_selection_run_ref UNIQUE (organization_id, project_id, classification, id, voce_calibration_run_id),
          CONSTRAINT ck_mdl_voce_selection_ids CHECK (id <> {_ZERO} AND current_revision_id <> {_ZERO} AND created_by <> {_ZERO} AND voce_calibration_run_id <> {_ZERO}),
          CONSTRAINT ck_mdl_voce_selection_label CHECK (selection_label = btrim(selection_label) AND length(selection_label) BETWEEN 1 AND 160),
          CONSTRAINT fk_mdl_voce_selection_run FOREIGN KEY (organization_id, project_id, classification, voce_calibration_run_id)
            REFERENCES modeling.voce_calibration_run (organization_id, project_id, classification, id) ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE modeling.voce_candidate_selection_revision (
          id uuid NOT NULL, aggregate_id uuid NOT NULL, organization_id uuid NOT NULL,
          project_id uuid NOT NULL, classification varchar(64) NOT NULL,
          revision_no bigint NOT NULL, based_on_revision_id uuid NULL,
          schema_id varchar(255) NOT NULL, schema_version varchar(64) NOT NULL,
          content_hash char(64) COLLATE "C" NOT NULL, created_at timestamptz NOT NULL,
          created_by uuid NOT NULL, change_reason text NOT NULL, request_id uuid NOT NULL,
          trace_id varchar(255) NOT NULL, voce_calibration_run_id uuid NOT NULL,
          voce_calibration_candidate_id uuid NOT NULL,
          candidate_sha256 char(64) COLLATE "C" NOT NULL, selection_reason text NOT NULL,
          selection_decision varchar(100) NOT NULL, non_production boolean NOT NULL,
          CONSTRAINT pk_mdl_voce_selection_revision PRIMARY KEY (organization_id, project_id, id),
          CONSTRAINT uq_mdl_voce_selection_revision_ref UNIQUE (organization_id, project_id, aggregate_id, id),
          CONSTRAINT uq_mdl_voce_selection_revision_scoped UNIQUE (organization_id, project_id, classification, aggregate_id, id),
          CONSTRAINT uq_mdl_voce_selection_revision_no UNIQUE (organization_id, project_id, aggregate_id, revision_no),
          CONSTRAINT ck_mdl_voce_selection_revision_ids CHECK (id <> {_ZERO} AND aggregate_id <> {_ZERO} AND created_by <> {_ZERO} AND request_id <> {_ZERO}),
          CONSTRAINT ck_mdl_voce_selection_revision_base CHECK ((revision_no = 1 AND based_on_revision_id IS NULL) OR (revision_no > 1 AND based_on_revision_id IS NOT NULL)),
          CONSTRAINT ck_mdl_voce_selection_revision_contract CHECK (schema_id = '{_SELECTION_SCHEMA}' AND schema_version = '1.0.0' AND content_hash ~ '^[0-9a-f]{{64}}$' AND candidate_sha256 ~ '^[0-9a-f]{{64}}$' AND selection_decision = '{_SELECTION_DECISION}' AND non_production),
          CONSTRAINT ck_mdl_voce_selection_revision_text CHECK (length(btrim(change_reason)) BETWEEN 1 AND 2000 AND length(btrim(selection_reason)) BETWEEN 1 AND 2000 AND length(btrim(trace_id)) BETWEEN 1 AND 255),
          CONSTRAINT fk_mdl_voce_selection_revision_identity FOREIGN KEY (organization_id, project_id, aggregate_id)
            REFERENCES modeling.voce_candidate_selection (organization_id, project_id, id) ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_mdl_voce_selection_revision_identity_run FOREIGN KEY (organization_id, project_id, classification, aggregate_id, voce_calibration_run_id)
            REFERENCES modeling.voce_candidate_selection (organization_id, project_id, classification, id, voce_calibration_run_id) ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_mdl_voce_selection_revision_candidate FOREIGN KEY (organization_id, project_id, classification, voce_calibration_candidate_id, voce_calibration_run_id)
            REFERENCES modeling.voce_calibration_candidate (organization_id, project_id, classification, id, calibration_run_id) ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_mdl_voce_selection_revision_base FOREIGN KEY (organization_id, project_id, aggregate_id, based_on_revision_id)
            REFERENCES modeling.voce_candidate_selection_revision (organization_id, project_id, aggregate_id, id) ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED
        )
        """
    )
    op.execute(
        "ALTER TABLE modeling.voce_candidate_selection ADD CONSTRAINT fk_mdl_voce_selection_current "
        "FOREIGN KEY (organization_id, project_id, id, current_revision_id) REFERENCES "
        "modeling.voce_candidate_selection_revision (organization_id, project_id, aggregate_id, id) "
        "ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED"
    )
    _secure("voce_candidate_selection")
    _secure("voce_candidate_selection_revision")
    op.execute("CREATE TRIGGER modeling_voce_selection_head BEFORE UPDATE OR DELETE ON modeling.voce_candidate_selection FOR EACH ROW EXECUTE FUNCTION revisioning.guard_identity_head_update()")
    op.execute("CREATE TRIGGER modeling_voce_selection_revision_immutable BEFORE UPDATE OR DELETE ON modeling.voce_candidate_selection_revision FOR EACH ROW EXECUTE FUNCTION revisioning.reject_immutable_row_mutation()")
    op.execute(
        """
        CREATE FUNCTION modeling.guard_voce_candidate_selection_insert() RETURNS trigger
        LANGUAGE plpgsql AS $$
        DECLARE candidate_status text; DECLARE candidate_digest text; DECLARE run_status text;
        BEGIN
          SELECT status, candidate_sha256 INTO candidate_status, candidate_digest
          FROM modeling.voce_calibration_candidate
          WHERE organization_id=NEW.organization_id AND project_id=NEW.project_id
            AND classification=NEW.classification AND id=NEW.voce_calibration_candidate_id
            AND calibration_run_id=NEW.voce_calibration_run_id;
          SELECT status INTO run_status FROM modeling.voce_calibration_run
          WHERE organization_id=NEW.organization_id AND project_id=NEW.project_id
            AND classification=NEW.classification AND id=NEW.voce_calibration_run_id;
          IF candidate_status IS DISTINCT FROM 'converged'
             OR candidate_digest IS DISTINCT FROM NEW.candidate_sha256
             OR run_status IS DISTINCT FROM 'succeeded' THEN
            RAISE EXCEPTION USING ERRCODE='23514', MESSAGE='Voce selection requires the exact converged Candidate from a succeeded Run';
          END IF;
          RETURN NEW;
        END $$
        """
    )
    op.execute("CREATE TRIGGER modeling_voce_selection_revision_guard BEFORE INSERT ON modeling.voce_candidate_selection_revision FOR EACH ROW EXECUTE FUNCTION modeling.guard_voce_candidate_selection_insert()")
    op.create_index("ix_mdl_voce_selection_run", "voce_candidate_selection_revision", ["organization_id", "project_id", "voce_calibration_run_id", "voce_calibration_candidate_id"], schema="modeling")


def _extend_material_model() -> None:
    op.execute(
        """
        ALTER TABLE modeling.material_model_revision
          ADD COLUMN calibration_input_scope_id uuid NULL,
          ADD COLUMN calibration_input_scope_revision_id uuid NULL,
          ADD COLUMN voce_calibration_plan_id uuid NULL,
          ADD COLUMN voce_calibration_plan_revision_id uuid NULL,
          ADD COLUMN voce_calibration_run_id uuid NULL,
          ADD COLUMN voce_calibration_candidate_id uuid NULL,
          ADD COLUMN voce_calibration_candidate_sha256 char(64) COLLATE "C" NULL,
          ADD COLUMN voce_candidate_selection_id uuid NULL,
          ADD COLUMN voce_candidate_selection_revision_id uuid NULL,
          ADD COLUMN voce_sampling_point_count integer NULL,
          ADD COLUMN voce_q_pa float8 NULL,
          ADD COLUMN voce_b float8 NULL
        """
    )
    for constraint in (
        "ck_modeling_material_model_family",
        "ck_modeling_material_model_family_digest",
        "ck_modeling_material_model_plastic_payload",
        "ck_modeling_material_model_plastic_profile",
        "ck_modeling_material_model_plastic_ranges",
    ):
        op.execute(f"ALTER TABLE modeling.material_model_revision DROP CONSTRAINT {constraint}")
    op.execute(
        f"""
        ALTER TABLE modeling.material_model_revision
          ADD CONSTRAINT ck_modeling_material_model_family CHECK (model_family_id IN ('{_LINEAR_FAMILY}','{_TENSILE_FAMILY}','{_VOCE_FAMILY}')),
          ADD CONSTRAINT ck_modeling_material_model_family_digest CHECK (
            (model_family_id='{_LINEAR_FAMILY}' AND model_schema_digest='{_LINEAR_DIGEST}') OR
            (model_family_id='{_TENSILE_FAMILY}' AND model_schema_digest='{_TENSILE_DIGEST}') OR
            (model_family_id='{_VOCE_FAMILY}' AND model_schema_digest='{_VOCE_DIGEST}')),
          ADD CONSTRAINT ck_modeling_material_model_plastic_payload CHECK (
            (model_family_id='{_LINEAR_FAMILY}' AND hardening_curve_artifact_id IS NULL AND source_dataset_id IS NULL AND voce_calibration_candidate_id IS NULL) OR
            (model_family_id='{_TENSILE_FAMILY}' AND source_dataset_id IS NOT NULL AND source_dataset_revision_id IS NOT NULL AND hardening_curve_artifact_id IS NOT NULL AND source_point_count IS NOT NULL AND voce_calibration_candidate_id IS NULL) OR
            (model_family_id='{_VOCE_FAMILY}' AND source_dataset_id IS NULL AND source_dataset_revision_id IS NULL AND source_point_count IS NULL AND pre_yield_excluded_point_count IS NULL AND post_necking_excluded_point_count IS NULL AND necking_source_point_index IS NULL AND necking_engineering_strain IS NULL
              AND hardening_curve_artifact_id IS NOT NULL AND hardening_curve_sha256 IS NOT NULL AND hardening_curve_point_count IS NOT NULL
              AND calibration_input_scope_id IS NOT NULL AND calibration_input_scope_revision_id IS NOT NULL
              AND voce_calibration_plan_id IS NOT NULL AND voce_calibration_plan_revision_id IS NOT NULL
              AND voce_calibration_run_id IS NOT NULL AND voce_calibration_candidate_id IS NOT NULL
              AND voce_calibration_candidate_sha256 ~ '^[0-9a-f]{{64}}$'
              AND voce_candidate_selection_id IS NOT NULL AND voce_candidate_selection_revision_id IS NOT NULL
              AND voce_sampling_point_count BETWEEN 21 AND 501 AND hardening_curve_point_count=voce_sampling_point_count+1
              AND voce_q_pa > 0 AND voce_b > 0 AND source_yield_stress_pa > 0
              AND characterized_max_true_plastic_strain > 0
              AND extension_max_true_plastic_strain > characterized_max_true_plastic_strain
              AND post_necking_approximation_acknowledged IS TRUE)),
          ADD CONSTRAINT ck_modeling_material_model_plastic_profile CHECK (
            transformation_profile_id IS NULL OR
            (model_family_id='{_TENSILE_FAMILY}' AND transformation_profile_id='urn:cmp:processing:reference-pre-necking-true-plastic-reduction:1.0.0' AND transformation_profile_version='1.0.0' AND transformation_profile_digest='309b38a58988f0c26a1dfeca702e91283abe025370471def0bf50f257c5e15bf') OR
            (model_family_id='{_VOCE_FAMILY}' AND transformation_profile_id='{_VOCE_PROFILE}' AND transformation_profile_version='1.0.0' AND transformation_profile_digest='{_VOCE_PROFILE_DIGEST}')
          ),
          ADD CONSTRAINT ck_modeling_material_model_plastic_ranges CHECK (
            model_family_id='{_LINEAR_FAMILY}' OR
            (model_family_id='{_TENSILE_FAMILY}' AND necking_engineering_strain >= 0 AND characterized_max_true_plastic_strain >= 0 AND extension_max_true_plastic_strain > characterized_max_true_plastic_strain) OR
            (model_family_id='{_VOCE_FAMILY}' AND necking_engineering_strain IS NULL AND characterized_max_true_plastic_strain > 0 AND extension_max_true_plastic_strain > characterized_max_true_plastic_strain)
          ),
          ADD CONSTRAINT fk_mdl_model_voce_scope FOREIGN KEY (organization_id, project_id, classification, calibration_input_scope_id, calibration_input_scope_revision_id)
            REFERENCES statistics.calibration_input_scope_revision (organization_id, project_id, classification, aggregate_id, id) ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          ADD CONSTRAINT fk_mdl_model_voce_plan FOREIGN KEY (organization_id, project_id, classification, voce_calibration_plan_id, voce_calibration_plan_revision_id)
            REFERENCES modeling.voce_calibration_plan_revision (organization_id, project_id, classification, aggregate_id, id) ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          ADD CONSTRAINT fk_mdl_model_voce_candidate FOREIGN KEY (organization_id, project_id, classification, voce_calibration_candidate_id, voce_calibration_run_id)
            REFERENCES modeling.voce_calibration_candidate (organization_id, project_id, classification, id, calibration_run_id) ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          ADD CONSTRAINT fk_mdl_model_voce_selection FOREIGN KEY (organization_id, project_id, classification, voce_candidate_selection_id, voce_candidate_selection_revision_id)
            REFERENCES modeling.voce_candidate_selection_revision (organization_id, project_id, classification, aggregate_id, id) ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION modeling.validate_reference_hardening_artifact()
        RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE artifact_kind text; DECLARE artifact_role text; DECLARE artifact_schema text; DECLARE artifact_digest text;
        BEGIN
          IF NEW.model_family_id NOT IN ('urn:cmp:reference:isotropic-tabulated-plasticity:1.0.0','urn:cmp:reference:isotropic-tabulated-plasticity:1.1.0') THEN RETURN NEW; END IF;
          SELECT a.artifact_kind,a.artifact_role,a.schema_ref,a.sha256 INTO artifact_kind,artifact_role,artifact_schema,artifact_digest
          FROM artifact.artifact a WHERE a.organization_id=NEW.organization_id AND a.project_id=NEW.project_id AND a.classification=NEW.classification AND a.id=NEW.hardening_curve_artifact_id;
          IF artifact_kind IS DISTINCT FROM 'derived' OR artifact_role IS DISTINCT FROM 'modeling.hardening_curve'
             OR artifact_schema IS DISTINCT FROM 'urn:cmp:modeling:reference-true-stress-plastic-strain-parquet:1.0.0'
             OR artifact_digest IS DISTINCT FROM NEW.hardening_curve_sha256 THEN
            RAISE EXCEPTION 'hardening curve Artifact contract is invalid' USING ERRCODE='23514';
          END IF;
          RETURN NEW;
        END $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION modeling.guard_voce_projected_model_insert() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE c record; DECLARE r record; DECLARE s record;
        BEGIN
          IF NEW.model_family_id <> 'urn:cmp:reference:isotropic-tabulated-plasticity:1.1.0' THEN RETURN NEW; END IF;
          SELECT * INTO c FROM modeling.voce_calibration_candidate WHERE organization_id=NEW.organization_id AND project_id=NEW.project_id AND classification=NEW.classification AND id=NEW.voce_calibration_candidate_id AND calibration_run_id=NEW.voce_calibration_run_id;
          SELECT * INTO r FROM modeling.voce_calibration_run WHERE organization_id=NEW.organization_id AND project_id=NEW.project_id AND classification=NEW.classification AND id=NEW.voce_calibration_run_id;
          SELECT * INTO s FROM modeling.voce_candidate_selection_revision WHERE organization_id=NEW.organization_id AND project_id=NEW.project_id AND classification=NEW.classification AND aggregate_id=NEW.voce_candidate_selection_id AND id=NEW.voce_candidate_selection_revision_id;
          IF c.status IS DISTINCT FROM 'converged' OR r.status IS DISTINCT FROM 'succeeded'
             OR c.candidate_sha256 IS DISTINCT FROM NEW.voce_calibration_candidate_sha256
             OR c.sigma_0_pa IS DISTINCT FROM NEW.source_yield_stress_pa OR c.q_pa IS DISTINCT FROM NEW.voce_q_pa OR c.b IS DISTINCT FROM NEW.voce_b
             OR s.voce_calibration_candidate_id IS DISTINCT FROM NEW.voce_calibration_candidate_id
             OR s.voce_calibration_run_id IS DISTINCT FROM NEW.voce_calibration_run_id
             OR s.candidate_sha256 IS DISTINCT FROM NEW.voce_calibration_candidate_sha256
             OR r.plan_id IS DISTINCT FROM NEW.voce_calibration_plan_id OR r.plan_revision_id IS DISTINCT FROM NEW.voce_calibration_plan_revision_id
             OR r.calibration_input_scope_id IS DISTINCT FROM NEW.calibration_input_scope_id OR r.calibration_input_scope_revision_id IS DISTINCT FROM NEW.calibration_input_scope_revision_id
             OR r.property_set_revision_id IS DISTINCT FROM NEW.property_set_revision_id THEN
            RAISE EXCEPTION USING ERRCODE='23514', MESSAGE='Voce projected IR differs from its exact accepted Candidate lineage';
          END IF;
          RETURN NEW;
        END $$
        """
    )
    op.execute("CREATE TRIGGER modeling_voce_projected_model_guard BEFORE INSERT ON modeling.material_model_revision FOR EACH ROW EXECUTE FUNCTION modeling.guard_voce_projected_model_insert()")
    op.execute(
        "CREATE INDEX ix_mdl_model_voce_candidate ON modeling.material_model_revision "
        "(organization_id, project_id, voce_calibration_candidate_id) "
        "WHERE voce_calibration_candidate_id IS NOT NULL"
    )


def _extend_exporting() -> None:
    op.execute("ALTER TABLE exporting.solver_card_revision DROP CONSTRAINT ck_exporting_solver_card_model_digest")
    op.execute(f"ALTER TABLE exporting.solver_card_revision ADD CONSTRAINT ck_exporting_solver_card_model_digest CHECK (model_schema_digest IN ('{_LINEAR_DIGEST}','{_TENSILE_DIGEST}','{_VOCE_DIGEST}'))")


def upgrade() -> None:
    op.execute("ALTER TABLE modeling.voce_calibration_candidate ADD CONSTRAINT uq_mdl_voce_candidate_run_ref UNIQUE (organization_id, project_id, classification, id, calibration_run_id)")
    _selection_tables()
    _extend_material_model()
    _extend_exporting()


def downgrade() -> None:
    op.execute("ALTER TABLE exporting.solver_card_revision DROP CONSTRAINT IF EXISTS ck_exporting_solver_card_model_digest")
    op.execute(f"ALTER TABLE exporting.solver_card_revision ADD CONSTRAINT ck_exporting_solver_card_model_digest CHECK (model_schema_digest IN ('{_LINEAR_DIGEST}','{_TENSILE_DIGEST}'))")
    op.execute("DROP TRIGGER IF EXISTS modeling_voce_projected_model_guard ON modeling.material_model_revision")
    op.execute("DROP FUNCTION IF EXISTS modeling.guard_voce_projected_model_insert()")
    for constraint in (
        "ck_modeling_material_model_family",
        "ck_modeling_material_model_family_digest",
        "ck_modeling_material_model_plastic_payload",
        "ck_modeling_material_model_plastic_profile",
        "ck_modeling_material_model_plastic_ranges",
    ):
        op.execute(
            "ALTER TABLE modeling.material_model_revision "
            f"DROP CONSTRAINT IF EXISTS {constraint}"
        )
    for constraint in ("fk_mdl_model_voce_selection","fk_mdl_model_voce_candidate","fk_mdl_model_voce_plan","fk_mdl_model_voce_scope"):
        op.execute(f"ALTER TABLE modeling.material_model_revision DROP CONSTRAINT IF EXISTS {constraint}")
    for column in ("voce_b","voce_q_pa","voce_sampling_point_count","voce_candidate_selection_revision_id","voce_candidate_selection_id","voce_calibration_candidate_sha256","voce_calibration_candidate_id","voce_calibration_run_id","voce_calibration_plan_revision_id","voce_calibration_plan_id","calibration_input_scope_revision_id","calibration_input_scope_id"):
        op.execute(f"ALTER TABLE modeling.material_model_revision DROP COLUMN IF EXISTS {column} CASCADE")
    op.execute(
        f"""
        ALTER TABLE modeling.material_model_revision
          ADD CONSTRAINT ck_modeling_material_model_family CHECK (model_family_id IN ('{_LINEAR_FAMILY}','{_TENSILE_FAMILY}')),
          ADD CONSTRAINT ck_modeling_material_model_family_digest CHECK (
            (model_family_id='{_LINEAR_FAMILY}' AND model_schema_digest='{_LINEAR_DIGEST}') OR
            (model_family_id='{_TENSILE_FAMILY}' AND model_schema_digest='{_TENSILE_DIGEST}')),
          ADD CONSTRAINT ck_modeling_material_model_plastic_payload CHECK (
            (model_family_id='{_TENSILE_FAMILY}'
              AND source_dataset_id IS NOT NULL AND source_dataset_revision_id IS NOT NULL
              AND hardening_curve_artifact_id IS NOT NULL AND hardening_curve_sha256 IS NOT NULL
              AND hardening_curve_schema_ref IS NOT NULL AND hardening_curve_point_count IS NOT NULL
              AND source_point_count IS NOT NULL AND pre_yield_excluded_point_count IS NOT NULL
              AND post_necking_excluded_point_count IS NOT NULL AND necking_source_point_index IS NOT NULL
              AND transformation_profile_id IS NOT NULL AND transformation_profile_version IS NOT NULL
              AND transformation_profile_digest IS NOT NULL AND necking_engineering_strain IS NOT NULL
              AND characterized_max_true_plastic_strain IS NOT NULL AND extension_max_true_plastic_strain IS NOT NULL
              AND post_necking_extension_policy IS NOT NULL AND post_necking_approximation_acknowledged IS TRUE
              AND source_yield_stress_pa IS NOT NULL)
            OR
            (model_family_id='{_LINEAR_FAMILY}'
              AND source_dataset_id IS NULL AND source_dataset_revision_id IS NULL
              AND hardening_curve_artifact_id IS NULL AND hardening_curve_sha256 IS NULL
              AND hardening_curve_schema_ref IS NULL AND hardening_curve_point_count IS NULL
              AND source_point_count IS NULL AND pre_yield_excluded_point_count IS NULL
              AND post_necking_excluded_point_count IS NULL AND necking_source_point_index IS NULL
              AND transformation_profile_id IS NULL AND transformation_profile_version IS NULL
              AND transformation_profile_digest IS NULL AND necking_engineering_strain IS NULL
              AND characterized_max_true_plastic_strain IS NULL AND extension_max_true_plastic_strain IS NULL
              AND post_necking_extension_policy IS NULL AND post_necking_approximation_acknowledged IS NULL)),
          ADD CONSTRAINT ck_modeling_material_model_plastic_profile CHECK (
            transformation_profile_id IS NULL OR
            (transformation_profile_id='urn:cmp:processing:reference-pre-necking-true-plastic-reduction:1.0.0'
             AND transformation_profile_version='1.0.0'
             AND transformation_profile_digest='309b38a58988f0c26a1dfeca702e91283abe025370471def0bf50f257c5e15bf'
             AND hardening_curve_schema_ref='{_HARDENING_SCHEMA}'
             AND post_necking_extension_policy='{_EXTENSION_POLICY}')),
          ADD CONSTRAINT ck_modeling_material_model_plastic_ranges CHECK (
            necking_engineering_strain IS NULL OR
            (necking_engineering_strain >= 0 AND characterized_max_true_plastic_strain >= 0
             AND extension_max_true_plastic_strain > characterized_max_true_plastic_strain))
        """
    )
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION modeling.validate_reference_hardening_artifact()
        RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE artifact_kind text; DECLARE artifact_role text; DECLARE artifact_schema text; DECLARE artifact_digest text;
        BEGIN
          IF NEW.model_family_id <> '{_TENSILE_FAMILY}' THEN RETURN NEW; END IF;
          SELECT a.artifact_kind,a.artifact_role,a.schema_ref,a.sha256 INTO artifact_kind,artifact_role,artifact_schema,artifact_digest
          FROM artifact.artifact a WHERE a.organization_id=NEW.organization_id AND a.project_id=NEW.project_id AND a.classification=NEW.classification AND a.id=NEW.hardening_curve_artifact_id;
          IF artifact_kind IS DISTINCT FROM 'derived' OR artifact_role IS DISTINCT FROM 'modeling.hardening_curve'
             OR artifact_schema IS DISTINCT FROM '{_HARDENING_SCHEMA}' OR artifact_digest IS DISTINCT FROM NEW.hardening_curve_sha256 THEN
            RAISE EXCEPTION 'hardening curve Artifact contract is invalid' USING ERRCODE='23514';
          END IF;
          RETURN NEW;
        END $$
        """
    )
    op.execute("ALTER TABLE modeling.voce_candidate_selection DROP CONSTRAINT IF EXISTS fk_mdl_voce_selection_current")
    op.execute("DROP TABLE IF EXISTS modeling.voce_candidate_selection_revision CASCADE")
    op.execute("DROP TABLE IF EXISTS modeling.voce_candidate_selection CASCADE")
    op.execute("DROP FUNCTION IF EXISTS modeling.guard_voce_candidate_selection_insert()")
    op.execute("ALTER TABLE modeling.voce_calibration_candidate DROP CONSTRAINT IF EXISTS uq_mdl_voce_candidate_run_ref")

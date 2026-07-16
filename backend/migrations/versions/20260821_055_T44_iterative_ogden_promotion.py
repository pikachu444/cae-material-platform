"""Add iterative Ogden selection and revision-owned promotion evidence.

Revision ID: 20260821_055_t44_ogden
Revises: 20260820_054_t43_ogden

Traceability: T-44, ADR-0026.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260821_055_t44_ogden"
down_revision: str | None = "20260820_054_t43_ogden"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _evidence_constraints(*, include_ogden: bool) -> None:
    kinds = (
        "'manual_catalog_projection','reference_candidate_selection',"
        "'reference_prony_candidate_selection'"
    )
    ogden_shape = ""
    if include_ogden:
        kinds += ",'reference_ogden_candidate_selection'"
        ogden_shape = """
            OR (calibration_evidence_kind='reference_ogden_candidate_selection'
             AND calibration_selection_id IS NULL
             AND calibration_selection_revision_id IS NULL
             AND calibration_run_id IS NULL AND calibration_candidate_id IS NULL
             AND calibration_candidate_sha256 IS NULL
             AND calibration_diagnostics_artifact_id IS NULL
             AND calibration_diagnostics_sha256 IS NULL
             AND prony_selection_id IS NULL AND prony_selection_revision_id IS NULL
             AND prony_calibration_run_id IS NULL
             AND prony_calibration_candidate_id IS NULL
             AND prony_calibration_candidate_sha256 IS NULL
             AND prony_diagnostics_artifact_id IS NULL
             AND prony_diagnostics_sha256 IS NULL)
        """
    op.execute(
        "ALTER TABLE modeling.material_model_revision "
        "DROP CONSTRAINT IF EXISTS ck_modeling_material_model_calibration_evidence_shape, "
        "DROP CONSTRAINT IF EXISTS ck_modeling_material_model_calibration_evidence_kind"
    )
    op.execute(
        f"""
        ALTER TABLE modeling.material_model_revision
          ADD CONSTRAINT ck_modeling_material_model_calibration_evidence_kind CHECK
            (calibration_evidence_kind IN ({kinds})),
          ADD CONSTRAINT ck_modeling_material_model_calibration_evidence_shape CHECK (
            (calibration_evidence_kind='manual_catalog_projection'
             AND calibration_selection_id IS NULL
             AND calibration_selection_revision_id IS NULL
             AND calibration_run_id IS NULL AND calibration_candidate_id IS NULL
             AND calibration_candidate_sha256 IS NULL
             AND calibration_diagnostics_artifact_id IS NULL
             AND calibration_diagnostics_sha256 IS NULL
             AND prony_selection_id IS NULL AND prony_selection_revision_id IS NULL
             AND prony_calibration_run_id IS NULL
             AND prony_calibration_candidate_id IS NULL
             AND prony_calibration_candidate_sha256 IS NULL
             AND prony_diagnostics_artifact_id IS NULL
             AND prony_diagnostics_sha256 IS NULL)
            OR (calibration_evidence_kind='reference_candidate_selection'
             AND calibration_selection_id IS NOT NULL
             AND calibration_selection_revision_id IS NOT NULL
             AND calibration_run_id IS NOT NULL AND calibration_candidate_id IS NOT NULL
             AND calibration_candidate_sha256 ~ '^[0-9a-f]{{64}}$'
             AND calibration_diagnostics_artifact_id IS NOT NULL
             AND calibration_diagnostics_sha256 ~ '^[0-9a-f]{{64}}$'
             AND prony_selection_id IS NULL AND prony_selection_revision_id IS NULL
             AND prony_calibration_run_id IS NULL
             AND prony_calibration_candidate_id IS NULL
             AND prony_calibration_candidate_sha256 IS NULL
             AND prony_diagnostics_artifact_id IS NULL
             AND prony_diagnostics_sha256 IS NULL)
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
             AND prony_diagnostics_sha256 ~ '^[0-9a-f]{{64}}$')
            {ogden_shape})
        """
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
        "'modeling.write'))"
    )
    if identity:
        op.execute(
            f"CREATE POLICY modeling_{table}_update ON modeling.{table} FOR UPDATE USING "
            "(access_control.can_access_row(organization_id, project_id, classification, "
            "'modeling.write')) WITH CHECK "
            "(access_control.can_access_row(organization_id, project_id, classification, "
            "'modeling.write'))"
        )


def upgrade() -> None:
    _evidence_constraints(include_ogden=True)
    op.execute(
        """
        CREATE TABLE modeling.ogden_candidate_selection (
          id uuid NOT NULL, organization_id uuid NOT NULL, project_id uuid NOT NULL,
          classification varchar(64) NOT NULL, current_revision_id uuid NOT NULL,
          created_at timestamptz NOT NULL, created_by uuid NOT NULL,
          updated_at timestamptz NOT NULL, selection_label varchar(160) NOT NULL,
          ogden_calibration_run_id uuid NOT NULL,
          CONSTRAINT pk_mdl_ogden_selection PRIMARY KEY (organization_id, project_id, id),
          CONSTRAINT uq_mdl_ogden_selection_scoped UNIQUE
            (organization_id, project_id, classification, id),
          CONSTRAINT uq_mdl_ogden_selection_label UNIQUE
            (organization_id, project_id, classification, selection_label),
          CONSTRAINT ck_mdl_ogden_selection_label CHECK
            (length(btrim(selection_label)) BETWEEN 1 AND 160)
        );

        CREATE TABLE modeling.ogden_candidate_selection_revision (
          id uuid NOT NULL, aggregate_id uuid NOT NULL, organization_id uuid NOT NULL,
          project_id uuid NOT NULL, classification varchar(64) NOT NULL,
          revision_no bigint NOT NULL, based_on_revision_id uuid NULL,
          schema_id varchar(255) NOT NULL, schema_version varchar(64) NOT NULL,
          content_hash char(64) COLLATE "C" NOT NULL, created_at timestamptz NOT NULL,
          created_by uuid NOT NULL, change_reason text NOT NULL, request_id uuid NOT NULL,
          trace_id varchar(255) NOT NULL, ogden_calibration_run_id uuid NOT NULL,
          ogden_calibration_candidate_id uuid NOT NULL,
          candidate_sha256 char(64) COLLATE "C" NOT NULL,
          diagnostics_artifact_id uuid NOT NULL,
          diagnostics_sha256 char(64) COLLATE "C" NOT NULL,
          baseline_model_id uuid NOT NULL, baseline_model_revision_id uuid NOT NULL,
          selection_reason text NOT NULL, selection_decision varchar(100) NOT NULL,
          non_production boolean NOT NULL,
          CONSTRAINT pk_mdl_ogden_selection_rev PRIMARY KEY
            (organization_id, project_id, id),
          CONSTRAINT uq_mdl_ogden_selection_rev_ref UNIQUE
            (organization_id, project_id, aggregate_id, id),
          CONSTRAINT uq_mdl_ogden_selection_rev_scoped UNIQUE
            (organization_id, project_id, classification, aggregate_id, id),
          CONSTRAINT uq_mdl_ogden_selection_rev_no UNIQUE
            (organization_id, project_id, aggregate_id, revision_no),
          CONSTRAINT uq_mdl_ogden_selection_candidate UNIQUE
            (organization_id, project_id, classification, ogden_calibration_candidate_id),
          CONSTRAINT ck_mdl_ogden_selection_rev_shape CHECK
            (revision_no=1 AND based_on_revision_id IS NULL AND
             schema_id='urn:cmp:modeling:reference-ogden-candidate-selection:1.0.0' AND
             schema_version='1.0.0' AND content_hash ~ '^[0-9a-f]{64}$' AND
             candidate_sha256 ~ '^[0-9a-f]{64}$' AND
             diagnostics_sha256 ~ '^[0-9a-f]{64}$' AND
             length(btrim(selection_reason)) BETWEEN 1 AND 2000 AND
             selection_decision='accepted_for_ogden_prony_ir_revision' AND non_production),
          CONSTRAINT fk_mdl_ogden_selection_identity FOREIGN KEY
            (organization_id, project_id, aggregate_id)
            REFERENCES modeling.ogden_candidate_selection
            (organization_id, project_id, id) ON DELETE RESTRICT
            DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_mdl_ogden_selection_run FOREIGN KEY
            (organization_id, project_id, classification, ogden_calibration_run_id)
            REFERENCES modeling.ogden_calibration_run
            (organization_id, project_id, classification, id) ON DELETE RESTRICT,
          CONSTRAINT fk_mdl_ogden_selection_candidate FOREIGN KEY
            (organization_id, project_id, classification, ogden_calibration_candidate_id)
            REFERENCES modeling.ogden_calibration_candidate
            (organization_id, project_id, classification, id) ON DELETE RESTRICT,
          CONSTRAINT fk_mdl_ogden_selection_diagnostics FOREIGN KEY
            (organization_id, project_id, classification,
             diagnostics_artifact_id, diagnostics_sha256)
            REFERENCES artifact.artifact
            (organization_id, project_id, classification, id, sha256) ON DELETE RESTRICT,
          CONSTRAINT fk_mdl_ogden_selection_model FOREIGN KEY
            (organization_id, project_id, classification,
             baseline_model_id, baseline_model_revision_id)
            REFERENCES modeling.ogden_prony_revision
            (organization_id, project_id, classification,
             material_model_id, material_model_revision_id) ON DELETE RESTRICT
        );

        ALTER TABLE modeling.ogden_candidate_selection
          ADD CONSTRAINT fk_mdl_ogden_selection_current FOREIGN KEY
          (organization_id, project_id, id, current_revision_id)
          REFERENCES modeling.ogden_candidate_selection_revision
          (organization_id, project_id, aggregate_id, id)
          ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED;

        CREATE TABLE modeling.ogden_promotion_evidence (
          organization_id uuid NOT NULL, project_id uuid NOT NULL,
          classification varchar(64) NOT NULL, material_model_id uuid NOT NULL,
          material_model_revision_id uuid NOT NULL,
          promoted_from_model_revision_id uuid NOT NULL,
          selection_id uuid NOT NULL, selection_revision_id uuid NOT NULL,
          calibration_run_id uuid NOT NULL, calibration_candidate_id uuid NOT NULL,
          candidate_sha256 char(64) COLLATE "C" NOT NULL,
          diagnostics_artifact_id uuid NOT NULL,
          diagnostics_sha256 char(64) COLLATE "C" NOT NULL,
          CONSTRAINT pk_mdl_ogden_promotion PRIMARY KEY
            (organization_id, project_id, material_model_revision_id),
          CONSTRAINT uq_mdl_ogden_promotion_scoped UNIQUE
            (organization_id, project_id, classification,
             material_model_id, material_model_revision_id),
          CONSTRAINT uq_mdl_ogden_promotion_candidate UNIQUE
            (organization_id, project_id, classification, calibration_candidate_id),
          CONSTRAINT uq_mdl_ogden_promotion_selection UNIQUE
            (organization_id, project_id, classification,
             selection_id, selection_revision_id),
          CONSTRAINT ck_mdl_ogden_promotion_sha CHECK
            (candidate_sha256 ~ '^[0-9a-f]{64}$' AND
             diagnostics_sha256 ~ '^[0-9a-f]{64}$' AND
             material_model_revision_id<>promoted_from_model_revision_id),
          CONSTRAINT fk_mdl_ogden_promotion_owner FOREIGN KEY
            (organization_id, project_id, classification,
             material_model_id, material_model_revision_id)
            REFERENCES modeling.ogden_prony_revision
            (organization_id, project_id, classification,
             material_model_id, material_model_revision_id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_mdl_ogden_promotion_prior FOREIGN KEY
            (organization_id, project_id, classification,
             material_model_id, promoted_from_model_revision_id)
            REFERENCES modeling.ogden_prony_revision
            (organization_id, project_id, classification,
             material_model_id, material_model_revision_id) ON DELETE RESTRICT,
          CONSTRAINT fk_mdl_ogden_promotion_selection FOREIGN KEY
            (organization_id, project_id, classification,
             selection_id, selection_revision_id)
            REFERENCES modeling.ogden_candidate_selection_revision
            (organization_id, project_id, classification, aggregate_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_mdl_ogden_promotion_run FOREIGN KEY
            (organization_id, project_id, classification, calibration_run_id)
            REFERENCES modeling.ogden_calibration_run
            (organization_id, project_id, classification, id) ON DELETE RESTRICT,
          CONSTRAINT fk_mdl_ogden_promotion_candidate FOREIGN KEY
            (organization_id, project_id, classification, calibration_candidate_id)
            REFERENCES modeling.ogden_calibration_candidate
            (organization_id, project_id, classification, id) ON DELETE RESTRICT,
          CONSTRAINT fk_mdl_ogden_promotion_diagnostics FOREIGN KEY
            (organization_id, project_id, classification,
             diagnostics_artifact_id, diagnostics_sha256)
            REFERENCES artifact.artifact
            (organization_id, project_id, classification, id, sha256) ON DELETE RESTRICT
        );

        CREATE INDEX ix_mdl_ogden_selection_run
          ON modeling.ogden_candidate_selection
          (organization_id, project_id, ogden_calibration_run_id);
        CREATE INDEX ix_mdl_ogden_promotion_model
          ON modeling.ogden_promotion_evidence
          (organization_id, project_id, material_model_id, material_model_revision_id);
        """
    )
    op.execute(
        """
        CREATE FUNCTION modeling.validate_ogden_candidate_selection()
        RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE run_row record; candidate_row record;
        BEGIN
          SELECT status, baseline_model_id, baseline_model_revision_id
            INTO run_row FROM modeling.ogden_calibration_run
           WHERE organization_id=NEW.organization_id AND project_id=NEW.project_id
             AND classification=NEW.classification AND id=NEW.ogden_calibration_run_id;
          SELECT calibration_run_id, status, candidate_sha256,
                 diagnostics_artifact_id, diagnostics_sha256
            INTO candidate_row FROM modeling.ogden_calibration_candidate
           WHERE organization_id=NEW.organization_id AND project_id=NEW.project_id
             AND classification=NEW.classification
             AND id=NEW.ogden_calibration_candidate_id;
          IF run_row.status IS DISTINCT FROM 'succeeded'
             OR candidate_row.status IS DISTINCT FROM 'converged'
             OR candidate_row.calibration_run_id IS DISTINCT FROM
                NEW.ogden_calibration_run_id
             OR candidate_row.candidate_sha256 IS DISTINCT FROM NEW.candidate_sha256
             OR candidate_row.diagnostics_artifact_id IS DISTINCT FROM
                NEW.diagnostics_artifact_id
             OR candidate_row.diagnostics_sha256 IS DISTINCT FROM NEW.diagnostics_sha256
             OR run_row.baseline_model_id IS DISTINCT FROM NEW.baseline_model_id
             OR run_row.baseline_model_revision_id IS DISTINCT FROM
                NEW.baseline_model_revision_id THEN
            RAISE EXCEPTION 'Ogden Selection lineage is inconsistent'
              USING ERRCODE='23514';
          END IF;
          RETURN NEW;
        END $$;
        CREATE TRIGGER modeling_ogden_selection_validate BEFORE INSERT
          ON modeling.ogden_candidate_selection_revision FOR EACH ROW
          EXECUTE FUNCTION modeling.validate_ogden_candidate_selection();

        CREATE FUNCTION modeling.validate_ogden_promotion_evidence()
        RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE owner_row record; selection_row record; run_row record;
        DECLARE candidate_row record; ogden_row record;
        BEGIN
          SELECT based_on_revision_id, schema_id, schema_version,
                 calibration_evidence_kind INTO owner_row
            FROM modeling.material_model_revision
           WHERE organization_id=NEW.organization_id AND project_id=NEW.project_id
             AND classification=NEW.classification
             AND aggregate_id=NEW.material_model_id
             AND id=NEW.material_model_revision_id;
          SELECT * INTO selection_row
            FROM modeling.ogden_candidate_selection_revision
           WHERE organization_id=NEW.organization_id AND project_id=NEW.project_id
             AND classification=NEW.classification AND aggregate_id=NEW.selection_id
             AND id=NEW.selection_revision_id;
          SELECT * INTO run_row FROM modeling.ogden_calibration_run
           WHERE organization_id=NEW.organization_id AND project_id=NEW.project_id
             AND classification=NEW.classification AND id=NEW.calibration_run_id;
          SELECT * INTO candidate_row FROM modeling.ogden_calibration_candidate
           WHERE organization_id=NEW.organization_id AND project_id=NEW.project_id
             AND classification=NEW.classification AND id=NEW.calibration_candidate_id;
          SELECT ogden_mu_pa, ogden_alpha INTO ogden_row
            FROM modeling.ogden_prony_revision
           WHERE organization_id=NEW.organization_id AND project_id=NEW.project_id
             AND classification=NEW.classification
             AND material_model_id=NEW.material_model_id
             AND material_model_revision_id=NEW.material_model_revision_id;
          IF owner_row.based_on_revision_id IS DISTINCT FROM
                NEW.promoted_from_model_revision_id
             OR owner_row.schema_id IS DISTINCT FROM
                'urn:cmp:modeling:reference-ogden-prony-hyperviscoelastic:1.1.0'
             OR owner_row.schema_version IS DISTINCT FROM '1.1.0'
             OR owner_row.calibration_evidence_kind IS DISTINCT FROM
                'reference_ogden_candidate_selection'
             OR selection_row.ogden_calibration_run_id IS DISTINCT FROM
                NEW.calibration_run_id
             OR selection_row.ogden_calibration_candidate_id IS DISTINCT FROM
                NEW.calibration_candidate_id
             OR selection_row.candidate_sha256 IS DISTINCT FROM NEW.candidate_sha256
             OR selection_row.diagnostics_artifact_id IS DISTINCT FROM
                NEW.diagnostics_artifact_id
             OR selection_row.diagnostics_sha256 IS DISTINCT FROM NEW.diagnostics_sha256
             OR selection_row.baseline_model_id IS DISTINCT FROM NEW.material_model_id
             OR selection_row.baseline_model_revision_id IS DISTINCT FROM
                NEW.promoted_from_model_revision_id
             OR run_row.status IS DISTINCT FROM 'succeeded'
             OR run_row.baseline_model_id IS DISTINCT FROM NEW.material_model_id
             OR run_row.baseline_model_revision_id IS DISTINCT FROM
                NEW.promoted_from_model_revision_id
             OR candidate_row.status IS DISTINCT FROM 'converged'
             OR candidate_row.calibration_run_id IS DISTINCT FROM NEW.calibration_run_id
             OR candidate_row.candidate_sha256 IS DISTINCT FROM NEW.candidate_sha256
             OR candidate_row.diagnostics_artifact_id IS DISTINCT FROM
                NEW.diagnostics_artifact_id
             OR candidate_row.diagnostics_sha256 IS DISTINCT FROM NEW.diagnostics_sha256
             OR ogden_row.ogden_mu_pa IS DISTINCT FROM candidate_row.mu_pa
             OR ogden_row.ogden_alpha IS DISTINCT FROM candidate_row.alpha THEN
            RAISE EXCEPTION 'Ogden promotion evidence is inconsistent'
              USING ERRCODE='23514';
          END IF;
          RETURN NEW;
        END $$;
        CREATE CONSTRAINT TRIGGER modeling_ogden_promotion_validate
          AFTER INSERT ON modeling.ogden_promotion_evidence
          DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
          EXECUTE FUNCTION modeling.validate_ogden_promotion_evidence();
        """
    )
    op.execute(
        "CREATE TRIGGER modeling_ogden_selection_head_only BEFORE UPDATE OR DELETE "
        "ON modeling.ogden_candidate_selection FOR EACH ROW "
        "EXECUTE FUNCTION revisioning.guard_identity_head_update()"
    )
    for table in (
        "ogden_candidate_selection_revision",
        "ogden_promotion_evidence",
    ):
        op.execute(
            f"CREATE TRIGGER modeling_{table}_immutable BEFORE UPDATE OR DELETE "
            f"ON modeling.{table} FOR EACH ROW "
            "EXECUTE FUNCTION revisioning.reject_immutable_row_mutation()"
        )
    _rls("ogden_candidate_selection", identity=True)
    _rls("ogden_candidate_selection_revision")
    _rls("ogden_promotion_evidence")


def downgrade() -> None:
    op.execute(
        """
        DO $$ BEGIN
          IF EXISTS (SELECT 1 FROM modeling.ogden_candidate_selection_revision)
             OR EXISTS (SELECT 1 FROM modeling.ogden_promotion_evidence) THEN
            RAISE EXCEPTION
              'cannot downgrade with immutable Ogden Selections or promotion evidence';
          END IF;
        END $$;
        """
    )
    op.execute(
        "DROP TRIGGER IF EXISTS modeling_ogden_promotion_validate "
        "ON modeling.ogden_promotion_evidence"
    )
    op.execute("DROP FUNCTION IF EXISTS modeling.validate_ogden_promotion_evidence()")
    op.execute("DROP TABLE modeling.ogden_promotion_evidence")
    op.execute(
        "ALTER TABLE modeling.ogden_candidate_selection "
        "DROP CONSTRAINT fk_mdl_ogden_selection_current"
    )
    op.execute("DROP TABLE modeling.ogden_candidate_selection_revision")
    op.execute("DROP TABLE modeling.ogden_candidate_selection")
    op.execute("DROP FUNCTION IF EXISTS modeling.validate_ogden_candidate_selection()")
    _evidence_constraints(include_ogden=False)

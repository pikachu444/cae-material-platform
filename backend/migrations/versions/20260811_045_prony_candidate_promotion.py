"""Add human Prony Candidate Selection and linear-Prony IR promotion evidence.

Revision ID: 20260811_045_prony_promote
Revises: 20260810_044_prony_cal
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260811_045_prony_promote"
down_revision: str | None = "20260810_044_prony_cal"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _secure(table: str, *, mutable: bool = False) -> None:
    for operation, permission in (("select", "modeling.read"), ("insert", "modeling.write")):
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
            "classification, 'modeling.write')) WITH CHECK "
            "(access_control.can_access_row(organization_id, project_id, "
            "classification, 'modeling.write'))"
        )
    op.execute(f"ALTER TABLE modeling.{table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE modeling.{table} FORCE ROW LEVEL SECURITY")


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE modeling.prony_candidate_selection (
          id uuid NOT NULL, organization_id uuid NOT NULL, project_id uuid NOT NULL,
          classification varchar(64) NOT NULL, current_revision_id uuid NOT NULL,
          created_at timestamptz NOT NULL, created_by uuid NOT NULL,
          updated_at timestamptz NOT NULL, selection_label varchar(160) NOT NULL,
          prony_calibration_run_id uuid NOT NULL,
          CONSTRAINT pk_mdl_prony_selection PRIMARY KEY (organization_id, project_id, id),
          CONSTRAINT uq_mdl_prony_selection_scoped UNIQUE
            (organization_id, project_id, classification, id),
          CONSTRAINT uq_mdl_prony_selection_label UNIQUE
            (organization_id, project_id, classification, selection_label),
          CONSTRAINT ck_mdl_prony_selection_shape CHECK
            (length(btrim(selection_label)) BETWEEN 1 AND 160)
        );
        CREATE TABLE modeling.prony_candidate_selection_revision (
          id uuid NOT NULL, aggregate_id uuid NOT NULL, organization_id uuid NOT NULL,
          project_id uuid NOT NULL, classification varchar(64) NOT NULL,
          revision_no bigint NOT NULL, based_on_revision_id uuid NULL,
          schema_id varchar(255) NOT NULL, schema_version varchar(64) NOT NULL,
          content_hash char(64) COLLATE "C" NOT NULL, created_at timestamptz NOT NULL,
          created_by uuid NOT NULL, change_reason text NOT NULL, request_id uuid NOT NULL,
          trace_id varchar(255) NOT NULL, prony_calibration_run_id uuid NOT NULL,
          prony_calibration_candidate_id uuid NOT NULL,
          candidate_sha256 char(64) COLLATE "C" NOT NULL,
          baseline_model_id uuid NOT NULL, baseline_model_revision_id uuid NOT NULL,
          selection_reason text NOT NULL, selection_decision varchar(100) NOT NULL,
          non_production boolean NOT NULL,
          CONSTRAINT pk_mdl_prony_selection_rev PRIMARY KEY (organization_id, project_id, id),
          CONSTRAINT uq_mdl_prony_selection_rev_ref UNIQUE
            (organization_id, project_id, aggregate_id, id),
          CONSTRAINT uq_mdl_prony_selection_rev_scoped UNIQUE
            (organization_id, project_id, classification, aggregate_id, id),
          CONSTRAINT uq_mdl_prony_selection_rev_no UNIQUE
            (organization_id, project_id, aggregate_id, revision_no),
          CONSTRAINT uq_mdl_prony_selection_candidate UNIQUE
            (organization_id, project_id, classification, prony_calibration_candidate_id),
          CONSTRAINT ck_mdl_prony_selection_rev_shape CHECK
            (revision_no=1 AND based_on_revision_id IS NULL AND
             schema_id='urn:cmp:modeling:reference-prony-candidate-selection:1.0.0' AND
             schema_version='1.0.0' AND content_hash ~ '^[0-9a-f]{64}$' AND
             candidate_sha256 ~ '^[0-9a-f]{64}$' AND
             length(btrim(selection_reason)) BETWEEN 1 AND 2000 AND
             selection_decision='accepted_for_linear_prony_ir_revision' AND non_production),
          CONSTRAINT fk_mdl_prony_selection_rev_identity FOREIGN KEY
            (organization_id, project_id, aggregate_id)
            REFERENCES modeling.prony_candidate_selection
            (organization_id, project_id, id) ON DELETE RESTRICT
            DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_mdl_prony_selection_rev_run FOREIGN KEY
            (organization_id, project_id, classification, prony_calibration_run_id)
            REFERENCES modeling.prony_calibration_run
            (organization_id, project_id, classification, id) ON DELETE RESTRICT,
          CONSTRAINT fk_mdl_prony_selection_rev_candidate FOREIGN KEY
            (organization_id, project_id, classification, prony_calibration_candidate_id)
            REFERENCES modeling.prony_calibration_candidate
            (organization_id, project_id, classification, id) ON DELETE RESTRICT,
          CONSTRAINT fk_mdl_prony_selection_rev_model FOREIGN KEY
            (organization_id, project_id, classification,
             baseline_model_id, baseline_model_revision_id)
            REFERENCES modeling.linear_viscoelastic_revision
            (organization_id, project_id, classification,
             material_model_id, material_model_revision_id) ON DELETE RESTRICT
        );
        ALTER TABLE modeling.prony_candidate_selection
          ADD CONSTRAINT fk_mdl_prony_selection_current FOREIGN KEY
          (organization_id, project_id, id, current_revision_id)
          REFERENCES modeling.prony_candidate_selection_revision
          (organization_id, project_id, aggregate_id, id)
          ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED;

        ALTER TABLE modeling.material_model_revision
          ADD COLUMN prony_selection_id uuid NULL,
          ADD COLUMN prony_selection_revision_id uuid NULL,
          ADD COLUMN prony_calibration_run_id uuid NULL,
          ADD COLUMN prony_calibration_candidate_id uuid NULL,
          ADD COLUMN prony_calibration_candidate_sha256 char(64) COLLATE "C" NULL,
          ADD COLUMN prony_diagnostics_artifact_id uuid NULL,
          ADD COLUMN prony_diagnostics_sha256 char(64) COLLATE "C" NULL;
        ALTER TABLE modeling.material_model_revision
          DROP CONSTRAINT ck_modeling_material_model_calibration_evidence_shape,
          DROP CONSTRAINT ck_modeling_material_model_calibration_evidence_kind;
        ALTER TABLE modeling.material_model_revision
          ADD CONSTRAINT ck_modeling_material_model_calibration_evidence_kind CHECK
            (calibration_evidence_kind IN
              ('manual_catalog_projection','reference_candidate_selection',
               'reference_prony_candidate_selection')),
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
             AND prony_diagnostics_artifact_id IS NULL AND prony_diagnostics_sha256 IS NULL)
            OR
            (calibration_evidence_kind='reference_candidate_selection'
             AND calibration_selection_id IS NOT NULL
             AND calibration_selection_revision_id IS NOT NULL
             AND calibration_run_id IS NOT NULL AND calibration_candidate_id IS NOT NULL
             AND calibration_candidate_sha256 ~ '^[0-9a-f]{64}$'
             AND calibration_diagnostics_artifact_id IS NOT NULL
             AND calibration_diagnostics_sha256 ~ '^[0-9a-f]{64}$'
             AND prony_selection_id IS NULL AND prony_selection_revision_id IS NULL
             AND prony_calibration_run_id IS NULL
             AND prony_calibration_candidate_id IS NULL
             AND prony_calibration_candidate_sha256 IS NULL
             AND prony_diagnostics_artifact_id IS NULL AND prony_diagnostics_sha256 IS NULL)
            OR
            (calibration_evidence_kind='reference_prony_candidate_selection'
             AND calibration_selection_id IS NULL
             AND calibration_selection_revision_id IS NULL
             AND calibration_run_id IS NULL AND calibration_candidate_id IS NULL
             AND calibration_candidate_sha256 IS NULL
             AND calibration_diagnostics_artifact_id IS NULL
             AND calibration_diagnostics_sha256 IS NULL
             AND prony_selection_id IS NOT NULL AND prony_selection_revision_id IS NOT NULL
             AND prony_calibration_run_id IS NOT NULL
             AND prony_calibration_candidate_id IS NOT NULL
             AND prony_calibration_candidate_sha256 ~ '^[0-9a-f]{64}$'
             AND prony_diagnostics_artifact_id IS NOT NULL
             AND prony_diagnostics_sha256 ~ '^[0-9a-f]{64}$')),
          ADD CONSTRAINT fk_mdl_model_prony_selection FOREIGN KEY
            (organization_id, project_id, classification,
             prony_selection_id, prony_selection_revision_id)
            REFERENCES modeling.prony_candidate_selection_revision
            (organization_id, project_id, classification, aggregate_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          ADD CONSTRAINT fk_mdl_model_prony_candidate FOREIGN KEY
            (organization_id, project_id, classification, prony_calibration_candidate_id)
            REFERENCES modeling.prony_calibration_candidate
            (organization_id, project_id, classification, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          ADD CONSTRAINT fk_mdl_model_prony_diagnostics FOREIGN KEY
            (organization_id, project_id, classification,
             prony_diagnostics_artifact_id, prony_diagnostics_sha256)
            REFERENCES artifact.artifact
            (organization_id, project_id, classification, id, sha256)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED;
        CREATE INDEX ix_mdl_model_prony_candidate
          ON modeling.material_model_revision
          (organization_id, project_id, prony_calibration_candidate_id)
          WHERE prony_calibration_candidate_id IS NOT NULL;
        """
    )
    op.execute(
        """
        DROP TRIGGER modeling_reference_calibrated_model_revision_guard
          ON modeling.material_model_revision;
        CREATE TRIGGER modeling_reference_calibrated_model_revision_guard
          BEFORE INSERT ON modeling.material_model_revision FOR EACH ROW
          WHEN (NEW.calibration_evidence_kind IN
            ('manual_catalog_projection', 'reference_candidate_selection'))
          EXECUTE FUNCTION modeling.guard_reference_calibrated_model_revision_insert();

        CREATE FUNCTION modeling.validate_prony_candidate_selection_revision()
        RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE run_row record; candidate_row record;
        BEGIN
          SELECT status, baseline_model_id, baseline_model_revision_id
            INTO run_row FROM modeling.prony_calibration_run
           WHERE organization_id=NEW.organization_id AND project_id=NEW.project_id
             AND classification=NEW.classification AND id=NEW.prony_calibration_run_id;
          SELECT calibration_run_id, status, candidate_sha256
            INTO candidate_row FROM modeling.prony_calibration_candidate
           WHERE organization_id=NEW.organization_id AND project_id=NEW.project_id
             AND classification=NEW.classification AND id=NEW.prony_calibration_candidate_id;
          IF run_row.status IS DISTINCT FROM 'succeeded'
             OR candidate_row.status IS DISTINCT FROM 'converged'
             OR candidate_row.calibration_run_id IS DISTINCT FROM NEW.prony_calibration_run_id
             OR candidate_row.candidate_sha256 IS DISTINCT FROM NEW.candidate_sha256
             OR run_row.baseline_model_id IS DISTINCT FROM NEW.baseline_model_id
             OR run_row.baseline_model_revision_id IS DISTINCT FROM
                NEW.baseline_model_revision_id THEN
            RAISE EXCEPTION 'invalid exact Prony Candidate Selection lineage'
              USING ERRCODE='23514';
          END IF;
          RETURN NEW;
        END $$;
        CREATE TRIGGER modeling_validate_prony_candidate_selection_revision
          BEFORE INSERT ON modeling.prony_candidate_selection_revision FOR EACH ROW
          EXECUTE FUNCTION modeling.validate_prony_candidate_selection_revision();

        CREATE FUNCTION modeling.validate_prony_promoted_model_revision()
        RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE selection_row record; candidate_row record;
        BEGIN
          IF NEW.calibration_evidence_kind<>'reference_prony_candidate_selection' THEN
            RETURN NEW;
          END IF;
          SELECT prony_calibration_run_id, prony_calibration_candidate_id, candidate_sha256,
                 baseline_model_id, baseline_model_revision_id
            INTO selection_row FROM modeling.prony_candidate_selection_revision
           WHERE organization_id=NEW.organization_id AND project_id=NEW.project_id
             AND classification=NEW.classification AND aggregate_id=NEW.prony_selection_id
             AND id=NEW.prony_selection_revision_id;
          SELECT calibration_run_id, candidate_sha256, diagnostics_artifact_id,
                 diagnostics_sha256, status
            INTO candidate_row FROM modeling.prony_calibration_candidate
           WHERE organization_id=NEW.organization_id AND project_id=NEW.project_id
             AND classification=NEW.classification AND id=NEW.prony_calibration_candidate_id;
          IF NEW.schema_id IS DISTINCT FROM
               'urn:cmp:modeling:reference-isotropic-linear-viscoelastic-prony:1.1.0'
             OR NEW.schema_version IS DISTINCT FROM '1.1.0'
             OR selection_row.prony_calibration_run_id IS DISTINCT FROM
                NEW.prony_calibration_run_id
             OR selection_row.prony_calibration_candidate_id IS DISTINCT FROM
                NEW.prony_calibration_candidate_id
             OR selection_row.candidate_sha256 IS DISTINCT FROM
                NEW.prony_calibration_candidate_sha256
             OR selection_row.baseline_model_id IS DISTINCT FROM NEW.aggregate_id
             OR selection_row.baseline_model_revision_id IS DISTINCT FROM
                NEW.based_on_revision_id
             OR candidate_row.calibration_run_id IS DISTINCT FROM
                NEW.prony_calibration_run_id
             OR candidate_row.candidate_sha256 IS DISTINCT FROM
                NEW.prony_calibration_candidate_sha256
             OR candidate_row.diagnostics_artifact_id IS DISTINCT FROM
                NEW.prony_diagnostics_artifact_id
             OR candidate_row.diagnostics_sha256 IS DISTINCT FROM
                NEW.prony_diagnostics_sha256
             OR candidate_row.status IS DISTINCT FROM 'converged' THEN
            RAISE EXCEPTION 'invalid exact Prony promotion lineage' USING ERRCODE='23514';
          END IF;
          RETURN NEW;
        END $$;
        CREATE TRIGGER modeling_validate_prony_promoted_model_revision
          BEFORE INSERT ON modeling.material_model_revision FOR EACH ROW
          EXECUTE FUNCTION modeling.validate_prony_promoted_model_revision();
        CREATE TRIGGER modeling_prony_selection_head
          BEFORE UPDATE OR DELETE ON modeling.prony_candidate_selection FOR EACH ROW
          EXECUTE FUNCTION revisioning.guard_identity_head_update();
        CREATE TRIGGER modeling_prony_selection_revision_immutable
          BEFORE UPDATE OR DELETE ON modeling.prony_candidate_selection_revision FOR EACH ROW
          EXECUTE FUNCTION revisioning.reject_immutable_row_mutation();
        """
    )
    _secure("prony_candidate_selection", mutable=True)
    _secure("prony_candidate_selection_revision")


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS modeling.validate_prony_promoted_model_revision() CASCADE")
    op.execute(
        "DROP FUNCTION IF EXISTS modeling.validate_prony_candidate_selection_revision() CASCADE"
    )
    op.execute(
        "ALTER TABLE modeling.prony_candidate_selection "
        "DROP CONSTRAINT IF EXISTS fk_mdl_prony_selection_current"
    )
    op.execute(
        """
        ALTER TABLE modeling.material_model_revision
          DROP CONSTRAINT IF EXISTS fk_mdl_model_prony_diagnostics,
          DROP CONSTRAINT IF EXISTS fk_mdl_model_prony_candidate,
          DROP CONSTRAINT IF EXISTS fk_mdl_model_prony_selection,
          DROP CONSTRAINT IF EXISTS ck_modeling_material_model_calibration_evidence_shape,
          DROP CONSTRAINT IF EXISTS ck_modeling_material_model_calibration_evidence_kind,
          DROP COLUMN IF EXISTS prony_diagnostics_sha256,
          DROP COLUMN IF EXISTS prony_diagnostics_artifact_id,
          DROP COLUMN IF EXISTS prony_calibration_candidate_sha256,
          DROP COLUMN IF EXISTS prony_calibration_candidate_id,
          DROP COLUMN IF EXISTS prony_calibration_run_id,
          DROP COLUMN IF EXISTS prony_selection_revision_id,
          DROP COLUMN IF EXISTS prony_selection_id;
        ALTER TABLE modeling.material_model_revision
          ADD CONSTRAINT ck_modeling_material_model_calibration_evidence_kind CHECK
            (calibration_evidence_kind IN
              ('manual_catalog_projection','reference_candidate_selection')),
          ADD CONSTRAINT ck_modeling_material_model_calibration_evidence_shape CHECK (
            (calibration_evidence_kind='manual_catalog_projection'
             AND calibration_selection_id IS NULL
             AND calibration_selection_revision_id IS NULL
             AND calibration_run_id IS NULL AND calibration_candidate_id IS NULL
             AND calibration_candidate_sha256 IS NULL
             AND calibration_diagnostics_artifact_id IS NULL
             AND calibration_diagnostics_sha256 IS NULL)
            OR
            (calibration_evidence_kind='reference_candidate_selection'
             AND calibration_selection_id IS NOT NULL
             AND calibration_selection_revision_id IS NOT NULL
             AND calibration_run_id IS NOT NULL AND calibration_candidate_id IS NOT NULL
             AND calibration_candidate_sha256 ~ '^[0-9a-f]{64}$'
             AND calibration_diagnostics_artifact_id IS NOT NULL
             AND calibration_diagnostics_sha256 ~ '^[0-9a-f]{64}$'));
        DROP TABLE IF EXISTS modeling.prony_candidate_selection_revision CASCADE;
        DROP TABLE IF EXISTS modeling.prony_candidate_selection CASCADE;
        """
    )

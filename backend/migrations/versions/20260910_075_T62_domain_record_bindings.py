"""T-62 exact configurable Record revision to governed domain revision bindings."""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260910_075_t62_binding"
down_revision: str | None = "20260909_074_t59"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE catalog.domain_record_binding (
          id uuid PRIMARY KEY,
          organization_id uuid NOT NULL,
          project_id uuid NOT NULL,
          classification varchar(64) NOT NULL,
          record_id uuid NOT NULL,
          record_revision_id uuid NOT NULL,
          domain_kind varchar(32) NOT NULL,
          domain_object_id uuid NOT NULL,
          domain_revision_id uuid NOT NULL,
          created_at timestamptz NOT NULL,
          created_by uuid NOT NULL REFERENCES identity.principal(id) ON DELETE RESTRICT,
          request_id uuid NOT NULL,
          trace_id varchar(255) NOT NULL,
          CONSTRAINT uq_catalog_domain_binding_record_revision UNIQUE
            (organization_id, project_id, classification, record_id, record_revision_id),
          CONSTRAINT uq_catalog_domain_binding_domain_revision UNIQUE
            (organization_id, project_id, classification, domain_kind,
             domain_object_id, domain_revision_id),
          CONSTRAINT fk_catalog_domain_binding_record_revision FOREIGN KEY
            (organization_id, project_id, classification, record_id, record_revision_id)
            REFERENCES catalog.catalog_record_revision
              (organization_id, project_id, classification, aggregate_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT ck_catalog_domain_binding_kind CHECK (domain_kind IN (
            'material', 'material_state', 'specimen', 'test_run', 'test_data',
            'processing_output', 'material_model', 'neutral_material',
            'solver_card', 'neutral_solver_card', 'release')),
          CONSTRAINT ck_catalog_domain_binding_trace CHECK
            (length(btrim(trace_id)) BETWEEN 1 AND 255)
        );

        CREATE INDEX ix_catalog_domain_binding_target ON catalog.domain_record_binding
          (organization_id, project_id, classification, domain_kind,
           domain_object_id, domain_revision_id);

        CREATE FUNCTION catalog.validate_domain_record_binding() RETURNS trigger
        LANGUAGE plpgsql AS $$
        DECLARE target_exists boolean := false;
        BEGIN
          IF NEW.domain_kind = 'material' THEN
            SELECT EXISTS (SELECT 1 FROM catalog.material_revision r WHERE
              (r.organization_id,r.project_id,r.classification,r.aggregate_id,r.id) =
              (NEW.organization_id,NEW.project_id,NEW.classification,
               NEW.domain_object_id,NEW.domain_revision_id)) INTO target_exists;
          ELSIF NEW.domain_kind = 'material_state' THEN
            SELECT EXISTS (SELECT 1 FROM catalog.material_state_revision r WHERE
              (r.organization_id,r.project_id,r.classification,r.aggregate_id,r.id) =
              (NEW.organization_id,NEW.project_id,NEW.classification,
               NEW.domain_object_id,NEW.domain_revision_id)) INTO target_exists;
          ELSIF NEW.domain_kind = 'specimen' THEN
            SELECT EXISTS (SELECT 1 FROM testing.specimen_revision r WHERE
              (r.organization_id,r.project_id,r.classification,r.aggregate_id,r.id) =
              (NEW.organization_id,NEW.project_id,NEW.classification,
               NEW.domain_object_id,NEW.domain_revision_id)) INTO target_exists;
          ELSIF NEW.domain_kind = 'test_run' THEN
            SELECT EXISTS (SELECT 1 FROM testing.test_run_revision r WHERE
              (r.organization_id,r.project_id,r.classification,r.aggregate_id,r.id) =
              (NEW.organization_id,NEW.project_id,NEW.classification,
               NEW.domain_object_id,NEW.domain_revision_id)) INTO target_exists;
          ELSIF NEW.domain_kind = 'test_data' THEN
            SELECT EXISTS (SELECT 1 FROM datasets.test_data_document_revision r WHERE
              (r.organization_id,r.project_id,r.classification,r.aggregate_id,r.id) =
              (NEW.organization_id,NEW.project_id,NEW.classification,
               NEW.domain_object_id,NEW.domain_revision_id)) INTO target_exists;
          ELSIF NEW.domain_kind = 'processing_output' THEN
            SELECT EXISTS (SELECT 1 FROM processing.common_processing_output_revision r WHERE
              (r.organization_id,r.project_id,r.classification,r.aggregate_id,r.id) =
              (NEW.organization_id,NEW.project_id,NEW.classification,
               NEW.domain_object_id,NEW.domain_revision_id)) INTO target_exists;
          ELSIF NEW.domain_kind = 'material_model' THEN
            SELECT EXISTS (SELECT 1 FROM modeling.material_model_revision r WHERE
              (r.organization_id,r.project_id,r.classification,r.aggregate_id,r.id) =
              (NEW.organization_id,NEW.project_id,NEW.classification,
               NEW.domain_object_id,NEW.domain_revision_id)) INTO target_exists;
          ELSIF NEW.domain_kind = 'neutral_material' THEN
            SELECT EXISTS (SELECT 1 FROM modeling.neutral_material_revision r WHERE
              (r.organization_id,r.project_id,r.classification,r.aggregate_id,r.id) =
              (NEW.organization_id,NEW.project_id,NEW.classification,
               NEW.domain_object_id,NEW.domain_revision_id)) INTO target_exists;
          ELSIF NEW.domain_kind = 'solver_card' THEN
            SELECT EXISTS (SELECT 1 FROM exporting.solver_card_revision r WHERE
              (r.organization_id,r.project_id,r.classification,r.aggregate_id,r.id) =
              (NEW.organization_id,NEW.project_id,NEW.classification,
               NEW.domain_object_id,NEW.domain_revision_id)) INTO target_exists;
          ELSIF NEW.domain_kind = 'neutral_solver_card' THEN
            SELECT EXISTS (SELECT 1 FROM exporting.neutral_solver_card_revision r WHERE
              (r.organization_id,r.project_id,r.classification,r.aggregate_id,r.id) =
              (NEW.organization_id,NEW.project_id,NEW.classification,
               NEW.domain_object_id,NEW.domain_revision_id)) INTO target_exists;
          ELSIF NEW.domain_kind = 'release' THEN
            SELECT EXISTS (SELECT 1 FROM governance.release_manifest r WHERE
              r.organization_id = NEW.organization_id AND r.project_id = NEW.project_id
              AND r.classification = NEW.classification
              AND r.release_id = NEW.domain_object_id AND r.id = NEW.domain_revision_id)
              INTO target_exists;
          END IF;
          IF NOT target_exists THEN
            RAISE EXCEPTION USING ERRCODE='23503',
              MESSAGE='domain binding target must be an exact revision in the same scope';
          END IF;
          RETURN NEW;
        END $$;

        CREATE TRIGGER domain_record_binding_validate BEFORE INSERT
          ON catalog.domain_record_binding FOR EACH ROW
          EXECUTE FUNCTION catalog.validate_domain_record_binding();
        CREATE TRIGGER domain_record_binding_immutable BEFORE UPDATE OR DELETE
          ON catalog.domain_record_binding FOR EACH ROW
          EXECUTE FUNCTION revisioning.reject_immutable_row_mutation();

        ALTER TABLE catalog.domain_record_binding ENABLE ROW LEVEL SECURITY;
        ALTER TABLE catalog.domain_record_binding FORCE ROW LEVEL SECURITY;
        CREATE POLICY domain_record_binding_select ON catalog.domain_record_binding
          FOR SELECT USING (access_control.can_access_row(
            organization_id, project_id, classification, 'catalog.read'));
        CREATE POLICY domain_record_binding_insert ON catalog.domain_record_binding
          FOR INSERT WITH CHECK (access_control.can_access_row(
            organization_id, project_id, classification, 'catalog.write'));
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP TABLE catalog.domain_record_binding;
        DROP FUNCTION catalog.validate_domain_record_binding();
        """
    )

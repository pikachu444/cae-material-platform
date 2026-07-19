"""Keep one Catalog identity per domain revision across Catalog revisions.

Revision ID: 20260917_082_t76_current_binding
Revises: 20260916_081_t70_metal_origin

Traceability: T-76.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260917_082_t76_current_binding"
down_revision: str | None = "20260916_081_t70_metal_origin"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE catalog.domain_record_identity_binding (
          organization_id uuid NOT NULL,
          project_id uuid NOT NULL,
          classification varchar(64) NOT NULL,
          domain_kind varchar(32) NOT NULL,
          domain_object_id uuid NOT NULL,
          domain_revision_id uuid NOT NULL,
          record_id uuid NOT NULL,
          created_at timestamptz NOT NULL,
          created_by uuid NOT NULL REFERENCES identity.principal(id) ON DELETE RESTRICT,
          request_id uuid NOT NULL,
          trace_id varchar(255) NOT NULL,
          CONSTRAINT pk_catalog_domain_identity_binding PRIMARY KEY
            (organization_id, project_id, classification, domain_kind,
             domain_object_id, domain_revision_id),
          CONSTRAINT uq_catalog_domain_identity_binding_target_record UNIQUE
            (organization_id, project_id, classification, domain_kind,
             domain_object_id, domain_revision_id, record_id),
          CONSTRAINT fk_catalog_domain_identity_binding_record FOREIGN KEY
            (organization_id, project_id, classification, record_id)
            REFERENCES catalog.catalog_record
              (organization_id, project_id, classification, id)
            ON DELETE RESTRICT,
          CONSTRAINT ck_catalog_domain_identity_binding_kind CHECK (domain_kind IN (
            'material', 'material_state', 'specimen', 'test_run', 'test_data',
            'processing_output', 'material_model', 'neutral_material',
            'solver_card', 'neutral_solver_card', 'release')),
          CONSTRAINT ck_catalog_domain_identity_binding_trace CHECK
            (length(btrim(trace_id)) BETWEEN 1 AND 255)
        );

        INSERT INTO catalog.domain_record_identity_binding
          (organization_id, project_id, classification, domain_kind,
           domain_object_id, domain_revision_id, record_id, created_at,
           created_by, request_id, trace_id)
        SELECT organization_id, project_id, classification, domain_kind,
               domain_object_id, domain_revision_id, record_id, created_at,
               created_by, request_id, trace_id
          FROM catalog.domain_record_binding;

        ALTER TABLE catalog.domain_record_binding
          DROP CONSTRAINT uq_catalog_domain_binding_domain_revision;
        ALTER TABLE catalog.domain_record_binding
          ADD CONSTRAINT fk_catalog_domain_binding_identity_target FOREIGN KEY
            (organization_id, project_id, classification, domain_kind,
             domain_object_id, domain_revision_id, record_id)
            REFERENCES catalog.domain_record_identity_binding
              (organization_id, project_id, classification, domain_kind,
               domain_object_id, domain_revision_id, record_id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED;

        CREATE TRIGGER domain_record_identity_binding_immutable BEFORE UPDATE OR DELETE
          ON catalog.domain_record_identity_binding FOR EACH ROW
          EXECUTE FUNCTION revisioning.reject_immutable_row_mutation();

        ALTER TABLE catalog.domain_record_identity_binding ENABLE ROW LEVEL SECURITY;
        ALTER TABLE catalog.domain_record_identity_binding FORCE ROW LEVEL SECURITY;
        CREATE POLICY domain_record_identity_binding_select
          ON catalog.domain_record_identity_binding FOR SELECT
          USING (access_control.can_access_row(
            organization_id, project_id, classification, 'catalog.read'));
        CREATE POLICY domain_record_identity_binding_insert
          ON catalog.domain_record_identity_binding FOR INSERT
          WITH CHECK (access_control.can_access_row(
            organization_id, project_id, classification, 'catalog.write'));
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE catalog.domain_record_binding
          DROP CONSTRAINT fk_catalog_domain_binding_identity_target;
        ALTER TABLE catalog.domain_record_binding NO FORCE ROW LEVEL SECURITY;
        ALTER TABLE catalog.domain_record_binding
          DISABLE TRIGGER domain_record_binding_immutable;
        DELETE FROM catalog.domain_record_binding newer
          USING catalog.domain_record_binding older
         WHERE (newer.organization_id, newer.project_id, newer.classification,
                newer.domain_kind, newer.domain_object_id, newer.domain_revision_id) =
               (older.organization_id, older.project_id, older.classification,
                older.domain_kind, older.domain_object_id, older.domain_revision_id)
           AND (newer.created_at, newer.id) > (older.created_at, older.id);
        ALTER TABLE catalog.domain_record_binding
          ENABLE TRIGGER domain_record_binding_immutable;
        ALTER TABLE catalog.domain_record_binding FORCE ROW LEVEL SECURITY;
        ALTER TABLE catalog.domain_record_binding
          ADD CONSTRAINT uq_catalog_domain_binding_domain_revision UNIQUE
            (organization_id, project_id, classification, domain_kind,
             domain_object_id, domain_revision_id);
        DROP TABLE catalog.domain_record_identity_binding;
        """
    )

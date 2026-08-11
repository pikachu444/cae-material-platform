"""Issue #160 review-backed publication, activity context, and Admin preset v2.

The migration is deliberately append-only at the product boundary.  Existing Administrator
rows are retained as revoked v1 evidence and a deterministic corrected successor is appended for
rows which were still active at the transition instant.  No historical grant/reason/expiry fields
are rewritten.
"""
# ruff: noqa: E501

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260925_094_issue160"
down_revision: str | None = "20260924_093_issue158_metal_fit"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ACTOR = "16000000-0000-4000-8000-000000000160"


def upgrade() -> None:
    # A Catalog Record revision may pin several exact governed revisions (for example a
    # Neutral Material and the immutable Solver Card delivered from it).  T-62's original
    # Record-revision-only uniqueness contradicted that contract; retain only exact duplicate
    # protection while preserving the immutable identity/domain uniqueness constraints.
    op.execute(
        """
        ALTER TABLE catalog.domain_record_binding
          DROP CONSTRAINT IF EXISTS uq_catalog_domain_binding_record_revision;
        ALTER TABLE catalog.domain_record_binding
          ADD CONSTRAINT uq_catalog_domain_binding_exact_revision UNIQUE
            (organization_id, project_id, classification, record_id, record_revision_id,
             domain_kind, domain_object_id, domain_revision_id);
        """
    )
    op.add_column(
        "product_access_assignment",
        sa.Column("preset_version", sa.SmallInteger(), nullable=False, server_default="1"),
        schema="identity",
    )
    # The predecessor constraint describes the five-grant v1 Administrator preset and
    # would reject a corrected v2 successor.  Install a temporary version-aware shape
    # before dropping it, so every existing row remains valid throughout the transition.
    op.create_check_constraint(
        "ck_product_access_admin_transition",
        "product_access_assignment",
        "product_role <> 'administrator' OR "
        "(preset_version = 1 AND schema_configuration AND catalog_edit "
        "AND processing_calibration AND model_approval AND solver_card_export) OR "
        "(preset_version = 2 AND schema_configuration AND catalog_edit "
        "AND processing_calibration AND NOT model_approval AND solver_card_export)",
        schema="identity",
    )
    op.drop_constraint(
        "ck_product_access_administrator_features",
        "product_access_assignment",
        schema="identity",
        if_exists=True,
    )
    op.drop_constraint("ck_product_access_role", "product_access_assignment", schema="identity")
    op.create_check_constraint(
        "ck_product_access_role_v2",
        "product_access_assignment",
        "product_role IN ('administrator', 'reviewer', 'user')",
        schema="identity",
    )
    # The migration actor is deterministic, inactive, and intentionally has no external
    # identity or access assignment.  It exists only to make the append-only transition auditable.
    op.execute(
        f"""
        INSERT INTO identity.principal
          (id, principal_type, display_name, active, created_at, updated_at)
        VALUES ('{_ACTOR}'::uuid, 'service', 'Issue #160 preset transition', false, now(), now())
        ON CONFLICT (id) DO NOTHING
        """
    )
    op.execute(
        """
        ALTER TABLE identity.product_access_assignment
          ALTER COLUMN preset_version SET DEFAULT 2
        """
    )
    # Transition every unrevoked legacy Administrator atomically.  Expired rows receive no
    # successor; current rows become valid at the transition; future rows retain their original
    # valid_from so the corrected successor has the same planned activation.
    op.execute(
        f"""
        DO $$
        DECLARE
          item record;
          transition_at timestamptz := now();
          successor uuid;
        BEGIN
          FOR item IN
            SELECT * FROM identity.product_access_assignment
             WHERE product_role = 'administrator'
               AND preset_version = 1
               AND revoked_at IS NULL
          LOOP
            UPDATE identity.product_access_assignment
               SET revoked_at = transition_at,
                   revoked_by = '{_ACTOR}'::uuid,
                   revocation_reason = 'Issue #160: corrected Administrator preset transition'
             WHERE id = item.id;

            IF item.expires_at IS NOT NULL AND item.expires_at <= transition_at THEN
              CONTINUE;
            END IF;
            successor := md5('issue160:administrator:v2:' || item.id::text)::uuid;
            INSERT INTO identity.product_access_assignment
              (id, organization_id, project_id, classification, subject_type, principal_id,
               group_issuer, group_name, product_role, schema_configuration, catalog_edit,
               processing_calibration, model_approval, solver_card_export, max_classification,
               allow_export_controlled, valid_from, expires_at, created_at, created_by,
               grant_reason, revoked_at, revoked_by, revocation_reason, preset_version)
            VALUES
              (successor, item.organization_id, item.project_id, item.classification,
               item.subject_type, item.principal_id, item.group_issuer, item.group_name,
               'administrator', true, true, true, false, true, item.max_classification,
               item.allow_export_controlled,
               CASE WHEN item.valid_from > transition_at THEN item.valid_from ELSE transition_at END,
               item.expires_at, transition_at, '{_ACTOR}'::uuid,
               'Issue #160: corrected Administrator preset successor; predecessor ' || item.id::text,
               NULL, NULL, NULL, 2);
          END LOOP;
        END
        $$
        """
    )
    # Replace the temporary transition check with exact versioned shapes.  v1 is historical
    # evidence only and must carry all three immutable revocation fields.
    op.drop_constraint(
        "ck_product_access_admin_transition",
        "product_access_assignment",
        schema="identity",
    )
    op.create_check_constraint(
        "ck_product_access_preset_version",
        "product_access_assignment",
        "preset_version IN (1, 2)",
        schema="identity",
    )
    op.create_check_constraint(
        "ck_product_access_admin_v1_legacy",
        "product_access_assignment",
        "product_role <> 'administrator' OR preset_version <> 1 OR "
        "(revoked_at IS NOT NULL AND revoked_by IS NOT NULL "
        "AND revocation_reason IS NOT NULL AND schema_configuration AND catalog_edit "
        "AND processing_calibration AND model_approval AND solver_card_export)",
        schema="identity",
    )
    op.create_check_constraint(
        "ck_product_access_admin_v2_corrected",
        "product_access_assignment",
        "product_role <> 'administrator' OR preset_version <> 2 OR "
        "(schema_configuration AND catalog_edit AND processing_calibration "
        "AND NOT model_approval AND solver_card_export)",
        schema="identity",
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION access_control.guard_product_access_preset_version()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF NEW.preset_version <> 2 THEN
            RAISE EXCEPTION USING ERRCODE = '23514',
              MESSAGE = 'new product access assignments must use preset_version 2';
          END IF;
          RETURN NEW;
        END
        $$
        """
    )
    op.execute(
        """
        DROP TRIGGER IF EXISTS product_access_assignment_preset_version_guard
          ON identity.product_access_assignment;
        CREATE TRIGGER product_access_assignment_preset_version_guard
        BEFORE INSERT ON identity.product_access_assignment
        FOR EACH ROW EXECUTE FUNCTION access_control.guard_product_access_preset_version()
        """
    )

    # Immutable typed evidence snapshot and review-backed publication projection.
    op.add_column(
        "review_request",
        sa.Column("subject_evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        schema="governance",
    )
    op.add_column(
        "review_request",
        sa.Column("requested_by_display_name", sa.String(length=255), nullable=False, server_default="Unknown requester"),
        schema="governance",
    )
    op.alter_column("review_request", "requested_by_display_name", server_default=None, schema="governance")
    op.execute(
        """
        CREATE TABLE governance.review_publication_projection (
          organization_id uuid NOT NULL,
          project_id uuid NOT NULL,
          classification varchar(64) NOT NULL,
          review_request_id uuid NOT NULL,
          subject_type varchar(64) NOT NULL,
          subject_id uuid NOT NULL,
          subject_revision_id uuid NOT NULL,
          neutral_material_id uuid,
          neutral_material_revision_id uuid,
          neutral_artifact_sha256 char(64),
          record_id uuid NOT NULL,
          record_revision_id uuid NOT NULL,
          record_table_id uuid NOT NULL,
          record_table_revision_id uuid NOT NULL,
          published_at timestamptz NOT NULL,
          published_by uuid NOT NULL,
          PRIMARY KEY (organization_id, project_id, review_request_id),
          UNIQUE (organization_id, project_id, subject_type, subject_id, subject_revision_id),
          CONSTRAINT ck_review_publication_subject_type CHECK
            (subject_type IN ('catalog.material', 'catalog.configurable_record',
             'datasets.test_data_document', 'modeling.material_model',
             'exporting.solver_card', 'exporting.neutral_solver_card')),
          CONSTRAINT ck_review_publication_digest CHECK
            (neutral_artifact_sha256 IS NULL OR neutral_artifact_sha256 ~ '^[0-9a-f]{64}$'),
          CONSTRAINT ck_review_publication_table_revision_pair CHECK
            (record_table_id IS NOT NULL AND record_table_revision_id IS NOT NULL)
        )
        """
    )
    op.execute(
        """
        CREATE TRIGGER review_publication_projection_immutable BEFORE UPDATE OR DELETE
          ON governance.review_publication_projection FOR EACH ROW
          EXECUTE FUNCTION revisioning.reject_immutable_row_mutation()
        """
    )
    op.execute(
        """
        ALTER TABLE governance.review_publication_projection ENABLE ROW LEVEL SECURITY;
        ALTER TABLE governance.review_publication_projection FORCE ROW LEVEL SECURITY;
        CREATE POLICY review_publication_projection_select
          ON governance.review_publication_projection FOR SELECT USING
          (access_control.can_access_row(organization_id, project_id, classification, 'governance.read')
           OR access_control.can_access_row(organization_id, project_id, classification, 'catalog.read'));
        CREATE POLICY review_publication_projection_insert
          ON governance.review_publication_projection FOR INSERT WITH CHECK
          (access_control.can_access_row(organization_id, project_id, classification, 'governance.write'));
        """
    )
    # Review requests are tenant-scoped governance facts, but they are not a tenant-wide
    # directory for ordinary readers.  Keep the requester-visible history and reviewer-visible
    # queue/history boundary in PostgreSQL as well as in the application repository.  The trusted
    # RLS context already carries the authorization roles in ``cmp.roles``.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION access_control.has_role(required_role text)
        RETURNS boolean
        LANGUAGE sql
        STABLE
        PARALLEL SAFE
        AS $$
          SELECT COALESCE(
            required_role = ANY(
              ARRAY(
                SELECT jsonb_array_elements_text(
                  COALESCE(
                    NULLIF(current_setting('cmp.roles', true), '')::jsonb,
                    '[]'::jsonb
                  )
                )
              )
            ),
            false
          )
        $$
        """
    )
    op.execute("DROP POLICY review_request_authorized_select ON governance.review_request")
    op.execute("DROP POLICY review_request_authorized_insert ON governance.review_request")
    op.execute("DROP POLICY review_decision_authorized_select ON governance.review_decision")
    op.execute("DROP POLICY review_decision_authorized_insert ON governance.review_decision")
    op.execute(
        """
        CREATE POLICY review_request_authorized_select
        ON governance.review_request
        FOR SELECT
        USING (
          access_control.can_access_row(
            organization_id, project_id, classification, 'governance.read'
          )
          AND (
            requested_by = access_control.current_principal_id()
            OR access_control.has_role('domain_reviewer')
          )
        )
        """
    )
    op.execute(
        """
        CREATE POLICY review_request_authorized_insert
        ON governance.review_request
        FOR INSERT
        WITH CHECK (
          access_control.can_access_row(
            organization_id, project_id, classification, 'governance.write'
          )
          AND requested_by = access_control.current_principal_id()
        )
        """
    )
    op.execute(
        """
        CREATE POLICY review_decision_authorized_select
        ON governance.review_decision
        FOR SELECT
        USING (
          access_control.can_access_row(
            organization_id, project_id, classification, 'governance.read'
          )
          AND (
            access_control.has_role('domain_reviewer')
            OR EXISTS (
              SELECT 1
                FROM governance.review_request AS request
               WHERE request.organization_id = governance.review_decision.organization_id
                 AND request.project_id = governance.review_decision.project_id
                 AND request.id = governance.review_decision.review_request_id
                 AND request.requested_by = access_control.current_principal_id()
            )
          )
        )
        """
    )
    op.execute(
        """
        CREATE POLICY review_decision_authorized_insert
        ON governance.review_decision
        FOR INSERT
        WITH CHECK (
          access_control.can_access_row(
            organization_id, project_id, classification, 'governance.write'
          )
          AND access_control.has_role('domain_reviewer')
          AND decided_by = access_control.current_principal_id()
          AND NOT EXISTS (
            SELECT 1
              FROM governance.review_request AS request
             WHERE request.organization_id = governance.review_decision.organization_id
               AND request.project_id = governance.review_decision.project_id
               AND request.id = governance.review_decision.review_request_id
               AND request.requested_by = access_control.current_principal_id()
          )
        )
        """
    )


def downgrade() -> None:
    # A downgrade after this transition would either delete immutable historical facts or
    # re-enable the pre-#160 five-grant approval semantics.  Refuse explicitly before any
    # destructive DDL; the migration actor is retained as an auditable service principal.
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (
            SELECT 1 FROM identity.product_access_assignment
             WHERE preset_version = 2
                OR created_by = '16000000-0000-4000-8000-000000000160'::uuid
                OR revoked_by = '16000000-0000-4000-8000-000000000160'::uuid
          ) THEN
            RAISE EXCEPTION USING ERRCODE = '55000',
              MESSAGE = 'Issue #160 downgrade refused: immutable transition evidence exists';
          END IF;
        END
        $$
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (
            SELECT 1
              FROM catalog.domain_record_binding
             GROUP BY organization_id, project_id, classification, record_id, record_revision_id
            HAVING COUNT(*) > 1
          ) THEN
            RAISE EXCEPTION USING ERRCODE = '55000',
              MESSAGE = 'Issue #160 downgrade refused: multiple domain bindings share a Record revision';
          END IF;
        END
        $$;
        ALTER TABLE catalog.domain_record_binding
          DROP CONSTRAINT IF EXISTS uq_catalog_domain_binding_exact_revision;
        ALTER TABLE catalog.domain_record_binding
          ADD CONSTRAINT uq_catalog_domain_binding_record_revision UNIQUE
            (organization_id, project_id, classification, record_id, record_revision_id);
        """
    )
    op.execute(
        "DROP POLICY IF EXISTS review_publication_projection_insert ON governance.review_publication_projection"
    )
    op.execute(
        "DROP POLICY IF EXISTS review_publication_projection_select ON governance.review_publication_projection"
    )
    op.execute("ALTER TABLE governance.review_publication_projection NO FORCE ROW LEVEL SECURITY")
    op.execute(
        "DROP TRIGGER IF EXISTS review_publication_projection_immutable ON governance.review_publication_projection"
    )
    op.execute("DROP TABLE governance.review_publication_projection")
    op.drop_column("review_request", "subject_evidence", schema="governance")
    op.drop_column("review_request", "requested_by_display_name", schema="governance")
    op.execute(
        "DROP TRIGGER IF EXISTS product_access_assignment_preset_version_guard "
        "ON identity.product_access_assignment"
    )
    op.execute("DROP POLICY IF EXISTS review_request_authorized_select ON governance.review_request")
    op.execute("DROP POLICY IF EXISTS review_request_authorized_insert ON governance.review_request")
    op.execute("DROP POLICY IF EXISTS review_decision_authorized_select ON governance.review_decision")
    op.execute("DROP POLICY IF EXISTS review_decision_authorized_insert ON governance.review_decision")
    op.execute(
        """
        CREATE POLICY review_request_authorized_select
        ON governance.review_request FOR SELECT USING
        (access_control.can_access_row(organization_id, project_id, classification, 'governance.read'));
        CREATE POLICY review_request_authorized_insert
        ON governance.review_request FOR INSERT WITH CHECK
        (access_control.can_access_row(organization_id, project_id, classification, 'governance.write'));
        CREATE POLICY review_decision_authorized_select
        ON governance.review_decision FOR SELECT USING
        (access_control.can_access_row(organization_id, project_id, classification, 'governance.read'));
        CREATE POLICY review_decision_authorized_insert
        ON governance.review_decision FOR INSERT WITH CHECK
        (access_control.can_access_row(organization_id, project_id, classification, 'governance.write'));
        """
    )
    op.execute("DROP FUNCTION IF EXISTS access_control.guard_product_access_preset_version()")
    op.execute("DROP FUNCTION IF EXISTS access_control.has_role(text)")
    for name in (
        "ck_product_access_admin_v2_corrected",
        "ck_product_access_admin_v1_legacy",
        "ck_product_access_preset_version",
        "ck_product_access_role_v2",
    ):
        op.drop_constraint(name, "product_access_assignment", schema="identity", if_exists=True)
    op.create_check_constraint(
        "ck_product_access_role",
        "product_access_assignment",
        "product_role IN ('administrator', 'reviewer', 'user')",
        schema="identity",
    )
    op.create_check_constraint(
        "ck_product_access_administrator_features",
        "product_access_assignment",
        "product_role <> 'administrator' OR "
        "(schema_configuration AND catalog_edit AND processing_calibration "
        "AND model_approval AND solver_card_export)",
        schema="identity",
    )
    op.drop_column("product_access_assignment", "preset_version", schema="identity")
    # Keep the deterministic migration actor: deleting an identity would violate the
    # principal append-only boundary even in the empty-table downgrade case.

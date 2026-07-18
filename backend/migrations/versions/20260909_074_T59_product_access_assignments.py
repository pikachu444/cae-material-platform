"""T-59 product-facing Administrator/User assignments and explicit feature grants.

The detailed T-04 role bindings remain supported.  This table is a typed, append-only product
projection: five boolean feature columns deliberately avoid an untyped permission EAV payload.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260909_074_t59"
down_revision: str | None = "20260908_073_t58_bulk"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    op.create_table(
        "product_access_assignment",
        sa.Column("id", uuid, nullable=False),
        sa.Column("organization_id", uuid, nullable=False),
        sa.Column("project_id", uuid, nullable=True),
        sa.Column("classification", sa.String(length=64), nullable=False),
        sa.Column("subject_type", sa.String(length=16), nullable=False),
        sa.Column("principal_id", uuid, nullable=True),
        sa.Column("group_issuer", sa.String(length=2048, collation="C"), nullable=True),
        sa.Column("group_name", sa.String(length=255, collation="C"), nullable=True),
        sa.Column("product_role", sa.String(length=32), nullable=False),
        sa.Column("schema_configuration", sa.Boolean(), nullable=False),
        sa.Column("catalog_edit", sa.Boolean(), nullable=False),
        sa.Column("processing_calibration", sa.Boolean(), nullable=False),
        sa.Column("model_approval", sa.Boolean(), nullable=False),
        sa.Column("solver_card_export", sa.Boolean(), nullable=False),
        sa.Column("max_classification", sa.String(length=64), nullable=False),
        sa.Column("allow_export_controlled", sa.Boolean(), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", uuid, nullable=False),
        sa.Column("grant_reason", sa.Text(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by", uuid, nullable=True),
        sa.Column("revocation_reason", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_product_access_assignment"),
        sa.ForeignKeyConstraint(
            ["principal_id"], ["identity.principal.id"], name="fk_product_access_principal"
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["identity.principal.id"], name="fk_product_access_created_by"
        ),
        sa.ForeignKeyConstraint(
            ["revoked_by"], ["identity.principal.id"], name="fk_product_access_revoked_by"
        ),
        sa.CheckConstraint(
            "classification = 'restricted'", name="ck_product_access_classification"
        ),
        sa.CheckConstraint(
            "(subject_type = 'principal' AND principal_id IS NOT NULL "
            "AND group_issuer IS NULL AND group_name IS NULL) OR "
            "(subject_type = 'group' AND principal_id IS NULL "
            "AND group_issuer IS NOT NULL AND group_name IS NOT NULL)",
            name="ck_product_access_subject",
        ),
        sa.CheckConstraint(
            "product_role IN ('administrator', 'user')", name="ck_product_access_role"
        ),
        sa.CheckConstraint(
            "product_role <> 'administrator' OR "
            "(schema_configuration AND catalog_edit AND processing_calibration "
            "AND model_approval AND solver_card_export)",
            name="ck_product_access_administrator_features",
        ),
        sa.CheckConstraint(
            "max_classification IN ('internal', 'confidential', 'restricted')",
            name="ck_product_access_max_classification",
        ),
        sa.CheckConstraint(
            "expires_at IS NULL OR expires_at > valid_from", name="ck_product_access_expiry"
        ),
        sa.CheckConstraint(
            "length(btrim(grant_reason)) BETWEEN 1 AND 2000",
            name="ck_product_access_grant_reason",
        ),
        sa.CheckConstraint(
            "(revoked_at IS NULL AND revoked_by IS NULL AND revocation_reason IS NULL) OR "
            "(revoked_at IS NOT NULL AND revoked_by IS NOT NULL "
            "AND length(btrim(revocation_reason)) BETWEEN 1 AND 2000)",
            name="ck_product_access_revocation",
        ),
        schema="identity",
    )
    op.create_index(
        "ix_product_access_scope_active",
        "product_access_assignment",
        ["organization_id", "project_id", "revoked_at", "valid_from"],
        schema="identity",
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_product_access_active_principal
        ON identity.product_access_assignment (
          organization_id,
          COALESCE(project_id, '00000000-0000-0000-0000-000000000000'::uuid),
          principal_id
        ) WHERE revoked_at IS NULL AND subject_type = 'principal'
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_product_access_active_group
        ON identity.product_access_assignment (
          organization_id,
          COALESCE(project_id, '00000000-0000-0000-0000-000000000000'::uuid),
          group_issuer,
          group_name
        ) WHERE revoked_at IS NULL AND subject_type = 'group'
        """
    )
    op.execute(
        """
        CREATE FUNCTION access_control.guard_product_access_assignment_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
          IF TG_OP = 'DELETE' THEN
            RAISE EXCEPTION USING ERRCODE = '55000',
              MESSAGE = 'product access assignments cannot be deleted';
          END IF;
          IF OLD.revoked_at IS NOT NULL THEN
            RAISE EXCEPTION USING ERRCODE = '55000',
              MESSAGE = 'revoked product access assignments are immutable';
          END IF;
          IF (to_jsonb(NEW) - ARRAY['revoked_at', 'revoked_by', 'revocation_reason'])
             IS DISTINCT FROM
             (to_jsonb(OLD) - ARRAY['revoked_at', 'revoked_by', 'revocation_reason']) THEN
            RAISE EXCEPTION USING ERRCODE = '55000',
              MESSAGE = 'product access grants are immutable; revoke and append a new assignment';
          END IF;
          IF NEW.revoked_at IS NULL OR NEW.revoked_by IS NULL
             OR NEW.revocation_reason IS NULL THEN
            RAISE EXCEPTION USING ERRCODE = '55000',
              MESSAGE = 'product access revocation fields must be written atomically';
          END IF;
          RETURN NEW;
        END
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER product_access_assignment_guard
        BEFORE UPDATE OR DELETE ON identity.product_access_assignment
        FOR EACH ROW EXECUTE FUNCTION access_control.guard_product_access_assignment_mutation()
        """
    )
    op.execute("ALTER TABLE identity.product_access_assignment ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE identity.product_access_assignment FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY product_access_own_select
        ON identity.product_access_assignment FOR SELECT
        USING (
          access_control.binding_scope_matches(organization_id, project_id)
          AND access_control.binding_subject_matches(
            subject_type, principal_id, group_issuer, group_name
          )
        )
        """
    )
    op.execute(
        """
        CREATE POLICY product_access_manager_select
        ON identity.product_access_assignment FOR SELECT
        USING (
          access_control.binding_scope_matches(organization_id, project_id)
          AND access_control.has_permission('identity.manage')
        )
        """
    )
    op.execute(
        """
        CREATE POLICY product_access_manager_insert
        ON identity.product_access_assignment FOR INSERT
        WITH CHECK (
          access_control.binding_scope_matches(organization_id, project_id)
          AND access_control.has_permission('identity.manage')
          AND created_by = access_control.current_principal_id()
          AND revoked_at IS NULL AND revoked_by IS NULL AND revocation_reason IS NULL
        )
        """
    )
    op.execute(
        """
        CREATE POLICY product_access_manager_update
        ON identity.product_access_assignment FOR UPDATE
        USING (
          access_control.binding_scope_matches(organization_id, project_id)
          AND access_control.has_permission('identity.manage')
        )
        WITH CHECK (
          access_control.binding_scope_matches(organization_id, project_id)
          AND access_control.has_permission('identity.manage')
          AND revoked_by = access_control.current_principal_id()
        )
        """
    )


def downgrade() -> None:
    for policy in (
        "product_access_manager_update",
        "product_access_manager_insert",
        "product_access_manager_select",
        "product_access_own_select",
    ):
        op.execute(
            f"DROP POLICY IF EXISTS {policy} ON identity.product_access_assignment"
        )
    op.execute(
        "DROP TRIGGER IF EXISTS product_access_assignment_guard "
        "ON identity.product_access_assignment"
    )
    op.drop_index(
        "uq_product_access_active_group",
        table_name="product_access_assignment",
        schema="identity",
    )
    op.drop_index(
        "uq_product_access_active_principal",
        table_name="product_access_assignment",
        schema="identity",
    )
    op.drop_index(
        "ix_product_access_scope_active",
        table_name="product_access_assignment",
        schema="identity",
    )
    op.drop_table("product_access_assignment", schema="identity")
    op.execute("DROP FUNCTION access_control.guard_product_access_assignment_mutation()")

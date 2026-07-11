"""T-04 deny-by-default role binding and classification-aware PostgreSQL RLS.

Traceability: T-04, NFR-SEC-002/003/006, ADR-001/002.
Material, testing, artifact, and solver-owned tables remain outside this migration.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260711_003_t04"
down_revision: str | None = "20260711_002_t03"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_ROLES = (
    "platform_admin",
    "org_admin",
    "project_admin",
    "test_engineer",
    "data_steward",
    "statistical_analyst",
    "material_modeler",
    "cae_analyst",
    "domain_reviewer",
    "release_approver",
    "consumer",
    "plugin_maintainer",
    "auditor",
)


def _quoted(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def _create_context_functions() -> None:
    op.execute(
        """
        CREATE FUNCTION access_control.current_principal_id()
        RETURNS uuid
        LANGUAGE sql
        STABLE
        PARALLEL SAFE
        AS $$
          SELECT NULLIF(current_setting('cmp.principal_id', true), '')::uuid
        $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION access_control.current_issuer()
        RETURNS text
        LANGUAGE sql
        STABLE
        PARALLEL SAFE
        AS $$
          SELECT NULLIF(current_setting('cmp.issuer', true), '')
        $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION access_control.current_groups()
        RETURNS text[]
        LANGUAGE sql
        STABLE
        PARALLEL SAFE
        AS $$
          SELECT COALESCE(
            ARRAY(
              SELECT jsonb_array_elements_text(
                COALESCE(
                  NULLIF(current_setting('cmp.groups', true), '')::jsonb,
                  '[]'::jsonb
                )
              )
            ),
            ARRAY[]::text[]
          )
        $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION access_control.current_permissions()
        RETURNS text[]
        LANGUAGE sql
        STABLE
        PARALLEL SAFE
        AS $$
          SELECT COALESCE(
            ARRAY(
              SELECT jsonb_array_elements_text(
                COALESCE(
                  NULLIF(current_setting('cmp.permissions', true), '')::jsonb,
                  '[]'::jsonb
                )
              )
            ),
            ARRAY[]::text[]
          )
        $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION access_control.current_max_classification_rank()
        RETURNS smallint
        LANGUAGE sql
        STABLE
        PARALLEL SAFE
        AS $$
          SELECT NULLIF(
            current_setting('cmp.max_classification_rank', true),
            ''
          )::smallint
        $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION access_control.current_export_controlled_access()
        RETURNS boolean
        LANGUAGE sql
        STABLE
        PARALLEL SAFE
        AS $$
          SELECT COALESCE(
            NULLIF(
              current_setting('cmp.allow_export_controlled', true),
              ''
            )::boolean,
            false
          )
        $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION access_control.classification_rank(value text)
        RETURNS smallint
        LANGUAGE sql
        IMMUTABLE
        PARALLEL SAFE
        AS $$
          SELECT CASE value
            WHEN 'internal' THEN 0::smallint
            WHEN 'confidential' THEN 1::smallint
            WHEN 'restricted' THEN 2::smallint
            ELSE NULL::smallint
          END
        $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION access_control.has_permission(required_permission text)
        RETURNS boolean
        LANGUAGE sql
        STABLE
        PARALLEL SAFE
        AS $$
          SELECT COALESCE(
            required_permission = ANY(access_control.current_permissions()),
            false
          )
        $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION access_control.tenant_matches(
          row_organization_id uuid,
          row_project_id uuid
        )
        RETURNS boolean
        LANGUAGE sql
        STABLE
        PARALLEL SAFE
        AS $$
          SELECT COALESCE(
            row_organization_id = revisioning.current_organization_id()
            AND row_project_id = revisioning.current_project_id(),
            false
          )
        $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION access_control.can_access_row(
          row_organization_id uuid,
          row_project_id uuid,
          row_classification text,
          required_permission text
        )
        RETURNS boolean
        LANGUAGE sql
        STABLE
        PARALLEL SAFE
        AS $$
          SELECT COALESCE(
            access_control.tenant_matches(row_organization_id, row_project_id)
            AND access_control.has_permission(required_permission)
            AND CASE row_classification
              WHEN 'export_controlled' THEN
                access_control.current_export_controlled_access()
              ELSE
                access_control.classification_rank(row_classification) IS NOT NULL
                AND access_control.current_max_classification_rank() IS NOT NULL
                AND access_control.classification_rank(row_classification)
                    <= access_control.current_max_classification_rank()
            END,
            false
          )
        $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION access_control.assert_application_role()
        RETURNS void
        LANGUAGE plpgsql
        STABLE
        AS $$
        DECLARE
          bypasses_rls boolean;
        BEGIN
          SELECT
            roles.rolsuper
            OR roles.rolbypassrls
            OR EXISTS (
              SELECT 1
              FROM pg_catalog.pg_class AS relations
              JOIN pg_catalog.pg_namespace AS namespaces
                ON namespaces.oid = relations.relnamespace
              WHERE relations.relowner = roles.oid
                AND namespaces.nspname NOT IN ('pg_catalog', 'information_schema')
                AND namespaces.nspname NOT LIKE 'pg_toast%'
            )
          INTO bypasses_rls
          FROM pg_catalog.pg_roles AS roles
          WHERE roles.rolname = current_user;
          IF COALESCE(bypasses_rls, true) THEN
            RAISE EXCEPTION USING
              ERRCODE = '42501',
              MESSAGE = 'application database role must be non-owner NOSUPERUSER NOBYPASSRLS';
          END IF;
        END
        $$
        """
    )


def _create_role_binding_table() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    op.create_table(
        "role_binding",
        sa.Column("id", uuid, nullable=False),
        sa.Column("organization_id", uuid, nullable=False),
        sa.Column("project_id", uuid, nullable=True),
        sa.Column(
            "classification",
            sa.String(length=64),
            nullable=False,
            server_default="restricted",
        ),
        sa.Column("subject_type", sa.String(length=16), nullable=False),
        sa.Column("principal_id", uuid, nullable=True),
        sa.Column(
            "group_issuer",
            sa.String(length=2048, collation="C"),
            nullable=True,
        ),
        sa.Column(
            "group_name",
            sa.String(length=255, collation="C"),
            nullable=True,
        ),
        sa.Column("role", sa.String(length=64), nullable=False),
        sa.Column("max_classification", sa.String(length=64), nullable=False),
        sa.Column(
            "allow_export_controlled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", uuid, nullable=False),
        sa.Column("grant_reason", sa.Text(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by", uuid, nullable=True),
        sa.Column("revocation_reason", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "id <> '00000000-0000-0000-0000-000000000000'::uuid",
            name="ck_role_binding_nonzero_id",
        ),
        sa.CheckConstraint(
            "organization_id <> '00000000-0000-0000-0000-000000000000'::uuid",
            name="ck_role_binding_nonzero_organization",
        ),
        sa.CheckConstraint(
            "project_id IS NULL OR "
            "project_id <> '00000000-0000-0000-0000-000000000000'::uuid",
            name="ck_role_binding_nonzero_project",
        ),
        sa.CheckConstraint(
            "classification = 'restricted'",
            name="ck_role_binding_record_classification",
        ),
        sa.CheckConstraint(
            "(subject_type = 'principal' AND principal_id IS NOT NULL "
            "AND group_issuer IS NULL AND group_name IS NULL) OR "
            "(subject_type = 'group' AND principal_id IS NULL "
            "AND group_issuer IS NOT NULL AND group_name IS NOT NULL)",
            name="ck_role_binding_subject",
        ),
        sa.CheckConstraint(
            "group_issuer IS NULL OR length(btrim(group_issuer)) BETWEEN 1 AND 2048",
            name="ck_role_binding_group_issuer",
        ),
        sa.CheckConstraint(
            "group_name IS NULL OR length(btrim(group_name)) BETWEEN 1 AND 255",
            name="ck_role_binding_group_name",
        ),
        sa.CheckConstraint(
            f"role IN ({_quoted(_ROLES)})",
            name="ck_role_binding_role",
        ),
        sa.CheckConstraint(
            "role <> 'platform_admin' OR "
            "(subject_type = 'principal' AND project_id IS NULL)",
            name="ck_role_binding_platform_admin_subject",
        ),
        sa.CheckConstraint(
            "role NOT IN ('org_admin', 'platform_admin') OR project_id IS NULL",
            name="ck_role_binding_admin_scope",
        ),
        sa.CheckConstraint(
            "role <> 'project_admin' OR project_id IS NOT NULL",
            name="ck_role_binding_project_admin_scope",
        ),
        sa.CheckConstraint(
            "max_classification IN ('internal', 'confidential', 'restricted')",
            name="ck_role_binding_max_classification",
        ),
        sa.CheckConstraint(
            "valid_from >= created_at",
            name="ck_role_binding_valid_from",
        ),
        sa.CheckConstraint(
            "length(btrim(grant_reason)) BETWEEN 1 AND 2000",
            name="ck_role_binding_grant_reason",
        ),
        sa.CheckConstraint(
            "expires_at IS NULL OR expires_at > valid_from",
            name="ck_role_binding_expiry",
        ),
        sa.CheckConstraint(
            "(revoked_at IS NULL AND revoked_by IS NULL AND revocation_reason IS NULL) OR "
            "(revoked_at IS NOT NULL AND revoked_by IS NOT NULL "
            "AND length(btrim(revocation_reason)) BETWEEN 1 AND 2000)",
            name="ck_role_binding_revocation",
        ),
        sa.CheckConstraint(
            "revoked_at IS NULL OR revoked_at >= valid_from",
            name="ck_role_binding_revoked_at",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_role_binding"),
        sa.ForeignKeyConstraint(
            ["principal_id"],
            ["identity.principal.id"],
            name="fk_role_binding_principal",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["identity.principal.id"],
            name="fk_role_binding_created_by",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["revoked_by"],
            ["identity.principal.id"],
            name="fk_role_binding_revoked_by",
            ondelete="RESTRICT",
        ),
        schema="identity",
    )
    op.create_index(
        "ix_role_binding_tenant_active",
        "role_binding",
        ["organization_id", "project_id", "revoked_at", "expires_at", "valid_from"],
        schema="identity",
    )
    op.create_index(
        "ix_role_binding_principal_lookup",
        "role_binding",
        ["principal_id", "organization_id", "project_id"],
        schema="identity",
        postgresql_where=sa.text("subject_type = 'principal' AND revoked_at IS NULL"),
    )
    op.create_index(
        "ix_role_binding_group_lookup",
        "role_binding",
        ["group_issuer", "group_name", "organization_id", "project_id"],
        schema="identity",
        postgresql_where=sa.text("subject_type = 'group' AND revoked_at IS NULL"),
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_role_binding_principal_grant
        ON identity.role_binding (
          organization_id, project_id, principal_id, role, valid_from
        ) NULLS NOT DISTINCT
        WHERE subject_type = 'principal'
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_role_binding_group_grant
        ON identity.role_binding (
          organization_id, project_id, group_issuer, group_name, role, valid_from
        ) NULLS NOT DISTINCT
        WHERE subject_type = 'group'
        """
    )


def _secure_role_bindings() -> None:
    op.execute(
        """
        CREATE FUNCTION access_control.guard_role_binding_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
          IF TG_OP = 'DELETE' THEN
            RAISE EXCEPTION USING
              ERRCODE = '55000',
              MESSAGE = 'identity.role_binding rows cannot be deleted';
          END IF;
          IF OLD.revoked_at IS NOT NULL THEN
            RAISE EXCEPTION USING
              ERRCODE = '55000',
              MESSAGE = 'revoked role bindings are immutable';
          END IF;
          IF (to_jsonb(NEW) - ARRAY['revoked_at', 'revoked_by', 'revocation_reason'])
             IS DISTINCT FROM
             (to_jsonb(OLD) - ARRAY['revoked_at', 'revoked_by', 'revocation_reason']) THEN
            RAISE EXCEPTION USING
              ERRCODE = '55000',
              MESSAGE = 'role binding grants are immutable; revoke and append a new grant';
          END IF;
          IF NEW.revoked_at IS NULL
             OR NEW.revoked_by IS NULL
             OR NEW.revocation_reason IS NULL THEN
            RAISE EXCEPTION USING
              ERRCODE = '55000',
              MESSAGE = 'role binding revocation fields must be written atomically';
          END IF;
          RETURN NEW;
        END
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER role_binding_guard
        BEFORE UPDATE OR DELETE ON identity.role_binding
        FOR EACH ROW EXECUTE FUNCTION access_control.guard_role_binding_mutation()
        """
    )
    op.execute(
        """
        CREATE FUNCTION access_control.binding_scope_matches(
          row_organization_id uuid,
          row_project_id uuid
        )
        RETURNS boolean
        LANGUAGE sql
        STABLE
        PARALLEL SAFE
        AS $$
          SELECT COALESCE(
            row_organization_id = revisioning.current_organization_id()
            AND (
              row_project_id IS NULL
              OR row_project_id = revisioning.current_project_id()
            ),
            false
          )
        $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION access_control.binding_subject_matches(
          row_subject_type text,
          row_principal_id uuid,
          row_group_issuer text,
          row_group_name text
        )
        RETURNS boolean
        LANGUAGE sql
        STABLE
        PARALLEL SAFE
        AS $$
          SELECT COALESCE(
            (
              row_subject_type = 'principal'
              AND row_principal_id = access_control.current_principal_id()
            )
            OR (
              row_subject_type = 'group'
              AND row_group_issuer = access_control.current_issuer()
              AND row_group_name = ANY(access_control.current_groups())
            ),
            false
          )
        $$
        """
    )
    op.execute("ALTER TABLE identity.role_binding ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE identity.role_binding FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY role_binding_own_select
        ON identity.role_binding
        FOR SELECT
        USING (
          access_control.binding_scope_matches(organization_id, project_id)
          AND access_control.binding_subject_matches(
            subject_type,
            principal_id,
            group_issuer,
            group_name
          )
        )
        """
    )
    op.execute(
        """
        CREATE POLICY role_binding_manager_select
        ON identity.role_binding
        FOR SELECT
        USING (
          access_control.binding_scope_matches(organization_id, project_id)
          AND access_control.has_permission('identity.manage')
        )
        """
    )
    op.execute(
        """
        CREATE POLICY role_binding_manager_insert
        ON identity.role_binding
        FOR INSERT
        WITH CHECK (
          access_control.binding_scope_matches(organization_id, project_id)
          AND access_control.has_permission('identity.manage')
          AND created_by = access_control.current_principal_id()
          AND revoked_at IS NULL
          AND revoked_by IS NULL
          AND revocation_reason IS NULL
        )
        """
    )
    op.execute(
        """
        CREATE POLICY role_binding_manager_update
        ON identity.role_binding
        FOR UPDATE
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


def _replace_governance_policies() -> None:
    for table in ("lifecycle_event", "lifecycle_projection"):
        op.execute(
            f"DROP POLICY {table}_tenant_isolation ON governance.{table}"
        )
        op.execute(
            f"""
            CREATE POLICY {table}_authorized_select
            ON governance.{table}
            FOR SELECT
            USING (
              access_control.can_access_row(
                organization_id,
                project_id,
                classification,
                'governance.read'
              )
            )
            """
        )
        op.execute(
            f"""
            CREATE POLICY {table}_authorized_insert
            ON governance.{table}
            FOR INSERT
            WITH CHECK (
              access_control.can_access_row(
                organization_id,
                project_id,
                classification,
                'governance.write'
              )
            )
            """
        )
    op.execute(
        """
        CREATE POLICY lifecycle_projection_authorized_update
        ON governance.lifecycle_projection
        FOR UPDATE
        USING (
          access_control.can_access_row(
            organization_id,
            project_id,
            classification,
            'governance.write'
          )
        )
        WITH CHECK (
          access_control.can_access_row(
            organization_id,
            project_id,
            classification,
            'governance.write'
          )
        )
        """
    )


def upgrade() -> None:
    op.execute("CREATE SCHEMA access_control")
    _create_context_functions()
    _create_role_binding_table()
    _secure_role_bindings()
    _replace_governance_policies()


def _restore_t06_governance_policies() -> None:
    op.execute(
        "DROP POLICY lifecycle_projection_authorized_update "
        "ON governance.lifecycle_projection"
    )
    for table in ("lifecycle_event", "lifecycle_projection"):
        op.execute(f"DROP POLICY {table}_authorized_insert ON governance.{table}")
        op.execute(f"DROP POLICY {table}_authorized_select ON governance.{table}")
        op.execute(
            f"""
            CREATE POLICY {table}_tenant_isolation
            ON governance.{table}
            USING (
              organization_id = revisioning.current_organization_id()
              AND project_id = revisioning.current_project_id()
            )
            WITH CHECK (
              organization_id = revisioning.current_organization_id()
              AND project_id = revisioning.current_project_id()
            )
            """
        )


def downgrade() -> None:
    _restore_t06_governance_policies()
    op.drop_index(
        "uq_role_binding_group_grant",
        table_name="role_binding",
        schema="identity",
    )
    op.drop_index(
        "uq_role_binding_principal_grant",
        table_name="role_binding",
        schema="identity",
    )
    op.drop_index(
        "ix_role_binding_group_lookup",
        table_name="role_binding",
        schema="identity",
    )
    op.drop_index(
        "ix_role_binding_principal_lookup",
        table_name="role_binding",
        schema="identity",
    )
    op.drop_index(
        "ix_role_binding_tenant_active",
        table_name="role_binding",
        schema="identity",
    )
    op.drop_table("role_binding", schema="identity")
    op.execute("DROP FUNCTION access_control.binding_subject_matches(text, uuid, text, text)")
    op.execute("DROP FUNCTION access_control.binding_scope_matches(uuid, uuid)")
    op.execute("DROP FUNCTION access_control.guard_role_binding_mutation()")
    op.execute("DROP FUNCTION access_control.assert_application_role()")
    op.execute("DROP FUNCTION access_control.can_access_row(uuid, uuid, text, text)")
    op.execute("DROP FUNCTION access_control.tenant_matches(uuid, uuid)")
    op.execute("DROP FUNCTION access_control.has_permission(text)")
    op.execute("DROP FUNCTION access_control.classification_rank(text)")
    op.execute("DROP FUNCTION access_control.current_export_controlled_access()")
    op.execute("DROP FUNCTION access_control.current_max_classification_rank()")
    op.execute("DROP FUNCTION access_control.current_permissions()")
    op.execute("DROP FUNCTION access_control.current_groups()")
    op.execute("DROP FUNCTION access_control.current_issuer()")
    op.execute("DROP FUNCTION access_control.current_principal_id()")
    op.execute("DROP SCHEMA access_control")

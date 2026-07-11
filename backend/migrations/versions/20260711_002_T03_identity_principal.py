"""T-03 OIDC principal and immutable external identity.

Traceability: T-03, NFR-SEC-001/002/003, NFR-AUD-001, RFC 6750/8725/9068.
Authorization bindings and tenant-owned RLS are added by the downstream T-04 migration.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260711_002_t03"
down_revision: str | None = "20260711_001_t06"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _create_guard_functions() -> None:
    op.execute(
        """
        CREATE FUNCTION identity.guard_principal_update()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
          IF TG_OP = 'DELETE' THEN
            RAISE EXCEPTION USING
              ERRCODE = '55000',
              MESSAGE = 'identity.principal rows cannot be deleted';
          END IF;
          IF (to_jsonb(NEW) - ARRAY['display_name', 'active', 'updated_at'])
             IS DISTINCT FROM
             (to_jsonb(OLD) - ARRAY['display_name', 'active', 'updated_at']) THEN
            RAISE EXCEPTION USING
              ERRCODE = '55000',
              MESSAGE = 'principal update attempted to replace immutable identity fields';
          END IF;
          RETURN NEW;
        END
        $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION identity.guard_external_identity_update()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
          IF TG_OP = 'DELETE' THEN
            RAISE EXCEPTION USING
              ERRCODE = '55000',
              MESSAGE = 'identity.external_identity rows cannot be deleted';
          END IF;
          IF (to_jsonb(NEW) - 'last_seen_at')
             IS DISTINCT FROM
             (to_jsonb(OLD) - 'last_seen_at') THEN
            RAISE EXCEPTION USING
              ERRCODE = '55000',
              MESSAGE = 'external issuer/subject identity is immutable';
          END IF;
          IF NEW.last_seen_at < OLD.last_seen_at THEN
            RAISE EXCEPTION USING
              ERRCODE = '55000',
              MESSAGE = 'external identity last_seen_at cannot move backwards';
          END IF;
          RETURN NEW;
        END
        $$
        """
    )


def upgrade() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    op.execute("CREATE SCHEMA identity")
    _create_guard_functions()
    op.create_table(
        "principal",
        sa.Column("id", uuid, nullable=False),
        sa.Column("principal_type", sa.String(length=16), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "id <> '00000000-0000-0000-0000-000000000000'::uuid",
            name="ck_principal_nonzero_id",
        ),
        sa.CheckConstraint(
            "principal_type IN ('user', 'service')", name="ck_principal_type"
        ),
        sa.CheckConstraint(
            "length(btrim(display_name)) BETWEEN 1 AND 255",
            name="ck_principal_display_name",
        ),
        sa.CheckConstraint("updated_at >= created_at", name="ck_principal_timestamp_order"),
        sa.PrimaryKeyConstraint("id", name="pk_principal"),
        schema="identity",
    )
    op.create_index(
        "ix_principal_type_active",
        "principal",
        ["principal_type", "active"],
        schema="identity",
    )
    op.create_table(
        "external_identity",
        sa.Column("id", uuid, nullable=False),
        sa.Column("principal_id", uuid, nullable=False),
        sa.Column("issuer", sa.String(length=2048, collation="C"), nullable=False),
        sa.Column("subject", sa.String(length=255, collation="C"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "id <> '00000000-0000-0000-0000-000000000000'::uuid",
            name="ck_external_identity_nonzero_id",
        ),
        sa.CheckConstraint(
            "length(btrim(issuer)) BETWEEN 1 AND 2048",
            name="ck_external_identity_issuer",
        ),
        sa.CheckConstraint(
            "length(btrim(subject)) BETWEEN 1 AND 255",
            name="ck_external_identity_subject",
        ),
        sa.CheckConstraint(
            "last_seen_at >= created_at", name="ck_external_identity_timestamp_order"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_external_identity"),
        sa.ForeignKeyConstraint(
            ["principal_id"],
            ["identity.principal.id"],
            name="fk_external_identity_principal",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("issuer", "subject", name="uq_external_identity_issuer_subject"),
        schema="identity",
    )
    op.create_index(
        "ix_external_identity_principal",
        "external_identity",
        ["principal_id"],
        schema="identity",
    )
    op.execute(
        """
        CREATE TRIGGER principal_guard
        BEFORE UPDATE OR DELETE ON identity.principal
        FOR EACH ROW EXECUTE FUNCTION identity.guard_principal_update()
        """
    )
    op.execute(
        """
        CREATE TRIGGER external_identity_guard
        BEFORE UPDATE OR DELETE ON identity.external_identity
        FOR EACH ROW EXECUTE FUNCTION identity.guard_external_identity_update()
        """
    )


def downgrade() -> None:
    op.drop_index(
        "ix_external_identity_principal",
        table_name="external_identity",
        schema="identity",
    )
    op.drop_table("external_identity", schema="identity")
    op.drop_index(
        "ix_principal_type_active", table_name="principal", schema="identity"
    )
    op.drop_table("principal", schema="identity")
    op.execute("DROP FUNCTION identity.guard_external_identity_update()")
    op.execute("DROP FUNCTION identity.guard_principal_update()")
    op.execute("DROP SCHEMA identity")

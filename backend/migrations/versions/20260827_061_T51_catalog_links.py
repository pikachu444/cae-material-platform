"""T-51 Link Types, exact-revision Record Links and explorer indexes.

Traceability: ADR-0024, ADR-0028; FR-CFG-015..021; T-51.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260827_061_t51"
down_revision: str | None = "20260826_060_t50"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _identity_columns(uuid: postgresql.UUID) -> list[sa.Column[object]]:
    return [
        sa.Column("id", uuid, nullable=False),
        sa.Column("organization_id", uuid, nullable=False),
        sa.Column("project_id", uuid, nullable=False),
        sa.Column("classification", sa.String(length=64), nullable=False),
        sa.Column("current_revision_id", uuid, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", uuid, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]


def _revision_columns(uuid: postgresql.UUID) -> list[sa.Column[object]]:
    return [
        sa.Column("id", uuid, nullable=False),
        sa.Column("aggregate_id", uuid, nullable=False),
        sa.Column("organization_id", uuid, nullable=False),
        sa.Column("project_id", uuid, nullable=False),
        sa.Column("classification", sa.String(length=64), nullable=False),
        sa.Column("revision_no", sa.BigInteger(), nullable=False),
        sa.Column("based_on_revision_id", uuid, nullable=True),
        sa.Column("schema_id", sa.String(length=255), nullable=False),
        sa.Column("schema_version", sa.String(length=64), nullable=False),
        sa.Column("content_hash", sa.CHAR(length=64, collation="C"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", uuid, nullable=False),
        sa.Column("change_reason", sa.Text(), nullable=False),
        sa.Column("request_id", uuid, nullable=False),
        sa.Column("trace_id", sa.String(length=255), nullable=False),
    ]


def _revision_constraints(name: str) -> list[sa.Constraint]:
    return [
        sa.PrimaryKeyConstraint(
            "organization_id", "project_id", "id", name=f"pk_catalog_{name}_revision"
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "aggregate_id",
            "id",
            name=f"uq_catalog_{name}_revision_scope_id",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "classification",
            "aggregate_id",
            "id",
            name=f"uq_catalog_{name}_revision_scoped_reference",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "aggregate_id",
            "revision_no",
            name=f"uq_catalog_{name}_revision_number",
        ),
        sa.CheckConstraint("revision_no > 0", name=f"ck_catalog_{name}_revision_number"),
        sa.CheckConstraint(
            "(revision_no = 1 AND based_on_revision_id IS NULL) OR "
            "(revision_no > 1 AND based_on_revision_id IS NOT NULL)",
            name=f"ck_catalog_{name}_revision_base",
        ),
        sa.CheckConstraint(
            "content_hash ~ '^[0-9a-f]{64}$'", name=f"ck_catalog_{name}_revision_hash"
        ),
        sa.CheckConstraint(
            "length(btrim(change_reason)) BETWEEN 1 AND 2000",
            name=f"ck_catalog_{name}_revision_reason",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "aggregate_id"],
            [
                f"catalog.{name}.organization_id",
                f"catalog.{name}.project_id",
                f"catalog.{name}.id",
            ],
            name=f"fk_catalog_{name}_revision_identity",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "aggregate_id", "based_on_revision_id"],
            [
                f"catalog.{name}_revision.organization_id",
                f"catalog.{name}_revision.project_id",
                f"catalog.{name}_revision.aggregate_id",
                f"catalog.{name}_revision.id",
            ],
            name=f"fk_catalog_{name}_revision_base",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
    ]


def _create_link_type() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    op.create_table(
        "link_type",
        *_identity_columns(uuid),
        sa.Column("link_key", sa.String(length=64), nullable=False),
        sa.Column("source_table_id", uuid, nullable=False),
        sa.Column("target_table_id", uuid, nullable=False),
        sa.PrimaryKeyConstraint("organization_id", "project_id", "id", name="pk_catalog_link_type"),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "classification",
            "id",
            name="uq_catalog_link_type_scoped_identity",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "classification",
            "link_key",
            name="uq_catalog_link_type_key",
        ),
        sa.CheckConstraint("link_key ~ '^[a-z][a-z0-9_]{0,63}$'", name="ck_catalog_link_type_key"),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "classification", "source_table_id"],
            [
                "catalog.schema_table.organization_id",
                "catalog.schema_table.project_id",
                "catalog.schema_table.classification",
                "catalog.schema_table.id",
            ],
            name="fk_catalog_link_type_source_table",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "classification", "target_table_id"],
            [
                "catalog.schema_table.organization_id",
                "catalog.schema_table.project_id",
                "catalog.schema_table.classification",
                "catalog.schema_table.id",
            ],
            name="fk_catalog_link_type_target_table",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        schema="catalog",
    )
    op.create_table(
        "link_type_revision",
        *_revision_columns(uuid),
        sa.Column("link_key", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("source_table_id", uuid, nullable=False),
        sa.Column("source_table_revision_id", uuid, nullable=False),
        sa.Column("target_table_id", uuid, nullable=False),
        sa.Column("target_table_revision_id", uuid, nullable=False),
        sa.Column("forward_label", sa.String(length=200), nullable=False),
        sa.Column("reverse_label", sa.String(length=200), nullable=False),
        sa.Column("source_cardinality", sa.String(length=16), nullable=False),
        sa.Column("target_cardinality", sa.String(length=16), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        *_revision_constraints("link_type"),
        sa.CheckConstraint(
            "link_key ~ '^[a-z][a-z0-9_]{0,63}$'", name="ck_catalog_link_type_revision_key"
        ),
        sa.CheckConstraint(
            "length(btrim(name)) BETWEEN 1 AND 200",
            name="ck_catalog_link_type_revision_name",
        ),
        sa.CheckConstraint(
            "length(btrim(forward_label)) BETWEEN 1 AND 200 AND "
            "length(btrim(reverse_label)) BETWEEN 1 AND 200",
            name="ck_catalog_link_type_revision_labels",
        ),
        sa.CheckConstraint(
            "source_cardinality IN ('one', 'many') AND target_cardinality IN ('one', 'many')",
            name="ck_catalog_link_type_revision_cardinality",
        ),
        sa.ForeignKeyConstraint(
            [
                "organization_id",
                "project_id",
                "classification",
                "source_table_id",
                "source_table_revision_id",
            ],
            [
                "catalog.schema_table_revision.organization_id",
                "catalog.schema_table_revision.project_id",
                "catalog.schema_table_revision.classification",
                "catalog.schema_table_revision.aggregate_id",
                "catalog.schema_table_revision.id",
            ],
            name="fk_catalog_link_type_revision_source_table",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.ForeignKeyConstraint(
            [
                "organization_id",
                "project_id",
                "classification",
                "target_table_id",
                "target_table_revision_id",
            ],
            [
                "catalog.schema_table_revision.organization_id",
                "catalog.schema_table_revision.project_id",
                "catalog.schema_table_revision.classification",
                "catalog.schema_table_revision.aggregate_id",
                "catalog.schema_table_revision.id",
            ],
            name="fk_catalog_link_type_revision_target_table",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        schema="catalog",
    )
    op.create_foreign_key(
        "fk_catalog_link_type_current_revision",
        "link_type",
        "link_type_revision",
        ["organization_id", "project_id", "id", "current_revision_id"],
        ["organization_id", "project_id", "aggregate_id", "id"],
        source_schema="catalog",
        referent_schema="catalog",
        ondelete="RESTRICT",
        deferrable=True,
        initially="DEFERRED",
    )


def _create_record_link() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    op.create_table(
        "record_link",
        *_identity_columns(uuid),
        sa.Column("link_type_id", uuid, nullable=False),
        sa.Column("source_record_id", uuid, nullable=False),
        sa.Column("target_record_id", uuid, nullable=False),
        sa.PrimaryKeyConstraint(
            "organization_id", "project_id", "id", name="pk_catalog_record_link"
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "classification",
            "id",
            name="uq_catalog_record_link_scoped_identity",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "classification",
            "link_type_id",
            "source_record_id",
            "target_record_id",
            name="uq_catalog_record_link_stable_endpoints",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "classification", "link_type_id"],
            [
                "catalog.link_type.organization_id",
                "catalog.link_type.project_id",
                "catalog.link_type.classification",
                "catalog.link_type.id",
            ],
            name="fk_catalog_record_link_type",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "classification", "source_record_id"],
            [
                "catalog.catalog_record.organization_id",
                "catalog.catalog_record.project_id",
                "catalog.catalog_record.classification",
                "catalog.catalog_record.id",
            ],
            name="fk_catalog_record_link_source",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "classification", "target_record_id"],
            [
                "catalog.catalog_record.organization_id",
                "catalog.catalog_record.project_id",
                "catalog.catalog_record.classification",
                "catalog.catalog_record.id",
            ],
            name="fk_catalog_record_link_target",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        schema="catalog",
    )
    op.create_table(
        "record_link_revision",
        *_revision_columns(uuid),
        sa.Column("link_type_id", uuid, nullable=False),
        sa.Column("link_type_revision_id", uuid, nullable=False),
        sa.Column("source_record_id", uuid, nullable=False),
        sa.Column("source_record_revision_id", uuid, nullable=False),
        sa.Column("target_record_id", uuid, nullable=False),
        sa.Column("target_record_revision_id", uuid, nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        *_revision_constraints("record_link"),
        sa.CheckConstraint(
            "NOT (source_record_id = target_record_id AND "
            "source_record_revision_id = target_record_revision_id)",
            name="ck_catalog_record_link_revision_not_self",
        ),
        sa.ForeignKeyConstraint(
            [
                "organization_id",
                "project_id",
                "classification",
                "link_type_id",
                "link_type_revision_id",
            ],
            [
                "catalog.link_type_revision.organization_id",
                "catalog.link_type_revision.project_id",
                "catalog.link_type_revision.classification",
                "catalog.link_type_revision.aggregate_id",
                "catalog.link_type_revision.id",
            ],
            name="fk_catalog_record_link_revision_type_revision",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.ForeignKeyConstraint(
            [
                "organization_id",
                "project_id",
                "classification",
                "source_record_id",
                "source_record_revision_id",
            ],
            [
                "catalog.catalog_record_revision.organization_id",
                "catalog.catalog_record_revision.project_id",
                "catalog.catalog_record_revision.classification",
                "catalog.catalog_record_revision.aggregate_id",
                "catalog.catalog_record_revision.id",
            ],
            name="fk_catalog_record_link_revision_source_revision",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.ForeignKeyConstraint(
            [
                "organization_id",
                "project_id",
                "classification",
                "target_record_id",
                "target_record_revision_id",
            ],
            [
                "catalog.catalog_record_revision.organization_id",
                "catalog.catalog_record_revision.project_id",
                "catalog.catalog_record_revision.classification",
                "catalog.catalog_record_revision.aggregate_id",
                "catalog.catalog_record_revision.id",
            ],
            name="fk_catalog_record_link_revision_target_revision",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        schema="catalog",
    )
    op.create_foreign_key(
        "fk_catalog_record_link_current_revision",
        "record_link",
        "record_link_revision",
        ["organization_id", "project_id", "id", "current_revision_id"],
        ["organization_id", "project_id", "aggregate_id", "id"],
        source_schema="catalog",
        referent_schema="catalog",
        ondelete="RESTRICT",
        deferrable=True,
        initially="DEFERRED",
    )


def _guards() -> None:
    op.execute(
        """
        CREATE FUNCTION catalog.guard_record_link_revision()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
            expected_source_table uuid;
            expected_target_table uuid;
            actual_source_table uuid;
            actual_target_table uuid;
            source_limit text;
            target_limit text;
        BEGIN
            SELECT source_table_id, target_table_id, source_cardinality, target_cardinality
              INTO expected_source_table, expected_target_table, source_limit, target_limit
              FROM catalog.link_type_revision
             WHERE organization_id = NEW.organization_id
               AND project_id = NEW.project_id
               AND classification = NEW.classification
               AND aggregate_id = NEW.link_type_id
               AND id = NEW.link_type_revision_id;
            SELECT table_id INTO actual_source_table
              FROM catalog.catalog_record_revision
             WHERE organization_id = NEW.organization_id
               AND project_id = NEW.project_id
               AND classification = NEW.classification
               AND aggregate_id = NEW.source_record_id
               AND id = NEW.source_record_revision_id;
            SELECT table_id INTO actual_target_table
              FROM catalog.catalog_record_revision
             WHERE organization_id = NEW.organization_id
               AND project_id = NEW.project_id
               AND classification = NEW.classification
               AND aggregate_id = NEW.target_record_id
               AND id = NEW.target_record_revision_id;
            IF expected_source_table IS DISTINCT FROM actual_source_table OR
               expected_target_table IS DISTINCT FROM actual_target_table THEN
                RAISE EXCEPTION 'Record Link endpoints do not match Link Type Tables'
                    USING ERRCODE = '23514';
            END IF;
            IF NOT NEW.active THEN
                RETURN NEW;
            END IF;
            PERFORM pg_advisory_xact_lock(hashtextextended(
                NEW.organization_id::text || NEW.project_id::text || NEW.link_type_id::text, 0
            ));
            IF EXISTS (
                SELECT 1
                  FROM catalog.record_link identity_row
                  JOIN catalog.record_link_revision head
                    ON head.organization_id = identity_row.organization_id
                   AND head.project_id = identity_row.project_id
                   AND head.classification = identity_row.classification
                   AND head.aggregate_id = identity_row.id
                   AND head.id = identity_row.current_revision_id
                 WHERE identity_row.organization_id = NEW.organization_id
                   AND identity_row.project_id = NEW.project_id
                   AND identity_row.classification = NEW.classification
                   AND identity_row.id <> NEW.aggregate_id
                   AND head.active
                   AND head.link_type_id = NEW.link_type_id
                   AND head.source_record_id = NEW.source_record_id
                   AND head.source_record_revision_id = NEW.source_record_revision_id
                   AND head.target_record_id = NEW.target_record_id
                   AND head.target_record_revision_id = NEW.target_record_revision_id
            ) THEN
                RAISE EXCEPTION 'duplicate active exact Record Link' USING ERRCODE = '23505';
            END IF;
            IF source_limit = 'one' AND EXISTS (
                SELECT 1
                  FROM catalog.record_link identity_row
                  JOIN catalog.record_link_revision head
                    ON head.organization_id = identity_row.organization_id
                   AND head.project_id = identity_row.project_id
                   AND head.classification = identity_row.classification
                   AND head.aggregate_id = identity_row.id
                   AND head.id = identity_row.current_revision_id
                 WHERE identity_row.organization_id = NEW.organization_id
                   AND identity_row.project_id = NEW.project_id
                   AND identity_row.classification = NEW.classification
                   AND identity_row.id <> NEW.aggregate_id
                   AND head.active
                   AND head.link_type_id = NEW.link_type_id
                   AND head.source_record_id = NEW.source_record_id
                   AND head.source_record_revision_id = NEW.source_record_revision_id
            ) THEN
                RAISE EXCEPTION 'source cardinality one exceeded' USING ERRCODE = '23514';
            END IF;
            IF target_limit = 'one' AND EXISTS (
                SELECT 1
                  FROM catalog.record_link identity_row
                  JOIN catalog.record_link_revision head
                    ON head.organization_id = identity_row.organization_id
                   AND head.project_id = identity_row.project_id
                   AND head.classification = identity_row.classification
                   AND head.aggregate_id = identity_row.id
                   AND head.id = identity_row.current_revision_id
                 WHERE identity_row.organization_id = NEW.organization_id
                   AND identity_row.project_id = NEW.project_id
                   AND identity_row.classification = NEW.classification
                   AND identity_row.id <> NEW.aggregate_id
                   AND head.active
                   AND head.link_type_id = NEW.link_type_id
                   AND head.target_record_id = NEW.target_record_id
                   AND head.target_record_revision_id = NEW.target_record_revision_id
            ) THEN
                RAISE EXCEPTION 'target cardinality one exceeded' USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        "CREATE TRIGGER catalog_record_link_revision_guard BEFORE INSERT "
        "ON catalog.record_link_revision FOR EACH ROW "
        "EXECUTE FUNCTION catalog.guard_record_link_revision()"
    )


def _secure_table(table: str) -> None:
    for operation in ("select", "insert", "update"):
        permission = "catalog.read" if operation == "select" else "catalog.write"
        if operation == "select":
            expression = (
                "USING (access_control.can_access_row(organization_id, project_id, "
                f"classification, '{permission}'))"
            )
        elif operation == "insert":
            expression = (
                "WITH CHECK (access_control.can_access_row(organization_id, project_id, "
                f"classification, '{permission}'))"
            )
        else:
            expression = (
                "USING (access_control.can_access_row(organization_id, project_id, "
                f"classification, '{permission}')) WITH CHECK "
                "(access_control.can_access_row(organization_id, project_id, "
                f"classification, '{permission}'))"
            )
        op.execute(
            f"CREATE POLICY catalog_{table}_{operation} ON catalog.{table} "
            f"FOR {operation.upper()} {expression}"
        )


def _indexes_and_security() -> None:
    op.create_index(
        "ix_catalog_link_type_endpoints",
        "link_type",
        ["organization_id", "project_id", "source_table_id", "target_table_id"],
        schema="catalog",
    )
    op.create_index(
        "ix_catalog_record_link_source",
        "record_link_revision",
        ["organization_id", "project_id", "source_record_id", "source_record_revision_id"],
        schema="catalog",
    )
    op.create_index(
        "ix_catalog_record_link_target",
        "record_link_revision",
        ["organization_id", "project_id", "target_record_id", "target_record_revision_id"],
        schema="catalog",
    )
    for identity in ("link_type", "record_link"):
        op.execute(
            f"CREATE TRIGGER catalog_{identity}_head_only BEFORE UPDATE OR DELETE "
            f"ON catalog.{identity} FOR EACH ROW "
            "EXECUTE FUNCTION revisioning.guard_identity_head_update()"
        )
    for table in ("link_type_revision", "record_link_revision"):
        op.execute(
            f"CREATE TRIGGER catalog_{table}_immutable BEFORE UPDATE OR DELETE "
            f"ON catalog.{table} FOR EACH ROW "
            "EXECUTE FUNCTION revisioning.reject_immutable_row_mutation()"
        )
    for table in ("link_type", "link_type_revision", "record_link", "record_link_revision"):
        op.execute(f"ALTER TABLE catalog.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE catalog.{table} FORCE ROW LEVEL SECURITY")
        _secure_table(table)


def upgrade() -> None:
    _create_link_type()
    _create_record_link()
    _guards()
    _indexes_and_security()


def downgrade() -> None:
    op.execute("DROP TRIGGER catalog_record_link_revision_guard ON catalog.record_link_revision")
    op.execute("DROP FUNCTION catalog.guard_record_link_revision()")
    op.drop_constraint(
        "fk_catalog_record_link_current_revision",
        "record_link",
        schema="catalog",
        type_="foreignkey",
    )
    op.drop_table("record_link_revision", schema="catalog")
    op.drop_table("record_link", schema="catalog")
    op.drop_constraint(
        "fk_catalog_link_type_current_revision", "link_type", schema="catalog", type_="foreignkey"
    )
    op.drop_table("link_type_revision", schema="catalog")
    op.drop_table("link_type", schema="catalog")

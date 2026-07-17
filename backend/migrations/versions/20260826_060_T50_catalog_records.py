"""T-50 configurable Catalog folders, datasheets and indexed record search.

Traceability: ADR-0028; FR-CFG-008..014; T-50. The migration activates the
typed record storage introduced by T-49. Folder and record links pin exact revisions.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260826_060_t50"
down_revision: str | None = "20260825_059_t49"
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


def _create_folder() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    op.create_table(
        "folder",
        *_identity_columns(uuid),
        sa.Column("table_id", uuid, nullable=False),
        sa.PrimaryKeyConstraint("organization_id", "project_id", "id", name="pk_catalog_folder"),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "classification",
            "id",
            name="uq_catalog_folder_scoped_identity",
        ),
        sa.CheckConstraint(
            "classification ~ '^[a-z][a-z0-9_.-]{0,63}$'",
            name="ck_catalog_folder_classification",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "classification", "table_id"],
            [
                "catalog.schema_table.organization_id",
                "catalog.schema_table.project_id",
                "catalog.schema_table.classification",
                "catalog.schema_table.id",
            ],
            name="fk_catalog_folder_table",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        schema="catalog",
    )
    op.create_table(
        "folder_revision",
        *_revision_columns(uuid),
        sa.Column("table_id", uuid, nullable=False),
        sa.Column("table_revision_id", uuid, nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("parent_folder_id", uuid, nullable=True),
        sa.Column("parent_folder_revision_id", uuid, nullable=True),
        sa.PrimaryKeyConstraint(
            "organization_id", "project_id", "id", name="pk_catalog_folder_revision"
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "aggregate_id",
            "id",
            name="uq_catalog_folder_revision_scope_id",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "classification",
            "aggregate_id",
            "id",
            name="uq_catalog_folder_revision_scoped_reference",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "aggregate_id",
            "revision_no",
            name="uq_catalog_folder_revision_number",
        ),
        sa.CheckConstraint("revision_no > 0", name="ck_catalog_folder_revision_number"),
        sa.CheckConstraint(
            "(revision_no = 1 AND based_on_revision_id IS NULL) OR "
            "(revision_no > 1 AND based_on_revision_id IS NOT NULL)",
            name="ck_catalog_folder_revision_base",
        ),
        sa.CheckConstraint(
            "content_hash ~ '^[0-9a-f]{64}$'", name="ck_catalog_folder_revision_hash"
        ),
        sa.CheckConstraint(
            "length(btrim(change_reason)) BETWEEN 1 AND 2000",
            name="ck_catalog_folder_revision_reason",
        ),
        sa.CheckConstraint(
            "length(btrim(name)) BETWEEN 1 AND 200", name="ck_catalog_folder_revision_name"
        ),
        sa.CheckConstraint(
            "(parent_folder_id IS NULL) = (parent_folder_revision_id IS NULL)",
            name="ck_catalog_folder_revision_parent_pair",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "aggregate_id"],
            [
                "catalog.folder.organization_id",
                "catalog.folder.project_id",
                "catalog.folder.id",
            ],
            name="fk_catalog_folder_revision_identity",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "aggregate_id", "based_on_revision_id"],
            [
                "catalog.folder_revision.organization_id",
                "catalog.folder_revision.project_id",
                "catalog.folder_revision.aggregate_id",
                "catalog.folder_revision.id",
            ],
            name="fk_catalog_folder_revision_base",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.ForeignKeyConstraint(
            [
                "organization_id",
                "project_id",
                "classification",
                "table_id",
                "table_revision_id",
            ],
            [
                "catalog.schema_table_revision.organization_id",
                "catalog.schema_table_revision.project_id",
                "catalog.schema_table_revision.classification",
                "catalog.schema_table_revision.aggregate_id",
                "catalog.schema_table_revision.id",
            ],
            name="fk_catalog_folder_revision_table_revision",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.ForeignKeyConstraint(
            [
                "organization_id",
                "project_id",
                "classification",
                "parent_folder_id",
                "parent_folder_revision_id",
            ],
            [
                "catalog.folder_revision.organization_id",
                "catalog.folder_revision.project_id",
                "catalog.folder_revision.classification",
                "catalog.folder_revision.aggregate_id",
                "catalog.folder_revision.id",
            ],
            name="fk_catalog_folder_revision_parent_revision",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        schema="catalog",
    )
    op.create_foreign_key(
        "fk_catalog_folder_current_revision",
        "folder",
        "folder_revision",
        ["organization_id", "project_id", "id", "current_revision_id"],
        ["organization_id", "project_id", "aggregate_id", "id"],
        source_schema="catalog",
        referent_schema="catalog",
        ondelete="RESTRICT",
        deferrable=True,
        initially="DEFERRED",
    )


def _attach_records_to_folders() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    op.add_column(
        "catalog_record_revision", sa.Column("folder_id", uuid, nullable=True), schema="catalog"
    )
    op.add_column(
        "catalog_record_revision",
        sa.Column("folder_revision_id", uuid, nullable=True),
        schema="catalog",
    )
    op.create_check_constraint(
        "ck_catalog_record_revision_folder_pair",
        "catalog_record_revision",
        "(folder_id IS NULL) = (folder_revision_id IS NULL)",
        schema="catalog",
    )
    op.create_foreign_key(
        "fk_catalog_record_revision_folder_revision",
        "catalog_record_revision",
        "folder_revision",
        [
            "organization_id",
            "project_id",
            "classification",
            "folder_id",
            "folder_revision_id",
        ],
        [
            "organization_id",
            "project_id",
            "classification",
            "aggregate_id",
            "id",
        ],
        source_schema="catalog",
        referent_schema="catalog",
        ondelete="RESTRICT",
        deferrable=True,
        initially="DEFERRED",
    )


def _guards() -> None:
    op.execute(
        """
        CREATE FUNCTION catalog.guard_folder_revision()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
            parent_table uuid;
            cycle_found boolean;
        BEGIN
            IF NEW.parent_folder_id IS NULL THEN
                RETURN NEW;
            END IF;
            SELECT table_id INTO parent_table
              FROM catalog.folder_revision
             WHERE organization_id = NEW.organization_id
               AND project_id = NEW.project_id
               AND classification = NEW.classification
               AND aggregate_id = NEW.parent_folder_id
               AND id = NEW.parent_folder_revision_id;
            IF parent_table IS DISTINCT FROM NEW.table_id THEN
                RAISE EXCEPTION 'Folder parent must belong to the same Table'
                    USING ERRCODE = '23514';
            END IF;
            WITH RECURSIVE ancestors AS (
                SELECT aggregate_id, parent_folder_id, parent_folder_revision_id
                  FROM catalog.folder_revision
                 WHERE organization_id = NEW.organization_id
                   AND project_id = NEW.project_id
                   AND classification = NEW.classification
                   AND aggregate_id = NEW.parent_folder_id
                   AND id = NEW.parent_folder_revision_id
                UNION
                SELECT parent.aggregate_id,
                       parent.parent_folder_id,
                       parent.parent_folder_revision_id
                  FROM catalog.folder_revision parent
                  JOIN ancestors child
                    ON parent.organization_id = NEW.organization_id
                   AND parent.project_id = NEW.project_id
                   AND parent.classification = NEW.classification
                   AND parent.aggregate_id = child.parent_folder_id
                   AND parent.id = child.parent_folder_revision_id
            )
            SELECT EXISTS(
                SELECT 1 FROM ancestors WHERE aggregate_id = NEW.aggregate_id
            ) INTO cycle_found;
            IF cycle_found THEN
                RAISE EXCEPTION 'Folder parent relationship creates a cycle'
                    USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        "CREATE TRIGGER catalog_folder_revision_guard BEFORE INSERT "
        "ON catalog.folder_revision FOR EACH ROW "
        "EXECUTE FUNCTION catalog.guard_folder_revision()"
    )
    op.execute(
        """
        CREATE FUNCTION catalog.guard_record_folder_table()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE folder_table uuid;
        BEGIN
            IF NEW.folder_id IS NULL THEN
                RETURN NEW;
            END IF;
            SELECT table_id INTO folder_table
              FROM catalog.folder_revision
             WHERE organization_id = NEW.organization_id
               AND project_id = NEW.project_id
               AND classification = NEW.classification
               AND aggregate_id = NEW.folder_id
               AND id = NEW.folder_revision_id;
            IF folder_table IS DISTINCT FROM NEW.table_id THEN
                RAISE EXCEPTION 'Catalog Record and Folder must belong to the same Table'
                    USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        "CREATE TRIGGER catalog_record_revision_folder_guard BEFORE INSERT "
        "ON catalog.catalog_record_revision FOR EACH ROW "
        "EXECUTE FUNCTION catalog.guard_record_folder_table()"
    )


def _indexes_and_security() -> None:
    op.create_index(
        "ix_catalog_folder_tenant_head",
        "folder",
        ["organization_id", "project_id", "classification", "current_revision_id"],
        schema="catalog",
    )
    op.create_index(
        "ix_catalog_folder_table",
        "folder",
        ["organization_id", "project_id", "classification", "table_id"],
        schema="catalog",
    )
    op.create_index(
        "ix_catalog_folder_revision_parent",
        "folder_revision",
        ["organization_id", "project_id", "parent_folder_id", "parent_folder_revision_id"],
        schema="catalog",
    )
    op.create_index(
        "ix_catalog_record_revision_folder",
        "catalog_record_revision",
        ["organization_id", "project_id", "table_id", "folder_id"],
        schema="catalog",
    )
    op.execute(
        "CREATE INDEX ix_catalog_record_revision_name_search "
        "ON catalog.catalog_record_revision "
        "(organization_id, project_id, table_id, lower(name) text_pattern_ops)"
    )
    op.execute(
        "CREATE INDEX ix_catalog_record_text_value_search_value "
        "ON catalog.record_text_value "
        "(organization_id, project_id, attribute_definition_id, lower(value) text_pattern_ops)"
    )
    op.create_index(
        "ix_catalog_record_discrete_search",
        "record_discrete_value",
        ["organization_id", "project_id", "attribute_definition_id", "value"],
        schema="catalog",
    )
    op.execute(
        "CREATE TRIGGER catalog_folder_head_only BEFORE UPDATE OR DELETE "
        "ON catalog.folder FOR EACH ROW "
        "EXECUTE FUNCTION revisioning.guard_identity_head_update()"
    )
    op.execute(
        "CREATE TRIGGER catalog_folder_revision_immutable BEFORE UPDATE OR DELETE "
        "ON catalog.folder_revision FOR EACH ROW "
        "EXECUTE FUNCTION revisioning.reject_immutable_row_mutation()"
    )
    for table in ("folder", "folder_revision"):
        op.execute(f"ALTER TABLE catalog.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE catalog.{table} FORCE ROW LEVEL SECURITY")
        _secure_table(table)


def upgrade() -> None:
    _create_folder()
    _attach_records_to_folders()
    _guards()
    _indexes_and_security()


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER catalog_record_revision_folder_guard "
        "ON catalog.catalog_record_revision"
    )
    op.execute("DROP FUNCTION catalog.guard_record_folder_table()")
    op.drop_constraint(
        "fk_catalog_record_revision_folder_revision",
        "catalog_record_revision",
        schema="catalog",
        type_="foreignkey",
    )
    op.drop_constraint(
        "ck_catalog_record_revision_folder_pair",
        "catalog_record_revision",
        schema="catalog",
        type_="check",
    )
    op.drop_column("catalog_record_revision", "folder_revision_id", schema="catalog")
    op.drop_column("catalog_record_revision", "folder_id", schema="catalog")
    op.drop_constraint(
        "fk_catalog_folder_current_revision", "folder", schema="catalog", type_="foreignkey"
    )
    op.drop_table("folder_revision", schema="catalog")
    op.drop_table("folder", schema="catalog")
    op.execute("DROP FUNCTION catalog.guard_folder_revision()")

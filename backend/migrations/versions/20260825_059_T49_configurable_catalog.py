"""T-49 configurable catalog schema and typed record value storage.

Traceability: ADR-0028; FR-CFG-001..007; T-49. Record values are stored in
type-specific relations. There is no generic untyped EAV value column and no opaque
record JSON authority.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260825_059_t49"
down_revision: str | None = "20260824_058_t47_leases"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_IDENTITIES = ("schema_table", "attribute_definition", "layout", "subset", "catalog_record")
_REVISIONS = (
    "schema_table_revision",
    "attribute_definition_revision",
    "layout_revision",
    "subset_revision",
    "catalog_record_revision",
)
_VALUE_TABLES = {
    "record_number_value": (
        sa.Column("original_value", sa.Numeric(), nullable=False),
        sa.Column("original_unit_string", sa.String(length=64), nullable=False),
        sa.Column("normalized_value", sa.Numeric(), nullable=False),
        sa.Column("normalized_unit", sa.String(length=64), nullable=False),
        sa.Column("quantity_semantics", sa.String(length=255), nullable=False),
    ),
    "record_integer_value": (sa.Column("value", sa.BigInteger(), nullable=False),),
    "record_text_value": (sa.Column("value", sa.Text(), nullable=False),),
    "record_boolean_value": (sa.Column("value", sa.Boolean(), nullable=False),),
    "record_date_value": (sa.Column("value", sa.Date(), nullable=False),),
    "record_discrete_value": (sa.Column("value", sa.String(length=255), nullable=False),),
    "record_file_value": (
        sa.Column("artifact_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("artifact_sha256", sa.CHAR(length=64, collation="C"), nullable=False),
    ),
    "record_curve_value": (
        sa.Column("artifact_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("artifact_sha256", sa.CHAR(length=64, collation="C"), nullable=False),
    ),
    "record_reference_value": (
        sa.Column("target_record_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target_record_revision_id", postgresql.UUID(as_uuid=True), nullable=False),
    ),
}
_EXPECTED_TYPE = {
    "record_number_value": "number",
    "record_integer_value": "integer",
    "record_text_value": "text",
    "record_boolean_value": "boolean",
    "record_date_value": "date",
    "record_discrete_value": "discrete",
    "record_file_value": "file",
    "record_curve_value": "curve",
    "record_reference_value": "record_reference",
}


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


def _identity_constraints(name: str) -> list[sa.Constraint]:
    return [
        sa.PrimaryKeyConstraint("organization_id", "project_id", "id", name=f"pk_catalog_{name}"),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "classification",
            "id",
            name=f"uq_catalog_{name}_scoped_identity",
        ),
        sa.CheckConstraint(
            "classification ~ '^[a-z][a-z0-9_.-]{0,63}$'",
            name=f"ck_catalog_{name}_classification",
        ),
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
    ]


def _revision_foreign_keys(name: str) -> list[sa.ForeignKeyConstraint]:
    return [
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "aggregate_id"],
            [f"catalog.{name}.organization_id", f"catalog.{name}.project_id", f"catalog.{name}.id"],
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


def _create_revision_pair(
    name: str,
    identity_extra: tuple[sa.SchemaItem, ...],
    revision_extra: tuple[sa.SchemaItem, ...],
) -> None:
    uuid = postgresql.UUID(as_uuid=True)
    op.create_table(
        name,
        *_identity_columns(uuid),
        *identity_extra,
        *_identity_constraints(name),
        schema="catalog",
    )
    op.create_table(
        f"{name}_revision",
        *_revision_columns(uuid),
        *revision_extra,
        *_revision_constraints(name),
        *_revision_foreign_keys(name),
        schema="catalog",
    )
    op.create_foreign_key(
        f"fk_catalog_{name}_current_revision",
        name,
        f"{name}_revision",
        ["organization_id", "project_id", "id", "current_revision_id"],
        ["organization_id", "project_id", "aggregate_id", "id"],
        source_schema="catalog",
        referent_schema="catalog",
        ondelete="RESTRICT",
        deferrable=True,
        initially="DEFERRED",
    )


def _table_revision_fk(local_table: str, local_revision: str, name: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        ["organization_id", "project_id", "classification", local_table, local_revision],
        [
            "catalog.schema_table_revision.organization_id",
            "catalog.schema_table_revision.project_id",
            "catalog.schema_table_revision.classification",
            "catalog.schema_table_revision.aggregate_id",
            "catalog.schema_table_revision.id",
        ],
        name=name,
        ondelete="RESTRICT",
        deferrable=True,
        initially="DEFERRED",
    )


def _create_schema_tables() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    _create_revision_pair(
        "schema_table",
        (
            sa.Column("table_key", sa.String(length=64), nullable=False),
            sa.UniqueConstraint(
                "organization_id",
                "project_id",
                "table_key",
                name="uq_catalog_schema_table_tenant_key",
            ),
        ),
        (
            sa.Column("table_key", sa.String(length=64), nullable=False),
            sa.Column("name", sa.String(length=200), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.CheckConstraint(
                "table_key ~ '^[a-z][a-z0-9_]{0,63}$'", name="ck_catalog_schema_table_key"
            ),
            sa.CheckConstraint(
                "length(btrim(name)) BETWEEN 1 AND 200", name="ck_catalog_schema_table_name"
            ),
        ),
    )
    _create_revision_pair(
        "attribute_definition",
        (
            sa.Column("table_id", uuid, nullable=False),
            sa.Column("attribute_key", sa.String(length=64), nullable=False),
            sa.UniqueConstraint(
                "organization_id",
                "project_id",
                "table_id",
                "attribute_key",
                name="uq_catalog_attribute_definition_table_key",
            ),
            sa.ForeignKeyConstraint(
                ["organization_id", "project_id", "classification", "table_id"],
                [
                    "catalog.schema_table.organization_id",
                    "catalog.schema_table.project_id",
                    "catalog.schema_table.classification",
                    "catalog.schema_table.id",
                ],
                name="fk_catalog_attribute_definition_table",
                ondelete="RESTRICT",
                deferrable=True,
                initially="DEFERRED",
            ),
        ),
        (
            sa.Column("table_id", uuid, nullable=False),
            sa.Column("table_revision_id", uuid, nullable=False),
            sa.Column("attribute_key", sa.String(length=64), nullable=False),
            sa.Column("name", sa.String(length=200), nullable=False),
            sa.Column("data_type", sa.String(length=32), nullable=False),
            sa.Column("required", sa.Boolean(), nullable=False),
            sa.Column("quantity_semantics", sa.String(length=255), nullable=True),
            sa.Column("normalized_unit", sa.String(length=64), nullable=True),
            sa.Column("minimum_number", sa.Numeric(), nullable=True),
            sa.Column("maximum_number", sa.Numeric(), nullable=True),
            sa.Column("minimum_length", sa.Integer(), nullable=True),
            sa.Column("maximum_length", sa.Integer(), nullable=True),
            sa.Column("pattern", sa.String(length=500), nullable=True),
            sa.Column("allowed_values", postgresql.ARRAY(sa.String(length=255)), nullable=False),
            sa.Column("reference_table_id", uuid, nullable=True),
            sa.Column("help_text", sa.Text(), nullable=True),
            _table_revision_fk(
                "table_id", "table_revision_id", "fk_catalog_attribute_revision_table_revision"
            ),
            sa.CheckConstraint(
                "data_type IN ('number','integer','text','boolean','date','discrete',"
                "'file','curve','record_reference')",
                name="ck_catalog_attribute_revision_data_type",
            ),
            sa.CheckConstraint(
                "(minimum_number IS NULL OR maximum_number IS NULL "
                "OR minimum_number <= maximum_number)",
                name="ck_catalog_attribute_revision_number_range",
            ),
            sa.CheckConstraint(
                "(data_type = 'discrete' AND cardinality(allowed_values) > 0) OR "
                "(data_type <> 'discrete' AND cardinality(allowed_values) = 0)",
                name="ck_catalog_attribute_revision_discrete_values",
            ),
            sa.CheckConstraint(
                "(data_type = 'record_reference' AND reference_table_id IS NOT NULL) OR "
                "(data_type <> 'record_reference' AND reference_table_id IS NULL)",
                name="ck_catalog_attribute_revision_reference_table",
            ),
            sa.ForeignKeyConstraint(
                ["organization_id", "project_id", "classification", "reference_table_id"],
                [
                    "catalog.schema_table.organization_id",
                    "catalog.schema_table.project_id",
                    "catalog.schema_table.classification",
                    "catalog.schema_table.id",
                ],
                name="fk_catalog_attribute_revision_reference_table",
                ondelete="RESTRICT",
                deferrable=True,
                initially="DEFERRED",
            ),
        ),
    )

    for name in ("layout", "subset"):
        _create_revision_pair(
            name,
            (
                sa.Column("table_id", uuid, nullable=False),
                sa.ForeignKeyConstraint(
                    ["organization_id", "project_id", "classification", "table_id"],
                    [
                        "catalog.schema_table.organization_id",
                        "catalog.schema_table.project_id",
                        "catalog.schema_table.classification",
                        "catalog.schema_table.id",
                    ],
                    name=f"fk_catalog_{name}_table",
                    ondelete="RESTRICT",
                    deferrable=True,
                    initially="DEFERRED",
                ),
            ),
            (
                sa.Column("table_id", uuid, nullable=False),
                sa.Column("table_revision_id", uuid, nullable=False),
                sa.Column("name", sa.String(length=200), nullable=False),
                sa.Column("description", sa.Text(), nullable=True),
                *(
                    (
                        sa.Column("filter_definition", sa.Text(), nullable=False),
                        sa.CheckConstraint(
                            "length(filter_definition) BETWEEN 2 AND 65536",
                            name="ck_catalog_subset_revision_filter_length",
                        ),
                    )
                    if name == "subset"
                    else ()
                ),
                _table_revision_fk(
                    "table_id", "table_revision_id", f"fk_catalog_{name}_revision_table_revision"
                ),
            ),
        )

    op.create_table(
        "layout_item",
        sa.Column("organization_id", uuid, nullable=False),
        sa.Column("project_id", uuid, nullable=False),
        sa.Column("classification", sa.String(length=64), nullable=False),
        sa.Column("layout_id", uuid, nullable=False),
        sa.Column("layout_revision_id", uuid, nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("attribute_definition_id", uuid, nullable=False),
        sa.Column("attribute_definition_revision_id", uuid, nullable=False),
        sa.Column("section", sa.String(length=100), nullable=False),
        sa.PrimaryKeyConstraint(
            "organization_id",
            "project_id",
            "layout_revision_id",
            "ordinal",
            name="pk_catalog_layout_item",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "layout_revision_id",
            "attribute_definition_id",
            name="uq_catalog_layout_item_attribute",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "classification", "layout_id", "layout_revision_id"],
            [
                "catalog.layout_revision.organization_id",
                "catalog.layout_revision.project_id",
                "catalog.layout_revision.classification",
                "catalog.layout_revision.aggregate_id",
                "catalog.layout_revision.id",
            ],
            name="fk_catalog_layout_item_layout_revision",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            [
                "organization_id",
                "project_id",
                "classification",
                "attribute_definition_id",
                "attribute_definition_revision_id",
            ],
            [
                "catalog.attribute_definition_revision.organization_id",
                "catalog.attribute_definition_revision.project_id",
                "catalog.attribute_definition_revision.classification",
                "catalog.attribute_definition_revision.aggregate_id",
                "catalog.attribute_definition_revision.id",
            ],
            name="fk_catalog_layout_item_attribute_revision",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint("ordinal >= 0", name="ck_catalog_layout_item_ordinal"),
        schema="catalog",
    )


def _create_record_storage() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    _create_revision_pair(
        "catalog_record",
        (
            sa.Column("table_id", uuid, nullable=False),
            sa.ForeignKeyConstraint(
                ["organization_id", "project_id", "classification", "table_id"],
                [
                    "catalog.schema_table.organization_id",
                    "catalog.schema_table.project_id",
                    "catalog.schema_table.classification",
                    "catalog.schema_table.id",
                ],
                name="fk_catalog_record_table",
                ondelete="RESTRICT",
                deferrable=True,
                initially="DEFERRED",
            ),
        ),
        (
            sa.Column("table_id", uuid, nullable=False),
            sa.Column("table_revision_id", uuid, nullable=False),
            sa.Column("name", sa.String(length=200), nullable=False),
            sa.Column("external_key", sa.String(length=255), nullable=True),
            sa.Column("description", sa.Text(), nullable=True),
            _table_revision_fk(
                "table_id", "table_revision_id", "fk_catalog_record_revision_table_revision"
            ),
        ),
    )
    for table_name, columns in _VALUE_TABLES.items():
        constraints: list[sa.SchemaItem] = [
            sa.PrimaryKeyConstraint(
                "organization_id",
                "project_id",
                "record_revision_id",
                "attribute_definition_id",
                name=f"pk_catalog_{table_name}",
            ),
            sa.ForeignKeyConstraint(
                [
                    "organization_id",
                    "project_id",
                    "classification",
                    "record_id",
                    "record_revision_id",
                ],
                [
                    "catalog.catalog_record_revision.organization_id",
                    "catalog.catalog_record_revision.project_id",
                    "catalog.catalog_record_revision.classification",
                    "catalog.catalog_record_revision.aggregate_id",
                    "catalog.catalog_record_revision.id",
                ],
                name=f"fk_catalog_{table_name}_record_revision",
                ondelete="RESTRICT",
            ),
            sa.ForeignKeyConstraint(
                [
                    "organization_id",
                    "project_id",
                    "classification",
                    "attribute_definition_id",
                    "attribute_definition_revision_id",
                ],
                [
                    "catalog.attribute_definition_revision.organization_id",
                    "catalog.attribute_definition_revision.project_id",
                    "catalog.attribute_definition_revision.classification",
                    "catalog.attribute_definition_revision.aggregate_id",
                    "catalog.attribute_definition_revision.id",
                ],
                name=f"fk_catalog_{table_name}_attribute_revision",
                ondelete="RESTRICT",
            ),
        ]
        if table_name in {"record_file_value", "record_curve_value"}:
            constraints.append(
                sa.ForeignKeyConstraint(
                    [
                        "organization_id",
                        "project_id",
                        "classification",
                        "artifact_id",
                        "artifact_sha256",
                    ],
                    [
                        "artifact.artifact.organization_id",
                        "artifact.artifact.project_id",
                        "artifact.artifact.classification",
                        "artifact.artifact.id",
                        "artifact.artifact.sha256",
                    ],
                    name=f"fk_catalog_{table_name}_artifact",
                    ondelete="RESTRICT",
                )
            )
            constraints.append(
                sa.CheckConstraint(
                    "artifact_sha256 ~ '^[0-9a-f]{64}$'",
                    name=f"ck_catalog_{table_name}_digest",
                )
            )
        if table_name == "record_number_value":
            constraints.append(
                sa.CheckConstraint(
                    "length(btrim(original_unit_string)) BETWEEN 1 AND 64 AND "
                    "length(btrim(normalized_unit)) BETWEEN 1 AND 64 AND "
                    "length(btrim(quantity_semantics)) BETWEEN 1 AND 255",
                    name="ck_catalog_record_number_value_semantics",
                )
            )
        if table_name == "record_reference_value":
            constraints.append(
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
                    name="fk_catalog_record_reference_value_target_revision",
                    ondelete="RESTRICT",
                )
            )
        op.create_table(
            table_name,
            sa.Column("organization_id", uuid, nullable=False),
            sa.Column("project_id", uuid, nullable=False),
            sa.Column("classification", sa.String(length=64), nullable=False),
            sa.Column("record_id", uuid, nullable=False),
            sa.Column("record_revision_id", uuid, nullable=False),
            sa.Column("attribute_definition_id", uuid, nullable=False),
            sa.Column("attribute_definition_revision_id", uuid, nullable=False),
            *columns,
            *constraints,
            schema="catalog",
        )


def _create_guards() -> None:
    op.execute(
        """
        CREATE FUNCTION catalog.guard_typed_record_value()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
            expected_type text := TG_ARGV[0];
            actual_type text;
            attribute_table uuid;
            record_table uuid;
            expected_semantics text;
            expected_unit text;
            permitted_values text[];
            expected_reference_table uuid;
            target_record_table uuid;
        BEGIN
            SELECT data_type, table_id, quantity_semantics, normalized_unit,
                   allowed_values, reference_table_id
              INTO actual_type, attribute_table, expected_semantics, expected_unit,
                   permitted_values, expected_reference_table
              FROM catalog.attribute_definition_revision
             WHERE organization_id = NEW.organization_id
               AND project_id = NEW.project_id
               AND classification = NEW.classification
               AND aggregate_id = NEW.attribute_definition_id
               AND id = NEW.attribute_definition_revision_id;
            SELECT table_id INTO record_table
              FROM catalog.catalog_record_revision
             WHERE organization_id = NEW.organization_id
               AND project_id = NEW.project_id
               AND classification = NEW.classification
               AND aggregate_id = NEW.record_id
               AND id = NEW.record_revision_id;
            IF actual_type IS DISTINCT FROM expected_type THEN
                RAISE EXCEPTION 'attribute data type % cannot be stored in %',
                    actual_type, TG_TABLE_NAME
                    USING ERRCODE = '23514';
            END IF;
            IF attribute_table IS DISTINCT FROM record_table THEN
                RAISE EXCEPTION 'attribute and record must belong to the same catalog table'
                    USING ERRCODE = '23514';
            END IF;
            IF expected_type = 'number' AND (
                (to_jsonb(NEW)->>'quantity_semantics') IS DISTINCT FROM expected_semantics OR
                (to_jsonb(NEW)->>'normalized_unit') IS DISTINCT FROM expected_unit
            ) THEN
                RAISE EXCEPTION 'number value metadata must match Attribute revision'
                    USING ERRCODE = '23514';
            END IF;
            IF expected_type = 'discrete' AND NOT (
                (to_jsonb(NEW)->>'value') = ANY(permitted_values)
            ) THEN
                RAISE EXCEPTION 'discrete value is not allowed by Attribute revision'
                    USING ERRCODE = '23514';
            END IF;
            IF expected_type = 'record_reference' THEN
                SELECT table_id INTO target_record_table
                  FROM catalog.catalog_record_revision
                 WHERE organization_id = NEW.organization_id
                   AND project_id = NEW.project_id
                   AND classification = NEW.classification
                   AND aggregate_id = (to_jsonb(NEW)->>'target_record_id')::uuid
                   AND id = (to_jsonb(NEW)->>'target_record_revision_id')::uuid;
                IF target_record_table IS DISTINCT FROM expected_reference_table THEN
                    RAISE EXCEPTION 'record reference target does not match Attribute target Table'
                        USING ERRCODE = '23514';
                END IF;
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    for table_name, expected in _EXPECTED_TYPE.items():
        op.execute(
            f"CREATE TRIGGER catalog_{table_name}_type_guard "
            f"BEFORE INSERT ON catalog.{table_name} FOR EACH ROW "
            f"EXECUTE FUNCTION catalog.guard_typed_record_value('{expected}')"
        )


def _secure_table(table: str) -> None:
    for operation, predicate in (
        ("select", "USING"),
        ("insert", "WITH CHECK"),
        ("update", "USING"),
    ):
        permission = "catalog.read" if operation == "select" else "catalog.write"
        if operation == "update":
            expression = (
                "USING (access_control.can_access_row(organization_id, project_id, "
                f"classification, '{permission}')) WITH CHECK "
                "(access_control.can_access_row(organization_id, project_id, "
                f"classification, '{permission}'))"
            )
        else:
            expression = (
                f"{predicate} (access_control.can_access_row(organization_id, project_id, "
                f"classification, '{permission}'))"
            )
        op.execute(
            f"CREATE POLICY catalog_{table}_{operation} ON catalog.{table} "
            f"FOR {operation.upper()} {expression}"
        )


def _secure_tables() -> None:
    immutable = (*_REVISIONS, "layout_item", *_VALUE_TABLES)
    for identity in _IDENTITIES:
        op.execute(
            f"CREATE TRIGGER catalog_{identity}_head_only BEFORE UPDATE OR DELETE "
            f"ON catalog.{identity} FOR EACH ROW "
            "EXECUTE FUNCTION revisioning.guard_identity_head_update()"
        )
    for table in immutable:
        op.execute(
            f"CREATE TRIGGER catalog_{table}_immutable BEFORE UPDATE OR DELETE "
            f"ON catalog.{table} FOR EACH ROW "
            "EXECUTE FUNCTION revisioning.reject_immutable_row_mutation()"
        )
    for table in (*_IDENTITIES, *immutable):
        op.execute(f"ALTER TABLE catalog.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE catalog.{table} FORCE ROW LEVEL SECURITY")
        _secure_table(table)


def _indexes() -> None:
    for table in _IDENTITIES:
        op.create_index(
            f"ix_catalog_{table}_tenant_head",
            table,
            ["organization_id", "project_id", "classification", "current_revision_id"],
            schema="catalog",
        )
    op.create_index(
        "ix_catalog_attribute_definition_table",
        "attribute_definition",
        ["organization_id", "project_id", "classification", "table_id", "attribute_key"],
        schema="catalog",
    )
    op.create_index(
        "ix_catalog_layout_table",
        "layout",
        ["organization_id", "project_id", "classification", "table_id"],
        schema="catalog",
    )
    op.create_index(
        "ix_catalog_subset_table",
        "subset",
        ["organization_id", "project_id", "classification", "table_id"],
        schema="catalog",
    )
    op.create_index(
        "ix_catalog_record_table",
        "catalog_record",
        ["organization_id", "project_id", "classification", "table_id"],
        schema="catalog",
    )
    op.create_index(
        "ix_catalog_record_number_search",
        "record_number_value",
        ["organization_id", "project_id", "attribute_definition_id", "normalized_value"],
        schema="catalog",
    )
    op.create_index(
        "ix_catalog_record_text_search",
        "record_text_value",
        ["organization_id", "project_id", "attribute_definition_id"],
        schema="catalog",
    )


def upgrade() -> None:
    _create_schema_tables()
    _create_record_storage()
    _create_guards()
    _indexes()
    _secure_tables()


def downgrade() -> None:
    for name in _VALUE_TABLES:
        op.drop_table(name, schema="catalog")
    op.execute("DROP FUNCTION catalog.guard_typed_record_value()")
    op.drop_constraint(
        "fk_catalog_catalog_record_current_revision",
        "catalog_record",
        schema="catalog",
        type_="foreignkey",
    )
    op.drop_table("catalog_record_revision", schema="catalog")
    op.drop_table("catalog_record", schema="catalog")
    op.drop_table("layout_item", schema="catalog")
    for name in ("subset", "layout", "attribute_definition", "schema_table"):
        op.drop_constraint(
            f"fk_catalog_{name}_current_revision",
            name,
            schema="catalog",
            type_="foreignkey",
        )
        op.drop_table(f"{name}_revision", schema="catalog")
        op.drop_table(name, schema="catalog")

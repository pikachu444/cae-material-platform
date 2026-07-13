"""Add the typed non-production reference Material Model IR.

Revision ID: 20260714_014_t22
Revises: 20260713_013_t07
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260714_014_t22"
down_revision: str | None = "20260713_013_t07"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_FAMILY = "urn:cmp:reference:isotropic-linear-elasticity:1.0.0"


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


def _identity_constraints() -> list[sa.Constraint]:
    return [
        sa.PrimaryKeyConstraint(
            "organization_id",
            "project_id",
            "id",
            name="pk_modeling_material_model",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "classification",
            "id",
            name="uq_modeling_material_model_scope_identity",
        ),
        sa.CheckConstraint(
            "classification ~ '^[a-z][a-z0-9_.-]{0,63}$'",
            name="ck_modeling_material_model_classification",
        ),
    ]


def _revision_constraints() -> list[sa.Constraint]:
    return [
        sa.PrimaryKeyConstraint(
            "organization_id", "project_id", "id", name="pk_modeling_material_model_revision"
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "aggregate_id",
            "id",
            name="uq_modeling_material_model_revision_scope_id",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "classification",
            "aggregate_id",
            "id",
            name="uq_modeling_material_model_revision_scoped_reference",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "aggregate_id",
            "revision_no",
            name="uq_modeling_material_model_revision_number",
        ),
        sa.CheckConstraint("revision_no > 0", name="ck_modeling_material_model_revision_number"),
        sa.CheckConstraint(
            "(revision_no = 1 AND based_on_revision_id IS NULL) "
            "OR (revision_no > 1 AND based_on_revision_id IS NOT NULL)",
            name="ck_modeling_material_model_revision_base",
        ),
        sa.CheckConstraint(
            "content_hash ~ '^[0-9a-f]{64}$'", name="ck_modeling_material_model_revision_hash"
        ),
        sa.CheckConstraint(
            "length(btrim(schema_id)) BETWEEN 1 AND 255",
            name="ck_modeling_material_model_revision_schema_id",
        ),
        sa.CheckConstraint(
            "length(btrim(schema_version)) BETWEEN 1 AND 64",
            name="ck_modeling_material_model_revision_schema_version",
        ),
        sa.CheckConstraint(
            "length(btrim(change_reason)) BETWEEN 1 AND 2000",
            name="ck_modeling_material_model_revision_reason",
        ),
        sa.CheckConstraint(
            "length(btrim(trace_id)) BETWEEN 1 AND 255",
            name="ck_modeling_material_model_revision_trace",
        ),
        sa.CheckConstraint(
            "classification ~ '^[a-z][a-z0-9_.-]{0,63}$'",
            name="ck_modeling_material_model_revision_classification",
        ),
    ]


def _create_tables() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    op.create_table(
        "material_model",
        *_identity_columns(uuid),
        sa.Column("material_state_id", uuid, nullable=False),
        *_identity_constraints(),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "classification",
            "id",
            "material_state_id",
            name="uq_modeling_material_model_identity_parent",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "classification", "material_state_id"],
            [
                "catalog.material_state.organization_id",
                "catalog.material_state.project_id",
                "catalog.material_state.classification",
                "catalog.material_state.id",
            ],
            name="fk_modeling_material_model_material_state",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        schema="modeling",
    )
    op.create_table(
        "material_model_revision",
        *_revision_columns(uuid),
        sa.Column("model_family_id", sa.String(length=255), nullable=False),
        sa.Column("model_schema_digest", sa.CHAR(length=64, collation="C"), nullable=False),
        sa.Column("material_id", uuid, nullable=False),
        sa.Column("material_revision_id", uuid, nullable=False),
        sa.Column("material_state_id", uuid, nullable=False),
        sa.Column("material_state_revision_id", uuid, nullable=False),
        sa.Column("property_set_id", uuid, nullable=False),
        sa.Column("property_set_revision_id", uuid, nullable=False),
        sa.Column("density_kg_per_m3", sa.Double(), nullable=False),
        sa.Column("youngs_modulus_pa", sa.Double(), nullable=False),
        sa.Column("poisson_ratio", sa.Double(), nullable=False),
        sa.Column("source_yield_stress_pa", sa.Double(), nullable=True),
        sa.Column("applicable_temperature_min_k", sa.Double(), nullable=True),
        sa.Column("applicable_temperature_max_k", sa.Double(), nullable=True),
        sa.Column("applicable_strain_rate_min_per_s", sa.Double(), nullable=True),
        sa.Column("applicable_strain_rate_max_per_s", sa.Double(), nullable=True),
        sa.Column("applicability_note", sa.Text(), nullable=True),
        sa.Column("reference_temperature_k", sa.Double(), nullable=False),
        sa.Column("non_production", sa.Boolean(), nullable=False),
        *_revision_constraints(),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "aggregate_id"],
            [
                "modeling.material_model.organization_id",
                "modeling.material_model.project_id",
                "modeling.material_model.id",
            ],
            name="fk_modeling_material_model_revision_identity",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.ForeignKeyConstraint(
            [
                "organization_id",
                "project_id",
                "classification",
                "aggregate_id",
                "material_state_id",
            ],
            [
                "modeling.material_model.organization_id",
                "modeling.material_model.project_id",
                "modeling.material_model.classification",
                "modeling.material_model.id",
                "modeling.material_model.material_state_id",
            ],
            name="fk_modeling_material_model_revision_identity_parent",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.ForeignKeyConstraint(
            [
                "organization_id",
                "project_id",
                "classification",
                "material_id",
                "material_revision_id",
            ],
            [
                "catalog.material_revision.organization_id",
                "catalog.material_revision.project_id",
                "catalog.material_revision.classification",
                "catalog.material_revision.aggregate_id",
                "catalog.material_revision.id",
            ],
            name="fk_modeling_material_model_revision_material_revision",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.ForeignKeyConstraint(
            [
                "organization_id",
                "project_id",
                "classification",
                "material_state_id",
                "material_state_revision_id",
                "material_id",
                "material_revision_id",
            ],
            [
                "catalog.material_state_revision.organization_id",
                "catalog.material_state_revision.project_id",
                "catalog.material_state_revision.classification",
                "catalog.material_state_revision.aggregate_id",
                "catalog.material_state_revision.id",
                "catalog.material_state_revision.material_id",
                "catalog.material_state_revision.material_revision_id",
            ],
            name="fk_modeling_material_model_revision_state_material_revision",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.ForeignKeyConstraint(
            [
                "organization_id",
                "project_id",
                "classification",
                "property_set_id",
                "material_state_id",
            ],
            [
                "catalog.property_set.organization_id",
                "catalog.property_set.project_id",
                "catalog.property_set.classification",
                "catalog.property_set.id",
                "catalog.property_set.material_state_id",
            ],
            name="fk_modeling_material_model_revision_property_set",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.ForeignKeyConstraint(
            [
                "organization_id",
                "project_id",
                "classification",
                "property_set_id",
                "property_set_revision_id",
                "material_state_id",
                "material_state_revision_id",
            ],
            [
                "catalog.property_set_revision.organization_id",
                "catalog.property_set_revision.project_id",
                "catalog.property_set_revision.classification",
                "catalog.property_set_revision.aggregate_id",
                "catalog.property_set_revision.id",
                "catalog.property_set_revision.material_state_id",
                "catalog.property_set_revision.material_state_revision_id",
            ],
            name="fk_modeling_material_model_revision_property_source",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "aggregate_id", "based_on_revision_id"],
            [
                "modeling.material_model_revision.organization_id",
                "modeling.material_model_revision.project_id",
                "modeling.material_model_revision.aggregate_id",
                "modeling.material_model_revision.id",
            ],
            name="fk_modeling_material_model_revision_base",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.CheckConstraint(
            f"model_family_id = '{_FAMILY}'", name="ck_modeling_material_model_reference_family"
        ),
        sa.CheckConstraint(
            "model_schema_digest ~ '^[0-9a-f]{64}$'",
            name="ck_modeling_material_model_schema_digest",
        ),
        sa.CheckConstraint(
            "density_kg_per_m3 > 0 AND density_kg_per_m3 < 'Infinity'::float8",
            name="ck_modeling_material_model_density",
        ),
        sa.CheckConstraint(
            "youngs_modulus_pa > 0 AND youngs_modulus_pa < 'Infinity'::float8",
            name="ck_modeling_material_model_youngs_modulus",
        ),
        sa.CheckConstraint(
            "poisson_ratio > -1 AND poisson_ratio < 0.5",
            name="ck_modeling_material_model_poisson_ratio",
        ),
        sa.CheckConstraint(
            "source_yield_stress_pa IS NULL OR "
            "(source_yield_stress_pa > 0 AND source_yield_stress_pa < 'Infinity'::float8)",
            name="ck_modeling_material_model_source_yield_stress",
        ),
        sa.CheckConstraint(
            "reference_temperature_k > 0 AND reference_temperature_k < 'Infinity'::float8",
            name="ck_modeling_material_model_reference_temperature",
        ),
        sa.CheckConstraint(
            "applicable_temperature_min_k IS NULL OR "
            "(applicable_temperature_min_k > 0 "
            "AND applicable_temperature_min_k < 'Infinity'::float8)",
            name="ck_modeling_material_model_temperature_min",
        ),
        sa.CheckConstraint(
            "applicable_temperature_max_k IS NULL OR "
            "(applicable_temperature_max_k > 0 "
            "AND applicable_temperature_max_k < 'Infinity'::float8)",
            name="ck_modeling_material_model_temperature_max",
        ),
        sa.CheckConstraint(
            "applicable_temperature_min_k IS NULL OR applicable_temperature_max_k IS NULL "
            "OR applicable_temperature_min_k <= applicable_temperature_max_k",
            name="ck_modeling_material_model_temperature_range",
        ),
        sa.CheckConstraint(
            "applicable_strain_rate_min_per_s IS NULL OR "
            "(applicable_strain_rate_min_per_s >= 0 "
            "AND applicable_strain_rate_min_per_s < 'Infinity'::float8)",
            name="ck_modeling_material_model_rate_min",
        ),
        sa.CheckConstraint(
            "applicable_strain_rate_max_per_s IS NULL OR "
            "(applicable_strain_rate_max_per_s >= 0 "
            "AND applicable_strain_rate_max_per_s < 'Infinity'::float8)",
            name="ck_modeling_material_model_rate_max",
        ),
        sa.CheckConstraint(
            "applicable_strain_rate_min_per_s IS NULL OR applicable_strain_rate_max_per_s IS NULL "
            "OR applicable_strain_rate_min_per_s <= applicable_strain_rate_max_per_s",
            name="ck_modeling_material_model_rate_range",
        ),
        sa.CheckConstraint(
            "applicability_note IS NULL OR length(btrim(applicability_note)) BETWEEN 1 AND 2000",
            name="ck_modeling_material_model_applicability_note",
        ),
        sa.CheckConstraint("non_production", name="ck_modeling_material_model_non_production"),
        schema="modeling",
    )
    op.create_foreign_key(
        "fk_modeling_material_model_current_revision",
        "material_model",
        "material_model_revision",
        ["organization_id", "project_id", "id", "current_revision_id"],
        ["organization_id", "project_id", "aggregate_id", "id"],
        source_schema="modeling",
        referent_schema="modeling",
        ondelete="RESTRICT",
        deferrable=True,
        initially="DEFERRED",
    )


def _secure_table(table: str) -> None:
    for operation, predicate in (
        ("select", "USING"),
        ("insert", "WITH CHECK"),
        ("update", "USING"),
    ):
        permission = "modeling.read" if operation == "select" else "modeling.write"
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
            f"CREATE POLICY modeling_{table}_{operation} ON modeling.{table} "
            f"FOR {operation.upper()} {expression}"
        )


def _add_catalog_source_constraints() -> None:
    """Make the model's four source revisions one coherent, tenant-scoped lineage path."""

    op.create_unique_constraint(
        "uq_catalog_material_state_revision_model_source",
        "material_state_revision",
        [
            "organization_id",
            "project_id",
            "classification",
            "aggregate_id",
            "id",
            "material_id",
            "material_revision_id",
        ],
        schema="catalog",
    )
    op.create_unique_constraint(
        "uq_catalog_property_set_revision_model_source",
        "property_set_revision",
        [
            "organization_id",
            "project_id",
            "classification",
            "aggregate_id",
            "id",
            "material_state_id",
            "material_state_revision_id",
        ],
        schema="catalog",
    )


def upgrade() -> None:
    op.execute("CREATE SCHEMA modeling")
    _add_catalog_source_constraints()
    _create_tables()
    op.create_index(
        "ix_modeling_material_model_tenant_state",
        "material_model",
        ["organization_id", "project_id", "classification", "material_state_id"],
        schema="modeling",
    )
    op.create_index(
        "ix_modeling_material_model_revision_tenant_created",
        "material_model_revision",
        ["organization_id", "project_id", "classification", "aggregate_id", "created_at"],
        schema="modeling",
    )
    for table in ("material_model", "material_model_revision"):
        op.execute(f"ALTER TABLE modeling.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE modeling.{table} FORCE ROW LEVEL SECURITY")
        _secure_table(table)
    op.execute(
        "CREATE TRIGGER modeling_material_model_head_only "
        "BEFORE UPDATE OR DELETE ON modeling.material_model FOR EACH ROW "
        "EXECUTE FUNCTION revisioning.guard_identity_head_update()"
    )
    op.execute(
        "CREATE TRIGGER modeling_material_model_revision_immutable "
        "BEFORE UPDATE OR DELETE ON modeling.material_model_revision FOR EACH ROW "
        "EXECUTE FUNCTION revisioning.reject_immutable_row_mutation()"
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_modeling_material_model_current_revision",
        "material_model",
        schema="modeling",
        type_="foreignkey",
    )
    op.drop_table("material_model_revision", schema="modeling")
    op.drop_table("material_model", schema="modeling")
    op.drop_constraint(
        "uq_catalog_property_set_revision_model_source",
        "property_set_revision",
        schema="catalog",
        type_="unique",
    )
    op.drop_constraint(
        "uq_catalog_material_state_revision_model_source",
        "material_state_revision",
        schema="catalog",
        type_="unique",
    )
    op.execute("DROP SCHEMA modeling")

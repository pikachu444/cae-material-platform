"""T-07 minimal typed Material Catalog.

Traceability: T-07, FR-CAT-001/002/003/004, NFR-INT-001, NFR-SEC-003/006,
ADR-001/002/003/006.  Core material properties are explicit typed columns; this migration
deliberately contains neither a generic key/value relation nor a JSON property payload.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260713_013_t07"
down_revision: str | None = "20260713_012_t05"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SOURCE_KINDS = "'manual', 'supplier_datasheet', 'test_derived', 'literature', 'calibration'"


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
            name=f"uq_catalog_{name}_scope_identity",
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
            "(revision_no = 1 AND based_on_revision_id IS NULL) "
            "OR (revision_no > 1 AND based_on_revision_id IS NOT NULL)",
            name=f"ck_catalog_{name}_revision_base",
        ),
        sa.CheckConstraint(
            "content_hash ~ '^[0-9a-f]{64}$'", name=f"ck_catalog_{name}_revision_hash"
        ),
        sa.CheckConstraint(
            "length(btrim(schema_id)) BETWEEN 1 AND 255",
            name=f"ck_catalog_{name}_revision_schema_id",
        ),
        sa.CheckConstraint(
            "length(btrim(schema_version)) BETWEEN 1 AND 64",
            name=f"ck_catalog_{name}_revision_schema_version",
        ),
        sa.CheckConstraint(
            "length(btrim(change_reason)) BETWEEN 1 AND 2000",
            name=f"ck_catalog_{name}_revision_reason",
        ),
        sa.CheckConstraint(
            "length(btrim(trace_id)) BETWEEN 1 AND 255",
            name=f"ck_catalog_{name}_revision_trace",
        ),
        sa.CheckConstraint(
            "classification ~ '^[a-z][a-z0-9_.-]{0,63}$'",
            name=f"ck_catalog_{name}_revision_classification",
        ),
    ]


def _create_tables() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    op.create_table(
        "material",
        *_identity_columns(uuid),
        *_identity_constraints("material"),
        schema="catalog",
    )
    op.create_table(
        "material_revision",
        *_revision_columns(uuid),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("material_code", sa.String(length=100), nullable=True),
        sa.Column("material_family", sa.String(length=100), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        *_revision_constraints("material"),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "aggregate_id"],
            [
                "catalog.material.organization_id",
                "catalog.material.project_id",
                "catalog.material.id",
            ],
            name="fk_catalog_material_revision_identity",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "aggregate_id", "based_on_revision_id"],
            [
                "catalog.material_revision.organization_id",
                "catalog.material_revision.project_id",
                "catalog.material_revision.aggregate_id",
                "catalog.material_revision.id",
            ],
            name="fk_catalog_material_revision_base",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.CheckConstraint(
            "length(btrim(name)) BETWEEN 1 AND 200", name="ck_catalog_material_name"
        ),
        sa.CheckConstraint(
            "material_code IS NULL OR length(btrim(material_code)) BETWEEN 1 AND 100",
            name="ck_catalog_material_code",
        ),
        sa.CheckConstraint(
            "material_family IS NULL OR length(btrim(material_family)) BETWEEN 1 AND 100",
            name="ck_catalog_material_family",
        ),
        sa.CheckConstraint(
            "description IS NULL OR length(btrim(description)) BETWEEN 1 AND 4000",
            name="ck_catalog_material_description",
        ),
        schema="catalog",
    )
    op.create_foreign_key(
        "fk_catalog_material_current_revision",
        "material",
        "material_revision",
        ["organization_id", "project_id", "id", "current_revision_id"],
        ["organization_id", "project_id", "aggregate_id", "id"],
        source_schema="catalog",
        referent_schema="catalog",
        ondelete="RESTRICT",
        deferrable=True,
        initially="DEFERRED",
    )

    op.create_table(
        "material_state",
        *_identity_columns(uuid),
        sa.Column("material_id", uuid, nullable=False),
        *_identity_constraints("material_state"),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "classification",
            "id",
            "material_id",
            name="uq_catalog_material_state_identity_parent",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "classification", "material_id"],
            [
                "catalog.material.organization_id",
                "catalog.material.project_id",
                "catalog.material.classification",
                "catalog.material.id",
            ],
            name="fk_catalog_material_state_material",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        schema="catalog",
    )
    op.create_table(
        "material_state_revision",
        *_revision_columns(uuid),
        sa.Column("material_id", uuid, nullable=False),
        sa.Column("material_revision_id", uuid, nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("manufacturing_route", sa.String(length=500), nullable=True),
        sa.Column("heat_treatment", sa.String(length=500), nullable=True),
        sa.Column("lot_or_batch", sa.String(length=255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        *_revision_constraints("material_state"),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "aggregate_id"],
            [
                "catalog.material_state.organization_id",
                "catalog.material_state.project_id",
                "catalog.material_state.id",
            ],
            name="fk_catalog_material_state_revision_identity",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "classification", "aggregate_id", "material_id"],
            [
                "catalog.material_state.organization_id",
                "catalog.material_state.project_id",
                "catalog.material_state.classification",
                "catalog.material_state.id",
                "catalog.material_state.material_id",
            ],
            name="fk_catalog_material_state_revision_identity_parent",
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
            name="fk_catalog_material_state_revision_material_revision",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "aggregate_id", "based_on_revision_id"],
            [
                "catalog.material_state_revision.organization_id",
                "catalog.material_state_revision.project_id",
                "catalog.material_state_revision.aggregate_id",
                "catalog.material_state_revision.id",
            ],
            name="fk_catalog_material_state_revision_base",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.CheckConstraint(
            "length(btrim(name)) BETWEEN 1 AND 200", name="ck_catalog_material_state_name"
        ),
        sa.CheckConstraint(
            "manufacturing_route IS NULL OR length(btrim(manufacturing_route)) BETWEEN 1 AND 500",
            name="ck_catalog_material_state_route",
        ),
        sa.CheckConstraint(
            "heat_treatment IS NULL OR length(btrim(heat_treatment)) BETWEEN 1 AND 500",
            name="ck_catalog_material_state_heat_treatment",
        ),
        sa.CheckConstraint(
            "lot_or_batch IS NULL OR length(btrim(lot_or_batch)) BETWEEN 1 AND 255",
            name="ck_catalog_material_state_lot_batch",
        ),
        sa.CheckConstraint(
            "description IS NULL OR length(btrim(description)) BETWEEN 1 AND 4000",
            name="ck_catalog_material_state_description",
        ),
        schema="catalog",
    )
    op.create_foreign_key(
        "fk_catalog_material_state_current_revision",
        "material_state",
        "material_state_revision",
        ["organization_id", "project_id", "id", "current_revision_id"],
        ["organization_id", "project_id", "aggregate_id", "id"],
        source_schema="catalog",
        referent_schema="catalog",
        ondelete="RESTRICT",
        deferrable=True,
        initially="DEFERRED",
    )

    op.create_table(
        "property_set",
        *_identity_columns(uuid),
        sa.Column("material_state_id", uuid, nullable=False),
        *_identity_constraints("property_set"),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "classification",
            "id",
            "material_state_id",
            name="uq_catalog_property_set_identity_parent",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "classification", "material_state_id"],
            [
                "catalog.material_state.organization_id",
                "catalog.material_state.project_id",
                "catalog.material_state.classification",
                "catalog.material_state.id",
            ],
            name="fk_catalog_property_set_material_state",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        schema="catalog",
    )
    op.create_table(
        "property_set_revision",
        *_revision_columns(uuid),
        sa.Column("material_state_id", uuid, nullable=False),
        sa.Column("material_state_revision_id", uuid, nullable=False),
        sa.Column("density_kg_per_m3", sa.Double(), nullable=False),
        sa.Column("density_source_kind", sa.String(length=32), nullable=False),
        sa.Column("density_source_reference", sa.Text(), nullable=True),
        sa.Column("youngs_modulus_pa", sa.Double(), nullable=False),
        sa.Column("youngs_modulus_source_kind", sa.String(length=32), nullable=False),
        sa.Column("youngs_modulus_source_reference", sa.Text(), nullable=True),
        sa.Column("poisson_ratio", sa.Double(), nullable=False),
        sa.Column("poisson_ratio_source_kind", sa.String(length=32), nullable=False),
        sa.Column("poisson_ratio_source_reference", sa.Text(), nullable=True),
        sa.Column("yield_stress_pa", sa.Double(), nullable=True),
        sa.Column("yield_stress_source_kind", sa.String(length=32), nullable=True),
        sa.Column("yield_stress_source_reference", sa.Text(), nullable=True),
        sa.Column("applicable_temperature_min_k", sa.Double(), nullable=True),
        sa.Column("applicable_temperature_max_k", sa.Double(), nullable=True),
        sa.Column("applicable_strain_rate_min_per_s", sa.Double(), nullable=True),
        sa.Column("applicable_strain_rate_max_per_s", sa.Double(), nullable=True),
        sa.Column("applicability_note", sa.Text(), nullable=True),
        *_revision_constraints("property_set"),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "aggregate_id"],
            [
                "catalog.property_set.organization_id",
                "catalog.property_set.project_id",
                "catalog.property_set.id",
            ],
            name="fk_catalog_property_set_revision_identity",
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
                "catalog.property_set.organization_id",
                "catalog.property_set.project_id",
                "catalog.property_set.classification",
                "catalog.property_set.id",
                "catalog.property_set.material_state_id",
            ],
            name="fk_catalog_property_set_revision_identity_parent",
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
            ],
            [
                "catalog.material_state_revision.organization_id",
                "catalog.material_state_revision.project_id",
                "catalog.material_state_revision.classification",
                "catalog.material_state_revision.aggregate_id",
                "catalog.material_state_revision.id",
            ],
            name="fk_catalog_property_set_revision_state_revision",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "aggregate_id", "based_on_revision_id"],
            [
                "catalog.property_set_revision.organization_id",
                "catalog.property_set_revision.project_id",
                "catalog.property_set_revision.aggregate_id",
                "catalog.property_set_revision.id",
            ],
            name="fk_catalog_property_set_revision_base",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.CheckConstraint(
            "density_kg_per_m3 > 0 AND density_kg_per_m3 < 'Infinity'::float8",
            name="ck_catalog_property_set_density",
        ),
        sa.CheckConstraint(
            "youngs_modulus_pa > 0 AND youngs_modulus_pa < 'Infinity'::float8",
            name="ck_catalog_property_set_youngs_modulus",
        ),
        sa.CheckConstraint(
            "poisson_ratio > -1 AND poisson_ratio < 0.5",
            name="ck_catalog_property_set_poisson_ratio",
        ),
        sa.CheckConstraint(
            "yield_stress_pa IS NULL OR (yield_stress_pa > 0 "
            "AND yield_stress_pa < 'Infinity'::float8)",
            name="ck_catalog_property_set_yield_stress",
        ),
        sa.CheckConstraint(
            f"density_source_kind IN ({_SOURCE_KINDS})",
            name="ck_catalog_property_set_density_source_kind",
        ),
        sa.CheckConstraint(
            f"youngs_modulus_source_kind IN ({_SOURCE_KINDS})",
            name="ck_catalog_property_set_youngs_source_kind",
        ),
        sa.CheckConstraint(
            f"poisson_ratio_source_kind IN ({_SOURCE_KINDS})",
            name="ck_catalog_property_set_poisson_source_kind",
        ),
        sa.CheckConstraint(
            f"yield_stress_source_kind IS NULL OR yield_stress_source_kind IN ({_SOURCE_KINDS})",
            name="ck_catalog_property_set_yield_source_kind",
        ),
        sa.CheckConstraint(
            "density_source_reference IS NULL OR length(btrim(density_source_reference)) "
            "BETWEEN 1 AND 2000",
            name="ck_catalog_property_set_density_source_reference",
        ),
        sa.CheckConstraint(
            "youngs_modulus_source_reference IS NULL OR "
            "length(btrim(youngs_modulus_source_reference)) BETWEEN 1 AND 2000",
            name="ck_catalog_property_set_youngs_source_reference",
        ),
        sa.CheckConstraint(
            "poisson_ratio_source_reference IS NULL OR "
            "length(btrim(poisson_ratio_source_reference)) BETWEEN 1 AND 2000",
            name="ck_catalog_property_set_poisson_source_reference",
        ),
        sa.CheckConstraint(
            "yield_stress_source_reference IS NULL OR "
            "length(btrim(yield_stress_source_reference)) BETWEEN 1 AND 2000",
            name="ck_catalog_property_set_yield_source_reference",
        ),
        sa.CheckConstraint(
            "density_source_kind = 'manual' OR density_source_reference IS NOT NULL",
            name="ck_catalog_property_set_density_source_reference_required",
        ),
        sa.CheckConstraint(
            "youngs_modulus_source_kind = 'manual' OR youngs_modulus_source_reference IS NOT NULL",
            name="ck_catalog_property_set_youngs_source_reference_required",
        ),
        sa.CheckConstraint(
            "poisson_ratio_source_kind = 'manual' OR poisson_ratio_source_reference IS NOT NULL",
            name="ck_catalog_property_set_poisson_source_reference_required",
        ),
        sa.CheckConstraint(
            "(yield_stress_pa IS NULL AND yield_stress_source_kind IS NULL "
            "AND yield_stress_source_reference IS NULL) OR "
            "(yield_stress_pa IS NOT NULL AND yield_stress_source_kind IS NOT NULL "
            "AND (yield_stress_source_kind = 'manual' "
            "OR yield_stress_source_reference IS NOT NULL))",
            name="ck_catalog_property_set_yield_source_pair",
        ),
        sa.CheckConstraint(
            "applicable_temperature_min_k IS NULL OR "
            "(applicable_temperature_min_k > 0 "
            "AND applicable_temperature_min_k < 'Infinity'::float8)",
            name="ck_catalog_property_set_temperature_min",
        ),
        sa.CheckConstraint(
            "applicable_temperature_max_k IS NULL OR "
            "(applicable_temperature_max_k > 0 "
            "AND applicable_temperature_max_k < 'Infinity'::float8)",
            name="ck_catalog_property_set_temperature_max",
        ),
        sa.CheckConstraint(
            "applicable_temperature_min_k IS NULL OR applicable_temperature_max_k IS NULL "
            "OR applicable_temperature_min_k <= applicable_temperature_max_k",
            name="ck_catalog_property_set_temperature_range",
        ),
        sa.CheckConstraint(
            "applicable_strain_rate_min_per_s IS NULL OR "
            "(applicable_strain_rate_min_per_s >= 0 "
            "AND applicable_strain_rate_min_per_s < 'Infinity'::float8)",
            name="ck_catalog_property_set_rate_min",
        ),
        sa.CheckConstraint(
            "applicable_strain_rate_max_per_s IS NULL OR "
            "(applicable_strain_rate_max_per_s >= 0 "
            "AND applicable_strain_rate_max_per_s < 'Infinity'::float8)",
            name="ck_catalog_property_set_rate_max",
        ),
        sa.CheckConstraint(
            "applicable_strain_rate_min_per_s IS NULL OR "
            "applicable_strain_rate_max_per_s IS NULL OR "
            "applicable_strain_rate_min_per_s <= applicable_strain_rate_max_per_s",
            name="ck_catalog_property_set_rate_range",
        ),
        sa.CheckConstraint(
            "applicability_note IS NULL OR length(btrim(applicability_note)) BETWEEN 1 AND 2000",
            name="ck_catalog_property_set_applicability_note",
        ),
        schema="catalog",
    )
    op.create_foreign_key(
        "fk_catalog_property_set_current_revision",
        "property_set",
        "property_set_revision",
        ["organization_id", "project_id", "id", "current_revision_id"],
        ["organization_id", "project_id", "aggregate_id", "id"],
        source_schema="catalog",
        referent_schema="catalog",
        ondelete="RESTRICT",
        deferrable=True,
        initially="DEFERRED",
    )


def _create_indexes() -> None:
    op.create_index(
        "ix_catalog_material_tenant_head",
        "material",
        ["organization_id", "project_id", "classification", "current_revision_id"],
        schema="catalog",
    )
    op.create_index(
        "ix_catalog_material_revision_tenant_created",
        "material_revision",
        ["organization_id", "project_id", "classification", "aggregate_id", "created_at"],
        schema="catalog",
    )
    op.create_index(
        "ix_catalog_material_revision_tenant_name",
        "material_revision",
        ["organization_id", "project_id", "classification", "name"],
        schema="catalog",
    )
    op.create_index(
        "ix_catalog_material_revision_tenant_code",
        "material_revision",
        ["organization_id", "project_id", "classification", "material_code"],
        schema="catalog",
    )
    op.create_index(
        "ix_catalog_material_state_tenant_material",
        "material_state",
        ["organization_id", "project_id", "classification", "material_id"],
        schema="catalog",
    )
    op.create_index(
        "ix_catalog_material_state_revision_tenant_created",
        "material_state_revision",
        ["organization_id", "project_id", "classification", "aggregate_id", "created_at"],
        schema="catalog",
    )
    op.create_index(
        "ix_catalog_property_set_tenant_state",
        "property_set",
        ["organization_id", "project_id", "classification", "material_state_id"],
        schema="catalog",
    )
    op.create_index(
        "ix_catalog_property_set_revision_tenant_created",
        "property_set_revision",
        ["organization_id", "project_id", "classification", "aggregate_id", "created_at"],
        schema="catalog",
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
                f"classification, '{permission}')) "
                "WITH CHECK (access_control.can_access_row(organization_id, project_id, "
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
    for identity, revision_table in (
        ("material", "material_revision"),
        ("material_state", "material_state_revision"),
        ("property_set", "property_set_revision"),
    ):
        op.execute(
            f"CREATE TRIGGER catalog_{identity}_head_only "
            f"BEFORE UPDATE OR DELETE ON catalog.{identity} "
            "FOR EACH ROW EXECUTE FUNCTION revisioning.guard_identity_head_update()"
        )
        op.execute(
            f"CREATE TRIGGER catalog_{revision_table}_immutable "
            f"BEFORE UPDATE OR DELETE ON catalog.{revision_table} "
            "FOR EACH ROW EXECUTE FUNCTION revisioning.reject_immutable_row_mutation()"
        )
        for table in (identity, revision_table):
            op.execute(f"ALTER TABLE catalog.{table} ENABLE ROW LEVEL SECURITY")
            op.execute(f"ALTER TABLE catalog.{table} FORCE ROW LEVEL SECURITY")
            _secure_table(table)


def upgrade() -> None:
    op.execute("CREATE SCHEMA catalog")
    _create_tables()
    _create_indexes()
    _secure_tables()


def downgrade() -> None:
    for identity in ("property_set", "material_state", "material"):
        op.drop_constraint(
            f"fk_catalog_{identity}_current_revision",
            identity,
            schema="catalog",
            type_="foreignkey",
        )
    op.drop_table("property_set_revision", schema="catalog")
    op.drop_table("property_set", schema="catalog")
    op.drop_table("material_state_revision", schema="catalog")
    op.drop_table("material_state", schema="catalog")
    op.drop_table("material_revision", schema="catalog")
    op.drop_table("material", schema="catalog")
    op.execute("DROP SCHEMA catalog")

"""Add immutable non-production OpenRadioss reference solver cards.

Revision ID: 20260714_015_t25
Revises: 20260714_014_t22
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260714_015_t25"
down_revision: str | None = "20260714_014_t22"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_MODEL_DIGEST = "a4e39b23b5d656abb50399b1ae76b799e01872f4f6ebe44a59bc8c901b622cd6"
_EXPORTER_DIGEST = "65a3f7ea55150a9c660b4303d12a168d8366bb1e41c6c86684a1e8a2fde20a20"
_STATUS_VALUES = (
    "'exact', 'transformed', 'approximated', 'ignored', 'unsupported', 'not_applicable'"
)


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
            name="pk_exporting_solver_card",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "classification",
            "id",
            name="uq_exporting_solver_card_scope_identity",
        ),
        sa.CheckConstraint(
            "classification ~ '^[a-z][a-z0-9_.-]{0,63}$'",
            name="ck_exporting_solver_card_classification",
        ),
        sa.CheckConstraint(
            "solver_material_id BETWEEN 1 AND 9999999999",
            name="ck_exporting_solver_card_material_id",
        ),
        sa.CheckConstraint(
            "target_solver = 'openradioss'",
            name="ck_exporting_solver_card_target_solver",
        ),
        sa.CheckConstraint(
            "target_version = '2025'",
            name="ck_exporting_solver_card_target_version",
        ),
        sa.CheckConstraint(
            "target_unit_system = 'kg_m_s'",
            name="ck_exporting_solver_card_target_unit_system",
        ),
    ]


def _revision_constraints() -> list[sa.Constraint]:
    status_constraints = {
        "density_mapping_status": "density_map_status",
        "youngs_modulus_mapping_status": "youngs_map_status",
        "poisson_ratio_mapping_status": "poisson_map_status",
        "source_yield_mapping_status": "yield_map_status",
        "temperature_applicability_mapping_status": "temperature_map_status",
        "strain_rate_applicability_mapping_status": "strain_rate_map_status",
        "unit_system_mapping_status": "unit_map_status",
    }
    constraints: list[sa.Constraint] = [
        sa.PrimaryKeyConstraint(
            "organization_id",
            "project_id",
            "id",
            name="pk_exporting_solver_card_revision",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "aggregate_id",
            "id",
            name="uq_exporting_solver_card_revision_scope_id",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "classification",
            "aggregate_id",
            "id",
            name="uq_exporting_solver_card_revision_scoped_reference",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "aggregate_id",
            "revision_no",
            name="uq_exporting_solver_card_revision_number",
        ),
        sa.CheckConstraint("revision_no > 0", name="ck_exporting_solver_card_revision_number"),
        sa.CheckConstraint(
            "(revision_no = 1 AND based_on_revision_id IS NULL) "
            "OR (revision_no > 1 AND based_on_revision_id IS NOT NULL)",
            name="ck_exporting_solver_card_revision_base",
        ),
        sa.CheckConstraint(
            "content_hash ~ '^[0-9a-f]{64}$'",
            name="ck_exporting_solver_card_revision_hash",
        ),
        sa.CheckConstraint(
            "length(btrim(schema_id)) BETWEEN 1 AND 255",
            name="ck_exporting_solver_card_revision_schema_id",
        ),
        sa.CheckConstraint(
            "length(btrim(schema_version)) BETWEEN 1 AND 64",
            name="ck_exporting_solver_card_revision_schema_version",
        ),
        sa.CheckConstraint(
            "length(btrim(change_reason)) BETWEEN 1 AND 2000",
            name="ck_exporting_solver_card_revision_reason",
        ),
        sa.CheckConstraint(
            "length(btrim(trace_id)) BETWEEN 1 AND 255",
            name="ck_exporting_solver_card_revision_trace",
        ),
        sa.CheckConstraint(
            "classification ~ '^[a-z][a-z0-9_.-]{0,63}$'",
            name="ck_exporting_solver_card_revision_classification",
        ),
        sa.CheckConstraint(
            f"model_schema_digest = '{_MODEL_DIGEST}'",
            name="ck_exporting_solver_card_model_digest",
        ),
        sa.CheckConstraint(
            "target_solver = 'openradioss'",
            name="ck_exporting_solver_card_revision_target_solver",
        ),
        sa.CheckConstraint(
            "target_version = '2025'",
            name="ck_exporting_solver_card_revision_target_version",
        ),
        sa.CheckConstraint(
            "target_unit_system = 'kg_m_s'",
            name="ck_exporting_solver_card_revision_target_unit_system",
        ),
        sa.CheckConstraint(
            "solver_material_id BETWEEN 1 AND 9999999999",
            name="ck_exporting_solver_card_revision_material_id",
        ),
        sa.CheckConstraint(
            "length(btrim(card_title)) BETWEEN 1 AND 100",
            name="ck_exporting_solver_card_title",
        ),
        sa.CheckConstraint(
            "density_kg_per_m3 > 0 AND density_kg_per_m3 < 'Infinity'::float8",
            name="ck_exporting_solver_card_density",
        ),
        sa.CheckConstraint(
            "youngs_modulus_pa > 0 AND youngs_modulus_pa < 'Infinity'::float8",
            name="ck_exporting_solver_card_youngs_modulus",
        ),
        sa.CheckConstraint(
            "poisson_ratio > -1 AND poisson_ratio < 0.5",
            name="ck_exporting_solver_card_poisson_ratio",
        ),
        sa.CheckConstraint(
            "source_yield_stress_pa IS NULL OR "
            "(source_yield_stress_pa > 0 AND source_yield_stress_pa < 'Infinity'::float8)",
            name="ck_exporting_solver_card_source_yield",
        ),
        sa.CheckConstraint(
            "applicable_temperature_min_k IS NULL OR "
            "(applicable_temperature_min_k > 0 "
            "AND applicable_temperature_min_k < 'Infinity'::float8)",
            name="ck_exporting_solver_card_temperature_min",
        ),
        sa.CheckConstraint(
            "applicable_temperature_max_k IS NULL OR "
            "(applicable_temperature_max_k > 0 "
            "AND applicable_temperature_max_k < 'Infinity'::float8)",
            name="ck_exporting_solver_card_temperature_max",
        ),
        sa.CheckConstraint(
            "applicable_temperature_min_k IS NULL OR applicable_temperature_max_k IS NULL "
            "OR applicable_temperature_min_k <= applicable_temperature_max_k",
            name="ck_exporting_solver_card_temperature_range",
        ),
        sa.CheckConstraint(
            "applicable_strain_rate_min_per_s IS NULL OR "
            "(applicable_strain_rate_min_per_s >= 0 "
            "AND applicable_strain_rate_min_per_s < 'Infinity'::float8)",
            name="ck_exporting_solver_card_rate_min",
        ),
        sa.CheckConstraint(
            "applicable_strain_rate_max_per_s IS NULL OR "
            "(applicable_strain_rate_max_per_s >= 0 "
            "AND applicable_strain_rate_max_per_s < 'Infinity'::float8)",
            name="ck_exporting_solver_card_rate_max",
        ),
        sa.CheckConstraint(
            "applicable_strain_rate_min_per_s IS NULL OR applicable_strain_rate_max_per_s IS NULL "
            "OR applicable_strain_rate_min_per_s <= applicable_strain_rate_max_per_s",
            name="ck_exporting_solver_card_rate_range",
        ),
        sa.CheckConstraint(
            "mapping_report_sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_exporting_solver_card_report_digest",
        ),
        sa.CheckConstraint(
            "card_sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_exporting_solver_card_card_digest",
        ),
        sa.CheckConstraint(
            "length(card_text) BETWEEN 1 AND 20000",
            name="ck_exporting_solver_card_text",
        ),
        sa.CheckConstraint(
            "exporter_id = 'cmp.reference.openradioss-elast'",
            name="ck_exporting_solver_card_exporter_id",
        ),
        sa.CheckConstraint(
            "exporter_version = '1.0.0'",
            name="ck_exporting_solver_card_exporter_version",
        ),
        sa.CheckConstraint(
            f"exporter_digest = '{_EXPORTER_DIGEST}'",
            name="ck_exporting_solver_card_exporter_digest",
        ),
        sa.CheckConstraint("non_production", name="ck_exporting_solver_card_non_production"),
    ]
    constraints.extend(
        sa.CheckConstraint(
            f"{column} IN ({_STATUS_VALUES})",
            name=f"ck_exporting_solver_card_{constraint_name}",
        )
        for column, constraint_name in status_constraints.items()
    )
    return constraints


def _create_tables() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    op.create_table(
        "solver_card",
        *_identity_columns(uuid),
        sa.Column("material_model_id", uuid, nullable=False),
        sa.Column("target_solver", sa.String(length=64), nullable=False),
        sa.Column("target_version", sa.String(length=64), nullable=False),
        sa.Column("target_unit_system", sa.String(length=64), nullable=False),
        sa.Column("solver_material_id", sa.BigInteger(), nullable=False),
        *_identity_constraints(),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "classification",
            "id",
            "material_model_id",
            "target_solver",
            "target_version",
            "target_unit_system",
            "solver_material_id",
            name="uq_exporting_solver_card_identity_target",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "classification", "material_model_id"],
            [
                "modeling.material_model.organization_id",
                "modeling.material_model.project_id",
                "modeling.material_model.classification",
                "modeling.material_model.id",
            ],
            name="fk_exporting_solver_card_model",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        schema="exporting",
    )
    op.create_table(
        "solver_card_revision",
        *_revision_columns(uuid),
        sa.Column("material_model_id", uuid, nullable=False),
        sa.Column("material_model_revision_id", uuid, nullable=False),
        sa.Column("model_schema_digest", sa.CHAR(length=64, collation="C"), nullable=False),
        sa.Column("target_solver", sa.String(length=64), nullable=False),
        sa.Column("target_version", sa.String(length=64), nullable=False),
        sa.Column("target_unit_system", sa.String(length=64), nullable=False),
        sa.Column("solver_material_id", sa.BigInteger(), nullable=False),
        sa.Column("card_title", sa.String(length=100), nullable=False),
        sa.Column("density_kg_per_m3", sa.Double(), nullable=False),
        sa.Column("youngs_modulus_pa", sa.Double(), nullable=False),
        sa.Column("poisson_ratio", sa.Double(), nullable=False),
        sa.Column("source_yield_stress_pa", sa.Double(), nullable=True),
        sa.Column("applicable_temperature_min_k", sa.Double(), nullable=True),
        sa.Column("applicable_temperature_max_k", sa.Double(), nullable=True),
        sa.Column("applicable_strain_rate_min_per_s", sa.Double(), nullable=True),
        sa.Column("applicable_strain_rate_max_per_s", sa.Double(), nullable=True),
        sa.Column("density_mapping_status", sa.String(length=32), nullable=False),
        sa.Column("youngs_modulus_mapping_status", sa.String(length=32), nullable=False),
        sa.Column("poisson_ratio_mapping_status", sa.String(length=32), nullable=False),
        sa.Column("source_yield_mapping_status", sa.String(length=32), nullable=False),
        sa.Column(
            "temperature_applicability_mapping_status",
            sa.String(length=32),
            nullable=False,
        ),
        sa.Column(
            "strain_rate_applicability_mapping_status",
            sa.String(length=32),
            nullable=False,
        ),
        sa.Column("unit_system_mapping_status", sa.String(length=32), nullable=False),
        sa.Column("mapping_report_sha256", sa.CHAR(length=64, collation="C"), nullable=False),
        sa.Column("card_text", sa.Text(), nullable=False),
        sa.Column("card_sha256", sa.CHAR(length=64, collation="C"), nullable=False),
        sa.Column("exporter_id", sa.String(length=255), nullable=False),
        sa.Column("exporter_version", sa.String(length=64), nullable=False),
        sa.Column("exporter_digest", sa.CHAR(length=64, collation="C"), nullable=False),
        sa.Column("non_production", sa.Boolean(), nullable=False),
        *_revision_constraints(),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "aggregate_id"],
            [
                "exporting.solver_card.organization_id",
                "exporting.solver_card.project_id",
                "exporting.solver_card.id",
            ],
            name="fk_exporting_solver_card_revision_identity",
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
                "material_model_id",
                "target_solver",
                "target_version",
                "target_unit_system",
                "solver_material_id",
            ],
            [
                "exporting.solver_card.organization_id",
                "exporting.solver_card.project_id",
                "exporting.solver_card.classification",
                "exporting.solver_card.id",
                "exporting.solver_card.material_model_id",
                "exporting.solver_card.target_solver",
                "exporting.solver_card.target_version",
                "exporting.solver_card.target_unit_system",
                "exporting.solver_card.solver_material_id",
            ],
            name="fk_exporting_solver_card_revision_identity_target",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.ForeignKeyConstraint(
            [
                "organization_id",
                "project_id",
                "classification",
                "material_model_id",
                "material_model_revision_id",
            ],
            [
                "modeling.material_model_revision.organization_id",
                "modeling.material_model_revision.project_id",
                "modeling.material_model_revision.classification",
                "modeling.material_model_revision.aggregate_id",
                "modeling.material_model_revision.id",
            ],
            name="fk_exporting_solver_card_revision_model_revision",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "aggregate_id", "based_on_revision_id"],
            [
                "exporting.solver_card_revision.organization_id",
                "exporting.solver_card_revision.project_id",
                "exporting.solver_card_revision.aggregate_id",
                "exporting.solver_card_revision.id",
            ],
            name="fk_exporting_solver_card_revision_base",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        schema="exporting",
    )
    op.create_foreign_key(
        "fk_exporting_solver_card_current_revision",
        "solver_card",
        "solver_card_revision",
        ["organization_id", "project_id", "id", "current_revision_id"],
        ["organization_id", "project_id", "aggregate_id", "id"],
        source_schema="exporting",
        referent_schema="exporting",
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
        permission = "export.read" if operation == "select" else "export.execute"
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
            f"CREATE POLICY exporting_{table}_{operation} ON exporting.{table} "
            f"FOR {operation.upper()} {expression}"
        )


def upgrade() -> None:
    op.execute("CREATE SCHEMA exporting")
    _create_tables()
    op.create_index(
        "ix_exporting_solver_card_tenant_model",
        "solver_card",
        ["organization_id", "project_id", "classification", "material_model_id"],
        schema="exporting",
    )
    op.create_index(
        "ix_exporting_solver_card_revision_tenant_created",
        "solver_card_revision",
        ["organization_id", "project_id", "classification", "aggregate_id", "created_at"],
        schema="exporting",
    )
    op.create_index(
        "ix_exporting_solver_card_revision_mapping_report",
        "solver_card_revision",
        ["organization_id", "project_id", "classification", "mapping_report_sha256"],
        schema="exporting",
    )
    for table in ("solver_card", "solver_card_revision"):
        op.execute(f"ALTER TABLE exporting.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE exporting.{table} FORCE ROW LEVEL SECURITY")
        _secure_table(table)
    op.execute(
        "CREATE TRIGGER exporting_solver_card_head_only "
        "BEFORE UPDATE OR DELETE ON exporting.solver_card FOR EACH ROW "
        "EXECUTE FUNCTION revisioning.guard_identity_head_update()"
    )
    op.execute(
        "CREATE TRIGGER exporting_solver_card_revision_immutable "
        "BEFORE UPDATE OR DELETE ON exporting.solver_card_revision FOR EACH ROW "
        "EXECUTE FUNCTION revisioning.reject_immutable_row_mutation()"
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_exporting_solver_card_current_revision",
        "solver_card",
        schema="exporting",
        type_="foreignkey",
    )
    op.drop_table("solver_card_revision", schema="exporting")
    op.drop_table("solver_card", schema="exporting")
    op.execute("DROP SCHEMA exporting")

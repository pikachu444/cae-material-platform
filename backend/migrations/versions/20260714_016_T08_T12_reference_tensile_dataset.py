"""Add the typed reference tensile Test and Dataset vertical slice.

Revision ID: 20260714_016_t08_t12
Revises: 20260714_015_t25
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260714_016_t08_t12"
down_revision: str | None = "20260714_015_t25"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_REFERENCE_METHOD = "reference_uniaxial_tensile"
_REFERENCE_IMPORTER = "urn:cmp:datasets:reference-uniaxial-tensile-csv:1.0.0"
_REFERENCE_IMPORTER_VERSION = "1.0.0"
_REFERENCE_PARQUET_SCHEMA = "urn:cmp:datasets:reference-tensile-normalized-parquet:1.0.0"
_ZERO = "'00000000-0000-0000-0000-000000000000'::uuid"


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


def _identity_constraints(prefix: str) -> list[sa.Constraint]:
    return [
        sa.PrimaryKeyConstraint("organization_id", "project_id", "id", name=f"pk_{prefix}"),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "classification",
            "id",
            name=f"uq_{prefix}_scope_identity",
        ),
        sa.CheckConstraint(
            "id <> "
            + _ZERO
            + " AND current_revision_id <> "
            + _ZERO
            + " AND created_by <> "
            + _ZERO,
            name=f"ck_{prefix}_nonzero_ids",
        ),
        sa.CheckConstraint(
            "classification ~ '^[a-z][a-z0-9_.-]{0,63}$'",
            name=f"ck_{prefix}_classification",
        ),
    ]


def _revision_constraints(prefix: str) -> list[sa.Constraint]:
    return [
        sa.PrimaryKeyConstraint(
            "organization_id",
            "project_id",
            "id",
            name=f"pk_{prefix}_revision",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "aggregate_id",
            "id",
            name=f"uq_{prefix}_revision_scope_id",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "classification",
            "aggregate_id",
            "id",
            name=f"uq_{prefix}_revision_scoped_ref",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "aggregate_id",
            "revision_no",
            name=f"uq_{prefix}_revision_number",
        ),
        sa.CheckConstraint(
            "id <> "
            + _ZERO
            + " AND aggregate_id <> "
            + _ZERO
            + " AND created_by <> "
            + _ZERO
            + " AND request_id <> "
            + _ZERO,
            name=f"ck_{prefix}_revision_nonzero_ids",
        ),
        sa.CheckConstraint("revision_no > 0", name=f"ck_{prefix}_revision_number"),
        sa.CheckConstraint(
            "(revision_no = 1 AND based_on_revision_id IS NULL) "
            "OR (revision_no > 1 AND based_on_revision_id IS NOT NULL)",
            name=f"ck_{prefix}_revision_base",
        ),
        sa.CheckConstraint(
            "content_hash ~ '^[0-9a-f]{64}$'", name=f"ck_{prefix}_revision_hash"
        ),
        sa.CheckConstraint(
            "length(btrim(schema_id)) BETWEEN 1 AND 255",
            name=f"ck_{prefix}_revision_schema_id",
        ),
        sa.CheckConstraint(
            "length(btrim(schema_version)) BETWEEN 1 AND 64",
            name=f"ck_{prefix}_revision_schema_version",
        ),
        sa.CheckConstraint(
            "length(btrim(change_reason)) BETWEEN 1 AND 2000",
            name=f"ck_{prefix}_revision_reason",
        ),
        sa.CheckConstraint(
            "length(btrim(trace_id)) BETWEEN 1 AND 255",
            name=f"ck_{prefix}_revision_trace",
        ),
        sa.CheckConstraint(
            "classification ~ '^[a-z][a-z0-9_.-]{0,63}$'",
            name=f"ck_{prefix}_revision_classification",
        ),
    ]


def _create_testing_tables() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    op.create_table(
        "specimen",
        *_identity_columns(uuid),
        sa.Column("material_state_id", uuid, nullable=False),
        sa.Column("specimen_code", sa.String(length=100), nullable=False),
        *_identity_constraints("testing_specimen"),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "classification",
            "id",
            "material_state_id",
            "specimen_code",
            name="uq_testing_specimen_identity_source",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "classification",
            "material_state_id",
            "specimen_code",
            name="uq_testing_specimen_state_code",
        ),
        sa.CheckConstraint(
            "length(btrim(specimen_code)) BETWEEN 1 AND 100 "
            "AND specimen_code = btrim(specimen_code)",
            name="ck_testing_specimen_code",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "classification", "material_state_id"],
            [
                "catalog.material_state.organization_id",
                "catalog.material_state.project_id",
                "catalog.material_state.classification",
                "catalog.material_state.id",
            ],
            name="fk_testing_specimen_material_state",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        schema="testing",
    )
    op.create_table(
        "specimen_revision",
        *_revision_columns(uuid),
        sa.Column("material_id", uuid, nullable=False),
        sa.Column("material_revision_id", uuid, nullable=False),
        sa.Column("material_state_id", uuid, nullable=False),
        sa.Column("material_state_revision_id", uuid, nullable=False),
        sa.Column("specimen_code", sa.String(length=100), nullable=False),
        sa.Column("orientation", sa.String(length=100), nullable=True),
        sa.Column("preparation_note", sa.Text(), nullable=True),
        *_revision_constraints("testing_specimen"),
        sa.CheckConstraint(
            "length(btrim(specimen_code)) BETWEEN 1 AND 100 "
            "AND specimen_code = btrim(specimen_code)",
            name="ck_testing_specimen_revision_code",
        ),
        sa.CheckConstraint(
            "orientation IS NULL OR (length(btrim(orientation)) BETWEEN 1 AND 100 "
            "AND orientation = btrim(orientation))",
            name="ck_testing_specimen_revision_orientation",
        ),
        sa.CheckConstraint(
            "preparation_note IS NULL OR (length(btrim(preparation_note)) BETWEEN 1 AND 2000 "
            "AND preparation_note = btrim(preparation_note))",
            name="ck_testing_specimen_revision_preparation",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "aggregate_id"],
            [
                "testing.specimen.organization_id",
                "testing.specimen.project_id",
                "testing.specimen.id",
            ],
            name="fk_testing_specimen_revision_identity",
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
                "specimen_code",
            ],
            [
                "testing.specimen.organization_id",
                "testing.specimen.project_id",
                "testing.specimen.classification",
                "testing.specimen.id",
                "testing.specimen.material_state_id",
                "testing.specimen.specimen_code",
            ],
            name="fk_testing_specimen_revision_identity_source",
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
            name="fk_testing_specimen_revision_material",
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
            name="fk_testing_specimen_revision_material_state",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "aggregate_id", "based_on_revision_id"],
            [
                "testing.specimen_revision.organization_id",
                "testing.specimen_revision.project_id",
                "testing.specimen_revision.aggregate_id",
                "testing.specimen_revision.id",
            ],
            name="fk_testing_specimen_revision_base",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        schema="testing",
    )
    op.create_foreign_key(
        "fk_testing_specimen_current_revision",
        "specimen",
        "specimen_revision",
        ["organization_id", "project_id", "id", "current_revision_id"],
        ["organization_id", "project_id", "aggregate_id", "id"],
        source_schema="testing",
        referent_schema="testing",
        ondelete="RESTRICT",
        deferrable=True,
        initially="DEFERRED",
    )

    op.create_table(
        "test_method",
        *_identity_columns(uuid),
        sa.Column("method_code", sa.String(length=100), nullable=False),
        *_identity_constraints("testing_test_method"),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "classification",
            "method_code",
            name="uq_testing_test_method_code",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "classification",
            "id",
            "method_code",
            name="uq_testing_test_method_identity_code",
        ),
        sa.CheckConstraint(
            f"method_code = '{_REFERENCE_METHOD}'", name="ck_testing_test_method_code"
        ),
        schema="testing",
    )
    op.create_table(
        "test_method_revision",
        *_revision_columns(uuid),
        sa.Column("method_code", sa.String(length=100), nullable=False),
        sa.Column("display_name", sa.String(length=160), nullable=False),
        sa.Column("reference_only", sa.Boolean(), nullable=False),
        *_revision_constraints("testing_test_method"),
        sa.CheckConstraint(
            f"method_code = '{_REFERENCE_METHOD}'", name="ck_testing_test_method_revision_code"
        ),
        sa.CheckConstraint(
            "display_name = 'Reference uniaxial tensile CSV'",
            name="ck_testing_test_method_revision_name",
        ),
        sa.CheckConstraint("reference_only", name="ck_testing_test_method_revision_reference"),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "classification",
            "id",
            name="uq_testing_test_method_revision_classified_id",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "aggregate_id"],
            [
                "testing.test_method.organization_id",
                "testing.test_method.project_id",
                "testing.test_method.id",
            ],
            name="fk_testing_test_method_revision_identity",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "classification", "aggregate_id", "method_code"],
            [
                "testing.test_method.organization_id",
                "testing.test_method.project_id",
                "testing.test_method.classification",
                "testing.test_method.id",
                "testing.test_method.method_code",
            ],
            name="fk_testing_test_method_revision_identity_code",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "aggregate_id", "based_on_revision_id"],
            [
                "testing.test_method_revision.organization_id",
                "testing.test_method_revision.project_id",
                "testing.test_method_revision.aggregate_id",
                "testing.test_method_revision.id",
            ],
            name="fk_testing_test_method_revision_base",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        schema="testing",
    )
    op.create_foreign_key(
        "fk_testing_test_method_current_revision",
        "test_method",
        "test_method_revision",
        ["organization_id", "project_id", "id", "current_revision_id"],
        ["organization_id", "project_id", "aggregate_id", "id"],
        source_schema="testing",
        referent_schema="testing",
        ondelete="RESTRICT",
        deferrable=True,
        initially="DEFERRED",
    )

    op.create_table(
        "test_run",
        *_identity_columns(uuid),
        sa.Column("specimen_id", uuid, nullable=False),
        sa.Column("test_method_id", uuid, nullable=False),
        sa.Column("run_label", sa.String(length=160), nullable=False),
        *_identity_constraints("testing_test_run"),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "classification",
            "id",
            "specimen_id",
            "test_method_id",
            "run_label",
            name="uq_testing_test_run_identity_source",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "classification",
            "specimen_id",
            "test_method_id",
            "run_label",
            name="uq_testing_test_run_source_label",
        ),
        sa.CheckConstraint(
            "length(btrim(run_label)) BETWEEN 1 AND 160 AND run_label = btrim(run_label)",
            name="ck_testing_test_run_label",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "classification", "specimen_id"],
            [
                "testing.specimen.organization_id",
                "testing.specimen.project_id",
                "testing.specimen.classification",
                "testing.specimen.id",
            ],
            name="fk_testing_test_run_specimen",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "classification", "test_method_id"],
            [
                "testing.test_method.organization_id",
                "testing.test_method.project_id",
                "testing.test_method.classification",
                "testing.test_method.id",
            ],
            name="fk_testing_test_run_method",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        schema="testing",
    )
    op.create_table(
        "test_run_revision",
        *_revision_columns(uuid),
        sa.Column("specimen_id", uuid, nullable=False),
        sa.Column("specimen_revision_id", uuid, nullable=False),
        sa.Column("test_method_id", uuid, nullable=False),
        sa.Column("test_method_revision_id", uuid, nullable=False),
        sa.Column("run_label", sa.String(length=160), nullable=False),
        sa.Column("performed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("test_temperature_k", sa.Double(), nullable=True),
        sa.Column("crosshead_speed_mm_per_min", sa.Double(), nullable=True),
        sa.Column("reference_only", sa.Boolean(), nullable=False),
        *_revision_constraints("testing_test_run"),
        sa.CheckConstraint(
            "length(btrim(run_label)) BETWEEN 1 AND 160 AND run_label = btrim(run_label)",
            name="ck_testing_test_run_revision_label",
        ),
        sa.CheckConstraint(
            "test_temperature_k IS NULL OR (test_temperature_k > 0 "
            "AND test_temperature_k < 'Infinity'::float8)",
            name="ck_testing_test_run_revision_temperature",
        ),
        sa.CheckConstraint(
            "crosshead_speed_mm_per_min IS NULL OR (crosshead_speed_mm_per_min > 0 "
            "AND crosshead_speed_mm_per_min < 'Infinity'::float8)",
            name="ck_testing_test_run_revision_speed",
        ),
        sa.CheckConstraint("reference_only", name="ck_testing_test_run_revision_reference"),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "classification",
            "id",
            name="uq_testing_test_run_revision_classified_id",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "aggregate_id"],
            [
                "testing.test_run.organization_id",
                "testing.test_run.project_id",
                "testing.test_run.id",
            ],
            name="fk_testing_test_run_revision_identity",
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
                "specimen_id",
                "test_method_id",
                "run_label",
            ],
            [
                "testing.test_run.organization_id",
                "testing.test_run.project_id",
                "testing.test_run.classification",
                "testing.test_run.id",
                "testing.test_run.specimen_id",
                "testing.test_run.test_method_id",
                "testing.test_run.run_label",
            ],
            name="fk_testing_test_run_revision_identity_source",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.ForeignKeyConstraint(
            [
                "organization_id",
                "project_id",
                "classification",
                "specimen_id",
                "specimen_revision_id",
            ],
            [
                "testing.specimen_revision.organization_id",
                "testing.specimen_revision.project_id",
                "testing.specimen_revision.classification",
                "testing.specimen_revision.aggregate_id",
                "testing.specimen_revision.id",
            ],
            name="fk_testing_test_run_revision_specimen",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.ForeignKeyConstraint(
            [
                "organization_id",
                "project_id",
                "classification",
                "test_method_id",
                "test_method_revision_id",
            ],
            [
                "testing.test_method_revision.organization_id",
                "testing.test_method_revision.project_id",
                "testing.test_method_revision.classification",
                "testing.test_method_revision.aggregate_id",
                "testing.test_method_revision.id",
            ],
            name="fk_testing_test_run_revision_method",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "aggregate_id", "based_on_revision_id"],
            [
                "testing.test_run_revision.organization_id",
                "testing.test_run_revision.project_id",
                "testing.test_run_revision.aggregate_id",
                "testing.test_run_revision.id",
            ],
            name="fk_testing_test_run_revision_base",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        schema="testing",
    )
    op.create_foreign_key(
        "fk_testing_test_run_current_revision",
        "test_run",
        "test_run_revision",
        ["organization_id", "project_id", "id", "current_revision_id"],
        ["organization_id", "project_id", "aggregate_id", "id"],
        source_schema="testing",
        referent_schema="testing",
        ondelete="RESTRICT",
        deferrable=True,
        initially="DEFERRED",
    )


def _create_dataset_tables() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    op.create_table(
        "dataset",
        *_identity_columns(uuid),
        sa.Column("test_run_id", uuid, nullable=False),
        sa.Column("raw_asset_id", uuid, nullable=False),
        sa.Column("raw_artifact_id", uuid, nullable=False),
        sa.Column("mapping_sha256", sa.CHAR(length=64, collation="C"), nullable=False),
        *_identity_constraints("datasets_dataset"),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "classification",
            "id",
            "test_run_id",
            "raw_asset_id",
            "raw_artifact_id",
            "mapping_sha256",
            name="uq_datasets_dataset_identity_source",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "classification",
            "test_run_id",
            "raw_asset_id",
            "raw_artifact_id",
            "mapping_sha256",
            name="uq_datasets_dataset_source",
        ),
        sa.CheckConstraint(
            "mapping_sha256 ~ '^[0-9a-f]{64}$'", name="ck_datasets_dataset_mapping_hash"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "classification", "test_run_id"],
            [
                "testing.test_run.organization_id",
                "testing.test_run.project_id",
                "testing.test_run.classification",
                "testing.test_run.id",
            ],
            name="fk_datasets_dataset_test_run",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "classification", "raw_asset_id"],
            [
                "artifact.raw_asset.organization_id",
                "artifact.raw_asset.project_id",
                "artifact.raw_asset.classification",
                "artifact.raw_asset.id",
            ],
            name="fk_datasets_dataset_raw_asset",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.ForeignKeyConstraint(
            [
                "organization_id",
                "project_id",
                "classification",
                "raw_artifact_id",
                "raw_asset_id",
            ],
            [
                "artifact.artifact.organization_id",
                "artifact.artifact.project_id",
                "artifact.artifact.classification",
                "artifact.artifact.id",
                "artifact.artifact.source_raw_asset_id",
            ],
            name="fk_datasets_dataset_raw_artifact",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        schema="datasets",
    )
    op.create_table(
        "dataset_revision",
        *_revision_columns(uuid),
        sa.Column("test_run_id", uuid, nullable=False),
        sa.Column("test_run_revision_id", uuid, nullable=False),
        sa.Column("raw_asset_id", uuid, nullable=False),
        sa.Column("raw_artifact_id", uuid, nullable=False),
        sa.Column("data_artifact_id", uuid, nullable=False),
        sa.Column("data_sha256", sa.CHAR(length=64, collation="C"), nullable=False),
        sa.Column("representation", sa.String(length=16), nullable=False),
        sa.Column("source_dataset_revision_id", uuid, nullable=True),
        sa.Column("point_count", sa.BigInteger(), nullable=False),
        sa.Column("strain_column", sa.String(length=255), nullable=False),
        sa.Column("stress_column", sa.String(length=255), nullable=False),
        sa.Column("strain_original_unit", sa.String(length=16), nullable=False),
        sa.Column("stress_original_unit", sa.String(length=16), nullable=False),
        sa.Column("mapping_sha256", sa.CHAR(length=64, collation="C"), nullable=False),
        sa.Column("importer_id", sa.String(length=255), nullable=False),
        sa.Column("importer_version", sa.String(length=64), nullable=False),
        *_revision_constraints("datasets_dataset"),
        sa.CheckConstraint(
            "representation IN ('raw', 'normalized')",
            name="ck_datasets_dataset_revision_representation",
        ),
        sa.CheckConstraint(
            "(representation = 'raw' AND revision_no = 1 "
            "AND based_on_revision_id IS NULL AND source_dataset_revision_id IS NULL "
            "AND data_artifact_id = raw_artifact_id) OR "
            "(representation = 'normalized' AND revision_no = 2 "
            "AND source_dataset_revision_id IS NOT NULL "
            "AND source_dataset_revision_id = based_on_revision_id "
            "AND data_artifact_id <> raw_artifact_id)",
            name="ck_datasets_dataset_revision_source_representation",
        ),
        sa.CheckConstraint(
            "point_count BETWEEN 2 AND 100000", name="ck_datasets_dataset_revision_points"
        ),
        sa.CheckConstraint(
            "data_sha256 ~ '^[0-9a-f]{64}$' AND mapping_sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_datasets_dataset_revision_hashes",
        ),
        sa.CheckConstraint(
            "length(btrim(strain_column)) BETWEEN 1 AND 255 "
            "AND strain_column = btrim(strain_column) "
            "AND length(btrim(stress_column)) BETWEEN 1 AND 255 "
            "AND stress_column = btrim(stress_column) "
            "AND strain_column <> stress_column",
            name="ck_datasets_dataset_revision_columns",
        ),
        sa.CheckConstraint(
            "strain_original_unit IN ('1', '%') "
            "AND stress_original_unit IN ('Pa', 'kPa', 'MPa', 'GPa')",
            name="ck_datasets_dataset_revision_units",
        ),
        sa.CheckConstraint(
            f"importer_id = '{_REFERENCE_IMPORTER}'", name="ck_datasets_dataset_revision_importer"
        ),
        sa.CheckConstraint(
            f"importer_version = '{_REFERENCE_IMPORTER_VERSION}'",
            name="ck_datasets_dataset_revision_importer_version",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "aggregate_id"],
            [
                "datasets.dataset.organization_id",
                "datasets.dataset.project_id",
                "datasets.dataset.id",
            ],
            name="fk_datasets_dataset_revision_identity",
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
                "test_run_id",
                "raw_asset_id",
                "raw_artifact_id",
                "mapping_sha256",
            ],
            [
                "datasets.dataset.organization_id",
                "datasets.dataset.project_id",
                "datasets.dataset.classification",
                "datasets.dataset.id",
                "datasets.dataset.test_run_id",
                "datasets.dataset.raw_asset_id",
                "datasets.dataset.raw_artifact_id",
                "datasets.dataset.mapping_sha256",
            ],
            name="fk_datasets_dataset_revision_identity_source",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.ForeignKeyConstraint(
            [
                "organization_id",
                "project_id",
                "classification",
                "test_run_id",
                "test_run_revision_id",
            ],
            [
                "testing.test_run_revision.organization_id",
                "testing.test_run_revision.project_id",
                "testing.test_run_revision.classification",
                "testing.test_run_revision.aggregate_id",
                "testing.test_run_revision.id",
            ],
            name="fk_datasets_dataset_revision_test_run",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "classification", "raw_asset_id"],
            [
                "artifact.raw_asset.organization_id",
                "artifact.raw_asset.project_id",
                "artifact.raw_asset.classification",
                "artifact.raw_asset.id",
            ],
            name="fk_datasets_dataset_revision_raw_asset",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.ForeignKeyConstraint(
            [
                "organization_id",
                "project_id",
                "classification",
                "raw_artifact_id",
                "raw_asset_id",
            ],
            [
                "artifact.artifact.organization_id",
                "artifact.artifact.project_id",
                "artifact.artifact.classification",
                "artifact.artifact.id",
                "artifact.artifact.source_raw_asset_id",
            ],
            name="fk_datasets_dataset_revision_raw_artifact",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.ForeignKeyConstraint(
            [
                "organization_id",
                "project_id",
                "classification",
                "data_artifact_id",
                "data_sha256",
            ],
            [
                "artifact.artifact.organization_id",
                "artifact.artifact.project_id",
                "artifact.artifact.classification",
                "artifact.artifact.id",
                "artifact.artifact.sha256",
            ],
            name="fk_datasets_dataset_revision_data_artifact",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.ForeignKeyConstraint(
            [
                "organization_id",
                "project_id",
                "aggregate_id",
                "source_dataset_revision_id",
            ],
            [
                "datasets.dataset_revision.organization_id",
                "datasets.dataset_revision.project_id",
                "datasets.dataset_revision.aggregate_id",
                "datasets.dataset_revision.id",
            ],
            name="fk_datasets_dataset_revision_source",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "aggregate_id", "based_on_revision_id"],
            [
                "datasets.dataset_revision.organization_id",
                "datasets.dataset_revision.project_id",
                "datasets.dataset_revision.aggregate_id",
                "datasets.dataset_revision.id",
            ],
            name="fk_datasets_dataset_revision_base",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        schema="datasets",
    )
    op.create_foreign_key(
        "fk_datasets_dataset_current_revision",
        "dataset",
        "dataset_revision",
        ["organization_id", "project_id", "id", "current_revision_id"],
        ["organization_id", "project_id", "aggregate_id", "id"],
        source_schema="datasets",
        referent_schema="datasets",
        ondelete="RESTRICT",
        deferrable=True,
        initially="DEFERRED",
    )


def _secure(schema: str, table: str, read_permission: str, write_permission: str) -> None:
    for operation, predicate, permission in (
        ("select", "USING", read_permission),
        ("insert", "WITH CHECK", write_permission),
    ):
        op.execute(
            f"CREATE POLICY {schema}_{table}_{operation} ON {schema}.{table} "
            f"FOR {operation.upper()} {predicate} (access_control.can_access_row("
            f"organization_id, project_id, classification, '{permission}'))"
        )
    op.execute(
        f"CREATE POLICY {schema}_{table}_update ON {schema}.{table} FOR UPDATE "
        "USING (access_control.can_access_row(organization_id, project_id, classification, "
        f"'{write_permission}')) WITH CHECK (access_control.can_access_row(organization_id, "
        f"project_id, classification, '{write_permission}'))"
    )


def _create_dataset_insert_guard() -> None:
    op.execute(
        f"""
        CREATE FUNCTION datasets.guard_reference_dataset_revision_insert()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
          source datasets.dataset_revision%ROWTYPE;
          selected_artifact_kind text;
          selected_artifact_schema text;
        BEGIN
          IF NEW.representation = 'normalized' THEN
            SELECT * INTO source
            FROM datasets.dataset_revision
            WHERE organization_id = NEW.organization_id
              AND project_id = NEW.project_id
              AND aggregate_id = NEW.aggregate_id
              AND id = NEW.source_dataset_revision_id;
            IF NOT FOUND
               OR source.representation <> 'raw'
               OR source.raw_asset_id <> NEW.raw_asset_id
               OR source.raw_artifact_id <> NEW.raw_artifact_id
               OR source.mapping_sha256 <> NEW.mapping_sha256 THEN
              RAISE EXCEPTION USING ERRCODE = '23514',
                MESSAGE = 'normalized Dataset must derive from its matching raw Dataset revision';
            END IF;
          END IF;
          SELECT a.artifact_kind, a.schema_ref
          INTO selected_artifact_kind, selected_artifact_schema
          FROM artifact.artifact AS a
          WHERE organization_id = NEW.organization_id
            AND project_id = NEW.project_id
            AND classification = NEW.classification
            AND id = NEW.data_artifact_id;
          IF NEW.representation = 'raw' THEN
            IF selected_artifact_kind IS DISTINCT FROM 'raw' THEN
              RAISE EXCEPTION USING ERRCODE = '23514',
                MESSAGE = 'raw Dataset must use a raw Artifact';
            END IF;
          ELSIF selected_artifact_kind IS DISTINCT FROM 'derived'
             OR selected_artifact_schema IS DISTINCT FROM '{_REFERENCE_PARQUET_SCHEMA}' THEN
            RAISE EXCEPTION USING ERRCODE = '23514',
              MESSAGE = 'normalized Dataset must use the reference Parquet derived Artifact';
          END IF;
          RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        "CREATE TRIGGER datasets_dataset_revision_reference_guard "
        "BEFORE INSERT ON datasets.dataset_revision FOR EACH ROW "
        "EXECUTE FUNCTION datasets.guard_reference_dataset_revision_insert()"
    )


def upgrade() -> None:
    op.execute("CREATE SCHEMA testing")
    op.execute("CREATE SCHEMA datasets")
    # These redundant-with-identity unique keys make source Raw Asset and immutable digest FKs
    # explicit; they prevent an arbitrary Artifact from being substituted into a Dataset revision.
    op.create_unique_constraint(
        "uq_artifact_manifest_source_raw",
        "artifact",
        ["organization_id", "project_id", "classification", "id", "source_raw_asset_id"],
        schema="artifact",
    )
    op.create_unique_constraint(
        "uq_artifact_manifest_id_digest",
        "artifact",
        ["organization_id", "project_id", "classification", "id", "sha256"],
        schema="artifact",
    )
    _create_testing_tables()
    op.create_foreign_key(
        "fk_artifact_upload_test_run_revision",
        "upload_session",
        "test_run_revision",
        ["organization_id", "project_id", "classification", "test_run_revision_id"],
        ["organization_id", "project_id", "classification", "id"],
        source_schema="artifact",
        referent_schema="testing",
        ondelete="RESTRICT",
        deferrable=True,
        initially="DEFERRED",
    )
    op.create_foreign_key(
        "fk_artifact_ingestion_test_run_revision",
        "ingestion_event",
        "test_run_revision",
        ["organization_id", "project_id", "classification", "test_run_revision_id"],
        ["organization_id", "project_id", "classification", "id"],
        source_schema="artifact",
        referent_schema="testing",
        ondelete="RESTRICT",
        deferrable=True,
        initially="DEFERRED",
    )
    _create_dataset_tables()
    _create_dataset_insert_guard()
    for name, table, columns in (
        (
            "ix_testing_specimen_state",
            "specimen",
            ["organization_id", "project_id", "classification", "material_state_id"],
        ),
        (
            "ix_testing_test_run_specimen",
            "test_run",
            ["organization_id", "project_id", "classification", "specimen_id"],
        ),
        (
            "ix_testing_test_run_revision_created",
            "test_run_revision",
            ["organization_id", "project_id", "classification", "aggregate_id", "created_at"],
        ),
    ):
        op.create_index(name, table, columns, schema="testing")
    for name, table, columns in (
        (
            "ix_datasets_dataset_test_run",
            "dataset",
            ["organization_id", "project_id", "classification", "test_run_id"],
        ),
        (
            "ix_datasets_dataset_revision_created",
            "dataset_revision",
            ["organization_id", "project_id", "classification", "aggregate_id", "created_at"],
        ),
        (
            "ix_datasets_dataset_revision_raw_asset",
            "dataset_revision",
            ["organization_id", "project_id", "classification", "raw_asset_id"],
        ),
    ):
        op.create_index(name, table, columns, schema="datasets")
    for table in (
        "specimen",
        "specimen_revision",
        "test_method",
        "test_method_revision",
        "test_run",
        "test_run_revision",
    ):
        op.execute(f"ALTER TABLE testing.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE testing.{table} FORCE ROW LEVEL SECURITY")
        _secure("testing", table, "testing.read", "testing.write")
    for table in ("dataset", "dataset_revision"):
        op.execute(f"ALTER TABLE datasets.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE datasets.{table} FORCE ROW LEVEL SECURITY")
        _secure("datasets", table, "dataset.read", "dataset.write")
    for table in ("specimen", "test_method", "test_run"):
        op.execute(
            f"CREATE TRIGGER testing_{table}_head_only BEFORE UPDATE OR DELETE ON testing.{table} "
            "FOR EACH ROW EXECUTE FUNCTION revisioning.guard_identity_head_update()"
        )
    for table in ("specimen_revision", "test_method_revision", "test_run_revision"):
        op.execute(
            f"CREATE TRIGGER testing_{table}_immutable BEFORE UPDATE OR DELETE ON testing.{table} "
            "FOR EACH ROW EXECUTE FUNCTION revisioning.reject_immutable_row_mutation()"
        )
    op.execute(
        "CREATE TRIGGER datasets_dataset_head_only BEFORE UPDATE OR DELETE ON datasets.dataset "
        "FOR EACH ROW EXECUTE FUNCTION revisioning.guard_identity_head_update()"
    )
    op.execute(
        "CREATE TRIGGER datasets_dataset_revision_immutable BEFORE UPDATE OR DELETE "
        "ON datasets.dataset_revision FOR EACH ROW "
        "EXECUTE FUNCTION revisioning.reject_immutable_row_mutation()"
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER datasets_dataset_revision_reference_guard "
        "ON datasets.dataset_revision"
    )
    op.execute("DROP FUNCTION datasets.guard_reference_dataset_revision_insert()")
    op.drop_constraint(
        "fk_datasets_dataset_current_revision", "dataset", schema="datasets", type_="foreignkey"
    )
    op.drop_table("dataset_revision", schema="datasets")
    op.drop_table("dataset", schema="datasets")
    op.execute("DROP SCHEMA datasets")
    op.drop_constraint(
        "fk_artifact_ingestion_test_run_revision",
        "ingestion_event",
        schema="artifact",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_artifact_upload_test_run_revision",
        "upload_session",
        schema="artifact",
        type_="foreignkey",
    )
    for table, constraint in (
        ("test_run", "fk_testing_test_run_current_revision"),
        ("test_method", "fk_testing_test_method_current_revision"),
        ("specimen", "fk_testing_specimen_current_revision"),
    ):
        op.drop_constraint(constraint, table, schema="testing", type_="foreignkey")
    op.drop_table("test_run_revision", schema="testing")
    op.drop_table("test_run", schema="testing")
    op.drop_table("test_method_revision", schema="testing")
    op.drop_table("test_method", schema="testing")
    op.drop_table("specimen_revision", schema="testing")
    op.drop_table("specimen", schema="testing")
    op.execute("DROP SCHEMA testing")
    op.drop_constraint("uq_artifact_manifest_id_digest", "artifact", schema="artifact")
    op.drop_constraint("uq_artifact_manifest_source_raw", "artifact", schema="artifact")

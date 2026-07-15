"""Add the typed reference shear-relaxation Dataset vertical slice.

Revision ID: 20260808_042_shear
Revises: 20260807_041_prony_card
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260808_042_shear"
down_revision: str | None = "20260807_041_prony_card"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _secure(table: str) -> None:
    for operation in ("select", "insert"):
        permission = "dataset.read" if operation == "select" else "dataset.write"
        predicate = "USING" if operation == "select" else "WITH CHECK"
        op.execute(
            f"CREATE POLICY datasets_{table}_{operation} ON datasets.{table} "
            f"FOR {operation.upper()} {predicate} "
            "(access_control.can_access_row(organization_id, project_id, "
            f"classification, '{permission}'))"
        )
    op.execute(
        f"CREATE POLICY datasets_{table}_update ON datasets.{table} FOR UPDATE "
        "USING (access_control.can_access_row(organization_id, project_id, "
        "classification, 'dataset.write')) WITH CHECK "
        "(access_control.can_access_row(organization_id, project_id, "
        "classification, 'dataset.write'))"
    )


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE testing.test_method DROP CONSTRAINT ck_testing_test_method_code;
        ALTER TABLE testing.test_method_revision
          DROP CONSTRAINT ck_testing_test_method_revision_code,
          DROP CONSTRAINT ck_testing_test_method_revision_name;
        ALTER TABLE testing.test_method ADD CONSTRAINT ck_testing_test_method_code CHECK
          (method_code IN ('reference_uniaxial_tensile','reference_shear_relaxation'));
        ALTER TABLE testing.test_method_revision ADD CONSTRAINT
          ck_testing_test_method_revision_declared CHECK
          ((method_code='reference_uniaxial_tensile' AND
            display_name='Reference uniaxial tensile CSV') OR
           (method_code='reference_shear_relaxation' AND
            display_name='Reference shear relaxation CSV'));

        CREATE TABLE datasets.shear_relaxation_dataset (
          id uuid NOT NULL,
          organization_id uuid NOT NULL,
          project_id uuid NOT NULL,
          classification varchar(64) NOT NULL,
          material_state_id uuid NOT NULL,
          test_run_id uuid NOT NULL,
          raw_asset_id uuid NOT NULL,
          raw_artifact_id uuid NOT NULL,
          mapping_sha256 char(64) COLLATE "C" NOT NULL,
          current_revision_id uuid NOT NULL,
          created_at timestamptz NOT NULL,
          created_by uuid NOT NULL,
          updated_at timestamptz NOT NULL,
          CONSTRAINT pk_datasets_shear_relaxation_dataset PRIMARY KEY
            (organization_id, project_id, id),
          CONSTRAINT uq_datasets_shear_relaxation_dataset_scope UNIQUE
            (organization_id, project_id, classification, id),
          CONSTRAINT uq_datasets_shear_relaxation_dataset_source UNIQUE
            (organization_id, project_id, classification, test_run_id,
             raw_asset_id, raw_artifact_id, mapping_sha256),
          CONSTRAINT ck_datasets_shear_relaxation_dataset_ids CHECK
            (id <> '00000000-0000-0000-0000-000000000000'::uuid AND
             current_revision_id <> '00000000-0000-0000-0000-000000000000'::uuid AND
             created_by <> '00000000-0000-0000-0000-000000000000'::uuid),
          CONSTRAINT ck_datasets_shear_relaxation_dataset_classification CHECK
            (classification ~ '^[a-z][a-z0-9_.-]{0,63}$'),
          CONSTRAINT ck_datasets_shear_relaxation_dataset_mapping CHECK
            (mapping_sha256 ~ '^[0-9a-f]{64}$'),
          CONSTRAINT fk_datasets_shear_relaxation_dataset_state FOREIGN KEY
            (organization_id, project_id, classification, material_state_id)
            REFERENCES catalog.material_state
            (organization_id, project_id, classification, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_datasets_shear_relaxation_dataset_run FOREIGN KEY
            (organization_id, project_id, classification, test_run_id)
            REFERENCES testing.test_run
            (organization_id, project_id, classification, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_datasets_shear_relaxation_dataset_raw_asset FOREIGN KEY
            (organization_id, project_id, classification, raw_asset_id)
            REFERENCES artifact.raw_asset
            (organization_id, project_id, classification, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_datasets_shear_relaxation_dataset_raw_artifact FOREIGN KEY
            (organization_id, project_id, classification, raw_artifact_id, raw_asset_id)
            REFERENCES artifact.artifact
            (organization_id, project_id, classification, id, source_raw_asset_id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED
        );

        CREATE TABLE datasets.shear_relaxation_dataset_revision (
          id uuid NOT NULL,
          aggregate_id uuid NOT NULL,
          organization_id uuid NOT NULL,
          project_id uuid NOT NULL,
          classification varchar(64) NOT NULL,
          revision_no bigint NOT NULL,
          based_on_revision_id uuid NULL,
          schema_id varchar(255) NOT NULL,
          schema_version varchar(64) NOT NULL,
          content_hash char(64) COLLATE "C" NOT NULL,
          created_at timestamptz NOT NULL,
          created_by uuid NOT NULL,
          change_reason text NOT NULL,
          request_id uuid NOT NULL,
          trace_id varchar(255) NOT NULL,
          material_state_id uuid NOT NULL,
          material_state_revision_id uuid NOT NULL,
          test_run_id uuid NOT NULL,
          test_run_revision_id uuid NOT NULL,
          raw_asset_id uuid NOT NULL,
          raw_artifact_id uuid NOT NULL,
          data_artifact_id uuid NOT NULL,
          data_sha256 char(64) COLLATE "C" NOT NULL,
          representation varchar(16) NOT NULL,
          source_dataset_revision_id uuid NULL,
          point_count bigint NOT NULL,
          time_column varchar(255) NOT NULL,
          shear_modulus_column varchar(255) NOT NULL,
          time_original_unit varchar(16) NOT NULL,
          shear_modulus_original_unit varchar(16) NOT NULL,
          mapping_sha256 char(64) COLLATE "C" NOT NULL,
          importer_id varchar(255) NOT NULL,
          importer_version varchar(64) NOT NULL,
          CONSTRAINT pk_datasets_shear_relaxation_dataset_revision PRIMARY KEY
            (organization_id, project_id, id),
          CONSTRAINT uq_datasets_shear_relaxation_dataset_revision_ref UNIQUE
            (organization_id, project_id, aggregate_id, id),
          CONSTRAINT uq_datasets_shear_relaxation_dataset_revision_scoped UNIQUE
            (organization_id, project_id, classification, aggregate_id, id),
          CONSTRAINT uq_datasets_shear_relaxation_dataset_revision_no UNIQUE
            (organization_id, project_id, aggregate_id, revision_no),
          CONSTRAINT ck_datasets_shear_relaxation_dataset_revision_ids CHECK
            (id <> '00000000-0000-0000-0000-000000000000'::uuid AND
             aggregate_id <> '00000000-0000-0000-0000-000000000000'::uuid AND
             created_by <> '00000000-0000-0000-0000-000000000000'::uuid AND
             request_id <> '00000000-0000-0000-0000-000000000000'::uuid),
          CONSTRAINT ck_datasets_shear_relaxation_dataset_revision_base CHECK
            ((revision_no=1 AND based_on_revision_id IS NULL) OR
             (revision_no>1 AND based_on_revision_id IS NOT NULL)),
          CONSTRAINT ck_datasets_shear_relaxation_dataset_revision_metadata CHECK
            (content_hash ~ '^[0-9a-f]{64}$' AND
             length(btrim(schema_id)) BETWEEN 1 AND 255 AND
             length(btrim(schema_version)) BETWEEN 1 AND 64 AND
             length(btrim(change_reason)) BETWEEN 1 AND 2000 AND
             length(btrim(trace_id)) BETWEEN 1 AND 255),
          CONSTRAINT ck_datasets_shear_relaxation_dataset_revision_representation CHECK
            ((representation='raw' AND revision_no=1 AND
              source_dataset_revision_id IS NULL AND data_artifact_id=raw_artifact_id) OR
             (representation='normalized' AND revision_no=2 AND
              source_dataset_revision_id=based_on_revision_id AND
              data_artifact_id<>raw_artifact_id)),
          CONSTRAINT ck_datasets_shear_relaxation_dataset_revision_points CHECK
            (point_count BETWEEN 3 AND 100000),
          CONSTRAINT ck_datasets_shear_relaxation_dataset_revision_columns CHECK
            (length(btrim(time_column)) BETWEEN 1 AND 255 AND
             length(btrim(shear_modulus_column)) BETWEEN 1 AND 255 AND
             time_column<>shear_modulus_column),
          CONSTRAINT ck_datasets_shear_relaxation_dataset_revision_units CHECK
            (time_original_unit IN ('s','ms','min','h') AND
             shear_modulus_original_unit IN ('Pa','kPa','MPa','GPa')),
          CONSTRAINT ck_datasets_shear_relaxation_dataset_revision_contract CHECK
            (data_sha256 ~ '^[0-9a-f]{64}$' AND
             mapping_sha256 ~ '^[0-9a-f]{64}$' AND
             importer_id='urn:cmp:datasets:reference-shear-relaxation-csv:1.0.0' AND
             importer_version='1.0.0'),
          CONSTRAINT fk_datasets_shear_relaxation_revision_identity FOREIGN KEY
            (organization_id, project_id, aggregate_id)
            REFERENCES datasets.shear_relaxation_dataset
            (organization_id, project_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_datasets_shear_relaxation_revision_state FOREIGN KEY
            (organization_id, project_id, classification,
             material_state_id, material_state_revision_id)
            REFERENCES catalog.material_state_revision
            (organization_id, project_id, classification, aggregate_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_datasets_shear_relaxation_revision_run FOREIGN KEY
            (organization_id, project_id, classification, test_run_id, test_run_revision_id)
            REFERENCES testing.test_run_revision
            (organization_id, project_id, classification, aggregate_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_datasets_shear_relaxation_revision_raw_asset FOREIGN KEY
            (organization_id, project_id, classification, raw_asset_id)
            REFERENCES artifact.raw_asset
            (organization_id, project_id, classification, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_datasets_shear_relaxation_revision_raw_artifact FOREIGN KEY
            (organization_id, project_id, classification, raw_artifact_id, raw_asset_id)
            REFERENCES artifact.artifact
            (organization_id, project_id, classification, id, source_raw_asset_id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_datasets_shear_relaxation_revision_data_artifact FOREIGN KEY
            (organization_id, project_id, classification, data_artifact_id, data_sha256)
            REFERENCES artifact.artifact
            (organization_id, project_id, classification, id, sha256)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_datasets_shear_relaxation_revision_base FOREIGN KEY
            (organization_id, project_id, aggregate_id, based_on_revision_id)
            REFERENCES datasets.shear_relaxation_dataset_revision
            (organization_id, project_id, aggregate_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_datasets_shear_relaxation_revision_source FOREIGN KEY
            (organization_id, project_id, aggregate_id, source_dataset_revision_id)
            REFERENCES datasets.shear_relaxation_dataset_revision
            (organization_id, project_id, aggregate_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED
        );
        ALTER TABLE datasets.shear_relaxation_dataset ADD CONSTRAINT
          fk_datasets_shear_relaxation_dataset_current FOREIGN KEY
          (organization_id, project_id, id, current_revision_id)
          REFERENCES datasets.shear_relaxation_dataset_revision
          (organization_id, project_id, aggregate_id, id)
          ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED;
        CREATE INDEX ix_datasets_shear_relaxation_dataset_state
          ON datasets.shear_relaxation_dataset
          (organization_id, project_id, material_state_id, updated_at DESC);
        CREATE INDEX ix_datasets_shear_relaxation_revision_run
          ON datasets.shear_relaxation_dataset_revision
          (organization_id, project_id, test_run_revision_id);
        """
    )
    for table in ("shear_relaxation_dataset", "shear_relaxation_dataset_revision"):
        op.execute(f"ALTER TABLE datasets.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE datasets.{table} FORCE ROW LEVEL SECURITY")
        _secure(table)
    op.execute(
        "CREATE TRIGGER datasets_shear_relaxation_dataset_revision_immutable "
        "BEFORE UPDATE OR DELETE ON datasets.shear_relaxation_dataset_revision "
        "FOR EACH ROW EXECUTE FUNCTION revisioning.reject_immutable_row_mutation()"
    )


def downgrade() -> None:
    op.execute(
        "DO $$ BEGIN IF EXISTS (SELECT 1 FROM datasets.shear_relaxation_dataset) "
        "THEN RAISE EXCEPTION 'cannot downgrade while immutable shear-relaxation "
        "Datasets exist'; END IF; END $$"
    )
    op.execute(
        "ALTER TABLE datasets.shear_relaxation_dataset DROP CONSTRAINT "
        "fk_datasets_shear_relaxation_dataset_current"
    )
    op.execute("DROP TABLE datasets.shear_relaxation_dataset_revision")
    op.execute("DROP TABLE datasets.shear_relaxation_dataset")
    op.execute(
        """
        ALTER TABLE testing.test_method DROP CONSTRAINT ck_testing_test_method_code;
        ALTER TABLE testing.test_method_revision
          DROP CONSTRAINT ck_testing_test_method_revision_declared;
        ALTER TABLE testing.test_method ADD CONSTRAINT ck_testing_test_method_code CHECK
          (method_code='reference_uniaxial_tensile');
        ALTER TABLE testing.test_method_revision ADD CONSTRAINT
          ck_testing_test_method_revision_code CHECK
          (method_code='reference_uniaxial_tensile');
        ALTER TABLE testing.test_method_revision ADD CONSTRAINT
          ck_testing_test_method_revision_name CHECK
          (display_name='Reference uniaxial tensile CSV');
        """
    )

"""Issue #209 DMA/FLD governed import diagnostics and idempotency.

Revision ID: 20260930_099_issue209_dma_fld
Revises: 20260929_098_issue210_dist
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260930_099_issue209_dma_fld"
down_revision: str | None = "20260929_098_issue210_dist"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _run_guard(*, include_idempotency: bool) -> None:
    immutable_idempotency = (
        " OR NEW.idempotency_key<>OLD.idempotency_key OR NEW.request_sha256<>OLD.request_sha256"
        if include_idempotency
        else ""
    )
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION datasets.guard_tabular_import_run_mutation()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF TG_OP='DELETE' OR OLD.status<>'executing' THEN
            RAISE EXCEPTION 'terminal tabular Import Runs are immutable';
          END IF;
          IF NEW.id<>OLD.id OR NEW.organization_id<>OLD.organization_id OR
             NEW.project_id<>OLD.project_id OR NEW.classification<>OLD.classification OR
             NEW.test_run_id<>OLD.test_run_id OR
             NEW.test_run_revision_id<>OLD.test_run_revision_id OR
             NEW.raw_asset_id<>OLD.raw_asset_id OR NEW.raw_artifact_id<>OLD.raw_artifact_id OR
             NEW.import_profile_id<>OLD.import_profile_id OR
             NEW.import_profile_revision_id<>OLD.import_profile_revision_id OR
             NEW.profile_sha256<>OLD.profile_sha256{immutable_idempotency} OR
             NEW.importer_id<>OLD.importer_id OR NEW.importer_version<>OLD.importer_version OR
             NEW.started_at<>OLD.started_at OR NEW.started_by<>OLD.started_by OR
             NEW.request_id<>OLD.request_id OR NEW.trace_id<>OLD.trace_id OR
             NEW.status='executing' THEN
            RAISE EXCEPTION 'tabular Import Run immutable inputs cannot change';
          END IF;
          RETURN NEW;
        END $$;
        """
    )


def upgrade() -> None:
    op.execute("DROP TRIGGER datasets_tabular_import_run_guard ON datasets.tabular_import_run")
    op.execute(
        """
        ALTER TABLE datasets.import_profile_revision
          DROP CONSTRAINT import_profile_revision_data_schema_check,
          ADD CONSTRAINT import_profile_revision_data_schema_check CHECK (data_schema IN
            ('monotonic_tension','monotonic_compression','planar_tension','biaxial_tension',
             'simple_shear','shear_relaxation','dma_frequency_temperature_sweep',
             'forming_limit_diagram'));
        ALTER TABLE datasets.import_profile_channel
          DROP CONSTRAINT import_profile_channel_ordinal_check,
          DROP CONSTRAINT import_profile_channel_source_quantity_check,
          ADD CONSTRAINT import_profile_channel_ordinal_check CHECK (ordinal BETWEEN 0 AND 4),
          ADD CONSTRAINT import_profile_channel_source_quantity_check CHECK
            (source_quantity IN ('engineering_strain','engineering_stress','shear_strain',
             'shear_stress','time','shear_modulus','displacement','force','temperature',
             'frequency','storage_modulus','loss_modulus','tan_delta','minor_strain',
             'major_strain'));
        ALTER TABLE datasets.governed_dataset_channel
          DROP CONSTRAINT governed_dataset_channel_ordinal_check,
          ADD CONSTRAINT governed_dataset_channel_ordinal_check
            CHECK (ordinal BETWEEN 0 AND 4);

        ALTER TABLE datasets.tabular_import_run
          ADD COLUMN idempotency_key varchar(255),
          ADD COLUMN request_sha256 char(64) COLLATE "C";
        UPDATE datasets.tabular_import_run
          SET idempotency_key='legacy-' || id::text,
              request_sha256=md5(id::text) || md5('legacy:' || id::text);
        ALTER TABLE datasets.tabular_import_run
          ALTER COLUMN idempotency_key SET NOT NULL,
          ALTER COLUMN request_sha256 SET NOT NULL,
          ADD CONSTRAINT ck_datasets_tabular_import_run_idempotency
            CHECK (idempotency_key ~ '^[!-~]{1,255}$'),
          ADD CONSTRAINT ck_datasets_tabular_import_run_request_sha256
            CHECK (request_sha256 ~ '^[0-9a-f]{64}$'),
          ADD CONSTRAINT uq_datasets_tabular_import_run_idempotency
            UNIQUE (organization_id, project_id, idempotency_key);

        ALTER TABLE datasets.tabular_import_row_error
          ADD COLUMN column_name varchar(255),
          ADD COLUMN channel_key varchar(64),
          ADD COLUMN recovery_hint varchar(500)
            NOT NULL DEFAULT 'Correct the governed source and retry with a new key.';
        ALTER TABLE datasets.tabular_import_row_error
          ALTER COLUMN recovery_hint DROP DEFAULT;

        ALTER TABLE governance.review_publication_projection
          DROP CONSTRAINT ck_review_publication_table_revision_pair,
          ALTER COLUMN record_id DROP NOT NULL,
          ALTER COLUMN record_revision_id DROP NOT NULL,
          ALTER COLUMN record_table_id DROP NOT NULL,
          ALTER COLUMN record_table_revision_id DROP NOT NULL,
          ADD COLUMN material_id uuid,
          ADD COLUMN material_revision_id uuid,
          ADD CONSTRAINT ck_review_publication_material_revision_pair CHECK
            ((material_id IS NULL) = (material_revision_id IS NULL)),
          ADD CONSTRAINT ck_review_publication_record_target CHECK
            ((record_id IS NULL AND record_revision_id IS NULL AND
              record_table_id IS NULL AND record_table_revision_id IS NULL) OR
             (record_id IS NOT NULL AND record_revision_id IS NOT NULL AND
              record_table_id IS NOT NULL AND record_table_revision_id IS NOT NULL)),
          ADD CONSTRAINT ck_review_publication_exact_target CHECK
            (record_id IS NOT NULL OR material_id IS NOT NULL);
        """
    )
    _run_guard(include_idempotency=True)
    op.execute(
        """
        CREATE TRIGGER datasets_tabular_import_run_guard BEFORE UPDATE OR DELETE
          ON datasets.tabular_import_run FOR EACH ROW
          EXECUTE FUNCTION datasets.guard_tabular_import_run_mutation()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER datasets_tabular_import_run_guard ON datasets.tabular_import_run")
    op.execute(
        """
        ALTER TABLE governance.review_publication_projection NO FORCE ROW LEVEL SECURITY;
        ALTER TABLE governance.review_publication_projection DISABLE ROW LEVEL SECURITY;
        DO $$
        BEGIN
          IF EXISTS (
            SELECT 1 FROM governance.review_publication_projection WHERE record_id IS NULL
          ) THEN
            RAISE EXCEPTION
              'cannot downgrade #209 while direct governed Material review projections exist';
          END IF;
        END $$;
        ALTER TABLE governance.review_publication_projection ENABLE ROW LEVEL SECURITY;
        ALTER TABLE governance.review_publication_projection FORCE ROW LEVEL SECURITY;
        ALTER TABLE governance.review_publication_projection
          DROP CONSTRAINT ck_review_publication_exact_target,
          DROP CONSTRAINT ck_review_publication_record_target,
          DROP CONSTRAINT ck_review_publication_material_revision_pair,
          DROP COLUMN material_revision_id,
          DROP COLUMN material_id,
          ALTER COLUMN record_table_revision_id SET NOT NULL,
          ALTER COLUMN record_table_id SET NOT NULL,
          ALTER COLUMN record_revision_id SET NOT NULL,
          ALTER COLUMN record_id SET NOT NULL,
          ADD CONSTRAINT ck_review_publication_table_revision_pair CHECK
            (record_table_id IS NOT NULL AND record_table_revision_id IS NOT NULL);

        ALTER TABLE datasets.tabular_import_row_error
          DROP COLUMN recovery_hint,
          DROP COLUMN channel_key,
          DROP COLUMN column_name;
        ALTER TABLE datasets.tabular_import_run
          DROP CONSTRAINT uq_datasets_tabular_import_run_idempotency,
          DROP CONSTRAINT ck_datasets_tabular_import_run_request_sha256,
          DROP CONSTRAINT ck_datasets_tabular_import_run_idempotency,
          DROP COLUMN request_sha256,
          DROP COLUMN idempotency_key;
        ALTER TABLE datasets.governed_dataset_channel
          DROP CONSTRAINT governed_dataset_channel_ordinal_check,
          ADD CONSTRAINT governed_dataset_channel_ordinal_check CHECK (ordinal IN (0,1));
        ALTER TABLE datasets.import_profile_channel
          DROP CONSTRAINT import_profile_channel_source_quantity_check,
          DROP CONSTRAINT import_profile_channel_ordinal_check,
          ADD CONSTRAINT import_profile_channel_ordinal_check CHECK (ordinal IN (0,1)),
          ADD CONSTRAINT import_profile_channel_source_quantity_check CHECK
            (source_quantity IN ('engineering_strain','engineering_stress','shear_strain',
             'shear_stress','time','shear_modulus','displacement','force'));
        ALTER TABLE datasets.import_profile_revision
          DROP CONSTRAINT import_profile_revision_data_schema_check,
          ADD CONSTRAINT import_profile_revision_data_schema_check CHECK (data_schema IN
            ('monotonic_tension','monotonic_compression','planar_tension','biaxial_tension',
             'simple_shear','shear_relaxation'));
        """
    )
    _run_guard(include_idempotency=False)
    op.execute(
        """
        CREATE TRIGGER datasets_tabular_import_run_guard BEFORE UPDATE OR DELETE
          ON datasets.tabular_import_run FOR EACH ROW
          EXECUTE FUNCTION datasets.guard_tabular_import_run_mutation()
        """
    )

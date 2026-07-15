"""Add explicit shear-relaxation processing and separate processed Dataset identities.

Revision ID: 20260809_043_shear_proc
Revises: 20260808_042_shear
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260809_043_shear_proc"
down_revision: str | None = "20260808_042_shear"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_INPUT_SCHEMA = "urn:cmp:datasets:reference-shear-relaxation-normalized-parquet:1.0.0"
_OUTPUT_SCHEMA = "urn:cmp:datasets:reference-shear-relaxation-processed-parquet:1.0.0"


def _secure(table: str, *, revision_table: bool = False) -> None:
    for operation, permission in (
        ("select", "processing.read"),
        ("insert", "processing.execute"),
    ):
        predicate = "USING" if operation == "select" else "WITH CHECK"
        op.execute(
            f"CREATE POLICY processing_{table}_{operation} ON processing.{table} "
            f"FOR {operation.upper()} {predicate} "
            "(access_control.can_access_row(organization_id, project_id, "
            f"classification, '{permission}'))"
        )
    if not revision_table:
        op.execute(
            f"CREATE POLICY processing_{table}_update ON processing.{table} FOR UPDATE "
            "USING (access_control.can_access_row(organization_id, project_id, "
            "classification, 'processing.execute')) WITH CHECK "
            "(access_control.can_access_row(organization_id, project_id, "
            "classification, 'processing.execute'))"
        )


def upgrade() -> None:
    op.execute(
        f"""
        CREATE TABLE processing.shear_relaxation_recipe (
          id uuid NOT NULL,
          organization_id uuid NOT NULL,
          project_id uuid NOT NULL,
          classification varchar(64) NOT NULL,
          recipe_label varchar(160) NOT NULL,
          recipe_kind varchar(100) NOT NULL,
          current_revision_id uuid NOT NULL,
          created_at timestamptz NOT NULL,
          created_by uuid NOT NULL,
          updated_at timestamptz NOT NULL,
          CONSTRAINT pk_processing_shear_relaxation_recipe PRIMARY KEY
            (organization_id, project_id, id),
          CONSTRAINT uq_processing_shear_relaxation_recipe_scope UNIQUE
            (organization_id, project_id, classification, id),
          CONSTRAINT uq_processing_shear_relaxation_recipe_label UNIQUE
            (organization_id, project_id, classification, recipe_label),
          CONSTRAINT ck_processing_shear_relaxation_recipe_ids CHECK
            (id <> '00000000-0000-0000-0000-000000000000'::uuid AND
             current_revision_id <> '00000000-0000-0000-0000-000000000000'::uuid AND
             created_by <> '00000000-0000-0000-0000-000000000000'::uuid),
          CONSTRAINT ck_processing_shear_relaxation_recipe_classification CHECK
            (classification ~ '^[a-z][a-z0-9_.-]{0,63}$'),
          CONSTRAINT ck_processing_shear_relaxation_recipe_label CHECK
            (length(btrim(recipe_label)) BETWEEN 1 AND 160 AND recipe_label=btrim(recipe_label)),
          CONSTRAINT ck_processing_shear_relaxation_recipe_kind CHECK
            (recipe_kind='reference_shear_relaxation_inclusive_time_crop')
        );

        CREATE TABLE processing.shear_relaxation_recipe_revision (
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
          recipe_kind varchar(100) NOT NULL,
          step_ordinal smallint NOT NULL,
          minimum_time_s double precision NOT NULL,
          maximum_time_s double precision NOT NULL,
          input_schema_ref varchar(500) NOT NULL,
          output_schema_ref varchar(500) NOT NULL,
          CONSTRAINT pk_processing_shear_relaxation_recipe_revision PRIMARY KEY
            (organization_id, project_id, id),
          CONSTRAINT uq_processing_shear_relaxation_recipe_revision_ref UNIQUE
            (organization_id, project_id, aggregate_id, id),
          CONSTRAINT uq_processing_shear_relaxation_recipe_revision_scoped UNIQUE
            (organization_id, project_id, classification, aggregate_id, id),
          CONSTRAINT uq_processing_shear_relaxation_recipe_revision_no UNIQUE
            (organization_id, project_id, aggregate_id, revision_no),
          CONSTRAINT ck_processing_shear_relaxation_recipe_revision_ids CHECK
            (id <> '00000000-0000-0000-0000-000000000000'::uuid AND
             aggregate_id <> '00000000-0000-0000-0000-000000000000'::uuid AND
             created_by <> '00000000-0000-0000-0000-000000000000'::uuid AND
             request_id <> '00000000-0000-0000-0000-000000000000'::uuid),
          CONSTRAINT ck_processing_shear_relaxation_recipe_revision_base CHECK
            ((revision_no=1 AND based_on_revision_id IS NULL) OR
             (revision_no>1 AND based_on_revision_id IS NOT NULL)),
          CONSTRAINT ck_processing_shear_relaxation_recipe_revision_metadata CHECK
            (content_hash ~ '^[0-9a-f]{64}$' AND
             length(btrim(schema_id)) BETWEEN 1 AND 255 AND
             length(btrim(schema_version)) BETWEEN 1 AND 64 AND
             length(btrim(change_reason)) BETWEEN 1 AND 2000 AND
             length(btrim(trace_id)) BETWEEN 1 AND 255),
          CONSTRAINT ck_processing_shear_relaxation_recipe_revision_contract CHECK
            (recipe_kind='reference_shear_relaxation_inclusive_time_crop' AND
             step_ordinal=0 AND minimum_time_s>=0 AND minimum_time_s<'Infinity'::float8 AND
             maximum_time_s>minimum_time_s AND maximum_time_s<'Infinity'::float8 AND
             input_schema_ref='{_INPUT_SCHEMA}' AND
             output_schema_ref='{_OUTPUT_SCHEMA}'),
          CONSTRAINT fk_processing_shear_relaxation_recipe_revision_identity FOREIGN KEY
            (organization_id, project_id, aggregate_id)
            REFERENCES processing.shear_relaxation_recipe
            (organization_id, project_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_processing_shear_relaxation_recipe_revision_base FOREIGN KEY
            (organization_id, project_id, aggregate_id, based_on_revision_id)
            REFERENCES processing.shear_relaxation_recipe_revision
            (organization_id, project_id, aggregate_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED
        );
        ALTER TABLE processing.shear_relaxation_recipe ADD CONSTRAINT
          fk_processing_shear_relaxation_recipe_current FOREIGN KEY
          (organization_id, project_id, id, current_revision_id)
          REFERENCES processing.shear_relaxation_recipe_revision
          (organization_id, project_id, aggregate_id, id)
          ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED;

        CREATE TABLE processing.shear_relaxation_run (
          id uuid NOT NULL,
          organization_id uuid NOT NULL,
          project_id uuid NOT NULL,
          classification varchar(64) NOT NULL,
          recipe_id uuid NOT NULL,
          recipe_revision_id uuid NOT NULL,
          input_dataset_id uuid NOT NULL,
          input_dataset_revision_id uuid NOT NULL,
          status varchar(16) NOT NULL,
          input_point_count bigint NOT NULL,
          output_point_count bigint NULL,
          removed_point_count bigint NULL,
          result_artifact_id uuid NULL,
          result_sha256 char(64) COLLATE "C" NULL,
          output_dataset_id uuid NULL,
          output_dataset_revision_id uuid NULL,
          failure_code varchar(100) NULL,
          change_reason text NOT NULL,
          started_at timestamptz NOT NULL,
          ended_at timestamptz NULL,
          created_by uuid NOT NULL,
          request_id uuid NOT NULL,
          trace_id varchar(255) NOT NULL,
          CONSTRAINT pk_processing_shear_relaxation_run PRIMARY KEY
            (organization_id, project_id, id),
          CONSTRAINT uq_processing_shear_relaxation_run_scope UNIQUE
            (organization_id, project_id, classification, id),
          CONSTRAINT ck_processing_shear_relaxation_run_ids CHECK
            (id <> '00000000-0000-0000-0000-000000000000'::uuid AND
             recipe_id <> '00000000-0000-0000-0000-000000000000'::uuid AND
             recipe_revision_id <> '00000000-0000-0000-0000-000000000000'::uuid AND
             input_dataset_id <> '00000000-0000-0000-0000-000000000000'::uuid AND
             input_dataset_revision_id <> '00000000-0000-0000-0000-000000000000'::uuid AND
             created_by <> '00000000-0000-0000-0000-000000000000'::uuid AND
             request_id <> '00000000-0000-0000-0000-000000000000'::uuid),
          CONSTRAINT ck_processing_shear_relaxation_run_classification CHECK
            (classification ~ '^[a-z][a-z0-9_.-]{0,63}$'),
          CONSTRAINT ck_processing_shear_relaxation_run_points CHECK
            (input_point_count BETWEEN 3 AND 100000),
          CONSTRAINT ck_processing_shear_relaxation_run_metadata CHECK
            (length(btrim(change_reason)) BETWEEN 1 AND 2000 AND
             length(btrim(trace_id)) BETWEEN 1 AND 255 AND
             ended_at IS NULL OR ended_at>=started_at),
          CONSTRAINT ck_processing_shear_relaxation_run_hash CHECK
            ((result_artifact_id IS NULL)=(result_sha256 IS NULL) AND
             (result_sha256 IS NULL OR result_sha256 ~ '^[0-9a-f]{64}$')),
          CONSTRAINT ck_processing_shear_relaxation_run_terminal CHECK
            ((status='executing' AND ended_at IS NULL AND result_artifact_id IS NULL AND
              output_point_count IS NULL AND removed_point_count IS NULL AND
              output_dataset_id IS NULL AND output_dataset_revision_id IS NULL AND
              failure_code IS NULL) OR
             (status='succeeded' AND ended_at IS NOT NULL AND result_artifact_id IS NOT NULL AND
              output_point_count BETWEEN 3 AND 100000 AND removed_point_count>=0 AND
              output_point_count+removed_point_count=input_point_count AND
              output_dataset_id IS NOT NULL AND output_dataset_revision_id IS NOT NULL AND
              failure_code IS NULL) OR
             (status='failed' AND ended_at IS NOT NULL AND
              output_point_count IS NULL AND removed_point_count IS NULL AND
              output_dataset_id IS NULL AND output_dataset_revision_id IS NULL AND
              length(btrim(failure_code)) BETWEEN 1 AND 100)),
          CONSTRAINT fk_processing_shear_relaxation_run_recipe FOREIGN KEY
            (organization_id, project_id, classification, recipe_id, recipe_revision_id)
            REFERENCES processing.shear_relaxation_recipe_revision
            (organization_id, project_id, classification, aggregate_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_processing_shear_relaxation_run_input FOREIGN KEY
            (organization_id, project_id, classification,
             input_dataset_id, input_dataset_revision_id)
            REFERENCES datasets.shear_relaxation_dataset_revision
            (organization_id, project_id, classification, aggregate_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_processing_shear_relaxation_run_artifact FOREIGN KEY
            (organization_id, project_id, classification, result_artifact_id, result_sha256)
            REFERENCES artifact.artifact
            (organization_id, project_id, classification, id, sha256)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED
        );
        CREATE INDEX ix_processing_shear_relaxation_run_input
          ON processing.shear_relaxation_run
          (organization_id, project_id, input_dataset_revision_id, started_at DESC);
        """
    )

    for table, immutable in (
        ("shear_relaxation_recipe", False),
        ("shear_relaxation_recipe_revision", True),
        ("shear_relaxation_run", False),
    ):
        op.execute(f"ALTER TABLE processing.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE processing.{table} FORCE ROW LEVEL SECURITY")
        _secure(table, revision_table=immutable)
    op.execute(
        "CREATE TRIGGER processing_shear_relaxation_recipe_revision_immutable "
        "BEFORE UPDATE OR DELETE ON processing.shear_relaxation_recipe_revision "
        "FOR EACH ROW EXECUTE FUNCTION revisioning.reject_immutable_row_mutation()"
    )

    op.execute(
        """
        ALTER TABLE datasets.shear_relaxation_dataset
          ADD COLUMN processing_run_id uuid NULL;
        ALTER TABLE datasets.shear_relaxation_dataset_revision
          ADD COLUMN processing_run_id uuid NULL;
        ALTER TABLE datasets.shear_relaxation_dataset
          DROP CONSTRAINT uq_datasets_shear_relaxation_dataset_source;
        CREATE UNIQUE INDEX ux_datasets_shear_relaxation_import_source
          ON datasets.shear_relaxation_dataset
          (organization_id, project_id, classification, test_run_id,
           raw_asset_id, raw_artifact_id, mapping_sha256)
          WHERE processing_run_id IS NULL;
        CREATE UNIQUE INDEX ux_datasets_shear_relaxation_processing_run
          ON datasets.shear_relaxation_dataset
          (organization_id, project_id, classification, processing_run_id)
          WHERE processing_run_id IS NOT NULL;
        ALTER TABLE datasets.shear_relaxation_dataset_revision
          DROP CONSTRAINT ck_datasets_shear_relaxation_dataset_revision_representation;
        ALTER TABLE datasets.shear_relaxation_dataset_revision
          DROP CONSTRAINT fk_datasets_shear_relaxation_revision_source;
        ALTER TABLE datasets.shear_relaxation_dataset_revision ADD CONSTRAINT
          ck_datasets_shear_relaxation_dataset_revision_representation CHECK
          ((representation='raw' AND revision_no=1 AND based_on_revision_id IS NULL AND
            source_dataset_revision_id IS NULL AND processing_run_id IS NULL AND
            data_artifact_id=raw_artifact_id) OR
           (representation='normalized' AND revision_no=2 AND
            source_dataset_revision_id=based_on_revision_id AND processing_run_id IS NULL AND
            data_artifact_id<>raw_artifact_id) OR
           (representation='processed' AND revision_no=1 AND based_on_revision_id IS NULL AND
            source_dataset_revision_id IS NOT NULL AND processing_run_id IS NOT NULL AND
            data_artifact_id<>raw_artifact_id));
        ALTER TABLE datasets.shear_relaxation_dataset ADD CONSTRAINT
          ck_datasets_shear_relaxation_dataset_processing_identity CHECK
          (processing_run_id IS NULL OR
           processing_run_id <> '00000000-0000-0000-0000-000000000000'::uuid);
        ALTER TABLE datasets.shear_relaxation_dataset_revision ADD CONSTRAINT
          fk_datasets_shear_relaxation_revision_source FOREIGN KEY
          (organization_id, project_id, source_dataset_revision_id)
          REFERENCES datasets.shear_relaxation_dataset_revision
          (organization_id, project_id, id)
          ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED;
        ALTER TABLE datasets.shear_relaxation_dataset ADD CONSTRAINT
          fk_datasets_shear_relaxation_dataset_processing_run FOREIGN KEY
          (organization_id, project_id, classification, processing_run_id)
          REFERENCES processing.shear_relaxation_run
          (organization_id, project_id, classification, id)
          ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED;
        ALTER TABLE datasets.shear_relaxation_dataset_revision ADD CONSTRAINT
          fk_datasets_shear_relaxation_revision_processing_run FOREIGN KEY
          (organization_id, project_id, classification, processing_run_id)
          REFERENCES processing.shear_relaxation_run
          (organization_id, project_id, classification, id)
          ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED;
        ALTER TABLE processing.shear_relaxation_run ADD CONSTRAINT
          fk_processing_shear_relaxation_run_output FOREIGN KEY
          (organization_id, project_id, classification,
           output_dataset_id, output_dataset_revision_id)
          REFERENCES datasets.shear_relaxation_dataset_revision
          (organization_id, project_id, classification, aggregate_id, id)
          ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED;
        """
    )

    op.execute(
        """
        CREATE FUNCTION processing.guard_shear_relaxation_run_insert()
        RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE input_representation text;
        BEGIN
          SELECT representation INTO input_representation
          FROM datasets.shear_relaxation_dataset_revision
          WHERE organization_id=NEW.organization_id AND project_id=NEW.project_id
            AND classification=NEW.classification AND aggregate_id=NEW.input_dataset_id
            AND id=NEW.input_dataset_revision_id;
          IF input_representation IS DISTINCT FROM 'normalized' THEN
            RAISE EXCEPTION 'shear-relaxation processing requires normalized input';
          END IF;
          RETURN NEW;
        END $$;
        CREATE TRIGGER processing_shear_relaxation_run_insert_guard
          BEFORE INSERT ON processing.shear_relaxation_run
          FOR EACH ROW EXECUTE FUNCTION processing.guard_shear_relaxation_run_insert();

        CREATE FUNCTION processing.guard_shear_relaxation_run_transition()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF TG_OP='DELETE' THEN
            RAISE EXCEPTION 'shear-relaxation Processing Runs are immutable evidence';
          END IF;
          IF OLD.status<>'executing' OR NEW.status NOT IN ('succeeded','failed') OR
             (NEW.id,NEW.organization_id,NEW.project_id,NEW.classification,
              NEW.recipe_id,NEW.recipe_revision_id,NEW.input_dataset_id,
              NEW.input_dataset_revision_id,NEW.input_point_count,NEW.change_reason,
              NEW.started_at,NEW.created_by,NEW.request_id,NEW.trace_id)
             IS DISTINCT FROM
             (OLD.id,OLD.organization_id,OLD.project_id,OLD.classification,
              OLD.recipe_id,OLD.recipe_revision_id,OLD.input_dataset_id,
              OLD.input_dataset_revision_id,OLD.input_point_count,OLD.change_reason,
              OLD.started_at,OLD.created_by,OLD.request_id,OLD.trace_id) THEN
            RAISE EXCEPTION 'invalid shear-relaxation Processing Run transition';
          END IF;
          RETURN NEW;
        END $$;
        CREATE TRIGGER processing_shear_relaxation_run_transition_guard
          BEFORE UPDATE OR DELETE ON processing.shear_relaxation_run
          FOR EACH ROW EXECUTE FUNCTION processing.guard_shear_relaxation_run_transition();
        """
    )


def downgrade() -> None:
    op.execute(
        "DO $$ BEGIN IF EXISTS (SELECT 1 FROM processing.shear_relaxation_run) THEN "
        "RAISE EXCEPTION 'cannot downgrade while immutable shear-relaxation "
        "Processing Runs exist'; "
        "END IF; END $$"
    )
    op.execute(
        """
        ALTER TABLE processing.shear_relaxation_run
          DROP CONSTRAINT fk_processing_shear_relaxation_run_output;
        ALTER TABLE datasets.shear_relaxation_dataset_revision
          DROP CONSTRAINT fk_datasets_shear_relaxation_revision_processing_run,
          DROP CONSTRAINT fk_datasets_shear_relaxation_revision_source,
          DROP CONSTRAINT ck_datasets_shear_relaxation_dataset_revision_representation;
        ALTER TABLE datasets.shear_relaxation_dataset
          DROP CONSTRAINT fk_datasets_shear_relaxation_dataset_processing_run,
          DROP CONSTRAINT ck_datasets_shear_relaxation_dataset_processing_identity;
        DROP INDEX datasets.ux_datasets_shear_relaxation_processing_run;
        DROP INDEX datasets.ux_datasets_shear_relaxation_import_source;
        ALTER TABLE datasets.shear_relaxation_dataset_revision ADD CONSTRAINT
          ck_datasets_shear_relaxation_dataset_revision_representation CHECK
          ((representation='raw' AND revision_no=1 AND
            source_dataset_revision_id IS NULL AND data_artifact_id=raw_artifact_id) OR
           (representation='normalized' AND revision_no=2 AND
            source_dataset_revision_id=based_on_revision_id AND
            data_artifact_id<>raw_artifact_id));
        ALTER TABLE datasets.shear_relaxation_dataset_revision ADD CONSTRAINT
          fk_datasets_shear_relaxation_revision_source FOREIGN KEY
          (organization_id, project_id, aggregate_id, source_dataset_revision_id)
          REFERENCES datasets.shear_relaxation_dataset_revision
          (organization_id, project_id, aggregate_id, id)
          ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED;
        ALTER TABLE datasets.shear_relaxation_dataset ADD CONSTRAINT
          uq_datasets_shear_relaxation_dataset_source UNIQUE
          (organization_id, project_id, classification, test_run_id,
           raw_asset_id, raw_artifact_id, mapping_sha256);
        ALTER TABLE datasets.shear_relaxation_dataset_revision DROP COLUMN processing_run_id;
        ALTER TABLE datasets.shear_relaxation_dataset DROP COLUMN processing_run_id;
        DROP TABLE processing.shear_relaxation_run;
        ALTER TABLE processing.shear_relaxation_recipe
          DROP CONSTRAINT fk_processing_shear_relaxation_recipe_current;
        DROP TABLE processing.shear_relaxation_recipe_revision;
        DROP TABLE processing.shear_relaxation_recipe;
        DROP FUNCTION processing.guard_shear_relaxation_run_transition();
        DROP FUNCTION processing.guard_shear_relaxation_run_insert();
        """
    )

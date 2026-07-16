"""Add viscoelastic replicate Selection, TTS Plan/Run, and derived Datasets.

Revision ID: 20260818_052_t42
Revises: 20260817_051_governed_import
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260818_052_t42"
down_revision: str | None = "20260817_051_governed_import"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_DATASET_IDENTITIES = ("viscoelastic_selection", "viscoelastic_derived_dataset")
_DATASET_IMMUTABLE = (
    "viscoelastic_selection_revision",
    "viscoelastic_selection_member",
    "viscoelastic_derived_dataset_revision",
)
_PROCESSING_IDENTITIES = ("viscoelastic_master_plan",)
_PROCESSING_IMMUTABLE = (
    "viscoelastic_master_plan_revision",
    "viscoelastic_master_plan_manual_shift",
    "viscoelastic_master_shift_factor",
)


def _rls(schema: str, table: str, read: str, write: str) -> None:
    op.execute(f"ALTER TABLE {schema}.{table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {schema}.{table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY {schema}_{table}_select ON {schema}.{table} FOR SELECT USING "
        "(access_control.can_access_row(organization_id, project_id, classification, "
        f"'{read}'))"
    )
    op.execute(
        f"CREATE POLICY {schema}_{table}_insert ON {schema}.{table} FOR INSERT WITH CHECK "
        "(access_control.can_access_row(organization_id, project_id, classification, "
        f"'{write}'))"
    )
    op.execute(
        f"CREATE POLICY {schema}_{table}_update ON {schema}.{table} FOR UPDATE USING "
        "(access_control.can_access_row(organization_id, project_id, classification, "
        f"'{write}')) WITH CHECK (access_control.can_access_row(organization_id, "
        f"project_id, classification, '{write}'))"
    )


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE datasets.viscoelastic_selection (
          id uuid NOT NULL, organization_id uuid NOT NULL, project_id uuid NOT NULL,
          classification varchar(64) NOT NULL, selection_label varchar(160) NOT NULL,
          material_state_id uuid NOT NULL, current_revision_id uuid NOT NULL,
          created_at timestamptz NOT NULL, created_by uuid NOT NULL,
          updated_at timestamptz NOT NULL,
          CONSTRAINT pk_datasets_viscoelastic_selection PRIMARY KEY
            (organization_id, project_id, id),
          CONSTRAINT uq_datasets_viscoelastic_selection_scope UNIQUE
            (organization_id, project_id, classification, id),
          CONSTRAINT uq_datasets_viscoelastic_selection_label UNIQUE
            (organization_id, project_id, classification, material_state_id, selection_label),
          CONSTRAINT ck_datasets_viscoelastic_selection_label CHECK
            (length(btrim(selection_label)) BETWEEN 1 AND 160),
          CONSTRAINT fk_datasets_viscoelastic_selection_state FOREIGN KEY
            (organization_id, project_id, classification, material_state_id)
            REFERENCES catalog.material_state
            (organization_id, project_id, classification, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED
        );
        CREATE TABLE datasets.viscoelastic_selection_revision (
          id uuid NOT NULL, aggregate_id uuid NOT NULL,
          organization_id uuid NOT NULL, project_id uuid NOT NULL,
          classification varchar(64) NOT NULL, revision_no bigint NOT NULL,
          based_on_revision_id uuid, schema_id varchar(255) NOT NULL,
          schema_version varchar(64) NOT NULL,
          content_hash char(64) COLLATE "C" NOT NULL,
          created_at timestamptz NOT NULL, created_by uuid NOT NULL,
          change_reason text NOT NULL, request_id uuid NOT NULL,
          trace_id varchar(255) NOT NULL, selection_label varchar(160) NOT NULL,
          material_state_id uuid NOT NULL, material_state_revision_id uuid NOT NULL,
          member_count smallint NOT NULL, temperature_count smallint NOT NULL,
          CONSTRAINT pk_datasets_viscoelastic_selection_revision PRIMARY KEY
            (organization_id, project_id, id),
          CONSTRAINT uq_datasets_viscoelastic_selection_revision_scope UNIQUE
            (organization_id, project_id, classification, aggregate_id, id),
          CONSTRAINT uq_datasets_viscoelastic_selection_revision_no UNIQUE
            (organization_id, project_id, aggregate_id, revision_no),
          CONSTRAINT ck_datasets_viscoelastic_selection_revision_metadata CHECK
            (revision_no > 0 AND content_hash ~ '^[0-9a-f]{64}$' AND
             length(btrim(selection_label)) BETWEEN 1 AND 160 AND
             length(btrim(change_reason)) BETWEEN 1 AND 2000 AND
             length(btrim(trace_id)) BETWEEN 1 AND 255),
          CONSTRAINT ck_datasets_viscoelastic_selection_revision_shape CHECK
            (member_count BETWEEN 2 AND 50 AND
             temperature_count BETWEEN 2 AND member_count),
          CONSTRAINT fk_datasets_viscoelastic_selection_revision_identity FOREIGN KEY
            (organization_id, project_id, classification, aggregate_id)
            REFERENCES datasets.viscoelastic_selection
            (organization_id, project_id, classification, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_datasets_viscoelastic_selection_revision_base FOREIGN KEY
            (organization_id, project_id, based_on_revision_id)
            REFERENCES datasets.viscoelastic_selection_revision
            (organization_id, project_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_datasets_viscoelastic_selection_revision_state FOREIGN KEY
            (organization_id, project_id, classification,
             material_state_id, material_state_revision_id)
            REFERENCES catalog.material_state_revision
            (organization_id, project_id, classification, aggregate_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED
        );
        ALTER TABLE datasets.viscoelastic_selection
          ADD CONSTRAINT fk_datasets_viscoelastic_selection_current FOREIGN KEY
          (organization_id, project_id, classification, id, current_revision_id)
          REFERENCES datasets.viscoelastic_selection_revision
          (organization_id, project_id, classification, aggregate_id, id)
          ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED;
        CREATE INDEX ix_datasets_viscoelastic_selection_state
          ON datasets.viscoelastic_selection
          (organization_id, project_id, classification, material_state_id, updated_at DESC);

        CREATE TABLE datasets.viscoelastic_selection_member (
          organization_id uuid NOT NULL, project_id uuid NOT NULL,
          classification varchar(64) NOT NULL, selection_id uuid NOT NULL,
          selection_revision_id uuid NOT NULL, ordinal smallint NOT NULL,
          dataset_id uuid NOT NULL, dataset_revision_id uuid NOT NULL,
          test_run_id uuid NOT NULL, test_run_revision_id uuid NOT NULL,
          temperature_k double precision NOT NULL, outlier_status varchar(32) NOT NULL,
          CONSTRAINT pk_datasets_viscoelastic_selection_member PRIMARY KEY
            (organization_id, project_id, selection_revision_id, ordinal),
          CONSTRAINT uq_datasets_viscoelastic_selection_member_dataset UNIQUE
            (organization_id, project_id, selection_revision_id, dataset_revision_id),
          CONSTRAINT uq_datasets_viscoelastic_selection_member_run UNIQUE
            (organization_id, project_id, selection_revision_id, test_run_revision_id),
          CONSTRAINT ck_datasets_viscoelastic_selection_member CHECK
            (ordinal BETWEEN 0 AND 49 AND temperature_k > 0 AND
             outlier_status='not_assessed'),
          CONSTRAINT fk_datasets_viscoelastic_selection_member_selection FOREIGN KEY
            (organization_id, project_id, classification,
             selection_id, selection_revision_id)
            REFERENCES datasets.viscoelastic_selection_revision
            (organization_id, project_id, classification, aggregate_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_datasets_viscoelastic_selection_member_dataset FOREIGN KEY
            (organization_id, project_id, classification,
             dataset_id, dataset_revision_id)
            REFERENCES datasets.shear_relaxation_dataset_revision
            (organization_id, project_id, classification, aggregate_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_datasets_viscoelastic_selection_member_run FOREIGN KEY
            (organization_id, project_id, classification,
             test_run_id, test_run_revision_id)
            REFERENCES testing.test_run_revision
            (organization_id, project_id, classification, aggregate_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED
        );
        CREATE INDEX ix_datasets_viscoelastic_selection_member_dataset
          ON datasets.viscoelastic_selection_member
          (organization_id, project_id, classification, dataset_revision_id);
        CREATE FUNCTION datasets.validate_viscoelastic_selection_counts()
        RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE revision_id uuid; expected_members integer; expected_temperatures integer;
                actual_members integer; actual_temperatures integer;
        BEGIN
          IF TG_TABLE_NAME='viscoelastic_selection_revision' THEN
            revision_id := NEW.id;
          ELSE
            revision_id := NEW.selection_revision_id;
          END IF;
          SELECT member_count, temperature_count
          INTO expected_members, expected_temperatures
          FROM datasets.viscoelastic_selection_revision
          WHERE organization_id=NEW.organization_id AND project_id=NEW.project_id
            AND id=revision_id;
          SELECT count(*), count(DISTINCT temperature_k)
          INTO actual_members, actual_temperatures
          FROM datasets.viscoelastic_selection_member
          WHERE organization_id=NEW.organization_id AND project_id=NEW.project_id
            AND selection_revision_id=revision_id;
          IF expected_members IS NULL OR actual_members<>expected_members OR
             actual_temperatures<>expected_temperatures THEN
            RAISE EXCEPTION
              'viscoelastic Selection summary must match exact members and temperatures';
          END IF;
          RETURN NULL;
        END $$;
        CREATE CONSTRAINT TRIGGER datasets_viscoelastic_selection_revision_counts
          AFTER INSERT ON datasets.viscoelastic_selection_revision
          DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
          EXECUTE FUNCTION datasets.validate_viscoelastic_selection_counts();
        CREATE CONSTRAINT TRIGGER datasets_viscoelastic_selection_member_counts
          AFTER INSERT ON datasets.viscoelastic_selection_member
          DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
          EXECUTE FUNCTION datasets.validate_viscoelastic_selection_counts();
        """
    )
    op.execute(
        """
        CREATE TABLE processing.viscoelastic_master_plan (
          id uuid NOT NULL, organization_id uuid NOT NULL, project_id uuid NOT NULL,
          classification varchar(64) NOT NULL, plan_label varchar(160) NOT NULL,
          selection_id uuid NOT NULL, current_revision_id uuid NOT NULL,
          created_at timestamptz NOT NULL, created_by uuid NOT NULL,
          updated_at timestamptz NOT NULL,
          CONSTRAINT pk_processing_viscoelastic_master_plan PRIMARY KEY
            (organization_id, project_id, id),
          CONSTRAINT uq_processing_viscoelastic_master_plan_scope UNIQUE
            (organization_id, project_id, classification, id),
          CONSTRAINT uq_processing_viscoelastic_master_plan_label UNIQUE
            (organization_id, project_id, classification, selection_id, plan_label),
          CONSTRAINT fk_processing_viscoelastic_master_plan_selection FOREIGN KEY
            (organization_id, project_id, classification, selection_id)
            REFERENCES datasets.viscoelastic_selection
            (organization_id, project_id, classification, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED
        );
        CREATE TABLE processing.viscoelastic_master_plan_revision (
          id uuid NOT NULL, aggregate_id uuid NOT NULL,
          organization_id uuid NOT NULL, project_id uuid NOT NULL,
          classification varchar(64) NOT NULL, revision_no bigint NOT NULL,
          based_on_revision_id uuid, schema_id varchar(255) NOT NULL,
          schema_version varchar(64) NOT NULL,
          content_hash char(64) COLLATE "C" NOT NULL,
          created_at timestamptz NOT NULL, created_by uuid NOT NULL,
          change_reason text NOT NULL, request_id uuid NOT NULL,
          trace_id varchar(255) NOT NULL, plan_label varchar(160) NOT NULL,
          selection_id uuid NOT NULL, selection_revision_id uuid NOT NULL,
          reference_temperature_k double precision NOT NULL,
          grid_point_count smallint NOT NULL, shift_method varchar(32) NOT NULL,
          interpolation varchar(64) NOT NULL, domain_policy varchar(64) NOT NULL,
          reduced_time_convention varchar(64) NOT NULL,
          CONSTRAINT pk_processing_viscoelastic_master_plan_revision PRIMARY KEY
            (organization_id, project_id, id),
          CONSTRAINT uq_processing_viscoelastic_master_plan_revision_scope UNIQUE
            (organization_id, project_id, classification, aggregate_id, id),
          CONSTRAINT uq_processing_viscoelastic_master_plan_revision_no UNIQUE
            (organization_id, project_id, aggregate_id, revision_no),
          CONSTRAINT ck_processing_viscoelastic_master_plan_revision CHECK
            (revision_no > 0 AND content_hash ~ '^[0-9a-f]{64}$' AND
             length(btrim(plan_label)) BETWEEN 1 AND 160 AND
             length(btrim(change_reason)) BETWEEN 1 AND 2000 AND
             reference_temperature_k > 0 AND grid_point_count BETWEEN 3 AND 501 AND
             shift_method IN ('manual','wlf_fit') AND
             interpolation='piecewise_linear_log_time' AND
             domain_policy='common_intersection_no_extrapolation' AND
             reduced_time_convention='time_divided_by_a_t'),
          CONSTRAINT fk_processing_viscoelastic_master_plan_revision_identity FOREIGN KEY
            (organization_id, project_id, classification, aggregate_id)
            REFERENCES processing.viscoelastic_master_plan
            (organization_id, project_id, classification, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_processing_viscoelastic_master_plan_revision_base FOREIGN KEY
            (organization_id, project_id, based_on_revision_id)
            REFERENCES processing.viscoelastic_master_plan_revision
            (organization_id, project_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_processing_viscoelastic_master_plan_revision_selection FOREIGN KEY
            (organization_id, project_id, classification,
             selection_id, selection_revision_id)
            REFERENCES datasets.viscoelastic_selection_revision
            (organization_id, project_id, classification, aggregate_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED
        );
        ALTER TABLE processing.viscoelastic_master_plan
          ADD CONSTRAINT fk_processing_viscoelastic_master_plan_current FOREIGN KEY
          (organization_id, project_id, classification, id, current_revision_id)
          REFERENCES processing.viscoelastic_master_plan_revision
          (organization_id, project_id, classification, aggregate_id, id)
          ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED;
        CREATE TABLE processing.viscoelastic_master_plan_manual_shift (
          organization_id uuid NOT NULL, project_id uuid NOT NULL,
          classification varchar(64) NOT NULL, plan_id uuid NOT NULL,
          plan_revision_id uuid NOT NULL, ordinal smallint NOT NULL,
          temperature_k double precision NOT NULL, log10_a_t double precision NOT NULL,
          CONSTRAINT pk_processing_viscoelastic_master_plan_manual_shift PRIMARY KEY
            (organization_id, project_id, plan_revision_id, ordinal),
          CONSTRAINT uq_processing_viscoelastic_master_plan_manual_temperature UNIQUE
            (organization_id, project_id, plan_revision_id, temperature_k),
          CONSTRAINT ck_processing_viscoelastic_master_plan_manual_shift CHECK
            (ordinal BETWEEN 0 AND 49 AND temperature_k > 0 AND
             log10_a_t BETWEEN -20 AND 20),
          CONSTRAINT fk_processing_viscoelastic_master_plan_manual_revision FOREIGN KEY
            (organization_id, project_id, classification, plan_id, plan_revision_id)
            REFERENCES processing.viscoelastic_master_plan_revision
            (organization_id, project_id, classification, aggregate_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED
        );
        CREATE TABLE processing.viscoelastic_master_run (
          id uuid NOT NULL, organization_id uuid NOT NULL, project_id uuid NOT NULL,
          classification varchar(64) NOT NULL, plan_id uuid NOT NULL,
          plan_revision_id uuid NOT NULL, selection_id uuid NOT NULL,
          selection_revision_id uuid NOT NULL, status varchar(16) NOT NULL,
          source_curve_count smallint NOT NULL, temperature_count smallint NOT NULL,
          aligned_row_count bigint, statistics_row_count bigint, master_row_count bigint,
          aligned_dataset_id uuid, aligned_dataset_revision_id uuid,
          statistics_dataset_id uuid, statistics_dataset_revision_id uuid,
          master_dataset_id uuid, master_dataset_revision_id uuid,
          wlf_c1 double precision, wlf_c2_k double precision,
          failure_code varchar(100), change_reason text NOT NULL,
          started_at timestamptz NOT NULL, ended_at timestamptz,
          created_by uuid NOT NULL, request_id uuid NOT NULL,
          trace_id varchar(255) NOT NULL,
          CONSTRAINT pk_processing_viscoelastic_master_run PRIMARY KEY
            (organization_id, project_id, id),
          CONSTRAINT uq_processing_viscoelastic_master_run_scope UNIQUE
            (organization_id, project_id, classification, id),
          CONSTRAINT ck_processing_viscoelastic_master_run_counts CHECK
            (source_curve_count BETWEEN 2 AND 50 AND
             temperature_count BETWEEN 2 AND source_curve_count),
          CONSTRAINT ck_processing_viscoelastic_master_run_reason CHECK
            (length(btrim(change_reason)) BETWEEN 1 AND 2000 AND
             length(btrim(trace_id)) BETWEEN 1 AND 255),
          CONSTRAINT ck_processing_viscoelastic_master_run_terminal CHECK
            ((status='executing' AND ended_at IS NULL AND aligned_dataset_id IS NULL AND
              statistics_dataset_id IS NULL AND master_dataset_id IS NULL AND
              failure_code IS NULL)
             OR (status='succeeded' AND ended_at IS NOT NULL AND
                 aligned_dataset_id IS NOT NULL AND aligned_dataset_revision_id IS NOT NULL AND
                 statistics_dataset_id IS NOT NULL AND
                 statistics_dataset_revision_id IS NOT NULL AND
                 master_dataset_id IS NOT NULL AND master_dataset_revision_id IS NOT NULL AND
                 aligned_row_count > 0 AND statistics_row_count > 0 AND master_row_count > 0 AND
                 failure_code IS NULL)
             OR (status='failed' AND ended_at IS NOT NULL AND aligned_dataset_id IS NULL AND
                 statistics_dataset_id IS NULL AND master_dataset_id IS NULL AND
                 failure_code IS NOT NULL)),
          CONSTRAINT fk_processing_viscoelastic_master_run_plan FOREIGN KEY
            (organization_id, project_id, classification, plan_id, plan_revision_id)
            REFERENCES processing.viscoelastic_master_plan_revision
            (organization_id, project_id, classification, aggregate_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_processing_viscoelastic_master_run_selection FOREIGN KEY
            (organization_id, project_id, classification,
             selection_id, selection_revision_id)
            REFERENCES datasets.viscoelastic_selection_revision
            (organization_id, project_id, classification, aggregate_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED
        );
        CREATE INDEX ix_processing_viscoelastic_master_run_selection
          ON processing.viscoelastic_master_run
          (organization_id, project_id, classification, selection_revision_id, started_at DESC);
        CREATE TABLE processing.viscoelastic_master_shift_factor (
          organization_id uuid NOT NULL, project_id uuid NOT NULL,
          classification varchar(64) NOT NULL, processing_run_id uuid NOT NULL,
          ordinal smallint NOT NULL, temperature_k double precision NOT NULL,
          log10_a_t double precision NOT NULL, source varchar(32) NOT NULL,
          observed_log10_a_t double precision, residual_log10_a_t double precision,
          alignment_rmse_pa double precision,
          CONSTRAINT pk_processing_viscoelastic_master_shift_factor PRIMARY KEY
            (organization_id, project_id, processing_run_id, ordinal),
          CONSTRAINT uq_processing_viscoelastic_master_shift_temperature UNIQUE
            (organization_id, project_id, processing_run_id, temperature_k),
          CONSTRAINT ck_processing_viscoelastic_master_shift_factor CHECK
            (ordinal BETWEEN 0 AND 49 AND temperature_k > 0 AND
             log10_a_t BETWEEN -20 AND 20 AND
             source IN ('reference','manual','wlf_fit') AND
             (alignment_rmse_pa IS NULL OR alignment_rmse_pa >= 0)),
          CONSTRAINT fk_processing_viscoelastic_master_shift_run FOREIGN KEY
            (organization_id, project_id, classification, processing_run_id)
            REFERENCES processing.viscoelastic_master_run
            (organization_id, project_id, classification, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED
        );
        """
    )
    op.execute(
        """
        CREATE TABLE datasets.viscoelastic_derived_dataset (
          id uuid NOT NULL, organization_id uuid NOT NULL, project_id uuid NOT NULL,
          classification varchar(64) NOT NULL, material_state_id uuid NOT NULL,
          processing_run_id uuid NOT NULL, representation varchar(32) NOT NULL,
          current_revision_id uuid NOT NULL, created_at timestamptz NOT NULL,
          created_by uuid NOT NULL, updated_at timestamptz NOT NULL,
          CONSTRAINT pk_datasets_viscoelastic_derived_dataset PRIMARY KEY
            (organization_id, project_id, id),
          CONSTRAINT uq_datasets_viscoelastic_derived_dataset_scope UNIQUE
            (organization_id, project_id, classification, id),
          CONSTRAINT uq_datasets_viscoelastic_derived_dataset_run_kind UNIQUE
            (organization_id, project_id, classification, processing_run_id, representation),
          CONSTRAINT ck_datasets_viscoelastic_derived_dataset_kind CHECK
            (representation IN ('aligned','statistics','master_curve')),
          CONSTRAINT fk_datasets_viscoelastic_derived_dataset_state FOREIGN KEY
            (organization_id, project_id, classification, material_state_id)
            REFERENCES catalog.material_state
            (organization_id, project_id, classification, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_datasets_viscoelastic_derived_dataset_run FOREIGN KEY
            (organization_id, project_id, classification, processing_run_id)
            REFERENCES processing.viscoelastic_master_run
            (organization_id, project_id, classification, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED
        );
        CREATE TABLE datasets.viscoelastic_derived_dataset_revision (
          id uuid NOT NULL, aggregate_id uuid NOT NULL,
          organization_id uuid NOT NULL, project_id uuid NOT NULL,
          classification varchar(64) NOT NULL, revision_no bigint NOT NULL,
          based_on_revision_id uuid, schema_id varchar(255) NOT NULL,
          schema_version varchar(64) NOT NULL,
          content_hash char(64) COLLATE "C" NOT NULL,
          created_at timestamptz NOT NULL, created_by uuid NOT NULL,
          change_reason text NOT NULL, request_id uuid NOT NULL,
          trace_id varchar(255) NOT NULL, material_state_id uuid NOT NULL,
          material_state_revision_id uuid NOT NULL, selection_id uuid NOT NULL,
          selection_revision_id uuid NOT NULL, processing_plan_id uuid NOT NULL,
          processing_plan_revision_id uuid NOT NULL, processing_run_id uuid NOT NULL,
          representation varchar(32) NOT NULL, data_artifact_id uuid NOT NULL,
          data_sha256 char(64) COLLATE "C" NOT NULL, row_count bigint NOT NULL,
          source_curve_count smallint NOT NULL,
          reference_temperature_k double precision NOT NULL, schema_ref varchar(500) NOT NULL,
          CONSTRAINT pk_datasets_viscoelastic_derived_dataset_revision PRIMARY KEY
            (organization_id, project_id, id),
          CONSTRAINT uq_datasets_viscoelastic_derived_dataset_revision_scope UNIQUE
            (organization_id, project_id, classification, aggregate_id, id),
          CONSTRAINT uq_datasets_viscoelastic_derived_dataset_revision_no UNIQUE
            (organization_id, project_id, aggregate_id, revision_no),
          CONSTRAINT ck_datasets_viscoelastic_derived_dataset_revision CHECK
            (revision_no > 0 AND content_hash ~ '^[0-9a-f]{64}$' AND
             data_sha256 ~ '^[0-9a-f]{64}$' AND row_count BETWEEN 1 AND 1000000 AND
             source_curve_count BETWEEN 2 AND 50 AND reference_temperature_k > 0 AND
             representation IN ('aligned','statistics','master_curve') AND
             length(btrim(schema_ref)) BETWEEN 1 AND 500 AND
             length(btrim(change_reason)) BETWEEN 1 AND 2000),
          CONSTRAINT fk_datasets_viscoelastic_derived_revision_identity FOREIGN KEY
            (organization_id, project_id, classification, aggregate_id)
            REFERENCES datasets.viscoelastic_derived_dataset
            (organization_id, project_id, classification, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_datasets_viscoelastic_derived_revision_base FOREIGN KEY
            (organization_id, project_id, based_on_revision_id)
            REFERENCES datasets.viscoelastic_derived_dataset_revision
            (organization_id, project_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_datasets_viscoelastic_derived_revision_state FOREIGN KEY
            (organization_id, project_id, classification,
             material_state_id, material_state_revision_id)
            REFERENCES catalog.material_state_revision
            (organization_id, project_id, classification, aggregate_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_datasets_viscoelastic_derived_revision_selection FOREIGN KEY
            (organization_id, project_id, classification,
             selection_id, selection_revision_id)
            REFERENCES datasets.viscoelastic_selection_revision
            (organization_id, project_id, classification, aggregate_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_datasets_viscoelastic_derived_revision_plan FOREIGN KEY
            (organization_id, project_id, classification,
             processing_plan_id, processing_plan_revision_id)
            REFERENCES processing.viscoelastic_master_plan_revision
            (organization_id, project_id, classification, aggregate_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_datasets_viscoelastic_derived_revision_run FOREIGN KEY
            (organization_id, project_id, classification, processing_run_id)
            REFERENCES processing.viscoelastic_master_run
            (organization_id, project_id, classification, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_datasets_viscoelastic_derived_revision_artifact FOREIGN KEY
            (organization_id, project_id, classification, data_artifact_id)
            REFERENCES artifact.artifact
            (organization_id, project_id, classification, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED
        );
        ALTER TABLE datasets.viscoelastic_derived_dataset
          ADD CONSTRAINT fk_datasets_viscoelastic_derived_dataset_current FOREIGN KEY
          (organization_id, project_id, classification, id, current_revision_id)
          REFERENCES datasets.viscoelastic_derived_dataset_revision
          (organization_id, project_id, classification, aggregate_id, id)
          ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED;
        CREATE INDEX ix_datasets_viscoelastic_derived_dataset_selection
          ON datasets.viscoelastic_derived_dataset_revision
          (organization_id, project_id, classification, selection_revision_id, representation);
        ALTER TABLE processing.viscoelastic_master_run
          ADD CONSTRAINT fk_processing_viscoelastic_master_run_aligned FOREIGN KEY
          (organization_id, project_id, classification,
           aligned_dataset_id, aligned_dataset_revision_id)
          REFERENCES datasets.viscoelastic_derived_dataset_revision
          (organization_id, project_id, classification, aggregate_id, id)
          ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          ADD CONSTRAINT fk_processing_viscoelastic_master_run_statistics FOREIGN KEY
          (organization_id, project_id, classification,
           statistics_dataset_id, statistics_dataset_revision_id)
          REFERENCES datasets.viscoelastic_derived_dataset_revision
          (organization_id, project_id, classification, aggregate_id, id)
          ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          ADD CONSTRAINT fk_processing_viscoelastic_master_run_master FOREIGN KEY
          (organization_id, project_id, classification,
           master_dataset_id, master_dataset_revision_id)
          REFERENCES datasets.viscoelastic_derived_dataset_revision
          (organization_id, project_id, classification, aggregate_id, id)
          ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED;
        """
    )
    op.execute(
        """
        CREATE FUNCTION processing.guard_viscoelastic_master_run_mutation()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF TG_OP='DELETE' OR OLD.status<>'executing' THEN
            RAISE EXCEPTION 'terminal viscoelastic master Runs are immutable';
          END IF;
          IF NEW.id<>OLD.id OR NEW.organization_id<>OLD.organization_id OR
             NEW.project_id<>OLD.project_id OR NEW.classification<>OLD.classification OR
             NEW.plan_id<>OLD.plan_id OR NEW.plan_revision_id<>OLD.plan_revision_id OR
             NEW.selection_id<>OLD.selection_id OR
             NEW.selection_revision_id<>OLD.selection_revision_id OR
             NEW.source_curve_count<>OLD.source_curve_count OR
             NEW.temperature_count<>OLD.temperature_count OR
             NEW.change_reason<>OLD.change_reason OR NEW.started_at<>OLD.started_at OR
             NEW.created_by<>OLD.created_by OR NEW.request_id<>OLD.request_id OR
             NEW.trace_id<>OLD.trace_id OR NEW.status='executing' THEN
            RAISE EXCEPTION 'viscoelastic master Run immutable inputs cannot change';
          END IF;
          RETURN NEW;
        END $$;
        CREATE TRIGGER processing_viscoelastic_master_run_guard BEFORE UPDATE OR DELETE
          ON processing.viscoelastic_master_run FOR EACH ROW
          EXECUTE FUNCTION processing.guard_viscoelastic_master_run_mutation();
        CREATE FUNCTION processing.validate_viscoelastic_shift_count()
        RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE expected integer; actual integer;
        BEGIN
          SELECT temperature_count INTO expected
          FROM processing.viscoelastic_master_run
          WHERE organization_id=NEW.organization_id AND project_id=NEW.project_id
            AND id=NEW.processing_run_id;
          SELECT count(*) INTO actual FROM processing.viscoelastic_master_shift_factor
          WHERE organization_id=NEW.organization_id AND project_id=NEW.project_id
            AND processing_run_id=NEW.processing_run_id;
          IF expected IS NULL OR actual<>expected THEN
            RAISE EXCEPTION 'shift-factor evidence must cover every selected temperature';
          END IF;
          RETURN NULL;
        END $$;
        CREATE CONSTRAINT TRIGGER processing_viscoelastic_shift_count_guard
          AFTER INSERT ON processing.viscoelastic_master_shift_factor
          DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
          EXECUTE FUNCTION processing.validate_viscoelastic_shift_count();
        """
    )
    for identity in _DATASET_IDENTITIES:
        op.execute(
            f"CREATE TRIGGER datasets_{identity}_head_only BEFORE UPDATE OR DELETE "
            f"ON datasets.{identity} FOR EACH ROW "
            "EXECUTE FUNCTION revisioning.guard_identity_head_update()"
        )
    for table in _DATASET_IMMUTABLE:
        op.execute(
            f"CREATE TRIGGER datasets_{table}_immutable BEFORE UPDATE OR DELETE "
            f"ON datasets.{table} FOR EACH ROW "
            "EXECUTE FUNCTION revisioning.reject_immutable_row_mutation()"
        )
    for identity in _PROCESSING_IDENTITIES:
        op.execute(
            f"CREATE TRIGGER processing_{identity}_head_only BEFORE UPDATE OR DELETE "
            f"ON processing.{identity} FOR EACH ROW "
            "EXECUTE FUNCTION revisioning.guard_identity_head_update()"
        )
    for table in _PROCESSING_IMMUTABLE:
        op.execute(
            f"CREATE TRIGGER processing_{table}_immutable BEFORE UPDATE OR DELETE "
            f"ON processing.{table} FOR EACH ROW "
            "EXECUTE FUNCTION revisioning.reject_immutable_row_mutation()"
        )
    for table in (*_DATASET_IDENTITIES, *_DATASET_IMMUTABLE):
        _rls("datasets", table, "dataset.read", "dataset.write")
    for table in (
        *_PROCESSING_IDENTITIES,
        *_PROCESSING_IMMUTABLE,
        "viscoelastic_master_run",
    ):
        _rls("processing", table, "processing.read", "processing.execute")


def downgrade() -> None:
    op.execute(
        "DROP FUNCTION IF EXISTS datasets.validate_viscoelastic_selection_counts() CASCADE"
    )
    op.execute("DROP FUNCTION IF EXISTS processing.validate_viscoelastic_shift_count() CASCADE")
    op.execute(
        "DROP FUNCTION IF EXISTS processing.guard_viscoelastic_master_run_mutation() CASCADE"
    )
    op.execute(
        "ALTER TABLE processing.viscoelastic_master_run "
        "DROP CONSTRAINT fk_processing_viscoelastic_master_run_aligned, "
        "DROP CONSTRAINT fk_processing_viscoelastic_master_run_statistics, "
        "DROP CONSTRAINT fk_processing_viscoelastic_master_run_master"
    )
    op.execute(
        "ALTER TABLE datasets.viscoelastic_derived_dataset "
        "DROP CONSTRAINT fk_datasets_viscoelastic_derived_dataset_current"
    )
    op.execute("DROP TABLE datasets.viscoelastic_derived_dataset_revision")
    op.execute("DROP TABLE datasets.viscoelastic_derived_dataset")
    op.execute("DROP TABLE processing.viscoelastic_master_shift_factor")
    op.execute("DROP TABLE processing.viscoelastic_master_run")
    op.execute("DROP TABLE processing.viscoelastic_master_plan_manual_shift")
    op.execute(
        "ALTER TABLE processing.viscoelastic_master_plan "
        "DROP CONSTRAINT fk_processing_viscoelastic_master_plan_current"
    )
    op.execute("DROP TABLE processing.viscoelastic_master_plan_revision")
    op.execute("DROP TABLE processing.viscoelastic_master_plan")
    op.execute("DROP TABLE datasets.viscoelastic_selection_member")
    op.execute(
        "ALTER TABLE datasets.viscoelastic_selection "
        "DROP CONSTRAINT fk_datasets_viscoelastic_selection_current"
    )
    op.execute("DROP TABLE datasets.viscoelastic_selection_revision")
    op.execute("DROP TABLE datasets.viscoelastic_selection")

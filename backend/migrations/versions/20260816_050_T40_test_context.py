"""Add governed Test Campaign, Instrument, condition, and Run context.

Revision ID: 20260816_050_test_context
Revises: 20260815_049_process_run

Traceability: T-40, FR-CAT-006/007, NFR-INT-001, NFR-SEC-003/006.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260816_050_test_context"
down_revision: str | None = "20260815_049_process_run"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_PAIRS = (
    ("test_campaign", "test_campaign_revision"),
    ("instrument", "instrument_revision"),
    ("instrument_calibration", "instrument_calibration_revision"),
    ("test_condition_snapshot", "test_condition_snapshot_revision"),
    ("test_run_context", "test_run_context_revision"),
)


def _security(identity: str, revision_table: str) -> None:
    op.execute(
        f"CREATE TRIGGER testing_{identity}_head_only BEFORE UPDATE OR DELETE "
        f"ON testing.{identity} FOR EACH ROW "
        "EXECUTE FUNCTION revisioning.guard_identity_head_update()"
    )
    op.execute(
        f"CREATE TRIGGER testing_{revision_table}_immutable BEFORE UPDATE OR DELETE "
        f"ON testing.{revision_table} FOR EACH ROW "
        "EXECUTE FUNCTION revisioning.reject_immutable_row_mutation()"
    )
    for table in (identity, revision_table):
        op.execute(f"ALTER TABLE testing.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE testing.{table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY testing_{table}_select ON testing.{table} FOR SELECT USING "
            "(access_control.can_access_row(organization_id, project_id, classification, "
            "'testing.read'))"
        )
        op.execute(
            f"CREATE POLICY testing_{table}_insert ON testing.{table} FOR INSERT WITH CHECK "
            "(access_control.can_access_row(organization_id, project_id, classification, "
            "'testing.write'))"
        )
        op.execute(
            f"CREATE POLICY testing_{table}_update ON testing.{table} FOR UPDATE USING "
            "(access_control.can_access_row(organization_id, project_id, classification, "
            "'testing.write')) WITH CHECK "
            "(access_control.can_access_row(organization_id, project_id, classification, "
            "'testing.write'))"
        )


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE testing.test_campaign (
          id uuid NOT NULL, organization_id uuid NOT NULL, project_id uuid NOT NULL,
          classification varchar(64) NOT NULL, test_method_id uuid NOT NULL,
          campaign_code varchar(100) NOT NULL, current_revision_id uuid NOT NULL,
          created_at timestamptz NOT NULL, created_by uuid NOT NULL,
          updated_at timestamptz NOT NULL,
          CONSTRAINT pk_testing_test_campaign PRIMARY KEY (organization_id, project_id, id),
          CONSTRAINT uq_testing_test_campaign_scope UNIQUE
            (organization_id, project_id, classification, id),
          CONSTRAINT uq_testing_test_campaign_parent UNIQUE
            (organization_id, project_id, classification, id, test_method_id, campaign_code),
          CONSTRAINT uq_testing_test_campaign_code UNIQUE
            (organization_id, project_id, classification, campaign_code),
          CONSTRAINT fk_testing_test_campaign_method FOREIGN KEY
            (organization_id, project_id, classification, test_method_id)
            REFERENCES testing.test_method
            (organization_id, project_id, classification, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT ck_testing_test_campaign_code CHECK
            (length(btrim(campaign_code)) BETWEEN 1 AND 100 AND campaign_code=btrim(campaign_code))
        );
        CREATE TABLE testing.test_campaign_revision (
          id uuid NOT NULL, aggregate_id uuid NOT NULL,
          organization_id uuid NOT NULL, project_id uuid NOT NULL,
          classification varchar(64) NOT NULL, revision_no bigint NOT NULL,
          based_on_revision_id uuid, schema_id varchar(255) NOT NULL,
          schema_version varchar(64) NOT NULL, content_hash char(64) COLLATE "C" NOT NULL,
          created_at timestamptz NOT NULL, created_by uuid NOT NULL,
          change_reason text NOT NULL, request_id uuid NOT NULL, trace_id varchar(255) NOT NULL,
          test_method_id uuid NOT NULL, test_method_revision_id uuid NOT NULL,
          campaign_code varchar(100) NOT NULL, name varchar(200) NOT NULL,
          objective text NOT NULL, population_description text NOT NULL,
          planned_specimen_count integer NOT NULL, standard_conformance varchar(32) NOT NULL,
          standard_designation varchar(200), standard_edition varchar(100),
          standard_deviation_reason text, reference_only boolean NOT NULL,
          CONSTRAINT pk_testing_test_campaign_revision PRIMARY KEY
            (organization_id, project_id, id),
          CONSTRAINT uq_testing_test_campaign_revision_id UNIQUE
            (organization_id, project_id, aggregate_id, id),
          CONSTRAINT uq_testing_test_campaign_revision_scope UNIQUE
            (organization_id, project_id, classification, aggregate_id, id),
          CONSTRAINT uq_testing_test_campaign_revision_no UNIQUE
            (organization_id, project_id, aggregate_id, revision_no),
          CONSTRAINT fk_testing_test_campaign_revision_identity FOREIGN KEY
            (organization_id, project_id, classification, aggregate_id,
             test_method_id, campaign_code) REFERENCES testing.test_campaign
            (organization_id, project_id, classification, id, test_method_id, campaign_code)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_testing_test_campaign_revision_base FOREIGN KEY
            (organization_id, project_id, aggregate_id, based_on_revision_id)
            REFERENCES testing.test_campaign_revision
            (organization_id, project_id, aggregate_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_testing_test_campaign_revision_method FOREIGN KEY
            (organization_id, project_id, classification, test_method_id,
             test_method_revision_id) REFERENCES testing.test_method_revision
            (organization_id, project_id, classification, aggregate_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT ck_testing_test_campaign_revision_base CHECK
            ((revision_no=1 AND based_on_revision_id IS NULL) OR
             (revision_no>1 AND based_on_revision_id IS NOT NULL)),
          CONSTRAINT ck_testing_test_campaign_revision_hash CHECK
            (content_hash ~ '^[0-9a-f]{64}$'),
          CONSTRAINT ck_testing_test_campaign_revision_content CHECK
            (planned_specimen_count BETWEEN 1 AND 1000000 AND reference_only AND
             length(btrim(name)) BETWEEN 1 AND 200 AND
             length(btrim(objective)) BETWEEN 1 AND 2000 AND
             length(btrim(population_description)) BETWEEN 1 AND 2000 AND
             ((standard_conformance='not_claimed' AND standard_designation IS NULL AND
               standard_edition IS NULL AND standard_deviation_reason IS NULL) OR
              (standard_conformance='conformant' AND
               length(btrim(standard_designation)) BETWEEN 1 AND 200 AND
               length(btrim(standard_edition)) BETWEEN 1 AND 100 AND
               standard_deviation_reason IS NULL) OR
              (standard_conformance='deviation_approved' AND
               length(btrim(standard_designation)) BETWEEN 1 AND 200 AND
               length(btrim(standard_edition)) BETWEEN 1 AND 100 AND
               length(btrim(standard_deviation_reason)) BETWEEN 1 AND 2000)))
        );
        ALTER TABLE testing.test_campaign ADD CONSTRAINT fk_testing_test_campaign_current
          FOREIGN KEY (organization_id, project_id, id, current_revision_id)
          REFERENCES testing.test_campaign_revision
          (organization_id, project_id, aggregate_id, id)
          ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED;

        CREATE TABLE testing.instrument (
          id uuid NOT NULL, organization_id uuid NOT NULL, project_id uuid NOT NULL,
          classification varchar(64) NOT NULL, instrument_code varchar(100) NOT NULL,
          serial_number varchar(200) NOT NULL, current_revision_id uuid NOT NULL,
          created_at timestamptz NOT NULL, created_by uuid NOT NULL,
          updated_at timestamptz NOT NULL,
          CONSTRAINT pk_testing_instrument PRIMARY KEY (organization_id, project_id, id),
          CONSTRAINT uq_testing_instrument_scope UNIQUE
            (organization_id, project_id, classification, id),
          CONSTRAINT uq_testing_instrument_parent UNIQUE
            (organization_id, project_id, classification, id, instrument_code, serial_number),
          CONSTRAINT uq_testing_instrument_code UNIQUE
            (organization_id, project_id, classification, instrument_code),
          CONSTRAINT uq_testing_instrument_serial UNIQUE
            (organization_id, project_id, classification, serial_number),
          CONSTRAINT ck_testing_instrument_identity CHECK
            (length(btrim(instrument_code)) BETWEEN 1 AND 100 AND
             length(btrim(serial_number)) BETWEEN 1 AND 200)
        );
        CREATE TABLE testing.instrument_revision (
          id uuid NOT NULL, aggregate_id uuid NOT NULL,
          organization_id uuid NOT NULL, project_id uuid NOT NULL,
          classification varchar(64) NOT NULL, revision_no bigint NOT NULL,
          based_on_revision_id uuid, schema_id varchar(255) NOT NULL,
          schema_version varchar(64) NOT NULL, content_hash char(64) COLLATE "C" NOT NULL,
          created_at timestamptz NOT NULL, created_by uuid NOT NULL,
          change_reason text NOT NULL, request_id uuid NOT NULL, trace_id varchar(255) NOT NULL,
          instrument_code varchar(100) NOT NULL, name varchar(200) NOT NULL,
          serial_number varchar(200) NOT NULL, manufacturer varchar(200), model varchar(200),
          location varchar(255), description text,
          CONSTRAINT pk_testing_instrument_revision PRIMARY KEY
            (organization_id, project_id, id),
          CONSTRAINT uq_testing_instrument_revision_id UNIQUE
            (organization_id, project_id, aggregate_id, id),
          CONSTRAINT uq_testing_instrument_revision_scope UNIQUE
            (organization_id, project_id, classification, aggregate_id, id),
          CONSTRAINT uq_testing_instrument_revision_no UNIQUE
            (organization_id, project_id, aggregate_id, revision_no),
          CONSTRAINT fk_testing_instrument_revision_identity FOREIGN KEY
            (organization_id, project_id, classification, aggregate_id,
             instrument_code, serial_number) REFERENCES testing.instrument
            (organization_id, project_id, classification, id, instrument_code, serial_number)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_testing_instrument_revision_base FOREIGN KEY
            (organization_id, project_id, aggregate_id, based_on_revision_id)
            REFERENCES testing.instrument_revision
            (organization_id, project_id, aggregate_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT ck_testing_instrument_revision_base CHECK
            ((revision_no=1 AND based_on_revision_id IS NULL) OR
             (revision_no>1 AND based_on_revision_id IS NOT NULL)),
          CONSTRAINT ck_testing_instrument_revision_hash CHECK
            (content_hash ~ '^[0-9a-f]{64}$'),
          CONSTRAINT ck_testing_instrument_revision_content CHECK
            (length(btrim(name)) BETWEEN 1 AND 200 AND
             (manufacturer IS NULL OR length(btrim(manufacturer)) BETWEEN 1 AND 200) AND
             (model IS NULL OR length(btrim(model)) BETWEEN 1 AND 200) AND
             (location IS NULL OR length(btrim(location)) BETWEEN 1 AND 255) AND
             (description IS NULL OR length(btrim(description)) BETWEEN 1 AND 2000))
        );
        ALTER TABLE testing.instrument ADD CONSTRAINT fk_testing_instrument_current
          FOREIGN KEY (organization_id, project_id, id, current_revision_id)
          REFERENCES testing.instrument_revision
          (organization_id, project_id, aggregate_id, id)
          ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED;

        CREATE TABLE testing.instrument_calibration (
          id uuid NOT NULL, organization_id uuid NOT NULL, project_id uuid NOT NULL,
          classification varchar(64) NOT NULL, instrument_id uuid NOT NULL,
          calibration_code varchar(100) NOT NULL, current_revision_id uuid NOT NULL,
          created_at timestamptz NOT NULL, created_by uuid NOT NULL,
          updated_at timestamptz NOT NULL,
          CONSTRAINT pk_testing_instrument_calibration PRIMARY KEY
            (organization_id, project_id, id),
          CONSTRAINT uq_testing_instrument_calibration_scope UNIQUE
            (organization_id, project_id, classification, id),
          CONSTRAINT uq_testing_instrument_calibration_parent UNIQUE
            (organization_id, project_id, classification, id, instrument_id,
             calibration_code),
          CONSTRAINT uq_testing_instrument_calibration_code UNIQUE
            (organization_id, project_id, classification, instrument_id, calibration_code),
          CONSTRAINT fk_testing_instrument_calibration_instrument FOREIGN KEY
            (organization_id, project_id, classification, instrument_id)
            REFERENCES testing.instrument
            (organization_id, project_id, classification, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED
        );
        CREATE TABLE testing.instrument_calibration_revision (
          id uuid NOT NULL, aggregate_id uuid NOT NULL,
          organization_id uuid NOT NULL, project_id uuid NOT NULL,
          classification varchar(64) NOT NULL, revision_no bigint NOT NULL,
          based_on_revision_id uuid, schema_id varchar(255) NOT NULL,
          schema_version varchar(64) NOT NULL, content_hash char(64) COLLATE "C" NOT NULL,
          created_at timestamptz NOT NULL, created_by uuid NOT NULL,
          change_reason text NOT NULL, request_id uuid NOT NULL, trace_id varchar(255) NOT NULL,
          instrument_id uuid NOT NULL, instrument_revision_id uuid NOT NULL,
          calibration_code varchar(100) NOT NULL, certificate_reference varchar(255) NOT NULL,
          provider varchar(200) NOT NULL, calibrated_at timestamptz NOT NULL,
          valid_from timestamptz NOT NULL, valid_until timestamptz NOT NULL,
          result varchar(32) NOT NULL, limitation_note text,
          CONSTRAINT pk_testing_instrument_calibration_revision PRIMARY KEY
            (organization_id, project_id, id),
          CONSTRAINT uq_testing_instrument_calibration_revision_id UNIQUE
            (organization_id, project_id, aggregate_id, id),
          CONSTRAINT uq_testing_instrument_calibration_revision_scope UNIQUE
            (organization_id, project_id, classification, aggregate_id, id),
          CONSTRAINT uq_testing_instrument_calibration_revision_no UNIQUE
            (organization_id, project_id, aggregate_id, revision_no),
          CONSTRAINT fk_testing_instrument_calibration_revision_identity FOREIGN KEY
            (organization_id, project_id, classification, aggregate_id,
             instrument_id, calibration_code) REFERENCES testing.instrument_calibration
            (organization_id, project_id, classification, id, instrument_id, calibration_code)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_testing_instrument_calibration_revision_base FOREIGN KEY
            (organization_id, project_id, aggregate_id, based_on_revision_id)
            REFERENCES testing.instrument_calibration_revision
            (organization_id, project_id, aggregate_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_testing_instrument_calibration_revision_instrument FOREIGN KEY
            (organization_id, project_id, classification, instrument_id,
             instrument_revision_id) REFERENCES testing.instrument_revision
            (organization_id, project_id, classification, aggregate_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT ck_testing_instrument_calibration_revision_base CHECK
            ((revision_no=1 AND based_on_revision_id IS NULL) OR
             (revision_no>1 AND based_on_revision_id IS NOT NULL)),
          CONSTRAINT ck_testing_instrument_calibration_revision_content CHECK
            (content_hash ~ '^[0-9a-f]{64}$' AND calibrated_at<=valid_from AND
             valid_from<valid_until AND result IN ('passed','limited','failed') AND
             ((result='limited' AND length(btrim(limitation_note)) BETWEEN 1 AND 2000) OR
              (result<>'limited' AND limitation_note IS NULL)))
        );
        ALTER TABLE testing.instrument_calibration
          ADD CONSTRAINT fk_testing_instrument_calibration_current FOREIGN KEY
          (organization_id, project_id, id, current_revision_id)
          REFERENCES testing.instrument_calibration_revision
          (organization_id, project_id, aggregate_id, id)
          ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED;

        CREATE TABLE testing.test_condition_snapshot (
          id uuid NOT NULL, organization_id uuid NOT NULL, project_id uuid NOT NULL,
          classification varchar(64) NOT NULL, test_method_id uuid NOT NULL,
          captured_at timestamptz NOT NULL, current_revision_id uuid NOT NULL,
          created_at timestamptz NOT NULL, created_by uuid NOT NULL,
          updated_at timestamptz NOT NULL,
          CONSTRAINT pk_testing_test_condition_snapshot PRIMARY KEY
            (organization_id, project_id, id),
          CONSTRAINT uq_testing_test_condition_snapshot_scope UNIQUE
            (organization_id, project_id, classification, id),
          CONSTRAINT uq_testing_test_condition_snapshot_parent UNIQUE
            (organization_id, project_id, classification, id, test_method_id, captured_at),
          CONSTRAINT fk_testing_test_condition_snapshot_method FOREIGN KEY
            (organization_id, project_id, classification, test_method_id)
            REFERENCES testing.test_method
            (organization_id, project_id, classification, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED
        );
        CREATE TABLE testing.test_condition_snapshot_revision (
          id uuid NOT NULL, aggregate_id uuid NOT NULL,
          organization_id uuid NOT NULL, project_id uuid NOT NULL,
          classification varchar(64) NOT NULL, revision_no bigint NOT NULL,
          based_on_revision_id uuid, schema_id varchar(255) NOT NULL,
          schema_version varchar(64) NOT NULL, content_hash char(64) COLLATE "C" NOT NULL,
          created_at timestamptz NOT NULL, created_by uuid NOT NULL,
          change_reason text NOT NULL, request_id uuid NOT NULL, trace_id varchar(255) NOT NULL,
          test_method_id uuid NOT NULL, test_method_revision_id uuid NOT NULL,
          captured_at timestamptz NOT NULL, temperature_setpoint_k numeric(18,8),
          temperature_observed_k numeric(18,8), humidity_setpoint_pct numeric(18,8),
          humidity_observed_pct numeric(18,8), loading_rate_value numeric(30,12),
          loading_rate_unit varchar(32), orientation varchar(100), medium varchar(200), note text,
          CONSTRAINT pk_testing_test_condition_snapshot_revision PRIMARY KEY
            (organization_id, project_id, id),
          CONSTRAINT uq_testing_test_condition_snapshot_revision_id UNIQUE
            (organization_id, project_id, aggregate_id, id),
          CONSTRAINT uq_testing_test_condition_snapshot_revision_scope UNIQUE
            (organization_id, project_id, classification, aggregate_id, id),
          CONSTRAINT uq_testing_test_condition_snapshot_revision_no UNIQUE
            (organization_id, project_id, aggregate_id, revision_no),
          CONSTRAINT fk_testing_test_condition_snapshot_revision_identity FOREIGN KEY
            (organization_id, project_id, classification, aggregate_id,
             test_method_id, captured_at) REFERENCES testing.test_condition_snapshot
            (organization_id, project_id, classification, id, test_method_id, captured_at)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_testing_test_condition_snapshot_revision_base FOREIGN KEY
            (organization_id, project_id, aggregate_id, based_on_revision_id)
            REFERENCES testing.test_condition_snapshot_revision
            (organization_id, project_id, aggregate_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_testing_test_condition_snapshot_revision_method FOREIGN KEY
            (organization_id, project_id, classification, test_method_id,
             test_method_revision_id) REFERENCES testing.test_method_revision
            (organization_id, project_id, classification, aggregate_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT ck_testing_test_condition_snapshot_revision_base CHECK
            ((revision_no=1 AND based_on_revision_id IS NULL) OR
             (revision_no>1 AND based_on_revision_id IS NOT NULL)),
          CONSTRAINT ck_testing_test_condition_snapshot_revision_content CHECK
            (content_hash ~ '^[0-9a-f]{64}$' AND
             (temperature_setpoint_k IS NULL OR temperature_setpoint_k>=0) AND
             (temperature_observed_k IS NULL OR temperature_observed_k>=0) AND
             (humidity_setpoint_pct IS NULL OR humidity_setpoint_pct BETWEEN 0 AND 100) AND
             (humidity_observed_pct IS NULL OR humidity_observed_pct BETWEEN 0 AND 100) AND
             ((loading_rate_value IS NULL AND loading_rate_unit IS NULL) OR
              (loading_rate_value>=0 AND loading_rate_unit IN ('mm/min','1/s','N/s','Pa/s'))) AND
             num_nonnulls(temperature_setpoint_k,temperature_observed_k,
               humidity_setpoint_pct,humidity_observed_pct,loading_rate_value,
               orientation,medium,note)>0)
        );
        ALTER TABLE testing.test_condition_snapshot
          ADD CONSTRAINT fk_testing_test_condition_snapshot_current FOREIGN KEY
          (organization_id, project_id, id, current_revision_id)
          REFERENCES testing.test_condition_snapshot_revision
          (organization_id, project_id, aggregate_id, id)
          ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED;

        CREATE TABLE testing.test_run_context (
          id uuid NOT NULL, organization_id uuid NOT NULL, project_id uuid NOT NULL,
          classification varchar(64) NOT NULL, test_run_id uuid NOT NULL,
          current_revision_id uuid NOT NULL, created_at timestamptz NOT NULL,
          created_by uuid NOT NULL, updated_at timestamptz NOT NULL,
          CONSTRAINT pk_testing_test_run_context PRIMARY KEY (organization_id, project_id, id),
          CONSTRAINT uq_testing_test_run_context_scope UNIQUE
            (organization_id, project_id, classification, id),
          CONSTRAINT uq_testing_test_run_context_parent UNIQUE
            (organization_id, project_id, classification, id, test_run_id),
          CONSTRAINT uq_testing_test_run_context_run UNIQUE
            (organization_id, project_id, test_run_id),
          CONSTRAINT fk_testing_test_run_context_run FOREIGN KEY
            (organization_id, project_id, classification, test_run_id)
            REFERENCES testing.test_run
            (organization_id, project_id, classification, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED
        );
        CREATE TABLE testing.test_run_context_revision (
          id uuid NOT NULL, aggregate_id uuid NOT NULL,
          organization_id uuid NOT NULL, project_id uuid NOT NULL,
          classification varchar(64) NOT NULL, revision_no bigint NOT NULL,
          based_on_revision_id uuid, schema_id varchar(255) NOT NULL,
          schema_version varchar(64) NOT NULL, content_hash char(64) COLLATE "C" NOT NULL,
          created_at timestamptz NOT NULL, created_by uuid NOT NULL,
          change_reason text NOT NULL, request_id uuid NOT NULL, trace_id varchar(255) NOT NULL,
          test_run_id uuid NOT NULL, test_run_revision_id uuid NOT NULL,
          test_campaign_id uuid NOT NULL, test_campaign_revision_id uuid NOT NULL,
          test_condition_id uuid NOT NULL, test_condition_revision_id uuid NOT NULL,
          instrument_id uuid NOT NULL, instrument_revision_id uuid NOT NULL,
          calibration_id uuid NOT NULL, calibration_revision_id uuid NOT NULL, note text,
          CONSTRAINT pk_testing_test_run_context_revision PRIMARY KEY
            (organization_id, project_id, id),
          CONSTRAINT uq_testing_test_run_context_revision_id UNIQUE
            (organization_id, project_id, aggregate_id, id),
          CONSTRAINT uq_testing_test_run_context_revision_scope UNIQUE
            (organization_id, project_id, classification, aggregate_id, id),
          CONSTRAINT uq_testing_test_run_context_revision_no UNIQUE
            (organization_id, project_id, aggregate_id, revision_no),
          CONSTRAINT fk_testing_test_run_context_revision_identity FOREIGN KEY
            (organization_id, project_id, classification, aggregate_id, test_run_id)
            REFERENCES testing.test_run_context
            (organization_id, project_id, classification, id, test_run_id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_testing_test_run_context_revision_base FOREIGN KEY
            (organization_id, project_id, aggregate_id, based_on_revision_id)
            REFERENCES testing.test_run_context_revision
            (organization_id, project_id, aggregate_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_testing_test_run_context_revision_run FOREIGN KEY
            (organization_id, project_id, classification, test_run_id, test_run_revision_id)
            REFERENCES testing.test_run_revision
            (organization_id, project_id, classification, aggregate_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_testing_test_run_context_revision_campaign FOREIGN KEY
            (organization_id, project_id, classification, test_campaign_id,
             test_campaign_revision_id) REFERENCES testing.test_campaign_revision
            (organization_id, project_id, classification, aggregate_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_testing_test_run_context_revision_condition FOREIGN KEY
            (organization_id, project_id, classification, test_condition_id,
             test_condition_revision_id) REFERENCES testing.test_condition_snapshot_revision
            (organization_id, project_id, classification, aggregate_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_testing_test_run_context_revision_instrument FOREIGN KEY
            (organization_id, project_id, classification, instrument_id,
             instrument_revision_id) REFERENCES testing.instrument_revision
            (organization_id, project_id, classification, aggregate_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_testing_test_run_context_revision_calibration FOREIGN KEY
            (organization_id, project_id, classification, calibration_id,
             calibration_revision_id) REFERENCES testing.instrument_calibration_revision
            (organization_id, project_id, classification, aggregate_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT ck_testing_test_run_context_revision_base CHECK
            ((revision_no=1 AND based_on_revision_id IS NULL) OR
             (revision_no>1 AND based_on_revision_id IS NOT NULL)),
          CONSTRAINT ck_testing_test_run_context_revision_content CHECK
            (content_hash ~ '^[0-9a-f]{64}$' AND
             (note IS NULL OR length(btrim(note)) BETWEEN 1 AND 2000))
        );
        ALTER TABLE testing.test_run_context
          ADD CONSTRAINT fk_testing_test_run_context_current FOREIGN KEY
          (organization_id, project_id, id, current_revision_id)
          REFERENCES testing.test_run_context_revision
          (organization_id, project_id, aggregate_id, id)
          ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED;

        CREATE INDEX ix_testing_test_campaign_method ON testing.test_campaign
          (organization_id, project_id, classification, test_method_id, campaign_code);
        CREATE INDEX ix_testing_instrument_calibration_time
          ON testing.instrument_calibration_revision
          (organization_id, project_id, classification, instrument_id, valid_from, valid_until);
        CREATE INDEX ix_testing_condition_method_time ON testing.test_condition_snapshot
          (organization_id, project_id, classification, test_method_id, captured_at);

        CREATE FUNCTION testing.validate_instrument_calibration_revision()
        RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE overlap_count integer;
        BEGIN
          IF NEW.result IN ('passed','limited') THEN
            SELECT count(*) INTO overlap_count
            FROM testing.instrument_calibration identity
            JOIN testing.instrument_calibration_revision current_revision
              ON current_revision.organization_id=identity.organization_id
             AND current_revision.project_id=identity.project_id
             AND current_revision.aggregate_id=identity.id
             AND current_revision.id=identity.current_revision_id
            WHERE identity.organization_id=NEW.organization_id
              AND identity.project_id=NEW.project_id
              AND identity.classification=NEW.classification
              AND identity.instrument_id=NEW.instrument_id
              AND identity.id<>NEW.aggregate_id
              AND current_revision.result IN ('passed','limited')
              AND NEW.valid_from<current_revision.valid_until
              AND current_revision.valid_from<NEW.valid_until;
            IF overlap_count>0 THEN
              RAISE EXCEPTION 'usable Instrument calibration intervals cannot overlap';
            END IF;
          END IF;
          RETURN NEW;
        END $$;
        CREATE CONSTRAINT TRIGGER testing_instrument_calibration_interval_guard
          AFTER INSERT ON testing.instrument_calibration_revision
          DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
          EXECUTE FUNCTION testing.validate_instrument_calibration_revision();

        CREATE FUNCTION testing.validate_test_run_context_revision()
        RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE run_method uuid; run_method_revision uuid; run_time timestamptz;
                campaign_method uuid; campaign_method_revision uuid;
                condition_method uuid; condition_method_revision uuid;
                calibration_instrument uuid; calibration_instrument_revision uuid;
                calibration_from timestamptz; calibration_until timestamptz;
                calibration_result varchar(32);
        BEGIN
          SELECT test_method_id,test_method_revision_id,performed_at
            INTO STRICT run_method,run_method_revision,run_time
          FROM testing.test_run_revision
          WHERE organization_id=NEW.organization_id AND project_id=NEW.project_id
            AND classification=NEW.classification AND aggregate_id=NEW.test_run_id
            AND id=NEW.test_run_revision_id;
          SELECT test_method_id,test_method_revision_id
            INTO STRICT campaign_method,campaign_method_revision
          FROM testing.test_campaign_revision
          WHERE organization_id=NEW.organization_id AND project_id=NEW.project_id
            AND aggregate_id=NEW.test_campaign_id AND id=NEW.test_campaign_revision_id;
          SELECT test_method_id,test_method_revision_id
            INTO STRICT condition_method,condition_method_revision
          FROM testing.test_condition_snapshot_revision
          WHERE organization_id=NEW.organization_id AND project_id=NEW.project_id
            AND aggregate_id=NEW.test_condition_id AND id=NEW.test_condition_revision_id;
          SELECT instrument_id,instrument_revision_id,valid_from,valid_until,result
            INTO STRICT calibration_instrument,calibration_instrument_revision,
              calibration_from,calibration_until,calibration_result
          FROM testing.instrument_calibration_revision
          WHERE organization_id=NEW.organization_id AND project_id=NEW.project_id
            AND aggregate_id=NEW.calibration_id AND id=NEW.calibration_revision_id;
          IF campaign_method<>run_method OR campaign_method_revision<>run_method_revision OR
             condition_method<>run_method OR condition_method_revision<>run_method_revision THEN
            RAISE EXCEPTION 'Campaign and Condition must pin the Test Run Method revision';
          END IF;
          IF calibration_instrument<>NEW.instrument_id OR
             calibration_instrument_revision<>NEW.instrument_revision_id THEN
            RAISE EXCEPTION 'Calibration must pin the Test Run Context Instrument revision';
          END IF;
          IF calibration_result NOT IN ('passed','limited') OR
             run_time<calibration_from OR run_time>=calibration_until THEN
            RAISE EXCEPTION 'Calibration is not usable at Test Run execution time';
          END IF;
          RETURN NEW;
        END $$;
        CREATE CONSTRAINT TRIGGER testing_test_run_context_guard
          AFTER INSERT ON testing.test_run_context_revision
          DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
          EXECUTE FUNCTION testing.validate_test_run_context_revision();
        """
    )
    for identity, revision_table in _PAIRS:
        _security(identity, revision_table)


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS testing.validate_test_run_context_revision() CASCADE")
    op.execute("DROP FUNCTION IF EXISTS testing.validate_instrument_calibration_revision() CASCADE")
    for identity, _ in reversed(_PAIRS):
        op.execute(f"ALTER TABLE testing.{identity} DROP CONSTRAINT fk_testing_{identity}_current")
    for table in (
        "test_run_context_revision",
        "test_run_context",
        "test_condition_snapshot_revision",
        "test_condition_snapshot",
        "instrument_calibration_revision",
        "instrument_calibration",
        "instrument_revision",
        "instrument",
        "test_campaign_revision",
        "test_campaign",
    ):
        op.execute(f"DROP TABLE testing.{table}")

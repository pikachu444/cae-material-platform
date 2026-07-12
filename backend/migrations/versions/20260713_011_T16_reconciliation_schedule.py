"""T-16 durable Artifact reconciliation schedule and staging cleanup receipts.

Revision ID: 20260713_011_t16
Revises: 20260713_010_t16
Create Date: 2026-07-13
"""

from alembic import op

revision = "20260713_011_t16"
down_revision = "20260713_010_t16"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE artifact.reconciliation_schedule (
          organization_id uuid NOT NULL,
          project_id uuid NOT NULL,
          classification varchar(64) NOT NULL,
          id uuid NOT NULL,
          interval_seconds integer NOT NULL,
          retention_seconds integer NOT NULL,
          next_run_at timestamptz NOT NULL,
          enabled boolean NOT NULL,
          lease_token uuid,
          lease_expires_at timestamptz,
          current_run_id uuid,
          failure_count integer NOT NULL,
          created_at timestamptz NOT NULL,
          created_by uuid NOT NULL REFERENCES identity.principal(id) ON DELETE RESTRICT,
          updated_at timestamptz NOT NULL,
          PRIMARY KEY (organization_id, project_id, id),
          UNIQUE (organization_id, project_id, classification, id),
          UNIQUE (organization_id, project_id, classification),
          CONSTRAINT ck_reconciliation_schedule_interval CHECK (
            interval_seconds BETWEEN 60 AND 2592000
            AND retention_seconds BETWEEN 3600 AND 31536000
          ),
          CONSTRAINT ck_reconciliation_schedule_lease CHECK (
            (lease_token IS NULL) = (lease_expires_at IS NULL)
            AND (lease_token IS NULL) = (current_run_id IS NULL)
          ),
          CONSTRAINT ck_reconciliation_schedule_failure CHECK (failure_count >= 0),
          CONSTRAINT ck_reconciliation_schedule_time CHECK (updated_at >= created_at)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE artifact.reconciliation_run (
          organization_id uuid NOT NULL,
          project_id uuid NOT NULL,
          classification varchar(64) NOT NULL,
          id uuid NOT NULL,
          schedule_id uuid NOT NULL,
          lease_token uuid NOT NULL,
          state varchar(16) NOT NULL,
          started_at timestamptz NOT NULL,
          finished_at timestamptz,
          artifacts_checked integer,
          pending_recovered integer,
          issues_recorded integer,
          staging_cleaned integer,
          failure_code varchar(100),
          executed_by uuid NOT NULL REFERENCES identity.principal(id) ON DELETE RESTRICT,
          request_id uuid NOT NULL,
          trace_id varchar(255) NOT NULL,
          PRIMARY KEY (organization_id, project_id, id),
          UNIQUE (organization_id, project_id, classification, id),
          FOREIGN KEY (organization_id, project_id, classification, schedule_id)
            REFERENCES artifact.reconciliation_schedule(
              organization_id, project_id, classification, id
            ) ON DELETE RESTRICT,
          CONSTRAINT ck_reconciliation_run_state CHECK (
            state IN ('running', 'succeeded', 'failed', 'timed_out')
          ),
          CONSTRAINT ck_reconciliation_run_terminal CHECK (
            (state = 'running' AND finished_at IS NULL AND failure_code IS NULL)
            OR (state = 'succeeded' AND finished_at IS NOT NULL AND failure_code IS NULL
                AND artifacts_checked >= 0 AND pending_recovered >= 0
                AND issues_recorded >= 0 AND staging_cleaned >= 0)
            OR (state IN ('failed', 'timed_out') AND finished_at IS NOT NULL
                AND failure_code ~ '^[a-z][a-z0-9_.-]{0,99}$')
          )
        )
        """
    )
    op.execute(
        """
        ALTER TABLE artifact.reconciliation_schedule
        ADD CONSTRAINT fk_reconciliation_schedule_current_run
        FOREIGN KEY (organization_id, project_id, classification, current_run_id)
        REFERENCES artifact.reconciliation_run(
          organization_id, project_id, classification, id
        ) DEFERRABLE INITIALLY DEFERRED
        """
    )
    op.execute(
        """
        CREATE TABLE artifact.staging_cleanup (
          organization_id uuid NOT NULL,
          project_id uuid NOT NULL,
          classification varchar(64) NOT NULL,
          pending_artifact_id uuid NOT NULL,
          staging_object_key varchar(1024) NOT NULL,
          cleaned_at timestamptz NOT NULL,
          cleaned_by uuid NOT NULL REFERENCES identity.principal(id) ON DELETE RESTRICT,
          run_id uuid NOT NULL,
          PRIMARY KEY (organization_id, project_id, pending_artifact_id),
          FOREIGN KEY (organization_id, project_id, classification, pending_artifact_id)
            REFERENCES artifact.artifact_pending(
              organization_id, project_id, classification, id
            ) ON DELETE RESTRICT,
          FOREIGN KEY (organization_id, project_id, classification, run_id)
            REFERENCES artifact.reconciliation_run(
              organization_id, project_id, classification, id
            ) ON DELETE RESTRICT
        )
        """
    )
    op.execute(
        "CREATE INDEX ix_reconciliation_schedule_due ON artifact.reconciliation_schedule "
        "(organization_id, project_id, enabled, next_run_at)"
    )
    op.execute(
        "CREATE INDEX ix_reconciliation_run_schedule ON artifact.reconciliation_run "
        "(organization_id, project_id, schedule_id, started_at DESC)"
    )
    op.execute(
        """
        CREATE FUNCTION artifact.guard_reconciliation_run_update()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF TG_OP = 'DELETE' OR OLD.state <> 'running' THEN
            RAISE EXCEPTION USING ERRCODE = '55000',
              MESSAGE = 'terminal reconciliation run is immutable';
          END IF;
          IF (NEW.organization_id, NEW.project_id, NEW.classification, NEW.id,
              NEW.schedule_id, NEW.lease_token, NEW.started_at, NEW.executed_by,
              NEW.request_id, NEW.trace_id) IS DISTINCT FROM
             (OLD.organization_id, OLD.project_id, OLD.classification, OLD.id,
              OLD.schedule_id, OLD.lease_token, OLD.started_at, OLD.executed_by,
              OLD.request_id, OLD.trace_id) THEN
            RAISE EXCEPTION USING ERRCODE = '55000',
              MESSAGE = 'reconciliation run identity is immutable';
          END IF;
          RETURN NEW;
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER artifact_reconciliation_run_guard BEFORE UPDATE OR DELETE "
        "ON artifact.reconciliation_run FOR EACH ROW "
        "EXECUTE FUNCTION artifact.guard_reconciliation_run_update()"
    )
    op.execute(
        "CREATE TRIGGER artifact_staging_cleanup_immutable BEFORE UPDATE OR DELETE "
        "ON artifact.staging_cleanup FOR EACH ROW "
        "EXECUTE FUNCTION revisioning.reject_immutable_row_mutation()"
    )
    op.execute(
        """
        CREATE FUNCTION artifact.guard_staging_cleanup_insert()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF NOT EXISTS (
            SELECT 1 FROM artifact.artifact_pending AS pending
            WHERE pending.organization_id = NEW.organization_id
              AND pending.project_id = NEW.project_id
              AND pending.classification = NEW.classification
              AND pending.id = NEW.pending_artifact_id
              AND pending.state IN ('available', 'rejected')
              AND pending.staging_object_key = NEW.staging_object_key
              AND pending.staging_object_key <> pending.final_object_key
          ) THEN
            RAISE EXCEPTION USING ERRCODE = '23514',
              MESSAGE = 'cleanup receipt requires an exact terminal staging object';
          END IF;
          RETURN NEW;
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER artifact_staging_cleanup_insert_guard BEFORE INSERT "
        "ON artifact.staging_cleanup FOR EACH ROW "
        "EXECUTE FUNCTION artifact.guard_staging_cleanup_insert()"
    )
    op.execute(
        """
        CREATE FUNCTION artifact.reject_reconciliation_schedule_delete()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          RAISE EXCEPTION USING ERRCODE = '55000',
            MESSAGE = 'reconciliation schedule cannot be deleted';
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER artifact_reconciliation_schedule_no_delete BEFORE DELETE "
        "ON artifact.reconciliation_schedule FOR EACH ROW "
        "EXECUTE FUNCTION artifact.reject_reconciliation_schedule_delete()"
    )
    for table in ("reconciliation_schedule", "reconciliation_run", "staging_cleanup"):
        op.execute(f"ALTER TABLE artifact.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE artifact.{table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY {table}_read ON artifact.{table} FOR SELECT USING ("
            "access_control.can_access_row("
            "organization_id, project_id, classification, 'artifact.read'))"
        )
        op.execute(
            f"CREATE POLICY {table}_write ON artifact.{table} FOR ALL USING ("
            "access_control.can_access_row("
            "organization_id, project_id, classification, 'artifact.write')) "
            "WITH CHECK (access_control.can_access_row("
            "organization_id, project_id, classification, 'artifact.write'))"
        )


def downgrade() -> None:
    op.drop_table("staging_cleanup", schema="artifact")
    op.drop_constraint(
        "fk_reconciliation_schedule_current_run",
        "reconciliation_schedule",
        schema="artifact",
        type_="foreignkey",
    )
    op.drop_table("reconciliation_run", schema="artifact")
    op.drop_table("reconciliation_schedule", schema="artifact")
    op.execute("DROP FUNCTION artifact.guard_reconciliation_run_update()")
    op.execute("DROP FUNCTION artifact.guard_staging_cleanup_insert()")
    op.execute("DROP FUNCTION artifact.reject_reconciliation_schedule_delete()")

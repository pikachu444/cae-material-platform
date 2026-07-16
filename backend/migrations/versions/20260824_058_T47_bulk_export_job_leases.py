"""T-47 lease fencing and hard-kill recovery for external Bundle Jobs.

Revision ID: 20260824_058_t47_leases
Revises: 20260823_057_t47_bundle
"""

# ruff: noqa: E501

from __future__ import annotations

from alembic import op

revision = "20260824_058_t47_leases"
down_revision = "20260823_057_t47_bundle"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DROP FUNCTION exporting.guard_bulk_export_job_transition() CASCADE;

        ALTER TABLE exporting.bulk_export_job
          DROP CONSTRAINT ck_exporting_bulk_export_job_terminal,
          ADD COLUMN lease_token uuid,
          ADD COLUMN lease_expires_at timestamptz,
          ADD COLUMN heartbeat_at timestamptz;

        ALTER TABLE exporting.bulk_export_job
          ADD CONSTRAINT ck_exporting_bulk_export_job_lease CHECK (
            (lease_token IS NULL AND lease_expires_at IS NULL AND heartbeat_at IS NULL) OR
            (lease_token IS NOT NULL AND lease_expires_at IS NOT NULL AND heartbeat_at IS NOT NULL AND
             state IN ('running','reconciling') AND started_at IS NOT NULL AND
             heartbeat_at >= started_at AND lease_expires_at > heartbeat_at)
          ),
          ADD CONSTRAINT ck_exporting_bulk_export_job_terminal CHECK (
            (state='queued' AND started_at IS NULL AND completed_at IS NULL AND bundle_id IS NULL AND failure_code IS NULL AND
             lease_token IS NULL) OR
            (state='running' AND started_at IS NOT NULL AND completed_at IS NULL AND bundle_id IS NULL AND failure_code IS NULL) OR
            (state='reconciliation_required' AND started_at IS NOT NULL AND completed_at IS NOT NULL AND bundle_id IS NULL AND
             failure_code='committed_output_pending' AND length(btrim(failure_detail)) BETWEEN 1 AND 1000 AND lease_token IS NULL) OR
            (state='reconciling' AND started_at IS NOT NULL AND completed_at IS NULL AND bundle_id IS NULL AND failure_code IS NULL) OR
            (state='succeeded' AND started_at IS NOT NULL AND completed_at IS NOT NULL AND bundle_id IS NOT NULL AND failure_code IS NULL AND failure_detail IS NULL AND lease_token IS NULL) OR
            (state='failed' AND started_at IS NOT NULL AND completed_at IS NOT NULL AND bundle_id IS NULL AND
             length(btrim(failure_code)) BETWEEN 1 AND 80 AND length(btrim(failure_detail)) BETWEEN 1 AND 1000 AND lease_token IS NULL)
          );

        -- A 057 worker may have died after moving a Job to an active state. Give each such Job a
        -- deterministic, already-expiring bootstrap lease so the first 058 worker reclaims it as
        -- a new attempt instead of leaving it permanently invisible to the claim query.
        UPDATE exporting.bulk_export_job
           SET lease_token=md5(id::text || '-20260824-058-bootstrap')::uuid,
               heartbeat_at=started_at,
               lease_expires_at=GREATEST(
                 started_at + interval '1 microsecond', CURRENT_TIMESTAMP
               )
         WHERE state IN ('running','reconciling') AND lease_token IS NULL;

        CREATE INDEX ix_exporting_bulk_export_job_expired_lease
          ON exporting.bulk_export_job (lease_expires_at, submitted_at, id)
          WHERE state IN ('running','reconciling') AND lease_token IS NOT NULL;

        CREATE FUNCTION exporting.guard_bulk_export_job_transition() RETURNS trigger
        LANGUAGE plpgsql AS $$
        DECLARE
          is_active_self_transition boolean;
          is_heartbeat boolean;
          is_reclaim boolean;
        BEGIN
          IF TG_OP='DELETE' THEN
            RAISE EXCEPTION USING ERRCODE='55000', MESSAGE='Bulk Export Jobs cannot be deleted';
          END IF;
          IF NEW.id<>OLD.id OR NEW.organization_id<>OLD.organization_id OR NEW.project_id<>OLD.project_id OR
             NEW.classification<>OLD.classification OR NEW.selection_id<>OLD.selection_id OR
             NEW.selection_revision_id<>OLD.selection_revision_id OR
             NEW.submitted_at<>OLD.submitted_at OR NEW.submitted_by<>OLD.submitted_by OR
             (OLD.started_at IS NOT NULL AND NEW.started_at IS DISTINCT FROM OLD.started_at) THEN
            RAISE EXCEPTION USING ERRCODE='55000', MESSAGE='Bulk Export Job identity fields are immutable';
          END IF;

          is_active_self_transition := OLD.state=NEW.state AND OLD.state IN ('running','reconciling');
          is_heartbeat := is_active_self_transition AND NEW.attempt_count=OLD.attempt_count AND
            NEW.lease_token IS NOT DISTINCT FROM OLD.lease_token AND NEW.lease_token IS NOT NULL AND
            OLD.lease_expires_at > NEW.heartbeat_at AND
            NEW.heartbeat_at > OLD.heartbeat_at AND NEW.lease_expires_at > OLD.lease_expires_at;
          is_reclaim := is_active_self_transition AND NEW.attempt_count=OLD.attempt_count+1 AND
            NEW.lease_token IS DISTINCT FROM OLD.lease_token AND NEW.lease_token IS NOT NULL AND
            OLD.lease_expires_at IS NOT NULL AND OLD.lease_expires_at <= NEW.heartbeat_at;

          IF NOT (
            (OLD.state='queued' AND NEW.state='running' AND NEW.attempt_count=OLD.attempt_count) OR
            (OLD.state='running' AND NEW.state IN ('reconciliation_required','succeeded','failed') AND NEW.attempt_count=OLD.attempt_count) OR
            (OLD.state='reconciliation_required' AND NEW.state='reconciling' AND NEW.attempt_count=OLD.attempt_count+1) OR
            (OLD.state='reconciling' AND NEW.state IN ('reconciliation_required','succeeded','failed') AND NEW.attempt_count=OLD.attempt_count) OR
            is_heartbeat OR is_reclaim
          ) THEN
            RAISE EXCEPTION USING ERRCODE='55000', MESSAGE='invalid Bulk Export Job state or lease transition';
          END IF;
          RETURN NEW;
        END $$;
        CREATE TRIGGER bulk_export_job_transition_guard BEFORE UPDATE OR DELETE
          ON exporting.bulk_export_job FOR EACH ROW
          EXECUTE FUNCTION exporting.guard_bulk_export_job_transition();
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (
            SELECT 1 FROM exporting.bulk_export_job
             WHERE state IN ('running','reconciling')
          ) THEN
            RAISE EXCEPTION 'cannot downgrade with active leased Bulk Export Jobs';
          END IF;
        END $$;

        DROP FUNCTION exporting.guard_bulk_export_job_transition() CASCADE;
        DROP INDEX exporting.ix_exporting_bulk_export_job_expired_lease;

        ALTER TABLE exporting.bulk_export_job
          DROP CONSTRAINT ck_exporting_bulk_export_job_terminal,
          DROP CONSTRAINT ck_exporting_bulk_export_job_lease,
          DROP COLUMN heartbeat_at,
          DROP COLUMN lease_expires_at,
          DROP COLUMN lease_token;

        ALTER TABLE exporting.bulk_export_job
          ADD CONSTRAINT ck_exporting_bulk_export_job_terminal CHECK (
            (state='queued' AND started_at IS NULL AND completed_at IS NULL AND bundle_id IS NULL AND failure_code IS NULL) OR
            (state='running' AND started_at IS NOT NULL AND completed_at IS NULL AND bundle_id IS NULL AND failure_code IS NULL) OR
            (state='reconciliation_required' AND started_at IS NOT NULL AND completed_at IS NOT NULL AND bundle_id IS NULL AND
             failure_code='committed_output_pending' AND length(btrim(failure_detail)) BETWEEN 1 AND 1000) OR
            (state='reconciling' AND started_at IS NOT NULL AND completed_at IS NULL AND bundle_id IS NULL AND failure_code IS NULL) OR
            (state='succeeded' AND started_at IS NOT NULL AND completed_at IS NOT NULL AND bundle_id IS NOT NULL AND failure_code IS NULL AND failure_detail IS NULL) OR
            (state='failed' AND started_at IS NOT NULL AND completed_at IS NOT NULL AND bundle_id IS NULL AND
             length(btrim(failure_code)) BETWEEN 1 AND 80 AND length(btrim(failure_detail)) BETWEEN 1 AND 1000)
          );

        CREATE FUNCTION exporting.guard_bulk_export_job_transition() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
          IF TG_OP='DELETE' THEN
            RAISE EXCEPTION USING ERRCODE='55000', MESSAGE='Bulk Export Jobs cannot be deleted';
          END IF;
          IF NEW.id<>OLD.id OR NEW.organization_id<>OLD.organization_id OR NEW.project_id<>OLD.project_id OR
             NEW.classification<>OLD.classification OR NEW.selection_id<>OLD.selection_id OR
             NEW.selection_revision_id<>OLD.selection_revision_id OR
             NOT (NEW.attempt_count=OLD.attempt_count OR
                  (OLD.state='reconciliation_required' AND NEW.state='reconciling' AND
                   NEW.attempt_count=OLD.attempt_count+1)) OR
             NEW.submitted_at<>OLD.submitted_at OR NEW.submitted_by<>OLD.submitted_by OR
             (OLD.started_at IS NOT NULL AND NEW.started_at IS DISTINCT FROM OLD.started_at) THEN
            RAISE EXCEPTION USING ERRCODE='55000', MESSAGE='Bulk Export Job identity fields are immutable';
          END IF;
          IF NOT ((OLD.state='queued' AND NEW.state='running') OR
                  (OLD.state='running' AND NEW.state IN ('reconciliation_required','succeeded','failed')) OR
                  (OLD.state='reconciliation_required' AND NEW.state='reconciling') OR
                  (OLD.state='reconciling' AND NEW.state IN ('reconciliation_required','succeeded','failed'))) THEN
            RAISE EXCEPTION USING ERRCODE='55000', MESSAGE='invalid Bulk Export Job state transition';
          END IF;
          RETURN NEW;
        END $$;
        CREATE TRIGGER bulk_export_job_transition_guard BEFORE UPDATE OR DELETE
          ON exporting.bulk_export_job FOR EACH ROW
          EXECUTE FUNCTION exporting.guard_bulk_export_job_transition();
        """
    )

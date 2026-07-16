"""T-47 external Bundle assembly and committed-output reconciliation.

Revision ID: 20260823_057_t47_bundle
Revises: 20260822_056_t45_bulk
"""

# ruff: noqa: E501

from __future__ import annotations

from alembic import op

revision = "20260823_057_t47_bundle"
down_revision = "20260822_056_t45_bulk"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE exporting.bulk_export_job
          DROP CONSTRAINT ck_exporting_bulk_export_job_state,
          DROP CONSTRAINT ck_exporting_bulk_export_job_terminal;

        ALTER TABLE exporting.bulk_export_job
          ADD CONSTRAINT ck_exporting_bulk_export_job_state CHECK
            (state IN ('queued','running','reconciliation_required','reconciling','succeeded','failed')),
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

        DROP FUNCTION exporting.guard_bulk_export_job_transition() CASCADE;
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

        CREATE TABLE exporting.bulk_export_output_commit (
          id uuid NOT NULL, organization_id uuid NOT NULL, project_id uuid NOT NULL,
          classification varchar(64) NOT NULL, job_id uuid NOT NULL,
          selection_revision_id uuid NOT NULL, archive_artifact_id uuid NOT NULL,
          archive_sha256 char(64) NOT NULL, archive_size_bytes bigint NOT NULL,
          manifest_sha256 char(64) NOT NULL, committed_at timestamptz NOT NULL,
          committed_by uuid NOT NULL,
          CONSTRAINT pk_exporting_bulk_export_output_commit PRIMARY KEY
            (organization_id, project_id, id),
          CONSTRAINT uq_exporting_bulk_export_output_commit_job UNIQUE
            (organization_id, project_id, job_id),
          CONSTRAINT uq_exporting_bulk_export_output_commit_scope UNIQUE
            (organization_id, project_id, classification, id),
          CONSTRAINT ck_exporting_bulk_export_output_commit_classification CHECK
            (classification IN ('internal','confidential','restricted','export_controlled')),
          CONSTRAINT ck_exporting_bulk_export_output_commit_digest CHECK
            (archive_sha256 ~ '^[0-9a-f]{64}$' AND manifest_sha256 ~ '^[0-9a-f]{64}$'),
          CONSTRAINT ck_exporting_bulk_export_output_commit_size CHECK
            (archive_size_bytes BETWEEN 1 AND 5368709120),
          CONSTRAINT fk_exporting_bulk_export_output_commit_job FOREIGN KEY
            (organization_id, project_id, classification, job_id) REFERENCES
            exporting.bulk_export_job (organization_id, project_id, classification, id),
          CONSTRAINT fk_exporting_bulk_export_output_commit_selection FOREIGN KEY
            (organization_id, project_id, selection_revision_id) REFERENCES
            exporting.export_selection_revision (organization_id, project_id, id),
          CONSTRAINT fk_exporting_bulk_export_output_commit_artifact FOREIGN KEY
            (organization_id, project_id, classification, archive_artifact_id) REFERENCES
            artifact.artifact (organization_id, project_id, classification, id),
          CONSTRAINT fk_exporting_bulk_export_output_commit_actor FOREIGN KEY (committed_by)
            REFERENCES identity.principal(id)
        );

        CREATE INDEX ix_exporting_bulk_export_output_commit_pending
          ON exporting.bulk_export_output_commit (organization_id, project_id, committed_at, job_id);
        CREATE TRIGGER bulk_export_output_commit_immutable BEFORE UPDATE OR DELETE
          ON exporting.bulk_export_output_commit FOR EACH ROW
          EXECUTE FUNCTION exporting.guard_bulk_export_immutable();

        ALTER TABLE exporting.bulk_export_output_commit ENABLE ROW LEVEL SECURITY;
        ALTER TABLE exporting.bulk_export_output_commit FORCE ROW LEVEL SECURITY;
        CREATE POLICY bulk_export_output_commit_select
          ON exporting.bulk_export_output_commit FOR SELECT
          USING (access_control.can_access_row(
            organization_id, project_id, classification, 'export.read'));
        CREATE POLICY bulk_export_output_commit_insert
          ON exporting.bulk_export_output_commit FOR INSERT
          WITH CHECK (access_control.can_access_row(
            organization_id, project_id, classification, 'export.execute'));
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM exporting.bulk_export_output_commit LIMIT 1)
             OR EXISTS (
               SELECT 1 FROM exporting.bulk_export_job
                WHERE state='reconciliation_required'
             ) THEN
            RAISE EXCEPTION 'cannot downgrade with committed Bundle output evidence';
          END IF;
        END $$;

        DROP TABLE exporting.bulk_export_output_commit;

        ALTER TABLE exporting.bulk_export_job
          DROP CONSTRAINT ck_exporting_bulk_export_job_state,
          DROP CONSTRAINT ck_exporting_bulk_export_job_terminal;
        ALTER TABLE exporting.bulk_export_job
          ADD CONSTRAINT ck_exporting_bulk_export_job_state CHECK
            (state IN ('queued','running','succeeded','failed')),
          ADD CONSTRAINT ck_exporting_bulk_export_job_terminal CHECK (
            (state='queued' AND started_at IS NULL AND completed_at IS NULL AND bundle_id IS NULL AND failure_code IS NULL) OR
            (state='running' AND started_at IS NOT NULL AND completed_at IS NULL AND bundle_id IS NULL AND failure_code IS NULL) OR
            (state='succeeded' AND started_at IS NOT NULL AND completed_at IS NOT NULL AND bundle_id IS NOT NULL AND failure_code IS NULL AND failure_detail IS NULL) OR
            (state='failed' AND started_at IS NOT NULL AND completed_at IS NOT NULL AND bundle_id IS NULL AND
             length(btrim(failure_code)) BETWEEN 1 AND 80 AND length(btrim(failure_detail)) BETWEEN 1 AND 1000)
          );

        DROP FUNCTION exporting.guard_bulk_export_job_transition() CASCADE;
        CREATE FUNCTION exporting.guard_bulk_export_job_transition() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
          IF TG_OP='DELETE' THEN
            RAISE EXCEPTION USING ERRCODE='55000', MESSAGE='Bulk Export Jobs cannot be deleted';
          END IF;
          IF NEW.id<>OLD.id OR NEW.organization_id<>OLD.organization_id OR NEW.project_id<>OLD.project_id OR
             NEW.classification<>OLD.classification OR NEW.selection_id<>OLD.selection_id OR
             NEW.selection_revision_id<>OLD.selection_revision_id OR NEW.attempt_count<>OLD.attempt_count OR
             NEW.submitted_at<>OLD.submitted_at OR NEW.submitted_by<>OLD.submitted_by THEN
            RAISE EXCEPTION USING ERRCODE='55000', MESSAGE='Bulk Export Job identity fields are immutable';
          END IF;
          IF NOT ((OLD.state='queued' AND NEW.state='running') OR
                  (OLD.state='running' AND NEW.state IN ('succeeded','failed'))) THEN
            RAISE EXCEPTION USING ERRCODE='55000', MESSAGE='invalid Bulk Export Job state transition';
          END IF;
          RETURN NEW;
        END $$;
        CREATE TRIGGER bulk_export_job_transition_guard BEFORE UPDATE OR DELETE
          ON exporting.bulk_export_job FOR EACH ROW
          EXECUTE FUNCTION exporting.guard_bulk_export_job_transition();
        """
    )

"""Allow one same-request provenance Activity input finalization.

Revision ID: 20260728_031_p02
Revises: 20260728_030_p02
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260728_031_p02"
down_revision: str | None = "20260728_030_p02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("DROP TRIGGER provenance_activity_immutable ON provenance.activity")
    op.execute(
        """
        CREATE FUNCTION provenance.guard_activity_input_finalization()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF TG_OP = 'DELETE' THEN
            RAISE EXCEPTION USING ERRCODE = '55000',
              MESSAGE = 'provenance Activity rows cannot be deleted';
          END IF;
          IF OLD.input_required OR NOT NEW.input_required
             OR OLD.organization_id IS DISTINCT FROM NEW.organization_id
             OR OLD.project_id IS DISTINCT FROM NEW.project_id
             OR OLD.classification IS DISTINCT FROM NEW.classification
             OR OLD.id IS DISTINCT FROM NEW.id
             OR OLD.activity_type IS DISTINCT FROM NEW.activity_type
             OR OLD.domain_run_type IS DISTINCT FROM NEW.domain_run_type
             OR OLD.domain_run_id IS DISTINCT FROM NEW.domain_run_id
             OR OLD.status IS DISTINCT FROM NEW.status
             OR OLD.output_required IS DISTINCT FROM NEW.output_required
             OR OLD.started_at IS DISTINCT FROM NEW.started_at
             OR OLD.ended_at IS DISTINCT FROM NEW.ended_at
             OR OLD.recorded_at IS DISTINCT FROM NEW.recorded_at
             OR OLD.recorded_by IS DISTINCT FROM NEW.recorded_by
             OR OLD.request_id IS DISTINCT FROM NEW.request_id
             OR OLD.trace_id IS DISTINCT FROM NEW.trace_id
             OR OLD.recorded_by::text IS DISTINCT FROM
                current_setting('cmp.principal_id', true)
             OR OLD.request_id::text IS DISTINCT FROM
                current_setting('cmp.request_id', true) THEN
            RAISE EXCEPTION USING ERRCODE = '55000',
              MESSAGE = 'provenance Activity permits only same-request input finalization';
          END IF;
          RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        "CREATE TRIGGER provenance_activity_immutable "
        "BEFORE UPDATE OR DELETE ON provenance.activity FOR EACH ROW "
        "EXECUTE FUNCTION provenance.guard_activity_input_finalization()"
    )
    op.execute(
        "CREATE POLICY activity_authorized_input_finalization ON provenance.activity "
        "FOR UPDATE USING (access_control.can_access_row(organization_id, project_id, "
        "classification, 'provenance.write') AND recorded_by::text = "
        "current_setting('cmp.principal_id', true) AND request_id::text = "
        "current_setting('cmp.request_id', true)) WITH CHECK "
        "(access_control.can_access_row(organization_id, project_id, classification, "
        "'provenance.write') AND recorded_by::text = current_setting('cmp.principal_id', true) "
        "AND request_id::text = current_setting('cmp.request_id', true))"
    )


def downgrade() -> None:
    op.execute("DROP POLICY activity_authorized_input_finalization ON provenance.activity")
    op.execute(
        "DROP TRIGGER IF EXISTS provenance_activity_input_finalization_guard "
        "ON provenance.activity"
    )
    op.execute("DROP TRIGGER provenance_activity_immutable ON provenance.activity")
    op.execute("DROP FUNCTION provenance.guard_activity_input_finalization()")
    op.execute(
        "CREATE TRIGGER provenance_activity_immutable "
        "BEFORE UPDATE OR DELETE ON provenance.activity FOR EACH ROW "
        "EXECUTE FUNCTION revisioning.reject_immutable_row_mutation()"
    )

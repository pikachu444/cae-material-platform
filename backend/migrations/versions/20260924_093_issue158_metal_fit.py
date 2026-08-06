"""Persist exact-source metal Fit evidence and deterministic Fit runs (Issue #158, task 3B).

The run/attempt tables are intentionally metal-specific.  They retain failed executions and
their reproducibility evidence without turning the common processing schema into a generic EAV
calibration store.
"""

from __future__ import annotations

# Embedded SQL keeps its reviewed statement layout; wrapping it would obscure constraints.
# ruff: noqa: E501
from collections.abc import Sequence

from alembic import op

revision: str = "20260924_093_issue158_metal_fit"
down_revision: str | None = "20260923_092_uxc08"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _rls(table: str) -> None:
    op.execute(f"ALTER TABLE processing.{table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE processing.{table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY processing_{table}_select ON processing.{table} FOR SELECT USING "
        "(access_control.can_access_row(organization_id, project_id, classification, 'processing.read'))"
    )
    op.execute(
        f"CREATE POLICY processing_{table}_insert ON processing.{table} FOR INSERT WITH CHECK "
        "(access_control.can_access_row(organization_id, project_id, classification, 'processing.execute'))"
    )
    op.execute(
        f"CREATE POLICY processing_{table}_update ON processing.{table} FOR UPDATE USING "
        "(access_control.can_access_row(organization_id, project_id, classification, 'processing.execute')) "
        "WITH CHECK (access_control.can_access_row(organization_id, project_id, classification, 'processing.execute'))"
    )


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE processing.common_processing_output_revision
          ADD COLUMN source_processing_output_id uuid,
          ADD COLUMN source_processing_output_revision_id uuid,
          ADD COLUMN source_processing_output_sha256 char(64),
          ADD CONSTRAINT ck_processing_common_output_source_processing_pin CHECK (
            (source_processing_output_id IS NULL AND source_processing_output_revision_id IS NULL
             AND source_processing_output_sha256 IS NULL) OR
            (source_processing_output_id IS NOT NULL AND source_processing_output_revision_id IS NOT NULL
             AND source_processing_output_sha256 ~ '^[0-9a-f]{64}$')
          );
        ALTER TABLE processing.common_processing_output_revision
          ADD CONSTRAINT fk_processing_common_output_source_processing_revision
          FOREIGN KEY (organization_id, project_id, classification,
                       source_processing_output_id, source_processing_output_revision_id)
          REFERENCES processing.common_processing_output_revision
          (organization_id, project_id, classification, aggregate_id, id)
          DEFERRABLE INITIALLY DEFERRED;
        CREATE INDEX ix_processing_common_output_source_processing
          ON processing.common_processing_output_revision
          (organization_id, project_id, source_processing_output_id, source_processing_output_revision_id)
          WHERE source_processing_output_id IS NOT NULL;

        CREATE TABLE processing.metal_fit_run (
          id uuid NOT NULL, organization_id uuid NOT NULL, project_id uuid NOT NULL,
          classification varchar(64) NOT NULL,
          source_processing_output_id uuid NOT NULL,
          source_processing_output_revision_id uuid NOT NULL,
          source_processing_output_sha256 char(64) NOT NULL CHECK (source_processing_output_sha256 ~ '^[0-9a-f]{64}$'),
          source_document_id uuid NOT NULL, source_document_revision_id uuid NOT NULL,
          mapping_profile_id uuid NOT NULL, mapping_profile_revision_id uuid NOT NULL,
          options jsonb NOT NULL CHECK (jsonb_typeof(options)='object'),
          reproducibility_evidence jsonb NOT NULL CHECK (jsonb_typeof(reproducibility_evidence)='object'),
          status varchar(32) NOT NULL CHECK (status IN ('executing','succeeded','failed','cancelled')),
          failure_code varchar(160), failure_reason text,
          started_at timestamptz NOT NULL, ended_at timestamptz,
          created_at timestamptz NOT NULL, created_by uuid NOT NULL,
          request_id uuid NOT NULL, trace_id varchar(255) NOT NULL,
          PRIMARY KEY (organization_id, project_id, id),
          CONSTRAINT uq_processing_metal_fit_run_scope UNIQUE (organization_id, project_id, classification, id),
          CONSTRAINT fk_processing_metal_fit_run_source FOREIGN KEY
            (organization_id, project_id, classification, source_processing_output_id,
             source_processing_output_revision_id)
            REFERENCES processing.common_processing_output_revision
            (organization_id, project_id, classification, aggregate_id, id),
          CONSTRAINT ck_processing_metal_fit_run_failure CHECK (
            (status='executing' AND ended_at IS NULL AND failure_code IS NULL AND failure_reason IS NULL)
            OR (status='succeeded' AND ended_at IS NOT NULL AND failure_code IS NULL AND failure_reason IS NULL)
            OR (status IN ('failed','cancelled') AND ended_at IS NOT NULL AND failure_code IS NOT NULL AND failure_reason IS NOT NULL)
          ),
          CONSTRAINT ck_processing_metal_fit_run_time CHECK (ended_at IS NULL OR ended_at >= started_at),
          CONSTRAINT ck_processing_metal_fit_run_trace CHECK (length(btrim(trace_id)) BETWEEN 1 AND 255),
          CONSTRAINT ck_processing_metal_fit_run_reason CHECK (length(btrim(failure_reason)) <= 2000)
        );

        CREATE TABLE processing.metal_fit_attempt (
          id uuid NOT NULL, organization_id uuid NOT NULL, project_id uuid NOT NULL,
          classification varchar(64) NOT NULL, run_id uuid NOT NULL,
          ordinal integer NOT NULL CHECK (ordinal >= 0), family varchar(64) NOT NULL,
          status varchar(32) NOT NULL CHECK (status IN ('executing','succeeded','failed','cancelled')),
          result jsonb, objective_history jsonb NOT NULL DEFAULT '[]'::jsonb
            CHECK (jsonb_typeof(objective_history)='array'),
          failure_code varchar(160), failure_reason text,
          started_at timestamptz NOT NULL, ended_at timestamptz,
          created_at timestamptz NOT NULL, created_by uuid NOT NULL,
          PRIMARY KEY (organization_id, project_id, id),
          CONSTRAINT uq_processing_metal_fit_attempt_ordinal UNIQUE (organization_id, project_id, run_id, ordinal),
          CONSTRAINT fk_processing_metal_fit_attempt_run FOREIGN KEY
            (organization_id, project_id, classification, run_id)
            REFERENCES processing.metal_fit_run (organization_id, project_id, classification, id),
          CONSTRAINT ck_processing_metal_fit_attempt_result CHECK (
            (status='executing' AND result IS NULL AND failure_code IS NULL AND failure_reason IS NULL AND ended_at IS NULL) OR
            (status='succeeded' AND result IS NOT NULL AND jsonb_typeof(result)='object' AND failure_code IS NULL AND failure_reason IS NULL AND ended_at IS NOT NULL) OR
            (status IN ('failed','cancelled') AND failure_code IS NOT NULL AND failure_reason IS NOT NULL AND ended_at IS NOT NULL)
          ),
          CONSTRAINT ck_processing_metal_fit_attempt_time CHECK (ended_at IS NULL OR ended_at >= started_at)
        );
        """
    )
    _rls("metal_fit_run")
    _rls("metal_fit_attempt")
    op.execute(
        """
        CREATE FUNCTION processing.guard_metal_fit_run_transition()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF TG_OP = 'DELETE' OR OLD.status <> 'executing'
             OR NEW.status NOT IN ('succeeded','failed','cancelled')
             OR NEW.id IS DISTINCT FROM OLD.id
             OR NEW.organization_id IS DISTINCT FROM OLD.organization_id
             OR NEW.project_id IS DISTINCT FROM OLD.project_id
             OR NEW.classification IS DISTINCT FROM OLD.classification
             OR NEW.source_processing_output_id IS DISTINCT FROM OLD.source_processing_output_id
             OR NEW.source_processing_output_revision_id IS DISTINCT FROM OLD.source_processing_output_revision_id
             OR NEW.source_processing_output_sha256 IS DISTINCT FROM OLD.source_processing_output_sha256
             OR NEW.source_document_id IS DISTINCT FROM OLD.source_document_id
             OR NEW.source_document_revision_id IS DISTINCT FROM OLD.source_document_revision_id
             OR NEW.mapping_profile_id IS DISTINCT FROM OLD.mapping_profile_id
             OR NEW.mapping_profile_revision_id IS DISTINCT FROM OLD.mapping_profile_revision_id
             OR NEW.options IS DISTINCT FROM OLD.options
             OR NEW.started_at IS DISTINCT FROM OLD.started_at
             OR NEW.created_at IS DISTINCT FROM OLD.created_at
             OR NEW.created_by IS DISTINCT FROM OLD.created_by
             OR NEW.request_id IS DISTINCT FROM OLD.request_id
             OR NEW.trace_id IS DISTINCT FROM OLD.trace_id THEN
            RAISE EXCEPTION USING ERRCODE='55000',
              MESSAGE='terminal metal Fit runs are immutable and transition only once';
          END IF;
          RETURN NEW;
        END;
        $$;
        CREATE FUNCTION processing.guard_metal_fit_attempt_transition()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF TG_OP = 'DELETE' OR OLD.status <> 'executing'
             OR NEW.status NOT IN ('succeeded','failed','cancelled')
             OR NEW.id IS DISTINCT FROM OLD.id
             OR NEW.organization_id IS DISTINCT FROM OLD.organization_id
             OR NEW.project_id IS DISTINCT FROM OLD.project_id
             OR NEW.classification IS DISTINCT FROM OLD.classification
             OR NEW.run_id IS DISTINCT FROM OLD.run_id
             OR NEW.ordinal IS DISTINCT FROM OLD.ordinal
             OR NEW.family IS DISTINCT FROM OLD.family
             OR NEW.started_at IS DISTINCT FROM OLD.started_at
             OR NEW.created_at IS DISTINCT FROM OLD.created_at
             OR NEW.created_by IS DISTINCT FROM OLD.created_by THEN
            RAISE EXCEPTION USING ERRCODE='55000',
              MESSAGE='terminal metal Fit attempts are immutable and transition only once';
          END IF;
          RETURN NEW;
        END;
        $$;
        CREATE TRIGGER metal_fit_run_transition_guard
          BEFORE UPDATE OR DELETE ON processing.metal_fit_run
          FOR EACH ROW EXECUTE FUNCTION processing.guard_metal_fit_run_transition();
        CREATE TRIGGER metal_fit_attempt_transition_guard
          BEFORE UPDATE OR DELETE ON processing.metal_fit_attempt
          FOR EACH ROW EXECUTE FUNCTION processing.guard_metal_fit_attempt_transition();
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP TRIGGER IF EXISTS metal_fit_attempt_transition_guard ON processing.metal_fit_attempt;
        DROP TRIGGER IF EXISTS metal_fit_run_transition_guard ON processing.metal_fit_run;
        DROP FUNCTION IF EXISTS processing.guard_metal_fit_attempt_transition();
        DROP FUNCTION IF EXISTS processing.guard_metal_fit_run_transition();
        """
    )
    op.execute("DROP TABLE processing.metal_fit_attempt")
    op.execute("DROP TABLE processing.metal_fit_run")
    op.execute(
        "ALTER TABLE processing.common_processing_output_revision "
        "DROP CONSTRAINT IF EXISTS fk_processing_common_output_source_processing_revision"
    )
    op.execute("DROP INDEX IF EXISTS processing.ix_processing_common_output_source_processing")
    op.execute(
        "ALTER TABLE processing.common_processing_output_revision "
        "DROP CONSTRAINT ck_processing_common_output_source_processing_pin, "
        "DROP COLUMN source_processing_output_sha256, "
        "DROP COLUMN source_processing_output_revision_id, "
        "DROP COLUMN source_processing_output_id"
    )

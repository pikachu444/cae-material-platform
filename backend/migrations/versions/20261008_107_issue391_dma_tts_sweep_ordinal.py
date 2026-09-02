"""Issue #391: preserve the source DMA sweep identity in governed imports.

This migration is deliberately limited to replacing the existing channel checks.  It does not
rewrite a row, move a current pointer, or mutate an Artifact/content revision.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20261008_107_dma_tts_sweep"
down_revision: str | None = "20261007_106_lve_plan_governance"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_SOURCE_QUANTITIES = (
    "'engineering_strain','engineering_stress','shear_strain','shear_stress',"
    "'time','shear_modulus','displacement','force','temperature','frequency',"
    "'storage_modulus','loss_modulus','tan_delta','minor_strain','major_strain',"
    "'source_sweep_ordinal'"
)
_SOURCE_QUANTITIES_PREVIOUS = (
    "'engineering_strain','engineering_stress','shear_strain','shear_stress',"
    "'time','shear_modulus','displacement','force','temperature','frequency',"
    "'storage_modulus','loss_modulus','tan_delta','minor_strain','major_strain'"
)


def upgrade() -> None:
    op.execute(
        f"""
        ALTER TABLE datasets.import_profile_channel
          DROP CONSTRAINT import_profile_channel_ordinal_check,
          DROP CONSTRAINT import_profile_channel_source_quantity_check,
          DROP CONSTRAINT import_profile_channel_axis_role_check,
          ADD CONSTRAINT import_profile_channel_ordinal_check CHECK (ordinal BETWEEN 0 AND 5),
          ADD CONSTRAINT import_profile_channel_source_quantity_check CHECK
            (source_quantity IN ({_SOURCE_QUANTITIES})),
          ADD CONSTRAINT import_profile_channel_axis_role_check CHECK
            (axis_role IN ('independent','dependent','auxiliary'));
        ALTER TABLE datasets.governed_dataset_channel
          DROP CONSTRAINT governed_dataset_channel_ordinal_check,
          ADD CONSTRAINT governed_dataset_channel_ordinal_check
            CHECK (ordinal BETWEEN 0 AND 5);
        """
    )
    # A revision is first written through the ordinary revision hook.  Existing
    # Dataset/Statistics specializers then refine that same-request Activity,
    # while DMA specializes a Common Processing Output after its two output
    # Artifacts are promoted and before the audit hook runs.  Preserve the general
    # semantic-specialization allowance from migration 032, with a separate exact
    # DMA branch; all request/actor/timestamp facts remain immutable.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION provenance.guard_activity_input_finalization()
        RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE
          general_semantic_specialization boolean;
          dma_semantic_specialization boolean;
        BEGIN
          IF TG_OP = 'DELETE' THEN
            RAISE EXCEPTION USING ERRCODE = '55000',
              MESSAGE = 'provenance Activity rows cannot be deleted';
          END IF;
          general_semantic_specialization :=
            OLD.activity_type = 'core.revision_commit'
            AND NEW.activity_type ~ '^(processing|statistics)\\.'
            AND NEW.activity_type <> 'processing.dma_frequency_master_curve'
            AND NEW.domain_run_type IS NOT NULL
            AND NEW.domain_run_id IS NOT NULL;
          dma_semantic_specialization :=
            OLD.activity_type = 'core.revision_commit'
            AND NEW.activity_type = 'processing.dma_frequency_master_curve'
            AND NEW.domain_run_type = 'processing.common_processing_output'
            AND NEW.domain_run_id IS NOT NULL;
          IF OLD.input_required OR NOT NEW.input_required
             OR OLD.organization_id IS DISTINCT FROM NEW.organization_id
             OR OLD.project_id IS DISTINCT FROM NEW.project_id
             OR OLD.classification IS DISTINCT FROM NEW.classification
             OR OLD.id IS DISTINCT FROM NEW.id
             OR (OLD.activity_type IS DISTINCT FROM NEW.activity_type
                 AND NOT (general_semantic_specialization OR dma_semantic_specialization))
             OR (OLD.domain_run_type IS DISTINCT FROM NEW.domain_run_type
                 AND NOT (general_semantic_specialization OR dma_semantic_specialization))
             OR (OLD.domain_run_id IS DISTINCT FROM NEW.domain_run_id
                 AND NOT (general_semantic_specialization OR dma_semantic_specialization))
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
              MESSAGE = 'provenance Activity permits only same-request DMA finalization';
          END IF;
          RETURN NEW;
        END;
        $$
        """
    )


def downgrade() -> None:
    # The old schema cannot represent the new identity or auxiliary role.  Refuse to hide
    # evidence before restoring only the checks that existed before this revision.
    op.execute(
        """
        DO $$ BEGIN
          IF EXISTS (
            SELECT 1 FROM provenance.activity
            WHERE activity_type = 'processing.dma_frequency_master_curve'
               OR domain_run_type = 'processing.common_processing_output'
          ) THEN
            RAISE EXCEPTION
              'cannot downgrade DMA Activity finalization while immutable DMA provenance exists';
          END IF;
        END $$;
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION provenance.guard_activity_input_finalization()
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
        """
        DO $$ BEGIN
          IF EXISTS (
            SELECT 1 FROM datasets.import_profile_channel
            WHERE ordinal = 5 OR source_quantity = 'source_sweep_ordinal'
              OR axis_role = 'auxiliary'
          ) OR EXISTS (
            SELECT 1 FROM datasets.governed_dataset_channel
            WHERE ordinal = 5 OR source_quantity = 'source_sweep_ordinal'
              OR axis_role = 'auxiliary'
          ) THEN
            RAISE EXCEPTION
              'cannot downgrade DMA sweep identity while ordinal, source quantity, or '
              'auxiliary data exist';
          END IF;
        END $$;
        """
    )
    op.execute(
        f"""
        ALTER TABLE datasets.governed_dataset_channel
          DROP CONSTRAINT governed_dataset_channel_ordinal_check,
          ADD CONSTRAINT governed_dataset_channel_ordinal_check
            CHECK (ordinal BETWEEN 0 AND 4);
        ALTER TABLE datasets.import_profile_channel
          DROP CONSTRAINT import_profile_channel_axis_role_check,
          DROP CONSTRAINT import_profile_channel_source_quantity_check,
          DROP CONSTRAINT import_profile_channel_ordinal_check,
          ADD CONSTRAINT import_profile_channel_ordinal_check CHECK (ordinal BETWEEN 0 AND 4),
          ADD CONSTRAINT import_profile_channel_source_quantity_check CHECK
            (source_quantity IN ({_SOURCE_QUANTITIES_PREVIOUS})),
          ADD CONSTRAINT import_profile_channel_axis_role_check CHECK
            (axis_role IN ('independent','dependent'));
        """
    )

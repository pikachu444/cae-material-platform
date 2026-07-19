"""Allow exact DMA Prony outputs to satisfy the linear-viscoelastic evidence trigger.

Revision ID: 20260918_083_t89_dma_prony
Revises: 20260917_082_t76_current_binding

Traceability: T-89.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260918_083_t89_dma_prony"
down_revision: str | None = "20260917_082_t76_current_binding"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _validation_function(allowed_methods: str) -> str:
    return f"""
    CREATE OR REPLACE FUNCTION modeling.validate_linear_prony_processing_evidence()
    RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE summary record; DECLARE evidence record;
    DECLARE output_row record; DECLARE final_step record;
    DECLARE evidence_count integer;
    BEGIN
      SELECT * INTO summary FROM modeling.linear_viscoelastic_revision
      WHERE organization_id=NEW.organization_id AND project_id=NEW.project_id
        AND material_model_revision_id=NEW.material_model_revision_id;
      SELECT count(*) INTO evidence_count
      FROM modeling.linear_viscoelastic_processing_evidence
      WHERE organization_id=NEW.organization_id AND project_id=NEW.project_id
        AND material_model_revision_id=NEW.material_model_revision_id;
      IF summary.promotion_kind='processing_output' THEN
        SELECT * INTO evidence
        FROM modeling.linear_viscoelastic_processing_evidence
        WHERE organization_id=NEW.organization_id AND project_id=NEW.project_id
          AND material_model_revision_id=NEW.material_model_revision_id;
        SELECT * INTO output_row FROM processing.common_processing_output_revision
        WHERE organization_id=NEW.organization_id AND project_id=NEW.project_id
          AND classification=NEW.classification
          AND aggregate_id=evidence.processing_output_id
          AND id=evidence.processing_output_revision_id;
        SELECT * INTO final_step FROM processing.common_processing_output_step
        WHERE organization_id=NEW.organization_id AND project_id=NEW.project_id
          AND classification=NEW.classification
          AND output_id=evidence.processing_output_id
          AND output_revision_id=evidence.processing_output_revision_id
          AND ordinal=output_row.step_count-1;
        IF evidence_count <> 1 OR output_row.output_sha256 IS DISTINCT FROM
             evidence.processing_output_sha256
           OR output_row.source_document_id IS DISTINCT FROM evidence.source_test_data_id
           OR output_row.source_document_revision_id IS DISTINCT FROM
             evidence.source_test_data_revision_id
           OR output_row.mapping_profile_id IS DISTINCT FROM evidence.mapping_profile_id
           OR output_row.mapping_profile_revision_id IS DISTINCT FROM
             evidence.mapping_profile_revision_id
           OR final_step.method_id NOT IN ({allowed_methods})
           OR final_step.method_version IS DISTINCT FROM '1.0.0'
           OR summary.term_count IS DISTINCT FROM evidence.selected_term_count THEN
          RAISE EXCEPTION 'linear Prony IR differs from exact Processing Output evidence'
            USING ERRCODE='23514';
        END IF;
      ELSIF evidence_count <> 0 THEN
        RAISE EXCEPTION 'non-processing linear Prony revision has Processing evidence'
          USING ERRCODE='23514';
      END IF;
      RETURN NEW;
    END $$;
    """


def upgrade() -> None:
    op.execute(_validation_function("'polymer.prony_fit_compare', 'polymer.dma_prony_fit_compare'"))


def downgrade() -> None:
    op.execute(
        """
        DO $$ BEGIN
          IF EXISTS (
            SELECT 1
            FROM modeling.linear_viscoelastic_processing_evidence e
            JOIN processing.common_processing_output_revision r
              ON r.organization_id=e.organization_id
             AND r.project_id=e.project_id
             AND r.classification=e.classification
             AND r.aggregate_id=e.processing_output_id
             AND r.id=e.processing_output_revision_id
            JOIN processing.common_processing_output_step s
              ON s.organization_id=r.organization_id
             AND s.project_id=r.project_id
             AND s.classification=r.classification
             AND s.output_id=r.aggregate_id
             AND s.output_revision_id=r.id
             AND s.ordinal=r.step_count-1
            WHERE s.method_id='polymer.dma_prony_fit_compare'
          ) THEN
            RAISE EXCEPTION 'cannot downgrade while immutable DMA Prony evidence exists';
          END IF;
        END $$;
        """
    )
    op.execute(_validation_function("'polymer.prony_fit_compare'"))

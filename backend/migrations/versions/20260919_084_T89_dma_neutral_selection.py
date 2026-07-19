"""Represent joint DMA storage/loss selection in Neutral Material evidence.

Revision ID: 20260919_084_t89_dma_neutral
Revises: 20260918_083_t89_dma_prony

Traceability: T-89.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260919_084_t89_dma_neutral"
down_revision: str | None = "20260918_083_t89_dma_prony"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _selection_constraint(allowed_series: str) -> str:
    return f"""
    ALTER TABLE modeling.neutral_material_revision
      DROP CONSTRAINT ck_modeling_neutral_material_selection_kind,
      ADD CONSTRAINT ck_modeling_neutral_material_selection_kind CHECK
      ((selection_kind='candidate' AND calibration_run_id IS NOT NULL AND
        family_candidate_id IS NOT NULL AND candidate_sha256 IS NOT NULL AND
        diagnostics_artifact_id IS NOT NULL AND diagnostics_sha256 IS NOT NULL AND
        processing_output_id IS NULL AND processing_output_revision_id IS NULL AND
        processing_output_sha256 IS NULL AND prony_selection_mode IS NULL) OR
       (selection_kind='processing_output' AND calibration_run_id IS NULL AND
        family_candidate_id IS NULL AND candidate_sha256 IS NULL AND
        diagnostics_artifact_id IS NULL AND diagnostics_sha256 IS NULL AND
        processing_output_id IS NOT NULL AND processing_output_revision_id IS NOT NULL AND
        processing_output_sha256 IS NOT NULL AND prony_selection_mode IS NULL) OR
       (selection_kind='prony_processing_output' AND model_family='generalized_maxwell' AND
        calibration_run_id IS NULL AND family_candidate_id IS NULL AND
        candidate_sha256 IS NULL AND diagnostics_artifact_id IS NULL AND
        diagnostics_sha256 IS NULL AND processing_output_id IS NOT NULL AND
        processing_output_revision_id IS NOT NULL AND processing_output_sha256 IS NOT NULL AND
        selected_series IN ({allowed_series}) AND candidate_families IS NULL AND
        primary_family IS NULL AND secondary_family IS NULL AND primary_weight IS NULL AND
        prony_selection_mode IN ('automatic_bic','manual') AND
        prony_selected_term_count BETWEEN 1 AND 10 AND
        prony_normalized_rmse >= 0 AND prony_normalized_rmse < 'Infinity'::float8 AND
        prony_bic > '-Infinity'::float8 AND prony_bic < 'Infinity'::float8 AND
        prony_fitted_g0_pa > 0 AND prony_catalog_g0_pa > 0 AND
        prony_relative_mismatch >= 0 AND
        prony_relative_mismatch <= prony_acknowledged_max_mismatch AND
        prony_acknowledged_max_mismatch BETWEEN 0 AND 1));
    """


def upgrade() -> None:
    op.execute(
        _selection_constraint(
            "'modulus.prony.selected', 'modulus.storage.prony.selected+modulus.loss.prony.selected'"
        )
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$ BEGIN
          IF EXISTS (
            SELECT 1 FROM modeling.neutral_material_revision
            WHERE selected_series=
              'modulus.storage.prony.selected+modulus.loss.prony.selected'
          ) THEN
            RAISE EXCEPTION 'cannot downgrade while immutable DMA Neutral evidence exists';
          END IF;
        END $$;
        """
    )
    op.execute(_selection_constraint("'modulus.prony.selected'"))

"""Add explicit Arrhenius master-curve shift evidence.

Revision ID: 20260903_068_t55p_arrhenius
Revises: 20260902_067_t55m_projection

Traceability: T-55P.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260903_068_t55p_arrhenius"
down_revision: str | None = "20260902_067_t55m_projection"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _replace_constraints(*, include_arrhenius: bool) -> None:
    shift_methods = "'manual','wlf_fit'"
    shift_sources = "'reference','manual','wlf_fit'"
    if include_arrhenius:
        shift_methods += ",'arrhenius_fit'"
        shift_sources += ",'arrhenius_fit'"
    op.execute(
        "ALTER TABLE processing.viscoelastic_master_plan_revision "
        "DROP CONSTRAINT ck_processing_viscoelastic_master_plan_revision"
    )
    op.execute(
        f"""
        ALTER TABLE processing.viscoelastic_master_plan_revision
          ADD CONSTRAINT ck_processing_viscoelastic_master_plan_revision CHECK
          (revision_no > 0 AND content_hash ~ '^[0-9a-f]{{64}}$' AND
           length(btrim(plan_label)) BETWEEN 1 AND 160 AND
           length(btrim(change_reason)) BETWEEN 1 AND 2000 AND
           reference_temperature_k > 0 AND grid_point_count BETWEEN 3 AND 501 AND
           shift_method IN ({shift_methods}) AND
           interpolation='piecewise_linear_log_time' AND
           domain_policy='common_intersection_no_extrapolation' AND
           reduced_time_convention='time_divided_by_a_t')
        """
    )
    op.execute(
        "ALTER TABLE processing.viscoelastic_master_shift_factor "
        "DROP CONSTRAINT ck_processing_viscoelastic_master_shift_factor"
    )
    op.execute(
        f"""
        ALTER TABLE processing.viscoelastic_master_shift_factor
          ADD CONSTRAINT ck_processing_viscoelastic_master_shift_factor CHECK
          (ordinal BETWEEN 0 AND 49 AND temperature_k > 0 AND
           log10_a_t BETWEEN -20 AND 20 AND source IN ({shift_sources}) AND
           (alignment_rmse_pa IS NULL OR alignment_rmse_pa >= 0))
        """
    )


def upgrade() -> None:
    _replace_constraints(include_arrhenius=True)
    op.execute(
        """
        ALTER TABLE processing.viscoelastic_master_run
          ADD COLUMN arrhenius_activation_energy_j_per_mol double precision,
          ADD CONSTRAINT ck_processing_viscoelastic_master_run_arrhenius CHECK
          (arrhenius_activation_energy_j_per_mol IS NULL OR
           arrhenius_activation_energy_j_per_mol > 0)
        """
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE processing.viscoelastic_master_run "
        "DROP CONSTRAINT ck_processing_viscoelastic_master_run_arrhenius, "
        "DROP COLUMN arrhenius_activation_energy_j_per_mol"
    )
    _replace_constraints(include_arrhenius=False)

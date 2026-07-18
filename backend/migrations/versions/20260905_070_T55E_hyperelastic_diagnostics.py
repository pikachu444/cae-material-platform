"""Pin immutable diagnostics Artifacts to hyperelastic family Candidates.

Revision ID: 20260905_070_t55e_diagnostics
Revises: 20260904_069_t55e_families

Traceability: T-55E.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260905_070_t55e_diagnostics"
down_revision: str | None = "20260904_069_t55e_families"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE modeling.hyperelastic_family_candidate
          ADD COLUMN diagnostics_artifact_id uuid,
          ADD COLUMN diagnostics_sha256 char(64),
          ADD COLUMN diagnostics_point_count integer NOT NULL DEFAULT 0;
        ALTER TABLE modeling.hyperelastic_family_candidate
          ALTER COLUMN diagnostics_point_count DROP DEFAULT,
          ADD CONSTRAINT ck_modeling_hyperelastic_family_candidate_diagnostics CHECK
            ((diagnostics_artifact_id IS NULL AND diagnostics_sha256 IS NULL AND
              diagnostics_point_count=0) OR
             (diagnostics_artifact_id IS NOT NULL AND
              diagnostics_sha256 ~ '^[0-9a-f]{64}$' AND
              diagnostics_point_count BETWEEN 5 AND 1200000)),
          ADD CONSTRAINT fk_modeling_hyperelastic_family_candidate_diagnostics FOREIGN KEY
            (organization_id, project_id, classification, diagnostics_artifact_id) REFERENCES
            artifact.artifact (organization_id, project_id, classification, id)
            ON DELETE RESTRICT;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE modeling.hyperelastic_family_candidate
          DROP CONSTRAINT fk_modeling_hyperelastic_family_candidate_diagnostics,
          DROP CONSTRAINT ck_modeling_hyperelastic_family_candidate_diagnostics,
          DROP COLUMN diagnostics_point_count,
          DROP COLUMN diagnostics_sha256,
          DROP COLUMN diagnostics_artifact_id;
        """
    )

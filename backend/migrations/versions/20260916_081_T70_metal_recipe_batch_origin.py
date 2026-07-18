"""Pin the exact Recipe and successful Batch attempt behind promoted metal Output.

Revision ID: 20260916_081_t70_metal_origin
Revises: 20260915_080_t69_origin

Traceability: ADR-0033, T-70.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260916_081_t70_metal_origin"
down_revision: str | None = "20260915_080_t69_origin"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_FAMILY_DIGESTS = (
    (
        "urn:cmp:reference:isotropic-linear-elasticity:1.0.0",
        "a4e39b23b5d656abb50399b1ae76b799e01872f4f6ebe44a59bc8c901b622cd6",
    ),
    (
        "urn:cmp:reference:isotropic-tabulated-plasticity:1.0.0",
        "18fd736897f26e6472443a5acf50bf899f8eb8f510ae0eca80dada81047a706f",
    ),
    (
        "urn:cmp:reference:isotropic-tabulated-plasticity:1.1.0",
        "60174f00940a5e371613f941649a61af20714b5664b8b95672e34e1a718251bd",
    ),
    (
        "urn:cmp:reference:isotropic-tabulated-plasticity:1.2.0",
        "60f4a0806126ccf7c918f664a97b4d49da593f1da9dacab4a843987b34a0c62f",
    ),
    (
        "urn:cmp:reference:isotropic-linear-viscoelastic-prony:1.0.0",
        "84f948444441bf8ead0c3e3a067d78a68335f2160c6d8d5c59348250ff492353",
    ),
    (
        "urn:cmp:reference:ogden-prony-hyperviscoelastic:1.0.0",
        "545ef081fd6b702d99710aa2ba1a253d0ef6961b8084647d157fac03cca29f2f",
    ),
    (
        "urn:cmp:reference:isotropic-linear-viscoelastic-prony:1.0.0",
        "16c70b294290c62d97e7eb42c5af56a4663af19c2b2e139d2fee898f1802889e",
    ),
    (
        "urn:cmp:reference:isotropic-linear-viscoelastic-prony:1.0.0",
        "705e6ca117a42552727b50fb7c0999bb22e4a13c1f1a31ec4afd10d10c248732",
    ),
)
_METAL_RECIPE_DIGEST = "e99bdd86790a81d2afeca9865bea3747fe5e2ab3001056c1079e7f49f7e16fc5"


def _family_constraint(*, include_metal_recipe: bool) -> str:
    values = list(_FAMILY_DIGESTS)
    if include_metal_recipe:
        values.append(
            ("urn:cmp:reference:isotropic-tabulated-plasticity:1.2.0", _METAL_RECIPE_DIGEST)
        )
    return " OR ".join(
        f"(model_family_id='{family}' AND model_schema_digest='{digest}')"
        for family, digest in values
    )


def upgrade() -> None:
    op.execute(
        "ALTER TABLE modeling.material_model_revision "
        "DROP CONSTRAINT ck_modeling_material_model_family_digest, "
        "ADD CONSTRAINT ck_modeling_material_model_family_digest CHECK ("
        + _family_constraint(include_metal_recipe=True)
        + ")"
    )
    op.execute(
        """
        ALTER TABLE modeling.material_model_revision
          ADD COLUMN processing_recipe_id uuid,
          ADD COLUMN processing_recipe_revision_id uuid,
          ADD COLUMN processing_recipe_sha256 char(64) COLLATE "C",
          ADD COLUMN processing_batch_id uuid,
          ADD COLUMN processing_batch_member_id uuid,
          ADD COLUMN processing_batch_attempt_id uuid,
          ADD COLUMN processing_batch_attempt_no integer,
          ADD CONSTRAINT ck_modeling_metal_recipe_batch_all_or_none CHECK (
            (processing_recipe_id IS NULL AND processing_recipe_revision_id IS NULL AND
             processing_recipe_sha256 IS NULL AND processing_batch_id IS NULL AND
             processing_batch_member_id IS NULL AND processing_batch_attempt_id IS NULL AND
             processing_batch_attempt_no IS NULL)
            OR
            (processing_recipe_id IS NOT NULL AND processing_recipe_revision_id IS NOT NULL AND
             processing_recipe_sha256 ~ '^[0-9a-f]{64}$' AND
             processing_batch_id IS NOT NULL AND processing_batch_member_id IS NOT NULL AND
             processing_batch_attempt_id IS NOT NULL AND processing_batch_attempt_no >= 1 AND
             model_schema_digest =
             'e99bdd86790a81d2afeca9865bea3747fe5e2ab3001056c1079e7f49f7e16fc5')
          ),
          ADD CONSTRAINT fk_modeling_metal_recipe_exact FOREIGN KEY
            (organization_id, project_id, classification, processing_recipe_id,
             processing_recipe_revision_id) REFERENCES
            processing.common_processing_recipe_revision
            (organization_id, project_id, classification, aggregate_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          ADD CONSTRAINT fk_modeling_metal_batch_exact FOREIGN KEY
            (organization_id, project_id, classification, processing_batch_id) REFERENCES
            processing.common_processing_batch
            (organization_id, project_id, classification, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          ADD CONSTRAINT fk_modeling_metal_batch_member_exact FOREIGN KEY
            (organization_id, project_id, classification, processing_batch_id,
             processing_batch_member_id) REFERENCES processing.common_processing_batch_member
            (organization_id, project_id, classification, batch_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          ADD CONSTRAINT fk_modeling_metal_batch_attempt_exact FOREIGN KEY
            (organization_id, project_id, processing_batch_attempt_id) REFERENCES
            processing.common_processing_batch_attempt (organization_id, project_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED;
        CREATE INDEX ix_mdl_metal_processing_recipe ON modeling.material_model_revision
          (organization_id, project_id, processing_recipe_revision_id)
          WHERE processing_recipe_revision_id IS NOT NULL;

        CREATE FUNCTION modeling.validate_metal_recipe_batch_origin()
        RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE origin record;
        BEGIN
          IF NEW.processing_recipe_id IS NULL THEN RETURN NEW; END IF;
          IF NEW.model_family_id IS DISTINCT FROM
             'urn:cmp:reference:isotropic-tabulated-plasticity:1.2.0' THEN
            RAISE EXCEPTION 'Recipe/Batch evidence is restricted to processed metal IR'
              USING ERRCODE='23514';
          END IF;
          SELECT b.recipe_id, b.recipe_revision_id, b.recipe_sha256,
                 a.batch_id, a.member_id, a.id AS attempt_id, a.attempt_no,
                 a.status, a.output_id, a.output_revision_id
            INTO origin
            FROM processing.common_processing_batch_attempt a
            JOIN processing.common_processing_batch b
              ON b.organization_id=a.organization_id AND b.project_id=a.project_id
             AND b.classification=a.classification AND b.id=a.batch_id
           WHERE a.organization_id=NEW.organization_id
             AND a.project_id=NEW.project_id AND a.classification=NEW.classification
             AND a.id=NEW.processing_batch_attempt_id;
          IF origin.recipe_id IS DISTINCT FROM NEW.processing_recipe_id OR
             origin.recipe_revision_id IS DISTINCT FROM NEW.processing_recipe_revision_id OR
             origin.recipe_sha256 IS DISTINCT FROM NEW.processing_recipe_sha256 OR
             origin.batch_id IS DISTINCT FROM NEW.processing_batch_id OR
             origin.member_id IS DISTINCT FROM NEW.processing_batch_member_id OR
             origin.attempt_id IS DISTINCT FROM NEW.processing_batch_attempt_id OR
             origin.attempt_no IS DISTINCT FROM NEW.processing_batch_attempt_no OR
             origin.status IS DISTINCT FROM 'succeeded' OR
             origin.output_id IS DISTINCT FROM NEW.processing_output_id OR
             origin.output_revision_id IS DISTINCT FROM NEW.processing_output_revision_id THEN
            RAISE EXCEPTION 'metal IR differs from exact Recipe/Batch execution origin'
              USING ERRCODE='23514';
          END IF;
          RETURN NEW;
        END $$;
        CREATE CONSTRAINT TRIGGER modeling_metal_recipe_batch_origin_validate
          AFTER INSERT ON modeling.material_model_revision
          DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
          EXECUTE FUNCTION modeling.validate_metal_recipe_batch_origin();
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$ BEGIN
          IF EXISTS (SELECT 1 FROM modeling.material_model_revision
                     WHERE processing_recipe_id IS NOT NULL) THEN
            RAISE EXCEPTION 'cannot downgrade while immutable metal Recipe/Batch evidence exists';
          END IF;
        END $$;
        DROP TRIGGER modeling_metal_recipe_batch_origin_validate
          ON modeling.material_model_revision;
        DROP FUNCTION modeling.validate_metal_recipe_batch_origin();
        DROP INDEX modeling.ix_mdl_metal_processing_recipe;
        ALTER TABLE modeling.material_model_revision
          DROP CONSTRAINT fk_modeling_metal_batch_attempt_exact,
          DROP CONSTRAINT fk_modeling_metal_batch_member_exact,
          DROP CONSTRAINT fk_modeling_metal_batch_exact,
          DROP CONSTRAINT fk_modeling_metal_recipe_exact,
          DROP CONSTRAINT ck_modeling_metal_recipe_batch_all_or_none,
          DROP COLUMN processing_batch_attempt_no,
          DROP COLUMN processing_batch_attempt_id,
          DROP COLUMN processing_batch_member_id,
          DROP COLUMN processing_batch_id,
          DROP COLUMN processing_recipe_sha256,
          DROP COLUMN processing_recipe_revision_id,
          DROP COLUMN processing_recipe_id;
        """
    )
    op.execute(
        "ALTER TABLE modeling.material_model_revision "
        "DROP CONSTRAINT ck_modeling_material_model_family_digest, "
        "ADD CONSTRAINT ck_modeling_material_model_family_digest CHECK ("
        + _family_constraint(include_metal_recipe=False)
        + ")"
    )

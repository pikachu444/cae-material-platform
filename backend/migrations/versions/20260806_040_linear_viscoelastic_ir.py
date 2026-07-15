"""Add the typed reference linear-viscoelastic Prony Material Model IR.

Revision ID: 20260806_040_prony
Revises: 20260805_039_steel
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260806_040_prony"
down_revision: str | None = "20260805_039_steel"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_LINEAR = "urn:cmp:reference:isotropic-linear-elasticity:1.0.0"
_TABULATED = "urn:cmp:reference:isotropic-tabulated-plasticity:1.0.0"
_VOCE = "urn:cmp:reference:isotropic-tabulated-plasticity:1.1.0"
_PRONY = "urn:cmp:reference:isotropic-linear-viscoelastic-prony:1.0.0"
_LINEAR_DIGEST = "a4e39b23b5d656abb50399b1ae76b799e01872f4f6ebe44a59bc8c901b622cd6"
_TABULATED_DIGEST = "18fd736897f26e6472443a5acf50bf899f8eb8f510ae0eca80dada81047a706f"
_VOCE_DIGEST = "60174f00940a5e371613f941649a61af20714b5664b8b95672e34e1a718251bd"
_PRONY_DIGEST = "84f948444441bf8ead0c3e3a067d78a68335f2160c6d8d5c59348250ff492353"


def _replace_family_constraints(include_prony: bool) -> None:
    for constraint in (
        "ck_modeling_material_model_family",
        "ck_modeling_material_model_family_digest",
        "ck_modeling_material_model_plastic_payload",
        "ck_modeling_material_model_plastic_ranges",
    ):
        op.execute(
            "ALTER TABLE modeling.material_model_revision "
            f"DROP CONSTRAINT IF EXISTS {constraint}"
        )
    families = f"'{_LINEAR}','{_TABULATED}','{_VOCE}'"
    digests = (
        f"(model_family_id='{_LINEAR}' AND model_schema_digest='{_LINEAR_DIGEST}') OR "
        f"(model_family_id='{_TABULATED}' AND model_schema_digest='{_TABULATED_DIGEST}') OR "
        f"(model_family_id='{_VOCE}' AND model_schema_digest='{_VOCE_DIGEST}')"
    )
    linear_like = f"model_family_id='{_LINEAR}'"
    if include_prony:
        families += f",'{_PRONY}'"
        digests += f" OR (model_family_id='{_PRONY}' AND model_schema_digest='{_PRONY_DIGEST}')"
        linear_like = f"model_family_id IN ('{_LINEAR}','{_PRONY}')"
    op.execute(
        f"""
        ALTER TABLE modeling.material_model_revision
          ADD CONSTRAINT ck_modeling_material_model_family
            CHECK (model_family_id IN ({families})),
          ADD CONSTRAINT ck_modeling_material_model_family_digest CHECK ({digests}),
          ADD CONSTRAINT ck_modeling_material_model_plastic_payload CHECK (
            ({linear_like} AND hardening_curve_artifact_id IS NULL
              AND source_dataset_id IS NULL AND voce_calibration_candidate_id IS NULL)
            OR (model_family_id='{_TABULATED}' AND source_dataset_id IS NOT NULL
              AND source_dataset_revision_id IS NOT NULL
              AND hardening_curve_artifact_id IS NOT NULL
              AND source_point_count IS NOT NULL AND voce_calibration_candidate_id IS NULL)
            OR (model_family_id='{_VOCE}' AND source_dataset_id IS NULL
              AND source_dataset_revision_id IS NULL AND source_point_count IS NULL
              AND pre_yield_excluded_point_count IS NULL
              AND post_necking_excluded_point_count IS NULL
              AND necking_source_point_index IS NULL AND necking_engineering_strain IS NULL
              AND hardening_curve_artifact_id IS NOT NULL
              AND hardening_curve_sha256 IS NOT NULL
              AND hardening_curve_point_count IS NOT NULL
              AND calibration_input_scope_id IS NOT NULL
              AND calibration_input_scope_revision_id IS NOT NULL
              AND voce_calibration_plan_id IS NOT NULL
              AND voce_calibration_plan_revision_id IS NOT NULL
              AND voce_calibration_run_id IS NOT NULL
              AND voce_calibration_candidate_id IS NOT NULL
              AND voce_calibration_candidate_sha256 ~ '^[0-9a-f]{{64}}$'
              AND voce_candidate_selection_id IS NOT NULL
              AND voce_candidate_selection_revision_id IS NOT NULL
              AND voce_sampling_point_count BETWEEN 21 AND 501
              AND hardening_curve_point_count=voce_sampling_point_count+1
              AND voce_q_pa > 0 AND voce_b > 0 AND source_yield_stress_pa > 0
              AND characterized_max_true_plastic_strain > 0
              AND extension_max_true_plastic_strain > characterized_max_true_plastic_strain
              AND post_necking_approximation_acknowledged IS TRUE)),
          ADD CONSTRAINT ck_modeling_material_model_plastic_ranges CHECK (
            {linear_like}
            OR (model_family_id='{_TABULATED}' AND necking_engineering_strain >= 0
              AND characterized_max_true_plastic_strain >= 0
              AND extension_max_true_plastic_strain > characterized_max_true_plastic_strain)
            OR (model_family_id='{_VOCE}' AND necking_engineering_strain IS NULL
              AND characterized_max_true_plastic_strain > 0
              AND extension_max_true_plastic_strain > characterized_max_true_plastic_strain))
        """
    )


def _secure(table: str) -> None:
    for operation in ("select", "insert"):
        permission = "modeling.read" if operation == "select" else "modeling.write"
        predicate = "USING" if operation == "select" else "WITH CHECK"
        op.execute(
            f"CREATE POLICY modeling_{table}_{operation} ON modeling.{table} "
            f"FOR {operation.upper()} {predicate} "
            "(access_control.can_access_row(organization_id, project_id, "
            f"classification, '{permission}'))"
        )


def upgrade() -> None:
    _replace_family_constraints(True)
    op.execute(
        """
        CREATE TABLE modeling.linear_viscoelastic_revision (
          organization_id uuid NOT NULL,
          project_id uuid NOT NULL,
          classification varchar(64) NOT NULL,
          material_model_id uuid NOT NULL,
          material_model_revision_id uuid NOT NULL,
          bulk_relaxation_status varchar(32) NOT NULL,
          term_count integer NOT NULL,
          CONSTRAINT pk_modeling_linear_viscoelastic_revision PRIMARY KEY
            (organization_id, project_id, material_model_revision_id),
          CONSTRAINT uq_modeling_linear_viscoelastic_revision_scoped UNIQUE
            (organization_id, project_id, classification, material_model_id,
             material_model_revision_id),
          CONSTRAINT fk_modeling_linear_viscoelastic_revision_model FOREIGN KEY
            (organization_id, project_id, classification, material_model_id,
             material_model_revision_id)
            REFERENCES modeling.material_model_revision
            (organization_id, project_id, classification, aggregate_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT ck_modeling_linear_viscoelastic_bulk_status CHECK
            (bulk_relaxation_status IN ('characterized', 'not_characterized')),
          CONSTRAINT ck_modeling_linear_viscoelastic_term_count CHECK
            (term_count BETWEEN 1 AND 5)
        );
        CREATE TABLE modeling.linear_viscoelastic_prony_term (
          organization_id uuid NOT NULL,
          project_id uuid NOT NULL,
          classification varchar(64) NOT NULL,
          material_model_id uuid NOT NULL,
          material_model_revision_id uuid NOT NULL,
          ordinal integer NOT NULL,
          g_ratio double precision NOT NULL,
          k_ratio double precision NOT NULL,
          relaxation_time_s double precision NOT NULL,
          CONSTRAINT pk_modeling_linear_viscoelastic_prony_term PRIMARY KEY
            (organization_id, project_id, material_model_revision_id, ordinal),
          CONSTRAINT fk_modeling_linear_viscoelastic_prony_summary FOREIGN KEY
            (organization_id, project_id, classification, material_model_id,
             material_model_revision_id)
            REFERENCES modeling.linear_viscoelastic_revision
            (organization_id, project_id, classification, material_model_id,
             material_model_revision_id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT ck_modeling_linear_viscoelastic_ordinal CHECK (ordinal BETWEEN 1 AND 5),
          CONSTRAINT ck_modeling_linear_viscoelastic_g_ratio CHECK
            (g_ratio >= 0 AND g_ratio < 1 AND g_ratio < 'Infinity'::float8),
          CONSTRAINT ck_modeling_linear_viscoelastic_k_ratio CHECK
            (k_ratio >= 0 AND k_ratio < 1 AND k_ratio < 'Infinity'::float8),
          CONSTRAINT ck_modeling_linear_viscoelastic_time CHECK
            (relaxation_time_s > 0 AND relaxation_time_s < 'Infinity'::float8)
        )
        """
    )
    op.execute(
        "CREATE INDEX ix_mdl_linear_viscoelastic_state_source ON "
        "modeling.material_model_revision (organization_id, project_id, "
        "material_state_id, property_set_revision_id) "
        f"WHERE model_family_id='{_PRONY}'"
    )
    op.execute(
        "CREATE INDEX ix_mdl_linear_viscoelastic_term_tau ON "
        "modeling.linear_viscoelastic_prony_term "
        "(organization_id, project_id, material_model_revision_id, relaxation_time_s)"
    )
    for table in ("linear_viscoelastic_revision", "linear_viscoelastic_prony_term"):
        op.execute(f"ALTER TABLE modeling.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE modeling.{table} FORCE ROW LEVEL SECURITY")
        _secure(table)
        op.execute(
            f"CREATE TRIGGER modeling_{table}_immutable BEFORE UPDATE OR DELETE "
            f"ON modeling.{table} FOR EACH ROW "
            "EXECUTE FUNCTION revisioning.reject_immutable_row_mutation()"
        )
    op.execute(
        f"""
        CREATE FUNCTION modeling.guard_linear_viscoelastic_source() RETURNS trigger
        LANGUAGE plpgsql AS $$
        DECLARE source_class text;
        BEGIN
          IF NEW.model_family_id <> '{_PRONY}' THEN RETURN NEW; END IF;
          SELECT COALESCE(material_class, 'unclassified') INTO source_class
          FROM catalog.material_revision
          WHERE organization_id=NEW.organization_id AND project_id=NEW.project_id
            AND classification=NEW.classification AND aggregate_id=NEW.material_id
            AND id=NEW.material_revision_id;
          IF source_class NOT IN ('polymer', 'elastomer') THEN
            RAISE EXCEPTION USING ERRCODE='23514', MESSAGE=
              'linear viscoelastic IR requires a polymer- or elastomer Material revision';
          END IF;
          RETURN NEW;
        END $$;
        CREATE TRIGGER modeling_linear_viscoelastic_source_guard BEFORE INSERT
          ON modeling.material_model_revision FOR EACH ROW
          EXECUTE FUNCTION modeling.guard_linear_viscoelastic_source()
        """
    )
    op.execute(
        f"""
        CREATE FUNCTION modeling.validate_linear_viscoelastic_terms() RETURNS trigger
        LANGUAGE plpgsql AS $$
        DECLARE summary record; DECLARE actual_count integer;
        DECLARE shear_sum double precision; DECLARE bulk_sum double precision;
        DECLARE ordered_count integer; DECLARE family text;
        BEGIN
          SELECT * INTO summary FROM modeling.linear_viscoelastic_revision
          WHERE organization_id=NEW.organization_id AND project_id=NEW.project_id
            AND material_model_revision_id=NEW.material_model_revision_id;
          SELECT model_family_id INTO family FROM modeling.material_model_revision
          WHERE organization_id=NEW.organization_id AND project_id=NEW.project_id
            AND aggregate_id=NEW.material_model_id AND id=NEW.material_model_revision_id;
          SELECT count(*), COALESCE(sum(g_ratio),0), COALESCE(sum(k_ratio),0)
            INTO actual_count, shear_sum, bulk_sum
          FROM modeling.linear_viscoelastic_prony_term
          WHERE organization_id=NEW.organization_id AND project_id=NEW.project_id
            AND material_model_revision_id=NEW.material_model_revision_id;
          SELECT count(*) INTO ordered_count FROM (
            SELECT ordinal, relaxation_time_s,
              lag(relaxation_time_s) OVER (ORDER BY ordinal) AS prior_tau
            FROM modeling.linear_viscoelastic_prony_term
            WHERE organization_id=NEW.organization_id AND project_id=NEW.project_id
              AND material_model_revision_id=NEW.material_model_revision_id
          ) terms WHERE ordinal BETWEEN 1 AND summary.term_count
            AND (prior_tau IS NULL OR relaxation_time_s > prior_tau);
          IF family IS DISTINCT FROM '{_PRONY}' OR summary.term_count IS DISTINCT FROM actual_count
             OR ordered_count IS DISTINCT FROM actual_count OR shear_sum >= 1 OR bulk_sum >= 1
             OR shear_sum + bulk_sum <= 0
             OR (summary.bulk_relaxation_status='not_characterized' AND bulk_sum <> 0)
             OR (summary.bulk_relaxation_status='characterized' AND bulk_sum <= 0) THEN
            RAISE EXCEPTION USING ERRCODE='23514', MESSAGE=
              'linear viscoelastic Prony term set violates its typed revision contract';
          END IF;
          RETURN NEW;
        END $$;
        CREATE CONSTRAINT TRIGGER modeling_linear_viscoelastic_summary_validate
          AFTER INSERT ON modeling.linear_viscoelastic_revision DEFERRABLE INITIALLY DEFERRED
          FOR EACH ROW EXECUTE FUNCTION modeling.validate_linear_viscoelastic_terms();
        CREATE CONSTRAINT TRIGGER modeling_linear_viscoelastic_term_validate
          AFTER INSERT ON modeling.linear_viscoelastic_prony_term DEFERRABLE INITIALLY DEFERRED
          FOR EACH ROW EXECUTE FUNCTION modeling.validate_linear_viscoelastic_terms()
        """
    )


def downgrade() -> None:
    op.execute(
        "DO $$ BEGIN IF EXISTS (SELECT 1 FROM modeling.linear_viscoelastic_revision) THEN "
        "RAISE EXCEPTION 'cannot downgrade while immutable linear-viscoelastic revisions exist'; "
        "END IF; END $$"
    )
    op.execute(
        "DROP TRIGGER IF EXISTS modeling_linear_viscoelastic_source_guard "
        "ON modeling.material_model_revision"
    )
    op.execute("DROP FUNCTION IF EXISTS modeling.guard_linear_viscoelastic_source()")
    op.execute("DROP TABLE modeling.linear_viscoelastic_prony_term")
    op.execute("DROP TABLE modeling.linear_viscoelastic_revision")
    op.execute("DROP FUNCTION modeling.validate_linear_viscoelastic_terms()")
    op.execute("DROP INDEX IF EXISTS modeling.ix_mdl_linear_viscoelastic_state_source")
    _replace_family_constraints(False)

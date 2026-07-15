"""Add the typed Abaqus time-domain card for the reference linear-Prony IR.

Revision ID: 20260807_041_prony_card
Revises: 20260806_040_prony
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260807_041_prony_card"
down_revision: str | None = "20260806_040_prony"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_LINEAR_DIGEST = "a4e39b23b5d656abb50399b1ae76b799e01872f4f6ebe44a59bc8c901b622cd6"
_PLASTIC_DIGEST = "18fd736897f26e6472443a5acf50bf899f8eb8f510ae0eca80dada81047a706f"
_VOCE_DIGEST = "60174f00940a5e371613f941649a61af20714b5664b8b95672e34e1a718251bd"
_PRONY_DIGEST = "84f948444441bf8ead0c3e3a067d78a68335f2160c6d8d5c59348250ff492353"
_PRONY_EXPORTER = "cmp.reference.abaqus-linear-prony"
_PRONY_EXPORTER_DIGEST = "3645e19c99d6030f5438d43407e05e5422f1f7413a4fd9650a2d786e5b343a5e"

_LINEAR_CONTRACT = (
    "exporter_id='cmp.reference.openradioss-elast' AND exporter_version='1.0.0' "
    "AND exporter_digest='65a3f7ea55150a9c660b4303d12a168d8366bb1e41c6c86684a1e8a2fde20a20' "
    f"AND target_solver='openradioss' AND model_schema_digest='{_LINEAR_DIGEST}' "
    "AND material_name IS NULL AND hardening_curve_artifact_id IS NULL "
    "AND hardening_curve_sha256 IS NULL AND hardening_curve_point_count IS NULL "
    "AND extension_max_true_plastic_strain IS NULL "
    "AND post_necking_extension_policy IS NULL "
    "AND hardening_curve_mapping_status IS NULL AND extension_mapping_status IS NULL"
)
_PLASTIC_REQUIRED = (
    "material_name IS NOT NULL AND source_yield_stress_pa IS NOT NULL "
    "AND hardening_curve_artifact_id IS NOT NULL AND hardening_curve_sha256 IS NOT NULL "
    "AND hardening_curve_point_count IS NOT NULL "
    "AND extension_max_true_plastic_strain IS NOT NULL "
    "AND post_necking_extension_policy IS NOT NULL "
    "AND hardening_curve_mapping_status IS NOT NULL AND extension_mapping_status IS NOT NULL "
    "AND density_mapping_status='exact' AND youngs_modulus_mapping_status='exact' "
    "AND poisson_ratio_mapping_status='exact' AND source_yield_mapping_status='transformed' "
    "AND hardening_curve_mapping_status='transformed' "
    "AND extension_mapping_status='approximated' "
    "AND temperature_applicability_mapping_status='not_applicable' "
    "AND strain_rate_applicability_mapping_status='not_applicable'"
)
_LAW36_CONTRACT = (
    "exporter_id='cmp.reference.openradioss-law36' AND exporter_version='1.0.0' "
    "AND exporter_digest='713da51619eedfeda972205426fe86ae25e0d9f75d85554183f35bca76f73be2' "
    f"AND target_solver='openradioss' AND model_schema_digest IN "
    f"('{_PLASTIC_DIGEST}','{_VOCE_DIGEST}') "
    f"AND unit_system_mapping_status='exact' AND {_PLASTIC_REQUIRED}"
)
_ABAQUS_PLASTIC_CONTRACT = (
    "exporter_id='cmp.reference.abaqus-isotropic-plasticity' AND exporter_version='1.0.0' "
    "AND exporter_digest='0585a5dbf0898fcea74009120045b29bf52fef6c428e1285c6603aaee5dd05ad' "
    f"AND target_solver='abaqus' AND model_schema_digest IN ('{_PLASTIC_DIGEST}','{_VOCE_DIGEST}') "
    f"AND unit_system_mapping_status='transformed' AND {_PLASTIC_REQUIRED}"
)
_PRONY_CONTRACT = (
    f"exporter_id='{_PRONY_EXPORTER}' AND exporter_version='1.0.0' "
    f"AND exporter_digest='{_PRONY_EXPORTER_DIGEST}' AND target_solver='abaqus' "
    f"AND model_schema_digest='{_PRONY_DIGEST}' AND material_name IS NOT NULL "
    "AND source_yield_stress_pa IS NULL AND hardening_curve_artifact_id IS NULL "
    "AND hardening_curve_sha256 IS NULL AND hardening_curve_point_count IS NULL "
    "AND extension_max_true_plastic_strain IS NULL "
    "AND post_necking_extension_policy IS NULL "
    "AND hardening_curve_mapping_status IS NULL AND extension_mapping_status IS NULL "
    "AND density_mapping_status='exact' AND youngs_modulus_mapping_status='exact' "
    "AND poisson_ratio_mapping_status='exact' AND source_yield_mapping_status='not_applicable' "
    "AND temperature_applicability_mapping_status='not_applicable' "
    "AND strain_rate_applicability_mapping_status='not_applicable' "
    "AND unit_system_mapping_status='transformed'"
)


def _replace_common_constraints(include_prony: bool) -> None:
    op.execute(
        "ALTER TABLE exporting.solver_card_revision "
        "DROP CONSTRAINT IF EXISTS ck_exporting_solver_card_model_digest"
    )
    op.execute(
        "ALTER TABLE exporting.solver_card_revision "
        "DROP CONSTRAINT IF EXISTS ck_exporting_solver_card_exporter_contract"
    )
    digests = f"'{_LINEAR_DIGEST}','{_PLASTIC_DIGEST}','{_VOCE_DIGEST}'"
    contracts = f"({_LINEAR_CONTRACT}) OR ({_LAW36_CONTRACT}) OR ({_ABAQUS_PLASTIC_CONTRACT})"
    if include_prony:
        digests += f",'{_PRONY_DIGEST}'"
        contracts += f" OR ({_PRONY_CONTRACT})"
    op.execute(
        "ALTER TABLE exporting.solver_card_revision ADD CONSTRAINT "
        f"ck_exporting_solver_card_model_digest CHECK (model_schema_digest IN ({digests})), "
        "ADD CONSTRAINT ck_exporting_solver_card_exporter_contract "
        f"CHECK ({contracts})"
    )


def _secure(table: str) -> None:
    for operation in ("select", "insert"):
        permission = "export.read" if operation == "select" else "export.execute"
        predicate = "USING" if operation == "select" else "WITH CHECK"
        op.execute(
            f"CREATE POLICY exporting_{table}_{operation} ON exporting.{table} "
            f"FOR {operation.upper()} {predicate} "
            "(access_control.can_access_row(organization_id, project_id, "
            f"classification, '{permission}'))"
        )


def upgrade() -> None:
    _replace_common_constraints(True)
    op.execute(
        """
        CREATE TABLE exporting.linear_viscoelastic_solver_card_revision (
          organization_id uuid NOT NULL,
          project_id uuid NOT NULL,
          classification varchar(64) NOT NULL,
          solver_card_id uuid NOT NULL,
          solver_card_revision_id uuid NOT NULL,
          bulk_relaxation_status varchar(32) NOT NULL,
          prony_terms_mapping_status varchar(32) NOT NULL,
          bulk_mapping_status varchar(32) NOT NULL,
          term_count integer NOT NULL,
          CONSTRAINT pk_exporting_linear_viscoelastic_card_revision PRIMARY KEY
            (organization_id, project_id, solver_card_revision_id),
          CONSTRAINT uq_exporting_linear_viscoelastic_card_revision_scoped UNIQUE
            (organization_id, project_id, classification, solver_card_id,
             solver_card_revision_id),
          CONSTRAINT fk_exporting_linear_viscoelastic_card_revision FOREIGN KEY
            (organization_id, project_id, classification, solver_card_id,
             solver_card_revision_id)
            REFERENCES exporting.solver_card_revision
            (organization_id, project_id, classification, aggregate_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT ck_exporting_linear_viscoelastic_card_bulk_status CHECK
            (bulk_relaxation_status IN ('characterized','not_characterized')),
          CONSTRAINT ck_exporting_linear_viscoelastic_card_term_status CHECK
            (prony_terms_mapping_status='exact'),
          CONSTRAINT ck_exporting_linear_viscoelastic_card_bulk_map CHECK
            ((bulk_relaxation_status='characterized' AND bulk_mapping_status='exact') OR
             (bulk_relaxation_status='not_characterized' AND
              bulk_mapping_status='not_applicable')),
          CONSTRAINT ck_exporting_linear_viscoelastic_card_term_count CHECK
            (term_count BETWEEN 1 AND 5)
        );
        CREATE TABLE exporting.linear_viscoelastic_solver_card_term (
          organization_id uuid NOT NULL,
          project_id uuid NOT NULL,
          classification varchar(64) NOT NULL,
          solver_card_id uuid NOT NULL,
          solver_card_revision_id uuid NOT NULL,
          ordinal integer NOT NULL,
          g_ratio double precision NOT NULL,
          k_ratio double precision NOT NULL,
          relaxation_time_s double precision NOT NULL,
          CONSTRAINT pk_exporting_linear_viscoelastic_card_term PRIMARY KEY
            (organization_id, project_id, solver_card_revision_id, ordinal),
          CONSTRAINT fk_exporting_linear_viscoelastic_card_term FOREIGN KEY
            (organization_id, project_id, classification, solver_card_id,
             solver_card_revision_id)
            REFERENCES exporting.linear_viscoelastic_solver_card_revision
            (organization_id, project_id, classification, solver_card_id,
             solver_card_revision_id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT ck_exporting_linear_viscoelastic_card_ordinal CHECK
            (ordinal BETWEEN 1 AND 5),
          CONSTRAINT ck_exporting_linear_viscoelastic_card_g CHECK
            (g_ratio >= 0 AND g_ratio < 1 AND g_ratio < 'Infinity'::float8),
          CONSTRAINT ck_exporting_linear_viscoelastic_card_k CHECK
            (k_ratio >= 0 AND k_ratio < 1 AND k_ratio < 'Infinity'::float8),
          CONSTRAINT ck_exporting_linear_viscoelastic_card_tau CHECK
            (relaxation_time_s > 0 AND relaxation_time_s < 'Infinity'::float8)
        )
        """
    )
    op.execute(
        "CREATE INDEX ix_exporting_linear_viscoelastic_card_source ON "
        "exporting.solver_card_revision "
        "(organization_id, project_id, material_model_revision_id) "
        f"WHERE exporter_id='{_PRONY_EXPORTER}'"
    )
    for table in (
        "linear_viscoelastic_solver_card_revision",
        "linear_viscoelastic_solver_card_term",
    ):
        op.execute(f"ALTER TABLE exporting.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE exporting.{table} FORCE ROW LEVEL SECURITY")
        _secure(table)
        op.execute(
            f"CREATE TRIGGER exporting_{table}_immutable BEFORE UPDATE OR DELETE "
            f"ON exporting.{table} FOR EACH ROW "
            "EXECUTE FUNCTION revisioning.reject_immutable_row_mutation()"
        )
    op.execute(
        f"""
        CREATE FUNCTION exporting.validate_linear_viscoelastic_card_terms()
        RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE summary record; DECLARE card record; DECLARE mismatch_count integer;
        BEGIN
          SELECT * INTO summary FROM exporting.linear_viscoelastic_solver_card_revision
          WHERE organization_id=NEW.organization_id AND project_id=NEW.project_id
            AND solver_card_revision_id=NEW.solver_card_revision_id;
          SELECT * INTO card FROM exporting.solver_card_revision
          WHERE organization_id=NEW.organization_id AND project_id=NEW.project_id
            AND aggregate_id=NEW.solver_card_id AND id=NEW.solver_card_revision_id;
          SELECT count(*) INTO mismatch_count FROM (
            (SELECT ordinal,g_ratio,k_ratio,relaxation_time_s
             FROM exporting.linear_viscoelastic_solver_card_term
             WHERE organization_id=NEW.organization_id AND project_id=NEW.project_id
               AND solver_card_revision_id=NEW.solver_card_revision_id
             EXCEPT
             SELECT ordinal,g_ratio,k_ratio,relaxation_time_s
             FROM modeling.linear_viscoelastic_prony_term
             WHERE organization_id=NEW.organization_id AND project_id=NEW.project_id
               AND material_model_revision_id=card.material_model_revision_id)
            UNION ALL
            (SELECT ordinal,g_ratio,k_ratio,relaxation_time_s
             FROM modeling.linear_viscoelastic_prony_term
             WHERE organization_id=NEW.organization_id AND project_id=NEW.project_id
               AND material_model_revision_id=card.material_model_revision_id
             EXCEPT
             SELECT ordinal,g_ratio,k_ratio,relaxation_time_s
             FROM exporting.linear_viscoelastic_solver_card_term
             WHERE organization_id=NEW.organization_id AND project_id=NEW.project_id
               AND solver_card_revision_id=NEW.solver_card_revision_id)
          ) mismatch;
          IF card.exporter_id IS DISTINCT FROM '{_PRONY_EXPORTER}'
             OR summary.term_count IS DISTINCT FROM (
               SELECT count(*) FROM exporting.linear_viscoelastic_solver_card_term
               WHERE organization_id=NEW.organization_id AND project_id=NEW.project_id
                 AND solver_card_revision_id=NEW.solver_card_revision_id)
             OR summary.bulk_relaxation_status IS DISTINCT FROM (
               SELECT bulk_relaxation_status FROM modeling.linear_viscoelastic_revision
               WHERE organization_id=NEW.organization_id AND project_id=NEW.project_id
                 AND material_model_revision_id=card.material_model_revision_id)
             OR mismatch_count <> 0 THEN
            RAISE EXCEPTION USING ERRCODE='23514', MESSAGE=
              'linear-Prony Solver Card terms differ from the exact source IR revision';
          END IF;
          RETURN NEW;
        END $$;
        CREATE CONSTRAINT TRIGGER exporting_linear_viscoelastic_card_summary_validate
          AFTER INSERT ON exporting.linear_viscoelastic_solver_card_revision
          DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
          EXECUTE FUNCTION exporting.validate_linear_viscoelastic_card_terms();
        CREATE CONSTRAINT TRIGGER exporting_linear_viscoelastic_card_term_validate
          AFTER INSERT ON exporting.linear_viscoelastic_solver_card_term
          DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
          EXECUTE FUNCTION exporting.validate_linear_viscoelastic_card_terms()
        """
    )


def downgrade() -> None:
    op.execute(
        "DO $$ BEGIN IF EXISTS (SELECT 1 FROM exporting.solver_card_revision "
        f"WHERE exporter_id='{_PRONY_EXPORTER}') THEN RAISE EXCEPTION "
        "'cannot downgrade while immutable Abaqus linear-Prony cards exist'; END IF; END $$"
    )
    op.execute("DROP TABLE exporting.linear_viscoelastic_solver_card_term")
    op.execute("DROP TABLE exporting.linear_viscoelastic_solver_card_revision")
    op.execute("DROP FUNCTION exporting.validate_linear_viscoelastic_card_terms()")
    op.execute("DROP INDEX IF EXISTS exporting.ix_exporting_linear_viscoelastic_card_source")
    _replace_common_constraints(False)

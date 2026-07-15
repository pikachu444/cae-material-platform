"""Persist Abaqus Ogden-Prony and OpenRadioss LAW62 cards.

Revision ID: 20260813_047_ogden_cards
Revises: 20260812_046_ogden
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260813_047_ogden_cards"
down_revision: str | None = "20260812_046_ogden"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_LINEAR_DIGEST = "a4e39b23b5d656abb50399b1ae76b799e01872f4f6ebe44a59bc8c901b622cd6"
_PLASTIC_DIGEST = "18fd736897f26e6472443a5acf50bf899f8eb8f510ae0eca80dada81047a706f"
_VOCE_DIGEST = "60174f00940a5e371613f941649a61af20714b5664b8b95672e34e1a718251bd"
_PRONY_DIGEST = "84f948444441bf8ead0c3e3a067d78a68335f2160c6d8d5c59348250ff492353"
_OGDEN_DIGEST = "545ef081fd6b702d99710aa2ba1a253d0ef6961b8084647d157fac03cca29f2f"
_ABAQUS_ID = "cmp.reference.abaqus-ogden-prony"
_ABAQUS_DIGEST = "1e092e39a8c08c912ba7bcd9838cc9fa8a2a960cb912b44478c94835a557444b"
_LAW62_ID = "cmp.reference.openradioss-law62"
_LAW62_DIGEST = "1ade1f1f59f00d94c0888802d5f07ddac3c0e11b376f2e4652c33e581f9e5174"

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
    f"AND target_solver='abaqus' AND model_schema_digest IN "
    f"('{_PLASTIC_DIGEST}','{_VOCE_DIGEST}') "
    f"AND unit_system_mapping_status='transformed' AND {_PLASTIC_REQUIRED}"
)
_PRONY_CONTRACT = (
    "exporter_id='cmp.reference.abaqus-linear-prony' AND exporter_version='1.0.0' "
    "AND exporter_digest='3645e19c99d6030f5438d43407e05e5422f1f7413a4fd9650a2d786e5b343a5e' "
    f"AND target_solver='abaqus' AND model_schema_digest='{_PRONY_DIGEST}' "
    "AND material_name IS NOT NULL AND source_yield_stress_pa IS NULL "
    "AND hardening_curve_artifact_id IS NULL AND hardening_curve_sha256 IS NULL "
    "AND hardening_curve_point_count IS NULL AND extension_max_true_plastic_strain IS NULL "
    "AND post_necking_extension_policy IS NULL AND hardening_curve_mapping_status IS NULL "
    "AND extension_mapping_status IS NULL AND density_mapping_status='exact' "
    "AND youngs_modulus_mapping_status='exact' AND poisson_ratio_mapping_status='exact' "
    "AND source_yield_mapping_status='not_applicable' "
    "AND temperature_applicability_mapping_status='not_applicable' "
    "AND strain_rate_applicability_mapping_status='not_applicable' "
    "AND unit_system_mapping_status='transformed'"
)


def _ogden_contract(exporter_id: str, digest: str, solver: str, poisson: str) -> str:
    return (
        f"exporter_id='{exporter_id}' AND exporter_version='1.0.0' "
        f"AND exporter_digest='{digest}' AND target_solver='{solver}' "
        f"AND model_schema_digest='{_OGDEN_DIGEST}' AND material_name IS NOT NULL "
        "AND source_yield_stress_pa IS NULL AND hardening_curve_artifact_id IS NULL "
        "AND hardening_curve_sha256 IS NULL AND hardening_curve_point_count IS NULL "
        "AND extension_max_true_plastic_strain IS NULL "
        "AND post_necking_extension_policy IS NULL "
        "AND hardening_curve_mapping_status IS NULL AND extension_mapping_status IS NULL "
        "AND density_mapping_status='exact' AND youngs_modulus_mapping_status='exact' "
        f"AND poisson_ratio_mapping_status='{poisson}' "
        "AND source_yield_mapping_status='not_applicable' "
        "AND temperature_applicability_mapping_status='not_applicable' "
        "AND strain_rate_applicability_mapping_status='not_applicable' "
        "AND unit_system_mapping_status='transformed'"
    )


def _replace_common_constraints(include_ogden: bool) -> None:
    op.execute(
        "ALTER TABLE exporting.solver_card_revision "
        "DROP CONSTRAINT IF EXISTS ck_exporting_solver_card_model_digest, "
        "DROP CONSTRAINT IF EXISTS ck_exporting_solver_card_exporter_contract"
    )
    digests = f"'{_LINEAR_DIGEST}','{_PLASTIC_DIGEST}','{_VOCE_DIGEST}','{_PRONY_DIGEST}'"
    contracts = (
        f"({_LINEAR_CONTRACT}) OR ({_LAW36_CONTRACT}) OR "
        f"({_ABAQUS_PLASTIC_CONTRACT}) OR ({_PRONY_CONTRACT})"
    )
    if include_ogden:
        digests += f",'{_OGDEN_DIGEST}'"
        contracts += (
            f" OR ({_ogden_contract(_ABAQUS_ID, _ABAQUS_DIGEST, 'abaqus', 'exact')})"
            f" OR ({_ogden_contract(_LAW62_ID, _LAW62_DIGEST, 'openradioss', 'approximated')})"
        )
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
        CREATE TABLE exporting.ogden_prony_solver_card_revision (
          organization_id uuid NOT NULL, project_id uuid NOT NULL,
          classification varchar(64) NOT NULL, solver_card_id uuid NOT NULL,
          solver_card_revision_id uuid NOT NULL,
          ogden_mu_pa double precision NOT NULL, ogden_alpha double precision NOT NULL,
          law62_poisson_ratio double precision NOT NULL, term_count integer NOT NULL,
          ogden_mapping_status varchar(32) NOT NULL,
          prony_mapping_status varchar(32) NOT NULL,
          volumetric_mapping_status varchar(32) NOT NULL,
          CONSTRAINT pk_exp_ogden_card_rev PRIMARY KEY
            (organization_id, project_id, solver_card_revision_id),
          CONSTRAINT uq_exp_ogden_card_rev_scoped UNIQUE
            (organization_id, project_id, classification, solver_card_id,
             solver_card_revision_id),
          CONSTRAINT fk_exp_ogden_card_rev FOREIGN KEY
            (organization_id, project_id, classification, solver_card_id,
             solver_card_revision_id) REFERENCES exporting.solver_card_revision
            (organization_id, project_id, classification, aggregate_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT ck_exp_ogden_card_shape CHECK
            (ogden_mu_pa > 0 AND ogden_alpha > 0 AND law62_poisson_ratio=0.495
             AND term_count BETWEEN 1 AND 5 AND ogden_mapping_status='exact'
             AND prony_mapping_status='exact'
             AND volumetric_mapping_status IN ('exact','approximated'))
        );
        CREATE TABLE exporting.ogden_prony_solver_card_term (
          organization_id uuid NOT NULL, project_id uuid NOT NULL,
          classification varchar(64) NOT NULL, solver_card_id uuid NOT NULL,
          solver_card_revision_id uuid NOT NULL, ordinal integer NOT NULL,
          g_ratio double precision NOT NULL, relaxation_time_s double precision NOT NULL,
          CONSTRAINT pk_exp_ogden_card_term PRIMARY KEY
            (organization_id, project_id, solver_card_revision_id, ordinal),
          CONSTRAINT fk_exp_ogden_card_term FOREIGN KEY
            (organization_id, project_id, classification, solver_card_id,
             solver_card_revision_id) REFERENCES exporting.ogden_prony_solver_card_revision
            (organization_id, project_id, classification, solver_card_id,
             solver_card_revision_id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT ck_exp_ogden_card_term CHECK
            (ordinal BETWEEN 1 AND 5 AND g_ratio > 0 AND g_ratio < 1
             AND relaxation_time_s > 0 AND relaxation_time_s < 'Infinity'::float8)
        );
        CREATE INDEX ix_exp_ogden_card_source ON exporting.solver_card_revision
          (organization_id, project_id, material_model_revision_id)
          WHERE exporter_id IN
            ('cmp.reference.abaqus-ogden-prony','cmp.reference.openradioss-law62')
        """
    )
    for table in ("ogden_prony_solver_card_revision", "ogden_prony_solver_card_term"):
        op.execute(f"ALTER TABLE exporting.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE exporting.{table} FORCE ROW LEVEL SECURITY")
        _secure(table)
        op.execute(
            f"CREATE TRIGGER exporting_{table}_immutable BEFORE UPDATE OR DELETE "
            f"ON exporting.{table} FOR EACH ROW "
            "EXECUTE FUNCTION revisioning.reject_immutable_row_mutation()"
        )
    op.execute(
        """
        CREATE FUNCTION exporting.validate_ogden_prony_card_terms()
        RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE summary record; card record; mismatch_count integer;
        BEGIN
          SELECT * INTO summary FROM exporting.ogden_prony_solver_card_revision
          WHERE organization_id=NEW.organization_id AND project_id=NEW.project_id
            AND solver_card_revision_id=NEW.solver_card_revision_id;
          SELECT * INTO card FROM exporting.solver_card_revision
          WHERE organization_id=NEW.organization_id AND project_id=NEW.project_id
            AND aggregate_id=NEW.solver_card_id AND id=NEW.solver_card_revision_id;
          SELECT count(*) INTO mismatch_count FROM (
            (SELECT ordinal,g_ratio,relaxation_time_s
             FROM exporting.ogden_prony_solver_card_term
             WHERE organization_id=NEW.organization_id AND project_id=NEW.project_id
               AND solver_card_revision_id=NEW.solver_card_revision_id
             EXCEPT SELECT ordinal,g_ratio,relaxation_time_s
             FROM modeling.ogden_prony_term
             WHERE organization_id=NEW.organization_id AND project_id=NEW.project_id
               AND material_model_revision_id=card.material_model_revision_id)
            UNION ALL
            (SELECT ordinal,g_ratio,relaxation_time_s FROM modeling.ogden_prony_term
             WHERE organization_id=NEW.organization_id AND project_id=NEW.project_id
               AND material_model_revision_id=card.material_model_revision_id
             EXCEPT SELECT ordinal,g_ratio,relaxation_time_s
             FROM exporting.ogden_prony_solver_card_term
             WHERE organization_id=NEW.organization_id AND project_id=NEW.project_id
               AND solver_card_revision_id=NEW.solver_card_revision_id)
          ) mismatch;
          IF summary.term_count IS DISTINCT FROM (
               SELECT count(*) FROM exporting.ogden_prony_solver_card_term
               WHERE organization_id=NEW.organization_id AND project_id=NEW.project_id
                 AND solver_card_revision_id=NEW.solver_card_revision_id)
             OR mismatch_count <> 0 THEN
            RAISE EXCEPTION 'Ogden-Prony card differs from exact source IR revision'
              USING ERRCODE='23514';
          END IF;
          RETURN NEW;
        END $$;
        CREATE CONSTRAINT TRIGGER exporting_ogden_card_summary_validate
          AFTER INSERT ON exporting.ogden_prony_solver_card_revision
          DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
          EXECUTE FUNCTION exporting.validate_ogden_prony_card_terms();
        CREATE CONSTRAINT TRIGGER exporting_ogden_card_term_validate
          AFTER INSERT ON exporting.ogden_prony_solver_card_term
          DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
          EXECUTE FUNCTION exporting.validate_ogden_prony_card_terms()
        """
    )


def downgrade() -> None:
    op.execute(
        "DO $$ BEGIN IF EXISTS (SELECT 1 FROM exporting.solver_card_revision WHERE "
        f"exporter_id IN ('{_ABAQUS_ID}','{_LAW62_ID}')) THEN RAISE EXCEPTION "
        "'cannot downgrade with immutable Ogden-Prony cards'; END IF; END $$"
    )
    op.execute("DROP TABLE exporting.ogden_prony_solver_card_term")
    op.execute("DROP TABLE exporting.ogden_prony_solver_card_revision")
    op.execute("DROP FUNCTION exporting.validate_ogden_prony_card_terms()")
    op.execute("DROP INDEX IF EXISTS exporting.ix_exp_ogden_card_source")
    _replace_common_constraints(False)

"""Add explicit common-grid replicate alignment recipes and grouped runs.

Revision ID: 20260729_032_p02
Revises: 20260728_031_p02
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260729_032_p02"
down_revision: str | None = "20260728_031_p02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CROP = "reference_tensile_inclusive_crop"
_ALIGN = "reference_tensile_common_grid_linear"
_CROP_DIAGNOSTICS = "urn:cmp:processing:reference-tensile-crop-diagnostics:1.0.0"
_ALIGN_DIAGNOSTICS = "urn:cmp:processing:reference-tensile-common-grid-diagnostics:1.0.0"


def upgrade() -> None:
    op.execute(
        "ALTER TABLE processing.processing_recipe DROP CONSTRAINT ck_processing_recipe_kind, "
        f"ADD CONSTRAINT ck_processing_recipe_kind CHECK (recipe_kind IN ('{_CROP}', '{_ALIGN}'))"
    )
    op.execute(
        "ALTER TABLE processing.processing_recipe_revision "
        "DROP CONSTRAINT ck_processing_recipe_revision_kind, "
        "DROP CONSTRAINT ck_processing_recipe_revision_minimum, "
        "DROP CONSTRAINT ck_processing_recipe_revision_maximum, "
        "DROP CONSTRAINT ck_processing_recipe_revision_diagnostics_schema, "
        "ALTER COLUMN minimum_engineering_strain DROP NOT NULL, "
        "ALTER COLUMN maximum_engineering_strain DROP NOT NULL, "
        "ADD COLUMN grid_start_engineering_strain float8, "
        "ADD COLUMN grid_end_engineering_strain float8, "
        "ADD COLUMN grid_point_count bigint, "
        "ADD COLUMN domain_policy varchar(32), "
        "ADD COLUMN interpolation_policy varchar(32), "
        "ADD COLUMN extrapolation_policy varchar(32)"
    )
    op.execute(
        "ALTER TABLE processing.processing_recipe_revision "
        "ADD CONSTRAINT ck_processing_recipe_revision_kind CHECK "
        f"(recipe_kind IN ('{_CROP}', '{_ALIGN}')), "
        "ADD CONSTRAINT ck_processing_recipe_revision_typed_shape CHECK ("
        f"(recipe_kind = '{_CROP}' AND minimum_engineering_strain >= 0 "
        " AND minimum_engineering_strain < 'Infinity'::float8 "
        " AND maximum_engineering_strain > minimum_engineering_strain "
        " AND maximum_engineering_strain < 'Infinity'::float8 "
        f" AND diagnostics_schema_ref = '{_CROP_DIAGNOSTICS}' "
        " AND grid_start_engineering_strain IS NULL AND grid_end_engineering_strain IS NULL "
        " AND grid_point_count IS NULL AND domain_policy IS NULL "
        " AND interpolation_policy IS NULL AND extrapolation_policy IS NULL) OR "
        f"(recipe_kind = '{_ALIGN}' AND minimum_engineering_strain IS NULL "
        " AND maximum_engineering_strain IS NULL AND grid_start_engineering_strain >= 0 "
        " AND grid_start_engineering_strain < 'Infinity'::float8 "
        " AND grid_end_engineering_strain > grid_start_engineering_strain "
        " AND grid_end_engineering_strain < 'Infinity'::float8 "
        " AND grid_point_count BETWEEN 2 AND 100000 "
        " AND domain_policy = 'intersection' "
        " AND interpolation_policy = 'piecewise_linear' "
        " AND extrapolation_policy = 'reject' "
        f" AND diagnostics_schema_ref = '{_ALIGN_DIAGNOSTICS}'))"
    )

    op.execute(
        "ALTER TABLE processing.processing_run "
        f"ADD COLUMN run_kind varchar(100) NOT NULL DEFAULT '{_CROP}', "
        "ADD COLUMN batch_id uuid, ADD COLUMN member_ordinal smallint"
    )
    op.execute("ALTER TABLE processing.processing_run ALTER COLUMN run_kind DROP DEFAULT")
    op.execute(
        "ALTER TABLE processing.processing_run "
        "DROP CONSTRAINT ck_processing_run_terminal_shape, "
        f"ADD CONSTRAINT ck_processing_run_kind CHECK (run_kind IN ('{_CROP}', '{_ALIGN}')), "
        "ADD CONSTRAINT ck_processing_run_group_shape CHECK ("
        f"(run_kind = '{_CROP}' AND batch_id IS NULL AND member_ordinal IS NULL) OR "
        f"(run_kind = '{_ALIGN}' AND batch_id IS NOT NULL "
        " AND batch_id <> '00000000-0000-0000-0000-000000000000'::uuid "
        " AND member_ordinal BETWEEN 0 AND 49)), "
        "ADD CONSTRAINT ck_processing_run_terminal_shape CHECK ("
        "(status = 'executing' AND ended_at IS NULL AND output_point_count IS NULL "
        " AND removed_point_count IS NULL AND result_artifact_id IS NULL "
        " AND output_dataset_id IS NULL AND output_dataset_revision_id IS NULL "
        " AND failure_code IS NULL) OR "
        "(status = 'succeeded' AND ended_at IS NOT NULL "
        " AND output_point_count BETWEEN 2 AND 100000 "
        f" AND ((run_kind = '{_CROP}' AND removed_point_count >= 0 "
        "       AND output_point_count + removed_point_count = input_point_count) "
        f"      OR (run_kind = '{_ALIGN}' AND removed_point_count IS NULL)) "
        " AND result_artifact_id IS NOT NULL AND output_dataset_id IS NOT NULL "
        " AND output_dataset_revision_id IS NOT NULL AND failure_code IS NULL) OR "
        "(status = 'failed' AND ended_at IS NOT NULL AND output_point_count IS NULL "
        " AND removed_point_count IS NULL AND output_dataset_id IS NULL "
        " AND output_dataset_revision_id IS NULL "
        " AND length(btrim(failure_code)) BETWEEN 1 AND 100))"
    )
    op.execute(
        "CREATE UNIQUE INDEX ux_processing_run_alignment_batch_member "
        "ON processing.processing_run "
        "(organization_id, project_id, classification, batch_id, member_ordinal) "
        f"WHERE run_kind = '{_ALIGN}'"
    )
    _replace_run_guards()
    _replace_provenance_finalization_guard()


def _replace_provenance_finalization_guard() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION provenance.guard_activity_input_finalization()
        RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE semantic_specialization boolean;
        BEGIN
          IF TG_OP = 'DELETE' THEN
            RAISE EXCEPTION USING ERRCODE = '55000',
              MESSAGE = 'provenance Activity rows cannot be deleted';
          END IF;
          semantic_specialization :=
            OLD.activity_type = 'core.revision_commit'
            AND NEW.activity_type ~ '^(processing|statistics)\\.'
            AND NEW.domain_run_type IS NOT NULL
            AND NEW.domain_run_id IS NOT NULL;
          IF NOT NEW.input_required
             OR OLD.organization_id IS DISTINCT FROM NEW.organization_id
             OR OLD.project_id IS DISTINCT FROM NEW.project_id
             OR OLD.classification IS DISTINCT FROM NEW.classification
             OR OLD.id IS DISTINCT FROM NEW.id
             OR (OLD.activity_type IS DISTINCT FROM NEW.activity_type
                 AND NOT semantic_specialization)
             OR (OLD.domain_run_type IS DISTINCT FROM NEW.domain_run_type
                 AND NOT semantic_specialization)
             OR (OLD.domain_run_id IS DISTINCT FROM NEW.domain_run_id
                 AND NOT semantic_specialization)
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
        END; $$
        """
    )
    op.execute("DROP TRIGGER provenance_association_immutable ON provenance.association")
    op.execute(
        """
        CREATE FUNCTION provenance.guard_association_plan_finalization()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF TG_OP = 'DELETE' OR OLD.plan_entity_id IS NOT NULL
             OR NEW.plan_entity_id IS NULL
             OR OLD.organization_id IS DISTINCT FROM NEW.organization_id
             OR OLD.project_id IS DISTINCT FROM NEW.project_id
             OR OLD.classification IS DISTINCT FROM NEW.classification
             OR OLD.activity_id IS DISTINCT FROM NEW.activity_id
             OR OLD.agent_id IS DISTINCT FROM NEW.agent_id
             OR OLD.role IS DISTINCT FROM NEW.role
             OR OLD.recorded_at IS DISTINCT FROM NEW.recorded_at
             OR OLD.recorded_by IS DISTINCT FROM NEW.recorded_by
             OR OLD.recorded_by::text IS DISTINCT FROM
                current_setting('cmp.principal_id', true)
             OR NOT EXISTS (
               SELECT 1 FROM provenance.activity activity
               WHERE activity.organization_id = OLD.organization_id
                 AND activity.project_id = OLD.project_id
                 AND activity.classification = OLD.classification
                 AND activity.id = OLD.activity_id
                 AND activity.request_id::text = current_setting('cmp.request_id', true)
             )
             OR NOT EXISTS (
               SELECT 1 FROM provenance.usage usage
               WHERE usage.organization_id = OLD.organization_id
                 AND usage.project_id = OLD.project_id
                 AND usage.classification = OLD.classification
                 AND usage.activity_id = OLD.activity_id
                 AND usage.entity_id = NEW.plan_entity_id
             ) THEN
            RAISE EXCEPTION USING ERRCODE = '55000',
              MESSAGE = 'provenance Association permits only same-request plan finalization';
          END IF;
          RETURN NEW;
        END; $$
        """
    )
    op.execute(
        "CREATE TRIGGER provenance_association_immutable BEFORE UPDATE OR DELETE "
        "ON provenance.association FOR EACH ROW "
        "EXECUTE FUNCTION provenance.guard_association_plan_finalization()"
    )
    op.execute(
        "CREATE POLICY association_authorized_plan_finalization ON provenance.association "
        "FOR UPDATE USING (access_control.can_access_row(organization_id, project_id, "
        "classification, 'provenance.write') AND recorded_by::text = "
        "current_setting('cmp.principal_id', true)) WITH CHECK "
        "(access_control.can_access_row(organization_id, project_id, classification, "
        "'provenance.write') AND recorded_by::text = "
        "current_setting('cmp.principal_id', true))"
    )


def _replace_run_guards() -> None:
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION processing.guard_processing_run_insert()
        RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE selected_dataset_id uuid; selected_dataset_revision_id uuid;
          selected_kind text; selected_recipe_kind text; selected_representation text;
        BEGIN
          SELECT selection_kind, dataset_id, dataset_revision_id
          INTO selected_kind, selected_dataset_id, selected_dataset_revision_id
          FROM datasets.dataset_selection_revision
          WHERE organization_id = NEW.organization_id AND project_id = NEW.project_id
            AND classification = NEW.classification AND aggregate_id = NEW.selection_id
            AND id = NEW.selection_revision_id;
          IF NOT FOUND THEN
            RAISE EXCEPTION USING ERRCODE = '23514', MESSAGE = 'Processing Run Selection is absent';
          END IF;
          IF NEW.run_kind = '{_CROP}' THEN
            IF selected_kind <> 'reference_curve_dataset_revision'
               OR selected_dataset_id <> NEW.input_dataset_id
               OR selected_dataset_revision_id <> NEW.input_dataset_revision_id THEN
              RAISE EXCEPTION USING ERRCODE = '23514',
                MESSAGE = 'crop Run input must equal its one-member Selection';
            END IF;
          ELSE
            IF selected_kind <> 'reference_tensile_replicate_set' OR NOT EXISTS (
              SELECT 1 FROM datasets.dataset_selection_member
              WHERE organization_id = NEW.organization_id AND project_id = NEW.project_id
                AND classification = NEW.classification
                AND selection_id = NEW.selection_id
                AND selection_revision_id = NEW.selection_revision_id
                AND ordinal = NEW.member_ordinal
                AND dataset_id = NEW.input_dataset_id
                AND dataset_revision_id = NEW.input_dataset_revision_id
            ) THEN
              RAISE EXCEPTION USING ERRCODE = '23514',
                MESSAGE = 'alignment Run input must equal its ordered replicate member';
            END IF;
          END IF;
          SELECT recipe_kind INTO selected_recipe_kind
          FROM processing.processing_recipe_revision
          WHERE organization_id = NEW.organization_id AND project_id = NEW.project_id
            AND classification = NEW.classification AND aggregate_id = NEW.recipe_id
            AND id = NEW.recipe_revision_id;
          IF selected_recipe_kind IS DISTINCT FROM NEW.run_kind THEN
            RAISE EXCEPTION USING ERRCODE = '23514',
              MESSAGE = 'Processing Run kind must match the typed Recipe revision';
          END IF;
          SELECT representation INTO selected_representation FROM datasets.dataset_revision
          WHERE organization_id = NEW.organization_id AND project_id = NEW.project_id
            AND classification = NEW.classification AND aggregate_id = NEW.input_dataset_id
            AND id = NEW.input_dataset_revision_id;
          IF selected_representation IS DISTINCT FROM 'normalized' THEN
            RAISE EXCEPTION USING ERRCODE = '23514',
              MESSAGE = 'Processing Run requires a normalized reference Dataset revision';
          END IF;
          RETURN NEW;
        END; $$
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION processing.guard_processing_run_transition()
        RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE output_run_id uuid; output_source_id uuid; output_artifact_id uuid;
          output_sha256 text;
        BEGIN
          IF TG_OP = 'DELETE' THEN
            RAISE EXCEPTION USING ERRCODE = '55000',
              MESSAGE = 'Processing Run rows are append-only and cannot be deleted';
          END IF;
          IF OLD.status <> 'executing' OR NEW.status NOT IN ('succeeded', 'failed') THEN
            RAISE EXCEPTION USING ERRCODE = '55000',
              MESSAGE = 'Processing Run may transition only once to a terminal state';
          END IF;
          IF NEW.organization_id IS DISTINCT FROM OLD.organization_id
             OR NEW.project_id IS DISTINCT FROM OLD.project_id
             OR NEW.classification IS DISTINCT FROM OLD.classification
             OR NEW.selection_id IS DISTINCT FROM OLD.selection_id
             OR NEW.selection_revision_id IS DISTINCT FROM OLD.selection_revision_id
             OR NEW.recipe_id IS DISTINCT FROM OLD.recipe_id
             OR NEW.recipe_revision_id IS DISTINCT FROM OLD.recipe_revision_id
             OR NEW.input_dataset_id IS DISTINCT FROM OLD.input_dataset_id
             OR NEW.input_dataset_revision_id IS DISTINCT FROM OLD.input_dataset_revision_id
             OR NEW.execution_mode IS DISTINCT FROM OLD.execution_mode
             OR NEW.input_point_count IS DISTINCT FROM OLD.input_point_count
             OR NEW.change_reason IS DISTINCT FROM OLD.change_reason
             OR NEW.started_at IS DISTINCT FROM OLD.started_at
             OR NEW.created_by IS DISTINCT FROM OLD.created_by
             OR NEW.request_id IS DISTINCT FROM OLD.request_id
             OR NEW.trace_id IS DISTINCT FROM OLD.trace_id
             OR NEW.run_kind IS DISTINCT FROM OLD.run_kind
             OR NEW.batch_id IS DISTINCT FROM OLD.batch_id
             OR NEW.member_ordinal IS DISTINCT FROM OLD.member_ordinal THEN
            RAISE EXCEPTION USING ERRCODE = '55000',
              MESSAGE = 'Processing Run plan and input snapshot are immutable';
          END IF;
          IF NEW.status = 'failed' AND EXISTS (
            SELECT 1 FROM datasets.dataset_revision
            WHERE organization_id = NEW.organization_id AND project_id = NEW.project_id
              AND classification = NEW.classification AND processing_run_id = NEW.id
          ) THEN
            RAISE EXCEPTION USING ERRCODE = '23514',
              MESSAGE = 'Processing Run with a committed Dataset cannot be failed';
          END IF;
          IF NEW.status = 'succeeded' THEN
            SELECT processing_run_id, source_dataset_revision_id, data_artifact_id, data_sha256
            INTO output_run_id, output_source_id, output_artifact_id, output_sha256
            FROM datasets.dataset_revision
            WHERE organization_id = NEW.organization_id AND project_id = NEW.project_id
              AND classification = NEW.classification
              AND aggregate_id = NEW.output_dataset_id AND id = NEW.output_dataset_revision_id
              AND representation = 'processed';
            IF NOT FOUND OR output_run_id <> NEW.id
               OR output_source_id <> NEW.input_dataset_revision_id
               OR output_artifact_id <> NEW.result_artifact_id
               OR output_sha256 <> NEW.result_sha256 THEN
              RAISE EXCEPTION USING ERRCODE = '23514',
                MESSAGE = 'Processing Run result must match its processed Dataset revision';
            END IF;
          END IF;
          RETURN NEW;
        END; $$
        """
    )


def downgrade() -> None:
    op.execute(
        f"""DO $$ BEGIN
          IF EXISTS (SELECT 1 FROM processing.processing_run WHERE run_kind = '{_ALIGN}')
             OR EXISTS (
               SELECT 1 FROM processing.processing_recipe WHERE recipe_kind = '{_ALIGN}'
             ) THEN
            RAISE EXCEPTION USING ERRCODE = '55000',
              MESSAGE = 'cannot downgrade while alignment recipes or runs exist';
          END IF;
        END $$"""
    )
    op.execute("DROP POLICY association_authorized_plan_finalization ON provenance.association")
    op.execute("DROP TRIGGER provenance_association_immutable ON provenance.association")
    op.execute("DROP FUNCTION provenance.guard_association_plan_finalization()")
    op.execute(
        "CREATE TRIGGER provenance_association_immutable BEFORE UPDATE OR DELETE "
        "ON provenance.association FOR EACH ROW "
        "EXECUTE FUNCTION revisioning.reject_immutable_row_mutation()"
    )
    _restore_activity_finalization_guard()
    op.execute("DROP TRIGGER processing_run_transition_guard ON processing.processing_run")
    op.execute("DROP TRIGGER processing_run_insert_guard ON processing.processing_run")
    op.execute("DROP FUNCTION processing.guard_processing_run_transition()")
    op.execute("DROP FUNCTION processing.guard_processing_run_insert()")
    op.execute("DROP INDEX processing.ux_processing_run_alignment_batch_member")
    op.execute(
        "ALTER TABLE processing.processing_run DROP CONSTRAINT ck_processing_run_terminal_shape, "
        "DROP CONSTRAINT ck_processing_run_group_shape, DROP CONSTRAINT ck_processing_run_kind, "
        "DROP COLUMN member_ordinal, DROP COLUMN batch_id, DROP COLUMN run_kind, "
        "ADD CONSTRAINT ck_processing_run_terminal_shape CHECK ("
        "(status = 'executing' AND ended_at IS NULL AND output_point_count IS NULL "
        " AND removed_point_count IS NULL AND result_artifact_id IS NULL "
        " AND output_dataset_id IS NULL AND output_dataset_revision_id IS NULL "
        " AND failure_code IS NULL) OR "
        "(status = 'succeeded' AND ended_at IS NOT NULL "
        " AND output_point_count BETWEEN 2 AND 100000 AND removed_point_count >= 0 "
        " AND output_point_count + removed_point_count = input_point_count "
        " AND result_artifact_id IS NOT NULL AND output_dataset_id IS NOT NULL "
        " AND output_dataset_revision_id IS NOT NULL AND failure_code IS NULL) OR "
        "(status = 'failed' AND ended_at IS NOT NULL AND output_point_count IS NULL "
        " AND removed_point_count IS NULL AND output_dataset_id IS NULL "
        " AND output_dataset_revision_id IS NULL "
        " AND length(btrim(failure_code)) BETWEEN 1 AND 100))"
    )
    op.execute(
        "ALTER TABLE processing.processing_recipe_revision "
        "DROP CONSTRAINT ck_processing_recipe_revision_typed_shape, "
        "DROP CONSTRAINT ck_processing_recipe_revision_kind, "
        "DROP COLUMN extrapolation_policy, DROP COLUMN interpolation_policy, "
        "DROP COLUMN domain_policy, DROP COLUMN grid_point_count, "
        "DROP COLUMN grid_end_engineering_strain, DROP COLUMN grid_start_engineering_strain, "
        "ALTER COLUMN minimum_engineering_strain SET NOT NULL, "
        "ALTER COLUMN maximum_engineering_strain SET NOT NULL, "
        f"ADD CONSTRAINT ck_processing_recipe_revision_kind CHECK (recipe_kind = '{_CROP}'), "
        "ADD CONSTRAINT ck_processing_recipe_revision_minimum CHECK "
        "(minimum_engineering_strain >= 0 AND minimum_engineering_strain < 'Infinity'::float8), "
        "ADD CONSTRAINT ck_processing_recipe_revision_maximum CHECK "
        "(maximum_engineering_strain > minimum_engineering_strain "
        " AND maximum_engineering_strain < 'Infinity'::float8), "
        "ADD CONSTRAINT ck_processing_recipe_revision_diagnostics_schema CHECK "
        f"(diagnostics_schema_ref = '{_CROP_DIAGNOSTICS}')"
    )
    op.execute(
        "ALTER TABLE processing.processing_recipe DROP CONSTRAINT ck_processing_recipe_kind, "
        f"ADD CONSTRAINT ck_processing_recipe_kind CHECK (recipe_kind = '{_CROP}')"
    )
    _restore_crop_run_guards()


def _restore_activity_finalization_guard() -> None:
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
        END; $$
        """
    )


def _restore_crop_run_guards() -> None:
    op.execute(
        f"""
        CREATE FUNCTION processing.guard_processing_run_insert()
        RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE selected_dataset_id uuid; selected_dataset_revision_id uuid;
          selected_representation text; selected_recipe_kind text;
        BEGIN
          SELECT dataset_id, dataset_revision_id
          INTO selected_dataset_id, selected_dataset_revision_id
          FROM datasets.dataset_selection_revision
          WHERE organization_id = NEW.organization_id AND project_id = NEW.project_id
            AND classification = NEW.classification AND aggregate_id = NEW.selection_id
            AND id = NEW.selection_revision_id;
          IF NOT FOUND OR selected_dataset_id <> NEW.input_dataset_id
             OR selected_dataset_revision_id <> NEW.input_dataset_revision_id THEN
            RAISE EXCEPTION USING ERRCODE = '23514',
              MESSAGE = 'Processing Run input must equal the pinned Selection revision member';
          END IF;
          SELECT recipe_kind INTO selected_recipe_kind
          FROM processing.processing_recipe_revision
          WHERE organization_id = NEW.organization_id AND project_id = NEW.project_id
            AND classification = NEW.classification AND aggregate_id = NEW.recipe_id
            AND id = NEW.recipe_revision_id;
          IF selected_recipe_kind IS DISTINCT FROM '{_CROP}' THEN
            RAISE EXCEPTION USING ERRCODE = '23514',
              MESSAGE = 'Processing Run requires the typed reference crop Recipe revision';
          END IF;
          SELECT representation INTO selected_representation FROM datasets.dataset_revision
          WHERE organization_id = NEW.organization_id AND project_id = NEW.project_id
            AND classification = NEW.classification AND aggregate_id = NEW.input_dataset_id
            AND id = NEW.input_dataset_revision_id;
          IF selected_representation IS DISTINCT FROM 'normalized' THEN
            RAISE EXCEPTION USING ERRCODE = '23514',
              MESSAGE = 'Processing Run requires a normalized reference Dataset revision';
          END IF;
          RETURN NEW;
        END; $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION processing.guard_processing_run_transition()
        RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE output_run_id uuid; output_source_id uuid; output_artifact_id uuid;
          output_sha256 text;
        BEGIN
          IF TG_OP = 'DELETE' THEN
            RAISE EXCEPTION USING ERRCODE = '55000',
              MESSAGE = 'Processing Run rows are append-only and cannot be deleted';
          END IF;
          IF OLD.status <> 'executing' OR NEW.status NOT IN ('succeeded', 'failed') THEN
            RAISE EXCEPTION USING ERRCODE = '55000',
              MESSAGE = 'Processing Run may transition only once from executing to terminal';
          END IF;
          IF NEW.organization_id IS DISTINCT FROM OLD.organization_id
             OR NEW.project_id IS DISTINCT FROM OLD.project_id
             OR NEW.classification IS DISTINCT FROM OLD.classification
             OR NEW.selection_id IS DISTINCT FROM OLD.selection_id
             OR NEW.selection_revision_id IS DISTINCT FROM OLD.selection_revision_id
             OR NEW.recipe_id IS DISTINCT FROM OLD.recipe_id
             OR NEW.recipe_revision_id IS DISTINCT FROM OLD.recipe_revision_id
             OR NEW.input_dataset_id IS DISTINCT FROM OLD.input_dataset_id
             OR NEW.input_dataset_revision_id IS DISTINCT FROM OLD.input_dataset_revision_id
             OR NEW.execution_mode IS DISTINCT FROM OLD.execution_mode
             OR NEW.input_point_count IS DISTINCT FROM OLD.input_point_count
             OR NEW.change_reason IS DISTINCT FROM OLD.change_reason
             OR NEW.started_at IS DISTINCT FROM OLD.started_at
             OR NEW.created_by IS DISTINCT FROM OLD.created_by
             OR NEW.request_id IS DISTINCT FROM OLD.request_id
             OR NEW.trace_id IS DISTINCT FROM OLD.trace_id THEN
            RAISE EXCEPTION USING ERRCODE = '55000',
              MESSAGE = 'Processing Run plan and input snapshot are immutable';
          END IF;
          IF NEW.status = 'failed' AND EXISTS (
            SELECT 1 FROM datasets.dataset_revision
            WHERE organization_id = NEW.organization_id AND project_id = NEW.project_id
              AND classification = NEW.classification AND processing_run_id = NEW.id
          ) THEN
            RAISE EXCEPTION USING ERRCODE = '23514',
              MESSAGE = 'Processing Run with a committed processed Dataset cannot be failed';
          END IF;
          IF NEW.status = 'succeeded' THEN
            SELECT processing_run_id, source_dataset_revision_id, data_artifact_id, data_sha256
            INTO output_run_id, output_source_id, output_artifact_id, output_sha256
            FROM datasets.dataset_revision
            WHERE organization_id = NEW.organization_id AND project_id = NEW.project_id
              AND classification = NEW.classification
              AND aggregate_id = NEW.output_dataset_id AND id = NEW.output_dataset_revision_id
              AND representation = 'processed';
            IF NOT FOUND OR output_run_id <> NEW.id
               OR output_source_id <> NEW.input_dataset_revision_id
               OR output_artifact_id <> NEW.result_artifact_id
               OR output_sha256 <> NEW.result_sha256 THEN
              RAISE EXCEPTION USING ERRCODE = '23514',
                MESSAGE = 'Processing Run result must match its processed Dataset revision';
            END IF;
          END IF;
          RETURN NEW;
        END; $$
        """
    )
    op.execute(
        "CREATE TRIGGER processing_run_insert_guard BEFORE INSERT "
        "ON processing.processing_run FOR EACH ROW "
        "EXECUTE FUNCTION processing.guard_processing_run_insert()"
    )
    op.execute(
        "CREATE TRIGGER processing_run_transition_guard BEFORE UPDATE OR DELETE "
        "ON processing.processing_run FOR EACH ROW "
        "EXECUTE FUNCTION processing.guard_processing_run_transition()"
    )

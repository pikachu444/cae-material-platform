"""Add typed append-only reference outlier candidate and assessment workflow.

Revision ID: 20260717_019_t21
Revises: 20260716_018_t20
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260717_019_t21"
down_revision: str | None = "20260716_018_t20"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ZERO = "'00000000-0000-0000-0000-000000000000'::uuid"
_DETECTION_KIND = "reference_tensile_pair_peak_difference_review"
_DETECTION_SCHEMA = "urn:cmp:statistics:reference-tensile-pair-outlier-detection-plan:1.0.0"
_ASSESSMENT_SCHEMA = "urn:cmp:statistics:reference-tensile-pair-outlier-assessment:1.0.0"
_RESULT_KIND = "reference_tensile_pair_scalar_and_curve"
_DETECTOR = "relative_peak_engineering_stress_difference"
_FORMULA_VERSION = "1.0.0"
_FEATURE = "peak_engineering_stress_pa"
_SCOPE_KIND = "reference_pair_analysis"


def _secure(table: str) -> None:
    for operation, predicate, permission in (
        ("select", "USING", "statistics.read"),
        ("insert", "WITH CHECK", "statistics.execute"),
    ):
        op.execute(
            f"CREATE POLICY statistics_{table}_{operation} ON statistics.{table} "
            f"FOR {operation.upper()} {predicate} (access_control.can_access_row("
            f"organization_id, project_id, classification, '{permission}'))"
        )
    op.execute(
        f"CREATE POLICY statistics_{table}_update ON statistics.{table} FOR UPDATE "
        "USING (access_control.can_access_row(organization_id, project_id, classification, "
        "'statistics.execute')) WITH CHECK (access_control.can_access_row(organization_id, "
        "project_id, classification, 'statistics.execute'))"
    )


def _create_tables() -> None:
    op.execute(
        f"""
        CREATE TABLE statistics.outlier_detection_plan (
          id uuid NOT NULL,
          organization_id uuid NOT NULL,
          project_id uuid NOT NULL,
          classification varchar(64) NOT NULL,
          current_revision_id uuid NOT NULL,
          created_at timestamptz NOT NULL,
          created_by uuid NOT NULL,
          updated_at timestamptz NOT NULL,
          plan_label varchar(160) NOT NULL,
          plan_kind varchar(100) NOT NULL,
          CONSTRAINT pk_statistics_outlier_detection_plan
            PRIMARY KEY (organization_id, project_id, id),
          CONSTRAINT uq_statistics_outlier_detection_plan_scope_identity
            UNIQUE (organization_id, project_id, classification, id),
          CONSTRAINT uq_statistics_outlier_detection_plan_label
            UNIQUE (organization_id, project_id, classification, plan_label),
          CONSTRAINT uq_statistics_outlier_detection_plan_identity_kind
            UNIQUE (organization_id, project_id, classification, id, plan_label, plan_kind),
          CONSTRAINT ck_statistics_outlier_detection_plan_nonzero_ids CHECK (
            id <> {_ZERO} AND current_revision_id <> {_ZERO} AND created_by <> {_ZERO}),
          CONSTRAINT ck_statistics_outlier_detection_plan_classification CHECK (
            classification ~ '^[a-z][a-z0-9_.-]{{0,63}}$'),
          CONSTRAINT ck_statistics_outlier_detection_plan_label CHECK (
            length(btrim(plan_label)) BETWEEN 1 AND 160 AND plan_label = btrim(plan_label)),
          CONSTRAINT ck_statistics_outlier_detection_plan_kind CHECK (
            plan_kind = '{_DETECTION_KIND}')
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE statistics.outlier_detection_plan_revision (
          id uuid NOT NULL,
          aggregate_id uuid NOT NULL,
          organization_id uuid NOT NULL,
          project_id uuid NOT NULL,
          classification varchar(64) NOT NULL,
          revision_no bigint NOT NULL,
          based_on_revision_id uuid NULL,
          schema_id varchar(255) NOT NULL,
          schema_version varchar(64) NOT NULL,
          content_hash char(64) COLLATE "C" NOT NULL,
          created_at timestamptz NOT NULL,
          created_by uuid NOT NULL,
          change_reason text NOT NULL,
          request_id uuid NOT NULL,
          trace_id varchar(255) NOT NULL,
          plan_kind varchar(100) NOT NULL,
          detector varchar(100) NOT NULL,
          formula_version varchar(64) NOT NULL,
          statistical_result_id uuid NOT NULL,
          statistical_result_revision_id uuid NOT NULL,
          statistical_result_kind varchar(100) NOT NULL,
          feature varchar(100) NOT NULL,
          relative_peak_difference_threshold double precision NOT NULL,
          candidate_policy varchar(100) NOT NULL,
          automatic_exclusion boolean NOT NULL,
          scope_kind varchar(100) NOT NULL,
          CONSTRAINT pk_statistics_outlier_detection_plan_revision
            PRIMARY KEY (organization_id, project_id, id),
          CONSTRAINT uq_statistics_outlier_detection_plan_revision_scope_id
            UNIQUE (organization_id, project_id, aggregate_id, id),
          CONSTRAINT uq_statistics_outlier_detection_plan_revision_scoped_ref
            UNIQUE (organization_id, project_id, classification, aggregate_id, id),
          CONSTRAINT uq_statistics_outlier_detection_plan_revision_number
            UNIQUE (organization_id, project_id, aggregate_id, revision_no),
          CONSTRAINT uq_statistics_outlier_detection_plan_revision_classified_id
            UNIQUE (organization_id, project_id, classification, id),
          CONSTRAINT ck_statistics_outlier_detection_plan_revision_nonzero_ids CHECK (
            id <> {_ZERO} AND aggregate_id <> {_ZERO} AND created_by <> {_ZERO}
            AND request_id <> {_ZERO} AND statistical_result_id <> {_ZERO}
            AND statistical_result_revision_id <> {_ZERO}),
          CONSTRAINT ck_statistics_outlier_detection_plan_revision_number CHECK (revision_no > 0),
          CONSTRAINT ck_statistics_outlier_detection_plan_revision_base CHECK (
            (revision_no = 1 AND based_on_revision_id IS NULL)
            OR (revision_no > 1 AND based_on_revision_id IS NOT NULL)),
          CONSTRAINT ck_statistics_outlier_detection_plan_revision_hash CHECK (
            content_hash ~ '^[0-9a-f]{{64}}$'),
          CONSTRAINT ck_statistics_outlier_detection_plan_revision_schema CHECK (
            schema_id = '{_DETECTION_SCHEMA}' AND schema_version = '{_FORMULA_VERSION}'),
          CONSTRAINT ck_statistics_outlier_detection_plan_revision_reason CHECK (
            length(btrim(change_reason)) BETWEEN 1 AND 2000),
          CONSTRAINT ck_statistics_outlier_detection_plan_revision_trace CHECK (
            length(btrim(trace_id)) BETWEEN 1 AND 255),
          CONSTRAINT ck_statistics_outlier_detection_plan_revision_classification CHECK (
            classification ~ '^[a-z][a-z0-9_.-]{{0,63}}$'),
          CONSTRAINT ck_statistics_outlier_detection_plan_revision_contract CHECK (
            plan_kind = '{_DETECTION_KIND}' AND detector = '{_DETECTOR}'
            AND formula_version = '{_FORMULA_VERSION}'
            AND statistical_result_kind = '{_RESULT_KIND}'
            AND feature = '{_FEATURE}'
            AND relative_peak_difference_threshold > 0
            AND relative_peak_difference_threshold <= 1
            AND candidate_policy = 'flag_both_pair_members_for_human_review'
            AND automatic_exclusion = false AND scope_kind = '{_SCOPE_KIND}'),
          CONSTRAINT fk_statistics_outlier_detection_plan_revision_identity FOREIGN KEY
            (organization_id, project_id, aggregate_id)
            REFERENCES statistics.outlier_detection_plan (organization_id, project_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_statistics_outlier_detection_plan_revision_identity_kind FOREIGN KEY
            (organization_id, project_id, classification, aggregate_id, plan_kind)
            REFERENCES statistics.outlier_detection_plan
              (organization_id, project_id, classification, id, plan_kind)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_statistics_outlier_detection_plan_revision_result FOREIGN KEY
            (organization_id, project_id, classification, statistical_result_id,
             statistical_result_revision_id)
            REFERENCES statistics.statistical_result_revision
              (organization_id, project_id, classification, aggregate_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_statistics_outlier_detection_plan_revision_base FOREIGN KEY
            (organization_id, project_id, aggregate_id, based_on_revision_id)
            REFERENCES statistics.outlier_detection_plan_revision
              (organization_id, project_id, aggregate_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED
        )
        """
    )
    op.execute(
        """
        ALTER TABLE statistics.outlier_detection_plan
          ADD CONSTRAINT fk_statistics_outlier_detection_plan_current_revision
          FOREIGN KEY (organization_id, project_id, id, current_revision_id)
          REFERENCES statistics.outlier_detection_plan_revision
            (organization_id, project_id, aggregate_id, id)
          ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED
        """
    )
    op.execute(
        f"""
        CREATE TABLE statistics.outlier_detection_run (
          id uuid NOT NULL,
          organization_id uuid NOT NULL,
          project_id uuid NOT NULL,
          classification varchar(64) NOT NULL,
          detection_plan_id uuid NOT NULL,
          detection_plan_revision_id uuid NOT NULL,
          statistical_result_id uuid NOT NULL,
          statistical_result_revision_id uuid NOT NULL,
          execution_mode varchar(16) NOT NULL,
          status varchar(16) NOT NULL,
          candidate_count smallint NOT NULL,
          failure_code varchar(100) NULL,
          change_reason text NOT NULL,
          started_at timestamptz NOT NULL,
          ended_at timestamptz NULL,
          created_by uuid NOT NULL,
          request_id uuid NOT NULL,
          trace_id varchar(255) NOT NULL,
          CONSTRAINT pk_statistics_outlier_detection_run
            PRIMARY KEY (organization_id, project_id, id),
          CONSTRAINT uq_statistics_outlier_detection_run_scope_identity
            UNIQUE (organization_id, project_id, classification, id),
          CONSTRAINT uq_statistics_outlier_detection_run_plan_revision
            UNIQUE (organization_id, project_id, classification, id, detection_plan_id,
                    detection_plan_revision_id),
          CONSTRAINT ck_statistics_outlier_detection_run_nonzero_ids CHECK (
            id <> {_ZERO} AND detection_plan_id <> {_ZERO}
            AND detection_plan_revision_id <> {_ZERO} AND statistical_result_id <> {_ZERO}
            AND statistical_result_revision_id <> {_ZERO} AND created_by <> {_ZERO}
            AND request_id <> {_ZERO}),
          CONSTRAINT ck_statistics_outlier_detection_run_classification CHECK (
            classification ~ '^[a-z][a-z0-9_.-]{{0,63}}$'),
          CONSTRAINT ck_statistics_outlier_detection_run_mode CHECK (execution_mode = 'committed'),
          CONSTRAINT ck_statistics_outlier_detection_run_status CHECK (
            status IN ('executing', 'succeeded', 'failed')),
          CONSTRAINT ck_statistics_outlier_detection_run_candidate_count CHECK (
            candidate_count IN (0, 2)),
          CONSTRAINT ck_statistics_outlier_detection_run_terminal_shape CHECK (
            (status = 'executing' AND ended_at IS NULL AND candidate_count = 0
             AND failure_code IS NULL) OR
            (status = 'succeeded' AND ended_at IS NOT NULL AND failure_code IS NULL) OR
            (status = 'failed' AND ended_at IS NOT NULL AND candidate_count = 0
             AND length(btrim(failure_code)) BETWEEN 1 AND 100)),
          CONSTRAINT ck_statistics_outlier_detection_run_time CHECK (
            ended_at IS NULL OR ended_at >= started_at),
          CONSTRAINT ck_statistics_outlier_detection_run_reason CHECK (
            length(btrim(change_reason)) BETWEEN 1 AND 2000),
          CONSTRAINT ck_statistics_outlier_detection_run_trace CHECK (
            length(btrim(trace_id)) BETWEEN 1 AND 255),
          CONSTRAINT fk_statistics_outlier_detection_run_plan FOREIGN KEY
            (organization_id, project_id, classification, detection_plan_id,
             detection_plan_revision_id)
            REFERENCES statistics.outlier_detection_plan_revision
              (organization_id, project_id, classification, aggregate_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_statistics_outlier_detection_run_result FOREIGN KEY
            (organization_id, project_id, classification, statistical_result_id,
             statistical_result_revision_id)
            REFERENCES statistics.statistical_result_revision
              (organization_id, project_id, classification, aggregate_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE statistics.outlier_candidate (
          id uuid NOT NULL,
          organization_id uuid NOT NULL,
          project_id uuid NOT NULL,
          classification varchar(64) NOT NULL,
          detection_run_id uuid NOT NULL,
          detection_plan_id uuid NOT NULL,
          detection_plan_revision_id uuid NOT NULL,
          statistical_result_id uuid NOT NULL,
          statistical_result_revision_id uuid NOT NULL,
          statistical_plan_id uuid NOT NULL,
          statistical_plan_revision_id uuid NOT NULL,
          selection_id uuid NOT NULL,
          selection_revision_id uuid NOT NULL,
          dataset_id uuid NOT NULL,
          dataset_revision_id uuid NOT NULL,
          pair_position varchar(16) NOT NULL,
          peak_engineering_stress_pa double precision NOT NULL,
          peer_peak_engineering_stress_pa double precision NOT NULL,
          relative_peak_difference double precision NOT NULL,
          relative_peak_difference_threshold double precision NOT NULL,
          status varchar(32) NOT NULL,
          recorded_at timestamptz NOT NULL,
          recorded_by uuid NOT NULL,
          CONSTRAINT pk_statistics_outlier_candidate
            PRIMARY KEY (organization_id, project_id, id),
          CONSTRAINT uq_statistics_outlier_candidate_scope_identity
            UNIQUE (organization_id, project_id, classification, id),
          CONSTRAINT uq_statistics_outlier_candidate_run_position
            UNIQUE (organization_id, project_id, detection_run_id, pair_position),
          CONSTRAINT ck_statistics_outlier_candidate_nonzero_ids CHECK (
            id <> {_ZERO} AND detection_run_id <> {_ZERO} AND detection_plan_id <> {_ZERO}
            AND detection_plan_revision_id <> {_ZERO} AND statistical_result_id <> {_ZERO}
            AND statistical_result_revision_id <> {_ZERO} AND statistical_plan_id <> {_ZERO}
            AND statistical_plan_revision_id <> {_ZERO} AND selection_id <> {_ZERO}
            AND selection_revision_id <> {_ZERO} AND dataset_id <> {_ZERO}
            AND dataset_revision_id <> {_ZERO} AND recorded_by <> {_ZERO}),
          CONSTRAINT ck_statistics_outlier_candidate_classification CHECK (
            classification ~ '^[a-z][a-z0-9_.-]{{0,63}}$'),
          CONSTRAINT ck_statistics_outlier_candidate_position CHECK (
            pair_position IN ('first', 'second')),
          CONSTRAINT ck_statistics_outlier_candidate_values CHECK (
            isfinite(peak_engineering_stress_pa) AND peak_engineering_stress_pa >= 0
            AND isfinite(peer_peak_engineering_stress_pa)
            AND peer_peak_engineering_stress_pa >= 0
            AND isfinite(relative_peak_difference)
            AND relative_peak_difference BETWEEN 0 AND 1
            AND isfinite(relative_peak_difference_threshold)
            AND relative_peak_difference_threshold > 0
            AND relative_peak_difference_threshold <= 1
            AND relative_peak_difference >= relative_peak_difference_threshold),
          CONSTRAINT ck_statistics_outlier_candidate_status CHECK (
            status = 'review_required'),
          CONSTRAINT fk_statistics_outlier_candidate_run FOREIGN KEY
            (organization_id, project_id, classification, detection_run_id)
            REFERENCES statistics.outlier_detection_run
              (organization_id, project_id, classification, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_statistics_outlier_candidate_plan FOREIGN KEY
            (organization_id, project_id, classification, detection_plan_id,
             detection_plan_revision_id)
            REFERENCES statistics.outlier_detection_plan_revision
              (organization_id, project_id, classification, aggregate_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_statistics_outlier_candidate_result FOREIGN KEY
            (organization_id, project_id, classification, statistical_result_id,
             statistical_result_revision_id)
            REFERENCES statistics.statistical_result_revision
              (organization_id, project_id, classification, aggregate_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_statistics_outlier_candidate_plan_scope FOREIGN KEY
            (organization_id, project_id, classification, statistical_plan_id,
             statistical_plan_revision_id)
            REFERENCES statistics.statistical_plan_revision
              (organization_id, project_id, classification, aggregate_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_statistics_outlier_candidate_selection FOREIGN KEY
            (organization_id, project_id, classification, selection_id, selection_revision_id)
            REFERENCES datasets.dataset_selection_revision
              (organization_id, project_id, classification, aggregate_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_statistics_outlier_candidate_dataset FOREIGN KEY
            (organization_id, project_id, classification, dataset_id, dataset_revision_id)
            REFERENCES datasets.dataset_revision
              (organization_id, project_id, classification, aggregate_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE statistics.outlier_assessment (
          id uuid NOT NULL,
          organization_id uuid NOT NULL,
          project_id uuid NOT NULL,
          classification varchar(64) NOT NULL,
          current_revision_id uuid NOT NULL,
          created_at timestamptz NOT NULL,
          created_by uuid NOT NULL,
          updated_at timestamptz NOT NULL,
          candidate_id uuid NOT NULL,
          scope_kind varchar(100) NOT NULL,
          CONSTRAINT pk_statistics_outlier_assessment
            PRIMARY KEY (organization_id, project_id, id),
          CONSTRAINT uq_statistics_outlier_assessment_scope_identity
            UNIQUE (organization_id, project_id, classification, id),
          CONSTRAINT uq_statistics_outlier_assessment_identity_scope
            UNIQUE (organization_id, project_id, classification, id, candidate_id, scope_kind),
          CONSTRAINT ck_statistics_outlier_assessment_nonzero_ids CHECK (
            id <> {_ZERO} AND current_revision_id <> {_ZERO} AND candidate_id <> {_ZERO}
            AND created_by <> {_ZERO}),
          CONSTRAINT ck_statistics_outlier_assessment_classification CHECK (
            classification ~ '^[a-z][a-z0-9_.-]{{0,63}}$'),
          CONSTRAINT ck_statistics_outlier_assessment_scope_kind CHECK (
            scope_kind = '{_SCOPE_KIND}')
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE statistics.outlier_assessment_revision (
          id uuid NOT NULL,
          aggregate_id uuid NOT NULL,
          organization_id uuid NOT NULL,
          project_id uuid NOT NULL,
          classification varchar(64) NOT NULL,
          revision_no bigint NOT NULL,
          based_on_revision_id uuid NULL,
          schema_id varchar(255) NOT NULL,
          schema_version varchar(64) NOT NULL,
          content_hash char(64) COLLATE "C" NOT NULL,
          created_at timestamptz NOT NULL,
          created_by uuid NOT NULL,
          change_reason text NOT NULL,
          request_id uuid NOT NULL,
          trace_id varchar(255) NOT NULL,
          candidate_id uuid NOT NULL,
          scope_kind varchar(100) NOT NULL,
          statistical_plan_id uuid NOT NULL,
          statistical_plan_revision_id uuid NOT NULL,
          decision varchar(100) NOT NULL,
          assessment_reason text NOT NULL,
          CONSTRAINT pk_statistics_outlier_assessment_revision
            PRIMARY KEY (organization_id, project_id, id),
          CONSTRAINT uq_statistics_outlier_assessment_revision_scope_id
            UNIQUE (organization_id, project_id, aggregate_id, id),
          CONSTRAINT uq_statistics_outlier_assessment_revision_scoped_ref
            UNIQUE (organization_id, project_id, classification, aggregate_id, id),
          CONSTRAINT uq_statistics_outlier_assessment_revision_number
            UNIQUE (organization_id, project_id, aggregate_id, revision_no),
          CONSTRAINT uq_statistics_outlier_assessment_revision_classified_id
            UNIQUE (organization_id, project_id, classification, id),
          CONSTRAINT ck_statistics_outlier_assessment_revision_nonzero_ids CHECK (
            id <> {_ZERO} AND aggregate_id <> {_ZERO} AND created_by <> {_ZERO}
            AND request_id <> {_ZERO} AND candidate_id <> {_ZERO}
            AND statistical_plan_id <> {_ZERO} AND statistical_plan_revision_id <> {_ZERO}),
          CONSTRAINT ck_statistics_outlier_assessment_revision_first_only CHECK (
            revision_no = 1 AND based_on_revision_id IS NULL),
          CONSTRAINT ck_statistics_outlier_assessment_revision_hash CHECK (
            content_hash ~ '^[0-9a-f]{{64}}$'),
          CONSTRAINT ck_statistics_outlier_assessment_revision_schema CHECK (
            schema_id = '{_ASSESSMENT_SCHEMA}' AND schema_version = '{_FORMULA_VERSION}'),
          CONSTRAINT ck_statistics_outlier_assessment_revision_reason CHECK (
            length(btrim(change_reason)) BETWEEN 1 AND 2000
            AND length(btrim(assessment_reason)) BETWEEN 1 AND 2000),
          CONSTRAINT ck_statistics_outlier_assessment_revision_trace CHECK (
            length(btrim(trace_id)) BETWEEN 1 AND 255),
          CONSTRAINT ck_statistics_outlier_assessment_revision_classification CHECK (
            classification ~ '^[a-z][a-z0-9_.-]{{0,63}}$'),
          CONSTRAINT ck_statistics_outlier_assessment_revision_scope_kind CHECK (
            scope_kind = '{_SCOPE_KIND}'),
          CONSTRAINT ck_statistics_outlier_assessment_revision_decision CHECK (
            decision IN ('retained', 'excluded_from_reference_analysis')),
          CONSTRAINT fk_statistics_outlier_assessment_revision_identity FOREIGN KEY
            (organization_id, project_id, aggregate_id)
            REFERENCES statistics.outlier_assessment (organization_id, project_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_statistics_outlier_assessment_revision_identity_scope FOREIGN KEY
            (organization_id, project_id, classification, aggregate_id, candidate_id, scope_kind)
            REFERENCES statistics.outlier_assessment
              (organization_id, project_id, classification, id, candidate_id, scope_kind)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_statistics_outlier_assessment_revision_candidate FOREIGN KEY
            (organization_id, project_id, classification, candidate_id)
            REFERENCES statistics.outlier_candidate
              (organization_id, project_id, classification, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_statistics_outlier_assessment_revision_plan FOREIGN KEY
            (organization_id, project_id, classification, statistical_plan_id,
             statistical_plan_revision_id)
            REFERENCES statistics.statistical_plan_revision
              (organization_id, project_id, classification, aggregate_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED
        )
        """
    )
    op.execute(
        """
        ALTER TABLE statistics.outlier_assessment
          ADD CONSTRAINT fk_statistics_outlier_assessment_current_revision
          FOREIGN KEY (organization_id, project_id, id, current_revision_id)
          REFERENCES statistics.outlier_assessment_revision
            (organization_id, project_id, aggregate_id, id)
          ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED
        """
    )


def _create_guards() -> None:
    op.execute(
        f"""
        CREATE FUNCTION statistics.guard_outlier_detection_plan_revision_insert()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF NOT EXISTS (
            SELECT 1 FROM statistics.statistical_result_revision result
            WHERE result.organization_id = NEW.organization_id
              AND result.project_id = NEW.project_id
              AND result.classification = NEW.classification
              AND result.aggregate_id = NEW.statistical_result_id
              AND result.id = NEW.statistical_result_revision_id
              AND result.result_kind = '{_RESULT_KIND}') THEN
            RAISE EXCEPTION USING ERRCODE = '23514',
              MESSAGE = 'Outlier Detection Plan requires a successful immutable reference result';
          END IF;
          RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION statistics.guard_outlier_detection_run_insert()
        RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE
          pinned_result_id uuid;
          pinned_result_revision_id uuid;
        BEGIN
          SELECT statistical_result_id, statistical_result_revision_id
          INTO pinned_result_id, pinned_result_revision_id
          FROM statistics.outlier_detection_plan_revision
          WHERE organization_id = NEW.organization_id
            AND project_id = NEW.project_id
            AND classification = NEW.classification
            AND aggregate_id = NEW.detection_plan_id
            AND id = NEW.detection_plan_revision_id;
          IF pinned_result_id IS DISTINCT FROM NEW.statistical_result_id
             OR pinned_result_revision_id IS DISTINCT FROM NEW.statistical_result_revision_id THEN
            RAISE EXCEPTION USING ERRCODE = '23514',
              MESSAGE = 'Outlier Detection Run must equal its pinned Detection Plan result';
          END IF;
          RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION statistics.guard_outlier_detection_run_transition()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF TG_OP = 'DELETE' THEN
            RAISE EXCEPTION USING ERRCODE = '55000',
              MESSAGE = 'Outlier Detection Run rows are append-only and cannot be deleted';
          END IF;
          IF OLD.status <> 'executing' OR NEW.status NOT IN ('succeeded', 'failed') THEN
            RAISE EXCEPTION USING ERRCODE = '55000',
              MESSAGE = 'Outlier Detection Run may transition only once to a terminal state';
          END IF;
          IF NEW.organization_id IS DISTINCT FROM OLD.organization_id
             OR NEW.project_id IS DISTINCT FROM OLD.project_id
             OR NEW.classification IS DISTINCT FROM OLD.classification
             OR NEW.detection_plan_id IS DISTINCT FROM OLD.detection_plan_id
             OR NEW.detection_plan_revision_id IS DISTINCT FROM OLD.detection_plan_revision_id
             OR NEW.statistical_result_id IS DISTINCT FROM OLD.statistical_result_id
             OR NEW.statistical_result_revision_id
                IS DISTINCT FROM OLD.statistical_result_revision_id
             OR NEW.execution_mode IS DISTINCT FROM OLD.execution_mode
             OR NEW.change_reason IS DISTINCT FROM OLD.change_reason
             OR NEW.started_at IS DISTINCT FROM OLD.started_at
             OR NEW.created_by IS DISTINCT FROM OLD.created_by
             OR NEW.request_id IS DISTINCT FROM OLD.request_id
             OR NEW.trace_id IS DISTINCT FROM OLD.trace_id THEN
            RAISE EXCEPTION USING ERRCODE = '55000',
              MESSAGE = 'Outlier Detection Run input snapshot is immutable';
          END IF;
          RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION statistics.guard_outlier_candidate_insert()
        RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE
          run statistics.outlier_detection_run%ROWTYPE;
          plan statistics.outlier_detection_plan_revision%ROWTYPE;
          result statistics.statistical_result_revision%ROWTYPE;
          expected_peak double precision;
          expected_peer_peak double precision;
          expected_selection_id uuid;
          expected_selection_revision_id uuid;
          expected_dataset_id uuid;
          expected_dataset_revision_id uuid;
          expected_difference double precision;
        BEGIN
          SELECT * INTO run FROM statistics.outlier_detection_run
          WHERE organization_id = NEW.organization_id AND project_id = NEW.project_id
            AND classification = NEW.classification AND id = NEW.detection_run_id;
          IF NOT FOUND THEN
            RAISE EXCEPTION USING ERRCODE = '23514',
              MESSAGE = 'Outlier Candidate requires its Detection Run';
          END IF;
          SELECT * INTO plan FROM statistics.outlier_detection_plan_revision
          WHERE organization_id = NEW.organization_id AND project_id = NEW.project_id
            AND classification = NEW.classification AND aggregate_id = NEW.detection_plan_id
            AND id = NEW.detection_plan_revision_id;
          IF NOT FOUND THEN
            RAISE EXCEPTION USING ERRCODE = '23514',
              MESSAGE = 'Outlier Candidate requires its Detection Plan revision';
          END IF;
          SELECT * INTO result FROM statistics.statistical_result_revision
          WHERE organization_id = NEW.organization_id AND project_id = NEW.project_id
            AND classification = NEW.classification AND aggregate_id = NEW.statistical_result_id
            AND id = NEW.statistical_result_revision_id;
          IF NOT FOUND OR run.status <> 'succeeded'
             OR run.detection_plan_id <> NEW.detection_plan_id
             OR run.detection_plan_revision_id <> NEW.detection_plan_revision_id
             OR run.statistical_result_id <> NEW.statistical_result_id
             OR run.statistical_result_revision_id <> NEW.statistical_result_revision_id
             OR plan.relative_peak_difference_threshold
                <> NEW.relative_peak_difference_threshold THEN
            RAISE EXCEPTION USING ERRCODE = '23514',
              MESSAGE = 'Outlier Candidate must be created only for its terminal pinned run';
          END IF;
          IF NEW.pair_position = 'first' THEN
            expected_peak := result.first_peak_engineering_stress_pa;
            expected_peer_peak := result.second_peak_engineering_stress_pa;
            expected_selection_id := result.first_selection_id;
            expected_selection_revision_id := result.first_selection_revision_id;
            expected_dataset_id := result.first_dataset_id;
            expected_dataset_revision_id := result.first_dataset_revision_id;
          ELSE
            expected_peak := result.second_peak_engineering_stress_pa;
            expected_peer_peak := result.first_peak_engineering_stress_pa;
            expected_selection_id := result.second_selection_id;
            expected_selection_revision_id := result.second_selection_revision_id;
            expected_dataset_id := result.second_dataset_id;
            expected_dataset_revision_id := result.second_dataset_revision_id;
          END IF;
          expected_difference := CASE WHEN greatest(expected_peak, expected_peer_peak) = 0
            THEN 0 ELSE abs(expected_peak - expected_peer_peak)
              / greatest(expected_peak, expected_peer_peak) END;
          IF NEW.statistical_plan_id <> result.plan_id
             OR NEW.statistical_plan_revision_id <> result.plan_revision_id
             OR NEW.selection_id <> expected_selection_id
             OR NEW.selection_revision_id <> expected_selection_revision_id
             OR NEW.dataset_id <> expected_dataset_id
             OR NEW.dataset_revision_id <> expected_dataset_revision_id
             OR NEW.peak_engineering_stress_pa <> expected_peak
             OR NEW.peer_peak_engineering_stress_pa <> expected_peer_peak
             OR NEW.relative_peak_difference <> expected_difference
             OR NEW.relative_peak_difference < NEW.relative_peak_difference_threshold THEN
            RAISE EXCEPTION USING ERRCODE = '23514',
              MESSAGE = 'Outlier Candidate must equal immutable result evidence';
          END IF;
          RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        f"""
        CREATE FUNCTION statistics.guard_outlier_assessment_revision_insert()
        RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE
          candidate statistics.outlier_candidate%ROWTYPE;
        BEGIN
          SELECT * INTO candidate FROM statistics.outlier_candidate
          WHERE organization_id = NEW.organization_id AND project_id = NEW.project_id
            AND classification = NEW.classification AND id = NEW.candidate_id;
          IF NOT FOUND OR candidate.statistical_plan_id <> NEW.statistical_plan_id
             OR candidate.statistical_plan_revision_id <> NEW.statistical_plan_revision_id
             OR NEW.scope_kind <> '{_SCOPE_KIND}' THEN
            RAISE EXCEPTION USING ERRCODE = '23514',
              MESSAGE = 'Outlier Assessment must use the candidate immutable reference scope';
          END IF;
          RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION statistics.validate_outlier_detection_run_candidate_count()
        RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE
          target_run_id uuid;
          target_organization_id uuid;
          target_project_id uuid;
          stored_status varchar(16);
          stored_candidate_count smallint;
          actual_candidate_count integer;
        BEGIN
          IF TG_OP = 'DELETE' THEN
            target_organization_id := OLD.organization_id;
            target_project_id := OLD.project_id;
            target_run_id := CASE
              WHEN TG_TABLE_NAME = 'outlier_detection_run' THEN OLD.id
              ELSE OLD.detection_run_id
            END;
          ELSE
            target_organization_id := NEW.organization_id;
            target_project_id := NEW.project_id;
            target_run_id := CASE
              WHEN TG_TABLE_NAME = 'outlier_detection_run' THEN NEW.id
              ELSE NEW.detection_run_id
            END;
          END IF;
          SELECT status, candidate_count
          INTO stored_status, stored_candidate_count
          FROM statistics.outlier_detection_run
          WHERE organization_id = target_organization_id
            AND project_id = target_project_id
            AND id = target_run_id;
          IF NOT FOUND THEN
            RETURN NULL;
          END IF;
          SELECT count(*) INTO actual_candidate_count
          FROM statistics.outlier_candidate
          WHERE organization_id = target_organization_id
            AND project_id = target_project_id
            AND detection_run_id = target_run_id;
          IF (stored_status = 'succeeded' AND actual_candidate_count <> stored_candidate_count)
             OR (stored_status <> 'succeeded' AND actual_candidate_count <> 0) THEN
            RAISE EXCEPTION USING ERRCODE = '23514',
              MESSAGE =
                'Outlier Detection Run candidate count must match immutable candidate facts';
          END IF;
          RETURN NULL;
        END;
        $$
        """
    )
    for trigger, table, function in (
        (
            "statistics_outlier_detection_plan_revision_guard",
            "outlier_detection_plan_revision",
            "guard_outlier_detection_plan_revision_insert",
        ),
        (
            "statistics_outlier_detection_run_insert_guard",
            "outlier_detection_run",
            "guard_outlier_detection_run_insert",
        ),
        (
            "statistics_outlier_candidate_insert_guard",
            "outlier_candidate",
            "guard_outlier_candidate_insert",
        ),
        (
            "statistics_outlier_assessment_revision_guard",
            "outlier_assessment_revision",
            "guard_outlier_assessment_revision_insert",
        ),
    ):
        op.execute(
            f"CREATE TRIGGER {trigger} BEFORE INSERT ON statistics.{table} FOR EACH ROW "
            f"EXECUTE FUNCTION statistics.{function}()"
        )
    op.execute(
        "CREATE TRIGGER statistics_outlier_detection_run_transition_guard BEFORE UPDATE OR DELETE "
        "ON statistics.outlier_detection_run FOR EACH ROW "
        "EXECUTE FUNCTION statistics.guard_outlier_detection_run_transition()"
    )
    op.execute(
        "CREATE CONSTRAINT TRIGGER statistics_outlier_detection_run_candidate_count_guard "
        "AFTER INSERT OR UPDATE OR DELETE ON statistics.outlier_detection_run "
        "DEFERRABLE INITIALLY DEFERRED FOR EACH ROW "
        "EXECUTE FUNCTION statistics.validate_outlier_detection_run_candidate_count()"
    )
    op.execute(
        "CREATE CONSTRAINT TRIGGER statistics_outlier_candidate_count_guard "
        "AFTER INSERT OR UPDATE OR DELETE ON statistics.outlier_candidate "
        "DEFERRABLE INITIALLY DEFERRED FOR EACH ROW "
        "EXECUTE FUNCTION statistics.validate_outlier_detection_run_candidate_count()"
    )


def upgrade() -> None:
    _create_tables()
    for table in (
        "outlier_detection_plan",
        "outlier_detection_plan_revision",
        "outlier_detection_run",
        "outlier_candidate",
        "outlier_assessment",
        "outlier_assessment_revision",
    ):
        op.execute(f"ALTER TABLE statistics.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE statistics.{table} FORCE ROW LEVEL SECURITY")
        _secure(table)
    for table in ("outlier_detection_plan", "outlier_assessment"):
        op.execute(
            f"CREATE TRIGGER statistics_{table}_head_only BEFORE UPDATE OR DELETE "
            f"ON statistics.{table} FOR EACH ROW "
            "EXECUTE FUNCTION revisioning.guard_identity_head_update()"
        )
    for table in (
        "outlier_detection_plan_revision",
        "outlier_assessment_revision",
        "outlier_candidate",
    ):
        op.execute(
            f"CREATE TRIGGER statistics_{table}_immutable BEFORE UPDATE OR DELETE "
            f"ON statistics.{table} FOR EACH ROW "
            "EXECUTE FUNCTION revisioning.reject_immutable_row_mutation()"
        )
    _create_guards()
    for name, table, columns in (
        (
            "ix_statistics_outlier_detection_plan_created",
            "outlier_detection_plan",
            ["organization_id", "project_id", "classification", "created_at"],
        ),
        (
            "ix_statistics_outlier_detection_plan_result",
            "outlier_detection_plan_revision",
            [
                "organization_id",
                "project_id",
                "classification",
                "statistical_result_revision_id",
            ],
        ),
        (
            "ix_statistics_outlier_detection_run_plan",
            "outlier_detection_run",
            [
                "organization_id",
                "project_id",
                "classification",
                "detection_plan_revision_id",
            ],
        ),
        (
            "ix_statistics_outlier_candidate_run",
            "outlier_candidate",
            ["organization_id", "project_id", "classification", "detection_run_id"],
        ),
        (
            "ix_statistics_outlier_candidate_plan",
            "outlier_candidate",
            [
                "organization_id",
                "project_id",
                "classification",
                "detection_plan_revision_id",
                "pair_position",
            ],
        ),
        (
            "ix_statistics_outlier_candidate_selection",
            "outlier_candidate",
            ["organization_id", "project_id", "classification", "selection_revision_id"],
        ),
        (
            "ix_statistics_outlier_assessment_candidate_scope",
            "outlier_assessment_revision",
            [
                "organization_id",
                "project_id",
                "classification",
                "candidate_id",
                "statistical_plan_revision_id",
                "created_at",
            ],
        ),
    ):
        op.create_index(name, table, columns, schema="statistics")


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM statistics.outlier_detection_plan)
             OR EXISTS (SELECT 1 FROM statistics.outlier_detection_run)
             OR EXISTS (SELECT 1 FROM statistics.outlier_candidate)
             OR EXISTS (SELECT 1 FROM statistics.outlier_assessment) THEN
            RAISE EXCEPTION 'cannot downgrade T-21 while outlier evidence exists';
          END IF;
        END;
        $$
    """
    )
    for trigger, table in (
        ("statistics_outlier_candidate_count_guard", "outlier_candidate"),
        ("statistics_outlier_detection_run_candidate_count_guard", "outlier_detection_run"),
        ("statistics_outlier_detection_run_transition_guard", "outlier_detection_run"),
        ("statistics_outlier_assessment_revision_guard", "outlier_assessment_revision"),
        ("statistics_outlier_candidate_insert_guard", "outlier_candidate"),
        ("statistics_outlier_detection_run_insert_guard", "outlier_detection_run"),
        ("statistics_outlier_detection_plan_revision_guard", "outlier_detection_plan_revision"),
        ("statistics_outlier_candidate_immutable", "outlier_candidate"),
        ("statistics_outlier_assessment_revision_immutable", "outlier_assessment_revision"),
        ("statistics_outlier_detection_plan_revision_immutable", "outlier_detection_plan_revision"),
        ("statistics_outlier_assessment_head_only", "outlier_assessment"),
        ("statistics_outlier_detection_plan_head_only", "outlier_detection_plan"),
    ):
        op.execute(f"DROP TRIGGER {trigger} ON statistics.{table}")
    for function in (
        "validate_outlier_detection_run_candidate_count",
        "guard_outlier_assessment_revision_insert",
        "guard_outlier_candidate_insert",
        "guard_outlier_detection_run_transition",
        "guard_outlier_detection_run_insert",
        "guard_outlier_detection_plan_revision_insert",
    ):
        op.execute(f"DROP FUNCTION statistics.{function}()")
    for table in (
        "outlier_assessment_revision",
        "outlier_assessment",
        "outlier_candidate",
        "outlier_detection_run",
        "outlier_detection_plan_revision",
        "outlier_detection_plan",
    ):
        op.drop_table(table, schema="statistics")

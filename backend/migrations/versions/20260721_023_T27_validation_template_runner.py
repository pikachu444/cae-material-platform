"""Add immutable reference Validation templates, Plans, runs, and Result Manifests.

Revision ID: 20260721_023_t27
Revises: 20260720_022_t24
"""

# ruff: noqa: E501

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260721_023_t27"
down_revision: str | None = "20260720_022_t24"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ZERO = "'00000000-0000-0000-0000-000000000000'::uuid"
_TEMPLATE_SCHEMA = "urn:cmp:validation:reference-uniaxial-virtual-specimen:1.0.0"
_PLAN_SCHEMA = "urn:cmp:validation:reference-uniaxial-validation-plan:1.0.0"
_TEMPLATE_KIND = "reference_uniaxial_tensile_virtual_specimen"
_PLAN_KIND = "reference_uniaxial_tensile_validation"
_TARGET_SOLVER = "openradioss"
_TARGET_VERSION = "2025"
_TARGET_UNITS = "kg_m_s"
_RUNNER_ID = "cmp.reference.inline-mock-runner"
_RUNNER_VERSION = "1.0.0"
_RUNNER_DIGEST = "c7ddb0df83e2304d7f0d754f1a8b94d0774d00b9fe434db853fbb21effcd0209"
_RUNNER_COMMAND = "reference_inline_mock"
_EXTRACTION_PROFILE = "urn:cmp:validation:reference-native-curve-extractor:1.0.0"
_METRIC_PROFILE = "urn:cmp:validation:reference-relative-rmse:1.0.0"
_DECK_SCHEMA = "urn:cmp:validation:reference-deck:1.0.0"
_STDOUT_SCHEMA = "urn:cmp:validation:reference-runner-stdout:1.0.0"
_STDERR_SCHEMA = "urn:cmp:validation:reference-runner-stderr:1.0.0"
_NATIVE_SCHEMA = "urn:cmp:validation:reference-native-result:1.0.0"
_MANIFEST_SCHEMA = "urn:cmp:validation:run-result-manifest:1.0.0"


def _secure(table: str) -> None:
    for operation, predicate, permission in (
        ("select", "USING", "validation.read"),
        ("insert", "WITH CHECK", "validation.execute"),
    ):
        op.execute(
            f"CREATE POLICY validation_{table}_{operation} ON validation.{table} "
            f"FOR {operation.upper()} {predicate} (access_control.can_access_row("
            f"organization_id, project_id, classification, '{permission}'))"
        )
    op.execute(
        f"CREATE POLICY validation_{table}_update ON validation.{table} FOR UPDATE "
        "USING (access_control.can_access_row(organization_id, project_id, classification, "
        "'validation.execute')) WITH CHECK (access_control.can_access_row("
        "organization_id, project_id, classification, 'validation.execute'))"
    )


def _create_template_tables() -> None:
    op.execute(
        f"""
        CREATE TABLE validation.validation_template (
          id uuid NOT NULL,
          organization_id uuid NOT NULL,
          project_id uuid NOT NULL,
          classification varchar(64) NOT NULL,
          current_revision_id uuid NOT NULL,
          created_at timestamptz NOT NULL,
          created_by uuid NOT NULL,
          updated_at timestamptz NOT NULL,
          template_label varchar(160) NOT NULL,
          template_kind varchar(100) NOT NULL,
          CONSTRAINT pk_validation_template PRIMARY KEY (organization_id, project_id, id),
          CONSTRAINT uq_validation_template_scope_identity
            UNIQUE (organization_id, project_id, classification, id),
          CONSTRAINT uq_validation_template_label
            UNIQUE (organization_id, project_id, classification, template_label),
          CONSTRAINT uq_validation_template_identity_kind
            UNIQUE (organization_id, project_id, classification, id, template_kind),
          CONSTRAINT ck_validation_template_nonzero_ids CHECK (
            id <> {_ZERO} AND current_revision_id <> {_ZERO} AND created_by <> {_ZERO}),
          CONSTRAINT ck_validation_template_classification CHECK (
            classification ~ '^[a-z][a-z0-9_.-]{{0,63}}$'),
          CONSTRAINT ck_validation_template_label CHECK (
            length(btrim(template_label)) BETWEEN 1 AND 160
            AND template_label = btrim(template_label)),
          CONSTRAINT ck_validation_template_kind CHECK (
            template_kind = '{_TEMPLATE_KIND}')
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE validation.validation_template_revision (
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
          template_kind varchar(100) NOT NULL,
          gauge_length_m double precision NOT NULL,
          cross_section_area_m2 double precision NOT NULL,
          axial_element_count integer NOT NULL,
          axial_displacement_end_m double precision NOT NULL,
          output_sample_count integer NOT NULL,
          result_extraction_profile_id varchar(255) NOT NULL,
          metric_profile_id varchar(255) NOT NULL,
          target_solver varchar(64) NOT NULL,
          target_version varchar(64) NOT NULL,
          target_unit_system varchar(64) NOT NULL,
          runner_command_id varchar(100) NOT NULL,
          non_production boolean NOT NULL,
          CONSTRAINT pk_validation_template_revision PRIMARY KEY (organization_id, project_id, id),
          CONSTRAINT uq_validation_template_revision_scope_id
            UNIQUE (organization_id, project_id, aggregate_id, id),
          CONSTRAINT uq_validation_template_revision_scoped_ref
            UNIQUE (organization_id, project_id, classification, aggregate_id, id),
          CONSTRAINT uq_validation_template_revision_number
            UNIQUE (organization_id, project_id, aggregate_id, revision_no),
          CONSTRAINT ck_validation_template_revision_nonzero_ids CHECK (
            id <> {_ZERO} AND aggregate_id <> {_ZERO} AND created_by <> {_ZERO}
            AND request_id <> {_ZERO}),
          CONSTRAINT ck_validation_template_revision_number CHECK (revision_no > 0),
          CONSTRAINT ck_validation_template_revision_base CHECK (
            (revision_no = 1 AND based_on_revision_id IS NULL)
            OR (revision_no > 1 AND based_on_revision_id IS NOT NULL)),
          CONSTRAINT ck_validation_template_revision_hashes CHECK (
            content_hash ~ '^[0-9a-f]{{64}}$'),
          CONSTRAINT ck_validation_template_revision_schema CHECK (
            schema_id = '{_TEMPLATE_SCHEMA}' AND schema_version = '1.0.0'),
          CONSTRAINT ck_validation_template_revision_text CHECK (
            classification ~ '^[a-z][a-z0-9_.-]{{0,63}}$'
            AND length(btrim(change_reason)) BETWEEN 1 AND 2000
            AND length(btrim(trace_id)) BETWEEN 1 AND 255),
          CONSTRAINT ck_validation_template_revision_reference_contract CHECK (
            template_kind = '{_TEMPLATE_KIND}'
            AND result_extraction_profile_id = '{_EXTRACTION_PROFILE}'
            AND metric_profile_id = '{_METRIC_PROFILE}'
            AND target_solver = '{_TARGET_SOLVER}'
            AND target_version = '{_TARGET_VERSION}'
            AND target_unit_system = '{_TARGET_UNITS}'
            AND runner_command_id = '{_RUNNER_COMMAND}'
            AND non_production),
          CONSTRAINT ck_validation_template_revision_numerics CHECK (
            gauge_length_m > 0 AND gauge_length_m < 'Infinity'::float8
            AND cross_section_area_m2 > 0 AND cross_section_area_m2 < 'Infinity'::float8
            AND axial_element_count BETWEEN 1 AND 10000
            AND axial_displacement_end_m > 0
            AND axial_displacement_end_m < gauge_length_m
            AND output_sample_count BETWEEN 2 AND 10000),
          CONSTRAINT fk_validation_template_revision_identity FOREIGN KEY
            (organization_id, project_id, aggregate_id)
            REFERENCES validation.validation_template (organization_id, project_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_validation_template_revision_identity_kind FOREIGN KEY
            (organization_id, project_id, classification, aggregate_id, template_kind)
            REFERENCES validation.validation_template
              (organization_id, project_id, classification, id, template_kind)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_validation_template_revision_base FOREIGN KEY
            (organization_id, project_id, aggregate_id, based_on_revision_id)
            REFERENCES validation.validation_template_revision
              (organization_id, project_id, aggregate_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED
        )
        """
    )
    op.execute(
        """
        ALTER TABLE validation.validation_template
          ADD CONSTRAINT fk_validation_template_current_revision
          FOREIGN KEY (organization_id, project_id, id, current_revision_id)
          REFERENCES validation.validation_template_revision
            (organization_id, project_id, aggregate_id, id)
          ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED
        """
    )


def _create_plan_tables() -> None:
    op.execute(
        f"""
        CREATE TABLE validation.validation_plan (
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
          CONSTRAINT pk_validation_plan PRIMARY KEY (organization_id, project_id, id),
          CONSTRAINT uq_validation_plan_scope_identity
            UNIQUE (organization_id, project_id, classification, id),
          CONSTRAINT uq_validation_plan_label
            UNIQUE (organization_id, project_id, classification, plan_label),
          CONSTRAINT uq_validation_plan_identity_kind
            UNIQUE (organization_id, project_id, classification, id, plan_kind),
          CONSTRAINT ck_validation_plan_nonzero_ids CHECK (
            id <> {_ZERO} AND current_revision_id <> {_ZERO} AND created_by <> {_ZERO}),
          CONSTRAINT ck_validation_plan_classification CHECK (
            classification ~ '^[a-z][a-z0-9_.-]{{0,63}}$'),
          CONSTRAINT ck_validation_plan_label CHECK (
            length(btrim(plan_label)) BETWEEN 1 AND 160 AND plan_label = btrim(plan_label)),
          CONSTRAINT ck_validation_plan_kind CHECK (plan_kind = '{_PLAN_KIND}')
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE validation.validation_plan_revision (
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
          template_id uuid NOT NULL,
          template_revision_id uuid NOT NULL,
          material_model_id uuid NOT NULL,
          material_model_revision_id uuid NOT NULL,
          solver_card_id uuid NOT NULL,
          solver_card_revision_id uuid NOT NULL,
          experimental_selection_id uuid NOT NULL,
          experimental_selection_revision_id uuid NOT NULL,
          runner_id varchar(255) NOT NULL,
          runner_version varchar(64) NOT NULL,
          runner_digest char(64) COLLATE "C" NOT NULL,
          non_production boolean NOT NULL,
          CONSTRAINT pk_validation_plan_revision PRIMARY KEY (organization_id, project_id, id),
          CONSTRAINT uq_validation_plan_revision_scope_id
            UNIQUE (organization_id, project_id, aggregate_id, id),
          CONSTRAINT uq_validation_plan_revision_scoped_ref
            UNIQUE (organization_id, project_id, classification, aggregate_id, id),
          CONSTRAINT uq_validation_plan_revision_number
            UNIQUE (organization_id, project_id, aggregate_id, revision_no),
          CONSTRAINT ck_validation_plan_revision_nonzero_ids CHECK (
            id <> {_ZERO} AND aggregate_id <> {_ZERO} AND created_by <> {_ZERO}
            AND request_id <> {_ZERO} AND template_id <> {_ZERO}
            AND template_revision_id <> {_ZERO} AND material_model_id <> {_ZERO}
            AND material_model_revision_id <> {_ZERO} AND solver_card_id <> {_ZERO}
            AND solver_card_revision_id <> {_ZERO} AND experimental_selection_id <> {_ZERO}
            AND experimental_selection_revision_id <> {_ZERO}),
          CONSTRAINT ck_validation_plan_revision_number CHECK (revision_no > 0),
          CONSTRAINT ck_validation_plan_revision_base CHECK (
            (revision_no = 1 AND based_on_revision_id IS NULL)
            OR (revision_no > 1 AND based_on_revision_id IS NOT NULL)),
          CONSTRAINT ck_validation_plan_revision_hashes CHECK (
            content_hash ~ '^[0-9a-f]{{64}}$' AND runner_digest ~ '^[0-9a-f]{{64}}$'),
          CONSTRAINT ck_validation_plan_revision_schema CHECK (
            schema_id = '{_PLAN_SCHEMA}' AND schema_version = '1.0.0'),
          CONSTRAINT ck_validation_plan_revision_text CHECK (
            classification ~ '^[a-z][a-z0-9_.-]{{0,63}}$'
            AND length(btrim(change_reason)) BETWEEN 1 AND 2000
            AND length(btrim(trace_id)) BETWEEN 1 AND 255),
          CONSTRAINT ck_validation_plan_revision_reference_contract CHECK (
            plan_kind = '{_PLAN_KIND}'
            AND runner_id = '{_RUNNER_ID}' AND runner_version = '{_RUNNER_VERSION}'
            AND runner_digest = '{_RUNNER_DIGEST}' AND non_production),
          CONSTRAINT fk_validation_plan_revision_identity FOREIGN KEY
            (organization_id, project_id, aggregate_id)
            REFERENCES validation.validation_plan (organization_id, project_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_validation_plan_revision_identity_kind FOREIGN KEY
            (organization_id, project_id, classification, aggregate_id, plan_kind)
            REFERENCES validation.validation_plan
              (organization_id, project_id, classification, id, plan_kind)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_validation_plan_revision_template FOREIGN KEY
            (organization_id, project_id, classification, template_id, template_revision_id)
            REFERENCES validation.validation_template_revision
              (organization_id, project_id, classification, aggregate_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_validation_plan_revision_model FOREIGN KEY
            (organization_id, project_id, classification, material_model_id, material_model_revision_id)
            REFERENCES modeling.material_model_revision
              (organization_id, project_id, classification, aggregate_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_validation_plan_revision_card FOREIGN KEY
            (organization_id, project_id, classification, solver_card_id, solver_card_revision_id)
            REFERENCES exporting.solver_card_revision
              (organization_id, project_id, classification, aggregate_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_validation_plan_revision_selection FOREIGN KEY
            (organization_id, project_id, classification,
             experimental_selection_id, experimental_selection_revision_id)
            REFERENCES datasets.dataset_selection_revision
              (organization_id, project_id, classification, aggregate_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_validation_plan_revision_base FOREIGN KEY
            (organization_id, project_id, aggregate_id, based_on_revision_id)
            REFERENCES validation.validation_plan_revision
              (organization_id, project_id, aggregate_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED
        )
        """
    )
    op.execute(
        """
        ALTER TABLE validation.validation_plan
          ADD CONSTRAINT fk_validation_plan_current_revision
          FOREIGN KEY (organization_id, project_id, id, current_revision_id)
          REFERENCES validation.validation_plan_revision
            (organization_id, project_id, aggregate_id, id)
          ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED
        """
    )


def _create_run_tables() -> None:
    op.execute(
        f"""
        CREATE TABLE validation.validation_run (
          id uuid NOT NULL,
          organization_id uuid NOT NULL,
          project_id uuid NOT NULL,
          classification varchar(64) NOT NULL,
          plan_id uuid NOT NULL,
          plan_revision_id uuid NOT NULL,
          template_id uuid NOT NULL,
          template_revision_id uuid NOT NULL,
          material_model_id uuid NOT NULL,
          material_model_revision_id uuid NOT NULL,
          solver_card_id uuid NOT NULL,
          solver_card_revision_id uuid NOT NULL,
          experimental_selection_id uuid NOT NULL,
          experimental_selection_revision_id uuid NOT NULL,
          execution_mode varchar(32) NOT NULL,
          runner_id varchar(255) NOT NULL,
          runner_version varchar(64) NOT NULL,
          runner_digest char(64) COLLATE "C" NOT NULL,
          status varchar(32) NOT NULL,
          deck_artifact_id uuid NOT NULL,
          deck_sha256 char(64) COLLATE "C" NOT NULL,
          external_job_reference varchar(256) NULL,
          result_manifest_id uuid NULL,
          failure_code varchar(100) NULL,
          submitted_at timestamptz NOT NULL,
          started_at timestamptz NULL,
          ended_at timestamptz NULL,
          created_by uuid NOT NULL,
          request_id uuid NOT NULL,
          trace_id varchar(255) NOT NULL,
          change_reason text NOT NULL,
          CONSTRAINT pk_validation_run PRIMARY KEY (organization_id, project_id, id),
          CONSTRAINT uq_validation_run_scope_identity
            UNIQUE (organization_id, project_id, classification, id),
          CONSTRAINT uq_validation_run_plan_revision
            UNIQUE (organization_id, project_id, classification, id, plan_id, plan_revision_id),
          CONSTRAINT ck_validation_run_nonzero_ids CHECK (
            id <> {_ZERO} AND plan_id <> {_ZERO} AND plan_revision_id <> {_ZERO}
            AND template_id <> {_ZERO} AND template_revision_id <> {_ZERO}
            AND material_model_id <> {_ZERO} AND material_model_revision_id <> {_ZERO}
            AND solver_card_id <> {_ZERO} AND solver_card_revision_id <> {_ZERO}
            AND experimental_selection_id <> {_ZERO}
            AND experimental_selection_revision_id <> {_ZERO}
            AND deck_artifact_id <> {_ZERO} AND created_by <> {_ZERO} AND request_id <> {_ZERO}),
          CONSTRAINT ck_validation_run_text CHECK (
            classification ~ '^[a-z][a-z0-9_.-]{{0,63}}$'
            AND runner_digest ~ '^[0-9a-f]{{64}}$' AND deck_sha256 ~ '^[0-9a-f]{{64}}$'
            AND length(btrim(change_reason)) BETWEEN 1 AND 2000
            AND length(btrim(trace_id)) BETWEEN 1 AND 255
            AND (external_job_reference IS NULL
                 OR external_job_reference ~ '^[A-Za-z0-9][A-Za-z0-9._:/-]{{0,255}}$')),
          CONSTRAINT ck_validation_run_reference_runner CHECK (
            runner_id = '{_RUNNER_ID}' AND runner_version = '{_RUNNER_VERSION}'
            AND runner_digest = '{_RUNNER_DIGEST}'),
          CONSTRAINT ck_validation_run_execution_status CHECK (
            execution_mode IN ('reference_inline_mock', 'manual_attach')
            AND status IN ('queued', 'waiting_manual', 'running', 'succeeded', 'failed', 'cancelled')),
          CONSTRAINT ck_validation_run_terminal_shape CHECK (
            ((status = 'queued' AND execution_mode = 'reference_inline_mock'
             AND started_at IS NULL AND ended_at IS NULL AND result_manifest_id IS NULL
             AND failure_code IS NULL AND external_job_reference IS NULL)
            OR (status = 'waiting_manual' AND execution_mode = 'manual_attach'
                AND started_at IS NULL AND ended_at IS NULL AND result_manifest_id IS NULL
                AND failure_code IS NULL AND external_job_reference IS NOT NULL)
            OR (status = 'running' AND execution_mode = 'reference_inline_mock'
                AND started_at IS NOT NULL AND ended_at IS NULL AND result_manifest_id IS NULL
                AND failure_code IS NULL AND external_job_reference IS NULL)
            OR (status = 'succeeded' AND ended_at IS NOT NULL AND result_manifest_id IS NOT NULL
                AND failure_code IS NULL)
            OR (status = 'failed' AND ended_at IS NOT NULL AND result_manifest_id IS NOT NULL
                AND failure_code ~ '^[a-z][a-z0-9_ ]{{0,99}}$')
            OR (status = 'cancelled' AND ended_at IS NOT NULL AND result_manifest_id IS NULL
                AND failure_code = 'cancelled'))
            AND (result_manifest_id IS NULL OR result_manifest_id <> {_ZERO})),
          CONSTRAINT fk_validation_run_plan FOREIGN KEY
            (organization_id, project_id, classification, plan_id, plan_revision_id)
            REFERENCES validation.validation_plan_revision
              (organization_id, project_id, classification, aggregate_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_validation_run_template FOREIGN KEY
            (organization_id, project_id, classification, template_id, template_revision_id)
            REFERENCES validation.validation_template_revision
              (organization_id, project_id, classification, aggregate_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_validation_run_model FOREIGN KEY
            (organization_id, project_id, classification, material_model_id, material_model_revision_id)
            REFERENCES modeling.material_model_revision
              (organization_id, project_id, classification, aggregate_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_validation_run_card FOREIGN KEY
            (organization_id, project_id, classification, solver_card_id, solver_card_revision_id)
            REFERENCES exporting.solver_card_revision
              (organization_id, project_id, classification, aggregate_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_validation_run_selection FOREIGN KEY
            (organization_id, project_id, classification,
             experimental_selection_id, experimental_selection_revision_id)
            REFERENCES datasets.dataset_selection_revision
              (organization_id, project_id, classification, aggregate_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_validation_run_deck_artifact FOREIGN KEY
            (organization_id, project_id, classification, deck_artifact_id, deck_sha256)
            REFERENCES artifact.artifact
              (organization_id, project_id, classification, id, sha256)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE validation.validation_run_result_manifest (
          id uuid NOT NULL,
          organization_id uuid NOT NULL,
          project_id uuid NOT NULL,
          classification varchar(64) NOT NULL,
          validation_run_id uuid NOT NULL,
          execution_mode varchar(32) NOT NULL,
          solver_termination varchar(32) NOT NULL,
          external_job_reference varchar(256) NULL,
          deck_artifact_id uuid NOT NULL,
          deck_sha256 char(64) COLLATE "C" NOT NULL,
          stdout_artifact_id uuid NOT NULL,
          stdout_sha256 char(64) COLLATE "C" NOT NULL,
          stderr_artifact_id uuid NOT NULL,
          stderr_sha256 char(64) COLLATE "C" NOT NULL,
          native_result_artifact_id uuid NULL,
          native_result_sha256 char(64) COLLATE "C" NULL,
          native_result_state varchar(32) NOT NULL,
          manifest_artifact_id uuid NOT NULL,
          manifest_sha256 char(64) COLLATE "C" NOT NULL,
          created_at timestamptz NOT NULL,
          created_by uuid NOT NULL,
          CONSTRAINT pk_validation_run_result_manifest
            PRIMARY KEY (organization_id, project_id, id),
          CONSTRAINT uq_validation_run_result_manifest_scope_identity
            UNIQUE (organization_id, project_id, classification, id),
          CONSTRAINT uq_validation_run_result_manifest_run
            UNIQUE (organization_id, project_id, classification, validation_run_id),
          CONSTRAINT ck_validation_run_result_manifest_nonzero_ids CHECK (
            id <> {_ZERO} AND validation_run_id <> {_ZERO} AND deck_artifact_id <> {_ZERO}
            AND stdout_artifact_id <> {_ZERO} AND stderr_artifact_id <> {_ZERO}
            AND manifest_artifact_id <> {_ZERO} AND created_by <> {_ZERO}
            AND (native_result_artifact_id IS NULL OR native_result_artifact_id <> {_ZERO})),
          CONSTRAINT ck_validation_run_result_manifest_text CHECK (
            classification ~ '^[a-z][a-z0-9_.-]{{0,63}}$'
            AND deck_sha256 ~ '^[0-9a-f]{{64}}$'
            AND stdout_sha256 ~ '^[0-9a-f]{{64}}$'
            AND stderr_sha256 ~ '^[0-9a-f]{{64}}$'
            AND manifest_sha256 ~ '^[0-9a-f]{{64}}$'
            AND (native_result_sha256 IS NULL OR native_result_sha256 ~ '^[0-9a-f]{{64}}$')
            AND (external_job_reference IS NULL
                 OR external_job_reference ~ '^[A-Za-z0-9][A-Za-z0-9._:/-]{{0,255}}$')),
          CONSTRAINT ck_validation_run_result_manifest_contract CHECK (
            execution_mode IN ('reference_inline_mock', 'manual_attach')
            AND solver_termination IN ('normal', 'abnormal', 'not_available')
            AND native_result_state IN ('available', 'not_available')
            AND ((native_result_state = 'available'
                  AND native_result_artifact_id IS NOT NULL AND native_result_sha256 IS NOT NULL)
                 OR (native_result_state = 'not_available'
                     AND native_result_artifact_id IS NULL AND native_result_sha256 IS NULL))
            AND ((execution_mode = 'reference_inline_mock' AND external_job_reference IS NULL)
                 OR (execution_mode = 'manual_attach' AND external_job_reference IS NOT NULL)),
          CONSTRAINT fk_validation_run_result_manifest_run FOREIGN KEY
            (organization_id, project_id, classification, validation_run_id)
            REFERENCES validation.validation_run (organization_id, project_id, classification, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_validation_run_result_manifest_deck FOREIGN KEY
            (organization_id, project_id, classification, deck_artifact_id, deck_sha256)
            REFERENCES artifact.artifact
              (organization_id, project_id, classification, id, sha256)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_validation_run_result_manifest_stdout FOREIGN KEY
            (organization_id, project_id, classification, stdout_artifact_id, stdout_sha256)
            REFERENCES artifact.artifact
              (organization_id, project_id, classification, id, sha256)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_validation_run_result_manifest_stderr FOREIGN KEY
            (organization_id, project_id, classification, stderr_artifact_id, stderr_sha256)
            REFERENCES artifact.artifact
              (organization_id, project_id, classification, id, sha256)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_validation_run_result_manifest_native FOREIGN KEY
            (organization_id, project_id, classification,
             native_result_artifact_id, native_result_sha256)
            REFERENCES artifact.artifact
              (organization_id, project_id, classification, id, sha256)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_validation_run_result_manifest_artifact FOREIGN KEY
            (organization_id, project_id, classification, manifest_artifact_id, manifest_sha256)
            REFERENCES artifact.artifact
              (organization_id, project_id, classification, id, sha256)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED
        )
        """
    )
    op.execute(
        """
        ALTER TABLE validation.validation_run
          ADD CONSTRAINT fk_validation_run_result_manifest
          FOREIGN KEY (organization_id, project_id, classification, result_manifest_id)
          REFERENCES validation.validation_run_result_manifest
            (organization_id, project_id, classification, id)
          ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED
        """
    )


def _create_guards() -> None:
    op.execute(
        f"""
        CREATE FUNCTION validation.guard_validation_plan_revision_insert()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
          template validation.validation_template_revision%ROWTYPE;
          card exporting.solver_card_revision%ROWTYPE;
          selected_dataset_id uuid;
          selected_dataset_revision_id uuid;
          model_state_id uuid;
          specimen_state_id uuid;
        BEGIN
          SELECT * INTO template
          FROM validation.validation_template_revision
          WHERE organization_id = NEW.organization_id AND project_id = NEW.project_id
            AND classification = NEW.classification AND aggregate_id = NEW.template_id
            AND id = NEW.template_revision_id;
          SELECT * INTO card
          FROM exporting.solver_card_revision
          WHERE organization_id = NEW.organization_id AND project_id = NEW.project_id
            AND classification = NEW.classification AND aggregate_id = NEW.solver_card_id
            AND id = NEW.solver_card_revision_id;
          IF NOT FOUND OR template.target_solver IS DISTINCT FROM '{_TARGET_SOLVER}'
             OR template.target_version IS DISTINCT FROM '{_TARGET_VERSION}'
             OR template.target_unit_system IS DISTINCT FROM '{_TARGET_UNITS}'
             OR card.material_model_id IS DISTINCT FROM NEW.material_model_id
             OR card.material_model_revision_id IS DISTINCT FROM NEW.material_model_revision_id
             OR card.target_solver IS DISTINCT FROM template.target_solver
             OR card.target_version IS DISTINCT FROM template.target_version
             OR card.target_unit_system IS DISTINCT FROM template.target_unit_system THEN
            RAISE EXCEPTION USING ERRCODE = '23514',
              MESSAGE = 'Validation Plan requires an exact compatible Template, IR, and Solver Card';
          END IF;
          SELECT dataset_id, dataset_revision_id INTO selected_dataset_id, selected_dataset_revision_id
          FROM datasets.dataset_selection_revision
          WHERE organization_id = NEW.organization_id AND project_id = NEW.project_id
            AND classification = NEW.classification
            AND aggregate_id = NEW.experimental_selection_id
            AND id = NEW.experimental_selection_revision_id;
          SELECT material_state_id INTO model_state_id
          FROM modeling.material_model_revision
          WHERE organization_id = NEW.organization_id AND project_id = NEW.project_id
            AND classification = NEW.classification AND aggregate_id = NEW.material_model_id
            AND id = NEW.material_model_revision_id;
          SELECT specimen.material_state_id INTO specimen_state_id
          FROM datasets.dataset_revision dataset
          JOIN testing.test_run run
            ON run.organization_id = dataset.organization_id
            AND run.project_id = dataset.project_id
            AND run.classification = dataset.classification
            AND run.id = dataset.test_run_id
          JOIN testing.specimen specimen
            ON specimen.organization_id = run.organization_id
            AND specimen.project_id = run.project_id
            AND specimen.classification = run.classification
            AND specimen.id = run.specimen_id
          WHERE dataset.organization_id = NEW.organization_id
            AND dataset.project_id = NEW.project_id
            AND dataset.classification = NEW.classification
            AND dataset.aggregate_id = selected_dataset_id
            AND dataset.id = selected_dataset_revision_id;
          IF selected_dataset_id IS NULL OR selected_dataset_revision_id IS NULL
             OR model_state_id IS NULL OR specimen_state_id IS NULL
             OR model_state_id <> specimen_state_id THEN
            RAISE EXCEPTION USING ERRCODE = '23514',
              MESSAGE = 'Validation Plan Selection and Material Model must share Material State';
          END IF;
          RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        f"""
        CREATE FUNCTION validation.guard_validation_run_insert()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
          plan validation.validation_plan_revision%ROWTYPE;
          artifact_kind text;
          artifact_role text;
          artifact_schema text;
          artifact_digest text;
        BEGIN
          SELECT * INTO plan
          FROM validation.validation_plan_revision
          WHERE organization_id = NEW.organization_id AND project_id = NEW.project_id
            AND classification = NEW.classification AND aggregate_id = NEW.plan_id
            AND id = NEW.plan_revision_id;
          IF NOT FOUND OR plan.template_id IS DISTINCT FROM NEW.template_id
             OR plan.template_revision_id IS DISTINCT FROM NEW.template_revision_id
             OR plan.material_model_id IS DISTINCT FROM NEW.material_model_id
             OR plan.material_model_revision_id IS DISTINCT FROM NEW.material_model_revision_id
             OR plan.solver_card_id IS DISTINCT FROM NEW.solver_card_id
             OR plan.solver_card_revision_id IS DISTINCT FROM NEW.solver_card_revision_id
             OR plan.experimental_selection_id IS DISTINCT FROM NEW.experimental_selection_id
             OR plan.experimental_selection_revision_id IS DISTINCT FROM NEW.experimental_selection_revision_id
             OR plan.runner_id IS DISTINCT FROM NEW.runner_id
             OR plan.runner_version IS DISTINCT FROM NEW.runner_version
             OR plan.runner_digest IS DISTINCT FROM NEW.runner_digest THEN
            RAISE EXCEPTION USING ERRCODE = '23514',
              MESSAGE = 'Validation Run must reproduce every immutable Plan revision input';
          END IF;
          SELECT artifact_kind, artifact_role, schema_ref, sha256
            INTO artifact_kind, artifact_role, artifact_schema, artifact_digest
          FROM artifact.artifact
          WHERE organization_id = NEW.organization_id AND project_id = NEW.project_id
            AND classification = NEW.classification AND id = NEW.deck_artifact_id;
          IF artifact_kind IS DISTINCT FROM 'derived'
             OR artifact_role IS DISTINCT FROM 'validation.solver_deck'
             OR artifact_schema IS DISTINCT FROM '{_DECK_SCHEMA}'
             OR artifact_digest IS DISTINCT FROM NEW.deck_sha256 THEN
            RAISE EXCEPTION USING ERRCODE = '23514',
              MESSAGE = 'Validation Run requires its declared immutable reference deck Artifact';
          END IF;
          RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION validation.guard_validation_run_transition()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
          manifest_termination text;
        BEGIN
          IF NEW.organization_id <> OLD.organization_id OR NEW.project_id <> OLD.project_id
             OR NEW.classification <> OLD.classification OR NEW.plan_id <> OLD.plan_id
             OR NEW.plan_revision_id <> OLD.plan_revision_id OR NEW.template_id <> OLD.template_id
             OR NEW.template_revision_id <> OLD.template_revision_id
             OR NEW.material_model_id <> OLD.material_model_id
             OR NEW.material_model_revision_id <> OLD.material_model_revision_id
             OR NEW.solver_card_id <> OLD.solver_card_id
             OR NEW.solver_card_revision_id <> OLD.solver_card_revision_id
             OR NEW.experimental_selection_id <> OLD.experimental_selection_id
             OR NEW.experimental_selection_revision_id <> OLD.experimental_selection_revision_id
             OR NEW.execution_mode <> OLD.execution_mode OR NEW.runner_id <> OLD.runner_id
             OR NEW.runner_version <> OLD.runner_version OR NEW.runner_digest <> OLD.runner_digest
             OR NEW.deck_artifact_id <> OLD.deck_artifact_id OR NEW.deck_sha256 <> OLD.deck_sha256
             OR NEW.external_job_reference IS DISTINCT FROM OLD.external_job_reference
             OR NEW.submitted_at <> OLD.submitted_at OR NEW.created_by <> OLD.created_by
             OR NEW.request_id <> OLD.request_id OR NEW.trace_id <> OLD.trace_id
             OR NEW.change_reason <> OLD.change_reason THEN
            RAISE EXCEPTION USING ERRCODE = '55000',
              MESSAGE = 'Validation Run immutable input facts cannot be changed';
          END IF;
          IF NEW.status IN ('succeeded', 'failed') THEN
            SELECT solver_termination INTO manifest_termination
            FROM validation.validation_run_result_manifest
            WHERE organization_id = NEW.organization_id AND project_id = NEW.project_id
              AND classification = NEW.classification AND id = NEW.result_manifest_id
              AND validation_run_id = NEW.id;
            IF NOT FOUND
               OR (NEW.status = 'succeeded' AND manifest_termination <> 'normal')
               OR (NEW.status = 'failed' AND manifest_termination = 'normal') THEN
              RAISE EXCEPTION USING ERRCODE = '23514',
                MESSAGE = 'Validation Run terminal status must match Result Manifest termination';
            END IF;
          END IF;
          IF (OLD.status = 'queued' AND NEW.status = 'running'
              AND NEW.started_at IS NOT NULL AND NEW.ended_at IS NULL
              AND NEW.result_manifest_id IS NULL AND NEW.failure_code IS NULL)
             OR (OLD.status IN ('queued', 'waiting_manual') AND NEW.status = 'cancelled'
                 AND NEW.started_at IS NOT DISTINCT FROM OLD.started_at
                 AND NEW.ended_at IS NOT NULL AND NEW.result_manifest_id IS NULL
                 AND NEW.failure_code = 'cancelled')
             OR (OLD.status = 'running' AND NEW.status IN ('succeeded', 'failed')
                 AND NEW.started_at = OLD.started_at AND NEW.ended_at IS NOT NULL
                 AND NEW.result_manifest_id IS NOT NULL)
             OR (OLD.status = 'waiting_manual' AND NEW.status IN ('succeeded', 'failed')
                 AND NEW.started_at IS NULL AND NEW.ended_at IS NOT NULL
                 AND NEW.result_manifest_id IS NOT NULL) THEN
            RETURN NEW;
          END IF;
          RAISE EXCEPTION USING ERRCODE = '55000',
            MESSAGE = 'Validation Run permits only its declared state transitions';
        END;
        $$
        """
    )
    op.execute(
        f"""
        CREATE FUNCTION validation.guard_validation_result_manifest_insert()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
          run validation.validation_run%ROWTYPE;
          expected_status text;
          artifact_kind text;
          artifact_role text;
          artifact_schema text;
          artifact_digest text;
        BEGIN
          SELECT * INTO run
          FROM validation.validation_run
          WHERE organization_id = NEW.organization_id AND project_id = NEW.project_id
            AND classification = NEW.classification AND id = NEW.validation_run_id;
          IF NOT FOUND OR run.result_manifest_id IS NOT NULL
             OR run.execution_mode IS DISTINCT FROM NEW.execution_mode
             OR run.external_job_reference IS DISTINCT FROM NEW.external_job_reference
             OR run.deck_artifact_id IS DISTINCT FROM NEW.deck_artifact_id
             OR run.deck_sha256 IS DISTINCT FROM NEW.deck_sha256 THEN
            RAISE EXCEPTION USING ERRCODE = '23514',
              MESSAGE = 'Result Manifest must reproduce its immutable Validation Run evidence';
          END IF;
          expected_status := CASE NEW.execution_mode
            WHEN 'reference_inline_mock' THEN 'running'
            WHEN 'manual_attach' THEN 'waiting_manual'
            ELSE NULL
          END;
          IF run.status IS DISTINCT FROM expected_status THEN
            RAISE EXCEPTION USING ERRCODE = '23514',
              MESSAGE = 'Result Manifest is not ready for collection in the Run state';
          END IF;
          SELECT artifact_kind, artifact_role, schema_ref, sha256 INTO artifact_kind, artifact_role, artifact_schema, artifact_digest
          FROM artifact.artifact WHERE organization_id = NEW.organization_id AND project_id = NEW.project_id
            AND classification = NEW.classification AND id = NEW.stdout_artifact_id;
          IF artifact_kind IS DISTINCT FROM 'derived' OR artifact_role IS DISTINCT FROM 'validation.runner_stdout'
             OR artifact_schema IS DISTINCT FROM '{_STDOUT_SCHEMA}' OR artifact_digest IS DISTINCT FROM NEW.stdout_sha256 THEN
            RAISE EXCEPTION USING ERRCODE = '23514', MESSAGE = 'Result Manifest stdout Artifact is invalid';
          END IF;
          SELECT artifact_kind, artifact_role, schema_ref, sha256 INTO artifact_kind, artifact_role, artifact_schema, artifact_digest
          FROM artifact.artifact WHERE organization_id = NEW.organization_id AND project_id = NEW.project_id
            AND classification = NEW.classification AND id = NEW.stderr_artifact_id;
          IF artifact_kind IS DISTINCT FROM 'derived' OR artifact_role IS DISTINCT FROM 'validation.runner_stderr'
             OR artifact_schema IS DISTINCT FROM '{_STDERR_SCHEMA}' OR artifact_digest IS DISTINCT FROM NEW.stderr_sha256 THEN
            RAISE EXCEPTION USING ERRCODE = '23514', MESSAGE = 'Result Manifest stderr Artifact is invalid';
          END IF;
          IF NEW.native_result_state = 'available' THEN
            SELECT artifact_kind, artifact_role, schema_ref, sha256 INTO artifact_kind, artifact_role, artifact_schema, artifact_digest
            FROM artifact.artifact WHERE organization_id = NEW.organization_id AND project_id = NEW.project_id
              AND classification = NEW.classification AND id = NEW.native_result_artifact_id;
            IF artifact_kind IS DISTINCT FROM 'derived'
               OR artifact_role IS DISTINCT FROM 'validation.native_solver_result'
               OR artifact_schema IS DISTINCT FROM '{_NATIVE_SCHEMA}'
               OR artifact_digest IS DISTINCT FROM NEW.native_result_sha256 THEN
              RAISE EXCEPTION USING ERRCODE = '23514', MESSAGE = 'Result Manifest native Artifact is invalid';
            END IF;
          END IF;
          SELECT artifact_kind, artifact_role, schema_ref, sha256 INTO artifact_kind, artifact_role, artifact_schema, artifact_digest
          FROM artifact.artifact WHERE organization_id = NEW.organization_id AND project_id = NEW.project_id
            AND classification = NEW.classification AND id = NEW.manifest_artifact_id;
          IF artifact_kind IS DISTINCT FROM 'derived'
             OR artifact_role IS DISTINCT FROM 'validation.run_result_manifest'
             OR artifact_schema IS DISTINCT FROM '{_MANIFEST_SCHEMA}'
             OR artifact_digest IS DISTINCT FROM NEW.manifest_sha256 THEN
            RAISE EXCEPTION USING ERRCODE = '23514', MESSAGE = 'Result Manifest Artifact is invalid';
          END IF;
          IF (NEW.solver_termination = 'normal' AND NEW.native_result_state <> 'available')
             OR (NEW.solver_termination = 'not_available' AND NEW.native_result_state <> 'not_available') THEN
            RAISE EXCEPTION USING ERRCODE = '23514',
              MESSAGE = 'Result Manifest termination and native result availability conflict';
          END IF;
          IF NEW.execution_mode = 'manual_attach' AND NEW.native_result_state <> 'available' THEN
            RAISE EXCEPTION USING ERRCODE = '23514',
              MESSAGE = 'manual Result Manifest requires its attached native result Artifact';
          END IF;
          RETURN NEW;
        END;
        $$
        """
    )
    for table, trigger, function in (
        ("validation_template", "validation_template_head_only", "revisioning.guard_identity_head_update()"),
        ("validation_template_revision", "validation_template_revision_immutable", "revisioning.reject_immutable_row_mutation()"),
        ("validation_plan", "validation_plan_head_only", "revisioning.guard_identity_head_update()"),
        ("validation_plan_revision", "validation_plan_revision_immutable", "revisioning.reject_immutable_row_mutation()"),
        ("validation_run_result_manifest", "validation_run_result_manifest_immutable", "revisioning.reject_immutable_row_mutation()"),
    ):
        op.execute(
            f"CREATE TRIGGER {trigger} BEFORE UPDATE OR DELETE ON validation.{table} "
            f"FOR EACH ROW EXECUTE FUNCTION {function}"
        )
    op.execute(
        "CREATE TRIGGER validation_plan_revision_input_guard "
        "BEFORE INSERT ON validation.validation_plan_revision FOR EACH ROW "
        "EXECUTE FUNCTION validation.guard_validation_plan_revision_insert()"
    )
    op.execute(
        "CREATE TRIGGER validation_run_input_guard BEFORE INSERT ON validation.validation_run "
        "FOR EACH ROW EXECUTE FUNCTION validation.guard_validation_run_insert()"
    )
    op.execute(
        "CREATE TRIGGER validation_run_transition_guard BEFORE UPDATE ON validation.validation_run "
        "FOR EACH ROW EXECUTE FUNCTION validation.guard_validation_run_transition()"
    )
    op.execute(
        "CREATE TRIGGER validation_run_no_delete BEFORE DELETE ON validation.validation_run "
        "FOR EACH ROW EXECUTE FUNCTION revisioning.reject_immutable_row_mutation()"
    )
    op.execute(
        "CREATE TRIGGER validation_run_result_manifest_input_guard "
        "BEFORE INSERT ON validation.validation_run_result_manifest FOR EACH ROW "
        "EXECUTE FUNCTION validation.guard_validation_result_manifest_insert()"
    )


def upgrade() -> None:
    op.execute("CREATE SCHEMA validation")
    _create_template_tables()
    _create_plan_tables()
    _create_run_tables()
    for name, table, columns in (
        (
            "ix_validation_template_tenant_created",
            "validation_template",
            ["organization_id", "project_id", "classification", "created_at"],
        ),
        (
            "ix_validation_template_revision_created",
            "validation_template_revision",
            ["organization_id", "project_id", "classification", "aggregate_id", "created_at"],
        ),
        (
            "ix_validation_plan_tenant_created",
            "validation_plan",
            ["organization_id", "project_id", "classification", "created_at"],
        ),
        (
            "ix_validation_plan_revision_inputs",
            "validation_plan_revision",
            [
                "organization_id",
                "project_id",
                "classification",
                "material_model_revision_id",
                "solver_card_revision_id",
                "experimental_selection_revision_id",
            ],
        ),
        (
            "ix_validation_run_tenant_status_submitted",
            "validation_run",
            ["organization_id", "project_id", "classification", "status", "submitted_at"],
        ),
        (
            "ix_validation_run_card_revision",
            "validation_run",
            ["organization_id", "project_id", "classification", "solver_card_revision_id"],
        ),
        (
            "ix_validation_run_result_manifest_artifact",
            "validation_run_result_manifest",
            ["organization_id", "project_id", "classification", "manifest_artifact_id"],
        ),
    ):
        op.create_index(name, table, columns, schema="validation")
    for table in (
        "validation_template",
        "validation_template_revision",
        "validation_plan",
        "validation_plan_revision",
        "validation_run",
        "validation_run_result_manifest",
    ):
        op.execute(f"ALTER TABLE validation.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE validation.{table} FORCE ROW LEVEL SECURITY")
        _secure(table)
    _create_guards()


def downgrade() -> None:
    for trigger, table in (
        ("validation_run_result_manifest_input_guard", "validation_run_result_manifest"),
        ("validation_run_result_manifest_immutable", "validation_run_result_manifest"),
        ("validation_run_transition_guard", "validation_run"),
        ("validation_run_no_delete", "validation_run"),
        ("validation_run_input_guard", "validation_run"),
        ("validation_plan_revision_input_guard", "validation_plan_revision"),
        ("validation_plan_revision_immutable", "validation_plan_revision"),
        ("validation_plan_head_only", "validation_plan"),
        ("validation_template_revision_immutable", "validation_template_revision"),
        ("validation_template_head_only", "validation_template"),
    ):
        op.execute(f"DROP TRIGGER IF EXISTS {trigger} ON validation.{table}")
    for function in (
        "validation.guard_validation_result_manifest_insert()",
        "validation.guard_validation_run_transition()",
        "validation.guard_validation_run_insert()",
        "validation.guard_validation_plan_revision_insert()",
    ):
        op.execute(f"DROP FUNCTION IF EXISTS {function}")
    for table in (
        "validation_run_result_manifest",
        "validation_run",
        "validation_plan_revision",
        "validation_plan",
        "validation_template_revision",
        "validation_template",
    ):
        for operation in ("select", "insert", "update"):
            op.execute(f"DROP POLICY IF EXISTS validation_{table}_{operation} ON validation.{table}")
    op.drop_constraint(
        "fk_validation_run_result_manifest",
        "validation_run",
        schema="validation",
        type_="foreignkey",
    )
    for table in ("validation_run_result_manifest", "validation_run"):
        op.drop_table(table, schema="validation")
    for table, constraint in (
        ("validation_plan", "fk_validation_plan_current_revision"),
        ("validation_template", "fk_validation_template_current_revision"),
    ):
        op.drop_constraint(constraint, table, schema="validation", type_="foreignkey")
    for table in (
        "validation_plan_revision",
        "validation_plan",
        "validation_template_revision",
        "validation_template",
    ):
        op.drop_table(table, schema="validation")
    op.execute("DROP SCHEMA validation")

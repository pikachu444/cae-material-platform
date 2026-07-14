"""Add immutable human Candidate Selection and reference IR promotion evidence.

Revision ID: 20260720_022_t24
Revises: 20260719_021_t23
"""

# ruff: noqa: E501

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260720_022_t24"
down_revision: str | None = "20260719_021_t23"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ZERO = "'00000000-0000-0000-0000-000000000000'::uuid"
_SELECTION_SCHEMA = "urn:cmp:modeling:reference-calibration-candidate-selection:1.0.0"
_SELECTION_DECISION = "accepted_for_reference_ir_promotion"
_MANUAL_EVIDENCE = "manual_catalog_projection"
_CANDIDATE_EVIDENCE = "reference_candidate_selection"


def _secure(table: str) -> None:
    op.execute(f"ALTER TABLE modeling.{table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE modeling.{table} FORCE ROW LEVEL SECURITY")
    for operation, predicate, permission in (
        ("select", "USING", "modeling.read"),
        ("insert", "WITH CHECK", "modeling.write"),
    ):
        op.execute(
            f"CREATE POLICY modeling_{table}_{operation} ON modeling.{table} "
            f"FOR {operation.upper()} {predicate} (access_control.can_access_row("
            f"organization_id, project_id, classification, '{permission}'))"
        )
    op.execute(
        f"CREATE POLICY modeling_{table}_update ON modeling.{table} FOR UPDATE "
        "USING (access_control.can_access_row(organization_id, project_id, classification, "
        "'modeling.write')) WITH CHECK (access_control.can_access_row("
        "organization_id, project_id, classification, 'modeling.write'))"
    )


def _create_selection_tables() -> None:
    op.execute(
        f"""
        CREATE TABLE modeling.calibration_candidate_selection (
          id uuid NOT NULL,
          organization_id uuid NOT NULL,
          project_id uuid NOT NULL,
          classification varchar(64) NOT NULL,
          current_revision_id uuid NOT NULL,
          created_at timestamptz NOT NULL,
          created_by uuid NOT NULL,
          updated_at timestamptz NOT NULL,
          selection_label varchar(160) NOT NULL,
          calibration_run_id uuid NOT NULL,
          CONSTRAINT pk_modeling_calibration_candidate_selection
            PRIMARY KEY (organization_id, project_id, id),
          CONSTRAINT uq_modeling_calibration_candidate_selection_scope_identity
            UNIQUE (organization_id, project_id, classification, id),
          CONSTRAINT uq_modeling_calibration_candidate_selection_label
            UNIQUE (organization_id, project_id, classification, selection_label),
          CONSTRAINT uq_modeling_calibration_candidate_selection_identity_run
            UNIQUE (organization_id, project_id, classification, id, calibration_run_id),
          CONSTRAINT ck_modeling_calibration_candidate_selection_nonzero_ids CHECK (
            id <> {_ZERO} AND current_revision_id <> {_ZERO}
            AND created_by <> {_ZERO} AND calibration_run_id <> {_ZERO}),
          CONSTRAINT ck_modeling_calibration_candidate_selection_classification CHECK (
            classification ~ '^[a-z][a-z0-9_.-]{{0,63}}$'),
          CONSTRAINT ck_modeling_calibration_candidate_selection_label CHECK (
            length(btrim(selection_label)) BETWEEN 1 AND 160
            AND selection_label = btrim(selection_label)),
          CONSTRAINT fk_modeling_calibration_candidate_selection_run FOREIGN KEY
            (organization_id, project_id, classification, calibration_run_id)
            REFERENCES modeling.calibration_run
              (organization_id, project_id, classification, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE modeling.calibration_candidate_selection_revision (
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
          calibration_run_id uuid NOT NULL,
          calibration_candidate_id uuid NOT NULL,
          candidate_sha256 char(64) COLLATE "C" NOT NULL,
          selection_reason text NOT NULL,
          selection_decision varchar(100) NOT NULL,
          non_production boolean NOT NULL,
          CONSTRAINT pk_modeling_calibration_candidate_selection_revision
            PRIMARY KEY (organization_id, project_id, id),
          CONSTRAINT uq_modeling_calibration_candidate_selection_revision_scope_id
            UNIQUE (organization_id, project_id, aggregate_id, id),
          CONSTRAINT uq_modeling_calibration_candidate_selection_revision_scoped_ref
            UNIQUE (organization_id, project_id, classification, aggregate_id, id),
          CONSTRAINT uq_modeling_calibration_candidate_selection_revision_number
            UNIQUE (organization_id, project_id, aggregate_id, revision_no),
          CONSTRAINT ck_modeling_calibration_candidate_selection_revision_nonzero_ids CHECK (
            id <> {_ZERO} AND aggregate_id <> {_ZERO} AND created_by <> {_ZERO}
            AND request_id <> {_ZERO} AND calibration_run_id <> {_ZERO}
            AND calibration_candidate_id <> {_ZERO}),
          CONSTRAINT ck_modeling_calibration_candidate_selection_revision_number CHECK (
            revision_no > 0),
          CONSTRAINT ck_modeling_calibration_candidate_selection_revision_base CHECK (
            (revision_no = 1 AND based_on_revision_id IS NULL)
            OR (revision_no > 1 AND based_on_revision_id IS NOT NULL)),
          CONSTRAINT ck_modeling_calibration_candidate_selection_revision_hashes CHECK (
            content_hash ~ '^[0-9a-f]{{64}}$'
            AND candidate_sha256 ~ '^[0-9a-f]{{64}}$'),
          CONSTRAINT ck_modeling_calibration_candidate_selection_revision_schema CHECK (
            schema_id = '{_SELECTION_SCHEMA}' AND schema_version = '1.0.0'),
          CONSTRAINT ck_modeling_calibration_candidate_selection_revision_text CHECK (
            classification ~ '^[a-z][a-z0-9_.-]{{0,63}}$'
            AND length(btrim(change_reason)) BETWEEN 1 AND 2000
            AND length(btrim(selection_reason)) BETWEEN 1 AND 2000
            AND length(btrim(trace_id)) BETWEEN 1 AND 255),
          CONSTRAINT ck_modeling_calibration_candidate_selection_revision_decision CHECK (
            selection_decision = '{_SELECTION_DECISION}' AND non_production),
          CONSTRAINT fk_modeling_calibration_candidate_selection_revision_identity FOREIGN KEY
            (organization_id, project_id, aggregate_id)
            REFERENCES modeling.calibration_candidate_selection
              (organization_id, project_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_modeling_calibration_candidate_selection_revision_identity_run FOREIGN KEY
            (organization_id, project_id, classification, aggregate_id, calibration_run_id)
            REFERENCES modeling.calibration_candidate_selection
              (organization_id, project_id, classification, id, calibration_run_id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_modeling_calibration_candidate_selection_revision_candidate FOREIGN KEY
            (organization_id, project_id, classification, calibration_candidate_id, calibration_run_id)
            REFERENCES modeling.calibration_candidate
              (organization_id, project_id, classification, id, calibration_run_id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_modeling_calibration_candidate_selection_revision_base FOREIGN KEY
            (organization_id, project_id, aggregate_id, based_on_revision_id)
            REFERENCES modeling.calibration_candidate_selection_revision
              (organization_id, project_id, aggregate_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED
        )
        """
    )
    op.execute(
        """
        ALTER TABLE modeling.calibration_candidate_selection
          ADD CONSTRAINT fk_modeling_calibration_candidate_selection_current_revision
          FOREIGN KEY (organization_id, project_id, id, current_revision_id)
          REFERENCES modeling.calibration_candidate_selection_revision
            (organization_id, project_id, aggregate_id, id)
          ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED
        """
    )


def _add_candidate_identity_constraint() -> None:
    op.execute(
        """
        ALTER TABLE modeling.calibration_candidate
          ADD CONSTRAINT uq_modeling_calibration_candidate_identity_run
          UNIQUE (organization_id, project_id, classification, id, calibration_run_id)
        """
    )


def _add_model_evidence_constraints() -> None:
    op.execute(
        f"""
        ALTER TABLE modeling.material_model_revision
          ADD COLUMN calibration_evidence_kind varchar(64) NOT NULL
            DEFAULT '{_MANUAL_EVIDENCE}',
          ADD COLUMN calibration_selection_id uuid NULL,
          ADD COLUMN calibration_selection_revision_id uuid NULL,
          ADD COLUMN calibration_run_id uuid NULL,
          ADD COLUMN calibration_candidate_id uuid NULL,
          ADD COLUMN calibration_candidate_sha256 char(64) COLLATE "C" NULL,
          ADD COLUMN calibration_diagnostics_artifact_id uuid NULL,
          ADD COLUMN calibration_diagnostics_sha256 char(64) COLLATE "C" NULL
        """
    )
    op.execute(
        "ALTER TABLE modeling.material_model_revision "
        "ALTER COLUMN calibration_evidence_kind DROP DEFAULT"
    )
    op.execute(
        f"""
        ALTER TABLE modeling.material_model_revision
          ADD CONSTRAINT ck_modeling_material_model_calibration_evidence_kind CHECK (
            calibration_evidence_kind IN ('{_MANUAL_EVIDENCE}', '{_CANDIDATE_EVIDENCE}')),
          ADD CONSTRAINT ck_modeling_material_model_calibration_evidence_shape CHECK (
            (calibration_evidence_kind = '{_MANUAL_EVIDENCE}'
             AND calibration_selection_id IS NULL AND calibration_selection_revision_id IS NULL
             AND calibration_run_id IS NULL AND calibration_candidate_id IS NULL
             AND calibration_candidate_sha256 IS NULL
             AND calibration_diagnostics_artifact_id IS NULL
             AND calibration_diagnostics_sha256 IS NULL)
            OR
            (calibration_evidence_kind = '{_CANDIDATE_EVIDENCE}'
             AND calibration_selection_id IS NOT NULL
             AND calibration_selection_revision_id IS NOT NULL
             AND calibration_run_id IS NOT NULL AND calibration_candidate_id IS NOT NULL
             AND calibration_candidate_sha256 ~ '^[0-9a-f]{{64}}$'
             AND calibration_diagnostics_artifact_id IS NOT NULL
             AND calibration_diagnostics_sha256 ~ '^[0-9a-f]{{64}}$')
          ),
          ADD CONSTRAINT fk_modeling_material_model_calibration_selection FOREIGN KEY
            (organization_id, project_id, classification, calibration_selection_id,
             calibration_selection_revision_id)
            REFERENCES modeling.calibration_candidate_selection_revision
              (organization_id, project_id, classification, aggregate_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          ADD CONSTRAINT fk_modeling_material_model_calibration_candidate FOREIGN KEY
            (organization_id, project_id, classification, calibration_candidate_id,
             calibration_run_id)
            REFERENCES modeling.calibration_candidate
              (organization_id, project_id, classification, id, calibration_run_id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          ADD CONSTRAINT fk_modeling_material_model_calibration_diagnostics FOREIGN KEY
            (organization_id, project_id, classification, calibration_diagnostics_artifact_id)
            REFERENCES artifact.artifact (organization_id, project_id, classification, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED
        """
    )
    op.execute(
        "CREATE INDEX ix_modeling_material_model_calibration_candidate "
        "ON modeling.material_model_revision "
        "(organization_id, project_id, classification, calibration_candidate_id) "
        "WHERE calibration_candidate_id IS NOT NULL"
    )


def _create_guards() -> None:
    op.execute(
        """
        CREATE FUNCTION modeling.guard_calibration_candidate_selection_revision_insert()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
          candidate_status text;
          candidate_run_id uuid;
          candidate_digest text;
          run_status text;
        BEGIN
          SELECT status, calibration_run_id, candidate_sha256
            INTO candidate_status, candidate_run_id, candidate_digest
          FROM modeling.calibration_candidate
          WHERE organization_id = NEW.organization_id AND project_id = NEW.project_id
            AND classification = NEW.classification AND id = NEW.calibration_candidate_id;
          IF candidate_status IS DISTINCT FROM 'converged'
             OR candidate_run_id IS DISTINCT FROM NEW.calibration_run_id
             OR candidate_digest IS DISTINCT FROM NEW.candidate_sha256 THEN
            RAISE EXCEPTION USING ERRCODE = '23514',
              MESSAGE = 'Candidate Selection requires its exact converged Candidate and digest';
          END IF;
          SELECT status INTO run_status
          FROM modeling.calibration_run
          WHERE organization_id = NEW.organization_id AND project_id = NEW.project_id
            AND classification = NEW.classification AND id = NEW.calibration_run_id;
          IF run_status IS DISTINCT FROM 'succeeded' THEN
            RAISE EXCEPTION USING ERRCODE = '23514',
              MESSAGE = 'Candidate Selection requires a succeeded Calibration Run';
          END IF;
          RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        f"""
        CREATE FUNCTION modeling.guard_reference_calibrated_model_revision_insert()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
          prior_evidence_kind text;
          selection_candidate_id uuid;
          selection_run_id uuid;
          selection_digest text;
          selection_current_revision_id uuid;
          candidate_status text;
          candidate_youngs_modulus double precision;
          candidate_digest text;
          candidate_artifact_id uuid;
          candidate_artifact_digest text;
          run_status text;
          run_model_id uuid;
          run_model_revision_id uuid;
        BEGIN
          IF NEW.based_on_revision_id IS NOT NULL THEN
            SELECT calibration_evidence_kind INTO prior_evidence_kind
            FROM modeling.material_model_revision
            WHERE organization_id = NEW.organization_id AND project_id = NEW.project_id
              AND aggregate_id = NEW.aggregate_id AND id = NEW.based_on_revision_id;
          END IF;
          IF NEW.calibration_evidence_kind = '{_MANUAL_EVIDENCE}' THEN
            IF prior_evidence_kind = '{_CANDIDATE_EVIDENCE}' THEN
              RAISE EXCEPTION USING ERRCODE = '23514',
                MESSAGE = 'a calibrated Material Model revision cannot discard its evidence';
            END IF;
            RETURN NEW;
          END IF;
          SELECT identity.current_revision_id, revision.calibration_candidate_id,
                 revision.calibration_run_id, revision.candidate_sha256
            INTO selection_current_revision_id, selection_candidate_id, selection_run_id,
                 selection_digest
          FROM modeling.calibration_candidate_selection AS identity
          JOIN modeling.calibration_candidate_selection_revision AS revision
            ON revision.organization_id = identity.organization_id
            AND revision.project_id = identity.project_id
            AND revision.aggregate_id = identity.id
          WHERE identity.organization_id = NEW.organization_id
            AND identity.project_id = NEW.project_id
            AND identity.classification = NEW.classification
            AND identity.id = NEW.calibration_selection_id
            AND revision.id = NEW.calibration_selection_revision_id;
          IF selection_current_revision_id IS DISTINCT FROM NEW.calibration_selection_revision_id
             OR selection_candidate_id IS DISTINCT FROM NEW.calibration_candidate_id
             OR selection_run_id IS DISTINCT FROM NEW.calibration_run_id
             OR selection_digest IS DISTINCT FROM NEW.calibration_candidate_sha256 THEN
            RAISE EXCEPTION USING ERRCODE = '23514',
              MESSAGE = 'calibrated Material Model evidence requires the current exact Selection revision';
          END IF;
          SELECT status, youngs_modulus_pa, candidate_sha256, diagnostics_artifact_id,
                 diagnostics_sha256
            INTO candidate_status, candidate_youngs_modulus, candidate_digest,
                 candidate_artifact_id, candidate_artifact_digest
          FROM modeling.calibration_candidate
          WHERE organization_id = NEW.organization_id AND project_id = NEW.project_id
            AND classification = NEW.classification AND id = NEW.calibration_candidate_id
            AND calibration_run_id = NEW.calibration_run_id;
          IF candidate_status IS DISTINCT FROM 'converged'
             OR candidate_digest IS DISTINCT FROM NEW.calibration_candidate_sha256
             OR candidate_artifact_id IS DISTINCT FROM NEW.calibration_diagnostics_artifact_id
             OR candidate_artifact_digest IS DISTINCT FROM NEW.calibration_diagnostics_sha256
             OR candidate_youngs_modulus IS DISTINCT FROM NEW.youngs_modulus_pa THEN
            RAISE EXCEPTION USING ERRCODE = '23514',
              MESSAGE = 'calibrated Material Model values must reproduce its converged Candidate';
          END IF;
          SELECT status, material_model_id, material_model_revision_id
            INTO run_status, run_model_id, run_model_revision_id
          FROM modeling.calibration_run
          WHERE organization_id = NEW.organization_id AND project_id = NEW.project_id
            AND classification = NEW.classification AND id = NEW.calibration_run_id;
          IF run_status IS DISTINCT FROM 'succeeded'
             OR run_model_id IS DISTINCT FROM NEW.aggregate_id
             OR run_model_revision_id IS DISTINCT FROM NEW.based_on_revision_id THEN
            RAISE EXCEPTION USING ERRCODE = '23514',
              MESSAGE = 'calibrated Material Model promotion requires the exact evaluated current IR';
          END IF;
          RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        "CREATE TRIGGER modeling_calibration_candidate_selection_head_only "
        "BEFORE UPDATE OR DELETE ON modeling.calibration_candidate_selection FOR EACH ROW "
        "EXECUTE FUNCTION revisioning.guard_identity_head_update()"
    )
    op.execute(
        "CREATE TRIGGER modeling_calibration_candidate_selection_revision_immutable "
        "BEFORE UPDATE OR DELETE ON modeling.calibration_candidate_selection_revision FOR EACH ROW "
        "EXECUTE FUNCTION revisioning.reject_immutable_row_mutation()"
    )
    op.execute(
        "CREATE TRIGGER modeling_calibration_candidate_selection_revision_guard "
        "BEFORE INSERT ON modeling.calibration_candidate_selection_revision FOR EACH ROW "
        "EXECUTE FUNCTION modeling.guard_calibration_candidate_selection_revision_insert()"
    )
    op.execute(
        "CREATE TRIGGER modeling_reference_calibrated_model_revision_guard "
        "BEFORE INSERT ON modeling.material_model_revision FOR EACH ROW "
        "EXECUTE FUNCTION modeling.guard_reference_calibrated_model_revision_insert()"
    )


def upgrade() -> None:
    _add_candidate_identity_constraint()
    _create_selection_tables()
    _add_model_evidence_constraints()
    op.create_index(
        "ix_modeling_calibration_candidate_selection_tenant_created",
        "calibration_candidate_selection",
        ["organization_id", "project_id", "classification", "created_at"],
        schema="modeling",
    )
    op.create_index(
        "ix_modeling_calibration_candidate_selection_revision_candidate",
        "calibration_candidate_selection_revision",
        [
            "organization_id",
            "project_id",
            "classification",
            "calibration_run_id",
            "calibration_candidate_id",
            "created_at",
        ],
        schema="modeling",
    )
    _secure("calibration_candidate_selection")
    _secure("calibration_candidate_selection_revision")
    _create_guards()


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS modeling_reference_calibrated_model_revision_guard "
        "ON modeling.material_model_revision"
    )
    op.execute("DROP FUNCTION IF EXISTS modeling.guard_reference_calibrated_model_revision_insert()")
    op.execute("DROP INDEX IF EXISTS modeling.ix_modeling_material_model_calibration_candidate")
    for constraint in (
        "fk_modeling_material_model_calibration_diagnostics",
        "fk_modeling_material_model_calibration_candidate",
        "fk_modeling_material_model_calibration_selection",
        "ck_modeling_material_model_calibration_evidence_shape",
        "ck_modeling_material_model_calibration_evidence_kind",
    ):
        op.execute(f"ALTER TABLE modeling.material_model_revision DROP CONSTRAINT IF EXISTS {constraint}")
    for column in (
        "calibration_diagnostics_sha256",
        "calibration_diagnostics_artifact_id",
        "calibration_candidate_sha256",
        "calibration_candidate_id",
        "calibration_run_id",
        "calibration_selection_revision_id",
        "calibration_selection_id",
        "calibration_evidence_kind",
    ):
        op.execute(f"ALTER TABLE modeling.material_model_revision DROP COLUMN IF EXISTS {column}")
    for trigger, table in (
        (
            "modeling_calibration_candidate_selection_revision_guard",
            "calibration_candidate_selection_revision",
        ),
        (
            "modeling_calibration_candidate_selection_revision_immutable",
            "calibration_candidate_selection_revision",
        ),
        ("modeling_calibration_candidate_selection_head_only", "calibration_candidate_selection"),
    ):
        op.execute(f"DROP TRIGGER IF EXISTS {trigger} ON modeling.{table}")
    op.execute("DROP FUNCTION IF EXISTS modeling.guard_calibration_candidate_selection_revision_insert()")
    for table in ("calibration_candidate_selection_revision", "calibration_candidate_selection"):
        op.execute(f"DROP POLICY IF EXISTS modeling_{table}_select ON modeling.{table}")
        op.execute(f"DROP POLICY IF EXISTS modeling_{table}_insert ON modeling.{table}")
        op.execute(f"DROP POLICY IF EXISTS modeling_{table}_update ON modeling.{table}")
    op.drop_table("calibration_candidate_selection_revision", schema="modeling")
    op.drop_table("calibration_candidate_selection", schema="modeling")
    op.execute(
        "ALTER TABLE modeling.calibration_candidate "
        "DROP CONSTRAINT IF EXISTS uq_modeling_calibration_candidate_identity_run"
    )

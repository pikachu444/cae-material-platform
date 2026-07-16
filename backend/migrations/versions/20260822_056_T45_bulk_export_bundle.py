"""T-45 typed Export Selection, durable assembly Job, and immutable Bundle.

Revision ID: 20260822_056_t45_bulk
Revises: 20260821_055_t44_ogden
"""

# ruff: noqa: E501

from __future__ import annotations

from alembic import op

revision = "20260822_056_t45_bulk"
down_revision = "20260821_055_t44_ogden"
branch_labels = None
depends_on = None

_KINDS = (
    "raw_original",
    "dataset_parquet",
    "dataset_csv",
    "model_ir_json",
    "model_ir_schema",
    "solver_mapping_report",
    "solver_card_native",
)


def _quoted(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def upgrade() -> None:
    kinds = _quoted(_KINDS)
    op.execute(
        f"""
        CREATE TABLE exporting.export_selection (
          id uuid NOT NULL, organization_id uuid NOT NULL, project_id uuid NOT NULL,
          classification varchar(64) NOT NULL, current_revision_id uuid NOT NULL,
          selection_label varchar(160) NOT NULL,
          created_at timestamptz NOT NULL, created_by uuid NOT NULL,
          updated_at timestamptz NOT NULL,
          CONSTRAINT pk_exporting_export_selection PRIMARY KEY (organization_id, project_id, id),
          CONSTRAINT uq_exporting_export_selection_scope UNIQUE
            (organization_id, project_id, classification, id),
          CONSTRAINT ck_exporting_export_selection_classification CHECK
            (classification IN ('internal','confidential','restricted','export_controlled')),
          CONSTRAINT ck_exporting_export_selection_label CHECK
            (length(btrim(selection_label)) BETWEEN 1 AND 160 AND selection_label=btrim(selection_label)),
          CONSTRAINT fk_exporting_export_selection_created_by FOREIGN KEY (created_by)
            REFERENCES identity.principal(id)
        );

        CREATE TABLE exporting.export_selection_revision (
          id uuid NOT NULL, aggregate_id uuid NOT NULL,
          organization_id uuid NOT NULL, project_id uuid NOT NULL,
          classification varchar(64) NOT NULL, revision_no bigint NOT NULL,
          based_on_revision_id uuid, schema_id varchar(255) NOT NULL,
          schema_version varchar(64) NOT NULL, content_hash char(64) NOT NULL,
          created_at timestamptz NOT NULL, created_by uuid NOT NULL,
          change_reason text NOT NULL, request_id uuid NOT NULL,
          trace_id varchar(255) NOT NULL, selection_label varchar(160) NOT NULL,
          member_count integer NOT NULL, omission_count integer NOT NULL,
          expected_size_bytes bigint NOT NULL,
          CONSTRAINT pk_exporting_export_selection_revision PRIMARY KEY
            (organization_id, project_id, id),
          CONSTRAINT uq_exporting_export_selection_revision_scope UNIQUE
            (organization_id, project_id, classification, aggregate_id, id),
          CONSTRAINT uq_exporting_export_selection_revision_reference UNIQUE
            (organization_id, project_id, aggregate_id, id),
          CONSTRAINT uq_exporting_export_selection_revision_no UNIQUE
            (organization_id, project_id, aggregate_id, revision_no),
          CONSTRAINT ck_exporting_export_selection_revision_number CHECK (revision_no > 0),
          CONSTRAINT ck_exporting_export_selection_revision_base CHECK
            ((revision_no=1 AND based_on_revision_id IS NULL) OR
             (revision_no>1 AND based_on_revision_id IS NOT NULL)),
          CONSTRAINT ck_exporting_export_selection_revision_hash CHECK
            (content_hash ~ '^[0-9a-f]{{64}}$'),
          CONSTRAINT ck_exporting_export_selection_revision_counts CHECK
            (member_count BETWEEN 1 AND 1000 AND omission_count BETWEEN 0 AND 999 AND
             member_count + omission_count <= 1000 AND
             expected_size_bytes BETWEEN 0 AND 5368709120),
          CONSTRAINT ck_exporting_export_selection_revision_classification CHECK
            (classification IN ('internal','confidential','restricted','export_controlled')),
          CONSTRAINT ck_exporting_export_selection_revision_reason CHECK
            (length(btrim(change_reason)) BETWEEN 1 AND 2000),
          CONSTRAINT fk_exporting_export_selection_revision_identity FOREIGN KEY
            (organization_id, project_id, classification, aggregate_id) REFERENCES
            exporting.export_selection (organization_id, project_id, classification, id),
          CONSTRAINT fk_exporting_export_selection_revision_base FOREIGN KEY
            (organization_id, project_id, based_on_revision_id) REFERENCES
            exporting.export_selection_revision (organization_id, project_id, id),
          CONSTRAINT fk_exporting_export_selection_revision_created_by FOREIGN KEY (created_by)
            REFERENCES identity.principal(id)
        );
        ALTER TABLE exporting.export_selection ADD CONSTRAINT
          fk_exporting_export_selection_current_revision FOREIGN KEY
          (organization_id, project_id, classification, id, current_revision_id) REFERENCES
          exporting.export_selection_revision
          (organization_id, project_id, classification, aggregate_id, id)
          DEFERRABLE INITIALLY DEFERRED;

        CREATE TABLE exporting.export_selection_member (
          organization_id uuid NOT NULL, project_id uuid NOT NULL,
          classification varchar(64) NOT NULL, selection_id uuid NOT NULL,
          selection_revision_id uuid NOT NULL, ordinal integer NOT NULL,
          member_kind varchar(64) NOT NULL,
          raw_asset_id uuid, artifact_id uuid,
          dataset_id uuid, dataset_revision_id uuid,
          material_model_id uuid, material_model_revision_id uuid,
          solver_card_id uuid, solver_card_revision_id uuid,
          archive_path varchar(512) NOT NULL, source_sha256 char(64) NOT NULL,
          source_size_bytes bigint NOT NULL, media_type varchar(255) NOT NULL,
          label varchar(255) NOT NULL,
          CONSTRAINT pk_exporting_export_selection_member PRIMARY KEY
            (organization_id, project_id, selection_revision_id, ordinal),
          CONSTRAINT uq_exporting_export_selection_member_path UNIQUE
            (organization_id, project_id, selection_revision_id, archive_path),
          CONSTRAINT ck_exporting_export_selection_member_ordinal CHECK (ordinal BETWEEN 1 AND 1000),
          CONSTRAINT ck_exporting_export_selection_member_kind CHECK (member_kind IN ({kinds})),
          CONSTRAINT ck_exporting_export_selection_member_classification CHECK
            (classification IN ('internal','confidential','restricted','export_controlled')),
          CONSTRAINT ck_exporting_export_selection_member_digest CHECK
            (source_sha256 ~ '^[0-9a-f]{{64}}$' AND source_size_bytes >= 0),
          CONSTRAINT ck_exporting_export_selection_member_labels CHECK
            (length(btrim(archive_path)) BETWEEN 1 AND 512 AND archive_path=btrim(archive_path) AND
             archive_path !~ '(^/|\\\\|(^|/)\\.\\.(/|$))' AND
             archive_path NOT IN ('manifest.json','checksums.sha256','README.md') AND
             length(btrim(media_type)) BETWEEN 1 AND 255 AND media_type=btrim(media_type) AND
             length(btrim(label)) BETWEEN 1 AND 255 AND label=btrim(label)),
          CONSTRAINT ck_exporting_export_selection_member_typed_source CHECK (
            (member_kind='raw_original' AND raw_asset_id IS NOT NULL AND artifact_id IS NOT NULL AND
             dataset_id IS NULL AND dataset_revision_id IS NULL AND material_model_id IS NULL AND
             material_model_revision_id IS NULL AND solver_card_id IS NULL AND solver_card_revision_id IS NULL)
            OR
            (member_kind IN ('dataset_parquet','dataset_csv') AND raw_asset_id IS NULL AND
             artifact_id IS NOT NULL AND dataset_id IS NOT NULL AND dataset_revision_id IS NOT NULL AND
             material_model_id IS NULL AND material_model_revision_id IS NULL AND
             solver_card_id IS NULL AND solver_card_revision_id IS NULL)
            OR
            (member_kind IN ('model_ir_json','model_ir_schema') AND raw_asset_id IS NULL AND artifact_id IS NULL AND
             dataset_id IS NULL AND dataset_revision_id IS NULL AND material_model_id IS NOT NULL AND
             material_model_revision_id IS NOT NULL AND solver_card_id IS NULL AND solver_card_revision_id IS NULL)
            OR
            (member_kind IN ('solver_mapping_report','solver_card_native') AND raw_asset_id IS NULL AND artifact_id IS NULL AND
             dataset_id IS NULL AND dataset_revision_id IS NULL AND material_model_id IS NULL AND
             material_model_revision_id IS NULL AND solver_card_id IS NOT NULL AND solver_card_revision_id IS NOT NULL)
          ),
          CONSTRAINT fk_exporting_export_selection_member_revision FOREIGN KEY
            (organization_id, project_id, selection_id, selection_revision_id) REFERENCES
            exporting.export_selection_revision (organization_id, project_id, aggregate_id, id),
          CONSTRAINT fk_exporting_export_selection_member_raw_asset FOREIGN KEY
            (organization_id, project_id, classification, raw_asset_id) REFERENCES
            artifact.raw_asset (organization_id, project_id, classification, id),
          CONSTRAINT fk_exporting_export_selection_member_artifact FOREIGN KEY
            (organization_id, project_id, classification, artifact_id) REFERENCES
            artifact.artifact (organization_id, project_id, classification, id),
          CONSTRAINT fk_exporting_export_selection_member_dataset FOREIGN KEY
            (organization_id, project_id, classification, dataset_id, dataset_revision_id) REFERENCES
            datasets.governed_dataset_revision
            (organization_id, project_id, classification, aggregate_id, id),
          CONSTRAINT fk_exporting_export_selection_member_model FOREIGN KEY
            (organization_id, project_id, classification, material_model_id, material_model_revision_id) REFERENCES
            modeling.material_model_revision
            (organization_id, project_id, classification, aggregate_id, id),
          CONSTRAINT fk_exporting_export_selection_member_card FOREIGN KEY
            (organization_id, project_id, classification, solver_card_id, solver_card_revision_id) REFERENCES
            exporting.solver_card_revision
            (organization_id, project_id, classification, aggregate_id, id)
        );

        CREATE TABLE exporting.export_selection_omission (
          organization_id uuid NOT NULL, project_id uuid NOT NULL,
          classification varchar(64) NOT NULL, selection_id uuid NOT NULL,
          selection_revision_id uuid NOT NULL, ordinal integer NOT NULL,
          member_kind varchar(64) NOT NULL,
          raw_asset_id uuid, artifact_id uuid, dataset_id uuid, dataset_revision_id uuid,
          material_model_id uuid, material_model_revision_id uuid,
          solver_card_id uuid, solver_card_revision_id uuid,
          reason_code varchar(80) NOT NULL, reason text NOT NULL,
          CONSTRAINT pk_exporting_export_selection_omission PRIMARY KEY
            (organization_id, project_id, selection_revision_id, ordinal),
          CONSTRAINT ck_exporting_export_selection_omission_ordinal CHECK (ordinal BETWEEN 1 AND 1000),
          CONSTRAINT ck_exporting_export_selection_omission_kind CHECK (member_kind IN ({kinds})),
          CONSTRAINT ck_exporting_export_selection_omission_classification CHECK
            (classification IN ('internal','confidential','restricted','export_controlled')),
          CONSTRAINT ck_exporting_export_selection_omission_reason CHECK
            (length(btrim(reason_code)) BETWEEN 1 AND 80 AND reason_code=btrim(reason_code) AND
             length(btrim(reason)) BETWEEN 1 AND 1000),
          CONSTRAINT ck_exporting_export_selection_omission_typed_source CHECK (
            (member_kind='raw_original' AND raw_asset_id IS NOT NULL AND artifact_id IS NOT NULL AND
             dataset_id IS NULL AND dataset_revision_id IS NULL AND material_model_id IS NULL AND
             material_model_revision_id IS NULL AND solver_card_id IS NULL AND solver_card_revision_id IS NULL)
            OR
            (member_kind IN ('dataset_parquet','dataset_csv') AND raw_asset_id IS NULL AND
             artifact_id IS NOT NULL AND dataset_id IS NOT NULL AND dataset_revision_id IS NOT NULL AND
             material_model_id IS NULL AND material_model_revision_id IS NULL AND
             solver_card_id IS NULL AND solver_card_revision_id IS NULL)
            OR
            (member_kind IN ('model_ir_json','model_ir_schema') AND raw_asset_id IS NULL AND artifact_id IS NULL AND
             dataset_id IS NULL AND dataset_revision_id IS NULL AND material_model_id IS NOT NULL AND
             material_model_revision_id IS NOT NULL AND solver_card_id IS NULL AND solver_card_revision_id IS NULL)
            OR
            (member_kind IN ('solver_mapping_report','solver_card_native') AND raw_asset_id IS NULL AND artifact_id IS NULL AND
             dataset_id IS NULL AND dataset_revision_id IS NULL AND material_model_id IS NULL AND
             material_model_revision_id IS NULL AND solver_card_id IS NOT NULL AND solver_card_revision_id IS NOT NULL)
          ),
          CONSTRAINT fk_exporting_export_selection_omission_revision FOREIGN KEY
            (organization_id, project_id, selection_id, selection_revision_id) REFERENCES
            exporting.export_selection_revision (organization_id, project_id, aggregate_id, id)
        );

        CREATE TABLE exporting.bulk_export_bundle (
          id uuid NOT NULL, organization_id uuid NOT NULL, project_id uuid NOT NULL,
          classification varchar(64) NOT NULL, selection_id uuid NOT NULL,
          selection_revision_id uuid NOT NULL, archive_artifact_id uuid NOT NULL,
          archive_sha256 char(64) NOT NULL, archive_size_bytes bigint NOT NULL,
          manifest_sha256 char(64) NOT NULL, component_count integer NOT NULL,
          omission_count integer NOT NULL, created_at timestamptz NOT NULL,
          created_by uuid NOT NULL,
          CONSTRAINT pk_exporting_bulk_export_bundle PRIMARY KEY (organization_id, project_id, id),
          CONSTRAINT uq_exporting_bulk_export_bundle_scope UNIQUE
            (organization_id, project_id, classification, id),
          CONSTRAINT uq_exporting_bulk_export_bundle_digest UNIQUE
            (organization_id, project_id, selection_revision_id, archive_sha256),
          CONSTRAINT ck_exporting_bulk_export_bundle_digest CHECK
            (archive_sha256 ~ '^[0-9a-f]{{64}}$' AND manifest_sha256 ~ '^[0-9a-f]{{64}}$'),
          CONSTRAINT ck_exporting_bulk_export_bundle_size CHECK
            (archive_size_bytes BETWEEN 1 AND 5368709120 AND component_count BETWEEN 1 AND 1000 AND
             omission_count BETWEEN 0 AND 999 AND component_count+omission_count <= 1000),
          CONSTRAINT ck_exporting_bulk_export_bundle_classification CHECK
            (classification IN ('internal','confidential','restricted','export_controlled')),
          CONSTRAINT fk_exporting_bulk_export_bundle_selection FOREIGN KEY
            (organization_id, project_id, selection_id, selection_revision_id) REFERENCES
            exporting.export_selection_revision (organization_id, project_id, aggregate_id, id),
          CONSTRAINT fk_exporting_bulk_export_bundle_artifact FOREIGN KEY
            (organization_id, project_id, classification, archive_artifact_id) REFERENCES
            artifact.artifact (organization_id, project_id, classification, id),
          CONSTRAINT fk_exporting_bulk_export_bundle_created_by FOREIGN KEY (created_by)
            REFERENCES identity.principal(id)
        );

        CREATE TABLE exporting.bulk_export_job (
          id uuid NOT NULL, organization_id uuid NOT NULL, project_id uuid NOT NULL,
          classification varchar(64) NOT NULL, selection_id uuid NOT NULL,
          selection_revision_id uuid NOT NULL, state varchar(32) NOT NULL,
          attempt_count integer NOT NULL, bundle_id uuid,
          failure_code varchar(80), failure_detail text,
          submitted_at timestamptz NOT NULL, submitted_by uuid NOT NULL,
          started_at timestamptz, completed_at timestamptz,
          CONSTRAINT pk_exporting_bulk_export_job PRIMARY KEY (organization_id, project_id, id),
          CONSTRAINT uq_exporting_bulk_export_job_scope UNIQUE
            (organization_id, project_id, classification, id),
          CONSTRAINT ck_exporting_bulk_export_job_state CHECK
            (state IN ('queued','running','succeeded','failed')),
          CONSTRAINT ck_exporting_bulk_export_job_attempt CHECK (attempt_count BETWEEN 1 AND 100),
          CONSTRAINT ck_exporting_bulk_export_job_classification CHECK
            (classification IN ('internal','confidential','restricted','export_controlled')),
          CONSTRAINT ck_exporting_bulk_export_job_terminal CHECK (
            (state='queued' AND started_at IS NULL AND completed_at IS NULL AND bundle_id IS NULL AND failure_code IS NULL) OR
            (state='running' AND started_at IS NOT NULL AND completed_at IS NULL AND bundle_id IS NULL AND failure_code IS NULL) OR
            (state='succeeded' AND started_at IS NOT NULL AND completed_at IS NOT NULL AND bundle_id IS NOT NULL AND failure_code IS NULL AND failure_detail IS NULL) OR
            (state='failed' AND started_at IS NOT NULL AND completed_at IS NOT NULL AND bundle_id IS NULL AND
             length(btrim(failure_code)) BETWEEN 1 AND 80 AND length(btrim(failure_detail)) BETWEEN 1 AND 1000)
          ),
          CONSTRAINT fk_exporting_bulk_export_job_selection FOREIGN KEY
            (organization_id, project_id, selection_id, selection_revision_id) REFERENCES
            exporting.export_selection_revision (organization_id, project_id, aggregate_id, id),
          CONSTRAINT fk_exporting_bulk_export_job_bundle FOREIGN KEY
            (organization_id, project_id, classification, bundle_id) REFERENCES
            exporting.bulk_export_bundle (organization_id, project_id, classification, id),
          CONSTRAINT fk_exporting_bulk_export_job_submitted_by FOREIGN KEY (submitted_by)
            REFERENCES identity.principal(id)
        );

        CREATE INDEX ix_exporting_selection_member_source ON exporting.export_selection_member
          (organization_id, project_id, member_kind, dataset_revision_id,
           material_model_revision_id, solver_card_revision_id, artifact_id);
        CREATE INDEX ix_exporting_bulk_export_job_state ON exporting.bulk_export_job
          (organization_id, project_id, state, submitted_at);
        CREATE INDEX ix_exporting_bulk_export_bundle_created ON exporting.bulk_export_bundle
          (organization_id, project_id, created_at DESC);
        """
    )
    op.execute(
        """
        CREATE FUNCTION exporting.guard_bulk_export_immutable() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
          RAISE EXCEPTION USING ERRCODE='55000',
            MESSAGE=TG_TABLE_SCHEMA || '.' || TG_TABLE_NAME || ' rows are immutable';
        END $$;
        CREATE TRIGGER export_selection_revision_immutable BEFORE UPDATE OR DELETE
          ON exporting.export_selection_revision FOR EACH ROW
          EXECUTE FUNCTION exporting.guard_bulk_export_immutable();
        CREATE TRIGGER export_selection_member_immutable BEFORE UPDATE OR DELETE
          ON exporting.export_selection_member FOR EACH ROW
          EXECUTE FUNCTION exporting.guard_bulk_export_immutable();
        CREATE TRIGGER export_selection_omission_immutable BEFORE UPDATE OR DELETE
          ON exporting.export_selection_omission FOR EACH ROW
          EXECUTE FUNCTION exporting.guard_bulk_export_immutable();
        CREATE TRIGGER bulk_export_bundle_immutable BEFORE UPDATE OR DELETE
          ON exporting.bulk_export_bundle FOR EACH ROW
          EXECUTE FUNCTION exporting.guard_bulk_export_immutable();

        CREATE FUNCTION exporting.guard_export_selection_head() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
          IF TG_OP='DELETE' THEN
            RAISE EXCEPTION USING ERRCODE='55000', MESSAGE='Export Selection identities cannot be deleted';
          END IF;
          IF NEW.id<>OLD.id OR NEW.organization_id<>OLD.organization_id OR
             NEW.project_id<>OLD.project_id OR NEW.classification<>OLD.classification OR
             NEW.selection_label<>OLD.selection_label OR NEW.created_at<>OLD.created_at OR
             NEW.created_by<>OLD.created_by OR NEW.updated_at<OLD.updated_at THEN
            RAISE EXCEPTION USING ERRCODE='55000', MESSAGE='only Export Selection head advancement is mutable';
          END IF;
          RETURN NEW;
        END $$;
        CREATE TRIGGER export_selection_head_guard BEFORE UPDATE OR DELETE
          ON exporting.export_selection FOR EACH ROW
          EXECUTE FUNCTION exporting.guard_export_selection_head();

        CREATE FUNCTION exporting.validate_export_selection_revision() RETURNS trigger
        LANGUAGE plpgsql AS $$
        DECLARE actual_members integer; actual_omissions integer; actual_size bigint;
        DECLARE max_rank integer; selection_rank integer;
        BEGIN
          SELECT count(*), COALESCE(sum(source_size_bytes),0),
                 max(CASE classification WHEN 'internal' THEN 0 WHEN 'confidential' THEN 1
                     WHEN 'restricted' THEN 2 WHEN 'export_controlled' THEN 3 ELSE -1 END)
            INTO actual_members, actual_size, max_rank
            FROM exporting.export_selection_member
           WHERE organization_id=NEW.organization_id AND project_id=NEW.project_id
             AND selection_revision_id=NEW.id;
          SELECT count(*) INTO actual_omissions FROM exporting.export_selection_omission
           WHERE organization_id=NEW.organization_id AND project_id=NEW.project_id
             AND selection_revision_id=NEW.id;
          selection_rank := CASE NEW.classification WHEN 'internal' THEN 0 WHEN 'confidential' THEN 1
             WHEN 'restricted' THEN 2 WHEN 'export_controlled' THEN 3 ELSE -1 END;
          IF max_rank<>selection_rank THEN
            RAISE EXCEPTION USING ERRCODE='23514',
              MESSAGE='selection classification must equal the maximum component classification';
          END IF;
          IF actual_members<>NEW.member_count OR actual_omissions<>NEW.omission_count OR
             actual_size<>NEW.expected_size_bytes THEN
            RAISE EXCEPTION USING ERRCODE='23514', MESSAGE='Export Selection member snapshot mismatch';
          END IF;
          IF EXISTS (
            SELECT ordinal FROM (
              SELECT ordinal FROM exporting.export_selection_member
               WHERE organization_id=NEW.organization_id AND project_id=NEW.project_id AND selection_revision_id=NEW.id
              UNION ALL
              SELECT ordinal FROM exporting.export_selection_omission
               WHERE organization_id=NEW.organization_id AND project_id=NEW.project_id AND selection_revision_id=NEW.id
            ) all_ordinals GROUP BY ordinal HAVING count(*)>1
          ) THEN
            RAISE EXCEPTION USING ERRCODE='23514', MESSAGE='Export Selection ordinals must be unique';
          END IF;
          RETURN NULL;
        END $$;
        CREATE CONSTRAINT TRIGGER export_selection_revision_snapshot_guard
          AFTER INSERT ON exporting.export_selection_revision DEFERRABLE INITIALLY DEFERRED
          FOR EACH ROW EXECUTE FUNCTION exporting.validate_export_selection_revision();

        CREATE FUNCTION exporting.guard_bulk_export_job_transition() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
          IF TG_OP='DELETE' THEN
            RAISE EXCEPTION USING ERRCODE='55000', MESSAGE='Bulk Export Jobs cannot be deleted';
          END IF;
          IF NEW.id<>OLD.id OR NEW.organization_id<>OLD.organization_id OR NEW.project_id<>OLD.project_id OR
             NEW.classification<>OLD.classification OR NEW.selection_id<>OLD.selection_id OR
             NEW.selection_revision_id<>OLD.selection_revision_id OR NEW.attempt_count<>OLD.attempt_count OR
             NEW.submitted_at<>OLD.submitted_at OR NEW.submitted_by<>OLD.submitted_by THEN
            RAISE EXCEPTION USING ERRCODE='55000', MESSAGE='Bulk Export Job identity fields are immutable';
          END IF;
          IF NOT ((OLD.state='queued' AND NEW.state='running') OR
                  (OLD.state='running' AND NEW.state IN ('succeeded','failed'))) THEN
            RAISE EXCEPTION USING ERRCODE='55000', MESSAGE='invalid Bulk Export Job state transition';
          END IF;
          RETURN NEW;
        END $$;
        CREATE TRIGGER bulk_export_job_transition_guard BEFORE UPDATE OR DELETE
          ON exporting.bulk_export_job FOR EACH ROW
          EXECUTE FUNCTION exporting.guard_bulk_export_job_transition();
        """
    )
    for table in (
        "export_selection",
        "export_selection_revision",
        "export_selection_member",
        "export_selection_omission",
        "bulk_export_job",
        "bulk_export_bundle",
    ):
        op.execute(f"ALTER TABLE exporting.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE exporting.{table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY {table}_select ON exporting.{table} FOR SELECT
              USING (access_control.can_access_row(
                organization_id, project_id, classification, 'export.read'));
            CREATE POLICY {table}_insert ON exporting.{table} FOR INSERT
              WITH CHECK (access_control.can_access_row(
                organization_id, project_id, classification, 'export.execute'));
            """
        )
    op.execute(
        """
        CREATE POLICY bulk_export_job_update ON exporting.bulk_export_job FOR UPDATE
          USING (access_control.can_access_row(
            organization_id, project_id, classification, 'export.execute'))
          WITH CHECK (access_control.can_access_row(
            organization_id, project_id, classification, 'export.execute'));
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM exporting.export_selection_revision LIMIT 1)
             OR EXISTS (SELECT 1 FROM exporting.bulk_export_job LIMIT 1)
             OR EXISTS (SELECT 1 FROM exporting.bulk_export_bundle LIMIT 1) THEN
            RAISE EXCEPTION 'cannot downgrade with immutable Bulk Export records';
          END IF;
        END $$;
        """
    )
    op.execute("DROP FUNCTION exporting.guard_bulk_export_job_transition() CASCADE")
    op.execute("DROP FUNCTION exporting.validate_export_selection_revision() CASCADE")
    op.execute("DROP FUNCTION exporting.guard_export_selection_head() CASCADE")
    op.execute("DROP FUNCTION exporting.guard_bulk_export_immutable() CASCADE")
    op.drop_constraint(
        "fk_exporting_export_selection_current_revision",
        "export_selection",
        schema="exporting",
        type_="foreignkey",
    )
    for table in (
        "bulk_export_job",
        "bulk_export_bundle",
        "export_selection_omission",
        "export_selection_member",
        "export_selection_revision",
        "export_selection",
    ):
        op.drop_table(table, schema="exporting")

"""Add typed Process, Lot/Batch, and Material State genealogy revisions.

Revision ID: 20260814_048_genealogy
Revises: 20260813_047_ogden_cards

Traceability: T-07, FR-CAT-001/002/004, NFR-INT-001, NFR-SEC-003/006,
ADR-001/002/003/006.  The genealogy is an explicit typed relation and is not EAV.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260814_048_genealogy"
down_revision: str | None = "20260813_047_ogden_cards"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _secure(identity: str, revision_table: str) -> None:
    op.execute(
        f"CREATE TRIGGER catalog_{identity}_head_only BEFORE UPDATE OR DELETE "
        f"ON catalog.{identity} FOR EACH ROW "
        "EXECUTE FUNCTION revisioning.guard_identity_head_update()"
    )
    op.execute(
        f"CREATE TRIGGER catalog_{revision_table}_immutable BEFORE UPDATE OR DELETE "
        f"ON catalog.{revision_table} FOR EACH ROW "
        "EXECUTE FUNCTION revisioning.reject_immutable_row_mutation()"
    )
    for table in (identity, revision_table):
        op.execute(f"ALTER TABLE catalog.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE catalog.{table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY catalog_{table}_select ON catalog.{table} FOR SELECT USING "
            "(access_control.can_access_row(organization_id, project_id, "
            "classification, 'catalog.read'))"
        )
        op.execute(
            f"CREATE POLICY catalog_{table}_insert ON catalog.{table} FOR INSERT WITH CHECK "
            "(access_control.can_access_row(organization_id, project_id, "
            "classification, 'catalog.write'))"
        )
    op.execute(
        f"CREATE POLICY catalog_{identity}_update ON catalog.{identity} FOR UPDATE USING "
        "(access_control.can_access_row(organization_id, project_id, "
        "classification, 'catalog.write')) WITH CHECK "
        "(access_control.can_access_row(organization_id, project_id, "
        "classification, 'catalog.write'))"
    )
    op.execute(
        f"CREATE POLICY catalog_{revision_table}_update ON catalog.{revision_table} "
        "FOR UPDATE USING (access_control.can_access_row(organization_id, project_id, "
        "classification, 'catalog.write')) WITH CHECK "
        "(access_control.can_access_row(organization_id, project_id, "
        "classification, 'catalog.write'))"
    )


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE catalog.process_definition (
          id uuid NOT NULL, organization_id uuid NOT NULL, project_id uuid NOT NULL,
          classification varchar(64) NOT NULL, current_revision_id uuid NOT NULL,
          created_at timestamptz NOT NULL, created_by uuid NOT NULL,
          updated_at timestamptz NOT NULL,
          CONSTRAINT pk_catalog_process_definition PRIMARY KEY (organization_id, project_id, id),
          CONSTRAINT uq_catalog_process_definition_scope UNIQUE
            (organization_id, project_id, classification, id),
          CONSTRAINT ck_catalog_process_definition_classification CHECK
            (classification ~ '^[a-z][a-z0-9_.-]{0,63}$')
        );
        CREATE TABLE catalog.process_definition_revision (
          id uuid NOT NULL, aggregate_id uuid NOT NULL,
          organization_id uuid NOT NULL, project_id uuid NOT NULL,
          classification varchar(64) NOT NULL, revision_no bigint NOT NULL,
          based_on_revision_id uuid, schema_id varchar(255) NOT NULL,
          schema_version varchar(64) NOT NULL, content_hash char(64) COLLATE "C" NOT NULL,
          created_at timestamptz NOT NULL, created_by uuid NOT NULL,
          change_reason text NOT NULL, request_id uuid NOT NULL, trace_id varchar(255) NOT NULL,
          process_code varchar(100) NOT NULL, name varchar(200) NOT NULL,
          kind varchar(32) NOT NULL, description text,
          CONSTRAINT pk_catalog_process_definition_revision PRIMARY KEY
            (organization_id, project_id, id),
          CONSTRAINT uq_catalog_process_definition_rev_id UNIQUE
            (organization_id, project_id, aggregate_id, id),
          CONSTRAINT uq_catalog_process_definition_rev_scope UNIQUE
            (organization_id, project_id, classification, aggregate_id, id),
          CONSTRAINT uq_catalog_process_definition_rev_no UNIQUE
            (organization_id, project_id, aggregate_id, revision_no),
          CONSTRAINT fk_catalog_process_definition_rev_identity FOREIGN KEY
            (organization_id, project_id, aggregate_id) REFERENCES catalog.process_definition
            (organization_id, project_id, id) ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_catalog_process_definition_rev_base FOREIGN KEY
            (organization_id, project_id, aggregate_id, based_on_revision_id)
            REFERENCES catalog.process_definition_revision
            (organization_id, project_id, aggregate_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT ck_catalog_process_definition_rev_base CHECK
            ((revision_no=1 AND based_on_revision_id IS NULL) OR
             (revision_no>1 AND based_on_revision_id IS NOT NULL)),
          CONSTRAINT ck_catalog_process_definition_rev_hash CHECK
            (content_hash ~ '^[0-9a-f]{64}$'),
          CONSTRAINT ck_catalog_process_definition_rev_metadata CHECK
            (revision_no>0 AND length(btrim(schema_id)) BETWEEN 1 AND 255 AND
             length(btrim(schema_version)) BETWEEN 1 AND 64 AND
             length(btrim(change_reason)) BETWEEN 1 AND 2000 AND
             length(btrim(trace_id)) BETWEEN 1 AND 255),
          CONSTRAINT ck_catalog_process_definition_content CHECK
            (length(btrim(process_code)) BETWEEN 1 AND 100 AND
             length(btrim(name)) BETWEEN 1 AND 200 AND
             kind IN ('manufacturing','heat_treatment','conditioning','other') AND
             (description IS NULL OR length(btrim(description)) BETWEEN 1 AND 4000))
        );
        ALTER TABLE catalog.process_definition ADD CONSTRAINT
          fk_catalog_process_definition_current FOREIGN KEY
          (organization_id, project_id, id, current_revision_id)
          REFERENCES catalog.process_definition_revision
          (organization_id, project_id, aggregate_id, id)
          ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED;
        CREATE TABLE catalog.material_lot (
          id uuid NOT NULL, organization_id uuid NOT NULL, project_id uuid NOT NULL,
          classification varchar(64) NOT NULL, material_id uuid NOT NULL,
          current_revision_id uuid NOT NULL, created_at timestamptz NOT NULL,
          created_by uuid NOT NULL, updated_at timestamptz NOT NULL,
          CONSTRAINT pk_catalog_material_lot PRIMARY KEY (organization_id, project_id, id),
          CONSTRAINT uq_catalog_material_lot_scope UNIQUE
            (organization_id, project_id, classification, id),
          CONSTRAINT uq_catalog_material_lot_parent UNIQUE
            (organization_id, project_id, classification, id, material_id),
          CONSTRAINT fk_catalog_material_lot_material FOREIGN KEY
            (organization_id, project_id, classification, material_id)
            REFERENCES catalog.material
            (organization_id, project_id, classification, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT ck_catalog_material_lot_classification CHECK
            (classification ~ '^[a-z][a-z0-9_.-]{0,63}$')
        );
        CREATE TABLE catalog.material_lot_revision (
          id uuid NOT NULL, aggregate_id uuid NOT NULL,
          organization_id uuid NOT NULL, project_id uuid NOT NULL,
          classification varchar(64) NOT NULL, revision_no bigint NOT NULL,
          based_on_revision_id uuid, schema_id varchar(255) NOT NULL,
          schema_version varchar(64) NOT NULL, content_hash char(64) COLLATE "C" NOT NULL,
          created_at timestamptz NOT NULL, created_by uuid NOT NULL,
          change_reason text NOT NULL, request_id uuid NOT NULL, trace_id varchar(255) NOT NULL,
          material_id uuid NOT NULL, material_revision_id uuid NOT NULL,
          lot_code varchar(100) NOT NULL, kind varchar(16) NOT NULL,
          manufacturer varchar(200), supplier varchar(200), description text,
          CONSTRAINT pk_catalog_material_lot_revision PRIMARY KEY
            (organization_id, project_id, id),
          CONSTRAINT uq_catalog_material_lot_rev_id UNIQUE
            (organization_id, project_id, aggregate_id, id),
          CONSTRAINT uq_catalog_material_lot_rev_scope UNIQUE
            (organization_id, project_id, classification, aggregate_id, id),
          CONSTRAINT uq_catalog_material_lot_rev_no UNIQUE
            (organization_id, project_id, aggregate_id, revision_no),
          CONSTRAINT fk_catalog_material_lot_rev_identity FOREIGN KEY
            (organization_id, project_id, classification, aggregate_id, material_id)
            REFERENCES catalog.material_lot
            (organization_id, project_id, classification, id, material_id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_catalog_material_lot_rev_material FOREIGN KEY
            (organization_id, project_id, classification, material_id, material_revision_id)
            REFERENCES catalog.material_revision
            (organization_id, project_id, classification, aggregate_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_catalog_material_lot_rev_base FOREIGN KEY
            (organization_id, project_id, aggregate_id, based_on_revision_id)
            REFERENCES catalog.material_lot_revision
            (organization_id, project_id, aggregate_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT ck_catalog_material_lot_rev_base CHECK
            ((revision_no=1 AND based_on_revision_id IS NULL) OR
             (revision_no>1 AND based_on_revision_id IS NOT NULL)),
          CONSTRAINT ck_catalog_material_lot_rev_hash CHECK
            (content_hash ~ '^[0-9a-f]{64}$'),
          CONSTRAINT ck_catalog_material_lot_rev_metadata CHECK
            (revision_no>0 AND length(btrim(schema_id)) BETWEEN 1 AND 255 AND
             length(btrim(schema_version)) BETWEEN 1 AND 64 AND
             length(btrim(change_reason)) BETWEEN 1 AND 2000 AND
             length(btrim(trace_id)) BETWEEN 1 AND 255),
          CONSTRAINT ck_catalog_material_lot_content CHECK
            (length(btrim(lot_code)) BETWEEN 1 AND 100 AND kind IN ('lot','batch') AND
             (manufacturer IS NULL OR length(btrim(manufacturer)) BETWEEN 1 AND 200) AND
             (supplier IS NULL OR length(btrim(supplier)) BETWEEN 1 AND 200) AND
             (description IS NULL OR length(btrim(description)) BETWEEN 1 AND 4000))
        );
        ALTER TABLE catalog.material_lot ADD CONSTRAINT fk_catalog_material_lot_current
          FOREIGN KEY (organization_id, project_id, id, current_revision_id)
          REFERENCES catalog.material_lot_revision
          (organization_id, project_id, aggregate_id, id)
          ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED;

        CREATE TABLE catalog.state_genealogy (
          id uuid NOT NULL, organization_id uuid NOT NULL, project_id uuid NOT NULL,
          classification varchar(64) NOT NULL, material_state_id uuid NOT NULL,
          current_revision_id uuid NOT NULL, created_at timestamptz NOT NULL,
          created_by uuid NOT NULL, updated_at timestamptz NOT NULL,
          CONSTRAINT pk_catalog_state_genealogy PRIMARY KEY (organization_id, project_id, id),
          CONSTRAINT uq_catalog_state_genealogy_scope UNIQUE
            (organization_id, project_id, classification, id),
          CONSTRAINT uq_catalog_state_genealogy_parent UNIQUE
            (organization_id, project_id, classification, id, material_state_id),
          CONSTRAINT uq_catalog_state_genealogy_state UNIQUE
            (organization_id, project_id, material_state_id),
          CONSTRAINT fk_catalog_state_genealogy_state FOREIGN KEY
            (organization_id, project_id, classification, material_state_id)
            REFERENCES catalog.material_state
            (organization_id, project_id, classification, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT ck_catalog_state_genealogy_classification CHECK
            (classification ~ '^[a-z][a-z0-9_.-]{0,63}$')
        );
        CREATE TABLE catalog.state_genealogy_revision (
          id uuid NOT NULL, aggregate_id uuid NOT NULL,
          organization_id uuid NOT NULL, project_id uuid NOT NULL,
          classification varchar(64) NOT NULL, revision_no bigint NOT NULL,
          based_on_revision_id uuid, schema_id varchar(255) NOT NULL,
          schema_version varchar(64) NOT NULL, content_hash char(64) COLLATE "C" NOT NULL,
          created_at timestamptz NOT NULL, created_by uuid NOT NULL,
          change_reason text NOT NULL, request_id uuid NOT NULL, trace_id varchar(255) NOT NULL,
          material_state_id uuid NOT NULL, material_state_revision_id uuid NOT NULL,
          manufacturing_process_id uuid, manufacturing_process_revision_id uuid,
          heat_treatment_process_id uuid, heat_treatment_process_revision_id uuid,
          material_lot_id uuid, material_lot_revision_id uuid, note text,
          CONSTRAINT pk_catalog_state_genealogy_revision PRIMARY KEY
            (organization_id, project_id, id),
          CONSTRAINT uq_catalog_state_genealogy_rev_id UNIQUE
            (organization_id, project_id, aggregate_id, id),
          CONSTRAINT uq_catalog_state_genealogy_rev_scope UNIQUE
            (organization_id, project_id, classification, aggregate_id, id),
          CONSTRAINT uq_catalog_state_genealogy_rev_no UNIQUE
            (organization_id, project_id, aggregate_id, revision_no),
          CONSTRAINT fk_catalog_state_genealogy_rev_identity FOREIGN KEY
            (organization_id, project_id, classification, aggregate_id, material_state_id)
            REFERENCES catalog.state_genealogy
            (organization_id, project_id, classification, id, material_state_id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_catalog_state_genealogy_rev_state FOREIGN KEY
            (organization_id, project_id, classification, material_state_id,
             material_state_revision_id) REFERENCES catalog.material_state_revision
            (organization_id, project_id, classification, aggregate_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_catalog_state_genealogy_rev_manufacturing FOREIGN KEY
            (organization_id, project_id, classification, manufacturing_process_id,
             manufacturing_process_revision_id) REFERENCES catalog.process_definition_revision
            (organization_id, project_id, classification, aggregate_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_catalog_state_genealogy_rev_heat FOREIGN KEY
            (organization_id, project_id, classification, heat_treatment_process_id,
             heat_treatment_process_revision_id) REFERENCES catalog.process_definition_revision
            (organization_id, project_id, classification, aggregate_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_catalog_state_genealogy_rev_lot FOREIGN KEY
            (organization_id, project_id, classification, material_lot_id,
             material_lot_revision_id) REFERENCES catalog.material_lot_revision
            (organization_id, project_id, classification, aggregate_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_catalog_state_genealogy_rev_base FOREIGN KEY
            (organization_id, project_id, aggregate_id, based_on_revision_id)
            REFERENCES catalog.state_genealogy_revision
            (organization_id, project_id, aggregate_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT ck_catalog_state_genealogy_rev_base CHECK
            ((revision_no=1 AND based_on_revision_id IS NULL) OR
             (revision_no>1 AND based_on_revision_id IS NOT NULL)),
          CONSTRAINT ck_catalog_state_genealogy_rev_hash CHECK
            (content_hash ~ '^[0-9a-f]{64}$'),
          CONSTRAINT ck_catalog_state_genealogy_rev_metadata CHECK
            (revision_no>0 AND length(btrim(schema_id)) BETWEEN 1 AND 255 AND
             length(btrim(schema_version)) BETWEEN 1 AND 64 AND
             length(btrim(change_reason)) BETWEEN 1 AND 2000 AND
             length(btrim(trace_id)) BETWEEN 1 AND 255),
          CONSTRAINT ck_catalog_state_genealogy_links CHECK
            ((manufacturing_process_id IS NULL) =
             (manufacturing_process_revision_id IS NULL) AND
             (heat_treatment_process_id IS NULL) =
             (heat_treatment_process_revision_id IS NULL) AND
             (material_lot_id IS NULL) = (material_lot_revision_id IS NULL) AND
             (manufacturing_process_id IS NOT NULL OR
              heat_treatment_process_id IS NOT NULL OR material_lot_id IS NOT NULL)),
          CONSTRAINT ck_catalog_state_genealogy_note CHECK
            (note IS NULL OR length(btrim(note)) BETWEEN 1 AND 2000)
        );
        ALTER TABLE catalog.state_genealogy ADD CONSTRAINT fk_catalog_state_genealogy_current
          FOREIGN KEY (organization_id, project_id, id, current_revision_id)
          REFERENCES catalog.state_genealogy_revision
          (organization_id, project_id, aggregate_id, id)
          ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED;

        CREATE INDEX ix_catalog_process_definition_kind ON catalog.process_definition_revision
          (organization_id, project_id, classification, kind, name);
        CREATE INDEX ix_catalog_material_lot_material ON catalog.material_lot
          (organization_id, project_id, classification, material_id);
        CREATE INDEX ix_catalog_state_genealogy_state ON catalog.state_genealogy
          (organization_id, project_id, classification, material_state_id);
        CREATE INDEX ix_catalog_state_genealogy_sources ON catalog.state_genealogy_revision
          (organization_id, project_id, material_lot_id, manufacturing_process_id,
           heat_treatment_process_id);

        CREATE FUNCTION catalog.validate_state_genealogy_sources()
        RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE
          state_material_id uuid; state_material_revision_id uuid;
          source_kind varchar(32); lot_material_id uuid; lot_material_revision_id uuid;
        BEGIN
          SELECT material_id, material_revision_id
            INTO STRICT state_material_id, state_material_revision_id
          FROM catalog.material_state_revision
          WHERE organization_id=NEW.organization_id AND project_id=NEW.project_id
            AND classification=NEW.classification
            AND aggregate_id=NEW.material_state_id
            AND id=NEW.material_state_revision_id;
          IF NEW.manufacturing_process_id IS NOT NULL THEN
            SELECT kind INTO STRICT source_kind FROM catalog.process_definition_revision
            WHERE organization_id=NEW.organization_id AND project_id=NEW.project_id
              AND classification=NEW.classification
              AND aggregate_id=NEW.manufacturing_process_id
              AND id=NEW.manufacturing_process_revision_id;
            IF source_kind <> 'manufacturing' THEN
              RAISE EXCEPTION 'manufacturing genealogy link requires manufacturing process';
            END IF;
          END IF;
          IF NEW.heat_treatment_process_id IS NOT NULL THEN
            SELECT kind INTO STRICT source_kind FROM catalog.process_definition_revision
            WHERE organization_id=NEW.organization_id AND project_id=NEW.project_id
              AND classification=NEW.classification
              AND aggregate_id=NEW.heat_treatment_process_id
              AND id=NEW.heat_treatment_process_revision_id;
            IF source_kind <> 'heat_treatment' THEN
              RAISE EXCEPTION 'heat-treatment genealogy link requires heat_treatment process';
            END IF;
          END IF;
          IF NEW.material_lot_id IS NOT NULL THEN
            SELECT material_id, material_revision_id
              INTO STRICT lot_material_id, lot_material_revision_id
            FROM catalog.material_lot_revision
            WHERE organization_id=NEW.organization_id AND project_id=NEW.project_id
              AND classification=NEW.classification
              AND aggregate_id=NEW.material_lot_id AND id=NEW.material_lot_revision_id;
            IF lot_material_id <> state_material_id OR
               lot_material_revision_id <> state_material_revision_id THEN
              RAISE EXCEPTION 'genealogy Lot must pin the State Material revision';
            END IF;
          END IF;
          RETURN NEW;
        END $$;
        CREATE CONSTRAINT TRIGGER catalog_state_genealogy_source_guard
          AFTER INSERT ON catalog.state_genealogy_revision
          DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
          EXECUTE FUNCTION catalog.validate_state_genealogy_sources();
        """
    )
    for identity, revision_table in (
        ("process_definition", "process_definition_revision"),
        ("material_lot", "material_lot_revision"),
        ("state_genealogy", "state_genealogy_revision"),
    ):
        _secure(identity, revision_table)


def downgrade() -> None:
    for identity in ("state_genealogy", "material_lot", "process_definition"):
        op.execute(
            f"ALTER TABLE catalog.{identity} DROP CONSTRAINT "
            f"fk_catalog_{identity}_current"
        )
    for table in (
        "state_genealogy_revision",
        "state_genealogy",
        "material_lot_revision",
        "material_lot",
        "process_definition_revision",
        "process_definition",
    ):
        op.execute(f"DROP TABLE catalog.{table}")
    op.execute("DROP FUNCTION IF EXISTS catalog.validate_state_genealogy_sources()")

"""Add Process Run Lot flows and Specimen source genealogy.

Revision ID: 20260815_049_process_run
Revises: 20260814_048_genealogy

Traceability: T-39, FR-CAT-004, NFR-INT-001, NFR-SEC-003/006,
ADR-001/002/003/006.  Ordered child rows are explicit relations, not EAV or JSON.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260815_049_process_run"
down_revision: str | None = "20260814_048_genealogy"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _identity_security(schema: str, table: str, revision_table: str, permission: str) -> None:
    op.execute(
        f"CREATE TRIGGER {schema}_{table}_head_only BEFORE UPDATE OR DELETE "
        f"ON {schema}.{table} FOR EACH ROW "
        "EXECUTE FUNCTION revisioning.guard_identity_head_update()"
    )
    op.execute(
        f"CREATE TRIGGER {schema}_{revision_table}_immutable BEFORE UPDATE OR DELETE "
        f"ON {schema}.{revision_table} FOR EACH ROW "
        "EXECUTE FUNCTION revisioning.reject_immutable_row_mutation()"
    )
    for item in (table, revision_table):
        op.execute(f"ALTER TABLE {schema}.{item} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {schema}.{item} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY {schema}_{item}_select ON {schema}.{item} FOR SELECT USING "
            "(access_control.can_access_row(organization_id, project_id, classification, "
            f"'{permission}.read'))"
        )
        op.execute(
            f"CREATE POLICY {schema}_{item}_insert ON {schema}.{item} FOR INSERT WITH CHECK "
            "(access_control.can_access_row(organization_id, project_id, classification, "
            f"'{permission}.write'))"
        )
    op.execute(
        f"CREATE POLICY {schema}_{table}_update ON {schema}.{table} FOR UPDATE USING "
        "(access_control.can_access_row(organization_id, project_id, classification, "
        f"'{permission}.write')) WITH CHECK "
        "(access_control.can_access_row(organization_id, project_id, classification, "
        f"'{permission}.write'))"
    )
    op.execute(
        f"CREATE POLICY {schema}_{revision_table}_update ON {schema}.{revision_table} "
        "FOR UPDATE USING (access_control.can_access_row(organization_id, project_id, "
        f"classification, '{permission}.write')) WITH CHECK "
        "(access_control.can_access_row(organization_id, project_id, classification, "
        f"'{permission}.write'))"
    )


def _child_security(schema: str, table: str, permission: str) -> None:
    op.execute(
        f"CREATE TRIGGER {schema}_{table}_immutable BEFORE UPDATE OR DELETE ON {schema}.{table} "
        "FOR EACH ROW EXECUTE FUNCTION revisioning.reject_immutable_row_mutation()"
    )
    op.execute(f"ALTER TABLE {schema}.{table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {schema}.{table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY {schema}_{table}_select ON {schema}.{table} FOR SELECT USING "
        "(access_control.can_access_row(organization_id, project_id, classification, "
        f"'{permission}.read'))"
    )
    op.execute(
        f"CREATE POLICY {schema}_{table}_insert ON {schema}.{table} FOR INSERT WITH CHECK "
        "(access_control.can_access_row(organization_id, project_id, classification, "
        f"'{permission}.write'))"
    )


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE catalog.process_run (
          id uuid NOT NULL, organization_id uuid NOT NULL, project_id uuid NOT NULL,
          classification varchar(64) NOT NULL, material_state_id uuid NOT NULL,
          run_code varchar(100) NOT NULL, current_revision_id uuid NOT NULL,
          created_at timestamptz NOT NULL, created_by uuid NOT NULL,
          updated_at timestamptz NOT NULL,
          CONSTRAINT pk_catalog_process_run PRIMARY KEY (organization_id, project_id, id),
          CONSTRAINT uq_catalog_process_run_scope UNIQUE
            (organization_id, project_id, classification, id),
          CONSTRAINT uq_catalog_process_run_parent UNIQUE
            (organization_id, project_id, classification, id, material_state_id, run_code),
          CONSTRAINT uq_catalog_process_run_code UNIQUE
            (organization_id, project_id, classification, material_state_id, run_code),
          CONSTRAINT fk_catalog_process_run_state FOREIGN KEY
            (organization_id, project_id, classification, material_state_id)
            REFERENCES catalog.material_state
            (organization_id, project_id, classification, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT ck_catalog_process_run_code CHECK
            (length(btrim(run_code)) BETWEEN 1 AND 100 AND run_code=btrim(run_code))
        );
        CREATE TABLE catalog.process_run_revision (
          id uuid NOT NULL, aggregate_id uuid NOT NULL,
          organization_id uuid NOT NULL, project_id uuid NOT NULL,
          classification varchar(64) NOT NULL, revision_no bigint NOT NULL,
          based_on_revision_id uuid, schema_id varchar(255) NOT NULL,
          schema_version varchar(64) NOT NULL, content_hash char(64) COLLATE "C" NOT NULL,
          created_at timestamptz NOT NULL, created_by uuid NOT NULL,
          change_reason text NOT NULL, request_id uuid NOT NULL, trace_id varchar(255) NOT NULL,
          process_definition_id uuid NOT NULL, process_definition_revision_id uuid NOT NULL,
          material_state_id uuid NOT NULL, material_state_revision_id uuid NOT NULL,
          run_code varchar(100) NOT NULL, started_at timestamptz NOT NULL, ended_at timestamptz,
          operator_name varchar(200), equipment_reference varchar(255),
          balance_basis varchar(32) NOT NULL, balance_tolerance_fraction numeric(36,24),
          balance_not_assessed_reason text, balance_input_total numeric(54,24),
          balance_output_total numeric(54,24), balance_relative_difference numeric(36,24),
          balance_within_tolerance boolean, note text,
          CONSTRAINT pk_catalog_process_run_revision PRIMARY KEY
            (organization_id, project_id, id),
          CONSTRAINT uq_catalog_process_run_rev_id UNIQUE
            (organization_id, project_id, aggregate_id, id),
          CONSTRAINT uq_catalog_process_run_rev_scope UNIQUE
            (organization_id, project_id, classification, aggregate_id, id),
          CONSTRAINT uq_catalog_process_run_rev_no UNIQUE
            (organization_id, project_id, aggregate_id, revision_no),
          CONSTRAINT fk_catalog_process_run_rev_identity FOREIGN KEY
            (organization_id, project_id, classification, aggregate_id,
             material_state_id, run_code) REFERENCES catalog.process_run
            (organization_id, project_id, classification, id, material_state_id, run_code)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_catalog_process_run_rev_base FOREIGN KEY
            (organization_id, project_id, aggregate_id, based_on_revision_id)
            REFERENCES catalog.process_run_revision
            (organization_id, project_id, aggregate_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_catalog_process_run_rev_process FOREIGN KEY
            (organization_id, project_id, classification, process_definition_id,
             process_definition_revision_id) REFERENCES catalog.process_definition_revision
            (organization_id, project_id, classification, aggregate_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_catalog_process_run_rev_state FOREIGN KEY
            (organization_id, project_id, classification, material_state_id,
             material_state_revision_id) REFERENCES catalog.material_state_revision
            (organization_id, project_id, classification, aggregate_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT ck_catalog_process_run_rev_base CHECK
            ((revision_no=1 AND based_on_revision_id IS NULL) OR
             (revision_no>1 AND based_on_revision_id IS NOT NULL)),
          CONSTRAINT ck_catalog_process_run_rev_hash CHECK (content_hash ~ '^[0-9a-f]{64}$'),
          CONSTRAINT ck_catalog_process_run_rev_metadata CHECK
            (revision_no>0 AND length(btrim(schema_id)) BETWEEN 1 AND 255 AND
             length(btrim(schema_version)) BETWEEN 1 AND 64 AND
             length(btrim(change_reason)) BETWEEN 1 AND 2000 AND
             length(btrim(trace_id)) BETWEEN 1 AND 255),
          CONSTRAINT ck_catalog_process_run_rev_content CHECK
            (length(btrim(run_code)) BETWEEN 1 AND 100 AND run_code=btrim(run_code) AND
             (ended_at IS NULL OR ended_at>=started_at) AND
             (operator_name IS NULL OR length(btrim(operator_name)) BETWEEN 1 AND 200) AND
             (equipment_reference IS NULL OR
              length(btrim(equipment_reference)) BETWEEN 1 AND 255) AND
             (note IS NULL OR length(btrim(note)) BETWEEN 1 AND 2000)),
          CONSTRAINT ck_catalog_process_run_rev_balance CHECK
            ((balance_basis='not_assessed' AND balance_tolerance_fraction IS NULL AND
              length(btrim(balance_not_assessed_reason)) BETWEEN 1 AND 2000 AND
              balance_input_total IS NULL AND balance_output_total IS NULL AND
              balance_relative_difference IS NULL AND balance_within_tolerance IS NULL) OR
             (balance_basis IN ('mass','volume','count') AND
              balance_tolerance_fraction BETWEEN 0 AND 1 AND
              balance_not_assessed_reason IS NULL AND balance_input_total>0 AND
              balance_output_total>0 AND balance_relative_difference>=0 AND
              balance_within_tolerance))
        );
        ALTER TABLE catalog.process_run ADD CONSTRAINT fk_catalog_process_run_current
          FOREIGN KEY (organization_id, project_id, id, current_revision_id)
          REFERENCES catalog.process_run_revision
          (organization_id, project_id, aggregate_id, id)
          ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED;
        CREATE TABLE catalog.process_run_lot_flow (
          process_run_revision_id uuid NOT NULL, process_run_id uuid NOT NULL,
          organization_id uuid NOT NULL, project_id uuid NOT NULL,
          classification varchar(64) NOT NULL, flow_role varchar(8) NOT NULL,
          ordinal integer NOT NULL, material_lot_id uuid NOT NULL,
          material_lot_revision_id uuid NOT NULL, original_quantity numeric(54,24) NOT NULL,
          original_unit varchar(16) NOT NULL, quantity_basis varchar(16) NOT NULL,
          normalized_quantity numeric(54,24) NOT NULL, normalized_unit varchar(16) NOT NULL,
          normalization_factor numeric(36,18) NOT NULL,
          CONSTRAINT pk_catalog_process_run_lot_flow PRIMARY KEY
            (organization_id, project_id, process_run_revision_id, flow_role, ordinal),
          CONSTRAINT uq_catalog_process_run_lot_flow_lot UNIQUE
            (organization_id, project_id, process_run_revision_id, flow_role,
             material_lot_id, material_lot_revision_id),
          CONSTRAINT fk_catalog_process_run_lot_flow_revision FOREIGN KEY
            (organization_id, project_id, classification, process_run_id,
             process_run_revision_id) REFERENCES catalog.process_run_revision
            (organization_id, project_id, classification, aggregate_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_catalog_process_run_lot_flow_lot FOREIGN KEY
            (organization_id, project_id, classification, material_lot_id,
             material_lot_revision_id) REFERENCES catalog.material_lot_revision
            (organization_id, project_id, classification, aggregate_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT ck_catalog_process_run_lot_flow_content CHECK
            (flow_role IN ('input','output') AND ordinal>=0 AND
             original_quantity>0 AND normalized_quantity>0 AND normalization_factor>0 AND
             length(btrim(original_unit)) BETWEEN 1 AND 16 AND
             length(btrim(normalized_unit)) BETWEEN 1 AND 16 AND
             quantity_basis IN ('mass','volume','count'))
        );
        CREATE INDEX ix_catalog_process_run_state ON catalog.process_run
          (organization_id, project_id, classification, material_state_id, run_code);
        CREATE INDEX ix_catalog_process_run_flow_lot ON catalog.process_run_lot_flow
          (organization_id, project_id, classification, material_lot_id,
           material_lot_revision_id, flow_role);

        CREATE TABLE testing.specimen_source_genealogy (
          id uuid NOT NULL, organization_id uuid NOT NULL, project_id uuid NOT NULL,
          classification varchar(64) NOT NULL, specimen_id uuid NOT NULL,
          current_revision_id uuid NOT NULL, created_at timestamptz NOT NULL,
          created_by uuid NOT NULL, updated_at timestamptz NOT NULL,
          CONSTRAINT pk_testing_specimen_source_genealogy PRIMARY KEY
            (organization_id, project_id, id),
          CONSTRAINT uq_testing_specimen_source_genealogy_scope UNIQUE
            (organization_id, project_id, classification, id),
          CONSTRAINT uq_testing_specimen_source_genealogy_parent UNIQUE
            (organization_id, project_id, classification, id, specimen_id),
          CONSTRAINT uq_testing_specimen_source_genealogy_specimen UNIQUE
            (organization_id, project_id, specimen_id),
          CONSTRAINT fk_testing_specimen_source_genealogy_specimen FOREIGN KEY
            (organization_id, project_id, classification, specimen_id)
            REFERENCES testing.specimen
            (organization_id, project_id, classification, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED
        );
        CREATE TABLE testing.specimen_source_genealogy_revision (
          id uuid NOT NULL, aggregate_id uuid NOT NULL,
          organization_id uuid NOT NULL, project_id uuid NOT NULL,
          classification varchar(64) NOT NULL, revision_no bigint NOT NULL,
          based_on_revision_id uuid, schema_id varchar(255) NOT NULL,
          schema_version varchar(64) NOT NULL, content_hash char(64) COLLATE "C" NOT NULL,
          created_at timestamptz NOT NULL, created_by uuid NOT NULL,
          change_reason text NOT NULL, request_id uuid NOT NULL, trace_id varchar(255) NOT NULL,
          specimen_id uuid NOT NULL, specimen_revision_id uuid NOT NULL, note text,
          CONSTRAINT pk_testing_specimen_source_genealogy_revision PRIMARY KEY
            (organization_id, project_id, id),
          CONSTRAINT uq_testing_specimen_source_genealogy_rev_id UNIQUE
            (organization_id, project_id, aggregate_id, id),
          CONSTRAINT uq_testing_specimen_source_genealogy_rev_scope UNIQUE
            (organization_id, project_id, classification, aggregate_id, id),
          CONSTRAINT uq_testing_specimen_source_genealogy_rev_no UNIQUE
            (organization_id, project_id, aggregate_id, revision_no),
          CONSTRAINT fk_testing_specimen_source_genealogy_rev_identity FOREIGN KEY
            (organization_id, project_id, classification, aggregate_id, specimen_id)
            REFERENCES testing.specimen_source_genealogy
            (organization_id, project_id, classification, id, specimen_id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_testing_specimen_source_genealogy_rev_specimen FOREIGN KEY
            (organization_id, project_id, classification, specimen_id,
             specimen_revision_id) REFERENCES testing.specimen_revision
            (organization_id, project_id, classification, aggregate_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_testing_specimen_source_genealogy_rev_base FOREIGN KEY
            (organization_id, project_id, aggregate_id, based_on_revision_id)
            REFERENCES testing.specimen_source_genealogy_revision
            (organization_id, project_id, aggregate_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT ck_testing_specimen_source_genealogy_rev_base CHECK
            ((revision_no=1 AND based_on_revision_id IS NULL) OR
             (revision_no>1 AND based_on_revision_id IS NOT NULL)),
          CONSTRAINT ck_testing_specimen_source_genealogy_rev_hash CHECK
            (content_hash ~ '^[0-9a-f]{64}$'),
          CONSTRAINT ck_testing_specimen_source_genealogy_rev_metadata CHECK
            (revision_no>0 AND length(btrim(schema_id)) BETWEEN 1 AND 255 AND
             length(btrim(schema_version)) BETWEEN 1 AND 64 AND
             length(btrim(change_reason)) BETWEEN 1 AND 2000 AND
             length(btrim(trace_id)) BETWEEN 1 AND 255 AND
             (note IS NULL OR length(btrim(note)) BETWEEN 1 AND 2000))
        );
        ALTER TABLE testing.specimen_source_genealogy ADD CONSTRAINT
          fk_testing_specimen_source_genealogy_current FOREIGN KEY
          (organization_id, project_id, id, current_revision_id)
          REFERENCES testing.specimen_source_genealogy_revision
          (organization_id, project_id, aggregate_id, id)
          ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED;
        CREATE TABLE testing.specimen_source_lot (
          specimen_source_revision_id uuid NOT NULL, specimen_source_genealogy_id uuid NOT NULL,
          organization_id uuid NOT NULL, project_id uuid NOT NULL,
          classification varchar(64) NOT NULL, ordinal integer NOT NULL,
          material_lot_id uuid NOT NULL, material_lot_revision_id uuid NOT NULL, note text,
          CONSTRAINT pk_testing_specimen_source_lot PRIMARY KEY
            (organization_id, project_id, specimen_source_revision_id, ordinal),
          CONSTRAINT uq_testing_specimen_source_lot_ref UNIQUE
            (organization_id, project_id, specimen_source_revision_id,
             material_lot_id, material_lot_revision_id),
          CONSTRAINT fk_testing_specimen_source_lot_revision FOREIGN KEY
            (organization_id, project_id, classification, specimen_source_genealogy_id,
             specimen_source_revision_id)
            REFERENCES testing.specimen_source_genealogy_revision
            (organization_id, project_id, classification, aggregate_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_testing_specimen_source_lot_lot FOREIGN KEY
            (organization_id, project_id, classification, material_lot_id,
             material_lot_revision_id) REFERENCES catalog.material_lot_revision
            (organization_id, project_id, classification, aggregate_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT ck_testing_specimen_source_lot_content CHECK
            (ordinal>=0 AND (note IS NULL OR length(btrim(note)) BETWEEN 1 AND 1000))
        );
        CREATE INDEX ix_testing_specimen_source_lot_ref ON testing.specimen_source_lot
          (organization_id, project_id, classification, material_lot_id,
           material_lot_revision_id);
        """
    )

    op.execute(
        """
        CREATE FUNCTION catalog.validate_process_run_revision()
        RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE
          state_material_id uuid; state_material_revision_id uuid;
          flow_count integer; bad_count integer; input_sum numeric; output_sum numeric;
          expected_unit varchar(16); has_cycle boolean;
        BEGIN
          SELECT material_id, material_revision_id
            INTO STRICT state_material_id, state_material_revision_id
          FROM catalog.material_state_revision
          WHERE organization_id=NEW.organization_id AND project_id=NEW.project_id
            AND classification=NEW.classification AND aggregate_id=NEW.material_state_id
            AND id=NEW.material_state_revision_id;

          SELECT count(*) FILTER (WHERE flow_role='input'),
                 count(*) FILTER (WHERE flow_role='output')
            INTO flow_count, bad_count
          FROM catalog.process_run_lot_flow
          WHERE organization_id=NEW.organization_id AND project_id=NEW.project_id
            AND process_run_revision_id=NEW.id;
          IF flow_count<1 OR bad_count<1 THEN
            RAISE EXCEPTION 'Process Run requires at least one input and output Lot';
          END IF;

          SELECT count(*) INTO bad_count
          FROM catalog.process_run_lot_flow flow
          JOIN catalog.material_lot_revision lot
            ON lot.organization_id=flow.organization_id AND lot.project_id=flow.project_id
           AND lot.classification=flow.classification
           AND lot.aggregate_id=flow.material_lot_id AND lot.id=flow.material_lot_revision_id
          WHERE flow.organization_id=NEW.organization_id AND flow.project_id=NEW.project_id
            AND flow.process_run_revision_id=NEW.id
            AND (lot.material_id<>state_material_id OR
                 lot.material_revision_id<>state_material_revision_id);
          IF bad_count>0 THEN
            RAISE EXCEPTION 'Process Run Lot must pin the State Material revision';
          END IF;

          IF EXISTS (
            SELECT 1 FROM catalog.process_run_lot_flow i
            JOIN catalog.process_run_lot_flow o
              ON o.organization_id=i.organization_id AND o.project_id=i.project_id
             AND o.process_run_revision_id=i.process_run_revision_id
             AND o.material_lot_id=i.material_lot_id
             AND o.material_lot_revision_id=i.material_lot_revision_id
            WHERE i.organization_id=NEW.organization_id AND i.project_id=NEW.project_id
              AND i.process_run_revision_id=NEW.id AND i.flow_role='input'
              AND o.flow_role='output'
          ) THEN
            RAISE EXCEPTION 'same Lot revision cannot be both Process Run input and output';
          END IF;

          IF NEW.balance_basis<>'not_assessed' THEN
            expected_unit := CASE NEW.balance_basis WHEN 'mass' THEN 'kg'
              WHEN 'volume' THEN 'm3' ELSE '1' END;
            SELECT count(*),
                   coalesce(sum(normalized_quantity) FILTER (WHERE flow_role='input'),0),
                   coalesce(sum(normalized_quantity) FILTER (WHERE flow_role='output'),0)
              INTO bad_count, input_sum, output_sum
            FROM catalog.process_run_lot_flow
            WHERE organization_id=NEW.organization_id AND project_id=NEW.project_id
              AND process_run_revision_id=NEW.id
              AND (quantity_basis<>NEW.balance_basis OR normalized_unit<>expected_unit);
            IF bad_count>0 THEN
              RAISE EXCEPTION 'assessed Process Run flow dimension mismatch';
            END IF;
            SELECT sum(normalized_quantity) FILTER (WHERE flow_role='input'),
                   sum(normalized_quantity) FILTER (WHERE flow_role='output')
              INTO input_sum, output_sum
            FROM catalog.process_run_lot_flow
            WHERE organization_id=NEW.organization_id AND project_id=NEW.project_id
              AND process_run_revision_id=NEW.id;
            IF input_sum<>NEW.balance_input_total OR output_sum<>NEW.balance_output_total OR
               round(abs(input_sum-output_sum)/input_sum,24)<>
                 NEW.balance_relative_difference OR
               abs(input_sum-output_sum)/input_sum>NEW.balance_tolerance_fraction THEN
              RAISE EXCEPTION 'stored Process Run balance evidence is inconsistent';
            END IF;
          END IF;

          WITH RECURSIVE edges(source_lot, target_lot) AS (
            SELECT i.material_lot_revision_id, o.material_lot_revision_id
            FROM catalog.process_run run
            JOIN catalog.process_run_lot_flow i
              ON i.organization_id=run.organization_id AND i.project_id=run.project_id
             AND i.process_run_revision_id=run.current_revision_id AND i.flow_role='input'
            JOIN catalog.process_run_lot_flow o
              ON o.organization_id=run.organization_id AND o.project_id=run.project_id
             AND o.process_run_revision_id=run.current_revision_id AND o.flow_role='output'
            WHERE run.organization_id=NEW.organization_id AND run.project_id=NEW.project_id
              AND run.classification=NEW.classification
          ), walk(source_lot, target_lot, path, cycle) AS (
            SELECT source_lot, target_lot, ARRAY[source_lot,target_lot],
                   source_lot=target_lot FROM edges
            UNION ALL
            SELECT walk.source_lot, edges.target_lot, walk.path||edges.target_lot,
                   edges.target_lot=ANY(walk.path)
            FROM walk JOIN edges ON edges.source_lot=walk.target_lot
            WHERE NOT walk.cycle
          ) SELECT coalesce(bool_or(cycle),false) INTO has_cycle FROM walk;
          IF has_cycle THEN
            RAISE EXCEPTION 'Process Run Lot genealogy cycle detected';
          END IF;
          RETURN NEW;
        END $$;
        CREATE CONSTRAINT TRIGGER catalog_process_run_revision_guard
          AFTER INSERT ON catalog.process_run_revision
          DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
          EXECUTE FUNCTION catalog.validate_process_run_revision();

        CREATE FUNCTION testing.validate_specimen_source_revision()
        RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE specimen_material_id uuid; specimen_material_revision_id uuid; bad_count integer;
        BEGIN
          SELECT material_id, material_revision_id
            INTO STRICT specimen_material_id, specimen_material_revision_id
          FROM testing.specimen_revision
          WHERE organization_id=NEW.organization_id AND project_id=NEW.project_id
            AND classification=NEW.classification AND aggregate_id=NEW.specimen_id
            AND id=NEW.specimen_revision_id;
          SELECT count(*) INTO bad_count FROM testing.specimen_source_lot source
          JOIN catalog.material_lot_revision lot
            ON lot.organization_id=source.organization_id AND lot.project_id=source.project_id
           AND lot.classification=source.classification
           AND lot.aggregate_id=source.material_lot_id
           AND lot.id=source.material_lot_revision_id
          WHERE source.organization_id=NEW.organization_id AND source.project_id=NEW.project_id
            AND source.specimen_source_revision_id=NEW.id
            AND (lot.material_id<>specimen_material_id OR
                 lot.material_revision_id<>specimen_material_revision_id);
          IF NOT EXISTS (
            SELECT 1 FROM testing.specimen_source_lot source
            WHERE source.organization_id=NEW.organization_id
              AND source.project_id=NEW.project_id
              AND source.specimen_source_revision_id=NEW.id
          ) THEN
            RAISE EXCEPTION 'Specimen source genealogy requires at least one Lot';
          END IF;
          IF bad_count>0 THEN
            RAISE EXCEPTION 'Specimen source Lot must pin the Specimen Material revision';
          END IF;
          RETURN NEW;
        END $$;
        CREATE CONSTRAINT TRIGGER testing_specimen_source_revision_guard
          AFTER INSERT ON testing.specimen_source_genealogy_revision
          DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
          EXECUTE FUNCTION testing.validate_specimen_source_revision();
        """
    )
    _identity_security("catalog", "process_run", "process_run_revision", "catalog")
    _child_security("catalog", "process_run_lot_flow", "catalog")
    _identity_security(
        "testing", "specimen_source_genealogy", "specimen_source_genealogy_revision", "testing"
    )
    _child_security("testing", "specimen_source_lot", "testing")


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS testing.validate_specimen_source_revision() CASCADE")
    op.execute("DROP FUNCTION IF EXISTS catalog.validate_process_run_revision() CASCADE")
    op.execute(
        "ALTER TABLE testing.specimen_source_genealogy DROP CONSTRAINT "
        "fk_testing_specimen_source_genealogy_current"
    )
    op.execute(
        "ALTER TABLE catalog.process_run DROP CONSTRAINT fk_catalog_process_run_current"
    )
    for schema, table in (
        ("testing", "specimen_source_lot"),
        ("testing", "specimen_source_genealogy_revision"),
        ("testing", "specimen_source_genealogy"),
        ("catalog", "process_run_lot_flow"),
        ("catalog", "process_run_revision"),
        ("catalog", "process_run"),
    ):
        op.execute(f"DROP TABLE {schema}.{table}")

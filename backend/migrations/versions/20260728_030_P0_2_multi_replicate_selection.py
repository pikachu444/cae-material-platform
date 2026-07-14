"""Add immutable ordered multi-replicate Dataset Selections.

Revision ID: 20260728_030_p02
Revises: 20260727_029_p0
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260728_030_p02"
down_revision: str | None = "20260727_029_p0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE datasets.dataset_selection "
        "ADD COLUMN selection_kind varchar(64) NOT NULL "
        "DEFAULT 'reference_curve_dataset_revision'"
    )
    op.execute(
        "ALTER TABLE datasets.dataset_selection_revision "
        "ADD COLUMN selection_kind varchar(64) NOT NULL "
        "DEFAULT 'reference_curve_dataset_revision'"
    )
    op.execute(
        "ALTER TABLE datasets.dataset_selection "
        "ALTER COLUMN selection_kind DROP DEFAULT"
    )
    op.execute(
        "ALTER TABLE datasets.dataset_selection_revision "
        "ALTER COLUMN selection_kind DROP DEFAULT"
    )
    op.execute(
        "ALTER TABLE datasets.dataset_selection_revision "
        "ALTER COLUMN dataset_id DROP NOT NULL, "
        "ALTER COLUMN dataset_revision_id DROP NOT NULL"
    )
    op.execute(
        "ALTER TABLE datasets.dataset_selection_revision "
        "DROP CONSTRAINT ck_datasets_dataset_selection_revision_member_count"
    )
    op.execute(
        "ALTER TABLE datasets.dataset_selection_revision "
        "ADD CONSTRAINT ck_datasets_dataset_selection_revision_shape CHECK ("
        "(selection_kind = 'reference_curve_dataset_revision' "
        " AND member_count = 1 AND dataset_id IS NOT NULL AND dataset_revision_id IS NOT NULL) OR "
        "(selection_kind = 'reference_tensile_replicate_set' "
        " AND member_count BETWEEN 2 AND 50 AND dataset_id IS NULL "
        "AND dataset_revision_id IS NULL))"
    )
    op.execute(
        "ALTER TABLE datasets.dataset_selection "
        "ADD CONSTRAINT ck_datasets_dataset_selection_kind CHECK "
        "(selection_kind IN ('reference_curve_dataset_revision', "
        "'reference_tensile_replicate_set'))"
    )
    op.execute(
        "ALTER TABLE datasets.dataset_selection_revision "
        "ADD CONSTRAINT ck_datasets_dataset_selection_revision_kind CHECK "
        "(selection_kind IN ('reference_curve_dataset_revision', "
        "'reference_tensile_replicate_set'))"
    )
    op.execute(
        "ALTER TABLE datasets.dataset_selection "
        "ADD CONSTRAINT uq_datasets_dataset_selection_identity_kind UNIQUE "
        "(organization_id, project_id, id, selection_kind)"
    )
    op.execute(
        "ALTER TABLE datasets.dataset_selection_revision "
        "ADD CONSTRAINT fk_datasets_dataset_selection_revision_identity_kind "
        "FOREIGN KEY (organization_id, project_id, aggregate_id, selection_kind) "
        "REFERENCES datasets.dataset_selection "
        "(organization_id, project_id, id, selection_kind) "
        "ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED"
    )
    op.execute(
        """
        CREATE TABLE datasets.dataset_selection_member (
          organization_id uuid NOT NULL,
          project_id uuid NOT NULL,
          classification varchar(64) NOT NULL,
          selection_id uuid NOT NULL,
          selection_revision_id uuid NOT NULL,
          ordinal smallint NOT NULL,
          dataset_id uuid NOT NULL,
          dataset_revision_id uuid NOT NULL,
          test_run_id uuid NOT NULL,
          test_run_revision_id uuid NOT NULL,
          CONSTRAINT pk_datasets_dataset_selection_member PRIMARY KEY
            (organization_id, project_id, selection_revision_id, ordinal),
          CONSTRAINT ck_datasets_dataset_selection_member_ordinal CHECK
            (ordinal BETWEEN 0 AND 49),
          CONSTRAINT uq_datasets_dataset_selection_member_dataset UNIQUE
            (organization_id, project_id, selection_revision_id, dataset_revision_id),
          CONSTRAINT uq_datasets_dataset_selection_member_test_run UNIQUE
            (organization_id, project_id, selection_revision_id, test_run_revision_id),
          CONSTRAINT fk_datasets_dataset_selection_member_selection_revision FOREIGN KEY
            (organization_id, project_id, classification, selection_id,
             selection_revision_id)
            REFERENCES datasets.dataset_selection_revision
            (organization_id, project_id, classification, aggregate_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_datasets_dataset_selection_member_dataset_revision FOREIGN KEY
            (organization_id, project_id, classification, dataset_id, dataset_revision_id)
            REFERENCES datasets.dataset_revision
            (organization_id, project_id, classification, aggregate_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_datasets_dataset_selection_member_test_run_revision FOREIGN KEY
            (organization_id, project_id, classification, test_run_id,
             test_run_revision_id)
            REFERENCES testing.test_run_revision
            (organization_id, project_id, classification, aggregate_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED
        )
        """
    )
    op.execute(
        "CREATE INDEX ix_datasets_dataset_selection_member_dataset_revision "
        "ON datasets.dataset_selection_member "
        "(organization_id, project_id, classification, dataset_revision_id)"
    )
    op.execute(
        "CREATE INDEX ix_datasets_dataset_selection_member_test_run_revision "
        "ON datasets.dataset_selection_member "
        "(organization_id, project_id, classification, test_run_revision_id)"
    )
    op.execute(
        """
        INSERT INTO datasets.dataset_selection_member
          (organization_id, project_id, classification, selection_id,
           selection_revision_id, ordinal, dataset_id, dataset_revision_id,
           test_run_id, test_run_revision_id)
        SELECT s.organization_id, s.project_id, s.classification, s.aggregate_id,
               s.id, 0, s.dataset_id, s.dataset_revision_id,
               d.test_run_id, d.test_run_revision_id
        FROM datasets.dataset_selection_revision s
        JOIN datasets.dataset_revision d
          ON d.organization_id = s.organization_id
         AND d.project_id = s.project_id
         AND d.classification = s.classification
         AND d.aggregate_id = s.dataset_id
         AND d.id = s.dataset_revision_id
        WHERE s.selection_kind = 'reference_curve_dataset_revision'
        """
    )
    op.execute("ALTER TABLE datasets.dataset_selection_member ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE datasets.dataset_selection_member FORCE ROW LEVEL SECURITY")
    for operation, predicate, permission in (
        ("SELECT", "USING", "dataset.read"),
        ("INSERT", "WITH CHECK", "dataset.write"),
    ):
        op.execute(
            f"CREATE POLICY datasets_dataset_selection_member_{operation.lower()} "
            "ON datasets.dataset_selection_member "
            f"FOR {operation} {predicate} (access_control.can_access_row("
            "organization_id, project_id, classification, "
            f"'{permission}'))"
        )
    op.execute(
        "CREATE TRIGGER datasets_dataset_selection_member_immutable "
        "BEFORE UPDATE OR DELETE ON datasets.dataset_selection_member FOR EACH ROW "
        "EXECUTE FUNCTION revisioning.reject_immutable_row_mutation()"
    )
    op.execute(
        """
        CREATE FUNCTION datasets.guard_reference_dataset_selection_member_insert()
        RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE source datasets.dataset_revision%ROWTYPE;
        BEGIN
          SELECT * INTO source FROM datasets.dataset_revision
          WHERE organization_id = NEW.organization_id
            AND project_id = NEW.project_id
            AND classification = NEW.classification
            AND aggregate_id = NEW.dataset_id
            AND id = NEW.dataset_revision_id;
          IF NOT FOUND OR source.representation NOT IN ('normalized', 'processed')
             OR source.test_run_id <> NEW.test_run_id
             OR source.test_run_revision_id <> NEW.test_run_revision_id THEN
            RAISE EXCEPTION USING ERRCODE = '23514',
              MESSAGE = 'Selection member must pin a normalized/processed Dataset '
                        'and its Test Run revision';
          END IF;
          RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        "CREATE TRIGGER datasets_dataset_selection_member_reference_guard "
        "BEFORE INSERT ON datasets.dataset_selection_member FOR EACH ROW "
        "EXECUTE FUNCTION datasets.guard_reference_dataset_selection_member_insert()"
    )
    op.execute(
        """
        CREATE FUNCTION datasets.validate_dataset_selection_member_count()
        RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE expected_count integer; actual_count integer;
        BEGIN
          SELECT member_count INTO expected_count
          FROM datasets.dataset_selection_revision
          WHERE organization_id = NEW.organization_id
            AND project_id = NEW.project_id AND id = NEW.selection_revision_id;
          SELECT count(*) INTO actual_count
          FROM datasets.dataset_selection_member
          WHERE organization_id = NEW.organization_id
            AND project_id = NEW.project_id
            AND selection_revision_id = NEW.selection_revision_id;
          IF expected_count IS NULL OR actual_count <> expected_count THEN
            RAISE EXCEPTION USING ERRCODE = '23514',
              MESSAGE = 'Selection member rows must match the immutable revision member_count';
          END IF;
          RETURN NULL;
        END;
        $$
        """
    )
    op.execute(
        "CREATE CONSTRAINT TRIGGER datasets_dataset_selection_member_count_guard "
        "AFTER INSERT ON datasets.dataset_selection_member DEFERRABLE INITIALLY DEFERRED "
        "FOR EACH ROW EXECUTE FUNCTION datasets.validate_dataset_selection_member_count()"
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION datasets.guard_reference_dataset_selection_revision_insert()
        RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE selected_representation text;
        BEGIN
          IF NEW.selection_kind = 'reference_tensile_replicate_set' THEN
            RETURN NEW;
          END IF;
          SELECT representation INTO selected_representation
          FROM datasets.dataset_revision
          WHERE organization_id = NEW.organization_id
            AND project_id = NEW.project_id
            AND classification = NEW.classification
            AND aggregate_id = NEW.dataset_id AND id = NEW.dataset_revision_id;
          IF selected_representation NOT IN ('normalized', 'processed') THEN
            RAISE EXCEPTION USING ERRCODE = '23514',
              MESSAGE = 'reference Dataset Selection requires a normalized or processed '
                        'Dataset revision';
          END IF;
          RETURN NEW;
        END;
        $$
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$ BEGIN
          IF EXISTS (SELECT 1 FROM datasets.dataset_selection
                     WHERE selection_kind = 'reference_tensile_replicate_set') THEN
            RAISE EXCEPTION USING ERRCODE = '55000',
              MESSAGE = 'cannot downgrade while multi-replicate Selections exist';
          END IF;
        END $$
        """
    )
    op.execute(
        "DROP TRIGGER datasets_dataset_selection_member_count_guard "
        "ON datasets.dataset_selection_member"
    )
    op.execute("DROP FUNCTION datasets.validate_dataset_selection_member_count()")
    op.execute(
        "DROP TRIGGER datasets_dataset_selection_member_reference_guard "
        "ON datasets.dataset_selection_member"
    )
    op.execute("DROP FUNCTION datasets.guard_reference_dataset_selection_member_insert()")
    op.execute("DROP TABLE datasets.dataset_selection_member")
    op.execute(
        "ALTER TABLE datasets.dataset_selection_revision "
        "DROP CONSTRAINT fk_datasets_dataset_selection_revision_identity_kind"
    )
    op.execute(
        "ALTER TABLE datasets.dataset_selection "
        "DROP CONSTRAINT uq_datasets_dataset_selection_identity_kind, "
        "DROP CONSTRAINT ck_datasets_dataset_selection_kind"
    )
    op.execute(
        "ALTER TABLE datasets.dataset_selection_revision "
        "DROP CONSTRAINT ck_datasets_dataset_selection_revision_kind, "
        "DROP CONSTRAINT ck_datasets_dataset_selection_revision_shape"
    )
    op.execute(
        "ALTER TABLE datasets.dataset_selection_revision "
        "ALTER COLUMN dataset_id SET NOT NULL, "
        "ALTER COLUMN dataset_revision_id SET NOT NULL, "
        "ADD CONSTRAINT ck_datasets_dataset_selection_revision_member_count "
        "CHECK (member_count = 1)"
    )
    op.execute("ALTER TABLE datasets.dataset_selection_revision DROP COLUMN selection_kind")
    op.execute("ALTER TABLE datasets.dataset_selection DROP COLUMN selection_kind")

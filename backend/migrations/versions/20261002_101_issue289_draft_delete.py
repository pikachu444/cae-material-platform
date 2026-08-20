"""Issue #289 narrow physical deletion for unused unpublished r1 catalog drafts.

Revision ID: 20261002_101_issue289_delete
Revises: 20261001_100_issue246_source_v2
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20261002_101_issue289_delete"
down_revision: str | None = "20261001_100_issue246_source_v2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_IDENTITIES = (
    ("database", "catalog.database"),
    ("profile", "catalog.profile"),
    ("schema_table", "catalog.configurable_table"),
    ("attribute_definition", "catalog.attribute_definition"),
    ("layout", "catalog.layout"),
    ("subset", "catalog.subset"),
    ("link_type", "catalog.link_type"),
)


def _replace_identity_revision_cycle(table: str, *, on_delete: str) -> None:
    """Keep the identity/revision cycle deferred so one authorized pair can be removed."""

    op.execute(
        f"""
        ALTER TABLE catalog.{table}
          DROP CONSTRAINT fk_catalog_{table}_current_revision;
        ALTER TABLE catalog.{table}
          ADD CONSTRAINT fk_catalog_{table}_current_revision
          FOREIGN KEY (organization_id, project_id, id, current_revision_id)
          REFERENCES catalog.{table}_revision
            (organization_id, project_id, aggregate_id, id)
          ON DELETE {on_delete} DEFERRABLE INITIALLY DEFERRED;
        ALTER TABLE catalog.{table}_revision
          DROP CONSTRAINT fk_catalog_{table}_revision_identity;
        ALTER TABLE catalog.{table}_revision
          ADD CONSTRAINT fk_catalog_{table}_revision_identity
          FOREIGN KEY (organization_id, project_id, aggregate_id)
          REFERENCES catalog.{table} (organization_id, project_id, id)
          ON DELETE {on_delete} DEFERRABLE INITIALLY DEFERRED;
        """
    )


def upgrade() -> None:
    # PostgreSQL checks ON DELETE RESTRICT immediately even on a declared deferred
    # constraint. NO ACTION retains the same protection at transaction end while
    # permitting the authorized function to remove the identity/revision pair atomically.
    for table, _aggregate_type in _IDENTITIES:
        _replace_identity_revision_cycle(table, on_delete="NO ACTION")

    # Callers cannot populate this table.  It is a transaction-local capability
    # used by the SECURITY DEFINER delete function and the replacement guards.
    op.execute(
        """
        CREATE TABLE catalog.draft_delete_authorization (
          backend_pid integer NOT NULL,
          transaction_id bigint NOT NULL,
          table_name text NOT NULL,
          aggregate_id uuid NOT NULL,
          organization_id uuid NOT NULL,
          project_id uuid NOT NULL,
          classification varchar(64) NOT NULL,
          PRIMARY KEY (backend_pid, transaction_id, table_name, aggregate_id)
        );
        REVOKE ALL ON catalog.draft_delete_authorization FROM PUBLIC;

        CREATE FUNCTION catalog.is_draft_delete_authorized(
          p_table_name text,
          p_aggregate_id uuid,
          p_organization_id uuid,
          p_project_id uuid,
          p_classification text
        ) RETURNS boolean
        LANGUAGE sql
        STABLE
        SECURITY DEFINER
        SET search_path = pg_catalog, catalog
        AS $$
          SELECT EXISTS (
            SELECT 1
              FROM catalog.draft_delete_authorization AS draft_auth
             WHERE draft_auth.backend_pid = pg_backend_pid()
               AND draft_auth.transaction_id = txid_current()
               AND draft_auth.table_name = p_table_name
               AND draft_auth.aggregate_id = p_aggregate_id
               AND draft_auth.organization_id = p_organization_id
               AND draft_auth.project_id = p_project_id
               AND draft_auth.classification = p_classification
          )
        $$;

        CREATE FUNCTION catalog.guard_configurable_identity_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = pg_catalog, catalog
        AS $$
        BEGIN
          IF TG_OP = 'DELETE' THEN
            IF catalog.is_draft_delete_authorized(
              TG_TABLE_NAME, OLD.id, OLD.organization_id, OLD.project_id, OLD.classification
            ) THEN
              RETURN OLD;
            END IF;
            RAISE EXCEPTION USING
              ERRCODE = '55000',
              MESSAGE = format(
                '%I.%I identities cannot be deleted', TG_TABLE_SCHEMA, TG_TABLE_NAME
              );
          END IF;
          IF (to_jsonb(NEW) - ARRAY['current_revision_id', 'updated_at'])
             IS DISTINCT FROM
             (to_jsonb(OLD) - ARRAY['current_revision_id', 'updated_at']) THEN
            RAISE EXCEPTION USING
              ERRCODE = '55000',
              MESSAGE = format(
                '%I.%I identity fields are immutable', TG_TABLE_SCHEMA, TG_TABLE_NAME
              );
          END IF;
          RETURN NEW;
        END
        $$;

        CREATE FUNCTION catalog.guard_configurable_immutable_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = pg_catalog, catalog
        AS $$
        DECLARE
          row_json jsonb := to_jsonb(OLD);
          aggregate uuid := COALESCE(
            NULLIF(row_json->>'aggregate_id', '')::uuid,
            NULLIF(row_json->>'layout_id', '')::uuid
          );
        BEGIN
          IF TG_OP = 'DELETE' AND catalog.is_draft_delete_authorized(
            TG_TABLE_NAME,
            aggregate,
            OLD.organization_id,
            OLD.project_id,
            OLD.classification
          ) THEN
            RETURN OLD;
          END IF;
          RAISE EXCEPTION USING
            ERRCODE = '55000',
            MESSAGE = format('%I.%I rows are immutable', TG_TABLE_SCHEMA, TG_TABLE_NAME);
        END
        $$;
        """
    )

    for table, _aggregate_type in _IDENTITIES:
        op.execute(f"DROP TRIGGER catalog_{table}_head_only ON catalog.{table}")
        op.execute(
            f"CREATE TRIGGER catalog_{table}_head_only BEFORE UPDATE OR DELETE "
            f"ON catalog.{table} FOR EACH ROW "
            "EXECUTE FUNCTION catalog.guard_configurable_identity_mutation()"
        )
        op.execute(
            f"DROP TRIGGER catalog_{table}_revision_immutable ON catalog.{table}_revision"
        )
        op.execute(
            f"CREATE TRIGGER catalog_{table}_revision_immutable BEFORE UPDATE OR DELETE "
            f"ON catalog.{table}_revision FOR EACH ROW "
            "EXECUTE FUNCTION catalog.guard_configurable_immutable_mutation()"
        )
        op.execute(
            f"CREATE POLICY catalog_{table}_draft_delete ON catalog.{table} FOR DELETE USING ("
            "catalog.is_draft_delete_authorized("
            f"'{table}', id, organization_id, project_id, classification))"
        )
        op.execute(
            f"CREATE POLICY catalog_{table}_revision_draft_delete ON catalog.{table}_revision "
            "FOR DELETE USING (catalog.is_draft_delete_authorized("
            f"'{table}_revision', aggregate_id, organization_id, project_id, classification))"
        )

    op.execute(
        """
        DROP TRIGGER catalog_layout_item_immutable ON catalog.layout_item;
        CREATE TRIGGER catalog_layout_item_immutable BEFORE UPDATE OR DELETE
          ON catalog.layout_item FOR EACH ROW
          EXECUTE FUNCTION catalog.guard_configurable_immutable_mutation();
        CREATE POLICY catalog_layout_item_draft_delete ON catalog.layout_item FOR DELETE USING (
          catalog.is_draft_delete_authorized(
            'layout_item', layout_id, organization_id, project_id, classification
          )
        );

        CREATE FUNCTION catalog.guard_draft_delete_publication_race()
        RETURNS trigger
        LANGUAGE plpgsql
        SET search_path = pg_catalog, catalog
        AS $$
        DECLARE
          identity_table text;
          target_exists boolean;
        BEGIN
          identity_table := CASE NEW.aggregate_type
            WHEN 'catalog.database' THEN 'database'
            WHEN 'catalog.profile' THEN 'profile'
            WHEN 'catalog.configurable_table' THEN 'schema_table'
            WHEN 'catalog.attribute_definition' THEN 'attribute_definition'
            WHEN 'catalog.layout' THEN 'layout'
            WHEN 'catalog.subset' THEN 'subset'
            WHEN 'catalog.link_type' THEN 'link_type'
            ELSE NULL
          END;
          IF identity_table IS NULL THEN
            RETURN NEW;
          END IF;
          EXECUTE format(
            'SELECT true FROM catalog.%I WHERE organization_id = $1 AND project_id = $2 '
            'AND classification = $3 AND id = $4 AND current_revision_id = $5 FOR KEY SHARE',
            identity_table
          ) INTO target_exists USING
            NEW.organization_id, NEW.project_id, NEW.classification,
            NEW.aggregate_id, NEW.revision_id;
          IF target_exists IS DISTINCT FROM true THEN
            RAISE EXCEPTION USING
              ERRCODE = '23503',
              MESSAGE = 'publication target catalog draft no longer exists';
          END IF;
          RETURN NEW;
        END
        $$;
        CREATE TRIGGER catalog_publication_marker_draft_delete_guard
          BEFORE INSERT ON catalog.publication_marker
          FOR EACH ROW EXECUTE FUNCTION catalog.guard_draft_delete_publication_race();
        """
    )

    op.execute(
        """
        CREATE FUNCTION catalog.delete_unpublished_r1_draft(
          p_aggregate_type text,
          p_aggregate_id uuid,
          p_expected_revision_id uuid
        ) RETURNS text
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = pg_catalog, catalog, access_control
        AS $$
        DECLARE
          identity_table text;
          revision_table text;
          row_organization_id uuid;
          row_project_id uuid;
          row_classification text;
          row_revision_id uuid;
          row_revision_no bigint;
        BEGIN
          identity_table := CASE p_aggregate_type
            WHEN 'catalog.database' THEN 'database'
            WHEN 'catalog.profile' THEN 'profile'
            WHEN 'catalog.configurable_table' THEN 'schema_table'
            WHEN 'catalog.attribute_definition' THEN 'attribute_definition'
            WHEN 'catalog.layout' THEN 'layout'
            WHEN 'catalog.subset' THEN 'subset'
            WHEN 'catalog.link_type' THEN 'link_type'
            ELSE NULL
          END;
          IF identity_table IS NULL THEN
            RETURN 'unsupported';
          END IF;
          revision_table := identity_table || '_revision';

          EXECUTE format(
            'SELECT organization_id, project_id, classification, current_revision_id '
            'FROM catalog.%I WHERE id = $1 FOR UPDATE', identity_table
          ) INTO row_organization_id, row_project_id, row_classification, row_revision_id
          USING p_aggregate_id;
          IF row_revision_id IS NULL THEN
            RETURN 'not_found';
          END IF;
          IF row_organization_id IS DISTINCT FROM
               NULLIF(current_setting('cmp.organization_id', true), '')::uuid
             OR row_project_id IS DISTINCT FROM
               NULLIF(current_setting('cmp.project_id', true), '')::uuid
             OR NOT access_control.can_access_row(
               row_organization_id, row_project_id, row_classification, 'catalog.write'
             ) THEN
            RETURN 'not_found';
          END IF;
          IF row_revision_id IS DISTINCT FROM p_expected_revision_id THEN
            RETURN 'stale';
          END IF;

          EXECUTE format(
            'SELECT revision_no FROM catalog.%I WHERE organization_id = $1 AND project_id = $2 '
            'AND classification = $3 AND aggregate_id = $4 AND id = $5', revision_table
          ) INTO row_revision_no USING
            row_organization_id, row_project_id, row_classification,
            p_aggregate_id, p_expected_revision_id;
          IF row_revision_no IS NULL THEN
            RETURN 'not_found';
          END IF;
          IF row_revision_no <> 1 THEN
            RETURN 'revised';
          END IF;
          IF EXISTS (
            SELECT 1 FROM catalog.publication_marker marker
             WHERE marker.organization_id = row_organization_id
               AND marker.project_id = row_project_id
               AND marker.aggregate_type = p_aggregate_type
               AND marker.aggregate_id = p_aggregate_id
          ) THEN
            RETURN 'published';
          END IF;

          BEGIN
            INSERT INTO catalog.draft_delete_authorization
              (backend_pid, transaction_id, table_name, aggregate_id,
               organization_id, project_id, classification)
            VALUES
              (pg_backend_pid(), txid_current(), identity_table, p_aggregate_id,
               row_organization_id, row_project_id, row_classification),
              (pg_backend_pid(), txid_current(), revision_table, p_aggregate_id,
               row_organization_id, row_project_id, row_classification);
            IF identity_table = 'layout' THEN
              INSERT INTO catalog.draft_delete_authorization
                (backend_pid, transaction_id, table_name, aggregate_id,
                 organization_id, project_id, classification)
              VALUES
                (pg_backend_pid(), txid_current(), 'layout_item', p_aggregate_id,
                 row_organization_id, row_project_id, row_classification);
              DELETE FROM catalog.layout_item
               WHERE organization_id = row_organization_id
                 AND project_id = row_project_id
                 AND classification = row_classification
                 AND layout_id = p_aggregate_id;
            END IF;

            EXECUTE format(
              'DELETE FROM catalog.%I WHERE organization_id = $1 AND project_id = $2 '
              'AND classification = $3 AND id = $4', identity_table
            ) USING row_organization_id, row_project_id, row_classification, p_aggregate_id;
            EXECUTE format(
              'DELETE FROM catalog.%I WHERE organization_id = $1 AND project_id = $2 '
              'AND classification = $3 AND aggregate_id = $4 AND id = $5', revision_table
            ) USING row_organization_id, row_project_id, row_classification,
                    p_aggregate_id, p_expected_revision_id;
            DELETE FROM catalog.draft_delete_authorization
             WHERE backend_pid = pg_backend_pid()
               AND transaction_id = txid_current()
               AND aggregate_id = p_aggregate_id;
          EXCEPTION WHEN foreign_key_violation THEN
            RETURN 'referenced';
          END;
          RETURN 'deleted';
        END
        $$;
        REVOKE ALL ON FUNCTION catalog.delete_unpublished_r1_draft(text, uuid, uuid) FROM PUBLIC;
        GRANT EXECUTE ON FUNCTION catalog.delete_unpublished_r1_draft(text, uuid, uuid) TO PUBLIC;
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER catalog_publication_marker_draft_delete_guard ON catalog.publication_marker"
    )
    op.execute("DROP FUNCTION catalog.guard_draft_delete_publication_race()")
    op.execute("DROP FUNCTION catalog.delete_unpublished_r1_draft(text, uuid, uuid)")
    op.execute("DROP POLICY catalog_layout_item_draft_delete ON catalog.layout_item")
    op.execute("DROP TRIGGER catalog_layout_item_immutable ON catalog.layout_item")
    op.execute(
        "CREATE TRIGGER catalog_layout_item_immutable BEFORE UPDATE OR DELETE "
        "ON catalog.layout_item FOR EACH ROW "
        "EXECUTE FUNCTION revisioning.reject_immutable_row_mutation()"
    )
    for table, _aggregate_type in reversed(_IDENTITIES):
        op.execute(f"DROP POLICY catalog_{table}_draft_delete ON catalog.{table}")
        op.execute(
            f"DROP POLICY catalog_{table}_revision_draft_delete ON catalog.{table}_revision"
        )
        op.execute(f"DROP TRIGGER catalog_{table}_head_only ON catalog.{table}")
        op.execute(
            f"CREATE TRIGGER catalog_{table}_head_only BEFORE UPDATE OR DELETE "
            f"ON catalog.{table} FOR EACH ROW "
            "EXECUTE FUNCTION revisioning.guard_identity_head_update()"
        )
        op.execute(
            f"DROP TRIGGER catalog_{table}_revision_immutable ON catalog.{table}_revision"
        )
        op.execute(
            f"CREATE TRIGGER catalog_{table}_revision_immutable BEFORE UPDATE OR DELETE "
            f"ON catalog.{table}_revision FOR EACH ROW "
            "EXECUTE FUNCTION revisioning.reject_immutable_row_mutation()"
        )
    op.execute("DROP FUNCTION catalog.guard_configurable_immutable_mutation()")
    op.execute("DROP FUNCTION catalog.guard_configurable_identity_mutation()")
    op.execute("DROP FUNCTION catalog.is_draft_delete_authorized(text, uuid, uuid, uuid, text)")
    op.execute("DROP TABLE catalog.draft_delete_authorization")
    for table, _aggregate_type in reversed(_IDENTITIES):
        _replace_identity_revision_cycle(table, on_delete="RESTRICT")

-- Test-only explicit typed consumer of the T-06 kernel. Never install in production.
-- The content columns are deliberately concrete; there is no JSON/EAV payload.

CREATE SCHEMA kernel_fixture;

CREATE TABLE kernel_fixture.revisioned_note (
    id uuid NOT NULL,
    organization_id uuid NOT NULL,
    project_id uuid NOT NULL,
    classification varchar(64) NOT NULL,
    current_revision_id uuid NOT NULL,
    created_at timestamptz NOT NULL,
    created_by uuid NOT NULL,
    updated_at timestamptz NOT NULL,
    CONSTRAINT pk_revisioned_note PRIMARY KEY (organization_id, project_id, id),
    CONSTRAINT ck_revisioned_note_classification
      CHECK (classification ~ '^[a-z][a-z0-9_.-]{0,63}$')
);

CREATE TABLE kernel_fixture.revisioned_note_revision (
    id uuid NOT NULL,
    aggregate_id uuid NOT NULL,
    organization_id uuid NOT NULL,
    project_id uuid NOT NULL,
    classification varchar(64) NOT NULL,
    revision_no bigint NOT NULL,
    based_on_revision_id uuid NULL,
    schema_id varchar(255) NOT NULL,
    schema_version varchar(64) NOT NULL,
    content_hash char(64) NOT NULL,
    created_at timestamptz NOT NULL,
    created_by uuid NOT NULL,
    change_reason text NOT NULL,
    request_id uuid NOT NULL,
    trace_id varchar(255) NOT NULL,
    title varchar(200) NOT NULL,
    body text NOT NULL,
    pinned boolean NOT NULL,
    CONSTRAINT pk_revisioned_note_revision
      PRIMARY KEY (organization_id, project_id, id),
    CONSTRAINT uq_revisioned_note_revision_scope_id
      UNIQUE (organization_id, project_id, aggregate_id, id),
    CONSTRAINT uq_revisioned_note_revision_number
      UNIQUE (organization_id, project_id, aggregate_id, revision_no),
    CONSTRAINT fk_revisioned_note_revision_identity
      FOREIGN KEY (organization_id, project_id, aggregate_id)
      REFERENCES kernel_fixture.revisioned_note (organization_id, project_id, id)
      DEFERRABLE INITIALLY DEFERRED,
    CONSTRAINT fk_revisioned_note_revision_base
      FOREIGN KEY (organization_id, project_id, aggregate_id, based_on_revision_id)
      REFERENCES kernel_fixture.revisioned_note_revision
        (organization_id, project_id, aggregate_id, id)
      DEFERRABLE INITIALLY DEFERRED,
    CONSTRAINT ck_revisioned_note_revision_number CHECK (revision_no > 0),
    CONSTRAINT ck_revisioned_note_revision_base CHECK (
      (revision_no = 1 AND based_on_revision_id IS NULL)
      OR (revision_no > 1 AND based_on_revision_id IS NOT NULL)
    ),
    CONSTRAINT ck_revisioned_note_revision_hash
      CHECK (content_hash ~ '^[0-9a-f]{64}$'),
    CONSTRAINT ck_revisioned_note_revision_reason CHECK (length(btrim(change_reason)) > 0),
    CONSTRAINT ck_revisioned_note_revision_title CHECK (length(btrim(title)) > 0),
    CONSTRAINT ck_revisioned_note_revision_classification
      CHECK (classification ~ '^[a-z][a-z0-9_.-]{0,63}$')
);

ALTER TABLE kernel_fixture.revisioned_note
  ADD CONSTRAINT fk_revisioned_note_current_revision
  FOREIGN KEY (organization_id, project_id, id, current_revision_id)
  REFERENCES kernel_fixture.revisioned_note_revision
    (organization_id, project_id, aggregate_id, id)
  DEFERRABLE INITIALLY DEFERRED;

CREATE INDEX ix_revisioned_note_tenant_head
  ON kernel_fixture.revisioned_note (organization_id, project_id, current_revision_id);

CREATE INDEX ix_revisioned_note_revision_tenant_created
  ON kernel_fixture.revisioned_note_revision
    (organization_id, project_id, aggregate_id, created_at);

CREATE TRIGGER revisioned_note_head_only
BEFORE UPDATE OR DELETE ON kernel_fixture.revisioned_note
FOR EACH ROW EXECUTE FUNCTION revisioning.guard_identity_head_update();

CREATE TRIGGER revisioned_note_revision_immutable
BEFORE UPDATE OR DELETE ON kernel_fixture.revisioned_note_revision
FOR EACH ROW EXECUTE FUNCTION revisioning.reject_immutable_row_mutation();

ALTER TABLE kernel_fixture.revisioned_note ENABLE ROW LEVEL SECURITY;
ALTER TABLE kernel_fixture.revisioned_note FORCE ROW LEVEL SECURITY;
CREATE POLICY revisioned_note_authorized_select
ON kernel_fixture.revisioned_note
FOR SELECT
USING (
  access_control.can_access_row(
    organization_id, project_id, classification, 'revision.read'
  )
);
CREATE POLICY revisioned_note_authorized_insert
ON kernel_fixture.revisioned_note
FOR INSERT
WITH CHECK (
  access_control.can_access_row(
    organization_id, project_id, classification, 'revision.write'
  )
);
CREATE POLICY revisioned_note_authorized_update
ON kernel_fixture.revisioned_note
FOR UPDATE
USING (
  access_control.can_access_row(
    organization_id, project_id, classification, 'revision.write'
  )
)
WITH CHECK (
  access_control.can_access_row(
    organization_id, project_id, classification, 'revision.write'
  )
);

ALTER TABLE kernel_fixture.revisioned_note_revision ENABLE ROW LEVEL SECURITY;
ALTER TABLE kernel_fixture.revisioned_note_revision FORCE ROW LEVEL SECURITY;
CREATE POLICY revisioned_note_revision_authorized_select
ON kernel_fixture.revisioned_note_revision
FOR SELECT
USING (
  access_control.can_access_row(
    organization_id, project_id, classification, 'revision.read'
  )
);
CREATE POLICY revisioned_note_revision_authorized_insert
ON kernel_fixture.revisioned_note_revision
FOR INSERT
WITH CHECK (
  access_control.can_access_row(
    organization_id, project_id, classification, 'revision.write'
  )
);

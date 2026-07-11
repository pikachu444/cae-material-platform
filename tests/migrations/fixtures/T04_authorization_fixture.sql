-- Test-only tenant/classification fixture for T-04. Never install in production.

CREATE SCHEMA authorization_fixture;

CREATE TABLE authorization_fixture.protected_document (
    id uuid NOT NULL,
    organization_id uuid NOT NULL,
    project_id uuid NOT NULL,
    classification varchar(64) NOT NULL,
    title varchar(200) NOT NULL,
    CONSTRAINT pk_protected_document
      PRIMARY KEY (organization_id, project_id, id),
    CONSTRAINT uq_protected_document_classified_ref
      UNIQUE (organization_id, project_id, classification, id),
    CONSTRAINT ck_protected_document_classification
      CHECK (classification IN ('internal', 'confidential', 'restricted', 'export_controlled')),
    CONSTRAINT ck_protected_document_title
      CHECK (length(btrim(title)) BETWEEN 1 AND 200)
);

CREATE INDEX ix_protected_document_tenant_classification
  ON authorization_fixture.protected_document
    (organization_id, project_id, classification, title);

CREATE TABLE authorization_fixture.document_ref (
    id uuid NOT NULL,
    organization_id uuid NOT NULL,
    project_id uuid NOT NULL,
    classification varchar(64) NOT NULL,
    document_id uuid NOT NULL,
    label varchar(200) NOT NULL,
    CONSTRAINT pk_document_ref
      PRIMARY KEY (organization_id, project_id, id),
    CONSTRAINT fk_document_ref_document
      FOREIGN KEY (organization_id, project_id, classification, document_id)
      REFERENCES authorization_fixture.protected_document
        (organization_id, project_id, classification, id)
      ON DELETE RESTRICT,
    CONSTRAINT ck_document_ref_classification
      CHECK (classification IN ('internal', 'confidential', 'restricted', 'export_controlled')),
    CONSTRAINT ck_document_ref_label
      CHECK (length(btrim(label)) BETWEEN 1 AND 200)
);

CREATE INDEX ix_document_ref_tenant_document
  ON authorization_fixture.document_ref
    (organization_id, project_id, document_id);

ALTER TABLE authorization_fixture.protected_document ENABLE ROW LEVEL SECURITY;
ALTER TABLE authorization_fixture.protected_document FORCE ROW LEVEL SECURITY;
CREATE POLICY protected_document_select
ON authorization_fixture.protected_document
FOR SELECT
USING (
  access_control.can_access_row(
    organization_id, project_id, classification, 'dataset.read'
  )
);
CREATE POLICY protected_document_insert
ON authorization_fixture.protected_document
FOR INSERT
WITH CHECK (
  access_control.can_access_row(
    organization_id, project_id, classification, 'dataset.write'
  )
);
CREATE POLICY protected_document_update
ON authorization_fixture.protected_document
FOR UPDATE
USING (
  access_control.can_access_row(
    organization_id, project_id, classification, 'dataset.write'
  )
)
WITH CHECK (
  access_control.can_access_row(
    organization_id, project_id, classification, 'dataset.write'
  )
);
CREATE POLICY protected_document_delete
ON authorization_fixture.protected_document
FOR DELETE
USING (
  access_control.can_access_row(
    organization_id, project_id, classification, 'dataset.write'
  )
);

ALTER TABLE authorization_fixture.document_ref ENABLE ROW LEVEL SECURITY;
ALTER TABLE authorization_fixture.document_ref FORCE ROW LEVEL SECURITY;
CREATE POLICY document_ref_select
ON authorization_fixture.document_ref
FOR SELECT
USING (
  access_control.can_access_row(
    organization_id, project_id, classification, 'dataset.read'
  )
);
CREATE POLICY document_ref_insert
ON authorization_fixture.document_ref
FOR INSERT
WITH CHECK (
  access_control.can_access_row(
    organization_id, project_id, classification, 'dataset.write'
  )
);
CREATE POLICY document_ref_update
ON authorization_fixture.document_ref
FOR UPDATE
USING (
  access_control.can_access_row(
    organization_id, project_id, classification, 'dataset.write'
  )
)
WITH CHECK (
  access_control.can_access_row(
    organization_id, project_id, classification, 'dataset.write'
  )
);
CREATE POLICY document_ref_delete
ON authorization_fixture.document_ref
FOR DELETE
USING (
  access_control.can_access_row(
    organization_id, project_id, classification, 'dataset.write'
  )
);

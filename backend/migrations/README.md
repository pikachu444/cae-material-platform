# Database migrations

The Alembic chain starts with `20260711_001_T06_revision_kernel.py`, followed by the T-03 identity
projection and T-04 access-control migrations.

## T-06 ownership

The migration creates:

- `revisioning.current_organization_id()` and `current_project_id()` RLS helpers;
- append-only/delete/head-only trigger functions used by future explicit typed tables;
- `governance.lifecycle_event`, an append-only lifecycle history;
- `governance.lifecycle_projection`, the mutable current-state projection;
- tenant-first constraints, foreign keys, indexes, forced RLS, and default-deny policies.

It deliberately does **not** create a central aggregate/revision/content table. Each bounded module
must create an explicit identity table and an explicit typed revision table in its owned schema.
JSONB is reserved for schema-validated plugin extension payloads, not core attributes.

## T-03 ownership

The second migration creates the `identity` schema with explicit relational tables:

- `identity.principal`: opaque stable UUID, `user|service` type, mutable display projection and
  active flag;
- `identity.external_identity`: immutable issuer/subject binding to a principal and monotonic
  last-seen timestamp;
- unique `(issuer, subject)`, principal lookup/type indexes, foreign keys, checks, and database
  triggers that reject key replacement or deletion.

These tables are deployment-level identity projections, not tenant-owned business rows. They do
not contain organization/project authorization or RLS policy. A validated token supplies the
selected request context, while T-04 owns organization/project membership, role bindings, ABAC,
and database session RLS enforcement. JIT provisioning is off by default; when enabled, the
adapter serializes the same external identity with a PostgreSQL transaction advisory lock and
creates random UUIDv4 identifiers.

## T-04 ownership

`20260711_003_T04_authorization_rls.py` adds:

- explicit `identity.role_binding` columns for principal or exact-issuer group subjects, org-wide
  or project scope, role, standard clearance, export compartment, validity, creator/reason, and
  atomic revocation;
- immutable-grant/delete guards, tenant/subject indexes, constrained role/classification values,
  and `FORCE ROW LEVEL SECURITY`;
- `access_control` functions for transaction-local principal/group/permission/clearance context,
  non-bypass application-role assertion, and classification-aware row checks;
- separate read/write policies on governance lifecycle tables, replacing the T-06 tenant-only
  policy while retaining fail-closed organization/project isolation.

The migration deliberately does not create a cluster-global application role because role names,
login secrets, and ownership belong to deployment provisioning. The runtime role must be a
non-owner `NOSUPERUSER NOBYPASSRLS` role with explicit schema/table grants. Migration, backup, and
reconciliation use separate privileged roles.

The executable test-only example is
`tests/migrations/fixtures/T06_typed_revision_fixture.sql`. It demonstrates:

- tenant-scoped composite foreign keys from revision to identity, base revision, and head;
- `revision_no` uniqueness per stable aggregate;
- concrete typed columns (`title`, `body`, `pinned`) instead of EAV/JSON content;
- a deferrable current-head foreign key so identity and first revision commit atomically;
- immutable revision and head-only identity triggers;
- organization/project forced RLS and tenant-first indexes.

## Commands

```bash
CMP_DATABASE_URL=postgresql+psycopg://... make migrate
CMP_TEST_POSTGRES_DSN=postgresql+psycopg://... make test-postgresql
```

`CMP_TEST_POSTGRES_DSN` must identify an isolated admin database. The test creates a uniquely named
temporary database, upgrades it, installs the T-04 authorization and T-06 typed fixtures, exercises
T-03/T-04/T-06 persistence, downgrades it, and removes it.


# Database migrations

The Alembic chain starts with `20260711_001_T06_revision_kernel.py`.

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
temporary database, upgrades it, installs the test-only typed fixture, tests it, downgrades it, and
removes it.


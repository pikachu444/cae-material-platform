# Database migrations

The linear Alembic chain is T-06 revision primitives, T-03 identity projection, T-04 access
control, T-15 durable jobs, T-17 plugin registry, T-09 streaming upload, T-10 immutable Artifact
storage, T-13 typed provenance, T-14 lineage read models, and T-16 transactional events. Task
numbers express delivery ownership, not migration chronology; every revision has one explicit
predecessor.

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

## T-09 ownership

`20260712_006_T09_streaming_upload.py` creates the bounded `artifact` schema with explicit tables:

- `artifact.upload_session`: immutable upload request/manifest identity plus a guarded operational
  state projection;
- `artifact.upload_part`: append-only numbered part digest, size, and object-store ETag facts;
- `artifact.raw_asset`: immutable content identity for a digest/size-verified staging object;
- `artifact.ingestion_event`: append-only actor/request/test-run context for each completed upload,
  including duplicate ingestion of an existing Raw Asset.

Tenant-first primary/foreign keys, classification-bearing references, digest/idempotency/storage
uniqueness, state/manifest checks, insert guards, immutable-row triggers, and targeted indexes are
created explicitly. All four tables use forced RLS and separate `artifact.read`/`artifact.write`
policies. There is no generic Artifact/EAV/JSON content table. `test_run_revision_id` is recorded as
an opaque non-zero UUID until T-08 creates its owning table and adds the tenant-qualified foreign
key. T-09 stops at `staged_verified`; T-10 links that immutable source to a separate final Artifact.

## T-10 ownership

`20260712_007_T10_content_artifacts.py` extends the bounded `artifact` schema with:

- `artifact.artifact_pending`: immutable staging/final manifest plus guarded promotion projection;
- `artifact.artifact`: immutable available content manifest linked to its pending record and,
  for raw content, the unchanged T-09 Raw Asset;
- `artifact.integrity_observation`: append-only expected/observed digest and size checks;
- `artifact.integrity_projection`: mutable current status backed by an immutable observation;
- `artifact.reconciliation_issue`: append-only orphan and pending-object mismatch facts;
- `artifact.content_object_key(...)`: deterministic
  organization/project/classification/SHA-256 key derivation enforced by DB checks.

The migration enforces no-overwrite metadata semantics, terminal pending immutability, exact
pending-to-Artifact insertion, observation/projection consistency, tenant-first composite FKs and
indexes, and forced classification-aware RLS. Artifact manifests have explicit columns and no
JSON/EAV payload. Internal object keys are persistence details and are excluded from public API
schemas. T-16 remains responsible for durable reconciliation scheduling, outbox delivery, and
retention cleanup; production object versioning/replication is deployment provisioning.

## T-13 ownership

`20260713_008_T13_typed_provenance.py` creates the bounded `provenance` schema with explicit
`entity`, `activity`, `agent`, `usage`, `generation`, `derivation`, `association`, `revision`, and
`attribution` relations. Every relation repeats organization/project/classification and uses
tenant-qualified composite foreign keys. Core relation metadata is typed columns only; there is no
JSONB, EAV key/value table, or unrestricted edge table.

Deferred constraint triggers require primary generation for generated Entity records and enforce
declared Activity input/output plus a responsible Agent before commit. Insert guards validate
Raw Asset/Artifact snapshots, principal/plugin Agent references, usage-generation/derivation/
revision cycles, revision type consistency, and plan usage. Every table is append-only and uses
forced classification-aware RLS with separate internal `provenance.write` and public
`provenance.read` capabilities. T-14 owns recursive lineage/impact read models and performance
limits; T-13 creates only the authoritative typed source relations and entity lookup.

## T-14 ownership

`20260713_009_T14_lineage_read_model.py` adds three security-invoker/security-barrier views over
the T-13 typed relations:

- `provenance.dependency_edge`: the fixed `derivation`, `usage_generation`, and `revision`
  relation families used by bounded traversal;
- `provenance.entity_completeness`: primary-generation status for immutable Entity records;
- `provenance.activity_completeness`: declared input, responsible Agent, and output status.

The views add no stored generic edge, EAV payload, closure table, or mutable projection. Their
underlying tables retain forced organization/project/classification RLS. The repository performs
bounded recursive discovery separately from typed Entity materialization, caps depth at 20 and
nodes at 10,000, then exposes pages of at most 1,000 nodes. T-30 remains responsible for Release
tables and release-specific evidence/review/mapping policy.

## T-16 phase 1 ownership

`20260713_010_T16_transactional_outbox.py` creates the `events` schema with explicit
`outbox_event`, `outbox_delivery`, and `consumer_inbox` relations. The immutable event stores a
CloudEvents 1.0 envelope projection, schema-identified JSON object data, canonical data digest,
tenant/classification scope, aggregate sequence, producer deduplication key, actor/request/trace,
and occurrence/recording times. JSONB is limited to this named versioned event data contract and is
not an EAV business store.

Delivery state is a separate guarded lease projection with fencing token, expiry, monotonic attempt
count, retry availability, terminal published/poison state, and a claim index. Inbox receipts are
immutable and unique by tenant, consumer, and event ID so a consumer can record the receipt in the
same transaction as its side effect. All three tables use forced RLS with internal
`events.publish`, `events.dispatch`, and `events.consume` capabilities. T-16 phase 2 owns durable
Artifact reconciliation scheduling and safe staging cleanup; no final object deletion is implied.

`20260713_011_T16_reconciliation_schedule.py` completes the task with explicit
`artifact.reconciliation_schedule`, `reconciliation_run`, and `staging_cleanup` relations. A
schedule has one fenced lease/current run; expired leases terminalize the abandoned run as
`timed_out` before a fresh run is appended. Successful/failed/timed-out run history becomes
immutable. Cleanup receipts have a classified composite FK to a terminal pending Artifact and a
run, and the application selects only old terminal staging keys that differ from the final key.
The migration contains no object-delete SQL and no final Artifact cleanup relation.

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

`CMP_TEST_POSTGRES_DSN` must identify an isolated admin database. PostgreSQL-gated suites create
uniquely named temporary databases and non-bypass application roles, upgrade to the requested
revision, exercise RLS and persistence against the real schema, downgrade, and remove them.


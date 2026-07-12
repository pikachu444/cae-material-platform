# CAE Material Platform

Status: identity, authorization, revision, streaming Raw Asset upload, immutable content Artifact,
typed provenance and bounded lineage, durable job, plugin registry, and isolated runner foundation
(`T-01`–`T-04` + `T-06` + `T-09`–`T-10` + `T-13`–`T-15` + `T-17` + `T-18`)

Version: `0.11.0`

This repository is the implementation workspace for the CAE material-data platform defined in
`docs/`. The current scope deliberately contains no material, test, fitting, or solver-card
business implementation. Database support is limited to the T-03/T-04 identity and access-control
foundation, the domain-neutral T-06 revision kernel, the generic T-15 Job/Attempt/Lease engine,
the T-17 immutable plugin package registry, and the T-18 isolated execution contract. T-18 adds no
Material, test, fitting, calibration, or solver business implementation. T-09 adds verified staging
Raw Assets, and T-10 promotes them into tenant-scoped content-addressed immutable Artifacts with
integrity observations and scoped streaming download.
T-13 adds domain-neutral typed Entity/Activity/Agent relations and fail-closed completeness without
creating any Material, Dataset, Test, fitting, or solver implementation.
T-14 adds bounded bidirectional lineage, impact pagination, and a generic Entity-root provenance
completeness gate. Release creation and release-specific evidence policy remain owned by T-30.

## Implemented foundation

- Modular-monolith Python package and bounded-module namespaces
- FastAPI `GET /api/v1/health` endpoint
- Generic durable worker with claim/start/heartbeat/cancel/finalize ports and an idle smoke mode
- Architecture dependency checker
- OpenAPI 3.1 and AsyncAPI baseline contracts
- JSON Schema baselines for jobs, plugin packages, and Material Model IR envelope
- Contract linter and minimal generated health client
- Unit, architecture, contract, and live-process integration tests
- Framework-free canonical hashing and typed aggregate revision application service
- SQLAlchemy adapter for explicit stable-identity/typed-revision table pairs
- Alembic/PostgreSQL immutability guards, tenant RLS helpers, and lifecycle projection
- Strong revision ETag and common content-free revision metadata contracts
- Strict OIDC JWT access-token validation for user and service principals
- Immutable `(issuer, subject)` external identities and stable opaque principal IDs
- Request-scoped organization/project context and authenticated `GET /api/v1/me`
- Conservative deny-by-default RBAC matrix and principal/IdP-group role bindings
- Transaction-local permission/classification context with forced PostgreSQL RLS
- Reusable service/API authorization decisions and append/revoke role administration
- Stable Job identities separated from immutable per-execution Attempt/Job Spec records
- PostgreSQL atomic claim (`FOR UPDATE SKIP LOCKED`), lease fencing, crash recovery, and retry policy
- Explicit runner capability/resource tables, per-runner concurrency, and tenant/classification RLS
- Idempotent Job submission/finalization and append-only retry attempts
- Protected `POST /api/v1/jobs`, `GET /api/v1/jobs/{id}`, `:cancel`, and `:retry` resources
- Stable project-scoped Plugin Definitions separated from immutable version/digest Packages
- Explicit extension, capability, JSON Schema, artifact-role, state-event, and activation tables
- Manifest 1.0 and JSON Schema 2020-12 validation without importing plugin implementations
- Signed-package, signature, and SBOM artifact UUID/digest snapshots; production registry admission
  still requires authoritative T-10 Artifact resolution in the deployment composition
- Plugin Maintainer registration separated from Org Admin verification/activation/revocation
- Forced PostgreSQL RLS, append-only package history, project activation, and fail-closed guards
- Protected plugin package register/read/verify/activate/revoke API resources
- Framework-free Python plugin SDK with typed Job Spec views, scoped input reads, bounded output
  writes, cooperative cancellation/deadlines, deterministic RNG, and structured diagnostics
- Non-production subprocess runner with package/input/output rehashing, safe ZIP extraction,
  path/link/process/network guards, bounded diagnostics, timeout, and cancellation enforcement
- OCI-runtime-neutral production execution plan that fails closed unless every required sandbox
  capability is attested; no Docker/Kubernetes/vendor dependency is embedded in core
- Compatibility test kit and synthetic contract-echo package covering all seven extension types
  without implementing domain, material, test, fitting, or solver behavior
- Tenant-scoped active-package resolution, durable worker result mapping, and explicit T-10
  materialization/commit ports; core never imports a plugin implementation
- Resumable upload sessions with immutable numbered part manifests, exact SHA-256/size/MIME policy,
  environment-bounded streaming, cancellation, and idempotent completion
- HMAC upload capabilities scoped to session, organization, project, actor, and expiry; internal
  object keys never appear in public API responses
- Explicit PostgreSQL `artifact.upload_session`, `upload_part`, `raw_asset`, and
  `ingestion_event` tables with tenant composite keys, forced RLS, append-only guards, and dedup
- Non-production filesystem multipart adapter for integration and development; production
  S3-compatible TLS/encryption/object-lock adapter selection remains a deployment boundary
- Deterministic organization/project/classification-scoped SHA-256 final keys with no-overwrite
  staging promotion, idempotent retry, and immutable Artifact manifests
- Explicit PostgreSQL `artifact_pending`, `artifact`, `integrity_observation`,
  `integrity_projection`, and `reconciliation_issue` relations with guarded state and forced RLS
- Reconciliation of object-success/DB-gap, missing, corrupt, orphan, and missing-staging fixtures
  without rewriting Raw Assets or Artifact manifests
- Actor/tenant/content/expiry-bound HMAC transfer grants and protected streaming content API;
  internal staging/final object keys are absent from all public contracts
- Explicit PostgreSQL provenance Entity/Activity/Agent plus usage, generation, derivation,
  association, revision, and attribution relations without JSONB/EAV or unrestricted graph edges
- Deferred primary-generation/Activity completeness, duplicate-generation and DAG cycle guards,
  append-only triggers, tenant/classification composite FKs, and forced RLS
- Owner-module immutable reference resolver, atomic terminal Activity write service, idempotent
  domain-run replay, and a T-06 revision transaction hook
- Protected immutable Entity lookup plus bounded upstream/downstream lineage, downstream impact,
  opaque cursor pagination, and fail-closed provenance completeness APIs
- PostgreSQL security-invoker typed read models and depth/node limits with 10-hop/10,000-edge
  performance and organization/project/classification isolation fixtures

## Prerequisites

- Python 3.12+
- `uv`
- `make`
- PostgreSQL 16+ for migration and persistence integration tests

## Start

```bash
make bootstrap
make test
make run-api
```

In another terminal:

```bash
curl http://127.0.0.1:8000/api/v1/health
make run-worker-once
```

`GET /api/v1/health` is public. `GET /api/v1/me` fails closed with `503` until all required OIDC
settings and the database URL are configured. Apply the migration first, then set:

```bash
export CMP_DATABASE_URL=postgresql+psycopg://...
export CMP_OIDC_ISSUER=https://idp.example.com/
export CMP_OIDC_AUDIENCE=urn:cmp:api
export CMP_OIDC_JWKS_URL=https://idp.example.com/.well-known/jwks.json
export CMP_OIDC_AUTO_PROVISION=true  # optional; false by default
make run-api
curl -H "Authorization: Bearer ${ACCESS_TOKEN}" http://127.0.0.1:8000/api/v1/me
```

The optional claim mapping settings are `CMP_OIDC_CLIENT_ID_CLAIM`,
`CMP_OIDC_ORGANIZATION_CLAIM`, `CMP_OIDC_PROJECT_CLAIM`, `CMP_OIDC_GROUPS_CLAIM`,
`CMP_OIDC_DISPLAY_NAME_CLAIM`, `CMP_OIDC_SERVICE_GRANT_CLAIM`, and
`CMP_OIDC_SERVICE_GRANT_VALUES`. `CMP_OIDC_ALGORITHMS` is an explicit asymmetric allowlist.
Loopback HTTP JWKS is disabled unless `CMP_OIDC_ALLOW_LOOPBACK_HTTP=true` is set for development.

The T-09/T-10 filesystem adapter is enabled only outside production. Upload and download
capability secrets are separate, must contain at least 32 bytes, and should come from a secret
manager rather than source control:

```bash
export CMP_UPLOAD_STORAGE_ROOT=/var/lib/cmp-upload-staging
export CMP_UPLOAD_CAPABILITY_SECRET='replace-with-a-secret-manager-value'
export CMP_ARTIFACT_TRANSFER_SECRET='replace-with-a-different-secret-manager-value'
export CMP_ARTIFACT_TRANSFER_TTL_SECONDS=300
export CMP_UPLOAD_MAX_OBJECT_BYTES=2147483648
export CMP_UPLOAD_PART_BYTES=8388608
```

Run migrations with a separate owner role. Runtime OIDC configuration must use a non-owner
application role; startup rejects `SUPERUSER`, `BYPASSRLS`, or a role that owns application
relations. A minimal privilege baseline is:

```sql
CREATE ROLE cmp_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;
GRANT CONNECT ON DATABASE cmp TO cmp_app;
GRANT USAGE ON SCHEMA identity, revisioning, access_control, governance, jobs, plugin, artifact, provenance TO cmp_app;
GRANT SELECT, INSERT, UPDATE ON identity.principal, identity.external_identity TO cmp_app;
GRANT SELECT, INSERT, UPDATE ON identity.role_binding TO cmp_app;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA jobs TO cmp_app;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA plugin TO cmp_app;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA artifact TO cmp_app;
GRANT SELECT, INSERT ON ALL TABLES IN SCHEMA provenance TO cmp_app;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA access_control, revisioning, plugin, artifact, provenance TO cmp_app;
```

Future bounded-module migrations grant only the table operations their adapters require. Every
tenant-owned table must use `access_control.can_access_row(...)`, `ENABLE ROW LEVEL SECURITY`, and
`FORCE ROW LEVEL SECURITY`; granting SQL privileges alone never grants row access.

## Development commands

```bash
make lint
make typecheck
make check-architecture
make check-contracts
make test-unit
make test-contract
make test-migration
make test-integration
make test
make ci
```

Apply the production migration to an explicitly selected database:

```bash
CMP_DATABASE_URL=postgresql+psycopg://... make migrate
```

The PostgreSQL integration suite creates and removes its own temporary database. Point it only at
an isolated PostgreSQL admin database:

```bash
CMP_TEST_POSTGRES_DSN=postgresql+psycopg://... make test-postgresql
```

## Scope guard

Read `AGENTS.md` before changing this repository. Production tensile standards, material models,
calibration choices, solver cards, and validation criteria remain `TBD`. T-06 provides a typed-table
pattern and never a generic revision/EAV content store. Do not add business tables or
production-looking reference implementations before the corresponding decision gates. T-04 does
not implement Material, artifact transfer, audit chains, lifecycle approval, or export-control
nationality rules. T-15 accepts only versioned generic Job Spec documents; it does not implement
Material, test importer, fitting, solver exporter, production plugin, or general-purpose DAG logic.
T-17 registers manifest/schema/supply-chain references and project activation facts only. It does
not implement a public marketplace or claim cryptographic verification without an explicit
authorized verification event. T-18 executes only approved,
digest-pinned packages through Job Spec/Result Manifest. The local subprocess is explicitly
non-production; production requires an attested OCI runtime. T-10 provides authoritative Artifact
finalization, integrity reconciliation, and protected byte streaming, but production S3/credential
composition and T-18 package/input/output policy adapters remain deployment work, so an
unconfigured worker stays idle. T-09 Raw Asset facts remain immutable after T-10 promotion.
T-16 owns durable reconciliation scheduling, outbox delivery, and retention cleanup automation.
T-13 accepts only owner-attested immutable references and does not expose arbitrary graph writes.
T-14 provides bounded Entity-root traversal and provenance completeness only; it does not provide
arbitrary graph analytics or create a Release resource. T-30 owns release composition and the
release-specific evidence/mapping/review gate that consumes this generic report.

## Traceability

- Tasks: `T-01`, `T-02`, `T-03`, `T-04`, `T-06`, `T-09`, `T-10`, `T-13`, `T-14`, `T-15`, `T-17`, `T-18`
- Requirements: `FR-CAT-001`, `FR-DAT-001`, `FR-DAT-006`, `FR-API-001`, `NFR-INT-001`,
  `FR-API-002`, `FR-PLG-004`, `NFR-DR-002`, `NFR-PERF-006`, `NFR-SEC-001`,
  `NFR-SEC-002`, `NFR-SEC-003`, `NFR-SEC-006`, `NFR-AUD-001`, `NFR-MOD-001`,
  `FR-PLG-001`, `FR-PLG-002`, `FR-PLG-003`, `FR-PLG-005`, `FR-DAT-005`, `FR-DAT-007`,
  `FR-DAT-008`, `FR-WF-003`, `NFR-INT-001`,
  `NFR-INT-002`, `NFR-PERF-003`, `NFR-PERF-004`,
  `NFR-REP-001`, `NFR-REP-002`, `NFR-REP-003`, `NFR-SEC-004`, `NFR-SEC-005`, `NFR-MOD-002`,
  `NFR-COMP-001`, `NFR-COMP-002`, `NFR-DOC-001`
- Decisions: `ADR-001`, `ADR-002`, `ADR-003`, `ADR-004` (with `ADR-005` as a scope guard)


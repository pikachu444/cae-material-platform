# Implementation Status

Date: `2026-07-12`
Foundation version: `0.8.0`

## Completed

- `T-01`: modular-monolith repository skeleton, bounded-module namespaces, deployable API and
  worker shells, developer commands, architecture rules and regression fixtures
- `T-02`: OpenAPI/AsyncAPI baseline, JSON Schema registry, positive/negative contract examples,
  deterministic minimal client generation, compatibility detector and validation pipeline
- `T-03`: strict OIDC JWT access-token validation, user/service principal resolution, immutable
  external identity projection, request security context, `/api/v1/me`, and development test IdP
- `T-04`: conservative deny-by-default role matrix, principal/group role bindings, append/revoke
  administration, classification ABAC, reusable authorization dependency, and forced PostgreSQL RLS
- `T-06`: framework-free aggregate revision kernel, explicit typed-table SQLAlchemy adapter,
  PostgreSQL/Alembic immutability and tenant primitives, initial lifecycle event/projection,
  strong ETag and revision metadata contracts
- `T-09`: resumable streaming multipart sessions, HMAC actor/tenant/expiry capabilities,
  immutable part manifests, verified staging Raw Assets, append-only ingestion events, duplicate
  content detection, protected API, filesystem development adapter, and forced PostgreSQL RLS
- `T-15`: stable Job/immutable Attempt separation, versioned Job Spec digests, PostgreSQL atomic
  claim/lease/heartbeat/recovery, generic retry taxonomy, runner resources, protected Job API,
  and a handler-neutral durable worker
- `T-17`: stable Plugin Definition/immutable Package separation, Manifest 1.0 and JSON Schema
  validation, explicit capability/schema/supply-chain references, append-only verification and
  activation history, project-scoped allowlisting, protected API, and forced PostgreSQL RLS
- `T-18`: framework-free Python SDK, immutable Job Spec/Result Manifest execution service,
  reviewed-package subprocess runner, OCI-ready production plan and capability attestation,
  tenant-scoped active-package planning, durable worker bridge, and seven-extension TCK

## Runtime proof

- FastAPI health endpoint: `GET /api/v1/health`
- Unconfigured durable-worker idle verification: `cmp-worker --once --json`
- Generated client calls a live Uvicorn process in integration tests
- Worker starts in a separate subprocess and exits successfully in one-cycle mode
- OIDC validation uses exact issuer/audience, explicit asymmetric algorithms, configured JWKS,
  access-token type checking, required organization/project context, and sanitized failures
- PostgreSQL principal persistence keeps `(issuer, subject)` immutable, produces opaque UUIDv4 IDs,
  and serializes concurrent JIT provisioning without duplicate actors
- PostgreSQL authorization runs under a non-owner `NOSUPERUSER NOBYPASSRLS` role with
  transaction-local principal/tenant/permission/clearance context
- Classification-aware RLS filters list/count/facet operations and rejects cross-project or
  above-clearance writes; tenant composite FKs normalize hidden/unknown target failures
- Revision writes use concrete UUID bases, canonical SHA-256, transaction-local fail-closed hooks,
  and PostgreSQL compare-and-swap head advancement
- PostgreSQL integration uses a migration-managed explicit typed fixture; no generic EAV/content
  table exists
- Job submission is tenant-idempotent; every retry appends a distinct immutable Attempt/Job Spec
- PostgreSQL claim uses runner serialization and `FOR UPDATE SKIP LOCKED`; fencing tokens reject
  stale heartbeat/finalize calls after lease recovery
- Failure/cancel/timeout attempts remain queryable, terminal attempts and Job results are immutable,
  and identical finalize calls replay without a second commit
- Job/Attempt/Runner RLS uses the same request/service principal, tenant, permission, and
  classification context as API resources
- Plugin Maintainers can register but cannot self-verify or activate; Org Admin verification and
  activation commands use a separate permission and append actor/request/trace facts
- PostgreSQL rejects plugin ID/version digest substitution, package/history mutation, activation
  before eligibility, incomplete schema/capability bundles, revoked packages, and cross-project
  access even when opaque UUIDs are known
- Active package lookup is pinned to project, plugin ID, exact version, and package digest; revoked
  or cross-project packages are hidden before runner materialization
- The local T-18 runner rehashes package/input/output bytes, safely extracts bounded ZIP entries,
  rejects links and traversal, supplies only scoped SDK I/O, and enforces parent timeout/cancel
- Network, child-process, ambient-path, symlink, oversized-output, corrupt-package, and corrupt
  Result Manifest fixtures fail closed with sanitized diagnostics
- An OCI runtime must attest every production isolation control before receiving an execution plan;
  core contains no Docker, Kubernetes, vendor runtime, or plugin implementation dependency
- Identical seeds produce byte-identical synthetic RNG output, and all seven extension types pass
  the same domain-neutral contract-echo compatibility matrix
- Upload parts stream incrementally to a fresh server-generated staging key; exact per-part and
  complete-object size/SHA-256 are checked before a Raw Asset can be committed
- Upload capabilities are deterministically signed but not persisted as plaintext, and are bound
  to session, organization, project, actor, and expiry in addition to bearer authorization
- PostgreSQL blocks part replacement, Raw Asset/Ingestion Event mutation, incomplete completion,
  invalid state transitions, cross-project reads/writes, and storage-key exposure in API contracts
- Same-classification duplicate bytes reuse one Raw Asset while appending a distinct immutable
  ingestion event; mismatch and cancellation leave no successful Raw Asset fact

## Validation result

Commands: `make ci` and `make test-postgresql` with an ephemeral PostgreSQL 16-compatible server

```text
Ruff: passed
mypy strict: passed (147 source/test files)
Architecture rules: passed
Contract lint: passed
OpenAPI compatibility: passed
make ci: 174 passed, 40 PostgreSQL-gated tests skipped without CMP_TEST_POSTGRES_DSN
Full suite with PostgreSQL 16.14: 214 passed
```

## Intentionally absent

- Public role-management API/UI and deployment-specific DB role/secret provisioning
- Export-control nationality/compartment policy (`OQ-SEC-002`)
- Material, test, dataset, typed provenance, or audit-chain implementations
- Content-addressed final Artifact promotion, download tokens, S3 production adapter,
  outbox/reconciliation, deployment runner credential provisioning, and
  signature/SBOM/malware/vulnerability verification automation
- A selected production OCI runtime implementation and production package/image admission policy
- Production plugins
- Constitutive equations, fitting algorithms, solver cards, or validation thresholds
- Frontend application

## Next gate

Per the repository blueprint, the next task is `T-10`: content-addressed final Artifact and
integrity reconciliation. T-09 deliberately stops at a digest/size-verified staging object and
`staged_verified` Raw Asset. T-18 package/input materialization and validated Result Manifest/output
commit remain behind T-10 ports; an unconfigured worker remains safely idle.
Audit (`T-05`), provenance (`T-13`), catalog (`T-07`), and outbox/reconciliation (`T-16`) are not
implied complete.


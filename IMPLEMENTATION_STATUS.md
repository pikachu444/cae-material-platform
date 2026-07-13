# Implementation Status

Date: `2026-07-14`
Foundation version: `0.17.0`

## Completed

- `T-01`: modular-monolith repository skeleton, bounded-module namespaces, deployable API and
  worker shells, developer commands, architecture rules and regression fixtures
- `T-02`: OpenAPI/AsyncAPI baseline, JSON Schema registry, positive/negative contract examples,
  deterministic minimal client generation, compatibility detector and validation pipeline
- `T-03`: strict OIDC JWT access-token validation, user/service principal resolution, immutable
  external identity projection, request security context, `/api/v1/me`, and development test IdP
- `T-04`: conservative deny-by-default role matrix, principal/group role bindings, append/revoke
  administration, classification ABAC, reusable authorization dependency, and forced PostgreSQL RLS
- `T-05`: project-scoped append-only audit chain, DB-computed canonical SHA-256, periodic segment
  roots, atomic revision hook, tamper verification, and protected query/export/integrity API
- `T-06`: framework-free aggregate revision kernel, explicit typed-table SQLAlchemy adapter,
  PostgreSQL/Alembic immutability and tenant primitives, initial lifecycle event/projection,
  strong ETag and revision metadata contracts
- `T-07` MVP subset: Material and Material State stable identities separated from immutable typed
  revisions; explicit SI density/Young's modulus/Poisson ratio/optional yield property columns,
  per-value source and applicability; search/detail/history/compare APIs; provenance/audit/lifecycle
  hooks; PostgreSQL composite tenant/classification FKs, indexes, and forced RLS. Process/Lot/Batch
  genealogy remains outside this subset.
- `T-08` reference subset: explicit Specimen, reference uniaxial tensile Test Method, and Test Run
  stable identities with immutable typed revisions; a Test Run pins concrete Specimen/Test Method
  revisions, a State-specific specimen code, optional test temperature/crosshead speed, protected
  APIs, audit/provenance/lifecycle hooks, PostgreSQL tenant/classification FKs, RLS, and immutable
  tables. Campaign, instrument, standard, and production test-method variants remain separate work.
- `T-12` reference subset: a user-confirmed UTF-8 reference tensile CSV mapping with explicit
  engineering strain/stress columns and limited `1`/`%` and `Pa`/`kPa`/`MPa`/`GPa` units; one stable
  Dataset identity appends raw CSV and normalized SI Parquet revisions without overwriting either;
  typed channel semantics, Raw Asset/Artifact/Test Run concrete references, raw-input provenance,
  bounded curve preview, PostgreSQL constraints/RLS, protected APIs, and deterministic regression
  coverage. Generic importer detection, arbitrary channel schemas, and other test formats remain
  separate work.
- `T-32` MVP subset: React/Vite Material Catalog workbench backed by protected Catalog, Modeling,
  and Exporting APIs; Dashboard, search, Material creation, State and typed Property Set
  entry/revision, revision compare/history, provenance summary, and the reference
  IR→mapping-preflight→Solver Card preview/download workflow. Test upload and tabular column-mapping
  UI remain outside this subset.
- `T-32` extension: the protected Material State screen now drives the reference tensile sequence:
  concrete Specimen selection, reference Method registration, immutable Test Run creation, browser
  multipart CSV upload, explicit column/unit mapping, and raw/normalized Dataset revision/curve
  inspection. It remains deliberately limited to the reference tensile CSV contract.
- Local demo composition: an explicit `CMP_ENVIRONMENT=demo` + `CMP_DEMO_IDENTITY=true` Docker
  Compose profile now runs PostgreSQL, owner-only migration/bootstrap, a non-owner `cmp_app` API,
  worker, React workbench, filesystem object storage, checked reference-plugin asset, and an
  API-driven synthetic seed. The seed creates a Material/State/properties/reference IR/OpenRadioss
  card plus a reference tensile Raw Asset and raw/normalized Dataset revisions without direct
  database writes or an authorization/RLS bypass.
- `T-22` reference subset: a stable Material Model identity and immutable reference
  isotropic-linear-elastic IR revision projected from one concrete Property Set revision; explicit
  SI density/Young's modulus/Poisson ratio columns, source-yield disposition, semantic/unit bounds,
  Material→State→Property lineage composite FKs, API/list/history resources, provenance/audit/lifecycle
  hooks, PostgreSQL RLS, and non-production-only contract. Generic model-schema registration,
  calibration evidence, and production model families remain separate work.
- `T-25` reference subset: an explicit OpenRadioss 2025 `/MAT/ELAST` exporter for only the
  reference linear-elastic IR and `kg_m_s` units; typed capability/preflight/mapping-report and
  immutable Solver Card identity/revision tables, source-revision FKs, SHA-256 report/card digests,
  provenance/audit/RLS, protected preview/download APIs, and no generic exporter/options payload.
  Production solver qualification, additional targets, transforms, approximations, and release
  approval remain separate work.
- `T-26` reference subset: a byte-exact `.rad` golden fixture plus report-acknowledgement,
  unsupported-target, and text-tamper regressions. A multi-target/version matrix, semantic parser,
  and domain-review golden-update workflow remain separate work.
- `T-09`: resumable streaming multipart sessions, HMAC actor/tenant/expiry capabilities,
  immutable part manifests, verified staging Raw Assets, append-only ingestion events, duplicate
  content detection, protected API, filesystem development adapter, and forced PostgreSQL RLS
- `T-10`: tenant/classification-scoped content-addressed promotion, immutable Artifact manifests,
  append-only integrity observations/issues, guarded current projection, mismatch reconciliation,
  scoped streaming download, protected API, and forced PostgreSQL RLS
- `T-13`: typed Entity/Activity/Agent and six core relation families, immutable owner-reference
  resolution, atomic run/revision hooks, deferred completeness, DAG cycle guards, protected Entity
  lookup, and forced PostgreSQL RLS
- `T-14`: bounded recursive upstream/downstream lineage, downstream impact filters and opaque
  pagination, deterministic shortest paths, generic Entity-root completeness gate, typed
  security-invoker read models, graph explosion limits, and tenant/classification-safe APIs
- `T-15`: stable Job/immutable Attempt separation, versioned Job Spec digests, PostgreSQL atomic
  claim/lease/heartbeat/recovery, generic retry taxonomy, runner resources, protected Job API,
  and a handler-neutral durable worker
- `T-16`: transactional CloudEvent outbox, aggregate sequence and producer deduplication, fenced
  at-least-once delivery, poison quarantine, inbox deduplication, atomic ArtifactAvailable event,
  durable reconciliation schedule/run lease, and staging-only retention receipts
- `T-17`: stable Plugin Definition/immutable Package separation, Manifest 1.0 and JSON Schema
  validation, explicit capability/schema/supply-chain references, append-only verification and
  activation history, project-scoped allowlisting, protected API, and forced PostgreSQL RLS
- `T-18`: framework-free Python SDK, immutable Job Spec/Result Manifest execution service,
  reviewed-package subprocess runner, OCI-ready production plan and capability attestation,
  tenant-scoped active-package planning, durable worker bridge, and seven-extension TCK

## Runtime proof

- FastAPI health endpoint: `GET /api/v1/health`
- Web workbench: `http://127.0.0.1:5173` after `npm run dev --workspace @cmp/web`; it uses the
  configured bearer token and `/api/v1` contract without an authorization bypass
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
- Material Catalog writes append separate Material, State, and Property Set revisions; original
  rows reject mutation/deletion, State/Property identities cannot move to another parent, and all
  parent references are concrete revisions rather than moving heads
- Catalog search/detail and writes use `catalog.read`/`catalog.write` with organization/project and
  classification RLS; PostgreSQL integration proves cross-project hiding plus lifecycle, provenance,
  and audit facts for every Catalog revision
- Reference Material Model creation uses `modeling.write` plus its explicit `catalog.read`
  dependency; source values are selected by concrete Property Set revision, then persisted with
  concrete Material/State/Property revision references. PostgreSQL constraints prevent mixed parent
  lineage, RLS hides cross-project models, and original IR revisions reject mutation/deletion.
- Reference Solver Card creation consumes a concrete Material Model revision only; an explicit
  OpenRadioss 2025 `/MAT/ELAST` `kg_m_s` preflight returns every mapping status and its digest must
  be acknowledged before an immutable typed card revision is written. PostgreSQL T-25 integration
  coverage proves provenance/audit derivation, tenant isolation, and card-revision immutability.
- Reference tensile Test Runs pin the exact Specimen and Test Method revisions used at registration;
  a Dataset import accepts only the matching tenant/classification Test Run and the completed
  `text/csv` Raw Asset Artifact, then appends raw and normalized Dataset revisions rather than
  mutating source bytes or a published curve.
- Dataset CSV import rejects missing/duplicate columns, unsupported units, non-finite/negative
  points, non-monotonic engineering strain, and ambiguous mapping. It produces typed SI Parquet
  only after the user supplied the mapping, and attaches the Raw Asset as input provenance to the
  Dataset generation activity.
- The Material State workbench calls the protected Testing/Dataset/Upload APIs directly; it keeps
  raw and normalized curve revisions selectable, labels their units, and uses deterministic preview
  sampling rather than treating a browser plot as a calculation artifact.
- The local Compose workbench can request a demo token only from an explicitly enabled demo API;
  the in-process token issuer is absent from normal/production configuration, and the resulting
  token follows the same JWT verification, group role-binding, authorization, and RLS path as a
  normal API request. The database bootstrap creates an owner-distinct `cmp_app` role and grants
  only the existing bounded-module table/function operations it requires.
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
- Raw Asset promotion never updates its staging fact; one separate immutable Artifact references
  it, and cross-actor duplicate ingestion reuses the same available Artifact
- PostgreSQL requires an exact promoting pending manifest before Artifact insertion and an exact
  immutable observation before integrity projection change; terminal pending/Artifact rows reject
  every mutation or deletion
- Content keys include organization, project, classification, and SHA-256; filesystem promotion
  rehashes source/final bytes and uses no-overwrite commit with idempotent identical replay
- Reconciliation recovers object-success/DB-gap, records missing/corrupt observations and
  orphan/missing-staging issues, and never rewrites an Artifact manifest
- Download grants are canonical HMAC capabilities bound to actor, tenant, Artifact, digest, and
  expiry; bearer authorization remains required and public contracts contain no object keys
- Raw Asset→synthetic revision commit records typed usage, generation, derivation, and association
  atomically; the same domain-run graph replays while digest substitution is rejected
- PostgreSQL rejects generated orphan Entity records, incomplete Activities, duplicate primary
  generation, reverse dependency cycles, cross-project reads, and every provenance mutation/delete
- T-06 typed revision transactions can install a fail-closed hook that records revision generation,
  author association/attribution, and `wasRevisionOf` in the caller's transaction
- Public provenance access is read-only Entity lookup, bounded lineage/impact, and completeness;
  moving heads, DB table details, raw payloads, and object keys are absent from the contract
- Recursive discovery and RLS-protected Entity materialization use separate bounded SQL phases so
  PostgreSQL avoids a pathological security-view join plan; known DAG paths remain deterministic
- A 10-hop chain and 10,000-edge fan-out run under the two-second query assertion, while depth 20,
  10,000 nodes, page size 1,000, cycles, duplicate paths, cursor rebinding, and graph truncation
  fail closed
- Artifact finalization and ArtifactAvailable outbox append commit or roll back together; exact
  replay emits one event, schema validation fails the transaction, and event data contains no
  object-store key
- Outbox aggregate sequence blocks out-of-order claims; publisher crash recovery replaces the
  lease token, stale fencing is rejected, poison blocks later aggregate events, and duplicate
  consumer delivery creates one inbox receipt
- Reconciliation schedules reclaim expired runs as timed out, append a fresh fenced run, execute
  the existing T-10 reconciler, and record idempotent cleanup only after discarding an eligible
  terminal pending staging object; the content-addressed final object remains intact
- Audit append derives only from an authorized modifying command; PostgreSQL serializes each
  project chain and computes sequence, previous hash, recorded time, and event hash itself
- Periodic roots cover only the next contiguous unsealed range and form their own root chain;
  application recomputation matches PostgreSQL and reports unsealed tail events separately
- Audit rows and roots reject update/delete, cross-project readers see no rows, and mutation,
  reorder, or deletion performed through a privileged tamper fixture makes integrity invalid
- Public audit access is read-only event query, bounded export, and integrity reporting; raw
  payloads, secrets, IP addresses, object keys, and generic JSON/EAV are absent from DB/contracts

## Validation result

Current command: `make ci` (or the equivalent `scripts/ci.sh` command sequence on a Windows
environment without `make`); the PostgreSQL integration suite additionally requires
`CMP_TEST_POSTGRES_DSN`.

```text
Ruff: passed
mypy strict: passed (265 source files)
Architecture rules: passed
Contract lint: passed
OpenAPI compatibility: passed
CI-equivalent test sequence: 261 passed, 61 PostgreSQL-gated tests skipped without CMP_TEST_POSTGRES_DSN
Web workbench build: passed; Vitest: 11 passed
Local demo identity/API, Compose seed request construction, Compose YAML, and browser connection
  token tests are implemented. Docker is not installed in this Windows environment, so the
  containers and live PostgreSQL demo could not be started here.
T-25 PostgreSQL integration coverage is implemented but not executed in this environment because
  CMP_TEST_POSTGRES_DSN is unavailable; the reference Test/Dataset migration has offline SQL
  rendering coverage, while a live PostgreSQL test remains the next verification task.
```

## Intentionally absent

- Public role-management API/UI and deployment-specific DB role/secret provisioning
- Export-control nationality/compartment policy (`OQ-SEC-002`)
- Process/Lot/Batch genealogy, richer typed property/curve families, Test Campaign/Instrument
  records, generic importer detection/mapping approval, and non-reference Dataset channels
- Release resources and release-specific evidence/review/mapping gates (`T-30`); T-14 exposes only
  the reusable provenance-completeness report
- Production S3 adapter, KMS/object-lock/versioning/replication provisioning, external event
  transport credentials, and deployment runner credentials
- T-17 authoritative package-Artifact admission, T-18 materializer/committer deployment wiring,
  and signature/SBOM/malware/vulnerability verification automation
- A selected production OCI runtime implementation and production package/image admission policy
- Production plugins
- External audit root signer, SIEM/WORM connector, retention/legal-hold policy, and deployment
  service-principal scheduling for periodic sealing
- Fitting algorithms, production solver cards/targets, or validation thresholds; the implemented
  reference IR and OpenRadioss card are not calibrated or production-qualified
- Production web identity/session integration, external demo IdP deployment, and a production
  Compose/deployment profile; the checked-in demo issuer is explicitly local-only

## Next gate

**Updated 2026-07-14:** the reference Test/Dataset slice described below is now implemented.
The current next step is versioned Processing and Selection: begin only with a small, explicitly
chosen crop/resample or engineering-to-true transform after the relevant Material/Test domain
decision. Statistics, outlier assessment, calibration, and release evidence remain separate
bounded work.

Prior planning note (superseded): the first vertical flow was described as a non-production reference subset:
Material → State → typed Property Set → frozen reference IR → explicit OpenRadioss mapping report
→ immutable card preview/download. The next contiguous product step is the Test/Dataset vertical
slice: Specimen/Test metadata, reference tensile CSV upload, column/unit mapping, raw and
normalized curve viewing, and a concrete Material link. T-30 still owns Release creation and
evidence policy; T-17/T-18 production Artifact composition and release-specific retention/backup
policy are not implied complete.


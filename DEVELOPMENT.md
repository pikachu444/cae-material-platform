# CAE Material Platform — Development Guide

Status: Material Catalog MVP, reference tensile Dataset/Statistics-QC/outlier review, reference Calibration Plan/Run diagnostics with human Candidate Selection/IR promotion, reference linear and tabulated-isotropic-plasticity Material Model IRs, OpenRadioss and Abaqus reference Solver Cards, and reference virtual-specimen evidence/result interpretation runner
plus identity, authorization, revision, streaming Raw Asset upload,
immutable content Artifact, typed provenance and bounded lineage, append-only audit, durable job
and transactional event, plugin registry, and isolated runner foundation
(`T-01`–`T-21` + reference `T-22`–`T-32` subsets + bounded `T-D03`)

Version: `0.30.0`

This repository is the implementation workspace for the CAE material-data platform defined in
`docs/`. The first product slice implements Material, Material State, and explicitly typed basic
mechanical Property Set revisions. It intentionally does not use generic EAV or JSON property
payloads: density, Young's modulus, Poisson ratio, optional yield stress, source, and applicability
are named SI fields. The React Material Catalog workbench connects to these protected APIs for
search, Material/State entry, typed property entry/revision, revision comparison, and provenance
summary. The first non-production Material Model IR can now be created only from one concrete
Property Set revision: it keeps Material/State/Property revision lineage, typed SI density/E/ν,
applicability, and an explicit disposition for an optional yield value that the linear-elastic
reference model does not use. The first card exporter consumes only that frozen IR revision and
creates a non-production OpenRadioss 2025 `/MAT/ELAST` text card after an explicit mapping
preflight/report acknowledgement. The workbench exposes the resulting immutable card preview and
authenticated download. A narrow reference tensile flow now creates a concrete Specimen, pins a
Test Run to concrete Specimen/Test Method revisions, uploads one UTF-8 CSV as a Raw Asset/Artifact,
records an immutable header-only Detection Report, requires a separate human-confirmed Mapping
revision, and then records a Processing-owned Import Run that pins the exact mapping before it
creates separate raw and normalized Dataset revisions. Low-confidence header suggestions are never
committed automatically.
The same protected Material State screen can reduce one normalized or processed monotonic tensile
Dataset through its first maximum engineering stress. The immutable solver-neutral IR records the
engineering-to-true conversion profile, exact source/excluded point counts, Catalog yield anchor,
and explicitly acknowledged constant-stress post-necking approximation in a Parquet hardening
Artifact. That one IR can produce either an OpenRadioss 2025 `/MAT/LAW36` + `/FUNCT` card or an
Abaqus 2025 `*DENSITY` + `*ELASTIC` + `*PLASTIC` card. Preflight labels the extension
`approximated`; card creation requires acknowledgement of that exact mapping-report digest.
The reference Statistics/QC slice pins two distinct normalized Selection revisions from distinct
Test Runs, records immutable QC observations, and creates a separate typed scalar/curve Result only
when their observed engineering-strain grids match exactly; it never aligns or resamples curves
implicitly. The reference calibration slice then pins one normalized or processed Selection revision
and one reference linear-elastic IR revision in an immutable Plan, records every deterministic
bounded-WLS multistart Attempt and Candidate, and stores typed observed/predicted/residual Parquet
diagnostics. It is a non-production closed-form `sigma = E * epsilon` workflow reference: it does
not select a production optimizer or approve a model. A Material Modeler can separately record a
reasoned human Candidate Selection and append a new IR revision only when the exact evaluated IR
is still current; it never rewrites the Candidate, source IR, Dataset, or a solver card. The T-03/T-04
identity and access-control foundation,
the domain-neutral T-06 revision kernel, the generic T-15 Job/Attempt/Lease engine, the T-17
immutable plugin package registry, and the T-18 isolated execution contract remain reusable
platform infrastructure. T-09 adds verified staging Raw Assets, and T-10 promotes them into
tenant-scoped content-addressed immutable Artifacts with integrity observations and scoped streaming
download.
T-13 adds domain-neutral typed Entity/Activity/Agent relations and fail-closed completeness without
creating any Material, Dataset, Test, fitting, or solver implementation.
T-14 adds bounded bidirectional lineage, impact pagination, and a generic Entity-root provenance
completeness gate. Release creation and release-specific evidence policy remain owned by T-30.
T-16 adds a PostgreSQL transactional CloudEvent outbox, fenced at-least-once delivery, consumer
inbox deduplication, an atomic ArtifactAvailable event, durable Artifact reconciliation scheduling,
and staging-only retention cleanup.
T-05 adds project-scoped append-only audit events, deterministic hash chains, periodic segment
roots, a same-transaction T-06 revision hook, and auditor-only query/export/integrity APIs.

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
- Explicit PostgreSQL `catalog.material`, `material_revision`, `material_state`,
  `material_state_revision`, `property_set`, and `property_set_revision` relations; immutable
  revisions, composite tenant/classification parent FKs, forced RLS, indexes, and no EAV payload
- Protected Material create/search/detail/revision comparison, State creation/revision, and typed
  Property Set create/revision APIs with same-transaction lifecycle, provenance, and audit facts
- React/Vite Material Catalog workbench connected to the protected APIs, including Dashboard,
  search, Material creation, State/property forms, revision history/compare, and provenance summary
- Reference IR creation, explicit OpenRadioss 2025 `/MAT/ELAST` mapping preflight, mapping-status
  report, immutable Solver Card preview, and authenticated `.rad` download in the Material State
  workbench; target/unit defaults and silent approximations are prohibited
- Typed pre-necking tensile reduction to true stress/true plastic strain with no hidden smoothing,
  fitting, resampling, or source mutation; immutable Parquet hardening Artifact plus explicit
  source/excluded point evidence in the tabulated-plasticity IR revision
- OpenRadioss 2025 `/MAT/LAW36` + `/FUNCT` and Abaqus 2025 `*DENSITY` + `*ELASTIC` +
  `*PLASTIC, HARDENING=ISOTROPIC, EXTRAPOLATION=CONSTANT` exporters from the same IR, with
  field-level mapping status, explicit approximation acknowledgement, byte-exact `.rad`/`.inp`
  golden fixtures, protected preview, and authenticated download
- Explicit reference tensile `testing.specimen`, `testing.test_method`, and `testing.test_run`
  identity/revision relations; Test Runs pin concrete source revisions and no test result overwrites
  a source run
- Explicit `datasets.dataset`/`dataset_revision` records linked to Raw Asset and Artifact IDs;
  raw UTF-8 CSV bytes remain unchanged while one normalized SI Parquet Artifact is appended as a
  second immutable revision, with typed engineering strain/stress channel semantics
- Material State workbench controls for Specimen, reference Test Method, Test Run, CSV upload,
  immutable header Detection Report, explicit human-approved Mapping revision, Import Run status,
  and bounded raw/normalized curve preview; no column or unit inference is committed by the browser
  or importer
- Reference Calibration workbench controls for concrete Dataset Selection/Material Model revision
  pinning, explicit Young's-modulus bounds/initial value/normalization/seed/multistart conventions,
  durable Run execution, Candidate summary, observed-versus-fitted diagnostics preview, explicit
  human Candidate Selection reason, and append-only IR promotion; the source Dataset and evaluated
  IR remain unchanged, while the promoted IR retains typed Selection/Candidate/Run/diagnostics evidence
- Explicit PostgreSQL `testing.import_detection_report`, `testing.import_mapping`,
  `testing.import_mapping_revision`, and `processing.import_run` relations with frozen Raw
  Asset/Artifact/Test Run/Mapping references, source-digest guards, tenant/classification composite
  keys, forced RLS, indexes, and append-only transition guards; no generic importer payload/EAV
- Explicit PostgreSQL `exporting.solver_card` and `solver_card_revision` relations with frozen
  Material Model revision FKs, typed SI card fields/status columns, mapping/card SHA-256 digests,
  tenant/classification composite keys, forced RLS, and append-only guards; no EAV/card JSON
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
- Explicit PostgreSQL `events.outbox_event`, delivery lease, and consumer inbox relations with
  aggregate sequence, producer deduplication, poison quarantine, forced RLS, and immutable facts
- Schema-validated CloudEvents 1.0 ArtifactAvailable event committed atomically with the immutable
  Artifact; no object key or vendor transport detail is exposed
- Broker-neutral at-least-once publisher port with lease fencing, crash reclaim, per-aggregate
  ordering, and same-transaction consumer inbox deduplication
- Tenant-scoped reconciliation schedule and immutable run history with crash lease recovery;
  retention receipts cover only terminal pending staging keys and never final objects
- Explicit PostgreSQL `audit.event` and `audit.segment_root` relations with DB-computed sequence,
  canonical SHA-256 chain/root hashes, append-only triggers, forced RLS, and no payload JSON/EAV
- T-06 same-transaction revision audit hook, policy-redacted client field, mutation/reorder/delete
  verifier, and protected auditor query, bounded export, and integrity-report APIs

## Prerequisites

- Python 3.12+
- `uv`
- `make`
- Node.js 20.19+ and `npm` for the web workbench
- Docker Engine with Docker Compose v2 for the canonical full-stack demo; on Windows use Docker
  Desktop with the WSL 2 backend
- PostgreSQL 16+ for migration and persistence integration tests. A separate host installation is
  not required when the Compose PostgreSQL service is used.

Windows installation requires user/admin interaction and may require a reboot: confirm hardware
virtualization, install or update WSL 2, install Docker Desktop, start it, and wait until the Docker
Engine is running. Exact commands, verification checks, and troubleshooting are in
[the Compose guide](deploy/compose/README.md#windows-installation-prerequisites).

## Local end-to-end demo

The fastest way to exercise the first product slice is the explicit local
Docker Compose demo:

```bash
docker compose -f deploy/compose/docker-compose.demo.yml up --build
# or: make demo
```

It starts PostgreSQL, an owner-only migration/bootstrap job, the non-owner API,
the generic worker, the React workbench, reference-plugin asset check, and an
API-only synthetic data seed. The seed follows the protected product path:

```text
Material → Material State → typed properties → reference IR
→ OpenRadioss mapping report → immutable .rad Solver Card
→ normalized tensile Dataset → tabulated-plasticity IR
→ OpenRadioss .rad and Abaqus .inp elastoplastic cards
```

It also creates one synthetic tensile CSV as a Raw Asset, appends raw plus normalized Dataset
revisions, reduces the normalized curve into a non-production elastoplastic IR, and generates both
reference elastoplastic cards. Open `http://127.0.0.1:5173`, select
**Connection**, choose **Use local demo identity**, and save. The button exists
only because this composition explicitly sets `CMP_ENVIRONMENT=demo` and
`CMP_DEMO_IDENTITY=true`; the issued 15-minute signed token is still verified
by the normal JWT, RBAC, and PostgreSQL RLS path. No real company or validated
engineering data is included. See [the compose guide](deploy/compose/README.md)
for ports and teardown.

For the P0-1 verification gate, run the composition detached, point the test suite at its disposable
owner endpoint, and require zero PostgreSQL-marked skips:

```powershell
docker compose -f deploy/compose/docker-compose.demo.yml up --build -d
docker compose -f deploy/compose/docker-compose.demo.yml --profile test up -d postgres-test
$env:CMP_TEST_POSTGRES_DSN = "postgresql+psycopg://cmp_test_owner@127.0.0.1:54330/postgres"
uv run pytest -m postgresql tests/integration -ra
& "C:\Program Files\Git\bin\bash.exe" scripts/ci.sh
```

The current count of 62 PostgreSQL-gated tests is an observed snapshot, not a contract. P0-1 means
the marker suite has skip 0/failure 0, the CI-equivalent suite passes with the same DSN, and the live
demo works. Never use a production or shared database for this command. See
[the test strategy](docs/14-testing/test-strategy.md#p0-1-windowscompose-verification-runbook) for the
full health, log, and teardown procedure.

The live P0-1 gate completed with 62 PostgreSQL-marked tests passed (zero skips/failures), 452
CI-equivalent Python tests passed, and 21 Vitest tests passed. The observed counts are not fixed;
skip zero and failure zero are the acceptance rule.

## Current delivery order

[ADR-0019](adr/0019-near-term-delivery-and-postgresql-verification-gate.md) applies this sequence
without discarding the implemented foundation:

1. `P0-1` (**complete**): live Docker Compose/PostgreSQL migration, RLS, integration, CI, and browser verification.
2. `P0-2` (**complete**): multi-replicate Selection, explicit common-grid processing, persisted
   Statistics/QC, outlier evidence, human assessment, and calibration-scoped inclusion/exclusion.
3. `P1` (**complete, non-production reference scope**): bounded Voce/SciPy calibration, Candidate
   selection, calibrated IR, OpenRadioss/Abaqus cards, and disjoint solver-independent holdout.
4. `P2` (**next**): Process/Lot/Batch and broader domain work, actual solver/HPC execution qualification,
   production plugins, and operational/release hardening.

The P1 Voce/SciPy path is a synthetic `reference_only` implementation choice. It does not approve a
production constitutive model, optimizer, parameter policy, card, or validation threshold. Actual
solver execution verification is deferred to P2; deterministic card goldens continue to guard
mapping regressions only.

The demo seed creates three calibration replicate Test Runs plus a fourth, disjoint holdout Test
Run. In the Material State workbench, align the three-member Selection, calculate Statistics/QC,
review outlier evidence, freeze a calibration input Scope, run and accept a Voce Candidate, generate
the calibrated OpenRadioss or Abaqus card, then select the fourth Dataset for the holdout check.
The holdout compares the frozen model response directly with the independent curve and explicitly
reports `solver_execution=not_used`; its fixed 5% relative-RMSE threshold is reference evidence,
not engineering approval.

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

## Material Catalog workbench

Start the API with a migrated PostgreSQL database and a valid OIDC configuration, then start the
web workbench in a second terminal:

```bash
npm ci --workspaces --include-workspace-root
npm run dev --workspace @cmp/web
```

Open `http://127.0.0.1:5173`. The development server proxies `/api` to
`http://127.0.0.1:8000`; set `VITE_CMP_API_TARGET` to use a different local API target. In the
**Connection** panel, provide the API base URL (default `/api/v1`) and a short-lived bearer access
token issued for the desired organization/project. The client deliberately sends no Material request
without a token and does not bypass the API's authorization or PostgreSQL RLS policy.

For the first runnable product flow, create a Material, add a Material State, record density/E/ν,
then use **Material Model IR → Solver Card** within that State. The UI creates an immutable reference
IR from the selected Property Set revision, requires an explicit OpenRadioss 2025 `kg_m_s` target,
shows every mapping status, and enables preview/download only after the report digest is acknowledged.
This narrow exporter is non-production and is based on the official
[OpenRadioss 2025 `/MAT/LAW1` (`/MAT/ELAST`) reference](https://2025.help.altair.com/2025/hwsolvers/rad/topics/solvers/rad/mat_law1_elast_starter_r.htm).

### Reference tensile CSV Dataset

Within a Material State, open **Manage reference tensile data** and perform the following explicit
sequence: register a Specimen, register the reference tensile Test Method for the State's
classification, create a Test Run, select a UTF-8 CSV, enter the source strain/stress column names
and units, then create the Dataset. The importer accepts only engineering strain (`1` or `%`) and
engineering stress (`Pa`, `kPa`, `MPa`, or `GPa`) and rejects ambiguous, missing, non-finite,
negative, or non-monotonic data. It never guesses a mapping. The resulting viewer permits a
concrete raw or normalized Dataset revision to be selected; the curve preview is bounded and is not
the calculation input.

### Reference tensile Processing

After a normalized Dataset revision exists, the same Material State workbench can create a named
Selection that pins that exact revision, create a named reference crop Recipe with inclusive minimum
and maximum engineering-strain bounds, and execute a **committed** Processing Run. Its only output
is a typed processed Parquet Artifact and a separate processed Dataset identity at revision 1; the
raw CSV, raw Dataset revision, and normalized Dataset revision remain unchanged. The output curve is
then shown from that concrete processed revision.

This is deliberately a small non-production reference operation: it accepts one normalized
reference tensile Dataset, retains observed points only, and does not interpolate, resample, smooth,
convert engineering to true quantities, average repeats, or make a temporary preview artifact.
Selection/Recipe revisions and the output Dataset are auditable, and the output provenance records
the pinned input, Recipe, and Processing Run. A normalized or processed Selection may subsequently
be used as a concrete Calibration input; neither representation is overwritten.

### Reference tensile Statistics/QC

The same Material State workbench can compare two pinned normalized Dataset Selections from
distinct Test Runs. A **Statistical Plan** immutably pins both Selection revisions. A committed
**Statistical Run** records the distinct-Test-Run and exact-observed-grid QC observations, then
creates a separate immutable Result revision and typed Parquet curve artifact when QC passes.
Scalar output uses one peak engineering-stress value per Test Run (`n=2`) and reports mean, sample
standard deviation, median, MAD, IQR, range, and coefficient of variation. Pointwise output carries
mean, sample standard deviation, median, minimum, and maximum on the unchanged observed grid.

This deliberately narrow reference method does not interpolate, resample, smooth, extrapolate, or
claim a confidence interval from the two-sample pair. Its response explicitly reports
`not_provided_reference_pair`; larger replicate groups, alignment processing, and calibration
remain separate bounded work.

### Reference tensile outlier review

After a successful reference Statistics Result is visible, the same Material State workbench can
create an immutable Outlier Detection Plan that pins that exact Result revision and a declared
relative peak engineering-stress difference threshold. The committed detector creates no candidate
below the threshold, or exactly two review_required candidates at/above it—one per pinned
Selection/Dataset/Test Run. With exactly two samples it does not claim to know which specimen is an
outlier and never excludes data automatically.

A human records a separate immutable Outlier Assessment identity as either retained or
excluded_from_reference_analysis, with reason and actor context. The decision is restricted to the
exact Statistical Plan revision that produced the candidate. The scope-comparison screen shows
candidate evidence and append-only assessment history while explicitly confirming that no Raw
Asset, Dataset, Selection, or Statistical Result was modified and no derived Selection was
created. Calibration-specific exclusion remains a later schema decision after a concrete
Calibration Plan exists.

### Reference linear-elastic Calibration

Open **Open calibration workbench** within the same Material State after creating a reference
Material Model IR and a normalized or processed Dataset Selection. Select those current immutable
revisions, enter explicit Young's-modulus lower/initial/upper values in Pa, normalization scale,
multistart count, and a seed, then create a Calibration Plan and execute it. The result keeps every
Attempt and Candidate, including failure, and shows the bounded observed-versus-fitted stress-strain
diagnostics preview.

This is deliberately a non-production reference calculation of `sigma = E * epsilon` using a
deterministic analytic bounded weighted least-squares solution. It does not select a production
optimizer or constitutive model, estimate uncertainty, approve a candidate, or validate/modify a
Solver Card. After inspecting diagnostics, select one `converged` Candidate, enter an explicit
human reason, and record the immutable Candidate Selection. A separate promotion action appends a
new Material Model IR revision only when the Selection revision and exact evaluated source IR are
still current. It stores typed Selection, Candidate, Run, and diagnostics Artifact evidence and
never overwrites any source revision. See the
[reference calibration contract](docs/10-execution/reference-linear-elastic-calibration.md).

### Reference virtual-specimen evidence

Within the same Material State, open **Reference virtual specimen runner** after a reference
Material Model IR, compatible OpenRadioss card, and experimental Dataset Selection exist. The
workbench creates a versioned one-dimensional tensile Template, then a Validation Plan that pins
the exact Template, IR, Card, and Selection revisions. It can submit and collect an explicit
`reference_inline_mock` outcome, or create a manual-attachment run with an opaque external job ID
and bounded native JSON/log evidence.

Both paths retain an immutable deck, stdout/stderr, optional native result, and Result Manifest
Artifact/provenance record. After a terminal manifest, **Extract response and evaluate** appends a
separate typed SI response Artifact, numerical-health Artifact, and comparison-result Artifact. The
workbench displays health, holdout independence, relative RMSE, fixed `0.05` reference threshold,
Artifact evidence, and an observed-versus-simulated curve. Comparison is linear interpolation only
at observed experimental strain points and rejects extrapolation. Abnormal/unhealthy/no-output,
unit/alignment-invalid, and fit/holdout-overlap results are `not_evaluated`.

This is deliberately **non-production reference evidence**: it does not execute OpenRadioss or an
HPC scheduler, and even a `passed` reference result is not solver qualification, material approval,
or release approval. See [ADR-0013](adr/0013-reference-validation-template-and-runner-boundary.md)
and [ADR-0014](adr/0014-reference-validation-result-interpretation-policy.md).

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
GRANT USAGE ON SCHEMA identity, revisioning, access_control, governance, jobs, plugin, artifact, provenance, events, audit, catalog, testing, datasets, processing, statistics, modeling, exporting, validation TO cmp_app;
GRANT SELECT, INSERT, UPDATE ON identity.principal, identity.external_identity TO cmp_app;
GRANT SELECT, INSERT, UPDATE ON identity.role_binding TO cmp_app;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA governance TO cmp_app;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA jobs TO cmp_app;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA plugin TO cmp_app;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA artifact TO cmp_app;
GRANT SELECT, INSERT ON ALL TABLES IN SCHEMA provenance TO cmp_app;
GRANT UPDATE ON provenance.activity, provenance.association TO cmp_app;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA events TO cmp_app;
GRANT SELECT, INSERT ON ALL TABLES IN SCHEMA audit TO cmp_app;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA catalog TO cmp_app;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA testing TO cmp_app;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA datasets TO cmp_app;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA processing TO cmp_app;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA statistics TO cmp_app;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA modeling TO cmp_app;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA exporting TO cmp_app;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA validation TO cmp_app;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA access_control, revisioning, plugin, artifact, provenance, audit TO cmp_app;
```

Future bounded-module migrations grant only the table operations their adapters require. Every
tenant-owned table must use the module's explicit tenant/permission policy,
`ENABLE ROW LEVEL SECURITY`, and `FORCE ROW LEVEL SECURITY`; granting SQL privileges alone never
grants row access.

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
make web-build
make web-test
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
calibration choices, solver cards, and validation criteria remain `TBD`; ADR-006's T-22/T-25
linear-elastic/OpenRadioss path is an explicitly non-production reference projection and card, not
a production material model or solver qualification. ADR-011/ADR-012's T-23/T-24 calibration path is
likewise an explicitly non-production reference evaluator and human-selection/promotion workflow,
not an approved optimizer/model or release policy. ADR-013's T-27 runner preserves mock/manual
execution evidence only; it is neither an actual solver/HPC adapter nor a validation verdict.
ADR-014's T-28 result is an explicit non-production extraction/health/comparison profile; it is not
a production acceptance threshold, solver qualification, approval, or release decision.
T-29 adds an explicit governance review request/decision flow: a request pins one immutable
aggregate revision and manifest digest, a domain reviewer decides through an append-only fact, and
changes requested requires a new revision. It does not publish a Release or replace candidate data.
T-06 provides a typed-table
pattern and never a generic revision/EAV content store. Do not add business tables or
production-looking reference implementations before the corresponding decision gates. T-04 does
not implement Material, artifact transfer, lifecycle approval, or export-control
nationality rules. T-15 accepts only versioned generic Job Spec documents; it does not implement
Material, test importer, fitting, production solver exporter, production plugin, or general-purpose
DAG logic.
T-17 registers manifest/schema/supply-chain references and project activation facts only. It does
not implement a public marketplace or claim cryptographic verification without an explicit
authorized verification event. T-18 executes only approved,
digest-pinned packages through Job Spec/Result Manifest. The local subprocess is explicitly
non-production; production requires an attested OCI runtime. T-10 provides authoritative Artifact
finalization, integrity reconciliation, and protected byte streaming, but production S3/credential
composition and T-18 package/input/output policy adapters remain deployment work, so an
unconfigured worker stays idle. T-09 Raw Asset facts remain immutable after T-10 promotion.
T-16 owns transactional outbox/inbox, durable reconciliation scheduling, and safe staging-only
retention cleanup. Final/raw/release objects are never cleanup candidates.
T-13 accepts only owner-attested immutable references and does not expose arbitrary graph writes.
T-14 provides bounded Entity-root traversal and provenance completeness only; it does not provide
arbitrary graph analytics or create a Release resource. T-30 owns release composition and the
release-specific evidence/mapping/review gate that consumes this generic report.
T-05 stores explicit audit facts only; it does not store raw command payloads or secrets and does
not provide an external SIEM/WORM/KMS connector. Production DB grants should omit audit
`UPDATE`/`DELETE`; immutable triggers remain a second enforcement layer.

## Traceability

- Tasks: `T-01`, `T-02`, `T-03`, `T-04`, `T-05`, `T-06`, `T-07` MVP, reference `T-08`, `T-09`, `T-10`, reference `T-11`/`T-12`,
  `T-13`, `T-14`, `T-15`, `T-16`, `T-17`, `T-18`, reference `T-19`, `T-20`, `T-21`, `T-22`, `T-23`, `T-24`, `T-25`, `T-26`, `T-27`, `T-28`, `T-29`, `T-30`, `T-31`, `T-32` MVP, and bounded `T-D03`
- Requirements: `FR-CAT-001`, `FR-DAT-001`, `FR-DAT-006`, `FR-API-001`, `NFR-INT-001`,
  `FR-API-002`, `FR-API-003`, `FR-API-004`, `FR-PLG-004`, `NFR-DR-002`, `NFR-PERF-006`, `NFR-SEC-001`,
  `NFR-SEC-002`, `NFR-SEC-003`, `NFR-SEC-006`, `NFR-AUD-001`, `NFR-AUD-002`, `NFR-MOD-001`,
  `FR-PLG-001`, `FR-PLG-002`, `FR-PLG-003`, `FR-PLG-005`, `FR-DAT-005`, `FR-DAT-007`,
  `FR-DAT-008`, `FR-WF-003`, `NFR-INT-001`,
  `NFR-INT-002`, `NFR-PERF-003`, `NFR-PERF-004`,
  `NFR-REP-001`, `NFR-REP-002`, `NFR-REP-003`, `NFR-SEC-004`, `NFR-SEC-005`, `NFR-MOD-002`,
  `NFR-COMP-001`, `NFR-COMP-002`, `NFR-DOC-001`
- Decisions: `ADR-001`–`ADR-019` (with `ADR-005` as a scope guard)

## T-30 reference Release channel

T-30 adds a bounded Release completeness gate to the product vertical slice. A Release is an
immutable `reference` package created only from one typed Material Model revision, non-production
Solver Card revision, passed Validation Result, approved T-29 Review digest, and provenance
snapshot. The protected API and React workbench expose create/list/read/download operations, and
the package stores explicit component identities and SHA-256 digests. Draft, cross-tenant,
unsupported, approximated, stale, or partially approved inputs are rejected. Supersede/withdraw
and production object-store publication remain outside this reference channel.

## T-31 Release lifecycle and impact

The reference Release channel now keeps lifecycle state in an append-only projection and records
each supersede/withdraw transition as an immutable event. A supersede operation requires an
explicit successor in the same organization/project/classification; a withdraw operation has no
successor. The original Release Manifest and package are never edited or deleted. Authenticated
downloads and explicit consume actions append typed usage facts. The protected impact endpoint and
Release workbench show predecessor/successor links, transition history, usage, and warnings, and
terminal Releases cannot be downloaded or consumed for new work. Automatic PLM replacement and
production publication are not part of this bounded reference slice.

## T-33/T-34 Evidence workbench

The Material State page now keeps the reference raw, normalized, processed, statistical, fitted,
and validation curve views on their source APIs and labels preview sampling separately from
calculation inputs. The Dashboard governance area adds a protected Lineage and Audit Inspector:
reviewers can inspect one immutable provenance Entity, bounded upstream/downstream evidence,
completeness state, and the append-only project audit chain before using the existing Review and
Release commands. Reviewers can resolve a provenance Entity from its typed immutable revision or
artifact reference, or paste an Entity UUID directly. Truncated graphs and invalid audit chains
are shown as warnings; the browser does not reconstruct or silently complete either result. The
organization/project/classification RLS boundary remains authoritative.

## Reference elastoplastic multi-solver slice

The Material State workbench now continues the product path from an actual normalized/processed
tensile Dataset to a solver-neutral, non-production isotropic tabulated-plasticity IR. Reduction
stops at the first global engineering-stress maximum, preserves source and exclusion counts, and
fails closed on non-monotone/softening data instead of repairing it silently. The user must approve
a constant true-stress extension beyond the measured range; mapping reports expose it as
`approximated`.

The same immutable IR and hardening Artifact drive two explicit 2025 `kg_m_s` targets:
OpenRadioss `/MAT/LAW36` + `/FUNCT`, and Abaqus `*DENSITY` + `*ELASTIC` + isotropic `*PLASTIC`.
Both have protected preflight, preview, and download endpoints and byte-exact golden fixtures.
This is not solver execution or qualification: inverse post-necking identification, rate and
temperature dependence, damage/failure, licensed-solver smoke tests, and production release remain
separate domain decisions.

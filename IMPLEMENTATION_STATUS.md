# Implementation Status

Date: `2026-07-27`
Foundation version: `0.30.0`

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
- `T-07` expanded vertical: Material and Material State stable identities separated from immutable typed
  revisions; explicit SI density/Young's modulus/Poisson ratio/optional yield property columns,
  per-value source and applicability; search/detail/history/compare APIs; provenance/audit/lifecycle
  hooks; PostgreSQL composite tenant/classification FKs, indexes, and forced RLS. Typed Process
  Definition, Material Lot/Batch, and State Genealogy identities now have append-only revisions;
  genealogy revisions pin exact State, Process, and Lot revisions with role/scope/material guards,
  protected APIs, and a connected Material State UI.
- `T-39`: explicit Process Run stable identities and immutable revisions pin one exact Process
  Definition and Material State revision plus ordered consumed/produced Lot revisions. Decimal
  quantities preserve original governed units and normalized SI evidence; assessed mass, volume,
  or count balances reject dimension/tolerance mismatches, while `not_assessed` requires a reason.
  Multi-lot split/merge, current-head graph-cycle rejection, tenant/classification isolation,
  forced RLS, immutable child rows, and exact Specimen-to-source-Lot genealogy are enforced in
  PostgreSQL migration 049 and exposed through protected APIs and the Material State workbench.
  Verification passed 561 Python tests, 30 web tests, production frontend build, live PostgreSQL
  constraints/RLS and a Docker browser workflow without skips or browser console errors.
- `T-40`: governed Test Campaign, Instrument, dated Calibration, typed Test Condition Snapshot and
  one-to-one Test Run Context stable identities use immutable revisions in PostgreSQL migration
  050. Campaigns explicitly declare standard designation/edition/conformance or an approved
  deviation; common conditions use typed temperature, humidity, loading-rate, orientation and
  medium columns rather than EAV/JSON. Each Context pins the exact Test Run, Method-backed
  Campaign/Condition, Instrument and Calibration revisions. Service and deferred database guards
  reject cross-scope or mismatched sources, stale/failed calibration, overlapping usable validity
  intervals and revision mutation. Protected APIs and the connected Material State workbench show
  only calibration records valid at the historical Run time. Verification passed 568 Python tests,
  31 web tests, ruff, mypy over 480 source files, architecture/contracts, the production frontend
  build, a fresh PostgreSQL 001--050 migration and a live Docker browser workflow without skips,
  test warnings or browser console errors.
- `T-41`: governed CSV/TSV/XLSX import with immutable source Artifact, explicit `needs_input`
  Preview Report, reusable human-approved typed Profile revisions, exact terminal Import Run and
  separate raw/normalized Dataset revisions. Parser limits, locale/sheet choices, formula/macro/
  external-link rejection and force/displacement geometry requirements are explicit. Migration 051,
  protected API, connected workbench and live PostgreSQL/browser evidence are complete.
- `T-42`: a multi-member Viscoelastic Selection revision pins exact normalized shear-relaxation
  Dataset/Test Run revisions and test temperatures. An immutable Master Curve Plan selects manual
  shift factors or deterministic WLF fitting with a reference temperature. The terminal Run creates
  separate aligned, pointwise-statistics and master-curve Dataset revisions plus ordered shift
  evidence; common log-time interpolation never extrapolates. Explicit migration 052 tables,
  composite tenant keys, forced RLS, immutable/deferred guards, provenance subactivities, protected
  APIs and the connected React workbench expose individual replicates, `n`, sample bands, outlier
  status, shifted curves and the master curve. The reference slice preserves every input and does
  not claim scientific or solver qualification.
- `T-08` reference subset: explicit Specimen, reference uniaxial tensile Test Method, and Test Run
  stable identities with immutable typed revisions; a Test Run pins concrete Specimen/Test Method
  revisions, a State-specific specimen code, optional test temperature/crosshead speed, protected
  APIs, audit/provenance/lifecycle hooks, PostgreSQL tenant/classification FKs, RLS, and immutable
  tables. Campaign, instrument, standard, and production test-method variants remain separate work.
- `T-11` reference subset: an immutable header-only Detection Report is created only from a verified
  UTF-8 CSV Raw Artifact and always remains `needs_input`; a stable Import Mapping identity has
  append-only, human-confirmed typed revisions that pin the exact Detection Report/Raw source and
  mapping digest; a Processing Import Run pins the concrete Test Run and Mapping revisions before
  delegating through the Dataset public application port. Explicit PostgreSQL
  `testing.import_detection_report`, `testing.import_mapping`,
  `testing.import_mapping_revision`, and `processing.import_run` tables enforce source/digest/output
  consistency, RLS, indexes, and append-only transitions. The Material State workbench calls the
  separate detect → approve → import APIs; the bounded `reference_inline` adapter is
  non-production and not a generic production importer/plugin worker.
- `T-12` reference subset: a user-confirmed UTF-8 reference tensile CSV mapping with explicit
  engineering strain/stress columns and limited `1`/`%` and `Pa`/`kPa`/`MPa`/`GPa` units; one stable
  Dataset identity appends raw CSV and normalized SI Parquet revisions without overwriting either;
  typed channel semantics, Raw Asset/Artifact/Test Run concrete references, raw-input provenance,
  bounded curve preview, PostgreSQL constraints/RLS, protected APIs, and deterministic regression
  coverage. The T-11 synthetic header detector/mapping orchestration is now present, while generic
  production importer plugins, arbitrary channel schemas, and other test formats remain separate
  work.
- `T-19` reference subset: an immutable one-member Selection pins one normalized reference tensile
  Dataset revision; a stable Recipe with immutable typed revisions performs only inclusive observed
  engineering-strain crop; a committed Processing Run creates a typed processed Parquet Artifact
  and a separate processed Dataset identity/revision 1. It preserves raw/normalized source bytes,
  records Selection/Recipe/output revision audit facts and concrete Processing provenance, and
  provides protected API plus Material State workbench controls. Multi-input selection, resampling,
  true-strain transforms, and durable Run reconciliation remain outside this subset.
- Reference elastoplastic multi-solver vertical (`T-D03` bounded subset): one concrete normalized
  or processed tensile Dataset revision and one typed Property Set revision produce an immutable
  solver-neutral isotropic tabulated-plasticity IR. The transformation converts engineering data
  only through the first global stress maximum, retains source/pre-yield/post-necking counts and
  necking index, rejects implicit repair/smoothing, and stores the hardening curve as a verified
  Parquet Artifact. A user-approved constant-stress extension remains visibly `approximated`.
  Explicit OpenRadioss 2025 `/MAT/LAW36` + `/FUNCT` and Abaqus 2025 `*DENSITY` + `*ELASTIC` +
  isotropic `*PLASTIC` mappings share the same IR, require the exact mapping-report digest, and
  expose protected preview/download plus byte-exact `.rad`/`.inp` golden regressions. This is a
  non-production monotonic, ambient, rate-independent reference slice without damage/failure or
  solver qualification.
- P2 linear-viscoelastic vertical (ADR-0020 item 3): a polymer/elastomer Material
  revision and one exact Property Set revision can create a stable Material Model identity with an
  immutable typed generalized-Maxwell/Prony revision. Explicit PostgreSQL companion tables store
  one to five ordered shear/bulk ratios and SI relaxation times under composite tenant keys, forced
  RLS, immutable triggers, deferred sum/order/evidence guards, and an exact source-class trigger.
  Protected create/list/read/response APIs and the connected Material State workbench expose manual
  term entry, explicit characterized/not-characterized bulk evidence, and a deterministic
  solver-neutral relaxation preview. Migration 041 adds an immutable Abaqus 2025 time-domain card
  projection with capability manifest, exact preflight acknowledgement, typed card/term tables,
  source-IR equality constraints, `.inp` preview/download, byte SHA-256 and golden regression. The
  Material State UI runs this full IR-to-card flow. Migrations 042--045 additionally preserve
  raw/normalized/processed shear-relaxation Datasets, execute explicit observed-point processing,
  fit a bounded deterministic two-term Prony model with multistart diagnostics, require a human
  Candidate Selection reason, and append the accepted Candidate as schema 1.1 of the same stable
  IR identity before card generation. No solver execution or production qualification is claimed.
- P2 hyper-viscoelastic vertical (ADR-0020 item 4 / ADR-0023 bounded reference scope): an
  explicitly elastomer-classified Material revision and exact Property Set revision create a
  stable Material Model identity with an immutable one-term Ogden plus one-to-five shear-Prony
  revision. Migrations 046/047 add explicit typed IR/card summary and term tables, composite
  tenant/classification foreign keys, forced RLS, immutable triggers, deferred source-term equality
  checks, and no EAV payload. Protected API and the Material State UI provide manual IR entry,
  Abaqus/OpenRadioss target selection, complete mapping status inspection, preflight digest
  acknowledgement, immutable card preview, and `.inp`/`.rad` download. Abaqus incompressibility
  maps exactly through D1=0; OpenRadioss LAW62's fixed ν=0.495 is recorded as `approximated`.
  Byte-exact golden fixtures and live PostgreSQL/API/UI verification cover both targets. Multiple
  Ogden terms, temperature dependence, compressible data, production calibration, and solver
  execution/qualification remain excluded.
- `T-20` reference subset: an immutable Statistical Plan pins exactly two existing one-member
  normalized Dataset Selection revisions from distinct Test Runs; a committed Statistical Run records
  typed QC observations and either fails durably or creates a separate immutable Statistical Result
  revision plus typed Parquet pointwise curve Artifact. Scalar statistics use one peak engineering
  stress per Test Run (`n=2`) with mean/sample SD/median/MAD/IQR/range/CV; curve statistics require
  exact observed engineering-strain grid equality and never align, interpolate, resample, or
  extrapolate. The API, provenance/audit hooks, PostgreSQL constraints/RLS, and Material State
  workbench expose the pinned inputs, QC, result scalar values, and mean curve. Larger groups, CI
  estimation, and approved alignment Processing remain outside this reference slice.
- `T-21` reference subset: an immutable Outlier Detection Plan pins one successful reference-pair
  Statistical Result revision and a declared relative peak-difference threshold. A committed
  Detection Run creates zero candidates below that threshold or exactly two review_required
  candidates at/above it, never chooses a true outlier at n=2, and never excludes data
  automatically. Separate immutable human Assessment identities record retained or
  excluded_from_reference_analysis only against the candidate's exact Statistical Plan revision.
  Typed PostgreSQL tables, composite tenant/classification FKs, forced RLS, append-only guards,
  provenance/audit hooks, contracts, APIs, and the Material State workbench expose append-only
  assessment history and a comparison projection without changing any Raw Asset, Dataset,
  Selection, or Statistics Result or creating a derived Selection.
- `T-21` P0-2 multi-replicate extension: a typed modified-z Detection Plan pins one exact
  multi-replicate Statistical Result revision and evaluates specimen-level peak stress from every
  pinned processed Dataset Artifact. An immutable Run stores zero or more `review_required`
  candidates, with explicit MAD-zero/nonmedian evidence and no infinite score. Separate append-only
  human Assessments drive an immutable calibration input Scope that pins every original
  Dataset/Test Run member plus the exact Candidate/Assessment revision for any decision. At least
  two members remain included; Raw Assets, Datasets, Selections, Results, prior scopes, and
  published outputs are never changed. Migration `20260731_034_p02`, composite tenant and
  classification FKs, forced RLS, append-only guards, API/contracts, React controls, unit/API/web
  regressions, and live PostgreSQL include/exclude verification are implemented. This is a bounded
  non-production review method, not an automatic scientific outlier decision.
- `T-32` MVP subset: React/Vite Material Catalog workbench backed by protected Catalog, Modeling,
  and Exporting APIs; Dashboard, search, Material creation, State and typed Property Set
  entry/revision, revision compare/history, provenance summary, and the reference
  IR→mapping-preflight→Solver Card preview/download workflow. Test upload and tabular column-mapping
  UI remain outside this subset.
- `T-32` extension: the protected Material State screen now drives the reference tensile sequence:
  concrete Specimen selection, reference Method registration, immutable Test Run creation, browser
  multipart CSV upload, explicit column/unit mapping, and raw/normalized Dataset revision/curve
  inspection. It remains deliberately limited to the reference tensile CSV contract.
- `T-32` extension: the same Material State screen now selects two pinned normalized Selections,
  creates a Statistical Plan, commits the reference Statistics/QC Run, surfaces passed/failed QC,
  scalar output, and the immutable mean-curve preview. It does not conceal grid mismatch through a
  browser-side alignment or alter either source revision.
- `T-32` extension: after the reference Statistics Result is visible, the same screen can pin a
  declared outlier-review threshold, commit a zero-or-two-candidate Detection Run, append a human
  assessment, and view the exact-scope history. The UI explicitly states that n=2 cannot identify
  an outlier and that no automatic deletion or source mutation occurs.
- `T-32` extension: the reference Calibration workbench now distinguishes a numerically converged
  Candidate from a human acceptance. It records a required Selection label/reason, displays the
  non-production acceptance status, and provides a separate stale-safe action that appends the
  promoted Material Model IR revision with its typed evidence.
- `T-33` reference workbench slice: the existing Material State workbench now presents raw,
  normalized, processed, statistical, fitted/residual, and validation curves through their
  protected display-view APIs. Every view labels representation, SI units, point counts, and
  deterministic preview sampling; fitted and validation panels retain residual/health status and
  never run fitting in the browser. This remains the bounded reference tensile path, not a generic
  plotting or downsampling service.
- `T-34` reference governance evidence slice: the Dashboard now includes a protected Lineage and
  Audit Inspector alongside the Review and Release workbenches. It loads one immutable provenance
  Entity, bounded upstream lineage or downstream impact, completeness, audit events, and audit
  integrity with explicit truncation/invalid warnings. No graph is reconstructed client-side and
  no audit payload, object key, or tenant scope is exposed; the inspector resolves a typed immutable
  revision/artifact reference to the opaque Entity UUID or accepts that UUID directly.
- Local demo composition: an explicit `CMP_ENVIRONMENT=demo` + `CMP_DEMO_IDENTITY=true` Docker
  Compose profile now runs PostgreSQL, owner-only migration/bootstrap, a non-owner `cmp_app` API,
  worker, React workbench, filesystem object storage, checked reference-plugin asset, and an
  API-driven synthetic seed. The seed creates a Material/State/properties/reference IR/OpenRadioss
  card plus a reference tensile Raw Asset and raw/normalized Dataset revisions, then derives the
  tabulated-plasticity IR and both OpenRadioss/Abaqus elastoplastic cards without direct database
  writes or an authorization/RLS bypass.
- `T-22` reference subset: a stable Material Model identity and immutable reference
  isotropic-linear-elastic IR revision projected from one concrete Property Set revision; explicit
  SI density/Young's modulus/Poisson ratio columns, source-yield disposition, semantic/unit bounds,
  Material→State→Property lineage composite FKs, API/list/history resources, provenance/audit/lifecycle
  hooks, PostgreSQL RLS, and non-production-only contract. Generic model-schema registration and
  production model families remain separate work; the bounded reference Candidate evidence path is
  implemented by `T-24`.
- `T-23` reference subset: a stable Calibration Plan identity with immutable typed revisions that
  pin one normalized or processed tensile Selection revision and one reference linear-elastic
  Material Model IR revision; explicit Young's-modulus bounds/initial value, normalization scale,
  point-weighting, multistart count, and seed; durable append-only Run/Attempt/Candidate records;
  typed observed/predicted/residual Parquet diagnostics Artifacts; protected API/contract and a
  Material State calibration workbench. The bounded analytic `sigma = E * epsilon` WLS evaluator
  is explicitly non-production and R3 only for its recorded reference environment. Uncertainty,
  production optimizer/model choice, and solver validation remain separate work.
- `T-24` reference subset: a stable Candidate Selection identity is fixed to one succeeded
  Calibration Run and has append-only human decision revisions. Each revision pins one converged
  Candidate and Candidate SHA-256 with an explicit reason; numerical convergence and human
  acceptance remain separate. Promotion only accepts the current Selection revision and only while
  the exact Material Model revision evaluated by the Run is still current. It appends a new
  reference IR revision with typed Selection/revision, Candidate/SHA-256, Run, and diagnostics
  Artifact/SHA-256 evidence. Explicit PostgreSQL tables, composite tenant/classification FKs,
  forced RLS, immutable guards, trigger-level evidence checks, protected API/contract, integration
  coverage, and the Material State workbench are implemented. It is non-production and is not a
  formal approval, release, uncertainty, or solver-validation decision.
- `T-25` reference subset: an explicit OpenRadioss 2025 `/MAT/ELAST` exporter for only the
  reference linear-elastic IR and `kg_m_s` units; typed capability/preflight/mapping-report and
  immutable Solver Card identity/revision tables, source-revision FKs, SHA-256 report/card digests,
  provenance/audit/RLS, protected preview/download APIs, and no generic exporter/options payload.
  Production solver qualification, additional targets, transforms, approximations, and release
  approval remain separate work.
- `T-26` reference subset: a byte-exact `.rad` golden fixture plus report-acknowledgement,
  unsupported-target, and text-tamper regressions. A multi-target/version matrix, semantic parser,
  and domain-review golden-update workflow remain separate work.
- `T-27` reference subset: stable Validation Template and Validation Plan identities append typed
  immutable revisions that pin exact Template, reference Material Model IR, OpenRadioss Solver Card,
  and experimental Dataset Selection revisions. A durable Run retains an immutable reference deck,
  stdout/stderr, optional bounded native result, and same-shaped Result Manifest for explicit
  inline-mock or manual-attachment evidence. Explicit PostgreSQL tables/constraints/indexes,
  composite tenant/classification FKs, forced RLS, state/role trigger guards, audit, and provenance
  preserve the evidence tuple. The protected Material State workbench creates/pins/submits/collects
  actual API resources and labels the feature as non-production. No real solver/HPC process,
  numerical-health result, comparison metric, validation pass, approval, or release claim exists;
  those are `T-28` and later work (ADR-0013).
- `T-28` reference subset: a terminal T-27 Result Manifest now produces separate immutable typed
  response-extraction, numerical-health, and experimental-comparison result records/Artifacts.
  Explicit PostgreSQL tables, composite tenant/classification FKs, forced RLS, immutable guards,
  comparison-point rows, provenance, audit, protected evaluate/read/curve APIs, and Material State
  workbench UI retain the frozen input tuple. The first profile validates declared SI response
  units/target/curve health, compares only on the observed experimental strain grid with linear
  interpolation/no extrapolation, uses fixed relative RMSE `0.05`, and records abnormal/unhealthy/
  missing/unit-invalid/alignment-invalid/fit-overlap outcomes as `not_evaluated`. It is reference
  evidence only, not real solver/HPC qualification, production material validation, approval, or
  release policy (ADR-0014).
- `T-29` reference governance subset: immutable `governance.review_request` and
  `governance.review_decision` tables pin an aggregate revision and manifest digest; protected
  request/list/read/decision APIs advance the shared lifecycle event/projection in one transaction.
  The author cannot decide, stale manifest or newer revision approval is rejected, decisions are
  append-only, and `changes_requested` requires a newly created immutable revision. The React
  dashboard includes a digest-pinned request/decision workbench and recent-review list. The MVP
  fixes the required role to `domain_reviewer`; configurable matrices, comments/evidence, legal
  signatures, and Release publication remain outside this task.
- `T-30` reference Release completeness subset: immutable `governance.release`, typed
  `release_manifest`, and digest-fixed `release_artifact` rows with composite tenant/classification
  keys, explicit Material Model/Solver Card/Validation/Review foreign keys, forced RLS, and
  append-only guards. The publish gate requires exact lineage and SHA-256 matches, a passed
  Validation Result, approved T-29 Review digest, non-production card, and no unsupported or
  approximated mapping statuses. Protected create/list/read/download APIs and a React Release
  workbench expose the reference package channel. Supersede/withdraw, production object storage,
  and broader release evidence policy remain outside T-30.
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
- Reference Processing pins exact Selection, Recipe, and normalized Dataset revisions before it
  creates a committed Run. The only reference operation is an inclusive observed-point crop: it
  creates a new processed Dataset identity and never edits raw/normalized revisions, interpolates
  points, or treats a browser curve preview as an artifact.
- The processed Dataset generation activity records the Processing Run, normalized Dataset usage,
  typed Recipe plan, output derivation, and generic revision audit facts in tenant/classification
  scope. If output Dataset commit succeeds but the terminal Run projection fails, the Run remains
  executing for explicit reconciliation rather than being falsely marked failed.
- Reference Statistics first validates that the two immutable Selection inputs resolve to distinct
  Test Runs and reads both normalized Artifacts without changing them. It stores an explicit failed
  terminal Run plus typed QC when an Artifact is unreadable, its point count disagrees with its
  revision, or the observed engineering-strain grids differ; no implicit alignment path exists.
- A successful Statistics Run creates a separate derived typed curve Artifact and immutable Result
  revision before its terminal transition, then records QC in the same terminal transaction. Result
  provenance captures both Selection revisions and the Plan; the two-sample confidence interval is
  explicitly `not_provided_reference_pair` rather than manufactured from point pseudo-replicates.
- Reference Calibration resolves only concrete Selection, Dataset, and Material Model revisions
  through public bounded-module ports, verifies shared Material State and tenant scope, and records
  a durable terminal failure if its typed curve Artifact cannot be read. Its analytic bounded WLS
  evaluator writes a separate typed diagnostics Artifact and immutable Candidate per recorded
  multistart Attempt; it never changes source curves or the IR it evaluated.
- Candidate Selection requires a succeeded Run and exact converged Candidate digest, retains human
  reason/history separately from convergence, and can promote only the current Selection revision
  against the still-current evaluated IR revision. The new IR revision records concrete Selection,
  Candidate, Run, and diagnostics Artifact evidence; all prior IR/Candidate/Run revisions remain
  immutable.
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

Normal command: `make ci`. This Windows environment has no native `make`, so the exact underlying
`scripts/ci.sh` target was invoked through Git Bash with the locked local environment. The
PostgreSQL integration suite additionally requires `CMP_TEST_POSTGRES_DSN`.

```text
Ruff: passed
mypy strict: passed (374 source files)
Architecture rules: passed
Contract lint: passed
OpenAPI compatibility: passed
Alembic `upgrade head --sql`: passed
PostgreSQL marker suite: 62 passed, 0 skipped, 0 failed
CI-equivalent pytest with the same disposable PostgreSQL DSN: 452 passed
Root web check: build passed; Vitest: 21 passed
Live P0-1 environment: Docker Engine 29.6.1, Compose 5.3.0, PostgreSQL 16, migration/bootstrap,
  non-owner API, worker, web, reference-plugin check, and synthetic seed all completed successfully.
  The disposable `postgres-test` profile supplied the owner DSN without weakening the
  SCRAM-authenticated demo database. Browser smoke verified the seeded Material, Material State,
  typed properties, normalized tensile Dataset, tabulated-plasticity IR, and OpenRadioss/Abaqus
  card previews and downloads.
T-11/T-19/T-21/T-D03 have unit, API integration, migration SQL, and browser-workbench regression
coverage.
Online Alembic `base -> head -> base`, forced-RLS integration, and the full CI-equivalent suite now
run against disposable PostgreSQL. This live pass exposed and fixed migration downgrade ordering,
composite-key, finite-value, SQL construction, authorization-capability, and typed-query defects
that offline SQL rendering could not prove.
```

## Intentionally absent

- Public role-management API/UI and deployment-specific DB role/secret provisioning
- Export-control nationality/compartment policy (`OQ-SEC-002`)
- Full Process Run input/output graphs, lot split/merge and multi-lot acceptance; richer typed
  property/curve families; Test Campaign/Instrument records; production importer plugin approval;
  arbitrary channel schemas; and non-reference Dataset channels
- General multi-member Selection/filter semantics, arbitrary recipe graphs, durable Processing Run
  reconciliation, inverse post-necking identification, calibration-specific outlier scope,
  larger-replicate/CI statistics, and production nonlinear calibration
- Production release publication, external PLM replacement, and release-specific evidence policy
  beyond the bounded T-30/T-31 reference channel
- Production S3 adapter, KMS/object-lock/versioning/replication provisioning, external event
  transport credentials, and deployment runner credentials
- T-17 authoritative package-Artifact admission, T-18 materializer/committer deployment wiring,
  and signature/SBOM/malware/vulnerability verification automation
- A selected production OCI runtime implementation and production package/image admission policy
- Production plugins
- External audit root signer, SIEM/WORM connector, retention/legal-hold policy, and deployment
  service-principal scheduling for periodic sealing
- Production fitting algorithms, production solver cards/targets, or qualified validation
  thresholds; the implemented linear/tabulated IRs and OpenRadioss/Abaqus cards are bounded
  reference outputs and are not production-qualified
- Production web identity/session integration, external demo IdP deployment, and a production
  Compose/deployment profile; the checked-in demo issuer is explicitly local-only

## Next gate

**Updated 2026-07-18 (superseded below):** the reference Test/Dataset, committed Processing, exact-grid
two-sample Statistics/QC, and append-only outlier-review slices are implemented. The completed
reference Material → Property Set → IR → OpenRadioss Card path remains the product's
second-priority CAE-use vertical slice; this T-21 work supports the separate Test Data → Statistics
demonstration and does not replace it. T-11 now makes the reference CSV path explicitly
detect → human mapping approval → pinned Import Run → immutable Dataset revisions. The next requested
sequence is T-23/T-24 reference calibration and candidate selection, then T-27/T-28 validation. Any
expansion beyond the existing exact linear-elastic OpenRadioss mapping also requires a documented
target/model mapping decision; it must not be silently inferred.

**Update 2026-07-19:** T-23 is now implemented as a non-production reference Calibration
Plan/Run/Attempt/Candidate diagnostics slice. It demonstrates `Selection revision -> Material
Model IR revision -> Candidate diagnostics` without mutating the source Dataset or IR. The next
requested work is T-24 human candidate selection and append-only IR promotion, followed by T-27/T-28
validation. Any expansion beyond the exact reference linear-elastic OpenRadioss mapping requires a
documented target/model decision and must not be silently inferred.

**Update 2026-07-20:** T-24 now completes the bounded reference path `Calibration Run ->
converged Candidate -> human Candidate Selection revision -> appended Material Model IR revision`.
The workbench and API make the human acceptance reason explicit, retain typed evidence, and reject
superseded Selection revisions or stale evaluated IR heads. The next requested work is `T-27`, then
`T-28`: a narrow non-production Validation Template/Runner slice followed by result extraction,
numerical-health, and experimental-comparison evidence. Neither step may imply a production solver,
HPC integration, approval, or release policy without a separate documented decision.

**Update 2026-07-21:** T-27 now completes the evidence-only boundary
`Validation Template revision -> Validation Plan revision -> deck -> Run -> Result Manifest`.
Both mock and manual branches retain the same immutable Artifact/provenance shape; the mock runner
does not execute a solver and `normal` termination is not a validation pass. The next requested
work is `T-28`: bounded native-result extraction, numerical-health, experimental comparison, and
an explicit non-production verdict that must keep abnormal/no-output runs `not_evaluated`.

**Update 2026-07-22:** T-28 now completes that bounded non-production interpretation path:
`Result Manifest -> typed SI response extraction -> numerical-health report -> observed-grid
comparison -> immutable Validation Result`. The API/workbench expose the extracted evidence,
health, holdout-independence, metric, threshold, and curve preview. The next delivery work is
T-29 review/lifecycle and T-30 release evidence gating; a real solver/HPC adapter, production
threshold, multiple solver/template support, and domain qualification remain explicit decisions.

**Update 2026-07-23:** T-29 now completes the bounded governance path:
`draft revision -> review request pinned to manifest digest -> separated reviewer decision ->
approved/changes_requested lifecycle projection`. Review facts and decisions are immutable,
tenant-scoped, and transactionally linked to lifecycle events. A stale digest, newer revision,
author-only decision, or repeated decision is rejected; changes requested cannot be resubmitted
without a new revision. The next delivery work is T-30 Release completeness and evidence gating.

**Update 2026-07-24:** T-30 now completes the bounded reference Release path:
`approved candidate -> typed completeness/integrity gate -> immutable Release Manifest ->
reference package search/download`. The gate binds one Material Model, Solver Card, passed
Validation Result, approved Review digest, and provenance snapshot by explicit IDs and SHA-256
digests; cross-tenant, stale, draft, unsupported, approximated, or partial inputs fail closed.
The API and dashboard expose the package, while supersede/withdraw and production publication
remain T-31+ scope.

**Update 2026-07-25:** T-31 now adds an append-only Release lifecycle projection and transition
event relation. A released package can be explicitly superseded by a same-scope successor or
withdrawn; the immutable Release, Manifest, and package rows remain untouched. Download and
explicit consume operations append typed usage facts, while the impact API reports predecessor,
successor, transition history, usage, and terminal warnings. The React Release workbench exposes
the lifecycle controls and prevents terminal download. Automatic PLM replacement, production
publication, and solver reruns remain outside this bounded reference slice.

**Update 2026-07-25:** T-33/T-34 now make the workbench path reviewable end to end. Curve panels
show raw/processed/statistical/fitted/validation evidence with explicit units and sampled-preview
labels, while the Dashboard Lineage and Audit Inspector reads bounded provenance paths,
completeness, append-only events, and chain integrity next to the existing Review/Release commands.
The next gate is a live PostgreSQL-backed demo/test run and then T-35/T-36 operational observability
and restore drills; generic importer formats, production solver/HPC execution, and external release
publication remain separate decisions.

**Update 2026-07-26:** the product vertical now performs actual bounded tensile-data reduction and
multi-solver card extraction. A normalized/processed engineering curve is converted only through
its first maximum stress to true stress and true plastic strain; source/excluded counts and the
necking index remain immutable evidence. The resulting IR drives OpenRadioss LAW36 and Abaqus
isotropic-plasticity cards through explicit preflight, preview, and download APIs and the Material
State workbench. The constant post-necking extension is `approximated`, never silently exact. Real
solver execution, inverse post-necking identification, rate/temperature dependence, damage/failure,
and production qualification remain separate decisions.

**Update 2026-07-27:** P0-1 is complete on a live Docker/PostgreSQL stack. Migration/bootstrap/seed,
non-owner API/worker/web, protected local-demo identity, PostgreSQL marker tests, CI-equivalent tests,
and browser smoke all passed. The online downgrade cycle and forced-RLS paths found defects that now
have regression coverage. The next implementation wave is P0-2 multi-replicate
Selection/processing/statistics/QC/outlier scope and its connected curve UI.

**Current delivery order (ADR-0019, accepted 2026-07-14):** all existing foundation and vertical
results above remain in place. Remaining work is now sequenced as follows:

1. `P0-1` — **complete**: Docker/Compose, migration/seed, live PostgreSQL/RLS integration,
   skip-zero marker suite, CI-equivalent suite, and protected browser smoke are recorded above.
2. `P0-2` — **complete**: expand T-19/T-20/T-21 from one/two-curve reference subsets to immutable multi-member
   repeat-test Selection, explicit processing/alignment, specimen-level statistics/pointwise bands,
   QC/outlier assessment with calibration-specific scope, and connected curve UI.
3. `P1` — **complete for the bounded non-production reference scope**: add the reference Voce/SciPy nonlinear calibration path, nonlinear
   Candidate diagnostics and human selection, calibrated solver-neutral IR plus explicit tabulated
   projection, and existing OpenRadioss/Abaqus preflight/preview/download. Add solver-independent
   material-model and disjoint-holdout validation; do not claim production model/optimizer approval.
4. `P2` — Process/Lot/Batch and broader domain expansion, production plugins/decisions, actual
   OpenRadioss/Abaqus execution qualification and HPC, observability, backup/restore, performance,
   security, and external release hardening.

Product-owner direction explicitly defers actual solver execution verification to P2. Existing
T-27/T-28 mock/manual evidence and immutable results are retained; they are neither deleted nor
reclassified as solver qualification. The immediate implementation gate is now the explicitly
documented `P2` decision and hardening wave.

Prior planning note (superseded): the first vertical flow was described as a non-production reference subset:
Material → State → typed Property Set → frozen reference IR → explicit OpenRadioss mapping report
→ immutable card preview/download. The next contiguous product step is the Test/Dataset vertical
slice: Specimen/Test metadata, reference tensile CSV upload, column/unit mapping, raw and
normalized curve viewing, and a concrete Material link. T-30 still owns Release creation and
evidence policy; T-17/T-18 production Artifact composition and release-specific retention/backup
policy are not implied complete.

## P0-2 progress (2026-07-28)

The first P0-2 increment is implemented. A typed `reference_tensile_replicate_set` Selection
revision pins 2..50 ordered normalized/processed Dataset revisions from distinct concrete Test Run
revisions and one Material State. Membership is stored in
`datasets.dataset_selection_member` with explicit foreign keys, uniqueness constraints, forced
RLS, immutable-row protection, and a deferred member-count guard; it is not JSON or EAV.

The API supports create/list/get/append-revision. The Material State tensile workbench supports
member selection and a common-scale overlay of pinned curves. Synthetic demo data now creates
three independent Test Runs/Datasets and one replicate Selection. Legacy one-member Selections are
backfilled without changing their revision hashes.

The second P0-2 increment is also implemented. Migration `20260729_032_p02` adds a typed
`reference_tensile_common_grid_linear` Recipe revision with explicit start/end/count,
`intersection` domain, `piecewise_linear` interpolation, and `reject` extrapolation columns and
database constraints. A grouped execution pins the multi-member Selection and Recipe revisions,
then creates one immutable `processing_run`, derived Artifact, and separate processed Dataset
identity/revision per member. The API and Material State workbench expose the policy, exact grid,
batch result, processed overlays, and concrete output revision links. No source revision is edited
and no statistical calculation performs hidden alignment.

The third and fourth P0-2 increments implement the complete persisted multi-replicate
Statistics/QC slice. The typed, solver-neutral kernel treats the 2..50 Selection members as the
specimen-level sample, requires already processed exact grids, and calculates peak-stress scalar
and pointwise mean, sample standard deviation, median, MAD, IQR, min/max, coefficient of variation,
and two-sided 95% Student-t mean intervals. Migration `20260730_033_p02` adds explicit typed Plan,
Plan Revision, Run, ordered Run Member, Result, Result Revision, and QC Observation tables with
foreign keys, constraints, indexes, forced RLS, immutable revision guards, and terminal Run-state
guards; no JSON/EAV storage is used.

The protected API creates/lists/reads Plans, commits and reads Runs, and reads immutable Results and
bounded pointwise curve previews. Provenance records the concrete Selection/Plan usages, Result
derivation, and `statistics.reference_tensile_replicates` generation activity. The connected web
flow explicitly pins alignment outputs as a new immutable Selection before creating a Plan; it then
shows exact members, QC, peak scalar statistics, observed range, mean, and Student-t 95% CI band.
Statistics performs no interpolation or hidden alignment, and the earlier pair workflow remains
unchanged.

P0-2 is complete through multi-member outlier evidence, append-only human assessment, and an
immutable calibration-specific input Scope. The bounded P1 wave described below subsequently added
multi-curve Voce calibration, Candidate diagnostics and selection, calibrated IR, two-solver card
generation, and solver-independent holdout validation. No automatic source mutation or exclusion
is permitted.

Verification includes a live non-owner Docker/PostgreSQL execution that committed three independent
31-point processed Dataset revisions in one batch. Unit tests cover interpolation, common-domain,
monotonicity, and extrapolation rejection; API integration covers explicit policy and grouped output;
migration regression covers typed columns, guards, RLS-compatible provenance finalization, and the
absence of JSONB/EAV. Migration 033 was also exercised as fresh upgrade, downgrade to 032, and
re-upgrade against disposable PostgreSQL 16. Updated full-suite counts are recorded after the
P0-2 persistence gate is merged.

## P1 completion (2026-08-03)

P1 is complete for the explicitly non-production reference scope. The platform consumes an
immutable calibration input Scope containing multiple preserved processed tensile curves, runs a
bounded deterministic Voce/SciPy `least_squares` calibration, stores every Attempt/Candidate and
diagnostic, requires append-only human Candidate selection, and promotes the accepted Candidate to
a calibrated solver-neutral Material Model IR. A separate frozen 51-point tabulated projection
feeds the existing OpenRadioss LAW36 and Abaqus elastoplastic exporters, including mapping preflight,
preview, Artifact-backed download, and deterministic regression fixtures.

Migration `20260803_037_p1` and the connected API/workbench add solver-independent holdout
validation. One immutable Plan pins the calibrated IR and an independent tensile Dataset. Both the
Dataset revision and Test Run revision must be disjoint from every calibration Scope member. The
Result retains exact observed/predicted/residual points, RMSE, relative RMSE, source/comparison
Artifact digests, full calibration lineage, audit, and provenance. The fixed `0.05` reference
threshold and `solver_execution=not_used` marker prevent this evidence from being mistaken for
production or solver qualification. The demo seed now provides three calibration curves and a
fourth disjoint holdout curve.

The completion gate passed 497 Python tests and 24 web tests, plus ruff, mypy, architecture,
OpenAPI contract lint/compatibility, TypeScript, and production web build checks. A live non-owner
Docker/PostgreSQL run also persisted both calibrated OpenRadioss and Abaqus cards and a four-point
disjoint holdout result with comparison Artifact/provenance evidence.

Remaining P2 work is deliberately not implemented: broader Process/Lot/Batch/Campaign/Instrument
domain depth and importer/property families; approved production constitutive models, objectives,
bounds and scientific fixtures; actual OpenRadioss/Abaqus data-check/execution, HPC adapters,
solver-output parsing and qualification; and observability, disaster-recovery, performance,
security, external release and connector hardening. Solver execution validation remains excluded by
product-owner direction until that P2 scope is explicitly resumed.

## P2 product vertical started (2026-07-15)

ADR-0020 changes the next execution order without discarding the completed foundation. Material
revision schema v2 adds a governed class for workflow guidance; legacy v1 revisions remain
unchanged and read as `unclassified`. The user-facing README now leads with Material management,
test/processing, IR and card workflows while the detailed engineering runbook lives in
`DEVELOPMENT.md`.

The ordered P2 delivery was: Steel elastoplastic regression protection; linear Prony IR and
Abaqus viscoelastic card; shear-relaxation import/processing/calibration; Ogden-Prony Abaqus and
OpenRadioss LAW62 cards; then Process/Lot/Batch genealogy. These are reference/non-production
capabilities until domain-approved schemas, numeric fixtures and mappings are available. Actual
solver execution validation remains excluded.

### Shear-relaxation Dataset increment

Migration 042 and the Dataset/Testing applications now implement the data-ingress half of P2 item
3. A declared `reference_shear_relaxation` Test Method and Test Run pin exact Specimen and Material
State revisions. The browser uploads a UTF-8 CSV as an immutable Raw Asset, requires explicit time
and shear-modulus columns and units, then creates separate raw and normalized Dataset revisions.
Normalized points are stored as a typed SI Parquet Artifact (`s`, `Pa`); the original units remain
in the revision. PostgreSQL uses dedicated non-EAV identity/revision tables, composite tenant/source
foreign keys, RLS, immutable revision triggers, and indexes. Raw-Asset usage is recorded in the
Provenance graph. The Material State screen renders a bounded deterministic curve preview.

Migration 043 completes the explicit Processing half. An inclusive observed-point time crop is
stored as a stable Recipe plus immutable revision; a committed Run pins exact normalized Dataset
and Recipe revisions and produces a verified derived Parquet Artifact. Its output is revision 1 of
a separate processed Dataset identity rather than a mutation of the imported Dataset. PostgreSQL
enforces typed columns, composite tenant FKs, normalized-input and terminal-transition guards,
forced RLS, and immutable Recipe revisions. Provenance records the source Dataset and Recipe as
inputs to the concrete Run. The Material State screen exposes time bounds, states that no
interpolation occurs, and previews the processed curve.

Live Docker/PostgreSQL verification on 2026-07-16 migrated to
`20260809_043_shear_proc` and committed a 6-point normalized input to a 3-point processed output
from `1 s` through `100 s`, with two provenance usages. Backend unit, contract, API, offline
migration, frontend test, and frontend build gates passed for this increment. The CI-equivalent
gate completed with 527 Python tests and 27 Vitest tests, plus a successful production web build.

Migration 044 implements the next bounded calibration increment. A revisioned Plan pins one exact
processed shear-relaxation Dataset revision and one exact baseline linear-Prony IR revision. The
reference two-term generalized-Maxwell evaluator fixes the baseline instantaneous shear modulus,
fits bounded total shear ratio, fast-term fraction and two separated log-time constants, and runs
deterministic SciPy TRF multistart with PCG64. Runs, Attempts and Candidates use explicit non-EAV
tables; observed/predicted/residual points are immutable Parquet Artifacts. Candidate objective,
RMSE, mean residual, convergence reason, evaluation counts, bound warning, Jacobian-rank
identifiability and explicit unassessed uncertainty are returned by the API and rendered in the
Material State workflow. No Candidate is selected or promoted automatically.

Live Docker/PostgreSQL verification migrated to `20260810_044_prony_cal`, retained all six observed
points in a separate processed Dataset, executed four deterministic starts, persisted four
Candidates and read back six diagnostic rows for the displayed Candidate. The successful live Run
is `40192c69-7491-4b68-828c-f76e5f491280`. The fixture reached the slow-time lower bound, and that
fact remains visible as a warning rather than being silently accepted.

The repository `make ci` gate passed with 467 Python tests and 27 Vitest tests; its 64 PostgreSQL
cases were expected skips because that command had no DSN. The same PostgreSQL marker suite was
then run against the isolated Compose PostgreSQL 16 service with `CMP_TEST_POSTGRES_DSN`, producing
64 passed, zero skipped and zero failed. Type checking covered 450 source files; architecture,
contract lint/compatibility and the production frontend build also passed.

Migration 045 completes P2 item 3. A human explicitly selects one converged Candidate, records a
reason, and creates an immutable Candidate Selection revision. Promotion uses compare-and-swap on
the exact baseline revision and appends schema 1.1 to the same stable Material Model identity. The
new IR pins the Selection, Run, Candidate and diagnostics Artifact digests. PostgreSQL validates
the exact tenant-scoped lineage and prevents the earlier linear-elastic Candidate guard from
handling the distinct Prony evidence kind. The connected UI requires an explicit Review action;
it never defaults to the lowest objective Candidate.

Live Docker/PostgreSQL verification selected Candidate
`0b8bd19e-5a0c-4ef2-923f-bec290f19c0f`, retained its visible slow-time lower-bound warning, and
promoted model `5ffc8864-e995-49d7-8fc9-f421ec48d45f` from revision 1 to revision 2
`4241a279-9e92-40df-ba7c-54c42d9cb75c`. Abaqus preflight reported density, elasticity and shear
Prony terms as exact, bulk/temperature as not applicable, and SI target transformation as
transformed. Solver Card `8c1569a4-b55a-4be2-969c-4c8abea1a656` pins that promoted revision;
preview and downloaded bytes matched SHA-256
`fdb9b4bdbb66e706d0350185940dbbfe9be4fe42d1156178fcee930a5638a1ce`.

The CI-equivalent gate passed with 471 Python tests and 27 Vitest tests, plus ruff, mypy over 456
source files, architecture rules, contract lint/compatibility and the production frontend build.
The isolated Compose PostgreSQL 16 marker suite then passed 64/64 with zero skips or failures.

At that increment boundary, the ordered next work was P2 item 4 Ogden-Prony/Abaqus/OpenRadioss
LAW62 and P2 item 5 Process/Lot/Batch genealogy. Both bounded reference slices are now complete as
recorded below. Actual solver execution qualification remains excluded by product-owner direction.

### Steel elastoplastic routing increment

The existing tabulated-plasticity and calibrated Voce paths now require the exact source Material
revision to be classified as `metal`. Modeling resolves that pinned revision through the Property
Set and Material State chain; an application guard rejects non-metal input before reading curve
bytes, and migration 039 adds a PostgreSQL insert trigger for the same invariant. The frontend
shows the elastoplastic workbench only for the class pinned by the State and offers explicit
append-only State rebase guidance when the Material head changed. The demo seed reclassifies and
rebases legacy demo Material/State/Property revisions through protected APIs. Existing
OpenRadioss LAW36 and Abaqus golden outputs are unchanged.

### Ogden--Prony and Catalog genealogy completion

Migrations 046/047 complete the bounded P2 item 4 reference vertical. An elastomer-classified
Material State and exact Property Set revision create a typed one-term Ogden plus one-to-five
shear-Prony IR. Abaqus 2025 and OpenRadioss 2025 are separate explicit targets with immutable
mapping reports and card revisions. Abaqus uses incompressible `D1=0`; OpenRadioss LAW62 records
its fixed `nu=0.495` conversion as `approximated`. Both cards have deterministic golden bytes,
preview/download APIs, and connected UI. Linear-Prony is never silently routed to LAW62.

Migration 048 completes the bounded P2 item 5/T-07 genealogy subset. Process Definition and
Material Lot/Batch stable identities each append immutable typed revisions. A State Genealogy
revision pins the exact Material State revision and optional manufacturing, heat-treatment, and
Lot/Batch revisions under composite organization/project/classification foreign keys, forced RLS,
immutable triggers, and deferred semantic guards. The Material State screen creates and revises
these links without replacing historical facts. Full Process Run inputs/outputs, split/merge, and
multi-lot acceptance remain future T-07 depth.

### Live user E2E evidence (2026-07-16)

The Compose demo was exercised against PostgreSQL 16 through the protected API and connected React
workbench. A new polymer Material was created and carried through:

`Material/State/Property Set -> Specimen/Test Run -> immutable CSV Raw Asset -> normalized Dataset
-> explicit crop Processing Run -> bounded five-start Prony Calibration -> reviewed Candidate
Selection -> IR revision 1 to 2 promotion -> Abaqus mapping preflight -> immutable .inp card`.

The Processing Run succeeded with six normalized and five processed points. All five Calibration
Candidates converged; the reviewed Candidate retained objective, RMSE, residual Artifact and bound
diagnostics. The promoted IR kept the same stable Material Model identity and a new revision ID.
The downloaded 418-byte Abaqus card returned HTTP 200 with a filename-bearing attachment header;
its SHA-256 exactly matched the stored card digest. The card contains `*DENSITY`, `*ELASTIC`, and
`*VISCOELASTIC`. Browser evidence also rechecked the Ogden--Prony LAW62 preview and exact-revision
Process/Lot genealogy. See `docs/15-demo/user-e2e-evidence-2026-07-16.md`.

## Current remaining work after the bounded P2 verticals

The user-visible reference flows requested by ADR-0020 are implemented. Remaining work is not a
new foundation rewrite; it is production depth and additional vertical coverage:

1. **Catalog/Test depth:** Process Run inputs/outputs, lot split/merge and multi-lot acceptance;
   Test Campaign, Instrument/calibration, standards, condition snapshots, and Specimen source-lot
   genealogy.
2. **Real data breadth:** governed property/curve families, production importer packages and
   mapping approval for selected laboratory formats, arbitrary channel schemas, richer replicate
   statistics, and viscoelastic alignment/master-curve/temperature-shift processing decisions.
3. **Scientific qualification:** domain-approved steel, linear-viscoelastic and hyper-viscoelastic
   schemas, parameter bounds, objective profiles, reference curves, tolerances, uncertainty and
   identifiability policy. The current Voce, two-term Prony, and one-term Ogden paths remain
   reference/non-production.
4. **Exporter productionization:** official version matrices, semantic card parsers/data-checks,
   approved golden fixtures and release policy. Actual solver execution/qualification remains
   explicitly excluded by product-owner direction.
5. **Operations and governance hardening:** production identity/role administration, object-store
   object lock/KMS/retention, package signing/SBOM/scanning, T-35 observability, T-36 restore drill,
   T-37 release-quality evidence, T-38 performance/security acceptance, and external PLM/CAE
   connectors. T-47 must also reconcile and expose an immutable derived output if a later step of a
   multi-output Run fails; committed evidence is never deleted or hidden, but failed Runs must not
   leave it operationally undiscoverable.

## Production-pilot execution baseline (2026-07-16)

ADR-0025 through ADR-0027 and backlog T-39 through T-47 now turn the remaining product depth into a
resumable implementation program. The program preserves migrations 001--048 and prioritizes the
user-visible Material/Test -> Dataset/Processing -> Calibration -> neutral IR -> Abaqus/OpenRadioss
Card -> Bulk Export workflow. Actual solver execution remains excluded. Domain-unapproved numeric
profiles and mappings remain visibly `reference/unapproved`.

The first documentation increment is complete. Official research now records MCalibration only as
a Processing/Modeling/Validation reference, not a product boundary. The stale pre-implementation
design index and README Candidate-selection claims are corrected. Requirements, domain, IR, API,
fitting and test documents now define iterative promotion evidence, governed CSV/TSV/XLSX intake,
immutable Bulk Export Bundles and the user-guide/screenshot gate. A Korean task-oriented guide
covers current Steel, Polymer and Elastomer workflows and reuses nine dated E2E screenshots through
an explicit manifest; future GUI changes must update the affected guide and capture evidence.

Verification: the guide link/manifest check validated nine documents and seven images. With the
disposable PostgreSQL 16 DSN enabled, the CI-equivalent suite passed 553 Python tests with zero
skips or failures, 28 Vitest tests, ruff, mypy over 469 source files, architecture and contract
checks, OpenAPI compatibility and the production Vite build. T-39 then added migration 049 and the
connected Process Run/Lot/Specimen source workflow. T-40 added migration 050 and the exact
Campaign/Instrument/Calibration/Condition execution-context workflow. T-41 adds migration 051 and
an end-to-end governed CSV/TSV/XLSX intake: immutable source Artifact, explicit `needs_input`
preview, human-approved reusable Import Profile revision, terminal exact-pinned Import Run and
separate raw/normalized SI Dataset revisions. CSV/TSV locale and XLSX sheet/formula/macro/external
link/decompression constraints are explicit; force/displacement derivation requires pinned
   geometry. T-42 then adds exact multi-temperature replicate selection, explicit common-domain
   alignment/statistics, manual or deterministic WLF shift evidence and separate immutable master-
   curve output. T-43 then adds typed scientific profiles and bounded multi-test Ogden fitting;
   T-44 adds append-only human Candidate promotion and T-45 Bulk Export is the next unit.

T-41 verification on 2026-07-16: migration 051 completed an upgrade/downgrade/re-upgrade round trip
on disposable PostgreSQL 16. The CI-equivalent gate passed 576 Python tests with zero skips or
failures, 32 Vitest tests, ruff, mypy over 486 source files, architecture and contract lint,
OpenAPI compatibility and the production Vite build; clean npm install/audit reported zero
vulnerabilities. Live protected API execution imported nine synthetic tensile rows into distinct
raw and normalized revisions, and the connected browser workbench reported no warning/error.

T-42 verification on 2026-07-16: the protected Docker/PostgreSQL workflow processed six synthetic
public relaxation curves at three temperatures into 606 aligned rows, 303 statistical rows and 101
master points. WLF evidence recorded the reference and fitted shifts, while the browser rendered
the shifted replicates, `n=2`, sample standard-deviation band and master curve without console
warnings/errors. Migration 052 completed a fresh 001--052 upgrade plus 052--051--052 round trip on
PostgreSQL 16. The CI-equivalent gate passed 585 Python tests with zero skips/failures, 33 Vitest
tests, ruff, mypy over 497 source files, architecture/contract/OpenAPI compatibility and the
production frontend build; npm audit reported zero vulnerabilities.

## T-43 scientific profiles and multi-test Ogden fitting (2026-07-16)

Foundation version `0.29.0` adds migrations 053 and 054 without rewriting prior revisions.
Migration 053 stores typed Steel Voce, Polymer linear-Prony and Elastomer Ogden--Prony scientific
profile identities/revisions with forced RLS; it does not use JSON/EAV and refuses direct
`domain_approved` self-assertion. Migration 054 stores typed exact-revision Ogden Plans and ordered
calibration/holdout members, terminal Runs, multistart Attempts/Candidates, mode objectives,
convergence, rank/condition, covariance/95% CI or explicit not-estimable state, warnings and exact
diagnostics Artifact references. The same migration expands the typed Test Method constraint with
separate reference planar- and biaxial-tension methods so multi-mode evidence is not mislabeled as
uniaxial execution.

The bounded numerical adapter consumes governed normalized engineering-strain/nominal-stress
curves and supports public one-term incompressible Ogden uniaxial, planar and equibiaxial nominal
responses. Weighting is normalized point → curve → mode; PCG64 starts and SciPy TRF execution are
deterministic. The React workbench is connected to the real API and database and exposes exact
Dataset selection, calibration/holdout roles, mode/curve weights, Candidate comparison,
uncertainty and fitted/residual plots. Single-mode and missing-holdout evidence remain allowed but
visibly warned. No solver is run, no Candidate is automatically accepted and no baseline or source
revision is overwritten. T-44 adds the separate human Candidate selection and repeated append-only
IR promotion gate described below.

Verification: analytic limit/recovery/weight/rank/holdout/deterministic-Parquet tests, protected API
tests, PostgreSQL 001→054→053→054 migration round trip, and a live PostgreSQL
upload→governed normalized Dataset→Plan→multistart fit→Candidate/Artifact persistence test all
pass. Project RLS and immutable-row rejection are exercised. The CI-equivalent gate passed 600
Python tests with zero skips/failures, 35 Vitest tests, ruff, mypy over 512 source files,
architecture/contract/OpenAPI compatibility and the production Vite build; npm audit reported zero
vulnerabilities. Browser verification found no console errors.

## T-44 iterative Ogden promotion evidence (2026-07-16)

Foundation version `0.30.0` adds migration 055 without rewriting any T-43 Plan, Run, Candidate,
diagnostics Artifact, Material Model revision, Solver Card or Release. The migration adds explicit
`ogden_candidate_selection`, `ogden_candidate_selection_revision` and
`ogden_promotion_evidence` tables; no JSON/EAV payload is used. Composite foreign keys and forced
RLS bind every row to one organization/project/classification. PostgreSQL validates succeeded Run,
converged Candidate, candidate/diagnostics digests, exact prior model revision, schema 1.1 owner,
and fitted `mu`/`alpha`. Unique constraints reject Candidate or Selection reuse, and immutable-row
triggers reject updates and deletes.

The protected API records a mandatory human Selection reason and requires the current Material
Model strong `If-Match` before promotion. A successful decision keeps the stable Material Model
identity and appends r2/r3 with one revision-owned evidence record; prior evidence is read through
the revision chain and is never copied into a mutable collection. The React workbench exposes the
human gate, promotion reason, 412 stale-head behavior and newest-first IR history. The existing
Abaqus Ogden and OpenRadioss LAW62 preflight/card paths immediately use the new current revision,
while cards already generated from prior revisions retain their payload and SHA-256. No solver is
executed and no Candidate is automatically accepted.

Verification includes 001→055 and 055→054→055 PostgreSQL 16 migration runs, exact-evidence API
tests, stale ETag rejection, browser selection/promotion/history coverage and a semantic regression
that proves a later IR promotion cannot alter a prior Solver Card payload or digest. The opt-in
`uv run python scripts/seed_ogden_calibration_demo.py --promote` helper creates only public
synthetic evidence and verifies any existing card digests during a local repeated-promotion round.

T-44 verification on 2026-07-16 passed fresh 001→055 and 055→054→055 PostgreSQL 16 migration
runs. The CI-equivalent gate passed 606 Python tests with zero skips or failures, 35 Vitest tests,
ruff, mypy over 518 source files, architecture and contract lint, OpenAPI compatibility and the
production Vite build; clean npm install/audit reported zero vulnerabilities. Two live protected
promotion rounds produced r2 then r3 on one stable model identity and verified three prior Solver
Card revision/digest pairs unchanged. Connected-browser verification recorded the three-revision
history and cards with no warning or error logs.


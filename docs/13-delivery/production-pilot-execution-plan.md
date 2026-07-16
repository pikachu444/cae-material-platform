# Production-pilot 실행 계획

기준일: 2026-07-16

결정: ADR-0025, ADR-0026, ADR-0027

범위: T-39~T-47

## 1. 최종 목적

현재 구현된 foundation과 reference vertical을 유지하면서 사용자가 다음 작업을 웹에서
완료하도록 한다.

```text
Material / State / Lot
→ Test Campaign / Specimen / Test Run
→ CSV/TSV/XLSX 시험 데이터 등록과 mapping 승인
→ raw / normalized / processed Dataset
→ 반복시험 통계와 명시적 processing
→ 자동 또는 수동 fitting과 Candidate 선택
→ solver-neutral Material Model IR revision
→ Abaqus / OpenRadioss material card
→ 개별 또는 provenance 포함 Bulk Export Bundle 다운로드
```

Steel 탄소성, Polymer 선형 점탄성, Elastomer Ogden--Prony가 첫 reference 범위다. 실제 solver
실행과 solver qualification은 제외한다. Domain 승인이 없는 scientific profile과 mapping은
`reference/unapproved`로 유지한다.

## 2. 현재 기준선

- latest schema: migration 058
- implemented: Material/State/typed Property, Process/Lot bounded genealogy, tensile and
  shear-relaxation Dataset, processing/statistics/outlier, Voce and Prony calibration, human
  Candidate selection, immutable IR promotion, bounded multi-test Ogden scientific profiles/fitting,
  Abaqus/OpenRadioss cards, review/release/provenance
- live evidence: `docs/15-demo/user-e2e-evidence-2026-07-16.md`
- missing product depth: T-47 long-running soak/broad fault acceptance, object-lock/KMS/signing,
  signed connectors and production worker identity/token rotation. The exact 10,000-Material search
  and 2-GiB streaming gates passed on the isolated production-scale composition.
- user experience: T-46 global navigation, contextual Material tabs and task-oriented guide gate complete

Migrations 001~058, raw objects, prior revisions, cards, releases and golden fixtures are never
rewritten. Migration 058 only appends explicit worker lease fields and transition/index guards to
the durable Bulk Export Job; the production-scale unit adds no migration.

## 3. PR 순서와 exit gate

| PR | Task | Required exit gate | Status |
| --- | --- | --- | --- |
| 1 | docs/research/user-guide baseline | docs links, contracts and guide checks; no stale README claim | complete |
| 2 | T-39 Process Run/Lot/Specimen genealogy | unit + migration + live PostgreSQL + API + React + `make ci` | complete |
| 3 | T-40 Campaign/Instrument/conditions | same vertical gate plus exact calibration snapshot | complete |
| 4 | T-41 tabular importer/schema | parser/security/contract/PostgreSQL/browser fixtures | complete |
| 5 | T-42 viscoelastic replicate/TTS/master | numeric fixtures + provenance + browser curves | complete |
| 6 | T-43 scientific profiles/fitting | analytic/reference fixtures + diagnostics UI | complete |
| 7 | T-44 iterative calibration | repeated promotion and prior evidence/card stability | complete |
| 8 | T-45 Bulk Export Bundle | deterministic archive/digest + RLS + Export Center | complete |
| 9 | T-46 final navigation/manual images | complete task guides and deterministic browser captures | complete |
| 10 | T-47 operational hardening | telemetry, restore, supply-chain, performance/security and external Bundle worker evidence | in progress: observability, isolated restore, supply-chain, bounded and 10k/2-GiB production-scale performance/security, external assembly/reconciliation and hard-kill lease recovery complete; soak/fault, KMS and connector work remains |
| 11 | final acceptance | three live user E2E workflows and one verified bulk bundle | pending |

Each PR is branched from the freshly merged `main`, uses meaningful commits, passes its relevant
tests, is pushed, reviewed as a PR and merged before the next PR starts. After each merge update this
table, `IMPLEMENTATION_STATUS.md`, related guide pages and GUI screenshots.

PR 1 verification on 2026-07-16: user-guide link/manifest validation covered nine documents and
seven screenshots. The CI-equivalent suite with disposable PostgreSQL 16 completed 553 Python tests
with zero skip/failure, 28 Vitest tests, ruff, mypy, architecture/contract/OpenAPI checks and the
production web build.

PR 2 implements T-39 with migration 049: Process Run input/output split/merge, typed decimal and
unit normalization, balance evidence, cycle rejection, exact Specimen source Lot pinning, protected
API and connected React controls. The CI-equivalent run on 2026-07-16 passed 561 Python tests and
30 Vitest tests with no skip/failure, plus ruff, mypy over 473 source files, architecture/contracts,
OpenAPI compatibility and the production Vite build. Live Docker/PostgreSQL browser verification
created one balanced Process Run and one current-revision Specimen source link; the resulting image
is `docs/15-demo/images/process-run-specimen-source.png`.

PR 3 implements T-40 with migration 050: governed Campaign/standard conformance, Instrument and
non-overlapping dated Calibration records, typed execution Condition snapshots and a one-to-one
Test Run Context that pins every exact source revision. The API and React workbench reject stale
calibrations and expose no generic condition EAV or moving-head reference. Live PostgreSQL tests
cover validity, overlap, immutable revisions and project RLS; the affected user guide and browser
image are maintained with the vertical slice. The Windows CI-equivalent gate passed 568 Python
tests and 31 Vitest tests without skips/failures/warnings, plus ruff, mypy over 480 source files,
architecture/contracts, OpenAPI compatibility and the production Vite build. Live Docker browser
evidence is `docs/15-demo/images/test-run-context.png` with no console warning/error.

PR 4 implements T-41 with migration 051: explicit reusable Import Profile revisions, header-only
`needs_input` Preview Reports, exact terminal Import Runs and separate raw/normalized governed
Dataset revisions. CSV/TSV locale and XLSX sheet/security limits are explicit; formulas, macros,
external links, unsafe ZIP members and missing force/displacement geometry are rejected. The
protected API and connected React workbench preserve exact Test Run/Raw Asset/Artifact/Profile
revision pins and surface failed-run evidence without changing source bytes. User instructions and
the synthetic tensile sample are in `docs/user-guide/08-governed-tabular-import.md` and
`examples/data/reference-tensile.csv`.
Migration 051 was upgraded, downgraded to 050 and re-upgraded on disposable PostgreSQL 16. The
CI-equivalent gate passed 576 Python tests with zero skips/failures, 32 Vitest tests, ruff, mypy
over 486 source files, architecture/contract/OpenAPI compatibility and the production Vite build;
the clean npm install reported zero vulnerabilities. Live protected API execution imported nine
synthetic tensile rows and created distinct raw and normalized revisions. The connected 1440x900
browser capture is `docs/15-demo/images/governed-tabular-import.png`, with no console warnings or
errors.

PR 5 implements T-42 with migration 052: an exact ordered Selection pins normalized relaxation
Dataset and historical Test Run temperature revisions; the Plan fixes manual or WLF shift policy
and a reference temperature. One terminal Run commits separate aligned, statistics and master-curve
Dataset revisions, ordered shift evidence and provenance subactivities without changing any source.
The numeric kernel uses the common log-time intersection, piecewise-linear interpolation and no
extrapolation. Live Docker/PostgreSQL execution processed six public synthetic curves across three
temperatures and the connected browser displayed replicate count, sample bands, outlier status,
shift factors and master curve. The screenshots are
`docs/15-demo/images/viscoelastic-master-statistics.png` and
`docs/15-demo/images/viscoelastic-master-curve.png`. Migration 052 completed a fresh 001--052
upgrade and a 052--051--052 round trip on PostgreSQL 16. The CI-equivalent gate passed 585 Python
tests without skips/failures, 33 Vitest tests, ruff, mypy over 497 source files,
architecture/contract/OpenAPI compatibility, production Vite build and npm audit with zero
vulnerabilities.

PR 6 implements the bounded T-43 reference slice with migrations 053/054. Family-specific
scientific profiles are stable identities with immutable typed revisions; direct self-assertion of
domain approval is rejected. The Ogden Plan pins exact profile, Material State, baseline
Ogden--Prony IR and governed normalized Dataset revisions. The deterministic SciPy TRF kernel fits
one-term incompressible Ogden nominal responses across uniaxial, planar and equibiaxial modes,
whose Test Runs pin separate mode-specific reference Test Method revisions,
keeps calibration and holdout evidence disjoint, and stores every multistart Candidate, per-mode
objective, convergence, rank, covariance/95% CI or explicit not-estimable state, warnings and
Parquet diagnostics Artifact. The connected React workbench displays Dataset roles/weights,
candidate comparison and fitted/residual curves. It remains reference/unapproved, runs no solver
and performs no automatic Candidate promotion. PR 7 adds the separate human Selection and
append-only promotion described below.

PR 7 implements T-44 with migration 055. A human Selection pins the exact succeeded Run,
converged Candidate, diagnostics Artifact and baseline IR revision. Promotion requires the current
strong IR ETag and appends a new revision to the same stable model identity. Candidate and
Selection reuse, stale heads, cross-scope evidence and overwrite attempts are rejected; prior
cards and releases retain their exact IR revision and digest.

The PR 7 exit gate completed on PostgreSQL 16: fresh 001→055 and 055→054→055 passed, and the
CI-equivalent suite recorded 606 Python tests plus 35 Vitest tests with zero skip/failure. Ruff,
mypy over 518 source files, architecture/contracts/OpenAPI/build and npm audit all passed. Two live
promotion rounds appended r2 and r3; three existing Solver Card revision/digest pairs remained
unchanged and the connected browser reported no warning/error.

PR 8 implements T-45 with migration 056. A revisioned Export Selection pins ordered typed
Raw Asset/Artifact, Dataset revision, Material Model revision and Solver Card revision sources.
The durable Job commits or digest-reuses an immutable deterministic ZIP Artifact; required missing
or unauthorized inputs block and optional omissions are visible in the manifest. The connected
`/exports` workbench selects one Material's exact raw/Parquet/CSV/IR/schema/mapping/card
representations and downloads the Bundle through a short-lived transfer capability without
changing Release semantics. The browser created a 22-component Bundle, the API returned `201` for
authorization and `200` for content, and PostgreSQL recorded Selection lifecycle, provenance and
audit facts. The complete CI result is appended when the PR gate finishes.

The PR 8 exit gate passed a fresh PostgreSQL 16 `001→056` migration and `056→055→056` round trip,
613 Python tests with zero skips/failures, 36 Vitest tests, ruff, mypy over 526 source files,
architecture/contracts/OpenAPI compatibility, production Vite build and npm audit with zero
vulnerabilities.

PR 9 implements T-46 without a schema migration. Seven global routes select a real visible Material
before entering contextual Overview/Test data/Datasets & Processing/Models & Cards/Governance
deep links. Existing Material URLs remain valid, and unrelated workbenches no longer load on every
Material view. The machine-readable navigation contract, Korean troubleshooting guide and
`cmp-check-user-guide` add a CI gate for route/guide/screenshot drift. Verification passed 614
Python tests, 38 Vitest tests, ruff/mypy/architecture/contracts/OpenAPI/build and the
12-document/20-capture/7-route guide check. Docker browser evidence covered Models and Governance
hubs plus the DP780 model context without visible application errors.

PR 10 begins T-47 without a domain migration. API and worker emit OTLP/HTTP traces and metrics to a
vendor-neutral Collector; worker execution continues the exact W3C trace context stored on its Job.
Allow-listed JSON logs exclude URL/query/header/body/raw payload and credential fields, and the
Governance operations panel reads a bounded route-template snapshot only with `audit.read`.
The isolated recovery command restores a PostgreSQL 16 custom dump to a random temporary database,
copies immutable objects to a distinct snapshot and verifies relation counts, object digests and
provenance references before deleting only the temporary database. The live demo drill passed in
32.018 seconds with raw 18/18, total object samples 100/100 and zero dangling lineage edges. No
Release existed in the source, so Release digest recovery remains an explicit next drill condition.
The CI-equivalent gate passed 627 Python tests against disposable PostgreSQL 16 with zero
skip/failure, 39 Vitest tests, ruff/mypy/architecture/contracts/OpenAPI/user-guide/build and npm
audit with zero vulnerabilities. The 541.66-kB frontend chunk warning is retained as explicit input
to the next T-47 performance unit rather than hidden by raising the warning threshold.

The external Bundle unit adds migration 057 and keeps existing Selection and Bundle revisions
unchanged. Estimates above the configured inline boundary return `202` and are claimed by the
composed worker with `FOR UPDATE SKIP LOCKED`; the worker creates deterministic ZIP bytes on disk,
streams them into an immutable Artifact and records a typed output commit before the Bundle
projection. A later projection failure becomes `reconciliation_required`, remains visible through
the API/UI and is linked on retry without reassembly. The live Docker path forced a 22-component
DP780 Selection above the 16-KiB demo limit and verified the stored and downloaded 21,822-byte ZIP
against SHA-256 `04f6aeca5f0f0ff48448dcb0f3c2e4d3e361b890027869b7f3943562d27097ab`.

The production-scale unit keeps migration 058 and every existing revision unchanged. A safe,
acknowledged fixture appends deterministic synthetic Materials until exactly 10,000 are visible in
one isolated organization/project. Catalog list responses now expose the RLS-filtered total
cardinality independently of their page limit. The API then accepted a deterministic 2-GiB object
as 32 64-MiB parts without buffering the full source. The 2026-07-16 report for source commit
`b506f6415f49774fb32692cf680ed56c866e9902` passed Catalog p95 182.128 ms, exact 2-GiB digest/size,
22.999 MiB/s upload throughput and a 67,164,359-byte Python allocation peak under the 192-MiB gate.
Its canonical report SHA-256 is
`96d75ca787695ad5848b0b65562554a93f8aa63dd204b82d92e159f723cef481`.

The PR 6 exit gate completed on disposable PostgreSQL 16: fresh 001→054 plus 054→053→054 passed,
the CI-equivalent suite recorded 600 Python tests with zero skips/failures and 35 Vitest tests,
ruff/mypy/architecture/contracts/OpenAPI/build all passed, and npm audit reported zero
vulnerabilities. The live Docker workbench recorded candidate comparison, covariance/95% CI and a
52-point fitted/residual diagnostics Artifact without browser console errors.

## 4. Acceptance scenarios

### Steel

Create Material/State/Lot/Campaign/Instrument/Specimen, import three tensile replicates, approve
mapping, align/statistically inspect them, fit or manually define Voce/tabulated plasticity, select
a Candidate, promote an IR and download Abaqus plus OpenRadioss cards.

### Polymer

Import relaxation replicates at at least three temperatures, preserve every curve, align on the
common log-time domain, record statistics and WLF shift evidence, create a master curve, fit Prony,
select/promote and download an Abaqus viscoelastic card.

### Elastomer

Import two or more compatible hyperelastic test modes plus relaxation evidence, fit or manually
define one-term Ogden--Prony, retain insufficient-mode warnings, select/promote and download Abaqus
and OpenRadioss LAW62 cards with the LAW62 volumetric approximation visible.

### Bulk delivery

Select raw/normalized/processed test data, IR JSON/schema, mapping reports and cards. Preflight the
selection and download a deterministic ZIP whose manifest and `checksums.sha256` verify every file.

## 5. Fixed engineering defaults

- PostgreSQL 16+, explicit typed tables, composite tenant/classification FKs, forced RLS
- CSV, TSV and XLSX only for the first governed importer; no proprietary vendor parser
- canonical curve Artifact is Parquet; human exchange is CSV; raw bytes remain unchanged
- viscoelastic alignment uses log-time intersection and forbids extrapolation by default
- WLF fitting requires three temperatures; manual shift factors remain versioned alternatives
- repeated calibration appends revisions under one stable Material Model identity
- no automatic Candidate approval or silent approximation
- bundle limit is 1,000 components or 5 GiB and is configurable
- actual Abaqus/OpenRadioss execution remains out of scope
- external proprietary connectors remain blocked until credentials, samples and authorization exist

## 6. Resume protocol

Another session resumes by reading AGENTS.md, README.md, this file, `IMPLEMENTATION_STATUS.md`, the
first pending Task in `backlog.md`, and its ADR. It verifies `git status -sb`, the latest migration,
open PRs and the last recorded test evidence. It does not redo a completed PR or modify historical
evidence. The first row whose Status is not `complete` is the only active implementation unit.

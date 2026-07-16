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

- latest schema: migration 048
- implemented: Material/State/typed Property, Process/Lot bounded genealogy, tensile and
  shear-relaxation Dataset, processing/statistics/outlier, Voce and Prony calibration, human
  Candidate selection, immutable IR promotion, Abaqus/OpenRadioss cards, review/release/provenance
- live evidence: `docs/15-demo/user-e2e-evidence-2026-07-16.md`
- missing product depth: T-39~T-45 and T-47
- user experience gap: global navigation and task-oriented user manual from T-46

Migrations 001~048, raw objects, prior revisions, cards, releases and golden fixtures are never
rewritten. New schema begins at migration 049.

## 3. PR 순서와 exit gate

| PR | Task | Required exit gate | Status |
| --- | --- | --- | --- |
| 1 | docs/research/user-guide baseline | docs links, contracts and guide checks; no stale README claim | complete |
| 2 | T-39 Process Run/Lot/Specimen genealogy | unit + migration + live PostgreSQL + API + React + `make ci` | pending |
| 3 | T-40 Campaign/Instrument/conditions | same vertical gate plus exact calibration snapshot | pending |
| 4 | T-41 tabular importer/schema | parser/security/contract/PostgreSQL/browser fixtures | pending |
| 5 | T-42 viscoelastic replicate/TTS/master | numeric fixtures + provenance + browser curves | pending |
| 6 | T-43 scientific profiles/fitting | analytic/reference fixtures + diagnostics UI | pending |
| 7 | T-44 iterative calibration | repeated promotion and prior evidence/card stability | pending |
| 8 | T-45 Bulk Export Bundle | deterministic archive/digest + RLS + Export Center | pending |
| 9 | T-46 final navigation/manual images | complete task guides and deterministic browser captures | pending |
| 10 | T-47 operational hardening | telemetry, restore, supply-chain, performance/security evidence | pending |
| 11 | final acceptance | three live user E2E workflows and one verified bulk bundle | pending |

Each PR is branched from the freshly merged `main`, uses meaningful commits, passes its relevant
tests, is pushed, reviewed as a PR and merged before the next PR starts. After each merge update this
table, `IMPLEMENTATION_STATUS.md`, related guide pages and GUI screenshots.

PR 1 verification on 2026-07-16: user-guide link/manifest validation covered nine documents and
seven screenshots. The CI-equivalent suite with disposable PostgreSQL 16 completed 553 Python tests
with zero skip/failure, 28 Vitest tests, ruff, mypy, architecture/contract/OpenAPI checks and the
production web build.

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

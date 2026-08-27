# Issue #341 — source-v2 remaining common units evidence

## Boundary and starting state

Issue #341 is the exact active native Sub-issue for #246 Task 2. Work started from fetched
`origin/main` `4d0ef93ff4b21dc66d298ac86732a6a71fdb3603` on branch
`codex/issue-246-task2-common-units`. #246 remains the parent tracker and stays open after this unit;
Task 1B is its next implementation unit.

The starting state was **partial**. Issue #205 already supplied eight explicit dimensions, immutable
Unit Profile revisions, Decimal precision/range/tolerance rules, public conversion endpoints and the
compatibility-only `kg_m_s` profile. Issue #209 supplied exact `Hz` handling for governed DMA as an
explicit legacy schema unit. Task 1A supplied source-v2 normalization, five approved product Links,
exact-source Artifact export and location-aware diagnostics. Missing behavior was bounded to an
explicit speed dimension, `tonne/mm3` density, the additive public contract revision and an unchanged
source-v2 database round trip.

Task 1B actual JSON data registration, `dma_strain_sweep`, viscoelastic policy, representative
envelopes, solver Templates/profiles, production defaults, UI work and #276 are not part of #341.

## Primary journey and acceptance

| Part | #341 journey |
| --- | --- |
| Setup | An Administrator selects the seven manifest-declared source-v2 JSON files without changing their bytes. The package contains six data formats, five approved direct Links and two source Unit Profiles. |
| Actions | The Administrator plans the package, atomically applies it, exports the exact source Artifact and repeats the same plan/apply as a no-op. A caller also reads `/api/v1/unit-system`, converts explicitly declared speed or density quantities, and creates/revises a non-production Unit Profile with the new stable IDs. |
| Visible outcome | The prior `mm/min` and `tonne/mm3` errors are absent. Plan/apply retains six Tables, five Links and two profiles. The source-only DMA→elastoplasticity expression remains excluded with `CMP-SCHEMA-SOURCE-0029`; no product Link is fabricated. |
| Persistence/read-back | PostgreSQL reload preserves the exact Unit Profile identity, revision pin, content hash, selection application location and historical revision. Exported source-set bytes and SHA-256 equal the input; the repeated apply produces no mutations. |
| Preserved contract/state | Original value/unit text, normalized value/unit, quantity semantics, raw source bytes, JSON pointers, member hashes, immutable revisions, all 1.0 unit IDs/aliases, profile-free history, `/api/v1`, `kg_m_s` and `production_default=false` remain unchanged. |
| Recovery | Cross-dimension conversion, wrong declared source, unsupported spelling, mismatched semantics and non-finite/range/precision failures close with stable code, location and source/target dimension details. Atomic apply prevents partial publication. |
| Owned scope | Backend common-unit domain/API, public unit schema and fixtures, source-v2 adapter boundary, migration, focused unit/contract/PostgreSQL/browser regression and current #341 delivery documentation. |
| Forbidden shortcuts | No unit-spelling dimension inference, generic unit library, source fixture edit, production solver profile, `Hz` reimplementation, Task 1B/2B/3/4 implementation or production React/CSS/DOM change. |

## Implemented contract

- Common-unit contract `1.1.0` additively defines `speed` with canonical `m/s`, `mm/s` and
  `mm/min`. `1 mm/s = 60 mm/min = 0.001 m/s`; all paths use the existing 34-significant-digit
  Decimal policy and the speed dimension's declared absolute/relative `1e-12` tolerance.
- `mass_per_volume` additively defines `tonne/mm3` with exact scale `1e12` against `kg/m3`;
  therefore `7.85e-9 tonne/mm3 = 7850 kg/m3 = 7.85 g/cm3`.
- Public request processing requires explicit dimension, stable unit ID and quantity semantics.
  It never derives a dimension or semantic from unit spelling. Existing aliases remain accepted
  only through their registered canonical IDs.
- `kg_m_s` remains compatibility-only and non-production. Its new speed member is canonical `m/s`;
  no production solver profile is selected.
- `Hz` remains the exact #209 legacy schema unit and is not added to the public common-unit registry
  or Unit Profile selection set.
- The source profile `cae_mm_t_s` declares source-only `mass: tonne`, which #341 is not authorized to
  add as a public MASS unit. The immutable source Artifact retains it byte-for-byte; the adapter emits
  location-aware `CMP-SCHEMA-SOURCE-0030` at `/manifest/unit_profiles/0/units/mass` and excludes only
  that unused selection from the common-unit projection. It does not infer or convert `tonne`.

## Immutable source authority

No file under `fixtures/schema-definition-bundle/source-v2` is changed. The manifest and six JSON
schema members used by the source-v2 package retain these SHA-256 values:

| Member | SHA-256 |
| --- | --- |
| `catalog-schema-bundle.manifest.json` | `d22c12a7b8805d9cf44554336cf41ed669c63ffd190fe746c47dc8a1c29a31c5` |
| `record-schemas/dma-test-v1.json` | `d6cd0befc77a50d957870924da22527f630e048d9f2975262d86d09485eca3c0` |
| `record-schemas/elastoplasticity-v2.json` | `d42508e828951adeb00382f812c22756c778d19431c4211acdf260e94afe77b6` |
| `record-schemas/fld-test-v1.json` | `c6ec09caccedce017b5904f8460dbe0be3995f1bc36235f4179ab84bfcfba4ac` |
| `record-schemas/statistics-v2.json` | `10210a75fc01d754163a2abe00374e91bd0cbb26ac262847d938a8e4a5cac11a` |
| `record-schemas/technical-data-v2.json` | `3c51f60f9df6218d874c5c0a82f8fff9888f2c56ec3df204bcf810b2def7b4a0` |
| `record-schemas/tensile-test-v2.json` | `8a310ecc215b67ca5abd23c56984d74355b633f6e40662a9c56880c2f0a7926e` |

## Verification record

| Gate | Result |
| --- | --- |
| Focused unit, source adapter, bundle, public contract and migration tests | PASS — 370 tests; includes every speed/density conversion pair and round trip, realistic density, API positive/negative fixtures, non-finite/range/precision and structured failure cases. |
| PostgreSQL Unit Profile and unchanged source-v2 acceptance | PASS — 2 tests against isolated PostgreSQL 16; includes reload, exact pins/hash/history and plan → atomic apply → exact-source export → no-op reapply. |
| Changed Python lint and type checking | PASS — Ruff on all changed Python files; mypy on the five changed production/migration modules. |
| Production web build | PASS during the rebuilt demo composition; bundle budget reports zero warnings and zero errors. No `apps/web` file changed. |
| Browser journey | PASS — the current `schema-definition-bundle-administration.spec.ts` journey passed 1/1 against a disposable PostgreSQL/API/worker/web stack: upload, plan, confirm, atomic apply, restore and checksum verification. Repeat seed compared 304 tables without changes, and permanent demo counts were identical before/after. |
| Existing unit/registration/DMA Hz/Processing/Fit/Export/`kg_m_s` regressions | PASS — 89 focused tests. The full contract suite passed 481 tests. Contract lint and OpenAPI backward compatibility also passed. |
| Documentation and worktree hygiene | PASS — user-guide registration/link validation, documentation-impact validation, Ruff, changed-scope mypy and `git diff --check`. No visual source changed. |
| Independent Balanced audit | APPROVE — the one canonical `independent_auditor_terra_high` read-only audit found blocker 0, major 0 and material-minor 0; no scope creep, `apps/web` change or fixture change. Publication may advance only to owner authorization. |
| Pre-publish | Correctly deferred — the manual gate requires committed bytes and refused the intentionally dirty, uncommitted worktree. It must pass from a clean worktree after an authorized commit and before push/PR. |

The host has two environment-specific canonical port conflicts: Apache owns `8000`, and Windows
reserves `54330–54429`. The canonical images and migration build successfully; PostgreSQL verification
uses an equivalent isolated PostgreSQL 16 tmpfs on `127.0.0.1:55430`, and browser verification uses
the repository's project-scoped disposable demo with dynamically published ports. No unrelated
process or persistent demo volume is stopped, removed or rewritten.

The legacy second test in `issue246-source-v2-categories.spec.ts` is not the current Format
Definitions journey: it still locates the removed Task 1 label `Definition bundle` and fabricates the
ten pre-Task-2 unit errors. Its first Materials category/direct-Link test passes, but the obsolete
second test times out before upload. #341 does not modify this forbidden `apps/web/**` test or treat
its stale invalid-plan expectation as product acceptance; the current Administration journey above
is the issue-authorized browser gate.

## Visual and publication boundary

There is no production React/CSS or visible DOM change. The mandatory five-viewport visual evidence
and screenshot approval are therefore **N/A** for #341; the existing Administration Format Definitions
journey is a behavior-only browser regression.

No commit, push, PR, ready transition or merge is authorized by this evidence. #341 delivery tracking
is synchronized only after an authorized merge. At that point #341 records the PR and merge SHA,
#246 and #117 record the completed Task 2 and Task 1B as next work, while #246, #117 and #276 remain
open as required.

# Issue #205 common units and versioned Unit Profile evidence

## Boundary and implemented journey

This packet records implementation evidence for GitHub issue #205. The working base is
`origin/main` `7bba7ab653eca15b8abedc988fc7c17afc79e873`, branch
`agent/issue-205-common-units`, in the managed worktree
`C:\SourceCodes\cae-material-platform-issue205`.

A data steward can inspect the bounded common unit contract, create a non-production Unit Profile,
revise it with `If-Match`, and read either revision back by exact identity. A Processing Output may
pin one exact revision and records every input/display application. Metal Fit inherits that exact
pin and application trace from its source. Target preview and delivery refuse a replacement pin;
the resulting Solver Card revision, delivery receipt and provenance all identify the same profile
ID, revision ID and content SHA-256 plus the actual solver locations. Missing selections, wrong
dimensions, stale hashes and cross-project reads fail without a default or `latest` fallback.

The implementation is additive. Profile-free results retain their previous schema version and
canonical/native bytes. Existing canonical Test Data semantics outside the closed #205 dimensions,
including the production `frequency.cyclic`/`Hz` channel, remain governed by their explicit stored
scale/offset and values; they are not inferred or added to the common unit registry.

## Supported contract and compatibility

- Contract `1.0.0`: `force_per_area`, `length`, `time`, `force`, `mass`,
  `mass_per_volume`, `temperature`, `strain`; supported IDs and tolerances are authoritative in
  `docs/02-requirements/requirements.md` and `contracts/units/unit-resources.schema.json`.
- Absolute/test `Cel` conversion is affine; temperature difference never receives the absolute
  offset. Strain remains distinct from arbitrary dimensionless semantics.
- The existing 13 registration conversions delegate to the common service while preserving their
  original evidence shape and original unit text.
- `µm`/`μm`, `kg/m^3`, `g/cm^3`, `degC`/`°C` are bounded read/input aliases. Unit Profile revisions
  store stable IDs only. Public conversion validates that the exact original text resolves to the
  declared source unit while preserving the accepted original spelling in evidence.
- `kg_m_s` remains the only existing solver compatibility system and declares
  `production_default=false`. Profile-bearing export currently requires its solver-export choices;
  no production default profile was selected.
- Schema Bundle/plan stays at `1.0.0`, validates `x-unit` against stable IDs and remains deterministic
  and no-write. Apply/publication is not implemented.

## Persistence and trace

Migration `20260926_095_issue205_common_units.py` adds typed Unit Profile identity/revision/selection
tables, exact-hash foreign keys, immutable triggers and forced RLS. It adds nullable exact pins and
typed application child rows to Processing Output, metal Fit, Neutral Solver Card and delivery
receipt storage. Profile-bearing Solver Card semantic content includes the exact pin/application
trace so its revision content hash covers unit usage; native card text and SHA-256 remain unchanged.
Solver Card provenance records `usage.role=unit_profile` and an explicit
`unit_profile_application` derivation.

An isolated PostgreSQL upgrade from `20260925_094_issue160` preserved a seeded profile-free
Processing Output with null pins. Stable identity, two immutable revisions, exact old/new read-back,
content-hash pin validation, cross-project RLS and immutable rows passed. After removing only the
test-owned profile, downgrade returned to `20260925_094_issue160`. A real profile-bearing delivery
also passed typed card/receipt read-back, semantic content-hash equality, provenance, child-row
immutability/RLS and legacy zero-child-row/native-SHA checks.

## Verification record

| Gate | Result |
| --- | --- |
| Common unit property/round-trip, temperature, density, precision/overflow, profile domain/API | PASS |
| Existing 13 registration mappings, Materials/Configurable Record, canonical Test Data | PASS |
| Processing Output, inherited metal Fit trace, Export preview/delivery/direct card and solver goldens | PASS |
| Versioned JSON Schema/OpenAPI parity and positive/negative contract fixtures | PASS |
| PostgreSQL Unit Profile lifecycle, exact revision/hash, migration upgrade/downgrade and RLS | PASS — 1 test |
| PostgreSQL profile-bearing card/delivery, Fit, typed trace, provenance and legacy compatibility | PASS — 6 tests |
| PostgreSQL #204 deterministic no-write planner | PASS — 1 test |
| PostgreSQL Materials/registration read-back and Configurable Record guards | PASS — 4 tests |
| Focused non-PostgreSQL domain/API/contract/regression suites | PASS — 476 tests |
| Full non-PostgreSQL repository suite | PASS — 1,466 tests; 91 PostgreSQL tests and the 3 unchanged baseline checks described below deselected |
| Migration and architecture automation | PASS — 126 migration tests, 29 architecture tests and `cmp-check-architecture` |
| Contract lint and compatibility | PASS — JSON Schema/OpenAPI lint and baseline compatibility |
| Python quality | PASS — Ruff; mypy on all 67 changed/new Python files |
| Documentation and whitespace | PASS — user-guide, worktree doc-impact and `git diff --check` |
| Web workspace CI check | PASS — production build/bundle budgets and 331 Vitest tests; no web source changed |
| Canonical Compose | PASS — current-source rebuild with preserved volume; migration/reference plugin/seed exit 0, API/PostgreSQL healthy, full demo seed completed |
| React/CSS, browser and five-viewport review | N/A — no frontend source or user-visible layout changed |

The initial parallel execution of three migration-heavy PostgreSQL suites exceeded its shell time
limit and was not counted as evidence. Its exact temporary DB/roles were removed, then the affected
planner and Materials cases were rerun sequentially with the passing results above. The canonical
Compose database and volume were not removed.

The unfiltered non-PostgreSQL run found and then cleared five #205-owned expectations (authorization
closure, API/worker version and a deliberately non-SI processing fixture). Three unrelated baseline
checks remain unchanged from `origin/main`: the root `AGENTS.md` byte budget, the old cold-start
backlog substring list, and an #184 crop manifest containing the original worktree's absolute path.
They were explicitly deselected from the passing full rerun rather than altered in this bounded
issue. The initial 60-second full-suite shell timeout was not counted. Full-repository mypy likewise
reports only unchanged baseline files; every changed/new Python file passes a no-incremental check.

Final documentation, lint/type, pre-publish and independent Balanced audit results are recorded
before the PR leaves draft. #206 and later work are not started by this issue.

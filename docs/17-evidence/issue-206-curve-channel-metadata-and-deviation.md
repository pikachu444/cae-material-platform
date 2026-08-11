# Issue #206 curve channel metadata and deviation evidence

## Boundary and starting state

This packet records implementation evidence for GitHub issue #206. Work started from fetched
`origin/main` `93ff2ba32a988a20cd910dbb3f2b29d728a20a40` on branch
`agent/issue-206-curve-metadata-deviation` in the managed worktree
`C:\SourceCodes\cae-material-platform-issue206`. At the start there was no open PR or remote #206
branch, #205 was complete in PR #234, and #206 was the first unfinished #117/backlog unit.

The original checkout was not modified. Its starting HEAD/tree fingerprints were
`391105f7a05639cce66df91e882944f6cc3005b6` and
`701dc7e3abdfcd43e7f5df72cdd75ea3e82cc93b`.

Initial classification was:

- complete: canonical Test Data channel meaning, original/normalized units and axis roles;
  immutable Artifact/revision storage; the #205 unit service; existing Processing and Statistics
  calculations and exact provenance;
- partial: source-specific curve responses, Processing/Statistics calculation evidence and the
  Modeling plot;
- missing: a shared versioned definition/deviation contract and adapter registry, an exact Catalog
  curve preview, Materials chart, shared Fit definition and metadata-aware tooltip;
- documentation mismatch: implementation status, contracts and user guides did not describe a
  shared contract or honest unknown-legacy handling.

## Primary user journey and acceptance

| Part | Issue-owned journey |
| --- | --- |
| Setup | Seed one synthetic non-production Material Record revision with an exact observed canonical Test Data curve and one exact replicate Statistical Result curve. |
| Actions | Open Materials → Curves, select both curves, inspect channels/units/band/Evidence, open only the observed curve in Modeling, then visit Data → Process → Fit. Use pointer and keyboard tooltip navigation and toggle the legend. |
| Visible outcome | Materials and Modeling show the same definition SHA, axis labels, display units and recorded deviation meaning. The observed curve has no invented band; the statistical curve shows its recorded pointwise Student-t interval and `n(x)` but remains view-only. |
| Persistence/read-back | Every response pins the exact Record/Test Data/Result revision and immutable Artifact ID/digest/schema. Reload and exact historical reads return the same values and definition. Preview sampling never becomes calculation input. |
| Preserved contract/state | Original bytes and prior revisions remain unchanged; unknown legacy values remain available with `metadata_state=absent`; #204 planning stays arbitrary-cardinality and no-write; #205 Unit Profile pins remain exact; Fit never resolves `latest`. |
| Recovery | Unknown legacy metadata produces an honest unavailable notice and no band/Fit action. A known or declared Artifact with corrupt bytes, digest, columns, length, unit, bound pair or provenance fails with a structured location-bearing error and may be retried only after the source is corrected. |
| Owned scope | Additive curve contract/domain/adapters, existing Dataset/Test Data/Processing/Statistics/Catalog APIs and Artifact writers, shared Materials/Modeling display components, synthetic fixtures, tests, current docs and this evidence. |
| Forbidden shortcuts | No row-per-point table, generic EAV, opaque JSON authority, historical rewrite/backfill, hidden conversion/alignment/resampling/smoothing, new statistical calculation, representative curve, automatic Fit approval or route-specific 4K override. |
| Exact acceptance | Contract/schema/runtime parity; positive/negative and legacy compatibility; real PostgreSQL Artifact/revision/provenance/RLS/no-write checks; affected backend/web/Compose/browser/doc gates; five viewport originals/crops; independent exact-SHA audit without blocker/major/material minor; direct Product Owner visual approval before ready/merge. |

## Contract, Artifact and compatibility result

- Shared schema: `urn:cmp:datasets:curve-channel-metadata:1.0.0`.
- HTTP/OpenAPI: `0.35.0`.
- Current Parquet curve schemas: canonical Test Data, reference normalized/processed tensile and
  pair/replicate Statistics use minor version `1.1.0`; canonical definition JSON and SHA-256 are
  stored in Parquet schema metadata.
- Current common Processing Output: `1.5.0` with stage definitions. Existing `1.3.0` and `1.4.0`
  outputs remain readable, and their canonical bytes are unchanged.
- Metadata state is `declared | legacy_compatible | absent`. A declared or reviewed legacy format
  is fully validated before same-index sampling. An unknown historical schema is not parsed into a
  guessed definition and returns `absent`; a known format with corrupt bytes/content fails closed.
- Reviewed adapters cover existing canonical/governed Test Data, tensile and shear normalized or
  processed curves, Processing ensemble stages, tensile pair/replicate Statistics,
  viscoelastic aligned/temperature-statistics/master curves and Modeling hardening curves.
- Exact source revision/digest and plan/run/result or calculation provenance pointers remain in the
  response. Catalog permits Modeling only for a canonical Test Data revision exactly bound to the
  selected Record revision. Statistical envelopes and unknown legacy curves are view-only.
- #205's closed eight-dimension unit registry and exact Unit Profile applications are reused.
  Existing outside-registry canonical semantics such as `frequency.cyclic`/`Hz` retain stored
  explicit scale/offset and are neither inferred nor added to the registry.

The contract describes existing values and statistics. It adds no statistical calculation,
alignment, resampling, smoothing, representative curve, automatic backfill or approved Fit input.
#207 bundle apply/export, #210 scalar distribution fitting and #211 representative/approved Fit
input remain outside this change.

## Persistence decision and PostgreSQL evidence

Canonical metadata is part of newly written immutable Artifact bytes; exact owning/source revisions
and existing provenance rows remain the authority. No new table, column, row-per-point store or
persistence lifecycle was added. Current-source Compose exposed one necessary existing-database
compatibility change: typed Dataset/Processing/Statistics guards originally accepted only the exact
`1.0.0` Parquet schema refs, so a newly persisted `1.1.0` recipe/result was correctly rejected.
Migration `20260927_096_issue206_curve` widens only those existing constraints and Artifact guard
functions to the reviewed `1.0.0 | 1.1.0` set. Upgrade preserves old rows and RLS unchanged;
downgrade restores the old guards only when no immutable `1.1.0` Artifact/recipe/plan evidence
exists and otherwise refuses losslessly.

An isolated PostgreSQL 16 container with tmpfs storage exercised the real repositories and RLS. It
created a legacy `1.0.0` and declared `1.1.0` curve Artifact, Catalog Record revision 1 pointing to
legacy bytes and revision 2 pointing to declared bytes, and read both back through the exact public
API. Values, Artifact IDs/digests, schema refs and metadata states matched; historical Artifact and
Record rows stayed pinned and preview reads did not change Catalog, Artifact or provenance counts.
Same-tenant authorized reads passed. Cross-organization, cross-project and insufficient
classification reads returned not found without leaking the records.

## Verification record

| Gate | Result |
| --- | --- |
| Curve domain, Artifact registry, positive/negative fixtures and legacy frequency | PASS — focused unit/contract suites, including 104 contract tests |
| Dataset, canonical Test Data, Processing, pair/replicate Statistics and Catalog API regression | PASS — included in the full non-PostgreSQL run |
| Real PostgreSQL exact legacy/current Artifact/Record round-trip, revision/provenance and RLS | PASS — included in 93 selected tests with zero skips |
| PostgreSQL migration up/down/up, #204 no-write planner, #205 Unit Profile and 10,000-record case | PASS — 93 selected tests, 140 deselected, zero skips |
| Full non-PostgreSQL repository suite | PASS — 1,494 passed, 93 PostgreSQL skipped and the three unchanged baseline checks below explicitly deselected |
| Web shared chart/tooltip/Materials/Modeling and full workspace tests | PASS — 62 files, 334 tests |
| Contract lint and generated client | PASS — generated client has no uncommitted drift |
| Python Ruff and architecture checks | PASS |
| Migration static contract | PASS — additive typed guards, no table/JSON/EAV, lossless downgrade refusal |
| Web production build/bundle and Storybook a11y build | PASS; lazy Materials chunk warning remains below its hard budget |
| Playwright canonical Compose journey | PASS — 14 tests, including keyboard/tooltip and saved Process → Fit reload |
| Current-source canonical Compose | PASS — preflight, rebuild/recreate, migration/reference plugin/seed exit 0, API/Web health and full demo verifier |
| User-guide inventory, documentation impact and whitespace | PASS — 20 guides, 95 current captures, structured evidence duplicate declarations and `git diff --check` |
| Five-viewport originals/crops, Web Interface Guidelines and Q01–Q20 Main review | PASS — deterministic geometry; actual Windows 4K physical readability remains #223 |
| Clean-worktree pre-publish | PASS — manual gate fingerprint `df646662367f0e87bd96476b5d1445b399939d9a1ea5c60e51da8b2f5a724038` at commit `3493ed718f986893493f82b25a6a56aea765b941` |
| Independent exact-SHA Balanced audit | PASS for draft publication at `3493ed718f986893493f82b25a6a56aea765b941` — blocker 0, major 0, material minor 0 |
| Product Owner visual approval | PENDING; draft PR must remain draft |

The broad repository tests expose three unchanged baseline checks already recorded by issue #205:
the root `AGENTS.md` byte budget, legacy cold-start backlog substrings and an #184 manifest absolute
path that names the original checkout. They are not weakened or changed in this issue. Full mypy
reports 31 existing errors in seven files. A no-incremental check of 60 changed Python files after
excluding only the two unchanged-error locations and optional capture imports passes; the #206
capture script also passes separately with its Playwright/Pillow environment and skipped imported
implementation. Its inherited `capture_current_product.py` dependency retains two existing untyped
lambda findings.

The initial live before-state capture reached the exact Material route but the preserved seeded
Record revision did not yet contain its workflow link. The diagnostic is preserved rather than
presented as an approved baseline:
[Material detail diagnostic](images/issue-206-curve-channel-metadata-and-deviation/before/diagnostic/material-detail-failure-1440x900.png).
The #206 seed correction creates exact synthetic observed/statistical curve links without deleting
or rewriting existing data.

Compose validation retained every pre-existing volume. An initial verifier call occurred before the
seed service had finished and was discarded. Once seed completed, the preserved database exposed a
real verifier defect: 113 immutable historical model projections existed, while the verifier chose
the first projection and first Neutral candidate instead of the exact pending-review revision and
its pinned Processing lineage. The verifier now joins model/review by model ID, revision ID,
manifest digest and lifecycle, then resolves the Neutral JSON with the same exact Recipe/Output
pins; focused regression and the full canonical verifier pass.

A separate clean diagnostic project/volume was also retained. Its first seed exposed two unchanged
boundaries inherited from `origin/main`: Catalog Table creation commits but its write-only response
lifecycle lookup returns 409, and a new Catalog Record containing the existing
`ratio.poisson`/`1` scalar is rejected by #205's deliberately closed registry. Replaying only after
the committed Table state change reached that second boundary. This clean diagnostic was not counted
as acceptance, was not bypassed by changing production contracts and did not weaken #205. Both new
declared curve pointers independently passed their actual Artifact validation there. The required
preserved-volume canonical composition, which is the same boundary used by #205, passes in full.

## Visual and accessibility acceptance

The registered manifest is
[`visual-evidence.yaml`](images/issue-206-curve-channel-metadata-and-deviation/visual-evidence.yaml).
It records Chromium 151.0.7922.34, browser zoom 100%, DPR 1, exact routes, SHA-256 and pixel sizes.
Main opened every image at original resolution: 12 immutable before originals, 20 after originals
for Materials Curves and Modeling Data/Process/Fit at 1366×768, 1440×900, 1920×1080, 2560×1440 and
3840×2160, 48 unscaled header/navigator/control/graph crops, and three 1440×900 interaction states
plus their three 1:1 crops. The images were captured from implementation commit
`e9b523a7f7b613d8d6efc0396160f0ceb2aff2c4`; subsequent changes are verification/docs only and do
not change web source or pixels.

The keyboard state proves SVG focus, Home/Arrow navigation, Escape clearing, a live accessible point
description and the same values as pointer exploration. The statistical tooltip names a pointwise
95% confidence interval, `student_t.mean_two_sided` version 1.0.0, `ddof=1`, lower/upper MPa and
`n=3`; the Evidence state exposes definition SHA, exact owning/source revisions, Artifact ID/digest/
schema and calculation provenance. The absent state keeps “Curve available” while stating that no
channel/deviation metadata was recorded and exposes no inferred axes, units, band or Fit action.
Legend controls are native buttons with `aria-pressed`; the chart has a task-specific accessible
name, focus indication, keyboard instructions and polite live text. The fresh Web Interface
Guidelines review found no blocker in focus order, names, controls, status announcements, target
reachability, overflow, text clipping or non-pointer operation.

### Main qualitative review — Q01 through Q20

| ID | Result | Direct evidence and rationale |
| --- | --- | --- |
| Q01 | pass | Materials navigator originals and current long-tree guide captures retain a visible independent local scrollbar where content overflows. |
| Q02 | pass | The two-item curve list has no fake rail; long Materials results retain their established independent rail. |
| Q03 | pass | 1366/1440 originals and navigator crops preserve shared compact rows, aligned glyph/label and reachable identities. |
| Q04 | pass | Modeling Fit originals/crops preserve the shallow six-group ribbon and dominant graph without squeezing controls. |
| Q05 | pass | All graph crops show contract-driven axis labels and units without title/tick/frame collision or detached x title. |
| Q06 | pass | Curve/band visibility remains a compact graph legend and does not compete with status or Evidence. |
| Q07 | pass | Five-viewport SVG frames recompute with stable glyph/stroke proportions; no non-uniform transform or route-specific scaling exists. |
| Q08 | pass | Modeling Fit retains true yield stress versus true plastic strain, including positive initial yield at zero plastic strain. |
| Q09 | pass | Existing navigator/result overflow affordances remain distinct and keyboard reachable; chart navigation itself is pointer/keyboard equivalent. |
| Q10 | pass | Fit legend remains in the established curve-free plot region in all five originals. |
| Q11 | pass | Modeling rail keeps shared flat-pane rhythm, aligned hierarchy, secondary revision text and curve-specific controls. |
| Q12 | not-applicable | Export setup, solver selection and unit selector topology are not changed or shown by this issue. |
| Q13 | not-applicable | Export setup/result row grammar is outside the target routes. |
| Q14 | not-applicable | Export readiness states are outside the target routes. |
| Q15 | pass | Materials and Modeling plots retain data-derived headroom, applicable zero anchors, correct units and clear frames at every viewport. |
| Q16 | not-applicable | Native solver-card preview and Export context topology are unchanged. |
| Q17 | not-applicable | Administration object lists are unchanged. |
| Q18 | not-applicable | Administration Add commands and Record/Layout editor topology are unchanged. |
| Q19 | not-applicable | Administration Link Type cardinality is unchanged; #206 only reads existing exact domain bindings. |
| Q20 | pass (deterministic geometry) | 1920/2560/3840 originals and 1:1 crops show full-width shells, elastic dominant graphs, bounded secondary panes and no clipping, work island, filler, CSS zoom or route-specific 4K override. Actual Windows 4K 100%/150%/200% physical readability remains unapproved in #223. |

## Independent audit and publication

The independent read-only auditor approved exact commit
`3493ed718f986893493f82b25a6a56aea765b941` for draft publication with no implementation,
contract, persistence, regression, visual-evidence or scope finding. The expected Product Owner
approval is an external post-audit gate: the PR must remain draft until the owner directly approves
the registered 1920/2560/3840 originals and crops. This tracking-only annotation changes no code or
pixels; the same auditor must review its final commit, whose exact SHA and disposition are recorded
in the draft PR because a commit cannot contain its own hash. Ready transition and squash merge are
forbidden until owner approval and all required gates remain green at that same audited remote head.

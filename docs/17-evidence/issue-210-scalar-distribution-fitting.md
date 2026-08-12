# Issue #210 scalar distribution fitting evidence

## Boundary and implemented journey

Work started from fetched `origin/main`
`15df8a6e217359c7646e7cf6edb4d024e592abe7` on branch
`agent/issue-210-scalar-distribution-fitting` in the managed worktree
`C:\SourceCodes\cae-material-platform-issue210`. The original checkout and every other worktree
were left unchanged. Issue #210 was the first unfinished backlog unit; no open PR or existing local
or remote #210 branch owned the work.

Initial classification was complete for exact processed-replicate Selection, descriptive
Plan/Run/Result, immutable revision/Artifact storage, provenance and #205 Unit Profile pins; partial
for scalar extraction and recommendation/selection separation; and missing for distribution
contracts, calculations, persistence, selection revision, API and the mounted Modeling surface.

| Part | Issue-owned journey |
| --- | --- |
| Setup | Canonical synthetic DP780 data supplies one exact Selection of eight processed Dataset/Test Run revisions, an immutable Plan with seed 210 and 999 bootstrap refits, and a separate descriptive Statistical Result. |
| Actions | In Modeling → Process, open Replicate analysis → Distribution candidates, inspect the saved Selection/Plan/Run, compare all candidates, select Normal, enter an explicit reason, save, reload, and reopen the dock. |
| Visible outcome | Normal, Lognormal and Weibull expose support, parameters, AICc, delta AICc, BIC, AD, estimator-aware bootstrap p, refit counts, state and warnings. Recommendation and selected model remain visibly separate. |
| Persistence/read-back | A separate immutable Distribution Result revision/Artifact pins the descriptive Result revision, Plan, Selection, observations, Unit Profile applications and runtime manifest. A separate selected-model revision pins the exact candidate digest and reason; reload returns both. |
| Preserved state | Source Dataset/Test Run/Selection and descriptive Statistical Result revisions are not updated. Flagged outliers are retained. Every Run pins exact revisions, never `latest`. `ReferenceTensileWorkflow` remains unmounted. |
| Recovery | n<8, constants, missing/non-finite/censored values and candidate-specific support/numerical failures stay explicit without complete-case deletion. n=8–19 is retained with a small-sample warning. Failed candidates do not block successful candidates. |
| Forbidden shortcuts | No parallel statistics lifecycle, descriptive-result overwrite, source mutation, automatic outlier deletion, automatic production default, censored/mixture/Bayesian/hierarchical fitting, representative curve, new route, third inspector or revived legacy completion screen. |
| Exact acceptance | Deterministic replay/checksum, candidate recovery and negative states, typed immutable PostgreSQL storage, API/UI comparison plus selection/reload, runtime manifest integrity, canonical Compose, five viewports/crops, independent exact-SHA audit and Product Owner visual approval before ready/merge. |

## Approved statistical policy

The Product Owner approved `scalar_distribution_fitting_v1` before implementation:

- two-parameter maximum likelihood estimation for all candidates: Normal location/scale MLE;
  Lognormal and Weibull with `loc=0` fixed;
- log likelihood, AICc, BIC and Anderson–Darling, plus estimator-aware parametric bootstrap p-value;
- AICc as the primary comparison, with every candidate at `delta AICc <= 2` co-recommended and no
  hidden tie-breaker;
- exactly 999 bootstrap samples, an explicit stored seed, NumPy `PCG64` and fixed per-family
  sub-seeds;
- minimum `n=8`; n 8–19 carries a warning, while n<8 is not eligible.

All successful candidates use `k=2`. The mathematical definitions, support, Weibull solve tolerance,
AD CDF clamp, recovery tolerances and replay boundary are recorded in
[`scatter-statistics.md`](../09-analytics/scatter-statistics.md). These regression tolerances are not
material-acceptance thresholds or production defaults.

## Contract and persistence result

- HTTP/OpenAPI is `0.37.0`; the existing statistics schema adds versioned Distribution Result and
  selected-model resources without changing the descriptive Result schema.
- Existing Selection, Plan and Run are extended. A Plan carries enabled candidate families, seed,
  bootstrap count and optional exact Unit Profile pin. A scalar-distribution Run points to the same
  exact processed-replicate Selection and descriptive Result.
- Migration `20260929_098_issue210_scalar_distribution.py` adds typed aggregate/revision/observation/
  candidate/parameter/diagnostic and selected-model tables, exact-hash foreign keys, immutable
  triggers, forced RLS and the minimum cardinality/status guards. Downgrade removes only #210-owned
  state and restores the prior Run constraint.
- Canonical Result JSON bytes become a separate immutable Artifact. Stored provenance distinguishes
  `statistics.scalar_distribution_result` and `statistics.scalar_distribution_selection`, records
  exact descriptive Result and Plan usage before association finalization, and preserves generation
  activity and responsible agents.
- The runtime manifest records algorithm/schema, Python, NumPy, SciPy, RNG, source/lock/environment
  digests, seed and options. Byte-identical replay is required only when those inputs match.
- The mounted surface is a bounded two-pane dock inside the current
  `MaterialModelingWorkspace`. It resolves pinned revisions through immutable Dataset history,
  keeps historical processed Selections visible after a head advances, excludes normalized source
  Selections, reuses an exactly matching immutable Plan, and exposes exact evidence under Advanced.

Canonical Compose read-back recorded one n=8 Distribution Result revision with three candidates,
recommendations `normal | lognormal | weibull`, seed 210, 999 refits and `numpy.random.PCG64`. Its
Artifact SHA-256 was `50a314e2bf37b315e8228ff428dba22efe98f05fa1f0f0bb6f7dfe15915f6abc`.
The exact descriptive Result and Selection revisions remain separate pinned inputs.

## Verification record

| Gate | Result |
| --- | --- |
| Synthetic parameter recovery and deterministic replay/checksum | PASS — Normal, Lognormal and Weibull recovery plus same-input/options/runtime replay |
| Small sample, constant, invalid support, extreme range, missing/non-finite/censored and outlier states | PASS — candidate-specific `not_eligible`/`failed`, no observation deletion |
| Service/Artifact/provenance and descriptive-result non-mutation | PASS — focused unit and provenance regression included in 775 tests |
| API candidate comparison, selected-model create/revise/list/get and reload contract | PASS — integration suite and live browser |
| PostgreSQL migration up/down/up and immutable revision | PASS — PostgreSQL 16, 1 test, zero skips |
| Migration/static guards | PASS — 131 tests |
| Backend unit and architecture | PASS — 775 tests |
| Integration without PostgreSQL opt-in | PASS — 143 passed, 96 PostgreSQL tests skipped by declared DSN boundary |
| Contract lint and generated Python client | PASS — no generated drift |
| Full contract tests | BASELINE-ONLY FAILURES — 290 passed; three unchanged origin/main failures are root `AGENTS.md` byte budget, stale cold-start strings and #184 absolute worktree path |
| Python Ruff and changed-file mypy | PASS — 20 changed source/test files in mypy |
| Web scalar/chart focus and responsive tests | PASS — 22 focused tests |
| Full web tests | PASS — 63 files, 336 tests under the final single-worker rerun |
| Web production build and bundle | PASS — scalar distribution lazy chunk is within budget; inherited Materials warning remains below the hard limit |
| Canonical Compose | PASS — preflight/config, preserved-volume rebuild/recreate, migration/reference plugin/seed exit 0, healthy API/PostgreSQL and full demo verifier with three scalar candidates |
| User guide, documentation impact and whitespace | PASS — 100 current captures, 1,697 referenced images, zero orphans; 77 changed files/5 visual sources; clean diff check |
| Five viewport originals and fifteen 1:1 crops | PASS Main review and deterministic geometry; Product Owner approval pending |
| Independent exact-SHA Balanced audit | PENDING final commit |
| Product Owner visual approval | PENDING; Draft PR must not become ready or merge |

## Visual and accessibility acceptance

The registered packet is
[`visual-evidence.yaml`](images/issue-210-scalar-distribution-fitting/visual-evidence.yaml). Main opened
five exact-main before originals, five live after originals and fifteen direct 100%-pixel crops at
original resolution. Chromium 151 used browser zoom 100% and DPR 1. Page horizontal overflow is
zero at every viewport. Candidate-table overflow is local and reachable only at 1366/1440. At
1366×768, opening the explicit comparison disclosure temporarily yields only the Process settings
ribbon and retains a 372px persistent graph; closing restores the ribbon without changing its
persisted state.

Q01–Q03 pass: the existing local navigator, real overflow behavior, compact rows and exact revision
identities remain visible. Q04–Q11 pass: the graph stays dominant, its axes/legend are readable,
candidate controls use the existing flat-pane grammar, focus enters the dock, Escape returns to the
trigger and all actions are keyboard reachable. Q12–Q19 are not applicable because Export and
Administration are unchanged. Q20 passes deterministic geometry at 1920/2560/3840 with an elastic
graph, bounded readable comparison work area, no page overflow, CSS zoom, transform scaling or
route-specific 4K override.

The available Windows displays are 2560×1440 and 2560×1600; the Windows logical setting was 144 DPI
(150%). No physical 3840×2160 display was available. The 3840 CSS capture does not claim actual
physical 4K readability; that product-wide gate remains `DEFERRED_TO_223`. The Product Owner must
review the registered 1920/2560/3840 originals and crops before the PR can leave Draft.

## Publication state

Implementation pixels are from commit `bd8e76196c36eb10f9cdf5165e2f25f675053966`.
The Draft PR read-back records the final documentation/evidence commit, pre-publish result and
exact-SHA independent audit disposition without rewriting this pre-publication packet after its
audit. Any post-audit code or evidence correction requires the same independent auditor to review
the new exact SHA. Ready transition, squash merge, issue/backlog completion and routing to #212
remain blocked on direct Product Owner visual approval.

# Implementation Instructions

## Authority and safety

- Preserve the current branch and all worktree changes. Never use `git reset`, `git clean`, stash,
  checkout discard, or another operation that drops or hides work.
- Start new issues from latest main with `git pull --ff-only origin main`. Keep an active issue on its
  branch; do not reopen merged work or close a multi-unit issue before all its listed units finish.
- `docs/planning/backlog.md` is the baseline, issue order, and handoff router. Read it and the exact
  issue first. Use `rg` to locate only affected requirements, ADRs, contracts, tests, and product specs.
  Start architecture-decision lookup at [`adr/README.md`](adr/README.md).
  `IMPLEMENTATION_STATUS.md`, live code, and user guides describe implemented behavior. Do not bulk-read
  archives or incoming material; read or delete temporary input only when the backlog's temporary-input owner and
  exit condition authorize it.
- For schema-driven integration issues #204-#216 and #246, read the exact P/G rows in
  [`docs/requirements/schema-driven-requirement-traceability.md`](docs/requirements/schema-driven-requirement-traceability.md)
  and its linked source fixture before changing a contract or narrowing acceptance. Record and resolve a
  source/Issue mismatch instead of silently dropping it.
- Product language is **test data**, **selected model**, **review request**, and **solver card**. Keep
  UUIDs, hashes, Mapping Profile, Recipe/Batch, provenance, and checksums in Evidence, Advanced, or
  Administration.

## Work definition and acceptance

- A fresh task takes the first unfinished backlog unit and its dependencies. Before
  implementation, classify existing behavior as complete, partial, or missing and change only the
  missing bounded scope.
- For nontrivial work, record one realistic primary user journey: setup, actions, visible outcome,
  persistence/read-back outcome, preserved contract/state, recovery, owned scope, forbidden shortcuts,
  and exact acceptance. Keep negative and technical cases separate; use
  [`docs/testing/product-work-acceptance.md`](docs/testing/product-work-acceptance.md).
- Read the exact requirement and affected contract before domain, API, data, migration, or
  documentation. Update contracts before adapters; load visual references only for UI work.
- Run Compose, database, browser, reload, and viewport checks only when applicable; otherwise record N/A
  or deferred. Before Docker, run `make compose-preflight`, recreate canonical composition, and reject
  stale environments without deleting data.
- After failure, continue safe applicable checks while evidence remains valid. Stop only for unsafe or
  invalid evidence, record that boundary, diagnose related causes, revise observable pass conditions,
  and never replay unchanged instructions. After three failures, recheck authority, scope, journey,
  gates, and evidence.
- Stop for unresolved product decisions, missing authority, unsafe action, external blockers, or
  scope-changing ambiguity. Repeated Compose or test execution never substitutes for semantic diagnosis.
- Keep automation thin: one realistic high-value browser flow when applicable, lower-level regression
  tests for rules, and Docker preflight. Do not create a generic verification framework.

## Visual work

- Every user-visible React/CSS change, including a small copy, control, or layout edit, must apply the
  **mandatory #249 design synthesis**: Carbon-level hierarchy, COMSOL-style engineering task flow, and
  SAP-style responsive logic. Read its canonical interpretation in
  [`docs/product/frontend-ui-principles.md`](docs/product/frontend-ui-principles.md). Review and
  evidence must explicitly pass its three axes: information hierarchy, engineering task flow, and
  responsive/wide-screen composition. A passing test suite or close screenshot match does not replace
  this judgment.
- Production UI uses `.agents/skills/desktop-engineering-ui`, its selected inventory/manifest entry,
  original assets, affected contracts, and `docs/product/visual-acceptance-matrix.md`.
- When explicit current product-owner feedback conflicts with a registered visual reference, the owner
  feedback controls. Record the conflict and update the affected reference and manifest in the same
  bounded visual unit instead of reproducing a stale defect.
- Use `frontend-ui-engineering` for React/CSS, `web-design-guidelines` for explicit UI audits, and
  `webapp-testing` for browser evidence.
- For every user-visible React/CSS change, capture the live before/after state at 1366×768,
  1440×900, 1920×1080, 2560×1440, and 3840×2160 with browser zoom fixed at 100%. Open every image at
  original resolution and also provide 100%-pixel crops of the header, navigator, table/form controls,
  and graph or native preview where applicable. A scaled contact sheet alone is not approval evidence.
- The application shell uses the full viewport. Inside it, graphs, tables, and native previews may grow
  while extra space improves comparison or interaction; navigators, property forms, and prose retain
  readable bounds. A one-sided 1920 px work island, unrelated internal void, or tiny fixed-density UI at
  2560/3840 fails, as does uniformly stretching every row, sentence, form, or plot merely to fill space.
- Carryover requires before/after evidence, exact affected routes/states, no new page-specific workaround,
  and explicit product-owner disposition.
- Implement display tiers only through shared typography, control, row, spacing, pane, and plot tokens.
  Do not use route-specific 4K overrides, CSS `zoom`, blanket `transform: scale`, fabricated filler, or
  non-uniform SVG stretching. Automated viewport capture proves geometry, not physical readability.
- Check visibility, clipping, wrapping, exact identity/revision, interaction reachability, and layout bounds.
- Hidden text and measurements do not replace normal-surface usability.
- Present the original 1920/2560/3840 comparison to the product owner and do not merge before the owner checklist and visual geometry approval pass.
- See [frontend change review playbook](docs/repository/frontend-change-review-playbook.md) for the
  authoritative high-DPI policy and historical handoff.

## Domain invariants

- Raw bytes and released artifacts are immutable. Stable identities and immutable revisions are
  separate; runs and links pin concrete revisions, never `latest`.
- Preserve original unit text, normalized unit, and quantity semantics. Never delete outliers;
  candidate detection and adjudication are separate records.
- Every derived entity records input usage, generation activity, and responsible agents. A production
  solver card requires a Material Model IR revision. Exporters report exact, transformed, approximated,
  and unsupported mappings without silent defaults.
- Core code never imports domain plugin implementations. Organization/project authorization is enforced
  at service and database levels.

## Product and UX invariants

- Normal navigation is `Materials | Modeling | Activity`; `/materials` is home. The Materials Browse
  tree exposes Technical Data, Test Data, Simulation Data, and Solver Cards with their data items.
  Database/Profile/Table/Folder/Record and format definitions remain available in Administration;
  exact-revision links and keyboard browsing remain available in Materials.
- Materials is one explorer/result/datasheet workspace with results dominant. Modeling keeps a compact
  curve/process explorer and dominant persistent graph; use a shallow ribbon or disclosure, never a
  third inspector column.
- Prefer flat panes, alignment, and dividers before borders, radius, background, or shadow. Avoid nested
  cards, decorative gradients, repeated eyebrow labels, and non-status badges.
- Every engineering field has a decision consequence and UI contract or moves to Advanced/Evidence.
  Recommendation, selection, saved result, review, release, and artifact are distinct states. Upstream
  changes invalidate current pointers without mutating revisions.
- Materials rows, totals, and facet counts come from one server-scoped query. Condition-aware properties
  are not universal facets. Approved static HTML/CSS and registered images are authority for their exact
  target.

## Frontend architecture routing

- Any nontrivial change under `apps/web` also reads [`apps/web/AGENTS.md`](apps/web/AGENTS.md),
  [`docs/product/frontend-ui-principles.md`](docs/product/frontend-ui-principles.md), and
  [`docs/architecture/frontend-architecture.md`](docs/architecture/frontend-architecture.md), then
  runs `.agents/skills/material-platform-frontend-architecture` before implementation.
- Every child unit of issue #249 must read the parent issue and
  [`docs/planning/frontend-refactoring-roadmap.md`](docs/planning/frontend-refactoring-roadmap.md)
  from FE-00 through the active FE unit before changing code. Its review records pass/fail for the
  inherited contracts and runs the applicable earlier-unit guards; a child issue is never reviewed in
  isolation from #249.
- Preserve two primary frontend journeys: Materials search/browse to exact card download or Start
  Modeling, and exact Material/State/Test Data through Data, Process, Fit, explicit saved model, Export,
  solver-card creation, and Materials read-back. Do not replace missing context with `latest`, first-item,
  global-output, or another-session fallback.
- Issue #249 is an owner-approved cross-cutting program governed by
  [`docs/planning/frontend-refactoring-roadmap.md`](docs/planning/frontend-refactoring-roadmap.md).
  Its documentation unit does not authorize production React/CSS changes. Later units require a bounded
  issue and explicit owner priority and do not silently reorder unrelated domain backlog work.
- Do not add a new feature responsibility to the registered frontend hotspots without an issue-owned
  extraction plan or approved exception. Separate behavior-preserving structural movement from broad
  semantic visual normalization.

## Delivery and publication

- Implement one issue or clearly bounded subset and add the specified unit, integration, regression,
  and browser tests. Run only gates required by issue acceptance, affected contracts, selected skills,
  changed behavior, or hooks; resolve hook failures.
- A unit remains incomplete until delivery tracking is synchronized. Before merge, record its PR and
  next row; after merge, record PR, merge SHA, and next unit in the issue, update parent #117 when
  applicable, and keep a multi-unit issue open until every row finishes.
- User-visible React/CSS changes update the current guide, screenshot manifest, and required live
  screenshots. An `app.tsx` navigation change also updates the navigation contract. README/user-guide
  prose follows `docs/documentation-manifest.yaml` and its restrained Korean-humanizer hook.
- Before handoff, run affected tests, `uv run cmp-check-user-guide --root .`, `make docs-impact` (or
  `uv run cmp-check-doc-impact --root . --mode worktree` when Make is unavailable), and
  `git diff --check` when applicable.
- An edit or validation authorizes no commit, push, PR, ready transition, or merge. Each requires an
  explicit owner instruction for the named repository, branch, diff, and action; failure or scope
  expansion requires renewed authority.
- Before commit, fetch `origin/main`, confirm expected base/head/diff/paths, and inspect the pending diff.
  After commit and before publication, require a clean worktree, inspect the exact commit diff, and run
  `make pre-publish` (or `uv run cmp-pre-publish --root . --trigger manual`). A failed gate blocks
  publication. After push/PR, fetch and read back remote state. Immediately after merge and before the
  final report, synchronize delivery records and verify the remote `main` merge SHA.

## Do not decide TBD domain items

Do not select or imply a production tensile standard, material family, constitutive model, optimizer
policy, solver card, virtual specimen, or validation threshold. Use bounded synthetic non-production
references until the corresponding open decision is approved.

## Forbidden shortcuts

No generic EAV for core domain data, row-per-point storage for large curves, mutable raw/released keys,
hidden conversion/resampling/smoothing/manual curve edits, direct plugin database access, in-process
production plugin loading, silent solver approximation, unreviewed golden updates, or confidential test
data in source control.
